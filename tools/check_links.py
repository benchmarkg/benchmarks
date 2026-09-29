"""The scheduled link-rot re-check: four outcomes, a digest comparison, a quarterly rotation
(P5-S8-T01; 06 S7.2, 08 S10, 05 S9).

    python -m tools.check_links                      # this week's slice; writes the Source records
    python -m tools.check_links --dry-run            # classify the slice; write nothing
    python -m tools.check_links --all                # every Source, a manual sweep
    python -m tools.check_links --summary out.md     # also write the pull request's body
    python -m tools.check_links --accept SRC_ID      # a curator accepts a page that changed

`bench check-links` (tools/links.py, P0-S5-T08) is the per-PR check: it classifies links and never
writes. This is the slow rotation 06 S7.2 names beside it -- "walks every Source on a slow rotation
sized so the whole corpus is covered each quarter" -- and it writes its verdicts back into the
records, where the site renders them (06 S7.2: "`link_status` and `archive_url` are rendered in
the UI, not hidden") and tools/build/feed.py reads them.

The fetch and the soft-404 heuristics are tools/links.py's, unchanged, so the two checks cannot
disagree about a page: GET with `Range: bytes=0-32767`, a plain GET when the server refuses the
range, never HEAD; redirects followed by hand; a 5xx or network error retried once; and the three
heuristics (under 2,048 bytes stripped, an SPA shell, a not-found title) applied BEFORE a link can be
live. What this adds is 06 S7.2's step 2 and its fourth outcome:

  live      2xx, passes the heuristics, and neither digest moved. Stamps link_checked_at; the first
            check of a Source records its body_sha256, the baseline later checks compare against
  changed   2xx, passes the heuristics, and the page's digest differs from body_sha256, or CDX holds
            a capture newer than archive_captured whose digest differs from archive_digest. The
            page is re-archived (SPN2 with if_not_archived_within=1d, so the new content is kept
            beside the old capture) AND flagged: "a silently rewritten leaderboard is a
            data-integrity event, not a refresh". So the baseline does NOT move -- body_sha256 and
            archive_* stay what the claims were taken from, the new digest waits in
            link_changed_sha256, and every later check reports `changed` until a curator runs
            --accept (or restores the page's standing some other way). Nothing is refreshed silently
  suspect   tools/links.py's suspect: a soft-404 or an SPA shell. Queued for human review; never live
  dead      tools/links.py's dead. archive_url is kept as the canonical reference and a lifecycle
            review is raised; a dead link found archived is still dead here (its record says so)

A 429 (tools/links.py's `unknown`) is not an outcome: nothing is written, and the Source stays at
the head of the rotation for the next run.

The page digest. A raw-byte hash of a live page changes on every fetch (a CSRF token, a nonce in an
inline script, a cache-buster), which would make every page `changed` every week and the flag
worthless. So an HTML body's digest is the sha256 of schema.source.normalise() applied to its first
32,768 bytes with <style> elements and every <script> element whose type does not name JSON removed:
the visible text plus the data a leaderboard ships as JSON (SWE-bench's, 07 S4.1). Any other body is
hashed as fetched. The CDX digest is Wayback's own (a SHA-1 of the whole raw capture), so it is
noisier; it is kept because it is the only signal for a change past the first 32 KB, and the report
names which signal fired.

The rotation (06 S7.2, "the whole corpus each quarter"). A weekly run checks ceil(N x 7 / 91)
Sources -- N the Sources outside ingest/no-collect.yaml -- never-checked first, then oldest
link_checked_at, ties by id. Thirteen weekly runs cover the corpus; a Source added mid-quarter
jumps the queue. A no-collect host is not fetched at all (06 S7.3: "honouring a no-collect request
means stopping").
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import math
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from schema.source import normalise  # noqa: E402
from tools import archive, fmt, links  # noqa: E402

CADENCE_DAYS = 7                # linkrot.yml runs weekly (08 S10)
QUARTER_DAYS = 91               # 06 S7.2: the whole corpus each quarter
DIGEST_BYTES = 32768            # the ranged head tools/links.py fetches
RECAPTURE_WITHIN = '1d'         # a changed page is re-captured unless SPN2 has one from today
OUTCOMES = ('live', 'changed', 'suspect', 'dead', 'unknown')
FIELDS = ('link_status', 'link_checked_at', 'link_detail', 'body_sha256', 'link_changed_sha256')
EVENTS = {'changed': 'data-integrity', 'suspect': 'human-review', 'dead': 'lifecycle-review'}
NO_COLLECT = os.path.join('ingest', 'no-collect.yaml')

_DROP = re.compile(r'<style\b[^>]*>.*?</style\s*>|<script\b(?![^>]*\btype\s*=\s*["\']?[^"\'>]*json)[^>]*>.*?</script\s*>',
                   re.I | re.S)


# ---- the digest ---------------------------------------------------------------------------------

def page_digest(body: bytes | None, content_type: str | None = None) -> str | None:
    """sha256 of what a reader of the page's head sees: see the module docstring."""
    if body is None:
        return None
    head = body[:DIGEST_BYTES]
    if not links.is_html(head, content_type):
        return hashlib.sha256(head).hexdigest()
    text = head.decode('utf-8', errors='replace')
    return hashlib.sha256(normalise(_DROP.sub(' ', text)).encode('utf-8')).hexdigest()


