#!/usr/bin/env python3
"""S9's croissant-benchmark JSON-LD: one document per published benchmark and a collection document, validated in
the build (P2-S3-T06; 08 S5.8, 10 "The permanent citation URL", 15 A8, 04 S5, 02 S13).

    bench build --out build/                                # also writes build/croissant-benchmark/
    python tools/build/croissant.py --check build/croissant-benchmark   # validate documents already written

08 S5.8: MLCommons Croissant describes datasets and has no benchmark extension, so the catalogue publishes one, in
its own namespace, and "an extension nobody can validate is a blog post". This module is that build obligation.

What it writes, into build/croissant-benchmark/ (the site serves it at /benchmarks/{id}/cite.jsonld and inlines the
same text in a <script type="application/ld+json"> on the detail page):

    {id}.jsonld          one per published benchmark: a schema.org Dataset, typed cb:Benchmark too
    _collection.jsonld   the catalogue as a Dataset whose hasPart lists every benchmark document, each typed
                         cb:Benchmark only (a document holds one schema.org Dataset node: mlcroissant validates
                         whichever one rdflib lists first). A benchmark id is a slug, which cannot start with `_`, so
                         the name can never collide with one

The namespace. Our terms live under NAMESPACE, `https://<host>/ns/croissant-benchmark/v1#` (08 S5.8). No host is
fixed yet -- 08 and P4-S6-T01 both write `<host>` -- and `<` is not an IRI character, so NS_HOST is `host.invalid`
until it is: RFC 2606 reserves .invalid, so the placeholder can never resolve to somebody else's vocabulary, and
fixing the host is a one-constant change that `bench schema gen --check` then holds the generated schema to. The
documents say they conform to both CROISSANT_VERSION and EXTENSION_VERSION. The extension is unofficial (15 A8):
nothing here is proposed to MLCommons, which is P4-S6-T06's. NS_HOST, the namespace, the terms and the document
models are schema/croissant_benchmark.py's (P4-S6-T02, ADR-0030); this module emits and validates with them.

The @context is the upstream Croissant context for CROISSANT_VERSION, taken from the pinned mlcroissant at build time
(the context its own writer emits), plus `cb` and one key per extension term. Nothing upstream is copied into this
repository, and nothing upstream is redefined: `context()` refuses an extension key that is an upstream context key
or a schema.org term name (rdflib's schema.org vocabulary, which mlcroissant installs), because under the upstream
`@vocab` a bare key already means the schema.org term of that name. That rule is why the lineage edge is
`isSupersededBy` (schema.org has `supersededBy`) and the headline flag is `isHeadline` (schema.org has `headline`).

The published context (P4-S6-T01; 08 S5.8). CONTEXT, site/public/ns/croissant-benchmark/v1/context.jsonld, is served at
CONTEXT_URL, beside the namespace it defines, and the site's /ns/croissant-benchmark/v1/ page documents it.
`context_document()` is its whole content and `bench schema gen` writes it (tools/build/codegen.py renders it), so the
codegen drift check holds the committed file to TERMS as it holds the extension schema. Its @context is a two-entry
array, the upstream context first, then `extension_context()` -- `cb` and one key per extension term, exactly the keys
the documents carry beside the upstream context:

  upstream    named by CROISSANT_VERSION, not copied. MLCommons publishes the Croissant context inline in the
              specification's appendix and serves no context document at that IRI (it redirects to the specification
              page, as read on 2026-11-18), so a JSON-LD processor that loads this file needs a document loader that
              answers that IRI with the context the pinned mlcroissant writes. The documents the build emits need
              neither this file nor such a loader: they inline the upstream context and these keys (`context()`)
  ours        after the upstream, so a key here that was an upstream term would redefine it, which `context()` refuses
              at every build. The guard over the published file itself is the croissant checker later in P4-S6

The host is NS_HOST, here as everywhere, so fixing it regenerates this file with the rest.

The mapping. taxonomy/crosswalks/croissant.yaml is the written mapping and tests/build/test_croissant.py holds it to
schema/croissant_benchmark.py, as tests/test_crosswalks.py holds its `rows` to schema/benchmark.py's CROISSANT_TERMS:

  base terms   CROISSANT_TERMS, schema.org terms Croissant uses, for the seven Benchmark fields that have one. Only
               those: a Benchmark field with no row there gets a cb: term, never an unlisted schema.org one, so the
               crosswalk cannot be silently incomplete. `license` is the model's computed licence (ADR-0024), read
               by re-validating the published record, because corpus.json carries no computed field
  TERMS        every extension property: term -> (the class it is a property of, the field of ours it carries).
               08 S5.8's five groups -- tasks, metrics, protocol, conditions, lineage -- are the Benchmark-level
               terms; each groups the node properties below it. None is a node that gathers several fields
  REUSES       the schema.org terms a node of ours reuses with their schema.org meaning, on another entity's fields
               (a Metric's id, name and range)
  CLASSES      the seven cb: classes

A Task node carries Benchmark.task and the admissibility fields 15 A8 files under cb:Task; a Metric node is one of
the benchmark's metrics (the headline first, then `metrics` in order) joined to the published Metric, or, for a
benchmark that records its scoring as named notes rather than Metric ids (CASP), the note's name; a Protocol node
gathers the submission process, the data access class, the aggregation policy and the subsets; an EvalConditions node
the reference conditions, the comparability profile, the material set, the rating-pool flag and the reference record's
condition values (below); a Lineage node the role and the supersession, subset, extension,
decontamination, variant and fork edges, each to a benchmark id. A null, an empty list and a node with nothing in it
are left out rather than written; `false` is written. 15 A8 leaves ResultClaim and Baseline unmapped on purpose, and
the YAML's `unmapped` lists those and the rest with their reasons.

P4-S6-T02 mapped every material field (ADR-0030), and P4-S6-T03 emits them, each from the committed mapping:

  benchmarkVersions  each of the record's versions by its tag, and Protocol's `subsets` each subset by its id: the
                     values a claim's benchmark_version and subset name (MATERIAL_KEY)
  materialFields     the benchmark's resolved material set (tools/build/comparability.py's resolve_profile: the
                     profiles its facets hit, or its pinned one, plus material_extra, less material_waived), in the
                     key's order, each field as the condition terms that carry it (terms_for; `sampling` is three). A
                     material field no term carries refuses the build: the set would be published short
  ratingPoolRequired the comparability block's flag, written when false too
  condition terms    the reference conditions record's value for each term in CONDITION_TERMS, walked along the
                     term's own path in TERMS (`EvalConditions.sampling.top_p` -> samplingTopP), so a term added to
                     the mapping is emitted with no change here. A null is left out; an answered empty list
                     (`tools_allowed: []`, no tools) is a value and is kept. A reference no conditions record answers
                     refuses the build

The conditions records are artifacts.Build.conditions, the ones the loader read that pass tier 1, held by one file
each; corpus.json carries none (08 S4.2), so the records reach the documents only through the build. TERMS is the
mapping's `extension.terms` by test (tests/build/test_croissant.py), and `documents()` holds the two equal at every
build as well, so a document is never emitted through a mapping the committed YAML does not state.

Release artifacts, not page assets (08 S5.8). The documents are S9's: never under the hashed /data/ namespace or in
the manifest's `paths`, and --data-only writes none. The site reads them as written (site/src/lib/croissant.ts) to
inline on the detail page and to serve as cite.jsonld, so the page's JSON-LD and the release's documents are one
emission. `release_payload()` is their part of a tagged release's payload (05 S10; docs/releasing.md), after the
file-count assertion, `count_problems()`: the directory holds exactly one document per published benchmark and the
collection. tools/build/manifest.py asserts it when it records the directory in build-manifest.json's `documents`, and
S13 asserts it again from the manifest's own counts. Assembling the rest of the release (data.tar.gz, corpus.csv.zip,
index.sqlite's hash) is P4-S7-T01's.

Validation, inside the build, so CI's `bench build` step enforces it (08 S5.8, "Validation in CI"). `check()` holds
every document to two things, and the build writes nothing if one fails:

  base         mlcroissant.Dataset over the document, which is what `mlcroissant validate` runs: any error fails it,
               and so does any warning other than "property ... is recommended, but does not exist": version,
               datePublished and citeAs, which no mapped field supplies yet (the YAML's `unmapped` says why), and
               license where the record states none
  extension    jsonschema against the COMMITTED schema/generated/croissant-benchmark.schema.json, which
               `bench schema gen` generates from schema/croissant_benchmark.py's Pydantic models (tools/build/codegen.py
               renders it, so the codegen drift check covers it). A model or mapping change that is not regenerated
               fails here as well as in CI job 5

Every benchmark that passes tier 1 is validated, the ai-drafted-unverified ones too (artifacts.Build.withheld): no
entry is published yet, and until one is, the drafts are the only documents there are to hold a mapping change to
base conformance in the pull request that makes it. Only the published ones are written.

Determinism (08 S6): emit.serialise's canonical bytes, documents in id order, no clock; write() removes a document
the build no longer emits, so the directory is exactly this build's.

The licence constraint (04 S5): the Croissant specification is CC BY-ND. This module and the YAML name terms; neither
restates the specification.
"""
from __future__ import annotations

