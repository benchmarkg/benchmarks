"""The arXiv triage classifier writes only triage, only under data/_discovery/ (P5-S5-T07; 06 S5.2).

The done_when: "The test asserts no schema field, no domain, no capability and no description is ever written by
the model, and nothing it emits reaches data/ outside _discovery."

The candidates are the arXiv adapter's own drafts of its recorded OAI-PMH window (tests/ingest/fixtures/arxiv/),
written into a scratch repository with a curated benchmark beside them; their abstracts go into the raw store by
sha256, as the classifier reads them. The Batches API is a fake that answers each request with the text a test
gives it, through the same submit/collect/write code a live run uses.

  - a request carries the rubric and the title and abstract only: the model the config names, no cache_control,
    no thinking, the constrained output schema;
  - a round writes triage -- label, rationale, a score marked unmeasured, the classifier, the prompt version,
    expires_at -- and leaves every other byte of the candidate, and every file outside data/_discovery/, alone;
  - the failure case: an answer that carries a domain, a capability, a description or a schema field, or a label
    off the enum, a score out of range, a cut or refused answer, or a failed result is refused whole, and the
    candidate's file is unchanged; a path outside data/_discovery/ is refused before a file is opened;
  - an abstract that does not hash to the candidate's sha256 is never classified.
"""
from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from types import SimpleNamespace as NS

import pytest
import yaml

from ingest import emit
from ingest.adapters import arxiv_oai as A
from ingest.http.fixture import FixtureTransport
from ingest.triage import classifier as C
from schema.taxonomy import read_yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'arxiv')
DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc)
CURATED = 'data/benchmarks/code/example-bench.yaml'
N = 14                      # the recorded window's new papers in cs.AI, cs.CL, cs.CV and cs.LG
GOOD = json.dumps({'label': 'likely-benchmark', 'rationale': 'The abstract says "we introduce X, a benchmark".',
                   'score': 0.87})


def abstracts() -> dict[str, str]:
    """arXiv id -> abstract, collapsed exactly as the adapter hashes it."""
    out = {}
    for name in ('set-cs-day.xml', 'set-cs-day-p2.xml'):
        with open(os.path.join(FIX, name), 'rb') as f:
            root = ET.fromstring(f.read())
        for raw in root.iter('{%s}arXivRaw' % A.NS['r']):
            out[A._text(raw, 'r:id')] = A._text(raw, 'r:abstract') or ''
    return out


@pytest.fixture
def repo(tmp_path):
    """A scratch repository: the adapter's candidates, their abstracts in the raw store, and a curated record."""
    report = A.run(A.ArxivOai(FixtureTransport(FIX), DAY, now=lambda: NOW), dict(A.new_state(), last_until=DAY.isoformat()))
    texts = abstracts()
    store = tmp_path / 'ingest' / 'raw' / 'arxiv-oai' / 'abstracts'
    store.mkdir(parents=True)
    for doc in report['documents']:
        rel = doc.pop('path')
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(emit.emit(doc, rel), encoding='utf-8', newline='\n')
        text = texts[doc['identity']['arxiv_id']]
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == doc['identity']['abstract']['sha256']
        (store / (doc['identity']['abstract']['sha256'] + '.txt')).write_text(text, encoding='utf-8', newline='')
    curated = tmp_path / CURATED
    curated.parent.mkdir(parents=True)
    curated.write_text('id: example-bench\nname: Example Bench\n', encoding='utf-8', newline='\n')
    return tmp_path, str(store)


class FakeBatches:
    """messages.batches as the SDK shapes it: create, retrieve, results (in reverse order: never positional)."""

    def __init__(self, answer):
        self.answer, self.created = answer, []

    def create(self, requests):
        self.created.append(requests)
        return NS(id='msgbatch_test', processing_status='in_progress')

    def retrieve(self, batch_id):
        return NS(id=batch_id, processing_status='ended')

    def results(self, batch_id):
        for r in reversed(self.created[-1]):
            got = self.answer(r)
            if isinstance(got, str):
                got = NS(type='succeeded', message=NS(stop_reason='end_turn', content=[NS(type='text', text=got)]))
            yield NS(custom_id=r['custom_id'], result=got)


def round_trip(root, store, answer):
    """One whole round: build, submit, wait, collect, write back. Returns (requests, report)."""
    model, (system, version) = C.model_row()['id'], C.rubric()
    cands = C.candidates(str(root))
    requests, skipped = C.build(cands, model, system, store)
    assert skipped == []
    api = NS(messages=NS(batches=FakeBatches(answer)))
    batch_id = C.submit(api, requests)
    C.wait(api, batch_id, sleep=lambda s: None)
    report = C.write_back(str(root), cands, C.collect(api, batch_id), model, version, NOW)
    return api.messages.batches.created[-1], report


