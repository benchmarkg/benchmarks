# Schema field needs: what the three hand-written entries used

<!-- Generated from data/benchmarks/**/*.yaml for P0-S3-T05. The appendix is regenerated
     mechanically; the group judgements above it are the review surface. -->

P0-S3-T05. The three Phase-0 entries -- `data/benchmarks/biology-genetics/casp.yaml`, `data/benchmarks/code/swe-bench.yaml`, `data/benchmarks/robotics-embodiment/roboarena.yaml` -- were written from their primary sources with no
schema in front of the author, on purpose. This list reconciles every field they used against
04-data-model.md §5's Benchmark field reference, and it is the input to ADR 0001 and to
`schema/benchmark.py` (P0-S4-T03).

Each row carries exactly one status:

- **needed** -- the entries need this information and `schema/benchmark.py` must carry it:
  either as the 04 §5 field named, or, where the counterpart column says **not in 04 §5**, as a
  field 04 does not yet define. Those are listed together in [Fields 04 does not define](#fields-04-does-not-define).
- **deferred** -- the entries need it, but it belongs to another entity (ResultClaim, Metric,
  System, Source, BenchmarkVersion) or is derived or machine-written, so it is not a Benchmark
  field a curator writes.
- **unused** -- 04 §5 defines it and none of the three entries used it, or an entry used it for
  something that is not data about the benchmark.

525 distinct field paths appear across the three files: 301 needed, 214 deferred, 10 unused.
Paths are written with `.` between keys and `[]` for a list item.

## By field group

| Group | Status | Entry paths | Used by | 04 counterpart | Finding |
| --- | --- | --- | --- | --- | --- |
| `identity` | **needed** | `aliases`, `full_name`, `id`, `name` (4 paths) | casp, roboarena, swe-bench | `id`, `name`, `aliases[]` | As specified. CASP's `full_name` fits `aliases[]`; no separate field proposed. |
| `tagline` | **needed** | `tagline` (1 path) | casp, roboarena, swe-bench | `tagline` | As specified. All three are under 120 characters. |
| `summary` | **needed** | `summary` (1 path) | casp, roboarena, swe-bench | `description` | The entries call it `summary`; rename to `description` at reconciliation. |
| `release` | **needed** | `release_venue`, `released` (2 paths) | roboarena, swe-bench | **not in 04 §5**; `versions[].released` (§6) | RoboArena and SWE-bench record a first-release date, SWE-bench a venue; CASP dates its editions instead. §6 dates versions, but the benchmark itself has no `released` or `release_venue`. |
| `paper` | **needed** | `paper`, `paper.arxiv`, `paper.title`, `paper.version_read` (4 paths) | roboarena, swe-bench | `curation.sources[]` + `external_ids.*` | The paper is a Source. Its arXiv id has no slot: `external_ids` is a fixed key set with no `arxiv` key. |
| `links` | **needed** | `api`, `dataset`, `homepage`, `leaderboard`, `maintainer_site`, `repository` (6 paths) | casp, roboarena, swe-bench | `homepage`, `repository`; `leaderboards[]` refs; `external_ids.huggingface` | `dataset`, `leaderboard`, `api` and `maintainer_site` are URLs 04 §5 either holds as refs (`leaderboards[]`) or not at all (`api`, `maintainer_site`). |
| `self_description` | **needed** | `self_description` (1 path) | roboarena | `description` + per-field evidence | A quoted self-description, kept as the evidence behind `description`. |
| `platform` | **needed** | `hardware`, `platform` (2 paths) | roboarena | **not in 04 §5** | RoboArena names its robot platform and hardware bill. There is no field for the physical platform a benchmark runs on. |
| `domain` | **needed** | `domain`, `domain.primary`, `domain.secondary` (3 paths) | casp, roboarena, swe-bench | `domain.primary`, `domain.secondary[]` | As specified. |
| `domain_per_edition` | **needed** | `domain.per_edition` (1 path) | casp | `subsets[].domain_override` (§6) | CASP's categories change primary domain. §6's override exists on Subset, not on an edition. |
| `facets` | **needed** | `capability`, `designed_for_subjects`, `evaluation_method`, `lifecycle` (4 paths) | casp, roboarena, swe-bench | `capability[]`, `evaluation_method[]`, `designed_for_subjects[]`, `lifecycle` | As specified. |
| `rejected` | **needed** | `capability_considered_and_rejected`, `capability_considered_and_rejected.reason`, `capability_considered_and_rejected.term`, `domain_considered_and_rejected`, `domain_considered_and_rejected.reason`, `domain_considered_and_rejected.term` ... (12 paths) | casp, roboarena, swe-bench | **not in 04 §5** | All three record near-miss terms with reasons (`*_considered_and_rejected`). Without them a reviewer cannot tell a judged short list from a skipped one. |
| `tag_basis` | **needed** | `capability_basis`, `capability_basis.calibration-uncertainty`, `capability_basis.distribution-shift-generalization`, `capability_basis.generation-fidelity`, `capability_basis.grounding`, `capability_basis.sensorimotor-control` ... (11 paths) | casp, roboarena, swe-bench | `curation.notes` (02 §11 rule 2) | Per-tag justifications. 02 §11 rule 2 routes them to `curation.notes`; the entries want them per term, which that single string cannot index. |
| `observed_subjects` | **needed** | `observed_subjects`, `observed_subjects.values` (2 paths) | swe-bench | **not in 04 §5** | Who actually submits, beside who it was designed for (SWE-bench: built for prompted models, used by agents). |
| `activity` | **needed** | `activity`, `activity_basis.newest_submission` (2 paths) | casp, roboarena, swe-bench | **not in 04 §5**; vocabulary `taxonomy/lifecycle.yaml` field `activity` | The activity vocabulary exists (six terms) but 04 §5 has no `activity` field. CASP also needs a value the vocabulary lacks: `assessment-in-progress`. |
| `schedule` | **needed** | `events`, `events.kind`, `events.name`, `planned_end` (4 paths) | roboarena | **not in 04 §5** | `planned_end` and `events[]`: a live benchmark's announced end and a dated challenge run on it, neither an edition nor a separate benchmark. |
| `maintenance_derived` | **deferred** | `maintenance_signals_seen`, `maintenance_signals_seen.repo_archived`, `maintenance_signals_seen.repo_pushed_at`, `maintenance_signals_seen.signal`, `maintenance_signals_seen.source`, `maintenance_status` (7 paths) | casp, roboarena, swe-bench | `maintenance_status` (derived) and `liveness.*` (machine-written) | Machine-written inputs and a derived verdict. 04 §5's convention is that a derived field may never appear in a hand-written file, so the entries' `maintenance_status: null` lines must be removed, not kept as null. |
| `data_core` | **needed** | `data`, `data.access`, `data.ceiling_anchor_type`, `data.contamination_evidence`, `data.contamination_risk`, `data.data_provenance` ... (8 paths) | casp, roboarena, swe-bench | `data.access`, `data.refresh`, `data.data_provenance[]`, `data.contamination_risk`, `data.contamination_evidence[]`, `data.ceiling_anchor_type` | As specified. RoboArena uses a provenance value the vocabulary lacks (`evaluator-improvised`); SWE-bench wants a `stance` on each contamination-evidence item. |
| `data_access_split` | **needed** | `data.access_by_phase`, `data.records_access`, `data.records_licence`, `data.records_snapshot` (6 paths) | casp, roboarena | **not in 04 §5** | Access that changes over an edition's life (`access_by_phase`), and access to the evaluation records as distinct from the items (`records_*`). |
| `ceiling_per_category` | **needed** | `data.ceiling_basis` (4 paths) | casp | `data.ceiling_anchor_type` (one value); `baselines[]` with a `noise-ceiling` anchor (§7) | CASP needs a ceiling per category, numeric where the source states one (affinity: tau ~0.73) and qualitative elsewhere. One `ceiling_anchor_type` per benchmark cannot hold that; per-subset Baselines can. |
| `licences` | **needed** | `data.code_licence`, `data.dataset_licence`, `data.upstream_licences`, `execution.code_licence` (4 paths) | roboarena, swe-bench | `license`, `license_notes` | Dataset, code and upstream licences are three facts with three answers; one `license` string holds one of them. |
| `size` | **needed** | `size`, `size.languages`, `size.n_items`, `size.n_repositories`, `size.other_splits` (11 paths) | swe-bench | `data.size` {items, unit}; `data.programming_languages` (§5 exemplar only) | Counts per split, and the repositories/languages behind them. `data.languages`, `programming_languages` and `modalities` appear in the §5 exemplar but not in the field reference table. |
| `scale_publication` | **needed** | `scale`, `scale.at_publication` (5 paths) | roboarena | `data.size` | The scale reported at publication. |
| `scale_live` | **deferred** | `scale.live_2026_09_23` (39 paths) | roboarena | `metrics/` adoption series (06 §3.2) | Live counts move daily; they belong in `metrics/`, not the entry. One of them is a real finding: evaluator concentration (one organisation ran 57.6% of RoboArena evaluations) bears on how distributed a distributed benchmark really is, and nothing in 04 records it. |
| `task` | **needed** | `feedback_per_item`, `feedback_per_item.signals`, `task`, `task.input`, `task.output`, `task.reference_solution` ... (16 paths) | roboarena, swe-bench | **not in 04 §5** | What an item is: input, output, scoring, and whether a task set exists at all (RoboArena has none). |
| `metric` | **deferred** | `metric`, `metric.absolute_score`, `metric.ceiling_anchor_type`, `metric.headroom`, `metric.kind`, `metric.model` ... (49 paths) | casp, roboarena, swe-bench | `metrics[]` refs to Metric (§6); `comparability.rating_pool_required`; RatingPool (§9) | Belongs to the Metric and RatingPool entities (P0-S4-T07). Findings for them: a ranking `authority` (CASP has two official rankings), an official-row threshold, and provisional rows sharing a board. |
| `saturation` | **deferred** | `saturation_by_category`, `saturation_by_category.category`, `saturation_by_category.quote`, `saturation_by_category.source`, `saturation_by_category.state` (5 paths) | casp | derived headroom per Subset (02 §8) | Saturation per category is derived from claims, and only possible once subsets carry their own claims. |
| `editions` | **deferred** | `editions`, `editions.cadence`, `editions.current`, `editions.first_edition`, `editions.list` (60 paths) | casp | `versions[]` with `version_kind: edition` (§6) | Editions map onto BenchmarkVersion. The entry's finding, that editions are new test sets and not revisions, is what `version_kind: edition` exists for; per-edition participation and assessors are not in §6. |
| `entrant_classes` | **needed** | `entrant_classes`, `entrant_classes.class`, `entrant_classes.deadline`, `entrant_classes.ranked_separately`, `entrant_classes_history` (5 paths) | casp | **not in 04 §5** | Separately ranked entrant classes (CASP: servers vs human groups), each with its own deadline. |
| `governance_core` | **needed** | `governance`, `governance.independence_flags`, `governance.maintainer`, `governance.maintainer_type`, `governance.submission_process` (6 paths) | casp, roboarena, swe-bench | `governance.maintainer_type`, `governance.maintainers[]`, `governance.submission_process`, `governance.independence_flags[]` | As specified, with the entries' `maintainer` as `maintainers[]` Organization refs. SWE-bench wants `submission_process` multi-valued or a new `artifact-backed` term. |
| `governance_extra` | **needed** | `governance.admission`, `governance.evaluation_budget`, `governance.funding`, `governance.independence_policy`, `governance.known_limitation`, `governance.participation` (8 paths) | casp, roboarena | **not in 04 §5** | Funding, admission rules, per-submitter evaluation budgets and independence policy all change how a result may be read. |
| `reviewer_notes` | **unused** | `governance.reviewer_check` (7 paths) | casp, roboarena, swe-bench | `curation.notes` | Notes addressed to the reviewer of this draft, not facts about the benchmark. Fold into `curation.notes` or drop at approval. |
| `execution_core` | **needed** | `execution`, `execution.compute_tier`, `execution.reproducibility_tier` (3 paths) | casp, roboarena, swe-bench | `execution.compute_tier`, `execution.reproducibility_tier` | As specified. |
| `execution_vocab` | **needed** | `execution.harness_availability`, `execution.reproducibility_blockers` (2 paths) | casp, roboarena, swe-bench | **not in 04 §5**; vocabulary `taxonomy/execution.yaml` | `reproducibility_blockers` and `harness_availability` have vocabularies in `execution.yaml` but no field in 04 §5. |
| `execution_role` | **needed** | `execution.compute_tier_by_role`, `execution.submitter_needs_no_robot` (4 paths) | roboarena | **not in 04 §5** | Cost by role: a RoboArena submitter needs a server, an evaluator a robot. One tier describes neither. |
| `harness` | **needed** | `execution.harness`, `execution.harness_gotcha` (2 paths) | swe-bench | `execution.runnable_via[]`, `execution.inspect_evals_id` | The harness an outside runner would use. |
| `submission_channel` | **needed** | `execution.submission_channel` (1 path) | casp | **not in 04 §5** | How entries are submitted (CASP: a web form per category with its own deadline). |
| `interop` | **needed** | `interop`, `interop.arxiv`, `interop.eee_benchmark_name`, `interop.epoch_benchmark_id`, `interop.huggingface_dataset`, `interop.inspect_evals_id` (6 paths) | swe-bench | `external_ids.*`, `execution.inspect_evals_id` | `epoch`, `inspect_evals`, `huggingface` and `every_eval_ever` exist. `arxiv` does not. |
| `lineage` | **needed** | `lineage`, `lineage.forks`, `lineage.role`, `lineage.variants`, `lineage.views` (15 paths) | swe-bench | `lineage.*` (supersedes, extended_by, subset_of, ...) | SWE-bench needs three relations 04 collapses: same-maintainer variants, other-maintainer forks, and views that are only filters. |
| `results` | **deferred** | `results_board_summary`, `results_board_summary.derived`, `results_board_summary.rows`, `results_board_summary.rows_checked`, `results_board_summary.source`, `results_observed` ... (30 paths) | casp, roboarena, swe-bench | ResultClaim (§7), System (§7); P0-S4-T05 | Results are claims, not benchmark fields. Findings for ResultClaim: `scaffold`, `checked`/`official`, `entrant_class` (including an assessor-run baseline that must not read as a winner), a rating's pool and snapshot. |
| `policy_identity` | **deferred** | `policy_identity`, `policy_identity.aliasing`, `policy_identity.linked_paper_example`, `policy_identity.open_source_flag_per_policy`, `policy_identity.open_source_quote`, `policy_identity.open_source_source` ... (13 paths) | roboarena | System (§7) and the alias tables (§10) | Backend ids, display names and an alias that names another system: the System entity and its aliases, not the Benchmark. |
| `curation_core` | **needed** | `curation`, `curation.drafted_by`, `curation.drafted_on`, `curation.retrieved_on`, `curation.verification_status` (5 paths) | casp, roboarena, swe-bench | `curation.added_by`, `curation.added_on`, `curation.last_verified`, `curation.verification_status`, `curation.sources[]` | As specified: `drafted_by`/`drafted_on`/`retrieved_on` are `added_by`/`added_on`/`last_verified`. |
| `curation_sources_inline` | **deferred** | `curation.sources` (11 paths) | casp, roboarena, swe-bench | the `Source` record (§9; `schema/source.py`) | Inline source descriptions (url, kind, hash, extract mode, personal data) now live in `data/sources/`. `curation.sources[]` becomes a list of Source ids. |
| `curation_extra` | **needed** | `curation.not_yet_available`, `curation.personal_data_excluded`, `curation.unreachable` (10 paths) | casp, roboarena, swe-bench | **not in 04 §5** | A source that 403s (`unreachable`), one that will exist but does not yet (`not_yet_available`), and personal data deliberately excluded. Each changes what may be claimed. |
| `evidence` | **needed** | *(across all blocks)* (93 paths) | casp, roboarena, swe-bench | **not in 04 §5** for Benchmark fields | Per-field `source` + `quote` (or a `quote_locator` where the value sits in structured data). 04 gives ResultClaim field provenance but Benchmark only a flat `curation.sources[]`; the quote-substring validator needs to know which source a number came from. |
| `field_notes` | **needed** | *(across all blocks)* (27 paths) | casp, roboarena, swe-bench | `curation.notes` | Per-field notes (`*_note`, `*_basis`, `*_caveat`). One `curation.notes` string cannot say which field a note is about. |
| `meta` | **unused** | `_schema_findings`, `_schema_findings.field`, `_schema_findings.need` (3 paths) | casp, roboarena, swe-bench | — | `_schema_findings`: this task's input, not data. Remove from the entries once P0-S4-T10 reconciles them. |

## 04 §5 fields none of the entries used

Every one is **unused** by these three entries. Two consequences matter now: the admissibility
block, which 04 §15 item 12 makes a prerequisite, is missing from all three, so none of them
validates as written; and no entry declares `reference_conditions`, so every headroom is null.

| 04 §5 field | Status | Note |
| --- | --- | --- |
| `external_ids.every_eval_ever` | **unused** | SWE-bench records `interop.eee_benchmark_name`, the join value, but not under this key. |
| `croissant_url` | **unused** | None of the three sets it; SWE-bench's Hugging Face dataset has one. |
| `learned_entrant_evidence[]` | **unused** | **Required at stub** (tier 3, >= 1) and absent from all three. Every entry would fail validation today. |
| `evaluation_target` | **unused** | Required at stub; absent from all three. |
| `execution_mode` | **unused** | Absent; RoboArena would be `physical-trial`. |
| `ground_truth_source` | **unused** | Absent; CASP would be `experimental`. |
| `reproducible_by_third_party` | **unused** | Absent; the entries say it in `reproducibility_note` prose instead. |
| `data.submission_limit` | **unused** | Absent. RoboArena's per-submitter weekly budget is a close cousin. |
| `training_data_eligibility_tiers[]` | **unused** | Absent; none of the three has tiers. |
| `execution.est_runtime_hours` | **unused** | Absent. |
| `execution.est_cost_usd` | **unused** | Absent. |
| `execution.est_participant_cost_usd` | **unused** | Absent. |
| `execution.inspect_evals_available` | **unused** | Derived; correctly absent. |
| `comparability.profile` | **unused** | Absent; derivable from the facets. |
| `comparability.material_extra[]` | **unused** | Absent. SWE-bench's scaffold finding is a candidate. |
| `comparability.material_waived[]` | **unused** | Absent. |
| `reference_conditions` | **unused** | Absent from all three, so SOTA and headroom are null for each (02 §8). |
| `aggregation_policy` | **unused** | Absent. CASP (two official rankings) is the case the enum exists for. |
| `headline_metric` | **unused** | Absent. |
| `no_legitimate_aggregate` | **unused** | Absent. |
| `secondary_axes[]` | **unused** | Absent. |
| `maintenance_status_contested` | **unused** | Absent; nothing is contested. |
| `contested_source` | **unused** | Absent (conditional). |
| `contested_statement_date` | **unused** | Absent (conditional). |
| `subsets[]` | **unused** | Absent. CASP's categories and SWE-bench's splits are candidates. |
| `baselines[]` | **unused** | Absent; CASP's assessor-run AlphaFold 3 is one, recorded as a result instead. |
| `tags[]` | **unused** | Absent. |
| `ingestion` | **unused** | Machine-written; correctly absent from hand-written entries. |
| `curation.stewardship` | **unused** | Derived; correctly absent. |
| `curation.confidence` | **unused** | Absent. |

## Fields 04 does not define

The **needed** groups whose counterpart is **not in 04 §5**: the input to ADR 0001. Each names
what the schema has to decide, not a field name it has to adopt; the entries' own names were
invented without a schema and are not proposals.

- **`release`** (roboarena, swe-bench). RoboArena and SWE-bench record a first-release date, SWE-bench a venue; CASP dates its editions instead. §6 dates versions, but the benchmark itself has no `released` or `release_venue`.
- **`platform`** (roboarena). RoboArena names its robot platform and hardware bill. There is no field for the physical platform a benchmark runs on.
- **`rejected`** (casp, roboarena, swe-bench). All three record near-miss terms with reasons (`*_considered_and_rejected`). Without them a reviewer cannot tell a judged short list from a skipped one.
- **`observed_subjects`** (swe-bench). Who actually submits, beside who it was designed for (SWE-bench: built for prompted models, used by agents).
- **`activity`** (casp, roboarena, swe-bench). The activity vocabulary exists (six terms) but 04 §5 has no `activity` field. CASP also needs a value the vocabulary lacks: `assessment-in-progress`.
- **`schedule`** (roboarena). `planned_end` and `events[]`: a live benchmark's announced end and a dated challenge run on it, neither an edition nor a separate benchmark.
- **`data_access_split`** (casp, roboarena). Access that changes over an edition's life (`access_by_phase`), and access to the evaluation records as distinct from the items (`records_*`).
- **`task`** (roboarena, swe-bench). What an item is: input, output, scoring, and whether a task set exists at all (RoboArena has none).
- **`entrant_classes`** (casp). Separately ranked entrant classes (CASP: servers vs human groups), each with its own deadline.
- **`governance_extra`** (casp, roboarena). Funding, admission rules, per-submitter evaluation budgets and independence policy all change how a result may be read.
- **`execution_vocab`** (casp, roboarena, swe-bench). `reproducibility_blockers` and `harness_availability` have vocabularies in `execution.yaml` but no field in 04 §5.
- **`execution_role`** (roboarena). Cost by role: a RoboArena submitter needs a server, an evaluator a robot. One tier describes neither.
- **`submission_channel`** (casp). How entries are submitted (CASP: a web form per category with its own deadline).
- **`curation_extra`** (casp, roboarena, swe-bench). A source that 403s (`unreachable`), one that will exist but does not yet (`not_yet_available`), and personal data deliberately excluded. Each changes what may be claimed.
- **`evidence`** (casp, roboarena, swe-bench). Per-field `source` + `quote` (or a `quote_locator` where the value sits in structured data). 04 gives ResultClaim field provenance but Benchmark only a flat `curation.sources[]`; the quote-substring validator needs to know which source a number came from.

Vocabulary values the entries needed that `taxonomy/` lacks, for the vocabulary owners rather
than the schema: `activity: assessment-in-progress` (CASP), `data_provenance:
evaluator-improvised` (RoboArena), and a `submission_process` term for artifact-backed
self-reporting (SWE-bench). CASP's `_schema_findings` also lists four draft definitions that
assume CASP has no leaderboard or ranks humans separately; those are review notes on the
approved vocabularies, recorded here so they are not lost.

## Appendix: every field path

Mechanical: each path the three files use, its group from the table above, and the status it
inherits.

| Path | Status | Group | Used by |
| --- | --- | --- | --- |
| `_schema_findings` | unused | `meta` | casp, roboarena, swe-bench |
| `_schema_findings[].field` | unused | `meta` | casp, roboarena, swe-bench |
| `_schema_findings[].need` | unused | `meta` | casp, roboarena, swe-bench |
| `activity` | needed | `activity` | casp, roboarena, swe-bench |
| `activity_basis` | needed | `field_notes` | swe-bench |
| `activity_basis.caveat` | needed | `field_notes` | swe-bench |
| `activity_basis.newest_submission` | needed | `activity` | swe-bench |
| `activity_basis.quote` | needed | `evidence` | swe-bench |
| `activity_basis.source` | needed | `evidence` | swe-bench |
| `activity_note` | needed | `field_notes` | casp |
| `activity_quote` | needed | `evidence` | roboarena |
| `activity_source` | needed | `evidence` | roboarena |
| `aliases` | needed | `identity` | casp, swe-bench |
| `api` | needed | `links` | roboarena |
| `capability` | needed | `facets` | casp, roboarena, swe-bench |
| `capability_basis` | needed | `tag_basis` | casp, roboarena |
| `capability_basis.calibration-uncertainty` | needed | `tag_basis` | casp |
| `capability_basis.calibration-uncertainty.quote` | needed | `evidence` | casp |
| `capability_basis.calibration-uncertainty.reason` | needed | `tag_basis` | casp |
| `capability_basis.calibration-uncertainty.source` | needed | `evidence` | casp |
| `capability_basis.distribution-shift-generalization` | needed | `tag_basis` | casp |
| `capability_basis.distribution-shift-generalization.quote` | needed | `evidence` | casp |
| `capability_basis.distribution-shift-generalization.reason` | needed | `tag_basis` | casp |
| `capability_basis.distribution-shift-generalization.source` | needed | `evidence` | casp |
| `capability_basis.generation-fidelity` | needed | `tag_basis` | casp |
| `capability_basis.grounding` | needed | `tag_basis` | roboarena |
| `capability_basis.sensorimotor-control` | needed | `tag_basis` | roboarena |
| `capability_considered_and_rejected` | needed | `rejected` | casp, roboarena, swe-bench |
| `capability_considered_and_rejected[].reason` | needed | `rejected` | casp, roboarena, swe-bench |
| `capability_considered_and_rejected[].term` | needed | `rejected` | casp, roboarena, swe-bench |
| `curation` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.drafted_by` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.drafted_on` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.extract_note` | needed | `field_notes` | casp |
| `curation.not_yet_available` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].consequence` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].expected` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].what` | needed | `curation_extra` | casp |
| `curation.personal_data_excluded` | needed | `curation_extra` | roboarena |
| `curation.personal_data_excluded[].source` | needed | `evidence` | roboarena |
| `curation.personal_data_excluded[].what` | needed | `curation_extra` | roboarena |
| `curation.retrieved_on` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.sources` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.sources[].bundle_hash_changes_on_redeploy` | deferred | `curation_sources_inline` | roboarena |
| `curation.sources[].contains_personal_data` | deferred | `curation_sources_inline` | roboarena |
| `curation.sources[].doi` | deferred | `curation_sources_inline` | casp |
| `curation.sources[].extract` | deferred | `curation_sources_inline` | roboarena, swe-bench |
| `curation.sources[].extract_warning` | deferred | `curation_sources_inline` | swe-bench |
| `curation.sources[].id` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.sources[].kind` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.sources[].text_sha256` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.sources[].title` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.sources[].url` | deferred | `curation_sources_inline` | casp, roboarena, swe-bench |
| `curation.unreachable` | needed | `curation_extra` | swe-bench |
| `curation.unreachable[].consequence` | needed | `curation_extra` | swe-bench |
| `curation.unreachable[].http_status` | needed | `curation_extra` | swe-bench |
| `curation.unreachable[].url` | needed | `curation_extra` | swe-bench |
| `curation.verification_status` | needed | `curation_core` | casp, roboarena, swe-bench |
| `data` | needed | `data_core` | casp, roboarena, swe-bench |
| `data.access` | needed | `data_core` | casp, roboarena, swe-bench |
| `data.access_basis` | needed | `field_notes` | swe-bench |
| `data.access_by_phase` | needed | `data_access_split` | casp |
| `data.access_by_phase.after_edition` | needed | `data_access_split` | casp |
| `data.access_by_phase.after_edition_quote` | needed | `evidence` | casp |
| `data.access_by_phase.after_edition_source` | needed | `evidence` | casp |
| `data.access_by_phase.during_edition` | needed | `data_access_split` | casp |
| `data.access_by_phase.note` | needed | `field_notes` | casp |
| `data.access_note` | needed | `field_notes` | roboarena |
| `data.access_source` | needed | `evidence` | swe-bench |
| `data.ceiling_anchor_type` | needed | `data_core` | casp, swe-bench |
| `data.ceiling_basis` | needed | `ceiling_per_category` | casp |
| `data.ceiling_basis[].category` | needed | `ceiling_per_category` | casp |
| `data.ceiling_basis[].metric` | needed | `ceiling_per_category` | casp |
| `data.ceiling_basis[].quote` | needed | `evidence` | casp |
| `data.ceiling_basis[].source` | needed | `evidence` | casp |
| `data.ceiling_basis[].value` | needed | `ceiling_per_category` | casp |
| `data.ceiling_note` | needed | `field_notes` | casp, swe-bench |
| `data.code_licence` | needed | `licences` | swe-bench |
| `data.code_licence_source` | needed | `evidence` | swe-bench |
| `data.contamination_basis` | needed | `field_notes` | casp, roboarena |
| `data.contamination_caveat` | needed | `field_notes` | casp |
| `data.contamination_evidence` | needed | `data_core` | swe-bench |
| `data.contamination_evidence[].quote` | needed | `evidence` | swe-bench |
| `data.contamination_evidence[].source` | needed | `evidence` | swe-bench |
| `data.contamination_evidence[].stance` | needed | `data_core` | swe-bench |
| `data.contamination_notes` | needed | `field_notes` | swe-bench |
| `data.contamination_quote` | needed | `evidence` | casp |
| `data.contamination_risk` | needed | `data_core` | casp, roboarena, swe-bench |
| `data.contamination_source` | needed | `evidence` | casp |
| `data.data_provenance` | needed | `data_core` | casp, roboarena, swe-bench |
| `data.data_provenance_note` | needed | `field_notes` | casp, roboarena, swe-bench |
| `data.dataset_licence` | needed | `licences` | swe-bench |
| `data.records_access` | needed | `data_access_split` | roboarena |
| `data.records_licence` | needed | `data_access_split` | roboarena |
| `data.records_quote` | needed | `evidence` | roboarena |
| `data.records_snapshot` | needed | `data_access_split` | roboarena |
| `data.records_source` | needed | `evidence` | roboarena |
| `data.refresh` | needed | `data_core` | casp, roboarena, swe-bench |
| `data.refresh_note` | needed | `field_notes` | swe-bench |
| `data.upstream_licences` | needed | `licences` | swe-bench |
| `dataset` | needed | `links` | roboarena, swe-bench |
| `designed_for_subjects` | needed | `facets` | casp, roboarena, swe-bench |
| `designed_for_subjects_basis` | needed | `tag_basis` | casp, swe-bench |
| `designed_for_subjects_note` | needed | `tag_basis` | roboarena |
| `domain` | needed | `domain` | casp, roboarena, swe-bench |
| `domain.per_edition` | needed | `domain_per_edition` | casp |
| `domain.per_edition_note` | needed | `field_notes` | casp |
| `domain.primary` | needed | `domain` | casp, roboarena, swe-bench |
| `domain.secondary` | needed | `domain` | casp, roboarena, swe-bench |
| `domain.secondary_basis` | needed | `field_notes` | roboarena |
| `domain.secondary_quote` | needed | `evidence` | roboarena |
| `domain.secondary_source` | needed | `evidence` | roboarena |
| `domain_considered_and_rejected` | needed | `rejected` | roboarena |
| `domain_considered_and_rejected[].quote` | needed | `evidence` | roboarena |
| `domain_considered_and_rejected[].reason` | needed | `rejected` | roboarena |
| `domain_considered_and_rejected[].source` | needed | `evidence` | roboarena |
| `domain_considered_and_rejected[].term` | needed | `rejected` | roboarena |
| `editions` | deferred | `editions` | casp |
| `editions.cadence` | deferred | `editions` | casp |
| `editions.cadence.quote` | deferred | `editions` | casp |
| `editions.cadence.source` | deferred | `editions` | casp |
| `editions.cadence.value` | deferred | `editions` | casp |
| `editions.current` | deferred | `editions` | casp |
| `editions.first_edition` | deferred | `editions` | casp |
| `editions.list` | deferred | `editions` | casp |
| `editions.list[].assessors_named` | deferred | `editions` | casp |
| `editions.list[].assessors_source` | deferred | `editions` | casp |
| `editions.list[].categories` | deferred | `editions` | casp |
| `editions.list[].categories_new` | deferred | `editions` | casp |
| `editions.list[].categories_new_quote` | deferred | `editions` | casp |
| `editions.list[].categories_new_source` | deferred | `editions` | casp |
| `editions.list[].categories_source` | deferred | `editions` | casp |
| `editions.list[].id` | deferred | `editions` | casp |
| `editions.list[].participation` | deferred | `editions` | casp |
| `editions.list[].participation.caveat` | deferred | `editions` | casp |
| `editions.list[].participation.preferred` | deferred | `editions` | casp |
| `editions.list[].participation.quote` | deferred | `editions` | casp |
| `editions.list[].participation.source` | deferred | `editions` | casp |
| `editions.list[].participation.sources_disagree` | deferred | `editions` | casp |
| `editions.list[].participation.unit` | deferred | `editions` | casp |
| `editions.list[].participation.value` | deferred | `editions` | casp |
| `editions.list[].participation.values` | deferred | `editions` | casp |
| `editions.list[].participation.values[].claim` | deferred | `editions` | casp |
| `editions.list[].participation.values[].quote` | deferred | `editions` | casp |
| `editions.list[].participation.values[].source` | deferred | `editions` | casp |
| `editions.list[].prediction_season` | deferred | `editions` | casp |
| `editions.list[].prediction_season.sources_disagree` | deferred | `editions` | casp |
| `editions.list[].prediction_season.values` | deferred | `editions` | casp |
| `editions.list[].prediction_season.values[].quote` | deferred | `editions` | casp |
| `editions.list[].prediction_season.values[].source` | deferred | `editions` | casp |
| `editions.list[].prediction_season.values[].value` | deferred | `editions` | casp |
| `editions.list[].proceedings` | deferred | `editions` | casp |
| `editions.list[].results_due` | deferred | `editions` | casp |
| `editions.list[].results_due.conflicts_with` | deferred | `editions` | casp |
| `editions.list[].results_due.conflicts_with.quote` | deferred | `editions` | casp |
| `editions.list[].results_due.conflicts_with.source` | deferred | `editions` | casp |
| `editions.list[].results_due.quote` | deferred | `editions` | casp |
| `editions.list[].results_due.source` | deferred | `editions` | casp |
| `editions.list[].results_due.value` | deferred | `editions` | casp |
| `editions.list[].server_only_quote` | deferred | `editions` | casp |
| `editions.list[].server_only_source` | deferred | `editions` | casp |
| `editions.list[].server_only_targets` | deferred | `editions` | casp |
| `editions.list[].site_error_noted` | deferred | `editions` | casp |
| `editions.list[].site_error_noted.note` | deferred | `editions` | casp |
| `editions.list[].site_error_noted.quote` | deferred | `editions` | casp |
| `editions.list[].site_error_noted.source` | deferred | `editions` | casp |
| `editions.list[].status` | deferred | `editions` | casp |
| `editions.list[].targets_assessed` | deferred | `editions` | casp |
| `editions.list[].targets_assessed.quote` | deferred | `editions` | casp |
| `editions.list[].targets_assessed.source` | deferred | `editions` | casp |
| `editions.list[].targets_assessed.unit` | deferred | `editions` | casp |
| `editions.list[].targets_assessed.value` | deferred | `editions` | casp |
| `editions.list[].targets_released` | deferred | `editions` | casp |
| `editions.list[].targets_released.quote` | deferred | `editions` | casp |
| `editions.list[].targets_released.source` | deferred | `editions` | casp |
| `editions.list[].targets_released.value` | deferred | `editions` | casp |
| `editions.list[].year` | deferred | `editions` | casp |
| `entrant_classes` | needed | `entrant_classes` | casp |
| `entrant_classes[].class` | needed | `entrant_classes` | casp |
| `entrant_classes[].deadline` | needed | `entrant_classes` | casp |
| `entrant_classes[].deadline_quote` | needed | `evidence` | casp |
| `entrant_classes[].deadline_source` | needed | `evidence` | casp |
| `entrant_classes[].quote` | needed | `evidence` | casp |
| `entrant_classes[].ranked_separately` | needed | `entrant_classes` | casp |
| `entrant_classes[].source` | needed | `evidence` | casp |
| `entrant_classes_history` | needed | `entrant_classes` | casp |
| `entrant_classes_history.quote` | needed | `evidence` | casp |
| `entrant_classes_history.source` | needed | `evidence` | casp |
| `evaluation_method` | needed | `facets` | casp, roboarena, swe-bench |
| `evaluation_method_considered_and_rejected` | needed | `rejected` | roboarena |
| `evaluation_method_considered_and_rejected[].reason` | needed | `rejected` | roboarena |
| `evaluation_method_considered_and_rejected[].term` | needed | `rejected` | roboarena |
| `evaluation_method_note` | needed | `tag_basis` | casp |
| `events` | needed | `schedule` | roboarena |
| `events[].kind` | needed | `schedule` | roboarena |
| `events[].name` | needed | `schedule` | roboarena |
| `events[].quote` | needed | `evidence` | roboarena |
| `events[].source` | needed | `evidence` | roboarena |
| `execution` | needed | `execution_core` | casp, roboarena, swe-bench |
| `execution.code_licence` | needed | `licences` | roboarena |
| `execution.code_licence_source` | needed | `evidence` | roboarena |
| `execution.compute_note` | needed | `field_notes` | roboarena, swe-bench |
| `execution.compute_tier` | needed | `execution_core` | casp, roboarena, swe-bench |
| `execution.compute_tier_by_role` | needed | `execution_role` | roboarena |
| `execution.compute_tier_by_role.evaluator` | needed | `execution_role` | roboarena |
| `execution.compute_tier_by_role.submitter` | needed | `execution_role` | roboarena |
| `execution.harness` | needed | `harness` | swe-bench |
| `execution.harness_availability` | needed | `execution_vocab` | casp, roboarena, swe-bench |
| `execution.harness_gotcha` | needed | `harness` | swe-bench |
| `execution.harness_gotcha.quote` | needed | `evidence` | swe-bench |
| `execution.harness_gotcha.source` | needed | `evidence` | swe-bench |
| `execution.harness_note` | needed | `field_notes` | casp, roboarena |
| `execution.harness_quote` | needed | `evidence` | roboarena, swe-bench |
| `execution.harness_source` | needed | `evidence` | roboarena, swe-bench |
| `execution.reproducibility_blockers` | needed | `execution_vocab` | casp, roboarena, swe-bench |
| `execution.reproducibility_blockers_note` | needed | `field_notes` | casp |
| `execution.reproducibility_note` | needed | `field_notes` | casp, roboarena |
| `execution.reproducibility_tier` | needed | `execution_core` | casp, roboarena, swe-bench |
| `execution.submission_channel` | needed | `submission_channel` | casp |
| `execution.submission_channel.quote` | needed | `evidence` | casp |
| `execution.submission_channel.source` | needed | `evidence` | casp |
| `execution.submitter_needs_no_robot` | needed | `execution_role` | roboarena |
| `execution.submitter_needs_no_robot.quote` | needed | `evidence` | roboarena |
| `execution.submitter_needs_no_robot.source` | needed | `evidence` | roboarena |
| `feedback_per_item` | needed | `task` | roboarena |
| `feedback_per_item.quote` | needed | `evidence` | roboarena |
| `feedback_per_item.quote_note` | needed | `field_notes` | roboarena |
| `feedback_per_item.signals` | needed | `task` | roboarena |
| `feedback_per_item.signals[].kind` | needed | `task` | roboarena |
| `feedback_per_item.signals[].ranks` | needed | `task` | roboarena |
| `feedback_per_item.source` | needed | `evidence` | roboarena |
| `full_name` | needed | `identity` | casp |
| `governance` | needed | `governance_core` | casp, roboarena, swe-bench |
| `governance.admission` | needed | `governance_extra` | roboarena |
| `governance.admission.quote` | needed | `evidence` | roboarena |
| `governance.admission.safety_screen` | needed | `governance_extra` | roboarena |
| `governance.admission.source` | needed | `evidence` | roboarena |
| `governance.evaluation_budget` | needed | `governance_extra` | roboarena |
| `governance.evaluation_budget.comparability_consequence` | needed | `governance_extra` | roboarena |
| `governance.evaluation_budget.quote` | needed | `evidence` | roboarena |
| `governance.evaluation_budget.source` | needed | `evidence` | roboarena |
| `governance.funding` | needed | `governance_extra` | casp |
| `governance.funding.quote` | needed | `evidence` | casp |
| `governance.funding.source` | needed | `evidence` | casp |
| `governance.independence_flags` | needed | `governance_core` | casp, roboarena, swe-bench |
| `governance.independence_flags[].flag` | needed | `governance_core` | swe-bench |
| `governance.independence_flags[].quote` | needed | `evidence` | swe-bench |
| `governance.independence_flags[].reviewer_check` | unused | `reviewer_notes` | swe-bench |
| `governance.independence_flags[].source` | needed | `evidence` | swe-bench |
| `governance.independence_flags_note` | needed | `field_notes` | casp, roboarena |
| `governance.independence_policy` | needed | `governance_extra` | casp |
| `governance.independence_policy.quote` | needed | `evidence` | casp |
| `governance.independence_policy.source` | needed | `evidence` | casp |
| `governance.known_limitation` | needed | `governance_extra` | roboarena |
| `governance.known_limitation.quote` | needed | `evidence` | roboarena |
| `governance.known_limitation.source` | needed | `evidence` | roboarena |
| `governance.maintainer` | needed | `governance_core` | casp, swe-bench |
| `governance.maintainer_note` | needed | `field_notes` | casp, roboarena |
| `governance.maintainer_type` | needed | `governance_core` | casp, roboarena, swe-bench |
| `governance.maintainer_type_source` | needed | `evidence` | roboarena |
| `governance.participation` | needed | `governance_extra` | casp |
| `governance.participation.quote` | needed | `evidence` | casp |
| `governance.participation.source` | needed | `evidence` | casp |
| `governance.reviewer_check` | unused | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].finding` | unused | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].note` | unused | `reviewer_notes` | roboarena |
| `governance.reviewer_check[].quote` | unused | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].source` | unused | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].why_no_flag` | unused | `reviewer_notes` | casp |
| `governance.submission_process` | needed | `governance_core` | casp, roboarena, swe-bench |
| `governance.submission_process_note` | needed | `field_notes` | casp, roboarena, swe-bench |
| `governance.submission_quote` | needed | `evidence` | swe-bench |
| `governance.submission_source` | needed | `evidence` | swe-bench |
| `hardware` | needed | `platform` | roboarena |
| `hardware.quote` | needed | `evidence` | roboarena |
| `hardware.source` | needed | `evidence` | roboarena |
| `homepage` | needed | `links` | casp, roboarena, swe-bench |
| `id` | needed | `identity` | casp, roboarena, swe-bench |
| `interop` | needed | `interop` | swe-bench |
| `interop.arxiv` | needed | `interop` | swe-bench |
| `interop.eee_benchmark_name` | needed | `interop` | swe-bench |
| `interop.epoch_benchmark_id` | needed | `interop` | swe-bench |
| `interop.huggingface_dataset` | needed | `interop` | swe-bench |
| `interop.inspect_evals_id` | needed | `interop` | swe-bench |
| `leaderboard` | needed | `links` | swe-bench |
| `lifecycle` | needed | `facets` | casp, roboarena, swe-bench |
| `lifecycle_note` | needed | `field_notes` | swe-bench |
| `lineage` | needed | `lineage` | swe-bench |
| `lineage.forks` | needed | `lineage` | swe-bench |
| `lineage.forks[].id` | needed | `lineage` | swe-bench |
| `lineage.forks[].maintainer` | needed | `lineage` | swe-bench |
| `lineage.forks[].quote` | needed | `evidence` | swe-bench |
| `lineage.forks[].source` | needed | `evidence` | swe-bench |
| `lineage.role` | needed | `lineage` | swe-bench |
| `lineage.variants` | needed | `lineage` | swe-bench |
| `lineage.variants[].co_maintainer` | needed | `lineage` | swe-bench |
| `lineage.variants[].id` | needed | `lineage` | swe-bench |
| `lineage.variants[].n_items` | needed | `lineage` | swe-bench |
| `lineage.variants[].n_items_history` | needed | `lineage` | swe-bench |
| `lineage.variants[].n_items_history[].quote` | needed | `evidence` | swe-bench |
| `lineage.variants[].n_items_history[].source` | needed | `evidence` | swe-bench |
| `lineage.variants[].n_items_history[].value` | needed | `lineage` | swe-bench |
| `lineage.variants[].n_items_note` | needed | `field_notes` | swe-bench |
| `lineage.variants[].quote` | needed | `evidence` | swe-bench |
| `lineage.variants[].relation` | needed | `lineage` | swe-bench |
| `lineage.variants[].source` | needed | `evidence` | swe-bench |
| `lineage.views` | needed | `lineage` | swe-bench |
| `lineage.views[].name` | needed | `lineage` | swe-bench |
| `lineage.views[].of` | needed | `lineage` | swe-bench |
| `lineage.views[].quote` | needed | `evidence` | swe-bench |
| `lineage.views[].source` | needed | `evidence` | swe-bench |
| `maintainer_site` | needed | `links` | casp |
| `maintenance_signals_seen` | deferred | `maintenance_derived` | casp, roboarena, swe-bench |
| `maintenance_signals_seen.repo_archived` | deferred | `maintenance_derived` | swe-bench |
| `maintenance_signals_seen.repo_pushed_at` | deferred | `maintenance_derived` | swe-bench |
| `maintenance_signals_seen.source` | deferred | `maintenance_derived` | swe-bench |
| `maintenance_signals_seen[].signal` | deferred | `maintenance_derived` | casp, roboarena |
| `maintenance_signals_seen[].source` | deferred | `maintenance_derived` | casp, roboarena |
| `maintenance_status` | deferred | `maintenance_derived` | casp, roboarena, swe-bench |
| `metric` | deferred | `metric` | roboarena |
| `metric.absolute_score` | deferred | `metric` | roboarena |
| `metric.ceiling_anchor_type` | deferred | `metric` | roboarena |
| `metric.headroom` | deferred | `metric` | roboarena |
| `metric.kind` | deferred | `metric` | roboarena |
| `metric.model` | deferred | `metric` | roboarena |
| `metric.model_quote` | deferred | `metric` | roboarena |
| `metric.model_source` | deferred | `metric` | roboarena |
| `metric.official_threshold` | deferred | `metric` | roboarena |
| `metric.official_threshold.quote` | deferred | `metric` | roboarena |
| `metric.official_threshold.source` | deferred | `metric` | roboarena |
| `metric.official_threshold.unit` | deferred | `metric` | roboarena |
| `metric.official_threshold.value` | deferred | `metric` | roboarena |
| `metric.official_threshold.value_locator` | deferred | `metric` | roboarena |
| `metric.paper_model_note` | deferred | `metric` | roboarena |
| `metric.paper_model_quote` | deferred | `metric` | roboarena |
| `metric.paper_model_source` | deferred | `metric` | roboarena |
| `metric.provisional_note` | deferred | `metric` | roboarena |
| `metric.provisional_quote` | deferred | `metric` | roboarena |
| `metric.provisional_rows_on_same_board` | deferred | `metric` | roboarena |
| `metric.provisional_source` | deferred | `metric` | roboarena |
| `metric.rating_pool_required` | deferred | `metric` | roboarena |
| `metric.snapshot` | deferred | `metric` | roboarena |
| `metric.snapshot.last_updated` | deferred | `metric` | roboarena |
| `metric.snapshot.quote` | deferred | `metric` | roboarena |
| `metric.snapshot.source` | deferred | `metric` | roboarena |
| `metrics` | deferred | `metric` | casp |
| `metrics.assessor_discretion` | deferred | `metric` | casp |
| `metrics.assessor_discretion.quote` | deferred | `metric` | casp |
| `metrics.assessor_discretion.source` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers.measures` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers.metric` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers.note` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers.quote` | deferred | `metric` | casp |
| `metrics.assessor_ranking_monomers.source` | deferred | `metric` | casp |
| `metrics.complexes` | deferred | `metric` | casp |
| `metrics.complexes_quote` | deferred | `metric` | casp |
| `metrics.complexes_source` | deferred | `metric` | casp |
| `metrics.ligands` | deferred | `metric` | casp |
| `metrics.ligands_quote` | deferred | `metric` | casp |
| `metrics.ligands_source` | deferred | `metric` | casp |
| `metrics.prediction_center_ranking` | deferred | `metric` | casp |
| `metrics.prediction_center_ranking.metric` | deferred | `metric` | casp |
| `metrics.prediction_center_ranking.quote` | deferred | `metric` | casp |
| `metrics.prediction_center_ranking.source` | deferred | `metric` | casp |
| `metrics.review_note` | deferred | `metric` | casp |
| `name` | needed | `identity` | casp, roboarena, swe-bench |
| `observed_subjects` | needed | `observed_subjects` | swe-bench |
| `observed_subjects.basis` | needed | `field_notes` | swe-bench |
| `observed_subjects.source` | needed | `evidence` | swe-bench |
| `observed_subjects.values` | needed | `observed_subjects` | swe-bench |
| `paper` | needed | `paper` | roboarena, swe-bench |
| `paper.arxiv` | needed | `paper` | roboarena, swe-bench |
| `paper.source` | needed | `evidence` | roboarena, swe-bench |
| `paper.title` | needed | `paper` | roboarena, swe-bench |
| `paper.version_read` | needed | `paper` | roboarena, swe-bench |
| `planned_end` | needed | `schedule` | roboarena |
| `platform` | needed | `platform` | roboarena |
| `policy_identity` | deferred | `policy_identity` | roboarena |
| `policy_identity.aliasing` | deferred | `policy_identity` | roboarena |
| `policy_identity.linked_paper_example` | deferred | `policy_identity` | roboarena |
| `policy_identity.linked_paper_example.backend_id` | deferred | `policy_identity` | roboarena |
| `policy_identity.linked_paper_example.display_name` | deferred | `policy_identity` | roboarena |
| `policy_identity.linked_paper_example.quote` | deferred | `policy_identity` | roboarena |
| `policy_identity.linked_paper_example.source` | deferred | `policy_identity` | roboarena |
| `policy_identity.open_source_flag_per_policy` | deferred | `policy_identity` | roboarena |
| `policy_identity.open_source_quote` | deferred | `policy_identity` | roboarena |
| `policy_identity.open_source_source` | deferred | `policy_identity` | roboarena |
| `policy_identity.quote` | deferred | `policy_identity` | roboarena |
| `policy_identity.source` | deferred | `policy_identity` | roboarena |
| `policy_identity.trap` | deferred | `policy_identity` | roboarena |
| `release_venue` | needed | `release` | swe-bench |
| `released` | needed | `release` | roboarena, swe-bench |
| `repository` | needed | `links` | roboarena, swe-bench |
| `results_board_summary` | deferred | `results` | swe-bench |
| `results_board_summary.derived` | deferred | `results` | swe-bench |
| `results_board_summary.rows` | deferred | `results` | swe-bench |
| `results_board_summary.rows_checked` | deferred | `results` | swe-bench |
| `results_board_summary.source` | deferred | `results` | swe-bench |
| `results_observed` | deferred | `results` | casp, roboarena, swe-bench |
| `results_observed[].backend_id` | deferred | `results` | roboarena |
| `results_observed[].category` | deferred | `results` | casp |
| `results_observed[].checked` | deferred | `results` | swe-bench |
| `results_observed[].date` | deferred | `results` | swe-bench |
| `results_observed[].display_name` | deferred | `results` | roboarena |
| `results_observed[].edition` | deferred | `results` | casp |
| `results_observed[].entrant_class` | deferred | `results` | casp |
| `results_observed[].label` | deferred | `results` | roboarena, swe-bench |
| `results_observed[].metric` | deferred | `results` | casp |
| `results_observed[].n_evals` | deferred | `results` | roboarena |
| `results_observed[].official` | deferred | `results` | roboarena |
| `results_observed[].open_source` | deferred | `results` | roboarena |
| `results_observed[].quote` | deferred | `results` | casp, roboarena, swe-bench |
| `results_observed[].quote_locator` | deferred | `results` | swe-bench |
| `results_observed[].rank` | deferred | `results` | casp |
| `results_observed[].rating` | deferred | `results` | roboarena |
| `results_observed[].rating_pool` | deferred | `results` | roboarena |
| `results_observed[].scaffold` | deferred | `results` | swe-bench |
| `results_observed[].snapshot` | deferred | `results` | roboarena |
| `results_observed[].source` | deferred | `results` | casp, roboarena, swe-bench |
| `results_observed[].std` | deferred | `results` | roboarena |
| `results_observed[].system` | deferred | `results` | casp, swe-bench |
| `results_observed[].value` | deferred | `results` | casp, swe-bench |
| `results_observed[].value_meaning` | deferred | `results` | casp |
| `saturation_by_category` | deferred | `saturation` | casp |
| `saturation_by_category[].category` | deferred | `saturation` | casp |
| `saturation_by_category[].quote` | deferred | `saturation` | casp |
| `saturation_by_category[].source` | deferred | `saturation` | casp |
| `saturation_by_category[].state` | deferred | `saturation` | casp |
| `scale` | needed | `scale_publication` | roboarena |
| `scale.at_publication` | needed | `scale_publication` | roboarena |
| `scale.at_publication.institutions` | needed | `scale_publication` | roboarena |
| `scale.at_publication.pairwise_comparisons` | needed | `scale_publication` | roboarena |
| `scale.at_publication.policies` | needed | `scale_publication` | roboarena |
| `scale.at_publication.quote` | needed | `evidence` | roboarena |
| `scale.at_publication.source` | needed | `evidence` | roboarena |
| `scale.live_2026_09_23` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.derived` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.largest_org_share_percent` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.maintainer_publishes_this` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.maintainer_quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.maintainer_source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_concentration.top3_org_share_percent` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_organizations` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_organizations.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_organizations.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.evaluator_organizations.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.first_evaluation` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.first_evaluation.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.first_evaluation.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.first_evaluation.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.last_evaluation` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.last_evaluation.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.last_evaluation.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.last_evaluation.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.official_policies` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.official_policies.derived` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.official_policies.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.official_policies.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policies` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policies.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policies.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policies.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policy_servers_up` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.policy_servers_up_derived` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.tie_rate_percent` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.tie_rate_percent.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.tie_rate_percent.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.tie_rate_percent.value` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.total_ab_evaluations` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.total_ab_evaluations.quote` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.total_ab_evaluations.source` | deferred | `scale_live` | roboarena |
| `scale.live_2026_09_23.total_ab_evaluations.value` | deferred | `scale_live` | roboarena |
| `self_description` | needed | `self_description` | roboarena |
| `self_description.quote` | needed | `evidence` | roboarena |
| `self_description.source` | needed | `evidence` | roboarena |
| `size` | needed | `size` | swe-bench |
| `size.languages` | needed | `size` | swe-bench |
| `size.n_items` | needed | `size` | swe-bench |
| `size.n_items.quote` | needed | `evidence` | swe-bench |
| `size.n_items.source` | needed | `evidence` | swe-bench |
| `size.n_items.split` | needed | `size` | swe-bench |
| `size.n_items.unit` | needed | `size` | swe-bench |
| `size.n_items.value` | needed | `size` | swe-bench |
| `size.n_repositories` | needed | `size` | swe-bench |
| `size.n_repositories.quote` | needed | `evidence` | swe-bench |
| `size.n_repositories.source` | needed | `evidence` | swe-bench |
| `size.n_repositories.value` | needed | `size` | swe-bench |
| `size.other_splits` | needed | `size` | swe-bench |
| `size.other_splits[].note` | needed | `field_notes` | swe-bench |
| `size.other_splits[].quote` | needed | `evidence` | swe-bench |
| `size.other_splits[].source` | needed | `evidence` | swe-bench |
| `size.other_splits[].split` | needed | `size` | swe-bench |
| `size.other_splits[].value` | needed | `size` | swe-bench |
| `subjects_considered_and_rejected` | needed | `rejected` | casp, roboarena |
| `subjects_considered_and_rejected[].reason` | needed | `rejected` | casp, roboarena |
| `subjects_considered_and_rejected[].term` | needed | `rejected` | casp, roboarena |
| `summary` | needed | `summary` | casp, roboarena, swe-bench |
| `tagline` | needed | `tagline` | casp, roboarena, swe-bench |
| `task` | needed | `task` | swe-bench |
| `task.input` | needed | `task` | swe-bench |
| `task.metric` | deferred | `metric` | swe-bench |
| `task.metric_range` | deferred | `metric` | swe-bench |
| `task.output` | needed | `task` | swe-bench |
| `task.reference_solution` | needed | `task` | swe-bench |
| `task.scoring` | needed | `task` | swe-bench |
| `task.scoring_quote` | needed | `evidence` | swe-bench |
| `task.scoring_source` | needed | `evidence` | swe-bench |
| `task.tests_hidden_from_system` | needed | `task` | swe-bench |
| `task_set` | needed | `task` | roboarena |
| `task_set.blinding` | needed | `task` | roboarena |
| `task_set.blinding.quote` | needed | `evidence` | roboarena |
| `task_set.blinding.source` | needed | `evidence` | roboarena |
| `task_set.constraint` | needed | `task` | roboarena |
| `task_set.constraint.quote` | needed | `evidence` | roboarena |
| `task_set.constraint.source` | needed | `evidence` | roboarena |
| `task_set.exists` | needed | `task` | roboarena |
| `task_set.item_definition` | needed | `task` | roboarena |
| `task_set.quote` | needed | `evidence` | roboarena |
| `task_set.source` | needed | `evidence` | roboarena |
| `task_set.task_distribution_drifts` | needed | `task` | roboarena |
| `task_set.task_distribution_quote` | needed | `evidence` | roboarena |
| `task_set.task_distribution_source` | needed | `evidence` | roboarena |
