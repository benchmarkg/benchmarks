"""build/derived/ingest-health.json and the public /sources page (P5-S7-T03; 07 S9.1, 06 S3.0).

The verify: `bench build --derived && pytest tests/site/test_sources_page.py`. Done when "Every source's
health is publicly visible and the published SLO is on the page rather than in a plan document". Two halves:

  - the artifact: one row per adapter the code holds, every field 07 S9.1 and 06 S3.0 name, the status and
    the SLO badge derived by the rules in tools/build/ingest_health.py, and the SLO sentence equal, word for
    word, to 06 S3.0's;
  - the page: Astro builds /sources from the artifact, and the built HTML carries the SLO and a row and a
    freshness strip for every source. The failure case: an artifact without its SLO fails the site build,
    rather than publishing a /sources page without the promise it exists to make.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone

import pytest

from ingest.adapters import epoch, hf_hub
from ingest.http.fixture import FixtureTransport
from ingest.runner import report as R
from ingest.runner import state as S
from tools.build import ingest_health as H

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, 'site')
AS_OF = date(2026, 10, 9)


def _plan_slo():
    """06 S3.0's SLO sentence, as the plan states it (between the asterisks after "published on that page:")."""
    with open(os.path.join(ROOT, '_plan', '06-sourcing-and-scraping.md'), encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'published on that page:\*\* \*(.+?)\*', text, re.S)
    return ' '.join(m.group(1).split())


# ---- the artifact ---------------------------------------------------------------------------------------------

def test_the_slo_published_is_06_s3_0s_word_for_word():
    assert H.SLO == _plan_slo()


def test_every_adapter_the_code_holds_has_a_row_with_every_field():
    doc = H.build(ROOT, AS_OF)
    assert doc['artifact'] == 'ingest-health' and doc['slo'] == H.SLO and doc['as_of'] == '2026-10-09'
    assert [r['adapter'] for r in doc['sources']] == sorted(c.name for c in H.adapters()) == ['arxiv-oai', 'epoch', 'github', 'hf-hub', 'lm-eval-harness', 'mteb-results', 'swe-bench']
    for r in doc['sources']:
        for key in ('licence', 'licence_class', 'attribution', 'last_successful_fetch', 'last_content_change',
                    'record_count', 'adapter_status', 'badge'):
            assert key in r, (r['adapter'], key)
        assert r['adapter_status'] in H.STATUSES


def test_licence_comes_from_the_source_record_where_one_exists():
    rows = {r['adapter']: r for r in H.build(ROOT, AS_OF)['sources']}
    assert rows['epoch']['licence'] == 'CC-BY-4.0' and rows['epoch']['licence_checked_on'] == '2026-09-28'
    assert rows['epoch']['licence_basis'] == 'source record src-epoch-benchmark-data'
    assert rows['hf-hub']['licence_basis'] == 'adapter declaration' and rows['hf-hub']['licence_class'] == 'unlicensed'


def test_records_count_what_cites_the_source_and_nothing_cited_only_in_a_comment(tmp_path):
    (tmp_path / 'data' / 'benchmarks' / '_stubs').mkdir(parents=True)
    (tmp_path / 'data' / 'benchmarks' / '_stubs' / 'a.yaml').write_text('sources:\n  - src-epoch-benchmark-data\n')
    (tmp_path / 'data' / 'benchmarks' / '_stubs' / 'b.yaml').write_text('# from src-epoch-benchmark-data\nid: b\n')
    (tmp_path / 'data' / '_discovery' / 'hf-hub').mkdir(parents=True)
    (tmp_path / 'data' / '_discovery' / 'hf-hub' / 'c.yaml').write_text('candidate_id: c\n')
    assert H.record_count(str(tmp_path), 'epoch', 'src-epoch-benchmark-data') == 1
    assert H.record_count(str(tmp_path), 'hf-hub', None) == 1


def test_data_fetched_by_hand_shows_the_source_records_fetch_and_says_so():
    epoch_row = next(r for r in H.build(ROOT, AS_OF)['sources'] if r['adapter'] == 'epoch')
    assert epoch_row['adapter_status'] == 'not-yet-run'                        # no scheduled run is logged
    assert epoch_row['last_successful_fetch'] == '2026-09-28T23:59:00Z'
    assert epoch_row['fetch_basis'] == 'source record (a by-hand fetch)'