def snapshot(root) -> dict[str, bytes]:
    out = {}
    for d, _, files in os.walk(root / 'data'):
        for f in files:
            p = os.path.join(d, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, root).replace(os.sep, '/')] = fh.read()
    return out


# ---- the request ---------------------------------------------------------------------------------------------

def test_a_request_is_the_rubric_and_the_title_and_abstract_only(repo):
    root, store = repo
    sent, _ = round_trip(root, store, lambda r: GOOD)
    assert len(sent) == len(C.candidates(str(root))) == N
    texts = abstracts()
    system, _ = C.rubric()
    for r in sent:
        p = r['params']
        assert sorted(p) == ['max_tokens', 'messages', 'model', 'output_config', 'system']
        assert p['model'] == 'claude-haiku-4-5' and p['system'] == system and p['max_tokens'] == C.MAX_TOKENS
        assert p['output_config'] == {'format': {'type': 'json_schema', 'schema': C.SCHEMA}}
        assert C.SCHEMA['properties']['label']['enum'] == list(C.LABELS) and C.SCHEMA['additionalProperties'] is False
        (msg,) = p['messages']
        doc = read_yaml(os.path.join(str(root), 'data', '_discovery', 'arxiv', r['custom_id'] + '.yaml'))
        assert msg == {'role': 'user', 'content': 'Title: %s\n\nAbstract: %s' % (doc['identity']['title'],
                                                                              texts[doc['identity']['arxiv_id']])}
    dump = json.dumps(sent)
    assert 'cache_control' not in dump and 'thinking' not in dump


def test_no_prompt_caching_because_the_rubric_is_under_the_models_cache_minimum():
    row = C.model_row()
    system, _ = C.rubric()
    assert row['min_cacheable_tokens'] == 4096
    assert len(system) / 3 < row['min_cacheable_tokens']        # generous: under a third of a token per character
    assert 'No prompt caching' in C.__doc__ and 'would never be read' in C.__doc__


def test_the_model_is_the_config_row_that_names_triage(tmp_path):
    assert C.model_row()['id'] == 'claude-haiku-4-5'
    bad = tmp_path / 'ai-models.yaml'
    bad.write_text('models:\n  - {id: a, status: active, used_by: [triage]}\n  - {id: b, status: active, used_by: [triage]}\n',
                   encoding='utf-8')
    with pytest.raises(C.TriageError, match='exactly one must be'):
        C.model_row(str(bad))


# ---- what a round writes -------------------------------------------------------------------------------------

def test_a_round_writes_triage_and_nothing_else(repo):
    root, store = repo
    before = snapshot(root)
    _, report = round_trip(root, store, lambda r: GOOD)
    assert report == {'written': N, 'refused': {}, 'labels': {'likely-benchmark': N}}
    after = snapshot(root)
    assert sorted(after) == sorted(before)                      # no file created, none removed
    changed = sorted(k for k in after if after[k] != before[k])
    assert changed and all(k.startswith('data/_discovery/arxiv/') for k in changed)
    assert after[CURATED] == before[CURATED]
    _, version = C.rubric()
    for rel in changed:
        new = read_yaml(os.path.join(str(root), rel))
        old = yaml.safe_load(before[rel].decode('utf-8'))
        assert {k: v for k, v in new.items() if k != 'triage'} == {k: v for k, v in old.items() if k != 'triage'}
        assert old['triage'] is None
        t = new['triage']
        assert sorted(t) == ['classifier', 'classifier_prompt_version', 'decided_at', 'expires_at', 'label',
                             'rationale', 'score', 'score_status']
        assert t['label'] == 'likely-benchmark' and t['classifier'] == 'claude-haiku-4-5'
        assert t['classifier_prompt_version'] == version and version.startswith('triage-v1+')
        assert t['score'] == 0.87 and t['score_status'].startswith('unmeasured')
        assert new['discovered_at'] == '2026-10-10T06:00:00Z' and t['expires_at'] == '2027-01-08'   # + 90 days


def test_already_triaged_candidates_are_not_sent_again(repo):
    root, store = repo
    round_trip(root, store, lambda r: GOOD)
    model, (system, _) = C.model_row()['id'], C.rubric()
    cands = C.candidates(str(root))
    assert C.build(cands, model, system, store) == ([], [])
    assert len(C.build(cands, model, system, store, again=True)[0]) == N


# ---- the failure case: the model writes nothing it was not asked for -------------------------------------------

