"""The croissant-benchmark extension's terms and the documents that carry them (P4-S6-T02, from P2-S3-T06's models;
08 S5.8, 04 S5, 04 S8, 15 A8; ADR-0030).

MLCommons Croissant describes datasets and has no benchmark extension, so the catalogue publishes one in its own
namespace (08 S5.8). This module is the extension's vocabulary and its JSON Schema: the namespace, the seven cb:
classes, every cb: term with the field of ours it carries, and the Pydantic models of the two documents the build
emits (tools/build/croissant.py writes and validates them). `bench schema gen` renders `json_schema()` as
schema/generated/croissant-benchmark.schema.json (tools/build/codegen.py), so the codegen drift check holds the
committed schema to these models, and renders the published context, site/public/ns/croissant-benchmark/v1/
context.jsonld, from TERMS. The models lived in tools/build/croissant.py until P4-S6-T02 asked for them here
(ADR-0030): Pydantic is canonical (ADR-0003), and an extension schema is a schema.

The mapping. taxonomy/crosswalks/croissant.yaml is the written mapping; its `extension` section must equal this
module (tests/build/test_croissant.py, tests/test_croissant_mapping.py):

  CLASSES       the seven cb: classes
  TERMS         every extension property: term -> (the class it is a property of, the field of ours it carries as a
                dotted path schema/paths.py resolves, or None for a Benchmark-level node gathering several fields).
                08 S5.8's five groups -- tasks, metrics, protocol, conditions, lineage -- are Benchmark-level terms
  REUSES        the schema.org terms a node of ours reuses with their schema.org meaning (a Metric's id, name, range)
  MATERIAL_KEY  the Benchmark's side of the comparability key: the component tools/build/comparability.py's
                compute() takes beside the conditions -> the Benchmark field whose entries it names

Every material field is accounted for (P4-S6-T02; 04 S8: "Two claims are comparable only when they agree on
benchmark version, metric, subset, and the material condition fields"). A field is material when
taxonomy/comparability-profiles.yaml names it in a profile or the fallback, when a curated benchmark's resolved set
holds it (tools/build/comparability.py's resolve_profile, which adds `comparability.material_extra`), when it is a
component of the key's Benchmark side, or when it is the Benchmark's comparability block, which resolves the set.
Each maps to a term here or is listed under the YAML's `unmapped` with its reason; tests/test_croissant_mapping.py
takes the material set from that code, never from a copied list, so a field that becomes material fails it until
it is mapped or listed. The other EvalConditions fields are accounted for too, so the accounting is total.

The condition terms. One cb:EvalConditions property per EvalConditions field, named as the field is, in camelCase
(`chain_of_thought` -> chainOfThought); `sampling`'s three keys are flattened to samplingTemperature, samplingTopP
and samplingSeed, because a bare nested `temperature` under the upstream @vocab would mean a schema.org term. Each
term's type and constraints are COPIED from the EvalConditions field it carries (`_record_field`), so a node
accepts exactly what a conditions record does and the two cannot drift. `materialFields` names the benchmark's
resolved material set in these terms. What a document carries is P4-S6-T03's emission: until it lands, the
documents carry the cb:EvalConditions node's reference and profile only, and these terms are declared, not filled.

Names. No term shares its name with an upstream context key or a schema.org term, because under the Croissant
context's @vocab a bare key already means the schema.org term of that name; tools/build/croissant.py's context()
refuses one at every build. So the lineage edge is `isSupersededBy` (schema.org has `supersededBy`), the headline
flag `isHeadline` (schema.org has `headline`), and the version list `benchmarkVersions` (schema.org has `version`).

The namespace host. 08 S5.8 writes `https://<host>/ns/croissant-benchmark/v1#`; no host is fixed yet and `<` is not
an IRI character, so NS_HOST is `host.invalid` (RFC 2606 reserves .invalid, so the placeholder never resolves to
somebody else's vocabulary). Fixing it is this one constant, which `bench schema gen --check` then holds the schema
and the context to.

The licence constraint (04 S5): the Croissant specification is CC BY-ND. This module names terms; it restates none
of the specification.
"""
from __future__ import annotations

import copy
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, create_model