import argparse
import copy
import functools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from schema.benchmark import CROISSANT_TERMS, Benchmark  # noqa: E402
# The extension's vocabulary and models, which P4-S6-T02 moved to schema/ (ADR-0030). Imported by name, so TERMS here
# is the same dict as there; the classes, REUSES and models are read through this module by its callers and tests.
from schema.croissant_benchmark import (  # noqa: E402,F401
    CLASSES, CONDITION_TERMS, CROISSANT_VERSION, DATA_LICENCE, DRAFT, EXTENSION_VERSION, NAMESPACE, NS_HOST, PREFIX,
    REUSES, SCHEMA, SCHEMA_ORG, TERMS, BenchmarkDocument, CollectionDocument, ConditionsNode, LineageNode, MetricNode,
    ProtocolNode, TaskNode, json_schema, terms_for)
from tools.build import comparability  # noqa: E402
from tools.build.emit import Refused, by_id, fold, nfc, serialise  # noqa: E402

DIR = 'croissant-benchmark'                                     # under the build's --out
COLLECTION = '_collection.jsonld'
MAPPING = 'taxonomy/crosswalks/croissant.yaml'                  # the committed mapping; `extension.terms` is TERMS
CONTEXT = 'site/public/ns/croissant-benchmark/v1/context.jsonld'          # the published context (P4-S6-T01)
CONTEXT_URL = 'https://%s/ns/croissant-benchmark/v1/context.jsonld' % NS_HOST   # where the site serves CONTEXT
CONTEXT_CACHE = 'public, max-age=604800'        # site/public/_headers' /ns/* rule, a week; it says why not immutable
# The one class of mlcroissant warning a document may carry (module docstring, "Validation").
RECOMMENDED = re.compile(r'^\[[^\]]*\] Property "[^"]+" is recommended, but does not exist\.$')


