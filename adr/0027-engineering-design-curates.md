# ADR-0027 -- Engineering-design curates to its floor of 12; it is not muted

- **Status:** Accepted -- the maintainer's decision on P1-S8-T02 (a human gate), recorded 2026-11-18 from their
  answer to the decision list ("I agree with all your recommendations", the recommendation being "curate").
- **Date:** 2026-11-18
- **Taxonomy version:** not affected. `coverage_status` stays `surveyed` in taxonomy/domains.yaml.
- **Facet:** none. A curation-plan decision under 02-taxonomy.md §3's floor rule
- **Change type:** plan decision; no schema or vocabulary change
- **Supersedes:** --
- **Superseded by:** --

## Context

02-taxonomy.md §3 gives engineering-design a hard floor of 12 entries and one exemption: a family whose
scoping survey cannot find twelve credible benchmarks is muted (`coverage_status: under-surveyed`) and
published with that badge instead of being padded. P1-S8-T02 asks a person to read the survey count against
the floor and decide.

The survey (data/surveys/engineering-design/_family-scoping.yaml, P0-S10-T03, conducted 2026-09-23) counts
**25** credible Tier-1 families by its three-part test, or **22** without its three weakest. Both are above 12.
The spread is uneven: circuit-eda holds 8, experimental-apparatus-design 1. The corpus holds one entry today
(circuitnet), so `python scripts/check_floor_rule.py --family engineering-design` reports 1 against 12, "below
its floor", and the family is the only one failing the P1-S13-T06 launch gate.

The sweep of 2026-11-17 (docs/sweeps/log/2026-11-17-engineering-design.yaml) found all four of the family's
hubs live and current (the CAD Contest at ICCAD, the ISPD contest, Parametric CAD Bench and Learn2Design), so
nothing seen since the survey lowers its count.

## Decision

**Curate to 12. The family is not muted.** P1-S8-T03 (6 entries) and P1-S8-T04 (12) proceed; their "skip if
muted" step does not apply. `coverage_status` stays `surveyed`.

The survey's own `accepted_by` stays null: this decision rests on its count, not on an acceptance of each
candidate. Each candidate is accepted or dropped when its entry is curated, by the usual rule that every field
is re-read from a fetched primary source.

## Consequences

- Curation picks from the survey's families, spreading across subdomains before filling circuit-eda, so the
  family's coverage row is not one dense cell. experimental-apparatus-design may stay at one entry; that is a
  gap-matrix finding, not a failure.
- If curation finds that fewer than twelve candidates survive the re-read, P1-S8-T02 reopens and muting is
  back on the table. A count that falls below the floor is not padded.
