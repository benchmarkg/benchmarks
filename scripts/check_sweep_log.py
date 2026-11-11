#!/usr/bin/env python3
"""Every hub on the sweep checklist has a dated visit this cycle (P1-S12-T02; 06 S6).

06 S6: a sweep is "a curator log entry that records 'checked, no change' as a first-class outcome",
and it "produces one PR per family containing every change plus a dated 'checked' stamp on every
unchanged entry". The log is docs/sweeps/log/<YYYY-MM-DD>-<family>.yaml, one file per family per
sweep. For each family named, this asserts on the newest log:

  fresh      a log exists and its date is within --max-age of today; a family never swept fails.
  shape      the file is well formed: its family and date match its name, every hub and entry
             carries an outcome from the vocabulary, and 'checked-no-change' counts as a result.
  hubs       every hub docs/sweeps/hubs.yaml lists for the family (its own, and any shared hub that
             serves it) has a row, so a hub never visited fails. A row for a hub hubs.yaml no longer
             lists must be 'dropped', and a 'dropped' hub must be gone from hubs.yaml: the hub list is
             corrected in the sweep's own PR (checklist.md, "Running a sweep" step 2).
  entries    every entry in data/benchmarks/<family>/ has a row, and carries liveness.last_checked
             within --max-age: the dated 'checked' stamp. No row names an entry that does not exist.

    python scripts/check_sweep_log.py --families robotics-embodiment,agents-tooluse --max-age 100d
    python scripts/check_sweep_log.py --families ... --today 2026-11-10 --root DIR   # the tests
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

HUBS = 'docs/sweeps/hubs.yaml'
LOG_DIR = 'docs/sweeps/log'
BENCHMARKS = 'data/benchmarks'

HUB_OUTCOMES = ('checked-no-change', 'changed', 'unreachable', 'dropped', 'found')
ENTRY_OUTCOMES = ('checked-no-change', 'changed')
PAGE_STATES = ('live', 'suspect', 'dead', 'no-url')
LOG_KEYS = {'version', 'family', 'date', 'curator', 'cdx', 'hubs', 'entries'}
HUB_KEYS = {'name', 'url', 'http_status', 'final_url', 'page_state', 'outcome', 'entries', 'findings', 'note'}
ENTRY_KEYS = {'id', 'outcome', 'pages', 'repo', 'hf', 'leaderboard_last_updated', 'leaderboard_rows',
              'reproduction_script_present', 'findings', 'note'}
NAME = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9-]+)\.yaml$')


def load(path):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def max_age(text):
    m = re.fullmatch(r'(\d+)d', text)
    if not m:
        raise argparse.ArgumentTypeError('--max-age takes a day count such as 100d, not %r' % text)
    return int(m.group(1))


def logs(root, family):
    """The family's sweep logs, newest first, as (date, path)."""
    out = []
    for path in glob.glob(os.path.join(root, LOG_DIR, '*.yaml')):
        m = NAME.match(os.path.basename(path))
        if m and m.group(2) == family:
            out.append((dt.date.fromisoformat(m.group(1)), path))
    return sorted(out, reverse=True)


def listed_hubs(root, family):
    doc = load(os.path.join(root, HUBS))
    block = next((b for b in doc.get('families') or [] if b.get('family') == family), None)
    if block is None:
        return None
    own = [h['name'] for h in block.get('hubs') or []]
    shared = [h['name'] for h in doc.get('shared_hubs') or [] if family in (h.get('families') or [])]
    return own + shared


def entries(root, family):
    """{id: liveness.last_checked or None} for the family's published entries."""
    out = {}
    for path in sorted(glob.glob(os.path.join(root, BENCHMARKS, family, '*.yaml'))):
        doc = load(path) or {}
        live = doc.get('liveness') or {}
        out[doc.get('id') or os.path.basename(path)[:-5]] = live.get('last_checked')
    return out