from schema.benchmark import (Access, AggregationPolicy, EvaluationTarget, ExecutionMode, GroundTruthSource, Lineage,
                              Profile, Slug, SubmissionProcess, Text, Url)
from schema.conditions import ConditionsId, EvalConditions
from schema.entities import SubsetId, VersionTag
from schema.metric import MetricId, Optimum, ValueType
from schema.paths import type_args

NS_HOST = 'host.invalid'                                        # 08 S5.8's <host>; see the module docstring
NAMESPACE = 'https://%s/ns/croissant-benchmark/v1#' % NS_HOST
EXTENSION_VERSION = 'https://%s/ns/croissant-benchmark/v1' % NS_HOST
CROISSANT_VERSION = 'http://mlcommons.org/croissant/1.1'
PREFIX = 'cb'
SCHEMA = 'schema/generated/croissant-benchmark.schema.json'
DRAFT = 'https://json-schema.org/draft/2020-12/schema'
SCHEMA_ORG = 'https://schema.org/'
DATA_LICENCE = 'https://spdx.org/licenses/CC-BY-4.0.html'       # LICENSE-DATA; the collection is ours (05 S12)

CLASSES = ('Benchmark', 'BenchmarkCollection', 'Task', 'Metric', 'Protocol', 'EvalConditions', 'Lineage')
# term -> (the class it is a property of, the field of ours it carries; None for a node gathering several).
# taxonomy/crosswalks/croissant.yaml's `extension.terms` must equal this (tests/build/test_croissant.py).
TERMS = {
    # --- the benchmark's own Dataset node: the id, the versions, and 08 S5.8's five groups
    'benchmarkId': ('Benchmark', 'Benchmark.id'),
    'benchmarkVersions': ('Benchmark', 'Benchmark.versions'),
    'tasks': ('Benchmark', 'Benchmark.task'),
    'metrics': ('Benchmark', 'Benchmark.metrics'),
    'protocol': ('Benchmark', None),
    'conditions': ('Benchmark', None),
    'lineage': ('Benchmark', 'Benchmark.lineage'),
    # --- Task
    'input': ('Task', 'Benchmark.task.input'),
    'output': ('Task', 'Benchmark.task.output'),
    'scoring': ('Task', 'Benchmark.task.scoring'),
    'testsHiddenFromSystem': ('Task', 'Benchmark.task.tests_hidden_from_system'),
    'evaluationTarget': ('Task', 'Benchmark.evaluation_target'),
    'executionMode': ('Task', 'Benchmark.execution_mode'),
    'groundTruthSource': ('Task', 'Benchmark.ground_truth_source'),
    # --- Metric
    'isHeadline': ('Metric', 'Benchmark.headline_metric'),
    'valueType': ('Metric', 'Metric.value_type'),
    'optimum': ('Metric', 'Metric.optimum'),
    'optimumTarget': ('Metric', 'Metric.optimum_target'),
    'unbounded': ('Metric', 'Metric.unbounded'),
    # --- Protocol
    'submissionProcess': ('Protocol', 'Benchmark.governance.submission_process'),
    'dataAccess': ('Protocol', 'Benchmark.data.access'),
    'aggregationPolicy': ('Protocol', 'Benchmark.aggregation_policy'),
    'subsets': ('Protocol', 'Benchmark.subsets'),
    # --- EvalConditions: the reference, the benchmark's comparability, then one term per condition field
    'conditionsId': ('EvalConditions', 'Benchmark.reference_conditions'),
    'comparabilityProfile': ('EvalConditions', 'Benchmark.comparability.profile'),
    'materialFields': ('EvalConditions', 'Benchmark.comparability'),
    'ratingPoolRequired': ('EvalConditions', 'Benchmark.comparability.rating_pool_required'),
    'shots': ('EvalConditions', 'EvalConditions.shots'),
    'shotSelection': ('EvalConditions', 'EvalConditions.shot_selection'),
    'chainOfThought': ('EvalConditions', 'EvalConditions.chain_of_thought'),
    'reasoningEffort': ('EvalConditions', 'EvalConditions.reasoning_effort'),
    'thinkingTokenBudget': ('EvalConditions', 'EvalConditions.thinking_token_budget'),
    'promptTemplateHash': ('EvalConditions', 'EvalConditions.prompt_template_hash'),
    'toolsAllowed': ('EvalConditions', 'EvalConditions.tools_allowed'),
    'scaffold': ('EvalConditions', 'EvalConditions.scaffold'),
    'harness': ('EvalConditions', 'EvalConditions.harness'),
    'maxSteps': ('EvalConditions', 'EvalConditions.max_steps'),
    'messageLimit': ('EvalConditions', 'EvalConditions.message_limit'),
    'tokenLimit': ('EvalConditions', 'EvalConditions.token_limit'),
    'sandbox': ('EvalConditions', 'EvalConditions.sandbox'),
    'samplingTemperature': ('EvalConditions', 'EvalConditions.sampling.temperature'),
    'samplingTopP': ('EvalConditions', 'EvalConditions.sampling.top_p'),
    'samplingSeed': ('EvalConditions', 'EvalConditions.sampling.seed'),
    'nSamples': ('EvalConditions', 'EvalConditions.n_samples'),
    'selectionStrategy': ('EvalConditions', 'EvalConditions.selection_strategy'),
    'k': ('EvalConditions', 'EvalConditions.k'),
    'retriesAllowed': ('EvalConditions', 'EvalConditions.retries_allowed'),
    'maxOutputTokens': ('EvalConditions', 'EvalConditions.max_output_tokens'),
    'contextWindowUsed': ('EvalConditions', 'EvalConditions.context_window_used'),
    'providerSnapshot': ('EvalConditions', 'EvalConditions.provider_snapshot'),
    'providerSnapshotAvailable': ('EvalConditions', 'EvalConditions.provider_snapshot_available'),
    'judgeModel': ('EvalConditions', 'EvalConditions.judge_model'),
    'judgeModelVersion': ('EvalConditions', 'EvalConditions.judge_model_version'),
    'judgePromptHash': ('EvalConditions', 'EvalConditions.judge_prompt_hash'),
    'gradingRubricRef': ('EvalConditions', 'EvalConditions.grading_rubric_ref'),
    'humanInLoop': ('EvalConditions', 'EvalConditions.human_in_loop'),
    'humanAssistance': ('EvalConditions', 'EvalConditions.human_assistance'),
    'userSimulator': ('EvalConditions', 'EvalConditions.user_simulator'),
    'userSimulatorVersion': ('EvalConditions', 'EvalConditions.user_simulator_version'),
    'simulator': ('EvalConditions', 'EvalConditions.simulator'),
    'simulatorVersion': ('EvalConditions', 'EvalConditions.simulator_version'),
    'hardwarePlatform': ('EvalConditions', 'EvalConditions.hardware_platform'),
    'venue': ('EvalConditions', 'EvalConditions.venue'),
    'assayProtocol': ('EvalConditions', 'EvalConditions.assay_protocol'),
    'targetConstruct': ('EvalConditions', 'EvalConditions.target_construct'),
    'activityThreshold': ('EvalConditions', 'EvalConditions.activity_threshold'),
    'leadTime': ('EvalConditions', 'EvalConditions.lead_time'),
    'resolutionWindow': ('EvalConditions', 'EvalConditions.resolution_window'),
    'eligibilityTrack': ('EvalConditions', 'EvalConditions.eligibility_track'),
    'trainingDataPolicy': ('EvalConditions', 'EvalConditions.training_data_policy'),
    'trainingDataEligibility': ('EvalConditions', 'EvalConditions.training_data_eligibility'),
    'decontaminationApplied': ('EvalConditions', 'EvalConditions.decontamination_applied'),
    'subsetUsed': ('EvalConditions', 'EvalConditions.subset_used'),
    'hardware': ('EvalConditions', 'EvalConditions.hardware'),
    'wallClockHours': ('EvalConditions', 'EvalConditions.wall_clock_hours'),
    'costUsd': ('EvalConditions', 'EvalConditions.cost_usd'),
    'dateEvaluated': ('EvalConditions', 'EvalConditions.date_evaluated'),
    # --- Lineage: each edge to a benchmark id
    'lineageRole': ('Lineage', 'Benchmark.lineage.role'),
    'supersedes': ('Lineage', 'Benchmark.lineage.supersedes'),
    'isSupersededBy': ('Lineage', 'Benchmark.lineage.superseded_by'),
    'subsetOf': ('Lineage', 'Benchmark.lineage.subset_of'),
    'extendedBy': ('Lineage', 'Benchmark.lineage.extended_by'),
    'decontaminates': ('Lineage', 'Benchmark.lineage.decontaminates'),
    'variants': ('Lineage', 'Benchmark.lineage.variants'),
    'forks': ('Lineage', 'Benchmark.lineage.forks'),
}
# (class, schema.org term) -> the field of ours it carries, with the schema.org meaning.
REUSES = {
    ('Metric', 'sc:identifier'): 'Metric.id',
    ('Metric', 'sc:name'): 'Metric.name',
    ('Metric', 'sc:minValue'): 'Metric.range.min',
    ('Metric', 'sc:maxValue'): 'Metric.range.max',
}
# 04 S8's key is [benchmark_version, metric, subset] + the material condition fields: the first three, by the name
# compute() gives them, -> the Benchmark field whose entries a claim's value names.
MATERIAL_KEY = {
    'benchmark_version': 'Benchmark.versions',
    'metric': 'Benchmark.metrics',
    'subset': 'Benchmark.subsets',
}
CONDITION_TERMS = tuple(t for t, (on, ours) in TERMS.items() if ours and ours.startswith('EvalConditions.'))
ConditionTerm = Literal[CONDITION_TERMS]  # type: ignore[valid-type]

