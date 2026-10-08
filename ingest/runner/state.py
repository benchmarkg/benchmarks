"""The state layer, the cursor and the checkpoint (P5-S2-T02; 07 S1.1, S3.2, S4).

07 S4's three layers, and which this module is:

    1  the repository       the YAML records themselves; what we know. Never duplicated here.
    2  ingest/state/<adapter>.json   THIS: committed, small, diffable -- ETags and normalised hashes, the
                            cursor, the checkpoint, 07 S7.3's absence counter, the yield history
    3  actions/cache        regenerable bulk only (clones, unpacked archives, request caches, the resolver
                            snapshot), under ingest/raw/, which is gitignored. Nothing here is written there,
                            and nothing that cannot be regenerated may live there.

The shape (07 S4), every key always present so a reader never guesses:

    adapter, adapter_version          whose state this is
    last_run, last_success, last_change, consecutive_failures
    cursor                            the adapter's own enumeration cursor (a listing ETag scheme, a date)
    checkpoint                        a partial run's resume point, or null: {after, done, run_started}
    urls                              url -> {etag, last_modified, sha256_normalised, bytes, last_fetched,
                                      last_changed}
    absences                          source key -> consecutive absences (07 S7.3)
    yield_history                     candidates seen by the last 8 complete runs (07 S9's adaptive band;
                                      ingest/runner/bands.py decides what enters it)

An adapter may keep more (hf-hub's `records`, Epoch's `etags`); load() keeps whatever it finds.

The checkpoint (07 S1.1, S3.2). run() calls the adapter's checkpoint() every CHECKPOINT_EVERY (200)
candidates, and once more when 80% of --max-runtime has gone, after which it stops and returns
status `partial`. A partial run is a normal outcome: its drafts so far are handed to the sink, its state
is saved, and `open_pr` is False -- "it commits its state file, opens no PR, and the next scheduled run
resumes". The next run passes over every candidate up to and including the checkpoint's `after` key and
carries on from there, rather than starting again.

Three rules that make a checkpoint safe rather than merely present:

  - Drafts before state. At every checkpoint the drafts produced so far go to the sink first and the
    state file is written second. fetch() records a payload's hash in the state as it fetches, so the
    other order could mark a record as seen whose draft was never written, and the next run, finding the
    hash unchanged, would never produce it.
  - A failed run keeps nothing it fetched. On an exception the in-memory state is discarded, the last
    saved file is reloaded, and only the failure is recorded on it (last_run, consecutive_failures). The
    checkpoint in that file still stands, so the next run resumes from the last safe point.
  - A cursor key that is no longer listed does not skip the run. Candidates passed over while looking for
    it are held, and if the key never appears they are processed after all: the run restarts rather
    than silently doing nothing.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from ingest.runner import bands

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(ROOT, 'ingest', 'state')
CHECKPOINT_EVERY = 200        # 07 S1.1: "every 200 candidates"
DEADLINE_FRACTION = 0.8       # 07 S1.1: "once at 80% of --max-runtime"
YIELD_RUNS = 8                # 07 S9: the band is the trailing median of the last 8 successful runs


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def path_for(adapter_name: str, root: str = ROOT) -> str:
    """ingest/state/<adapter>.json: 05 S2 owns the path."""
    return os.path.join(root, 'ingest', 'state', adapter_name + '.json')


def new(adapter_name: str, adapter_version: str, cursor=None, **extra) -> dict:
    """An empty state in 07 S4's shape, plus whatever the adapter keeps of its own."""
    state = {
        'adapter': adapter_name, 'adapter_version': adapter_version,
        'last_run': None, 'last_success': None, 'last_change': None, 'consecutive_failures': 0,
        'cursor': cursor, 'checkpoint': None, 'urls': {}, 'absences': {}, 'yield_history': [],
    }
    state.update(extra)
    return state


def load(path: str, empty: dict) -> dict:
    """The state at `path`, or `empty` when there is none yet. Keys an older file lacks are filled from
    `empty`; a file that names another adapter is refused rather than silently adopted."""
    if not os.path.exists(path):
        return empty
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    if state.get('adapter') not in (None, empty['adapter']):    # get-default: an older file may not name it
        raise ValueError('%s is the state of %r, not %r' % (path, state['adapter'], empty['adapter']))
    for k, v in empty.items():
        state.setdefault(k, v)
    return state


