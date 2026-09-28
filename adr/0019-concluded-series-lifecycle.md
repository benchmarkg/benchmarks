# ADR-0019 -- A concluded competition series keeps its lifecycle, and its ending goes to `activity`

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** lifecycle
- **Change type:** edit definition prose, `dormant` and `mature` (03 §8.1: PATCH, no migration, one
  reviewer). No term is added.
- **Supersedes:** --
- **Superseded by:** --

## Context

The VoxSRC maintainers state that "The series of VoxSRC challenges has now officially finished". The
classifier found no lifecycle term for that, abstained, and logged a blocking `missing-term`
proposing `concluded` (voxsrc-retired-2023-003). The other terms were each ruled out:
- `dormant` is "neither maintained nor formally ended".
- `deprecated` needs advice against use.
- `retracted` needs a withdrawal.
- `mature` "reads as current and loses the ending".

Two non-blocking records hit the same question. HELM "entered maintenance mode on June 1, 2026",
with "no new evaluations ... added to the HELM leaderboards". MedHELM and HELM Capabilities both took
`mature` as an escape hatch for that formal freeze (medhelm-007, helm-capabilities-004).

02 has already answered this, and the answer is not a new term:
- 02 §8 retired `archived` as a lifecycle value because "It conflated `dormant` (the instrument's
  standing) with `closed` (the competition) and `abandoned` (the code)", and split those three into
  `lifecycle`, `activity` and `maintenance_status`.
- 02 §8 introduces `activity` with VoxSRC by name: it "ran 2019–2023 ... and retired as an annual
  challenge while remaining heavily cited. Without this field, all three look identical to
  `dormant`."
- The legality matrix in 02 §11 has a row for exactly this case: `active` + `closed` +
  `actively-maintained`, "The competition ended; the artefact is maintained and cited (VoxSRC)".

A `concluded` lifecycle term would re-introduce the conflation 02 removed, because it would record a
competition's ending on the instrument's field. The gap is that the definitions of `dormant` and
`mature` do not say where a formal ending goes, so a careful classifier reading only the terms could
not find it.

## Decision

**No term is added.** A formally concluded competition series, or a result record its maintainer has
frozen, keeps the lifecycle that describes the instrument. The ending is recorded in `activity`:
`closed`, or `leaderboard-live-no-round` where a permanent phase stays open.

The two definitions gain one sentence each (P1-S1-T07):

```yaml
- id: dormant
  definition: >
    The benchmark is neither maintained nor formally ended, and no activity has been observed
    for long enough that it should not be read as current. A formally ended competition series is
    not dormant: its ending is recorded in `activity`, and `lifecycle` keeps the instrument's
    standing.
- id: mature
  definition: >
    The benchmark is established and stable, with a settled result record and no expectation of
    structural change. This includes an instrument whose maintainer has ended its competition or
    frozen its leaderboard while it remains available and in use.
```

Which of `active` and `mature` applies is decided by the usual evidence: whether results are still
being produced against the instrument.

## Consequences

- **VoxSRC.** P1-S1-T08 re-runs the lifecycle field for VoxSRC. The expected reading is 02's own row:
  `active` or `mature` on the evidence, with activity `leaderboard-live-no-round`, because the
  permanent evaluation phase "Ends Never". voxsrc-retired-2023-003 is resolved by this clarification,
  not by a term.
- **HELM.** medhelm-007 and helm-capabilities-004 are confirmed rather than escaped. `mature` with
  activity `closed` is the intended reading of maintenance mode, so the escape-hatch records close.
- **HAL.** holistic-agent-leaderboard-hal-006 is not covered. A leaderboard paused by its maintainer
  "pending a successor" expects structural change, so it is not `mature`. It stays in the Stage 4
  revision list, which decides whether a `paused` activity state is needed.
- 02 §8 needs no edit. The clarification brings the term definitions into line with 02.

## Alternatives considered

- **Add `concluded` to lifecycle** (the classifier's proposal). Rejected, because it records the
  competition's state on the instrument's field, which is the `archived` conflation 02 §8 retired.
  Every concluded challenge with a live dataset would then read as finished instruments, and the
  coverage figures would drop them from "current" counts they belong in.
- **Treat a formal ending as `deprecated`.** Rejected. Deprecation is advice against use, and the
  VoxSRC maintainers say the data "was (and will continue to be) free and available".
- **Leave the definitions as they are.** Rejected. The classifier read them carefully and could not
  find the answer, which makes this a documentation defect even though 02 is internally consistent.

## Migration

None. The edit is definition prose only, and no entry's correct value changes. P1-S1-T08 re-reads
three lifecycle fields.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-voxsrc-retired-2023-003.yaml

Non-blocking, closed by the same clarification:
- taxonomy/_failures/2026-09-28-medhelm-007.yaml
- taxonomy/_failures/2026-09-28-helm-capabilities-004.yaml

Non-blocking, deliberately not covered (stays in Stage 4):
- taxonomy/_failures/2026-09-28-holistic-agent-leaderboard-hal-006.yaml
