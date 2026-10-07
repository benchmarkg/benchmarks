#!/usr/bin/env python3
"""The HuggingFace Hub adapter: discover() and fetch() (P5-S1-T03; 06 S3.2, 07 S1.1, S4.1).

    python -m ingest.adapters.hf_hub --fixture tests/ingest/fixtures/hf-hub   # offline, zero network
    python -m ingest.adapters.hf_hub                                          # live, anonymous
    python -m ingest.adapters.hf_hub --dry-run --limit 50                     # live, write nothing

What it enumerates (06 S3.2). Two listings, fetched slim:

    spaces?filter=leaderboard&limit=1000     one Candidate per Space      kind leaderboard
    datasets?filter=benchmark:official       one Candidate per dataset    kind benchmark

and, selectively, `datasets/{id}?full=true` for a dataset whose listing entry has changed. Spaces
get no detail fetch: their listing entry already carries every tag 06 S3.2 maps, and 1,019 detail
calls would spend half a five-minute anonymous window on data the listing already gave us.

How it avoids re-fetching (07 S4.1, "ETag on list endpoints, plus short-circuit on lastModified in
the payload before fetching detail"):

  1. Pagination follows the `Link: <...>; rel="next"` header, cursor to cursor, until there is none.
  2. Every URL's ETag is kept in the state file (07 S4 layer 2, ingest/state/hf-hub.json), and every
     request for a URL we have an ETag for is sent with If-None-Match.
  3. A dataset whose listing `lastModified` equals the one recorded in state is not fetched at all:
     the decision is made before any request is issued.
  4. Whatever does come back is hashed after the volatile fields are stripped (07 S1.5); an unchanged
     hash is "no payload", exactly like a 304.

A 304 on a listing still has to enumerate the listing, so listing bodies are kept in a request cache
(07 S4 layer 3: "the HF request cache"), under ingest/raw/, which is gitignored. The cache is only
ever an optimisation: If-None-Match is sent for a listing only when its body is in the cache, so an
evicted cache costs one unconditional GET, never a blind 304.

Fixture mode. `--fixture DIR` swaps the transport for recorded bytes: each `<name>.headers.json`
from scripts/capture_hf_fixtures.py names its URL, and a request for that URL replays the body and
headers -- or a 304 when the request's If-None-Match matches the recorded ETag, which is how a second
fixture run proves the conditional path. The fixture transport has no network code in it at all. A
URL the fixture set does not hold raises FixtureMiss: on a listing's first page that is a hard fail;
on a later page or a detail it is recorded in the run report as the edge of the recorded set, never
silently read as "nothing there".

Why urllib and not `huggingface_hub`. 06 S3.2 says "use the library, not raw HTTP". The library's
list calls follow the Link header internally and neither expose the ETag nor accept If-None-Match on
a listing, so steps 1 and 2 above cannot be done through it. 07 S4.3 already makes our own RateLimit
parser the mechanism and the library's sleep an optimisation, so this adapter uses
ingest/http/ratelimit.py and ingest/http/backoff.py directly: 07 S4.2's retry policy, and 07 S10's
budget of ~1 request per second and at most 2,000 requests a run.

Volatile fields. 07 S1.5 declares downloads, likes, downloadsAllTime and _id for hf-hub. This adds
trendingScore, which both captured listings carry and which moves at least as often as likes; without
it no Space could ever hash as unchanged.

State is mutated in memory as candidates are fetched. Whoever consumes the payloads saves it, so a
crash between fetch and write can never mark a record as seen. normalise() (P5-S1-T04, below) turns a
payload into a discovery candidate, but nothing writes those yet, so the CLI saves to
ingest/raw/hf-hub[-fixture]/state.json, which is
gitignored, and never to the committed ingest/state/hf-hub.json unless --state names it: a live run
today would otherwise record ETags and hashes for payloads no draft was ever written from, and the
first real run would then see nothing to do.

Candidate and Payload are 07 S1.1's shapes, declared here until ingest/adapters/base.py exists
(P3-S1-T02); P5-S1-T08 moves this adapter onto the shared Adapter class.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if __name__ == '__main__' and not __package__:
    # Run as a file, this directory is sys.path[0]; put the repository root there so that
    # `ingest.http` resolves and nothing here shadows the standard library.
    sys.path[0] = ROOT

import argparse  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from collections import Counter  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from email.utils import parsedate_to_datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from ingest.adapters.base import Candidate, Payload  # noqa: E402,F401  (07 S1.1's types; tests import them from here)
from ingest.http import backoff, ratelimit  # noqa: E402
from ingest.http.fixture import (FixtureMiss, FixtureTransport, NetworkForbidden, NoNetwork,  # noqa: E402,F401
                                 header, header_values)
from ingest.http.backoff import Response  # noqa: E402

NAME = 'hf-hub'
VERSION = '0.1.0'
API = 'https://huggingface.co/api'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
VOLATILE_FIELDS = ('downloads', 'likes', 'downloadsAllTime', '_id', 'trendingScore')
MIN_INTERVAL = 1.0      # seconds between requests to the Hub (07 S10: ~1 req/s)
MAX_REQUESTS = 2000     # per run (07 S10)
EXIT = {'ok': 0, 'no-change': 0, 'partial': 0, 'capped': 0, 'soft-fail': 1, 'hard-fail': 2}  # by run status
MAX_PAGES = 50          # per listing; 1,019 Spaces is two pages, so fifty is a loop, not a listing
CACHE_CAP = 16 << 20    # bytes; a listing body larger than this is not cached
STATE = os.path.join(ROOT, 'ingest', 'state', 'hf-hub.json')
RAW = os.path.join(ROOT, 'ingest', 'raw')

# The keys each payload kind must carry before it is trusted (06 S3.2, "assert structure
# explicitly"); the same sets tests/ingest/test_hf_fixtures.py pins against the captured fixtures.
SPACE_KEYS = frozenset({'id', 'tags', 'likes', 'createdAt'})
DATASET_KEYS = frozenset({'id', 'tags', 'gated', 'disabled', 'downloads', 'likes', 'lastModified'})
DETAIL_KEYS = DATASET_KEYS | {'cardData', 'siblings'}


@dataclass(frozen=True)
class Listing:
    name: str
    url: str
    kind: str        # the Candidate kind its entries become
    prefix: str      # source_key namespace: "space:" / "dataset:"
    required: frozenset
    site: str        # canonical human URL prefix, for Candidate.url


LISTINGS = (
    Listing('spaces-leaderboard', API + '/spaces?filter=leaderboard&limit=1000', 'leaderboard', 'space',
            SPACE_KEYS, 'https://huggingface.co/spaces/'),
    Listing('datasets-benchmark-official', API + '/datasets?filter=benchmark:official', 'benchmark', 'dataset',
            DATASET_KEYS, 'https://huggingface.co/datasets/'),
)


class SchemaDrift(Exception):
    """06 S3.2 "When it breaks": zero rows, or a record missing a mapped key. A hard fail."""


class Capped(Exception):
    """The run's request budget is spent."""


