"""The Well / PDEBench / FAIR Universe: coverage and error-norm metrics (P3-S6-T08; 04 S6, S7; 12 S3.2, S3.4).

The verify: "bench validate --tier all, plus `uv run pytest tests/test_physics_metrics.py -q` asserting every
confidence-interval-coverage and PDE-error-norm Metric declares an explicit optimum (lower-is-better-optimum-zero
where the optimum is zero), declares a range or an unbounded flag, and carries either a Baseline or a
value_absent_reason." Each of the three is a function below that returns what is wrong. It runs on the committed
records, which must pass, and on copies broken the way the verification names, which must fail, so the test also
fails if a check stops catching its case.

The twelve metrics are the three entries' `metrics` lists, each of one kind:

  - a PDE error norm (The Well's VRMSE, PDEBench's eight forward metrics): its optimum is zero, so
    Metric.headroom_null_reason() answers lower-is-better-optimum-zero, and its range starts at that zero;
  - an interval metric of the FAIR Universe HiggsML Uncertainty Challenge: the coverage, whose optimum is the
    target 0.6827 and which is therefore never headroom-computable; the average width, optimum zero like an error
    norm; and the Quantile Score built from both, higher-is-better and bounded above.

The done-when, "No physics metric is treated as an accuracy", is the optimum rule: none of the eleven
non-score metrics may declare `max`, and an error norm may not declare `min` either, since that would let the
headroom code compute against a zero "ceiling" as it does for an accuracy. Headroom itself is P3-S9-T04's to
assert; the one gap it inherits is pinned here: a target optimum answers metric-not-headroom-computable, which is
not one of 12 S3.4's six null reasons (review check on fair-universe-higgsml).
"""
import copy
import math
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import Baseline, BaselineFile  # noqa: E402
from schema.benchmark import load_benchmark  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

ERROR_NORM, COVERAGE, WIDTH, SCORE = 'pde-error-norm', 'ci-coverage', 'ci-width', 'ci-score'
ENTRIES = {
    'the-well': ('physics/the-well.yaml', {'the-well-vrmse': ERROR_NORM}),
    'pdebench': ('physics/pdebench.yaml', {
        'pdebench-rmse': ERROR_NORM, 'pdebench-nrmse': ERROR_NORM, 'pdebench-max-error': ERROR_NORM,
        'pdebench-crmse': ERROR_NORM, 'pdebench-brmse': ERROR_NORM, 'pdebench-frmse-low': ERROR_NORM,
        'pdebench-frmse-mid': ERROR_NORM, 'pdebench-frmse-high': ERROR_NORM}),
    'fair-universe-higgsml': ('physics/fair-universe-higgsml.yaml', {
        'fair-universe-higgsml-quantile-score': SCORE, 'fair-universe-higgsml-coverage': COVERAGE,
        'fair-universe-higgsml-interval-width': WIDTH}),
}
KIND = {mid: kind for _, mids in ENTRIES.values() for mid, kind in mids.items()}
OWNER = {mid: bid for bid, (_, mids) in ENTRIES.items() for mid in mids}
# The optimum each kind must declare; the coverage's target is the nominal probability of a 68.27% interval.
OPTIMUM = {ERROR_NORM: 'zero', WIDTH: 'zero', COVERAGE: 'target', SCORE: 'max'}
NOMINAL_COVERAGE = 0.6827
# 12 S3.4's table: the only reasons a headroom null may give.
NULL_REASONS = {'no-baseline-established', 'unbounded-metric', 'lower-is-better-optimum-zero',
                'vector-valued-by-design', 'relative-rating-only', 'resolution-pending'}


def metric_doc(mid: str) -> dict:
    return read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml'))


def baselines_of(bid: str) -> list[dict]:
    return read_yaml(os.path.join(ROOT, 'data', 'baselines', bid + '.yaml'))


def source_doc(sid: str) -> dict | None:
    for d, _, files in os.walk(os.path.join(ROOT, 'data', 'sources')):
        if sid + '.yaml' in files:
            return read_yaml(os.path.join(d, sid + '.yaml'))
    return None


# ---- the three checks ---------------------------------------------------------------------------------------