# ---- status and the SLO badge, on a tree with state files and run logs ------------------------------------------

def tree(tmp_path, adapter='hf-hub', state=None, runs=()):
    if state is not None:
        st = S.new(adapter, '0.1.0', **state)
        S.save(str(tmp_path / 'ingest' / 'state' / ('%s.json' % adapter)), st)
    for status, finished, notes in runs:
        R.write(R.build(adapter=adapter, adapter_version='0.1.0', started_at=finished, finished_at=finished,
                        status=status, http_codes={}, candidates_seen=0, payloads_fetched=0, payloads_from_cache=0,
                        drafts={}, unresolved_new=0, unresolved_carried=0, resolver_snapshot_sha256='0' * 64,
                        notes=notes), str(tmp_path))
    return {r['adapter']: r for r in H.build(str(tmp_path), AS_OF)['sources']}


def at(day):
    return datetime(2026, 10, day, 6, 0, tzinfo=timezone.utc)


def test_an_adapter_that_never_ran_is_never_shown_as_ok(tmp_path):
    row = tree(tmp_path)['hf-hub']
    assert row['adapter_status'] == 'not-yet-run' and row['last_successful_fetch'] is None and row['badge'] is None


def test_a_working_run_is_ok(tmp_path):
    row = tree(tmp_path, state={'last_success': '2026-10-08T06:00:00Z', 'last_change': '2026-10-07T06:00:00Z'},
               runs=[('no-change', at(8), [])])['hf-hub']
    assert row['adapter_status'] == 'ok' and row['days_since_success'] == 1
    assert row['last_content_change'] == '2026-10-07T06:00:00Z' and row['fetch_basis'] == 'state file'


@pytest.mark.parametrize('status, notes', [('soft-fail', []), ('ok', ['ZERO YIELD: 0 candidates ...'])])
def test_a_soft_fail_or_a_zero_yield_run_is_degraded(tmp_path, status, notes):
    row = tree(tmp_path, state={'last_success': '2026-10-08T06:00:00Z'}, runs=[(status, at(8), notes)])['hf-hub']
    assert row['adapter_status'] == 'degraded' and row['badge'] is None


def test_a_broken_tier_1_adapter_badges_its_records_stale_after_two_weeks_not_before(tmp_path):
    fresh = tree(tmp_path / 'a', state={'last_success': '2026-09-26T06:00:00Z'}, runs=[('hard-fail', at(8), [])])['hf-hub']
    assert fresh['adapter_status'] == 'broken' and fresh['days_since_success'] == 13 and fresh['badge'] is None
    late = tree(tmp_path / 'b', state={'last_success': '2026-09-24T06:00:00Z'}, runs=[('hard-fail', at(8), [])])['hf-hub']
    assert late['days_since_success'] == 15 and late['badge'] == 'stale'


def test_a_broken_tier_2_adapter_is_badged_at_30_days(tmp_path, monkeypatch):
    monkeypatch.setattr(hf_hub.HfHub, 'tier', 2)
    row = tree(tmp_path / 'a', state={'last_success': '2026-09-24T06:00:00Z'}, runs=[('hard-fail', at(8), [])])['hf-hub']
    assert row['badge'] is None                                          # 15 days: inside Tier 2's 30
    row = tree(tmp_path / 'b', state={'last_success': '2026-09-01T06:00:00Z'}, runs=[('hard-fail', at(8), [])])['hf-hub']
    assert row['badge'] == 'stale'


def test_a_retired_adapter_carries_the_permanent_badge(tmp_path, monkeypatch):
    monkeypatch.setattr(hf_hub.HfHub, 'retired', True)
    row = tree(tmp_path, state={'last_success': '2026-10-08T06:00:00Z'}, runs=[('ok', at(8), [])])['hf-hub']
    assert row['adapter_status'] == 'retired' and row['badge'] == 'source-retired'


def test_the_runner_records_the_credit_line_the_build_publishes(tmp_path):
    """07 S9.1: the build reads attribution from ingest/state/. Epoch's is its bundle README's citation, so the
    run that fetched the bundle records it, and a 304 run after it keeps it."""
    path = str(tmp_path / 'ingest' / 'state' / 'epoch.json')
    fix = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
    for _ in range(2):
        st = S.load(path, S.new(epoch.NAME, epoch.VERSION, etags={}))
        S.run(epoch.Epoch(FixtureTransport(fix)), st, path, now=lambda: at(8))
    with open(path, encoding='utf-8') as f:
        saved = json.load(f)
    with open(os.path.join(fix, 'benchmark_data.zip'), 'rb') as f:
        credit = epoch.attribution(epoch.ZipBundle(f.read()))
    assert saved['attribution'] == credit and saved['licence_class'] == 'permissive-attribution'
    row = {r['adapter']: r for r in H.build(str(tmp_path), AS_OF)['sources']}['epoch']
    assert row['attribution'] == credit and row['adapter_status'] == 'ok'


