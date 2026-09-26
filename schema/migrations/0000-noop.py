"""Migration 0000: the no-op fixture (P0-S5-T07).

It changes nothing and has no ADR, so `bench migrate 0000 --dry-run` prints a zero-row plan and
`bench migrate 0000 --apply` is refused. It is the convention's worked example: copy it to
<nnnn>-<slug>.py beside adr/<nnnn>-<slug>.md, set KIND and SUMMARY, and return the rows from `plan`.
"""
KIND = 'noop'
SUMMARY = 'changes nothing; the fixture for the migration convention'


def plan(root: str) -> list:
    return []
