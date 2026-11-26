#!/usr/bin/env python3
"""Validate every croissant-benchmark document in CI, hold the extension schema to base-Croissant conformance, and
refuse any committed copy of the Croissant specification's text (P4-S6-T04; 08 S5.8 "Validation in CI", 05 S9, 04 S5).

    python scripts/check_croissant.py --all          # every document a build emits or withholds; the CI job's command
    python scripts/check_croissant.py                # the schema, the published context and the spec guard only
    python scripts/check_croissant.py --all --schema PATH      # the same, held to another extension schema
    python scripts/check_croissant.py --corpus DIR   # --all, with the documents built from another tree (a fixture)
    python scripts/check_croissant.py --fingerprint SPEC.md [SPEC.md ...]   # regenerate FINGERPRINTS (below)

08 S5.8: "Each emitted document is validated with `mlcroissant` for base-Croissant conformance and against our own JSON
Schema for the extension terms. A schema change that breaks base conformance fails the build. An extension nobody can
validate is a blog post." tools/build/croissant.py already runs both validators inside `bench build`; this is the
standalone check pr-validate.yml's `croissant-benchmark` job runs, so the obligation is a job of its own that goes red
on its own, and it adds what a build cannot see: the schema's own conformance, the published context, and the licence.

What --all validates. No entry is published yet (every committed benchmark is an ai-drafted-unverified draft, which
05 S4 publishes none of), so a plain `bench build` writes one document, the collection, and validates every draft's
document without writing it; scripts/preview_corpus.py writes the drafts' documents and a collection listing them. --all
is the union, built in memory from one `artifacts.build` over the repository (tools/build/croissant.py's `documents`):

  published   one document per published benchmark (none today) and the collection `bench build` writes
  drafts      one document per draft that passes tier 1, the documents `bench build` withholds and the preview writes
  preview     the collection over published and drafts together, the one the preview writes

Nothing is published to raise a count, and no status is read but the build's own. Five checks, every one blocking:

  base        mlcroissant over each document (tools/build/croissant.py's base_problems, which is what `mlcroissant
              validate` runs): any error fails it, and so does any warning but a recommended-property notice
  extension   the extension schema (default: the committed schema/generated/croissant-benchmark.schema.json, which
              `bench schema gen` generates from schema/croissant_benchmark.py) over each document, Draft 2020-12
  context     each document's @context is exactly the upstream context the pinned mlcroissant writes plus the
              published context's own keys, read from the committed site/public/ns/croissant-benchmark/v1/
              context.jsonld; and that file is a two-entry array, the upstream context's IRI first, whose keys bind
              only our namespace, redefine no upstream key and no schema.org term, and are exactly the keys the
              schema pins. The upstream context comes from mlcroissant, the extension's from the local file:
              nothing is fetched, ever, and no TLS setting is touched
  schema      the extension schema cannot admit a document that fails base conformance (below)
  spec        no committed file carries the Croissant specification's text (below)

"A schema change that breaks base conformance" (08 S5.8). mlcroissant validates the documents the emitter writes, which
is necessary and not sufficient: a schema change can loosen what the extension admits without changing one emitted
document, and mlcroissant 1.1.1 itself enforces little at the dataset level (a missing name is an error only for a 0.8
document; a context that redefines `name`, or a bare key that no context binds, passes it). So the schema is held to
base conformance directly, as five rules:

  meta        it is a valid Draft 2020-12 schema
  context     its Context pins `@vocab` and `sc` to schema.org, `cb` to the namespace, and every other key it pins to
              `cb:<key>`, required; none of those keys is an upstream context key or a schema.org term (a redefinition)
  properties  every property a document or node admits is a JSON-LD keyword, a key the Context pins, an upstream
              context key or a schema.org term: anything else would expand under the upstream @vocab into a
              schema.org IRI schema.org does not define
  essentials  a document of either kind whose @type lacks sc:Dataset (mlcroissant: "doesn't extend
              https://schema.org/Dataset"), or whose conformsTo lacks the Croissant version, is rejected
  minimal     the smallest document of each kind the schema admits (a real one, every property the schema leaves
              optional removed) passes mlcroissant

`essentials` and `minimal` need a document of each kind to probe from, so they run with --all; without it the check
says so rather than passing them. tests/test_check_croissant.py turns each rule red with a deliberately broken schema,
and the CI job's last step runs that file, so a check that has stopped catching a broken schema fails too.

The specification guard (04 S5, 08 S5.8: "we may never republish a modified copy of the spec"). The Croissant
specification is CC BY-ND 4.0; the extension is a separate document in our own namespace precisely so nothing of it is
ever copied here. The guard cannot hold the text it looks for, since that would be the copy, so FINGERPRINTS holds
hashes: the specification's prose (fenced code removed, because every Croissant document shares its JSON-LD examples),
NFKC-normalised, casefolded and split into words, every SHINGLE-word run hashed with SHA-256, and the runs whose hash
is 0 mod SAMPLE kept, truncated to 64 bits. Sampling by value is position-independent, so a copied passage of W words
carries about (W - SHINGLE + 1) / SAMPLE of them wherever it sits. Every committed file (`git ls-files`, text only, the
fingerprint file itself excepted) is normalised the same way, and one sharing THRESHOLD or more fingerprints is a copy.
Measured over random passages of the 1.1 prose on 2026-11-26: a verbatim passage of 80 words is caught 98 times in 100,
of 60 words 87 and of 40 words 57, while a 20-word one is caught 4 times in 100, so a sentence quoted with its
attribution stays below it. On that date no committed file shared a single fingerprint. A committed file the guard
cannot list or read fails rather than passing unscanned.

FINGERPRINTS was computed on 2026-11-26 from docs/croissant-spec-1.0.md and docs/croissant-spec-1.1.md of the
specification's repository (github.com/mlcommons/croissant) at commit 5be19989e9aa82ec14f29e93db817f678ab93d03, read
through raw.githubusercontent.com and never committed; `sources` in the file records each copy's SHA-256. To refresh
it for a new version, download the specification's Markdown outside the repository and run --fingerprint over it.

Exit 0 when every check holds, 1 otherwise.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.build import croissant  # noqa: E402
from tools.build.emit import Refused  # noqa: E402

FINGERPRINTS = 'scripts/croissant_spec_fingerprints.json'
SHINGLE = 8                     # words per hashed run
SAMPLE = 8                      # a run is a fingerprint when its hash is 0 mod SAMPLE
THRESHOLD = 4                   # fingerprints one committed file may share with the specification, less one
KEYWORDS = frozenset({'@context', '@type', '@id'})
KINDS = ('BenchmarkDocument', 'CollectionDocument')

FENCE = re.compile(r'^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$', re.M | re.S)
URL = re.compile(r'(?:https?|ftp)://\S+')
TAG = re.compile(r'<[^<>\n]*>')
LINK_TARGET = re.compile(r'\]\([^)\n]*\)')
WORD = re.compile(r'[^\W_]+')


# ---- the documents ------------------------------------------------------------------------------------------------

def emitted(corpus: str = ROOT) -> tuple[dict[str, dict], dict[str, int]]:
    """(name -> document for everything --all validates, the count of each part), built from the tree at `corpus` (the
    repository; a fixture in the tests); raises Refused when the build or the emission fails. A draft's name is its
    file name, as the preview writes it; the preview's collection is named apart from the published one, since both
    are _collection.jsonld on disk."""
    from tools.build import artifacts
    result = artifacts.build(corpus)
    if result.errors:
        raise Refused(['build: %s' % e for e in result.errors])
    docs, held = croissant.documents(result.corpus, result.withheld, result.conditions)
    preview = croissant.collection_document(result.corpus['entities']['benchmark'] + list(result.withheld.values()),
                                            croissant.context())
    out = {**held, **docs, 'preview/%s' % croissant.COLLECTION: preview}
    return out, {'published': len(docs) - 1, 'drafts': len(held), 'collections': 2}


def kind_of(name: str) -> str:
    return 'CollectionDocument' if os.path.basename(name) == croissant.COLLECTION else 'BenchmarkDocument'


def validators(schema: dict) -> dict:
    """document kind -> a Draft 2020-12 validator over `schema`'s definition of it, as tools/build/croissant.py builds
    them over the committed schema."""
    import jsonschema
    return {kind: jsonschema.Draft202012Validator({'$schema': croissant.DRAFT, '$defs': schema['$defs'],
                                                   '$ref': '#/$defs/%s' % kind}) for kind in KINDS}


def published_context(root: str = ROOT) -> dict:
    with open(os.path.join(root, croissant.CONTEXT), encoding='utf-8') as fh:
        return json.load(fh)


def ours(published: dict) -> dict:
    """The published context's own keys: its second entry, or {} when the file is not the two-entry array."""
    ctx = published.get('@context')            # get-default: a malformed file is reported by context_problems
    return ctx[1] if isinstance(ctx, list) and len(ctx) == 2 and isinstance(ctx[1], dict) else {}


