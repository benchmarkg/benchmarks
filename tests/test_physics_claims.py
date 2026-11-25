"""The physics claims on The Well, PDEBench and the FAIR Universe HiggsML Uncertainty Challenge (P3-S7-T07;
04-data-model.md S7 and S8, 12-analytics-and-trends.md S3.2).

The verify: "bench validate --tier all; bench report completeness shows six physics claims at >= 0.6". The done-when:
"Six physics claims exist, none of which is stored as if it were an accuracy." That is held here as:

  1. Six claims on coverage or PDE error-norm metrics, across the three benchmarks: two on The Well's VRMSE, three on
     PDEBench's nRMSE and RMSE, one on the challenge's interval coverage. The challenge's results page names only one
     finalist by something other than its members' names, so it gives one coverage. The coverage metric may never be
     shown without the interval width (its must_report_with), so a seventh claim, that width from the same evaluation,
     shares the coverage's result_group; it is the coverage's partner, not one of the six. No two claims form a
     (benchmark, system, metric) group, and nothing else is in the three shards.
  2. Never an accuracy. Each claim's metric ref resolves to a Metric whose optimum is recorded and is zero (an error
     norm or the width) or a target (the coverage), never max, so higher_is_better is never True; the metric refuses
     headroom (12 S3.4), so no surface reads the value as a score climbing to 1; the value lies in the metric's range.
  3. The optimum direction is the metric's. Each claim's notes quote the direction its source states, as
     `Direction (<source id>): "<quote>"`; the quote is in that Source's extract, and the direction it states
     (lower is better, the smaller the better, low errors, or the closer to 68.27% the better) is the metric's optimum.
  4. The value is the printed cell, not a complement or a percentage. The notes quote the table's header
     (`under "..."`) and the row (`the row "..."`); both are in the claim's Source's extract, the row follows the header
     inside one window, and the cell in the system's column, for the claim's metric, equals the value.
  5. The verify's count: bench report completeness gives each of the seven claims a condition_completeness of at
     least 0.6 (every material field is answered), and no system is LLM-run (tools/report/llm_run.py).
  6. The failure cases: an accuracy metric, a metric whose optimum is flipped to max, a value stored as its complement
     or as a percentage, a direction quote that is not in the extract or disagrees with the metric, a row read from
     the wrong column, and a coverage shown without its width.

Ids are content-derived (05 S2), as the files' headers say, and are recomputed here.
"""
import collections
import glob
import hashlib
import json
import math
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, fold, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness, llm_run  # noqa: E402

BENCHES = ('the-well', 'pdebench', 'fair-universe-higgsml')
ERROR_NORMS = ('the-well-vrmse', 'pdebench-rmse', 'pdebench-nrmse')
COVERAGE, WIDTH = 'fair-universe-higgsml-coverage', 'fair-universe-higgsml-interval-width'
NEW_SOURCES = ('src-arxiv-2412-00568-v3-html', 'src-arxiv-2210-07182-v7-html')

HEADER = re.compile(r'under "([^"]+)"')
ROW = re.compile(r'the row "([^"]+)"')
DIRECTION = re.compile(r'Direction \((src-[a-z0-9-]+)\): "([^"]+)"')
# The direction a source states, and the optima it allows. "low errors" is PDEBench's: its tables print no direction,
# and the text ties the best prediction to the lowest errors.
DIRECTIONS = {'lower is better': {'zero', 'min'}, 'the smaller the better': {'zero', 'min'},
              'leading to low errors': {'zero', 'min'},
              'the closer to the standard 68.27% probability the better': {'target'}}
# A PDEBench cell, printed twice by arXiv's HTML: rendered (2.9×10−2) and as LaTeX (2.9\times 10^{-2}).
SCI = re.compile(r'(\d+(?:\.\d+)?)×10([−+])(\d+?)\1\\times 10\^\{([-+])(\d+)\}')
PDE_LABEL = {'pdebench-nrmse': 'nRMSE ', 'pdebench-rmse': ' RMSE '}
FAIR_COLUMN = {COVERAGE: 'Avg Coverage', WIDTH: 'Avg Interval'}


def load(kind, ident, model):
    return model.model_validate(read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml')))


def claims(benches=BENCHES):
    return [ResultClaim.model_validate(read_yaml(p)) for b in benches
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', b, '*.yaml')))]


CLAIMS = claims()
CORPUS = [ResultClaim.model_validate(read_yaml(p))
          for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True))]
METRICS = {m: load('metrics', m, Metric) for m in ERROR_NORMS + (COVERAGE, WIDTH)}
EXTRACTS = {}


def extract(sid):
    if sid not in EXTRACTS:
        EXTRACTS[sid] = load(os.path.join('sources', '2026'), sid, Source).quote_extract
    return EXTRACTS[sid]


