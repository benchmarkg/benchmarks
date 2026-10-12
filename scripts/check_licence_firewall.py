#!/usr/bin/env python3
"""Check 8, the licence firewall (P0-S6-T04; 05 S9, 04 S9, 05 S12).

05 S9: "Reject any commit that moves content out of `vendor/` into `data/` without a `Re-derived-from:`
trailer naming a primary source." vendor/ holds inbound material under a licence the CC-BY core cannot
carry (the Papers with Code archive is CC-BY-SA; 04 S9's licence table): it may inform a curator, and a
value may enter data/ only once re-derived from a primary source, which the trailer names.

A commit moves content from vendor/ into data/ when, against its first parent:

  rename/copy  git's rename or copy detection (-M -C --find-copies-harder) pairs a vendor/ file with an
               added or changed data/ file;
  lines        a line it adds under data/ appears verbatim in a vendor/ file of the parent tree. Lines
               shorter than MIN_LINE characters, once stripped, are ignored: `access: fully-open` is a
               shared vocabulary, not copied content.

Such a commit passes only with a `Re-derived-from:` trailer whose value names a primary source: a Source
id (`src-...`) or a URL.

    python scripts/check_licence_firewall.py --base origin/main          # every commit in base..HEAD
    python scripts/check_licence_firewall.py --base REF --head REF       # another range
    python scripts/check_licence_firewall.py                             # HEAD's own commit only
    python scripts/check_licence_firewall.py --root DIR                  # another repository (the tests do)

Exit 0 when no commit in the range breaks the rule, 1 otherwise, 2 on a git error.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR, DATA = 'vendor/', 'data/'
MIN_LINE = 40
TRAILER = 'Re-derived-from'
PRIMARY = re.compile(r'^(src-[a-z0-9]+(-[a-z0-9]+)*|https?://\S+)$')


class GitError(RuntimeError):
    pass


def git(root: str, *args: str) -> str:
    r = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise GitError('git %s: %s' % (' '.join(args), r.stderr.strip()))
    return r.stdout


def commits(root: str, base: str | None, head: str) -> list[str]:
    if base is None:
        return [git(root, 'rev-parse', head).strip()]
    return git(root, 'rev-list', '--reverse', '%s..%s' % (base, head)).split()


def parent(root: str, sha: str) -> str | None:
    parents = git(root, 'rev-list', '--parents', '-n', '1', sha).split()[1:]
    return parents[0] if parents else None


def paired_moves(root: str, sha: str) -> list[str]:
    """data/ paths git pairs with a vendor/ source in this commit (a rename or a copy)."""
    out = git(root, 'diff-tree', '-r', '--root', '--no-commit-id', '-M', '-C', '--find-copies-harder',
              '--name-status', sha)
    moves = []
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[0][:1] in 'RC' and parts[1].startswith(VENDOR) and parts[2].startswith(DATA):
            moves.append('%s -> %s' % (parts[1], parts[2]))
    return moves


def vendor_lines(root: str, rev: str | None) -> set[str]:
    if rev is None:
        return set()
    files = [f for f in git(root, 'ls-tree', '-r', '--name-only', rev).splitlines() if f.startswith(VENDOR)]
    lines: set[str] = set()
    for f in files:
        for line in git(root, 'show', '%s:%s' % (rev, f)).splitlines():
            s = line.strip()
            if len(s) >= MIN_LINE:
                lines.add(s)
    return lines


def copied_lines(root: str, sha: str) -> list[str]:
    """data/ paths where this commit adds a line a vendor/ file of the parent tree already held."""
    before = parent(root, sha)
    known = vendor_lines(root, before)
    if not known:
        return []
    diff = git(root, 'diff', '--unified=0', '--no-color', before, sha, '--', DATA) if before else \
        git(root, 'show', '--unified=0', '--no-color', '--format=', sha, '--', DATA)
    hits, path = [], None
    for line in diff.splitlines():
        if line.startswith('+++ '):
            path = line[6:] if line.startswith('+++ b/') else None
        elif line.startswith('+') and path and line[1:].strip() in known and path not in hits:
            hits.append(path)
    return hits


def trailer(root: str, sha: str) -> list[str]:
    raw = git(root, 'log', '-1', '--format=%(trailers:key=' + TRAILER + ',valueonly)', sha)
    return [v.strip() for v in raw.splitlines() if v.strip()]


def check(root: str, base: str | None, head: str = 'HEAD') -> list[str]:
    bad = []
    for sha in commits(root, base, head):
        moves = paired_moves(root, sha) + ['line copied into %s' % p for p in copied_lines(root, sha)]
        if not moves:
            continue
        names = trailer(root, sha)
        if any(PRIMARY.match(n) for n in names):
            continue
        why = 'its %s: trailer does not name a primary source (a src- id or a URL)' % TRAILER if names else \
            'it has no %s: trailer' % TRAILER
        bad.append('%s moves content from vendor/ into data/ (%s), and %s' % (sha[:12], '; '.join(moves), why))
    return bad


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--base', default=None, help='check every commit in BASE..HEAD (default: HEAD only)')
    p.add_argument('--head', default='HEAD')
    a = p.parse_args(argv)
    try:
        bad = check(a.root, a.base, a.head)
    except GitError as e:
        print('check_licence_firewall: %s' % e, file=sys.stderr)
        return 2
    for line in bad:
        print('BLOCKING  8/licence-firewall  %s' % line)
    print('check_licence_firewall: %d commit(s) move vendor/ content into data/ without a primary source'
          % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
