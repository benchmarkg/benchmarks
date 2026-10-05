"""F7 near-duplicate candidate generation and its threshold calibration (P1-S2-T05; 11-ai-features.md S F7).

    python -m tools.dedup candidates [PATH ...]   # candidate pairs among data/benchmarks/ and the named drafts
    python -m tools.dedup calibrate [--write]     # score the known-pair set; --write records the result

11 S F7: "Cheap candidate generation first -- normalised-name Jaccard, the alias table, embedding cosine
above a threshold, shared URL host plus path -- then model adjudication on only the couple of hundred
borderline pairs, returning `same | variant-of | distinct` with a reason." This module is the cheap
first stage. It never merges anything: a candidate is a pair for a person (or, later, the adjudicating
model) to look at, because SWE-bench, SWE-bench Verified and SWE-bench Pro are different benchmarks and
lineage is one of the project's differentiators. A pair whose lineage already relates them (one record's
`lineage` names the other: subset_of, variants, forks, supersedes, ...) has been adjudicated by a curator and
is never proposed. Any other pair is a candidate when any one signal fires:

  alias      a normalised name or alias of one record equals a normalised name or alias of the other
             (the alias table: each record's `aliases`, and data/aliases/benchmarks.yaml once it exists);
  url        the records share a site: the same host, and one URL's directory path is a prefix of the
             other's at a segment boundary. A code host (github.com and the like) needs owner and
             repository to match, and a catalogue host (arXiv, the benchmark directories) the whole
             path, because one host holds thousands of unrelated entries;
  name       the Jaccard similarity of the name tokens (the best pairing of names and aliases; tokens
             split where letters meet digits) is at least `name_jaccard`, or the names are equal once
             their edition and version tokens are removed (CASP14 and CASP17, ARC-AGI-2 and -3);
  cosine     the cosine similarity of the two records' identity text (names, aliases and titles) is at
             least `cosine_threshold`.

The cosine is not yet the static embedding 11 S4 specifies: `bench embed` (model2vec/potion) is not
built, and this module adds no dependency. It is a character n-gram (3 to 5) TF-IDF vector, fitted on the
records being compared: deterministic, dependency-free, and good at exactly what a name comparison needs
(shared stems, reordered words, punctuation variants). config/dedup.yaml names the scorer, so the
threshold is only ever read beside the scorer it was calibrated for; when the static embedding lands,
`calibrate --write` re-derives it.

The calibration is 11 S F7's: the known-pair set (tests/dedup/fixtures/known-pairs.yaml, 200 pairs
whose answer we already know) is scored at every cosine threshold from 0.80 to 0.95 in steps of 0.01,
and the threshold committed is the one that maximises recall subject to precision above 0.9, with both
numbers written into the file. Among thresholds of equal recall the highest is taken, since it proposes
the fewest pairs. The other signals are fixed while the cosine moves, so the precision and recall are
those of the whole candidate rule, not of the cosine alone; the ablation in the file shows what each
signal contributes.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import math
import os
import re
import sys
import unicodedata
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, 'config', 'dedup.yaml')
PAIRS = os.path.join(ROOT, 'tests', 'dedup', 'fixtures', 'known-pairs.yaml')
GRID = [round(0.80 + 0.01 * i, 2) for i in range(16)]            # 0.80 .. 0.95
DIAGNOSTIC_GRID = [round(0.10 + 0.05 * i, 2) for i in range(18)]  # 0.10 .. 0.95, reported only
PRECISION_FLOOR = 0.9
LABELS = ('same', 'variant-of', 'distinct')
POSITIVE = {'same', 'variant-of'}            # a candidate should be proposed; `distinct` should not
SIGNALS = ('alias', 'url', 'name', 'cosine')
SCORER = 'char-ngram-tfidf-v1'
NGRAMS = (3, 4, 5)


# ---- records ------------------------------------------------------------------------------------

@dataclass
class Record:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)      # a paper or page title: identity text, not prose
    related: set[str] = field(default_factory=set)       # ids this record's lineage names (already adjudicated)

    @classmethod
    def of(cls, d: dict) -> 'Record':
        return cls(d['id'], d['name'], list(d.get('aliases') or []), list(d.get('urls') or []),
                   list(d.get('titles') or []))

    @property
    def names(self) -> list[str]:
        return [self.name] + self.aliases

    @property
    def identity(self) -> str:
        return ' '.join(self.names + self.titles)


def from_benchmark(raw: dict, rid: str | None = None) -> Record:
    """A Record from a Benchmark (or BenchmarkDraft) YAML mapping."""
    urls = [raw.get(k) for k in ('homepage', 'repository', 'leaderboard_url', 'dataset_url')]
    paper = raw.get('paper') if isinstance(raw.get('paper'), dict) else {}
    return Record(rid or raw['id'], raw.get('name') or raw['id'], [a for a in raw.get('aliases') or [] if a],
                  [u for u in urls if u], [paper['title']] if paper.get('title') else [], lineage_ids(raw))


LINEAGE_ONE = ('subset_of', 'decontaminates')
LINEAGE_MANY = ('supersedes', 'superseded_by', 'extended_by')
LINEAGE_ENTRIES = ('variants', 'forks')


def lineage_ids(raw: dict) -> set[str]:
    """The benchmark ids a record's lineage declares. A declared edge is a curator's answer to the question a
    candidate asks -- 11 S F7's `variant-of` -- so the pair is not proposed again."""
    lin = raw.get('lineage') if isinstance(raw.get('lineage'), dict) else {}
    out = {lin[k] for k in LINEAGE_ONE if isinstance(lin.get(k), str)}       # get-default: optional fields
    out |= {x for k in LINEAGE_MANY for x in (lin.get(k) or []) if isinstance(x, str)}     # get-default: as above
    out |= {e['id'] for k in LINEAGE_ENTRIES for e in (lin.get(k) or []) if isinstance(e, dict) and e.get('id')}  # get-default
    return out


