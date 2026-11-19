"""Matbench Discovery's six metrics, compliance tiers and anchors (P3-S6-T01; 04 S6, S7, S8; 12 S3.2).

The verify: "bench validate --tier all, plus `uv run pytest tests/test_matbench_discovery.py -q` asserting all six
Metric records carry a range and an optimum, that training_data_eligibility_tiers[] is populated from the
compliance tiers, that eligibility_track is present in comparability.material_extra, and that every Baseline
carries either a source or a value_absent_reason." Each of the four is a function below that returns what is
wrong. It runs on the committed records, which must pass, and on a copy broken the way the verification names,
which must fail, so the test also fails if a check stops catching its case.

The six are 02 S12.6's "stability F1 + energy MAE + phonons + κ_SRME thermal conductivity + MD stability +
diatomic PES" as the sources name them (the entry's header comment and review_checks say how each was mapped).
Headroom itself is P3-S9-T04's to assert; here only that the headroom code can reason about each metric: it is
computable against its anchors, or it names one of 12 S3.4's six null reasons.
"""
import copy
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import CEILING_ANCHOR, FLOOR_KINDS, Baseline, BaselineFile  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.metric import HeadroomNotComputable, Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability  # noqa: E402

BID = 'matbench-discovery'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BID + '.yaml')
BASELINES = os.path.join(ROOT, 'data', 'baselines', BID + '.yaml')
SIX = ('f1-score', 'e-above-hull-mae', 'phonon-spectrum-w1', 'kappa-srme', 'matbench-cmds', 'matbench-cds')
# 12 S3.4's table: the only reasons a headroom null may give.
NULL_REASONS = {'no-baseline-established', 'unbounded-metric', 'lower-is-better-optimum-zero',
                'vector-valued-by-design', 'relative-rating-only', 'resolution-pending'}
PAPER_TIERS = {'compliant', 'non-compliant'}


def metric_doc(mid: str) -> dict:
    return read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml'))


def source_doc(sid: str) -> dict | None:
    for d, _, files in os.walk(os.path.join(ROOT, 'data', 'sources')):
        if sid + '.yaml' in files:
            return read_yaml(os.path.join(d, sid + '.yaml'))
    return None


@pytest.fixture(scope='module')
def entry() -> Benchmark:
    return load_benchmark(ENTRY)


@pytest.fixture(scope='module')
def baselines() -> list[dict]:
    return read_yaml(BASELINES)


# ---- the four checks ----------------------------------------------------------------------------------------

def metric_problems(doc: dict) -> list[str]:
    """A range and an optimum, and a range the headroom code can use: a lower bound always, and an upper bound
    where higher is better (the bound headroom reads as the ceiling)."""
    m = Metric.model_validate(doc)                 # `optimum` is required, so a record without it raises here
    if m.range is None:
        return ['%s has no range' % m.id]
    out = []
    if m.range.min is None:
        out.append('%s: range has no min' % m.id)
    if m.optimum == 'max' and m.range.max is None:
        out.append('%s: a higher-is-better metric with no range.max' % m.id)
    reason = m.headroom_null_reason()
    if reason is not None and reason not in NULL_REASONS:
        out.append('%s: headroom null reason %s is not one of 12 S3.4\'s six' % (m.id, reason))
    return out


def tier_problems(b: Benchmark) -> list[str]:
    """training_data_eligibility_tiers[] holds the benchmark's compliance tiers, each sourced from the entry."""
    tiers = b.training_data_eligibility_tiers
    if not tiers:
        return ['training_data_eligibility_tiers is empty']
    out = []
    missing = PAPER_TIERS - {t.id for t in tiers}
    if missing:
        out.append('the compliance tiers lack %s' % ', '.join(sorted(missing)))
    cited = set(b.curation.source_ids())
    out += ['tier %s cites %s, which curation.sources does not list' % (t.id, t.source)
            for t in tiers if t.source not in cited]
    return out


