"""The Benchmark entity (P0-S4-T03, reconciled by P0-S4-T10; 04-data-model.md S5, 00 S6 A5, 13 S3.1, S5.4).

One file per benchmark at data/benchmarks/{domain-family}/{id}.yaml, validated by `Benchmark`. The
field set, types and defaults are 04 S5's field reference table plus the fields the three Phase-0
entries needed and 04 did not define (docs/schema-field-needs.md, resolved by P0-S4-T10). The
vocabulary-typed fields are Literal enums built at import time from taxonomy/ (04 S12), through
schema/taxonomy.py, so a taxonomy edit changes this model and the generated JSON Schema with it.

What this model enforces:

  - Tier 1: types, closed vocabularies, id formats, and the fields 04 S5 marks "required at stub".
  - UNKNOWN KEYS ARE REJECTED. A key is accepted only if it is (a) a modelled field, (b) an
    ANNOTATION of a modelled field in the same block, or (c) a DEFERRED key the block declares.
      (b) `<field>_note`, `_notes`, `_caveat` (text), `_basis` (text or a Basis block), `_source`
          (a Source id) and `_quote` (text). A per-term basis is the modelled `capability_basis`. This is the
          per-field notes-and-evidence mechanism the entries needed: one `curation.notes` string
          cannot say which field a note is about, and the quote-substring validator has to know
          which source a value came from (docs/schema-field-needs.md groups `field_notes` and
          `evidence`). An annotation of a field the block does not have is an unknown key.
      (c) Blocks whose information belongs to another entity -- results, editions, metric
          descriptions, live counts, inline source descriptions -- are declared per block in
          DEFERRED and accepted untyped until the entity that owns them takes them over.
          `deferred_fields()` lists every one present.
  - The admissibility boundary (00 S6 A5): at least one `learned_entrant_evidence` item, each citing
    a Source, plus `evaluation_target`.
  - Derived fields are never hand-written (04 S5): `maintenance_status`,
    `execution.inspect_evals_available` and `curation.stewardship` are rejected if present, and
    `lifecycle: saturated` may not be hand-set. `inspect_evals_available` is computed.
  - A facet term cannot be both assigned and `*_considered_and_rejected`, and a per-term
    `capability_basis` justifies only a term that is assigned.

Tier-2 referential checks (a Source or Organization id resolves) are P0-S5-T02; the tier-3
cross-field rules are schema/validators.py (P0-S4-T08).

Croissant. `CROISSANT_TERMS` maps field -> the schema.org term Croissant uses for the same thing,
for the croissant-benchmark extension (04 S5) to serialise from; taxonomy/crosswalks/croissant.yaml
must agree with it.
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Annotated, Any, ClassVar, Literal, Union

from pydantic import (BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, computed_field,
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
Activity = _enum(_FIELDS['activity'])
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
ReproducibilityBlocker = _enum(_FIELDS['execution.reproducibility_blockers'])
HarnessAvailability = _enum(_FIELDS['execution.harness_availability'])
Profile = _enum([p.id for p in _MODELS['comparability-profiles.yaml'].profiles])

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
SourceId = Annotated[str, StringConstraints(pattern=r'^src-[a-z0-9]+(-[a-z0-9]+)*$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
YearMonth = Annotated[str, StringConstraints(pattern=r'^\d{4}-\d{2}(-\d{2})?$')]

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


# ---- blocks, annotations and deferred keys ------------------------------------------------------

class Closed(BaseModel):
    """A block with no annotations and no unknown keys."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class Basis(Closed):
    """The structured form of a `<field>_basis` annotation."""
    reason: Text | None = None
    source: SourceId | None = None
    quote: Text | None = None
    caveat: Text | None = None
    newest_submission: date | None = None      # SWE-bench's activity basis: the newest row seen


