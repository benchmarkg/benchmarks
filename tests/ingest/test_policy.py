"""Per-host policy, the robots.txt cache and the no-collect list (P5-S2-T01; 07 S10.1, 06 S9.6).

The verify: `pytest tests/ingest/test_policy.py`. Done when "An unlisted host raises; epoch.ai/inspect-viewer/,
epoch.ai/frontiermath/tiers-1-4/benchmark-problems and drivendata.org/*/leaderboard_partial are unreachable by
any code path; a no-collect host is refused." So:

  - ingest/policy.yaml: one token bucket per host, each with its basis, the three forbidden paths, the UA;
  - the gate: an unlisted host raises UnlistedHost; a forbidden URL raises Forbidden on every host and subdomain,
    whatever robots.txt says; a no-collect host (and its subdomains) raises NoCollect before anything is sent;
    a spent or zero budget raises; robots.txt is fetched once per host per run, read by RFC 9309 (wildcards
    included, which urllib.robotparser cannot), and honoured; the bucket paces;
  - "any code path": every live transport refuses the three URLs without opening a socket, and a scan of
    ingest/, tools/ and scripts/ fails any function that opens a URL without asking the gate -- with a seeded
    unguarded function as the failure case.
"""
import ast
import glob
import os
import urllib.request

import pytest

from ingest.http import policy as P

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
THE_THREE = [
    'https://epoch.ai/inspect-viewer/36231d6d/viewer.html',
    'https://epoch.ai/frontiermath/tiers-1-4/benchmark-problems',
    'https://www.drivendata.org/competitions/66/flu-shot-learning/leaderboard_partial/',
]


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 6))
        self.t += s


def robots(answers):
    """A robots.txt fetcher answering {host: (status, body)}; it records what it was asked."""
    asked = []

    def fetch(url, ua):
        asked.append(url)
        host = url.split('/')[2]
        return answers.get(host, (404, ''))       # get-default: a host with no robots.txt
    fetch.asked = asked
    return fetch


def gate(doc=None, answers=None, clock=None):
    base = P.Policy.load()
    pol = P.Policy.from_dict(doc) if doc is not None else base
    clock = clock or Clock()
    return P.Gate(pol, robots=robots(answers or {}), clock=clock, sleep=clock.sleep)


def doc(**over):
    d = {'user_agent': 'UAIBI/0.1 (+test)', 'robots_token': 'UAIBI',
         'hosts': {'example.org': {'rate': 1.0, 'burst': 1, 'basis': 'test'},
                   'data.example.org': {'rate': 1.0, 'basis': 'test'},
                   'epoch.ai': {'rate': 1.0, 'basis': 'test'},
                   'logs.epoch.ai': {'rate': 1.0, 'basis': 'test'},
                   'www.drivendata.org': {'rate': 1.0, 'basis': 'test'}},
         'forbidden': [{'host': r.host, 'path': r.path, 'basis': r.basis} for r in P.Policy.load().forbidden],
         'no_collect': []}
    d.update(over)
    return d


# ---- ingest/policy.yaml -----------------------------------------------------------------------------------------

def test_the_policy_file_has_one_bucket_per_host_each_with_its_basis():
    pol = P.Policy.load()
    assert len(pol.hosts) >= 10
    for h in pol.hosts.values():
        assert h.rate > 0 and h.burst >= 1 and h.basis, h
    assert pol.hosts['huggingface.co'].rate == 1.0 and pol.hosts['huggingface.co'].max_requests == 2000
    assert pol.hosts['export.arxiv.org'].rate == pytest.approx(1 / 3, rel=1e-3)
    assert pol.hosts['arxiv.org'].rate == pytest.approx(1 / 15, rel=1e-2)
    for h in ('grand-challenge.org', 'www.codabench.org', 'eval.ai', 'predictioncenter.org'):
        assert pol.hosts[h].rate == 0.5                      # 06 S9.6: roughly 1 req / 2 s
    assert pol.hosts['artificialanalysis.ai'].max_requests == 0  # 07 S10: "Zero. Link out only"


