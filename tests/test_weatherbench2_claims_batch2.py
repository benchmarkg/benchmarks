"""WeatherBench 2's second claims, and the two rules its real data must keep: no aggregate claim, and IFS/ENS only as a
Baseline (P3-S7-T06; 04-data-model.md S8, 12-analytics-and-trends.md S3.4).

The verify: "bench validate --tier all, plus a test asserting no aggregate claim exists for this benchmark and that
IFS/ENS appears only as a Baseline record". The done-when: "Eight earth-climate claims exist and the
no-aggregate-by-design rule survives real data." That is held here as:

  1. Eight claims on the earth-climate entry, all in data/claims/weatherbench-2/: P3-S7-T05's four, every one Z500 at
     120 h or 240 h, and four more, each at a variable and a lead time none of the first four holds: T850 RMSE at
     72 h (GraphCast and Pangu-Weather), WS850 CRPS at 168 h (NeuralGCM ENS) and TP24hr SEEPS at 24 h (FuXi). With
     them every metric the entry carries has a claim. tests/test_weatherbench2_claims.py runs its one-point-of-the-grid
     rules on every claim on the benchmark, so on these too; their Sources are batch 1's four results files, the
     extracts rebuilt from the same bytes with the new windows added.
  2. No aggregate claim exists for this benchmark. The entry is none-by-design with no headline metric (asserted in
     full by tests/test_weatherbench2.py), and every claim on weatherbench-2, wherever it lives under data/claims/ (an
     adapter's shard included), keeps to it: an absolute value at one cell of the grid -- one headline variable
     (subset), one of the entry's metrics, one region (subset_used), one lead time -- equal to exactly one line of a
     results file of the maintainers' bucket. A claim on the whole benchmark, a rank, a rating or a pairwise score, a
     metric the entry does not carry, a value pooled over variables, a pooled region or lead time: each is an
     aggregate, and each is caught.
  3. IFS/ENS appears only as a Baseline record. IFS HRES and IFS ENS are the operational-system primaries of RMSE and
     CRPS in data/baselines/weatherbench-2.yaml, each from its own results file; no System record is an IFS forecast
     or another forecast the site scores as a reference (by name, or by the results file it is indexed to); and no
     claim names one as its system or opponent, or cites a reference forecast's results file. A claim by IFS HRES, a
     pairwise claim against IFS ENS, a claim on the HRES file, an IFS System record, the IFS Baseline dropped or
     stored as a floor: each is caught.
  4. Comparability: the two T850 claims share a key, the other two new claims have keys of their own, and the eight
     still form no (benchmark, subset, metric, system) group of two, so `bench report conflicts` gains no row and
     tests/report/test_reports.py's pin is untouched.
"""
import collections
import copy
import glob
import os
import re
import statistics
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import Baseline  # noqa: E402
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.source import Source  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import conflicts  # noqa: E402

BENCH = 'weatherbench-2'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'earth-climate', BENCH + '.yaml')
BASELINES = os.path.join(ROOT, 'data', 'baselines', BENCH + '.yaml')
FIRST = ('claim-97ccdee40ee2', 'claim-fd2e2bb3ecfd', 'claim-1347a99e2e5a', 'claim-b81ace24efa9')     # P3-S7-T05
# This batch: id -> (system, subset, metric, lead time)
SECOND = {'claim-dfcd552df835': ('graphcast', 't850', 'weatherbench-2-rmse', '72 h'),
          'claim-ef50cffa2b3c': ('pangu-weather', 't850', 'weatherbench-2-rmse', '72 h'),
          'claim-568dab3c8b22': ('neuralgcm-ens', 'wv-ws850', 'weatherbench-2-crps', '168 h'),
          'claim-604ec4f2c9f1': ('fuxi', 'tp24hr', 'weatherbench-2-seeps', '24 h')}
# Each headline subset's variable as the results files name it, and its pressure level (None at the surface); the
# 850 hPa wind is the wind-vector RMSE or the wind-speed CRPS (the entry's subset notes).
VARIABLE = {'z500': ('geopotential', 500), 't850': ('temperature', 850), 'q700': ('specific_humidity', 700),
            'wv-ws850': ('wind_speed', 850), 't2m': ('2m_temperature', None), 'ws10': ('10m_wind_speed', None),
            'mslp': ('mean_sea_level_pressure', None), 'tp24hr': ('total_precipitation_24hr', None)}
