"""Adaptive yield bands and the zero-yield guard (P5-S4-T02; 07 S9).

The verify: `pytest tests/ingest/test_bands.py`. Done when "Eight successful runs move the band off its
seed, and a zero-yield run against a non-zero median alerts regardless of band width". Both halves are
asserted on the band arithmetic and again through the shared runner, with the state file and run log on
disk. The failure case beside them is the guard silencing itself: if zero-yield runs entered the history,
five of them would drag the trailing median to 0 and the sixth would pass unnoticed.
"""
import json

import pytest

from ingest.adapters import epoch, hf_hub
from ingest.adapters.base import Adapter, Candidate
from ingest.runner import bands as B
from ingest.runner import report as R
from ingest.runner import state as S

SEED = (41, 162)              # Epoch's seed band (07 S9's table)


# ---- the band ------------------------------------------------------------------------------------------------

def test_no_history_is_the_seed_band():
    assert B.band([], SEED) == B.Band(41, 162, 'seed')


def test_fewer_than_eight_runs_never_narrow_the_band_below_its_seed():
    b = B.band([81, 81, 80], SEED)                            # median 81: [40.5, 162] -- the seed is wider at 41
    assert (b.lo, b.hi, b.basis) == (40.5, 162, 'seed+median')
    b = B.band([300] * 7, SEED)                               # a grown source widens the band upward at once
    assert (b.lo, b.hi, b.basis) == (41, 600, 'seed+median')


def test_eight_successful_runs_move_the_band_off_its_seed():
    """The done_when's first half: from the eighth run the data alone sets the band."""
    b = B.band([300] * 8, SEED)
    assert (b.lo, b.hi, b.basis) == (150, 600, 'adaptive')
    assert not b.holds(100) and B.band([300] * 7, SEED).holds(100)    # the seed no longer shelters 100


def test_the_median_is_of_the_last_eight_only():
    assert B.band([10_000] * 5 + [100] * 8, SEED) == B.Band(50, 200, 'adaptive')


@pytest.mark.parametrize('value, status', [(81, 'in-band'), (41, 'in-band'), (162, 'in-band'),
                                           (40, 'out-of-band'), (400, 'out-of-band')])
def test_a_yield_inside_or_outside_the_band(value, status):
    assert B.check(value, [81] * 8, (0, 10_000)).status == status   # adaptive: [40.5, 162]


# ---- the zero guard ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize('history, seed', [
    ([81] * 8, SEED),            # adaptive band [40.5, 162]
    ([81] * 3, (0, 5_000)),      # a band whose floor is 0 holds zero -- the guard does not care
    ([1], (0, 10)),              # a median of 1 is still non-zero
])
def test_zero_against_a_non_zero_median_alerts_regardless_of_band_width(history, seed):
    """The done_when's second half."""
    v = B.check(0, history, seed)
    assert v.status == 'zero-yield' and v.alert and 'ZERO YIELD' in v.note()


def test_zero_with_no_history_is_judged_by_the_seed_alone():
    assert B.check(0, [], (0, 10)).status == 'in-band'           # a source that may legitimately be empty
    assert B.check(0, [], SEED).status == 'out-of-band'          # below the seed, but not the guard's case


def test_a_zero_yield_run_never_enters_the_history():
    state = {'yield_history': [81] * 8}
    B.record(state, B.check(0, state['yield_history'], SEED))
    assert state['yield_history'] == [81] * 8
    B.record(state, B.check(400, state['yield_history'], SEED))   # out of band, but recorded: the band adapts
    assert state['yield_history'] == [81] * 7 + [400]


