# The Universal AI Benchmark Index — Build Plan

## What this is

A faceted, source-linked, version-controlled **catalogue of AI benchmarks across every domain** —
language, code, mathematics, vision, audio, robotics, chemistry, biology, medicine, climate,
materials, games, agents, safety, society and more. It publishes as a static site backed by a git
repository of YAML files under CC-BY. Every number traces to a primary source and carries the
conditions that produced it as structured data, and the catalogue mechanically **refuses to rank**
numbers whose conditions differ. It never hosts benchmark data, never runs evaluations, and never
computes a universal score. The database is a build artifact; the YAML at a commit hash is the
citable thing.

**This is a plan, not an implementation.** Nothing here has been built. The eighteen design documents
below carry the decisions, each with its reason and its main risk, written so that someone —
including someone who is not us — can execute them or argue with them.
[16-execution-plan.md](16-execution-plan.md) is not a design document: it is those decisions
decomposed into **594 tasks across 87 stages and 10 phases**, each with a dependency, an owner and a
command that proves it done. It is generated from `execution/tasks.yaml` and is the thing you
actually work through.

**The catalogue is one of four surfaces.** The repository is the citable object and the site is how
it is read; both are load-bearing. The **package** ([17-packages-and-sdk.md](17-packages-and-sdk.md))
puts the catalogue and its refusals inside someone else's program — a Python SDK, the `bench` CLI, an
MCP server for agents, and a runner that evaluates on the user's own machine. The **API**
([18-api-and-submissions.md](18-api-and-submissions.md)) answers the queries static files serve badly
and takes in results from outside, through review. Neither of the last two is load-bearing, and
[00-vision-and-scope.md](00-vision-and-scope.md) §2.5 says why that must stay true.

