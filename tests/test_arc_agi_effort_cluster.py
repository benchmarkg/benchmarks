"""The claude-opus-4-6_120K cluster on ARC-AGI-1 (P3-S5-T01; 04 S10, 12 S8, 01 S10).

Epoch's arc_agi_external.csv holds five rows under one Model version, claude-opus-4-6_120K, told apart only by a
free-text Name. The ledger counts them as five claims at five efforts with five distinct comparability keys; the
sources support four. Two of the rows -- "Claude Opus 4.6 (120K, High)" with Source `https://arcprize.org/leaderboard`
and "Claude Opus 4.6 (High, 120k thinking)" with Source `ARC Prize Leaderboard` -- are one run spelled twice (04 S10's
second kind of near-duplicate), and ARC Prize's leaderboard lists exactly four rows for the group, one per effort. So
this module holds what the sources support, not the ledger's count: five Epoch rows, four runs, four claims, four
distinct keys, every claim at condition_completeness 0.8 (k is unknown: four of the five material fields).

The three rules, each a function so the failure cases run the same check the committed claims pass:
  - one claim per effort, and the efforts' comparability keys are distinct;
  - one claim per run: every Epoch row is recorded by exactly one claim, so the High pair is one claim with two
    sources -- neither merged away (a row no claim records) nor duplicated (two claims for one run);
  - 120K is a thinking budget, not a context window, on the leaderboard's own note.
Which Name label is which effort is a human reading of free text (READING below); every claim records its own and
says a reviewer confirms it.
"""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness  # noqa: E402

SYSTEM = 'claude-opus-4-6'
LEADERBOARD, EPOCH = 'src-arc-prize-leaderboard-2026-11-24', 'src-epoch-benchmark-data-2026-11-24'

# Epoch's five rows as the export prints them (CC-BY-4.0, epoch.ai/data), and the human reading of each Name label.
ROWS = {
    'recazrzN9UYUSV1iu': '"Claude Opus 4.6 (120K, High)",,https://arcprize.org/leaderboard,,,',
    'recZTnD93GgPevLI2': '"Claude Opus 4.6 (High, 120k thinking)",,ARC Prize Leaderboard,https://arcprize.org/leaderboard,,',
    'recM43lOIaRtUf1mn': '"Claude Opus 4.6 (120K, Max)",,https://arcprize.org/leaderboard,,,',
    'recoN4YV9cS1BcESr': '"Claude Opus 4.6 (120K, Medium)",,https://arcprize.org/leaderboard,,,',
    'recAgfLcp2ceTsir9': '"Claude Opus 4.6 (120K, Low)",,https://arcprize.org/leaderboard,,,',
}
SCORES = {'recazrzN9UYUSV1iu': '0.9400000000000001', 'recZTnD93GgPevLI2': '0.94', 'recM43lOIaRtUf1mn': '0.93',
          'recoN4YV9cS1BcESr': '0.92', 'recAgfLcp2ceTsir9': '0.86'}
READING = {'recazrzN9UYUSV1iu': 'high', 'recZTnD93GgPevLI2': 'high', 'recM43lOIaRtUf1mn': 'max',
           'recoN4YV9cS1BcESr': 'medium', 'recAgfLcp2ceTsir9': 'low'}
HIGH_PAIR = ('recazrzN9UYUSV1iu', 'recZTnD93GgPevLI2')
NOTE = "Evaluation conducted with a 120K thinking budget and a maximum context window of 128K tokens and '%s' output effort."


def extract(sid):
    return read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml'))['quote_extract']


