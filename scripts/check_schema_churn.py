#!/usr/bin/env python3
"""The schema freeze and stopping rule (b) (P1-S3-T09; 14-roadmap "Stopping rules and re-plans", Phase 1 exit).

14-roadmap Phase 1's exit criterion: "The schema has not changed in the last 40 entries. If it is still churning
at entry 260, Phase 0 did not finish and the checkpoint was not honest." Stopping rule (b): "Trigger: any schema
change after entry 60. Response: stop curation entirely and finish Phase 0 properly."

This counts the curated benchmark entries (data/benchmarks/<family>/*.yaml, not _stubs/) added since the last
commit that changed the schema's code -- a schema/*.py module whose syntax tree, docstrings aside, changed
(scripts/check_schema_change_gate.py's test), so a reworded docstring does not reset the count -- and reports:

  window     entries added since that change, against --window (40). Inside the window exits 1.
  rule (b)   how many entries existed when the schema last changed; above 60, the rule fires and says so.

    python scripts/check_schema_churn.py --window 40      # exit 0 when the schema held for 40 entries, else 1
    python scripts/check_schema_churn.py --root DIR       # another repository (the tests do)

In pr-validate.yml it is a reported signal, run through scripts/reported.py (a warning on a green job, never a
block); at the Phase 1 exit gate it is blocking, which is where a still-moving schema means the plan has to stop.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_schema_change_gate import code_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY = re.compile(r'^data/benchmarks/(?!_)[^/]+/[^/]+\.yaml$')
SCHEMA = re.compile(r'^schema/[^/]+\.py$')
RULE_B_ENTRY = 60


def git(root: str, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', check=True).stdout


def blob(root, rev, path):
    r = subprocess.run(['git', 'show', '%s:%s' % (rev, path)], cwd=root, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return r.stdout if r.returncode == 0 else None


def last_schema_change(root: str) -> str | None:
    """The newest commit whose schema/*.py code changed against its first parent."""
    for sha in git(root, 'log', '--format=%H', '--', 'schema/').split():
        parents = git(root, 'rev-list', '--parents', '-n', '1', sha).split()[1:]
        files = [f for f in git(root, 'diff-tree', '-r', '--root', '--no-commit-id', '--name-only', sha).split()
                 if SCHEMA.match(f)]
        before = parents[0] if parents else None
        if any(code_of(blob(root, before, f) if before else None) != code_of(blob(root, sha, f)) for f in files):
            return sha
    return None


def entries_added(root: str, rev_range: str | None) -> list[str]:
    args = ['log', '--diff-filter=A', '--name-only', '--format=']
    out = git(root, *args, *( [rev_range] if rev_range else []), '--', 'data/benchmarks/')
    return sorted({p for p in out.split() if ENTRY.match(p)})


def report(root: str, window: int) -> dict:
    sha = last_schema_change(root)
    since = entries_added(root, '%s..HEAD' % sha if sha else None)
    at_change = len(entries_added(root, sha)) if sha else 0
    return {'last_change': sha, 'entries_since': len(since), 'entries_at_change': at_change, 'window': window,
            'inside_window': sha is not None and len(since) < window, 'rule_b_fires': at_change > RULE_B_ENTRY}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--window', type=int, default=40)
    a = p.parse_args(argv)
    r = report(a.root, a.window)
    if r['last_change'] is None:
        print('check_schema_churn: no schema change in the history; nothing to freeze')
        return 0
    date = git(a.root, 'log', '-1', '--format=%ad', '--date=short', r['last_change']).strip()
    print('check_schema_churn: the schema last changed in %s (%s), when %d entries existed; %d entries added since'
          % (r['last_change'][:12], date, r['entries_at_change'], r['entries_since']))
    if r['rule_b_fires']:
        print('STOPPING RULE (b) FIRES: the schema changed after entry %d. Stop curation and finish Phase 0 '
              '(14-roadmap).' % RULE_B_ENTRY)
    if r['inside_window']:
        print('schema freeze: NOT YET -- the schema changed inside the last %d entries (%d of %d entries since)'
              % (a.window, r['entries_since'], a.window))
        return 1
    print('schema freeze: held for the last %d entries' % a.window)
    return 0


if __name__ == '__main__':
    sys.exit(main())