class _Quiet:
    """mlcroissant logs every warning through absl; base_problems returns them instead."""
    def __enter__(self):
        from absl import logging as absl_logging
        self.log, self.was = absl_logging, absl_logging.get_verbosity()
        absl_logging.set_verbosity(absl_logging.ERROR)

    def __exit__(self, *exc):
        self.log.set_verbosity(self.was)


def document_problems(docs: dict[str, dict], schema: dict, published: dict) -> tuple[list[str], int]:
    """(one line per problem, the recommended-property notices counted) for `docs`, name -> document: mlcroissant,
    the extension schema, and the @context against the upstream context and the published one. A schema that fails
    `meta` holds no document (its own problem says why), so the documents meet the other two only."""
    checks = {} if meta_problems(schema) else validators(schema)
    want = {**dict(croissant.upstream_context()), **ours(published)}
    out, notices = [], 0
    with _Quiet():
        for name, doc in sorted(docs.items()):
            problems, n = croissant.base_problems(doc)
            notices += n
            out += ['%s: fails Croissant base conformance (mlcroissant %s, %s): %s'
                    % (name, croissant.mlcroissant_version(), croissant.CROISSANT_VERSION, p) for p in problems]
            errors = checks[kind_of(name)].iter_errors(doc) if checks else []
            for e in sorted(errors, key=lambda e: (list(e.absolute_path), e.message)):
                out.append('%s: fails the extension schema at /%s: %s'
                           % (name, '/'.join(str(p) for p in e.absolute_path), e.message))
            ctx = doc.get('@context')          # get-default: a document without one is reported on this line
            if ctx != want:
                keys = set(ctx) if isinstance(ctx, dict) else set()
                out.append('%s: its @context is not the upstream context plus %s (missing %s; extra %s; differing %s)'
                           % (name, croissant.CONTEXT, sorted(set(want) - keys) or 'none',
                              sorted(keys - set(want)) or 'none',
                              sorted(k for k in keys & set(want) if ctx[k] != want[k]) or 'none'))
    return out, notices