_BASIS = Union[Text, Basis]
ANNOTATIONS: dict[str, TypeAdapter] = {
    'note': TypeAdapter(Text), 'notes': TypeAdapter(Text), 'caveat': TypeAdapter(Text),
    'basis': TypeAdapter(_BASIS), 'source': TypeAdapter(SourceId), 'quote': TypeAdapter(Text),
}
_ANNOTATION_KEY = re.compile(r'^(?P<field>[a-z][a-z0-9_]*?)_(?P<kind>%s)$' % '|'.join(ANNOTATIONS))


class Block(BaseModel):
    """A block that accepts annotations of its own fields and the deferred keys it declares, and
    rejects every other unknown key. Both are kept as extras, so they round-trip."""
    model_config = ConfigDict(extra='allow', populate_by_name=True)
    DEFERRED: ClassVar[frozenset[str]] = frozenset()
    DEFERRED_PATTERN: ClassVar[str | None] = None

    @classmethod
    def _field_names(cls) -> set[str]:
        names = set(cls.model_fields) | set(cls.model_computed_fields)
        return names | {f.alias for f in cls.model_fields.values() if f.alias}

    @classmethod
    def classify(cls, key: str) -> str:
        """field | annotation | deferred | unknown."""
        if key in cls._field_names():
            return 'field'
        if key in cls.DEFERRED or (cls.DEFERRED_PATTERN and re.fullmatch(cls.DEFERRED_PATTERN, key)):
            return 'deferred'
        m = _ANNOTATION_KEY.match(key)
        if m and m.group('field') in cls._field_names():
            return 'annotation'
        return 'unknown'

    @model_validator(mode='before')
    @classmethod
    def _keys(cls, data: Any):
        if not isinstance(data, dict):
            return data
        unknown = sorted(str(k) for k in data if cls.classify(str(k)) == 'unknown')
        if unknown:
            raise ValueError('%s: keys the schema does not define: %s' % (cls.__name__, ', '.join(unknown)))
        for k, v in data.items():
            if cls.classify(str(k)) == 'annotation':
                kind = _ANNOTATION_KEY.match(str(k)).group('kind')
                try:
                    ANNOTATIONS[kind].validate_python(v)
                except Exception as e:
                    raise ValueError('%s: annotation %s is not a valid %s: %s' % (cls.__name__, k, kind, e)) from None
        return data

    def annotations(self) -> dict[str, Any]:
        return {k: v for k, v in (self.model_extra or {}).items() if type(self).classify(k) == 'annotation'}


def _no_derived(data: Any, fields: tuple[str, ...], where: str):
    if isinstance(data, dict):
        present = [f for f in fields if f in data]
        if present:
            raise ValueError('%s %s derived and may never appear in a hand-written file (04 S5); remove %s'
                             % (where, 'is' if len(present) == 1 else 'are', ', '.join(present)))
    return data


class Evidence(Closed):
    """A source and the verbatim quote in it that carries a fact."""
    source: SourceId
    quote: Text | None = None


class Count(Block):
    value: int = Field(ge=0)
    unit: Text | None = None
    split: Text | None = None
    note: Text | None = None
    source: SourceId | None = None
    quote: Text | None = None


class Rejected(Closed):
    """A near-miss term and why it was not assigned (the entries' `*_considered_and_rejected`)."""
    term: Text
    reason: Text
    source: SourceId | None = None
    quote: Text | None = None


# ---- identity and description -------------------------------------------------------------------

class LearnedEntrantEvidence(Closed):
    """00 S6 A5: one learned entrant, and where the entry shows it."""
    system: Text        # a System ref once systems are curated; free text until then
    source: SourceId
    observed_on: date
    quote: Text | None = None
    note: Text | None = None


class ExternalIds(Closed):
    """04 S5: a fixed key set of cross-registry join keys, all null by default. `arxiv` added by
    P0-S4-T10 (group `interop`)."""
    epoch: str | None = None
    inspect_evals: str | None = None
    huggingface: str | None = None
    papers_with_code: str | None = None
    every_eval_ever: str | None = None
    benchmark_radar: str | None = None
    arxiv: Annotated[str, StringConstraints(pattern=r'^\d{4}\.\d{4,5}$')] | None = None


