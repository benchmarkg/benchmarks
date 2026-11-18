"""Tests for scripts/adoption_measure.py, the three adoption instruments (P8-S1-T02; 13 S0.2; docs/adoption/instruments.md).

The verify: "All three conditions compute from recorded fixtures, and an injected API failure yields FAILED rather
than a silent zero or an unknown." The fixtures are tests/fixtures/adoption_measure/, written by hand from the
documented response shapes of the GitHub REST API, OpenAlex, DataCite and Semantic Scholar: every login, name,
ORCID and e-mail address in them is an invented placeholder. measured.json clears all three conditions, with the
counts worked out by hand below; nothing-yet.json is the repository as it stands, with nothing to count yet.

No test touches the network: urllib, sockets and subprocess raise for the whole module, and the live transport is
driven through a fake opener.
"""
import copy
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'adoption_measure')
MEASURED = os.path.join(FIXTURES, 'measured.json')
NOTHING_YET = os.path.join(FIXTURES, 'nothing-yet.json')
RULINGS = os.path.join(FIXTURES, 'rulings.yaml')
spec = importlib.util.spec_from_file_location('adoption_measure', os.path.join(ROOT, 'scripts', 'adoption_measure.py'))
am = importlib.util.module_from_spec(spec)
sys.modules['adoption_measure'] = am
spec.loader.exec_module(am)

