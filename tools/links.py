"""`bench check-links [PATH...] [--changed-only] [--archive-missing] [--timeout 20] [--format text|json]`
(P0-S5-T08; 05 S3, 06 S7; the soft-404 heuristics and PATH, P1-S1-T02).

05 S3: "HTTP-check every `url` in the touched files; report rot; optionally queue archiving."

What is checked. Every whole-string http(s) value in every YAML file under data/ -- `url`,
`homepage`, `repository`, the `*_url` fields and any other -- except Wayback captures themselves
(an `archive_url`, or anything on web.archive.org): those are the archived copies a dead link falls
back to, and checking them would hammer the one host 06 S9.6 most needs us to be polite to. Each
distinct URL is requested once however many records cite it. `--changed-only` narrows the files to
those changed against the merge base with origin/main, as `bench validate --changed-only` does.
PATH names the YAML files (or directories of them) to check instead of data/, and may lie outside it:
`bench check-links taxonomy/_corpus/stress-corpus.yaml` is P1-S1-T02's verification.

How. 06 S7.2: "`GET` with `Range: bytes=0-32767` ... Never `HEAD`" -- many servers answer HEAD
with 405. Redirects are followed by hand, up to ten, so the chain is known; requests are sequential
and spaced per host; a 5xx or a network error gets one retry.

The classes, each a fact about the link:

  live           2xx with no redirect, and the body passes the soft-404 heuristics
  redirected     2xx after a redirect within the same site (www., http->https, a subdomain; an HTTP 3xx
                 or a `<meta http-equiv="refresh">` on a page under 2,048 bytes), or
                 from a resolver whose job is to redirect (doi.org, hdl.handle.net, ...), and passes
  suspect        2xx, but an HTML body fails a soft-404 heuristic (06 S7.2): under 2,048 bytes after
                 whitespace stripping, an SPA shell (a single root `div` and no text node over 200
                 characters), or a title matching /404|not found|page not found/i. "Never `live`"
  dead           4xx, 5xx after the retry, DNS or connection failure, too many redirects, or a
                 redirect to an unrelated host (06 S7.2: the host changed hands or the page moved)
  archived-only  dead, but a capture exists: the record's own `archive_url` beside the URL, or
                 CDX's newest capture. The citation survives; the record needs a lifecycle review
  unknown        429: the server declined to answer, which says nothing about the link

Exit status: 1 on any `dead` or `suspect` link. `archived-only` is reported and does not fail -- its
canonical reference is the capture, which is what 06 S7.2 says to keep -- and `unknown` does not
either. A suspect link fails because 06 S7.2 names it the worse failure: "a green link check on a page
that has become an empty React root", where a 404 would at least be visible.

The heuristics read HTML only (a text/html Content-Type, or a body that opens with markup when none
is given): they describe pages, and a 900-byte JSON answer or a PDF is not a soft-404 for being
short. They are applied to the ranged first 32 KB where that decides them; a page whose first 32 KB
cannot (no text node over 200 characters yet, markup still open) is fetched whole, up to 4 MB.

`--archive-missing`: every non-DOI Source in scope without an `archive_url` goes through
tools/archive.py's `ensure` (cache, then CDX, then an SPN2 request with if_not_archived_within=30d),
and the run exits 1 while any remains unarchived in its record: a capture CDX found or SPN2 is making
still has to be written into the record, which is the nightly archiver's job (ingest/archive_sources.py),
not a link checker's. A DOI Source is exempt (04 S12). check-links never writes data/.

The cache (ingest/state/links.json, gitignored). A live or redirected resolution and every capture
outcome worth remembering are kept for the 30-day window, so a re-run inside it costs no request;
a dead link is never cached, because a link that died should be re-checked the next time, not a
month later.

06 S7.2's `changed` class and its body-digest comparison belong to the scheduled link-rot job (08
S3.5: Phase 5), not to this check. Cache entries written before the heuristics existed carry no
`heuristics` stamp and are re-checked rather than trusted.
"""
from __future__ import annotations

import html.parser
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
CLASSES = ('live', 'redirected', 'suspect', 'archived-only', 'dead', 'unknown')
FULL_BODY = 4 * 1024 * 1024
HEURISTICS = 1                  # the soft-404 rule set a cached verdict was reached under
MIN_BODY = 2048
MIN_TEXT = 200
# 404 as a number of its own: not the '404' inside '[2404.07917] DesignQA', an arXiv page's title.
NOT_FOUND = re.compile(r'(?<![\w.])404(?![\w.])|not found|page not found', re.I)


@dataclass
class Link:
    path: str                   # root-relative file
    where: str                  # dotted location in the record
    url: str
    archive_url: str | None     # the capture recorded beside it, if any