# ---- the published context ----------------------------------------------------------------------------------------

def upstream_keys() -> frozenset[str]:
    return frozenset(dict(croissant.upstream_context()))


def context_problems(published: dict, schema: dict) -> list[str]:
    """The committed context file: the upstream context's IRI first, then keys that bind only our namespace, redefine
    nothing upstream, and are exactly the keys the extension schema pins."""
    ctx = published.get('@context')            # get-default: a file without one is reported on the next line
    if not (isinstance(ctx, list) and len(ctx) == 2 and ctx[0] == croissant.CROISSANT_VERSION
            and isinstance(ctx[1], dict)):
        return ['%s: its @context must be [%r, {our keys}], the upstream context first, so no key of ours is read '
                'before it' % (croissant.CONTEXT, croissant.CROISSANT_VERSION)]
    mine, out = ctx[1], []
    for k, v in sorted(mine.items()):
        want = croissant.NAMESPACE if k == croissant.PREFIX else '%s:%s' % (croissant.PREFIX, k)
        if v != want:
            out.append('%s: %s is bound to %r; a key of ours binds %r, in our namespace'
                       % (croissant.CONTEXT, k, v, want))
        if k in upstream_keys() or k in croissant.schema_org_terms():
            out.append('%s: %s redefines %s; name ours differently' % (
                croissant.CONTEXT, k, 'an upstream context key' if k in upstream_keys() else 'a schema.org term'))
    pinned = {k for k in pins(schema) if k not in ('@vocab', 'sc')}
    if set(mine) != pinned:
        out.append('%s: its keys are not the ones the extension schema pins (extra %s; missing %s); `bench schema gen` '
                   'writes both' % (croissant.CONTEXT, sorted(set(mine) - pinned) or 'none',
                                    sorted(pinned - set(mine)) or 'none'))
    return out


