# ADR-0017 -- Three corpus entries are outside the classification scope, and no term is added for them

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** none added or changed. A scope ruling that closes failures in capability,
  designed_for_subjects and domain
- **Change type:** scope ruling (no row of 03 §8.1 applies; no term changes)
- **Supersedes:** --
- **Superseded by:** --

## Context

Three stress-corpus entries are not benchmarks of AI systems, and 02 already says so. The Stage 3
pass classified them as the corpus defines them (02 §11 rule 5), and their failures are the
vocabulary correctly refusing them. None of those failures is a vocabulary gap.

- **Metriq / QED-C** scores quantum computers: gate error, throughput and circuit fidelity per device
  and date.
  - 02 §6 lists `hardware-device` as a subject term that was deliberately excluded.
  - 02 §13 records the boundary: "Metriq, the QED-C application-oriented quantum benchmarks, MLPerf
    system benchmarks and SPEC evaluate devices and systems, not models ... revisit by ADR if a
    genuine cross-over case appears."
  - 03 §3.2 put the entry in the physics row, and its two blocking failures show the boundary held:
    no capability fits (metriq-qed-c-001) and no subject fits (metriq-qed-c-002). The classifier said
    so in both records: "This may be a corpus scope defect rather than a vocabulary gap."
- **Inspect Evals** is a library of about 170 evaluation implementations. It spans every family and
  publishes no scores.
  - 02 §11 rule 10 makes it an interop identifier on other benchmarks (`inspect_evals_id`, with
    `inspect_evals_available` derived from it).
  - 03 §2 uses its categories as a reference vocabulary and a sanity check.
  - It is the front door to a harness, not a benchmark, so its missing primary domain
    (inspect-evals-001) is not a missing subdomain.
- **Open X-Embodiment** is a pooled training dataset. 02 §13 names it: "it is a dataset, not a
  benchmark ... It enters the index as a linked `Resource`, referenced by the benchmarks that use it,
  never as a benchmark with a leaderboard." Its ten non-blocking failures are that fact surfacing
  field by field: no evaluation set, no lifecycle, no submission channel.

## Decision

**No term is added, and the three entries are ruled out of classification scope.** The rulings
already in 02 stand: no `hardware-device` subject, no domain for a harness library, and training
datasets entered as Resources.

1. The corpus keeps all three entries. They were chosen to stress the boundary, and they did.
   P1-S1-T07 adds a corpus flag `out-of-scope: ADR-0017` with the reason for each.
2. Their classification records and failure records stay in the repository, because the failure
   log is permanent (03 §3.3). Every one of their failures is routed to this ADR, and none enters
   the Stage 4 revision list.
3. None of the three is upgraded into a `data/` benchmark entry when the 90 records become the
   first entries (03 §3). Open X-Embodiment enters as a `Resource`. Inspect Evals enters as the
   `inspect_evals_id` values on the benchmarks it implements. Metriq does not enter.
4. The taxonomy examples that cite these entries as qualifying for a term are removed or turned
   into near misses in P1-S1-T07, because an example must be a benchmark the term can be tagged on:
   - capabilities.yaml cites `inspect-evals` for four capabilities (inspect-evals-002);
   - capabilities.yaml cites `open-x-embodiment` for `continual-learning` (open-x-embodiment-002).

## Consequences

- The five blocking and non-blocking records of Metriq and Inspect Evals, and the ten of Open
  X-Embodiment, are closed by this ruling, not by a vocabulary change.
- The seed-entry count that 03 §3 draws from the corpus falls from 90 to 87.
- The physics row keeps five in-scope entries. The stress corpus is a sample for breaking the
  vocabulary, not a coverage allocation, so no replacement is drawn.
- **Cross-over cases stay in scope.** A quantum machine-learning *algorithm* benchmark, with a
  model-shaped subject, is `physics/quantum-systems`, as 02 §6 says. A benchmark implemented in
  Inspect Evals is classified as that benchmark.

## Alternatives considered

- **Add `hardware-device` to subjects and a hardware capability.** Rejected, for the reason 02 §13
  gives: it would roughly double the surface area and import another community's vocabulary. Nothing
  in the pass is a genuine cross-over case.
- **Add an `evaluation-collection` domain or entity for harness libraries** (inspect-evals-001's
  proposal). Deferred. 04 has no Collection entity, and the interop field already carries the link.
  If lm-evaluation-harness, OpenCompass or HELM's scenario library need to be listed as objects,
  that is a data-model ADR, not a taxonomy term.
- **Replace the three entries with in-scope benchmarks and classify those.** Rejected. It would cost
  a classification pass for no new stress, and the corpus would lose the evidence that the boundary
  was tested.

## Migration

None. P1-S1-T07 flags the corpus entries and edits the examples, and no facet value changes.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-metriq-qed-c-001.yaml
- taxonomy/_failures/2026-09-28-metriq-qed-c-002.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-001.yaml

Non-blocking, closed by the same ruling:
- taxonomy/_failures/2026-09-28-metriq-qed-c-003.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-002.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-003.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-004.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-005.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-006.yaml
- taxonomy/_failures/2026-09-28-inspect-evals-007.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-001.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-002.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-003.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-004.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-005.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-006.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-007.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-008.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-009.yaml
- taxonomy/_failures/2026-09-28-open-x-embodiment-010.yaml
