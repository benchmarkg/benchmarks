"""The rolling archival budget (P5-S8-T02; 06 S7.1, S7.3, S3.18; 07 S10; 14 Phase 5 exit criterion 3).

ingest/archive_sources.py (P1-S2-T08) implements the budget; this holds it across runs, and adds
the two things P5-S8-T02 asks for: a failed capture lowers the Source's reliability
(schema.source.reliability), and scripts/count_unarchived.py counts what is still uncaptured and
fails above the budget or on any dead uncaptured Source -- "zero dead unarchived source links".

The Wayback client is faked at the level of its methods for the run tests, and at the level of its
one HTTP primitive (`_request`) for the transport tests, so the URLs and form fields it sends are
the production ones. Nothing touches the network.
"""
import json
import os
import sys
from datetime import datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import count_unarchived as CU  # noqa: E402
from check_archive_coverage import Source as Held  # noqa: E402
from ingest import archive_sources as A  # noqa: E402
from schema.source import RELIABILITY, reliability  # noqa: E402
from tools.archive import Wayback  # noqa: E402

NOW = datetime(2026, 9, 29, 3, 31, tzinfo=timezone.utc)
FIELDS = ('archive_url', 'archive_captured', 'archive_status', 'archive_digest', 'archive_requested_at',
          'failure_reason')


def write(root, sid, **over):
    rec = {'id': sid, 'type': 'documentation', 'url': 'https://%s.example.org/' % sid, 'doi': None,
           'fetched_at': None, 'accessed': None, 'archive_url': None, 'archive_captured': None,
           'archive_status': 'pending', 'archive_digest': None, 'archive_requested_at': None,
           'failure_reason': None, 'licence_class': 'unlicensed', 'licence_checked_on': '2026-09-01',
           'provenance': 'primary', 'notes': None, **over}
    d = os.path.join(root, 'data', 'sources', '2026')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, sid + '.yaml')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for k, v in rec.items():
            fh.write('%s: %s\n' % (k, 'null' if v is None else json.dumps(v) if isinstance(v, str) else v))
    return path


def corpus(root, n=7):
    """n pending Sources, first ingested on consecutive days: src-s0 is the oldest."""
    for i in range(n):
        write(root, 'src-s%d' % i, accessed='2026-09-%02d' % (10 + i))
    return A.load_sources(str(root))


class Fake:
    """Wayback's four calls. `polls` maps a URL to what its job reports; default success."""

    def __init__(self, polls=None, cdx=None, can_capture=True):
        self.polls, self.cdx, self.can_capture = polls or {}, cdx or {}, can_capture
        self.submitted, self.looked_up, self._jobs = [], [], {}

    def latest(self, url):
        self.looked_up.append(url)
        return self.cdx.get(url)                   # get-default: no capture in the fake

    def submit(self, url):
        self.submitted.append(url)
        job = 'job-%d' % len(self.submitted)
        self._jobs[job] = url
        return job

    def poll(self, job):
        url = self._jobs[job]
        return self.polls.get(url, ('success', '20260929033100', url))   # get-default: success unless told


def run(root, wb, state_path, **kw):
    state = A.load_state(state_path)
    stats = A.run(A.load_sources(str(root)), state, wb, now=lambda: NOW, poll_every=0, log=lambda m: None,
                  persist=lambda: A.save_state(state_path, state), **kw)
    A.save_state(state_path, state)
    return stats, state


# ---- the cap and the cursor, across runs --------------------------------------------------------

def test_the_nightly_cap_and_the_cursor_hold_across_runs(tmp_path):
    corpus(tmp_path)
    state = str(tmp_path / 'ingest' / 'state' / 'archive.json')
    seen = []
    for expected in (['src-s0', 'src-s1', 'src-s2'], ['src-s3', 'src-s4', 'src-s5'], ['src-s6']):
        wb = Fake()
        stats, st = run(tmp_path, wb, state, max_captures=3)
        got = [u.split('//')[1].split('.')[0] for u in wb.submitted]
        assert got == expected and stats['submitted'] == len(expected) <= 3
        seen += got
    assert seen == ['src-s%d' % i for i in range(7)]                      # each Source once, oldest first
    assert all(s.record['archive_status'] == 'ok' for s in A.load_sources(str(tmp_path)))
    assert [r['submitted'] for r in json.load(open(state))['runs']] == [3, 3, 1]


