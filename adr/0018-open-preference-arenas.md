# ADR-0018 -- Add the subdomain `general-intelligence/open-preference-arenas`

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** domain
- **Change type:** add (03 §8.1: MINOR, no migration, two reviewers)
- **Supersedes:** --
- **Superseded by:** --
- **Applied:** taxonomy 0.9.0, P1-S1-T07. P1-S1-T08 re-classifies the fields it touches

## Context

LMArena has no legal primary domain (lmarena-001, blocking). It claims breadth of real use, judged by
people: "an open platform for evaluating LLMs based on human preferences", with crowdsourced prompts
"sufficiently diverse to encompass a wide range of LLM use cases". The corpus entry is the 2026
platform, whose text, vision, webdev, image, video and search arenas are separate leaderboards with no
score across them.

- **`general-intelligence` fits.** Its inclusion test, "coverage of many fields", matches the
  claim, and the corpus files the entry there.
- **No subdomain of the family fits.**
  - `human-comparison-batteries` compares systems with measured human performance; here humans are
    the judges, not a comparison population.
  - `agi-composite-suites` needs a task set aggregated into one score, and the arena has a stream of
    user prompts and no aggregate.
- **Outside the family, nothing fits either.**
  - `language/dialogue` scores a multi-turn conversation as a whole, while the text arena's
    conversations average 1.3 turns, and the image, video and webdev arenas are not language
    benchmarks.
  - `multimodal/any-to-any-generation` fits only the generation arenas.

The vocabulary already carries everything else about an arena: `evaluation_method:
pairwise-preference-elo`, `governance.submission_process: live-arena`,
`comparability.rating_pool_required`, and `generative-media-model` for the media arenas (02 §6). An
arena confined to one field already has a home in that field: RoboArena is
`robotics-embodiment/manipulation` (02 §12.2). What is missing is only the primary for an arena whose
claim is breadth.

## Decision

Add one subdomain:

```yaml
- id: general-intelligence/open-preference-arenas
  label: Open preference arenas
  parent: general-intelligence
  status: proposed
  introduced_in: 1.0.0
  source: own
  definition: >
    Open platforms where people submit their own prompts and choose between anonymised system
    outputs, and systems are ranked by a rating model over the votes, across many uses.
  inclusion_test: >
    Tag this as PRIMARY if prompts come from the public rather than a fixed item set, the score is
    a rating fitted to human pairwise votes, and the arena's own claim is general usefulness across
    many uses or modalities.
  exclusion_test: >
    Do NOT tag this if the arena is confined to one field or task (a robotics, coding or
    text-to-speech arena takes that field's subdomain, as RoboArena does), or if the judges are a
    model rather than people (`model-graded-judge` on the arena's own domain).
  examples:
    - ref: lmarena
      qualifies: true
      why: Public prompts, anonymous pairwise votes and ratings across text, vision and generation arenas.
    - ref: roboarena
      qualifies: false
      why: NEAR MISS. Pairwise human preference over rollouts, but confined to robot manipulation.
```

The leaf equals no capability id, so checks 9d and 9e are unaffected.

## Consequences

- P1-S1-T08 re-runs `domain.primary` for LMArena, which resolves lmarena-001.
- Under 02 §11 rule 4, each arena (text, WebDev, vision, image, video, search) may become a child entry
  with its own domain. WebDev Arena, for example, would take a `code` subdomain, and the text-to-image
  arena a `vision` subdomain with `generative-media-model`. The parent keeps this subdomain. P1-S1-T08 does not create children.
  That is curation, not re-classification.
- The family ambiguity the classifier logged (the paper is the 2024 text-only Chatbot Arena, while the
  entry is the 2026 platform) is unchanged. It is a question of editions, not of domain.

## Alternatives considered

- **Classify the platform by its text arena, as `language/dialogue`.** Rejected. It fails that
  subdomain's own test and misfiles the media arenas.
- **Widen `human-comparison-batteries` to any benchmark with humans in the loop.** Rejected. It would
  merge human judges with a human comparison population, which are different measurements and are
  read differently.
- **Treat an arena as a suite under ADR-0016.** Rejected. ADR-0016's suite subdomains are inside one
  family, and this arena spans families. `agi-composite-suites` is the cross-family suite term, and it
  needs a task set and an aggregate, which an arena does not have.

## Migration

None, pre-freeze. P1-S1-T08 re-classifies `domain.primary` for LMArena.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-lmarena-001.yaml
