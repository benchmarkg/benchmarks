#!/usr/bin/env python3
"""The draft preview: the site's artifacts with the ai-drafted-unverified entries included (P2-S3-T01).

    uv run python scripts/preview_corpus.py --out build/preview
    cd site && UAIBI_CORPUS=../build/preview/corpus.json UAIBI_SITE_DRAFTS=1 npm run build

No entry is published yet -- every committed benchmark is still an agent's draft, and 05 S4 publishes none of
those -- so a site built over build/corpus.json has no detail pages to test or to look at. This writes, into its
own directory, what `bench build` would write if the drafts that pass tier 1 counted as published:
corpus.json (saying `"drafts": true`), facets.json, derived/adoption.json (tools/build/adoption.py), which the
detail page reads its claim and system counts from, and croissant-benchmark/ (tools/build/croissant.py), validated as
`bench build` validates it, which the detail page inlines and serves as cite.jsonld. site/playwright.config.ts runs it
before the page tests; a person reviewing the drafts can run it to read them rendered.

It also writes what `bench build` writes beside them for the site's own fetches (tools/build/manifest.py `write`, 08
S4.4): data/<name>.<sha8>.json and build-manifest.json, so a preview site names its data artifacts by their hashed URLs,
as the published one does (site/src/lib/manifest.ts dataHref), and the browse view (P2-S4-T04) has a facets.json to
fetch. `python tools/build/manifest.py --site <dist> --build build/preview` copies them into a preview's dist.

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
from tools.build import adoption, artifacts, croissant, manifest  # noqa: E402


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
    documents, problems, summary = croissant.build(result.corpus, result.withheld)
    for e in problems:
        print('error  %s' % e, file=sys.stderr)
    if problems:
        print('preview_corpus: %d croissant-benchmark problem(s); nothing written' % len(problems), file=sys.stderr)
        return 1
    shipped = artifacts.write(result, a.out)
    for path in shipped:
        print('wrote %s' % path)
    croissant.write(documents, os.path.join(a.out, croissant.DIR))
    print('wrote %s (%d benchmark document(s) and the collection)'
          % (os.path.join(a.out, croissant.DIR), summary['written']))
    path = os.path.join(a.out, 'derived', 'adoption.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(adoption.serialise(adoption.build(a.root)))
    print('wrote %s' % path)
    try:
        hashed = manifest.write(a.out, shipped, os.path.join(a.out, croissant.DIR), root=a.root)
    except manifest.ManifestError as e:
        print('preview_corpus: %s' % e, file=sys.stderr)
        return 1
    print('wrote %s (%d content-hashed artifact(s) under %s)' % (hashed[-1], len(hashed) - 1, os.path.join(a.out, 'data')))
    print('preview_corpus: %s, drafts included' % ', '.join('%d %s' % (n, k) for k, n in result.counts().items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
