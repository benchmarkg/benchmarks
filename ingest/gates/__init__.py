"""The thirteen ingest gates of 07 S8, as one shared module (P5-S2-T05).

07 S8: "Every gate runs in CI on every daily run, before anything reaches the weekly branch, and a red gate
means no commit rather than a commit with a warning. A warning in a PR body is a thing humans learn to
scroll past." So a gate here has exactly three outcomes, and none of them is a warning:

    pass      the draft goes on to the next gate
    drop      the row is removed and becomes an Unresolved; the rest of the run goes on
              (referential: "the dependent record is dropped, not stubbed"; sanity band: "reject the row")
    red       the run commits nothing at all (every other gate; caps make the run `capped`, which commits
              nothing either and asks for an issue instead of a PR)

The thirteen, where each lives, and what it reads:

    schema                checks.schema            the draft, by the entity model its path names
    referential           checks.referential       the draft's refs and terms, against the tree + this run
    provenance            record.provenance        the ingestion block (07 S8's keys, the Ingestion model)
    verification-ceiling  record.verification_ceiling   a claim's rung, and its reached transcript
    derived-field         record.derived_field_guard    no build-derived field anywhere in the draft
    sanity-band           numeric.sanity_band      a claim's value against its Metric
    metric-definition     numeric.metric_definition     the claim's Metric declares range/unbounded/qualitative
    unit-guard            numeric.unit_guard       the claim's mapping stanza has an explicit scale
    caps                  checks.caps              drafts per entity type against 07 S8.1's floors and ceilings
    metadata-only         checks.metadata_only[_files]   no string over 280 chars; no data file by its magic
    attribution           checks.attribution       the adapter's credit line on every record
    licence-firewall      checks.licence_firewall, raw_retention   04 S9's placement rule; 07 S4.4's raw rule
    round-trip            checks.round_trip        re-emitting the draft through 07 S1.5's emitter changes nothing

evaluate() runs them over one run's drafts and returns a Verdict; commit() calls the writer only when the
verdict is green, so a failing gate produces zero commits by construction, not by convention.

Two scopes, stated because the gates read records and a discovery candidate is not one. A draft under
data/_discovery/ (06 S1.1) is held to its own shape by the schema gate, and to the metadata-only,
attribution, derived-field and round-trip gates; it carries no references, no claim value, and its
provenance is per suggestion, so the referential, numeric and provenance gates do not apply, and the
licence firewall lets it lie in a tree that is never published. Every other draft meets all thirteen.

The names the Phase-3 module exported (`from ingest import gates; gates.sanity_band(...)`) are all
re-exported here unchanged.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

from ingest.adapters.base import Unresolved
from ingest.gates import checks, drift  # noqa: F401  (drift: the schema-drift contract, P5-S4-T05)
from ingest.gates._common import ROOT, GateError
from ingest.gates.checks import (CAP_ROWS, MAX_PROSE, Tree, attribution, cap_for, caps, licence_firewall,  # noqa: F401
                                 metadata_only, metadata_only_files, raw_retention, referential, round_trip,
                                 schema, sniff)
from ingest.gates.numeric import (MIN_HISTORY, SIGMAS, TOLERANCE, Band, band, check, has_range,  # noqa: F401
                                  history, metric_definition, sanity_band, span, unit_guard)
from ingest.gates.record import (CEILING_RANK, DERIVED_FIELDS, PROVENANCE_KEYS, derived_field_guard,  # noqa: F401
                                 derived_fields, provenance, ranks, verification_ceiling)

GATES = ('schema', 'referential', 'provenance', 'verification-ceiling', 'derived-field', 'sanity-band',
         'metric-definition', 'unit-guard', 'caps', 'metadata-only', 'attribution', 'licence-firewall',
         'round-trip')


def document(draft) -> dict:
    """The file a draft becomes: its payload, with the ingestion block in it unless it already is, or
    unless there is none -- a curated record's (ADR-0022), or an empty one."""
    doc = dict(draft.payload)
    if draft.ingestion and 'ingestion' not in doc:
        doc['ingestion'] = draft.ingestion
    return doc


@dataclass(frozen=True)
class Failure:
    gate: str
    path: str | None
    message: str


@dataclass
class Context:
    """What the gates need to know about the run besides its drafts."""
    adapter: str                          # its name: the mapping stanzas live under ingest/mappings/<adapter>/
    licence_class: str                    # the adapter's; a record's own class wins (04 S9)
    attribution: str                      # the credit line every record must carry
    raw_retainable: bool = True
    batch: str | None = None              # the IngestBatch id this run writes; its drafts may name it
    root: str = ROOT
    allow_bulk: bool = False
    transcripts: dict = field(default_factory=dict)   # draft path -> reached Transcript (verification ceiling)
    files: list = field(default_factory=list)         # repo-relative files the run writes or keeps (metadata-only)
    retain: list = field(default_factory=list)        # raw bodies the run would keep (07 S4.4)
    mappings: str | None = None                       # the stanza root; default ingest/mappings/
    tree: Tree | None = None

    def __post_init__(self):
        self.tree = self.tree or Tree(self.root)

    @classmethod
    def of(cls, adapter, **kw) -> 'Context':
        """A Context from an Adapter's own declarations (ingest/adapters/base.py)."""
        return cls(adapter=adapter.name, licence_class=adapter.licence_class, attribution=adapter.attribution,
                   raw_retainable=adapter.raw_retainable, **kw)


