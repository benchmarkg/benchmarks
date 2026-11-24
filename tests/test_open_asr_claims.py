"""The Open ASR Leaderboard claims: four systems, each a WER and an RTFx bound by result_group (P3-S8-T08;
04-data-model.md S7 and S8).

The verify: "bench validate --tier all passes, plus a test asserting WER and RTFx claims share a result_group and
that neither renders alone". Done when: "Eight audio-speech claims exist and the non-LLM half of the gate is met."

  1. The pairs. Four systems, each with exactly one open-asr-wer and one open-asr-rtfx claim, and the two share a
     result_group that no other claim in the corpus holds. A pair is one run: one system, benchmark version,
     subset, source, date and conditions record.
  2. Neither renders alone. 04 S7: "the renderer will not show one member of a group alone", and 04 S6's
     must_report_with names the metrics a metric may never be shown without. No renderer draws claims yet (the
     claims table is P3-S10-T03's), so render_problems() below states the rule that table must apply, and the
     test holds the corpus to it, with the failure cases: a member shown alone, a bound metric with no group, a
     group missing its partner metric, and a group that mixes two systems' runs.
  3. Every number is the board's. Each claim's notes quote its row from the Space's Gradio config, the quote is in
     that Source's extract, and the row's Average WER and RTFx columns are the pair's two values.
  4. The pair counts toward the non-LLM half of the Phase 3 gate: no system is LLM-run (tools/report/llm_run.py),
     and each pair's conditions answer every material field of the board's profile. Whether the gate's >= 60 is
     met is the verify's count over data/claims/, not this test's.
"""
import collections
import glob
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import llm_run  # noqa: E402

BENCH = 'open-asr-leaderboard'
WER, RTFX = 'open-asr-wer', 'open-asr-rtfx'
SOURCE = 'src-hf-open-asr-leaderboard-config-7f8e531'
ROW = re.compile(r'the row "(\[.*?\])"')


def load_claims(pattern):
    return [ResultClaim.model_validate(read_yaml(p))
            for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', pattern, '*.yaml')))]


CLAIMS = load_claims(BENCH)
CORPUS = load_claims('**')
METRICS = {m: Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', m + '.yaml'))) for m in (WER, RTFX)}


def system(ref):
    return System.model_validate(read_yaml(os.path.join(ROOT, 'data', 'systems', ref.split('@')[0] + '.yaml')))


def pairs(claims):
    out = collections.defaultdict(list)
    for c in claims:
        out[c.result_group].append(c)
    return dict(out)


# ---- the rule --------------------------------------------------------------------------------------------

def render_problems(shown, corpus, metrics):
    """Why a surface may not render the claims `shown`, given every claim in `corpus` (04 S6, S7). A claim whose
    metric must be reported with another names a result_group; its group holds a claim on every such metric; and
    a claim is shown only beside every other member of its group."""
    out, ids = [], {c.id for c in shown}
    for c in shown:
        partners = metrics[c.metric].must_report_with if c.metric in metrics else []
        if c.result_group is None:
            if partners:
                out.append('%s: %s must be reported with %s, and the claim names no result_group'
                           % (c.id, c.metric, ', '.join(partners)))
            continue
        members = [x for x in corpus if x.result_group == c.result_group]
        for p in partners:
            if not any(x.metric == p for x in members):
                out.append('%s: its result_group %s holds no %s claim' % (c.id, c.result_group, p))
        missing = sorted(x.id for x in members if x.id not in ids)
        if missing:
            out.append('%s is shown without %s, the rest of its result_group' % (c.id, ', '.join(missing)))
    return out


def group_problems(members):
    """Why the claims of one result_group are not one run's numbers, if they are not."""
    out = []
    for field in ('system', 'benchmark', 'subset', 'source', 'date_reported', 'eval_conditions'):
        values = {str(getattr(c, field)) for c in members}
        if len(values) != 1:
            out.append('the group mixes %s: %s' % (field, ', '.join(sorted(values))))
    metrics = collections.Counter(c.metric for c in members)
    out += ['the group holds %d %s claims' % (n, m) for m, n in sorted(metrics.items()) if n != 1]
    return out


# ---- 1. the pairs ----------------------------------------------------------------------------------------

def test_four_systems_eight_claims():
    assert len(CLAIMS) == 8
    assert len({c.system for c in CLAIMS}) == 4
    assert collections.Counter(c.metric for c in CLAIMS) == {WER: 4, RTFX: 4}


def test_each_system_s_wer_and_rtfx_share_a_result_group():
    by_group = pairs(CLAIMS)
    assert None not in by_group
    assert len(by_group) == 4
    for group, members in by_group.items():
        assert sorted(c.metric for c in members) == sorted([WER, RTFX]), group
        assert group_problems(members) == [], group


def test_no_other_claim_joins_an_open_asr_group():
    groups = {c.result_group for c in CLAIMS}
    outsiders = [c.id for c in CORPUS if c.result_group in groups and c.benchmark.split('@')[0] != BENCH]
    assert outsiders == []
    assert sorted(c.id for c in CORPUS if c.result_group in groups) == sorted(c.id for c in CLAIMS)


def test_the_metrics_bind_each_other():
    assert METRICS[WER].must_report_with == [RTFX] and METRICS[RTFX].must_report_with == [WER]


# ---- 2. neither renders alone ------------------------------------------------------------------------------

def test_the_whole_pair_renders():
    assert render_problems(CLAIMS, CORPUS, METRICS) == []
    for group, members in pairs(CLAIMS).items():
        assert render_problems(members, CORPUS, METRICS) == [], group


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.system, c.metric))
def test_neither_member_renders_alone(claim):
    partner = next(c for c in CLAIMS if c.result_group == claim.result_group and c.id != claim.id)
    assert render_problems([claim], CORPUS, METRICS) == \
        ['%s is shown without %s, the rest of its result_group' % (claim.id, partner.id)]