# ---- headers ----------------------------------------------------------------------------------

_PARAM = re.compile(r';\s*([^\s=;,]+)\s*(?:=\s*("([^"]*)"|[^;,]*))?')


def next_link(headers, base):
    """The `rel="next"` target of any Link header (RFC 8288), resolved against the request URL."""
    for value in header_values(headers, 'Link'):
        for link in re.split(r',\s*(?=<)', value.strip()):
            m = re.match(r'<([^>]*)>(.*)$', link.strip(), re.S)
            if not m:
                continue
            for p in _PARAM.finditer(m.group(2)):
                if p.group(1).lower() != 'rel':
                    continue
                rel = p.group(3) if p.group(3) is not None else (p.group(2) or '')
                if 'next' in rel.lower().split():
                    return urllib.parse.urljoin(base, m.group(1).strip())
    return None


def response_date(headers, fallback):
    try:
        return parsedate_to_datetime(header(headers, 'Date')).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return fallback


# ---- hashing ----------------------------------------------------------------------------------

def strip_volatile(doc):
    if isinstance(doc, list):
        return [strip_volatile(d) for d in doc]
    if isinstance(doc, dict):
        return {k: v for k, v in doc.items() if k not in VOLATILE_FIELDS}
    return doc


def sha256_normalised(doc):
    """07 S1.5: the hash of the payload with volatile fields removed, as sorted, spaceless JSON."""
    canon = json.dumps(strip_volatile(doc), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


# ---- transports -------------------------------------------------------------------------------

class NetworkTransport:
    """GET over urllib, under 07 S4.2's retry policy and the Hub's own RateLimit headers."""

    def __init__(self, token=None, min_interval=MIN_INTERVAL, timeout=60,
                 clock=time.monotonic, wall=time.time, sleep=time.sleep):
        self.token, self.min_interval, self.timeout = token, min_interval, timeout
        self.clock, self.wall, self.sleep = clock, wall, sleep
        self._not_before = 0.0

    def _once(self, url, headers):
        wait = self._not_before - self.clock()
        if wait > 0:
            self.sleep(wait)
        h = {'User-Agent': USER_AGENT, 'Accept': 'application/json', **headers}
        if self.token:
            h['Authorization'] = 'Bearer ' + self.token
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:  # urllib raises for 304 too
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        stated = ratelimit.wait_seconds(resp.status, resp.headers, now=self.wall()) or 0.0
        self._not_before = resp.received_at + max(self.min_interval, stated)
        return resp

    def get(self, url, headers):
        return backoff.retry(lambda: self._once(url, headers), clock=self.clock, wall=self.wall,
                             sleep=self.sleep)


# ---- layer 3: the request cache ---------------------------------------------------------------

class RequestCache:
    """Listing bodies and headers by URL, so a 304 can still be enumerated. Regenerable, gitignored."""

    def __init__(self, directory):
        self.dir = directory

    def _base(self, url):
        return os.path.join(self.dir, hashlib.sha256(url.encode('utf-8')).hexdigest()[:32])

    def get(self, url):
        base = self._base(url)
        try:
            with open(base + '.json', encoding='utf-8') as f:
                meta = json.load(f)
            with gzip.open(base + '.body.gz', 'rb') as f:
                body = f.read()
        except (OSError, ValueError, EOFError):
            return None
        if meta.get('url') != url or hashlib.sha256(body).hexdigest() != meta.get('sha256'):
            return None
        return meta['headers'], body

    def put(self, url, headers, body):
        if len(body) > CACHE_CAP:
            return
        os.makedirs(self.dir, exist_ok=True)
        base = self._base(url)
        with gzip.GzipFile(base + '.body.gz', 'wb', mtime=0) as f:
            f.write(body)
        with open(base + '.json', 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'url': url, 'sha256': hashlib.sha256(body).hexdigest(),
                       'headers': [list(kv) for kv in (headers.items() if hasattr(headers, 'items') else headers)]},
                      f, indent=1)