REPO = 'example-org/catalogue'
CONCEPT, VERSION = '10.5555/adoption-fixture.concept', '10.5555/adoption-fixture.v1'
# Every identity the fixtures invent. None may reach the default output.
IDENTITIES = ('contributor-a', 'Contributor-A', 'contributor-b', 'contributor-c', 'contributor-d', 'maintainer-a',
              'maintainer-b', 'requester-', 'example-intake-bot', 'Placeholder', 'example.org', '0000-0000-0000-0001',
              'openalex.org/A300', '"9001"', '"9002"')


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('a test reached for the network or a subprocess')
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)
    monkeypatch.setattr(urllib.request.OpenerDirector, 'open', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(subprocess, 'run', refuse)
    monkeypatch.setattr(subprocess, 'Popen', refuse)
    for name in am.CREDENTIALS:
        monkeypatch.delenv(name, raising=False)


def transcript(path=MEASURED):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def rulings():
    return am.read_rulings(RULINGS)


def run(doc=None, ruled=None):
    return am.from_transcript(doc if doc is not None else transcript(), ruled if ruled is not None else rulings())


def changed(doc, part, **fields):
    """A copy of `doc` in which every exchange whose URL contains `part` answers with `fields` instead."""
    doc = copy.deepcopy(doc)
    hits = [e for e in doc['exchanges'] if part in e['url']]
    assert hits, part
    for e in hits:
        for key in ('status', 'body', 'error'):
            e.pop(key, None)
        e.update({'status': None, **fields})
    return doc


def unreachable(doc, part):
    return changed(doc, part, error='unreachable: [Errno 11001] getaddrinfo failed')


def dropped(doc, *parts):
    doc = copy.deepcopy(doc)
    doc['exchanges'] = [e for e in doc['exchanges'] if not any(p in e['url'] for p in parts)]
    return doc


def result(m, condition):
    return m.results[condition - 1]


# ---- the verify: all three conditions from the recorded fixture --------------------------------------------------

def test_the_measured_fixture_meets_all_three_conditions():
    m = run()
    assert [(r.condition, r.count, r.verdict) for r in m.results] == [(1, 3, 'MET'), (2, 3, 'MET'), (3, 5, 'MET')]
    assert m.verdict == 'MET'


# condition 1, by hand: the list holds 9 items -- 7 merged pull requests (#101-#106, #108) linking issues #11-#16
# and #18, one closed unmerged (#107), one issue carrying the label (#19). Issues #11 and #12 are one contributor
# (the login's case differs). Of 6 authors, contributor-a, -b and -c count; maintainer-a holds commit rights,
# maintainer-a-alt is ruled an alt account, transcriber[bot] is a bot.

def test_condition_1_counts_each_contributor_once():
    r = result(run(), 1)
    assert r.detail == {'merged_pull_requests': 7, 'linked_issues': 7, 'linked_pull_requests': 0, 'authors': 6,
                        'collaborators': 3, 'external': 3,
                        'excluded': {'a bot': 1, 'a maintainer or alt account': 1, 'commit rights': 1}}
    assert r.complete and r.reasons == []
    assert r.people['counted'] == ['contributor-a', 'contributor-b', 'contributor-c']


def test_condition_1_reads_only_the_issues_merged_pull_requests_close():
    urls = [e.url for e in run().exchanges]
    assert am.issue_url(REPO, 11) in urls and am.issue_url(REPO, 18) in urls
    assert am.issue_url(REPO, 17) not in urls          # #107 was closed unmerged
    assert am.issue_url(REPO, 19) not in urls          # #19 is an issue, not a pull request


def test_condition_1_needs_the_ruling_to_exclude_an_alt_account():
    r = result(run(ruled=am.Rulings()), 1)
    assert r.count == 4 and 'maintainer-a-alt' in r.people['counted']


def test_an_unreadable_collaborators_list_fails_condition_1_whatever_the_count():
    doc = changed(transcript(), '/collaborators', status=401, body={'message': 'Requires authentication'})
    r = result(run(doc), 1)
    assert r.count == 3 and r.verdict == 'FAILED' and not r.complete
    assert r.reasons == ['unmeasurable: GET %s: HTTP 401 (the collaborators list needs GH_TOKEN with push access)'
                         % am.collaborators_url(REPO, 1)]


def test_an_unreachable_pull_request_list_fails_condition_1_and_is_no_silent_zero():
    r = result(run(unreachable(transcript(), 'labels=source:issue-form')), 1)
    assert r.count == 0 and r.verdict == 'FAILED' and not r.complete
    assert r.reasons[0] == 'below the threshold on what could be measured: 0 < 3'
    assert any(x.startswith('unmeasurable: GET') and 'getaddrinfo' in x for x in r.reasons)


def test_a_failed_issue_lookup_fails_condition_1_only_while_below_the_threshold():
    below = result(run(changed(transcript(), '/issues/16', status=503)), 1)      # contributor-c unreadable
    assert below.count == 2 and below.verdict == 'FAILED'
    assert 'unmeasurable: GET %s: HTTP 503' % am.issue_url(REPO, 16) in below.reasons
    above = result(run(changed(transcript(), '/issues/14', status=503)), 1)      # a maintainer's issue unreadable
    assert above.count == 3 and above.verdict == 'MET' and not above.complete   # it could only have added one


def test_a_merged_pull_request_that_links_no_issue_is_unmeasured():
    doc = transcript()
    pr = next(i for i in doc['exchanges'][0]['body'] if i['number'] == 106)
    pr['body'] = 'Drafted from the form.'
    r = result(run(doc), 1)
    assert r.count == 2 and r.verdict == 'FAILED'
    assert 'unmeasurable: 1 merged pull request(s) link no issue, so their contributors are unknown: #106' in r.reasons


@pytest.mark.parametrize('body, issues', [
    ('From issue #12.\n\nCloses #12', [12]),
    ('fixes #3, resolves: #4 and Closed #5', [3, 4, 5]),
    ('Closes other-org/other-repo#9', []),
    ('This disclosed #7 and refixes #8', []),
    (None, []),
])
def test_linked_issues(body, issues):
    assert am.linked_issues(body) == issues


# condition 2, by hand: OpenAlex reads 2 citing works of the concept DOI (citing-external, by an outside author, and
# citing-self, by "Maintainer Placeholder"); DataCite lists 3 (citing-external, citing-datacite-only and our own
# version DOI); Semantic Scholar 2 (citing-external again, and p-0002 with no DOI). The version DOI is in neither
# OpenAlex nor Semantic Scholar. So 4 citing works outside our DOIs: 3 external, 1 self-citation.

def test_condition_2_counts_each_external_citing_work_once():
    r = result(run(), 2)
    assert r.counted == ['doi:10.5555/citing-datacite-only', 'doi:10.5555/citing-external', 's2:p-0002']
    assert r.detail['citing_works'] == 4 and r.detail['by_kind'] == {'external': 3, 'self-citation': 1}
    assert r.complete


def test_a_datacite_only_citation_takes_its_authors_from_an_openalex_lookup():
    doc = dropped(transcript(), 'doi:10.5555/citing-datacite-only')
    r = result(run(doc), 2)
    assert r.detail['by_kind'] == {'authors unknown': 1, 'external': 2, 'self-citation': 1}
    assert r.count == 2 and r.verdict == 'MET' and not r.complete


def test_not_indexed_is_recorded_and_never_zero():
    readings = {(rd['doi'], rd['instrument']): rd for rd in result(run(), 2).detail['readings']}
    assert readings[(VERSION, 'OpenAlex')] == {'doi': VERSION, 'instrument': 'OpenAlex', 'status': 'not-indexed',
                                               'count': None}
    assert readings[(VERSION, 'Semantic Scholar')]['status'] == 'not-indexed'
    assert readings[(VERSION, 'DataCite')] == {'doi': VERSION, 'instrument': 'DataCite', 'status': 'ok', 'count': 0}
    assert '| `10.5555/adoption-fixture.v1` | OpenAlex | not indexed | -- |' in am.block(run())


def test_without_a_maintainer_name_self_citation_is_unchecked_and_condition_2_fails():
    ruled = am.Rulings.parse({'maintainers': ['github:maintainer-a-alt'], 'unsolicited': [31, 32, 33, 34, 35]})
    r = result(run(ruled=ruled), 2)
    assert r.count == 0 and r.verdict == 'FAILED'
    assert r.detail['by_kind'] == {'not checked for self-citation': 4}
    assert any('not checked for self-citation' in x for x in r.reasons)


def test_a_failed_instrument_cannot_undo_a_citation_another_found():
    r = result(run(unreachable(transcript(), 'semanticscholar.org/graph/v1/paper/DOI:10.5555/adoption-fixture.concept')), 2)
    assert r.counted == ['doi:10.5555/citing-datacite-only', 'doi:10.5555/citing-external']
    assert r.verdict == 'MET' and not r.complete


def test_every_citation_instrument_unreachable_fails_condition_2():
    doc = transcript()
    for part in ('api.openalex.org', 'api.datacite.org', 'api.semanticscholar.org'):
        doc = unreachable(doc, part)
    r = result(run(doc), 2)
    assert r.count == 0 and r.verdict == 'FAILED' and not r.complete
    assert 'unmeasurable: no instrument returned a reading for any DOI' in r.reasons
    assert len([x for x in r.reasons if 'getaddrinfo' in x]) == 6       # three instruments, two DOIs


def test_a_datacite_count_beyond_its_list_fails_that_reading():
    doc = transcript(NOTHING_YET)
    dc = next(e for e in doc['exchanges'] if e['url'] == am.datacite_url(CONCEPT))
    dc['body']['data']['attributes']['citationCount'] = 1
    r = result(run(doc, am.Rulings()), 2)
    assert r.verdict == 'FAILED'
    assert 'unmeasurable: DataCite for %s: counts 1 citation(s) but lists 0 citing DOI(s)' % CONCEPT in r.reasons


# condition 3, by hand: 7 issues labelled request:rerun (#31-#37) and a pull request (#38). The rulings call #31-#35
# unsolicited -- #34 a maintainer's transcription of an e-mail, which still counts -- and #36 solicited; #37 has none.

def test_condition_3_counts_only_requests_ruled_unsolicited():
    r = result(run(), 3)
    assert r.counted == ['#31', '#32', '#33', '#34', '#35']
    assert r.detail == {'labelled': 7, 'unsolicited': 5, 'solicited': 1, 'unjudged': 1, 'ruled_but_not_labelled': 0}
    assert r.verdict == 'MET' and not r.complete               # #37 could only have added one


def test_an_unjudged_request_fails_condition_3_while_below_the_threshold():
    ruled = am.Rulings.parse({'maintainers': ['name:Maintainer Placeholder'], 'unsolicited': [31, 32, 33, 34],
                              'solicited': [36]})
    r = result(run(ruled=ruled), 3)
    assert r.count == 4 and r.verdict == 'FAILED'
    assert 'unmeasurable: 2 labelled request(s) carry no ruling on whether they were unsolicited: #35, #37' in r.reasons


def test_without_rulings_condition_3_has_no_judgement_and_fails():
    r = result(run(ruled=am.Rulings()), 3)
    assert r.count == 0 and r.verdict == 'FAILED' and r.detail['unjudged'] == 7


def test_nothing_yet_fails_all_three_on_complete_measurements():
    m = run(transcript(NOTHING_YET), am.Rulings())
    assert [(r.count, r.verdict, r.complete) for r in m.results] == [(0, 'FAILED', True)] * 3
    assert [r.reasons for r in m.results] == [['below the threshold: 0 < 3'], ['below the threshold: 0 < 1'],
                                              ['below the threshold: 0 < 5']]
    assert m.verdict == 'FAILED'


# ---- the verify: an injected failure is FAILED, never a silent zero or an unknown --------------------------------

def test_an_unreachable_network_fails_every_condition(monkeypatch, capsys):
    def offline(req, timeout=None):
        raise urllib.error.URLError('no network in the tests')
    monkeypatch.setattr(urllib.request, 'urlopen', offline)
    monkeypatch.setattr(am.time, 'sleep', lambda s: None)
    assert am.main(['--live', '--json', '--repo', REPO]) == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report['gate'] == 'FAILED'
    for c in report['conditions']:
        assert c['verdict'] == 'FAILED' and c['complete'] is False and c['count'] == 0
        assert c['reasons'][0].startswith('below the threshold on what could be measured')
        assert any(x.startswith('unmeasurable: ') and 'no network in the tests' in x for x in c['reasons'])
    assert 'UNKNOWN' not in out.upper().replace('UNKNOWN_', '')


@pytest.mark.parametrize('doc, gate', [
    (unreachable(transcript(), 'labels=source:issue-form'), 'FAILED'),
    (changed(transcript(), '/collaborators', status=403), 'FAILED'),
    (unreachable(transcript(), 'api.datacite.org'), 'MET'),        # OpenAlex and Semantic Scholar found citations
    (changed(transcript(), 'labels=request:rerun', status=200, body={'message': 'not a list'}), 'FAILED'),
    (dropped(transcript(), 'api.github.com'), 'FAILED'),
])
def test_no_verdict_is_ever_unknown(doc, gate):
    m = run(doc)
    for r in m.results:
        assert r.verdict in ('MET', 'FAILED')
        assert isinstance(r.count, int)
        if not r.complete and r.count < r.threshold:
            assert r.verdict == 'FAILED' and any(x.startswith('unmeasurable: ') for x in r.reasons)
    assert m.verdict == gate


def test_a_url_the_recording_lacks_is_a_failed_request():
    ex = am.Replay([])(am.datacite_url(CONCEPT))
    assert not ex.ok and ex.status is None and ex.error == 'not in the recording'


# ---- the network, only when asked ---------------------------------------------------------------------------------

def test_the_plan_requests_nothing_and_prints_no_credential(monkeypatch, capsys):
    monkeypatch.setenv('GH_TOKEN', 'gh-placeholder-secret')
    assert am.main([]) == 0                         # urlopen raises: had anything been requested, this would fail
    out = capsys.readouterr().out
    assert 'nothing was requested' in out and 'GH_TOKEN: set' in out and 'OPENALEX_API_KEY: not set' in out
    assert 'placeholder-secret' not in out
    assert am.issues_url(am.REPO, am.FORM_LABEL, 'closed', 1) in out


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status, self._body, self.headers = status, body, headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_live_transport_keeps_every_credential_inside_it():
    sent = []

    def opener(req, timeout=None):
        sent.append(req)
        raise urllib.error.URLError('refused at %s' % req.full_url)     # an error that would leak the URL's key
    env = {'GH_TOKEN': 'gh-placeholder-secret', 'OPENALEX_API_KEY': 'oa-placeholder-secret',
           'SEMANTIC_SCHOLAR_API_KEY': 's2-placeholder-secret'}
    live = am.Live(env=env, opener=opener, sleep=lambda s: None)
    m = am.measure(live, REPO, [CONCEPT], am.Rulings(), '2027-01-15', live.credentials())
    gh = next(r for r in sent if 'api.github.com' in r.full_url)
    oa = next(r for r in sent if 'api.openalex.org' in r.full_url)
    s2 = next(r for r in sent if 'api.semanticscholar.org' in r.full_url)
    dc = next(r for r in sent if 'api.datacite.org' in r.full_url)
    assert gh.get_header('Authorization') == 'Bearer gh-placeholder-secret'
    assert 'api_key=oa-placeholder-secret' in oa.full_url
    assert s2.get_header('X-api-key') == 's2-placeholder-secret'
    assert dc.get_header('Authorization') is None and 'secret' not in dc.full_url
    assert m.credentials == {'GH_TOKEN': True, 'OPENALEX_API_KEY': True, 'SEMANTIC_SCHOLAR_API_KEY': True}
    out = am.block(am.published(m)) + json.dumps(am.report(m, identify=True))
    assert 'placeholder-secret' not in out and '[credential]' in out
    assert all('api_key' not in e.url for e in m.exchanges)


def test_the_live_transport_spaces_requests_and_retries_a_503():
    now, calls = [0.0], []

    def sleep(s):
        now[0] += s

    def opener(req, timeout=None):
        calls.append(now[0])
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 503, 'busy', {}, io.BytesIO(b''))
        return FakeResponse(200, b'[]')
    live = am.Live(env={}, opener=opener, clock=lambda: now[0], sleep=sleep)
    first = live(am.issues_url(REPO, am.FORM_LABEL, 'closed', 1))
    second = live(am.collaborators_url(REPO, 1))
    assert first.ok and first.body == [] and second.ok
    assert len(calls) == 3
    assert calls[1] - calls[0] >= 1.0 and calls[2] - calls[1] >= 1.0      # 06 S9.6: one second apart on GitHub
    assert live(am.collaborators_url(REPO, 1)) is second and len(calls) == 3   # each URL once


