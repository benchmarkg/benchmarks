# Schema findings from the first twenty checkpoint entries

P1-S3-T04 (DRAFT for review). This is input for P1-S3-T05, which applies the agreed changes with a migration and an
ADR. Nothing here is applied.

**Sources.**

- `python scripts/notes_field_audit.py` over the 34 curated entries: the twenty checkpoint entries and the
  fourteen from Phase 0 and P3.
- `docs/checkpoint/curation-notes.md`, written per entry as each was curated.
- The `taxonomy/_failures/` records the twenty entries logged.

**What a reviewer decides.**

- For each pattern in section 1, whether the note is structural (the schema should hold it) or editorial (prose
  explaining a judgement).
- Which of the adds and deletions in section 4 are agreed.

The audit lists every note with the fields beside it. This document groups those notes and argues each group
once.

The test is 14-roadmap's Phase 0: "a `notes` field doing structural work is the tell" that the schema is wrong.

## 1. Notes doing structural work

The audit finds 419 free-text notes in 34 entries (`notes`, `*_note`, `*_notes`). The most frequent keys:

| key | uses | reading |
| --- | --- | --- |
| `notes` (mostly `curation.notes`) | 58 | the reviewer checklist; editorial by design, but see 1.8 |
| `independence_flags_note` | 33 | **structural**: says whether `[]` means "none" or "not assessed" (1.1) |
| `sources_note` | 32 | editorial: how the Sources were read |
| `contamination_risk_note` | 31 | editorial, and required: 02 S7 asks for the structure behind the value |
| `data_provenance_note` | 29 | mostly editorial |
| `ground_truth_source_note` | 26 | partly structural (1.5) |
| `released_note` | 25 | partly structural: which version dates the release, and a journal DOI with no field (1.6) |
| `submission_process_note` | 24 | partly structural: how results reach a board, and hand-overs (1.2, 1.3) |
| `size_note` | 21 | **structural**: written instead of `data.size` (1.4) |
| `code_licence_note`, `dataset_licence_note`, `license_notes` | 25 | **structural**: licences per task, conflicting licences, licence from an API (1.7) |
| `maintainer_type_note` | 13 | mostly editorial (which test decided), partly hand-over history (1.3) |
| `reproducibility_tier_note` | 10 | partly structural: a hosted-model dependency with no blocker term (1.9) |
| `activity_note` | 9 | structural when it records why `activity` is unknown (1.1) |
| `access_note`, `refresh_note` | 9 | structural: a gate under `train-open-test-held-out`, access that changed on a date (1.3) |

### 1.1 Empty and unknown are indistinguishable

- `governance.independence_flags: []` appears in 24 of 34 entries.
  - In some, the note says no conflict was found: "None recorded; there is no ranking of its own."
  - In others, nobody looked: "Not assessed. The board's rows were not read" (OC20); "Not assessed. Sierra builds
    customer-service agents" (τ-bench).
- `governance.submission_process: []` (CALVIN, HarmBench) means "not stated", and the note says so.
- `aggregation_policy` has no `unknown` (SUPERB).
- `activity: unknown` exists, but its reason lives in `activity_note`.

Every consumer has to read prose to tell "none" from "unknown".

### 1.2 The protocol as used differs from the protocol as designed

- MedQA: open-book over released textbooks, used closed-book.
- LIBERO: lifelong (FWT, NBT, AUC), used multitask.
- HumanEval: base-model continuation, used with instruction-tuned prompts.
- FOLIO: designated test split never released; everyone reports validation.

In each case `capability`, `designed_for_subjects` or `data.access` follows the design, and the use lives in a
basis or `curation.notes`. That is four of twenty entries, the most frequent single gap.

### 1.3 Hand-overs and dated changes have no structure

| entry | what changed | where it went |
| --- | --- | --- |
| coco | test server moved: competitions.codalab.org to codalab.lisn.upsaclay.fr | `submission_channel_note` |
| oc20 | EvalAI board closed 2026-01-31; Hugging Face board opened | `activity_basis`, `submission_channel_note` |
| mmmu | EvalAI closed 2026-02-11; test answers released 2026-02-12 | `access_basis`, `activity_basis` |
| flores | Meta AI to OLDI; test split dropped | description, `maintainer_basis` |
| nle | facebookresearch to a personal account to the NetHack-LE organisation | `maintainer_basis` |
| minif2f | OpenAI (archived) to Meta's fork | `maintainer_basis` |
| tau-bench | τ to τ² to τ³, across two repositories | header comment, `refresh_basis` |

