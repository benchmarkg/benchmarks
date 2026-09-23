# 00 -- Vision and Scope

This is the opening document of the build plan. A reader who reads only this one should understand
what is being built, for whom, what is deliberately excluded, what would count as success, and what
would count as failure. Everything else in the plan is detail hung off this frame.

Reading order and the full document map live in [README.md](README.md). The two documents to read
immediately after this one are [01-landscape-and-positioning.md](01-landscape-and-positioning.md),
which defends every positioning claim made here with evidence, and
[02-taxonomy.md](02-taxonomy.md), which is where the project's actual intellectual work lives.

Every confident factual claim in this document is listed with its source and its confidence tier in
[§11](#11-provenance-of-the-claims-in-this-document). A document arguing that unsourced confidence
destroys trust cannot itself be a wall of unsourced confidence, and the first draft of this file
was exactly that.

---

## The one-paragraph version

Benchmarks are the coordinate system of AI progress, but they are scattered across papers,
leaderboards and repositories with incompatible vocabularies and unstated evaluation conditions.
This project builds the **index**: a faceted, source-linked, version-controlled catalogue of AI
benchmarks across every domain — language, code, mathematics, vision, audio, robotics, chemistry,
biology, medicine, climate, materials, games, agents, safety, society and more — published as a
static site backed by a git repository of YAML files under CC-BY. Every number in it traces to a
primary source and carries the conditions that produced it, stored as structured data rather than
prose. The catalogue mechanically refuses to rank numbers whose conditions differ. It never hosts
benchmark data and never runs evaluations. The database is a build artifact; the YAML at a commit
hash is the citable thing.

---

## 1. The problem, stated concretely

### 1.1 The information is fragmented and each fragment has its own vocabulary

To find out what exists for a given evaluation question today you read arXiv abstracts, then a
GitHub README, then a HuggingFace dataset card, then a leaderboard site, then a vendor's launch
post, then a system card appendix. Each of these calls the same thing something different. One
source's "reasoning" is another's "problem solving" is a third's "System-2". One source's
"benchmark" is a dataset; another's is a task family with eight editions; a third's is a live
competition with no fixed test set at all.

The volume makes this worse, not better. In the seven days to 2026-09-17, arXiv's `cs.CL`, `cs.LG`,
`cs.CV` and `cs.AI` categories published **2,315 distinct papers**, of which **670 mention
"benchmark" in the abstract** and **103 carry it in the title**. A researcher cannot read that. A
catalogue can, if one exists.

That is the one number this project generated itself rather than inheriting, so it is stated
reproducibly. The query, verbatim, and the counting rule:

```
GET https://export.arxiv.org/api/query
    ?search_query=(cat:cs.CL+OR+cat:cs.LG+OR+cat:cs.CV+OR+cat:cs.AI)
                  +AND+submittedDate:[202609100000+TO+202609170000]
    &start=0&max_results=100&sortBy=submittedDate&sortOrder=descending

Date field  : submittedDate (NOT lastUpdatedDate -- v2 resubmissions of old papers
              would otherwise be counted as new)
Dedup rule  : the four categories are combined with OR inside one query, so arXiv
              returns the UNION and each paper is counted once however many of the
              four it is cross-listed in. 2,315 is the union, not a sum of four
              category counts.
Filters     : abs:"benchmark" -> 670 ; ti:"benchmark" -> 103
Must use HTTPS: http:// returns a 301 and yields an empty body if redirects are
              not followed. Rate limit per arXiv's ToU: 1 request / 3 s, 1 connection.
```

Measured by recon:sources on 2026-09-17. The script that regenerates this number is committed to
`tools/arxiv_volume.py` in Phase 0, and the figure on the site is regenerated weekly rather than
quoted from this document — the same standard [§5.1](#51-transparency-is-structural-not-aspirational)
imposes on every `Source` record. Keyword filtering alone is a weak instrument: measured
hand-scoring of 40 abstracts put a regex prefilter at roughly **60% precision and 70% recall**, which
is why [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) makes an LLM triage pass mandatory
rather than optional.

### 1.2 Comparable-looking numbers are routinely not comparable

Two reported scores on the same named benchmark are frequently not measuring the same thing. The
difference lives in shot count, chain-of-thought prompting, tool access, the agent scaffold, the
sampling temperature, the selection strategy (`best-of-n` versus first sample), the judge model and
its version, the retry budget, the reasoning effort setting, and the harness that glued it all
together. These are almost never structured fields. They are prose footnotes, or they are absent.

This is not a hypothetical. In Epoch AI's own `mmlu_external.csv`, the model `falcon-7b` appears six
times, all at a nominal 5 shots, with scores of 0.35, 0.269, 0.262, 0.262, 0.2603 and 0.239 — a
**34% relative spread on the same model and the same benchmark**, sourced from four different
vendors' technical reports. Epoch stores all six and does not adjudicate, which is the right call.
What is missing is the structure that would explain the spread.

The field knows this and has not fixed it. Stanford's BetterBench assessed 24 benchmarks against 46
criteria and found **17 of 24 had no easy-to-run reproduction script**. Our own analysis of the
Epoch AI dataset — the highest-quality public benchmark result set in existence — finds that the
subset meeting a plausible condition-completeness bar of 0.5 is **approximately zero**: even its
best-documented file leaves chain-of-thought, judge model, temperature, retries and shot selection
null. Across all 6,598 rows, `chain_of_thought`, `shot_selection`, `sampling.temperature`, `seed`,
`retries_allowed` and `judge_model` have **zero coverage**. The consequences for our own ingestion
are worked through in [04-data-model.md](04-data-model.md) and
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).

The consequence is that every leaderboard which sorts a column is making an unstated claim that the
rows are comparable, and that claim is usually false.

### 1.3 Benchmark identity is chaotic and nobody models it

A benchmark's name does not identify it. Live examples, all verified by reconnaissance on
2026-09-17:

- **OSWorld** now exists as OSWorld, OSWorld-Verified and OSWorld 2.0 — different benchmarks, one
  name in most citations.
- **Terminal-Bench 2.0 and 2.1** run concurrent leaderboards, with a third generation on a
  different domain.
- **SWE-bench** has spawned Verified, Lite, Multimodal, Multilingual and Pro.
- **FrontierMath** has tiers 1–3 v2, tier 4, tier 4 v2 and Erdős — and Epoch reissued a corrected
  edition on **12 June 2026 after finding errors in 42% of problems**, which makes version pinning
  mandatory rather than fastidious.
- **HELM** has eight leaderboard variants across text, vision, image generation, tables, medicine
  and audio.

Epoch AI's metadata already carries a `superseded_by` column — populated on exactly 2 of its 81
benchmark rows, both FrontierMath — which is the only acknowledgement of this problem in any public
catalogue. No one models fork lineage, edition-versus-version, or "which variant produced this
score." A score without a version is not evidence.

### 1.4 Coverage is wildly uneven and nobody can see it

There are dozens of overlapping language-reasoning benchmarks and near-nothing for causal reasoning
in chemistry. Published research has begun finding specific holes — one 2026 survey reports **zero
benchmark coverage for evading human oversight, self-replication, and AI R&D capabilities**
(arXiv 2605.16282, *unverified — confirm the exact claim before citing it in the product*). Another
found behavioural benchmarks clustered heavily in sandboxed (34/40) and rule-based (28/40)
settings. There is no education benchmark of consequence at all; tutoring quality is measured by
learning-gain RCTs, not leaderboards.

Every one of these findings was produced once, by a paper, and then frozen. There is no live,
queryable domain × capability coverage surface anywhere. The empty cells are invisible by default,
which is exactly backwards: the empty cells are the most decision-relevant information in the field.

For scale, the grid this project publishes gap claims from is **19 domain families × 13 capability
groups = 247 cells**, with a finer navigational grid of **204 (family, subdomain) pairs × 44
capability terms = 8,976 cells** underneath it. [02-taxonomy.md](02-taxonomy.md) owns both
vocabularies and both cell counts; [12-analytics-and-trends.md](12-analytics-and-trends.md) owns
what is published from them and why only the coarse grid may carry a gap claim.

### 1.5 The domains outside language are worse served still

Robotics, protein structure, weather, materials discovery, medical imaging and formal proof each
have mature, well-run benchmark cultures that are invisible to anyone outside the subfield. CASP
and CAMEO (protein structure, CAMEO evaluating **weekly**, CASP **biennially**), Grand Challenge
(**264 medical-imaging challenges** with deadlines into 2027, verified through its public REST API),
Matbench Discovery (**43 eligible models**, with a training-data eligibility tier system), Open
Catalyst, WeatherBench 2, GEO-Bench 2, and the entire robotics cluster — LIBERO (130 tasks),
RoboCasa365 (365 tasks), BEHAVIOR-1K, Open X-Embodiment (22 embodiments, 500+ skills), ManiSkill,
RoboArena. **Robotics is the single largest unindexed field, with no central hub of any kind.**

**Stated precisely, because the loose version of this claim is false.** BenchmarkList carries at
least two of these — Open Catalyst OC22 and GEO-Bench 2 were verified present on 2026-09-17 — so
"they appear in no catalogue" is wrong and a reader can disprove it in one minute. What is true is
narrower and is the claim this project actually rests on: **they appear in at most one closed
catalogue, as a name and a link, and are indexed nowhere with lineage, evaluation conditions, metric
definitions and access model as structured, downloadable fields.** Those four fields are the
operational test of "at depth" used throughout this plan, and they are the test because they are the
four things that make an entry usable rather than merely findable. See
[§2.4](#24-the-honest-positioning-statement) for the full competitive picture, and note that
recon:landscape itself carries both the loose and the precise version of this claim in adjacent
paragraphs — the precise one is the one that survives checking.

This is not a niche complaint. These are the domains where AI is being deployed into physical and
biological systems, and they are the domains where no one can currently answer "what is the state
of measurement here?" without being a specialist.

### 1.6 Previous attempts to fix this have died, and their corpses are still being cited

This is the part of the problem statement that most shapes the design, so it appears here rather
than only in the risk register. **Every cross-domain AI catalogue attempt to date has died within
12–24 months, and none died of insufficient ambition.**

| Attempt | Scale reached | Fate | Cause of death |
| --- | --- | --- | --- |
| Papers with Code | 9,327 benchmarks, 5,628 datasets, 79,817 paper↔code links | Sunset **2025-07-24**, domain 301s to HuggingFace papers | Single corporate owner deprioritised it; the benchmark layer was never replaced |
| Stanford CRFM Ecosystem Graphs | Structured catalogue in git + static site — *the exact architecture proposed here* | Last push **2025-01-24**, **no licence**, 274★, **0 open issues** | Curation treadmill exceeded the lab's attention; no licence meant nobody could fork it |
| `JonathanChavezTamales/llm-leaderboard` | JSON-in-git, schema-validated, 356★, 40 forks | Self-deprecated, converted into the **closed** llm-stats.com | **Contribution friction** — PRs were too slow versus website discussion threads |
| Stanford HELM | 8 leaderboard variants across text/vision/image/tables/medicine/audio | **Maintenance mode 2026-06-01** (verbatim from its own README) | Academic funding and student-turnover half-life of ~3–4 years |
| HuggingFace Open LLM Leaderboard | 13,000+ models evaluated | **Retired 2025-03-14** | Stated reason: it *"was becoming obsolete and could encourage people to optimize in irrelevant directions"* |
| BIG-bench | 200+ collaborative tasks, ~450 authors | **Archived read-only 2026-04-17** | Saturation and collaboration decay |
| Evidently AI benchmark database | 250 LLM benchmarks | Published 2024-12-10, **last updated 2025-07-31** | Built as a lead-gen asset for an adjacent product |
| BetterBench | 24 benchmarks, 46 criteria, NeurIPS 2024 Spotlight | Still 24 benchmarks; calls itself a *"living repository"* | Paper-shaped, not product-shaped |
| Princeton HAL | 9 agent benchmarks, cost-controlled | **Submissions paused** within a year of publication | Operating cost of running evaluations |
| AISafetyBenchExplorer | 195 safety benchmarks | arXiv 2604.12875 **withdrawn 2026-04-23** | Solo-author institutional fragility |
| Dynabench | MLCommons-owned, DADC / DataPerf / Flores / BabyLM | Last push **2026-02-11**, 29★ | Near-dormant despite institutional ownership |

Three details deserve emphasis. First, Ecosystem Graphs is **still cited as a data source by
2025–26 research** while twenty months stale — so dead curation is actively propagating errors into
the literature. Second, the single most instructive case is llm-leaderboard: a git-backed,
schema-validated community catalogue with real traction that **abandoned git for a closed website
because pull requests were too much friction for contributors.** Any plan whose contribution path
is "open a PR" is walking into that same gravity well. Third, MedHELM survived HELM's freeze by
spinning out to an independent steward (Apache 2.0, technical stewardship by Pacific AI) — which is
the only observed instance in this table of a catalogue surviving its parent, and it is the model
for the per-domain stewardship described in
[05-repository-and-workflow.md](05-repository-and-workflow.md).

The whole mortality analysis is in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md). Its three design consequences
are baked into this plan's principles below and are not negotiable.

### 1.6.1 The corollary: there is now a regulatory demand with no supply

EU AI Act GPAI obligations became enforceable **2026-08-02** and require systemic-risk models to be
evaluated *"using standard benchmarks and state-of-the-art tests"* — **with no registry defining
what qualifies.** NIST published AI 800-2 ipd, *Practices for Automated Benchmark Evaluations of
Language Models*, in January 2026; the UK announced a Centre for AI Measurement at NPL in January
2026; the International Network for Advanced AI Measurement (10 countries, founded Nov 2024)
published consensus areas in February 2026. All of these are writing *practices*. None is building
a *catalogue*. The OECD's Catalogue of Tools & Metrics covers governance tooling, explicitly
disclaims vetting its entries, and excludes capability benchmarks.

---

## 2. What this project is

### 2.1 The short version

A **faceted, source-linked, version-controlled catalogue of AI benchmarks across every domain**,
published as a static site over a git repository of YAML files, licensed CC-BY, DOI'd per release,
forkable at any commit. It catalogues; it does not host data and does not run evaluations.

### 2.2 The expanded version

The unit of the catalogue is the **benchmark**, modelled as a real entity with lineage: families,
versions, editions, forks, supersession. Around it sit eight other entities — organizations,
systems, result claims, evaluation conditions, metrics, sources, human baselines and taxonomy terms
— specified in [04-data-model.md](04-data-model.md).

Benchmarks are classified by **one navigational spine (Domain, two levels) plus seven flat,
multi-valued, orthogonal facets**. Not a hierarchy: benchmarks are irreducibly multi-dimensional
and any tree forces a false primary axis. The nineteen domain families, in the order
[02-taxonomy.md](02-taxonomy.md) §3 lists them, are:

```
language              mathematics           code                  reasoning-general
vision                audio-speech          multimodal            robotics-embodiment
physics               chemistry-materials   biology-genetics      medicine-health
earth-climate         games-planning        agents-tooluse        safety-alignment
general-intelligence  society-econ-law      engineering-design
```

That list is a verbatim copy of the family level of a vocabulary
[02-taxonomy.md](02-taxonomy.md) owns; it is reproduced here only because a reader of this document
alone cannot otherwise know what "every domain" means, and if the two ever differ, 02 is right. The
second level (204 `(family, subdomain)` pairs, 204 distinct slugs after decision D3.5's rename of
`games-planning/puzzle-solving` to `puzzle-games`), the 44 capability terms, the 13 capability
groups and the other six facets are all specified there; how they get built, tested and governed is
in [03-taxonomy-build-process.md](03-taxonomy-build-process.md).

**EvalConditions is a separate, shareable, referenceable entity** — not a blob hanging off a
result. Each conditions record computes a `comparability_key`: a hash over the *material* condition
fields. When two claims have different keys, the interface does not rank them. It shows a
field-level diff and says why the comparison is refused. This refusal is the product's signature
behaviour, not a caveat on it.

**Result-claim curation is tiered by existing coverage.** Where a mainstream leaderboard already
maintains numbers — which is most LLM benchmarks — we catalogue the benchmark richly and ingest or
link rather than hand-curate claims. Where nobody else has numbers — robotics, chemistry, climate,
protein structure, formal proof — we curate claims ourselves. This is the concrete mechanism for the
user's "avoid repetition" requirement, and it is the difference between a plan that survives a
two-person team and one that does not. Details in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10 and
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).

