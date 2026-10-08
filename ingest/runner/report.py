"""The RunReport and the committed run log (P5-S4-T01; 07 S1.1, S9, S6.4).

07 S9's first mechanism, and the one the other three read: "Every adapter run writes
ingest/runs/<adapter>/<YYYY-MM-DD>.json -- the RunReport from S1.1 -- and commits it even when nothing else
changed ... Because it is in git, 'when did this adapter last actually work' is answerable by anyone with a
clone." So:

    build()        a RunReport with every one of 07 S1.1's fields populated -- http_codes, drafts by all six
                   change classes, unresolved new and carried (against the 07 S5.5 ledger), and the resolver
                   snapshot's sha256 -- and refuses one that is not
    write()        ingest/runs/<adapter>/<YYYY-MM-DD>.json, for every run whatever its status: a no-change run
                   and a failed run are exactly the records 07 S9 exists to keep. A second run on the same day
                   writes <date>.2.json beside it rather than overwrite the first: a log that loses a run is
                   not a log
    history()      every report an adapter has, oldest first, read back from the files
    last_worked()  the latest run whose status says it worked -- the question a clone must answer

Where they go (07 S6.4, exception (a)): run logs and state files "commit directly to main under ingest/**".
They are outside the citable data tree and carry `export-ignore` in .gitattributes, so no release tarball
holds them. The CODEOWNERS path rule that keeps a human edit of them reviewed is P1's (".github/CODEOWNERS",
with the review matrix), and the commit itself is the ingest workflow's (P5-S3): with Actions disabled,
nothing here pushes.

The raw store (07 S4.4): `raw_artifact()` names the CI artifact a run uploads and how long GitHub keeps it,
so that the last 8 runs per adapter survive; for an adapter whose licence bars keeping bodies it is the
headers and hashes only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, fields
from datetime import date, datetime, timezone

from ingest.adapters.base import RunReport

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'metrics-only', 'gone', 'no-change')
STATUSES = ('ok', 'no-change', 'partial', 'soft-fail', 'hard-fail', 'capped')
WORKED = ('ok', 'no-change', 'partial')       # 07 S1.1: "A partial run is a normal outcome, not an error"
RAW_RUNS_KEPT = 8                             # 07 S4.4: "Retention: the last 8 runs per adapter"
_SHA = re.compile(r'^[0-9a-f]{64}$')
_LOG = re.compile(r'^(\d{4}-\d{2}-\d{2})(?:\.(\d+))?\.json$')


class ReportError(ValueError):
    """A RunReport with a field missing or malformed: it is not written."""


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def resolver_sha256(resolver) -> str:
    """07 S1.3: the sha256 a run records for the resolver snapshot it resolved against. A frozen snapshot
    states its own (`snapshot_sha256`, or `sha256` on a frozen document); a {kind: Index} map is hashed the
    way ingest/resolve.freeze() hashes; no resolver at all is the hash of an empty snapshot, so the field is
    never blank and two resolver-less runs agree."""
    for attr in ('snapshot_sha256', 'sha256'):
        value = getattr(resolver, attr, None)
        if isinstance(value, str) and _SHA.match(value):
            return value
    if isinstance(resolver, dict) and isinstance(resolver.get('sha256'), str):   # get-default: a frozen document
        return resolver['sha256']
    indexes = {}
    if isinstance(resolver, dict):
        indexes = {k: v.snapshot() for k, v in sorted(resolver.items()) if hasattr(v, 'snapshot')}
    canon = json.dumps(indexes, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def unresolved_counts(adapter: str, items, run: date, root: str = ROOT) -> tuple[int, int]:
    """(new, carried) for this run's Unresolved items against the adapter's 07 S5.5 ledger, read only:
    recording them is the ledger's own step (ingest/unresolved.py). A reopened item counts as new -- it
    is shown in full again -- and a suppressed one (wontfix, blocked-upstream) as carried."""
    from ingest import unresolved
    d = unresolved.diff(list(items), unresolved.load(adapter, root), run)
    return len(d.new) + len(d.reopened), len(d.carried) + sum(d.suppressed.values())


def build(*, adapter: str, adapter_version: str, started_at: datetime, finished_at: datetime, status: str,
          http_codes: dict, candidates_seen: int, payloads_fetched: int, payloads_from_cache: int, drafts: dict,
          unresolved_new: int, unresolved_carried: int, resolver_snapshot_sha256: str, errors=(), notes=()) -> RunReport:
    """A RunReport, every field present and well-formed (07 S1.1), or ReportError."""
    if status not in STATUSES:
        raise ReportError('status %r is not one of %s' % (status, ', '.join(STATUSES)))
    unknown = set(drafts) - set(CHANGE_CLASSES)
    if unknown:
        raise ReportError('drafts names no change class %s' % ', '.join(sorted(unknown)))
    if not _SHA.match(resolver_snapshot_sha256 or ''):
        raise ReportError('resolver_snapshot_sha256 %r is not a sha256' % resolver_snapshot_sha256)
    counts = {'candidates_seen': candidates_seen, 'payloads_fetched': payloads_fetched,
              'payloads_from_cache': payloads_from_cache, 'unresolved_new': unresolved_new,
              'unresolved_carried': unresolved_carried}
    bad = [k for k, v in counts.items() if not isinstance(v, int) or v < 0]
    if bad:
        raise ReportError('%s must be counts' % ', '.join(bad))
    if finished_at < started_at:
        raise ReportError('the run finished before it started')
    return RunReport(
        adapter=adapter, adapter_version=adapter_version, started_at=started_at, finished_at=finished_at,
        status=status, http_codes={int(k): int(v) for k, v in sorted(http_codes.items(), key=lambda kv: int(kv[0]))},
        drafts={c: int(drafts.get(c, 0)) for c in CHANGE_CLASSES},  # get-default: a class the run drafted none of
        resolver_snapshot_sha256=resolver_snapshot_sha256, errors=list(errors), notes=list(notes), **counts)


def as_dict(report: RunReport) -> dict:
    """07 S1.1's field order; times as ISO-8601 UTC; HTTP codes as JSON keys."""
    out = asdict(report)
    out['started_at'], out['finished_at'] = iso(report.started_at), iso(report.finished_at)
    out['http_codes'] = {str(k): v for k, v in report.http_codes.items()}
    return out


