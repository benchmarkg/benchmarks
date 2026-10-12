---
title: Comparability
description: When two reported numbers may be compared, how the index decides, and what it shows when they may not.
---

<!-- docs/comparability.md -- P2-S3-T05, an agent draft for review (04 S8; 12 S4; 09 S11.3). Rendered at
/docs/comparability/. The arithmetic is tools/build/comparability.py's; the per-benchmark field sets are
taxonomy/comparability-profiles.yaml's. -->

# Comparability

Two numbers on the same benchmark are often not the same measurement. A different number of examples in the
prompt, a different agent scaffold, best-of-four sampling instead of one attempt, or a different grading model
can each move a score by more than the gap between two systems. The index records the conditions behind every
result, and compares two results only when their conditions agree.

## Material conditions

A condition is **material** when changing it changes what the number measures. Examples:

- the number of shots, and whether chain of thought was used;
- the reasoning effort and the tools allowed;
- the scaffold and the harness;
- the selection strategy and the number of samples;
- the retries allowed;
- the judge model, for a model-graded benchmark;
- the simulator version, for a robotics benchmark;
- the subset used.

Other conditions are recorded but are not material: temperature, wall-clock time and cost, for a pure-accuracy
metric.

The material set is **specific to each benchmark**. The number of shots means nothing for a robotics
simulation, and a simulator version means nothing for a multiple-choice test. So there is no fixed "number of
material fields". Each benchmark's set comes from a profile chosen by its evaluation method and the subjects it
is designed for (`taxonomy/comparability-profiles.yaml`). A benchmark may add fields to its set, or waive them
with a stated reason. Waivers are visible, because quietly waiving inconvenient fields until everything compares
is the failure being guarded against.
([04-data-model.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/04-data-model.md) §8)

## The comparability key

Each claim gets a key, a hash over:

- the benchmark version, the metric and the subset;
- each material condition in turn, with an unknown condition recorded as unknown rather than skipped.

```
comparability_key      = sha256([version, metric, subset, condition_1 or "?", ...])[:16]
key_unknown_count      = the number of "?" in it
condition_completeness = the stated share of the material fields, weighted
```

The weighting counts 2.0 for the judge model on a model-graded benchmark, and 2.0 for the scaffold when the
subject under test is an agent scaffold. Those are the fields whose absence does the most damage. Every other
field counts 1.0.

Condition values are written one way: a temperature of 1 and 1.0 is one condition, and the order of the tools
allowed is not a condition.

## What the index shows

| Two claims | What the index does |
| --- | --- |
| Same key, no unknown conditions on either | Comparable. Plotted together. |
| Same key, unknown conditions on one or both | Possibly comparable. Plotted together under a banner naming which conditions are unknown on which claim, because two claims that are both silent about a condition agree only in their silence. |
| Different keys | **Not compared.** The index shows which conditions differ instead of a chart. |

The refusal in the last row is the point. A difference between two results is never explained in prose by a
person. The two claims are recorded, and the difference in their conditions is computed and stated:

> One lab reports 0.712 (self-reported). The benchmark's maintainers report 0.648 under re-run conditions
> (independent reproduction). Material conditions differ in: `n_samples`, `selection_strategy`, `retries_allowed`.

The first two sentences are data. The third is computed from the two condition records. This is how the index
can be useful about disagreements without taking sides in them.
([04-data-model.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/04-data-model.md) §8;
[09-design-system.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/09-design-system.md) §11.3)

## Numbers that are never compared

Some numbers cannot be compared at all, and a warning banner is not enough. These are refused, not annotated:

- **An Elo rating across rating-pool snapshots.** A rating changes when a different model joins the pool, with
  no change to the model rated, so the pool and its snapshot date are part of the stored result.
- **`pass^k` against a mean success rate.** `pass^k` is the fraction of tasks solved in all k trials, and
  averaging destroys exactly what it measures.
- **Human-assisted against automated entries.** CASP ranks human-expert groups separately from automated
  servers.
- **Results under different training-data eligibility tiers.** Matbench Discovery groups models by what they
  were allowed to train on.
- **Scores on either side of a version marked breaking.** That marker is what lets a comparison refuse to put
  the two on one axis.

A score that resolves later, such as a forecast, is marked pending rather than compared before it resolves.
([12-analytics-and-trends.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/12-analytics-and-trends.md) §10 rule 4;
[04-data-model.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/04-data-model.md) §6)

## Related

- [Methodology](/docs/methodology/): how counts and coverage are computed.
- [Provenance](/docs/provenance/): where each condition and value comes from.
