# 12 -- Derived Analytics and Trends

Every metric in this document is computed by the build pipeline from committed data, written to
`build/derived/`, and traceable to the individual claims that produced it. No derived number is
hand-maintained, because anything hand-maintained drifts out of date and quietly becomes a lie.
That is not a stylistic preference. Stanford CRFM's Ecosystem Graphs is still cited as a data source
by 2025-26 research while its last push was 2025-01-24 -- roughly twenty months stale -- so stale
curation is actively propagating errors into the literature right now
([01-landscape-and-positioning.md](01-landscape-and-positioning.md)). A hand-typed "saturated" flag
or a hand-typed coverage percentage has exactly that failure mode with none of the visibility.

This document specifies what gets computed, from what, with which caveats, and -- equally important
-- what will never be computed at all.

---

## 1. The framing: derived data is a function, not a record

### 1.1 The contract

```
data/**/*.yaml   (source of truth, CC-BY, citable at a commit SHA)
      |
      | pure function, deterministic, no network, no hand edits
      v
build/derived/*.json   (build artifact, regenerated from scratch every build)
      |
      v
site + two shipped JSON artifacts (slim facet index, full corpus)
```

Four rules govern the boundary, and CI enforces all four:

1. **Derived values are never written back into `data/`.** A curator can hand-set
   `lifecycle: deprecated` because that is a judgement with evidence. A curator can never hand-set
   `lifecycle: saturated`, because saturation is defined quantitatively in [02-taxonomy.md](02-taxonomy.md)
   and computed here. If a derived value appeared in the YAML it would be a second source of truth,
   and the two would diverge within a month.
2. **Recompute everything, every build.** The full corpus measures 2.76 MB raw and 0.52 MB brotli
   ([08-infrastructure-and-build.md](08-infrastructure-and-build.md)), so a total recompute costs
   seconds. There is no incremental derived cache and there never will be. Incremental derived state
   is how a derived layer silently desynchronises from its inputs, and at this data size the
   optimisation buys nothing.
3. **Every derived file records its inputs.** `build/derived/manifest.json` carries the data commit
   SHA, the taxonomy version, the schema version, the Python and library versions, the content hash
   of the concatenated input tree, the wall-clock build time, and -- per metric -- the verification
   threshold, date window and cohort definition used. A figure without those parameters is not
   reproducible and is therefore not publishable.
4. **Determinism is a CI gate.** The build runs twice on the same input and the two `build/derived/`
   trees must be byte-identical apart from the manifest's timestamp field. This is the same posture
   the Atlas layout takes, where CI is the sole authority permitted to write `atlas.json` because
   UMAP reproducibility is guaranteed across runs but not across machines
   ([08-infrastructure-and-build.md](08-infrastructure-and-build.md)).

### 1.2 The artifact layout

| Path | Contents | Consumed by |
| --- | --- | --- |
| `build/derived/headroom.json` | Per benchmark-version-metric: anchors, SOTA, headroom, null reasons | V3 Saturation Wall, V5 Comparison Workbench, V6 detail pages |
| `build/derived/saturation.json` | Bands, velocity, time-to-saturation with censoring | V3, V4 Frontier Timeline |
| `build/derived/coverage.json` | Domain x capability density at two grid resolutions | V2 Coverage Map |
| `build/derived/gaps.json` | Ranked gap cells with every input factor exposed | V7 Gap Finder |
| `build/derived/adoption.json` | Distinct systems, orgs, reporting velocity, citations | V1 Atlas node size, V6 |
| `build/derived/liveness.json` | Observed staleness signals per benchmark | V6, lifecycle warnings |
| `build/derived/hygiene.json` | Verification mix, condition completeness, dispute and correction rates | The public hygiene dashboard |
| `build/derived/ecosystem/*.json` | The ecosystem series in section 9 | V9 Ecosystem view |
| `build/derived/manifest.json` | Inputs, parameters, versions, hashes | Every "cite this figure" block |
| `build/index.sqlite` | Build-time query artifact and citable data release | Our own analysis; never shipped to the browser |

SQLite stays build-time only. It is enormously useful for gap scoring and coverage queries, and a
`.sqlite` at a commit hash is a good citable release artifact, but it never reaches a client --
DuckDB-WASM's engine alone is 35.66 MB, roughly seventy times the entire dataset
([08-infrastructure-and-build.md](08-infrastructure-and-build.md)).

### 1.3 Two data tiers feed the analytics, and they are not equal

The result corpus is deliberately segregated. `data/claims/` holds hand-curated claims.
`data/claims/_ingested/epoch/` holds the roughly 6,598 rows ingested in bulk from Epoch AI's CC-BY
export, each carrying `curation.verification_status: machine-ingested` and an honestly computed
`condition_completeness` that we expect to average around 0.10
([04-data-model.md](04-data-model.md), [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)).

Every derived metric declares which tier it consumes:

- **Coverage, adoption, liveness and ecosystem series** consume both tiers. Breadth is the point, and
  a machine-ingested claim still proves that somebody evaluated something on that benchmark.
- **Headroom, saturation and any comparison** consume only claims at or above the verification
  threshold *and* above a condition-completeness floor -- `frontier_floor` for the SOTA line,
  `comparison_floor` for anything placed side by side (section 1.4). The bulk data provides coverage -- which is
  exactly what the user asked for, a great searchable collection -- without polluting comparison,
  which is where credibility lives.

The threshold and the floor are parameters, shown next to every number, adjustable by the reader,
and recorded in the manifest. A metric whose filter is invisible is a metric nobody can check.

### 1.4 The two completeness thresholds, declared here and referenced by name everywhere else

Two different questions need two different floors, and the plan previously carried four literal
numbers (0.3, 0.35, 0.4, 0.5) across five documents for what were really only two constants. They are
declared once, here, and live in `taxonomy/thresholds.yaml` so that a recalibration is one edit and
one CI-checked file rather than a grep:

```yaml
# taxonomy/thresholds.yaml -- owned by 12-analytics-and-trends.md section 1.4
frontier_floor:    0.30   # minimum condition_completeness for a claim to set the SOTA / frontier line
comparison_floor:  0.40   # minimum condition_completeness for a claim to appear in a side-by-side
```

They differ because they answer different questions. `frontier_floor` asks "is this claim specified
well enough to stand as the best known result", where the cost of excluding a real record is a
headroom number that is too low and visibly so. `comparison_floor` asks "may this claim be placed
beside another one", where the cost of including an under-specified record is a comparison that looks
like an answer and is not — the failure this project exists to refuse. The stricter bar therefore
belongs on the comparison side.

Both values are starting points, not measurements. Nothing has yet measured the completeness
distribution of hand-curated claims, and the Epoch ingest tells us only about the machine-ingested
tier (a mean near 0.10, [04-data-model.md](04-data-model.md)). Recalibrate both once ~200
hand-curated claims exist, and record the recalibration as an ADR
([03-taxonomy-build-process.md](03-taxonomy-build-process.md)) so the change to every published
figure is dated and attributable.

**No document restates these values.** [05-repository-and-workflow.md](05-repository-and-workflow.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md),
[10-visualization.md](10-visualization.md) and [11-ai-features.md](11-ai-features.md) all reference
them by name. A threshold typed as a literal in five places is a threshold that will be calibrated in
one of them and diverge in the other four, at exactly the moment the number starts to matter.

---

## 2. The cross-domain problem

A GDT-TS of 92 on a CASP target and an MMLU accuracy of 0.89 are not comparable, and no amount of
normalisation makes them so. The obvious move -- collapse everything into a single "AI capability
index" -- is the one thing that would most damage this project's credibility, because it manufactures
a comparison that does not exist and hides exactly the detail the index was built to expose.

This is not a hypothetical temptation. Four separate operators have already yielded to it:

| Composite | Operator | Construction | Why we do not copy it |
| --- | --- | --- | --- |
| Epoch Capabilities Index (ECI) | Epoch AI | 2-parameter IRT/Rasch latent-ability fit over a sparse 58-benchmark x 266-model matrix, 500 bootstrap resamples, 90% CIs, affinely anchored so Claude 3.5 Sonnet = 130 and GPT-5 = 150 | Statistically respectable and honestly documented, but it assumes a single latent ability dimension. That assumption is defensible inside 58 LLM benchmarks and indefensible across protein folding, weather and manipulation. |
| Experimental Capability Index | BenchmarkList | "Rosetta Stone method" aligning overlapping benchmark results onto one scale | Closed as of 2026-09-17: no licence statement and no method paper were found, so there is nothing to audit. The same single-axis assumption with none of Epoch's disclosure. |
| Intelligence Index | Artificial Analysis | Published composite over ~10 evals plus cost and speed axes | Commercial product; redistribution contractually barred, so we can only ever link to it. |
| CPS, EPDMS, NDS, VBench total | Matbench Discovery, NAVSIM v2, nuScenes, VBench | Within-domain weighted composites (Matbench Discovery's CPS is F1 50% / RMSD 10% / kappa 40%) | These are legitimate *within* a domain, defined by the domain's own maintainers. We record them as the benchmark's declared metric. We never extend them across domains. |

Every description in that table is a reading of a third party's published method **as of
2026-09-17**, not a re-derivation: nobody here has refitted the ECI or reproduced the CPS.
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §2 owns the ecosystem snapshot and
the dating convention — a statement about a named live service is a snapshot, never a permanent
property of it. The ECI anchor values in particular (Claude 3.5 Sonnet = 130, GPT-5 = 150) are
reported rather than checked, and [02-taxonomy.md](02-taxonomy.md) marks them *(unverified -- confirm
before relying on this)*; that marking governs here too. Licence terms are owned by
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8 with evidence grades and as-of dates
attached, and the Artificial Analysis redistribution bar is read from their published terms on the
same date.

The argument against a universal index does not rest on our taste. The biggest ranking operator in
open-source AI retired its own ranking and said why: HuggingFace shut the Open LLM Leaderboard on
2025-03-14, after 13,000+ models, stating that it "was becoming obsolete and could encourage people
to optimize in irrelevant directions." That is the strongest available external validation of a
refusal to rank, and it belongs on the methodology page verbatim.

**The one legitimate cross-domain axis is headroom consumed** -- position between a baseline and a
ceiling that are both defined *inside* the benchmark's own domain. It says nothing about difficulty,
importance or generality. It says only how much of a defined distance has been travelled.

---

## 3. Headroom

### 3.1 The formula

```
headroom_consumed = (sota - baseline) / (ceiling - baseline)
```

Stored **unclamped**. A value above 1.0 means the system has passed the anchor, which is one of the
most interesting facts a record can carry, and clamping would erase it. OSWorld publishes a 72.4%
human baseline while top-5 2026 runs reach 73.1-82.6%, so the honest derived value for the leader is
`headroom_consumed: 1.14, exceeds_ceiling: true`, rendered as "human anchor surpassed" rather than as
a full bar. Cybench moved from 17.5% at launch to roughly 93% for frontier models in 2026; GAIA's
~92% human figure and WebArena's human baseline are now within a few points of the frontier. A metric
that silently pins those at 1.0 destroys the single most newsworthy pattern in the data.

### 3.2 The anchors, and where their vocabularies live

**This document owns neither vocabulary and does not restate either.** The ceiling side is the
`ceiling_anchor_type` facet, ten terms, owned by [02-taxonomy.md](02-taxonomy.md) §7. The entity that
stores an anchor is `Baseline`, whose `kind` enum is owned by [04-data-model.md](04-data-model.md)
§7 and covers floors as well as ceilings. An earlier draft of this section printed a third
vocabulary of its own invention -- `replicate-experiment` against `02`'s `experimental-replicate`,
`measurement-ceiling` against `measured-ceiling` -- which meant a headroom number computed from this
document's prose used terms the schema could not store. That is precisely the unsourced confident
number the project exists to oppose, and the fix is to stop having a vocabulary here at all. The
worked examples below use the owners' terms and nothing else.

`baseline` is the *floor* -- what a system that has learned nothing about the task achieves. The
floors are the `Baseline.kind` members that `02` §7's ceiling facet deliberately does not carry
(`random-chance`, `classical-algorithm`, `field-practice-reference`) plus an explicit empty floor:

| Floor, in `Baseline.kind` terms | What it is here | Example |
| --- | --- | --- |
| `random-chance` | Uniform guessing over the answer space | GPQA Diamond 0.25; PIQA and Winogrande 0.5; HLE 0.048; SimpleBench 0.1667 (all read from Epoch's `random_baseline` column, non-zero on 21 of its 81 benchmarks) |
| `classical-algorithm` | A non-learned or pre-deep-learning reference | Climatology and persistence forecasts in WeatherBench 2 and ChaosBench; the cell-context mean in the Virtual Cell Challenge |
| `field-practice-reference` | What practitioners in the field currently achieve without AI | The trivial-symbolic bot floor in NetHack |
| (no baseline record) | Genuinely zero -- generation or resolution tasks with no free credit | SWE-bench resolve rate; most success-rate benchmarks |

`ceiling` is the *reference frontier*, and it is the anchor that most often goes wrong. The ten terms
are `02` §7's; four of them carry most of the corpus and are worth an example each:

| `ceiling_anchor_type` ([02](02-taxonomy.md) §7) | What it is here | Example |
| --- | --- | --- |
| `expert-average` / `expert-best` | The designated primary human `Baseline` record | GPQA Diamond PhD experts ~65-74%; GAIA ~92%; OSWorld 72.4% |
| `crowd-average` | Non-expert human performance where that is the relevant comparison | ForecastBench's public crowd; MLE-bench's real Kaggle medal distribution |
| `experimental-replicate` | A repeat of the physical measurement | Virtual Cell Challenge 2026, where each of six metrics is scaled between the cell-context mean and a real wet-lab replicate |
| `operational-system` | A deployed non-AI system that is the frontier a learned model is trying to reach | ECMWF IFS HRES/ENS for WeatherBench 2 |
| `measured-ceiling` | The highest score the instrument can produce, for reasons unrelated to human ability | Epoch's `score_ceiling`, below 1.0 on exactly three of its benchmarks: FrontierMath 0.57, FrontierMath Tier 4 0.60, LMCA 0.85 |
| `theoretical-maximum` | A hard mathematical bound | Exact-match accuracy of 1.0; symbolic-equivalence rate in SRBench |

**The operational forecast is a ceiling, not a floor, and the plan has to say so once.** An earlier
draft of this section put ECMWF's IFS/ENS on the baseline side while `02` records WeatherBench 2 as
`ceiling_anchor_type: operational-system`, which made headroom for that benchmark the reciprocal of
itself depending on which document you read. `02` is right: IFS/ENS is what a learned forecaster is
trying to beat, so it is the reference frontier. The genuinely non-learned floor for weather is
climatology and persistence, which are `classical-algorithm` in the table above. Where a domain has
both an operational incumbent and a naive reference, both are stored and the primary is designated;
the alternative-anchor list under the bar makes the choice visible.

One reconciliation is still owed and it belongs to `04`, not here: `Baseline.kind` has no
`noise-ceiling`, so Brain-Score -- the benchmark `02` §7 names as the sole reason that term exists --
cannot currently be stored as a `Baseline` record. Until `04` carries it, Brain-Score's headroom is
`null` with reason `no-baseline-established`, which is an honest failure but the wrong one.

**A measured ceiling is not a human baseline, and conflating the two is a real error.** Epoch's
`score_ceiling` reflects problem-set properties, not what a person can do. The schema keeps them as
separate fields, the derived record names which kind it used, and the UI prints the anchor type next
to the bar. Where multiple baselines exist -- and multiple baselines are normal: crowd average,
expert average, expert best, theoretical max -- headroom uses the designated `primary_baseline`, the
choice is recorded, and the alternatives are listed underneath so a reader can see what a different
choice would do.

### 3.3 The SOTA side

`sota` is the highest value among claims that satisfy **all** of:

- the same benchmark **version**, metric and subset. A score against "FrontierMath" without a version
  is now meaningless -- Epoch reissued a corrected FrontierMath on 2026-06-12 after finding errors in
  42% of problems;
- `verification` at or above the threshold, defaulting to `maintainer-verified`, user-adjustable,
  default stated on the page;
- `condition_completeness` at or above **`frontier_floor`** (section 1.4), never a literal;
- the claim is not `disputed` and not superseded by a later claim about the same run.

Where the qualifying set is empty but lower-verification claims exist, headroom is `null` with reason
`no-qualifying-claim`, and the page shows the best unqualified claim greyed out with its verification
badge. Hiding it would be dishonest; promoting it would be worse.

### 3.4 When headroom is not computed, and why the null is a finding

Headroom is computed **only when both anchors exist and are sourced.** Otherwise it is `null` with an
explicit machine-readable reason, rendered as text rather than as a blank:

| Null reason | Rendered as | Why it matters |
| --- | --- | --- |
| `no-baseline-established` | "No baseline established" | A benchmark with no human or reference baseline cannot tell you whether a score is good. This is the most common null and it is a genuine finding about the field's reporting norms. |
| `unbounded-metric` | "Metric has no upper bound" | Kaggle Game Arena Elo; Atari-100k human-normalised score, which runs above 100%; Vending-Bench 2 scored in dollars (11,181.87 for the leader); METR Time Horizons scored in minutes |
| `lower-is-better-optimum-zero` | "Optimum is zero, not maximum" | WMDP, where lower is safer; BBQ, where the target is zero bias and the result is a pair of numbers |
| `vector-valued-by-design` | "No aggregate exists" | VBench's 16+ dimensions; ReXrank, which deliberately publishes eight metrics and no aggregate; WeatherBench 2, whose authors state it is "a tool to compare different approaches on different aspects", not a challenge with one ranking |
| `relative-rating-only` | "Rating is pool-relative" | RoboArena's double-blind pairwise policy comparisons; any Elo |
| `resolution-pending` | "Ground truth not yet resolved" | ForecastBench and Metaculus FutureEval, where questions resolve months to years after submission |

WeatherBench 2 deserves emphasis. A canonical, well-funded benchmark whose maintainers explicitly
refuse to produce a single ranking is the strongest external validation of this project's
comparability thesis that exists in the wild, and it should be cited on the methodology page.

### 3.5 The caveats, displayed with the number and not in an appendix

- **Linearity between anchors is frequently false.** The last five points of a benchmark are usually
  far harder than the first five. FATE's open provers reach roughly 50% on FATE-M, 3% on FATE-H and
  0% on FATE-X; CritPt's best base model sits near 4%, rising to about 10% with code tools. A
  headroom of 0.5 on one benchmark and 0.5 on another do not represent equal remaining effort.
- **The result is sensitive to the choice of ceiling.** Swap GPQA's "PhD expert" anchor (~65-74%) for
  its "skilled non-expert with web access" anchor (~34%) and the headroom of every claim changes
  dramatically. The alternative-anchor list under the bar exists so this is visible rather than
  arguable.
- **Headroom measures distance travelled, never difficulty or importance.** A saturated toy benchmark
  and a saturated field-defining benchmark both read 1.0.

These three sentences appear on the page, next to the chart. A caveat in a methodology appendix that
nobody reads is a caveat that does not exist.

---

## 4. Saturation

### 4.1 Bands

```
saturation_band:
  emerging   = headroom < 0.25
  contested  = 0.25 <= headroom < 0.75
  closing    = 0.75 <= headroom < 0.95
  saturated  = headroom >= 0.95
```

The minimum-evidence threshold for any `closing` or `saturated` verdict is set in
[02-taxonomy.md](02-taxonomy.md) §8 and is not redefined here: **at least 3 claims at verification
level `maintainer-verified` or above, from at least 2 independent sources**. Below that,
`headroom_status: insufficient-evidence` and no lifecycle transition is derived.

`lifecycle: saturated` in [02-taxonomy.md](02-taxonomy.md) is driven by this computation rather than
by hand, so the status cannot go stale. The band boundaries are arbitrary and are declared as such;
the underlying continuous value is always available and the bands exist only for filtering and
colour.

### 4.2 Saturation velocity

Change in headroom per month over a trailing 12-month window, computed as an ordinary least-squares
slope over the **frontier series** -- the running maximum of qualifying claims ordered by
`date_reported`.

**The statistical caveat that must ship with it:** a running maximum cannot decrease, so this slope
is non-negative by construction. It measures how fast the record is falling, not how the field as a
whole is performing, and it says nothing about the median system. The Saturation Wall sorts on it;
the tooltip says what it is.

Velocity is computed only where at least four qualifying claims exist in the window. Below that a
slope is a line through noise, and the field reports `insufficient-data` rather than a number.

### 4.3 Time-to-saturation, and the survivorship problem

Months from benchmark release to the first qualifying claim at headroom >= 0.95. Plotted against
release year, this produces what is likely the project's single most communicative chart: the
shortening lifespan of benchmarks over time.

It is also the chart most likely to be wrong, because it is computable only for benchmarks that
saturated. Benchmarks that never saturate are excluded, which biases the median downward, and the
bias grows with recency because recent benchmarks have had less time to saturate.

**The fix is standard and we should use it rather than inventing one:** treat unsaturated benchmarks
as right-censored observations and report a Kaplan-Meier survival curve per release-year cohort, with
censored observations drawn as tick marks and `n_censored` printed beside every median. The headline
number becomes "median time to saturation for the 2023 cohort: 19 months (n = 41, 12 censored)"
rather than a bare mean over survivors. The archive draft was right that the censored population must
be shown alongside; this specifies how.

Two further honesty requirements:

- **Saturation is a lifecycle stage, not a death.** BIG-bench was archived on 2026-04-17 with
  BIG-Bench Hard near-saturated, but SWE-bench is saturating while remaining the most-used coding
  benchmark in the field. The chart must not imply that saturated means abandoned. Liveness
  (section 7) is a separate axis and the two are plotted separately.
- **Our own coverage biases the curve.** We catalogue famous benchmarks first, and famous benchmarks
  are disproportionately the ones that got attacked hard enough to saturate. The cohort definition
  and the `curation_confidence` for each release year print on the chart.

---

## 5. Coverage density and the gap score

### 5.1 The grid problem, which the earlier draft missed

The taxonomy ([02-taxonomy.md](02-taxonomy.md)) has 19 domain families spanning **204
(family, subdomain) pairs** and **44 capability terms**. State the convention with the number, because
there are two of them — pairs and bare leaf slugs — and a reader cannot tell which a percentage was
computed from. Since D3.5 renamed the games-planning leaf `puzzle-solving` to `puzzle-games`, **the
two conventions agree: 204 (family, subdomain) pairs over 204 distinct leaf slugs**
([`_workflow/decisions/D3-vocabulary-namespacing.md`](_workflow/decisions/D3-vocabulary-namespacing.md),
applied; [02-taxonomy.md](02-taxonomy.md) §3 owns both counts). The grid is still indexed by the
pairs, because domain is a two-level facet and a matrix row is a navigational position rather than a
bare word, but nothing now turns on the distinction. The naive fine matrix is therefore
**204 x 44 = 8,976 cells**. (These counts are generated by `scripts/taxonomy_stats.py` from
`taxonomy/*.yaml` and CI fails if this document and 02 disagree.)

Occupancy is a function of corpus size, and the percentages below move with it, so they are written
as a function rather than as a headline. At the canonical seed target of 320 Tier-1 benchmark
families -- [02-taxonomy.md](02-taxonomy.md) §3 owns the per-family allocation and this document does
not restate it -- with each benchmark carrying **4.2** capability tags on average, measured against
the ten worked classifications in [02-taxonomy.md](02-taxonomy.md) §12 rather than assumed, there are
at most 320 x 4.2 = ~1,344 occupied (subdomain, capability) pairs. **At least 85% of that matrix is
empty by arithmetic before a single curation decision is made** (~89% at the
three-tags-per-benchmark rate the earlier draft assumed, which is the figure quoted in
[`_workflow/decisions/D1-capability-groups.md`](_workflow/decisions/D1-capability-groups.md) §4).
Every figure here is an *upper bound* on occupancy, because two benchmarks can land in the same cell
and the arithmetic does not deduplicate.

[00-vision-and-scope.md](00-vision-and-scope.md) §8 owns the corpus-size horizons and this document
reads them rather than restating them. Against that column the fine grid stays mostly empty for
years:

| Corpus size ([00](00-vision-and-scope.md) §8) | Occupied fine cells, upper bound | Fine grid empty |
| --- | --- | --- |
| 320 families (v1) | ~1,344 | **>= 85%** |
| 500--700 families (twelve months post-launch) | ~2,100--2,940 | **67--77%** |
| 1,200--1,500 families (steady state, year 2) | ~5,040--6,300 | **30--44%** |

An earlier draft attached "roughly 44% empty" to a "12-18 month target of ~1,200 families" that
`00` §8 puts two horizons further out, so the plan carried a figure that was right for year two and
labelled for year one. The lesson is the general one: an emptiness percentage is meaningless without
the corpus size it was computed from printed beside it, and the site prints both.

A gap finder that reads empty cells off that grid is a random-number generator with a heatmap on top.
This is the failure mode that would most embarrass the project, because gap analysis is
differentiator #3 and a reviewer from any specialist field will check the cells they know.

**The fix:** two grid resolutions, with the coarse one as the default and the only one permitted to
produce published gap claims.

| Grid | Rows x columns | Cells | Incidences at the 320-entry seed | Mean per cell | Use |
| --- | --- | --- | --- | --- | --- |
| Coarse (default) | 19 domain families x 13 capability groups | **247** | ~1,056 (~739 if only 70% of entries reach `full` completeness) | ~4.3 (~3.0) | Published coverage map, gap ranking, all external claims |
| Fine (drill-down) | 204 (family, subdomain) pairs x 44 capability terms | **8,976** | ~1,344 | ~0.15 | Exploration only, inside an already-dense coarse cell |

The coarse figures multiply 320 entries by the **3.3-group collapse factor** -- the mean number of
distinct capability groups a benchmark's 4.2 terms roll up into, measured against the ten worked
classifications in [02-taxonomy.md](02-taxonomy.md) §12 and reconciled with the canonical seed total
in [`_workflow/decisions/D1-capability-groups.md`](_workflow/decisions/D1-capability-groups.md) §4.
That factor is the weakest input in this section and it should be treated as such: it rests on ten
adversarially chosen benchmarks with no language, code or safety-alignment representation among them,
so it could move by a third *(unverified -- confirm before relying on this)*. Re-validate it against
real tag co-occurrence at ~200 entries at `full` completeness, **before Phase 3 publishes the coverage
map**, not after. Secondary domains at the published 0.5 weight lift every coarse figure above by
roughly 40%.

The 13 capability groups are a documented rollup of the capability facet -- a strict partition of
all 44 terms, each term in exactly one group -- **enumerated by id, label, definition and member
terms in [02-taxonomy.md](02-taxonomy.md) §4.3**, stored as `taxonomy/capability_groups.yaml` and
governed by the same ADR process as every other vocabulary change
([03-taxonomy-build-process.md](03-taxonomy-build-process.md)), extended so that *moving* a term
between groups also requires an ADR and not only adding or removing one. The member lists are not
restated here. 02 owns them, and the reason this document previously asserted a twelve-group rollup
and cited a §4.3 that did not exist is that the number was typed into prose instead of read out of
the vocabulary -- the exact drift mechanism this plan is supposed to be immune to. The group axis is
**derived and never hand-tagged**: curators tag capability terms and the rollup is computed, which is
why the inter-annotator agreement bar in [03-taxonomy-build-process.md](03-taxonomy-build-process.md)
§6 is scored on terms and not on groups. `capability_groups.yaml` carries a version, that version is
recorded in `build/derived/manifest.json`, and it is cited with every published coverage figure,
because a re-grouping silently re-shapes every gap claim in the affected columns without changing a
single benchmark record. The fine grid is reachable but carries a permanent banner stating its
expected occupancy under a null model, so a reader can see what "empty" looks like by chance before
concluding that it looks like a gap.

Three properties of these grids have to travel with every coverage figure, because they are the
things a reader will otherwise assume wrongly and each one is a published-error waiting to happen.

**The coarse grid counts benchmarks per group, not tags.** A benchmark tagged four capability terms
that all roll into one group occupies one coarse cell and four fine cells, so "how much is measured
here" has two correct answers and **the coarse total is not the row sum of the fine grid**. The
methodology page says so in those words; without it, the first person to add the two up publishes a
discrepancy as a bug report against our arithmetic.

**Every cell tooltip decomposes its count by member term**, never reporting the group total alone.
This is not presentational politeness. `communication` carries the base rate of four separate
subdomains inside `conduct-and-cooperation`, and `distribution-shift-generalization` is the
most-applied term in the whole corpus inside `robustness-and-stability`, so a group total can read
"covered" while `honesty`, `harm-avoidance`, `adversarial-robustness` and `reliability-consistency`
sit at zero underneath it. A rollup that hides the terms it buries converts differentiator #3 into a
claim about our column design.

**Four of the 8,976 fine cells are tautological and are excluded from the analysis entirely.** Where
a subdomain leaf and a capability term are the same word -- `planning`, `spatial-reasoning`,
`temporal-reasoning`, `compositional-generalization`, declared in `taxonomy/homographs.yaml` and
ruled on in
[`_workflow/decisions/D3-vocabulary-namespacing.md`](_workflow/decisions/D3-vocabulary-namespacing.md)
-- the cell is occupied by construction and is uninformative full *and* empty: full it reports the
tagging convention, empty it reports that the row has no entries at all. Those four cells are
excluded from gap ranking and from both sides of every coverage percentage. No coarse cell is
tautological, because no domain-family slug collides with any capability term.

At maturity the coarse grid is dense and the fine grid is not, which is the entire reason for keeping
two resolutions rather than one. 1,500 benchmark families at the 3.3 collapse factor give ~4,950
incidences over 247 coarse cells, a mean of **20.0**; the same corpus gives ~6,300 incidences over
8,976 fine cells, a mean of **0.70**. A coarse cell still empty at a mean of 20 is a finding worth
publishing. A fine cell empty at a mean of 0.70 is the default state of the grid, and that asymmetry
is why only the coarse grid may produce a published gap claim.

### 5.2 Coverage density

Per coarse cell:

```
density = SUM over benchmarks of ( domain_weight * quality_weight )

domain_weight:
  primary domain match       1.0
  secondary domain match     0.5    # matches [02-taxonomy.md] section 11 rule 1; two secondaries = one primary
  subset-derived match       0.5

quality_weight, multiplicative, clamped to [0.5, 1.5]:
  verification_status primary-source-verified   x1.2
  verification_status machine-ingested          x0.7
  activity signal within 18 months              x1.1
  no activity signal in 18 months               x0.8
  human baseline present                        x1.1
  sourced release date                          x1.05
```

Subset-derived matching is what lets MMLU's college-chemistry subject count as chemistry coverage
rather than as pure language coverage -- a distinction that materially changes the gap analysis, and
one of the concrete reasons `Subset` is a first-class entity in [04-data-model.md](04-data-model.md).

Three toggles ship with the map, because they answer different questions: **raw count** ("how many
things exist"), **quality-weighted density** ("how much of it is trustworthy") and **claim density**
("does anybody actually run these"). A cell can hold six benchmarks on which nobody has reported a
result since 2023, and that is a different kind of gap from an empty cell.

### 5.3 The gap score

```
gap_score = (1 - normalised_density)
          x domain_activity        [0-1]  publication and release velocity in that domain family
          x capability_salience    [0-1]  how often that capability is measured anywhere else
          x curation_confidence    [0-1]  how thoroughly WE have covered that domain
```

Every factor is published alongside the score, not just the product, so a reader who disagrees with
our weighting can re-derive their own ranking from the same JSON. A single opaque score would be an
editorial opinion wearing a number's clothes.

**`curation_confidence` is the honesty term and it is the most important field in this document.**
Without it, every under-curated domain looks like a research gap, and the Gap Finder becomes a map of
the maintainers' blind spots presented as a map of the field's. Given that the seed corpus will be
thinnest in exactly the domains we claim as our differentiator, omitting it would turn our strongest
feature into our loudest error.

```
curation_confidence(domain_family) =
    0.40 * min(1, entries_curated / expected_tier1_families)
  + 0.30 * fraction_of_entries_verified_within_180_days
  + 0.30 * reviewer_signoff        (0 = none, 0.5 = generalist review, 1 = domain expert review)
```

`expected_tier1_families` is the **Tier-1 (field-defining) column of the per-family table in
[02-taxonomy.md](02-taxonomy.md) §3**, which is the single canonical copy of those numbers and is
generated from `taxonomy/domains.yaml`. The per-family values are deliberately not repeated here: two
hand-maintained copies of nineteen numbers is how this plan came to carry three different seed
totals, and a denominator that disagrees with the taxonomy is worse than no denominator at all. Three
properties of that column matter to this formula. It totals **300 Tier-1 families across the thirteen
domains the reconnaissance actually sized**, against a realistic ceiling of roughly 4,700 families
across all domains. It is an estimate of what *exists*, which is not the seed target of 320 -- two
different numbers with two different jobs, and conflating them is what made "~300" mean three things
at once. And six families (code, language, mathematics, reasoning-general, multimodal,
engineering-design) were never sized at all, so for those rows the denominator falls back to the
family's seed target and the chart must mark the cell as unsized rather than quietly present a
target-over-target ratio as a coverage fraction. **These denominators are one
researcher's estimate made on 2026-09-17, not a measurement** (unverified -- confirm before relying
on this). They are stored in `taxonomy/domain-expectations.yaml` with that provenance attached, they
are versioned, and every domain reviewer who signs off is expected to revise their own domain's
number. A denominator that nobody revises is a denominator that becomes a lie.

### 5.4 Three kinds of empty, and how to tell them apart

An empty cell means one of three things, and the view must make the distinction visible:

1. **Nobody measures it.** The valuable case. Evidence: the capability is measured in adjacent
   domains, the domain is active, our curation confidence is high, and a domain reviewer has
   confirmed it.
2. **The taxonomy does not describe this field well.** Evidence: a domain reviewer flags the cell as
   miscut, or the domain's benchmarks cluster oddly in the Atlas. This is a taxonomy bug and routes
   to [03-taxonomy-build-process.md](03-taxonomy-build-process.md), not to the gap list.
3. **We have not curated it yet.** Evidence: low `curation_confidence`. Routes to the curation
   backlog and is excluded from published gap claims entirely.

Only category 1 is published as a gap. Categories 2 and 3 are visible internally and drawn on the map
in a different treatment, because hiding them would make our own backlog look like a discovery.

There is a fourth state that is not a kind of empty at all, and the coverage percentages in section
5.1 are wrong without it. A cell can be **declared not applicable** -- the question it asks is
incoherent for that family -- and a declared cell leaves both the numerator and the denominator of
every coverage figure, alongside the four tautological cells. That triage is mandatory
([03-taxonomy-build-process.md](03-taxonomy-build-process.md),
[10-visualization.md](10-visualization.md)) and it is a hard dependency of the capability-group
rollup rather than a nicety: `autonomy-and-oversight` and `conduct-and-cooperation` read near-empty
across physics, chemistry-materials, biology-genetics, earth-climate and engineering-design, and
undeclared they manufacture roughly twenty false gaps on day one in exactly the rows a specialist
reviewer opens first. The triage is not a blanket, either -- autonomous laboratories make
chemistry-materials x `autonomy-and-oversight` a live and informative cell, and declaring that one
inapplicable would itself be the error.

### 5.5 Gaps we can publish on day one

Five findings survived live verification on 2026-09-17 and are strong enough to publish with the seed
release, each with its evidence rather than as an assertion:

| Claimed gap | Evidence | Caveat |
| --- | --- | --- |
| Phylogenetics has no standing benchmark | Comparisons are simulation-based and per-paper; no dominant benchmark found | Absence of evidence after targeted search, not proof of absence |
| Education and tutoring has no public leaderboard | Tutoring quality is measured by learning-gain RCTs, not leaderboards | Same |
| Human-comparison psychometric batteries for AI have no canonical benchmark | None found across the general-intelligence survey | Same |
| Retrosynthesis has a canonical dataset but no canonical leaderboard | USPTO-50k (50,016 atom-mapped reactions); 2026 papers report RxnNano at 75.1% top-1 and RETROSPECT at 55.0% top-1 / 86.2% top-10 on the same 5,007-reaction test set | This is a *comparability* finding as much as a coverage one, and it is the cleanest example of the failure mode the whole index exists to fix |
| Several dangerous-capability areas have zero benchmark coverage | arXiv 2605.16282 reports no coverage for evading human oversight, self-replication or AI R&D capabilities; behavioural benchmarks clustered at 34/40 sandboxed, 26/40 constrained-tool, 28/40 rule-based | One paper, one snapshot; we reproduce the analysis over our own corpus rather than restating theirs |

The last row shows the intended pattern. Papers do this analysis once and freeze. Our version
recomputes on every build, so the finding either persists or visibly closes -- and a closing gap is
as publishable as an open one. It is also the reason the capability rollup groups `autonomy`,
`self-improvement` and `situational-awareness` together: those three terms sit in one capability
group, so this finding is a claim about a single coarse cell and is publishable under section 5.1's
rule. Split across three columns it would have been a fine-grid claim, which section 5.1 forbids
publishing -- a vocabulary decision deciding, in advance, which of our findings we are allowed to
state.

---

## 6. Adoption and influence

| Metric | Computation | Source of truth |
| --- | --- | --- |
| Adoption | Count of distinct `System` entities with at least one claim | Our claims |
| Organisational breadth | Count of distinct reporting organisations | `ResultClaim.reported_by` |
| Reporting velocity | Claims per month, bucketed by **`date_reported`**, never by ingest date | Our claims |
| Citations | Ingested from a bibliographic source, dated, **never estimated** | OpenAlex plus Semantic Scholar, cross-checked |
| Repository adoption | `stargazers_count` and `forks_count` snapshotted weekly into a self-built time series | GitHub API |
| Dataset adoption | HuggingFace downloads and likes, snapshotted weekly | HF API |
| Leaderboard liveness | Days since the hosted leaderboard last changed | Per-source adapters |

**The ingest-date trap.** Bucketing claims by ingest date would put roughly 6,598 Epoch claims on a
single day and produce a spectacular, entirely fictitious spike in "field activity". Every time
series in this document buckets on the event's own date -- `date_reported`, `date_evaluated`,
`released` -- and any record lacking one is excluded from time series and counted in a visible
`undated` bucket. Epoch's `release_date` is missing on exactly one of its 81 benchmarks (BTF-3), and
a `date_reported` equivalent is present on only about 30% of its 6,598 result rows. That 70%
exclusion prints on the chart.

**Citations are ingested, never estimated, and never trusted from one source.** OpenAlex moved to a
metered, key-required API announced in January 2026 and enforced around 2026-02-13; its own sources
disagree on the free allowance (the blog says $1/day, the stale docs repo says 100,000 credits/day, a
live measurement suggested $0.10/day -- unverified, measure with a real key before sizing anything).
More seriously, a live probe found OpenAlex record `W4387561453` carrying the right DOI and the right
authors with the wrong title and a citation count off by roughly two orders of magnitude. Semantic
Scholar's unauthenticated tier returned HTTP 429 on the first request. The resulting rule: **use
Semantic Scholar for arXiv-to-paper identity resolution, OpenAlex for institution/ROR and topic
concepts, cross-check the counts, and render any citation figure sourced from a single aggregator
with a visible "single source, unverified" marker.** A citation count is an influence claim, and an
influence claim from one flaky aggregator is exactly the quietly-wrong data that destroys a
trust-based index.

**Adoption counters live outside the citable core.** `github_stars` and `hf_downloads` change daily,
are not editorial content, and would otherwise generate constant churn in the CC-BY data tree. They
are written to a separate `metrics/` tree that auto-merges, is excluded from the DOI'd release, and
is labelled on the site as an observed counter rather than curated data
([05-repository-and-workflow.md](05-repository-and-workflow.md)). Do not build star history from
GitHub's `star+json` endpoint: it requires auth and paginates at 100 per page over the full star
list, so a 5,000-star repo costs 50 requests. Snapshot the current count weekly and own the series
going forward.

**What adoption cannot show.** A benchmark with few claims may be unused, or used privately by labs
that do not publish, or simply outside our curation reach. Falling reporting velocity on an
unsaturated benchmark usually means abandonment rather than difficulty -- but "usually" is not
"always", and the metric is presented as an observation with its date window, never as a verdict.

---

## 7. Liveness and decay

No catalogue the landscape reconnaissance examined marks benchmarks as dead
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1 states exactly how far that
claim is supported and what would retire it; the link carries the hedge and this document does not
restate it). The evidence that the absence matters is substantial: a 2026 survey of 195 AI safety benchmarks
reported 137 with stale GitHub repositories and 96 with stale HuggingFace datasets (arXiv 2604.12875,
**withdrawn on 2026-04-23** over an institutional-affiliation matter, so treat the figures as
indicative -- unverified, confirm before relying on this); BetterBench found 17 of 24 assessed
benchmarks had no easy-to-run reproduction scripts; the Aider leaderboards were last updated
2025-11-20.

We therefore publish **observations, not verdicts**:

```
liveness (per benchmark, all optional, all dated):
  days_since_repo_push              from GitHub pushed_at
  days_since_dataset_modified       from HF lastModified
  days_since_leaderboard_change     from our own adapter's content-hash history
  has_reproduction_script           tri-state: yes | no | not-checked   (hand-assessed)
  archived_source_rot               fraction of this entry's sources whose live URL now 404s
```

Two derived flags, each computed only when at least two signals were actually observed:

- `dormant-signal` -- no observed activity on any checked signal for **18 months**. Ecosystem Graphs
  sat 20 months stale while still being cited; 18 months is early enough to be useful and late enough
  to avoid flagging a stable, finished benchmark every quarter.
- `likely-inactive` -- no observed activity for **36 months** across all checked signals.

Both render with the underlying dates and the list of signals checked. Neither ever writes
`lifecycle: deprecated` into the YAML: deprecation is a judgement that needs a human and a source,
and the flag exists to prompt that review rather than replace it
([04-data-model.md](04-data-model.md)).

**What this cannot show.** A finished benchmark that needs no maintenance looks identical from the
outside to an abandoned one. A private leaderboard we cannot poll looks dead even when it is
thriving. The flag names what was observed and what was not, and the phrasing on the page is "no
observed activity in N days across M checked signals" -- never "dead".

---

## 8. Trust and hygiene metrics

These make the index self-auditing. **They are published, not internal.** A reference that never
publishes corrections is not error-free; it is unaudited.

| Metric | Computation | Why it is published |
| --- | --- | --- |
| Verification mix | Share of a benchmark's claims at each verification level | A benchmark where every number is self-reported is a weaker evidence base regardless of how impressive the numbers are |
| Condition completeness | Fraction of material `EvalConditions` fields populated; report **median and the share at zero**, not the mean | The mean hides a bimodal distribution. Epoch's rows land around 0.05-0.15, with `selection_strategy`, `chain_of_thought`, `judge_model` and `retries_allowed` at 0% structured coverage |
| Uncertainty availability | Share of claims carrying any uncertainty field | Epoch supplies a stderr or CI on 2,819 of 6,598 rows (42.7%). Below half. Say so. |
| Contamination exposure | Per system: share of its claims on benchmarks at `high` or `confirmed` contamination risk | A property of the **evidence**, never an accusation against the system |
| Machine-ingested share | Share of the corpus at `verification_status: machine-ingested`, overall and per domain | Our own honesty badge; if it climbs, our differentiator is eroding |
| Index staleness | Distribution of days since `last_verified`; publish p50, p90 and the count over 365 days | The metric that would have made Ecosystem Graphs' decay visible to its own readers |
| Dispute rate | Claims with a non-empty `disputed_by`, over total claims | Disputes are healthy; zero disputes means nobody is checking |
| Correction rate | Corrections merged per month, with a public corrections log | See above |

The hygiene dashboard is a first-class public page linked from the footer of every benchmark page,
not a hidden diagnostic. The most credible thing this project can do in its first year is publish the
number of times it was wrong.

**Condition completeness is the metric that states our thesis numerically.** Against the ten material
fields in the comparability rule, Epoch supplies `shots` on 19.4% of rows (with dirty mixed types:
`5`, `few`, `0-shot`, `25-shot`), `tools_allowed` on under 1%, and `selection_strategy`, `k`,
`n_samples`, `chain_of_thought`, `retries_allowed`, `judge_model` and `human_in_loop` at 0%
structured coverage -- `pass@1` and `AVG@5` are parseable only out of metric *names*. Ingesting Epoch
gives us 6,598 claims at roughly 10% condition completeness. **Our differentiator is raising that
number, not collecting more rows**, and publishing the number is how we stay honest about it.

The sharpest single illustration is already in Epoch's own data. Five rows of `arc_agi_external.csv`
share the identical `Model version` key `claude-opus-4-6_120K` with scores of 0.94, 0.94, 0.93, 0.92
and 0.86, distinguished only by a free-text `Name` field reading "(120K, High)", "(High, 120k
thinking)", "(120K, Max)", "(120K, Medium)" and "(120K, Low)". Their primary key cannot tell those
five claims apart, and two of them are near-duplicate spellings of the same run. A structured
`reasoning_effort` field plus the `comparability_key` resolves it exactly. That example, drawn from
the best-quality dataset in the landscape, is the strongest argument for the project that exists.