def test_the_live_transport_records_spent_retries_and_policy_refusals(monkeypatch):
    def busy(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 503, 'busy', {}, io.BytesIO(b''))
    ex = am.Live(env={}, opener=busy, sleep=lambda s: None)(am.datacite_url(CONCEPT))
    assert ex.status == 503 and not ex.ok and ex.error.startswith('retries spent: ')
    from ingest.http import policy

    def forbid(url):
        raise policy.Forbidden(url, 'a test rule')
    monkeypatch.setattr(policy, 'refuse', forbid)
    ex = am.Live(env={}, opener=busy, sleep=lambda s: None)(am.datacite_url(CONCEPT))
    assert ex.status is None and ex.error == 'refused by ingest/policy.yaml: a test rule'


# ---- the raw output, naming no one -------------------------------------------------------------------------------

def test_the_default_output_names_no_one(capsys):
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS]) == 0
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS, '--json']) == 0
    out = capsys.readouterr().out
    leaked = [s for s in IDENTITIES if s in out]
    assert leaked == []
    assert '"login": "github-' in out and '"display_name": "name-' in out and '"orcid": "orcid-' in out
    assert am.DROPPED in out and 'Thanks @github-' in out            # the mention is the issue author's alias


def test_identify_keeps_the_identities_and_never_goes_into_a_file(capsys, tmp_path):
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS, '--identify']) == 0
    out = capsys.readouterr().out
    assert 'condition 1, counted: contributor-a, contributor-b, contributor-c' in out
    assert 'do not commit this' in out and 'contributor-a@example.org' in out
    with pytest.raises(SystemExit) as e:
        am.main(['--replay', MEASURED, '--identify', '--write', str(tmp_path / 'q.md')])
    assert e.value.code == 2 and not (tmp_path / 'q.md').exists()


