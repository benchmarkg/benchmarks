"""System and SystemVersion (P0-S4-T05; 04-data-model.md S7, S15 items 3 and 14).

A System is a model, agent, pipeline, policy, classical algorithm or human team that gets evaluated.
Deliberately thin (constraint 5): only what is needed to interpret a result. One file per system at
data/systems/{id}.yaml; a claim refers to `{system}@{version}` or to the bare system id.

The fields that carry a rule, and the rule:

  - Training compute (04 S15 item 3, a C5 pre-ingest addition). `training_compute_flop` with
    `training_compute_estimated` and the verbatim `training_compute_notes`. Epoch's notes separate
    honest arithmetic from compute "imputed ... from benchmark scores", and the second must never be
    plotted against benchmark scores. So: a FLOP figure must say whether it is estimated; an estimate
    must keep its notes; a figure that is neither disclosed nor estimated is not a figure.
  - `parameters_disclosed` is distinct from `parameter_count`: "not disclosed" is a state, not a small
    number. An undisclosed count must be null.
  - `availability` and `retired_on` (04 S15 item 14): `retired_on` is required exactly when the
    system is `deprecated` or `retired`.
  - An `agent-scaffold` is a System with a populated `built_on`, because "which base model was under
    the scaffold" is the first question every reader has.

`system_type` is the subject-under-test vocabulary (taxonomy/subjects.yaml, 04 S7's "facet 4").
"""
from __future__ import annotations

import os
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.taxonomy import load_taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODELS, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))

SystemType = Literal[tuple(t.id for t in _MODELS['subjects.yaml'].terms if t.status != 'retired')]  # type: ignore[valid-type]
SystemId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9.-]{0,62}$')]
# `{system}@{version}` or a bare system id.
SystemRef = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9.-]{0,62}(@[A-Za-z0-9][A-Za-z0-9._-]*)?$')]
OrgRef = Annotated[str, StringConstraints(pattern=r'^org-[a-z0-9]+(-[a-z0-9]+)*$')]
SourceId = Annotated[str, StringConstraints(pattern=r'^src-[a-z0-9]+(-[a-z0-9]+)*$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

LicenceClass = Literal['api-access', 'hosted-no-api', 'open-unrestricted', 'open-restricted', 'open-noncommercial',
                       'unreleased']
Availability = Literal['generally-available', 'limited-preview', 'research-only', 'deprecated', 'retired',
                       'never-released']


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SystemVersion(Closed):
    version: Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    released: date | None = None
    api_identifier: Text | None = None
    deprecated: bool = False
    notes: str | None = None


class System(Closed):
    id: SystemId
    name: Text
    organization: OrgRef | None = None     # null for a human team with no organisational home
    system_type: SystemType
    modalities_in: list[Text] = Field(default_factory=list)
    modalities_out: list[Text] = Field(default_factory=list)
    open_weights: bool | None = None
    license: Text | None = None
    license_class: LicenceClass | None = None
    api_identifier: Text | None = None
    first_released: date | None = None
    built_on: list[SystemRef] = Field(default_factory=list)
    parameters_disclosed: bool = False
    parameter_count: int | None = Field(default=None, ge=1)
    training_compute_disclosed: bool = False
    training_compute_flop: float | None = Field(default=None, gt=0)
    training_compute_estimated: bool | None = None
    training_compute_notes: Text | None = None
    availability: Availability
    retired_on: date | None = None
    external_ids: dict[Text, str | None] = Field(default_factory=dict)
    versions: list[SystemVersion] = Field(default_factory=list)
    sources: list[SourceId] = Field(min_length=1)

    @model_validator(mode='after')
    def _parameters(self):
        if self.parameter_count is not None and not self.parameters_disclosed:
            raise ValueError('%s: parameter_count without parameters_disclosed -- an undisclosed count is null (04 S7)'
                             % self.id)
        return self

    @model_validator(mode='after')
    def _compute(self):
        flop, est = self.training_compute_flop, self.training_compute_estimated
        if flop is None:
            if est is not None or self.training_compute_notes:
                raise ValueError('%s: training_compute_estimated/notes without a training_compute_flop' % self.id)
            return self
        if est is None:
            raise ValueError('%s: a training_compute_flop must say whether it is estimated (04 S7)' % self.id)
        if est and not self.training_compute_notes:
            raise ValueError('%s: an estimated training_compute_flop keeps its verbatim notes, which say whether it '
                             'was imputed from benchmark scores (04 S7)' % self.id)
        if not est and not self.training_compute_disclosed:
            raise ValueError('%s: a training_compute_flop that is neither disclosed nor estimated' % self.id)
        return self

    @model_validator(mode='after')
    def _availability(self):
        retired = self.availability in ('deprecated', 'retired')
        if retired and self.retired_on is None:
            raise ValueError('%s: availability %s needs retired_on (04 S7)' % (self.id, self.availability))
        if not retired and self.retired_on is not None:
            raise ValueError('%s: retired_on on a system that is %s' % (self.id, self.availability))
        return self

    @model_validator(mode='after')
    def _scaffold(self):
        if self.system_type == 'agent-scaffold' and not self.built_on:
            raise ValueError('%s: an agent-scaffold names what it is built on (04 S7)' % self.id)
        return self

    def compute_is_independent_of_scores(self) -> bool:
        """False for compute imputed from benchmark scores, which 12's analytics must exclude. Read from
        the verbatim notes, conservatively: any estimate whose notes mention benchmark scores is out."""
        if self.training_compute_flop is None:
            return False
        notes = (self.training_compute_notes or '').lower()
        return not (self.training_compute_estimated and 'benchmark' in notes and 'score' in notes)