def column(claim):
    """The table column a claim's system is printed under: its name before the bracket (`FNO (PDEBench baseline)`)."""
    return load('systems', claim.system.split('@')[0], System).name.split(' (')[0]


# ---- the rule --------------------------------------------------------------------------------------------

def cell(claim, header, row):
    """The number the quoted row prints in the claim's system's column, for the claim's metric."""
    bench = claim.benchmark.split('@')[0]
    if bench == 'the-well':                                 # "Dataset Model FNO TFNO U-net CNextU-net"
        labels = header.split()[2:]
        return float(row.split()[1:][labels.index(column(claim))])
    if bench == 'pdebench':                                 # "... Metric U-Net FNO PINN", then a metric's three cells
        labels = header.split('Metric ', 1)[1].split()[:3]
        cells = list(SCI.finditer(row.split(PDE_LABEL[claim.metric], 1)[1]))[:3]
        m = cells[labels.index(column(claim))]
        assert m.group(3) == m.group(5) and (m.group(2) == '−') == (m.group(4) == '-'), m.group(0)
        return float(m.group(1)) * 10 ** (-int(m.group(3)) if m.group(2) == '−' else int(m.group(3)))
    words = row.split()                                     # "... Team Avg Coverage Avg Interval Avg Quantile Score"
    assert words[-4] == column(claim), row
    return float(words[-3:][['Avg Coverage', 'Avg Interval', 'Avg Quantile Score'].index(FAIR_COLUMN[claim.metric])])


def one_window(header, row, text):
    """True when the row follows the header in the extract with no window break or caption between them."""
    f, h, r = fold(text), fold(header), fold(row)
    i = f.find(h)
    j = f.find(r, i + len(h)) if i >= 0 else -1
    between = f[i + len(h):j] if j >= 0 else ''
    return j >= 0 and '…' not in between and 'table ' not in between


def problems(claim, metrics=METRICS):
    """Why `claim` is, or could be read as, an accuracy, or does not hold the number and direction its source prints."""
    out, m = [], metrics.get(claim.metric)
    if m is None:
        return ['%s: %s is not a coverage or error-norm metric' % (claim.id, claim.metric)]
    if m.optimum == 'max' or m.higher_is_better:
        out.append('%s: %s is higher-is-better (optimum %s), the shape of an accuracy' % (claim.id, m.id, m.optimum))
    if m.headroom_null_reason() is None:
        out.append('%s: %s would be given a headroom, as an accuracy is' % (claim.id, m.id))
    if claim.value is None or (m.range and ((m.range.min is not None and claim.value < m.range.min)
                                            or (m.range.max is not None and claim.value > m.range.max))):
        out.append('%s: value %s is outside %s\'s range' % (claim.id, claim.value, m.id))
    notes = claim.notes or ''
    d = DIRECTION.search(notes)
    if not d:
        out.append('%s: the notes quote no direction' % claim.id)
    elif not quote_found(d.group(2), extract(d.group(1))):
        out.append('%s: the direction is not in %s' % (claim.id, d.group(1)))
    else:
        phrase = next((p for p in DIRECTIONS if p in d.group(2)), None)
        if phrase is None or m.optimum not in DIRECTIONS[phrase]:
            out.append('%s: the source says "%s", and %s\'s optimum is %s' % (claim.id, d.group(2), m.id, m.optimum))
        elif m.optimum == 'target' and not math.isclose(m.optimum_target * 100, float(re.search(
                r'(\d+\.\d+)%', phrase).group(1))):
            out.append('%s: the source\'s target is not %s\'s %s' % (claim.id, m.id, m.optimum_target))
    h, r = HEADER.search(notes), ROW.search(notes)
    if not (h and r):
        return out + ['%s: the notes quote no table header and row' % claim.id]
    text = extract(claim.source)
    header, row = h.group(1), r.group(1)
    if not (quote_found(header, text) and quote_found(row, text) and one_window(header, row, text)):
        return out + ['%s: the header and row are not one window of %s' % (claim.id, claim.source)]
    printed = cell(claim, header, row)
    if not math.isclose(printed, claim.value, rel_tol=1e-9):
        out.append('%s: value %s is not the printed cell, %s' % (claim.id, claim.value, printed))
    return out


def render_problems(shown, corpus, metrics=METRICS):
    """04 S6-S7: a claim whose metric must be reported with another names a result_group holding a claim on each such
    metric, and is shown only beside the rest of its group."""
    out, ids = [], {c.id for c in shown}
    for c in shown:
        partners = metrics[c.metric].must_report_with if c.metric in metrics else []
        if c.result_group is None:
            out += ['%s: %s must be reported with %s, and the claim names no result_group' % (c.id, c.metric, p)
                    for p in partners]
            continue
        members = [x for x in corpus if x.result_group == c.result_group]
        out += ['%s: its result_group holds no %s claim' % (c.id, p) for p in partners
                if not any(x.metric == p for x in members)]
        missing = sorted(x.id for x in members if x.id not in ids)
        if missing:
            out.append('%s is shown without %s, the rest of its result_group' % (c.id, ', '.join(missing)))
    return out


