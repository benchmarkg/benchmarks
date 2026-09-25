# ADR-0001 -- Classify benchmarks by facets, not by a hierarchy

- **Status:** Proposed
- **Date:** 2026-09-25
- **Taxonomy version:** 0.1.0 (pre-freeze)
- **Facet:** all -- the structure of the taxonomy, not a term within it
- **Change type:** founding decision (no row in 03 §8.1 applies: nothing exists to add to, split or retire)
- **Supersedes:** --
- **Superseded by:** --

## Context

The index has to place benchmarks that belong to several fields at once, and in the non-language
half of the map those are the majority, not the exceptions (02 §1):

- **CASP** is structural biology, prediction and wet-lab ground truth at once. Its assessors publish
  peer-reviewed papers beside the ranking tables, and servers and expert groups are ranked
  separately.
- **ARC-AGI** is visual reasoning, abstraction and general intelligence, and ARC-AGI-3 is also an
  interactive environment.
- **RLBench** is robotics, vision and simulation; **OCx24** is computational chemistry scored by a
  wet-lab measurement; **MLE-bench** is ML engineering, agentic tool use and a human-comparison
  battery.

A single tree forces each of these under one false parent, and every exception is then fought
forever.

The three Phase-0 entries (P0-S3) were written from their primary sources with no schema in front of
the author, on purpose. P0-S3-T05 reconciled every field they used, and P0-S4-T10 reconciled the
schema back against them (docs/schema-field-needs.md). They are the first evidence about this
decision that the plan itself did not write:

- **Every entry needed more than one domain.** Each also needed a secondary axis the others did not
  share:
  - CASP needed per-edition categories.
  - RoboArena needed a language-conditioned secondary.
  - SWE-bench needed a subject it was not designed for (`observed_subjects`: built for prompted
    models, used by agents).
- **All three recorded near-miss terms with reasons** (`*_considered_and_rejected`), for every facet
  they tagged. A tree has no place for "this was considered and is not it". A flat facet does,
  because each term is judged on its own inclusion test.
- **The facets held; the vocabularies were incomplete.** Three values were missing:
  - CASP's `activity: assessment-in-progress`;
  - RoboArena's `data_provenance: evaluator-improvised`;
  - a `submission_process` term for SWE-bench's artifact-backed self-reporting.

  None was a missing *axis*, and each went to `tags[]`, 02 §11 rule 7's escape hatch, pending the
  vocabulary owners. That is what a faceted design predicts: growth happens inside a facet, not by
  restructuring.

## Decision

Classify benchmarks by **faceted classification** (02 §1, §2):

- **Domain is the navigational spine**, two levels (`family/subdomain`). It drives the site's browse
  structure and the Atlas clusters. A benchmark has exactly one *primary* domain, which must be a
  subdomain leaf (families are navigational only), and any number of *secondary* domains.
- **Seven further facets are flat, multi-valued and orthogonal:**
  - Capability;
  - Evaluation method;
  - Subject under test;
  - Data properties;
  - Lifecycle;
  - Governance and host;
  - Execution cost and reproducibility.

  They drive filtering, the coverage matrix and the comparability warnings.
- **Every vocabulary is a closed enum** in `taxonomy/`, validated in CI and loaded into the Pydantic
  schema at import time. Changing one requires an ADR (03 §8). `tags[]` is the free-text release
  valve. It is searchable, never validated, and excluded from the coverage matrix.
- **Tagging is progressive.** A `stub` needs three decisions (`domain.primary`, `lifecycle`, a
  homepage). A `full` entry needs all eight facets and sourced fields. The site renders both, with the
  completeness state visible (02 §1, "The cost of facets").

Prior art is inherited, not reinvented:
- **HELM's scenario taxonomy** is recorded as ancestry, never as equivalence
  (`taxonomy/crosswalks/helm.yaml`).
- **Every Eval Ever's condition field names** are crosswalked rather than adopted
  (`taxonomy/crosswalks/eee.yaml`).
- **The Papers with Code task taxonomy** is used as a reconciliation key only, because it is
  CC-BY-SA (03 §2).

## Consequences

- **An entry is more work than in a tree.** A `full` entry makes about twenty vocabulary-valued
  decisions across nineteen controlled vocabularies (02 §1, §14). Progressive tagging is what keeps
  the catalogue from stalling. The seed target is 70% `full`: the seven Core families at 100%, and
  45% of the rest.
- **Counts need rules a tree would not.**
  - The coverage matrix weighs a primary domain at 1.0 and a secondary at 0.5, labelled "weighted
    benchmark count" and never "count".
  - Cell *state* is decided by presence at any weight.
  - All published counts are family counts (02 §11 rules 1 and 5).
- **Same word, two facets.** The same word can be a capability and a subdomain leaf. Such homographs
  are declared, never prevented, and their cells are marked occupied-by-construction (02 §11 rule 11;
  CI checks 9c–9e).
- **Fields can overlap.** Several fields encode overlapping facts, such as lifecycle, activity and
  maintenance status, or access, submission process and blockers. So the combinations are checked
  across fields, not field by field: 02 §11's legality matrix and implications, in
  `schema/validators.py`.
- **The entries need structure a flat record lacks.** The schema carries per-field evidence and
  notes, as annotations of the field they qualify, plus a near-miss list per facet. Both came from
  the Phase-0 entries (docs/schema-field-needs.md, groups `evidence`, `field_notes`, `rejected`).
- **Adding a term is cheap; removing one in use is expensive.** That asymmetry is deliberate (03 §8.1).

## Alternatives considered

- **A single hierarchy.** Rejected: every benchmark in the Context section needs two or more
  parents. Picking one hides the others from browse and from the coverage matrix, which makes the gap
  analysis report artefacts of placement.
- **Open tags only (a folksonomy).** Rejected: an open vocabulary degrades into synonyms within
  months, and the coverage matrix's empty cells, which are the product, stop meaning anything (02
  §2). Tags survive as the escape hatch, outside the matrix.
- **Adopt HELM's taxonomy wholesale.** Rejected: it entered maintenance mode on 2026-06-01, so it will
  not track new terms. It is also centred on language-model scenarios, and a protein-structure or
  wet-lab benchmark has no home in it. It is kept as ancestry.
- **Adopt the Papers with Code task taxonomy.** Rejected: it is the largest cold-start vocabulary
  available, but it is CC-BY-SA-4.0, and a derived taxonomy file would inherit the share-alike
  obligation and relicense the CC-BY core (03 §2, 06 §3.9).

## Migration

None for the taxonomy: this is the founding decision, and the vocabularies are pre-freeze (0.1.0).

The three Phase-0 entries were reconciled to the schema by P0-S4-T10. That pass changed no value.
It renamed keys to the schema's names, moved blocks to their schema homes, removed each entry's
`_schema_findings` into docs/schema-field-needs.md, and folded the reviewer checks into
`curation.notes`. The one exception is CASP's out-of-vocabulary activity, which became `unknown` with
the term in `tags[]`. docs/schema-field-needs.md, section "Resolution (P0-S4-T10)", lists every
rename.