PREFIX = {'weatherbench-2-rmse': 'rmse', 'weatherbench-2-crps': 'crps', 'weatherbench-2-seeps': 'seeps'}
RESULTS = re.compile(r'^https://storage\.googleapis\.com/weatherbench2/benchmark_results/'
                     r'(?P<forecast>[a-z0-9_]+)_vs_(?P<truth>era5|hres_t0)_(?P<grid>\d+x\d+)_(?P<year>\d{4})\.nc$')
LEAD = re.compile(r'^(\d+) h$')
REGION = re.compile(r'^region ([a-z0-9-]+)$')
# The forecasts the site scores as references, by their results-file names: the IFS forecasts (HRES, ENS, its mean and
# one member), ERA5's own forecasts and the classical floors. Baselines here, never claims (12 S3.2).
REFERENCE = {'hres', 'ens', 'ens_mean', 'ens_single_member', 'era5_forecast', 'climatology',
             'probabilistic_climatology', 'persistence'}
IFS = re.compile(r'\b(ifs|ecmwf)\b', re.I)          # AIFS, ECMWF's learned model, is not matched, and may compete
IFS_BASELINES = {'weatherbench-2-rmse': ('base-weatherbench-2-2020-z500-rmse-ifs-hres', 'hres'),
                 'weatherbench-2-crps': ('base-weatherbench-2-2020-z500-crps-ifs-ens', 'ens')}


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def raw_claims():
    """(repo-relative path, raw mapping) for every claim under data/claims/ on weatherbench-2, wherever it lives."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict) and str(raw.get('benchmark', '')).partition('@')[0] == BENCH:
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), raw))
    return out


CLAIMS = [ResultClaim.model_validate(raw) for _, raw in raw_claims()]
SOURCES = {sid: Source.model_validate(load(os.path.join('sources', '2026'), sid))
           for sid in sorted({c.source for c in CLAIMS} | {
               'src-weatherbench-2-results-hres-vs-hres-t0-240x121-2020',
               'src-weatherbench-2-results-ens-vs-hres-t0-240x121-2020'})}
SYSTEMS = {s.id: s for s in (System.model_validate(read_yaml(p))
                             for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'systems', '*.yaml'))))}


def by_id(cid):
    return next(c for c in CLAIMS if c.id == cid)


def conditions(cid):
    return EvalConditions.model_validate(load('conditions', cid)) if cid else None


@pytest.fixture(scope='module')
def entry():
    return load_benchmark(ENTRY)


@pytest.fixture(scope='module')
def baselines():
    return read_yaml(BASELINES)


# ---- the rules, as functions the corpus tests and the failure cases share ------------------------------------------

def results_file(src):
    m = RESULTS.match(src.url or '') if src is not None else None
    return m.groupdict() if m else None


def cell(claim, cond):
    """The results-file line, up to its value, that the claim's fields name; None when they do not name one."""
    slug = (claim.subset or '').partition('#')[2]
    variable, level = VARIABLE.get(slug, (None, None))
    prefix = ('vector_rmse.wind' if slug == 'wv-ws850' and claim.metric == 'weatherbench-2-rmse'
              else '%s.%s' % (PREFIX.get(claim.metric), variable))
    lead = LEAD.match(cond.lead_time or '') if cond is not None else None
    region = REGION.match(cond.subset_used or '') if cond is not None else None
    if variable is None or claim.metric not in PREFIX or lead is None or region is None:
        return None
    at = ', level %d' % level if level is not None else ''
    return '%s, region %s%s, lead_time %s h: ' % (prefix, region.group(1), at, lead.group(1))


def line_value(extract, head):
    """The value of the one complete line `head` begins in the extract, or None (absent, cut by a window, repeated)."""
    found = re.findall(r'(?:^|\s)%s(\S+);' % re.escape(head), extract or '')
    return float(found[0]) if len(found) == 1 and found[0] != 'nan' else None


