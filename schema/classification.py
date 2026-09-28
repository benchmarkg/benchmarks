"""Stage-3 classification records and the failure log (P1-S1-T03; 03-taxonomy-build-process.md S3.3).

Stage 3 classifies every stress-corpus entry and logs every failure. 03 S3.3 fixes the failure
record's shape. It gives no shape for the classification record, so this module defines one, and 03
S3.3 now points here.

A classification record, taxonomy/_corpus/classifications/<entry-id>.yaml, fills all nineteen facet
fields (FIELDS). The eight facets of 02 S2 expand to nineteen fields: domain has two, and data
properties, lifecycle, governance and execution have two to five each. Every field maps to a list of
assignments. An assignment is one of:

    a term      `value`, `source` (a key of the record's `sources`) and `quote`, a verbatim passage
                of that source which supports the value (03 S3.3 rule 1, "source-bound")
    epistemic   one of the few terms that state what is known rather than what the source says
                (EPISTEMIC: `contamination_risk: unknown`, `activity: unknown`, `ceiling_anchor_type:
                none-known`), which carries a `note` in place of a quote
    abstention  `value: null` and the id of the failure record that explains it (03 S3.3 rule 2)

A single-valued field takes exactly one assignment, and an abstention on a multi-valued field is its
only assignment. `[]` is accepted only where "none applies" is itself a classification (NONE_OK). 02
S11 rule 6 reads an empty `capability` as "not yet tagged", so an empty capability is refused here.
Any assignment may also cite a `failure`: a collision, or an escape hatch taken with a value still
assigned, is logged without abstaining.

A failure record, taxonomy/_failures/<yyyy-mm-dd>-<benchmark>-<nnn>.yaml, is 03 S3.3's block. It
adds optional fields: `terms[]` names the terms a collision or a two-primaries case is between,
`classification` names the record that cites it, and triage (P1-S1-T06) adds `route` (ROUTES) and,
for a failure an ADR decides, `adr`, the ADR's path. What the files must agree on is checked in
tools/validate/classifications.py: the entry is in the stress corpus; a cited failure exists and
names the same benchmark and field; no failure goes uncited; a blocking failure is routed to an ADR;
and the ADR it names exists and names it back.

What cannot be checked offline is that each quote is in its source. The source is a live URL, not a
committed Source record with an extract. The classifying agent checks every quote against the text it
fetched before committing, and the reviewer re-opens the sources.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schema import benchmark as B

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
Key = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9-]{0,31}$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
FailureId = Annotated[str, StringConstraints(pattern=r'^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*-\d{3}$')]
SemVer = Annotated[str, StringConstraints(pattern=r'^\d+\.\d+\.\d+$')]
AdrPath = Annotated[str, StringConstraints(pattern=r'^adr/\d{4}-[a-z0-9][a-z0-9-]*\.md$')]


def _terms(t) -> tuple[str, ...]:
    return get_args(t)


# field -> (vocabulary, multi-valued). The Benchmark model's own enums, so the two cannot disagree.
FIELDS: dict[str, tuple[tuple[str, ...], bool]] = {
    'domain.primary': (_terms(B.DomainLeaf), False),
    'domain.secondary': (_terms(B.DomainLeaf), True),
    'capability': (_terms(B.Capability), True),
    'evaluation_method': (_terms(B.EvaluationMethod), True),
    'designed_for_subjects': (_terms(B.Subject), True),
    'data.access': (_terms(B.Access), False),
    'data.refresh': (_terms(B.Refresh), False),
    'data.data_provenance': (_terms(B.DataProvenance), True),
    'data.contamination_risk': (_terms(B.ContaminationRisk), False),
    'data.ceiling_anchor_type': (_terms(B.CeilingAnchor), False),
    'lifecycle': (_terms(B.Lifecycle), False),
    'activity': (_terms(B.Activity), False),
    'governance.maintainer_type': (_terms(B.MaintainerType), False),
    'governance.submission_process': (_terms(B.SubmissionProcess), True),
    'governance.independence_flags': (_terms(B.IndependenceFlag), True),
    'execution.compute_tier': (_terms(B.ComputeTier), False),
    'execution.reproducibility_tier': (_terms(B.ReproducibilityTier), False),
    'execution.reproducibility_blockers': (_terms(B.ReproducibilityBlocker), True),
    'execution.harness_availability': (_terms(B.HarnessAvailability), False),
}
NONE_OK = frozenset({'domain.secondary', 'execution.reproducibility_blockers'})
EPISTEMIC = {'data.contamination_risk': {'unknown'}, 'activity': {'unknown'},
             'data.ceiling_anchor_type': {'none-known'}}
NEVER_HAND_SET = {('lifecycle', t) for (f, t) in B._DERIVED_TERMS if f == 'lifecycle'}
FAILURE_KINDS = ('missing-term', 'collision', 'two-primaries', 'undefined-boundary', 'escape-hatch-used',
                 'source-silent')
# Where triage (P1-S1-T06; 03 S3.3) sends a failure: an ADR decides it, homographs.yaml declares it (a
# collision whose terms sit in different facet files), or the Stage 4 revision batches it.
ROUTES = ('adr', 'homograph', 'stage-4')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Assignment(Strict):
    value: Text | None
    source: Key | None = None
    quote: Text | None = None
    note: Text | None = None
    failure: FailureId | None = None


class Classification(Strict):
    id: Slug                                    # the stress-corpus entry id; the file is <id>.yaml
    corpus_item: int = Field(ge=1)              # the entry's 1-based position in the corpus
    curator: Text
    classified_on: date
    taxonomy_version: SemVer
    sources: dict[Key, Url] = Field(min_length=1)
    facets: dict[str, list[Assignment]]
    notes: Text | None = None

    @model_validator(mode='after')
    def _every_field_filled_or_abstained(self):
        missing = [f for f in FIELDS if f not in self.facets]
        unknown = [f for f in self.facets if f not in FIELDS]
        if missing or unknown:
            raise ValueError('facets must hold exactly the %d fields: %s%s' % (
                len(FIELDS), 'missing %s' % ', '.join(missing) if missing else '',
                '%sunknown %s' % ('; ' if missing else '', ', '.join(unknown)) if unknown else ''))
        problems = []
        for field, items in self.facets.items():
            vocab, multi = FIELDS[field]
            where = 'facets.%s' % field
            if not items and field not in NONE_OK:
                problems.append('%s: empty; abstain with `value: null` and a failure instead' % where)
            if not multi and len(items) != 1:
                problems.append('%s: single-valued, takes exactly one assignment (has %d)' % (where, len(items)))
            values = [a.value for a in items]
            if None in values and len(items) > 1:
                problems.append('%s: an abstention is the field\'s only assignment' % where)
            dup = sorted({v for v in values if v is not None and values.count(v) > 1})
            if dup:
                problems.append('%s: %s assigned more than once' % (where, ', '.join(dup)))
            for i, a in enumerate(items):
                at = '%s[%d]' % (where, i)
                if a.value is None:
                    if not a.failure:
                        problems.append('%s: an abstention names the failure record that explains it' % at)
                    continue
                if a.value not in vocab:
                    problems.append('%s: %r is not a term of %s' % (at, a.value, field))
                if (field, a.value) in NEVER_HAND_SET:
                    problems.append('%s: %r is derived and never hand-set (taxonomy/lifecycle.yaml)' % (at, a.value))
                if a.value in EPISTEMIC.get(field, ()):
                    if not (a.note or a.quote):
                        problems.append('%s: %r states what is known, and says how in `note`' % (at, a.value))
                elif not (a.source and a.quote):
                    problems.append('%s: a value is source-bound and carries `source` and `quote` (03 S3.3 rule 1)' % at)
                if a.source and a.source not in self.sources:
                    problems.append('%s: source %r is not a key of `sources`' % (at, a.source))
        if problems:
            raise ValueError('; '.join(problems))
        return self

    def failures(self) -> list[tuple[str, str]]:
        """(field, failure id) for every failure the record cites."""
        return [(f, a.failure) for f, items in self.facets.items() for a in items if a.failure]

    def abstentions(self) -> list[str]:
        return [f for f, items in self.facets.items() if any(a.value is None for a in items)]


class FailureRecord(Strict):
    kind: Literal[FAILURE_KINDS]  # type: ignore[valid-type]
    facet: Text
    benchmark: Slug
    curator: Text
    date: date
    description: Text
    proposed_term: Text | None = None
    blocking: bool
    terms: list[Text] = Field(default_factory=list)
    classification: Slug | None = None
    route: Literal[ROUTES] | None = None  # type: ignore[valid-type]
    adr: AdrPath | None = None

    @model_validator(mode='after')
    def _facet_is_a_field(self):
        if self.facet not in FIELDS:
            raise ValueError('facet %r is not a classified field (%s)' % (self.facet, ', '.join(FIELDS)))
        if self.kind in ('collision', 'two-primaries') and len(self.terms) < 2:
            raise ValueError('a %s names the terms it is between in `terms` (at least two)' % self.kind)
        if (self.route == 'adr') != (self.adr is not None):
            raise ValueError('`adr` names the ADR exactly when `route` is adr')
        if self.route == 'homograph' and self.kind != 'collision':
            raise ValueError('only a collision routes to homographs.yaml')
        return self


FAILURE_NAME = re.compile(r'^(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]*)-(\d{3})$')
