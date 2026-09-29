"""The link-rot re-check (P5-S8-T01; 06 S7.2): tools/check_links.py.

DONE WHEN: "All four outcomes are exercised by fixtures including an SPA shell and a soft-404, and a
silently rewritten leaderboard is flagged as a data-integrity event rather than a refresh."

The pages are tests/fixtures/linkrot/*.html. The fetch is tools/links.py's own Resolver.get with only
its one-request primitive `_once` replaced, so redirects, the Range fallback, the retry and the
whole-body re-fetch are the code that runs in production; nothing touches the network.
"""
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.source import Source  # noqa: E402
from tools import check_links as C  # noqa: E402
from tools import links  # noqa: E402
from tools.fmt import emitter  # noqa: E402

PAGES = os.path.join(ROOT, 'tests', 'fixtures', 'linkrot')
NOW = datetime(2026, 9, 29, 8, 43, tzinfo=timezone.utc)
URL = 'https://bench.example.org/leaderboard'
HTML = 'text/html; charset=utf-8'


def page(name: str) -> bytes:
    with open(os.path.join(PAGES, name), 'rb') as fh:
        return fh.read()


class Resolver(links.Resolver):
    """links.Resolver with `_once` answered from a table: url -> (status, body, content type, location)."""

    def __init__(self, table):
        super().__init__(timeout=1, spacing=0, retry_after=0)
        self.table, self.seen = table, []

    def _once(self, url, ranged=True, limit=32768):
        self.requests += 1
        self.seen.append((url, ranged))
        status, body, ctype, location = self.table[url]
        if status is None:
            return links._Got(None, None, 'Name or service not known')
        if body is None:
            return links._Got(status, location, None)
        return links._Got(status, None, None, body[:limit], ctype, len(body) <= limit)


class Wayback:
    def __init__(self, latest=None, can_capture=True):
        self._latest, self.can_capture, self.submitted = latest or {}, can_capture, []

    def latest(self, url):
        return self._latest.get(url)          # get-default: a URL with no capture in the fake

    def submit(self, url, within='30d'):
        self.submitted.append((url, within))
        return 'spn2-job-1'


def source(root, sid='src-example-bench-leaderboard', url=URL, **extra):
    rec = {'id': sid, 'type': 'leaderboard-page', 'url': url,
           'archive_url': 'https://web.archive.org/web/20260901000000/%s' % url, 'archive_captured': '2026-09-01',
           'archive_status': 'ok', 'archive_digest': 'A' * 32, 'licence_class': 'unlicensed',
           'licence_checked_on': '2026-09-01', 'provenance': 'primary', **extra}
    d = os.path.join(root, 'data', 'sources', '2026')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, sid + '.yaml'), 'w', encoding='utf-8', newline='\n') as fh:
        for k, v in rec.items():
            fh.write('%s: %s\n' % (k, 'null' if v is None else v))
    return os.path.join(d, sid + '.yaml')


def reread(path):
    with open(path, encoding='utf-8') as fh:
        return dict(emitter().load(fh))


def validated(path):
    rec = reread(path)
    Source.model_validate(rec)                 # what the job writes is a valid Source
    return rec


def run(root, table, wayback=None, **kw):
    return C.run(str(root), resolver=Resolver(table), wayback=wayback or Wayback(), now=NOW, every=True, **kw)


BASE = C.page_digest(page('leaderboard.html'), HTML)


# ---- the four outcomes --------------------------------------------------------------------------

