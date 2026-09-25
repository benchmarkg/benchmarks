"""Tests for schema/conditions.py and tools/build/comparability.py (P0-S4-T06; 04 S8, 13 S4.5).

The verify: "the material set resolves per benchmark rather than globally, key_unknown_count and
condition_completeness match hand-computed fixtures, a waiver without a reason is rejected, and a
hosted-API fixture with provider_snapshot null but provider_snapshot_available false scores that
field as answered while an identical fixture with both null does not".

The fixtures under fixtures/comparability/ carry their expected numbers and the expected key tuple,
worked by hand in each file's header; the key is checked by hashing that hand-written tuple here,
not by rebuilding it the way the code does.
"""
import copy
import glob
import hashlib
import importlib.util
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.conditions import COMPANIONS, FIELDS, EvalConditions, parse_reasoning_effort  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('comparability', os.path.join(ROOT, 'tools', 'build', 'comparability.py'))
comp = importlib.util.module_from_spec(spec)
sys.modules['comparability'] = comp            # dataclasses look their module up while decorating
spec.loader.exec_module(comp)

FIXTURES = sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'fixtures', 'comparability', '*.yaml')))
ENTRIES = sorted(glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True))
PROFILES = comp.load_profiles()


def bench(**overrides):
    doc = {
        'id': 'example-bench', 'name': 'Example Bench', 'tagline': 'A benchmark used in tests.',
        'domain': {'primary': 'code/repository-scale-se'},
        'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-example', 'observed_on': '2026-09-25'}],
        'evaluation_target': 'learned-system',
        'data': {'access': 'fully-open'},
        'homepage': 'https://example.org/',
        'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25',
                     'sources': ['src-example']},
    }
    doc.update(copy.deepcopy(overrides))
    return Benchmark.model_validate(doc)


def cond(**fields):
    return EvalConditions.model_validate({'id': 'cond-0123456789ab', **fields})


def run_fixture(path):
    fx = read_yaml(path)
    r = comp.resolve_profile(bench(**fx['benchmark']), PROFILES)
    c = EvalConditions.model_validate(fx['conditions'])
    return fx, r, comp.compute(r, c, **fx['claim'])


# ---- the material set resolves per benchmark -----------------------------------------------------

def test_the_three_entries_resolve_to_different_material_sets():
    got = {os.path.basename(p): comp.resolve_profile(load_benchmark(p), PROFILES) for p in ENTRIES}
    assert {k: (r.profiles, r.fields_material_total) for k, r in got.items()} == {
        'casp.yaml': (('wet-lab',), 3),
        'roboarena.yaml': (('physical-trial',), 4),
        'swe-bench.yaml': (('agentic',), 11),
    }
    assert len({r.material for r in got.values()}) == 3


def test_the_material_set_follows_the_facets_not_a_global_list():
    llm = comp.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model']))
    sim = comp.resolve_profile(bench(evaluation_method=['simulation-rollout'], designed_for_subjects=['rl-policy']))
    assert 'shots' in llm.material and 'shots' not in sim.material
    assert 'simulator_version' in sim.material and 'simulator_version' not in llm.material
    # No resolution uses the universe of material fields.
    universe = {f for p in PROFILES.profiles for f in p.material}
    assert all(set(r.material) < universe for r in (llm, sim))


def test_two_profiles_hit_union_their_fields_and_keep_the_higher_weight():
    r = comp.resolve_profile(bench(evaluation_method=['execution-tests', 'model-graded-judge'],
                                   designed_for_subjects=['agent-scaffold']))
    assert r.basis == 'facets' and r.profiles == ('agentic', 'model-graded')
    assert r.weights['scaffold'] == 2.0 and r.weights['judge_model'] == 2.0 and r.weights['shots'] == 1.0


def test_a_hand_set_profile_pins_that_profile():
    r = comp.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
                                   comparability={'profile': 'hosted-api'}))
    assert (r.basis, r.profiles) == ('explicit', ('hosted-api',))
    assert 'provider_snapshot' in r.material and 'chain_of_thought' not in r.material