def test_the_redacted_raw_output_replays_to_the_same_measurement():
    m = run()
    replayed = am.from_transcript(am.transcript(m))
    assert replayed.redacted
    assert [(r.count, r.verdict, r.reasons, r.detail, r.counted) for r in replayed.results] == \
        [(r.count, r.verdict, r.reasons, r.detail, r.counted) for r in m.results]
    assert am.block(am.published(m)) == am.block(replayed)
    ruled = am.transcript(m)['rulings']                        # the identities the run saw, as their aliases
    kinds = [re.fullmatch(r'(github|name):(github|name)-\d+', x).group(1) for x in ruled['maintainers']]
    assert kinds == ['github', 'name']
    assert ruled['supplied'] == {'github': 1, 'name': 1}
    assert ruled['unsolicited'] == [31, 32, 33, 34, 35] and ruled['solicited'] == [36]


def test_redaction_never_touches_the_urls_dois_and_ids_a_replay_reads():
    doc = transcript()
    issue = next(e for e in doc['exchanges'] if e['url'] == am.issue_url(REPO, 16))
    issue['body']['user']['login'] = 'citing-external'          # a login that is also a citing DOI's suffix
    m = run(doc)
    pub = am.published(m)                                       # raises if redaction moved a count
    assert result(pub, 2).counted == result(m, 2).counted and 'doi:10.5555/citing-external' in result(pub, 2).counted
    assert [e.url for e in pub.exchanges] == [e.url for e in m.exchanges]


