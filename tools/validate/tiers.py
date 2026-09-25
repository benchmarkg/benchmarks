"""The four validation tiers (P0-S5-T02; 04-data-model.md S12, 05 S3 and S9 jobs 2-4 and 12).

    bench validate [paths...] [--tier schema|ref|semantic|quality|all] [--changed-only] [--single] [--json]

| Tier | Here | Blocking |
| --- | --- | --- |
| 1 schema   | YAML parses; the file's Pydantic model accepts it (types, enums, required fields, id format); the file sits where 05 S2 says its id and kind put it | yes |
| 2 ref      | every reference resolves; no id in two files; no retired id reused; domain and capability values are assignable taxonomy terms | yes |
| 3 semantic | schema/validators.py's cross-field rules (P0-S4-T08), unchanged | yes (a rule's warnings do not block) |
| 4 quality  | signals that a record is thin, stale or unloved | **never**: report-only (04 S12) |

The exit code is 1 when a reported tier-1, -2 or -3 finding is blocking, and 0 otherwise. Tier 4
cannot change it: its findings carry severity `quality`, which `Report.exit_code` does not count, so
a dashboard signal can never turn into a red X (04 S12, "Tier 4 is deliberately non-blocking").

Scope. By default every entity file under data/ (and vendor/**/claims/) is checked. Tiers 2 and 3
always read the whole corpus, because a reference or a cross-record rule cannot be judged from one
file; `paths` and `--changed-only` narrow what is REPORTED, not what is read:

  - `paths`: findings on the named files or directories, plus tier-2 findings whose target is one
    of them (a deleted source leaves dangling references in files nobody touched);
  - `--changed-only`: the same, for the files `git diff` shows changed against the merge base with
    origin/$GITHUB_BASE_REF (origin/main outside a PR run), plus untracked files.

`--single` is the other way round: it reads ONE file and nothing else -- no corpus walk -- which is
what the issue-intake bot calls (05 S3). Tier 1 runs in full; tier 2 checks only the taxonomy
references, which need no corpus; tier 3 runs over a corpus of that one record, so rules that need a
second record say nothing; tier 4 runs on the record. What it could not check is listed in
`not_checked`, never silently passed.

A file that fails tier 1 is still read for tier 2 -- its references are in its YAML whether or not
its model accepts it -- but it is left out of the tier-3 corpus, which holds validated models only.

Files under data/surveys/, data/tombstones/, data/_discovery/ and data/_analysis/ have no entity
model yet and are listed as `unmodelled`; tombstones are read by tier 2 for their redirects. Any
other file under data/ that no kind claims is a tier-1 failure: it is in a place 05 S2 has no
entity for.
"""
from __future__ import annotations

import datetime as _dt
import glob
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from schema import validators as semantic
from schema.baseline import BaselineFile
from schema.benchmark import Benchmark
from schema.claim import ResultClaim
from schema.conditions import EvalConditions
from schema.dispute import Dispute
from schema.entities import AliasFile, IngestBatch, Leaderboard, Organization, RatingPool
from schema.metric import Metric
from schema.source import Source
from schema.system import System
from schema.taxonomy import RetiredIdFile, load_taxonomy, read_yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIERS = {1: 'schema', 2: 'ref', 3: 'semantic', 4: 'quality'}
TIER_BY_NAME = {v: k for k, v in TIERS.items()}

# Tier-4 thresholds that no plan document fixes. 04 S12 says "last_verified older than 12 months"
# (so that one is fixed) and "liveness last_checked stale" without a number; freshness.yml runs the
# liveness check weekly (05 S9), so two missed runs is the staleness line.
LAST_VERIFIED_MONTHS = 12
LIVENESS_STALE_DAYS = 14
TAGLINE_MAX = 120


@dataclass(frozen=True)
class Kind:
    name: str
    model: type[BaseModel]
    many: bool = False                  # the file holds a list of records, not one entity with an id