def check_family(root, family, today, days):
    errs = []
    hubs = listed_hubs(root, family)
    if hubs is None:
        return ['%s is not a family in %s' % (family, HUBS)]
    found = logs(root, family)
    if not found:
        return ['%s has never been swept: no %s/<date>-%s.yaml' % (family, LOG_DIR, family)]
    date, path = found[0]
    rel = os.path.relpath(path, root).replace(os.sep, '/')
    age = (today - date).days
    if age > days:
        errs.append('%s: the newest sweep, %s, is %d days old (max %d)' % (family, rel, age, days))
    doc = load(path) or {}

    unknown = set(doc) - LOG_KEYS
    if unknown:
        errs.append('%s: unknown key %s' % (rel, ', '.join(sorted(unknown))))
    if doc.get('family') != family:
        errs.append('%s: family %r does not match the file name' % (rel, doc.get('family')))
    if doc.get('date') != date:
        errs.append('%s: date %r does not match the file name' % (rel, doc.get('date')))
    if not str(doc.get('curator') or '').strip():
        errs.append('%s: no curator' % rel)

    rows = doc.get('hubs') or []
    names = [h.get('name') for h in rows]
    for h in rows:
        where = '%s hub %r' % (rel, h.get('name'))
        bad = set(h) - HUB_KEYS
        if bad:
            errs.append('%s: unknown key %s' % (where, ', '.join(sorted(bad))))
        if h.get('outcome') not in HUB_OUTCOMES:
            errs.append('%s: outcome %r is not one of %s' % (where, h.get('outcome'), ', '.join(HUB_OUTCOMES)))
        if h.get('page_state') not in PAGE_STATES:
            errs.append('%s: page_state %r is not one of %s' % (where, h.get('page_state'), ', '.join(PAGE_STATES)))
        if h.get('http_status') is not None and not isinstance(h['http_status'], int):
            errs.append('%s: http_status must be an integer or null' % where)
        if h.get('outcome') == 'dropped' and h.get('name') in hubs:
            errs.append('%s: dropped, but %s still lists it' % (where, HUBS))
        elif h.get('name') not in hubs and h.get('outcome') != 'dropped':
            errs.append('%s: %s does not list this hub for %s, and the row is not a drop' % (where, HUBS, family))
    dupes = sorted({n for n in names if names.count(n) > 1}, key=str)
    if dupes:
        errs.append('%s: hub rows repeat %s' % (rel, ', '.join(map(str, dupes))))
    for n in hubs:
        if n not in names:
            errs.append('%s: hub %r on the checklist was never visited' % (rel, n))

    held = entries(root, family)
    ids = [e.get('id') for e in doc.get('entries') or []]
    for e in doc.get('entries') or []:
        where = '%s entry %r' % (rel, e.get('id'))
        bad = set(e) - ENTRY_KEYS
        if bad:
            errs.append('%s: unknown key %s' % (where, ', '.join(sorted(bad))))
        if e.get('outcome') not in ENTRY_OUTCOMES:
            errs.append('%s: outcome %r is not one of %s' % (where, e.get('outcome'), ', '.join(ENTRY_OUTCOMES)))
        if e.get('id') not in held:
            errs.append('%s: no such entry in %s/%s/' % (where, BENCHMARKS, family))
    dupes = sorted({i for i in ids if ids.count(i) > 1}, key=str)
    if dupes:
        errs.append('%s: entry rows repeat %s' % (rel, ', '.join(map(str, dupes))))
    for i, checked in sorted(held.items()):
        if i not in ids:
            errs.append('%s: entry %s has no row' % (rel, i))
        if not isinstance(checked, dt.date):
            errs.append('%s/%s/%s.yaml: no liveness.last_checked stamp' % (BENCHMARKS, family, i))
        elif (today - checked).days > days:
            errs.append('%s/%s/%s.yaml: liveness.last_checked %s is %d days old (max %d)'
                        % (BENCHMARKS, family, i, checked, (today - checked).days, days))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--families', required=True, help='comma-separated domain families')
    ap.add_argument('--max-age', type=max_age, default=max_age('100d'), help='e.g. 100d (default)')
    ap.add_argument('--today', type=dt.date.fromisoformat, default=dt.date.today(), help='YYYY-MM-DD')
    ap.add_argument('--root', default=ROOT, help='the repository root (default: this checkout)')
    a = ap.parse_args(argv)
    fams = [f.strip() for f in a.families.split(',') if f.strip()]
    errs = []
    for f in fams:
        errs += check_family(a.root, f, a.today, a.max_age)
    if errs:
        print('\n'.join('FAIL  ' + e for e in errs))
        print('%d problem(s)' % len(errs))
        return 1
    for f in fams:
        date, path = logs(a.root, f)[0]
        print('OK    %s swept %s: every hub on the checklist visited, %d entries stamped'
              % (f, date, len(entries(a.root, f))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
