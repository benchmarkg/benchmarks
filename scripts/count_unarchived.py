#!/usr/bin/env python3
"""Count the non-DOI Sources with no archive capture, oldest first (P5-S8-T02; 06 S7.1, 14 Phase 5).

    python scripts/count_unarchived.py                  # budget 500, the nightly capture cap
    python scripts/count_unarchived.py --budget 20
    python scripts/count_unarchived.py --json

A Source is unarchived when it has no DOI and no archive_url: a DOI needs no capture (04 S12), and
`archive_status: not-required` on a non-DOI Source (04 S9's paywall case, citable but never quoted)
is listed apart as exempt, not counted. Each unarchived Source is shown with its reliability
(schema.source.reliability) and its age from first ingest, oldest first -- the order the nightly
archiver (ingest/archive_sources.py) works in, so the head of this list is what tonight's run
reaches first and anything still at the head after a week has missed 06 S7.1's seven-day SLA.

Exit status, and why each is a failure:
  1  more unarchived Sources than --budget: the backlog no longer clears in one nightly run of 500
     captures, so it is growing faster than the rolling budget can drain it (06 S7.1)
  1  any `lost` Source -- dead (link_status: dead, written by tools/check_links.py) and uncaptured.
     14's Phase 5 exit criterion 3 is "zero dead unarchived source links": such a citation points at
     nothing and no run of the archiver can bring it back, only a curator (a new URL for the same
     work, or retiring the claim that cites it)
  0  otherwise

A Source never link-checked is not known to be dead, so it is counted `unchecked` and named: the
count of lost Sources is only as good as the link checks behind it, and
`python -m tools.check_links --unarchived` checks every unarchived Source at once.

The first-ingest date is scripts/check_archive_coverage.py's (the earliest of fetched_at, accessed
and archive_requested_at), so the two scripts cannot disagree about which Source is oldest.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(1, ROOT)
from check_archive_coverage import first_ingest, load_sources, parse_time  # noqa: E402

from schema.source import reliability  # noqa: E402

BUDGET = 500                    # 06 S7.1 / 07 S10: captures per nightly run


def survey(root=ROOT, now=None):
    """{'unarchived': [...oldest first], 'exempt': [...], 'lost': [...], 'unchecked': [...]}."""
    unarchived, exempt = [], []
    for s in load_sources(root):
        r = s.record
        if r.get('doi') or r.get('archive_url'):          # get-default: absent is null
            continue
        born = first_ingest(r)
        row = {'id': r['id'], 'path': os.path.relpath(s.path, root).replace(os.sep, '/'), 'url': r.get('url'),  # get-default: tier 1 reports a missing url
               'archive_status': r.get('archive_status'), 'reliability': reliability(r),               # get-default: the same
               'link_status': r.get('link_status'), 'first_ingest': born.strftime('%Y-%m-%d') if born else None,  # get-default: never link-checked
               'age_days': (now - born).days if now and born else None,
               'failure_reason': r.get('failure_reason')}                                             # get-default: only a failure has one
        (exempt if r.get('archive_status') == 'not-required' else unarchived).append(row)                 # get-default: the same
    unarchived.sort(key=lambda x: (x['first_ingest'] or '0000', x['id']))     # undated first: they are the oldest unknowns
    return {'unarchived': unarchived, 'exempt': exempt,
            'lost': [x for x in unarchived if x['reliability'] == 'lost'],
            'unchecked': [x for x in unarchived if x['link_status'] is None]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--budget', type=int, default=BUDGET, help='fail above this many unarchived (default 500)')
    p.add_argument('--now', help='as-of instant for ages (default: now, UTC)')
    p.add_argument('--limit', type=int, default=20, help='name at most this many, oldest first (default 20)')
    p.add_argument('--json', action='store_true')
    a = p.parse_args(argv)
    from datetime import datetime, timezone
    now = parse_time(a.now) if a.now else datetime.now(timezone.utc).replace(microsecond=0)
    got = survey(a.root, now)
    n, lost = len(got['unarchived']), got['lost']
    over = n > a.budget
    code = 1 if over or lost else 0
    if a.json:
        print(json.dumps(dict(got, budget=a.budget, exit_code=code), indent=2))
        return code
    for x in lost:
        print('LOST        %s  %s  (link dead, no capture%s)' % (x['id'], x['url'],
                                                              '; ' + x['failure_reason'] if x['failure_reason'] else ''))
    for x in got['unarchived'][:a.limit]:
        print('%-11s %s  first ingest %s%s  link %s' % (x['reliability'], x['id'], x['first_ingest'] or 'unknown',
                                                       ' (%d days)' % x['age_days'] if x['age_days'] is not None else '',
                                                       x['link_status'] or 'unchecked'))
    if n > a.limit:
        print('... and %d more' % (n - a.limit))
    by = {k: sum(1 for x in got['unarchived'] if x['reliability'] == k) for k in ('lost', 'unarchivable', 'pending')}
    print('count_unarchived: %d non-DOI Source(s) with no capture (budget %d%s): %d lost, %d unarchivable, %d pending; '
          '%d never link-checked; %d exempt (not-required)'
          % (n, a.budget, ', OVER' if over else '', by['lost'], by['unarchivable'], by['pending'],
             len(got['unchecked']), len(got['exempt'])))
    if lost:
        print('exit criterion 3 (14 Phase 5): %d dead unarchived source link(s); a curator re-points or retires each' % len(lost))
    return code


if __name__ == '__main__':
    sys.exit(main())