KINDS: dict[str, Kind] = {                # anchored directory -> kind (05 S2)
    'data/benchmarks/': Kind('benchmark', Benchmark),
    'data/systems/': Kind('system', System),
    'data/organizations/': Kind('organization', Organization),
    'data/metrics/': Kind('metric', Metric),
    'data/leaderboards/': Kind('leaderboard', Leaderboard),
    'data/rating-pools/': Kind('rating-pool', RatingPool),
    'data/conditions/': Kind('conditions', EvalConditions),
    'data/baselines/': Kind('baselines', BaselineFile, many=True),
    'data/sources/': Kind('source', Source),
    'data/claims/': Kind('claim', ResultClaim),
    'data/disputes/': Kind('dispute', Dispute),
    'data/_ingest/batches/': Kind('batch', IngestBatch),
    'data/aliases/': Kind('aliases', AliasFile, many=True),
}
VENDOR_CLAIM = Kind('claim', ResultClaim)
UNMODELLED = ('data/surveys/', 'data/tombstones/', 'data/_discovery/', 'data/_analysis/')

# Prefixed ids are references wherever they appear as a whole string value (the record's own
# top-level `id` excepted): the id grammar makes them unambiguous (05 S2, "File naming").
PREFIXED = (
    (re.compile(r'^src-[a-z0-9]+(-[a-z0-9]+)*$'), 'source'),
    (re.compile(r'^cond-[0-9a-f]{12}$'), 'conditions'),
    (re.compile(r'^claim-[0-9a-f]{12}$'), 'claim'),
    (re.compile(r'^lb-[a-z0-9-]+$'), 'leaderboard'),
    (re.compile(r'^org-[a-z0-9]+(-[a-z0-9]+)*$'), 'organization'),
    (re.compile(r'^pool-[a-z0-9]+(-[a-z0-9]+)*$'), 'rating-pool'),
    (re.compile(r'^ingest-[a-z0-9]+(-[a-z0-9]+)*$'), 'batch'),
    (re.compile(r'^dispute-[a-z0-9]+(-[a-z0-9]+)*$'), 'dispute'),
)
ALIAS_FILES = {'systems': 'system', 'benchmarks': 'benchmark', 'organizations': 'organization'}


# ---- findings and the report --------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    tier: int
    rule: str
    severity: str                       # blocking | warning | quality
    entity: str
    path: str | None
    message: str
    auto_fix: str | None = None
    related: tuple[str, ...] = ()       # ids the finding is also about (a reference's target)

    @property
    def blocks(self) -> bool:
        return self.tier in (1, 2, 3) and self.severity == 'blocking'

    def as_dict(self) -> dict:
        return {'tier': self.tier, 'tier_name': TIERS[self.tier], 'rule': self.rule, 'severity': self.severity,
                'entity': self.entity, 'path': self.path, 'message': self.message, 'auto_fix': self.auto_fix,
                'related': list(self.related)}

    def __str__(self):
        fix = ' [auto-fix offered: %s]' % self.auto_fix if self.auto_fix else ''
        where = ' (%s)' % self.path if self.path else ''
        return '%-8s %d/%-8s %s %s%s: %s%s' % (self.severity.upper(), self.tier, TIERS[self.tier], self.rule,
                                               self.entity, where, self.message, fix)


@dataclass
class Report:
    tiers: tuple[int, ...]
    scope: str                          # all | paths | changed-only | single
    files: int
    findings: list[Finding] = field(default_factory=list)
    unmodelled: list[str] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.blocks]

    @property
    def exit_code(self) -> int:
        return 1 if self.blocking else 0

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    def as_dict(self) -> dict:
        return {'tiers': [TIERS[t] for t in self.tiers], 'scope': self.scope, 'files': self.files,
                'exit_code': self.exit_code, 'blocking': len(self.blocking), 'warnings': self.count('warning'),
                'quality': self.count('quality'), 'findings': [f.as_dict() for f in self.findings],
                'unmodelled': self.unmodelled, 'not_checked': self.not_checked}

    def summary(self) -> str:
        return ('validate: %s over %d file(s): %d blocking, %d warning(s), %d quality signal(s)%s'
                % (','.join(TIERS[t] for t in self.tiers), self.files, len(self.blocking), self.count('warning'),
                   self.count('quality'), ' (tier 4 is report-only)' if 4 in self.tiers else ''))


# ---- reading files ------------------------------------------------------------------------------

