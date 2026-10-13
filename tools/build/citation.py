#!/usr/bin/env python3
"""Check the built site's citations and footers (P2-S3-T07; 10 "The permanent citation URL", 05 S10, 08 S4.4).

    python tools/build/citation.py --check site/dist      # exit 0 when every citation and footer holds, else 1

site/src/lib/cite.ts writes each benchmark's citation as files beside its page (cite.bib, cite.json, cite.ris,
cite.yaml) and as the page's citation block; site/src/layouts/Base.astro prints the build in every page's footer.
This reads what was built, independently of that code, and reports:

  formats    each file parses by its own format's rules: BibTeX an @misc with title, author, year, \\url and note;
             CSL-JSON one `dataset` item with id, title, URL, issued and accessed; RIS TY - DATA through ER -, with
             CRLF line ends; the raw YAML byte-identical to the record's file in the repository
  agreement  the four, and the page, cite one thing: the same key, title, permalink, commit and DOI; the permalink is
             the record's own YAML path at a 40-digit commit; the DOI is CITATION.cff's concept DOI
  no cache   no format and no citation block points at an artifact URL (/data/...): 08 S4.4, "an artifact URL is a
             cache key, not a citation"
  footers    every page carries the release, the commit SHA and the build timestamp, and the cache-key sentence; one
             build, so one commit and one timestamp across all of them

Croissant JSON-LD, the fifth format 10 names, is P2-S3-T06's (tools/build/croissant.py) and is not checked here.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORMATS = ('bib', 'json', 'ris', 'yaml')
PERMALINK = re.compile(r'^https://github\.com/benchmarkg/benchmarks/blob/([0-9a-f]{40})/(data/benchmarks/[^/]+/[^/]+\.yaml)$')
ARTIFACT = re.compile(r'/data/(?:latest/)?[\w./-]*\.json|/data/latest/')
FOOTER_SENTENCE = 'An artifact URL is a cache key, not a citation'


def concept_doi(root: str) -> str | None:
    path = os.path.join(root, 'CITATION.cff')
    if not os.path.exists(path):
        return None
    m = re.search(r'^doi:\s*(\S+)\s*$', open(path, encoding='utf-8').read(), re.M)
    return m.group(1) if m else None


def parse_bibtex(text: str) -> dict:
    m = re.match(r'@misc\{([A-Za-z0-9-]+),\n', text)
    if not m or not text.rstrip().endswith('}'):
        raise ValueError('not an @misc{key, ...} entry')
    fields = dict(re.findall(r'^  (\w+) = \{(.*)\},?$', text, re.M))
    for f in ('title', 'author', 'year', 'howpublished', 'note'):
        if f not in fields:
            raise ValueError('no %s' % f)
    url = re.fullmatch(r'\\url\{(.+)\}', fields['howpublished'])
    if not url:
        raise ValueError('howpublished is not a \\url{}')
    unescape = lambda s: re.sub(r'\\([&%$#_{}])', r'\1', s)
    return {'key': m.group(1), 'title': unescape(fields['title']), 'url': url.group(1), 'doi': fields.get('doi'),
            'note': unescape(fields['note']), 'year': fields['year']}


def parse_csl(text: str) -> dict:
    items = json.loads(text)
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError('CSL-JSON is a one-item array')
    item = items[0]
    for f in ('id', 'type', 'title', 'URL', 'issued', 'accessed'):
        if f not in item:
            raise ValueError('no %s' % f)
    if item['type'] != 'dataset':
        raise ValueError('type is %r, not dataset' % item['type'])
    return {'key': item['id'], 'title': item['title'], 'url': item['URL'], 'doi': item.get('DOI'), 'note': item.get('note', '')}


def parse_ris(raw: bytes) -> dict:
    text = raw.decode('utf-8')
    if '\n' in text.replace('\r\n', ''):
        raise ValueError('RIS lines must end in CRLF')
    lines = text.split('\r\n')
    if lines[0] != 'TY  - DATA' or lines[-2] != 'ER  - ' or lines[-1] != '':
        raise ValueError('RIS must run from TY  - DATA to ER  - ')
    tags = {}
    for line in lines[1:-2]:
        m = re.fullmatch(r'([A-Z][A-Z0-9])  - (.*)', line)
        if not m:
            raise ValueError('not a RIS line: %r' % line)
        tags.setdefault(m.group(1), m.group(2))
    for t in ('TI', 'UR', 'N1'):
        if t not in tags:
            raise ValueError('no %s' % t)
    return {'title': tags['TI'], 'url': tags['UR'], 'doi': tags.get('DO'), 'note': tags['N1']}


def check_benchmark(dist: str, bid: str, root: str, doi: str | None) -> list[str]:
    here = os.path.join(dist, 'benchmarks', bid)
    out = []
    raw = {}
    for ext in FORMATS:
        path = os.path.join(here, 'cite.' + ext)
        if not os.path.exists(path):
            out.append('%s: no cite.%s' % (bid, ext))
            continue
        raw[ext] = open(path, 'rb').read()
    if out:
        return out
    try:
        parsed = {'bib': parse_bibtex(raw['bib'].decode('utf-8')), 'json': parse_csl(raw['json'].decode('utf-8')),
                  'ris': parse_ris(raw['ris'])}
    except (ValueError, json.JSONDecodeError) as e:
        return ['%s: %s' % (bid, e)]
    bib = parsed['bib']
    m = PERMALINK.match(bib['url'])
    if not m:
        return ['%s: the permalink %s is not a record\'s YAML at a commit' % (bid, bib['url'])]
    commit, yaml_path = m.groups()
    if not yaml_path.endswith('/%s.yaml' % bid):
        out.append('%s: the permalink cites %s' % (bid, yaml_path))
    for fmt, p in parsed.items():
        if p['url'] != bib['url']:
            out.append('%s: cite.%s cites %s, not %s' % (bid, fmt, p['url'], bib['url']))
        if p['title'] != bib['title']:
            out.append('%s: cite.%s titles it %r, not %r' % (bid, fmt, p['title'], bib['title']))
        if p['doi'] != doi:
            out.append('%s: cite.%s carries DOI %r, not the concept DOI %r' % (bid, fmt, p['doi'], doi))
        if commit not in p['note']:
            out.append('%s: cite.%s does not name commit %s' % (bid, fmt, commit))
    if parsed['json']['key'] != bib['key']:
        out.append('%s: CSL-JSON id %s is not the BibTeX key %s' % (bid, parsed['json']['key'], bib['key']))
    record = os.path.join(root, *yaml_path.split('/'))
    if not os.path.exists(record) or open(record, 'rb').read() != raw['yaml']:
        out.append('%s: cite.yaml is not %s as the repository holds it' % (bid, yaml_path))
    for ext in ('bib', 'json', 'ris'):
        if ARTIFACT.search(raw[ext].decode('utf-8')):
            out.append('%s: cite.%s points at an artifact URL' % (bid, ext))
    page = open(os.path.join(here, 'index.html'), encoding='utf-8').read()
    block = re.search(r'<section[^>]*class="cite"[^>]*>(.*?)</section>', page, re.S)
    if not block:
        out.append('%s: the page has no citation block' % bid)
    else:
        b = html.unescape(block.group(1))
        if bib['url'] not in b:
            out.append('%s: the citation block does not link the permalink' % bid)
        if doi is not None and doi not in b:
            out.append('%s: the citation block does not carry the concept DOI' % bid)
        if ARTIFACT.search(b):
            out.append('%s: the citation block points at an artifact URL' % bid)
        for ext in FORMATS:
            if 'href="/benchmarks/%s/cite.%s"' % (bid, ext) not in block.group(1):
                out.append('%s: the citation block does not link cite.%s' % (bid, ext))
    return out


def check_footers(dist: str) -> tuple[list[str], int]:
    out, commits, stamps, n = [], set(), set(), 0
    for folder, _, files in os.walk(dist):
        for name in files:
            if not name.endswith('.html'):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, dist).replace(os.sep, '/')
            page = open(path, encoding='utf-8').read()
            if 'http-equiv="refresh"' in page:                    # a static redirect is not a page
                continue
            n += 1
            foot = re.search(r'<footer[^>]*data-build-footer[^>]*>(.*?)</footer>', page, re.S)
            if not foot:
                out.append('%s: no build footer' % rel)
                continue
            f = foot.group(1)
            commit = re.search(r'data-commit="([0-9a-f]{40})"', f)
            stamp = re.search(r'data-built[^>]*datetime="(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"', f)
            if not re.search(r'data-release', f):
                out.append('%s: the footer names no release' % rel)
            if not commit:
                out.append('%s: the footer carries no commit SHA' % rel)
            else:
                commits.add(commit.group(1))
            if not stamp:
                out.append('%s: the footer carries no build timestamp' % rel)
            else:
                stamps.add(stamp.group(1))
            if FOOTER_SENTENCE not in f:
                out.append('%s: the footer does not say an artifact URL is a cache key, not a citation' % rel)
    if len(commits) > 1 or len(stamps) > 1:
        out.append('one build, but footers carry %d commits and %d timestamps' % (len(commits), len(stamps)))
    return out, n


def check(dist: str, root: str = ROOT) -> tuple[list[str], int, int]:
    doi = concept_doi(root)
    ids = sorted(d for d in os.listdir(os.path.join(dist, 'benchmarks'))
                 if os.path.exists(os.path.join(dist, 'benchmarks', d, 'index.html'))) \
        if os.path.isdir(os.path.join(dist, 'benchmarks')) else []
    out = []
    for bid in ids:
        out += check_benchmark(dist, bid, root, doi)
    footers, pages = check_footers(dist)
    return out + footers, len(ids), pages


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', required=True, metavar='DIST', help='a built site (site/dist)')
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    problems, benchmarks, pages = check(a.check, a.root)
    for line in problems:
        print('BLOCKING  citation  %s' % line)
    print('citation: %d benchmark(s) in four formats and %d page footer(s) checked, %d problem(s)'
          % (benchmarks, pages, len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
