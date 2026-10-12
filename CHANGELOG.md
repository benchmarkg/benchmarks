# Changelog

**Schema and taxonomy changes only.** This file records changes to the shape of the data -- the
Pydantic schema in `schema/` and the vocabularies in `taxonomy/` -- because those are what break
consumers and forks. Changes to entries, claims and sources are not listed here; they live in the
git history, and substantive corrections are on the public corrections page.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versions are the
aggregate taxonomy version in `taxonomy/VERSION`, and follow the version rules of
`_plan/03-taxonomy-build-process.md` §8.1: adding a term is MINOR; merging, splitting or retiring a
term is MAJOR; editing definition prose without changing its meaning is PATCH.

**How entries get here.** Every accepted schema or taxonomy change must pass the ADR-plus-migration
gate (`scripts/check_schema_change_gate.py`, see [`GOVERNANCE.md`](GOVERNANCE.md)), and adds one line
under `## [Unreleased]` in the same pull request, in this form:

    - <what changed, in one sentence>. ADR: adr/NNNN-<slug>.md. Migration: schema/migrations/NNNN-<slug>.py

`Migration: none` is allowed only where §8.1 says no migration is required. At a release, the
`Unreleased` entries move under a new version heading with the release date.

## [Unreleased]

### Added

- `Curation.review_checks[]` (the questions a draft leaves for its verifier, each with its field, whether it needs a
  specialist, and its source and quote), `Baseline.subset`, `Baseline.evidence[]` and `Subset.evidence[]`; the
  entries' reviewer checks move out of `curation.notes` into the new field, and their schema findings out of the
  entries into docs/schema-findings-ledger.md. ADR: adr/0026-review-checks-and-evidence.md. Migration:
  schema/migrations/0026-review-checks.py
- The 20-entry checkpoint's additions: `Benchmark.history[]` (dated moves, closures and hand-overs),
  `Benchmark.as_used[]` (how a benchmark is run where that differs from its design), `Paper.doi`,
  `Governance.independence_assessed`, `Data.languages`, `EvalConditions.user_simulator` and
  `user_simulator_version`, `Source.rendered_url` and `Source.extract_preprocessing`; the
  `ground_truth_source` values `formal-verifier` and `released-classifier`; `aggregation_policy: unknown`;
  and the `surrogate-fit` comparability profile (comparability-profiles.yaml 0.2.0). ADR:
  adr/0024-checkpoint-schema-revision.md. Migration: schema/migrations/0024-checkpoint-revision.py
- `Metric.rubric`, an optional block recording a rubric-graded metric's rubric structure (tree or
  flat, rubric, leaf and node counts, leaf scoring, node aggregation, leaves per type). ADR:
  adr/0008-metric-rubric.md. Migration: schema/migrations/0008-metric-rubric.py
- `Leaderboard.conditions`, an optional reference to the EvalConditions record holding a board's
  legality rules and eligibility_track. ADR: adr/0007-leaderboard-conditions.md. Migration:
  schema/migrations/0007-leaderboard-conditions.py
- The taxonomy vocabularies at version 0.1.0: capability (44 terms), evaluation method (27), subject
  (18), domain (19 families, 204 subdomains), and the field vocabularies for data properties,
  ceiling anchors, lifecycle, maintenance status, governance and execution. Pre-freeze drafts;
  nothing is stable before 1.0.0. ADR: none (initial vocabulary). Migration: none
- Pydantic models for every `taxonomy/*.yaml` file (`schema/taxonomy.py`) and the `Source` record
  (`schema/source.py`). ADR: none (initial schema). Migration: none

### Changed

- `lifecycle` is nullable and defaults to null (was `active`); `data.size` is a list of `{count, unit,
  subset, note, source, quote}` rows, headline first (was `{n_items, n_repositories, other_splits,
  languages}`); `license` is derived from `data.dataset_licence` and `execution.code_licence` and may not
  be hand-written; `[statistical-fit, scientific-surrogate-model]` resolves `surrogate-fit`, not
  `forecasting`. ADR: adr/0024-checkpoint-schema-revision.md. Migration:
  schema/migrations/0024-checkpoint-revision.py

### Removed

- The hand-written top-level `license_notes`. ADR: adr/0024-checkpoint-schema-revision.md. Migration:
  schema/migrations/0024-checkpoint-revision.py