def test_the_three_exclusions_are_in_the_file_and_the_no_collect_list_exists():
    pol = P.Policy.load()
    assert {(r.host, r.path) for r in pol.forbidden} == {
        ('drivendata.org', '/*/leaderboard_partial'), ('epoch.ai', '/inspect-viewer/'),
        ('epoch.ai', '/frontiermath/tiers-1-4/benchmark-problems'),
        ('swe-bench-submissions.s3.amazonaws.com', '/')}      # 06 S3.7: link, never fetch (P5-S6-T03)
    assert pol.no_collect == ()


def test_every_transport_sends_the_policy_files_user_agent():
    from ingest import verification
    from ingest.adapters import hf_hub, openalex, semantic_scholar
    from tools import archive
    ua = P.Policy.load().user_agent
    assert hf_hub.USER_AGENT == openalex.USER_AGENT == semantic_scholar.USER_AGENT == verification.USER_AGENT \
        == archive.USER_AGENT == ua


@pytest.mark.parametrize('bad,msg', [
    ({'hosts': {'x.org': {'rate': 0, 'basis': 'b'}}}, 'rate > 0'),
    ({'hosts': {'x.org': {'rate': 1}}}, 'basis'),
    ({'user_agent': ''}, 'user_agent'),
])
def test_a_malformed_policy_is_refused(bad, msg):
    with pytest.raises(P.PolicyError, match=msg):
        P.Policy.from_dict(doc(**bad))


# ---- the gate: unlisted, forbidden, no-collect, budget ----------------------------------------------------------

def test_an_unlisted_host_raises_and_nothing_is_sent():
    g = gate()
    with pytest.raises(P.UnlistedHost, match='no entry in ingest/policy.yaml'):
        g.admit('https://unlisted.example.net/data.json')
    assert g.robots_fetch.asked == [] and g.log == [('https://unlisted.example.net/data.json', 'UnlistedHost')]


@pytest.mark.parametrize('url', THE_THREE + [
    'https://epoch.ai/inspect-viewer/',
    'https://logs.epoch.ai/inspect-viewer/36231d6d/viewer.html?log_file=x.eval',   # a subdomain of epoch.ai
    'https://epoch.ai/frontiermath/tiers-1-4/benchmark-problems/7?page=2',
    'https://drivendata.org/a/leaderboard_partial',
])
def test_the_three_are_forbidden_even_on_a_listed_host_with_a_permissive_robots_txt(url):
    g = gate(doc(), answers={h: (200, 'User-agent: *\nAllow: /\n') for h in doc()['hosts']})
    with pytest.raises(P.Forbidden):
        g.admit(url)
    with pytest.raises(P.Forbidden):
        g.refuse(url)
    assert g.robots_fetch.asked == []                         # refused before robots.txt is even read


@pytest.mark.parametrize('url', ['https://epoch.ai/data/benchmark_data.zip', 'https://epoch.ai/frontiermath',
                                 'https://www.drivendata.org/competitions/66/flu-shot-learning/'])
def test_their_neighbours_are_not(url):
    g = gate(doc())
    g.admit(url)
    assert g.log[-1] == (url, 'sent')


def test_a_no_collect_host_and_its_subdomains_are_refused_outright():
    g = gate(doc(no_collect=[{'host': 'example.org', 'requested_on': '2026-10-09', 'recorded_in': 'issue 1'}]))
    for url in ('https://example.org/', 'https://data.example.org/leaderboard.json'):
        with pytest.raises(P.NoCollect, match='no-collect'):
            g.admit(url)
        with pytest.raises(P.NoCollect):
            g.refuse(url)
    assert g.robots_fetch.asked == [] and g.counts == {}


