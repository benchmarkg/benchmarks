"""Liveness probes, the derived maintenance_status and the bot's `dead` proposal (P5-S7-T01; 05 S7, 02 S8, 06 S3.3).

The verify: `pytest tests/ingest/test_liveness.py`. Done when "Twelve cold months produce a linked, evidenced proposal
and nothing is reclassified without human confirmation." So, with no network at all (every socket and urlopen is
patched to raise; the transports are scripted or replay tests/ingest/fixtures/liveness/http/):

  - the records: one line per signal per probe with 02 S8's eight fields, in metrics/liveness/<yyyy>-W<ww>.jsonl,
    idempotent within an ISO week, on 02 S8's cadence;
  - the reads: pushed_at and archived, lastModified, the leaderboard fingerprint, the curated board date, the
    homepage's HTTP state; 02 S8's dead / blocked / refused / error outcomes, three consecutive failures before a
    signal is dead, a 403 or an anti-bot page never death;
  - the derivation: 02 S8's table at its boundaries, the two-indicator rule, `unobservable` for blocked and
    too-young signals, the 30-day quarantine toward `abandoned` and none away from it;
  - the proposal: twelve cold months produce one, linked to the week file and probe behind each piece of evidence;
    eleven do not, nor does one warm or unobservable signal, a contested status or an entry already dormant; it is
    opened once and never rewritten; and the failure case -- a reclassification without people -- is impossible:
    data/ is byte-identical after a run and the writer refuses any path under it;
  - politeness: the policy's User-Agent, a token only for its own host and only from the environment, robots.txt
    and the no-collect list honoured, one request at a time per host, budgets kept, redirects admitted hop by hop.

The ledger also names ingest/test_liveness.py. No test module lives under ingest/ -- the repository's tests are all
under tests/, and ingest/ is the tree the adapters' lints sweep (scripts/check_no_get_default.py, the URL-opening
scan in tests/ingest/test_policy.py) -- so the tests are here only.
"""
import hashlib
import json
import os
import shutil
import socket
import ssl
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import pytest

from ingest import liveness as L
from ingest.http import policy as P

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'liveness')
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.date()
FIELD = {'git-host': 'repository', 'hf-dataset': 'dataset_url', 'hf-space': 'leaderboard_url',
         'leaderboard': 'leaderboard_url', 'leaderboard-date': 'liveness.leaderboard_last_updated',
         'homepage': 'homepage'}
URL = {'git-host': 'https://api.github.com/repos/o/r', 'hf-dataset': 'https://huggingface.co/api/datasets/o/d',
       'hf-space': 'https://huggingface.co/api/spaces/o/s', 'leaderboard': 'https://board.example.org/lb',
       'leaderboard-date': 'https://board.example.org/lb', 'homepage': 'https://home.example.org/'}
EIGHT = ('signal_type', 'url', 'http_method', 'http_status', 'observed_at', 'value', 'consecutive_failures',
         'probe_blocked')


# ---- no network, ever -------------------------------------------------------------------------------------------

def no_network(*a, **k):
    raise AssertionError('a test reached for the network')


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    monkeypatch.setattr(socket, 'create_connection', no_network)
    monkeypatch.setattr(socket, 'getaddrinfo', no_network)
    monkeypatch.setattr(urllib.request, 'urlopen', no_network)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', no_network)
    monkeypatch.delenv('GH_API_TOKEN', raising=False)
    monkeypatch.delenv('HF_TOKEN', raising=False)


# ---- helpers ----------------------------------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 6))
        self.t += s


