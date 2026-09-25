"""Pydantic models for every file under taxonomy/ (P0-S4-T02; 04-data-model.md S12).

04 S12: "A taxonomy file with a misspelled key would produce a schema that validates the corpus
against the wrong vocabulary, and CI would pass. So the taxonomy files get Pydantic models of their
own." Every model here forbids unknown keys, so a misspelled key is a validation error, not a field
silently ignored. `load_taxonomy()` loads every taxonomy/*.yaml through its model; a file with no
model is itself an error, so a new vocabulary cannot slip in unvalidated.

The admissibility rules, reconciled from the two places that state them:

  03 S5, for the spine facets (capability, evaluation_method, subject, domain) -- `Term`:
    1. definition: one sentence, non-empty. Checked mechanically as one sentence-ending
       punctuation mark, after common abbreviations. ("No examples inside it" is not mechanical:
       "such as forms, tables and reports" enumerates kinds, not benchmarks, and is allowed.)
    2. inclusion_test: an operational "tag this if ..." -- phrased as a tagging instruction.
    3. exclusion_test: an operational "do NOT tag this if ...".
    4. >= 2 examples, >= 1 of them a near-miss with `qualifies: false`.
  Rules 2 and 3 bind every term that is `active` or `deprecated`. A `proposed` term is
  definition-only: 03 S5 and 02 S14 give the 204 subdomains "a definition and `status: proposed` at
  Phase 0, and their examples[] are drawn from catalogued entries in Phase 1".

  02 S11 rule 8, for every enum term, spine or field vocabulary (`FieldTerm`):
    - definition is mandatory from the first commit;
    - "While taxonomy/VERSION < 1.0.0, `examples: []` is permitted and produces a CI *warning*,
      not a failure. At the v1.0.0 freeze, fewer than two examples is a hard failure";
    - `gap_placeholder: true` is the one named exception, "never by inference".
  So rule 4 above is a warning before the freeze and an error from it. The version comes from the
  validation context (`load_taxonomy` reads taxonomy/VERSION); validating without a context is
  treated as post-freeze, i.e. strict.

Field vocabularies (access, lifecycle, governance, ...) are definition-only by P0-S2-T05's design and
carry no inclusion or exclusion test; 04 S12's `Term`, with the tests, is the spine.

The shapes follow the files as they exist, where 04 S12's table abbreviates: homographs.yaml holds
`entries` of {capability, domain, relationship, rationale} (05 S9 check 9d's fields), the retired and
forbidden ledgers are keyed `retired` and `forbidden`, and `not_to_be_confused_with` is a list of
{term, distinction}. Three files 04 S12 does not list get models too -- comparability-profiles,
domain-expectations and verification -- because every file must load through one.
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, ValidationInfo, model_validator

# D3-vocabulary-namespacing.md S3's id grammar.
SLUG_RE = r'^[a-z0-9]+(-[a-z0-9]+)*$'
SUBDOMAIN_RE = r'^[a-z0-9]+(-[a-z0-9]+)*/[a-z0-9]+(-[a-z0-9]+)*$'
QUALIFIED_RE = r'^[a-z_]+:[a-z0-9/-]+$'
TERM_REF_RE = r'^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)?$'
SEMVER_RE = r'^\d+\.\d+\.\d+$'
FIELD_RE = r'^[a-z_]+(\.[a-z_]+)*$'
FREEZE = (1, 0, 0)

Slug = Annotated[str, StringConstraints(pattern=SLUG_RE)]
TermRef = Annotated[str, StringConstraints(pattern=TERM_REF_RE)]
Qualified = Annotated[str, StringConstraints(pattern=QUALIFIED_RE)]
SemVer = Annotated[str, StringConstraints(pattern=SEMVER_RE)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Status = Literal['proposed', 'active', 'deprecated', 'retired']

_ABBREV = re.compile(r'\b(?:e\.g|i\.e|etc|vs|cf|al|approx|incl)\.', re.I)


def sentence_count(text: str) -> int:
    s = _ABBREV.sub('ABBR', text.strip())
    s = re.sub(r'\d\.\d', 'N', s)
    return len(re.findall(r'[.!?](?=\s|$)', s))


def version_tuple(v: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in v.split('.'))  # type: ignore[return-value]


def _frozen(info: ValidationInfo) -> bool:
    """Past the v1.0.0 freeze? No context means strict."""
    ctx = info.context or {}
    return 'taxonomy_version' not in ctx or version_tuple(ctx['taxonomy_version']) >= FREEZE


def _warn(info: ValidationInfo, message: str) -> None:
    ctx = info.context or {}
    if isinstance(ctx.get('warnings'), list):
        ctx['warnings'].append(message)


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=False)


# ---- terms ------------------------------------------------------------------------------------

class Example(Strict):
    ref: Slug
    qualifies: bool
    why: Text


class Confusion(Strict):
    term: TermRef
    distinction: Text


class BaseTerm(Strict):
    """What every enum term carries (02 S11 rule 8)."""
    id: str
    label: Text
    status: Status
    introduced_in: SemVer
    source: str | None = None
    definition: Text
    examples: list[Example] = Field(default_factory=list)
    gap_placeholder: bool = False

    # 03 S5 rule 4 asks for a near-miss too; field vocabularies need only the count (rule 8).
    needs_near_miss: ClassVar[bool] = False

    @model_validator(mode='after')
    def _definition_is_one_sentence(self):
        if sentence_count(self.definition) != 1:
            raise ValueError('definition must be one sentence (03 S5); %r has %d'
                             % (self.id, sentence_count(self.definition)))
        return self

    @model_validator(mode='after')
    def _examples_rule(self, info: ValidationInfo):
        if self.gap_placeholder or self.status not in ('active', 'deprecated'):
            return self
        problems = []
        if len(self.examples) < 2:
            problems.append('%d example(s), fewer than two' % len(self.examples))
        if self.needs_near_miss and self.examples and not any(e.qualifies is False for e in self.examples):
            problems.append('no near-miss example (qualifies: false)')
        if problems:
            msg = '%s: %s' % (self.id, '; '.join(problems))
            if _frozen(info):
                raise ValueError(msg + ' -- a hard failure from the v1.0.0 freeze (02 S11 rule 8)')
            _warn(info, msg + ' -- permitted while taxonomy/VERSION < 1.0.0 (02 S11 rule 8)')
        return self


class Term(BaseTerm):
    """A spine-facet term: capability, evaluation_method, subject (and, via DomainTerm, domain)."""
    id: Slug
    inclusion_test: Text | None = None
    exclusion_test: Text | None = None
    see_also: list[TermRef] = Field(default_factory=list)
    not_to_be_confused_with: list[Confusion] = Field(default_factory=list)

    needs_near_miss: ClassVar[bool] = True

    @model_validator(mode='after')
    def _tests_rule(self):
        if self.status not in ('active', 'deprecated'):
            return self  # a proposed term is definition-only until Phase 1 (03 S5)
        if not self.inclusion_test:
            raise ValueError('%s: an %s term needs an inclusion_test (03 S5)' % (self.id, self.status))
        if not self.exclusion_test:
            raise ValueError('%s: an %s term needs an exclusion_test (03 S5)' % (self.id, self.status))
        if not re.search(r'\btag\b.*\b(?:if|when|only)\b', self.inclusion_test, re.I | re.S):
            raise ValueError('%s: inclusion_test must be an operational "tag this if ..." (03 S5)' % self.id)
        if not re.search(r'\bnot\s+tag\b', self.exclusion_test, re.I):
            raise ValueError('%s: exclusion_test must be an operational "do NOT tag this if ..." (03 S5)' % self.id)
        return self


class DomainTerm(Term):
    """A domains.yaml term. `parent: null` is a family -- navigational, never assignable -- and only a
    family carries the curation fields; a subdomain is `{parent}/{leaf}` (03 S4, check 9c)."""
    id: TermRef
    parent: Slug | None
    seed_target: int | None = Field(default=None, ge=1)
    core: bool | None = None
    coverage_status: Literal['surveyed', 'under-surveyed'] | None = None
    curation_posture: Literal['hand-curate', 'mixed', 'ingest-then-verify'] | None = None
    reviewer_signoff: Literal['none', 'generalist', 'domain-expert'] | None = None
    reviewer: str | None = None
    signed_on: date | None = None

    FAMILY_FIELDS: ClassVar[tuple[str, ...]] = ('seed_target', 'core', 'coverage_status', 'curation_posture', 'reviewer_signoff')

    @model_validator(mode='after')
    def _family_or_subdomain(self):
        if self.parent is None:
            if not re.fullmatch(SLUG_RE, self.id):
                raise ValueError('%s: a family id is a bare slug' % self.id)
            missing = [f for f in self.FAMILY_FIELDS if getattr(self, f) is None]
            if missing:
                raise ValueError('%s: a domain family needs %s (04 S7)' % (self.id, ', '.join(missing)))
            if self.reviewer_signoff != 'none' and (not self.reviewer or not self.signed_on):
                raise ValueError('%s: reviewer_signoff %s needs reviewer and signed_on (04 S7)'
                                 % (self.id, self.reviewer_signoff))
        else:
            if not re.fullmatch(SUBDOMAIN_RE, self.id) or self.id.split('/')[0] != self.parent:
                raise ValueError('%s: a subdomain id is {parent}/{leaf} with parent %s (03 S4)' % (self.id, self.parent))
            present = [f for f in self.FAMILY_FIELDS + ('reviewer', 'signed_on') if getattr(self, f) is not None]
            if present:
                raise ValueError('%s: %s belong on the family, not a subdomain' % (self.id, ', '.join(present)))
        return self


class FieldTerm(BaseTerm):
    """A term in a definition-only field vocabulary (P0-S2-T05): access, lifecycle, governance, ..."""
    id: Slug
    field: Annotated[str, StringConstraints(pattern=FIELD_RE)]
    derived: bool = False
    derivation: Text | None = None

    @model_validator(mode='after')
    def _derivation_stated(self):
        if self.derived and not self.derivation:
            raise ValueError('%s: a derived term must state its derivation' % self.id)
        if self.derivation and not self.derived:
            raise ValueError('%s: a derivation on a term not marked derived' % self.id)
        return self


# ---- facet files ------------------------------------------------------------------------------

def _unique(ids, what):
    seen, dups = set(), []
    for i in ids:
        if i in seen:
            dups.append(i)
        seen.add(i)
    if dups:
        raise ValueError('%s used more than once: %s' % (what, ', '.join(sorted(set(dups)))))


class FacetFile(Strict):
    """The header every facet file carries (04 S12), over spine terms."""
    facet: Annotated[str, StringConstraints(pattern=r'^[a-z_]+$')]
    facet_kind: Literal['navigational', 'flat']
    version: SemVer
    updated: date
    description: Text
    terms: list[Term] = Field(min_length=1)

    @model_validator(mode='after')
    def _ids_unique_and_refs_resolve(self):
        _unique([t.id for t in self.terms], 'term id')  # including deprecated and retired (check 9c)
        known = {t.id for t in self.terms}
        for t in self.terms:
            for ref in getattr(t, 'see_also', []) + [c.term for c in getattr(t, 'not_to_be_confused_with', [])]:
                if ref not in known:
                    raise ValueError('%s refers to %r, which is not a term in this file' % (t.id, ref))
        return self


class DomainFacetFile(FacetFile):
    facet_kind: Literal['navigational']
    terms: list[DomainTerm] = Field(min_length=1)

    @model_validator(mode='after')
    def _spine_shape(self):
        families = {t.id for t in self.terms if t.parent is None}
        if not families:
            raise ValueError('domains.yaml has no family (a term with parent: null)')
        for t in self.terms:
            if t.parent is not None and t.parent not in families:
                raise ValueError('%s: parent %s is not a family in this file' % (t.id, t.parent))
        # The leaf is unique across the whole file, not merely within its parent (check 9c).
        _unique([t.id.split('/', 1)[1] for t in self.terms if t.parent is not None], 'subdomain leaf')
        return self


class FieldFacetFile(FacetFile):
    """02 S11 rule 11: in a file carrying several fields, ids are unique within the field
    vocabulary, not the file -- execution.yaml defines `wet-lab` as both a compute_tier and a
    reproducibility_blocker by design -- and an id shared across two fields is reported, not passed
    over silently."""
    facet_kind: Literal['flat']
    terms: list[FieldTerm] = Field(min_length=1)

    @model_validator(mode='after')
    def _ids_unique_and_refs_resolve(self, info: ValidationInfo):  # replaces FacetFile's file-wide rule
        _unique(['%s %s' % (t.field, t.id) for t in self.terms], '(field, id)')
        fields_by_id: dict[str, list[str]] = {}
        for t in self.terms:
            fields_by_id.setdefault(t.id, []).append(t.field)
        for tid, fields in sorted(fields_by_id.items()):
            if len(fields) > 1:
                _warn(info, 'id %r is defined in %d fields (%s); allowed by 02 S11 rule 11, reported as it asks'
                      % (tid, len(fields), ', '.join(fields)))
        return self


# ---- groups, homographs, thresholds, ledgers --------------------------------------------------

class Group(Strict):
    id: Slug
    label: Text
    members: list[Slug] = Field(min_length=1)


class GroupFile(Strict):
    """capability_groups.yaml (a strict partition of the capability terms, 02 S4.3, check 9g) and
    domain_groups.yaml (display-only bands over the families, check 9h).

    Intrinsically: group ids unique, and no member in two groups. Against the vocabulary, when the
    context supplies it (`load_taxonomy` does): `group_universe` -- every term in exactly one group,
    no unknown member -- and `reserved_ids`, which no group id may equal."""
    facet: str | None = None
    facet_kind: Literal['flat'] | None = None
    version: SemVer
    updated: date
    display_only: bool
    description: Text
    groups: list[Group] = Field(min_length=1)

    @model_validator(mode='after')
    def _strict_partition(self, info: ValidationInfo):
        _unique([g.id for g in self.groups], 'group id')
        members = [m for g in self.groups for m in g.members]
        _unique(members, 'group member (a strict partition puts each in exactly one group)')
        ctx = info.context or {}
        universe = ctx.get('group_universe')
        if universe is not None:
            unknown = sorted(set(members) - set(universe))
            missing = sorted(set(universe) - set(members))
            if unknown:
                raise ValueError('members that are not terms: %s' % ', '.join(unknown))
            if missing:
                raise ValueError('terms in no group, so not a partition: %s' % ', '.join(missing))
        clash = sorted({g.id for g in self.groups} & set(ctx.get('reserved_ids') or ()))
        if clash:
            raise ValueError('group ids that collide with a term, leaf or family id: %s' % ', '.join(clash))
        return self


class Homograph(Strict):
    capability: Qualified
    domain: Qualified
    relationship: Literal['same-concept-two-facets', 'false-friend']
    rationale: Text

    @model_validator(mode='after')
    def _is_a_homograph(self):
        if not self.capability.startswith('capability:') or not self.domain.startswith('domain:'):
            raise ValueError('a homograph pairs a capability: ref with a domain: ref')
        cap = self.capability.split(':', 1)[1]
        dom = self.domain.split(':', 1)[1]
        if '/' not in dom or dom.split('/', 1)[1] != cap:
            raise ValueError('%s and %s: the capability id must equal the subdomain leaf' % (self.capability, self.domain))
        return self


class HomographFile(Strict):
    """homographs.yaml, read by checks 9d and 9e. Whether each declared pair still computes is
    check 9d's job (scripts/taxonomy_stats.py), which has both vocabularies in hand."""
    version: SemVer
    updated: date
    description: Text
    entries: list[Homograph]

    @model_validator(mode='after')
    def _unique_pairs(self):
        _unique([e.capability for e in self.entries], 'homograph capability')
        return self


