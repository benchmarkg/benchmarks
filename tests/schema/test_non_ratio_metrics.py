"""The four non-ratio metrics of the Epoch corpus (P3-S2-T05; 04 S6, 12 S3.4, 07 S8).

DONE WHEN: "Each of the four metrics validates and none can accept a numeric claim without declaring its
bound, so the metric-definition gate can pass." 07 S8's gate: the metric declares "either a `range`, or
`unbounded: true` with a `value_type`, or `value_type: qualitative`". The gate itself is P3-S2-T06's
(ingest/gates.py); `declares_bound` below is its condition, stated once here so these records are held to
it before that code exists.

Dollars, minutes and Elo are the three 07 S8 names ("must be modelled before they are ingested, not
discovered at 2am"); the 0-10 scale is the fourth that Epoch's `scale` column would silently rescale.
"""
import csv
import os
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.metric import HeadroomNotComputable, Metric  # noqa: E402

EPOCH = os.path.join(ROOT, 'epochdl')             # gitignored (00 S8.1): present only where it was downloaded

# metric id -> (Epoch file, the column its values come from, 12 S3.4's null reason)
FOUR = {
    'vending-bench-2-money-balance': ('vending_bench_2', 'Score', 'unbounded-metric'),
    'metr-time-horizon-50': ('metr_time_horizons', 'Time horizon', 'unbounded-metric'),
    'webdev-arena-score': ('webdev_arena', 'Arena Score', 'unbounded-metric'),
    'lech-mazur-writing-v1-score': ('lech_mazur_writing', 'Mean score', 'metric-not-headroom-computable'),
}


def load(mid: str) -> dict:
    with open(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml'), encoding='utf-8') as fh:
        return YAML(typ='safe', pure=True).load(fh)


def declares_bound(m: Metric) -> bool:
    """07 S8's metric-definition gate: a numeric claim is refused against a metric without this."""
    return m.range is not None or (m.unbounded and m.value_type is not None) or m.value_type == 'qualitative'


@pytest.mark.parametrize('mid', sorted(FOUR))
def test_each_metric_validates_and_declares_its_bound(mid):
    m = Metric.model_validate(load(mid))
    assert declares_bound(m)
    assert m.value_type != 'ratio'                        # the task: the four NON-ratio metrics
    assert m.optimum == 'max' and m.units


@pytest.mark.parametrize('mid', sorted(FOUR))
def test_without_its_bound_the_gate_would_refuse_it(mid):
    raw = {k: v for k, v in load(mid).items() if k not in ('range', 'unbounded')}
    raw['headroom_computable'] = False
    assert not declares_bound(Metric.model_validate(raw))


def test_the_value_types_are_the_four_the_task_names():
    types = {mid: Metric.model_validate(load(mid)).value_type for mid in FOUR}
    assert types == {'vending-bench-2-money-balance': 'currency', 'metr-time-horizon-50': 'duration',
                     'webdev-arena-score': 'elo', 'lech-mazur-writing-v1-score': 'ordinal'}
    lech = Metric.model_validate(load('lech-mazur-writing-v1-score'))
    assert (lech.range.min, lech.range.max, lech.unbounded) == (0, 10, False)


def test_only_the_elo_metric_requires_a_pool():
    assert {mid for mid in FOUR if Metric.model_validate(load(mid)).requires_pool} == {'webdev-arena-score'}


@pytest.mark.parametrize('mid', sorted(FOUR))
def test_none_carries_headroom_and_each_says_why(mid):
    m = Metric.model_validate(load(mid))
    assert m.headroom_computable is False
    assert m.headroom_null_reason() == FOUR[mid][2]
    with pytest.raises(HeadroomNotComputable):
        m.headroom_consumed(1.0, 0.0, 2.0)


@pytest.mark.skipif(not os.path.isdir(EPOCH), reason='epochdl/ is not in the working tree (00 S8.1)')
@pytest.mark.parametrize('mid', sorted(FOUR))
def test_every_epoch_value_fits_the_declared_bound(mid):
    """Where the corpus is present: the metric accepts every row Epoch has, in the file's own unit."""
    m = Metric.model_validate(load(mid))
    name, column, _ = FOUR[mid]
    with open(os.path.join(EPOCH, name + '_external.csv'), encoding='utf-8') as fh:
        values = [float(r[column]) for r in csv.DictReader(fh) if r[column].strip()]
    assert values
    lo = m.range.min if m.range and m.range.min is not None else float('-inf')
    hi = m.range.max if m.range and m.range.max is not None else float('inf')
    assert all(lo <= v <= hi for v in values), (min(values), max(values))
    if not m.unbounded:
        assert max(values) > 1                              # Epoch's 0-1 `scale` has not been applied