@dataclass
class Record:
    path: str                           # as reported: root-relative, forward slashes
    anchored: str                       # from data/ or vendor/ on, which decides the kind
    kind: Kind | None
    raw: Any = None
    model: BaseModel | None = None
    parsed: bool = False
    schema_findings: list[Finding] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return os.path.basename(self.path).rsplit('.', 1)[0]

    @property
    def id(self) -> str:
        if isinstance(self.raw, dict) and isinstance(self.raw.get('id'), str):
            return self.raw['id']
        return self.stem

    @property
    def unmodelled(self) -> bool:
        return self.kind is None and self.anchored.startswith(UNMODELLED)


def _posix(p: str) -> str:
    return p.replace(os.sep, '/')


def relative(path: str, root: str) -> str:
    """`path` relative to `root` with forward slashes, or absolute when it lies outside `root`
    (on Windows, possibly on another drive, where relpath raises)."""
    full = os.path.abspath(path)
    try:
        rel = os.path.relpath(full, root)
    except ValueError:
        return _posix(full)
    return _posix(full) if rel.startswith('..') else _posix(rel)


def anchor(rel: str) -> str:
    """The path from its data/ or vendor/ segment on, so a fixture tree outside the repository is
    classified the way the same file inside it would be."""
    rel = _posix(rel)
    for seg in ('data/', 'vendor/'):
        if rel.startswith(seg):
            return rel
        i = rel.rfind('/' + seg)
        if i >= 0:
            return rel[i + 1:]
    return rel


def kind_of(anchored: str) -> Kind | None:
    if anchored.startswith('vendor/') and '/claims/' in anchored:
        return VENDOR_CLAIM
    for prefix, k in KINDS.items():
        if anchored.startswith(prefix):
            return k
    return None


def _read(full: str, rel: str) -> Record:
    """One file through tier 1: `full` is read, and reported and classified as `rel`."""
    rel = _posix(rel)
    anchored = anchor(rel)
    rec = Record(rel, anchored, kind_of(anchored))
    try:
        rec.raw = read_yaml(full)
        rec.parsed = True
    except Exception as e:                                  # ruamel raises several unrelated types
        rec.schema_findings.append(Finding(1, 'yaml', 'blocking', rec.stem, rel, 'does not parse: %s'
                                           % ' '.join(str(e).split())[:300]))
        return rec
    if rec.kind is None:
        if not rec.unmodelled:
            rec.schema_findings.append(Finding(1, 'unknown-path', 'blocking', rec.stem, rel,
                                               'no entity kind is stored at this path (05 S2)'))
        return rec
    try:
        rec.model = rec.kind.model.model_validate(rec.raw)
    except ValidationError as e:
        for err in e.errors():
            loc = '.'.join(str(x) for x in err['loc']) or '<record>'
            msg = err['msg'].removeprefix('Value error, ')
            rec.schema_findings.append(Finding(1, 'schema', 'blocking', rec.id, rel, '%s: %s' % (loc, msg)))
    rec.schema_findings += _placement(rec)
    return rec


def _placement(rec: Record) -> list[Finding]:
    """05 S2's file naming: `<id>.yaml`, in the directory its kind and content put it."""
    out = []

    def bad(msg):
        out.append(Finding(1, 'file-name', 'blocking', rec.id, rec.path, msg))

    parts = rec.anchored.split('/')
    raw = rec.raw if isinstance(rec.raw, dict) else None
    if not rec.kind.many and raw is not None and isinstance(raw.get('id'), str) and raw['id'] != rec.stem:
        bad('the file is named %s.yaml but holds id %s; an entity file is <id>.yaml' % (rec.stem, raw['id']))
    if rec.kind.name == 'benchmark' and raw is not None:
        primary = raw['domain']['primary'] if isinstance(raw.get('domain'), dict) and \
            isinstance(raw['domain'].get('primary'), str) else None
        family = primary.split('/')[0] if primary else None
        if family and (len(parts) != 4 or parts[2] != family):
            bad('a benchmark lives at data/benchmarks/%s/%s.yaml, the family of its domain.primary' % (family, rec.stem))
    if rec.kind.name == 'claim' and rec.anchored.startswith('data/') and raw is not None \
            and isinstance(raw.get('benchmark'), str):
        bench = raw['benchmark'].split('@')[0]
        ingested = len(parts) == 6 and parts[2] == '_ingested'
        if not ((len(parts) == 4 and parts[2] == bench) or (ingested and parts[4] == bench)):
            bad('a claim lives at data/claims/%s/ (or data/claims/_ingested/<source>/%s/)' % (bench, bench))
    if rec.kind.name == 'source' and (len(parts) != 4 or not re.fullmatch(r'\d{4}', parts[2])):
        bad('a source lives at data/sources/<yyyy>/<id>.yaml')
    if rec.kind.name == 'baselines' and isinstance(rec.raw, list):
        for b in rec.raw:
            bv = b.get('benchmark_version') if isinstance(b, dict) else None
            if isinstance(bv, str) and bv.split('@')[0] != rec.stem:
                bad('data/baselines/%s.yaml holds a baseline on %s' % (rec.stem, bv))
    if rec.kind.name == 'aliases':
        if rec.stem not in ALIAS_FILES:
            bad('alias files are data/aliases/{%s}.yaml' % ','.join(sorted(ALIAS_FILES)))
        elif isinstance(rec.raw, list):
            for a in rec.raw:
                target = a.get('resolves_to') if isinstance(a, dict) else None
                if isinstance(target, str) and target.split(':')[0] != ALIAS_FILES[rec.stem]:
                    bad('%s.yaml resolves %r to a %s' % (rec.stem, a.get('alias'), target.split(':')[0]))
    return out


