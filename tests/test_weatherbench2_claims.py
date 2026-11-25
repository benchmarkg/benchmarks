"""WeatherBench 2's first claims: four cells of the 2020 grid, each at one lead time (P3-S7-T05; 04-data-model.md S7
and S8, 12-analytics-and-trends.md S3.4).

The verify: "bench validate --tier all, plus a test asserting every claim carries a non-null lead_time and that no
claim aggregates across lead times". The done-when: "Four claims exist, each pinned to one point of the grid rather
than to a summary." That is held here as:

  1. Four claims in data/claims/weatherbench-2/, on the 2020 version (the paper's protocol, and the year the anchors
     in data/baselines/weatherbench-2.yaml are stated at), each on a headline subset and a headline Metric of the
     entry, from a results file of the maintainers' bucket, by four systems that are learned models. No anchor is a
     claim: the IFS forecasts, ERA5's own forecasts, climatology and persistence stay Baselines (P3-S7-T06 asserts
     the IFS half again for its batch).
  2. Every claim carries a non-null lead_time, in its own condition record, and it is one lead time: a whole number
     of hours in the results files' spelling ("120 h"), never a range, a list, a mean or the reference conditions'
     description of the grid.
  3. No claim aggregates across lead times. Each claim is one point of the grid: the (metric, variable, level, region,
     lead time) its fields name -- metric; subset for the variable and its level; subset_used for the region;
     lead_time -- is exactly one line of its Source's extract, the line's value is the claim's value, and its notes
     quote that line and the file's header. A value that is the mean of the row, or the row's value at another lead
     time, is not that line, and is caught. So is every "VALUE at N h" its notes cite from the same row.
  4. The grid's other coordinates the schema cannot hold -- ground truth, evaluation resolution, evaluation year --
     are read off the file name, and must agree with the claim: the year is the benchmark version, and the four sit
     at the anchors' resolution (240x121) against ERA5, the ground truth of every learned model on the site.
  5. Comparability: two claims at one cell share a comparability key (GraphCast and Pangu-Weather), one at another
     lead time does not (FuXi at 240 h), and without lead_time in their conditions the two lead times would collide.
  6. The selection forms no new (benchmark, subset, metric, system) group of two or more, so `bench report conflicts`
     gains no row and tests/report/test_reports.py's pin is untouched.

Ids are content-derived (05 S2), as the files' headers say, and are recomputed here.
"""
import collections
import glob
import hashlib
import json
import os
import re
import statistics
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import Organization  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import conflicts  # noqa: E402
from tools.report.llm_run import llm_run  # noqa: E402

BENCH = 'weatherbench-2'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'earth-climate', BENCH + '.yaml')
SHARD = os.path.join(ROOT, 'data', 'claims', BENCH)
# Each headline subset's variable as the results files name it, and its pressure level (None at the surface). The
# 850 hPa wind is two quantities: the deterministic headline is the wind-vector RMSE, the probabilistic one the
# wind-speed CRPS (the entry's subset notes).
VARIABLE = {'z500': ('geopotential', 500), 't850': ('temperature', 850), 'q700': ('specific_humidity', 700),
            'wv-ws850': ('wind_speed', 850), 't2m': ('2m_temperature', None), 'ws10': ('10m_wind_speed', None),
            'mslp': ('mean_sea_level_pressure', None), 'tp24hr': ('total_precipitation_24hr', None)}
PREFIX = {'weatherbench-2-rmse': 'rmse', 'weatherbench-2-crps': 'crps', 'weatherbench-2-seeps': 'seeps'}
RESULTS = re.compile(r'^https://storage\.googleapis\.com/weatherbench2/benchmark_results/'
                     r'(?P<forecast>[a-z0-9_]+)_vs_(?P<truth>era5|hres_t0)_(?P<grid>\d+x\d+)_(?P<year>\d{4})\.nc$')