def test_the_failure_case_the_guard_would_silence_itself_if_zeros_were_recorded():
    """Ten days of zeros after eight healthy runs. Recording only what record() admits, every day alerts;
    appending every yield naively, the median of the last eight hits 0 on day 5 and day 6 passes clean."""
    kept, naive = {'yield_history': [81] * 8}, [81] * 8
    kept_alerts, naive_alerts = [], []
    for _ in range(10):
        v = B.check(0, kept['yield_history'], SEED)
        B.record(kept, v)
        kept_alerts.append(v.alert)
        w = B.check(0, naive, SEED)
        naive.append(0)
        naive_alerts.append(w.alert)
    assert all(kept_alerts)
    assert naive_alerts == [True] * 5 + [False] * 5         # day 5 appends the fifth zero; day 6 is silent


# ---- the canary (07 S9 mechanism 4) ------------------------------------------------------------------------------

def test_the_canary_opens_on_two_consecutive_out_of_band_runs_not_one():
    hist = [81] * 8
    one = [B.check(81, hist, SEED), B.check(400, hist, SEED)]
    two = one + [B.check(500, hist, SEED)]
    assert B.canary(one) == []
    assert B.canary(two) == ['yield outside its band for 2 consecutive runs: 400, 500']


def test_the_canary_opens_at_once_on_a_zero_yield():
    assert 'ZERO YIELD' in B.canary([B.check(0, [81] * 8, SEED)])[0]
    assert B.canary([]) == []


# ---- through the shared runner, with the state file and the run log ---------------------------------------------

class Source(Adapter):
    name, version, licence, licence_class = 'source', '0.0.1', 'CC0-1.0', 'permissive-attribution'
    attribution, expected_yield = 'Source', (2, 8)

    def __init__(self, n):
        self.n = n

    def discover(self, state):
        for i in range(self.n):
            yield Candidate('k:%d' % i, 'claim', None)

    def fetch(self, c, state):
        return None                                           # unchanged: yield counts candidates seen

    def normalise(self, p, resolver):
        return [], []


def run(tmp_path, n, day):
    from datetime import datetime, timedelta, timezone
    path = str(tmp_path / 'state.json')
    when = datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(days=day)
    return S.run(Source(n), S.load(path, S.new('source', '0.0.1')), path, now=lambda: when, log_root=str(tmp_path))


def test_eight_runs_through_the_runner_move_the_band_and_persist_the_history(tmp_path):
    reports = [run(tmp_path, 20, d) for d in range(9)]
    assert reports[0]['yield']['basis'] == 'seed' and reports[0]['yield']['status'] == 'out-of-band'   # 20 > 8
    assert reports[7]['yield']['basis'] == 'seed+median'
    assert reports[8]['yield'] == {'value': 20, 'band': [10.0, 40.0], 'basis': 'adaptive', 'median': 20,
                                   'status': 'in-band'}
    assert json.load(open(tmp_path / 'state.json', encoding='utf-8'))['yield_history'] == [20] * 8


def test_a_zero_yield_run_through_the_runner_alerts_logs_and_leaves_the_history(tmp_path):
    for d in range(3):
        run(tmp_path, 5, d)
    out = run(tmp_path, 0, 3)
    assert out['status'] == 'no-change' and out['alerts'] == ['zero-yield']
    assert json.load(open(tmp_path / 'state.json', encoding='utf-8'))['yield_history'] == [5, 5, 5]
    log = R.history('source', str(tmp_path))[-1]
    assert any('ZERO YIELD' in n for n in log.notes)                # the committed record says so too


def test_a_partial_run_records_no_yield(tmp_path):
    from datetime import datetime, timezone
    path = str(tmp_path / 'state.json')
    clock = iter(range(100)).__next__
    out = S.run(Source(50), S.new('source', '0.0.1'), path, max_runtime=10, clock=clock,
                now=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert out['status'] == 'partial' and out['yield'] is None
    assert json.load(open(path, encoding='utf-8'))['yield_history'] == []


def test_the_real_adapters_seed_bands_are_bands():
    for a in (epoch.Epoch, hf_hub.HfHub):
        b = B.band([], a.expected_yield)
        assert b.basis == 'seed' and 0 < b.lo < b.hi
