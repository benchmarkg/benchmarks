#!/usr/bin/env python3
"""Entity overlap with BenchmarkList and Benchmark Radar, measured on a seeded sample (P0-S10-T01; 01 S4).

    python scripts/overlap_sample.py --n 50 [--seed 320] [--date YYYY-MM-DD] [--refresh]
    python scripts/overlap_sample.py --summary          # re-read the files and print; no lookups

01 S4 defines the quantity:

    entity_overlap(S) = | seed_set ∩ catalogued_by(S) | / | seed_set |

and schedules this script to "draw the 50 families, record each lookup as a URL and a boolean with a
date, write data/_analysis/overlap-<service>-<date>.yaml, and publish the proportion with its 95%
interval". It writes one file per service and prints each proportion with its Wilson 95% interval.

The frame. 01 S4 draws "uniformly at random from the seed list", but the 320-entry seed is an
allocation, not yet a list: 02 S3's table gives each domain family a count and names nothing. The
frame is therefore the named field-defining families the repo already holds, per domain family:

    13 families   the named entries of the domain recon, _plan/_workflow/recon/recon_domains.md S1-13
     5 families   code, language, mathematics, reasoning-general, multimodal: the recon never sized
                  them (02 S3, note ‡), so Epoch's benchmark list as mapped in recon_epoch-assets.md S6
                  plus the stress corpus's entries in those families (taxonomy/_corpus/stress-corpus.yaml)
     1 family     engineering-design: the scoping survey's families
                  (data/surveys/engineering-design/_family-scoping.yaml)

and the draw is stratified by 02 S3's seed allocation (each family's `seed_target` in
taxonomy/domains.yaml): the n draws are split across the 19 families in proportion to their targets,
by largest remainder, then drawn uniformly without replacement within each. A proportional
stratified sample is self-weighting, so the pooled proportion estimates overlap over the seed's
domain mix. Drawing uniformly from the pooled frame instead would weight each domain by how many
names one recon happened to write down. The seed makes the draw reproducible, and the frame's
SHA-256 is recorded so a changed frame is visible.

The lookups. One bounded search per name or alias, sequential and spaced:

    benchmarklist    its public find-benchmarks operation (benchmarklist.com/llms.txt lists it for
                     exactly this use). It matches full text, so a hit is proposed only when a returned
                     entry's name is the family's own
    benchmark-radar  its benchmark catalogue search: the site's own name-and-alias rule
                     (assets/app.js, searchBenchmarkIndex) over /data/benchmark-index.json, the file
                     the search page loads. "Carries an entry" means a benchmark page. Its daily
                     discovery feed is items, not entries, and is not counted

Nothing of either service's content is kept: a row is the family, a boolean, the entry's id and name
when present, and an evidence URL -- the entry's page when present, the search when absent -- which
`bench check-links` walks like any other URL under data/. 01 S7.5: we never scrape BenchmarkList or
ingest Benchmark Radar, and fifty named lookups apiece are neither.

The boolean is a judgement. The search proposes it; the checker confirms or overrides it and says
why in `note`. A re-run keeps every row already in the file (so a reviewer's correction survives);
`--refresh` looks everything up again. The task's verification: a reviewer independently re-runs a
seeded 10 of the 50, records each answer under `review.rerun`, and the run is void if any disagrees.
Until all ten are answered the run is pending, and a void run prints no proportion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RECON_DOMAINS = '_plan/_workflow/recon/recon_domains.md'
RECON_EPOCH = '_plan/_workflow/recon/recon_epoch-assets.md'
SURVEY = 'data/surveys/engineering-design/_family-scoping.yaml'
STRESS = 'taxonomy/_corpus/stress-corpus.yaml'
DOMAINS = 'taxonomy/domains.yaml'
FRAME_SOURCES = (RECON_DOMAINS, RECON_EPOCH, SURVEY, STRESS, DOMAINS)
OUT_DIR = 'data/_analysis'
SEED = 320
REVIEW_N = 10
CHECKED_BY = 'agent (P0-S10-T01)'

# recon_domains.md's thirteen numbered sections.
RECON_SECTIONS = {
    1: 'robotics-embodiment', 2: 'physics', 3: 'chemistry-materials', 4: 'biology-genetics',
    5: 'medicine-health', 6: 'earth-climate', 7: 'games-planning', 8: 'audio-speech', 9: 'vision',
    10: 'agents-tooluse', 11: 'safety-alignment', 12: 'general-intelligence', 13: 'society-econ-law',
}
# recon_epoch-assets.md S6's groups for the five families the domain recon never sized.
EPOCH_GROUPS = {
    'mathematics': 'mathematics', 'code': 'code', 'language': 'language',
    'reasoning-general': 'reasoning-general', 'multimodal / vision': 'multimodal',
}
UNSIZED = tuple(EPOCH_GROUPS.values())
# One family under several names (02 S11: a benchmark and its versions are one family).
COLLAPSE = ((re.compile(r'^FrontierMath\b'), 'FrontierMath'), (re.compile(r'^ARC-AGI\b'), 'ARC-AGI'))
# Trailing version and edition markers, stripped for the family key only: 'Video-MME v2' is VideoMME.
VERSION = re.compile(r'[\s-]*(v\d+(\.\d+)*|\d+\.\d+|20\d\d)$', re.I)
# Recon bullets that are not benchmark families, each by the recon's own description of it. The
# name is the bullet's first bold name, before any ' / '.
NOT_FAMILIES = {
    'Phylogenetics:': 'the recon flags a gap: "I could not find a dominant standing benchmark"',
    'Education:': 'the recon flags a gap: "no dominant public benchmark"',
    'Human-comparison psychometric batteries': 'the recon flags a gap: "no canonical benchmark exists"',
    'Privacy/memorization:': 'a category heading over several benchmarks',
    'Open-ended discovery': 'a category heading over several benchmarks',
    'Open Reaction Database (ORD)': 'the recon: "infrastructure, not a leaderboard"',
    'UK AISI Frontier AI Trends Report': 'the recon: "ecosystem source, not a benchmark"',
    'ECMWF operational verification': 'the recon: "Not a public benchmark"',
    'grand-challenge.org': 'a platform hosting challenges, not a challenge',
    'Epoch AI Benchmarking Hub': 'a registry of benchmarks',
    'Inspect Evals': 'a collection of eval implementations',
    'Vals AI': 'a benchmarking firm',
    'Holistic Agent Leaderboard (HAL)': 'a leaderboard running agents across other benchmarks',
    'Epoch Capabilities Index (ECI)': 'a composite index over other benchmarks',
    'Artificial Analysis Intelligence Index': 'a composite index over other benchmarks',
}


def fold(s) -> str:
    """Benchmark Radar's foldName: lower case, alphanumerics only."""
    return re.sub(r'[^a-z0-9]+', '', str(s or '').lower())


