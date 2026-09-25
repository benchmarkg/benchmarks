"""EvalConditions (P0-S4-T06; 04-data-model.md S8, 13-execution-runners.md S4.5).

One file per condition set at data/conditions/{id}.yaml, shared by the claims that ran under it.
The comparability arithmetic that reads these records -- the profile resolver, `comparability_key`,
`key_unknown_count`, `condition_completeness` -- is derived, so it lives in the build
(tools/build/comparability.py), never in the YAML (04 S1).

The rules this model carries:

  - EVERY FIELD DEFAULTS TO NULL. `condition_completeness` counts a material field as answered when
    it is not None, so a default of `false` or `0` would answer a question nobody asked and inflate
    every score. 04 S8's example shows `human_in_loop: false` and `retries_allowed: 0` because that
    record answered them, not because they are defaults. An empty list is an answer too:
    `tools_allowed: []` says "no tools", `null` says nobody looked.
  - `reasoning_effort` is the enum 04 S15 item 4 seeds from Epoch's observed suffixes
    (none|minimal|low|medium|high|xhigh|max, and `unknown` -> null), and `reasoning_effort_raw` is the
    provider's verbatim string, always preserved: an enum value with no raw string is rejected, and a
    raw string the enum cannot hold keeps the enum null. 04 S14: vendors' `high`s are not the same
    `high`, which is why the raw string is kept.
  - `provider_snapshot` + `provider_snapshot_available` (13 S4.5). "The schema penalises unknowns, not
    absences": `provider_snapshot_available: false` is an answer -- the provider publishes no dated
    snapshot -- and a snapshot id beside it is a contradiction. The same shape applies to any field
    that gains an `*_available` or `*_applicable` companion; COMPANIONS lists them.
  - The environment block carries `target_construct` and `activity_threshold` beside 04 S8's list,
    because 04 S13's CACHE record names both as part of that block and as material_extra.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.system import SourceId, SystemRef, Text

ConditionsId = Annotated[str, StringConstraints(pattern=r'^cond-[0-9a-f]{12}$')]
PromptHash = Annotated[str, StringConstraints(pattern=r'^sha256:[0-9a-f]{64}$')]

REASONING_EFFORTS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')
ReasoningEffort = Literal[REASONING_EFFORTS]  # type: ignore[valid-type]
ShotSelection = Literal['fixed', 'random', 'retrieved']
SelectionStrategy = Literal['single', 'best-of-n', 'self-consistency', 'majority-vote', 'pass-at-k', 'pass-hat-k',
                            'avg-at-k', 'best-across-scorers']
HumanAssistance = Literal['none', 'permitted', 'required']
TrainingDataPolicy = Literal['open', 'restricted-list', 'zero-shot-only', 'undeclared']

# field -> its companion boolean. A companion that is explicitly False answers the field (13 S4.5).
COMPANIONS = {'provider_snapshot': 'provider_snapshot_available'}

_K_STRATEGIES = ('best-of-n', 'pass-at-k', 'pass-hat-k', 'avg-at-k')


def parse_reasoning_effort(raw: str | None) -> str | None:
    """The enum value for a provider's effort string, or None when it names none of them. `unknown` is
    None by 04 S15 item 4; so is anything the enum does not hold, and the raw string keeps it."""
    if raw is None:
        return None
    v = raw.strip().lower()
    return v if v in REASONING_EFFORTS else None


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Sampling(Closed):
    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    seed: int | None = None


class EvalConditions(Closed):
    id: ConditionsId

    # --- prompting
    shots: int | None = Field(default=None, ge=0)
    shot_selection: ShotSelection | None = None
    chain_of_thought: bool | None = None
    reasoning_effort: ReasoningEffort | None = None
    reasoning_effort_raw: Text | None = None
    thinking_token_budget: int | None = Field(default=None, ge=0)
    prompt_template_hash: PromptHash | None = None
    prompt_template_source: SourceId | None = None

    # --- agency and tools
    tools_allowed: list[Text] | None = None
    scaffold: SystemRef | None = None
    scaffold_source: SourceId | None = None
    harness: Text | None = None
    harness_source: SourceId | None = None
    max_steps: int | None = Field(default=None, ge=1)
    message_limit: int | None = Field(default=None, ge=1)
    token_limit: int | None = Field(default=None, ge=1)
    sandbox: Text | None = None

    # --- sampling and selection
    sampling: Sampling | None = None
    n_samples: int | None = Field(default=None, ge=1)
    selection_strategy: SelectionStrategy | None = None
    k: int | None = Field(default=None, ge=1)
    retries_allowed: int | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    context_window_used: int | None = Field(default=None, ge=1)

    # --- the endpoint (13 S4.5; material on the hosted-api profile only)
    provider_snapshot: Text | None = None
    provider_snapshot_available: bool | None = None

    # --- grading
    judge_model: SystemRef | None = None
    judge_model_version: Text | None = None
    judge_prompt_hash: PromptHash | None = None
    grading_rubric_ref: Text | None = None
    human_in_loop: bool | None = None
    human_assistance: HumanAssistance | None = None

    # --- environment (non-LLM domains)
    simulator: Text | None = None
    simulator_version: Text | None = None
    hardware_platform: Text | None = None
    venue: Text | None = None
    assay_protocol: SourceId | None = None
    target_construct: Text | None = None         # 04 S13 (CACHE)
    activity_threshold: Text | None = None       # 04 S13 (CACHE)
    lead_time: Text | None = None
    resolution_window: Text | None = None

    # --- eligibility
    eligibility_track: Text | None = None
    training_data_policy: TrainingDataPolicy | None = None
    decontamination_applied: bool | None = None
    subset_used: Text | None = None

    # --- cost and provenance of the run
    hardware: Text | None = None
    wall_clock_hours: float | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    date_evaluated: date | None = None

    @model_validator(mode='after')
    def _effort(self):
        if self.reasoning_effort is not None and self.reasoning_effort_raw is None:
            raise ValueError('%s: reasoning_effort without reasoning_effort_raw -- the verbatim provider string is '
                             'always preserved (04 S8)' % self.id)
        return self

    @model_validator(mode='after')
    def _companions(self):
        for field, companion in COMPANIONS.items():
            if getattr(self, companion) is False and getattr(self, field) is not None:
                raise ValueError('%s: %s is false but %s is set' % (self.id, companion, field))
        return self

    @model_validator(mode='after')
    def _dependents(self):
        for dependent, on in (('judge_model_version', 'judge_model'), ('judge_prompt_hash', 'judge_model'),
                              ('simulator_version', 'simulator'), ('scaffold_source', 'scaffold'),
                              ('harness_source', 'harness'), ('prompt_template_source', 'prompt_template_hash')):
            if getattr(self, dependent) is not None and getattr(self, on) is None:
                raise ValueError('%s: %s without %s' % (self.id, dependent, on))
        if self.k is not None and self.selection_strategy not in (None,) + _K_STRATEGIES:
            raise ValueError('%s: k is meaningless under selection_strategy %s' % (self.id, self.selection_strategy))
        return self

    def answered(self, field: str) -> bool:
        """Whether `field` was answered: set, or declared absent through its companion (13 S4.5).
        `false` is not None, and a companion that says `false` answers the field it accompanies."""
        if getattr(self, field) is not None:
            return True
        companion = COMPANIONS.get(field)
        return companion is not None and getattr(self, companion) is False

    def value(self, field: str) -> Any:
        v = getattr(self, field)
        return v.model_dump() if isinstance(v, BaseModel) else v


FIELDS = tuple(f for f in EvalConditions.model_fields if f != 'id')
