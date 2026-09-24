"""Parse smoke test over the frozen HuggingFace Hub fixtures (P5-S1-T02; 06 S3.2, 07 S1.2).

Offline by construction: nothing here touches the network. Each fixture is a body exactly as the
Hub returned it plus <name>.headers.json (scripts/capture_hf_fixtures.py). The tests assert the
key set 06 S3.2's mapping table reads, and 06 S3.2's "When it breaks" rule: a zero-row listing, or
a record missing a key the adapter maps, is schema drift and must fail loudly -- never be read as
an empty result.
"""
import hashlib
import json
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, 'fixtures', 'hf-hub')

ENDPOINTS = {  # 06 S3.2's endpoint list
    'spaces-leaderboard.json': 'https://huggingface.co/api/spaces?filter=leaderboard&limit=1000',
    'datasets-benchmark-official.json': 'https://huggingface.co/api/datasets?filter=benchmark:official',
    'dataset-detail.json': 'https://huggingface.co/api/datasets/openai/gsm8k?full=true',
    'croissant.jsonld': 'https://huggingface.co/api/datasets/openai/gsm8k/croissant',
}
# Keys 06 S3.2's mapping table reads, per payload kind.
SPACE_KEYS = {'id', 'tags', 'likes', 'createdAt'}
DATASET_KEYS = {'id', 'tags', 'gated', 'disabled', 'downloads', 'likes', 'lastModified'}
# paperswithcode_id is OPTIONAL: 1 of the 47 benchmark:official records carries it (captured
# 2026-09-24), so the adapter reads it when present and must not require it.
DETAIL_KEYS = DATASET_KEYS | {'cardData', 'siblings', 'paperswithcode_id'}
CROISSANT_KEYS = {'@context', '@type', 'conformsTo', 'distribution', 'recordSet', 'license', 'url'}
SPACE_NAMESPACES = {'test', 'submission', 'judge', 'eval', 'modality', 'language', 'domain'}


class SchemaDrift(Exception):
    pass


def check_listing(records, required, what):
    """What the adapter must assert before trusting a listing (06 S3.2, "When it breaks")."""
    if not isinstance(records, list) or not records:
        raise SchemaDrift('%s returned zero rows: schema drift, not an empty result' % what)
    for r in records:
        missing = required - set(r)
        if missing:
            raise SchemaDrift('%s record %s lacks %s' % (what, r.get('id'), sorted(missing)))
    return records


def body(name):
    with open(os.path.join(FIX, name), 'rb') as f:
        return json.loads(f.read().decode('utf-8'))


def meta(name):
    with open(os.path.join(FIX, name + '.headers.json'), encoding='utf-8') as f:
        return json.load(f)


def header(name, key):
    vals = [v for k, v in meta(name)['headers'] if k.lower() == key.lower()]
    return vals[0] if vals else None


@pytest.mark.parametrize('name', sorted(ENDPOINTS))
def test_every_fixture_is_a_recorded_200_from_its_endpoint(name):
    m = meta(name)
    assert (m['url'], m['method'], m['status']) == (ENDPOINTS[name], 'GET', 200)
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', m['fetched_at'])
    assert header(name, 'Content-Type').startswith('application/json')
    assert header(name, 'ETag')  # what a conditional re-fetch keys on
    with open(os.path.join(FIX, name), 'rb') as f:
        raw = f.read()
    # "Strip nothing": the committed body is the captured body, byte for byte.
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (m['body_bytes'], m['body_sha256'])
    body(name)  # parses


@pytest.mark.parametrize('name', sorted(ENDPOINTS))
def test_rate_limit_headers_follow_the_ietf_draft(name):
    # 06 S3.2: RateLimit / RateLimit-Policy per draft-ietf-httpapi-ratelimit-headers.
    policy = header(name, 'RateLimit-Policy')
    limit = header(name, 'RateLimit')
    assert re.search(r'\bq=\d+', policy) and re.search(r'\bw=\d+', policy), policy
    assert re.search(r'\br=\d+', limit) and re.search(r'\bt=\d+', limit), limit


def test_spaces_listing_key_set_and_pagination():
    spaces = check_listing(body('spaces-leaderboard.json'), SPACE_KEYS, 'spaces?filter=leaderboard')
    assert len(spaces) == 1000  # limit=1000 works (06 S3.2 [M]) and the listing continues:
    assert re.search(r'<https://huggingface\.co/api/spaces\?[^>]*cursor=[^>]+>;\s*rel="next"',
                     header('spaces-leaderboard.json', 'Link'))


def test_spaces_carry_the_tag_namespaces_06_maps():
    spaces = body('spaces-leaderboard.json')
    seen = {t.split(':', 1)[0] for s in spaces for t in s['tags'] if ':' in t}
    assert SPACE_NAMESPACES <= seen
    with_test = sum(1 for s in spaces if any(t.startswith('test:') for t in s['tags']))
    # 06 S3.2 measured 128 of 1,000 (12.8%); these tags are sparse hints, never ground truth.
    assert 100 <= with_test <= 160, with_test
    langs = {t for s in spaces for t in s['tags'] if t.lower() == 'language:english'}
    assert langs == {'language:english', 'language:English'}  # why normalisation is mandatory


def test_benchmark_official_listing_key_set():
    ds = check_listing(body('datasets-benchmark-official.json'), DATASET_KEYS, 'datasets?filter=benchmark:official')
    assert len(ds) == 47  # 06 S3.2 [M]
    assert any(d['gated'] for d in ds)  # gated is a real access class and must be modelled
    pwc = [d['paperswithcode_id'] for d in ds if 'paperswithcode_id' in d]
    assert pwc and all(isinstance(x, str) and x for x in pwc)  # optional, but a real join key when set


def test_dataset_detail_key_set():
    d = body('dataset-detail.json')
    check_listing([d], DETAIL_KEYS, 'datasets/openai/gsm8k?full=true')
    tags = set(d['tags'])
    assert any(t.startswith('license:') for t in tags) and any(t.startswith('arxiv:') for t in tags)
    assert isinstance(d['siblings'], list)  # present, and dropped by the adapter (06 S3.2)


def test_croissant_is_a_croissant_dataset():
    c = body('croissant.jsonld')
    check_listing([c], CROISSANT_KEYS, 'croissant')
    assert c['@type'] == 'sc:Dataset'
    assert 'mlcommons.org/croissant' in c['conformsTo']


# ---- the failure case: schema drift fails loudly ----------------------------------------------

def test_a_zero_row_listing_is_schema_drift_not_an_empty_result():
    with pytest.raises(SchemaDrift, match='zero rows'):
        check_listing([], DATASET_KEYS, 'datasets?filter=benchmark:official')


def test_a_renamed_key_is_schema_drift():
    renamed = [dict(r) for r in body('datasets-benchmark-official.json')]
    renamed[0]['gatedStatus'] = renamed[0].pop('gated')
    with pytest.raises(SchemaDrift, match="lacks \\['gated'\\]"):
        check_listing(renamed, DATASET_KEYS, 'datasets?filter=benchmark:official')