def test_bot_and_organisation_accounts_are_not_people():
    r = am.Redactor()
    out = r.exchanges([{'url': 'u', 'status': 200, 'body': [{'login': 'transcriber[bot]', 'type': 'Bot'},
                                                            {'login': 'example-org', 'type': 'Organization'},
                                                            {'login': 'contributor-a', 'type': 'User'}]}])
    assert [u['login'] for u in out[0]['body']] == ['transcriber[bot]', 'example-org', 'github-1']


def test_a_condition_met_on_partial_data_says_what_was_not_measured():
    assert ('- condition 3: met; not measured, and able only to add: 1 labelled request(s) carry no ruling on '
            'whether they were unsolicited: #37') in am.block(am.published(run()))


# ---- publishing: --write and --validate --------------------------------------------------------------------------

def confirm(path):
    text = path.read_text(encoding='utf-8')
    for label in am.CONFIRMATIONS:
        text = text.replace('- **%s:** --' % label, '- **%s:** 2027-01-20, checked against the rulings' % label)
    path.write_text(text, encoding='utf-8', newline='\n')


def test_write_then_validate(tmp_path, capsys):
    doc = tmp_path / '2027-Q1.md'
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS, '--write', str(doc)]) == 0
    text = doc.read_text(encoding='utf-8')
    assert text.startswith('# Adoption measurement, run on 2027-01-15\n')
    assert '**The gate: MET.**' in text and '## Human rulings' in text and '## Corroborating signals' in text
    assert [s for s in IDENTITIES if s in text] == []
    capsys.readouterr()
    assert am.main(['--validate', str(doc)]) == 1                  # the rulings are not confirmed yet
    err = capsys.readouterr().err
    assert '"Condition 1: exclusions confirmed" is not filled in' in err and 'does not replay' not in err
    confirm(doc)
    assert am.main(['--validate', str(doc)]) == 0
    assert 'replays and is confirmed (gate MET)' in capsys.readouterr().out
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS, '--write', str(doc)]) == 0   # a rewrite
    assert '2027-01-20, checked against the rulings' in doc.read_text(encoding='utf-8')     # keeps the person's
    assert am.main(['--validate', str(doc)]) == 0


