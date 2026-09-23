# 14 -- Roadmap

This is the synthesis document. Every other document in the set describes *what* to build; this one
says in what order, why that order, what "finished" looks like at each step, what will go wrong, and
-- new in this revision -- **when to stop and re-plan**. Read
[00-vision-and-scope.md](00-vision-and-scope.md) first for the constraints this plan operates under,
and [01-landscape-and-positioning.md](01-landscape-and-positioning.md) for the competitive reality
that reshaped it.

---

## The sizing assumption, stated up front

**One to two people working part-time with heavy AI assistance.** Concretely: roughly **15--25 hours
a week of combined effective effort**, with **20 h/week as the planning figure**. Every range below
is in **calendar weeks at that intensity**, not person-weeks of a funded team. If you are reading
this with a different team size, rescale the curation numbers first and the engineering numbers
second, because they scale differently.

**Curation, not engineering, is the long pole.** This surprises most people planning a project like
this, and planning as though the site is the hard part is the most common way these efforts stall.
The whole build pipeline -- Pydantic schema, JSON Schema and TypeScript generation, two static JSON
artifacts, an Astro site, a WebGL atlas, a design system, a Pagefind index, the Epoch adapter and the
derived-metrics layer -- is on the order of **185--330 hours**. The catalogue those artifacts render
is on the order of **273--688 hours** of hand-curation alone, plus a further 230--455 hours of
taxonomy authoring, discovery sweeps and outreach that no phase row used to carry, and it never stops
needing attention. The effort breakdown in
[Effort sizing](#effort-sizing-where-the-hours-actually-go) makes this explicit; look at it before
you argue with any phase estimate.

The mortality evidence in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) says
the same thing from the other direction. Stanford CRFM's Ecosystem Graphs was *exactly* this
architecture -- a structured catalogue as files in git with a static site -- built by a
well-resourced Stanford lab, and its last push was 2025-01-24. The architecture was never the
problem. The curation treadmill was, and it still is.

### The headline schedule, with its uncertainty attached

