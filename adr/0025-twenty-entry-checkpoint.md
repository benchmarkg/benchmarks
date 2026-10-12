# ADR-0025 -- The 20-entry checkpoint: the measured rate, the copilot, and stopping rule (a)

- **Status:** Proposed -- an agent draft (P1-S3-T06). The stopping-rule decision below is the maintainer's
  (P1-S3-T07, a human gate); it counts as recorded when they close P1-S3-T07.
- **Date:** 2026-10-12
- **Taxonomy version:** not affected
- **Facet:** none. A planning decision (14-roadmap.md, "The 20-entry checkpoint" and "Stopping rules and
  re-plans")
- **Change type:** measurement and plan decision; no schema or vocabulary change
- **Supersedes:** --
- **Superseded by:** --
- **Measurements:** metrics/checkpoint-20.json, from the timing ledger metrics/curation-rate.jsonl
  (`python scripts/curation_timer.py --checkpoint`; the ledger's sha256 is in the file)

The plan names this ADR `adr/0008-twenty-entry-checkpoint.md`. ADR 0008 is the metric-rubric decision,
0009 to 0013 are reserved for other planned tasks, and 0024 is the checkpoint's schema revision, so this
is 0025 (agreed 2026-10-12).

## Context

14-roadmap.md makes the 20-entry checkpoint "the highest-leverage moment in the whole project": the plan's
per-entry curation rate (30 to 90 minutes, "this document's, and unmeasured") and its claim that the F6
copilot "roughly halves" the work are both assumptions, and every schedule figure rests on them. The
checkpoint replaces them with two measured numbers and writes them here, so the next re-plan has a
baseline. P1-S3-T01 and T02 curated twenty entries across all nineteen domain families, each timed from
first source opened to a validating, formatted file, alternating copilot on and off. P1-S3-T03 computed
the numbers; P1-S3-T04 reviewed the schema; P1-S3-T05 revised it (ADR-0024).

## The two numbers

**Median minutes per entry: 6.02** (n = 20; quartiles 4.95 and 7.60). The timing includes reading and
archiving the sources and writing the Source records.

**Copilot speedup: 0.87** (n = 10 with the copilot, 10 without; median 6.13 minutes on, 5.31 off). The
speedup is minutes without over minutes with, so 2.0 would halve the work and below 1.0 the copilot is
slower. The 90% bootstrap interval is 0.635 to 1.087 (10,000 resamples, seed 20261010), and the two
interleaved pairings give medians of 0.916 and 0.873. The interval includes 1: **the measurement shows
no speedup, and it rules out the plan's "roughly halves".** Times fell by 0.31 minutes per entry over the
sequence; the arms alternate, so that learning falls on both alike.

Both numbers carry three limits, and a re-plan that quotes them has to quote these too:

1. **The curator was an agent, not a person.** Every entry was curated by the coding agent (P1-S3-T01,
   T02). Six minutes is an agent's time with full tool access; it is not a measured human rate, and it
   does not confirm the plan's 30-minute floor for a person.
2. **The copilot was the extractive drafter**, the one that runs without an API key. It filled one to
   five of 24 drafted fields per entry and never a facet. A model-backed drafter was not measured.
3. **The entries stop short of `full`.** `versions`, `metrics` and `governance.maintainers` are empty in
   most of them (docs/checkpoint/schema-findings.md §3.1) because they need their own records first. Six
   minutes is the cost of an entry at the level these reached, not of a `full` entry.

## What the schema review changed, and what it refused

ADR-0024 applied the agreed list: a nullable lifecycle; explicit unknowns (`aggregation_policy: unknown`,
`submission_process: null`, `governance.independence_assessed`); `history[]` for dated moves and
hand-overs; `as_used[]` for a protocol run differently from its design; `paper.doi`; two mechanical
ground-truth values; the `user_simulator` condition; `rendered_url` and `extract_preprocessing` on
Sources; `data.size` as rows; a derived `license`; and the `surrogate-fit` comparability profile in place
of six forecasting waivers. 124 values in 63 files moved, by migration 0024.

It refused, or left for elsewhere:
- a program-synthesis capability (a vocabulary change; the taxonomy revision path);
- the `hosted-judge-dependency` blocker (it needs an ADR amending 02 §11's fully-automatable rule);
- a stub as a lineage target (stubs are bound to the Epoch id allocation; lineage's inline variants do
  the job);
- deleting any unused field (revisit at 100 entries);
- changing `aggregation_policy`'s `official-aggregate` default (23 entries were curated against it).

Stopping rule (b) is not triggered: the change came at entry 34, before entry 60.

## Which rows of the effort table the measurement invalidates

14-roadmap.md's "Effort sizing" table, Block A:

- **"Benchmark entry curation", 175 to 495 hours.** Its basis is the unmeasured 30-to-90-minute rate.
  The measurement does not replace that rate (limits 1 and 3), so the row is not re-cut here. What it
  invalidates is the reason for the row's range, the copilot: the plan calls the claimed halving "the
  single largest swing in the effort table", and the measured speedup is 0.87 with an interval that
  includes 1. **The row should be planned at its own rate without a copilot discount**, until a
  model-backed copilot or a human-timed sample shows otherwise.
- **"Schema, CLI, CI", 45 to 80 hours**, which includes "schema churn through the 20-entry checkpoint".
  The churn happened (ADR-0024) and is inside the row's scope. It does not invalidate it.
- No other row depends on either number.

The headline schedule ("eight to eighteen months") is unchanged: its low end assumed 30 to 45 minutes an
entry, and nothing measured here is a human rate.

## Stopping rule (a)

The trigger is a measured median above 60 minutes; the measured median is 6.02 minutes, so the rule does
not fire. `python scripts/curation_timer.py --report` prints the median beside the trigger.

**Decision: proceed at 320 entries.** Recorded 2026-10-12, from the maintainer's choice on the checkpoint
decision card (they accepted the recommendation "Proceed at 320"), before any Phase 1 entry beyond the
checkpoint's twenty was written. 02-taxonomy.md §3's allocation stands; P1-S3-T08's re-cut has nothing to cut.

## Consequences

- The plan's copilot-halving claim should be marked measured-and-not-confirmed wherever it is quoted
  (14-roadmap.md "Why the AI layer sits after public v1"); the 30-to-90-minute rate stays marked
  unmeasured for a human curator.
- A human-timed sample (a person re-curating a handful of the twenty, timed the same way) is the cheapest
  way to turn limit 1 into a number; it is not scheduled by the plan.
- Phase 1 scales from entry 35 on the revised schema.
