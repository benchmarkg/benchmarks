#!/usr/bin/env python3
"""Checks 9d and 9e: homographs declared, and their tautological coverage cells flagged (P0-S6-T05; 05 S9,
D3, 08 S3, 12).

  9d  homograph declaration   the capability ids equal to a subdomain leaf, computed from capabilities.yaml
                              and domains.yaml, are exactly the pairs taxonomy/homographs.yaml declares,
                              each with a relationship and a rationale, and a false-friend pair carries
                              not_to_be_confused_with on both terms (scripts/taxonomy_stats.py's 9d, run here
                              against this tree).
  9e  tautological cells      for every `same-concept-two-facets` declaration, the fine-grid cell (subdomain
                              F/X, capability X) is occupied by construction, so `bench build --derived`
                              flags it `degenerate: tautological-homograph` in build/derived/coverage.json;
                              the flagged set must equal the declarations, no more and no fewer.

coverage.json is the coverage build's (08 S3: sparse, the non-empty cells plus the `degenerate` flags). A
flagged cell is any object in it carrying `degenerate: tautological-homograph`; it names its pair by
`subdomain` (or `domain`) and `capability`, bare or facet-qualified. Until the coverage build emits the file,
9e reports PENDING, which does not fail: a check that has nothing to read is not a pass either, and says so.

    python scripts/check_homographs.py                       # check; exit 1 on a failure
    python scripts/check_homographs.py --root DIR            # another tree (the tests do)
    python scripts/check_homographs.py --coverage PATH       # another coverage.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_identifiers import ROOT, stats  # noqa: E402

COVERAGE = os.path.join('build', 'derived', 'coverage.json')
FLAG = 'tautological-homograph'


def bare(ref: str) -> str:
    return str(ref).split(':', 1)[-1]


def declared_cells(ts) -> set[tuple[str, str]]:
    hom = ts.load_facet('homographs') or {}
    return {(bare(e['domain']), bare(e['capability'])) for e in hom.get('entries') or []
            if e.get('relationship') == 'same-concept-two-facets'}


def flagged_cells(doc) -> set[tuple[str, str]]:
    out = set()

    def walk(x):
        if isinstance(x, dict):
            if x.get('degenerate') == FLAG:
                sub = x['subdomain'] if 'subdomain' in x else x['domain']
                out.add((bare(sub), bare(x['capability'])))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    return out


def check_9e(r, ts, path: str):
    want = declared_cells(ts)
    if not os.path.exists(path):
        return r.pend('9e tautological cells', '%s is not built yet; %d declared cell(s) to flag when it is'
                      % (os.path.relpath(path, ROOT).replace(os.sep, '/') if path.startswith(ROOT) else path,
                         len(want)))
    with open(path, encoding='utf-8') as fh:
        got = flagged_cells(json.load(fh))
    problems = []
    if want - got:
        problems.append('not flagged: %s' % sorted('%s x %s' % c for c in want - got))
    if got - want:
        problems.append('flagged but not declared same-concept-two-facets: %s' % sorted('%s x %s' % c for c in got - want))
    if problems:
        return r.fail('9e tautological cells', '; '.join(problems))
    r.ok('9e tautological cells', '%d flagged, equal to the declarations' % len(got))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--coverage', default=None)
    a = p.parse_args(argv)
    ts = stats(a.root)
    r = ts.Result()
    ts.check_9d(r)
    check_9e(r, ts, a.coverage or os.path.join(a.root, COVERAGE))
    print('check_homographs: %d passed, %d failed, %d pending' % (len(r.passed), len(r.failed), len(r.pending)))
    return 1 if r.failed else 0


if __name__ == '__main__':
    sys.exit(main())
