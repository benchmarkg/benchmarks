"""The FacetQuery JSON Schema, generated from enums.json at build time (P6-S3-T01; 11 S4 "The pipeline" and
"The FacetQuery shape", D3 S3.4 context 4).

    bench schema gen            # writes schema/generated/facetquery.schema.json beside the entity schemas
    bench schema gen --check    # and fails when the committed file differs from a regeneration

11 S4 step 1: F1 is one claude-haiku-4-5 call with `output_config.format` set to "a JSON Schema **generated at build
time from `enums.json`**. Every facet field is a `string[]` whose `items.enum` is the literal enum list." `schema()`
takes an enums.json document. codegen.render() hands it the one the S8 emitter builds and `bench build` writes
(tools/build/emit.py enums_artifact(), NFC as emit() leaves it), which is a function of taxonomy/ alone: `--check`
needs no build/ directory, the file regenerates byte-identically at a fixed commit, and a taxonomy edit to one of the
ten fields' vocabularies is drift that CI job 5 catches, as it catches drift in the entity schemas.

The task's four steps, each a rule here:

  1. Ten fields, no more (11 S4: "the schema exposes ten fields, not the whole taxonomy"). FIELDS maps each to the
     enums.json vocabulary, and the field or level within it, its values come from:

        domain_family       domain              terms without a parent: the 19 families
        domain_subdomain    domain              terms with a parent
        capability          capability
        evaluation_method   evaluation_method
        subject             subject             the subject under test (Benchmark.designed_for_subjects)
        access              data_properties     data.access
        contamination_risk  data_properties     data.contamination_risk
        lifecycle           lifecycle           the `lifecycle` field, not `activity`
        compute_tier        execution           execution.compute_tier
        year_min            none                an integer or null, against facets.json's `year`

     The other controlled vocabularies (refresh, provenance, ceiling anchors, activity, maintenance, governance, the
     other three execution fields, capability groups, the verification ladder) stay in the filter UI. `hard` (filters)
     and `soft` (score boosts) are one object, $defs/Facets, holding exactly these ten properties. Beside them sits
     the rest of 11 S4's shape, none of it a facet: free_text_terms, unmapped_terms and assumptions, the
     honest-failure surface, and intent and confidence, two closed lists of 11's own rather than taxonomy.
  2. Facet-qualified references, D3 S3.1's `{facet}:{id}` (mandatory in this output by D3 S3.4 context 4): every
     enum value is the enums.json vocabulary name, a colon and the term id, `capability:planning`,
     `domain:reasoning-general/planning`, never a bare slug, because the four declared homographs are exactly where a
     bare value cannot be scored. 11 S4's example writes `"access": ["fully-open"]` bare; the step and D3 overrule
     it, so access is `data_properties:fully-open`. A slot names one field, so the slot and the stripped id together
     identify a term even where one vocabulary repeats an id across its fields (`wet-lab` is a compute tier and a
     reproducibility blocker, 02 S11 rule 11). A consumer strips the prefix (11 S4, the client "strips the facet
     prefix before executing the filter") and joins (slot's field, id) to the term's enums.json `key`, which is
     what facets.json writes: for that compute tier, `execution.compute_tier:wet-lab`.
  3. Domain is two slots: data is tagged at subdomain level only (a family is navigational, 02 S3, D3.1), but a
     query filters at either level and a family filter expands to its subdomains at execution time. Every object has
     `additionalProperties: false`, and every property is required. config/ai-models.yaml
     (structured-outputs-behaviour) caps optional parameters at 24 across a request, which two ten-field objects would
     nearly spend; each optional parameter roughly doubles part of the compiled grammar; and required properties keep
     the output in schema order. "No constraint" is therefore an empty array or a null year_min, at the cost of a few
     output tokens per call.
  4. No unsupported constraint. The file is the wire schema the worker sends, so it carries only keywords the
     structured-outputs documentation lists as supported (ALLOWED_KEYWORDS), and no `$schema` or `$comment` banner
     either, unlike its siblings in schema/generated/: its provenance is this docstring and codegen's. `audit()` walks
     a schema, and `schema()` refuses to return one that names any other keyword, leaves an object open or a
     property optional. What minimum, maximum, minLength and uniqueItems would have said is CODE_ENFORCED instead,
     and `violations()` enforces it in code, beside the schema check: the reference for the worker's post-validator
     (P6-S3-T04), which re-checks enum membership anyway (G1) and, per config/ai-models.yaml, first maps a value that
     differs from an enum member only in capitalisation to the member.

Terms with `status: retired` are left out, as schema/benchmark.py leaves them out of the record enums: no record can
carry one, so a filter on it matches nothing. Deprecated and proposed terms stay. Values keep enums.json's order, which
is taxonomy file order.

`Refused` is raised, naming every problem, when enums.json lacks a vocabulary or a field a slot is drawn from, when a
slot would have no value, when a value would not match D3's FQR grammar, or when audit() finds anything.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = 'schema/generated/facetquery.schema.json'

# The ten fields, in 11 S4's order: slot -> (enums.json vocabulary, the term `field` it is drawn from or None for a
# single-field vocabulary, and for `domain` the level: 'family' or 'subdomain'). year_min has no vocabulary.
FIELDS = {
    'domain_family': ('domain', 'family'),
    'domain_subdomain': ('domain', 'subdomain'),
    'capability': ('capability', None),
    'evaluation_method': ('evaluation_method', None),
    'subject': ('subject', None),
    'access': ('data_properties', 'data.access'),
    'contamination_risk': ('data_properties', 'data.contamination_risk'),
    'lifecycle': ('lifecycle', 'lifecycle'),
    'compute_tier': ('execution', 'execution.compute_tier'),
    'year_min': (None, None),
}
INTENTS = ('suite_build', 'lookup', 'compare', 'ecosystem_question', 'out_of_scope')     # 11 S4
CONFIDENCE = ('high', 'low')
FQR = re.compile(r'^[a-z_]+:[a-z0-9/-]+$')          # D3 S3.1's grammar for a facet-qualified reference

# The documented-supported keywords (config/ai-models.yaml structured-outputs-supported) this generator may emit.
# Anything else -- minimum, maximum, multipleOf, minLength, maxLength, maxItems, uniqueItems, pattern, oneOf, not,
# $schema, $comment -- is refused, because the API answers it with a 400 and the SDKs silently strip it (11 S4's trap).
ALLOWED_KEYWORDS = frozenset({'title', 'description', 'type', 'properties', 'required', 'additionalProperties',
                              'items', 'enum', 'const', 'anyOf', '$ref', '$defs', 'minItems'})

# What the schema cannot say, enforced in code by violations() (step 4): keyword -> the rule.
YEAR_FLOOR = 1950       # catches a two-digit or garbage year; it is not a curation threshold
CODE_ENFORCED = {
    'minimum': 'hard.year_min and soft.year_min, when not null, are at least %d' % YEAR_FLOOR,
    'maximum': 'hard.year_min and soft.year_min, when not null, are at most the current year',
    'minLength': 'every free_text_terms, unmapped_terms and assumptions item is a non-blank string',
    'uniqueItems': 'no array repeats a value',
}

DESCRIPTIONS = {
    'domain_family': 'Domain families, domain:<family>. A family matches every subdomain under it.',
    'domain_subdomain': 'Domain subdomains, domain:<family>/<subdomain>.',
    'capability': 'Capabilities the benchmark measures.',
    'evaluation_method': 'How the benchmark scores a response.',
    'subject': 'The kind of system under test the benchmark is designed for.',
    'access': 'How the benchmark data can be obtained.',
    'contamination_risk': 'The risk that the benchmark data is in training sets.',
    'lifecycle': 'The lifecycle stage of the benchmark.',
    'compute_tier': 'The compute a full run of the benchmark needs.',
    'year_min': 'The earliest release year wanted, or null.',
    'free_text_terms': 'Phrases from the query kept for lexical search. Never a filter.',
    'unmapped_terms': 'Every query term no facet value expresses. Declare it here rather than force a value.',
    'assumptions': 'Each reading of an ambiguous phrase, one sentence each.',
    'intent': 'What the user wants done.',
    'confidence': 'low when the query could not be mapped with confidence.',
}
TITLE = 'FacetQuery'
ROOT_DESCRIPTION = ('A search query translated into the catalogue facets. hard facets filter; soft facets only rank '
                    'matches higher. Every facet value is facet-qualified. An empty array or a null year_min '
                    'constrains nothing.')
FACETS_DESCRIPTION = 'The ten facets a query can name.'


class Refused(ValueError):
    """schema() will not produce a FacetQuery schema; `errors` says why, one line each."""

    def __init__(self, errors: list[str]):
        super().__init__('\n'.join(errors))
        self.errors = errors


# ---- the slots ----------------------------------------------------------------------------------

def slot_values(enums: dict, slot: str) -> list[str]:
    """The facet-qualified values of one vocabulary slot, in enums.json order, retired terms left out."""
    vocabulary, which = FIELDS[slot]
    terms = [t for t in enums['vocabularies'][vocabulary]['terms'] if t.get('status') != 'retired']
    if vocabulary == 'domain':
        terms = [t for t in terms if (t.get('parent') is None) == (which == 'family')]
    elif which is not None:
        terms = [t for t in terms if t.get('field') == which]
    return ['%s:%s' % (vocabulary, t['id']) for t in terms]


def _refusals(enums: dict) -> list[str]:
    vocabularies = enums.get('vocabularies') or {}      # get-default: a document with no vocabularies refuses below
    errors = []
    for slot, (vocabulary, which) in FIELDS.items():
        if vocabulary is None:
            continue
        if vocabulary not in vocabularies:
            errors.append('%s: enums.json has no vocabulary %r' % (slot, vocabulary))
            continue
        values = slot_values(enums, slot)
        if not values:
            errors.append('%s: no %s term in enums.json vocabulary %r, so the slot would have no value'
                          % (slot, which or 'non-retired', vocabulary))
        errors += ['%s: %r is not a facet-qualified reference (D3 S3.1: %s)' % (slot, v, FQR.pattern)
                   for v in values if not FQR.match(v)]
        errors += ['%s: %r appears twice' % (slot, v) for v in sorted({v for v in values if values.count(v) > 1})]
    return errors


def _strings(description: str, values=None) -> dict:
    item = {'type': 'string', 'enum': list(values)} if values is not None else {'type': 'string'}
    return {'description': description, 'type': 'array', 'items': item}


def _object(properties: dict, **head) -> dict:
    return {**head, 'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


# ---- the schema ---------------------------------------------------------------------------------

def schema(enums: dict) -> dict:
    """The FacetQuery wire schema from one enums.json document; raises Refused instead of returning a bad one."""
    errors = _refusals(enums)
    if errors:
        raise Refused(errors)
    facets = {slot: _strings(DESCRIPTIONS[slot], slot_values(enums, slot)) for slot in FIELDS if slot != 'year_min'}
    facets['year_min'] = {'description': DESCRIPTIONS['year_min'], 'type': ['integer', 'null']}
    out = _object({
        'hard': {'$ref': '#/$defs/Facets'},
        'soft': {'$ref': '#/$defs/Facets'},
        'free_text_terms': _strings(DESCRIPTIONS['free_text_terms']),
        'unmapped_terms': _strings(DESCRIPTIONS['unmapped_terms']),
        'assumptions': _strings(DESCRIPTIONS['assumptions']),
        'intent': {'description': DESCRIPTIONS['intent'], 'type': 'string', 'enum': list(INTENTS)},
        'confidence': {'description': DESCRIPTIONS['confidence'], 'type': 'string', 'enum': list(CONFIDENCE)},
    }, title=TITLE, description=ROOT_DESCRIPTION)
    out['$defs'] = {'Facets': _object({slot: facets[slot] for slot in FIELDS}, description=FACETS_DESCRIPTION)}
    problems = audit(out)
    if problems:
        raise Refused(problems)
    return out


def audit(node: Any, where: str = '#') -> list[str]:
    """Every way `node` breaks step 3 or 4: a keyword outside ALLOWED_KEYWORDS, an object that is not closed or has
    an optional property, minItems other than 0 or 1, or a $ref that is not to this document's $defs."""
    if not isinstance(node, dict):
        return ['%s: %r is not a schema object' % (where, node)]
    out = ['%s: %s is not a keyword this schema may use (structured outputs reject it or the SDKs strip it)'
           % (where, k) for k in node if k not in ALLOWED_KEYWORDS]
    props = node.get('properties')
    if node.get('type') == 'object' or props is not None:
        if node.get('additionalProperties') is not False:
            out.append('%s: an object without additionalProperties: false' % where)
        optional = [k for k in props or {} if k not in (node.get('required') or [])]
        if optional:
            out.append('%s: optional properties %s; every property must be required' % (where, ', '.join(optional)))
    if 'minItems' in node and node['minItems'] not in (0, 1):
        out.append('%s: minItems %r; only 0 and 1 are supported' % (where, node['minItems']))
    if '$ref' in node and not (isinstance(node['$ref'], str) and node['$ref'].startswith('#/$defs/')):
        out.append('%s: $ref %r is not to this document\'s $defs' % (where, node['$ref']))
    for key in ('properties', '$defs'):
        for name, sub in (node.get(key) or {}).items():
            out += audit(sub, '%s/%s/%s' % (where, key, name))
    if 'items' in node:
        out += audit(node['items'], where + '/items')
    for i, sub in enumerate(node.get('anyOf') or []):
        out += audit(sub, '%s/anyOf/%d' % (where, i))
    return out


