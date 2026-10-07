#!/usr/bin/env python3
"""02 S3's floor rule, asserted against the published corpus (P1-S2-T09; 14 Phase 1 exit criteria).

02 S3, "Three numbers, three jobs":
  1. hard floor, 12 entries, blocking at launch: no family ships below twelve;
  2. Core floor, 18 entries, blocking at launch, no exemption: the seven Core families;
  3. credibility target, 15, by v1.x: an aspiration, not a gate, and not checked here.
"The muting exemption, and it is the only one": a family that cannot reach its floor ships with
`coverage_status: under-surveyed` in taxonomy/domains.yaml. "Muting is not available to the seven Core
families."

The counts are scripts/seed_progress.py's (one implementation); the floors are scripts/taxonomy_stats.py's
HARD_FLOOR and CORE_FLOOR, the same constants check 9f holds the seed targets to.

    python scripts/check_floor_rule.py
        The standing invariants, which hold at every point in the build, then the report. The Core set
        in domains.yaml is exactly the seven 02 S3 names, and no Core family is muted. Every family's
        count against its floor is printed, never asserted: the launch gates are asserted by name, below.
    python scripts/check_floor_rule.py --family engineering-design [--assert-min 12] [--satisfied-or-muted]
        One family's count against its floor. With --assert-min, exit 1 below it, unless
        --satisfied-or-muted and the family carries under-surveyed and is not Core.
    python scripts/check_floor_rule.py --assert-total 290 --assert-core 130
        The launch gates (14 Phase 1 exit criteria). --assert-total N: at least N entries, all 19
        families populated, and none below 12 unless muted. --assert-core N: at least N across the Core
        seven, none below 18 and none muted. --core-only restricts the family checks to the Core seven.

Exit 0 when every assertion holds, 1 when one fails (each failing family is named; nothing is rounded),
2 on a usage error.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seed_progress as S  # noqa: E402
from taxonomy_stats import CORE_FLOOR, HARD_FLOOR  # noqa: E402

PLAN_02 = os.path.join('_plan', '02-taxonomy.md')
MUTED = 'under-surveyed'
# 02 S3, floor rule 2: "The seven Core families — a, b, ... — are the product."
CORE_SENTENCE = re.compile(r'The seven Core families\s*—\s*(.+?)\s*—\s*are the product', re.S)


def named_core(root: str = S.ROOT) -> list[str] | None:
    """The Core families 02 S3's floor rule names, or None where the plan is not in the tree."""
    path = os.path.join(root, PLAN_02)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        m = CORE_SENTENCE.search(fh.read())
    return [x.strip() for x in m.group(1).replace('\n', ' ').split(',')] if m else []


def floor(f: dict) -> int:
    return CORE_FLOOR if f.get('core') is True else HARD_FLOOR       # get-default: core is false unless stated


def muted(f: dict) -> bool:
    return f.get('coverage_status') == MUTED                         # get-default: unmuted unless stated


def standing(root: str, fams: list[dict]) -> list[str]:
    """The invariants that hold at every point in the build, not only at launch."""
    errs = []
    core = sorted(f['id'] for f in fams if f.get('core') is True)    # get-default: as above
    named = named_core(root)
    if named is not None and sorted(named) != core:
        errs.append('the Core set in %s is %s; 02 S3 names %s' % (S.DOMAINS, core or 'empty', sorted(named) or 'none'))
    for f in fams:
        if f.get('core') is True and muted(f):                      # get-default: as above
            errs.append('%s is a Core family and carries coverage_status: %s; 02 S3: "Muting is not available '
                        'to the seven Core families"' % (f['id'], MUTED))
    return errs


def state(n: int, f: dict) -> str:
    if n >= floor(f):
        return 'at or above its floor'
    if muted(f) and f.get('core') is not True:                       # get-default: as above
        return 'below its floor, muted (%s)' % MUTED
    return 'below its floor'


def report(fams: list[dict], c, only: str | None = None) -> str:
    rows = ['%-22s %9s %5s  %s' % ('family', 'published', 'floor', 'state')]
    for f in fams:
        if not only or f['id'] == only:
            rows.append('%-22s %9d %5d  %s%s' % (f['id'], c[f['id']], floor(f), state(c[f['id']], f),
                                                 '  [Core]' if f.get('core') is True else ''))  # get-default: as above
    return '\n'.join(rows)


