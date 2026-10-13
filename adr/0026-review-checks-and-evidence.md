# ADR-0026 -- Reviewer checks, baseline and subset evidence, and schema findings leave the notes

- **Status:** Proposed -- an agent draft (P0-S9-T05). It counts as decided only when two reviewers ratify it
  (05 §5: a schema change needs two, an ADR, a migration script and a full revalidation). The maintainer chose
  this route on 2026-10-12: "audit, then route structure".
- **Date:** 2026-10-12
- **Taxonomy version:** not affected.
- **Facet:** none. Schema changes to Benchmark's curation block, Baseline and Subset (04 §5, §6, §7)
- **Change type:** schema, additive: one new list field on curation, two on Baseline, one on Subset; `Evidence`
  moves module (same shape)
- **Supersedes:** --
- **Superseded by:** --
- **Migration:** schema/migrations/0026-review-checks.py (68 rows in 34 files), plus five hand edits listed below

## Context

P0-S9-T05, the escape-hatch audit, asks whether any `notes` field in the ten stress entries does structural work
(14-roadmap Phase 0: "a `notes` field doing structural work is the tell"). Its verify bounds every `notes` and
`curation.notes` string in those entries at 200 characters; fifteen exceeded it, the longest at 2,616. The audit
(docs/schema-stress-audit.md) found three kinds of structure in them:

1. **Reviewer checks.** Every curated entry's `curation.notes` -- all 34, not only the ten -- is a list of
   questions the drafter left for the person who verifies the entry, each about one field, some needing a domain
   specialist, some resting on a source and a verbatim quote. A list of records, written as prose, where neither
   the field a check concerns nor its quote can be read or verified by anything.
2. **Schema findings.** Eight entries append a numbered list of what the schema could not say. That is about the
   schema, not the benchmark: it does not belong in the entry at all.
3. **Evidence on baselines and subsets.** `Baseline` has a `source` and no quote, and `Subset` has neither, so the
   quotes behind a baseline's or a subset's facts went into its `notes`, unverified; and `Baseline` has no subset,
   so a baseline measured on part of a benchmark said so in a note ("Baseline has no subset field, so the subset is
   stated here", PaperBench; ForecastBench's schema finding 4 is the same gap).

## Decision

**R1. `curation.review_checks[]`.** A `ReviewCheck` is `{check, field?, specialist, source?, quote?}`: the
question, verbatim; the dotted field it concerns, when it names one; whether it needs a domain specialist (05 §4's
expert-reviewed); and the source and verbatim quote it rests on, which the quote check verifies like any other
quote. A quote needs its source. A reviewer resolves a check by acting on it and deleting it. Migration 0026 moves
all 88 checks out of the 34 entries' notes; no other prose was in them, so every `curation.notes` key goes.

**R2. Schema findings leave the entries.** The 45 findings eight entries recorded are kept verbatim, by entry, in
docs/schema-findings-ledger.md, written from the notes before the migration removed them. New findings are added
there, not to an entry. The ledger decides nothing: whether a finding needs a schema change is an ADR's to say.

**R3. `Baseline.subset` and `Baseline.evidence[]`.** `subset` names the subset a baseline was measured on, when it
is not the whole version, and must belong to the baseline's own benchmark. `evidence` holds further `{source,
quote}` pairs behind the value, beside the existing `source`.

**R4. `Subset.evidence[]`.** The sources and quotes behind a subset's notes.

**R5. `Evidence` moves to schema/system.py**, below every entity module, so Baseline and Subset can use the type
Benchmark uses. Its shape and JSON Schema are unchanged.

Five notes in the stress entries are rewritten by hand into prose under 200 characters plus the new fields. Nothing
is dropped: each quote moves into `evidence` and is now verified, and one modelling judgement moves into a review
check.

- Virtual Cell Challenge `base-vcc-2026-replicate`: two quotes (src-vcc-2026-evaluation, src-vcc-2026-faq) into
  `evidence`.
- Virtual Cell Challenge `base-vcc-2026-context-mean`: the "classical-algorithm is the nearest floor kind"
  judgement becomes a review check on `baselines` (schema finding 2 in the ledger names the missing kind).
- PaperBench `base-paperbench-human-best-of-3`: `subset: paperbench#human-baseline-3`.
- PaperBench `paperbench#code-dev`: the 85% grading-cost and r = 0.48 figures gain their quotes from
  src-paperbench-arxiv-html in `evidence`.
- ARC-AGI-3 `arc-agi-3#public-demo`: the maintainers' quote (src-arc-agi-3-report-arxiv) into `evidence`.

## Consequences

- Every `notes` and `curation.notes` string in the ten stress entries is at most 200 characters, which is
  P0-S9-T05's verify.
- Seven quotes that were prose are now checked against their sources' extracts: two in review checks (CASP,
  RoboArena) and five evidence rows (Virtual Cell Challenge 2, PaperBench 2, ARC-AGI-3 1). All match.
- A verifier's work list is data: `curation.review_checks`, per field, with the specialist ones marked. A follow-up
  worth deciding (not made here): promoting an entry above `curator-reviewed` while it still holds review checks
  could be refused by a semantic rule.
- This is a schema change, so it restarts P1-S3-T09's count of entries curated since the schema last changed.
- `*_note` and `*_basis` fields are not touched: they are annotations of one field, which the schema defines
  (ADR-0001), not escape hatches.