LEAD = re.compile(r'^(\d+) h$')
REGION = re.compile(r'^region ([a-z0-9-]+)$')
# The forecasts the site scores as references, which are Baselines here and never claims (12 S3.2).
ANCHORS = {'hres', 'ens', 'ens_mean', 'ens_single_member', 'era5_forecast', 'climatology',
           'probabilistic_climatology', 'persistence'}
NEIGHBOUR = re.compile(r'(\d+(?:\.\d+)?(?:e[-+]?\d+)?) at (\d+) h\b')


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def source(sid):
    return Source.model_validate(load(os.path.join('sources', '2026'), sid))


def system(ref):
    return System.model_validate(load('systems', ref.split('@')[0]))


def conditions(cid):
    return EvalConditions.model_validate(load('conditions', cid)) if cid else None


def raw_claims():
    """(repo-relative path, raw mapping) for every claim under data/claims/ on weatherbench-2, wherever it lives."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict) and str(raw.get('benchmark', '')).partition('@')[0] == BENCH:
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), raw))
    return out


CLAIMS = [ResultClaim.model_validate(raw) for _, raw in raw_claims()]


@pytest.fixture(scope='module')
def entry():
    return load_benchmark(ENTRY)


def by_system(sid):
    return next(c for c in CLAIMS if c.system == sid)


# ---- the rule, as functions the corpus tests and the failure cases share ----------------------------------------

def lead_hours(cond):
    """The claim's one lead time in hours, or None when it states none, or not one."""
    m = LEAD.match(cond.lead_time) if cond is not None and cond.lead_time is not None else None
    return int(m.group(1)) if m else None


def cell(claim, cond):
    """The results-file line, up to its value, that the claim's fields name; None when they do not name one."""
    slug = (claim.subset or '').partition('#')[2]
    variable, level = VARIABLE.get(slug, (None, None))
    if slug == 'wv-ws850' and claim.metric == 'weatherbench-2-rmse':
        prefix = 'vector_rmse.wind'
    else:
        prefix = '%s.%s' % (PREFIX.get(claim.metric), variable)
    region = REGION.match(cond.subset_used or '') if cond is not None else None
    hours = lead_hours(cond)
    if variable is None or claim.metric not in PREFIX or region is None or hours is None:
        return None
    at = ', level %d' % level if level is not None else ''
    return '%s, region %s%s, lead_time %d h: ' % (prefix, region.group(1), at, hours)


def line_value(extract, head):
    """The value of the one complete line `head` begins in the extract, or None (absent, cut by a window, repeated)."""
    found = re.findall(r'(?:^|\s)%s(\S+);' % re.escape(head), extract)
    return float(found[0]) if len(found) == 1 and found[0] != 'nan' else None


def header(src):
    m = re.match(r'file \S+\.nc; region \d+, lead_time \d+ \(hours\), level \d+', src.quote_extract or '')
    return m.group(0) if m else None


def results_file(src):
    m = RESULTS.match(src.url or '')
    return m.groupdict() if m else None


def lead_problems(claim, cond, entry_):
    """Why a claim does not carry one non-null lead_time; empty when it does."""
    out = []
    if cond is None:
        out.append('%s has no condition record, so no lead_time' % claim.id)
        return out
    if cond.lead_time is None:
        out.append('%s: lead_time is null' % claim.id)
    elif lead_hours(cond) is None:
        out.append('%s: lead_time %r is not one lead time in hours' % (claim.id, cond.lead_time))
    if cond.id == entry_.reference_conditions:
        out.append('%s: the reference conditions state the grid, not a point on it' % claim.id)
    return out