@pytest.mark.parametrize('old, new', [
    ('| ≥ 3 | 3 | **MET** |', '| ≥ 3 | 4 | **MET** |'),                                  # an edited count
    ('"merged_at": "2027-01-06T10:00:00Z"', '"merged_at": null'),                         # edited raw output
    ('"unsolicited": [\n   31,', '"unsolicited": [\n   30,'),                              # an edited ruling
])
def test_validate_catches_an_edit(tmp_path, capsys, old, new):
    doc = tmp_path / '2027-Q1.md'
    assert am.main(['--replay', MEASURED, '--rulings', RULINGS, '--write', str(doc)]) == 0
    confirm(doc)
    text = doc.read_text(encoding='utf-8')
    assert text.count(old) == 1
    doc.write_text(text.replace(old, new), encoding='utf-8', newline='\n')
    assert am.main(['--validate', str(doc)]) == 1
    assert 'does not replay from its own raw output' in capsys.readouterr().err


def test_validate_refuses_a_file_with_no_block(tmp_path, capsys):
    doc = tmp_path / 'empty.md'
    doc.write_text('# Nothing here\n', encoding='utf-8')
    assert am.main(['--validate', str(doc)]) == 2
    assert 'no generated block' in capsys.readouterr().err


# ---- inputs ------------------------------------------------------------------------------------------------------

