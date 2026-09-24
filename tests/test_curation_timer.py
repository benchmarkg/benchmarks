"""Tests for scripts/curation_timer.py against tests/fixtures/curation-rate-3.jsonl.

The fixture is three records by one curator, timed from their start/stop stamps:

    fixture-off-1  copilot off  09:00:00 -> 10:12:00   72.0 min
    fixture-on-1   copilot on   10:30:00 -> 11:07:30   37.5 min
    fixture-on-2   copilot on   13:00:00 -> 13:49:00   49.0 min

Worked by hand, inclusive (linear-interpolation) quartiles over the sorted 37.5, 49.0, 72.0:
the positions are (n-1)p = 0.5, 1, 1.5, so

    median = 49.0
    Q1     = 37.5 + 0.5 x (49.0 - 37.5) = 43.25
    Q3     = 49.0 + 0.5 x (72.0 - 49.0) = 60.5

and the copilot split is on n=2, median (37.5 + 49.0) / 2 = 43.25; off n=1, median 72.0; the
on/off ratio is 43.25 / 72.0 = 0.600694..., a copilot 39.9% faster. These constants are typed
in, not computed, so a change to any of them fails a test.
"""
import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'curation-rate-3.jsonl')

spec = importlib.util.spec_from_file_location('curation_timer', os.path.join(ROOT, 'scripts', 'curation_timer.py'))
curation_timer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curation_timer)

MEDIAN = 49.0
Q1, Q3 = 43.25, 60.5
ON_N, ON_MEDIAN = 2, 43.25
OFF_N, OFF_MEDIAN = 1, 72.0
RATIO = 43.25 / 72.0


def report_json(ledger, capsys):
    assert curation_timer.main(['--report', '--json', '--ledger', str(ledger)]) == 0
    return json.loads(capsys.readouterr().out)


def test_report_reproduces_the_hand_computed_median(capsys):
    assert report_json(FIXTURE, capsys)['median'] == MEDIAN


def test_report_reproduces_the_hand_computed_quartiles(capsys):
    rep = report_json(FIXTURE, capsys)
    assert (rep['q1'], rep['q3']) == (Q1, Q3)


def test_report_reproduces_the_hand_computed_copilot_split(capsys):
    rep = report_json(FIXTURE, capsys)
    assert (rep['copilot']['on']['n'], rep['copilot']['on']['median']) == (ON_N, ON_MEDIAN)
    assert (rep['copilot']['off']['n'], rep['copilot']['off']['median']) == (OFF_N, OFF_MEDIAN)
    assert rep['on_off_ratio'] == pytest.approx(RATIO, abs=1e-12)
    assert rep['copilot']['on']['curators'] == rep['copilot']['off']['curators'] == ['fixture-curator']


def test_text_report_prints_the_same_numbers(capsys):
    assert curation_timer.main(['--report', '--ledger', FIXTURE]) == 0
    out = capsys.readouterr().out
    assert 'median          49.00 min' in out
    assert 'Q1 43.25  Q3 60.50' in out
    assert 'copilot on      n 2  median 43.25 min' in out
    assert 'copilot off     n 1  median 72.00 min' in out
    assert 'on/off ratio    0.6007  (copilot faster by 39.9%)' in out
    assert 'WARNING' not in out and 'STOPPING RULE' not in out


def test_a_changed_record_changes_the_numbers(tmp_path, capsys):
    # The guard the verify asks for, from the other side: move one stop by a minute and every
    # one of the three hand-computed figures that depends on it must move too.
    lines = open(FIXTURE, encoding='utf-8').read().splitlines()
    r = json.loads(lines[2])
    r['stop'], r['minutes'] = '2026-01-05T13:50:00Z', 50.0
    lines[2] = json.dumps(r)
    edited = tmp_path / 'edited.jsonl'
    edited.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    rep = report_json(edited, capsys)
    assert rep['median'] != MEDIAN and rep['q1'] != Q1 and rep['q3'] != Q3
    assert rep['copilot']['on']['median'] != ON_MEDIAN


def test_a_timed_entry_appends_one_record(tmp_path, capsys):
    ledger, state = tmp_path / 'rate.jsonl', tmp_path / 'timer.json'
    t0 = curation_timer.parse('2026-02-01T08:00:00Z')
    curation_timer.start('casp', 'curator-a', False, state=str(state), now=t0)
    rec = curation_timer.stop(ledger=str(ledger), state=str(state),
                              now=curation_timer.parse('2026-02-01T09:05:00Z'))
    assert rec['minutes'] == 65.0 and not state.exists()
    assert len(ledger.read_text(encoding='utf-8').splitlines()) == 1
    assert curation_timer.main(['--report', '--ledger', str(ledger)]) == 0
    out = capsys.readouterr().out
    assert 'median          65.00 min' in out
    assert 'STOPPING RULE (a)' in out  # one 65-minute entry is above the 60-minute trigger
    assert 'on/off ratio    - (one arm is empty)' in out


def test_start_refuses_a_second_open_timer_and_stop_needs_one(tmp_path):
    state, ledger = str(tmp_path / 'timer.json'), str(tmp_path / 'rate.jsonl')
    with pytest.raises(curation_timer.LedgerError):
        curation_timer.stop(ledger=ledger, state=state)
    curation_timer.start('a', 'c', True, state=state)
    with pytest.raises(curation_timer.LedgerError):
        curation_timer.start('b', 'c', True, state=state)
    curation_timer.cancel(state=state)
    assert not os.path.exists(ledger)


def test_minutes_that_disagree_with_the_timestamps_are_rejected(tmp_path):
    bad = tmp_path / 'bad.jsonl'
    r = json.loads(open(FIXTURE, encoding='utf-8').readline())
    r['minutes'] = 30.0  # the stamps say 72
    bad.write_text(json.dumps(r) + '\n', encoding='utf-8')
    with pytest.raises(curation_timer.LedgerError, match='disagrees'):
        curation_timer.load(str(bad))


def test_an_empty_ledger_exits_2(tmp_path, capsys):
    empty = tmp_path / 'empty.jsonl'
    empty.write_text('', encoding='utf-8')
    assert curation_timer.main(['--report', '--ledger', str(empty)]) == 2


def test_the_committed_live_ledger_parses():
    curation_timer.load(os.path.join(ROOT, 'metrics', 'curation-rate.jsonl'))


def test_self_test_passes(capsys):
    assert curation_timer.main(['--self-test']) == 0
