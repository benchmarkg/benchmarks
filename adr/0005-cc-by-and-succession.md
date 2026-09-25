# ADR-0005 -- Plain CC-BY for the data, MIT for the code, and a written succession plan

- **Status:** Proposed
- **Date:** 2026-09-25
- **Taxonomy version:** not affected (`taxonomy/` is licensed CC-BY-4.0 with the data)
- **Facet:** none -- a licensing and governance decision
- **Change type:** founding decision (no row in 03 §8.1 applies)
- **Supersedes:** --
- **Superseded by:** --

## Context

Catalogues in this space die, and the way they die depends on their licence and their ownership:
- **Papers with Code** died when a single corporate owner deprioritised it, and 9,327 benchmarks
  went with it (05 §10).
- **Ecosystem Graphs** is unrescuable: 274 people starred a dataset nobody is legally clear to
  continue (05 §10).
- **HELM** entered maintenance mode on 2026-06-01. MedHELM survived by spinning out to an
  independent steward: the vertical that found a steward lived, and the parent did not (05 §10).

The licences of the neighbours (05 §12):
- Benchmark Radar is CC BY-NC-SA;
- the Papers with Code archive and Evaluation Cards are CC BY-SA;
- BenchmarkList and llm-stats are closed;
- Artificial Analysis bars redistribution.

Plain CC-BY is nearly unoccupied ground. The adopters that matter need to build on the index:
- a company embedding the facet vocabulary in an internal eval tool;
- a regulator referencing the registry in guidance;
- a commercial eval vendor building a product on top.

One inbound source is share-alike: the Papers with Code archive, CC-BY-SA-4.0, which the index
uses for name-to-id reconciliation keys.

## Decision

**Licences, by path** (05 §12), mapped by `REUSE.toml` so they can be checked by machine:

| Path | Licence |
| --- | --- |
| `data/`, `taxonomy/`, `docs/`, `evals/golden/` (and `adr/`, root documents such as `SUCCESSION.md`) | **CC-BY-4.0** |
| `tools/`, `ingest/`, `schema/`, `site/`, workflows, `scripts/`, `tests/` | **MIT** |
| `vendor/pwc-archive/` | CC-BY-SA-4.0, inherited and quarantined |
| `metrics/` | CC0-1.0 |
| the `croissant-benchmark` extension (a separate repository) | CC-BY-4.0 |

- **No share-alike, no non-commercial clause, no "contact us"** on the core. CC-BY makes the index
  citable and reusable, and it is the only licence under which companies, regulators and
  commercial vendors can build. It is cheap for this project to claim and hard for incumbents to
  retrofit (05 §12).
- **MIT, not Apache-2.0, for the code.** Apache-2.0's explicit patent grant is the better
  instrument in the abstract. This project, though, is a schema, a validator, a static-site build
  and some scrapers, with no patentable mechanism. MIT is what the neighbourhood uses:
  `inspect_evals`, Every Eval Ever's code, `lm-evaluation-harness`, HELM and Dynabench. Matching it
  removes a friction the project gets nothing for (05 §12). This ADR is where that choice is
  revisited, rather than re-argued.
- **Share-alike content never enters the core.** `vendor/pwc-archive/`, which does not exist yet,
  is to hold reconciliation keys only, with no prose. 04 §9's licence firewall decides where a record derived from each licence
  class may live, and it is a blocking tier-3 rule, not a convention.
- **Succession is written down before it matters,** in `SUCCESSION.md` at the repository root
  (05 §10). Its seven commitments:
  1. the licence permits a fork without asking anyone;
  2. every release is citable and downloadable independently of the maintainers (a Zenodo DOI per
     quarterly release, under a concept DOI);
  3. mirrors (Codeberg, a Hugging Face dataset, and an explicit Software Heritage save request)
     are pushed on every release;
  4. the build is documented and rebuilt monthly on a clean runner (`reproduce.yml`);
  5. dormancy is announced automatically, and the steward search comes before the public banner:
     at 90 days without a human commit to `data/`, succession is invoked; at 180 days, the
     site-wide staleness banner turns on;
  6. per-domain stewards own their families through path-scoped `CODEOWNERS`;
  7. a named handover order: per-domain stewards, then MLCommons, then the EvalEval coalition,
     then a university group. Failing all of those, the final release stays DOI'd, the banner
     visible and the licence permissive.