# ---- the context ----------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def upstream_context() -> tuple:
    """The Croissant @context for CROISSANT_VERSION, as the pinned mlcroissant writes it (items, to be cacheable)."""
    import mlcroissant as mlc
    from mlcroissant._src.core.rdf import make_context
    return tuple(make_context(mlc.Context(conforms_to=CROISSANT_VERSION)).items())


@functools.lru_cache(maxsize=None)
def schema_org_terms() -> frozenset[str]:
    from rdflib.namespace import SDO
    return frozenset(str(u)[len(SCHEMA_ORG):] for u in dir(SDO) if str(u).startswith(SCHEMA_ORG))


def extension_context() -> dict:
    """Our keys of the @context: the prefix, then one per extension term, each the term in our namespace."""
    return {PREFIX: NAMESPACE, **{t: '%s:%s' % (PREFIX, t) for t in TERMS}}


def context_document() -> dict:
    """The published context, CONTEXT (module docstring): the upstream context by its IRI, then ours."""
    return {'@context': [CROISSANT_VERSION, extension_context()]}


def context() -> dict:
    """The documents' @context; raises Refused if an extension key would redefine an upstream term."""
    upstream = dict(upstream_context())
    ours = extension_context()
    clash = sorted(set(ours) & (set(upstream) | schema_org_terms()))
    if clash:
        raise Refused(['croissant: extension key %s is already an upstream term (%s); name ours differently'
                       % (k, 'the Croissant context' if k in upstream else 'schema.org') for k in clash])
    return {**upstream, **ours}