def by_metric(metric):
    return next(c for c in CLAIMS if c.metric == metric)


# ---- 1. six coverage and error-norm claims, and the coverage's partner ----------------------------------------

def test_six_coverage_or_error_norm_claims_across_the_three_benchmarks():
    assert collections.Counter((c.benchmark.split('@')[0], c.metric) for c in CLAIMS) == {
        ('the-well', 'the-well-vrmse'): 2, ('pdebench', 'pdebench-nrmse'): 2, ('pdebench', 'pdebench-rmse'): 1,
        ('fair-universe-higgsml', COVERAGE): 1, ('fair-universe-higgsml', WIDTH): 1}
    six = [c for c in CLAIMS if c.metric in ERROR_NORMS + (COVERAGE,)]
    assert len(six) == 6 and {c.benchmark.split('@')[0] for c in six} == set(BENCHES)


def test_the_seventh_is_the_width_bound_to_the_coverage():
    cov, wid = by_metric(COVERAGE), by_metric(WIDTH)
    assert METRICS[COVERAGE].must_report_with == [WIDTH] and METRICS[WIDTH].must_report_with == [COVERAGE]
    assert cov.result_group and cov.result_group == wid.result_group
    for field in ('system', 'benchmark', 'subset', 'source', 'date_reported', 'eval_conditions'):
        assert getattr(cov, field) == getattr(wid, field), field          # one evaluation's two numbers
    assert sorted(c.id for c in CORPUS if c.result_group == cov.result_group) == sorted([cov.id, wid.id])


def test_no_two_claims_form_a_benchmark_system_metric_group():
    keys = [(c.benchmark.split('@')[0], c.system, c.metric) for c in CORPUS]
    assert all(keys.count((c.benchmark.split('@')[0], c.system, c.metric)) == 1 for c in CLAIMS)


# ---- 2-4. never an accuracy; the direction is the metric's; the value is the printed cell --------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.system, c.metric))
def test_the_claim_is_never_stored_as_an_accuracy(claim):
    assert problems(claim) == []


@pytest.mark.parametrize('metric', sorted(METRICS))
def test_each_metric_ref_records_its_optimum(metric):
    m = METRICS[metric]
    assert m.higher_is_better is not True and m.headroom_computable is False
    if metric == COVERAGE:
        assert (m.optimum, m.optimum_target, m.range.min, m.range.max) == ('target', 0.6827, 0, 1)
        assert m.headroom_null_reason() == 'metric-not-headroom-computable'
    else:                                       # an error norm, or the width: zero is exact, and nothing bounds it
        assert (m.optimum, m.range.min, m.range.max) == ('zero', 0, None)
        assert m.headroom_null_reason() == 'lower-is-better-optimum-zero'


def test_the_well_claims_name_their_horizon():
    for c in (c for c in CLAIMS if c.benchmark == 'the-well'):
        cond = load('conditions', c.eval_conditions, EvalConditions)
        assert 'one-step' in cond.subset_used and cond.lead_time    # a rollout window must not share the key


# ---- 5. the verify's count -----------------------------------------------------------------------------------

def test_verify_every_claim_is_at_completeness_0_6_or_more():
    rows = [r for r in completeness.build(ROOT)['rows'] if r['benchmark'].split('@')[0] in BENCHES]
    assert sorted(r['claim'] for r in rows) == sorted(c.id for c in CLAIMS)
    low = [(r['claim'], r['condition_completeness']) for r in rows if r['condition_completeness'] < 0.6]
    assert low == []
    assert sum(1 for r in rows if r['metric'] != WIDTH) == 6


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.system, c.metric))
def test_no_claim_is_llm_run(claim):
    assert llm_run.llm_run(claim.system) is False


# ---- 6. the failure cases ------------------------------------------------------------------------------------

def test_an_accuracy_metric_is_refused():
    accuracy = load('metrics', 'critpt-challenge-accuracy', Metric)
    claim = by_metric('the-well-vrmse').model_copy(update={'metric': accuracy.id})
    assert problems(claim) == ['%s: critpt-challenge-accuracy is not a coverage or error-norm metric' % claim.id]
    got = problems(claim, dict(METRICS, **{accuracy.id: accuracy}))
    assert '%s: critpt-challenge-accuracy is higher-is-better (optimum max), the shape of an accuracy' % claim.id in got
    assert any('and critpt-challenge-accuracy\'s optimum is max' in p for p in got)


