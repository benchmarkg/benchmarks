"""Metric (P0-S4-T07; 04-data-model.md S6, 12-analytics-and-trends.md S3).

A separate entity because metrics are shared across benchmarks and routinely misunderstood. One file
per metric at data/metrics/{id}.yaml.

The rules this model carries:

  - `optimum` (max | min | zero | target) replaces "higher is better". `higher_is_better` is derived
    from it, so it is computed and may not be hand-written (04 S1). `optimum: target` names its
    target in `optimum_target`, which 04 S6 leaves unnamed.
  - `unbounded` and `requires_pool` exist for Elo. An unbounded metric has no `range.max` and is never
    `headroom_computable`; a pool-relative one is not either.
  - `headroom_consumed()` is 12 S3.1's formula, unclamped, and it REFUSES rather than guesses: an
    unbounded metric, a pool-relative one, a vector, a zero-optimum pair or a metric marked
    `headroom_computable: false` raises HeadroomNotComputable carrying 12 S3.4's null reason. The
    last case, and an ordinal, categorical or qualitative metric, has no reason in 12 S3.4's table and
    carries `metric-not-headroom-computable`.
  - Epoch's two anchors (04 S6): its `random_baseline` column lands in `chance_baseline`, the name 04
    and 07 S3 use for the same number, and its `score_ceiling` in `score_ceiling`. A score ceiling is
    a MEASUREMENT ceiling, not a human baseline, and the two never share a field.
  - `must_report_with` names metrics that may never be shown without this one, and never itself.
"""
from __future__ import annotations

import os
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, model_validator

from schema.system import SourceId, Text
from schema.taxonomy import load_taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))

DomainLeaf = Literal[tuple(t.id for t in _MODELS['domains.yaml'].terms  # type: ignore[valid-type]
                           if t.parent and t.status != 'retired')]
MetricId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]
ValueType = Literal['ratio', 'count', 'duration', 'currency', 'elo', 'ordinal', 'categorical', 'vector', 'qualitative']
Optimum = Literal['max', 'min', 'zero', 'target']


class HeadroomNotComputable(ValueError):
    """Raised instead of a number. `reason` is one of 12 S3.4's machine-readable null reasons."""

    def __init__(self, metric: str, reason: str):
        self.reason = reason
        super().__init__('%s: headroom is not computable (%s)' % (metric, reason))


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Range(Closed):
    min: float | None = None
    max: float | None = None

    @model_validator(mode='after')
    def _order(self):
        if self.min is not None and self.max is not None and self.min >= self.max:
            raise ValueError('range min %s is not below max %s' % (self.min, self.max))
        return self


class Metric(Closed):
    id: MetricId
    name: Text
    full_name: Text | None = None
    definition: Text
    formula_reference: Url | None = None
    value_type: ValueType
    range: Range | None = None
    unbounded: bool = False
    optimum: Optimum
    optimum_target: float | None = None
    chance_baseline: float | None = None       # Epoch's `random_baseline`
    score_ceiling: float | None = None         # Epoch's `score_ceiling`: a measurement ceiling
    normalization_anchor: Text | None = None
    aggregation: Text | None = None
    units: Text | None = None
    requires_pool: bool = False
    headroom_computable: bool = True
    must_report_with: list[MetricId] = Field(default_factory=list)
    domains: list[DomainLeaf] = Field(default_factory=list)
    pitfalls: Text | None = None
    sources: list[SourceId] = Field(min_length=1)

    @computed_field
    @property
    def higher_is_better(self) -> bool | None:
        """Derived from `optimum` (04 S6); None where neither direction is better."""
        return {'max': True, 'min': False}.get(self.optimum)

    @model_validator(mode='after')
    def _bounds(self):
        if self.unbounded and self.range is not None and self.range.max is not None:
            raise ValueError('%s: an unbounded metric has no range.max' % self.id)
        if self.unbounded and self.headroom_computable:
            raise ValueError('%s: an unbounded metric is never headroom_computable (12 S3.4)' % self.id)
        if self.requires_pool and self.headroom_computable:
            raise ValueError('%s: a pool-relative metric is never headroom_computable (12 S3.4)' % self.id)
        if (self.optimum == 'target') != (self.optimum_target is not None):
            raise ValueError('%s: optimum_target is given exactly when optimum is target' % self.id)
        if self.range is not None:
            for name in ('chance_baseline', 'score_ceiling'):
                v = getattr(self, name)
                if v is not None and not ((self.range.min is None or v >= self.range.min)
                                          and (self.range.max is None or v <= self.range.max)):
                    raise ValueError('%s: %s %s lies outside the range' % (self.id, name, v))
        if self.id in self.must_report_with:
            raise ValueError('%s: must_report_with names the metric itself' % self.id)
        return self

    def headroom_null_reason(self) -> str | None:
        """12 S3.4's reason when this metric can never carry headroom, else None."""
        if self.unbounded:
            return 'unbounded-metric'
        if self.requires_pool or self.value_type == 'elo':
            return 'relative-rating-only'
        if self.value_type == 'vector':
            return 'vector-valued-by-design'
        if self.optimum == 'zero':
            return 'lower-is-better-optimum-zero'
        if not self.headroom_computable or self.value_type in ('ordinal', 'categorical', 'qualitative'):
            return 'metric-not-headroom-computable'      # ours: 12 S3.4 lists no reason for this case
        return None

    def headroom_consumed(self, sota: float, baseline: float, ceiling: float) -> float:
        """12 S3.1: (sota - baseline) / (ceiling - baseline), stored unclamped -- above 1.0 means the
        anchor was passed. A lower-is-better metric passes a ceiling below its baseline and the same
        formula holds. Raises HeadroomNotComputable where 12 S3.4 says the number does not exist."""
        reason = self.headroom_null_reason()
        if reason:
            raise HeadroomNotComputable(self.id, reason)
        if ceiling == baseline:
            raise HeadroomNotComputable(self.id, 'no-baseline-established')
        return (sota - baseline) / (ceiling - baseline)
