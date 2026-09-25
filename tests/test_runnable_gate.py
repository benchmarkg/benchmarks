"""Tests for scripts/runnable_gate.py, the five-clause gate query (P8-S1-T06; 13 S3, S3.2, S5.6).

The verify: "A fixture corpus with known per-clause attrition reproduces both the final count and
every intermediate drop exactly." The corpus is tests/fixtures/runnable_gate/: fourteen records, each
named for the clause that stops it, built so that every clause both fails and leaves undetermined at
least one record, and exactly one record passes all five.
"""
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'runnable_gate')
spec = importlib.util.spec_from_file_location('runnable_gate', os.path.join(ROOT, 'scripts', 'runnable_gate.py'))
gate = importlib.util.module_from_spec(spec)
sys.modules['runnable_gate'] = gate
spec.loader.exec_module(gate)

# (clause, entering, failed ids, undetermined ids, remaining) -- worked out by hand from the fixtures
EXPECTED = [
    (1, 14, ['r-physical', 'r-raters'], ['r-not-a-term', 'r-null'], 10),
    (2, 10, ['c-gpu', 'c-simulator'], ['c-missing'], 7),
    (3, 7, ['a-dua', 'a-server'], [], 5),
    (4, 5, ['k-carved'], ['k-unknown'], 3),
    (5, 3, ['h-covered'], ['h-unclear'], 1),
]


def fixture_gate(**kw):
    return gate.run(gate.load(FIXTURE), **kw)


# ---- the verify ---------------------------------------------------------------------------------

def test_the_fixture_reproduces_the_final_count():
    g = fixture_gate()
    assert g.total == 14
    assert g.count == 1 and g.passing == ['gate-passer']


@pytest.mark.parametrize('clause, entering, failed, undetermined, remaining', EXPECTED)
def test_the_fixture_reproduces_every_intermediate_drop(clause, entering, failed, undetermined, remaining):
    step = fixture_gate().steps[clause - 1]
    assert step.clause.number == clause
    assert step.entering == entering
    assert sorted(step.failed) == failed
    assert sorted(step.undetermined) == undetermined
    assert step.remaining == remaining


def test_each_step_starts_from_the_previous_step_s_survivors():
    steps = fixture_gate().steps
    for before, after in zip(steps, steps[1:]):
        assert after.entering == before.remaining
    assert steps[-1].remaining == fixture_gate().count