@pytest.mark.parametrize('metric', ['the-well-vrmse', 'pdebench-nrmse', COVERAGE])
def test_a_metric_whose_optimum_is_flipped_to_max_is_refused(metric):
    claim = by_metric(metric)
    flipped = METRICS[metric].model_copy(update={'optimum': 'max', 'optimum_target': None})
    got = problems(claim, dict(METRICS, **{metric: flipped}))
    assert got[0] == '%s: %s is higher-is-better (optimum max), the shape of an accuracy' % (claim.id, metric)
    assert any(p.endswith('optimum is max') for p in got)


@pytest.mark.parametrize('metric', ['the-well-vrmse', 'pdebench-rmse', COVERAGE])
def test_a_complement_or_a_percentage_is_not_the_printed_cell(metric):
    claim = by_metric(metric)
    for wrong in (round(1 - claim.value, 6), round(claim.value * 100, 6)):
        got = problems(claim.model_copy(update={'value': wrong}))
        assert any(p.startswith('%s: value %s is not the printed cell' % (claim.id, wrong)) for p in got), got


def test_a_cell_from_another_column_is_caught():
    claim = next(c for c in CLAIMS if c.system == 'pdebench-u-net')
    fno = claim.model_copy(update={'system': 'pdebench-fno'})               # same row, FNO's column: 1.7e-3, not 0.15
    assert problems(fno) == ['%s: value 0.15 is not the printed cell, %s' % (claim.id, 1.7 * 10 ** -3)]


def test_a_direction_that_disagrees_or_is_unquoted_is_caught():
    claim = by_metric('the-well-vrmse')
    target = claim.notes.replace('(lower is better)', '(the closer to the standard 68.27% probability the better)')
    assert problems(claim.model_copy(update={'notes': target})) == \
        ['%s: the direction is not in src-arxiv-2412-00568-v3-html' % claim.id]
    cov = by_metric(COVERAGE)
    lower = cov.notes.replace('the closer to the standard 68.27% probability the better',
                              'Average Interval Width w (the smaller the better)')
    assert problems(cov.model_copy(update={'notes': lower})) == \
        ['%s: the source says "Average Interval Width w (the smaller the better)", and %s\'s optimum is target'
         % (cov.id, COVERAGE)]
    assert problems(claim.model_copy(update={'notes': DIRECTION.sub('', claim.notes)})) == \
        ['%s: the notes quote no direction' % claim.id]


def test_the_coverage_is_never_shown_without_its_width():
    cov, wid = by_metric(COVERAGE), by_metric(WIDTH)
    assert render_problems(CLAIMS, CORPUS) == []
    assert render_problems([cov], CORPUS) == ['%s is shown without %s, the rest of its result_group' % (cov.id, wid.id)]
    assert render_problems([cov.model_copy(update={'result_group': None})], CORPUS) == \
        ['%s: %s must be reported with %s, and the claim names no result_group' % (cov.id, COVERAGE, WIDTH)]
    alone = [c for c in CORPUS if c.id != wid.id]
    assert render_problems([cov], alone) == ['%s: its result_group holds no %s claim' % (cov.id, WIDTH)]


# ---- the records' identity and provenance -----------------------------------------------------------------------

def _content_id(prefix, payload):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(payload, separators=(',', ':'), sort_keys=prefix == 'cond')
                                             .encode('utf-8')).hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_ids_are_content_derived(claim):
    assert claim.id == _content_id('claim', [claim.benchmark, claim.system, claim.metric, claim.subset, claim.value,
                                             claim.source, claim.date_reported.isoformat()])
    raw = read_yaml(os.path.join(ROOT, 'data', 'conditions', claim.eval_conditions + '.yaml'))
    assert claim.eval_conditions == _content_id('cond', comp.canonicalise({k: v for k, v in raw.items() if k != 'id'}))


def test_every_source_is_archived_or_a_doi_and_the_new_ones_hold_no_contact_line():
    cited = {c.source for c in CLAIMS} | {DIRECTION.search(c.notes).group(1) for c in CLAIMS}
    for sid in sorted(cited):
        s = load(os.path.join('sources', '2026'), sid, Source)
        if s.doi:
            assert s.archive_status == 'not-required', sid
        elif s.contains_personal_data:
            assert s.archive_status == 'withheld' and s.failure_reason, sid
        else:
            assert s.archive_status in ('ok', 'pending'), sid
    for sid in NEW_SOURCES:
        s = load(os.path.join('sources', '2026'), sid, Source)
        # the body has a byline (and PDEBench's, its authors' addresses): marked, and kept out of every window
        assert s.doi and s.archive_status == 'not-required' and s.contains_personal_data is True
        assert '@' not in s.quote_extract and '[view email]' not in s.quote_extract
