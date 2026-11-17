#!/usr/bin/env python3
"""A benchmark's lineage as a build-time SVG plus its table, from one figure object (P2-S3-T03; 10 V6 section 11 and
V1 "Edges", 09 S6.12, S7, S8.4, 04 S3).

    python tools/build/lineage_svg.py --corpus build/corpus.json --out build/derived/lineage.json [--pages DIR]

10 V6, section 11: "Lineage graph -- supersedes, superseded-by, subset-of, extends, decontaminates -- rendered as a
small static SVG ... SWE-bench's six forks, FrontierMath's four variants, HELM's eight." lineage_figure() turns one
benchmark record (its `lineage` block, schema/benchmark.py Lineage) and the set of published ids into a figure
object in tools/build/svgcharts.py's shape; render() draws the SVG from it and emits the table, the wrapper ids and
the summary sentence with svgcharts' rules (currentColor and var() only, no text under 11px, role="img" with
aria-labelledby and aria-describedby, everything escaped, no clock).

Each table row is one edge, read "from RELATION to", and the SVG draws the same rows, each labelled in text:

    schema field                     from     relation         to       detail
    supersedes: [X]                  this     supersedes       X
    superseded_by: [X]               X        supersedes       this
    subset_of: X                     this     subset of        X
    extended_by: [X]                 X        extends          this     (the schema records `extends` from the base)
    decontaminates: X                this     decontaminates   X
    variants: [{id, relation, ...}]  id       variant of       this     the variant's relation, n_items, co_maintainer
    forks: [{id, maintainer, ...}]   id       fork of          this     maintained by <maintainer>
    views: [{name, of, ...}]         name     view of          of       a filter on that board

The first five are 10 V1's typed lineage edges. variants, forks and views are drawn too, under their own relation:
a variant's `relation` is free text ("human-filtered-subset", "successor", "multimodal-extension", ...), so it is
carried in the detail column rather than mapped onto subset_of or extends by guesswork. Not drawn: correlates_with,
which is a measured correlation and not lineage (10 V1 draws it apart, dashed, and only when it has a source), and
`role`, a property of this node that the page prints beside the figure.

A node is linked to /benchmarks/{id}/ when its id is published and it is not the page's own benchmark; any other
node (an id with no page, a view's name) is drawn unlinked. Layout: an entry sits to the LEFT of what it derives
from, so every edge reads left to right as its table row does. The benchmark is rank 0 and an edge's `to` is one
rank right of its `from`, assigned in row order, the first assignment winning; a column holds one rank, its nodes in
order of first appearance and centred on the tallest column. Each edge is an elbow with an arrowhead at `to`, and its
label sits on the segment beside the node farther from the benchmark (labels sharing one segment stack). Node
labels are in the mono face at --fs-xs (12px), whose advance is exactly 0.6em, so the boxes fit them; edge labels
are at --fs-2xs (11px).

The artifact (--out) is {artifact: lineage, format, drafts, benchmarks: {id: entry}}, entry = the figure's caption,
summary, svg, table, their ids and its counts, for every benchmark with at least one edge;
site/src/components/LineageFigure.astro renders an entry. --pages writes one HTML page per figure, for
scripts/lint_svg.mjs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import svgcharts  # noqa: E402
from tools.build.svgcharts import FS_2XS, FS_XS, PAD, esc, num, text_el, text_width  # noqa: E402

FORMAT = 1
RELATIONS = ('supersedes', 'subset of', 'extends', 'decontaminates', 'variant of', 'fork of', 'view of')
NOUNS = {'supersedes': 'supersession', 'subset of': 'subset', 'extends': 'extension',
         'decontaminates': 'decontamination', 'variant of': 'variant', 'fork of': 'fork', 'view of': 'view'}
COLUMNS = [
    {'key': 'from', 'label': 'Entry', 'code': True, 'link': True},
    {'key': 'relation', 'label': 'Relation'},
    {'key': 'to', 'label': 'Related entry', 'code': True, 'link': True},
    {'key': 'detail', 'label': 'Detail', 'absent': 'not-applicable'},
]
NODE_H, PITCH, NODE_PAD = 28, 44, 12          # box height, row pitch, text inset
ELBOW, ARROW = 16, 8
MONO = 'font-family:var(--font-mono)'


def href(benchmark_id: str) -> str:
    return '/benchmarks/%s/' % benchmark_id


def edges(record: dict) -> list[dict]:
    """The record's lineage as table rows, in the module docstring's order."""
    me = record['id']
    lin = record.get('lineage') or {}
    rows = []

    def add(a, relation, b, detail=None):
        rows.append({'from': a, 'relation': relation, 'to': b, 'detail': detail})
    for x in lin.get('supersedes') or []:
        add(me, 'supersedes', x)
    for x in lin.get('superseded_by') or []:
        add(x, 'supersedes', me)
    if lin.get('subset_of') is not None:
        add(me, 'subset of', lin['subset_of'])
    for x in lin.get('extended_by') or []:
        add(x, 'extends', me)
    if lin.get('decontaminates') is not None:
        add(me, 'decontaminates', lin['decontaminates'])
    for v in lin.get('variants') or []:
        detail = [v['relation']]
        if v.get('n_items') is not None:
            detail.append('%s items' % svgcharts.fmt(v['n_items']))
        if v.get('co_maintainer') is not None:
            detail.append('with %s' % v['co_maintainer'])
        add(v['id'], 'variant of', me, ', '.join(detail))
    for f in lin.get('forks') or []:
        add(f['id'], 'fork of', me, 'maintained by %s' % f['maintainer'])
    for v in lin.get('views') or []:
        add(v['name'], 'view of', v['of'], 'a filter on that board')
    return rows


def lineage_figure(record: dict, published) -> dict | None:
    """One benchmark record and the published ids -> its lineage figure object, or None when it records no edge.
    The object is svgcharts' {rows, columns, caption, units} plus `focal` (the record's id), `name` and `links`."""
    rows = edges(record)
    if not rows:
        return None
    me = record['id']
    nodes = []
    for r in rows:
        for n in (r['from'], r['to']):
            if n not in nodes:
                nodes.append(n)
    return {
        'id': 'lineage-%s' % me,
        'caption': 'Lineage of %s' % (record.get('name') or me),
        'units': None,
        'columns': COLUMNS,
        'rows': rows,
        'links': {n: href(n) for n in nodes if n != me and n in published},
        'focal': me,
        'name': record.get('name') or me,
    }


def join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else '%s and %s' % (', '.join(words[:-1]), words[-1])


def summary(figure: dict) -> str:
    """One sentence, from the rows: how many relations of each kind, with how many other entries, and how many of
    those have a page here."""
    rows, me = figure['rows'], figure['focal']
    others = []
    for r in rows:
        for n in (r['from'], r['to']):
            if n != me and n not in others:
                others.append(n)
    kinds = [svgcharts.count_phrase(sum(1 for r in rows if r['relation'] == k), NOUNS[k])
             for k in RELATIONS if any(r['relation'] == k for r in rows)]
    paged = sum(1 for n in others if n in figure['links'])
    pages = ('none of them has a page here' if paged == 0 else 'all of them have a page here' if paged == len(others)
             else '%d of them %s a page here' % (paged, 'has' if paged == 1 else 'have'))
    return "%s's lineage records %s with %s: %s; %s." % (
        figure['name'], svgcharts.count_phrase(len(rows), 'relation'),
        svgcharts.count_phrase(len(others), 'other entry', 'other entries'), join(kinds), pages)


def layout(figure: dict) -> tuple[dict, dict]:
    """rank and in-column position of every node: {node: rank}, {node: index in its column}."""
    me = figure['focal']
    rank, order = {me: 0}, [me]
    pending = list(figure['rows'])
    while pending:
        rest = []
        for r in pending:
            a, b = r['from'], r['to']
            if a in rank and b not in rank:
                rank[b] = rank[a] + 1
                order.append(b)
            elif b in rank and a not in rank:
                rank[a] = rank[b] - 1
                order.append(a)
            elif a not in rank:
                rest.append(r)
        if len(rest) == len(pending):          # a component that never touches this benchmark: anchor it beside it
            rank[rest[0]['to']] = 0
            order.append(rest[0]['to'])
        pending = rest
    slot, last = {}, {}
    for n in order:
        k = rank[n]
        slot[n] = last[k] = last[k] + 1 if k in last else 0
    return rank, slot


def lineage_svg(figure: dict, fid: str) -> str:
    me = figure['focal']
    rows = figure['rows']
    rank, slot = layout(figure)
    ranks = sorted(set(rank.values()))
    col_nodes = {k: [n for n in rank if rank[n] == k] for k in ranks}
    tallest = max(len(v) for v in col_nodes.values())
    col_w = {k: max(text_width(n, FS_XS) for n in col_nodes[k]) + 2 * NODE_PAD for k in ranks}
    gap = {}
    for k in ranks[:-1]:
        labels = [r['relation'] for r in rows if rank[r['to']] - 1 == k]
        gap[k] = max([48.0] + [text_width(lab, FS_2XS) + 12 + ELBOW + ARROW for lab in labels])
    col_x, x = {}, PAD
    for k in ranks:
        col_x[k] = x
        x += col_w[k] + (gap[k] if k in gap else 0)
    # Each label sits on the segment beside its edge's outer node; two edges sharing that segment stack their labels
    # 13 apart, and the top margin makes room for the tallest stack.
    seg = [('from', r['from']) if rank[r['to']] <= 0 else ('to', r['to']) for r in rows]
    stack = max(seg.count(s) for s in seg)
    top = PAD + 13 * (stack - 1)
    width = x + PAD
    height = top + tallest * PITCH - (PITCH - NODE_H) + PAD

    def cy(n):
        k = rank[n]
        return top + (tallest - len(col_nodes[k])) * PITCH / 2 + slot[n] * PITCH + NODE_H / 2
    out = [svgcharts.svg_open(fid, width, height, 'lineage')]
    out.append('<defs><marker id="%s-arrow" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" '
               'markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0 L8 4 L0 8 z" style="fill:var(--c-ink-muted)"/>'
               '</marker></defs>' % esc(fid))
    for i, r in enumerate(rows):
        a, b = r['from'], r['to']
        x1, y1 = col_x[rank[a]] + col_w[rank[a]], cy(a)
        x2, y2 = col_x[rank[b]], cy(b)
        outer_left = rank[b] <= 0                # the edge is left of the benchmark: its outer node is `from`
        ex = x2 - ELBOW - ARROW if outer_left else x1 + ELBOW
        k = seg[:i].count(seg[i])                # labels already on this segment
        lx, ly = (x1 + 6, y1 - 5 - 13 * k) if outer_left else (ex + 6, y2 - 5 - 13 * k)
        out.append('<g class="edge" data-from="%s" data-relation="%s" data-to="%s">'
                   '<path d="M%s %s H%s V%s H%s" fill="none" style="stroke:var(--c-ink-muted)" stroke-width="1.5" '
                   'marker-end="url(#%s-arrow)"/>%s</g>' % (
                       esc(a), esc(r['relation']), esc(b), num(x1), num(y1), num(ex), num(y2), num(x2), esc(fid),
                       text_el(lx, ly, r['relation'], FS_2XS, fill='c-ink-muted', cls='relation')))
    views = {r['from'] for r in rows if r['relation'] == 'view of'}
    for n in rank:
        k = rank[n]
        bx, by = col_x[k], cy(n) - NODE_H / 2
        focal, link = n == me, figure['links'].get(n)
        box = ('<rect x="%s" y="%s" width="%s" height="%s" rx="2" style="fill:var(--c-surface);stroke:%s" '
               'stroke-width="%s"%s/>' % (num(bx), num(by), num(col_w[k]), num(NODE_H),
                                          'currentColor' if focal else 'var(--c-border-strong)', 2 if focal else 1,
                                          ' stroke-dasharray="4 3"' if n in views else ''))
        style = [MONO] + (['text-decoration:underline'] if link is not None else [])
        label = text_el(bx + NODE_PAD, cy(n) + 4, n, FS_XS, weight=600 if focal else None,
                        fill='c-link' if link is not None else None, cls='label', style=style)
        body = box + label
        if link is not None:
            body = '<a href="%s">%s</a>' % (esc(link), body)
        out.append('<g class="node" data-id="%s" data-linked="%s"%s>%s</g>' % (
            esc(n), 'false' if link is None else 'true', ' data-focal="true"' if focal else '', body))
    out.append('</svg>')
    return ''.join(out)


def render(figure: dict) -> svgcharts.Rendered:
    """The lineage figure object -> its SVG, its table and its summary."""
    svgcharts.check(figure, chart=False)
    for r in figure['rows']:
        if r['relation'] not in RELATIONS:
            raise ValueError('lineage_svg: %r is not one of %s' % (r['relation'], ', '.join(RELATIONS)))
    fid = svgcharts.figure_id(figure)
    return svgcharts.Rendered(lineage_svg(figure, fid), svgcharts.table_html(figure), summary(figure), fid,
                              figure['caption'], figure.get('units'), figure.get('notes'))


def entry(r: svgcharts.Rendered, figure: dict) -> dict:
    """What LineageFigure.astro reads for one benchmark."""
    others = {n for row in figure['rows'] for n in (row['from'], row['to'])} - {figure['focal']}
    return {'id': r.id, 'caption': r.caption, 'caption_id': r.caption_id, 'summary': r.summary,
            'summary_id': r.summary_id, 'svg': r.svg, 'table': r.table,
            'relations': len(figure['rows']), 'related': len(others)}


def build(corpus: dict) -> tuple[dict, list[svgcharts.Rendered]]:
    """corpus.json -> the lineage artifact, and the rendered figures in id order."""
    benchmarks = sorted(corpus['entities']['benchmark'], key=lambda b: b['id'])
    published = {b['id'] for b in benchmarks}
    out, figures = {}, []
    for b in benchmarks:
        fig = lineage_figure(b, published)
        if fig is None:
            continue
        r = render(fig)
        out[b['id']] = entry(r, fig)
        figures.append(r)
    return {'artifact': 'lineage', 'format': FORMAT, 'drafts': corpus.get('drafts') is True, 'benchmarks': out}, figures


def serialised(corpus: dict) -> bytes:
    from tools.build.artifacts import nfc, serialise
    return serialise(nfc(build(corpus)[0]))


def write(corpus: dict, path: str) -> str:
    """The lineage artifact for `corpus` at `path`; what `bench build --derived` calls."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(serialised(corpus))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--corpus', default=os.path.join(ROOT, 'build', 'corpus.json'), help='the corpus artifact to read')
    ap.add_argument('--out', default=None, help='write the lineage artifact here; default stdout')
    ap.add_argument('--pages', default=None, help='also write one HTML page per figure into this directory')
    a = ap.parse_args(argv)
    with open(a.corpus, encoding='utf-8') as fh:
        corpus = json.load(fh)
    if corpus.get('artifact') != 'corpus':
        print('lineage_svg: %s is not the corpus artifact' % a.corpus, file=sys.stderr)
        return 2
    _, figures = build(corpus)
    if a.out:
        write(corpus, a.out)
    else:
        sys.stdout.buffer.write(serialised(corpus))
    if a.pages:
        os.makedirs(a.pages, exist_ok=True)
        for r in figures:
            with open(os.path.join(a.pages, '%s.html' % r.id), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(svgcharts.page([r], r.caption))
    return 0


if __name__ == '__main__':
    sys.exit(main())
