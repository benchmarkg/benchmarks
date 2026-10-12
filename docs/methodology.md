---
title: Methodology
description: How every figure the index publishes is counted and computed, and the ranking it refuses to compute.
---

<!-- docs/methodology.md -- P2-S3-T05, an agent draft for review (10 "Information architecture": /methodology/;
02 S11 rule 1; 12 S2-S3, S5.3). Rendered at /docs/methodology/. Every convention here is owned by the plan section
named beside it; this page states it once for readers and links the owner. -->

# Methodology

This page states how the index counts and computes what it publishes. Every published figure that rests on a
convention links back to the section here that defines it. A convention that a reader cannot find is one they
cannot dispute.

## What is counted: families

A **family** is a named benchmark identity: DCASE, BraTS, CASP, Matbench Discovery. Its editions, tasks,
tracks and splits are its **children**. **Every count the index publishes is a family count**, and the site
says so wherever a count appears. Counting children instead would multiply the totals several times over,
and again by the number of editions. ([02-taxonomy.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/02-taxonomy.md) §11 rule 5)

## The weighted benchmark count

A benchmark has exactly one primary domain and any number of secondary domains. Where the coverage view
needs one number per cell, it uses:

```
density = n_primary + 0.5 × n_secondary
```

Three constraints govern the formula:

- The figure is labelled the **weighted benchmark count**, never a benchmark count, because 2.5 benchmarks
  do not exist. It sets the colour scale of the coverage heatmap and nothing else.
- Beside it, the integer counts are published unweighted: "4 primary, 3 secondary". The integers are what
  a claim rests on.
- Whether a cell is occupied is decided by presence at any weight. A cell with one secondary-tagged
  benchmark and no primary one has benchmarks; it is not empty. The weight never decides a state, so no
  0.5 has to be rounded anywhere.

The 0.5 is a decision, published here and revisable by ADR. ([02-taxonomy.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/02-taxonomy.md) §11 rule 1)

## Subsets

A subset inherits every facet of its parent and may override any of them. The override **replaces** the
inherited value; it is never merged with it. The build writes each subset's fully resolved facets, so no
view walks a parent chain. A subset counts toward coverage only if it carries its own domain; otherwise the
family counts once, at its own primary domain. ([02-taxonomy.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/02-taxonomy.md) §11 rule 4)

## Tags are claims about sources

- **A capability is never inferred.** If neither the benchmark's own paper or site nor a cited critique says
  it tests a capability, the index does not say so. Under-tagging can be recovered; over-tagging silently
  fills a cell that should be empty, and empty cells are what the gap analysis is for.
- **No facet value is written by a model.** Machine suggestions arrive as suggestions and need a person to
  confirm them.

The definition, inclusion test, exclusion test and near misses of every term are on its own page under
[the taxonomy](/taxonomy/capability/knowledge-recall/), read from the governed files in `taxonomy/`.
([02-taxonomy.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/02-taxonomy.md) §11 rules 2 and 3)

## Coverage denominators

A coverage figure divides what the index has curated in a domain family by what the family is expected to
hold. The expected counts are stored in `taxonomy/domain-expectations.yaml`, with their provenance:

- **They are one researcher's estimate made on 2026-09-17, not a measurement.** They are versioned, and
  every domain reviewer who signs off is expected to revise their own domain's number.
- Six families were never sized. For those the denominator falls back to the family's seed target, and
  the cell is marked unsized rather than shown as a coverage fraction.
- A cell the taxonomy declares not applicable, because the question it asks is incoherent for that family,
  leaves both the numerator and the denominator of every coverage figure.

Each family's coverage is shown with its **curation confidence**: how much of the family has been curated,
how recently it was verified, and whether a domain reviewer has signed off. An empty cell in a thinly curated
family is our backlog, not a gap in the field, and is never published as one.
([12-analytics-and-trends.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/12-analytics-and-trends.md) §5.3, §5.4)

## The ranking the index does not compute

The index publishes no universal score, no cross-domain ranking and no composite index of its own. A single
latent ability is a defensible assumption inside a few dozen language-model benchmarks. It is not a
defensible assumption across protein folding, weather forecasting and robot manipulation. Composites that a
benchmark's own maintainers define inside their domain are recorded as that benchmark's declared metric,
and never extended across domains.
([12-analytics-and-trends.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/12-analytics-and-trends.md) §2)

The argument does not rest on our taste. When Hugging Face retired the Open LLM Leaderboard, after
evaluating over 13K models, it gave this reason:

> The leaderboard is slowly becoming obsolete; we feel it could encourage people to hill climb irrelevant
> directions in the field.

— Hugging Face, ["It's been a wild ride, folks :) (end of the Open LLM Leaderboard)"](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135),
13 March 2025 ([archived 2026-09-29](https://web.archive.org/web/20260929102854/https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135);
source record `src-hf-open-llm-leaderboard-end`).

## Headroom, the one cross-domain axis

One quantity does cross domains: **headroom consumed**. It is the position of the highest reported value
between a floor and a ceiling that are both defined inside the benchmark's own domain:

```
headroom_consumed = (sota - baseline) / (ceiling - baseline)
```

It says nothing about difficulty, importance or generality, only how much of a defined distance has been
travelled. It is stored unclamped, because a value above 1.0 means the reference has been surpassed, and
that is a fact worth showing. It is not computed where the benchmark has no known ceiling, no legitimate
aggregate, or an unbounded metric. In those cases the page says which reason applies rather than showing a
number. ([12-analytics-and-trends.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/12-analytics-and-trends.md) §3)

## Related

- [Provenance](/docs/provenance/): where every value comes from, and how a reader checks it.
- [Comparability](/docs/comparability/): when two numbers may be compared, and what the index does when
  they may not.
- [The data contract](/api/): the artifacts and their stability guarantees.
