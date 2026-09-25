"""Dispute (P0-S4-T07; 05-repository-and-workflow.md S8, 12-analytics-and-trends.md S3.3).

One file per dispute at data/disputes/{id}.yaml. "Disputes are never resolved by deletion": the
contested claim stays, gains an entry in `disputed_by[]`, and renders with both positions visible --
the claim's number with its source, and the dispute with its own.

The fields are 05 S8's, plus the three this task's step names that 05's sketch leaves implicit:

  - `claim_sources[]`: the sources behind the contested figure, so the record states BOTH positions
    with their sources (the disputant's are `evidence[]`) without the reader opening the claim.
  - `resolved_on`: required exactly when `status` is not `open`, and not before `raised_on`.
  - `corrected_by`: the claim that replaced the contested one, required exactly when `status` is
    `resolved-claim-corrected`. The original is then superseded, which 12 S3.3 excludes separately.

`disputant_relationship` is shown on the site: "an organisation contesting its own score is useful
information, and so is the fact that it is the one contesting."

12 S3.3's SOTA rule excludes a claim that is "disputed". `is_standing` is what it reads: only an
`open` dispute makes a claim disputed. A dispute that was resolved (either way) or withdrawn does not,
and `claim_is_disputed()` applies that over a set of records.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema.claim import ClaimId
from schema.system import SourceId, Text

DisputeId = Annotated[str, StringConstraints(pattern=r'^dispute-[a-z0-9]+(-[a-z0-9]+)*$')]
DisputeStatus = Literal['open', 'resolved-claim-corrected', 'resolved-claim-retained', 'withdrawn']
DisputantRelationship = Literal['evaluated-party', 'benchmark-maintainer', 'third-party', 'unknown']


class Dispute(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: DisputeId
    concerns: ClaimId
    raised_by: Text                            # an org id, a handle, or `redacted` on request (05 S8.1)
    disputant_relationship: DisputantRelationship
    raised_on: date
    position: Text
    evidence: list[SourceId] = Field(min_length=1)
    claim_sources: list[SourceId] = Field(min_length=1)
    our_response: Text | None = None
    status: DisputeStatus = 'open'
    resolved_on: date | None = None
    corrected_by: ClaimId | None = None

    @property
    def is_standing(self) -> bool:
        """True while the dispute is open: the one state in which 12 S3.3 reads the claim as disputed."""
        return self.status == 'open'

    @model_validator(mode='after')
    def _lifecycle(self):
        if self.status == 'open' and self.resolved_on is not None:
            raise ValueError('%s: an open dispute has no resolved_on' % self.id)
        if self.status != 'open':
            if self.resolved_on is None:
                raise ValueError('%s: status %s needs resolved_on' % (self.id, self.status))
            if self.resolved_on < self.raised_on:
                raise ValueError('%s: resolved_on %s is before raised_on %s' % (self.id, self.resolved_on, self.raised_on))
            if not self.our_response:
                raise ValueError('%s: a closed dispute states our_response' % self.id)
        if (self.status == 'resolved-claim-corrected') != (self.corrected_by is not None):
            raise ValueError('%s: corrected_by is given exactly when status is resolved-claim-corrected' % self.id)
        if self.corrected_by == self.concerns:
            raise ValueError('%s: a claim cannot be corrected by itself' % self.id)
        return self


def claim_is_disputed(claim_id: str, disputes: Iterable[Dispute]) -> bool:
    """12 S3.3's test: a claim is disputed while any dispute concerning it is open."""
    return any(d.concerns == claim_id and d.is_standing for d in disputes)
