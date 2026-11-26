# ADR-0030 -- The croissant-benchmark extension maps every material field, from a schema module

- **Status:** Proposed -- an agent draft (P4-S6-T02). It counts as decided only when two reviewers ratify it
  (GOVERNANCE.md: a schema change needs two, an ADR, a migration script and a full revalidation). The judgements a
  reviewer should confirm or overturn are listed under "Reviewer checks".
- **Date:** 2026-11-26
- **Taxonomy version:** not affected. No vocabulary file changes; taxonomy/crosswalks/croissant.yaml is a crosswalk.
- **Facet:** none. A schema change to the croissant-benchmark extension (08 §5.8), not to an entity (04 §5, §8)
- **Change type:** schema, additive (a new module; no entity model, record or vocabulary changes)
- **Supersedes:** --
- **Superseded by:** --
- **Migration:** schema/migrations/0030-croissant-benchmark-mapping.py (a noop: 0 rows)

## Context

08 §5.8 obliges the catalogue to publish `croissant-benchmark`, a namespaced extension of MLCommons Croissant whose
`conditions` group is "a reference to our `EvalConditions` entity -- the differentiator", and to validate it against
"our own JSON Schema for the extension terms". P2-S3-T06 built the emitter and its Pydantic models in
tools/build/croissant.py with 31 terms; P4-S6-T01 published their context at /ns/croissant-benchmark/v1/. Neither
carried a condition field: a document named its reference conditions by id and nothing more, and the crosswalk's
`unmapped` list deferred the rest to "P4-S6-T02's full mapping".

P4-S6-T02 asks for that mapping: every Benchmark and EvalConditions material field onto an extension term, every
unmapped field listed with its reason, a Pydantic model and generated JSON Schema for the terms in
schema/croissant_benchmark.py, and a test that every material field is accounted for. "Material" is 04 §8's: "Two
claims are comparable only when they agree on benchmark version, metric, subset, and the material condition fields",
with the condition fields resolved per benchmark from taxonomy/comparability-profiles.yaml (0.3.0, ADR-0029) plus each
benchmark's `material_extra` less its `material_waived`.

## Decision

**D1. The extension's models live in schema/croissant_benchmark.py.** The namespace, the seven classes, every term
with the field it carries, and the two document models move there from tools/build/croissant.py, which imports them
and keeps emission and validation. `bench schema gen` renders the one existing
schema/generated/croissant-benchmark.schema.json from the module, so there is still exactly one extension schema and
the codegen drift check holds it; the published context is rendered from the same TERMS. The module is not an entity,
so it is not in schema/paths.py's ENTITIES and has no TypeScript type.

**D2. What counts as material, each part taken from the code that defines it.**

| Part | Source in code | Fields today |
| --- | --- | --- |
| Condition fields a profile makes material | `comparability.load_profiles()`: every profile's and the fallback's `material` | 30 |
| Condition fields a curated benchmark's resolved set holds | `comparability.resolve_profile()` over the 325 curated entries (adds `material_extra`) | 46 (16 more, all from `material_extra`) |
| The key's Benchmark side | `comparability.compute()`'s parameters after `conditions` | benchmark_version, metric, subset |
| The Benchmark's comparability block | `schema.benchmark.Comparability`'s fields, and `reference_conditions` | 5 |

tests/test_croissant_mapping.py derives each set at run time, so a field that becomes material -- a new profile
member, a curator's new `material_extra` -- fails it until it is mapped or listed.

**D3. One cb:EvalConditions term per condition field, typed as the field.** Each term is the field's name in
camelCase (`chain_of_thought` -> `chainOfThought`); `sampling`'s three keys become `samplingTemperature`,
`samplingTopP` and `samplingSeed`, since a bare nested key would mean a schema.org term under the upstream @vocab.
The node model copies each field's type and constraints from EvalConditions, so a node accepts what a record does.
The six condition fields no profile or entry makes material are held to the same rule, so the accounting is total:
`shot_selection` and `message_limit` are mapped; `reasoning_effort_raw` and the three `*_source` provenance fields are
listed.

**D4. The key's Benchmark side and the comparability block.** `benchmarkVersions` (on Benchmark: each version's
tag) and `subsets` (on Protocol, 08 §5.8's splits: each subset's id) carry the two lists a claim's benchmark_version
and subset name; `metrics` already carried the third. `materialFields` carries the benchmark's resolved material set
as condition terms -- derived, as `license` is -- and `ratingPoolRequired` the block's flag; `material_extra` and
`material_waived` are listed, since the resolved set already contains their effect.

**D5. Counts.** 54 terms are added (85 in all): 50 condition terms over 48 fields, plus benchmarkVersions, subsets,
materialFields and ratingPoolRequired. No term is renamed or removed, so v1 only gains terms, which is what the
/ns/* cache rule in site/public/_headers assumes. Unmapped and listed with a reason: 4 condition fields, the 2
comparability adjustments, and the 7 non-material Benchmark fields the crosswalk already listed less `subsets`, which is
now mapped.

**D6. Declared, not yet emitted.** The documents carry the new terms' values when P4-S6-T03 emits them from the
mapping. Until then each document's context declares them, the schema accepts them, and the test builds a node from
every committed conditions record through the mapping alone and validates it against the committed schema.

**D7. Left open.** `Benchmark.released` and `Benchmark.paper` have natural Croissant homes (`datePublished`,
`citeAs`), but a base term is a CROISSANT_TERMS row in schema/benchmark.py, which this decision does not change;
neither is material.

## Reviewer checks

- D2's reading of "Benchmark material field": the key's three Benchmark-side components and the comparability block.
  A narrower reading (the condition fields only) would drop benchmarkVersions, subsets, materialFields and
  ratingPoolRequired; a wider one (every Benchmark field) is the base crosswalk's job, not the material accounting's.
- `subsets` reverses the P2-S3-T06 listing ("a subset is a data split or a task variant and the record does not say
  which"): as our own term it claims neither, and 15 A8's RecordSet stays for a subset known to be a data split.
- `materialFields` is derived, not recorded; the alternative, carrying `material_extra` and `material_waived` as
  recorded, leaves a reader unable to tell the set without the profile table.
- The 16 fields material only through `material_extra` (cost_usd, hardware, wall_clock_hours, date_evaluated, sampling
  among them) are mapped, though 04 §8 calls such fields informative in general: curators declared them material for
  specific entries, and the resolver treats them so.
- The placement of `subsets` on Protocol and of the comparability terms on the cb:EvalConditions node.

## Consequences

- schema/generated/croissant-benchmark.schema.json and site/public/ns/croissant-benchmark/v1/context.jsonld are
  regenerated (`bench schema gen`). No entity schema, TypeScript type or record changes, so the migration plans no
  rows; it exists because the schema-change gate asks every schema/*.py change for one.
- **The schema freeze counter restarts.** scripts/check_schema_churn.py counts any schema/*.py code change, a new
  module included, so merging this restarts the 40-entry window the Phase 1 exit asserts (P1-S13-T07) and makes stopping
  rule (b) report a schema change after entry 60. No record has to migrate, which is what rule (b) guards against;
  whether to merge before or after P1-S13-T07, or to teach the counter that a module defining no entity is not churn,
  is the maintainer's call.
- Every benchmark document inlines the extended context: 54 more keys, about 2 KB per document before compression.
- The namespace page's one-line description of `conditions` ("a reference ... and the comparability profile") still
  holds and now undersells the group; its term list is read from the context and gains the terms by itself.