class Script:
    """A transport answering {url: Reply or [Reply, ...] served in turn}; it records what it was asked."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def get(self, url, headers):
        self.asked.append((url, dict(headers)))
        a = self.answers[url]
        return a.pop(0) if isinstance(a, list) else a


def gate(robots=None, clock=None, doc=None):
    clock = clock or Clock()
    pol = P.Policy.from_dict(doc) if doc else P.Policy.load()
    return L.ProbeGate(pol, robots=robots or (lambda url, ua: (404, '')), clock=clock, sleep=clock.sleep)


def prober(answers, **kw):
    return L.Prober(Script(answers), gate(**kw))


def html(rows=(('1', 'sys-a', '50.0'), ('2', 'sys-b', '40.0')), extra=''):
    trs = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in rows)
    return ('<html><head><title>Board</title></head><body>%s<p>%s</p><table>%s</table></body></html>'
            % (extra, 'x' * 600, trs)).encode()


def target(kind='git-host', url=None, bench='b', **kw):
    return L.Target(bench, kind, FIELD[kind], url or URL[kind], url or URL[kind], **kw)


def rec(day, kind='git-host', value=None, outcome='ok', failures=0, bench='b', detail=None, status=200, url=None):
    return {'benchmark': bench, 'signal_type': kind, 'field': FIELD[kind], 'url': url or URL[kind],
            'http_method': 'GET', 'http_status': status, 'observed_at': '%sT12:00:00Z' % day, 'value': value,
            'consecutive_failures': failures, 'probe_blocked': outcome in ('blocked', 'refused'),
            'outcome': outcome, 'note': None, 'detail': detail or {}}


def repo(pushed='2026-11-01T09:00:00Z', archived=False):
    return json.dumps({'pushed_at': pushed, 'archived': archived}).encode()


def fixture_prober(clock=None):
    t = L.FixtureProbeTransport(os.path.join(FIX, 'http'))
    clock = clock or Clock()
    return L.Prober(t, L.ProbeGate(P.Policy.load(), robots=t.robots, clock=clock, sleep=clock.sleep))


@pytest.fixture()
def tree(tmp_path):
    """A writable copy of the fixture repository tree."""
    dst = tmp_path / 'root'
    shutil.copytree(os.path.join(FIX, 'root'), dst)
    return str(dst)


def digest(path):
    out = {}
    for d, _, fs in os.walk(path):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, path).replace(os.sep, '/')] = hashlib.sha256(fh.read()).hexdigest()
    return out


# ---- the vocabulary ---------------------------------------------------------------------------------------------

def test_the_statuses_are_taxonomy_maintenance_yamls_five_and_the_proposed_value_is_a_lifecycle_term():
    from schema.taxonomy import read_yaml
    maintenance = {t['id'] for t in read_yaml(os.path.join(ROOT, 'taxonomy', 'maintenance.yaml'))['terms']}
    assert set(L.STATUSES) == maintenance
    assert L.PROPOSED_VALUE in L.lifecycle_terms()


def test_dead_is_not_a_lifecycle_term_which_is_why_the_proposal_names_dormant():
    # 05 S7 says `lifecycle: dead`; taxonomy/lifecycle.yaml's ten terms hold no `dead`. If one is ever added, this
    # fails and PROPOSED_VALUE should be revisited.
    assert L.PLAN_TERM not in L.lifecycle_terms() and len(L.lifecycle_terms()) == 10


# ---- what is probed ---------------------------------------------------------------------------------------------

def test_a_records_fields_become_its_signals_each_url_once():
    rec_ = {'repository': 'https://github.com/org-x/bench-y', 'dataset_url': 'https://huggingface.co/datasets/org-x/d',
            'leaderboard_url': 'https://huggingface.co/spaces/org-x/board',
            'homepage': 'https://github.com/org-x/bench-y/',
            'external_ids': {'huggingface': 'org-x/other'},
            'liveness': {'leaderboard_last_updated': date(2026, 9, 1), 'last_checked': date(2026, 11, 10)}}
    got = [(t.signal_type, t.field, t.url) for t in L.targets('y', rec_)]
    assert got == [
        ('git-host', 'repository', 'https://api.github.com/repos/org-x/bench-y'),
        ('hf-dataset', 'dataset_url', 'https://huggingface.co/api/datasets/org-x/d'),
        ('hf-space', 'leaderboard_url', 'https://huggingface.co/api/spaces/org-x/board'),
        ('leaderboard-date', 'liveness.leaderboard_last_updated', 'https://huggingface.co/spaces/org-x/board'),
    ]                                       # the homepage is the repository page: probed once, through the API
    t = L.targets('y', {'external_ids': {'huggingface': 'org-x/only'}, 'leaderboard_url': 'https://lb.example.org/',
                        'homepage': 'https://site.example.org/', 'repository': 'https://gitlab.com/a/b'})
    assert [(x.signal_type, x.url) for x in t] == [
        ('hf-dataset', 'https://huggingface.co/api/datasets/org-x/only'),
        ('leaderboard', 'https://lb.example.org/'), ('homepage', 'https://site.example.org/')]   # no GitLab reader


def test_the_curated_board_date_is_a_signal_read_from_the_record_with_no_request():
    live = {'leaderboard_last_updated': date(2025, 11, 20), 'last_checked': date(2026, 11, 10)}
    t = L.targets('y', {'leaderboard_url': 'https://lb.example.org/', 'liveness': live})
    s = Script({})
    r = L.probe(t[1], L.Prober(s, gate()), [], NOW)
    assert (r['value'], r['http_method'], r['http_status'], r['outcome']) == ('2025-11-20', None, None, 'ok')
    assert r['detail'] == {'source': 'the curated record', 'checked_on': '2026-11-10'} and s.asked == []


# ---- the reads --------------------------------------------------------------------------------------------------

def test_a_git_host_probe_records_02_s8s_eight_fields_with_pushed_at_and_archived():
    p = prober({URL['git-host']: L.Reply(200, [('ETag', '"e1"')], repo('2024-06-01T16:40:11Z', True))})
    r = L.probe(target(), p, [], NOW)
    assert set(EIGHT) <= set(r)
    assert (r['value'], r['http_status'], r['outcome'], r['probe_blocked'], r['consecutive_failures']) == \
        ('2024-06-01', 200, 'ok', False, 0)
    assert r['detail'] == {'archived': True, 'etag': '"e1"'} and r['observed_at'] == '2026-11-23T12:00:00Z'
    assert p.transport.asked[0][1]['Accept'] == 'application/vnd.github+json'


def test_a_304_to_the_recorded_etag_carries_the_value_forward():
    p = prober({URL['git-host']: L.Reply(304, [], b'')})
    prev = rec('2026-11-16', value='2024-06-01', detail={'archived': True, 'etag': '"e1"'})
    r = L.probe(target(), p, [prev], NOW)
    assert p.transport.asked[0][1]['If-None-Match'] == '"e1"'
    assert (r['value'], r['outcome'], r['detail']['archived']) == ('2024-06-01', 'not-modified', True)


def test_a_hugging_face_probe_reads_last_modified_and_a_401_is_blocked_not_dead():
    p = prober({URL['hf-dataset']: [L.Reply(200, [], b'{"lastModified": "2026-10-15T07:02:44.000Z"}'),
                                    L.Reply(401, [], b'{"error": "Repository not found"}')]})
    assert L.probe(target('hf-dataset'), p, [], NOW)['value'] == '2026-10-15'
    r = L.probe(target('hf-dataset'), p, [], NOW)
    assert (r['outcome'], r['probe_blocked']) == ('blocked', True) and 'private, gated or missing' in r['note']


def test_an_answer_missing_its_field_is_an_error_and_the_last_value_stands():
    p = prober({URL['git-host']: L.Reply(200, [], b'{"full_name": "o/r"}')})
    prev = rec('2026-11-16', value='2026-10-01')
    r = L.probe(target(), p, [prev], NOW)
    assert (r['outcome'], r['value']) == ('error', None) and 'pushed_at' in r['note']
    assert L.derive([prev, r], TODAY)['last_activity'] == '2026-10-01'


def test_a_404_on_a_catalogued_repository_is_signal_counted_three_times_before_it_is_dead():
    p = prober({URL['git-host']: L.Reply(404, [], b'{"message": "Not Found"}')})
    history = [rec('2026-10-26', value='2026-10-01')]
    for day, n in (('2026-11-02', 1), ('2026-11-09', 2), ('2026-11-16', 3)):
        r = L.probe(target(), p, history, datetime.fromisoformat(day + 'T12:00:00+00:00'))
        assert (r['outcome'], r['consecutive_failures']) == ('dead', n)
        history.append(r)
        state = L.assess(history, date.fromisoformat(day))['state']
        assert state == ('dead' if n == 3 else 'dated')        # "A single failure never changes a status"
    s = L.assess(history, date(2026, 11, 16))
    assert s['last_activity'] == '2026-10-01' and '3 consecutive dead probes since 2026-11-02' in s['basis']


def test_blocked_and_errors_neither_count_nor_reset_and_a_success_resets():
    p = prober({URL['homepage']: [L.Reply(404, [], b''), L.Reply(403, [], b''), L.Reply(503, [], b''),
                                  L.Reply(404, [], b''), L.Reply(200, [], html())]})
    history, seen = [], []
    for _ in range(5):
        r = L.probe(target('homepage'), p, history, NOW)
        history.append(r)
        seen.append((r['outcome'], r['consecutive_failures']))
    assert seen == [('dead', 1), ('blocked', 1), ('error', 1), ('dead', 2), ('ok', 0)]
    assert p.transport.asked[0][1] == {'Range': L.RANGE}


@pytest.mark.parametrize('reply,outcome', [
    (L.Reply(None, [], b'', 'DNS failure: Name or service not known', 'dead'), 'dead'),
    (L.Reply(410, [], b''), 'dead'),
    (L.Reply(200, [], b'<html><body>Page not found</body></html>'), 'dead'),          # 02 S8's soft-404
    (L.Reply(200, [], b'<html><body>This dataset is no longer available.</body></html>'), 'dead'),
    (L.Reply(401, [], b''), 'blocked'),
    (L.Reply(403, [], b''), 'blocked'),
    (L.Reply(429, [('Retry-After', '60')], b''), 'blocked'),
    (L.Reply(403, [('cf-mitigated', 'challenge')], b'<html>...</html>'), 'blocked'),
    (L.Reply(200, [], b'<html><head><title>Just a moment...</title></head></html>'), 'blocked'),
    (L.Reply(503, [], b'<script src="/cdn-cgi/challenge-platform/h/b/x"></script>'), 'blocked'),
    (L.Reply(None, [], b'', 'timed out: read timeout', 'error'), 'error'),
    (L.Reply(500, [], b''), 'error'),
])
def test_02_s8s_dead_blocked_and_everything_else(reply, outcome):
    r = L.probe(target('leaderboard'), prober({URL['leaderboard']: reply}), [], NOW)
    assert r['outcome'] == outcome
    assert r['probe_blocked'] is (outcome == 'blocked')


def test_a_page_served_through_a_cdn_that_carries_its_script_is_still_a_page():
    body = html(extra='<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>')
    r = L.probe(target('leaderboard'), prober({URL['leaderboard']: L.Reply(200, [], body)}), [], NOW)
    assert r['outcome'] == 'ok' and r['value']


@pytest.mark.parametrize('exc,kind,words', [
    (urllib.error.URLError(socket.gaierror(-2, 'Name or service not known')), 'dead', 'DNS failure'),
    (ConnectionRefusedError(111, 'Connection refused'), 'dead', 'refused or reset'),
    (ConnectionResetError(104, 'Connection reset by peer'), 'dead', 'refused or reset'),
    (urllib.error.URLError(ssl.SSLCertVerificationError(1, 'certificate verify failed')), 'dead', 'TLS failure'),
    (TimeoutError('The read operation timed out'), 'error', 'timed out'),
])
def test_network_failures_are_read_by_02_s8s_list(exc, kind, words):
    got = L.network_failure(exc)
    assert got[0] == kind and words in got[1]


def test_a_redirect_to_the_site_root_is_a_soft_404_and_a_same_site_move_is_not():
    to_root = {URL['leaderboard']: L.Reply(301, [('Location', '/')], b''),
               'https://board.example.org/': L.Reply(200, [], html())}
    r = L.probe(target('leaderboard'), prober(to_root), [], NOW)
    assert r['outcome'] == 'dead' and 'site root' in r['note']
    assert r['detail']['final_url'] == 'https://board.example.org/'
    moved = {URL['leaderboard']: L.Reply(302, [('Location', '/v2/lb')], b''),
             'https://board.example.org/v2/lb': L.Reply(200, [], html())}
    r = L.probe(target('leaderboard'), prober(moved), [], NOW)
    assert r['outcome'] == 'ok' and r['detail']['final_url'] == 'https://board.example.org/v2/lb'


def test_a_homepage_that_refuses_the_range_is_asked_again_without_it():
    p = prober({URL['homepage']: [L.Reply(416, [], b''), L.Reply(200, [], html())]})
    assert L.probe(target('homepage'), p, [], NOW)['outcome'] == 'ok'
    assert [h for _, h in p.transport.asked] == [{'Range': L.RANGE}, {}]


# ---- the fingerprint (02 S8: an undated board) ------------------------------------------------------------------

def test_the_fingerprint_reads_result_rows_only_and_ignores_order_scripts_styles_whitespace_and_ad_slots():
    a = L.fingerprint(html(), 'text/html')
    b = L.fingerprint(html(rows=(('2', '  sys-b ', '40.0'), ('1', 'sys-a', '50.0')),
                           extra='<script>var t = Date.now()</script><style>td{}</style>'
                                 '<div id="ad-banner"><table><tr><td>Buy now</td></tr></table></div>'), 'text/html')
    assert a == b and a[1] == {'basis': 'table-rows', 'rows': 2}
    assert L.fingerprint(html(rows=(('1', 'sys-a', '50.1'), ('2', 'sys-b', '40.0'))), 'text/html')[0] != a[0]


def test_a_board_with_no_result_table_has_no_fingerprint_and_is_unobservable_never_stale():
    shell = b'<html><body><div id="root"></div><script src="/app.js"></script></body></html>' + b' ' * 600
    value, detail = L.fingerprint(shell, 'text/html')
    assert value is None and detail == {'basis': 'no-table-rows'}
    r = L.probe(target('leaderboard'), prober({URL['leaderboard']: L.Reply(200, [], shell)}), [], NOW)
    old = rec('2025-01-06', 'leaderboard', value=None)
    assert L.derive([old, r], TODAY)['status'] == 'unobservable'


def test_a_json_board_is_fingerprinted_canonically():
    a = L.fingerprint(b'[{"model": "m1", "score": 1}, {"model": "m2", "score": 2}]', 'application/json')
    b = L.fingerprint(b'[{"score": 2, "model": "m2"}, {"score": 1, "model": "m1"}]', None)
    assert a == b and a[1] == {'basis': 'json', 'rows': 2}


def test_an_unchanged_fingerprint_is_no_evidence_before_180_days_and_a_lower_bound_after():
    f = 'f' * 64
    history = [rec('2026-06-01', 'leaderboard', value=f), rec('2026-11-16', 'leaderboard', value=f)]
    young = L.derive(history, date(2026, 11, 27))                       # 179 days of our own history
    assert young['status'] == 'unobservable' and young['building_history']
    assert 'under 180 days' in young['signals'][0]['basis']
    old = L.derive(history, date(2026, 11, 28))                         # 180 days
    s = old['signals'][0]
    assert (s['state'], s['last_activity'], old['status']) == ('bounded', '2026-06-01', 'slow')
    assert 'lower bound' in s['basis'] and not old['building_history']


def test_a_fingerprint_change_is_an_update_dated_at_probe_time():
    history = [rec('2026-06-01', 'leaderboard', value='a' * 64), rec('2026-10-05', 'leaderboard', value='b' * 64),
               rec('2026-11-16', 'leaderboard', value='b' * 64)]
    d = L.derive(history, TODAY)
    assert (d['status'], d['last_activity']) == ('actively-maintained', '2026-10-05')
    assert d['signals'][0]['dated_by']['observed_at'].startswith('2026-10-05')


# ---- the derivation (02 S8's table) -----------------------------------------------------------------------------

@pytest.mark.parametrize('days,status', [
    (0, 'actively-maintained'), (179, 'actively-maintained'), (180, 'slow'), (364, 'slow'),
    (365, 'stale'), (729, 'stale'), (730, 'abandoned'), (1500, 'abandoned')])
def test_02_s8s_table_at_its_boundaries(days, status):
    pushed = (TODAY - timedelta(days=days)).isoformat()
    assert L.derive([rec('2026-11-23', value=pushed)], TODAY)['status'] == status


def test_the_most_recent_signal_decides():
    records = [rec('2026-11-23', value='2023-01-01'), rec('2026-11-23', 'hf-dataset', value='2026-09-30'),
               rec('2026-11-23', 'homepage', status=200)]
    d = L.derive(records, TODAY)
    assert (d['status'], d['last_activity']) == ('actively-maintained', '2026-09-30')


def test_two_confirmed_indicators_are_abandoned_whatever_the_dates_say():
    archived = rec('2026-11-23', value='2026-11-01', detail={'archived': True})
    home = [rec(d, 'homepage', outcome='dead', failures=n, status=404)
            for n, d in enumerate(('2026-11-09', '2026-11-16', '2026-11-23'), start=1)]
    d = L.derive([archived] + home, TODAY)
    assert d['status'] == 'abandoned' and d['indicators'] == ['homepage dead', 'repository archived or removed']
    assert L.derive([archived] + home[:2], TODAY)['status'] == 'actively-maintained'   # two 404s confirm nothing


def test_no_signal_or_only_blocked_ones_is_unobservable_never_abandoned():
    assert L.derive([], TODAY)['status'] == 'unobservable'
    only_home = L.derive([rec('2026-11-23', 'homepage', status=200)], TODAY)
    assert (only_home['status'], only_home['basis']) == ('unobservable', 'no dated signal we can poll')
    p = prober({URL['git-host']: L.Reply(403, [('X-RateLimit-Remaining', '4000')], b'{"message": "blocked"}')})
    blocked = [rec('2026-10-01', value='2026-09-01')]
    for day in ('2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23'):
        blocked.append(L.probe(target(), p, blocked, datetime.fromisoformat(day + 'T12:00:00+00:00')))
    d = L.derive(blocked, TODAY)
    assert d['status'] == 'unobservable' and d['basis'] == 'every probe blocked or refused'
    assert [(r['outcome'], r['consecutive_failures']) for r in blocked[1:]] == [('blocked', 0)] * 4   # never death


def test_a_move_toward_abandoned_is_withheld_30_days_and_a_move_away_publishes_at_once():
    first = [rec('2026-11-23', value='2023-01-01')]
    p = L.published(first, TODAY)
    assert (p['computed'], p['published']) == ('abandoned', 'unobservable')
    assert p['withheld'] == {'status': 'abandoned', 'computed_on': '2026-11-23', 'publishes_from': '2026-12-23',
                             'why': '02 S8: a transition toward abandoned is withheld for 30 days'}
    held = [rec('2026-10-19', value='2023-01-01')] + first
    assert L.published(held, TODAY)['published'] == 'abandoned'       # it was already abandoned 30 days before
    back = held + [rec('2026-11-24', value='2026-11-24')]
    p = L.published(back, date(2026, 11, 24))
    assert (p['published'], p['withheld']) == ('actively-maintained', None)


@pytest.mark.parametrize('status,days_since,due', [
    ('actively-maintained', 7, True), ('slow', 7, True), ('stale', 27, False), ('stale', 28, True),
    ('abandoned', 90, False), ('abandoned', 91, True), ('unobservable', 90, False)])
def test_02_s8s_cadence(status, days_since, due):
    records = [rec((TODAY - timedelta(days=days_since)).isoformat())]
    assert L.due({'status': status, 'building_history': False, 'unprobed': 0}, records, TODAY) is due


def test_a_benchmark_building_its_fingerprint_history_is_probed_weekly_and_a_new_one_at_once():
    records = [rec((TODAY - timedelta(days=14)).isoformat(), 'leaderboard', value='f' * 64)]
    assert L.due({'status': 'unobservable', 'building_history': True, 'unprobed': 0}, records, TODAY)
    assert L.due({'status': 'unobservable', 'building_history': False, 'unprobed': 0}, [], TODAY)
    assert L.due({'status': 'abandoned', 'building_history': False, 'unprobed': 1}, records, TODAY)


def test_the_week_file_is_the_iso_week_across_a_year_boundary():
    assert [L.week_of(date.fromisoformat(d)) for d in ('2026-11-23', '2026-12-31', '2027-01-03', '2027-01-04')] == \
        ['2026-W48', '2026-W53', '2026-W53', '2027-W01']
    assert L.week_file(TODAY) == 'metrics/liveness/2026-W48.jsonl'


# ---- coldness and the proposal ----------------------------------------------------------------------------------

def cold_records(last='2025-11-23'):
    return [rec('2026-11-23', value=last), rec('2026-11-23', 'hf-dataset', value='2024-05-20'),
            rec('2026-11-23', 'homepage', status=200)]


def propose(records, **record):
    d = L.published(records, TODAY)
    return L.proposal('b', 'data/benchmarks/code/b.yaml', dict({'lifecycle': 'active'}, **record), d, TODAY)


def test_twelve_calendar_months_cold_on_every_signal_is_the_threshold():
    p, why = propose(cold_records('2025-11-23'))
    assert p is not None and why == 'every one of 2 signal(s) cold for twelve months or more'
    assert (p['proposed_value'], p['plan_term'], p['field'], p['current_value']) == \
        ('dormant', 'dead', 'lifecycle', 'active')
    assert (p['status'], p['confirmations'], p['resolution']) == ('open', [], None)
    p, why = propose(cold_records('2025-11-24'))                   # one day short of twelve months
    assert p is None and why.startswith('active within twelve months: git-host 2025-11-24')


def test_a_live_homepage_is_not_maintenance_and_does_not_hold_back_the_proposal():
    p, _ = propose(cold_records())
    assert [e['signal_type'] for e in p['evidence']] == ['git-host', 'hf-dataset', 'homepage']
    assert p['evidence'][2]['state'] == 'live'


def test_one_unobservable_signal_holds_back_the_proposal():
    records = cold_records() + [rec('2026-11-23', 'leaderboard', outcome='blocked', status=403)]
    p, why = propose(records)
    assert p is None and why.startswith('not every signal is observable: leaderboard (probe blocked')


@pytest.mark.parametrize('record,why', [
    ({'lifecycle': 'dormant'}, 'lifecycle is already dormant'),
    ({'lifecycle': 'deprecated'}, 'lifecycle is already deprecated'),
    ({'maintenance_status_contested': True, 'contested_source': 'src-x', 'contested_statement_date': '2026-08-14'},
     'maintenance_status is contested (src-x, 2026-08-14)'),
])
def test_no_proposal_for_an_entry_already_classified_or_contested(record, why):
    p, got = propose(cold_records(), **record)
    assert p is None and got.startswith(why)


def test_no_signal_at_all_is_no_proposal():
    p, why = propose([])
    assert p is None and why == 'no maintenance signal to read'


# ---- the done-when, end to end over the fixture tree ------------------------------------------------------------

def test_twelve_cold_months_produce_a_linked_evidenced_proposal_and_nothing_is_reclassified(tree):
    data_before = digest(os.path.join(tree, 'data'))
    report = L.run(tree, fixture_prober(), now=lambda: NOW)
    assert data_before == digest(os.path.join(tree, 'data'))          # nothing reclassified, nothing touched
    with open(os.path.join(tree, 'data', 'benchmarks', 'code', 'bravo-cold.yaml'), encoding='utf-8') as f:
        assert 'lifecycle: active' in f.read()
    assert [p['benchmark'] for p in report['proposals']] == ['bravo-cold']
    path = os.path.join(tree, 'metrics', 'liveness', 'proposals', 'bravo-cold.json')
    with open(path, encoding='utf-8') as f:
        p = json.load(f)
    assert p['record'] == 'data/benchmarks/code/bravo-cold.yaml' and os.path.exists(os.path.join(tree, p['record']))
    assert p['maintenance_status']['computed'] == 'abandoned' and p['coldness']['last_activity'] == '2025-09-29'
    pages = {e['signal_type']: e['page'] for e in p['evidence']}
    assert pages == {'git-host': 'https://github.com/fixture-org/bravo-cold',
                     'hf-dataset': 'https://huggingface.co/datasets/fixture-org/bravo-cold',
                     'leaderboard': 'https://bravo.example.net/board', 'homepage': 'https://bravo.example.net/'}
    # Linked: every piece of evidence names the week file and the probe behind it, and that line is there.
    for e in p['evidence']:
        for ref in (e['latest_probe'], e['dated_by']):
            if ref is None:
                continue
            lines = [json.loads(x) for x in open(os.path.join(tree, *ref['file'].split('/')), encoding='utf-8')]
            assert any(all(x[k] == ref[k] for k in ('benchmark', 'signal_type', 'url', 'observed_at', 'value'))
                       for x in lines), ref
    git = next(e for e in p['evidence'] if e['signal_type'] == 'git-host')
    assert git['dated_by']['file'] == 'metrics/liveness/2025-W40.jsonl'      # the 200 that read it, not the 304
    assert git['latest_probe']['http_status'] == 304


def test_the_week_file_holds_one_line_per_signal_with_02_s8s_fields(tree):
    L.run(tree, fixture_prober(), now=lambda: NOW)
    lines = [json.loads(x) for x in open(os.path.join(tree, 'metrics', 'liveness', '2026-W48.jsonl'), encoding='utf-8')]
    assert len(lines) == 15 and all(set(EIGHT) <= set(x) and x['outcome'] in L.OUTCOMES for x in lines)
    assert {x['signal_type'] for x in lines} == set(L.SIGNAL_TYPES) - {'hf-space'}
    bravo_home = next(x for x in lines if x['benchmark'] == 'bravo-cold' and x['signal_type'] == 'homepage')
    assert (bravo_home['outcome'], bravo_home['consecutive_failures']) == ('dead', 4)


def test_statuses_over_the_fixture(tree):
    s = L.run(tree, fixture_prober(), now=lambda: NOW)['statuses']
    assert {b: (d['computed'], d['published']) for b, d in s.items()} == {
        'alpha-live': ('actively-maintained', 'actively-maintained'),
        'bravo-cold': ('abandoned', 'abandoned'),
        'charlie-blocked': ('unobservable', 'unobservable'),
        'delta-contested': ('abandoned', 'unobservable'),              # first observation: quarantined
        'echo-quiet': ('slow', 'slow'),
    }
    assert s['delta-contested']['contested'] and s['charlie-blocked']['basis'] == 'every probe blocked or refused'


def test_a_second_run_in_the_week_probes_nothing_and_a_proposal_is_never_rewritten(tree):
    L.run(tree, fixture_prober(), now=lambda: NOW)
    path = os.path.join(tree, 'metrics', 'liveness', 'proposals', 'bravo-cold.json')
    with open(path, encoding='utf-8') as f:
        p = json.load(f)
    p['status'], p['resolution'] = 'rejected', {'rationale': 'still in use (a test edit)'}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(p, f)
    week = os.path.join(tree, 'metrics', 'liveness', '2026-W48.jsonl')
    before = digest(os.path.join(tree, 'metrics'))
    again = fixture_prober()
    r = L.run(tree, again, now=lambda: NOW + timedelta(days=2))
    assert r['lines'] == [] and r['already_this_week'] == 15 and again.transport.requests == []
    assert r['already_proposed'] == ['bravo-cold'] and r['proposals'] == []
    assert digest(os.path.join(tree, 'metrics')) == before and os.path.exists(week)
    with pytest.raises(FileExistsError):
        L.write_proposal(tree, dict(p, status='open'))


def test_the_failure_case_nothing_under_data_can_be_written(tree, monkeypatch):
    with pytest.raises(PermissionError, match='never writes under data/'):
        L.guard(tree, os.path.join(tree, 'data', 'benchmarks', 'code', 'bravo-cold.yaml'))
    with pytest.raises(PermissionError):                              # a path that climbs back into data/
        L.write_proposal(tree, {'benchmark': '../../../data/benchmarks/code/bravo-cold'})
    assert not os.path.exists(os.path.join(tree, 'data', 'benchmarks', 'code', 'bravo-cold.json'))
    # And a whole run opens nothing under data/ for writing.
    import builtins
    real_open, data = builtins.open, os.path.normcase(os.path.join(tree, 'data'))
    writes = []

    def watching(file, mode='r', *a, **k):
        if any(c in mode for c in 'wax+') and os.path.normcase(os.path.abspath(str(file))).startswith(data):
            writes.append(file)
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, 'open', watching)
    L.run(tree, fixture_prober(), now=lambda: NOW)
    assert writes == []


def test_a_dry_run_writes_nothing(tree):
    before = digest(tree)
    report = L.run(tree, fixture_prober(), now=lambda: NOW, dry_run=True)
    assert digest(tree) == before and report['proposals'] and report['written'] == []


def test_the_fixture_dry_run_from_the_command_line(capsys):
    before = digest(os.path.join(FIX, 'root'))
    code = L.main(['--dry-run', '--today', '2026-11-23', '--root', os.path.join(FIX, 'root'),
                   '--fixture', os.path.join(FIX, 'http')])
    out = capsys.readouterr().out
    assert code == 0 and digest(os.path.join(FIX, 'root')) == before
    assert 'proposals: 1 new, 0 already open' in out and 'bravo-cold.json: lifecycle active -> dormant' in out
    assert 'unobservable (computed abandoned, withheld to 2026-12-23)' in out and 'dry run: nothing written' in out


def test_a_replaced_url_is_no_longer_one_of_the_benchmarks_signals(tree):
    # bravo-cold's board moves: the old board's year of unchanged fingerprints stays in metrics/ but stops counting,
    # and the new board, never observed, holds the proposal back.
    path = os.path.join(tree, 'data', 'benchmarks', 'code', 'bravo-cold.yaml')
    with open(path, encoding='utf-8') as f:
        text = f.read()
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text.replace('https://bravo.example.net/board', 'https://bravo.example.net/board-v2'))
    r = L.run(tree, None, now=lambda: NOW, derive_only=True, dry_run=True)
    urls = {s['url'] for s in r['statuses']['bravo-cold']['signals']}
    assert 'https://bravo.example.net/board' not in urls
    assert r['not_proposed']['bravo-cold'].startswith('not every signal is observable')


def test_derive_only_sends_nothing(tree):
    r = L.run(tree, None, now=lambda: NOW, derive_only=True, dry_run=True)
    assert r['lines'] == [] and r['statuses']['bravo-cold']['computed'] == 'abandoned'


def test_the_fixture_history_holds_the_fingerprint_of_the_fixture_board():
    with open(os.path.join(FIX, 'http', 'bravo-board.html'), 'rb') as f:
        value, _ = L.fingerprint(f.read(), 'text/html')
    history = L.load_history(os.path.join(FIX, 'root'))
    assert {r['value'] for r in history if r['signal_type'] == 'leaderboard'} == {value}


# ---- politeness and credentials ---------------------------------------------------------------------------------

def test_the_user_agent_is_the_policy_files():
    assert L.USER_AGENT == P.Policy.load().user_agent


class FakeResponse:
    def __init__(self, status=200, body=b'{}', headers=()):
        self.status, self._body, self.headers = status, body, FakeHeaders(headers)

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeHeaders(dict):
    def items(self):
        return list(super().items())


def test_the_network_transport_sends_the_user_agent_and_a_token_only_to_its_own_host(monkeypatch):
    sent = []

    def fake_open(self, req, timeout=None):
        sent.append((req.full_url, dict(req.header_items())))
        return FakeResponse()
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', fake_open)
    monkeypatch.setenv('GH_API_TOKEN', 'tok-gh-test')
    monkeypatch.setenv('HF_TOKEN', 'tok-hf-test')
    t = L.NetworkTransport(gate(), L.tokens_from_env())
    for url in ('https://api.github.com/repos/o/r', 'https://huggingface.co/api/datasets/o/d',
                'https://board.example.org/lb'):
        t.get(url, {})
    auth = {u: h.get('Authorization') for u, h in sent}
    assert auth == {'https://api.github.com/repos/o/r': 'Bearer tok-gh-test',
                    'https://huggingface.co/api/datasets/o/d': 'Bearer tok-hf-test',
                    'https://board.example.org/lb': None}
    assert all(h['User-agent'] == P.Policy.load().user_agent for _, h in sent)


def test_tokens_come_from_the_environment_only_and_no_credential_store_is_read():
    assert L.tokens_from_env() == {}
    with open(L.__file__, encoding='utf-8') as f:
        src = f.read()
    for name in ('keyring', 'win32cred', 'CredRead', 'cmdkey', 'wincred'):
        assert name not in src


def test_the_network_transport_follows_no_redirect_and_refuses_the_forbidden_without_a_socket():
    t = L.NetworkTransport(gate())
    assert any(isinstance(h, L._NoRedirect) for h in t._opener.handlers)
    with pytest.raises(P.Forbidden):
        t.get('https://epoch.ai/frontiermath/tiers-1-4/benchmark-problems', {})


def test_robots_txt_is_honoured_and_a_disallowed_board_is_refused_not_dead():
    robots = {'https://board.example.org/robots.txt': (200, 'User-agent: *\nDisallow: /lb\n')}
    p = prober({}, robots=lambda url, ua: robots.get(url, (404, '')))
    r = L.probe(target('leaderboard'), p, [], NOW)
    assert (r['outcome'], r['probe_blocked'], r['consecutive_failures']) == ('refused', True, 0)
    assert 'RobotsDisallowed' in r['note'] and p.transport.asked == []


def test_a_no_collect_host_is_refused_before_anything_is_sent():
    doc = {'user_agent': L.USER_AGENT, 'robots_token': 'UAIBI', 'hosts': {}, 'forbidden': [],
           'no_collect': [{'host': 'example.org'}]}
    asked = []
    p = prober({}, doc=doc, robots=lambda url, ua: asked.append(url) or (404, ''))
    r = L.probe(target('homepage'), p, [], NOW)
    assert r['outcome'] == 'refused' and 'NoCollect' in r['note'] and asked == [] and p.transport.asked == []


def test_one_request_at_a_time_per_host_at_the_policys_pace():
    clock = Clock()
    answers = {URL['leaderboard']: L.Reply(200, [], html()), 'https://board.example.org/b': L.Reply(200, [], html()),
               URL['git-host']: L.Reply(200, [], repo()), 'https://api.github.com/repos/o/s': L.Reply(200, [], repo())}
    p = prober(answers, clock=clock)
    for t in (target('leaderboard'), target('leaderboard', url='https://board.example.org/b')):
        L.probe(t, p, [], NOW)
    assert clock.slept == [5.0, 5.0]                     # an unlisted host: robots.txt, then one every 5 s
    for t in (target(), target(url='https://api.github.com/repos/o/s')):
        L.probe(t, p, [], NOW)
    assert clock.slept == [5.0, 5.0, 1.0, 1.0]           # api.github.com: ingest/policy.yaml's one a second
    assert p.gate.policy.hosts['board.example.org'].basis == L.PROBE_BASIS
    assert 'board.example.org' not in P.Policy.load().hosts       # the widening never leaks into the shared policy


def test_a_zero_budget_host_is_refused_and_a_spent_budget_is_left_for_the_next_run(monkeypatch):
    r = L.probe(target('leaderboard', url='https://artificialanalysis.ai/leaderboards/models'), prober({}), [], NOW)
    assert r['outcome'] == 'refused' and 'BudgetExhausted' in r['note']     # 07 S10: "Zero. Link out only"
    monkeypatch.setattr(L, 'PROBE_HOST', (100.0, 1, 2))
    p = prober({URL['leaderboard']: L.Reply(200, [], html())})
    L.probe(target('leaderboard'), p, [], NOW)                               # robots.txt and this: two of two
    with pytest.raises(L.Unsent, match='budget for board.example.org is spent'):
        L.probe(target('leaderboard', url='https://board.example.org/other'), p, [], NOW)


def test_every_redirect_hop_is_admitted_and_a_hop_to_a_no_collect_host_is_refused():
    doc = {'user_agent': L.USER_AGENT, 'robots_token': 'UAIBI', 'hosts': {}, 'forbidden': [],
           'no_collect': [{'host': 'elsewhere.example.net'}]}
    p = prober({URL['leaderboard']: L.Reply(302, [('Location', 'https://elsewhere.example.net/lb')], b'')}, doc=doc)
    r = L.probe(target('leaderboard'), p, [], NOW)
    assert r['outcome'] == 'refused' and 'NoCollect' in r['note']
    assert [u for u, _ in p.transport.asked] == [URL['leaderboard']]


def test_a_spent_api_rate_limit_is_a_soft_fail_that_records_nothing_and_leaves_the_host(tree):
    spent = L.Reply(403, [('X-RateLimit-Remaining', '0')], b'{"message": "API rate limit exceeded"}')
    answers = {'https://api.github.com/repos/fixture-org/%s' % b: spent
               for b in ('alpha-live', 'bravo-cold', 'delta-contested', 'echo-quiet')}
    t = L.FixtureProbeTransport(os.path.join(FIX, 'http'))
    real = t.get

    def get(url, headers):
        return answers[url] if url in answers else real(url, headers)
    t.get = get
    clock = Clock()
    p = L.Prober(t, L.ProbeGate(P.Policy.load(), robots=t.robots, clock=clock, sleep=clock.sleep))
    r = L.run(tree, p, now=lambda: NOW, dry_run=True)
    assert len(r['soft_fails']) == 1 and 'rate limit is spent' in r['soft_fails'][0]
    assert not any(x['signal_type'] == 'git-host' for x in r['lines'])
    asked = [u for u, what in p.gate.log if what == 'sent' and u.startswith('https://api.github.com/repos/')]
    assert asked == ['https://api.github.com/repos/fixture-org/alpha-live']   # the host is left after the first


def test_a_refused_github_token_is_a_soft_fail_too():
    with pytest.raises(L.Unsent, match='GH_API_TOKEN was refused'):
        L.probe(target(), prober({URL['git-host']: L.Reply(401, [], b'')}), [], NOW)
