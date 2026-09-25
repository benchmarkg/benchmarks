"""The Benchmark entity (P0-S4-T03; 04-data-model.md S5, 00 S6 A5, 13 S3.1 and S5.4).

One file per benchmark at data/benchmarks/{domain-family}/{id}.yaml, validated by `Benchmark`. The
field set, types and defaults are 04 S5's field reference table. The vocabulary-typed fields are
Literal enums built at import time from taxonomy/ (04 S12: "taxonomy/*.yaml --loaded at import
time--> dynamic Literal enums"), through schema/taxonomy.py, so a taxonomy edit changes this
model and the generated JSON Schema with it.

What this model enforces at Phase 0:

  - Tier 1: types, closed vocabularies, id formats, and the fields 04 S5 marks "required at stub".
  - The admissibility boundary (00 S6 A5): at least one `learned_entrant_evidence` item, each citing
    a Source, plus `evaluation_target`. A benchmark with none is out of scope and is rejected.
  - Derived fields are never hand-written (04 S5, "a field marked derived may never appear in a
    hand-written YAML file at all"): `maintenance_status`, `execution.inspect_evals_available` and
    `curation.stewardship` are rejected if present, and `lifecycle: saturated` (derived per
    taxonomy/lifecycle.yaml) may not be hand-set. `inspect_evals_available` is computed.
  - `execution.maintainer_rerun_policy` (13 S5.4 rule 1), four values, defaulting to `unstated`.

What it deliberately does not do yet:

  - Unknown keys are ACCEPTED by default. The three Phase-0 entries were written without a schema
    and use about 300 field paths 04 does not define (docs/schema-field-needs.md). P0-S4-T10 adds
    the needed ones and deletes the rest; until then `unmodelled_fields()` lists every key the
    model did not recognise, and validating with context {'strict': True} rejects them. T10 makes
    strict the default. The risk this carries until then, a misspelled 04 field passing as an
    unknown key, is the reason `unmodelled_fields()` exists.
  - Four shapes the entries need and 04 does not define are accepted alongside 04's own form,
    pending T10: `submission_process` as a list; independence flags, contamination evidence and
    `curation.sources[]` items carrying their own source and quote. Values inside them are still
    vocabulary-checked.
  - Tier-2 referential checks (a Source or Organization id resolves) and the other tier-3 rules
    (contamination evidence above `medium`, the contested-status pair, ...) are P0-S5-T02 and
    P0-S4-T08. `versions[]`, `subsets[]` and `baselines[]` are the P0-S4-T07 models (schema/entities.py,
    schema/baseline.py), checked here only for belonging to this benchmark; `metrics` stays as it
    was until P0-S4-T10, because CASP's entry holds a descriptive dict under that name.

Croissant. Where a schema.org term used by Croissant names the same thing, the field uses that name
or records the term: `CROISSANT_TERMS` maps field -> term, for the croissant-benchmark extension
(04 S5) to serialise from. 04 S5 fixes the YAML names; `homepage` is Croissant's `url`.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Annotated, Any, ClassVar, Literal, Union

from pydantic import (BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo, computed_field,
                      model_validator)

from schema.baseline import Baseline
from schema.entities import BenchmarkVersion, Subset
from schema.taxonomy import load_taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))


def _field_terms(*files):
    out: dict[str, list[str]] = {}
    for f in files:
        for t in _MODELS[f].terms:
            if t.status != 'retired':
                out.setdefault(t.field, []).append(t.id)
    return out


_FIELDS = _field_terms('data-properties.yaml', 'ceiling-anchors.yaml', 'execution.yaml', 'governance.yaml',
                       'lifecycle.yaml', 'maintenance.yaml')
_DERIVED_TERMS = {(t.field, t.id) for f in ('lifecycle.yaml', 'maintenance.yaml') for t in _MODELS[f].terms if t.derived}


def _live(file):
    return [t.id for t in _MODELS[file].terms if t.status != 'retired']


def _enum(values):
    return Literal[tuple(values)]  # type: ignore[valid-type]


DomainLeaf = _enum([t.id for t in _MODELS['domains.yaml'].terms if t.parent and t.status != 'retired'])
Capability = _enum(_live('capabilities.yaml'))
EvaluationMethod = _enum(_live('evaluation-methods.yaml'))
Subject = _enum(_live('subjects.yaml'))
Lifecycle = _enum(_FIELDS['lifecycle'])
Access = _enum(_FIELDS['data.access'])
Refresh = _enum(_FIELDS['data.refresh'])
DataProvenance = _enum(_FIELDS['data.data_provenance'])
ContaminationRisk = _enum(_FIELDS['data.contamination_risk'])
CeilingAnchor = _enum(_FIELDS['data.ceiling_anchor_type'])
MaintainerType = _enum(_FIELDS['governance.maintainer_type'])
SubmissionProcess = _enum(_FIELDS['governance.submission_process'])
IndependenceFlag = _enum(_FIELDS['governance.independence_flags'])
ComputeTier = _enum(_FIELDS['execution.compute_tier'])
ReproducibilityTier = _enum(_FIELDS['execution.reproducibility_tier'])
Profile = _enum([p.id for p in _MODELS['comparability-profiles.yaml'].profiles])

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
SourceId = Annotated[str, StringConstraints(pattern=r'^src-[a-z0-9]+(-[a-z0-9]+)*$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

EvaluationTarget = Literal['learned-system', 'numerical-method', 'human-population', 'mixed']
ExecutionMode = Literal['automated', 'human-in-loop', 'wet-lab', 'physical-trial', 'panel']
GroundTruthSource = Literal['repository-tests', 'held-out-labels', 'simulation', 'experimental', 'expert-panel',
                            'forecast-resolution', 'none']
RunnableVia = Literal['inspect', 'lm_eval', 'helm', 'custom', 'none']
# 13 S5.4 rule 1: populated during curation from the benchmark's own stated terms.
MaintainerRerunPolicy = Literal['unrestricted', 'no-third-party-endpoints', 'contact-first', 'unstated']
AggregationPolicy = Literal['official-aggregate', 'community-aggregate', 'none-by-design']
SecondaryAxis = Literal['cost', 'latency', 'throughput', 'energy', 'reliability']
VerificationStatus = Literal['ai-drafted-unverified', 'machine-ingested', 'curator-reviewed', 'primary-source-verified',
                             'expert-reviewed', 'maintainer-confirmed']  # 05 S4's ladder

CROISSANT_TERMS = {  # field -> the schema.org term Croissant uses for the same thing
    'name': 'sc:name',
    'description': 'sc:description',
    'aliases': 'sc:alternateName',
    'homepage': 'sc:url',
    'license': 'sc:license',
    'tags': 'sc:keywords',
    'croissant_url': 'sc:subjectOf',
}


class Open(BaseModel):
    """A block that accepts keys it does not model, pending P0-S4-T10, unless validated strictly."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    @model_validator(mode='before')
    @classmethod
    def _strict(cls, data: Any, info: ValidationInfo):
        if isinstance(data, dict) and (info.context or {}).get('strict'):
            unknown = sorted(set(data) - set(cls.model_fields))
            if unknown:
                raise ValueError('%s: keys the schema does not define: %s' % (cls.__name__, ', '.join(map(str, unknown))))
        return data