# ---- layer 2: the state file ------------------------------------------------------------------

def new_state():
    """07 S4's shape. `records` is this adapter's per-candidate memory: the listing lastModified the
    detail short-circuit compares, and the first 16 hex of the last payload's normalised hash."""
    return {
        'adapter': NAME, 'adapter_version': VERSION,
        'last_run': None, 'last_success': None, 'last_change': None, 'consecutive_failures': 0,
        'cursor': {'type': 'link-next+etag',
                   'note': 'listings are re-enumerated each run; Link rel=next pages them, ETags make them cheap'},
        'checkpoint': None, 'urls': {}, 'records': {}, 'yield_history': [],
    }


def load_state(path):
    if not os.path.exists(path):
        return new_state()
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    for k, v in new_state().items():
        state.setdefault(k, v)
    return state


def save_state(path, state):
    """Sorted, with `records` one line per candidate, so a run's state diff reads as the list of
    records whose payload changed. Still plain JSON; load_state() reads it back unchanged."""
    records = sorted(state['records'].items())
    text = json.dumps(dict(state, urls=dict(sorted(state['urls'].items())), records={}),
                      indent=2, ensure_ascii=False)
    if records:
        lines = ',\n'.join('    %s: %s' % (json.dumps(k, ensure_ascii=False),
                                            json.dumps(v, ensure_ascii=False, sort_keys=True))
                           for k, v in records)
        text = text.replace('"records": {}', '"records": {\n%s\n  }' % lines, 1)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text + '\n')
    os.replace(tmp, path)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---- the adapter ------------------------------------------------------------------------------

def check_listing(doc, listing, first_page):
    if not isinstance(doc, list):
        raise SchemaDrift('%s: expected a JSON array, got %s' % (listing.name, type(doc).__name__))
    if first_page and not doc:
        raise SchemaDrift('%s returned zero rows: schema drift, not an empty result' % listing.name)
    for r in doc:
        missing = listing.required - set(r) if isinstance(r, dict) else listing.required
        if missing:
            raise SchemaDrift('%s record %s lacks %s' % (listing.name, r.get('id') if isinstance(r, dict) else r,
                                                         sorted(missing)))
    return doc


