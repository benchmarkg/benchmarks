# ADR-0024 -- The 20-entry checkpoint's schema revision

- **Status:** Proposed -- an agent draft (P1-S3-T05). It counts as decided only when two reviewers ratify it
  (05 §5: a schema change needs two, an ADR, a migration script and a full revalidation).
- **Date:** 2026-10-12
- **Taxonomy version:** not affected. Every vocabulary file stays at 0.9.0. `taxonomy/comparability-profiles.yaml`,
  which versions itself, goes from 0.1.0 to 0.2.0 (one profile added).
- **Facet:** none. Schema changes to Benchmark, EvalConditions and Source (04 §5, §8, §9)
- **Change type:** schema, mixed: additive fields, one nullable field, two reshaped fields, one field made
  derived, and one comparability rule moved
- **Supersedes:** --
- **Superseded by:** --
- **Migration:** schema/migrations/0024-checkpoint-revision.py (124 rows in 63 files)

The plan names this ADR `adr/0007-checkpoint-schema-revision.md` and its migration `0002`. ADRs 0007 and 0008
were taken by P0-S8's leaderboard-conditions and metric-rubric decisions, 0006 and 0009 to 0013 are reserved
for other planned tasks, and a migration takes its ADR's number, so this is 0024 (agreed 2026-10-12).

## Context

The first twenty checkpoint entries (P1-S3-T01, T02) were curated against the Phase 0 schema, and
P1-S3-T04 read what they wrote in free-text notes because the schema had nowhere structured to put it
(docs/checkpoint/schema-findings.md, from `scripts/notes_field_audit.py` over all 34 curated entries).
14-roadmap's Phase 0 test is that "a `notes` field doing structural work is the tell". The findings
proposed ten additions (A1-A10) and four deletions or reconciliations (D1-D4). The maintainer agreed the
recommended option for each on 2026-10-12, through the checkpoint decision card.

## Decision

**A1. `lifecycle` may be null, and no longer defaults to `active`.** lifecycle.yaml's `dormant` exclusion
already says "where the sources show only that inactivity and are silent on current use, leave the field
null and log it"; the schema refused null and filled an omitted field with `active`, so an omission
asserted use. A null lifecycle is now a tier-3 warning (`lifecycle-unobserved`) that points at the failure
log. All 34 entries already set lifecycle, so none changes meaning; The Well, whose basis said its
`active` was forced, becomes null. 04 §5's table row (`Required at: stub`, default `active`) is amended:
default null. The `bench new` template now writes null.

**A2. Explicit unknowns.**

- `aggregation_policy` gains `unknown` (SUPERB, which states no aggregate). Its default stays
  `official-aggregate`: the 23 entries that omit it were curated against that default, and rewriting it
  would change their meaning without a source.
- `governance.submission_process: null` means "not stated" (the type already allowed it); CALVIN's and
  HarmBench's `[]`, which their notes said meant exactly that, become null.
- `governance.independence_assessed` (bool): `[]` beside `true` is "checked, and no flag applies", beside
  `false` "not assessed". `no-known-conflict` stays the stronger statement about a search. Three entries
  are false (tau-bench, OC20, CALVIN: their notes say "Not assessed"), 31 true. A flag beside `false` is a
  tier-3 block (`independence-assessed`).

**A3. `history[]`**, a list of `{date, event, field, from, to, source, quote, note}` for changes to fields
that hold one current value: `channel-opened`, `channel-closed`, `channel-moved`, `maintainer-changed`,
`repository-moved`, `access-changed`, `licence-changed`. `date` is a date or a month, null where the
sources show a change without dating it. Seven entries are backfilled from their notes, each item with a
quote the entry already carried or its Source's extract holds: COCO, OC20, MMMU, FLORES, NLE, miniF2F,
tau-bench. Version changes are not history; they belong in `versions[]`.

**A4. `as_used[]`**, `{protocol, split, source, quote, note}`: how a benchmark is run where that differs from
its design. The facets keep describing the design. Filled for MedQA (closed-book), LIBERO (multitask
success), HumanEval (instruction-tuned models) and FOLIO (the validation split). The agreed shape listed
`subjects` too; it is left out because `observed_subjects` already records who actually submits, and two
fields for one fact is the drift this project exists to prevent.