**Public v1 lands six to thirteen months in on the phase-scoped work alone, and eight to eighteen
months once the taxonomy authoring, discovery sweeps and outreach that run alongside every phase are
counted. Both figures are driven almost entirely by the per-entry curation rate.** The two are
derived, and the reason there are two, in
[Effort sizing](#effort-sizing-where-the-hours-actually-go). Quote the second one to anyone asking
when the site goes live.

That is a range, not a point estimate, and the range is honest rather than defensive. The domain
research puts a fully-sourced entry at **30--90 minutes with heavy AI assistance**; the canonical
seed total of **320 entries** ([02-taxonomy.md](02-taxonomy.md) §3) is therefore **175--495
person-hours**, taking the ten stress entries at 2--3 h
([00-vision-and-scope.md](00-vision-and-scope.md) §8 and
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §11 carry the same per-entry rate
against the recon's older 300-entry figure).

**This document owns the per-entry rate, and the rate has never been measured.** It is
[recon:domains]'s judgement, formed before this schema, this taxonomy and this tooling existed, and
every document that quotes it should say so and link here rather than re-assert it. The 20-entry
checkpoint below exists to replace it with a measurement. A 3x spread on the single largest line item propagates
into a 3x spread on the schedule, and the earlier version of this document hid that by silently
picking 45 minutes and publishing "six to eight months" as though it were measured. It was not
measured. It was chosen.

**The measurement that collapses the range is the 20-entry checkpoint.** It yields the first real
per-entry time on this schema, this taxonomy and this tooling. **Re-cut every estimate in this
document against it before Phase 1 scales past twenty entries**, and record the measurement in an
ADR so the next re-plan has a baseline rather than an argument. Until that number exists, treat
every week figure below as a range with the low end contingent on 30--45 minutes an entry and the
high end on 90.

### Why public v1 is later here than in the earlier draft

The archived roadmap put public v1 at four to six months. This one puts it at **six to thirteen on the
phase-scoped work and eight to eighteen all-in**, and
the four reasons are worth recording so nobody "optimises" them back out:

1. **The seed target went up.** The domain research puts a credible cross-domain seed at **320
   Tier-1 benchmark families**, 12--25 per family ([02-taxonomy.md](02-taxonomy.md) §3), with a hard
   floor of 12 at launch and 18 for the seven Core families; fifteen is the credibility target every
   family reaches by v1.x, not a launch gate. A cross-domain index that a roboticist dismisses in
   thirty seconds has failed at the only thing it was for.
2. **Survivability work moved to day one.** Licence, DOI, citation file, succession document and a
   non-PR contribution path are now Phase 0 and Phase 2 deliverables rather than nice-to-haves.
   Ecosystem Graphs could not be rescued when Stanford's attention moved on because it had **no
   licence at all**. That is a two-hour job that, skipped, makes every other hour unrecoverable.
3. **The competitive ground is occupied.** BenchmarkList launched 2026-07-15 with 2,545 benchmarks;
   Benchmark Radar published 2026-09-10. Shipping a thin catalogue fast is no longer a strategy,
   because "thin but first" is not available. What is available is "narrow, deep, sourced, open and
   forkable", and that takes longer to produce.
4. **The non-LLM result claims are now funded.** The earlier draft made "at least 60 claims from
   non-LLM domains" a launch gate while costing nothing for them. Those sixty claims *are*
   differentiator 1, they are the most expensive claims in the project at 60--90 minutes each, and
   they now carry their own deliverable and their own effort row. See
   [Phase 3](#phase-3----result-claims-provenance-and-the-epoch-ingestion-adapter).

---

## Version pins and third-party facts: as-of date

**This block governs the whole plan, not only this document.** Every version number, price, rate
limit, bundle size, open-issue count, registry "last published" date, free-tier quota, file-size
measurement and service status **anywhere in these nineteen documents** was verified on
**2026-09-17** and is expected to have moved. **Re-verify all of them at the start of Phase 0
before writing the lockfile.** None of them is load-bearing on the schedule.

**Two documents are outside that sweep and the difference matters.**
[17-packages-and-sdk.md](17-packages-and-sdk.md) and
[18-api-and-submissions.md](18-api-and-submissions.md) were written after 2026-09-17, so nothing in
them was verified on that date and this block cannot vouch for them. What they assert about third
parties is small and is named here so it is not mistaken for checked: **`benchindex` availability on
PyPI** — which `17` §9 already carries as an open question and which is unverified on PyPI, npm and
GitHub alike; **PyPI Trusted Publishing** as the release mechanism; and the **Python 3.11 consumer
floor**, which is a choice rather than an observation but depends on the dependency set's own
floors. `18`'s rate limits, burst sizes and GraphQL point costs are *our* policy, not third-party
facts, and are not covered by this block at all. Check the three above with the rest at the start of
Phase 0.

The detail — the figure, its source and its evidence grade — is recorded in the documents that
derive it, and those are the ones to change when a pin moves:

| Class of fact | Recorded in |
| --- | --- |
| Third-party licences and terms, with `[M]`/`[D]`/`[E]`/`[U]` evidence grades | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8 |
| Build toolchain, hosting quotas, artifact measurements, search timings | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| Model IDs, prices, token counts, tier caps | [11-ai-features.md](11-ai-features.md) §5 (`config/ai-models.yaml`, with a `verified_on` per row) |
| Python/Pydantic/codegen pins | [04-data-model.md](04-data-model.md) §14 |
| Font licences, Astro behaviour, chart-library issues | [09-design-system.md](09-design-system.md) |
| Chart, graph and search library versions, release dates, bundle sizes and issue counts | [10-visualization.md](10-visualization.md) §1 |
| Competitor status, coverage and closedness | [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1--§2 |

The pins this document names by way of illustration: Pydantic 2.13.5, Astro 7.3.3, Node >=22.12,
`json-schema-to-typescript@16.0.0`, ECharts 6.1.0, sigma.js 3.0.3, cosmos.gl 3.4.1, Pagefind 1.5.2,
scikit-learn 1.9.1, Python 3.12, the Cloudflare Workers free-tier limits, the Anthropic tier caps and
per-call prices, and every "last published" date used to reject a library.

A plan whose stated premise is that unsourced confident data destroys trust cannot assert twenty
perishable third-party facts without saying when it checked them. This block is that statement, and
it is deliberately the *only* one: nineteen per-document as-of blocks would drift apart within one
revision pass, which is the failure this pass exists to repair. Where a specific figure carries more
risk than the rest, it is marked inline below.

---

## Phase table

| Phase | Outcome | Size (one person, serial) |
| --- | --- | --- |
| **0** | Schema and taxonomy foundation, validated against ten stress entries | 3--6 wk |
| **1** | Seeded index, breadth-first: 320 **benchmark families** across all 19 domain families; taxonomy and gap analysis published | 9--25 wk |
| **2** | Public static site: detail pages, faceted browse, Atlas, design system, contribution path | 4--8 wk |
| **3** | Result claims (LLM *and* non-LLM), provenance, comparability keys, headroom, Epoch ingestion adapter | 7--13 wk |
| **4** | Coverage, gaps, ecosystem view, release feed, Croissant extension, DOI -- **public v1** | 3--5 wk |
| **5** | Ingestion at scale and freshness automation | 5--8 wk |
| **6** | AI layer: semantic search and suite builder | 8--12 wk |
| **7** | The package: Python SDK, public CLI and MCP server on PyPI | 4--6 wk |
| **8** | Local evaluation runner, shipped in the package and run on the user's own infrastructure | 11--20 wk |
| **9** | Hosted query API and community submissions through review | 4--7 wk |

**Two different things are called a "family" in that row and the plan uses both words deliberately.**
A **domain family** is one of the nineteen top-level domains ([02-taxonomy.md](02-taxonomy.md) §3). A
**benchmark family** is the counting unit for benchmarks — BraTS, DCASE, CASP, LifeCLEF, Matbench
Discovery — not its editions, tasks, tracks or splits ([02-taxonomy.md](02-taxonomy.md) §11 rule 5).
Where this document says "320", it always means 320 benchmark families, and
[00-vision-and-scope.md](00-vision-and-scope.md) §8's row label "Benchmark families" is the model to
copy. Counting children instead multiplies by roughly 3--6x, and again by the number of editions, and
makes every number in this plan meaningless.

**Phases 6 and 7 were re-sized on 2026-09-21** against the bottom-up estimates in the documents that
own them: [11-ai-features.md](11-ai-features.md) §10 puts the AI layer at 150--243 h (7.5--12 weeks
at 20 h/week), and [13-execution-runners.md](13-execution-runners.md) §8 puts the execution layer at
190--350 h (9.5--17.5 weeks). Both were built from steps rather than from a week count, so both win
over the earlier top-down figures; both ends are rounded outward to whole weeks. Neither move touches
the critical path, because both phases are post-v1.

**To public v1, one person, strictly serial: 26--57 calendar weeks -- six to thirteen months.** That
is the sum of Phases 0--4. **It prices the phase-scoped work only.** Four workstreams -- taxonomy
definition authoring, the taxonomy build process, the manual discovery sweeps and the outreach
programme -- run alongside every phase rather than inside one, are owned and sized by `02`, `03`,
`06` and `15`, and add **230--455 hours, or 11--23 further weeks**. The all-in figure is **36--77
weeks, eight to eighteen months**, and that is the number to plan against unless you actually have
two people. The breakdown, and why the two figures both exist, is in
[Effort sizing](#effort-sizing-where-the-hours-actually-go).

**To public v1, two people with a clean split: roughly 20--46 phase-scoped weeks** (32--69 all-in).
This is not a discount for
working harder; it is what you get when one person owns curation and the other owns engineering with
no shared work, so Phase 2 and the engineering half of Phase 3 genuinely run alongside Phase 1. See
[Critical path](#critical-path) for the conditions that have to hold.

Phases 5--9 are post-v1 and are sized for information, not committed. Phase 8 has an explicit
evidence gate and may never be built.

### Which document is canonical for scale

[00-vision-and-scope.md](00-vision-and-scope.md) §8's scale table describes the **shape of the
corpus** across three horizons — launch, twelve months post-launch, and steady state at year two.
**This document is canonical for anything scoped to a phase**, and `00` §8 says so itself. The two
now agree and the earlier disagreement is closed: `00`'s launch column carries 320 benchmark families
and a hand-curated claim row split 60--80 non-LLM plus 50--80 LLM, which is exactly the 110--160 this
document gates on, and its 500--700 figure sits under "twelve months post-launch" where it belongs.

What this document gates on, stated once: **v1 ships at 320 benchmark families with a launch gate of
290, and 110--160 hand-curated claims with a gate of 130, of which at least 60 are non-LLM.**

One naming point, because it caused the original divergence: `00` §8's launch column is **the end of
Phase 4**, not Phase 2. Phase 2 is the first public *build* of the site; the claims in that column
arrive in Phase 3 and the coverage figures in Phase 4. A reader who schedules `00`'s launch column
against Phase 2 will start the Epoch ingest before the claims schema exists.

### Why the AI layer sits after public v1, and why that will feel wrong

The temptation to build the AI feature early will be strong. It demos well, it is the newest part of
the plan, and it is the part the user explicitly asked about. Build it fourth from last anyway.

The governing rule from [11-ai-features.md](11-ai-features.md) is the reason:

> **THE AI LAYER IS A LENS, NEVER A SOURCE.**
> Retrieval is deterministic, client-side, and reproducible from the static artifact at a commit
> hash. The model's only jobs are to translate English into a facet query, to order and annotate
> entries the deterministic retriever already selected, and to narrate verdicts that code computed.
> Nothing the model emits is ever stored in `data/`, and nothing it emits is citable. The citable
> surface remains the YAML at a commit SHA. **THE MODEL NEVER PRODUCES A NUMBER.**

A lens over nothing magnifies nothing. Semantic search across 60 entries is worse than a filter
dropdown. A suite builder that recommends eight benchmarks from a catalogue with three robotics
entries will confidently recommend the wrong three, and the user has no way to tell, because absence
looks exactly like completeness. That is the single worst failure mode in the entire feature set:
**the model silently omits a domain the index simply has not curated, and the omission reads as an
authoritative statement that nothing exists.** The only defence is a catalogue complete enough that
the "Not covered" section is a real finding rather than an artefact of our own gaps.

**One deliberate exception, and it matters.** The *maintainer-facing* AI tooling -- F6 curation
copilot (draft an entry from a paper or repo URL, with a verbatim source quote and a confidence flag
attached to every field) and F7 near-duplicate detection -- is used from Phase 1 onward. It is an
internal accelerator behind a mandatory human gate, writing only to `drafts/` with
`curation.verification_status: ai-drafted-unverified` (the ladder in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §4 owns that value; there is no
separate `status` field), which the site build refuses to publish. It is not a public surface, it
is not citable, and it does not change the ordering argument. Build the copilot as a script in
Phase 0/1, not as a product.

The claim that the copilot roughly halves per-entry curation time is **(unverified -- confirm before
relying on this)**: it is an expectation about an unbuilt script with no pilot behind it, and it is
the single largest swing in the effort table. **The 20-entry checkpoint measures it**: ten entries
drafted with the copilot and ten without, both timed, the result recorded in the ADR. If the
speedup is not real, the curation estimate moves to the top of its range and the allocation in
[02-taxonomy.md](02-taxonomy.md) §3 gets re-cut -- see
[Stopping rules and re-plans](#stopping-rules-and-re-plans).

---

## Phase 0 -- Schema and taxonomy foundation

*3--6 weeks.* Everything downstream inherits these decisions. Time spent here pays back more than
anywhere else in the plan, and the phase is short only because the thinking is already captured in
[02-taxonomy.md](02-taxonomy.md), [03-taxonomy-build-process.md](03-taxonomy-build-process.md) and
[04-data-model.md](04-data-model.md).

### Deliverables

- `taxonomy/*.yaml` -- all eight facet vocabularies, every term carrying `id`, `label`, `definition`
  and `examples[]`. Nineteen domain families, two levels, per [02-taxonomy.md](02-taxonomy.md).
- `schema/*.py` -- Pydantic **2.13.5** models for every entity, with the cross-field validators
  (human-baseline rule, judge-model rule, ID-reuse ledger) that genuinely need imperative code.
  **Python 3.12**, pinned in a lockfile -- not 3.13, because scikit-learn 1.9.1 needs >=3.11 and the
  numba/UMAP stack that the Atlas layout depends on always lags new CPython.
- Generated and committed `schema/generated/*.schema.json` (Draft 2020-12, from
  `model_json_schema()`) and `site/src/types/*.ts` via **`json-schema-to-typescript@16.0.0`**.
  CI fails if regeneration produces a diff. Note that `datamodel-code-generator` emits **Python
  only** and cannot do the TypeScript leg, and `json-schema-to-zod` was archived 2026-06-30 -- the
  obvious Zod path is dead.
- **The four schema additions required before any Epoch ingest**, because retrofitting thousands of
  records is painful: `ResultClaim.artifact_url` (transcript or log), `ResultClaim.provenance_snapshot`,
  `System.training_compute_flop` + `training_compute_estimated` + `training_compute_notes`, and
  `EvalConditions.reasoning_effort` as an enum-plus-free-text (Epoch's observed vocabulary
  `max/xhigh/high/medium/low/minimal/none` is a reasonable starting enum, drawn from 2,402 rows).
- **The quote-enforcement field, specified now because it is what makes the copilot safe.** Every
  AI-drafted field carries a sibling `quote` string. **The validator requires that `quote` be an
  exact substring of the archived source snapshot for that field's source** -- not the live page,
  the snapshot, so the check is reproducible at any commit. A quote that does not match **fails
  validation and the field is set to `null`**. The model cannot assert a value it cannot quote, and
  cannot quote text the snapshot does not contain. Without this the "verbatim source quote" is
  decorative: a model can fabricate a quote exactly as easily as it can fabricate a value.
- **Interoperability field names adopted, not invented.** Take Every Eval Ever's `eval.schema.json`
  names for shared conditions (`generation_args`, `agentic_eval_config.available_tools`, `sandbox`,
  `metric_config`) so a result validated against EEE joins our benchmark record on a stable ID. Take
  Epoch's `random_baseline`, `score_ceiling` and `superseded_by`. Take HuggingFace's leaderboard tag
  namespaces (`test:public|private`, `submission:manual|automatic|semiautomatic`, `judge:auto`,
  `eval:code`) as hints with a `source: hf_space_tag` provenance stamp -- never as ground truth,
  since only **12.8%** of leaderboard Spaces carry `test:*` (128 of a 1,000-Space sample;
  [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3 owns the count and records that an
  earlier "~11%" was a mis-transcription of the same sample) and the tags are author-declared.
- **Croissant-compatible field naming**, so the Phase 2 JSON-LD emission and the Phase 4 extension
  proposal are mechanical rather than interpretive. This costs nothing now and is expensive to
  retrofit. See [15-open-questions.md](15-open-questions.md) A8.
- **`Benchmark.execution.runnable_via` and `Benchmark.execution.inspect_evals_id`**, which
  [13-execution-runners.md](13-execution-runners.md) §3.1 places in Phase 0 and
  [04-data-model.md](04-data-model.md) owns. They are Phase 0 because the Phase 6 suite builder and
  the Phase 7 gate query both read them, and because `inspect_evals_id` falls out of ingest for free
  if the field exists and costs a re-sweep if it does not.
- `bench` CLI: `new`, `validate`, `build` (minimal). Every subcommand any document invokes must be
  declared in [05-repository-and-workflow.md](05-repository-and-workflow.md) §3, which is the CLI's
  only specification -- a command that is not in it is a command nobody builds.
- **Two Phase-0 scripts other documents already depend on**, neither of which is engineering work of
  any size: `scripts/overlap_sample.py`, which measures the overlap band against BenchmarkList and
  Benchmark Radar over a 50-family sample ([01-landscape-and-positioning.md](01-landscape-and-positioning.md)
  §4 -- the most quotable figure in the positioning and currently an analyst prior rather than a
  measurement), and `scripts/epoch_audit.py`, which re-derives the Epoch row decomposition from
  `epochdl/` so the figures in `00` §8.1 are reproducible rather than recorded.
- CI: validation on every PR, blocking on tiers 1--3.
- **Survivability artifacts, on day one:** `LICENSE-DATA` (CC-BY-4.0), `LICENSE-CODE` (MIT) and
  `REUSE.toml` -- three files, not one, because a single `LICENSE` holding two licences is exactly
  the ambiguity the split exists to avoid and `REUSE.toml` is what makes the split machine-checkable
  ([05-repository-and-workflow.md](05-repository-and-workflow.md) §2); plus
  `CITATION.cff`, a reserved Zenodo *concept* DOI (version-independent, so every release inherits
  it), and `SUCCESSION.md` answering "what happens when we stop" in plain words -- **including the
  trigger that invokes it**, specified in [Stopping rules](#stopping-rules-and-re-plans). This is not
  paperwork. It is the difference between Ecosystem Graphs (no licence, unforkable, dead) and an
  asset somebody else can pick up.
- ADRs: `0001-faceted-taxonomy`, `0002-data-as-git`, `0003-pydantic-canonical`,
  `0004-no-universal-score`, `0005-cc-by-and-succession`, and
  **`0006-papers-with-code-licence-posture`** -- the CC-BY-SA-4.0 quarantine decision, made before
  the first ingest rather than discovered at launch. See
  [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md).
- **Ten stress-test entries**, each chosen because it breaks a different assumption.

### The stress-test entry table

| Entry | Domain | What it breaks |
| --- | --- | --- |
| **SWE-bench** (+ Verified / Lite / Multimodal / Multilingual / Pro) | code | Identity and lineage: six live forks under one name. The result carries `agent`, `agent_org`, `reasoning_effort`, `instance_calls`, `cost` and a third-party `checked` flag -- scaffold is part of the number, not context. High contamination exposure. |
| **CASP17** | biology-genetics | `version` (editions, not versions); `leaderboard` (the output is peer-reviewed assessment *papers*, not a table); `metric` (GDT_TS, lDDT, TM-score, DockQ, ICS, IPS -- different per category); and a **separately ranked human-expert category**, so the same method appears twice with different numbers. |
| **RoboArena** | robotics-embodiment | `tasks` (evaluators choose their own), `metric` (double-blind pairwise A/B preference, no absolute score), `maintainer` (a distributed network of labs), `reproducibility` (physical DROID robots in different rooms), `as_of` (a live ranking running through Dec 2026). Forces pairwise/relative results and physical evaluation venues. |
| **WeatherBench 2** | earth-climate | The assumption that a benchmark *has* a ranking. Its authors explicitly say it is a tool to compare approaches on different aspects, not a challenge with one ranking. Also breaks `human_baseline` (the comparator is an operational NWP supercomputer) and `score` (a grid of variable x pressure level x lead time x metric). Forces a lead-time dimension and a **"no aggregate by design"** flag. |
| **Matbench Discovery** | chemistry | `metric` (stability F1 + energy MAE + phonons + kappa_SRME thermal conductivity + MD stability + diatomic PES) and, critically, **compliance tiers that group models by what data they were allowed to train on**. Forces a training-data eligibility concept -- a comparability key on the *training* side, which LLM-shaped schemas have no slot for. |
| **ARC-AGI-3** | general-intelligence | `one_result_per_model`: **two official leaderboards with different legality rules** (unmodified general-purpose API systems vs harness-permitted community entries). Also `environment` (interactive, agent-driven, not a dataset) and `score_range` (frontier models below 1% while humans solve all environments). Forces harness legality into the comparability key. |
| **Virtual Cell Challenge 2026** | biology-genetics | `human_baseline`: the ceiling is **a real biological replicate experiment** and the floor is the cell-context mean. Six complementary metrics, each independently normalised. Zero-shot only -- deliberately no challenge training set. Forces a normalisation anchor that is not "human". |
| **Kaggle Game Arena** | games-planning | `score` (unbounded Elo, all-play-all, 40 games per pair), `stability` (a model's rating moves when a *different* model joins the pool), `comparable_across_time` (ratings are meaningful only within one pool snapshot). Forces rating-pool identity + snapshot date into every stored result, and a UI rule that refuses to compare Elo across snapshots. |
| **ForecastBench / Metaculus FutureEval** | society-econ-law | `result_is_final` and `ground_truth_exists`: questions have no answer at submission and resolve months to years later. Forces `resolution_status: pending\|partial\|resolved` and a distinction between "measured on" and "resolved as of". Also supplies real human baselines at two tiers (public crowd, superforecasters). |
| **PaperBench** | agents-tooluse | `metric` (a hierarchical rubric of ~8,316 leaf nodes aggregated into a tree score), `grader` (an LLM judge is part of the measurement apparatus, so judge model and version must be recorded), `task_count` (20 papers, thousands of scored sub-criteria). The case that proves judge-as-condition. |

**Runners-up, if the ten fit too easily** -- and at least three of these should be tried, because a
schema that survives ten hand-picked cases has survived ten hand-picked cases: CACHE Challenges
(wet-lab ground truth, participants must *buy compounds from Enamine*, multi-year two-phase cycles,
a medicinal-chemistry panel's qualitative commentary, structurally irreproducible by third parties);
tau-squared-bench (`pass^k` -- the fraction of tasks solved in *all* k trials, which averaging
destroys); AgentDojo (utility and targeted-attack-success as two orthogonal axes with no scalar);
AudioSet (distributed as YouTube IDs, so the dataset rots); DCASE 2026 (one name, seven unrelated
tasks, new eval set every year); LifeCLEF (official ranking requires submitting a CEUR-WS working
note -- a publication gate on eligibility); FrontierMath (Epoch reissued a corrected version on
2026-06-12 after finding errors in **42% of problems**, which makes version pinning mandatory);
AILuminate (ordinal letter grades whose meaning is explicitly relative to current state of the art);
BBQ (a pair of bias numbers where zero, not maximum, is optimal).

### Exit criteria

- All ten stress entries validate with **zero errors and zero schema hacks**.
- Headroom returns `null` *gracefully* for WeatherBench 2, Kaggle Game Arena and RoboArena rather
  than erroring or silently producing a number.
- `comparability_key` is computed for all ten and two deliberately-different conditions on the same
  benchmark produce different keys.
- A schema change requires an ADR **and** a migration script; CI rejects a schema diff without both.
- The quote validator rejects a deliberately fabricated quote in a fixture, and sets the field to
  `null` rather than failing the whole record.
- `LICENSE-DATA`, `LICENSE-CODE`, `REUSE.toml`, `CITATION.cff`, `SUCCESSION.md` (with its invocation
  trigger written in) and the reserved Zenodo concept DOI exist in the repo.
- Every version pin in the lockfile was re-verified against its registry this phase, not taken from
  this document.

### The real test of this phase

**If any stress entry required adding an optional escape-hatch field or a free-text blob to fit, the
schema is wrong and should be revised now, not in Phase 3 with 200 entries to migrate.** An
`extra: {}` map or a `notes` field doing structural work is the tell. Epoch's own corpus is the
cautionary example: conditions that should be structured live in a `Notes` column filled on **5.7%
of rows**, containing entries like `"Assuming medium based on GPT-5 being run at medium."` and
`"Couldn't find shot count"`. Those are exactly the unknown-versus-default distinctions our schema
is supposed to make structural. If we end up with our own `Notes` column, we have rebuilt Epoch with
fewer resources.

### Phase risk

**Taxonomy bikeshedding.** Eight facets across nineteen families is a lot of surface to argue about,
and argument feels like progress. Mitigation: closed vocabularies, ADR friction on every term
addition, and a hard rule from [03-taxonomy-build-process.md](03-taxonomy-build-process.md) that a
term is only added when a real benchmark cannot be classified without it.

---

## Phase 1 -- Seed the index, breadth-first

*9--25 weeks.* The longest phase by a wide margin, the one that produces the differentiator, and the
one where the project lives or dies. (175 h / 20 = 8.75 and 495 h / 20 = 24.75, rounded outward; the
8--22 an earlier draft printed here was the superseded 300-entry figure, and it disagreed with this
document's own phase table and serial total.) The width of that range is the whole schedule risk in this plan;
see [Stopping rules](#stopping-rules-and-re-plans) for what to do at each end of it.

### Breadth before depth, deliberately

The instinct is to start with the domains you know best. Resist it. **A schema validated only
against language benchmarks will fail on genetics, and finding that out at entry 200 is expensive.**
The Epoch corpus proves the point quantitatively: **0 of its ~81 benchmarks** touch robotics,
chemistry, biology, medicine, climate, materials or audio. Every field an LLM-only corpus never
needs -- wet-lab ground truth, simulator build version, lead time, training-data eligibility,
resolution status, edition cycles -- is a field you will discover the hard way if you seed from the
language half of the map.

Breadth is also the moat. It is curation labour no leaderboard company wants to do, because it does
not convert into a ranking. CASP/CAMEO, Grand Challenge's 264 medical-imaging challenges, Matbench
Discovery, Open Catalyst, WeatherBench 2, GEO-Bench and the entire robotics cluster appear in **no**
cross-domain catalogue. Robotics is the single largest unindexed field in AI evaluation.

### The 20-entry checkpoint -- the highest-leverage moment in the whole project

1. **First 20 entries, spread across at least 12 domain families.** Two to three days.
2. **Stop. Schema review checkpoint.** What was awkward? What needed a workaround? What did you
   write in a `notes` field that should have been structured? Revise the schema now, while migration
   costs an afternoon rather than a fortnight. Write the ADR.
3. **Measure, and write the numbers into the ADR.** Two numbers, both of which the rest of this
   document depends on:
   - **Median minutes per entry, timed.** Not estimated afterwards -- timed, per entry, with the
     source-reading and archiving included.
   - **The copilot speedup**, measured as ten entries drafted with the F6 copilot against ten
     drafted without, same curator, interleaved to control for learning effects. The plan asserts
     the copilot roughly halves the work; this is the experiment that tells you whether that is
     true.
4. **Re-cut the effort table and the [02-taxonomy.md](02-taxonomy.md) §3 allocation against the
   measured rate before scaling.**
   If the median is 60 minutes or more, go to
   [Stopping rules](#stopping-rules-and-re-plans) rule (a) before writing entry 21.
5. Only then scale, domain family by domain family.

Do not skip step 2 because the first twenty went smoothly. Going smoothly is what a schema that has
only met easy cases feels like.

### Domain reviewer recruitment starts in week 2, not at the exit gate

This is a correction to the earlier draft and it matters more than its size suggests. **Recruiting a
specialist reviewer is a human-relations workstream with a three-month lead time, and discovering
that at the Phase 1 exit gate is fatal to the schedule.** An academic who is interested will still
take six weeks to answer, and the ones worth having are the ones with the least free attention.

- **Start outreach in week 2 of Phase 1**, with two or three entries in their domain already written
  so the ask is "please check these five entries" rather than "please help with my project".
- **Approach conference communities, not individuals cold**: CoRL and RSS for robotics, ISMB and the
  Protein Structure Prediction Center for structural biology, Climate Informatics and the ECMWF/ML
  community for earth-climate, MICCAI and the Grand Challenge organisers for medicine, DCASE and
  ISCA for audio, the Materials Project and Open Catalyst communities for chemistry.
- **Offer named credit in `CITATION.cff` and on every entry they touched.** That is the currency
  academics actually want, and it costs nothing.
- **Budget 8--20 hours for this across the phase** -- it has its own effort row. It is not
  engineering and it does not feel like progress, which is exactly why it gets deferred.
- **Target seven reviewers (one per differentiating family), gate at three.** Seven is what makes
  the Phase 4 Gap Finder assertable across the whole differentiating core; three is what blocks
  the phase. The gap between them is handled honestly rather than by waiting -- see below.

**The honest gate, replacing a contradiction in the earlier draft.** The previous version made
reviewer sign-off a blocking exit criterion *and* told the risk register to proceed without it. Both
cannot be true. The rule is:

> For each domain family, **either** a named reviewer has signed off, **or** every entry in that
> family renders a visible `curation_confidence: unreviewed` badge, the domain is marked unreviewed
> in the coverage map, and the Gap Finder refuses to assert a gap in it. **Shipping unreviewed is
> permitted; shipping unreviewed *silently* is not.**

The phase exits when at least three unfamiliar domains are signed off *and* every unreviewed domain
is correctly badged. An unanswered email now costs a badge, not a schedule slip.

### Publish the taxonomy and the gap analysis before the catalogue

**Add this deliverable to the end of Phase 1. It costs about eight hours and it is the strongest
available hedge against the biggest competitive risk in the plan.**

The problem it solves: BenchmarkList (2,545 entries, verified to already contain Open Catalyst OC22
and GEO-Bench 2) and Benchmark Radar (daily updates, 37 ingestion sources) are both actively adding
entries during the eight to eighteen months in which this project is invisible. The moat is non-language
depth, and nothing stops a two-person indie team from adding a robotics tab in a fortnight. A plan
whose first public act is eight months away has no answer to that.

So make the first public act happen at month three:

- **Release `taxonomy/` under CC-BY with its own Zenodo DOI** at the end of Phase 1 -- the eight
  facet vocabularies, nineteen domain families, every term with a definition and examples.
- **Post a short preprint of the domain x capability gap matrix** as it stands at the seed corpus
  (320 targeted), with
  the four already-confirmed gaps (phylogenetics, education/tutoring, AI psychometrics,
  retrosynthesis) as its worked examples, and with our own curation confidence shown alongside
  density so the gaps are not overclaimed.

The taxonomy is the part that takes reading, it is the part a competitor cannot copy without
attribution, and publishing it first converts eight months of silence into eight months of being
cited. Under CC-BY, being copied is adoption, not loss -- the argument is already made in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10, and this is the step that
cashes it.

### Per-domain-family curation allocation

**The allocation lives in [02-taxonomy.md](02-taxonomy.md) §3 and is not restated here** -- one table,
generated from `taxonomy/domains.yaml`, because two copies of nineteen numbers is exactly how this
plan came to carry three different seed totals. What this document gates on: **320 entries targeted,
290 as the launch gate; 144 across the seven Core families, 130 as the gate; no family below 12, no
Core family below 18.** The **Core seven** are robotics-embodiment, biology-genetics,
chemistry-materials, medicine-health, physics, earth-climate and audio-speech -- every other gate in
this document that says "the seven" means exactly these, and the non-duplication doctrine in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10 is what sets each family's
posture.

**Not estimated, and say so when quoting the total.** The domain recon's count table covers
**thirteen** domains totalling ~300 Tier-1 families and does **not** size code, language,
mathematics, reasoning-general, multimodal or engineering-design at all. Those six rows (78 entries)
are **our own estimates and are weaker than the other thirteen**: the 320 figure is *242 of the
recon's 300 estimated Tier-1 families across thirteen domains (81%), plus 78 entries across six
domains nobody has sized.* Sizing those six is a Phase 0 task, not a Phase 5 one, because it is the
only part of the allocation with no external grounding.

**Floor rule:** three numbers with three jobs -- **12 is the hard launch gate**, **18 is the
Core-family launch gate**, and **15 is the v1.x credibility target** every family reaches eventually.
A family that cannot reach its floor ships muted (`coverage_status: under-surveyed`, badged entries,
Gap Finder silent on that row); muting is not available to the Core seven. Stated in full in
[02-taxonomy.md](02-taxonomy.md) §3. The reason the Core floor is 18 rather than 12: a specialist
scanning their own field with eighteen entries in it says "yes, you got my field right"; with six,
they close the tab.

**Reconciling the "~120" figure.** [01-landscape-and-positioning.md](01-landscape-and-positioning.md)
puts the differentiating core at "~120 Tier-1 families". That figure counts **five** domains
(robotics, chemistry-materials, biology, climate, physics = 25+25+30+20+20 = 120 estimated to
exist); under the canonical allocation those same five are **106 targeted**. This document's Core set
adds **medicine-health and audio-speech**, giving seven families, 163 estimated to exist and **144
targeted**. None of these figures is in conflict with the others; they count different sets, and
every one of them should say which set it means.

**Counting convention, decided now because it is the single highest-leverage schema decision:** the
seed targets count **families** (BraTS, DCASE, CASP, LifeCLEF, NTIRE, Matbench Discovery), not
children (editions, tasks, tracks, splits). Counting children instead multiplies by roughly 3--6x
and again by the number of editions, and makes every number in this plan meaningless. The
family/child relation is modelled explicitly in [04-data-model.md](04-data-model.md).

### Deliverables

- 320 benchmark entries, all 19 domain families non-empty, floor rule respected, Core families at 18+.
- Every entry `primary-source-verified` or better; **zero `ai-drafted-unverified` on `main`**.
- Every entry has at least one archived source (Wayback SPN2 via
  `if_not_archived_within`, which is the idempotency key; CDX for existence checks, because the
  Availability API returned 429 on a single cold request).
- The F6 curation copilot running as an internal script: URL in, YAML draft out, a `quote` attached
  to every field and validated as an exact substring of the archived snapshot, `confidence:
  high|low|absent`, and `null` wherever no quote supports a value. Fields are never guessed.
- **`taxonomy/` released under CC-BY with a DOI, plus the gap-matrix preprint** -- the first public
  artifact of the project, shipped months before the site.
- Reviewer outreach begun in week 2; a named reviewer credited for at least three unfamiliar
  domains; every unreviewed domain badged.
- The 20-entry checkpoint ADR, containing the measured per-entry median and the measured copilot
  speedup.

### Exit criteria

- **>=290 benchmarks** (320 targeted); 19 of 19 domain families populated; none below 12 unless
  muted under the floor rule.
- **>=130 entries across the seven Core families** -- *robotics-embodiment, biology-genetics,
  chemistry-materials, medicine-health, physics, earth-climate, audio-speech* -- against a target of
  144. This is the differentiating core, and it is a *tractable* number.
- Zero validation errors; quality warnings triaged rather than suppressed.
- **Either** a named specialist reviewer has signed off on each of three unfamiliar domains, **or**
  every unsigned domain carries `curation_confidence: unreviewed` on every entry and in the coverage
  map. Both are acceptable exits; silence is not.
- **The schema has not changed in the last 40 entries.** If it is still churning at entry 260,
  Phase 0 did not finish and the checkpoint was not honest.
- `taxonomy/` is published with a resolving DOI and the gap-matrix preprint is posted.

### Phase risk

**Curation burden exceeds capacity, silently.** The failure is not that curation stops; it is that
it slows to two entries a week while the plan still says three hundred and twenty. Mitigation: track
entries per week publicly in the repo, pull the Tier-2 lighter-stub lever on the stated trigger
([Stopping rules](#stopping-rules-and-re-plans) rule (c)) rather than on a feeling, and re-cut the
allocation rather than the quality bar. A 270-entry index where every entry is right beats a
600-entry index where a tenth are wrong, because one wrong entry in a reader's own field destroys
their trust in the other 599.

---

## Phase 2 -- Public static site with the Atlas and detail pages

*4--8 weeks.* At two people this runs alongside Phase 1 once the catalogue passes 100 entries. At one
person it does not start until Phase 1 exits -- see [Critical path](#critical-path).

### Deliverables

- Build pipeline: YAML -> **two unsharded JSON artifacts** -- `facets.json` (~36 KB gzipped: id,
  name, domains, capabilities, year, lifecycle) loaded with the filter UI, and `corpus.json`
  (2.76 MB raw / ~0.52 MB brotli, upper bound) loaded lazily. Sharding was measured and rejected;
  see [08-infrastructure-and-build.md](08-infrastructure-and-build.md). SQLite is generated at build
  time for our own analytics and as a citable release artifact, and never ships to the browser.
  DuckDB-WASM's engine alone is 35.66 MB, roughly 70x the dataset.
- Astro **7.3.3** on Node >=22.12, with `compressHTML` set **explicitly** -- it now defaults to
  `'jsx'` and will eat the whitespace between inline facet chips.
- Generated TypeScript types consumed by the site; Astro collection `schema` left undefined so there
  is exactly one schema, one validator, one source of truth.
- Benchmark detail pages: static, readable **without JavaScript**, permanent URLs.
- Faceted browse and filter; full-text search via **Pagefind**, using `addCustomRecord()` to index
  the YAML directly rather than only the rendered HTML.
- **The design system implemented, not just designed.** [09-design-system.md](09-design-system.md)
  is the one document the earlier draft never costed, and it is not free: `tokens.yaml` as the single
  source of colour, the `check_contrast.py` CI gate over every declared ink-on-surface pair in both
  themes, the no-`px`-font-sizes rule, the redundant-encoding rule (colour is never the sole carrier
  of meaning), the eight archetype pages the Axe/Pa11y job runs against, and the component inventory
  the five view templates are built from. **15--30 hours**, and skipping it means retrofitting
  accessibility after the views exist, which costs more.
- **V1 Atlas** on **sigma.js 3.0.3** (cosmos.gl 3.4.1 as fallback; it has no label API at all, which
  disqualifies it as primary), with a precomputed layout.
- **Atlas layout stability**, specified concretely below. This is the hardest unsolved engineering
  problem in the plan and it gets its own effort row (**5--15 h, high variance**) rather than being
  buried in the site line.
- **`croissant.jsonld` emitted per benchmark** from the build, as a namespaced unofficial extension.
  Mechanical, because Phase 0 named the fields for it. The *proposal* to MLCommons is Phase 4.
- **The non-PR contribution path**, modelled on UK AISI's `inspect_evals` `/register/` (launched
  2026-05-08): GitHub issue template -> validation bot -> auto-generated PR -> human review. The PR
  path stays for power users. Review rules, labels and branch protection in
  [05-repository-and-workflow.md](05-repository-and-workflow.md).
- Published taxonomy definitions and methodology pages.
- Deploy on push to **Cloudflare Workers with static assets** (not Pages, not GitHub Pages), built
  in GitHub Actions. Static asset requests are unbilled; a Hacker News front page cannot generate an
  invoice. PR previews on.

### Atlas layout stability, specified

"Frozen positions" is not a mechanism. This is:

1. **A frozen SVD basis.** The facet-vector matrix is projected through an SVD basis computed once
   and committed. New entries project into the existing basis; the basis is not recomputed per build.
2. **A warm start.** `umap.UMAP(init=<ndarray>)` seeded with the previous build's coordinates for
   every entry that existed in it, and with the SVD projection for new entries.
3. **Procrustes alignment** between the new layout and the previous one before anything is written,
   so a global rotation or reflection is not mistaken for drift.
4. **The drift gate.** [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.3 owns the
   atlas build and therefore the gate's statistic and threshold: after alignment, **CI fails when the
   median per-point displacement exceeds 2% of the bounding-box diagonal**, which is the form
   [05-repository-and-workflow.md](05-repository-and-workflow.md) §9 and
   [10-visualization.md](10-visualization.md) also use. This document previously stated a different
   statistic in different units (mean > 0.02, p95 > 0.05, in bare normalised coordinates); a
   mean-plus-p95 pair is arguably the better refinement, but if it is adopted it has to be adopted in
   `08` §5.3 and followed by `05` and `10`, not asserted here alone.
5. **CI is the sole authority that writes `atlas.json`.** UMAP reproducibility is guaranteed across
   runs but **not across machines**, so a local build must never commit it.

**And -- the part the earlier draft was missing -- what happens when the gate fires for a good
reason.** Adding fifty robotics entries *will* move the layout; that is the entire point of adding
them. Without an escape, growing the catalogue breaks the build.

> **Layout epochs.** `atlas.json` carries `layout_epoch: N` and the reference layout is the one from
> the current epoch. The drift gate fails on unexplained drift. A commit that also touches
> `atlas_epoch.yaml`, adding a new epoch entry with a `reason` string and the triggering PR number,
> **bumps the epoch and re-bases the reference** -- the gate then passes and the next build measures
> against the new positions. Only a human can write `atlas_epoch.yaml`; the bot cannot. The Atlas
> page renders *"Layout re-based on `<date>` -- `<reason>`"* whenever the current epoch is less than
> ninety days old, because users learn positions and deserve to be told when they changed.

Two consequences worth stating: a re-base is a normal, expected event a few times a year, not an
incident; and an epoch bump with a reason like *"drift"* is a review failure, because the reason
field exists to make re-baselining visible rather than routine.

**Three documents have to carry this for the Phase 2 exit criterion below to be reachable, and this
is the only place the mechanism is currently specified.** The epoch ledger replaces the bare
`atlas_layout_version` integer that [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
§5.3.1 and [10-visualization.md](10-visualization.md) currently describe — it does the same job and
additionally carries a reason string and a triggering PR number, which is the whole point. So: `08`
§4.2 adds `layout_epoch` to `atlas.json`'s field list and `08` §5.3.1 replaces the version bump with
the ledger; `10` follows; and [05-repository-and-workflow.md](05-repository-and-workflow.md) §2 adds
`atlas_epoch.yaml` beside `atlas/basis_v1.npz`. Until those land, this is a v1 exit criterion that
depends on a file no other document defines, and the correct resolution is to add the file rather
than to drop the criterion.

### Exit criteria

These adopt [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §8's budgets and
enforcement verbatim, replacing the earlier draft's weaker wording. "Current scale" at Phase 2 is
~320 nodes, which sigma.js renders at 60fps on anything -- a criterion that tests nothing is worse
than no criterion, because it reads as tested.

- **Landing page interactive in < 2.0 s on a mid-tier mobile over simulated 4G.** Lighthouse CI on
  every PR against a budget file; **fails the job**.
- **JS on any detail page = 0 KB**; **Atlas route <= 120 KB gzipped**; **detail page total weight
  <= 120 KB including fonts**. Enforced by `size-limit` per route group; fails the job.
- **Atlas holds 60 fps sustained while panning and while a facet filter is applied, at 1,500+
  nodes** -- measured by a nightly Playwright trace against a **fixed synthetic 2,000-node corpus**,
  not against the live catalogue.
- Client-side full-text search returns a first result in **< 100 ms**, measured in the same nightly
  run.
- Every benchmark has a stable citable URL that renders with JavaScript disabled.
- **Atlas clustering produces visually obvious domain structure.** If it looks like a hairball, fix
  the facet vectors, not the styling.
- The CI drift gate has failed at least once on a deliberate perturbation, and an `atlas_epoch.yaml`
  bump has cleared it once, proving both halves work.
- **Accessibility:** Axe/Pa11y CI pass with zero WCAG 2.2 AA violations across the eight archetype
  pages; the Atlas and the facet UI fully keyboard-operable including the non-drag selection path
  (SC 2.5.7); `check_contrast.py` green in both themes. Per
  [09-design-system.md](09-design-system.md) §8.
- **An outsider has successfully added a benchmark through the issue form without touching git.**
  This is a tested exit criterion, not an aspiration -- see the risk register.

### Phase risk

**Contribution friction converting the project into a closed website.** This is not hypothetical.
`JonathanChavezTamales/llm-leaderboard` was a JSON-in-git, schema-validated community benchmark
catalogue with 356 stars; it deprecated itself and became llm-stats.com, a closed site with no repo
and no licence. The stated reason was contribution friction -- PRs were too slow compared with
per-model discussion threads on a website. It is the most instructive failure in the whole landscape,
and the issue-form path is the direct response to it.

---

## Phase 3 -- Result claims, provenance, and the Epoch ingestion adapter

*7--13 weeks.* Longer than the earlier draft's 5--7 because the non-LLM claims are now funded rather
than assumed. This is the phase that makes the project distinctive, with the highest data-entry cost
per unit of visible output -- which makes it the easiest to under-resource, and the earlier draft
under-resourced it.

### The Epoch decision (settled)

**Ingest in bulk, badge honestly, segregate, and hand-curate a small adversarially-chosen set.** The
local `epochdl/` snapshot is **80 or 81 benchmarks** *(the count is reported as 80 in one recon
report and 81 in another; the discrepancy is unresolved, immaterial to the plan, and must be checked
at ingest time -- carried forward from [00-vision-and-scope.md](00-vision-and-scope.md) §8)*, 1,063
model rows (~550 distinct `model_group`) and 6,598 result rows under CC-BY-4.0. One line summarises
why this is the right split: *Epoch gives us the numbers for free; it does not give us the
conditions, the facets, the provenance grade, or any domain outside LLMs -- which is precisely the
list of things this project exists to provide.*

All rows land in `data/claims/_ingested/epoch/`, each carrying `provenance: epoch-2026-09-16`, an
honestly computed `condition_completeness` (expect a mean around **0.10**),
`curation.verification_status: machine-ingested`, and a verification level assigned **by rule**:

| Rule | Condition | Assigned | Rows |
| --- | --- | --- | --- |
| `epoch-run-public-log` | Epoch-run file, Inspect `.eval` log on the `-public` bucket | `independent-reproduction` | 828 |
| `epoch-run-private-log` | Epoch-run file, log URL on the `-private` bucket | `maintainer-verified` | 459 |
| `epoch-run-no-log` | Epoch-run file, log URL blank | `self-reported` | **263** |
| `external-scrape` | One of the 66 external/scraped files | `self-reported` | 5,048 |
| `unmatched` (default) | Matches no rule above | `self-reported`, `verification_rule: unmatched` | 0 expected |
| | | **Total** | **6,598** |

**The four rules sum to 6,598 exactly.** The earlier draft listed only three and quietly lost the
263 Epoch-run rows with no log -- a rule that drops 4% of a bulk ingest is exactly the quiet failure
this section warns about. The `unmatched` default exists anyway, because a rule set that cannot
express "I did not recognise this" will express it as a wrong answer instead: **any row matching no
rule is assigned `self-reported` with `verification_rule: unmatched`, and the count of unmatched
rows is published on the trust page.** If that count is ever non-zero, the adapter has met a file
shape it was not built for and somebody needs to look.

Two further settled points:

- Default sort and default filter are `verification` and `condition_completeness`. Comparison views
  hide machine-ingested claims below a completeness threshold; browse views still show them. The
  bulk data provides **coverage** -- the great searchable collection the user asked for -- without
  polluting **comparison**, which is where credibility lives.
- Benchmarks become **stubs only**: ~81 files with id, name, aliases, release date, homepage,
  `verification_status: unreviewed` and every facet `null`. They are not published to the site until
  a human assigns domain facets, because an unfaceted benchmark is invisible to the coverage map
  anyway. **Benchmark ID allocation stays manual** -- automated slugification produces wrong IDs, and
  our IDs are permanent and never reused. `FrontierMath-Tier-4-2025-07-01-Private` is one string
  encoding benchmark, tier, snapshot date and access mode; `MATH level 5` is a subset of MATH;
  `ARC AI2` and `ARC-AGI` are unrelated benchmarks sharing a prefix.

### Deliverables

**A. The Epoch adapter.**

- Conditional GET on `https://epoch.ai/data/benchmark_data.zip` using the **ETag** (there is no
  `Last-Modified` header), sha256 of the archive recorded in the `IngestBatch` record at
  `data/_ingest/batches/<id>.yaml` ([04-data-model.md](04-data-model.md) §9 owns the entity and its
  path; three different spellings of it were in circulation and this is the one that wins) with
  retrieval date, verbatim citation string and per-file row counts. Roughly **80 small per-file column-mapping YAML stanzas** -- 62 distinct
  header signatures across 80 files means there is no generic parser, and pretending otherwise is
  how the scale traps bite.
- **The scale traps, handled explicitly:** `benchmark_metadata.scale` covers only 59 of ~81
  benchmarks. `vending_bench_2` `Score` is **dollars** (11,181.87). `metr_time_horizons`
  `Time horizon` is **minutes**. `webdev_arena` is an **Elo**. `lech_mazur_writing` is 0--10.
  Defaulting the missing files to `scale: 1.0` silently produces nonsense.
- **Decision on the 21 orphan files: hand-map all 21, do not skip any.** Each needs a `score_column`
  and a `scale` read off the benchmark's own leaderboard -- roughly 15--30 minutes each, so
  **5--10 hours total**. It is the difference between 59 and ~80 benchmarks of Epoch coverage, i.e.
  26% of the ingest, and it is cheap relative to what it buys. Skipping them would also mean the
  coverage claim on the trust page has a 26% hole in it that is invisible from the outside, which is
  the kind of quiet inaccuracy this project exists to oppose.
- Systems and organizations populated: ~550 systems from `model_group`, versions from
  `model_version`, ~70 organizations after splitting comma-joined values
  (`Z.ai (Zhipu AI),Tsinghua University`). `training_compute_flop` carried with
  `estimated: true` wherever the notes say "imputed" -- note that `"Training compute imputed to be
  1.58e25 FLOP from benchmark scores"` is **circular for our purposes** and must never be used as an
  independent covariate.
- Wayback capture of every ingested `Source link` -- 74 distinct targets, many bare leaderboard URLs
  where rot is guaranteed.

**B. 50--80 hand-curated LLM claims, chosen adversarially rather than representatively.**

1. The `arc_agi` `claude-opus-4-6_120K` cluster at five reasoning efforts (0.94 / 0.94 / 0.93 /
   0.92 / 0.86), fully specified. Epoch's primary key cannot distinguish these five claims; the
   only discriminator is a human-readable label, and two of them are the same run under two
   spellings of the same source. **This one cluster demonstrates the entire thesis.**
2. The `falcon-7b` MMLU six-way conflict -- 0.35 / 0.262 / 0.262 / 0.2603 / 0.269 / 0.239, a **34%
   relative spread** on the same model and benchmark at the same nominal shot count, from four
   different vendors' technical reports -- with all six sources archived and none adjudicated.
3. SWE-bench Verified across three or four different scaffolds, using Terminal-Bench's clean
   `Agent Org` / `Model Org` split as the model for `built_on`.
4. Ten to fifteen claims on the science-adjacent bridge benchmarks (CritPt, Surface Evolver Bench,
   CadEval, SciCode, GeoBench) that connect to the non-LLM half of the map. **These are still
   LLM-run and do not count toward the non-LLM target below.**

Budget these at **~45--55 minutes each**: the sources are online, indexed and written in a vocabulary
we already speak.

**C. 60--80 non-LLM result claims -- a deliverable of equal weight to the Epoch adapter.**

This is the part the earlier draft required at the gate and funded nowhere. **These sixty claims
*are* differentiator 1** -- the part no competitor has and the part that makes the non-language
breadth mean something rather than being a list of names.

Target roughly ten per Core family, curated from the leaderboard or assessment paper of record:

| Family | Source of record | ~Claims | What makes it expensive |
| --- | --- | --- | --- |
| chemistry / materials | Matbench Discovery rolling leaderboard | 10 | Six metrics per entry plus the **compliance tier** (what the model was allowed to train on) |
| chemistry / catalysis | Open Catalyst EvalAI leaderboards (OC20/OC22/OCx24) | 8 | Hidden test splits; OCx24's ground truth is wet-lab |
| biology-genetics | CASP assessment papers + CAMEO rolling | 10 | Results are **papers, not tables**; per-category metrics; human-expert vs server categories ranked separately |
| earth-climate | WeatherBench 2 scorecards | 8 | A grid of variable x pressure level x lead time x metric; no aggregate by design |
| robotics-embodiment | RoboArena live ranking + the per-benchmark cluster | 12 | Pairwise preference, no absolute score; simulator build, embodiment and episode protocol all material |
| medicine-health | Grand Challenge leaderboards (subset) | 8 | 264 challenges; data-access gating; per-challenge metric definitions |
| audio-speech | DCASE annual results pages + Open ASR Leaderboard | 8 | Seven unrelated tasks under one name, new eval set each year |
| physics | The Well / PDEBench / FAIR Universe | 6 | Metrics are confidence-interval coverage or PDE error norms, not accuracy |

**Budget these at 60--90 minutes each, not 45.** A robotics result requires decoding the simulator
build, the embodiment, the episode protocol and the evaluator pool before the number means anything;
a Matbench Discovery row requires reading the compliance tier definition. These are the expensive
claims and they carry their own effort row. Pretending they cost the same as an MMLU row is how this
gate silently goes unmet.

**D. Headroom and saturation, arriving with the claims.**

Headroom needs a sourced baseline, a sourced ceiling and a current best claim, so it arrives here
rather than in Phase 4: headroom computation using Epoch's `random_baseline` and `score_ceiling`
where available (21 benchmarks have a non-zero chance baseline, a genuinely useful and rarely
published field), **null-reason reporting** on every benchmark where headroom is undefined, and
saturation bands. Formulas in [12-analytics-and-trends.md](12-analytics-and-trends.md).

**E. The comparison surface.**

`comparability_key` computation in the build; **V5 Comparison Workbench** with field-level
apples-to-oranges diffs; provenance drill-down on every number; verification badges everywhere; a
`/corrections` page.

### Exit criteria, and a restated target

The archived plan's target was "500 result claims". **That is the wrong metric once Epoch is
ingested**, because a single adapter run clears it 13x over. Claim count is free; conditions are
not. And the earlier revision's arithmetic did not close: 50--80 LLM claims plus 60 non-LLM is
110--140 against a stated gate of 150, with the segregated Epoch rows unable to make up the
difference at a mean completeness of 0.10. Restate it so the parts sum to the whole:

- Hand-curated claims planned: **50--80 LLM + 60--80 non-LLM = 110--160.**
- **Gate: >=130 claims at `condition_completeness` >= 0.6**, each with a named source and an archived
  URL, **of which >=60 are from non-LLM domains**.
- Full Epoch bulk ingest present, segregated, badged, with mean `condition_completeness` published
  **whatever it turns out to be**. Expect roughly 0.10. Reporting that honestly is a finding, not a
  failure -- quantifying the field's reporting opacity may be one of this project's more useful
  outputs.
- **The four verification rules account for all 6,598 rows, and the `unmatched` count is published.**
- Every claim has exactly one source and one conditions record.
- Conflicting claims render side by side without the index adjudicating.
- Assembling a cross-condition comparison produces a field-level diff warning rather than a ranking.
- Headroom is `null` **with a stated reason** on every benchmark where it is undefined, and the
  reason distribution is published.
- **No automated dedupe has run.** 843 rows share a `Model version` with another row in the same
  file; some are genuine conflicting claims (which we want), some are the same run listed twice
  under two spellings of a source, some are different reasoning efforts collapsed onto one key. Emit
  every row as a separate claim and surface near-duplicates in a quality dashboard for human
  resolution.

### Phase risk

**Ingestion identity resolution failing quietly.** Two counts appear in the Epoch recon and they
measure different populations, so both are correct: **927** distinct `Model version` strings appear
in the 80 benchmark CSVs, and all 927 join to `model_metadata.csv` at 100%; **1,048** distinct
`model_version` keys exist in `model_metadata.csv` itself, which is the larger registry including
versions no benchmark row references. The crosswalk we have to maintain is sized by the registry,
not by the join: **~550 `model_group` entities and ~1,048 version strings.**

The strings themselves are the problem: `accounts/fireworks/models/glm-4p6`,
`chutes/DeepSeek-R1-0528`, `amazon.nova-pro-v1:0`, `gpt-6-astra_max` mix model identity, hosting
provider and reasoning effort into one token. Mapping them to our System + SystemVersion +
EvalConditions triple needs a hand-maintained crosswalk. **This is the single largest manual cost in
the ingest** and the place where a silent failure produces duplicates nobody notices for months.

---

## Phase 4 -- Coverage, gaps, ecosystem view, release feed -> public v1

*3--5 weeks.*

### Deliverables

- Derived pipeline, continued from Phase 3: coverage density, curation confidence, gap scores,
  velocity, ecosystem statistics. Formulas in
  [12-analytics-and-trends.md](12-analytics-and-trends.md).
- **V2 Coverage Map**, **V3 Saturation Wall**, **V4 Frontier Timeline**, **V7 Gap Finder**,
  **V8 Release Feed** with RSS, per [10-visualization.md](10-visualization.md).
- Charts on **ECharts 6.1.0** (MatrixComponent, BrushComponent, AriaComponent, tree-shaken to
  ~80--100 KB) plus hand-rolled build-time SVG for the sparkline small-multiples. Observable Plot is
  rejected: no npm release since 2025-02-14, 349 open issues, and its pointer transform breaks SVG
  serialisation. Every chart ships with its data table as the accessible representation, per
  [09-design-system.md](09-design-system.md) §8.4 (with the component contract in `09` §6.12) -- the
  table is not a fallback, it is the canonical form.
- Ecosystem analysis using OpenAlex institutions and ROR IDs -- **but never OpenAlex citation counts
  as a headline number**. Record `W4387561453`: correct SWE-bench DOI, correct authors, correct date,
  **wrong title** and a citation count off by roughly two orders of magnitude. Any figure sourced
  from a single aggregator renders with a visible "unverified, single source" marker.
- Trust metrics published as a first-class page: verification mix, condition completeness
  distribution, contamination exposure, per-entry `last_verified`, and the `unmatched` ingest count.
- **The `croissant-benchmark` extension, proposed properly.** Not a checkbox. Concretely:
  1. A **namespaced JSON-LD context** (`https://<our-domain>/ns/croissant-benchmark/v1`) defining the
     terms a benchmark adds to a dataset: tasks, metrics with ranges and polarity, splits, evaluation
     protocol, evaluation conditions, baselines and ceilings, lineage and supersession.
  2. A **field-level mapping** from our `Benchmark` and `EvalConditions` entities onto it, committed
     as `croissant/mapping.yaml` so it is testable rather than prose.
  3. **A worked example for three entries from three domains** -- one language, one robotics, one
     chemistry -- because a standard demonstrated only on the easy case is not a standard.
  4. **A submitted issue on the MLCommons Croissant repository** proposing it as an extension, with
     the three examples attached and the mapping linked.
  5. **Never a modified copy of the Croissant spec**, which is CC BY-ND. We publish in our own
     namespace and link to theirs. This constraint is non-negotiable and is the one way this
     deliverable could create a real legal problem.
  Budget **10--20 hours**. See [15-open-questions.md](15-open-questions.md) A8, which settled the
  timing as "build the mapping early, propose after v1" -- this is the propose step.
- **Zenodo release DOI minted** against the reserved concept DOI; machine-generated `/attributions`
  page built from the `sources` entity so it cannot drift from what was actually ingested.
- Launch: methodology docs, contribution guide, citation format, `SUCCESSION.md` linked from the
  footer.

### The Gap Finder ships restricted, not ungated

[12-analytics-and-trends.md](12-analytics-and-trends.md) §13 gates the Gap Finder on
"domain-reviewer sign-off on at least half the domain families" -- nine domains -- because
"publishing gaps before expert review publishes our blind spots as findings." That is correct
reasoning. Phase 1 gates at three reviewers and targets seven. Nine at v1 is not reachable without
making the schedule hostage to other people's inboxes, and waiting is not the only option.

**Decision: ship the Gap Finder at v1, restricted to reviewed domains.**

- A domain with a named reviewer's sign-off renders gap scores and appears in the gap matrix as an
  assertion.
- A domain without one renders **"insufficient curation confidence to assert a gap"** in every cell,
  greyed, with a link to the reviewer-recruitment page. The cell is visibly *unknown*, not visibly
  *empty*. This distinction is the whole difference between an honest artifact and a misleading one.
- The Gap Finder's header states how many of nineteen domains are review-backed, as a fraction, on
  every view.

This satisfies `12`'s actual concern -- never publish an unreviewed blind spot as a finding -- while
letting the feature ship. It also creates the right incentive: an unreviewed domain is visibly
degraded on the site, which is a better recruitment argument than an email.

**Reconciling the two phasing tables.** `12` §13 lists headroom at "Phase 2" and coverage density at
"Phase 3"; this document ships headroom in Phase 3 and coverage in Phase 4. **Read `12`'s column as
data-readiness tiers -- the order in which metrics become honest -- and this table as canonical for
scheduling.** The orderings agree; only the numbering differs, by one. *(Action for whoever maintains
`12`: add that sentence under its table, or renumber its column to match.)*

### Exit criteria

- Headroom computed for >=60% of benchmarks with established baselines; `null` handled **visibly**
  and with a stated reason everywhere else, never silently.
- The coverage map shows **curation confidence alongside density**, so our own gaps cannot be
  misread as field gaps.
- **The Gap Finder surfaces at least one gap the maintainers did not already know about**, within a
  review-backed domain. This is the genuine success test for the whole project. Four gaps are
  already confirmed and publishable on day one: phylogenetics has no standing benchmark; education
  and tutoring have no public leaderboard (only learning-gain RCTs); human-comparison psychometric
  batteries for AI have no canonical benchmark; and retrosynthesis has a canonical *dataset*
  (USPTO-50k) but **no canonical leaderboard**, which is why 2026 papers report mutually inconsistent
  top-1 numbers -- RxnNano 75.1% and RETROSPECT 55.0% on the same 5,007-reaction test set.
- Every unreviewed domain renders "insufficient curation confidence to assert a gap" rather than an
  empty cell.
- A researcher unfamiliar with a domain can orient in it in under five minutes.
- The DOI resolves and the CC-BY YAML at that commit hash is downloadable as a single archive.
- The Croissant extension issue is filed on the MLCommons repository and the three worked examples
  validate against our own context.

### Phase risk

**The Atlas is beautiful and useless.** Explicit exit criterion on clustering legibility in Phase 2,
tested with someone unfamiliar with the field *before* any styling polish. Related and worse: a gap
matrix that shows our curation shape and is read as the field's shape. Every empty cell must say
which it is -- which is now a hard exit criterion rather than an intention.

---

## Phase 5 -- Ingestion at scale and freshness automation

*5--8 weeks.* At a few hundred entries manual maintenance stops scaling. The failure mode is silent:
entries do not disappear, they quietly become wrong. Ecosystem Graphs is still cited as a data source
by 2025--26 research while twenty months stale, so stale curation actively propagates errors into
the literature.

### Deliverables

- **Scrapers run as GitHub Actions cron in the data repo itself.** Cloudflare Workers Free gives
  **10 ms CPU per cron trigger** *(unverified -- confirm before relying on this; it is the figure
  that decides the hosting split for scraping)*, which cannot parse a 3.9 MB `runs.json`; a VPS is a
  machine a two-person team now has to patch. The runner already has `git`, a token and PR rights,
  and the scraper lives next to the YAML it writes. Full workflow split, crons and state design in
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md); never schedule on the hour,
  because scheduled events are dropped under load.
- Adapter build order, by licence cleanliness x transport stability x differentiator hit:
  **HuggingFace Hub** (1,019 leaderboard Spaces and the `test:`/`submission:`/`judge:`/`eval:` tag
  taxonomy, 47 `benchmark:official` datasets, Croissant JSON-LD per dataset);
  **GitHub metadata + a `git clone --depth 1` of `EleutherAI/lm-evaluation-harness`** (227 task
  directories of YAML with `num_fewshot`, `output_type`, `metric_list` -- arguably the best
  structured evaluation-condition data in existence, MIT, one clone) **and
  `embeddings-benchmark/results`** (CC0);
  **arXiv** (OAI-PMH `set=cs` daily delta, then LLM triage). Expect **~60% precision and ~70% recall
  from keyword heuristics alone** *(unverified -- these are the recon's estimates from a sample, not
  a measured evaluation; measure them on our own labelled set before sizing the triage budget)*,
  rising to ~85--90% precision after an LLM classifier with a strict "does this paper *release* an
  evaluation artifact, or merely use one?" rubric, at **~15--95 LLM calls a day** *(unverified --
  derived from the same estimate)*.
- Second wave: HELM's public GCS bucket (26 suites including `robo-reward-bench`, `medhelm`,
  `finance`, `audio`, `vhelm`; `run_specs.json` maps `max_train_instances` -> shots,
  `chain_of_thought_prefix` -> CoT, `model_deployment` -> which provider served it, straight into
  the comparability key -- **but the bucket's data licence is unverified; confirm with CRFM in
  writing before redistributing anything beyond derived structured facts**); LMArena's
  `lmarena-ai/leaderboard-dataset` (CC-BY-4.0 parquet); SWE-bench's inline `<script
  id="leaderboard-data">` JSON (323 claims with agent, reasoning effort, cost and a `checked` flag);
  **Grand Challenge's API (264 medical-imaging challenges with publication links -- the cheapest
  possible route to non-LLM breadth)**; OpenRouter and LiteLLM for the System entity.
- **Papers with Code archive, under quarantine.** 9,327 benchmarks in the largest cold-start corpus
  available, on the HuggingFace `pwc-archive` org, **CC-BY-SA-4.0 and therefore viral**. It goes into
  a segregated tree with every field tagged `provenance: pwc-archive` and is re-derived from primary
  sources before promotion into the CC-BY core. The ADR for this was written in Phase 0.
- **Liveness and deprecation signalling**: `maintenance_status` driven by observable repo, dataset
  and leaderboard signals. One study found **137 of 195** safety benchmarks had stale GitHub repos
  and 96 of 195 stale HF datasets; BetterBench found **17 of 24** had no working reproduction
  scripts. No catalogue the landscape reconnaissance examined marks benchmarks as dead
  ([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1 states exactly how far that
  claim is supported and what one counterexample would do to it). We will.
- Draft PRs, never auto-merge, one PR per source per run with a rendered before/after diff table in
  the body. The single exception: pure adoption counters (`github_stars`, `hf_downloads`) auto-merge
  into a `metrics/` tree that is **not** part of the citable CC-BY core.
- Staleness dashboard, prioritised re-verification queue, link-rot automation, per-release
  diff changelog, and a weekly canary issue that fails loudly when a cron silently stops firing.

### Exit criteria

- >=50% of new claims originate from ingestion drafts with human approval.
- No entry on `main` unverified for over 12 months without being **visibly** flagged on its page.
- Zero dead unarchived source links.
- A deliberately broken adapter (rename the SWE-bench script tag in a fixture) **hard-fails and opens
  an issue** rather than silently writing nulls. Assert structure; never `.get()` with a default.
- arXiv triage precision and recall measured on our own labelled set of at least 200 papers, and the
  measured numbers replace the estimates above in this document.

### Phase risk

**A tier-1 upstream source sunsets.** Papers with Code was the biggest and best-funded attempt in
this space and Meta retired it on 2025-07-24 -- not from staleness, but because a single owner
deprioritised it. Mitigation is structural: every ingested field records its source and is
re-derivable from a primary source; raw responses are kept hashed under `_ingest/raw/`; and no
single upstream is allowed to be the sole source of record for an entire entity type.

---

## Phase 6 -- AI layer: semantic search and suite builder

*8--12 weeks*, widened from 6--10 against [11-ai-features.md](11-ai-features.md) §10's bottom-up
150--243 h. Build only over a catalogue that is already complete and trusted. Full design in
[11-ai-features.md](11-ai-features.md).

### Deliverables

- **Deterministic client-side retrieval first, and it must work with the Worker entirely offline:**
  facet filter, then BM25 via MiniSearch, then cosine over an embedding matrix shipped as int8 and
  dequantised once into a `Float32Array` at load, fused with reciprocal rank fusion. Measured:
  **0.61 ms at 1,500 x 256, which is the shipped configuration**
  ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5 owns the timings; 0.75 ms at
  1,500 x 384 is the recon's headline figure and a conservative upper bound, and the int8 dot loop is
  *slower* at 2.0 ms, so int8 is a transport format only). Ship a
  typed array and a loop. **No HNSW, no vector index, no vector database** -- at this scale that is
  both the correct engineering answer and the auditable one. Use static embeddings
  (model2vec/potion-style), not a transformer in the browser.
- A thin Cloudflare Worker on the same deployment: `claude-haiku-4-5` for structured facet-query
  translation (**~$0.0013 per cached call** *(unverified -- prices move; re-derive from the current
  rate card before committing to the budget)*), `claude-sonnet-5` for synthesis with citations
  enabled (**~$0.045 per suite build** *(unverified -- same caveat)*).
- **G5 spend control, shipped before any public AI endpoint exists.** The site has no auth by
  constraint 7, which means a single publicly reachable POST endpoint is the entire attack surface
  for the monthly bill. Four layers, in order, per [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
  §9 and [11-ai-features.md](11-ai-features.md) G5:
  1. **Cloudflare Turnstile on `/api/*`** -- handles casual abuse.
  2. **The Workers rate-limiting binding** for burst, with the documented caveat that it is
     **per-colo, not global**, and `period` accepts only 10 or 60 seconds. It is not a spend cap.
  3. **A Durable Object or KV daily counter, checked before every model call** -- this is the actual
     hard cap -- plus a self-imposed org spend limit in the Anthropic Console set below the tier
     ceiling.
  4. **A degraded mode.** When the counter trips, or Anthropic returns 429/5xx, the endpoint returns
     **HTTP 200** with `{mode: "deterministic", results: [...]}` and the client renders the facet
     results with a banner and a footer status line. The site must never 500 because the AI is off.
- F1 NL -> facet search, with the facet query rendered **before** the results, editable, every
  constraint carrying a one-click "loosen" toggle, and an `unmapped_terms[]` list displayed as
  "I ignored: ...".
- F2/F3 Suite builder and runnable manifest export (`suite.yaml` in our own CC-BY schema, with entry
  IDs, the index commit SHA, recommended conditions and comparability keys; adapters for Inspect AI,
  lm-evaluation-harness, HELM run-specs, and a plain README). Every entry carries
  `runnable_via: [inspect|lm_eval|helm|custom|none]` and the export header says "3 of 12 runnable
  from a harness; 9 link to their own repos". That admission is a differentiator -- every other tool
  implies everything is runnable. Note that "build your own custom benchmark" is interpreted here as
  **suite assembly** only; authoring new benchmark tasks or data is out of scope for v1 and is
  recorded as a deferred open question in [15-open-questions.md](15-open-questions.md).
- F4 comparability explainer and F5 "explain this number", where the verdict is a deterministic diff
  computed in JavaScript and rendered **above** the prose, and the prose is labelled "generated
  summary of the table above".
- The golden eval set: ~150 items across four splits (`nl_search` 60, `facet_translation` 40,
  `suite_build` 30, `abstention` 20), shipped as a CC-BY versioned artifact in the same repo with an
  entry in the index describing itself. Hard gates: enum-hallucination rate **= 0.000**,
  forbidden-inclusion rate (deprecated, contaminated or licence-incompatible) **= 0.000**, citation
  validity **= 1.000**, "Not covered" section present **= 1.000**. Only deterministic metrics gate a
  release; an LLM-judge score never does, and the judge--human agreement number is published, not
  internal.

### The budget, with its traffic model reproduced

"Budget holds" is not checkable without the assumptions behind it, so the assumption goes here. The
**numbers** stay in [11-ai-features.md](11-ai-features.md) §5, which owns the cost model; an earlier
draft of this document copied `11`'s six-figure budget table verbatim and had already dropped the
load-bearing `(cached)` annotation on one cell, which turned prefix caching into what looked like
sublinear scaling. One table, one owner.

> **Traffic model: one "query" is one F1 FacetQuery call; 35% escalate to a suite build; 20% trigger
> a narration.** F2 runs on Sonnet 5 at ~$0.045; F1 costs ~$0.0013 cached; F4/F5 narration ~$0.0038.

At that model, `11` §5's itemised monthly totals are roughly **$23 at 1,000 queries, $184 at 10,000
and $1,786 at 100,000**, and roughly **$9 / $77 / $717** if a 60% response-cache hit rate holds --
which is an assumption about traffic shape, not a forecast. Plan against the uncached column. All of
these are **(unverified -- confirm before relying on this)**; `11` §5 reconciles them against the
source report's second set of headline figures, where one of three rows differs by about 22% and the
other two agree within 2%. The Anthropic **Start tier's $500/month hard cap** is likewise a documented
figure that should be re-checked before it is relied on.

**Decision on the 100k-queries remedy, which the earlier draft left open and got wrong.** The earlier
text said "suite building moves to Haiku 4.5 or deep mode goes behind a click". Haiku alone does not
clear the cap. `11` §5 prices the substitution: F2 on Haiku 4.5 is $0.0227 a query against Sonnet 5's
$0.045, so 100k queries at the stated 35% escalation is ~$795 of suite building and a **~$1,006
monthly total** -- twice the $500 Start ceiling. With a 60% cache hit it lands around $400, which
clears with no headroom and depends on a hit rate that a traffic spike destroys at exactly the moment
it matters.

> **Pick: gate deep mode behind an explicit click, and move to the Build tier ($1,000 cap) before
> sustained traffic reaches 100k queries a month.** Model substitution is a quality decision, not a
> cost control, and using it as one produces a worse product at a cost that is still unsafe. The
> daily KV cap in G5 is what actually protects the bill; the tier move is what raises the ceiling.

### Exit criteria

- With the Worker disabled, facet search, lexical search and semantic search all still work and the
  site remains fully useful, readable and citable.
- **A synthetic load test of 5,000 requests in one hour trips the daily cap, degrades to
  deterministic retrieval with a visible footer status line, and produces no model charge above the
  cap.** This is the observable version of "budget holds" and it is a hard gate before the endpoint
  is publicly reachable.
- Abstention rate published. A tool that says "I don't know" six percent of the time and is right the
  rest is worth more to this audience than one that always answers.
- No number anywhere in the AI surface was produced by a model. Cost estimates, runtime estimates,
  comparability verdicts and coverage percentages are computed in JavaScript from structured fields
  and shown with their formula.
- Measured per-call costs replace the estimates in this document after the first full month.

### Phase risk

**The AI layer launders guesses into apparent authority.** A fluent paragraph reads as more
authoritative than the table it summarises, and a suite recommendation that omits a domain reads as
a statement that the domain has nothing. Mitigations are structural rather than prompt-based: the
mandatory "Not covered" section, the post-validator that strips uncited claims and marks the
response `partial: true`, hard code filters (never model judgement) for licence and deprecation
exclusions with a visible "excluded N entries because..." panel, and the rule that thin retrieval
produces no synthesis at all -- only the facet query, the thin result set, and *"The index contains
no entries matching X at commit `abc123`. This may be a real gap in the field or a gap in our
curation."* Both readings must be offered; asserting either alone is a lie.

---

## Phase 8 -- Local evaluation runner

*10--18 weeks*, widened from 8--14 against [13-execution-runners.md](13-execution-runners.md) §8's
bottom-up 190--350 h. See [13-execution-runners.md](13-execution-runners.md). It converts the project from a
catalogue into a service with an operational burden a two-person team has to carry forever, so the
gate on building it is deliberately hard and deliberately numeric.

**The evidence gate, decided rather than deferred.** The earlier draft said "build only if Phases
0--5 have demonstrated real usage", which is unfalsifiable and therefore always satisfiable by
whoever wants to build it. Replace it:

> **Build the second adapter, scheduled reruns and the public execution pages only when all three
> of the following are true, measured over the six months after
> public v1: (1) at least three external contributors have landed data through the issue form;
> (2) at least one external publication cites the Zenodo DOI; (3) at least five unsolicited requests
> for reruns or verification have arrived through issues or email.** Below that, the runner stops
> at its first adapter. The first adapter itself is unconditional: it ships with the package,
> runs on the user's own machine, and costs this project nothing per evaluation. What the gate
> now controls is adapter *maintenance*, which is the real recurring cost. Below that bar,
> Phase 8 is not
> built, and the honest thing to do is say so on the roadmap page rather than leave it as a
> perpetual "coming soon".

**Exit:** >=10 benchmarks producing `sandboxed-rerun` claims through the normal contribution path,
with transcripts archived and every run's conditions recorded as a first-class EvalConditions entity.

**Phase risk:** scope creep into becoming a leaderboard service. Constraint 2 exists for a reason;
the execution layer must stay a source of *claims* with a verification badge, never a ranking.

---

## Critical path

Genuinely blocking, in order:

```
taxonomy ─────────► curation ─────────► visualisation ───► AI layer
   │                   ▲                     ▲                ▲
   │                   │                     │                │
schema ───► ingestion ─┘                     │                │
   │                                         │                │
   └──► build pipeline ──► static artifacts ─┘                │
                                                              │
                 catalogue complete and trusted ──────────────┘
```

Four true dependencies, and only four:

1. **Taxonomy before curation.** Entries classified against a vocabulary that then changes must be
   re-classified by hand. This is why the 20-entry checkpoint exists.
2. **Schema before ingestion.** Retrofitting `artifact_url`, `provenance_snapshot`,
   `training_compute_flop` and `reasoning_effort` across 6,598 ingested records is painful enough
   that the Epoch recon flags it explicitly. Add the fields in Phase 0.
3. **Data before visualisation.** An Atlas over 60 entries cannot be evaluated for legibility, and a
   coverage matrix over a partial catalogue shows our shape, not the field's.
4. **Catalogue before AI.** Argued above at length.

**Everything else is schedulable in principle.** The design system
([09-design-system.md](09-design-system.md)) does not depend on the catalogue. The Epoch adapter can
be written before the site. The ingestion adapters can be prototyped whenever a rainy afternoon
appears, as long as they do not write to `main` before the schema settles. The legal and licensing
work is two hours and blocks nothing, which is exactly why it gets deferred forever and must not be.

### Overlap is a function of headcount, not of scheduling

This is a correction to the earlier draft, which claimed overlap bought three months and used the
claim to justify the headline schedule. It does not survive its own arithmetic.

**At one person, these phases are strictly serial and the phase table's totals already reflect
that.** "Schedulable in parallel" and "actually parallel" are different claims. One person context-
switching between curating a robotics entry and debugging an Astro build is not parallelism; it is
the same hours spent differently, plus the switching cost. And the plan argues correctly elsewhere
that curation is the binding constraint -- which means overlapping engineering onto it does not
compress the schedule, it **slows curation**. If you are one person: Phase 2 engineering does not
start until Phase 1 exits, and the total is the upper end of every range in the phase table.

**Overlap is available at two people, and only under one condition: one person owns curation and the
other owns engineering, with no shared work and no review queue between them.** Under that split,
Phase 2 and the adapter half of Phase 3 genuinely run alongside Phase 1, and the engineering person
is idle at the start (Phase 0 is shared) and at the end (Phase 4 is light).

| Configuration | Phases 0--4 to public v1 |
| --- | --- |
| **One person, serial** | **26--57 phase-scoped weeks** (six to thirteen months); **36--77 all-in** (eight to eighteen) |
| **Two people, curation/engineering split** | **20--46 phase-scoped weeks** (five to eleven months); **32--69 all-in** (seven and a half to sixteen) |

The two-person number is not half the one-person number, and that is the point: the curation hours
do not parallelise across two people unless both are curating, and if both are curating nobody is
building the site.

---

## Effort sizing: where the hours actually go

To public v1, at the stated intensity. **These are estimates, not measurements**, and the curation
rows carry nearly all of the uncertainty -- the domain research puts a fully-sourced entry at
**30--90 minutes with heavy AI assistance**, and 2--3 hours for the stress-test cases. Every row is a
range for the same reason the schedule is: publishing a point estimate for the largest line item in
the plan is how a six-month plan becomes a thirteen-month one without anybody noticing.

**Block A -- the phase-scoped workstreams.** These are the twelve lines the phase table's durations
were built from, and "~490--1,080 h" refers to this block wherever another document quotes it.

| Workstream | Hours | Basis |
| --- | --- | --- |
| Benchmark entry curation (310 ordinary + 10 stress = 320 entries) | **175--495** | `(310 x 0.5 h) + (10 x 2 h) = 175`; `(310 x 1.5 h) + (10 x 3 h) = 495`. The per-entry rate is 30--90 min, this document's, and unmeasured |
| Result claims -- non-LLM, hand-curated (60--80) | **60--120** | 60--90 min each; simulator builds, compliance tiers, lead times and assessment papers all have to be read |
| Result claims -- LLM, hand-curated (50--80) | **38--73** | `50 x 45 min = 37.5`; `80 x 55 min = 73.3`. An earlier draft printed 40--75, rounding *both* ends up while the rows either side were exact to the hour |
| Schema, CLI, CI | **45--80** | Phase 0 plus schema churn through the 20-entry checkpoint. **Taxonomy work is no longer inside this row** -- see Block B |
| Site, detail pages, browse, search, build pipeline | **50--80** | Astro + Pagefind + the two-artifact build |
| Atlas: sigma.js view + layout stability + drift gate + epochs | **15--35** | High variance; the stability work alone is 5--15 h and is the least predictable line in the table |
| Design system: tokens, contrast CI, a11y, component inventory | **15--30** | [09-design-system.md](09-design-system.md); cheaper here than retrofitted after the views exist |
| Epoch adapter, ~80 column stanzas, 21 orphan hand-maps | **35--60** | The stanzas are the real cost, not the parser; the orphans are 5--10 h of that |
| Derived metrics, trend, coverage and gap views | **25--45** | ECharts over an already-built pipeline |
| Croissant mapping and extension proposal | **10--20** | Context, mapping file, three worked examples, one MLCommons issue |
| Reviewer recruitment and liaison | **8--20** | Not engineering, does not feel like progress, and has a three-month lead time |
| Legal, licence, DOI, succession, contribution path | **12--20** | Small, blocking nothing, and the thing that makes failure survivable |
| **Block A total** | **488--1,078 h**, quoted elsewhere as **~490--1,080** | **24.5--54 weeks at 20 h/week** |

**Block B -- four workstreams that other documents hand to this table and that no phase row carries.**
This is a correction, and it is the least comfortable arithmetic in the plan. Each of these was
specified, sized and explicitly assigned to the roadmap by the document that owns it; none of them
appeared in any effort row, so the project total was understating itself by a quarter.

| Workstream | Hours | Basis and owner |
| --- | --- | --- |
| Taxonomy definition authoring -- 446 term records | **40--110** | [02-taxonomy.md](02-taxonomy.md) §14 sizes it and states in terms that "all three consequences are for `14-roadmap.md` to absorb". The Phase-0 slice is the 108 spine terms at **11--36 h** and is on the critical path, because a term is not admissible without a definition, an inclusion test, an exclusion test and a near-miss ([03-taxonomy-build-process.md](03-taxonomy-build-process.md) §5) |
| Taxonomy build process -- stress corpus, pilot classification, disagreement measurement, resolution | **~73** | [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §3's own stage table sums to 73 h. It is a point estimate rather than a range because `03` gives it as one; treat that as a weakness, not a precision |
| Manual domain sweeps running *during* the build | **63--185** | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §6 owns the rate at **126--169 h/yr**; prorated over the 26--57 week build that is `126 x 26/52 = 63` to `169 x 57/52 = 185`. Discovery does not pause while curation runs |
| Outreach, alliance and publication programme | **52--88** | [15-open-questions.md](15-open-questions.md) E4's five-row table, 6.5--11 person-days: the EvalEval registry-pairing proposal, the UK AISI cross-reference offer, the MLCommons approach, one post per unindexed domain, and the arXiv technical report. **Distinct from Block A's "Reviewer recruitment and liaison"**, which is [15](15-open-questions.md) B3's specialist-reviewer workstream -- different people, different ask, different calendar |
| **Block B total** | **~230--455 h** | |

| | Hours | At 20 h/week |
| --- | --- | --- |
| **All-in total to public v1 (A + B)** | **~715--1,535 h** | **36--77 weeks -- eight to eighteen months** |

**Which figure to quote, because there are now two and they have different jobs.** Block A is what
the phase table prices and is the figure to use when reasoning about a phase or comparing a feature
against the build. The all-in total is what to use when answering "how long until this is public",
and it is the honest one. The phase table's serial sum of 26--57 weeks prices Block A only; Block B
runs alongside every phase rather than inside one, which is precisely why it went unbudgeted. **Do
not treat the gap as slack.** A plan whose credibility rests on doing arithmetic nobody else does has
to publish the arithmetic that makes it look worse, and this is that arithmetic.

**Hand-curation of entries and claims is 273--688 hours, or 56--64% of Block A at both ends of the
range**, and **38--45% of the all-in total**. Widen "curation" to include the taxonomy authoring, the
taxonomy build process and the discovery sweeps — all of which are the same kind of labour, done by
the same person, and none of which is engineering — and it is **449--1,056 hours, 63--69% of
everything**. That is the number to show anyone who proposes adding a feature. The correct response to schedule pressure is to cut the vision
long tail or drop to Tier-2 stubs in the ingest-then-verify families -- never to cut the seven Core
families, because they *are* the product.

Three sanity checks on the arithmetic, since a document arguing for numerical rigour should survive
being checked:

- **Engineering total** (schema/CLI/CI + site + Atlas + design system + Epoch adapter + derived
  views) = **185--330 h**, which is the figure quoted at the top of this document. Block B adds
  nothing to it; every line in Block B is curation, taxonomy or outreach.
- **At 20 h/week**, Block A's 490 h is **24.5** weeks and 1,080 h is 54 weeks. The phase table's
  serial sum (26--57 weeks) is slightly wider because phase boundaries do not divide hours evenly;
  take the phase table as the schedule for Block A and this table as its justification.
- **Block B at 20 h/week** is 11--23 further weeks, which is where "six to thirteen months" becomes
  "eight to eighteen". The headline at the top of this document gives both.

**Post-v1, sized for information and not committed.** These sit outside both blocks above, because
Phases 5--7 follow public v1 and folding them into the v1 total would overstate the launch cost by
the same margin Block B understated the whole.

| Post-v1 workstream | Hours | Owner |
| --- | --- | --- |
| Ingestion at scale and freshness automation (Phase 5) | not separately bottom-up costed | [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) |
| AI layer (Phase 6) | **150--243** | [11-ai-features.md](11-ai-features.md) §10 |
| The package: SDK, CLI, MCP server (Phase 7) | **75--127** | [17-packages-and-sdk.md](17-packages-and-sdk.md) |
| Local evaluation runner (Phase 8; scope beyond the first adapter is gated) | **217--402** | [13-execution-runners.md](13-execution-runners.md) §8 |
| Hosted API and submissions (Phase 9) | **85--143** | [18-api-and-submissions.md](18-api-and-submissions.md) |

---

## Stopping rules and re-plans

Every other criterion in this document describes a success path. This section describes what to do
when one is not met, because for a project whose central intelligence is that **every predecessor
died**, having no stated stopping rule is the conspicuous omission.

These are triggers, not judgement calls. When one fires, the response happens.

**(a) The per-entry rate is too high.** *Trigger: the measured median at the 20-entry checkpoint
exceeds 60 minutes.* **Response: re-cut the allocation down to ~270 entries before writing entry 21
-- do not absorb it into the schedule.** Cut from the non-Core rows first (vision 22-->12, agents
20-->12, safety-alignment 18-->12, code 16-->12, language 14-->12, society-econ-law 14-->12), then
from the Core rows (robotics 25-->18, biology 25-->18, medicine 20-->18, chemistry-materials
20-->18), preserve the floor rule, and publish the revised table in
[02-taxonomy.md](02-taxonomy.md) §3 with the measured rate as its justification. **270 is the
arithmetic minimum of a 19-family index that obeys both floors** -- 126 in the Core seven at 18 each
plus 144 in the twelve non-Core families at 12 each -- and the path there is fully determined by the
cut above. Below 270 the floor rule cannot be preserved and families must be muted or dropped, which
is a re-plan, not a re-cut, and should be called one. For calibration: **at exactly 60 minutes an
entry -- the trigger value itself -- the 320-entry seed is about 340 h, or 17 weeks of curation
alone.** A 270-entry index where every entry is right is a good outcome; a 320-entry plan quietly
running 50% over is how the thirteen-month case arrives without a decision ever being made.

**(b) The schema is still moving.** *Trigger: any schema change after entry 60.* **Response: stop
curation entirely and finish Phase 0 properly.** Migration cost is superlinear in entry count -- a
field rename at 20 entries is an afternoon, at 60 it is a weekend, at 200 it is a fortnight of work
that produces nothing visible. The exit criterion "the schema has not changed in the last 40 entries"
is the leading indicator; this rule is what happens when it fails.

**(c) Throughput has collapsed.** *Trigger: entries per week below five for four consecutive weeks.*
**Response: switch the ingest-then-verify families to Tier-2 stub mode** (name, URL, domain, status,
one source) **and publish that decision in the repo** as a dated note on the methodology page. This
is the escape valve the risk register keeps pointing at, and it now has a number attached instead of
a feeling. Tier-2 stubs are a documented quality tier, not a failure -- the failure is running at
two entries a week for three months while the plan still claims three hundred and twenty.

**(d) No reviewer answers.** *Trigger: a Core domain still has no named reviewer 10 weeks after
outreach began.* **Response: ship it badged `curation_confidence: unreviewed`, exclude it from Gap
Finder assertions, and keep the recruitment ask visible on the domain page.** This is not a stopping
rule so much as a refusal to let someone else's inbox stop the project -- see
[Phase 1](#domain-reviewer-recruitment-starts-in-week-2-not-at-the-exit-gate).

**(e) The project has stopped.** *Trigger: no commit has touched `data/` in **90 days**.* **Response:
`SUCCESSION.md` is invoked** -- the maintainers post the succession notice, the repo README carries
it, and the search for a steward begins while the data is still current enough to be worth taking
on. **At 180 days the site's staleness banner turns on automatically**, driven by the same commit
timestamp, with no human action required. Both triggers are written into `SUCCESSION.md` itself in
Phase 0, because a succession plan that depends on somebody deciding to invoke it is a succession
plan that will not be invoked.

The hardest of these to honour is (a), because it fires at the moment of maximum optimism, three days
into the most exciting phase of the project. Write the trigger down now, while you have no stake in
the answer.

---

## What "done" means for public v1

A concrete launch checklist. Every line is observable; none of them is a judgement call.

**Data**
- [ ] >=290 benchmarks across 19 of 19 domain families, none below 12 entries, or muted under the
      floor rule (320 targeted).
- [ ] >=130 entries across the seven differentiating families: **robotics-embodiment,
      biology-genetics, chemistry-materials, medicine-health, physics, earth-climate,
      audio-speech** (144 targeted; none of the seven below 18).
- [ ] Zero `ai-drafted-unverified` records on `main`; every entry `primary-source-verified` or better.
- [ ] Every entry has >=1 source with either a DOI or an archived Wayback URL.
- [ ] Every AI-drafted field's `quote` validates as an exact substring of its archived snapshot, or
      the field is `null`.
- [ ] >=130 hand-curated result claims at `condition_completeness` >= 0.6, **>=60 of them non-LLM**
      (110--160 planned).
- [ ] Epoch bulk ingest present, segregated under `data/claims/_ingested/epoch/`, badged
      `machine-ingested`, with its true mean condition completeness and its `unmatched` row count
      published.
- [ ] Every domain is **either** signed off by a named external reviewer **or** visibly badged
      `curation_confidence: unreviewed`; at least three unfamiliar domains are signed off.

**Site**
- [ ] Every benchmark has a permanent URL that renders with JavaScript disabled.
- [ ] Faceted browse, lexical search, and an Atlas that shows obvious domain structure.
- [ ] Comparison Workbench refuses to rank across differing comparability keys and shows a
      field-level diff instead.
- [ ] Coverage map renders curation confidence alongside density; unreviewed domains render
      "insufficient curation confidence to assert a gap" rather than an empty cell.
- [ ] Gap Finder surfaces at least one previously-unknown gap **within a review-backed domain**.
- [ ] Release feed with RSS.
- [ ] **Performance budgets enforced in CI**: landing page interactive < 2.0 s on mid-tier mobile
      over simulated 4G (Lighthouse CI, fails the job); JS on detail pages = 0 KB; Atlas route
      <= 120 KB gzipped (`size-limit`, fails the job); 60 fps sustained at 1,500+ nodes on the fixed
      2,000-node synthetic corpus (nightly Playwright).
- [ ] **Accessibility**: Axe/Pa11y CI pass with zero WCAG 2.2 AA violations across the eight
      archetype pages; Atlas and facet UI fully keyboard-operable including the non-drag selection
      path; contrast verified in both themes by `check_contrast.py`. Per
      [09-design-system.md](09-design-system.md).

**Infrastructure and trust**
- [ ] Deployed on Cloudflare Workers with static assets; CI is the sole writer of `atlas.json`.
- [ ] CI blocks on schema validation, generated-artifact drift, the Atlas drift gate, contrast, and
      the accessibility job.
- [ ] `atlas_epoch.yaml` exists, the drift gate has fired and been cleared once by a reasoned epoch
      bump, and the Atlas page renders the re-base notice when the epoch is recent.
- [ ] `LICENSE-DATA` (CC-BY-4.0), `LICENSE-CODE` (MIT) and `REUSE.toml`, `CITATION.cff`,
      `SUCCESSION.md` **with its 90/180-day triggers written in**, `/attributions` generated from the
      sources entity.
- [ ] Zenodo release DOI minted and resolving; full YAML downloadable at a commit hash.
- [ ] An outsider has added a benchmark through the issue form without touching git.
- [ ] Methodology, taxonomy definitions and the non-goals page published -- including an explicit
      statement of what this index refuses to do and why.

**Positioning**
- [ ] `taxonomy/` was released under CC-BY with its own DOI at the end of Phase 1, and the gap-matrix
      preprint was posted -- months before this launch.
- [ ] The landscape page names BenchmarkList, Benchmark Radar, Every Eval Ever and Epoch AI by name,
      states what each does better, and states our boundary. A plan that claims unoccupied ground
      that is visibly occupied is exactly the unsourced confidence this project exists to oppose.
- [ ] `croissant-benchmark` published as a namespaced JSON-LD context with a committed field mapping,
      three worked examples from three domains, and a filed issue on the MLCommons Croissant
      repository -- never as a modified copy of the spec (CC BY-ND).

---

## Risk register

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **Existing indexes make this redundant** | **High** *(raised from Low -- the user flagged it, and the research confirmed it)* | BenchmarkList (2,545 benchmarks, closed, no licence, no API) and Benchmark Radar (open but CC BY-NC-SA, LLM-centric) both occupy adjacent ground; Every Eval Ever occupies the results half. The boundary is stated in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) and is never raw count: **open, citable, forkable, provenanced, and cross-domain at depth**. Concretely -- non-language domains nobody indexes, lineage and supersession nobody models, comparability as a *refusal* mechanism everyone's instinct opposes, liveness signalling nobody does, a live gap matrix, plain CC-BY, and a Croissant benchmark extension. Propose ourselves as the benchmark-registry counterpart to EEE's result-registry rather than a rival. |
| **A competitor adds the non-language domains first** | **High** *(raised from Medium-High: the all-in schedule is eight to eighteen months, so the window of invisibility is now longer than the moat)* | The moat is eight to twelve months wide, our silence is eight to eighteen, and nothing stops a two-person indie team from adding a robotics tab in a fortnight. That inversion is the reason the Phase-1 taxonomy-and-gap-matrix release is a deliverable rather than an optional flourish: it is the only thing that puts a public, citable, dated stake in the ground before the catalogue exists. Mitigation: **publish the taxonomy and gap analysis at the end of Phase 1**, months before the catalogue, so the claim is staked and citable early. CC-BY means being copied is adoption, not loss. And the defensible layer is not the entry list -- it is evaluation conditions and comparability-as-refusal, which a ranking-first competitor structurally will not build, because refusing to rank is the opposite of their product. |
| **Curation burden exceeds capacity** | **High** | Realistic per-domain targets; Tier-2 stubs as an escape valve with a numeric trigger ([Stopping rules](#stopping-rules-and-re-plans) (c)); the 20-entry checkpoint re-cut ((a)); automated ingest from permissive sources from Phase 5; hand-curation spent only where it is the differentiator; visible staleness beats invisible rot. |
| **Maintainer burnout / bus factor of one** | **High** | The cause of death in most of the prior art. Automate tier-1 ingestion; recruit per-domain stewards (MedHELM survived HELM's maintenance mode by spinning out to an independent steward); no-PR contribution path; `SUCCESSION.md` published from day one **with automatic 90-day invocation and 180-day staleness-banner triggers**; scope deliberately capped (vision long tail). Data-as-git plus CC-BY means the asset survives the maintainer. |
| **Ingestion identity resolution silently creates duplicates** | **High** | Never dedupe on ingest. Emit every row as a separate claim with honest completeness and surface near-duplicate signatures (same benchmark + same model version + delta < 0.005 + different source spelling) in a quality dashboard for human resolution. Manual benchmark-ID allocation; a hand-maintained crosswalk over ~550 model groups and ~1,048 version strings; the `unmatched` verification rule and its published count. |
| **AI-drafted data enters as fact** | **High** | Unverified entries excluded from the build; **every numeric field requires a `quote` that validates as an exact substring of the archived snapshot, or the field is nulled**; the status ladder enforced in CI; the curation copilot writes only to `drafts/` with `curation.verification_status: ai-drafted-unverified` and the site build refuses to publish it. |
| **The AI layer launders guesses into authority** | **High** | The governing rule, reproduced verbatim in [11-ai-features.md](11-ai-features.md). The model never produces a number. Mandatory "Not covered" section; post-validator strips uncited claims; hard code filters for licence and deprecation; thin retrieval produces no prose; abstention rate published. |
| **Licence contamination from CC-BY-SA / NC sources** | **High** | The single largest legal risk in the ingestion strategy. Papers with Code is CC-BY-SA-4.0 and viral; Evaluation Cards is CC-BY-SA; Benchmark Radar's content is CC BY-NC-SA and must **not** be ingested at all. ADR written in Phase 0; quarantined tree; `provenance: pwc-archive` on every field; re-derivation from primary sources before promotion. |
| **Schema churn after seeding** | **High** | Ten stress entries in Phase 0; hard checkpoint at 20 entries; ADR plus migration script required for every schema change; exit criterion that the schema has not moved in 40 entries; **stopping rule (b) halts curation outright on any change after entry 60**. |
| **The AI endpoint is abused into a five-figure bill** | **Medium-High** | No auth by constraint 7 means one public POST endpoint is the whole attack surface. G5 ships *before* the endpoint is public: Turnstile on `/api/*`, the Workers rate-limit binding for burst, a KV/Durable-Object hard daily cap checked before every model call, an Anthropic Console org limit below the tier ceiling, and a degraded mode returning HTTP 200 with deterministic results. Gated by a synthetic 5,000-request load test. |
| **Contribution friction pushes the project closed** | **Medium-High** | The llm-leaderboard -> llm-stats.com failure, exactly. Issue-form -> validation bot -> auto-PR, modelled on UK AISI's `/register/`. Tested as a Phase 2 exit criterion by an actual outsider. |
| **A tier-1 upstream source sunsets** | **Medium-High** | The Papers with Code lesson. Per-field source recording, re-derivability from primaries, hashed raw snapshots under `_ingest/raw/`, and no single upstream as sole source of record for an entity type. |
| **Stale curation propagates errors into the literature** | **Medium** | Ecosystem Graphs is still cited while twenty months stale. Per-entry `last_verified` on every page, a site-wide freshness indicator that turns on automatically at 180 days, and a prioritised re-verification queue. A stale index must *look* stale. |
| **Atlas is beautiful and useless** | **Medium** | Explicit clustering-legibility exit criterion, tested with an outsider before any styling polish. Fix the facet vectors, not the CSS. |
| **Atlas layout unstable across builds or machines** | **Medium** | Frozen SVD basis, `init=` warm start, Procrustes alignment, a numeric CI drift gate (mean > 0.02 or p95 > 0.05 in normalised coordinates), **layout epochs with a human-written reason as the only escape**, and CI as the only writer of `atlas.json`. |
| **Contamination flags provoke disputes** | **Medium** | Evidence-linked only, never editorial; two-reviewer rule; a dispute path that annotates and never deletes. |
| **Scope creep into *hosting* evaluations** | **Medium** | The non-goal is now precise: we never run an evaluation on our own hardware. The runner ships in the package and executes on the user's infrastructure, so our marginal cost per evaluation is zero. A numeric evidence gate on Phase 8's scope beyond the first adapter (3 external contributors, 1 DOI citation, 5 rerun requests); the index must stand alone first. |
| **Link rot destroys citations** | **Medium** | Mandatory archival at ingest via SPN2 with `if_not_archived_within`; CDX `digest` to detect real content change; weekly automated checks. *(SPN2's exact concurrency and daily caps are unverified -- confirm before relying on this.)* |
| **Taxonomy bikeshedding** | **Medium** | Closed vocabularies; ADR friction on every term addition; terms added only when a real benchmark cannot be classified without one. |
| **Domain expert review unobtainable** | **Medium** | Outreach starts in **week 2**, not at the exit gate, because three months is a normal lead time on an academic's attention. Offer named credit in `CITATION.cff` and on the entry. Approach conference communities (CoRL, MICCAI, ISMB, DCASE, Climate Informatics) rather than individuals cold. If no reviewer is found, the domain ships badged `curation_confidence: unreviewed` and is excluded from Gap Finder assertions -- the gate and the mitigation now agree. |
| **The Croissant extension is ignored** | **Medium** | It costs 10--20 h and the field mapping is useful internally regardless, because it is what makes our records emit valid JSON-LD for Google Dataset Search. Adoption is upside, not a dependency. **The failure mode to avoid is spending months courting a standards body instead of curating** -- file the issue, attach the examples, answer questions, and go back to the catalogue. |
| **Rate-limit misbehaviour against small academic servers** | **Low-Medium** | Over-throttle deliberately against Grand Challenge, Codabench, EvalAI and predictioncenter.org. Being the project that took down the CASP server is a reputational injury no licence protects against. |
| **Cloudflare 20,000-file-per-version cap** | **Low** | Pagefind writes one fragment file per page and has no bundling option in 1.5.2. ~3,100 files at 1,500 benchmarks is fine; ~20,200 at 10,000 benchmarks hits the cap. **Decision: move to Pagefind's Node API with grouped custom records** (one record per domain-subdomain with anchors) when the catalogue passes **~7,000 entries**, per [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §7. Requesting a limit increase depends on somebody else's answer and is not a plan. *(The 20,000 cap is unverified -- confirm before relying on this.)* |

---

## Start here: the concrete first month

This was called "the concrete first week" and it was not one. Summed at this document's own rates it
is **60--120 hours -- three to six weeks** at 20 h/week, and the spine term records alone are 11--36 h
of writing before a line of Python. Calling three weeks of work "the first week" is the one place this
otherwise ruthless document flatters itself, and the first schedule slip is the one that recalibrates
every estimate after it. So: four weekly blocks, in order, as a person can start on Monday morning.

**The ordering is deliberate and it is not the obvious one: entries come before the schema.** Writing
a real entry first surfaces field needs that schema-first design misses, and an implementer who writes
the schema, is then told to ignore it, and then rewrites it has done the work twice.

### Week 1 -- the definitions, because nothing downstream is repeatable without them

1. **Write the 108 spine term records with full definitions** -- 19 domain families, 44 capability
   terms, 27 evaluation-method terms, 18 subject terms -- into `taxonomy/domains.yaml`,
   `taxonomy/capabilities.yaml` and their siblings. Each carries a one-sentence definition, an
   operational inclusion test, an operational exclusion test and at least two examples of which one
   is a near-miss with its reason stated ([03-taxonomy-build-process.md](03-taxonomy-build-process.md)
   §5 sets that bar; [02-taxonomy.md](02-taxonomy.md) §14 sizes the pass at **11--36 h** for this
   slice). **Stub the 204 subdomain terms** with `definition:` and `status: proposed` only -- their
   examples are supposed to be drawn from catalogued entries that do not exist yet, so writing them
   now is writing them twice.
2. **Write `taxonomy/homographs.yaml`.** Four entries, and it has to exist before the first
   `capability[]` value is written, because CI check 9d fails closed and the first PR carrying a
   capability tag will trip it otherwise. Write `games-planning/puzzle-games` under its corrected
   slug on the first pass rather than as a later correction ([02-taxonomy.md](02-taxonomy.md) §3).

### Week 2 -- three entries by hand, then the schema that fits them

3. **Hand-write `data/benchmarks/code/swe-bench.yaml` *without* looking at any schema.** This is
   deliberately counter-intuitive and it is the most useful hour of the month: writing the entry first
   surfaces field needs that schema-first design misses. You will find yourself wanting fields for
   fork lineage, for which scaffold produced the number, and for whether a third party checked it --
   none of which a schema drafted in the abstract would have contained.
4. **Do the same for `data/benchmarks/biology-genetics/casp.yaml`,** and if time remains
   `robotics-embodiment/roboarena.yaml`. The gap between these entries is where the schema's real
   difficulties live: one has a public dataset, a GitHub repo, a leaderboard and rolling submissions;
   the second has biennial editions, embargoed targets, results published as peer-reviewed assessment
   papers, and separately-ranked human and automated categories; the third has no task list, no
   absolute score and physical robots.
5. **Now write `schema/benchmark.py`, `schema/source.py` and `schema/taxonomy.py` in Pydantic**, on
   Python 3.12 with a lockfile, against what those entries actually needed. `schema/taxonomy.py` is
   easy to forget and is load-bearing: the vocabulary files are an *input* to the canonical schema
   (they become dynamic `Literal` enums), so without a model for them the first CI check you write is
   checking files whose shape you invented. Re-verify every version pin against its registry as you
   write it; the numbers in this document were checked on 2026-09-17 and will have moved.
6. **Reconcile.** Write down every field the three entries needed that the schema did not have. Add
   them. Delete every field the schema had that no entry used. Write ADR `0001`.

### Week 3 -- CI, and the legal work that makes failure survivable

7. **Wire `bench validate` and make CI enforce it.** Blocking, on every PR, from the first commit.
   Include the quote-substring check against the archived source snapshot from the start -- the check
   itself is ten lines, but it depends on a `Source` record that stores a normalised text extract and
   a content hash rather than a raw body, and on a stated normalisation (NFC, whitespace collapsed,
   HTML stripped). Settle both with [04-data-model.md](04-data-model.md) before writing the check,
   not after.
8. **Create `LICENSE-DATA` (CC-BY-4.0), `LICENSE-CODE` (MIT), `REUSE.toml`, `CITATION.cff` and
   `SUCCESSION.md`** -- the last of these **including its 90-day invocation trigger and 180-day
   staleness-banner trigger**. Two hours. Ecosystem Graphs had none of these and could not be rescued
   when its lab moved on.
9. **Reserve the Zenodo concept DOI** so every future release inherits a stable citation handle.

### Week 4 -- the decisions that are cheap now and expensive later

10. **Write ADR `0006`, the Papers with Code CC-BY-SA posture**, before a single row is ingested from
    anywhere. This decision is cheap now and expensive after the first ingest.
11. **Draft the reviewer outreach email and send the first three.** Not week twelve. Three
    months is a normal lead time on an academic's attention, and discovering that at the Phase 1 exit
    gate is fatal to the schedule. Write it once, personalise the domain paragraph, send it to CoRL,
    ISMB and Climate Informatics contacts.
12. **Run `scripts/overlap_sample.py` over a 50-family sample** against BenchmarkList and Benchmark
    Radar, and record the result. The overlap band is the most quotable figure in the positioning and
    is currently an analyst prior rather than a measurement
    ([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §4).
13. **Do not start the site until 20 entries exist -- and per the phase table, you will not actually
    start it until 100.** The temptation to build the visible part first is strong and it is how this
    project fails. The site and design system together are 10--13% of the hours; curation is
    56--64%, and curation is the only part nobody else has.

---

*Related: [00-vision-and-scope.md](00-vision-and-scope.md) for constraints and scale;
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) for the competitive reality;
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) for the budgets this document
enforces; [11-ai-features.md](11-ai-features.md) for the AI layer's costs and guardrails;
[12-analytics-and-trends.md](12-analytics-and-trends.md) for the derived-metric ordering;
[15-open-questions.md](15-open-questions.md) for what is still undecided.*
