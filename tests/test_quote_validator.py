"""Tests for the quote-substring validator (P0-S5-T06; tools/validate/quotes.py; 14-roadmap Phase 0).

The verify: "`pytest tests/test_quote_validator.py` passes: a matching quote is accepted, a fabricated
one nulls its field and records a reason, and the record as a whole still validates". The absent
cases -- no source, an unknown source, a source with no snapshot -- fail the same way, and tier 3's
`quote-substring` rule is exercised through `bench validate`'s own entry point. P0-S9-T04 extends
this file with the fabricated-quote fixture.
"""
import copy
import os
import socket
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import Benchmark  # noqa: E402
from schema.source import extract_sha256, normalise  # noqa: E402
from tools.validate import quotes, tiers  # noqa: E402

EXTRACT = normalise('We collect <b>2,294</b> task instances from 12 popular Python repositories. '
                    'The dev split has 225 instances.  If the patch applies and all tests pass, the issue is resolved.')
SOURCES = {'src-paper': {'id': 'src-paper', 'quote_extract': EXTRACT}}
RECORD = {
    'id': 'quoted-bench', 'name': 'Quoted Bench', 'tagline': 'A benchmark used in quote tests.',
    'domain': {'primary': 'code/repository-scale-se'},
    'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-paper', 'observed_on': '2026-09-25',
                                  'quote': '12 popular Python repositories'}],
    'evaluation_target': 'learned-system',
    'task': {'scoring': 'resolved if all tests pass', 'scoring_source': 'src-paper',
             'scoring_quote': 'If the patch applies and all tests pass'},
    'data': {'access': 'fully-open', 'size': {
        'n_items': {'value': 2294, 'unit': 'task instances', 'source': 'src-paper', 'quote': 'We collect 2,294 task instances'},
        'n_repositories': {'value': 12, 'source': 'src-paper', 'quote': 'from 12 popular Python repositories'},
        'other_splits': [{'value': 225, 'split': 'dev', 'source': 'src-paper', 'quote': 'The dev split has 225 instances.'}],
    }},
    'homepage': 'https://example.org/',
    'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25', 'sources': ['src-paper']},
}
FAKE = 'The dev split has 9,999 instances.'


def record(**at):
    """RECORD with values replaced at dotted paths (list indices as integers in the path)."""
    r = copy.deepcopy(RECORD)
    for path, value in at.items():
        *head, last = [int(p) if p.isdigit() else p for p in path.split('__')]
        node = r
        for p in head:
            node = node[p]
        node[last] = value
    return r


def valid(r) -> bool:
    Benchmark.model_validate(r)
    return True


# ---- matching -----------------------------------------------------------------------------------

def test_the_base_record_is_valid_and_every_quote_in_it_matches():
    assert valid(RECORD)
    found = quotes.find(RECORD)
    assert [(quotes.dotted(q.at), q.key, q.source) for q in found] == [
        ('learned_entrant_evidence[0]', 'quote', 'src-paper'),
        ('task', 'scoring_quote', 'src-paper'),
        ('data.size.n_items', 'quote', 'src-paper'),
        ('data.size.n_repositories', 'quote', 'src-paper'),
        ('data.size.other_splits[0]', 'quote', 'src-paper'),
    ]
    assert quotes.check(RECORD, SOURCES) == []


def test_a_matching_quote_is_accepted_and_the_record_is_untouched():
    fixed, results = quotes.apply(RECORD, SOURCES)
    assert results == [] and fixed == RECORD


@pytest.mark.parametrize('quote', [
    'we  COLLECT 2,294\n task   instances',          # case and whitespace: both sides are folded alike
    'We collect 2,294 task instances',              # the extract's <b> tags are gone from the snapshot
    'We collect <i>2,294</i> task instances',       # and a quote's tags go the same way
    'We collect 2&#44;294 task instances',          # entities decode on both sides
])
def test_quote_and_extract_are_normalised_identically(quote):
    assert quotes.check(record(data__size__n_items__quote=quote), SOURCES) == []


