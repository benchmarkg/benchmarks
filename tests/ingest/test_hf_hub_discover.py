"""Tests for the hf-hub adapter's discover() and fetch() (P5-S1-T03; 06 S3.2, 07 S1.1, S4.1).

The done_when: "A fixture run enumerates candidates, issues no network calls, and a second run with
unchanged ETags yields zero payloads." Every test that runs the adapter does so with the network
cut at the socket, so reaching for it is a failure rather than a slow pass. The failure cases the
verification names are asserted beside the passing ones: a second run that re-fetches, an edited
record that yields nothing, a network call in fixture mode.

The committed fixtures (tests/ingest/fixtures/hf-hub, P5-S1-T02) hold the first page of the Spaces
listing, the whole benchmark:official listing and one dataset detail (openai/gsm8k). Behaviour the
recorded set cannot show -- several pages, a cursor loop, an edited record, schema drift -- runs
against synthetic fixture directories in the same format, written into tmp_path.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from ingest.adapters import hf_hub  # noqa: E402
from ingest.adapters.hf_hub import (FixtureTransport, HfHub, RequestCache, load_state,  # noqa: E402
                                    new_state, next_link, run, save_state)

FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
SPACES = hf_hub.LISTINGS[0].url
DATASETS = hf_hub.LISTINGS[1].url
GSM8K = hf_hub.API + '/datasets/openai/gsm8k?full=true'
NOW = datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Cut the network at the socket and at urllib: any attempt fails the test outright."""
    def refuse(*a, **k):
        raise AssertionError('network call attempted: %r' % (a,))
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket.socket, 'connect_ex', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)


def fixture_meta(name):
    with open(os.path.join(FIX, name + '.headers.json'), encoding='utf-8') as f:
        return json.load(f)


def recorded_etag(name):
    return hf_hub.header(fixture_meta(name)['headers'], 'ETag')


class Harness:
    """A fixture directory, its state and its cache, run as many times as a test likes."""

    def __init__(self, tmp_path, fixture=FIX):
        self.fixture = fixture
        self.state = new_state()
        self.cache = RequestCache(str(tmp_path / 'cache'))

    def run(self, **kw):
        self.transport = FixtureTransport(self.fixture)
        self.adapter = HfHub(self.transport, self.cache, now=lambda: NOW)
        self.candidates = []
        real = self.adapter.discover

        def recording(state):
            for c in real(state):
                self.candidates.append(c)
                yield c
        self.adapter.discover = recording
        report, payloads = run(self.adapter, self.state, **kw)
        return report, payloads

    def sent(self, url):
        return [h for u, h in self.transport.requests if u == url]


def write_fixture(directory, name, url, body, etag, extra_headers=(), status=200):
    """One response in scripts/capture_hf_fixtures.py's format."""
    raw = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
    with open(os.path.join(directory, name), 'wb') as f:
        f.write(raw)
    headers = [['Content-Type', 'application/json; charset=utf-8'], ['Date', 'Thu, 24 Sep 2026 15:22:26 GMT'],
               ['ETag', etag], *[list(h) for h in extra_headers]]
    with open(os.path.join(directory, name + '.headers.json'), 'w', encoding='utf-8') as f:
        json.dump({'url': url, 'method': 'GET', 'status': status, 'headers': headers}, f)


def space(i, **kw):
    return dict({'_id': 'x%d' % i, 'id': 'org/space-%d' % i, 'likes': i, 'trendingScore': 0, 'private': False,
                 'tags': ['leaderboard'], 'createdAt': '2026-01-01T00:00:00.000Z'}, **kw)


def dataset(name, lm='2026-01-01T00:00:00.000Z', **kw):
    return dict({'_id': 'd', 'id': name, 'author': name.split('/')[0], 'tags': ['benchmark:official'],
                 'gated': False, 'disabled': False, 'downloads': 1, 'likes': 1, 'lastModified': lm}, **kw)


