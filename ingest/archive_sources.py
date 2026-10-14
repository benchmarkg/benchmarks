#!/usr/bin/env python3
"""The rolling archival budget: capture non-DOI Sources in Wayback, a bounded slice per night.

06-sourcing-and-scraping.md S7.1 sets the policy and this implements it:

  - at most 500 captures per run (--max-captures), ordered oldest-unarchived first, and
    resumable from the cursor in ingest/state/archive.json, so a run cut off at its cap or its
    timeout carries on from where it stopped instead of re-hitting the head of the queue;
  - every capture is a Save Page Now 2 request with if_not_archived_within=30d, which is the
    idempotency key: a re-run inside the window costs no capture, and a dropped cron costs nothing;
  - existence is checked through CDX first, never the Availability API (it 429s on a cold request,
    07 S10), and a CDX capture younger than 30 days is recorded without submitting anything -- if it
    holds every window of the Source's committed quote_extract. A capture that lacks one is stale (the
    page changed after it was taken) and is re-captured unless SPN2 has one from today;
  - one request per Source, never per field;
  - a Source SPN2 refuses is recorded `archive_status: failed` with its reason (S7.3), and a
    transient error leaves it `pending` with the reason, up to --max-attempts runs, after which it
    is recorded failed too. Nothing is retried forever;
  - two refusals are read for what they mean. "The same snapshot had been made N hours ago" with no
    200 capture in CDX means the URL now redirects (Wayback holds a 3xx capture of it): retrying
    cannot help, so it is recorded failed at once with where it redirects to, for a curator to
    re-point the Source. An error that names a URL other than the Source's (SPN2's headless browser
    failing on the page's favicon) means the page itself answered, so the next attempt captures
    with force_get, a plain GET.

    python -m ingest.archive_sources                 # the nightly run
    python -m ingest.archive_sources --dry-run       # print the queue and what CDX says; write nothing
    python -m ingest.archive_sources --max-captures 20

Credentials. SPN2 refuses anonymous captures (401, observed 2026-09-23). With IA_SPN_KEY and
IA_SPN_SECRET unset the run degrades, as 07 S5 asks, to CDX-only: it still records any existing
capture younger than 30 days, submits nothing, stamps nothing, and says so. A 401 with keys set
stops the run without touching any record, because a bad key is not a fact about the Source.

Politeness. SPN2 is asynchronous: a POST returns a job id and the capture runs server-side. So the
client stays sequential against web.archive.org (06 S9.6: never fan out at one host) and at most
--in-flight jobs are open server-side at once, polled round-robin.

Records. Only these top-level keys of a Source are rewritten, in place, line by line, so each
file's comments and layout survive: archive_url, archive_captured, archive_status, archive_digest,
archive_requested_at, failure_reason. `archive_requested_at` is the FIRST request and is never
moved forward, or the seven-day SLA that scripts/check_archive_coverage.py enforces could be reset
nightly by a request that keeps failing.

The HTTP calls live in tools/archive.py's `Wayback` (moved there by P0-S5-T08, which wraps it for
`bench check-links`); this module keeps the budget, the cursor and the record writer.
"""
import os
import sys

if __name__ == '__main__' and not __package__:
    # Run as a file, this directory is sys.path[0], and ingest/http/ would then shadow the standard
    # library's `http`, which urllib imports. Put the repository root there instead.
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
if ROOT not in sys.path:
    sys.path.insert(1, ROOT)
from check_archive_coverage import first_ingest, load_sources  # noqa: E402
from tools.archive import WINDOW, StopRun, Wayback, location, wayback_time  # noqa: E402,F401  (StopRun: callers catch it here)

STATE = os.path.join(ROOT, 'ingest', 'state', 'archive.json')
KEEP_RUNS = 30
RECAPTURE_WITHIN = '1d'    # a stale CDX capture is re-captured unless SPN2 has one from today (tools/check_links.py)
JOB_TIMEOUT = 600          # seconds a submitted capture may stay pending before it counts as an error
FIELDS = ('archive_url', 'archive_captured', 'archive_status', 'archive_digest',
          'archive_requested_at', 'failure_reason')

