# ADR-0002 -- The index is YAML in git; the database is a build artifact

- **Status:** Proposed
- **Date:** 2026-09-25
- **Taxonomy version:** not affected
- **Facet:** none -- a repository and workflow decision
- **Change type:** founding decision (no row in 03 §8.1 applies)
- **Supersedes:** --
- **Superseded by:** --

## Context

The index exists to be trusted about numbers other people publish. The positioning in 01 rests
on one property: a reader can check where any number came from, and nobody can change it quietly
(05 §1). The closed operators in the space, such as BenchmarkList, llm-stats and BenchLM, keep their
records in databases. A number changing from 0.412 to 0.487 on such a site leaves no public trace.

The corpus is also meant to outlive its maintainers (05 §10, ADR-0005). What a stranger has to be
able to fork in 2029 is the data together with the schema that validates it, the build that renders
it, and the documented procedure for running both.

The corpus has two write paths:
- **Curators**, including outside experts with no git experience. The issue form (05 §6) serves
  them.
- **Bots:** ingest adapters and the archiver, which write through pull requests.

## Decision

**The index lives as YAML files in version control, one entity per file.** A database, SQLite
included, is only ever a build artifact, never the source of truth (05 §1). Every change is
therefore a commit with an author, a date and a reviewable rationale. The maintainers change data
the way a stranger does: a commit on a branch, reviewed. The dataset can be cited at a commit hash.

- **One repository** holds data, schema, tools, ingestion adapters and site (05 §1, "One
  repository, not two"). Scrapers run as GitHub Actions cron jobs in that repository.
- **One entity per file, at a path its id decides** (05 §2): `data/benchmarks/<domain-family>/<id>.yaml`,
  `data/sources/<yyyy>/<src-id>.yaml`, `data/claims/<benchmark-id>/<claim-id>.yaml`, and so on.
- **No index files.** The build derives every index; nothing aggregates by hand.
- **Content-derived ids** for conditions and claims (`cond-` and `claim-` plus 12 hex), so no
  shared counter exists to contend on (05 §2).

## Consequences

Git is a poor database, and this decision is sound only if its costs are paid deliberately.
05 §1's table, which this ADR adopts as its statement of the cost:

| Cost | Consequence | Mitigation |
| --- | --- | --- |
| No transactional writes | A rename that touches 40 files can land half-applied if a PR is partially merged | CI validates referential integrity on the merged tree, not on the diff; `main` is protected and squash-merged so a PR is one atomic commit |
| No concurrent editing | Two curators editing the same benchmark produce a conflict | One entity per file, narrow file scope; `bench claim` and `bench new` allocate content-derived IDs so there is never a shared counter to contend on |
| Merge conflicts on hot files | `taxonomy/*.yaml` and any index file are contention points | Taxonomy changes go through ADRs and are rare by design; there are **no index files** -- the build derives every index, so nothing aggregates by hand |
| Cosmetic diffs | Two editors' YAML formatting differ, producing noise that hides real changes | `bench fmt` normalises key order, quoting, line width and list style; CI fails on any file `bench fmt` would change |
| No referential integrity at write time | A claim can reference a benchmark that does not exist | CI's referential tier catches it before merge; this is a review-latency cost, not a correctness one |
| Review latency | A contributor waits hours or days for a human | The issue-form path (§6) removes git from the contributor's side entirely; batch ingest PRs remove it from the bot's side |

The mitigation that matters most is one entity per file with narrow scope. Ten thousand small
files are comfortable for git; forty large files that everyone edits are not. Further consequences:

- **Site churn can pollute the data history.** The mitigations are path-scoped `CODEOWNERS`, a
  convention that data commits never touch code (CI warns on mixed commits), and a data-only
  mirror (`uaibi-data`) of `data/`, `taxonomy/` and `schema/` pushed on every release (05 §1).
- **Formatting is a gate.** Two YAML writers produce two formats, so there is one emitter
  (07 §1.5), shared by `bench fmt` and every adapter, and `bench fmt --check` is CI job 1 (05 §9).
- **Content-derived ids make ids unmemorable.** The site's claim URLs are readable
  `/claim/<benchmark>/<system>/<metric>` paths, and `bench diff` prints labels, not hashes (05 §2).
  In exchange, re-running an adapter is idempotent and a collision is a signal, not a bug.
- **Floats must be emitted one way.** A float written two ways gives the same measurement two
  `claim-` ids, so the emitter writes `repr(round(x, 6))` and refuses a value it would have to
  change (07 §1.5; tools/fmt.py).

## Alternatives considered

- **A database as the source of truth, with an admin interface.** Rejected: changes become
  invisible, there is a privileged mutation path, and neither the corpus nor its history can be
  forked or cited at a point in time. That is the property that separates this index from the
  closed operators (05 §1).
- **Two repositories, data and code.** Rejected for succession: a fork gets one half of what it
  needs. It would also put the scrapers outside the repository they write to, adding a deploy step
  and secret-syncing (05 §1, 07). The data-only mirror serves consumers who want the core alone.
- **Sequential claim ids (`claim-00042`), the earlier draft's scheme.** Rejected: a global counter
  is a hot file every contributor and bot must read-modify-write. It guarantees merge conflicts when
  throughput is highest, during a bulk ingest of roughly 6,598 rows (05 §2).
- **Hand-maintained index files** (a benchmark list, a per-domain table). Rejected: they are
  contention points and drift from the entities they summarise. The build derives them.

## Migration

None: this is a founding decision. The corpus has had this shape since P0-S3. P0-S5-T04 brought
the 39 files under `data/` to `bench fmt`'s normal form. That pass changed no value, and it was
checked against the previous commit.

## Evidence

- 05-repository-and-workflow.md §1 ("Data as git", "The honest cost", "One repository, not two"),
  §2 (layout and file naming), §9 (CI jobs 1-3).
- The corpus layout: `data/benchmarks/{biology-genetics,code,robotics-embodiment}/`,
  `data/sources/2026/` (35 Source records).
- `tools/fmt.py` and `tests/cli/test_fmt.py` (P0-S5-T04): the one emitter, and `bench fmt --check`.
- `tools/validate/tiers.py` and `tests/cli/test_validate_tiers.py` (P0-S5-T02): the referential tier
  that catches, before merge, what git cannot enforce at write time. `pr-validate.yml`, which runs
  both on every pull request, is not yet written.
