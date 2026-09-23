# 16 -- Execution Plan

[14-roadmap.md](14-roadmap.md) says what order to build in and why, in prose, at the level of
phases. This document is the same plan decomposed until every item is small enough for one
person or one agent to pick up, finish, and prove finished without asking anyone what was
meant. It is the execution surface; 14 remains the reasoning.

**This document is generated.** `execution/tasks.yaml` is the single owner of every task fact,
the same way [02-taxonomy.md](02-taxonomy.md) owns the vocabularies. Edit the YAML and re-run
`_workflow/scripts/render_execution_plan.py`; do not hand-edit this file.

---

## 1. How to execute this

Work in ascending `seq`. That field is a topological sort of `depends_on`, so when a task comes
up, every input it names has already been produced. **Document order is not safe to execute** --
it is grouped by stage for reading, and seven tasks sit before something they depend on. `seq`
exists precisely so that grouping and ordering do not have to be the same thing.

For each task in turn: read the documents in `reads`, do the `steps`, then run the `verify`
command. Set `status: done` only when that command has actually run and passed. Everything else
in the backlog is description; `verify` is the only thing that decides whether a task is
finished, and a task recorded done without it is worse than a task not started, because nothing
downstream will re-check it.

### The four executors

| Value | Who | What it means |
| --- | --- | --- |
| `agent` | An agent, alone | Does it end to end and verifies it. No review needed before the next task starts. |
| `agent-draft` | An agent, then a person | The agent produces the artifact; a human must review it before it counts as done. Almost all curation is this: an agent can find and format an entry, but whether the classification is *right* is the judgement this project exists to get right. |
| `human` | A person | Needs an account, a signature, a credential action or a legal reading. An agent cannot do it, and pretending otherwise strands the pipeline. |
| `human-gate` | A person | A decision that stops the pipeline until it is answered. Produces no artifact. |

### The ledger

`status` is the execution ledger, one of `todo`, `doing`, `blocked`, `done`. It is the only field
an executor writes. `produces` names the paths a task **creates** -- exactly one task may create
any given path -- and `modifies` names paths it edits that another task created. A task that only
edits has an empty `produces`, which is legitimate and common for shared files like the CI
workflow, which accumulates jobs from tasks across five phases.

---

## 2. The shape of the work

| Phase | Title | Stages | Tasks | Hours | `agent` | `agent-draft` | `human` | `human-gate` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **0** | Schema and taxonomy foundation | 10 | 69 | 123.5-247.5 | 39 | 26 | 3 | 1 |
| **1** | Seed the index, breadth-first | 14 | 111 | 421-906 | 24 | 78 | 5 | 4 |
| **2** | Public static site with the Atlas and detail pages | 8 | 61 | 116.5-204.5 | 51 | 5 | 4 | 1 |
| **3** | Result claims, provenance, and the Epoch ingestion adapter | 11 | 78 | 278-447 | 34 | 42 | 1 | 1 |
| **4** | Coverage, gaps, ecosystem view, release feed -> public v1 | 7 | 52 | 90-169 | 39 | 8 | 3 | 2 |
| **5** | Ingestion at scale and freshness automation | 8 | 60 | 168.5-261 | 48 | 5 | 6 | 1 |
| **6** | AI layer: semantic search and suite builder | 7 | 54 | 184-308 | 42 | 5 | 4 | 3 |
| **7** | The package - SDK, CLI and MCP server | 8 | 28 | 74.5-127 | 25 | 1 | 1 | 1 |
| **8** | Local evaluation runner, shipped in the package | 7 | 56 | 217-402 | 37 | 11 | 6 | 2 |
| **9** | Hosted API and community submissions | 7 | 29 | 84.5-142.5 | 25 | 3 | 0 | 1 |
| | **Total** | **87** | **598** | **1757.5-3214.5** | **364** | **184** | **33** | **17** |

At the [14-roadmap.md](14-roadmap.md) planning figure of 20 hours a week, the whole backlog is
**88-161 weeks**. Phases 0-4, which is everything up to public v1, are **1029-1974 hours**.

**These numbers are larger than the roadmap’s, and that is the expected direction.** 14 sizes
phases top-down from the shape of the work; this document sums them bottom-up from 598
individually estimated items, and bottom-up decomposition characteristically lands above a
top-down estimate because it makes visible the work that prose elides. Treat the gap as an input
to planning -- it says the roadmap is optimistic by roughly this factor -- rather than as a
defect in either document. The two have deliberately not been reconciled: forcing them to agree
would destroy the only independent check available on either.

The `agent-draft` count is the honest constraint on how fast this can go. 184 of 598 tasks need a
human to review the artifact before it counts, and 50 more need a human to do them outright.
Phase 1 alone is 78 `agent-draft` against 24 `agent`, which is the true shape of a curation
phase: the bottleneck is review capacity, not generation.

---

## Phase 0 -- Schema and taxonomy foundation

*10 stages, 69 tasks, 123.5-247.5 hours.*

**Goal.** The vocabularies, entities, codegen, CI gates and legal scaffolding exist and are machine-enforced, and ten deliberately hostile benchmark entries validate against them with no escape-hatch field, so every later phase inherits a settled schema instead of migrating one.

**Entry condition.** A git repository with a Python 3.12 toolchain available. Nothing else: Phase 0 has no predecessor phase and no external dependency other than network access to the registries the pins are re-verified against and to the primary sources the ten stress entries cite.

**Exit gate.** From 14-roadmap.md "Phase 0 / Exit criteria": all ten stress entries validate with zero errors and zero schema hacks; headroom returns null gracefully for WeatherBench 2, Kaggle Game Arena and RoboArena rather than erroring or silently producing a number; comparability_key is computed for all ten and two deliberately-different conditions on the same benchmark produce different keys; a schema change requires an ADR AND a migration script, with CI rejecting a schema diff without both; the quote validator rejects a deliberately fabricated quote in a fixture and sets the field to null rather than failing the whole record; LICENSE-DATA, LICENSE-CODE, REUSE.toml, CITATION.cff, SUCCESSION.md (with its invocation trigger written in) and the reserved Zenodo concept DOI exist in the repo; every version pin in the lockfile was re-verified against its registry this phase, not taken from the document.

**Parallelism.** At one person Phase 0 is close to serial and the hour total is the schedule. Four genuine entry points exist: P0-S7 (survivability) depends on nothing at all and is 4-8.5 h that blocks nothing, which is exactly why it gets deferred forever and must not be; P0-S4-T01 (pins and lockfile) depends on nothing and must run before any Python is written; P0-S10-T06 (outreach) depends only on P0-S1-T02 and should go out as early as possible because its lead time is eight weeks and the Phase 1 taxonomy freeze blocks on the answer; and P0-S10-T01/T02 (the two measurement scripts) are independent of the schema work. The critical path is S1 -> S2 -> S3 -> S4 -> S5 -> S6/S8 -> S9 -> S10-T07, and S2 is the widest single band on it (18-48.5 h). The one genuinely parallel block is S8: the seven stress entries are mutually independent once bench validate and bench new exist, so at two people one person curates S8 while the other finishes S6. Per 14-roadmap.md's own overlap argument that split only pays if one person owns curation and the other owns engineering with no shared review queue; two people both curating means nobody is building. Best-case overlap removes roughly S7 plus S10-T01/T02 plus half of S8 from the critical path, about 15-25 h of the 109-215.

### P0-S1 -- The navigational spine and its checkers

taxonomy/ exists with the domain spine, the two group vocabularies and the scripts that police them, so every later CI check has data to read.

*6 tasks, 7.5-15.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 1 | `P0-S1-T01` | Scaffold the taxonomy file set and VERSION | A | 0.5-1 | -- |
| 2 | `P0-S1-T02` | Write domains.yaml: 19 families, five gating fields, 204 subdomain stubs | A | 2-4 | `P0-S1-T01` |
| 3 | `P0-S1-T03` | Write scripts/taxonomy_stats.py with --check | A | 2-4 | `P0-S1-T02` |
| 4 | `P0-S1-T04` | Write capability_groups.yaml from D1 and lay down the 44 capability ids | A | 1-2.5 | `P0-S1-T03` |
| 5 | `P0-S1-T05` | Write domain_groups.yaml and scripts/check_display_only_vocab.py | A | 1-2 | `P0-S1-T02` |
| 6 | `P0-S1-T06` | Write homographs.yaml, retired-ids.yaml and forbidden-identifiers.yaml | A | 1-2 | `P0-S1-T02`, `P0-S1-T04` |

### P0-S2 -- The spine definitions and the remaining vocabularies

Every term a stress entry can reference carries a definition, and the 108 spine terms carry the full four-artifact treatment from 03 S5.

*7 tasks, 25-65.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 7 | `P0-S2-T01` | Author the 44 capability term records | A-d | 4.5-14.5 | `P0-S1-T04` |
| 8 | `P0-S2-T02` | Author the 27 evaluation-method term records | A-d | 2.5-9 | `P0-S1-T01` |
| 9 | `P0-S2-T03` | Author the 18 subject-under-test term records | A-d | 2-6 | `P0-S1-T01` |
| 10 | `P0-S2-T04` | Author the 19 domain-family definitions | A-d | 2-6.5 | `P0-S1-T02`, `P0-S1-T03` |
| 11 | `P0-S2-T05` | Write the six remaining facet vocabularies, definition-only | A-d | 6-10 | `P0-S1-T01` |
| 12 | `P0-S2-T06` | Write the four control files the schema reads | A-d | 1-2.5 | `P0-S1-T01` |
| 13 | `P0-S2-T07` | Author the 204 subdomain definitions | A-d | 7-17 | `P0-S1-T02`, `P0-S2-T04` |

### P0-S3 -- Three entries by hand, before the schema

Surface the schema's real field needs empirically, in the order 14-roadmap.md insists on: entries first, schema second.

*5 tasks, 7.5-12 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 14 | `P0-S3-T01` | Hand-write swe-bench.yaml with no schema in front of you | A-d | 2-3 | `P0-S2-T01`, `P0-S2-T02`, `P0-S2-T03`, `P0-S2-T05` |
| 15 | `P0-S3-T02` | Hand-write casp.yaml with no schema in front of you | A-d | 2-3 | `P0-S2-T01`, `P0-S2-T02`, `P0-S2-T03`, `P0-S2-T05` |
| 16 | `P0-S3-T03` | Hand-write roboarena.yaml with no schema in front of you | A-d | 2-3 | `P0-S2-T01`, `P0-S2-T02`, `P0-S2-T03`, `P0-S2-T05` |
| 17 | `P0-S3-T04` | Write the Source records and capture archive snapshots for the three entries | A-d | 1-2 | `P0-S3-T01`, `P0-S3-T02`, `P0-S3-T03` |
| 18 | `P0-S3-T05` | Write the field-need reconciliation list | A | 0.5-1 | `P0-S3-T01`, `P0-S3-T02`, `P0-S3-T03` |

### P0-S4 -- The canonical Pydantic schema

Pydantic 2.13.5 on Python 3.12 is the single source of truth, and every field 04 S15 calls a prerequisite exists before any ingest can run.

*10 tasks, 20-38 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 19 | `P0-S4-T01` | Pin the toolchain and re-verify every pin against its registry | A | 3-6 | -- |
| 20 | `P0-S4-T02` | Write schema/taxonomy.py | A | 1.5-3 | `P0-S4-T01`, `P0-S2-T06` |
| 21 | `P0-S4-T03` | Write schema/benchmark.py | A | 3-5 | `P0-S4-T02`, `P0-S3-T05` |
| 22 | `P0-S4-T04` | Write schema/source.py with the quote substrate | A | 1.5-3 | `P0-S4-T02` |
| 23 | `P0-S4-T05` | Write schema/system.py and schema/claim.py with the four C5 additions | A | 2-4 | `P0-S4-T03`, `P0-S4-T04` |
| 24 | `P0-S4-T06` | Write schema/conditions.py, the profile resolver and comparability_key | A | 2.5-4.5 | `P0-S4-T05`, `P0-S2-T06` |
| 25 | `P0-S4-T07` | Write the remaining nine entity models | A | 2-4 | `P0-S4-T03`, `P0-S4-T05` |
| 26 | `P0-S4-T08` | Write the tier-3 cross-field validators | A | 2-3.5 | `P0-S4-T03`, `P0-S4-T05`, `P0-S4-T06`, `P0-S4-T07` |
| 27 | `P0-S4-T09` | Write the interoperability crosswalks and adopt the external field names | A | 1.5-3 | `P0-S4-T03`, `P0-S4-T05`, `P0-S4-T06`, `P0-S4-T07` |
| 28 | `P0-S4-T10` | Reconcile the schema against the three entries and write ADR 0001 | A-d | 1-2 | `P0-S4-T03`, `P0-S4-T05`, `P0-S4-T06`, `P0-S4-T07`, `P0-S4-T08`, `P0-S3-T05` |

### P0-S5 -- Codegen, the bench CLI and the validation tiers

One command validates the corpus and one regenerates the derived artifacts, so CI can call both. Only subcommands declared in 05 S3 are built.

*8 tasks, 15.5-28.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 29 | `P0-S5-T01` | Build bench schema gen and commit the generated artifacts | A | 2-3.5 | `P0-S4-T08`, `P0-S4-T09` |
| 30 | `P0-S5-T02` | Build bench validate with the four tiers | A | 3-5 | `P0-S5-T01` |
| 31 | `P0-S5-T03` | Build bench new and the entity templates | A | 1.5-3 | `P0-S5-T02` |
| 32 | `P0-S5-T04` | Build bench fmt and --check | A | 1-2 | `P0-S5-T01` |
| 33 | `P0-S5-T05` | Build bench build (minimal) | A | 2-4 | `P0-S5-T02` |
| 34 | `P0-S5-T06` | Build the quote-substring validator | A | 1.5-3 | `P0-S5-T02`, `P0-S4-T04` |
| 35 | `P0-S5-T07` | Scaffold schema/migrations/ and bench migrate | A | 1.5-3 | `P0-S5-T02` |
| 36 | `P0-S5-T08` | Build bench check-links and the archival call it wraps | A | 3-5 | `P0-S5-T02` |

### P0-S6 -- CI: the blocking check list

05 S9's numbered check list exists as workflows, blocking, from the first pull request; this stage does not renumber it.

*7 tasks, 9-18 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 37 | `P0-S6-T01` | Wire pr-validate.yml with checks 1 to 4 | A | 1.5-3 | `P0-S5-T02`, `P0-S5-T04` |
| 38 | `P0-S6-T02` | Wire codegen-check.yml, check 5 | A | 1-2 | `P0-S5-T01`, `P0-S6-T01` |
| 39 | `P0-S6-T03` | Wire checks 6 and 9i: the verification-status gate and the drafts grep | A | 1-2 | `P0-S6-T01` |
| 40 | `P0-S6-T04` | Wire checks 7 and 8: the metadata-only invariant and the licence firewall | A | 1.5-3 | `P0-S6-T01` |
| 41 | `P0-S6-T05` | Wire checks 9, 9a, 9c, 9d and 9e | A | 2-4 | `P0-S6-T01`, `P0-S1-T06` |
| 42 | `P0-S6-T06` | Wire checks 9b, 9f, 9g and 9h | A | 1-2 | `P0-S6-T01`, `P0-S1-T03`, `P0-S1-T05` |
| 43 | `P0-S6-T07` | Wire the ADR-plus-migration gate on schema diffs | A | 1-2 | `P0-S6-T01`, `P0-S5-T07` |

### P0-S7 -- Survivability: licences, citation, DOI, succession

The two-hour job that, skipped, makes every other hour unrecoverable. It blocks nothing, which is exactly why it is scheduled early rather than left to drift.

*6 tasks, 6-13 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 44 | `P0-S7-T01` | Create LICENSE-DATA, LICENSE-CODE, REUSE.toml and .gitattributes | A | 0.5-1.5 | -- |
| 45 | `P0-S7-T02` | Write CITATION.cff | A | 0.5-1 | `P0-S7-T01` |
| 46 | `P0-S7-T03` | Write SUCCESSION.md with its invocation triggers | A-d | 1-2 | `P0-S7-T01` |
| 47 | `P0-S7-T04` | Implement the dormancy triggers and their fake-clock test | A | 1.5-3 | `P0-S7-T03`, `P0-S6-T01` |
| 48 | `P0-S7-T05` | Reserve the Zenodo concept DOI | H | 0.5-1.5 | `P0-S7-T02` |
| 49 | `P0-S7-T06` | Write GOVERNANCE.md, CODE_OF_CONDUCT.md and CHANGELOG.md | A-d | 2-4 | `P0-S7-T03` |

### P0-S8 -- The seven remaining stress entries

The schema meets the seven cases it was not designed against, each at 14-roadmap.md's own 2 to 3 hour stress-case rate.

*8 tasks, 15-23 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 50 | `P0-S8-T01` | Curate WeatherBench 2 | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 51 | `P0-S8-T02` | Curate Matbench Discovery | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 52 | `P0-S8-T03` | Curate ARC-AGI-3 | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 53 | `P0-S8-T04` | Curate Virtual Cell Challenge 2026 | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 54 | `P0-S8-T05` | Curate Kaggle Game Arena | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 55 | `P0-S8-T06` | Curate ForecastBench | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 56 | `P0-S8-T07` | Curate PaperBench | A-d | 2-3 | `P0-S5-T02`, `P0-S5-T03` |
| 57 | `P0-S8-T08` | Write the Source records and archive captures for the seven | A-d | 1-2 | `P0-S8-T01`, `P0-S8-T02`, `P0-S8-T03`, `P0-S8-T04`, `P0-S8-T05`, `P0-S8-T06`, `P0-S8-T07`, `P0-S5-T08` |

### P0-S9 -- The exit-gate instruments

Turn each of 14-roadmap.md's five technical exit criteria into a test that runs in CI, so the gate is observable rather than asserted.

