"""BenchmarkVersion, Subset, Leaderboard, Organization, RatingPool, IngestBatch and Alias (P0-S4-T07;
04-data-model.md S6, S9, S10).

Each is deliberately thin: they exist to be joined to. BenchmarkVersion and Subset live inline on
their Benchmark (`versions[]`, `subsets[]`); the others are one file per record:

    data/organizations/{id}.yaml     data/leaderboards/{id}.yaml    data/rating-pools/{id}.yaml
    data/_ingest/batches/{id}.yaml   data/aliases/{systems,benchmarks,organizations}.yaml

The rules each carries:

  - BenchmarkVersion: `version_kind` revision | edition | track-set, and an edition is always
    `breaking: true` (04 S6: an annual re-competition with new data). A version neither supersedes
    nor is superseded by itself. `errata[]` entries say what changed and cite it.
  - Subset: `{benchmark}#{slug}` ids, inheriting every facet from the parent and overriding
    selectively (`domain_override`, `capability_override`, `metric_override`). `parent` allows the
    deeper trees 04 S6 permits (BraTS edition -> sub-challenge -> split).
  - RatingPool: "a pool is a pool AT A DATE; this is part of its identity" (04 S9). `snapshot_date`
    is required, and the id must carry that date (as YYYY-MM or YYYY-MM-DD). An `anchor` is a member.
  - IngestBatch: the licence and attribution text live here once instead of on every row (04 S9), so
    the licence block is checked for coherence: an attribution-required licence carries its text, and
    the class agrees with the share-alike / non-commercial / redistribution flags.
  - Alias: "an adapter may never create an entity" (04 S10); an alias resolves to an existing
    `{entity}:{id}` and routes what it strips through `extracts` to fields that exist -- a stripped
    `_max` suffix is `eval_conditions.reasoning_effort: max`, a provider prefix is `serving_provider`.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, StringConstraints, model_validator

from schema.claim import LicenceClass, Sha256, Url
from schema.conditions import FIELDS as CONDITION_FIELDS
from schema.conditions import REASONING_EFFORTS
from schema.system import OrgRef, SourceId, SystemRef, Text
from schema.taxonomy import load_taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))


def _enum(values):
    return Literal[tuple(values)]  # type: ignore[valid-type]


DomainLeaf = _enum([t.id for t in _MODELS['domains.yaml'].terms if t.parent and t.status != 'retired'])
Capability = _enum([t.id for t in _MODELS['capabilities.yaml'].terms if t.status != 'retired'])
SubmissionProcess = _enum([t.id for t in _MODELS['governance.yaml'].terms
                           if t.field == 'governance.submission_process' and t.status != 'retired'])

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
VersionTag = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9._-]*$')]
BenchmarkRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}(@[a-z0-9][a-z0-9._-]*)?$')]
SubsetId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}#[a-z0-9][a-z0-9-]*$')]
LeaderboardId = Annotated[str, StringConstraints(pattern=r'^lb-[a-z0-9]+(-[a-z0-9]+)*$')]
PoolId = Annotated[str, StringConstraints(pattern=r'^pool-[a-z0-9]+(-[a-z0-9]+)*$')]
BatchId = Annotated[str, StringConstraints(pattern=r'^ingest-[a-z0-9]+(-[a-z0-9]+)*$')]


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


# ---- 04 S6: BenchmarkVersion and Subset ---------------------------------------------------------

class Erratum(Closed):
    date: _dt.date | None = None      # `_dt.`: the field name shadows the type
    scope: Text | None = None
    description: Text
    source: SourceId


class BenchmarkVersion(Closed):
    version: VersionTag
    label: Text | None = None
    version_kind: Literal['revision', 'edition', 'track-set'] = 'revision'
    released: date | None = None
    items: int | None = Field(default=None, ge=1)
    changes: Text | None = None
    breaking: bool = False
    supersedes_version: VersionTag | None = None
    superseded_by: VersionTag | None = None
    errata: list[Erratum] = Field(default_factory=list)
    frozen: bool = True
    sources: list[SourceId] = Field(default_factory=list)

    @model_validator(mode='after')
    def _rules(self):
        if self.version_kind == 'edition' and not self.breaking:
            raise ValueError('version %s: an edition is always breaking: true (04 S6)' % self.version)
        if self.version in (self.supersedes_version, self.superseded_by):
            raise ValueError('version %s supersedes or is superseded by itself' % self.version)
        return self


class DomainOverride(Closed):
    primary: DomainLeaf
    secondary: list[DomainLeaf] = Field(default_factory=list)


class Subset(Closed):
    id: SubsetId
    label: Text
    parent: SubsetId | None = None
    items: int | None = Field(default=None, ge=1)
    scored_separately: bool = True
    domain_override: DomainOverride | None = None
    capability_override: list[Capability] | None = None
    metric_override: Slug | None = None
    notes: str | None = None

    @property
    def benchmark(self) -> str:
        return self.id.split('#')[0]

    @model_validator(mode='after')
    def _parent(self):
        if self.parent is not None and (self.parent == self.id or self.parent.split('#')[0] != self.benchmark):
            raise ValueError('%s: parent %s is itself or another benchmark\'s subset' % (self.id, self.parent))
        return self


# ---- 04 S9: Organization, Leaderboard, RatingPool -----------------------------------------------

class Organization(Closed):
    id: OrgRef
    name: Text
    kind: Literal['academic-lab', 'company', 'government-agency', 'non-profit', 'community', 'consortium',
                  'individual']
    parent: OrgRef | None = None
    country: Annotated[str, StringConstraints(pattern=r'^[A-Z]{2}$')] | None = None     # ISO 3166-1 alpha-2
    homepage: Url | None = None
    ror: Annotated[str, StringConstraints(pattern=r'^https://ror\.org/0[a-z0-9]{8}$')] | None = None
    wikidata: Annotated[str, StringConstraints(pattern=r'^Q[1-9]\d*$')] | None = None
    roles: list[Literal['benchmark-maintainer', 'system-developer', 'evaluator', 'funder']] = Field(default_factory=list)
    sources: list[SourceId] = Field(min_length=1)

    @model_validator(mode='after')
    def _parent(self):
        if self.parent == self.id:
            raise ValueError('%s is its own parent' % self.id)
        return self


class ArchivedSnapshot(Closed):
    url: Url
    captured: date


class Leaderboard(Closed):
    id: LeaderboardId
    name: Text
    host_org: OrgRef | None = None
    url: Url | None = None
    form: Literal['live-table', 'periodic-snapshot', 'assessment-paper', 'none']
    benchmarks: list[Slug] = Field(min_length=1)
    submission_process: SubmissionProcess | None = None
    is_live: bool
    last_updated: date | None = None
    archived_snapshots: list[ArchivedSnapshot] = Field(default_factory=list)

    @model_validator(mode='after')
    def _live(self):
        if self.is_live and self.form not in ('live-table', 'periodic-snapshot'):
            raise ValueError('%s: a %s leaderboard is not live' % (self.id, self.form))
        return self


class RatingPool(Closed):
    id: PoolId
    leaderboard: LeaderboardId | None = None
    benchmark: BenchmarkRef
    snapshot_date: date                        # required: part of the pool's identity (04 S9)
    members: list[SystemRef] = Field(min_length=2)
    games_per_pair: int | None = Field(default=None, ge=1)
    rating_system: Literal['elo', 'bradley-terry', 'trueskill', 'glicko']
    anchor: SystemRef | None = None
    sources: list[SourceId] = Field(min_length=1)

    @model_validator(mode='after')
    def _identity(self):
        d = self.snapshot_date.isoformat()
        if not (self.id.endswith('-' + d) or self.id.endswith('-' + d[:7])):
            raise ValueError('%s: a pool id carries its snapshot date (%s or %s) -- a pool is a pool at a date'
                             % (self.id, d[:7], d))
        if len(set(self.members)) != len(self.members):
            raise ValueError('%s: a member is listed twice' % self.id)
        if self.anchor is not None and self.anchor not in self.members:
            raise ValueError('%s: anchor %s is not a member of the pool' % (self.id, self.anchor))
        return self


# ---- 04 S9: IngestBatch -------------------------------------------------------------------------

class BatchSource(Closed):
    name: Text
    url: Url
    retrieved_at: datetime
    http_etag: Text | None = None
    artefact_sha256: Sha256 | None = None
    artefact_bytes: int | None = Field(default=None, ge=0)
    upstream_version_handle: Text | None = None


class BatchLicence(Closed):
    spdx: Text | None = None                   # null when upstream states no licence
    class_: LicenceClass = Field(alias='class')
    redistribution_permitted: bool
    share_alike: bool
    non_commercial: bool
    attribution_required: bool
    attribution_text: Text | None = None
    source_record: SourceId

    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    @model_validator(mode='after')
    def _coherent(self):
        if self.attribution_required and not self.attribution_text:
            raise ValueError('an attribution-required licence carries its attribution_text (04 S9)')
        expect = {'share-alike': ('share_alike', True), 'non-commercial': ('non_commercial', True),
                  'no-redistribution': ('redistribution_permitted', False)}.get(self.class_)
        if expect and getattr(self, expect[0]) is not expect[1]:
            raise ValueError('licence class %s but %s is %s' % (self.class_, expect[0], getattr(self, expect[0])))
        return self


class IngestBatch(Closed):
    id: BatchId
    adapter: Slug
    adapter_version: Annotated[str, StringConstraints(pattern=r'^\d+\.\d+\.\d+$')]
    run_started: datetime
    source: BatchSource
    licence: BatchLicence
    resolver_snapshot_sha256: Sha256
    counts: dict[Annotated[str, StringConstraints(pattern=r'^[a-z_]+$')], Annotated[int, Field(ge=0)]]
    target_tree: Annotated[str, StringConstraints(pattern=r'^data/[a-z0-9_./-]+/$')]
    notes: str | None = None


# ---- 04 S10: Alias ------------------------------------------------------------------------------

ENTITY_KINDS = ('system', 'benchmark', 'organization')
_EXTRACT_TARGETS = {'serving_provider'} | {'eval_conditions.' + f for f in CONDITION_FIELDS}


class Alias(Closed):
    alias: Annotated[str, StringConstraints(min_length=1)]      # verbatim, whitespace and all
    resolves_to: Annotated[str, StringConstraints(pattern=r'^(system|benchmark|organization):[a-z0-9][a-z0-9.-]*$')]
    extracts: dict[str, Any] = Field(default_factory=dict)
    kind: Literal['exact', 'spelling', 'provider-endpoint', 'legacy-name', 'typo']
    confidence: Literal['high', 'medium', 'low']
    decided_by: Text
    decided_on: date
    source: SourceId | None = None

    @property
    def entity(self) -> tuple[str, str]:
        kind, _, ident = self.resolves_to.partition(':')
        return kind, ident

    @model_validator(mode='after')
    def _extracts(self):
        stray = sorted(set(self.extracts) - _EXTRACT_TARGETS)
        if stray:
            raise ValueError('alias %r extracts to fields that do not exist: %s' % (self.alias, ', '.join(stray)))
        effort = self.extracts.get('eval_conditions.reasoning_effort')
        if effort is not None and effort not in REASONING_EFFORTS:
            raise ValueError('alias %r extracts reasoning_effort %r, not in the enum (04 S10: _unknown is null)'
                             % (self.alias, effort))
        sp = self.extracts.get('serving_provider')
        if sp is not None and not re.match(r'^org-[a-z0-9]+(-[a-z0-9]+)*$', str(sp)):
            raise ValueError('alias %r: serving_provider %r is not an organization id' % (self.alias, sp))
        return self


class AliasFile(RootModel[list[Alias]]):
    """data/aliases/{systems,benchmarks,organizations}.yaml: one resolution per verbatim string."""

    @model_validator(mode='after')
    def _unique(self):
        seen: dict[str, str] = {}
        for a in self.root:
            if a.alias in seen and seen[a.alias] != a.resolves_to:
                raise ValueError('alias %r resolves to both %s and %s' % (a.alias, seen[a.alias], a.resolves_to))
            if a.alias in seen:
                raise ValueError('alias %r is listed twice' % a.alias)
            seen[a.alias] = a.resolves_to
        return self
