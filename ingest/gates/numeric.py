"""The numeric gates (07 S8): unit guard, metric definition and sanity band (P3-S2-T06). Moved from
ingest/gates.py into the gates package by P5-S2-T05; nothing in them changed.

The first three stand between an upstream number and a wrong claim:

    unit guard          "A claim whose mapping stanza has no explicit `scale` is refused. There is no default."
                        HARD FAIL (GateError). ingest/mappings/schema.py already refuses to load such a stanza;
                        this gate is where an ingest run meets that refusal, and also refuses a claim with no
                        stanza at all.
    metric definition   "The referenced Metric declares either a range, or unbounded: true with a value_type,
                        or value_type: qualitative. A numeric claim against a metric with none of the three is
                        refused." HARD FAIL: "Elo, dollars and minutes ... must be modelled before they are
                        ingested, not discovered at 2am."
    sanity band         "After scaling, value lies within [chance_baseline - 0.02, score_ceiling + 0.02] where
                        both are known; otherwise within Metric.range; for Metric.unbounded: true within +/-5
                        sigma of the metric's existing claim distribution." The ROW is rejected as
                        Unresolved(reason="unparseable"): "the gate that catches the dollars-in-a-0-1-field
                        class of bug".

Two readings of 07 S8, stated because the gate depends on them:

  - The 0.02 tolerance is written for a 0-1 metric. It is applied as 2% of the metric's span (range.max -
    range.min, else 1.0), which is exactly 0.02 on a 0-1 metric and 2 points on a 0-100 one; an absolute 0.02
    would make ForecastBench's 0-100 index reject a forecaster 0.03 points below chance.
  - The +/-5 sigma band needs a distribution. Below MIN_HISTORY claims it is not evaluated, and the result says
    so (`basis` is 'not-evaluated'), rather than rejecting the first claims an unbounded metric ever gets. An
    unbounded metric with a declared lower bound (a currency that cannot go below some floor) is held to that
    bound as well as to the sigma band.
"""
from __future__ import annotations

import glob
import math
import os
from dataclasses import dataclass

from ingest.adapters.base import Unresolved
from ingest.gates._common import ROOT, GateError

TOLERANCE = 0.02            # 07 S8, as a fraction of the metric's span
SIGMAS = 5.0                # 07 S8
MIN_HISTORY = 5             # claims needed before the sigma band means anything


# ---- the unit guard ---------------------------------------------------------------------------------------

def unit_guard(adapter: str, source_key: str, root: str | None = None):
    """The stanza for a claim's file, which by construction carries an explicit scale; GateError otherwise."""
    from ingest.mappings.schema import MAPPINGS, MappingError, load_mapping
    try:
        stanza = load_mapping(adapter, source_key, root or MAPPINGS)
    except MappingError as e:
        raise GateError('unit-guard', 'the stanza does not load, so its scale is not known: %s' % e) from None
    if stanza is None:
        raise GateError('unit-guard', '%s has no mapping stanza, so no scale: a claim is never drafted from it'
                        % source_key)
    return stanza


# ---- the metric definition --------------------------------------------------------------------------------

def has_range(metric) -> bool:
    return metric.range is not None and (metric.range.min is not None or metric.range.max is not None)


def metric_definition(metric) -> None:
    """GateError unless the metric declares a range, or is unbounded (its value_type is required by the
    model), or is qualitative."""
    if has_range(metric) or metric.unbounded or metric.value_type == 'qualitative':
        return
    raise GateError('metric-definition', '%s declares no range, is not unbounded and is not qualitative, so a '
                    'number against it cannot be checked; model the metric first (07 S8)' % metric.id)


# ---- the sanity band --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Band:
    lo: float
    hi: float
    basis: str              # anchors | range | sigma | range+sigma | not-evaluated

    def holds(self, value: float) -> bool:
        return self.basis == 'not-evaluated' or self.lo <= value <= self.hi


def span(metric) -> float:
    r = metric.range
    if r is not None and r.min is not None and r.max is not None:
        return r.max - r.min
    return 1.0


def band(metric, history=()) -> Band:
    """The interval a scaled value must lie in, by 07 S8's order: anchors, else range, else sigma."""
    tol = TOLERANCE * span(metric)
    if metric.chance_baseline is not None and metric.score_ceiling is not None:
        lo, hi = sorted((metric.chance_baseline, metric.score_ceiling))      # a lower-is-better ceiling is below
        return Band(lo - tol, hi + tol, 'anchors')
    if not metric.unbounded and has_range(metric):
        r = metric.range
        return Band(-math.inf if r.min is None else r.min, math.inf if r.max is None else r.max, 'range')
    if metric.unbounded:
        lo = metric.range.min if has_range(metric) and metric.range.min is not None else -math.inf
        values = [float(v) for v in history]
        if len(values) < MIN_HISTORY:
            if lo > -math.inf:
                return Band(lo, math.inf, 'range')
            return Band(-math.inf, math.inf, 'not-evaluated')
        mean = sum(values) / len(values)
        sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        return Band(max(lo, mean - SIGMAS * sd), mean + SIGMAS * sd, 'range+sigma' if lo > -math.inf else 'sigma')
    return Band(-math.inf, math.inf, 'not-evaluated')                       # qualitative: no number to band


def sanity_band(value: float, metric, source_key: str, history=(), field: str = 'value') -> Unresolved | None:
    """None when the scaled value is plausible; else the row's Unresolved(reason='unparseable')."""
    b = band(metric, history)
    if b.holds(value):
        return None
    return Unresolved(
        source_key=source_key, field=field, observed=repr(value), reason='unparseable',
        human_task=('%r is outside %s\'s plausible band [%s, %s] (%s; 07 S8). The usual cause is a unit: a '
                    'percentage at scale 1.0, dollars or an Elo in a 0-1 metric. Check the stanza\'s scale and '
                    'metric_ref against the file, then re-run.' % (value, metric.id, _show(b.lo), _show(b.hi), b.basis)))


def _show(x: float) -> str:
    return '%g' % x if math.isfinite(x) else ('-inf' if x < 0 else 'inf')


# ---- one claim through all three ----------------------------------------------------------------------------

def check(raw: float, adapter: str, source_key: str, metric, history=(), root: str | None = None):
    """(scaled value, None) for a claim that passes; (None, Unresolved) for a row the sanity band rejects.
    The unit guard and the metric definition raise GateError: the record is not drafted at all."""
    stanza = unit_guard(adapter, source_key, root)
    metric_definition(metric)
    value = raw * stanza.scale
    u = sanity_band(value, metric, source_key, history)
    return (None, u) if u else (value, None)


def history(metric_id: str, root: str = ROOT) -> list[float]:
    """The numeric values of the curated claims against a metric: the distribution the sigma band reads."""
    from schema.taxonomy import read_yaml
    out = []
    for p in glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True):
        d = read_yaml(p)
        if isinstance(d, dict) and d.get('metric') == metric_id and isinstance(d.get('value'), (int, float)):  # get-default: a claim without these is not this metric's
            out.append(float(d['value']))
    return out
