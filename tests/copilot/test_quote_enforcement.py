"""Quote enforcement in the F6 copilot (P1-S2-T02; tools/copilot/draft.py; 11 S F6; 14-roadmap Phase 0).

14-roadmap: "The validator requires that `quote` be an exact substring of the archived source snapshot
for that field's source -- not the live page, the snapshot, so the check is reproducible at any commit.
A quote that does not match fails validation and the field is set to `null`." The task's steps:
validate against the archived snapshot, not the live page; null the field and never fail the whole
record; a fixture with a deliberately fabricated quote. DONE WHEN: "The fabricated-quote fixture yields
a null field and a recorded rejection, not a populated value."

tests/fixtures/swe-bench.html has canonical URL https://arxiv.org/abs/2310.06770, which
data/sources/2026/src-swebench-arxiv-abs.yaml already holds. So these drafts are quoted against that
committed snapshot, and the network is never touched: `_get` raises in every test.
"""
import copy
import datetime
import json
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.draft import BenchmarkDraft  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.copilot import draft as D  # noqa: E402
from tools.validate import quotes  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'swe-bench.html')
FABRICATED = os.path.join(ROOT, 'tests', 'fixtures', 'copilot', 'fabricated-quote.answer.json')
ARCHIVED = 'data/sources/2026/src-swebench-arxiv-abs.yaml'
TODAY = datetime.date(2026, 9, 28)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(url):
        raise AssertionError('the copilot fetched %s; an archived snapshot means no fetch' % url)
    monkeypatch.setattr(D, '_get', refuse)


def draft(tmp_path, answer=FABRICATED, url=FIXTURE, **kw):
    return D.run(url, str(tmp_path / 'drafts'), D.ReplayDrafter(answer), today=TODAY, curator='tester', **kw)


def row(bench, field, term=None):
    got = [f for f in bench['provenance']['fields'] if f['field'] == field and f.get('term') == term]
    return got[0] if got else None


def rejected(bench, field, term=None):
    return [r for r in bench['provenance']['rejected'] if r['field'] == field and r.get('term') == term]


def test_the_fabricated_quote_yields_a_null_field_and_a_recorded_rejection(tmp_path):
    r = draft(tmp_path)
    on_disk = read_yaml(r.bench_path)
    BenchmarkDraft.model_validate(on_disk)                                     # written, and valid
    assert 'size' not in on_disk.get('data', {})                               # null, not 3,000
    assert row(on_disk, 'data.size.n_items') == {
        'field': 'data.size.n_items', 'confidence': 'absent',
        'note': 'value rejected: its quote is not in the source snapshot'}
    assert rejected(on_disk, 'data.size.n_items') == [{
        'field': 'data.size.n_items', 'value': {'count': 3000, 'unit': 'task instances'},
        'claimed': 'SWE-bench consists of 3,000 task instances collected from GitHub.',
        'reason': 'its quote is not in the source snapshot', 'stage': 'vet'}]
    assert on_disk['capability'] == ['context-integration']                    # the fabricated term is gone
    assert rejected(on_disk, 'capability', 'tool-use')[0]['claimed'] == 'models must call external tools to resolve each issue'
    for kept in ('name', 'external_ids.arxiv', 'learned_entrant_evidence'):    # the truthful quotes stand
        assert row(on_disk, kept)['confidence'] == 'high'
    assert on_disk['name'] == 'SWE-bench' and on_disk['learned_entrant_evidence'][0]['system'] == 'Claude 2'


def test_a_rejection_never_carries_a_quote_the_substring_check_would_read(tmp_path):
    r = draft(tmp_path)
    assert all('quote' not in rj for rj in r.bench['provenance']['rejected'])
    source = read_yaml(os.path.join(ROOT, ARCHIVED))
    assert quotes.check(read_yaml(r.bench_path), {source['id']: source}) == []


def test_quotes_are_checked_against_the_archived_snapshot_not_the_live_page(tmp_path):
    r = draft(tmp_path)
    assert r.archived and r.source_path == os.path.join(ROOT, ARCHIVED)
    assert r.bench['curation']['sources'] == ['src-swebench-arxiv-abs']
    assert 'committed snapshot of src-swebench-arxiv-abs' in r.bench['curation']['notes']
    assert not os.path.exists(tmp_path / 'drafts' / 'sources')                # no second snapshot written
    # The homepage's quote is on the live page, as the copilot renders it, but not in the archived snapshot.
    assert rejected(r.bench, 'homepage')[0]['reason'] == 'its quote is not in the source snapshot'
    assert 'homepage' not in r.bench
    live = draft(tmp_path / 'live', fresh=True)
    assert live.bench['homepage'] == 'https://www.swebench.com' and not live.archived


