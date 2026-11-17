"""S8, the JSON emitter: facets.json, corpus.json and enums.json (P2-S1-T02; 08 S4.2, S3.2, S6).

    bench build --out build/    # artifacts.build() loads and publishes (S1); this module writes the three files

tools/build/artifacts.py is the loader and the publish rules: which records are read, which are published,
the closure over Sources, the materialised subsets. This module is what 08 S3.5 calls the S8 emitter: what
each artifact holds, the refusal 08 S3.2 puts on the emitter, and the serialisation. artifacts.build() and
artifacts.write() call it, so `bench build` and scripts/preview_corpus.py emit through it.

corpus.json -- 08 S4.2: "Every published field of every benchmark, system, organization, metric and source
entity ... **No claim records.**" The shape the site reads (site/src/lib/corpus.ts) is kept: `entities` by
kind, each record dumped by its own model, and the materialised `subsets`. Before anything is written,
`claim_records` walks it and the build fails if any object in it is a ResultClaim -- one whose `id` is a
claim id, or one carrying every field a ResultClaim requires. A claim id as a reference is not a record, and
nor is a benchmark's own `results_observed` row, which is a curated field of the benchmark.

facets.json -- one row per published benchmark, and each row is exactly 08 S4.2's list (FACET_ROW):

  id, slug             the id; a benchmark's URL slug is its id (05 S2)
  name, aliases
  domain, subdomain    the family of domain.primary, and domain.primary
  facets               "the seven flat facet arrays", keyed by the taxonomy `facet:` names (FLAT_FACETS)
  year                 the year of `released`
  lifecycle            the record's lifecycle, a scalar
  verification_max, condition_completeness_max, claim_count     from the benchmark's claims (below)
  headroom             null

Decisions where 08 S4.2 is not specific, each with its reason:

  - The seven arrays sit in a `facets` object rather than beside the scalars, because the Lifecycle facet
    is named `lifecycle` and 08 S4.2 also lists `lifecycle` the scalar. Each is keyed by the `facet:` its
    taxonomy file declares; 02 S2 counts seven flat facets, so the two vocabularies with a file of their own
    fold into the facet 02 puts their field in: ceiling-anchors.yaml (`ceiling_anchor_type`) into
    data_properties (02 S7's fifth field) and maintenance.yaml (`maintenance_status`) into lifecycle (02 S8).
  - A multi-field facet concatenates its fields' values in FLAT_FACETS order, de-duplicated. One id repeats
    across two fields of one facet: execution.yaml defines `wet-lab` as an `execution.compute_tier` and as
    an `execution.reproducibility_blockers` term, by design (02 S11 rule 11), and they mean different
    things. So an id a facet's vocabulary defines in more than one field is written `{field}:{id}`
    (`execution.compute_tier:wet-lab`) and every other value is the bare id, and enums.json gives every
    term the `key` facets.json writes for it: a value joins to exactly one term. `term_keys` computes the
    qualified set from the taxonomy, so a second shared id is qualified without a code change.
  - `maintenance_status` is derived from the probe protocol (04 S5) and no build stage computes it yet, so
    it contributes nothing to the lifecycle array until one does; a record that carried it would already
    have failed tier 1.
  - Secondary domains are left out. 08 S4.2 lists `domain` and `subdomain` and nothing else from the spine,
    and the coverage rule that weighs a secondary at 0.5 (02 S3) is an S4 computation over corpus.json,
    which carries domain.secondary in full. A secondary-domain filter is an addition to 08's list for the
    view that needs it, not something this emitter assumes.
  - The claim-derived fields read every claim under data/claims/ whose `benchmark`, before any `@`, is the
    row's id, machine-ingested ones INCLUDED. 07 S11.4 is explicit that ingested claims "affect three
    integers already in the record -- claim_count, verification_max, condition_completeness_max -- and the
    last two are deliberately *maxima*, so a heap of thin ingested claims cannot inflate them"; 08 S4.2's
    claims.json / claims-ingested split decides which file carries a claim *record*, not whether an
    aggregate counts it, and facets.json is the browse index where 04 S12 keeps ingested claims "fully
    visible". The population is derived/adoption.json's (tools/build/adoption.py, both tiers), so a page's
    claim count and the filter's cannot disagree. vendor/ claims are never read: 08 S3.2 keeps vendor/
    material out of every CC-BY artifact.
      verification_max            the claim rung ranked highest by taxonomy/verification.yaml. `disputed_by`
                                  does not lower it: a dispute is a state, not a rung (04 S7).
      condition_completeness_max  the highest claim's condition_completeness, computed exactly as the
                                  quality tier does it (tools.build.comparability over the claim's
                                  EvalConditions); a claim whose every material field is waived has none.
      claim_count                 the number of claims.
    With no claim: null, null, 0. The envelope's `claim_basis` states that rule -- the tiers counted, and
    that no verification threshold or date window applies -- because 08 S3.2's first S4 obligation is that
    a derived number carries its inclusion rule in the artifact.
  - `headroom` is null on every row: nothing in the repository computes a headroom value yet. schema/metric.py
    holds 12 S3.1's formula, but the SOTA selection and the baseline and ceiling join that feed it are S4's
    (08 S3.5, P3-S9-T02), and a null is the honest value until they exist.

enums.json -- 08 S4.2: "Every controlled vocabulary with glosses." Every taxonomy/*.yaml that declares
`facet:` (`facet_files`: the facet vocabularies, the domain spine and the capability groups), keyed by that
facet name, plus the ResultClaim verification ladder (taxonomy/verification.yaml declares no facet, but it is a
closed vocabulary, and verification_max is one of its rungs):

  {artifact, format, taxonomy: <taxonomy/VERSION>, flat_facets: {facet: {fields, vocabularies}},
   vocabularies: {name: {file, facet_kind, version, gloss, terms: [term, ...]}}}

and every term, in file order, is {id, key, label, status, gloss} plus `field` where it has one, `parent` on a
domain term, `members` on a capability group and `rank` and `machine_assignable` on a rung. `gloss` is the
term's definition (a rung's meaning), whitespace-folded. Of those five, what a file does not state -- a
group's status and gloss, a rung's label and status -- is null rather than absent, so every term carries all
five. `flat_facets` says which fields and which vocabularies each facets.json array is made of.
taxonomy/domain_groups.yaml declares no facet and is not here.

The refusal (08 S3.2, S4's third obligation; D4). The ids in taxonomy/domain_groups.yaml are display-only:
`refuse` fails the build if one appears in any key or string value of any of the three artifacts, before
anything is written. A hit is a whole-token match, the rule scripts/check_display_only_vocab.py (CI 9h)
applies to the shipped files, so a build the emitter accepts cannot then fail 9h. A group id that
equals an id some other vocabulary defines (a term, a subdomain leaf, a capability group, a rung, a profile)
would make that term's every use look like a leak, and no rule can tell the two apart in prose or in an
untyped field: `display_only_ids` refuses such a taxonomy outright, naming the file, rather than guessing.
The remedy is renaming the group, which changes no published figure because the group is display-only. No
group id equals any other id today.

Determinism (08 S6, S3.2's S1 obligations): the loader reads files in sorted POSIX path order
(tools/validate/tiers.py discover(); a Python str sort is code-point order, which is UTF-8 byte order),
records are emitted sorted by the UTF-8 bytes of their id, every string and key is NFC, keys are sorted,
separators compact, UTF-8 with no ASCII escaping, LF and one trailing newline, and no clock. The claim-derived
values are a maximum and a count, which no input order changes. Two builds of one tree are byte-identical.
"""
from __future__ import annotations

