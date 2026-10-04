"""The adapter contract's data types: 07-ingestion-infrastructure.md S1.1 (P3-S1-T02).

Five frozen dataclasses an adapter passes around:

    Candidate   one thing the source claims exists (discover())
    Payload     the fetched bytes of one Candidate, with its parsed views (fetch())
    Unresolved  something seen, partly understood and not guessed at; `fingerprint` identifies it
                across runs and drives the lifecycle ledger (07 S5.4)
    Draft       a proposed entity or patch, already shaped like our YAML (normalise())
    RunReport   what one run did (finalise())

07 S1.1 freezes only Candidate and Payload; this module freezes all five, as the task asks, so no
stage can change what an earlier stage handed it. A field holding a list or dict is still a mutable
object, so freezing stops reassignment, not mutation in place: build the list before constructing.

There is deliberately no Adapter ABC and no runner here. 07 S11.3: phase 0 of ingestion is "a single
script ... no cron, no canary, no replay, no PR bot, no ABC", and "the Adapter ABC gets extracted when
the third adapter is written". P5-S1-T08 owns that extraction and adds it to this file.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ChangeClass = Literal['new', 'field-change', 'result-change', 'metrics-only', 'gone', 'no-change']
EntityType = Literal['benchmark', 'benchmark_version', 'system', 'organization',
                     'metric', 'leaderboard', 'source', 'claim', 'conditions']
UnresolvedReason = Literal['no-match', 'ambiguous-match', 'unparseable', 'out-of-band', 'policy']
RunStatus = Literal['ok', 'no-change', 'partial', 'soft-fail', 'hard-fail', 'capped']


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Candidate:
    """One thing the source claims exists.

    Cheap for API sources: no payload fetched yet. For a bundle-shaped source the bundle has been
    fetched once and the candidate names a logical record inside it (07 S1.2)."""
    source_key: str                       # the SOURCE's own stable identifier, verbatim, unique
    kind: EntityType
    url: str | None                       # canonical upstream URL (provenance and archiving)
    hint: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Payload:
    candidate: Candidate
    body: bytes
    content_type: str
    http_status: int
    fetched_at: datetime
    etag: str | None
    last_modified: str | None
    sha256_normalised: str                # the hash of the NORMALISED body (07 S1.5)
    from_cache: bool

    # Parsed views, filled by the adapter's own parse step so that normalise() never re-parses and
    # never sees raw bytes. A CSV record: headers and rows. JSON: doc.
    headers: Sequence[str] | None = None
    rows: Sequence[dict[str, str]] | None = None
    doc: Any | None = None


@dataclass(frozen=True)
class Unresolved:
    """Something the adapter saw, partly understood, and refuses to guess about."""
    source_key: str
    field: str
    observed: str
    reason: UnresolvedReason
    suggestions: list[tuple[str, float]] = field(default_factory=list)   # (entity_id, score)
    human_task: str = ''                  # phrased as an instruction, not a complaint

    @property
    def fingerprint(self) -> str:
        """Stable identity across runs: the first 16 hex of sha256("source_key|field|observed"). It
        reads nothing but those three, so a new suggestion or a reworded task is the same item; and it
        is the rule schema/entities.py's UnresolvedRecord checks a committed fingerprint against."""
        return sha256_hex('%s|%s|%s' % (self.source_key, self.field, self.observed))[:16]


@dataclass(frozen=True)
class Draft:
    """A proposed entity or entity patch, already shaped like our YAML."""
    entity_type: EntityType
    entity_id: str | None                 # None: the runner mints it (07 S1.4); adapters never do
    path: Path
    payload: dict[str, Any]
    change_class: ChangeClass
    ingestion: dict[str, Any]             # the `ingestion` block, owned by 04 S9
    confidence: float                     # 0..1; written to ingestion.extraction_confidence
    labels: list[str] = field(default_factory=list)   # PR labels this draft demands


@dataclass(frozen=True)
class RunReport:
    adapter: str
    adapter_version: str
    started_at: datetime
    finished_at: datetime
    status: RunStatus
    http_codes: dict[int, int]
    candidates_seen: int
    payloads_fetched: int
    payloads_from_cache: int
    drafts: dict[ChangeClass, int]
    unresolved_new: int
    unresolved_carried: int
    resolver_snapshot_sha256: str
    errors: list[str]
    notes: list[str]