---

## 9. Ecosystem and direction analysis

This section backs the ecosystem view in [10-visualization.md](10-visualization.md) and the user's
explicit requirement to "analyze/view the current ecosystem (systems, benchmark makers, managing
orgs, trends)". It is also the part of the project most likely to produce a citable output, because
almost none of it is currently quantified anywhere.

Each analysis states its computation, the data it requires, its confounders, and what it cannot show.
The last of those is not decoration. Every series here is a claim about the field, and a claim about
the field with no stated limits is exactly the confident unsourced assertion this project exists to
oppose.

### 9.0 The cohort rule, which applies to everything in section 9

Every ecosystem series is computed over a **declared cohort**, never over "everything in the
database". The default cohort is:

```
cohort_v1 = benchmarks with
      a sourced release date
  AND verification_status in {primary-source-verified, maintainer-confirmed}
  AND a primary domain assigned by a human
```

The cohort definition, its size and its per-domain composition print on every chart. Without this,
every trend line is confounded by our own ingestion schedule: ingest 300 LLM benchmarks in March and
40 robotics benchmarks in June, and an uncorrected "domain attention" chart shows a language boom and
a robotics boom that happened in our repository, not in the world.

### 9.1 Who builds benchmarks

**Computation.** New benchmarks per release year, grouped by `governance.maintainer_type`
(`academic-lab`, `industry-lab`, `consortium`, `nonprofit`, `government-agency`, `individual`,
`community-collective`, `unmaintained`). Stacked area for shares; small multiples for absolute counts.

