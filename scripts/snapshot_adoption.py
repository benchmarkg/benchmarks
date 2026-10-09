#!/usr/bin/env python3
"""Snapshot GitHub stars and HF downloads into metrics/adoption-counters.jsonl, weekly (P4-S2-T07; 12 S6).

    uv run python scripts/snapshot_adoption.py              # GITHUB_TOKEN optional: 60 requests/hour without
    uv run python scripts/snapshot_adoption.py --dry-run    # print the lines, write nothing

12 S6: "Snapshot the current count weekly and own the series going forward." For every curated benchmark with a
GitHub `repository` or a Hugging Face dataset (its dataset_url, or external_ids.huggingface), one line:

    {"observed_on": "2026-10-04", "benchmark": "swe-bench",
     "github": {"repo": "owner/name", "stars": 4100, "forks": 700, "pushed_at": "...", "archived": false},
     "huggingface": {"dataset": "owner/name", "downloads": 1234, "likes": 56, "lastModified": "..."}}

Weekly means idempotent within an ISO week: a benchmark that already has a line in this week's file is not
asked again. Never the star history (`star+json` paginates the whole star list, 12 S6), never written into
data/: these are observed counters, outside the citable core, read by tools/build/adoption.py and
tools/build/liveness.py. A failed request is that side's `{"error": "HTTP 404"}`, never a zero.

This is the only part of P4-S2-T07 that touches the network; the two build steps never do (12 S1.1).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build.adoption import COUNTERS, benchmarks, read_jsonl  # noqa: E402

USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
GITHUB = re.compile(r'^https://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?(?:[#?].*)?$')
HF = re.compile(r'^https://huggingface\.co/datasets/([^/]+/[^/#?]+)')


def github_repo(b: dict) -> str | None:
    m = GITHUB.match(b.get('repository') or '')                    # get-default: optional field
    return '%s/%s' % m.groups() if m else None


def hf_dataset(b: dict) -> str | None:
    m = HF.match(b.get('dataset_url') or '')                       # get-default: optional field
    if m:
        return m.group(1)
    ext = (b.get('external_ids') or {}).get('huggingface')         # get-default: optional field
    return ext.split('datasets/', 1)[-1] if ext else None


def fetch_json(url: str, headers: dict) -> tuple[int, dict | None]:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json', **headers})
    from ingest.http.policy import refuse
    refuse(url)                                          # # 07 S10.1: no-collect and forbidden hold for every code path
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def github(repo: str, fetch, token: str | None) -> dict:
    headers = {'Authorization': 'Bearer %s' % token} if token else {}
    status, doc = fetch('https://api.github.com/repos/%s' % repo, headers)
    if status != 200:
        return {'repo': repo, 'error': 'HTTP %d' % status}
    return {'repo': repo, 'stars': doc['stargazers_count'], 'forks': doc['forks_count'],
            'pushed_at': doc['pushed_at'], 'archived': doc['archived']}


def huggingface(dataset: str, fetch) -> dict:
    status, doc = fetch('https://huggingface.co/api/datasets/%s' % dataset, {})
    if status != 200:
        return {'dataset': dataset, 'error': 'HTTP %d' % status}
    return {'dataset': dataset, 'downloads': doc['downloads'], 'likes': doc['likes'],
            'lastModified': doc['lastModified']}


def same_week(a: str, b: date) -> bool:
    return date.fromisoformat(a).isocalendar()[:2] == b.isocalendar()[:2]


def snapshot(root: str, today: date, fetch=fetch_json, token: str | None = None, sleep=time.sleep) -> list[dict]:
    """The lines this week still needs, one per benchmark with something to observe."""
    done = {r['benchmark'] for r in read_jsonl(os.path.join(root, COUNTERS)) if same_week(r['observed_on'], today)}
    lines = []
    for bid, b in sorted(benchmarks(root).items()):
        repo, ds = github_repo(b), hf_dataset(b)
        if bid in done or not (repo or ds):
            continue
        lines.append({'observed_on': today.isoformat(), 'benchmark': bid,
                      'github': github(repo, fetch, token) if repo else None,
                      'huggingface': huggingface(ds, fetch) if ds else None})
        sleep(1.0)                                                   # polite; nine requests, not a crawl
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    lines = snapshot(a.root, date.today(), token=os.environ.get('GITHUB_TOKEN') or None)
    for line in lines:
        print(json.dumps(line, sort_keys=True))
    if lines and not a.dry_run:
        with open(os.path.join(a.root, COUNTERS), 'a', encoding='utf-8', newline='\n') as fh:
            for line in lines:
                fh.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + '\n')
    print('snapshot_adoption: %d line(s)%s' % (len(lines), ' (dry run)' if a.dry_run else ''), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
