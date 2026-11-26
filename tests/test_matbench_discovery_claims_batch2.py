"""Matbench Discovery claims, batch 2: five non-compliant leaderboard entries, from the other compliance tier than
batch 1's, and the proof that the tier is a material condition (P3-S7-T02; 04-data-model.md S7 and S8).

The verify: "bench validate --tier all, plus a test asserting the ten claims span at least two eligibility_track
values and that claims in different tiers have different comparability keys". The done-when: "Ten claims exist and
the training-side comparability key is demonstrably material."

Batch 1 (P3-S7-T01, tests/test_matbench_discovery_claims.py) read five compliant models' F1 off the v1 paper's
all-model unique-prototype table. This batch reads five non-compliant models' F1 off the same table, so that the
ten differ in their tier and in nothing else a reader would call a condition. That is held here as:

  1. Ten claims. Batch 1's five and these five, all in data/claims/matbench-discovery/: ten Systems, one metric
     (f1-score) on one subset, one Source, one date, and one conditions record per tier. Three of the five are
     batch 1's models' counterparts trained on MPtrj and more (eqV2 M, ORB v2 and MACE-MPA-0 beside eqV2 S DeNS,
     ORB v2 MPtrj and MACE-MP-0).
  2. The verify, first half. The ten span two eligibility_track values, compliant and non-compliant, each an id of
     the entry's training_data_eligibility_tiers and equal to its record's training_data_eligibility. Failure case:
     the ten with batch 2 relabelled compliant span one value.
  3. The verify, second half. Claims in different tiers have different comparability keys, and the claims of one
     tier share one. Failure cases: two claims identical except for their tier (a batch-1 claim and its copy in the
     other tier) get different keys under the entry's resolution, through either tier field alone, and the same
     key once the tier fields are waived; and under a resolution that waives the training side, the two tiers
     collide on one key, which the check refuses.
  4. The done-when. The two tiers' key tuples agree on benchmark, metric, subset and subset_used and differ on
     exactly the training-side fields (eligibility_track, training_data_eligibility, training_data_policy and
     decontamination_applied); each of the four moves the key on its own; and eligibility_track is in the entry's
     material_extra, so no change of facets drops it.
  5. The tier follows the sources. Each Training Set cell names a dataset the compliant rows do not train on, and
     each F1 is above the top row of the paper's compliant-only table (eqV2 S DeNS, 0.815), which is ranked by F1,
     so none of the five is in that table. Failure cases: an MPtrj-only cell reads compliant, an unreadable cell is
     never compliant, and an F1 at or below 0.815 proves no absence.
  6. Every number is the table's and the board's, as batch 1's test 4 has it for its five.
  7. Completeness. Each of the five is at 0.8: decontamination_applied is the one unknown, because the test set was
     cleaned against the MP release only. The report shows all ten at >= 0.6 with eligibility_track populated.
     Failure case: a record that also drops the policy and the tier id falls under the gate.
  8. Identity and provenance. Content-derived ids, no claim LLM-run, no (benchmark, subset, metric, system) group
     of two, so `bench report conflicts` gains no row; the Sources are batch 1's, nameless and archived.
"""
import collections
import glob
import hashlib
import itertools
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import Waiver, load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.source import Source, fold, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness, conflicts, llm_run  # noqa: E402

BENCH = 'matbench-discovery'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BENCH + '.yaml')
METRIC, SUBSET = 'f1-score', 'matbench-discovery#unique-prototypes'
SOURCE = 'src-github-matbench-discovery-metrics-table-uniq-protos-6d587c1'
COMPLIANT_TABLE = 'src-github-matbench-discovery-metrics-table-compliant-6d587c1'
BOARD = 'src-matbench-discovery-homepage'
NATURE = 'src-matbench-discovery-nature'
# claim id -> System, per batch
FIRST = {'claim-f83949fcbbac': 'eqv2-s-dens', 'claim-33cffc25e71e': 'orb-v2-mptrj', 'claim-0104f677651c': 'mace-mp-0',
         'claim-aa0bfaee5578': 'chgnet', 'claim-06c74c9cd199': 'm3gnet'}                       # P3-S7-T01, compliant
