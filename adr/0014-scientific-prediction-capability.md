# ADR-0014 -- Add the capability `scientific-prediction`

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** capability
- **Change type:** add (03 §8.1: MINOR, no migration, two reviewers)
- **Supersedes:** --
- **Superseded by:** --
- **Applied:** taxonomy 0.9.0, P1-S1-T07. P1-S1-T08 re-classifies the fields it touches

## Context

The Stage 3 pass (P1-S1-T03 to T05) found that the capability facet has no term for the competence
that most science benchmarks score: predicting a property, structure or state of a physical,
chemical, biological or Earth system, and being scored against what an experiment, an observation or
a reference computation says.

- **Where it blocks.** Six entries abstain on capability with a blocking `missing-term`, because
  nothing else in their sources can be tagged. They span biology, chemistry, physics and agriculture:
  - CAFA (protein function from sequence);
  - the CASP16 nucleic-acid assessment (RNA and DNA 3D structure);
  - Open Problems in Single-Cell Analysis (label projection, modality prediction, denoising);
  - CY-Bench (crop yield from weather and soil);
  - The Well (the next state of a simulated physical field);
  - USPTO-50k (reactants from a product).
- **Where it doesn't block.** Eight more entries log the same gap, `proposed_term:
  scientific-property-prediction`, as non-blocking only because they carry a second capability,
  usually `distribution-shift-generalization` from an out-of-distribution split:
  - CASP17, ProteinGym, Runs N' Poses and PoseBusters;
  - OMol25 and Open Catalyst;
  - WeatherBench 2 and ChaosBench.

  Their headline competence is still untagged. So 14 of the 90 corpus entries are missing their
  primary capability, and all 14 sit in the biology, chemistry, physics and earth-climate rows:
  more than half of those rows' 27 entries.

The existing terms were each tried and rejected on their own tests:
- `knowledge-recall`: the answer is not held knowledge.
- `probabilistic-forecasting`: its exclusion covers answers that already exist but are withheld.
- `spatial-reasoning`: it excludes reconstruction accuracy.
- `generation-fidelity`: tagging it would be inferred from the metric, against 02 §11 rule 2, and
  would make every regression benchmark `generation-fidelity`.

The cost of the gap is concrete. The coverage matrix crosses domain with capability-group, so the
science rows show empty or near-empty capability columns for reasons that have nothing to do with the
field. That is the over-read failure 03 §7.1 warns against, but in the other direction: a gap the
product would publish that is an artefact of the vocabulary.

## Decision

Add one capability term:

```yaml
- id: scientific-prediction
  label: Scientific prediction
  status: active
  introduced_in: 1.0.0
  definition: >
    Predicting a property, structure or state of a physical, chemical, biological or Earth system
    from its description or from measurements of it.
  inclusion_test: >
    Tag this if the benchmark's own claim is that systems predict such a quantity, structure or
    state, and the score compares the prediction with experimental measurement, observation or a
    reference computation.
  exclusion_test: >
    Do NOT tag this if the answer is recalled rather than predicted (`knowledge-recall`), if the
    truth does not yet exist and probabilities are scored on resolution (`probabilistic-forecasting`),
    or if the benchmark claims a reasoning competence and scientific content is only its subject
    matter, as in exam-style question answering.
  examples:
    - ref: cafa
      qualifies: true
      why: Protein function predicted from sequence and scored against annotations that appear later.
    - ref: the-well
      qualifies: true
      why: The next state of a simulated physical field, scored against the simulator.
    - ref: gpqa-diamond
      qualifies: false
      why: >
        NEAR MISS. Science questions, but the claim is expert-level reasoning over them, answered
        by selection; no system predicts a property of a physical system.
    - ref: forecastbench
      qualifies: false
      why: NEAR MISS. Predictions of events that have not happened, scored on resolution; that is
        `probabilistic-forecasting`.
  see_also: [probabilistic-forecasting, calibration-uncertainty, knowledge-recall]
```

The term joins the capability group `causal-and-experimental-inference`, alongside
`hypothesis-generation` and `experimental-design`, the other capabilities of doing science.

The term is deliberately broad. Structure, property and dynamics are distinguished by the domain
facet: `biology-genetics/protein-structure-prediction`, `chemistry-materials/molecular-property-prediction`
and `earth-climate/weather-forecasting` already say *what* is predicted. A capability that repeated
that split would duplicate the domain axis in the capability axis, and the coverage matrix would
count each science benchmark twice.

## Consequences

- P1-S1-T08 re-runs the capability field for the 14 entries above. The six blocking abstentions
  become assignments, and the eight non-blocking records are resolved.
- The rest of the science rows are re-read for the new term, because under-tagging is the safe
  error and the term did not exist when they were classified: BEND, the Virtual Cell Challenge,
  Matbench Discovery, Brain-Score, FAIR Universe, the Fusion Equilibrium Challenge and SRBench.
- Open Problems is the weakest fit. Denoising and integration are analysis steps, not predictions of
  a measured quantity. If the re-run does not tag the term there, it logs a new failure against the
  record rather than stretching the definition.
- The `causal-and-experimental-inference` group gains a member. The coarse coverage grid changes for
  the science rows, which have had no v1.0.0 figure published yet.

## Alternatives considered

- **Three terms: structure prediction, property prediction and dynamics forecasting.** Rejected. The
  domain facet carries that distinction already (see Decision). Splitting later is still possible
  (03 §9.1), and the failure log will show whether a split is needed.
- **A `not-a-cognitive-capability` marker in place of a term.** Rejected. 02 §11 rule 6 reads an
  empty capability as "not yet tagged", and a marker would leave the science rows of the matrix
  empty by construction, which is the artefact this ADR exists to remove.
- **Redefine `generation-fidelity` to cover predicted fields and structures.** Rejected. Its
  inclusion test is met by any distance to a target, so widening it would tag every regression
  benchmark and corrupt the gap analysis (02 §11 rule 2).

## Migration

None. Pre-freeze, no `data/` record carries a capability yet. P1-S1-T08 re-classifies the affected
field over the corpus.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-cafa-001.yaml
- taxonomy/_failures/2026-09-28-casp16-na-rna-puzzles-joint-assessment-001.yaml
- taxonomy/_failures/2026-09-28-cy-bench-001.yaml
- taxonomy/_failures/2026-09-28-open-problems-in-single-cell-analysis-002.yaml
- taxonomy/_failures/2026-09-28-the-well-002.yaml
- taxonomy/_failures/2026-09-28-uspto-50k-002.yaml

Non-blocking, same gap:
- taxonomy/_failures/2026-09-28-casp17-003.yaml
- taxonomy/_failures/2026-09-28-chaosbench-002.yaml
- taxonomy/_failures/2026-09-28-omol25-001.yaml
- taxonomy/_failures/2026-09-28-open-catalyst-oc20-oc22-001.yaml
- taxonomy/_failures/2026-09-28-posebusters-002.yaml
- taxonomy/_failures/2026-09-28-proteingym-001.yaml
- taxonomy/_failures/2026-09-28-runs-n-poses-002.yaml
- taxonomy/_failures/2026-09-28-weatherbench-2-001.yaml