def discover(root: str) -> list[str]:
    """Every entity file the corpus holds, root-relative. drafts/ is never read (05 S9 check 9i)."""
    found = glob.glob(os.path.join(root, 'data', '**', '*.yaml'), recursive=True)
    found += glob.glob(os.path.join(root, 'vendor', '**', 'claims', '**', '*.yaml'), recursive=True)
    return sorted({_posix(os.path.relpath(p, root)) for p in found})


def load(root: str) -> list[Record]:
    """The corpus: every discovered file, through tier 1."""
    return [_read(os.path.join(root, rel), rel) for rel in discover(root)]


# ---- tier 2: references -------------------------------------------------------------------------

def _strs(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, list):
        return [v for v in x if isinstance(v, str)]
    return []


def _items(x) -> list[dict]:
    return [v for v in x if isinstance(v, dict)] if isinstance(x, list) else []


def _field(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


@dataclass
class Index:
    ids: dict[str, dict[str, list[str]]] = field(default_factory=dict)   # kind -> id -> [paths]
    versions: dict[str, set[str]] = field(default_factory=dict)          # benchmark or system -> declared versions
    subsets: dict[str, set[str]] = field(default_factory=dict)           # benchmark -> subset slugs
    declared: set[str] = field(default_factory=set)                      # variant and fork ids declared inline
    tombstones: dict[str, str | None] = field(default_factory=dict)      # id -> redirects_to

    def add(self, kind, ident, path):
        self.ids.setdefault(kind, {}).setdefault(ident, []).append(path)

    def has(self, kind, ident) -> bool:
        return ident in self.ids.get(kind, {})  # get-default: a kind with no files has no ids


def index(records: list[Record]) -> Index:
    ix = Index()
    for r in records:
        if not r.parsed:
            continue
        if r.anchored.startswith('data/tombstones/') and isinstance(r.raw, dict):
            ix.tombstones[r.id] = r.raw.get('redirects_to')
            continue
        if r.kind is None:
            continue
        if r.kind.name == 'baselines':
            for b in _items(r.raw):
                if isinstance(b.get('id'), str):
                    ix.add('baseline', b['id'], r.path)
            continue
        if r.kind.many:
            continue
        ix.add(r.kind.name, r.id, r.path)
        raw = r.raw if isinstance(r.raw, dict) else {}
        if r.kind.name == 'benchmark':
            ix.versions[r.id] = {v['version'] for v in _items(raw.get('versions')) if isinstance(v.get('version'), str)}
            ix.subsets[r.id] = {s['id'].split('#', 1)[-1] for s in _items(raw.get('subsets')) if isinstance(s.get('id'), str)}
            lineage = raw.get('lineage')
            ix.declared |= {x['id'] for k in ('variants', 'forks') for x in _items(_field(lineage, k))
                            if isinstance(x.get('id'), str)}
            for b in _items(raw.get('baselines')):
                if isinstance(b.get('id'), str):
                    ix.add('baseline', b['id'], r.path)
        if r.kind.name == 'system':
            ix.versions['system:' + r.id] = {v['version'] for v in _items(raw.get('versions'))
                                             if isinstance(v.get('version'), str)}
    return ix


def _walk_prefixed(x, where, top=True):
    """(dotted path, value) for every whole-string value that is a prefixed id."""
    if isinstance(x, dict):
        for k, v in x.items():
            if top and k == 'id':
                continue
            yield from _walk_prefixed(v, '%s.%s' % (where, k) if where else str(k), False)
    elif isinstance(x, list):
        for v in x:
            yield from _walk_prefixed(v, where + '[]', False)
    elif isinstance(x, str):
        for pattern, kind in PREFIXED:
            if pattern.match(x):
                yield where, x, kind
                break


def _typed_refs(r: Record):
    """(field, kind, value) for the unprefixed references each kind carries."""
    raw = r.raw
    k = r.kind.name if r.kind else None
    if k == 'benchmark' and isinstance(raw, dict):
        for m in _strs(raw.get('metrics')) + _strs(raw.get('headline_metric')):
            yield 'metrics', 'metric', m
        lineage = raw.get('lineage')
        for key in ('supersedes', 'superseded_by', 'extended_by', 'subset_of', 'decontaminates'):
            for v in _strs(_field(lineage, key)):
                yield 'lineage.' + key, 'benchmark', v
        for c in _items(_field(lineage, 'correlates_with')):
            for v in _strs(c.get('benchmark')):
                yield 'lineage.correlates_with[].benchmark', 'benchmark', v
        for view in _items(_field(lineage, 'views')):
            for v in _strs(view.get('of')):
                yield 'lineage.views[].of', 'benchmark', v
        for b in _items(raw.get('baselines')):
            for v in _strs(b.get('metric')):
                yield 'baselines[].metric', 'metric', v
    elif k == 'claim' and isinstance(raw, dict):
        for key in ('system', 'opponent'):
            for v in _strs(raw.get(key)):
                yield key, 'system', v
        for v in _strs(raw.get('benchmark')):
            yield 'benchmark', 'benchmark', v
        for v in _strs(raw.get('metric')):
            yield 'metric', 'metric', v
        for v in _strs(raw.get('subset')):
            bench = raw['benchmark'].split('@')[0] if isinstance(raw.get('benchmark'), str) else ''
            yield 'subset', 'subset:' + bench, v
    elif k == 'baselines':
        for b in _items(raw):
            for v in _strs(b.get('benchmark_version')):
                yield 'benchmark_version', 'benchmark', v
            for v in _strs(b.get('metric')):
                yield 'metric', 'metric', v
    elif k == 'metric' and isinstance(raw, dict):
        for v in _strs(raw.get('must_report_with')):
            yield 'must_report_with', 'metric', v
    elif k == 'system' and isinstance(raw, dict):
        for v in _strs(raw.get('built_on')):
            yield 'built_on', 'system', v
    elif k == 'rating-pool' and isinstance(raw, dict):
        for v in _strs(raw.get('benchmark')):
            yield 'benchmark', 'benchmark', v
        for v in _strs(raw.get('members')) + _strs(raw.get('anchor')):
            yield 'members', 'system', v
    elif k == 'leaderboard' and isinstance(raw, dict):
        for v in _strs(raw.get('benchmarks')):
            yield 'benchmarks', 'benchmark', v
    elif k == 'aliases':
        for a in _items(raw):
            target = a.get('resolves_to')
            if isinstance(target, str) and ':' in target:
                kind, _, ident = target.partition(':')
                yield 'resolves_to', kind, ident


def _resolve(ix: Index, kind: str, value: str) -> str | None:
    """None when `value` resolves, else why not."""
    if kind.startswith('subset:'):
        bench = kind.split(':', 1)[1]
        declared = ix.subsets.get(bench) or set()
        slug = value.split('#', 1)[-1]
        return None if not declared or slug in declared else 'subset %s is not declared by %s' % (value, bench)
    ident, _, version = value.partition('@')
    if ident in ix.tombstones:
        return None if ix.tombstones[ident] else '%s is tombstoned with no redirects_to' % ident
    if kind == 'benchmark' and not version and ident in ix.declared:
        return None                     # a variant or fork declared inline in its root's lineage
    if not ix.has(kind, ident):
        return 'no %s record %s' % (kind, ident)
    if version:
        declared = ix.versions.get(ident if kind == 'benchmark' else '%s:%s' % (kind, ident)) or set()
        subsets = ix.subsets.get(ident) or set() if kind == 'benchmark' else set()
        if declared and version not in declared and version not in subsets:
            return '%s declares no version %s' % (ident, version)
    return None


def ref_tier(records: list[Record], ix: Index, taxonomy: dict) -> list[Finding]:
    out: list[Finding] = []
    for kind, ids in sorted(ix.ids.items()):
        for ident, paths in sorted(ids.items()):
            if len(paths) > 1:
                out.append(Finding(2, 'duplicate-id', 'blocking', ident, paths[0],
                                   'the %s id is held by %d files: %s' % (kind, len(paths), ', '.join(paths))))
    for r in records:
        if not r.parsed or r.kind is None:
            continue
        seen = set()
        refs = [(w, kind, v) for w, v, kind in _walk_prefixed(r.raw, '')] + list(_typed_refs(r))
        for where, kind, value in refs:
            why = _resolve(ix, kind, value)
            if why and (where, value) not in seen:
                seen.add((where, value))
                out.append(Finding(2, 'dangling-ref', 'blocking', r.id, r.path, '%s: %s' % (where, why),
                                   related=(value.partition('@')[0],)))
        out += _taxonomy_refs(r, taxonomy)
    return out


def _taxonomy(root: str) -> dict:
    tdir = os.path.join(root, 'taxonomy') if os.path.isdir(os.path.join(root, 'taxonomy')) else os.path.join(ROOT, 'taxonomy')
    models, _ = load_taxonomy(tdir)
    domains = models['domains.yaml'].terms
    retired_path = os.path.join(tdir, 'retired-ids.yaml')
    return {
        'dir': tdir,
        'leaves': {t.id for t in domains if t.parent and t.status != 'retired'},
        'families': {t.id for t in domains if not t.parent},
        'capabilities': {t.id for t in models['capabilities.yaml'].terms if t.status != 'retired'},
        'retired': {x.id for x in RetiredIdFile.model_validate(read_yaml(retired_path)).retired}
        if os.path.exists(retired_path) else set(),
        'live_terms': {t.id for m in models.values() for t in (getattr(m, 'terms', None) or []) if t.status != 'retired'},
    }


def _taxonomy_refs(r: Record, taxonomy: dict) -> list[Finding]:
    """04 S12 tier 2: domain values resolve to a term that HAS a parent (families are navigational,
    not assignable), and capability values to bare ids in capabilities.yaml."""
    if r.kind is None or r.kind.name != 'benchmark' or not isinstance(r.raw, dict):
        return []
    out = []
    domain = r.raw.get('domain')
    for where, v in [('domain.primary', x) for x in _strs(_field(domain, 'primary'))] + \
            [('domain.secondary[]', x) for x in _strs(_field(domain, 'secondary'))]:
        if v in taxonomy['families']:
            out.append(Finding(2, 'taxonomy-ref', 'blocking', r.id, r.path,
                               '%s: %s is a domain family, which is navigational and not assignable' % (where, v)))
        elif v not in taxonomy['leaves']:
            out.append(Finding(2, 'taxonomy-ref', 'blocking', r.id, r.path, '%s: %s is not a domains.yaml term' % (where, v)))
    for v in _strs(r.raw.get('capability')):
        if v not in taxonomy['capabilities']:
            out.append(Finding(2, 'taxonomy-ref', 'blocking', r.id, r.path,
                               'capability[]: %s is not a bare id in capabilities.yaml' % v))
    return out


# ---- tier 3: the semantic rules -----------------------------------------------------------------

def corpus_of(records: list[Record], taxonomy: dict) -> semantic.Corpus:
    """schema/validators.py's Corpus from the records tier 1 accepted (sources: every parsed one,
    raw, as validators.load_corpus reads them)."""
    c = semantic.Corpus(retired=taxonomy['retired'], live_terms=taxonomy['live_terms'])
    slots = {'benchmark': c.benchmarks, 'conditions': c.conditions, 'claim': c.claims, 'system': c.systems,
             'metric': c.metrics, 'batch': c.batches}
    for r in records:
        if r.kind is None or not r.parsed:
            continue
        if r.kind.name == 'source' and isinstance(r.raw, dict):
            c.sources[r.id], c.paths[r.id] = r.raw, r.path
        elif r.model is not None and r.kind.name == 'baselines':
            c.baselines += list(r.model.root)
        elif r.model is not None and r.kind.name in slots:
            slots[r.kind.name][r.id], c.paths[r.id] = r.model, r.path
    return c


def semantic_tier(corpus: semantic.Corpus, tier: int = 3, only=None) -> list[Finding]:
    out = []
    for rule_id in only or [r for r in semantic.RULES if r != 'retired-id-ledger']:
        for f in semantic.RULES[rule_id].check(corpus, 'stub'):
            out.append(Finding(tier, f.rule, f.severity, f.entity, corpus.paths.get(f.entity), f.message, f.auto_fix,
                               related=tuple(x for x in re.split(r'[/@]', f.entity) if x)))
    return out


# ---- tier 4: quality ----------------------------------------------------------------------------

def _months_ago(today: _dt.date, months: int) -> _dt.date:
    y, m = divmod(today.year * 12 + today.month - 1 - months, 12)
    m += 1
    for d in range(today.day, 0, -1):
        try:
            return _dt.date(y, m, d)
        except ValueError:
            continue
    raise AssertionError('unreachable')


def quality_tier(corpus: semantic.Corpus, taxonomy: dict, today: _dt.date, whole: bool = True) -> list[Finding]:
    """`whole` False (--single): the signals that need a second record are not evaluated."""
    from tools.build import comparability
    out: list[Finding] = []

    def q(rule, entity, msg):
        out.append(Finding(4, rule, 'quality', entity, corpus.paths.get(entity), msg))

    stale_before = _months_ago(today, LAST_VERIFIED_MONTHS)
    baselined = {x.benchmark_version.split('@')[0] for x in corpus.baselines}
    for bid, b in sorted(corpus.benchmarks.items()):
        if len(b.tagline) > TAGLINE_MAX:
            q('tagline-length', bid, 'tagline is %d characters; the card shows %d' % (len(b.tagline), TAGLINE_MAX))
        if b.curation.last_verified < stale_before:
            q('last-verified-stale', bid, 'last_verified %s is older than %d months' % (b.curation.last_verified,
                                                                                         LAST_VERIFIED_MONTHS))
        checked = b.liveness.last_checked if b.liveness else None
        if checked is None:
            q('liveness-stale', bid, 'liveness has never been checked')
        elif (today - checked).days > LIVENESS_STALE_DAYS:
            q('liveness-stale', bid, 'liveness last_checked %s is %d days old' % (checked, (today - checked).days))
        if b.comparability.material_waived:
            q('material-waived', bid, 'material fields waived: %s'
              % ', '.join('%s (%s)' % (w.field, w.reason) for w in b.comparability.material_waived))
        if whole and not b.baselines and bid not in baselined:
            q('no-baseline', bid, 'no baseline record, and so no value_absent_reason either')
    for sid, s in sorted(corpus.sources.items()):
        status = s.get('archive_status')
        if status in ('pending', 'failed'):
            q('unarchived-source', sid, 'archive_status %s%s' % (status, ': ' + ' '.join(str(s['failure_reason']).split())
                                                                  if s.get('failure_reason') else ''))
    if corpus.claims:
        floor = read_yaml(os.path.join(taxonomy['dir'], 'thresholds.yaml'))['thresholds']['frontier_floor']
        profiles = comparability.load_profiles(os.path.join(taxonomy['dir'], 'comparability-profiles.yaml'))
        resolutions = {}
        for cid, c in sorted(corpus.claims.items()):
            bench = c.benchmark.split('@')[0]
            if bench not in corpus.benchmarks:
                continue
            if bench not in resolutions:
                resolutions[bench] = comparability.resolve_profile(corpus.benchmarks[bench], profiles)
            cond = corpus.conditions.get(c.eval_conditions) if c.eval_conditions else None
            done = comparability.compute_for_claim(c, resolutions[bench], cond).condition_completeness
            if done is not None and done < floor:
                q('condition-completeness', cid, 'condition_completeness %.2f is below frontier_floor (%s)' % (done, floor))
    return out


# ---- running ------------------------------------------------------------------------------------

def changed_files(root: str) -> set[str]:
    """Root-relative paths changed against the merge base, plus untracked files. Deleted and
    renamed-away paths are included: their ids can leave dangling references behind."""
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8',
                              check=True).stdout
    branch = os.environ.get('GITHUB_BASE_REF') or 'main'
    base = 'HEAD'
    for ref in ('origin/' + branch, branch):
        try:
            base = git('merge-base', ref, 'HEAD').strip()
            break
        except subprocess.CalledProcessError:
            continue
    out = set(git('diff', '--name-only', '--no-renames', '--relative', base).splitlines())
    out |= set(git('ls-files', '--others', '--exclude-standard').splitlines())
    return {_posix(p) for p in out if p}