import functools
import json
import os
import re
import unicodedata
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACTS = ('corpus.json', 'facets.json', 'enums.json')
# Per-artifact envelope format. facets.json moved to 08 S4.2's row in this task, so it is 2.
FORMATS = {'corpus': 1, 'facets': 2, 'enums': 1}
CLAIM_TIERS = ('curated', 'machine-ingested')     # what the claim-derived fields count (module docstring)

# 08 S4.2's facets.json row, in its order.
FACET_ROW = ('id', 'slug', 'name', 'aliases', 'domain', 'subdomain', 'facets', 'year', 'lifecycle',
             'verification_max', 'condition_completeness_max', 'claim_count', 'headroom')
# The row keys that project one Benchmark field unchanged: key -> the field's dotted path.
PROJECTED = {
    'id': 'id',
    'slug': 'id',                       # a benchmark's URL slug is its id (05 S2)
    'name': 'name',
    'aliases': 'aliases',
    'subdomain': 'domain.primary',
    'lifecycle': 'lifecycle',
}
# 02 S2's seven flat facets: facet (its taxonomy `facet:` name) -> (the taxonomy files its terms come from,
# the Benchmark fields its array is built from, in 02's order). A single-field facet's field is the
# Benchmark's; a field vocabulary's are the `field:` its terms declare. tests/build/test_emit_artifacts.py
# holds this table to the taxonomy, so a field added to a vocabulary fails a test until it is placed here.
FLAT_FACETS = {
    'capability': (('capabilities.yaml',), ('capability',)),
    'evaluation_method': (('evaluation-methods.yaml',), ('evaluation_method',)),
    'subject': (('subjects.yaml',), ('designed_for_subjects',)),
    'data_properties': (('data-properties.yaml', 'ceiling-anchors.yaml'),
                        ('data.access', 'data.refresh', 'data.data_provenance', 'data.contamination_risk',
                         'data.ceiling_anchor_type')),
    'lifecycle': (('lifecycle.yaml', 'maintenance.yaml'), ('lifecycle', 'activity', 'maintenance_status')),
    'governance': (('governance.yaml',),
                   ('governance.maintainer_type', 'governance.submission_process', 'governance.independence_flags')),
    'execution': (('execution.yaml',),
                  ('execution.compute_tier', 'execution.reproducibility_tier', 'execution.reproducibility_blockers',
                   'execution.harness_availability')),
}
# Derived fields no build stage computes yet: a record never carries them (04 S5), so they add nothing.
NOT_YET_DERIVED = frozenset({'maintenance_status'})
CLAIM_ID = re.compile(r'^claim-[0-9a-f]{12}$')