**As of.** The reconnaissance underlying every third-party fact was done **2026-09-17**. The corpus
was drafted and revised **2026-09-21**, then audited, reconciled and mechanically verified
**2026-09-22**. Every version pin, price, rate
limit and competitor status in the plan is expected to have moved; see
[the state of the plan](#5-the-state-of-the-plan) before acting on any of them.

---

## 1. Reading order

The whole set is long enough that reading it front to back is a mistake. Pick a path.

### If you are deciding whether this is worth doing

Read **[00-vision-and-scope.md](00-vision-and-scope.md)** in full — it is written so that a reader
who reads only it understands the project, its exclusions, and what would count as failure. Then
**[01-landscape-and-positioning.md](01-landscape-and-positioning.md)**, which is the document that
matters most to this decision: three projects launched into this ground in 2026, every prior
cross-domain catalogue has died within 12–24 months, and §1–§3 say exactly what is left unoccupied
and why. Then **[14-roadmap.md](14-roadmap.md)** — the phase table, "Effort sizing", the stopping
rules and the risk register — because the honest answer to "is this feasible" is an effort number,
not an architecture. Finish with the twelve genuinely-unresolved rows named at the top of
**[15-open-questions.md](15-open-questions.md)**; the rest of that register is settled with a review
trigger.

*Skip entirely:* 04, 06, 07, 08, 09, 11, 13. They are implementation detail and none of them changes
the go/no-go. Skim 02 §0–§2 only, for what the taxonomy is for.

### If you are about to implement it

Read **[02-taxonomy.md](02-taxonomy.md)** properly before anything else. It is the only part of the
system that cannot be regenerated: code can be rewritten, but a thousand entries tagged against a
wrong vocabulary have to be re-read by a human. Then **[04-data-model.md](04-data-model.md)**
(entities, identity, the comparability rule) and
**[05-repository-and-workflow.md](05-repository-and-workflow.md)** (layout, CI, the no-PR
contribution path) — those two plus 02 are the whole Phase-0 surface. Then
**[08-infrastructure-and-build.md](08-infrastructure-and-build.md)** for the machine, and
**[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md)** with
**[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)** as a pair when you reach
ingestion — 06 is *what and why*, 07 is *how*.

Then stop reading and start working from **[16-execution-plan.md](16-execution-plan.md)**, which is
the actual task list: 531 items in dependency order, each naming what to read, what it produces and
the command that proves it done. Phase 0 is its first 66 tasks. Read
[14-roadmap.md](14-roadmap.md) §"Start here: the concrete first month" alongside it for the prose
argument about why that order, which the backlog deliberately does not repeat.

*Defer, do not skip:* 09 and 10 until Phase 2, 12 until Phase 4, 11 until Phase 6, 17 until Phase 7
and 18 until Phase 9. **13 is still last**, and reading it early mainly risks building it early —
but note it is no longer optional: the runner ships inside the package and executes on the user's
own machine, which is what removed the operating cost that made it deferrable in the first place.

### If you are a domain specialist checking whether the taxonomy respects your field

Read **[02-taxonomy.md](02-taxonomy.md)** §3 (find your family and its subdomains), §4 (the
capability axis), §11 (the cross-cutting rules, especially rule 5 — what counts as one benchmark)
and §12 (worked classifications of hard real benchmarks, including the non-language ones). Then
**[03-taxonomy-build-process.md](03-taxonomy-build-process.md)** §5–§6 for how definitions are
tested and how disagreement is measured, §12 for the reviewer programme you would be joining, and
§13 for what would tell us the taxonomy is wrong. If you care about the gap claims the project will
publish about your field, add [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.

*Skip entirely:* 05, 07, 08, 09, 10, 11, 13, 14. None of them can change whether the vocabulary is
right.

### If you are deciding whether to reuse or cite the data

[04-data-model.md](04-data-model.md) for what a record contains and the verification ladder,
[05-repository-and-workflow.md](05-repository-and-workflow.md) §10–§12 for releases, DOIs,
succession and licensing, and [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §6
for what a licence does and does not restrict. That is enough.

---

## 2. The documents

The third column is the one that matters. This corpus drifted because several documents each kept
their own prose copy of a shared number; the fix is a single owner per fact, and everything else
links.

| File | What it decides | What it owns canonically |
| --- | --- | --- |
| [00-vision-and-scope.md](00-vision-and-scope.md) | The problem, the three audiences, what the project is and is not, the principles, and what counts as success or failure | Corpus-shape counts and the counting rules that separate them (§8), including the Epoch row count; the working assumptions A1–A5 and the planning figure for weekly effort; success criteria S1–S11; the learned-entrant admissibility test |
| [01-landscape-and-positioning.md](01-landscape-and-positioning.md) | Who else is in this space, why every predecessor died, and the rule a curator applies before spending an hour on an entry | Every claim about a named third-party project and its as-of date; the definition of "overlap" and the overlap bands; the volume policy; the metadata-only invariant; the **ingest-versus-curate doctrine** that sets each family's `curation_posture`; the complement-and-alliance list |
| [02-taxonomy.md](02-taxonomy.md) | The eight facets and their full controlled vocabularies | **The eight facet vocabularies** — domain families and subdomains, capability terms, evaluation method, subject under test, data properties, lifecycle, governance and host, execution cost; the capability-group rollup (§4.3, D1); the **per-family seed allocation and its total** (§3, D2); the cross-cutting tagging rules (§11), including what counts as one benchmark |
| [03-taxonomy-build-process.md](03-taxonomy-build-process.md) | How the taxonomy gets built bottom-up, tested against real disagreement, governed and evolved | The bootstrapping stages and the failure log; the `taxonomy/*.yaml` file format; definition-quality rules; inter-rater reliability method and its floors; the limits on AI-assisted classification; the ADR process and template; term lifecycle and migration; taxonomy health metrics; the domain-expert review programme |
| [04-data-model.md](04-data-model.md) | Entities, fields, identity, provenance and validation tiers | The **fourteen entities and every field name**; slug and identity rules; the family/edition/child counting convention; the **verification ladder** and its ranks; `EvalConditions`, its material-field set and the `comparability_key`; the `ingestion` block and `IngestBatch`; the identity-resolution *procedure*; the Every Eval Ever crosswalk; the Python, Pydantic and codegen pins |
| [05-repository-and-workflow.md](05-repository-and-workflow.md) | The physical repository, how a change gets in, who checks it, and what happens when the maintainers stop | The directory layout and file naming; the `bench` CLI surface; the six-value curation ladder; the review matrix; **the contribution paths, including the issue-form path that does not require a pull request**; freshness display; corrections and disputes; the **CI check list and its numbering**; the workflow inventory and cron cadences; releases, DOI, succession and the 90/180-day triggers; the licences on our own outputs |
| [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) | Which sources exist, what each one is actually worth, what its terms permit, and what it costs a curator | Every per-source endpoint, rate limit, licence, ToS reading and `[M]`/`[D]`/`[E]`/`[U]` evidence grade with its as-of date; the discovery heuristics and their measured precision; the **manual sweep programme and its annual hours**; the tiered build order; the legal and ethical posture toward sources; the steady-state weekly curation budget |
| [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) | How the scrapers actually run, and how you find out one stopped working three weeks ago | The adapter contract and the single YAML emitter; where jobs execute and how state persists between runs; identity-resolution *scoring* (04 owns the procedure); the draft-PR output path; quality gates; observability on a zero-budget stack; our usage budget against each source's limits |
| [08-infrastructure-and-build.md](08-infrastructure-and-build.md) | How a directory of YAML becomes a fast static site that is still reproducible from a commit hash years later | Every build stage; **every build artifact, its filename, shape and size**; the technology picks and the measurements behind them; determinism, the Atlas layout basis and the drift gate; hosting and CI/CD; performance budgets; the cost model; supply-chain security; disaster recovery and bus factor |
| [09-design-system.md](09-design-system.md) | The visual language — how any surface looks and behaves | Type scale and font licensing; colour tokens and the palette and contrast checks; spacing and grid; the component inventory; data-visualisation rendering conventions; accessibility; dark mode; responsive strategy; voice and content design; the Astro `compressHTML` hazard; design governance |
| [10-visualization.md](10-visualization.md) | The interactive surfaces, view by view — what each one shows | The eleven views V1–V11 and their content; **the route table and URL grammar**; progressive disclosure; per-view performance budgets; what is deliberately not built |
| [11-ai-features.md](11-ai-features.md) | Semantic search and the suite builder, under a rule that the AI layer is a lens and never a source | The AI feature set and its non-AI fallbacks; the retrieval architecture; **model selection, the rate card and the AI cost model**; the guardrails; how we evaluate our own AI features and the labelling rates; privacy; what we refuse to build with AI |
| [12-analytics-and-trends.md](12-analytics-and-trends.md) | What gets computed from the data, with which caveats, and what will never be computed at all | **Headroom**, saturation, coverage density, the gap score and its weights; adoption and influence; liveness and decay; trust and hygiene metrics; ecosystem analysis; the values in `taxonomy/thresholds.yaml`; the statistical discipline rules; the list of analyses we will not publish |
| [13-execution-runners.md](13-execution-runners.md) | The deferred execution layer: why it is last, what it would be, and when to stop | The **instruments** that measure the Phase-7 gate (14 owns the gate itself); the runner design and adapter contract; isolation, safety and cost control; the stopping rule; what is explicitly never built |
| [14-roadmap.md](14-roadmap.md) | Phases, deliverables, exit criteria, effort sizing and risk | **The phase table and every phase gate**; the corpus-wide version-pin as-of rule; the effort model and the per-entry curation rate; the critical path; stopping rules and re-plan triggers; the risk register; the concrete first month |
| [15-open-questions.md](15-open-questions.md) | Every decision still needed, each with a recommendation so that work proceeds today | The decisions register: each question, why it matters, the current recommendation, the **trigger** that reopens it, and its blast radius. It is also the record of answered decisions until public v1 |
| [17-packages-and-sdk.md](17-packages-and-sdk.md) | The installable surface: what `pip install` gives you, what it promises, and what it refuses | The three package artifacts and why there is no JavaScript client; the **public API surface** and the manifest that governs it; the two version numbers and the one-way compatibility rule; the offline and air-gapped behaviour; the MCP tool set; the packaging boundary and the no-second-model-definition rule |
| [18-api-and-submissions.md](18-api-and-submissions.md) | The hosted query layer and the path by which an outsider's own result becomes a reviewed claim | The endpoint set, response envelope and deprecation window; the rate, cost and **spend-cap degrade** rules; the submission envelope and its mandatory fields; the review and badging path; the anti-gaming measures **and the defence the project does not have** |
| [16-execution-plan.md](16-execution-plan.md) | The whole plan as an ordered, checkable backlog — what to do next, who can do it, and what proves it finished | **Every task, stage and phase id**; the `seq` execution order; the four executor classes and what each means; the per-task dependency, `produces`/`modifies` and `verify` contract. Generated from `execution/tasks.yaml`, which is the owner |

---

## 3. The settled decisions

Four questions that several documents had been answering differently were adjudicated on
**2026-09-21** by a dedicated panel and applied across the corpus. They are closed. If you think one
is wrong, write the argument down as a finding — do not make an edit that contradicts one, because a
half-applied decision is strictly worse than an unapplied one.

| # | What it settled | Record of reasoning |
| --- | --- | --- |
| **D1** | The capability-group vocabulary — the coarse (column) axis of the coverage matrix, a verified strict partition of the capability terms, enumerated canonically in [02-taxonomy.md](02-taxonomy.md) §4.3. Until this decision it was cited by two documents and enumerated by none | [`_workflow/decisions/D1-capability-groups.md`](_workflow/decisions/D1-capability-groups.md) |
| **D2** | The seed total and its per-family allocation, owned by [02-taxonomy.md](02-taxonomy.md) §3 and summing by construction; and three distinct floors with three distinct jobs — a hard launch gate, a Core-family launch gate, and a specialist-credibility target reached by v1.x. A family that cannot reach its floor ships muted, not padded | [`_workflow/decisions/D2-seed-targets-and-floor.md`](_workflow/decisions/D2-seed-targets-and-floor.md) |
| **D3** | The identifier scheme: subdomain ids are family-qualified paths, capability ids are bare slugs, and the facet is carried by the field name rather than a prefix on the value. The slugs that appear in both vocabularies are declared homographs, not collisions; CI check 9c is replaced by three correctly-scoped checks | [`_workflow/decisions/D3-vocabulary-namespacing.md`](_workflow/decisions/D3-vocabulary-namespacing.md) |
| **D4** | Domain family is **never** encoded by hue, anywhere. The families roll up into six presentation groups whose only job is ordering and banding; the grouping is marked `display_only` and machine-forbidden from the filter grammar and from any published coverage or gap number | [`_workflow/decisions/D4-nineteen-family-cascade.md`](_workflow/decisions/D4-nineteen-family-cascade.md) |

**The decision documents are the record of reasoning; the plan documents are the current state.** If
the two disagree, the plan is current and the decision explains why it is what it is.

---

## 4. How to change the plan

One rule carries the plan's internal consistency: **one document owns each fact; every other
document links to it.**

The failure this rule exists against is specific, and it has already happened here. Sixteen documents
were drafted in parallel from a shared brief, and each author restated the others' figures in their
own prose. The copies then drifted independently and nothing detected it — three different subdomain
counts and two different coverage-grid sizes were in circulation, a per-family column summed to a
different total than the prose beside it, and two documents cited a section of
[02-taxonomy.md](02-taxonomy.md) by name for a vocabulary that did not exist anywhere in the corpus.
The coverage matrix, which is the project's headline output, rested on a vocabulary nobody had
written.

So:

1. **If a number is wrong, fix it in the owning document.** Find the owner in the table above, change
   it there, and make every other mention a link rather than a second copy. A restated number is a
   defect even when the two copies currently agree — agreeing copies are a defect waiting to happen,
   not a passing state.
2. **If a decision changes, write the decision down before editing nineteen files.** Use D1–D4 as the
   template: what it settles, what it depends on, what it costs, and an explicit
   edits-required-by-file-and-line list. A decision applied straight into the prose leaves nobody
   able to tell later whether an inconsistency was a mistake or an intention.
3. **Run both checkers before and after.** From the repository root:

   ```
   python _plan/_workflow/scripts/verify_corpus.py
   python _plan/_workflow/scripts/verify_execution.py
   ```

   The first re-derives every vocabulary from [02-taxonomy.md](02-taxonomy.md) and checks the rest of
   the corpus against it: family, subdomain, capability and group counts; that the capability-group
   rollup is a strict partition; the coverage-grid arithmetic; the seed column summing to its stated
   total; every relative link and heading anchor; H1 conformance; and retired field names.

   The second checks the backlog, which fails in ways prose cannot: a dependency that resolves to
   nothing, a cycle, a task waiting on a later phase, two tasks that both claim to create one file, a
   `verify` command that runs a script no earlier task builds, and a `verify` that cannot fail. Both
   are deliberately mechanical — judgement belongs in review, and a linter that cries wolf gets
   ignored.
4. **Do not hand-edit the generated blocks.** The term lists and counts in
   [02-taxonomy.md](02-taxonomy.md) §§3–10 and §14 are rendered from `taxonomy/*.yaml` and checked
   byte-for-byte in CI. Edit the YAML. The whole of
   [16-execution-plan.md](16-execution-plan.md) is likewise rendered from `execution/tasks.yaml`:
   edit the YAML and re-run `_workflow/scripts/render_execution_plan.py`, whose `--check` mode fails
   if the committed document has drifted.

---

## 5. The state of the plan

**Settled.** The scope and the non-goals; faceted classification with one navigational spine and
seven orthogonal facets; all eight vocabularies; the schema chain (Pydantic canonical, JSON Schema
generated from it, TypeScript generated from that, all three committed and CI-gated);
`EvalConditions` as a separate referenceable entity with a computed comparability key; two unsharded
JSON build artifacts rather than the sharded scheme an earlier draft called for; CC-BY, a DOI and
forkable-at-commit from day one with a written succession story; an issue-form contribution path that
does not require a pull request; curation tiered by existing coverage — ingest where someone else
already maintains the numbers, hand-curate where nobody does; the Epoch ingestion policy; the AI
layer as a lens and never a source; suite assembly rather than benchmark authoring; and the four
decisions in §3.

**Open.** [15-open-questions.md](15-open-questions.md) is the register and this README does not
duplicate it. Read its index first: most rows are decisions with a review trigger rather than live
arguments, and the twelve where a reasonable person could still choose differently today are named at
the top of that index. Every row carries a recommendation, so nothing in it blocks starting.

**Perishable, and to be re-verified before anyone acts on it.** Every version number, price, rate
limit, bundle size, free-tier quota, open-issue count, registry "last published" date, file-size
measurement, licence tag and service status anywhere in these nineteen documents was checked on
**2026-09-17**, except in `17` and `18`, which postdate that sweep. [14-roadmap.md](14-roadmap.md) §"Version pins and third-party facts: as-of date"
owns that statement for the whole plan and names which document records which class of fact.
Re-verify all of them at the start of Phase 0, before writing the lockfile; none of them is
load-bearing on the schedule. Three changed in the nine months before the plan was written — OpenAlex
went metered, Semantic Scholar's anonymous tier died, OpenReview grew a bot challenge — which is the
rate to expect. The competitor material in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) has the shortest shelf life of
anything here: it describes live services run by people who can falsify any sentence in it in an
afternoon, and §1.9 states how far its negative claims are supported.

**Known gaps in the plan itself.** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §10 and
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §12 each list what they deliberately
did not settle and hand those items to [15-open-questions.md](15-open-questions.md) §F. No document
in the set is a stub.

---

## 6. How this was produced

The corpus was produced by a pipeline — six parallel reconnaissance researchers, then drafting, then
eighteen adversarial critiques, then a four-question decision panel, then a five-lens whole-corpus
audit and reconciliation, then the execution decomposition. [`_workflow/`](_workflow/) keeps only the
part of that history the plan still depends on, and its [runbook](_workflow/README.md) says what each
piece is for.

**What is kept.** The six reconnaissance reports, because the plan cites them as `recon:landscape`,
`recon:sources`, `recon:domains`, `recon:tech`, `recon:epoch-assets` and `recon:ai-features` — they
are the source behind most third-party facts in it. The four adjudicated decisions D1–D4, because §3
above points at them as the record of reasoning. And the three scripts that check and render the
plan.

**What was removed, on 2026-09-22.** The eighteen critiques and the five audit-lens findings, all of
which were applied to the documents and are now superseded by them; the eight intermediate phase
decompositions and the raw backlog they were compiled into, superseded by `execution/tasks.yaml`; the
five one-time generator scripts that authored a corpus which now exists; and the pre-revision
snapshot trees. None of them was cited by any document in the set. If you want to know why a document
says what it says, the document says so in place — that was the point of writing it that way.
