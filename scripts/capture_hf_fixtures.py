#!/usr/bin/env python3
"""Capture the HuggingFace Hub fixtures the hf-hub adapter is developed against (P5-S1-T02).

    python scripts/capture_hf_fixtures.py            # re-capture into tests/ingest/fixtures/hf-hub/

Four responses from the endpoints 06-sourcing-and-scraping.md S3.2 lists, frozen so the adapter
(P5-S1-T03 onward) runs offline, as 07 S1.2 requires of every adapter's --fixture mode:

    spaces-leaderboard.json          GET /api/spaces?filter=leaderboard&limit=1000   (first page)
    datasets-benchmark-official.json GET /api/datasets?filter=benchmark:official
    dataset-detail.json              GET /api/datasets/openai/gsm8k?full=true
    croissant.jsonld                 GET /api/datasets/openai/gsm8k/croissant

"Strip nothing": each body is written byte for byte as received, and beside it
<name>.headers.json records the request URL, the time, the status and every response header in
order, duplicates included -- RateLimit, RateLimit-Policy and the pagination Link header among
them -- plus the body's length and sha256, which the fixture tests re-check. openai/gsm8k is
the first dataset in the benchmark:official listing by downloads (06 S3.2).
Anonymous: no token is sent, so the fixtures show the anonymous rate-limit policy.
"""
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
UA = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
FIXTURES = [
    ('spaces-leaderboard.json', 'https://huggingface.co/api/spaces?filter=leaderboard&limit=1000'),
    ('datasets-benchmark-official.json', 'https://huggingface.co/api/datasets?filter=benchmark:official'),
    ('dataset-detail.json', 'https://huggingface.co/api/datasets/openai/gsm8k?full=true'),
    ('croissant.jsonld', 'https://huggingface.co/api/datasets/openai/gsm8k/croissant'),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, url in FIXTURES:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
        fetched_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        from ingest.http.policy import refuse
        refuse(url)                                      # # 07 S10.1: no-collect and forbidden hold for every code path
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            meta = {'url': url, 'method': 'GET', 'fetched_at': fetched_at, 'status': r.status,
                    'body_bytes': len(body), 'body_sha256': hashlib.sha256(body).hexdigest(),
                    'request_headers': {'User-Agent': UA, 'Accept': 'application/json'},
                    'headers': [[k, v] for k, v in r.headers.items()]}
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(body)
        with open(os.path.join(OUT, name + '.headers.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print('%-34s %3d %8d bytes' % (name, meta['status'], len(body)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