class Refused(Exception):
    """The emitter will not write these artifacts; `errors` says why, one line each."""

    def __init__(self, errors: list[str]):
        super().__init__('\n'.join(errors))
        self.errors = errors


# ---- serialisation ------------------------------------------------------------------------------

def nfc(x: Any) -> Any:
    if isinstance(x, str):
        return unicodedata.normalize('NFC', x)
    if isinstance(x, list):
        return [nfc(v) for v in x]
    if isinstance(x, dict):
        return {nfc(k): nfc(v) for k, v in x.items()}
    return x


def serialise(artifact: dict) -> bytes:
    """08 S6's canonical bytes: sorted keys, compact separators, UTF-8 unescaped, LF, one trailing newline."""
    return (json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def by_id(records) -> list:
    return sorted(records, key=lambda r: r['id'].encode('utf-8'))


def fold(text: str | None) -> str | None:
    return ' '.join(text.split()) if text is not None else None


def at(record: dict, dotted: str) -> Any:
    for key in dotted.split('.'):
        record = record[key]
    return record


# ---- the taxonomy -------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def taxonomy() -> dict:
    """The repository's taxonomy models. The build always reads the repository's taxonomy/, whatever data
    root it was pointed at, because that is what the schema's enums were built from at import time."""
    from schema.taxonomy import load_taxonomy
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))
    return models


def facet_files() -> list[tuple[str, str]]:
    """(file, facet) for every taxonomy file that declares `facet:`, in file-name order."""
    from schema.taxonomy import FILES
    return [(name, facet) for name, (_, facet) in sorted(FILES.items()) if facet is not None]


def term_field(t, facet: str) -> str:
    """The Benchmark field a flat facet's term is a value of: its `field:`, or the facet's one field."""
    return getattr(t, 'field', None) or FLAT_FACETS[facet][1][0]


@functools.lru_cache(maxsize=None)
def term_keys() -> dict[str, dict[tuple[str, str], str]]:
    """flat facet -> {(field, id): the value facets.json writes}: the bare id, or `{field}:{id}` for an id
    the facet's vocabulary defines in more than one field (module docstring; 02 S11 rule 11)."""
    models = taxonomy()
    out = {}
    for facet, (files, _) in FLAT_FACETS.items():
        pairs = [(term_field(t, facet), t.id) for f in files for t in models[f].terms]
        fields_of: dict[str, set] = {}
        for field, ident in pairs:
            fields_of.setdefault(ident, set()).add(field)
        out[facet] = {(field, ident): ('%s:%s' % (field, ident) if len(fields_of[ident]) > 1 else ident)
                      for field, ident in pairs}
    return out


