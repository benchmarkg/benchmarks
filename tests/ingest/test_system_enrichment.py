"""OpenRouter and LiteLLM system-entity enrichment (P5-S6-T07; 06 S3.16, 07 S5.1).

The done_when: "Every unmatched slug becomes a human task rather than a new entity." Verified against
tests/ingest/fixtures/system-enrichment/: synthetic responses with the live endpoints' shape (neither feed licenses its
data, so none is committed); make_fixture.py writes them and this file regenerates them to compare bytes.

  - resolution is an exact dictionary lookup -- a System's external id or an alias record -- so the two near misses
    (`:free`, a case change) that a fuzzy matcher would take stay unmatched;
  - a matched model is a discovery candidate suggesting 06 S3.16's fields; its prices are an observation, never on
    the candidate; an unmatched one is one human task; nothing anywhere is a System record;
  - OpenRouter: conditional on an ETag when there is one, pricing volatile, a >10% shorter list an anomaly, a missing
    key drift; LiteLLM: everything held under the licence veto, sample_spec skipped, a silent ETag change with the same
    body no change, a file of the wrong shape drift.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
from datetime import date

import pytest
from typer.testing import CliRunner

from ingest import gates
from ingest.adapters import litellm as LL
from ingest.adapters import openrouter as OR
from ingest.http import policy as P
from ingest.http.fixture import FixtureTransport
from ingest.resolve import Entry, Index
from schema.entities import AliasFile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'system-enrichment')
_spec = importlib.util.spec_from_file_location('enrichment_fixture', os.path.join(FIX, 'make_fixture.py'))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc)


def resolvers():
    """Model Alpha by its OpenRouter id; Model Beta by two alias rows (OpenRouter's slug and LiteLLM's key)."""
    aliases = AliasFile.model_validate([
        {'alias': alias, 'resolves_to': 'system:model-beta', 'kind': 'provider-endpoint', 'confidence': 'high',
         'decided_by': 'test', 'decided_on': date(2026, 10, 10)}
        for alias in ('example-lab/model-beta-20260815', 'model-beta')]).root
    return {'system': Index('system', [Entry('model-alpha', 'Model Alpha', external_ids=('example-lab/model-alpha',)),
                                       Entry('model-beta', 'Model Beta')], aliases)}


def or_run(fix=os.path.join(FIX, 'openrouter'), state=None, transport=None):
    return OR.run(OR.OpenRouter(transport or FixtureTransport(fix), now=_now),
                  state if state is not None else OR.new_state(), resolvers())


def ll_run(fix=os.path.join(FIX, 'litellm'), state=None, transport=None):
    return LL.run(LL.LiteLLM(transport or FixtureTransport(fix), now=_now),
                  state if state is not None else LL.new_state(), resolvers())


def test_the_committed_fixture_is_what_its_generator_writes():
    def snap():
        return {os.path.join(d, f): open(os.path.join(d, f), 'rb').read()
                for d, _, fs in os.walk(FIX) for f in fs if not f.endswith('.py') and '__pycache__' not in d}
    before = snap()
    M.main()
    assert snap() == before


# ---- the done_when ---------------------------------------------------------------------------------------------

def test_every_unmatched_openrouter_slug_is_a_human_task_and_nothing_is_a_system():
    report = or_run()
    assert report['status'] == 'ok' and report['candidates_seen'] == 6         # seven ids, six models
    unmatched = {'example-lab/model-alpha-20260901:free', 'Example-Lab/Model-Alpha', 'other-lab/model-gamma-20260701',
                 'stealth/union-alpha'}
    assert {u['source_key'] for u in report['unresolved_items']} == unmatched and report['unresolved'] == 4
    for u in report['unresolved_items']:
        assert u['field'] == 'system' and 'never creates a System' in u['human_task']
        assert 'only if a result claim needs this model' in u['human_task']
    assert report['matched'] == 2
    assert all(d['path'].startswith('data/_discovery/openrouter/') for d in report['documents'])
    assert not any(d['path'].startswith('data/systems/') for d in report['documents'])


def test_every_unmatched_litellm_key_is_a_human_task_too():
    entries = json.loads(open(os.path.join(FIX, 'litellm', 'prices.json'), encoding='utf-8').read())
    from ingest.adapters.base import Candidate, Payload
    tasks = {}
    for key, entry in entries.items():
        if key == LL.TEMPLATE:
            continue
        obs, unresolved = LL.normalise(Payload(Candidate(key, 'system', None), b'', 'application/json', 200, _now(),
                                               None, None, 'x', False, doc=entry), resolvers())
        if obs is None:
            (u,) = unresolved
            assert u.reason == 'no-match' and 'never creates a System' in u.human_task
            tasks[key] = u
        else:
            assert unresolved == [] and obs['system'] in ('model-alpha', 'model-beta')
    assert sorted(tasks) == ['openrouter/example-lab/model-alpha', 'other/model-delta']


# ---- exact, never fuzzy -----------------------------------------------------------------------------------------

def test_a_near_miss_is_a_different_model_not_a_spelling():
    idx = resolvers()['system']
    assert idx.exact('example-lab/model-alpha').entity == 'system:model-alpha'            # step 1: external id
    assert idx.exact('example-lab/model-beta-20260815').entity == 'system:model-beta'     # step 2: alias
    for near in ('example-lab/model-alpha:free', 'Example-Lab/Model-Alpha', 'Model Alpha', 'model alpha'):
        assert idx.exact(near) is None
    assert idx.resolve('Model Alpha').entity == 'system:model-alpha'   # what the per-row fuzzy steps would have done


# ---- OpenRouter's candidate --------------------------------------------------------------------------------------

def test_a_matched_model_suggests_06_s3_16s_fields_and_carries_no_price():
    report = or_run()
    docs = {d['identity']['system']: d for d in report['documents']}
    alpha = docs['model-alpha']
    s = {x['field']: x['value'] for x in alpha['_suggested']}
    assert s['external_ids.openrouter'] == 'example-lab/model-alpha'
    assert s['external_ids.huggingface'] == 'example-lab/Model-Alpha'
    assert s['versions[].available_on'] == '2026-09-01' and s['versions[].context_length'] == 131072
    assert s['versions[].supported_parameters'] == ['max_tokens', 'temperature', 'top_p']
    assert alpha['identity']['matched_on'] == 'example-lab/model-alpha'     # not its canonical_slug: the id matched
    assert docs['model-beta']['identity']['matched_on'] == 'example-lab/model-beta-20260815'
    beta = {x['field'] for x in docs['model-beta']['_suggested']}
    assert 'external_ids.huggingface' not in beta                      # null hugging_face_id: nothing to suggest
    assert 'pricing' not in json.dumps(report['documents'])
    assert sorted(o['id'] for o in report['observations']) == sorted(m['id'] for m in M.MODELS)
    assert docs['model-beta']['identity']['routes'] == ['example-lab/model-beta', 'example-lab/model-beta:batch']


def test_openrouter_candidates_pass_the_discovery_gates():
    for d in or_run()['documents']:
        rel, body = d['path'], {k: v for k, v in d.items() if k not in ('path', 'change_class')}
        gates.schema(body, rel)
        gates.metadata_only(body, rel)
        gates.attribution(body, rel, OR.ATTRIBUTION)
        gates.licence_firewall(body, rel, OR.LICENCE_CLASS)
        gates.round_trip(body, rel)


def test_a_price_change_alone_is_no_change_and_an_etag_is_sent_when_there_is_one(tmp_path):
    state = OR.new_state()
    or_run(state=state)
    d = tmp_path / 'or'
    shutil.copytree(os.path.join(FIX, 'openrouter'), d)
    doc = json.loads((d / 'models.json').read_text(encoding='utf-8'))
    for m in doc['data']:
        m['pricing']['prompt'] = '0.000009'
    (d / 'models.json').write_text(json.dumps(doc), encoding='utf-8')
    again = or_run(str(d), state=state)
    assert again['drafts']['no-change'] == 2 and again['documents'] == []
    sent = []

    class Recording(FixtureTransport):
        def get(self, url, headers):
            sent.append(headers)
            return super().get(url, headers)
    state['etag'] = '"abc"'
    or_run(state=state, transport=Recording(os.path.join(FIX, 'openrouter')))
    assert sent == [{'If-None-Match': '"abc"'}]


def test_a_list_more_than_ten_percent_shorter_is_an_anomaly_not_a_deletion(tmp_path):
    state = OR.new_state()
    or_run(state=state)
    d = tmp_path / 'or'
    shutil.copytree(os.path.join(FIX, 'openrouter'), d)
    doc = json.loads((d / 'models.json').read_text(encoding='utf-8'))
    doc['data'] = doc['data'][:5]
    (d / 'models.json').write_text(json.dumps(doc), encoding='utf-8')
    report = or_run(str(d), state=state)
    assert report['labels'] == ['needs-scrutiny'] and report['anomalies'][0].startswith('the list holds 5 models, down from 7')
    assert state['count'] == 7 and report['drafts']['gone'] == 0


@pytest.mark.parametrize('change, says', [
    (lambda doc: doc['data'][1].pop('canonical_slug'), "lacks ['canonical_slug']"),
    (lambda doc: doc.pop('data'), 'no `data` list'),
    (lambda doc: doc['data'].append(dict(doc['data'][0])), 'a model id repeats'),
])
def test_openrouter_drift_is_a_hard_fail(tmp_path, change, says):
    d = tmp_path / 'or'
    shutil.copytree(os.path.join(FIX, 'openrouter'), d)
    doc = json.loads((d / 'models.json').read_text(encoding='utf-8'))
    change(doc)
    (d / 'models.json').write_text(json.dumps(doc), encoding='utf-8')
    report = or_run(str(d))
    assert report['status'] == 'hard-fail' and says in report['errors'][0]
    assert report['issue']['labels'] == ['adapter-broken', 'source:openrouter']


# ---- LiteLLM, under the veto ------------------------------------------------------------------------------------

def test_litellm_output_is_held_whole():
    report = ll_run()
    assert report['status'] == 'ok' and report['candidates_seen'] == 4          # sample_spec is not a model
    assert report['matched'] == 2 and report['unresolved'] == 2
    assert report['held'] == {'observations': 2, 'unresolved': 2, 'reason': LL.VETO}
    assert report['documents'] == [] and report['observations'] == [] and report['unresolved_items'] == []
    assert LL.LiteLLM.raw_retainable is False and LL.LiteLLM.licence_class == 'unlicensed'


def test_litellm_is_conditional_and_a_silent_etag_change_is_no_change(tmp_path):
    state = LL.new_state()
    ll_run(state=state)
    assert state['etag'] == '"fixture-litellm-1"' and state['sha256']
    d = tmp_path / 'll'
    shutil.copytree(os.path.join(FIX, 'litellm'), d)
    h = json.loads((d / 'prices.json.headers.json').read_text(encoding='utf-8'))
    h['headers'] = [['ETag', '"fixture-litellm-2"']]
    (d / 'prices.json.headers.json').write_text(json.dumps(h), encoding='utf-8')
    assert ll_run(str(d), state=state)['status'] == 'no-change'          # a new ETag over the same body
    assert ll_run(state={'etag': '"fixture-litellm-1"', 'sha256': None})['status'] == 'no-change'   # a 304


def test_litellm_of_the_wrong_shape_is_drift(tmp_path):
    d = tmp_path / 'll'
    shutil.copytree(os.path.join(FIX, 'litellm'), d)
    (d / 'prices.json').write_text(json.dumps({'a': {'mode': 'chat'}}), encoding='utf-8')
    report = ll_run(str(d))
    assert report['status'] == 'hard-fail' and 'no entry names a litellm_provider' in report['errors'][0]


# ---- the network -------------------------------------------------------------------------------------------------

def test_both_ask_the_gate_first_and_both_hosts_are_listed():
    asked = []

    class Refusing:
        def admit(self, url):
            asked.append(url)
            raise P.Forbidden(url, 'refused in this test')
    assert OR.run(OR.OpenRouter(OR.NetworkTransport(gate=Refusing()), now=_now), OR.new_state(), resolvers())['status'] == 'hard-fail'
    assert LL.run(LL.LiteLLM(OR.NetworkTransport(gate=Refusing()), now=_now), LL.new_state(), resolvers())['status'] == 'hard-fail'
    assert asked == [OR.URL, LL.URL]
    hosts = P.Policy.load().hosts
    assert 'openrouter.ai' in hosts and 'raw.githubusercontent.com' in hosts


def test_bench_ingest_runs_both_over_the_fixtures():
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'openrouter', '--dry-run', '--fixture', os.path.join(FIX, 'openrouter')])
    assert r.exit_code == 0 and 'ingest openrouter %s: ok' % OR.VERSION in r.output, r.output
    r = CliRunner().invoke(cli.app, ['ingest', 'litellm', '--dry-run', '--fixture', os.path.join(FIX, 'litellm')])
    assert r.exit_code == 0 and 'held' in r.output, r.output