SECOND = {'claim-5d2e2dc0aae7': 'eqv2-m', 'claim-09a3ff4eefc1': 'grace-2l-oam', 'claim-88f9834df091': 'orb-v2',
          'claim-30d613d3efe2': 'mattersim-v1-5m', 'claim-b2a96a079433': 'mace-mpa-0'}         # this batch
COND = {'compliant': 'cond-0cf2df0d2e99', 'non-compliant': 'cond-35c1dde1d3b6'}
# Batch 2's model -> batch 1's model of the same architecture trained on MPtrj alone.
COUNTERPART = {'eqv2-m': 'eqv2-s-dens', 'orb-v2': 'orb-v2-mptrj', 'mace-mpa-0': 'mace-mp-0'}
TIER_FIELDS = ('eligibility_track', 'training_data_eligibility')
TRAINING_SIDE = ('decontamination_applied', 'eligibility_track', 'training_data_eligibility', 'training_data_policy')
TABLE_HEADER = ('Model F1 ↑ DAF ↑ Prec ↑ Acc ↑ TPR ↑ TNR ↑ MAE ↓ RMSE ↓ R2 ↑ Training Set Model Params Targets '
                'Date Added')
BOARD_HEADER = 'Model CPS ↑ Acc F1 DAF Prec MAE R2 κSRME RMSD Training Set Params Targets Date Added'
# The compliant-only table opens with its header and then its best row, at F1 0.815.
COMPLIANT_TOP, COMPLIANT_TOP_F1 = TABLE_HEADER + ' eqV2 S DeNS 0.815', 0.815
TABLE_ROW = re.compile(r'the table row "([^"]+)"')
BOARD_ROW = re.compile(r'the board row "([^"]+)"')
NUMBER = r'(-?\d+(?:\.\d+)?)'
# The datasets the compliant rows of the two tables train on (batch 1's test, and the entry's compliant rule).
COMPLIANT_SETS = {'MPtrj', 'MPF', 'MP 2022', 'MP Graphs'}
GATE = 0.6
# The table's name for a row where the System takes the board's newer name.
TABLE_NAMES = {'orb-v2': 'ORB'}