# ---- the documents --------------------------------------------------------------------------------------------

def _prune(x):
    """A null, an empty list and a node with only its @type are left out; `false` and 0 stay."""
    if isinstance(x, dict):
        out = {k: v for k, v in ((k, _prune(v)) for k, v in x.items()) if v is not None and v != []}
        return None if set(out) == {'@type'} else out
    if isinstance(x, list):
        return [v for v in (_prune(v) for v in x) if v is not None]
    return x


def task_node(b: dict) -> dict:
    t = b.get('task') or {}                    # get-default: a record may have no task block
    return {'@type': 'cb:Task', 'input': t.get('input') or [], 'output': t.get('output'),
            'scoring': t.get('scoring'), 'testsHiddenFromSystem': t.get('tests_hidden_from_system'),
            'evaluationTarget': b['evaluation_target'], 'executionMode': b['execution_mode'],
            'groundTruthSource': b['ground_truth_source']}


def metric_nodes(b: dict, metrics: dict[str, dict]) -> list[dict]:
    if isinstance(b['metrics'], dict):         # named scoring notes, not Metric ids (schema/benchmark.py)
        return [{'@type': 'cb:Metric', 'name': name, 'isHeadline': False} for name in b['metrics']]
    ids = list(dict.fromkeys(([b['headline_metric']] if b['headline_metric'] else []) + list(b['metrics'])))
    out = []
    for mid in ids:
        m = metrics.get(mid)                   # get-default: an unpublished metric is named by its id alone
        node = {'@type': 'cb:Metric', 'identifier': mid, 'name': m['name'] if m else mid,
                'isHeadline': mid == b['headline_metric']}
        if m:
            rng = m['range'] or {}
            node.update({'valueType': m['value_type'], 'optimum': m['optimum'], 'optimumTarget': m['optimum_target'],
                         'minValue': rng.get('min'), 'maxValue': rng.get('max'), 'unbounded': m['unbounded']})
        out.append(node)
    return out


def protocol_node(b: dict) -> dict:
    sub = b['governance']['submission_process']
    return {'@type': 'cb:Protocol', 'submissionProcess': sub if isinstance(sub, list) else [] if sub is None else [sub],
            'dataAccess': b['data']['access'], 'aggregationPolicy': b['aggregation_policy'],
            'subsets': [s['id'] for s in b['subsets']]}


def material_terms(model: Benchmark, profiles) -> list[str]:
    """The benchmark's resolved material set as condition terms, in the key's order (sorted fields); raises Refused for
    a material field no term carries, since materialFields would then name less than the key is built over."""
    try:
        material = comparability.resolve_profile(model, profiles).material
    except ValueError as e:                    # a material_extra or waiver naming no EvalConditions field
        raise Refused(['%s.jsonld: %s' % (model.id, e)])
    unmapped = [f for f in material if not terms_for(f)]
    if unmapped:
        raise Refused(['%s.jsonld: material field(s) %s carry no extension term (%s lists them unmapped), so '
                       'materialFields cannot name the set the comparability key is built over; map them'
                       % (model.id, ', '.join(unmapped), MAPPING)])
    return [t for f in material for t in terms_for(f)]


def condition_values(record: dict) -> dict:
    """term -> the conditions record's value, for every condition term, walked along the term's path in TERMS; a null
    is left out, and an answered empty list is kept (the caller adds these after _prune, which would drop it)."""
    out = {}
    for term in CONDITION_TERMS:
        v = record
        for seg in TERMS[term][1].split('.')[1:]:
            v = v[seg] if isinstance(v, dict) else None        # a null `sampling` answers none of its keys
        if v is not None:
            out[term] = v
    return out


