# Governance

Who decides what in this repository, how a decision is recorded, and how disputes are settled.
It names roles, not people, so it stays true as people come and go. What happens if the
maintainers stop is in [`SUCCESSION.md`](SUCCESSION.md); expected behaviour is in
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Roles

Write access is earned in four rungs. Contributing never requires any of them: the issue forms need
no repository privileges, and a submission from a stranger is reviewed like any other.

| Role | Earned by | May |
| --- | --- | --- |
| **Contributor** | Nothing | Submit entries, corrections and disputes through the issue forms or a pull request |
| **Triage** | 5 merged substantive contributions | Label, close and request changes. No write access to `data/` |
| **Domain maintainer** | 15 merged contributions in one domain family | Review and merge within `data/benchmarks/<family>/`, through a `CODEOWNERS` entry for that path |
| **Admin** | Explicit invitation by the admins | Everything, including the rules in this file |

Three standing rules:

1. **At least two admins**, from the moment a second person exists. One admin account is a single
   point of failure that no process can mitigate.
2. **A written tie-break.** While the project is in its first year, the founding maintainer decides
   when reviewers disagree. After that, decisions are by rough consensus of the admins, and the
   tie-break falls to a named admin recorded in the repository, not to a procedure.
3. **Domain ownership lapses, reversibly and automatically.** A `CODEOWNERS` entry for a family
   whose maintainer has merged nothing in 6 months lapses to the admins. A scheduled workflow opens
   the change as a pull request labelled `governance:lapse`, mentions the maintainer, and waits 14
   days for an objection before it can merge. One merged contribution and a one-line pull request
   reinstate it.

## Who must review what

A change is merged when it has the reviews and evidence the table asks for. A reviewer is never the
change's own author.

| Change | Reviewers | Required evidence |
| --- | --- | --- |
| Typo, formatting, link fix | 0 (any maintainer may self-merge) | None |
| Adoption counters into `metrics/` | 0 (bot auto-merge) | The adapter's run record |
| New benchmark entry | 1 | Sources opened and checked; numeric fields quoted in the pull request |
| Result claim, hand-curated | 1 | Source link verified and archived; `condition_completeness` stated |
| Bulk ingest (`ingest:new`, `ingest:update`) | 1 | Rendered before/after table; adapter version; response hash |
| Numeric result change from ingest (`ingest:result`) | 1, **always a person** | Old value, new value, source URL, archive URL, fetch time |
| `verification_status` promotion | 1, not the author | The evidence cited when promoting |
| Contamination flag above `medium` | 2 | A published, linked, archived evidence source |
| Lifecycle to `retracted`, `disputed` or `dead` | 2 | A public rationale and the observable signal behind it |
| Human baseline addition | 2 | The baseline's methodology, n, population and time limit |
| Taxonomy term addition or definition change | 2 + ADR | See [Decisions](#how-decisions-are-recorded) |
| Moving a capability between capability groups | 2 + ADR | The published gap claims it re-shapes, named |
| Schema change | 2 + ADR + migration script + full revalidation | Regenerated JSON Schema and TypeScript types in the same pull request |
| Licence, governance or succession change | 2, both of them admins | ADR |

The table is deliberately lopsided. **Fixing a wrong number is the easiest change in the repository;
adding a vocabulary term is one of the hardest.** An open vocabulary decays into synonyms within
months and quietly breaks the coverage analysis, while a project that makes corrections hard
accumulates errors while it debates terminology.

## How decisions are recorded

- **Entries and claims:** by the pull request that changes them. The git history is the record, and
  a substantive correction carries a `Correction:` trailer so it appears on the public corrections
  page.
- **Taxonomy and schema:** by an Architecture Decision Record in `adr/`, numbered, immutable once
  merged, and superseded rather than edited. The change types, their version impact, and whether each
  needs a migration script are fixed in the taxonomy build process (`_plan/03-taxonomy-build-process.md`
  §8.1): adding a term is MINOR, merging, splitting or retiring one is MAJOR, and a term id that has
  been published is never reused.
- **Every accepted taxonomy or schema change also gets a [`CHANGELOG.md`](CHANGELOG.md) entry**,
  naming its ADR and migration script, written by the change's own pull request. CI rejects a schema
  or taxonomy diff that lacks its ADR or its migration script, so the changelog lists only changes
  that passed that gate. Data changes are never listed there; they live in the git history.
- **Governance itself** changes only by an ADR reviewed by two admins, like the licence and
  `SUCCESSION.md`.

## Disputes about the data

Anyone can dispute an entry, including a benchmark's maintainers and the organisations whose
systems are scored.

- **A dispute is never resolved by deletion.** The disputed claim records the dispute, a file appears
  in `data/disputes/`, and both positions are shown with their sources. Deleting a contested number
  would turn a public disagreement into a private one.
- **If the index is wrong, the fix is a commit with a rationale**, and the history keeps what was
  shown before. Nothing is edited quietly.
- **An evaluated party's dispute is treated like anyone else's**, and the record says who raised it:
  an organisation contesting its own score is itself useful information.

Requests to remove personal data are handled separately, through the contact route that
`SECURITY.md` will publish (it is not written yet), and each request and its outcome are recorded.

## Conduct

Conduct problems are reported as [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) says, and handled by
the admins. An admin who is party to a report takes no part in handling it.
