#!/usr/bin/env python3
"""build/derived/freshness.json: every entry's freshness badge and its source freshness (P5-S7-T04; 05 S7, 06 S3.0).

    python tools/build/freshness.py --out build/derived/freshness.json [--root PATH] [--as-of YYYY-MM-DD]

05 S7: "Every entry carries `curation.last_verified` -- the date a human last opened the cited sources and
confirmed the fields ... the site displays it on every entry". Its display thresholds, applied here at build
time and nowhere else (the site reads the state and the thresholds from this artifact, never a literal):

  | Age of last_verified           | state     | treatment                                                  |
  | < 180 days                     | neutral   | neutral text                                               |
  | 180-365 days                   | amber     | amber badge                                                |
  | > 365 days                     | red       | red badge, "not verified in over a year", demoted below    |
  |                                |           | fresher entries in default sort                            |
  | > 730 days on an active entry  | + critical| bench report staleness --critical (P5-S7-T05 routes it)    |

An entry with no last_verified at all has never been verified by a person: it is red and demoted, because
nothing is staler than never.

06 S3.0: "The build derives a per-record `source_freshness` and renders a 'last verified' badge on any record
whose sole live source has not refreshed in more than 90 days." A live source is a Source record an adapter
refreshes (the adapter's `source_id`); its refresh date is ingest-health.json's last successful fetch (07 S9.1).
An entry citing one live source is badged when that source is more than 90 days old or never fetched; an entry
citing several is badged only when none of them is fresh, since one fresh live source is a live source. The
per-source SLO badge (`stale` for a broken adapter past its window, `source-retired`) is carried onto every entry
that depends on the source, because 06 S3.0's SLO badges "every record depending on it".

Entries are the published records: every file under data/ with a `curation` block, outside the `_`-prefixed
trees (stubs, discovery candidates, ingest batches), which are never published.

`as_of` defaults to the data commit's date, as ingest_health.py's does, so the artifact is a function of the
commit and two builds of it are byte-identical.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

FORMAT = 1
ARTIFACT = os.path.join('build', 'derived', 'freshness.json')
AMBER_FROM = 180            # days since last_verified: 180-365 is amber (05 S7)
RED_AFTER = 365             # more than this is red and demoted (05 S7)
CRITICAL_AFTER = 730        # more than this on an active entry enters `bench report staleness --critical` (05 S7)
SOURCE_REFRESH_DAYS = 90    # a live source older than this badges the entries resting on it (06 S3.0)
STATES = ('neutral', 'amber', 'red')
ACTIVE = 'active'           # 05 S7: "> 730 days on an `active` benchmark"


def state(days: int | None) -> str:
    """05 S7's treatment for an age in days; None (never verified) is red."""
    if days is None or days > RED_AFTER:
        return 'red'
    return 'amber' if days >= AMBER_FROM else 'neutral'


def _published(rel: str) -> bool:
    return not any(part.startswith('_') for part in rel.split('/')[1:-1])


def entries(root: str):
    """(root-relative path, record) for every published record with a curation block, sorted by path."""
    from schema.taxonomy import read_yaml
    for full in sorted(glob.glob(os.path.join(root, 'data', '**', '*.yaml'), recursive=True)):
        rel = os.path.relpath(full, root).replace(os.sep, '/')
        if not _published(rel):
            continue
        doc = read_yaml(full)
        if isinstance(doc, dict) and isinstance(doc.get('curation'), dict):
            yield rel, doc


def _source_ids(curation: dict) -> list[str]:
    out = []
    for s in curation.get('sources') or []:                 # get-default: the schema requires it; a fixture may not
        sid = s if isinstance(s, str) else s.get('id') if isinstance(s, dict) else None
        if sid:
            out.append(sid)
    return out


def live_sources(health: dict) -> dict[str, dict]:
    """{source id: its ingest-health row} for every adapter that refreshes a Source record."""
    from tools.build import ingest_health
    ids = {cls.name: getattr(cls, 'source_id', None) for cls in ingest_health.adapters()}
    return {ids[r['adapter']]: r for r in health['sources'] if ids.get(r['adapter'])}