class Paper(Closed):
    """The benchmark's own paper. It is a Source; this names which one and which arXiv version was read."""
    title: Text
    arxiv: Annotated[str, StringConstraints(pattern=r'^\d{4}\.\d{4,5}$')] | None = None
    version_read: Annotated[str, StringConstraints(pattern=r'^v\d+$')] | None = None
    source: SourceId


class Event(Closed):
    """A dated challenge run on a live benchmark: neither an edition nor a separate benchmark."""
    name: Text
    kind: Text
    source: SourceId
    quote: Text | None = None


class ObservedSubjects(Closed):
    """Who actually submits, beside `designed_for_subjects` (who it was built for)."""
    values: list[Subject] = Field(min_length=1)
    basis: Text
    source: SourceId


class Domain(Block):
    primary: DomainLeaf
    secondary: list[DomainLeaf] = Field(default_factory=list)
    per_edition: bool = False         # the category set changes by edition, so the list is a union


# ---- task ---------------------------------------------------------------------------------------

class Task(Block):
    """What an item is. `exists: false` is a benchmark with no stored task set (RoboArena)."""
    exists: bool = True
    input: list[Text] = Field(default_factory=list)
    output: Text | None = None
    scoring: Text | None = None
    metric: Slug | None = None
    metric_range: list[float] | None = Field(default=None, min_length=2, max_length=2)
    tests_hidden_from_system: bool | None = None
    reference_solution: bool | None = None
    item_definition: Text | None = None
    constraint: Evidence | None = None
    blinding: Evidence | None = None
    task_distribution_drifts: bool | None = None
    source: SourceId | None = None
    quote: Text | None = None


class FeedbackSignal(Closed):
    kind: Text
    ranks: bool


class Feedback(Block):
    """What an evaluator records per item, and which of it enters the ranking."""
    signals: list[FeedbackSignal] = Field(min_length=1)
    source: SourceId | None = None
    quote: Text | None = None


class EntrantClass(Block):
    """A separately admitted class of entrant (CASP: servers and expert groups), with its deadline."""
    class_: Text = Field(alias='class')
    deadline: Text | None = None
    ranked_separately: bool
    source: SourceId | None = None
    quote: Text | None = None


class Scale(Block):
    """The scale reported at publication. Live counts (`live_YYYY_MM_DD`) are deferred to metrics/."""
    DEFERRED_PATTERN: ClassVar[str | None] = r'live_\d{4}_\d{2}_\d{2}'
    at_publication: 'Counts | None' = None


class Counts(BaseModel):
    """Named non-negative counts plus the source that states them."""
    model_config = ConfigDict(extra='allow')
    source: SourceId
    quote: Text | None = None

    @model_validator(mode='after')
    def _ints(self):
        for k, v in (self.model_extra or {}).items():
            if not re.fullmatch(r'[a-z][a-z0-9_]*', k) or isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError('counts: %s must be a non-negative integer under a snake_case name' % k)
        return self


Scale.model_rebuild()


# ---- data ---------------------------------------------------------------------------------------

class Size(Block):
    """Item counts per split and what they are drawn from. Replaces 04 S5's `{items, unit}`, which no
    entry used, with the shape SWE-bench needed (P0-S4-T10)."""
    n_items: Count
    n_repositories: Count | None = None
    other_splits: list[Count] = Field(default_factory=list)
    languages: list[Text] = Field(default_factory=list)


class SubmissionLimit(Closed):
    """02 S7's shape."""
    max_submissions: int = Field(ge=1)
    period_days: int = Field(ge=0)   # 0 means lifetime (02 S7)
    per: Text
    source: SourceId


