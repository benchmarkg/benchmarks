"""WeatherBench 2: lead time, the operational ceiling and the no-aggregate flag (P3-S6-T04; 04 S8, 12 S3.2, S3.4).

The verify: "bench validate --tier all, plus `uv run pytest tests/test_weatherbench2.py -q` asserting
no_legitimate_aggregate is set on weatherbench-2, that the (variable, level, lead time, metric) grid is recorded as
secondary_axes, that lead_time is material on the comparability profile, and that the ECMWF IFS/ENS ceiling and the
climatology/persistence floors exist as Baselines." The done-when: "The benchmark that refuses to produce a ranking
is stored without the index inventing one." Each of the four is a function below that returns what is wrong. It runs
on the committed records, which must pass, and on a copy broken the way the verification names, which must fail, so
the test also fails if a check stops catching its case.

  - The flag: no_legitimate_aggregate with its quoted basis, aggregation_policy none-by-design and no
    headline_metric. An entry that drops the flag or names a headline metric is caught.
  - The grid. secondary_axes is a closed vocabulary of five cost axes (schema.benchmark.SecondaryAxis) and refuses a
    grid axis, which is asserted, so the day the schema changes this test says the entry must move. The grid is
    recorded where the schema can hold it, and secondary_axes_note says so: the headline variables with their
    pressure levels as subsets, each quoted from the paper's Table 3; the headline metrics as Metric records; lead
    time as a material condition; the evaluation year as versions. Every cell of that grid gets a comparability key
    of its own, and dropping any one axis makes two cells collide, which is the failure case.
  - lead_time is in comparability.material_extra and in the resolved material set, so a 72 h and a 240 h score never
    share a key. The facets alone hold it only through uncertainty-calibration-score, the one method that resolves
    the `forecasting` profile here; without material_extra, dropping that method would drop lead_time.
  - The anchors: IFS HRES and IFS ENS are operational-system ceilings, primary on RMSE and CRPS; the climatology and
    persistence forecasts are classical-algorithm floors. Every value carries its source and a quote found in that
    Source's extract, an absent value a reason, and on these lower-is-better metrics the ceiling lies below its
    floors at the stated cell. IFS stored as a floor, a floor dropped, a value whose quote is not in its Source:
    each is caught.

Headroom's null with reason vector-valued-by-design is P3-S9-T04's to assert, where headroom exists.
"""
import copy
import dataclasses
import os
import sys
import typing

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import CEILING_ANCHOR, FLOOR_KINDS, Baseline, BaselineFile  # noqa: E402
from schema.benchmark import Benchmark, SecondaryAxis, load_benchmark  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

BID = 'weatherbench-2'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'earth-climate', BID + '.yaml')
BASELINES = os.path.join(ROOT, 'data', 'baselines', BID + '.yaml')
# The paper's Table 3: each headline variable and its pressure level (None for a surface variable).
HEADLINE = {'z500': 500, 't850': 850, 'q700': 700, 'wv-ws850': 850, 't2m': None, 'ws10': None, 'mslp': None,
            'tp24hr': None}
METRICS = ('weatherbench-2-rmse', 'weatherbench-2-seeps', 'weatherbench-2-crps')
YEARS = {'2020', '2022'}
# What secondary_axes_note must name: the four axes of the task, and where each of them is recorded.
AXES = ('variable', 'pressure level', 'lead time', 'metric')
HOMES = ('subsets[]', 'metrics[]', 'EvalConditions.lead_time', 'versions[]')
# The anchors 12 S3.2 assigns: per metric, the operational ceiling and the classical floors.
CEILING = {'weatherbench-2-rmse': 'ifs-hres', 'weatherbench-2-crps': 'ifs-ens'}
FLOORS = ('climatology', 'persistence')


def source_doc(sid: str) -> dict | None:
    for d, _, files in os.walk(os.path.join(ROOT, 'data', 'sources')):
        if sid + '.yaml' in files:
            return read_yaml(os.path.join(d, sid + '.yaml'))
    return None