def _in_scope(f: Finding, paths: set[str], ids: set[str]) -> bool:
    if f.path is not None and any(f.path == p or f.path.startswith(p + '/') for p in paths):
        return True
    return f.entity in ids or any(r in ids for r in f.related)


def _select(tiers) -> tuple[int, ...]:
    if tiers in (None, 'all'):
        return (1, 2, 3, 4)
    names = [tiers] if isinstance(tiers, (str, int)) else list(tiers)
    return tuple(sorted({TIER_BY_NAME[t] if isinstance(t, str) else t for t in names}))


def run(root: str = ROOT, tiers='all', paths: list[str] | None = None, changed_only: bool = False,
        today: _dt.date | None = None) -> Report:
    """The corpus through the selected tiers. See the module docstring for scope."""
    selected = _select(tiers)
    today = today or _dt.date.today()
    records = load(root)
    taxonomy = _taxonomy(root)
    findings: list[Finding] = []
    if 1 in selected:
        findings += [f for r in records for f in r.schema_findings]
    corpus = corpus_of(records, taxonomy)
    if 2 in selected:
        findings += ref_tier(records, index(records), taxonomy)
        findings += semantic_tier(corpus, tier=2, only=['retired-id-ledger'])
    if 3 in selected:
        findings += semantic_tier(corpus)
    if 4 in selected:
        findings += quality_tier(corpus, taxonomy, today)
    scope, n = 'all', len(records)
    if paths is not None or changed_only:
        wanted = set(changed_files(root)) if changed_only else set()
        wanted |= {relative(p, root).rstrip('/') for p in paths or []}
        if not wanted & {'', '.'}:                              # naming the root itself scopes nothing out
            ids = {os.path.basename(p).rsplit('.', 1)[0] for p in wanted if p.endswith('.yaml')}
            findings = [f for f in findings if _in_scope(f, wanted, ids)]
            n = sum(1 for r in records if any(r.path == p or r.path.startswith(p + '/') for p in wanted))
        scope = 'changed-only' if changed_only else 'paths'
    return Report(selected, scope, n, findings, sorted(r.path for r in records if r.unmodelled))


