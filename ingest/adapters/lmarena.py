#!/usr/bin/env python3
"""The LMArena adapter (P5-S6-T02; 06 S3.6, 04 S2, 07 S1.2).

    python -m ingest.adapters.lmarena --fixture tests/ingest/fixtures/lmarena     # offline
    bench ingest lmarena --dry-run [--fixture PATH]

06 S3.6: "Do not scrape the site." The data is the Hugging Face dataset lmarena-ai/leaderboard-dataset
(CC-BY-4.0), one subset per arena, each with a `latest` and a `full` parquet. This adapter reads `latest` only:
`full` holds every historical snapshot, which 06 S3.6 drops from the published artifact ("cap at the latest
snapshot"), and its URLs are never requested.

The fetch (07 S1.2: a bundle). One request for the dataset's metadata with blob hashes
(/api/datasets/<id>?blobs=true): the commit, the licence tag and each file's LFS sha256. An unchanged commit is no
change; an arena whose latest file's sha256 the state already holds is not downloaded. A changed file is fetched by
its resolve URL at that commit, which answers 302 to a CDN; the transport does not follow redirects itself, so the
gate (ingest/policy.yaml) is asked about the CDN host before the second request, and the bytes must hash to the
LFS sha256 the metadata named. The licence tag is a veto (06 S1.2): any tag but license:cc-by-4.0 stops the run
before a file is read; snapshots ingested under the old tag stay.

The mapping (06 S3.6), per arena, from its stanza (ingest/mappings/lmarena/<arena>.yaml, which the unit guard
reads for every claim):

    arena (text, vision, ...)     one Leaderboard (lb-lmarena-<arena>) and one RatingPool per snapshot
                                  (pool-lmarena-<arena>-<date>), with the stanza's benchmark and metric
    *_style_control               a separate Leaderboard, RatingPool and Metric -- never a flag on the parent --
                                  so its claims never share a comparability key with the parent's
    model_name                    the System, through the resolver; never created
    rating, rating_lower/_upper   a `rating` claim: value, and uncertainty ci95 [lower, upper]; the metric is
                                  unbounded, requires_pool, headroom_computable: false
    leaderboard_publish_date      the pool's snapshot_date and its id's date, and the claim's date_reported:
                                  every rating claim names its pool, so no rating exists without its snapshot
    vote_count                    metrics/ only: an observation in the report, never on a claim
    category                      only `overall`; the other categories are other subsets of the battles

Capped at the top 25 rows of `overall` per arena (06 S3.6, after 01 S8). The pool's members are those 25, as
resolved: the systems this catalogue holds claims for, not the arena's whole roster, whose size the report gives.
A row whose model does not resolve is a human task and is left out; a pool with fewer than two resolved members is
not drafted, and neither is any claim that would name it.

Agent Arena (agent and its five per-signal subsets) publishes IPS scores, not Bradley-Terry ratings: a different
schema (score, score_ci_*, observation_count), and no rating system RatingPool can hold (elo, bradley-terry,
trueskill, glicko). Those arenas have no stanza, so each is one Unresolved asking a person how to model it; their
columns are still checked, so drift there is caught too.

When it breaks (06 S3.6). An arena that disappears is a lineage event, not an error: a lifecycle review, and the
state keeps its last snapshot. A file whose columns match neither schema -- a renamed rating column -- is schema
drift, a hard fail; so is an `overall` category with more than one publish date, or none. A download that does not
hash to its metadata is a hard fail.

What it writes: nothing. run() returns drafts -- metrics, leaderboards and pools at their entity paths, claims
under data/claims/_ingested/lmarena/<benchmark>/ -- all `new` for the runner to re-classify and the gates to judge.
Today every one rests on records a curator has not written (the LMArena benchmarks, org-lmarena,
src-lmarena-leaderboard-dataset, most systems), so the referential gate holds them; nothing is invented to let
them through (04 S10).
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from collections import Counter  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from ingest.adapters.base import BulkArchiveAdapter, Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.backoff import Response, retry  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

NAME = 'lmarena'
VERSION = '0.1.0'
DATASET = 'lmarena-ai/leaderboard-dataset'
API = 'https://huggingface.co/api/datasets/%s?blobs=true' % DATASET
HOME = 'https://huggingface.co/datasets/%s' % DATASET
LICENCE = 'CC-BY-4.0'
LICENCE_TAG = 'license:cc-by-4.0'
LICENCE_CLASS = 'permissive-attribution'
ATTRIBUTION = 'LMArena, Arena Leaderboard Dataset (lmarena-ai/leaderboard-dataset), CC-BY-4.0, %s' % HOME
SOURCE = 'src-lmarena-leaderboard-dataset'
REPORTED_BY = 'org-lmarena'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
TOP = 25                                  # 06 S3.6: "top 25 rows per arena"
CATEGORY = 'overall'
LATEST = 'latest-00000-of-00001.parquet'
TARGET = 'data/claims/_ingested/%s' % NAME
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
BT_COLUMNS = ('model_name', 'organization', 'license', 'rating', 'rating_lower', 'rating_upper', 'variance',
              'vote_count', 'rank', 'category', 'leaderboard_publish_date')
IPS_COLUMNS = ('model_name', 'organization', 'license', 'score', 'score_ci_lower', 'score_ci_upper',
               'observation_count', 'session_count', 'rank', 'category', 'leaderboard_publish_date')
SchemaDrift = drift.DriftError


class FetchError(Exception):
    """A request answered something the adapter cannot use, or bytes that do not hash to their metadata."""


class LicenceVeto(Exception):
    """06 S1.2: the dataset's licence tag is no longer the one this adapter ingests under."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def slug(arena: str) -> str:
    return arena.replace('_', '-')