def test_a_zero_budget_is_never_spent_and_a_budget_runs_out():
    g = gate()
    with pytest.raises(P.BudgetExhausted, match='0 of 0'):
        g.admit('https://artificialanalysis.ai/leaderboards/models')
    d = doc()
    d['hosts']['example.org']['max_requests'] = 3                # robots.txt plus two
    g = gate(d)
    g.admit('https://example.org/a')
    g.admit('https://example.org/b')
    with pytest.raises(P.BudgetExhausted, match='3 of 3'):
        g.admit('https://example.org/c')


def test_a_url_that_is_not_http_is_refused():
    with pytest.raises(P.PolicyRefusal):
        gate().admit('file:///etc/passwd')


# ---- robots.txt -------------------------------------------------------------------------------------------------

DRIVENDATA = """# a robots.txt in DrivenData's shape
User-agent: *
Disallow: /*/leaderboard_partial
Disallow: /accounts/
Allow: /accounts/public/
"""


@pytest.mark.parametrize('path,ok', [
    ('/competitions/66/leaderboard_partial', False),      # the wildcard urllib.robotparser cannot read
    ('/competitions/66/', True),
    ('/accounts/me', False),
    ('/accounts/public/x', True),                         # the longer, Allow rule wins
])
def test_robots_txt_wildcards_and_longest_match(path, ok):
    assert P.parse_robots(DRIVENDATA, 'UAIBI').allowed(path) is ok


def test_our_own_group_wins_over_star_and_an_empty_disallow_allows():
    text = 'User-agent: *\nDisallow: /\n\nUser-agent: OtherBot\nUser-agent: uaibi\nDisallow:\n'
    assert P.parse_robots(text, 'UAIBI').allowed('/anything')
    assert not P.parse_robots(text, 'SomeoneElse').allowed('/anything')


def test_dollar_anchors_the_end_and_a_tie_goes_to_allow():
    r = P.parse_robots('User-agent: *\nDisallow: /*.json$\nAllow: /a\nDisallow: /a\n', 'UAIBI')
    assert not r.allowed('/x/data.json') and r.allowed('/x/data.json?v=1') and r.allowed('/a')


def test_the_gate_honours_robots_txt_and_fetches_it_once_per_host_per_run():
    g = gate(doc(), answers={'example.org': (200, 'User-agent: *\nDisallow: /private/\n')})
    g.admit('https://example.org/a')
    g.admit('https://example.org/b')
    with pytest.raises(P.RobotsDisallowed, match='disallowed by https://example.org/robots.txt'):
        g.admit('https://example.org/private/x')
    assert g.robots_fetch.asked == ['https://example.org/robots.txt']
    g.admit('https://data.example.org/a')                     # its own host, its own robots.txt
    assert g.robots_fetch.asked[-1] == 'https://data.example.org/robots.txt'


@pytest.mark.parametrize('status,ok', [(404, True), (410, True), (500, False), (503, False), (None, False)])
def test_no_robots_txt_allows_everything_and_an_unreachable_one_allows_nothing(status, ok):
    g = gate(doc(), answers={'example.org': (status, '')})
    if ok:
        g.admit('https://example.org/a')
    else:
        with pytest.raises(P.RobotsDisallowed, match='unreachable'):
            g.admit('https://example.org/a')


# ---- the bucket -------------------------------------------------------------------------------------------------

def test_the_bucket_paces_requests_to_one_host_and_not_across_hosts():
    clock = Clock()
    d = doc()
    d['hosts']['example.org']['rate'] = 0.5                   # one per 2 s
    g = gate(d, clock=clock)
    for p in 'abc':
        g.admit('https://example.org/' + p)
    assert clock.slept == [2.0, 2.0, 2.0]                     # robots.txt, then a, b and c each 2 s apart
    g.admit('https://data.example.org/a')                     # another host: its own robots.txt, then 1 s (rate 1)
    assert clock.slept == [2.0, 2.0, 2.0, 1.0]


def test_a_burst_spends_its_tokens_then_paces():
    clock = Clock()
    d = doc()
    d['hosts']['example.org'].update(rate=1.0, burst=3)
    g = gate(d, clock=clock)
    for p in 'abcd':
        g.admit('https://example.org/' + p)
    assert clock.slept == [1.0, 1.0]                          # robots.txt, a, b free; c and d wait a second each


