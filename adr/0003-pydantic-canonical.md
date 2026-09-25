# ADR-0003 -- Pydantic models are the canonical schema; JSON Schema and TypeScript are generated

- **Status:** Proposed
- **Date:** 2026-09-25
- **Taxonomy version:** not affected (the vocabularies are an input to the schema; see Decision)
- **Facet:** none -- a schema-implementation decision
- **Change type:** founding decision (no row in 03 §8.1 applies)
- **Supersedes:** --
- **Superseded by:** --

## Context

The data model (04) is mostly rules, not shapes. For example:
- a contamination risk of `high` needs evidence;
- a model-graded benchmark names its judge;
- a share-alike record may not sit in the CC-BY core;
- a retired id is never reused;
- exactly one baseline is primary per (benchmark_version, metric).

A schema language that can state types and enums but not these rules leaves them to convention.
A convention is what the corpus stops meaning after a year.

The schema has three consumers:
- the Python build and validators;
- external consumers who want a language-neutral schema;
- the Astro frontend, which wants types.

It has one input it does not own: the controlled vocabularies in `taxonomy/*.yaml`, which change
by ADR (03 §8).

Three facts were measured, not assumed, and they close off the obvious alternatives (04 §12):
- **`datamodel-code-generator` cannot do the TypeScript leg.** It emits Python only (Pydantic,
  dataclasses, TypedDict, msgspec). It suits the inbound direction and not the frontend.
- **`json-schema-to-zod` was archived on 2026-06-30**, although Astro 7's Zod 4 makes it look
  natural.
- **Python 3.12, not 3.13:** scikit-learn 1.9.1 requires 3.11 or later, and the numba and UMAP
  stack the Atlas layout depends on lags new CPython releases.

## Decision

**Pydantic v2 (2.13.5) on Python 3.12 is canonical.** Everything else is generated from it and
committed, and CI fails on drift (04 §12):

```
taxonomy/*.yaml --loaded at import time--> dynamic Literal enums
schema/*.py        model_json_schema()      -> schema/generated/*.schema.json  (Draft 2020-12, committed)
                   json-schema-to-typescript@16.0.0 -> site/src/types/*.d.ts   (committed)
```

- **Vocabularies become `Literal` enums at import time.** A term that is not in `taxonomy/` fails
  validation. A taxonomy edit changes the generated schema, so `bench schema gen --check` runs on
  `taxonomy/` changes too (05 §3).
- **The taxonomy files have models of their own** (`schema/taxonomy.py`). An input to the
  canonical schema is itself validated, so a misspelled key cannot silently validate the corpus
  against the wrong vocabulary.
- **Cross-field and cross-record rules are validators in Python.** Four tiers: schema, referential,
  semantic and quality. The first three block and the fourth is report-only (04 §12). They run as
  `bench validate`.
- **The frontend gets types, not runtime validation.** Pydantic has already validated everything
  at build time. A second schema definition on the frontend would be a second thing that can drift.

## Consequences

- **Python is the only runtime validator.** A consumer in another language gets the generated JSON
  Schema, which states shapes and enums but not the cross-field rules. The rules exist in one
  place, as code with tests.
- **The committed JSON Schema is the validation schema.** It describes what a hand-written or
  ingested record may contain. Derived, computed fields such as `Metric.higher_is_better` and
  `execution.inspect_evals_available` are not in it (P0-S5-T01).
- **Every model or taxonomy change is a three-artifact commit:** the model, the generated JSON
  Schema and the generated types. `bench schema gen` writes all three, and the drift check is
  CI job 5 (05 §9).
- **Tier 4 is deliberately non-blocking.** A blocking quality check produces compliance behaviour:
  a bumped `last_verified`, an invented baseline. A visible dashboard produces better behaviour
  (04 §12).
- **The toolchain is pinned** (pyproject.toml, uv.lock, site/package.json, docs/pins.md). The
  conclusions (Pydantic canonical, Python validation over Zod, 3.12 over 3.13) do not depend on
  the exact versions, which is why 04 §12 states them as conclusions and the versions as inputs.

## Alternatives considered

- **Hand-written JSON Schema as the source of truth.** It is more language-neutral, which is a real
  advantage, but it is materially worse to author. It also gives the cross-field rules nowhere to
  live, and those rules carry most of 04. Rejected; the generated JSON Schema preserves the
  neutrality for consumers (04 §12).
- **Zod on the frontend, through `json-schema-to-zod`.** Rejected twice over. The tool was archived
  on 2026-06-30, and runtime validation on the frontend is a second schema definition that can
  drift from the first (04 §12).
- **`datamodel-code-generator` for the TypeScript leg.** Not possible: it emits Python only. It
  stays the right tool for turning third-party JSON Schema into Pydantic (04 §12).
- **Python 3.13.** Rejected for now because of the Atlas stack's lag behind new CPython releases;
  to be revisited when numba and UMAP support it (05 §3).
- **Vocabularies as hand-copied enums in the Python code.** Rejected: `taxonomy/*.yaml` is what
  the ADR process governs, and two copies of a vocabulary drift. Loading at import time makes the
  YAML the only copy.

## Migration

None: this is a founding decision. P0-S4 wrote the models and P0-S5-T01 generated and committed
the artifacts. P0-S4-T10 reconciled the three Phase-0 entries to the models without changing a
value (docs/schema-field-needs.md).

## Evidence

- 04-data-model.md §12: the pipeline, the three measured corrections, `schema/taxonomy.py`, and
  the four validation tiers.
- The models, `schema/*.py`:
  - `schema/taxonomy.py` loads the vocabularies;
  - `schema/validators.py` holds 24 tier-3 rules (P0-S4-T08).
- The generated artifacts:
  - `schema/generated/*.schema.json`: 16 files, Draft 2020-12;
  - `site/src/types/*.d.ts`: 16 files, from json-schema-to-typescript 16.0.0.
- The generator and its drift check: `tools/build/codegen.py`, `tests/test_codegen.py` and
  `.github/workflows/schema-codegen.yml` (P0-S5-T01).
- The tiers: `tools/validate/tiers.py` and `tests/cli/test_validate_tiers.py` (P0-S5-T02).
