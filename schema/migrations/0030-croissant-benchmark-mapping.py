"""Migration 0030: the croissant-benchmark extension's models move to schema/ and gain the material fields
(ADR-0030; P4-S6-T02).

A noop. schema/croissant_benchmark.py is a new module describing the JSON-LD documents the build emits, not an
entity: no record under data/ is read against it, no field is added to, renamed in or removed from any entity, and no
vocabulary changes. The plan is empty and always will be; the migration exists because the schema-change gate
(scripts/check_schema_change_gate.py, GOVERNANCE.md) asks every schema/*.py change for one under its ADR's number.
"""
KIND = 'noop'
SUMMARY = ('ADR-0030: the croissant-benchmark extension models move to schema/croissant_benchmark.py and map every '
           'material field; no record changes')


def plan(root: str) -> list:
    return []
