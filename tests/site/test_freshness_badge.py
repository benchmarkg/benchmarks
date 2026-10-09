"""The per-entry freshness badge and its tokens (P5-S7-T04; 05 S7, 06 S3.0, 09 S4).

The verify: `pytest tests/site/test_freshness_badge.py && python scripts/check_contrast.py`. Done when "An entry
last verified 400 days ago visibly says so and sorts lower, with contrast passing in both themes". Three halves:

  - the build (tools/build/freshness.py): 05 S7's 180/365/730-day thresholds on curation.last_verified, read
    against the plan's own table; the red state demoted in the default order; the critical flag on an active
    entry; 06 S3.0's source_freshness on an entry whose live source has not refreshed in more than 90 days;
  - the tokens: the three badge states in design/tokens.yaml, every pair passing its floor in both themes, and a
    fixture amber below the floor failing check_contrast;
  - the page: Astro builds /freshness from the artifact, the 400-day entry says so in a red badge and sorts below
    the fresher ones. The failure case: an artifact whose default order drops an entry fails the site build, so
    no entry can be published without its badge.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

import pytest
import yaml

from tools.build import freshness as F
from tools.build import ingest_health as H
from tools.build import tokens as T

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_contrast as C  # noqa: E402

SITE = os.path.join(ROOT, 'site')
AS_OF = date(2026, 10, 9)
EPOCH = 'src-epoch-benchmark-data'


# ---- the thresholds are the plan's ------------------------------------------------------------------------------

def _plan(name):
    with open(os.path.join(ROOT, '_plan', name), encoding='utf-8') as f:
        return f.read()


def test_the_thresholds_are_05_s7s_table_and_06_s3_0s_window():
    s7 = _plan('05-repository-and-workflow.md').split('## 7. Freshness', 1)[1].split('\n## ', 1)[0]
    assert '| < %d days | Neutral text |' % F.AMBER_FROM in s7
    assert '| %d--%d days | Amber badge |' % (F.AMBER_FROM, F.RED_AFTER) in s7
    assert '| > %d days | Red badge, "not verified in over a year", demoted below fresher entries in default sort |' \
        % F.RED_AFTER in s7
    assert '| > %d days on an `active` benchmark |' % F.CRITICAL_AFTER in s7
    assert 'has not refreshed in more than %d days' % F.SOURCE_REFRESH_DAYS in ' '.join(
        _plan('06-sourcing-and-scraping.md').split())


@pytest.mark.parametrize('days,state', [(0, 'neutral'), (179, 'neutral'), (180, 'amber'), (365, 'amber'),
                                        (366, 'red'), (400, 'red'), (None, 'red')])
def test_each_age_gets_05_s7s_treatment(days, state):
    assert F.state(days) == state


# ---- the artifact, on a fixture tree ----------------------------------------------------------------------------

def record(root, path, name, last_verified, sources=('src-paper',), lifecycle='active', curation=True):
    full = root / 'data' / path
    full.parent.mkdir(parents=True, exist_ok=True)
    doc = {'id': full.stem, 'name': name, 'lifecycle': lifecycle}
    if curation:
        doc['curation'] = {'added_by': 'test', 'added_on': '2024-01-01', 'last_verified': last_verified,
                           'verification_status': 'ai-drafted-unverified', 'sources': list(sources)}
    full.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')


def health(days=None, badge=None, status='ok'):
    """An ingest-health artifact whose epoch adapter last fetched `days` before AS_OF (None: never)."""
    fetched = None if days is None else (date.fromordinal(AS_OF.toordinal() - days).isoformat() + 'T06:00:00Z')
    return {'sources': [{'adapter': 'epoch', 'last_successful_fetch': fetched, 'fetch_basis': 'state file',
                         'days_since_success': days, 'adapter_status': status, 'badge': badge},
                        {'adapter': 'hf-hub', 'last_successful_fetch': None, 'fetch_basis': None,
                         'days_since_success': None, 'adapter_status': 'not-yet-run', 'badge': None}]}


def ago(days):
    return date.fromordinal(AS_OF.toordinal() - days).isoformat()


@pytest.fixture()
def corpus(tmp_path):
    record(tmp_path, 'benchmarks/code/aardvark.yaml', 'Aardvark', ago(400))           # first by name, and stale
    record(tmp_path, 'benchmarks/code/middle.yaml', 'Middle', ago(250))
    record(tmp_path, 'benchmarks/code/zebra.yaml', 'Zebra', ago(12))
    record(tmp_path, 'benchmarks/_stubs/stub.yaml', 'Stub', None)                      # never published
    record(tmp_path, 'systems/sys.yaml', 'Sys', None, curation=False)                  # no curation block
    return tmp_path


def by_id(doc):
    return {e['id']: e for e in doc['entries']}


def test_an_entry_last_verified_400_days_ago_is_red_and_sorts_below_every_fresher_one(corpus):
    doc = F.build(str(corpus), AS_OF, health())
    e = by_id(doc)
    assert e['aardvark']['state'] == 'red' and e['aardvark']['days_since_verified'] == 400
    assert e['aardvark']['demoted'] and e['aardvark']['last_verified'] == ago(400)
    assert e['middle']['state'] == 'amber' and not e['middle']['demoted']
    assert e['zebra']['state'] == 'neutral' and not e['zebra']['demoted']
    assert doc['order'] == ['middle', 'zebra', 'aardvark']        # by name, the red one below both


def test_only_published_curated_records_are_entries(corpus):
    assert sorted(by_id(F.build(str(corpus), AS_OF, health()))) == ['aardvark', 'middle', 'zebra']


def test_an_entry_never_verified_is_red(corpus):
    record(corpus, 'benchmarks/code/never.yaml', 'Never', None)
    e = by_id(F.build(str(corpus), AS_OF, health()))['never']
    assert e['state'] == 'red' and e['demoted'] and e['days_since_verified'] is None


def test_past_730_days_an_active_entry_is_critical_and_nothing_else_is(corpus):
    record(corpus, 'benchmarks/code/old.yaml', 'Old', ago(731))
    record(corpus, 'benchmarks/code/edge.yaml', 'Edge', ago(730))
    record(corpus, 'benchmarks/code/retired.yaml', 'Retired', ago(900), lifecycle='deprecated')
    e = by_id(F.build(str(corpus), AS_OF, health()))
    assert e['old']['critical'] and not e['edge']['critical'] and not e['retired']['critical']
    assert not e['aardvark']['critical']


@pytest.mark.parametrize('days,badged', [(12, False), (90, False), (91, True), (None, True)])
def test_an_entry_whose_sole_live_source_has_not_refreshed_in_over_90_days_is_badged(corpus, days, badged):
    record(corpus, 'benchmarks/code/live.yaml', 'Live', ago(12), sources=('src-paper', EPOCH))
    sf = by_id(F.build(str(corpus), AS_OF, health(days)))['live']['source_freshness']
    assert sf['badged'] is badged
    assert [s['source'] for s in sf['sources']] == [EPOCH] and sf['sources'][0]['days_since_refresh'] == days


def test_an_entry_on_no_live_source_carries_no_source_freshness(corpus):
    assert by_id(F.build(str(corpus), AS_OF, health(400)))['zebra']['source_freshness'] is None


def test_a_broken_sources_slo_badge_reaches_every_entry_resting_on_it(corpus):
    record(corpus, 'benchmarks/code/live.yaml', 'Live', ago(12), sources=(EPOCH,))
    sf = by_id(F.build(str(corpus), AS_OF, health(20, badge='stale', status='broken')))['live']['source_freshness']
    assert sf['slo_badges'] == ['stale'] and not sf['badged']                # 20 days: fresh, but its SLO says stale


# ---- the artifact, on the repository ----------------------------------------------------------------------------

@pytest.fixture(scope='module')
def real():
    return F.build(ROOT, AS_OF)


def test_every_published_entry_is_badged_and_in_the_order_once(real):
    published = [rel for rel, _ in F.entries(ROOT)]
    assert len(real['entries']) == len(published) > 0
    assert sorted(real['order']) == sorted(e['id'] for e in real['entries'])
    assert all(e['state'] in F.STATES for e in real['entries'])
    assert not any('/_' in e['path'] for e in real['entries'])


def test_an_entry_citing_epoch_carries_epochs_freshness(real):
    sf = by_id(real)['scicode']['source_freshness']
    assert [s['source'] for s in sf['sources']] == [EPOCH]
    assert sf['sources'][0]['last_successful_fetch'] == '2026-09-28T23:59:00Z' and not sf['badged']


def test_the_artifact_is_a_function_of_the_tree(real):
    assert F.serialise(real) == F.serialise(F.build(ROOT, AS_OF))
    assert F.build(ROOT)['as_of'] == H.commit_date(ROOT).isoformat()      # no clock: the data commit's date


def test_bench_build_derived_writes_it(tmp_path):
    from typer.testing import CliRunner

    from tools import cli
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path), '--derived'])
    assert r.exit_code == 0, r.output
    with open(tmp_path / 'derived' / 'freshness.json', encoding='utf-8') as f:
        assert json.load(f)['thresholds']['red_after_days'] == F.RED_AFTER


def test_no_threshold_literal_appears_in_the_site_code():
    for rel in ('src/components/FreshnessBadge.astro', 'src/lib/freshness.ts', 'src/pages/freshness.astro'):
        with open(os.path.join(SITE, rel), encoding='utf-8') as f:
            code = re.sub(r'^\s*//.*$', '', f.read(), flags=re.M)              # the comments cite 05 S7's table
        for n in (F.AMBER_FROM, F.RED_AFTER, F.CRITICAL_AFTER, F.SOURCE_REFRESH_DAYS):
            assert not re.search(r'(?<![\w.-])%d(?![\w.])' % n, code), (rel, n)


# ---- the tokens -------------------------------------------------------------------------------------------------

FRESHNESS_TOKENS = {'c-freshness-neutral', 'c-freshness-amber', 'c-freshness-amber-bg', 'c-freshness-red',
                    'c-freshness-red-bg'}


def _tokens():
    return T.load_yaml(os.path.join(ROOT, T.TOKENS))


def test_the_three_badge_states_have_tokens_in_both_themes():
    group = next(g for g in T.resolve(_tokens(), ROOT) if g['id'] == 'freshness')
    assert {r['id'] for r in group['rows']} == FRESHNESS_TOKENS
    with open(os.path.join(ROOT, T.CSS_OUT), encoding='utf-8') as f:
        css = f.read()
    for tid in FRESHNESS_TOKENS:
        assert css.count('--%s:' % tid) == 3, tid                  # light, the OS-dark block, data-theme="dark"


def test_every_badge_pair_passes_its_floor_in_both_themes():
    results, failures = C.check(_tokens(), ROOT)
    badge = [r for r in results if r.fg.startswith('c-freshness-')]
    assert {r.theme for r in badge} == {'light', 'dark'} and len(badge) == 16
    assert all(r.passes and r.waiver is None for r in badge), [(r.fg, r.on, r.theme, r.ratio) for r in badge]
    assert failures == []


def test_the_failure_case_an_amber_below_the_floor_fails_check_contrast(tmp_path, capsys):
    doc = _tokens()
    group = next(g for g in doc['groups'] if g['id'] == 'freshness')
    group['tokens']['c-freshness-amber']['light'] = '70% 0.09 70'          # 43% -> 70%: about 2.5:1 on its tint
    from ruamel.yaml import YAML
    path = tmp_path / 'tokens.yaml'
    with open(path, 'w', encoding='utf-8') as f:
        YAML(typ='safe', pure=True).dump(doc, f)
    assert C.main(['--tokens', str(path), '--root', ROOT]) == 1
    assert 'FAIL light c-freshness-amber on c-freshness-amber-bg' in capsys.readouterr().err


# ---- the page, built --------------------------------------------------------------------------------------------

def _npx():
    return shutil.which('npx') or shutil.which('npx.cmd')


needs_site = pytest.mark.skipif(not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and _npx()),
                                reason='site/node_modules is not installed')


def astro_build(artifact, out):
    env = dict(os.environ, FRESHNESS=str(artifact), BENCH_PYTHON=sys.executable, REPO_ROOT=ROOT)
    return subprocess.run([_npx(), 'astro', 'build', '--outDir', str(out)], cwd=SITE, env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=900)


def _fixture(tmp_path_factory):
    base = tmp_path_factory.mktemp('fresh')
    record(base, 'benchmarks/code/aardvark.yaml', 'Aardvark', ago(400))
    record(base, 'benchmarks/code/middle.yaml', 'Middle', ago(250))
    record(base, 'benchmarks/code/zebra.yaml', 'Zebra', ago(12), sources=(EPOCH,))
    return F.build(str(base), AS_OF, health(120))


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    artifact = tmp_path_factory.mktemp('artifact') / 'freshness.json'
    artifact.write_bytes(F.serialise(_fixture(tmp_path_factory)))
    out = tmp_path_factory.mktemp('dist')
    r = astro_build(artifact, out)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    with open(os.path.join(out, 'freshness', 'index.html'), encoding='utf-8') as f:
        return f.read()


def _text(html):
    return ' '.join(re.sub(r'<[^>]+>', ' ', html).replace('&#39;', "'").replace('&quot;', '"').split())


def _item(html, entry):
    return re.search(r'<li[^>]*data-entry="%s".*?</li>' % entry, html, re.S).group(0)


@needs_site
def test_the_400_day_entry_visibly_says_so_on_the_page(built):
    item = _item(built, 'aardvark')
    assert 'data-test="badge-red"' in item and 'data-state="red"' in item
    assert 'Not verified in over a year: last verified %s (400 days)' % ago(400) in _text(item)
    assert re.search(r'<time datetime="%s"[^>]*>%s</time>' % (ago(400), ago(400)), item)


@needs_site
def test_and_sorts_below_the_fresher_entries(built):
    assert re.findall(r'<li[^>]*data-entry="([^"]+)"', built) == ['middle', 'zebra', 'aardvark']


@needs_site
def test_the_amber_and_neutral_states_and_the_stale_live_source_render(built):
    assert 'data-test="badge-amber"' in _item(built, 'middle')
    zebra = _item(built, 'zebra')
    assert 'data-test="badge' not in zebra.replace('data-test="badge-source"', '')    # neutral: no badge of its own
    assert 'Source data not refreshed in over 90 days: %s last fetched %s (120 days)' % (EPOCH, ago(120)) \
        in _text(zebra)
    assert 'within 180 days, 1 amber, 1 red' in _text(built)


@needs_site
def test_the_failure_case_an_artifact_that_drops_an_entry_from_its_order_fails_the_build(tmp_path_factory):
    doc = _fixture(tmp_path_factory)
    doc['order'].remove('aardvark')                                    # the stale entry, quietly left off the list
    bad = tmp_path_factory.mktemp('bad') / 'freshness.json'
    bad.write_text(json.dumps(doc), encoding='utf-8')
    r = astro_build(bad, tmp_path_factory.mktemp('dist-bad'))
    assert r.returncode != 0 and 'does not list every entry exactly once' in (r.stdout + r.stderr)