**Data required.** `released`, `maintainer_type`, `maintainers[]` resolved to `Organization`.

**Confounders.** Maintainer type can change over a benchmark's life: MedHELM began inside Stanford
CRFM and spun out in 2026 into an independent community project with technical stewardship by Pacific
AI. We record the type at release, note transitions in lineage, and the chart says which it plots.
Joint academic-industry efforts must be split into multiple refs and counted fractionally rather than
assigned to one side -- Epoch's export records organisations as comma-joined pairs such as
"Z.ai (Zhipu AI),Tsinghua University" and "DeepSeek,Peking University", and collapsing those to a
first value would systematically under-count academic participation.

**Cannot show.** Who *funded* the work. Funding disclosure is inconsistent and we do not infer it.

### 9.2 The academic-to-industry shift

**Computation.** The industry share from 9.1; the same split computed over *claims* rather than
benchmarks (who reports numbers); and the share of benchmarks whose maintainer also ships an
evaluated system.

**Data required.** As 9.1, plus `reported_by` on claims and the `Organization` graph.

**Confounders.** Industry labs publish launch posts; academic labs publish papers, which our
bibliographic sources index far better. Our source mix therefore biases this series directly. The
correction is to report it separately for benchmarks discovered through arXiv, through GitHub and
through first-party lab feeds, so a reader can see whether the shift survives the source split.