*5 tasks, 5.5-11 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 58 | `P0-S9-T01` | Wire the ten stress entries as permanent CI fixtures | A | 1-2 | `P0-S8-T08`, `P0-S3-T04`, `P0-S6-T01` |
| 59 | `P0-S9-T02` | Write the headroom-null guard tests | A | 1-2 | `P0-S9-T01`, `P0-S4-T07` |
| 60 | `P0-S9-T03` | Write the comparability_key fixture tests | A | 1-2 | `P0-S9-T01`, `P0-S4-T06` |
| 61 | `P0-S9-T04` | Write the fabricated-quote fixture | A | 1-2 | `P0-S5-T06` |
| 62 | `P0-S9-T05` | Run the escape-hatch audit | A-d | 1.5-3 | `P0-S9-T01`, `P0-S8-T08` |

### P0-S10 -- Measurements, decisions and the phase gate

The measurements other documents already cite as Phase-0 deliverables, the five remaining ADRs, the outreach that carries a three-month lead time, and the gate itself.

*7 tasks, 12.5-23 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 63 | `P0-S10-T01` | Write scripts/overlap_sample.py and run it over 50 families | A-d | 5-8 | `P0-S5-T02`, `P0-S5-T08` |
| 64 | `P0-S10-T02` | Write scripts/epoch_audit.py | A | 1.5-3 | `P0-S4-T01` |
| 65 | `P0-S10-T03` | Run the engineering-design scoping survey and size the six un-estimated families | A-d | 2-4 | `P0-S1-T03`, `P0-S2-T04` |
| 66 | `P0-S10-T04` | Write ADRs 0002 to 0005 | A-d | 1.5-3 | `P0-S4-T10`, `P0-S7-T03` |
| 67 | `P0-S10-T05` | Write ADR 0006, the Papers with Code licence posture | H | 1-2 | `P0-S7-T01` |
| 68 | `P0-S10-T06` | Draft the reviewer outreach email and send the first three | H | 1-2 | `P0-S1-T02` |
| 69 | `P0-S10-T07` | Phase 0 exit gate | gate | 0.5-1 | `P0-S9-T01`, `P0-S9-T02`, `P0-S9-T03`, `P0-S9-T04`, `P0-S9-T05`, `P0-S7-T05`, `P0-S10-T05`, `P0-S1-T05` |

---

## Phase 1 -- Seed the index, breadth-first

*14 stages, 111 tasks, 421-906 hours.*

**Goal.** 320 source-verified benchmark families exist across all 19 domain families with the per-entry curation rate measured rather than estimated, and the taxonomy and gap matrix are published under CC-BY with a resolving DOI months before the catalogue.