def test_the_json_report_carries_the_attrition(capsys):
    assert gate.main(['--root', FIXTURE, '--json', '--threshold', '70']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['count'] == 1 and report['threshold'] == 70 and report['meets_threshold'] is False
    assert [(s['entering'], s['failed'], s['undetermined'], s['remaining']) for s in report['steps']] == \
        [(e, len(f), len(u), r) for _, e, f, u, r in EXPECTED]


def test_the_table_report(capsys):
    assert gate.main(['--root', FIXTURE]) == 0
    out = capsys.readouterr().out
    assert '| 1 | reproducibility_tier in {fully-automatable, automatable-with-simulator} | 14 | 2 | 2 | 10 |' in out
    assert 'passing all five: 1 (gate-passer)' in out


# ---- the clauses --------------------------------------------------------------------------------

def test_the_clauses_are_13_s3_s_five_in_its_order():
    assert [c.number for c in gate.CLAUSES] == [1, 2, 3, 4, 5]
    assert [c.field for c in gate.CLAUSES] == [
        'execution.reproducibility_tier', 'execution.compute_tier', 'data.access',
        'execution.dangerous_capability_carveout', 'execution.covered_by_maintained_harness_leaderboard']
    assert gate.REPRODUCIBLE == ('fully-automatable', 'automatable-with-simulator')
    assert gate.API_ONLY == 'api-credits-only'
    assert gate.OPEN_ACCESS == ('fully-open', 'gated-registration')


def test_order_changes_the_attrition_not_the_final_count(monkeypatch):
    """13 S3: a threshold set before the carve-out is set against the wrong population. A record
    that fails two clauses is charged to whichever it meets first."""
    ok = {'reproducibility_tier': 'fully-automatable', 'compute_tier': 'api-credits-only',
          'dangerous_capability_carveout': False, 'covered_by_maintained_harness_leaderboard': False}
    records = {
        'carved-and-gpu': {'execution': {**ok, 'compute_tier': 'single-gpu', 'dangerous_capability_carveout': True},
                           'data': {'access': 'fully-open'}},
        'passer': {'execution': ok, 'data': {'access': 'fully-open'}},
    }
    forward = gate.run(records)
    assert forward.steps[1].failed == ['carved-and-gpu'] and forward.steps[3].failed == []
    monkeypatch.setattr(gate, 'CLAUSES', tuple(reversed(gate.CLAUSES)))
    backward = gate.run(records)
    assert backward.steps[1].clause.number == 4 and backward.steps[1].failed == ['carved-and-gpu']
    assert backward.passing == forward.passing == ['passer']
    # on the fixture (still reversed here) the populations each clause sees move; the survivor does not
    assert [s.entering for s in fixture_gate().steps] == [14, 12, 10, 8, 5]
    assert fixture_gate().passing == ['gate-passer']


def test_an_undetermined_fact_is_never_a_pass():
    vocab = gate.vocabularies()
    empty = {}
    assert all(c.test(empty, vocab) == gate.UNDETERMINED for c in gate.CLAUSES)
    assert gate.run({'x': empty}, vocab=vocab).count == 0
    # a boolean clause wants a boolean: a string, a number or null is not an answer
    for value in ('false', 0, None, 'no'):
        assert gate.CLAUSES[3].test({'execution': {'dangerous_capability_carveout': value}}, vocab) == gate.UNDETERMINED


def test_a_term_that_is_not_in_the_vocabulary_is_undetermined_not_a_fail():
    vocab = gate.vocabularies()
    assert 'requires-eval-server' not in vocab['reproducibility_tier']        # 13 S3's spelling, not a term
    assert gate.CLAUSES[0].test({'execution': {'reproducibility_tier': 'requires-eval-server'}}, vocab) \
        == gate.UNDETERMINED


def test_a_gate_term_renamed_out_of_the_taxonomy_stops_the_query(monkeypatch, capsys):
    monkeypatch.setattr(gate, 'OPEN_ACCESS', ('fully-open', 'registration-gated'))
    assert gate.main(['--root', FIXTURE]) == 2
    assert 'registration-gated' in capsys.readouterr().err


def test_a_file_that_does_not_parse_stops_the_query(tmp_path, capsys):
    d = tmp_path / 'data' / 'benchmarks' / 'x'
    d.mkdir(parents=True)
    (d / 'broken.yaml').write_text('id: a\nid: b\n', encoding='utf-8')          # a duplicate key
    assert gate.main(['--root', str(tmp_path)]) == 2


def test_the_threshold_is_derived_from_phase_hours():
    assert (gate.threshold_for(190), gate.threshold_for(350)) == (38, 70)        # 13 S3.2's band


# ---- the committed corpus -----------------------------------------------------------------------

def test_the_committed_corpus():
    """SWE-bench clears the first three clauses and stops, undetermined, at the carve-out: the fact
    is not a schema field yet. RoboArena needs physical hardware; CASP's tier is not curated."""
    g = gate.run(gate.load(ROOT))
    assert g.count == 0
    steps = {s.clause.number: s for s in g.steps}
    assert steps[1].failed == ['roboarena'] and steps[1].undetermined == ['casp']
    assert steps[3].remaining == 1
    assert steps[4].undetermined == ['swe-bench']


def test_the_gate_is_not_on_the_bench_surface():
    """05 S3's block is the CLI's only specification (the task's step 3)."""
    cli = open(os.path.join(ROOT, 'tools', 'cli.py'), encoding='utf-8').read()
    assert 'runnable' not in cli and 'gate' not in cli