def assert_total(fams, c, n: int, core_only: bool) -> list[str]:
    errs = []
    total = sum(c.values())
    if total < n:
        errs.append('%d published entries in all, below the gate of %d' % (total, n))
    for f in fams:
        if core_only and f.get('core') is not True:                 # get-default: as above
            continue
        k = c[f['id']]
        if k == 0:
            errs.append('%s has no published entry; the gate is 19 of 19 families populated' % f['id'])
        elif k < HARD_FLOOR and not (muted(f) and f.get('core') is not True):   # get-default: as above
            errs.append('%s has %d, below the hard floor of %d, and is not muted' % (f['id'], k, HARD_FLOOR))
    return errs


def assert_core(fams, c, n: int) -> list[str]:
    errs = []
    core = [f for f in fams if f.get('core') is True]               # get-default: as above
    total = sum(c[f['id']] for f in core)
    if total < n:
        errs.append('%d published entries across the %d Core families, below the gate of %d' % (total, len(core), n))
    for f in core:
        if c[f['id']] < CORE_FLOOR:
            errs.append('%s (Core) has %d, below the Core floor of %d; no exemption' % (f['id'], c[f['id']], CORE_FLOOR))
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=S.ROOT)
    ap.add_argument('--family', help='one domain family')
    ap.add_argument('--assert-min', type=int, help='with --family: exit 1 below this many entries')
    ap.add_argument('--satisfied-or-muted', action='store_true',
                    help='with --assert-min: a muted non-Core family passes (02 S3, the muting exemption)')
    ap.add_argument('--assert-total', type=int, help='launch gate: total, 19/19 populated, hard floor unless muted')
    ap.add_argument('--assert-core', type=int, help='launch gate: Core total, Core floor, none muted')
    ap.add_argument('--core-only', action='store_true', help='restrict the family checks to the Core seven')
    a = ap.parse_args(argv)

    fams, _ = S.vocabulary(a.root)
    by_id = {f['id']: f for f in fams}
    if a.family and a.family not in by_id:
        print('FAIL  %s is not a domain family in %s' % (a.family, S.DOMAINS))
        return 2
    if (a.assert_min is not None or a.satisfied_or_muted) and not a.family:
        ap.error('--assert-min and --satisfied-or-muted need --family')
    if a.satisfied_or_muted and a.assert_min is None:
        ap.error('--satisfied-or-muted needs --assert-min')

    c = S.counts(a.root)
    fails = standing(a.root, fams)
    if a.family and a.assert_min is not None:
        f, n = by_id[a.family], c[a.family]
        if n >= a.assert_min:
            print('OK    %s has %d published entries, asserted at least %d' % (a.family, n, a.assert_min))
        elif a.satisfied_or_muted and muted(f) and f.get('core') is not True:           # get-default: as above
            print('OK    %s has %d, below %d, and is muted (coverage_status: %s), which 02 S3 permits for a '
                  'non-Core family' % (a.family, n, a.assert_min, MUTED))
        else:
            why = (', and it is Core, so muting cannot exempt it' if f.get('core') is True and a.satisfied_or_muted  # get-default: as above
                   else ', and it is not muted' if a.satisfied_or_muted else '')
            fails.append('%s has %d published entries, below %d%s' % (a.family, n, a.assert_min, why))
    if a.assert_total is not None:
        errs = assert_total(fams, c, a.assert_total, a.core_only)
        fails += errs
        if not errs:
            print('OK    %d published entries; every %sfamily populated and at its floor or muted'
                  % (sum(c.values()), 'Core ' if a.core_only else ''))
    if a.assert_core is not None:
        errs = assert_core(fams, c, a.assert_core)
        fails += errs
        if not errs:
            print('OK    the Core families total %d, none below %d, none muted'
                  % (sum(c[f['id']] for f in fams if f.get('core') is True), CORE_FLOOR))   # get-default: as above
    if a.core_only and a.assert_total is None and a.assert_core is None:
        ap.error('--core-only restricts --assert-total or --assert-core; give one')

    print(report([f for f in fams if not a.core_only or f.get('core') is True], c, a.family))   # get-default: as above
    if not fails and a.assert_total is None and a.assert_core is None and a.assert_min is None:
        print('OK    standing invariants: the Core set is 02 S3\'s seven and none is muted; the launch gates '
              'are asserted with --assert-total and --assert-core')
    for f in fails:
        print('FAIL  ' + f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
