#!/usr/bin/env python3
"""Every near-duplicate candidate pair carries an adjudicated verdict (P1-S13-T05; 11 S F7, 05 S3).

`bench resolve --candidates` proposes the pairs of curated entries that a name, alias, URL or cosine signal
says might be one benchmark. 05 S3: resolution never merges; a person (or an agent draft a person reviews)
decides each pair. The decisions are data/_dedup/verdicts.yaml, one row per pair: `pair`, the `signal` that
proposed it, `verdict` (same | variant-of | distinct), a one-sentence `reason`, `decided_by`, `decided_on`,
and for a variant the lineage edge it is `expressed_as`. This asserts:

  shape        every row names two different curated entries, once (in either order), with a known verdict,
               a one-sentence reason, a curator and a date not after today.
  adjudicated  every pair the generator proposes at --threshold has a row: "No unresolved candidate pair
               remains above the calibrated threshold".
  expressed    a variant-of has a lineage edge between the two entries (supersedes, superseded_by,
               extended_by, subset_of, decontaminates, variants or forks, in either entry), which is also what
               stops the generator proposing the pair again; a same has a tombstone for one of the two ids in
               data/tombstones/, since a merge retires an id and never edits one entry into the other.

    bench resolve --candidates --threshold 0.88 && python scripts/check_dedup_resolved.py      # the verify
    python scripts/check_dedup_resolved.py --threshold 0.95                                     # the calibrated one
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VERDICTS = 'data/_dedup/verdicts.yaml'
KINDS = ('same', 'variant-of', 'distinct')
REQUIRED = {'pair', 'signal', 'verdict', 'reason', 'decided_by', 'decided_on'}
OPTIONAL = {'expressed_as'}
SECOND_SENTENCE = re.compile(r'[.!?]\s+[A-Z]')


def one_sentence(text):
    return isinstance(text, str) and text.strip().endswith('.') and not SECOND_SENTENCE.search(text.strip()[:-1])


def entries(root):
    """{id: raw} for every curated entry, not the stubs."""
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)).startswith('_'):
            continue
        with open(path, encoding='utf-8') as fh:
            raw = yaml.safe_load(fh)
        if isinstance(raw, dict) and isinstance(raw.get('id'), str):
            out[raw['id']] = raw
    return out


def proposed(threshold):
    """The pairs `bench resolve --candidates --threshold T` lists, as sorted id tuples."""
    from tools import resolve
    return [tuple(sorted((v.a, v.b))) for v in resolve.resolve_corpus([], resolve.config(threshold))]


def linked(a, b, raws):
    from tools.dedup import lineage_ids
    return b in lineage_ids(raws.get(a) or {}) or a in lineage_ids(raws.get(b) or {})


def check(root, today, candidates):
    path = os.path.join(root, *VERDICTS.split('/'))
    if not os.path.exists(path):
        return ['%s does not exist' % VERDICTS]
    with open(path, encoding='utf-8') as fh:
        doc = yaml.safe_load(fh)
    rows = doc.get('pairs') if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return ['%s: needs a list `pairs`' % VERDICTS]
    raws = entries(root)
    errs, seen = [], {}
    for i, row in enumerate(rows):
        where = '%s pairs[%d]' % (VERDICTS, i)
        if not isinstance(row, dict):
            errs.append('%s is not a mapping' % where)
            continue
        pair = row.get('pair')
        if not (isinstance(pair, list) and len(pair) == 2 and all(isinstance(x, str) for x in pair)
                and pair[0] != pair[1]):
            errs.append('%s: `pair` must name two different ids' % where)
            continue
        key = tuple(sorted(pair))
        where = '%s (%s, %s)' % (where, key[0], key[1])
        if not REQUIRED <= set(row) <= REQUIRED | OPTIONAL:
            errs.append('%s: keys must be %s, optionally %s; not %s' % (where, sorted(REQUIRED), sorted(OPTIONAL),
                                                                       sorted(row)))
        for x in key:
            if x not in raws:
                errs.append('%s: %s is not a curated entry' % (where, x))
        if key in seen:
            errs.append('%s: the pair already has a row' % where)
        seen.setdefault(key, row)
        if row.get('verdict') not in KINDS:
            errs.append('%s: verdict %r is not one of %s' % (where, row.get('verdict'), ', '.join(KINDS)))
        if not one_sentence(row.get('reason')):
            errs.append('%s: the reason must be one sentence ending in a full stop' % where)
        if not isinstance(row.get('decided_by'), str) or not row['decided_by'].strip():
            errs.append('%s: no decided_by: a verdict names who made it' % where)
        when = row.get('decided_on')
        if not isinstance(when, dt.date):
            errs.append('%s: decided_on %r is not a date' % (where, when))
        elif when > today:
            errs.append('%s: decided_on %s is after today, %s' % (where, when, today))
        if row.get('verdict') == 'variant-of' and not linked(key[0], key[1], raws):
            errs.append('%s: variant-of, but no lineage edge links the two entries: express it as lineage '
                        '(supersedes, extended_by, forks, ...), never as a merge' % where)
        if row.get('verdict') == 'same' and not any(
                os.path.exists(os.path.join(root, 'data', 'tombstones', x + '.yaml')) for x in key):
            errs.append('%s: same, but neither id has a tombstone in data/tombstones/: a merge retires one id' % where)
    for key in sorted(set(candidates)):
        if key not in seen:
            errs.append('(%s, %s) is a candidate pair with no verdict in %s: adjudicate it' % (key[0], key[1],
                                                                                              VERDICTS))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--threshold', type=float, default=0.88, help='the cosine threshold (default 0.88, the verify)')
    ap.add_argument('--today', type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date(),
                    help='YYYY-MM-DD (default: today in UTC, as CI runs)')
    a = ap.parse_args(argv)
    candidates = proposed(a.threshold)
    errs = check(a.root, a.today, candidates)
    for e in errs:
        print('FAIL  ' + e)
    if errs:
        print('%d problem(s)' % len(errs))
        return 1
    with open(os.path.join(a.root, *VERDICTS.split('/')), encoding='utf-8') as fh:
        rows = yaml.safe_load(fh)['pairs']
    counts = {k: sum(1 for r in rows if r['verdict'] == k) for k in KINDS}
    print('OK    %d candidate pairs at cosine %.2f, every one adjudicated; %d verdicts recorded: %s'
          % (len(set(candidates)), a.threshold, len(rows), ', '.join('%s %d' % kv for kv in counts.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