class EvidenceItem(Closed):
    """A contamination-evidence item with its own quote and stance."""
    source: SourceId
    stance: Literal['supports', 'against'] | None = None
    quote: Text | None = None


class AccessByPhase(Block):
    """Access over an edition's life, where no single `access` value is true throughout (CASP)."""
    during_edition: Text
    after_edition: Text
    note: Text | None = None


class CategoryCeiling(Closed):
    """A ceiling stated for one category, numeric where the source gives a number."""
    category: Text
    value: float | None = None
    metric: Text | None = None
    source: SourceId
    quote: Text | None = None


class Data(Block):
    access: Access
    access_by_phase: AccessByPhase | None = None
    records_access: Access | None = None       # access to the evaluation records, as distinct from the items
    records_licence: Text | None = None
    records_snapshot: date | None = None
    refresh: Refresh | None = None
    data_provenance: list[DataProvenance] = Field(default_factory=list)
    contamination_risk: ContaminationRisk = 'unknown'
    contamination_evidence: list[Union[SourceId, EvidenceItem]] = Field(default_factory=list)
    ceiling_anchor_type: CeilingAnchor | None = 'none-known'
    ceiling_by_category: list[CategoryCeiling] = Field(default_factory=list)
    dataset_licence: Text | None = None
    upstream_licences: Text | None = None
    size: Size | None = None
    submission_limit: SubmissionLimit | None = None


class EligibilityTier(Closed):
    id: Slug
    label: Text
    rule: Text
    source: SourceId


# ---- governance ---------------------------------------------------------------------------------

class FlagItem(Closed):
    """An independence flag carrying its own evidence."""
    flag: IndependenceFlag
    source: SourceId | None = None
    quote: Text | None = None


class Admission(Closed):
    safety_screen: Text
    source: SourceId
    quote: Text | None = None


class EvaluationBudget(Closed):
    source: SourceId
    quote: Text | None = None
    comparability_consequence: Text | None = None


class Governance(Block):
    maintainer: Text | None = None             # the display name; `maintainers[]` holds Organization refs
    maintainer_type: MaintainerType | None = None
    maintainers: list[Annotated[str, StringConstraints(pattern=r'^org-[a-z0-9-]+$')]] = Field(default_factory=list)
    submission_process: SubmissionProcess | list[SubmissionProcess] | None = None
    independence_flags: list[Union[IndependenceFlag, FlagItem]] = Field(default_factory=list)
    funding: Evidence | None = None
    participation: Evidence | None = None
    independence_policy: Evidence | None = None
    admission: Admission | None = None
    evaluation_budget: EvaluationBudget | None = None
    known_limitation: Evidence | None = None


# ---- execution ----------------------------------------------------------------------------------

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


class Execution(Block):
    compute_tier: ComputeTier | None = None
    compute_tier_by_role: dict[Slug, ComputeTier | None] | None = None
    reproducibility_tier: ReproducibilityTier | None = None
    reproducibility_blockers: list[ReproducibilityBlocker] = Field(default_factory=list)
    harness_availability: HarnessAvailability | None = None
    harness: Text | None = None
    harness_gotcha: Evidence | None = None
    submission_channel: Evidence | None = None
    code_licence: Text | None = None
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


# ---- comparability, liveness, lineage, curation -------------------------------------------------

class Waiver(Closed):
    field: Text
    reason: Text


class Comparability(Closed):
    profile: Profile | None = None
    material_extra: list[Text] = Field(default_factory=list)
    material_waived: list[Waiver] = Field(default_factory=list)
    rating_pool_required: bool = False


class Liveness(Closed):
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


class Variant(Block):
    """A same-maintainer variant (subset, filtered subset, extension)."""
    id: Slug
    relation: Text
    n_items: int | None = Field(default=None, ge=0)
    n_items_history: list[Count] = Field(default_factory=list)
    co_maintainer: Text | None = None
    source: SourceId
    quote: Text | None = None


