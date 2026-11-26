"""The retrieval configurations the harness pools and grades (P6-S3-T09; 11-ai-features.md S7 "Where the items come
from", 11 S4 "The pipeline", 08 S5.7 "The fusion order").

TREC-style pooling (11 S7): "for each query, run the retrieval pipeline in several configurations, take the union of
the top 20, and grade that pool of roughly 40-60 candidates rather than the whole corpus." The configurations are the
pipeline's own pieces, each run on the query text as typed, with no model call anywhere:

  lexical        the site's BM25 leg (site/src/islands/search/lexical.ts, P6-S1-T04) over facets.json's name, aliases,
                 editions and id, run by Node through tools/evals/lexical_runs.mjs, so the harness grades the code the
                 site ships rather than a second BM25.
  lexical-wide   the same leg over the five fields 11 S4 names and the tagline, the fields lexical.ts leaves out for
                 facets.json's size budget (lexical_runs.mjs says how). A pooling configuration: the site does not
                 run it, and it finds the entries a query describes rather than names.
  dense          cosine similarity between the query's potion-base-8M embedding and the dequantised int8 document
                 matrix `bench build --embed` writes (tools/build/embed.py, P6-S1-T03), restricted to nothing. The
                 query is encoded in Python with the full model; the site's query-side encoder (P6-S1-T01) is not
                 built, so this is the semantic tier as 11 S4 designs it, not as a browser runs it yet.
  fused          reciprocal rank fusion at k = 60 of lexical and dense, 08 S5.7 step 4 exactly as site/src/lib/query.ts
                 computes it (score = sum of 1 / (k + rank), ranks from 1, equal scores by row): the pipeline 11 S4
                 describes, minus the F1 facet query.

A configuration that cannot run says why and the run goes on without it: lexical needs Node and `npm ci` in site/
(minisearch); dense and fused need the `embed` extra and the pinned model in the local cache (`uv run --extra embed
python -m tools.build.embed --fetch`). The results file names every configuration with `ran` and, if not, the reason,
so a pool is never mistaken for one built from more configurations than it was.

The configurations that need a model -- F1 writing the facet query that filters and boosts, then the same fusion --
are the Batch API run's (tools/evals/batch.py), which refuses without a key.

The corpus. No entry is published yet (05 S4), so the published corpus is empty and nothing could be retrieved from
it. The run reads the catalogue as scripts/preview_corpus.py does, the drafts that pass tier 1 included
(tools/build/artifacts.py build(drafts=True)), and every results file says `"drafts": true`. Gold labels name entries
under data/benchmarks/ (P6-S3-T08's label_shape), so that is the population they can be graded against. Whether the
harness moves to the published corpus once one exists is the maintainer's decision; CORPUS_DRAFTS is the switch.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lexical_runs.mjs')
MINISEARCH = os.path.join('site', 'node_modules', 'minisearch')
CORPUS_DRAFTS = True
RRF_K = 60                       # site/src/lib/query.ts RRF_K (08 S5.7)
POOL_DEPTH = 20                  # 11 S7: "the union of the top 20"
CONFIGURATIONS = ('lexical', 'lexical-wide', 'dense', 'fused')
DESCRIBES = {
    'lexical': "the site's BM25 leg over name, aliases, editions and id (site/src/islands/search/lexical.ts)",
    'lexical-wide': "the site's BM25 leg over 11 S4's five fields and the tagline (tools/evals/lexical_runs.mjs)",
    'dense': 'potion-base-8M query cosine over the dequantised int8 document matrix (tools/build/embed.py)',
    'fused': 'reciprocal rank fusion, k = 60, of lexical and dense (site/src/lib/query.ts rrf)',
}


class RetrievalError(Exception):
    """The corpus could not be built; nothing can be pooled."""


@dataclass
class Corpus:
    rows: list[dict]                                 # facets.json benchmarks, in facets.json order: row numbers
    records: dict[str, dict]                         # entry id -> its corpus.json benchmark record
    drafts: bool
    facets: dict = field(default_factory=dict)       # the whole facets.json document (dense needs its format)
    corpus: dict = field(default_factory=dict)       # the whole corpus.json document

    @property
    def ids(self) -> list[str]:
        return [r['id'] for r in self.rows]


@dataclass
class Run:
    """One configuration over every query: query id -> [(row, score)], best first; or why it did not run."""
    name: str
    ranked: dict[str, list[tuple[int, float]]] | None = None
    reason: str | None = None

    @property
    def ran(self) -> bool:
        return self.ranked is not None

    def ids(self, corpus: Corpus, query: str) -> list[str]:
        return [corpus.rows[r]['id'] for r, _ in (self.ranked or {}).get(query, [])]   # get-default: a query the run did not see ranks nothing

    def describe(self) -> dict:
        out = {'name': self.name, 'describes': DESCRIBES[self.name], 'ran': self.ran}
        if not self.ran:
            out['reason'] = self.reason
        return out


def build_corpus(root: str = ROOT, drafts: bool = CORPUS_DRAFTS) -> Corpus:
    from tools.build import artifacts
    result = artifacts.build(root, drafts=drafts)
    if result.errors:
        raise RetrievalError('the catalogue does not build: %s' % '; '.join(str(e) for e in result.errors[:5]))
    records = {b['id']: b for b in result.corpus['entities']['benchmark']}
    return Corpus(rows=list(result.facets['benchmarks']), records=records, drafts=drafts, facets=result.facets,
                  corpus=result.corpus)


# ---- lexical, through the site's leg ----------------------------------------------------------------------------

def lexical_rows(corpus: Corpus) -> list[dict]:
    """What lexical_runs.mjs reads of each row: facets.json's text fields and corpus.json's tagline, description and
    governance.maintainer."""
    out = []
    for r in corpus.rows:
        rec = corpus.records.get(r['id']) or {}          # get-default: a row with no record adds no wide text
        gov = rec.get('governance') or {}                # get-default: governance is optional on a record
        out.append({'id': r['id'], 'name': r['name'], 'aliases': list(r['aliases']), 'editions': list(r['editions']),
                    'tagline': rec.get('tagline') or '', 'description': rec.get('description') or '',
                    'maintainer': gov.get('maintainer') or ''})
    return out


def lexical(corpus: Corpus, queries: dict[str, str], root: str = ROOT, node: str | None = None) -> list[Run]:
    """lexical and lexical-wide, or both refused with the reason."""
    names = ('lexical', 'lexical-wide')
    node = node or shutil.which('node')
    if node is None:
        return [Run(n, reason='Node is not on PATH (the site runs Node 24)') for n in names]
    if not os.path.isdir(os.path.join(root, MINISEARCH)):
        return [Run(n, reason='%s is missing: run `npm ci` in site/' % MINISEARCH.replace(os.sep, '/')) for n in names]
    request = {'rows': lexical_rows(corpus), 'queries': [{'id': q, 'text': t} for q, t in queries.items()],
               'configurations': list(names)}
    done = subprocess.run([node, BRIDGE], input=json.dumps(request), capture_output=True, text=True,
                          encoding='utf-8', cwd=root)
    if done.returncode != 0:
        why = (done.stderr.strip().splitlines() or ['exit %d' % done.returncode])[-1]
        return [Run(n, reason='tools/evals/lexical_runs.mjs failed: %s' % why) for n in names]
    answer = json.loads(done.stdout)
    return [Run(n, ranked={q: [(int(r), float(s)) for r, s in answer[n][q]] for q in queries}) for n in names]


# ---- dense, through tools/build/embed.py ------------------------------------------------------------------------

def dense(corpus: Corpus, queries: dict[str, str], encoder=None) -> Run:
    """Each query's unit embedding dotted with every dequantised document row, best first, equal scores by row: the
    cosine to within the quantiser's row fidelity (tools/build/embed.py TOLERANCE), computed as the site's loop
    computes it, over the rows as dequantised and not renormalised."""
    try:
        from tools.build import embed               # numpy, at the embed extra's pin
    except ImportError as e:
        return Run('dense', reason='tools/build/embed.py does not import (%s): uv run --extra embed' % e)
    try:
        enc = encoder or embed.encoder()
        vectors = embed.build(corpus.corpus, corpus.facets, enc)
    except embed.EmbedError as e:
        return Run('dense', reason='needs the `embed` extra and the pinned model in the local cache: `uv run --extra '
                                   'embed bench eval`, after `%s` once (tools/build/embed.py: %s)' % (embed.FETCH, e))
    import numpy as np
    docs = embed.dequantise(vectors.q, vectors.scales).astype(np.float64)
    ids = list(queries)
    if not ids or not len(docs):
        return Run('dense', ranked={q: [] for q in ids})
    qv = np.asarray(enc.encode([queries[q] for q in ids]), dtype=np.float64)
    qv /= np.maximum(np.linalg.norm(qv, axis=1, keepdims=True), 1e-12)
    sims = qv @ docs.T
    ranked = {}
    for i, q in enumerate(ids):
        ranked[q] = sorted(((r, float(s)) for r, s in enumerate(sims[i])), key=lambda x: (-x[1], x[0]))
    return Run('dense', ranked=ranked)


# ---- fused --------------------------------------------------------------------------------------------------------

def rrf(lists: list[list[tuple[int, float]]], k: int = RRF_K) -> list[tuple[int, float]]:
    """site/src/lib/query.ts rrf: score(d) = the sum over the lists of 1 / (k + rank(d)), best first, ties by row."""
    score: dict[int, float] = {}
    for ranked in lists:
        for i, (row, _) in enumerate(ranked):
            score[row] = score.get(row, 0.0) + 1 / (k + i + 1)   # get-default: a row's first list starts its sum
    return sorted(score.items(), key=lambda x: (-x[1], x[0]))


def fused(lex: Run, den: Run) -> Run:
    if not (lex.ran and den.ran):
        return Run('fused', reason='fusion needs both lexical and dense: %s'
                   % '; '.join('%s did not run' % r.name for r in (lex, den) if not r.ran))
    return Run('fused', ranked={q: rrf([lex.ranked[q], den.ranked[q]]) for q in lex.ranked})


def runs(corpus: Corpus, queries: dict[str, str], root: str = ROOT) -> list[Run]:
    """Every configuration in CONFIGURATIONS order, each run or refused."""
    lex, wide = lexical(corpus, queries, root)
    den = dense(corpus, queries)
    return [lex, wide, den, fused(lex, den)]


# ---- the pool -----------------------------------------------------------------------------------------------------

def pool(corpus: Corpus, configurations: list[Run], query: str, depth: int = POOL_DEPTH) -> list[dict]:
    """The union of every configuration's top `depth` for one query: each entry with the configurations that put it
    there and its best rank, best rank first, then by id."""
    seen: dict[str, dict] = {}
    for run in configurations:
        if not run.ran:
            continue
        for rank, ident in enumerate(run.ids(corpus, query)[:depth], start=1):
            entry = seen.setdefault(ident, {'id': ident, 'best_rank': rank, 'configurations': []})
            entry['best_rank'] = min(entry['best_rank'], rank)
            entry['configurations'].append(run.name)
    return sorted(seen.values(), key=lambda e: (e['best_rank'], e['id']))