**A5. `paper.doi`**, the published version's DOI beside the preprint. OC20's moves out of its
`released_note`; ClimateBench's is its paper Source's. CircuitNet and LegalBench have none recorded.

**A6. `ground_truth_source` gains `formal-verifier` and `released-classifier`**, mechanical judges that
`none` had read as "no ground truth": miniF2F and HarmBench move to them.

**A7. `EvalConditions.user_simulator`** and `user_simulator_version`, the model that plays the user in a
simulated conversation; tau-bench lists it in `material_extra`. The reproducibility blocker Stage 3
proposed (`hosted-judge-dependency`) is **not** added: 02 §11 allows no blocker but `licence-restriction`
beside `fully-automatable`, and amending that rule needs its own ADR.

**A8. Not here.** A capability for program synthesis (`2026-10-10-humaneval-001`) is a vocabulary change;
it goes through the taxonomy revision path with the other logged gaps.

**A9. `Source.rendered_url` and `Source.extract_preprocessing`.** Ten Sources fetched something other than
the page a reader opens (COCO's tab fragments, EvalAI and Hugging Face API records, a Crossref record, a
Gradio app's text module) and now name that page. Nineteen whose notes say their script and style blocks
were stripped before normalising now say so in a field.

**A10. Lineage to benchmarks not yet catalogued, through the inline declarations that already exist.**
The agreed option was "a stub as a lineage target". Stubs, it turned out, are bound to the Epoch id
allocation: every file in `data/benchmarks/_stubs/` must be an Epoch row, and a test holds the directory to
the emitter's output. `lineage.variants[]` and `forks[]` already declare a related benchmark's id inline,
with a source and a quote, and tier 2 already resolves them. So no schema change: MMMU declares MMMU-Pro
and ClimateBench declares v2, each from a Source the entry had read. OC22 and miniF2F-Dafny stay in header
comments until a Source for each is read.

**D1. `license` is derived.** The top-level `license` and `license_notes` may no longer be hand-written.
`license` is computed from `data.dataset_licence` and `execution.code_licence` (one, or both labelled when
they differ), so Croissant's `sc:license` and 04 §5's full-level requirement still have a value. Five
entries carried the keys; the notes move to the data or code licence note, and the paper licences they
repeated are already on the papers' Sources. The copilot drafts `execution.code_licence` where it drafted
`license`. The feed watches the two licence fields.

**D2. `data.size` is a list of rows**, `{count, unit, subset, note, source, quote}`, headline first, in
place of `{n_items, n_repositories, other_splits, languages}`. Ten entries convert, one row per count, and
`languages` moves to `data.languages`. The 21 entries that wrote `size_note` instead are not converted
here: that is curation, with quotes, not a migration.

**D3. The comparability rule moves, not the entries.** `[statistical-fit, scientific-surrogate-model]` leaves
`forecasting` for a new profile, `surrogate-fit` (`subset_used`, `training_data_policy`): exactly the
forecasting set less the two fields all six entries waived. The six waivers go.

**D4. Nothing deleted.** The interop keys and the contested-maintenance fields no entry used are kept and
revisited at 100 entries; zero uses in 34 says little about 320.

## Consequences

- `bench migrate 0024 --dry-run` plans 124 rows in 63 files (34 benchmarks, 29 Sources); `--apply` writes
  them through the project's emitter. The migration extends `Row` with `ABSENT` (add a key, or remove one).
- schema/generated/*.schema.json and site/src/types/*.d.ts are regenerated in the same commit.
- 04 §5's field reference rows for `lifecycle`, `ground_truth_source`, `data.size`, `aggregation_policy`,
  `license` and `license_notes` are amended by this ADR; `scripts/notes_field_audit.py` skips a derived
  field when it lists empty full-level fields.
- Consumers: a lifecycle chip is omitted for a null lifecycle (site BenchmarkCard); the copilot's drafted
  size is a one-row `data.size`.
- The six-minute median from P1-S3-T03 is unchanged by this; entries still stop short of `full` on
  `versions`, `metrics` and `governance.maintainers`, which need their target records, not schema.