@pytest.mark.parametrize('answer, why', [
    (json.dumps({'label': 'likely-benchmark', 'rationale': 'x', 'score': 0.9, 'domain': 'language-communication/qa'}),
     'the model writes no other field'),
    (json.dumps({'label': 'likely-benchmark', 'rationale': 'x', 'score': 0.9, 'capability': 'reasoning'}),
     'the model writes no other field'),
    (json.dumps({'label': 'likely-benchmark', 'rationale': 'x', 'score': 0.9, 'description': 'A benchmark for X.'}),
     'the model writes no other field'),
    (json.dumps({'label': 'likely-benchmark', 'rationale': 'x', 'score': 0.9, 'identity': {'name': 'X'}}),
     'the model writes no other field'),
    (json.dumps({'label': 'likely-benchmark', 'rationale': 'x'}), 'not exactly'),
    (json.dumps({'label': 'new-benchmark', 'rationale': 'x', 'score': 0.9}), 'is not one of'),
    (json.dumps({'label': 'survey', 'rationale': ' ', 'score': 0.2}), 'no rationale'),
    (json.dumps({'label': 'survey', 'rationale': 'x', 'score': 1.5}), 'not in [0, 1]'),
    (json.dumps({'label': 'survey', 'rationale': 'x', 'score': True}), 'not in [0, 1]'),
    ('{"label": "survey", "rationale": "x", "sco', 'not JSON'),
    (NS(type='succeeded', message=NS(stop_reason='max_tokens', content=[NS(type='text', text=GOOD)])), 'stop_reason max_tokens'),
    (NS(type='succeeded', message=NS(stop_reason='refusal', content=[])), 'stop_reason refusal'),
    (NS(type='errored'), 'batch result errored'),
    (NS(type='expired'), 'batch result expired'),
])
def test_an_answer_beyond_the_three_fields_is_refused_whole_and_nothing_changes(repo, answer, why):
    root, store = repo
    before = snapshot(root)
    _, report = round_trip(root, store, lambda r: answer)
    assert report['written'] == 0 and len(report['refused']) == N
    assert all(why in reason for reason in report['refused'].values()), report['refused']
    assert snapshot(root) == before


def test_one_bad_answer_spoils_only_its_own_candidate(repo):
    root, store = repo
    target = sorted(C.candidates(str(root)))[0][1]['candidate_id']
    bad = json.dumps({'label': 'likely-benchmark', 'rationale': 'x', 'score': 0.5, 'domain': 'robotics'})
    before = snapshot(root)
    _, report = round_trip(root, store, lambda r: bad if r['custom_id'] == target else GOOD)
    assert report['written'] == N - 1 and list(report['refused']) == [target]
    rel = 'data/_discovery/arxiv/%s.yaml' % target
    assert snapshot(root)[rel] == before[rel] and b'robotics' not in before[rel]


def test_nothing_is_written_outside_data_discovery(repo):
    root, _ = repo
    doc = {'candidate_id': 'cand-x', 'discovered_at': '2026-10-09T00:00:00Z', 'triage': None}
    for rel in (CURATED, 'data/claims/_ingested/x.yaml', 'data/_discovery/../benchmarks/code/x.yaml', 'evals/x.yaml'):
        before = snapshot(root)
        with pytest.raises(C.TriageError, match='outside data/_discovery/'):
            C.write(str(root), rel, C.apply(doc, json.loads(GOOD), 'm', 'v', NOW))
        assert snapshot(root) == before
    model, (system, _) = C.model_row()['id'], C.rubric()
    requests, skipped = C.build([(CURATED, dict(doc, identity={}))], model, system)
    assert requests == [] and skipped == [(CURATED, 'not under data/_discovery/')]


def test_a_long_rationale_is_cut_to_the_metadata_only_limit():
    out = C.parse(json.dumps({'label': 'unclear', 'rationale': 'word ' * 100, 'score': 0.1}))
    assert len(out['rationale']) == C.MAX_RATIONALE and out['rationale'].endswith('…')


# ---- the input -----------------------------------------------------------------------------------------------

def test_an_abstract_that_does_not_match_its_sha256_is_never_classified(repo):
    root, store = repo
    first = sorted(os.listdir(store))[0]
    with open(os.path.join(store, first), 'a', encoding='utf-8') as f:
        f.write(' (tampered)')
    model, (system, _) = C.model_row()['id'], C.rubric()
    requests, skipped = C.build(C.candidates(str(root)), model, system, store)
    assert len(requests) == N - 1 and len(skipped) == 1
    assert 'does not hash to %s' % first[:12] in skipped[0][1]
    os.remove(os.path.join(store, first))
    requests, skipped = C.build(C.candidates(str(root)), model, system, store)
    assert 'no abstract %s' % first[:12] in skipped[0][1]


def test_the_rubric_asks_the_one_question_and_declares_its_version():
    text, version = C.rubric()
    assert 'Does this paper release an evaluation artifact, or merely use one?' in text
    assert version.startswith('triage-v1+') and len(version) == len('triage-v1+') + 12
    for label in C.LABELS:
        assert '`%s`' % label in text
