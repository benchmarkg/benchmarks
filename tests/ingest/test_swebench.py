"""The SWE-bench leaderboard adapter (P5-S6-T03; 06 S3.7, 07 S1.5, S8.2).

Verified against tests/ingest/fixtures/swebench/: a synthetic page with the real page's shape (five leaderboards,
323 results, every key and type mix) and none of its content, because the real page is no-redistribution and may
not be committed. The fixture's README says how it was built; make_fixture.py rebuilds it byte for byte.

  - the inline JSON is extracted and parsed: five leaderboards, 323 results; every result becomes a claim draft
    that validates as a ResultClaim and its EvalConditions once its references resolve, or a human task;
  - the mapping is 06 S3.7's: agent_org reports it, checked is the ladder, logs/trajs link (s3:// as https),
    reasoning_effort and cost are conditions, the warning is kept -- and instance_calls is NOT max_steps;
  - the hash is of the extracted JSON without logo and site, so a page whose logos rotate is no change;
  - the failure case: a row count down by more than 10% is a semantic anomaly labelled needs-scrutiny, nothing is
    classed gone, and the accepted counts are kept; a missing or broken script tag is drift, a hard fail;
  - every draft is held by the licence firewall, no raw body is kept, and the s3 bucket is never fetched.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil

import pytest
from typer.testing import CliRunner

from ingest import gates
from ingest.adapters import swebench as S
from ingest.http import policy as P
from ingest.http.fixture import FixtureTransport
from ingest.resolve import Entry, Index
from schema.claim import ResultClaim, check_source_record_id
from schema.conditions import EvalConditions
from schema.taxonomy import read_yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'swebench')
_spec = importlib.util.spec_from_file_location('swebench_fixture', os.path.join(FIX, 'make_fixture.py'))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 9, 20, 5, tzinfo=timezone.utc)


def resolvers():
    """A frozen resolver over a handful of records: the pinned submissions, two labs, Verified and the full split."""
    return {
        'system': Index('system', [Entry('pinned-agent-model-a', 'Pinned Agent + Model A'),
                                   Entry('pinned-agent-model-b', 'Pinned Agent + Model B'),
                                   Entry('second-agent-model-a', 'Second Agent + Model A'),
                                   Entry('second-agent-model-c', 'Second Agent + Model C'),
                                   Entry('model-a', 'Model A')]),
        'organization': Index('organization', [Entry('org-example-lab-1', 'Example Lab 1'),
                                               Entry('org-example-lab-2', 'Example Lab 2')]),
        'benchmark': Index('benchmark', [Entry('swe-bench-verified', 'SWE-bench Verified'), Entry('swe-bench', 'SWE-bench')]),
        'metric': Index('metric', [Entry('swe-bench-verified-score', 'SWE-bench Verified resolve rate')]),
    }


class Everything:
    """A resolver that resolves any string: what the drafts look like once every record exists."""

    class Hit:
        def __init__(self, entity):
            self.entity, self.version, self.score = entity, None, 1.0

    def __init__(self, kind):
        self.kind = kind

    def resolve(self, raw):
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', raw.lower()).strip('-')
        return self.Hit('%s:%s%s' % (self.kind, 'org-' if self.kind == 'organization' else '', slug))


def everything():
    return {k: Everything(k) for k in ('system', 'organization', 'benchmark', 'metric')}


def page(data=None, salt='v1'):
    return S.Page(M.page(M.boards() if data is None else data, salt), retrieved_at=_now())


def run(p=None, state=None, res=None):
    return S.run(S.SweBench(page=p or page(), now=_now), state if state is not None else S.new_state(),
                 res or resolvers())


def by_record(report):
    return {d['ingestion']['source_record_id']: d for d in report['documents']}


def minted(doc):
    """What the runner will write (07 S1.4): the conditions split out, both ids minted. Placeholder ids here."""
    doc = dict(doc)
    doc.pop('path')
    cond = doc.pop('eval_conditions')
    ingestion = dict(doc.pop('ingestion'), extraction_confidence=1.0)
    return (EvalConditions(id='cond-000000000000', **cond),
            ResultClaim(id='claim-000000000000', eval_conditions='cond-000000000000', ingestion=ingestion, **doc))


# ---- the fixture -----------------------------------------------------------------------------------------------

def test_the_committed_fixture_is_what_its_generator_writes(tmp_path):
    M.write(str(tmp_path))
    for name in ('page.html', 'page.html.headers.json'):
        with open(os.path.join(FIX, name), 'rb') as a, open(tmp_path / name, 'rb') as b:
            assert a.read().replace(b'\r\n', b'\n') == b.read(), name


def test_five_leaderboards_and_323_results_parse_from_the_page():
    with open(os.path.join(FIX, 'page.html'), 'rb') as f:
        p = S.Page(f.read())
    assert p.counts() == {'Multilingual': 13, 'Test': 24, 'Verified': 180, 'Lite': 84, 'Multimodal': 22}
    assert sum(p.counts().values()) == 323


def test_every_result_is_a_valid_claim_draft_or_a_human_task_once_references_resolve():
    report = run(res=everything())
    docs = report['documents']
    held_back = report['unresolved_by_field']
    assert set(held_back) <= {'claim.reported_by', 'claim.verification'}
    rows = [r for b in M.boards() for r in b['results']]
    no_org = sum(1 for r in rows if not r['agent_org'])
    bad_rung = sum(1 for r in rows if r['agent_org'] and S.verification(r['checked']) is None)
    assert len(docs) == report['drafts']['new'] == 323 - no_org - bad_rung
    assert no_org > 90                                  # a third of rows, as on the real page
    for d in docs:
        minted(d)                                       # validates as both entities
        gates.metadata_only({k: v for k, v in d.items() if k != 'path'}, d['path'] + 'claim-000000000000.yaml')
        check_source_record_id(d['ingestion']['source_record_id'])


def test_normalise_is_a_pure_function_of_the_payload():
    a, b = run(), run()
    assert a['documents'] == b['documents'] and a['unresolved_by_field'] == b['unresolved_by_field']


# ---- the mapping (06 S3.7) -------------------------------------------------------------------------------------

def test_a_checked_submission_maps_as_06_s3_7_says():
    d = by_record(run())['Verified#folder=20260301_pinned-agent_model-a']
    assert d['path'] == 'data/claims/_ingested/swe-bench/swe-bench-verified/'
    assert (d['system'], d['benchmark'], d['metric'], d['reported_by']) == \
        ('pinned-agent-model-a', 'swe-bench-verified', 'swe-bench-verified-score', 'org-example-lab-1')
    assert d['value'] == 0.614 and d['date_reported'] == '2026-03-01' and d['source'] == 'src-swebench-leaderboard'
    assert d['verification'] == 'maintainer-verified'                       # checked: true
    assert d['artifact_url'] == ('https://swe-bench-submissions.s3.amazonaws.com/verified/'
                                 '20260301_pinned-agent_model-a/logs')
    assert d['eval_conditions'] == {'reasoning_effort': 'high', 'reasoning_effort_raw': 'high', 'cost_usd': 123.456789}
    assert d['notes'] == 'SWE-bench marks this entry: Uses a repository-level hint file; see the submission README.'
    assert d['ingestion']['licence_class'] == 'no-redistribution'
    assert d['ingestion']['field_provenance']['artifact_url'] == 'derived'


def test_instance_calls_is_a_mean_and_never_written_as_max_steps():
    d = by_record(run())['Verified#folder=20260301_pinned-agent_model-a']
    assert 'max_steps' not in d['eval_conditions']                         # the row's instance_calls is 28.853333
    assert d['ingestion']['field_provenance']['eval_conditions.max_steps'] == 'absent'
    for doc in run(res=everything())['documents']:
        assert 'max_steps' not in doc['eval_conditions']


def test_an_unchecked_row_is_self_reported_and_an_unusable_link_is_absent():
    d = by_record(run())['Verified#folder=20260303_second-agent_model-a']
    assert d['verification'] == 'self-reported'                             # checked: null
    assert d['artifact_url'] is None                                        # logs false, trajs a relative path
    assert d['ingestion']['field_provenance']['artifact_url'] == 'absent'
    # an effort outside the vocabulary keeps its verbatim string and is never coerced (04 S8)
    assert d['eval_conditions'] == {'reasoning_effort': None, 'reasoning_effort_raw': 'Thinking-32k'}


@pytest.mark.parametrize('checked, rung', [(True, 'maintainer-verified'), (False, 'self-reported'), (None, 'self-reported'),
                                           (M.NOT_VERIFIED, 'self-reported'), ('pending review', None), (1, None)])
def test_checked_onto_the_ladder(checked, rung):
    assert S.verification(checked) == rung


def test_rows_that_cannot_be_drafted_become_human_tasks_never_guesses():
    report = run()
    docs = by_record(report)
    assert 'Verified#folder=20260302_pinned-agent_model-b' not in docs      # agent_org null: who reported it?
    assert 'Verified#folder=20260304_second-agent_model-c' not in docs      # checked: "pending review"
    u = {(x.field, x.observed): x
         for x in S.normalise(page().payload_for(S.Candidate('board:Verified', 'claim', S.PAGE_URL)), resolvers())[1]}
    assert ('claim.verification', "'pending review'") in u
    assert ('claim.reported_by', '(null)') in u
    assert 'SWE-bench/experiments pull request' in u[('claim.reported_by', '(null)')].human_task
    unknown = [x for (f, _), x in u.items() if f == 'claim.system']
    assert unknown and all('built_on' in x.human_task for x in unknown)


def test_an_unknown_system_suggests_its_model_and_is_never_created():
    u = S.normalise(page().payload_for(S.Candidate('board:Verified', 'claim', S.PAGE_URL)), resolvers())[1]
    on_a = [x for x in u if x.field == 'claim.system' and x.observed.endswith('+ Model A')]
    assert on_a and all(x.suggestions == [('system:model-a', 1.0)] for x in on_a)


def test_a_leaderboard_whose_records_are_missing_is_one_task_and_no_drafts():
    report = run()
    assert report['drafts_by_board'] == {'Multilingual': 0, 'Test': 0, 'Verified': 2, 'Lite': 0, 'Multimodal': 0}
    p = page()
    test_board = S.normalise(p.payload_for(S.Candidate('board:Test', 'claim', S.PAGE_URL)), resolvers())
    assert test_board[0] == [] and [(x.field, x.observed) for x in test_board[1]] == [('metric', 'swe-bench-score')]
    lite = S.normalise(p.payload_for(S.Candidate('board:Lite', 'claim', S.PAGE_URL)), resolvers())[1]
    assert [(x.field, x.observed) for x in lite] == [('benchmark', 'swe-bench-lite'), ('metric', 'swe-bench-lite-score')]
    data = M.boards()
    data[0]['name'] = 'Bash Only'                       # a leaderboard the stanza does not name
    odd = S.normalise(page(data).payload_for(S.Candidate('board:Bash Only', 'claim', S.PAGE_URL)), resolvers())
    assert odd[0] == [] and [(x.field, x.reason) for x in odd[1]] == [('leaderboard', 'no-match')]


# ---- hashing and conditional fetches (07 S1.5) -----------------------------------------------------------------

def test_the_hash_is_of_the_extracted_json_without_logo_and_site():
    data = M.boards()
    a = page(data, salt='v1')
    for b in data:
        for r in b['results']:
            r['logo'] = ['img/logos/rotated-%s.png' % r['folder']]
            r['site'] = 'https://cdn.example.org/%s' % r['folder']
    b = page(data, salt='v2')                            # different bytes, different logos and sites
    assert a.sha256 == b.sha256
    data[2]['results'][0]['resolved'] = 61.5
    assert page(data).sha256 != a.sha256
    assert S.SweBench.volatile_fields == ('logo', 'site')


def test_an_unchanged_hash_is_no_change_whatever_the_page_bytes_did(tmp_path):
    M.write(str(tmp_path), logo_salt='v2')
    state = dict(S.new_state(), sha256=page().sha256)
    report = S.run(S.SweBench(FixtureTransport(str(tmp_path)), now=_now), state, resolvers())
    assert report['status'] == 'no-change' and report['documents'] == []


def test_a_304_is_no_change_and_the_validator_is_if_modified_since():
    transport = FixtureTransport(FIX)
    state = S.new_state()
    first = S.run(S.SweBench(transport, now=_now), state, resolvers())
    assert first['status'] == 'ok' and state['last_modified'] == M.LAST_MODIFIED
    assert state['counts'] == {'Multilingual': 13, 'Test': 24, 'Verified': 180, 'Lite': 84, 'Multimodal': 22}
    second = S.run(S.SweBench(transport, now=_now), state, resolvers())
    assert second['status'] == 'no-change' and state['last_status'] == 304
    assert transport.requests[1] == (S.PAGE_URL, {'If-Modified-Since': M.LAST_MODIFIED})
    assert first['snapshot']['artefact_sha256'] == page().sha256 and first['snapshot']['http_etag'] is None


# ---- the failure case: a semantic anomaly is not a deletion (06 S3.7, 07 S8.2) ----------------------------------

def _drop(n, board='Verified'):
    data = M.boards()
    b = next(x for x in data if x['name'] == board)
    b['results'] = b['results'][:len(b['results']) - n]
    return data


def test_a_row_count_drop_over_10_percent_is_a_semantic_anomaly_not_a_deletion():
    accepted = {'Multilingual': 13, 'Test': 24, 'Verified': 180, 'Lite': 84, 'Multimodal': 22}
    state = dict(S.new_state(), counts=dict(accepted))
    report = run(page(_drop(19)), state)                # 161 of 180: down 10.6%
    assert report['anomalies'] == ['leaderboard Verified holds 161 results, down from 180 (-11%)']
    assert report['labels'] == ['needs-scrutiny'] and report['status'] == 'ok'
    assert report['drafts']['gone'] == 0                # nothing is deleted
    assert state['counts'] == accepted                  # and the anomalous run does not become the baseline
    assert report['drafts']['new'] == 2                 # the claims still present still draft


def test_a_drop_of_exactly_10_percent_is_not_an_anomaly_and_becomes_the_baseline():
    state = dict(S.new_state(), counts={'Multilingual': 13, 'Test': 24, 'Verified': 180, 'Lite': 84, 'Multimodal': 22})
    report = run(page(_drop(18)), state)                # 162 of 180: exactly 10%
    assert report['anomalies'] == [] and report['labels'] == []
    assert state['counts']['Verified'] == 162


def test_a_vanished_leaderboard_and_a_whole_page_drop_are_anomalies():
    assert S.anomalies({'A': 100}, {'A': 100, 'B': 50}) == [
        'leaderboard B holds 0 results, down from 50 (-100%)', 'the page holds 100 results, down from 150 (-33%)']
    assert S.anomalies({'A': 1}, None) == []            # a cold run has nothing to compare


@pytest.mark.parametrize('body, why', [
    (b'<html><body>no data here</body></html>', 'no <script id="leaderboard-data">'),
    (b'<script type="application/json" id="leaderboard-data">[{"name": </script>', 'does not parse'),
    (b'<script id="leaderboard-data">{"name": "Verified"}</script>', 'not a list'),
    (M.page(M.boards()[:4]), 'holds 4 leaderboards'),
    (M.page([{'name': b['name'], 'rows': b['results']} for b in M.boards()]), 'is not {"name", "results"}'),
    (M.page([dict(b, results=[{k: v for k, v in r.items() if k != 'resolved'} for r in b['results']]) for b in M.boards()]),
     "lacks ['resolved']"),
    (M.page([dict(b, results=b['results'] + b['results'][:1]) for b in M.boards()]), 'repeats a folder'),
], ids=['no-script-tag', 'not-json', 'not-a-list', 'four-boards', 'no-results-key', 'row-lacks-a-key', 'repeated-folder'])
def test_a_page_that_is_not_shaped_as_expected_is_drift_a_hard_fail(tmp_path, body, why):
    with open(tmp_path / 'page.html', 'wb') as f:
        f.write(body)
    with open(tmp_path / 'page.html.headers.json', 'w', encoding='utf-8') as f:
        json.dump(M.headers(), f)
    report = S.run(S.SweBench(FixtureTransport(str(tmp_path)), now=_now), S.new_state(), resolvers())
    assert report['status'] == 'hard-fail' and why in report['errors'][0], report['errors']
    assert report['issue']['labels'] == ['adapter-broken', 'source:swe-bench'] and report['documents'] == []


# ---- the licence veto, and politeness -------------------------------------------------------------------------

def test_every_draft_is_held_by_the_licence_firewall_and_no_raw_body_is_kept():
    report = run(res=everything())
    assert report['held'] == report['drafts']['new'] > 0
    assert report['proposals'] == ['%d claim drafts held by the licence firewall: src-swebench-leaderboard is '
                                   'no-redistribution (04 S9), so nothing is written until P5-S6-T01 settles the '
                                   'terms' % report['held']]
    with pytest.raises(gates.GateError, match='may live only in nowhere'):
        gates.licence_firewall(report['documents'][0], 'data/claims/_ingested/swe-bench/x/claim-000000000000.yaml',
                               S.LICENCE_CLASS)
    with pytest.raises(gates.GateError, match='may keep no raw body'):
        gates.raw_retention(S.SweBench.raw_retainable, S.LICENCE_CLASS, ['page.html'])
    assert S.SweBench.raw_retainable is False


def test_the_adapter_declares_the_licence_class_its_source_record_holds():
    src = read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', 'src-swebench-leaderboard.yaml'))
    assert S.SweBench.source_id == src['id'] == S.SOURCE
    assert S.SweBench.licence_class == src['licence_class'] == 'no-redistribution'
    assert src['licence_spdx'] is None and S.SweBench.licence == 'NOASSERTION'


def test_the_submissions_bucket_is_never_fetched_and_the_page_host_is_paced():
    pol = P.Policy.load()
    assert pol.hosts['www.swebench.com'].rate == 0.2 and pol.hosts['www.swebench.com'].burst == 1
    url, _ = S.artifact(M.PINNED[0])
    with pytest.raises(P.Forbidden):
        P.Gate(pol, robots=lambda u, ua: (404, '')).admit(url)
    with pytest.raises(P.Forbidden):
        P.refuse(url)


def test_the_network_transport_asks_the_gate_and_refuses_http():
    asked = []

    class Refusing:
        def admit(self, url):
            asked.append(url)
            raise P.Forbidden(url, 'refused in this test')

    with pytest.raises(P.Forbidden):
        S.NetworkTransport(gate=Refusing()).get(S.PAGE_URL, {})
    assert asked == [S.PAGE_URL]
    with pytest.raises(ValueError, match='HTTPS only'):
        S.NetworkTransport(gate=Refusing()).get('http://www.swebench.com/', {})
    assert asked == [S.PAGE_URL]


# ---- the command line -----------------------------------------------------------------------------------------

def test_bench_ingest_swe_bench_over_the_fixture(tmp_path):
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'swe-bench', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 0, r.output
    assert 'results       Multilingual=13, Test=24, Verified=180, Lite=84, Multimodal=22 (323)' in r.output
    assert 'unresolved' in r.output
    r = CliRunner().invoke(cli.app, ['ingest', 'swe-bench', '--dry-run', '--no-network'])
    assert r.exit_code == 2
    shutil.copy(os.path.join(FIX, 'page.html.headers.json'), tmp_path / 'page.html.headers.json')
    (tmp_path / 'page.html').write_bytes(b'<html></html>')
    r = CliRunner().invoke(cli.app, ['ingest', 'swe-bench', '--dry-run', '--fixture', str(tmp_path)])
    assert r.exit_code == 1 and 'schema drift' in r.output