# ---- the signals --------------------------------------------------------------------------------

def normalise_name(s: str) -> str:
    """Casefolded, accents and punctuation removed, whitespace collapsed: 'SWE-Bench  Pro' -> 'swe bench pro'."""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).casefold()
    return ' '.join(re.sub(r'[^0-9a-z]+', ' ', s).split())


def tokens(s: str) -> set[str]:
    """Name tokens, split where letters meet digits: 'CASP14' -> {'casp', '14'}."""
    return set(re.sub(r'(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])', ' ', normalise_name(s)).split())


VERSION = re.compile(r'^(?:v?\d+|\d+(?:st|nd|rd|th))$')


def stem(s: str) -> str:
    """The name without its edition or version tokens: 'CASP14' -> 'casp', 'Terminal-Bench 2.0' -> 'terminal bench'."""
    return ' '.join(t for t in sorted(tokens(s)) if not VERSION.match(t))


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def name_jaccard(a: Record, b: Record) -> float:
    return max(jaccard(tokens(x), tokens(y)) for x in a.names for y in b.names)


def same_stem(a: Record, b: Record) -> bool:
    """Two editions or versions of one name (CASP14 and CASP17, ARC-AGI-2 and ARC-AGI-3)."""
    return bool({stem(x) for x in a.names} & {stem(y) for y in b.names} - {''})


def alias_hit(a: Record, b: Record) -> bool:
    return bool({normalise_name(x) for x in a.names} & {normalise_name(y) for y in b.names} - {''})


CODE_HOSTS = ('github.com', 'gitlab.com', 'huggingface.co', 'bitbucket.org', 'kaggle.com')
CATALOGUE_HOSTS = ('arxiv.org', 'doi.org', 'openreview.net', 'aclanthology.org', 'benchmark-radar.org',
                   'benchmarklist.com', 'paperswithcode.com', 'zenodo.org', 'figshare.com')