# ---- the code-enforced half ---------------------------------------------------------------------

def violations(query: Any, facetquery: dict, this_year: int) -> list[str]:
    """Everything wrong with one FacetQuery: what the schema checks (jsonschema, Draft 2020-12), then CODE_ENFORCED.
    `this_year` is the caller's clock, so the result is reproducible."""
    from jsonschema import Draft202012Validator
    out = ['%s: %s' % ('/'.join(str(p) for p in e.absolute_path) or '<root>', e.message)
           for e in sorted(Draft202012Validator(facetquery).iter_errors(query),
                           key=lambda e: ('/'.join(str(p) for p in e.absolute_path), e.message))]
    if out:
        return out                              # the code rules assume the shape the schema guarantees
    for side in ('hard', 'soft'):
        year = query[side]['year_min']
        if year is not None and not YEAR_FLOOR <= year <= this_year:
            out.append('%s/year_min: %d is outside %d..%d (%s)' % (side, year, YEAR_FLOOR, this_year,
                                                                   'minimum' if year < YEAR_FLOOR else 'maximum'))
        for slot in FIELDS:
            if slot != 'year_min':
                out += _repeats('%s/%s' % (side, slot), query[side][slot])
    for key in ('free_text_terms', 'unmapped_terms', 'assumptions'):
        out += ['%s/%d: a blank string (minLength)' % (key, i) for i, s in enumerate(query[key]) if not s.strip()]
        out += _repeats(key, query[key])
    return out


def _repeats(where: str, values: list) -> list[str]:
    return ['%s: %r appears more than once (uniqueItems)' % (where, v)
            for v in sorted({v for v in values if values.count(v) > 1})]
