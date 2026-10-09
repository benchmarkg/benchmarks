"""The GitHub metadata adapter and the conditional-request probe (P5-S5-T01; 06 S3.3, 07 S4.1, S1.5, S10).

The verify: `pytest tests/ingest/test_github.py && python scripts/probe_conditional_requests.py`. Done when "The
probe issues 100 conditional requests and confirms X-RateLimit-Remaining is unchanged". The live probe needs
GH_API_TOKEN and is run by hand (the PR records its result); here it runs against scripted transports, the
failure case -- 304s that are charged -- included. The adapter, over synthetic recorded responses:

  - GH_API_TOKEN in the Authorization header only, and If-None-Match on every request a previous run saw;
  - volatile_fields are 07 S1.5's (pushed_at, stargazers_count, forks_count) plus subscribers_count, and a
    counters-only change is 'metrics-only' while a licence change is a 'field-change';
  - 06 S3.3's mapping: pushed_at, license.spdx_id (null kept as a value), topics, homepage, CITATION.cff and
    release tags; README and release-note prose are never requested or kept;
  - a 404 on a catalogued repository is a lifecycle review, not an error; a spent rate limit is a soft fail and a
    refused token a hard one;
  - CITATION.cff is read only when the root listing shows a new blob sha, so a repository without one costs no
    request beyond its listing.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from email.message import Message

import pytest
from typer.testing import CliRunner

from ingest.adapters import github as G
from ingest.adapters.base import Adapter
from ingest.http.backoff import Response
from ingest.http.fixture import FixtureTransport

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'github')
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
REPOS = {'fixture-org/alpha': [('alpha', 'data/benchmarks/code/alpha.yaml'), ('alpha-lite', 'data/benchmarks/code/alpha-lite.yaml')],
         'fixture-org/bravo': [('bravo', 'data/benchmarks/code/bravo.yaml')],
         'fixture-org/gone': [('gone', 'data/benchmarks/code/gone.yaml')]}


def adapter(transport=None):
    return G.GitHub(transport or FixtureTransport(FIX), repos=REPOS, now=lambda: NOW)


def docs(report):
    """{repo name: the candidate's identity, plus its suggestions by field}."""
    out = {}
    for d in report['documents']:
        out[d['identity']['repository'].rsplit('/', 1)[1]] = dict(
            d['identity'], suggested={s['field']: s['value'] for s in d['_suggested']})
    return out


@pytest.fixture()
def first():
    state = G.new_state()
    t = FixtureTransport(FIX)
    return G.run(adapter(t), state), state, t


# ---- the declaration --------------------------------------------------------------------------------------------

def test_the_adapter_declares_07_s1_1_and_07_s1_5s_volatile_fields():
    assert issubclass(G.GitHub, Adapter) and G.GitHub.name == 'github'
    assert {'pushed_at', 'stargazers_count', 'forks_count'} <= set(G.GitHub.volatile_fields)
    assert G.GitHub.licence_class == 'unlicensed' and G.GitHub.raw_retainable is False
    from tools.build import ingest_health
    assert 'github' in [c.name for c in ingest_health.adapters()]       # it has a row on /sources


def test_catalogued_repositories_are_the_curated_benchmarks_and_a_shared_repo_is_one_candidate():
    repos = G.catalogued(ROOT)
    assert sorted(b for b, _ in repos['SWE-bench/SWE-bench']) == ['swe-bench', 'swe-bench-verified']
    assert all(not p.split('/')[2].startswith('_') for v in repos.values() for _, p in v)   # never a stub


# ---- the mapping ------------------------------------------------------------------------------------------------

def test_06_s3_3s_mapping(first):
    report, _, _ = first
    a, b = docs(report)['alpha'], docs(report)['bravo']
    assert a['benchmarks'] == ['alpha', 'alpha-lite']
    assert (a['code_licence'], a['homepage']) == ('MIT', 'https://alpha.example.org')
    assert a['suggested'] == {'released': '2024-02-03', 'topics': ['benchmark', 'llm']}
    assert a['liveness'] == {'pushed_at': '2026-10-01T09:00:00Z', 'archived': False, 'disabled': False}
    assert a['adoption'] == {'stargazers_count': 420, 'forks_count': 12, 'subscribers_count': 3}
    assert a['citation_cff']['title'] == 'Alpha Bench' and a['citation_cff']['doi'] == '10.5555/alpha.2025'
    assert a['citation_cff']['version'] == '2.1.0' and a['citation_cff']['date_released'] == '2025-05-01'
    assert [r['tag'] for r in a['release_tags']] == ['v3.0.0-rc1', 'v2.1.0']          # newest first, no draft
    assert a['release_tags'][0]['prerelease'] is True


def test_no_licence_is_a_value_and_an_empty_homepage_is_none(first):
    b = docs(first[0])['bravo']
    assert 'code_licence' in b and b['code_licence'] is None
    assert b['homepage'] is None and b['citation_cff'] is None and b['release_tags'] == []


def test_readme_and_release_note_prose_are_never_requested_or_kept(first):
    report, _, t = first
    assert not any('readme' in url.lower() for url, _ in t.requests)
    text = json.dumps(report['documents'])
    assert 'prose' not in text and '"body"' not in text and 'synthetic repository' not in text   # nor the description


def test_drafts_are_review_documents_under_the_discovery_tree(first):
    state = G.new_state()
    a = adapter()
    drafts = []
    for c in a.discover(state):
        p = a.fetch(c, state)
        drafts += a.normalise(p)[0] if p else []
    assert sorted(str(d.path).replace(os.sep, '/') for d in drafts) == [
        'data/_discovery/github/cand-gh-fixture-org--alpha.yaml', 'data/_discovery/github/cand-gh-fixture-org--bravo.yaml']
    assert all(d.change_class == 'new' and d.ingestion['adapter'] == 'github' and d.entity_id is None for d in drafts)
    from ingest.gates import checks
    for d in drafts:                                     # 06 S1.1's shape, and 07 S8's metadata-only limit
        checks.schema(d.payload, str(d.path))
        checks.metadata_only(d.payload, str(d.path))


def test_normalise_is_a_pure_function_of_the_payload():
    state = G.new_state()
    a = adapter()
    c = next(a.discover(state))
    p = a.fetch(c, state)
    assert G.normalise(p) == G.normalise(p)


# ---- a 404, and failures ----------------------------------------------------------------------------------------

def test_a_404_on_a_catalogued_repo_is_a_lifecycle_review_not_an_error(first):
    report, _, _ = first
    assert report['status'] == 'ok' and report['errors'] == []
    assert report['unresolved'] == 1 and 'gone' not in docs(report)
    assert 'Review Benchmark.lifecycle' in report['lifecycle_reviews'][0] and 'fixture-org/gone' in report['lifecycle_reviews'][0]
    assert {o['repo']: o['http_status'] for o in report['observations']}['fixture-org/gone'] == 404


class Scripted:
    """A transport answering from a {url: [Response, ...]} script, recording what it was asked."""

    def __init__(self, script):
        self.script, self.requests = {k: list(v) for k, v in script.items()}, []

    def get(self, url, headers):
        self.requests.append((url, dict(headers)))
        return self.script[url].pop(0)


def resp(status, body=None, remaining=4990, etag='W/"e"'):
    h = [('X-RateLimit-Remaining', str(remaining)), ('X-RateLimit-Reset', '1791564748'), ('X-RateLimit-Resource', 'core')]
    if etag:
        h.append(('ETag', etag))
    return Response(status, h, json.dumps(body).encode() if body is not None else b'')


BASE = G.API + '/repos/o/r'


def repo_body(**over):
    d = {'full_name': 'o/r', 'html_url': 'https://github.com/o/r', 'homepage': None, 'license': {'spdx_id': 'MIT'},
         'topics': [], 'created_at': '2024-01-01T00:00:00Z', 'pushed_at': '2026-01-01T00:00:00Z', 'archived': False,
         'disabled': False, 'stargazers_count': 1, 'forks_count': 1, 'subscribers_count': 1, 'default_branch': 'main'}
    d.update(over)
    return d


def one(script):
    a = G.GitHub(Scripted(script), repos={'o/r': [('r', 'data/benchmarks/code/r.yaml')]}, now=lambda: NOW)
    return G.run(a, G.new_state()), a


@pytest.mark.parametrize('status,remaining,expected', [(403, 0, 'soft-fail'), (429, 10, 'soft-fail'),
                                                       (401, 10, 'hard-fail'), (403, 10, 'hard-fail')])
def test_a_spent_rate_limit_is_soft_and_a_refused_token_is_hard(status, remaining, expected):
    report, _ = one({BASE: [resp(status, {'message': 'x'}, remaining=remaining, etag=None)] * 3})
    assert report['status'] == expected and report['errors']


# ---- conditional requests and change classes --------------------------------------------------------------------

def test_a_second_run_sends_if_none_match_everywhere_and_finds_no_change(first):
    _, state, _ = first
    t = FixtureTransport(FIX)
    report = G.run(adapter(t), state)
    assert report['drafts']['no-change'] == 2 and sum(report['drafts'].values()) == 2
    assert report['unresolved'] == 1 and report['status'] == 'ok'     # the 404 is raised again: it does not go quiet
    asked = [(u, h) for u, h in t.requests if not u.endswith('/fixture-org/gone')]
    assert asked and all('If-None-Match' in h for _, h in asked)
    assert not any(u.endswith('CITATION.cff') for u, _ in t.requests)   # unchanged sha: not re-read


def run_twice(second_repo, cff_sha='s1'):
    root1 = [{'name': 'CITATION.cff', 'path': 'CITATION.cff', 'sha': 's1', 'type': 'file'}]
    root2 = [{'name': 'CITATION.cff', 'path': 'CITATION.cff', 'sha': cff_sha, 'type': 'file'}]
    cff = {'path': 'CITATION.cff', 'sha': 's1', 'html_url': 'u', 'content': ''}
    script = {BASE: [resp(200, repo_body(), etag='W/"1"'), resp(200, second_repo, etag='W/"2"')],
              BASE + '/contents/': [resp(200, root1, etag='W/"r1"'), resp(200 if cff_sha != 's1' else 304, root2, etag='W/"r2"')],
              BASE + '/contents/CITATION.cff': [resp(200, cff), resp(200, dict(cff, sha=cff_sha))],
              BASE + '/releases?per_page=30': [resp(200, [], etag='W/"l"'), resp(304, None, etag='W/"l"')]}
    t = Scripted(script)
    a = G.GitHub(t, repos={'o/r': [('r', 'data/benchmarks/code/r.yaml')]}, now=lambda: NOW)
    state = G.new_state()
    G.run(a, state)
    return G.run(G.GitHub(t, repos=a.repos, now=lambda: NOW), state), t


def test_a_counters_only_change_is_metrics_only():
    report, _ = run_twice(repo_body(stargazers_count=999, forks_count=50, pushed_at='2026-10-01T00:00:00Z'))
    assert report['drafts']['metrics-only'] == 1 and report['drafts']['field-change'] == 0
    assert report['observations'][0]['stargazers_count'] == 999


def test_a_licence_change_is_a_field_change():
    report, _ = run_twice(repo_body(license={'spdx_id': 'Apache-2.0'}))
    assert report['drafts']['field-change'] == 1
    assert report['documents'][0]['identity']['code_licence'] == 'Apache-2.0'


def test_citation_cff_is_read_again_only_when_its_blob_sha_changes():
    _, t = run_twice(repo_body(), cff_sha='s1')
    assert sum(u.endswith('CITATION.cff') for u, _ in t.requests) == 1
    _, t = run_twice(repo_body(), cff_sha='s2')
    assert sum(u.endswith('CITATION.cff') for u, _ in t.requests) == 2


def test_a_304_that_costs_a_request_is_named():
    script = {BASE: [resp(304, None, remaining=100)], BASE + '/contents/': [resp(304, None, remaining=99)],
              BASE + '/releases?per_page=30': [resp(304, None, remaining=98)]}
    a = G.GitHub(Scripted(script), repos={'o/r': [('r', 'p')]}, now=lambda: NOW)
    state = G.new_state()
    for url in script:
        state['etags'][url] = {'etag': 'W/"e"', 'doc': repo_body() if url == BASE else [] if 'releases' in url else None}
    report = G.run(a, state)
    assert report['charged_304s'] == ['o/r'] and any('charged' in p for p in report['proposals'])


# ---- the network transport --------------------------------------------------------------------------------------

class FakeHTTP:
    def __init__(self, status, body=b'{}'):
        self.status, self.headers, self.body = status, Message(), body

    def read(self, *a):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_token_travels_in_the_authorization_header_only(monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append((req.full_url, dict(req.header_items())))
        return FakeHTTP(200)
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    G.NetworkTransport('ghp_secret', sleep=lambda s: None).get(BASE, {'If-None-Match': 'W/"x"'})
    url, headers = sent[0]
    assert headers['Authorization'] == 'Bearer ghp_secret' and 'ghp_secret' not in url
    assert headers['If-none-match'] == 'W/"x"' and headers['User-agent'] == G.USER_AGENT
    assert headers['X-github-api-version'] == '2022-11-28'


def test_the_cli_runs_it_over_the_fixtures(monkeypatch):
    monkeypatch.setattr(G, 'catalogued', lambda root=ROOT: REPOS)
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'github', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 0, r.output
    assert 'ingest github 0.1.0: ok' in r.output and 'new           2' in r.output and 'unresolved    1' in r.output


# ---- the probe --------------------------------------------------------------------------------------------------

def rate_limit(remaining=5000, reset=1):
    return resp(200, {'resources': {'core': {'limit': 5000, 'remaining': remaining, 'used': 5000 - remaining,
                                              'reset': reset}}}, etag=None)


def probe_script(n, remaining_on_304, reset_after='1791564748', first_status=200):
    url = G.API + '/repos/o/r'
    first = resp(first_status, {'id': 1}, remaining=4991, etag='W/"p"')
    three = [Response(304, [('X-RateLimit-Remaining', str(remaining_on_304(i))), ('X-RateLimit-Resource', 'core'),
                            ('X-RateLimit-Reset', reset_after if i == n - 1 else '1791564748'), ('ETag', 'W/"p"')], b'')
             for i in range(n)]
    return Scripted({G.API + '/rate_limit': [rate_limit(), rate_limit()], url: [first] + three})


@pytest.fixture()
def probe():
    import importlib.util
    spec = importlib.util.spec_from_file_location('probe', os.path.join(ROOT, 'scripts', 'probe_conditional_requests.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_probe_confirms_when_100_304s_leave_remaining_unchanged(probe):
    result = probe.probe(probe_script(100, lambda i: 4991), 'o/r', 100)
    assert result['exit_code'] == 0 and result['statuses'] == {'304': 100} and result['spent_by_conditional_requests'] == 0


def test_the_failure_case_the_probe_fails_when_304s_are_charged(probe):
    result = probe.probe(probe_script(100, lambda i: 4990 - i), 'o/r', 100)
    assert result['exit_code'] == 1 and result['spent_by_conditional_requests'] == 100
    assert 'NOT confirmed' in result['verdict']


def test_the_probe_is_inconclusive_across_a_window_reset_and_fails_on_a_non_304(probe):
    assert probe.probe(probe_script(10, lambda i: 4991, reset_after='1791568348'), 'o/r', 10)['exit_code'] == 3
    s = probe_script(10, lambda i: 4991)
    s.script[G.API + '/repos/o/r'][3] = resp(200, {'id': 1}, remaining=4990)
    assert probe.probe(s, 'o/r', 10)['exit_code'] == 2


def test_the_probe_refuses_to_run_without_a_token(probe, monkeypatch):
    monkeypatch.delenv('GH_API_TOKEN', raising=False)
    assert probe.main([]) == 2
