#!/usr/bin/env python3
"""Build-time SVG charts, each emitted with its <table> from one data object (P2-S3-T03; 10 "Technology
decisions", 09 S6.12, S7, S8.4, 08 S4.3, S5.4).

    from tools.build import svgcharts
    r = svgcharts.render(figure)              # r.svg, r.table, r.summary; r.html() is the whole <figure>
    python tools/build/svgcharts.py FIGURE.json [--out PAGE.html]

10 "Technology decisions": sparklines and detail-page charts are "hand-rolled inline SVG generated at build time in
Python ... it can use `currentColor` and CSS custom properties so dark mode is free", and "every chart is generated
from a `{rows, columns, caption, units}` object from which the build emits both the chart and a `<table>`". Both
halves come out of render() from the same object, so the chart and the citable data cannot disagree (09 S6.12).

The figure object, exactly (site/src/lib/chart.ts's ChartData and ChartSpec, in one dict):

    {
      'caption': str,                  required, non-empty: the <figcaption>, which is the SVG's accessible name
      'units':   str | None,           the plotted value's unit, printed after the caption and in the summary
      'notes':   str | None,           optional; printed after the units
      'columns': [                     the table's columns, in order; keys unique
        {'key': str, 'label': str,
         'unit': str | None,           optional; printed in the header cell
         'code': bool,                 optional; the cell is an identifier, set in <code>
         'link': bool,                 optional; a cell whose text is a key of 'links' becomes that link
         'absent': str},               optional; the absence phrase for a None cell (09 S11.2), default not-reported
      ],
      'rows':    [{key: str | int | float | None}],   at least one; every key one a column declares, and a
                                       key left out is None. None is "not reported", never a zero (09 S7.4)
      'links':   {str: str},           optional; cell text -> href, for the columns that set 'link'
      'id':      str | None,           optional; the id prefix. Default: 'fig-' + 10 hex of the object's sha256,
                                       so a figure's ids are a function of its data and never of the clock
      'chart':   {'type': 'bar' | 'line',
                  'x': key,            the category (bar) or the ordered position (line); never None
                  'y': key,            the plotted number
                  'domain': [lo, hi]}  optional; the value axis (09 S7.1: a line starts at the metric's floor, not
                                       at zero by reflex). A bar always includes zero, because a bar is a length
    }

What every SVG here holds to, and the tests (tests/build/test_svgcharts.py) check:

  colour       only `currentColor` and `var(--c-...)` / `var(--seq-...)` tokens (design/tokens.yaml), so the page's
               theme switch recolours it with no second code path; a var() goes in a style="" declaration, where
               every browser substitutes it
  text         every <text> carries its own font-size, in rem at or above 0.6875rem (--fs-2xs, 11px; 09 S3.2: "11px
               is an absolute floor, including inside SVG charts"). It is written as the token's literal rem,
               not var(--fs-2xs), because scripts/lint_svg.mjs cannot read a var() and would pass it unread. The
               <svg> carries width and height equal to its viewBox, so it renders at scale 1 and lint_svg reads the
               size it is drawn at; the page scrolls a wide figure rather than shrinking its text
  ARIA         role="img", aria-labelledby the <figcaption>'s id and aria-describedby the id of a one-sentence
               summary computed here from the same rows (09 S8.4). Never aria-label (09 S6.12)
  escaping     every string from the object is escaped, in text and in attributes
  determinism  no clock, no randomness, no set iteration: one object gives one byte string

The table is the accessible representation (09 S8.4) and the element that exists without JavaScript (09 S8.6).
tools/build/lineage_svg.py draws a benchmark's lineage with this module's table, wrapper and summary rules.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import sys
from typing import NamedTuple

REM = 16                      # px per rem: the root size lint_svg reads rem against
FLOOR_PX = 11                 # 09 S3.2, scripts/lint_svg.mjs FLOOR
FS_2XS = '0.6875rem'          # --fs-2xs, 11px: tick and edge labels, the floor
FS_XS = '0.75rem'             # --fs-xs, 12px: category and node labels
CHAR_EM = 0.6                 # the advance width layout allows per character, in em (IBM Plex Mono's is 0.6)
PAD = 8
ABSENCE = {                   # 09 S11.2's four phrases, as site/src/lib/vocab.ts absencePhrase has them
    'not-reported': 'not reported',
    'not-recorded': 'not recorded',
    'not-applicable': 'not applicable',
    'unknown': 'unknown',
}
TYPES = ('bar', 'line')


class Rendered(NamedTuple):
    """One figure's two halves and the sentence that describes them, plus what the <figure> wrapper needs."""
    svg: str
    table: str
    summary: str
    id: str
    caption: str
    units: str | None
    notes: str | None

    @property
    def caption_id(self) -> str:
        return '%s-caption' % self.id

    @property
    def summary_id(self) -> str:
        return '%s-summary' % self.id

    def html(self) -> str:
        """figure -> figcaption -> svg -> summary -> table: the server-rendered order of 09 S6.12, with the build's
        SVG between the caption and the table and the summary it is described by beside it."""
        return figure_html(self)