def quoted(sid: str, quote: str | None) -> bool:
    s = source_doc(sid)
    return s is not None and bool(quote) and quote_found(quote, s.get('quote_extract') or '')


def metric(mid: str) -> Metric:
    return Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))


@pytest.fixture(scope='module')
def entry() -> Benchmark:
    return load_benchmark(ENTRY)


@pytest.fixture(scope='module')
def baselines() -> list[dict]:
    return read_yaml(BASELINES)


def with_fields(**changes) -> Benchmark:
    """The committed entry with some top-level fields replaced, validated again."""
    return Benchmark.model_validate({**read_yaml(ENTRY), **changes})


# ---- the four checks ----------------------------------------------------------------------------------------

def aggregate_problems(b: Benchmark) -> list[str]:
    out = []
    if not b.no_legitimate_aggregate:
        out.append('no_legitimate_aggregate is not set')
    if b.aggregation_policy != 'none-by-design':
        out.append('aggregation_policy is %s, not none-by-design' % b.aggregation_policy)
    if b.headline_metric is not None:
        out.append('headline_metric %s ranks a benchmark that refuses a ranking' % b.headline_metric)
    basis = b.annotations().get('no_legitimate_aggregate_basis') or {}
    if not quoted(basis.get('source', ''), basis.get('quote')):
        out.append('no_legitimate_aggregate_basis has no quote found in its source')
    return out


def grid_problems(b: Benchmark) -> list[str]:
    out = []
    if b.secondary_axes:
        out.append('secondary_axes holds %s, which are cost axes WeatherBench 2 does not report' % b.secondary_axes)
    note = b.annotations().get('secondary_axes_note') or ''
    out += ['secondary_axes_note does not name the %s axis' % a for a in AXES if a not in note]
    out += ['secondary_axes_note does not say the grid is in %s' % h for h in HOMES if h not in note]
    # variable x level: one subset per headline variable, its level in its label, quoted from Table 3
    subsets = {s.id.split('#', 1)[1]: s for s in b.subsets}
    out += ['the headline variable %s has no subset' % v for v in HEADLINE if v not in subsets]
    for v, level in HEADLINE.items():
        s = subsets.get(v)
        if s is None:
            continue
        if not s.scored_separately:
            out.append('%s is not scored separately' % s.id)
        if level is not None and '%d hPa' % level not in s.label:
            out.append('%s does not name its level %d hPa' % (s.id, level))
        if not s.evidence or not all(quoted(e.source, e.quote) for e in s.evidence):
            out.append('%s has no quote from Table 3 found in its source' % s.id)
    # metric: the headline metrics, each a Metric record
    metrics = list(b.metrics) if isinstance(b.metrics, list) else []
    out += ['the headline metric %s is not in metrics' % m for m in METRICS if m not in metrics]
    out += ['%s has no Metric record' % m for m in metrics
            if not os.path.isfile(os.path.join(ROOT, 'data', 'metrics', m + '.yaml'))]
    # lead time: a material condition; evaluation year: a version
    if 'lead_time' not in comp.resolve_profile(b).material:
        out.append('lead_time is not material')
    if {v.version for v in b.versions} != YEARS:
        out.append('the evaluation years are not the versions')
    return out


def material_problems(b: Benchmark) -> list[str]:
    out = []
    if 'lead_time' not in b.comparability.material_extra:
        out.append('lead_time is not in comparability.material_extra')
    if 'lead_time' not in comp.resolve_profile(b).material:
        out.append('lead_time is not material in the resolved profile')
    return out