def aggregate_problems(claim, cond, src, entry_):
    """Why a claim is an aggregate -- over systems, variables, metrics, regions or lead times -- rather than one cell
    of the grid; empty when it is one cell."""
    out = []
    if claim.claim_type != 'absolute' or claim.opponent is not None or claim.rating_pool is not None:
        out.append('%s is a %s claim, an ordering of systems the benchmark refuses' % (claim.id, claim.claim_type))
    if claim.subset is None:
        out.append('%s scores the whole benchmark, not one variable' % claim.id)
    elif claim.subset not in {s.id for s in entry_.subsets}:
        out.append('%s: %s is not one headline variable' % (claim.id, claim.subset))
    if claim.metric not in entry_.metrics:
        out.append('%s: %s is not one of the metrics the entry scores a cell by' % (claim.id, claim.metric))
    if cond is None or LEAD.match(cond.lead_time or '') is None:
        out.append('%s: no single lead time' % claim.id)
    if cond is None or REGION.match(cond.subset_used or '') is None:
        out.append('%s: no single region' % claim.id)
    f = results_file(src)
    if f is None:
        out.append('%s: %s is not a results file of the maintainers\' bucket' % (claim.id, src.id))
    head = cell(claim, cond)
    if head is not None and line_value(src.quote_extract, head) != claim.value:
        out.append('%s: the value %r is not the one line %r of %s' % (claim.id, claim.value, head, src.id))
    return out


def is_reference(s):
    """A System record that is an IFS forecast, or another forecast the site scores as a reference."""
    return (s.external_ids.get('weatherbench2_results') in REFERENCE
            or any(IFS.search(n or '') for n in (s.id, s.name)))


def ifs_problems(claims, systems, sources, baselines_raw):
    """Why IFS/ENS is not only a Baseline record; empty when it is."""
    out = []
    records = {d['id']: Baseline.model_validate(d) for d in baselines_raw}
    for metric, (bid, forecast) in IFS_BASELINES.items():
        b = records.get(bid)
        if b is None:
            out.append('%s: no IFS Baseline %s' % (metric, bid))
            continue
        if (b.kind, b.is_primary, b.metric, b.value is not None) != ('operational-system', True, metric, True):
            out.append('%s is not the operational-system primary of %s with a value' % (bid, metric))
        f = results_file(sources.get(b.source))
        if f is None or f['forecast'] != forecast:
            out.append('%s is not from the %s results file' % (bid, forecast))
    out += ['%s is a System record of a reference forecast, which is a Baseline' % s.id
            for s in systems.values() if is_reference(s)]
    for c in claims:
        for role, ref in (('system', c.system), ('opponent', c.opponent)):
            if ref is None:
                continue
            s = systems.get(ref.split('@')[0])
            if s is None or is_reference(s):
                out.append('%s: its %s %s is a reference forecast or no System record' % (c.id, role, ref))
        f = results_file(sources.get(c.source))
        if f is not None and f['forecast'] in REFERENCE:
            out.append('%s cites the results file of %s, a reference forecast' % (c.id, f['forecast']))
    return out


# ---- 1. eight claims ------------------------------------------------------------------------------------------------

def test_done_when_eight_earth_climate_claims(entry):
    assert entry.domain.primary.startswith('earth-climate/') and '/earth-climate/' in ENTRY.replace(os.sep, '/')
    assert len(CLAIMS) == 8
    assert all(rel.startswith('data/claims/weatherbench-2/') for rel, _ in raw_claims())
    assert {c.id for c in CLAIMS} == set(FIRST) | set(SECOND)


@pytest.mark.parametrize('cid', sorted(SECOND))
def test_each_new_claim_is_the_cell_it_says(cid):
    c = by_id(cid)
    system, slug, metric, lead = SECOND[cid]
    cond = conditions(c.eval_conditions)
    assert (c.system, c.subset, c.metric, cond.lead_time) == (system, BENCH + '#' + slug, metric, lead)
    assert (c.benchmark, c.claim_type, c.reported_by, c.verification) == \
        (BENCH + '@2020', 'absolute', 'org-google-research', 'maintainer-verified')
    # batch 1's Source for the same system: one results file per system, reused rather than duplicated
    first = next(by_id(f) for f in FIRST if by_id(f).system == system)
    assert c.source == first.source
    assert line_value(SOURCES[c.source].quote_extract, cell(c, cond)) == c.value
    assert 'IFS' in c.notes and 'no_legitimate_aggregate' in c.notes


def test_the_new_cells_are_other_variables_and_lead_times():
    def at(cid):
        c = by_id(cid)
        return c.subset, conditions(c.eval_conditions).lead_time
    first, second = {at(c) for c in FIRST}, {at(c) for c in SECOND}
    assert not first & second
    assert {s for s, _ in first} == {BENCH + '#z500'} and BENCH + '#z500' not in {s for s, _ in second}
    assert {lead for _, lead in first}.isdisjoint({lead for _, lead in second})
    assert {lead for _, lead in first | second} == {'24 h', '72 h', '120 h', '168 h', '240 h'}


