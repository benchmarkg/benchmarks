"""`bench migrate <nnnn> [--dry-run|--apply]` (P0-S5-T07; 03 S9, 05 S3).

05 S3: "Apply a taxonomy migration script from `schema/migrations/<nnnn>-<slug>.py` across the
corpus. `--dry-run` reports only, and its output is attached to the ADR's PR; `--apply` writes.
Splits are never automatic." The convention a migration follows is schema/migrations/__init__.py's.

Three refusals, each mechanical:

  - `--apply` needs adr/<nnnn>-*.md. A migration is the corpus half of a decision; without the
    decision on file it is an unexplained rewrite of the data.
  - A split's plan may write only `sentinel(old)` where the old term was (03 S9.1: "no rule can
    decide which of the 41 existing entries is tabletop and which is bimanual"). Any other value is
    a guess, and the plan is refused before it is printed, not only before it is applied.
  - A split never applies unattended: not in CI, not without a terminal, and not without a human
    typing the migration's number. The sentinels it writes are publication blockers that someone
    has to re-adjudicate, one primary source at a time; that someone should be present.

Writing goes through tools/fmt.py's emitter, file by file, after every row has been checked against
the file it targets -- a row whose old value is not what the file holds means the plan is stale, and
then nothing is written at all.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from types import ModuleType

from schema.migrations import KINDS, Row, sentinel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS = os.path.join(ROOT, 'schema', 'migrations')
NUMBER = re.compile(r'^\d{4}$')
STATUS = re.compile(r'^- \*\*Status:\*\*\s*(.+?)\s*$', re.M)


class MigrateError(ValueError):
    pass


@dataclass
class Migration:
    number: str
    path: str
    module: ModuleType

    @property
    def kind(self) -> str:
        return self.module.KIND

    @property
    def summary(self) -> str:
        return self.module.SUMMARY

    def plan(self, root: str) -> list[Row]:
        rows = list(self.module.plan(root))
        check_plan(self, rows)
        return rows


def find(number: str, directory: str | None = None) -> Migration:
    if not NUMBER.match(number):
        raise MigrateError('a migration number is four digits, the ADR\'s (e.g. 0027), not %r' % number)
    directory = directory or MIGRATIONS
    hits = sorted(glob.glob(os.path.join(directory, number + '-*.py')))
    if len(hits) != 1:
        raise MigrateError('%s migration file(s) match schema/migrations/%s-*.py%s' % (
            len(hits) or 'no', number, ': ' + ', '.join(os.path.basename(h) for h in hits) if hits else ''))
    spec = importlib.util.spec_from_file_location('migration_' + number, hits[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, ok in (('KIND', lambda v: v in KINDS), ('SUMMARY', lambda v: isinstance(v, str) and v.strip()),
                     ('plan', callable)):
        if not hasattr(module, name) or not ok(getattr(module, name)):
            raise MigrateError('%s: needs %s (%s)' % (os.path.basename(hits[0]), name,
                                                      'one of ' + ', '.join(KINDS) if name == 'KIND' else 'see schema/migrations/__init__.py'))
    return Migration(number, hits[0], module)


def check_plan(m: Migration, rows: list[Row]) -> None:
    for r in rows:
        if not isinstance(r, Row):
            raise MigrateError('migration %s: plan() returned %r, not a Row' % (m.number, r))
        parts = r.path.split('/')
        if os.path.isabs(r.path) or '..' in parts or '\\' in r.path or not r.at:
            raise MigrateError('migration %s: row %s:%s is not a root-relative path and a location' % (m.number, r.path, r.at))
    if m.kind == 'noop' and rows:
        raise MigrateError('migration %s is a noop, and its plan changes %d value(s)' % (m.number, len(rows)))
    if m.kind == 'split':
        guesses = [r for r in rows if not (isinstance(r.old, str) and r.new == sentinel(r.old))]
        if guesses:
            r = guesses[0]
            raise MigrateError('migration %s is a split, and a split writes only the sentinel %r in place of the old '
                               'term; %s %s writes %r, which is a guess (03 S9.1). %d row(s) like it'
                               % (m.number, sentinel(str(r.old)), r.path, r.where(), r.new, len(guesses)))


def adr_for(number: str, root: str) -> str | None:
    hits = sorted(glob.glob(os.path.join(root, 'adr', number + '-*.md')))
    if len(hits) > 1:
        raise MigrateError('%d ADR files are numbered %s: %s' % (len(hits), number, ', '.join(map(os.path.basename, hits))))
    return os.path.relpath(hits[0], root).replace(os.sep, '/') if hits else None


def adr_status(root: str, rel: str) -> str:
    with open(os.path.join(root, rel), encoding='utf-8') as fh:
        m = STATUS.search(fh.read())
    return m.group(1) if m else 'no Status line'


def unattended() -> str | None:
    """Why no human is at the controls, or None when one is."""
    if os.environ.get('CI'):
        return 'CI is set'
    if not (sys.stdin and sys.stdin.isatty()):
        return 'stdin is not a terminal'
    return None


def _node(doc, at):
    for p in at:
        doc = doc[p]
    return doc


def render(rows: list[Row], root: str) -> OrderedDict[str, str]:
    """The new text of every file the rows touch, or MigrateError before anything is written."""
    from tools import fmt
    by_file: OrderedDict[str, list[Row]] = OrderedDict()
    for r in rows:
        by_file.setdefault(r.path, []).append(r)
    out: OrderedDict[str, str] = OrderedDict()
    for rel, file_rows in by_file.items():
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            raise MigrateError('%s: the plan names a file that does not exist' % rel)
        with open(full, encoding='utf-8') as fh:
            doc = fmt.emitter().load(fh)
        for r in file_rows:
            try:
                parent, current = _node(doc, r.at[:-1]), _node(doc, r.at)
            except (KeyError, IndexError, TypeError):
                raise MigrateError('%s %s: the plan names a location the file does not have; re-run --dry-run'
                                   % (rel, r.where())) from None
            if current != r.old:
                raise MigrateError('%s %s holds %r, not the planned %r; the plan is stale, re-run --dry-run'
                                   % (rel, r.where(), current, r.old))
            parent[r.at[-1]] = r.new
        out[rel] = fmt.format_text(fmt.dumps(doc), fmt.model_for(rel), rel)
    return out


def apply(m: Migration, root: str, confirm=None) -> list[str]:
    """Write the plan. `confirm(m, rows)` is asked before a split writes, and must return True."""
    adr = adr_for(m.number, root)
    if adr is None:
        raise MigrateError('migration %s has no ADR: --apply needs adr/%s-*.md, the decision this migration carries '
                           '(03 S9)' % (m.number, m.number))
    rows = m.plan(root)
    if m.kind == 'split':
        why = unattended()
        if why:
            raise MigrateError('migration %s is a split, and a split never applies unattended (03 S9.1; %s). Run it '
                               'from a terminal, outside CI, and confirm it by hand' % (m.number, why))
        if confirm is None or not confirm(m, rows):
            raise MigrateError('migration %s: the split was not confirmed; nothing written' % m.number)
    texts = render(rows, root)
    for rel, text in texts.items():
        with open(os.path.join(root, rel), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return list(texts)
