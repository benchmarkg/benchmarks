"""The adapter contract: 07-ingestion-infrastructure.md S1.1-S1.2 (data types P3-S1-T02; the ABC P5-S1-T08).

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

It also holds the two base classes every adapter derives from. They were extracted once two adapters
existed to extract them from (07 S11.5 step 3: "Extract the Adapter ABC here, with adapters #1 and #2
refactored onto it"):

    Adapter             discover(), fetch(), normalise(); checkpoint() and finalise() have defaults
    BulkArchiveAdapter  one bundle fetch, then N logical records (07 S1.2): fetch_bundle() is the only
                        method that touches the network, and fetch() slices the bundle it returned

ingest/adapters/epoch.py is a BulkArchiveAdapter, ingest/adapters/hf_hub.py an Adapter. A concrete
adapter that leaves out one of 07 S1.1's declarations -- its name, version, licence, licence class,
attribution or seed yield band -- is refused when its class is defined, not when a run first needs the
value. So is one that would retain the raw body of a source whose licence forbids it (07 S4.4).

What the ABC does not hold yet: the runner (P5-S2), the state layer and its checkpoint file (P5-S2-T02),
and `politeness`, the per-host policy (P5-S2-T01). Until those exist, checkpoint() and finalise() work
on the in-memory state the caller saves, and `politeness` is None.

Two asks from ADR-0022 (Proposed) were weighed here. `Draft.ingestion` is now optional: a record a
person submitted is curated, not ingested, and has no ingestion block (04 S9). `Payload` keeps 07 S1.1's
fields in 07 S1.1's order: splitting its HTTP fields into a subclass changes the positional order every
caller builds it with, so it waits until the ADR is accepted and the intake bot needs it.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
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
    ingestion: dict[str, Any] | None      # the `ingestion` block, owned by 04 S9; None for a curated record
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


# ---- the Adapter ABC (P5-S1-T08; 07 S1.1, S1.2) --------------------------------------------------------

LICENCE_CLASSES = ('permissive-attribution', 'share-alike', 'non-commercial', 'no-redistribution', 'unlicensed')
# 07 S4.4: "raw_retainable = False on any adapter whose licence_class is share-alike, non-commercial,
# no-redistribution or unlicensed".
NOT_RETAINABLE = frozenset(LICENCE_CLASSES[1:])
DECLARED = ('name', 'version', 'licence', 'licence_class', 'attribution', 'expected_yield')


def _abstract(cls) -> bool:
    """Whether `cls` still has an abstract method. ABCMeta sets __abstractmethods__ only after
    __init_subclass__ has run, so it is read off the attributes themselves."""
    return any(getattr(getattr(cls, n, None), '__isabstractmethod__', False) for n in dir(cls))


class AdapterDeclarationError(TypeError):
    """A concrete adapter class without one of 07 S1.1's declarations, or with an unlawful one."""


class Adapter(ABC):
    """One source. 07 S1.1's interface: discover() what exists, fetch() it conditionally, normalise() it
    into drafts and Unresolved records, checkpoint() a long run, finalise() a finished one."""

    name: str                             # "epoch", "hf-hub", "arxiv-oai", ...
    version: str                          # bump on ANY change to normalise(); stamped per record
    licence: str                          # SPDX id or URL. An adapter with none is refused.
    licence_class: str                    # 04 S9 firewall: one of LICENCE_CLASSES
    attribution: str                      # the exact credit line this source requires
    expected_yield: tuple[int, int]       # seed band for a new adapter; adaptive after 8 runs (07 S9)
    politeness: Any = None                # the per-host policy, enforced by the fetcher (P5-S2-T01)
    volatile_fields: Sequence[str] = ()   # stripped before hashing (07 S1.5)
    raw_retainable: bool = True           # False when the licence bars us keeping the body (07 S4.4)
    caps: Mapping[str, int] = MappingProxyType({})   # per-entity-type draft caps; defaults in 07 S8

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if _abstract(cls):
            return
        missing = [a for a in DECLARED if not hasattr(cls, a)]
        if missing:
            raise AdapterDeclarationError('%s does not declare %s (07 S1.1)' % (cls.__name__, ', '.join(missing)))
        if not cls.licence:
            raise AdapterDeclarationError('%s declares no licence; an adapter with none is refused (07 S1.1)'
                                          % cls.__name__)
        if cls.licence_class not in LICENCE_CLASSES:
            raise AdapterDeclarationError('%s: licence_class %r is not one of %s (04 S9)'
                                          % (cls.__name__, cls.licence_class, ', '.join(LICENCE_CLASSES)))
        if cls.raw_retainable and cls.licence_class in NOT_RETAINABLE:
            raise AdapterDeclarationError('%s: a %s source may not retain its raw body (07 S4.4); set '
                                          'raw_retainable = False' % (cls.__name__, cls.licence_class))
        low, high = cls.expected_yield
        if not 0 <= low <= high:
            raise AdapterDeclarationError('%s: expected_yield %r is not a band' % (cls.__name__, cls.expected_yield))

    @abstractmethod
    def discover(self, state: dict) -> Iterator[Candidate]:
        """Enumerate what the source says exists, using the persisted cursor."""

    @abstractmethod
    def fetch(self, candidate: Candidate, state: dict) -> Payload | None:
        """None on a 304 or an unchanged hash."""

    @abstractmethod
    def normalise(self, payload: Payload, resolver: Any) -> tuple[list[Draft], list[Unresolved]]:
        """A pure function of (payload, resolver snapshot): no network, no clock, no randomness."""

    def checkpoint(self, state: dict, cursor: dict[str, Any]) -> None:
        """Keep a mid-run cursor in the state, which the caller persists. P5-S2-T02's runner calls this
        every 200 candidates and at 80% of --max-runtime, and writes ingest/state/<name>.json."""
        state['checkpoint'] = dict(cursor)

    def finalise(self, state: dict, report: RunReport | dict) -> None:
        """A finished run leaves no checkpoint to resume from. Writing ingest/runs/<name>/<date>.json is
        the runner's (P5-S2-T02)."""
        state['checkpoint'] = None


class BulkArchiveAdapter(Adapter):
    """One bundle fetch, then N logical records (07 S1.2). fetch() is implemented here, once, and
    touches no network: it slices the bundle discover() fetched. `--fixture` therefore swaps one call,
    fetch_bundle(), and the whole adapter runs offline."""

    bundle: Any = None

    @abstractmethod
    def fetch_bundle(self, state: dict) -> Any:
        """One conditional GET or clone: a bundle with payload_for(candidate), or None on a 304 or an
        unchanged content hash. The only method of a bundle adapter that touches the network."""

    @abstractmethod
    def enumerate(self, bundle: Any) -> Iterator[Candidate]:
        """The logical records inside the bundle. Each source_key must be unique."""

    def discover(self, state: dict) -> Iterator[Candidate]:
        self.bundle = self.fetch_bundle(state)
        if self.bundle is None:
            return iter(())
        return self.enumerate(self.bundle)

    def fetch(self, candidate: Candidate, state: dict | None = None) -> Payload | None:
        return self.bundle.payload_for(candidate)
