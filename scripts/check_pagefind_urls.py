#!/usr/bin/env python3
"""The search index holds every rendered route once, in the mode its family is indexed by (P2-S4-T06; 08 S3.2, S7.5).

    python scripts/check_pagefind_urls.py --dist site/dist

08 S3.2: "Duplicate URLs between the two passes are prevented mechanically, not by convention: every entity route
template carries `data-pagefind-ignore` on its `<body>`, so the crawl skips exactly the pages the custom records
already cover. A CI assertion compares the set of indexed URLs against the set of rendered routes and fails on any URL
indexed twice or any narrative route indexed zero times." This is that assertion. S12 (site/src/lib/pagefind.ts) runs
it at the end of every `astro build`, so every site build -- the pull-request workflow's included -- fails on it.

Rendered routes are the .html files under dist/, spelled as Pagefind spells a crawled page (index.html dropped). A page
Astro writes for a redirect (astro.config.mjs `redirects`, a meta refresh) is not a route, and is indexed by neither
mode. Each route's family is tools/build/pagefind_records.py FAMILIES, 08 S7.5's table: a record family (benchmarks,
systems, orgs, metrics, taxonomy terms), an unindexed one (/browse/, version-pinned views, claims tables, claim,
conditions and source pages), or narrative, which is everything else.

Indexed URLs are read from the bundle itself, dist/pagefind/: every fragment (gzip, the `pagefind_dcd` signature, then
JSON carrying the url and the filters) is one indexed record, and pagefind-entry.json's page_count says how many there
are. Pagefind 1.6.0 writes one fragment per record while its `max_fragments` is unset, as S12 leaves it (08 S7.5); a
count that disagrees -- a stale fragment, or a bundle whose fragments were grouped -- fails rather than passing unread.

BLOCKING, each one:

  one index   pagefind-entry.json names one language, `en`: both modes went into one index
  bundle      the fragments are what the entry counts, and each decodes
  twice       no URL is indexed more than once
  rendered    every indexed URL is a rendered route
  records     every route of a record family is indexed exactly once, by its custom record: its fragment's `type`
              filter is the family's own (a crawled copy of an entity page would say `page`, or nothing)
  crawl       every narrative route is indexed exactly once, by the crawl: its `type` is `page` (Base.astro) or absent,
              never a record's
  none        every route of an unindexed family, and every redirect, is indexed zero times
  ignore      the mechanism itself: the <body> of every record and unindexed route carries data-pagefind-ignore, and
              no narrative route's does

Exit codes: 0 clean; 1 a problem; 2 no dist/ or no bundle in it. Standard library only, so any Python runs it.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build.pagefind_records import CRAWL, LANGUAGE, NONE, PAGE, RECORD, TYPE, family  # noqa: E402

BUNDLE = 'pagefind'
ENTRY = 'pagefind-entry.json'
FRAGMENTS = 'fragment'
SIGNATURE = b'pagefind_dcd'
IGNORE = 'data-pagefind-ignore'


class _Page(HTMLParser):
    """The first <body> tag's attributes, and whether the page is a meta-refresh redirect."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body: dict | None = None
        self.redirect = False

    def handle_starttag(self, tag, attrs):
        a = {k: v for k, v in attrs}
        if tag == 'meta' and (a.get('http-equiv') or '').lower() == 'refresh':
            self.redirect = True
        elif tag == 'body' and self.body is None:
            self.body = a

    handle_startendtag = handle_starttag


def page_url(rel: str) -> str:
    """'docs/x/index.html' -> '/docs/x/'; 'index.html' -> '/'; '404.html' -> '/404.html' (Pagefind's spelling)."""
    return '/' + (rel[:-len('index.html')] if rel == 'index.html' or rel.endswith('/index.html') else rel)


def rendered(dist: str) -> dict[str, dict]:
    """url -> {rel, redirect, ignored} for every page under dist/, the bundle's own directory left out."""
    out = {}
    for folder, dirs, names in os.walk(dist):
        if os.path.normpath(folder) == os.path.normpath(dist):
            dirs[:] = [d for d in dirs if d != BUNDLE]
        for n in names:
            if not n.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(folder, n), dist).replace(os.sep, '/')
            with open(os.path.join(folder, n), encoding='utf-8') as fh:
                p = _Page()
                p.feed(fh.read())
                p.close()
            out[page_url(rel)] = {'rel': rel, 'redirect': p.redirect, 'ignored': p.body is not None and IGNORE in p.body}
    return out