def test_an_unlisted_pair_falls_back_and_says_so():
    r = comp.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['physical-robot-system']))
    assert (r.basis, r.profiles, r.material) == ('fallback', (), ('subset_used',))
    r = comp.resolve_profile(bench())                                         # no facets at all
    assert r.basis == 'fallback'


def test_provider_snapshot_is_material_on_hosted_api_only():
    for f in COMPANIONS.items():
        for field in f:
            holders = [p.id for p in PROFILES.profiles if field in p.material]
            assert holders == ['hosted-api'], (field, holders)
            assert field not in PROFILES.fallback.material


# ---- material_extra and material_waived ----------------------------------------------------------

def test_extra_adds_and_waiver_removes_and_both_are_reported():
    r = comp.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
                                   comparability={'material_extra': ['judge_model'],
                                                  'material_waived': [{'field': 'shots', 'reason': 'Zero-shot by design.'}]}))
    assert 'judge_model' in r.material and 'shots' not in r.material and r.fields_material_total == 6
    d = r.as_dict()
    assert d['material_waived'] == {'shots': 'Zero-shot by design.'} and d['material_extra'] == ['judge_model']
    assert d['stray_waivers'] == []


def test_a_waiver_of_a_field_that_was_not_material_is_reported_as_stray():
    r = comp.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
                                   comparability={'material_waived': [{'field': 'sampling', 'reason': 'Not sampled.'}]}))
    assert r.stray_waivers == ('sampling',) and r.fields_material_total == 6


@pytest.mark.parametrize('waiver', [
    {'field': 'shots'},                          # no reason at all
    {'field': 'shots', 'reason': ''},
    {'field': 'shots', 'reason': '   '},         # whitespace is not a reason
    {'field': 'shots', 'reason': None},
    'shots',                                     # a bare field name
])
def test_a_waiver_without_a_reason_is_rejected(waiver):
    with pytest.raises(ValidationError):
        bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
              comparability={'material_waived': [waiver]})


@pytest.mark.parametrize('block', [{'material_extra': ['shot_count']},
                                   {'material_waived': [{'field': 'shot_count', 'reason': 'typo'}]}])
def test_extra_and_waived_must_name_condition_fields(block):
    with pytest.raises(ValueError, match='shot_count'):
        comp.resolve_profile(bench(comparability=block))


def test_a_profile_naming_a_field_conditions_lack_is_rejected(tmp_path):
    doc = read_yaml(comp.PROFILES_PATH)
    doc['profiles'][0]['material'].append('shot_count')
    p = tmp_path / 'profiles.yaml'
    import json
    p.write_text(json.dumps(doc, default=str), encoding='utf-8')          # JSON is YAML
    with pytest.raises(ValueError, match='shot_count'):
        comp.load_profiles(str(p))


def test_everything_waived_leaves_completeness_undefined_not_perfect():
    r = comp.resolve_profile(bench(comparability={'material_waived': [{'field': 'subset_used', 'reason': 'One split.'}]}))
    assert r.material == ()
    assert comp.compute(r, cond(), 'example-bench', 'm', None).condition_completeness is None


# ---- hand-computed fixtures ----------------------------------------------------------------------

def test_there_are_five_fixtures():
    assert [os.path.basename(p) for p in FIXTURES] == [
        'agentic-partial.yaml', 'epoch-llm.yaml', 'hosted-absent.yaml', 'hosted-unknown.yaml', 'union-waiver.yaml']


@pytest.mark.parametrize('path', FIXTURES, ids=[os.path.basename(p) for p in FIXTURES])
def test_fixture_matches_its_hand_computed_values(path):
    fx, r, got = run_fixture(path)
    exp = fx['expected']
    assert list(r.profiles) == exp['profiles']
    assert got.fields_material_total == exp['fields_material_total']
    assert list(got.unknown_fields) == exp['unknown_fields']
    assert got.key_unknown_count == exp['key_unknown_count']
    assert got.condition_completeness == pytest.approx(exp['condition_completeness'], abs=1e-12)
    assert got.comparability_key == hashlib.sha256(exp['key_tuple'].encode('utf-8')).hexdigest()[:16]


