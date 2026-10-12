# Schema findings the first entries recorded

<!-- docs/schema-findings-ledger.md -- P0-S9-T05 (ADR-0026). Written once, from the entries' curation.notes, before
     migration 0026 moved the reviewer checks into curation.review_checks and removed these findings from the
     entries. New findings are added here by hand, not to an entry. -->

While drafting the first entries, the drafter recorded what the schema could not say, under a "Schema
findings" heading in each entry's `curation.notes`. A finding is about the schema, not about the benchmark,
so it does not belong in the entry: the escape-hatch audit ([schema-stress-audit.md](schema-stress-audit.md))
found these blocks doing structural work in a free-text field, and ADR-0026 moved them here. Each is
verbatim, numbered as the entry numbered it.

This is a ledger, not a decision. Some findings were already resolved when they were written (the entry
says so, for example "ADR-0024 fixed the pair's mapping"); the rest are open, and whether each needs a
schema change is a judgement for the schema's owners, recorded by an ADR when it is made.
[checkpoint/schema-findings.md](checkpoint/schema-findings.md) is the P1-S3-T04 analysis that grouped the entries'
notes and fed ADR-0024; this file is the entries' own findings, kept verbatim.

45 findings from 8 entries.

## arc-agi-3

From `data/benchmarks/general-intelligence/arc-agi-3.yaml`.

1. Leaderboard had no way to say which rules it applies; ADR-0007 adds Leaderboard.conditions, and the two boards here are its first users.
2. A board's conditions are a floor, not one run: the Verified board accepts two harnesses, so its record leaves `harness` null, and "harness is one of {standard, provider-adapter}" is not expressible. The claim records carry the harness.
3. The facets resolve the `simulation` profile, which makes hardware_platform material and says nothing of harness, eligibility track or reasoning effort. The three are added through comparability.material_extra (the policy re-tests models "at varied reasoning levels"), and hardware_platform is waived with its reason.
4. simulation-rollout's definition is "success rate over episodes"; RHAE is an efficiency-weighted completion score, which no evaluation-method term names.
5. A board-level cap ($10,000 per run) and an action budget (five times the human median) have no EvalConditions field; cost_usd is a run's cost, not a limit.

## forecastbench

From `data/benchmarks/society-econ-law/forecastbench.yaml`.

1. EvalConditions has no field for the context a forecaster is given (freeze values, news, the crowd forecast), which the paper shows moves the score (Table 2); the claims state it in notes.
2. resolution_window is undefined in 04 S8 and overlaps ResultClaim.resolved_as_of; the claims' conditions use it for the resolution cut-off a score was computed at.
3. Tier 3 forbids live-world-state beside fully-automatable, but a benchmark can be reproducible in its scoring and unrepeatable in its runs; the tier has no way to say which it describes.
4. Baseline has no subset field: the 2024 baselines are on the 200-question human set.
5. A pending claim has no value but still needs a metric and conditions; nothing says when it is due to resolve (here 2034), which a reader of a pending claim most wants to know.

## kaggle-game-arena

From `data/benchmarks/games-planning/kaggle-game-arena.yaml`.

1. live-world-state beside fully-automatable: the not-independently-reproducible exclusion test says to tag the tier a fresh run needs and add live-world-state, and tier 3's fully-automatable rule forbids exactly that. ForecastBench hit the same contradiction.
2. A RatingPool has no subset: Chess Text and Chess Opening are rated separately over the same eleven models, so one pool record serves both, and a claim's subset says which ratings it holds.
3. The ratings are Elo-scaled Bradley-Terry fits; rating_system takes one value and is recorded as bradley-terry, with the Elo scaling in the metric's definition.
4. No comparability profile resolves for tournament-play x model-in-benchmark-harness: the second term is in no profile's applies_to at all, so its material set is subset_used alone. Four fields are added through comparability.material_extra.

## matbench-discovery

From `data/benchmarks/chemistry-materials/matbench-discovery.yaml`.

1. Metric.value_type has no term for a dimensional quantity: MAE in eV/atom and RMSD in Angstrom are recorded as `ratio`, the nearest term.
2. A composite with viewer-adjustable weights (CPS) has nowhere to say that its weights are a parameter; Metric.aggregation holds the defaults as text.
3. training_data_eligibility_tiers[] is a flat list; the live leaderboard's vocabulary is now a per-dataset filter plus an openness class, which a flat tier list cannot express.
4. EligibilityTier has no quote field, so the tier rules are quoted in a training_data_eligibility_tiers_basis annotation instead of on each tier.
5. No reference_conditions: the leaderboard mixes tiers by default and names no reference tier, so choosing one (compliant, unique prototypes) would be ours, not the maintainers'. Without one, SOTA and headroom stay undefined, which is what a tier-dependent ranking should produce.
6. As with WeatherBench 2, submission_process has no term for "the maintainer scores submitted predictions against public ground truth".
7. The comparability profile table keys on facet pairs, and statistical-fit x scientific-surrogate-model is mapped to `forecasting`, so lead_time and resolution_window arrived as material for a crystal benchmark. Waived with reasons (comparability.material_waived); ADR-0024 fixed the pair's mapping (surrogate-fit), and the waivers are gone.
8. Metric has no verification status, so the six agent-drafted Metric records here publish as soon as they load (tools/build/artifacts.py), with their Sources, while this entry stays a draft. Metrics need the draft gate Benchmarks have.

