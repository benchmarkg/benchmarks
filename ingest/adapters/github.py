#!/usr/bin/env python3
"""The GitHub metadata adapter (P5-S5-T01; 06 S3.3, 07 S4.1, S1.5, S10).

    bench ingest github --dry-run                          # live: GH_API_TOKEN from the environment
    bench ingest github --dry-run --fixture tests/ingest/fixtures/github

What it asks. For every repository a curated benchmark names as its `repository` (one candidate per repository:
SWE-bench and SWE-bench Verified share one), three conditional GETs against api.github.com, each with the ETag
the last run saw in If-None-Match (07 S4.1: authorised 304s do not count against the 5,000/hr limit -- the claim
scripts/probe_conditional_requests.py exists to check):

    /repos/{owner}/{repo}                       the repository
    /repos/{owner}/{repo}/contents/              the root listing: whether CITATION.cff exists, and its blob sha
    /repos/{owner}/{repo}/releases?per_page=30   release tags: BenchmarkVersion candidates

and /repos/{owner}/{repo}/contents/CITATION.cff -- the one place a repo states how it wants to be cited -- only
when the listing shows one whose blob sha is new. Asking for the file directly would cost a request every run on
every repository without one: a 404 carries no ETag, so it can never 304. A run where all three answer 304 for a
repository fetches nothing for it. README prose is never requested: 06
S3.3 stores README-derived facts, never README text, because the prose is unlicensed by default.

What it maps (06 S3.3's table), into one discovery candidate per repository under data/_discovery/github/, in
06 S1.1's shape (candidate_id, discovered_via, discovered_at, identity, _suggested as a list) -- the shape the
gates hold that tree to:

    license.spdx_id        identity.code_licence   `null` is a value: the repo declares no licence
    homepage               identity.homepage
    CITATION.cff           identity.citation_cff   its URL, blob sha, and the title, DOI, version and date it states
    release tags           identity.release_tags   tag, date, URL; release-note prose is dropped
    pushed_at, archived    identity.liveness       the observable behind lifecycle review (P5-S7-T01 records it)
    stargazers_count,
    forks_count,
    subscribers_count      identity.adoption       the metrics/ series, snapshotted weekly, never star history
    created_at             _suggested released     a candidate only: a repo predates a release as often as not
    topics[]               _suggested topics       facet hints

Change classes. volatile_fields (07 S1.5: "pushed_at on list endpoints, stargazers_count, forks_count", and
subscribers_count, which moves the same way) are stripped before hashing, so a repository whose only change is
its counters is 'metrics-only': its observation is recorded and no curated field is proposed. Any other change
is 'field-change' ('new' the first time the adapter sees the repository).

A 404 on a catalogued repository is a signal, not an error (06 S3.3): "the benchmark's home disappeared, so it
raises a lifecycle review rather than being swallowed" -- an Unresolved item for each benchmark naming it, and an
observation with http_status 404. Rate-limit exhaustion (a 403 or 429 with X-RateLimit-Remaining 0) is a soft
fail the next run resumes; a 401, or any other 403, is a hard fail: the token was refused.

Every live request passes the fetcher's gate (ingest/policy.yaml: api.github.com at one request a second, 2,000 a
run). The token travels in the Authorization header, set inside the network transport and nowhere else.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.adapters.base import Adapter, Candidate, Draft, Payload, Unresolved, sha256_hex  # noqa: E402
from ingest.http import policy, ratelimit  # noqa: E402
from ingest.http.backoff import Response, SoftFail, retry  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

NAME = 'github'
VERSION = '0.1.0'
API = 'https://api.github.com'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
ACCEPT = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
VOLATILE_FIELDS = ('pushed_at', 'stargazers_count', 'forks_count', 'subscribers_count')
REPO_KEYS = ('full_name', 'html_url', 'homepage', 'license', 'topics', 'created_at', 'pushed_at', 'archived',
             'disabled', 'stargazers_count', 'forks_count', 'subscribers_count', 'default_branch')
RELEASES = 30
DISCOVERY = 'data/_discovery/github'
REPO_URL = re.compile(r'^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$')
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')


class RateLimited(SoftFail):
    """The core budget is spent: a soft fail, resumed next run (06 S3.3)."""


class Refused(Exception):
    """A 401, or a 403 that is not the rate limit: the token was refused. A hard fail."""


# ---- the transport ----------------------------------------------------------------------------------------------

class NetworkTransport:
    """GET over urllib under 07 S4.2's retry policy, behind the fetcher's gate. The token is added here only."""

    def __init__(self, token: str | None = None, timeout: int = 60, clock=time.monotonic, wall=time.time,
                 sleep=time.sleep, gate=None):
        self.token, self.timeout, self.clock, self.wall, self.sleep = token, timeout, clock, wall, sleep
        self.gate = gate or policy.gate()                # 07 S10.1: ingest/policy.yaml, robots.txt, no-collect
        self._not_before = 0.0

    def _once(self, url, headers):
        self.gate.admit(url)
        wait = self._not_before - self.clock()
        if wait > 0:
            self.sleep(wait)
        h = {'User-Agent': USER_AGENT, **ACCEPT, **headers}
        if self.token:
            h['Authorization'] = 'Bearer ' + self.token
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:              # urllib raises for 304 and 404 too
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        stated = ratelimit.wait_seconds(resp.status, resp.headers, now=self.wall()) or 0.0
        self._not_before = resp.received_at + min(stated, 60.0)
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, wall=self.wall, sleep=self.sleep)


def token_from_env() -> str | None:
    return os.environ.get('GH_API_TOKEN') or None        # get-default: a run without a token is the 60/hr budget


# ---- extraction: the facts we keep, never prose -----------------------------------------------------------------

def repo_facts(doc: dict) -> dict:
    out = {k: doc.get(k) for k in REPO_KEYS}             # get-default: GitHub omits some keys on some repos
    lic = doc.get('license')                              # get-default: absent when no licence is detected
    out['license'] = (lic or {}).get('spdx_id') if isinstance(lic, dict) else None
    out['topics'] = sorted(doc.get('topics') or [])       # get-default: as above
    return out


def citation_facts(doc: dict) -> dict:
    """CITATION.cff's identifying fields. The file is metadata a repository publishes to be cited by; what we keep
    is its URL, its blob sha (the change handle), and the title, DOI, version and date it states."""
    from ruamel.yaml import YAML
    text = base64.b64decode(doc.get('content') or '').decode('utf-8', 'replace')  # get-default: an empty file
    try:
        cff = YAML(typ='safe', pure=True).load(text) or {}
    except Exception:                                     # ruamel raises several unrelated types
        cff = {}
    cff = cff if isinstance(cff, dict) else {}
    pref = cff.get('preferred-citation') if isinstance(cff.get('preferred-citation'), dict) else {}  # get-default: optional in CFF
    pick = lambda k: (str(pref[k]) if pref.get(k) else str(cff[k]) if cff.get(k) else None)  # noqa: E731  get-default: every CFF key is optional
    doi = pick('doi') or next((str(i['value']) for i in (cff.get('identifiers') or [])  # get-default: optional in CFF
                               if isinstance(i, dict) and i.get('type') == 'doi' and i.get('value')), None)  # get-default: as above
    return {'path': doc.get('path'), 'url': doc.get('html_url'), 'sha': doc.get('sha'),  # get-default: as GitHub sends them
            'title': pick('title'), 'doi': doi, 'version': pick('version'),
            'date_released': pick('date-released'), 'parsed': bool(cff)}


def citation_entry(listing: list) -> dict | None:
    """CITATION.cff's entry in a repository's root listing ({path, sha}), or None when the repository has none."""
    for e in listing if isinstance(listing, list) else []:
        if isinstance(e, dict) and e.get('type') == 'file' and str(e.get('name')).lower() == 'citation.cff':  # get-default: as GitHub sends them
            return {'path': e['path'], 'sha': e['sha']}
    return None


def release_facts(docs: list) -> list[dict]:
    """Release tags, newest first, drafts excluded; the release notes (prose) are dropped."""
    out = [{'tag': r.get('tag_name'), 'published_at': r.get('published_at'), 'url': r.get('html_url'),  # get-default: as GitHub sends them
            'prerelease': bool(r.get('prerelease'))}                                                   # get-default: as above
           for r in docs if isinstance(r, dict) and not r.get('draft')]                                # get-default: as above
    return sorted(out, key=lambda r: (r['published_at'] or '', r['tag'] or ''), reverse=True)


def strip_volatile(doc: dict) -> dict:
    repo = doc.get('repo')                                # get-default: None on a 404
    kept = {k: v for k, v in (repo or {}).items() if k not in VOLATILE_FIELDS}
    return {**doc, 'repo': kept if repo is not None else None}


def sha256_normalised(doc: dict) -> str:
    """07 S1.5: the volatile fields removed, the rest as JSON with sorted keys and no whitespace."""
    clean = {k: v for k, v in strip_volatile(doc).items() if not k.startswith('_')}
    return sha256_hex(json.dumps(clean, sort_keys=True, separators=(',', ':'), ensure_ascii=False))


# ---- the adapter ------------------------------------------------------------------------------------------------

def catalogued(root: str = ROOT) -> dict[str, list[tuple[str, str]]]:
    """{owner/repo: [(benchmark id, its path)]} for every curated benchmark whose `repository` is on GitHub."""
    from schema.taxonomy import read_yaml
    import glob
    out: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)).startswith('_'):
            continue
        rec = read_yaml(path)
        m = REPO_URL.match(str(rec.get('repository') or ''))   # get-default: `repository` is optional
        if m:
            key = '%s/%s' % m.groups()
            out.setdefault(key, []).append((rec['id'], os.path.relpath(path, root).replace(os.sep, '/')))
    return out


def new_state() -> dict:
    return {'adapter': NAME, 'etags': {}, 'hashes': {}, 'cff': {}, 'checkpoint': None}


class GitHub(Adapter):
    name = NAME
    version = VERSION
    licence = 'https://docs.github.com/en/site-policy/github-terms/github-terms-of-service'
    licence_class = 'unlicensed'          # repository metadata under GitHub's terms, not an open licence (as hf-hub)
    raw_retainable = False
    attribution = 'GitHub'
    expected_yield = (0, 200)             # seed: most weekly runs are 304s and metrics-only (07 S4.1)
    volatile_fields = VOLATILE_FIELDS
    tier = 1                              # 06 S8.1: the liveness signal every benchmark's lifecycle review reads

    def __init__(self, transport, root: str = ROOT, repos: dict | None = None, now=None):
        self.transport, self.root = transport, root
        self.repos = repos if repos is not None else catalogued(root)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.http_codes: Counter = Counter()
        self.remaining: list[int] = []                # X-RateLimit-Remaining, response by response
        self.charged: set[str] = set()                # repositories whose 304s were charged (see run())

    def discover(self, state):
        for key in sorted(self.repos):
            yield Candidate(key, 'benchmark', 'https://github.com/' + key,
                            {'benchmarks': [b for b, _ in self.repos[key]], 'paths': [p for _, p in self.repos[key]]})

    def _get(self, url: str, state: dict, extract):
        """(status, extract(body) or None, served from the ETag cache). Only what `extract` keeps is cached."""
        cached = state['etags'].get(url)                # get-default: a URL not seen before has no ETag
        headers = {'If-None-Match': cached['etag']} if cached else {}
        r = self.transport.get(url, headers)            # get-default: an HTTP GET with request headers
        self.http_codes[r.status] += 1
        left = header(r.headers, 'X-RateLimit-Remaining')
        if left is not None and str(left).isdigit():
            if r.status == 304 and self.remaining and int(left) < self.remaining[-1]:
                self.charged.add(url.split('/repos/', 1)[1].split('/contents', 1)[0].split('/releases', 1)[0])
            self.remaining.append(int(left))
        if r.status == 304 and cached:
            return 304, cached['doc'], True
        if r.status == 200:
            body = json.loads(r.body)
            doc = extract(body)
            etag = header(r.headers, 'ETag')
            if etag:
                state['etags'][url] = {'etag': etag, 'doc': doc}
            return 200, doc, False
        if r.status == 404:
            state['etags'].pop(url, None)
            return 404, None, False
        if r.status in (403, 429) and (left == '0' or r.status == 429):
            raise RateLimited('HTTP %d, X-RateLimit-Remaining %s' % (r.status, left), r, 1)
        if r.status in (401, 403):
            raise Refused('HTTP %d from %s: the token was refused or lacks access' % (r.status, url))
        raise Refused('HTTP %d from %s' % (r.status, url))

    def fetch(self, candidate, state):
        key = candidate.source_key
        base = '%s/repos/%s' % (API, key)
        status, repo, c1 = self._get(base, state, repo_facts)
        fetched_at = self.now()
        if status == 404:
            doc = {'repo': None, 'citation_cff': None, 'releases': [], '_status': 404,
                   '_previous_sha256': state['hashes'].get(key)}          # get-default: never seen before
            return Payload(candidate, b'', 'application/json', 404, fetched_at, None, None,
                           sha256_normalised(doc), False, doc=doc)
        # The root listing, not CITATION.cff itself: a missing file is a 404 with no ETag, re-asked and charged every
        # run, while the listing 304s like everything else. The file is read only when its blob sha changes.
        _, listing, c2 = self._get(base + '/contents/', state, citation_entry)
        cff = None
        if listing is not None:
            known = state['cff'].get(key)               # get-default: a file not read before
            if known and known['sha'] == listing['sha']:
                cff = known['facts']
            else:
                _, cff, _ = self._get('%s/contents/%s' % (base, listing['path']), state, citation_facts)
                state['etags'].pop('%s/contents/%s' % (base, listing['path']), None)   # keyed by sha, not ETag
                state['cff'][key] = {'sha': listing['sha'], 'facts': cff}
                c2 = False
        else:
            state['cff'].pop(key, None)
        _, rels, c3 = self._get('%s/releases?per_page=%d' % (base, RELEASES), state, release_facts)
        if c1 and c2 and c3:
            return None                                  # all three 304: nothing to normalise, nothing changed
        doc = {'repo': repo, 'citation_cff': cff, 'releases': rels or [],
               '_status': 200, '_previous_sha256': state['hashes'].get(key)}  # get-default: as above
        sha = sha256_normalised(doc)
        state['hashes'][key] = sha
        return Payload(candidate, b'', 'application/json', 200, fetched_at, None, None, sha, c1, doc=doc)

    def normalise(self, payload, resolver=None):
        return normalise(payload)


def observation(payload: Payload) -> dict:
    """The metrics/ line for one repository on one day: liveness and adoption, a 404 included."""
    repo = payload.doc['repo'] or {}
    return {'observed_on': payload.fetched_at.strftime('%Y-%m-%d'), 'repo': payload.candidate.source_key,
            'benchmarks': list(payload.candidate.hint['benchmarks']), 'http_status': payload.http_status,
            'pushed_at': repo.get('pushed_at'), 'archived': repo.get('archived'),          # get-default: absent on a 404
            'stargazers_count': repo.get('stargazers_count'), 'forks_count': repo.get('forks_count'),  # get-default: as above
            'subscribers_count': repo.get('subscribers_count')}                             # get-default: as above


def normalise(payload: Payload) -> tuple[list[Draft], list[Unresolved]]:
    """A pure function of the payload: one review document per repository, or a lifecycle review on a 404."""
    c, doc = payload.candidate, payload.doc
    key = c.source_key
    if payload.http_status == 404:
        return [], [Unresolved(
            key, 'repository', c.url, 'out-of-band',
            human_task=('%s returned 404, so the repository %s names has gone. Review Benchmark.lifecycle '
                        '(06 S3.3: a 404 on a catalogued repository is a signal, not an error).' % (c.url, bid)))
            for bid in c.hint['benchmarks']]
    repo = doc['repo']
    previous = doc['_previous_sha256']
    change = 'new' if previous is None else 'metrics-only' if previous == payload.sha256_normalised else 'field-change'
    homepage = repo['homepage'] or None                   # '' is GitHub's way of saying none
    fetched = payload.fetched_at.strftime('%Y-%m-%dT%H:%M:%SZ')
    source_url = '%s/repos/%s' % (API, key)

    def suggest(field, value, rationale):
        return {'field': field, 'value': value, 'adapter': NAME, 'adapter_version': VERSION, 'source_url': source_url,
                'fetched_at': fetched, 'confidence': 0.3, 'rationale': rationale}
    body = {
        'candidate_id': candidate_id(key),
        'discovered_via': NAME,
        'discovered_at': fetched,
        'identity': {
            'repository': c.url,
            'benchmarks': list(c.hint['benchmarks']),
            'code_licence': repo['license'],
            'homepage': homepage,
            'citation_cff': doc['citation_cff'],
            'release_tags': doc['releases'],
            'liveness': {'pushed_at': repo['pushed_at'], 'archived': repo['archived'], 'disabled': repo['disabled']},
            'adoption': {k: repo[k] for k in ('stargazers_count', 'forks_count', 'subscribers_count')},
        },
        '_suggested': [
            suggest('released', (repo['created_at'] or '')[:10] or None,
                    '06 S3.3: created_at is a release-date candidate only; a repo predates a release as often as not'),
            suggest('topics', repo['topics'], '06 S3.3: topics are facet hints'),
        ],
    }
    ingestion = {'adapter': NAME, 'adapter_version': VERSION, 'source_url': source_url, 'fetched_at': fetched,
                 'sha256_normalised': payload.sha256_normalised}
    path = Path(DISCOVERY) / ('%s.yaml' % body['candidate_id'])
    return [Draft('benchmark', None, path, body, change, ingestion, 1.0, labels=['ingest:github'])], []


def candidate_id(key: str) -> str:
    """SWE-bench/SWE-bench -> cand-gh-swe-bench--swe-bench: a discovery candidate's id, not an entity id."""
    owner, repo = key.lower().split('/', 1)
    return 'cand-gh-%s--%s' % (re.sub(r'[^a-z0-9]+', '-', owner).strip('-'), re.sub(r'[^a-z0-9]+', '-', repo).strip('-'))


