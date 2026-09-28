# ADR-0015 -- Add the subdomain `general-intelligence/multi-subject-knowledge-exams`

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0 (applied by P1-S1-T07)
- **Facet:** domain
- **Change type:** add (03 §8.1: MINOR, no migration, two reviewers)
- **Supersedes:** --
- **Superseded by:** --

## Context

MMLU-Pro and Humanity's Last Exam have no legal primary domain. Both claim breadth, closed-ended
questions across many academic subjects, and that places them in `general-intelligence`:
- The family's inclusion test reads "the benchmark's own claim is coverage of many fields".
- domains.yaml's own example says of MMLU-Pro: "Breadth across fourteen subjects is the entire
  claim".
- 02 §3 names both, with GPQA, among the twelve field-defining families of the row.

No subdomain of the family describes them:
- `human-comparison-batteries` needs measured human performance, and neither reports any.
- `agi-composite-suites` needs many heterogeneous tasks aggregated into one score, and each of them
  is one task format across subjects.
- `abstraction-generalization`, `novel-task-acquisition`, `meta-learning`, `open-ended-discovery`
  and `compositional-generalization` are about other things.

A bare family is never assignable (02 §3), so both abstain with a blocking `missing-term`
(mmlu-pro-001, humanity-s-last-exam-001), and both propose this subdomain.

GPQA Diamond is the same case, resolved differently. It was forced into `human-comparison-batteries`
as an escape hatch (gpqa-diamond-001, non-blocking), only because it reports expert and non-expert
accuracy. In GPQA that measurement exists to certify difficulty, not to be the benchmark's purpose.
The row that 02 §3 targets for a complete sweep would therefore split its three most-cited members
across two subdomains, one of them by accident.

## Decision

Add one subdomain:

```yaml
- id: general-intelligence/multi-subject-knowledge-exams
  label: Multi-subject knowledge exams
  parent: general-intelligence
  status: proposed
  introduced_in: 1.0.0
  source: own
  definition: >
    Closed-ended question sets drawn from exams, textbooks or expert-written questions across many
    academic subjects, scored on the answers alone.
  inclusion_test: >
    Tag this as PRIMARY if the benchmark's own claim is breadth of subject knowledge or expertise,
    its items are closed-ended questions, and no single subject holds most of them.
  exclusion_test: >
    Do NOT tag this if one subject holds most of the items (that subject's family is primary), if
    measured human performance is the benchmark's purpose (`human-comparison-batteries`), or if the
    headline number aggregates heterogeneous task formats (`agi-composite-suites`).
  examples:
    - ref: mmlu-pro
      qualifies: true
      why: Ten-option questions across 14 subjects; breadth is the whole claim.
    - ref: humanity-s-last-exam
      qualifies: true
      why: Closed-ended questions across over a hundred subjects, with no human solve rate.
    - ref: helm-capabilities
      qualifies: false
      why: >
        NEAR MISS. Includes MMLU-Pro and GPQA, but aggregates five heterogeneous scenarios into
        one mean; that is `agi-composite-suites`.
```

The leaf `multi-subject-knowledge-exams` equals no capability id, so it is not a homograph (checks
9d and 9e are unaffected).

## Consequences

- P1-S1-T08 re-runs `domain.primary` for MMLU-Pro and HLE, which resolves the two blocking records.
- GPQA Diamond is re-adjudicated against the new term. Its escape hatch is expected to move here,
  with `human-comparison-batteries` rejected because the human measurement certifies difficulty.
  gpqa-diamond-001 is resolved either way.
- MMMU-Pro, a multimodal exam across many subjects, is re-read. Its boundary record, mmmu-pro-001
  (`multimodal/visual-qa` against a breadth claim), gains a third candidate. The rule that decides
  it is the family tests (02 §3): whether the scored quantity is the relation between modalities.
  A subject-count rule does not decide it.
- 02 §11 rule 4 is unaffected. An MMLU subject still inherits this primary and may override it with
  its own subject's domain, which is what lets college chemistry count as chemistry coverage.

## Alternatives considered

- **File each exam under its majority subject.** Rejected. MMLU-Pro and HLE have no majority
  subject, and a plurality rule would move a benchmark whenever its maintainers add questions.
- **Widen `human-comparison-batteries` to all broad batteries.** Rejected. It would erase the
  distinction the term exists for: whether a human population is measured on the same items.
- **`language/understanding`, where the corpus files MMLU-Pro.** Rejected by that subdomain's own
  test: it needs a supplied passage, and a closed-book exam supplies none.

## Migration

None, pre-freeze. P1-S1-T08 re-classifies `domain.primary` for the entries above.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-mmlu-pro-001.yaml
- taxonomy/_failures/2026-09-28-humanity-s-last-exam-001.yaml

Non-blocking, same gap:
- taxonomy/_failures/2026-09-28-gpqa-diamond-001.yaml
