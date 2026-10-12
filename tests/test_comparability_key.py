"""The comparability_key fixture tests (P0-S9-T03; 14-roadmap Phase 0 exit criterion 3, 04 S8).

The verify: "`pytest tests/test_comparability_key.py` passes all four assertions". Done when: "Exit criterion 3
is verified by a test that would fail if the key ignored a material field."

  1. two SWE-bench condition records differing only in scaffold (data/conditions/, A and B below);
  2. a key is computed for all ten stress entries;
  3. A and B give different keys, and two identical condition sets give the same key;
  4. key_unknown_count is non-zero where a material field is null.

The two records are named by their content-derived ids (07 S1.4: `cond-` and twelve hex digits), not the
`cond-swebench-scaffold-a` the plan's task sketch used, which the EvalConditions id pattern refuses.
"""
import copy
import importlib.util
import json
import hashlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('comparability_key_test', os.path.join(ROOT, 'tools', 'build', 'comparability.py'))
C = importlib.util.module_from_spec(spec)
sys.modules['comparability_key_test'] = C
spec.loader.exec_module(C)

A, B = 'cond-e29963a458c4', 'cond-cbbb506b483b'
STRESS = os.path.join(ROOT, 'tests', 'fixtures', 'stress-entries.yaml')


def conditions(cid):
    return EvalConditions.model_validate(read_yaml(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml')))


@pytest.fixture(scope='module')
def profiles():
    return C.load_profiles()


@pytest.fixture(scope='module')
def swe(profiles):
    return C.resolve_profile(load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'code', 'swe-bench.yaml')), profiles)


def key(resolution, cond):
    return C.compute(resolution, cond, 'swe-bench@verified', 'resolved-rate', None)


# ---- 1. the two records ------------------------------------------------------------------------------

def test_verify_the_two_swe_bench_records_differ_only_in_scaffold():
    a, b = conditions(A), conditions(B)
    da, db = a.model_dump(exclude={'id'}), b.model_dump(exclude={'id'})
    assert {f for f in da if da[f] != db[f]} == {'scaffold'}
    assert (a.scaffold, b.scaffold) == ('swe-agent-gpt-4o', 'agentless-gpt-4o')


@pytest.mark.parametrize('cid', [A, B])
def test_each_id_is_content_derived(cid):
    raw = {k: v for k, v in read_yaml(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml')).items() if k != 'id'}
    assert cid == 'cond-%s' % hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:12]


# ---- 2. a key for every stress entry -------------------------------------------------------------------

def test_verify_a_key_is_computed_for_all_ten_stress_entries(profiles):
    entries = read_yaml(STRESS)['entries']
    assert len(entries) == 10
    for e in entries:
        r = C.resolve_profile(load_benchmark(os.path.join(ROOT, *e['path'].split('/'))), profiles)
        got = C.compute(r, None, e['id'], 'any-metric', None)
        assert len(got.comparability_key) == 16 and int(got.comparability_key, 16) >= 0, e['id']
        assert got.key_unknown_count == len(r.material), e['id']          # no conditions: every material field unknown


# ---- 3. the key moves with a material field, and only with one -------------------------------------------

def test_verify_the_two_scaffolds_give_different_keys(swe):
    assert 'scaffold' in swe.material
    assert key(swe, conditions(A)).comparability_key != key(swe, conditions(B)).comparability_key


def test_verify_identical_conditions_give_the_same_key(swe):
    a = conditions(A)
    twin = EvalConditions.model_validate(dict(a.model_dump(exclude_none=True), id='cond-000000000000'))
    assert key(swe, a).comparability_key == key(swe, twin).comparability_key       # the id is not a condition


def test_a_field_the_profile_does_not_make_material_leaves_the_key_alone(swe):
    assert 'judge_model' not in swe.material
    a = conditions(A)
    judged = EvalConditions.model_validate(dict(a.model_dump(exclude_none=True), judge_model='gpt-4o'))
    assert key(swe, a).comparability_key == key(swe, judged).comparability_key


# ---- 4. unknowns are counted -------------------------------------------------------------------------------

def test_verify_key_unknown_count_is_non_zero_where_a_material_field_is_null(swe):
    got = key(swe, conditions(A))
    assert got.key_unknown_count == len(swe.material) - 1 > 0                # only scaffold is answered
    assert 'scaffold' not in got.unknown_fields and 'shots' in got.unknown_fields
    filled = EvalConditions.model_validate(dict(conditions(A).model_dump(exclude_none=True), shots=0))
    assert key(swe, filled).key_unknown_count == got.key_unknown_count - 1
