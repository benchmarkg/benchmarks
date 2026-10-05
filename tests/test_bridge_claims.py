"""The science-adjacent bridge claims (P3-S5-T04; 14-roadmap Phase 3, 04 S8).

The verify: bench report completeness shows >= 12 claims at >= 0.6 across the five bridge benchmarks, and none
of them counts as non-LLM. The done-when adds that tools_allowed is populated on every one. The Phase 3 gate
script (P3-S11-T01) is not built yet; tools/report/llm_run.py is the partition it is to use, and is held here.
"""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.report import completeness, llm_run  # noqa: E402

BRIDGE = ('critpt', 'surface-evolver-bench', 'cadeval', 'scicode', 'geobench-geoguessr')


def claims():
    return [ResultClaim.model_validate(read_yaml(p)) for b in BRIDGE
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', b, '*.yaml')))]


CLAIMS = claims()


def test_twelve_to_fifteen_bridge_claims_at_completeness_0_6():
    rows = [r for r in completeness.build(ROOT)['rows'] if r['benchmark'] in BRIDGE]
    assert 12 <= len(rows) <= 15
    assert all(r['condition_completeness'] >= 0.6 for r in rows), [(r['claim'], r['condition_completeness']) for r in rows]


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.benchmark, c.system))
def test_every_bridge_claim_states_its_tools(claim):
    cond = EvalConditions.model_validate(read_yaml(os.path.join(ROOT, 'data', 'conditions', claim.eval_conditions + '.yaml')))
    assert cond.tools_allowed is not None                   # an empty list is "no tools", stated; None is unknown


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.benchmark, c.system))
def test_every_bridge_claim_is_llm_run_whatever_its_domain(claim):
    assert llm_run.llm_run(claim.system) is True


def test_the_tools_case_is_one_model_at_one_effort():
    gpt5 = sorted((c.value, tuple(EvalConditions.model_validate(read_yaml(os.path.join(
        ROOT, 'data', 'conditions', c.eval_conditions + '.yaml'))).tools_allowed))
        for c in CLAIMS if c.benchmark == 'critpt' and c.system == 'gpt-5' and c.value > 0)
    assert gpt5 == [(0.057, ()), (0.106, ('code-interpreter',)), (0.126, ('code-interpreter', 'web-search'))]


# ---- the partition itself ---------------------------------------------------------------------------------

def write(root, sid, body):
    p = root / 'data' / 'systems' / (sid + '.yaml')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('id: %s\n%s' % (sid, body), encoding='utf-8')


def test_the_partition_is_by_subject_not_domain(tmp_path):
    write(tmp_path, 'm', 'system_type: reasoning-model\n')
    write(tmp_path, 'scaffold', 'system_type: agent-scaffold\nbuilt_on: [m@v1]\n')
    write(tmp_path, 'surrogate', 'system_type: scientific-surrogate-model\n')
    write(tmp_path, 'pipeline', 'system_type: full-product-pipeline\nbuilt_on: [surrogate]\n')
    write(tmp_path, 'team', 'system_type: human-expert\n')
    root = str(tmp_path)
    assert llm_run.llm_run('m', root) and llm_run.llm_run('scaffold', root)          # a wrapper around a model
    assert not any(llm_run.llm_run(s, root) for s in ('surrogate', 'pipeline', 'team'))


def test_an_unreadable_or_cyclic_system_is_never_counted(tmp_path):
    write(tmp_path, 'a', 'system_type: agent-scaffold\nbuilt_on: [b]\n')
    write(tmp_path, 'b', 'system_type: agent-scaffold\nbuilt_on: [a]\n')
    with pytest.raises(LookupError):
        llm_run.llm_run('nowhere', str(tmp_path))
    with pytest.raises(ValueError, match='cycles'):
        llm_run.llm_run('a', str(tmp_path))