# ---- the transport --------------------------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand a 3xx back to the caller, so the gate sees the next host before anything is sent to it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class NetworkTransport:
    """GET over urllib behind the fetcher's gate, one request at a time, redirects returned rather than followed."""

    def __init__(self, timeout: int = 120, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.gate = gate or policy.gate()                  # 07 S10.1: ingest/policy.yaml, robots.txt, no-collect

    def _once(self, url, headers):
        if not url.startswith('https://'):
            raise ValueError('%s: the Hub and its CDN are HTTPS only' % url)
        self.gate.admit(url)
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, **headers})
        try:
            with opener.open(req, timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:                 # a 3xx comes back here too, unfollowed
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


def download(transport, url: str) -> bytes:
    """The body at `url`, following at most one redirect -- each hop a request the gate admits."""
    r = transport.get(url, {})                              # get-default: an HTTP GET with request headers
    if r.status in (301, 302, 303, 307, 308):
        location = header(r.headers, 'Location')
        if not location:
            raise FetchError('%s answered %d with no Location' % (url, r.status))
        r = transport.get(urllib.parse.urljoin(url, location), {})   # get-default: an HTTP GET, not a lookup
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (url, r.status))
    return r.body


# ---- the bundle -----------------------------------------------------------------------------------------------

def read_parquet(body: bytes) -> tuple[list[str], list[dict]]:
    import pyarrow.parquet as pq
    table = pq.read_table(io.BytesIO(body))
    return list(table.column_names), table.to_pylist()


def scoring(arena: str, columns: list[str]) -> str:
    """bradley-terry or ips, read off the columns; anything else is drift (a renamed rating column)."""
    if list(columns) == list(BT_COLUMNS):
        return 'bradley-terry'
    if list(columns) == list(IPS_COLUMNS):
        return 'ips'
    raise SchemaDrift('%s/%s: columns %s are neither the Arena Score schema %s nor the IPS schema'
                      % (arena, LATEST, columns, list(BT_COLUMNS)))


