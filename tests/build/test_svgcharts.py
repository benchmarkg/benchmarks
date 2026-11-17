"""Tests for the build-time SVG charts and the lineage renderer (P2-S3-T03; tools/build/svgcharts.py,
tools/build/lineage_svg.py; 10 "Technology decisions", 09 S6.12, S7, S8.4).

The verify: "uv run pytest tests/build/test_svgcharts.py && node scripts/lint_svg.mjs build/". Done when: "Each figure
emits a chart and a table from one data object, a SWE-bench fixture with six forks renders its lineage SVG plus table,
and no SVG text is below 11px." So, per figure kind (bar, line, lineage):

  - one object gives an SVG and a <table> carrying the same values, row for row, and a missing value is the absence
    token in the table and no mark (an unknown-lane mark for a line) in the SVG -- never a zero;
  - the SVG is role="img", aria-labelledby its <figcaption> and aria-describedby a one-sentence summary that the
    figure's HTML holds; there is no aria-label;
  - every <text> has its own font-size at or above 11px, and the SVG is drawn at scale 1;
  - every colour is currentColor or a var() of a token design/tokens.yaml defines;
  - one object renders to one byte string, and its ids come from its data;
  - `<` and `&` in any label are escaped in the SVG, the table and the figure;
  - the SWE-bench fixture (tests/build/fixtures/lineage/swe-bench.yaml, the record's lineage block) draws the six
    members of the family and every edge in both halves, published ids linked and the rest not.

test_figures_written_for_lint_svg writes every figure these tests make into build/svgcharts/, which the verify's
`node scripts/lint_svg.mjs build/` then reads, and runs lint_svg on them itself when node is on PATH.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import lineage_svg, svgcharts  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'lineage', 'swe-bench.yaml')
BUILD = os.path.join(ROOT, 'build', 'svgcharts')
TOKENS = os.path.join(ROOT, 'site', 'src', 'lib', 'tokens.json')
SIX = ['swe-bench', 'swe-bench-verified', 'swe-bench-lite', 'swe-bench-multimodal', 'swe-bench-multilingual',
       'swe-bench-pro']                      # 02's "six forks: original, Verified, Lite, Multimodal, Multilingual, Pro"
PUBLISHED = {'swe-bench', 'swe-bench-verified', 'swe-bench-pro'}
COLOUR_PROPS = ('fill', 'stroke', 'color', 'stop-color', 'flood-color', 'lighting-color')
VOID = {'br', 'hr', 'img', 'input', 'meta', 'link', 'col', 'wbr'}


def bar_figure(**over) -> dict:
    fig = {'caption': 'Rows by rule', 'units': 'rows',
           'columns': [{'key': 'rule', 'label': 'Rule'}, {'key': 'n', 'label': 'Rows'}],
           'rows': [{'rule': 'public', 'n': 828}, {'rule': 'private', 'n': 459}, {'rule': 'none', 'n': None},
                    {'rule': 'returned', 'n': -12}, {'rule': 'big', 'n': 12345.5}],
           'chart': {'type': 'bar', 'x': 'rule', 'y': 'n'}}
    fig.update(over)
    return fig


def line_figure(**over) -> dict:
    fig = {'caption': 'Highest reported value', 'units': '%',
           'columns': [{'key': 'month', 'label': 'Month'}, {'key': 'v', 'label': 'Value', 'unit': '%'}],
           'rows': [{'month': '2023-03', 'v': 34}, {'month': '2023-09', 'v': None}, {'month': '2024-05', 'v': 52.5},
                    {'month': '2025-01', 'v': 49}, {'month': '2026-08', 'v': 71}],
           'chart': {'type': 'line', 'x': 'month', 'y': 'v', 'domain': [25, 100]}}
    fig.update(over)
    return fig


def swe_bench() -> dict:
    with open(FIXTURE, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def lineage_rendered():
    fig = lineage_svg.lineage_figure(swe_bench(), PUBLISHED)
    return fig, lineage_svg.render(fig)


def all_rendered() -> list:
    return [svgcharts.render(bar_figure()), svgcharts.render(line_figure()), lineage_rendered()[1],
            svgcharts.render(nasty_figure()), lineage_svg.render(lineage_svg.lineage_figure(every_relation(), {'old', 'z'}))]


def nasty_figure() -> dict:
    return bar_figure(caption='A <b>bold</b> & "quoted" caption', units='<units> & more', notes='notes & <i>',
                      rows=[{'rule': '<script>alert(1)</script>', 'n': 1}, {'rule': 'R&D "x" \'y\'', 'n': 2}],
                      columns=[{'key': 'rule', 'label': 'Rule <th>'}, {'key': 'n', 'label': 'N & M', 'unit': '<u>'}])


def every_relation() -> dict:
    return {'id': 'mid', 'name': 'Middle & <Co>', 'lineage': {
        'role': 'root',
        'supersedes': ['old'], 'superseded_by': ['new'], 'subset_of': 'whole', 'extended_by': ['ext'],
        'decontaminates': 'dirty',
        'correlates_with': [{'benchmark': 'corr', 'coefficient': 0.9, 'source': 'src-x'}],
        'variants': [{'id': 'v1', 'relation': 'refined-subset', 'n_items': 12000, 'co_maintainer': 'Org <A>',
                      'source': 'src-v'}],
        'forks': [{'id': 'z', 'maintainer': 'Another lab', 'source': 'src-f'}],
        'views': [{'name': 'Easy & <hard>', 'of': 'v1', 'source': 'src-w'}]}}


class Tree(HTMLParser):
    """Every element of a fragment: {tag, attrs, text (all descendant text, entities resolved), parent}."""

    def __init__(self, markup: str):
        super().__init__(convert_charrefs=True)
        self.els, self.stack = [], []
        self.feed(markup)
        self.close()

    def _add(self, tag, attrs) -> int:
        self.els.append({'tag': tag, 'attrs': dict(attrs), 'text': '', 'parent': self.stack[-1] if self.stack else None})
        return len(self.els) - 1

    def handle_starttag(self, tag, attrs):
        i = self._add(tag, attrs)
        if tag not in VOID:
            self.stack.append(i)

    def handle_startendtag(self, tag, attrs):
        self._add(tag, attrs)

    def handle_endtag(self, tag):
        for j in range(len(self.stack) - 1, -1, -1):
            if self.els[self.stack[j]]['tag'] == tag:
                del self.stack[j:]
                return

    def handle_data(self, data):
        for i in self.stack:
            self.els[i]['text'] += data

    def find(self, tag, cls=None) -> list:
        return [e for e in self.els if e['tag'] == tag
                and (cls is None or cls in (e['attrs'].get('class') or '').split())]

    def inside(self, el, tag, cls=None) -> list:
        i = self.els.index(el)

        def under(e):
            p = e['parent']
            while p is not None:
                if p == i:
                    return True
                p = self.els[p]['parent']
            return False
        return [e for e in self.find(tag, cls) if under(e)]


def table_rows(markup: str) -> list:
    t = Tree(markup)
    return [[c['text'] for c in t.inside(tr, 'td')] for tr in t.inside(t.find('tbody')[0], 'tr')]


def styles(el) -> dict:
    out = {}
    for decl in (el['attrs'].get('style') or '').split(';'):
        if ':' in decl:
            k, v = decl.split(':', 1)
            out[k.strip()] = v.strip()
    return out


# ---- one object, two halves -----------------------------------------------------------------------------------

def test_a_bar_figure_emits_an_svg_and_a_table_with_the_same_values():
    fig = bar_figure()
    r = svgcharts.render(fig)
    assert r.svg.startswith('<svg') and r.table.startswith('<table')
    svg = Tree(r.svg)
    marks = svg.find('g', 'mark')
    rows = table_rows(r.table)
    assert len(marks) == len(rows) == len(fig['rows'])
    for i, (row, mark, cells) in enumerate(zip(fig['rows'], marks, rows)):
        assert mark['attrs']['data-row'] == str(i)
        assert svg.inside(mark, 'text', 'label')[0]['text'] == row['rule'] == cells[0]
        if row['n'] is None:
            assert 'data-value' not in mark['attrs'] and not svg.inside(mark, 'rect')     # no bar: never a zero
            assert cells[1] == '∅ not reported' and 'not reported' in mark['text']
        else:
            value = svgcharts.fmt(row['n'])
            assert mark['attrs']['data-value'] == value == cells[1]
            assert svg.inside(mark, 'text', 'value')[0]['text'] == value
            assert len(svg.inside(mark, 'rect')) == 1
    assert rows[3][1] == '−12' and rows[4][1] == '12,345.5'       # the site's formatValue: a true minus, grouping


def test_a_line_figure_emits_an_svg_and_a_table_with_the_same_values():
    fig = line_figure()
    r = svgcharts.render(fig)
    svg = Tree(r.svg)
    marks = svg.find('g', 'mark')
    rows = table_rows(r.table)
    assert len(marks) == len(rows) == len(fig['rows'])
    for row, mark, cells in zip(fig['rows'], marks, rows):
        assert mark['attrs']['data-x'] == row['month'] == cells[0]
        if row['v'] is None:
            assert 'data-value' not in mark['attrs'] and cells[1] == '∅ not reported'
            assert svg.inside(mark, 'circle')[0]['attrs']['fill'] == 'none'               # the open unknown-lane mark
        else:
            assert mark['attrs']['data-value'] == svgcharts.fmt(row['v']) == cells[1]
    path = svg.find('path', 'line')[0]['attrs']['d']
    assert path.count('M') == 1 and path.count('L') == 2       # the gap at 2023-09 breaks the line; 34 stands alone
    assert 'not reported' in svg.find('text', 'lane')[0]['text']


def test_the_table_header_carries_labels_and_units_and_a_cell_is_never_blank():
    r = svgcharts.render(line_figure())
    t = Tree(r.table)
    assert [th['text'] for th in t.find('th')] == ['Month', 'Value (%)']
    assert all(th['attrs']['scope'] == 'col' for th in t.find('th'))
    assert all(td['text'].strip() for td in t.find('td'))


def test_the_summary_is_one_sentence_computed_from_the_rows():
    assert svgcharts.render(bar_figure()).summary == (
        'The highest is big at 12,345.5 rows and the lowest is returned at −12 rows, across 5 rows, '
        '1 of them not reported.')
    assert svgcharts.render(line_figure()).summary == (
        'Rose from 34% at 2023-03 to 71% at 2026-08, across 5 rows, 1 of them not reported.')
    lone = bar_figure(rows=[{'rule': 'a', 'n': None}, {'rule': 'b', 'n': 3}])
    assert svgcharts.render(lone).summary == 'The only reported value is b at 3 rows, across 2 rows, 1 of them not reported.'
    none = bar_figure(rows=[{'rule': 'a', 'n': None}])
    assert svgcharts.render(none).summary == 'None of the 1 row reports a value.'
    dip = line_figure(rows=[{'month': 'a', 'v': 5}, {'month': 'b', 'v': 1}, {'month': 'c', 'v': 9}, {'month': 'd', 'v': 4}])
    assert svgcharts.render(dip).summary == 'Fell from 5% at a to 4% at d, between a low of 1% and a high of 9%, across 4 rows.'
    for r in all_rendered():
        assert r.summary.endswith('.') and not re.search(r'[.;:!?]\s+[A-Z]', r.summary), r.summary


# ---- ARIA -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('r', all_rendered(), ids=lambda r: r.id)
def test_role_img_labelled_by_the_figcaption_and_described_by_the_summary(r):
    page = Tree(r.html())
    svg = page.find('svg')[0]
    assert svg['attrs']['role'] == 'img'
    caption = [e for e in page.els if e['attrs'].get('id') == svg['attrs']['aria-labelledby']]
    summary = [e for e in page.els if e['attrs'].get('id') == svg['attrs']['aria-describedby']]
    assert len(caption) == 1 and caption[0]['tag'] == 'figcaption'
    assert len(summary) == 1 and summary[0]['text'] == r.summary
    assert caption[0]['text'].startswith(r.caption)
    assert 'aria-label=' not in r.html()                          # 09 S6.12: never rely on aria-label
    order = [e['tag'] for e in page.els if e['tag'] in ('figure', 'figcaption', 'svg', 'p', 'table')]
    assert order == ['figure', 'figcaption', 'svg', 'p', 'table']


# ---- 11px, colour, determinism, escaping --------------------------------------------------------------------------

@pytest.mark.parametrize('r', all_rendered(), ids=lambda r: r.id)
def test_no_text_below_11px_and_drawn_at_scale_1(r):
    svg = Tree(r.svg)
    root = svg.find('svg')[0]['attrs']
    assert root['viewbox'] == '0 0 %s %s' % (root['width'], root['height'])      # scale 1: drawn at its authored size
    texts = svg.find('text') + svg.find('tspan')
    assert texts
    for t in texts:
        size = styles(t)['font-size']
        assert size.endswith('rem') and float(size[:-3]) * svgcharts.REM >= svgcharts.FLOOR_PX, (t['text'], size)
        assert 'font-size' not in t['attrs']


@pytest.mark.parametrize('r', all_rendered(), ids=lambda r: r.id)
def test_colours_are_only_currentcolor_and_token_vars(r):
    with open(TOKENS, encoding='utf-8') as fh:
        tokens = set(json.load(fh)['themes']['light'])
    used = set()
    for el in Tree(r.svg).els:
        values = [el['attrs'][p] for p in COLOUR_PROPS if p in el['attrs']]
        values += [v for p, v in styles(el).items() if p in COLOUR_PROPS]
        for v in values:
            m = re.fullmatch(r'var\(--([a-z0-9-]+)\)', v)
            assert v in ('currentColor', 'none') or m, v
            if m:
                used.add(m.group(1))
    assert used and used <= tokens, used - tokens
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(', r.svg)


def test_output_is_deterministic_and_ids_come_from_the_data():
    a, b = svgcharts.render(bar_figure()), svgcharts.render(bar_figure())
    assert a == b and a.html() == b.html()
    assert a.id == svgcharts.render(bar_figure()).id != svgcharts.render(bar_figure(caption='Other')).id
    assert re.fullmatch(r'fig-[0-9a-f]{10}', a.id)
    assert lineage_rendered()[1] == lineage_rendered()[1]
    for mod in (svgcharts, lineage_svg):
        src = open(mod.__file__, encoding='utf-8').read()
        assert not re.search(r'^\s*(?:import|from)\s+(?:time|datetime|random|uuid)\b', src, re.M), mod.__name__


def test_lt_and_amp_in_labels_are_escaped_everywhere():
    fig = nasty_figure()
    r = svgcharts.render(fig)
    whole = r.html()
    assert '<script' not in whole and '<b>' not in whole and '<i>' not in whole and '<u>' not in whole
    assert '&lt;script&gt;' in r.svg and '&lt;script&gt;' in r.table
    assert 'R&amp;D &quot;x&quot; &#x27;y&#x27;' in r.svg
    page = Tree(whole)
    assert page.find('figcaption')[0]['text'] == 'A <b>bold</b> & "quoted" caption (<units> & more) notes & <i>'
    assert [row[0] for row in table_rows(r.table)] == ['<script>alert(1)</script>', 'R&D "x" \'y\'']
    assert [t['text'] for t in Tree(r.svg).find('text', 'label')] == ['<script>alert(1)</script>', 'R&D "x" \'y\'']
    assert [th['text'] for th in page.find('th')] == ['Rule <th>', 'N & M (<u>)']
    lin = lineage_svg.render(lineage_svg.lineage_figure(every_relation(), set()))
    assert '<hard>' not in lin.svg and 'Easy &amp; &lt;hard&gt;' in lin.svg and 'data-from="Easy &amp; &lt;hard&gt;"' in lin.svg
    assert "Middle & <Co>'s lineage" in lin.summary and '<Co>' not in lin.html()


def test_a_malformed_figure_is_refused():
    for bad, msg in [
        (bar_figure(caption=' '), 'caption'),
        (bar_figure(rows=[]), 'no rows'),
        (bar_figure(rows=[{'rule': 'a', 'n': 1, 'extra': 2}]), 'no column declares'),
        (bar_figure(rows=[{'rule': None, 'n': 1}]), 'plotted at'),
        (bar_figure(rows=[{'rule': 'a', 'n': True}]), 'a cell is'),
        (bar_figure(rows=[{'rule': 'a', 'n': 'ten'}]), 'not a finite number'),
        (bar_figure(chart={'type': 'pie', 'x': 'rule', 'y': 'n'}), 'chart of type'),
        (bar_figure(chart={'type': 'bar', 'x': 'rule', 'y': 'nope'}), 'not a column'),
        (bar_figure(columns=[{'key': 'rule', 'label': 'Rule'}, {'key': 'n', 'label': 'N', 'absent': 'n/a'}]), 'absence state'),
        (line_figure(chart={'type': 'line', 'x': 'month', 'y': 'v', 'domain': [5, 5]}), 'domain'),
    ]:
        with pytest.raises(ValueError, match=msg):
            svgcharts.render(bad)


# ---- lineage ------------------------------------------------------------------------------------------------------

def test_lineage_edges_map_from_every_schema_field():
    rows = lineage_svg.edges(every_relation())
    assert [(r['from'], r['relation'], r['to']) for r in rows] == [
        ('mid', 'supersedes', 'old'), ('new', 'supersedes', 'mid'), ('mid', 'subset of', 'whole'),
        ('ext', 'extends', 'mid'), ('mid', 'decontaminates', 'dirty'), ('v1', 'variant of', 'mid'),
        ('z', 'fork of', 'mid'), ('Easy & <hard>', 'view of', 'v1')]
    assert 'corr' not in {n for r in rows for n in (r['from'], r['to'])}      # a correlation is not lineage
    assert rows[5]['detail'] == 'refined-subset, 12,000 items, with Org <A>'
    assert rows[6]['detail'] == 'maintained by Another lab'
    assert [r['detail'] for r in rows[:5]] == [None] * 5
    assert lineage_svg.lineage_figure({'id': 'x', 'lineage': {'role': 'root'}}, set()) is None
    assert lineage_svg.lineage_figure({'id': 'x'}, set()) is None


def test_the_swe_bench_fixture_draws_its_six_forks_and_every_edge_in_both_halves():
    fig, r = lineage_rendered()
    assert fig['rows'] and svgcharts.check(fig, chart=False) is None
    svg = Tree(r.svg)
    nodes = {n['attrs']['data-id']: n for n in svg.find('g', 'node')}
    table = table_rows(r.table)
    named = {c for row in table for c in (row[0], row[2])}
    for member in SIX:                                                   # the six forks, in the SVG and the table
        assert member in nodes and member in named, member
        assert svg.inside(nodes[member], 'text', 'label')[0]['text'] == member
    assert len(table) == len(fig['rows']) == 6
    edges = [(e['attrs']['data-from'], e['attrs']['data-relation'], e['attrs']['data-to'], svg.inside(e, 'text')[0]['text'])
             for e in svg.find('g', 'edge')]
    assert edges == [(row[0], row[1], row[2], row[1]) for row in table]   # every edge, labelled in text, in table order
    assert sorted(row[1] for row in table) == ['fork of'] + ['variant of'] * 4 + ['view of']
    assert all(len(svg.inside(e, 'path')) == 1 and 'marker-end' in svg.inside(e, 'path')[0]['attrs'] for e in svg.find('g', 'edge'))
    assert r.summary == ("SWE-bench's lineage records 6 relations with 6 other entries: 4 variants, 1 fork and 1 view; "
                         '2 of them have a page here.')
    assert r.caption == 'Lineage of SWE-bench' and r.id == 'lineage-swe-bench'


def test_published_ids_are_linked_and_the_rest_are_drawn_unlinked():
    fig, r = lineage_rendered()
    svg = Tree(r.svg)
    for node in svg.find('g', 'node'):
        n = node['attrs']['data-id']
        links = svg.inside(node, 'a')
        if n in PUBLISHED and n != 'swe-bench':
            assert node['attrs']['data-linked'] == 'true' and links[0]['attrs']['href'] == '/benchmarks/%s/' % n
        else:
            assert node['attrs']['data-linked'] == 'false' and not links, n
    assert svg.find('g', 'node')[0]['attrs'].get('data-focal') == 'true'
    t = Tree(r.table)
    hrefs = {a['text']: a['attrs']['href'] for a in t.find('a')}
    assert hrefs == {'swe-bench-verified': '/benchmarks/swe-bench-verified/', 'swe-bench-pro': '/benchmarks/swe-bench-pro/'}
    unlinked = lineage_svg.render(lineage_svg.lineage_figure(swe_bench(), set()))
    assert '<a ' not in unlinked.svg and '<a ' not in unlinked.table
    assert unlinked.summary.endswith('none of them has a page here.')


def test_lineage_reads_left_to_right_derived_before_what_it_derives_from():
    fig, r = lineage_rendered()
    rank, _ = lineage_svg.layout(fig)
    assert rank['swe-bench'] == 0 and rank['Bash Only'] == -2
    assert all(rank[m] == -1 for m in SIX[1:])
    svg = Tree(r.svg)
    x = {n['attrs']['data-id']: float(svg.inside(n, 'rect')[0]['attrs']['x']) for n in svg.find('g', 'node')}
    for row in fig['rows']:
        assert x[row['from']] < x[row['to']], row
    every = lineage_svg.lineage_figure(every_relation(), set())
    rank, _ = lineage_svg.layout(every)
    assert rank['new'] == rank['ext'] == rank['v1'] == rank['z'] == -1 and rank['Easy & <hard>'] == -2
    assert rank['old'] == rank['whole'] == rank['dirty'] == 1


def test_the_lineage_artifact_covers_every_benchmark_with_an_edge(tmp_path):
    corpus = {'artifact': 'corpus', 'entities': {'benchmark': [
        swe_bench(), {'id': 'swe-bench-pro', 'name': 'SWE-Bench Pro', 'lineage': {'role': 'fork'}},
        {'id': 'lonely', 'name': 'Lonely'}]}}
    artifact, figures = lineage_svg.build(corpus)
    assert artifact['artifact'] == 'lineage' and artifact['drafts'] is False
    assert list(artifact['benchmarks']) == ['swe-bench'] and len(figures) == 1
    e = artifact['benchmarks']['swe-bench']
    assert set(e) == {'id', 'caption', 'caption_id', 'summary', 'summary_id', 'svg', 'table', 'relations', 'related'}
    assert (e['relations'], e['related']) == (6, 6)
    assert 'aria-labelledby="%s"' % e['caption_id'] in e['svg'] and 'aria-describedby="%s"' % e['summary_id'] in e['svg']
    assert 'href="/benchmarks/swe-bench-pro/"' in e['svg'] and 'href="/benchmarks/swe-bench-verified/"' not in e['svg']
    src, out, pages = tmp_path / 'corpus.json', tmp_path / 'derived' / 'lineage.json', tmp_path / 'pages'
    src.write_text(json.dumps(corpus), encoding='utf-8')
    assert lineage_svg.main(['--corpus', str(src), '--out', str(out), '--pages', str(pages)]) == 0
    first = out.read_bytes()
    assert json.loads(first)['benchmarks']['swe-bench']['svg'] == e['svg']
    assert sorted(os.listdir(pages)) == ['lineage-swe-bench.html']
    assert lineage_svg.main(['--corpus', str(src), '--out', str(out)]) == 0 and out.read_bytes() == first
    src.write_text(json.dumps({'artifact': 'facets'}), encoding='utf-8')
    assert lineage_svg.main(['--corpus', str(src), '--out', str(out)]) == 2


# ---- the verify's second half --------------------------------------------------------------------------------------

def test_figures_written_for_lint_svg():
    """Every figure above as one page in build/svgcharts/, for `node scripts/lint_svg.mjs build/`."""
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, 'test-figures.html')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(svgcharts.page(all_rendered(), 'P2-S3-T03 test figures'))
    assert open(path, encoding='utf-8').read().count('<svg') == len(all_rendered())
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not on PATH: the verify runs lint_svg itself')
    res = subprocess.run([node, os.path.join(ROOT, 'scripts', 'lint_svg.mjs'), BUILD], capture_output=True, text=True,
                         encoding='utf-8')
    assert res.returncode == 0, res.stdout + res.stderr
    assert ' 0 below 11px; 0 <svg> read at scale 1' in res.stdout
