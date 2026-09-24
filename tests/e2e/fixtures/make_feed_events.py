#!/usr/bin/env python3
"""Regenerate tests/e2e/fixtures/feed-events.json, the events the feed e2e test builds against.

    python tests/e2e/fixtures/make_feed_events.py

The live repository cannot serve the e2e test: its only entries are Phase-0 drafts, which are not
publishable, so every feed would be empty and nothing would be tested. This script writes a
synthetic history into a temporary git repository -- every V8 event type, two domain families, two
organisations, one machine-ingested claim and one still-unverified draft -- and runs the real
tools/build/feed.py over it, so the fixture is feed.py's output rather than a hand-written guess.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feed-events.json')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'build'))
import feed  # noqa: E402


def bench(bid, family, org, lifecycle='active', status='primary-source-verified', licence='MIT', maint='actively-maintained'):
    return textwrap.dedent(f"""\
        id: {bid}
        name: {bid}
        domain: {{primary: {family}/x, secondary: []}}
        capability: [planning]
        evaluation_method: [execution-tests]
        designed_for_subjects: [agent-scaffold]
        lifecycle: {lifecycle}
        maintenance_status: {maint}
        liveness: {{last_checked: 2026-04-10}}
        data: {{access: fully-open}}
        license: {licence}
        governance: {{maintainers: [{org}]}}
        curation:
          added_on: 2026-01-0{2 if family == 'code' else 3}
          verification_status: {status}
        """)


def main():
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GIT_AUTHOR_NAME='fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                   GIT_COMMITTER_NAME='fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')

        def git(*args, when=None):
            e = dict(env, **({'GIT_AUTHOR_DATE': when, 'GIT_COMMITTER_DATE': when} if when else {}))
            subprocess.run(['git', '-C', d, *args], check=True, capture_output=True, env=e)

        def put(path, text):
            p = os.path.join(d, path)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            git('add', path)

        git('init', '-q', '-b', 'main')
        code, robo = 'data/benchmarks/code/alpha-bench.yaml', 'data/benchmarks/robotics-embodiment/beta-arena.yaml'
        put(code, bench('alpha-bench', 'code', 'org-alpha-lab'))
        put(robo, bench('beta-arena', 'robotics-embodiment', 'org-beta-lab'))
        put('data/benchmarks/code/draft-bench.yaml', bench('draft-bench', 'code', 'org-alpha-lab',
                                                           status='ai-drafted-unverified'))
        put('data/sources/2026/src-beta-leaderboard.yaml',
            'id: src-beta-leaderboard\ncited_by: [beta-arena]\nlink_status: live\n')
        git('commit', '-q', '-m', 'add two benchmarks, a draft and a source', when='2026-03-01T10:00:00Z')
        put('data/claims/alpha-bench/claim-hand-0001.yaml',
            'id: claim-hand-0001\nbenchmark: alpha-bench@v1\nreported_by: org-alpha-lab\ndate_reported: 2026-02-20\n')
        put('data/claims/_ingested/epoch/alpha-bench/claim-bulk-0001.yaml',
            'id: claim-bulk-0001\nbenchmark: alpha-bench@v1\nreported_by: org-gamma-lab\ndate_reported: 2026-02-25\n')
        git('commit', '-q', '-m', 'claims: one curated, one machine-ingested', when='2026-03-05T10:00:00Z')
        put(code, bench('alpha-bench', 'code', 'org-alpha-lab', licence='Apache-2.0'))
        git('commit', '-q', '-m', 'fix(alpha-bench): licence was misread', when='2026-03-10T10:00:00Z')
        put(robo, bench('beta-arena', 'robotics-embodiment', 'org-beta-lab', lifecycle='superseded'))
        git('commit', '-q', '-m', 'beta-arena superseded', when='2026-03-12T10:00:00Z')
        put(robo, bench('beta-arena', 'robotics-embodiment', 'org-beta-lab', lifecycle='superseded', maint='stale'))
        git('commit', '-q', '-m', 'probe verdict', when='2026-04-12T03:31:00Z')
        put('data/sources/2026/src-beta-leaderboard.yaml',
            'id: src-beta-leaderboard\ncited_by: [beta-arena]\nlink_status: dead\nlink_checked_at: 2026-05-01T08:07:00Z\n')
        git('commit', '-q', '-m', 'linkrot sweep', when='2026-05-02T08:07:00Z')
        put(code, bench('alpha-bench', 'code', 'org-alpha-lab', licence='Apache-2.0').replace(
            'capability: [planning]', 'capability: [planning, tool-use]'))
        git('commit', '-q', '-m', 'alpha-bench: add tool-use', when='2026-05-10T10:00:00Z')
        events = feed.derive(d)
    for e in events:  # the temporary repository's hashes mean nothing outside it
        e['commit'] = 'fixture'
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print('wrote %s: %d events, types %s' % (os.path.relpath(OUT, ROOT), len(events),
                                            sorted({e['type'] for e in events})))
    return 0


if __name__ == '__main__':
    sys.exit(main())