# A section that holds many unrelated things: two pages under it are not one site's family.
GENERIC_SECTIONS = {'en', 'docs', 'doc', 'blog', 'posts', 'news', 'benchmarks', 'projects', 'research', 'gr',
                    'pub', 'papers', 'datasets', 'leaderboard', 'leaderboards', 'events', 'challenges'}
FILE = re.compile(r'\.(?:html?|php|aspx?|cgi|md|pdf)$', re.I)


def url_key(url: str) -> tuple[str, tuple[str, ...], str]:
    """(host, directory segments, kind). On an ordinary site a last segment that is a file is dropped,
    so swebench.com/verified.html and swebench.com/lite.html are one site; so are a trailing `latest`
    or `index`. A catalogue or code host keeps its whole path: arxiv.org/abs/2406.01574 is an entry,
    and its id is not a file name."""
    p = urllib.parse.urlsplit(url.strip())
    host = p.netloc.lower().split('@')[-1].split(':')[0].removeprefix('www.')
    segs = [s for s in p.path.split('/') if s]
    kind = 'code' if host in CODE_HOSTS else 'catalogue' if host in CATALOGUE_HOSTS else 'site'
    if kind == 'site':
        if segs and FILE.search(segs[-1]):
            segs = segs[:-1]
        while segs and segs[-1] in ('latest', 'index'):
            segs = segs[:-1]
    return host, tuple(segs), kind


def same_site(u: str, v: str) -> bool:
    """One site: the same host, and either one directory path is a prefix of the other, or both sit
    under the same first section (crfm.stanford.edu/helm/lite and /helm/safety) when that section is
    not a generic one. A code host needs owner and repository; a catalogue host the whole path."""
    (h1, s1, kind), (h2, s2, _) = url_key(u), url_key(v)
    if h1 != h2 or not h1:
        return False
    if kind == 'code':
        return len(s1) >= 2 and s1[:2] == s2[:2]
    if kind == 'catalogue':
        return s1 == s2 and bool(s1)
    short, long_ = sorted((s1, s2), key=len)
    if long_[:len(short)] == short:
        return True
    return (len(s1) >= 2 and len(s2) >= 2 and s1[0] == s2[0] and s1[0] not in GENERIC_SECTIONS
            and not re.fullmatch(r'\d{4}', s1[0]))


def url_match(a: Record, b: Record) -> bool:
    return any(same_site(u, v) for u in a.urls for v in b.urls)


class Vectors:
    """Character n-gram TF-IDF over the records' identity text, fitted on the records given."""

    def __init__(self, records: list[Record]):
        grams = {r.id: self._grams(r.identity) for r in records}
        df = Counter(g for gs in grams.values() for g in set(gs))
        n = len(records)
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1 for g, c in df.items()}
        self.vec = {rid: self._weigh(gs) for rid, gs in grams.items()}

    @staticmethod
    def _grams(text: str) -> Counter:
        t = ' %s ' % normalise_name(text)
        return Counter(t[i:i + n] for n in NGRAMS for i in range(len(t) - n + 1))

    def _weigh(self, grams: Counter) -> dict[str, float]:
        w = {g: (1 + math.log(c)) * self.idf[g] for g, c in grams.items()}
        norm = math.sqrt(sum(x * x for x in w.values())) or 1.0
        return {g: x / norm for g, x in w.items()}

    def cosine(self, a: str, b: str) -> float:
        va, vb = self.vec[a], self.vec[b]
        if len(va) > len(vb):
            va, vb = vb, va
        return sum(x * vb.get(g, 0.0) for g, x in va.items())


@dataclass(frozen=True)
class Scored:
    a: str
    b: str
    alias: bool
    url: bool
    name: float
    cosine: float
    stem: bool = False

    def fires(self, cfg: dict, without: str | None = None) -> list[str]:
        on = {'alias': self.alias, 'url': self.url, 'name': self.stem or self.name >= cfg['name_jaccard'],
              'cosine': self.cosine >= cfg['cosine_threshold']}
        return [s for s in SIGNALS if on[s] and s != without]


