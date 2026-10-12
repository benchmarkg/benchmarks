#!/usr/bin/env python3
"""The ADR-plus-migration gate on schema and taxonomy diffs (P0-S6-T07; 05 S5, 05 S9, GOVERNANCE.md, 03 S9).

GOVERNANCE.md: "CI rejects a schema or taxonomy diff that lacks its ADR or its migration script". 05 S5's
review matrix asks a schema change for "2 + ADR + migration script + full revalidation". This is the
mechanical half: a diff that changes the schema or a vocabulary must also add an ADR and a migration
under one number, adr/NNNN-*.md and schema/migrations/NNNN-*.py (03 S9: the migration's number is its
ADR's).

What counts as a change, against the merge base:

  schema     a schema/*.py module (not schema/migrations/, not schema/generated/) whose code differs: its
             syntax tree, docstrings removed, is not the base's. Rewording a docstring or a comment is not
             a schema change; adding, removing or retyping a field, a validator or a vocabulary is.
  taxonomy   a taxonomy/*.yaml file whose structure differs: its terms (field, id, status, parent), its
             comparability profiles (material and applies_to), its groups (members), its homograph entries
             or its ledgers (retired and forbidden ids). Definition prose, examples and comments are not;
             05 S5 routes a gloss change through review, not through a migration.

The gate needs, in the same diff, an added ADR and an added or edited migration with the same number. The
regenerated JSON Schema and TypeScript types are required too, and job 5 (codegen drift) is what checks
them on the same pull request: a schema change that was not regenerated fails there.

    python scripts/check_schema_change_gate.py --base origin/main        # the diff base...HEAD
    python scripts/check_schema_change_gate.py --base REF --head REF
    python scripts/check_schema_change_gate.py --root DIR --base REF     # another repository (the tests do)

Exit 0 when the diff changes no schema or carries its ADR and migration, 1 otherwise, 2 on a git error.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADR = re.compile(r'^adr/(\d{4})-[^/]+\.md$')
MIGRATION = re.compile(r'^schema/migrations/(\d{4})-[^/]+\.py$')
SCHEMA_MODULE = re.compile(r'^schema/[^/]+\.py$')
TAXONOMY_FILE = re.compile(r'^taxonomy/[^/]+\.ya?ml$')


class GitError(RuntimeError):
    pass


def git(root: str, *args: str) -> str:
    r = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise GitError('git %s: %s' % (' '.join(args), r.stderr.strip()))
    return r.stdout


def changed(root: str, base: str, head: str) -> list[tuple[str, str]]:
    """(status letter, path) for every file the diff base...head touches; a rename is a delete and an add."""
    out = []
    for line in git(root, 'diff', '--name-status', '--no-renames', '%s...%s' % (base, head)).splitlines():
        status, path = line.split('\t', 1)
        out.append((status[0], path))
    return out


def blob(root: str, rev: str, path: str) -> str | None:
    r = subprocess.run(['git', 'show', '%s:%s' % (rev, path)], cwd=root, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.stdout if r.returncode == 0 else None


def code_of(source: str | None) -> str | None:
    """The module's syntax tree with every docstring removed, as a string; None for no file."""
    if source is None:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source                                   # unparsable: compare the text, a change is a change
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body \
                and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def structure_of(text: str | None):
    """A vocabulary file's structure, prose left out; None for no file."""
    if text is None:
        return None
    doc = yaml.safe_load(text) or {}
    if not isinstance(doc, dict):
        return repr(doc)
    out = {}
    if doc.get('terms'):
        out['terms'] = sorted((str(t.get('field')), str(t.get('id')), str(t.get('status')), str(t.get('parent')))
                              for t in doc['terms'])
    if doc.get('profiles'):
        out['profiles'] = sorted((p['id'], tuple(sorted(p.get('material') or [])),
                                  tuple(sorted(tuple(x) for x in p.get('applies_to') or []))) for p in doc['profiles'])
    if 'fallback' in doc and isinstance(doc['fallback'], dict):
        out['fallback'] = tuple(sorted(doc['fallback'].get('material') or []))
    if doc.get('groups'):
        out['groups'] = sorted((g['id'], tuple(sorted(g.get('members') or []))) for g in doc['groups'])
    if doc.get('entries'):
        out['entries'] = sorted(repr(sorted((k, str(v)) for k, v in e.items() if k != 'rationale'))
                                for e in doc['entries'] if isinstance(e, dict))
    for ledger, key in (('retired', 'id'), ('forbidden', 'identifier')):
        if doc.get(ledger):
            out[ledger] = sorted(str(e.get(key)) for e in doc[ledger])
    return out


def schema_changes(root: str, base: str, head: str, files: list[tuple[str, str]]) -> list[str]:
    merge_base = git(root, 'merge-base', base, head).strip()
    out = []
    for _, path in files:
        if SCHEMA_MODULE.match(path):
            if code_of(blob(root, merge_base, path)) != code_of(blob(root, head, path)):
                out.append(path)
        elif TAXONOMY_FILE.match(path):
            if structure_of(blob(root, merge_base, path)) != structure_of(blob(root, head, path)):
                out.append(path)
    return out


def check(root: str, base: str, head: str = 'HEAD') -> tuple[list[str], list[str]]:
    """(the schema and taxonomy changes found, the problems with them)."""
    files = changed(root, base, head)
    found = schema_changes(root, base, head, files)
    if not found:
        return [], []
    adrs = {m.group(1) for s, p in files if s == 'A' for m in [ADR.match(p)] if m}
    migrations = {m.group(1) for s, p in files if s in 'AM' for m in [MIGRATION.match(p)] if m}
    problems = []
    if not adrs:
        problems.append('no ADR is added (adr/NNNN-*.md)')
    if not migrations:
        problems.append('no migration is added or edited (schema/migrations/NNNN-*.py)')
    if adrs and migrations and not adrs & migrations:
        problems.append('the ADR (%s) and the migration (%s) carry different numbers; a migration takes its '
                        "ADR's number (03 S9)" % (', '.join(sorted(adrs)), ', '.join(sorted(migrations))))
    return found, problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--base', default='origin/main')
    p.add_argument('--head', default='HEAD')
    a = p.parse_args(argv)
    try:
        found, problems = check(a.root, a.base, a.head)
    except GitError as e:
        print('check_schema_change_gate: %s' % e, file=sys.stderr)
        return 2
    if not found:
        print('check_schema_change_gate: no schema or taxonomy change in %s...%s' % (a.base, a.head))
        return 0
    print('check_schema_change_gate: schema or taxonomy change in %s' % ', '.join(found))
    for line in problems:
        print('BLOCKING  schema-change-gate  %s' % line)
    if not problems:
        print('check_schema_change_gate: the ADR and its migration are in the diff')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