def synthetic(tmp_path, pages, datasets=(), details=()):
    """A fixture set whose Spaces listing is `pages` (lists of records), chained by Link headers."""
    d = tmp_path / 'fixture'
    d.mkdir(exist_ok=True)
    urls = [SPACES] + ['%s&cursor=c%d' % (SPACES, i) for i in range(1, len(pages))]
    for i, records in enumerate(pages):
        link = [('Link', '<%s>; rel="next"' % urls[i + 1])] if i + 1 < len(pages) else []
        write_fixture(str(d), 'spaces-%d.json' % i, urls[i], records, 'W/"s%d"' % i, link)
    write_fixture(str(d), 'datasets.json', DATASETS, list(datasets) or [dataset('org/ds')], 'W/"d"')
    for doc in details:
        write_fixture(str(d), 'detail-%s.json' % doc['id'].replace('/', '__'),
                      '%s/datasets/%s?full=true' % (hf_hub.API, doc['id']), doc, 'W/"%s"' % doc['id'])
    return str(d), urls


# ---- the done_when, on the committed fixtures ----------------------------------------------------

def test_a_fixture_run_enumerates_candidates_with_no_network(tmp_path):
    h = Harness(tmp_path)
    report, payloads = h.run()
    assert report['status'] == 'ok' and report['errors'] == []
    keys = [c.source_key for c in h.candidates]
    assert len(keys) == len(set(keys)) == 1047          # 1,000 Spaces on page 1 + 47 datasets
    assert sum(k.startswith('space:') for k in keys) == 1000
    assert sum(k.startswith('dataset:') for k in keys) == 47
    assert {c.kind for c in h.candidates} == {'leaderboard', 'benchmark'}
    c = next(c for c in h.candidates if c.source_key == 'dataset:openai/gsm8k')
    assert c.url == 'https://huggingface.co/datasets/openai/gsm8k'
    assert c.hint['detail_url'] == GSM8K
    assert c.hint['croissant_url'] == hf_hub.API + '/datasets/openai/gsm8k/croissant'
    # Every request went to the fixture transport; none reached a socket (the autouse guard).
    assert {u for u, _ in h.transport.requests} <= set(h.transport.index) | {
        c.hint['detail_url'] for c in h.candidates if c.kind == 'benchmark'} | {
        next_link(fixture_meta('spaces-leaderboard.json')['headers'], SPACES)}


def test_the_first_run_yields_a_payload_per_space_and_for_the_recorded_detail(tmp_path):
    h = Harness(tmp_path)
    report, payloads = h.run()
    assert len(payloads) == report['payloads_fetched'] == 1001
    gsm = [p for p in payloads if p.candidate.source_key == 'dataset:openai/gsm8k']
    assert len(gsm) == 1
    p = gsm[0]
    assert (p.http_status, p.etag, p.from_cache) == (200, recorded_etag('dataset-detail.json'), False)
    assert p.doc['id'] == 'openai/gsm8k' and p.body.startswith(b'{')
    assert p.fetched_at == datetime(2026, 9, 24, 15, 22, 28, tzinfo=timezone.utc)  # the response's Date
    assert p.sha256_normalised == hf_hub.sha256_normalised(p.doc)
    # The recorded set stops where the capture stopped: page 2 and 46 details, each reported.
    assert report['fixture_missing'] == 47
    assert any('fixture set ends after page 1' in n for n in report['notes'])


def test_a_second_run_with_unchanged_etags_yields_zero_payloads(tmp_path):
    h = Harness(tmp_path)
    h.run()
    report, payloads = h.run()
    assert payloads == [] and report['payloads_fetched'] == 0
    assert report['status'] == 'no-change'
    # Both listings were asked conditionally, with the ETag the first run stored, and got 304 ...
    assert h.sent(SPACES) == [{'If-None-Match': recorded_etag('spaces-leaderboard.json')}]
    assert h.sent(DATASETS) == [{'If-None-Match': recorded_etag('datasets-benchmark-official.json')}]
    assert report['http_codes'] == {'304': 2}
    # ... were still enumerated in full, from the request cache ...
    assert len(h.candidates) == 1047
    # ... and gsm8k's detail was never requested: its listing lastModified had not moved.
    assert h.sent(GSM8K) == [] and report['short_circuited'] == 1
    assert report['unchanged'] == 1000