class Fork(Closed):
    """A derivative by another maintainer."""
    id: Slug
    maintainer: Text
    source: SourceId
    quote: Text | None = None


class View(Closed):
    """A board that is only a filter on another, not a benchmark of its own."""
    name: Text
    of: Slug
    source: SourceId
    quote: Text | None = None


class Lineage(Block):
    role: Literal['root', 'variant', 'fork'] | None = None
    supersedes: list[Slug] = Field(default_factory=list)
    superseded_by: list[Slug] = Field(default_factory=list)
    subset_of: Slug | None = None
    extended_by: list[Slug] = Field(default_factory=list)
    decontaminates: Slug | None = None
    correlates_with: list[Correlation] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    forks: list[Fork] = Field(default_factory=list)
    views: list[View] = Field(default_factory=list)


class InlineSource(Block):
    """A source described inline (the Phase-0 entries' shape). A Source lives in data/sources/ and is
    referenced by id; the inline description is deferred to it (group `curation_sources_inline`)."""
    DEFERRED: ClassVar[frozenset[str]] = frozenset({
        'kind', 'url', 'title', 'doi', 'text_sha256', 'extract', 'extract_warning',
        'bundle_hash_changes_on_redeploy', 'contains_personal_data'})
    id: SourceId


class NotYetAvailable(Closed):
    what: Text
    expected: Text
    consequence: Text


class Unreachable(Closed):
    url: Url
    http_status: int = Field(ge=100, le=599)
    consequence: Text


class PersonalDataExcluded(Closed):
    source: SourceId
    what: Text


class Curation(Block):
    added_by: Text
    added_on: date
    last_verified: date
    verification_status: VerificationStatus = 'ai-drafted-unverified'
    sources: list[Union[SourceId, InlineSource]] = Field(min_length=1)
    confidence: Literal['low', 'medium', 'high'] = 'medium'
    notes: str | None = None
    not_yet_available: list[NotYetAvailable] = Field(default_factory=list)
    unreachable: list[Unreachable] = Field(default_factory=list)
    personal_data_excluded: list[PersonalDataExcluded] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def _derived(cls, data):
        return _no_derived(data, ('stewardship',), 'curation.stewardship')  # set by CI at 24 months (00 S8.2)

    def source_ids(self) -> list[str]:
        return [s if isinstance(s, str) else s.id for s in self.sources]


# ---- the entity -------------------------------------------------------------------------------

