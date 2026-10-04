"""Tests for ingest/adapters/openalex.py, institution and ROR resolution (P4-S2-T06; 06 S3.10).

The verify is `bench ingest openalex --dry-run --limit 20` (run live, with a key, for the PR). These replay
the responses tests/fixtures/openalex/capture.py recorded on 2026-10-04, with sockets disabled.
"""
import json
import os
import socket
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import openalex as oa  # noqa: E402
from ingest.http.backoff import Response  # noqa: E402
from ingest.http.fixture import FixtureTransport  # noqa: E402
from tools import cli  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures', 'openalex')
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def inst(name, ror='https://ror.org/0abcdefgh', country='US', alts=(), acronyms=(), wd=None):
    return {'id': 'https://openalex.org/I%d' % (abs(hash(name)) % 10**8), 'display_name': name, 'ror': ror,
            'country_code': country, 'display_name_alternatives': list(alts), 'display_name_acronyms': list(acronyms),
            'ids': {'wikidata': 'https://www.wikidata.org/wiki/%s' % wd} if wd else {}}


# ---- the recorded run ----------------------------------------------------------------------------------

def test_every_curated_organisation_resolves_through_the_recorded_responses():
    report = oa.run(FixtureTransport(FIX))
    assert report['status'] == 'ok' and report['errors'] == [] and report['unresolved'] == 0
    assert report['candidates_seen'] == 6 and report['drafts']['field-change'] == 6
    got = {p.split(' -> ')[0]: p for p in report['proposals']}
    assert 'ror=https://ror.org/05wx9n238' in got['org-openai'] and 'country=US' in got['org-openai']
    assert "'Google DeepMind (United Kingdom)'" in got['org-google-deepmind'] and 'country=GB' in got['org-google-deepmind']
    assert 'wikidata=Q131577453' in got['org-deepseek']
    assert report['allowance']['X-RateLimit-Limit'] == '10000'          # the meter, recorded every run


def test_limit_caps_the_organisations_asked_about():
    assert oa.run(FixtureTransport(FIX), limit=2)['candidates_seen'] == 2


def test_the_url_carries_no_key_and_asks_only_for_what_is_read():
    url = oa.institutions_url('OpenAI')
    assert 'api_key' not in url and 'select=id%2Cdisplay_name' in url and 'per-page=5' in url
    assert all('api_key' not in json.load(open(os.path.join(FIX, n), encoding='utf-8'))['url']
               for n in os.listdir(FIX) if n.endswith('.headers.json'))


def test_the_key_is_added_inside_the_network_transport_only(monkeypatch):
    seen = []

    class Answer:
        status, headers = 200, {}

        def read(self):
            return b'{"results": []}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        return Answer()
    monkeypatch.setattr(oa.urllib.request, 'urlopen', fake_urlopen)
    t = oa.NetworkTransport('k3y', clock=lambda: 0.0, sleep=lambda s: None)
    t.get(oa.institutions_url('OpenAI'), {})
    oa.NetworkTransport(None, clock=lambda: 0.0, sleep=lambda s: None).get(oa.institutions_url('OpenAI'), {})
    assert seen[0].endswith('&api_key=k3y') and 'api_key' not in seen[1]


# ---- matching ------------------------------------------------------------------------------------------

def test_the_country_tail_alternatives_and_acronyms_count_as_names():
    assert 'openai' in oa.labels(inst('OpenAI (United States)'))
    assert 'cmu' in oa.labels(inst('Carnegie Mellon University', acronyms=['CMU']))
    # 'open ai' is not 'openai': normalising does not join words, so this is no match, not a guess
    drafts, unresolved = oa.normalise_org('org-x', 'Open AI', {'id': 'org-x'}, [inst('OpenAI (United States)')])
    assert drafts == [] and unresolved[0].reason == 'no-match'


def test_two_institutions_with_the_name_are_ambiguous_and_nothing_is_applied():
    results = [inst('Anthropic (United States)', 'https://ror.org/056y0v115'),
               inst('Anthropic', 'https://ror.org/0zzzzzzzz')]
    drafts, [u] = oa.normalise_org('org-anthropic', 'Anthropic', {'id': 'org-anthropic'}, results)
    assert drafts == [] and u.reason == 'ambiguous-match'
    assert [s[0] for s in u.suggestions] == ['https://ror.org/056y0v115', 'https://ror.org/0zzzzzzzz']


def test_a_lookalike_is_only_a_suggestion():
    results = [inst('Institute for the Study of Anthropic Impact', 'https://ror.org/013fk0013')]
    drafts, [u] = oa.normalise_org('org-anthropic', 'Anthropic', {'id': 'org-anthropic'}, results)
    assert drafts == [] and u.reason == 'no-match' and u.suggestions == [('https://ror.org/013fk0013', 0.0)]


def test_the_patch_carries_ror_wikidata_and_country():
    [d], _ = oa.normalise_org('org-x', 'Example Lab', {'id': 'org-x'},
                              [inst('Example Lab (France)', 'https://ror.org/0abcdefgh', 'FR', wd='Q123')])
    assert d.payload == {'ror': 'https://ror.org/0abcdefgh', 'wikidata': 'Q123', 'country': 'FR'}
    assert (d.entity_type, d.entity_id, d.change_class) == ('organization', 'org-x', 'field-change')


def test_a_held_field_is_never_overwritten_and_a_disagreement_is_reported():
    record = {'id': 'org-x', 'country': 'US'}
    [d], [u] = oa.normalise_org('org-x', 'Example Lab', record, [inst('Example Lab', country='GB')])
    assert 'country' not in d.payload and u.reason == 'policy' and "holds country 'US'" in u.human_task


def test_a_patch_that_would_not_validate_is_an_error():
    report_inst = inst('Example Lab', ror='https://example.org/not-a-ror')
    [d], _ = oa.normalise_org('org-x', 'Example Lab', {'id': 'org-x'}, [report_inst])
    record = {'id': 'org-x', 'name': 'Example Lab', 'kind': 'company', 'sources': ['src-x']}
    assert 'organization org-x' in oa.validate_patch(d, record)


# ---- statuses and the command --------------------------------------------------------------------------

class Fixed:
    def __init__(self, status, body=b'{"results": []}'):
        self.r = Response(status, [('X-RateLimit-Remaining', '0')], body)

    def get(self, url, headers):
        return self.r


def test_a_spent_budget_is_a_soft_fail():
    report = oa.run(Fixed(429))
    assert report['status'] == 'soft-fail' and 'daily budget' in report['errors'][0]
    assert report['allowance'] == {'X-RateLimit-Remaining': '0'}


def test_any_other_error_is_a_hard_fail_that_names_no_key():
    report = oa.run(Fixed(403))
    assert report['status'] == 'hard-fail' and 'HTTP 403' in report['errors'][0] and 'api_key' not in report['errors'][0]


def test_the_command_replays_the_fixture_and_exits_0():
    r = runner.invoke(cli.app, ['ingest', 'openalex', '--dry-run', '--fixture', FIX, '--limit', '20'])
    assert r.exit_code == 0, r.output
    assert 'field-change  6' in r.output and 'proposal: org-openai' in r.output and 'allowance' in r.output


def test_no_network_without_a_fixture_exits_2():
    r = runner.invoke(cli.app, ['ingest', 'openalex', '--dry-run', '--no-network'])
    assert r.exit_code == 2 and 'needs --fixture' in r.output