def baseline_problems(raw: list[dict]) -> list[str]:
    """Each Baseline loads, carries a value with its source and a quote found in it or a value_absent_reason, and
    every evidence quote is in its Source's extract; each metric has the IFS ceiling as its one primary and both
    classical floors; and on these lower-is-better metrics the ceiling lies below every floor with a value."""
    out, records = [], []
    for d in raw:
        try:
            records.append(Baseline.model_validate(d))
        except ValidationError as e:
            out.append('%s: %s' % (d.get('id'), e.errors()[0]['msg']))
    try:
        BaselineFile.model_validate(raw)
    except ValidationError as e:
        out.append(e.errors()[0]['msg'])
    for x in records:
        if x.benchmark_version.split('@')[0] != BID:
            out.append('%s is on %s' % (x.id, x.benchmark_version))
        for ev in x.evidence:
            if not quoted(ev.source, ev.quote):
                out.append('%s: quote not in %s: %r' % (x.id, ev.source, ev.quote))
        if x.value is not None and not any(e.source == x.source and (': %g;' % x.value) in (e.quote or '')
                                           for e in x.evidence):
            out.append('%s: no quote from %s states its value %g' % (x.id, x.source, x.value))
    for mid, ceiling in CEILING.items():
        mine = [x for x in records if x.metric == mid]
        primary = [x for x in mine if x.is_primary]
        if len(primary) != 1 or primary[0].id.split('-')[-2:] != ceiling.split('-'):
            out.append('%s: the primary is not the %s ceiling' % (mid, ceiling))
        elif primary[0].kind != 'operational-system' or primary[0].value is None:
            out.append('%s: %s is not an operational-system ceiling with a value' % (mid, primary[0].id))
        for floor in FLOORS:
            got = [x for x in mine if x.id.endswith('-' + floor)]
            if not got or got[0].kind not in FLOOR_KINDS:
                out.append('%s: no %s floor' % (mid, floor))
        if primary and primary[0].value is not None and metric(mid).optimum == 'min':
            above = [x.id for x in mine if x.is_floor and x.value is not None and x.value <= primary[0].value]
            out += ['%s: the floor %s is not above the ceiling' % (mid, f) for f in above]
    return out


# ---- the committed records pass -----------------------------------------------------------------------------

def test_verify_no_legitimate_aggregate_is_set(entry):
    assert aggregate_problems(entry) == []
    assert entry.no_legitimate_aggregate is True and entry.headline_metric is None


def test_verify_the_grid_is_recorded(entry):
    assert grid_problems(entry) == []
    assert entry.secondary_axes == []           # the vocabulary's cost axes; WeatherBench 2 reports none


def test_verify_lead_time_is_material(entry):
    assert material_problems(entry) == []
    r = comp.resolve_profile(entry)
    assert 'forecasting' in r.profiles and r.weights['lead_time'] == 1.0


def test_verify_the_ifs_ceiling_and_the_classical_floors_exist_as_baselines(baselines):
    assert baseline_problems(baselines) == []
    by_id = {b['id']: b for b in baselines}
    assert by_id['base-weatherbench-2-2020-z500-rmse-ifs-hres']['value'] == 304.354
    assert by_id['base-weatherbench-2-2020-z500-crps-ifs-ens']['value'] == 114.909
    assert by_id['base-weatherbench-2-2020-z500-rmse-climatology']['value'] == 820.873
    assert by_id['base-weatherbench-2-2020-z500-rmse-persistence']['value'] == 1049.58
    assert by_id['base-weatherbench-2-2020-z500-crps-climatology']['value'] == 369.95
    # No persistence forecast is published for the probabilistic scores: absent, with the reason.
    assert by_id['base-weatherbench-2-2020-z500-crps-persistence']['value_absent_reason'] == 'no-published-comparator'


def test_the_ceilings_are_the_entrys_anchor_type_and_the_floors_have_none(entry, baselines):
    records = [Baseline.model_validate(d) for d in baselines]
    assert {x.ceiling_anchor_type for x in records if not x.is_floor} == {entry.data.ceiling_anchor_type}
    assert entry.data.ceiling_anchor_type == 'operational-system' == CEILING_ANCHOR['operational-system']
    assert {x.kind for x in records if x.is_floor} == {'classical-algorithm'}