# ---- the schema ---------------------------------------------------------------------------------------------------

def pins(schema: dict) -> dict[str, object]:
    """The Context definition's pinned keys: key -> its const (None where it has none)."""
    props = schema.get('$defs', {}).get('Context', {}).get('properties', {})   # get-default: reported as unpinned
    return {k: v.get('const') for k, v in props.items()}                       # get-default: a key with no const


def minimal(doc: dict, schema: dict, kind: str) -> dict:
    """`doc` with every top-level property the schema leaves optional removed."""
    required = set(schema['$defs'][kind].get('required', []))                  # get-default: none required
    return {k: copy.deepcopy(v) for k, v in doc.items() if k in required}


def meta_problems(schema: dict, label: str = croissant.SCHEMA) -> list[str]:
    """`meta`: a valid Draft 2020-12 schema defining both documents and the Context. Nothing else is checked against a
    schema that fails it."""
    import jsonschema
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as e:
        return ['%s: not a valid Draft 2020-12 schema: %s' % (label, e.message)]
    missing = [k for k in KINDS + ('Context',) if k not in schema.get('$defs', {})]   # get-default: none defined
    return ['%s: defines no %s' % (label, ', '.join(missing))] if missing else []


def schema_problems(schema: dict, samples: dict[str, dict] | None = None, label: str = croissant.SCHEMA) -> list[str]:
    """The extension schema held to base conformance (module docstring, "a schema change"), each problem prefixed with
    `label`, the schema's path. `samples` is a document of each kind to probe from; without them `essentials` and
    `minimal` are not run, and the caller says so."""
    meta = meta_problems(schema, label)
    if meta:
        return meta
    defs, out, pinned = schema['$defs'], [], pins(schema)
    required = set(defs['Context'].get('required', []))                        # get-default: none required
    for k, want in (('@vocab', croissant.SCHEMA_ORG), ('sc', croissant.SCHEMA_ORG),
                    (croissant.PREFIX, croissant.NAMESPACE)):
        if pinned.get(k) != want or k not in required:                         # get-default: an unpinned key
            out.append('%s: the Context must require %s, pinned to %r' % (label, k, want))
    terms = {k for k in pinned if k not in ('@vocab', 'sc', croissant.PREFIX)}
    for k in sorted(terms):
        if pinned[k] != '%s:%s' % (croissant.PREFIX, k) or k not in required:
            out.append('%s: the Context must require %s, pinned to %r: otherwise a document may bind it elsewhere, or '
                       'leave it to mean a schema.org term' % (label, k, '%s:%s' % (croissant.PREFIX, k)))
        if k in upstream_keys() or k in croissant.schema_org_terms():
            out.append('%s: the Context binds %s to our namespace, redefining %s' % (
                label, k, 'an upstream context key' if k in upstream_keys() else 'a schema.org term'))
    known = KEYWORDS | terms | upstream_keys() | croissant.schema_org_terms()
    for name, d in sorted(defs.items()):
        if name == 'Context':
            continue
        for p in sorted(set(d.get('properties', {})) - known):                 # get-default: a def with none
            out.append('%s: %s admits %s, which no context binds: under the upstream @vocab it would mean %s%s, '
                       'which schema.org does not define' % (label, name, p, croissant.SCHEMA_ORG, p))
    if samples:
        out += probe_problems(schema, samples, label)
    return out


def probe_problems(schema: dict, samples: dict[str, dict], label: str = croissant.SCHEMA) -> list[str]:
    """`essentials` and `minimal` (module docstring), from a document of each kind the schema admits."""
    checks, out = validators(schema), []
    for kind in KINDS:
        doc = samples[kind]
        if list(checks[kind].iter_errors(doc)):
            out.append('%s: rejects the %s it is probed from, so neither probe can run; the document check names why'
                       % (label, kind))
            continue
        broken = {'an @type without sc:Dataset': {**doc, '@type': [t for t in doc['@type'] if t != 'sc:Dataset']},
                  'a conformsTo without %s' % croissant.CROISSANT_VERSION:
                      {**doc, 'conformsTo': [c for c in doc['conformsTo'] if c != croissant.CROISSANT_VERSION]}}
        for what, d in broken.items():
            if not list(checks[kind].iter_errors(d)):
                out.append('%s: admits a %s with %s, which is no Croissant %s dataset'
                           % (label, kind, what, croissant.CROISSANT_VERSION))
        small = minimal(doc, schema, kind)
        if not list(checks[kind].iter_errors(small)):
            with _Quiet():
                problems, _ = croissant.base_problems(small)
            out += ['%s: admits a %s with only %s, which fails Croissant base conformance (mlcroissant %s): %s'
                    % (label, kind, ', '.join(sorted(small)), croissant.mlcroissant_version(), p)
                    for p in problems]
    return out