class ThresholdFile(Strict):
    """thresholds.yaml: the named completeness floors (04 S12). A threshold without a meaning, or a
    meaning without a threshold, is the drift the file exists to prevent."""
    version: SemVer
    updated: date
    description: Text
    declared_by: Text
    calibrated_on: date | None
    thresholds: dict[Annotated[str, StringConstraints(pattern=r'^[a-z_]+$')], Annotated[float, Field(ge=0, le=1)]]
    meanings: dict[str, Text]

    @model_validator(mode='after')
    def _named_and_explained(self):
        for name in ('frontier_floor', 'comparison_floor'):
            if name not in self.thresholds:
                raise ValueError('thresholds.yaml must declare %s (04 S12)' % name)
        if set(self.thresholds) != set(self.meanings):
            raise ValueError('thresholds and meanings name different keys: %s'
                             % sorted(set(self.thresholds) ^ set(self.meanings)))
        return self


class RetiredId(Strict):
    id: TermRef
    retired_on: date
    reason: Text
    replaced_by: TermRef | None = None


class RetiredIdFile(Strict):
    """retired-ids.yaml: the never-reuse ledger (03 S4)."""
    version: SemVer
    updated: date
    description: Text
    retired: list[RetiredId]

    @model_validator(mode='after')
    def _once(self):
        _unique([r.id for r in self.retired], 'retired id')
        return self


