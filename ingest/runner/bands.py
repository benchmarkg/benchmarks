"""Adaptive yield bands and the zero-yield guard (P5-S4-T02; 07 S9).

07 S9 names the failure this exists for: "the arXiv adapter has silently returned zero results for three
weeks. Not a crash -- a clean exit, a green checkmark, and nothing in the PR queue." Zero results is not an
error in any HTTP sense; it is only visible as a yield anomaly. So every finished run's yield -- the
candidates it saw -- is checked against a band, by 07 S9's rule:

    band = trailing_median(last 8 successful runs) x [0.5, 2.0]
           floored by the hand-written seed band until 8 runs exist
    plus an absolute guard: yield == 0 while trailing_median > 0  ->  alert immediately, always

How "floored by the seed band" is read: until eight successful runs exist, the band is never narrower than
the seed the adapter's author wrote (Adapter.expected_yield) -- it is the wider of the seed and the median
band -- because three runs are too few to trust a median over the author's memory of normal. From the eighth
run on, the data alone sets it ("after eight runs the data takes over"), so a source that has honestly grown
past its seed stops alerting instead of being muted.

The guard is checked before the band and does not depend on it: a seed band whose floor is 0, or a band so
wide it holds 0, still alerts on a zero against a non-zero median.

What enters the history (07 S4's yield_history, at most 8 entries, in the state file). Every successful,
complete run's yield -- including one outside its band, because that is how the band adapts -- except a
run the zero guard alerted on. Were zeros recorded, five days of them would make the trailing median of
eight zero, and the guard, reading that median, would fall silent on the sixth day: the three-week silence
07 S9 exists to catch, reproduced by its own monitor. A source that really has emptied keeps alerting until
a person looks, which is the point.

The canary (07 S9 mechanism 4) opens an issue when a yield "has been outside the band for two consecutive
runs, or is zero against a non-zero median". `canary()` decides that from the run log (ingest/runs/).
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

TRAILING = 8                  # 07 S9: "last 8 successful runs"
LOW, HIGH = 0.5, 2.0          # 07 S9: "x [0.5, 2.0]"
CONSECUTIVE = 2               # 07 S9: "outside the band for two consecutive runs"


@dataclass(frozen=True)
class Band:
    lo: float
    hi: float
    basis: str                # seed | seed+median | adaptive

    def holds(self, value: int) -> bool:
        return self.lo <= value <= self.hi


@dataclass(frozen=True)
class YieldCheck:
    value: int
    band: Band
    median: float | None      # the trailing median the band and guard read, None with no history
    status: str               # in-band | out-of-band | zero-yield

    @property
    def alert(self) -> bool:
        """The zero guard alerts at once; an out-of-band run alerts only on its second in a row (canary())."""
        return self.status == 'zero-yield'

    @property
    def recorded(self) -> bool:
        """Whether this run's yield enters yield_history (see the module docstring)."""
        return self.status != 'zero-yield'

    def as_dict(self) -> dict:
        return {'value': self.value, 'band': [self.band.lo, self.band.hi], 'basis': self.band.basis,
                'median': self.median, 'status': self.status}

    def note(self) -> str | None:
        if self.status == 'zero-yield':
            return ('ZERO YIELD: 0 candidates against a trailing median of %g; this is how an adapter dies quietly '
                    '(07 S9). Alerting now, whatever the band.' % self.median)
        if self.status == 'out-of-band':
            return ('yield %d is outside the band [%g, %g] (%s); a second run outside it opens adapter-broken (07 S9)'
                    % (self.value, self.band.lo, self.band.hi, self.band.basis))
        return None


def band(history, seed: tuple[int, int]) -> Band:
    """07 S9's band from the yields of the last successful runs (oldest first) and the adapter's seed."""
    recent = list(history)[-TRAILING:]
    if not recent:
        return Band(float(seed[0]), float(seed[1]), 'seed')
    m = median(recent)
    lo, hi = LOW * m, HIGH * m
    if len(recent) >= TRAILING:
        return Band(lo, hi, 'adaptive')
    return Band(min(float(seed[0]), lo), max(float(seed[1]), hi), 'seed+median')


def check(value: int, history, seed: tuple[int, int]) -> YieldCheck:
    """One finished run's yield against the band its history and seed give, the zero guard first."""
    recent = list(history)[-TRAILING:]
    m = median(recent) if recent else None
    b = band(recent, seed)
    if value == 0 and m:
        return YieldCheck(value, b, m, 'zero-yield')
    return YieldCheck(value, b, m, 'in-band' if b.holds(value) else 'out-of-band')


def record(state: dict, verdict: YieldCheck) -> None:
    """Append a run's yield to the state's yield_history, kept to the last TRAILING, unless the zero guard
    alerted on it."""
    if verdict.recorded:
        state['yield_history'] = (list(state['yield_history']) + [verdict.value])[-TRAILING:]


def canary(checks) -> list[str]:
    """07 S9 mechanism 4, for one adapter's run checks in order: why to open adapter-broken, or []."""
    checks = list(checks)
    if not checks:
        return []
    out = []
    if checks[-1].status == 'zero-yield':
        out.append(checks[-1].note())
    tail = checks[-CONSECUTIVE:]
    if len(tail) == CONSECUTIVE and all(c.status == 'out-of-band' for c in tail):
        out.append('yield outside its band for %d consecutive runs: %s'
                   % (CONSECUTIVE, ', '.join(str(c.value) for c in tail)))
    return out