# ---- the corpus and the rotation ----------------------------------------------------------------

def _posix(p: str) -> str:
    return p.replace(os.sep, '/')


def load(root: str) -> list[tuple[str, dict]]:
    """(root-relative path, record) for every data/sources/ record with an id and a url."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '**', '*.yaml'), recursive=True)):
        rel = _posix(os.path.relpath(path, root))
        rec = links.read(root, rel)
        if isinstance(rec, dict) and isinstance(rec.get('id'), str) and isinstance(rec.get('url'), str):  # get-default: tier 1 reports a bad record
            out.append((rel, rec))
    return out


def no_collect(root: str) -> set[str]:
    """Hosts a maintainer asked us to stop collecting from: `- host` lines (as ingest/archive_sources.py)."""
    path = os.path.join(root, NO_COLLECT)
    if not os.path.exists(path):
        return set()
    with open(path, encoding='utf-8') as fh:
        return {m.group(1).lower() for m in re.finditer(r'^\s*-\s*([^\s#]+)', fh.read(), re.M)}


def slice_size(n: int, cadence_days: int = CADENCE_DAYS, quarter_days: int = QUARTER_DAYS) -> int:
    """Sources per run so that n are all checked within a quarter of runs every cadence_days."""
    return math.ceil(n * cadence_days / quarter_days)


def _stamp(rec: dict) -> str:
    v = rec.get('link_checked_at')          # get-default: a Source never checked has none
    if v is None:
        return ''
    return archive._iso(v) if isinstance(v, datetime) else str(v)


def rotation(items: list[tuple[str, dict]], n: int) -> list[tuple[str, dict]]:
    """The n Sources this run checks: never-checked first, then oldest link_checked_at, then id."""
    return sorted(items, key=lambda it: (_stamp(it[1]), it[1]['id']))[:n]


# ---- one Source ---------------------------------------------------------------------------------

def _captured(rec: dict) -> date | None:
    v = rec.get('archive_captured')         # get-default: an unarchived Source has none
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)) if v else None


def check(rec: dict, resolver, wayback, now: datetime) -> dict:
    """{'outcome', 'detail', 'updates', 'signals', 'digest', 'capture'}: what this check found and the
    record fields it sets. 'updates' is empty for `unknown`, which writes nothing."""
    url = rec['url']
    r = resolver.get(url)
    cls, detail = links.classify(url, r)
    stamp = {'link_checked_at': now, 'link_detail': detail}
    if cls == 'unknown':
        return {'outcome': 'unknown', 'detail': detail, 'updates': {}, 'signals': []}
    if cls == 'suspect':
        return {'outcome': 'suspect', 'detail': detail, 'signals': [],
                'updates': dict(stamp, link_status='suspect', link_changed_sha256=None)}
    if cls == 'dead':
        kept = rec.get('archive_url')       # get-default: a DOI Source may have no capture
        detail = '%s; %s' % (detail, 'the canonical reference is now %s' % kept if kept
                             else 'no capture on the record')
        return {'outcome': 'dead', 'detail': detail, 'signals': [],
                'updates': dict(stamp, link_detail=detail, link_status='dead', link_changed_sha256=None)}

    digest = page_digest(r.body, r.content_type)
    base = rec.get('body_sha256')           # get-default: the first check has no baseline
    signals, notes = [], []
    if base and digest and digest != base:
        signals.append('body')
        notes.append('the page digest is %s, not the accepted %s' % (digest[:12], base[:12]))
    capture = None
    try:
        capture = wayback.latest(url)
    except archive.StopRun as e:
        notes.append('CDX not consulted: %s' % e)
    recorded, on = rec.get('archive_digest'), _captured(rec)   # get-default: both absent before a capture
    if capture and recorded and capture[2] != recorded and on and archive.wayback_time(capture[0]).date() > on:
        signals.append('cdx')
        notes.append('CDX capture %s has digest %s, not the recorded %s of %s' % (capture[0], capture[2], recorded, on))
    if not signals:
        return {'outcome': 'live', 'detail': detail, 'signals': [], 'digest': digest, 'capture': capture,
                'updates': dict(stamp, link_status='live', body_sha256=base or digest, link_changed_sha256=None)}
    detail = 'changed (%s): %s' % ('+'.join(signals), '; '.join(notes))
    return {'outcome': 'changed', 'detail': detail, 'signals': signals, 'digest': digest, 'capture': capture,
            'updates': dict(stamp, link_detail=detail, link_status='changed', link_changed_sha256=digest or base)}


# ---- writing ------------------------------------------------------------------------------------

def write(root: str, rel: str, updates: dict) -> None:
    """Set top-level keys of a Source through the project's one emitter (tools/fmt.py), adding any
    the record does not have yet; `bench fmt` puts them in the model's order."""
    path = os.path.join(root, rel)
    with open(path, encoding='utf-8') as fh:
        doc = fmt.emitter().load(fh)
    for k, v in updates.items():
        doc[k] = archive._iso(v) if isinstance(v, datetime) else v
    text = fmt.format_text(fmt.dumps(doc), fmt.model_for(rel), rel)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