def optimum_problems(doc: dict, kind: str) -> list[str]:
    """An explicit optimum, the one the metric's kind has: zero for an error norm or a width, with the null
    reason lower-is-better-optimum-zero and a range that starts at the zero; the 68.27% target for the coverage,
    never headroom-computable; max for the score."""
    m = Metric.model_validate(doc)                 # `optimum` is required, so a record without it raises here
    want = OPTIMUM[kind]
    if m.optimum != want:
        return ['%s: a %s\'s optimum is %s, not %s' % (m.id, kind, want, m.optimum)]
    out = []
    if want == 'zero':
        if m.headroom_null_reason() != 'lower-is-better-optimum-zero':
            out.append('%s: optimum zero, but headroom answers %s, not lower-is-better-optimum-zero'
                       % (m.id, m.headroom_null_reason()))
        if m.range is None or m.range.min != 0:
            out.append('%s: optimum zero, but the range does not start at 0' % m.id)
    if want == 'target':
        if m.optimum_target != NOMINAL_COVERAGE:
            out.append('%s: the target is %s, not the nominal %s' % (m.id, m.optimum_target, NOMINAL_COVERAGE))
        if m.headroom_computable:
            out.append('%s: a target optimum is not a ceiling, so the metric is not headroom-computable' % m.id)
    reason = m.headroom_null_reason()
    if reason is not None and reason not in NULL_REASONS and want != 'target':
        out.append('%s: headroom null reason %s is not one of 12 S3.4\'s six' % (m.id, reason))
    return out


def range_problems(doc: dict) -> list[str]:
    """A range with at least one bound, or `unbounded: true`; and for a higher-is-better metric the upper bound
    headroom reads as the ceiling, unless it is unbounded; and a target inside the range."""
    m = Metric.model_validate(doc)
    bounded = m.range is not None and (m.range.min is not None or m.range.max is not None)
    if not bounded and not m.unbounded:
        return ['%s declares neither a range nor unbounded' % m.id]
    out = []
    if m.optimum == 'max' and not m.unbounded and m.range.max is None:
        out.append('%s: a higher-is-better metric with no range.max and no unbounded flag' % m.id)
    if m.optimum == 'target' and bounded and not ((m.range.min is None or m.range.min <= m.optimum_target)
                                                  and (m.range.max is None or m.optimum_target <= m.range.max)):
        out.append('%s: the target %s lies outside the range' % (m.id, m.optimum_target))
    return out


def baseline_problems(raw: list[dict], mids) -> list[str]:
    """Every metric has a Baseline record, exactly one of them primary; every record has a value with its source
    or a value_absent_reason; and every quote is in its Source's committed extract."""
    out = []
    records = []
    for d in raw:
        try:
            records.append(Baseline.model_validate(d))
        except ValidationError as e:
            out.append('%s: %s' % (d.get('id'), e.errors()[0]['msg']))
    for x in records:
        for sid in [x.source] if x.source else []:
            if source_doc(sid) is None:
                out.append('%s cites %s, which is not under data/sources/' % (x.id, sid))
        for ev in x.evidence:
            s = source_doc(ev.source)
            if s is None or not ev.quote or not quote_found(ev.quote, s.get('quote_extract') or ''):
                out.append('%s: quote not in %s: %r' % (x.id, ev.source, ev.quote))
    for mid in mids:
        mine = [x for x in records if x.metric == mid]
        if not mine:
            out.append('%s has no Baseline record, not even a value_absent_reason' % mid)
            continue
        primary = [x for x in mine if x.is_primary]
        if len(primary) != 1:
            out.append('%s: %d primary baselines' % (mid, len(primary)))
    return out


# ---- the committed records pass -----------------------------------------------------------------------------

@pytest.mark.parametrize('mid', sorted(KIND))
def test_verify_each_metric_declares_its_explicit_optimum(mid):
    doc = metric_doc(mid)
    assert 'optimum' in doc
    assert optimum_problems(doc, KIND[mid]) == []


@pytest.mark.parametrize('mid', sorted(KIND))
def test_verify_each_metric_declares_a_range_or_unbounded(mid):
    assert range_problems(metric_doc(mid)) == []


@pytest.mark.parametrize('bid', sorted(ENTRIES))
def test_verify_each_metric_carries_a_baseline_or_a_value_absent_reason(bid):
    raw = baselines_of(bid)
    BaselineFile.model_validate(raw)                                   # one primary per (version, metric)
    assert baseline_problems(raw, ENTRIES[bid][1]) == []
    assert {b['metric'] for b in raw} == set(ENTRIES[bid][1])
    assert {b['benchmark_version'].split('@')[0] for b in raw} == {bid}