def material_problems(b: Benchmark) -> list[str]:
    out = []
    if 'eligibility_track' not in b.comparability.material_extra:
        out.append('eligibility_track is not in comparability.material_extra')
    if 'eligibility_track' not in comparability.resolve_profile(b).material:
        out.append('eligibility_track is not material in the resolved profile')
    return out


def baseline_problems(raw: list[dict]) -> list[str]:
    """Every Baseline carries a value with its source, or a value_absent_reason; every quote is in its Source's
    extract; and each of the six metrics has one primary, which is a ceiling, and a floor record."""
    out = []
    records = []
    for d in raw:
        try:
            records.append(Baseline.model_validate(d))
        except ValidationError as e:
            out.append('%s: %s' % (d.get('id'), e.errors()[0]['msg']))
    for x in records:
        if x.value is None and x.value_absent_reason is None:
            out.append('%s has neither a value nor a value_absent_reason' % x.id)
        if x.value is not None and x.source is None:
            out.append('%s has a value and no source' % x.id)
        for sid in [x.source] if x.source else []:
            if source_doc(sid) is None:
                out.append('%s cites %s, which is not under data/sources/' % (x.id, sid))
        for ev in x.evidence:
            s = source_doc(ev.source)
            if s is None or not ev.quote or not quote_found(ev.quote, s.get('quote_extract') or ''):
                out.append('%s: quote not in %s: %r' % (x.id, ev.source, ev.quote))
    for mid in SIX:
        mine = [x for x in records if x.metric == mid]
        primary = [x for x in mine if x.is_primary]
        if len(primary) != 1:
            out.append('%s: %d primary baselines' % (mid, len(primary)))
        elif primary[0].kind not in CEILING_ANCHOR or primary[0].value is None:
            out.append('%s: the primary is not a ceiling with a value' % mid)
        if not any(x.kind in FLOOR_KINDS for x in mine):
            out.append('%s: no floor record, not even an absent one' % mid)
    return out


# ---- the committed records pass -----------------------------------------------------------------------------

@pytest.mark.parametrize('mid', SIX)
def test_verify_each_of_the_six_metrics_carries_a_range_and_an_optimum(entry, mid):
    assert metric_problems(metric_doc(mid)) == []
    assert mid in entry.metrics


def test_verify_the_tiers_are_populated_from_the_compliance_tiers(entry):
    assert tier_problems(entry) == []
    assert read_yaml(ENTRY)['training_data_eligibility_tiers_basis']['quote']     # the paper's rule, quoted


def test_verify_eligibility_track_is_in_material_extra(entry):
    assert material_problems(entry) == []


def test_verify_every_baseline_has_a_source_or_a_value_absent_reason(baselines):
    BaselineFile.model_validate(baselines)                                         # one primary per metric
    assert baseline_problems(baselines) == []
    assert {b['metric'] for b in baselines} == set(SIX)


@pytest.mark.parametrize('mid', SIX)
def test_the_headroom_code_can_reason_about_each_metric(baselines, mid):
    """Computable against its anchors where both exist, else one of 12 S3.4's reasons -- never an exception
    other than HeadroomNotComputable, and never a number from a missing anchor."""
    m = Metric.model_validate(metric_doc(mid))
    mine = [b for b in baselines if b['metric'] == mid]
    [ceiling] = [b['value'] for b in mine if b.get('is_primary')]
    floors = [b['value'] for b in mine if b['kind'] in FLOOR_KINDS and b.get('value') is not None]
    if m.headroom_null_reason() is not None:
        with pytest.raises(HeadroomNotComputable) as e:
            m.headroom_consumed(ceiling, 0.0, ceiling)
        assert e.value.reason in NULL_REASONS
    elif floors:
        assert m.headroom_consumed(sota=ceiling, baseline=floors[0], ceiling=ceiling) == pytest.approx(1.0)
        assert m.headroom_consumed(sota=floors[0], baseline=floors[0], ceiling=ceiling) == pytest.approx(0.0)
    else:
        assert all(b.get('value_absent_reason') for b in mine if b['kind'] in FLOOR_KINDS)