@dataclass
class _Got:
    status: int | None
    location: str | None
    error: str | None
    body: bytes | None = None
    content_type: str | None = None
    complete: bool = True


@dataclass
class Response:
    status: int | None          # the final status; None when nothing came back
    final: str
    redirects: list[str] = field(default_factory=list)
    error: str | None = None
    body: bytes | None = None           # what was read of the final 2xx body; None when not kept
    content_type: str | None = None
    complete: bool = True               # False when `body` is the ranged head of a longer body


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


def _posix(p: str) -> str:
    return p.replace(os.sep, '/')


def named(root: str, paths: list[str]) -> list[str]:
    """PATH arguments as root-relative YAML files: a file as given, a directory by its *.yaml."""
    out = []
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(root, p)
        if os.path.isdir(full):
            for d, _, fs in os.walk(full):
                out += [os.path.join(d, f) for f in fs if f.endswith(('.yaml', '.yml'))]
        elif os.path.isfile(full):
            out.append(full)
        else:
            raise FileNotFoundError(p)
    return sorted({_posix(os.path.relpath(f, root)) for f in out})


def files(root: str, changed_only: bool = False, paths: list[str] | None = None) -> list[str]:
    from tools.validate import tiers
    if paths:
        found = named(root, paths)
        if changed_only:
            changed = tiers.changed_files(root)
            found = [p for p in found if p in changed]
        return found
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

    def _once(self, url: str, ranged: bool = True, limit: int = 32768) -> _Got:
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
                body = r.read(limit)
                if r.status == 206:             # the server honoured the Range: its total says the rest
                    total = (r.headers.get('Content-Range') or '').rpartition('/')[2]
                    complete = total.isdigit() and int(total) <= len(body)
                else:
                    complete = len(body) < limit or not r.read(1)
                return _Got(r.status, None, None, body, r.headers.get('Content-Type'), complete)
        except urllib.error.HTTPError as e:
            return _Got(e.code, e.headers.get('Location'), None)
        except (urllib.error.URLError, OSError, ValueError) as e:   # DNS, refused, reset, timeout, bad URL
            return _Got(None, None, ' '.join(str(getattr(e, 'reason', e)).split())[:200])
        finally:
            self._last[host] = time.monotonic()

    def _one(self, url) -> _Got:
        got = self._once(url)
        if got.status == 416:                   # a server that refuses the Range: ask for the page
            got = self._once(url, ranged=False)
        if got.status is None or got.status >= 500:
            time.sleep(self.retry_after)
            got = self._once(url)
        return got

    def get(self, url: str) -> Response:
        chain, cur = [], url
        for _ in range(MAX_REDIRECTS + 1):
            got = self._one(cur)
            if got.status in (301, 302, 303, 307, 308) and got.location:
                chain.append(cur)
                cur = urllib.parse.urljoin(cur, got.location)
                continue
            target = meta_refresh(got)
            if target:                          # a small page whose only job is to send the reader on
                chain.append(cur)
                cur = urllib.parse.urljoin(cur, target)
                continue
            r = Response(got.status, cur, chain, got.error, got.body, got.content_type, got.complete)
            if r.status and 200 <= r.status < 300 and soft404(r)[0] == 'undecided':
                whole = self._once(cur, ranged=False, limit=FULL_BODY)
                if whole.status and 200 <= whole.status < 300:
                    r.body, r.content_type, r.complete = whole.body, whole.content_type or r.content_type, True
            return r
        return Response(None, cur, chain, 'more than %d redirects' % MAX_REDIRECTS)


# ---- the soft-404 heuristics (06 S7.2) ----------------------------------------------------------

SKIPPED = frozenset({'script', 'style', 'noscript', 'template', 'svg'})
VOID = frozenset({'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
                  'source', 'track', 'wbr'})
NOT_CONTENT = SKIPPED | frozenset({'link', 'meta', 'base'})


class _Page(html.parser.HTMLParser):
    """The three facts the heuristics read: the title, the longest text node outside script and
    style, and the element children of <body> (of the document, when there is no <body>)."""

    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.title, self.longest, self.roots, self._in_title = None, 0, [], False
        self._body_depth: int | None = None

    def handle_starttag(self, tag, attrs):
        root = self._body_depth if self._body_depth is not None else 0
        if tag == 'body':
            self._body_depth = len(self.stack) + 1
        elif (len(self.stack) == root and tag not in ('html', 'head') and tag not in NOT_CONTENT
              and 'head' not in self.stack):
            self.roots.append(tag)
        if tag == 'title':
            self._in_title = True
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._in_title:
            self.title = ((self.title or '') + data).strip()
        elif not SKIPPED & set(self.stack):
            self.longest = max(self.longest, len(' '.join(data.split())))