def cell_problems(claim, cond, src, sys_=None):
    """Why a claim is not exactly one point of the grid in its results file; empty when it is."""
    out = []
    head = cell(claim, cond)
    if head is None:
        return ['%s: its fields name no single cell (metric, variable, level, region, lead time)' % claim.id]
    extract = src.quote_extract or ''
    value = line_value(extract, head)
    if value is None:
        out.append('%s: no single line %r in %s' % (claim.id, head, src.id))
    elif value != claim.value:
        out.append('%s: the value %r is not the line %r%r' % (claim.id, claim.value, head, value))
    line = '%s%s;' % (head, '%g' % claim.value if claim.value is not None else '')
    if line not in (claim.notes or ''):
        out.append('%s: the notes do not quote the line %r' % (claim.id, line))
    top = header(src)
    if top is None or top not in (claim.notes or ''):
        out.append('%s: the notes do not quote the file header of %s' % (claim.id, src.id))
    for v, hours in NEIGHBOUR.findall(claim.notes or ''):
        other = head.replace('lead_time %d h: ' % lead_hours(cond), 'lead_time %s h: ' % hours)
        if line_value(extract, other) != float(v):
            out.append('%s: the notes cite %s at %s h, which is not the line %r' % (claim.id, v, hours, other))
    f = results_file(src)
    if f is None:
        out.append('%s: %s is not a results file of the bucket' % (claim.id, src.id))
    else:
        if f['year'] != claim.benchmark.partition('@')[2]:
            out.append('%s: the file is for %s, the claim on %s' % (claim.id, f['year'], claim.benchmark))
        if f['forecast'] in ANCHORS:
            out.append('%s: %s is an anchor, which is a Baseline, not a claim' % (claim.id, f['forecast']))
        s = sys_ or system(claim.system)
        if s.external_ids.get('weatherbench2_results') != f['forecast']:
            out.append('%s: the file scores %s, not %s' % (claim.id, f['forecast'], claim.system))
    return out


# ---- 1. four claims ------------------------------------------------------------------------------------------

def test_four_claims_in_the_shard(entry):
    paths = [rel for rel, _ in raw_claims()]
    assert len(CLAIMS) == 4
    assert all(rel.startswith('data/claims/weatherbench-2/') for rel in paths), paths
    subsets, metrics = {s.id for s in entry.subsets}, set(entry.metrics)
    for c in CLAIMS:
        assert c.benchmark == BENCH + '@2020' and c.claim_type == 'absolute'
        assert c.subset in subsets and c.metric in metrics
        assert c.uncertainty is None and c.value_text is None
    assert len({c.system for c in CLAIMS}) == 4


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_every_system_is_a_learned_model_and_no_anchor_is_a_claim(claim):
    s = system(claim.system)
    assert s.system_type == 'scientific-surrogate-model'
    assert llm_run(claim.system) is False
    assert results_file(source(claim.source))['forecast'] not in ANCHORS
    assert not re.search(r'\bifs\b|climatology|persistence', claim.system)


def test_the_reporter_is_the_maintainer():
    org = Organization.model_validate(load('organizations', 'org-google-research'))
    assert {c.reported_by for c in CLAIMS} == {org.id} and 'benchmark-maintainer' in org.roles
    assert {c.verification for c in CLAIMS} == {'maintainer-verified'}


# ---- 2. every claim carries a non-null lead_time ------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_verify_every_claim_carries_a_non_null_lead_time(claim, entry):
    cond = conditions(claim.eval_conditions)
    assert cond is not None and cond.lead_time is not None
    assert lead_problems(claim, cond, entry) == []
    assert 'lead_time' in comp.resolve_profile(entry).material


def test_a_claim_without_a_lead_time_is_caught(entry):
    c = by_system('graphcast')
    cond = conditions(c.eval_conditions)
    assert any('no condition record' in p for p in lead_problems(c.model_copy(update={'eval_conditions': None}),
                                                                 None, entry))
    assert any('lead_time is null' in p for p in lead_problems(c, cond.model_copy(update={'lead_time': None}), entry))


@pytest.mark.parametrize('spelling', ['24-240 h', '120 h, 240 h', 'mean over 1-10 days', '5 days', 'all lead times'])
def test_a_range_a_list_or_a_summary_is_not_a_lead_time(spelling, entry):
    c = by_system('graphcast')
    cond = conditions(c.eval_conditions).model_copy(update={'lead_time': spelling})
    assert any('not one lead time' in p for p in lead_problems(c, cond, entry))
    assert any('no single cell' in p for p in cell_problems(c, cond, source(c.source)))


