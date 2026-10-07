# ADR-0022 -- Issue intake reuses the adapter's front half, and has its own back half

- **Status:** Proposed
- **Date:** 2026-10-07
- **Taxonomy version:** not affected
- **Facet:** none -- an ingestion and contribution-path decision
- **Change type:** architecture decision recorded before the Adapter ABC is extracted (07 §11.5 step 3)
- **Supersedes:** --
- **Superseded by:** --

## Context

07 §12 leaves one question open for a spike: "whether the issue-form contribution path can reuse this
contract". It names the assumption to test: "a `FormPayload` can substitute for `Payload` in
`normalise()`, because `normalise()` takes no network and no clock, so a human-submitted form is just
another payload shape. If it holds, the validation bot reuses the gates, the resolver and the PR
generator for free."

The answer has to come before P5-S1-T08 extracts the Adapter ABC. Finding out after the contract
hardens means either a second pipeline or a refactor.

The spike is `tests/ingest/test_form_payload.py`, with 12 tests:

1. It renders a `new-benchmark.yml` submission the way GitHub renders an issue form. It uses 05 §6's
   labels verbatim and the real vocabulary.
2. It builds a `Payload` from the issue event. It then runs a `normalise()` with 07 §1.1's signature
   against the frozen resolver snapshot from P5-S1-T06.
3. It applies the existing gates in `ingest/gates.py` without changing them.

The spike code stays in the test module and is not in `ingest/`. P2-S6-T04 builds the intake bot.

## What the spike found

**The front half holds.**

- **`Payload` carries a form with no change to the dataclass:**
  - `candidate.source_key` is `issue:<n>`, `doc` holds the parsed answers and attestations, and `body`
    holds the issue body;
  - `fetched_at` is the event's `updated_at`, so no clock is read;
  - `sha256_normalised` hashes the parsed answers. An edit that leaves them alone hashes the same, and
    yields the same draft.
- **`normalise()` stays pure.** With the clock, randomness, sockets, `urlopen` and `open` patched to
  raise, 20 form payloads normalise to the same result as an unpatched run.
- **The resolver works as is.** A submission naming a benchmark we hold comes back as an `Unresolved`
  pointing at that benchmark, so the bot can redirect the contributor to the correction form.
- **`Unresolved` is the field-level error 05 §6 asks for.** The error is `reason: no-match`, the
  suggestions are the nearest vocabulary terms, and `human_task` reads "Primary domain `…` is not in the
  vocabulary. Did you mean `…`?". There is no stack trace. Its `fingerprint` is stable across re-runs,
  which is what the bot needs to replace its own previous comment.
- **Two gates apply unchanged:**
  - the derived-field guard;
  - the sanity band's check on a submitted claim value. The band's *message* sends the reader to an
    adapter's "stanza", which a contributor has never seen, so the bot has to reword it before posting.

**The back half does not hold.**

- **The provenance gate refuses every form draft.** 07 §8 requires "a complete ingestion block" on
  every record. A form record is curated, not ingested: 04 §9 calls `ingestion` "machine-written", and
  06 §1.1 Check B reads a null `ingestion` as "a hand-authored record". Giving a form draft an
  ingestion block, with a batch, an adapter and a licence class, would label a contributor's record as
  a machine's.
- **The unit guard refuses every form claim.** It reads the adapter's mapping stanza for the scale. A
  contributor's claim has no stanza, because the form states its own unit.
- **06 §1.1 Check A would fail the intake bot's PR.** Check A fails any bot-authored commit outside
  `data/_discovery/`, `data/claims/_ingested/`, `data/_ingest/` and `metrics/`. The intake bot writes
  `data/benchmarks/` (05 §6), and 08 already calls it "the one bot-authored path". The allowlist does
  not yet say so.
- **The PR generator does not fit, by design rather than by test, since it does not exist yet:**
  - 07 §6 batches one PR per source per run onto a weekly `ingest/<adapter>/<week>` branch;
  - 05 §6 needs one PR per issue on `contrib/<issue>-<slug>`, with a `Co-authored-by` trailer for the
    contributor and a comment on the issue within a minute.

  Those are different review surfaces, with different latencies.

## Decision

**The issue-intake path reuses the contract's front half and has its own back half.**

- **Reused:**
  - `Candidate`, `Payload` and `Unresolved` (and its fingerprint);
  - `normalise(payload, resolver) -> (drafts, unresolved)`, with the same purity rule;
  - the frozen `Resolver`;
  - the gates that read only a value and the vocabulary: the derived-field guard and the sanity band.
- **Its own:**
  - a curation-provenance check in place of the ingestion-provenance gate. It requires `ingestion` to
    be null (06 §1.1 Check B's mark of a hand-authored record) and `curation.verification_status` to be
    `ai-drafted-unverified` (05 §6 step 4);
  - the form's stated unit in place of the unit guard;
  - a per-issue PR writer;
  - Check A extended by exactly one named exception: the intake bot's identity on a `contrib/*` branch.

**Two changes P5-S1-T08 should make while extracting the ABC, so the front half stays shared:**

1. **Split `Payload`'s HTTP fields from the rest.** `http_status`, `etag`, `last_modified` and
   `from_cache` describe a fetch. A form fills them with placeholders: 200, None, None and False. The
   base needs `candidate`, `body`, `content_type`, `fetched_at`, `sha256_normalised` and the parsed
   views; the HTTP fields belong to a fetched subclass.
2. **Make `Draft.ingestion` optional, or name the block by kind.** A form draft has `ingestion=None`
   today, which the dataclass allows but its comment ("the `ingestion` block, owned by 04 S9") does not
   anticipate. The gates downstream must then choose the provenance check by that kind, never by
   adapter name.

## Consequences

- P2-S6-T04 (the intake bot) builds `tools/intake/` on `ingest.adapters.base` and `ingest.resolve`,
  and does not fork them.
- P5-S2-T05 (the shared gates module) keeps the ingestion-provenance gate for adapters. The
  curation-provenance check sits beside it, and the gate runner selects between them.
- 05 §9 / 06 §1.1 Check A gains its one exception when the intake bot is built, not before.
- **Observed, outside this decision:** 05 §6's `new-benchmark.yml` field list cannot by itself produce
  a valid Benchmark. Validating the spike's draft fails on four required fields:
  - `data` and `learned_entrant_evidence`, which the form never asks for;
  - `evaluation_target`, where the form offers "model / agent scaffold / full pipeline / other", not
    the schema's terms;
  - `curation`, which needs fields the bot must fill.

  P2-S6-T02 (the forms) and P2-S6-T04 must close this: add the questions, or have the bot write a
  draft that a curator completes. Otherwise the bot's `bench validate --tier schema` step fails on
  every submission.

## Alternatives considered

- **Reuse everything, giving form drafts a synthetic ingestion block.** Rejected. It passes the gate
  by making the record lie about its origin. Check B would then treat a contributor's facet as an
  adapter's, and would demand `field_provenance: curator` on every facet the contributor chose.
- **A separate pipeline for intake, sharing nothing.** Rejected. The resolver, the vocabulary errors
  and the purity rule are the expensive, correctness-critical parts, and they carry over unchanged. A
  second copy is a second place for a resolution rule to drift.