@pytest.mark.parametrize('bid', sorted(ENTRIES))
def test_each_entry_references_exactly_its_metrics(bid):
    path, mids = ENTRIES[bid]
    entry = load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', path))
    assert sorted(entry.metrics) == sorted(mids)
    assert entry.headline_metric is None or entry.headline_metric in mids


def test_no_physics_metric_is_an_accuracy():
    """The done-when: only the Quantile Score is higher-is-better, and it is not a [0, 1] share."""
    for mid, kind in KIND.items():
        m = Metric.model_validate(metric_doc(mid))
        if kind == SCORE:
            assert m.optimum == 'max' and (m.range.min, m.range.max) != (0, 1)
        else:
            assert m.optimum in ('zero', 'target') and m.higher_is_better is None


def test_coverage_and_width_name_each_other():
    cov = Metric.model_validate(metric_doc('fair-universe-higgsml-coverage'))
    width = Metric.model_validate(metric_doc('fair-universe-higgsml-interval-width'))
    assert cov.must_report_with == [width.id] and width.must_report_with == [cov.id]


def test_the_target_optimum_is_the_gap_p3_s9_t04_inherits():
    """12 S3.4 has no reason for a target optimum; the schema answers its own. Pinned so the change is seen."""
    m = Metric.model_validate(metric_doc('fair-universe-higgsml-coverage'))
    assert m.headroom_null_reason() == 'metric-not-headroom-computable'
    assert m.headroom_null_reason() not in NULL_REASONS


def test_the_anchors_are_the_bounds_and_the_quoted_scale_point():
    by_id = {b['id']: b for bid in ENTRIES for b in baselines_of(bid)}
    for mid, kind in KIND.items():
        [primary] = [b for b in baselines_of(OWNER[mid]) if b['metric'] == mid and b.get('is_primary')]
        if kind in (ERROR_NORM, WIDTH):
            assert primary['kind'] == 'theoretical-maximum' and primary['value'] == 0.0
        if kind == COVERAGE:
            assert primary['value_absent_reason'] == 'not-applicable'
    assert by_id['base-the-well-vrmse-spatial-mean']['value'] == 1.0
    assert by_id['base-the-well-vrmse-spatial-mean']['kind'] == 'classical-algorithm'
    bound = by_id['base-fair-universe-higgsml-quantile-score-bound']['value']
    assert -math.log(0.01) <= bound < -math.log(0.01) + 1e-4                       # -ln(eps), rounded up
    assert Metric.model_validate(metric_doc('fair-universe-higgsml-quantile-score')).range.max == bound


# ---- and each check catches the case the verification names -------------------------------------------------

@pytest.mark.parametrize('mid', sorted(m for m, k in KIND.items() if k == ERROR_NORM))
def test_an_error_norm_treated_as_an_accuracy_fails(mid):
    doc = dict(metric_doc(mid), optimum='max')
    assert optimum_problems(doc, ERROR_NORM) == ['%s: a %s\'s optimum is zero, not max' % (mid, ERROR_NORM)]


@pytest.mark.parametrize('mid', sorted(m for m, k in KIND.items() if k == ERROR_NORM))
def test_an_error_norm_declared_min_rather_than_zero_fails(mid):
    doc = dict(metric_doc(mid), optimum='min', headroom_computable=True)
    assert optimum_problems(doc, ERROR_NORM) == ['%s: a %s\'s optimum is zero, not min' % (mid, ERROR_NORM)]
    assert Metric.model_validate(doc).headroom_null_reason() is None   # min would let headroom be computed


@pytest.mark.parametrize('mid', sorted(KIND))
def test_a_metric_without_its_optimum_is_refused(mid):
    doc = {k: v for k, v in metric_doc(mid).items() if k not in ('optimum', 'optimum_target')}
    with pytest.raises(ValidationError, match='optimum'):
        optimum_problems(doc, KIND[mid])


def test_a_zero_optimum_whose_range_starts_elsewhere_fails():
    doc = copy.deepcopy(metric_doc('pdebench-nrmse'))
    doc['range']['min'] = 0.01
    assert optimum_problems(doc, ERROR_NORM) == ['pdebench-nrmse: optimum zero, but the range does not start at 0']