class HfHub:
    name, version, volatile_fields = NAME, VERSION, VOLATILE_FIELDS

    def __init__(self, transport, cache, max_requests=MAX_REQUESTS, now=None):
        self.transport, self.cache, self.max_requests = transport, cache, max_requests
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.requests = 0
        self.http_codes = Counter()
        self.stats = Counter()
        self.fixture_missing = []
        self.notes = []

    # One GET. need_body: the caller cannot act on a 304 without the body (a listing), so
    # If-None-Match is sent only when the cache can answer for it.
    def _get(self, url, state, need_body):
        entry = state['urls'].get(url, {})  # get-default: our own state file; an unfetched URL has no entry
        cached = self.cache.get(url) if need_body else None
        req = {}
        if entry.get('etag') and (cached is not None or not need_body):
            req['If-None-Match'] = entry['etag']
        if self.requests >= self.max_requests:
            raise Capped('request budget of %d spent' % self.max_requests)
        self.requests += 1
        resp = self.transport.get(url, req)  # get-default: an HTTP GET with request headers, not a lookup
        self.http_codes[resp.status] += 1
        now = iso(self.now())
        if resp.status == 304:
            entry['last_fetched'] = now
            state['urls'][url] = entry
            if need_body:
                return resp, cached[1], cached[0], True
            return resp, None, resp.headers, True
        if resp.status != 200:
            raise backoff.SoftFail('%s: HTTP %d' % (url, resp.status), resp, 1)
        entry.update({'etag': header(resp.headers, 'ETag'), 'last_modified': header(resp.headers, 'Last-Modified'),
                      'bytes': len(resp.body), 'last_fetched': now})
        state['urls'][url] = entry
        if need_body:
            self.cache.put(url, resp.headers, resp.body)
        return resp, resp.body, resp.headers, False

    def _stamp(self, state, url, sha):
        entry = state['urls'][url]
        if entry.get('sha256_normalised') != sha:
            entry['sha256_normalised'] = sha
            entry['last_changed'] = entry['last_fetched']

    def discover(self, state):
        """Every Space on the leaderboard listing and every benchmark:official dataset, in order."""
        seen = set()
        for listing in LISTINGS:
            url, page, visited = listing.url, 0, set()
            while url:
                if url in visited or page >= MAX_PAGES:
                    self.notes.append('%s: pagination stopped at page %d (%s)'
                                      % (listing.name, page, 'cursor loop' if url in visited else 'page cap'))
                    break
                visited.add(url)
                try:
                    resp, body, headers, from_cache = self._get(url, state, need_body=True)
                except FixtureMiss:
                    if page == 0:
                        raise
                    self.fixture_missing.append(url)
                    self.notes.append('%s: the fixture set ends after page %d' % (listing.name, page))
                    break
                doc = check_listing(json.loads(body.decode('utf-8')), listing, first_page=page == 0)
                self._stamp(state, url, sha256_normalised(doc))
                fetched_at = response_date(resp.headers, self.now())
                for rec in doc:
                    key = '%s:%s' % (listing.prefix, rec['id'])
                    if key in seen:  # a cursor over a moving sort can repeat an entry
                        self.stats['duplicates'] += 1
                        continue
                    seen.add(key)
                    hint = {'listing': listing.name, 'page_url': url, 'record': rec, 'from_cache': from_cache,
                            'fetched_at': fetched_at, 'lastModified': rec.get('lastModified')}
                    if listing.prefix == 'dataset':
                        quoted = urllib.parse.quote(rec['id'], safe='/')
                        hint['detail_url'] = '%s/datasets/%s?full=true' % (API, quoted)
                        hint['croissant_url'] = '%s/datasets/%s/croissant' % (API, quoted)
                    yield Candidate(key, listing.kind, listing.site + rec['id'], hint)
                url = next_link(headers, url)
                page += 1

    def normalise(self, payload, resolvers, xwalk=None):
        """07 S1.1's normalise(payload, resolver): the module function, with the committed crosswalk."""
        return normalise(payload, resolvers, xwalk if xwalk is not None else self.crosswalk)

    @property
    def crosswalk(self):
        if getattr(self, '_crosswalk', None) is None:
            self._crosswalk = load_crosswalk()
        return self._crosswalk

    def fetch(self, candidate, state):
        """A Payload, or None when nothing changed: short-circuited, 304, or an unchanged hash."""
        if candidate.source_key.startswith('space:'):
            return self._from_listing(candidate, state)
        return self._dataset(candidate, state)

    def _payload(self, candidate, state, doc, body, status, fetched_at, etag, last_modified, from_cache):
        sha = sha256_normalised(doc)
        lm = candidate.hint.get('lastModified')
        entry = {'sha256': sha[:16], **({'lastModified': lm} if lm else {})}  # a Space has no lastModified
        prev = state['records'].get(candidate.source_key)
        if prev is not None and prev['sha256'] == sha[:16]:
            state['records'][candidate.source_key] = entry
            self.stats['unchanged'] += 1
            return None
        state['records'][candidate.source_key] = entry
        self.stats['payloads'] += 1
        self.stats['payloads_from_cache'] += from_cache
        return Payload(candidate=candidate, body=body, content_type='application/json', http_status=status,
                       fetched_at=fetched_at, etag=etag, last_modified=last_modified, sha256_normalised=sha,
                       from_cache=from_cache, doc=doc)

    def _from_listing(self, candidate, state):
        doc = candidate.hint['record']
        body = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode('utf-8')
        return self._payload(candidate, state, doc, body, 200, candidate.hint['fetched_at'], None, None,
                             candidate.hint['from_cache'])

    def _dataset(self, candidate, state):
        lm = candidate.hint.get('lastModified')
        rec = state['records'].get(candidate.source_key)
        if rec and lm and rec.get('lastModified') == lm:
            self.stats['short_circuited'] += 1  # decided before any request is issued
            return None
        url = candidate.hint['detail_url']
        try:
            resp, body, headers, _ = self._get(url, state, need_body=False)
        except FixtureMiss:
            self.fixture_missing.append(url)
            return None
        if resp.status == 304:
            if rec is not None:
                rec['lastModified'] = lm
            self.stats['not_modified'] += 1
            return None
        doc = json.loads(body.decode('utf-8'))
        want = candidate.source_key.split(':', 1)[1]
        missing = DETAIL_KEYS - set(doc) if isinstance(doc, dict) else DETAIL_KEYS
        if missing or doc.get('id') != want:
            raise SchemaDrift('%s: detail for %s lacks %s or names %r'
                              % (url, want, sorted(missing), doc.get('id') if isinstance(doc, dict) else doc))
        self._stamp(state, url, sha256_normalised(doc))
        return self._payload(candidate, state, doc, body, resp.status, response_date(headers, self.now()),
                             header(headers, 'ETag'), header(headers, 'Last-Modified'), False)


