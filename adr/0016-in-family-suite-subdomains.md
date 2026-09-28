# ADR-0016 -- Add a suite subdomain to the families whose corpus entries need one

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** domain
- **Change type:** add, three subdomains (03 §8.1: MINOR, no migration, two reviewers)
- **Supersedes:** --
- **Superseded by:** --
- **Applied:** taxonomy 0.9.0, P1-S1-T07. P1-S1-T08 re-classifies the fields it touches

## Context

Four entries have an unambiguous family and no legal primary. Each is a suite whose tasks span several
of its family's subdomains, and no one subdomain holds them:

| Entry | Family | What it spans | Failure |
| --- | --- | --- | --- |
| MedHELM | medicine-health | 35 benchmarks across five clinical categories, including note generation, patient messaging and administration, which no subdomain covers | medhelm-001 |
| HAL | agents-tooluse | Nine existing agent benchmarks (web navigation, tool calling, research agents, coding), on separate boards with no aggregate | holistic-agent-leaderboard-hal-001 |
| Kaggle Game Arena | games-planning | 19 boards across board games, imperfect-information card games, social deduction and bargaining | kaggle-game-arena-001 |
| BALROG | games-planning | Six RL environments (BabyAI, Crafter, TextWorld, Baba Is AI, MiniHack, NetHack), averaged into one progress score | balrog-001 |

The escape routes were each tried and fail on their own tests:
- `general-intelligence/agi-composite-suites` needs "a single general-capability score", and it is
  cross-field by the family's definition. The breadth of these four is inside one field, and
  general-intelligence's exclusion forbids using the family "as a home for benchmarks that were
  hard to place".
- A majority subdomain doesn't exist for any of them.
- A bare family is never assignable (02 §3).

All four abstain with a blocking `missing-term`, and all four propose a family-level suite subdomain.

The shape is known and will recur. 02 §11 rule 4 already gives suites children that inherit and
override (DCASE's seven tasks), and 02 §12.5 classifies one Kaggle Game Arena board,
`kaggle-game-arena-chess`, as its own entry under `games-planning/board-games`. What neither
provides is a primary for the parent record itself.

## Decision

Add one suite subdomain to each of the three families that need one now:

- `medicine-health/clinical-task-suites`
- `agents-tooluse/agent-evaluation-suites`
- `games-planning/multi-game-suites`, which covers both the arena (Kaggle Game Arena) and the suite
  (BALROG). Whether the games are played against other entrants or against environments is carried
  by `evaluation_method` (`tournament-play` for an arena), not by the domain.

All three share one definition and one pair of tests, with the family substituted:

```yaml
definition: >
  Suites whose scored tasks span several of this family's subdomains, reported per task or as one
  aggregate, where the suite's own claim is coverage within the family.
inclusion_test: >
  Tag this as PRIMARY if the tasks span two or more of the family's subdomains, no one subdomain
  holds most of them, and the benchmark's own claim is breadth within the family. Record the
  subdomains the tasks fall in as secondary.
exclusion_test: >
  Do NOT tag this if one subdomain holds most of the tasks (tag that subdomain primary and the
  others secondary), or if the suite spans several families, which is `general-intelligence`.
```

A suite subdomain is added to a family only when an entry needs one, and each later addition is an
`add` ADR that cites this one. The pattern is not pre-populated across all eighteen families,
because an empty subdomain is a row of the coverage matrix that reports a gap in something nobody
builds.

None of the three leaves equals a capability id, so checks 9d and 9e are unaffected.

## Consequences

- P1-S1-T08 re-runs `domain.primary` for the four entries, which resolves their blocking records.
  The secondaries the classifiers already recorded stand.
- Per 02 §11 rule 4, a suite's children (a HAL board, a Kaggle Game Arena game, a MedHELM scenario)
  are classified as their own entries under their own subdomains, as 02 §12.5 does for chess. The
  parent's primary does not propagate to them, because children override.
- The coverage matrix gains three subdomain rows. Their cells count suites, not task coverage, so
  the gap ranking must read a suite row as "is there a suite", not as coverage of the field. P1-S1-T07
  records that note in each term's definition block.
- HELM Capabilities and the Epoch Capabilities Index stay in `agi-composite-suites`. They are
  cross-field and publish a single aggregate, which is the case that subdomain exists for.

## Alternatives considered

- **Allow a bare family as primary when the entry is flagged as a suite.** Rejected. It breaks 02
  §3's rule that the family is a navigational node, and it adds a special case to every query and
  every coverage count, where three subdomains add none.
- **Classify only the children and give the parent no domain.** Rejected. The parent is what is
  cited ("MedHELM", "HAL"), and a record with no primary cannot be placed or found.
- **One cross-family `suites` family.** Rejected. It would take suites out of the family whose
  field they measure, which is the first filter a reader applies.

## Migration

None, pre-freeze. P1-S1-T08 re-classifies `domain.primary` for the four entries.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-medhelm-001.yaml
- taxonomy/_failures/2026-09-28-holistic-agent-leaderboard-hal-001.yaml
- taxonomy/_failures/2026-09-28-kaggle-game-arena-001.yaml
- taxonomy/_failures/2026-09-28-balrog-001.yaml