# SPN2 status_ext values that are facts about the URL, not about the moment. Anything else is
# treated as transient until --max-attempts is reached.
PERMANENT = {
    'error:bad-request', 'error:blocked', 'error:blocked-url', 'error:blocked-client-ip',
    'error:filesize-limit', 'error:ftp-access-denied', 'error:invalid-host-resolution',
    'error:invalid-url-syntax', 'error:method-not-allowed', 'error:network-authentication-required',
    'error:no-access', 'error:not-found', 'error:not-implemented', 'error:too-many-redirects',
    'error:unauthorized', 'error:redirect',
}
SAME_SNAPSHOT = 'The same snapshot had been made'
_URL = re.compile(r'https?://[^\s"<>]+')
# These mean our budget is spent, so the run stops and nobody's attempt count moves.
BUDGET = {'error:too-many-daily-captures', 'error:user-session-limit', 'error:too-many-requests'}


def fmt(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def captured_on(ts):
    """`archive_captured` is a date in the Source schema (04 S9), not a timestamp: the capture's UTC day.
    The full instant stays in the archive_url's timestamp."""
    return wayback_time(ts).date().isoformat()


def sub_resource(error, url):
    """True when an SPN2 error names a URL other than the one captured: a sub-resource failed, not
    the page, and force_get (no headless browser) avoids fetching it."""
    named = [u.rstrip('.,;:)') for u in _URL.findall(error or '')]
    return any(u != url for u in named)


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


_SCRIPT_STYLE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.S | re.I)
_BETWEEN_WINDOWS = re.compile(r'\s*…\s*')


def lacking_windows(record, wayback, ts, original):
    """How many windows of a Source's committed quote_extract a CDX capture does not hold.

    A capture younger than 30 days is reused only if it holds the text the quotes were checked against: a
    leaderboard that gained rows since the capture would otherwise be archived by a copy without them
    (RoboTwin's board data, 2026-10-14). 0 when it cannot be told -- no extract, a raw-body extract, a PDF
    body, or a capture that does not load -- in which case the capture is reused as before."""
    from schema.source import fold, normalise
    extract = record.get('quote_extract')
    if not extract or record.get('quote_extract_basis') == 'raw-body' or not hasattr(wayback, 'capture_body'):
        return 0
    body = wayback.capture_body(ts, original)
    if not body or body[:4] == b'%PDF':
        return 0
    text = fold(normalise(_SCRIPT_STYLE.sub(' ', body.decode('utf-8', 'replace'))))
    windows = _BETWEEN_WINDOWS.split(extract) if record.get('quote_extract_mode') == 'windows' else [extract]
    return sum(1 for w in windows if w.strip() and fold(w.strip()) not in text)


def rewrite(path, updates):
    """Set top-level keys through the project's one YAML emitter (07 S1.5, tools/fmt.py), so the
    file stays exactly what `bench fmt` writes and comments survive; every key in `updates` must
    already exist. (Until P0-S5-T04 this replaced `key: value` lines as text, which left the
    continuation lines of a wrapped value behind: a two-line failure_reason set to null became
    the string "null <second line>".)"""
    from tools import fmt
    with open(path, encoding='utf-8') as f:
        doc = fmt.emitter().load(f)
    missing = set(updates) - set(doc)
    if missing:
        raise ValueError('%s has no top-level %s' % (path, ', '.join(sorted(missing))))
    for k, v in updates.items():
        doc[k] = v
    text = fmt.format_text(fmt.dumps(doc), fmt.model_for(path.replace(os.sep, '/')), path)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def load_state(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'cursor': None, 'attempts': {}, 'runs': []}


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write('\n')


def load_no_collect(path):
    """Hosts a maintainer asked us to stop collecting from (06 S9.6): one per line, `- host`."""
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as f:
        return {m.group(1).lower() for m in re.finditer(r'^\s*-\s*([^\s#]+)', f.read(), re.M)}