# ---- normalise (P5-S1-T04; 07 S1.1, S1.5; 06 S1.1, S3.2) ---------------------------------------
#
# 07 S1.1: normalise() is "a pure function of (payload, resolver snapshot). No network, no clock, no
# randomness." The timestamp arrives on the Payload, the entity lookup on the resolver, and the
# crosswalk is a committed file read once and passed in. Two calls on the same inputs return equal
# results, and tests/ingest/test_hf_hub_normalise.py runs it with the clock, the network and the
# random module made to raise.
#
# What it writes. One discovery candidate per payload, at data/_discovery/hf-hub/<candidate_id>.yaml
# in 06 S1.1's shape, and never a field of data/benchmarks/: 02 S11 rule 3, "no facet value is written
# to data/ by a machine". Facts the source states verbatim (ids, URLs, the licence tag, arXiv ids, the
# Papers with Code id) go in `identity`, as join keys. Everything interpretive -- every facet, access,
# lifecycle, submission process, judge -- is a `_suggested` entry carrying the tag it came from, its
# candidates and the 12.8% tag-density caveat, for a curator to confirm or discard.
#
# Spaces are mapped through taxonomy/crosswalks/hf-tags.yaml. Datasets are mapped by 06 S3.2's
# dataset-side rows (license:, arxiv:, paperswithcode_id, gated, disabled, the Croissant URL); the
# crosswalk is a Space-tag crosswalk, and its namespaces are not applied to dataset tags. Dropped, per
# 06 S3.2: siblings (file lists), and the counters (downloads, likes), which are the metrics/ series's
# and not a candidate's. A Space tag in a namespace the crosswalk does not declare is an Unresolved
# (06 S3.2: a renamed namespace "must stop rather than fall back to free-text matching"), never a hint.
#
# Resolution. A dataset id is looked up as a Benchmark (external_ids.huggingface is step 1 of
# ingest/resolve.py), a Space id as a Leaderboard. An id nothing resolves is an Unresolved, and its
# candidate's entity_id stays None: the adapter never mints an entity (04 S10, 07 S1.1).

CROSSWALK = os.path.join(ROOT, 'taxonomy', 'crosswalks', 'hf-tags.yaml')
DISCOVERY = 'data/_discovery/hf-hub'
SPACE_TAG = 'hf_space_tag'
DATASET_FIELD = 'hf_dataset_metadata'
FREE = '_free'

