"""Tests for scripts/check_single_source.py and the components it checks (P4-S5-T06; 12 S6, 06 S3.10).

Two halves. The rules, on hand-written HTML. Then the components themselves: site/test/fixtures/citations.astro
renders CitationCount.astro over the citation cross-check's own output (P4-S2-T10's recorded figures), Astro
builds it into a temporary directory, and the check reads the result -- so what passes is the real markup, and
deleting the markers from it is what fails. The build half needs site/node_modules and is skipped without it.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_single_source as css  # noqa: E402

SITE = os.path.join(ROOT, 'site')
MARKER = '<span data-marker="unverified">◇ unverified, single source</span>'


def fig(arxiv='1', single='true', disagree='false', source='semantic_scholar', aggs='semantic_scholar', inner=MARKER,
        **extra):
    attrs = {'data-citation-figure': arxiv, 'data-single-source': single, 'data-disagreement': disagree,
             'data-value-source': source, 'data-aggregators': aggs, **extra}
    return '<span %s><span>4,090</span> citations %s</span>' % (
        ' '.join('%s="%s"' % kv for kv in attrs.items() if kv[1] is not None), inner)


def findings(html):
    return css.check_html('<html><body>%s</body></html>' % html, 'page.html')[0]


def kinds(html):
    return [f.split()[0] for f in findings(html)]


# ---- the rules ------------------------------------------------------------------------------------------

def test_a_marked_single_source_figure_and_an_agreeing_unmarked_one_pass():
    html = fig() + fig('2', 'false', 'false', aggs='semantic_scholar openalex', inner='')
    assert findings(html) == [] and css.check_html(html)[1] == 2


@pytest.mark.parametrize('single, disagree, aggs', [
    ('true', 'false', 'semantic_scholar'),
    ('true', 'false', 'openalex'),
    ('false', 'true', 'semantic_scholar openalex'),
])
def test_an_unverified_figure_without_the_marker_fails(single, disagree, aggs):
    assert kinds(fig(single=single, disagree=disagree, aggs=aggs, inner='')) == ['unmarked']


def test_a_marker_that_does_not_say_unverified_fails():
    assert kinds(fig(inner='<span data-marker="unverified">◇</span>')) == ['unmarked']


def test_a_marker_beside_the_figure_rather_than_inside_it_does_not_count():
    assert kinds(fig(inner='') + MARKER) == ['unmarked']


@pytest.mark.parametrize('single, aggs', [('false', 'semantic_scholar'), ('true', 'semantic_scholar openalex')])
def test_a_single_source_flag_that_does_not_follow_from_the_aggregators_fails(single, aggs):
    assert 'flag' in kinds(fig(single=single, aggs=aggs))


@pytest.mark.parametrize('drop', css.REQUIRED)
def test_a_figure_missing_a_provenance_attribute_fails(drop):
    html = fig(**{drop: None})
    assert kinds(html) == ['attributes'] and drop in findings(html)[0]


@pytest.mark.parametrize('bad', [{'data-aggregators': 'google_scholar'}, {'data-aggregators': ''},
                                 {'data-single-source': 'yes'}])
def test_unreadable_provenance_fails(bad):
    assert kinds(fig(**bad)) == ['attributes']


@pytest.mark.parametrize('wrap', ['<h1>%s</h1>', '<h3>Most cited %s</h3>', '<div data-headline="true"><p>%s</p></div>'])
def test_an_openalex_count_in_a_headline_fails(wrap):
    html = wrap % fig(source='openalex', aggs='openalex')
    assert kinds(html) == ['headline']


def test_a_semantic_scholar_count_in_a_headline_and_an_openalex_one_in_the_body_pass():
    assert findings('<h1>%s</h1><p>%s</p>' % (fig(), fig('2', source='openalex', aggs='openalex'))) == []


@pytest.mark.parametrize('text', ['<p>SWE-bench has 4,090 citations.</p>', '<td>Cited by 56</td>',
                                  '<li>1.2k citations</li>', '<h2>12,000+ citations</h2>', '<p>cited 9 times</p>'])
def test_a_bare_citation_count_outside_a_figure_fails(text):
    assert 'bare-count' in kinds(text)


@pytest.mark.parametrize('text', ['<p>counts more than 2x apart</p>', '<p>3 sources</p>',
                                  '<script>var s = "40 citations";</script>', '<style>/* 5 citations */</style>',
                                  '<p>citations are ingested, never estimated</p>'])
def test_text_that_is_not_a_citation_count_passes(text):
    assert findings(text) == []


def test_main_exits_2_with_no_built_site(tmp_path):
    assert css.main(['--dist', str(tmp_path / 'absent')]) == 2
    assert css.main(['--dist', str(tmp_path)]) == 2                 # a directory with no pages is not a site


def test_main_exits_1_on_a_finding_and_names_the_page(tmp_path, capsys):
    (tmp_path / 'deep').mkdir()
    (tmp_path / 'deep' / 'p.html').write_text('<p>Cited by 7</p>', encoding='utf-8')
    assert css.main(['--dist', str(tmp_path)]) == 1
    assert 'deep/p.html' in capsys.readouterr().out


# ---- the components, built ------------------------------------------------------------------------------

def _npx():
    return shutil.which('npx') or shutil.which('npx.cmd')


needs_site = pytest.mark.skipif(not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and _npx()),
                                reason='site/node_modules is not installed')


def build(fixture, out):
    env = dict(os.environ, UAIBI_SITE_FIXTURES=fixture, BENCH_PYTHON=sys.executable)
    return subprocess.run([_npx(), 'astro', 'build', '--outDir', str(out)], cwd=SITE, env=env,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp('dist')
    r = build('citations', out)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    with open(os.path.join(out, '_fixtures', 'citations', 'index.html'), encoding='utf-8') as fh:
        return str(out), fh.read()


@needs_site
def test_the_built_components_pass_the_check(built):
    out, page = built
    found, pages, figures = css.check_dist(out)
    assert found == [] and figures == 9 and pages >= 2
    assert page.count('data-marker="unverified"') == 8               # every figure but the agreeing one
    # three single-source and three disagreeing recorded figures, the headline T5 (disagreeing) and OpenAlex-only
    assert page.count('data-reason="single-source"') == 4 and page.count('data-reason="disagreement"') == 4


@needs_site
def test_the_recorded_regression_case_renders_single_source_with_its_aggregator_named(built):
    page = built[1]
    swe = re.search(r'<span[^>]*data-citation-figure="2310\.06770".*?</span></span></span>', page).group(0)
    assert 'data-single-source="true"' in swe and '4,090' in swe and 'Only Semantic Scholar supports' in swe


@needs_site
def test_the_built_page_without_its_markers_fails(built):
    stripped = re.sub(r'<span[^>]*data-marker="unverified".*?</span></span>', '', built[1])
    assert stripped != built[1]
    found, _ = css.check_html(stripped)
    assert len(found) == 8 and all(f.startswith('unmarked') for f in found)


@needs_site
def test_an_openalex_headline_fails_the_build(tmp_path):
    r = build('citations-openalex-headline', tmp_path / 'dist')
    assert r.returncode != 0 and 'cannot be a headline number' in r.stdout + r.stderr


# ---- wired into pr-validate.yml -------------------------------------------------------------------------

def test_pr_validate_builds_the_site_and_runs_the_check_blocking():
    from ruamel.yaml import YAML
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        wf = YAML(typ='safe').load(fh)
    job = wf['jobs']['single-source']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s.get('run', '') for s in job['steps']]                  # get-default: a uses: step has no run
    assert all('continue-on-error' not in s and 'if' not in s for s in job['steps'])
    assert not any(re.search(r'\|\|\s*(true|:|exit 0)', r) for r in runs)
    build_at = runs.index('npx astro build')
    assert runs[-1] == 'uv run --locked --python "$PYTHON" python scripts/check_single_source.py' and build_at < len(runs) - 1
    assert job['steps'][0]['with']['fetch-depth'] == 0                # tools/build/feed.py walks the history
