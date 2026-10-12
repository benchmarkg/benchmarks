---
title: Provenance
description: Where every value in the index comes from, how it is checked, and how a reader checks it again.
---

<!-- docs/provenance.md -- P2-S3-T05, an agent draft for review (05 S4; 04 S9; 09 S11.2; 10 V6 "The provenance
drill-down"). Rendered at /docs/provenance/. -->

# Provenance

## No field without a source

Every entry cites at least one primary source, and every result claim cites exactly one. Nobody fills a
field from memory or by inference. A guessed number in a data file looks exactly like a correct one, so an
index that might be guessing is worse than no index: a reader cannot tell which fields to check.

`null` is a valid answer, and always better than a plausible number. A missing value renders as one of four
phrases, never as a blank, a dash or a zero:

| Phrase | Means |
| --- | --- |
| **not reported** | The source did not state it |
| **not recorded** | The source may state it; the index has not curated it |
| **not applicable** | The field is meaningless for this entity |
| **unknown** | A condition that makes two results comparable was not stated (the narrowest of the four) |

([05-repository-and-workflow.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/05-repository-and-workflow.md) §4;
[09-design-system.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/09-design-system.md) §11.2)

## Sources are records

A source is a record of its own, with:

- its URL;
- when it was read;
- an archived copy and the date of that capture;
- the hash of the text that was read;
- its licence class.

Every value taken from it carries a **verbatim quote**. Each quote is checked against an extract of the
source's text. A quote that is not in the extract fails validation, so a value cannot quietly drift from what
its source says.

A source has no page of its own. It renders as an anchored block on every page that cites it, and its archive
link is its durable identity: what a citation resolves to if the original moves.
([04-data-model.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/04-data-model.md) §9)

## Who checked it

AI-assisted drafting is how a small team covers several thousand benchmarks. It is marked so that a machine's
draft is never mistaken for a person's check. Every entry carries a `verification_status`:

| Status | Meaning | Published? |
| --- | --- | --- |
| `ai-drafted-unverified` | A model wrote it from cited sources; no person has opened those sources | **No, never** |
| `machine-ingested` | An ingestion adapter wrote it from a structured source under a known licence | Yes, marked |
| `curator-reviewed` | A person read it and it is coherent; not every field re-checked against its source | Yes, marked |
| `primary-source-verified` | A person opened each source and confirmed each factual field against it | Yes |
| `expert-reviewed` | A domain expert outside the core team reviewed it | Yes, marked |
| `maintainer-confirmed` | The benchmark's own maintainers signed off | Yes, marked |

Drafts are not greyed out or hidden behind a toggle. They are absent from the published build, and a check on
every change enforces it.
([05-repository-and-workflow.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/05-repository-and-workflow.md) §4)

A result claim carries a second, separate ladder: how the number itself was verified, from `self-reported`
through `maintainer-verified` and `independent-reproduction` to `sandboxed-rerun`. The badge beside every
number names its rung.

## Reading the provenance of a number

Every number on a benchmark's page sits in a disclosure. Its summary is the value, its verification badge and
how many of the benchmark's material conditions it states. Opening it shows:

- the source, when it was read, and its archive copy;
- the date reported and who reported it;
- its verification;
- its comparability key and how many other claims share it;
- any artifact (transcripts, logs);
- for a machine-ingested row, the snapshot of the upstream row it came from;
- every material condition, and the ones that are unknown, listed together as a set.

This works without JavaScript, because it is the one interaction that turns the transparency claim into
something a reader can check.
([10-visualization.md](https://github.com/benchmarkg/benchmarks/blob/main/_plan/10-visualization.md) V6)

## Citing the index

The live site is always the latest commit. To cite an entry, cite the YAML file at a commit, or the release and
its DOI. Every entry page has a citation block with both. An artifact URL is a cache key, not a citation.

## Corrections

Every entry page has a "Suggest a correction" link, at the top and beside each field. It opens a form that
already names the entry and the field. A correction is a commit with a rationale, never a quiet edit, and it is
listed with the date, what the entry said before, what it says now, and who reported it.