class Snapshot:
    """One fetch: the dataset metadata at a commit, and the latest file of every arena whose hash moved."""

    def __init__(self, meta: dict, files: dict[str, bytes], retrieved_at: datetime):
        self.commit, self.retrieved_at = meta['sha'], retrieved_at
        self.arenas = arenas(meta)
        self.files = files                                 # arena -> bytes, for the arenas fetched this run
        self.parsed = {}
        for arena, body in sorted(files.items()):
            columns, rows = read_parquet(body)
            kind = scoring(arena, columns)
            overall = [r for r in rows if r['category'] == CATEGORY]
            dates = sorted({r['leaderboard_publish_date'] for r in overall})
            if len(dates) != 1:
                raise SchemaDrift('%s/%s: the %s category carries %s publish dates (%s); one is a snapshot'
                                  % (arena, LATEST, CATEGORY, len(dates) or 'no', ', '.join(dates)))
            key = 'rating' if kind == 'bradley-terry' else 'score'
            overall.sort(key=lambda r: (r['rank'], -r[key], r['model_name']))
            self.parsed[arena] = {'scoring': kind, 'date': dates[0], 'rows': overall, 'roster': len(overall),
                                  'sha256': hashlib.sha256(body).hexdigest(), 'file': '%s/%s' % (arena, LATEST)}

    def payload_for(self, candidate: Candidate) -> Payload:
        arena = candidate.source_key.split(':', 1)[1]
        p = self.parsed[arena]
        doc = {'arena': arena, 'commit': self.commit, 'scoring': p['scoring'], 'date': p['date'],
               'roster': p['roster'], 'rows': p['rows'][:TOP], 'file': p['file']}
        return Payload(candidate=candidate, body=b'', content_type='application/vnd.apache.parquet', http_status=200,
                       fetched_at=self.retrieved_at, etag=None, last_modified=None, sha256_normalised=p['sha256'],
                       from_cache=False, doc=doc)

    def snapshot(self) -> dict:
        return {'name': DATASET, 'url': HOME, 'retrieved_at': iso(self.retrieved_at), 'commit': self.commit,
                'artefact_sha256': hashlib.sha256(json.dumps(sorted(self.arenas.items())).encode()).hexdigest(),
                'artefact_bytes': sum(len(b) for b in self.files.values())}


def arenas(meta: dict) -> dict[str, str]:
    """arena -> the LFS sha256 of its latest parquet, from the metadata's siblings."""
    out = {}
    for s in meta['siblings']:
        name = s['rfilename']
        if name.endswith('/' + LATEST) and name.count('/') == 1:
            out[name.split('/')[0]] = s['lfs']['sha256']
    if not out:
        raise SchemaDrift('%s: no <arena>/%s in the dataset; the layout changed' % (DATASET, LATEST))
    return out


def fetch_snapshot(transport, state: dict, now=utcnow) -> Snapshot | None:
    """The metadata, then each changed arena's latest file. None when the commit is the one the state holds."""
    r = transport.get(API, {})                              # get-default: an HTTP GET with request headers
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (API, r.status))
    meta = json.loads(r.body)
    for key in ('sha', 'tags', 'siblings'):
        if key not in meta:
            raise SchemaDrift('%s: the metadata lacks %r' % (API, key))
    if LICENCE_TAG not in meta['tags']:
        raise LicenceVeto('%s is tagged %s, not %s: the licence veto (06 S1.2) stops ingestion from this run on; '
                          'snapshots already ingested stay' % (DATASET, [t for t in meta['tags'] if t.startswith('license:')]
                                                               or 'no licence', LICENCE_TAG))
    if meta['sha'] == state.get('commit'):                  # get-default: a cold run has no commit
        return None
    held = state.get('arenas') or {}                        # get-default: a cold run holds no arena
    files = {}
    for arena, sha in sorted(arenas(meta).items()):
        if held.get(arena, {}).get('sha256') == sha:        # get-default: an arena the state has not seen
            continue
        url = '%s/resolve/%s/%s/%s' % (HOME, meta['sha'], arena, LATEST)
        body = download(transport, url)
        if hashlib.sha256(body).hexdigest() != sha:
            raise FetchError('%s does not hash to the sha256 its metadata names (%s)' % (url, sha))
        files[arena] = body
    return Snapshot(meta, files, now())


# ---- the mapping ------------------------------------------------------------------------------------------------

def pool_id(arena: str, date: str) -> str:
    return 'pool-lmarena-%s-%s' % (slug(arena), date)


def leaderboard_id(arena: str) -> str:
    return 'lb-lmarena-%s' % slug(arena)