def source_freshness(cited: list[str], live: dict[str, dict]) -> dict | None:
    """06 S3.0's per-record source_freshness, or None for an entry that rests on no live source."""
    rows = [(sid, live[sid]) for sid in cited if sid in live]
    if not rows:
        return None
    sources = [{
        'source': sid, 'adapter': r['adapter'], 'last_successful_fetch': r['last_successful_fetch'],
        'fetch_basis': r['fetch_basis'], 'days_since_refresh': r['days_since_success'],
        'adapter_status': r['adapter_status'], 'slo_badge': r['badge'],
    } for sid, r in rows]
    fresh = [s for s in sources
             if s['days_since_refresh'] is not None and s['days_since_refresh'] <= SOURCE_REFRESH_DAYS]
    slo = sorted({s['slo_badge'] for s in sources if s['slo_badge']})
    return {'sources': sources, 'badged': not fresh, 'slo_badges': slo}


def entry(rel: str, doc: dict, live: dict[str, dict], as_of: date) -> dict:
    from tools.build.liveness import as_date
    curation = doc['curation']
    verified = as_date(curation.get('last_verified'))      # get-default: a draft carries null; the schema requires it
    days = (as_of - verified).days if verified is not None else None
    st = state(days)
    lifecycle = doc.get('lifecycle') if isinstance(doc.get('lifecycle'), str) else None  # get-default: not every kind has one
    return {
        'id': doc.get('id') or os.path.basename(rel)[:-5],  # get-default: the file stem is the id (05 S2)
        'kind': rel.split('/')[1],
        'name': doc.get('name') or doc.get('id') or os.path.basename(rel)[:-5],  # get-default: not every kind is named
        'path': rel,
        'lifecycle': lifecycle,
        'last_verified': verified.isoformat() if verified else None,
        'days_since_verified': days,
        'state': st,
        'demoted': st == 'red',
        'critical': lifecycle == ACTIVE and (days is None or days > CRITICAL_AFTER),
        'verification_status': curation.get('verification_status'),  # get-default: as the schema defaults it
        'source_freshness': source_freshness(_source_ids(curation), live),
    }


def default_order(rows: list[dict]) -> list[str]:
    """05 S7's default sort: by name, every red entry demoted below every fresher one. Stable, so a view with
    its own primary order (the browse view's) applies the same partition and keeps its order inside each half."""
    by_name = sorted(rows, key=lambda r: (r['name'].casefold(), r['id']))
    return [r['id'] for r in by_name if not r['demoted']] + [r['id'] for r in by_name if r['demoted']]


def build(root: str = ROOT, as_of: date | None = None, health: dict | None = None) -> dict:
    from tools.build import ingest_health
    as_of = as_of or ingest_health.commit_date(root)
    health = health or ingest_health.build(root, as_of)
    live = live_sources(health)
    rows = [entry(rel, doc, live, as_of) for rel, doc in entries(root)]
    return {
        'artifact': 'freshness', 'format': FORMAT, 'as_of': as_of.isoformat(),
        'thresholds': {'amber_from_days': AMBER_FROM, 'red_after_days': RED_AFTER,
                       'critical_after_days': CRITICAL_AFTER, 'source_refresh_days': SOURCE_REFRESH_DAYS},
        'states': list(STATES),
        'order': default_order(rows),
        'entries': sorted(rows, key=lambda r: r['path']),
    }


def serialise(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + '\n').encode('utf-8')


def write(root: str = ROOT, out: str | None = None, as_of: date | None = None) -> str:
    path = out or os.path.join(root, ARTIFACT)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(serialise(build(root, as_of)))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--as-of', type=date.fromisoformat, default=None, help="default: the data commit's date")
    ap.add_argument('--out', default=None, help='write here; default stdout')
    a = ap.parse_args(argv)
    if a.out:
        write(a.root, a.out, a.as_of)
    else:
        sys.stdout.buffer.write(serialise(build(a.root, a.as_of)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
