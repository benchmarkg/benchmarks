#!/usr/bin/env python3
"""build/derived/ingest-health.json: every source's health, published (P5-S7-T03; 07 S9.1, 06 S3.0).

    bench build --derived                                   # writes it with the other derived artifacts
    python tools/build/ingest_health.py --out build/derived/ingest-health.json [--root PATH] [--as-of YYYY-MM-DD]

07 S9.1: "The build reads ingest/state/*.json and emits build/derived/ingest-health.json -- per source: last
successful fetch, last content change, current record count, licence class and attribution". 06 S3.0 makes
it public: "adapter health is not an internal alarm. It is a published field, and the SLO is stated in
public", on a /sources page with "one row per source, its licence, its attribution, its last successful
fetch and its current status".

One row per adapter the code holds (every concrete ingest.adapters Adapter), whether or not it has run:

    licence, licence_class    the Source record's (04 S9: "a field on Source carrying its own
                              licence_checked_on date, never a constant in the loader") where the adapter
                              names one, else the adapter's own declaration
    attribution               what the last successful run recorded in the state file (Epoch's is its
                              bundle README's citation, read only when a bundle is fetched), else the
                              adapter's static credit line, else null with the reason
    last_successful_fetch     state.last_success; for data fetched by hand before any scheduled run (07 S11.3's
                              phase 0), the Source record's fetched_at, with `fetch_basis` saying which
    last_content_change       state.last_change
    record_count              records in data/ the source produced: every file citing its Source record,
                              its data/_discovery/<adapter>/ candidates and data/claims/_ingested/<adapter>/
    adapter_status            ok | degraded | broken | retired (06 S3.0), or not-yet-run for an adapter with
                              no state file and no run log -- reported as such, never as ok
    badge                     what 06 S3.0's SLO makes the site show on the records: `stale` once a broken
                              Tier-1 adapter has gone two weeks (Tier-2: 30 days) without a successful run,
                              `source-retired` for a retired one, else null

How the status is read. The latest run log (ingest/runs/<adapter>/, P5-S4-T01) is the evidence; the state file
fills in when there is none. A hard fail -- schema drift above all (07 S9.2) -- is `broken`. A soft fail, or a
run the zero-yield guard alerted on (P5-S4-T02), is `degraded`. A run that worked is `ok`.

`as_of` is the date ages are counted to: the data commit's own date by default, so the artifact is a function
of the commit and two builds of it are byte-identical (12 S1.1 rule 4, as liveness.json does).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FORMAT = 1
ARTIFACT = os.path.join('build', 'derived', 'ingest-health.json')

# 06 S3.0, verbatim: the page publishes these words, not a paraphrase of them.
SLO = ('a broken Tier-1 adapter is fixed within two weeks or every record depending on it is badged stale; '
       'a broken Tier-2 adapter is badged at 30 days; a retired adapter\'s records keep their last-known values '
       'with a permanent "source retired" badge and a link to the archived snapshot.')
STALE_AFTER = {1: 14, 2: 30}          # days a broken adapter of each tier may go before its records are badged
STATUSES = ('ok', 'degraded', 'broken', 'retired', 'not-yet-run')


def adapters() -> list:
    """Every concrete Adapter class the codebase holds, by name."""
    import importlib
    import inspect
    import pkgutil

    from ingest import adapters
    from ingest.adapters import base
    # Importing registers the subclasses: every module in the package, so the list never depends on what some
    # other caller happened to import first.
    for m in pkgutil.iter_modules(adapters.__path__):
        importlib.import_module('ingest.adapters.%s' % m.name)
    found, todo = {}, list(base.Adapter.__subclasses__())
    while todo:
        cls = todo.pop()
        todo += cls.__subclasses__()
        if not inspect.isabstract(cls) and cls.__module__.startswith('ingest.adapters.'):
            found[cls.name] = cls
    return [found[n] for n in sorted(found)]


def _json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _state(root, name):
    path = os.path.join(root, 'ingest', 'state', name + '.json')
    return _json(path) if os.path.exists(path) else None


def _latest_run(root, name):
    from ingest.runner import report
    runs = report.history(name, root)
    return runs[-1] if runs else None


def _source(root, source_id):
    if not source_id:
        return None
    from schema.taxonomy import read_yaml
    hits = glob.glob(os.path.join(root, 'data', 'sources', '**', source_id + '.yaml'), recursive=True)
    return read_yaml(hits[0]) if hits else None


def record_count(root, name, source_id) -> int:
    """Records in data/ this source produced: files citing its Source record (a value, not a comment), its
    discovery candidates and its ingested claims."""
    paths = set(glob.glob(os.path.join(root, 'data', '_discovery', name, '**', '*.yaml'), recursive=True))
    paths |= set(glob.glob(os.path.join(root, 'data', 'claims', '_ingested', name, '**', '*.yaml'), recursive=True))
    if source_id:
        cite = re.compile(r'^[^#]*(?<![\w-])%s(?![\w-])' % re.escape(source_id), re.M)
        for p in glob.glob(os.path.join(root, 'data', '**', '*.yaml'), recursive=True):
            if os.path.basename(p) == source_id + '.yaml':
                continue
            with open(p, encoding='utf-8') as f:
                if cite.search(f.read()):
                    paths.add(p)
    return len(paths)


def _day(stamp) -> date | None:
    return datetime.strptime(stamp[:10], '%Y-%m-%d').date() if stamp else None


def status(cls, state, run) -> str:
    if getattr(cls, 'retired', False):
        return 'retired'
    if state is None and run is None:
        return 'not-yet-run'
    last = run.status if run is not None else None
    if last == 'hard-fail':
        return 'broken'
    if last in ('soft-fail', 'capped') or (run is not None and any('ZERO YIELD' in n for n in run.notes)):
        return 'degraded'
    if last is None and state['consecutive_failures']:
        return 'degraded'
    return 'ok'


def badge(cls, adapter_status, last_success, as_of) -> str | None:
    """06 S3.0's SLO, applied: what the records depending on this adapter are badged."""
    if adapter_status == 'retired':
        return 'source-retired'
    if adapter_status != 'broken':
        return None
    window = STALE_AFTER[getattr(cls, 'tier', 1) or 1]
    since = _day(last_success)
    return 'stale' if since is None or (as_of - since).days > window else None


