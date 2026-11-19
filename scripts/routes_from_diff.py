#!/usr/bin/env python3
"""BENCH_ROUTES for a preview build: the routes a diff touches (P2-S1-T04; 08 S3.4, the --routes-from-diff mode).

    uv run bench build --data-only --out build/
    BENCH_ROUTES="$(uv run python scripts/routes_from_diff.py --base origin/main)"
    cd site && BENCH_ROUTES="$BENCH_ROUTES" npm run build     # site/src/lib/bench-routes.ts filters every getStaticPaths()

08 S3.4: "`BENCH_ROUTES`, a newline-separated list of route paths computed by mapping `git diff --name-only
<base>...<head>` through the entity-to-route map". This runs that diff (with --no-renames, so a renamed file's old
and new paths are both mapped), maps each path through tools/build/modes.py `plan`, and prints one route per line,
sorted: `*` alone when the diff touches something every route reads, and nothing at all when it touches no route,
which leaves the fixed narrative routes. --explain writes, per changed path, what it added and why, to stderr.

The map reads which records the head commit publishes from its corpus.json, so the data-only build of the same
checkout runs first (`--corpus`, default build/corpus.json). Records are read at head, and a deleted claim at the merge
base, with read-only git, so --head may name any commit; the corpus must be that commit's. Nothing here decides that
main renders everything: main's build sets no BENCH_ROUTES, and a build of main ignores it (bench-routes.ts).

Exit codes: 0 routes printed; 2 no corpus, or a ref git cannot resolve.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build import modes  # noqa: E402


def default_base() -> str:
    """The pull request's base on GitHub Actions, else origin/main."""
    return 'origin/%s' % (os.environ.get('GITHUB_BASE_REF') or 'main')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--base', default=None, help='the diff base (default: origin/$GITHUB_BASE_REF, else origin/main)')
    p.add_argument('--head', default='HEAD', help='the diff head (default: HEAD)')
    p.add_argument('--corpus', default=os.path.join(ROOT, 'build', 'corpus.json'),
                   help="the head commit's corpus.json, from `bench build --data-only` (default: build/corpus.json)")
    p.add_argument('--root', default=ROOT, help='the repository (default: this checkout)')
    p.add_argument('--out', help='write the routes here as well as to stdout')
    p.add_argument('--explain', action='store_true', help='say, per changed path, what it added and why (stderr)')
    a = p.parse_args(argv)
    if not os.path.exists(a.corpus):
        print('routes_from_diff: %s does not exist; run `uv run bench build --data-only` first, so the map knows which '
              'records this commit publishes' % a.corpus, file=sys.stderr)
        return 2
    with open(a.corpus, encoding='utf-8') as fh:
        corpus = json.load(fh)
    try:
        tree = modes.GitTree(a.root, a.base or default_base(), a.head)
        changed = tree.changed()
    except subprocess.CalledProcessError as e:
        print('routes_from_diff: `%s` failed: %s' % (' '.join(map(str, e.cmd)), (e.stderr or '').strip()), file=sys.stderr)
        return 2
    result = modes.plan(changed, corpus, tree)
    text = ''.join(line + '\n' for line in result.lines())
    if a.explain:
        for path, why in result.why:
            print('%s  ->  %s' % (path, why), file=sys.stderr)
        print('routes_from_diff: %d changed path(s) -> %s' % (len(changed), 'every route' if result.everything else
                                                              '%d route(s) and the fixed narrative routes'
                                                              % len(result.routes)), file=sys.stderr)
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    raw = getattr(sys.stdout, 'buffer', None)            # LF on every platform: a CR would end up in BENCH_ROUTES
    if raw is None:
        sys.stdout.write(text)
    else:
        sys.stdout.flush()
        raw.write(text.encode('utf-8'))
        raw.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