def test_every_metric_the_entry_carries_has_a_claim(entry):
    assert {c.metric for c in CLAIMS} == set(entry.metrics)


# ---- 2. no aggregate claim exists for this benchmark -------------------------------------------------------------

def test_the_entry_refuses_an_aggregate(entry):
    assert entry.no_legitimate_aggregate is True and entry.aggregation_policy == 'none-by-design'
    assert entry.headline_metric is None


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_no_aggregate_claim_exists(claim, entry):
    assert aggregate_problems(claim, conditions(claim.eval_conditions), SOURCES[claim.source], entry) == []


def _case(cid='claim-dfcd552df835'):
    c = by_id(cid)
    return c, conditions(c.eval_conditions), SOURCES[c.source]


def test_a_claim_on_the_whole_benchmark_is_caught(entry):
    c, cond, src = _case()
    found = aggregate_problems(c.model_copy(update={'subset': None}), cond, src, entry)
    assert any('scores the whole benchmark' in p for p in found)
    found = aggregate_problems(c.model_copy(update={'subset': BENCH + '#all-variables'}), cond, src, entry)
    assert any('not one headline variable' in p for p in found)


@pytest.mark.parametrize('update', [
    {'claim_type': 'ordinal', 'value': 1.0},
    {'claim_type': 'rating', 'rating_pool': 'pool-weatherbench-2-2020'},
    {'claim_type': 'pairwise', 'opponent': 'pangu-weather'},
], ids=['rank', 'rating', 'pairwise'])
def test_a_rank_a_rating_or_a_pairwise_score_is_caught(update, entry):
    c, cond, src = _case()
    assert any('an ordering of systems' in p for p in aggregate_problems(c.model_copy(update=update), cond, src, entry))


def test_a_metric_the_entry_does_not_carry_is_caught(entry):
    c, cond, src = _case()
    found = aggregate_problems(c.model_copy(update={'metric': 'weatherbench-2-skill-index'}), cond, src, entry)
    assert any('not one of the metrics' in p for p in found)


def test_a_value_pooled_over_variables_is_caught(entry):
    """GraphCast's two claims, T850 at 72 h and Z500 at 120 h, averaged into one number."""
    c, cond, src = _case()
    pooled = round(statistics.mean(x.value for x in CLAIMS if x.system == 'graphcast'), 6)
    found = aggregate_problems(c.model_copy(update={'value': pooled}), cond, src, entry)
    assert any('is not the one line' in p for p in found), found


@pytest.mark.parametrize('field, value, reason', [
    ('subset_used', 'region global and tropics', 'no single region'),
    ('subset_used', 'all 34 regions', 'no single region'),
    ('subset_used', None, 'no single region'),
    ('lead_time', '24-240 h', 'no single lead time'),
    ('lead_time', 'mean over 1-10 days', 'no single lead time'),
])
def test_a_pooled_region_or_lead_time_is_caught(field, value, reason, entry):
    c, cond, src = _case()
    assert any(reason in p for p in aggregate_problems(c, cond.model_copy(update={field: value}), src, entry))


def test_a_value_from_no_results_file_is_caught(entry):
    c, cond, src = _case()
    scorecard = src.model_copy(update={'url': 'https://sites.research.google/gr/weatherbench/'})
    assert any("not a results file" in p for p in aggregate_problems(c, cond, scorecard, entry))


# ---- 3. IFS/ENS appears only as a Baseline record ----------------------------------------------------------------

def test_verify_ifs_ens_appears_only_as_a_baseline(baselines):
    assert ifs_problems(CLAIMS, SYSTEMS, SOURCES, baselines) == []
    ifs = [d for d in baselines if '-ifs-' in d['id']]
    assert {d['id'] for d in ifs} == {bid for bid, _ in IFS_BASELINES.values()}
    assert {d['kind'] for d in ifs} == {'operational-system'}
    assert not [s for s in SYSTEMS.values() if is_reference(s)]
    assert all(not IFS.search(c.system) and c.opponent is None for c in CLAIMS)


def _ifs_system(sid='ifs-hres', name='IFS HRES', results='hres'):
    return System.model_validate({'id': sid, 'name': name, 'system_type': 'classical-algorithm',
                                  'availability': 'generally-available',
                                  'external_ids': {'weatherbench2_results': results},
                                  'sources': ['src-weatherbench-2-homepage']})