def test_live_stamps_the_check_and_keeps_the_baseline(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    report = run(tmp_path, {URL: (200, page('leaderboard.html'), HTML, None)})
    rec = validated(p)
    assert report['counts']['live'] == 1 and report['events'] == []
    assert (rec['link_status'], rec['link_checked_at'], rec['body_sha256']) == ('live', '2026-09-29T08:43:00Z', BASE)
    assert rec['link_changed_sha256'] is None


def test_the_first_check_records_the_baseline(tmp_path):
    p = source(tmp_path)
    run(tmp_path, {URL: (200, page('leaderboard.html'), HTML, None)})
    assert validated(p)['body_sha256'] == BASE


def test_a_silently_rewritten_leaderboard_is_a_data_integrity_event_not_a_refresh(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    wb = Wayback()
    report = run(tmp_path, {URL: (200, page('leaderboard-rewritten.html'), HTML, None)}, wb)
    rec = validated(p)
    [event] = report['events']
    assert (event['kind'], event['new'], event['signals']) == ('data-integrity', True, ['body'])
    assert rec['link_status'] == 'changed'
    assert rec['body_sha256'] == BASE                                   # not refreshed: the baseline stays
    assert rec['link_changed_sha256'] == C.page_digest(page('leaderboard-rewritten.html'), HTML) != BASE
    assert rec['archive_url'].startswith('https://web.archive.org/web/20260901')   # the old capture stays
    assert wb.submitted == [(URL, '1d')] and event['recapture'] == {'outcome': 'requested', 'job_id': 'spn2-job-1'}


def test_a_changed_page_stays_flagged_until_a_curator_accepts_it(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    table = {URL: (200, page('leaderboard-rewritten.html'), HTML, None)}
    run(tmp_path, table)
    wb = Wayback()
    again = run(tmp_path, table, wb)
    assert validated(p)['link_status'] == 'changed' and again['events'][0]['new'] is False
    assert wb.submitted == []                                           # re-archived once, not weekly
    capture = ('20260929090000', URL, 'B' * 32)
    got = C.accept(str(tmp_path), 'src-example-bench-leaderboard', Wayback({URL: capture}), NOW)
    rec = validated(p)
    assert rec['link_status'] == 'live' and rec['link_changed_sha256'] is None
    assert rec['body_sha256'] == C.page_digest(page('leaderboard-rewritten.html'), HTML)
    assert (rec['archive_digest'], rec['archive_captured']) == ('B' * 32, '2026-09-29') and got['path']
    assert run(tmp_path, table, Wayback({URL: capture}))['counts']['live'] == 1


def test_a_newer_capture_with_another_digest_is_a_change(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    wb = Wayback({URL: ('20260920120000', URL, 'C' * 32)})
    report = run(tmp_path, {URL: (200, page('leaderboard.html'), HTML, None)}, wb)
    assert report['events'][0]['signals'] == ['cdx'] and validated(p)['link_status'] == 'changed'


def test_an_older_or_identical_capture_is_not_a_change(tmp_path):
    source(tmp_path, body_sha256=BASE)
    for capture in [('20260920120000', URL, 'A' * 32), ('20260815000000', URL, 'C' * 32)]:
        assert run(tmp_path, {URL: (200, page('leaderboard.html'), HTML, None)}, Wayback({URL: capture}))['counts']['live'] == 1


def test_an_spa_shell_is_suspect_never_live(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    report = run(tmp_path, {URL: (200, page('spa-shell.html'), HTML, None)})
    rec = validated(p)
    assert rec['link_status'] == 'suspect' and 'SPA shell' in rec['link_detail']
    assert report['events'][0]['kind'] == 'human-review' and rec['body_sha256'] == BASE


def test_a_soft_404_is_suspect_never_live(tmp_path):
    p = source(tmp_path)
    run(tmp_path, {URL: (200, page('soft-404.html'), HTML, None)})
    rec = validated(p)
    assert rec['link_status'] == 'suspect' and 'Page Not Found' in rec['link_detail']
    assert 'body_sha256' not in rec                                    # a soft-404 is never a baseline


@pytest.mark.parametrize('answer', [(404, None, None, None), (None, None, None, None),
                                    (301, None, None, 'https://parked.example.net/')])
def test_dead_keeps_the_capture_as_the_canonical_reference(tmp_path, answer):
    p = source(tmp_path, body_sha256=BASE)
    table = {URL: answer, 'https://parked.example.net/': (200, page('leaderboard.html'), HTML, None)}
    report = run(tmp_path, table)
    rec = validated(p)
    assert rec['link_status'] == 'dead' and rec['archive_url'] in rec['link_detail']
    assert rec['archive_url'].startswith('https://web.archive.org/') and rec['archive_status'] == 'ok'
    assert report['events'][0]['kind'] == 'lifecycle-review'


def test_a_429_writes_nothing(tmp_path):
    p = source(tmp_path)
    before = reread(p)
    report = run(tmp_path, {URL: (429, None, None, None)})
    assert report['counts']['unknown'] == 1 and reread(p) == before and report['events'] == []


# ---- the fetch ----------------------------------------------------------------------------------

def test_the_fetch_is_a_ranged_get_never_head(monkeypatch):
    sent = []

    class Answer:
        status, headers = 200, {'Content-Type': HTML}

        def __init__(self, req):
            sent.append(req)

        def read(self, n=-1):
            return page('leaderboard.html')[:n] if n and n > 0 else b''

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    r = links.Resolver(timeout=1, spacing=0, retry_after=0)
    monkeypatch.setattr(r._opener, 'open', lambda req, timeout: Answer(req))
    got = C.check({'id': 'src-x', 'url': URL}, r, Wayback(), NOW)
    assert got['outcome'] == 'live'
    assert [q.get_method() for q in sent] == ['GET'] and sent[0].get_header('Range') == 'bytes=0-32767'
    assert isinstance(sent[0], urllib.request.Request)


def test_a_refused_range_falls_back_to_a_plain_get(tmp_path):
    class Picky(Resolver):
        def _once(self, url, ranged=True, limit=32768):
            if ranged:
                self.requests += 1
                self.seen.append((url, ranged))
                return links._Got(416, None, None)
            return super()._once(url, ranged, limit)

    source(tmp_path)
    r = Picky({URL: (200, page('leaderboard.html'), HTML, None)})
    C.run(str(tmp_path), resolver=r, wayback=Wayback(), now=NOW, every=True)
    assert r.seen == [(URL, True), (URL, False)]


# ---- the digest ---------------------------------------------------------------------------------

def test_a_new_nonce_or_token_is_not_a_change():
    assert C.page_digest(page('leaderboard-new-nonce.html'), HTML) == BASE
    assert page('leaderboard-new-nonce.html') != page('leaderboard.html')


def test_json_data_in_a_script_is_part_of_the_digest():
    a = page('leaderboard.html')
    b = a.replace(b'"score":68.9', b'"score":60.0')
    assert b != a and C.page_digest(b, HTML) != BASE


def test_a_non_html_body_is_hashed_as_fetched():
    import hashlib
    assert C.page_digest(b'{"a": 1}', 'application/json') == hashlib.sha256(b'{"a": 1}').hexdigest()
    assert C.page_digest(None) is None


# ---- the rotation -------------------------------------------------------------------------------

@pytest.mark.parametrize('n, per_week', [(0, 0), (1, 1), (13, 1), (14, 2), (130, 10), (1000, 77), (5000, 385)])
def test_the_slice_covers_the_corpus_each_quarter(n, per_week):
    assert C.slice_size(n) == per_week
    assert per_week * (C.QUARTER_DAYS // C.CADENCE_DAYS) >= n


def test_thirteen_weekly_runs_check_every_source_oldest_first(tmp_path):
    ids = ['src-page-%02d' % i for i in range(30)]
    table = {}
    for sid in ids:
        u = 'https://bench.example.org/%s' % sid
        source(tmp_path, sid, u)
        table[u] = (200, page('leaderboard.html'), HTML, None)
    seen, week = [], NOW
    for _ in range(13):
        r = C.run(str(tmp_path), resolver=Resolver(table), wayback=Wayback(), now=week)
        assert r['slice'] == 3
        seen += [row['id'] for row in r['checked']]
        week += timedelta(days=7)
    assert sorted(set(seen)) == ids
    assert seen[:30] == ids                                             # never-checked first, then oldest


def test_a_new_source_jumps_the_queue(tmp_path):
    for sid in ('src-a', 'src-b'):
        source(tmp_path, sid, 'https://bench.example.org/' + sid, link_status='live',
               link_checked_at='2026-09-01T00:00:00Z', body_sha256=BASE)
    source(tmp_path, 'src-c', 'https://bench.example.org/src-c')
    table = {'https://bench.example.org/' + s: (200, page('leaderboard.html'), HTML, None) for s in ('src-a', 'src-b', 'src-c')}
    r = C.run(str(tmp_path), resolver=Resolver(table), wayback=Wayback(), now=NOW, limit=1)
    assert [row['id'] for row in r['checked']] == ['src-c']


def test_a_no_collect_host_is_never_fetched(tmp_path):
    source(tmp_path)
    os.makedirs(tmp_path / 'ingest')
    (tmp_path / 'ingest' / 'no-collect.yaml').write_text('- bench.example.org\n', encoding='utf-8')
    r = Resolver({})
    report = C.run(str(tmp_path), resolver=r, wayback=Wayback(), now=NOW, every=True)
    assert report['checked'] == [] and report['skipped_no_collect'] == 1 and r.seen == []


def test_dry_run_writes_nothing_and_requests_no_capture(tmp_path):
    p = source(tmp_path, body_sha256=BASE)
    before, wb = reread(p), Wayback()
    report = run(tmp_path, {URL: (200, page('leaderboard-rewritten.html'), HTML, None)}, wb, dry_run=True)
    assert report['counts']['changed'] == 1 and reread(p) == before and wb.submitted == []


# ---- the schema and the report ------------------------------------------------------------------

def test_the_source_model_holds_the_link_fields_together():
    base = {'id': 'src-x', 'type': 'paper', 'url': URL, 'doi': '10.1234/x', 'archive_status': 'not-required',
            'licence_class': 'unlicensed', 'licence_checked_on': '2026-09-01', 'provenance': 'primary'}
    Source.model_validate(dict(base, link_status='live', link_checked_at='2026-09-29T08:43:00Z'))
    for bad in [{'link_status': 'live'}, {'link_checked_at': '2026-09-29T08:43:00Z'},
                {'link_status': 'changed', 'link_checked_at': '2026-09-29T08:43:00Z'},
                {'link_status': 'live', 'link_checked_at': '2026-09-29T08:43:00Z', 'link_changed_sha256': 'a' * 64}]:
        with pytest.raises(ValueError):
            Source.model_validate(dict(base, **bad))


def test_the_summary_leads_with_the_data_integrity_event(tmp_path):
    source(tmp_path, body_sha256=BASE)
    report = run(tmp_path, {URL: (200, page('leaderboard-rewritten.html'), HTML, None)})
    body = C.summary(report)
    assert 'Data-integrity events' in body and 'src-example-bench-leaderboard' in body and '--accept' in body
    assert 'check_links: 1 of 1' in C.text(report)