# 06 S9.3: "Carry each dataset's own license: tag through into our record." Its class, by the HF tag,
# for the 04 S9 firewall. Anything not listed is `unlicensed`, so 06 S1.2's veto applies until a person
# classes it: a guessed class would let a restrictive licence through.
LICENCE_CLASSES = {
    'permissive-attribution': ('mit', 'apache-2.0', 'bsd', 'bsd-2-clause', 'bsd-3-clause', 'cc-by-4.0',
                               'cc-by-3.0', 'cc-by-2.0', 'cc0-1.0', 'odc-by', 'pddl', 'unlicense'),
    'share-alike': ('cc-by-sa-4.0', 'cc-by-sa-3.0', 'odbl', 'gpl-3.0', 'gpl-2.0', 'lgpl-3.0', 'agpl-3.0'),
    'non-commercial': ('cc-by-nc-4.0', 'cc-by-nc-sa-4.0', 'cc-by-nc-nd-4.0', 'cc-by-nc-2.0', 'cc-by-nc-3.0',
                       'cc-by-nc-sa-3.0'),
    'no-redistribution': ('cc-by-nd-4.0',),
}
LICENCE_CLASS_OF = {tag: cls for cls, tags in LICENCE_CLASSES.items() for tag in tags}

# 06 S3.2's dataset flags, mapped onto the vocabulary terms that exist (data.access has no
# `credentialed`, lifecycle no `withdrawn`; these are the nearest, and a curator chooses).
GATED_CANDIDATES = ['gated-registration', 'credentialed-dua']
DISABLED_CANDIDATES = ['retracted', 'deprecated']


def load_crosswalk(path=CROSSWALK):
    """taxonomy/crosswalks/hf-tags.yaml, read once and passed to normalise(), which reads no file."""
    import yaml
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def candidate_id(source_key):
    """Deterministic, from the source's own key: `space:open-llm/board` -> cand-hf-space-open-llm-board.
    A discovery candidate's id, not an entity id: an entity is named by a person on promotion."""
    kind, ident = source_key.split(':', 1)
    return 'cand-hf-%s-%s' % (kind, _slug(ident.replace('/', '--')))


def languages(value, rule):
    """The crosswalk's `normalise.language`: split, trim, casefold, alias, drop non-languages, title."""
    out = []
    for part in value.split(rule['split_on']):
        v = part.strip().casefold()
        v = rule['aliases'].get(v, v)                       # get-default: an unaliased value is itself
        if v and v not in rule['not_a_language']:
            out.append(v.title() if rule['emit'] == 'title' else v)
    return out


def _field(ours):
    """`Benchmark.domain.primary` -> (`Benchmark`, `domain.primary`)."""
    entity, _, path = ours.partition('.')
    return entity, path


def space_hints(tags, xwalk):
    """(suggestions, arxiv ids, undeclared namespaces) for one Space's tags, through the crosswalk."""
    rows = {}
    for r in xwalk['rows']:
        rows.setdefault(r['tag'], []).append(r)
    namespaces, caveat = xwalk['namespaces'], xwalk['caveats']['hf-tag-density']
    out, arxiv, undeclared = [], [], []
    for tag in tags:
        ns, val = tag.split(':', 1) if ':' in tag else (FREE, tag)
        spec = namespaces.get(ns)                           # get-default: an undeclared namespace is reported below
        if spec is None:
            undeclared.append(tag)
            continue
        if spec['use'] == 'drop':
            continue
        if spec['use'] == 'match-only':
            if ns == 'arxiv':
                arxiv.append(val)
            continue
        hit = rows.get(tag) or rows.get('%s:*' % ns) or []  # get-default: no row is the unlisted case below
        if not hit:
            if ns == FREE and (spec['unlisted'] == 'drop' or tag in spec['drop']):
                continue
            if spec['unlisted'] == 'hint-by-rule':
                hit = [{'ours': o, 'value': v} for o in spec['ours'] for v in languages(val, xwalk['normalise'][spec['normalise']])]
            else:                                           # hint-without-candidate: the tag verbatim
                hit = [{'ours': o, 'candidates': []} for o in spec['ours']]
        for r in hit:
            entity, path = _field(r['ours'])
            s = {'field': path, 'entity': entity, 'tag': tag}
            if 'value' in r:
                s['value'] = r['value']
            else:
                s['candidates'] = list(r.get('candidates') or [])   # get-default: a row may name none
            if r.get('value_kind'):                                  # get-default: optional on a row
                s['value_kind'] = r['value_kind']
            s.update({'source': SPACE_TAG, 'caveat': 'hf-tag-density', 'density': caveat['density']})
            out.append(s)
    return out, arxiv, undeclared