def load():
    claims = [ResultClaim.model_validate(read_yaml(p))
              for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', 'arc-agi-1', '*.yaml')))]
    claims = [c for c in claims if c.system == SYSTEM]
    conds = {c.eval_conditions: EvalConditions.model_validate(read_yaml(
        os.path.join(ROOT, 'data', 'conditions', c.eval_conditions + '.yaml'))) for c in claims}
    return claims, conds


RESOLUTION = comp.resolve_profile(load_benchmark(
    os.path.join(ROOT, 'data', 'benchmarks', 'general-intelligence', 'arc-agi-1.yaml')))


def key(claim, conds):
    return comp.compute_for_claim(claim, RESOLUTION, conds[claim.eval_conditions]).comparability_key


def run_problems(claims, conds):
    """Everything that breaks one-claim-per-run and one-key-per-effort; empty when both hold."""
    out = []
    for rid in ROWS:
        holders = [c.id for c in claims if rid in (c.notes or '')]
        if not holders:
            out.append('row %s is recorded by no claim (merged away)' % rid)
        elif len(holders) > 1:
            out.append('row %s is recorded by %d claims (duplicated): %s' % (rid, len(holders), ', '.join(holders)))
    for c in claims:
        effort = conds[c.eval_conditions].reasoning_effort
        for rid in ROWS:
            if rid in (c.notes or '') and READING[rid] != effort:
                out.append('%s records row %s, read as %s, at effort %s' % (c.id, rid, READING[rid], effort))
    seen = {}
    for c in claims:
        seen.setdefault(key(c, conds), []).append(c.id)
    out += ['claims %s share comparability key %s' % (', '.join(ids), k) for k, ids in sorted(seen.items())
            if len(ids) > 1]
    return out


def budget_problems(claims, conds, leaderboard_extract):
    """Everything that contradicts "120K is a thinking budget" on the leaderboard's note; empty when it holds."""
    out = []
    for c in claims:
        cond = conds[c.eval_conditions]
        note = NOTE % cond.reasoning_effort
        if cond.thinking_token_budget != 120000:
            out.append('%s: thinking_token_budget is %s, not 120K' % (c.id, cond.thinking_token_budget))
        if cond.context_window_used == 120000:
            out.append('%s: 120K recorded as the context window' % c.id)
        if note not in (c.notes or '') or not quote_found(note, leaderboard_extract):
            out.append('%s: the leaderboard note for %s is not its quoted basis' % (c.id, cond.reasoning_effort))
    return out


CLAIMS, CONDS = load()


# ---- the committed cluster ----------------------------------------------------------------------------------

def test_five_rows_four_runs_four_claims_one_per_effort():
    assert len(ROWS) == 5 and len(CLAIMS) == 4
    assert sorted(CONDS[c.eval_conditions].reasoning_effort for c in CLAIMS) == ['high', 'low', 'max', 'medium']
    assert {c.benchmark for c in CLAIMS} == {'arc-agi-1@2024'} and {c.subset for c in CLAIMS} == \
        {'arc-agi-1#semi-private-evaluation'} and {c.metric for c in CLAIMS} == {'arc-agi-1-score'}


def test_four_distinct_keys_and_every_claim_at_completeness_0_6():
    keys = {key(c, CONDS) for c in CLAIMS}
    assert len(keys) == 4                                   # the ledger's five: one is the High pair's second row
    rows = {r['claim']: r for r in completeness.build(ROOT)['rows']}
    # Six material fields since ADR-0029 (P3-S10-T01): [exact-match, classical-algorithm] resolves trained-model, which
    # adds training_data_policy to the five the entry declared; the effort cluster's sources do not state it.
    for c in CLAIMS:
        r = rows[c.id]
        assert r['condition_completeness'] >= 0.6 and r['fields_material_total'] == 6, r
        assert r['unknown_fields'] == ['k', 'training_data_policy'], r


def test_every_epoch_row_is_in_the_export_and_every_value_on_the_leaderboard():
    epoch, board = extract(EPOCH), extract(LEADERBOARD)
    for rid, middle in ROWS.items():
        row = 'claude-opus-4-6_120K,%s,2026-02-05,Anthropic,United States of America,,,%s%s' % (SCORES[rid], middle, rid)
        assert quote_found(row, epoch), rid
    bs = chr(92)
    for c in CLAIMS:
        assert c.source == LEADERBOARD and c.reported_by == 'org-arc-prize-foundation'
        effort = CONDS[c.eval_conditions].reasoning_effort
        record = '"modelId":"claude-opus-4-6-thinking-120K-%s","score":%s' % (effort, c.value)
        assert quote_found(record.replace('"', bs + '"'), board), c.id
        assert c.provenance_snapshot.raw['modelId'] == 'claude-opus-4-6-thinking-120K-%s' % effort
        assert c.provenance_snapshot.raw['score'] == c.value


def test_the_high_pair_is_one_claim_with_two_sources():
    assert run_problems(CLAIMS, CONDS) == []
    [high] = [c for c in CLAIMS if CONDS[c.eval_conditions].reasoning_effort == 'high']
    assert all(rid in high.notes for rid in HIGH_PAIR)
    assert 'https://arcprize.org/leaderboard' in high.notes and '"ARC Prize Leaderboard"' in high.notes
    assert EPOCH in high.notes and high.source == LEADERBOARD


def test_each_claim_records_its_label_reading_for_a_reviewer():
    for c in CLAIMS:
        assert 'a human reading of free text' in c.notes and 'a reviewer confirms it' in c.notes, c.id


def test_120k_is_a_thinking_budget():
    assert budget_problems(CLAIMS, CONDS, extract(LEADERBOARD)) == []
    assert {CONDS[c.eval_conditions].context_window_used for c in CLAIMS} == {128000}


# ---- the failure cases --------------------------------------------------------------------------------------

def with_claim(claims, cid, **update):
    return [c.model_copy(update=update) if c.id == cid else c for c in claims]


def by_effort(effort):
    return next(c for c in CLAIMS if CONDS[c.eval_conditions].reasoning_effort == effort)


def test_a_second_claim_for_the_high_run_is_refused():
    high = by_effort('high')
    twin = high.model_copy(update={'id': 'claim-000000000001', 'notes': 'Epoch row %s' % HIGH_PAIR[1],
                                   'value': 0.9400000000000001})
    split = with_claim(CLAIMS, high.id, notes=high.notes.replace(HIGH_PAIR[1], 'the other row')) + [twin]
    problems = run_problems(split, CONDS)
    assert problems == ['claims %s, claim-000000000001 share comparability key %s' % (high.id, key(high, CONDS))]
    copied = CLAIMS + [high.model_copy(update={'id': 'claim-000000000002'})]
    assert 'row %s is recorded by 2 claims (duplicated): %s, claim-000000000002' % (HIGH_PAIR[0], high.id) in \
        run_problems(copied, CONDS)


def test_a_row_merged_away_is_refused():
    high = by_effort('high')
    merged = with_claim(CLAIMS, high.id, notes=high.notes.replace(HIGH_PAIR[1], 'the other row'))
    assert run_problems(merged, CONDS) == ['row %s is recorded by no claim (merged away)' % HIGH_PAIR[1]]


def test_two_efforts_collapsed_onto_one_key_are_refused():
    mx = by_effort('max')
    conds = dict(CONDS)
    conds[mx.eval_conditions] = CONDS[mx.eval_conditions].model_copy(update={'reasoning_effort': 'high',
                                                                            'reasoning_effort_raw': 'High'})
    problems = run_problems(CLAIMS, conds)
    assert '%s records row recM43lOIaRtUf1mn, read as max, at effort high' % mx.id in problems
    assert any('share comparability key' in p and mx.id in p for p in problems), problems


@pytest.mark.parametrize('update, expected', [
    ({'thinking_token_budget': None, 'context_window_used': 120000},
     ['thinking_token_budget is None, not 120K', '120K recorded as the context window']),
    ({'thinking_token_budget': 128000}, ['thinking_token_budget is 128000, not 120K']),
])
def test_120k_read_as_anything_but_a_thinking_budget_is_refused(update, expected):
    low = by_effort('low')
    conds = dict(CONDS)
    conds[low.eval_conditions] = CONDS[low.eval_conditions].model_copy(update=update)
    assert budget_problems(CLAIMS, conds, extract(LEADERBOARD)) == ['%s: %s' % (low.id, e) for e in expected]


def test_a_claim_without_the_note_as_its_basis_is_refused():
    low = by_effort('low')
    bare = with_claim(CLAIMS, low.id, notes=low.notes.replace(NOTE % 'low', 'a 120K run'))
    assert budget_problems(bare, CONDS, extract(LEADERBOARD)) == [
        '%s: the leaderboard note for low is not its quoted basis' % low.id]
