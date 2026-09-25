# ADR-0004 -- No universal score: comparability is a refusal mechanism

- **Status:** Proposed
- **Date:** 2026-09-25
- **Taxonomy version:** not affected
- **Facet:** none directly. The comparability profiles are keyed by the Evaluation method and
  Subject facets (04 §8)
- **Change type:** founding decision (no row in 03 §8.1 applies)
- **Supersedes:** --
- **Superseded by:** --

## Context

Every competitor's instinct is to put results on one scale (00 §2.4, 04 §8):
- BenchmarkList's "Rosetta Stone method" aligns overlapping results onto one scale;
- Epoch's ECI fits a latent-ability IRT model across 58 benchmarks and 266 models;
- Artificial Analysis publishes an Intelligence Index.

Hugging Face retired the most-used leaderboard in open-source AI on the opposite reasoning: that it
*"could encourage people to optimize in irrelevant directions"* (00 §4).

The numbers themselves do not support one scale:
- **Two results on one benchmark are often not the same measurement.** Shots, reasoning effort,
  tools, retries, judge model and harness differ, and mostly go unreported.
- **Across Epoch's 6,598 rows,** the best public corpus, condition completeness is about 0.10 on a
  six-field material profile (04 §8).
- **Across domains, some methods have no cardinal scale:** ordinal grades, pairwise Elo,
  tournament play, unbounded episodic return (02 §8 guard 4).
- **Some benchmarks report a vector with no published aggregate:** AgentDojo, BBQ, VBench,
  ReXrank (02 §5).

A catalogue that refuses to rank non-comparable numbers cannot also publish an index that averages
them. That combination is the one artifact that would destroy the comparability thesis (00 §4).

## Decision

**The index computes no composite or universal score.** Comparability is decided per pair of
claims, and refusal is the default when it cannot be established (00 §5.3, 04 §8).

- **Every claim gets a `comparability_key`.** It is a hash over the benchmark version, metric,
  subset and the material condition fields. The material set is resolved per benchmark from
  `taxonomy/comparability-profiles.yaml`, adjusted by `material_extra` and `material_waived`. The
  key is a build output, "computed, never asserted" (08 invariant I7).
- **Three states in every comparison view** (04 §8):
  - **Same key, nothing unknown:** plot together.
  - **Same key, some fields unknown:** plot together, under a banner naming which material fields
    are unknown on which claim.
  - **Different keys:** refuse. Render a field-by-field diff instead of a chart.
- **`condition_completeness` is displayed on every claim** and is a default sort and filter. A
  number whose conditions are half unknown looks worse than a fully specified one, even when it is
  higher.
- **The only cross-domain axis is headroom consumed:** the position between a defined baseline and
  a defined ceiling. It is computed only where both exist and the method is cardinal, and it is
  shown as a visible `null` otherwise (00 §4, 02 §8).
- **A benchmark whose result is a vector** carries several Metric refs and
  `no_legitimate_aggregate: true`. The UI renders the vector (02 §5).
- **Composites made by others are catalogued as ecosystem artefacts and linked, never computed
  here:** ECI, the AA Intelligence Index and the Rosetta Stone method (04 §11).

## Consequences

- **The named failure mode is refusal saturation** (00 §5.3). If the key hashes too many fields,
  every real pair differs, every comparison is refused and users leave. Given completeness near
  0.10, this is the likely launch state. If it hashes too few, the site grants false
  comparability. Three mechanisms hold the middle:
  - **per-benchmark comparability profiles**, so a community that never varies the judge model
    does not see judge-model nulls forcing refusals;
  - **success criterion S4,** a two-sided refusal-rate band of 40% to 90% over hand-curated pairs
    with a CI gate, because 100% means the key hashes too much and near 0% means too little;
  - **every refusal screen offering a genuinely comparable alternative,** or stating that none
    exists.
- **Low completeness is published, not hidden.** Quantifying the field's reporting opacity is a
  finding. The Phase-3 target is "500 claims at condition_completeness >= 0.6", not 500 claims,
  because ingestion makes claim count free (04 §8).
- **Two thresholds are named constants,** `frontier_floor` and `comparison_floor` in
  `taxonomy/thresholds.yaml`, referenced by name and never typed as numbers (04 §12, 12).
- **"Which model is best?" gets no single answer.** The saturation and headroom views answer per
  domain, and some visitors will want the leaderboard this project declines to be. That is the
  positioning (01), and the cost is accepted.

## Alternatives considered

- **Publish a composite, IRT-fitted or averaged (ECI-style).** Rejected: it contradicts the
  refusal to rank non-comparable numbers, and it becomes the headline figure everyone optimises
  and cites (00 §4).
- **Rank everything, with comparability as a footnote or tooltip.** Rejected: a caveat nobody reads
  does not prevent the harm. The refusal is "the product's signature behaviour, not a caveat on
  it" (00 §2.2).
- **One global material field set.** Rejected: it forces refusals wherever a community does not
  vary a field. That is the refusal-saturation failure, and it is why profiles exist (00 §5.3,
  04 §8).
- **Compare on value alone when conditions are unknown** (hash only the fields that were reported).
  Rejected: two claims that agree only in their ignorance would look confirmed-comparable. The
  unknowns stay in the key, and the second state names them.
- **Headroom as a universal ranking across domains.** Rejected: headroom is undefined for
  non-cardinal methods and unbounded metrics. A universal ordering would have to invent values for
  those, so headroom is reported where it exists and `null` where it does not.

## Migration

None: this is a founding decision. The machinery was built in P0-S4-T06 (comparability) and
P0-S4-T07 (headroom). No composite has ever existed in the corpus.

## Evidence

- 00-vision-and-scope.md §2.2, §2.4 (gap 3), §4 ("Not a single-number ranking"), §5.3 (refusal saturation)
  and §7 (success criterion S4); 04-data-model.md §8 and §11; 02-taxonomy.md §5 and §8.
- The key and completeness:
  - `tools/build/comparability.py`, which computes `comparability_key`, `key_unknown_count` and
    `condition_completeness` from `taxonomy/comparability-profiles.yaml`;
  - `tests/schema/test_comparability.py`, with five hand-computed fixtures in
    `tests/schema/fixtures/comparability/` (P0-S4-T06).
- Headroom: `schema/metric.py`, where `headroom_consumed()` raises `HeadroomNotComputable` where a
  metric has no defined headroom (P0-S4-T07).
- The rules: `schema/validators.py`, rules `headroom-guard-4` and `rating-pool-required` (P0-S4-T08).