def test_a_bound_metric_with_no_group_is_refused():
    wer = next(c for c in CLAIMS if c.metric == WER)
    loose = wer.model_copy(update={'result_group': None})
    assert render_problems([loose], CORPUS, METRICS) == \
        ['%s: open-asr-wer must be reported with open-asr-rtfx, and the claim names no result_group' % wer.id]


def test_a_group_without_its_partner_metric_is_refused():
    wer = next(c for c in CLAIMS if c.metric == WER)
    rest = [c for c in CORPUS if not (c.result_group == wer.result_group and c.metric == RTFX)]
    assert render_problems([wer], rest, METRICS) == \
        ['%s: its result_group %s holds no open-asr-rtfx claim' % (wer.id, wer.result_group)]


def test_a_group_mixing_two_systems_runs_is_not_a_pair():
    one, other = sorted(pairs(CLAIMS).values(), key=lambda m: m[0].system)[:2]
    wer = next(c for c in one if c.metric == WER)
    rtfx = next(c for c in other if c.metric == RTFX).model_copy(update={'result_group': wer.result_group})
    problems = group_problems([wer, rtfx])
    assert problems and problems[0].startswith('the group mixes system: ')
    assert 'the group mixes eval_conditions: ' in ' '.join(problems)
    assert group_problems([wer, wer.model_copy(update={'id': 'claim-000000000000'})]) == ['the group holds 2 open-asr-wer claims']


# ---- 3. every number is the board's -----------------------------------------------------------------------

@pytest.fixture(scope='module')
def extract():
    return Source.model_validate(read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', SOURCE + '.yaml'))).quote_extract


@pytest.mark.parametrize('members', list(pairs(CLAIMS).values()), ids=lambda m: m[0].system)
def test_the_pair_is_one_quoted_row_of_the_board(members, extract):
    by_metric = {c.metric: c for c in members}
    rows = set()
    for c in members:
        assert c.source == SOURCE
        m = ROW.search(c.notes or '')
        assert m, '%s quotes no row' % c.id
        assert quote_found(m.group(1), extract), '%s: the row is not in %s' % (c.id, SOURCE)
        rows.add(m.group(1))
    assert len(rows) == 1                                   # both members quote the same row
    row = json.loads(rows.pop())                            # rank, rank delta, model, Average WER, RTFx, datasets
    board_id = system(members[0].system).external_ids['huggingface']
    assert row[2].split(' ')[0] == board_id
    assert (row[3], row[4]) == (by_metric[WER].value, by_metric[RTFX].value)


def test_the_columns_are_average_wer_then_rtfx(extract):
    assert quote_found('"model","Average WER ⬇️","RTFx ⬆️️"', extract)
    assert quote_found('Last updated on 20 November 2026 (v1.16.2)', extract)


def test_the_source_is_withheld_because_the_body_names_people():
    s = Source.model_validate(read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', SOURCE + '.yaml')))
    assert (s.archive_status, s.contains_personal_data, s.archive_url) == ('withheld', True, None)
    assert s.failure_reason


# ---- 4. the non-LLM half of the gate ----------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: '%s-%s' % (c.system, c.metric))
def test_no_open_asr_claim_is_llm_run(claim):
    assert llm_run.llm_run(claim.system) is False
    assert system(claim.system).system_type == 'task-specific-supervised-model'


def test_every_material_field_is_answered():
    built = comp.build(ROOT)['claims']
    for c in CLAIMS:
        assert built[c.id]['condition_completeness'] == 1.0, c.id
        assert built[c.id]['unknown_fields'] == [], c.id
    keys = {c.system: built[c.id]['comparability_key'] for c in CLAIMS if c.metric == WER}
    assert len(set(keys.values())) == 4                     # each model is its own provider_snapshot