def score(a: Record, b: Record, vectors: Vectors) -> Scored:
    return Scored(a.id, b.id, alias_hit(a, b), url_match(a, b), round(name_jaccard(a, b), 4),
                  round(vectors.cosine(a.id, b.id), 4), same_stem(a, b))


def candidates(records: list[Record], cfg: dict) -> list[tuple[Scored, list[str]]]:
    """Every pair at least one signal proposes, with the signals that fired."""
    vectors = Vectors(records)
    out = []
    for a, b in combinations(records, 2):
        if b.id in a.related or a.id in b.related:          # lineage already says what the pair is
            continue
        s = score(a, b, vectors)
        fired = s.fires(cfg)
        if fired:
            out.append((s, fired))
    return out


# ---- calibration --------------------------------------------------------------------------------

def load_pairs(path: str = PAIRS) -> tuple[dict[str, Record], list[dict]]:
    from schema.taxonomy import read_yaml
    d = read_yaml(path)
    return {r['id']: Record.of(r) for r in d['records']}, list(d['pairs'])


def file_sha256(path: str) -> str:
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read().replace(b'\r\n', b'\n')).hexdigest()


def confusion(scored: list[tuple[Scored, str]], cfg: dict, without: str | None = None) -> dict:
    tp = fp = fn = tn = 0
    for s, label in scored:
        proposed, positive = bool(s.fires(cfg, without)), label in POSITIVE
        tp += proposed and positive
        fp += proposed and not positive
        fn += positive and not proposed
        tn += not positive and not proposed
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {'precision': round(precision, 4), 'recall': round(recall, 4), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}


def calibrate(cfg: dict, path: str = PAIRS) -> dict:
    """The calibration record config/dedup.yaml carries, computed from the known-pair set."""
    records, pairs = load_pairs(path)
    vectors = Vectors(list(records.values()))       # IDF over the calibration records, as over a corpus
    scored = [(score(records[p['a']], records[p['b']], vectors), p['label']) for p in pairs]
    grid = []
    for t in GRID:
        c = confusion(scored, dict(cfg, cosine_threshold=t))
        grid.append(dict(threshold=t, **c))
    ok = [g for g in grid if g['precision'] > PRECISION_FLOOR]
    chosen = dict(max(ok, key=lambda g: (g['recall'], g['threshold']))) if ok else None
    labels = Counter(p['label'] for p in pairs)
    out = {
        'pairs': os.path.relpath(path, ROOT).replace(os.sep, '/'),
        'pairs_sha256': file_sha256(path),
        'n_pairs': len(pairs),
        'labels': {k: labels.get(k, 0) for k in LABELS},
        'rule': 'maximise recall subject to precision > %.1f over cosine thresholds %.2f..%.2f step 0.01; '
                'ties go to the higher threshold' % (PRECISION_FLOOR, GRID[0], GRID[-1]),
        'chosen': chosen,
        'grid': grid,
    }
    if chosen:
        at = dict(cfg, cosine_threshold=chosen['threshold'])
        out['ablation'] = {'without_%s' % s: {k: v for k, v in confusion(scored, at, s).items()
                                              if k in ('precision', 'recall')} for s in SIGNALS}
    # Not used for the choice: where THIS scorer's cosine separates, which is far below 11 S F7's grid
    # (set for a static embedding, whose cosines sit high). Shown so the grid can be revisited by decision.
    out['diagnostic_grid'] = [dict(threshold=t, **{k: v for k, v in confusion(scored, dict(cfg, cosine_threshold=t))
                                                  .items() if k in ('precision', 'recall')})
                              for t in DIAGNOSTIC_GRID]
    return out


# ---- config -------------------------------------------------------------------------------------

def load_config(path: str = CONFIG) -> dict:
    from schema.taxonomy import read_yaml
    return read_yaml(path)