def test_the_reference_conditions_are_not_a_point_on_the_grid(entry):
    c = by_system('graphcast')
    ref = conditions(entry.reference_conditions)
    found = lead_problems(c.model_copy(update={'eval_conditions': ref.id}), ref, entry)
    assert any('not one lead time' in p for p in found) and any('state the grid' in p for p in found)


# ---- 3. no claim aggregates across lead times -------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_verify_no_claim_aggregates_across_lead_times(claim):
    cond = conditions(claim.eval_conditions)
    src = source(claim.source)
    assert cell_problems(claim, cond, src) == []
    head = cell(claim, cond)
    assert quote_found('%s%g;' % (head, claim.value), src.quote_extract)
    assert len(NEIGHBOUR.findall(claim.notes)) >= 2            # the row it is one point of, at other lead times


def test_the_mean_of_the_row_is_caught():
    c = by_system('graphcast')
    cond, src = conditions(c.eval_conditions), source(c.source)
    row = [float(v) for v, _ in NEIGHBOUR.findall(c.notes)] + [c.value]
    mean = round(statistics.mean(row), 3)
    found = cell_problems(c.model_copy(update={'value': mean}), cond, src)
    assert any('is not the line' in p for p in found), found


def test_the_value_at_another_lead_time_is_caught():
    c = by_system('graphcast')
    cond, src = conditions(c.eval_conditions), source(c.source)
    at_240 = line_value(src.quote_extract, cell(c, cond).replace('120 h', '240 h'))
    assert at_240 is not None and at_240 != c.value
    assert any('is not the line' in p for p in cell_problems(c.model_copy(update={'value': at_240}), cond, src))
    shifted = cond.model_copy(update={'lead_time': '240 h'})                  # the right number, the wrong lead time
    assert any('is not the line' in p for p in cell_problems(c, shifted, src))


def test_a_cell_the_fields_do_not_name_is_caught():
    c = by_system('neuralgcm-ens')
    cond, src = conditions(c.eval_conditions), source(c.source)
    assert any('no single line' in p for p in cell_problems(c.model_copy(update={'metric': 'weatherbench-2-rmse'}),
                                                            cond, src))
    assert any('no single line' in p for p in cell_problems(c.model_copy(update={'subset': BENCH + '#t850'}),
                                                            cond, src))
    europe = cond.model_copy(update={'subset_used': 'region europe'})
    assert any('no single line' in p for p in cell_problems(c, europe, src))
    assert any('no single cell' in p for p in cell_problems(c, cond.model_copy(update={'subset_used': 'full'}), src))


# ---- 4. the coordinates the schema cannot hold -------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_ground_truth_resolution_and_year_are_the_files(claim):
    src = source(claim.source)
    f = results_file(src)
    assert (f['truth'], f['grid'], f['year']) == ('era5', '240x121', '2020')
    for named in ('ERA5', '240x121', '1.5 degrees'):
        assert named in claim.notes
    assert src.type == 'dataset-export' and src.publisher.startswith('Google Research')
    assert src.published.isoformat() == claim.date_reported.isoformat()


def test_a_file_for_another_year_or_an_anchor_is_caught():
    c = by_system('pangu-weather')
    cond, src = conditions(c.eval_conditions), source(c.source)
    assert any('the file is for 2020' in p
               for p in cell_problems(c.model_copy(update={'benchmark': BENCH + '@2022'}), cond, src))
    hres = src.model_copy(update={'url': src.url.replace('pangu_vs_era5', 'hres_vs_era5')})
    found = cell_problems(c, cond, hres)
    assert any('is an anchor' in p for p in found) and any('not pangu-weather' in p for p in found)


# ---- 5. comparability ---------------------------------------------------------------------------------------------

def key(claim, entry_, cond=None):
    r = comp.resolve_profile(entry_)
    return comp.compute_for_claim(claim, r, cond or conditions(claim.eval_conditions))