def dataset_facts(doc):
    """(identity facts, suggestions) from a dataset detail payload, by 06 S3.2's dataset-side rows."""
    tags = doc['tags']
    licence = sorted({t.split(':', 1)[1] for t in tags if t.startswith('license:')})
    facts = {
        'arxiv_ids': sorted({t.split(':', 1)[1] for t in tags if t.startswith('arxiv:')}),
        'licence': licence,                                  # verbatim; 06 S9.3
        'papers_with_code': doc.get('paperswithcode_id'),    # get-default: absent on most datasets
    }
    hints = []
    if doc['gated']:
        hints.append({'field': 'data.access', 'entity': 'Benchmark', 'observed': 'gated: %s' % doc['gated'],
                      'candidates': list(GATED_CANDIDATES), 'source': DATASET_FIELD})
    if doc['disabled']:
        hints.append({'field': 'lifecycle', 'entity': 'Benchmark', 'observed': 'disabled: true',
                      'candidates': list(DISABLED_CANDIDATES), 'source': DATASET_FIELD})
    card = doc.get('cardData') or {}                         # get-default: a dataset may have no card
    if isinstance(card, dict) and card.get('pretty_name'):  # get-default: as above
        hints.append({'field': 'name', 'entity': 'Benchmark', 'value': str(card['pretty_name']),
                      'source': DATASET_FIELD, 'note': '06 S3.2: cardData is author prose, suggested only'})
    return facts, hints


def licence_class(licences):
    """The firewall class of a record's licence tags: the most restrictive one, or `unlicensed`."""
    order = ['permissive-attribution', 'share-alike', 'non-commercial', 'no-redistribution', 'unlicensed']
    classes = [LICENCE_CLASS_OF.get(l.casefold(), 'unlicensed') for l in licences] or ['unlicensed']  # get-default: unknown is unlicensed
    return max(classes, key=order.index)


def normalise(payload, resolvers, xwalk):
    """(drafts, unresolved) for one Payload. Pure: no clock, no network, no randomness, no file read.

    `resolvers` maps an entity kind ('benchmark', 'leaderboard') to an object whose resolve(raw)
    returns something with an `entity` ('kind:id' or None), as ingest/resolve.py's Index does."""
    from ingest.adapters.base import Draft, Unresolved
    c, doc = payload.candidate, payload.doc
    kind, ident = c.source_key.split(':', 1)
    if doc is None or doc.get('id') != ident:
        raise SchemaDrift('%s: the payload names %r' % (c.source_key, None if doc is None else doc.get('id')))
    fetched = iso(payload.fetched_at)
    unresolved, identity = [], {'hf_id': ident, 'url': c.url}
    if kind == 'space':
        hints, arxiv, undeclared = space_hints(doc['tags'], xwalk)
        identity['arxiv_ids'] = sorted(set(arxiv))
        target, licences = 'leaderboard', []
        for tag in undeclared:
            unresolved.append(Unresolved(
                source_key=c.source_key, field='tags', observed=tag, reason='out-of-band',
                human_task='Space tag %r is in a namespace taxonomy/crosswalks/hf-tags.yaml does not declare. '
                           'Declare the namespace (with a row if it maps) or mark it drop; the adapter does not '
                           'guess at an undeclared namespace (06 S3.2).' % tag))
    else:
        facts, hints = dataset_facts(doc)
        identity.update(facts)
        identity['croissant_url'] = c.hint.get('croissant_url')        # get-default: a dataset hint carries it
        target, licences = 'benchmark', facts['licence']
    for h in hints:
        h.update({'adapter': NAME, 'adapter_version': VERSION, 'source_url': c.url, 'fetched_at': fetched})

    resolver = resolvers.get(target)                                    # get-default: a kind with no resolver resolves nothing
    hit = resolver.resolve(ident).entity if resolver is not None else None
    if hit is None:
        unresolved.append(Unresolved(
            source_key=c.source_key, field='id', observed=ident, reason='no-match',
            human_task='No %s resolves %r. If it is one we hold, add the id to its external_ids (a dataset: '
                       'external_ids.huggingface) or an alias in data/aliases/; if it is new, promote the '
                       'discovery candidate. Nothing was created (04 S10).' % (target, ident)))
    cid = candidate_id(c.source_key)
    record = {
        'candidate_id': cid,
        'discovered_via': NAME,
        'discovered_at': fetched,
        'identity': dict(identity, resolves_to=hit),
        '_suggested': hints,
    }
    ingestion = {
        'batch': 'ingest-%s-%s' % (NAME, payload.fetched_at.strftime('%Y%m%d')),
        'source_adapter': NAME, 'adapter_version': VERSION,
        'source_record_id': c.source_key, 'last_seen_upstream': payload.fetched_at.date().isoformat(),
        'source_url': c.url, 'source_licence': ', '.join(licences) or 'unstated',
        'licence_class': licence_class(licences),
        'source_attribution': 'Hugging Face Hub, %s' % c.url,
        'ingested_at': fetched, 'sha256_normalised': payload.sha256_normalised,
    }
    draft = Draft(entity_type=target, entity_id=hit.split(':', 1)[1] if hit else None,
                  path=Path(DISCOVERY) / (cid + '.yaml'), payload=record,
                  change_class='field-change' if hit else 'new', ingestion=ingestion,
                  confidence=1.0,          # identity is copied verbatim; every interpretive value is a suggestion
                  labels=['source:hf-hub', 'discovery'])
    return [draft], unresolved


