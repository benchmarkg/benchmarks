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

**P0-S4-T10 resolved every row** ([Resolution](#resolution-p0-s4-t10)). Two statuses were added
by that pass and no row is `unused` any more:

- **resolved** -- was `unused`; removed from the entries or folded into a modelled field.
- **deferred (full)** -- a 04 §5 field no entry used yet, kept because 04 requires it at `full` and
  other code or documents read it. Whether any of them should have been deleted instead is the
  reviewer's call.

532 distinct field paths appeared across the three files at P0-S3-T05: 309 needed, 213 deferred and 10
unused, the 10 now resolved. The paths are the entries' names at that time; P0-S4-T10 renamed some of
them, and the Resolution section says where each group now lives.
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
| `admissibility` | **needed** | `evaluation_target`, `learned_entrant_evidence`, `learned_entrant_evidence.observed_on`, `learned_entrant_evidence.system` (4 paths) | casp, roboarena, swe-bench | `learned_entrant_evidence[]`, `evaluation_target` | Added to all three entries by P0-S4-T03, with the user's approval, from systems each entry already cited: the admissibility boundary (00 §6 A5) the model enforces. |
| `tags` | **needed** | `tags` (1 path) | roboarena | `tags[]` | RoboArena holds `evaluator-improvised` here, the escape hatch 02 §11 rule 7 gives an undefined term, since P0-S4-T03 moved it out of `data_provenance`. |
| `facets` | **needed** | `capability`, `designed_for_subjects`, `evaluation_method`, `lifecycle` (4 paths) | casp, roboarena, swe-bench | `capability[]`, `evaluation_method[]`, `designed_for_subjects[]`, `lifecycle` | As specified. |
| `rejected` | **needed** | `capability_considered_and_rejected`, `capability_considered_and_rejected.reason`, `capability_considered_and_rejected.term`, `domain_considered_and_rejected`, `domain_considered_and_rejected.reason`, `domain_considered_and_rejected.term` ... (12 paths) | casp, roboarena, swe-bench | **not in 04 §5** | All three record near-miss terms with reasons (`*_considered_and_rejected`). Without them a reviewer cannot tell a judged short list from a skipped one. |
| `tag_basis` | **needed** | `capability_basis`, `capability_basis.calibration-uncertainty`, `capability_basis.distribution-shift-generalization`, `capability_basis.generation-fidelity`, `capability_basis.grounding`, `capability_basis.sensorimotor-control` ... (11 paths) | casp, roboarena, swe-bench | `curation.notes` (02 §11 rule 2) | Per-tag justifications. 02 §11 rule 2 routes them to `curation.notes`; the entries want them per term, which that single string cannot index. |
| `observed_subjects` | **needed** | `observed_subjects`, `observed_subjects.values` (2 paths) | swe-bench | **not in 04 §5** | Who actually submits, beside who it was designed for (SWE-bench: built for prompted models, used by agents). |
| `activity` | **needed** | `activity`, `activity_basis.newest_submission` (2 paths) | casp, roboarena, swe-bench | **not in 04 §5**; vocabulary `taxonomy/lifecycle.yaml` field `activity` | The activity vocabulary exists (six terms) but 04 §5 has no `activity` field. CASP also needs a value the vocabulary lacks: `assessment-in-progress`. |
| `schedule` | **needed** | `events`, `events.kind`, `events.name`, `planned_end` (4 paths) | roboarena | **not in 04 §5** | `planned_end` and `events[]`: a live benchmark's announced end and a dated challenge run on it, neither an edition nor a separate benchmark. |
| `maintenance_derived` | **deferred** | `maintenance_signals_seen`, `maintenance_signals_seen.repo_archived`, `maintenance_signals_seen.repo_pushed_at`, `maintenance_signals_seen.signal`, `maintenance_signals_seen.source` (6 paths) | casp, roboarena, swe-bench | `maintenance_status` (derived) and `liveness.*` (machine-written) | Machine-written inputs to a derived verdict. 04 §5 forbids derived fields in a hand-written file, so P0-S4-T03 removed the entries' `maintenance_status: null` lines; the raw signals stay, for the probe protocol. |
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
| `reviewer_notes` | **resolved** | `governance.reviewer_check` (7 paths) | casp, roboarena, swe-bench | `curation.notes` | Notes addressed to the reviewer of this draft, not facts about the benchmark. Fold into `curation.notes` or drop at approval. |
| `execution_core` | **needed** | `execution`, `execution.compute_tier`, `execution.reproducibility_tier` (3 paths) | casp, roboarena, swe-bench | `execution.compute_tier`, `execution.reproducibility_tier` | As specified. |
| `execution_vocab` | **needed** | `execution.harness_availability`, `execution.reproducibility_blockers` (2 paths) | casp, roboarena, swe-bench | **not in 04 §5**; vocabulary `taxonomy/execution.yaml` | `reproducibility_blockers` and `harness_availability` have vocabularies in `execution.yaml` but no field in 04 §5. |
| `execution_role` | **needed** | `execution.compute_tier_by_role`, `execution.submitter_needs_no_robot` (4 paths) | roboarena | **not in 04 §5** | Cost by role: a RoboArena submitter needs a server, an evaluator a robot. One tier describes neither. |
| `harness` | **needed** | `execution.harness`, `execution.harness_gotcha` (2 paths) | swe-bench | `execution.runnable_via[]`, `execution.inspect_evals_id` | The harness an outside runner would use. |
| `submission_channel` | **needed** | `execution.submission_channel` (1 path) | casp | **not in 04 §5** | How entries are submitted (CASP: a web form per category with its own deadline). |
| `interop` | **needed** | `interop`, `interop.arxiv`, `interop.eee_benchmark_name`, `interop.epoch_benchmark_id`, `interop.huggingface_dataset`, `interop.inspect_evals_id` (6 paths) | swe-bench | `external_ids.*`, `execution.inspect_evals_id` | `epoch`, `inspect_evals`, `huggingface` and `every_eval_ever` exist. `arxiv` does not. |
| `lineage` | **needed** | `lineage`, `lineage.forks`, `lineage.role`, `lineage.variants`, `lineage.views` (15 paths) | swe-bench | `lineage.*` (supersedes, extended_by, subset_of, ...) | SWE-bench needs three relations 04 collapses: same-maintainer variants, other-maintainer forks, and views that are only filters. |
| `results` | **deferred** | `results_board_summary`, `results_board_summary.derived`, `results_board_summary.rows`, `results_board_summary.rows_checked`, `results_board_summary.source`, `results_observed` ... (30 paths) | casp, roboarena, swe-bench | ResultClaim (§7), System (§7); P0-S4-T05 | Results are claims, not benchmark fields. Findings for ResultClaim: `scaffold`, `checked`/`official`, `entrant_class` (including an assessor-run baseline that must not read as a winner), a rating's pool and snapshot. |
| `policy_identity` | **deferred** | `policy_identity`, `policy_identity.aliasing`, `policy_identity.linked_paper_example`, `policy_identity.open_source_flag_per_policy`, `policy_identity.open_source_quote`, `policy_identity.open_source_source` ... (13 paths) | roboarena | System (§7) and the alias tables (§10) | Backend ids, display names and an alias that names another system: the System entity and its aliases, not the Benchmark. |
| `curation_core` | **needed** | `curation`, `curation.added_by`, `curation.added_on`, `curation.last_verified`, `curation.verification_status` (5 paths) | casp, roboarena, swe-bench | `curation.added_by`, `curation.added_on`, `curation.last_verified`, `curation.verification_status`, `curation.sources[]` | As specified. The entries wrote `drafted_by`/`drafted_on`/`retrieved_on`; P0-S4-T03 renamed them. |
| `curation_sources_inline` | **deferred** | `curation.sources` (11 paths) | casp, roboarena, swe-bench | the `Source` record (§9; `schema/source.py`) | Inline source descriptions (url, kind, hash, extract mode, personal data) now live in `data/sources/`. `curation.sources[]` becomes a list of Source ids. |
| `curation_extra` | **needed** | `curation.not_yet_available`, `curation.personal_data_excluded`, `curation.unreachable` (10 paths) | casp, roboarena, swe-bench | **not in 04 §5** | A source that 403s (`unreachable`), one that will exist but does not yet (`not_yet_available`), and personal data deliberately excluded. Each changes what may be claimed. |
| `evidence` | **needed** | *(across all blocks)* (95 paths) | casp, roboarena, swe-bench | **not in 04 §5** for Benchmark fields | Per-field `source` + `quote` (or a `quote_locator` where the value sits in structured data). 04 gives ResultClaim field provenance but Benchmark only a flat `curation.sources[]`; the quote-substring validator needs to know which source a number came from. |
| `field_notes` | **needed** | *(across all blocks)* (28 paths) | casp, roboarena, swe-bench | `curation.notes` | Per-field notes (`*_note`, `*_basis`, `*_caveat`). One `curation.notes` string cannot say which field a note is about. |
| `meta` | **resolved** | `_schema_findings`, `_schema_findings.field`, `_schema_findings.need` (3 paths) | casp, roboarena, swe-bench | — | `_schema_findings`: this task's input, not data. Remove from the entries once P0-S4-T10 reconciles them. |

## Resolution (P0-S4-T10)

Where each group now lives. **Schema field** names real field paths on the Pydantic models, each
from its root entity, and `tests/schema/test_benchmark_model.py` resolves every one through
`schema/paths.py`: a `needed` row must name at least one, and every name in any row must resolve.

Two mechanisms carry the cross-cutting groups, rather than a field per case:

- **Annotations** (`evidence`, `field_notes`). A key `<field>_note`, `_notes`, `_caveat`, `_basis`,
  `_source` or `_quote` beside a modelled `<field>` in the same block is an annotation of that
  field, and is type-checked: `_source` must be a Source id, `_basis` text or a Basis block, the
  rest text. It says which field a note or a quote is about, which is what one `curation.notes`
  string could not, and it lets the quote-substring validator know which source a value came from.
  An annotation of a field the block does not have is an unknown key and is rejected. Seven entry
  keys were renamed so each annotates a real field (`contamination_*` became `contamination_risk_*`,
  `submission_*` became `submission_process_*`, `ceiling_note`, `compute_note`, `reproducibility_note`,
  `records_*`, `task_distribution_*`).
- **Deferred keys** (every `deferred` row). A block declares the keys that belong to another entity;
  they are accepted untyped and `deferred_fields()` lists them, until the owning entity takes them
  over. Every other unknown key is now rejected, so the entries validate with no unmodelled key.

| Group | Status | Schema field | Resolution |
| --- | --- | --- | --- |
| `identity` | needed | `Benchmark.id`, `Benchmark.name`, `Benchmark.aliases` | CASP's `full_name` moved into `aliases`. |
| `tagline` | needed | `Benchmark.tagline` | As specified. |
| `summary` | needed | `Benchmark.description` | The entries' `summary` renamed to `description`. |
| `release` | needed | `Benchmark.released`, `Benchmark.release_venue` | Added. |
| `paper` | needed | `Benchmark.paper`, `Benchmark.external_ids.arxiv` | Added: `paper` names the Source and the arXiv version read; `external_ids` gains `arxiv`. |
| `links` | needed | `Benchmark.homepage`, `Benchmark.repository`, `Benchmark.dataset_url`, `Benchmark.leaderboard_url`, `Benchmark.api_url`, `Benchmark.maintainer_url` | Four URL fields added; the entries' `dataset`, `leaderboard`, `api`, `maintainer_site` renamed. `leaderboards[]` stays for Leaderboard record ids. |
| `self_description` | needed | `Benchmark.self_description` | Added, as a source and quote. |
| `platform` | needed | `Benchmark.platform`, `Benchmark.hardware` | Added. |
| `domain` | needed | `Benchmark.domain.primary`, `Benchmark.domain.secondary` | As specified. |
| `domain_per_edition` | needed | `Benchmark.domain.per_edition` | Added. A per-edition `domain_override` waits for editions to become BenchmarkVersions. |
| `admissibility` | needed | `Benchmark.learned_entrant_evidence`, `Benchmark.evaluation_target` | As P0-S4-T03 added them. |
| `tags` | needed | `Benchmark.tags` | As specified. CASP's out-of-vocabulary activity also lands here (below). |
| `facets` | needed | `Benchmark.capability`, `Benchmark.designed_for_subjects`, `Benchmark.evaluation_method`, `Benchmark.lifecycle` | As specified. |
| `rejected` | needed | `Benchmark.capability_considered_and_rejected`, `Benchmark.domain_considered_and_rejected`, `Benchmark.evaluation_method_considered_and_rejected`, `Benchmark.designed_for_subjects_considered_and_rejected` | Added. Each term must be a real term of its facet and must not also be assigned. `subjects_considered_and_rejected` renamed to match its facet. |
| `tag_basis` | needed | `Benchmark.capability_basis` | Added: a map from an assigned capability to its reason, as text or a Basis block. A basis for a term that is not assigned is rejected. |
| `observed_subjects` | needed | `Benchmark.observed_subjects` | Added. |
| `activity` | needed | `Benchmark.activity` | Added, typed by the `activity` vocabulary in `taxonomy/lifecycle.yaml`. CASP's `assessment-in-progress` is not in it, so CASP now reads `activity: unknown` with the term in `tags[]` -- the precedent P0-S4-T03 set for RoboArena's `evaluator-improvised` -- until the vocabulary owners decide. |
| `schedule` | needed | `Benchmark.planned_end`, `Benchmark.events` | Added. |
| `maintenance_derived` | deferred | `Benchmark.liveness` | `maintenance_signals_seen` is a declared deferred key; the machine-written `liveness` block will carry it. |
| `data_core` | needed | `Benchmark.data.access`, `Benchmark.data.refresh`, `Benchmark.data.data_provenance`, `Benchmark.data.contamination_risk`, `Benchmark.data.contamination_evidence`, `Benchmark.data.ceiling_anchor_type` | As specified, with a `stance` on each contamination-evidence item. |
| `data_access_split` | needed | `Benchmark.data.access_by_phase`, `Benchmark.data.records_access`, `Benchmark.data.records_licence`, `Benchmark.data.records_snapshot` | Added. |
| `ceiling_per_category` | needed | `Benchmark.data.ceiling_by_category` | Added; CASP's `ceiling_basis` renamed. P0-S3-T05 suggested per-subset Baselines, which needs CASP's categories to be Subsets first. |
| `licences` | needed | `Benchmark.data.dataset_licence`, `Benchmark.data.upstream_licences`, `Benchmark.execution.code_licence` | Added. SWE-bench's `data.code_licence` moved to `execution`, beside RoboArena's, so code licences have one home. |
| `size` | needed | `Benchmark.data.size.n_items`, `Benchmark.data.size.n_repositories`, `Benchmark.data.size.other_splits`, `Benchmark.data.size.languages` | SWE-bench's `size` moved under `data`, 04 §5's home for it, and its shape replaces 04's `{items, unit}`, which no entry used. This is the one model field P0-S4-T10 deleted. |
| `scale_publication` | needed | `Benchmark.scale.at_publication` | Added. |
| `scale_live` | deferred | `Benchmark.scale` | `scale.live_YYYY_MM_DD` is a declared deferred key, for the `metrics/` adoption series. |
| `task` | needed | `Benchmark.task`, `Benchmark.feedback_per_item` | Added. RoboArena's `task_set` renamed to `task`, with `exists: false`. |
| `metric` | deferred | `Metric`, `RatingPool.snapshot_date` | RoboArena's `metric` is a declared deferred key; CASP's `metrics` dict is accepted until Metric records exist. |
| `saturation` | deferred | `Subset` | `saturation_by_category` is a declared deferred key: derived per Subset from claims. |
| `editions` | deferred | `BenchmarkVersion.version_kind` | A declared deferred key, for BenchmarkVersion with `version_kind: edition`. |
| `entrant_classes` | needed | `Benchmark.entrant_classes`, `Benchmark.entrant_classes_history` | Added. |
| `governance_core` | needed | `Benchmark.governance.maintainer`, `Benchmark.governance.maintainer_type`, `Benchmark.governance.maintainers`, `Benchmark.governance.submission_process`, `Benchmark.governance.independence_flags` | `maintainer` kept as a display name beside the `maintainers[]` Organization refs, since no Organization record exists yet; `submission_process` may be a list. |
| `governance_extra` | needed | `Benchmark.governance.funding`, `Benchmark.governance.participation`, `Benchmark.governance.independence_policy`, `Benchmark.governance.admission`, `Benchmark.governance.evaluation_budget`, `Benchmark.governance.known_limitation` | Added. |
| `reviewer_notes` | resolved | `Benchmark.curation.notes` | Folded into `curation.notes` verbatim, with source and quote, one paragraph each, for the reviewer who approves the entry to act on or drop. |
| `execution_core` | needed | `Benchmark.execution.compute_tier`, `Benchmark.execution.reproducibility_tier` | As specified. |
| `execution_vocab` | needed | `Benchmark.execution.harness_availability`, `Benchmark.execution.reproducibility_blockers` | Added, typed by `taxonomy/execution.yaml`. |
| `execution_role` | needed | `Benchmark.execution.compute_tier_by_role` | Added. RoboArena's `submitter_needs_no_robot` became its source and quote annotations. |
| `harness` | needed | `Benchmark.execution.harness`, `Benchmark.execution.harness_gotcha`, `Benchmark.execution.runnable_via`, `Benchmark.execution.inspect_evals_id` | Added `harness` and `harness_gotcha`. |
| `submission_channel` | needed | `Benchmark.execution.submission_channel` | Added. |
| `interop` | needed | `Benchmark.external_ids.huggingface`, `Benchmark.external_ids.arxiv`, `Benchmark.external_ids.epoch`, `Benchmark.external_ids.every_eval_ever`, `Benchmark.external_ids.inspect_evals` | SWE-bench's `interop` block became `external_ids`. 04 §5 also defines `execution.inspect_evals_id` for the same identifier; which one survives is the reviewer's call. |
| `lineage` | needed | `Benchmark.lineage.role`, `Benchmark.lineage.variants`, `Benchmark.lineage.forks`, `Benchmark.lineage.views` | Added: three relations, not one. |
| `results` | deferred | `ResultClaim`, `System` | `results_board_summary` and `results_observed` are declared deferred keys. |
| `policy_identity` | deferred | `System`, `Alias.extracts` | A declared deferred key. |
| `curation_core` | needed | `Benchmark.curation.added_by`, `Benchmark.curation.added_on`, `Benchmark.curation.last_verified`, `Benchmark.curation.verification_status`, `Benchmark.curation.sources` | As specified. |
| `curation_sources_inline` | deferred | `Source` | An inline source's descriptive keys (`kind`, `url`, `title`, `doi`, `text_sha256`, `extract`, ...) are deferred keys of the inline item; the `Source` record owns them. |
| `curation_extra` | needed | `Benchmark.curation.not_yet_available`, `Benchmark.curation.unreachable`, `Benchmark.curation.personal_data_excluded` | Added. |
| `evidence` | needed | `Benchmark.self_description.source`, `Benchmark.governance.funding.quote`, `Benchmark.data.size.n_items.source`, `Benchmark.lineage.variants.quote` | The `_source` / `_quote` annotations, plus a source and quote on every block that states a fact. The names here are representatives. |
| `field_notes` | needed | `Benchmark.curation.notes`, `Benchmark.data.access_by_phase.note`, `Benchmark.data.size.other_splits.note` | The `_note` / `_notes` / `_caveat` / `_basis` annotations; `curation.notes` stays for notes about the entry as a whole. |
| `meta` | resolved | — | `_schema_findings` removed from the entries, and carried verbatim below. |

## Findings carried over from `_schema_findings`

Each entry ended with a `_schema_findings` block: what writing it without a schema surfaced. P0-S4-T10
removed the blocks from the entries, because they are this list's input and not data about the
benchmark, and carries them here verbatim so none is lost.

### casp

| Field | Need |
| --- | --- |
| editions[] with per-edition targets, participation, categories, assessors, status | The claim-bearing unit is the edition. `version` is the wrong model: editions are new test sets, not revisions of one. |
| sources_disagree + values[] + preferred | The organisers give four participation figures for CASP16 (80,000 / 120,000 / 128,000 / 128,161 models or submissions) and two end dates for CASP17's season on one page. An entry must hold disagreement without picking silently. |
| activity value `assessment-in-progress` | Not in the vocabulary. Every edition-based benchmark passes through this state and none of the six activity terms describes it. |
| access_by_phase | One edition moves from held-out to fully open. A single access value is only true for part of its life. |
| entrant_classes[] with ranked_separately | The plan predicted a separately ranked human category. The sources show a separately ranked server category. Either way it is per-class, with its own deadline. |
| metrics with more than one ranking authority | The Prediction Center's GDT_TS table and the assessors' nine-measure formula are both official and can disagree. The Metric model needs an `authority` and an edition. |
| saturation_by_category | Fold prediction is near-solved while complexes and RNA are open, in the same edition. |
| ceiling per category, with a numeric noise ceiling where the source gives one | Affinity has a stated ceiling (tau ~0.73); monomers have a qualitative one. |
| reproducibility split into rescoring vs rerunning | Rescoring archived models is automatable; re-running the blind experiment is impossible after the edition. One tier cannot say both. |
| vocabulary definitions that encode a false premise about CASP | Four P0-S2 drafts assume "no leaderboard" or "humans ranked separately": evaluation-methods expert-panel-assessment (OUT clause), governance assessment-committee ("There is no leaderboard"), subjects human-expert (its CASP example), and 02 S12.1's prose. These are review notes for P0-S2-T02, T03 and T05, not edits this task may make. |
| results_observed[].entrant_class including `assessor-run baseline` | AlphaFold 3's 0.8 LDDT-PLI beat every entrant but was not an entrant. Without a class it reads as the winner. |
| curation.not_yet_available | A source that will exist is different from one that 403s; both change what may be claimed. |

### swe-bench

| Field | Need |
| --- | --- |
| lineage.{variants,forks,views} | Three different relations, not one `variant_of`. A same-maintainer subset (Lite), a same-maintainer extension (Multimodal), an other-maintainer fork (Pro) and a view that is only a filter (Bash Only) must not collapse into one edge. |
| results_observed[].scaffold and [].checked | Per-result, not per-benchmark. The top unchecked row (52.62) and the top checked row (33.83) differ by 19 points, and the checked one used the maintainers' own scaffold. |
| governance.submission_process as a list, plus a note | Artifact-backed self-reporting with optional maintainer re-runs fits neither `self-reported` nor `maintainer-verified`. Either the field is multi-valued or the vocabulary needs a term such as `artifact-backed`. |
| observed_subjects alongside designed_for_subjects | Built for prompted models with retrieval; used almost entirely by agents. Facet 4 already names that divergence at claim level; this entry wants it at benchmark level too. |
| capability_considered_and_rejected | Near-misses with reasons. Without them, a reviewer cannot tell a thin tag list that was judged from one that was skipped. |
| contamination_evidence[].stance | Evidence can cut both ways, and the maintainers' own counter-check should be kept. |
| size.n_items with split, and n_items_history on variants | Counts change between versions (Multimodal 617 to 480); one integer loses that. |
| sources[].extract and quote_locator | The quote-substring check fails for any number held in inline JSON, since the normalisation strips <script>. Structured sources need a locator, not a substring. The arXiv HTML extract also loses every number typeset as math. |
| curation.unreachable | A source that 403s is information; recording it stops the claim being made from memory. |
| dataset_licence vs code_licence vs upstream_licences | Three different licences with three different answers, one of them null. |

### roboarena

| Field | Need |
| --- | --- |
| task_set.exists = false, with item_definition | n_items, splits and a dataset licence all presuppose a task set. Here the item is an event, and the thing with a licence is the log of events. |
| metric.kind relative-rating, rating_pool_required, snapshot, official_threshold | A rating is a claim about a pool at a time. The same number means nothing a month later or on another board, and rows under the threshold share the board with rows over it. |
| results_observed[].official | The top API row is not an official result. Without the flag, ingestion crowns the wrong policy. |
| policy_identity with backend_id AND display_name | Anonymised backend ids, display aliases, and one alias that points at another system's name. Claims keyed on a single string will mis-attach. |
| feedback_per_item[] with `ranks` | Three signals are collected and one ranks. Partial-success data exists and must not be mistaken for the metric. |
| execution.compute_tier_by_role | Submitter and evaluator costs differ by class (a server vs a robot). A single tier describes neither entrant. |
| data.access `generated-on-demand` + records_access | Access to items and access to evaluation records are different facts with different answers. |
| data_provenance value `evaluator-improvised` | Not in the vocabulary. Items authored live by the evaluating party are neither crowd-authored nor instrument recordings. |
| evaluator_concentration | A distributed benchmark's credibility rests on how distributed it actually is. The maintainers publish this; the schema has no place for it. |
| events[] on a live benchmark | A dated challenge run on the arena is neither an edition nor a separate benchmark. |
| curation.personal_data_excluded and sources[].contains_personal_data | The archive-snapshot plan (04, 07) would store this API body verbatim. It holds e-mail addresses. Source archiving needs a PII rule before it archives anything. |
| designed_for_subjects when the submitter does not supply the body | physical-robot-system assumes the evaluated system includes its hardware. Here the hardware is the evaluator's and varies per item. Neither subject term fits a remotely served policy on someone else's robot. |


## 04 §5 fields none of the entries used

None of the three entries uses any of them. P0-S4-T10 kept every one as **deferred (full)**: 04 §5
requires them at `full`, and each is read by 04 itself and, for most, by the validators, the
comparability build or a crosswalk. One consequence matters now: no entry declares
`reference_conditions`, so every headroom is null. (The admissibility block, 04 §15 item 12, was
missing from all three when this list was first written; P0-S4-T03 added its two stub fields.)

| 04 §5 field | Status | Note |
| --- | --- | --- |
| `external_ids.every_eval_ever` | **deferred (full)** | SWE-bench records `interop.eee_benchmark_name`, the join value, but not under this key. |
| `croissant_url` | **deferred (full)** | None of the three sets it; SWE-bench's Hugging Face dataset has one. |
| `execution_mode` | **deferred (full)** | Absent; RoboArena would be `physical-trial`. |
| `ground_truth_source` | **deferred (full)** | Absent; CASP would be `experimental`. |
| `reproducible_by_third_party` | **deferred (full)** | Absent; the entries say it in `reproducibility_note` prose instead. |
| `data.submission_limit` | **deferred (full)** | Absent. RoboArena's per-submitter weekly budget is a close cousin. |
| `training_data_eligibility_tiers[]` | **deferred (full)** | Absent; none of the three has tiers. |
| `execution.est_runtime_hours` | **deferred (full)** | Absent. |
| `execution.est_cost_usd` | **deferred (full)** | Absent. |
| `execution.est_participant_cost_usd` | **deferred (full)** | Absent. |
| `execution.inspect_evals_available` | **deferred (full)** | Derived; correctly absent. |
| `comparability.profile` | **deferred (full)** | Absent; derivable from the facets. |
| `comparability.material_extra[]` | **deferred (full)** | Absent. SWE-bench's scaffold finding is a candidate. |
| `comparability.material_waived[]` | **deferred (full)** | Absent. |
| `reference_conditions` | **deferred (full)** | Absent from all three, so SOTA and headroom are null for each (02 §8). |
| `aggregation_policy` | **deferred (full)** | Absent. CASP (two official rankings) is the case the enum exists for. |
| `headline_metric` | **deferred (full)** | Absent. |
| `no_legitimate_aggregate` | **deferred (full)** | Absent. |
| `secondary_axes[]` | **deferred (full)** | Absent. |
| `maintenance_status_contested` | **deferred (full)** | Absent; nothing is contested. |
| `contested_source` | **deferred (full)** | Absent (conditional). |
| `contested_statement_date` | **deferred (full)** | Absent (conditional). |
| `subsets[]` | **deferred (full)** | Absent. CASP's categories and SWE-bench's splits are candidates. |
| `baselines[]` | **deferred (full)** | Absent; CASP's assessor-run AlphaFold 3 is one, recorded as a result instead. |
| `ingestion` | **deferred (full)** | Machine-written; correctly absent from hand-written entries. |
| `curation.stewardship` | **deferred (full)** | Derived; correctly absent. |
| `curation.confidence` | **deferred (full)** | Absent. |

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
| `_schema_findings` | resolved | `meta` | casp, roboarena, swe-bench |
| `_schema_findings[].field` | resolved | `meta` | casp, roboarena, swe-bench |
| `_schema_findings[].need` | resolved | `meta` | casp, roboarena, swe-bench |
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
| `curation.added_by` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.added_on` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.extract_note` | needed | `field_notes` | casp |
| `curation.last_verified` | needed | `curation_core` | casp, roboarena, swe-bench |
| `curation.not_yet_available` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].consequence` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].expected` | needed | `curation_extra` | casp |
| `curation.not_yet_available[].what` | needed | `curation_extra` | casp |
| `curation.personal_data_excluded` | needed | `curation_extra` | roboarena |
| `curation.personal_data_excluded[].source` | needed | `evidence` | roboarena |
| `curation.personal_data_excluded[].what` | needed | `curation_extra` | roboarena |
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
| `evaluation_target` | needed | `admissibility` | casp, roboarena, swe-bench |
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
| `governance.independence_flags[].reviewer_check` | resolved | `reviewer_notes` | swe-bench |
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
| `governance.reviewer_check` | resolved | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].finding` | resolved | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].note` | resolved | `reviewer_notes` | roboarena |
| `governance.reviewer_check[].quote` | resolved | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].source` | resolved | `reviewer_notes` | casp, roboarena |
| `governance.reviewer_check[].why_no_flag` | resolved | `reviewer_notes` | casp |
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
| `learned_entrant_evidence` | needed | `admissibility` | casp, roboarena, swe-bench |
| `learned_entrant_evidence[].note` | needed | `field_notes` | casp |
| `learned_entrant_evidence[].observed_on` | needed | `admissibility` | casp, roboarena, swe-bench |
| `learned_entrant_evidence[].quote` | needed | `evidence` | casp, roboarena, swe-bench |
| `learned_entrant_evidence[].source` | needed | `evidence` | casp, roboarena, swe-bench |
| `learned_entrant_evidence[].system` | needed | `admissibility` | casp, roboarena, swe-bench |
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
| `tags` | needed | `tags` | roboarena |
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