def display_only_ids() -> frozenset[str]:
    """The domain-group ids, after refusing a taxonomy in which one of them equals another vocabulary's id."""
    models = taxonomy()
    groups = frozenset(g.id for g in models['domain_groups.yaml'].groups)
    others: dict[str, set[str]] = {}
    for name, m in sorted(models.items()):
        if name == 'domain_groups.yaml':
            continue
        for item in (getattr(m, 'terms', None) or []) + (getattr(m, 'groups', None) or []) + \
                (getattr(m, 'rungs', None) or []) + (getattr(m, 'profiles', None) or []):
            for ident in {item.id, item.id.split('/')[-1]}:      # a subdomain leaf is an id too (02 S11 rule 11)
                others.setdefault(ident, set()).add(name)
    clash = sorted(groups & set(others))
    if clash:
        raise Refused(['taxonomy/domain_groups.yaml: group id %s is also an id in %s, so no artifact could tell '
                       'the display-only group from that term; rename the group (D4) before building'
                       % (g, ', '.join('taxonomy/' + n for n in sorted(others[g]))) for g in clash])
    return groups


# ---- facets.json --------------------------------------------------------------------------------

def facet_values(b: dict) -> dict[str, list[str]]:
    """The seven flat facet arrays of one corpus.json benchmark record."""
    keys = term_keys()
    out = {}
    for facet, (_, fields) in FLAT_FACETS.items():
        values: list[str] = []
        for field in fields:
            if field in NOT_YET_DERIVED:
                continue
            v = at(b, field)
            for item in v if isinstance(v, list) else [] if v is None else [v]:
                ident = item['flag'] if isinstance(item, dict) else item   # an independence flag with its evidence
                key = keys[facet][(field, ident)]
                if key not in values:
                    values.append(key)
        out[facet] = values
    return out


def claim_fields(benchmarks: dict, claims: list, conditions: dict) -> tuple[dict[str, dict], list[str]]:
    """benchmark id -> {verification_max, condition_completeness_max, claim_count}, over the claims on the
    published benchmarks in `benchmarks` (id -> Benchmark model); and every reason those cannot be computed.
    `claims` are tools.validate.tiers Records from data/claims/; `conditions` maps a cond- id to its Records."""
    from tools.build import comparability
    rank = {r.id: r.rank for r in taxonomy()['verification.yaml'].rungs}
    profiles = comparability.load_profiles(os.path.join(ROOT, 'taxonomy', 'comparability-profiles.yaml'))
    resolutions, out, errors = {}, {}, []
    for r in claims:
        bench = r.raw.get('benchmark') if isinstance(r.raw, dict) else None
        bench = bench.split('@')[0] if isinstance(bench, str) else None
        if bench not in benchmarks:
            continue                    # a claim on an unpublished benchmark has no row to feed
        broken = '; '.join(f.message for f in r.schema_findings if f.blocks)
        if r.model is None or broken:
            errors.append('%s: %s is a claim on published benchmark %s, but fails tier 1: %s'
                          % (r.path, r.id, bench, broken or 'no model loaded'))
            continue
        c, cond = r.model, None
        if c.eval_conditions is not None:
            held = conditions.get(c.eval_conditions, [])      # get-default: a dangling ref is reported below
            why = ('no data/conditions/ file holds it' if not held else
                   'it is held by %d files' % len(held) if len(held) > 1 else
                   'it fails tier 1' if held[0].model is None or any(f.blocks for f in held[0].schema_findings)
                   else None)
            if why:
                errors.append('%s: %s names eval_conditions %s, but %s' % (r.path, c.id, c.eval_conditions, why))
                continue
            cond = held[0].model
        if bench not in resolutions:
            resolutions[bench] = comparability.resolve_profile(benchmarks[bench], profiles)
        done = comparability.compute_for_claim(c, resolutions[bench], cond).condition_completeness
        row = out.setdefault(bench, {'verification_max': None, 'condition_completeness_max': None, 'claim_count': 0})
        row['claim_count'] += 1
        if row['verification_max'] is None or rank[c.verification] > rank[row['verification_max']]:
            row['verification_max'] = c.verification
        if done is not None and (row['condition_completeness_max'] is None or done > row['condition_completeness_max']):
            row['condition_completeness_max'] = done
    return out, errors