def conditions_node(b: dict, material: list[str]) -> dict:
    """The reference, the profile, the material set and the rating-pool flag; the reference record's values are
    condition_values', added by benchmark_document."""
    comp = b['comparability']
    return {'@type': 'cb:EvalConditions', 'conditionsId': b['reference_conditions'],
            'comparabilityProfile': comp['profile'], 'materialFields': material,
            'ratingPoolRequired': comp['rating_pool_required']}


def lineage_node(b: dict) -> dict | None:
    L = b['lineage']
    if L is None:
        return None
    return {'@type': 'cb:Lineage', 'lineageRole': L['role'], 'supersedes': L['supersedes'],
            'isSupersededBy': L['superseded_by'], 'subsetOf': L['subset_of'], 'extendedBy': L['extended_by'],
            'decontaminates': L['decontaminates'], 'variants': [v['id'] for v in L['variants']],
            'forks': [f['id'] for f in L['forks']]}


def benchmark_document(b: dict, metrics: dict[str, dict], ctx: dict, conditions: dict[str, dict] | None = None,
                       profiles=None) -> dict:
    """One corpus.json benchmark record's document. `conditions` is the build's conditions records by id
    (artifacts.Build.conditions), `profiles` taxonomy/comparability-profiles.yaml as loaded (read when not given).
    Raises Refused for a reference no record answers or a material field no term carries."""
    model = Benchmark.model_validate(b)        # the computed licence (ADR-0024), which corpus.json leaves out
    ref, record = b['reference_conditions'], None
    if ref is not None:
        record = (conditions or {}).get(ref)
        if record is None:
            raise Refused(['%s.jsonld: reference_conditions %s has no conditions record in this build (no file under '
                           'data/conditions/ that passes tier 1 holds it alone)' % (b['id'], ref)])
    material = material_terms(model, profiles or comparability.load_profiles())
    doc = {'@context': ctx, '@type': ['sc:Dataset', 'cb:Benchmark'], 'conformsTo': [CROISSANT_VERSION, EXTENSION_VERSION]}
    for field, term in CROISSANT_TERMS.items():
        doc[term.split(':', 1)[1]] = model.license if field == 'license' else b[field]
    doc.update({'benchmarkId': b['id'], 'benchmarkVersions': [v['version'] for v in b['versions']],
                'tasks': [task_node(b)], 'metrics': metric_nodes(b, metrics), 'protocol': protocol_node(b),
                'conditions': conditions_node(b, material), 'lineage': lineage_node(b)})
    out = _prune(doc)
    if record is not None:                     # after the prune, which would drop an answered empty list
        out['conditions'].update(condition_values(record))    # never pruned: ratingPoolRequired is a bool
    return nfc(out)


def collection_document(benchmarks: list[dict], ctx: dict, root: str = ROOT) -> dict:
    """The catalogue as one Dataset, named and cited as CITATION.cff names and cites it."""
    from schema.taxonomy import read_yaml
    cff = read_yaml(os.path.join(root, 'CITATION.cff'))
    doc = {'@context': ctx, '@type': ['sc:Dataset', 'cb:BenchmarkCollection'],
           'conformsTo': [CROISSANT_VERSION, EXTENSION_VERSION], 'name': cff['title'],
           'description': fold(cff['abstract']), 'url': cff['repository-code'], 'license': DATA_LICENCE,
           'citeAs': '%s. https://doi.org/%s' % (cff['title'], cff['doi']),
           'hasPart': [{'@id': '%s.jsonld' % b['id'], '@type': 'cb:Benchmark', 'name': b['name'],
                        'benchmarkId': b['id']} for b in by_id(benchmarks)]}
    return nfc(doc)


