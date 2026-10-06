#!/usr/bin/env python3
"""taxonomy/*.yaml -> site/src/lib/taxonomy.json, the terms the site's components resolve (P2-S2-T06; 09 S6.2).

    python tools/build/site_taxonomy.py            # regenerate in place
    python tools/build/site_taxonomy.py --check    # exit 1 if the committed file differs from a fresh generation

09 S6.2: "Every chip's term_id must resolve in taxonomy/; a chip with an unresolvable term is a build failure,
because a stale chip silently breaks the coverage analysis." The site cannot read YAML, so `bench build` writes
this file beside tokens.json, from the same tree, and the committed copy is the generator's output (the same
drift rule as tools/build/tokens.py). It carries, per facet file:

    facets.<facet>.<term id> = {label, status}     every `terms:` entry of a file that declares `facet:`
    verification             = [rung ids by rank]  taxonomy/verification.yaml's ladder, for the badge's segments

Only the id, label and status travel: definitions and tests stay in taxonomy/, where they are governed.
Deterministic: sorted keys, LF, one trailing newline, no clock.
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAXONOMY = 'taxonomy'
OUT = os.path.join('site', 'src', 'lib', 'taxonomy.json')
FORMAT = 1


def generate(root: str = ROOT) -> bytes:
    from tools.build.tokens import load_yaml, rungs
    facets: dict[str, dict] = {}
    sources = []
    for path in sorted(glob.glob(os.path.join(root, TAXONOMY, '*.yaml'))):
        doc = load_yaml(path)
        if not isinstance(doc, dict) or 'facet' not in doc or 'terms' not in doc:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, '/')
        if doc['facet'] in facets:
            raise ValueError('%s: facet %s is declared by two files' % (rel, doc['facet']))
        facets[doc['facet']] = {t['id']: {'label': t['label'], 'status': t['status']} if 'status' in t
                                else {'label': t['label']} for t in doc['terms']}
        sources.append(rel)
    doc = {'artifact': 'taxonomy', 'format': FORMAT, 'sources': sources + ['taxonomy/verification.yaml'],
           'facets': facets, 'verification': rungs(root)}
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode('utf-8')


def write(root: str = ROOT) -> list[str]:
    path = os.path.join(root, OUT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(generate(root))
    return [OUT]


def stale(root: str = ROOT) -> bool:
    path = os.path.join(root, OUT)
    return not os.path.exists(path) or open(path, 'rb').read() != generate(root)


def main(argv: list[str]) -> int:
    if '--check' in argv:
        if stale():
            print('stale  %s: regenerate with `python tools/build/site_taxonomy.py`' % OUT, file=sys.stderr)
            return 1
        return 0
    for rel in write():
        print('wrote %s' % rel)
    return 0


if __name__ == '__main__':
    sys.path.insert(0, ROOT)
    sys.exit(main(sys.argv[1:]))