def test_one_cell_shares_a_key_and_another_lead_time_does_not(entry):
    g, p, f, n = (by_system(s) for s in ('graphcast', 'pangu-weather', 'fuxi', 'neuralgcm-ens'))
    assert key(g, entry).comparability_key == key(p, entry).comparability_key
    assert key(g, entry).comparability_key != key(f, entry).comparability_key
    assert key(g, entry).comparability_key != key(n, entry).comparability_key        # same conditions, another metric
    assert len({key(c, entry).comparability_key for c in CLAIMS}) == 3


def test_without_lead_time_two_lead_times_would_collide(entry):
    g, f = by_system('graphcast'), by_system('fuxi')
    blind = {c.id: conditions(c.eval_conditions).model_copy(update={'lead_time': None}) for c in (g, f)}
    assert key(g, entry, blind[g.id]).comparability_key == key(f, entry, blind[f.id]).comparability_key
    assert lead_hours(conditions(g.eval_conditions)) != lead_hours(conditions(f.eval_conditions))


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_condition_completeness_and_the_unknowns(claim, entry):
    c = key(claim, entry)
    # lead_time, resolution_window, subset_used and training_data_policy are answered; the eligibility-gated
    # profile's three fields are not (the condition records' headers say why).
    assert set(c.unknown_fields) == {'decontamination_applied', 'eligibility_track', 'training_data_eligibility'}
    assert c.condition_completeness == pytest.approx(4 / 7)


# ---- 6. no new conflict group --------------------------------------------------------------------------------------

def test_no_two_claims_share_benchmark_subset_metric_and_system():
    groups = collections.Counter((c.benchmark, c.subset, c.metric, c.system) for c in CLAIMS)
    assert max(groups.values()) == 1
    conds = {c.eval_conditions: conditions(c.eval_conditions) for c in CLAIMS}
    assert conflicts.find(CLAIMS, conds) == []
    report = conflicts.build(ROOT)
    assert not [r for r in report['rows'] if r['benchmark'].partition('@')[0] == BENCH]


def test_one_system_at_two_lead_times_would_form_a_group():
    """The failure case for the selection: GraphCast at 120 h and at 240 h is one (benchmark, subset, metric, system)
    group whose values differ, which `bench report conflicts` reports, explained by lead_time."""
    g = by_system('graphcast')
    src = source(g.source)
    cond = conditions(g.eval_conditions)
    late = cond.model_copy(update={'id': 'cond-0123456789ab', 'lead_time': '240 h'})
    other = g.model_copy(update={'id': 'claim-0123456789ab', 'eval_conditions': late.id,
                                 'value': line_value(src.quote_extract, cell(g, late))})
    rows = conflicts.find([g, other], {cond.id: cond, late.id: late})
    assert len(rows) == 1 and 'eval_conditions.lead_time' in rows[0]['differing_fields']


# ---- the records' identity and provenance ------------------------------------------------------------------------

def _content_id(prefix, d):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8'))
                      .hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_ids_are_content_derived(claim, entry):
    k = {'benchmark': claim.benchmark, 'system': claim.system, 'metric': claim.metric, 'subset': claim.subset,
         'value': claim.value, 'source': claim.source, 'date_reported': claim.date_reported.isoformat()}
    assert claim.id == _content_id('claim', k)
    cond = conditions(claim.eval_conditions)
    material = comp.resolve_profile(entry).material
    assert cond.id == _content_id('cond', {f: comp.canonicalise(cond.value(f)) for f in material})


def test_the_sources():
    for sid in {c.source for c in CLAIMS}:
        s = source(sid)
        # a machine-written file that names no one: archived by the lead, never withheld
        assert s.contains_personal_data is False and s.archive_status in ('pending', 'ok') and s.doi is None
        assert BENCH in s.cited_by and s.licence_class == 'unlicensed'
        assert '@' not in s.quote_extract and 'netcdf' in (s.extract_preprocessing or '').lower()
        assert s.content_bytes and s.quote_extract_mode == 'windows'