def test_the_artifact_is_a_function_of_the_tree():
    assert H.serialise(H.build(ROOT, AS_OF)) == H.serialise(H.build(ROOT, AS_OF))
    assert H.build(ROOT)['as_of'] == H.commit_date(ROOT).isoformat()     # no clock: the data commit's date


def test_bench_build_derived_writes_it(tmp_path):
    from typer.testing import CliRunner

    from tools import cli
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path), '--derived'])
    assert r.exit_code == 0, r.output
    with open(tmp_path / 'derived' / 'ingest-health.json', encoding='utf-8') as f:
        assert json.load(f)['slo'] == H.SLO


# ---- the page, built --------------------------------------------------------------------------------------------

def _npx():
    return shutil.which('npx') or shutil.which('npx.cmd')


needs_site = pytest.mark.skipif(not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and _npx()),
                                reason='site/node_modules is not installed')


def astro_build(health_path, out):
    env = dict(os.environ, INGEST_HEALTH=str(health_path), BENCH_PYTHON=sys.executable, REPO_ROOT=ROOT)
    return subprocess.run([_npx(), 'astro', 'build', '--outDir', str(out)], cwd=SITE, env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=900)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    """The site, built over an artifact with one broken, stale adapter and one working one."""
    base = tmp_path_factory.mktemp('health')
    tree(base, state={'last_success': '2026-09-20T06:00:00Z'}, runs=[('hard-fail', at(8), [])])
    tree(base, adapter='epoch', state={'last_success': '2026-10-08T06:00:00Z', 'attribution': 'Epoch AI, credit'},
         runs=[('no-change', at(8), [])])
    artifact = base / 'ingest-health.json'
    artifact.write_bytes(H.serialise(H.build(str(base), AS_OF)))
    out = tmp_path_factory.mktemp('dist')
    r = astro_build(artifact, out)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    with open(os.path.join(out, 'sources', 'index.html'), encoding='utf-8') as f:
        return f.read()


def _text(html):
    return ' '.join(re.sub(r'<[^>]+>', ' ', html).replace('&#39;', "'").replace('&quot;', '"').split())


@needs_site
def test_the_page_publishes_the_slo(built):
    m = re.search(r'<p[^>]*data-test="slo"[^>]*>(.*?)</p>', built, re.S)
    assert m and _text(m.group(1)) == H.SLO[0].upper() + H.SLO[1:]


@needs_site
def test_the_page_has_a_row_and_a_freshness_strip_for_every_source(built):
    for name in ('epoch', 'hf-hub'):
        assert re.search(r'<tr[^>]*data-adapter="%s"' % name, built), name
        assert re.search(r'<p[^>]*data-adapter="%s"' % name, built), name
    assert re.search(r'<tr[^>]*data-adapter="hf-hub"[^>]*data-status="broken"', built)
    assert re.search(r'<tr[^>]*data-adapter="epoch"[^>]*data-status="ok"', built)
    assert 'Epoch AI, credit' in built and 'CC-BY-4.0' in built


@needs_site
def test_a_stale_source_shows_its_badge_on_the_page(built):
    strip = re.search(r'<p[^>]*data-adapter="hf-hub".*?</p>', built, re.S).group(0)
    assert 'data-badge="stale"' in strip and 'badged stale' in _text(strip)
    assert '2026-09-20' in strip and '(19 days)' in _text(strip)


@needs_site
def test_the_failure_case_an_artifact_without_its_slo_fails_the_build(tmp_path):
    doc = H.build(ROOT, AS_OF)
    doc['slo'] = ''
    bad = tmp_path / 'ingest-health.json'
    bad.write_text(json.dumps(doc), encoding='utf-8')
    r = astro_build(bad, tmp_path / 'dist')
    assert r.returncode != 0 and 'not the artifact tools/build/ingest_health.py writes' in (r.stdout + r.stderr)
