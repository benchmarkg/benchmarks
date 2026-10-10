"""The HELM adapter, behind the licence veto (P5-S6-T05; 06 S3.5, S1.2, 07 S4.4).

Verified against tests/ingest/fixtures/helm/: a synthetic bucket with the real API's shape and none of HELM's
content, since the bucket's data states no licence and may not be committed. make_fixture.py builds it and this
file regenerates it to compare bytes.

The done_when, three parts:
  - conditions parse: shots, chain of thought ("" is a known off; a missing key is unknown), temperature,
    n_samples, the evaluation subset, method and the serving provider, each condition set a valid EvalConditions;
  - a renamed adapter_spec key hard-fails, before any draft, with adapter-broken -- and so does a top-level rename;
  - no HELM score reaches the citable core while the licence is open: runs.json is never requested, every draft is
    under data/_discovery/helm/, nothing is retained raw, and no prompt text is copied.
Also step 1: the listing is diffed on generation and size before any download.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import shutil

import pytest
from typer.testing import CliRunner

from ingest import gates
from ingest.adapters import helm as H
from ingest.http import policy as P
from ingest.http.fixture import FixtureTransport
from schema.conditions import EvalConditions

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'helm')
_spec = importlib.util.spec_from_file_location('helm_fixture', os.path.join(FIX, 'make_fixture.py'))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 10, 5, 0, tzinfo=timezone.utc)


class Recording(FixtureTransport):
    def __init__(self, path):
        super().__init__(path)
        self.asked = []

    def get(self, url, headers):
        self.asked.append(url)
        return super().get(url, headers)


def run(fix=FIX, state=None):
    t = Recording(fix)
    return H.run(H.Helm(t, now=_now), state if state is not None else H.new_state()), t


@pytest.fixture(scope='module')
def result():
    return run()


def doc(report, suite, cls):
    (d,) = [d for d in report['documents'] if d['identity']['suite'] == suite and d['identity']['scenario_class'] == cls]
    return d


def test_the_committed_fixture_is_what_its_generator_writes(tmp_path):
    before = {f: open(os.path.join(FIX, f), 'rb').read() for f in os.listdir(FIX) if f != 'make_fixture.py'
              and not f.startswith('__')}
    M.main()
    after = {f: open(os.path.join(FIX, f), 'rb').read() for f in os.listdir(FIX) if f != 'make_fixture.py'
             and not f.startswith('__')}
    assert after == before


# ---- conditions parse --------------------------------------------------------------------------------------------

def test_the_newest_release_of_every_suite_is_read(result):
    report, _ = result
    assert report['status'] == 'ok', report['errors']
    assert {s: v['release'] for s, v in report['suites'].items()} == {'classic': 'v0.4.0', 'lite': 'v1.13.0',
                                                                       'mmlu': 'v1.13.0'}
    assert report['no_releases'] == ['audio']                # data, not an error
    assert report['candidates_seen'] == report['drafts']['new'] == 4


def test_06_s3_5s_mapping_into_eval_conditions(result):
    report, _ = result
    qa = doc(report, 'lite', M.QA)['identity']
    (c,) = qa['conditions']
    assert {k: v for k, v in c.items() if k not in ('id', 'runs')} == {
        'shots': 5, 'chain_of_thought': False, 'sampling': {'temperature': 0.0}, 'n_samples': 1,
        'subset_used': 'first 1000 evaluation instances (HELM max_eval_instances)'}
    assert c['runs'] == 3 and qa['runs'] == 3 and qa['models'] == 3
    assert qa['methods'] == {'generation': 3} and qa['metrics'] == ['exact_match']
    # together and huggingface served someone else's model; example-org served its own, which is no serving provider
    assert qa['serving_providers'] == {'huggingface': 1, 'together': 1}
    math = doc(report, 'lite', M.MATH)['identity']
    (m,) = math['conditions']
    assert m['shots'] == 8 and m['chain_of_thought'] is True and m['sampling'] == {'temperature': 0.7}
    assert m['n_samples'] == 4 and m['subset_used'].startswith('first 500 ')
    assert math['metrics'] == ['exact_match', 'math_equiv'] and math['scenario_args'] == ['subject=algebra', 'subject=geometry']


def test_a_key_the_older_shape_lacks_is_unknown_never_defaulted(result):
    report, _ = result
    old = doc(report, 'classic', M.QA)['identity']
    (c,) = old['conditions']
    assert 'chain_of_thought' not in c                       # classic has no chain_of_thought_prefix: unknown, not false
    assert c['shots'] == 0 and old['serving_providers'] == {}    # and no model_deployment to read a provider from
    assert old['train_trials_and_trials'] == {'1/None': 1}


def test_every_condition_set_is_a_valid_eval_conditions_with_a_content_id(result):
    report, _ = result
    for d in report['documents']:
        for c in d['identity']['conditions']:
            fields = {k: v for k, v in c.items() if k not in ('id', 'runs')}
            assert c['id'] == H.conditions_id(fields)
            EvalConditions.model_validate({'id': c['id'], **fields})


def test_every_draft_is_a_discovery_candidate_that_passes_the_gates(result):
    report, _ = result
    for d in report['documents']:
        rel = d['path']
        body = {k: v for k, v in d.items() if k != 'path'}
        assert rel.startswith('data/_discovery/helm/cand-helm-')
        gates.schema(body, rel)
        gates.metadata_only(body, rel)
        gates.attribution(body, rel, H.ATTRIBUTION)
        gates.licence_firewall(body, rel, H.LICENCE_CLASS)
        gates.round_trip(body, rel)
    assert doc(report, 'lite', M.QA)['candidate_id'] == 'cand-helm-lite-example-exampleqa'


# ---- a renamed key hard-fails ----------------------------------------------------------------------------------

def rewritten(tmp_path, change):
    """A copy of the bucket whose lite run_specs.json is `change`d, re-listed with a matching size, MD5 and gzip."""
    import base64
    import hashlib
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    specs = json.loads(gzip.decompress((d / 'lite-run_specs.bin').read_bytes()))
    change(specs)
    stored = gzip.compress(json.dumps(specs).encode('utf-8'), mtime=0)
    (d / 'lite-run_specs.bin').write_bytes(stored)
    listing = json.loads((d / 'lite-objects.json').read_text(encoding='utf-8'))
    for item in listing['items']:
        if item['name'].endswith('/run_specs.json'):
            item['size'] = str(len(stored))
            item['md5Hash'] = base64.b64encode(hashlib.md5(stored).digest()).decode()
    (d / 'lite-objects.json').write_text(json.dumps(listing), encoding='utf-8')
    return str(d)


def _rename(old, new):
    def change(specs):
        a = specs[1]['adapter_spec']
        a[new] = a.pop(old)
    return change


@pytest.mark.parametrize('change, says', [
    (_rename('temperature', 'sampling_temperature'), "missing ['temperature'], new ['sampling_temperature']"),
    (_rename('max_train_instances', 'num_in_context_examples'), "missing ['max_train_instances']"),
    (_rename('model_deployment', 'deployment'), "missing ['model_deployment'], new ['deployment']"),
    (_rename('chain_of_thought_prefix', 'cot_prefix'), "new ['cot_prefix']"),
    (lambda specs: specs[0]['adapter_spec'].pop('method'), "missing ['method']"),
    (lambda specs: specs[0].update(run_group=specs[0].pop('groups')), "a run spec's keys are"),
    (lambda specs: specs.clear(), 'not a non-empty list of run specs'),
])
def test_a_renamed_adapter_spec_key_hard_fails_before_any_draft(tmp_path, change, says):
    report, _ = run(rewritten(tmp_path, change))
    assert report['status'] == 'hard-fail' and report['documents'] == [] and report['candidates_seen'] == 0
    assert report['errors'][0].startswith('schema drift: ') and says in report['errors'][0], report['errors']
    assert report['issue']['labels'] == ['adapter-broken', 'source:helm']


def test_a_bucket_that_answers_403_is_a_hard_fail(tmp_path):
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    h = json.loads((d / 'lite-releases.json.headers.json').read_text(encoding='utf-8'))
    h['status'] = 403
    (d / 'lite-releases.json.headers.json').write_text(json.dumps(h), encoding='utf-8')
    report, _ = run(str(d))
    assert report['status'] == 'hard-fail' and report['errors'][0].startswith('Forbidden')


def test_bytes_that_do_not_match_their_listing_are_refused(tmp_path):
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    (d / 'classic-run_specs.bin').write_bytes((d / 'classic-run_specs.bin').read_bytes()[:-1] + b' ')
    report, _ = run(str(d))
    assert report['status'] == 'hard-fail' and 'does not match its listing' in report['errors'][0]


# ---- no score reaches the citable core ------------------------------------------------------------------------

def test_runs_json_the_scores_is_never_requested(result):
    report, transport = result
    assert transport.asked and not any('runs.json' in u for u in transport.asked)
    from urllib.parse import unquote
    assert all(unquote(u).split('?')[0].endswith('/run_specs.json') or 'delimiter' in u for u in transport.asked)


def test_no_prompt_text_and_no_score_is_copied(result):
    report, _ = result
    text = json.dumps(report['documents'])
    assert M.PROMPT.strip() not in text and 'Think step by step' not in text and 'Q: ' not in text
    for d in report['documents']:
        assert d['identity']['licence'].startswith('open: no HELM score is read')
        assert not any(k in json.dumps(d['identity']) for k in ('"value"', '"score"', '"mean"'))


def test_the_adapter_keeps_no_raw_body_and_declares_its_licence_open():
    assert H.Helm.raw_retainable is False and H.Helm.licence_class == 'unlicensed'
    with pytest.raises(gates.GateError, match='may keep no raw body'):
        gates.raw_retention(H.Helm.raw_retainable, H.LICENCE_CLASS, ['run_specs.json'])
    with pytest.raises(gates.GateError, match='may live only in nowhere'):
        gates.licence_firewall({'ingestion': {'licence_class': 'unlicensed'}}, 'data/claims/_ingested/helm/x.yaml',
                               H.LICENCE_CLASS)


# ---- step 1: the listing first ---------------------------------------------------------------------------------

def test_an_object_whose_generation_and_size_did_not_move_is_not_downloaded():
    state = H.new_state()
    first, t1 = run(state=state)
    assert sum('alt=media' in u for u in t1.asked) == 3
    again, t2 = run(state=state)
    assert again['status'] == 'no-change' and not any('alt=media' in u for u in t2.asked)
    name = next(k for k in state['objects'] if k.startswith('lite/'))
    state['objects'][name][0] = '1'                          # a new generation of lite's run_specs.json
    third, t3 = run(state=state)
    with open(os.path.join(FIX, 'lite-objects.json'), encoding='utf-8') as f:
        generation = next(i for i in json.load(f)['items'] if i['name'] == name)['generation']
    assert [u for u in t3.asked if 'alt=media' in u] == [H.media_url(name, generation)]
    assert sorted(third['suites']) == ['lite'] and sorted(third['unchanged']) == ['classic', 'mmlu']


def test_a_suite_quiet_for_two_quarters_is_surfaced_as_a_liveness_fact(result):
    report, _ = result
    assert report['proposals'] == ['mmlu: newest release v1.13.0, last written 2025-12-01, over two quarters ago -- a '
                                   'liveness fact (06 S3.5), not a scraper bug']


def test_newest_is_by_version_not_by_string():
    assert H.newest(['x/v1.2.0/', 'x/v1.13.0/', 'x/v1.12.0/', 'x/latest/']) == 'x/v1.13.0/'
    assert H.newest(['x/latest/']) is None


# ---- the network -------------------------------------------------------------------------------------------------

def test_the_network_transport_asks_the_gate_and_the_bucket_host_is_listed():
    asked = []

    class Refusing:
        def admit(self, url):
            asked.append(url)
            raise P.Forbidden(url, 'refused in this test')
    report = H.run(H.Helm(H.NetworkTransport(gate=Refusing()), now=_now), H.new_state())
    assert report['status'] == 'hard-fail' and asked == [H.list_url('')]
    assert 'storage.googleapis.com' in P.Policy.load().hosts


def test_bench_ingest_helm_over_the_fixture():
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'helm', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 0, r.output
    assert 'ingest helm %s: ok' % H.VERSION in r.output and 'no releases  audio' in r.output