**Entry condition.** Phase 0 complete: schema/*.py validating the ten stress entries with zero errors and zero escape-hatch fields; taxonomy/*.yaml carrying the 108 spine term records, capability_groups.yaml, domain_groups.yaml and homographs.yaml; the bench CLI's new/validate/build; tools/validate/quotes.py; CI blocking on tiers 1-3 with checks 9f, 9g and 9h green; LICENSE-DATA, LICENSE-CODE, REUSE.toml, CITATION.cff, SUCCESSION.md and the reserved Zenodo concept DOI; ADRs 0001-0006.

**Exit gate.** >=290 benchmarks (320 targeted) across 19 of 19 populated domain families, none below 12 unless muted under the floor rule; >=130 entries across the seven Core families with none below 18; zero validation errors and every quality warning triaged rather than suppressed; either a named specialist reviewer has signed off on each of three unfamiliar domains or every unsigned domain carries curation_confidence: unreviewed on every entry and in the coverage map; the schema has not changed in the last 40 entries; taxonomy/ is published with a resolving DOI and the gap-matrix preprint is posted.

**Parallelism.** P1-S1 (taxonomy) blocks all curation - critical-path dependency 1 in 14-roadmap.md - so nothing in P1-S5..P1-S11 may start before P1-S1-T07. P1-S2 (copilot, dedup, instrumentation, archival) runs fully in parallel with P1-S1: it is engineering and touches no vocabulary. P1-S4 starts in week 2 and runs across the whole phase; it is the only workstream with a three-month lead time, and P1-S4-T03 depends on P1-S3-T02 only so that two or three finished entries exist to attach to the ask. P1-S5..P1-S11 are mutually independent after the checkpoint, and within each family the tranches are strictly serial. At one person the curation stages are serial and the phase runs to the top of its 9-25 week range; per 14-roadmap.md "Overlap is a function of headcount", overlapping engineering onto curation at one person does not compress the schedule, it slows curation. At two people with a clean curation/engineering split, the split buys P1-S2 and P1-S12's tooling and the Phase 2 engineering, not the curation hours. P1-S12's sweeps each depend on the family they sweep already being curated, so they interleave with P1-S5..P1-S11 rather than following them. P1-S14-T01..T05 (the IRR round) must be initiated roughly two months before the freeze per 03 S6.5, which places them alongside the late curation stages rather than after them. Cost of parallelism: the only genuinely free parallelism is S2 against S1; everything else is either serialised by the critical path or costs curator attention, which is the binding constraint.

### P1-S1 -- Taxonomy stress corpus, classification and revision

Put the Phase 0 vocabulary through 90 real benchmarks and fix it before 300 entries are tagged against it.

*9 tasks, 47-68 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 70 | `P1-S1-T01` | Assemble the 90-benchmark taxonomy stress corpus | A-d | 4-7 | `P0-S2-T04` |
| 71 | `P1-S1-T02` | Verify every stress-corpus entry is live and primary-sourced | A-d | 5-8 | `P1-S1-T01`, `P0-S5-T08` |
| 72 | `P1-S1-T03` | Classify stress-corpus items 1-30 and log every failure | A-d | 7-9 | `P1-S1-T02` |
| 73 | `P1-S1-T04` | Classify stress-corpus items 31-60 and log every failure | A-d | 7-9 | `P1-S1-T03` |
| 74 | `P1-S1-T05` | Classify stress-corpus items 61-90 and log every failure | A-d | 7-9 | `P1-S1-T04` |
| 75 | `P1-S1-T06` | Triage the failure log and open an ADR per blocking failure | A-d | 4-6 | `P1-S1-T05`, `P0-S1-T06` |
| 76 | `P1-S1-T07` | Revise the vocabularies to v0.9 with inclusion and exclusion tests | A-d | 8-12 | `P1-S1-T06` |
| 77 | `P1-S1-T08` | Re-classify the facets the revision touched | A-d | 4-6 | `P1-S1-T07` |
| 78 | `P1-S1-T09` | Generate the 02 S3 allocation table from taxonomy/domains.yaml | A | 1-2 | `P1-S1-T07`, `P0-S1-T03` |

### P1-S2 -- Curation machinery: copilot, dedup, instrumentation, archival

Build the tools that make 320 entries affordable and make the per-entry rate measurable.

*11 tasks, 43-70 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 79 | `P1-S2-T01` | Build the F6 curation copilot as an internal draft-only script | A | 8-12 | `P0-S5-T06` |
| 80 | `P1-S2-T02` | Enforce quote-substring validation and null-on-absence in the copilot | A | 4-6 | `P1-S2-T01` |
| 81 | `P1-S2-T03` | Harden the copilot against indirect prompt injection | A | 3-5 | `P1-S2-T01` |
| 82 | `P1-S2-T04` | Assert the drafts/ boundary in CI | A | 2-4 | `P1-S2-T01`, `P0-S6-T01` |
| 83 | `P1-S2-T05` | Build F7 near-duplicate detection and calibrate its threshold | A-d | 5-8 | `P1-S2-T01` |
| 84 | `P1-S2-T06` | Build the per-entry curation timing ledger | A | 2-3 | -- |
| 85 | `P1-S2-T07` | Publish entries-per-week throughput in the repository | A | 2-4 | `P1-S2-T06` |
| 86 | `P1-S2-T08` | Wire the rolling archival budget and its cursor | A | 4-6 | -- |
| 87 | `P1-S2-T09` | Build the seed-progress and floor-rule checkers | A | 3-5 | `P1-S1-T09` |
| 88 | `P1-S2-T10` | Build bench promote, bench resolve and bench tag-gap | A | 6-10 | `P1-S2-T05`, `P0-S5-T02` |
| 89 | `P1-S2-T11` | Build the coarse-grid gap emitter and bench gaps | A | 4-7 | `P1-S2-T09`, `P0-S1-T04`, `P0-S5-T01` |

### P1-S3 -- The 20-entry checkpoint

Replace the two estimates the whole schedule rests on with measurements, and revise the schema while migration still costs an afternoon.

*9 tasks, 25-51 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 90 | `P1-S3-T01` | Curate checkpoint entries 1-10, alternating copilot on and off | A-d | 5-12 | `P1-S1-T07`, `P1-S2-T02`, `P1-S2-T06`, `P1-S2-T09` |
| 91 | `P1-S3-T02` | Curate checkpoint entries 11-20, alternating copilot on and off | A-d | 5-12 | `P1-S3-T01` |
| 92 | `P1-S3-T03` | Compute the measured per-entry median and the copilot speedup | A | 2-3 | `P1-S3-T02` |
| 93 | `P1-S3-T04` | Collect the schema defects the first twenty entries exposed | A-d | 3-5 | `P1-S3-T02` |
| 94 | `P1-S3-T05` | Apply the schema revision with a migration script and an ADR | A-d | 4-8 | `P1-S3-T04`, `P0-S5-T07` |
| 95 | `P1-S3-T06` | Write the 20-entry checkpoint ADR with both measured numbers | A-d | 2-3 | `P1-S3-T03`, `P1-S3-T05` |
| 96 | `P1-S3-T07` | Run stopping-rule (a): decide whether to re-cut to 270 entries | gate | 1-2 | `P1-S3-T06` |
| 97 | `P1-S3-T08` | Re-cut and republish the seed allocation if the gate fired | A | 2-4 | `P1-S3-T07` |
| 98 | `P1-S3-T09` | Freeze the schema and arm stopping rule (b) | A | 1-2 | `P1-S3-T05`, `P0-S6-T01` |

### P1-S4 -- Domain reviewer recruitment and the unreviewed-badging gate

Start a three-month-lead-time human workstream in week 2 and make an unanswered email cost a badge rather than the schedule.

*9 tasks, 24-40 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 99 | `P1-S4-T01` | Draft the reviewer outreach email carrying both asks | A-d | 2-3 | -- |
| 100 | `P1-S4-T02` | Build the priority-ordered reviewer contact list | A-d | 3-5 | -- |
| 101 | `P1-S4-T03` | Send the first three approaches in week 2 | H | 2-3 | `P1-S4-T01`, `P1-S4-T02`, `P1-S3-T02` |
| 102 | `P1-S4-T04` | Stand up the reviewer tracker and the credit mechanism | A-d | 2-3 | `P1-S4-T01`, `P0-S1-T01`, `P0-S7-T02`, `P1-S4-T03` |
| 105 | `P1-S4-T05` | Generate the per-domain review packet | A | 3-5 | `P1-S4-T04`, `P1-S5-T01` |
| 106 | `P1-S4-T06` | Send the remaining four approaches and run the follow-up cadence | H | 4-8 | `P1-S4-T03`, `P1-S4-T05` |
| 107 | `P1-S4-T07` | Record reviewer sign-off and promote the reviewed entries | A-d | 3-6 | `P1-S4-T06` |
| 103 | `P1-S4-T08` | Implement the unreviewed badge and the Gap Finder refusal | A | 4-6 | `P1-S4-T04`, `P0-S1-T01`, `P1-S2-T11` |
| 108 | `P1-S4-T09` | Run stopping-rule (d) ten weeks after outreach began | gate | 1 | `P1-S4-T06`, `P1-S4-T08`, `P1-S4-T07` |

### P1-S5 -- Core curation A: robotics-embodiment and biology-genetics

Seed the two hardest and least-indexed Core families to their targets of 25 each.

*6 tasks, 23.5-70.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 104 | `P1-S5-T01` | Curate robotics-embodiment to 9 entries | A-d | 4-12 | `P1-S3-T07`, `P1-S3-T09` |
| 109 | `P1-S5-T02` | Curate robotics-embodiment to 17 entries | A-d | 4-12 | `P1-S5-T01` |
| 110 | `P1-S5-T03` | Curate robotics-embodiment to 25 entries | A-d | 4-12 | `P1-S5-T02` |
| 111 | `P1-S5-T04` | Curate biology-genetics to 9 entries | A-d | 3.5-10.5 | `P1-S3-T07`, `P1-S3-T09` |
| 112 | `P1-S5-T05` | Curate biology-genetics to 17 entries | A-d | 4-12 | `P1-S5-T04` |
| 113 | `P1-S5-T06` | Curate biology-genetics to 25 entries | A-d | 4-12 | `P1-S5-T05` |

### P1-S6 -- Core curation B: chemistry-materials, medicine-health, physics

Seed three Core families to 20, 20 and 18 against their stated curation difficulties.

*6 tasks, 28.5-85.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 114 | `P1-S6-T01` | Curate chemistry-materials to 10 entries | A-d | 4.5-13.5 | `P1-S3-T07`, `P1-S3-T09` |
| 115 | `P1-S6-T02` | Curate chemistry-materials to 20 entries | A-d | 5-15 | `P1-S6-T01` |
| 116 | `P1-S6-T03` | Curate medicine-health to 10 entries | A-d | 5-15 | `P1-S3-T07`, `P1-S3-T09` |
| 117 | `P1-S6-T04` | Curate medicine-health to 20 entries | A-d | 5-15 | `P1-S6-T03` |
| 118 | `P1-S6-T05` | Curate physics to 9 entries | A-d | 4.5-13.5 | `P1-S3-T07`, `P1-S3-T09` |
| 119 | `P1-S6-T06` | Curate physics to 18 entries | A-d | 4.5-13.5 | `P1-S6-T05` |

### P1-S7 -- Core curation C: earth-climate, audio-speech, and the Core gate

Finish the Core seven and prove the 130/144 gate mechanically.

*6 tasks, 20.5-58.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 120 | `P1-S7-T01` | Curate earth-climate to 9 entries | A-d | 4-12 | `P1-S3-T07`, `P1-S3-T09` |
| 121 | `P1-S7-T02` | Curate earth-climate to 18 entries | A-d | 4.5-13.5 | `P1-S7-T01` |
| 122 | `P1-S7-T03` | Curate audio-speech to 9 entries | A-d | 4.5-13.5 | `P1-S3-T07`, `P1-S3-T09` |
| 123 | `P1-S7-T04` | Curate audio-speech to 18 entries | A-d | 4.5-13.5 | `P1-S7-T03` |
| 124 | `P1-S7-T05` | Run the 100-entry subdomain-emptiness checkpoint | A | 2-4 | `P1-S7-T04` |
| 125 | `P1-S7-T06` | Assert the Core-seven gate | A | 1-2 | `P1-S5-T06`, `P1-S6-T06`, `P1-S7-T04`, `P1-S2-T09` |

### P1-S8 -- Non-Core hand-curate: vision, multimodal, engineering-design

Seed the three hand-curate families outside the Core, with vision deliberately capped.

*9 tasks, 26-76 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 126 | `P1-S8-T01` | Extend the engineering-design survey against real instances | A-d | 2-5 | `P0-S10-T03`, `P1-S1-T07`, `P1-S2-T09` |
| 127 | `P1-S8-T02` | Decide whether engineering-design curates or mutes | gate | 1-2 | `P1-S8-T01` |
| 128 | `P1-S8-T03` | Curate engineering-design to 6 entries | A-d | 3-9 | `P1-S8-T02`, `P1-S3-T01` |
| 129 | `P1-S8-T04` | Curate engineering-design to 12 entries | A-d | 3-9 | `P1-S8-T03`, `P1-S3-T01` |
| 130 | `P1-S8-T05` | Curate vision to 8 entries | A-d | 4-12 | `P1-S3-T07`, `P1-S3-T09` |
| 131 | `P1-S8-T06` | Curate vision to 15 entries | A-d | 3.5-10.5 | `P1-S8-T05` |
| 132 | `P1-S8-T07` | Curate vision to 22 entries | A-d | 3.5-10.5 | `P1-S8-T06` |
| 133 | `P1-S8-T08` | Curate multimodal to 6 entries | A-d | 3-9 | `P1-S3-T07`, `P1-S3-T09` |
| 134 | `P1-S8-T09` | Curate multimodal to 12 entries | A-d | 3-9 | `P1-S8-T08` |

### P1-S9 -- Mixed posture: agents-tooluse, safety-alignment, society-econ-law

Seed the three mixed-posture families, ingesting the catalogue and hand-curating the conditions.

*6 tasks, 25-75 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 135 | `P1-S9-T01` | Curate agents-tooluse to 10 entries | A-d | 4.5-13.5 | `P1-S3-T07`, `P1-S3-T09` |
| 136 | `P1-S9-T02` | Curate agents-tooluse to 20 entries | A-d | 5-15 | `P1-S9-T01` |
| 137 | `P1-S9-T03` | Curate safety-alignment to 9 entries | A-d | 4.5-13.5 | `P1-S3-T07`, `P1-S3-T09` |
| 138 | `P1-S9-T04` | Curate safety-alignment to 18 entries | A-d | 4.5-13.5 | `P1-S9-T03` |
| 139 | `P1-S9-T05` | Curate society-econ-law to 7 entries | A-d | 3-9 | `P1-S3-T07`, `P1-S3-T09` |
| 140 | `P1-S9-T06` | Curate society-econ-law to 14 entries | A-d | 3.5-10.5 | `P1-S9-T05` |

### P1-S10 -- Ingest-then-verify A: code, language, mathematics

Catalogue the saturated families richly and add the lineage nobody else models.

*6 tasks, 20.5-61.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 141 | `P1-S10-T01` | Curate code to 8 entries | A-d | 3.5-10.5 | `P1-S3-T07`, `P1-S3-T09` |
| 142 | `P1-S10-T02` | Curate code to 16 entries | A-d | 4-12 | `P1-S10-T01` |
| 143 | `P1-S10-T03` | Curate language to 7 entries | A-d | 3.5-10.5 | `P1-S3-T07`, `P1-S3-T09` |
| 144 | `P1-S10-T04` | Curate language to 14 entries | A-d | 3.5-10.5 | `P1-S10-T03` |
| 145 | `P1-S10-T05` | Curate mathematics to 6 entries | A-d | 3-9 | `P1-S3-T07`, `P1-S3-T09` |
| 146 | `P1-S10-T06` | Curate mathematics to 12 entries | A-d | 3-9 | `P1-S10-T05` |

### P1-S11 -- Ingest-then-verify B: reasoning-general, games-planning, general-intelligence

Finish the six ingest-then-verify families, sweeping general-intelligence completely.

*6 tasks, 17-51 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 147 | `P1-S11-T01` | Curate reasoning-general to 6 entries | A-d | 3-9 | `P1-S3-T07`, `P1-S3-T09` |
| 148 | `P1-S11-T02` | Curate reasoning-general to 12 entries | A-d | 3-9 | `P1-S11-T01` |
| 149 | `P1-S11-T03` | Curate games-planning to 6 entries | A-d | 2.5-7.5 | `P1-S3-T07`, `P1-S3-T09` |
| 150 | `P1-S11-T04` | Curate games-planning to 12 entries | A-d | 3-9 | `P1-S11-T03` |
| 151 | `P1-S11-T05` | Curate general-intelligence to 6 entries | A-d | 2.5-7.5 | `P1-S3-T07`, `P1-S3-T09` |
| 152 | `P1-S11-T06` | Curate general-intelligence to 12 entries | A-d | 3-9 | `P1-S11-T05` |

### P1-S12 -- Surveys, not-applicable triage, and the sweeps that run during the build

Make an empty cell a sourced claim rather than a blank, and keep discovery running while curation runs.

*9 tasks, 52-75 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 153 | `P1-S12-T01` | Write the sweep checklist and the generated hub list | A-d | 3-5 | `P1-S1-T09` |
| 154 | `P1-S12-T02` | Run the first quarterly sweep: robotics-embodiment and agents-tooluse | A-d | 8-10 | `P1-S12-T01`, `P1-S5-T03`, `P1-S9-T02` |
| 155 | `P1-S12-T03` | Run the first quarterly sweep: vision and medicine-health | A-d | 8-10 | `P1-S12-T01`, `P1-S8-T07`, `P1-S6-T04`, `P1-S12-T02` |
| 156 | `P1-S12-T04` | Run the quarterly code sweep and the annual lineage pass | A-d | 6-9 | `P1-S12-T01`, `P1-S10-T06`, `P1-S11-T02`, `P1-S10-T01`, `P1-S10-T03`, `P1-S12-T02` |
| 157 | `P1-S12-T05` | Run the semi-annual sweep: chemistry-materials, biology-genetics, earth-climate | A-d | 6-9 | `P1-S12-T01`, `P1-S6-T02`, `P1-S5-T06`, `P1-S7-T02`, `P1-S12-T02` |
| 158 | `P1-S12-T06` | Run the semi-annual sweep: audio-speech, physics, safety-alignment | A-d | 6-9 | `P1-S12-T01`, `P1-S7-T04`, `P1-S6-T06`, `P1-S9-T04`, `P1-S12-T02` |
| 159 | `P1-S12-T07` | Run the semi-annual sweep: society-econ-law, games-planning, multimodal | A-d | 6-9 | `P1-S12-T01`, `P1-S9-T06`, `P1-S11-T04`, `P1-S8-T09`, `P1-S12-T02` |
| 160 | `P1-S12-T08` | Write dated survey notes for every surveyed-and-empty subdomain | A-d | 5-8 | `P1-S7-T05`, `P0-S5-T05` |
| 161 | `P1-S12-T09` | Triage the declared-not-applicable coverage cells | A-d | 4-6 | `P1-S12-T08` |

### P1-S13 -- Verification, promotion and the phase exit gate

Move the whole corpus to primary-source-verified and prove every Phase 1 exit criterion mechanically.

*8 tasks, 32-53 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 162 | `P1-S13-T01` | Promote every Core-seven entry to primary-source-verified | A-d | 8-14 | `P1-S7-T06` |
| 163 | `P1-S13-T02` | Promote every non-Core entry to primary-source-verified | A-d | 8-14 | `P1-S8-T09`, `P1-S9-T06`, `P1-S10-T06`, `P1-S11-T06`, `P1-S13-T01` |
| 164 | `P1-S13-T03` | Clear the archival backlog and assert one archived source per entry | A | 3-5 | `P1-S2-T08`, `P1-S13-T02` |
| 165 | `P1-S13-T04` | Triage every outstanding quality warning | A-d | 5-8 | `P1-S13-T02` |
| 166 | `P1-S13-T05` | Run the whole-corpus near-duplicate sweep and resolve it | A-d | 4-6 | `P1-S2-T05`, `P1-S13-T02`, `P1-S2-T10` |
| 167 | `P1-S13-T06` | Assert the floor rule and the 290/130 launch gates | A | 1-2 | `P1-S13-T02`, `P1-S2-T09` |
| 168 | `P1-S13-T07` | Assert the schema has not moved in the last 40 entries | A | 1 | `P1-S13-T02` |
| 169 | `P1-S13-T08` | Hold the Phase 1 exit review | gate | 2-3 | `P1-S13-T03`, `P1-S13-T04`, `P1-S13-T05`, `P1-S13-T06`, `P1-S13-T07`, `P1-S4-T09` |

### P1-S14 -- Taxonomy v1.0.0 freeze, CC-BY DOI release and the gap-matrix preprint

Make the first public act of the project happen months before the catalogue: a citable taxonomy and a sourced gap matrix.

*11 tasks, 37-71 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 170 | `P1-S14-T01` | Draw the 30-item IRR sample and prepare the blind instrument | A | 2-4 | `P1-S13-T02` |
| 171 | `P1-S14-T02` | Run the human second-rater round | H | 3-5 | `P1-S14-T01`, `P1-S4-T07` |
| 172 | `P1-S14-T03` | Run the LLM taxonomy drift check as a defect detector | A | 2-4 | `P1-S14-T01` |
| 173 | `P1-S14-T04` | Compute per-facet agreement and triage every disagreement | A-d | 3-5 | `P1-S14-T02` |
| 174 | `P1-S14-T05` | Fix the failing definitions and re-run the affected facets | A-d | 4-8 | `P1-S14-T04` |
| 175 | `P1-S14-T11` | Draw the 204 subdomain examples from catalogued entries | A-d | 7-17 | `P0-S2-T07`, `P1-S13-T06` |
| 176 | `P1-S14-T06` | Freeze taxonomy v1.0.0 and turn the examples gate blocking | A-d | 5-9 | `P1-S14-T05`, `P1-S14-T11`, `P1-S13-T06` |
| 177 | `P1-S14-T07` | Cut the CC-BY taxonomy release and mint its Zenodo DOI | H | 2-4 | `P1-S14-T06`, `P0-S7-T02` |
| 178 | `P1-S14-T08` | Compute the domain x capability-group gap matrix at the seed corpus | A | 3-5 | `P1-S12-T09`, `P1-S4-T08`, `P1-S13-T06` |
| 179 | `P1-S14-T09` | Write the gap-matrix preprint with its four worked examples | A-d | 5-8 | `P1-S14-T08` |
| 180 | `P1-S14-T10` | Post the preprint and record its citation handle | H | 1-2 | `P1-S14-T09`, `P1-S14-T07`, `P0-S7-T02` |

---

## Phase 2 -- Public static site with the Atlas and detail pages

*8 stages, 61 tasks, 116.5-204.5 hours.*

**Goal.** The catalogue becomes a public, citable, accessible static site: detail pages that render with JavaScript disabled, faceted browse and search, the Atlas with a proved drift gate, the design system enforced in CI, and a contribution path an outsider can use without git.

**Entry condition.** Phase 1 has exited: >=290 benchmarks, 19 of 19 domain families populated, zero validation errors, the schema unchanged over the last 40 entries, and taxonomy/ published with a resolving DOI. At two people on a clean curation/engineering split, the engineering half may start once the catalogue passes 100 entries; at one person this does not start until Phase 1 exits.

**Exit gate.** All eight exit criteria in 14-roadmap.md Phase 2 are green with a linked CI run, or explicitly waived with a recorded reason: landing page interactive < 2.0 s on a mid-tier mobile over simulated 4G; JS on any detail page = 0 KB, Atlas route <= 120 KB gzipped, detail page total weight <= 120 KB including fonts, enforced by size-limit and failing the job; the Atlas holds its frame budget while panning and while a facet filter is applied at 1,500+ nodes, measured nightly against a fixed synthetic 2,000-node corpus; client-side full-text search returns a first result in < 100 ms in the same nightly run; every benchmark has a stable citable URL that renders with JavaScript disabled; Atlas clustering produces visually obvious domain structure; the CI drift gate has failed at least once on a deliberate perturbation and an atlas_epoch.yaml bump has cleared it once; Axe/Pa11y pass with zero WCAG 2.2 AA violations across the eight archetype pages, the Atlas and facet UI are fully keyboard-operable including the non-drag selection path (SC 2.5.7), and check_contrast.py is green in both themes; and an outsider has successfully added a benchmark through the issue form without touching git.

**Parallelism.** At ONE PERSON this phase is strictly serial and runs to the upper end of every estimate; 14-roadmap.md's "Overlap is a function of headcount, not of scheduling" says so explicitly and this decomposition does not argue with it. At TWO PEOPLE on the curation/engineering split, the engineering person takes S1 then S3 while the second takes S2 then S5, with S4 going to whoever finishes first; that is the only configuration in which Phase 2 runs alongside Phase 1 at all. S6 is nearly independent of the view work — only T05 (the correction deep-link) and T08 (the outsider test) reach into S3 and S7 — so it is the natural thing to pick up whenever the view work blocks. The three human tasks with real lead time (P2-S7-T01 the Cloudflare account and domain, P2-S6-T03 the bot credential, P2-S6-T06 the repository settings) should be started in week one regardless of what else is happening, because nothing in S6 or S7 can be tested until they land and none of them is on anyone's critical path until it is. The genuine serialisation points are exactly three: P2-S1-T02 gates everything that reads an artifact; P2-S2-T01 gates every component and every design lint; and P2-S7-T02 gates P2-S5-T08, P2-S8-T05 and P2-S8-T06, because none of them can be measured against a deployment that does not exist. Within S5, T01–T04 (the shipping pack Atlas) and T05–T07 (the UMAP machinery and its gate) are independent of each other until T08 needs both, so a second person can take the UMAP branch without blocking the view.

### P2-S1 -- Build pipeline and site skeleton

The build emits the site's data artifacts and Astro renders from generated types.

*6 tasks, 9-16 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 181 | `P2-S1-T01` | Scaffold the Astro app with pinned toolchain and explicit compressHTML | A | 1-2 | -- |
| 182 | `P2-S1-T02` | Implement the S8 emitter for facets.json, corpus.json and enums.json | A | 3-5 | `P0-S4-T07`, `P1-S13-T02`, `P0-S1-T05`, `P0-S5-T05` |
| 183 | `P2-S1-T03` | Consume the generated TypeScript types in the site | A | 0.5-1.5 | `P2-S1-T01`, `P0-S5-T01`, `P0-S6-T02` |
| 184 | `P2-S1-T04` | Add the --data-only and --routes-from-diff build modes | A | 2-3 | `P2-S1-T01`, `P2-S1-T02` |
| 185 | `P2-S1-T05` | Emit build-manifest.json and the three artifact URL namespaces | A | 1.5-2.5 | `P2-S1-T02` |
| 186 | `P2-S1-T06` | Generate index.sqlite at build time and keep it out of the browser | A | 1-2 | `P2-S1-T02` |

### P2-S2 -- The design system, implemented

design/tokens.yaml is the single source of colour and type, and five CI gates keep it that way.

*8 tasks, 14.5-26.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 187 | `P2-S2-T01` | Author design/tokens.yaml and generate tokens.css and tokens.json | A-d | 2-4 | `P0-S5-T05` |
| 188 | `P2-S2-T02` | Implement scripts/check_contrast.py as a blocking gate | A | 1.5-2.5 | `P2-S2-T01` |
| 189 | `P2-S2-T03` | Rewrite scripts/check_palette.py with assertion groups A-F | A | 2.5-4 | `P2-S2-T01` |
| 190 | `P2-S2-T04` | Add the three JS lint gates: tokens, absence and SVG | A | 1.5-3 | `P2-S2-T01` |
| 191 | `P2-S2-T05` | Self-host and subset the IBM Plex faces with metric-matched fallbacks | A | 1.5-3 | -- |
| 192 | `P2-S2-T06` | Build the component inventory from 09 section 6 | A | 3-5 | `P2-S2-T01`, `P2-S2-T04` |
| 193 | `P2-S2-T07` | Implement the three-state theme toggle and the pre-paint theme script | A | 1.5-3 | `P2-S2-T01` |
| 212 | `P2-S2-T08` | Calibrate the delta-E floor against real renders and record it | A-d | 1-2 | `P2-S2-T03`, `P2-S4-T04`, `P2-S5-T02` |

### P2-S3 -- The citable surface: detail pages and narrative routes

Every entity has a permanent URL that a crawler, an archiver and a screen reader can read with JavaScript switched off.

*8 tasks, 18-30 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 194 | `P2-S3-T01` | Build the V6 benchmark detail page, zero JS, all eighteen sections | A | 4-6 | `P2-S1-T03`, `P2-S2-T06` |
| 195 | `P2-S3-T02` | Implement the provenance drill-down as native <details> | A | 2-3 | `P2-S3-T01` |
| 196 | `P2-S3-T03` | Write the build-time SVG chart and lineage generator in Python | A | 3-5 | `P2-S1-T02`, `P2-S2-T04` |
| 197 | `P2-S3-T04` | Build the system, organization and metric detail routes | A | 1.5-3 | `P2-S3-T01` |
| 198 | `P2-S3-T05` | Publish the taxonomy term routes, the methodology pages and /api/ | A-d | 2-3.5 | `P2-S3-T01` |
| 199 | `P2-S3-T06` | Emit croissant-benchmark JSON-LD per benchmark and validate it in CI | A | 2.5-4 | `P2-S1-T02`, `P2-S3-T01` |
| 200 | `P2-S3-T07` | Build the citation block, the export formats and the page footer | A | 1.5-3 | `P2-S3-T01` |
| 201 | `P2-S3-T08` | Add version-pinned detail views and tombstone redirects | A | 1.5-2.5 | `P2-S3-T01` |

### P2-S4 -- Browse, facets and search

The workhorse view: a facet rail, a result list, and a search box that answers on every keystroke.

*8 tasks, 17-29.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 202 | `P2-S4-T01` | Pre-render the single-facet browse pages | A | 1.5-2.5 | `P2-S1-T02`, `P2-S2-T06` |
| 203 | `P2-S4-T02` | Build the bitset facet index, the query pipeline and its latency benchmark | A | 3-5 | `P2-S1-T02` |
| 204 | `P2-S4-T03` | Canonicalise filter state in the query string | A | 1-2 | `P2-S4-T02` |
| 205 | `P2-S4-T04` | Build the V11 browse view: facet rail, result list, live counts | A | 3-5 | `P2-S4-T02`, `P2-S4-T03`, `P2-S2-T06` |
| 206 | `P2-S4-T05` | Make the browse view work at phone width | A | 1.5-3 | `P2-S4-T04` |
| 207 | `P2-S4-T06` | Wire Pagefind in both modes into one index | A | 2.5-4 | `P2-S3-T01`, `P2-S3-T05`, `P2-S4-T01` |
| 208 | `P2-S4-T07` | Add the search UI and its no-JS degradation | A | 1.5-3 | `P2-S4-T06`, `P2-S4-T04` |
| 209 | `P2-S4-T08` | Build the landing page | A | 3-5 | `P2-S4-T02`, `P2-S2-T03` |

### P2-S5 -- The Atlas

A hero view stable by construction, keyboard-operable, and whose drift gate has been proved in both directions.

*9 tasks, 21.5-35 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 210 | `P2-S5-T01` | Implement the deterministic pack layout and emit atlas.json | A | 2.5-4 | `P2-S1-T02` |
| 211 | `P2-S5-T02` | Build the sigma.js Atlas island | A | 4-6 | `P2-S5-T01`, `P2-S2-T06` |
| 213 | `P2-S5-T03` | Build the linearised family index that is legend, fallback and a11y path | A | 2.5-4 | `P2-S5-T01`, `P2-S5-T02` |
| 214 | `P2-S5-T04` | Add the non-drag selection path required by SC 2.5.7 | A | 2-3 | `P2-S5-T02`, `P2-S5-T03` |
| 215 | `P2-S5-T05` | Fit and commit the frozen SVD basis | A | 1.5-3 | `P2-S1-T02`, `P1-S13-T02` |
| 216 | `P2-S5-T06` | Implement the warm-start UMAP, Procrustes alignment and drift gate | A | 4-7 | `P2-S5-T05` |
| 217 | `P2-S5-T07` | Build the layout-epoch ledger and its banner | A | 2-3 | `P2-S5-T06` |
| 228 | `P2-S5-T08` | Prove the drift gate and the epoch escape on a real build | A | 1-2 | `P2-S5-T06`, `P2-S5-T07`, `P2-S7-T02` |
| 218 | `P2-S5-T09` | Calibrate and apply the legibility gate | A-d | 2-3 | `P2-S5-T01`, `P2-S5-T06` |

### P2-S6 -- The non-PR contribution path

An outsider fixes a field or adds a benchmark without cloning anything, and the path is tested with a real outsider.

*8 tasks, 12-20.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 219 | `P2-S6-T01` | Generate the issue-form dropdowns from taxonomy/*.yaml | A | 1.5-2.5 | `P0-S2-T06`, `P0-S6-T02` |
| 220 | `P2-S6-T02` | Author the five issue forms | A | 1.5-2.5 | `P2-S6-T01` |
| 221 | `P2-S6-T03` | Provision the uaibi-bot identity | H | 0.5-1 | -- |
| 222 | `P2-S6-T04` | Build the issue-intake validation bot | A | 4-6 | `P2-S6-T02`, `P2-S6-T03`, `P0-S5-T02` |
| 223 | `P2-S6-T05` | Deep-link 'Suggest a correction' from every entity page | A | 0.5-1 | `P2-S6-T02`, `P2-S3-T01` |
| 224 | `P2-S6-T06` | Set branch protection, CODEOWNERS and the review matrix | H | 1-2 | `P2-S6-T04` |
| 225 | `P2-S6-T07` | Write CONTRIBUTING.md in the prescribed order | A-d | 1.5-2.5 | `P2-S6-T02`, `P2-S6-T04` |
| 229 | `P2-S6-T08` | Run the outsider test end to end | H | 1.5-3 | `P2-S6-T04`, `P2-S6-T05`, `P2-S6-T07`, `P2-S7-T02` |

### P2-S7 -- Hosting, deploy and previews

A push to main deploys, and every PR, including one from a fork, gets a preview a reviewer can read.

*5 tasks, 8-14 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 226 | `P2-S7-T01` | Stand up the Cloudflare Workers project and the domain | H | 1-2 | -- |
| 227 | `P2-S7-T02` | Wire deploy.yml to build in Actions and deploy with wrangler | A | 2-3 | `P2-S7-T01`, `P2-S1-T02`, `P2-S3-T01`, `P2-S5-T06` |
| 230 | `P2-S7-T03` | Wire the fork-safe preview deploy | A | 2.5-4 | `P2-S7-T02`, `P0-S6-T01` |
| 231 | `P2-S7-T04` | Assert the build-time and file-count budgets in CI | A | 1.5-3 | `P2-S7-T02`, `P0-S6-T01` |
| 232 | `P2-S7-T05` | Measure the cold and warm build at ~200 entries and adopt or void the budget table | A | 1-2 | `P2-S7-T02`, `P2-S3-T01`, `P2-S4-T01`, `P2-S7-T04` |

### P2-S8 -- Performance, accessibility and the phase gate

Every exit criterion has a job that proves it, and a human decides whether Phase 3 starts.

*9 tasks, 16.5-33 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 233 | `P2-S8-T01` | Enforce the per-route size budgets with size-limit | A | 1.5-2.5 | `P2-S3-T01`, `P2-S4-T04`, `P2-S5-T02`, `P0-S6-T01` |
| 234 | `P2-S8-T02` | Add the no-JS render gate | A | 1.5-3 | `P2-S3-T01`, `P2-S4-T01`, `P2-S5-T03` |
| 235 | `P2-S8-T03` | Define the eight archetype pages and build the accessibility harness | A | 2-4 | `P2-S3-T01`, `P2-S3-T05`, `P2-S4-T04`, `P2-S5-T02`, `P0-S6-T01` |
| 236 | `P2-S8-T09` | Remediate every WCAG 2.2 AA violation the archetype audit reports | A | 3-8 | `P2-S8-T03`, `P2-S2-T01`, `P2-S2-T07` |
| 237 | `P2-S8-T04` | Test keyboard operability of the Atlas and the facet UI | A | 1.5-3 | `P2-S5-T03`, `P2-S5-T04`, `P2-S4-T04` |
| 238 | `P2-S8-T05` | Stand up Lighthouse CI against a committed budget and baseline | A | 2-3.5 | `P2-S7-T02` |
| 239 | `P2-S8-T06` | Build the nightly Playwright performance harness | A | 2.5-4 | `P2-S5-T02`, `P2-S4-T07`, `P2-S7-T02`, `P2-S8-T05` |
| 240 | `P2-S8-T07` | Verify every benchmark has a citable URL that renders without JavaScript | A | 1-2 | `P2-S8-T02`, `P2-S3-T01`, `P2-S3-T07` |
| 241 | `P2-S8-T08` | Hold the Phase 2 exit review | gate | 1.5-3 | `P2-S5-T08`, `P2-S5-T09`, `P2-S6-T08`, `P2-S8-T01`, `P2-S8-T03`, `P2-S8-T04`, `P2-S8-T05`, `P2-S8-T06`, `P2-S8-T07` |

---

## Phase 3 -- Result claims, provenance, and the Epoch ingestion adapter

*11 stages, 78 tasks, 278-447 hours.*

**Goal.** Every number in the index carries its conditions and its provenance: the Epoch corpus is ingested in bulk and badged honestly, 110-160 claims are hand-curated with at least 60 from non-LLM domains, and the build refuses to compare claims whose conditions differ.

**Entry condition.** Phase 0 exited: the four C5 schema additions, the `ingestion` block and `IngestBatch`, the alias tables and resolution rule, `Baseline`, `Metric.optimum/unbounded/range`, `taxonomy/thresholds.yaml`, CI tiers 1-3, and `bench validate|build|archive|resolve` all exist (04 §15 items 1-21). Phase 1 exited: >=290 benchmarks across 19 populated domain families with Core families at 18+, so every benchmark a claim points at already exists, and the eight non-LLM sources of record are curated entries. Phase 2's Astro build pipeline and benchmark detail pages exist -- required only by stage S10, so S1-S9 may start before Phase 2 finishes.

**Exit gate.** 14-roadmap.md §"Phase 3 -- Exit criteria, and a restated target", in full: >=130 claims at `condition_completeness` >= 0.6, each with a named source and an archived URL, of which >=60 are from non-LLM domains; the full Epoch bulk ingest present, segregated under `data/claims/_ingested/epoch/`, badged, with its mean `condition_completeness` published whatever it turns out to be; the four verification rules accounting for all 6,598 rows with the `unmatched` count published; every claim carrying exactly one source and one conditions record; conflicting claims rendering side by side without the index adjudicating; a cross-condition comparison producing a field-level diff warning rather than a ranking; headroom `null` with a stated machine-readable reason wherever it is undefined, with the reason distribution published; and no automated dedupe having run, near-duplicates surfaced in a quality dashboard instead.

**Parallelism.** Two independent tracks after entry, and they are exactly the curation/engineering split 14-roadmap.md §"Overlap is a function of headcount" describes. ENGINEERING TRACK: S1 -> S2 -> S3 -> S4, then S9 (once S6 lands) -> S10. CURATION TRACK: S5 and S6, then S7 and S8, which run concurrently with each other and internally parallel across families. The only hard cross-track edges are S10-T01/T02 -> S4-T08 (completeness is per-profile, so the profile lookup must exist before the ingest can report its own completeness), S4-T08 -> S5-T05 (picking the thinnest-conditioned benchmarks needs the ingest measured) and S4-T08 -> S10-T07. At two people this compresses the phase to roughly the engineering track plus the tail of S8, about 9-13 weeks. AT ONE PERSON THE TRACKS SERIALISE and the total is the upper end: 14-roadmap.md is explicit that context-switching between curating a robotics entry and debugging an adapter is not parallelism, it is the same hours plus the switching cost, and that overlapping engineering onto curation slows curation rather than compressing the schedule. Within S7 and S8, the per-family batches are independent of each other once their S6 anchors task is done, so a second curator can be added at any point without re-sequencing. S2-T03/T04 (79 stanzas) and S3-T05 (927 aliases) are the two tasks that most reward a second pair of hands and least reward AI assistance, because both are dominated by human adjudication.

### P3-S1 -- Adapter spine, batch provenance, and the offline fixture

The Epoch bundle is fetched conditionally, hashed and recorded as an IngestBatch, with nothing yet written to data/.

*7 tasks, 21-33 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 242 | `P3-S1-T01` | Assert the pre-ingest schema prerequisites are present | A | 2-4 | `P0-S4-T05` |
| 243 | `P3-S1-T02` | Write the minimum adapter base types | A | 3-5 | `P3-S1-T01` |
| 244 | `P3-S1-T03` | Implement the ETag-conditional bundle fetch over an offline fixture | A | 3-5 | `P3-S1-T02` |
| 245 | `P3-S1-T04` | Emit the IngestBatch record | A | 3-4 | `P3-S1-T03`, `P0-S5-T02` |
| 246 | `P3-S1-T05` | Deterministic YAML emitter and round-trip gate | A | 2-3 | `P3-S1-T02` |
| 247 | `P3-S1-T06` | Wire `bench ingest epoch` | A | 3-4 | `P3-S1-T04`, `P3-S1-T05` |
| 248 | `P3-S1-T07` | Build bench report completeness, conflicts and quality | A | 5-8 | `P3-S1-T04`, `P0-S5-T02` |

### P3-S2 -- Mapping stanzas, the unit traps, and the benchmark stubs

All 80 per-benchmark CSVs have an explicit column mapping with an explicit scale, and the ~81 Epoch benchmarks exist as human-id'd stubs.

*7 tasks, 22-36 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 249 | `P3-S2-T01` | Extend epoch_audit.py into a header-signature census | A | 2-3 | `P0-S10-T02` |
| 250 | `P3-S2-T02` | Model and load the mapping stanza, with no default scale | A | 2-3 | `P3-S1-T02` |
| 251 | `P3-S2-T03` | Author the 59 metadata-covered stanzas | A-d | 5-8 | `P3-S2-T01`, `P3-S2-T02` |
| 252 | `P3-S2-T04` | Hand-map the 21 orphan files | A-d | 5-9 | `P3-S2-T03` |
| 253 | `P3-S2-T05` | Model the four non-ratio metrics | A-d | 2-3 | `P3-S2-T01`, `P0-S5-T02` |
| 254 | `P3-S2-T06` | Implement the unit, metric-definition and sanity-band gates | A | 3-5 | `P3-S2-T02`, `P3-S2-T05` |
| 255 | `P3-S2-T07` | Allocate ids and emit the ~81 benchmark stubs | A-d | 3-5 | `P3-S2-T01`, `P0-S5-T02`, `P0-S5-T05` |

### P3-S3 -- The identity-resolution crosswalk

Every Epoch model string resolves to an existing entity or becomes a human task; an adapter never creates an entity. This is the phase's named risk and the largest manual cost in the ingest.

*7 tasks, 30-58 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 256 | `P3-S3-T01` | Census the identity population | A | 2-3 | `P3-S2-T01` |
| 257 | `P3-S3-T02` | Implement resolution steps 1-4 with `extracts` routing | A | 4-6 | `P3-S1-T02` |
| 258 | `P3-S3-T03` | Calibrate the fuzzy scorer against 100 hand-labelled pairs | A-d | 4-6 | `P3-S3-T02` |
| 259 | `P3-S3-T04` | Generate the System, SystemVersion and Organization entities | A-d | 6-10 | `P3-S3-T01`, `P0-S5-T02` |
| 260 | `P3-S3-T05` | Author data/aliases/systems.yaml | A-d | 8-24 | `P3-S3-T03`, `P3-S3-T04`, `P1-S2-T10` |
| 261 | `P3-S3-T06` | Author the benchmark and organization alias tables | A-d | 3-5 | `P3-S3-T02`, `P3-S2-T07` |
| 262 | `P3-S3-T07` | Build the unresolved lifecycle ledger | A | 3-4 | `P3-S3-T02`, `P3-S2-T04` |

### P3-S4 -- The bulk run: verification by rule, gates, and honest badging

6,598 claims land segregated under data/claims/_ingested/epoch/, badged by rule, with the rule accounting and the mean condition completeness published.

*8 tasks, 22-33 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 263 | `P3-S4-T01` | Implement the structural transcript check and the verification rule | A-d | 3-4 | `P3-S1-T03` |
| 264 | `P3-S4-T02` | Implement the verification-ceiling and provenance gates | A | 3-4 | `P3-S4-T01`, `P3-S2-T06` |
| 265 | `P3-S4-T03` | Publish the four-rule row accounting and the unmatched count | A | 2-3 | `P3-S4-T01` |
| 266 | `P3-S4-T04` | Compute the near-duplicate signature, with no dedupe | A | 3-4 | `P3-S3-T05` |
| 267 | `P3-S4-T05` | Archive the 74 distinct Source link targets | A-d | 3-5 | `P3-S3-T04`, `P0-S5-T08` |
| 268 | `P3-S4-T06` | Execute the one-off bulk ingest | A-d | 4-6 | `P3-S2-T04`, `P3-S3-T05`, `P3-S4-T02`, `P3-S4-T03` |
| 269 | `P3-S4-T07` | Spot-check ten transcripts | H | 1-2 | `P3-S4-T06`, `P3-S1-T07` |
| 299 | `P3-S4-T08` | Compute and publish condition_completeness for the ingest | A | 3-5 | `P3-S4-T06`, `P3-S10-T02`, `P0-S5-T05` |

### P3-S5 -- Hand-curated LLM claims, chosen adversarially (50-80)

The LLM half of the hand-curated target, every cluster chosen because it breaks something Epoch's primary key cannot express.

*7 tasks, 39-62 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 270 | `P3-S5-T01` | Curate the arc_agi claude-opus-4-6_120K cluster (5 claims) | A-d | 3-5 | `P0-S4-T07`, `P1-S11-T04`, `P3-S1-T07` |
| 271 | `P3-S5-T02` | Curate the falcon-7b MMLU six-way conflict (6 claims) | A-d | 4-6 | `P0-S4-T07`, `P3-S1-T07`, `P3-S2-T07`, `P3-S3-T04` |
| 272 | `P3-S5-T03` | Curate SWE-bench Verified across three or four scaffolds | A-d | 4-6 | `P0-S4-T07`, `P3-S1-T07`, `P3-S2-T07`, `P3-S3-T04` |
| 273 | `P3-S5-T04` | Curate the science-adjacent bridge claims (12-15) | A-d | 10-14 | `P0-S4-T07`, `P3-S1-T07`, `P3-S2-T07`, `P3-S3-T04` |
| 300 | `P3-S5-T05` | Curate frontier claims where Epoch's conditions are thinnest (12-18) | A-d | 9-15 | `P3-S4-T08`, `P3-S5-T04` |
| 301 | `P3-S5-T06` | Curate the remainder to reach the 50-80 band | A-d | 7-13 | `P3-S5-T05`, `P3-S5-T04` |
| 302 | `P3-S5-T07` | Archive and verification sweep over the hand-curated LLM set | A-d | 2-3 | `P3-S5-T06`, `P3-S5-T02` |

### P3-S6 -- Non-LLM anchors, metrics and comparability profiles (eight families)

Before a single non-LLM claim is written, each family's source of record has its Metric records, its Baseline anchors and its comparability profile, because headroom is undefined without them.

*8 tasks, 20-35 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 274 | `P3-S6-T01` | Matbench Discovery: six metrics, compliance tiers, anchors | A-d | 3-5 | `P1-S6-T02`, `P3-S2-T05` |
| 275 | `P3-S6-T02` | Open Catalyst (OC20/OC22/OCx24): metrics, hidden splits, anchors | A-d | 2-4 | `P1-S6-T02`, `P3-S2-T05`, `P3-S6-T01` |
| 276 | `P3-S6-T03` | CASP / CAMEO: per-category metrics and the human-expert split | A-d | 3-5 | `P1-S5-T06`, `P3-S2-T05` |
| 277 | `P3-S6-T04` | WeatherBench 2: lead time, operational ceiling, no-aggregate flag | A-d | 3-5 | `P1-S7-T02`, `P3-S2-T05`, `P3-S6-T01` |
| 278 | `P3-S6-T05` | RoboArena and the robotics cluster: pairwise, sim and embodiment | A-d | 3-5 | `P1-S5-T03`, `P3-S2-T05` |
| 279 | `P3-S6-T06` | Grand Challenge subset: per-challenge metrics and access gating | A-d | 2-4 | `P1-S6-T04`, `P3-S2-T05` |
| 280 | `P3-S6-T07` | DCASE and Open ASR: one name over seven tasks, annual eval sets | A-d | 2-4 | `P1-S7-T04`, `P3-S2-T05` |
| 281 | `P3-S6-T08` | The Well / PDEBench / FAIR Universe: coverage and error-norm metrics | A-d | 2-3 | `P1-S6-T06`, `P3-S2-T05`, `P3-S6-T01` |

### P3-S7 -- Non-LLM claims: physical and simulated sciences (32 claims)

32 of the >=60 non-LLM claims, in batches small enough to be one working session at 20 h/week.

*7 tasks, 32-49 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 282 | `P3-S7-T01` | Curate Matbench Discovery claims, batch 1 (5) | A-d | 5-8 | `P3-S6-T01`, `P3-S5-T01` |
| 283 | `P3-S7-T02` | Curate Matbench Discovery claims, batch 2 (5) | A-d | 5-8 | `P3-S7-T01` |
| 284 | `P3-S7-T03` | Curate Open Catalyst claims, batch 1 (4) | A-d | 4-6 | `P3-S6-T02` |
| 285 | `P3-S7-T04` | Curate Open Catalyst claims, batch 2 including OCx24 wet-lab (4) | A-d | 4-6 | `P3-S7-T03` |
| 286 | `P3-S7-T05` | Curate WeatherBench 2 claims, batch 1 (4) | A-d | 4-6 | `P3-S6-T04` |
| 287 | `P3-S7-T06` | Curate WeatherBench 2 claims, batch 2 (4) | A-d | 4-6 | `P3-S7-T05` |
| 288 | `P3-S7-T07` | Curate physics claims across The Well / PDEBench / FAIR Universe (6) | A-d | 6-9 | `P3-S6-T08`, `P3-S5-T04` |

### P3-S8 -- Non-LLM claims: life sciences, robotics and audio (38 claims)

The remaining 38 non-LLM claims, including the two most expensive families in the plan.

*8 tasks, 38-58 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 289 | `P3-S8-T01` | Curate CASP assessment-paper claims (5) | A-d | 5-8 | `P3-S6-T03`, `P3-S5-T02` |
| 290 | `P3-S8-T02` | Curate CAMEO rolling claims (5) | A-d | 5-8 | `P3-S6-T03` |
| 291 | `P3-S8-T03` | Curate Grand Challenge claims, batch 1 (4) | A-d | 4-6 | `P3-S6-T06` |
| 292 | `P3-S8-T04` | Curate Grand Challenge claims, batch 2 (4) | A-d | 4-6 | `P3-S8-T03`, `P3-S1-T07` |
| 293 | `P3-S8-T05` | Curate RoboArena pairwise claims (6) | A-d | 6-9 | `P3-S6-T05` |
| 294 | `P3-S8-T06` | Curate robotics per-benchmark cluster claims (6) | A-d | 6-9 | `P3-S6-T05`, `P3-S5-T04` |
| 295 | `P3-S8-T07` | Curate DCASE claims (4) | A-d | 4-6 | `P3-S6-T07` |
| 296 | `P3-S8-T08` | Curate Open ASR Leaderboard claims (4) | A-d | 4-6 | `P3-S6-T07` |

### P3-S9 -- Headroom, saturation bands, and the null-reason surface

Headroom ships with the claims because it needs a sourced baseline, a sourced ceiling and a qualifying claim, and all three exist only now.

*6 tasks, 17-25 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 303 | `P3-S9-T01` | Implement the SOTA qualification rule | A | 3-5 | `P3-S5-T06`, `P0-S2-T06` |
| 304 | `P3-S9-T02` | Implement headroom, unclamped, with exceeds_ceiling | A | 4-6 | `P3-S9-T01`, `P3-S6-T08` |
| 305 | `P3-S9-T03` | Implement the seven null reasons and publish their distribution | A | 3-4 | `P3-S9-T02` |
| 306 | `P3-S9-T04` | Verify graceful nulls on the three stress cases at real scale | A | 2-3 | `P3-S9-T03`, `P3-S6-T04`, `P3-S6-T05` |
| 307 | `P3-S9-T05` | Implement saturation bands with the minimum-evidence threshold | A | 3-4 | `P3-S9-T02` |
| 308 | `P3-S9-T06` | Add the determinism gate and manifest parameters for the derived tree | A | 2-3 | `P3-S9-T05`, `P3-S4-T08` |

### P3-S10 -- The comparison surface

The build computes comparability_key and the site refuses to compare claims that do not share one; the refusal is the feature.

*9 tasks, 31-48 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 297 | `P3-S10-T01` | Author the comparability profile lookup | A-d | 3-5 | `P3-S6-T08` |
| 298 | `P3-S10-T02` | Compute comparability_key, key_unknown_count and completeness in the build | A | 4-6 | `P3-S10-T01`, `P0-S9-T03` |
| 309 | `P3-S10-T03` | Emit claims.json, claims-ingested/ and derived/comparability.json | A | 3-6 | `P3-S10-T02`, `P2-S1-T02`, `P2-S1-T05` |
| 310 | `P3-S10-T04` | Implement the three comparability UI states | A | 3-4 | `P3-S10-T02`, `P2-S1-T02`, `P3-S10-T03` |
| 311 | `P3-S10-T05` | Build the V5 Comparison Workbench at /compare/ | A | 6-9 | `P3-S10-T04`, `P3-S10-T03` |
| 312 | `P3-S10-T06` | Implement the six categorical refusals | A | 4-6 | `P3-S10-T05` |
| 313 | `P3-S10-T07` | Build the provenance drill-down and verification badges | A | 3-5 | `P3-S10-T02`, `P2-S3-T01` |
| 314 | `P3-S10-T08` | Apply the default sort and the machine-ingested comparison filter | A | 3-4 | `P3-S10-T05`, `P3-S4-T08` |
| 315 | `P3-S10-T09` | Build the /corrections page and feed | A | 2-3 | `P3-S10-T07` |

### P3-S11 -- Phase gate

Every Phase 3 exit criterion is checked by something that can fail, and the phase is closed by a recorded human decision.

*4 tasks, 6-10 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 316 | `P3-S11-T01` | Build the Phase 3 gate script | A | 2-3 | `P3-S8-T08`, `P3-S5-T07`, `P3-S4-T08` |
| 317 | `P3-S11-T02` | Assert the structural exit criteria | A | 2-3 | `P3-S11-T01`, `P3-S10-T06`, `P3-S9-T03` |
| 318 | `P3-S11-T03` | Publish the trust numbers this phase owes | A | 1-2 | `P3-S11-T02` |
| 319 | `P3-S11-T04` | Hold the Phase 3 exit review | gate | 1-2 | `P3-S11-T03` |

---

## Phase 4 -- Coverage, gaps, ecosystem view, release feed -> public v1

*7 stages, 52 tasks, 90-169 hours.*

**Goal.** A curated, claim-bearing catalogue becomes a citable public v1: the coarse 19x13 coverage grid, a Gap Finder restricted to review-backed domains, the ecosystem and trust surfaces, the release feed, the croissant-benchmark extension and a resolving DOI all exist and are verified.

**Entry condition.** Phase 3 exited: >=130 hand-curated claims at condition_completeness >= 0.6 with >=60 non-LLM, the Epoch bulk ingest present and segregated under data/claims/_ingested/epoch/ with its unmatched count, headroom and saturation bands computed with null reasons, comparability_key computed in the build, V5 Comparison Workbench and V6 detail pages live. Phase 1 exited at >=290 benchmark families across 19 of 19 domain families, with reviewer outreach begun and at least three unfamiliar domains signed off or every unsigned domain badged. Phase 2's Astro site, design system, CI gate set and per-benchmark croissant.jsonld emission are in place.

**Exit gate.** All seven Phase 4 exit criteria in 14-roadmap.md are green: (1) headroom computed for >=60% of benchmarks with established baselines and null handled visibly with a stated reason everywhere else; (2) the coverage map shows curation confidence alongside density; (3) the Gap Finder surfaces at least one gap the maintainers did not already know about, within a review-backed domain; (4) every unreviewed domain renders "insufficient curation confidence to assert a gap" rather than an empty cell; (5) a researcher unfamiliar with a domain can orient in it in under five minutes; (6) the DOI resolves and the CC-BY YAML at that commit hash downloads as a single archive; (7) the Croissant extension issue is filed on the MLCommons repository and the three worked examples validate against our own context. Recorded by P4-S7-T09.

**Parallelism.** S1 is a hard serial prefix: nothing in S2 can honestly emit a number before taxonomy/not-applicable.yaml, reviewer_signoff and the survey notes exist, and S1-T02/T05/T06 are curation, not engineering, so they do not speed up with more compute. From there S2 -> S3 is a chain. But S4 (Saturation Wall, Frontier Timeline, Release Feed) and S6 (Croissant) are fully independent of S1, S2 and S3 -- S4 needs only Phase 3's headroom.json and the Phase 2 site shell, S6 needs only Phase 2's croissant.jsonld emission -- so both can run from day one of the phase. S5 forks after P4-S2-T06 (the citation adapters) and rejoins only at S7. Within S3, T02-T05 can run concurrently once T01 lands; within S7, T01-T04 and T06-T07 are independent of each other. At one person the phase is effectively serial and the 4.5-8.5 week estimate stands. At two people the only split that buys anything is curation (S1-T02/T05/T06, S3-T08, S7-T08) against engineering (everything else); it takes roughly a week off the top end and no more, because the curation prefix is what gates S2 and S3 and it does not parallelise across two people unless both are curating. Running S4 and S6 concurrently with S1 is the single cheapest overlap available and costs nothing, because neither touches taxonomy/ or data/.

### P4-S1 -- Preconditions for an honest coverage claim

The inputs that make a published coverage or gap number defensible exist as committed data before any view is drawn.

*7 tasks, 11.5-23 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 320 | `P4-S1-T01` | Re-validate the 3.3 capability-group collapse factor against real tag co-occurrence | A | 1-2 | `P1-S13-T06` |
| 321 | `P4-S1-T02` | Triage and declare the not-applicable coarse cells | A-d | 1-2 | `P1-S12-T09`, `P1-S13-T06` |
| 322 | `P4-S1-T03` | Record domain-reviewer sign-offs as structured data | A-d | 1-2 | `P1-S4-T07`, `P0-S7-T02`, `P3-S1-T07` |
| 323 | `P4-S1-T04` | Implement curation_confidence per domain family | A | 1.5-3 | `P4-S1-T03` |
| 324 | `P4-S1-T05` | Add the SurveyNote entity and write survey notes for one review-backed family | A-d | 2-4 | `P4-S1-T03`, `P1-S12-T08` |
| 325 | `P4-S1-T06` | Write survey notes for the remaining review-backed families | A-d | 4-8 | `P4-S1-T05`, `P1-S12-T08`, `P1-S2-T11` |
| 326 | `P4-S1-T07` | Recalibrate frontier_floor and comparison_floor against the hand-curated distribution | A-d | 1-2 | `P3-S8-T08`, `P3-S1-T07` |

### P4-S2 -- The S4 derived-analytics stage

build/derived/ grows from headroom-and-saturation to the full artifact set 12-analytics-and-trends.md S1.2 specifies, deterministically and with every parameter recorded.

*10 tasks, 18-36 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 327 | `P4-S2-T01` | Emit coverage.json -- both grids, sparse, with degenerate flags | A | 2-4 | `P4-S1-T02`, `P4-S1-T04` |
| 328 | `P4-S2-T02` | Extend the gap emitter with the score, its weights and the publishability gate | A | 2-4 | `P4-S2-T01`, `P1-S2-T11` |
| 329 | `P4-S2-T03` | Gate gap publishability on survey note, confidence, survey status and sign-off | A | 1.5-3 | `P4-S2-T02`, `P4-S1-T06` |
| 330 | `P4-S2-T04` | Compute saturation velocity and Kaplan-Meier time-to-saturation with censoring | A | 2-4 | `P3-S9-T05` |
| 331 | `P4-S2-T05` | Audit headroom coverage and the null-reason distribution against the 60% gate | A-d | 1.5-3 | `P3-S9-T03` |
| 332 | `P4-S2-T06` | Build the OpenAlex adapter with institution and ROR resolution | A | 2-4 | `P3-S1-T02`, `P3-S1-T06` |
| 333 | `P4-S2-T10` | Build the Semantic Scholar adapter and cross-check citation counts | A | 2-4 | `P4-S2-T06` |
| 334 | `P4-S2-T07` | Emit adoption.json and liveness.json | A | 2-4 | `P4-S2-T06` |
| 335 | `P4-S2-T08` | Emit hygiene.json -- the eight trust metrics | A | 1.5-3 | `P3-S4-T06` |
| 336 | `P4-S2-T09` | Extend the derived manifest and make determinism a CI gate | A | 1.5-3 | `P4-S2-T01`, `P4-S2-T02`, `P4-S2-T04`, `P4-S2-T07`, `P4-S2-T08`, `P0-S6-T01`, `P2-S1-T05` |

### P4-S3 -- V2 Coverage Map and V7 Gap Finder

The two views carrying differentiator 3 ship, with a curation gap made impossible to read as a field gap.

*8 tasks, 14.5-28 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 337 | `P4-S3-T01` | Build the V2 coverage-map island and SSR it to SVG | A | 3-5 | `P4-S2-T01` |
| 338 | `P4-S3-T02` | Emit the accessible table twin from the same data object | A | 1.5-3 | `P4-S3-T01` |
| 339 | `P4-S3-T03` | Implement the four cell renderings and resolve the hatch collision | A | 1.5-3 | `P4-S3-T01`, `P4-S1-T02`, `P2-S2-T01`, `P2-S2-T03` |
| 340 | `P4-S3-T04` | Render curation confidence alongside density, never fused into it | A | 1.5-3 | `P4-S3-T01`, `P4-S1-T04` |
| 341 | `P4-S3-T05` | Ship the fine-grid drill-down behind the null-model banner | A | 1.5-3 | `P4-S3-T01` |
| 342 | `P4-S3-T06` | Build the V7 Gap Finder table with per-component columns and export | A | 2-4 | `P4-S2-T02`, `P4-S2-T03` |
| 343 | `P4-S3-T07` | Restrict the Gap Finder to review-backed domains | A | 1.5-3 | `P4-S3-T06`, `P4-S1-T03` |
| 344 | `P4-S3-T08` | Run the gap hunt and get a reviewer's confirmation | gate | 2-4 | `P4-S3-T07`, `P4-S1-T06` |

### P4-S4 -- V3 Saturation Wall, V4 Frontier Timeline, V8 Release Feed

Three views ship, two of them at zero JavaScript, and the index acquires the retention surface that brings people back weekly.

*6 tasks, 11.5-20 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 345 | `P4-S4-T01` | Write the build-time SVG sparkline generator | A | 2-4 | `P3-S9-T03` |
| 346 | `P4-S4-T02` | Ship the V3 Saturation Wall with pre-rendered sort variants | A | 2-3 | `P4-S4-T01`, `P4-S2-T04` |
| 347 | `P4-S4-T03` | Build the V4 Frontier Timeline two-band chart | A | 2-4 | `P4-S2-T04` |
| 348 | `P4-S4-T04` | Add the nineteen family strips and the censored lifespan overlay | A | 2-3 | `P4-S4-T01`, `P4-S4-T03` |
| 349 | `P4-S4-T05` | Derive release-feed events from git history over data/ | A | 2-3 | `P2-S1-T01` |
| 350 | `P4-S4-T06` | Emit the feed formats and the feed page | A | 1.5-3 | `P4-S4-T05` |

### P4-S5 -- Ecosystem view and the trust page

The organisation becomes a unit of analysis and the index starts auditing itself in public.

*6 tasks, 11-20.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 351 | `P4-S5-T01` | Emit derived/ecosystem/*.json for series 9.1-9.4 over cohort_v1 | A | 2-4 | `P4-S2-T06`, `P4-S2-T09` |
| 352 | `P4-S5-T02` | Build the V9 dashboard E1-E6 | A | 3-5 | `P4-S5-T01` |
| 353 | `P4-S5-T03` | Ship the /orgs/{id}/ profile page type | A | 1.5-3 | `P4-S5-T01`, `P2-S3-T04` |
| 354 | `P4-S5-T04` | Enforce disclosure-not-accusation on the independence surface | A | 1.5-2.5 | `P4-S5-T02`, `P4-S5-T03`, `P0-S6-T01` |
| 355 | `P4-S5-T05` | Ship the trust and hygiene dashboard as a first-class page | A | 2-4 | `P4-S2-T08` |
| 356 | `P4-S5-T06` | Add the single-source marker and assert it everywhere a citation figure renders | A | 1-2 | `P4-S2-T06` |

### P4-S6 -- The croissant-benchmark extension

A namespaced, validated, mapped and publicly proposed benchmark extension to MLCommons Croissant exists, without ever republishing the CC BY-ND spec.

*6 tasks, 9.5-15.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 357 | `P4-S6-T01` | Publish the namespaced JSON-LD context | A | 1.5-2.5 | `P2-S3-T06` |
| 358 | `P4-S6-T02` | Commit the field-level mapping and its schema | A | 2-3 | `P4-S6-T01` |
| 359 | `P4-S6-T03` | Emit per-benchmark and collection JSON-LD from stage S9 | A | 1.5-2.5 | `P4-S6-T02` |
| 360 | `P4-S6-T04` | Validate every emitted document in CI | A | 1.5-2.5 | `P4-S6-T03`, `P0-S6-T01` |
| 361 | `P4-S6-T05` | Produce the three worked examples from three domains | A-d | 2-3 | `P4-S6-T04` |
| 362 | `P4-S6-T06` | File the extension proposal on the MLCommons Croissant repository | H | 1-2 | `P4-S6-T05` |

### P4-S7 -- Release, DOI, launch, and the v1 gate

Everything that has to be true to call it v1 is true, tested, and recorded.

*9 tasks, 14-26 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 363 | `P4-S7-T01` | Emit the S9 release artifacts | A | 1.5-3 | `P4-S2-T09`, `P4-S6-T03`, `P1-S14-T07` |
| 364 | `P4-S7-T02` | Wire bench verify and the monthly clean-machine rebuild | A | 1.5-2.5 | `P4-S7-T01` |
| 365 | `P4-S7-T03` | Wire the restore drill from the mirror | A | 1-2 | `P4-S7-T02` |
| 366 | `P4-S7-T04` | Generate the /attributions page from the sources entity | A | 1.5-2.5 | `P3-S4-T06`, `P3-S1-T07` |
| 367 | `P4-S7-T05` | Mint the v1 release against the concept DOI reserved in Phase 0 | H | 1.5-3 | `P4-S7-T01`, `P0-S7-T02`, `P0-S7-T05` |
| 368 | `P4-S7-T06` | Publish the launch documentation set | A-d | 2.5-4 | `P4-S3-T07`, `P4-S5-T05`, `P0-S7-T03`, `P2-S3-T05`, `P2-S6-T07` |
| 369 | `P4-S7-T07` | Extend the route-size, no-JS and accessibility gates to the seven new routes | A | 1.5-3 | `P4-S3-T01`, `P4-S4-T03`, `P4-S5-T02`, `P0-S6-T01`, `P2-S8-T01`, `P2-S2-T02` |
| 370 | `P4-S7-T08` | Run the orientation test | H | 1.5-3 | `P4-S7-T06` |
| 371 | `P4-S7-T09` | Verify the v1 launch checklist and hold the phase exit review | gate | 1.5-3 | `P4-S1-T07`, `P4-S2-T09`, `P4-S3-T08`, `P4-S4-T06`, `P4-S5-T06`, `P4-S6-T06`, `P4-S7-T05`, `P4-S7-T07`, `P4-S7-T08` |

---

## Phase 5 -- Ingestion at scale and freshness automation

*8 stages, 60 tasks, 168.5-261 hours.*

**Goal.** Ingestion stops being one hand-run script and becomes a scheduled, self-monitoring pipeline that drafts more than half of all new claims for human approval, while staleness and upstream death become visible to readers rather than only to maintainers.

**Entry condition.** Phase 4 has exited (public v1: DOI minted, coverage and gap views live). Phase 3's Epoch adapter (`ingest/epoch.py`) exists and has survived one hand-run bulk ingest, carrying the shared YAML emitter, content-derived claim ids, the unit guard, the sanity band and the caps. Phase 1's Wayback SPN2 + CDX archiver exists. The three ingestion schema additions in 07 §12 are ratified, or are picked up by P5-S2-T08.

**Exit gate.** All five criteria in 14-roadmap.md "Phase 5 -> Exit criteria" hold: (1) >=50% of new claims originate from ingestion drafts with human approval, measured by `bench report ingest-share`; (2) no entry on `main` unverified for over 12 months without a visible flag on its page; (3) zero dead unarchived source links; (4) a deliberately broken adapter -- the SWE-bench script tag renamed in a fixture -- hard-fails and opens an issue rather than writing nulls; (5) arXiv triage precision and recall measured on our own labelled set of at least 200 papers, with the measured numbers replacing the estimates in 14-roadmap.md. Recorded at the P5-S8-T05 human gate.

**Parallelism.** S1 -> S2 is strictly serial: the ABC must exist before the shared runner is written onto it (07 S11.5 step 3). After S2, three tracks run concurrently and touch disjoint files: the adapter track (S5 then S6, sharing ingest/adapters/ and the fetcher), the pipeline track (S3 then S4, sharing .github/workflows/ and ingest/runner/), and the freshness track (S7 then S8, sharing site/ and tools/report/). At two people on the 06/07 split -- one curation-facing, one engineering-facing -- the adapter track and the freshness/site track genuinely run alongside each other, and Phase 5 compresses to roughly the length of the adapter track plus S1-S2. At one person there is no compression at all: the phase table's totals already assume serial execution, and context-switching between debugging an OAI-PMH resumption token and reviewing an ingest PR is the same hours spent worse. Two cross-track edges constrain it: S7-T01 (liveness) needs S5-T01's GitHub signals and S6-T06's Grand Challenge lifecycle data, and S6-T04 (the breakage drill, exit criterion 4) needs both S6-T03 and S4-T05. S3-T01 (the bot PAT) is a human task with no dependencies and should be started on day one, because everything in S3 after T03 waits on it and it can sit in an inbox. S6-T01 and S6-T08 (licence correspondence and reading) likewise have zero dependencies, multi-week third-party latency, and gate promotion out of the discovery trees -- start them in week one of the phase, not when the adapters are ready.

### P5-S1 -- HuggingFace Hub adapter and the extracted contract

A second, API-shaped adapter runs end to end against fixtures, and the Adapter ABC is extracted from two real instances rather than guessed from one.

*8 tasks, 21-33 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 372 | `P5-S1-T01` | Author the HuggingFace tag crosswalk | A-d | 2-4 | `P0-S2-T05`, `P0-S4-T09`, `P0-S5-T02` |
| 373 | `P5-S1-T02` | Capture HuggingFace Hub fixtures | A | 1-2 | -- |
| 374 | `P5-S1-T03` | Implement hf-hub discover and fetch | A | 4-6 | `P5-S1-T02` |
| 375 | `P5-S1-T04` | Implement hf-hub normalise | A | 5-7 | `P5-S1-T01`, `P5-S1-T03` |
| 376 | `P5-S1-T05` | Build the shared RateLimit parser and backoff | A | 2-3 | -- |
| 377 | `P5-S1-T06` | Add the hf-hub determinism and idempotency suite | A | 2-3 | `P5-S1-T04` |
| 378 | `P5-S1-T07` | Run the FormPayload spike | A | 1-2 | `P5-S1-T04` |
| 379 | `P5-S1-T08` | Extract the Adapter ABC and refactor adapters 1-2 onto it | A | 4-6 | `P5-S1-T06`, `P5-S1-T07`, `P3-S1-T02`, `P3-S1-T03` |

### P5-S2 -- The shared runner: politeness, state, resolver, differ, gates

The parts every subsequent adapter inherits are written once, so adapters 3 to 8 are 30-100 lines each.

*8 tasks, 24-38 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 380 | `P5-S2-T01` | Build per-host policy, robots cache and the no-collect list | A | 3-5 | `P5-S1-T08` |
| 381 | `P5-S2-T02` | Build the state layer, cursor and checkpoint | A | 2-4 | `P5-S1-T08` |
| 382 | `P5-S2-T03` | Build the resolver, its snapshot and the lineage index | A | 4-6 | `P5-S1-T08`, `P3-S4-T06`, `P3-S1-T06` |
| 383 | `P5-S2-T04` | Build the differ and change classification | A | 3-5 | `P5-S2-T03` |
| 384 | `P5-S2-T05` | Implement the thirteen quality gates as one shared module | A | 6-9 | `P5-S1-T08` |
| 385 | `P5-S2-T06` | Add the round-trip emitter assertion over data/ | A | 2-3 | `P0-S6-T01` |
| 386 | `P5-S2-T07` | Build the unresolved status ledger and bench ingest unresolved | A | 3-4 | `P5-S2-T04` |
| 387 | `P5-S2-T08` | Land the three ingestion schema additions | A-d | 1-2 | `P0-S4-T07`, `P0-S5-T01` |

### P5-S3 -- Scheduling, weekly branching and the draft-PR pipeline at volume

Adapters run unattended on GitHub Actions cron and their output reaches a human at a rate one human can actually review.

*9 tasks, 22-32 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 388 | `P5-S3-T01` | Mint the uaibi-bot PAT and repository secrets | H | 1-2 | -- |
| 389 | `P5-S3-T02` | Verify and date the platform facts Phase 5 rests on | A | 2-3 | -- |
| 390 | `P5-S3-T03` | Implement the weekly ingest branch and per-run commit | A | 3-4 | `P0-S7-T01`, `P5-S2-T02`, `P2-S6-T06` |
| 391 | `P5-S3-T04` | Build the PR body generator | A | 4-6 | `P5-S2-T04`, `P5-S2-T07` |
| 392 | `P5-S3-T05` | Wire promote-ingest.yml weekly promotion | A | 3-4 | `P5-S3-T01`, `P5-S3-T03`, `P5-S3-T04` |
| 393 | `P5-S3-T06` | Implement same-day escalation for conflicts and broken adapters | A | 2-3 | `P5-S3-T04` |
| 394 | `P5-S3-T07` | Wire the four ingest workflows | A | 2-3 | `P5-S3-T05` |
| 395 | `P5-S3-T08` | Build the metrics/ auto-merge lane | A | 3-4 | `P5-S3-T03`, `P1-S14-T07` |
| 396 | `P5-S3-T09` | Enforce intake throttling: ceiling, WIP cap and expiry | A | 2-3 | `P5-S3-T04` |

### P5-S4 -- Breakage detection and observability

A scraper that quietly stops working becomes visible within a week rather than a quarter.

*6 tasks, 13-20 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 397 | `P5-S4-T01` | Implement RunReport and the committed run log | A | 2-3 | `P5-S2-T02` |
| 398 | `P5-S4-T02` | Implement adaptive yield bands and the zero-yield guard | A | 2-3 | `P5-S4-T01` |
| 399 | `P5-S4-T03` | Build bench report staleness | A | 3-4 | `P5-S4-T01`, `P5-S2-T07`, `P3-S1-T07` |
| 400 | `P5-S4-T04` | Build the health-check.yml canary | A | 3-5 | `P5-S4-T03`, `P0-S7-T04` |
| 401 | `P5-S4-T05` | Implement the schema-drift hard-fail contract | A | 2-3 | `P5-S1-T04` |
| 402 | `P5-S4-T06` | Add the structure-assertion lint | A | 1-2 | -- |

### P5-S5 -- Adapters #4 and #5: the eval-conditions corpus and arXiv discovery

comparability_key gets real values instead of nulls, and the only continuous source of genuinely new benchmarks runs behind a measured, not asserted, classifier.

*9 tasks, 29-46 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 403 | `P5-S5-T01` | Build the GitHub metadata adapter | A | 4-6 | `P5-S2-T01` |
| 404 | `P5-S5-T02` | Build the harness and MTEB shallow-clone ingest | A | 5-8 | `P5-S5-T01` |
| 405 | `P5-S5-T03` | Author the harness YAML to EvalConditions mapping stanzas | A-d | 4-6 | `P5-S5-T02`, `P0-S5-T05` |
| 406 | `P5-S5-T04` | Build the arXiv OAI-PMH adapter | A | 5-7 | `P5-S2-T01` |
| 407 | `P5-S5-T05` | Draw the 200-abstract labelling sample with a real denominator | A | 2-3 | `P5-S5-T04` |
| 408 | `P5-S5-T06` | Hand-label the 200 abstracts | H | 2-4 | `P5-S5-T05` |
| 409 | `P5-S5-T07` | Implement the triage classifier | A | 3-5 | `P5-S5-T04` |
| 410 | `P5-S5-T08` | Measure triage precision and recall and replace the estimates | A | 2-4 | `P5-S5-T06`, `P5-S5-T07` |
| 411 | `P5-S5-T09` | Add the monthly false-negative audit | A | 2-3 | `P5-S5-T08` |

### P5-S6 -- Second wave, PwC quarantine and licence closure

The remaining Tier-1 and Tier-2 sources are ingesting or explicitly vetoed, and every licence question that gates promotion is closed in writing.

*9 tasks, 26.5-42 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 412 | `P5-S6-T01` | Close the open licence questions by correspondence | H | 4-8 | -- |
| 413 | `P5-S6-T02` | Build the LMArena adapter | A | 4-6 | `P5-S2-T01` |
| 414 | `P5-S6-T03` | Build the SWE-bench adapter | A | 3-4 | `P5-S2-T01` |
| 415 | `P5-S6-T04` | Run the deliberately broken adapter drill | A | 2-3 | `P5-S6-T03`, `P5-S4-T05` |
| 416 | `P5-S6-T05` | Build the HELM adapter behind the licence veto | A | 4-6 | `P5-S2-T01` |
| 417 | `P5-S6-T06` | Build the Grand Challenge adapter | A | 3-5 | `P5-S2-T01` |
| 418 | `P5-S6-T07` | Build OpenRouter and LiteLLM system-entity enrichment | A | 3-4 | `P5-S2-T01` |
| 419 | `P5-S6-T08` | Read the PwC archive licence and close the Phase-0 ADR | H | 0.5-1 | `P0-S10-T05` |
| 420 | `P5-S6-T09` | Build the PwC identifier crosswalk, keys only | A-d | 3-5 | `P5-S6-T08` |

### P5-S7 -- Liveness signalling and freshness display

Differentiator (iv) is produced rather than asserted, and staleness is visible to readers instead of only to the two people most likely to stop looking.

*6 tasks, 17-25 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 421 | `P5-S7-T01` | Derive maintenance_status from observable signals | A-d | 4-6 | `P5-S5-T01`, `P5-S6-T06` |
| 422 | `P5-S7-T02` | Confirm the first lifecycle: dead proposals | H | 1-2 | `P5-S7-T01` |
| 423 | `P5-S7-T03` | Emit ingest-health.json and build the public /sources page | A | 3-4 | `P5-S4-T01`, `P0-S5-T05` |
| 424 | `P5-S7-T04` | Ship the per-entry freshness badge and its tokens | A | 4-6 | `P5-S7-T03`, `P2-S2-T01`, `P2-S2-T02` |
| 425 | `P5-S7-T05` | Build the prioritised re-verification queue | A | 3-4 | `P5-S7-T04`, `P3-S1-T07` |
| 426 | `P5-S7-T06` | Generate the per-release diff changelog | A | 2-3 | `P1-S14-T07` |

### P5-S8 -- Link rot, archival and the phase exit

Every cited source resolves or is archived, and the phase is measured against its own criteria rather than declared done.

*5 tasks, 16-25 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 427 | `P5-S8-T01` | Implement the link-rot re-check with four outcomes | A | 4-6 | `P1-S2-T08`, `P0-S5-T08` |
| 428 | `P5-S8-T02` | Implement the rolling archival budget with a cursor | A | 3-4 | `P5-S8-T01` |
| 429 | `P5-S8-T03` | Build bench report ingest-share | A | 2-3 | `P5-S3-T05`, `P3-S1-T07` |
| 430 | `P5-S8-T04` | Operate the pipeline for four consecutive weeks | H | 6-10 | `P5-S8-T03`, `P5-S3-T05`, `P5-S4-T04` |
| 431 | `P5-S8-T05` | Hold the Phase 5 exit review | gate | 1-2 | `P5-S8-T04`, `P5-S7-T04`, `P5-S6-T04`, `P5-S5-T08`, `P5-S8-T02` |

---

## Phase 6 -- AI layer: semantic search and suite builder

*7 stages, 54 tasks, 184-308 hours.*

**Goal.** The AI layer ships as a lens over an already-complete catalogue: deterministic retrieval works with the Worker entirely offline, every model call is bounded by a hard daily cap that degrades rather than bills, and no number on any AI surface was produced by a model.

**Entry condition.** Phase 5 exit met. facets.json, corpus.json, enums.json (with glosses), claims.json and derived/comparability.json are built and stable; comparability_key is computed; runnable_via, inspect_evals_id, execution.est_cost_usd and execution.est_runtime_hours are populated on enough entries to be usable; the catalogue is at >=290 benchmark families with the seven Core families at >=18. Public v1 (Phase 4) has shipped, because 11 §10's rule is that an AI increment slips whenever curation is behind, never the reverse.

**Exit gate.** All five of 14-roadmap.md Phase 6's exit criteria hold: (1) with the Worker disabled, facet, lexical and semantic search all still work and the site remains fully useful, readable and citable; (2) a synthetic load test of 5,000 requests in one hour trips the daily cap, degrades to deterministic retrieval with a visible footer status line, and produces no model charge above the cap — a hard gate before the endpoint is publicly reachable; (3) the abstention rate is published; (4) no number anywhere in the AI surface was produced by a model, every figure being computed in JavaScript from structured fields and shown with its formula; (5) measured per-call costs have replaced the estimates in 14 and 11 §5 after the first full month.

**Parallelism.** At one person this is strictly serial and the phase table already prices it that way; 14's "Overlap is a function of headcount" section is explicit that context-switching is not parallelism. What follows is what a second pair of hands could take.

S1 (AI-0, no model anywhere) and S2 (the Worker and G5, no model call yet) share no files and no artifacts: S1 is client-side TypeScript plus a Python build stage, S2 is `site/worker/` plus `wrangler.toml`. They run fully concurrently at two people. That is the single largest saving available, roughly 24-36 h off the critical path.

S4 (the deterministic suite surface and the manifest export) contains no model call at all and depends only on Phase 2/4 artifacts plus P6-S4's own chain. It can run alongside S2 and S3 entirely. Its only edge into the model work is P6-S4-T02 feeding P6-S5-T01.

Inside S2, the two human tasks (T02 Anthropic console limit, T04 Turnstile provisioning) are 30-60 minutes each and gate agent work behind them. Do them first, in one sitting, or T05 and T07 stall on a dashboard login.

P6-S6-T02 (recruiting external reviewers for the non-LLM suite_build items) has a multi-week lead time and no dependency on any code. Start it the week S3 starts, not when S6 starts. Treated as a serial S6 task it will be the thing that holds the phase open.

P6-S6-T01 (growing the golden set to 150) is 20-34 h of human labelling and is the largest single line in the phase. It runs alongside all of S5 once S5's synthesis path is callable. Do not serialise it after S5.

What cannot be parallelised: S5 is a chain (Call A, then Call B, then streaming, then the post-validator), and S7 is a gate sequence by construction. P6-S7-T03 lags the rest of the phase by a full calendar month by definition.

### P6-S1 -- AI-0: the deterministic retrieval floor

Facet, lexical and semantic retrieval run entirely client-side, with the Worker offline.

*9 tasks, 29-50 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 432 | `P6-S1-T01` | Spike the model2vec query encoder in JavaScript | A | 6-12 | `P2-S1-T02` |
| 433 | `P6-S1-T02` | Decide whether the static encoder holds or the AI2 fallback fires | gate | 1-2 | `P6-S1-T01` |
| 434 | `P6-S1-T03` | Implement bench embed and emit the document vector matrix | A | 4-7 | `P2-S1-T02` |
| 435 | `P6-S1-T04` | Ship the BM25 leg over facets.json with MiniSearch | A | 3-5 | `P2-S1-T02` |
| 436 | `P6-S1-T05` | Implement the cosine loop, RRF k=60 and the deterministic rerank | A | 4-6 | `P6-S1-T03`, `P6-S1-T04` |
| 437 | `P6-S1-T06` | Load the semantic tier off the critical path and cache it in IndexedDB | A | 3-5 | `P6-S1-T01`, `P6-S1-T03` |
| 438 | `P6-S1-T07` | Measure the four cold-start numbers and commit the two new budget lines | A | 3-5 | `P6-S1-T06`, `P2-S8-T05` |
| 439 | `P6-S1-T08` | Prove the whole search stack with /api/* blocked | A | 3-4 | `P6-S1-T05`, `P6-S1-T06` |
| 440 | `P6-S1-T09` | Render the semantic results as a separate labelled block | A | 2-4 | `P6-S1-T05` |

### P6-S2 -- The Worker and G5 spend control, before any model call exists

A thin Worker whose spend is bounded by a counter that degrades rather than bills.

*10 tasks, 22-37 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 441 | `P6-S2-T01` | Create config/ai-models.yaml with a verified_on per row | A-d | 3-5 | -- |
| 442 | `P6-S2-T02` | Set the org spend limit in the Anthropic Console below the tier ceiling | H | 0.5-1 | `P6-S2-T01` |
| 443 | `P6-S2-T03` | Stand up the Worker with run_worker_first scoped to /api/* and /mcp | A | 2-4 | `P2-S7-T02` |
| 444 | `P6-S2-T04` | Provision the Turnstile widget and store its secrets | H | 0.5-1 | `P6-S2-T03` |
| 445 | `P6-S2-T05` | Wire Turnstile verification on /api/* | A | 2-3 | `P6-S2-T04` |
| 446 | `P6-S2-T06` | Implement the per-endpoint caps table and the burst rate-limit binding | A | 3-5 | `P6-S2-T03` |
| 447 | `P6-S2-T07` | Implement the Durable Object daily counter at $6/day | A | 4-6 | `P6-S2-T03` |
| 448 | `P6-S2-T08` | Implement degraded mode: HTTP 200 with a deterministic payload | A | 3-5 | `P6-S2-T07` |
| 449 | `P6-S2-T09` | Cache responses in Workers KV keyed on query, index SHA and prompt version | A | 2-4 | `P6-S2-T03` |
| 450 | `P6-S2-T10` | Write the privacy note and confirm Anthropic's retention terms for our tier | H | 2-3 | `P6-S2-T06` |

### P6-S3 -- AI-1: F1 natural language to facet query, F5 explain this number, golden set v0

The first public model call is bounded by a generated schema and a post-validator, with a v0 evaluation behind it.

*9 tasks, 37-60 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 451 | `P6-S3-T01` | Generate the FacetQuery JSON Schema from enums.json at build time | A | 4-6 | `P2-S1-T02` |
| 452 | `P6-S3-T02` | Build the cached system prefix and gate its token count in CI | A | 2-4 | `P6-S3-T01` |
| 453 | `P6-S3-T03` | Implement /api/facet-query on claude-haiku-4-5 | A | 4-6 | `P6-S2-T07`, `P6-S2-T09`, `P6-S3-T02` |
| 454 | `P6-S3-T04` | Implement the FacetQuery post-validator | A | 3-5 | `P6-S3-T03` |
| 455 | `P6-S3-T05` | Build the AiPanel: query above results, editable, loosenable | A | 5-8 | `P6-S3-T04`, `P6-S1-T05` |
| 459 | `P6-S3-T06` | Fire 200 adversarial prompts at the FacetQuery schema and publish the result | A | 2-3 | `P6-S3-T04`, `P6-S3-T09` |
| 456 | `P6-S3-T07` | Implement /api/narrate (F5) with the comparison_floor hard gate | A | 4-6 | `P6-S2-T07`, `P3-S4-T06` |
| 457 | `P6-S3-T08` | Author golden set v0: 40 hand-labelled items across four splits | A-d | 8-14 | `P6-S3-T01` |
| 458 | `P6-S3-T09` | Build the pooling grading harness and the evals.yml workflow | A | 5-8 | `P6-S3-T08` |

### P6-S4 -- AI-2a: the deterministic suite surface and the manifest export

The suite builder works and exports an honest manifest with the AI layer switched off; no model is involved anywhere in this stage.

*7 tasks, 22-36 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 460 | `P6-S4-T01` | Build the V10 basket: three panes, URL-encoded selection | A | 4-6 | `P2-S1-T02` |
| 461 | `P6-S4-T02` | Compute the four analysis panels in JavaScript from structured fields | A | 4-6 | `P6-S4-T01`, `P4-S2-T01` |
| 462 | `P6-S4-T03` | Implement the hard exclusion filters and the excluded-N panel | A | 2-4 | `P6-S4-T01` |
| 463 | `P6-S4-T04` | Implement bench suite and the suite.yaml emitter | A | 4-6 | `P6-S4-T02`, `P0-S4-T03` |
| 464 | `P6-S4-T05` | Build the Inspect AI and plain-README adapters with the runnability header | A | 3-5 | `P6-S4-T04` |
| 465 | `P6-S4-T06` | Generate the lm-evaluation-harness adapter from a regenerated mapping | A | 3-5 | `P6-S4-T05` |
| 466 | `P6-S4-T07` | Render the no-JS static suite report from ?b= | A | 2-4 | `P6-S4-T02` |

### P6-S5 -- AI-2b: F2 synthesis and its containment, F4 the comparability explainer

The model can only annotate a set that code selected, and cannot introduce, rank or number anything.

*8 tasks, 27-43 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 467 | `P6-S5-T01` | Implement Call A: the stable structured schema with entry_ref | A | 4-6 | `P6-S2-T07`, `P6-S4-T02` |
| 468 | `P6-S5-T02` | Implement Call B: cited prose over field-group search_result blocks | A | 4-6 | `P6-S5-T01` |
| 469 | `P6-S5-T03` | Stream the prose, hold the manifest until it has been validated | A | 3-5 | `P6-S5-T01`, `P6-S5-T02` |
| 470 | `P6-S5-T04` | Implement the citation post-validator | A | 3-5 | `P6-S5-T03` |
| 471 | `P6-S5-T05` | Implement the refusal contract and derive theta at build time | A | 3-5 | `P6-S3-T09`, `P6-S5-T03` |
| 472 | `P6-S5-T06` | Put deep mode behind an explicit click | A | 2-3 | `P6-S5-T03` |
| 473 | `P6-S5-T07` | Implement F4: the deterministic comparability diff and its ternary verdict | A | 5-8 | `P3-S10-T02`, `P6-S3-T07` |
| 474 | `P6-S5-T08` | Harden the synthesis path against injection from ingested text | A | 3-5 | `P6-S5-T02` |

### P6-S6 -- The golden set at 150 and the published self-evaluation

The AI layer's own evaluation exists, is CC-BY, is an entry in the index, and gates releases on deterministic metrics only.

*6 tasks, 36-63 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 475 | `P6-S6-T01` | Grow the golden set from 40 to about 150 items | A-d | 20-34 | `P6-S3-T08`, `P6-S5-T03` |
| 476 | `P6-S6-T02` | Recruit external reviewers for the non-LLM suite_build items | H | 4-8 | `P6-S6-T01` |
| 477 | `P6-S6-T03` | Build the judge harness and publish judge-human agreement | A | 4-7 | `P6-S6-T01`, `P6-S3-T09` |
| 478 | `P6-S6-T04` | Wire the release gates: hard zeros block, judge scores never do | A | 3-5 | `P6-S6-T03`, `P6-S3-T09` |
| 479 | `P6-S6-T05` | Publish evals/ as a CC-BY artifact with its own entry in the index | A-d | 3-5 | `P6-S6-T04`, `P2-S3-T05` |
| 480 | `P6-S6-T06` | Publish the abstention rate on the public trend page | A | 2-4 | `P6-S6-T04`, `P6-S5-T05` |

### P6-S7 -- The pre-exposure gate, the no-number audit and phase exit

Nothing is publicly reachable until the cap has been proven under load and no model-produced number survives on any AI surface.

*5 tasks, 11-19 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 481 | `P6-S7-T01` | Run the 5,000-request synthetic load test against the cap | A | 4-6 | `P6-S2-T07`, `P6-S2-T08`, `P6-S5-T03` |
| 482 | `P6-S7-T02` | Audit that no number on the AI surface came from a model | A | 3-5 | `P6-S5-T07`, `P6-S4-T02` |
| 484 | `P6-S7-T03` | Replace the estimated per-call costs with measured ones | A-d | 2-4 | `P6-S7-T04`, `P5-S5-T08`, `P6-S2-T01` |
| 483 | `P6-S7-T04` | Gate: do not make /api/* publicly reachable until the cap is proven | gate | 1-2 | `P6-S7-T01`, `P6-S7-T02`, `P6-S6-T04` |
| 485 | `P6-S7-T05` | Hold the Phase 6 exit review | gate | 1-2 | `P6-S7-T03`, `P6-S7-T04`, `P6-S1-T08`, `P6-S6-T06` |

---

## Phase 7 -- The package - SDK, CLI and MCP server

*8 stages, 28 tasks, 74.5-127 hours.*

**Goal.** The catalogue becomes an installable object: pip install benchindex gives a typed client, a public CLI and an MCP server that answer exactly what the site answers, carry the same comparability refusals, and state the data version behind every answer - so a number used in a script and a number cited in a paper are the same number.

**Entry condition.** Public v1 has shipped (Phase 4 exit) and the build artifacts are stable at their published URL namespace. The AI layer is not required: the package's default path is deterministic and makes no model call. Phase 5's adapters are not required either, but the package is more useful after them because the catalogue is fresher.

**Exit gate.** benchindex is on PyPI with a reproducible wheel built by CI under Trusted Publishing; a cold `pip install benchindex` followed by the six documented calls in 17 S2 works against the live artifacts with no other setup; the package refuses to compare two claims whose comparability_key differs and names the differing fields; `Index(path=...)` works with the network disabled; every public model is asserted identical to the object in schema/; the MCP server answers all five tools against the live catalogue; and the offline failure path raises with the remedy named rather than returning an empty catalogue.

**Parallelism.** S1 must land first and blocks everything. After that S2 is the spine that S3, S4 and S5 all consume, so it is the critical path. S6 (MCP) depends only on S2 to S5's public surface and can run alongside S7. S7 (offline) is independent of S6 and touches only S2's resolution path. S8 is the gate. At two people the split is S3+S4 against S5+S6, which is roughly balanced; at one person the order below is the order.

### P7-S1 -- Package skeleton, the API boundary and the release pipeline

packages/benchindex/ exists as a buildable wheel with its public surface declared and its release path automated, so every later task adds to a boundary that is already enforced.

*6 tasks, 12-21 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 486 | `P7-S1-T01` | Scaffold packages/benchindex with its build backend and pins | A | 2-4 | `P4-S7-T09` |
| 487 | `P7-S1-T02` | Re-export the canonical models and assert no second definition | A | 2-3.5 | `P7-S1-T01` |
| 488 | `P7-S1-T03` | Declare the public API surface and make additions deliberate | A | 2.5-4 | `P7-S1-T02` |
| 489 | `P7-S1-T04` | Implement the two-version scheme and the schema compatibility floor | A | 2-3.5 | `P7-S1-T03` |
| 490 | `P7-S1-T05` | Wire the Trusted Publishing release pipeline | A | 3-5 | `P7-S1-T04` |
| 491 | `P7-S1-T06` | Reserve the PyPI names | H | 0.5-1 | `P7-S1-T01` |

### P7-S2 -- The read path - resolution, caching and provenance

Index() resolves a data version, caches it, and every object it returns can say where it came from.

*3 tasks, 10-17 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 492 | `P7-S2-T01` | Implement Index resolution across the four construction modes | A | 4-7 | `P7-S1-T04` |
| 493 | `P7-S2-T02` | Implement the provenance object and attach it to every record | A | 3-5 | `P7-S2-T01` |
| 494 | `P7-S2-T03` | Implement the on-disk cache and bench cache warm | A | 3-5 | `P7-S2-T02` |

### P7-S3 -- Search, facets and typed vocabularies

A misspelled facet value is an error at call time rather than an empty result set.

*3 tasks, 9.5-16 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 495 | `P7-S3-T01` | Generate typed facet enums from the taxonomy | A | 3-5 | `P7-S2-T01` |
| 496 | `P7-S3-T02` | Implement search over the facet artifact | A | 3-5 | `P7-S3-T01` |
| 497 | `P7-S3-T03` | Implement the entity accessors and lazy claim loading | A | 3.5-6 | `P7-S3-T02`, `P7-S2-T03` |

### P7-S4 -- Comparison and the six refusals

The comparability rule lives in one place and the package cannot be talked out of it.

*4 tasks, 12-20 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 498 | `P7-S4-T01` | Port comparability_key computation into the package | A | 3-5 | `P7-S3-T03` |
| 499 | `P7-S4-T02` | Implement comparable() returning a verdict, never a boolean | A | 2.5-4 | `P7-S4-T01` |
| 500 | `P7-S4-T03` | Implement the six categorical refusals | A | 4-7 | `P7-S4-T02` |
| 501 | `P7-S4-T04` | Implement compare() as grouping, with no force argument | A | 2.5-4 | `P7-S4-T03` |

### P7-S5 -- Suite assembly and the public CLI

The terminal surface is the same API, and the maintenance subcommands stop being the first thing a new user sees.

*3 tasks, 8.5-14.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 502 | `P7-S5-T01` | Port deterministic suite assembly into the package | A | 3-5 | `P7-S4-T04` |
| 503 | `P7-S5-T02` | Build the public CLI surface | A | 3.5-6 | `P7-S5-T01` |
| 504 | `P7-S5-T03` | Hide the maintenance subcommands outside a checkout | A | 2-3.5 | `P7-S5-T02` |

### P7-S6 -- The MCP server

An agent can ask the catalogue instead of answering from its weights, and gets data with provenance rather than a conclusion.

*3 tasks, 8.5-14.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 505 | `P7-S6-T01` | Scaffold benchindex-mcp as its own wheel | A | 2-3.5 | `P7-S5-T02` |
| 506 | `P7-S6-T02` | Implement the five tools | A | 4-7 | `P7-S6-T01` |
| 507 | `P7-S6-T03` | Assert the server exposes no recommendation surface | A | 2.5-4 | `P7-S6-T02` |

### P7-S7 -- Offline, air-gapped and the failure modes

The package fails loudly with the remedy named, and never answers from stale data without saying so.

*2 tasks, 4.5-7.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 508 | `P7-S7-T01` | Implement the cold-cache offline failure path | A | 2.5-4 | `P7-S2-T03` |
| 509 | `P7-S7-T02` | Prove the air-gapped path end to end | A | 2-3.5 | `P7-S7-T01` |

### P7-S8 -- Documentation, adoption instruments and the phase gate

Someone who has never seen the project can install it and get a correct answer in five minutes, and the gate is checked by something that can fail.

*4 tasks, 9.5-16.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 510 | `P7-S8-T01` | Write the package documentation and the five-minute path | A-d | 4-7 | `P7-S5-T03`, `P7-S6-T02`, `P7-S7-T02` |
| 511 | `P7-S8-T02` | Instrument package adoption | A | 2-3.5 | `P7-S1-T05` |
| 512 | `P7-S8-T03` | Build the Phase 7 gate script | A | 2.5-4 | `P7-S7-T02`, `P7-S8-T01`, `P7-S4-T04` |
| 513 | `P7-S8-T04` | Hold the Phase 7 exit review | gate | 1-2 | `P7-S8-T02`, `P7-S8-T03` |

---

## Phase 8 -- Local evaluation runner, shipped in the package

*7 stages, 56 tasks, 217-402 hours.*

**Goal.** `bench run` executes a benchmark on the user's own infrastructure with the user's own keys and emits a RunRecord they own, so the catalogue gains reruns without gaining a compute bill. At least 10 benchmarks produce sandboxed-rerun claims through the normal contribution path, with archived transcripts and first-class EvalConditions. The scope gate in 13-execution-runners.md S0.1 governs how far past the first adapter this goes, not whether it happens.

**Entry condition.** Phases 0-6 have shipped (14-roadmap.md §0.4 sequencing: the gate sits on top of, not instead of, the ordering). Public v1 has been live for six months and docs/adoption/ carries two recorded measurements inside that window. Phase 7 has shipped the package the runner lives inside, which is the real prerequisite. Stage P8-S1 may begin at the end of Phase 4, and its instruments now size the phase rather than decide it: per 13-execution-runners.md S0.1 the first adapter is built unconditionally, and the gate controls whether a second adapter, scheduled reruns and the public execution pages follow. The Phase-0 schema preconditions in 13-execution-runners.md §9 (runnable_via, inspect_evals_id, maintainer_rerun_policy, provider_snapshot/_available, artifact_url, provenance_snapshot, the three-class material-field partition and its CI totality check) must already be shipped and populated.

**Exit gate.** From 14-roadmap.md §"Phase 8": ">=10 benchmarks producing `sandboxed-rerun` claims through the normal contribution path, with transcripts archived and every run's conditions recorded as a first-class EvalConditions entity." 13-execution-runners.md §8 adds five further criteria that the roadmap's exit does not restate: >=2 adapters with one agentic/containerised; every self-produced claim at condition_completeness == 1.0; a live public spend page showing the inference/storage and measured/estimated splits; zero privileged writes to data/ verified by the same CI that gates contributor PRs; the §4.4 divergence test green for every field in every adapter's recovers_material_fields and the field-class partition check green for every comparability profile. All six are checked by `python scripts/check_phase7_exit.py` (P8-S7-T01), and the exit review is recorded at P8-S7-T05. The legitimate alternative exit is P8-S1-T09: the gate failed, and the roadmap page says so with the measurement attached.

**Parallelism.** At one person nothing in P8-S2 through P8-S7 is genuinely parallel; 14-roadmap.md's "Overlap is a function of headcount, not of scheduling" applies unchanged, and the stage totals assume serial execution.

At two people with a clean split, four things run concurrently and are worth the split. (1) P8-S1 runs entirely alongside Phases 5 and 6 — it is measurement, not build, and it costs nothing downstream if the gate fails. (2) P8-S2's three human tasks (T01 provider ToS reads, T02 hard-cap survey, T03 R2 and credentials) plus T05's maintainer correspondence have multi-week lead times and block only P8-S4 and P8-S5; they should run alongside the whole of P8-S3, and starting them late is the most likely way this phase stalls. (3) P8-S3-T09, the Every Eval Ever serialiser, depends only on P8-S3-T02 and is independent of T04 through T08 — it is the natural filler when a live test is blocked on an API. (4) P8-S6-T03 through P8-S6-T05 (spend page, funding disclosure, methods page) are front-end and documentation work independent of P8-S5's adapter, and are the obvious second track while the agentic adapter (20-34 h, the single largest task in the phase) is in progress.

What that costs: the two-person split needs the engineering person to hold both the runner and the site build in their head, and P8-S6-T04 is a schema change requiring two named reviewers, so it serialises against whatever else needs review that week. Nothing else in the phase has a review queue between the two tracks.

What must stay serial regardless of headcount: P8-S1-T08 gates everything after it; P8-S3-T04 -> T05 -> T06 -> T08 is a true chain (the adapter must exist before its recovered fields can be proven, and they must be proven before a claim builder can compare against them); P8-S5-T01 -> T04 -> T05 is a true chain (keys must exist before the monthly cap can be enforced by provisioning, and both before the runaway test means anything); and P8-S7-T01 cannot run until P8-S4, P8-S5 and P8-S6 have all landed.

### P8-S1 -- The evidence gate: instrument it, measure it, make "no" cheap

Produce a defensible go/no-go on Phase 8, and make the "no" a published, dated, two-hour outcome rather than a perpetual "coming soon".

*9 tasks, 24-44 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 514 | `P8-S1-T01` | Obtain OpenAlex and Semantic Scholar API keys and record the instruments | H | 1-2 | -- |
| 515 | `P8-S1-T02` | Implement the three adoption instruments as one script | A | 6-10 | `P8-S1-T01` |
| 516 | `P8-S1-T03` | Add the request:rerun label, its issue template and the email-transcription rule | A | 1-2 | `P2-S6-T07` |
| 517 | `P8-S1-T04` | Publish the first quarterly adoption measurement | A-d | 3-5 | `P8-S1-T02`, `P8-S1-T03` |
| 518 | `P8-S1-T05` | Publish the second quarterly adoption measurement | A-d | 2-4 | `P8-S1-T04` |
| 519 | `P8-S1-T06` | Implement the five-clause gate query over the corpus | A | 5-9 | `P0-S4-T03` |
| 520 | `P8-S1-T07` | Run the gate query and publish the count with its query | A-d | 2-4 | `P8-S1-T06` |
| 521 | `P8-S1-T08` | Decide Phase-8 go / no-go | gate | 2-4 | `P8-S1-T05`, `P8-S1-T07` |
| 522 | `P8-S1-T09` | Execute the honest no: close the phase out in public | A | 2-4 | `P8-S1-T08` |

### P8-S2 -- Preconditions: isolation substrate, credentials, and the legal reads

Make it possible to run anything at all: a digest-pinned container that cannot reach the open web, credentials that cannot write data/, an artifact store, and written answers to the legal and policy questions that must be settled before the first API call.

*8 tasks, 24-48 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 523 | `P8-S2-T01` | Read each candidate provider's ToS and AUP for automated benchmarking | H | 3-6 | `P8-S1-T08` |
| 524 | `P8-S2-T02` | Survey which providers offer a per-key hard spend cap | A-d | 2-4 | `P8-S1-T08` |
| 525 | `P8-S2-T03` | Provision the R2 artifact bucket and the runner credential boundary | H | 3-6 | `P8-S1-T08` |
| 526 | `P8-S2-T04` | Audit maintainer_rerun_policy across the gate-passing set | A | 3-6 | `P8-S1-T07` |
| 527 | `P8-S2-T05` | Contact maintainers of contact-first gate-passing benchmarks | H | 3-8 | `P8-S2-T04` |
| 528 | `P8-S2-T06` | Decide the unstated rerun-policy default and record it as an ADR | A-d | 2-4 | `P8-S2-T04` |
| 529 | `P8-S2-T07` | Build the runner container, pinned by digest | A | 4-7 | `P8-S2-T03` |
| 530 | `P8-S2-T08` | Enforce the network egress allowlist | A | 4-7 | `P8-S2-T07` |

### P8-S3 -- The adapter contract and the Inspect adapter

Produce a RunRecord end to end from a blind parser, with recovers_material_fields proven by a divergence test rather than asserted, so that a sandboxed-rerun claim means what the badge says.

*9 tasks, 49-90 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 531 | `P8-S3-T01` | Write the HarnessAdapter ABC with a blind parse() | A | 3-5 | `P8-S2-T07` |
| 532 | `P8-S3-T02` | Implement RunRecord, HarnessInvocation, ParsedRun, RunLimits and run_id | A | 4-7 | `P8-S3-T01` |
| 533 | `P8-S3-T03` | Re-derive the Inspect .eval to EvalConditions mapping against a pinned version | A | 5-10 | `P8-S2-T07` |
| 534 | `P8-S3-T04` | Implement the Inspect adapter | A | 10-18 | `P8-S3-T02`, `P8-S3-T03` |
| 535 | `P8-S3-T05` | Build the golden divergence test that proves recovers_material_fields | A | 6-11 | `P8-S3-T04` |
| 536 | `P8-S3-T06` | Make plan/log divergence a failed run, not a footnote | A | 4-8 | `P8-S3-T05` |
| 537 | `P8-S3-T07` | Implement the repetition policy | A | 3-5 | `P8-S3-T02` |
| 538 | `P8-S3-T08` | Produce the first end-to-end RunRecord over 3-5 gate-passing benchmarks | A-d | 6-12 | `P8-S3-T06`, `P8-S3-T07`, `P8-S2-T08` |
| 539 | `P8-S3-T09` | Serialise RunRecord to Every Eval Ever and vendor the schema | A | 8-14 | `P8-S3-T02` |

### P8-S4 -- Write-back through the normal review path, and the artifact store

Get a machine-generated ResultClaim into data/ only by the same door a contributor uses, with its evidence in R2 and its integrity checkable by a stranger.

*7 tasks, 22-42 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 540 | `P8-S4-T01` | Emit ResultClaim and EvalConditions YAML and open a draft PR | A | 4-8 | `P8-S3-T06` |
| 541 | `P8-S4-T02` | Upload artifacts to R2 under content-addressed keys | A | 4-8 | `P8-S2-T03`, `P8-S3-T02` |
| 542 | `P8-S4-T03` | Implement retention and the pruned-artifact notice | A | 4-7 | `P8-S4-T02` |
| 543 | `P8-S4-T04` | Enforce the 100 GB storage cap by blocking runs, never by deleting | A | 2-4 | `P8-S4-T02` |
| 544 | `P8-S4-T05` | Prove zero privileged writes to data/ | A | 4-7 | `P8-S2-T03`, `P8-S4-T01` |
| 545 | `P8-S4-T06` | Merge the first machine-generated ResultClaim after human review | A-d | 2-4 | `P8-S4-T05` |
| 546 | `P8-S4-T07` | Add the review-matrix row and CODEOWNERS routing for machine-generated reruns | A | 2-4 | `P8-S4-T06`, `P2-S6-T06`, `P2-S6-T07` |

### P8-S5 -- Second adapter and the full cost stack

Prove the interface generalises to a containerised agentic harness without special-casing, and that a runaway run is stopped by the provider-side cap rather than by luck.

*9 tasks, 52-91 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 547 | `P8-S5-T01` | Provision per-run dedicated keys and the monthly budget policy | H | 2-4 | `P8-S2-T02` |
| 548 | `P8-S5-T02` | Implement layer 2: in-adapter token metering between agent steps | A | 6-11 | `P8-S3-T04` |
| 549 | `P8-S5-T03` | Implement layer 3: the out-of-container wall-clock watchdog | A | 5-8 | `P8-S2-T07` |
| 550 | `P8-S5-T04` | Implement layer 4: the monthly cap enforced by key provisioning | A | 3-5 | `P8-S5-T01` |
| 551 | `P8-S5-T05` | Run the deliberate runaway test and confirm layer 1 stopped it | A-d | 4-8 | `P8-S5-T02`, `P8-S5-T03`, `P8-S5-T04` |
| 552 | `P8-S5-T06` | Make a tripped ceiling produce a failed run record, never a partial claim | A | 3-5 | `P8-S5-T05`, `P8-S4-T01` |
| 553 | `P8-S5-T07` | Build the second adapter: a containerised agentic harness | A | 20-34 | `P8-S3-T05`, `P8-S5-T03` |
| 554 | `P8-S5-T08` | Prove the interface generalises without benchmark special cases | A | 2-4 | `P8-S5-T07` |
| 555 | `P8-S5-T09` | Implement cost reconciliation and the meaning of measured | A | 7-12 | `P8-S5-T01`, `P8-S4-T01` |

### P8-S6 -- Scheduled reruns, the public pages, and the divergence procedure

Make the running programme bounded, its cost public, its methods legible, and its first disagreement with a lab a process rather than an incident.

*8 tasks, 29-56 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 556 | `P8-S6-T01` | Define the named, bounded, published high-value rerun set | A-d | 3-5 | `P8-S5-T07` |
| 557 | `P8-S6-T02` | Schedule the reruns on an odd cron offset | A | 2-4 | `P8-S6-T01` |
| 558 | `P8-S6-T03` | Build the public spend page | A | 6-12 | `P8-S4-T04`, `P8-S5-T09` |
| 559 | `P8-S6-T04` | Add funding_disclosure to the claim schema and surface it | A-d | 4-8 | `P8-S6-T03`, `P0-S4-T05`, `P3-S10-T07` |
| 560 | `P8-S6-T05` | Write the methods page, including where our items went | A | 5-9 | `P8-S4-T06`, `P8-S6-T01` |
| 561 | `P8-S6-T06` | Automate the divergent-claim procedure | A | 5-10 | `P8-S4-T05` |
| 562 | `P8-S6-T07` | Notify the benchmark maintainer and the system publisher on the first divergence | H | 2-5 | `P8-S6-T06`, `P8-S4-T06` |
| 563 | `P8-S6-T08` | Align the methods page with NIST AI 800-2 and check its designation | A-d | 2-3 | `P8-S6-T05` |

### P8-S7 -- Phase exit, kill switch, and the recurring load

Check every exit criterion mechanically, pre-register the conditions under which the runner gets archived, and hand the operator a runbook for the 3-8 h/month this phase costs forever.

*6 tasks, 17-31 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 564 | `P8-S7-T01` | Implement the phase-exit checker over all six criteria | A | 3-6 | `P8-S6-T03`, `P8-S5-T07`, `P8-S4-T05` |
| 565 | `P8-S7-T02` | Enforce condition_completeness == 1.0 on self-produced claims | A | 3-5 | `P8-S4-T06`, `P0-S6-T01` |
| 566 | `P8-S7-T03` | Assert transcripts are archived and conditions are first-class | A | 3-5 | `P8-S4-T02`, `P8-S4-T06` |
| 567 | `P8-S7-T04` | Instrument the kill switch | A | 4-7 | `P8-S1-T02`, `P8-S7-T01` |
| 568 | `P8-S7-T05` | Hold the Phase-8 exit review | gate | 1-2 | `P8-S7-T01`, `P8-S7-T02`, `P8-S7-T03`, `P8-S7-T04` |
| 569 | `P8-S7-T06` | Write the recurring-operations runbook and the EEE drift check | A | 3-6 | `P8-S7-T05` |

---

## Phase 9 -- Hosted API and community submissions

*7 stages, 29 tasks, 84.5-142.5 hours.*

**Goal.** The two surfaces that let people who are not maintainers lean on the catalogue and write to it: a query layer over the same artifacts for the joins and point lookups static files serve badly, and a submission path by which an outsider's own run becomes a reviewed, badged claim - without either becoming something the repository depends on.

**Entry condition.** Phase 7 has shipped the package and Phase 8 the runner, because a submission is a RunRecord the runner emits and the API's compare endpoint reuses the package's comparability code. Public v1 has been live long enough that the corrections and disputes paths in 05 have been exercised at least once, because submissions will exercise them far harder.

**Exit gate.** Every REST endpoint answers from the published artifacts with its provenance attached and none holds state git does not hold; the rate limiter sheds load to a 429 naming the static artifact that answers the same question; the spend cap returns 503 rather than incurring a charge, proved under load; a submitted RunRecord with a missing mandatory field is rejected at the API with the field named; a valid submission opens a draft PR and writes nothing to data/; no submission path can promote a claim above the rung its evidence supports; and the whole catalogue, package and site still work with the API switched off, proved by a deliberate outage drill.

**Parallelism.** S1 blocks S2 and S3. S4 depends on the runner's RunRecord model and on S1's validation code but not on S2 or S3, so the submission half and the query half are genuinely independent after S1 and are the natural two-person split. S5 follows S4. S6 can be written alongside S5 because it is checks over a submission, not a stage in its path. S7 is the gate.

### P9-S1 -- The REST read layer over the published artifacts

Point lookups and filtered lists answer from the same artifacts the site and the package read, with no second database anywhere.

*5 tasks, 15.5-26 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 570 | `P9-S1-T01` | Stand up the API worker over the artifact namespace | A | 4-7 | `P7-S2-T02`, `P2-S7-T02` |
| 571 | `P9-S1-T02` | Implement the claims and taxonomy endpoints | A | 3.5-6 | `P9-S1-T01` |
| 572 | `P9-S1-T03` | Implement the compare endpoint over the package's own code | A | 3-5 | `P9-S1-T02`, `P7-S4-T03`, `P7-S5-T02` |
| 573 | `P9-S1-T04` | Attach provenance to every response and version the shape | A | 2.5-4 | `P9-S1-T03` |
| 574 | `P9-S1-T05` | Publish the OpenAPI description and generate the client docs | A | 2.5-4 | `P9-S1-T04` |

### P9-S2 -- Limits, keys and the degrade-rather-than-bill cap

One misbehaving client cannot make the service unavailable for everyone, and no client can make it expensive.

*4 tasks, 11-18 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 575 | `P9-S2-T01` | Implement the token-bucket rate limiter and the 429 body | A | 3-5 | `P9-S1-T04` |
| 576 | `P9-S2-T02` | Implement free self-serve API keys | A | 2.5-4 | `P9-S2-T01` |
| 577 | `P9-S2-T03` | Implement the hard spend cap with a 503 degrade path | A | 3-5 | `P9-S2-T02` |
| 578 | `P9-S2-T04` | Run the outage drill that proves the API is not load-bearing | A | 2.5-4 | `P9-S2-T03`, `P7-S7-T02`, `P7-S5-T02` |

### P9-S3 -- GraphQL for the joins, cost-limited

The three queries static artifacts genuinely cannot serve are answerable, and a runaway query is rejected with its cost rather than truncated.

*3 tasks, 10-18 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 579 | `P9-S3-T01` | Measure whether GraphQL is earned before building it | A-d | 2-4 | `P9-S1-T05` |
| 580 | `P9-S3-T02` | Implement the read-only GraphQL endpoint | A | 5-9 | `P9-S3-T01` |
| 581 | `P9-S3-T03` | Implement query cost limiting with an honest rejection | A | 3-5 | `P9-S3-T02` |

### P9-S4 -- Submission intake and validation

A submission is validated hard at the door, and what passes is a proposed change to the repository rather than a write to a database.

*5 tasks, 17-29 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 582 | `P9-S4-T01` | Define the submission envelope over the runner's RunRecord | A | 3-5 | `P8-S3-T02`, `P9-S1-T04` |
| 583 | `P9-S4-T02` | Implement POST /api/v1/submissions with synchronous validation | A | 4-7 | `P9-S4-T01` |
| 584 | `P9-S4-T03` | Implement the automated evidence checks | A | 4-7 | `P9-S4-T02` |
| 585 | `P9-S4-T04` | Require a GitHub identity and record it on the claim | A | 3-5 | `P9-S4-T02` |
| 586 | `P9-S4-T05` | Implement bench submit in the package | A | 3-5 | `P9-S4-T04`, `P7-S5-T02` |

### P9-S5 -- The review pipeline and honest badging

What passes the door still enters through the same review a maintainer's change does, and lands at the rung its evidence supports.

*4 tasks, 12-20 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 587 | `P9-S5-T01` | Open a draft pull request from a queued submission | A | 4-7 | `P9-S4-T03`, `P8-S4-T01` |
| 588 | `P9-S5-T02` | Extend the review matrix for submitted claims | A-d | 2.5-4 | `P9-S5-T01`, `P2-S6-T06`, `P8-S4-T07` |
| 589 | `P9-S5-T03` | Enforce the badging ceiling on submitted claims | A | 3-5 | `P9-S5-T02` |
| 590 | `P9-S5-T04` | Publish the submission backlog when review capacity binds | A | 2.5-4 | `P9-S5-T03`, `P4-S5-T05` |

### P9-S6 -- Anti-gaming and contamination

Faking a number is expensive, attributable and correctable - which is the claim this project can actually support.

*4 tasks, 10-16.5 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 591 | `P9-S6-T01` | Require and record the contamination attestation | A | 3-5 | `P9-S4-T03` |
| 592 | `P9-S6-T02` | Record declared interest where a submitter is the subject | A | 2.5-4 | `P9-S6-T01` |
| 593 | `P9-S6-T03` | Implement per-identity submission limits and first-time review | A | 2.5-4 | `P9-S6-T02` |
| 594 | `P9-S6-T04` | Write the published limits of the anti-gaming story | A-d | 2-3.5 | `P9-S6-T03` |

### P9-S7 -- Launch and the phase gate

Both surfaces are public, documented and measured, and the invariants they could have broken are tested rather than assumed.

*4 tasks, 9-15 hours.*

| seq | Task | Title | Who | Hours | Waits on |
| ---: | --- | --- | --- | ---: | --- |
| 595 | `P9-S7-T01` | Assert no endpoint holds state git does not hold | A | 2.5-4 | `P9-S5-T01`, `P9-S2-T04` |
| 596 | `P9-S7-T02` | Run the load test against the cap and the limiter | A | 3-5 | `P9-S2-T03`, `P9-S7-T01` |
| 597 | `P9-S7-T03` | Build the Phase 9 gate script | A | 2.5-4 | `P9-S7-T02`, `P9-S6-T04`, `P9-S3-T03` |
| 598 | `P9-S7-T04` | Hold the Phase 9 exit review | gate | 1-2 | `P9-S7-T03` |

---

## 3. Checking the backlog

```
python _plan/_workflow/scripts/verify_execution.py
```

It enforces the properties that make one-by-one execution safe. Each has been violated by this
backlog at least once:

- every `depends_on` resolves to a real task, and no task waits on a later phase;
- the dependency graph is acyclic, so something is always ready;
- exactly one task creates each path, and every task that modifies a path waits on its creator;
- every file named in a `verify` command is built by the task itself or by one of its ancestors
  -- the check against a verification that fails with `command not found`;
- `seq` is a contiguous 1..N and never places a task before one of its dependencies;
- no `verify` is a weak one that cannot fail, and an `agent` task either names a runnable command
  or says why no machine check is possible.

```
python _plan/_workflow/scripts/render_execution_plan.py --check
```

re-renders this document from the backlog and fails if the committed copy has drifted.
