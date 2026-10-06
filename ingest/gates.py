"""The ingest gates (07 S8): unit, metric definition and sanity band (P3-S2-T06); verification ceiling,
provenance and the derived-field guard (P3-S4-T02, at the end of this module).

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOLERANCE = 0.02            # 07 S8, as a fraction of the metric's span
SIGMAS = 5.0                # 07 S8
MIN_HISTORY = 5             # claims needed before the sigma band means anything


class GateError(Exception):
    """A hard fail: the run commits nothing for this record (07 S8, "a red gate means no commit")."""

    def __init__(self, gate: str, message: str):
        super().__init__('%s: %s' % (gate, message))
        self.gate = gate


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


# ---- the verification ceiling (P3-S4-T02) -----------------------------------------------------------------
#
# 07 S8: "No ingested record above independent-reproduction (rank 3). Rank 3 additionally requires a reachable
# artifact_url." Two locks, so that a future adapter cannot promote itself: the rung must be one
# taxonomy/verification.yaml lets a machine assign (ingest/verification.py), AND its rank must be at most
# CEILING_RANK whatever that file says -- a taxonomy edit marking rung 4 machine-assignable does not lift it.

CEILING_RANK = 3


def ranks(root: str = ROOT) -> dict[str, int]:
    from schema.taxonomy import read_yaml
    return {r['id']: r['rank'] for r in read_yaml(os.path.join(root, 'taxonomy', 'verification.yaml'))['rungs']}


def verification_ceiling(draft: dict, transcript=None, root: str = ROOT) -> None:
    """GateError unless the draft's verification is machine-assignable, at most rank 3, and -- at rank 3 --
    backed by a transcript that was reached (`transcript`: ingest.verification.Transcript) at the draft's
    artifact_url."""
    from ingest.verification import check_machine_claim
    rung = draft.get('verification')                                    # get-default: absent is refused below
    rank = ranks(root).get(rung)                                        # get-default: an unknown rung has no rank
    if rank is None:
        raise GateError('verification-ceiling', 'verification %r is not a rung of taxonomy/verification.yaml' % rung)
    if rank > CEILING_RANK:
        raise GateError('verification-ceiling', '%s is rank %d; no ingested record goes above rank %d '
                        '(independent-reproduction), whatever the taxonomy marks machine-assignable' % (rung, rank, CEILING_RANK))
    try:
        check_machine_claim(rung, transcript, root)
    except ValueError as e:
        raise GateError('verification-ceiling', str(e)) from None
    if rank == CEILING_RANK and transcript.url != draft.get('artifact_url'):    # get-default: absent is a mismatch
        raise GateError('verification-ceiling', 'the reached transcript %s is not the artifact_url %r of the draft'
                        % (transcript.url, draft.get('artifact_url')))        # get-default: as above


# ---- provenance (P3-S4-T02) -------------------------------------------------------------------------------
#
# 07 S8: "Every record carries a complete ingestion block ... A record without provenance must never merge."
# The keys 07 S8 lists, plus last_seen_upstream (04 S9: how an upstream deletion becomes visible). Each must be
# PRESENT; source_record_id may be null only for a source the adapter declares full-replace (04 S9), and
# otherwise must be a content key, never a row ordinal (schema.claim.check_source_record_id).

PROVENANCE_KEYS = ('batch', 'source_adapter', 'adapter_version', 'source_record_id', 'source_url', 'source_licence',
                   'licence_class', 'source_attribution', 'ingested_at', 'review_state', 'field_provenance',
                   'last_seen_upstream')


def provenance(draft: dict, full_replace: bool = False) -> None:
    """GateError unless the draft carries a complete, valid ingestion block."""
    from pydantic import ValidationError

    from schema.claim import Ingestion
    block = draft.get('ingestion')                                      # get-default: absent is refused below
    if not isinstance(block, dict):
        raise GateError('provenance', 'the draft has no ingestion block; a record without provenance never merges')
    missing = [k for k in PROVENANCE_KEYS if k not in block]
    if missing:
        raise GateError('provenance', 'the ingestion block lacks %s' % ', '.join(missing))
    if block['source_record_id'] is None and not full_replace:
        raise GateError('provenance', 'source_record_id is null, which only a full-replace source may declare (04 S9)')
    try:
        Ingestion.model_validate(block)
    except ValidationError as e:
        raise GateError('provenance', ' '.join(str(e).split())) from None


# ---- the derived-field guard (P3-S4-T02) ------------------------------------------------------------------
#
# 07 S8: "No draft contains comparability_key, condition_completeness, headroom or any other build-derived
# field." The others are the fields 04 marks derived and the models compute: a value the build owns, written
# by an adapter, is a value that rots.

DERIVED_FIELDS = frozenset({
    'comparability_key', 'condition_completeness', 'headroom', 'headroom_consumed',      # 07 S8 by name
    'curation_confidence', 'maintenance_status', 'inspect_evals_available', 'stewardship',  # 04: derived
    'higher_is_better',                                                                   # Metric, computed
})


def derived_fields(doc, path: str = '') -> list[str]:
    """Every dotted path in `doc` whose key is a derived field, at any depth."""
    out = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            here = '%s.%s' % (path, k) if path else str(k)
            if k in DERIVED_FIELDS:
                out.append(here)
            out += derived_fields(v, here)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            out += derived_fields(v, '%s[%d]' % (path, i))
    return out


def derived_field_guard(draft) -> None:
    hits = derived_fields(draft)
    if hits:
        raise GateError('derived-field', 'the draft writes build-derived field(s) %s; only the build computes them'
                        % ', '.join(hits))