NO_CLAIMS = {'verification_max': None, 'condition_completeness_max': None, 'claim_count': 0}


def facet_row(b: dict, claimed: dict | None) -> dict:
    row = {key: at(b, path) for key, path in PROJECTED.items()}
    row['domain'] = b['domain']['primary'].split('/')[0]
    row['facets'] = facet_values(b)
    row['year'] = int(b['released'][:4]) if b['released'] else None
    row.update(claimed or NO_CLAIMS)
    row['headroom'] = None              # S4 computes it (08 S3.5); nothing in the repository does yet
    return row


def facets_artifact(benchmarks: list[dict], claimed: dict[str, dict], vocabularies: dict, drafts: bool) -> dict:
    return {'artifact': 'facets', 'format': FORMATS['facets'], 'vocabularies': vocabularies,
            'claim_basis': {'tiers': list(CLAIM_TIERS), 'verification_threshold': None, 'date_window': None,
                            'verification_ladder': taxonomy()['verification.yaml'].version},
            'benchmarks': [facet_row(b, claimed.get(b['id'])) for b in by_id(benchmarks)],
            **({'drafts': True} if drafts else {})}


# ---- corpus.json --------------------------------------------------------------------------------

def corpus_artifact(entities: dict[str, list[dict]], subsets: list[dict], drafts: bool) -> dict:
    return {'artifact': 'corpus', 'format': FORMATS['corpus'],
            'entities': {kind: by_id(records) for kind, records in entities.items()}, 'subsets': subsets,
            **({'drafts': True} if drafts else {})}


@functools.lru_cache(maxsize=None)
def _claim_keys() -> frozenset[str]:
    from schema.claim import ResultClaim
    return frozenset(name for name, f in ResultClaim.model_fields.items() if f.is_required())


