"""BenchmarkStub and the Epoch id allocation (P3-S2-T07; 07 S2.4, 14 Phase 3, 04 S3).

07 S2.4: "Benchmark drafts are therefore stubs with `id`, `name`, `aliases`, `release_date`,
`homepage`, `chance_baseline`, `score_ceiling` and `superseded_by`, every facet `null`, withheld from
the published build until a human assigns domain facets." 14 Phase 3 adds `verification_status:
unreviewed`. That is not a Benchmark at 04 S5's `stub` level, which already requires a domain, a
tagline, learned-entrant evidence and an evaluation target, so a stub is its own entity:

  - it lives at data/benchmarks/_stubs/<id>.yaml, never in a family directory, and the build
    refuses to publish it (tools/build/artifacts.py reports it as excluded);
  - every facet of 02 S2 is present and null -- the type admits nothing else, so a stub with a facet
    filled in is not a stub any more and must be promoted to data/benchmarks/<family>/<id>.yaml;
  - `curation.verification_status` is `unreviewed`, a value only a stub can hold: it sits below 05
    S4's ladder rather than on it, because no one has reviewed anything about the benchmark yet;
  - the Epoch facts are kept per Epoch row (`epoch[]`), because one benchmark can be several Epoch
    rows (FrontierMath is four) with different baselines, ceilings and dates. `released` is Epoch's
    release_date only for a benchmark that is exactly one unversioned, unsubsetted row; otherwise
    Epoch's date belongs to a version or a snapshot, not to the benchmark, and the stub says null.

07's `release_date` is spelled `released`, Benchmark's name for it (04 S5), so promotion renames
nothing. `homepage` is null until a curator finds one: Epoch's metadata carries none, and a stub
states only what its source states.

The allocation file (ingest/mappings/epoch/_id_allocation.yaml) is where the ids are decided: one
row per Epoch `benchmark` string, mapping it to a benchmark id and, where the string names one, a
version or a subset. 04 S3: "Adapters may never allocate an id"; a row is a human decision once
`ratified_by` names who made it. tools/validate/tiers.py holds stubs and allocation together.
"""
from __future__ import annotations

import glob
import os
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.benchmark import Slug, SourceId, Text, Url
from schema.entities import SubsetId, VersionTag

STUB_DIR = '_stubs'                            # data/benchmarks/_stubs/
STUB_STATUS = 'unreviewed'
FACETS = ('domain', 'capability', 'evaluation_method', 'designed_for_subjects', 'data', 'lifecycle',
          'governance', 'execution')              # 02 S2's eight facets, as Benchmark spells them


def curated_files(root: str, kind: str) -> list[str]:
    """Every data/<kind>/**/*.yaml the curated model reads, never data/<kind>/_stubs/. Each loader that
    walks data/benchmarks/ or data/systems/ for curated records goes through this, so a stub never
    reaches a model it does not fit."""
    stubs = os.sep + os.path.join(kind, STUB_DIR) + os.sep
    return [p for p in sorted(glob.glob(os.path.join(root, 'data', kind, '**', '*.yaml'), recursive=True))
            if stubs not in os.path.normpath(p)]


def curated_benchmark_files(root: str) -> list[str]:
    """data/benchmarks/**/*.yaml without _stubs/ (P3-S2-T07)."""
    return curated_files(root, 'benchmarks')


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class EpochRow(Closed):
    """One row of Epoch's benchmark_metadata.csv, as Epoch wrote it, and where it lands in this benchmark."""
    benchmark: Text                          # Epoch's `benchmark` string, verbatim (external_ids.epoch)
    version: VersionTag | None = None        # the version of this benchmark the row is, if it is one
    subset: SubsetId | None = None           # the subset of this benchmark the row is, if it is one
    in_eci: bool
    source_file: Text | None = None
    score_column: Text | None = None
    released: date | None = None             # Epoch's release_date
    chance_baseline: float | None = None     # Epoch's random_baseline
    score_ceiling: float | None = None       # Epoch's score_ceiling: a measurement ceiling (04 S6)
    superseded_by: Text | None = None        # Epoch's superseded_by: an Epoch string, not an id


class StubCuration(Closed):
    added_by: Text
    added_on: date
    verification_status: Literal['unreviewed'] = STUB_STATUS
    sources: list[SourceId] = Field(min_length=1)
    notes: Text | None = None


class BenchmarkStub(Closed):
    id: Slug
    name: Text
    aliases: list[Text] = Field(default_factory=list)
    released: date | None = None
    homepage: Url | None = None
    epoch: list[EpochRow] = Field(min_length=1)

    domain: None = None
    capability: None = None
    evaluation_method: None = None
    designed_for_subjects: None = None
    data: None = None
    lifecycle: None = None
    governance: None = None
    execution: None = None

    curation: StubCuration

    @model_validator(mode='after')
    def _rows(self):
        names = [r.benchmark for r in self.epoch]
        if len(set(names)) != len(names):
            raise ValueError('%s: an Epoch row is listed twice' % self.id)
        for r in self.epoch:
            if r.subset is not None and r.subset.split('#')[0] != self.id:
                raise ValueError('%s: Epoch row %r names subset %s of another benchmark'
                                 % (self.id, r.benchmark, r.subset))
        single = len(self.epoch) == 1 and self.epoch[0].version is None and self.epoch[0].subset is None
        if self.released is not None and not (single and self.released == self.epoch[0].released):
            raise ValueError('%s: released is Epoch\'s release_date only for a single unversioned, unsubsetted '
                             'row; otherwise that date belongs to a version or subset' % self.id)
        return self


