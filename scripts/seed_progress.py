#!/usr/bin/env python3
"""Seed progress: published benchmark entries per domain family, against 02 S3's allocation (P1-S2-T09).

The one implementation of "how many entries does a family have". The curation tranches assert their
progress with it, scripts/check_floor_rule.py asserts 02 S3's floor rule with it, and nothing else counts.

    python scripts/seed_progress.py                                  # the table: published vs seed target
    python scripts/seed_progress.py --check                          # the count is well defined (below)
    python scripts/seed_progress.py --family physics --assert-min 9  # exit 1 below 9
    python scripts/seed_progress.py --assert-total 20 --assert-min-families 12
    python scripts/seed_progress.py --family engineering-design --report
    python scripts/seed_progress.py --subdomain-emptiness [--out FILE] [--assert-total 100]
    python scripts/seed_progress.py --root DIR                       # another tree (the tests do)

What counts. A published entry is a curated Benchmark file, data/benchmarks/<family>/<id>.yaml. Not
data/benchmarks/_stubs/ (unpublished id allocations, 04 S3) and not drafts/ (05 S4: AI drafts live there
until a person has reviewed them). 04 S4: "A `Benchmark` is a family" and "we count and publish families",
so every Benchmark file counts once, toward the family of its `domain.primary`. Editions, revisions and
subsets are not files, so they cannot be counted by mistake. An entry that declares `lineage.subset_of` is
still a Benchmark and still counts; the table names how many there are, because 04 S4's table and such an
entry disagree about what it is, and that is a curator's question, not a counter's.

--check asserts the count is well defined: every entry sits in a family directory, under the family of
its own domain.primary, with that primary a subdomain the vocabulary holds, and with an id that is unique
and matches its file name. An entry in the wrong directory would otherwise be counted toward one family
by its path and another by its data.

The empty-subdomain figure (02 S3 "The browse spine is mostly empty at launch") is the share of
(family, subdomain) pairs with no entry whose domain.primary is that subdomain: 02 S3's own arithmetic
("320 seed entries over 209 (family, subdomain) pairs") counts primaries. Secondaries are reported beside
it, labelled, because a subdomain page lists them too.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS = os.path.join('taxonomy', 'domains.yaml')
BENCHMARKS = os.path.join('data', 'benchmarks')
NOT_PUBLISHED = ('_stubs',)


@dataclass(frozen=True)
class Entry:
    id: str
    path: str                       # relative to the root, forward slashes
    directory: str                  # the family directory it sits in
    primary: str | None             # domain.primary as written
    secondary: tuple = ()
    subset_of: str | None = None

    @property
    def family(self) -> str | None:
        return self.primary.split('/', 1)[0] if self.primary else None


def _load(path: str):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def vocabulary(root: str = ROOT) -> tuple[list[dict], dict[str, list[str]]]:
    """(families in domains.yaml order, family -> its subdomain ids). Retired terms are not families."""
    terms = [t for t in _load(os.path.join(root, DOMAINS))['terms'] if t.get('status') != 'retired']  # get-default: status is optional on a term
    fams = [t for t in terms if t.get('parent') is None]                                             # get-default: a family has no parent
    subs = {f['id']: [t['id'] for t in terms if t.get('parent') == f['id']] for f in fams}           # get-default: as above
    return fams, subs


def entries(root: str = ROOT) -> list[Entry]:
    out = []
    for path in sorted(glob.glob(os.path.join(root, BENCHMARKS, '*', '*.yaml'))):
        directory = os.path.basename(os.path.dirname(path))
        if directory in NOT_PUBLISHED:
            continue
        d = _load(path) or {}
        dom = d.get('domain') or {}                                  # get-default: --check reports a missing domain
        lin = d.get('lineage') or {}                                 # get-default: lineage is optional
        out.append(Entry(str(d.get('id') or ''), os.path.relpath(path, root).replace(os.sep, '/'), directory,  # get-default: --check reports a missing id
                         dom.get('primary'), tuple(dom.get('secondary') or ()), lin.get('subset_of')))       # get-default: as above
    return out


def counts(root: str = ROOT) -> Counter:
    """family -> published entries. The single count every floor and progress assertion reads."""
    return Counter(e.family for e in entries(root) if e.family)


def check(root: str = ROOT) -> list[str]:
    fams, subs = vocabulary(root)
    known = {f['id'] for f in fams}
    leaves = {s for v in subs.values() for s in v}
    errs, ids = [], Counter(e.id for e in entries(root))
    for e in entries(root):
        stem = os.path.basename(e.path)[:-5]
        if e.directory not in known:
            errs.append('%s: %s/ is not a domain family' % (e.path, e.directory))
        if not e.id:
            errs.append('%s: no id' % e.path)
        elif e.id != stem:
            errs.append('%s: id %r does not match its file name' % (e.path, e.id))
        if ids[e.id] > 1:
            errs.append('%s: id %r is used by %d entries' % (e.path, e.id, ids[e.id]))
        if e.primary is None:
            errs.append('%s: no domain.primary, so no family to count it toward' % e.path)
        elif e.primary not in leaves:
            errs.append('%s: domain.primary %r is not a subdomain in %s' % (e.path, e.primary, DOMAINS))
        elif e.family != e.directory:
            errs.append('%s: sits in %s/ but its domain.primary %r is %s' % (e.path, e.directory, e.primary, e.family))
    return errs


def emptiness(root: str = ROOT) -> dict:
    fams, subs = vocabulary(root)
    es = entries(root)
    primary = Counter(e.primary for e in es if e.primary)
    any_ = Counter(s for e in es for s in ((e.primary,) if e.primary else ()) + e.secondary)
    pairs = [s for f in fams for s in subs[f['id']]]
    empty = [s for s in pairs if not primary[s]]
    return {'entries': len(es), 'pairs': len(pairs), 'empty_primary': len(empty),
            'empty_primary_fraction': round(len(empty) / len(pairs), 4) if pairs else None,
            'empty_with_secondary': sum(1 for s in pairs if not any_[s]),
            'empty_by_family': {f['id']: sum(1 for s in subs[f['id']] if not primary[s]) for f in fams}}


def table(root: str = ROOT, only: str | None = None) -> str:
    fams, _ = vocabulary(root)
    c, es = counts(root), entries(root)
    sub = Counter(e.family for e in es if e.subset_of)
    rows = ['%-22s %9s %6s %5s  %s' % ('family', 'published', 'target', 'core', 'coverage_status')]
    for f in fams:
        if only and f['id'] != only:
            continue
        rows.append('%-22s %9d %6s %5s  %s%s' % (
            f['id'], c[f['id']], f.get('seed_target', '-'), 'yes' if f.get('core') else '',   # get-default: a target-less family prints '-'
            f.get('coverage_status') or '-',                                                   # get-default: as above
            '   (%d declare lineage.subset_of)' % sub[f['id']] if sub[f['id']] else ''))
    if not only:
        total = sum(f.get('seed_target') or 0 for f in fams)                                   # get-default: as above
        rows.append('%-22s %9d %6d' % ('total', sum(c.values()), total))
        rows.append('%d of %d families non-empty' % (sum(1 for f in fams if c[f['id']]), len(fams)))
    return '\n'.join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--check', action='store_true', help='assert the count is well defined')
    ap.add_argument('--family', help='one domain family')
    ap.add_argument('--assert-min', type=int, help='with --family: exit 1 below this many entries')
    ap.add_argument('--assert-total', type=int, help='exit 1 below this many entries in all')
    ap.add_argument('--assert-min-families', type=int, help='exit 1 with fewer non-empty families')
    ap.add_argument('--report', action='store_true', help='print the table (the default when nothing is asserted)')
    ap.add_argument('--subdomain-emptiness', action='store_true', help='the empty (family, subdomain) share')
    ap.add_argument('--out', help='with --subdomain-emptiness: also write the figure as JSON here')
    a = ap.parse_args(argv)

    fams, _ = vocabulary(a.root)
    if a.family and a.family not in {f['id'] for f in fams}:
        print('FAIL  %s is not a domain family in %s' % (a.family, DOMAINS))
        return 2
    if a.assert_min is not None and not a.family:
        ap.error('--assert-min needs --family')

    fails = []
    if a.check:
        errs = check(a.root)
        fails += errs
        if not errs:
            print('OK    %d published entries, each counted once toward the family of its domain.primary'
                  % len(entries(a.root)))
    c = counts(a.root)
    total = sum(c.values())
    if a.subdomain_emptiness:
        em = emptiness(a.root)
        print('%d of %d (family, subdomain) pairs have no primary entry (%.1f%%) at %d entries; %d with '
              'secondaries counted too' % (em['empty_primary'], em['pairs'], 100 * em['empty_primary_fraction'],
                                           em['entries'], em['empty_with_secondary']))
        if a.out:
            with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(em, fh, indent=1, sort_keys=True)
                fh.write('\n')
    if a.family and a.assert_min is not None:
        n = c[a.family]
        (fails.append if n < a.assert_min else print)(
            '%s %s has %d published entr%s, asserted at least %d' % ('' if n < a.assert_min else 'OK   ',
                                                                        a.family, n, 'y' if n == 1 else 'ies', a.assert_min))
    if a.assert_total is not None:
        (fails.append if total < a.assert_total else print)(
            '%s%d published entries in all, asserted at least %d' % ('' if total < a.assert_total else 'OK    ',
                                                                    total, a.assert_total))
    if a.assert_min_families is not None:
        nonempty = sum(1 for f in fams if c[f['id']])
        (fails.append if nonempty < a.assert_min_families else print)(
            '%s%d families non-empty, asserted at least %d' % ('' if nonempty < a.assert_min_families else 'OK    ',
                                                              nonempty, a.assert_min_families))
    asserted = a.check or a.subdomain_emptiness or a.assert_min is not None or a.assert_total is not None \
        or a.assert_min_families is not None
    if a.report or not asserted:
        print(table(a.root, a.family))
    for f in fails:
        print('FAIL  ' + f.strip())
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
