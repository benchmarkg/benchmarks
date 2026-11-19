"""CASP and CAMEO: per-category metrics and the human-expert split (P3-S6-T03; 04 S6, S8, 12 S3.2).

The verify: "bench validate --tier all, plus a test asserting human_assistance is material on the CASP profile and
that all six metrics exist". The done-when: "The separately ranked human-expert category is expressible without a
free-text blob". That is held here as:

  - the six Metric records the task names (GDT_TS, lDDT, TM-score, DockQ, ICS, IPS) exist and load, and casp
    references them, with kendall-tau, which the ligand-affinity ceiling is measured in;
  - human_assistance is material on casp's resolved profile, through the entry's comparability.material_extra
    rather than a change to taxonomy/comparability-profiles.yaml, and a server's claim (`none`) and an expert
    group's (`permitted`) that agree on everything else get different comparability keys; without the field they
    would collide, which is the failure case;
  - the editions are BenchmarkVersions of kind edition, and the deferred `editions` block keeps no edition's
    identity;
  - each category is a Subset, and each Baseline sits on one, sourced from a DOI'd CASP16 assessment paper.
"""
import dataclasses
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

SIX = ('gdt-ts', 'lddt', 'tm-score', 'dockq', 'ics', 'ips')
CASP = os.path.join(ROOT, 'data', 'benchmarks', 'biology-genetics', 'casp.yaml')
CAMEO = os.path.join(ROOT, 'data', 'benchmarks', 'biology-genetics', 'cameo.yaml')


def metric(mid):
    return Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))


def source(sid):
    return Source.model_validate(read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml')))


@pytest.fixture(scope='module')
def casp():
    return load_benchmark(CASP)


# ---- the six metrics -------------------------------------------------------------------------------

@pytest.mark.parametrize('mid', SIX)
def test_each_of_the_six_metrics_exists_and_is_bounded(mid):
    m = metric(mid)
    assert m.id == mid and m.optimum == 'max' and m.higher_is_better is True
    assert m.range is not None and m.range.min == 0 and m.range.max in (1, 100)
    assert m.headroom_null_reason() is None          # bounded, so headroom against a stated anchor is defined
    for sid in m.sources:
        assert source(sid).id == sid


def test_casp_references_the_six_and_cameo_the_two_it_scores(casp):
    assert set(SIX) <= set(casp.metrics) and 'kendall-tau' in casp.metrics
    assert set(load_benchmark(CAMEO).metrics) == {'lddt', 'tm-score'}
    for ref in casp.metrics:
        metric(ref)                                  # a list of Metric refs now, not the descriptive dict


def test_lddt_records_its_two_scales_and_gdt_ts_its_percent():
    assert metric('lddt').range.max == 1 and '0 to 100' in metric('lddt').pitfalls
    assert metric('gdt-ts').range.max == 100 and metric('gdt-ts').units == 'percent'


# ---- the human-expert split ------------------------------------------------------------------------

def test_human_assistance_is_material_on_the_casp_profile(casp):
    r = comp.resolve_profile(casp)
    assert 'human_assistance' in r.material
    assert 'human_assistance' in casp.comparability.material_extra
    # It comes from the entry, not the shared profile: the vocabulary file is untouched.
    profiles = {p.id: p for p in comp.load_profiles().profiles}
    assert r.profiles and all('human_assistance' not in profiles[p].material for p in r.profiles)


def _key(resolution, human_assistance):
    cond = EvalConditions(id='cond-0123456789ab', human_assistance=human_assistance, selection_strategy='single',
                          subset_used='casp#protein-domains', eligibility_track='all groups')
    return comp.compute(resolution, cond, 'casp@casp16', 'gdt-ts', 'casp#protein-domains')


def test_a_server_and_an_expert_group_never_share_a_key(casp):
    r = comp.resolve_profile(casp)
    server, expert = _key(r, 'none'), _key(r, 'permitted')
    assert server.comparability_key != expert.comparability_key
    assert 'human_assistance' not in server.unknown_fields + expert.unknown_fields


def test_without_human_assistance_the_two_would_collide(casp):
    """The failure case: drop the field from the material set and the two claims become one key."""
    r = comp.resolve_profile(casp)
    blind = dataclasses.replace(r, material=tuple(f for f in r.material if f != 'human_assistance'),
                                weights={f: w for f, w in r.weights.items() if f != 'human_assistance'})
    assert _key(blind, 'none').comparability_key == _key(blind, 'permitted').comparability_key


def test_the_entrant_classes_and_the_server_only_targets(casp):
    by = {c.class_: c for c in casp.entrant_classes}
    assert by['server'].ranked_separately is True and by['expert'].ranked_separately is False
    assert 'casp#server-only-targets' in {s.id for s in casp.subsets}


# ---- editions, categories, baselines --------------------------------------------------------------

def test_the_editions_are_benchmark_versions(casp):
    assert [v.version for v in casp.versions] == ['casp16', 'casp17']
    assert all(v.version_kind == 'edition' and v.breaking for v in casp.versions)
    v16, v17 = casp.versions
    assert v16.superseded_by == 'casp17' and v17.supersedes_version == 'casp16'
    assert v16.frozen and not v17.frozen                     # CASP17's assessment is in progress
    deferred = read_yaml(CASP)['editions']
    assert set(deferred) == {'casp16', 'casp17'}             # per-edition facts only, keyed by version tag
    for facts in deferred.values():
        assert not {'id', 'year', 'status', 'categories', 'targets_assessed'} & set(facts)


def test_every_subset_metric_is_a_metric_record_and_every_quote_is_in_its_source(casp):
    for s in casp.subsets:
        if s.metric_override:
            metric(s.metric_override)
        assert s.evidence, s.id
        for ev in s.evidence:
            assert quote_found(ev.quote, source(ev.source).quote_extract), (s.id, ev.source)


def test_baselines_sit_on_categories_and_come_from_assessment_papers(casp):
    subsets = {s.id for s in casp.subsets}
    assert casp.baselines
    primaries = {}
    for b in casp.baselines:
        assert b.benchmark_version == 'casp@casp16' and b.subset in subsets
        metric(b.metric)
        paper = source(b.source)
        assert paper.type == 'paper' and paper.doi and paper.doi.startswith('10.1002/prot.')
        assert b.evidence and all(quote_found(ev.quote, source(ev.source).quote_extract) for ev in b.evidence)
        if b.is_primary:
            primaries.setdefault((b.benchmark_version, b.metric), []).append(b.id)
    assert all(len(ids) == 1 for ids in primaries.values())
    kinds = {b.kind for b in casp.baselines}
    assert kinds <= {'noise-ceiling', 'theoretical-maximum'}  # the papers' anchors; no learned reference as a floor
    affinity = [b for b in casp.baselines if b.metric == 'kendall-tau']
    assert [b.value for b in affinity] == [0.73]