def run(adapter, state, limit=None):
    """discover() then fetch() for each candidate; returns (report, payloads). State is updated in
    memory, including the run bookkeeping; saving it is the caller's decision."""
    started = adapter.now()
    payloads, errors, seen, status = [], [], 0, None
    try:
        for c in adapter.discover(state):
            if limit is not None and seen >= limit:
                adapter.notes.append('--limit %d reached' % limit)
                status = 'partial'
                break
            seen += 1
            p = adapter.fetch(c, state)
            if p is not None:
                payloads.append(p)
    except (SchemaDrift, FixtureMiss, NetworkForbidden) as e:
        status, errors = 'hard-fail', ['%s: %s' % (type(e).__name__, e)]
    except Capped as e:
        status, errors = 'capped', [str(e)]
    except (backoff.SoftFail, urllib.error.URLError, TimeoutError, ConnectionError) as e:
        status, errors = 'soft-fail', ['%s: %s' % (type(e).__name__, e)]
    status = status or ('ok' if payloads else 'no-change')
    finished = adapter.now()
    state['last_run'] = iso(finished)
    if status in ('ok', 'no-change', 'partial', 'capped'):
        state['last_success'] = iso(finished)
        state['consecutive_failures'] = 0
        if payloads:
            state['last_change'] = iso(finished)
        if status in ('ok', 'no-change'):
            state['yield_history'] = (state['yield_history'] + [seen])[-8:]
    else:
        state['consecutive_failures'] += 1
    report = {
        'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(started), 'finished_at': iso(finished),
        'status': status, 'requests': adapter.requests,
        'http_codes': {str(k): v for k, v in sorted(adapter.http_codes.items())},
        'candidates_seen': seen, 'payloads_fetched': len(payloads),
        'payloads_from_cache': adapter.stats['payloads_from_cache'],
        'short_circuited': adapter.stats['short_circuited'], 'not_modified': adapter.stats['not_modified'],
        'unchanged': adapter.stats['unchanged'], 'duplicates': adapter.stats['duplicates'],
        'fixture_missing': len(adapter.fixture_missing), 'errors': errors, 'notes': adapter.notes,
    }
    return report, payloads


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--fixture', metavar='DIR', help='replay recorded responses; no network')
    ap.add_argument('--no-network', action='store_true', help='fail if anything reaches for the network')
    ap.add_argument('--state', help='state file (default ingest/raw/hf-hub[-fixture]/state.json, gitignored; '
                                    'the committed %s only when named here)' % os.path.relpath(STATE, ROOT))
    ap.add_argument('--cache', help='request cache directory (default ingest/raw/hf-hub[-fixture]/cache)')
    ap.add_argument('--limit', type=int, help='stop after N candidates')
    ap.add_argument('--max-requests', type=int, default=MAX_REQUESTS)
    ap.add_argument('--dry-run', action='store_true', help='report only; do not save the state')
    a = ap.parse_args(argv)
    work = os.path.join(RAW, 'hf-hub-fixture' if a.fixture else 'hf-hub')
    state_path = a.state or os.path.join(work, 'state.json')
    if a.fixture:
        transport = FixtureTransport(a.fixture)
    elif a.no_network:
        transport = NoNetwork()
    else:
        transport = NetworkTransport(token=os.environ.get('HF_TOKEN') or None)
    adapter = HfHub(transport, RequestCache(a.cache or os.path.join(work, 'cache')), max_requests=a.max_requests)
    state = load_state(state_path)
    report, _ = run(adapter, state, limit=a.limit)
    if not a.dry_run:
        save_state(state_path, state)
    print(json.dumps(report, indent=2))
    return EXIT[report['status']]


if __name__ == '__main__':
    sys.exit(main())