A **coverage and gap matrix** is a first-class output, not a chart. It is rebuilt on every commit
and shows curation confidence alongside coverage density, so that a gap in our curation cannot be
misread as a gap in the field. See [12-analytics-and-trends.md](12-analytics-and-trends.md).

An **AI layer** sits on top as a lens: semantic search, English-to-facet-query translation, and
suite assembly (helping someone pick the right set of *existing* benchmarks for their system and
export a manifest). It is additive and degrades gracefully; the site is fully useful, readable and
citable with it switched off entirely. See [11-ai-features.md](11-ai-features.md).

#### What "Tier-1" means, because the whole scale model rests on it

The seed target, the per-family floors and success criterion S8 are all counted in **Tier-1
families**, and until this revision nothing in the plan defined the term. It is defined here and
this document owns it.

> **Tier-1 (field-defining).** A benchmark family is Tier-1 if **any one** of the following holds,
> and the entry records which one and its evidence:
> 1. it is named in **two or more independent vendor system cards, regulator documents or
>    standards drafts**; or
> 2. it carries **published results from three or more independent organisations**; or
> 3. it is **the recognised standard instrument within its subfield community** — evidenced by a
>    community registry, a recurring challenge cycle, or a survey paper naming it as such.
>
> Test 3 exists because tests 1 and 2 are LLM-shaped. CASP, DCASE and the CCDC blind tests would
> fail both and are unarguably field-defining. A family that satisfies none of the three is Tier-2:
> worth a catalogue entry, not worth a curation hour beyond a stub.