def test_a_run_cut_off_by_the_cap_resumes_after_its_cursor_not_at_the_head(tmp_path):
    corpus(tmp_path)
    state = str(tmp_path / 'archive.json')
    transient = {'https://src-s%d.example.org/' % i: ('error', 'error:service-unavailable', 'busy') for i in range(7)}
    wb = Fake(polls=transient)
    stats, st = run(tmp_path, wb, state, max_captures=3)
    assert stats['stopped'] == 'budget: 3 captures' and st['cursor'][1] == 'src-s2'
    wb2 = Fake(polls=transient)
    run(tmp_path, wb2, state, max_captures=3)
    assert [u.split('//')[1].split('.')[0] for u in wb2.submitted] == ['src-s3', 'src-s4', 'src-s5']
    wb3 = Fake(polls=transient)
    run(tmp_path, wb3, state, max_captures=3)                              # wraps: s6, then the head again
    assert [u.split('//')[1].split('.')[0] for u in wb3.submitted] == ['src-s6', 'src-s0', 'src-s1']


def test_the_default_budget_is_500(tmp_path):
    for i in range(503):
        write(tmp_path, 'src-b%03d' % i, accessed='2026-09-01')
    wb = Fake()
    stats, _ = run(tmp_path, wb, str(tmp_path / 'archive.json'))
    assert stats['submitted'] == 500 and len(wb.submitted) == 500 and stats['stopped'] == 'budget: 500 captures'
    import inspect
    assert inspect.signature(A.run).parameters['max_captures'].default == 500 == CU.BUDGET


def test_a_cdx_capture_inside_the_window_costs_no_capture(tmp_path):
    corpus(tmp_path, 2)
    wb = Fake(cdx={'https://src-s0.example.org/': ('20260920000000', 'https://src-s0.example.org/', 'D' * 32)})
    stats, _ = run(tmp_path, wb, str(tmp_path / 'archive.json'))
    assert stats['from_cdx'] == 1 and wb.submitted == ['https://src-s1.example.org/']
    assert wb.looked_up == ['https://src-s0.example.org/', 'https://src-s1.example.org/']   # CDX first, every time


def test_one_request_per_source_never_per_field(tmp_path):
    write(tmp_path, 'src-many', accessed='2026-09-01',
          notes='See https://mirror.example.net/a and https://docs.example.net/b for the same table.')
    wb = Fake()
    run(tmp_path, wb, str(tmp_path / 'archive.json'))
    assert wb.submitted == ['https://src-many.example.org/'] and wb.looked_up == ['https://src-many.example.org/']


# ---- the transport: if_not_archived_within=30d, CDX, never the Availability API ----------------

def test_the_capture_asks_for_30d_and_existence_goes_through_cdx(monkeypatch):
    sent = []

    def request(url, data=None, auth=False):
        sent.append((url, data))
        if '/cdx/' in url:
            return 200, '[["timestamp","original","digest"]]'
        return 200, '{"job_id": "spn2-1"}'

    wb = Wayback('key', 'secret', spacing=0)
    monkeypatch.setattr(wb, '_request', request)
    assert wb.latest('https://x.example.org/') is None
    assert wb.submit('https://x.example.org/') == 'spn2-1'
    (cdx, _), (save, form) = sent
    assert cdx.startswith('https://web.archive.org/cdx/search/cdx?')
    assert save == 'https://web.archive.org/save' and form['if_not_archived_within'] == '30d'
    assert not any('archive.org/wayback/available' in u for u, _ in sent)
    src = open(os.path.join(ROOT, 'tools', 'archive.py'), encoding='utf-8').read()
    assert 'wayback/available?' not in src                                 # nowhere in the client


# ---- a failure is recorded, with its reason, and lowers reliability ----------------------------

def test_a_refused_capture_is_failed_with_its_reason_and_lowers_reliability(tmp_path):
    corpus(tmp_path, 1)
    before = A.load_sources(str(tmp_path))[0].record
    assert reliability(before) == 'pending'
    wb = Fake(polls={'https://src-s0.example.org/': ('error', 'error:blocked-url', 'robots.txt forbids it')})
    stats, _ = run(tmp_path, wb, str(tmp_path / 'archive.json'))
    after = A.load_sources(str(tmp_path))[0].record
    assert stats['failed'] == 1 and after['archive_status'] == 'failed'
    assert 'error:blocked-url' in after['failure_reason'] and 'robots' in after['failure_reason']
    assert reliability(after) == 'unarchivable'
    assert RELIABILITY.index(reliability(after)) < RELIABILITY.index(reliability(before))


