"""`bench build [--out build/]`: the loader and publish rules behind the S8 artifacts (P0-S5-T05; 05 S3, 08 S4.2).

    bench build --out build/    # load data/, write build/corpus.json, build/facets.json and build/enums.json

08 S3.5 stages the pipeline, and this is the loader (S1) and the publish rules, wired to the S8
emitter (tools/build/emit.py, P2-S1-T02), which owns what the three artifacts hold -- exactly 08
S4.2's field lists -- the domain-group refusal and the serialisation. Every derived, claims, search
or release artifact belongs to the stage that 08 S3.5 ships it in.

What gets published. 05 S4: "Entries at this level are NOT published." So:

  - A Benchmark is published unless its `curation.verification_status` is ai-drafted-unverified,
    read from the raw file so that a draft which fails tier 1 is left out rather than failing the
    build; `bench validate` is where a broken draft blocks. A published record that fails tier 1
    fails the build: the build never ships a record its own models refuse.
  - A stub (data/{benchmarks,systems,organizations}/_stubs/, P3-S2-T07 and P3-S3-T04) is never
    published: 07 S2.4 withholds it "until a human assigns domain facets", a system or organisation
    stub lacks what 04 S7 requires, and each is reported as excluded, whether or not it loads.
  - Systems, Organizations and Metrics carry no curation block, so each is published when it loads.
  - A Source is published when a published record cites it -- the corpus is closed under source
    references, and a Source nothing published cites has no reader in the artifact. A cited Source
    that is missing or fails tier 1 fails the build. This is what keeps P0-S3-T04's draft Source
    records (unarchived, so failing tier 1) out without special-casing them.

Everything else under data/ (claims, conditions, leaderboards, baselines, ...) belongs to other
artifacts: 08 S4.2 puts "no claim records" in corpus.json. The claims under data/claims/ and the
conditions they name are read for one purpose, facets.json's claim-derived fields (emit.claim_fields).

Records are dumped in JSON mode by alias, without computed fields, so each one validates against its
own schema/generated/<kind>.schema.json -- the validation schema, which has no derived fields
(tools/build/codegen.py). A derived value is recomputable from what is published.

Subsets (02 S11 rule 4): "Inherited values are materialised into the build artifact ... Nothing
downstream ever walks the parent chain." corpus.json keeps each benchmark's `subsets` exactly as
curated, and adds a top-level `subsets` list with every subset's fully resolved facet block.
Inheritance is field-by-field replace: a subset's value for a facet is its own override, else its
nearest ancestor's, else the benchmark's. `overrides` names the facets the subset declares itself,
which is what the coverage rule ("a subset contributes only if it carries a domain_override") reads.

Determinism: files are read in sorted POSIX path order (tiers.discover) and written by emit.py's
serialisation (08 S6), so two builds of one tree are byte-identical.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from tools.build import emit
from tools.build.emit import ARTIFACTS, at, nfc, serialise  # noqa: F401 -- re-exported: adoption.py, the tests

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRAFT = 'ai-drafted-unverified'
STUB = 'unfaceted stub'                      # data/benchmarks/_stubs/ (P3-S2-T07)
CORPUS_KINDS = ('benchmark', 'system', 'organization', 'metric', 'source')   # 08 S4.2's corpus.json row
# A subset's resolved facet block: facet -> (the Subset field that overrides it, or None when a
# subset cannot override it, and the Benchmark field it inherits from).
SUBSET_FACETS = {
    'domain': ('domain_override', 'domain'),
    'capability': ('capability_override', 'capability'),
    'metric': ('metric_override', 'headline_metric'),
    'evaluation_method': (None, 'evaluation_method'),
    'designed_for_subjects': (None, 'designed_for_subjects'),
    'lifecycle': (None, 'lifecycle'),
}


@dataclass
class Build:
    corpus: dict = field(default_factory=dict)
    facets: dict = field(default_factory=dict)
    enums: dict = field(default_factory=dict)
    excluded: list[tuple[str, str, str]] = field(default_factory=list)    # (path, id, reason)
    errors: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.corpus['entities'].items()} if self.corpus else {}


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)


def status(raw: Any) -> str:
    """A benchmark file's verification_status, read without the model; absent means the model's default."""
    from schema.benchmark import Curation
    curation = raw.get('curation') if isinstance(raw, dict) else None
    if isinstance(curation, dict) and 'verification_status' in curation:
        return curation['verification_status']
    return Curation.model_fields['verification_status'].default


def cited_sources(record: dict) -> set[str]:
    from tools.validate.tiers import _walk_prefixed
    return {value for _, value, kind in _walk_prefixed(record, '') if kind == 'source'}


def resolve_subsets(b: dict) -> tuple[list[dict], list[str]]:
    """Every subset of one benchmark with its facets materialised; and any parent-chain errors."""
    by_id = {s['id']: s for s in b['subsets']}
    rows, errors = [], []
    for s in b['subsets']:
        chain, cur = [], s
        while cur is not None:
            if cur['id'] in [c['id'] for c in chain]:
                errors.append('%s: subset %s has a parent cycle (%s)'
                              % (b['id'], s['id'], ' -> '.join(c['id'] for c in chain + [cur])))
                break
            chain.append(cur)
            cur = by_id[cur['parent']] if cur['parent'] is not None else None
        else:
            facets, overrides = {}, []
            for facet, (override, inherited) in SUBSET_FACETS.items():
                declared = [c[override] for c in chain if override and c[override] is not None]
                facets[facet] = declared[0] if declared else b[inherited]
                if override and s[override] is not None:
                    overrides.append(facet)
            facets['domain'] = {k: facets['domain'][k] for k in ('primary', 'secondary')}  # a DomainOverride's shape
            rows.append({'id': s['id'], 'benchmark': b['id'], 'parent': s['parent'], 'label': s['label'],
                         'depth': len(chain), 'overrides': overrides, 'facets': facets})
    return rows, errors


def build(root: str = ROOT, drafts: bool = False) -> Build:
    """`drafts=True` is the preview build (scripts/preview_corpus.py; not a `bench build` flag, which 05 S3 does
    not list): an ai-drafted-unverified benchmark that passes tier 1 is included rather than excluded, and the
    corpus says `"drafts": true`, so that a person reviewing the drafts, and the site's page tests, can read them
    rendered. The site refuses to build from such a corpus unless
    it is told it is a preview (site/src/lib/corpus.ts), so a preview never ships as the published site."""
    from tools.validate import tiers
    out = Build()
    published: dict[str, dict[str, dict]] = {k: {} for k in CORPUS_KINDS}
    models: dict[str, BaseModel] = {}                  # the published benchmarks' models, for emit.claim_fields
    sources: dict[str, list] = {}
    claims: list = []
    conditions: dict[str, list] = {}

    def broken(r) -> str:
        return '; '.join(f.message for f in r.schema_findings if f.blocks)

    for r in tiers.load(root):
        kind = r.kind.name if r.kind else None
        if kind and kind.endswith('-stub'):          # 07 S2.4, 04 S7: withheld until a curator fills them in
            out.excluded.append((r.path, r.id, STUB if kind == 'benchmark-stub' else 'unreviewed %s' % kind))
            continue
        if kind == 'claim' and r.anchored.startswith('data/'):    # never vendor/: 08 S3.2's licence boundary
            claims.append(r)
            continue
        if kind == 'conditions':
            conditions.setdefault(r.id, []).append(r)
            continue
        if kind not in CORPUS_KINDS:
            continue
        if kind == 'source':
            sources.setdefault(r.id, []).append(r)
            continue
        if kind == 'benchmark' and r.parsed and status(r.raw) == DRAFT and not (drafts and r.model and not broken(r)):
            out.excluded.append((r.path, r.id, DRAFT + (' (and fails tier 1)' if broken(r) else '')))
            continue
        if not r.parsed or r.model is None or broken(r):
            out.errors.append('%s: %s would be published, but fails tier 1: %s'
                              % (r.path, r.id, broken(r) or 'no model loaded'))
            continue
        if r.id in published[kind]:
            out.errors.append('%s: a second %s with id %s' % (r.path, kind, r.id))
            continue
        published[kind][r.id] = dump(r.model)
        if kind == 'benchmark':
            models[r.id] = r.model

    citers: dict[str, list[str]] = {}
    for kind, records in published.items():
        for ident, rec in records.items():
            for sid in cited_sources(rec):
                citers.setdefault(sid, []).append('%s %s' % (kind, ident))
    for sid, rs in sorted(sources.items()):
        if sid not in citers:
            out.excluded += [(r.path, sid, 'no published record cites it') for r in rs]
        elif len(rs) > 1:
            out.errors.append('%s: source id %s is held by %d files' % (', '.join(r.path for r in rs), sid, len(rs)))
        elif rs[0].model is None or broken(rs[0]):
            out.errors.append('%s: %s is cited by %s, but fails tier 1: %s'
                              % (rs[0].path, sid, ', '.join(sorted(citers[sid])), broken(rs[0]) or 'no model loaded'))
        else:
            published['source'][sid] = dump(rs[0].model)
    for sid in sorted(set(citers) - set(sources)):
        out.errors.append('%s is cited by %s, but no data/sources/ file holds it' % (sid, ', '.join(sorted(citers[sid]))))

    subsets = []
    for ident in sorted(published['benchmark']):
        rows, errors = resolve_subsets(published['benchmark'][ident])
        subsets += rows
        out.errors += errors
    if out.errors:
        return out
    try:
        done = emit.emit({k: list(v.values()) for k, v in published.items()}, subsets, models, claims, conditions,
                         vocabulary_versions(), drafts=drafts)
    except emit.Refused as e:
        out.errors += e.errors
        return out
    out.corpus, out.facets, out.enums = done['corpus.json'], done['facets.json'], done['enums.json']
    return out


def vocabulary_versions(root: str = ROOT) -> dict[str, str]:
    """The vocabulary versions a build was made against (P0-S6-T06; 02 S4.3, 12 S5.1): the aggregate taxonomy
    version, and the two presentation-group files, which version themselves. A re-grouping of capability
    terms changes every coverage figure without touching a benchmark record, so the build says which grouping
    it used; P2-S1-T05's build-manifest.json carries this forward when it exists. It reads the repository's
    taxonomy/, because that is what the models were built from at import time (schema/benchmark.py), whatever
    data root the build was pointed at."""
    from schema.taxonomy import read_yaml
    tax = os.path.join(root, 'taxonomy')
    with open(os.path.join(tax, 'VERSION'), encoding='utf-8') as fh:
        out = {'taxonomy': fh.read().strip()}
    for name in ('capability_groups', 'domain_groups'):
        out[name] = str(read_yaml(os.path.join(tax, name + '.yaml'))['version'])
    return out


def write(result: Build, out_dir: str) -> list[str]:
    """The three files, through emit.write, which refuses a group id or a claim record again before writing."""
    return emit.write({'corpus.json': result.corpus, 'facets.json': result.facets, 'enums.json': result.enums},
                      out_dir)