**Cannot show.** Whether industry benchmarks are better or worse. That is a quality judgement and
section 12 explains why we do not make it.

### 9.3 Independence exposure

**Computation.** Share of benchmarks per year carrying `independence_flags` other than
`no-known-conflict` -- principally `maintainer-competes-on-own-benchmark`,
`funded-by-evaluated-party` and `commercial-leaderboard-placement`. Cross-tabulated with
`submission_process`, because self-reporting on a benchmark whose maintainer competes is a materially
different evidence situation from a held-out server.

**Data required.** `independence_flags`, each with an evidence source -- the flag is invalid without
one.

**Confounders.** The flag is only as complete as curation. A rising line may mean rising conflict or
rising diligence. Publish the curation-confidence series on the same axis so the two are separable.

**Cannot show.** Bad faith. This is disclosure, never accusation: the point is that a reader can see
that a lab built the benchmark its own model tops, and weigh it themselves.

### 9.4 Evaluation-method drift -- the flagship

**Computation.** Share of newly released benchmarks per year by `evaluation_method`, with particular
attention to `model-graded-judge` against `execution-tests`, `human-expert-eval`,
`formal-proof-check` and `pairwise-preference-elo`. A benchmark may declare several methods; count
fractionally across its declared methods and publish both the fractional and the any-of series. On
the claim side, track the share of claims whose `EvalConditions.judge_model` is populated at all.

