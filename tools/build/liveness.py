#!/usr/bin/env python3
"""build/derived/liveness.json: observed staleness signals per benchmark (P4-S2-T07; 12 S7, S1).

    python tools/build/liveness.py --out build/derived/liveness.json [--root PATH] [--as-of YYYY-MM-DD]

Observations, not verdicts (12 S7). Per curated benchmark, every signal optional and dated:

  days_since_repo_push            GitHub `pushed_at`, from the latest metrics/adoption-counters.jsonl
                                  snapshot, else the record's liveness.repo_last_commit
  days_since_dataset_modified     HF `lastModified`, from the latest snapshot
  days_since_leaderboard_change   the record's liveness.leaderboard_last_updated (an adapter's
                                  content-hash history will feed it when one exists)
  has_reproduction_script         yes | no | not-checked, from liveness.reproduction_script_present
  archived_source_rot             of the Sources the record cites and the link-rot check has read, the
                                  share whose link_status is dead (P5-S8-T01)

Two flags, each computed only when at least two of the three activity signals were observed; below two
they abstain (null, with the reason), because one quiet signal is not evidence of anything:

  dormant-signal    no observed activity on any checked signal for 18 months
  likely-inactive   no observed activity for 36 months

Each carries the dates and the signals checked, and the phrase the page prints: "no observed activity in
N days across M checked signals" -- never "dead". Neither ever writes `lifecycle: deprecated` (12 S7; 12
S1.1 rule 1): the flag prompts a curator's review, it does not replace it.

`as_of` is the date the days are counted to. It defaults to the data commit's own date, not today, so a
build is a function of the commit (12 S1.1 rule 4) and two builds of it are byte-identical.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FORMAT = 1
MIN_SIGNALS = 2
FLAGS = (('dormant-signal', 18), ('likely-inactive', 36))       # months of no observed activity (12 S7)
ACTIVITY = ('repo_push', 'dataset_modified', 'leaderboard_change')


def as_date(value) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):                  # 31 Aug + 18 months is the last day of February
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise AssertionError('unreachable')


def tri_state(value) -> str:
    return 'not-checked' if value is None else ('yes' if value else 'no')


def flags(activity: dict[str, date | None], as_of: date) -> dict:
    """12 S7's two flags from the observed activity dates, or an abstention naming how many were observed."""
    seen = {k: v for k, v in activity.items() if v is not None}
    if len(seen) < MIN_SIGNALS:
        reason = 'abstains: %d of %d activity signals observed, %d needed' % (len(seen), len(activity), MIN_SIGNALS)
        return {name: None for name, _ in FLAGS} | {'basis': reason, 'last_activity': None, 'statement': None}
    last = max(seen.values())
    days = (as_of - last).days
    out = {name: add_months(last, months) <= as_of for name, months in FLAGS}
    out['basis'] = 'signals checked: %s' % ', '.join(sorted(seen))
    out['last_activity'] = last.isoformat()
    out['statement'] = 'no observed activity in %d days across %d checked signals' % (days, len(seen))
    return out


def rot(record: dict, sources: dict[str, dict]) -> dict | None:
    """Of the Sources this record cites that the link-rot check has read, how many are dead."""
    from tools.build.artifacts import cited_sources
    checked = [sources[s] for s in sorted(cited_sources(record)) if s in sources and sources[s].get('link_status')]
    if not checked:
        return None
    dead = sum(1 for s in checked if s['link_status'] == 'dead')
    return {'dead': dead, 'checked': len(checked), 'fraction': round(dead / len(checked), 4)}


def load_sources(root: str) -> dict[str, dict]:
    from schema.taxonomy import read_yaml
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '**', '*.yaml'), recursive=True)):
        rec = read_yaml(path)
        out[rec['id']] = rec
    return out


def benchmark_liveness(b: dict, snap: dict | None, sources: dict[str, dict], as_of: date) -> dict:
    live = b.get('liveness') or {}                                  # get-default: unobserved is an empty block
    gh = (snap or {}).get('github') or {}                           # get-default: no snapshot is no signal
    hf = (snap or {}).get('huggingface') or {}                      # get-default: as above
    activity = {
        'repo_push': as_date(gh.get('pushed_at')) or as_date(live.get('repo_last_commit')),  # get-default: optional
        'dataset_modified': as_date(hf.get('lastModified')),                                 # get-default: optional
        'leaderboard_change': as_date(live.get('leaderboard_last_updated')),                 # get-default: optional
    }
    days = {k: (as_of - v).days if v else None for k, v in activity.items()}
    return {
        'id': b['id'],
        'signals': {
            'days_since_repo_push': days['repo_push'],
            'days_since_dataset_modified': days['dataset_modified'],
            'days_since_leaderboard_change': days['leaderboard_change'],
            'has_reproduction_script': tri_state(live.get('reproduction_script_present')),   # get-default: optional
            'archived_source_rot': rot(b, sources),
        },
        'observed': {k: v.isoformat() if v else None for k, v in activity.items()},
        'flags': flags(activity, as_of),
    }


def commit_date(root: str) -> date:
    out = subprocess.run(['git', '-C', root, 'log', '-1', '--format=%cs'], capture_output=True, text=True, check=True)
    return date.fromisoformat(out.stdout.strip())


def build(root: str = ROOT, as_of: date | None = None) -> dict:
    from tools.build.adoption import benchmarks, latest_counters
    as_of = as_of or commit_date(root)
    counters, sources = latest_counters(root), load_sources(root)
    rows = [benchmark_liveness(b, counters.get(bid), sources, as_of) for bid, b in sorted(benchmarks(root).items())]
    return {'artifact': 'liveness', 'format': FORMAT, 'as_of': as_of.isoformat(),
            'min_signals': MIN_SIGNALS, 'flags': {name: '%d months' % m for name, m in FLAGS},
            'benchmarks': rows}


def main(argv=None) -> int:
    from tools.build.adoption import serialise
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--as-of', type=date.fromisoformat, default=None, help="default: the data commit's date")
    ap.add_argument('--out', default=None, help='write here; default stdout')
    a = ap.parse_args(argv)
    body = serialise(build(a.root, a.as_of))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'wb') as fh:
            fh.write(body)
    else:
        sys.stdout.buffer.write(body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
