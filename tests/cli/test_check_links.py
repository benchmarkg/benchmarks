"""Tests for `bench check-links` (P0-S5-T08; tools/links.py, tools/archive.py; 05 S3, 06 S7).

The verify: "a fixture with a dead link exits non-zero, an unarchived non-DOI source fails
--archive-missing, a DOI source does not, and a second run inside the 30-day window issues no
capture request". The command runs against a corpus written into tmp_path, with the resolver and
the Wayback client replaced by fakes that count their requests, so no test leaves the machine; the
real Resolver is tested against an http.server on 127.0.0.1.
"""
import http.server
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import archive, cli, links  # noqa: E402
from tools.links import Response  # noqa: E402

runner = CliRunner()
NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
OK = Response(200, '')


class FakeResolver:
    """url -> Response; anything unlisted is live. Counts every request."""

    def __init__(self, answers=None):
        self.answers, self.requests, self.asked = answers or {}, 0, []

    def get(self, url):
        self.requests += 1
        self.asked.append(url)
        r = self.answers.get(url, OK)  # get-default: an unlisted URL is a live one
        return Response(r.status, r.final or url, r.redirects, r.error)


class FakeWayback:
    def __init__(self, can_capture=True, cdx=None, submit=None):
        self.can_capture, self.cdx, self.submit_result = can_capture, cdx or {}, submit or {}
        self.submitted, self.looked_up = [], []

    def latest(self, url):
        self.looked_up.append(url)
        ts = self.cdx.get(url)
        return (ts, url, 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA') if ts else None

    def submit(self, url):
        self.submitted.append(url)
        return self.submit_result.get(url, 'job-%d' % len(self.submitted))  # get-default: an unscripted capture is accepted


def write(root, rel, record):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        YAML().dump(record, fh)
    return path


def source(ident, url, doi=None, archive_url=None):
    return {'id': ident, 'type': 'documentation', 'url': url, 'doi': doi, 'archive_url': archive_url,
            'archive_status': 'ok' if archive_url else ('not-required' if doi else 'pending'),
            'licence_class': 'permissive-attribution', 'licence_checked_on': '2026-09-24', 'provenance': 'primary'}


@pytest.fixture
def corpus(tmp_path):
    """A benchmark whose links all resolve, and one DOI Source (exempt from archiving)."""
    root = tmp_path / 'root'
    write(root, 'data/benchmarks/code/link-bench.yaml', {
        'id': 'link-bench', 'homepage': 'https://bench.example.org/',
        'repository': 'https://github.com/example/link-bench',
        'curation': {'sources': ['src-link-paper']}})
    write(root, 'data/sources/2026/src-link-paper.yaml',
          source('src-link-paper', 'https://doi.org/10.1234/link', doi='10.1234/link'))
    return root


def go(root, resolver=None, wayback=None, now=NOW, cache=True, **kw):
    resolver, wayback = resolver or FakeResolver(), wayback or FakeWayback()
    report = links.run(str(root), resolver=resolver, wayback=wayback, now=now,
                       cache_path=str(root.parent / 'links.json') if cache else False, **kw)
    return report, resolver, wayback


def cls(report, url):
    [row] = [r for r in report['links'] if r['url'] == url]
    return row['class']


@pytest.fixture
def cli_env(corpus, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', str(corpus))
    monkeypatch.setattr(links, 'CACHE', str(corpus.parent / 'links.json'))
    fakes = {'resolver': FakeResolver(), 'wayback': FakeWayback()}
    monkeypatch.setattr(links, 'default_resolver', lambda timeout: fakes['resolver'])
    monkeypatch.setattr(links, 'default_wayback', lambda: fakes['wayback'])
    return corpus, fakes


# ---- the verify ---------------------------------------------------------------------------------

def test_verify_a_dead_link_exits_non_zero(cli_env):
    root, fakes = cli_env
    fakes['resolver'].answers['https://bench.example.org/'] = Response(404, '')
    res = runner.invoke(cli.app, ['check-links'])
    assert res.exit_code == 1, res.output
    assert 'dead' in res.output and 'https://bench.example.org/' in res.output and 'HTTP 404' in res.output


def test_verify_an_unarchived_non_doi_source_fails_archive_missing(cli_env):
    root, fakes = cli_env
    write(root, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    assert runner.invoke(cli.app, ['check-links']).exit_code == 0          # no dead link: fine without the flag
    res = runner.invoke(cli.app, ['check-links', '--archive-missing'])
    assert res.exit_code == 1, res.output
    assert 'unarchived' in res.output and 'src-link-page.yaml' in res.output and '-> requested' in res.output


def test_verify_a_doi_source_does_not_fail_archive_missing(cli_env):
    root, fakes = cli_env
    res = runner.invoke(cli.app, ['check-links', '--archive-missing'])
    assert res.exit_code == 0, res.output
    assert fakes['wayback'].submitted == [] and fakes['wayback'].looked_up == []
    report = json.loads(runner.invoke(cli.app, ['check-links', '--archive-missing', '--format', 'json']).output)
    assert [(a['id'], a['outcome'], a['unarchived']) for a in report['archive']] == [('src-link-paper', 'doi-exempt', False)]


def test_verify_a_second_run_inside_the_window_issues_no_capture_request(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    first, r1, wb = go(corpus, archive_missing=True)
    assert wb.submitted == ['https://bench.example.org/about'] and first['exit_code'] == 1
    second, r2, wb2 = go(corpus, archive_missing=True, now=NOW + timedelta(days=29))
    assert wb2.submitted == [] and wb2.looked_up == []                    # no capture, no CDX lookup
    assert r2.requests == 0 and second['from_cache'] == len({r['url'] for r in second['links']})
    [a] = [a for a in second['archive'] if a['id'] == 'src-link-page']
    assert a['outcome'] == 'requested' and a['cached'] is True and second['exit_code'] == 1   # still unarchived
    third, _, wb3 = go(corpus, archive_missing=True, now=NOW + timedelta(days=31))
    assert wb3.submitted == ['https://bench.example.org/about']           # the window has passed


# ---- classification -----------------------------------------------------------------------------

@pytest.mark.parametrize('url, response, expect', [
    ('https://a.example.org/', Response(200, ''), 'live'),
    ('https://a.example.org/', Response(206, ''), 'live'),                 # the ranged GET's own answer
    ('http://a.example.org/x', Response(200, 'https://www.a.example.org/x', ['http://a.example.org/x']), 'redirected'),
    ('https://example.org/x', Response(200, 'https://docs.example.org/x', ['https://example.org/x']), 'redirected'),
    ('https://doi.org/10.1/x', Response(200, 'https://publisher.example.com/x', ['https://doi.org/10.1/x']), 'redirected'),
    ('https://a.example.org/', Response(200, 'https://parked.example.net/', ['https://a.example.org/']), 'dead'),
    ('https://a.example.org/', Response(404, ''), 'dead'),
    ('https://a.example.org/', Response(503, ''), 'dead'),
    ('https://a.example.org/', Response(301, 'https://a.example.org/loop', [], 'more than 10 redirects'), 'dead'),
    ('https://a.example.org/', Response(None, '', [], 'Name or service not known'), 'dead'),
    ('https://a.example.org/', Response(429, ''), 'unknown'),
])
def test_classify(url, response, expect):
    assert links.classify(url, response)[0] == expect


def test_a_dead_link_with_a_capture_beside_it_is_archived_only_and_passes(corpus):
    write(corpus, 'data/sources/2026/src-gone.yaml',
          source('src-gone', 'https://gone.example.net/page', archive_url='https://web.archive.org/web/2026/x'))
    report, resolver, wb = go(corpus, FakeResolver({'https://gone.example.net/page': Response(410, '')}))
    assert cls(report, 'https://gone.example.net/page') == 'archived-only'
    assert report['exit_code'] == 0 and wb.looked_up == []                 # the record's own capture sufficed


def test_a_dead_link_cdx_holds_a_capture_of_is_archived_only(corpus):
    write(corpus, 'data/benchmarks/code/other.yaml', {'id': 'other', 'homepage': 'https://gone.example.net/'})
    wb = FakeWayback(cdx={'https://gone.example.net/': '20240101000000'})
    report, _, _ = go(corpus, FakeResolver({'https://gone.example.net/': Response(404, '')}), wb)
    assert cls(report, 'https://gone.example.net/') == 'archived-only' and report['exit_code'] == 0


def test_a_429_is_unknown_and_does_not_fail(corpus):
    report, _, _ = go(corpus, FakeResolver({'https://bench.example.org/': Response(429, '')}))
    assert cls(report, 'https://bench.example.org/') == 'unknown' and report['exit_code'] == 0


# ---- what is requested --------------------------------------------------------------------------

def test_wayback_urls_are_never_requested_and_each_url_once(corpus):
    write(corpus, 'data/sources/2026/src-a.yaml',
          source('src-a', 'https://bench.example.org/', archive_url='https://web.archive.org/web/2026/https://bench.example.org/'))
    write(corpus, 'data/benchmarks/code/other.yaml', {
        'id': 'other', 'homepage': 'https://bench.example.org/',
        'notes': ['see https://bench.example.org/ for more', 'https://web.archive.org/web/2025/x']})
    report, resolver, _ = go(corpus)
    assert sorted(resolver.asked) == ['https://bench.example.org/', 'https://doi.org/10.1234/link',
                                      'https://github.com/example/link-bench']
    assert not any('web.archive.org' in r['url'] for r in report['links'])
    assert sum(1 for r in report['links'] if r['url'] == 'https://bench.example.org/') == 3     # every citing location


def test_a_dead_link_is_not_cached(corpus):
    dead = FakeResolver({'https://bench.example.org/': Response(404, '')})
    go(corpus, dead)
    report, again, _ = go(corpus, now=NOW + timedelta(days=1))
    assert again.asked == ['https://bench.example.org/'] and cls(report, 'https://bench.example.org/') == 'live'


def test_changed_only_checks_only_the_changed_files(corpus, monkeypatch):
    from tools.validate import tiers
    monkeypatch.setattr(tiers, 'changed_files', lambda root: {'data/sources/2026/src-link-paper.yaml'})
    report, resolver, _ = go(corpus, changed_only=True)
    assert resolver.asked == ['https://doi.org/10.1234/link'] and report['files'] == 1


def test_check_links_never_writes_data(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    before = {p: p.read_bytes() for p in corpus.rglob('*.yaml')}
    go(corpus, FakeResolver({'https://bench.example.org/': Response(404, '')}),
       FakeWayback(cdx={'https://bench.example.org/about': '20260920000000'}), archive_missing=True)
    assert {p: p.read_bytes() for p in corpus.rglob('*.yaml')} == before


# ---- the archival call --------------------------------------------------------------------------

def test_a_fresh_cdx_capture_is_reported_and_nothing_is_submitted(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    wb = FakeWayback(cdx={'https://bench.example.org/about': '20260920000000'})
    report, _, _ = go(corpus, wayback=wb, archive_missing=True)
    [a] = [a for a in report['archive'] if a['id'] == 'src-link-page']
    assert a['outcome'] == 'exists' and wb.submitted == []
    assert a['archive_url'] == 'https://web.archive.org/web/20260920000000/https://bench.example.org/about'
    assert report['exit_code'] == 1                 # found, but not yet in the record


def test_an_old_cdx_capture_still_gets_a_capture_request(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    wb = FakeWayback(cdx={'https://bench.example.org/about': '20250101000000'})
    go(corpus, wayback=wb, archive_missing=True)
    assert wb.submitted == ['https://bench.example.org/about']


def test_without_credentials_nothing_is_submitted_or_cached(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    report, _, wb = go(corpus, wayback=FakeWayback(can_capture=False), archive_missing=True)
    assert [a['outcome'] for a in report['archive'] if a['unarchived']] == ['no-credentials'] and wb.submitted == []
    _, _, wb2 = go(corpus, wayback=FakeWayback(can_capture=False), archive_missing=True)
    assert wb2.looked_up == ['https://bench.example.org/about']            # asked again next run


def test_a_refused_capture_is_cached_but_a_network_error_is_not(corpus):
    write(corpus, 'data/sources/2026/src-link-page.yaml', source('src-link-page', 'https://bench.example.org/about'))
    url = 'https://bench.example.org/about'
    go(corpus, wayback=FakeWayback(submit={url: ('error', 'error:network', 'reset')}), archive_missing=True)
    _, _, wb = go(corpus, wayback=FakeWayback(submit={url: ('error', 'error:blocked-url', 'robots')}), archive_missing=True)
    assert wb.submitted == [url]
    report, _, wb = go(corpus, archive_missing=True)
    assert wb.submitted == [] and [a['outcome'] for a in report['archive'] if a['unarchived']] == ['refused']


def test_a_stopped_wayback_leaves_the_rest_unattempted(corpus):
    for i in range(3):
        write(corpus, 'data/sources/2026/src-p%d.yaml' % i, source('src-p%d' % i, 'https://bench.example.org/%d' % i))

    class Refusing(FakeWayback):
        def submit(self, url):
            self.submitted.append(url)
            raise archive.StopRun('SPN2 returned 429')
    report, _, wb = go(corpus, wayback=Refusing(), archive_missing=True)
    assert len(wb.submitted) == 1
    assert [a['outcome'] for a in report['archive'] if a['unarchived']] == ['not-attempted'] * 3
    assert report['exit_code'] == 1


# ---- the real resolver, against a local server -------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    seen = []
    flaky = {'n': 0}

    def log_message(self, *a):
        pass

    def _reply(self, code, headers=None, body=b'ok'):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        Handler.seen.append(('HEAD', self.path, None))
        self._reply(405)

    def do_GET(self):
        Handler.seen.append(('GET', self.path, self.headers.get('Range')))
        if self.path == '/ok':
            self._reply(206, {'Content-Range': 'bytes 0-1/2'})
        elif self.path == '/redirect':
            self._reply(301, {'Location': '/ok'})
        elif self.path == '/loop':
            self._reply(302, {'Location': '/loop'})
        elif self.path == '/flaky':
            Handler.flaky['n'] += 1
            self._reply(503 if Handler.flaky['n'] == 1 else 200)
        elif self.path == '/norange':
            self._reply(416 if self.headers.get('Range') else 200)
        else:
            self._reply(404)


@pytest.fixture(scope='module')
def server():
    httpd = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % httpd.server_address[1]
    httpd.shutdown()


@pytest.mark.parametrize('path, status, final, hops', [
    ('/ok', 206, '/ok', 0),
    ('/redirect', 206, '/ok', 1),
    ('/missing', 404, '/missing', 0),
    ('/flaky', 200, '/flaky', 0),                    # a 5xx is retried once
    ('/norange', 200, '/norange', 0),                # a 416 is asked again without the Range
])
def test_the_resolver_gets_with_a_range_and_follows_redirects_by_hand(server, path, status, final, hops):
    Handler.seen.clear()
    r = links.Resolver(timeout=5, spacing=0, retry_after=0).get(server + path)
    assert (r.status, r.final, len(r.redirects)) == (status, server + final, hops)
    assert all(method == 'GET' for method, _, _ in Handler.seen)             # never HEAD (06 S7.2)
    assert Handler.seen[0][2] == links.RANGE


def test_the_resolver_gives_up_on_a_redirect_loop(server):
    r = links.Resolver(timeout=5, spacing=0, retry_after=0).get(server + '/loop')
    assert r.status is None and 'more than 10 redirects' in r.error


def test_the_resolver_reports_a_refused_connection(server):
    import socket
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    r = links.Resolver(timeout=5, spacing=0, retry_after=0).get('http://127.0.0.1:%d/' % port)
    assert r.status is None and r.error and links.classify('http://127.0.0.1/', r)[0] == 'dead'