class Closed(BaseModel):
    """A block this task defines for the first time: no unknown keys, ever."""
    model_config = ConfigDict(extra='forbid')


def _no_derived(data: Any, fields: tuple[str, ...], where: str):
    if isinstance(data, dict):
        present = [f for f in fields if f in data]
        if present:
            raise ValueError('%s %s derived and may never appear in a hand-written file (04 S5); remove %s'
                             % (where, 'is' if len(present) == 1 else 'are', ', '.join(present)))
    return data


# ---- blocks -----------------------------------------------------------------------------------

class LearnedEntrantEvidence(Closed):
    """00 S6 A5: one learned entrant, and where the entry shows it."""
    system: Text        # a System ref once P0-S4-T05 lands; free text until then
    source: SourceId
    observed_on: date
    quote: Text | None = None
    note: Text | None = None


class ExternalIds(Closed):
    """04 S5: a fixed key set of cross-registry join keys, all null by default."""
    epoch: str | None = None
    inspect_evals: str | None = None
    huggingface: str | None = None
    papers_with_code: str | None = None
    every_eval_ever: str | None = None
    benchmark_radar: str | None = None


class Domain(Open):
    primary: DomainLeaf
    secondary: list[DomainLeaf] = Field(default_factory=list)


class Size(Closed):
    items: int | None = Field(default=None, ge=0)
    unit: Text


class SubmissionLimit(Closed):
    """02 S7's shape."""
    max_submissions: int = Field(ge=1)
    period_days: int = Field(ge=0)   # 0 means lifetime (02 S7)
    per: Text
    source: SourceId


class EvidenceItem(Open):
    """A contamination-evidence item with its own quote and stance (SWE-bench's shape), pending T10."""
    source: SourceId
    stance: Literal['supports', 'against'] | None = None
    quote: Text | None = None


class Data(Open):
    access: Access
    refresh: Refresh | None = None
    data_provenance: list[DataProvenance] | None = Field(default_factory=list)
    contamination_risk: ContaminationRisk = 'unknown'
    contamination_evidence: list[Union[SourceId, EvidenceItem]] | None = Field(default_factory=list)
    ceiling_anchor_type: CeilingAnchor | None = 'none-known'
    size: Size | None = None
    submission_limit: SubmissionLimit | None = None