def test_an_arxiv_url_held_in_data_is_drafted_without_fetching_it(tmp_path):
    r = draft(tmp_path, url='https://arxiv.org/pdf/2310.06770v3')             # _get raises if called
    assert r.archived and r.bench['provenance']['source_urls'] == ['https://arxiv.org/abs/2310.06770']


def test_a_held_source_with_no_extract_is_cited_not_quoted_so_a_new_snapshot_is_taken(tmp_path, monkeypatch):
    rec = read_yaml(os.path.join(ROOT, ARCHIVED))
    del rec['quote_extract']
    monkeypatch.setattr(D, 'archived_source', lambda url, root=D.ROOT: (ARCHIVED, rec))
    r = draft(tmp_path)
    assert not r.archived and r.bench['curation']['sources'] == ['src-arxiv-2310-06770']
    assert 'with no quote_extract' in r.bench['curation']['notes']


def test_a_quote_the_stored_source_lacks_nulls_that_field_and_only_that_field(tmp_path):
    r = draft(tmp_path, fresh=True)
    bench, source = copy.deepcopy(r.bench), copy.deepcopy(r.source)
    source['quote_extract'] = source['quote_extract'].replace('Claude 2', 'Claude Two')
    added = D.enforce(bench, {source['id']: source})
    assert [(a['field'], a['value'], a['stage']) for a in added] == [('learned_entrant_evidence', 'Claude 2', 'snapshot')]
    assert 'learned_entrant_evidence' not in bench
    assert row(bench, 'learned_entrant_evidence')['confidence'] == 'absent'
    assert bench['name'] == 'SWE-bench' and row(bench, 'name')['confidence'] == 'high'
    assert [f['field'] for f in bench['provenance']['fields']] == [f['field'] for f in r.bench['provenance']['fields']]
    assert quotes.check(bench, {source['id']: source}) == []
    BenchmarkDraft.model_validate(bench)


def test_a_term_whose_quote_the_stored_source_lacks_is_removed_alone(tmp_path):
    r = draft(tmp_path, fresh=True)
    bench, source = copy.deepcopy(r.bench), copy.deepcopy(r.source)
    source['quote_extract'] = source['quote_extract'].replace('process extremely long contexts', 'process long inputs')
    D.enforce(bench, {source['id']: source})
    assert 'capability' not in bench and row(bench, 'capability')['confidence'] == 'absent'
    assert rejected(bench, 'capability', 'context-integration')[0]['stage'] == 'snapshot'
    BenchmarkDraft.model_validate(bench)


def test_an_answer_whose_every_quote_is_fabricated_still_writes_a_record(tmp_path):
    answer = json.load(open(FABRICATED, encoding='utf-8'))
    for path, a in answer['fields'].items():
        for item in a.get('terms', [a]):
            item['quote'] = 'This sentence appears nowhere in the source.'
    path = tmp_path / 'all-fabricated.json'
    path.write_text(json.dumps(answer), encoding='utf-8')
    r = draft(tmp_path, answer=str(path), bench_id='swe-bench')
    assert r.populated == [] and os.path.exists(r.bench_path)
    assert len(r.bench['provenance']['rejected']) == 7                        # six fields, two capability terms
    BenchmarkDraft.model_validate(read_yaml(r.bench_path))


def test_the_contract_refuses_a_rejection_beside_a_value(tmp_path):
    bench = read_yaml(draft(tmp_path).bench_path)
    bad = copy.deepcopy(bench)
    bad['provenance']['rejected'].append({'field': 'name', 'value': 'SWE-bench', 'reason': 'test', 'stage': 'vet'})
    with pytest.raises(ValidationError, match='name was rejected, so its value is null'):
        BenchmarkDraft.model_validate(bad)
    bad = copy.deepcopy(bench)
    bad['provenance']['rejected'].append({'field': 'capability', 'reason': 'test', 'stage': 'vet'})
    with pytest.raises(ValidationError, match='names the term refused'):
        BenchmarkDraft.model_validate(bad)
