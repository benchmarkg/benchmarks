"""Tests for the HuggingFace Hub adapter's normalise() (P5-S1-T04; 07 S1.1, S1.5; 06 S1.1, S3.2).

The verify: `pytest tests/ingest/test_hf_hub_normalise.py`. Done when "Drafts and Unresolved records are
emitted, and the test asserts zero facet fields were written by machine". Every Space in the committed
1,000-Space fixture and the dataset detail fixture go through normalise(); synthetic payloads cover the
cases the fixtures do not (a resolved id, an undeclared namespace, a gated or disabled dataset).
"""
import builtins
import json
import os
import random
import socket
import time
import urllib.request
from datetime import datetime, timezone

import pytest
import yaml

from ingest.adapters import hf_hub as H
from ingest.adapters.base import Candidate, Draft, Payload, Unresolved
from ingest.resolve import Index

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
WHEN = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
XWALK = H.load_crosswalk()
RESOLVERS = {'benchmark': Index.load('benchmark'), 'leaderboard': Index.load('leaderboard')}


def _json(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return json.load(f)


SPACES = _json('spaces-leaderboard.json')
DETAIL = _json('dataset-detail.json')


def space(rec):
    c = Candidate('space:' + rec['id'], 'leaderboard', 'https://huggingface.co/spaces/' + rec['id'], {})
    return Payload(c, b'', 'application/json', 200, WHEN, None, None, H.sha256_normalised(rec), False, doc=rec)


def dataset(rec):
    c = Candidate('dataset:' + rec['id'], 'benchmark', 'https://huggingface.co/datasets/' + rec['id'],
                  {'croissant_url': 'https://huggingface.co/api/datasets/%s/croissant' % rec['id']})
    return Payload(c, b'', 'application/json', 200, WHEN, None, None, H.sha256_normalised(rec), False, doc=rec)


def norm(payload):
    return H.normalise(payload, RESOLVERS, XWALK)


def synthetic_space(tags, ident='someone/some-board'):
    return space({'id': ident, 'tags': tags, 'likes': 3, 'createdAt': '2026-01-01T00:00:00.000Z'})


def synthetic_dataset(ident='someone/some-set', tags=(), gated=False, disabled=False, **extra):
    return dataset(dict({'id': ident, 'tags': list(tags), 'gated': gated, 'disabled': disabled, 'downloads': 9,
                         'likes': 1, 'lastModified': '2026-01-01T00:00:00.000Z'}, **extra))


# ---- facet fields: derived from the code and the crosswalk, never typed here --------------------------

def facet_fields():
    """Every controlled or interpretive field a machine may only ever SUGGEST: the Benchmark vocabulary
    fields, the copilot's enum and term fields, and every field the HF crosswalk points a tag at."""
    from schema.benchmark import _FIELDS
    from schema.draft import DRAFT_FIELDS
    paths = set(_FIELDS) | {p for p, kind in DRAFT_FIELDS.items() if kind in ('enum', 'terms')}
    paths |= {r['ours'].split('.', 1)[1] for r in XWALK['rows'] if r['use'] == 'suggested'}
    for ns in XWALK['namespaces'].values():
        if ns['use'] == 'suggested':
            paths |= {o.split('.', 1)[1] for o in ns['ours']}
    return paths


FACETS = facet_fields()
FACET_LEAVES = {p.split('.')[-1] for p in FACETS} | {p.split('.')[0] for p in FACETS}


def keys(doc, prefix=''):
    if isinstance(doc, dict):
        for k, v in doc.items():
            path = prefix + k
            yield path
            yield from keys(v, path + '.')
    elif isinstance(doc, list):
        for v in doc:
            yield from keys(v, prefix)


def machine_written_facets(record):
    """Facet fields anywhere in a draft record outside its `_suggested` list."""
    outside = {k: v for k, v in record.items() if k != '_suggested'}
    return [k for k in keys(outside) if k in FACETS or k.split('.')[-1] in FACET_LEAVES]


def test_the_facet_list_is_not_empty_and_covers_the_crosswalk_targets():
    assert {'domain.primary', 'capability', 'evaluation_method', 'data.access', 'lifecycle',
            'submission_process'} <= FACETS


# ---- the verify: drafts and unresolved records are emitted, and no facet is machine-written -------------

def test_verify_every_fixture_space_yields_one_draft_and_zero_machine_written_facets():
    drafts = unresolved = 0
    for rec in SPACES:
        d, u = norm(space(rec))
        assert len(d) == 1 and isinstance(d[0], Draft)
        assert machine_written_facets(d[0].payload) == [], rec['id']
        drafts, unresolved = drafts + 1, unresolved + len(u)
    assert drafts == len(SPACES) == 1000
    assert unresolved >= 1          # the Spaces we hold no Leaderboard for


def test_verify_the_dataset_detail_yields_a_draft_and_zero_machine_written_facets():
    [d], u = norm(dataset(DETAIL))
    assert machine_written_facets(d.payload) == []
    assert all(isinstance(x, Unresolved) for x in u)


def test_a_record_that_wrote_a_facet_would_be_caught():
    """The check above would fail on the failure it exists for: a facet outside `_suggested`."""
    [d], _ = norm(synthetic_space(['eval:code']))
    bad = dict(d.payload, domain={'primary': 'code/function-synthesis'})
    assert machine_written_facets(bad) == ['domain', 'domain.primary']
    assert machine_written_facets(dict(d.payload, identity=dict(d.payload['identity'], lifecycle='active'))) \
        == ['identity.lifecycle']


def test_every_draft_is_a_discovery_candidate_never_a_data_benchmarks_file():
    for rec in SPACES[:50] + [DETAIL]:
        [d], _ = norm(space(rec) if rec is not DETAIL else dataset(rec))
        assert str(d.path).replace('\\', '/').startswith('data/_discovery/hf-hub/cand-hf-')
        assert set(d.payload) == {'candidate_id', 'discovered_via', 'discovered_at', 'identity', '_suggested'}


# ---- unmatched owner/name: an Unresolved, never an entity ---------------------------------------------

def test_an_unmatched_id_is_unresolved_and_mints_nothing():
    [d], u = norm(synthetic_space([], ident='nobody/nothing-here'))
    assert d.entity_id is None and d.change_class == 'new' and d.payload['identity']['resolves_to'] is None
    [miss] = [x for x in u if x.field == 'id']
    assert (miss.reason, miss.observed, miss.source_key) == ('no-match', 'nobody/nothing-here', 'space:nobody/nothing-here')
    assert len(miss.fingerprint) == 16


def test_a_dataset_we_hold_resolves_through_external_ids_and_raises_no_unresolved():
    [d], u = norm(synthetic_dataset('princeton-nlp/SWE-bench'))
    assert d.payload['identity']['resolves_to'] == 'benchmark:swe-bench'
    assert (d.entity_id, d.change_class) == ('swe-bench', 'field-change')
    assert not [x for x in u if x.field == 'id']


def test_an_undeclared_namespace_is_reported_not_guessed():
    [d], u = norm(synthetic_space(['newns:whatever', 'eval:code']))
    assert [x.observed for x in u if x.reason == 'out-of-band'] == ['newns:whatever']
    assert [s['tag'] for s in d.payload['_suggested']] == ['eval:code']


def test_every_space_namespace_in_the_fixture_is_declared():
    for rec in SPACES:
        assert not [x for x in norm(space(rec))[1] if x.reason == 'out-of-band'], rec['id']


# ---- the crosswalk mapping ---------------------------------------------------------------------------------

def vocab():
    from schema.benchmark import _FIELDS

    def ids(name):
        with open(os.path.join(ROOT, 'taxonomy', name), encoding='utf-8') as f:
            return {t['id'] for t in yaml.safe_load(f)['terms']}
    return {'domain.primary': ids('domains.yaml'), 'capability': ids('capabilities.yaml'),
            'evaluation_method': ids('evaluation-methods.yaml'), 'data.access': set(_FIELDS['data.access']),
            'lifecycle': set(_FIELDS['lifecycle']),
            'submission_process': set(_FIELDS['governance.submission_process'])}


def test_every_suggested_candidate_is_a_real_vocabulary_term():
    v = vocab()
    payloads = [space(r) for r in SPACES] + [dataset(DETAIL), synthetic_dataset(gated='manual', disabled=True)]
    for p in payloads:
        for s in norm(p)[0][0].payload['_suggested']:
            if s['field'] in v:
                assert set(s.get('candidates', [])) <= v[s['field']], (p.candidate.source_key, s)   # get-default: a value hint has no candidates


def test_every_space_hint_carries_its_tag_source_and_the_density_caveat():
    for rec in SPACES[:200]:
        for s in norm(space(rec))[0][0].payload['_suggested']:
            assert s['source'] == 'hf_space_tag' and s['caveat'] == 'hf-tag-density' and s['density'] == 0.128
            assert s['tag'] in rec['tags'] and s['fetched_at'] == '2026-09-24T12:00:00Z'
            assert s['adapter'] == 'hf-hub' and s['adapter_version'] == H.VERSION


def test_one_tag_can_hint_at_two_fields():
    hints = norm(synthetic_space(['judge:auto']))[0][0].payload['_suggested']
    assert {s['field'] for s in hints} == {'judge_model', 'evaluation_method'}


def test_dropped_tags_leave_no_hint():
    assert norm(synthetic_space(['region:us', 'leaderboard', 'gradio', 'some-free-word']))[0][0].payload['_suggested'] == []


def test_a_listed_value_without_a_row_is_a_hint_without_candidates_for_each_field_its_namespace_names():
    hints = norm(synthetic_space(['eval:chemistry-of-cheese']))[0][0].payload['_suggested']
    want = [o.split('.', 1)[1] for o in XWALK['namespaces']['eval']['ours']]
    assert [s['field'] for s in hints] == want and len(want) == 2
    assert all(s['tag'] == 'eval:chemistry-of-cheese' and s['candidates'] == [] for s in hints)


@pytest.mark.parametrize('tags, values', [
    (['language:English'], ['English']),
    (['language:english'], ['English']),
    (['language:English, Hindi'], ['English', 'Hindi']),
    (['language:日本語'], ['Japanese']),
    (['language:code'], []),
])
def test_language_values_are_normalised(tags, values):
    hints = norm(synthetic_space(tags))[0][0].payload['_suggested']
    assert [s['value'] for s in hints] == values
    assert all(s['field'] == 'data.size.languages' for s in hints)


def test_arxiv_is_a_join_key_in_identity_never_a_suggestion():
    [d], _ = norm(synthetic_space(['arxiv:2401.00001', 'arxiv:2401.00001']))
    assert d.payload['identity']['arxiv_ids'] == ['2401.00001'] and d.payload['_suggested'] == []


# ---- the dataset side (06 S3.2) ----------------------------------------------------------------------------

def test_the_dataset_detail_carries_licence_arxiv_pwc_and_croissant_verbatim():
    [d], _ = norm(dataset(DETAIL))
    i = d.payload['identity']
    assert i['licence'] == ['mit'] and i['arxiv_ids'] == ['2110.14168'] and i['papers_with_code'] == 'gsm8k'
    assert i['croissant_url'].endswith('/openai/gsm8k/croissant')
    assert d.ingestion['source_licence'] == 'mit' and d.ingestion['licence_class'] == 'permissive-attribution'


def test_gated_and_disabled_are_suggestions_not_values():
    [d], _ = norm(synthetic_dataset(gated='manual', disabled=True))
    by = {s['field']: s for s in d.payload['_suggested']}
    assert by['data.access']['candidates'] == H.GATED_CANDIDATES and by['data.access']['observed'] == 'gated: manual'
    assert by['lifecycle']['candidates'] == H.DISABLED_CANDIDATES
    assert machine_written_facets(d.payload) == []


def test_card_prose_is_suggested_and_siblings_are_dropped():
    [d], _ = norm(dataset(DETAIL))
    assert [s['field'] for s in d.payload['_suggested']] == ['name']
    assert 'siblings' not in json.dumps(d.payload)


@pytest.mark.parametrize('licences, cls', [
    (['mit'], 'permissive-attribution'),
    (['cc-by-sa-4.0'], 'share-alike'),
    (['MIT', 'cc-by-nc-4.0'], 'non-commercial'),
    (['other'], 'unlicensed'),
    ([], 'unlicensed'),
])
def test_licence_class_is_the_most_restrictive_and_unknown_is_unlicensed(licences, cls):
    assert H.licence_class(licences) == cls


def test_no_licence_tag_is_stated_as_unstated():
    [d], _ = norm(synthetic_dataset())
    assert d.ingestion['source_licence'] == 'unstated' and d.ingestion['licence_class'] == 'unlicensed'


# ---- volatile fields (07 S1.5) -------------------------------------------------------------------------------

def test_the_volatile_fields_are_declared():
    assert {'downloads', 'likes', 'downloadsAllTime', '_id'} <= set(H.VOLATILE_FIELDS)
    assert H.HfHub.volatile_fields == H.VOLATILE_FIELDS


def test_no_counter_reaches_a_draft():
    for p in [dataset(DETAIL), space(SPACES[0])]:
        record = norm(p)[0][0].payload
        assert not set(keys(record)) & {'downloads', 'likes', 'downloadsAllTime', '_id', 'trendingScore'}


def test_a_volatile_change_does_not_change_the_draft():
    a = dict(DETAIL)
    b = dict(DETAIL, downloads=DETAIL['downloads'] + 1000, likes=DETAIL['likes'] + 5)
    da, db = norm(dataset(a))[0][0], norm(dataset(b))[0][0]
    assert da.payload == db.payload and da.ingestion == db.ingestion


# ---- purity: no clock, no network, no randomness (07 S1.1) -----------------------------------------------------

def test_normalise_takes_no_clock_no_network_no_randomness_and_reads_no_file(monkeypatch):
    payloads = [space(r) for r in SPACES[:100]] + [dataset(DETAIL)]
    before = [norm(p) for p in payloads]

    def forbidden(*a, **k):
        raise AssertionError('normalise() reached for the clock, the network, randomness or a file')

    class NoNow(datetime):
        @classmethod
        def now(cls, tz=None):
            forbidden()

        @classmethod
        def utcnow(cls):
            forbidden()

    for target, name in [(time, 'time'), (time, 'monotonic'), (time, 'perf_counter'), (random, 'random'),
                         (random, 'randint'), (random, 'choice'), (socket.socket, 'connect'),
                         (urllib.request, 'urlopen'), (builtins, 'open')]:
        monkeypatch.setattr(target, name, forbidden)
    monkeypatch.setattr(H, 'datetime', NoNow)
    after = [norm(p) for p in payloads]
    monkeypatch.undo()
    assert after == before


def test_normalise_is_deterministic():
    p = space(next(r for r in SPACES if len(r['tags']) > 5))
    assert norm(p) == norm(p)
    assert H.candidate_id('space:Org/My_Board') == 'cand-hf-space-org-my-board'


def test_a_payload_naming_another_id_is_schema_drift():
    p = space({'id': 'a/b', 'tags': [], 'likes': 0, 'createdAt': 'x'})
    wrong = Payload(Candidate('space:c/d', 'leaderboard', 'https://huggingface.co/spaces/c/d', {}), b'',
                    'application/json', 200, WHEN, None, None, 'x', False, doc=p.doc)
    with pytest.raises(H.SchemaDrift):
        norm(wrong)


# ---- end to end through the adapter, offline --------------------------------------------------------------------

def test_the_fixture_run_normalises_every_payload(tmp_path):
    adapter = H.HfHub(H.FixtureTransport(FIX), H.RequestCache(str(tmp_path / 'cache')))
    report, payloads = H.run(adapter, H.new_state())
    assert report['status'] in ('ok', 'partial') and payloads
    drafts, unresolved = [], []
    for p in payloads:
        d, u = adapter.normalise(p, RESOLVERS)
        drafts += d
        unresolved += u
    assert len(drafts) == len(payloads)
    assert all(machine_written_facets(d.payload) == [] for d in drafts)
    assert unresolved and all(isinstance(u, Unresolved) for u in unresolved)
