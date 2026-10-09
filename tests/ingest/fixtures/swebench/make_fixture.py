#!/usr/bin/env python3
"""Generate the synthetic SWE-bench leaderboard page the adapter's tests read (P5-S6-T03).

    python tests/ingest/fixtures/swebench/make_fixture.py        # rewrites page.html and its headers

Why synthetic. The real page's footer reads "All rights reserved" and src-swebench-leaderboard classes it
no-redistribution (04 S9), so a capture of it may not be committed, not even as a test fixture. This page has
the real page's shape and none of its content: five leaderboards of 13, 24, 180, 84 and 22 results (06 S3.7's
count of 323, which the live page still held on 2026-10-09); every key the real results carry, with the same
mix of types (agent_org null on a third of rows, `checked` true, false, null or the string "false (See
README.md ...)", cost and instance_calls null on most, s3://, relative, false and null log links); and the
inline `<script id="leaderboard-data">` with rotating logo paths around it. Every name, organisation, date,
score and folder is invented. The output is deterministic: the tests regenerate it and compare bytes.
"""
from __future__ import annotations

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = (('Multilingual', 13), ('Test', 24), ('Verified', 180), ('Lite', 84), ('Multimodal', 22))
LAST_MODIFIED = 'Tue, 01 Sep 2026 02:54:51 GMT'
NOT_VERIFIED = 'false (See README.md for info on how to get your results verified)'


def _row(rng: random.Random, board: str, i: int) -> dict:
    agent = 'Example Agent %02d' % rng.randrange(1, 40)
    model = 'Model %s' % rng.choice('ABCDEFGHJK')
    folder = '2026%02d%02d_%s_%s_%03d' % (rng.randrange(1, 10), rng.randrange(1, 29), agent.lower().replace(' ', '-'),
                                          model.lower().replace(' ', '-'), i)
    s3 = 's3://swe-bench-submissions/%s/%s/' % (board.lower(), folder)
    mini = rng.random() < 0.2
    row = {
        'agent': agent,
        'agent_org': None if rng.random() < 0.33 else 'Example Lab %d' % rng.randrange(1, 12),
        'checked': rng.choice([True, False, False, None, NOT_VERIFIED]),
        'cost': round(rng.uniform(20, 400), 8) if mini else None,
        'date': '2026-%02d-%02d' % (rng.randrange(1, 10), rng.randrange(1, 29)),
        'folder': folder,
        'instance_calls': round(rng.uniform(10, 60), 6) if mini else None,
        'instance_cost': round(rng.uniform(0.05, 1.2), 8) if mini else None,
        'logo': None if rng.random() < 0.06 else ['img/logos/%s.png' % folder],
        'logs': rng.choice([s3 + 'logs'] * 8 + [None, False]),
        'model_display': model,
        'model_org': None if mini else 'Example Model Org %d' % rng.randrange(1, 6),
        'model_release_date': 20260000 + rng.randrange(101, 928) if mini else None,
        'name': '%s + %s' % (agent, model),
        'os_model': rng.random() < 0.3,
        'os_system': rng.random() < 0.5,
        'reasoning_effort': rng.choice([None] * 15 + ['high', 'medium']),
        'resolved': round(rng.uniform(0.2, 80.0), 2),
        'site': None if rng.random() < 0.07 else 'https://example.org/%s' % folder,
        'tags': ['Model: %s' % model.lower().replace(' ', '-'), 'System: Attempts - 1'],
        'trajs': rng.choice([s3 + 'trajs'] * 7 + [None, False, 'evaluation/%s/%s/trajs' % (board.lower(), folder)]),
        'trajs_docent': False,
        'warning': None,
    }
    if mini:
        row['mini-swe-agent_version'] = rng.choice(['1.0.0', '2.0.0'])
        row['per_instance_details'] = {'example__repo-%d' % k: {'api_calls': rng.randrange(5, 80),
                                                               'cost': round(rng.uniform(0.01, 2), 8),
                                                               'resolved': rng.random() < 0.5} for k in range(3)}
    return row


