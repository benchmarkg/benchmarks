"""Matbench Discovery claims, batch 1: five compliant leaderboard entries, each one F1 claim with its compliance tier
(P3-S7-T01; 04-data-model.md S7 and S8, 14-roadmap.md Phase 3).

The verify: "bench validate --tier all; bench report completeness shows five claims at >= 0.6 each with
eligibility_track populated". The done-when: "Five entries are curated with all six metrics grouped and their
compliance tier recorded."

The reading taken. The ledger counts five: the title's "(5)", the verify's "five claims", P3-S7's 32 claims
(10 + 8 + 8 + 6 over its four families) and P3-S7-T02's done-when, "Ten claims exist", after a second batch of
five. So a batch is five claims, one per entry, not five entries times their metrics. The step "one claim per
metric bound by result_group" and the done-when's "all six metrics grouped" are not met, for two reasons the
sources and 04 S7 give: result_group binds claims that must never be shown apart, and on this board only CPS must
(its must_report_with names F1, kappa-SRME and RMSD), while the six tasks are subsets scored separately; and no
nameless archived source holds all six for any entry (CMDS and CDS are computed by the live site's code, the
phonon spectrum distance is only in per-model files that name people).

  1. Five entries. Five claims in data/claims/matbench-discovery/, five Systems, one metric (f1-score) on one
     subset (the unique-prototype discovery set), one Source, one date and one conditions record.
  2. The verify. Each claim's condition_completeness, from tools/report/completeness.py (what `bench report
     completeness` prints), is at least 0.6, and its eligibility_track is populated. Failure cases: a record
     without eligibility_track, and one with three of its five material fields unanswered.
  3. The compliance tier. eligibility_track and training_data_eligibility both hold the tier, an id of the entry's
     training_data_eligibility_tiers, and the tier follows from the row's Training Set cell: every dataset in it
     is one the compliant rule admits. eligibility_track is material, so the five share one comparability key and
     a non-compliant claim on the same metric and subset gets another (the property P3-S7-T02 must show).
  4. Every number is the table's. Each claim's notes quote its row of the v1 unique-prototype table; the row is in
     the Source's extract and its first number, F1, is the claim's value. The notes also quote the entry's row on
     the archived 2026-06-10 leaderboard capture, the rolling board, whose third number (after CPS and Acc) is the
     same F1, with the same Training Set and Date Added.
  5. No result_group, and none needed: f1-score names no partner; the rule that would refuse a CPS claim shown
     without its components is checked on a CPS copy (the failure case).
  6. Identity and provenance: content-derived ids, no claim is LLM-run, the Source is nameless and archived,
     and no claim forms a (benchmark, subset, metric, system) group with another.

P3-S7-T02 added five non-compliant claims to the directory (tests/test_matbench_discovery_claims_batch2.py, which
asserts the ten together). Everything here is about this batch's five, by id (FIRST_IDS).
"""
import collections
import glob
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness, conflicts, llm_run  # noqa: E402

BENCH = 'matbench-discovery'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BENCH + '.yaml')
METRIC, SUBSET, CPS = 'f1-score', 'matbench-discovery#unique-prototypes', 'matbench-cps'
SOURCE = 'src-github-matbench-discovery-metrics-table-uniq-protos-6d587c1'
BOARD = 'src-matbench-discovery-homepage'
NATURE = 'src-matbench-discovery-nature'
TABLE_HEADER = ('Model F1 ↑ DAF ↑ Prec ↑ Acc ↑ TPR ↑ TNR ↑ MAE ↓ RMSE ↓ R2 ↑ Training Set Model Params Targets '
                'Date Added')
BOARD_HEADER = 'Model CPS ↑ Acc F1 DAF Prec MAE R2 κSRME RMSD Training Set Params Targets Date Added'
TABLE_ROW = re.compile(r'the table row "([^"]+)"')
BOARD_ROW = re.compile(r'the board row "([^"]+)"')
NUMBER = r'(-?\d+(?:\.\d+)?)'
# The datasets the compliant tier admits, by the names the two Training Set columns use: the entry's compliant rule
# ("Trained on nothing beyond the Materials Project v2022.10.28 release ... (MPtrj, for example)") and the datasets
# its compliant-preset rule lists as flagged compliant (MP v2022.10.28, MPtrj, MPF.2021.2.8, the MP 2019 graphs).
COMPLIANT_SETS = {'MPtrj', 'MPF', 'MP 2022', 'MP Graphs'}
GATE = 0.6
# The table's name for a row where the System takes the board's newer name (data/systems/orb-v2-mptrj.yaml).
TABLE_NAMES = {'orb-v2-mptrj': 'ORB MPtrj'}


