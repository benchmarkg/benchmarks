"""The unit, metric-definition and sanity-band gates (P3-S2-T06; 07 S8).

The done-when: "A fixture putting 11,181.87 into a 0-1 metric is rejected as Unresolved(reason="unparseable"),
and a scale-less stanza hard-fails." Both are below, with the rest of each gate's rule.
"""
import glob
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import gates as G  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

STANZA = ('benchmark_ref: xx\nfamily: external-scrape\nscore_column: Score\n%sscale_source: benchmark_metadata.csv\n'
          'metric_ref: x-score\nsource_ref: src-x\n')


def stanza(tmp_path, stem, scale='scale: 1.0\n'):
    d = tmp_path / 'epoch'
    d.mkdir(exist_ok=True)
    (d / (stem + '.yaml')).write_text(STANZA % scale, encoding='utf-8')
    return str(tmp_path)


def metric(**kw):
    doc = dict(id='x-score', name='X', definition='a test metric', value_type='ratio', optimum='max',
               sources=['src-x'])
    doc.update(kw)
    return Metric.model_validate(doc)


FRACTION = metric(range={'min': 0, 'max': 1})


def real(mid):
    return Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))


# ---- the done-when ----------------------------------------------------------------------------------------

def test_dollars_in_a_0_1_metric_are_rejected_as_unparseable(tmp_path):
    root = stanza(tmp_path, 'vending')
    value, u = G.check(11181.87, 'epoch', 'csv:vending', FRACTION, root=root)
    assert value is None
    assert (u.reason, u.field, u.observed, u.source_key) == ('unparseable', 'value', '11181.87', 'csv:vending')
    assert '[0, 1]' in u.human_task


def test_a_scale_less_stanza_hard_fails(tmp_path):
    root = stanza(tmp_path, 'noscale', scale='')
    with pytest.raises(G.GateError, match='unit-guard') as e:
        G.check(0.5, 'epoch', 'csv:noscale', FRACTION, root=root)
    assert e.value.gate == 'unit-guard' and 'Stanza scale Field required' in ' '.join(str(e.value).split())


# ---- the unit guard ---------------------------------------------------------------------------------------

def test_a_claim_with_no_stanza_is_refused_too(tmp_path):
    (tmp_path / 'epoch').mkdir()
    with pytest.raises(G.GateError, match='has no mapping stanza'):
        G.unit_guard('epoch', 'csv:missing', str(tmp_path))


def test_the_scale_is_applied_before_the_band(tmp_path):
    root = stanza(tmp_path, 'pct', scale='scale: 0.01\n')
    assert G.check(82.35, 'epoch', 'csv:pct', FRACTION, root=root) == (pytest.approx(0.8235), None)


# ---- the metric definition --------------------------------------------------------------------------------

def test_a_metric_with_no_range_no_unbounded_and_not_qualitative_is_refused():
    with pytest.raises(G.GateError, match='metric-definition'):
        G.metric_definition(metric())
    with pytest.raises(G.GateError):
        G.metric_definition(metric(range={}))                      # an empty range is no range
    G.metric_definition(FRACTION)
    G.metric_definition(metric(value_type='currency', unbounded=True, headroom_computable=False))
    G.metric_definition(metric(value_type='qualitative'))


def test_every_curated_metric_but_matbench_cps_is_defined_well_enough_to_ingest_against():
    # matbench-cps says "No source states its range", on purpose: the gate refuses an ingested CPS until
    # someone models it, which is 07 S8's point ("modelled before they are ingested")
    refused = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'metrics', '*.yaml'))):
        m = Metric.model_validate(read_yaml(p))
        try:
            G.metric_definition(m)
        except G.GateError:
            refused.append(m.id)
    assert refused == ['matbench-cps']


# ---- the sanity band --------------------------------------------------------------------------------------

def test_the_anchors_band_is_chance_and_ceiling_with_the_tolerance():
    m = metric(range={'min': 0, 'max': 1}, chance_baseline=0.25, score_ceiling=1.0)
    b = G.band(m)
    assert (b.basis, round(b.lo, 6), round(b.hi, 6)) == ('anchors', 0.23, 1.02)
    assert G.sanity_band(0.2, m, 'k') is not None and G.sanity_band(1.01, m, 'k') is None