class EligibilityTier(Closed):
    id: Slug
    label: Text
    rule: Text
    source: SourceId


class FlagItem(Open):
    """An independence flag carrying its own evidence (SWE-bench's shape), pending T10."""
    flag: IndependenceFlag


class Governance(Open):
    maintainer_type: MaintainerType | None = None
    maintainers: list[Annotated[str, StringConstraints(pattern=r'^org-[a-z0-9-]+$')]] = Field(default_factory=list)
    submission_process: SubmissionProcess | list[SubmissionProcess] | None = None
    independence_flags: list[Union[IndependenceFlag, FlagItem]] | None = Field(default_factory=list)


class Range(Closed):
    """02 S10's shape, `{min, max, basis, source}`. `basis` is nullable here because 02 S11's
    "any range estimate present -> basis non-null" is a tier-3 rule (schema/validators.py)."""
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    basis: Text | None = None
    source: SourceId | None = None

    @model_validator(mode='after')
    def _ordered(self):
        if self.min > self.max:
            raise ValueError('min %s is above max %s' % (self.min, self.max))
        return self


class ParticipantCost(Range):
    """02 S12: ranged, and `basis` is mandatory when the block is non-null (CACHE, RoboCup, A2RL)."""
    basis: Text


class Execution(Open):
    compute_tier: ComputeTier | None = None
    reproducibility_tier: ReproducibilityTier | None = None
    est_runtime_hours: Range | None = None
    est_cost_usd: Range | None = None
    est_participant_cost_usd: ParticipantCost | None = None
    runnable_via: list[RunnableVia] = Field(default_factory=lambda: ['none'])
    inspect_evals_id: Text | None = None
    maintainer_rerun_policy: MaintainerRerunPolicy = 'unstated'

    @model_validator(mode='before')
    @classmethod
    def _derived(cls, data):
        return _no_derived(data, ('inspect_evals_available',), 'execution.inspect_evals_available')

    @computed_field
    @property
    def inspect_evals_available(self) -> bool:
        """13 S3.1: derived from `inspect_evals_id`, never hand-set, so the two cannot disagree."""
        return self.inspect_evals_id is not None


class Waiver(Closed):
    field: Text
    reason: Text


class Comparability(Open):
    profile: Profile | None = None
    material_extra: list[Text] = Field(default_factory=list)
    material_waived: list[Waiver] = Field(default_factory=list)
    rating_pool_required: bool = False


class Liveness(Open):
    """Raw observations, machine-written (07). `reproduction_script_verified: null` is 'not checked'."""
    repo_last_commit: date | None = None
    leaderboard_last_updated: date | None = None
    reproduction_script_present: bool | None = None
    reproduction_script_verified: bool | None = None
    last_checked: date | None = None


class Correlation(Closed):
    benchmark: Slug
    coefficient: float | None = Field(default=None, ge=-1, le=1)
    source: SourceId | None = None


class Lineage(Open):
    supersedes: list[Slug] = Field(default_factory=list)
    superseded_by: list[Slug] = Field(default_factory=list)
    subset_of: Slug | None = None
    extended_by: list[Slug] = Field(default_factory=list)
    decontaminates: Slug | None = None
    correlates_with: list[Correlation] = Field(default_factory=list)


class InlineSource(Open):
    """A source described inline (the Phase-0 entries' shape). Since P0-S4-T04 a Source lives in
    data/sources/ and is referenced by id; T10 reduces these to ids."""
    id: SourceId


class Curation(Open):
    added_by: Text
    added_on: date
    last_verified: date
    verification_status: VerificationStatus = 'ai-drafted-unverified'
    sources: list[Union[SourceId, InlineSource]] = Field(min_length=1)
    confidence: Literal['low', 'medium', 'high'] = 'medium'
    notes: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _derived(cls, data):
        return _no_derived(data, ('stewardship',), 'curation.stewardship')  # set by CI at 24 months (00 S8.2)

    def source_ids(self) -> list[str]:
        return [s if isinstance(s, str) else s.id for s in self.sources]


# ---- the entity -------------------------------------------------------------------------------