# ---- the run ------------------------------------------------------------------------------------

def run(root: str = ROOT, resolver=None, wayback=None, now: datetime | None = None, every: bool = False,
        dry_run: bool = False, limit: int | None = None) -> dict:
    now = now or links.utcnow()
    resolver = resolver or links.default_resolver(20)
    wayback = wayback or links.default_wayback()
    blocked = no_collect(root)
    items = [it for it in load(root) if links._host(it[1]['url']) not in blocked]
    size = len(items) if every else slice_size(len(items))
    chosen = rotation(items, limit if limit is not None else size)

    rows, events = [], []
    for rel, rec in chosen:
        got = check(rec, resolver, wayback, now)
        row = {'path': rel, 'id': rec['id'], 'url': rec['url'], 'outcome': got['outcome'],
               'detail': got['detail'], 'signals': got['signals']}
        if got['outcome'] in EVENTS:
            new = not (rec.get('link_status') == got['outcome'] and       # get-default: an unchecked Source
                       rec.get('link_changed_sha256') == got['updates'].get('link_changed_sha256'))
            event = {'kind': EVENTS[got['outcome']], 'new': new, **row}
            if got['outcome'] == 'changed' and new and not dry_run:
                event['recapture'] = recapture(rec['url'], wayback)
            events.append(event)
        if got['updates'] and not dry_run:
            write(root, rel, got['updates'])
        rows.append(row)

    counts = {o: sum(1 for r in rows if r['outcome'] == o) for o in OUTCOMES}
    return {'at': archive._iso(now), 'corpus': len(items), 'slice': size, 'checked': rows, 'counts': counts,
            'events': events, 'skipped_no_collect': len(load(root)) - len(items), 'dry_run': dry_run,
            'requests': resolver.requests}


def recapture(url: str, wayback) -> dict:
    """06 S7.2: a changed page is re-archived. Without SPN2 credentials this says so and asks nothing."""
    if not wayback.can_capture:
        return {'outcome': 'no-credentials'}
    try:
        job = wayback.submit(url, within=RECAPTURE_WITHIN)
    except archive.StopRun as e:
        return {'outcome': 'not-attempted', 'reason': str(e)}
    if isinstance(job, tuple):
        return {'outcome': 'refused', 'reason': '%s %s' % (job[1], job[2])}
    return {'outcome': 'requested', 'job_id': job}


