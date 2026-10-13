#!/usr/bin/env python3
"""The tombstone redirect table the site's Worker serves (P2-S3-T08; 04 S3, 05 S2, 10 "Information architecture").

    python tools/build/redirects.py --out site/worker/redirects.json      # regenerate the committed table
    python tools/build/redirects.py --check                               # exit 1 if it is stale

04 S3: "Merges leave a tombstone file carrying `redirects_to`, so old URLs and published citations keep resolving.
A tombstone is a real file with a real id; it is never deleted." A citation to /benchmarks/{old}/ must therefore
keep landing somewhere real, so every tombstone becomes a 301 from its id's route to its target's route, and
site/worker/redirects.ts serves them (the Worker runs on an asset miss, which is exactly a tombstoned path).

The table is built from data/ alone, never from what is published, so that a redirect does not appear and vanish
with a target's verification status:

  route       the route family of the TARGET's record: data/benchmarks/ -> /benchmarks/, data/systems/ ->
              /systems/, data/organizations/ -> /orgs/, data/metrics/ -> /metrics/ (10's URL scheme). A merge
              is within a kind, so the tombstoned id lives in the same family.
  chains      a tombstone pointing at another tombstone resolves to the end of the chain, so a reader gets one
              301, never a hop per merge.
  refusals    a tombstone with no redirects_to, a target that is no record, a cycle, or a tombstoned id that
              still has a live record each fail the build: a citation URL that cannot resolve, or resolves to
              two places, is the thing this exists to prevent.

The table is committed (site/worker/redirects.json) and reviewed with the tombstone that changes it;
tests/build/test_tombstone_redirects.py fails when the two disagree.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402

OUT = os.path.join(ROOT, 'site', 'worker', 'redirects.json')
FAMILIES = {'benchmarks': 'benchmarks', 'systems': 'systems', 'organizations': 'orgs', 'metrics': 'metrics'}


class RedirectError(Exception):
    pass


def records(root: str) -> dict[str, str]:
    """Every record id under the four routed families -> its route segment. Stubs are records too: a merge into
    a stub id still has a page to come."""
    out: dict[str, str] = {}
    for folder, route in FAMILIES.items():
        for path in sorted(glob.glob(os.path.join(root, 'data', folder, '**', '*.yaml'), recursive=True)):
            doc = read_yaml(path)
            ident = doc.get('id') if isinstance(doc, dict) else None     # get-default: a malformed file is tier 1's to report
            if isinstance(ident, str):
                out[ident] = route
    return out


def tombstones(root: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'tombstones', '*.yaml'))):
        doc = read_yaml(path)
        if not isinstance(doc, dict) or not isinstance(doc.get('id'), str):
            raise RedirectError('%s: a tombstone needs an id' % os.path.relpath(path, root))
        out[doc['id']] = doc.get('redirects_to')                          # get-default: a missing target is refused below
    return out


def build(root: str = ROOT) -> dict:
    live = records(root)
    graves = tombstones(root)
    rows = []
    for old in sorted(graves):
        if old in live:
            raise RedirectError('%s is tombstoned but still has a live record' % old)
        seen, target = [old], graves[old]
        while target in graves:
            if target in seen:
                raise RedirectError('tombstone cycle: %s' % ' -> '.join(seen + [target]))
            seen.append(target)
            target = graves[target]
        if target is None:
            raise RedirectError('%s is tombstoned with no redirects_to (via %s)' % (old, ' -> '.join(seen)))
        if target not in live:
            raise RedirectError('%s redirects to %s, which is no benchmark, system, organisation or metric' % (old, target))
        route = live[target]
        rows.append({'from': '/%s/%s/' % (route, old), 'to': '/%s/%s/' % (route, target), 'status': 301})
    return {'artifact': 'redirects', 'format': 1, 'redirects': rows}


def serialise(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--out', default=OUT)
    p.add_argument('--check', action='store_true', help='exit 1 if --out differs from what the tombstones say')
    a = p.parse_args(argv)
    try:
        text = serialise(build(a.root))
    except RedirectError as e:
        print('redirects: %s' % e, file=sys.stderr)
        return 1
    if a.check:
        current = open(a.out, encoding='utf-8').read() if os.path.exists(a.out) else None
        print('redirects: %s' % ('up to date' if current == text else 'STALE; rerun without --check'))
        return 0 if current == text else 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print('wrote %s (%d redirect(s))' % (a.out, len(json.loads(text)['redirects'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