LineageRole = Lineage.model_fields['role'].annotation
DocumentName = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}\.jsonld$')]   # {Slug}.jsonld


def terms_for(field: str) -> tuple[str, ...]:
    """The condition terms carrying EvalConditions `field`: one, or sampling's three."""
    return tuple(t for t in CONDITION_TERMS if TERMS[t][1] == 'EvalConditions.' + field
                 or TERMS[t][1].startswith('EvalConditions.%s.' % field))


def _record_field(path: str) -> tuple:
    """(annotation, a copy of the FieldInfo) of `EvalConditions.<field>[.<key>]`, walked through the nested models:
    the term accepts what the record does, constraints (`ge`, patterns) included."""
    _, *names = path.split('.')
    model: type[BaseModel] = EvalConditions
    for name in names[:-1]:
        [model] = [a for a in type_args(model.model_fields[name].annotation)
                   if isinstance(a, type) and issubclass(a, BaseModel)]
    info = copy.deepcopy(model.model_fields[names[-1]])
    return info.annotation, info


# ---- the nodes ---------------------------------------------------------------------------------------------------

class _Node(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class TaskNode(_Node):
    """cb:Task: what is asked (08 S5.8 `tasks`; 15 A8's task-and-protocol row)."""
    type_: Literal['cb:Task'] = Field(alias='@type')
    input: list[Text] = Field(default_factory=list)
    output: Text | None = None
    scoring: Text | None = None
    testsHiddenFromSystem: bool | None = None
    evaluationTarget: EvaluationTarget
    executionMode: ExecutionMode | None = None
    groundTruthSource: GroundTruthSource | None = None


class MetricNode(_Node):
    """cb:Metric: a metric with its range and direction (08 S5.8 `metrics`). A named scoring note has a name only."""
    type_: Literal['cb:Metric'] = Field(alias='@type')
    identifier: MetricId | None = None
    name: Text
    isHeadline: bool
    valueType: ValueType | None = None
    optimum: Optimum | None = None
    optimumTarget: float | None = None
    minValue: float | None = None
    maxValue: float | None = None
    unbounded: bool | None = None


class ProtocolNode(_Node):
    """cb:Protocol: how a result is produced and admitted (08 S5.8 `protocol`), and the subsets a result is reported
    on, each by its id (08 S5.8's splits, whether a subset is a data split or a task variant)."""
    type_: Literal['cb:Protocol'] = Field(alias='@type')
    submissionProcess: list[SubmissionProcess] = Field(default_factory=list)
    dataAccess: Access
    aggregationPolicy: AggregationPolicy
    subsets: list[SubsetId] = Field(default_factory=list)


class _ConditionsBase(_Node):
    type_: Literal['cb:EvalConditions'] = Field(alias='@type')
    conditionsId: ConditionsId | None = None
    comparabilityProfile: Profile | None = None
    materialFields: list[ConditionTerm] = Field(default_factory=list)
    ratingPoolRequired: bool | None = None


ConditionsNode = create_model(
    'ConditionsNode', __base__=_ConditionsBase,
    __doc__=('cb:EvalConditions (08 S5.8 `conditions`): the reference to our EvalConditions entity, the benchmark\'s '
             'comparability profile, its resolved material set as condition terms and whether a claim needs a rating '
             'pool, and one term per condition field, typed as the EvalConditions field it carries.'),
    **{t: _record_field(TERMS[t][1]) for t in CONDITION_TERMS})


class LineageNode(_Node):
    """cb:Lineage: supersession, subset, extension, decontamination, variant and fork edges (08 S5.8 `lineage`)."""
    type_: Literal['cb:Lineage'] = Field(alias='@type')
    lineageRole: LineageRole = None
    supersedes: list[Slug] = Field(default_factory=list)
    isSupersededBy: list[Slug] = Field(default_factory=list)
    subsetOf: Slug | None = None
    extendedBy: list[Slug] = Field(default_factory=list)
    decontaminates: Slug | None = None
    variants: list[Slug] = Field(default_factory=list)
    forks: list[Slug] = Field(default_factory=list)


# ---- the documents -----------------------------------------------------------------------------------------------

# The @context: the upstream keys are allowed through unchecked (they are mlcroissant's), ours are pinned.
Context = create_model(
    'Context', __config__=ConfigDict(extra='allow', populate_by_name=True),
    vocab=(Literal[SCHEMA_ORG], Field(alias='@vocab')), sc=(Literal[SCHEMA_ORG], ...),
    cb=(Literal[NAMESPACE], ...), **{t: (Literal['%s:%s' % (PREFIX, t)], ...) for t in TERMS})
ConformsTo = tuple[Literal[CROISSANT_VERSION], Literal[EXTENSION_VERSION]]


class BenchmarkDocument(_Node):
    """One benchmark's document: build/croissant-benchmark/{id}.jsonld."""
    context: Context = Field(alias='@context')
    type_: tuple[Literal['sc:Dataset'], Literal['cb:Benchmark']] = Field(alias='@type')
    conformsTo: ConformsTo
    name: Text
    description: str | None = None
    alternateName: list[Text] = Field(default_factory=list)
    url: Url
    license: Text | None = None
    keywords: list[Text] = Field(default_factory=list)
    subjectOf: Url | None = None
    benchmarkId: Slug
    benchmarkVersions: list[VersionTag] = Field(default_factory=list)
    tasks: list[TaskNode] = Field(min_length=1)
    metrics: list[MetricNode] = Field(default_factory=list)
    protocol: ProtocolNode
    conditions: ConditionsNode | None = None
    lineage: LineageNode | None = None


class Part(_Node):
    """One entry of the collection's hasPart: a benchmark document, by its file name beside the collection. Typed
    cb:Benchmark alone: mlcroissant takes whichever schema.org Dataset node rdflib lists first for the document's
    own, so a document holds exactly one."""
    id_: DocumentName = Field(alias='@id')
    type_: Literal['cb:Benchmark'] = Field(alias='@type')
    name: Text
    benchmarkId: Slug


class CollectionDocument(_Node):
    """The catalogue's document: build/croissant-benchmark/_collection.jsonld."""
    context: Context = Field(alias='@context')
    type_: tuple[Literal['sc:Dataset'], Literal['cb:BenchmarkCollection']] = Field(alias='@type')
    conformsTo: ConformsTo
    name: Text
    description: Text
    url: Url
    license: Literal[DATA_LICENCE]
    citeAs: Text
    hasPart: list[Part] = Field(default_factory=list)


def json_schema() -> dict:
    """The generated extension schema (tools/build/codegen.py writes it to SCHEMA): either document, by $ref."""
    body = TypeAdapter(Union[BenchmarkDocument, CollectionDocument]).json_schema(mode='validation', by_alias=True)
    return {'$schema': DRAFT, '$comment': 'Generated by `bench schema gen` from schema/croissant_benchmark.py. Do not '
            'edit.', 'title': 'croissant-benchmark', **body}