def family_key(name: str) -> str:
    s = re.sub(r'\s*\(.*?\)', '', name).strip()
    for pat, to in COLLAPSE:
        s = to if pat.search(s) else s
    return fold(VERSION.sub('', s)) or fold(s)


def kebab(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


@dataclass(frozen=True)
class Family:
    id: str
    name: str
    domain: str
    frame_source: str
    aliases: tuple[str, ...] = ()


# ---- the frame ----------------------------------------------------------------------------------

def _read(root, rel):
    with open(os.path.join(root, rel), encoding='utf-8') as f:
        return f.read()


def _yaml(root, rel):
    from schema.taxonomy import read_yaml
    return read_yaml(os.path.join(root, rel))


def _names(label: str) -> tuple[str, tuple[str, ...]]:
    """'RoboCasa / RoboCasa GR1 Tabletop' -> ('RoboCasa', ('RoboCasa GR1 Tabletop',))."""
    parts = [p.strip() for p in label.split(' / ') if p.strip()]
    return parts[0], tuple(parts[1:])


def recon_families(text: str) -> list[Family]:
    out, domain = [], None
    for line in text.splitlines():
        m = re.match(r'^# (\d+)\. ', line)
        if m:
            domain = RECON_SECTIONS.get(int(m.group(1)))
            continue
        if line.startswith('# ('):
            domain = None                   # S(a) onwards re-lists names; they are not a domain's list
            continue
        m = re.match(r'^- \*\*(.+?)\*\*', line)
        if domain and m:
            name, aliases = _names(m.group(1))
            if name in NOT_FAMILIES:
                continue
            out.append(Family(kebab(name), name, domain, RECON_DOMAINS, aliases))
    return out


def _split_top(s: str) -> list[str]:
    """Split on , and ; outside parentheses and brackets."""
    out, depth, cur = [], 0, ''
    for ch in s:
        depth += ch in '(['
        depth -= ch in ')]'
        if ch in ',;' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    return out + [cur]


def epoch_families(text: str) -> list[Family]:
    out = []
    for line in text.splitlines():
        m = re.match(r'^\*\*(.+?) \(\d[^)]*\)\*\* — (.*)$', line)
        if not m or m.group(1) not in EPOCH_GROUPS:
            continue
        domain = EPOCH_GROUPS[m.group(1)]
        for item in _split_top(m.group(2)):
            if 'UNVERIFIED' in item:
                continue
            name = re.sub(r'\s*[(\[].*$', '', item).strip()
            for pat, to in COLLAPSE:
                name = to if pat.search(name) else name
            if name:
                out.append(Family(kebab(name), name, domain, RECON_EPOCH))
    return out


def survey_families(doc) -> list[Family]:
    out = []
    for f in doc['families']:
        name = re.sub(r'\s*\(.*\)$', '', f['name']).strip()
        alias = tuple([f['name']] if name != f['name'] else [])
        out.append(Family(kebab(f['name']), name, 'engineering-design', SURVEY, alias))
    return out


def stress_families(doc) -> list[Family]:
    return [Family(e['id'], e['name'], e['domain_family'], STRESS)
            for e in doc['entries'] if e['domain_family'] in UNSIZED]


def seed_targets(doc) -> dict[str, int]:
    return {t['id']: t['seed_target'] for t in doc['terms'] if t.get('parent') is None and 'seed_target' in t}


def build_frame(root: str = ROOT) -> dict[str, list[Family]]:
    """domain family -> its named families, sorted by id. A family is in one stratum only: the first
    source to name it keeps it, in the order recon (by section), Epoch, stress corpus, survey, which
    is the order of how directly each source was asked what a domain's field-defining families are."""
    raw = (recon_families(_read(root, RECON_DOMAINS)) + epoch_families(_read(root, RECON_EPOCH))
           + stress_families(_yaml(root, STRESS)) + survey_families(_yaml(root, SURVEY)))
    frame: dict[str, dict[str, Family]] = {d: {} for d in seed_targets(_yaml(root, DOMAINS))}
    seen: set[str] = set()
    for f in raw:
        keys = {family_key(f.name), *map(family_key, f.aliases)}
        if keys & seen:
            continue
        seen |= keys
        frame[f.domain][f.id] = f
    return {d: sorted(v.values(), key=lambda f: f.id) for d, v in sorted(frame.items())}


def frame_sha256(frame: dict[str, list[Family]]) -> str:
    canon = [[d, [[f.id, f.name, list(f.aliases), f.frame_source] for f in fs]] for d, fs in frame.items()]
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


# ---- the draw -----------------------------------------------------------------------------------

def allocate(targets: dict[str, int], n: int) -> dict[str, int]:
    """Largest-remainder apportionment of n draws in proportion to the seed targets; ties by name."""
    total = sum(targets.values())
    quota = {d: n * t / total for d, t in targets.items()}
    out = {d: math.floor(q) for d, q in quota.items()}
    for d in sorted(quota, key=lambda d: (-(quota[d] - out[d]), d))[:n - sum(out.values())]:
        out[d] += 1
    return dict(sorted(out.items()))


def draw(frame: dict[str, list[Family]], targets: dict[str, int], n: int, seed: int) -> list[Family]:
    rng = random.Random(seed)
    out = []
    for d, k in allocate(targets, n).items():
        members = frame.get(d, [])
        if k > len(members):
            raise SystemExit('%s: %d draws allocated, %d families in the frame' % (d, k, len(members)))
        out += sorted(rng.sample(members, k), key=lambda f: f.id)
    return out


def review_sample(ids: list[str], seed: int, k: int = REVIEW_N) -> list[str]:
    """The families a reviewer re-runs: seeded, and a different stream from the draw."""
    return sorted(random.Random('review:%d' % seed).sample(sorted(ids), min(k, len(ids))))


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


# ---- the lookups --------------------------------------------------------------------------------

def _is_family(query: str, name: str) -> bool:
    """A search hit is the family when its name is the query, or the query and then a qualifier:
    'LIBERO' names 'LIBERO' and 'LIBERO-Long', not 'WatchAct ... an executable LIBERO task'."""
    q, n = fold(query), fold(name)
    if not q:
        return False
    if q == n:
        return True
    head = re.split(r'[:(]', name, maxsplit=1)[0]
    return fold(head) == q or bool(re.match(r'^%s(?![a-z0-9])' % re.escape(query.lower()), name.lower()))


def queries(fam: Family) -> list[str]:
    """What a person types: the name without its parenthetical, the name's own acronym when the
    parenthetical is one ('Humanity's Last Exam (HLE)', not 'NTIRE (CVPR)'), each side of a colon,
    then the aliases the same way."""
    out = []
    for label in (fam.name, *fam.aliases):
        bare = re.sub(r'\s*\(.*?\)', '', label).strip() or label
        out.append(bare)
        initials = ''.join(w[0] for w in re.split(r'[\s-]+', bare) if w).lower()
        out += [m for m in re.findall(r'\(([^()\s]{2,12})\)', label) if m.lower() == initials]
        if ': ' in bare:
            out += [p.strip() for p in bare.split(': ') if p.strip()]
    return list(dict.fromkeys(q for q in out if fold(q)))


@dataclass
class Lookup:
    present: bool
    evidence_url: str
    queries: list[str]
    matched: dict | None = None
    candidates: list[dict] = field(default_factory=list)


class Http:
    """Sequential GETs, spaced per host."""

    def __init__(self, spacing: float = 1.0, timeout: float = 30):
        from tools import archive
        self.spacing, self.timeout, self.ua = spacing, timeout, archive.USER_AGENT
        self._last: dict[str, float] = {}

    def json(self, url: str):
        host = urllib.parse.urlsplit(url).hostname
        wait = self._last.get(host, 0.0) + self.spacing - time.monotonic()  # get-default: first request to a host waits for nothing
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.ua, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        finally:
            self._last[host] = time.monotonic()


class BenchmarkList:
    key = 'benchmarklist'
    title = 'BenchmarkList'
    url = 'https://benchmarklist.com/'
    method = ('One find-benchmarks query per name and alias (https://benchmarklist.com/api/v1/operations/'
              'find-benchmarks.json, limit 10), the bounded read-only operation benchmarklist.com/llms.txt '
              'offers for discovery. It matches full text, so a returned entry counts only when its name is '
              "the family's own; the checker confirms each proposal.")
    FIND = 'https://benchmarklist.com/api/v1/operations/find-benchmarks.json?query=%s&limit=10'

    def __init__(self, http):
        self.http = http

    def lookup(self, fam: Family) -> Lookup:
        asked, candidates, first = [], [], None
        for q in queries(fam):
            url = self.FIND % urllib.parse.quote(q)
            first = first or url
            asked.append(q)
            for hit in self.http.json(url).get('data') or []:
                c = {'id': hit['benchmark_id'], 'name': hit['name'], 'url': hit['urls']['page']}
                if c not in candidates:
                    candidates.append(c)
                if _is_family(q, hit['name']) or _is_family(q, hit['benchmark_id'].replace('_', ' ')):
                    return Lookup(True, c['url'], asked, {'id': c['id'], 'name': c['name']}, candidates)
        return Lookup(False, first, asked, None, candidates)


class BenchmarkRadar:
    key = 'benchmark-radar'
    title = 'Benchmark Radar'
    url = 'https://benchmark-radar.org/'
    method = ("The site's benchmark search: its name-and-alias rule (assets/app.js, searchBenchmarkIndex, "
              "folded substring over name and aliases) over /data/benchmark-index.json, the catalogue the "
              'search page loads. An entry counts when it has a benchmark page and its name is the '
              "family's own; items only in the daily discovery feed are not entries. The checker confirms "
              'each proposal.')
    INDEX = 'https://benchmark-radar.org/data/benchmark-index.json'
    PAGE = 'https://benchmark-radar.org/benchmarks/%s/'
    SEARCH = 'https://benchmark-radar.org/benchmarks/?bq=%s'

    def __init__(self, http):
        self.http = http
        self._index = None

    def index(self) -> list[dict]:
        if self._index is None:
            self._index = self.http.json(self.INDEX)['benchmarks']
        return self._index

    @staticmethod
    def search(records: list[dict], query: str) -> list[dict]:
        """The named half of searchBenchmarkIndex, in its order: exact, prefix, substring; shorter first."""
        needle = fold(query)
        if not needle:
            return []
        scored = []
        for r in records:
            names = [fold(v) for v in [r.get('name'), *(r.get('aliases') or [])]]
            if not any(needle in v for v in names):
                continue
            rank = 0 if needle in names else 1 if any(v.startswith(needle) for v in names) else 2
            scored.append(((rank, len(fold(r.get('name'))), r.get('name') or ''), r))
        return [r for _, r in sorted(scored, key=lambda x: x[0])]

    def lookup(self, fam: Family) -> Lookup:
        asked, candidates = [], []
        for q in queries(fam):
            asked.append(q)
            for r in self.search(self.index(), q)[:10]:
                c = {'id': r['slug'], 'name': r['name'], 'url': self.PAGE % r['slug']}
                if c not in candidates:
                    candidates.append(c)
                if any(_is_family(q, v) for v in [r['name'], *(r.get('aliases') or [])]):
                    return Lookup(True, c['url'], asked, {'id': c['id'], 'name': c['name']}, candidates)
        return Lookup(False, self.SEARCH % urllib.parse.quote(asked[0]), asked, None, candidates)


SERVICES = (BenchmarkList, BenchmarkRadar)


# ---- the files ----------------------------------------------------------------------------------

def out_path(root: str, service: str, on: str) -> str:
    return os.path.join(root, OUT_DIR, 'overlap-%s-%s.yaml' % (service, on[:7]))


def row(fam: Family, got: Lookup, on: str) -> dict:
    return {
        'family': fam.id, 'name': fam.name, 'domain': fam.domain, 'queries': got.queries,
        'present': got.present, 'matched': got.matched, 'evidence_url': got.evidence_url,
        'checked_by': CHECKED_BY, 'checked_on': on, 'basis': 'search-proposal', 'note': None,
    }


def check_rows(rows: list[dict]) -> list[str]:
    """Every row is a lookup: a boolean, a URL and a date, and who checked it."""
    bad = []
    for r in rows:
        for k in ('family', 'present', 'evidence_url', 'checked_by', 'checked_on'):
            v = r.get(k)
            if v is None or v == '' or (k == 'present' and not isinstance(v, bool)):
                bad.append('%s: %s missing' % (r.get('family'), k))
        if r.get('evidence_url') and isinstance(r['evidence_url'], str) and not re.match(r'^https?://\S+$', r['evidence_url']):
            bad.append('%s: evidence_url is not a URL' % r.get('family'))
        if r.get('present') and not r.get('matched'):
            bad.append('%s: present with no matched entry' % r.get('family'))
    return bad


def review_status(doc: dict) -> str:
    """pending until the reviewer answers all of review.rerun; void if any answer disagrees."""
    by = {r['family']: r['present'] for r in doc['rows']}
    answers = doc['review']['rerun']
    if any(a.get('present') is None for a in answers) or not answers:
        return 'pending'
    return 'void' if any(a['present'] != by[a['family']] for a in answers) else 'confirmed'


def summarise(doc: dict) -> dict:
    rows = doc['rows']
    k, n = sum(1 for r in rows if r['present']), len(rows)
    lo, hi = wilson(k, n)
    return {'present': k, 'n': n, 'proportion': round(k / n, 4) if n else None,
            'ci95': [round(lo, 4), round(hi, 4)], 'ci95_method': 'wilson'}


def document(svc, sample, frame, targets, seed, on, rows, previous=None) -> dict:
    alloc = allocate(targets, len(sample))
    doc = {
        'service': svc.key, 'service_title': svc.title, 'service_url': svc.url, 'measured_on': on,
        'quantity': 'entity_overlap (01-landscape-and-positioning.md S4)',
        'catalogued_by': ('the service carries an entry for the family, matched by name or alias; any '
                          'version or child of the family counts (02 S11)'),
        'method': svc.method,
        'sample': {
            'n': len(sample), 'seed': seed, 'design': 'stratified by seed_target (02 S3), largest remainder; '
            'uniform without replacement within each domain family',
            'frame_sources': list(FRAME_SOURCES), 'frame_size': sum(len(v) for v in frame.values()),
            'frame_sha256': frame_sha256(frame),
            'strata': [{'domain': d, 'seed_target': targets[d], 'frame': len(frame.get(d, [])), 'drawn': alloc[d]}
                       for d in alloc],
        },
        'result': None,
        'review': (previous or {}).get('review') or {
            'rule': 'a reviewer independently re-runs these lookups; the run is void if any answer disagrees',
            'reviewed_by': None, 'reviewed_on': None, 'status': 'pending',
            'rerun': [{'family': f, 'present': None} for f in review_sample([f.id for f in sample], seed)],
        },
        'drafted_by': CHECKED_BY,
        'rows': rows,
    }
    doc['result'] = summarise(doc)
    doc['review']['status'] = review_status(doc)
    return doc


def load(path: str):
    if not os.path.exists(path):
        return None
    from schema.taxonomy import read_yaml
    return json.loads(json.dumps(read_yaml(path), default=str))


def write(path: str, doc: dict, root: str = ROOT) -> None:
    from tools import fmt
    rel = os.path.relpath(path, root).replace(os.sep, '/')
    head = ('# %s -- P0-S10-T01\n'
            '# Written by scripts/overlap_sample.py; see its docstring and 01-landscape-and-positioning.md S4.\n'
            '# Not part of the citable core; excluded from every build artifact (05 S2). Each row is a\n'
            '# judgement: `basis` says whether the search proposal stands (search-proposal) or the checker\n'
            '# overrode it (checker-override, with the reason in `note`).\n' % rel)
    text = fmt.format_text(head + fmt.dumps(doc), None, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def line(doc: dict) -> str:
    r, status = doc['result'], doc['review']['status']
    if status == 'void':
        return '%-16s VOID: the reviewer re-run disagrees; no proportion is published' % doc['service']
    return '%-16s %d/%d = %.2f, 95%% interval [%.2f, %.2f] (Wilson); measured %s; review %s' % (
        doc['service'], r['present'], r['n'], r['proportion'], r['ci95'][0], r['ci95'][1],
        doc['measured_on'], status)


def run(root: str, n: int, seed: int, on: str, refresh: bool = False, services=None, http=None,
        candidates: dict | None = None, out_root: str | None = None) -> list[dict]:
    """Look the sample up in each service and write its file under `out_root` (default `root`).
    `candidates`, when given, receives every search hit per service and family, for the checker to
    confirm or override the proposals against."""
    out_root = out_root or root
    frame = build_frame(root)
    targets = seed_targets(_yaml(root, DOMAINS))
    sample = draw(frame, targets, n, seed)
    http = http or Http()
    docs = []
    for cls in services or SERVICES:
        svc = cls(http)
        path = out_path(out_root, svc.key, on)
        previous = None if refresh else load(path)
        kept = {r['family']: r for r in (previous or {}).get('rows') or []}
        rows = []
        for f in sample:
            if f.id in kept:
                rows.append(kept[f.id])
                continue
            got = svc.lookup(f)
            if candidates is not None:
                candidates.setdefault(svc.key, {})[f.id] = got.candidates
            rows.append(row(f, got, on))
        doc = document(svc, sample, frame, targets, seed, on, rows, previous)
        bad = check_rows(doc['rows'])
        if bad:
            raise SystemExit('\n'.join(bad))
        write(path, doc, out_root)
        docs.append(doc)
    return docs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--n', type=int, default=50)
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--date', default=date.today().isoformat(), help='The measurement date; its month names the files.')
    ap.add_argument('--refresh', action='store_true', help='Look every family up again, discarding recorded rows.')
    ap.add_argument('--summary', action='store_true', help='Print from the files already written; no lookups.')
    ap.add_argument('--candidates', help='Write every search hit to this JSON file, for the checker.')
    ap.add_argument('--root', default=ROOT)
    a = ap.parse_args(argv)
    if a.summary:
        docs = [d for d in (load(out_path(a.root, s.key, a.date)) for s in SERVICES) if d]
        for d in docs:
            d['result'], d['review']['status'] = summarise(d), review_status(d)
    else:
        hits = {} if a.candidates else None
        docs = run(a.root, a.n, a.seed, a.date, a.refresh, candidates=hits)
        if a.candidates:
            with open(a.candidates, 'w', encoding='utf-8') as f:
                json.dump(hits, f, ensure_ascii=False, indent=1)
    for d in docs:
        print(line(d))
    return 0 if docs else 1


if __name__ == '__main__':
    sys.exit(main())
