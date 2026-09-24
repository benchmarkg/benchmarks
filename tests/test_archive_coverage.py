"""Tests for scripts/check_archive_coverage.py and the rolling archiver, ingest/archive_sources.py.

The archiver is driven against a fake Wayback, so no test touches the network; each fixture Source
is a small file in tmp_path shaped like the P0-S3-T04 records.
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cov = _load('check_archive_coverage', 'scripts/check_archive_coverage.py')
arch = _load('archive_sources', 'ingest/archive_sources.py')

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
SLA = timedelta(days=7)

RECORD = """\
# data/sources/2026/{id}.yaml -- test fixture
id: {id}
type: leaderboard-page
url: {url}
doi: {doi}
fetched_at: '{fetched}'
archive_url: null
archive_captured: null
archive_status: {status}
archive_digest: null
archive_requested_at: {requested}
failure_reason: {reason}
quote_extract: |-
  a line that must survive the rewrite
notes: null
"""


def write(root, id, url='https://example.org/{id}', doi='null', fetched='2026-09-28T00:00:00Z',
          status='pending', requested='null', reason='null'):
    d = root / 'data' / 'sources' / '2026'
    d.mkdir(parents=True, exist_ok=True)
    (d / (id + '.yaml')).write_text(RECORD.format(
        id=id, url=url.format(id=id), doi=doi, fetched=fetched, status=status,
        requested=requested, reason=reason), encoding='utf-8')
    return d / (id + '.yaml')


def rec(**kw):
    base = {'id': 'x', 'doi': None, 'archive_url': None, 'archive_status': 'pending',
            'archive_requested_at': None, 'failure_reason': None, 'quote_extract': 'q',
            'fetched_at': '2026-09-28T00:00:00Z'}
    base.update(kw)
    return base


# ---- the SLA check -----------------------------------------------------------------------------

@pytest.mark.parametrize('r, want', [
    (rec(doi='10.1/x'), 'doi-exempt'),
    (rec(archive_url='https://web.archive.org/web/1/x', archive_status='ok'), 'ok'),
    (rec(archive_url='https://web.archive.org/web/1/x', archive_status='pending'), 'VIOLATION'),
    (rec(archive_status='failed', failure_reason='error:blocked-url'), 'failed'),
    (rec(archive_status='failed'), 'VIOLATION'),
    (rec(archive_requested_at='2026-09-25T00:00:00Z'), 'pending'),
    (rec(archive_requested_at='2026-09-20T00:00:00Z'), 'VIOLATION'),  # pending past the SLA
    (rec(archive_status='not-required', quote_extract=None), 'not-required'),
    (rec(archive_status='not-required'), 'VIOLATION'),  # quoted from, so it must be archived
    (rec(), 'new'),  # fetched three days ago, never tried
    (rec(fetched_at='2026-09-01T00:00:00Z'), 'VIOLATION'),
    (rec(fetched_at=None), 'VIOLATION'),
    (rec(archive_status='withheld', failure_reason='personal data'), 'WARNING'),
    (rec(archive_status='withheld'), 'VIOLATION'),
])
def test_classify(r, want):
    assert cov.classify(r, NOW, SLA)[0] == want


def test_strict_turns_an_unknown_status_into_a_violation():
    assert cov.classify(rec(archive_status='withheld', failure_reason='pd'), NOW, SLA, strict=True)[0] == 'VIOLATION'


def test_a_refetch_does_not_reset_the_clock():
    # fetched_at moves on every re-fetch; accessed records the first human read.
    r = rec(fetched_at='2026-09-30T00:00:00Z', accessed='2026-09-01')
    assert cov.classify(r, NOW, SLA)[0] == 'VIOLATION'


def test_cli_exit_codes(tmp_path, capsys):
    write(tmp_path, 'src-young')
    assert cov.main(['--root', str(tmp_path), '--now', '2026-10-01T12:00:00Z']) == 0
    write(tmp_path, 'src-old', fetched='2026-09-01T00:00:00Z')
    assert cov.main(['--root', str(tmp_path), '--now', '2026-10-01T12:00:00Z']) == 1
    assert 'VIOLATION src-old' in capsys.readouterr().out


# ---- the rolling archiver ----------------------------------------------------------------------

class FakeWayback:
    """cdx: url -> timestamp; results: url -> list of outcomes returned by successive polls."""

    def __init__(self, can_capture=True, cdx=None, submit=None, results=None):
        self.can_capture = can_capture
        self.cdx = cdx or {}
        self.submit_result = submit or {}
        self.results = results or {}
        self.submitted, self.looked_up = [], []

    def latest(self, url):
        self.looked_up.append(url)
        ts = self.cdx.get(url)
        return (ts, url, 'DIGEST') if ts else None

    def submit(self, url):
        if url in self.submit_result:
            r = self.submit_result[url]
            if isinstance(r, Exception):
                raise r
            return r
        self.submitted.append(url)
        return 'job-' + url

    def poll(self, job_id):
        url = job_id[4:]
        seq = self.results.get(url, [('success', '20261001120000', url)])
        return seq.pop(0) if len(seq) > 1 else seq[0]


def go(root, wb, state=None, **kw):
    state = state if state is not None else arch.load_state(str(root / 'state.json'))
    kw.setdefault('now', lambda: NOW)
    kw.setdefault('poll_every', 0)
    kw.setdefault('log', lambda *_: None)
    stats = arch.run(cov.load_sources(str(root)), state, wb, **kw)
    return stats, state


def fields(path):
    return cov._yaml_load(open(path, encoding='utf-8'))


def test_a_capture_records_the_url_and_keeps_the_file_layout(tmp_path):
    p = write(tmp_path, 'src-a')
    stats, _ = go(tmp_path, FakeWayback())
    r = fields(p)
    assert r['archive_status'] == 'ok'
    assert r['archive_url'] == 'https://web.archive.org/web/20261001120000/https://example.org/src-a'
    assert r['archive_requested_at'] == '2026-10-01T12:00:00Z'
    text = p.read_text(encoding='utf-8')
    assert text.startswith('# data/sources/2026/src-a.yaml -- test fixture')
    assert 'a line that must survive the rewrite' in text
    assert stats['captured'] == 1 and stats['submitted'] == 1


def test_a_recent_cdx_capture_is_used_without_submitting(tmp_path):
    p = write(tmp_path, 'src-a')
    wb = FakeWayback(cdx={'https://example.org/src-a': '20260920000000'})
    stats, _ = go(tmp_path, wb)
    assert wb.submitted == [] and stats['from_cdx'] == 1
    assert fields(p)['archive_digest'] == 'DIGEST'


def test_a_cdx_capture_older_than_30_days_is_not_enough(tmp_path):
    write(tmp_path, 'src-a')
    wb = FakeWayback(cdx={'https://example.org/src-a': '20260801000000'})
    go(tmp_path, wb)
    assert wb.submitted == ['https://example.org/src-a']


def test_doi_done_failed_and_no_collect_sources_are_skipped(tmp_path):
    write(tmp_path, 'src-doi', doi="'10.1/x'")
    write(tmp_path, 'src-failed', status='failed', reason="'error:blocked-url'")
    write(tmp_path, 'src-blocked', url='https://nocollect.example/{id}')
    (tmp_path / 'ingest').mkdir()
    wb = FakeWayback()
    go(tmp_path, wb, no_collect={'nocollect.example'})
    assert wb.looked_up == []


def test_the_budget_caps_submissions_and_the_cursor_resumes(tmp_path):
    for i, day in enumerate(['25', '26', '27', '28']):
        write(tmp_path, 'src-%d' % i, fetched='2026-09-%sT00:00:00Z' % day)
    wb = FakeWayback()
    stats, state = go(tmp_path, wb, max_captures=2)
    assert wb.submitted == ['https://example.org/src-0', 'https://example.org/src-1']  # oldest first
    assert stats['stopped'] == 'budget: 2 captures'
    wb2 = FakeWayback()
    go(tmp_path, wb2, state=state, max_captures=2)
    assert wb2.submitted == ['https://example.org/src-2', 'https://example.org/src-3']


def test_the_cursor_rotates_past_a_source_that_keeps_failing(tmp_path):
    write(tmp_path, 'src-0', fetched='2026-09-25T00:00:00Z')
    write(tmp_path, 'src-1', fetched='2026-09-26T00:00:00Z')
    flaky = [('error', 'error:service-unavailable', 'down')]
    wb = FakeWayback(results={'https://example.org/src-0': list(flaky)})
    _, state = go(tmp_path, wb, max_captures=1)
    wb2 = FakeWayback()
    go(tmp_path, wb2, state=state, max_captures=1)
    assert wb2.submitted == ['https://example.org/src-1']  # not the head of the queue again


def test_a_transient_error_stays_pending_then_fails_after_max_attempts(tmp_path):
    p = write(tmp_path, 'src-a')
    err = ('error', 'error:service-unavailable', 'try later')
    state = arch.load_state(str(tmp_path / 'state.json'))
    for n in (1, 2):
        wb = FakeWayback(results={'https://example.org/src-a': [err]})
        go(tmp_path, wb, state=state, max_attempts=3)
        r = fields(p)
        assert r['archive_status'] == 'pending' and 'service-unavailable' in r['failure_reason']
        assert state['attempts']['src-a']['count'] == n
        assert r['archive_requested_at'] == '2026-10-01T12:00:00Z'  # the first request, never moved
    go(tmp_path, FakeWayback(results={'https://example.org/src-a': [err]}), state=state, max_attempts=3)
    r = fields(p)
    assert r['archive_status'] == 'failed' and r['failure_reason'].startswith('gave up after 3 runs')
    assert 'src-a' not in state['attempts']


def test_a_permanent_refusal_fails_at_once(tmp_path):
    p = write(tmp_path, 'src-a')
    wb = FakeWayback(submit={'https://example.org/src-a': ('error', 'error:blocked-url', 'robots')})
    go(tmp_path, wb)
    r = fields(p)
    assert r['archive_status'] == 'failed' and 'error:blocked-url' in r['failure_reason']


def test_the_first_request_stamp_is_not_moved_forward(tmp_path):
    p = write(tmp_path, 'src-a', requested="'2026-09-23T19:35:56Z'")
    go(tmp_path, FakeWayback(results={'https://example.org/src-a': [('error', 'error:proxy-error', '')]}))
    assert fields(p)['archive_requested_at'] == '2026-09-23T19:35:56Z'


def test_bad_credentials_stop_the_run_without_touching_records(tmp_path):
    p = write(tmp_path, 'src-a')
    before = p.read_text(encoding='utf-8')
    wb = FakeWayback(submit={'https://example.org/src-a': arch.StopRun('401')})
    stats, state = go(tmp_path, wb)
    assert stats['stopped'] == '401' and state['attempts'] == {}
    assert p.read_text(encoding='utf-8') == before


def test_a_spent_daily_budget_stops_the_run_and_counts_no_attempt(tmp_path):
    write(tmp_path, 'src-a')
    write(tmp_path, 'src-b', fetched='2026-09-29T00:00:00Z')
    wb = FakeWayback(submit={'https://example.org/src-a': ('error', 'error:too-many-daily-captures', '')})
    stats, state = go(tmp_path, wb)
    assert stats['stopped'].startswith('SPN2 error:too-many-daily-captures') and state['attempts'] == {}
    assert wb.submitted == []


def test_without_keys_the_run_is_cdx_only(tmp_path):
    p = write(tmp_path, 'src-a')
    before = p.read_text(encoding='utf-8')
    wb = FakeWayback(can_capture=False)
    stats, _ = go(tmp_path, wb)
    assert stats['mode'] == 'cdx-only' and wb.submitted == [] and wb.looked_up
    assert p.read_text(encoding='utf-8') == before  # no stamp for a request never made


def test_dry_run_writes_nothing(tmp_path):
    p = write(tmp_path, 'src-a')
    before = p.read_text(encoding='utf-8')
    go(tmp_path, FakeWayback(cdx={'https://example.org/src-a': '20260930000000'}), dry_run=True)
    assert p.read_text(encoding='utf-8') == before


def test_every_committed_source_has_the_fields_the_archiver_rewrites():
    for s in cov.load_sources(ROOT):
        missing = [k for k in arch.FIELDS if k not in s.record]
        assert not missing, (s.record['id'], missing)


def test_the_committed_state_file_loads():
    st = arch.load_state(arch.STATE)
    assert set(st) >= {'version', 'cursor', 'attempts', 'runs'}


def test_a_spent_daily_budget_leaves_the_record_unstamped(tmp_path):
    p = write(tmp_path, 'src-a')
    before = p.read_text(encoding='utf-8')
    go(tmp_path, FakeWayback(submit={'https://example.org/src-a': ('error', 'error:too-many-daily-captures', '')}))
    assert p.read_text(encoding='utf-8') == before


def test_network_errors_are_transient_and_three_in_a_row_stop_the_run(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError('The read operation timed out')
    monkeypatch.setattr(arch.urllib.request, 'urlopen', boom)
    wb = arch.Wayback('k', 's', spacing=0)
    assert wb.latest('https://example.org/') is None
    assert wb.submit('https://example.org/') == ('error', 'error:network', 'The read operation timed out')
    with pytest.raises(arch.StopRun, match='unreachable'):
        wb.poll('job')


def test_a_job_pending_past_the_timeout_settles_as_an_error(tmp_path, monkeypatch):
    p = write(tmp_path, 'src-a')
    monkeypatch.setattr(arch, 'JOB_TIMEOUT', -1)
    go(tmp_path, FakeWayback(results={'https://example.org/src-a': [('pending',)]}))
    assert 'error:poll-timeout' in fields(p)['failure_reason']
