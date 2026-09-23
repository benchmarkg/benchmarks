# `_workflow/` — the provenance the plan still depends on

The plan was produced by a pipeline: six parallel reconnaissance researchers, drafting of all
sixteen documents, eighteen adversarial critiques, a four-question decision panel, a five-lens
whole-corpus audit and reconciliation, and finally the execution decomposition into
`execution/tasks.yaml`.

**This directory is not an archive of that pipeline.** It holds the three things the plan still
points at, and nothing else. The critiques, the audit findings, the intermediate phase
decompositions, the raw backlog and the one-time generator scripts were removed on **2026-09-22**;
every one of them had been applied to the documents, and no document in the set cited any of them.
The reasoning that survived is in the documents, in place, which is why they were written that way.

**Before you change anything in `_plan/`, and after:**

```
python _plan/_workflow/scripts/verify_corpus.py
python _plan/_workflow/scripts/verify_execution.py
```

---

## What is here

```
_workflow/
├── recon/        six reconnaissance reports, 2026-09-17
│                 the source behind most third-party facts in the plan, which cites
│                 them as recon:landscape, recon:sources, recon:domains, recon:tech,
│                 recon:epoch-assets and recon:ai-features
├── decisions/    D1-D4, adjudicated 2026-09-21
│                 the record of reasoning behind the four settled questions in
│                 README §3. The plan documents are the current state; these explain
│                 why that state is what it is
└── scripts/
    ├── verify_corpus.py          checks the nineteen documents against each other
    ├── verify_execution.py       checks execution/tasks.yaml
    └── render_execution_plan.py  renders 16-execution-plan.md from the backlog
```

Everything in `recon/` carries an **as-of date of 2026-09-17** and was perishable when it was
written. Re-verify before acting on any version pin, price, rate limit or competitor status; see
README §5.

---

## The three scripts

**`verify_corpus.py`** re-derives every vocabulary from `02-taxonomy.md` — the only document that
owns them — and checks the rest of the corpus against it: family, subdomain, capability and group
counts; the capability-group rollup being a strict partition; the coverage-grid arithmetic; the seed
column summing to its stated total; every relative link and heading anchor; H1 conformance; and
retired field names.

**`verify_execution.py`** checks the backlog, which fails in ways a prose plan cannot. Each check
exists for a failure this backlog actually had: a dependency resolving to nothing, a cycle, a task
waiting on a later phase, two tasks both claiming to create one file, a `verify` command that runs a
script no earlier task builds, a `seq` that puts a task before its own inputs, and a `verify` that
cannot fail.

**`render_execution_plan.py`** regenerates `16-execution-plan.md` from `execution/tasks.yaml`.
`--check` fails if the committed document has drifted. Never hand-edit the document; edit the YAML.

Both verifiers are deliberately mechanical. Judgement belongs in review, and a linter that cries
wolf gets ignored.

---

## What the 2026-09-21 pass fixed, and why the ownership rule exists

The 2026-09-17 run drafted all sixteen documents in parallel from a shared brief. Each author
restated the others' figures in its own prose, the copies drifted independently, and nothing
detected it. A mechanical count on 2026-09-21 found **26 defects**, including:

- Three different subdomain counts in circulation (205, 198, ~174) and two different coarse-grid
  sizes (228, 144), none of which matched the vocabulary as written.
- `12-analytics-and-trends.md` citing **`02-taxonomy.md` §4.3** by name for a capability-group
  vocabulary that **did not exist anywhere in the corpus**, while `10-visualization.md`
  independently assumed a different number of groups. The coverage matrix — the project's headline
  output — rested on a vocabulary nobody had written.
- A CI check asserting the capability and subdomain vocabularies were disjoint when four slugs were
  in both, so the check would have failed on day one.
- A per-family curation column summing to 333 beside prose saying "~300" and a roadmap saying "308",
  with one family targeted below both stated floors.

All 26 are fixed. The lesson is recorded in the plan itself and enforced by `verify_corpus.py`:
**one document owns each fact; every other document links to it.** Agreeing copies are a defect
waiting to happen, not a passing state.

---

## What the 2026-09-22 pass fixed

The execution decomposition inherited the same class of problem one level down: the backlog was
written stage by stage, and the seams between stages were prose rather than references. 165
structural failures, all now closed:

- **49 dependencies written as descriptions instead of task ids** — `P0-schema/*.py`,
  `P1-(data/benchmarks earth-climate)`, `P3-headroom-json`. Each was resolved to the task that
  actually produces the named artifact.