REFRESH = re.compile(rb"""<meta[^>]+http-equiv=["']?refresh["']?[^>]*content=["']?\s*\d*\s*;\s*url\s*=\s*['"]?([^'">\s]+)""",
                     re.I)


def meta_refresh(got) -> str | None:
    """The target of a `<meta http-equiv="refresh">` on a 2xx HTML page under MIN_BODY bytes: a
    redirect done in markup, which a browser follows at once. Followed as a redirect, under the same
    same-site rule; a large page with a refresh timer is a page, not a redirect."""
    if not (got.status and 200 <= got.status < 300 and got.body is not None and got.complete):
        return None
    if not is_html(got.body, got.content_type) or len(re.sub(rb'\s+', b'', got.body)) >= MIN_BODY:
        return None
    m = REFRESH.search(got.body)
    return m.group(1).decode('utf-8', errors='replace') if m else None


def is_html(body: bytes, content_type: str | None) -> bool:
    if content_type:
        return 'html' in content_type.lower()
    return body.lstrip()[:1] == b'<'


def soft404(r: Response) -> tuple[str, str | None]:
    """('ok' | 'suspect' | 'undecided', reason). Only an HTML body is judged; `undecided` means the
    ranged head could not settle it and the whole page is needed."""
    if r.body is None or not is_html(r.body, r.content_type):
        return 'ok', None
    charset = re.search(r'charset=([\w-]+)', r.content_type or '')
    try:
        text = r.body.decode(charset.group(1) if charset else 'utf-8', errors='replace')
    except LookupError:
        text = r.body.decode('utf-8', errors='replace')
    page = _Page()
    page.feed(text)
    if page.title and NOT_FOUND.search(page.title):
        return 'suspect', 'soft-404: the title is %r' % page.title[:80]
    size = len(re.sub(rb'\s+', b'', r.body))
    if r.complete and size < MIN_BODY:
        return 'suspect', 'soft-404: the body is %d bytes after whitespace stripping, under %d' % (size, MIN_BODY)
    if page.longest > MIN_TEXT:
        return 'ok', None
    if not r.complete:
        return 'undecided', None
    if page.roots == ['div']:
        return 'suspect', ('soft-404: an SPA shell, a single root div and no text node over %d characters '
                           '(the longest is %d)' % (MIN_TEXT, page.longest))
    return 'ok', None


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
    start, end = _host(url), _host(r.final)
    if r.redirects and not (_site(start) == _site(end) or start in REDIRECTING):
        return 'dead', 'redirects to an unrelated host: %s' % r.final
    state, why = soft404(r)
    if state == 'suspect':
        return 'suspect', why + (' (after redirects, at %s)' % r.final if r.redirects else '')
    if not r.redirects:
        return 'live', 'HTTP %d' % r.status
    return 'redirected', 'to %s' % r.final


# ---- the run ------------------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def default_resolver(timeout: float) -> Resolver:
    return Resolver(timeout)


def default_wayback():
    return archive.Wayback(os.environ.get('IA_SPN_KEY'), os.environ.get('IA_SPN_SECRET'))


def run(root: str = ROOT, changed_only: bool = False, archive_missing: bool = False, resolver=None,
        wayback=None, cache_path: str | bool | None = None, now: datetime | None = None, timeout: float = 20,
        paths: list[str] | None = None) -> dict:
    """One check. `cache_path` None means CACHE; False means no cache at all. `paths`, when given,
    are the files checked in place of data/."""
    now = now or utcnow()
    cache_path = CACHE if cache_path is None else cache_path
    resolver = resolver or default_resolver(timeout)
    wayback = wayback or default_wayback()
    cache = archive.load_cache(cache_path) if cache_path else {'version': 1, 'resolved': {}, 'captures': {}}
    resolved = cache.setdefault('resolved', {})
    rels = files(root, changed_only, paths)
    links = collect(root, rels)

    verdicts: dict[str, dict] = {}
    for url in dict.fromkeys(lk.url for lk in links):
        hit = resolved.get(url)
        if archive.fresh(hit, now) and hit.get('heuristics') == HEURISTICS:
            verdicts[url] = dict(hit, cached=True)
            continue
        r = resolver.get(url)
        cls, detail = classify(url, r)
        verdicts[url] = {'class': cls, 'detail': detail, 'status': r.status, 'final': r.final,
                         'at': archive._iso(now), 'cached': False}
        if cls in ('live', 'redirected'):
            resolved[url] = dict({k: v for k, v in verdicts[url].items() if k != 'cached'}, heuristics=HEURISTICS)
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
            'exit_code': 1 if counts['dead'] or counts['suspect'] or unarchived else 0}


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