# ---- one dry run ------------------------------------------------------------------------------------------------

def run(adapter: GitHub, state: dict | None = None, *, limit: int | None = None) -> dict:
    """Discover, fetch and normalise every catalogued repository. Writes nothing; returns the report."""
    state = state if state is not None else new_state()
    now = adapter.now
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': now().strftime('%Y-%m-%dT%H:%M:%SZ'),
              'status': 'ok', 'candidates_seen': 0, 'drafts': {k: 0 for k in CHANGE_CLASSES}, 'unresolved': 0,
              'errors': [], 'snapshot': None, 'proposals': [], 'observations': [], 'documents': [],
              'lifecycle_reviews': [], 'allowance': {}}
    for i, cand in enumerate(adapter.discover(state)):
        if limit is not None and i >= limit:
            break
        report['candidates_seen'] += 1
        try:
            payload = adapter.fetch(cand, state)
        except SoftFail as e:
            report['status'] = 'soft-fail'
            report['errors'].append('%s: %s; the next run resumes' % (cand.source_key, e))
            break
        except Refused as e:
            report['status'] = 'hard-fail'
            report['errors'].append(str(e))
            break
        if payload is None:
            report['drafts']['no-change'] += 1
            continue
        report['observations'].append(observation(payload))
        drafts, unresolved = adapter.normalise(payload)
        for d in drafts:
            report['drafts'][d.change_class] += 1
            report['documents'].append({'path': str(d.path).replace(os.sep, '/'), 'change_class': d.change_class,
                                        **d.payload})
            if d.change_class != 'metrics-only':
                report['proposals'].append('%s (%s): %s, licence %s' % (cand.source_key, ', '.join(cand.hint['benchmarks']),
                                                                        d.change_class, d.payload['identity']['code_licence']))
        for u in unresolved:
            report['unresolved'] += 1
            report['lifecycle_reviews'].append(u.human_task)
            report['proposals'].append('lifecycle review: ' + u.human_task)
    if adapter.remaining:
        report['allowance'] = {'x_ratelimit_remaining_first': adapter.remaining[0],
                               'x_ratelimit_remaining_last': adapter.remaining[-1]}
    # 07 S10's budget assumes a 304 is free, and for nearly every repository it is. Not for all: on 2026-10-09
    # every 304 from openai/preparedness was charged while openai/simple-evals' were not. A repository whose
    # Remaining fell on a 304 is named here, so the budget counts it instead of assuming it free.
    report['charged_304s'] = sorted(adapter.charged)
    report['proposals'] += ['%s: its 304s were charged against the rate limit (07 S10 assumes them free)' % k
                            for k in report['charged_304s']]
    report['http_codes'] = {str(k): v for k, v in sorted(adapter.http_codes.items())}
    if report['status'] == 'ok' and not any(report['drafts'][k] for k in CHANGE_CLASSES if k != 'no-change') \
            and not report['unresolved']:
        report['status'] = 'no-change'
    report['finished_at'] = now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--fixture', help='recorded responses in place of the network')
    ap.add_argument('--limit', type=int)
    a = ap.parse_args(argv)
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport(token_from_env())
    report = run(GitHub(transport), limit=a.limit)
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}, indent=2))
    return {'ok': 0, 'no-change': 0, 'hard-fail': 1, 'soft-fail': 4}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