**Data required.** `evaluation_method[]` and `released` over `cohort_v1`; `judge_model` on claims.

**Why this matters more than anything else in section 9.** The rise of model-graded evaluation is one
of the most consequential quiet shifts in the field and **it is currently unquantified anywhere**.
The evidence that it is happening is everywhere and nowhere: HealthBench grades 5,000 conversations
against 48,562 physician-authored rubric criteria with a *model* as the grader; PaperBench aggregates
a rubric of roughly 8,316 leaf nodes via an LLM judge; BixBench scores open answers with an LLM
judge; GenEval and T2I-CompBench compute their metric with another model, so the score moves when the
evaluator's version moves; HarmBench judges attack success with a fine-tuned classifier; AILuminate
uses an ensemble of tuned safety evaluator models; Epoch's Lech Mazur Writing entry is LLM-judged on
a 0-10 scale. Nobody has counted it. **Quantifying this may be one of this project's most cited
outputs**, and it is achievable with facet data we are already collecting for other reasons.

**Confounders.** Three, all serious. (i) The facet is hand-assigned and never inferred
([02-taxonomy.md](02-taxonomy.md), cross-cutting rule 2), so under-tagging suppresses the signal --
the correction is to publish the share of cohort entries with *any* evaluation method assigned
alongside the trend. (ii) Judged benchmarks are cheaper to build, so they proliferate in raw count
while attracting fewer serious runs -- publish the series weighted by claim count as well as by
benchmark count. (iii) Our cohort skews toward benchmarks that got attention, and model-graded
benchmarks are newer, so recency bias inflates the recent end.

**Cannot show.** Whether model-graded evaluation is more or less accurate. It shows adoption, not
validity. Where a benchmark publishes judge-versus-human agreement figures we record them on the
benchmark as sourced facts; we never aggregate them into a verdict about the method.

**A note on the four short entries that follow.** Sections 9.5, 9.6, 9.9 and 9.10 ship in Phase 5 or
later against a cohort whose shape nobody can yet see, so they are specified to the level that
actually transfers -- the axis, the precondition, the one confounder that would invalidate the series,
and what it cannot show -- and no further. Writing a full design now for an analysis over unknown data
is how a plan accumulates pages that are stale before they are built. Sections 9.7, 9.8 and 9.11 stay
in full because each carries a decision rather than a design: a lineage differentiator, an exclusion
rule, and a deferral with a reason.

### 9.5 Domain attention flow

New benchmarks per year by primary domain family, normalised to shares, plus a flow view of which
domains gain and lose share year over year. **Requires** `released` and `domain.primary` over
`cohort_v1`, with per-domain `curation_confidence` printed as an opacity channel on the same chart.
**The confounder that would invalidate it:** raw counts are dominated by how aggressively each field
names things -- the domain reconnaissance estimates a ceiling of 1,000+ vision benchmark families and
700+ in medicine against 60 in general intelligence -- so vision eats the chart unless shares are
reported within a fixed-denominator cohort and the per-family cap in
[02-taxonomy.md](02-taxonomy.md) holds. **Cannot show** research effort or funding; a domain can
produce few benchmarks and enormous work.

### 9.6 Access trend as the field's response to contamination

Share of newly released benchmarks per year with `access` in {`private-test-server`,
`generated-on-demand`, `gated-registration`} and `refresh` in {`rolling-live`,
`continuously-generated`, `periodic-recompetition`}, plotted against `reproducibility_tier` so the
trade is visible: each of those choices buys contamination resistance and spends reproducibility.
**Requires** the data-properties facet plus `released`. **Why it is worth the slot:** this is the
field structurally defending itself, and the corpus is full of it -- FrontierMath held privately by
Epoch, Scale's SEAL evaluating models "only the FIRST TIME an org encounters the prompts", ARC-AGI's
Kaggle private set, CARLA 2.0's secret routes, LiveBench's monthly refresh, AILuminate's 12,000
private prompts beside 12,000 public, Apollo Research's scheming suite held out entirely. **The
confounder that would invalidate it:** gating is also a commercial strategy and, separately, a privacy
requirement -- CheXpert and MIMIC sit behind PhysioNet credentialing for patient-privacy reasons, not
contamination ones -- so split by `maintainer_type` and never characterise the motive. **Cannot show**
whether contamination is actually decreasing.

### 9.7 Benchmark half-life, lineage churn and the catalogue graveyard

**Computation.** Three related series.

- **Half-life:** median months from release to peak reporting velocity, by release cohort, with the
  same Kaplan-Meier censoring treatment as section 4.3.
- **Lineage churn:** versions and forks per benchmark family per year, from the `lineage` graph. The
  raw material is abundant: SWE-bench has spawned Verified, Lite, Multimodal, Multilingual and Pro;
  HELM has eight variants; FrontierMath has four private variants plus Erdos; OSWorld became
  OSWorld-Verified and OSWorld 2.0 concurrently; Terminal-Bench 2.0 and 2.1 ran at the same time;
  miniF2F spawned MINIF2F-DAFNY. Epoch needed a `superseded_by` column and populated it on only two
  of 81 rows, which understates the real churn by an order of magnitude -- and that understatement is
  itself the finding.
- **Supersession velocity:** months between a version's release and the release of the version that
  supersedes it.