@dataclass
class Verdict:
    status: str                           # green | red | capped
    passed: list = field(default_factory=list)        # drafts that may be written
    dropped: list = field(default_factory=list)       # drafts removed, each with an Unresolved
    unresolved: list = field(default_factory=list)
    failures: list = field(default_factory=list)      # Failure, for red and capped
    texts: dict = field(default_factory=dict)         # draft path -> the exact text round-trip approved

    @property
    def green(self) -> bool:
        return self.status == 'green'


def _is_discovery(rel: str) -> bool:
    from tools.validate import tiers as T
    return T.anchor(rel).startswith(checks.DISCOVERY)


def _metric(metric_id: str, root: str):
    from schema.metric import Metric
    from schema.taxonomy import read_yaml
    path = os.path.join(root, 'data', 'metrics', metric_id + '.yaml')
    return Metric.model_validate(read_yaml(path)) if os.path.exists(path) else None


def _claim_value(doc, rel, ctx: Context, history_of) -> Unresolved | None:
    """The numeric gates on one claim draft: unit guard and metric definition are red; the sanity band
    drops the row. A claim with no numeric value (qualitative) meets only the first two."""
    if ctx.mappings is not None or os.path.isdir(os.path.join(ctx.root, 'ingest', 'mappings', ctx.adapter)):
        rid = (doc.get('ingestion') or {}).get('source_record_id') or ''   # get-default: provenance reports it
        unit_guard(ctx.adapter, 'csv:' + rid.split('#', 1)[0].removesuffix('.csv'), ctx.mappings)
    metric = _metric(doc['metric'], ctx.root) if isinstance(doc.get('metric'), str) else None  # get-default: referential reports a missing metric
    if metric is None:
        return None
    metric_definition(metric)
    value = doc.get('value')                                                # get-default: a qualitative claim has none
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return sanity_band(float(value), metric, rel, history_of(metric.id))
    return None


def evaluate(drafts, ctx: Context) -> Verdict:
    """All thirteen gates over one run's drafts. Drops first (they change what the rest see), then every
    red gate on every remaining draft, then the run-level gates: caps on what is left to write, and the
    file sniff and raw-retention rule on what the run writes or keeps."""
    v = Verdict('green')
    docs = [(d.path.as_posix(), document(d), d) for d in drafts]
    histories: dict = {}

    def history_of(metric_id):
        if metric_id not in histories:
            histories[metric_id] = history(metric_id, ctx.root)
        return histories[metric_id]

    def red(gate, path, message):
        v.failures.append(Failure(gate, path, message))

    # drops: referential, and the sanity band
    drop = {rel: u for rel, u in referential([(rel, doc) for rel, doc, _ in docs], ctx.tree, ctx.batch)}
    for rel, doc, _ in docs:
        if rel in drop or _is_discovery(rel) or not (rel.startswith('data/claims/') or '/claims/' in rel):
            continue
        try:
            u = _claim_value(doc, rel, ctx, history_of)
        except GateError as e:
            red(e.gate, rel, str(e))
            continue
        if u is not None:
            drop[rel] = u
    kept = []
    for rel, doc, d in docs:
        if rel in drop:
            v.dropped.append(d)
            v.unresolved.append(drop[rel])
        else:
            kept.append((rel, doc, d))

    # the red gates, on every draft that is left
    def attempt(path, fn, *args):
        try:
            return fn(*args)
        except GateError as e:
            red(e.gate, path, str(e))
            return None

    for rel, doc, d in kept:
        gates = [(schema, doc, rel), (derived_field_guard, doc), (metadata_only, doc, rel),
                 (attribution, doc, rel, ctx.attribution), (licence_firewall, doc, rel, ctx.licence_class)]
        if not _is_discovery(rel):
            gates.append((provenance, doc))
        if isinstance(doc, dict) and 'verification' in doc:
            gates.append((verification_ceiling, doc, ctx.transcripts.get(rel), ctx.root))  # get-default: no transcript reached
        for fn, *args in gates:
            attempt(rel, fn, *args)
        text = attempt(rel, round_trip, doc, rel)
        if text is not None:
            v.texts[rel] = text
        v.passed.append(d)

    # the run-level gates
    attempt(None, metadata_only_files, ctx.files, ctx.root)
    attempt(None, raw_retention, ctx.raw_retainable, ctx.licence_class, ctx.retain)
    if v.failures:
        v.status, v.passed, v.texts = 'red', [], {}
        return v
    try:
        over = caps(Counter(d.entity_type for _, _, d in kept), ctx.tree.counts(), ctx.allow_bulk)
    except GateError as e:
        over = [str(e)]
    if over:
        v.status, v.passed, v.texts = 'capped', [], {}
        v.failures.append(Failure('caps', None, 'over the 07 S8.1 caps without --allow-bulk: %s' % ', '.join(over)))
    return v


def commit(verdict: Verdict, write) -> list:
    """`write(drafts, texts)` for a green verdict; nothing at all otherwise. Returns what write returned,
    or [] -- the zero commits a red or capped gate means (07 S8)."""
    if not verdict.green:
        return []
    return write(verdict.passed, verdict.texts)