def title(arena: str) -> str:
    base, variant = arena, ''
    for suf, label in (('_style_control', ' (style control)'), ('_factuality', ' (factuality)')):
        if arena.endswith(suf):
            base, variant = arena[:-len(suf)], label
    return 'LMArena %s Arena%s' % (base.replace('_', ' ').title().replace('To', 'to'), variant)


def record_id(arena: str, row: dict) -> str:
    """04 S9's content key: the file, and the row's category, publish date and model -- never its rank."""
    return '%s#%s' % (arena, urllib.parse.urlencode([('category', row['category']),
                                                     ('leaderboard_publish_date', row['leaderboard_publish_date']),
                                                     ('model_name', row['model_name'])]))


def metric_doc(arena: str, metric: str) -> dict:
    return {
        'id': metric, 'name': 'Arena Score', 'full_name': '%s Arena Score' % title(arena),
        'definition': ('A Bradley-Terry rating fitted to pairwise human votes between anonymous models in %s, '
                       'on an Elo-like scale.' % title(arena)),
        'value_type': 'elo', 'unbounded': True, 'optimum': 'max',
        'aggregation': 'Bradley-Terry fit over the pool\'s pairwise votes, with a 95% confidence interval',
        'units': 'rating points', 'requires_pool': True, 'headroom_computable': False,
        'pitfalls': ('Pool-relative: a score moves when the pool changes, with no change to the model, so it is '
                     'read with its snapshot date and never compared across pools, snapshots or arenas (06 S3.6).'),
        'sources': [SOURCE],
    }


def normalise(payload: Payload, resolvers: dict, stanzas: dict) -> tuple[list[Draft], list[Unresolved]]:
    """Drafts and human tasks for one arena's latest snapshot. Pure: the payload, the resolvers and the stanzas."""
    doc = payload.doc
    arena, date = doc['arena'], doc['date']
    key = payload.candidate.source_key
    stanza = stanzas.get('csv:' + arena)                     # get-default: an arena with no stanza yet
    if stanza is None:
        why = ('Agent Arena publishes IPS scores (score, score_ci_*), which no RatingPool rating system holds; '
               'decide how to model them' if doc['scoring'] == 'ips' else 'Write its stanza')
        return [], [Unresolved(key, 'stanza', arena, 'no-match',
                               human_task='%s: no stanza at ingest/mappings/lmarena/%s.yaml. %s; its %d rows wait '
                                          '(06 S3.6).' % (arena, arena, why, doc['roster']))]
    if doc['scoring'] != 'bradley-terry':
        raise SchemaDrift('%s: its stanza maps a rating, but the file holds %s scores' % (arena, doc['scoring']))
    fetched = iso(payload.fetched_at)
    source_url = '%s/blob/%s/%s' % (HOME, doc['commit'], doc['file'])
    unresolved, members, rows = [], [], []
    for row in doc['rows']:
        hit = resolvers['system'].resolve(row['model_name'])
        if hit.entity is None:
            unresolved.append(Unresolved(
                row['model_name'], 'claim.system', row['model_name'], 'no-match',
                human_task='No System is %r (%s, rank %d in %s on %s). Add it, or an alias in '
                           'data/aliases/systems.yaml; never a guess (04 S10).'
                           % (row['model_name'], row['organization'], int(row['rank']), title(arena), date)))
            continue
        system = hit.entity.split(':', 1)[1] + ('@%s' % hit.version if hit.version else '')
        if system in members:
            unresolved.append(Unresolved(record_id(arena, row), 'claim.system', row['model_name'], 'ambiguous-match',
                                         human_task='%r resolves to %s, which another row of %s on %s already is; say '
                                                    'which version each names.' % (row['model_name'], system, arena, date)))
            continue
        members.append(system)
        rows.append((row, system, hit.score))
    if len(members) < 2:
        unresolved.append(Unresolved(key, 'rating_pool', '%s@%s' % (arena, date), 'no-match',
                                     human_task='%s on %s: %d of its top %d resolve to a System, and a pool needs two; '
                                                'no pool, so no rating claim (06 S3.6).' % (arena, date, len(members), TOP)))
        return [], unresolved
    pid, lid = pool_id(arena, date), leaderboard_id(arena)
    batch = 'ingest-%s-%s' % (NAME, payload.fetched_at.strftime('%Y%m%d'))
    base_ingestion = {'batch': batch, 'source_adapter': NAME, 'adapter_version': VERSION, 'source_url': source_url,
                      'source_licence': LICENCE, 'licence_class': LICENCE_CLASS, 'source_attribution': ATTRIBUTION,
                      'ingested_at': fetched, 'review_state': 'machine-ingested'}
    drafts = [
        Draft('metric', stanza.metric_ref, Path('data/metrics') / ('%s.yaml' % stanza.metric_ref),
              metric_doc(arena, stanza.metric_ref), 'new', None, 1.0, labels=['ingest:new']),
        Draft('leaderboard', lid, Path('data/leaderboards') / ('%s.yaml' % lid),
              {'id': lid, 'name': title(arena), 'host_org': REPORTED_BY, 'url': '%s/viewer/%s' % (HOME, arena),
               'form': 'periodic-snapshot', 'benchmarks': [stanza.benchmark_ref.split('@')[0].split('#')[0]],
               'is_live': True, 'last_updated': date},
              'new', None, 1.0, labels=['ingest:new']),
        Draft('rating_pool', pid, Path('data/rating-pools') / ('%s.yaml' % pid),
              {'id': pid, 'leaderboard': lid, 'benchmark': stanza.benchmark_ref, 'snapshot_date': date,
               'members': sorted(members), 'rating_system': 'bradley-terry', 'sources': [SOURCE]},
              'new', None, 1.0, labels=['ingest:new']),
    ]
    for row, system, score in rows:
        rid = record_id(arena, row)
        drafts.append(Draft(
            'claim', None, Path(TARGET) / stanza.benchmark_ref.split('@')[0].split('#')[0],
            {'system': system, 'benchmark': stanza.benchmark_ref, 'metric': stanza.metric_ref, 'claim_type': 'rating',
             'value': round(float(row['rating']) * stanza.scale, 6), 'rating_pool': pid,
             'uncertainty': {'type': 'ci95', 'value': [round(float(row['rating_lower']), 6),
                                                       round(float(row['rating_upper']), 6)]},
             'date_reported': date, 'reported_by': REPORTED_BY, 'verification': 'maintainer-verified',
             'source': SOURCE},
            'new',
            {**base_ingestion, 'source_record_id': rid, 'last_seen_upstream': date,
             'field_provenance': {'value': 'source', 'uncertainty': 'source', 'rating_pool': 'derived',
                                  'date_reported': 'source', 'verification': 'derived'}},
            score, labels=['source:%s' % NAME]))
    return drafts, unresolved


