"""Identity resolution, steps 1-4 (P3-S3-T02; 04 S10, 07 S5.2).

An upstream string such as `accounts/fireworks/models/qwen3-235b-a22b-thinking-2507` or `gpt-6-astra_max`
mixes model identity, serving provider, reasoning effort and a version into one token. 04 S10's rule is
that an adapter never creates an entity: it resolves the string to an existing id, or it records an
Unresolved. This module is the resolving half, steps 1-4 of 04 S10's procedure:

    1. external_ids exact match              confidence high
    2. alias table exact match               confidence from the alias record, its extracts applied
    3. normalised-string match against name, aliases[] and "<name> <version>"
       (lowercase, punctuation to spaces, whitespace collapsed)        confidence high
    4. structured parse, in this fixed order, then steps 1-3 again on the residue:
         provider prefix   accounts/<org>/models/, chutes/, zai-org/, together/   -> serving_provider
         provider suffix   " (Fireworks)", " (Novita)", " (Together)"            -> serving_provider
         effort suffix     _(max|xhigh|high|medium|low|minimal|none|unknown)$    -> reasoning_effort
         date suffix       -YYYY-MM-DD$                                          -> the SystemVersion

Every stripped part is routed into `extracts` (04 S10: "a resolution that strips information and throws it
away is a bug"), and `_unknown` routes to an explicit null, never to a default. A version is found where
the matched string names one of the entity's SystemVersions (its api_identifier, or "<name> <version>").

Steps 5 and 6 -- fuzzy proposals that are never auto-accepted, and the unresolved record with its curation
task -- are not here. What is here declines to guess: a residue that still ends in an underscore token
step 4 does not know (07 S5.2's `claude-opus-4-6_120K`: a context window or a thinking budget?) is an
Unresolved even when the part before it names a system, which is offered as a suggestion only.

A frozen snapshot (07 S1.3; P5-S1-T06). freeze() serialises the indexes a run resolves against, with the
commit they were built from and a sha256 of their content; thaw() rebuilds them and refuses a snapshot
whose content no longer matches its hash. A fixture set keeps one beside it, so its drafts stay
byte-identical while data/ moves on:

    python -m ingest.resolve --freeze benchmark leaderboard --out tests/ingest/fixtures/hf-hub/resolver-snapshot.json

P5-S2-T03's runner resolver (ingest/runner/resolver.py) extends this to every kind and the lineage index.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

from ingest.adapters.base import Unresolved

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIDENCE = {'high': 1.0, 'medium': 0.8, 'low': 0.5}

# 04 S10's lists, in its order. A prefix org is a group in the pattern or fixed.
PROVIDER_PREFIXES = (
    (re.compile(r'^accounts/([a-z0-9-]+)/models/'), None),          # accounts/<org>/models/ -> org-<org>
    (re.compile(r'^chutes/'), 'org-chutes'),
    (re.compile(r'^zai-org/'), 'org-z-ai'),                    # the organisation's id (data/organizations/_stubs/)
    (re.compile(r'^together/'), 'org-together'),
)
PROVIDER_SUFFIXES = {'Fireworks': 'org-fireworks', 'Novita': 'org-novita', 'Together': 'org-together'}
PROVIDER_SUFFIX = re.compile(r'\s*\((%s)\)$' % '|'.join(PROVIDER_SUFFIXES))
EFFORT_SUFFIX = re.compile(r'_(max|xhigh|high|medium|low|minimal|none|unknown)$')
DATE_SUFFIX = re.compile(r'-(\d{4}-\d{2}-\d{2})$')
TRAILING_TOKEN = re.compile(r'_([A-Za-z0-9]+)$')
EFFORT_FIELD = 'eval_conditions.reasoning_effort'


def normalise(s: str) -> str:
    """04 S10 step 3: lowercase, punctuation to spaces, whitespace collapsed."""
    return ' '.join(re.sub(r'[^0-9a-z]+', ' ', s.lower()).split())


@dataclass(frozen=True)
class Resolution:
    raw: str
    entity: str | None                    # 'system:gpt-6-astra', or None
    version: str | None = None            # a SystemVersion of that entity, where the string names one
    subset: str | None = None             # a benchmark subset ref (`gpqa#diamond`), where an alias names one
    confidence: str | None = None         # high | medium | low
    step: int | None = None               # 1, 2 or 3; 4 when the match came after the structured parse
    extracts: dict = field(default_factory=dict)      # routed parts: serving_provider, eval_conditions.*
    residue: str = ''                     # what steps 1-3 were last tried on
    unresolved: Unresolved | None = None

    @property
    def score(self) -> float:
        return CONFIDENCE[self.confidence] if self.confidence else 0.0


@dataclass
class Entry:
    """What one entity offers the matcher."""
    id: str
    name: str = ''
    aliases: tuple = ()
    external_ids: tuple = ()
    versions: tuple = ()                  # ((version, api_identifier or None), ...)


class Index:
    """A read-only view of one entity kind and its alias records (07 S1.3's resolver, steps 1-4 only)."""

    def __init__(self, kind: str, entries, aliases=()):
        self.kind = kind
        self.entries = {e.id: e for e in entries}
        self.alias_records = [a for a in aliases if a.entity[0] == kind]
        self._external, self._norm = {}, {}
        for e in self.entries.values():
            for x in e.external_ids:
                self._external.setdefault(x, set()).add((e.id, None))
            for v, api in e.versions:
                if api:
                    self._external.setdefault(api, set()).add((e.id, v))
            for label in (e.id, e.name, *e.aliases):
                if label:
                    self._norm.setdefault(normalise(label), set()).add((e.id, None))
            for v, _ in e.versions:
                self._norm.setdefault(normalise('%s %s' % (e.name or e.id, v)), set()).add((e.id, v))
                self._norm.setdefault(normalise('%s %s' % (e.id, v)), set()).add((e.id, v))

    @classmethod
    def load(cls, kind: str = 'system', root: str = ROOT) -> 'Index':
        """The curated records under data/<kind>s/ (stubs are not resolution targets: a curated claim may
        not point at one) and data/aliases/<kind>s.yaml."""
        from schema.entities import AliasFile
        from schema.taxonomy import read_yaml
        entries = []
        # benchmarks live under data/benchmarks/<domain>/, the other kinds flat; _stubs/ is never a target
        pattern = ('*', '*.yaml') if kind == 'benchmark' else ('*.yaml',)
        paths = [p for p in glob.glob(os.path.join(root, 'data', kind + 's', *pattern))
                 if os.sep + '_stubs' + os.sep not in p]
        for p in sorted(paths):
            d = read_yaml(p)
            entries.append(Entry(
                d['id'], d.get('name') or '', tuple(d.get('aliases') or ()),             # get-default: optional fields
                tuple(str(v) for v in (d.get('external_ids') or {}).values() if v),   # get-default: as above
                tuple((str(v['version']), v.get('api_identifier')) for v in d.get('versions') or ())))  # get-default: as above
        aliases = ()
        path = os.path.join(root, 'data', 'aliases', kind + 's.yaml')
        if os.path.exists(path):
            aliases = AliasFile.model_validate(read_yaml(path) or []).root
        return cls(kind, entries, aliases)

    # ---- steps 1-3 on one string --------------------------------------------------------------------

    def _one(self, hits):
        """The single (id, version) of a hit set, or None when there is none or more than one."""
        return next(iter(hits)) if len(hits) == 1 else None

    def match(self, s: str):
        """(id, version, confidence, step, alias extracts) by steps 1-3, or None."""
        hit = self._one(self._external.get(s, set()))           # get-default: no identifier, no hit
        if hit:
            # an alias record for the same string still routes its extracts (04 S10: stripping a part
            # and dropping it is a bug); the match itself stays step 1's
            extracts = {k: v for a in self.alias_records if a.alias == s and a.entity[1] == hit[0]
                        for k, v in a.extracts.items()}
            return hit[0], hit[1], 'high', 1, extracts
        for a in self.alias_records:
            if a.alias == s:
                ident = a.entity[1]
                return ident, a.version or self._version_in(ident, s), a.confidence, 2, dict(a.extracts)
        hit = self._one(self._norm.get(normalise(s), set()))    # get-default: no label, no hit
        if hit:
            return hit[0], hit[1], 'high', 3, {}
        return None

    def _version_in(self, ident: str, s: str) -> str | None:
        e = self.entries.get(ident)                              # get-default: an alias to a missing entity
        if e is None:
            return None
        for v, api in e.versions:
            if api == s or normalise('%s %s' % (e.name or e.id, v)) == normalise(s):
                return v
        return None

    # ---- the procedure --------------------------------------------------------------------------------

    def subset_of(self, s: str) -> str | None:
        """The subset an alias for exactly `s` names (07 S5.4: `GPQA diamond` is gpqa#diamond, not a new
        benchmark), or None."""
        return next((a.subset for a in self.alias_records if a.alias == s), None)

    def resolve(self, raw: str) -> Resolution:
        got = self.match(raw)
        if got:
            ident, version, conf, step, extracts = got
            return Resolution(raw, '%s:%s' % (self.kind, ident), version, self.subset_of(raw), conf, step,
                              extracts, raw)
        residue, routed, date = parse(raw)
        got = self.match(residue) if residue != raw else None
        if got:
            ident, version, conf, _, extracts = got
            # a stripped date tail is the version the string names, unless the match already named one
            return Resolution(raw, '%s:%s' % (self.kind, ident), version or date, self.subset_of(residue), conf, 4,
                              {**routed, **extracts}, residue)
        return Resolution(raw, None, extracts=routed, residue=residue, unresolved=self._unresolved(raw, residue))

    def _unresolved(self, raw: str, residue: str) -> Unresolved:
        m = TRAILING_TOKEN.search(residue)
        base = self.match(residue[:m.start()]) if m else None
        if m and base:
            token = m.group(1)
            return Unresolved(
                source_key=raw, field='%s' % self.kind, observed=raw, reason='unparseable',
                suggestions=[('%s:%s' % (self.kind, base[0]), CONFIDENCE[base[2]])],
                human_task=('%r names %s:%s plus a suffix %r that is not a reasoning effort: it may be a '
                            'context window or a thinking budget. Read the source row (its Name column) and '
                            'write an alias whose extracts say which (04 S10).'
                            % (raw, self.kind, base[0], '_' + token)))
        return Unresolved(
            source_key=raw, field=self.kind, observed=raw, reason='no-match',
            human_task='No %s matches %r (residue %r). Add an alias to data/aliases/%ss.yaml, or the entity '
                       'if it is new (04 S10).' % (self.kind, raw, residue, self.kind))

    def system(self, raw: str) -> tuple[str | None, float]:
        """07 S1.3's Resolver.system(): (entity id or None, score)."""
        r = self.resolve(raw)
        return (r.entity.split(':', 1)[1] if r.entity else None), r.score

    # ---- a frozen snapshot (07 S1.3) -------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Everything this index matches on, as plain JSON-ready data: from_snapshot() rebuilds it."""
        return {
            'entries': [{'id': e.id, 'name': e.name, 'aliases': list(e.aliases), 'external_ids': list(e.external_ids),
                         'versions': [list(v) for v in e.versions]} for e in sorted(self.entries.values(),
                                                                                     key=lambda e: e.id)],
            'aliases': [a.model_dump(mode='json', exclude_defaults=True) for a in self.alias_records],
        }

    @classmethod
    def from_snapshot(cls, kind: str, doc: dict) -> 'Index':
        from schema.entities import AliasFile
        entries = [Entry(e['id'], e['name'], tuple(e['aliases']), tuple(e['external_ids']),
                         tuple(tuple(v) for v in e['versions'])) for e in doc['entries']]
        return cls(kind, entries, AliasFile.model_validate(doc['aliases']).root)


def _canonical(doc) -> str:
    import json
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def freeze(kinds, root: str = ROOT, commit: str | None = None) -> dict:
    """07 S1.3's frozen resolver, for the kinds given: each Index's snapshot, the commit it was built
    from, and the sha256 of the indexes' canonical JSON, which is what a run records. A fixture set
    freezes one beside itself so its drafts stay byte-identical while data/ moves on."""
    import hashlib
    indexes = {k: Index.load(k, root).snapshot() for k in sorted(kinds)}
    return {'built_from_commit': commit, 'sha256': hashlib.sha256(_canonical(indexes).encode('utf-8')).hexdigest(),
            'indexes': indexes}


def thaw(doc: dict) -> dict:
    """{kind: Index} from a frozen snapshot; a snapshot whose content does not match its sha256 is refused."""
    import hashlib
    if hashlib.sha256(_canonical(doc['indexes']).encode('utf-8')).hexdigest() != doc['sha256']:
        raise ValueError('the resolver snapshot does not match its recorded sha256; refreeze it, do not edit it')
    return {k: Index.from_snapshot(k, v) for k, v in doc['indexes'].items()}


def main(argv=None) -> int:
    import argparse
    import json
    import subprocess
    p = argparse.ArgumentParser(description='Freeze a resolver snapshot (07 S1.3).')
    p.add_argument('--freeze', nargs='+', required=True, metavar='KIND', help='entity kinds, e.g. benchmark leaderboard')
    p.add_argument('--out', required=True, help='the snapshot file to write')
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    commit = subprocess.run(['git', '-C', a.root, 'rev-parse', 'HEAD'], capture_output=True, text=True,
                            check=False).stdout.strip()
    doc = freeze(a.freeze, a.root, commit or None)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write('\n')
    print('%s: %s, sha256 %s' % (a.out, ', '.join('%d %s' % (len(v['entries']), k) for k, v in doc['indexes'].items()),
                                doc['sha256']))
    return 0


def parse(raw: str) -> tuple[str, dict, str | None]:
    """04 S10 step 4's strips, in its fixed order: (residue, routed extracts, date tail or None)."""
    s, routed = raw, {}
    for pattern, org in PROVIDER_PREFIXES:
        m = pattern.match(s)
        if m:
            routed['serving_provider'] = org or 'org-%s' % m.group(1)
            s = s[m.end():]
            break
    m = PROVIDER_SUFFIX.search(s)
    if m:
        routed['serving_provider'] = PROVIDER_SUFFIXES[m.group(1)]
        s = s[:m.start()]
    m = EFFORT_SUFFIX.search(s)
    if m:
        effort = m.group(1)
        routed[EFFORT_FIELD] = None if effort == 'unknown' else effort       # never a default (04 S10)
        s = s[:m.start()]
    date = None
    m = DATE_SUFFIX.search(s)
    if m:
        date = m.group(1)
        s = s[:m.start()]
    return s, routed, date


if __name__ == '__main__':
    import sys
    sys.exit(main())