def claim_records(x: Any, where: str = '') -> list[str]:
    """The JSON path of every object in `x` that is a claim record: a claim id as its `id`, or every field a
    ResultClaim requires. 08 S4.2: corpus.json holds "No claim records"."""
    out = []
    if isinstance(x, dict):
        if (isinstance(x.get('id'), str) and CLAIM_ID.match(x['id'])) or _claim_keys() <= set(x):
            out.append(where or '<root>')
        for k, v in x.items():
            out += claim_records(v, '%s.%s' % (where, k) if where else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out += claim_records(v, '%s[%d]' % (where, i))
    return out


# ---- enums.json ---------------------------------------------------------------------------------

def _term(t, key: str) -> dict:
    out = {'id': t.id, 'key': key, 'label': t.label, 'status': t.status, 'gloss': fold(t.definition)}
    if getattr(t, 'field', None) is not None:
        out['field'] = t.field
    if hasattr(t, 'parent'):
        out['parent'] = t.parent                # null: a family, navigational and never assignable (04 S3)
    return out


def enums_artifact() -> dict:
    models = taxonomy()
    flat_of = {f: facet for facet, (files, _) in FLAT_FACETS.items() for f in files}
    vocabularies = {}
    for name, facet in facet_files():
        m = models[name]
        if name in flat_of:                     # a flat facet's term: the value facets.json writes for it
            keys = term_keys()[flat_of[name]]
            terms = [_term(t, keys[(term_field(t, flat_of[name]), t.id)]) for t in m.terms]
        elif hasattr(m, 'terms'):               # domains.yaml: subdomain is the bare id
            terms = [_term(t, t.id) for t in m.terms]
        else:                                   # capability_groups.yaml: a partition, with members and no gloss
            terms = [{'id': g.id, 'key': g.id, 'label': g.label, 'status': None, 'gloss': None,
                      'members': list(g.members)} for g in m.groups]
        vocabularies[facet] = {'file': 'taxonomy/' + name, 'facet_kind': m.facet_kind, 'version': m.version,
                               'gloss': fold(m.description), 'terms': terms}
    ladder = models['verification.yaml']        # verification_max is one of its rungs; ranked weakest first
    vocabularies['verification'] = {
        'file': 'taxonomy/verification.yaml', 'facet_kind': None, 'version': ladder.version,
        'gloss': fold(ladder.description),
        'terms': [{'id': r.id, 'key': r.id, 'label': None, 'status': None, 'gloss': fold(r.meaning), 'rank': r.rank,
                   'machine_assignable': r.machine_assignable} for r in sorted(ladder.rungs, key=lambda r: r.rank)]}
    facet_of = dict(facet_files())
    with open(os.path.join(ROOT, 'taxonomy', 'VERSION'), encoding='utf-8') as fh:
        version = fh.read().strip()
    return {'artifact': 'enums', 'format': FORMATS['enums'], 'taxonomy': version,
            'flat_facets': {facet: {'fields': list(fields), 'vocabularies': [facet_of[f] for f in files]}
                            for facet, (files, fields) in FLAT_FACETS.items()},
            'vocabularies': vocabularies}


# ---- the refusal --------------------------------------------------------------------------------

def token_re(ids) -> re.Pattern:
    """A whole-token match on any of `ids`, bounded on the id characters: CI 9h's rule
    (scripts/check_display_only_vocab.py token_re), so `reasoning-general` never matches inside
    `reasoning-general-ability` and the reverse."""
    alt = '|'.join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    return re.compile(r'(?<![A-Za-z0-9_-])(%s)(?![A-Za-z0-9_-])' % alt)


def group_hits(x: Any, pattern: re.Pattern, where: str = '') -> list[tuple[str, str]]:
    """(JSON path, group id) for every key and string value of `x` that carries a group id as a token."""
    out = []
    if isinstance(x, str):
        out += [(where or '<root>', m.group(1)) for m in pattern.finditer(x)]
    elif isinstance(x, dict):
        for k, v in x.items():
            path = '%s.%s' % (where, k) if where else k
            out += [(path + ' (key)', m.group(1)) for m in pattern.finditer(k)]
            out += group_hits(v, pattern, path)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out += group_hits(v, pattern, '%s[%d]' % (where, i))
    return out


def refuse(artifacts: dict[str, dict]) -> None:
    """Raise Refused unless the three (file name -> artifact) are fit to write: each was built, corpus.json
    holds no claim record (08 S4.2), and no domain-group id is anywhere in any of them (08 S3.2, D4)."""
    errors = ['%s was not built' % name for name in ARTIFACTS if not artifacts.get(name)]
    if errors:
        raise Refused(errors)
    errors = ['corpus.json: %s is a claim record, and 08 S4.2 puts none in corpus.json' % where
              for where in claim_records(artifacts['corpus.json'])]
    pattern = token_re(display_only_ids())
    errors += ['%s: %s carries the display-only domain-group id %s (taxonomy/domain_groups.yaml; 08 S3.2, D4)'
               % (name, path, gid) for name in ARTIFACTS for path, gid in group_hits(artifacts[name], pattern)]
    if errors:
        raise Refused(errors)


# ---- the three artifacts ------------------------------------------------------------------------

def emit(entities: dict[str, list[dict]], subsets: list[dict], benchmark_models: dict, claims: list,
         conditions: dict, vocabularies: dict, drafts: bool = False) -> dict[str, dict]:
    """file name -> artifact, NFC throughout, after every refusal has passed; raises Refused otherwise."""
    claimed, errors = claim_fields(benchmark_models, claims, conditions)
    if errors:
        raise Refused(errors)
    out = nfc({'corpus.json': corpus_artifact(entities, subsets, drafts),
               'facets.json': facets_artifact(entities['benchmark'], claimed, vocabularies, drafts),
               'enums.json': enums_artifact()})
    refuse(out)
    return out


def write(artifacts: dict[str, dict], out_dir: str) -> list[str]:
    """Write the three files, refusing again first: whatever built `artifacts`, nothing unfit is written."""
    refuse(artifacts)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name in ARTIFACTS:
        path = os.path.join(out_dir, name)
        with open(path, 'wb') as fh:
            fh.write(serialise(artifacts[name]))
        written.append(path)
    return written