def single(path: str, tiers='all', root: str = ROOT, today: _dt.date | None = None) -> Report:
    """One file and nothing else: no corpus walk (05 S3, the issue-intake bot's call)."""
    selected = _select(tiers)
    today = today or _dt.date.today()
    rec = _read(os.path.abspath(path), relative(path, root))
    taxonomy = _taxonomy(root)
    findings: list[Finding] = []
    if 1 in selected:
        findings += rec.schema_findings
    corpus = corpus_of([rec], taxonomy)
    if 2 in selected:
        findings += _taxonomy_refs(rec, taxonomy)
    if 3 in selected:
        findings += semantic_tier(corpus)
    if 4 in selected:
        findings += quality_tier(corpus, taxonomy, today, whole=False)
    not_checked = []
    if 2 in selected:
        not_checked.append('tier 2 cross-record references and duplicate ids: they need the corpus (run without --single)')
    if 3 in selected:
        not_checked.append('tier 3 rules that read a second record (a claim\'s benchmark, conditions or system; '
                           'baselines across files; ingestion batches)')
    if 4 in selected:
        not_checked.append('tier 4 no-baseline, which reads data/baselines/, and condition-completeness, which reads '
                           'the claim\'s benchmark and conditions')
    return Report(selected, 'single', 1, findings, [rec.path] if rec.unmodelled else [], not_checked)

