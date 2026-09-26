"""`bench build [--out build/]`, minimal: corpus.json and facets.json (P0-S5-T05; 05 S3, 08 S4.2).

    bench build --out build/    # load data/, write build/corpus.json and build/facets.json

08 S3.5 stages the pipeline, and this is the loader (S1) wired straight to a first emitter (S8)
for the two artifacts every later stage and the site start from. P2-S1-T02 owns the full S8
emitter -- exactly 08 S4.2's field lists, enums.json, the domain-group refusal -- and every
derived, claims, search or release artifact belongs to the stage that 08 S3.5 ships it in.

What gets published. 05 S4: "Entries at this level are NOT published." So:

  - A Benchmark is published unless its `curation.verification_status` is ai-drafted-unverified,
    read from the raw file so that a draft which fails tier 1 is left out rather than failing the
    build; `bench validate` is where a broken draft blocks. A published record that fails tier 1
    fails the build: the build never ships a record its own models refuse.
  - Systems, Organizations and Metrics carry no curation block, so each is published when it loads.
  - A Source is published when a published record cites it -- the corpus is closed under source
    references, and a Source nothing published cites has no reader in the artifact. A cited Source
    that is missing or fails tier 1 fails the build. This is what keeps P0-S3-T04's draft Source
    records (unarchived, so failing tier 1) out without special-casing them.

Everything else under data/ (claims, conditions, leaderboards, baselines, ...) belongs to other
artifacts: 08 S4.2 puts "no claim records" in corpus.json.

Records are dumped in JSON mode by alias, without computed fields, so each one validates against its
own schema/generated/<kind>.schema.json -- the validation schema, which has no derived fields
(tools/build/codegen.py). A derived value is recomputable from what is published.

Subsets (02 S11 rule 4): "Inherited values are materialised into the build artifact ... Nothing
downstream ever walks the parent chain." corpus.json keeps each benchmark's `subsets` exactly as
curated, and adds a top-level `subsets` list with every subset's fully resolved facet block.
Inheritance is field-by-field replace: a subset's value for a facet is its own override, else its
nearest ancestor's, else the benchmark's. `overrides` names the facets the subset declares itself,
which is what the coverage rule ("a subset contributes only if it carries a domain_override") reads.

Determinism: records sorted by id, keys sorted, every string NFC, compact separators, UTF-8, LF,
one trailing newline, and no clock: two builds of one tree are byte-identical.
"""
from __future__ import annotations

import json
import os
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORMAT = 1
DRAFT = 'ai-drafted-unverified'
CORPUS_KINDS = ('benchmark', 'system', 'organization', 'metric', 'source')   # 08 S4.2's corpus.json row
ARTIFACTS = ('corpus.json', 'facets.json')

# facets.json: key -> the Benchmark field it projects, as a dotted path. The two keys not listed
# are computed: `domain` is the family of domain.primary and `year` is the year of `released`.
# P2-S1-T02 completes 08 S4.2's field list (the claim-derived fields need claims to exist).
FACET_FIELDS = {
    'id': 'id',
    'slug': 'id',                       # a benchmark's URL slug is its id (05 S2)
    'name': 'name',
    'aliases': 'aliases',
    'subdomain': 'domain.primary',
    'domain_secondary': 'domain.secondary',
    'capability': 'capability',
    'evaluation_method': 'evaluation_method',
    'designed_for_subjects': 'designed_for_subjects',
    'lifecycle': 'lifecycle',
}
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
    excluded: list[tuple[str, str, str]] = field(default_factory=list)    # (path, id, reason)
    errors: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.corpus['entities'].items()} if self.corpus else {}


def nfc(x: Any) -> Any:
    if isinstance(x, str):
        return unicodedata.normalize('NFC', x)
    if isinstance(x, list):
        return [nfc(v) for v in x]
    if isinstance(x, dict):
        return {nfc(k): nfc(v) for k, v in x.items()}
    return x


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)


def at(record: dict, dotted: str) -> Any:
    for key in dotted.split('.'):
        record = record[key]
    return record


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


def facet_row(b: dict) -> dict:
    row = {key: at(b, path) for key, path in FACET_FIELDS.items()}
    row['domain'] = b['domain']['primary'].split('/')[0]
    row['year'] = int(b['released'][:4]) if b['released'] else None
    return row


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


def build(root: str = ROOT) -> Build:
    from tools.validate import tiers
    out = Build()
    published: dict[str, dict[str, dict]] = {k: {} for k in CORPUS_KINDS}
    sources: dict[str, list] = {}

    def broken(r) -> str:
        return '; '.join(f.message for f in r.schema_findings if f.blocks)

    for r in tiers.load(root):
        kind = r.kind.name if r.kind else None
        if kind not in CORPUS_KINDS:
            continue
        if kind == 'source':
            sources.setdefault(r.id, []).append(r)
            continue
        if kind == 'benchmark' and r.parsed and status(r.raw) == DRAFT:
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
    entities = {k: [v[i] for i in sorted(v)] for k, v in published.items()}
    out.corpus = nfc({'artifact': 'corpus', 'format': FORMAT, 'entities': entities, 'subsets': subsets})
    out.facets = nfc({'artifact': 'facets', 'format': FORMAT,
                      'benchmarks': [facet_row(b) for b in entities['benchmark']]})
    return out


def serialise(artifact: dict) -> bytes:
    return (json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def write(result: Build, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, artifact in zip(ARTIFACTS, (result.corpus, result.facets)):
        path = os.path.join(out_dir, name)
        with open(path, 'wb') as fh:
            fh.write(serialise(artifact))
        written.append(path)
    return written