`submission_channel`, `governance.maintainer` and `data.access` each hold one value. `AccessByPhase` exists but is
shaped for CASP's edition phases, not for "until 2026-02-12".

### 1.4 `data.size` is skipped

Twenty-one entries wrote `size_note` instead of `data.size`.

- `Size` wants `n_items` as a Count, with optional repository and language lists.
- The entries had splits by version (CircuitNet N28, N14, N45), counts per language (FLORES, MedQA), suites
  (LIBERO, SUPERB) and items that are not items (NLE's seeds).

The shape fits SWE-bench, which it was built for.

### 1.5 `ground_truth_source` lacks two values

- miniF2F's truth is the proof assistant's verdict. `none` was used, which reads as "no truth".
- HarmBench's truth is a released classifier's verdict. `none` again.

Both are mechanical judges, not labels.

### 1.6 The paper has no DOI field

`paper` holds an arXiv id only. The OC20 entry puts its journal DOI (ACS Catalysis) in `released_note`. CircuitNet
(Science China), ClimateBench (JAMES) and LegalBench (NeurIPS) have the same need.

### 1.7 Licences

- The table's top-level `license` is absent in 31 of 34 entries, because the model's `data.dataset_licence` and
  `execution.code_licence` carry licences instead.
- LegalBench has a licence per task.
- FOLIO's GitHub (CC-BY-SA-4.0) and Hugging Face (MIT) records disagree.
- Several code licences come from GitHub's API, which is not a quotable page, so their `*_licence_note` says so.

### 1.8 `curation.notes` carries findings, not only checks

Besides reviewer checks, `curation.notes` holds several kinds of evidence:

- saturation evidence: MedQA 96.5%, LIBERO 97.1%, CALVIN 4.67 of 5;
- a successor announced (ClimateBench v2);
- third-party subsets (LegalBench on Vals AI).

Saturation is derived and needs claims. Until claims exist, the evidence has nowhere structured to go.

### 1.9 A hosted model in the loop

τ-bench's simulated user is an LLM reached by API.

- On the reproducibility side, Stage 3 proposed `hosted-judge-dependency` eight times.
- On the comparability side, the user-simulator model changes the score and no condition field names it.

## 2. Fields a curator wanted and could not express

| wanted | entries | today |
| --- | --- | --- |
| `lifecycle` unobserved. The vocabulary says "leave the field null and log it"; the schema refuses null and defaults to `active`. | the-well | `active` with a basis saying it was not observed |
| the protocol as used, and the split results are reported on | medqa, libero, humaneval, folio | basis text, `comparability.material_extra` |
| a dated history of submission channel, maintainer and access | coco, oc20, mmmu, flores, nle, minif2f, tau-bench | notes |
| "unknown" for `submission_process`, `independence_flags` and `aggregation_policy` | 26 entries | `[]`, or the default, plus a note |
| a successor announced, not yet replacing | climatebench | reviewer check |
| `paper.doi` | oc20, climatebench, circuitnet, legalbench | `released_note` |
| access and licence per constituent or task | superb, legalbench | notes |
| the user-simulator model as a condition | tau-bench | comparability comment |
| a capability for program synthesis | humaneval | empty, gap logged (`2026-10-10-humaneval-001`) |
| ground truth from a mechanical verifier | minif2f, harmbench | `none` plus a note |
| a Source's rendered URL beside its fetched URL, and the extract's preprocessing | coco (script fragments), vals-ai, the-well | Source notes |
| relations to entries that do not exist yet: OC20 and OC22, MMMU and MMMU-Pro, miniF2F and miniF2F-Dafny, ClimateBench and v2 | 4 | header comments |

## 3. Schema fields no entry used

From `notes_field_audit.py --section unused`:

- **Machine-written or draft-only, unused because nothing writes them yet.** Keep these: `liveness.*`, `ingestion`,
  `provenance.*` (copilot drafts only), `execution.inspect_evals_id`.
- **Interop keys** with no value in these 34: `external_ids.inspect_evals`, `papers_with_code`, `every_eval_ever`,
  `benchmark_radar`; `croissant_url`.
- **Conditional fields** whose condition never arose: `maintenance_status_contested`, `contested_source`,
  `contested_statement_date`, `execution.est_participant_cost_usd`.
- **`governance.maintainers`** (Organization references): unused because none of the twenty maintainers has an
  Organization record. The string `governance.maintainer` carried every one.
- **`comparability.profile`**: a hand-set override. The derived profile was right except for the forecasting rule
  (4.2, D3).
- **`lineage.*`**: unused, though four entries needed it (section 2). Its targets must be existing entries, and the
  related benchmarks were not catalogued yet.

### 3.1 Fields required at `full` that most entries leave empty

From `notes_field_audit.py --section nulls`: the fields 04's field reference requires before an entry counts
toward its family's seed target, and that most of the 34 entries leave empty. No entry is yet at `full` by that
table.

| field | empty in | why |
| --- | --- | --- |
| `governance.maintainers` (Organization references) | 34 of 34 | no Organization records exist for these maintainers; the string `governance.maintainer` is used |
| `license` | 31 of 34 | superseded in practice by `data.dataset_licence` and `execution.code_licence` (1.7, D1) |
| `versions` | 30 of 34 | editions are described in prose; family entries (FLORES, τ-bench, CircuitNet, NLE) name versions in their descriptions and headers |
| `execution.compute_tier` | 24 of 34 | the sources are silent; Stage 3 logged 22 source-silent failures on this field |
| `metrics` (Metric references) | 23 of 34 | no Metric records exist for most; metrics are described in `evaluation_method_basis` |
| `governance.independence_flags` | 24 of 34 | 1.1: `[]` is ambiguous |

Before entries can reach `full`, `versions`, `metrics` and `governance.maintainers` each need their target
records: BenchmarkVersion inline, Metric and Organization files. That is curation work the 20-entry timings
do not include. P1-S3-T03's six-minute median is for entries at the level these twenty reached, which is
between `stub` and `full`. The re-cut should not read it as the cost of a `full` entry.

## 4. Proposed adds and deletions (not applied)

### Adds

- **A1. An unobserved lifecycle.** Allow `lifecycle: null`, as the vocabulary's dormant exclusion asks, or add an
  `unobserved` value, and stop defaulting an omitted lifecycle to `active`. This matters most: an omitted field
  today asserts the benchmark is in use.
- **A2. Explicit unknowns.**
  - `submission_process: unknown` and `aggregation_policy: unknown`.
  - For `independence_flags`, either a `not-assessed` marker or a boolean `independence_assessed`, so that `[]`
    means "none found".
- **A3. A dated history block.** `history[]` of {date, event, field, from, to, source}, for channel moves,
  maintainer hand-overs, forks and access changes. Most of 1.3 becomes data.
- **A4. The protocol as used.** `as_used` {protocol, split, subjects, source} beside the designed fields. The
  facets keep describing the design.
- **A5. `paper.doi`.**
- **A6. Two `ground_truth_source` values**: `formal-verifier` and `released-classifier`.
- **A7.** A comparability condition `user_simulator` (+ version), and the reproducibility blocker Stage 3 proposed
  (`hosted-model-dependency`).
- **A8.** A capability for program synthesis (from the logged gap; a taxonomy change with its own ADR).
- **A9. Source fields** `rendered_url` and `extract_preprocessing` (for example "script and style blocks stripped").
  Six Sources compute `content_sha256` over a stripped page, and a reader can only learn that from their notes.
- **A10. `lineage` to targets not yet catalogued**, as a stub id (04 S3's id allocation) or an unresolved
  reference.

### Deletions and reconciliations

- **D1.** Reconcile the table's top-level `license` and `license_notes` with `data.dataset_licence` and
  `execution.code_licence`. Keep one scheme. The entries chose the second, so this deletes `license` and
  `license_notes`, or redefines them as derived.
- **D2.** Reshape or drop `data.size`. Twenty-one entries chose a note over it. A list of {split or subset, count,
  unit} would fit what they wrote.
- **D3.** Fix the comparability rule, not the entries: statistical-fit x scientific-surrogate-model resolves
  `forecasting`. Seven entries waive its lead_time and resolution_window, so the rule, not the waiver, should
  change.
- **D4.** Keep the unused interop keys and conditional fields for now, and revisit them at 100 entries. Zero uses
  in 34 is not evidence that 320 will not need them. Nothing in section 3 is proposed for deletion outright.

## 5. Not schema, but found here

- **The extract builder.** Each curator writes their own, and the agent's had two bugs:
  - casefold offsets on ligature-heavy PDFs;
  - markup stripping applied to Markdown (`<PATH/TO/DATASET>`).

  It also needed a forbid-list for personal data next to cited facts (contact lines, handles, ORCIDs) in seven
  entries. A project tool would fix all three.
- **`bench fmt` was not part of the curation loop.** Entries passed validation and failed the fmt gate.
- **The validator names a bad key, not the expected spelling** (`aggregation_basis` against
  `aggregation_policy_basis`; a bare flag term against `{flag, source, quote}`).