def accept(root: str, source_id: str, wayback=None, now: datetime | None = None) -> dict:
    """A curator has read a `changed` page and accepts it: the new digest becomes the baseline, and the
    newest CDX capture, when it is newer than the recorded one, becomes archive_*. The old capture
    stays in git history, and in Wayback."""
    now = now or links.utcnow()
    wayback = wayback or links.default_wayback()
    for rel, rec in load(root):
        if rec['id'] != source_id:
            continue
        if rec.get('link_status') != 'changed':   # get-default: an unchecked Source is not changed
            raise SystemExit('%s: link_status is %s, not changed; nothing to accept' % (source_id, rec.get('link_status')))
        updates = {'body_sha256': rec['link_changed_sha256'], 'link_changed_sha256': None, 'link_status': 'live',
                   'link_checked_at': now, 'link_detail': 'the changed page was accepted by a curator'}
        found = wayback.latest(rec['url'])
        on = _captured(rec)
        if found and (on is None or archive.wayback_time(found[0]).date() > on):
            ts, original, digest = found
            updates.update({'archive_url': 'https://web.archive.org/web/%s/%s' % (ts, original),
                            'archive_captured': archive.wayback_time(ts).date().isoformat(),
                            'archive_digest': digest, 'archive_status': 'ok'})
        write(root, rel, updates)
        return dict(updates, path=rel)
    raise SystemExit('%s: no such Source under data/sources/' % source_id)


# ---- reporting ----------------------------------------------------------------------------------

def text(report: dict) -> str:
    out = ['%-9s %s  %s  (%s)' % (r['outcome'], r['id'], r['url'], r['detail'])
           for r in report['checked'] if r['outcome'] != 'live']
    c = report['counts']
    out.append('check_links: %d of %d Source(s) checked (a quarter\'s slice is %d a week): %s; %d event(s), %d new'
               % (len(report['checked']), report['corpus'], report['slice'], ', '.join('%d %s' % (c[k], k) for k in OUTCOMES),
                  len(report['events']), sum(1 for e in report['events'] if e['new'])))
    return '\n'.join(out)


def summary(report: dict) -> str:
    """The pull request's body: the events first, because they are what a curator acts on."""
    heads = {'data-integrity': 'Data-integrity events: the page changed under its citations',
             'human-review': 'Suspect: a soft-404 or an empty SPA shell',
             'lifecycle-review': 'Dead: the capture is now the canonical reference'}
    out = ['Weekly link-rot re-check (`python -m tools.check_links`, 06 S7.2): %d of %d Sources, %s.'
           % (len(report['checked']), report['corpus'], ', '.join('%d %s' % (report['counts'][k], k) for k in OUTCOMES)), '']
    for kind, head in heads.items():
        rows = [e for e in report['events'] if e['kind'] == kind]
        if not rows:
            continue
        out += ['### %s' % head, '']
        for e in rows:
            out.append('- %s`%s` <%s>: %s%s' % ('' if e['new'] else '(still) ', e['id'], e['url'], e['detail'],
                                               ' -- re-archive: %s' % e['recapture']['outcome'] if 'recapture' in e else ''))
        out.append('')
    if any(e['kind'] == 'data-integrity' for e in report['events']):
        out.append('A changed page is not refreshed: read it, then `python -m tools.check_links --accept <id>`.')
    return '\n'.join(out).rstrip() + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='python -m tools.check_links', description=__doc__.split('\n\n')[0])
    ap.add_argument('--all', action='store_true', help='check every Source, not this week\'s slice')
    ap.add_argument('--dry-run', action='store_true', help='classify; write nothing and request no capture')
    ap.add_argument('--limit', type=int, help='check at most this many Sources')
    ap.add_argument('--summary', help='write the pull request body (markdown) here')
    ap.add_argument('--accept', metavar='SRC_ID', help='accept the changed page of this Source')
    ap.add_argument('--timeout', type=float, default=20)
    a = ap.parse_args(argv)
    if a.accept:
        got = accept(ROOT, a.accept)
        print('accepted %s: %s' % (a.accept, ', '.join(sorted(k for k in got if k != 'path'))))
        return 0
    report = run(ROOT, resolver=links.default_resolver(a.timeout), every=a.all, dry_run=a.dry_run, limit=a.limit)
    print(text(report))
    if a.summary:
        with open(a.summary, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(summary(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
