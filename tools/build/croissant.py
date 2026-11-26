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
gathers the submission process, the data access class and the aggregation policy; an EvalConditions node the
reference conditions and the comparability profile; a Lineage node the role and the supersession, subset, extension,
decontamination, variant and fork edges, each to a benchmark id. A null, an empty list and a node with nothing in it
are left out rather than written; `false` is written. 15 A8 leaves ResultClaim and Baseline unmapped on purpose, and
the YAML's `unmapped` lists those and the rest with their reasons.

P4-S6-T02 mapped every material field (ADR-0030): the benchmark's versions and subsets, its resolved material set and
rating-pool rule, and one cb:EvalConditions term per condition field. The documents written here do not carry those
yet -- emitting them from the mapping is P4-S6-T03's -- but every document's context declares them, and the schema
the documents are validated against accepts them.

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
    CLASSES, CROISSANT_VERSION, DATA_LICENCE, DRAFT, EXTENSION_VERSION, NAMESPACE, NS_HOST, PREFIX, REUSES, SCHEMA,
    SCHEMA_ORG, TERMS, BenchmarkDocument, CollectionDocument, ConditionsNode, LineageNode, MetricNode, ProtocolNode,
    TaskNode, json_schema)
from tools.build.emit import Refused, by_id, fold, nfc, serialise  # noqa: E402

DIR = 'croissant-benchmark'                                     # under the build's --out
COLLECTION = '_collection.jsonld'
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
            'dataAccess': b['data']['access'], 'aggregationPolicy': b['aggregation_policy']}


def conditions_node(b: dict) -> dict:
    return {'@type': 'cb:EvalConditions', 'conditionsId': b['reference_conditions'],
            'comparabilityProfile': b['comparability']['profile']}


def lineage_node(b: dict) -> dict | None:
    L = b['lineage']
    if L is None:
        return None
    return {'@type': 'cb:Lineage', 'lineageRole': L['role'], 'supersedes': L['supersedes'],
            'isSupersededBy': L['superseded_by'], 'subsetOf': L['subset_of'], 'extendedBy': L['extended_by'],
            'decontaminates': L['decontaminates'], 'variants': [v['id'] for v in L['variants']],
            'forks': [f['id'] for f in L['forks']]}


def benchmark_document(b: dict, metrics: dict[str, dict], ctx: dict) -> dict:
    """One corpus.json benchmark record's document."""
    model = Benchmark.model_validate(b)        # the computed licence (ADR-0024), which corpus.json leaves out
    doc = {'@context': ctx, '@type': ['sc:Dataset', 'cb:Benchmark'], 'conformsTo': [CROISSANT_VERSION, EXTENSION_VERSION]}
    for field, term in CROISSANT_TERMS.items():
        doc[term.split(':', 1)[1]] = model.license if field == 'license' else b[field]
    doc.update({'benchmarkId': b['id'], 'tasks': [task_node(b)], 'metrics': metric_nodes(b, metrics),
                'protocol': protocol_node(b), 'conditions': conditions_node(b), 'lineage': lineage_node(b)})
    return nfc(_prune(doc))


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


def documents(corpus: dict, withheld: dict[str, dict] | None = None) -> tuple[dict[str, dict], dict[str, dict]]:
    """(file name -> document for every published benchmark and the collection, file name -> document for every
    withheld draft, which is validated and never written)."""
    ctx = context()
    metrics = {m['id']: m for m in corpus['entities']['metric']}
    published = corpus['entities']['benchmark']
    docs = {'%s.jsonld' % b['id']: benchmark_document(b, metrics, ctx) for b in by_id(published)}
    docs[COLLECTION] = collection_document(published, ctx)
    held = {'%s.jsonld' % b['id']: benchmark_document(b, metrics, ctx) for b in by_id((withheld or {}).values())}
    return docs, held


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


def build(corpus: dict, withheld: dict[str, dict] | None = None, root: str = ROOT) -> tuple[dict[str, dict], list[str], dict]:
    """(the documents to write, every problem, a summary) for one build: the published benchmarks' documents and the
    collection, and the withheld drafts' documents, all validated."""
    try:
        docs, held = documents(corpus, withheld)
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
