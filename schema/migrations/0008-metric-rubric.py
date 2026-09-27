"""Migration 0008: `Metric.rubric` (ADR-0008; P0-S8-T07).

Additive: a new optional block, null by default. No existing Metric record carries it and none has
to, so the plan changes nothing; the migration exists because the schema-change gate asks every
schema change for one (GOVERNANCE.md).
"""
KIND = 'field'
SUMMARY = 'adds optional Metric.rubric, the structure of the rubric a rubric-graded metric aggregates'


def plan(root: str) -> list:
    return []
