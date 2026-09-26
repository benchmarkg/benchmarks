#!/usr/bin/env python3
"""The rolling archival budget: capture non-DOI Sources in Wayback, a bounded slice per night.

06-sourcing-and-scraping.md S7.1 sets the policy and this implements it:

  - at most 500 captures per run (--max-captures), ordered oldest-unarchived first, and
    resumable from the cursor in ingest/state/archive.json, so a run cut off at its cap or its
    timeout carries on from where it stopped instead of re-hitting the head of the queue;
  - every capture is a Save Page Now 2 request with if_not_archived_within=30d, which is the
    idempotency key: a re-run inside the window costs no capture, and a dropped cron costs nothing;
  - existence is checked through CDX first, never the Availability API (it 429s on a cold request,
    07 S10), and a CDX capture younger than 30 days is recorded without submitting anything;
  - one request per Source, never per field;
  - a Source SPN2 refuses is recorded `archive_status: failed` with its reason (S7.3), and a
    transient error leaves it `pending` with the reason, up to --max-attempts runs, after which it
    is recorded failed too. Nothing is retried forever.

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
from tools.archive import WINDOW, StopRun, Wayback, wayback_time  # noqa: E402,F401  (StopRun: callers catch it here)

STATE = os.path.join(ROOT, 'ingest', 'state', 'archive.json')
KEEP_RUNS = 30
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
    'error:unauthorized',
}
# These mean our budget is spent, so the run stops and nobody's attempt count moves.
BUDGET = {'error:too-many-daily-captures', 'error:user-session-limit', 'error:too-many-requests'}


def fmt(t):
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


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
        persist=lambda: None):
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

    def settle(key, src, outcome):
        r, sid = src.record, src.record['id']
        if outcome[0] == 'success':
            ts, original = outcome[1], outcome[2] or r['url']
            finish(key, src, {'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original),
                              'archive_captured': fmt(wayback_time(ts)), 'archive_status': 'ok',
                              'failure_reason': None})
            state['attempts'].pop(sid, None)
            stats['captured'] += 1
            log('ok      %s  %s' % (sid, ts))
            return
        ext, msg = outcome[1], outcome[2]
        if ext in BUDGET:
            raise StopRun('SPN2 %s: %s' % (ext, msg))
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
            if hit and now() - wayback_time(hit[0]) <= WINDOW:
                ts, original, digest = hit
                stats['from_cdx'] += 1
                log('cdx     %s  %s' % (r['id'], ts))
                finish(key, src, {'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original),
                                  'archive_captured': fmt(wayback_time(ts)), 'archive_status': 'ok',
                                  'archive_digest': digest, 'failure_reason': None})
                continue
            if not wayback.can_capture or dry_run:
                log('queued  %s  (%s)' % (r['id'], 'CDX did not answer' if getattr(wayback, 'lookup_failed', False)
                                          else 'no capture in the last 30 days'))
                continue
            if stats['submitted'] >= max_captures:
                stats['stopped'] = 'budget: %d captures' % max_captures
                break
            drain(in_flight - 1)
            job = wayback.submit(r['url'])  # a StopRun here leaves the record untouched
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