def test_hosted_api_companion_false_answers_the_field_and_null_does_not():
    absent = run_fixture(FIXTURES[2])[2]
    unknown = run_fixture(FIXTURES[3])[2]
    assert 'provider_snapshot' not in absent.unknown_fields
    assert 'provider_snapshot' in unknown.unknown_fields
    assert (absent.condition_completeness, absent.key_unknown_count) == (1.0, 0)
    assert unknown.condition_completeness < 1.0 and unknown.key_unknown_count == 2
    assert absent.comparability_key != unknown.comparability_key


def test_companion_true_with_no_snapshot_leaves_the_snapshot_unknown():
    r = comp.resolve_profile(bench(evaluation_method=['exact-match'], designed_for_subjects=['hosted-inference-endpoint']))
    got = comp.compute(r, cond(provider_snapshot_available=True), 'b@1', 'm', None)
    assert 'provider_snapshot' in got.unknown_fields and 'provider_snapshot_available' not in got.unknown_fields
    got = comp.compute(r, cond(provider_snapshot='model-2026-05-01', provider_snapshot_available=True), 'b@1', 'm', None)
    assert 'provider_snapshot' not in got.unknown_fields


# ---- the key -------------------------------------------------------------------------------------

AGENTIC = dict(evaluation_method=['execution-tests'], designed_for_subjects=['agent-scaffold'])


def key(conditions, subset='verified', **b):
    return comp.compute(comp.resolve_profile(bench(**(b or AGENTIC))), conditions, 'swe-bench@verified', 'resolved-rate',
                        subset)


def test_the_key_ignores_spelling_but_not_meaning():
    assert key(cond(tools_allowed=['bash', 'search'])).comparability_key == \
        key(cond(tools_allowed=['search', ' bash', 'bash'])).comparability_key
    assert key(cond(tools_allowed=['bash'])).comparability_key != key(cond(tools_allowed=[])).comparability_key
    assert key(cond(tools_allowed=[])).comparability_key != key(cond()).comparability_key
    assert key(cond(shots=0)).comparability_key != key(cond(shots=5)).comparability_key
    assert key(cond(), subset='full').comparability_key != key(cond()).comparability_key


def test_non_material_fields_do_not_move_the_key():
    assert key(cond(shots=0, cost_usd=12.5, wall_clock_hours=3, sampling={'temperature': 1.0})).comparability_key == \
        key(cond(shots=0)).comparability_key


def test_two_silent_claims_share_a_key_and_both_carry_unknowns():
    a, b = key(cond(shots=0)), key(cond(shots=0, cost_usd=1))
    assert a.comparability_key == b.comparability_key and a.key_unknown_count == b.key_unknown_count == 10


def test_false_and_zero_are_answers():
    got = key(cond(chain_of_thought=False, retries_allowed=0, shots=0))
    for f in ('chain_of_thought', 'retries_allowed', 'shots'):
        assert f not in got.unknown_fields


def test_canonicalise():
    assert comp.canonicalise(1.0) == 1 and comp.canonicalise(0.7) == 0.7 and comp.canonicalise(True) is True
    assert comp.canonicalise({'b': 1.0, 'a': ' x '}) == {'a': 'x', 'b': 1}
    with pytest.raises(ValueError):
        comp.canonicalise('?')


# ---- EvalConditions ------------------------------------------------------------------------------

def test_every_condition_field_defaults_to_null():
    c = cond()
    assert all(getattr(c, f) is None for f in FIELDS)


def test_04_s8_fields_are_all_present():
    for f in ('shots', 'shot_selection', 'chain_of_thought', 'reasoning_effort', 'reasoning_effort_raw',
              'thinking_token_budget', 'prompt_template_hash', 'prompt_template_source', 'tools_allowed', 'scaffold',
              'scaffold_source', 'harness', 'harness_source', 'max_steps', 'message_limit', 'token_limit', 'sandbox',
              'sampling', 'n_samples', 'selection_strategy', 'k', 'retries_allowed', 'max_output_tokens',
              'context_window_used', 'judge_model', 'judge_model_version', 'judge_prompt_hash', 'grading_rubric_ref',
              'human_in_loop', 'human_assistance', 'simulator', 'simulator_version', 'hardware_platform', 'venue',
              'assay_protocol', 'lead_time', 'resolution_window', 'eligibility_track', 'training_data_policy',
              'decontamination_applied', 'subset_used', 'hardware', 'wall_clock_hours', 'cost_usd', 'date_evaluated',
              'provider_snapshot', 'provider_snapshot_available'):
        assert f in FIELDS, f


