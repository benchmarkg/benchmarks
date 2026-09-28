# ADR-0021 -- `medicine-health/clinical-dialogue` covers a scored reply within a health conversation

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.9.0 -> 0.9.1 (not yet applied)
- **Facet:** domain
- **Change type:** redefine a subdomain (03 §8.1: MINOR; no migration, since no `data/` record uses
  it; two reviewers)
- **Supersedes:** --
- **Superseded by:** --

## Context

The P1-S1-T08 re-run removed every escape hatch. HealthBench's primary domain had been one:
`medicine-health/clinical-dialogue`, forced (healthbench-001). Under 0.9.0 the field has no legal
value (healthbench-012):

- HealthBench scores one open-ended reply: "Given a conversation, the task for an LLM is to respond to
  the last user message". Physician-written rubrics grade the reply across seven themes.
- `clinical-dialogue` is defined as "Conducting a multi-turn clinical conversation, scored on the
  conduct of the exchange rather than on a single reply", which excludes exactly that.
- `clinical-qa` needs a determinate correct answer, and HealthBench's are open-ended.
- `diagnosis-triage` covers only the emergency-referral theme, and `medical-safety` only half the
  claim ("performance and safety").
- `clinical-task-suites` (ADR-0016) names HealthBench as its near miss, because every item is the
  same task.

The family is not in doubt, and ADR-0020 deferred the proposed `medicine-health/health-advice-quality`
until a second entry showed whether `clinical-dialogue` should cover a single scored reply. The
re-run supplies the answer that deferral was waiting for: without an escape hatch, the benchmark has no
primary. That is blocking under the Stage 3 rule, as mmlu-pro-001 and humanity-s-last-exam-001 were.
The shape recurs for LLM health-advice benchmarks, and MedHELM's Patient Communication and Education
category is one more.

## Decision

Widen `medicine-health/clinical-dialogue` rather than add a term. The distinction the current
definition draws, whole exchange against single reply, is a property of the scoring protocol, and
`evaluation_method` (`rubric-graded`, `model-graded-judge`, `human-expert-eval`) already carries it.
The domain question is only whether the benchmark's subject is a clinical or health conversation.

```yaml
- id: medicine-health/clinical-dialogue
  definition: >
    Responding within a clinical or health conversation with a patient, carer or clinician, scored
    on the replies or on the exchange as a whole.
  inclusion_test: >
    Tag this as PRIMARY if the system's output is a turn in a health conversation, whether it is the
    last reply to a given history or every turn of a live exchange, and the score concerns what was
    said to the other party.
  exclusion_test: >
    Do NOT tag this if the item has one determinate correct answer (`clinical-qa`), if the output is
    a clinical document such as a note or a report (`radiology-report-generation`, or the note
    generation tasks of a suite), or if the conversation drives actions in a health record
    (`clinical-agent-workflows`).
  examples:
    - ref: healthbench
      qualifies: true
      why: The last reply to a health conversation, graded by physician rubrics.
    - ref: medhelm
      qualifies: false
      why: >
        NEAR MISS. Patient messaging is one of its categories, but the suite spans five, which
        is `clinical-task-suites`.
```

## Consequences

- **Until this ADR is accepted and applied,** HealthBench's primary stays null and healthbench-012
  stays open and blocking. P1-S1-T08's DONE WHEN clause "the re-run adds no blocking record" is
  therefore not met, by this one record, and the task reports it rather than hiding it.
- **Once applied (0.9.1),** a re-run of HealthBench's `domain.primary` resolves healthbench-012, and
  `health-advice-quality` is closed as merged into this redefinition.
- **No other corpus record moves.** No entry currently carries `clinical-dialogue`.

## Alternatives considered

- **Add `medicine-health/health-advice-quality`** (the classifier's proposal). Rejected. It would sit
  beside `clinical-dialogue` and differ only in whether one turn or several is scored. The coverage
  matrix would then split one field of study, conversational health AI, into two thin rows.
- **Log it as non-blocking to meet the DONE WHEN.** Rejected. A benchmark with no legal primary
  cannot be placed or browsed, and the Stage 3 rule has treated that as blocking in every other case.

## Migration

None. No `data/` record uses the term.

## Evidence

Blocking:
- taxonomy/_failures/2026-09-28-healthbench-012.yaml
