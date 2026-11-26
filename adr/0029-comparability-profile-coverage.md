# ADR-0029 -- Every pair the corpus uses has a comparability profile

- **Status:** Proposed -- an agent draft (P3-S10-T01). It counts as decided only when two reviewers ratify it
  (05 §5: a taxonomy change needs two, an ADR, a migration script and a full revalidation). Which fields are
  material to a shape is a curation judgement; each profile's `Basis:` and `Reviewer checks:` comments in
  taxonomy/comparability-profiles.yaml are the list to confirm or overturn.
- **Date:** 2026-11-25
- **Taxonomy version:** not affected. Every vocabulary file stays where it is. `taxonomy/comparability-profiles.yaml`,
  which versions itself, goes from 0.2.0 to 0.3.0 (eight profiles added, 187 pairs added, none moved).
- **Facet:** none directly. The profiles are keyed by Facet 3 (evaluation method) and Facet 4 (subject).
- **Change type:** taxonomy control file, additive
- **Supersedes:** --
- **Superseded by:** --
- **Migration:** schema/migrations/0029-comparability-profile-coverage.py (5 rows in 5 files)

## Context

04 §8 resolves a benchmark's material condition fields from its `evaluation_method` and `designed_for_subjects`
through taxonomy/comparability-profiles.yaml, and P3-S10-T01 asks that every benchmark resolve to exactly one
profile before the comparison surface ships. 04 §14 already said the table "should be revised after the first fifty
non-LLM benchmarks"; the corpus now holds 325 curated entries. On main before this change:

- 133 entries resolved to the fallback (`subset_used` alone), and 267 made at least one pair the table did not
  list: 187 distinct unlisted pairs. The vocabulary had grown (environment-state-check, classification-metric,
  numeric-tolerance-match, entrant-relative-ranking; model-in-benchmark-harness, task-specific-supervised-model,
  attack-or-intervention-method) and the table had not.
- Curators had compensated per entry: the fallback entries' `material_extra` lists are what each shape makes
  material in their judgement, written against a stopgap.
- Five entries leave a facet list empty on purpose (hear, superb, zerospeech, epoch-capabilities-index: no
  subject term fits; fiction-livebench: no source states the grading), so no pair exists to look up.

## Decision

**D1. One row per pair, for every pair the curated corpus makes.** Each of the 187 pairs is added to exactly one
profile. Nothing moves between existing rows, so no entry that already resolved from all its pairs changes.

**D2. Eight profiles, each from a stated basis.** Where the existing rows fit, pairs join them (agentic for the
answer-keyed methods under the entrant-built systems; llm-static-text for the remaining prompted-model methods;
model-graded for the judge methods under systems; and so on). Where none fits, a profile is added:

| Profile | Material | Basis |
| --- | --- | --- |
| trained-model | subset_used, training_data_policy | 73 and 61 of the 88 fallback entries of this shape declared them; ADR-0024's surrogate-fit is the same set |
| harnessed-model | harness, reasoning_effort, n_samples, selection_strategy, retries_allowed, subset_used | subjects.yaml ("the number belongs to the model inside that harness"); 16 of 16 declared harness |
| human-participant | human_assistance, subset_used | 04 §8's CASP row; 02 §6: the human-ai-team pairs, where human-assisted entrants are ranked beside servers |
| human-baseline | subset_used | 04 §7: where people sit the test beside machines, their scores are Baselines, not conditions of a machine's claim |
| llm-code | llm-static-text's six, harness, selection_strategy | 04 §8's pass@k row; 8 code entries (n_samples, declared by 6, left an extra: see its reviewer check) |
| model-scored | subset_used, training_data_policy, judge_model (2.0), judge_model_version | 02 §5 model-derived-metric, for entrants that are not prompted |
| relative-ranking | subset_used | entrant-relative-ranking adds no run condition; the pool has no condition field |
| intervention | harness, subset_used | subjects.yaml attack-or-intervention-method; 4 of 4 declared harness |

**D3. The union rule stays.** A benchmark's one resolved profile is the union of the rows its pairs hit
(tools/build/comparability.py, P0-S4-T06); 148 entries compose more than one row. Choosing a single row by
precedence was rejected: it would let two claims share a key while differing on a field the benchmark's own
method makes material, the failure the union exists to prevent.

**D4. Empty facets pin.** The five entries pin `comparability.profile` to the row their own notes describe
(trained-model for the three probed encoders, relative-ranking for the Epoch Capabilities Index, llm-static-text for
Fiction.LiveBench). An entry whose facets are later filled resolves from them, and the migration plans nothing.

**D5. Deferred, not decided here.** Nine entries waive eligibility_track or training_data_eligibility from
eligibility-gated, ADR-0024's signal that the rule should move; geo-bench and massspecgym waive all five prompting
fields that [*, domain-specialist-model] brings through llm-static-text. Both moves touch Matbench Discovery and
WeatherBench 2 or retire waivers, so each needs its own ADR.

## Consequences

- 103 entries' material sets grow (none shrinks, and no waiver becomes stray); fallback entries whose curators had
  declared the new row's fields are unchanged. Every curated entry resolves from its facets or a pin, never the fallback, and
  tests/test_comparability_profiles.py holds it there: a new entry with an unlisted pair fails until the pair is
  given a row.
- Claims on five benchmarks get new denominators. arc-agi-1, casp, fair-universe-higgsml and
  open-asr-leaderboard gain training_data_policy (trained-model), which no claim on them states; forecastbench
  admits agent scaffolds, so the agentic row joins forecasting (4 to 14 fields). Three ForecastBench claims fall
  below frontier_floor (0.27) and the CASP claims that state two of six fields below comparison_floor (0.33); the
  ARC-AGI-1 effort cluster stays above 0.6. The tests that held these claims to the old denominators now name the
  new unknowns. Answering them is claim curation.
- The `Profile` enum grows by eight ids, so schema/generated/*.schema.json and site/src/types/benchmark.d.ts are
  regenerated (`bench schema gen`).
- tests/fixtures/corpus_pins/ is re-derived for every entry whose profiles or material changed.
- `bench report quality` lists every waiver with its field and reason (04 §8: a waiver "shows up in the quality
  dashboard"); tier 4's `material-waived` finding is unchanged.