- **115 paths claimed as created by more than one task**, up to eleven tasks for
  `taxonomy/domains.yaml`. Exactly one task now creates each path; the rest declare `modifies` and
  wait on the creator. This is what the `modifies` field is for, and it is why a task that only
  edits legitimately has an empty `produces`.
- **119 tasks whose `verify` ran a script no earlier task built**, 53 of which no task built at all.
  Every one would have failed with `command not found`, which reads as a flaky check rather than as
  unfinished work.
- **`claims.json` and `derived/comparability.json` were emitted by nothing**, although
  `08-infrastructure-and-build.md` specifies both and Phase 6's own entry condition requires them.
  The Comparison Workbench had no data to render. `P3-S10-T03` now emits them.
- **The `seq` field was added**: a deterministic topological sort of the dependency graph. Document
  order is grouped for reading and is not a safe execution order — seven tasks sat before something
  they depended on.

Two of these were gaps in `verify_execution.py` itself rather than in the backlog: its shape check
had no case for a task that only edits existing files, and it had no check at all that a `verify`
command names something that exists by the time it runs. Both are now checks.

A second pass the same day applied the blocker and fabrication findings from the three stress
reports, which had been written but never applied:

- **Ten `bench` subcommands were declared in 05 §3, invoked by tasks, and built by nobody.**
  `bench tag-gap` alone appeared in the steps of 41 curation tranches. Four builder tasks now exist
  — `P0-S5-T08` (`check-links`), `P1-S2-T10` (`promote`, `resolve`, `tag-gap`), `P1-S2-T11`
  (`gaps`), `P3-S1-T07` (`report`) — and `verify_execution.py` gained `check_cli_surface`, which
  fails when a `verify` runs a subcommand no earlier task builds. Two of these were also ordering
  defects: `bench gaps` was used in Phase 1 and built in Phase 4, `bench report` used in Phase 3 and
  built in Phase 5. Phase 4 and Phase 5 now extend those tools rather than creating them.
- **Thirteen executor misclassifications.** `P0-S10-T01` would have had an agent assert 100 facts
  about two named competitors and pass a verify that only checked the sampler was seeded; it is now
  `agent-draft`, re-priced from 2–4 h to 5–8 h, and its verify requires a `checked_by` and a
  resolvable `evidence_url` per row plus an independent human re-run of ten of the fifty.
  `P3-S4-T01` built a host allowlist whose two real values sit in 07 §2.2, a section it was not told
  to read, and that allowlist decides the top verification rung on 828 published rows; it now reads
  §2.2 and is `agent-draft`.
- **Orphaned deliverables.** The landing page — Phase 2's first exit criterion — had no task.
  Neither did `GOVERNANCE.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md` (which the schema-change gate
  needs somewhere to write to), the HELM crosswalk, or the `Dispute` entity that the dispute issue
  form, 05 §8's both-positions rule and the SOTA rule all depend on.
- **Three ADR numbers were claimed by two documents each.** Numbers are now blocked per phase:
  P0 0001–0006, P1 0007–0009, P2 0010–0013.
- **ARC-AGI-3 was filed under `games-planning/`** while 02 §12 gives it
  `general-intelligence/novel-task-acquisition`. Since 05 §2 derives the path from the domain
  family, the entry would have failed its own tier-2 check.
- **The 53 scripts adopted in the first pass got real step text.** Declaring a path under `produces`
  made ownership honest but left the instruction incomplete — an agent would have done the work and
  never learned it also had to write the checker its own `verify` runs.

A third pass took the remaining stress findings. Eight agents re-validated every finding against
the current backlog — the reports predate the two repair passes, so nothing was applied on trust —
and an adversarial verifier had to fail to refute each proposed change before it was applied. **183
defects were proposed live, 149 survived, 142 were applied** across 74 tasks after conflict
resolution; the 34 refuted ones are recorded as rejected, several because the finding itself was
wrong about what a document said.

What that pass changed, beyond the field edits:

- **`bench diff` was declared in 05 §3 and built by nobody; `bench eval` was invoked by three
  Phase-6 tasks and declared nowhere in the corpus.** 05 §3 states it is the CLI's only
  specification and that "other documents add to this surface, they never invent on it", so the
  second is a rule violation rather than an omission. `bench diff` is now built by `P5-S7-T06`,
  `bench eval` by `P6-S3-T09`, and 05 §3 gained the `eval` signature and row.