def mapping_problems(root: str = ROOT) -> list[str]:
    """The committed mapping's `extension.terms` against TERMS, which the documents are emitted through: one line per
    term the two disagree on. Empty means every document is emitted from what the YAML states."""
    from schema.taxonomy import read_yaml
    rows = read_yaml(os.path.join(root, MAPPING))['extension']['terms']
    stated = {r['term']: (r['on'], r['ours']) for r in rows}
    listed = [r['term'] for r in rows]
    out = ['croissant: %s states term %s twice' % (MAPPING, t) for t in sorted(stated) if listed.count(t) > 1]
    for t in sorted(set(stated) | set(TERMS)):
        if stated.get(t) != TERMS.get(t):
            out.append('croissant: term %s is %s in %s but %s in schema/croissant_benchmark.py; the documents are '
                       'emitted from the committed mapping, so the two must agree'
                       % (t, stated.get(t), MAPPING, TERMS.get(t)))
    return out


def documents(corpus: dict, withheld: dict[str, dict] | None = None,
              conditions: dict[str, dict] | None = None) -> tuple[dict[str, dict], dict[str, dict]]:
    """(file name -> document for every published benchmark and the collection, file name -> document for every
    withheld draft, which is validated and never written). `conditions` is artifacts.Build.conditions. Raises Refused
    with every benchmark's problem when one cannot be emitted from the mapping."""
    problems = mapping_problems()
    if problems:
        raise Refused(problems)
    ctx = context()
    profiles = comparability.load_profiles()
    metrics = {m['id']: m for m in corpus['entities']['metric']}
    published = corpus['entities']['benchmark']
    docs, held, errors = {}, {}, []
    for target, records in ((docs, by_id(published)), (held, by_id((withheld or {}).values()))):
        for b in records:
            try:
                target['%s.jsonld' % b['id']] = benchmark_document(b, metrics, ctx, conditions, profiles)
            except Refused as e:
                errors += e.errors
    if errors:
        raise Refused(errors)
    docs[COLLECTION] = collection_document(published, ctx)
    return docs, held


# ---- the release payload and the file-count assertion -------------------------------------------------------------

def names(corpus: dict) -> list[str]:
    """The file names one build writes into DIR for `corpus`: one document per published benchmark, and the
    collection, in byte order."""
    return sorted(['%s.jsonld' % b['id'] for b in corpus['entities']['benchmark']] + [COLLECTION],
                  key=lambda n: n.encode('utf-8'))


def count_problems(folder: str, corpus: dict) -> list[str]:
    """The file-count assertion: `folder` holds exactly one document per benchmark `corpus` publishes and the
    collection, and nothing else. One line per way it does not; empty means it holds."""
    want = names(corpus)
    have = sorted(os.listdir(folder), key=lambda n: n.encode('utf-8')) if os.path.isdir(folder) else []
    if have == want:
        return []
    out = ['%s: %d file(s), but the corpus publishes %d benchmark(s), so %d: one document each and the collection'
           % (folder, len(have), len(want) - 1, len(want))]
    out += ['%s: no %s, which the build emits' % (folder, n) for n in sorted(set(want) - set(have))]
    out += ['%s: %s is not a document this build emits' % (folder, n) for n in sorted(set(have) - set(want))]
    return out


def release_payload(folder: str, corpus: dict) -> list[str]:
    """The documents' part of a tagged release's payload (05 S10, docs/releasing.md): each as its path under --out,
    `croissant-benchmark/<name>`, in byte order. Raises Refused unless the file-count assertion holds, so a release
    never carries a stale, missing or stray document."""
    problems = count_problems(folder, corpus)
    if problems:
        raise Refused(problems)
    return ['%s/%s' % (DIR, n) for n in names(corpus)]


# ---- validation -----------------------------------------------------------------------------------------------

def mlcroissant_version() -> str:
    from importlib.metadata import version
    return version('mlcroissant')


def base_problems(doc: dict) -> tuple[list[str], int]:
    """mlcroissant's verdict on one document: (every error and every warning that is not a recommended-property
    notice, the number of recommended-property notices)."""
    import mlcroissant as mlc
    try:
        dataset = mlc.Dataset(jsonld=copy.deepcopy(doc))
    except mlc.ValidationError as e:
        return [' '.join(str(e).split())], 0
    warnings = sorted(dataset.metadata.ctx.issues.warnings)
    return [w for w in warnings if not RECOMMENDED.match(w)], sum(1 for w in warnings if RECOMMENDED.match(w))


