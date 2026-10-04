"""Record the OpenAlex responses tests/test_openalex_adapter.py replays (P4-S2-T06).

    OPENALEX_API_KEY=... python tests/fixtures/openalex/capture.py

One institutions list call per curated Organization, exactly as ingest/adapters/openalex.py makes it. Each
response is saved as <n>.json with <n>.json.headers.json naming its URL -- the URL WITHOUT the key, which the
network transport adds and the fixture transport never sees -- and keeping only Content-Type and the
X-RateLimit-* headers. OpenAlex's metadata is CC0 (06 S3.10).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from ingest.adapters import openalex  # noqa: E402


def main():
    t = openalex.NetworkTransport(openalex.key_from_env())
    for n, (org_id, name, _) in enumerate(openalex.candidates(ROOT)):
        url = openalex.institutions_url(name)
        r = t.get(url, {})
        kept = [[k, v] for k, v in r.headers if k.lower() == 'content-type' or k.lower().startswith('x-ratelimit')]
        stem = os.path.join(HERE, '%02d-%s.json' % (n, org_id))
        with open(stem, 'wb') as f:
            f.write(json.dumps(json.loads(r.body), indent=1, sort_keys=True, ensure_ascii=False).encode('utf-8') + b'\n')
        with open(stem + '.headers.json', 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'url': url, 'status': r.status, 'headers': kept}, f, indent=2)
            f.write('\n')
        print('%s: HTTP %d' % (org_id, r.status))


if __name__ == '__main__':
    main()
