"""`bench eval`: pool, grade and publish the golden set (P6-S3-T09; 11-ai-features.md S7; 05 S3 and S9).

    uv run bench eval [--split <name>|all] [--report] [--judge] [--holdout N]

One run, in order:

  1. the golden set (tools/evals/golden.py): evals/golden/, refused whole while scripts/check_golden_composition.py
     reports anything; `--split` selects nl_search, facet_translation, suite_build, abstention or all four;
     `--holdout N` names the N-item test split, scored but never tuned on, and every metric is then published for
     train and test apart (11 S7);
  2. the pool (tools/evals/retrieval.py): for every item of a split whose gold names entries (nl_search and
     suite_build), each retrieval configuration's top 20, unioned. That is what a person grades, and its size against
     items x corpus is the grading cost pooling bounds (11 S7: "Without pooling ... it is unbounded");
  3. the grades (tools/evals/metrics.py): every labelled nl_search item against every configuration that ran --
     Recall@20 on grade 3, nDCG@10, the must-include violation rate -- each with its Wilson interval and its verdict
     against 11 S7's bar (tools/evals/stats.py). Each is published for the whole split and for each population 11 S7
     separates: generated against harvested and adversarial items, and train against test under --holdout. The
     model-dependent metrics (facet_translation's macro-F1, over-constraint and enum canary; abstention's
     correct-abstention rate; suite_build's four) are graded by the same code from the Batch API run's outputs
     (`evaluate(outputs=...)`), and are reported as not run, with the reason, while that run refuses
     (tools/evals/batch.py);
  4. the results file, evals/results/<date>-<commit>.json (11 S7, 05 S2): the date the run was made, the first eight
     hex digits of HEAD, and inside, the full commit, whether the tree was clean, the corpus, every configuration with
     whether it ran, the pools, the holdout, the model run's status and every metric. It is written only when
     something was graded. With no gold label set there is no measurement to publish, and the run says so plainly
     rather than printing a number: every gold label in evals/golden/ is null until a person sets it (P6-S3-T08).

--report prints the whole of it as Markdown, the pool to grade included; without it the run prints a summary.
--judge asks for the LLM-as-judge pass, which refuses (tools/evals/batch.py says why) and never gates.

Exit codes: 0 the run completed, whatever it could grade; 1 the golden set or the corpus is broken; 2 a usage error.
Gating a release on the verdicts is P6-S6-T04's scripts/check_eval_gates.py, which reads the results file.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess

from tools.evals import batch, golden, metrics, retrieval
from tools.evals.stats import APPROXIMATION, METHOD

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = 'evals/results'
FORMAT = 1
POOLED = ('nl_search', 'suite_build')          # the splits whose gold labels name entries
SMOKE_TEST_N = 200                             # 11 S7: facet_translation is a smoke test below n = 200
DISCLOSURES = [
    'Self-grading: the gold labels are written by the maintainers, who also wrote the taxonomy and the prompts '
    '(11 S7 "Who judges, stated honestly"). The gold sets are published so that anyone can dispute an item.',
    'Only deterministic metrics gate a release; a judge score never does (11 S7).',
]
DRAFTS = ('The corpus is the catalogue with its drafts (`corpus.drafts`), because no entry is published yet; the site '
          'retrieves over published entries only.')


class UsageError(ValueError):
    """A --split or --holdout the golden set cannot satisfy."""


class EvalError(Exception):
    """The run cannot start; `errors` says why, one line each."""

    def __init__(self, errors: list[str]):
        super().__init__('\n'.join(errors))
        self.errors = errors


def select(split: str) -> list[str]:
    if split == 'all':
        return list(golden.SPLITS)
    if split not in golden.SPLITS:
        raise UsageError('--split %r: give one of %s, or all' % (split, ', '.join(golden.SPLITS)))
    return [split]


def git(root: str) -> tuple[str, str]:
    """(HEAD's full sha or 'unknown', 'clean', 'dirty' or 'unknown')."""
    def run(*args):
        return subprocess.run(['git', '-c', 'core.longpaths=true', *args], cwd=root, capture_output=True, text=True,
                              encoding='utf-8')
    try:
        head, porcelain = run('rev-parse', 'HEAD'), run('status', '--porcelain')
    except OSError:
        return 'unknown', 'unknown'
    sha = head.stdout.strip() if head.returncode == 0 else 'unknown'
    tree = 'unknown' if porcelain.returncode != 0 else 'dirty' if porcelain.stdout.strip() else 'clean'
    return sha, tree


def results_path(root: str, date: _dt.date, commit: str) -> str:
    return os.path.join(root, *RESULTS.split('/'), '%s-%s.json' % (date.isoformat(), commit[:8]))


# ---- populations ------------------------------------------------------------------------------------------------

def populations(items: list[dict], test: set[str]) -> dict[str, list[dict]]:
    """name -> its labelled items: all; generated and not-generated (11 S7); train and test under --holdout."""
    out = {'all': items}
    for name in ('generated', 'not-generated'):
        out[name] = [it for it in items if golden.population(it) == name]
    if test:
        out['train'] = [it for it in items if it['id'] not in test]
        out['test'] = [it for it in items if it['id'] in test]
    return {k: v for k, v in out.items() if v}


# ---- the run ------------------------------------------------------------------------------------------------------

def evaluate(root: str = ROOT, splits: list[str] | None = None, holdout: int = 0, judge: bool = False,
             env: dict | None = None, today: _dt.date | None = None, outputs: dict | None = None,
             corpus: retrieval.Corpus | None = None, configurations=None) -> dict:
    """The results document (module docstring). `outputs` is the model run's answers by split and item id (none
    today); `corpus` and `configurations` (a function (corpus, queries) -> [Run]) replace the build and the retrieval
    runs, which the tests do."""
    splits = splits or list(golden.SPLITS)
    try:
        docs, ctx = golden.load(root)
    except golden.GoldenError as e:
        raise EvalError(e.errors) from None
    try:
        test = set(golden.holdout(docs, splits, holdout))
    except ValueError as e:
        raise UsageError(str(e)) from None
    outputs = outputs or {}
    commit, tree = git(root)
    doc = {'artifact': 'eval-results', 'format': FORMAT, 'set_version': docs[splits[0]]['set_version'],
           'date': (today or _dt.date.today()).isoformat(), 'commit': commit, 'tree': tree, 'splits': {},
           'corpus': None, 'configurations': [], 'pool': None,
           'holdout': {'n': len(test), 'method': 'N shared over the splits by size, then the lowest sha256 of the item '
                                                  'id (tools/evals/golden.py)', 'test': sorted(test)},
           'interval': {'method': METHOD, 'note': APPROXIMATION}, 'results': {}, 'not_measured': {},
           'disclosures': list(DISCLOSURES)}
    for s in splits:
        d = docs[s]
        doc['splits'][s] = {'items': len(d['items']), 'labelled': len(golden.labelled(d)),
                            'labelled_by': d['labelled_by'], 'labelled_against': d['labelled_against']}

    # ---- 2. the pool ----------------------------------------------------------------------------------------------
    pooled = [s for s in splits if s in POOLED]
    queries = {it['id']: it['query'] for s in pooled for it in docs[s]['items']}
    runs: list[retrieval.Run] = []
    if queries:
        try:
            corpus = corpus or retrieval.build_corpus(root)
        except retrieval.RetrievalError as e:
            raise EvalError([str(e)]) from None
        runs = (configurations or (lambda c, q: retrieval.runs(c, q, root)))(corpus, queries)
        doc['corpus'] = {'drafts': corpus.drafts, 'benchmarks': len(corpus.rows)}
        if corpus.drafts:
            doc['disclosures'].append(DRAFTS)
        doc['configurations'] = [r.describe() for r in runs]
        items = {q: retrieval.pool(corpus, runs, q) for q in queries}
        judgments = sum(len(p) for p in items.values())
        doc['pool'] = {'depth': retrieval.POOL_DEPTH, 'configurations': [r.name for r in runs if r.ran],
                       'judgments': judgments, 'without_pooling': len(queries) * len(corpus.rows),
                       'items': {q: {'size': len(p), 'entries': p} for q, p in items.items()}}

    # ---- 3. the grades --------------------------------------------------------------------------------------------
    unlabelled = 'no gold label is set (P6-S3-T08: a person sets every one)'
    if 'nl_search' in splits:
        labelled = golden.labelled(docs['nl_search'])
        by_config = {}
        for run in runs:
            if not run.ran or not labelled:
                continue
            ranked = {it['id']: run.ids(corpus, it['id']) for it in labelled}
            judged = [metrics.judged_at(ranked[it['id']], it['gold']) for it in labelled]
            by_config[run.name] = {
                'populations': {name: metrics.nl_search([(ranked[it['id']], it['gold']) for it in group])
                                for name, group in populations(labelled, test).items()},
                'judged@20': {'judged': sum(j for j, _ in judged), 'retrieved': sum(n for _, n in judged)}}
        missing = {}
        if by_config:
            known = set(corpus.ids)
            doc['results']['nl_search'] = {
                'configurations': by_config,
                'gold_outside_corpus': sorted({e for it in labelled for e, g in it['gold'].items()
                                               if g > 0 and e not in known})}
        else:
            why = unlabelled if not labelled else 'no retrieval configuration ran'
            missing = {m: why for m in metrics.BARS['nl_search']}
        missing['the F1 configurations'] = ('F1 writes the facet query that filters and boosts the fused list: needs '
                                            'the model run (model_run)')
        doc['not_measured']['nl_search'] = missing
    # facet_translation and abstention: graded from the model run's outputs, item id -> the FacetQuery F1 returned, or
    # the behaviour the response showed (11 S7's refusal contract, P6-S5, turns a response into one)
    allowed = {s: set(v) for s, v in ctx.slots.items()}
    for split, grade, needs in (
            ('facet_translation', lambda pairs: metrics.facet_translation(pairs, allowed), 'the F1 outputs'),
            ('abstention', metrics.abstention, 'the F1 outputs and the refusal contract (P6-S5)')):
        if split not in splits:
            continue
        answers = outputs.get(split, {})                                   # get-default: no model run, no outputs
        labelled = golden.labelled(docs[split])
        lab = [it for it in labelled if it['id'] in answers]
        if not lab:
            why = unlabelled if not labelled else 'needs %s: not run (model_run)' % needs
            doc['not_measured'][split] = {m: why for m in metrics.BARS[split]}
            continue
        res = {name: grade([(it['gold'], answers[it['id']]) for it in group])
               for name, group in populations(lab, test).items()}
        if split == 'facet_translation':
            for pop in res.values():
                for m in pop.values():
                    m['smoke_test'] = m['n'] < SMOKE_TEST_N             # 11 S7: a gate only from n = 200
        doc['results'][split] = {'configurations': {'F1': {'populations': res}}}
    if 'suite_build' in splits:
        why = 'needs the F2 synthesis (P6-S5): not run (model_run)'
        if not golden.labelled(docs['suite_build']):
            why = '%s; and %s' % (unlabelled, why)
        doc['not_measured']['suite_build'] = {m: why for m in metrics.BARS['suite_build']}

    features = sorted({batch.FEATURE[s] for s in splits})
    doc['model_run'] = batch.status(features, env, root).as_dict()
    if judge:
        doc['judge'] = batch.status([batch.JUDGE], env, root).as_dict()
    doc['graded'] = bool(doc['results'])
    return doc


def write(doc: dict, root: str = ROOT) -> str | None:
    """evals/results/<date>-<commit>.json when something was graded; None, writing nothing, otherwise."""
    if not doc['graded']:
        return None
    path = results_path(root, _dt.date.fromisoformat(doc['date']), doc['commit'])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    return path


# ---- what the run prints ------------------------------------------------------------------------------------------

def nothing_graded(doc: dict) -> str:
    total = sum(s['items'] for s in doc['splits'].values())
    set_ = sum(s['labelled'] for s in doc['splits'].values())
    if set_ == 0:
        return ('Nothing can be graded yet. %d of %d gold labels are set: every gold label in evals/golden/ stays null '
                'until a person sets it (P6-S3-T08), because an agent-written label would make the evaluation '
                'circular. No metric is reported and no results file is written.' % (set_, total))
    return ('Nothing could be graded. %d of %d gold labels are set, but what they grade did not run (see "Not '
            'measured"). No metric is reported and no results file is written.' % (set_, total))


def summary(doc: dict) -> list[str]:
    out = ['eval: golden set %s, %s at %s (tree %s)' % (doc['set_version'], ', '.join(
        '%s %d/%d labelled' % (s, v['labelled'], v['items']) for s, v in doc['splits'].items()),
        doc['commit'][:8], doc['tree'])]
    if doc['configurations']:
        out.append('eval: configurations %s' % ', '.join(
            '%s %s' % (c['name'], 'ran' if c['ran'] else 'not run') for c in doc['configurations']))
    if doc['pool']:
        out.append('eval: pool of %d candidate(s) for %d item(s) (depth %d), against %d without pooling'
                   % (doc['pool']['judgments'], len(doc['pool']['items']), doc['pool']['depth'],
                      doc['pool']['without_pooling']))
    if not doc['graded']:
        out.append('eval: ' + nothing_graded(doc))
    else:
        verdicts: dict[str, int] = {}
        for split in doc['results'].values():
            for cfg in split['configurations'].values():
                for m in cfg['populations'].get('all', {}).values():   # get-default: an empty population is absent
                    if 'verdict' in m:
                        verdicts[m['verdict']] = verdicts.get(m['verdict'], 0) + 1   # get-default: first count
        out.append('eval: graded %s; verdicts over the whole splits: %s' % (
            ', '.join(doc['results']), ', '.join('%d %s' % (n, v) for v, n in sorted(verdicts.items())) or 'none'))
    return out


def _cell(m: dict) -> str:
    return '%.3f | [%.3f, %.3f] | %s | %s | %s%s' % (
        m['value'], m['interval'][0], m['interval'][1], m['n'], m.get('bar', ''), m.get('verdict', ''),   # get-default: a metric may have no bar
        ' (smoke test)' if m.get('smoke_test') else '')                                                    # get-default: only facet_translation carries it


def report(doc: dict) -> str:
    """The run as Markdown (module docstring)."""
    lines = ['# bench eval: golden set %s, %s, commit %s (tree %s)' % (doc['set_version'], doc['date'],
                                                                     doc['commit'][:8], doc['tree']), '']
    lines += ['- %s: %d item(s), %d labelled%s' % (s, v['items'], v['labelled'],
                                                   ', by %s' % v['labelled_by'] if v['labelled_by'] else '')
              for s, v in doc['splits'].items()]
    if doc['holdout']['n']:
        lines.append('- holdout: %d item(s) held out as the test split: %s' % (doc['holdout']['n'],
                                                                           ', '.join(doc['holdout']['test'])))
    if doc['tree'] == 'dirty':
        lines.append('- the tree is dirty: a results file from it is not attributable to its commit; publish one '
                     'from a clean checkout')
    lines.append('')
    if not doc['graded']:
        lines += ['**%s**' % nothing_graded(doc), '']
    if doc['corpus']:
        lines += ['## Retrieval configurations', '',
                  'Over %d benchmark entries%s.' % (doc['corpus']['benchmarks'],
                                                   ', drafts included (no entry is published yet)'
                                                   if doc['corpus']['drafts'] else ''), '']
        lines += ['- %s: %s -- %s' % (c['name'], 'ran' if c['ran'] else 'NOT RUN: %s' % c['reason'], c['describes'])
                  for c in doc['configurations']]
        lines.append('')
    lines += ['## The model run (Batch API)', '']
    for f, model in doc['model_run']['models'].items():
        lines.append('- %s (%s): not run: %s' % (f, model, '; '.join(doc['model_run']['not_run'][f])))
    if 'judge' in doc:
        for f, model in doc['judge']['models'].items():
            lines.append('- --judge, %s (%s): not run: %s' % (f, model, '; '.join(doc['judge']['not_run'][f])))
    lines.append('')
    if doc['graded']:
        lines += ['## Metrics', '', 'Interval: %s. Note: %s.' % (doc['interval']['method'], doc['interval']['note']),
                  '', '| split | configuration | population | metric | value | 95% interval | n | bar | verdict |',
                  '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
        for split, res in doc['results'].items():
            for cfg, body in res['configurations'].items():
                for pop, ms in body['populations'].items():
                    for name, m in ms.items():
                        lines.append('| %s | %s | %s | %s | %s |' % (split, cfg, pop, name, _cell(m)))
        lines.append('')
        for split, res in doc['results'].items():
            for cfg, body in res['configurations'].items():
                if 'judged@20' in body:
                    j = body['judged@20']
                    lines.append('- %s / %s: %d of the %d entries it ranked in the top 20 are graded; an ungraded '
                                 'one counts as grade 0' % (split, cfg, j['judged'], j['retrieved']))
            if res.get('gold_outside_corpus'):                        # get-default: nl_search only
                lines.append('- %s: gold names %s, not in the corpus this run retrieves over'
                             % (split, ', '.join(res['gold_outside_corpus'])))
        lines.append('')
    if doc['not_measured']:
        lines += ['## Not measured', '']
        for split, ms in doc['not_measured'].items():
            for name, why in ms.items():
                lines.append('- %s %s: %s' % (split, name, why))
        lines.append('')
    if doc['pool']:
        p = doc['pool']
        share = 100.0 * p['judgments'] / p['without_pooling'] if p['without_pooling'] else 0.0
        lines += ['## The pool to grade', '',
                  'TREC-style (11 S7): the union of each configuration\'s top %d (%s). %d candidate(s) over %d '
                  'item(s), %.1f an item, against %d judgments without pooling (%.1f%%). Grade these in each item\'s '
                  '`gold`; an entry left out is grade 0.' % (
                      p['depth'], ', '.join(p['configurations']) or 'no configuration ran', p['judgments'],
                      len(p['items']), p['judgments'] / max(1, len(p['items'])), p['without_pooling'], share), '']
        for q, item in p['items'].items():
            lines.append('- %s (%d): %s' % (q, item['size'], ', '.join(e['id'] for e in item['entries']) or 'none'))
        lines.append('')
    lines += ['## Disclosures', ''] + ['- %s' % d for d in doc['disclosures']]
    return '\n'.join(lines) + '\n'