**Data required.** `lineage`, `BenchmarkVersion.breaking`, `released`, claim dates.

**Confounders.** Fork proliferation partly measures a benchmark's *success* -- SWE-bench has six
descendants because it mattered. Report churn alongside adoption so the two readings stay separable.

**Cannot show.** Whether the forks were necessary. But the series does something nobody else does: it
makes the cost of version chaos visible, which is the direct argument for the lineage model being a
differentiator at all.

**A companion series, maintained as curated data rather than as derived analytics:** a catalogue
mortality record. Papers with Code (sunset 2025-07-24 with 9,327 benchmarks, 5,628 datasets and
79,817 paper-code links), Ecosystem Graphs (last push 2025-01-24, no licence), HELM (maintenance mode
2026-06-01), the HuggingFace Open LLM Leaderboard (retired 2025-03-14), BIG-bench (archived
2026-04-17), `JonathanChavezTamales/llm-leaderboard` (self-deprecated into the closed llm-stats.com),
Evidently AI's 250-benchmark database (last updated 2025-07-31), Princeton HAL (submissions paused),
VoxSRC (retired after 2023), TrackML (retired, still cited), the Annual Computer Poker Competition
(dormant since roughly 2018). These are `Organization` and `Leaderboard` records with dates and
sources, not computed numbers -- but rendering them as a timeline beside our own index-staleness
metric is the single most honest thing the site can display. It is the argument for CC-BY, a DOI and
a documented succession story made in data rather than in prose
([01-landscape-and-positioning.md](01-landscape-and-positioning.md),
[05-repository-and-workflow.md](05-repository-and-workflow.md)).

### 9.8 Capability releases against benchmark releases

**Computation.** Two aligned time series -- system releases from `System.first_released` and benchmark
releases from `BenchmarkVersion.released` -- plus a lag analysis: for each benchmark, months from its
release to the first claim reaching `closing` or `saturated`, plotted against release year.

**Data required.** System release dates (Epoch supplies `date` on 97% of 1,063 model rows), benchmark
release dates, qualifying claims.

**What it is for.** The relationship between the two bands is the actual story of the field:
benchmarks appearing in response to capability jumps, capabilities saturating benchmarks, the gap
between the two compressing. HLE was built explicitly against benchmark saturation; ARC-AGI-3
launched on 2026-03-25 with humans solving every environment and all frontier models below 1%
(Gemini 3.1 Pro ~0.37%, Claude Opus 4.6 ~0.2%); by 2026-09-15 HLE's leader stood at 55.5%. All four
of those figures are **reported, not re-derived here** *(unverified -- confirm before relying on
this)*; they are illustration in a "what it is for" paragraph, and no chart in this document depends
on them. Once they are curated entries they carry their own sources and this paragraph cites the
entries instead. The compression is real and visible.

**Confounders.** Severe, and they must be stated. System release dates are vendor announcements, not
availability dates. Benchmark "release" is ambiguous between paper preprint, dataset publication and
leaderboard launch -- we record which one the date refers to on `BenchmarkVersion` and exclude
records where it is unknown. The causal story runs both ways, so this is a correlation display and is
labelled as one.

**Explicitly excluded: compute-versus-capability regressions.** Epoch's `training_compute_flop` is
populated on only 31% of model rows, and its own notes disclose values "imputed to be 1.58e25 FLOP
from benchmark scores". Using a compute figure that was inferred *from* benchmark scores as a
predictor *of* benchmark scores is circular. The field is ingested with an `estimated` flag and the
notes preserved ([04-data-model.md](04-data-model.md)), it is displayed on system pages, and it is
never used as an independent variable in any published analysis.

### 9.9 Metric pluralism and the appetite for aggregation

Two counter-posed series over `cohort_v1`: **metric pluralism**, the mean number of distinct
maintainer-designated headline metrics per benchmark by release year, against **composite
proliferation**, the count of benchmarks per year whose headline number is a `composite` evaluation
method or a declared weighted index. **Why it is worth the slot:** both instincts appear to be rising
at once. Pluralist side -- ReXrank's eight metrics and deliberate non-aggregate, VBench's 16+
dimensions, HELM's seven axes, WeatherBench 2's refusal to rank, AgentDojo's two orthogonal axes,
BBQ's pair of numbers whose optimum is zero. Aggregating side -- ECI, the Intelligence Index,
BenchmarkList's Rosetta Stone, Matbench Discovery's CPS, NAVSIM v2's EPDMS, nuScenes' NDS,
AILuminate's ordinal grades. We refuse to build a composite; counting how many other people build them
is a legitimate use of that refusal, it is cheap, and nobody else is counting it. **The confounder
that would invalidate it:** "number of metrics" is partly a documentation artifact, so count only
metrics the maintainer designates as headline and say so on the chart. **Cannot show** whether either
instinct is right.

### 9.10 Geographic and organisational concentration

Benchmark releases and result claims by maintainer country and organisation over time, reported as a
concentration measure (share held by the top five organisations) rather than as a ranking, per section
12's refusal to publish league tables of labs or countries. **Requires** `Organization.country` and
resolved refs; Epoch's export supplies country on 87% of model rows and per-organisation result
counts, which is enough to build the series and not enough to publish it. **The confounder that would
invalidate it, and it is disqualifying on its own:** those numbers describe *who Epoch evaluated*, not
who builds. All 81 of Epoch's benchmarks are LLM-centric and zero touch robotics, chemistry, biology,
medicine, climate, materials or audio, so publishing them as "the field" would be exactly the error
this document criticises in others. **Gate:** publishable only once the non-LLM half of the corpus is
curated; until then it ships with an explicit "LLM subset only" label or it does not ship. **Cannot
show** capability; it is an attention and resource map, nothing more.

### 9.11 Regulatory alignment coverage (deferred)

**Computation.** Share of benchmarks tagged against published regulatory or standards frameworks --
principally the EU AI Act GPAI obligations, enforceable since 2026-08-02, which require evaluation
"using standard benchmarks and state-of-the-art tests" for systemic-risk models above 10^25 FLOP,
with **no registry defining what qualifies**. COMPL-AI (ETH Zurich / INSAIT / LatticeFlow, arXiv
2410.07959) is the strongest existing regulation-to-benchmark mapping and should be cited as ancestry
rather than reimplemented.

**Why it is deferred.** The analysis is valuable and the gap is real, but the mapping is an
interpretation of law. It requires either a legal reviewer or a clearly-labelled restatement of
someone else's published mapping. Producing our own uncredentialed interpretation would be the worst
kind of editorial overreach, and it would hand a regulator a reason to distrust everything else on
the site. Recorded as an open question in [15-open-questions.md](15-open-questions.md).

---

## 10. Statistical discipline

Six rules, enforced in the derived layer rather than left to the UI.

**1. Never rank on point estimates alone.** Where `uncertainty` exists, show it. Where it does not,
show that it does not -- the absence is common and meaningful, and Epoch supplies an uncertainty
field on only 42.7% of its rows.

**2. No significance claims without the data to support them.** Most published claims carry no run
count and no confidence interval. The index reports what exists; it does not compute significance
from unavailable information, and it never converts a bare pair of numbers into "X beats Y".

**3. Small-n warnings, computed once and attached to the benchmark.** Benchmarks under roughly 200
items produce accuracy differences of several points that are indistinguishable from noise. GPQA
Diamond, which the field treats as a headline benchmark, has **198 questions**: the binomial standard
error at p = 0.7 is about 3.3 points, the standard error of a difference between two systems is about
4.6 points, and a 95% interval on that difference is roughly +/- 9 points. **A five-point gap on GPQA
Diamond is noise.** The derived layer computes `min_detectable_difference_95` from `size.items` and
the metric type wherever both are known, stores it on the benchmark, and the UI shows it once on the
benchmark page rather than repeating it in every comparison cell.

**4. Structural non-comparabilities are refused, not annotated.** Some numbers cannot be compared at
all, and a warning banner is not enough:

| Situation | Rule |
| --- | --- |
| Elo across rating-pool snapshots | Refuse. A model's Kaggle Game Arena rating changes when a *different* model joins the pool, with no change to the model. Rating-pool identity plus snapshot date are part of the stored result. |
| `pass^k` against mean success rate | Refuse. Tau-bench's headline metric is the fraction of tasks solved in **all** k independent trials; averaging destroys exactly what it measures. |
| Human-assisted against automated entries | Refuse. CASP ranks human-expert groups separately from automated servers, so the same method legitimately appears twice with different numbers. |
| Different training-data eligibility tiers | Refuse. Matbench Discovery groups models by what data they were allowed to train on -- a comparability key on the *training* side, which most LLM-shaped schemas have no slot for. |
| Scores that resolve later | Mark `resolution_status: pending`. ForecastBench questions have no answer at submission and resolve months to years later. |

**5. Multiple comparisons on the coverage matrix.** The coarse grid has **247** cells
(19 domain families x 13 capability groups) and the fine grid **8,976** (204 (family, subdomain)
pairs x 44 capability terms), minus the four tautological cells declared in
`taxonomy/homographs.yaml`, which leave the family before any multiple-comparisons correction is
applied -- a cell occupied by construction inflates the family size without contributing a testable
hypothesis. Both counts are read out of `taxonomy/*.yaml` at build time, with the
`capability_groups.yaml` version recorded alongside them (section 5.1). No claim of the form
"domain X significantly under-measures capability Y" is made from cell counts alone. The gap score is a heuristic ranking with its inputs exposed, and it is described
as one.

