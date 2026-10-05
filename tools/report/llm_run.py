"""Which claims are LLM-run: the partition 14-roadmap's Phase 3 gate needs (P3-S5-T04).

The Phase 3 exit asks for >=60 claims "from non-LLM domains". A domain cannot answer that: CritPt is physics and
SciCode is natural-science research code, and every one of their claims is a language model's output (14-roadmap
Phase 3: the bridge claims "are still LLM-run and do not count toward the non-LLM target"). So the partition is
by the subject under test -- the claim's System -- and not by the benchmark's domain family:

    LLM-run   the System's system_type is a language-model subject (LLM_SUBJECTS), or it is built_on a System
              that is LLM-run (an agent scaffold around a model)
    not       anything else: a surrogate or specialist model, a classical algorithm, a robot, a human team

scripts/check_phase3_gate.py (P3-S11-T01) should count non-LLM claims with `llm_run() is False`, never by domain.
A System that cannot be read is neither: llm_run() raises, so a claim is never counted on a guess.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# taxonomy/subjects.yaml's terms for a language model under test, alone or wrapped. domain-specialist-model and
# task-specific-supervised-model are not here: a protein model or a trained classifier is not an LLM run.
LLM_SUBJECTS = frozenset({
    'base-model', 'instruction-tuned-model', 'reasoning-model', 'tool-augmented-model', 'retrieval-augmented-system',
    'model-in-benchmark-harness', 'hosted-inference-endpoint',
})
WRAPPERS = frozenset({'agent-scaffold', 'multi-agent-system', 'full-product-pipeline', 'human-ai-team'})


def _system(ref: str, root: str) -> dict:
    from schema.taxonomy import read_yaml
    path = os.path.join(root, 'data', 'systems', ref.split('@')[0] + '.yaml')
    if not os.path.exists(path):
        raise LookupError('%s: no curated System record, so whether its claims are LLM-run is unknown' % ref)
    return read_yaml(path)


def llm_run(system_ref: str, root: str = ROOT, _seen: frozenset = frozenset()) -> bool:
    """True when the subject under test is a language model, or a wrapper built on one."""
    if system_ref in _seen:
        raise ValueError('%s: built_on cycles back to itself' % system_ref)
    s = _system(system_ref, root)
    kind = s['system_type']
    if kind in LLM_SUBJECTS:
        return True
    if kind in WRAPPERS:
        return any(llm_run(b, root, _seen | {system_ref}) for b in s.get('built_on') or [])   # get-default: optional
    return False