class Benchmark(Open):
    """04 S5's Benchmark, in the field order of its field reference table."""
    CROISSANT: ClassVar[dict[str, str]] = CROISSANT_TERMS

    id: Slug
    name: Text
    aliases: list[Text] = Field(default_factory=list)
    tagline: Text                                   # <= 120 chars is tier 4 (quality), not enforced here
    description: str | None = None
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    croissant_url: Url | None = None

    domain: Domain
    capability: list[Capability] = Field(default_factory=list)
    evaluation_method: list[EvaluationMethod] = Field(default_factory=list)
    designed_for_subjects: list[Subject] = Field(default_factory=list)
    lifecycle: Lifecycle = 'active'

    # The admissibility block (00 S6 A5; 15 S A3).
    learned_entrant_evidence: list[LearnedEntrantEvidence] = Field(min_length=1)
    evaluation_target: EvaluationTarget
    execution_mode: ExecutionMode | None = None
    ground_truth_source: GroundTruthSource | None = None
    reproducible_by_third_party: bool | None = None

    data: Data
    training_data_eligibility_tiers: list[EligibilityTier] = Field(default_factory=list)
    governance: Governance = Field(default_factory=Governance)
    execution: Execution = Field(default_factory=Execution)
    comparability: Comparability = Field(default_factory=Comparability)

    reference_conditions: Annotated[str, StringConstraints(pattern=r'^cond-[0-9a-f]{12}$')] | None = None
    aggregation_policy: AggregationPolicy = 'official-aggregate'
    headline_metric: Slug | None = None
    no_legitimate_aggregate: bool = False
    secondary_axes: list[SecondaryAxis] = Field(default_factory=list)

    liveness: Liveness | None = None
    maintenance_status_contested: bool = False
    contested_source: SourceId | None = None
    contested_statement_date: date | None = None

    homepage: Url
    repository: Url | None = None
    license: str | None = None
    license_notes: str | None = None

    versions: list[BenchmarkVersion] = Field(default_factory=list)
    subsets: list[Subset] = Field(default_factory=list)
    # Metric refs. CASP's entry holds a descriptive dict under this name (docs/schema-field-needs.md,
    # group `metric`: deferred to the Metric entity); accepted until P0-S4-T07/T10 move it there.
    metrics: list[Slug] | dict = Field(default_factory=list)
    leaderboards: list[Annotated[str, StringConstraints(pattern=r'^lb-[a-z0-9-]+$')]] = Field(default_factory=list)
    baselines: list[Baseline] = Field(default_factory=list)
    lineage: Lineage | None = None
    tags: list[Text] = Field(default_factory=list)
    ingestion: dict | None = None                           # machine-written (04 S9)
    curation: Curation

    @model_validator(mode='before')
    @classmethod
    def _derived(cls, data):
        data = _no_derived(data, ('maintenance_status',), 'maintenance_status')
        if isinstance(data, dict) and ('lifecycle', data.get('lifecycle')) in _DERIVED_TERMS:
            raise ValueError('lifecycle %r is derived (taxonomy/lifecycle.yaml) and may never be hand-set'
                             % data['lifecycle'])
        return data

    @model_validator(mode='after')
    def _inline_entities(self):
        tags = [v.version for v in self.versions]
        if len(set(tags)) != len(tags):
            raise ValueError('%s: a version tag is listed twice' % self.id)
        for v in self.versions:
            for ref in (v.supersedes_version, v.superseded_by):
                if ref is not None and ref not in tags:
                    raise ValueError('%s@%s refers to version %s, which is not listed' % (self.id, v.version, ref))
        ids = {s.id for s in self.subsets}
        for s in self.subsets:
            if s.benchmark != self.id:
                raise ValueError('%s: subset %s belongs to another benchmark' % (self.id, s.id))
            if s.parent is not None and s.parent not in ids:
                raise ValueError('%s: subset %s has parent %s, which is not listed' % (self.id, s.id, s.parent))
        for b in self.baselines:
            if b.benchmark_version.split('@')[0] != self.id:
                raise ValueError('%s: baseline %s is on %s' % (self.id, b.id, b.benchmark_version))
        return self


# ---- helpers ----------------------------------------------------------------------------------

def unmodelled_fields(obj: BaseModel, prefix: str = '') -> list[str]:
    """Every key the model accepted without recognising, as a dotted path: the list P0-S4-T10 works
    through, and what `{'strict': True}` would reject."""
    out: list[str] = []
    for key in sorted((obj.model_extra or {}), key=str):
        out.append(prefix + str(key))
    for name in type(obj).model_fields:
        value = getattr(obj, name)
        items = value if isinstance(value, list) else [value]
        for v in items:
            if isinstance(v, BaseModel):
                sub = prefix + name + ('[]' if isinstance(value, list) else '') + '.'
                out.extend(unmodelled_fields(v, sub))
    return sorted(set(out))


def load_benchmark(path: str, strict: bool = False) -> Benchmark:
    from schema.taxonomy import read_yaml
    return Benchmark.model_validate(read_yaml(path), context={'strict': strict})