def schema_validators(root: str = ROOT) -> dict:
    """document kind -> a Draft 2020-12 validator over the committed extension schema's definition of it."""
    import jsonschema                          # the dev group's pin (docs/pins.md), which `uv run` installs
    path = os.path.join(root, SCHEMA)
    if not os.path.exists(path):
        raise Refused(['croissant: %s is missing; run `bench schema gen`' % SCHEMA])
    with open(path, encoding='utf-8') as fh:
        schema = json.load(fh)
    return {kind: jsonschema.Draft202012Validator({'$schema': DRAFT, '$defs': schema['$defs'],
                                                   '$ref': '#/$defs/%s' % kind})
            for kind in ('BenchmarkDocument', 'CollectionDocument')}


def check(docs: dict[str, dict], root: str = ROOT) -> tuple[list[str], int]:
    """(every problem with `docs` -- file name -> document -- one line each, the recommended-property notices
    counted). Empty means each passes mlcroissant base conformance and the committed extension schema."""
    from absl import logging as absl_logging
    validators = schema_validators(root)
    verbosity = absl_logging.get_verbosity()
    absl_logging.set_verbosity(absl_logging.ERROR)   # mlcroissant logs every warning; they are returned instead
    out, notices = [], 0
    try:
        for name, doc in sorted(docs.items()):
            problems, n = base_problems(doc)
            notices += n
            out += ['%s: fails Croissant base conformance (mlcroissant %s, %s): %s'
                    % (name, mlcroissant_version(), CROISSANT_VERSION, p) for p in problems]
            kind = 'CollectionDocument' if name == COLLECTION else 'BenchmarkDocument'
            for e in sorted(validators[kind].iter_errors(doc), key=lambda e: (list(e.absolute_path), e.message)):
                out.append('%s: fails %s at /%s: %s' % (name, SCHEMA, '/'.join(str(p) for p in e.absolute_path),
                                                        e.message))
    finally:
        absl_logging.set_verbosity(verbosity)
    return out, notices


def build(corpus: dict, withheld: dict[str, dict] | None = None, root: str = ROOT,
          conditions: dict[str, dict] | None = None) -> tuple[dict[str, dict], list[str], dict]:
    """(the documents to write, every problem, a summary) for one build: the published benchmarks' documents and the
    collection, and the withheld drafts' documents, all validated. `conditions` is artifacts.Build.conditions, which
    a benchmark's reference conditions are read from."""
    try:
        docs, held = documents(corpus, withheld, conditions)
        problems, notices = check({**held, **docs}, root)
    except Refused as e:
        return {}, e.errors, {}
    return docs, problems, {'written': len(docs) - 1, 'withheld': len(held), 'notices': notices,
                            'mlcroissant': mlcroissant_version()}


def write(docs: dict[str, dict], out_dir: str) -> list[str]:
    """Write the documents into `out_dir`, removing any .jsonld this build does not emit."""
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(os.listdir(out_dir)):
        if name.endswith('.jsonld') and name not in docs:
            os.remove(os.path.join(out_dir, name))
    written = []
    for name, doc in sorted(docs.items()):
        path = os.path.join(out_dir, name)
        with open(path, 'wb') as fh:
            fh.write(serialise(doc))
        written.append(path)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', required=True, metavar='DIR', help='a directory of written documents to validate')
    a = ap.parse_args(argv)
    docs = {}
    for name in sorted(os.listdir(a.check)):
        if name.endswith('.jsonld'):
            with open(os.path.join(a.check, name), encoding='utf-8') as fh:
                docs[name] = json.load(fh)
    problems, notices = check(docs)
    for line in problems:
        print('BLOCKING  croissant  %s' % line)
    print('croissant: %d document(s) checked, %d problem(s), %d recommended-property notice(s)'
          % (len(docs), len(problems), notices))
    return 1 if problems or not docs else 0


if __name__ == '__main__':
    sys.exit(main())