class ForbiddenId(Strict):
    identifier: Annotated[str, StringConstraints(pattern=r'^[a-z_][a-z0-9_]*$')]
    renamed_to: Annotated[str, StringConstraints(pattern=r'^[a-z_][a-z0-9_]*$')]
    renamed_on: date
    owner: Text
    reason: Text
    note: Text | None = None


class ForbiddenIdFile(Strict):
    """forbidden-identifiers.yaml: renamed field names check 9a greps for."""
    version: SemVer
    updated: date
    description: Text
    forbidden: list[ForbiddenId]

    @model_validator(mode='after')
    def _once(self):
        _unique([f.identifier for f in self.forbidden], 'forbidden identifier')
        return self


# ---- the three control files 04 S12 does not list ---------------------------------------------

class Fallback(Strict):
    material: list[Annotated[str, StringConstraints(pattern=r'^[a-z_]+$')]] = Field(min_length=1)
    note: Text


class Profile(Strict):
    id: Slug
    description: Text
    material: list[Annotated[str, StringConstraints(pattern=r'^[a-z_]+$')]] = Field(min_length=1)
    applies_to: list[tuple[Slug, Slug]] = Field(min_length=1)   # (evaluation_method, subject)
    weights: dict[str, Annotated[float, Field(gt=0)]] | None = None

    @model_validator(mode='after')
    def _weights_on_material(self):
        stray = sorted(set(self.weights or {}) - set(self.material))
        if stray:
            raise ValueError('%s: weights on fields that are not material: %s' % (self.id, ', '.join(stray)))
        return self