def samples_of(docs: dict[str, dict]) -> dict[str, dict]:
    """A document of each kind to probe from: the first of each in name order."""
    out = {}
    for name in sorted(docs):
        out.setdefault(kind_of(name), docs[name])
    return out


# ---- the specification guard ------------------------------------------------------------------------------------

def words(text: str, prose: bool = False) -> list[str]:
    """`text` as the guard reads it: NFKC, casefolded, URLs, tags and link targets out, then its words. `prose` also
    removes fenced code, which the specification's side drops (module docstring)."""
    text = unicodedata.normalize('NFKC', text).casefold()
    if prose:
        text = FENCE.sub(' ', text)
    return WORD.findall(TAG.sub(' ', LINK_TARGET.sub('] ', URL.sub(' ', text))))


def fingerprints_of(ws: list[str]) -> set[str]:
    out = set()
    for i in range(len(ws) - SHINGLE + 1):
        h = hashlib.sha256(' '.join(ws[i:i + SHINGLE]).encode('utf-8')).hexdigest()[:16]
        if int(h, 16) % SAMPLE == 0:
            out.add(h)
    return out


def fingerprint(paths: list[str]) -> dict:
    """The FINGERPRINTS document for local copies of the specification at `paths` (--fingerprint)."""
    sources, every = [], set()
    for path in paths:
        with open(path, 'rb') as fh:
            raw = fh.read()
        fps = fingerprints_of(words(raw.decode('utf-8'), prose=True))
        sources.append({'name': os.path.basename(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'fingerprints': len(fps)})
        every |= fps
    return {'$comment': 'Generated by `python scripts/check_croissant.py --fingerprint` from local copies of the '
                        'Croissant specification; it holds hashes, no text of it. Regenerate, do not edit.',
            'method': {'shingle': SHINGLE, 'sample': SAMPLE, 'hash': 'sha256, first 16 hex digits'},
            'sources': sources, 'fingerprints': sorted(every)}


def committed(root: str) -> list[str]:
    """Every committed path under `root`, relative; raises Refused when git cannot list them."""
    try:
        r = subprocess.run(['git', '-c', 'core.longpaths=true', '-c', 'core.quotepath=false', 'ls-files', '-z'],
                           cwd=root, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise Refused(['spec: cannot list the committed files under %s (%s), so none is vouched for' % (root, e)])
    return sorted(p for p in r.stdout.decode('utf-8').split('\0') if p)


def load_fingerprints(root: str = ROOT) -> set[str]:
    with open(os.path.join(root, FINGERPRINTS), encoding='utf-8') as fh:
        doc = json.load(fh)
    if doc['method'] != fingerprint([])['method']:
        raise Refused(['spec: %s was computed with %s, but the guard reads %s; regenerate it with --fingerprint'
                       % (FINGERPRINTS, doc['method'], fingerprint([])['method'])])
    return set(doc['fingerprints'])


def spec_problems(root: str = ROOT, fps: set[str] | None = None,
                  files: list[str] | None = None) -> tuple[list[str], dict]:
    """(one line per committed file that carries the specification's text, a summary). `files`, relative to `root`,
    defaults to every committed file; `fps` to FINGERPRINTS."""
    try:
        fps = load_fingerprints(root) if fps is None else fps
        files = committed(root) if files is None else files
    except Refused as e:
        return e.errors, {}
    out, scanned, worst = [], 0, (0, None)
    for rel in files:
        if rel.replace(os.sep, '/') == FINGERPRINTS:
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):                   # a committed file deleted in the working tree: nothing to read
            continue
        try:
            with open(path, 'rb') as fh:
                raw = fh.read()
        except OSError as e:
            out.append('%s: cannot be read (%s), so it is not vouched for' % (rel, e))
            continue
        if b'\0' in raw[:8192]:                        # binary: fonts, images, archives
            continue
        scanned += 1
        shared = len(fingerprints_of(words(raw.decode('utf-8', errors='replace'))) & fps)
        worst = max(worst, (shared, rel), key=lambda t: t[0])
        if shared >= THRESHOLD:
            out.append('%s: shares %d of the Croissant specification\'s %d fingerprints (%s), a copied passage of '
                       'about %d words or more. The specification is CC BY-ND 4.0: link to it, never commit its text '
                       '(04 S5, 08 S5.8)' % (rel, shared, len(fps), FINGERPRINTS, shared * SAMPLE + SHINGLE - 1))
    return out, {'scanned': scanned, 'most': worst[0], 'most_in': worst[1]}


# ---- the command --------------------------------------------------------------------------------------------------

def run(root: str = ROOT, corpus: str | None = None, schema_path: str | None = None,
        spec: bool = True) -> tuple[list[str], list[str]]:
    """(problems, the summary lines) of one run over the repository at `root`. `corpus` is the tree whose documents
    are built and checked (--all: the repository; None: no documents); `spec` False skips the guard (the tests')."""
    schema_path = schema_path or os.path.join(root, croissant.SCHEMA)
    with open(schema_path, encoding='utf-8') as fh:
        schema = json.load(fh)
    published = published_context(root)
    problems, summary = context_problems(published, schema), []
    docs, samples = {}, None
    if corpus is not None:
        try:
            docs, parts = emitted(corpus)
        except Refused as e:
            problems += e.errors
            parts = None
        if parts is not None:
            samples = samples_of(docs)
            if set(samples) != set(KINDS):
                problems.append('documents: the build emits no %s, so the schema probes cannot run; that is never a '
                                'pass' % ' or '.join(sorted(set(KINDS) - set(samples))))
                samples = None
            found, notices = document_problems(docs, schema, published)
            problems += found
            summary.append('documents: %d checked -- %d published benchmark(s), %d draft(s) that pass tier 1 (withheld '
                           'by `bench build`, written by the preview) and %d collections, the published and the '
                           'preview\'s; %d problem(s), %d recommended-property notice(s), mlcroissant %s'
                           % (len(docs), parts['published'], parts['drafts'], parts['collections'], len(found),
                              notices, croissant.mlcroissant_version()))
    try:
        shown = os.path.relpath(schema_path, root).replace(os.sep, '/')
    except ValueError:                                 # relpath raises across Windows drive letters
        shown = schema_path
    found = schema_problems(schema, samples, shown)
    problems += found
    summary.append('schema: %s, %d problem(s)%s' % (shown, len(found), '' if samples else
                                                   '; the essentials and minimal probes NOT RUN (they need --all)'))
    if spec:
        found, stats = spec_problems(root)
        problems += found
        if stats:
            summary.append('spec: %d committed text file(s) scanned, %d carrying the specification; the most any '
                           'shares is %d fingerprint(s) (%s), against a threshold of %d'
                           % (stats['scanned'], len(found), stats['most'], stats['most_in'] or 'none', THRESHOLD))
    return problems, summary


def main(argv=None, root: str = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--all', action='store_true', dest='everything',
                    help='also build and validate every document: published, the drafts, both collections')
    ap.add_argument('--corpus', metavar='DIR',
                    help='build the documents from this tree instead (a fixture); implies --all')
    ap.add_argument('--schema', metavar='PATH',
                    help='the extension schema to hold them to (default: the committed one)')
    ap.add_argument('--fingerprint', nargs='+', metavar='SPEC', help='write %s from local copies of the specification'
                    % FINGERPRINTS)
    a = ap.parse_args(argv)
    if a.fingerprint:
        with open(os.path.join(root, FINGERPRINTS), 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(fingerprint(a.fingerprint), fh, indent=1, ensure_ascii=False)
            fh.write('\n')
        print('check_croissant: wrote %s' % FINGERPRINTS)
        return 0
    problems, summary = run(root, a.corpus or (root if a.everything else None), a.schema)
    for line in problems:
        print('BLOCKING  croissant  %s' % line)
    for line in summary:
        print('croissant: %s' % line)
    print('croissant: %d problem(s)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
