"""Taxonomy and schema migrations: schema/migrations/<nnnn>-<slug>.py (P0-S5-T07; 03 S9, 05 S3).

    bench migrate <nnnn> [--dry-run|--apply]

03 S9: "Every vocabulary-changing ADR ships a migration script ... and the migration lands in the
same commit as the taxonomy change." The number is the ADR's: migration 0027 is adr/0027-*.md's, and
`--apply` refuses to run without that file (tools/migrate.py).

The convention. A migration is a module named `<nnnn>-<slug>.py` (05 S2's spelling; the hyphen means
it is loaded by path, never imported), declaring:

    KIND = 'merge'            # one of KINDS
    SUMMARY = 'one line: what changes and why'
    def plan(root: str) -> list[Row]: ...

`plan` reads the corpus and returns the rows it would change; it never writes. tools/migrate.py
prints the plan (`--dry-run`, the output attached to the ADR's PR) or writes it (`--apply`) through
the project's one YAML emitter, so comments survive and the file stays what `bench fmt` writes.
Keeping the writing out of the migration is what lets the dry run be exactly the apply.

Splits (03 S9.1): "A split cannot be automated ... So a split migration writes a sentinel." A
`KIND = 'split'` plan may write nothing but `sentinel(old)` in place of the old term -- tools/migrate.py
refuses any other value, so no split can guess -- and it never applies unattended.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from typing import Any, Iterator

KINDS = ('noop', 'merge', 'rename', 'deprecate', 'retire', 'split', 'field')
SENTINEL_PREFIX = '__NEEDS_REVIEW__:'
HERE = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class Row:
    """One value a migration changes: in `path` (root-relative), at `at` (keys and list indices)."""
    path: str
    at: tuple
    old: Any
    new: Any

    def where(self) -> str:
        out = ''
        for p in self.at:
            out += '[%d]' % p if isinstance(p, int) else ('.' if out else '') + str(p)
        return out


def sentinel(term: str) -> str:
    """03 S9.1's publication-blocking placeholder for a term a split retired."""
    return SENTINEL_PREFIX + term


def entity_files(root: str, kind: str = 'benchmarks') -> Iterator[tuple[str, Any]]:
    """(root-relative path, parsed YAML) for every file under data/<kind>/, in path order."""
    from schema.taxonomy import read_yaml
    for full in sorted(glob.glob(os.path.join(root, 'data', kind, '**', '*.yaml'), recursive=True)):
        yield os.path.relpath(full, root).replace(os.sep, '/'), read_yaml(full)


def term_rows(root: str, old: str, new: str, kind: str = 'benchmarks') -> list[Row]:
    """A row for every whole-string value equal to `old` in data/<kind>/: the shape of a merge or a
    rename, where every occurrence of B becomes A (03 S9.1)."""
    rows = []

    def walk(x, at, rel):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, at + (k,), rel)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, at + (i,), rel)
        elif x == old:
            rows.append(Row(rel, at, old, new))

    for rel, doc in entity_files(root, kind):
        walk(doc, (), rel)
    return rows
