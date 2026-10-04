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
crash between fetch and write can never mark a record as seen. Nothing consumes them yet --
normalise() is P5-S1-T04's -- so the CLI saves to ingest/raw/hf-hub[-fixture]/state.json, which is
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

from ingest.adapters.base import Candidate, Payload  # noqa: E402,F401  (07 S1.1's types; tests import them from here)
from ingest.http import backoff, ratelimit  # noqa: E402
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


class FixtureMiss(Exception):
    """The fixture set holds no response for this URL."""


class NetworkForbidden(Exception):
    """--no-network, and something reached for the network."""


class Capped(Exception):
    """The run's request budget is spent."""


# ---- headers ----------------------------------------------------------------------------------

def header_values(headers, name):
    items = headers.items() if hasattr(headers, 'items') else headers
    return [v for k, v in items if k.lower() == name.lower()]


def header(headers, name):
    vals = header_values(headers, name)
    return vals[0] if vals else None


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


def etag_matches(if_none_match, etag):
    """RFC 9110 S13.1.2: If-None-Match uses the weak comparison -- W/ is ignored on both sides."""
    if not if_none_match or not etag:
        return False
    if if_none_match.strip() == '*':
        return True
    weak = lambda t: t.strip()[2:] if t.strip().startswith('W/') else t.strip()  # noqa: E731
    return any(weak(t) == weak(etag) for t in re.findall(r'(?:W/)?"[^"]*"', if_none_match))


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

class FixtureTransport:
    """Recorded responses, keyed by the URL each `.headers.json` names. No network code at all."""

    def __init__(self, directory):
        self.index = {}
        for n in sorted(os.listdir(directory)):
            if n.endswith('.headers.json'):
                with open(os.path.join(directory, n), encoding='utf-8') as f:
                    meta = json.load(f)
                self.index[meta['url']] = (os.path.join(directory, n[:-len('.headers.json')]), meta)
        if not self.index:
            raise FileNotFoundError('no <name>.headers.json fixtures in %s' % directory)
        self.requests = []

    def get(self, url, headers):
        self.requests.append((url, dict(headers)))
        if url not in self.index:
            raise FixtureMiss(url)
        path, meta = self.index[url]
        if etag_matches(header(headers, 'If-None-Match'), header(meta['headers'], 'ETag')):
            kept = [(k, v) for k, v in meta['headers'] if k.lower() not in ('content-length', 'content-type')]
            return Response(304, kept, b'')
        with open(path, 'rb') as f:
            return Response(meta['status'], meta['headers'], f.read())


class NoNetwork:
    def get(self, url, headers):
        raise NetworkForbidden(url)


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
