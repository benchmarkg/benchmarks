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

- The taxonomy vocabularies at version 0.1.0: capability (44 terms), evaluation method (27), subject
  (18), domain (19 families, 204 subdomains), and the field vocabularies for data properties,
  ceiling anchors, lifecycle, maintenance status, governance and execution. Pre-freeze drafts;
  nothing is stable before 1.0.0. ADR: none (initial vocabulary). Migration: none
- Pydantic models for every `taxonomy/*.yaml` file (`schema/taxonomy.py`) and the `Source` record
  (`schema/source.py`). ADR: none (initial schema). Migration: none