def test_every_anchor_is_one_stated_cell_of_the_grid(entry, baselines):
    """Baseline has no lead-time, region or resolution field: each record is the same cell, its subset and version
    in fields and the rest in its notes, and its Metric is one of the entry's headline metrics."""
    subsets = {s.id for s in entry.subsets}
    for d in baselines:
        assert d['subset'] == 'weatherbench-2#z500' and d['subset'] in subsets
        assert d['benchmark_version'] == 'weatherbench-2@2020'
        assert d['metric'] in entry.metrics and d['metric'] in CEILING
        if d.get('value') is not None:
            assert 'lead_time 120 h' in d['evidence'][0]['quote'] and 'region global' in d['evidence'][0]['quote']


def test_the_metrics_are_lower_is_better_with_a_floor_of_zero():
    for mid in METRICS:
        m = metric(mid)
        assert m.optimum == 'min' and m.range is not None and m.range.min == 0 and m.range.max is None
        assert m.headroom_null_reason() is None     # the benchmark's flag, not the metric, refuses an aggregate


# ---- and each check catches the case the verification names -------------------------------------------------

def test_dropping_the_flag_fails():
    assert aggregate_problems(with_fields(no_legitimate_aggregate=False)) == \
        ['no_legitimate_aggregate is not set']


def test_inventing_a_ranking_fails():
    """The done-when's case: an index that picks a headline metric for the benchmark that refuses one."""
    assert aggregate_problems(with_fields(headline_metric='weatherbench-2-rmse')) == \
        ['headline_metric weatherbench-2-rmse ranks a benchmark that refuses a ranking']


def test_the_schema_refuses_the_grid_in_secondary_axes():
    """The gap, made explicit: secondary_axes takes only the five cost axes, so the grid cannot be written there.
    When the vocabulary or a score-axes field changes, this fails and the entry should move its grid."""
    assert set(typing.get_args(SecondaryAxis)) == {'cost', 'latency', 'throughput', 'energy', 'reliability'}
    for axis in ('variable', 'level', 'lead_time', 'metric'):
        with pytest.raises(ValidationError, match='secondary_axes'):
            with_fields(secondary_axes=[axis])


def test_a_grid_without_one_of_its_axes_fails(entry):
    note = entry.annotations()['secondary_axes_note']
    dropped = [s for s in entry.subsets if s.id != 'weatherbench-2#q700']
    assert grid_problems(entry.model_copy(update={'subsets': dropped})) == ['the headline variable q700 has no subset']
    assert grid_problems(entry.model_copy(update={'metrics': list(METRICS[:2])})) == \
        ['the headline metric weatherbench-2-crps is not in metrics']
    assert grid_problems(with_fields(secondary_axes_note=note.replace('lead time', 'horizon'))) == \
        ['secondary_axes_note does not name the lead time axis']


CONDITIONS = dict(decontamination_applied=False, eligibility_track='scorecard', resolution_window='none',
                  subset_used='full', training_data_eligibility=None, training_data_policy='open')


def key(resolution, lead_time, subset='weatherbench-2#z500', metric_id='weatherbench-2-rmse', year='2020'):
    cond = EvalConditions(id='cond-0123456789ab', lead_time=lead_time, **CONDITIONS)
    return comp.compute(resolution, cond, '%s@%s' % (BID, year), metric_id, subset).comparability_key


def test_every_cell_of_the_grid_has_its_own_key(entry):
    r = comp.resolve_profile(entry)
    cells = [(lt, '%s#%s' % (BID, v), m, y) for lt in ('72 h', '240 h') for v in HEADLINE for m in METRICS
             for y in sorted(YEARS)]
    assert len({key(r, *c) for c in cells}) == len(cells)