def test_state_carries_the_etag_of_every_url_and_round_trips(tmp_path):
    h = Harness(tmp_path)
    h.run()
    path = str(tmp_path / 'state.json')
    save_state(path, h.state)
    back = load_state(path)
    assert back == json.loads(json.dumps(h.state))
    assert back['urls'][SPACES]['etag'] == recorded_etag('spaces-leaderboard.json')
    assert back['urls'][DATASETS]['etag'] == recorded_etag('datasets-benchmark-official.json')
    assert back['urls'][GSM8K]['etag'] == recorded_etag('dataset-detail.json')
    assert back['records']['dataset:openai/gsm8k']['lastModified'] == '2026-03-23T10:18:13.000Z'
    with open(path, encoding='utf-8') as f:
        text = f.read()
    assert '\n    "space:agent-memory-leaderboard/leaderboard": {"sha256": ' in text  # one line per record
    # A reloaded state drives the same zero-payload second run as the in-memory one.
    h.state = back
    assert h.run()[1] == []


def test_an_unchanged_detail_etag_is_a_304_and_no_payload(tmp_path):
    h = Harness(tmp_path)
    h.run()
    del h.state['records']['dataset:openai/gsm8k']['lastModified']  # defeat the short-circuit
    report, payloads = h.run()
    assert h.sent(GSM8K) == [{'If-None-Match': recorded_etag('dataset-detail.json')}]
    assert report['not_modified'] == 1 and payloads == []
    # The 304 re-learns the lastModified, so the run after that short-circuits again.
    report, _ = h.run()
    assert h.sent(GSM8K) == [] and report['short_circuited'] == 1


def test_an_evicted_cache_costs_one_unconditional_get_and_still_no_payloads(tmp_path):
    h = Harness(tmp_path)
    h.run()
    shutil.rmtree(tmp_path / 'cache')
    report, payloads = h.run()
    assert h.sent(SPACES) == [{}] and h.sent(DATASETS) == [{}]  # no If-None-Match without a body to fall back on
    assert report['http_codes'] == {'200': 2}
    assert len(h.candidates) == 1047 and payloads == []


def test_the_cli_fixture_run_twice(tmp_path, capsys):
    args = ['--fixture', FIX, '--state', str(tmp_path / 's.json'), '--cache', str(tmp_path / 'c')]
    assert hf_hub.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert hf_hub.main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert (first['candidates_seen'], first['payloads_fetched']) == (1047, 1001)
    assert (second['candidates_seen'], second['payloads_fetched'], second['status']) == (1047, 0, 'no-change')


def test_the_cli_never_defaults_to_the_committed_state_file(tmp_path, monkeypatch):
    saved = []
    monkeypatch.setattr(hf_hub, 'save_state', lambda path, state: saved.append(path))
    monkeypatch.setattr(hf_hub, 'print', lambda *a, **k: None, raising=False)
    hf_hub.main(['--fixture', FIX, '--cache', str(tmp_path / 'c')])
    assert saved and os.path.normcase(os.path.abspath(saved[0])) != os.path.normcase(hf_hub.STATE)
    assert os.path.normcase(os.path.join('ingest', 'raw')) in os.path.normcase(saved[0])


# ---- change detection: the negative controls -----------------------------------------------------

def edited_copy(tmp_path, edit, etag):
    """The committed fixtures, with the Spaces listing edited and given a new ETag."""
    d = tmp_path / 'edited'
    shutil.copytree(FIX, d)
    with open(d / 'spaces-leaderboard.json', 'rb') as f:
        spaces = json.loads(f.read().decode('utf-8'))
    edit(spaces)
    (d / 'spaces-leaderboard.json').write_bytes(json.dumps(spaces).encode('utf-8'))
    meta = json.loads((d / 'spaces-leaderboard.json.headers.json').read_text(encoding='utf-8'))
    meta['headers'] = [[k, etag if k == 'ETag' else v] for k, v in meta['headers']]
    (d / 'spaces-leaderboard.json.headers.json').write_text(json.dumps(meta), encoding='utf-8')
    return str(d)


