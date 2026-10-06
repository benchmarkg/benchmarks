"""The unresolved lifecycle ledger (P3-S3-T07; 07 S5.5, 04 S10).

normalise() is pure and stateless, so next week's run raises `claude-opus-4-6_120K` again, identically, forever.
Without memory, the same items reappear in full in every ingest PR until the reviewer stops reading that
section -- 07 S5.5's reason for this module. The memory is the status ledger beside the batches,
data/_ingest/unresolved/{adapter}/status.yaml (schema.entities.UnresolvedStatus), keyed by
Unresolved.fingerprint, and each run is diffed against it:

    new          a fingerprint the ledger has never held: shown IN FULL, entered as open
    reopened     a resolved (or superseded) item that is back: the resolution did not hold, so it flips to
                 open and is shown IN FULL
    carried      an open item seen again: ONE LINE for all of them -- "Carried over: 4 (oldest 65 days)"
    suppressed   wontfix and blocked-upstream: counted, never shown (07 S5.5: "suppressed from the PR body
                 entirely and surface only in the report")

Every item seen moves its row's last_seen to the run date and adds one to occurrences. A row the run does not
see is left alone: an item that stops appearing is not thereby resolved, only a person resolves it.

The backlog band: open items whose first_seen is more than BACKLOG_DAYS (90) before the run date are counted
apart (backlog(), and a line of their own in render()). 07 S5.5: "a growing unresolved backlog is a
slow-motion version of the silent failure S9 exists to catch", so it must be visible, not folded into the
carried count.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKLOG_DAYS = 90
SUPPRESSED = ('wontfix', 'blocked-upstream')
CLOSED = ('resolved', 'superseded')         # a reappearance means the closure did not hold


def ledger_path(adapter: str, root: str = ROOT) -> str:
    return os.path.join(root, 'data', '_ingest', 'unresolved', adapter, 'status.yaml')


def load(adapter: str, root: str = ROOT) -> list[dict]:
    """The ledger rows as plain mappings, validated; [] when the adapter has no ledger yet."""
    from schema.entities import UnresolvedStatusFile
    from schema.taxonomy import read_yaml
    path = ledger_path(adapter, root)
    if not os.path.exists(path):
        return []
    rows = UnresolvedStatusFile.model_validate(read_yaml(path) or []).root
    return [r.model_dump(mode='python') for r in rows]


@dataclass
class Diff:
    run: date
    new: list = field(default_factory=list)          # Unresolved items, in run order
    reopened: list = field(default_factory=list)     # Unresolved items whose closed row flipped back to open
    carried: list = field(default_factory=list)      # ledger rows (after the update), open and seen again
    suppressed: dict = field(default_factory=dict)   # status -> how many were seen this run
    rows: list = field(default_factory=list)         # the whole ledger after this run

    def backlog(self) -> list[dict]:
        return backlog(self.rows, self.run)


def diff(items, rows: list[dict], run: date) -> Diff:
    """This run's Unresolved items against the ledger. `rows` is not modified; Diff.rows is the new ledger."""
    out = Diff(run=run, suppressed={s: 0 for s in SUPPRESSED})
    by_print = {r['fingerprint']: dict(r) for r in rows}
    order = [r['fingerprint'] for r in rows]
    seen = set()
    for u in items:
        fp = u.fingerprint
        if fp in seen:                               # the same item twice in one run is one sighting
            continue
        seen.add(fp)
        row = by_print.get(fp)                       # get-default: an unseen fingerprint has no row yet
        if row is None:
            by_print[fp] = {'fingerprint': fp, 'source_key': u.source_key, 'observed': u.observed, 'field': u.field,
                            'status': 'open', 'first_seen': run, 'last_seen': run, 'occurrences': 1,
                            'note': None, 'decided_by': None, 'decided_on': None}
            order.append(fp)
            out.new.append(u)
            continue
        row['last_seen'] = max(row['last_seen'], run)
        row['occurrences'] += 1
        if row['status'] in CLOSED:
            row.update(status='open', decided_by=None, decided_on=None,
                       note=('Reopened %s: it was %s, and the run raised it again. %s'
                             % (run.isoformat(), row['status'], row['note'] or '')).strip())
            out.reopened.append(u)
        elif row['status'] in SUPPRESSED:
            out.suppressed[row['status']] += 1
        else:
            out.carried.append(row)
    out.rows = [by_print[fp] for fp in order]
    return out