def test_every_profile_field_is_a_condition_field():
    for p in PROFILES.profiles:
        assert set(p.material) <= set(FIELDS), p.id


def test_reasoning_effort_is_an_enum_and_keeps_its_raw_string():
    assert cond(reasoning_effort='xhigh', reasoning_effort_raw='xhigh').reasoning_effort == 'xhigh'
    with pytest.raises(ValidationError, match='reasoning_effort_raw'):
        cond(reasoning_effort='high')
    with pytest.raises(ValidationError):
        cond(reasoning_effort='extreme', reasoning_effort_raw='extreme')
    assert cond(reasoning_effort_raw='thinking-32k').reasoning_effort is None      # raw with no enum: kept


@pytest.mark.parametrize('raw, enum', [('high', 'high'), (' XHigh ', 'xhigh'), ('unknown', None), ('max', 'max'),
                                       ('none', 'none'), ('thinking-32k', None), (None, None)])
def test_parse_reasoning_effort(raw, enum):
    assert parse_reasoning_effort(raw) == enum


def test_a_snapshot_beside_available_false_is_a_contradiction():
    with pytest.raises(ValidationError, match='provider_snapshot_available is false'):
        cond(provider_snapshot='model-2026-05-01', provider_snapshot_available=False)


@pytest.mark.parametrize('fields', [
    {'judge_model_version': '1'}, {'judge_prompt_hash': 'sha256:' + '0' * 64}, {'simulator_version': '4.1'},
    {'scaffold_source': 'src-x'}, {'harness_source': 'src-x'}, {'selection_strategy': 'single', 'k': 4},
    {'unknown_field': 1}, {'id': 'cond-cache-r1'}, {'human_assistance': 'some'}, {'shots': -1},
])
def test_condition_rules(fields):
    with pytest.raises(ValidationError):
        EvalConditions.model_validate({'id': 'cond-0123456789ab', **fields})


# ---- the build step ------------------------------------------------------------------------------

def test_build_over_the_repository():
    out = comp.build()
    assert set(out['profiles']) == {'casp', 'roboarena', 'swe-bench'}
    assert out['profiles']['swe-bench']['fields_material_total'] == 11


def test_build_computes_claims_from_their_condition_records(tmp_path):
    import shutil
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    shutil.copytree(os.path.join(ROOT, 'data', 'benchmarks'), tmp_path / 'data' / 'benchmarks')
    fx = read_yaml(FIXTURES[0])
    (tmp_path / 'data' / 'conditions').mkdir()
    (tmp_path / 'data' / 'claims').mkdir()
    import json
    (tmp_path / 'data' / 'conditions' / 'c.yaml').write_text(json.dumps(fx['conditions']), encoding='utf-8')
    claim = {'id': 'claim-0123456789ab', 'system': 'sys-x', 'benchmark': 'swe-bench@verified', 'subset': 'verified',
             'metric': 'resolved-rate', 'value': 0.5, 'date_reported': '2026-09-25', 'reported_by': 'org-x',
             'verification': 'self-reported', 'source': 'src-x', 'eval_conditions': fx['conditions']['id']}
    (tmp_path / 'data' / 'claims' / 'a.yaml').write_text(json.dumps(claim), encoding='utf-8')
    got = comp.build(str(tmp_path))['claims']['claim-0123456789ab']
    assert got['key_unknown_count'] == 3 and got['condition_completeness'] == 0.75
    assert got['comparability_key'] == hashlib.sha256(fx['expected']['key_tuple'].encode()).hexdigest()[:16]

    claim['eval_conditions'] = 'cond-ffffffffffff'
    (tmp_path / 'data' / 'claims' / 'a.yaml').write_text(json.dumps(claim), encoding='utf-8')
    with pytest.raises(ValueError, match='no record'):
        comp.build(str(tmp_path))
