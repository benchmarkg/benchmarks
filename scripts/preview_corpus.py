#!/usr/bin/env python3
"""The draft preview: the site's artifacts with the ai-drafted-unverified entries included (P2-S3-T01).

    uv run python scripts/preview_corpus.py --out build/preview
    cd site && UAIBI_CORPUS=../build/preview/corpus.json UAIBI_SITE_DRAFTS=1 npm run build

No entry is published yet -- every committed benchmark is still an agent's draft, and 05 S4 publishes none of
those -- so a site built over build/corpus.json has no detail pages to test or to look at. This writes, into its
own directory, what `bench build` would write if the drafts that pass tier 1 counted as published:
corpus.json (saying `"drafts": true`), facets.json, and derived/adoption.json (tools/build/adoption.py), which the
detail page reads its claim and system counts from. site/playwright.config.ts runs it before the page tests; a
person reviewing the drafts can run it to read them rendered.

It is a script rather than a `bench build` flag because 05 S3's code block is the CLI's only specification. It
refuses to write into build/ itself, which is what the site deploys from, and the site refuses to build from a
preview corpus unless UAIBI_SITE_DRAFTS=1 says the build is one (site/src/lib/corpus.ts), so a preview cannot
become the published index by accident.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build import adoption, artifacts  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--out', required=True, help='the preview directory, e.g. build/preview (never build/)')
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(os.path.join(a.root, 'build')):
        print('preview_corpus: build/ is what the site deploys from; write the preview to its own --out, '
              'e.g. build/preview', file=sys.stderr)
        return 2
    result = artifacts.build(a.root, drafts=True)
    for e in result.errors:
        print('error  %s' % e, file=sys.stderr)
    if result.errors:
        print('preview_corpus: %d error(s); nothing written' % len(result.errors), file=sys.stderr)
        return 1
    for path in artifacts.write(result, a.out):
        print('wrote %s' % path)
    path = os.path.join(a.out, 'derived', 'adoption.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(adoption.serialise(adoption.build(a.root)))
    print('wrote %s' % path)
    print('preview_corpus: %s, drafts included' % ', '.join('%d %s' % (n, k) for k, n in result.counts().items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