# ---- primitives ------------------------------------------------------------------------------------------------

def esc(text) -> str:
    """Text or an attribute value, escaped: & < > " and '."""
    return html.escape(str(text), quote=True)


def num(x: float) -> str:
    """A coordinate: one decimal, no trailing .0, no -0."""
    s = '%.1f' % x
    if s in ('-0.0', '0.0'):
        return '0'
    return s[:-2] if s.endswith('.0') else s


def fmt(value) -> str:
    """A number as the site prints it (site/src/lib/vocab.ts formatValue): digits grouped from five, a true minus."""
    if isinstance(value, bool):
        raise ValueError('svgcharts: %r is a boolean, not a number' % value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('svgcharts: %r is not a finite number' % value)
        if value.is_integer():
            value = int(value)
    s = repr(value) if isinstance(value, float) else str(value)
    if 'e' in s or 'E' in s:
        s = ('%.12f' % value).rstrip('0').rstrip('.')
    neg = s.startswith('-')
    whole, _, frac = s.lstrip('-').partition('.')
    if len(whole) >= 5:
        whole = '{:,}'.format(int(whole))
    return ('−' if neg else '') + whole + ('.' + frac if frac else '')


def with_units(value: str, units: str | None) -> str:
    if units is None:
        return value
    return value + units if units.startswith('%') else '%s %s' % (value, units)


def text_width(text: str, rem: str) -> float:
    """The width layout reserves for `text` at a font size given in rem."""
    return len(str(text)) * CHAR_EM * float(rem[:-3]) * REM


def text_el(x: float, y: float, content: str, size: str, *, anchor: str | None = None, fill: str | None = None,
            weight: int | None = None, cls: str | None = None, style: list[str] | None = None) -> str:
    """A <text> with its own font size; `fill` is a token name (no var()), else the text is currentColor. `style`
    adds declarations that are not colours (a font family, a decoration)."""
    style = ['font-size:%s' % size] + (style or [])
    if fill is not None:
        style.append('fill:var(--%s)' % fill)
    if weight is not None:
        style.append('font-weight:%d' % weight)
    attrs = ['x="%s"' % num(x), 'y="%s"' % num(y)]
    if cls is not None:
        attrs.append('class="%s"' % cls)
    if anchor is not None:
        attrs.append('text-anchor="%s"' % anchor)
    if fill is None:
        attrs.append('fill="currentColor"')
    attrs.append('style="%s"' % ';'.join(style))
    return '<text %s>%s</text>' % (' '.join(attrs), esc(content))


def svg_open(r_id: str, width: float, height: float, kind: str) -> str:
    w, h = num(math.ceil(width)), num(math.ceil(height))
    return ('<svg xmlns="http://www.w3.org/2000/svg" class="svgchart svgchart-%s" role="img" aria-labelledby="%s-caption" '
            'aria-describedby="%s-summary" width="%s" height="%s" viewBox="0 0 %s %s">' % (kind, r_id, r_id, w, h, w, h))


# ---- the data object -------------------------------------------------------------------------------------------

def figure_id(figure: dict) -> str:
    if figure.get('id') is not None:
        return str(figure['id'])
    canon = json.dumps(figure, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return 'fig-%s' % hashlib.sha256(canon.encode('utf-8')).hexdigest()[:10]


def check(figure: dict, *, chart: bool = True) -> None:
    """The shape the docstring gives, or ValueError. `chart=False` checks the table half only (lineage_svg)."""
    if not isinstance(figure.get('caption'), str) or not figure['caption'].strip():
        raise ValueError('svgcharts: a figure needs a non-empty caption')
    for k in ('units', 'notes'):
        if figure.get(k) is not None and not isinstance(figure[k], str):
            raise ValueError('svgcharts: %s is a string or None' % k)
    cols = figure.get('columns')
    if not isinstance(cols, list) or not cols:
        raise ValueError('svgcharts: "%s" has no columns' % figure['caption'])
    keys = [c.get('key') for c in cols]
    if len(set(keys)) != len(keys) or not all(isinstance(k, str) and k for k in keys):
        raise ValueError('svgcharts: "%s" column keys must be unique strings' % figure['caption'])
    for c in cols:
        if not isinstance(c.get('label'), str) or not c['label']:
            raise ValueError('svgcharts: column %s has no label' % c['key'])
        if c.get('absent') is not None and c['absent'] not in ABSENCE:
            raise ValueError('svgcharts: column %s: absence state %r is not one of %s (09 S11.2)'
                             % (c['key'], c['absent'], ', '.join(ABSENCE)))
    rows = figure.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('svgcharts: "%s" has no rows' % figure['caption'])
    for i, r in enumerate(rows):
        for k, v in r.items():
            if k not in keys:
                raise ValueError('svgcharts: row %d has %s, which no column declares' % (i, k))
            if v is not None and (isinstance(v, bool) or not isinstance(v, (str, int, float))):
                raise ValueError('svgcharts: row %d %s is %r: a cell is a string, a number or None' % (i, k, v))
    if not chart:
        return
    spec = figure.get('chart')
    if not isinstance(spec, dict) or spec.get('type') not in TYPES:
        raise ValueError('svgcharts: "%s" needs a chart of type %s' % (figure['caption'], ' or '.join(TYPES)))
    for axis in ('x', 'y'):
        if spec.get(axis) not in keys:
            raise ValueError('svgcharts: chart %s %r is not a column of "%s"' % (axis, spec.get(axis), figure['caption']))
    for i, r in enumerate(rows):
        if r.get(spec['x']) is None:
            raise ValueError('svgcharts: row %d has no %s, the position it is plotted at' % (i, spec['x']))
        y = r.get(spec['y'])
        if y is not None and (isinstance(y, (bool, str)) or not math.isfinite(y)):
            raise ValueError('svgcharts: row %d %s is %r, not a finite number' % (i, spec['y'], y))
    domain = spec.get('domain')
    if domain is not None and (len(domain) != 2 or not domain[0] < domain[1]):
        raise ValueError('svgcharts: chart domain %r is not [lo, hi] with lo < hi' % (domain,))


# ---- the table half --------------------------------------------------------------------------------------------

def absent(state: str) -> str:
    """The absence token, as <Absent> renders it (site/src/components/Absent.astro): never blank, never a dash."""
    return ('<span class="absent" data-absent="%s"><span class="glyph" aria-hidden="true">∅</span> %s</span>'
            % (state, ABSENCE[state]))


def cell(figure: dict, col: dict, value) -> str:
    if value is None:
        return absent(col.get('absent') or 'not-reported')
    text = esc(fmt(value) if isinstance(value, (int, float)) else value)
    if col.get('code'):
        text = '<code>%s</code>' % text
    href = (figure.get('links') or {}).get(value) if col.get('link') and isinstance(value, str) else None
    if href is not None:
        text = '<a href="%s">%s</a>' % (esc(href), text)
    return text


def table_html(figure: dict) -> str:
    """The rows as a <table>: one header row from the columns, one body row per row, every cell filled."""
    cols = figure['columns']
    head = ''.join('<th scope="col">%s%s</th>' % (esc(c['label']), '' if c.get('unit') is None
                                                   else '<span class="unit"> (%s)</span>' % esc(c['unit']))
                   for c in cols)
    body = ''.join('<tr>%s</tr>' % ''.join(
        '<td%s>%s</td>' % (' class="num"' if isinstance(r.get(c['key']), (int, float)) else '', cell(figure, c, r.get(c['key'])))
        for c in cols) for r in figure['rows'])
    return '<table class="svgchart-table" id="%s-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        esc(figure_id(figure)), head, body)


def figure_html(r: Rendered) -> str:
    """The <figure> both halves sit in, for a page that is not an Astro component (LineageFigure.astro writes the same
    order itself): figcaption -> svg -> summary -> table."""
    caption = esc(r.caption)
    if r.units is not None:
        caption += '<span class="units"> (%s)</span>' % esc(r.units)
    if r.notes is not None:
        caption += '<span class="notes"> %s</span>' % esc(r.notes)
    return ('<figure class="svgchart-figure" data-figure="%s"><figcaption id="%s">%s</figcaption>'
            '<div class="svgchart-scroll">%s</div><p class="svgchart-summary" id="%s">%s</p>%s</figure>'
            % (esc(r.id), esc(r.caption_id), caption, r.svg, esc(r.summary_id), esc(r.summary), r.table))


# ---- the summary sentence (09 S8.4: generated by code from structured fields) ------------------------------------

def count_phrase(n: int, one: str, many: str | None = None) -> str:
    return '%d %s' % (n, one if n == 1 else (many or one + 's'))


def summary(figure: dict) -> str:
    """One sentence from the plotted rows: the highest and the lowest (bar), or where the series starts, ends and
    peaks (line), and how many rows report no value."""
    spec, units = figure['chart'], figure.get('units')
    x, y = spec['x'], spec['y']
    rows = figure['rows']
    have = [(r[x], r[y]) for r in rows if r.get(y) is not None]
    missing = len(rows) - len(have)
    tail = '' if not missing else ', %d of them not reported' % missing
    noun = count_phrase(len(rows), 'row')

    def place(p):
        return p[0] if isinstance(p[0], str) else fmt(p[0])

    def value(p):
        return with_units(fmt(p[1]), units)
    if not have:
        return 'None of the %s reports a value.' % noun
    hi = max(have, key=lambda p: p[1])           # max/min keep the first of equal values: row order breaks ties
    lo = min(have, key=lambda p: p[1])
    if spec['type'] == 'bar':
        if len(have) == 1:
            return 'The only reported value is %s at %s, across %s%s.' % (place(hi), value(hi), noun, tail)
        return 'The highest is %s at %s and the lowest is %s at %s, across %s%s.' % (
            place(hi), value(hi), place(lo), value(lo), noun, tail)
    first, last = have[0], have[-1]
    if len(have) == 1:
        return 'The only reported point is %s at %s, across %s%s.' % (value(first), place(first), noun, tail)
    move = 'Rose' if last[1] > first[1] else 'Fell' if last[1] < first[1] else 'Went'
    between = '' if {hi, lo} <= {first, last} else ', between a low of %s and a high of %s' % (value(lo), value(hi))
    return '%s from %s at %s to %s at %s%s, across %s%s.' % (
        move, value(first), place(first), value(last), place(last), between, noun, tail)


# ---- scales ------------------------------------------------------------------------------------------------------

def ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    """Round tick values (1, 2, 2.5 or 5 times a power of ten) covering [lo, hi]."""
    if hi <= lo:
        hi = lo + (abs(lo) or 1)
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag * (1 + 1e-9))
    places = max(0, -math.floor(math.log10(step)) + (1 if step / mag in (2.5, 25) else 0))
    start, end = math.floor(lo / step + 1e-9) * step, math.ceil(hi / step - 1e-9) * step
    n = int(round((end - start) / step))
    return [round(start + i * step, places) for i in range(n + 1)]


# ---- the chart half ----------------------------------------------------------------------------------------------

def bar_svg(figure: dict, fid: str) -> str:
    """Horizontal bars from zero: the category label left, the value at the bar's end, one gridline direction
    (vertical, the one values are read along) behind the marks, the zero rule at --c-border-strong (09 S7.1).
    A None is no bar and the absence phrase where the bar would start (09 S7.4)."""
    spec = figure['chart']
    rows = figure['rows']
    vals = [r.get(spec['y']) for r in rows]
    have = [v for v in vals if v is not None]
    lo = min([0.0] + have + ([spec['domain'][0]] if spec.get('domain') else []))
    hi = max([0.0] + have + ([spec['domain'][1]] if spec.get('domain') else []))
    tk = ticks(lo, hi)
    d0, d1 = tk[0], tk[-1]
    row_h, bar_h, plot_w = 24, 14, 240
    label_w = max(text_width(r[spec['x']] if isinstance(r[spec['x']], str) else fmt(r[spec['x']]), FS_XS) for r in rows)
    value_w = max([text_width(fmt(v), FS_2XS) for v in have] + [text_width('∅ not reported', FS_2XS)])
    x0 = PAD + label_w + PAD + (value_w + 4 if lo < 0 else 0)     # a negative bar's value is written left of it
    top = PAD
    plot_h = len(rows) * row_h
    width = x0 + plot_w + 4 + value_w + PAD
    height = top + plot_h + 4 + FLOOR_PX + PAD

    def sx(v):
        return x0 + (v - d0) / (d1 - d0) * plot_w
    out = [svg_open(fid, width, height, 'bar')]
    out.append('<g class="grid">%s</g>' % ''.join(
        '<line x1="%s" y1="%s" x2="%s" y2="%s" style="stroke:var(--c-border)" stroke-width="1"/>'
        % (num(sx(t)), num(top), num(sx(t)), num(top + plot_h)) for t in tk))
    out.append('<g class="ticks">%s</g>' % ''.join(
        text_el(sx(t), top + plot_h + 4 + FLOOR_PX - 2, fmt(t), FS_2XS, anchor='middle', fill='c-ink-muted') for t in tk))
    for i, (r, v) in enumerate(zip(rows, vals)):
        cy = top + i * row_h + row_h / 2
        cat = r[spec['x']] if isinstance(r[spec['x']], str) else fmt(r[spec['x']])
        parts = [text_el(PAD + label_w, cy + 4, cat, FS_XS, anchor='end', cls='label')]
        if v is None:
            parts.append(text_el(sx(0) + 4, cy + 4, '∅ not reported', FS_2XS, fill='c-absent-ink', cls='absent'))
        else:
            a, b = sorted((sx(0), sx(v)))
            parts.append('<rect x="%s" y="%s" width="%s" height="%s" fill="currentColor"/>'
                         % (num(a), num(cy - bar_h / 2), num(b - a), num(bar_h)))
            parts.append(text_el(b + 4 if v >= 0 else a - 4, cy + 4, fmt(v), FS_2XS, anchor='start' if v >= 0 else 'end',
                                 cls='value'))
        out.append('<g class="mark" data-row="%d"%s>%s</g>' % (
            i, '' if v is None else ' data-value="%s"' % esc(fmt(v)), ''.join(parts)))
    out.append('<line class="axis" x1="%s" y1="%s" x2="%s" y2="%s" style="stroke:var(--c-border-strong)" stroke-width="1"/>'
               % (num(sx(0)), num(top), num(sx(0)), num(top + plot_h)))
    out.append('</svg>')
    return ''.join(out)


def line_svg(figure: dict, fid: str) -> str:
    """Points in row order joined by a line that breaks at a None (a gap, never a zero), horizontal gridlines, the
    baseline at --c-border-strong, the first and last values labelled, and an unknown lane below the axis where
    each None is an open mark at its position (09 S7.4)."""
    spec = figure['chart']
    rows = figure['rows']
    vals = [r.get(spec['y']) for r in rows]
    have = [v for v in vals if v is not None]
    if spec.get('domain'):
        lo, hi = spec['domain']
        lo, hi = min([lo] + have), max([hi] + have)
    else:
        lo, hi = (min(have), max(have)) if have else (0.0, 1.0)
    tk = ticks(lo, hi)
    d0, d1 = tk[0], tk[-1]
    n = len(rows)
    xs = [str(r[spec['x']]) if isinstance(r[spec['x']], str) else fmt(r[spec['x']]) for r in rows]
    labelled = {vals.index(have[0]), n - 1 - vals[::-1].index(have[-1])} if have else set()

    def edge_w(i):                           # half the widest label centred on position i
        return max(6.0, text_width(xs[i], FS_2XS) / 2, text_width(fmt(vals[i]), FS_2XS) / 2 if i in labelled else 0)
    # every position label is drawn, so positions are at least the widest label apart: none overlaps another
    step = max(48.0, max(text_width(s, FS_2XS) for s in xs) + 8)
    tick_w = max(text_width(fmt(t), FS_2XS) for t in tk)
    lane_w = text_width('not reported', FS_2XS) if None in vals else 0
    left = PAD + max(tick_w, lane_w) + 6     # where the gridlines start; the tick labels end 6 before it
    x0 = left + edge_w(0)
    plot_w = max(240.0, step * (n - 1))
    right = x0 + plot_w + edge_w(n - 1)
    top = PAD + FLOOR_PX + 4                 # room for a value label above the highest point
    plot_h = 120
    base = top + plot_h
    lane = base + 8 if None in vals else base
    lane_h = 12 if None in vals else 0
    width = right + PAD
    height = lane + lane_h + 4 + FLOOR_PX + PAD

    def sx(i):
        return x0 + (i / (n - 1) * plot_w if n > 1 else plot_w / 2)

    def sy(v):
        return top + (d1 - v) / (d1 - d0) * plot_h
    out = [svg_open(fid, width, height, 'line')]
    out.append('<g class="grid">%s</g>' % ''.join(
        '<line x1="%s" y1="%s" x2="%s" y2="%s" style="stroke:var(--c-border)" stroke-width="1"/>'
        % (num(left), num(sy(t)), num(right), num(sy(t))) for t in tk[1:]))
    out.append('<g class="ticks">%s</g>' % ''.join(
        text_el(left - 6, sy(t) + 4, fmt(t), FS_2XS, anchor='end', fill='c-ink-muted') for t in tk))
    out.append('<line class="axis" x1="%s" y1="%s" x2="%s" y2="%s" style="stroke:var(--c-border-strong)" stroke-width="1"/>'
               % (num(left), num(base), num(right), num(base)))
    runs, run = [], []
    for i, v in enumerate(vals):
        if v is None:
            if run:
                runs.append(run)
            run = []
        else:
            run.append((sx(i), sy(v)))
    if run:
        runs.append(run)
    d = ' '.join('M%s' % ' L'.join('%s %s' % (num(px), num(py)) for px, py in r) for r in runs if len(r) > 1)
    if d:
        out.append('<path class="line" d="%s" fill="none" stroke="currentColor" stroke-width="1.5"/>' % d)
    if None in vals:
        out.append(text_el(left - 6, lane + 10, 'not reported', FS_2XS, anchor='end', fill='c-absent-ink', cls='lane'))
    for i, v in enumerate(vals):
        parts = []
        if v is None:
            parts.append('<circle cx="%s" cy="%s" r="3" fill="none" style="stroke:var(--c-absent-rule)" stroke-width="1.5"/>'
                         % (num(sx(i)), num(lane + lane_h / 2)))
        else:
            parts.append('<circle cx="%s" cy="%s" r="3" fill="currentColor"/>' % (num(sx(i)), num(sy(v))))
            if i in labelled:
                parts.append(text_el(sx(i), sy(v) - 6, fmt(v), FS_2XS, anchor='middle', cls='value'))
        parts.append(text_el(sx(i), lane + lane_h + 4 + FLOOR_PX - 2, xs[i], FS_2XS, anchor='middle',
                             fill='c-ink-muted', cls='label'))
        out.append('<g class="mark" data-row="%d" data-x="%s"%s>%s</g>' % (
            i, esc(xs[i]), '' if v is None else ' data-value="%s"' % esc(fmt(v)), ''.join(parts)))
    out.append('</svg>')
    return ''.join(out)


def render(figure: dict) -> Rendered:
    """The figure object -> its SVG, its table and its summary (the module docstring gives the object's shape)."""
    check(figure)
    fid = figure_id(figure)
    svg = (bar_svg if figure['chart']['type'] == 'bar' else line_svg)(figure, fid)
    return Rendered(svg, table_html(figure), summary(figure), fid, figure['caption'], figure.get('units'),
                    figure.get('notes'))


def page(figures: list[Rendered], title: str) -> str:
    """A standalone HTML page of figures, for scripts/lint_svg.mjs and for looking at: no styles, no script."""
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>%s</title></head><body>\n%s\n</body></html>\n'
            % (esc(title), '\n'.join(f.html() for f in figures)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('figure', help='a JSON file holding one figure object')
    ap.add_argument('--out', default=None, help='write an HTML page here; default stdout')
    a = ap.parse_args(argv)
    with open(a.figure, encoding='utf-8') as fh:
        r = render(json.load(fh))
    body = page([r], r.caption)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(body)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