def test_a_3_day_and_a_10_day_score_never_share_a_key(entry):
    r = comp.resolve_profile(entry)
    assert key(r, '72 h') != key(r, '240 h')


def test_without_lead_time_material_two_lead_times_collide(entry):
    """The failure case: take lead_time out of the material set and a 3-day and a 10-day score are one key."""
    r = comp.resolve_profile(entry)
    blind = dataclasses.replace(r, material=tuple(f for f in r.material if f != 'lead_time'),
                                weights={f: w for f, w in r.weights.items() if f != 'lead_time'})
    assert key(blind, '72 h') == key(blind, '240 h')


def test_without_material_extra_a_facet_change_would_drop_lead_time(entry):
    """lead_time reaches the facets' material set through uncertainty-calibration-score alone (the `forecasting`
    profile; statistical-fit resolves `surrogate-fit`, which has no horizon). material_extra is what keeps it."""
    no_ucs = [m for m in entry.evaluation_method if m != 'uncertainty-calibration-score']
    pinned = with_fields(evaluation_method=no_ucs)
    assert 'lead_time' in comp.resolve_profile(pinned).material
    bare = with_fields(evaluation_method=no_ucs, comparability={'material_extra': []})
    assert 'lead_time' not in comp.resolve_profile(bare).material
    assert material_problems(bare) == ['lead_time is not in comparability.material_extra',
                                       'lead_time is not material in the resolved profile']


def test_the_ifs_forecast_stored_as_a_floor_fails(baselines):
    """12 S3.2: "The operational forecast is a ceiling, not a floor". Filed as a classical floor, it is caught."""
    raw = copy.deepcopy(baselines)
    hres = next(b for b in raw if b['id'].endswith('-rmse-ifs-hres'))
    hres['kind'] = 'classical-algorithm'
    assert 'weatherbench-2-rmse: base-weatherbench-2-2020-z500-rmse-ifs-hres is not an operational-system ceiling ' \
        'with a value' in baseline_problems(raw)


def test_a_dropped_floor_fails(baselines):
    raw = [b for b in baselines if not b['id'].endswith('-rmse-persistence')]
    assert baseline_problems(raw) == ['weatherbench-2-rmse: no persistence floor']


def test_a_value_whose_quote_is_not_in_its_source_fails(baselines):
    raw = copy.deepcopy(baselines)
    clim = next(b for b in raw if b['id'].endswith('-rmse-climatology'))
    clim['value'] = 820.5
    clim['evidence'][0]['quote'] = 'rmse.geopotential, region global, level 500, lead_time 120 h: 820.5;'
    assert baseline_problems(raw) == [
        "base-weatherbench-2-2020-z500-rmse-climatology: quote not in "
        "src-weatherbench-2-results-climatology-vs-era5-240x121-2020: "
        "'rmse.geopotential, region global, level 500, lead_time 120 h: 820.5;'"]


def test_a_floor_below_its_ceiling_fails(baselines):
    raw = copy.deepcopy(baselines)
    hres = next(b for b in raw if b['id'].endswith('-rmse-ifs-hres'))
    hres['value'] = 1100.0
    hres['evidence'][0]['quote'] = 'rmse.geopotential, region global, level 500, lead_time 240 h: 801.499;'
    problems = baseline_problems(raw)
    assert 'weatherbench-2-rmse: the floor base-weatherbench-2-2020-z500-rmse-persistence is not above the ceiling' \
        in problems
    assert 'base-weatherbench-2-2020-z500-rmse-ifs-hres: no quote from ' \
        'src-weatherbench-2-results-hres-vs-hres-t0-240x121-2020 states its value 1100' in problems


def test_a_baseline_with_neither_a_value_nor_a_reason_is_refused(baselines):
    raw = copy.deepcopy(baselines)
    absent = next(b for b in raw if b.get('value_absent_reason'))
    del absent['value_absent_reason']
    assert any('value or a value_absent_reason' in p for p in baseline_problems(raw))