class Benchmark(Block):
    """04 S5's Benchmark, in the field order of its field reference table, with the P0-S4-T10
    additions beside the fields they qualify."""
    CROISSANT: ClassVar[dict[str, str]] = CROISSANT_TERMS
    # Information that belongs to another entity (docs/schema-field-needs.md, `deferred` rows).
    DEFERRED: ClassVar[frozenset[str]] = frozenset({
        'maintenance_signals_seen',            # machine-written inputs to a derived verdict (liveness)
        'metric',                              # Metric and RatingPool
        'saturation_by_category',              # derived headroom per Subset
        'editions',                            # BenchmarkVersion, version_kind: edition
        'results_board_summary', 'results_observed',   # ResultClaim and System
        'policy_identity',                     # System and the alias tables
    })

    id: Slug
    name: Text
    aliases: list[Text] = Field(default_factory=list)
    tagline: Text                                   # <= 120 chars is tier 4 (quality), not enforced here
    description: str | None = None
    self_description: Evidence | None = None
    external_ids: ExternalIds = Field(default_factory=ExternalIds)
    croissant_url: Url | None = None
    paper: Paper | None = None
    released: date | None = None
    release_venue: Text | None = None

    domain: Domain
    domain_considered_and_rejected: list[Rejected] = Field(default_factory=list)
    capability: list[Capability] = Field(default_factory=list)
    capability_basis: dict[str, Union[Text, Basis]] = Field(default_factory=dict)
    capability_considered_and_rejected: list[Rejected] = Field(default_factory=list)
    evaluation_method: list[EvaluationMethod] = Field(default_factory=list)
    evaluation_method_considered_and_rejected: list[Rejected] = Field(default_factory=list)
    designed_for_subjects: list[Subject] = Field(default_factory=list)
    designed_for_subjects_considered_and_rejected: list[Rejected] = Field(default_factory=list)
    observed_subjects: ObservedSubjects | None = None
    lifecycle: Lifecycle = 'active'
    activity: Activity | None = None
    planned_end: YearMonth | None = None
    events: list[Event] = Field(default_factory=list)

    # The admissibility block (00 S6 A5; 15 S A3).
    learned_entrant_evidence: list[LearnedEntrantEvidence] = Field(min_length=1)
    evaluation_target: EvaluationTarget
    execution_mode: ExecutionMode | None = None
    ground_truth_source: GroundTruthSource | None = None
    reproducible_by_third_party: bool | None = None

    task: Task | None = None
    feedback_per_item: Feedback | None = None
    entrant_classes: list[EntrantClass] = Field(default_factory=list)
    entrant_classes_history: Evidence | None = None
    scale: Scale | None = None
    platform: Text | None = None                     # the physical platform a benchmark runs on
    hardware: Evidence | None = None

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
    dataset_url: Url | None = None
    leaderboard_url: Url | None = None
    api_url: Url | None = None
    maintainer_url: Url | None = None
    license: str | None = None
    license_notes: str | None = None

    versions: list[BenchmarkVersion] = Field(default_factory=list)
    subsets: list[Subset] = Field(default_factory=list)
    # Metric refs. CASP's entry holds a descriptive dict under this name, deferred to the Metric
    # entity (docs/schema-field-needs.md, group `metric`).
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
    def _rejected_terms(self):
        """A term is assigned or considered-and-rejected, never both, and a rejected term is a real term."""
        vocab = {'capability': Capability, 'evaluation_method': EvaluationMethod,
                 'designed_for_subjects': Subject, 'domain': DomainLeaf}
        for facet, lit in vocab.items():
            assigned = set([self.domain.primary] + self.domain.secondary) if facet == 'domain' else set(getattr(self, facet))
            for r in getattr(self, facet + '_considered_and_rejected'):
                if r.term not in lit.__args__:
                    raise ValueError('%s: %s_considered_and_rejected names %r, which is not a %s term'
                                     % (self.id, facet, r.term, facet))
                if r.term in assigned:
                    raise ValueError('%s: %s is both assigned and considered-and-rejected' % (self.id, r.term))
        stray = sorted(set(self.capability_basis) - set(self.capability))
        if stray:
            raise ValueError('%s: capability_basis justifies terms that are not assigned: %s' % (self.id, ', '.join(stray)))
        return self

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

def _walk(obj: BaseModel, prefix: str, kind: str) -> list[str]:
    out: list[str] = []
    if isinstance(obj, Block):
        out += [prefix + str(k) for k in (obj.model_extra or {}) if type(obj).classify(str(k)) == kind]
    for name in type(obj).model_fields:
        value = getattr(obj, name)
        items = value if isinstance(value, list) else [value]
        for v in items:
            if isinstance(v, BaseModel):
                out += _walk(v, prefix + name + ('[]' if isinstance(value, list) else '') + '.', kind)
    return sorted(set(out))


def deferred_fields(obj: BaseModel) -> list[str]:
    """Every deferred key present, as a dotted path: information another entity will take over."""
    return _walk(obj, '', 'deferred')


def annotation_fields(obj: BaseModel) -> list[str]:
    """Every per-field annotation present, as a dotted path."""
    return _walk(obj, '', 'annotation')


def load_benchmark(path: str) -> Benchmark:
    from schema.taxonomy import read_yaml
    return Benchmark.model_validate(read_yaml(path))