def test_an_unbounded_error_norm_loses_its_zero_reason():
    """`unbounded` answers unbounded-metric first, so an error norm flagged that way no longer reports the
    lower-is-better-optimum-zero the verification asks for."""
    doc = dict(metric_doc('the-well-vrmse'), unbounded=True)
    assert optimum_problems(doc, ERROR_NORM) == [
        'the-well-vrmse: optimum zero, but headroom answers unbounded-metric, not lower-is-better-optimum-zero']


def test_a_coverage_scored_as_a_maximum_fails():
    doc = {k: v for k, v in metric_doc('fair-universe-higgsml-coverage').items() if k != 'optimum_target'}
    doc['optimum'] = 'max'
    assert optimum_problems(doc, COVERAGE) == [
        'fair-universe-higgsml-coverage: a %s\'s optimum is target, not max' % COVERAGE]


def test_a_headroom_computable_coverage_fails():
    doc = dict(metric_doc('fair-universe-higgsml-coverage'), headroom_computable=True)
    assert optimum_problems(doc, COVERAGE) == [
        'fair-universe-higgsml-coverage: a target optimum is not a ceiling, so the metric is not headroom-computable']


@pytest.mark.parametrize('mid', sorted(KIND))
def test_a_metric_without_a_range_or_unbounded_fails(mid):
    doc = {k: v for k, v in metric_doc(mid).items() if k != 'range'}
    assert range_problems(doc) == ['%s declares neither a range nor unbounded' % mid]


def test_the_unbounded_flag_stands_in_for_a_range():
    doc = {k: v for k, v in metric_doc('fair-universe-higgsml-quantile-score').items() if k != 'range'}
    doc.update(unbounded=True, headroom_computable=False)
    assert range_problems(doc) == []


def test_a_score_without_its_upper_bound_fails():
    doc = copy.deepcopy(metric_doc('fair-universe-higgsml-quantile-score'))
    doc['range'] = {'min': -10.0}
    assert range_problems(doc) == [
        'fair-universe-higgsml-quantile-score: a higher-is-better metric with no range.max and no unbounded flag']


def test_a_coverage_target_outside_its_range_fails():
    doc = dict(metric_doc('fair-universe-higgsml-coverage'), range={'min': 0.7, 'max': 1})
    assert range_problems(doc) == ['fair-universe-higgsml-coverage: the target 0.6827 lies outside the range']


@pytest.mark.parametrize('mid', sorted(KIND))
def test_a_metric_left_without_any_baseline_fails(mid):
    bid = OWNER[mid]
    raw = [b for b in baselines_of(bid) if b['metric'] != mid]
    assert baseline_problems(raw, ENTRIES[bid][1]) == [
        '%s has no Baseline record, not even a value_absent_reason' % mid]


def test_a_baseline_with_neither_a_value_nor_a_reason_is_refused():
    raw = copy.deepcopy(baselines_of('pdebench'))
    floor = next(b for b in raw if b.get('value_absent_reason'))
    del floor['value_absent_reason']
    with pytest.raises(ValidationError, match='value or a value_absent_reason'):
        Baseline.model_validate(floor)
    assert any('value or a value_absent_reason' in p for p in baseline_problems(raw, ENTRIES['pdebench'][1]))


def test_a_baseline_value_without_its_source_is_refused():
    raw = copy.deepcopy(baselines_of('the-well'))
    del raw[0]['source']
    assert any('needs its source' in p for p in baseline_problems(raw, ENTRIES['the-well'][1]))


def test_a_baseline_quote_not_in_its_source_fails():
    raw = copy.deepcopy(baselines_of('fair-universe-higgsml'))
    anchor = next(b for b in raw if b.get('evidence'))
    anchor['evidence'][0]['quote'] = 'The final Quantile Score (the smaller the better)'
    assert any('quote not in' in p for p in baseline_problems(raw, ENTRIES['fair-universe-higgsml'][1]))


def test_a_second_primary_fails():
    raw = copy.deepcopy(baselines_of('the-well'))
    for b in raw:
        b['is_primary'] = True
    assert baseline_problems(raw, ENTRIES['the-well'][1]) == ['the-well-vrmse: 2 primary baselines']