## paperbench

From `data/benchmarks/agents-tooluse/paperbench.yaml`.

1. EvalConditions has no field for the agent's wall-clock time limit, which the paper shows is material (o1 at 24.4% in 12 hours, 26.0% in 36); max_steps, message_limit and token_limit do not cover it.
2. Baseline has no subset field: the human baseline is on 3 of 20 papers, and headroom against it for a full-benchmark score compares different item sets.
3. The verify's "tier-3 judge-model rule" is claim-level; the benchmark-level check is reference-grader. Both require a named judge; only reference-grader can fire on an entry with no claims.
4. independence_flags has no term for a judge model supplied by an evaluated party.
5. The per-type leaf totals (3,674 / 4,076 / 566) and the node total (11,218) are sums of the paper's tables, not quoted figures; Metric carries no quote fields, so they are unquoted by construction.

## scicode

From `data/benchmarks/code/scicode.yaml`.

1. The paper's two protocol switches -- scientific background supplied or not, and gold or generated solutions carried over -- move pass@1 by several points (Table 3) and have no EvalConditions field. ForecastBench met the same gap (supplied context). Until one exists, only standard-setup claims are curated, so no two claims differ by an unrecorded condition.
2. Epoch's scicode_external.csv cites Artificial Analysis, whose SciCode score is not this metric (main-problem pass@1); its mapping stanza (P3-S2-T04's orphan files) should name its own metric.
3. taxonomy/comparability-profiles.yaml has no profile for execution-tests x instruction-tuned-model -- prompted code generation, HumanEval's shape -- so it falls back to subset_used alone. The llm-static-text fields are added here through material_extra; the profile file should gain the pair.

## virtual-cell-challenge

From `data/benchmarks/biology-genetics/virtual-cell-challenge.yaml`.

1. EvalConditions.training_data_policy's four terms have no definitions. Here `zero-shot-only` means no perturbation response in a target context is released; training on any other data is allowed. Read as a training ban -- 02 S12.10's "none" -- it would be false.
2. Baseline.kind has no term for a reference point computed from the ground truth itself (the cell-context mean); classical-algorithm, the nearest floor kind, suggests an entrant-style method.
3. A reference-scaled metric whose ceiling anchor is passable has no field saying so: Metric's `unbounded` marks it, which also makes headroom uncomputable, although headroom against the replicate is exactly what the scale is built for.
4. The anchors are per metric and per context (six by three per round), measured on the held-out data; Baseline stores one value per (version, metric), so only the overall score's 0 and 1 are stored, and the per-context raw anchors are not.
5. taxonomy/domains.yaml and taxonomy/capabilities.yaml cite `virtual-cell-challenge-2026`, which is not an entry id (aliases_note).
6. independence_flags has no term for a sponsor that co-develops the scorer (NVIDIA and cell-eval).
7. As with Matbench Discovery, statistical-fit x scientific-surrogate-model resolves the forecasting profile, so lead_time and resolution_window arrived as material and were waived, until ADR-0024 gave the pair its own profile.
8. A site that renders client-side can only be sourced through its script bundles; Source has no field to say that the extract's bytes are a bundle and not the page at `url`, so the notes say it.

## weatherbench-2

From `data/benchmarks/earth-climate/weatherbench-2.yaml`.

1. Evaluation resolution is material and has no EvalConditions field. The maintainers: "Note that absolute values of metrics computed at different resolution are not necessarily comparable (see paper)." (src-weatherbench-2-submit). `resolution_window` is a forecast-resolution date, a different thing. P1-S7-T01 already plans for it: "Record lead time and spatial resolution as first-class conditions." (_plan/execution/tasks.yaml).
2. The ground truth an entrant is scored against is material and has no field: "Operational models are evaluated against IFS analysis. All other models evaluated against ERA5." (src-weatherbench-2-homepage). Two claims at the same lead time and metric, one vs analysis and one vs ERA5, would today get the same comparability key.
3. reference_conditions is one EvalConditions record, and a grid-valued benchmark has no single reference lead time. cond-eb116e6670bf states the grid instead of a value, so no claim will ever sit exactly at reference conditions, which leaves SOTA and headroom undefined -- the right outcome here (no aggregate by design), reached by accident rather than by rule.
4. secondary_axes is an enum of {cost, latency, throughput, energy, reliability}. P3-S6-T04 plans to record the (variable, level, lead time, metric) grid there; it cannot. A `score_axes` field, or reading the grid off the claims' conditions, is the decision to make.
5. submission_process has no term for "the maintainer scores submitted predictions against public ground truth" (governance.submission_process_note).
6. ceiling_anchor_type is single-valued, and this benchmark anchors deterministic scores on IFS HRES and probabilistic ones on IFS ENS; ceiling_by_category carries the split.
7. The earth-climate/weather-forecasting definition says "scored against observed weather"; WeatherBench 2 is scored against reanalysis (domain.primary_note).