def load(kind, ident, model):
    return model.model_validate(read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml')))


def load_claims(pattern):
    return [ResultClaim.model_validate(read_yaml(p))
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', pattern, '*.yaml')))]


ALL = load_claims(BENCH)
CORPUS = load_claims('**')
TEN = [c for c in ALL if c.id in FIRST or c.id in SECOND]
CLAIMS = [c for c in ALL if c.id in SECOND]
ENTRY_B = load_benchmark(ENTRY)
RESOLUTION = comp.resolve_profile(ENTRY_B)


def source(sid):
    return load(os.path.join('sources', '2026'), sid, Source)


def conditions(claim):
    return load('conditions', claim.eval_conditions, EvalConditions)


def claim_of(system):
    return next(c for c in TEN if c.system == system)


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


def absent_from_compliant_table(f1):
    """Whether a model with this F1 is provably not in the compliant-only table, which is ranked by F1 and whose
    best row is at COMPLIANT_TOP_F1: only a score above that row can be missing from it."""
    return f1 > COMPLIANT_TOP_F1


def key_of(claim, cond, resolution=RESOLUTION):
    return comp.compute_for_claim(claim, resolution, cond).comparability_key


def key_tuple(claim, cond):
    """04 S8's key tuple for a claim, by field name, checked against the key the build computes from it."""
    names = ['benchmark', 'metric', 'subset'] + list(RESOLUTION.material)
    tup = [claim.benchmark, claim.metric, claim.subset] + [
        comp.canonicalise(cond.value(f)) if cond.answered(f) else comp.UNKNOWN for f in RESOLUTION.material]
    assert hashlib.sha256(json.dumps(tup, separators=(',', ':')).encode('utf-8')).hexdigest()[:16] == \
        key_of(claim, cond)
    return dict(zip(names, tup))


def waiving(*fields):
    """The entry's resolution with `fields` waived, as a curator's comparability.material_waived would make it."""
    c = ENTRY_B.comparability.model_copy(
        update={'material_waived': [Waiver(field=f, reason='Counterfactual for the test.') for f in fields]})
    return comp.resolve_profile(ENTRY_B.model_copy(update={'comparability': c}))


def span_problems(claims, conds):
    """Why a set of claims fails the verify's first half: fewer than two eligibility_track values."""
    tracks = sorted({conds[c.id].eligibility_track for c in claims} - {None})
    return [] if len(tracks) >= 2 else ['the claims span %d eligibility_track value(s): %s'
                                        % (len(tracks), ', '.join(tracks))]


def tier_key_problems(claims, conds, resolution=RESOLUTION):
    """Why a set of claims fails the verify's second half: two claims in different tiers that share a key."""
    out = []
    for a, b in itertools.combinations(claims, 2):
        ta, tb = conds[a.id].eligibility_track, conds[b.id].eligibility_track
        if ta != tb and key_of(a, conds[a.id], resolution) == key_of(b, conds[b.id], resolution):
            out.append('%s (%s) and %s (%s) share a comparability key' % (a.id, ta, b.id, tb))
    return out


def gate_problems(claim, cond):
    """Why a claim fails batch 1's gate: completeness under 0.6 or no eligibility_track."""
    out = []
    got = comp.compute_for_claim(claim, RESOLUTION, cond)
    if got.condition_completeness is None or got.condition_completeness < GATE:
        out.append('%s: condition_completeness %s is under %s' % (claim.id, got.condition_completeness, GATE))
    if cond is None or cond.eligibility_track is None:
        out.append('%s: eligibility_track is not populated' % claim.id)
    return out


CONDS = {c.id: conditions(c) for c in TEN}


# ---- 1. ten claims ------------------------------------------------------------------------------------------------

def test_ten_claims_ten_systems_two_records():
    assert sorted(c.id for c in ALL) == sorted(list(FIRST) + list(SECOND))
    assert {c.id: c.system for c in TEN} == {**FIRST, **SECOND}
    assert len({c.system for c in TEN}) == 10
    for field in ('benchmark', 'metric', 'subset', 'source', 'date_reported', 'reported_by', 'verification',
                  'claim_type'):
        assert len({str(getattr(c, field)) for c in TEN}) == 1, field
    assert {c.eval_conditions for c in TEN} == set(COND.values())
    assert {c.eval_conditions for c in CLAIMS} == {COND['non-compliant']}
    c = CLAIMS[0]
    assert (c.benchmark, c.metric, c.subset, c.source) == (BENCH, METRIC, SUBSET, SOURCE)
    assert (c.claim_type, c.verification) == ('absolute', 'maintainer-verified')


def test_three_are_batch_ones_models_trained_on_more_data():
    for second, first in COUNTERPART.items():
        _, _, more, _ = table_row(TABLE_ROW.search(claim_of(second).notes).group(1))
        _, _, mptrj, _ = table_row(TABLE_ROW.search(claim_of(first).notes).group(1))
        assert mptrj == {'MPtrj'} and more > mptrj, (second, more)
        assert CONDS[claim_of(second).id].eligibility_track != CONDS[claim_of(first).id].eligibility_track


# ---- 2. the verify: at least two eligibility_track values -------------------------------------------------------

def test_the_ten_span_two_eligibility_tracks():
    assert span_problems(TEN, CONDS) == []
    assert collections.Counter(CONDS[c.id].eligibility_track for c in TEN) == {'compliant': 5, 'non-compliant': 5}
    tiers = {t.id for t in ENTRY_B.training_data_eligibility_tiers}
    for c in TEN:
        cond = CONDS[c.id]
        assert cond.eligibility_track in tiers
        assert cond.eligibility_track == cond.training_data_eligibility
        assert c.eval_conditions == COND[cond.eligibility_track]


def test_one_tier_only_is_refused():
    relabelled = {cid: cond.model_copy(update={'eligibility_track': 'compliant'}) for cid, cond in CONDS.items()}
    assert span_problems(TEN, relabelled) == ['the claims span 1 eligibility_track value(s): compliant']
    assert span_problems(CLAIMS, CONDS) == ['the claims span 1 eligibility_track value(s): non-compliant']


# ---- 3. the verify: different tiers, different keys ----------------------------------------------------------------

def test_claims_in_different_tiers_have_different_keys():
    assert tier_key_problems(TEN, CONDS) == []
    built = comp.build(ROOT)['claims']
    keys = {tier: {built[c.id]['comparability_key'] for c in TEN if CONDS[c.id].eligibility_track == tier}
            for tier in COND}
    assert all(len(k) == 1 for k in keys.values()), keys                 # one key per tier
    assert keys['compliant'].isdisjoint(keys['non-compliant'])
    for c in TEN:
        assert built[c.id]['comparability_key'] == key_of(c, CONDS[c.id])


def test_two_claims_identical_but_for_their_tier_get_different_keys():
    c = claim_of('eqv2-s-dens')
    cond = CONDS[c.id]
    other = cond.model_copy(update={f: 'non-compliant' for f in TIER_FIELDS})
    twin = c.model_copy(update={'id': 'claim-000000000000', 'eval_conditions': 'cond-000000000000'})
    assert key_of(c, cond) != key_of(twin, other)
    for f in TIER_FIELDS:                                                # either tier field moves the key alone
        assert key_of(c, cond) != key_of(twin, cond.model_copy(update={f: 'non-compliant'})), f
    assert tier_key_problems([c, twin], {c.id: cond, twin.id: other}) == []
    # With the tier fields waived the two are one key: it is the tier, and nothing else, that keeps them apart.
    assert key_of(c, cond, waiving(*TIER_FIELDS)) == key_of(twin, other, waiving(*TIER_FIELDS))
    assert tier_key_problems([c, twin], {c.id: cond, twin.id: other}, waiving(*TIER_FIELDS)) == [
        '%s (compliant) and %s (non-compliant) share a comparability key' % (c.id, twin.id)]


def test_with_the_training_side_waived_the_tiers_collide_and_are_refused():
    resolution = waiving(*TRAINING_SIDE)
    assert resolution.material == ('subset_used',)
    assert len({key_of(c, CONDS[c.id], resolution) for c in TEN}) == 1
    problems = tier_key_problems(TEN, CONDS, resolution)
    assert len(problems) == 25                                           # every compliant x non-compliant pair
    assert {frozenset(re.findall(r'claim-[0-9a-f]{12}', p)) for p in problems} == {
        frozenset((a, b)) for a in FIRST for b in SECOND}


# ---- 4. the done-when: the training-side key is material -----------------------------------------------------------

def test_the_two_tiers_differ_on_the_training_side_only():
    assert set(TRAINING_SIDE) < set(RESOLUTION.material)
    assert 'eligibility_track' in RESOLUTION.extra                      # material whatever the facets resolve to
    first, second = (key_tuple(claim_of(s), CONDS[claim_of(s).id]) for s in ('eqv2-s-dens', 'eqv2-m'))
    assert {k for k in first if first[k] != second[k]} == set(TRAINING_SIDE)
    assert (second['eligibility_track'], second['training_data_eligibility']) == ('non-compliant', 'non-compliant')
    assert (first['training_data_policy'], second['training_data_policy']) == ('restricted-list', 'open')
    assert (first['decontamination_applied'], second['decontamination_applied']) == (True, comp.UNKNOWN)


@pytest.mark.parametrize('field', TRAINING_SIDE)
def test_each_training_side_field_moves_the_key_alone(field):
    c = claim_of('eqv2-s-dens')
    cond, other = CONDS[c.id], CONDS[claim_of('eqv2-m').id]
    moved = cond.model_copy(update={field: getattr(other, field)})
    assert getattr(moved, field) != getattr(cond, field)
    assert key_of(c, moved) != key_of(c, cond)
    assert key_of(c, moved, waiving(field)) == key_of(c, cond, waiving(field))     # and only while it is material


# ---- 5. the tier follows the sources --------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_the_tier_follows_the_training_set_cell_and_the_compliant_table(claim):
    _, f1, sets, _ = table_row(TABLE_ROW.search(claim.notes).group(1))
    assert tier_of(sets) == CONDS[claim.id].training_data_eligibility == 'non-compliant'
    assert absent_from_compliant_table(f1)
    extract = fold(source(SOURCE).quote_extract)         # the all-model table ranks it above eqV2 S DeNS's 0.815
    assert extract.index(fold(TABLE_ROW.search(claim.notes).group(1))) < extract.index(fold('eqV2 S DeNS 0.815'))


def test_the_compliant_table_opens_at_0_815():
    assert quote_found(COMPLIANT_TOP, source(COMPLIANT_TABLE).quote_extract)
    for c in CLAIMS:
        assert '"Date Added eqV2 S DeNS 0.815"' in c.notes, c.id
    assert claim_of('eqv2-s-dens').value == COMPLIANT_TOP_F1
    assert max(c.value for c in TEN if c.id in FIRST) <= COMPLIANT_TOP_F1 < min(c.value for c in CLAIMS)


def test_a_compliant_cell_or_a_lower_score_proves_nothing():
    assert tier_of({'MPtrj'}) == tier_of({'MPF'}) == 'compliant'
    assert tier_of(set()) == 'non-compliant'                             # an unreadable cell is never compliant
    assert not absent_from_compliant_table(COMPLIANT_TOP_F1)             # eqV2 S DeNS is that table's top row
    assert not absent_from_compliant_table(0.765)
    row = 'eqV2 S DeNS 0.815 5.04 0.771 0.941 0.864 0.953 0.036 0.085 0.788 146K (1.6M) (MPtrj) 31.2M EFSD 2024-10-18'
    assert quote_found(row, source(SOURCE).quote_extract)
    assert tier_of(table_row(row)[2]) == 'compliant'


# ---- 6. every number is the table's, and the board's -----------------------------------------------------------------

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


def test_a_wrong_value_or_another_row_is_caught():
    c = claim_of('orb-v2')
    assert table_row(TABLE_ROW.search(c.notes).group(1))[1] != c.value + 0.001
    other = claim_of('orb-v2-mptrj')                                     # the same name stem, the other tier's row
    assert table_row(TABLE_ROW.search(other.notes).group(1))[0] != TABLE_NAMES['orb-v2']


# ---- 7. completeness ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.system)
def test_four_of_five_answered_and_decontamination_unknown(claim):
    got = comp.compute_for_claim(claim, RESOLUTION, CONDS[claim.id])
    assert got.condition_completeness == pytest.approx(0.8)
    assert got.unknown_fields == ('decontamination_applied',) and got.key_unknown_count == 1
    assert gate_problems(claim, CONDS[claim.id]) == []


def test_the_report_shows_ten_claims_at_the_gate_with_eligibility_track():
    rows = [r for r in completeness.build(ROOT)['rows'] if r['benchmark'] == BENCH]
    assert sorted(r['claim'] for r in rows) == sorted(c.id for c in TEN)
    for r in rows:
        assert r['condition_completeness'] >= GATE, r['claim']
        assert 'eligibility_track' in r['material'] and 'eligibility_track' not in r['unknown_fields'], r['claim']


def test_a_thinner_record_falls_under_the_gate():
    c = CLAIMS[0]
    thin = CONDS[c.id].model_copy(update={'training_data_policy': None, 'training_data_eligibility': None})
    assert gate_problems(c, thin) == ['%s: condition_completeness 0.4 is under 0.6' % c.id]
    assert gate_problems(c, thin.model_copy(update={'eligibility_track': None})) == [
        '%s: condition_completeness 0.2 is under 0.6' % c.id, '%s: eligibility_track is not populated' % c.id]


# ---- 8. identity and provenance --------------------------------------------------------------------------------------

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


def test_the_sources_are_batch_ones_nameless_and_archived():
    for sid in (SOURCE, COMPLIANT_TABLE):
        s = source(sid)
        assert (s.doi, s.archive_status, s.contains_personal_data) == (None, 'ok', False), sid
        assert s.archive_url and BENCH in s.cited_by and '@' not in s.quote_extract, sid
    assert source(BOARD).archive_status == 'ok'
    nature = source(NATURE).quote_extract
    for quote in ('our benchmark contains models trained on varying datasets, and any model that can intake more '
                  'physical modalities from DFT calculations is a valid model for materials discovery',
                  'we cleaned the WBM test set based on protostructure matching',
                  'leaving 215,488 structures in the unique prototype test set'):
        assert quote_found(quote, nature), quote


def test_no_new_conflict_group():
    conds = {c.eval_conditions: CONDS[c.id] for c in TEN}
    assert [r for r in conflicts.find(CORPUS, conds) if r['benchmark'].split('@')[0] == BENCH] == []
    groups = collections.Counter((c.benchmark, c.subset, c.metric, c.system) for c in CORPUS)
    assert all(groups[(c.benchmark, c.subset, c.metric, c.system)] == 1 for c in TEN)