def test_an_edited_record_behind_a_new_etag_is_exactly_one_payload(tmp_path):
    h = Harness(tmp_path)
    h.run()
    h.fixture = edited_copy(tmp_path, lambda s: s[5]['tags'].append('test:private'), 'W/"edited"')
    report, payloads = h.run()
    assert report['http_codes']['200'] == 1  # the new ETag missed; the listing came back in full
    assert [p.candidate.source_key for p in payloads] == ['space:' + h.candidates[5].hint['record']['id']]
    assert 'test:private' in payloads[0].doc['tags']


def test_a_counter_only_change_is_no_payload(tmp_path):
    def bump(spaces):
        for s in spaces:
            s['likes'] += 1
            s['trendingScore'] += 3
            s['_id'] = s['_id'][::-1]
    h = Harness(tmp_path)
    h.run()
    h.fixture = edited_copy(tmp_path, bump, 'W/"counters"')
    report, payloads = h.run()
    assert report['http_codes']['200'] == 1 and payloads == [] and report['unchanged'] == 1000


def test_a_moved_lastmodified_fetches_the_detail(tmp_path):
    ds = dataset('org/ds', lm='2026-01-01T00:00:00.000Z')
    fixture, _ = synthetic(tmp_path, [[space(1)]], datasets=[ds], details=[dict(ds, cardData={}, siblings=[])])
    h = Harness(tmp_path, fixture)
    h.run()
    detail = '%s/datasets/org/ds?full=true' % hf_hub.API
    assert len(h.sent(detail)) == 1
    h.run()
    assert h.sent(detail) == []  # unchanged: short-circuited
    ds2 = dict(ds, lastModified='2026-02-01T00:00:00.000Z', tags=['benchmark:official', 'license:mit'])
    write_fixture(fixture, 'datasets.json', DATASETS, [ds2], 'W/"d2"')
    write_fixture(fixture, 'detail-org__ds.json', detail, dict(ds2, cardData={}, siblings=[]), 'W/"ds2"')
    report, payloads = h.run()
    assert h.sent(detail) == [{'If-None-Match': 'W/"org/ds"'}]
    assert [p.candidate.source_key for p in payloads] == ['dataset:org/ds']
    assert payloads[0].etag == 'W/"ds2"'


# ---- pagination ---------------------------------------------------------------------------------

def test_pagination_follows_link_next_to_the_last_page(tmp_path):
    pages = [[space(1), space(2)], [space(3)], [space(4), space(5)]]
    fixture, urls = synthetic(tmp_path, pages)
    h = Harness(tmp_path, fixture)
    report, _ = h.run()
    assert [u for u, _ in h.transport.requests][:3] == urls
    assert [c.source_key for c in h.candidates if c.kind == 'leaderboard'] == [
        'space:org/space-%d' % i for i in range(1, 6)]
    assert report['status'] == 'ok' and report['notes'] == []
    # Every page's ETag is kept, and the second run asks each page conditionally.
    assert all(h.state['urls'][u]['etag'] == 'W/"s%d"' % i for i, u in enumerate(urls))
    h.run()
    assert [h.sent(u) for u in urls] == [[{'If-None-Match': 'W/"s%d"' % i}] for i in range(3)]


def test_a_cursor_loop_stops_and_says_so(tmp_path):
    fixture, urls = synthetic(tmp_path, [[space(1)], [space(2)]])
    write_fixture(fixture, 'spaces-1.json', urls[1], [space(2)], 'W/"s1"', [('Link', '<%s>; rel="next"' % urls[0])])
    h = Harness(tmp_path, fixture)
    report, _ = h.run()
    assert len(h.sent(urls[0])) == 1
    assert any('cursor loop' in n for n in report['notes'])