def row(root, cls, as_of) -> dict:
    state, run = _state(root, cls.name), _latest_run(root, cls.name)
    source_id = getattr(cls, 'source_id', None)
    src = _source(root, source_id)
    if src is not None:
        licence, licence_class, checked = src.get('licence_spdx'), src['licence_class'], src['licence_checked_on']  # get-default: an SPDX id is optional on a Source
        licence_basis = 'source record %s' % source_id
    else:
        licence, licence_class, checked = cls.licence, cls.licence_class, None
        licence_basis = 'adapter declaration'
    recorded = (state or {}).get('attribution')                          # get-default: a run records it; none yet
    static = cls.__dict__.get('attribution') if isinstance(cls.__dict__.get('attribution'), str) else None  # get-default: a property is not static
    attribution = recorded or static
    st = status(cls, state, run)
    last_success = (state or {}).get('last_success') or (run.finished_at.strftime('%Y-%m-%dT%H:%M:%SZ')  # get-default: a never-run adapter has none
                                                           if run is not None and run.status in ('ok', 'no-change', 'partial') else None)
    fetch_basis = 'state file' if last_success else None
    if not last_success and src is not None and src.get('fetched_at'):     # get-default: optional on a Source
        # data in the tree from a by-hand fetch (07 S11.3's phase 0), before any scheduled run was logged: the
        # Source record's own fetch is the honest date, and the row says where it came from
        last_success, fetch_basis = str(src['fetched_at']).replace('+00:00', 'Z'), 'source record (a by-hand fetch)'
    return {
        'adapter': cls.name, 'adapter_version': cls.version, 'tier': getattr(cls, 'tier', None),
        'licence': licence, 'licence_class': licence_class, 'licence_checked_on': str(checked) if checked else None,
        'licence_basis': licence_basis,
        'attribution': attribution,
        'attribution_note': None if attribution else 'read from the source itself at its first successful fetch',
        'last_successful_fetch': last_success,
        'fetch_basis': fetch_basis,
        'last_content_change': (state or {}).get('last_change'),            # get-default: as above
        'days_since_success': (as_of - _day(last_success)).days if last_success else None,
        'record_count': record_count(root, cls.name, source_id),
        'adapter_status': st,
        'last_run_status': run.status if run is not None else None,
        'badge': badge(cls, st, last_success, as_of),
    }


def commit_date(root: str) -> date:
    from tools.build.liveness import commit_date as cd
    return cd(root)


def build(root: str = ROOT, as_of: date | None = None) -> dict:
    as_of = as_of or commit_date(root)
    return {'artifact': 'ingest-health', 'format': FORMAT, 'as_of': as_of.isoformat(), 'slo': SLO,
            'stale_after_days': {'tier-%d' % t: d for t, d in sorted(STALE_AFTER.items())},
            'sources': [row(root, cls, as_of) for cls in adapters()]}


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