def dumps(state: dict) -> str:
    """Sorted JSON, LF, one final newline. A per-record map (`records`) is written one record per line,
    so a run's state diff reads as the list of records whose payload changed."""
    records = sorted((state.get('records') or {}).items())       # get-default: only some adapters keep records
    body = dict(state, urls=dict(sorted(state['urls'].items())), absences=dict(sorted(state['absences'].items())))
    if 'records' in state:
        body['records'] = {}
    text = json.dumps(body, indent=2, ensure_ascii=False, sort_keys=False)
    if records:
        lines = ',\n'.join('    %s: %s' % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False, sort_keys=True))
                           for k, v in records)
        text = text.replace('"records": {}', '"records": {\n%s\n  }' % lines, 1)
    return text + '\n'


def save(path: str, state: dict) -> None:
    """Atomically: a reader, or a run killed mid-write, sees the old file or the new one, never half."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(dumps(state))
    os.replace(tmp, path)


def problems(state: dict) -> list[str]:
    """What is wrong with a state document's shape; empty when it is 07 S4's."""
    out = []
    for k in new('', '').keys():
        if k not in state:
            out.append('missing %s' % k)
    if out:
        return out
    if not isinstance(state['urls'], dict) or not isinstance(state['absences'], dict):
        out.append('urls and absences must be maps')
    if not all(isinstance(n, int) and n > 0 for n in state['absences'].values()):
        out.append('an absence count must be a positive integer')
    if not isinstance(state['yield_history'], list) or len(state['yield_history']) > YIELD_RUNS:
        out.append('yield_history must be a list of at most %d runs' % YIELD_RUNS)
    cp = state['checkpoint']
    if cp is not None and not (isinstance(cp, dict) and {'after', 'done', 'run_started'} <= set(cp)):
        out.append('a checkpoint must carry after, done and run_started')
    return out


# ---- one run, checkpointed (07 S1.1, S3.2) ------------------------------------------------------------------

def run(adapter, state: dict, path: str, *, resolver=None, sink=None, max_runtime: float | None = None,
        every: int = CHECKPOINT_EVERY, clock=time.monotonic, now=None, log_root: str | None = None) -> dict:
    """discover(), fetch() and normalise() every candidate, checkpointing as 07 S1.1 says, and save the
    state at `path`. `sink(drafts, unresolved)` receives each batch before the state that covers it is
    written. Returns the run report: status (ok, no-change, partial or hard-fail), whether to open a PR,
    candidates seen and processed, how many were passed over on a resume, checkpoints taken, errors.

    With `log_root`, every run -- a no-change run and a failed one included -- also writes 07 S1.1's
    RunReport to <log_root>/ingest/runs/<adapter>/<date>.json (ingest/runner/report.py), and the report's
    `log` names the file."""
    now = now or (lambda: datetime.now(timezone.utc))
    sink = sink or (lambda drafts, unresolved: None)
    started, t0 = now(), clock()
    resume = state['checkpoint']
    report = {'adapter': adapter.name, 'adapter_version': adapter.version, 'started_at': iso(started),
              'status': None, 'open_pr': False, 'candidates_seen': 0, 'processed': 0, 'passed_over': 0,
              'resumed_from': resume['after'] if resume else None, 'checkpoints': 0, 'drafts': 0,
              'unresolved': 0, 'errors': [], 'notes': [], 'log': None, 'yield': None, 'alerts': []}
    pending, pending_u = [], []
    tally = {'fetched': 0, 'from_cache': 0, 'classes': {}, 'unresolved': []}
    done = resume['done'] if resume else 0
    run_started = resume['run_started'] if resume else iso(started)

    def flush():
        for d in pending:
            tally['classes'][d.change_class] = tally['classes'].get(d.change_class, 0) + 1  # get-default: a first draft of its class
        tally['unresolved'] += pending_u
        sink(list(pending), list(pending_u))
        report['drafts'] += len(pending)
        report['unresolved'] += len(pending_u)
        pending.clear()
        pending_u.clear()

    def checkpoint(after):
        flush()
        adapter.checkpoint(state, {'after': after, 'done': done, 'run_started': run_started})
        report['checkpoints'] += 1
        save(path, state)

    def process(c):
        nonlocal done
        p = adapter.fetch(c, state)
        if p is not None:
            tally['fetched'] += 1
            tally['from_cache'] += bool(p.from_cache)
            d, u = adapter.normalise(p, resolver)
            pending.extend(d)
            pending_u.extend(u)
        done += 1
        report['processed'] += 1

    try:
        held, looking = [], resume is not None
        for c in adapter.discover(state):
            report['candidates_seen'] += 1
            if looking:
                held.append(c)
                if c.source_key == resume['after']:
                    looking, held = False, []
                    report['passed_over'] = report['candidates_seen']
                continue
            process(c)
            if max_runtime is not None and clock() - t0 >= DEADLINE_FRACTION * max_runtime:
                checkpoint(c.source_key)
                report['status'] = 'partial'
                report['notes'].append('stopped at %d%% of --max-runtime %ss; the next run resumes after %s'
                                       % (DEADLINE_FRACTION * 100, max_runtime, c.source_key))
                break
            if report['processed'] % every == 0:
                checkpoint(c.source_key)
        if looking:
            report['notes'].append('the checkpoint key %r is no longer listed; the run restarted from the first '
                                   'candidate rather than skip them all' % resume['after'])
            done = 0
            for c in held:
                process(c)
    except Exception as e:  # noqa: BLE001 -- whatever failed, the rule is the same: keep nothing it fetched
        failed = load(path, new(adapter.name, adapter.version))
        failed['last_run'] = iso(now())
        failed['consecutive_failures'] = failed['consecutive_failures'] + 1
        save(path, failed)
        state.clear()
        state.update(failed)
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(now()))
        from ingest.gates import drift
        if isinstance(e, drift.DriftError):        # 07 S9.2: drift opens adapter-broken, and commits nothing
            report['alerts'].append('adapter-broken')
            report['issue'] = drift.issue(adapter.name, e.message, report['started_at'])
        _log(adapter, report, tally, resolver, started, now(), log_root)
        return report

    flush()
    finished = now()
    state['last_run'] = state['last_success'] = iso(finished)
    state['consecutive_failures'] = 0
    if report['drafts']:
        state['last_change'] = iso(finished)
    if report['status'] != 'partial':
        adapter.finalise(state, report)
        report['status'] = 'ok' if report['drafts'] else 'no-change'
        report['open_pr'] = bool(report['drafts'])
        verdict = bands.check(done, state['yield_history'], adapter.expected_yield)   # 07 S9 (P5-S4-T02)
        bands.record(state, verdict)
        report['yield'] = verdict.as_dict()
        if verdict.note():
            report['notes'].append(verdict.note())
        if verdict.alert:
            report['alerts'].append('zero-yield')
    report['finished_at'] = iso(finished)
    save(path, state)
    _log(adapter, report, tally, resolver, started, finished, log_root)
    return report


def _log(adapter, report, tally, resolver, started, finished, log_root):
    """07 S9 mechanism 1: the run's RunReport, committed whatever happened. A hard fail logs the drafts it
    had already handed the sink -- the ones before its last checkpoint -- because those were written."""
    if log_root is None:
        return
    from ingest.runner import report as R
    run_day = finished.astimezone(timezone.utc).date()
    new, carried = R.unresolved_counts(adapter.name, tally['unresolved'], run_day, log_root)
    codes = getattr(adapter, 'http_codes', None) or {}
    rr = R.build(adapter=adapter.name, adapter_version=adapter.version, started_at=started, finished_at=finished,
                 status=report['status'], http_codes=dict(codes), candidates_seen=report['candidates_seen'],
                 payloads_fetched=tally['fetched'], payloads_from_cache=tally['from_cache'],
                 drafts=tally['classes'], unresolved_new=new, unresolved_carried=carried,
                 resolver_snapshot_sha256=R.resolver_sha256(resolver), errors=report['errors'], notes=report['notes'])
    report['log'] = R.write(rr, log_root)