def test_an_entry_repeated_across_pages_is_one_candidate(tmp_path):
    fixture, _ = synthetic(tmp_path, [[space(1), space(2)], [space(2), space(3)]])
    h = Harness(tmp_path, fixture)
    report, _ = h.run()
    assert [c.source_key for c in h.candidates if c.kind == 'leaderboard'] == [
        'space:org/space-1', 'space:org/space-2', 'space:org/space-3']
    assert report['duplicates'] == 1


def test_the_captured_link_header_yields_the_cursor_url():
    nxt = next_link(fixture_meta('spaces-leaderboard.json')['headers'], SPACES)
    assert nxt.startswith(SPACES + '&cursor=') and len(nxt) > len(SPACES) + 20


@pytest.mark.parametrize('value, want', [
    ('<https://h/a?cursor=2>; rel="next"', 'https://h/a?cursor=2'),
    ('<https://h/a?cursor=2>; rel=next', 'https://h/a?cursor=2'),
    ('<https://h/p>; rel="prev", <https://h/n>; rel="next"', 'https://h/n'),
    ('<https://h/n>; title="a, b"; rel="next last"', 'https://h/n'),
    ('<?cursor=3>; rel="next"', 'https://huggingface.co/api/spaces?cursor=3'),   # relative to the request
    ('<https://h/p>; rel="prev"', None),
    ('<https://h/n>; rel="nextish"', None),
])
def test_next_link(value, want):
    assert next_link([('Link', value)], 'https://huggingface.co/api/spaces?filter=leaderboard') == want


def test_no_link_header_means_one_page():
    assert next_link([('ETag', 'W/"x"')], SPACES) is None


# ---- failing loudly ------------------------------------------------------------------------------

def test_a_zero_row_listing_is_schema_drift_not_an_empty_result(tmp_path):
    fixture, _ = synthetic(tmp_path, [[]])
    report, payloads = Harness(tmp_path, fixture).run()
    assert report['status'] == 'hard-fail' and payloads == []
    assert 'zero rows' in report['errors'][0]


def test_a_record_missing_a_mapped_key_is_schema_drift(tmp_path):
    broken = space(1)
    del broken['tags']
    fixture, _ = synthetic(tmp_path, [[space(0), broken]])
    report, _ = Harness(tmp_path, fixture).run()
    assert report['status'] == 'hard-fail' and "lacks ['tags']" in report['errors'][0]


def test_a_detail_naming_another_dataset_is_schema_drift(tmp_path):
    ds = dataset('org/ds')
    fixture, _ = synthetic(tmp_path, [[space(1)]], datasets=[ds])
    write_fixture(fixture, 'detail.json', '%s/datasets/org/ds?full=true' % hf_hub.API,
                  dict(ds, id='org/other', cardData={}, siblings=[]), 'W/"x"')
    report, _ = Harness(tmp_path, fixture).run()
    assert report['status'] == 'hard-fail' and 'org/other' in report['errors'][0]


def test_a_listing_the_fixture_set_does_not_hold_is_a_hard_fail(tmp_path):
    d = tmp_path / 'partial'
    shutil.copytree(FIX, d)
    os.remove(d / 'spaces-leaderboard.json.headers.json')
    report, _ = Harness(tmp_path, str(d)).run()
    assert report['status'] == 'hard-fail' and 'FixtureMiss' in report['errors'][0]


def test_no_network_mode_refuses_the_network(tmp_path):
    adapter = HfHub(hf_hub.NoNetwork(), RequestCache(str(tmp_path / 'c')), now=lambda: NOW)
    report, _ = run(adapter, new_state())
    assert report['status'] == 'hard-fail' and 'NetworkForbidden' in report['errors'][0]


def test_the_request_budget_caps_the_run(tmp_path):
    h = Harness(tmp_path)
    h.transport = FixtureTransport(FIX)
    adapter = HfHub(h.transport, h.cache, max_requests=2, now=lambda: NOW)
    report, _ = run(adapter, h.state)
    assert report['status'] == 'capped' and report['requests'] == 2


