# ADR-0008 -- A rubric-graded Metric records its rubric's structure as data

- **Status:** Proposed
- **Date:** 2026-09-27
- **Taxonomy version:** not affected
- **Facet:** none. A schema change to the Metric entity (04 §6)
- **Change type:** schema, additive (one optional block; no existing record changes)
- **Supersedes:** --
- **Superseded by:** --

## Context

`rubric-graded` (02 §5) is an evaluation method whose score aggregates a structured rubric, and 02
calls PaperBench's "~8,316-leaf hierarchical rubric" out as the case that forced the term: "Record
the grader separately -- it may be human or model". What the grader applies is a rubric with a
shape -- how many criteria, whether they nest, how a leaf is scored and a parent combined -- and that
shape decides what a score means. PaperBench's replication score is a weighted average over a tree
of binary leaves, 8,316 of them across 20 papers, and a score of 20% is 20% of that tree.

A Metric (04 §6) had nowhere to say so. `aggregation` is free text, so the leaf count, the tree
structure and the leaf types could only be prose, and P0-S8-T07's step "Record the hierarchical
rubric as a Metric with its leaf count, not as a free-text note" could not be met.

## Decision

**`Metric.rubric`: an optional block describing the rubric a rubric-graded metric aggregates.**

    rubric:
      structure: tree                          # tree | flat
      rubric_count: 20                         # one rubric per item, when there are several
      leaf_count: 8316                         # over the whole benchmark version
      node_count: 11218                        # leaves plus inner nodes; a flat rubric has none
      leaf_scoring: binary                     # binary | graded
      node_aggregation: weighted-mean-of-children   # | mean-of-children | sum-of-children
      leaf_types:                              # optional; sums to leaf_count
        - {type: code-development, count: 3674}
        - {type: execution, count: 4076}
        - {type: result-match, count: 566}

Rules: `node_count` is at least `leaf_count`; a flat rubric has no inner nodes and no
`node_aggregation`; a tree states its `node_aggregation`; leaf types are listed once each and sum
to `leaf_count`.

The grader is **not** in the block. Who applied the rubric -- a judge model and its version, or a
person -- is a condition of a run, and 04 §8 already holds it (`EvalConditions.judge_model`,
`judge_model_version`, `grading_rubric_ref`). Putting it on the Metric would make every change of
judge a new metric.

Alternatives considered: the count in the benchmark's `data.size` (structured, but it describes the
item set, not how a score is built, and it cannot carry the tree or the leaf types); a leaf count as
a single integer on Metric (loses the structure that makes the count meaningful); a separate Rubric
entity (the right shape once rubrics themselves are published and versioned per item, which no
record needs yet).

## Consequences

- Additive: the block is optional and defaults to null, so no existing record changes and the
  migration plans no rows (schema/migrations/0008-metric-rubric.py).
- schema/generated/metric.schema.json and site/src/types/metric.d.ts are regenerated.
- First user: paperbench-replication-score (P0-S8-T07). HealthBench's 48,562 criteria are the next
  candidate; whether its per-conversation rubrics fit `rubric_count` is its curator's check.