def fragments(dist: str) -> tuple[list[dict], list[str]]:
    """(every fragment's JSON, problems) of dist/pagefind/."""
    bundle = os.path.join(dist, BUNDLE)
    problems, found = [], []
    with open(os.path.join(bundle, ENTRY), encoding='utf-8') as fh:
        entry = json.load(fh)
    languages = sorted(entry.get('languages') or {})                     # an entry with none fails below
    if languages != [LANGUAGE]:
        problems.append('%s: languages %s, not one index in %r: both modes go into one index (08 S3.2)'
                        % (ENTRY, languages, LANGUAGE))
    counted = sum(v.get('page_count') or 0 for v in (entry.get('languages') or {}).values())
    top = os.path.join(bundle, FRAGMENTS)
    names = sorted(os.listdir(top)) if os.path.isdir(top) else []
    for n in names:
        with open(os.path.join(top, n), 'rb') as fh:
            raw = fh.read()
        try:
            data = gzip.decompress(raw)
        except OSError as e:
            problems.append('%s/%s: not a gzip fragment (%s)' % (FRAGMENTS, n, e))
            continue
        if not data.startswith(SIGNATURE):
            problems.append('%s/%s: no %s signature, so not a fragment Pagefind wrote' % (FRAGMENTS, n, SIGNATURE.decode()))
            continue
        doc = json.loads(data[len(SIGNATURE):])
        doc['file'] = n
        found.append(doc)
    if len(names) != counted:
        problems.append('%s counts %d indexed page(s), but %s/ holds %d fragment(s): a stale fragment, or a bundle that '
                        'groups fragments, which this check cannot read' % (ENTRY, counted, FRAGMENTS, len(names)))
    return found, problems


def check(dist: str) -> tuple[list[str], dict]:
    """(problems, summary) for a built dist/ with its bundle."""
    pages = rendered(dist)
    found, problems = fragments(dist)
    by_url: dict[str, list[dict]] = {}
    for f in found:
        by_url.setdefault(f.get('url'), []).append(f)
    summary = {'indexed': len(found), 'routes': 0, 'records': {}, 'narrative': 0, 'unindexed': 0, 'redirects': 0}
    for url, fs in sorted(by_url.items(), key=lambda kv: str(kv[0])):
        if len(fs) > 1:
            problems.append('%s: indexed %d times (%s), so a search answers it %d times'
                            % (url, len(fs), ', '.join(f['file'] for f in fs), len(fs)))
        if url not in pages:
            problems.append('%s: indexed, but no page renders it' % url)
    for url, p in sorted(pages.items()):
        hits = by_url.get(url, [])
        types = sorted({t for f in hits for t in (f.get('filters') or {}).get(TYPE) or [PAGE]})   # absent: a crawl
        if p['redirect']:
            summary['redirects'] += 1
            if hits:
                problems.append('%s: a redirect (%s), indexed %d time(s); it is not a route' % (url, p['rel'], len(hits)))
            continue
        summary['routes'] += 1
        name, mode, kind = family(url)
        if mode == RECORD:
            summary['records'][kind] = summary['records'].get(kind, 0) + 1     # get-default: a family's first route
            if not hits:
                problems.append('%s: a %s route indexed zero times; its custom record is missing' % (url, name))
            elif types != [kind]:
                problems.append('%s: a %s route indexed as %s, not by its %s record: the crawl read the page'
                                % (url, name, ', '.join(types), kind))
        elif mode == NONE:
            summary['unindexed'] += 1
            if hits:
                problems.append('%s: a %s route, which 08 S7.5 Decision 2 leaves out of the index, indexed %d time(s)'
                                % (url, name, len(hits)))
        else:
            summary['narrative'] += 1
            if not hits:
                problems.append('%s: a narrative route indexed zero times (%s); the crawl did not index it'
                                % (url, p['rel']))
            elif types != [PAGE]:
                problems.append('%s: a narrative route indexed as %s, which is a record\'s type, not the crawl\'s'
                                % (url, ', '.join(types)))
        if mode in (RECORD, NONE) and not p['ignored']:
            problems.append('%s: a %s route whose <body> lacks %s, so the crawl indexes it as well (Base.astro `search`)'
                            % (url, name, IGNORE))
        if mode == CRAWL and p['ignored']:
            problems.append('%s: a narrative route whose <body> carries %s, so the crawl skips it' % (url, IGNORE))
    return problems, summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--dist', required=True, help='the built site (site/dist)')
    a = p.parse_args(argv)
    if not os.path.isdir(a.dist):
        print('check_pagefind_urls: %s does not exist; build the site first (cd site && npx astro build)' % a.dist)
        return 2
    if not os.path.exists(os.path.join(a.dist, BUNDLE, ENTRY)):
        print('check_pagefind_urls: %s has no %s/%s; S12 (site/src/lib/pagefind.ts) writes it at the end of `astro '
              'build`' % (a.dist, BUNDLE, ENTRY))
        return 2
    problems, s = check(a.dist)
    for line in problems:
        print('BLOCKING  pagefind  %s' % line)
    print('check_pagefind_urls: %d indexed URL(s) over %d route(s): %s record(s) (%s), %d narrative page(s) by the '
          'crawl; %d unindexed route(s) and %d redirect(s) held out; %d problem(s)'
          % (s['indexed'], s['routes'], sum(s['records'].values()),
             ', '.join('%d %s' % (n, k) for k, n in sorted(s['records'].items())) or 'none', s['narrative'],
             s['unindexed'], s['redirects'], len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
