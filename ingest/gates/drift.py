"""The schema-drift hard-fail contract (P5-S4-T05; 07 S9.2, 06 S3.2).

07 S9.2's second failure class: "200 OK but <script id="leaderboard-data"> is gone ... Hard fail
immediately. Open an adapter-broken issue. Assert structure explicitly; never .get() with a default. This is
the class that silently corrupts data if swallowed." Four rules, one per step of the task:

  1. Each adapter declares the minimum structure it expects, per listing or file: the keys every record must
     carry and a minimum row count (`Expect`). `rows()` asserts it; nothing reads a record with a default.
  2. A zero-row response from a filter that previously returned rows is drift, not an empty result (06 S3.2:
     "A zero-row response from a filter that previously returned dozens is schema drift"). `rows()` takes
     the count the filter last returned, from the state file, and refuses a fall to zero whatever the
     declared minimum.
  3. Drift is a hard fail that commits nothing and opens `adapter-broken` (`DriftError`, `issue()`). The
     shared runner (ingest/runner/state.py) catches it, keeps nothing the run fetched, and puts the issue in
     its report; an adapter checks its whole structure before it hands out a single candidate, so there is
     nothing earlier in the run to have committed.
  4. No fallback to free-text matching (06 S3.2: "If the tag namespace is renamed, the adapter must stop
     rather than fall back to free-text matching"). A tag namespace that carried tags last run and carries
     none now has most likely been renamed; `namespaces()` stops the run rather than let the renamed tags
     drift into the unmatched pile, where no rule would ever see them again.

DriftError is a GateError (gate `schema-drift`), so `except GateError` catches it with the other gates.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ingest.gates._common import GateError

RENAME_MIN = 5               # a namespace must have carried this many tags before its vanishing means a rename


class DriftError(GateError):
    """The source is not shaped the way the adapter reads it. A hard fail: nothing is committed."""

    def __init__(self, message: str):
        super().__init__('schema-drift', message)
        self.message = message


@dataclass(frozen=True)
class Expect:
    """What one listing, file or endpoint must look like (rule 1)."""
    name: str
    required: frozenset = frozenset()   # keys every record carries
    min_rows: int = 0                   # fewer is drift even with no history


def rows(expect: Expect, records, previous: int | None = None) -> list:
    """`records` when they meet `expect`, else DriftError. `previous` is the row count this filter returned
    on its last successful run (None: never run)."""
    if not isinstance(records, list):
        raise DriftError('%s: expected a list of records, got %s' % (expect.name, type(records).__name__))
    n = len(records)
    if n == 0 and previous:
        raise DriftError('%s returned zero rows; it previously returned %d. That is schema drift, not an empty '
                         'result (06 S3.2)' % (expect.name, previous))
    if n < expect.min_rows:
        raise DriftError('%s returned %d rows; at least %d are expected (zero rows is drift, not an empty result)'
                         % (expect.name, n, expect.min_rows))
    for r in records:
        missing = sorted(expect.required - set(r)) if isinstance(r, dict) else sorted(expect.required)
        if missing:
            ident = r.get('id') if isinstance(r, dict) else r     # get-default: the id only labels the error
            raise DriftError('%s record %s lacks %s' % (expect.name, ident, missing))
    return records


def namespace_counts(tag_lists, declared) -> Counter:
    """Tags per declared namespace across a listing (`ns:value` tags; a bare tag is not namespaced)."""
    out = Counter()
    for tags in tag_lists:
        for t in tags:
            ns = t.split(':', 1)[0] if ':' in t else None
            if ns in declared:
                out[ns] += 1
    return out


def namespaces(now: Counter, before: dict | None, listing: str) -> None:
    """Rule 4: DriftError when a namespace that carried at least RENAME_MIN tags last run carries none now."""
    gone = sorted(ns for ns, n in (before or {}).items() if n >= RENAME_MIN and not now[ns])
    if gone:
        raise DriftError('%s: the tag namespace%s %s carried %s tags last run and none now -- most likely renamed. '
                         'The adapter stops rather than fall back to free-text matching (06 S3.2); declare the new '
                         'name in the crosswalk.' % (listing, 's' if len(gone) > 1 else '', ', '.join(gone),
                                                     ', '.join(str(before[ns]) for ns in gone)))


def issue(adapter: str, error: Exception, run_started: str | None = None) -> dict:
    """The adapter-broken issue a drifted run opens (07 S9.2): what a workflow passes to `gh issue create`."""
    return {
        'title': 'adapter-broken: %s -- schema drift' % adapter,
        'labels': ['adapter-broken', 'source:%s' % adapter],
        'body': ('The %s adapter stopped on schema drift%s and committed nothing.\n\n    %s\n\n'
                 'Until the adapter is fixed the last good ingest keeps serving (06 S3.1). 07 S9.2: assert the '
                 'structure explicitly; never read it with a default.'
                 % (adapter, ' in the run started %s' % run_started if run_started else '', error)),
    }
