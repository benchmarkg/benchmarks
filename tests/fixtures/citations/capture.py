"""Record the responses tests/test_citation_crosscheck.py replays (P4-S2-T10).

    SEMANTIC_SCHOLAR_API_KEY=... OPENALEX_API_KEY=... python tests/fixtures/citations/capture.py

For each paper below, the two lookups ingest/adapters/semantic_scholar.py makes, exactly as it makes them:
Semantic Scholar by arXiv id into semantic-scholar/, OpenAlex by DOI into openalex/. Each response is saved as
<n>.body with <n>.body.headers.json naming its URL -- without either key, which the network transports add and
the fixture transport never sees -- and keeping only Content-Type and the X-RateLimit-* headers.

The papers are chosen for the cases, not for coverage: SWE-bench (2310.06770) is OpenAlex record W4387561453,
the wrong-title, wrong-count regression case (06 S3.10); the GPT-4 report (2303.08774) is not indexed by
OpenAlex under its arXiv DOI, so its figure is single-source; the other four are papers both aggregators know.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from ingest.adapters import openalex, semantic_scholar as s2  # noqa: E402

PAPERS = ('1910.10683', '2005.14165', '2203.15556', '2303.08774', '2307.09288', '2310.06770')


def save(directory, stem, url, r):
    os.makedirs(directory, exist_ok=True)
    kept = [[k, v] for k, v in r.headers if k.lower() == 'content-type' or k.lower().startswith('x-ratelimit')]
    path = os.path.join(directory, stem + '.body')
    with open(path, 'wb') as f:
        f.write(r.body)
    with open(path + '.headers.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'url': url, 'status': r.status, 'headers': kept}, f, indent=2)
        f.write('\n')
    print('%s %s: HTTP %d' % (os.path.basename(directory), stem, r.status))


def main():
    st = s2.NetworkTransport(s2.key_from_env())
    ot = openalex.NetworkTransport(openalex.key_from_env())
    for arxiv in PAPERS:
        url = s2.paper_url(arxiv)
        save(os.path.join(HERE, 'semantic-scholar'), arxiv, url, st.get(url, {}))
        url = openalex.work_url(s2.arxiv_doi(arxiv))
        save(os.path.join(HERE, 'openalex'), arxiv, url, ot.get(url, {}))


if __name__ == '__main__':
    main()
