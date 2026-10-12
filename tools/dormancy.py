"""The dormancy triggers (P0-S7-T04; 05 S10 item 5, SUCCESSION.md item 5, 14-roadmap stopping rules).

SUCCESSION.md: "The build reads the date of the last human commit to `data/`.
  - At 90 days without a human commit to `data/`, this file is invoked. A `Maintainer succession` issue is
    opened and pinned ...
  - At 180 days without a human commit to `data/`, the site-wide staleness banner turns on, driven by the
    same commit timestamp ... Automated ingestion commits do not count as curation and do not reset either
    clock."

    python -m tools.dormancy                    # print the state; write nothing
    python -m tools.dormancy --out build/dormancy.json
    python -m tools.dormancy --apply            # also open and pin the succession issue when it is due
    python -m tools.dormancy --today 2027-01-15 # any clock (the tests inject one)

The state is {last_human_commit, days, succession, banner}. `succession` holds from day 90, `banner` from
day 180. `bench build` writes it to build/dormancy.json, which the site's base layout reads for the banner;
.github/workflows/health-check.yml runs `--apply` on a schedule, which is what opens the issue. Opening is
idempotent: an open issue with the title is left as it is.

A commit is a curator's unless its author is a bot (a name ending `[bot]`, or the project's own uaibi-bot)
or its subject marks an ingest (`ingest:`), so neither the bot's pull requests nor an adapter's batch resets
a clock.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUCCESSION_DAYS = 90
BANNER_DAYS = 180
ISSUE_TITLE = 'Maintainer succession'
BOT_NAMES = ('uaibi-bot',)


def is_automated(name: str, email: str, subject: str) -> bool:
    n = name.strip().lower()
    return n.endswith('[bot]') or n in BOT_NAMES or email.lower().endswith('[bot]@users.noreply.github.com') \
        or subject.strip().lower().startswith('ingest:')


def last_human_commit(root: str = ROOT) -> dt.date | None:
    """The author date of the newest commit touching data/ that a person made, or None if there is none."""
    out = subprocess.run(['git', 'log', '--format=%aI%x1f%an%x1f%ae%x1f%s', '--', 'data/'], cwd=root,
                         capture_output=True, text=True, encoding='utf-8', errors='replace', check=True).stdout
    for line in out.splitlines():
        when, name, email, subject = line.split('\x1f', 3)
        if not is_automated(name, email, subject):
            return dt.datetime.fromisoformat(when).date()
    return None


def state(last: dt.date | None, today: dt.date) -> dict:
    if last is None:
        return {'last_human_commit': None, 'days': None, 'succession': False, 'banner': False}
    days = (today - last).days
    return {'last_human_commit': last.isoformat(), 'days': days,
            'succession': days >= SUCCESSION_DAYS, 'banner': days >= BANNER_DAYS}


def banner_text(s: dict) -> str | None:
    """SUCCESSION.md's wording, or None while the banner is off."""
    if not s['banner']:
        return None
    return ('This index has not been curated since %s. Data older than that should be checked against primary '
            'sources.' % s['last_human_commit'])


def gh(*args: str) -> str:
    return subprocess.run(['gh', *args], capture_output=True, text=True, encoding='utf-8', check=True).stdout


def open_succession_issue(s: dict, run: Callable[..., str] = gh) -> str:
    """Open and pin the succession issue unless one is already open. Returns what was done."""
    found = json.loads(run('issue', 'list', '--state', 'open', '--search', 'in:title "%s"' % ISSUE_TITLE,
                           '--json', 'number,title') or '[]')
    if any(i['title'] == ISSUE_TITLE for i in found):
        return 'already open'
    body = ('No person has committed to `data/` since %s (%d days). SUCCESSION.md item 5 is invoked: the README '
            'carries the notice, the stewards and institutions in its handover list are contacted in order, and '
            'the search for a successor begins. The site-wide staleness banner turns on at %d days.'
            % (s['last_human_commit'], s['days'], BANNER_DAYS))
    url = run('issue', 'create', '--title', ISSUE_TITLE, '--body', body).strip()
    run('issue', 'pin', url)
    return 'opened and pinned %s' % url


def write(s: dict, path: str) -> str:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(dict(s, banner_text=banner_text(s)), fh, indent=2, sort_keys=True)
        fh.write('\n')
    return path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--today', type=dt.date.fromisoformat, default=None)
    p.add_argument('--out', default=None, help='write the state as JSON here')
    p.add_argument('--apply', action='store_true', help='open and pin the succession issue when it is due')
    a = p.parse_args(argv)
    s = state(last_human_commit(a.root), a.today or dt.date.today())
    print('dormancy: last human commit to data/ %s, %s day(s); succession %s, banner %s'
          % (s['last_human_commit'], s['days'], 'DUE' if s['succession'] else 'not due', 'ON' if s['banner'] else 'off'))
    if a.out:
        print('wrote %s' % write(s, a.out))
    if a.apply and s['succession']:
        print('succession issue: %s' % open_succession_issue(s))
    return 0


if __name__ == '__main__':
    sys.exit(main())
