"""Migration 0007: `Leaderboard.conditions` (ADR-0007; P0-S8-T03).

Additive: a new optional field, null by default. No existing Leaderboard record carries it and none
has to, so the plan changes nothing; the migration exists because the schema-change gate asks every
schema change for one (GOVERNANCE.md).
"""
KIND = 'field'
SUMMARY = 'adds optional Leaderboard.conditions, a reference to the EvalConditions holding a board\'s rules'


def plan(root: str) -> list:
    return []