def test_a_failed_run_counts_consecutive_failures(tmp_path):
    fixture, _ = synthetic(tmp_path, [[]])
    h = Harness(tmp_path, fixture)
    h.run()
    h.run()
    assert h.state['consecutive_failures'] == 2 and h.state['last_success'] is None


# ---- the fixture transport and the network transport ---------------------------------------------

@pytest.mark.parametrize('inm, hit', [
    ('W/"b60-6K5f9WHhepevPVs8UV/vuZ0f66Q"', True),
    ('"b60-6K5f9WHhepevPVs8UV/vuZ0f66Q"', True),        # weak comparison: W/ ignored
    ('"x", W/"b60-6K5f9WHhepevPVs8UV/vuZ0f66Q"', True),
    ('*', True),
    ('W/"b60-something-else"', False),
])
def test_the_fixture_transport_honours_if_none_match(inm, hit):
    t = FixtureTransport(FIX)
    r = t.get(GSM8K, {'If-None-Match': inm})
    assert (r.status == 304) is hit and (r.body == b'') is hit


class FakeClock:
    def __init__(self):
        self.t = 100.0
        self.slept = []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


class FakeHTTP:
    def __init__(self, status, headers, body=b''):
        self.status, self.headers, self.body = status, Message(), body
        for k, v in headers:
            self.headers[k] = v

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_network_transport_paces_requests_and_reads_304s(monkeypatch):
    """No socket: urlopen is scripted. A 304 arrives as an HTTPError from urllib and must come back
    as a response; a RateLimit with nothing remaining holds the next request until the reset."""
    clock = FakeClock()
    sent = []
    script = [
        (200, [('RateLimit', '"api";r=10;t=100'), ('ETag', 'W/"a"')], b'[]'),
        (304, [('ETag', 'W/"a"')], b''),
        (200, [('RateLimit', '"api";r=0;t=42')], b'[]'),
        (200, [], b'[]'),
    ]

    def urlopen(req, timeout):
        sent.append((clock(), req.full_url, dict(req.header_items())))
        status, headers, body = script.pop(0)
        if status == 304:
            m = Message()
            for k, v in headers:
                m[k] = v
            raise urllib.error.HTTPError(req.full_url, 304, 'Not Modified', m, None)
        return FakeHTTP(status, headers, body)

    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    t = hf_hub.NetworkTransport(token='hf_x', clock=clock, wall=lambda: 1_790_000_000.0, sleep=clock.sleep)
    assert t.get(SPACES, {}).status == 200
    r = t.get(SPACES, {'If-None-Match': 'W/"a"'})
    assert (r.status, r.body) == (304, b'')
    t.get(DATASETS, {})
    t.get(DATASETS, {})
    times = [s[0] for s in sent]
    assert [b - a for a, b in zip(times, times[1:])] == [1.0, 1.0, 42.0]  # 1 req/s, then the reset
    assert sent[1][2]['If-none-match'] == 'W/"a"'
    assert sent[0][2]['Authorization'] == 'Bearer hf_x'
    assert sent[0][2]['User-agent'] == hf_hub.USER_AGENT


def test_the_network_transport_never_retries_a_403(monkeypatch):
    calls = []

    def urlopen(req, timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 403, 'Forbidden', Message(), None)

    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    clock = FakeClock()
    adapter = HfHub(hf_hub.NetworkTransport(clock=clock, sleep=clock.sleep), RequestCache('unused'), now=lambda: NOW)
    report, _ = run(adapter, new_state())
    assert len(calls) == 1 and report['status'] == 'soft-fail' and 'HTTP 403' in report['errors'][0]


def test_runs_as_a_file_without_shadowing_the_stdlib():
    env = dict(os.environ, PYTHONPATH='')
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'ingest', 'adapters', 'hf_hub.py'), '--help'],
                         capture_output=True, text=True, env=env, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    assert '--fixture' in out.stdout