def test_the_dois_come_from_instruments_md(tmp_path):
    dois = am.dois_from(ROOT)
    assert dois[0] == '10.5281/zenodo.23045827'                     # the concept DOI, first in the table
    assert len(dois) >= 2 and all(d.startswith('10.5281/zenodo.') for d in dois)
    (tmp_path / 'docs' / 'adoption').mkdir(parents=True)
    (tmp_path / 'docs' / 'adoption' / 'instruments.md').write_text('# No table\n', encoding='utf-8')
    with pytest.raises(ValueError, match='no "## The DOIs" section'):
        am.dois_from(str(tmp_path))


def test_the_rulings_fixture_parses():
    r = rulings()
    assert r.maintainers == frozenset({('github', 'maintainer-a-alt'), ('name', 'maintainer placeholder')})
    assert r.unsolicited == frozenset({31, 32, 33, 34, 35}) and r.solicited == frozenset({36})
    assert r.checks_self_citation


@pytest.mark.parametrize('doc, message', [
    ({'maintainers': ['twitter:someone-invented']}, 'maintainer entry 1 is not <kind>:<value>'),
    ({'maintainers': ['no-kind-at-all']}, 'maintainer entry 1 is not <kind>:<value>'),
    ({'unsolicited': [3], 'solicited': [3]}, 'ruled both unsolicited and solicited: #3'),
    ({'unsolicited': ['3']}, 'unsolicited is not a list of issue numbers'),
    ({'exclusions': []}, 'unknown key'),
])
def test_bad_rulings_are_refused_without_echoing_an_identity(doc, message):
    with pytest.raises(ValueError, match=message) as e:
        am.Rulings.parse(doc)
    assert 'someone-invented' not in str(e.value)


def test_a_transcript_of_another_shape_is_refused(tmp_path, capsys):
    bad = tmp_path / 't.json'
    bad.write_text(json.dumps({'format': 99}), encoding='utf-8')
    assert am.main(['--replay', str(bad)]) == 2
    assert 'not a format-1 adoption transcript' in capsys.readouterr().err
