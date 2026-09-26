"""`bench check-links [--changed-only] [--archive-missing] [--timeout 20] [--format text|json]`
(P0-S5-T08; 05 S3, 06 S7).

05 S3: "HTTP-check every `url` in the touched files; report rot; optionally queue archiving."

What is checked. Every whole-string http(s) value in every YAML file under data/ -- `url`,
`homepage`, `repository`, the `*_url` fields and any other -- except Wayback captures themselves
(an `archive_url`, or anything on web.archive.org): those are the archived copies a dead link falls
back to, and checking them would hammer the one host 06 S9.6 most needs us to be polite to. Each
distinct URL is requested once however many records cite it. `--changed-only` narrows the files to
those changed against the merge base with origin/main, as `bench validate --changed-only` does.

How. 06 S7.2: "`GET` with `Range: bytes=0-32767` ... Never `HEAD`" -- many servers answer HEAD
with 405. Redirects are followed by hand, up to ten, so the chain is known; requests are sequential
and spaced per host; a 5xx or a network error gets one retry.

The classes, each a fact about the link:

  live           2xx with no redirect
  redirected     2xx after a redirect within the same site (www., http->https, a subdomain), or
                 from a resolver whose job is to redirect (doi.org, hdl.handle.net, ...)
  dead           4xx, 5xx after the retry, DNS or connection failure, too many redirects, or a
                 redirect to an unrelated host (06 S7.2: the host changed hands or the page moved)
  archived-only  dead, but a capture exists: the record's own `archive_url` beside the URL, or
                 CDX's newest capture. The citation survives; the record needs a lifecycle review
  unknown        429: the server declined to answer, which says nothing about the link

Exit status: 1 on any `dead` link. `archived-only` is reported and does not fail -- its canonical
reference is the capture, which is what 06 S7.2 says to keep -- and `unknown` does not either.

`--archive-missing`: every non-DOI Source in scope without an `archive_url` goes through
tools/archive.py's `ensure` (cache, then CDX, then an SPN2 request with if_not_archived_within=30d),
and the run exits 1 while any remains unarchived in its record: a capture CDX found or SPN2 is making
still has to be written into the record, which is the nightly archiver's job (ingest/archive_sources.py),
not a link checker's. A DOI Source is exempt (04 S12). check-links never writes data/.

The cache (ingest/state/links.json, gitignored). A live or redirected resolution and every capture
outcome worth remembering are kept for the 30-day window, so a re-run inside it costs no request;
a dead link is never cached, because a link that died should be re-checked the next time, not a
month later.

06 S7.2's `suspect` class (a 2xx soft-404 or an empty SPA shell) and its body-digest comparison
belong to the scheduled link-rot job (08 S3.5: Phase 5), not to this check.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from tools import archive

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'ingest', 'state', 'links.json')
URL = re.compile(r'^https?://\S+$')
RANGE = 'bytes=0-32767'
MAX_REDIRECTS = 10
REDIRECTING = frozenset({'doi.org', 'dx.doi.org', 'hdl.handle.net', 'w3id.org', 'purl.org', 'n2t.net'})
ARCHIVE_HOSTS = frozenset({'web.archive.org', 'archive.org'})
CLASSES = ('live', 'redirected', 'archived-only', 'dead', 'unknown')


@dataclass
class Link:
    path: str                   # root-relative file
    where: str                  # dotted location in the record
    url: str
    archive_url: str | None     # the capture recorded beside it, if any


@dataclass
class Response:
    status: int | None          # the final status; None when nothing came back
    final: str
    redirects: list[str] = field(default_factory=list)
    error: str | None = None


# ---- collecting ---------------------------------------------------------------------------------

def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or '').lower()


def _walk(x, where, path, out):
    if isinstance(x, dict):
        capture = x.get('archive_url')
        for k, v in x.items():
            at = '%s.%s' % (where, k) if where else str(k)
            if isinstance(v, str) and URL.match(v):
                if k != 'archive_url' and _host(v) not in ARCHIVE_HOSTS:
                    out.append(Link(path, at, v, capture if isinstance(capture, str) else None))
            else:
                _walk(v, at, path, out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            if isinstance(v, str) and URL.match(v):
                if _host(v) not in ARCHIVE_HOSTS:
                    out.append(Link(path, '%s[%d]' % (where, i), v, None))
            else:
                _walk(v, '%s[%d]' % (where, i), path, out)


def files(root: str, changed_only: bool = False) -> list[str]:
    from tools.validate import tiers
    found = [p for p in tiers.discover(root) if p.startswith('data/')]
    if changed_only:
        changed = tiers.changed_files(root)
        found = [p for p in found if p in changed]
    return found


def read(root: str, rel: str):
    from schema.taxonomy import read_yaml
    try:
        return read_yaml(os.path.join(root, rel))
    except Exception:           # ruamel raises several unrelated types; tier 1 reports the file
        return None


def collect(root: str, rels: list[str]) -> list[Link]:
    out: list[Link] = []
    for rel in rels:
        _walk(read(root, rel), '', rel, out)
    return out


# ---- resolving ----------------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None             # a 3xx then surfaces as an HTTPError, Location header and all


class Resolver:
    """GET with a Range header, redirects followed by hand, sequential and spaced per host."""

    def __init__(self, timeout: float = 20, spacing: float = 1.0, retry_after: float = 2.0):
        self.timeout, self.spacing, self.retry_after = timeout, spacing, retry_after
        self.requests = 0
        self._last: dict[str, float] = {}
        self._opener = urllib.request.build_opener(_NoRedirect)

    def _once(self, url: str, ranged: bool = True) -> tuple[int | None, str | None, str | None]:
        host = _host(url)
        wait = self._last.get(host, 0.0) + self.spacing - time.monotonic()  # get-default: a host not yet asked has no wait
        if wait > 0:
            time.sleep(wait)
        headers = {'User-Agent': archive.USER_AGENT, 'Accept': '*/*'}
        if ranged:
            headers['Range'] = RANGE
        self.requests += 1
        try:
            with self._opener.open(urllib.request.Request(url, headers=headers), timeout=self.timeout) as r:
                r.read(32768)
                return r.status, None, None
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Location'), None
        except (urllib.error.URLError, OSError, ValueError) as e:   # DNS, refused, reset, timeout, bad URL
            return None, None, ' '.join(str(getattr(e, 'reason', e)).split())[:200]
        finally:
            self._last[host] = time.monotonic()

    def _one(self, url):
        status, location, error = self._once(url)
        if status == 416:                       # a server that refuses the Range: ask for the page
            status, location, error = self._once(url, ranged=False)
        if status is None or status >= 500:
            time.sleep(self.retry_after)
            status, location, error = self._once(url)
        return status, location, error

    def get(self, url: str) -> Response:
        chain, cur = [], url
        for _ in range(MAX_REDIRECTS + 1):
            status, location, error = self._one(cur)
            if status in (301, 302, 303, 307, 308) and location:
                chain.append(cur)
                cur = urllib.parse.urljoin(cur, location)
                continue
            return Response(status, cur, chain, error)
        return Response(None, cur, chain, 'more than %d redirects' % MAX_REDIRECTS)


def _site(host: str) -> str:
    return '.'.join(host.removeprefix('www.').split('.')[-2:])


def classify(url: str, r: Response) -> tuple[str, str]:
    """(class, detail) for a response, before any archive is looked for."""
    if r.status == 429:
        return 'unknown', 'HTTP 429: the server declined to answer'
    if r.status is None:
        return 'dead', r.error or 'no response'
    if not 200 <= r.status < 300:
        return 'dead', 'HTTP %d%s' % (r.status, ' after %d redirect(s), at %s' % (len(r.redirects), r.final)
                                      if r.redirects else '')
    if not r.redirects:
        return 'live', 'HTTP %d' % r.status
    start, end = _host(url), _host(r.final)
    if _site(start) == _site(end) or start in REDIRECTING:
        return 'redirected', 'to %s' % r.final
    return 'dead', 'redirects to an unrelated host: %s' % r.final


# ---- the run ------------------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def default_resolver(timeout: float) -> Resolver:
    return Resolver(timeout)


def default_wayback():
    return archive.Wayback(os.environ.get('IA_SPN_KEY'), os.environ.get('IA_SPN_SECRET'))


def run(root: str = ROOT, changed_only: bool = False, archive_missing: bool = False, resolver=None,
        wayback=None, cache_path: str | bool | None = None, now: datetime | None = None, timeout: float = 20) -> dict:
    """One check. `cache_path` None means CACHE; False means no cache at all."""
    now = now or utcnow()
    cache_path = CACHE if cache_path is None else cache_path
    resolver = resolver or default_resolver(timeout)
    wayback = wayback or default_wayback()
    cache = archive.load_cache(cache_path) if cache_path else {'version': 1, 'resolved': {}, 'captures': {}}
    resolved = cache.setdefault('resolved', {})
    rels = files(root, changed_only)
    links = collect(root, rels)

    verdicts: dict[str, dict] = {}
    for url in dict.fromkeys(lk.url for lk in links):
        hit = resolved.get(url)
        if archive.fresh(hit, now):
            verdicts[url] = dict(hit, cached=True)
            continue
        r = resolver.get(url)
        cls, detail = classify(url, r)
        verdicts[url] = {'class': cls, 'detail': detail, 'status': r.status, 'final': r.final,
                         'at': archive._iso(now), 'cached': False}
        if cls in ('live', 'redirected'):
            resolved[url] = {k: v for k, v in verdicts[url].items() if k != 'cached'}
        else:
            resolved.pop(url, None)

    rows = []
    for lk in links:
        v = dict(verdicts[lk.url])
        if v['class'] == 'dead':
            capture = lk.archive_url
            if capture is None:
                try:
                    found = wayback.latest(lk.url)
                except archive.StopRun:
                    found = None
                capture = 'https://web.archive.org/web/%s/%s' % (found[0], found[1]) if found else None
            if capture:
                v['class'], v['detail'] = 'archived-only', '%s; archived at %s' % (v['detail'], capture)
        rows.append({'path': lk.path, 'where': lk.where, 'url': lk.url, **v})

    archived = []
    if archive_missing:
        stopped = None
        for rel in rels:
            if not rel.startswith('data/sources/'):
                continue
            rec = read(root, rel)
            if not isinstance(rec, dict) or not isinstance(rec.get('url'), str):
                continue
            base = {'path': rel, 'id': rec.get('id'), 'url': rec['url']}
            if rec.get('doi'):
                archived.append(dict(base, outcome='doi-exempt', unarchived=False))
            elif rec.get('archive_url'):
                archived.append(dict(base, outcome='archived', unarchived=False, archive_url=rec['archive_url']))
            elif stopped:
                archived.append(dict(base, outcome='not-attempted', reason=stopped, unarchived=True))
            else:
                try:
                    got = archive.ensure(rec['url'], wayback, cache, now)
                except archive.StopRun as e:
                    stopped = str(e)
                    got = {'outcome': 'not-attempted', 'reason': stopped, 'cached': False}
                archived.append(dict(base, **got, unarchived=True))
    if cache_path:
        archive.save_cache(cache_path, cache)

    counts = {c: sum(1 for r in rows if r['class'] == c) for c in CLASSES}
    unarchived = [a for a in archived if a['unarchived']]
    return {'files': len(rels), 'links': rows, 'counts': counts, 'archive': archived,
            'requests': resolver.requests, 'from_cache': sum(1 for v in verdicts.values() if v['cached']),
            'exit_code': 1 if counts['dead'] or unarchived else 0}


def text(report: dict) -> str:
    out = []
    for r in report['links']:
        if r['class'] != 'live':
            out.append('%-13s %s  %s  %s  (%s)' % (r['class'], r['path'], r['where'], r['url'], r['detail']))
    for a in report['archive']:
        if a['unarchived']:
            extra = a.get('archive_url') or a.get('job_id') or a.get('reason') or ''
            out.append('%-13s %s  %s  -> %s%s%s' % ('unarchived', a['path'], a['url'], a['outcome'],
                                                  ' (cached)' if a.get('cached') else '', ': %s' % extra if extra else ''))
    c = report['counts']
    out.append('check-links: %d link(s) in %d file(s): %s; %d from cache, %d request(s)' % (
        len(report['links']), report['files'], ', '.join('%d %s' % (c[k], k) for k in CLASSES),
        report['from_cache'], report['requests']))
    if report['archive']:
        n = sum(1 for a in report['archive'] if a['unarchived'])
        out.append('archive-missing: %d non-DOI Source(s) unarchived in their records%s' % (
            n, '; a capture found or requested is written by `python -m ingest.archive_sources`' if n else ''))
    return '\n'.join(out)


def as_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, default=asdict)
