#!/usr/bin/env python3
"""Draft the mapping stanzas for the Epoch files benchmark_metadata.csv covers (P3-S2-T03; 07 S2.1).

    python scripts/epoch_stanzas.py                   # write ingest/mappings/epoch/<stem>.yaml + the review report
    python scripts/epoch_stanzas.py --dry-run         # report only

For each of the 59 per-benchmark CSVs a metadata row names (`source_file`), one stanza
(ingest/mappings/schema.py) from that row and the file's header. What is filled, and from where:

  benchmark_ref   ingest/mappings/epoch/_id_allocation.yaml's row for the metadata `benchmark` string
                  (id, plus its version and subset), never derived here
  score_column    the metadata row's `score_column` -- Epoch names it, so it is never chosen here
  scale           the metadata row's `scale`; scale_source benchmark_metadata.csv
  metric_ref      <benchmark id>-score, the corpus's convention (webdev-arena-score); the Metric records,
                  which carry Epoch's random_baseline and score_ceiling, are a later task's
  family          epoch-run when the header has `Logs` or `Log viewer` (scripts/epoch_audit.py's family A),
                  else external-scrape
  uncertainty     `stderr`, only where that exact column exists
  artifact        `Logs` and `Log viewer`
  date_column     `Started at`, only where it exists (`Release date` is the model's, never the result's)
  conditions      reasoning_effort from a `Reasoning effort` column, else from the model-version suffix where
                  any version in the file carries one (07 S2.2's EFFORT_SUFFIX); shots from a `Shots` column;
                  selection_strategy best-across-scorers for "Best score (across scorers)"

Everything this does NOT decide is flagged for the reviewer in reports/epoch-stanza-review.md, file by
file: other score-like columns beside the named one, uncertainty and date columns it did not pick, and
scaled values outside 0-1 (a unit trap: a percentage left at scale 1.0). Every stanza is written with
reviewed_by: null; a person who has checked the score column sets it (the task's step 3). A stanza whose
reviewed_by is already set is never overwritten.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import epoch_audit as A  # noqa: E402

MAPPINGS = os.path.join(ROOT, 'ingest', 'mappings', 'epoch')
ALLOCATION = os.path.join(MAPPINGS, '_id_allocation.yaml')
REPORT = os.path.join(ROOT, 'reports', 'epoch-stanza-review.md')
SOURCE = 'src-epoch-benchmark-data'
EFFORT_SUFFIX = re.compile(r'_(max|xhigh|high|medium|low|minimal|none|unknown)$')     # 07 S2.2
SCORE_LIKE = re.compile(r'score|accura|correct|pass|resolv|solved|progress|average|\bmean\b|overall|win|reach'
                        r'|^em$|^r\d$|opt@|%|rate', re.I)
UNCERTAINTY_LIKE = re.compile(r'std|stderr|standard error|\bse\b|\bsd\b|\bci\b|ci_|±|half-width', re.I)
DATE_LIKE = re.compile(r'\bdate\b|started at|created|run date', re.I)
NOT_SCORES = {'Release date', 'Training compute (FLOP)', 'Training compute notes', 'Cost per task', 'Cost',
              'Time per case (seconds)', 'Total tokens', 'Total cost (USD)', 'Estimated cost (USD)'}


def number(cell):
    try:
        return float(cell.strip().rstrip('%'))
    except (AttributeError, ValueError):
        return None


def allocation():
    from ruamel.yaml import YAML
    with open(ALLOCATION, encoding='utf-8') as f:
        rows = YAML(typ='safe', pure=True).load(f)['allocations']
    return {r['epoch']: r for r in rows}


def benchmark_ref(row):
    ref = row['benchmark'] + ('@%s' % row['version'] if row.get('version') else '')
    if row.get('subset'):
        ref += '#' + row['subset'].split('#', 1)[1]
    return ref


def covered(export):
    """[(metadata row, file name)] for every metadata row whose source_file is on disk."""
    _, meta = A.read(os.path.join(export, A.META))
    out = []
    for m in meta:
        src = (m.get('source_file') or '').strip()
        if src and os.path.isfile(os.path.join(export, src)):
            out.append((m, src))
    return out


def draft(m, name, export, alloc):
    """(stanza dict, [flags]) for one covered file."""
    header, rows = A.read(os.path.join(export, name))
    bench = m['benchmark'].strip()
    a = alloc[bench]
    score = m['score_column']
    flags = []
    stanza = {
        'benchmark_ref': benchmark_ref(a),
        'family': 'epoch-run' if ('Logs' in header or 'Log viewer' in header) else 'external-scrape',
        'score_column': score,
        'scale': float(m['scale']),
        'scale_source': 'benchmark_metadata.csv',
        'metric_ref': '%s-score' % a['benchmark'],
        'source_ref': SOURCE,
    }
    if 'stderr' in header:
        stanza['uncertainty'] = {'column': 'stderr', 'type': 'stderr'}
    if 'Logs' in header or 'Log viewer' in header:
        stanza['artifact'] = {k: c for k, c in (('log_column', 'Logs'), ('viewer_column', 'Log viewer')) if c in header}
    if 'Started at' in header:
        stanza['date_column'] = 'Started at'
    conditions = {}
    versions = [r.get('Model version', '') for r in rows]
    if 'Reasoning effort' in header:
        conditions['reasoning_effort'] = {'from': 'column', 'column': 'Reasoning effort'}
    elif any(EFFORT_SUFFIX.search(v or '') for v in versions):
        conditions['reasoning_effort'] = {'from': 'model_version_suffix'}
    if 'Shots' in header:
        conditions['shots'] = {'from': 'column', 'column': 'Shots'}
    if score == 'Best score (across scorers)':
        conditions['selection_strategy'] = {'const': 'best-across-scorers'}
    if conditions:
        stanza['conditions'] = conditions
    stanza['reviewed_by'] = None
    stanza['notes'] = ('Drafted by scripts/epoch_stanzas.py (P3-S2-T03) from the benchmark_metadata.csv row '
                       '%r and the header of %s; see reports/epoch-stanza-review.md.' % (bench, name))

    rivals = [c for c in header if c != score and c not in NOT_SCORES and SCORE_LIKE.search(c)
              and not UNCERTAINTY_LIKE.search(c)]
    if score == 'Best score (across scorers)' and 'mean_score' in rivals:
        rivals.remove('mean_score')         # Epoch's run-family pair: one decision for all of them (the report)
    if rivals:
        flags.append('other score-like columns: %s' % ', '.join(rivals))
    unc = [c for c in header if UNCERTAINTY_LIKE.search(c) and c != 'stderr']
    if unc:
        flags.append('uncertainty column(s) not mapped: %s' % ', '.join(unc))
    dates = [c for c in header if DATE_LIKE.search(c) and c not in ('Release date', 'Started at')]
    if dates and 'date_column' not in stanza:
        flags.append('no date_column; candidate(s): %s' % ', '.join(dates))
    values = [number(r.get(score)) for r in rows]
    nums = [v * stanza['scale'] for v in values if v is not None]
    blanks = sum(1 for v in values if v is None)
    if nums and (min(nums) < 0 or max(nums) > 1.0 + 1e-9):
        flags.append('UNIT: scaled values span %.4g..%.4g, outside 0-1' % (min(nums), max(nums)))
    if blanks:
        flags.append('%d of %d rows have no number in %r' % (blanks, len(rows), score))
    if conditions.get('reasoning_effort', {}).get('from') == 'column' and any(EFFORT_SUFFIX.search(v or '') for v in versions):  # get-default: a missing rule is no rule
        flags.append('effort is in a column AND in model-version suffixes; the column is used')
    return stanza, flags, len(rows), (min(nums), max(nums)) if nums else None


def render(results):
    L = ['# Epoch mapping stanzas: the review list (P3-S2-T03)', '',
         'Generated by `python scripts/epoch_stanzas.py` from benchmark_metadata.csv and each file\'s header. '
         'Every stanza in ingest/mappings/epoch/ is a draft with `reviewed_by: null`: the score column is '
         "Epoch's own, but whether it is the RIGHT one, and every item below, is a person's call (07 S2.1). "
         'Set `reviewed_by` to your handle in each stanza you have checked.', '',
         '| | files |', '| --- | --- |',
         '| stanzas drafted | %d |' % len(results),
         '| with at least one flag | %d |' % sum(1 for r in results if r[2]),
         '| UNIT flags (scaled values outside 0-1) | %d |' % sum(1 for r in results if any(f.startswith('UNIT') for f in r[2])),
         '']
    runs = [n for n, s, _, _, _ in results if s['score_column'] == 'Best score (across scorers)']
    undated = [n for n, s, flags, _, _ in results            # no date column, and no candidate one either
               if 'date_column' not in s and not any(f.startswith('no date_column') for f in flags)]
    L += ['## Decisions that cover many files at once', '',
          '1. **Best score or mean score (%d Epoch-run files).** Each also carries `mean_score`. Epoch\'s metadata '
          'names "Best score (across scorers)" as the score, so the stanzas use it, with selection_strategy '
          '`best-across-scorers` as a condition of the claim (07 S2.1\'s own example). If the catalogue should hold '
          'the mean instead, or both as two claims, that is one decision for all of: %s.' % (len(runs), ', '.join(runs)),
          '',
          '2. **No date in the file (%d files).** These carry no result date at all (only `Release date`, which is '
          'the model\'s), so a claim drafted from them has no date_reported from the row. Where its date comes from '
          '-- the Epoch snapshot date, the benchmark\'s own leaderboard, or nowhere -- is one decision for all of: %s.'
          % (len(undated), ', '.join(undated)),
          '', '## Flagged files', '']
    for name, stanza, flags, n, span in results:
        if not flags:
            continue
        L.append('### %s -> `%s`' % (name, stanza['benchmark_ref']))
        L.append('')
        L.append('score `%s` x %s, %d rows%s, family %s' % (
            stanza['score_column'], stanza['scale'], n,
            ', scaled %.4g..%.4g' % span if span else '', stanza['family']))
        L.append('')
        L += ['- %s' % f for f in flags]
        L.append('')
    L += ['## Unflagged files', '']
    L += ['- %s -> `%s` (score `%s` x %s)' % (name, s['benchmark_ref'], s['score_column'], s['scale'])
          for name, s, flags, _, _ in results if not flags]
    return '\n'.join(L).rstrip('\n') + '\n'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--dir', default=os.path.join(ROOT, 'epochdl'))
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)
    from ingest import emit
    from ingest.mappings.schema import Stanza, read
    alloc = allocation()
    results, kept = [], []
    for m, name in covered(a.dir):
        stanza, flags, n, span = draft(m, name, a.dir, alloc)
        Stanza.model_validate(stanza)
        stem = name[:-len('.csv')]
        rel = 'ingest/mappings/epoch/%s.yaml' % stem
        results.append((name, stanza, flags, n, span))
        if a.dry_run:
            continue
        path = os.path.join(ROOT, *rel.split('/'))
        if os.path.exists(path) and read(path).reviewed_by:
            kept.append(rel)
            continue
        emit.write(stanza, rel, ROOT, header='%s -- the mapping stanza for Epoch\'s %s (07 S2.1; P3-S2-T03)'
                   % (rel, name), replace=True)
    if not a.dry_run:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, 'w', encoding='utf-8', newline='\n') as f:
            f.write(render(results))
    print('epoch_stanzas: %d covered file(s), %d flagged, %d reviewed and kept'
          % (len(results), sum(1 for r in results if r[2]), len(kept)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
