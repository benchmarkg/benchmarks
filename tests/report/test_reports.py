"""Tests for `bench report completeness|conflicts|quality` (P3-S1-T07; 05 S3, 04 S8).

The verify: "completeness shows its denominator, conflicts finds the seeded disagreement fixture and names the
field, quality groups by rule, and all three emit byte-identical json on a re-run".
"""
import csv
import io
import json
import os
import sys
from datetime import date

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from tools import cli  # noqa: E402
from tools import report as R  # noqa: E402
from tools.report import completeness, conflicts, quality  # noqa: E402

runner = CliRunner()
BASE = {'system': 'example-model', 'benchmark': 'example-bench', 'metric': 'accuracy', 'value': 0.5,
        'date_reported': date(2026, 9, 1), 'reported_by': 'org-x', 'verification': 'self-reported', 'source': 'src-x'}


def claim(n, **kw):
    return ResultClaim.model_validate(dict(BASE, id='claim-%012x' % n, **kw))


# ---- completeness ----------------------------------------------------------------------------------------

def test_completeness_shows_its_denominator():
    rep = completeness.build(ROOT)
    assert rep['rows'], 'the corpus holds claims (ForecastBench, P0-S8-T06)'
    for r in rep['rows']:
        assert r['fields_material_total'] == len(r['material']) > 0
        assert r['weight_total'] > 0 and 0 <= r['weight_answered'] <= r['weight_total']
        assert r['condition_completeness'] == round(r['weight_answered'] / r['weight_total'], 6)
        assert r['populated'] == len(r['material']) - len(r['unknown_fields'])
    md = R.render(rep, 'md')
    assert 'fields_material_total' in md and 'weight_total' in md
    assert 'compare a claim only with its own denominator' in md


def test_completeness_counts_an_unanswered_field(monkeypatch):
    # drop one answered field from a committed claim's conditions and the report says which, and by how much
    from tools.build import comparability as comp
    real = comp.compute_for_claim

    def without_lead_time(cl, res, cond):
        if cond is not None and 'lead_time' in res.material:
            cond = cond.model_copy(update={'lead_time': None})
        return real(cl, res, cond)
    monkeypatch.setattr(comp, 'compute_for_claim', without_lead_time)
    rows = completeness.build(ROOT)['rows']
    hit = [r for r in rows if 'lead_time' in r['material']]
    assert hit and all('lead_time' in r['unknown_fields'] and r['condition_completeness'] < 1.0 for r in hit)


# ---- conflicts -------------------------------------------------------------------------------------------

CONDITIONS = {
    'cond-00000000000a': EvalConditions.model_validate({'id': 'cond-00000000000a', 'reasoning_effort': 'high',
                                                        'reasoning_effort_raw': 'high'}),
    'cond-00000000000b': EvalConditions.model_validate({'id': 'cond-00000000000b', 'reasoning_effort': 'low',
                                                        'reasoning_effort_raw': 'low'}),
}


def test_conflicts_finds_the_seeded_disagreement_and_names_the_fields():
    seeded = [claim(1, value=0.94, eval_conditions='cond-00000000000a'),
              claim(2, value=0.86, eval_conditions='cond-00000000000b'),         # 07 S5.2's 120K cluster, in small
              claim(3, value=0.7, metric='brier-score'),                         # another measurement
              claim(4, value=0.71, metric='brier-score', source='src-y')]
    rows = conflicts.find(seeded, CONDITIONS)
    assert [r['metric'] for r in rows] == ['accuracy', 'brier-score']
    effort, source = rows
    assert effort['claims'] == ['claim-000000000001', 'claim-000000000002'] and effort['values'] == [0.86, 0.94]
    assert effort['differing_fields'] == ['eval_conditions', 'value', 'eval_conditions.reasoning_effort',
                                          'eval_conditions.reasoning_effort_raw']
    assert source['differing_fields'] == ['source', 'value']


def test_an_unexplained_disagreement_names_only_the_value():
    rows = conflicts.find([claim(1, value=0.5), claim(2, value=0.6)], {})
    assert rows[0]['differing_fields'] == ['value']