def test_a_quote_is_checked_against_its_own_source_before_the_mappings():
    r = record(task__scoring_source='src-other')
    sources = dict(SOURCES, **{'src-other': {'id': 'src-other', 'quote_extract': 'Nothing about patches.'}})
    [(q, why)] = quotes.check(r, sources)
    assert q.source == 'src-other' and 'src-other' in why


# ---- a fabricated quote nulls its field, records a reason, and the record still validates --------

def test_verify_a_fabricated_block_quote_removes_its_item_and_the_record_validates():
    r = record(data__size__other_splits__0__quote=FAKE)
    assert valid(r)                                                   # a fabricated quote is well-formed YAML
    fixed, [res] = quotes.apply(r, SOURCES)
    assert res.nulled == ('data', 'size', 'other_splits', 0) and 'not a substring' in res.reason
    assert fixed['data']['size']['other_splits'] == []
    assert 'data.size.other_splits[0] removed: the quote is not a substring' in fixed['curation']['notes']
    assert valid(fixed)
    assert fixed['data']['size']['n_items'] == r['data']['size']['n_items']      # nothing else is touched


def test_verify_a_fabricated_annotation_quote_nulls_the_field_it_annotates():
    fixed, [res] = quotes.apply(record(task__scoring_quote=FAKE), SOURCES)
    assert res.nulled == ('task', 'scoring')
    assert fixed['task']['scoring'] is None and 'scoring_quote' not in fixed['task']
    assert fixed['task']['scoring_source'] == 'src-paper'
    assert 'task.scoring set to null' in fixed['curation']['notes']
    assert valid(fixed)


def test_a_required_slot_nulls_the_enclosing_field_instead():
    """n_items is required in a Size, so an unquotable item count takes the size block with it."""
    fixed, [res] = quotes.apply(record(data__size__n_items__quote=FAKE), SOURCES)
    assert res.nulled == ('data', 'size')
    assert fixed['data']['size'] is None and valid(fixed)


def test_a_quote_inside_an_already_nulled_field_reports_that_field():
    r = record(data__size__n_items__quote=FAKE, data__size__n_repositories__quote=FAKE)
    fixed, results = quotes.apply(r, SOURCES)
    assert [res.nulled for res in results] == [('data', 'size'), ('data', 'size')]
    assert fixed['data']['size'] is None and valid(fixed)


def test_removals_do_not_shift_the_items_still_to_be_checked():
    good = {'value': 12, 'split': 'kept', 'source': 'src-paper', 'quote': '12 popular'}
    bad = {'value': 1, 'split': 'fabricated', 'source': 'src-paper', 'quote': FAKE}
    fixed, results = quotes.apply(record(data__size__other_splits=[bad, good, bad]), SOURCES)
    assert [res.nulled for res in results] == [('data', 'size', 'other_splits', 0), ('data', 'size', 'other_splits', 2)]
    assert fixed['data']['size']['other_splits'] == [good]


def test_a_quote_that_cannot_be_nulled_says_so_and_leaves_the_record_as_it_was():
    """learned_entrant_evidence is required with at least one row: no enclosing slot is nullable."""
    r = record(learned_entrant_evidence__0__quote=FAKE)
    fixed, [res] = quotes.apply(r, SOURCES)
    assert res.nulled is None and 'cannot be nulled' in res.reason
    assert fixed == r


def test_existing_curation_notes_are_kept():
    fixed, _ = quotes.apply(record(curation__notes='Checked the licence.', task__scoring_quote=FAKE), SOURCES)
    assert fixed['curation']['notes'].splitlines()[0] == 'Checked the licence.'
    assert fixed['curation']['notes'].splitlines()[1].startswith('quote-substring: task.scoring set to null')


def test_apply_does_not_modify_its_input():
    r = record(task__scoring_quote=FAKE)
    before = copy.deepcopy(r)
    quotes.apply(r, SOURCES)
    assert r == before


# ---- the absent cases fail rather than pass on nothing -------------------------------------------