**Which test produced the existing numbers, stated honestly:** none of them. The recon's estimate of
roughly 300 Tier-1 families across thirteen domains is one researcher's expert judgement, recorded
on 2026-09-17, not the output of this test *(unverified — confirm before relying on this)*. The test
above is what a curator applies from Phase 0 onward, and the Phase-0 sizing survey re-scores the
thirteen estimated families against it, which is also when the six never-sized families (code,
language, mathematics, reasoning-general, multimodal, engineering-design) get their first evidenced
count. Expect the retrospective re-scoring to move the estimate; publishing the denominator with its
provenance, as [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3 requires, is what makes
that survivable rather than embarrassing.

### 2.3 The four differentiators

These are the answer to "why not just use X?" They are load-bearing; every subsequent document
should be checkable against them.

1. **Cross-domain breadth at depth.** Robotics, protein structure, weather, materials and formal
   proof appear in at most one closed catalogue as a name and a link, and are indexed by nobody with
   **lineage, evaluation conditions, metric definitions and access model as structured fields**.
   Those four fields are the test of depth, not presence — see
   [§1.5](#15-the-domains-outside-language-are-worse-served-still) for why the looser claim is
   false and [§2.4](#24-the-honest-positioning-statement) for who holds the adjacent ground. This is
   the moat precisely because it is curation labour that no leaderboard company wants to do — it
   does not convert into a ranking.
2. **Evaluation conditions as structured data**, with a computed `comparability_key`, so the
   interface can mechanically refuse to rank non-comparable numbers and show a field-level diff
   instead.
3. **Coverage and gap analysis.** A live domain × capability matrix showing what nobody is
   measuring. The empty cells are the most valuable output of the project.
4. **The index as citable data.** CC-BY YAML at a commit hash, forkable, DOI'd per release. This is
   infrastructure, not a website.

### 2.4 The honest positioning statement

**The premise "nobody has done this" is false as stated, and the plan must say so.** As of
2026-09-17 three projects occupy adjacent or overlapping ground, all launched after most model
training data:

| Project | Scale | Licence / openness | Overlap band (analyst prior, 2026-09-17 — judgement, not measurement) | Our boundary |
| --- | --- | --- | --- | --- |
| **BenchmarkList** (benchmarklist.com), launched **2026-07-15**, two-person indie team | 2,545 benchmarks, 1,604 providers, 24,074 models; genuinely cross-domain (Open Catalyst OC22, GEO-Bench 2 verified present) | **Closed** — no API, no bulk download, no stated licence, not open source | **High** (~75%) | **Open / citable / forkable / provenanced.** Never raw count. They build an "Experimental Capability Index" via a "Rosetta Stone method" aligning overlapping results onto one scale — precisely the single-number ranking we reject |
| **Benchmark Radar** (benchmark-radar.org, arXiv 2609.11115, **2026-09-10**) | 37 ingestion sources, 14,810 raw records, ~1,283 curated | Code MIT, **content CC BY-NC-SA 4.0** — blocks commercial and institutional reuse | **High** (~70%) | **Curation over discovery; CC-BY over NC-SA.** LLM-centric by its own abstract. Do **not** ingest their content — the licence is incompatible with ours |
| **Every Eval Ever / EvalEval Coalition** (HuggingFace + Edinburgh + EleutherAI, arXiv 2606.14516) | 22,235 models, 2,273 benchmarks | **Data CC BY 4.0, code MIT** | **Complementary** (~45%) | **They model results; we model benchmarks.** No benchmark-entity catalogue, no domain taxonomy, no non-language domains. Our best alliance target |

**The overlap column is a band, not a number.** The percentages are recon:landscape's own analyst
prior formed on 2026-09-17, not a measurement, and
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §4 — which owns the overlap
question — demonstrates that the 50-family sample it schedules cannot distinguish 70% from 75% at
any useful confidence (±14 points at 95%). Read the band; the number is there only so a later
measurement has something to move.

The unoccupied ground is **narrower and more specific** than "a cross-domain catalogue", and it is
genuinely still there:

1. **Non-language domains at depth**, on the four-field test above — robotics first, then medical
   imaging, materials, structural biology, climate, formal proof.
2. **Benchmark lineage, versioning and supersession** — modelled by no one except Epoch's single
   `superseded_by` column, populated on 2 of 81 rows.
3. **Comparability as a refusal mechanism** — every competitor's instinct is the opposite
   (BenchmarkList's Rosetta Stone, Epoch's ECI, Artificial Analysis's Intelligence Index). A
   catalogue whose signature behaviour is declining to rank is unoccupied and is the most
   defensible trust position available.
4. **Liveness and deprecation signalling** — 137 of 195 safety benchmarks reportedly had stale repos
   *(arXiv 2604.12875, withdrawn 2026-04-23 with no PDF available — treat the figure as
   unverified-by-peer-review while treating the direction as credible)*; no catalogue marks
   benchmarks as dead.
5. **A live coverage/gap matrix** — papers do this once and freeze.
6. **The regulatory reference artifact** — EU AI Act GPAI, enforceable 2026-08-02, with no registry.
7. **Plain CC-BY** — nearly unoccupied, and the only licence under which companies, regulators and
   commercial eval vendors can build.
8. **A Croissant benchmark extension.** MLCommons Croissant is the adopted ML-dataset metadata
   standard (HuggingFace, Kaggle, OpenML, TFDS, Google Dataset Search) and has **no
   evaluation/benchmark extension**. A benchmark is not a dataset — it adds tasks, metrics, splits,
   protocols and conditions. Publishing `croissant-benchmark` converts this from "another website"
   into a standard with an institutional home and free distribution through Google Dataset Search.
   *Constraint: the Croissant spec is CC BY-ND, so we may publish a namespaced extension but must
   never republish a modified spec.*

A plan that claims unoccupied ground which is visibly occupied is exactly the unsourced confidence
this project exists to oppose. Stating the overlap honestly is not a weakness in the pitch; it is
the pitch.

### 2.5 The four surfaces

The same catalogue is reachable four ways, and the rule that binds them is that **they are one
object**. All four are built from the YAML at a commit, all four carry the same
`comparability_key`, and all four refuse to rank claims whose conditions differ. If any two would
answer a question differently, one of them is wrong. That is what lets a citation in a paper and a
call in a script refer to the same thing.

| Surface | What it is for | Owned by |
| --- | --- | --- |
| **The repository** | The citable object. YAML at a commit, CC-BY, forkable, reconstructible with no service running | [05-repository-and-workflow.md](05-repository-and-workflow.md) |
| **The site** | Reading, browsing and the visual arguments — coverage, saturation, the Atlas, the comparison workbench | [10-visualization.md](10-visualization.md) |
| **The package** | Putting the catalogue and its refusals inside someone else's program: a Python SDK, the `bench` CLI, an MCP server for agents, and the local-first evaluation runner | [17-packages-and-sdk.md](17-packages-and-sdk.md) |
| **The API** | Queries the static artifacts cannot serve well — joins, point lookups from constrained clients, freshness between releases — plus the submission intake | [18-api-and-submissions.md](18-api-and-submissions.md) |

**Only the first two are load-bearing.** The package and the API are additive, and the project's
survivability argument requires that it stay that way: if the API disappears tomorrow the package
still works, the site still works, and the data is still citable. Any proposal that makes either of
the last two a dependency of either of the first two should be refused on that ground alone.

---

## 3. The three audiences

In priority order. Each gets a concrete job to be done, written as a task someone actually has.

### 3.1 Researchers — first priority

**What they need:** what to evaluate on, where measurement is absent, and whether a reported number
is trustworthy.

> *Job to be done.* A postdoc has a new method for long-horizon robotic manipulation and three
> months before a submission deadline. She needs to know which manipulation benchmarks reviewers
> will expect, which are simulator-locked and to which simulator build, which have live
> leaderboards versus frozen result tables, and which have been effectively saturated. Today this
> takes her a week of reading GitHub repos and asking people on Slack, and she will still miss
> RoboCasa365 because it did not exist when her advisor last looked. She wants: filter Domain =
> `robotics-embodiment`, Capability = long-horizon planning, Access = open, `maintenance_status` =
> actively-maintained; read twelve entries with their metrics, task counts, simulator dependencies
> and last-verified dates; see that three of them have no published results since 2025 and are
> flagged `stale`; export the shortlist with links.

> *Second job.* A safety researcher wants to know what is *not* measured. He opens the coverage
> matrix, filters to `safety-alignment`, and sees the cells with zero benchmarks and high curation
> confidence — meaning we looked and there is nothing there, as distinct from we have not looked.
> That distinction is the whole design of the coverage view, and it is why curation confidence is
> rendered alongside density rather than as a footnote.

### 3.2 Developers and engineers — second priority

**What they need:** to select benchmarks for a system they are shipping, and to interpret other
people's claims about systems they might buy.

> *Job to be done.* An engineer at a mid-sized company is choosing between three coding agents. Two
> vendors quote SWE-bench Verified numbers, 72.1% and 69.8%. She needs to know whether those are
> the same measurement. In this catalogue, she opens the comparison workbench, adds both claims,
> and gets a refusal: the `comparability_key`s differ. The field-level diff shows one used a
> proprietary scaffold with a 200-step budget and `best-of-8` selection, the other a bash-only
> harness with a single sample. The catalogue does not tell her which agent is better. It tells her
> that the two numbers do not answer the question she asked, and then — this part is not optional,
> see S4 — it offers her the closest pair of claims on that benchmark that *are* comparable, or
> states plainly that none exists.

> *Second job.* The same engineer then uses suite assembly: describes her system ("a retrieval
> agent over internal documents, tool-calling, no code execution") and receives a proposed set of
> existing benchmarks with links, licences, access models and recommended evaluation conditions,
> exported as a manifest. Note what this is not: it does not author new benchmark tasks or data.
> That would require hosting data and contradicts the first hard constraint.

### 3.3 Analysts and the interested public — third priority

**What they need:** to see where capability is moving, how fast, and where the measurement
apparatus itself is weak.

> *Job to be done.* A policy analyst has to brief a committee on whether GPAI evaluation
> obligations are satisfiable in practice. She needs a defensible, citable answer to "what counts
> as a standard benchmark for X capability", plus honest evidence about how many of those
> benchmarks are maintained, reproducible and uncontaminated. She cites the index at a commit hash
> so that her brief remains checkable in eighteen months even after the underlying entries change.
> That citability is not a nicety — it is the entire reason a catalogue in git beats a catalogue in
> a database.

> *Second job.* A journalist wants to know whether "AI is saturating benchmarks" is true. The
> saturation and headroom views give a defensible answer per domain, with the refusal to produce a
> single cross-domain number as itself part of the story.

**Explicit non-audience for v1:** anyone wanting *us* to run their evaluation on our hardware.
Running evaluations on demand is an unbounded compute bill and a permanent operating obligation;
see below and [13-execution-runners.md](13-execution-runners.md).

Note what that does **not** exclude, and did not always: a researcher who runs the evaluation
themselves, on their own machine and their own bill, with the runner shipped in our package, and
submits the result for review. That path costs us a review rather than a GPU, and it is how the
catalogue acquires numbers that scale with interest rather than with maintainer hours
([17-packages-and-sdk.md](17-packages-and-sdk.md),
[18-api-and-submissions.md](18-api-and-submissions.md)).

---

## 4. What this project is not

These are the most important paragraphs in the document, because scope creep is the most likely
failure mode and each item below is a genuinely attractive adjacent product.

**Not a dataset host.** The index catalogues metadata and links out; it never redistributes
benchmark data. *Adopting it early would sink the project* because it converts a zero-liability
metadata catalogue into a licensing-exposure surface across hundreds of heterogeneous dataset
licences, and it makes the project a contributor to test-set contamination — which is the exact
harm the catalogue exists to help people reason about.

**Not a hosted evaluation service.** We never run an evaluation on our own hardware, for anyone, on
demand. *Adopting that would sink the project* because it converts near-zero static hosting cost
into an unbounded compute bill and a permanent operations obligation — the cost that paused
Princeton HAL's submissions within a year of publication.

The distinction that makes an evaluation runner admissible at all is **whose machine and whose
bill**. [13-execution-runners.md](13-execution-runners.md) ships as a local-first runner inside the
package: `bench run` executes on the user's own infrastructure, with the user's own keys, and emits
a `RunRecord` they may then submit. Our marginal cost per evaluation is zero and stays zero however
many people run one. What we accept is the *result*, through the review path in
[18-api-and-submissions.md](18-api-and-submissions.md) §4, badged at the rung its evidence supports
and never higher. A submission is a proposed change to the repository, not a write to a database.

**Not a single-number ranking.** There is no universal "AI score". The only legitimate cross-domain
axis is **headroom consumed** — position between a defined baseline and a defined ceiling, computed
only where both are defined and returning `null` visibly where they are not.
*Adopting it early would sink the project* because a composite score is the one artifact that
destroys the comparability thesis: you cannot simultaneously refuse to rank non-comparable numbers
and publish an index that averages them. HuggingFace retired the most-used leaderboard in
open-source AI on exactly this reasoning — that it *"could encourage people to optimize in
irrelevant directions."*

**Not an editorial opinion site.** Every claim about contamination, saturation or benchmark quality
must be evidence-linked, never asserted; where experts disagree, both positions are represented
with their sources. *Adopting editorial voice early would sink the project* because the moment the
catalogue is perceived as having opinions about whose benchmark is good, every correction becomes a
negotiation and the neutrality that makes institutional adoption possible is gone.

**Not a model directory.** Systems exist in the schema only as the subjects of result claims; model
specifications beyond what is needed to interpret a result are out of scope. *Adopting it early
would sink the project* because model metadata decays in weeks rather than years, it is already
well served by HuggingFace and several funded competitors, and maintaining it would consume exactly
the curation hours that the non-language domains need.

**Not a benchmark authoring tool.** "Build your own custom benchmark" is interpreted as **suite
assembly** — selecting the right set of existing benchmarks and exporting a manifest with links and
recommended conditions. *Adopting authoring early would sink the project* because authoring tasks
or data means hosting data, which violates the first constraint outright. This is recorded as a
deferred open question in [15-open-questions.md](15-open-questions.md), not a rejected idea.

**Not a discovery firehose.** We are not trying to surface every benchmark-shaped arXiv paper
within 24 hours; Benchmark Radar already does that with 37 connectors and it is a reasonable thing
to do. *Adopting it as our identity would sink the project* because a firehose's quality ceiling is
set by its worst automated record, and our entire differentiation is that a human verified the
entry. We ingest to draft; we do not publish raw.

**No accounts, no auth, no server-side product in v1.** Static-first, near-zero operating cost.
*Adopting accounts early would sink the project* because auth implies a database, a privacy policy,
a support burden and a migration path away from "the data is the repository" — and it is the first
step on the road that took llm-leaderboard from git to a closed website.

### 4.1 "Near-zero operating cost", in dollars

"Near-zero" without a number is a wish. The costed position, with
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) and
[11-ai-features.md](11-ai-features.md) as the owners of the detail:

| Line | Monthly | Notes |
| --- | --- | --- |
| Domain registration | ~$1–2 | Amortised; the only unavoidable fixed cost |
| Hosting — Cloudflare Workers with static assets | **$0** | Static asset requests are explicitly unbilled and unmetered; only Worker *script* invocations count |
| CI — GitHub Actions | **$0** | Unlimited minutes on standard runners for public repositories |
| Archival — Wayback SPN2 | **$0** | Free API; the constraint is rate, not price |
| AI layer — Worker + model calls | **$0–50, hard-capped** | ~$23/mo at 1,000 queries; ~$184/mo at 10,000 (recon:ai-features, estimated token counts) |
| **Ceiling** | **$50/month** | Enforced, not hoped for |

The AI layer is the only unbounded exposure in the design, because it is a public endpoint that
calls a paid model. Three mechanisms bound it, and all three are required:

1. A **Durable Object daily token counter** is the spend cap. The Workers Rate Limiting binding is
   *not* — it is per-colo with only 10- or 60-second periods, so it stops bursts and not a
   distributed drain.
2. **Cloudflare Turnstile** on the AI endpoint only, plus a Workers KV response cache keyed on
   `SHA-256(normalised_query + index_commit_sha + prompt_version)` so that a rebuild invalidates
   every stale answer automatically and popular queries cost nothing.
3. An **organisation-level spend cap in the model provider's console**, set below the tier ceiling.

**The behaviour when the budget is exhausted is specified, because a cost risk with an unspecified
failure mode is an outage waiting to happen.** The Worker returns **HTTP 200** with
`{mode: "deterministic", facet_query: <best-effort or null>, results: [...]}` and the client renders
the deterministic facet result under a banner reading "AI rationale unavailable — showing
deterministic facet search". It does **not** return 503 and the site does **not** 500. S10 already
requires every function to work with the Worker offline, so budget exhaustion degrades to a state
the test suite covers rather than to an incident.

---

## 5. Principles

Six principles, each with the engineering consequence it forces. A principle with no mechanical
consequence is decoration.

### 5.1 Transparency is structural, not aspirational

Every field traces to a source. Every number carries its conditions. The data lives as diffable
text in git, so every claim can be audited, every change has an author and a date, and any state of
the catalogue can be reconstructed at a commit hash.

*Engineering consequence.* There is **no privileged mutation path** — no admin panel, no direct
database write, no "the maintainers can just fix it in prod". The build reads YAML and emits
artifacts; if the artifact is wrong, the YAML is wrong, and fixing it produces a diff with an
author. The AI layer writes nothing into `data/`, ever ([§5.6](#56-the-ai-layer-is-a-lens-never-a-source)).

**Archival is mandatory, and mandatory needs a mechanism and a failure policy**, because at
6,000–10,000 archived sources at steady state this is a real engineering constraint rather than a
good intention. [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §7 owns the detail; the
shape is:

- **Archiver: Wayback Save Page Now 2.** `POST https://web.archive.org/save` with
  `Authorization: LOW <key>:<secret>`, using `if_not_archived_within=30d` as the idempotency key.
  Limits are **12 concurrent / 100,000 per day authenticated** *(from Internet Archive's own public
  SPN2 spec document, mirrored rather than re-read on 2026-09-17 — lightly unverified, confirm
  before relying on this)*. The per-URL cap of **10 per day** is the one that actually binds, so the
  archiver is invoked per source record, never per field.
- **Existence checks use the CDX API**, never the Availability API, which returned `429` on a single
  cold request during reconnaissance. CDX also returns a content `digest`, which is how we know
  whether a leaderboard actually changed rather than merely being re-fetched.
- **Perma.cc is dropped** from the plan: institutional account required, 10 links/month free. Not
  viable at our volume.
- **Failure policy: a failed archive does not block a merge.** The record carries
  `archive_status: failed` with its reason, the count is published on the trust page (S9), and an
  un-archivable source lowers that source's own reliability rather than stopping a contribution.
  Blocking merges on a third-party service is how contribution friction returns through the back
  door, and [§5.5](#55-curated-not-scraped) exists to keep that door shut.

### 5.2 The schema is the product

Everything downstream inherits the schema's mistakes. A schema that only accommodates LLM
evaluations is a failed schema, and that failure is detectable only by forcing genuinely alien
benchmarks through it early.

*Engineering consequence.* Pydantic v2 is canonical; JSON Schema is generated from it; TypeScript
types are generated from the JSON Schema with `json-schema-to-typescript@16.0.0`; all three are
committed and CI fails if regeneration produces a diff. Before curating at scale, the schema is
validated against ten deliberately hostile cases, each of which breaks a different assumption:
RoboArena (no task list, pairwise preference, physical robots in different rooms), CACHE Challenges
(wet-lab hit rate, participants must buy compounds), CASP17 (editions not versions; human-expert
and automated-server categories ranked separately), WeatherBench 2 (no aggregate ranking by
design), ARC-AGI-3 (two leaderboards with different legality rules), Matbench Discovery
(training-data eligibility tiers), Virtual Cell Challenge (ceiling is a biological replicate, not a
human), Kaggle Game Arena (unbounded Elo that changes when a different model joins the pool),
ForecastBench (results resolve months later), PaperBench (a rubric of ~8,316 leaf nodes and an LLM
judge inside the measurement apparatus). **If any of the ten needs an escape-hatch field or a
free-text blob, the schema is wrong and is revised then — not at entry 200.** Full list and what
each breaks: [04-data-model.md](04-data-model.md).

Four schema additions are required **before** the first bulk ingest, because retrofitting thousands
of records is painful and this is the cheapest moment they will ever be added:
`ResultClaim.artifact_url` (transcript or log URL), `ResultClaim.provenance_snapshot`,
`System.training_compute_flop` with an `estimated` flag and notes, and
`EvalConditions.reasoning_effort` as an enum-plus-free-text. Two more were requested by this document
and are now carried by [04-data-model.md](04-data-model.md) §5, which owns them: `curation.stewardship`
(see [§8.2](#82-the-effort-model-in-three-lines-including-the-one-the-first-draft-omitted)) and the
five-field admissibility block behind [§6](#6-working-assumptions-and-settled-decisions) A5.

### 5.3 Comparability is earned, not assumed

The default posture toward any two numbers is that they are **not** comparable until their
conditions are shown to match.

*Engineering consequence.* `comparability_key` is a computed hash over the material condition
fields, stored on the built artifact and recomputed deterministically from the YAML. The comparison
interface refuses to sort when keys differ and renders a field-level diff instead. Claims carry an
honestly computed `condition_completeness`; it is a default sort key and a default filter, and the
mean is published whatever it turns out to be. Expect it to be low — the Epoch corpus, the best
public one in existence, lands around **0.10** — and quantifying the field's reporting opacity is a
finding, not an embarrassment.

**Name the failure mode: refusal saturation.** The mechanism has two ways to break and only one of
them is obvious. If `comparability_key` hashes too many fields, every pair of real-world claims
differs, the site refuses every comparison, and a principled stance becomes an unusable product that
users leave — and given that condition completeness in the best available source is near zero, this
is the *likely* launch state, not the unlikely one. If it hashes too few, the site grants false
comparability, which is the precise harm it exists to prevent. Three mechanisms hold the middle:

1. **Per-benchmark comparability profiles.** The material field set is not global. A benchmark
   record carries `comparability.profile` plus `material_extra` and `material_waived`
   ([04-data-model.md](04-data-model.md) §8), so a benchmark whose community genuinely does not
   vary the judge model does not have judge-model nulls forcing refusals.
2. **A measured refusal-rate band with a CI gate**, specified in S4 below. Outside the band, the
   profile is wrong and the build says so.
3. **Every refusal offers a next step.** A refusal screen that ends in a refusal is a dead end, and
   dead ends are how a trust position becomes a bounce rate.

### 5.4 Absence is data

The empty cells of the coverage map are among the most valuable outputs of the whole project. The
design must make gaps as visible as coverage.

*Engineering consequence, and it is more expensive than the catalogue it sits on.* An empty cell
means one of three very different things — nobody measures this, our taxonomy cuts this field badly,
or we have not looked — and conflating them would make the project's flagship output untrustworthy.
The distinction cannot be computed from the cell, because an empty cell has no records to compute
from. It has to come from a positive assertion about our own sweep, and
[12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3 owns the mechanism:
`curation_confidence` is a per-family term combining how much of the family's expected Tier-1 set we
have curated, what fraction of its entries were verified within 180 days, and whether a **named
domain reviewer** signed the family off. It multiplies into the gap score, and every factor is
published alongside the product so a reader can re-derive their own ranking. **Only cells in a
reviewer-signed family with high curation confidence are ever published as gaps**; the other two
kinds of empty are visible internally, drawn differently on the map, and routed to the curation
backlog or to [03-taxonomy-build-process.md](03-taxonomy-build-process.md) as a taxonomy bug.

The date on that confidence comes from the **scheduled manual sweep programme** in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §6 — a written per-domain checklist run
quarterly for fast-moving families and semi-annually for slow ones, producing one PR per domain
containing every change plus a dated sweep record. That programme costs **126–169 hours a year**
— [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §6 owns that figure and derives it from
its own tiered sweep table; the "12–20 person-days" an earlier draft carried here was the
superseded estimate — and is what makes "we looked, on this date, at these sources" a fact rather than a feeling.

`null` is a first-class value throughout: headroom returns `null` visibly for Chatbot Arena and
WeatherBench 2 rather than erroring or inventing a ceiling.

**Deadness is derived from observable signals, and the mechanism is specified rather than implied.**
[02-taxonomy.md](02-taxonomy.md) owns the five-term `maintenance_status` vocabulary and its
derivation rules; the parts that matter to the vision are these. The probe reads git-host
`pushed_at`, HuggingFace `lastModified`, package-release dates, extracted leaderboard dates and —
for undated leaderboards, which are the modal case in the non-LLM domains — a normalised SHA-256
fingerprint of the result table. Cadence is weekly for live benchmarks and quarterly for dead ones.
A single failure never changes a status, and any transition *toward* `abandoned` is withheld for 30
days, because a transient outage should not publish a death notice about someone else's work.

Two consequences are uncomfortable and are stated rather than hidden. First, **a fingerprint change
is an update dated at probe time; an unchanged fingerprint is a lower bound on staleness, never a
date.** Second, **`unobservable` will be the modal value in exactly the non-language domains this
project calls its moat** — CASP, CACHE, grand-challenge.org, DCASE and LifeCLEF have no pollable
dated signal at all. `unobservable` is therefore treated as missing data everywhere, never as a
proxy for dead, and is rendered as a statement about our instruments rather than about the
benchmark. The repo-less fallback is a curator-set expected-event date read from the community's own
cycle — CASP is biennial, CAMEO weekly — where a missed expected event, not a silent repo, is the
liveness signal.

### 5.5 Curated, not scraped

Automated ingestion drafts; humans verify and merge. An index whose entries might be hallucinated
or stale is worse than no index, because it launders uncertainty into apparent authority.

*Engineering consequence, and this is the one that decides whether the project survives.* Three
mechanisms follow directly from the mortality analysis in
[§1.6](#16-previous-attempts-to-fix-this-have-died-and-their-corpses-are-still-being-cited):

1. **CC-BY + DOI + forkable-at-commit from day one**, plus an explicit, documented succession story.
   Ecosystem Graphs could not be rescued because it had no licence. This is simultaneously the
   survival mechanism and the differentiator against BenchmarkList (closed) and Benchmark Radar
   (non-commercial). See [05-repository-and-workflow.md](05-repository-and-workflow.md).
2. **Contribution must not require a pull request.** A bot-validated issue-form path — GitHub issue
   template → validation bot → auto-generated PR → human review — modelled on UK AISI's
   `inspect_evals` `/register/`, launched 2026-05-08. The bot comments with the rendered YAML it
   intends to write, adds `Co-authored-by:` so the contributor appears in `git log` and in the
   release notes of a CC-BY dataset, and never merges. The PR path stays for power users. This is
   the specific friction that killed llm-leaderboard, and it is not optional.
3. **Automate ingestion from Tier-1 permissive sources; hand-curate only where hand-curation is the
   differentiator** — the cross-domain taxonomy, the evaluation conditions, the gap matrix, and the
   non-LLM domains. The curation treadmill, not the architecture, is what kills these projects.
   Concretely: Epoch AI's CC-BY data is ingested in bulk into a segregated tree, badged honestly,
   and never mixed into hand-curated claims; 50–80 LLM claims are hand-curated adversarially rather
   than representatively; everything else goes to the domains nobody else covers. See
   [01-landscape-and-positioning.md](01-landscape-and-positioning.md) and
   [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).

**The succession answer, in three sentences, because deferring it to another document is how it
stops existing.** (a) The build reads the date of the last human commit to `data/` and renders a
site-wide dormancy banner automatically — a build-time fact computed from git, costing nothing, and
the direct answer to Ecosystem Graphs, which went twenty months stale while looking current.
(b) `SUCCESSION.md` is written in Phase 0, not at the end, and states its own invocation triggers,
the transfer conditions, and the preferred stewards by name — MLCommons (which already owns
Dynabench and Croissant), EleutherAI and HuggingFace are the candidates the landscape supports, and
per-domain stewards on the MedHELM model are preferred over one central successor.
(c) Every release mints a Zenodo DOI and is mirrored to Codeberg and a HuggingFace dataset repo,
with Software Heritage archival requested explicitly rather than assumed, so the corpus survives the
domain lapsing. **The two triggers are now assigned, and the assignment is
[05-repository-and-workflow.md](05-repository-and-workflow.md) §"What happens when we stop"'s to
own: `SUCCESSION.md` is invoked at 90 days without a commit, and the site-wide staleness banner
turns on at 180.** Succession comes first deliberately — the steward search has to begin while the
data is still worth taking on, whereas the banner is a public admission that it already is not.

**Name the second failure mode: source mortality applies to us too.** This document proves that every
upstream catalogue dies, and then builds the coverage strategy on ingesting from Epoch, Every Eval
Ever and mainstream leaderboards. When one of those sources dies, changes licence or closes its API,
the "ingest, don't curate" tier silently becomes a hole — and nobody notices, because there is no
curator watching a tier we decided not to curate. Papers with Code is the precedent: 9,327
benchmarks, gone in a day, and the replacement never arrived. Two mitigations, both cheap:
**every ingest run commits a dated raw snapshot into the repository**, so a dead source degrades to
a visibly-dated snapshot rather than an empty section; and **per-source liveness runs in the same CI
as per-benchmark liveness**, with each source's last-successful-fetch date on the public trust page
alongside the entry staleness counts.

### 5.6 The AI layer is a lens, never a source

Stated as the governing rule, reproduced in full because it is easy to erode one feature at a time:

> **THE AI LAYER IS A LENS, NEVER A SOURCE.**
> - Retrieval is deterministic, client-side, and reproducible from the static artifact at a commit
>   hash.
> - The model's only jobs are to translate English into a facet query, to order and annotate
>   entries the deterministic retriever already selected, and to narrate verdicts that code
>   computed.
> - Nothing the model emits is ever stored in `data/`, and nothing it emits is citable. The citable
>   surface remains the YAML at a commit SHA.
> - **THE MODEL NEVER PRODUCES A NUMBER.** Cost estimates, runtime estimates, comparability
>   verdicts and coverage percentages are computed in JavaScript from structured fields and shown
>   with their formula. The model writes the sentence around the number, not the number.

*Engineering consequence.* Retrieval must work with the language-model Worker entirely offline: a
facet filter, then BM25 via MiniSearch (5.9 kB gzipped), then cosine over a document-embedding
matrix, fused with reciprocal rank fusion. **Brute-force cosine over 1,500 × 384 vectors measured at
0.75 ms** — Node v24.11.0 / V8, the same engine Chrome runs, measured by recon:tech on 2026-09-17;
sorting the results added 0.03 ms. That is the conservative upper bound, not the shipped
configuration: [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5 settles the
embedding at **256 dimensions**, where the same loop measures **0.61 ms**, and owns every search
timing in the plan. So: **no HNSW, no vector index, no vector database.** A typed
array and a loop is both the correct engineering answer at this scale and the auditable one, and
the in-browser vector libraries the technology reconnaissance surveyed on 2026-09-17 had all last
published in 2023 — a survey of the obvious candidates, not an exhaustive search, and decoration on
a decision the 0.61 ms measurement already justifies on its own. Vectors ship **int8-quantised
for transport (0.58 MB on the wire at 384 dimensions, ~0.4 MB brotli) and are dequantised once into
a `Float32Array` at load** — a measured counterintuitive result, because a naive Int8Array dot loop
was *slower* (2.0 ms) than f32, V8 not auto-vectorising.

**Where the two recon reports disagree, and they do.** recon:tech recommends *static embeddings*
(model2vec / `potion-base-8M`, 256-dimensional) computed in plain JS with no ONNX runtime, on the
grounds that a model2vec model is an embedding matrix and encoding is a token lookup plus a mean
pool — **no transformer runs in the browser**. recon:ai-features marks model2vec "not recommended"
because no JS or browser package exists (checked 2026-09-17; Python and Rust only) and recommends
embedding the query server-side in the Worker with a hosted small embedding model instead. Both
agree on the part that matters — no transformer in the browser, no vector index — and differ on
where the *query* gets embedded. The plan's position, owned by [11-ai-features.md](11-ai-features.md):
**ship the document matrix statically, embed the query in the Worker by default, and keep a
hand-written ~150-line JS static encoder as the offline fallback**, since it is the only option that
satisfies the "retrieval works with the Worker offline" requirement literally. Budget the encoder as
real work — it is not turnkey *(unverified — the transformers.js maintainer confirmed compatibility
for correctly-exported model2vec models on 2026-04-12, but no official `potion-*` repository carries
the `transformers.js` tag)*.

---

## 6. Working assumptions and settled decisions

The first draft filed the licence, the hosting model and the sequencing beside genuinely open
questions, which tells a future reader they are still up for discussion. They are not. The table is
split.

### 6.1 Settled — restated here so nobody relitigates them

| # | Decision | Why it is settled | Owner |
| --- | --- | --- | --- |
| A2 | **Team is 1–2 people part-time with heavy AI assistance**, 20 h/week as the planning figure. All effort sizing assumes this, not a funded staff. If funding appears, spend it on domain reviewers before engineers. | A brief constraint. Every plan that assumed staff is in [§1.6](#16-previous-attempts-to-fix-this-have-died-and-their-corpses-are-still-being-cited)'s table. | [14-roadmap.md](14-roadmap.md) |
| A3 | **Static-first hosting, no auth, no accounts in v1.** Cloudflare Workers with static assets, built in GitHub Actions, deployed with `wrangler`. Not Pages (where the platform stopped investing), not GitHub Pages (no serverless path, which the AI layer needs). | A brief constraint, plus a measured free-tier comparison. | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| A4 | **CC-BY-4.0 for `data/` and `taxonomy/`, MIT for `tools/` and `site/`.** ShareAlike is explicitly rejected — it is what makes Benchmark Radar unusable as infrastructure. | It is simultaneously the survival mechanism ([§5.5](#55-curated-not-scraped)) and the main differentiator. Ecosystem Graphs died unrescuable for want of it. | [05-repository-and-workflow.md](05-repository-and-workflow.md) |
| A5 | **The inclusion boundary is the learned-entrant test.** A benchmark is in scope if at least one entrant, submission or leaderboard row is a learned system **and the entry records a citation for it** in `learned_entrant_evidence`. | Decided in [15-open-questions.md](15-open-questions.md) §A3, with the worked cases. See the note below. | [15-open-questions.md](15-open-questions.md) §A3, schema in [04-data-model.md](04-data-model.md) |
| A6 | **Counting convention: families, not children.** A family (BraTS, DCASE, CASP, Matbench Discovery) has children (editions, tasks, tracks, splits). Every target in this plan counts families. | Counting children multiplies every number by 3–6× and by the number of editions, making all published counts incomparable with everyone else's and with our own earlier ones. | [02-taxonomy.md](02-taxonomy.md) §"How the Domain facet is counted" |
| A7 | **Index-first sequencing.** Taxonomy → index → visualization → claims → analytics → ingestion → (optional) execution. | Building the visible part first is the most common way projects like this stall. | [14-roadmap.md](14-roadmap.md) |
| A8 | **The Papers with Code archive is quarantined, and the decision is made before first ingest.** Its 9,327 benchmarks are the largest cold-start corpus available and it is **CC-BY-SA-4.0 — viral and incompatible with a CC-BY core.** Segregate under `provenance: pwc-archive`, re-derive from primary sources before promoting into the core, or do not ingest it at all. | The single largest legal risk in the ingestion strategy. It is settled *that* it is quarantined; *whether to ingest at all* remains open. | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) |

**A5, and why this document declines a stricter test.** An adversarial critique of this file proposed
a two-part conjunction requiring *two* independent submissions from learned systems. That bar is
attractive and is rejected, for two reasons: [15-open-questions.md](15-open-questions.md) §A3 owns
this question and settled on one entrant with recorded evidence, and a two-submission bar would
exclude a brand-new benchmark in its first year — which is precisely the window in which an index
has early-warning value. The three hard cases the critique asked for are worked in 15's own table: a
numerical-methods intercomparison with no learned entrant (CMIP-style) is **out**; WeatherBench 2 is
**in**, because learned entrants are the point of it; a CACHE wet-lab challenge is **in**, flagged
`ground_truth_source: experimental` and `reproducible_by_third_party: false`, and it is one of the
ten schema stress cases in [§5.2](#52-the-schema-is-the-product) precisely because it breaks the
assumption that a benchmark can be re-run. `learned_entrant_evidence` and the four fields beside it — `evaluation_target`, `execution_mode`,
`ground_truth_source` and `reproducible_by_third_party` — were requested by this document and by
[15-open-questions.md](15-open-questions.md) §A3 and carried by neither schema document until this
pass; they are now in [04-data-model.md](04-data-model.md) §5 and on §15's Phase-0 prerequisite
list. An admissibility rule that references unmodelled fields is a rule enforced by taste, which is
constraint 4 broken from the inside.

### 6.2 Genuinely open — each decided in [15-open-questions.md](15-open-questions.md)

| # | Assumption | If wrong | Where it is decided |
| --- | --- | --- | --- |
| A1 | **Public and community-contributable.** Usefulness to researchers and developers implies public; the contribution path is designed for outsiders from day one even while the contributor set is one person. | An internal tool drops the contribution path, the dispute process and mandatory archival — roughly 30% less work, and none of the survival properties. | [15-open-questions.md](15-open-questions.md) |
| A8b | **Whether to ingest the Papers with Code archive at all**, given CC-BY-SA contamination risk, versus re-deriving its most valuable entries from primary sources. | Ingesting and later discovering the quarantine leaked is unrecoverable without a corpus rebuild. Re-deriving costs curation hours the plan has not budgeted. | [15-open-questions.md](15-open-questions.md) |
| A9 | **English-language primary sourcing.** One study reported 165 of 195 safety benchmarks were English-only *(arXiv 2604.12875, withdrawn — direction credible, figure unverified)*; our sourcing will inherit that bias unless it is countered deliberately. | Multilingual and Chinese-ecosystem coverage (OpenCompass, CompassHub) would need dedicated adapters and a reviewer who reads Chinese. | [15-open-questions.md](15-open-questions.md) §B, as the non-English sourcing question. **Not** 15's §A9, which is a different question — the two documents number their own questions independently and this pointer is by topic, not by number |
| A10 | **Domain reviewers can be recruited at zero cost**, paid only in named credit. See [§7.3](#73-the-external-dependency-this-plan-runs-on). | Two of the ten success criteria are gated on it. Each now has a machine-checkable fallback. | [15-open-questions.md](15-open-questions.md), recruitment plan in [14-roadmap.md](14-roadmap.md) |

---

## 7. Success criteria — and failure criteria

### 7.1 Success, written as observable tests

Each of these is something a person can run and get a yes or no from. Aspirations that cannot be
tested are excluded deliberately.

| # | Test | Passing condition |
| --- | --- | --- |
| S1 | **Orientation test.** Sit a researcher who does not work in domain X in front of the site. | They can name the serious benchmarks in X, with their metrics and access models, in **under five minutes**, without help. |
| S2 | **Provenance test.** Pick any number rendered anywhere on the site. | Its primary source and its full evaluation-conditions record are reachable in **one click**, and the source has an `archive_url` that resolves or an `archive_status: failed` visible on the page. |
| S3 | **The gap test — the strongest single criterion.** Run `bench gaps --grid coarse --min-confidence 0.6 --reviewed-only` over the 19 × 13 coarse grid, which emits `build/derived/gaps.json` with every input factor exposed. | It surfaces **at least one genuine measurement gap the maintainers did not already know about**, in a reviewer-signed family, and **the named reviewer for that family agrees the gap is real** and says so in the issue thread. Fallback if no reviewer answers: the gap survives a check against that domain's own community registry (CASP, Matbench Discovery, Grand Challenge, RoboArena) showing no family we lack. |
| S4 | **Refusal test, two-sided.** Compute the refusal rate over all pairs of hand-curated claims on the same benchmark. | The rate falls **between 40% and 90%**; CI fails outside the band, because 100% means the key hashes too much and near-0% means it hashes too little. Every refusal renders a field-level diff naming every differing material condition, and **every refusal screen offers at least one genuinely comparable alternative claim or states that none exists.** |
| S5 | **Correction test, split by who owns the latency.** An outside expert with no git experience finds an error. | **Machine half:** the validation bot acknowledges, validates and opens a PR **within 5 minutes, 100% of the time** — this is the part contributors actually experience, and 05 specifies about a minute. **Human half:** median time from issue to merged correction **under 7 days**. 72 hours is the goal; it is not a criterion, because a published criterion that a two-person team fails routinely trains everyone to ignore the criteria. |
| S6 | **Citation test.** Cite a specific benchmark entry, at a specific version, in a paper. | The URL is stable, the commit hash is resolvable, the release has a DOI, and rebuilding from that commit reproduces the artifact byte for byte. |
| S7 | **Fork test — the succession criterion.** A third party clones the repository on a clean machine with no credentials of ours. | They can rebuild the entire site and all artifacts in **under 30 minutes**, and the licence permits them to publish it. A monthly `reproduce.yml` run on a clean runner with no cache is what keeps this true. This is what Ecosystem Graphs could not do. |
| S8 | **Breadth test.** Count Tier-1 benchmark families per family, against the definition in [§2.2](#what-tier-1-means-because-the-whole-scale-model-rests-on-it). | **All 19 families non-empty; none below 12; the seven Core families at 18 or more** ([02-taxonomy.md](02-taxonomy.md) §3 owns the allocation and the floor rule). Any family below its floor ships **muted** — `coverage_status: under-surveyed`, badged on every entry, and the Gap Finder silent on that row. Fifteen per family is the credibility target reached by v1.x, not a launch gate. |
| S9 | **Staleness test.** Query the catalogue for entries unverified for more than 12 months. | Every such entry is **visibly flagged in the interface**, and the count is published on a public trust page alongside the verification mix, mean condition completeness, failed-archive count and per-source last-successful-fetch dates. |
| S10 | **Offline-AI test.** Disable the language-model Worker entirely. | Search, faceting, comparison, coverage and every page still work. Nothing in the citable surface changes, and nothing returns a 5xx. |

### 7.2 Failure, stated equally plainly

**The project has failed, regardless of how much has been built, if:**

- **Entries go stale without the staleness being visible.** Ecosystem Graphs is still cited twenty
  months dead, which means it is now a source of errors in the literature. Invisible rot is worse
  than no catalogue, because it launders uncertainty into apparent authority.
- **The site presents non-comparable numbers as a ranking.** The single act that would destroy the
  trust position and make us a worse BenchmarkList.

Four further failure conditions follow from the mortality evidence and deserve the same status:

- **Contribution requires a pull request.** That is the gravity that pulled llm-leaderboard from
  git into a closed product, and there is no reason to expect we are immune.
- **The data becomes uncitable** — licence ambiguity, an unstable identifier scheme, or a build
  that cannot be reproduced from a commit. At that point the project is a website, and websites in
  this space have a 12–24 month half-life.
- **The model produces a number.** One generated figure that a reader cites as ours and the
  provenance story is over. This is why
  [§5.6](#56-the-ai-layer-is-a-lens-never-a-source) is a principle and not a guardrail.
- **The comparison workbench refuses everything.** A refusal rate at or near 100% is not a strong
  stance, it is a broken feature wearing a principle's clothes, and S4 exists to catch it before a
  user does.

### 7.3 The external dependency this plan runs on

S3 and S8 both invoke a domain specialist, and A2 says the team is one or two unfunded people. That
is an unbudgeted external dependency carrying two of the ten success criteria, and pretending
otherwise is how a plan passes review and fails in month nine.

**The recruitment mechanism, and the only currency available.** Outreach starts in **week 2 of Phase
1**, not at the exit gate, because recruiting a specialist reviewer is a human-relations workstream
with a three-month lead time. The ask is always "please check these five entries in your field",
never "please help with my project", which means two or three entries in their domain must already
exist before the first email. Approach communities rather than individuals — CoRL and RSS for
robotics, ISMB and the Protein Structure Prediction Center for structural biology, Climate
Informatics and the ECMWF ML community for earth-climate, MICCAI and the Grand Challenge organisers
for medicine, DCASE and ISCA for audio, the Materials Project and Open Catalyst communities for
chemistry. The offer is **named credit in `CITATION.cff` and on every entry they touched, in a
CC-BY dataset that gets a DOI**. That is the currency academics actually want and it costs nothing.
[14-roadmap.md](14-roadmap.md) budgets 8–20 hours for it and targets seven reviewers, gating at
three.

**The expected yield, honestly.** Unknown, and probably low: cold outreach to busy academics from an
unknown project has no published base rate we could find *(unverified — no source)*. Plan for
silence.

**Therefore every reviewer-gated criterion has a fallback the team can pass alone.** For S3, the
machine-checkable substitute is the community-registry check in the table above. For S8, it is that
the domain's own registry lists no family we lack. And the governing rule, from
[14-roadmap.md](14-roadmap.md), is that **shipping unreviewed is permitted; shipping unreviewed
silently is not** — an unreviewed family renders a visible `curation_confidence: unreviewed` badge
on every entry, is marked unreviewed in the coverage map, and the Gap Finder refuses to assert a gap
in it. An unanswered email costs a badge, not a schedule slip.

---

## 8. Scale expectations

Sizing for the realistic case, not the imagined one. All benchmark counts are **families** per
assumption A6.

The per-domain research estimate is **~300 Tier-1 families across the thirteen domains the recon
actually surveyed, ~1,470 worth a catalogue entry at all, and a realistic ceiling around 4,710** —
with vision and medicine the two domains whose long tails will eat the project if not capped
deliberately. **That is an estimate of what exists, not a target.** The seed target is **320
entries**, and the per-family allocation, the Core-family set and the floor rule all live in
[02-taxonomy.md](02-taxonomy.md) §3, which is the only copy. Six of the nineteen families were never
sized by the recon at all, so 78 of the 320 rest on our own estimate and are weaker than the rest;
say so when quoting the total.

| Entity | Public v1 (end of Phase 4) | Twelve months post-launch | Steady state (year 2) |
| --- | --- | --- | --- |
| Benchmark families | **320** (launch gate 290) | 500–700 | 1,200–1,500 |
| Benchmark versions/editions | ~370 | 700–1,000 | 2,000–2,500 |
| Domain families represented, non-empty | **19 of 19** | 19 of 19 | 19 of 19 |
| Systems (models, agents, methods) | ~150 | 400–500 | 800–1,200 |
| Result claims — hand-curated, **non-LLM domains** | **60–80** | 150–250 | 900–1,800 |
| Result claims — hand-curated, **LLM adversarial set** | **50–80** | 100–150 | 600–1,200 |
| Result claims — machine-ingested, segregated | ~6,600 (Epoch) | 8,000–15,000 | 25,000–45,000 |
| EvalConditions records | ~110 | 300–450 | 2,000–3,500 |
| Organizations | ~120 | 250 | 400–600 |
| Sources (archived) | ~900 | 2,000–2,500 | 6,000–10,000 |
| Ingestion adapters live | 3–4 | 8–12 | 18–25 |

**This table is the owner of every corpus-shape count in the plan.** Where
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §7.5 derives page counts, file
counts and the Cloudflare 20,000-file runway, it derives them from *these* numbers; where its own
estimates differ — and on systems, organizations and archived sources they currently differ by
factors of 2 to 4 — this table is the one to re-derive from, because it states a counting rule and
§8.1 shows its working. The archived-sources row matters most: at ~900 sources for 320 benchmarks
and 6,000–10,000 at steady state, the per-benchmark file ratio `08` §7.5 computes is materially
higher than its own working figure, which moves the file-cap runway without changing its
conclusion about which wall arrives first.

**Three notes on this table, because two of its columns were previously misread.**

First, the **column labels are the fix for two real contradictions**.
[14-roadmap.md](14-roadmap.md) §"Which document is canonical for scale" correctly observed that the
first draft's "Public v1" column described a twelve-month steady state rather than the v1 launch,
and that its claim count predated the non-LLM claim deliverable. Both are corrected here. The second
contradiction was this document's own: it labelled the launch column **Phase 2**, which is wrong
under [14-roadmap.md](14-roadmap.md)'s phase table — Phase 2 is the public static site, Phase 3 is
result claims and the Epoch adapter, and **public v1 is the exit of Phase 4**. A reader who planned
against the old label would have scheduled the Epoch ingest inside Phase 2 and found no claims
schema waiting. **[14-roadmap.md](14-roadmap.md) is canonical for anything scoped to a phase**; this
table is the shape of the corpus, not the schedule.

**And one figure in it is contradicted elsewhere, so read this before quoting the second column.**
Several documents quote "1,000–1,500 benchmark families" against a twelve-to-eighteen-month horizon.
That range is the domain reconnaissance's estimate of **how many families exist that are worth a
catalogue entry at all** (~1,470, the middle figure in this section's opening sentence) — it is a
property of the field, not a schedule. This table's 500–700 at twelve months is the number the
effort model can actually pay for: §8.2 shows standing maintenance consuming 33–66% of a 20 h/week
budget by year two, which leaves 7–13 h/week for growth, which at the planning rate buys roughly
180–380 new entries in a year. Where a document needs a twelve-month figure, it is 500–700 and this
table owns it; where it needs "how big could this get", it is ~1,470 and
[02-taxonomy.md](02-taxonomy.md) §3's ceiling column owns that.

Second, the **hand-curated claim rows are now split, because the single row hid the doctrine**. If
the 50–80 adversarial LLM claims sat inside a single 60–100 row, then the v1 curation budget would
hand-curate 10–50 claims across robotics, chemistry, climate, protein structure, medical imaging and formal
proof combined — the domains where the plan says hand-curation has no substitute. They are
additive, the non-LLM row is the larger of the two at launch, and the v1 gate is **130 hand-curated
claims at `condition_completeness` ≥ 0.6, of which at least 60 non-LLM**
([14-roadmap.md](14-roadmap.md) owns the gate).

Third, the **machine-ingested count is not an achievement**. A single Epoch adapter run delivers
roughly 6,598 rows on day one at an expected mean `condition_completeness` around **0.10**. The
meaningful target is the hand-curated row: *claims at condition completeness ≥ 0.6 with a named
source and an archived URL*. Epoch's data does not come close to satisfying that bar, which is
exactly why it remains a measure of our own work.

### 8.1 Resolving the Epoch counts, which the first draft called "unresolved and immaterial"

A document arguing that catalogues die from unverified inheritance does not get to decline to count
files it already has. The counting rule, from recon:epoch-assets' column-level pass over the local
drop on 2026-09-16:

| Quantity | Count | What it counts |
| --- | --- | --- |
| `benchmark_metadata.csv` data rows | **81** | The benchmark universe. This is the number to quote for "how many benchmarks Epoch tracks" |
| Per-benchmark result CSVs on disk | **80** | 59 referenced by `benchmark_metadata.source_file`, 21 unreferenced; one metadata row (`METR`) has no CSV. 81 − 1 = 80 resolves the 80/81 discrepancy entirely |
| Data rows across those 80 CSVs | **6,598** | **This is what "result rows" means throughout the plan.** Mean 82.5 rows/file; largest `gpqa_diamond.csv` at 313 |
| Rows with a public Inspect-AI `.eval` log | **828** | The only subset that earns a verification level above `self-reported` |
| `model_metadata.csv` data rows | **1,063** | 550 distinct `model_group`, 1,048 distinct `model_version` |
| `processed_data_for_eci.csv` rows | **2,760** | 58 benchmarks × 266 models, already normalised — the single most ingestion-friendly file |
| If every secondary numeric score column also became a claim | ~13,400 | Sub-metrics and subsets; deferred to a second pass |

Two things follow. **The brief's "390 models" figure does not match any count in the recon** — 1,063
metadata rows, 550 model groups, 927 distinct `model_version` strings appearing in the benchmark
CSVs — and should be dropped rather than propagated. And **the `epochdl/` directory is not present
in the current working tree**, so these figures are recon's counts, not ones re-run in this pass. The
reproduction command belongs in the repository, not in a plan document:

```bash
# tools/epoch_counts.py --dir epochdl/ --emit counts.json
#   benchmarks        := rows in benchmark_metadata.csv                 (expect 81)
#   result_csvs       := *.csv minus benchmark_metadata, model_metadata (expect 80)
#   result_rows       := sum of data rows across result_csvs            (expect 6,598)
#   eci_rows          := rows in epoch_capabilities_index/*.csv         (counted separately,
#                        NEVER folded into result_rows -- they are a derived latent-ability
#                        fit, not observations)
```

Commit it in Phase 0 and run it in CI on every re-ingest, so the snapshot's row counts are a fact in
`data/_ingest/batches/<id>.yaml` — the `IngestBatch` path owned by
[04-data-model.md](04-data-model.md) §9 — rather than a sentence in a plan.

### 8.2 The effort model, in three lines, including the one the first draft omitted

The first draft priced initial curation and called it "the real shape of the project". It is not.
It omitted the standing maintenance treadmill that
[§1.6](#16-previous-attempts-to-fix-this-have-died-and-their-corpses-are-still-being-cited)
identifies as the actual cause of death in every prior attempt — which is the exact error the
mortality analysis exists to prevent.

**Line 1 — initial curation.** At the planning rate of 30–90 minutes per fully sourced entry — an
estimate from the domain reconnaissance, never a measurement, owned by
[14-roadmap.md](14-roadmap.md) §"Effort sizing" — and 2–3 hours for the ten stress cases, the
320-entry seed target is **175–495 person-hours**.

**Line 2 — one-off engineering and everything else.** Schema, taxonomy, CLI, CI, the site, the
Atlas, the design system, the Epoch adapter, derived views, the Croissant mapping, reviewer liaison
and the legal/DOI/succession work. [14-roadmap.md](14-roadmap.md) §"Effort sizing" owns the breakdown and
totals the whole project at **~490–1,080 hours — 24–54 weeks at 20 h/week, six to twelve and a half
months**,
of which curation is 275–690 hours or 56–64%.

**Line 3 — annual standing maintenance at steady state, which no other document costs.** This is my
derivation from figures the plan already contains, not a measurement *(unverified — recompute once
Phase 3 gives real per-entry re-verification times)*:

| Standing line | Hours/year | Basis |
| --- | --- | --- |
| Scheduled manual domain sweeps | **126–169** | Not derived here. [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §6 owns the figure and the tiered table it sums from (5 quarterly families × 4 sweeps × 4–5 h, 9 semi-annual × 2 × 2–3 h, 5 annual × 1 × 2–3 h) |
| Entry re-verification | **140–260** | ~1,050 re-checks/year at 8–15 min. Tiered, not uniform: fast-moving families annually (~40% of a 1,500-entry corpus), slow challenge-cycle families biennially |
| Ingest adapter repair | **36–100** | One breakage per adapter per quarter at 30–60 min, over the 18–25 live adapters in §8's steady-state row: 18 × 4 × 30 min at the low end, 25 × 4 × 60 min at the high. The earlier 50–100 silently used 25 adapters at *both* ends |
| Issue triage and contribution review | **25–133** | 3–8 items/week at 10–20 min each over a 50-week year. The earlier 40–100 reproduced from neither end |
| **Total** | **327–662 h/year** | **6.5–13.2 h/week, i.e. 33–66% of the 20 h/week planning figure.** All four rows divide by a **50-week working year**, which is the convention this document uses throughout |

**Read that last cell before anything else in this document.** By year two, standing maintenance
consumes between a third and two-thirds of all available time, and the corpus stops growing at the
upper end. This is not a reason to plan differently; it is the reason the ingest-versus-hand-curate
doctrine and the no-PR contribution path exist at all.

**And read this table next to [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §5.4(a),
not instead of it.** That section budgets the *whole* steady-state week at 19.5–20.3 h — discovery
triage, sweeps, re-verification, claims and conditions, review and disputes — and it is the
canonical weekly allocation. This table is the **maintenance subset of it, expressed annually**: it
deliberately excludes discovery triage and intake (roughly 6 h/week in `06`) and new claim and
condition curation (roughly 4 h/week), because those are growth work rather than upkeep, and the
point being made here is how much of the week is consumed *before any growth happens*. The two
figures are therefore not alternatives and must never be added together. The failure mode to name:
**three plausible budgets is indistinguishable from no budget**, and a reader who sums two of them
publishes a discrepancy as a bug report against the plan's own arithmetic. If the allocations ever
need to change, change `06` §5.4(a) and re-derive this table from it.

**The policy for when maintenance falls behind, because it will.** Three mechanisms, in order of how
much they carry:

1. **Automated liveness probes carry the cheap majority.** `maintenance_status` is derived weekly
   with no human in the loop ([§5.4](#54-absence-is-data)), so a human only looks at an entry when a
   signal actually changed.
2. **`last_verified` decays visibly.** A site-wide freshness indicator turns on automatically at 180
   days; at 12 months the entry is flagged in the interface and counted on the trust page (S9).
3. **At 24 months unverified, an entry enters an explicit lapsed state rather than silently
   persisting.** `curation.stewardship: current | lapsed` is the field that
   expresses it; it was requested by this document and is now defined in
   [04-data-model.md](04-data-model.md) §5. A `lapsed` entry stays
   visible and searchable, is labelled "not maintained by this index since <date>", is excluded from
   the verified fraction in `curation_confidence`, and is excluded from published gap claims. The
   reasoning is the whole of [§7.2](#72-failure-stated-equally-plainly)'s first bullet: the failure
   mode is not going stale, it is going stale invisibly, and an explicit lapsed state is the
   cheapest possible defence against becoming the next Ecosystem Graphs.

### 8.3 Implied artifact sizes, and the engineering consequence

**This overturns the earlier draft's "sharded output from day one" decision.** That decision was
made without measurement; measurement does not support it.

recon:tech measured a realistic 1,500-record corpus on 2026-09-17: the full corpus JSON is **0.52 MB
brotli** and the slim facet index **36 KB gzipped**, which is why sharding was rejected. The full
measurement table, its assumptions and its compression caveat are owned by
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.1 and are deliberately not
restated here — a measured table copied into two documents is a table that will disagree with itself
within one revision.

What this document does derive is what those figures mean at *our launch scale*. Scaling linearly to
the **320-family seed** (320/1,500 = 0.213): roughly **0.59 MB raw and ~0.11 MB brotli for the
corpus, with a facet index around 42 KB raw and ~8 KB gzipped.** At launch the entire faceting layer
is smaller than one photograph.

**Therefore: ship two unsharded JSON artifacts.** A slim `facets.json` loads with the filter UI and
drives instant client-side faceting; a full `corpus.json` loads lazily on entry to the comparison
workbench. A 0.5 MB brotli file is one HTTP request on a CDN. Sharding solves a problem this project
does not have, and it costs a permanently more complex build and a frontend that must reason about
which shard holds what.

Three consequences follow, and all three belong in
[08-infrastructure-and-build.md](08-infrastructure-and-build.md):

- **Result claims are the only entity with unbounded growth**, and they do not belong in
  `corpus.json`. At year-2 volumes (up to ~45,000 claims, mostly machine-ingested) a single claims
  file would be somewhere in the **18–32 MB raw** range *(my derivation from a ~400–700 byte record,
  not a measurement — verify before building)*. Split claims **per benchmark**, using the natural
  key, served statically alongside the detail page. That is a partition by meaning, not a shard by
  hash, and it never requires a client-side routing table.
- **SQLite stays a build-time-only artifact**, generated by Python, published as a downloadable
  data release at each commit. It is genuinely useful for our own analytics and as a citable
  artifact; it never ships to the browser. DuckDB-WASM was considered and rejected outright: its
  engine alone is **35.66 MB**, roughly 70× the entire dataset.
- **One landmine to record now.** Pagefind creates one `.pf_fragment` file per indexed page,
  Pagefind 1.5.2 has no option to group fragments (only an unmerged PR #1020), and Cloudflare caps a
  deployment at **20,000 files per version**. At the 320-entry seed that is roughly 700 files; at
  1,500 benchmarks ~3,100 files and fine; at **10,000 benchmarks ~20,200 files, landing almost
  exactly on the cap.** That is beyond year-2 steady state, so it is a recorded future constraint
  rather than a Phase-2 problem, and the mitigations when it arrives are a Cloudflare limit-increase
  request or Pagefind's Node API with fewer, larger custom records.

---

## 9. Why now

Six things changed in the ecosystem between mid-2025 and today, and together they make this both
possible and necessary in a way it was not eighteen months ago.

**1. The incumbent map-makers stopped.** Papers with Code — 9,327 benchmarks, the closest thing the
field had to a universal index — was sunset on **2025-07-24** and its benchmark layer was never
replaced; the domain now 301s to a paper feed. HELM entered maintenance mode on **2026-06-01**. The
HuggingFace Open LLM Leaderboard retired on **2025-03-14**. BIG-bench was archived on
**2026-04-17**. The successor slot is genuinely open, and it is open because the previous occupants
were owned rather than forkable.

**2. The non-language benchmark cultures reached scale, and remain unindexed at depth.** Matbench
Discovery (43 eligible models, training-data eligibility tiers), WeatherBench 2, Open Catalyst,
GEO-Bench 2, Grand Challenge (264 medical-imaging challenges with deadlines into 2027), the Virtual
Cell Challenge 2026, RoboArena and RoboCasa365 all exist *now*, at real scale, with real
participation. Some of them appear as names and links in one closed catalogue; **none of them is
indexed anywhere with lineage, evaluation conditions, metric definitions and access model as
structured fields** — the four-field test from [§1.5](#15-the-domains-outside-language-are-worse-served-still).
Five years ago this material was too thin to index. It is not thin any more.

**3. Regulation created demand with no supply.** EU AI Act GPAI obligations became enforceable
**2026-08-02** and require evaluation "using standard benchmarks and state-of-the-art tests" with
no registry defining what qualifies. NIST AI 800-2 ipd (Jan 2026), the UK's Centre for AI
Measurement at NPL (Jan 2026) and the 10-country International Network for Advanced AI Measurement
are all writing practices, not catalogues. A neutral, sourced, CC-BY benchmark registry is the
obvious missing reference artifact and a credible route to institutional adoption.

**4. A standards slot opened.** MLCommons Croissant became the adopted ML-dataset metadata standard
— HuggingFace emits it per dataset, Kaggle exports it, OpenML offers it, Google Dataset Search
crawls it — and it has **no evaluation or benchmark extension**. That gap will not stay open
indefinitely, and filling it converts this project from a website into a standard with free
distribution.

**5. A complement with institutional weight appeared.** Every Eval Ever (HuggingFace + University of
Edinburgh + EleutherAI, arXiv 2606.14516, CC BY 4.0) models **results** and explicitly does not
model benchmarks. That is a partnership shaped exactly like our gap, and it did not exist in June
2025. Adopting their `eval.schema.json` field names for shared conditions (`generation_args`,
`agentic_eval_config.available_tools`, `sandbox`, `metric_config`) is close to free and makes us
join-compatible with their registry on a stable shared id.

**6. AI assistance changed the curation economics.** Thirty to ninety minutes for a fully sourced
entry is what makes **320 entries** a part-time project rather than a funded one. Without that, this
plan would be a proposal for a grant, and grant-funded evaluation infrastructure has a 3–4 year
half-life.

**And the honest counter-pressure.** BenchmarkList launched **2026-07-15** and Benchmark Radar
published on **2026-09-10**. The window is visibly closing, and the correct response is not to race
them on count — which we would lose — but to occupy the ground they left vacant: open licensing,
verifiable provenance, non-language depth, lineage, and the refusal to rank. If a well-funded
competitor adopts CC-BY and cross-domain depth tomorrow, the differentiation thins considerably.
That risk is real, it is sized in [14-roadmap.md](14-roadmap.md), and it argues for shipping the
breadth proof — the **320-family seed with all 19 domain families non-empty**
([02-taxonomy.md](02-taxonomy.md) §3) — before polishing anything.

---

## 10. Where to go next

- **Why the competitive claims above hold, with evidence:**
  [01-landscape-and-positioning.md](01-landscape-and-positioning.md)
- **The eight facets and their vocabularies:** [02-taxonomy.md](02-taxonomy.md), then
  [03-taxonomy-build-process.md](03-taxonomy-build-process.md)
- **Entities, identity, provenance and validation tiers:** [04-data-model.md](04-data-model.md)
- **How curation actually happens, including the no-PR contribution path:**
  [05-repository-and-workflow.md](05-repository-and-workflow.md)
- **Where the data comes from and the legal posture:**
  [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) and
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)
- **Build, hosting, budgets:** [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
- **What it looks like and what it shows:** [09-design-system.md](09-design-system.md) and
  [10-visualization.md](10-visualization.md)
- **The lens, not the source:** [11-ai-features.md](11-ai-features.md)
- **Headroom, saturation, coverage, gaps:**
  [12-analytics-and-trends.md](12-analytics-and-trends.md)
- **The deferred execution layer:** [13-execution-runners.md](13-execution-runners.md)
- **Phases, exit criteria, effort, risks:** [14-roadmap.md](14-roadmap.md)
- **What is still undecided, with recommendations:** [15-open-questions.md](15-open-questions.md)

---

## 11. Provenance of the claims in this document

The project's own standard is that a confident number without a source is a liability. This section
applies that standard to this document. Three tiers, deliberately mirroring the shape of the
verification ladder in [04-data-model.md](04-data-model.md) §"The verification ladder":

- **`re-derived here`** — computed or checked during this revision pass, from files or from
  arithmetic shown in the text.
- **`recon-observed`** — a named reconnaissance report observed it live on 2026-09-17 (or
  2026-09-16 for the Epoch drop) and stated the method. Solid, but second-hand to this document.
- **`reported, not re-verified`** — the recon is quoting a paper, a vendor page or a third party. We
  have not seen the primary source. Anything in this tier that reaches the *product* needs a real
  `Source` record with an archive URL before it ships.

| Claim | Where used | Source | Tier |
| --- | --- | --- | --- |
| 2,315 arXiv papers / 670 abstract / 103 title, 7 days to 2026-09-17 | §1.1 | recon:sources, live arXiv API query (reproduced verbatim in §1.1) | recon-observed |
| ~60% precision / ~70% recall for regex benchmark-paper detection | §1.1 | recon:sources, hand-scored 40 abstracts | recon-observed |
| `falcon-7b` MMLU six-way 34% relative spread | §1.2 | recon:epoch-assets, read from `mmlu_external.csv` | recon-observed |
| BetterBench: 17 of 24 with no reproduction script; 24 benchmarks / 46 criteria | §1.2, §1.6 | arXiv 2411.12990, via recon:landscape | reported, not re-verified |
| Epoch condition-completeness ≥ 0.5 subset ≈ zero; mean ≈ 0.10 | §1.2, §5.3, §8 | recon:epoch-assets, column-level fill-rate analysis | recon-observed |
| Zero coverage of `chain_of_thought`, `temperature`, `judge_model`, `retries_allowed` in 6,598 rows | §1.2 | recon:epoch-assets | recon-observed |
| OSWorld / Terminal-Bench / SWE-bench / HELM variant lists | §1.3 | recon:landscape, recon:domains | recon-observed |
| FrontierMath: 42% of problems corrected, reissued 2026-06-12 | §1.3 | recon:domains, verified live 2026-09-17 | recon-observed |
| `superseded_by` populated on 2 of 81 Epoch rows | §1.3, §2.4 | recon:epoch-assets | recon-observed |
| Zero coverage for oversight-evasion / self-replication / AI R&D | §1.4 | arXiv 2605.16282 — already marked unverified inline | reported, not re-verified |
| Behavioural benchmarks 34/40 sandboxed, 28/40 rule-based | §1.4 | recon:landscape, secondary | reported, not re-verified |
| 19 families; 204 (family, subdomain) pairs; 44 capability terms; 13 groups; 247 and 8,976 cells | §1.4, §2.2 | [02-taxonomy.md](02-taxonomy.md) (owner); decisions D1, D3, D4 | re-derived here |
| Grand Challenge: 264 medical-imaging challenges | §1.5, §9 | recon:sources, counted via the public REST API | recon-observed |
| CAMEO weekly / CASP biennial; CASP17 target call open | §1.5 | recon:landscape | recon-observed |
| Matbench Discovery: 43 eligible models, eligibility tiers | §1.5, §9 | recon:landscape | recon-observed |
| LIBERO 130 tasks; RoboCasa365 365 tasks; Open X-Embodiment 22 embodiments / 500+ skills | §1.5 | recon:landscape, recon:domains | recon-observed |
| Open Catalyst OC22 and GEO-Bench 2 verified present in BenchmarkList | §1.5, §2.4 | recon:landscape, checked live 2026-09-17 | recon-observed |
| "Robotics is the single largest unindexed field; no central hub" | §1.5 | recon:landscape | recon-observed |
| Papers with Code: 9,327 benchmarks, sunset 2025-07-24, 301 redirect | §1.6, §9 | recon:landscape, redirect observed live | recon-observed |
| Ecosystem Graphs: last push 2025-01-24, no licence, 274★, 0 open issues | §1.6 | recon:landscape, GitHub API | recon-observed |
| Ecosystem Graphs still cited as a data source in 2025–26 research | §1.6, §7.2 | recon:landscape, citing arXiv 2510.01286 | reported, not re-verified |
| llm-leaderboard: 356★, 40 forks, self-deprecated for contribution friction | §1.6 | recon:landscape, repo + stated reason | recon-observed |
| HELM maintenance mode 2026-06-01 | §1.6, §9 | Verbatim from the HELM repo README, via recon:landscape | recon-observed |
| Open LLM Leaderboard retirement quote and date | §1.6, §4, §9 | HuggingFace's own retirement notice, via recon:landscape | reported, not re-verified |
| MedHELM spun out, Apache 2.0, stewardship by Pacific AI | §1.6, §5.5 | recon:landscape | recon-observed |
| Dynabench: last push 2026-02-11, 29★ | §1.6 | recon:landscape, GitHub API | recon-observed |
| AISafetyBenchExplorer withdrawn 2026-04-23; 137/195 stale repos; 165/195 English-only | §2.4, §6.2 | arXiv 2604.12875 — **withdrawn, no PDF available**; marked unverified at every use | reported, not re-verified |
| EU AI Act GPAI enforceable 2026-08-02, quoted wording | §1.6.1, §9 | recon:landscape | reported, not re-verified |
| NIST AI 800-2 ipd; UK NPL Centre; International Network (10 countries) | §1.6.1, §9 | recon:landscape | reported, not re-verified |
| OECD Catalogue disclaims vetting, excludes capability benchmarks | §1.6.1 | recon:landscape | reported, not re-verified |
| BenchmarkList: launched 2026-07-15, 2,545 / 1,604 / 24,074, closed, "Rosetta Stone" | §2.4, §9 | recon:landscape, site observed 2026-09-17 | recon-observed |
| Benchmark Radar: arXiv 2609.11115, 2026-09-10, 37 sources, 14,810 raw / ~1,283 curated, CC BY-NC-SA 4.0 | §2.4, §4, §9 | recon:landscape, paper + repo | recon-observed |
| Every Eval Ever: arXiv 2606.14516, 22,235 models, 2,273 benchmarks, CC BY 4.0 / MIT | §2.4, §9 | recon:landscape | recon-observed |
| Croissant adoption set; spec CC BY-ND 4.0; no benchmark extension | §2.4, §9 | recon:landscape, MLCommons repo | recon-observed |
| Overlap bands High / High / Complementary (~75 / ~70 / ~45) | §2.4 | recon:landscape — **the researcher's own judgement**, not a measurement; printed as a band in §2.4 and demoted to an analyst prior by [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §4, which owns the question | reported, not re-verified |
| ~300 Tier-1 / ~1,470 / 4,710 ceiling | §8 | recon:domains — expert judgement, **attributed as an estimate at use** (§8's opening sentence), not marked with the unverified marker. Column totals owned by [02-taxonomy.md](02-taxonomy.md) §3 | reported, not re-verified |
| Seed target 320; gates 290 / 144 / 130; floors 12 / 18 / 15 | §7.1 S8, §8 | Decision D2, allocation owned by [02-taxonomy.md](02-taxonomy.md) §3 | re-derived here |
| Epoch counts: 81 / 80 / 6,598 / 828 / 1,063 / 2,760 | §8.1 | recon:epoch-assets, counted from the local drop on 2026-09-16; **`epochdl/` is absent from the current tree, so not re-counted in this pass** | recon-observed |
| Curation 175–495 h; project 490–1,080 h; 24–54 weeks; six to twelve and a half months | §8.2 | Decision D2; breakdown owned by [14-roadmap.md](14-roadmap.md) §"Effort sizing". Note that 14's *phase-table* serial sum (26–57 wk, six to thirteen months) is a different figure from the same document and the two are not interchangeable | re-derived here |
| Manual sweeps 126–169 h/year | §5.4, §8.2 | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §6 owns it; restated here, not derived here | recon-observed |
| Standing maintenance 327–662 h/year, 6.5–13.2 h/week | §8.2 | **My derivation** from the four lines shown, at a 50-week year; marked unverified inline | re-derived here |
| Corpus 2.76 MB raw / 0.52 MB brotli; facet index 198 KB / 36 KB gzip | §8.3 | recon:tech, measured 2026-09-17 | recon-observed |
| 320-seed sizes ~0.59 MB raw / ~0.11 MB brotli / ~8 KB gzip | §8.3 | Linear scaling of the above, shown in the text | re-derived here |
| Claims file 18–32 MB raw at year 2 | §8.3 | **My derivation** from a 400–700 byte record; marked unverified inline | re-derived here |
| DuckDB-WASM engine 35.66 MB | §8.3 | recon:tech | recon-observed |
| Cloudflare 20,000 files/version; Pagefind one fragment per page; PR #1020 unmerged | §8.3 | recon:tech, Cloudflare docs + Pagefind 1.5.2 CLI option list | recon-observed |
| Brute-force cosine 0.75 ms at 1,500 × 384 (conservative upper bound) and 0.61 ms at the shipped 1,500 × 256, Node v24.11.0 / V8; int8 loop slower at 2.0 ms | §5.6 | recon:tech, measured in-session 2026-09-17; [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5 owns the timings | recon-observed |
| model2vec has no JS package (recon:ai-features) vs. hand-portable in ~150 lines (recon:tech) | §5.6 | **The two reports disagree; both positions stated in the text** | recon-observed |
| AI layer ~$23/mo at 1k queries, ~$184/mo at 10k | §4.1 | recon:ai-features — prices verified, **token counts are the researcher's estimates** | reported, not re-verified |
| Cloudflare static asset requests unbilled; GitHub Actions free for public repos | §4.1 | recon:tech, vendor billing docs | recon-observed |
| Workers Rate Limiting binding is per-colo, 10s/60s periods only | §4.1 | recon:ai-features, Cloudflare docs | recon-observed |
| Wayback SPN2 limits 12 concurrent / 100,000 per day / 10 per URL per day | §5.1 | recon:sources — from IA's public spec doc, **mirrored not re-read**; marked unverified inline | reported, not re-verified |
| Availability API returned 429 on a cold request; CDX works | §5.1 | recon:sources, observed live | recon-observed |
| Perma.cc free tier 10 links/month | §5.1 | recon:sources | recon-observed |
| UK AISI `inspect_evals` `/register/` launched 2026-05-08; issue → bot → auto-PR | §5.5 | recon:landscape, repo observed 2026-09-17 | recon-observed |
| Validation bot behaviour (~1 minute, rendered YAML, `Co-authored-by:`, never merges) | §5.5, §7.1 S5 | [05-repository-and-workflow.md](05-repository-and-workflow.md) §"The validation bot" | re-derived here |
| Reviewer-recruitment communities, credit-as-currency, 8–20 h budget, 7 targeted / 3 gate | §7.3 | [14-roadmap.md](14-roadmap.md) §"Domain reviewer recruitment" | re-derived here |
| Cold-outreach response rate for unknown projects | §7.3 | **No source. Stated as unknown.** | — |
| `maintenance_status` derivation, probe signals, 30-day quarantine, `unobservable` | §5.4 | [02-taxonomy.md](02-taxonomy.md) §`maintenance_status` | re-derived here |
| `curation_confidence` formula and the three kinds of empty | §5.4 | [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3–5.4 | re-derived here |
| Learned-entrant test and its worked cases | §6.1 A5 | [15-open-questions.md](15-open-questions.md) §A3 | re-derived here |
| 90/180-day succession trigger ordering | §5.5 | Settled in this pass: succession at 90 days, staleness banner at 180. [05-repository-and-workflow.md](05-repository-and-workflow.md) §"What happens when we stop" owns it; [01](01-landscape-and-positioning.md), [08](08-infrastructure-and-build.md) and [14](14-roadmap.md) already agreed on the 180-day banner | re-derived here |

Two honest notes about this table. It does not make the claims true; it makes them **checkable**,
which is the only property this document can supply on its own. And roughly a third of the rows sit
in `reported, not re-verified` — which is exactly the proportion a reader should expect from a
planning document written against a week-old reconnaissance pass, and exactly the proportion that
must fall before any of these figures appears on the site as data rather than as prose.