# ---- any code path ----------------------------------------------------------------------------------------------

def no_socket(*a, **k):
    raise AssertionError('a socket was opened')


@pytest.mark.parametrize('url', THE_THREE)
def test_no_ingest_transport_can_reach_the_three(url, monkeypatch):
    from ingest import verification
    from ingest.adapters import hf_hub, openalex, semantic_scholar
    monkeypatch.setattr(urllib.request, 'urlopen', no_socket)
    for t in (hf_hub.NetworkTransport(), openalex.NetworkTransport(), semantic_scholar.NetworkTransport()):
        with pytest.raises(P.Forbidden):
            t.get(url, {})
    assert verification.head(url) == (None, 'refused by ingest/policy.yaml: Forbidden')


@pytest.mark.parametrize('url', THE_THREE)
def test_no_tool_can_reach_the_three_either(url, monkeypatch):
    from tools import archive, links
    from tools.copilot import draft
    monkeypatch.setattr(urllib.request, 'urlopen', no_socket)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', no_socket)
    with pytest.raises(P.Forbidden):
        draft._get(url)
    with pytest.raises(P.Forbidden):
        archive.Wayback()._request(url)
    with pytest.raises(P.Forbidden):
        links.Resolver()._once(url)
    with pytest.raises(P.Forbidden):
        archive.location(url)


def test_the_policed_wrapper_keeps_a_refused_url_from_its_inner_transport():
    class Inner:
        def __init__(self):
            self.asked = []

        def get(self, url, headers):
            self.asked.append(url)
    inner = Inner()
    t = P.PolicedTransport(inner, gate(doc()))
    with pytest.raises(P.Forbidden):
        t.get(THE_THREE[0], {})
    t.get('https://example.org/ok', {})
    assert inner.asked == ['https://example.org/ok']


OPENS = {'urlopen'}
GUARDS = {'admit', 'refuse'}


def unguarded(paths):
    """'file:function' for every function that opens a URL (urlopen, or an opener's open) and asks no gate."""
    out = []
    for path in paths:
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read(), path)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = [n.func for n in ast.walk(fn) if isinstance(n, ast.Call)]
            names = {c.attr if isinstance(c, ast.Attribute) else c.id if isinstance(c, ast.Name) else None
                     for c in calls}
            opens = names & OPENS or any(isinstance(c, ast.Attribute) and c.attr == 'open'
                                         and 'opener' in ast.unparse(c.value).lower() for c in calls)
            if opens and not names & GUARDS:
                rel = os.path.abspath(path)
                if os.path.splitdrive(rel)[0].lower() == os.path.splitdrive(ROOT)[0].lower():
                    rel = os.path.relpath(rel, ROOT)
                out.append('%s:%s' % (rel.replace(os.sep, '/'), fn.name))
    return out


def test_every_function_that_opens_a_url_asks_the_gate_first():
    paths = [p for d in ('ingest', 'tools', 'scripts')
             for p in glob.glob(os.path.join(ROOT, d, '**', '*.py'), recursive=True)]
    found = unguarded(paths)
    # the gate's own robots.txt fetch, which Gate.robots_for calls only after its checks
    assert found == ['ingest/http/policy.py:fetch_robots'], found


def test_the_failure_case_a_seeded_unguarded_fetch_is_caught(tmp_path):
    seeded = tmp_path / 'adapter.py'
    seeded.write_text('import urllib.request\n\n'
                      'def leaderboard(url):\n'
                      '    with urllib.request.urlopen(url) as r:\n'
                      '        return r.read()\n\n'
                      'def guarded(url):\n'
                      '    policy.admit(url)\n'
                      '    return urllib.request.urlopen(url)\n', encoding='utf-8')
    assert [s.rsplit(':', 1)[1] for s in unguarded([str(seeded)])] == ['leaderboard']