def backlog(rows: list[dict], run: date, days: int = BACKLOG_DAYS) -> list[dict]:
    """Open rows first seen more than `days` before the run, oldest first."""
    old = [r for r in rows if r['status'] == 'open' and (run - r['first_seen']).days > days]
    return sorted(old, key=lambda r: (r['first_seen'], r['fingerprint']))


def _cell(s) -> str:
    return str(s if s is not None else '').replace('|', '\\|').replace('\n', ' ')


def render(d: Diff, adapter: str) -> str:
    """07 S6.3's "What the adapter could NOT resolve" section, from a Diff."""
    rel = 'data/_ingest/unresolved/%s/status.yaml' % adapter
    L = ['### What the adapter could NOT resolve', '']
    for title, items in (('New this run', d.new), ('Reopened -- a resolution that did not hold', d.reopened)):
        if not items:
            continue
        L += ['**%s (%d)**' % (title, len(items)),
              '| Observed | Field | Reason | Top suggestions | Human task |', '|---|---|---|---|---|']
        for u in items:
            sug = ', '.join('%s (%.2f)' % (e, s) for e, s in u.suggestions[:3]) or '--'
            L.append('| `%s` | %s | %s | %s | %s |' % (_cell(u.observed)[:120], _cell(u.field), u.reason, _cell(sug),
                                                   _cell(u.human_task)))
        L.append('')
    if d.carried:
        oldest = max((d.run - r['first_seen']).days for r in d.carried)
        L.append('**Carried over: %d** (oldest %d days) -> `%s`' % (len(d.carried), oldest, rel))
    else:
        L.append('**Carried over: 0**')
    L.append('**Suppressed:** %s' % ' / '.join('%d `%s`' % (d.suppressed[s], s) for s in SUPPRESSED))
    old = d.backlog()
    if old:
        L.append('**Open over %d days: %d** (oldest first seen %s) -- the backlog band (07 S5.5)'
                 % (BACKLOG_DAYS, len(old), old[0]['first_seen'].isoformat()))
    else:
        L.append('**Open over %d days: 0**' % BACKLOG_DAYS)
    return '\n'.join(L) + '\n'


HEADER = ('data/_ingest/unresolved/%s/status.yaml -- the status ledger (07 S5.5), keyed by Unresolved.fingerprint.\n'
          '# Written by ingest/unresolved.py: a run adds new items as open, moves last_seen and occurrences, and\n'
          '# reopens a resolved item that reappears. Only a person sets resolved, wontfix or blocked-upstream.')


def save(rows: list[dict], adapter: str, root: str = ROOT) -> str:
    """Write the ledger, validated first, through the corpus emitter."""
    from ingest import emit
    from schema.entities import UnresolvedStatusFile
    UnresolvedStatusFile.model_validate(rows)
    def own(v):     # a fresh object per date: the emitter would anchor (&id001) one date shared by two fields
        return date.fromordinal(v.toordinal()) if isinstance(v, date) else v
    clean = [{k: own(v) for k, v in r.items() if v is not None or k in ('note', 'decided_by', 'decided_on')}
             for r in rows]
    rel = 'data/_ingest/unresolved/%s/status.yaml' % adapter
    return emit.write(clean, rel, root, header=HEADER % adapter, replace=True)


def record(adapter: str, items, run: date, root: str = ROOT) -> tuple[Diff, str]:
    """Diff a run against the ledger, write the ledger, and return (the Diff, its PR-body section)."""
    d = diff(items, load(adapter, root), run)
    save(d.rows, adapter, root)
    return d, render(d, adapter)