@pytest.mark.parametrize('seeded', [
    [claim(1, value=0.5), claim(2, value=0.5, source='src-y')],                        # agree on the value
    [claim(1, value=0.5, subset='example-bench#a'), claim(2, value=0.6, subset='example-bench#b')],  # two subsets
    [claim(1, value=0.5, superseded_by='claim-000000000002'), claim(2, value=0.6)],   # history, not a rival
    [claim(1, value=0.5)],
])
def test_what_is_not_a_conflict(seeded):
    assert conflicts.find(seeded, {}) == []


def test_the_committed_corpus_has_no_false_conflict():
    # ForecastBench's three claims share benchmark, metric and system, at three horizons (subsets): no row.
    # The one row is P3-S5-T02's falcon-7b MMLU conflict, which is real -- eight claims, none adjudicated.
    [row] = conflicts.build(ROOT)['rows']
    assert (row['benchmark'], row['system'], row['metric'], len(row['claims'])) == ('mmlu', 'falcon-7b', 'mmlu-score', 8)


# ---- quality ---------------------------------------------------------------------------------------------

def test_quality_groups_warnings_and_signals_by_rule(monkeypatch):
    from tools.validate import tiers
    F = tiers.Finding
    fake = tiers.Report(tiers=(1, 2, 3, 4), scope='all', files=9, findings=[
        F(4, 'liveness-stale', 'quality', 'b-1', None, 'm'), F(4, 'liveness-stale', 'quality', 'b-2', None, 'm'),
        F(4, 'liveness-stale', 'quality', 'b-2', None, 'again'),                 # one entity, counted once
        F(3, 'private-server-submission', 'warning', 'b-3', None, 'm'),
        F(1, 'schema', 'blocking', 'b-4', None, 'm')])
    monkeypatch.setattr(tiers, 'run', lambda root: fake)
    rep = quality.build(ROOT)
    assert [(r['rule'], r['count'], r['entities']) for r in rep['rows']] == [
        ('liveness-stale', 2, ['b-1', 'b-2']), ('private-server-submission', 1, ['b-3'])]
    assert rep['summary']['blocking (see bench validate)'] == 1 and rep['summary']['warnings'] == 1


def test_quality_over_the_repository_has_one_row_per_rule():
    rows = quality.build(ROOT)['rows']
    keys = [(r['rule'], r['tier'], r['severity']) for r in rows]
    assert rows and len(keys) == len(set(keys)) and all(r['count'] == len(r['entities']) for r in rows)


# ---- the command and its output ----------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['completeness', 'conflicts', 'quality'])
def test_every_report_emits_byte_identical_json_on_a_re_run(name):
    first = runner.invoke(cli.app, ['report', name, '--format', 'json'])
    second = runner.invoke(cli.app, ['report', name, '--format', 'json'])
    assert first.exit_code == 0, first.output
    assert first.output == second.output
    assert json.loads(first.output)['report'] == name


def test_the_three_formats_render():
    rep = {'report': 'x', 'summary': {'n': 1}, 'columns': ['a', 'b'],
           'rows': [{'a': 'p|q', 'b': list(range(25))}, {'a': None, 'b': 0.1 + 0.2}]}
    md = R.render(rep, 'md')
    assert '| a | b |\n| --- | --- |\n' in md and 'p\\|q' in md and '... and 5 more' in md and '0.3' in md
    rows = list(csv.reader(io.StringIO(R.render(rep, 'csv'))))
    assert rows[0] == ['a', 'b'] and rows[1][1].count(',') == 24             # csv keeps every item
    assert json.loads(R.render(rep, 'json'))['rows'][0]['b'] == list(range(25))
    with pytest.raises(ValueError, match='format'):
        R.render(rep, 'xml')


def test_out_writes_the_report(tmp_path):
    out = tmp_path / 'r' / 'conflicts.md'
    r = runner.invoke(cli.app, ['report', 'conflicts', '--out', str(out)])
    assert r.exit_code == 0 and out.read_text(encoding='utf-8').startswith('# bench report conflicts')