## Consequences

- **A well-funded competitor may ingest the whole index and ship a closed product over it,** owing
  nothing but attribution. The cost is real and accepted. The moat is not the data snapshot: it is
  the curation cadence, the provenance chain, the comparability machinery and the community, none
  of which fork cleanly. A competitor who takes the data still has to keep it true (05 §12).
- **One decision does two jobs.** The permissive licence is both the adoption mechanism and the
  survival mechanism: a successor needs no permission.
- **Every inbound source's licence is recorded:** each Source carries `licence_class` and
  `licence_checked_on`. Placement is checked mechanically by the `licence-placement` rule, so a
  share-alike record under `data/` blocks the merge.
- **Attribution becomes an obligation the build must meet:** `docs/attribution.md` is generated
  from `data/sources/` (05 §2).
- **Some of these commitments are not mechanisms yet.** The following do not exist as of this ADR:
  - `docs/reproduce.md` and `reproduce.yml`;
  - the dormancy triggers and their fake-clock CI test;
  - the mirrors;
  - a CI job running `reuse lint`. It is run by hand today; `REUSE.toml`'s header says CI runs it,
    which is true only once `pr-validate.yml` lands.

  Until these are built, the commitments are promises. 05 §10 names that distinction as the one
  that matters.

## Alternatives considered

- **CC-BY-SA for the data.** Rejected: share-alike blocks the adoption that matters (company,
  regulator, vendor). Deriving from share-alike content would also carry the obligation into the
  core and relicense it. That is why the Papers with Code archive is quarantined in `vendor/`
  (05 §12, 04 §9).
- **A non-commercial licence (CC-BY-NC, CC-BY-NC-SA).** Rejected: it forecloses commercial eval
  vendors and most institutional reuse. It also cannot be continued by a successor without
  clearing the question, which is Ecosystem Graphs' failure (05 §10).
- **Closed, or redistribution barred, as several neighbours are.** Rejected: incompatible with
  forking, with citation at a commit, and with the trust position (ADR-0002).
- **Apache-2.0 for the code.** Considered and not adopted, for the reason above. Revisit if the
  project ever produces a patentable mechanism.
- **No written succession plan; decide when it happens.** Rejected: the projects that did not write
  it down could not be rescued (05 §10).
- **The staleness banner before the steward search.** This was an earlier draft's order. Rejected:
  the search has to start while the data is still worth taking on, whereas the banner is a public
  admission that it no longer is (05 §10).

## Migration

None: this is a founding decision. The licence files and `REUSE.toml` were written in P0-S7-T01,
`CITATION.cff` in P0-S7-T02, and `SUCCESSION.md` in P0-S7-T03, which is still awaiting review. `reuse lint` passes on the repository as of this ADR.

## Evidence

- 05-repository-and-workflow.md §10 ("Releases and DOI", "What happens when we stop") and §12
  ("Licensing our own outputs").
- The licence files: `LICENSE-DATA` (CC-BY-4.0), `LICENSE-CODE` (MIT), and the `LICENSES/` texts.
- `REUSE.toml`: the per-path SPDX map, compliant with REUSE 3.3 (`reuse lint`).
- `SUCCESSION.md`: the seven commitments, at the repository root. `CITATION.cff` is also there.
- The licence firewall: 04-data-model.md §9, and `schema/validators.py`'s `licence-placement` rule
  and its `PLACEMENT` table (P0-S4-T08).