# The first rows of Verified are fixed, so the tests can name each case the adapter must handle.
PINNED = [
    {'agent': 'Pinned Agent', 'agent_org': 'Example Lab 1', 'checked': True, 'cost': 123.456789, 'date': '2026-03-01',
     'folder': '20260301_pinned-agent_model-a', 'instance_calls': 28.853333, 'instance_cost': 0.246914,
     'logo': ['img/logos/20260301_pinned-agent_model-a.png'],
     'logs': 's3://swe-bench-submissions/verified/20260301_pinned-agent_model-a/logs', 'model_display': 'Model A',
     'model_org': 'Example Model Org 1', 'model_release_date': None, 'name': 'Pinned Agent + Model A',
     'os_model': False, 'os_system': True, 'reasoning_effort': 'high', 'resolved': 61.4,
     'site': 'https://example.org/pinned', 'tags': ['Model: model-a', 'Org: Example Lab 1'],
     'trajs': 's3://swe-bench-submissions/verified/20260301_pinned-agent_model-a/trajs', 'trajs_docent': False,
     'warning': 'Uses a repository-level hint file; see the submission README.'},
    {'agent': 'Pinned Agent', 'agent_org': None, 'checked': NOT_VERIFIED, 'cost': None, 'date': '2026-03-02',
     'folder': '20260302_pinned-agent_model-b', 'instance_calls': None, 'instance_cost': None, 'logo': None,
     'logs': None, 'model_display': 'Model B', 'model_org': None, 'model_release_date': None,
     'name': 'Pinned Agent + Model B', 'os_model': True, 'os_system': True, 'reasoning_effort': None,
     'resolved': 40.0, 'site': None, 'tags': [], 'trajs': None, 'trajs_docent': False, 'warning': None},
    {'agent': 'Second Agent', 'agent_org': 'Example Lab 2', 'checked': None, 'cost': None, 'date': '2026-03-03',
     'folder': '20260303_second-agent_model-a', 'instance_calls': None, 'instance_cost': None,
     'logo': ['img/logos/20260303_second-agent_model-a.png'], 'logs': False, 'model_display': 'Model A',
     'model_org': 'Example Model Org 1', 'model_release_date': None, 'name': 'Second Agent + Model A',
     'os_model': False, 'os_system': False, 'reasoning_effort': 'Thinking-32k', 'resolved': 55.25,
     'site': 'https://example.org/second', 'tags': ['Model: model-a'],
     'trajs': 'evaluation/verified/20260303_second-agent_model-a/trajs', 'trajs_docent': False, 'warning': None},
    {'agent': 'Second Agent', 'agent_org': 'Example Lab 2', 'checked': 'pending review', 'cost': None,
     'date': '2026-03-04', 'folder': '20260304_second-agent_model-c', 'instance_calls': None, 'instance_cost': None,
     'logo': None, 'logs': 'https://example.org/logs/second-c', 'model_display': 'Model C', 'model_org': None,
     'model_release_date': None, 'name': 'Second Agent + Model C', 'os_model': False, 'os_system': False,
     'reasoning_effort': None, 'resolved': 12.5, 'site': None, 'tags': [], 'trajs': None, 'trajs_docent': False,
     'warning': None},
]


def boards(seed: int = 20261009) -> list:
    rng = random.Random(seed)
    out = []
    for name, n in SIZES:
        rows = [dict(r) for r in PINNED] if name == 'Verified' else []
        rows += [_row(rng, name, i) for i in range(len(rows), n)]
        out.append({'name': name, 'results': rows})
    return out


def page(data: list, logo_salt: str = 'v1') -> bytes:
    """The page around the data: rotating logo paths (the volatile noise 07 S1.5 hashes past), then the script."""
    logos = '\n'.join('    <img src="img/logos/%s.png?%s" alt="">' % (r['folder'], logo_salt)
                      for b in data for r in (b.get('results') or [])[:3])   # get-default: a malformed test page
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n    <meta charset="UTF-8">\n'
            '    <title>SWE-bench Leaderboards (synthetic fixture)</title>\n</head>\n<body>\n'
            '<div id="leaderboard-container"></div>\n%s\n'
            '<script type="application/json" id="leaderboard-data">\n    %s\n</script>\n'
            '<footer>Synthetic test fixture; not SWE-bench data.</footer>\n</body>\n</html>\n'
            % (logos, json.dumps(data))).encode('utf-8')


def headers(last_modified: str = LAST_MODIFIED) -> dict:
    return {'url': 'https://www.swebench.com/', 'status': 200,
            'headers': [['Content-Type', 'text/html; charset=utf-8'], ['Last-Modified', last_modified]]}


def write(directory: str, data: list | None = None, logo_salt: str = 'v1', last_modified: str = LAST_MODIFIED) -> None:
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, 'page.html'), 'wb') as f:
        f.write(page(boards() if data is None else data, logo_salt))
    with open(os.path.join(directory, 'page.html.headers.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(headers(last_modified), f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    write(HERE)