class LMArena(BulkArchiveAdapter):
    """06 S3.6's adapter on 07 S1.2's contract: one metadata fetch, one logical record per arena."""

    name, version, licence, licence_class, attribution = NAME, VERSION, LICENCE, LICENCE_CLASS, ATTRIBUTION
    expected_yield = (100, 450)       # 07 S9's seed band: 16 rated arenas x top 25, about 400 rows
    tier, source_id = 2, SOURCE        # 06 S8.2: Tier 2
    volatile_fields = ()

    def __init__(self, transport=None, now=utcnow, stanzas: dict | None = None):
        self.transport, self.now, self.bundle = transport, now, None
        self.stanzas = stanzas

    def fetch_bundle(self, state: dict) -> Snapshot | None:
        return fetch_snapshot(self.transport, state, self.now)

    def enumerate(self, snap: Snapshot):
        for arena in sorted(snap.parsed):
            yield Candidate('arena:%s' % arena, 'leaderboard', '%s/viewer/%s' % (HOME, arena), {})

    def normalise(self, payload, resolver=None):
        if self.stanzas is None:
            from ingest.mappings.schema import load_all
            self.stanzas = load_all(NAME)
        return normalise(payload, resolver, self.stanzas)


# ---- one run ------------------------------------------------------------------------------------------------------

def new_state() -> dict:
    return {'version': 1, 'commit': None, 'arenas': {}}


def resolvers_from(root: str | None = None) -> dict:
    from ingest.resolve import ROOT as R, Index
    return {'system': Index.load('system', root or R)}


