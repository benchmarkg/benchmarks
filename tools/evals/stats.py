"""Wilson score intervals and the bar verdicts (P6-S3-T09; 11-ai-features.md S7 "Statistical power").

11 S7 asks three things of every published number, all mechanical: "Every published metric carries its Wilson
interval, not just its point estimate"; "A bar is only failed when the upper bound falls below it. A point estimate
below the bar with an interval straddling it is reported as inconclusive"; and the hard zeros "are exempt from this
reasoning because they are not estimates of a rate".

The interval, written out here rather than imported, because the harness adds no dependency. For s successes in n
trials, p = s / n and z the standard normal quantile at 0.975 (Z95, to double precision, not 1.96):

    centre = (p + z^2 / 2n) / (1 + z^2 / n)
    half   = z * sqrt(p (1 - p) / n + z^2 / 4n^2) / (1 + z^2 / n)
    [lo, hi] = [centre - half, centre + half], clipped to [0, 1] against rounding only

Unlike the normal (Wald) interval it is never zero-width at 0 or n successes and never leaves [0, 1]. A metric that is
not a count of successes -- nDCG@10, a mean of per-query values in [0, 1], and macro-F1 -- takes the same formula with
s = value x n over the n items it averages: the convention 11 S7 uses itself ("At n=40, one facet_translation item is
2.5 percentage points"). That is an approximation and every results file says so beside the interval: such a metric is
not a binomial proportion, and its true sampling spread may be wider or narrower.

Verdicts (`verdict`). A rate bar is `>= b` (a rate that should be high) or `<= b` (one that should be low):

    >= b   fail when hi < b;  pass when lo >= b;  otherwise inconclusive
    <= b   fail when lo > b;  pass when hi <= b;  otherwise inconclusive

The ledger's words are the rule: "Fail a rate bar only when the interval's upper bound falls below it; report a
straddling interval as inconclusive." Any interval that straddles the bar is inconclusive, on whichever side the point
estimate falls, and `point_meets_bar` says which. A consequence worth stating: at golden set v0's sizes no rate bar can
pass. 20 of 20 abstentions give [0.839, 1.0] against 0.95, and 12 of 12 facet_translation items [0.758, 1.0] against
0.85. Those gates are smoke tests until the set grows, as 11 S7 says of facet_translation below n = 200.

A hard zero (`== 0` or `== 1`, kind ASSERT) is no estimate: one occurrence fails it at any n and none passes it. Its
interval is still published (every published metric carries one) and decides nothing.

11 S7's own figures against the formula. At n = 200 its "roughly [0.79, 0.89]" for 0.85 is this interval
([0.794, 0.893]). At n = 40 and n = 20 they are not: 34 of 40 gives [0.709, 0.929], not [0.69, 0.91], and 19 of 20
gives [0.764, 0.991], not [0.72, 0.95]. And 11 S7's "two misses fail it" for abstention at n = 20 does not follow from
its own rule: 18 of 20 gives [0.699, 0.972], which straddles 0.95 and is inconclusive; three misses (17 of 20, upper
bound 0.948) are the first that fail. This module follows the rule, not the prose; tests/evals/test_eval_harness.py
holds every figure in this paragraph.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Z95 = 1.959963984540054          # statistics.NormalDist().inv_cdf(0.975), to double precision
METHOD = 'Wilson score interval, 95%% (z = %.6f), computed by hand (tools/evals/stats.py)' % Z95
APPROXIMATION = ('a mean of per-item values in [0, 1] (nDCG@10, macro-F1) takes the formula with s = value x n: an '
                 'approximation, since it is not a binomial proportion (11 S7 counts it per item the same way)')

AT_LEAST, AT_MOST, ASSERT = '>=', '<=', '=='
PASS, FAIL, INCONCLUSIVE = 'pass', 'fail', 'inconclusive'


def wilson(successes: float, n: int, z: float = Z95) -> tuple[float, float]:
    """The Wilson score interval for `successes` of `n` (module docstring). Raises ValueError for n < 1 or
    successes outside [0, n]."""
    if n < 1:
        raise ValueError('a Wilson interval needs n >= 1, not %r' % n)
    if not 0 <= successes <= n:
        raise ValueError('successes %r is outside [0, %d]' % (successes, n))
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True)
class Bar:
    """One pass bar of 11 S7's table: `kind` AT_LEAST, AT_MOST or ASSERT (a hard zero), against `value`."""
    kind: str
    value: float

    def text(self) -> str:
        return '%s %.3f' % (self.kind, self.value)


def verdict(value: float, interval: tuple[float, float], bar: Bar) -> str:
    """pass, fail or inconclusive (module docstring)."""
    lo, hi = interval
    if bar.kind == ASSERT:
        return PASS if value == bar.value else FAIL
    if bar.kind == AT_LEAST:
        return FAIL if hi < bar.value else PASS if lo >= bar.value else INCONCLUSIVE
    if bar.kind == AT_MOST:
        return FAIL if lo > bar.value else PASS if hi <= bar.value else INCONCLUSIVE
    raise ValueError('unknown bar kind %r' % bar.kind)


def meets(value: float, bar: Bar) -> bool:
    """Whether the point estimate alone is on the bar's right side."""
    return value >= bar.value if bar.kind == AT_LEAST else value <= bar.value if bar.kind == AT_MOST \
        else value == bar.value


def rate(successes: float, n: int, bar: Bar | None, per_item: bool = False) -> dict:
    """One published rate: its value, s and n, its interval, and against a bar the verdict. `per_item` marks a
    mean of per-item values (APPROXIMATION) rather than a count."""
    lo, hi = wilson(successes, n)
    value = successes / n
    out = {'value': round(value, 4), 'successes': round(successes, 4), 'n': n,
           'interval': [round(lo, 4), round(hi, 4)]}
    if per_item:
        out['interval_note'] = APPROXIMATION
    if bar is not None:
        out['bar'] = bar.text()
        out['verdict'] = verdict(value, (lo, hi), bar)
        out['point_meets_bar'] = meets(value, bar)
        if bar.kind == ASSERT:
            out['interval_note'] = 'a hard zero: one occurrence fails it at any n, and the interval decides nothing'
    return out
