"""Wayback Machine capture and lookup: the archival call `bench check-links` wraps (P0-S5-T08).

06 S7.1 and 07 S10, the rules every caller inherits:

  - existence is checked through CDX (`/cdx/search/cdx`), never the Availability API, which
    returned 429 on a single cold request during reconnaissance;
  - a capture is a Save Page Now 2 POST with `if_not_archived_within=30d`, the idempotency key:
    inside the window the server records nothing new, so a re-run costs no capture;
  - one request at a time against web.archive.org, spaced (06 S9.6: never fan out at one host).

`Wayback` is the HTTP client, moved here from ingest/archive_sources.py (P1-S2-T08), whose
docstring anticipated it; the nightly archiver keeps its budget, cursor and record writer and
imports the client from here. `ensure()` is the per-URL call `bench check-links --archive-missing`
makes: the local cache first, then CDX, then a capture request, and every outcome that should not
be re-requested inside the window is cached, so a second run inside it issues no request at all.

Credentials: IA_SPN_KEY / IA_SPN_SECRET (07 S5). SPN2 refuses anonymous captures (401, observed
2026-09-23), so without them `ensure` looks up and never submits.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

USER_AGENT = 'UAIBI/0.1 (+https://github.com/intelligence-benchmark/benchmarks)'
WINDOW = timedelta(days=30)
MAX_NETWORK_FAILURES = 3   # consecutive, before the run stops rather than hammering a sick host


class StopRun(Exception):
    """The run cannot continue (budget spent, bad credentials); records are left as they are."""


class Wayback:
    """CDX lookups and SPN2 submissions against web.archive.org, one request at a time."""

    def __init__(self, key=None, secret=None, spacing=1.0):
        self.key, self.secret, self.spacing = key, secret, spacing
        self._last = 0.0
        self._network_failures = 0
        self.lookup_failed = False  # the last CDX lookup got no answer, as opposed to no capture

    @property
    def can_capture(self):
        return bool(self.key and self.secret)

    def _request(self, url, data=None, auth=False):
        wait = self._last + self.spacing - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
        if auth:
            headers['Authorization'] = 'LOW %s:%s' % (self.key, self.secret)
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = r.status, r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            out = e.code, e.read().decode('utf-8', 'replace')
        except (urllib.error.URLError, OSError) as e:  # timeouts, resets, DNS: nothing came back
            self._network_failures += 1
            if self._network_failures >= MAX_NETWORK_FAILURES:
                raise StopRun('web.archive.org unreachable: %d network errors in a row, last %s'
                              % (self._network_failures, e))
            return None, str(e)
        finally:
            self._last = time.monotonic()
        self._network_failures = 0
        return out

    def latest(self, url):
        """(timestamp, original, digest) of the newest 200 capture, or None."""
        q = urllib.parse.urlencode({'url': url, 'output': 'json', 'limit': '-1',
                                    'filter': 'statuscode:200', 'fl': 'timestamp,original,digest'})
        status, body = self._request('https://web.archive.org/cdx/search/cdx?' + q)
        self.lookup_failed = status != 200
        if status == 429:
            raise StopRun('CDX returned 429')
        if status != 200:  # unknown, not absent; the capture's own 30d window still deduplicates
            return None
        try:
            rows = json.loads(body) if body.strip() else []
        except ValueError:
            return None
        if len(rows) < 2:  # the first row is the header
            return None
        ts, original, digest = rows[-1]
        return ts, original, digest

    def submit(self, url):
        """A job id, or ('error', status_ext, message)."""
        status, body = self._request('https://web.archive.org/save', auth=True, data={
            'url': url, 'if_not_archived_within': '30d', 'skip_first_archive': '1'})
        if status is None:
            return ('error', 'error:network', body)
        if status == 401:
            raise StopRun('SPN2 returned 401 with credentials set: check IA_SPN_KEY/IA_SPN_SECRET')
        if status == 429:
            raise StopRun('SPN2 returned 429')
        try:
            j = json.loads(body)
        except ValueError:
            return ('error', 'error:http-%d' % status, body[:200])
        if j.get('job_id'):
            return j['job_id']
        return ('error', j.get('status_ext') or 'error:unknown', j.get('message') or '')

    def poll(self, job_id):
        """('pending',) | ('success', timestamp, original) | ('error', status_ext, message)."""
        status, body = self._request('https://web.archive.org/save/status/' + job_id, auth=True)
        if status != 200:
            return ('pending',)
        try:
            j = json.loads(body)
        except ValueError:
            return ('pending',)
        if j.get('status') == 'success':
            return ('success', j['timestamp'], j.get('original_url'))
        if j.get('status') == 'error':
            return ('error', j.get('status_ext') or 'error:unknown', j.get('message') or '')
        return ('pending',)


def wayback_time(ts):
    return datetime.strptime(ts[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)




# ---- one URL, idempotently ----------------------------------------------------------------------

def _iso(t: datetime) -> str:
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse(s: str) -> datetime:
    return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def load_cache(path: str) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    return {'version': 1, 'resolved': {}, 'captures': {}}


def save_cache(path: str, cache: dict) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(cache, fh, indent=2, sort_keys=True)
        fh.write('\n')


def fresh(entry: dict | None, now: datetime, window: timedelta = WINDOW) -> bool:
    return bool(entry) and now - _parse(entry['at']) <= window


def ensure(url: str, wayback, cache: dict, now: datetime) -> dict:
    """Make sure `url` has, or has been asked for, a capture inside the window.

    Returns {'outcome': ..., 'at': ..., ...} with outcome one of:
      exists      CDX holds a 200 capture younger than the window (`capture`, `archive_url`, `digest`)
      requested   SPN2 accepted a capture job (`job_id`); the capture runs server-side
      refused     SPN2 refused it (`reason`), e.g. robots or a paywall -- a fact about the URL
      no-credentials, unreachable   nothing could be asked; not cached, so the next run tries again
    and `cached: True` when the answer came from `cache` with no request made.
    """
    captures = cache.setdefault('captures', {})
    hit = captures.get(url)
    if fresh(hit, now):
        return dict(hit, cached=True)
    out = None
    found = wayback.latest(url)
    if found and now - wayback_time(found[0]) <= WINDOW:
        ts, original, digest = found
        out = {'outcome': 'exists', 'capture': ts, 'digest': digest,
               'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original)}
    elif not wayback.can_capture:
        return {'outcome': 'no-credentials', 'at': _iso(now), 'cached': False}
    else:
        job = wayback.submit(url)
        if isinstance(job, tuple):
            if job[1] == 'error:network':
                return {'outcome': 'unreachable', 'reason': job[2], 'at': _iso(now), 'cached': False}
            out = {'outcome': 'refused', 'reason': '%s %s' % (job[1], job[2])}
        else:
            out = {'outcome': 'requested', 'job_id': job}
    out['at'] = _iso(now)
    captures[url] = out
    return dict(out, cached=False)
