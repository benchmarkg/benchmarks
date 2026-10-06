"""The promotion record: who raised a record's curation.verification_status, when, against what (P1-S2-T10).

05 S3: `bench promote <path...> --to <verification_status> --evidence <src-id>` raises a record up 05 S4's
six-value ladder, "recording who, when, and against which evidence". The record's own `curation` block has no
field for who promoted it, and adding one is a schema change (05 S5: two reviewers and an ADR), so each
promotion is its own file, beside the data it changed:

    data/_curation/promotions/<yyyy-mm-dd>-<entity id>-<nnn>.yaml

One file per promotion, never edited: the log is append-only by construction, the way taxonomy/_failures/ is.
05 S5's review matrix needs the promoter not to be the record's author, and the evidence to be cited; the
model holds what a single file can (a real rise up the ladder, never to a status only an adapter or a draft
holds, and a named reviewer for the two rungs that are someone else's sign-off), and tools/promote.py holds
the rest against the record itself.
"""
from __future__ import annotations

import re
import typing
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.benchmark import VerificationStatus
from schema.system import SourceId, Text

LADDER: tuple[str, ...] = typing.get_args(VerificationStatus)      # 05 S4, lowest first
NOT_A_TARGET = {
    'ai-drafted-unverified': 'promotion never makes a record a draft',
    'machine-ingested': 'only an ingestion adapter assigns machine-ingested (05 S4)',
}
NEEDS_REVIEWER = ('expert-reviewed', 'maintainer-confirmed')    # someone outside the team signed it off
PROMOTION_NAME = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]*)-(\d{3})$')
DataPath = Annotated[str, StringConstraints(pattern=r'^data/[a-z0-9_./-]+\.yaml$')]


class Promotion(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    entity: DataPath
    entity_id: Text
    from_: VerificationStatus = Field(alias='from')
    to: VerificationStatus
    by: Text
    on: date
    evidence: list[SourceId] = Field(min_length=1)
    reviewer: Text | None = None
    note: Text | None = None

    @model_validator(mode='after')
    def _a_real_promotion(self):
        if self.to in NOT_A_TARGET:
            raise ValueError('to %s: %s' % (self.to, NOT_A_TARGET[self.to]))
        if LADDER.index(self.to) <= LADDER.index(self.from_):
            raise ValueError('%s -> %s does not go up the ladder (%s)' % (self.from_, self.to, ' < '.join(LADDER)))
        if self.to in NEEDS_REVIEWER and not self.reviewer:
            raise ValueError('%s names the reviewer who signed it off' % self.to)
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError('evidence names a source twice')
        return self
