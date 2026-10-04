#!/usr/bin/env python3
"""Check the built site: no single-aggregator citation figure renders unmarked (P4-S5-T06; 12 S6, 06 S3.10).

    uv run python scripts/check_single_source.py                 # site/dist, after `npx astro build`
    uv run python scripts/check_single_source.py --dist PATH

Every citation count renders through site/src/components/CitationCount.astro, which writes its provenance as
data-* attributes and attaches SingleSourceMarker.astro when the figure is unverified. This reads every built
HTML page back and fails on:

  attributes   a [data-citation-figure] missing data-single-source, data-disagreement, data-value-source or
               data-aggregators -- a figure whose provenance cannot be read is not one this check can clear;
  flag         data-single-source that does not follow from data-aggregators (true exactly when fewer than
               two aggregators support the figure: semantic_scholar.check_figure()'s rule, on the page);
  unmarked     a single-source or disagreeing figure with no [data-marker="unverified"] inside it, or a
               marker that does not say "unverified" in its visible text;
  headline     a figure whose value is OpenAlex's inside h1-h6 or a [data-headline] element (06 S3.10: an
               OpenAlex citation count is never a headline influence number);
  bare-count   a citation count in the page text outside any [data-citation-figure] ("1,234 citations",
               "cited by 56"): a number whose provenance is not on the page is unmarked by definition
               (10, "Design stance" rule 1).

Exit 0 when clean, 1 on any finding, 2 when there is no built site to read.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, 'site', 'dist')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
REQUIRED = ('data-single-source', 'data-disagreement', 'data-value-source', 'data-aggregators')
AGGREGATORS = {'semantic_scholar', 'openalex'}
BARE_COUNT = re.compile(r'\b\d[\d,]*(?:\.\d+)?\s*[kKmM]?\+?\s+(?:citations?|cites|times\s+cited)\b'
                        r'|\bcited\s+(?:by\s+)?\d', re.I)


@dataclass
class Node:
    tag: str
    attrs: dict
    parent: 'Node | None' = None
    children: list = field(default_factory=list)      # Node or str

    def text(self) -> str:
        return ''.join(c if isinstance(c, str) else c.text() for c in self.children)

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.walk()

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node('#root', {})

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else '') for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: (v if v is not None else '') for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:          # close back to the matching open tag, if there is one
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(html: str) -> Node:
    t = _Tree()
    t.feed(html)
    t.close()
    return t.root


def _is_headline(node: Node) -> bool:
    return any(n.tag in HEADINGS or n.attrs.get('data-headline') == 'true' for n in (node, *node.ancestors()))


def _outside_figures(node: Node):
    """Text runs not inside a citation figure, a script or a style."""
    for c in node.children:
        if isinstance(c, str):
            yield c
        elif c.tag not in ('script', 'style') and 'data-citation-figure' not in c.attrs:
            yield from _outside_figures(c)


def check_html(html: str, where: str = '<html>') -> tuple[list[str], int]:
    """(findings, the number of citation figures seen) for one page."""
    root, findings, seen = parse(html), [], 0
    for n in root.walk():
        if 'data-citation-figure' not in n.attrs:
            continue
        seen += 1
        fig = '%s: figure %r' % (where, n.attrs['data-citation-figure'])
        missing = [a for a in REQUIRED if a not in n.attrs]
        if missing:
            findings.append('attributes  %s lacks %s' % (fig, ', '.join(missing)))
            continue
        aggs = n.attrs['data-aggregators'].split()
        single, disagree = n.attrs['data-single-source'], n.attrs['data-disagreement']
        if not aggs or set(aggs) - AGGREGATORS or single not in ('true', 'false') or disagree not in ('true', 'false'):
            findings.append('attributes  %s: unreadable provenance (aggregators %r, single-source %r, '
                            'disagreement %r)' % (fig, aggs, single, disagree))
            continue
        if (single == 'true') != (len(set(aggs)) < 2):
            findings.append('flag        %s: data-single-source="%s" but %d aggregator(s) support it (%s)'
                            % (fig, single, len(set(aggs)), ' '.join(aggs)))
        if single == 'true' or disagree == 'true':
            markers = [m for m in n.walk() if m.attrs.get('data-marker') == 'unverified']
            if not markers:
                findings.append('unmarked    %s is %s and renders without the unverified marker'
                                % (fig, 'single-source' if single == 'true' else 'disagreeing'))
            elif not any('unverified' in m.text().lower() for m in markers):
                findings.append('unmarked    %s: its marker does not say "unverified"' % fig)
        if n.attrs['data-value-source'] == 'openalex' and _is_headline(n):
            findings.append('headline    %s: an OpenAlex citation count as a headline number (06 S3.10)' % fig)
    for run in _outside_figures(root):
        for m in BARE_COUNT.finditer(run):
            findings.append('bare-count  %s: %r outside any citation figure, so its provenance is not on '
                            'the page' % (where, m.group(0)))
    return findings, seen


def check_dist(dist: str) -> tuple[list[str], int, int]:
    """(findings, pages, figures) for every .html file under a built site."""
    findings, pages, figures = [], 0, 0
    for base, _, names in sorted(os.walk(dist)):
        for name in sorted(names):
            if not name.endswith('.html'):
                continue
            path = os.path.join(base, name)
            with open(path, encoding='utf-8') as fh:
                found, seen = check_html(fh.read(), os.path.relpath(path, dist).replace(os.sep, '/'))
            findings += found
            pages += 1
            figures += seen
    return findings, pages, figures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dist', default=DIST, help='the built site (default: site/dist)')
    a = ap.parse_args(argv)
    if not os.path.isdir(a.dist):
        print('check_single_source: no built site at %s; run `npx astro build` in site/ first' % a.dist,
              file=sys.stderr)
        return 2
    findings, pages, figures = check_dist(a.dist)
    if not pages:
        print('check_single_source: %s holds no HTML pages' % a.dist, file=sys.stderr)
        return 2
    for f in findings:
        print(f)
    print('check_single_source: %d page(s), %d citation figure(s), %d finding(s)' % (pages, figures, len(findings)))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