@pytest.mark.parametrize('sources, r, expect', [
    ({'src-paper': {'id': 'src-paper', 'quote_extract': None}}, RECORD, 'has no quote_extract'),
    ({'src-paper': {'id': 'src-paper'}}, RECORD, 'has no quote_extract'),
    ({}, RECORD, 'which has no Source record'),
    (SOURCES, record(task={'scoring': 'resolved', 'scoring_quote': 'all tests pass'}), 'names no source'),
])
def test_an_absent_snapshot_or_source_fails_the_quote(sources, r, expect):
    failures = quotes.check(r, sources)
    assert failures and all(expect in why for _, why in failures)
    fixed, results = quotes.apply(r, sources)
    assert all(res.nulled is not None or 'cannot be nulled' in res.reason for res in results)


def test_the_snapshot_is_read_never_the_live_page(monkeypatch):
    """The check is file-only: with the network gone it still runs, and text that is on the page but
    not in the committed extract fails."""
    def no_network(*a, **k):
        raise AssertionError('the quote validator opened a socket')
    monkeypatch.setattr(socket, 'socket', no_network)
    monkeypatch.setattr(socket, 'create_connection', no_network)
    sources = {'src-paper': {'id': 'src-paper', 'url': 'https://example.org/', 'quote_extract': 'Only an abstract.'}}
    failures = quotes.check(RECORD, sources)
    assert len(failures) == len(quotes.find(RECORD))


# ---- tier 3 -------------------------------------------------------------------------------------

@pytest.fixture
def corpus(tmp_path):
    """A one-benchmark corpus on disk whose Source is valid at tier 1 (a DOI, so no archive needed)."""
    from ruamel.yaml import YAML
    yaml = YAML()
    root = tmp_path / 'root'
    (root / 'data' / 'benchmarks' / 'code').mkdir(parents=True)
    (root / 'data' / 'sources' / '2026').mkdir(parents=True)
    source = {'id': 'src-paper', 'type': 'paper', 'title': 'Quoted', 'url': 'https://example.org/paper',
              'doi': '10.1234/quoted', 'archive_status': 'not-required', 'content_sha256': extract_sha256(EXTRACT),
              'quote_extract': EXTRACT, 'licence_class': 'permissive-attribution', 'licence_checked_on': '2026-09-24',
              'provenance': 'primary'}
    with open(root / 'data' / 'sources' / '2026' / 'src-paper.yaml', 'w', encoding='utf-8') as fh:
        yaml.dump(source, fh)

    def write(r):
        with open(root / 'data' / 'benchmarks' / 'code' / 'quoted-bench.yaml', 'w', encoding='utf-8') as fh:
            yaml.dump(r, fh)
        return tiers.run(str(root), 'all')
    return write


def _quote_findings(report):
    return [f for f in report.findings if f.rule == 'quote-substring']


def test_tier_3_passes_a_matching_record(corpus):
    report = corpus(RECORD)
    assert report.blocking == [] and _quote_findings(report) == []


def test_tier_3_warns_on_a_draft_and_offers_the_null(corpus):
    report = corpus(record(task__scoring_quote=FAKE))
    [f] = _quote_findings(report)
    assert f.tier == 3 and f.severity == 'warning' and not f.blocks
    assert f.entity == 'quoted-bench' and f.path == 'data/benchmarks/code/quoted-bench.yaml'
    assert 'task.scoring_quote' in f.message and 'the record still validates' in f.message
    assert f.auto_fix == 'set to null task.scoring, the reason recorded in curation.notes'
    assert report.exit_code == 0


def test_tier_3_blocks_a_reviewed_record(corpus):
    report = corpus(record(task__scoring_quote=FAKE, curation__verification_status='curator-reviewed'))
    [f] = _quote_findings(report)
    assert f.blocks and 'curator-reviewed' in f.message and report.exit_code == 1


def test_tier_3_blocks_a_quote_that_cannot_be_nulled(corpus):
    [f] = _quote_findings(corpus(record(learned_entrant_evidence__0__quote=FAKE)))
    assert f.blocks and 'cannot be nulled' in f.message


def test_the_committed_entries_quotes_all_match_their_snapshots():
    report = tiers.run(ROOT, 'semantic')
    assert _quote_findings(report) == []
    corpus = tiers.corpus_of(tiers.load(ROOT), tiers._taxonomy(ROOT))
    checked = sum(len(quotes.find(b.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)))
                  for b in corpus.benchmarks.values())
    assert checked >= 100          # 102 at P0-S5-T06: the rule is not passing on an empty set