def queue(sources, cursor, no_collect):
    """Non-DOI Sources still lacking a capture, oldest first, rotated to start after the cursor."""
    todo = []
    for s in sources:
        r = s.record
        if r.get('doi') or r.get('archive_url') or r.get('archive_status') not in (None, 'pending'):
            continue  # DOI-exempt, done, failed, withheld or not-required: none is ours to retry
        host = (urllib.parse.urlsplit(r.get('url') or '').hostname or '').lower()
        if not host or host in no_collect:
            continue
        born = first_ingest(r)
        todo.append(((fmt(born) if born else '0000'), r['id'], s))
    todo.sort(key=lambda t: t[:2])
    if cursor:
        cur = tuple(cursor)
        split = next((i for i, t in enumerate(todo) if t[:2] > cur), len(todo))
        todo = todo[split:] + todo[:split]
    return todo


def run(sources, state, wayback, max_captures=500, max_attempts=5, in_flight=6,
        no_collect=frozenset(), dry_run=False, now=utcnow, poll_every=5.0, log=print,
        persist=lambda: None, locate=location):
    """One run. `persist` is called after every settled Source, so a killed job loses at most one."""
    stats = {'started': fmt(now()), 'queued': 0, 'from_cdx': 0, 'captured': 0, 'failed': 0,
             'pending': 0, 'submitted': 0, 'mode': 'capture' if wayback.can_capture else 'cdx-only',
             'stopped': None}
    items = queue(sources, state.get('cursor'), no_collect)
    stats['queued'] = len(items)
    if not wayback.can_capture:
        log('IA_SPN_KEY/IA_SPN_SECRET not set: CDX-only run, nothing will be submitted')

    def finish(key, src, updates):
        if not dry_run:
            rewrite(src.path, updates)
            src.record.update(updates)
            state['cursor'] = list(key)
            persist()

    open_jobs = []  # (key, src, job_id, monotonic submit time)

    def redirected(url):
        """Why SPN2's "same snapshot" refusal is final, or None when it is not about a redirect."""
        hit = wayback.newest(url)
        if not hit or not str(hit[1]).startswith('3'):
            return None
        to = locate(url)
        where = 'to %s (HTTP %s)' % (to[1], to[0]) if to else '(the live URL no longer says where)'
        return ('the URL redirects %s, and the newest Wayback capture of it (%s) is an HTTP %s redirect, so '
                'there is no page at this URL to capture; a curator re-points the Source (06 S7.3)'
                % (where, hit[0], hit[1]))

    def settle(key, src, outcome):
        r, sid = src.record, src.record['id']
        if outcome[0] == 'success':
            ts, original = outcome[1], outcome[2] or r['url']
            finish(key, src, {'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original),
                              'archive_captured': captured_on(ts), 'archive_status': 'ok',
                              'failure_reason': None})
            state['attempts'].pop(sid, None)
            stats['captured'] += 1
            log('ok      %s  %s' % (sid, ts))
            return
        ext, msg = outcome[1], outcome[2]
        if ext in BUDGET:
            raise StopRun('SPN2 %s: %s' % (ext, msg))
        moved = SAME_SNAPSHOT in (msg or '') and redirected(r['url'])
        if moved:
            ext, msg = 'error:redirect', moved
        att = state['attempts'].setdefault(sid, {'count': 0})
        att['count'] += 1
        att['last_error'] = '%s %s' % (ext, msg)
        att['last_at'] = fmt(now())
        reason = 'Save Page Now %s: %s' % (ext, msg or '(no message)')
        if ext in PERMANENT or att['count'] >= max_attempts:
            if ext not in PERMANENT:
                reason = 'gave up after %d runs; last: %s' % (att['count'], reason)
            finish(key, src, {'archive_status': 'failed', 'failure_reason': reason})
            state['attempts'].pop(sid, None)
            stats['failed'] += 1
            log('failed  %s  %s' % (sid, reason))
        else:
            finish(key, src, {'archive_status': 'pending', 'failure_reason': reason})
            stats['pending'] += 1
            log('pending %s  attempt %d: %s' % (sid, att['count'], reason))

    def drain(limit):
        while len(open_jobs) > limit:
            for job in list(open_jobs):
                key, src, job_id, submitted = job
                outcome = wayback.poll(job_id)
                if outcome[0] == 'pending' and time.monotonic() - submitted > JOB_TIMEOUT:
                    outcome = ('error', 'error:poll-timeout', 'still pending after %ds' % JOB_TIMEOUT)
                if outcome[0] != 'pending':
                    open_jobs.remove(job)
                    settle(key, src, outcome)
            if len(open_jobs) > limit:
                time.sleep(poll_every)

    try:
        for key0, key1, src in items:
            key, r = (key0, key1), src.record
            hit = wayback.latest(r['url'])
            stale = 0
            if hit and now() - wayback_time(hit[0]) <= WINDOW:
                ts, original, digest = hit
                stale = lacking_windows(r, wayback, ts, original)
                if not stale:
                    stats['from_cdx'] += 1
                    log('cdx     %s  %s' % (r['id'], ts))
                    finish(key, src, {'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original),
                                      'archive_captured': captured_on(ts), 'archive_status': 'ok',
                                      'archive_digest': digest, 'failure_reason': None})
                    continue
                stats['stale'] = stats.get('stale', 0) + 1
                log('stale   %s  %s lacks %d of the extract\'s windows' % (r['id'], ts, stale))
            if not wayback.can_capture or dry_run:
                log('queued  %s  (%s)' % (r['id'], 'the capture CDX has is stale' if stale else
                                          'CDX did not answer' if getattr(wayback, 'lookup_failed', False)
                                          else 'no capture in the last 30 days'))
                continue
            if stats['submitted'] >= max_captures:
                stats['stopped'] = 'budget: %d captures' % max_captures
                break
            drain(in_flight - 1)
            plain = sub_resource((state['attempts'].get(r['id']) or {}).get('last_error'), r['url'])
            if plain:
                log('force_get %s  (the last attempt failed on a sub-resource)' % r['id'])
            # a StopRun here leaves the record untouched. A stale capture is re-captured unless SPN2 has one from
            # today, as the link-rot re-check does (06 S7.2): the 30-day key would hand the stale one back.
            within = {'within': RECAPTURE_WITHIN} if stale else {}
            job = wayback.submit(r['url'], force_get=True, **within) if plain else wayback.submit(r['url'], **within)
            if isinstance(job, tuple) and job[1] in BUDGET:
                raise StopRun('SPN2 %s: %s' % (job[1], job[2]))
            stats['submitted'] += 1
            if not r.get('archive_requested_at'):
                finish(key, src, {'archive_status': 'pending', 'archive_requested_at': fmt(now())})
            if isinstance(job, tuple):
                settle(key, src, job)
            else:
                open_jobs.append((key, src, job, time.monotonic()))
        drain(0)
    except StopRun as e:
        stats['stopped'] = str(e)
        log('stopped: %s' % e)
    stats['finished'] = fmt(now())
    state['runs'] = (state.get('runs') or [])[-(KEEP_RUNS - 1):] + [stats]
    return stats


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT, help='repository root holding data/sources/')
    p.add_argument('--state', default=STATE)
    p.add_argument('--max-captures', type=int, default=500)
    p.add_argument('--max-attempts', type=int, default=5)
    p.add_argument('--in-flight', type=int, default=6)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args(argv)

    sources = load_sources(a.root)
    state = load_state(a.state)
    wayback = Wayback(os.environ.get('IA_SPN_KEY'), os.environ.get('IA_SPN_SECRET'))
    stats = run(sources, state, wayback, a.max_captures, a.max_attempts, a.in_flight,
                load_no_collect(os.path.join(a.root, 'ingest', 'no-collect.yaml')), a.dry_run,
                persist=lambda: save_state(a.state, state))
    if not a.dry_run:
        save_state(a.state, state)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
