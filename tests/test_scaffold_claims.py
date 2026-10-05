"""The SWE-bench Verified scaffold claims (P3-S5-T03; 04 S7-S8).

The verify: every scaffold claim has a non-empty built_on and a comparability_key distinct from every other
scaffold claim on the same benchmark version. The done-when adds that the scaffold is part of the number
rather than context, which is held here as: the scaffold is a material field of the benchmark, each claim's
conditions name its own scaffold, and changing only that field changes the key.
"""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

BENCH = 'swe-bench-verified'


def claims():
    return [ResultClaim.model_validate(read_yaml(p))
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', BENCH, '*.yaml')))]


def system(ref):
    return System.model_validate(read_yaml(os.path.join(ROOT, 'data', 'systems', ref.split('@')[0] + '.yaml')))


def conditions(cid):
    return EvalConditions.model_validate(read_yaml(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml')))


SCAFFOLD_CLAIMS = [c for c in claims() if system(c.system).system_type == 'agent-scaffold']


def test_three_or_four_scaffold_claims_on_one_benchmark_version():
    assert 3 <= len(SCAFFOLD_CLAIMS) <= 4
    assert len({c.benchmark for c in SCAFFOLD_CLAIMS}) == 1


@pytest.mark.parametrize('claim', SCAFFOLD_CLAIMS, ids=lambda c: c.system)
def test_every_scaffold_names_a_published_base_model_and_version(claim):
    s = system(claim.system)
    assert s.built_on, '%s: an agent-scaffold with no built_on' % s.id
    for ref in s.built_on:
        base = system(ref)                                  # a curated System file, not a stub
        assert base.system_type != 'agent-scaffold'
        if '@' in ref:
            assert ref.split('@')[1] in {v.version for v in base.versions}


def test_no_two_scaffold_claims_share_a_comparability_key():
    built = comp.build(ROOT)['claims']
    keys = [built[c.id]['comparability_key'] for c in SCAFFOLD_CLAIMS]
    assert len(set(keys)) == len(keys)


def test_the_scaffold_is_material_and_each_claim_names_its_own():
    resolution = comp.resolve_profile(comp.load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'code', BENCH + '.yaml')),
                                      comp.load_profiles())
    assert 'scaffold' in resolution.material
    for c in SCAFFOLD_CLAIMS:
        assert conditions(c.eval_conditions).scaffold == c.system


def test_changing_only_the_scaffold_changes_the_key():
    resolution = comp.resolve_profile(comp.load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'code', BENCH + '.yaml')),
                                      comp.load_profiles())
    c = SCAFFOLD_CLAIMS[0]
    cond = conditions(c.eval_conditions)
    other = cond.model_copy(update={'scaffold': next(x.system for x in SCAFFOLD_CLAIMS if x.system != c.system)})
    assert (comp.compute_for_claim(c, resolution, cond).comparability_key
            != comp.compute_for_claim(c, resolution, other).comparability_key)


def test_one_base_model_so_the_spread_is_the_scaffolds():
    bases = {system(c.system).built_on[0].split('@')[0] for c in SCAFFOLD_CLAIMS}
    values = sorted(c.value for c in SCAFFOLD_CLAIMS)
    assert bases == {'gpt-4o'} and values == [0.232, 0.262, 0.384, 0.388]
