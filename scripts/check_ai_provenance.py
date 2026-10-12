#!/usr/bin/env python3
"""The drafts/ boundary: no AI-written record and no unvouched bot commit under data/ (P1-S2-T04; 05 S9 check 9i).

Two checks, both over data/:

  9i          no path carries `verification_status: ai-drafted-unverified` or `provenance: ai-worker` -- the grep of
              scripts/check_no_ai_records.py (P0-S6-T03), shared rather than repeated
  committers  the last commit to touch each tracked path under data/ was made by a person, or by one of the two
              automated authors the plan settles as legitimate: the issue-form bot, which authors a contributor's
              commit with a `Co-authored-by:` trailer naming them (05 S6), and an ingestion adapter, whose commits
              are subject-marked `ingest:` (07). Any other bot -- an AI worker above all -- fails.

The committer half follows 15-open-questions AI1 rather than the task's first wording ("assert a human committer for
every path under data/"): 15 records that a bare human-committer assertion "would fail every single one" of the
issue-form commits, because the bot authors them. So a bot commit passes only with a human co-author or an ingest
subject, which still fails the case the assertion exists for: a path whose last commit came from an unvouched bot.
A bot is a name ending `[bot]`, the project's own `uaibi-bot`, or a `[bot]@users.noreply.github.com` address
(tools/dormancy.py's definition).

    python scripts/check_ai_provenance.py              # exit 0 when both hold, 1 otherwise
    python scripts/check_ai_provenance.py --root DIR   # another git tree (the tests do)

Reported until the drafts are promoted (the maintainer's decision of 2026-10-12), as check 9i's own job is.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_no_ai_records import hits  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_NAMES = ('uaibi-bot',)
RS, US, GS = '\x1e', '\x1f', '\x1d'


def is_bot(name: str, email: str) -> bool:
    n = name.strip().lower()
    return n.endswith('[bot]') or n in BOT_NAMES or email.strip().lower().endswith('[bot]@users.noreply.github.com')


def git(root: str, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                          check=True).stdout


def last_commits(root: str) -> dict[str, dict]:
    """Each tracked path under data/ -> the newest commit that touched it: author, email, subject, co-authors."""
    tracked = set(git(root, 'ls-files', '--', 'data/').splitlines())
    fmt = RS + US.join(('%H', '%an', '%ae', '%s', '%(trailers:key=Co-authored-by,valueonly,separator=' + '%x1d' + ')'))
    out: dict[str, dict] = {}
    for record in git(root, 'log', '--format=' + fmt, '--name-only', '--', 'data/').split(RS)[1:]:
        head, _, names = record.partition('\n')
        sha, name, email, subject, trailers = (head.split(US) + [''] * 5)[:5]
        commit = {'sha': sha, 'name': name, 'email': email, 'subject': subject,
                  'coauthors': [t.strip() for t in trailers.split(GS) if t.strip()]}
        for path in names.split('\n'):
            path = path.strip()
            if path in tracked and path not in out:
                out[path] = commit
    return out


def committer_problems(root: str) -> list[str]:
    out = []
    for path, c in sorted(last_commits(root).items()):
        if not is_bot(c['name'], c['email']):
            continue
        if c['coauthors'] or c['subject'].strip().lower().startswith('ingest:'):
            continue
        out.append('%s: last committed by %s <%s> in %s with no human co-author and no ingest: subject'
                   % (path, c['name'], c['email'], c['sha'][:12]))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    drafts = hits(a.root)
    commits = committer_problems(a.root)
    for rel, n, label in drafts:
        print('BLOCKING  9i  %s:%d: %s under data/' % (rel, n, label))
    for line in commits:
        print('BLOCKING  committer  %s' % line)
    print('check_ai_provenance: %d AI-written record marker(s), %d path(s) last committed by an unvouched bot'
          % (len(drafts), len(commits)))
    return 1 if drafts or commits else 0


if __name__ == '__main__':
    sys.exit(main())