def test_a_transient_failure_gives_up_after_max_attempts_with_the_reason(tmp_path):
    corpus(tmp_path, 1)
    busy = {'https://src-s0.example.org/': ('error', 'error:service-unavailable', 'busy')}
    state = str(tmp_path / 'archive.json')
    for _ in range(3):
        run(tmp_path, Fake(polls=busy), state, max_attempts=3)
    rec = A.load_sources(str(tmp_path))[0].record
    assert rec['archive_status'] == 'failed' and rec['failure_reason'].startswith('gave up after 3 runs')


@pytest.mark.parametrize('record, rung', [
    ({'doi': '10.48550/arXiv.2310.06770', 'archive_status': 'not-required'}, 'archived'),
    ({'archive_url': 'https://web.archive.org/web/2026/x', 'archive_status': 'ok'}, 'archived'),
    ({'archive_status': 'not-required'}, 'archived'),
    ({'archive_status': 'pending'}, 'pending'),
    ({'archive_status': 'failed', 'failure_reason': 'x'}, 'unarchivable'),
    ({'archive_status': 'failed', 'failure_reason': 'x', 'link_status': 'dead'}, 'lost'),
    ({'archive_status': 'pending', 'link_status': 'dead'}, 'lost'),
    ({'archive_url': 'https://web.archive.org/web/2026/x', 'archive_status': 'ok', 'link_status': 'dead'}, 'archived'),
    ({'doi': '10.1234/x', 'archive_status': 'not-required', 'link_status': 'dead'}, 'archived'),
])
def test_the_reliability_ladder(record, rung):
    assert reliability(record) == rung


# ---- scripts/count_unarchived.py ----------------------------------------------------------------

def test_the_count_is_non_doi_and_uncaptured_only_oldest_first(tmp_path):
    write(tmp_path, 'src-new', accessed='2026-09-20')
    write(tmp_path, 'src-old', accessed='2026-09-02')
    write(tmp_path, 'src-undated')
    write(tmp_path, 'src-paper', doi='10.48550/arXiv.2310.06770', archive_status='not-required')
    write(tmp_path, 'src-kept', archive_url='https://web.archive.org/web/20260901000000/x', archive_status='ok',
          archive_captured='2026-09-01')
    write(tmp_path, 'src-paywall', archive_status='not-required')
    got = CU.survey(str(tmp_path), NOW)
    assert [x['id'] for x in got['unarchived']] == ['src-undated', 'src-old', 'src-new']
    assert [x['id'] for x in got['exempt']] == ['src-paywall']
    assert got['unarchived'][1]['age_days'] == 27 and got['lost'] == []
    assert CU.main(['--root', str(tmp_path), '--now', '2026-09-29T03:31:00Z']) == 0


def test_above_the_budget_it_fails_naming_the_oldest_first(tmp_path, capsys):
    for i in range(5):
        write(tmp_path, 'src-u%d' % i, accessed='2026-09-%02d' % (20 - i))       # src-u4 is the oldest
    assert CU.main(['--root', str(tmp_path), '--budget', '4', '--now', '2026-09-29T03:31:00Z']) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].split()[1] == 'src-u4' and out[4].split()[1] == 'src-u0'
    assert 'budget 4, OVER' in out[-1]
    assert CU.main(['--root', str(tmp_path), '--budget', '5']) == 0


def test_a_dead_unarchived_source_fails_the_count_whatever_the_budget(tmp_path, capsys):
    write(tmp_path, 'src-gone', accessed='2026-09-10', archive_status='failed',
          failure_reason='dead and never captured', link_status='dead', link_checked_at='2026-09-29T08:43:00Z')
    write(tmp_path, 'src-fine', accessed='2026-09-01')
    assert CU.main(['--root', str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert out.startswith('LOST        src-gone') and '1 lost' in out and 'exit criterion 3' in out
    got = CU.survey(str(tmp_path), NOW)
    assert [x['id'] for x in got['lost']] == ['src-gone'] and [x['id'] for x in got['unchecked']] == ['src-fine']


def test_the_json_report_carries_the_exit_code(tmp_path, capsys):
    write(tmp_path, 'src-u', accessed='2026-09-01')
    assert CU.main(['--root', str(tmp_path), '--json']) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc['budget'] == 500 and doc['exit_code'] == 0 and doc['unarchived'][0]['reliability'] == 'pending'