def from_dict(doc: dict) -> RunReport:
    def when(s):
        return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    names = [f.name for f in fields(RunReport)]
    missing = [n for n in names if n not in doc]
    if missing:
        raise ReportError('a run log lacks %s' % ', '.join(missing))
    return build(**{n: doc[n] for n in names if n not in ('started_at', 'finished_at')},
                 started_at=when(doc['started_at']), finished_at=when(doc['finished_at']))


def runs_dir(adapter: str, root: str = ROOT) -> str:
    return os.path.join(root, 'ingest', 'runs', adapter)


def write(report: RunReport, root: str = ROOT) -> str:
    """ingest/runs/<adapter>/<YYYY-MM-DD>.json (the finishing date, UTC), or <date>.<n>.json for the n-th run of
    that day. Atomic, LF, one final newline. Returns the repository-relative path."""
    folder = runs_dir(report.adapter, root)
    os.makedirs(folder, exist_ok=True)
    day = report.finished_at.astimezone(timezone.utc).date().isoformat()
    name, n = day + '.json', 1
    while os.path.exists(os.path.join(folder, name)):
        n += 1
        name = '%s.%d.json' % (day, n)
    path = os.path.join(folder, name)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(as_dict(report), indent=2, ensure_ascii=False) + '\n')
    os.replace(tmp, path)
    return os.path.relpath(path, root).replace(os.sep, '/')


def history(adapter: str, root: str = ROOT) -> list[RunReport]:
    """Every run log the adapter has, in the order the runs happened."""
    folder = runs_dir(adapter, root)
    if not os.path.isdir(folder):
        return []
    named = []
    for n in os.listdir(folder):
        m = _LOG.match(n)
        if m:
            named.append(((m.group(1), int(m.group(2) or 1)), n))
    out = []
    for _, n in sorted(named):
        with open(os.path.join(folder, n), encoding='utf-8') as f:
            out.append(from_dict(json.load(f)))
    return out


def last_worked(adapter: str, root: str = ROOT) -> RunReport | None:
    """The latest run that worked: ok, no-change or partial. A run of 304s is a run that worked."""
    return next((r for r in reversed(history(adapter, root)) if r.status in WORKED), None)


def raw_artifact(adapter, report: RunReport, cadence_days: int = 1) -> dict:
    """The CI artifact a run uploads its raw store as (07 S4.4): its name, the path, and a retention long
    enough that the last RAW_RUNS_KEPT runs survive at the adapter's cadence. An adapter whose licence bars
    keeping bodies uploads the headers and hashes only."""
    day = report.finished_at.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return {
        'name': 'raw-%s-%s' % (adapter.name, day),
        'path': 'ingest/raw/%s/' % adapter.name,
        'exclude': [] if adapter.raw_retainable else ['**/*.body', '**/*.body.gz'],   # bodies stay behind
        'retention-days': max(1, RAW_RUNS_KEPT * cadence_days),
    }