**6. Every derived number records its parameters.** Verification threshold, condition-completeness
floor, date window, cohort definition, data commit SHA. They are shown next to the number, not in a
footnote.

### The narration rule

Where the AI layer describes any of these figures, the governing rule from
[11-ai-features.md](11-ai-features.md) applies without exception:

> **THE MODEL NEVER PRODUCES A NUMBER.** Cost estimates, runtime estimates, comparability verdicts
> and coverage percentages are computed in JavaScript from structured fields and shown with their
> formula. The model writes the sentence around the number, not the number.

The AI layer is a lens, never a source. Every number in every AI-generated sentence on this site is a
value read out of `build/derived/`, and the sentence is generated around it.

---

## 11. Recomputation and citability

Derived metrics are deterministic functions of committed data, so any published figure is reproducible
from a commit hash. That is what makes the analytics citable rather than decorative, and it is the
property that separates this project from every catalogue whose charts are screenshots of a private
database.

**Every analytics page carries a build-time-generated citation block:**

```
Universal AI Benchmark Index. "Evaluation-method drift, 2018-2026."
  build/derived/ecosystem/method-drift.json at commit 4f2a9c1e.
  Computed 2026-09-17T04:12:09Z.
  Verification threshold: maintainer-verified. Condition-completeness floor: frontier_floor = 0.30.
  Cohort: cohort_v1, n = 312 benchmarks (see manifest).
  Data: CC BY 4.0. https://<domain>/analytics/method-drift?rev=4f2a9c1e
```

Three mechanics make that citation resolve rather than rot:

1. **`?rev=<sha>` is honoured.** Each release build's `derived/` tree is published under a
   content-addressed path, and a page loaded with `?rev=` renders that build's numbers behind a
   banner naming the revision and its date. A figure cited in a paper must still render in three
   years.
2. **The manifest is the audit trail.** `build/derived/manifest.json` carries the input tree hash,
   every metric's parameters and the tool versions, so a third party can clone at that SHA, run
   `make derived`, and byte-compare. The CI determinism gate means that comparison is expected to
   succeed exactly, which turns "reproducible in principle" into a test that fails when it stops
   being true.
3. **Releases are DOI'd.** Each tagged release mints a DOI covering the YAML corpus, the generated
   JSON Schema, the two shipped JSON artifacts, the build-time SQLite and `build/derived/`. The
   derived layer is part of the citable release, not a website feature
   ([05-repository-and-workflow.md](05-repository-and-workflow.md)).

**The honest limit on reproducibility.** The derived layer is fully deterministic. The Atlas layout is
not reproducible across machines even with pinned versions -- UMAP guarantees reproducibility across
runs but not across hardware -- which is why CI is the sole authority permitted to write
`atlas.json`. Position on the Atlas is therefore a presentational artifact, and it is never an input
to any derived metric in this document. No analytic claim depends on a coordinate.

---

## 12. Analyses we will not publish

The discipline that makes the rest of this document credible is the list of things it refuses to
compute. Each entry names what we do instead.

**A benchmark quality score.** BetterBench's 46 criteria across four lifecycle stages are the best
existing prior art for benchmark quality assessment and should be cited as ancestry. We will not
produce a composite quality grade. A quality score is an editorial opinion wearing a number's
clothes; it invites gaming; and it would make adversaries of the maintainers we need as contributors
and domain reviewers. *Instead:* publish the observable components separately and let readers weight
them -- reproduction script present or absent, sources archived, licence stated, human baseline
present, condition completeness of its claims, verification mix, liveness signals. Every one of those
is a fact with a source. Their sum would be an opinion.

**A universal model ranking or capability index.** Constraint 3, and section 2. This is the single
most important refusal in the project and the most defensible trust position available: every
competitor's instinct is to force non-comparable scores onto one scale, and a catalogue whose
signature behaviour is declining to rank is genuinely unoccupied ground.

**Cross-benchmark score alignment.** No Rosetta Stone, no IRT fit across domains, no "equivalent
score on benchmark B" estimator. We catalogue Epoch's ECI and BenchmarkList's index as ecosystem
artifacts, link to them, and explain the difference. Building our own would be adopting the thing we
positioned against.

**Adjudication between conflicting claims.** Where two sources report different numbers for the same
system, benchmark, version and conditions, we show both with their provenance and a conditions diff.
The retrosynthesis case -- 75.1% top-1 and 55.0% top-1 reported on the same 5,007-reaction test set
-- is displayed as a conflict with both sources archived, not resolved by us. Picking a winner would
require re-running the evaluation, which is [13-execution-runners.md](13-execution-runners.md)
territory and explicitly deferred and optional.

**Predicted or extrapolated saturation dates.** Saturation velocity is a trailing measurement over a
stated window. It is never extended forward into "this benchmark will saturate in March". The
relationship is non-linear (section 3.5), the frontier series is a running maximum (section 4.2), and
a forecast would be the one number on the site with no evidence behind it.

**Contamination accusations against systems.** Contamination exposure is computed and displayed as a
property of the *evidence base* -- what share of a system's claims sit on benchmarks with documented
contamination risk. It is never framed as a claim that a system was trained on test data. Epoch's
corpus contains an unstructured note reading "Explicitly fine-tuned on it"; in our schema that
becomes a sourced, structured contamination-evidence record on the benchmark, not a verdict about a
lab.

**"Best benchmark for X" rankings.** The suite builder in [11-ai-features.md](11-ai-features.md)
assembles candidate sets against stated criteria -- domain, capability, access, cost, reproducibility
tier -- and exports a manifest with links and recommended conditions. It orders by those stated
criteria, shows the criteria, and never emits an unqualified "best".

**League tables of people, labs or countries.** Counts by organisation are published with their
confounders (section 9.10). A ranking of researchers, labs or nations by benchmark output is not,
because the counting convention dominates the result and the output is a status game rather than
information.

**"Trending" driven by our own ingestion.** Any feed or ranking sorted by when we added or updated a
record measures our scraper's schedule, not the field's attention. The release feed sorts on the
event's own date and says so.

---

## 13. Delivery phasing

The derived layer is cheap to compute and expensive to get right, so it ships in the order of how
much curated data each metric needs in order to be honest. Phases align with
[14-roadmap.md](14-roadmap.md).

| Phase | Ships | Precondition | Why not earlier |
| --- | --- | --- | --- |
| 2 | Headroom, null-reason reporting, saturation bands | `Baseline` and `Metric.range` populated for the seed set | Headroom without sourced anchors is a made-up number |
| 3 | Coverage density (coarse grid), curation confidence, hygiene dashboard | Seed corpus at 320 Tier-1 families with all 19 domain families non-empty ([02-taxonomy.md](02-taxonomy.md) §3) | A coverage map over 60 benchmarks is a map of our backlog |
| 3 | Saturation velocity, time-to-saturation with censoring | At least four qualifying claims on enough benchmarks to fit slopes | A slope through two points is decoration |
| 4 | Gap score and Gap Finder, adoption, liveness, citations | Domain-reviewer sign-off on at least half the domain families | Publishing gaps before expert review publishes our blind spots as findings |
| 4 | Ecosystem 9.1-9.4 (maintainer mix, industry shift, independence, method drift) | `cohort_v1` above 320 entries with sourced release dates | The cohort is too small to survive its own confounders |
| 5 | Ecosystem 9.5-9.9 (domain flow, access trend, half-life and lineage churn, release cadence, metric pluralism) | Non-LLM domains meaningfully curated | These series are meaningless on an LLM-only corpus and would look exactly like every competitor's |
| 5+ | Ecosystem 9.10 concentration, 9.11 regulatory alignment | Non-LLM curation; legal review for 9.11 | See sections 9.10 and 9.11 |

The general rule behind the table: **a derived metric ships when the data underneath it can survive
being checked by a specialist in that domain, and not before.** The cost of publishing a coverage map
that a roboticist can falsify in ten minutes is far higher than the cost of shipping it two months
later, because differentiator #3 is the one that has to be right the first time.

---

## Related documents

- [02-taxonomy.md](02-taxonomy.md) -- the facets every metric here aggregates over
- [03-taxonomy-build-process.md](03-taxonomy-build-process.md) -- governance of the capability rollup and the domain expectation denominators
- [04-data-model.md](04-data-model.md) -- `Baseline` (renamed from `HumanBaseline`), `Metric.range`, `EvalConditions`, the verification ladder
- [05-repository-and-workflow.md](05-repository-and-workflow.md) -- the `metrics/` tree, DOIs, the corrections log
- [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) -- the segregated ingest tree these metrics filter on
- [08-infrastructure-and-build.md](08-infrastructure-and-build.md) -- build pipeline, artifacts, determinism gates
- [10-visualization.md](10-visualization.md) -- every view that consumes `build/derived/`
- [11-ai-features.md](11-ai-features.md) -- the narration rule and the suite builder
- [14-roadmap.md](14-roadmap.md) -- phasing and effort
- [15-open-questions.md](15-open-questions.md) -- regulatory-alignment coverage, domain expectation denominators