class ComparabilityProfileFile(Strict):
    """comparability-profiles.yaml: (evaluation_method, subject) -> material condition fields."""
    version: SemVer
    updated: date
    description: Text
    default_weight: Annotated[float, Field(gt=0)]
    fallback: Fallback
    profiles: list[Profile] = Field(min_length=1)

    @model_validator(mode='after')
    def _one_profile_per_pair(self):
        _unique([p.id for p in self.profiles], 'profile id')
        _unique(['%s x %s' % pair for p in self.profiles for pair in p.applies_to],
                '(evaluation_method, subject) pair in more than one profile, or')
        return self


class Expectation(Strict):
    family: Slug
    tier1_expectation: int | None = Field(ge=1)
    sized: bool
    denominator_source: str | None = None
    denominator_fallback: Literal['seed_target'] | None = None
    fallback_value: int | None = Field(default=None, ge=1)
    render_as: Literal['unsized'] | None = None

    @model_validator(mode='after')
    def _sized_or_fallback(self):
        if self.sized and (self.tier1_expectation is None or not self.denominator_source):
            raise ValueError('%s: a sized family needs tier1_expectation and denominator_source' % self.family)
        if not self.sized and (self.tier1_expectation is not None or self.denominator_fallback is None
                               or self.fallback_value is None or self.render_as is None):
            raise ValueError('%s: an unsized family has no tier1_expectation and states its fallback and render_as'
                             % self.family)
        return self