def test_a_lower_is_better_ceiling_below_its_baseline_still_bands():
    m = metric(optimum='min', range={'min': 0, 'max': 1}, chance_baseline=0.25, score_ceiling=0.0)
    assert G.sanity_band(0.1, m, 'k') is None and G.sanity_band(0.3, m, 'k') is not None


def test_the_tolerance_is_two_percent_of_the_span_not_an_absolute_0_02():
    index = metric(range={'min': 0, 'max': 100}, chance_baseline=50, score_ceiling=100)
    assert G.sanity_band(49.0, index, 'k') is None and G.sanity_band(47.9, index, 'k') is not None


def test_without_anchors_the_range_is_the_band():
    assert G.band(real('forecastbench-brier-index')).basis == 'range'
    assert G.sanity_band(62.5, real('forecastbench-brier-index'), 'k') is None
    assert G.sanity_band(0.625, FRACTION, 'k') is None and G.sanity_band(62.5, FRACTION, 'k') is not None


def test_an_unbounded_metric_is_banded_at_five_sigma_once_it_has_a_distribution():
    elo = metric(value_type='elo', unbounded=True, headroom_computable=False)
    few = [1200, 1300]
    assert G.band(elo, few).basis == 'not-evaluated' and G.sanity_band(0.71, elo, 'k', few) is None
    hist = [1100, 1200, 1250, 1300, 1400, 1350]
    b = G.band(elo, hist)
    assert b.basis == 'sigma' and b.lo < 1100 and b.hi > 1400
    assert G.sanity_band(1500, elo, 'k', hist) is None
    assert G.sanity_band(0.71, elo, 'k', hist) is not None                  # a 0-1 rate in an Elo field


def test_an_unbounded_metric_keeps_its_declared_floor():
    horizon = real('metr-time-horizon-50')                                  # minutes, range.min 0, unbounded
    assert horizon.unbounded and G.band(horizon).basis == 'range'
    assert G.sanity_band(-3.0, horizon, 'k') is not None
    assert G.band(horizon, [10, 20, 30, 40, 50]).basis == 'range+sigma'


def test_vending_dollars_pass_their_own_metric():
    # the same 11,181.87 that a 0-1 metric rejects is a plausible balance in the currency metric
    assert G.sanity_band(11181.87, real('vending-bench-2-money-balance'), 'k') is None


def test_history_reads_the_curated_claims_of_one_metric():
    values = G.history('mmlu-score')
    assert values and all(0 <= v <= 1 for v in values)
    assert G.history('no-such-metric') == []
    assert not math.isnan(sum(values))


# ---- over the Epoch export --------------------------------------------------------------------------------

EPOCHDL = os.path.join(ROOT, 'epochdl')
needs_epoch = pytest.mark.skipif(not glob.glob(os.path.join(EPOCHDL, '*.csv')),
                                 reason='epochdl/ is not in the working tree (00 S8.1)')


def rows(stem, column):
    import csv
    with open(os.path.join(EPOCHDL, stem + '.csv'), encoding='utf-8', newline='') as f:
        return [float(r[column]) for r in csv.DictReader(f) if (r[column] or '').strip()]


@needs_epoch
def test_every_epoch_row_against_a_curated_metric_passes_all_three_gates():
    from ingest.mappings.schema import load_all
    checked = 0
    for key, s in sorted(load_all('epoch').items()):
        path = os.path.join(ROOT, 'data', 'metrics', s.metric_ref + '.yaml')
        if not os.path.exists(path):
            continue
        m, hist = real(s.metric_ref), G.history(s.metric_ref)
        for v in rows(key[4:], s.score_column):
            assert G.check(v, 'epoch', key, m, hist)[1] is None, (key, v)
            checked += 1
    assert checked >= 700            # 729 on 2026-10-06: critpt, forecastbench, mmlu, swe-bench, vending, webdev


@needs_epoch
def test_livebench_at_epochs_metadata_scale_is_caught_row_by_row():
    # the trap P3-S2-T04 found by hand: benchmark_metadata.csv says 1.0, the column is 0-100
    values = rows('live_bench_external', 'Global average')
    rejected = [v for v in values if G.sanity_band(v * 1.0, FRACTION, 'csv:live_bench_external')]
    assert len(rejected) == len(values) == 64
    assert not [v for v in values if G.sanity_band(v * 0.01, FRACTION, 'csv:live_bench_external')]