def test_a_claim_by_ifs_hres_is_caught(baselines):
    hres = _ifs_system()
    c = by_id('claim-97ccdee40ee2')
    as_claim = c.model_copy(update={'system': 'ifs-hres', 'value': 304.354,
                                    'source': 'src-weatherbench-2-results-hres-vs-hres-t0-240x121-2020'})
    found = ifs_problems([as_claim], {**SYSTEMS, 'ifs-hres': hres}, SOURCES, baselines)
    assert 'ifs-hres is a System record of a reference forecast, which is a Baseline' in found
    assert any('its system ifs-hres is a reference forecast' in p for p in found)
    assert any('cites the results file of hres' in p for p in found)


def test_a_pairwise_claim_against_ifs_ens_is_caught(baselines, entry):
    ens = _ifs_system('ifs-ens', 'IFS ENS', 'ens')
    c = by_id('claim-b81ace24efa9')
    versus = c.model_copy(update={'claim_type': 'pairwise', 'opponent': 'ifs-ens'})
    found = ifs_problems([versus], {**SYSTEMS, 'ifs-ens': ens}, SOURCES, baselines)
    assert any('its opponent ifs-ens is a reference forecast' in p for p in found)
    assert aggregate_problems(versus, conditions(c.eval_conditions), SOURCES[c.source], entry)


def test_an_ifs_system_record_by_name_alone_is_caught(baselines):
    found = ifs_problems(CLAIMS, {**SYSTEMS, 'ecmwf-ifs': _ifs_system('ecmwf-ifs', 'ECMWF IFS', None)}, SOURCES,
                         baselines)
    assert found == ['ecmwf-ifs is a System record of a reference forecast, which is a Baseline']
    aifs = _ifs_system('aifs', 'AIFS', 'aifs')                    # ECMWF's learned model may compete
    assert ifs_problems(CLAIMS, {**SYSTEMS, 'aifs': aifs}, SOURCES, baselines) == []


def test_a_learned_model_on_the_hres_file_is_caught(baselines):
    c = by_id('claim-97ccdee40ee2')
    moved = c.model_copy(update={'source': 'src-weatherbench-2-results-hres-vs-hres-t0-240x121-2020'})
    assert any('cites the results file of hres' in p for p in ifs_problems([moved], SYSTEMS, SOURCES, baselines))


def test_the_ifs_baseline_dropped_or_stored_as_a_floor_is_caught(baselines):
    dropped = [d for d in baselines if not d['id'].endswith('-ifs-ens')]
    assert ifs_problems(CLAIMS, SYSTEMS, SOURCES, dropped) == \
        ['weatherbench-2-crps: no IFS Baseline base-weatherbench-2-2020-z500-crps-ifs-ens']
    floor = copy.deepcopy(baselines)
    hres = next(d for d in floor if d['id'].endswith('-ifs-hres'))
    hres.update(kind='classical-algorithm', is_primary=False)
    assert ifs_problems(CLAIMS, SYSTEMS, SOURCES, floor) == [
        'base-weatherbench-2-2020-z500-rmse-ifs-hres is not the operational-system primary of weatherbench-2-rmse '
        'with a value']


# ---- 4. comparability and conflicts ------------------------------------------------------------------------------

def key(claim, entry_):
    return comp.compute_for_claim(claim, comp.resolve_profile(entry_), conditions(claim.eval_conditions))


def test_the_t850_pair_shares_a_key_and_the_rest_do_not(entry):
    keys = {c.id: key(c, entry).comparability_key for c in CLAIMS}
    g, p, n, f = SECOND                                       # GraphCast, Pangu-Weather, NeuralGCM ENS, FuXi
    assert keys[g] == keys[p]
    assert len({keys[g], keys[n], keys[f]}) == 3
    assert not {keys[g], keys[n], keys[f]} & {keys[c] for c in FIRST}
    assert len(set(keys.values())) == 6                       # batch 1's three and this batch's three
    for c in CLAIMS:
        assert key(c, entry).condition_completeness == pytest.approx(4 / 7)


def test_no_conflict_group_among_the_eight():
    assert max(collections.Counter((c.benchmark, c.subset, c.metric, c.system) for c in CLAIMS).values()) == 1
    assert conflicts.find(CLAIMS, {c.eval_conditions: conditions(c.eval_conditions) for c in CLAIMS}) == []
    assert not [r for r in conflicts.build(ROOT)['rows'] if r['benchmark'].partition('@')[0] == BENCH]
