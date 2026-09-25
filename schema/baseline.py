"""Baseline, which replaces HumanBaseline (P0-S4-T07; 04-data-model.md S7, 12 S3.2).

Stored as a list per benchmark at data/baselines/{benchmark-id}.yaml, or inline on the Benchmark.

The rules this model carries:

  - `kind` is twelve terms, split deliberately: nine CEILINGS, one-to-one with 02 S7's
    `ceiling_anchor_type` (taxonomy/ceiling-anchors.yaml) -- the tenth facet term, `none-known`, is
    the absence of a ceiling and is `value_absent_reason` here -- and three FLOORS the facet does not
    carry. CEILING_ANCHOR maps each ceiling kind to its facet term; the spellings differ on purpose
    (04 S7 governs the stored record, 02 S7 the facet), and ceiling-anchors.yaml says not to
    reconcile them by editing one side. `experimental-replicate` and `noise-ceiling` are the two 04
    added so the Virtual Cell Challenge and Brain-Score can be stored at all.
  - A baseline has a `value` or a `value_absent_reason`, never both, never neither: a reader needs to
    know whether a missing number means nobody measured it or the concept does not apply.
  - Exactly one `is_primary` per (benchmark_version, metric) in a file (BaselineFile), because
    headroom is computed against the primary and the choice is recorded.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints, model_validator

from schema.system import SourceId, Text

CEILING_ANCHOR = {                       # Baseline.kind -> data.ceiling_anchor_type
    'human-crowd-average': 'crowd-average',
    'human-crowd-best': 'crowd-best',
    'human-expert-average': 'expert-average',
    'human-expert-best': 'expert-best',
    'theoretical-maximum': 'theoretical-maximum',
    'measured-ceiling': 'measured-ceiling',
    'experimental-replicate': 'experimental-replicate',
    'operational-system': 'operational-system',
    'noise-ceiling': 'noise-ceiling',
}
FLOOR_KINDS = ('classical-algorithm', 'random-chance', 'field-practice-reference')
BaselineKind = Literal[tuple(CEILING_ANCHOR) + FLOOR_KINDS]  # type: ignore[valid-type]
ValueAbsentReason = Literal['no-published-comparator', 'not-applicable', 'not-yet-measured']
BaselineId = Annotated[str, StringConstraints(pattern=r'^base-[a-z0-9]+(-[a-z0-9]+)*$')]
BenchmarkVersionRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}(@[a-z0-9][a-z0-9._-]*)?$')]
MetricRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]


class Baseline(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: BaselineId
    benchmark_version: BenchmarkVersionRef
    kind: BaselineKind
    metric: MetricRef
    value: float | None = None
    value_absent_reason: ValueAbsentReason | None = None
    n_humans: int | None = Field(default=None, ge=1)
    population: Text | None = None
    time_limit: Text | None = None
    is_primary: bool = False
    source: SourceId | None = None
    notes: str | None = None

    @property
    def is_floor(self) -> bool:
        return self.kind in FLOOR_KINDS

    @property
    def ceiling_anchor_type(self) -> str | None:
        """The facet term this record stands for, or None for a floor."""
        return CEILING_ANCHOR.get(self.kind)

    @model_validator(mode='after')
    def _value(self):
        if (self.value is None) == (self.value_absent_reason is None):
            raise ValueError('%s: a baseline has a value or a value_absent_reason, exactly one (04 S7)' % self.id)
        if self.value is not None and self.source is None:
            raise ValueError('%s: a baseline value needs its source' % self.id)
        if self.n_humans is not None and not self.kind.startswith('human-'):
            raise ValueError('%s: n_humans on a %s baseline' % (self.id, self.kind))
        return self


class BaselineFile(RootModel[list[Baseline]]):
    """data/baselines/{benchmark-id}.yaml."""

    @model_validator(mode='after')
    def _one_primary(self):
        ids = [b.id for b in self.root]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError('duplicate baseline ids: %s' % ', '.join(dup))
        primaries: dict[tuple[str, str], list[str]] = {}
        for b in self.root:
            primaries.setdefault((b.benchmark_version, b.metric), [])
            if b.is_primary:
                primaries[(b.benchmark_version, b.metric)].append(b.id)
        for (bv, m), got in sorted(primaries.items()):
            if len(got) != 1:
                raise ValueError('%s / %s: exactly one is_primary baseline, found %d%s'
                                 % (bv, m, len(got), (' (%s)' % ', '.join(got)) if got else ''))
        return self