- **Five modules sat under `src/derived/`, a tree 05 §2's layout does not contain** and which
  appears in no document — only in the backlog. All are retargeted to `tools/build/`, which
  exposed two genuine duplications the mechanical pass could not see because the strings differed:
  `comparability.py` and `saturation.py` were each being written twice against one spec.
- **A zero-width space (U+200B) was corrupting a workflow path**, which had been hiding a real
  two-creator collision on `.github/workflows/evals.yml`. Removing the character surfaced it.
- **The mean/median contradiction**: three Phase-3 tasks required publishing a mean that 12 §8
  forbids ("report median and the share at zero, not the mean. The mean hides a bimodal
  distribution"), and `P4-S2-T08`'s test would have failed Phase 3's own output.
- **Six document fixes**, each a case where the document was the last stale copy of a fact the
  rest of the corpus already had right: 10 said "five categorical refusals" above a table of six
  and named `no_aggregate_by_design`, a field appearing once in the corpus against
  `no_legitimate_aggregate`'s eleven; 14 put the generated TypeScript where four other documents
  do not; 05 §9 check 9a scanned `src/`.

**Two of the checks had been passing vacuously.** `check_verify_inputs` and `check_cli_surface`
were written with word-boundary escapes that reached the file as literal U+0008 bytes, so their
regexes matched nothing from the moment they were added. Repairing them surfaced **133 further
failures** — 69 test files no task declared and 64 missing edges to CLI builders — all since
closed. The lesson is the one the corpus already states about agreeing copies: a check that has
never failed is not evidence that it passes.

## What the 2026-09-22 widening changed

The plan as audited above built one thing: a citable, source-linked catalogue with a website. A
scope decision on the same day widened it to four surfaces, on the explicit condition that only the
first two are load-bearing.

- **Two new documents.** [17-packages-and-sdk.md](../17-packages-and-sdk.md) owns the installable
  surface — the Python SDK, the public CLI, the MCP server, the public API manifest and the two
  version numbers. [18-api-and-submissions.md](../18-api-and-submissions.md) owns the hosted query
  layer and the path by which an outsider's own run becomes a reviewed, badged claim.
- **The runner stopped being optional.** 13 was written to argue for deferring execution
  indefinitely. That argument was right about the danger and wrong about its cause: the danger was
  never execution, it was *whose machine and whose bill*. A runner shipped inside a package and run
  on the user's own infrastructure costs this project nothing per evaluation. The evidence gate
  survives but is repurposed — it now controls how far past the first adapter the phase goes, not
  whether the phase happens, because the real recurring cost is adapter maintenance.
- **Three new phases, 57 new tasks.** Phase 7 is the package, Phase 8 is the runner (renumbered from
  7), Phase 9 is the API and submissions. The backlog went from 537 tasks in 8 phases to **594 in
  10**, and from 1,576–2,884 h to **1,736–3,153 h**.
- **The non-goals were narrowed, not dropped.** "Not a leaderboard service that runs evaluations"
  became "not a *hosted* evaluation service". Metadata-only, no universal score, no benchmark
  authoring, no data hosting and no account required for reading are all unchanged.

**Two further checker bugs surfaced during the widening**, both of the same family as the U+0008
defect above. `VERIFY_PATH` used a word boundary where it needed a negative lookbehind, so it matched
the *tail* of a longer path and reported `packages/benchindex/tests/x.py` as the unbuilt
`tests/x.py`. `BENCH_BUILD` used a fixed 120-character window, so a step reading "Implement bench
search, bench show, bench compare and bench suite" registered only the first subcommand. Builder
detection is now sentence-scoped. Both bugs produced *false* results rather than silence, which is
why they were caught within one run rather than sitting undetected.

**What is still outstanding.** Three task splits are proposed and not applied — `P3-S3-T05` (the
927-string crosswalk, now priced 17–43 h as one task), `P4-S2-T06` (two adapters plus a
cross-check) and `P2-S8-T03` (accessibility harness versus remediation to zero). Each is priced at
the combined band, so splitting redistributes rather than adds. 10's performance-budget table is
still missing rows for `/trust/` and `/orgs/`; the backlog now makes measuring them an explicit
deliverable rather than inventing the numbers. And 07 §1.6 still declares four `bench ingest` flags
that 05 §3 does not, which 05 §3's own rule forbids.