def load(kind, ident, model):
    return model.model_validate(read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml')))


def load_claims(pattern):
    return [ResultClaim.model_validate(read_yaml(p))
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', pattern, '*.yaml')))]


# This batch's five (P3-S7-T01); P3-S7-T02's are in tests/test_matbench_discovery_claims_batch2.py.
FIRST_IDS = ('claim-f83949fcbbac', 'claim-33cffc25e71e', 'claim-0104f677651c', 'claim-aa0bfaee5578',
             'claim-06c74c9cd199')
CLAIMS = [c for c in load_claims(BENCH) if c.id in FIRST_IDS]
CORPUS = load_claims('**')
ENTRY_B = load_benchmark(ENTRY)
RESOLUTION = comp.resolve_profile(ENTRY_B)


def source(sid):
    return load(os.path.join('sources', '2026'), sid, Source)


def conditions(claim):
    return load('conditions', claim.eval_conditions, EvalConditions)


# ---- the rules, as functions the corpus tests and the failure cases share -------------------------------------

def table_row(row):
    """(model, F1, training sets, date added) from a row of the v1 table: model, F1, DAF, ..., Training Set, ..."""
    m = re.match(r'^(.+?) ' + NUMBER + ' ', row)
    cell = re.findall(r'\(([A-Za-z][^()]*)\)', row)          # (1.6M) and (N=10) are counts, not the Training Set
    return m.group(1), float(m.group(2)), set(cell[0].split('+')) if cell else set(), row.rsplit(' ', 1)[-1]


def board_row(row):
    """(model, F1, training sets, date added) from a row of the board capture: model, CPS, Acc, F1, ..."""
    m = re.match(r'^(.+?) (?:n/a|%s) %s %s ' % (NUMBER, NUMBER, NUMBER), row)
    sets = re.search(r' \d+(?:\.\d+)?[kM]?(?: \([\d.]+[kM]\))? ([A-Za-z][\w+ ]*?) [\d.]+[kKM]? E', row)
    return m.group(1), float(m.group(4)), set(sets.group(1).split('+')) if sets else set(), row.rsplit(' ', 1)[-1]


def tier_of(training_sets):
    """The compliance tier a Training Set cell puts a model in: compliant only when every dataset is admitted."""
    return 'compliant' if training_sets and training_sets <= COMPLIANT_SETS else 'non-compliant'


def gate_problems(claim, cond):
    """Why a claim fails the verify: completeness under 0.6 or no eligibility_track."""
    out = []
    got = comp.compute_for_claim(claim, RESOLUTION, cond)
    if got.condition_completeness is None or got.condition_completeness < GATE:
        out.append('%s: condition_completeness %s is under %s' % (claim.id, got.condition_completeness, GATE))
    if cond is None or cond.eligibility_track is None:
        out.append('%s: eligibility_track is not populated' % claim.id)
    return out


def render_problems(shown, corpus, metrics):
    """Why a surface may not render the claims `shown` (04 S6, S7): a claim whose metric must be reported with
    another names a result_group that holds every such metric, and is shown beside the rest of its group."""
    out, ids = [], {c.id for c in shown}
    for c in shown:
        partners = metrics[c.metric].must_report_with
        if c.result_group is None:
            if partners:
                out.append('%s: %s must be reported with %s, and the claim names no result_group'
                           % (c.id, c.metric, ', '.join(partners)))
            continue
        members = [x for x in corpus if x.result_group == c.result_group]
        out += ['%s: its result_group holds no %s claim' % (c.id, p) for p in partners
                if not any(x.metric == p for x in members)]
        missing = sorted(x.id for x in members if x.id not in ids)
        if missing:
            out.append('%s is shown without %s, the rest of its result_group' % (c.id, ', '.join(missing)))
    return out


# ---- 1. five entries -------------------------------------------------------------------------------------------

def test_five_entries_five_claims():
    assert len(CLAIMS) == 5
    assert len({c.system for c in CLAIMS}) == 5
    for field in ('benchmark', 'metric', 'subset', 'source', 'date_reported', 'eval_conditions', 'reported_by',
                  'verification', 'claim_type'):
        assert len({str(getattr(c, field)) for c in CLAIMS}) == 1, field
    c = CLAIMS[0]
    assert (c.benchmark, c.metric, c.subset, c.source) == (BENCH, METRIC, SUBSET, SOURCE)
    assert c.subset in {s.id for s in ENTRY_B.subsets} and c.metric in ENTRY_B.metrics
    assert (c.claim_type, c.verification) == ('absolute', 'maintainer-verified')


# ---- 2. the verify -----------------------------------------------------------------------------------------------

def test_the_report_shows_five_claims_at_the_gate_with_eligibility_track():
    rows = [r for r in completeness.build(ROOT)['rows'] if r['benchmark'] == BENCH and r['claim'] in FIRST_IDS]
    assert sorted(r['claim'] for r in rows) == sorted(c.id for c in CLAIMS)
    for r in rows:
        assert r['condition_completeness'] >= GATE, r['claim']
        assert 'eligibility_track' in r['material'] and 'eligibility_track' not in r['unknown_fields'], r['claim']
    for c in CLAIMS:
        assert gate_problems(c, conditions(c)) == []


def test_a_record_without_eligibility_track_or_most_fields_is_refused():
    c = CLAIMS[0]
    cond = conditions(c)
    blank = cond.model_copy(update={'eligibility_track': None})
    assert gate_problems(c, blank) == ['%s: eligibility_track is not populated' % c.id]
    assert comp.compute_for_claim(c, RESOLUTION, blank).condition_completeness == pytest.approx(0.8)
    thin = cond.model_copy(update={'training_data_policy': None, 'decontamination_applied': None,
                                   'subset_used': None})
    assert gate_problems(c, thin) == ['%s: condition_completeness 0.4 is under 0.6' % c.id]
    assert gate_problems(c, None) == ['%s: condition_completeness 0.0 is under 0.6' % c.id,
                                      '%s: eligibility_track is not populated' % c.id]


# ---- 3. the compliance tier -------------------------------------------------------------------------------------

def test_the_tier_is_declared_and_material():
    tiers = {t.id for t in ENTRY_B.training_data_eligibility_tiers}
    assert {'eligibility_track', 'training_data_eligibility'} <= set(RESOLUTION.material)
    for c in CLAIMS:
        cond = conditions(c)
        assert cond.training_data_eligibility in tiers
        assert cond.eligibility_track == cond.training_data_eligibility == 'compliant'


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_the_tier_follows_the_training_set_cell(claim):
    _, _, sets, _ = table_row(TABLE_ROW.search(claim.notes).group(1))
    assert tier_of(sets) == conditions(claim).training_data_eligibility


def test_a_larger_training_set_is_not_compliant():
    extract = source(SOURCE).quote_extract
    row = 'MACE-MPA-0 0.852 5.58 0.853 0.954 0.851 0.973 0.028 0.073 0.842 3M (12.0M) (MPtrj+sAlex) 9.1M EFSG 2024-12-09'
    assert quote_found(row, extract)
    assert tier_of(table_row(row)[2]) == 'non-compliant'
    assert tier_of(set()) == 'non-compliant'                  # an unreadable cell is never compliant


def test_the_five_share_one_key_and_another_tier_does_not():
    built = comp.build(ROOT)['claims']
    keys = {built[c.id]['comparability_key'] for c in CLAIMS}
    assert len(keys) == 1
    c = CLAIMS[0]
    other = conditions(c).model_copy(update={'eligibility_track': 'non-compliant',
                                              'training_data_eligibility': 'non-compliant'})
    assert comp.compute_for_claim(c, RESOLUTION, other).comparability_key not in keys


# ---- 4. every number is the table's, and the board's --------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_the_value_is_the_quoted_table_row(claim):
    extract = source(SOURCE).quote_extract
    assert quote_found(TABLE_HEADER, extract)
    row = TABLE_ROW.search(claim.notes).group(1)
    assert quote_found(row, extract), '%s: the row is not in %s' % (claim.id, SOURCE)
    model, f1, _, _ = table_row(row)
    assert model == TABLE_NAMES.get(claim.system, load('systems', claim.system, System).name)
    assert f1 == claim.value


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_the_rolling_board_shows_the_same_f1(claim):
    extract = source(BOARD).quote_extract
    assert quote_found(BOARD_HEADER, extract)
    row = BOARD_ROW.search(claim.notes).group(1)
    assert quote_found(row, extract), '%s: the row is not in %s' % (claim.id, BOARD)
    model, f1, sets, added = board_row(row)
    assert model == load('systems', claim.system, System).name
    assert f1 == claim.value
    _, _, table_sets, table_added = table_row(TABLE_ROW.search(claim.notes).group(1))
    assert (sets, added) == (table_sets, table_added)          # the same entry: same data, same date added


def test_a_wrong_value_is_caught():
    c = CLAIMS[0]
    assert table_row(TABLE_ROW.search(c.notes).group(1))[1] != c.value + 0.001


# ---- 5. no result_group, and none needed --------------------------------------------------------------------------

def test_f1_renders_alone_and_a_bare_cps_claim_would_not():
    metrics = {m: load('metrics', m, Metric) for m in (METRIC, CPS)}
    assert metrics[METRIC].must_report_with == []
    assert all(c.result_group is None for c in CLAIMS)
    assert render_problems(CLAIMS, CORPUS, metrics) == []
    for c in CLAIMS:
        assert render_problems([c], CORPUS, metrics) == []
    cps = CLAIMS[0].model_copy(update={'metric': CPS})
    assert render_problems([cps], CORPUS, metrics) == [
        '%s: matbench-cps must be reported with f1-score, kappa-srme, structure-rmsd, and the claim names no '
        'result_group' % cps.id]


# ---- 6. identity and provenance ------------------------------------------------------------------------------------

def _content_id(prefix, payload):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(payload, separators=(',', ':'), sort_keys=prefix == 'cond')
                                             .encode('utf-8')).hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_ids_are_content_derived(claim):
    assert claim.id == _content_id('claim', [claim.benchmark, claim.system, claim.metric, claim.subset, claim.value,
                                             claim.source, claim.date_reported.isoformat()])
    raw = read_yaml(os.path.join(ROOT, 'data', 'conditions', claim.eval_conditions + '.yaml'))
    assert claim.eval_conditions == _content_id('cond', comp.canonicalise({k: v for k, v in raw.items() if k != 'id'}))


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_no_claim_is_llm_run(claim):
    assert llm_run.llm_run(claim.system) is False
    assert load('systems', claim.system, System).system_type == 'scientific-surrogate-model'


def test_the_source_is_nameless_whole_and_archived_and_so_is_the_board():
    s = source(SOURCE)
    assert (s.doi, s.archive_status, s.contains_personal_data) == (None, 'ok', False)
    assert s.archive_url and s.archive_captured.isoformat() == '2026-11-25'     # the lead's archiver, after review
    assert s.quote_extract_mode == 'full' and '@' not in s.quote_extract
    assert BENCH in s.cited_by
    board = source(BOARD)
    assert board.archive_status == 'ok' and board.archive_url and board.archive_captured.isoformat() == '2026-06-10'


def test_the_conditions_quotes_are_in_the_paper():
    nature = source(NATURE).quote_extract
    for quote in ('database release as the maximum allowed training set for any compliant model submission',
                  'we cleaned the WBM test set based on protostructure matching',
                  'leaving 215,488 structures in the unique prototype test set'):
        assert quote_found(quote, nature), quote


def test_no_new_conflict_group():
    conds = {c.eval_conditions: conditions(c) for c in CLAIMS}
    assert [r for r in conflicts.find(CORPUS, conds) if r['benchmark'].split('@')[0] == BENCH] == []
    groups = collections.Counter((c.benchmark, c.subset, c.metric, c.system) for c in CORPUS)
    assert all(groups[(c.benchmark, c.subset, c.metric, c.system)] == 1 for c in CLAIMS)