class Allocation(Closed):
    """One Epoch string's identity decision (04 S3 "Id allocation is a human act")."""
    epoch: Text                               # Epoch's `benchmark` string, verbatim
    benchmark: Slug                           # the permanent id
    name: Text | None = None                  # the stub's name, where no one Epoch string is it (FrontierMath)
    version: VersionTag | None = None
    subset: SubsetId | None = None
    existing: bool = False                    # the id is already a curated data/benchmarks/ entry
    rationale: Text
    proposed_by: Text
    ratified_by: Text | None = None           # the human who made the decision; null = still a proposal
    ratified_on: date | None = None

    @model_validator(mode='after')
    def _shape(self):
        if self.subset is not None and self.subset.split('#')[0] != self.benchmark:
            raise ValueError('%s: subset %s is not a subset of %s' % (self.epoch, self.subset, self.benchmark))
        if (self.ratified_by is None) != (self.ratified_on is None):
            raise ValueError('%s: ratified_by and ratified_on are given together' % self.epoch)
        return self


class AllocationFile(Closed):
    version: Text
    source: SourceId
    added_on: date                            # the stubs' curation.added_on, so emission is reproducible
    rules: list[Text] = Field(min_length=1)
    allocations: list[Allocation] = Field(min_length=1)

    @model_validator(mode='after')
    def _unique(self):
        seen = [a.epoch for a in self.allocations]
        if len(set(seen)) != len(seen):
            raise ValueError('an Epoch string is allocated twice')
        return self


# ---- System and Organization stubs (P3-S3-T04; 04 S7, 07 S5) ------------------------------------
#
# The same reasoning as BenchmarkStub, applied to Epoch's model registry (model_metadata.csv). A System
# at 04 S7 needs a `system_type` and an `availability`, and an Organization a `kind`; Epoch's registry
# states none of them (it has no base/instruct/reasoning split, no retirement dates, no organisation
# types), so filling them would be guessing. A stub holds exactly what Epoch states, those fields are
# present and null, and a curator promotes the file to data/systems/<id>.yaml or
# data/organizations/<id>.yaml when the gaps are filled from the system's own sources.
#
# Identity is a human review recorded per file (the task's verify): `identity.reviewed_by` is null
# until a person has confirmed the Epoch strings in the file are one system (or one organisation) and
# that none of them is another file's.

SystemId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9.-]{0,62}$')]
OrgRef = Annotated[str, StringConstraints(pattern=r'^org-[a-z0-9]+(-[a-z0-9]+)*$')]


def stub_files(root: str, kind: str) -> list[str]:
    """data/<kind>/_stubs/*.yaml, in path order."""
    return sorted(glob.glob(os.path.join(root, 'data', kind, STUB_DIR, '*.yaml')))


class IdentityReview(Closed):
    proposed_by: Text
    reviewed_by: Text | None = None           # the person who confirmed this file is one entity
    reviewed_on: date | None = None
    note: Text | None = None                  # what the reviewer should look at first

    @model_validator(mode='after')
    def _pair(self):
        if (self.reviewed_by is None) != (self.reviewed_on is None):
            raise ValueError('identity: reviewed_by and reviewed_on are given together')
        return self


class EpochModelRow(Closed):
    """One model_metadata.csv row: a registry `model_version`, verbatim. Not a SystemVersion yet --
    splitting provider prefixes and effort suffixes off it is the resolver's (04 S10 step 4)."""
    model_version: Text
    display_name: Text | None = None
    released: date | None = None              # Epoch's `date`


class EpochSystem(Closed):
    model_groups: list[Text] = Field(min_length=1)    # Epoch's model_group string(s), verbatim
    organization: Text | None = None          # Epoch's `organization` as written (a joint value is one string)
    country: Text | None = None               # Epoch's `country` as written
    accessibility: Text | None = None         # Epoch's `accessibility` as written
    versions: list[EpochModelRow] = Field(min_length=1)


class SystemStub(Closed):
    id: SystemId
    name: Text
    aliases: list[Text] = Field(default_factory=list)
    organizations: list[OrgRef] = Field(default_factory=list)   # Epoch's organization string, split on commas
    system_type: None = None                  # not stated by Epoch
    availability: None = None                 # not stated by Epoch
    training_compute_flop: float | None = Field(default=None, gt=0)
    training_compute_estimated: bool | None = None
    training_compute_notes: Text | None = None
    training_compute_from: Literal['model_metadata', 'notes'] | None = None
    external_ids: dict[Text, Text] = Field(default_factory=dict)
    epoch: EpochSystem
    curation: StubCuration
    identity: IdentityReview

    @model_validator(mode='after')
    def _compute(self):
        if self.training_compute_flop is None:
            if self.training_compute_estimated is not None or self.training_compute_from is not None:
                raise ValueError('%s: training_compute_estimated/_from without a training_compute_flop' % self.id)
            return self
        if self.training_compute_from is None:
            raise ValueError('%s: a training_compute_flop says where it came from' % self.id)
        notes = self.training_compute_notes or ''
        if 'imput' in notes.lower() and self.training_compute_estimated is not True:
            raise ValueError('%s: the notes say the compute was imputed, so training_compute_estimated is true '
                             '(04 S7: imputed compute is never plotted against benchmark scores)' % self.id)
        if self.training_compute_from == 'notes' and 'imput' not in notes.lower():
            raise ValueError('%s: a figure is read from the notes only where they say it was imputed, and '
                             'keeps them' % self.id)
        return self


class EpochOrganization(Closed):
    written_as: list[Text] = Field(min_length=1)   # every Epoch `organization` string this name appears in


class OrganizationStub(Closed):
    id: OrgRef
    name: Text                                # the name as Epoch writes it
    kind: None = None                         # not stated by Epoch
    country: None = None                      # Epoch's country is per model, not per organisation
    homepage: None = None
    epoch: EpochOrganization
    curation: StubCuration
    identity: IdentityReview