def test_the_dummy_floors_are_the_v1_tables_and_sit_below_their_ceilings(baselines):
    by_id = {b['id']: b for b in baselines}
    assert by_id['base-matbench-discovery-f1-dummy']['value'] == 0.185
    assert by_id['base-matbench-discovery-mae-dummy']['value'] == 0.124
    assert by_id['base-matbench-discovery-f1-dummy']['kind'] == 'random-chance'
    assert by_id['base-matbench-discovery-f1-maximum']['value'] == 1.0
    assert by_id['base-matbench-discovery-mae-zero']['value'] == 0.0


def test_the_md_and_diatomics_subsets_score_their_own_metric(entry):
    by_id = {s.id: s for s in entry.subsets}
    assert by_id[BID + '#md'].metric_override == 'matbench-cmds'
    assert by_id[BID + '#diatomics'].metric_override == 'matbench-cds'
    assert by_id[BID + '#phonons'].metric_override == 'kappa-srme'


# ---- and each check catches the case the verification names -------------------------------------------------

@pytest.mark.parametrize('mid', SIX)
def test_a_metric_without_its_range_fails(mid):
    doc = {k: v for k, v in metric_doc(mid).items() if k != 'range'}
    assert metric_problems(doc) == ['%s has no range' % mid]


@pytest.mark.parametrize('mid', SIX)
def test_a_metric_without_its_optimum_is_refused(mid):
    doc = {k: v for k, v in metric_doc(mid).items() if k != 'optimum'}
    with pytest.raises(ValidationError, match='optimum'):
        metric_problems(doc)


def test_a_higher_is_better_metric_without_an_upper_bound_fails():
    doc = copy.deepcopy(metric_doc('matbench-cmds'))
    del doc['range']['max']
    assert metric_problems(doc) == ['matbench-cmds: a higher-is-better metric with no range.max']


def test_empty_tiers_fail(entry):
    assert tier_problems(entry.model_copy(update={'training_data_eligibility_tiers': []})) == \
        ['training_data_eligibility_tiers is empty']


def test_a_tier_set_without_the_papers_compliant_tier_fails(entry):
    kept = [t for t in entry.training_data_eligibility_tiers if t.id != 'compliant']
    assert tier_problems(entry.model_copy(update={'training_data_eligibility_tiers': kept})) == \
        ['the compliance tiers lack compliant']


def test_without_material_extra_the_check_fails(entry):
    stripped = entry.model_copy(update={'comparability': entry.comparability.model_copy(update={'material_extra': []})})
    assert material_problems(stripped) == ['eligibility_track is not in comparability.material_extra']


def test_a_baseline_with_neither_a_value_nor_a_reason_is_refused(baselines):
    raw = copy.deepcopy(baselines)
    floor = next(b for b in raw if b.get('value_absent_reason'))
    del floor['value_absent_reason']
    with pytest.raises(ValidationError, match='value or a value_absent_reason'):
        Baseline.model_validate(floor)
    assert any('value or a value_absent_reason' in p for p in baseline_problems(raw))


def test_a_baseline_value_without_its_source_is_refused(baselines):
    raw = copy.deepcopy(baselines)
    anchor = next(b for b in raw if b.get('value') is not None)
    del anchor['source']
    assert any('needs its source' in p for p in baseline_problems(raw))


def test_a_baseline_quote_not_in_its_source_fails(baselines):
    raw = copy.deepcopy(baselines)
    anchor = next(b for b in raw if b.get('evidence'))
    anchor['evidence'][0]['quote'] = 'Dummy 0.999 1 0.154'
    assert any('quote not in' in p for p in baseline_problems(raw))


def test_a_metric_left_without_a_floor_record_fails(baselines):
    raw = [b for b in baselines if b['id'] != 'base-matbench-discovery-cds-floor']
    assert baseline_problems(raw) == ['matbench-cds: no floor record, not even an absent one']