def run(adapter: LMArena, state: dict | None = None, resolvers: dict | None = None) -> dict:
    """Fetch, check, normalise. Writes nothing: `state` is updated in place for the caller to persist."""
    state = state if state is not None else new_state()
    started = adapter.now()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(started), 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'drafts_by_type': {}, 'unresolved': 0,
              'unresolved_items': [], 'errors': [], 'snapshot': None, 'arenas': {}, 'observations': [],
              'proposals': [], 'documents': []}
    try:
        snap = adapter.fetch_bundle(state)
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    except (LicenceVeto, FetchError, policy.PolicyRefusal) as e:
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(adapter.now()))
        return report
    if snap is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    adapter.bundle = snap
    report['snapshot'] = snap.snapshot()
    if resolvers is None:
        resolvers = resolvers_from()
    asked = set()
    gone = sorted(set(state.get('arenas') or {}) - set(snap.arenas))   # get-default: a cold run holds none
    for arena in gone:
        u = Unresolved('arena:%s' % arena, 'leaderboard', arena, 'out-of-band',
                       human_task='The %s arena is no longer in %s at %s. A lineage event, not an error (06 S3.6): '
                                  'review its Leaderboard\'s lifecycle; its last snapshot (%s) stays.'
                                  % (arena, DATASET, snap.commit[:12], state['arenas'][arena]['date']))
        report['unresolved_items'].append({'source_key': u.source_key, 'field': u.field, 'reason': u.reason,
                                           'human_task': u.human_task})
        report['unresolved'] += 1
    report['drafts']['gone'] = len(gone)
    try:
        _normalise_all(adapter, snap, resolvers, report, asked)
    except SchemaDrift as e:                                # a stanza that no longer fits its file: commit nothing
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], documents=[], observations=[],
                      finished_at=iso(adapter.now()), issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    held = dict(state.get('arenas') or {})                  # get-default: as above
    for arena, p in snap.parsed.items():
        held[arena] = {'sha256': p['sha256'], 'date': p['date']}
    state.update(commit=snap.commit, arenas=held)            # a vanished arena keeps its last snapshot (06 S3.6)
    report['finished_at'] = iso(adapter.now())
    return report


def _normalise_all(adapter, snap, resolvers, report, asked):
    for cand in adapter.enumerate(snap):
        report['candidates_seen'] += 1
        payload = adapter.fetch(cand)
        doc = payload.doc
        report['arenas'][doc['arena']] = {'date': doc['date'], 'scoring': doc['scoring'], 'roster': doc['roster']}
        report['observations'] += [{'arena': doc['arena'], 'model_name': r['model_name'], 'snapshot': doc['date'],
                                    'votes': r['vote_count'] if doc['scoring'] == 'bradley-terry' else r['observation_count']}
                                   for r in doc['rows']]
        drafts, unresolved = adapter.normalise(payload, resolvers)
        for u in unresolved:
            if u.fingerprint in asked:
                continue
            asked.add(u.fingerprint)
            report['unresolved'] += 1
            report['unresolved_items'].append({'source_key': u.source_key, 'field': u.field, 'reason': u.reason,
                                               'human_task': u.human_task})
        for d in drafts:
            report['drafts'][d.change_class] += 1
            kind = d.path.parts[1] if d.entity_type != 'claim' else 'claims'
            report['drafts_by_type'][kind] = report['drafts_by_type'].get(kind, 0) + 1   # get-default: a first draft of its kind
            report['documents'].append({'path': d.path.as_posix(), 'entity_type': d.entity_type, 'entity_id': d.entity_id,
                                        **d.payload, **({'ingestion': dict(d.ingestion, extraction_confidence=d.confidence)}
                                                        if d.ingestion else {})})   # 07 S1.1: confidence lands there


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture', help='a recorded-response directory in place of the network')
    a = p.parse_args(argv)
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport()
    report = run(LMArena(transport), new_state())
    print(json.dumps({k: v for k, v in report.items() if k not in ('documents', 'observations')}, indent=2,
                     default=str))
    return 1 if report['status'] == 'hard-fail' else 0


if __name__ == '__main__':
    sys.exit(main())