class DomainExpectationFile(Strict):
    """domain-expectations.yaml: the per-family coverage denominator, with its provenance."""
    version: SemVer
    updated: date
    description: Text
    source: Text
    estimated_on: date
    verified: bool
    basis: Text
    expectations: list[Expectation] = Field(min_length=1)

    @model_validator(mode='after')
    def _once(self):
        _unique([e.family for e in self.expectations], 'family')
        return self


class Rung(Strict):
    rank: int = Field(ge=1)
    id: Slug
    meaning: Text
    typical_evidence: Text
    machine_assignable: bool


class VerificationFile(Strict):
    """verification.yaml: the seven-rung ladder, ranked 1 (weakest) upward without gaps."""
    version: SemVer
    updated: date
    description: Text
    rungs: list[Rung] = Field(min_length=1)

    @model_validator(mode='after')
    def _ranked(self):
        _unique([r.id for r in self.rungs], 'rung id')
        if sorted(r.rank for r in self.rungs) != list(range(1, len(self.rungs) + 1)):
            raise ValueError('rung ranks must be 1..%d, each once' % len(self.rungs))
        return self


# ---- loading ----------------------------------------------------------------------------------

# Every taxonomy/*.yaml, its model, and the `facet` it must declare (None: the file has no facet key).
FILES: dict[str, tuple[type[BaseModel], str | None]] = {
    'capabilities.yaml': (FacetFile, 'capability'),
    'evaluation-methods.yaml': (FacetFile, 'evaluation_method'),
    'subjects.yaml': (FacetFile, 'subject'),
    'domains.yaml': (DomainFacetFile, 'domain'),
    'ceiling-anchors.yaml': (FieldFacetFile, 'ceiling_anchor_type'),
    'data-properties.yaml': (FieldFacetFile, 'data_properties'),
    'execution.yaml': (FieldFacetFile, 'execution'),
    'governance.yaml': (FieldFacetFile, 'governance'),
    'lifecycle.yaml': (FieldFacetFile, 'lifecycle'),
    'maintenance.yaml': (FieldFacetFile, 'maintenance_status'),
    'capability_groups.yaml': (GroupFile, 'capability_group'),
    'domain_groups.yaml': (GroupFile, None),
    'homographs.yaml': (HomographFile, None),
    'thresholds.yaml': (ThresholdFile, None),
    'retired-ids.yaml': (RetiredIdFile, None),
    'forbidden-identifiers.yaml': (ForbiddenIdFile, None),
    'comparability-profiles.yaml': (ComparabilityProfileFile, None),
    'domain-expectations.yaml': (DomainExpectationFile, None),
    'verification.yaml': (VerificationFile, None),
}