HEADER = """\
# config/dedup.yaml -- F7 near-duplicate candidate generation (P1-S2-T05; 11-ai-features.md S F7).
#
# 11 S F7: "The cosine threshold is 0.88 as a starting value, not a constant. It lives in
# config/dedup.yaml with its calibration record ... the value committed is the one that maximises
# recall subject to precision above 0.9 on that set, with both numbers written into the file."
#
# `cosine_threshold` is derived, never hand-edited: `python -m tools.dedup calibrate --write` computes
# it from the known-pair set and rewrites the `calibration` block, and
# tests/dedup/test_threshold_calibration.py fails if the file and a fresh calibration disagree.
# The threshold holds only for `scorer`; a new scorer (the static embedding of 11 S4) is recalibrated.
# `name_jaccard` is set, not calibrated, and so are tools/dedup.py's host lists; the ablation shows what
# each signal adds, and `diagnostic_grid` where this scorer's cosine would start to contribute.
"""


def write_config(cfg: dict, path: str = CONFIG) -> str:
    from tools import fmt
    cal = calibrate(cfg)
    if cal['chosen'] is None:
        raise SystemExit('no cosine threshold in %.2f..%.2f reaches precision > %.1f on the known pairs; '
                         'nothing written' % (GRID[0], GRID[-1], PRECISION_FLOOR))
    out = {
        'schema_version': 1,
        'scorer': SCORER,
        'scorer_note': 'character n-gram (%s) TF-IDF cosine over names, aliases and titles; a stand-in for the '
                       'static embedding of 11 S4, which is not built yet' % '-'.join(map(str, (NGRAMS[0], NGRAMS[-1]))),
        'cosine_threshold': cal['chosen']['threshold'],
        'name_jaccard': cfg['name_jaccard'],
        'calibration': dict(cal, calibrated_on=cfg.get('calibration', {}).get('calibrated_on') or _today()),
    }
    text = fmt.format_text(HEADER + fmt.dumps(out), None, 'config/dedup.yaml')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return text


def _today() -> str:
    import datetime
    return datetime.date.today().isoformat()


# ---- CLI ----------------------------------------------------------------------------------------

def corpus_records(paths: list[str]) -> list[Record]:
    from schema.taxonomy import read_yaml
    from schema.stub import curated_benchmark_files
    files = curated_benchmark_files(ROOT)                   # stubs are proposals; pass _stubs/ as a path to compare them
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, '**', '*.yaml'), recursive=True)) if os.path.isdir(p) else [p]
    out = []
    for f in files:
        raw = read_yaml(f)
        if isinstance(raw, dict) and isinstance(raw.get('id'), str) and 'curation' in raw:
            rel = os.path.relpath(f, ROOT).replace(os.sep, '/')
            out.append(from_benchmark(raw, rel if rel.startswith('drafts/') or not rel.startswith('data/')
                                      else raw['id']))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='python -m tools.dedup', description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('candidates', help='candidate pairs among data/benchmarks/ and the named drafts')
    c.add_argument('paths', nargs='*')
    k = sub.add_parser('calibrate', help='score the known-pair set at every threshold')
    k.add_argument('--write', action='store_true', help='rewrite config/dedup.yaml with the result')
    a = ap.parse_args(argv)
    cfg = load_config()
    if a.cmd == 'candidates':
        for s, fired in candidates(corpus_records(a.paths), cfg):
            print('%s  <->  %s   [%s]  name %.2f  cosine %.2f' % (s.a, s.b, ', '.join(fired), s.name, s.cosine))
        return 0
    if a.write:
        print(write_config(cfg), end='')
        return 0
    cal = calibrate(cfg)
    for g in cal['grid']:
        print('%.2f  precision %.3f  recall %.3f  (tp %d fp %d fn %d tn %d)' % (
            g['threshold'], g['precision'], g['recall'], g['tp'], g['fp'], g['fn'], g['tn']))
    print('chosen:', cal['chosen'])
    return 0


if __name__ == '__main__':
    sys.path.insert(0, ROOT)
    sys.exit(main())
