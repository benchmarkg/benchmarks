"""ResultClaim and the `ingestion` block (P0-S4-T05; 04-data-model.md S7, S9, S15 items 1, 2, 5-7).

"Not a score -- a claim that someone made about a score." One file per claim under data/claims/.

The rules this model carries, each from 04 S7 unless marked:

  - `claim_type` decides the shape. `absolute` and `rating` carry a `value`; `pairwise` carries a
    `value` and an `opponent`, and no other type may name one; `rating` names its `rating_pool`
    (a rating means nothing outside its pool), and no other type may; `ordinal` carries a `value` or a
    `value_text`; `qualitative` carries `value_text`.
  - `resolution_status: pending` is the one case where a numeric claim has no value yet
    (ForecastBench: the answer does not exist at submission). `partial` and `resolved` need one.
  - `artifact_url` + `artifact_archived` (04 S15 item 1, a C5 addition): `artifact_archived` says
    something only when there is an artifact.
  - `provenance_snapshot` (04 S15 item 2, a C5 addition) is the upstream record frozen as retrieved:
    `{source_record_id, retrieved_at, content_sha256, raw}`, with `raw` the row's own key-value
    mapping. `content_sha256` is checked against `raw`, hashed as sorted, spaceless JSON (07 S1.5's
    canonical form), so a snapshot cannot be edited without the hash saying so.
  - The `ingestion` block (04 S9, S15 item 7) records how an adapter wrote the claim, and its
    `field_provenance` maps OUR fields to source | derived | absent | curator. It is not the
    snapshot: the snapshot is what upstream said, `field_provenance` is where each of our fields came
    from. `source_record_id` is a content key: the upstream columns that identify the record,
    URL-encoded after the `#` (04 S9, 07 S1.4). A row, line or index ordinal is forbidden in any
    spelling, because a regenerated export renumbers it when nothing else changed.
  - `verification` is a rung of taxonomy/verification.yaml; `disputed` is a state carried by
    `disputed_by[]`, not a rung (04 S7).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.system import OrgRef, SourceId, SystemRef, Text
from schema.taxonomy import load_taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))

Verification = Literal[tuple(r.id for r in _MODELS['verification.yaml'].rungs)]  # type: ignore[valid-type]
ClaimId = Annotated[str, StringConstraints(pattern=r'^claim-[0-9a-f]{12}$')]
BenchmarkRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}(@[a-z0-9][a-z0-9._-]*)?$')]
MetricRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
ConditionsRef = Annotated[str, StringConstraints(pattern=r'^cond-[0-9a-f]{12}$')]
PoolRef = Annotated[str, StringConstraints(pattern=r'^pool-[a-z0-9]+(-[a-z0-9]+)*$')]
Sha256 = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]

ClaimType = Literal['absolute', 'pairwise', 'rating', 'ordinal', 'qualitative']
ResolutionStatus = Literal['pending', 'partial', 'resolved']
LicenceClass = Literal['permissive-attribution', 'share-alike', 'non-commercial', 'no-redistribution', 'unlicensed']
ReviewState = Literal['machine-ingested', 'spot-checked', 'human-reviewed', 'promoted']
FieldOrigin = Literal['source', 'derived', 'absent', 'curator']


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


def snapshot_sha256(raw: Any) -> str:
    """The hash `provenance_snapshot.content_sha256` must carry: sha256 of `raw` as sorted, spaceless
    UTF-8 JSON (07 S1.5's canonical form)."""
    canon = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


class Uncertainty(Closed):
    type: Literal['stderr', 'ci95', 'ci90', 'range', 'iqr', 'none']
    value: float | list[float] | None = None     # a range or CI is a [low, high] pair
    n_runs: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def _shape(self):
        if self.type == 'none' and self.value is not None:
            raise ValueError('uncertainty type none carries no value')
        if self.type in ('ci95', 'ci90', 'range', 'iqr') and self.value is not None and not (
                isinstance(self.value, list) and len(self.value) == 2 and self.value[0] <= self.value[1]):
            raise ValueError('uncertainty type %s is a [low, high] pair' % self.type)
        return self


# Keys that name a position rather than the record (04 S9: "a content key, not a row ordinal").
ORDINAL_KEYS = frozenset({'row', 'rows', 'rownum', 'row_num', 'row_number', 'row_index', 'rowid', 'line', 'lines',
                          'lineno', 'line_number', 'index', 'idx', 'n', 'position', 'pos', 'offset', 'ordinal'})
_PAIR = re.compile(r'^[A-Za-z0-9_.~%-]+=[^&=\s]*$')


def check_source_record_id(sid: str | None) -> None:
    """Raise ValueError unless `sid` is null or a content key. After a `#`, the discriminators are
    `key=value` pairs joined by `&`, URL-encoded (so no whitespace), none of them an ordinal."""
    if sid is None:
        return
    if re.search(r'\s', sid):
        raise ValueError('source_record_id %r contains whitespace; URL-encode the discriminators (04 S9)' % sid)
    if '#' not in sid:
        return                                      # an upstream key of its own, e.g. `gpqa-diamond:model`
    fragment = sid.split('#', 1)[1]
    pairs = fragment.split('&')
    if not fragment or not all(_PAIR.match(p) for p in pairs):
        raise ValueError('source_record_id %r: after `#` come key=value discriminators joined by `&` (04 S9)' % sid)
    ordinal = sorted({p.split('=', 1)[0] for p in pairs if p.split('=', 1)[0].lower() in ORDINAL_KEYS})
    if ordinal:
        raise ValueError('source_record_id %r is a row ordinal (%s); use the columns that identify the record '
                         '(04 S9)' % (sid, ', '.join(ordinal)))


class ProvenanceSnapshot(Closed):
    """04 S7: the upstream record exactly as retrieved. Small by design -- an Epoch row is a few
    hundred bytes."""
    source_record_id: Text | None
    retrieved_at: datetime
    content_sha256: Sha256
    raw: dict[str, Any]

    @model_validator(mode='after')
    def _content_key(self):
        check_source_record_id(self.source_record_id)
        return self

    @model_validator(mode='after')
    def _hash(self):
        if self.content_sha256 != snapshot_sha256(self.raw):
            raise ValueError('provenance_snapshot.content_sha256 is not the sha256 of `raw` (07 S1.5 canonical JSON)')
        return self


class ClaimExternalIds(Closed):
    eee_result_id: Text | None = None       # Every Eval Ever's result id (04 S15 item 6)


class Ingestion(Closed):
    """04 S9: present on every machine-written record, null on hand-curated ones."""
    batch: Annotated[str, StringConstraints(pattern=r'^ingest-[a-z0-9]+(-[a-z0-9]+)*$')]
    source_adapter: Text
    adapter_version: Annotated[str, StringConstraints(pattern=r'^\d+\.\d+\.\d+$')]
    source_record_id: Text | None           # null only for a full-replace source (04 S9)
    last_seen_upstream: date
    source_url: Url
    source_licence: Text
    licence_class: LicenceClass
    source_attribution: Text
    ingested_at: datetime
    extraction_confidence: float = Field(ge=0, le=1)
    review_state: ReviewState = 'machine-ingested'
    reviewed_by: Text | None = None
    reviewed_on: date | None = None
    field_provenance: dict[Annotated[str, StringConstraints(pattern=r'^[a-z_]+(\.[a-z_]+)*$')], FieldOrigin] = \
        Field(default_factory=dict)

    @model_validator(mode='after')
    def _content_key(self):
        check_source_record_id(self.source_record_id)
        return self

    @model_validator(mode='after')
    def _reviewed(self):
        if self.review_state in ('human-reviewed', 'promoted') and not (self.reviewed_by and self.reviewed_on):
            raise ValueError('review_state %s names reviewed_by and reviewed_on' % self.review_state)
        return self


class ResultClaim(Closed):
    id: ClaimId
    system: SystemRef
    benchmark: BenchmarkRef
    subset: Text | None = None
    metric: MetricRef
    claim_type: ClaimType = 'absolute'
    value: float | None = None
    value_text: Text | None = None
    opponent: SystemRef | None = None
    rating_pool: PoolRef | None = None
    uncertainty: Uncertainty | None = None
    serving_provider: OrgRef | None = None       # a third-party host, not the first-party API
    date_reported: date
    reported_by: OrgRef
    verification: Verification
    disputed_by: list[SourceId] = Field(default_factory=list)
    resolution_status: ResolutionStatus = 'resolved'
    resolved_as_of: date | None = None
    source: SourceId
    artifact_url: Url | None = None
    artifact_archived: bool | None = None
    provenance_snapshot: ProvenanceSnapshot | None = None
    external_ids: ClaimExternalIds = Field(default_factory=ClaimExternalIds)
    eval_conditions: ConditionsRef | None = None
    result_group: Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]*$')] | None = None
    superseded_by: ClaimId | None = None
    ingestion: Ingestion | None = None
    notes: str | None = None

    @model_validator(mode='after')
    def _shape_by_type(self):
        t, pending = self.claim_type, self.resolution_status == 'pending'
        if t in ('absolute', 'pairwise', 'rating') and self.value is None and not pending:
            raise ValueError('%s: a %s claim needs a value unless resolution_status is pending' % (self.id, t))
        if t == 'ordinal' and self.value is None and self.value_text is None and not pending:
            raise ValueError('%s: an ordinal claim needs a value or value_text' % self.id)
        if t == 'qualitative' and self.value_text is None:
            raise ValueError('%s: a qualitative claim needs value_text' % self.id)
        if t == 'qualitative' and self.value is not None:
            raise ValueError('%s: a qualitative claim has no numeric value' % self.id)
        if t == 'pairwise':
            if self.opponent is None:
                raise ValueError('%s: a pairwise claim requires an opponent (04 S7)' % self.id)
            if self.opponent.split('@')[0] == self.system.split('@')[0]:
                raise ValueError('%s: a system cannot be its own opponent' % self.id)
        elif self.opponent is not None:
            raise ValueError('%s: opponent is for pairwise claims only' % self.id)
        if t == 'rating' and self.rating_pool is None:
            raise ValueError('%s: a rating claim names its rating_pool -- a rating means nothing outside it' % self.id)
        if t != 'rating' and self.rating_pool is not None:
            raise ValueError('%s: rating_pool is for rating claims only' % self.id)
        return self

    @model_validator(mode='after')
    def _resolution(self):
        if self.resolution_status == 'pending' and self.resolved_as_of is not None:
            raise ValueError('%s: a pending claim has no resolved_as_of' % self.id)
        return self

    @model_validator(mode='after')
    def _artifact(self):
        if self.artifact_archived is not None and self.artifact_url is None:
            raise ValueError('%s: artifact_archived without an artifact_url' % self.id)
        return self