class TaxonomyError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__('\n'.join(errors))
        self.errors = errors


def read_yaml(path: str) -> Any:
    """ruamel's safe loader, which rejects a duplicate key -- PyYAML keeps the last one silently."""
    from ruamel.yaml import YAML
    with open(path, encoding='utf-8') as f:
        return YAML(typ='safe').load(f)


def validate_file(name: str, data: Any, context: dict | None = None) -> BaseModel:
    """One file's data through its model; raises ValidationError or ValueError."""
    if name not in FILES:
        raise ValueError('%s: no model for this file -- add it to schema/taxonomy.py FILES' % name)
    model, facet = FILES[name]
    obj = model.model_validate(data, context=context)
    declared = getattr(obj, 'facet', None)
    if declared != facet:
        raise ValueError('%s declares facet %r, expected %r' % (name, declared, facet))
    return obj


def load_taxonomy(root: str = 'taxonomy') -> tuple[dict[str, BaseModel], list[str]]:
    """Every taxonomy/*.yaml through its model. Returns (models by file name, warnings); raises
    TaxonomyError listing every failure, not just the first."""
    with open(os.path.join(root, 'VERSION'), encoding='utf-8') as f:
        version = f.read().strip()
    if not re.fullmatch(SEMVER_RE, version):
        raise TaxonomyError(['taxonomy/VERSION %r is not semver' % version])
    names = sorted(n for n in os.listdir(root) if n.endswith('.yaml'))
    errors, warnings, out = [], [], {}
    for n in sorted(set(FILES) - set(names)):
        errors.append('%s: expected in %s and missing' % (n, root))

    def run(name, extra=None):
        ctx = {'taxonomy_version': version, 'warnings': [], **(extra or {})}
        try:
            out[name] = validate_file(name, read_yaml(os.path.join(root, name)), ctx)
        except ValidationError as e:
            for err in e.errors():
                loc = '.'.join(str(p) for p in err['loc'])
                errors.append('%s: %s%s' % (name, (loc + ': ') if loc else '', err['msg']))
        except Exception as e:  # noqa: BLE001 -- a YAML error, a duplicate key, an unmodelled file
            errors.append('%s: %s' % (name, str(e).splitlines()[0] if str(e) else type(e).__name__))
        warnings.extend('%s: %s' % (name, w) for w in ctx['warnings'])

    later = ('capability_groups.yaml', 'domain_groups.yaml')
    for name in names:
        if name not in later:
            run(name)
    caps, doms = out.get('capabilities.yaml'), out.get('domains.yaml')
    if caps is not None and doms is not None:
        cap_ids = [t.id for t in caps.terms if t.status != 'retired']
        families = [t.id for t in doms.terms if t.parent is None]
        leaves = [t.id.split('/', 1)[1] for t in doms.terms if t.parent is not None]
        extras = {
            'capability_groups.yaml': {'group_universe': cap_ids, 'reserved_ids': set(cap_ids) | set(families) | set(leaves)},
            'domain_groups.yaml': {'group_universe': families},
        }
    else:
        extras = {}
    for name in later:
        if name in names:
            run(name, extras.get(name))
    if errors:
        raise TaxonomyError(errors)
    return out, warnings
