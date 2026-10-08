"""The thirteen quality gates as one shared module (P5-S2-T05; 07 S8, S8.1, 04 S9).

The verify: `pytest tests/ingest/test_gates.py`. Done when "One pass case and one fail case per gate (26
cases) are green and a failing gate produces zero commits". The 26 are the PASS and FAIL tables below,
each run through `gates.evaluate()` exactly as an ingest run would, against the real tree: the claim
draft under test is a copy of a committed CritPt claim, re-homed under data/claims/_ingested/ with a
complete ingestion block, so every reference in it resolves and every gate has something real to read.
A further test asserts the fail table names all thirteen gates, so a gate cannot go untested by omission.
"""
import copy
import os
import shutil
from collections import Counter
from pathlib import Path

import pytest
import yaml

from ingest import gates
from ingest.adapters.base import Draft

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = 'data/claims/_ingested/epoch/critpt/claim-0000000000aa.yaml'
CREDIT = 'Epoch AI, Data on AI Benchmarking'


def _committed_claim():
    with open(os.path.join(ROOT, 'data', 'claims', 'critpt', 'claim-683480dddf58.yaml'), encoding='utf-8') as f:
        return yaml.safe_load(f)


CLAIM = dict(_committed_claim(), id='claim-0000000000aa', verification='self-reported', notes='A gate test row.')
INGESTION = {
    'batch': 'ingest-epoch-2026-10-08', 'source_adapter': 'epoch', 'adapter_version': '0.1.0',
    'source_record_id': 'critpt.csv#model_version=gpt-5&score_column=mean_score',
    'last_seen_upstream': '2026-10-08', 'source_url': 'https://epoch.ai/data/benchmark_data.zip',
    'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
    'source_attribution': CREDIT + '. Published online at epoch.ai.', 'ingested_at': '2026-10-08T06:00:00Z',
    'extraction_confidence': 1.0, 'review_state': 'machine-ingested', 'field_provenance': {},
}


@pytest.fixture(scope='module')
def stanzas(tmp_path_factory):
    """A mapping root holding a stanza for csv:critpt: any committed stanza, copied under that name."""
    root = tmp_path_factory.mktemp('mappings')
    os.makedirs(root / 'epoch')
    shutil.copy(os.path.join(ROOT, 'ingest', 'mappings', 'epoch', 'arc_agi_external.yaml'), root / 'epoch' / 'critpt.yaml')
    return str(root)


@pytest.fixture(scope='module')
def tree():
    return gates.Tree(ROOT)          # read once for the module


def claim(path=PATH, ingestion='default', **over):
    payload = copy.deepcopy(dict(CLAIM, **over))
    payload['ingestion'] = copy.deepcopy(INGESTION) if ingestion == 'default' else ingestion
    if payload['ingestion'] is None:
        del payload['ingestion']
    return Draft('claim', None, Path(path), payload, 'new', None, 1.0)


def ctx(stanzas, tree, **over):
    kw = dict(adapter='epoch', batch=INGESTION['batch'], licence_class='permissive-attribution', attribution=CREDIT,
              mappings=stanzas, tree=tree)
    kw.update(over)
    return gates.Context(**kw)


def with_ingestion(**change):
    block = copy.deepcopy(INGESTION)
    for k, v in change.items():
        if v is None:
            block.pop(k)
        else:
            block[k] = v
    return block


# ---- the 13 pass cases --------------------------------------------------------------------------------------

def test_the_reference_draft_passes_every_gate(stanzas, tree):
    v = gates.evaluate([claim()], ctx(stanzas, tree))
    assert v.status == 'green' and v.failures == [] and v.dropped == [] and len(v.passed) == 1


PASS = {
    'schema': lambda s, t: ([claim()], ctx(s, t)),
    'referential': lambda s, t: ([claim(eval_conditions=CLAIM['eval_conditions'])], ctx(s, t)),
    'provenance': lambda s, t: ([claim()], ctx(s, t)),
    'verification-ceiling': lambda s, t: ([claim(verification='maintainer-verified')], ctx(s, t)),
    'derived-field': lambda s, t: ([claim()], ctx(s, t)),
    'sanity-band': lambda s, t: ([claim(value=1.0)], ctx(s, t)),                       # the range's edge
    'metric-definition': lambda s, t: ([claim()], ctx(s, t)),
    'unit-guard': lambda s, t: ([claim()], ctx(s, t)),
    'caps': lambda s, t: ([claim(id='claim-%012x' % i) for i in range(50)], ctx(s, t)),  # the floor, exactly
    'metadata-only': lambda s, t: ([claim(notes='x' * gates.MAX_PROSE)], ctx(s, t)),
    'attribution': lambda s, t: ([claim()], ctx(s, t)),
    'licence-firewall': lambda s, t: ([claim()], ctx(s, t)),
    'round-trip': lambda s, t: ([claim(value=0.123457)], ctx(s, t)),                    # six places is exact
}


@pytest.mark.parametrize('gate', sorted(PASS))
def test_pass(gate, stanzas, tree):
    drafts, c = PASS[gate](stanzas, tree)
    v = gates.evaluate(drafts, c)
    assert v.status == 'green' and v.failures == [] and v.dropped == [], v.failures


# ---- the 13 fail cases --------------------------------------------------------------------------------------

def _no_range_metric(monkeypatch):
    from schema.metric import Metric
    with open(os.path.join(ROOT, 'data', 'metrics', 'critpt-challenge-accuracy.yaml'), encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    doc.pop('range')
    bare = Metric.model_validate(doc)
    monkeypatch.setattr(gates, '_metric', lambda metric_id, root: bare)


FAIL = {   # gate -> (drafts and context, the outcome: red | dropped | capped)
    'schema': (lambda s, t: ([claim(value='twelve point six')], ctx(s, t)), 'red'),
    'referential': (lambda s, t: ([claim(system='no-such-model')], ctx(s, t)), 'dropped'),
    'provenance': (lambda s, t: ([claim(ingestion=with_ingestion(batch=None))], ctx(s, t)), 'red'),
    'verification-ceiling': (lambda s, t: ([claim(verification='third-party-audited')], ctx(s, t)), 'red'),
    'derived-field': (lambda s, t: ([claim(headroom=0.4)], ctx(s, t)), 'red'),
    'sanity-band': (lambda s, t: ([claim(value=12.6)], ctx(s, t)), 'dropped'),          # a percentage in a 0-1 field
    'metric-definition': (lambda s, t: ([claim()], ctx(s, t)), 'red'),                  # with _no_range_metric
    'unit-guard': (lambda s, t: ([claim()], ctx(s, t, mappings=os.path.dirname(s) + '/nowhere')), 'red'),
    'caps': (lambda s, t: ([claim(id='claim-%012x' % i) for i in range(51)], ctx(s, t)), 'capped'),
    'metadata-only': (lambda s, t: ([claim(notes='x' * (gates.MAX_PROSE + 1))], ctx(s, t)), 'red'),
    'attribution': (lambda s, t: ([claim(ingestion=with_ingestion(source_attribution='Someone else'))],
                                  ctx(s, t)), 'red'),
    'licence-firewall': (lambda s, t: ([claim(ingestion=with_ingestion(licence_class='share-alike'))],
                                       ctx(s, t)), 'red'),
    'round-trip': (lambda s, t: ([claim(value=0.1234567891)], ctx(s, t)), 'red'),       # a float that would move
}


@pytest.mark.parametrize('gate', sorted(FAIL))
def test_fail(gate, stanzas, tree, monkeypatch):
    if gate == 'metric-definition':
        _no_range_metric(monkeypatch)
    make, outcome = FAIL[gate]
    drafts, c = make(stanzas, tree)
    v = gates.evaluate(drafts, c)
    if outcome == 'dropped':
        # the row is removed and becomes an Unresolved; nothing red, the rest of the run goes on
        assert v.status == 'green' and v.passed == [] and len(v.dropped) == 1 and len(v.unresolved) == 1
        assert v.unresolved[0].reason == ('no-match' if gate == 'referential' else 'unparseable')
    else:
        assert v.status == outcome and v.passed == [] and v.texts == {}
        assert gate in {f.gate for f in v.failures}, v.failures


def test_the_fail_table_covers_all_thirteen_gates():
    assert set(FAIL) == set(PASS) == set(gates.GATES) and len(gates.GATES) == 13


# ---- the done_when's second half: a failing gate produces zero commits ------------------------------------------

@pytest.mark.parametrize('gate', sorted(g for g, (_, outcome) in FAIL.items() if outcome != 'dropped'))
def test_a_failing_gate_produces_zero_commits(gate, stanzas, tree, monkeypatch):
    if gate == 'metric-definition':
        _no_range_metric(monkeypatch)
    drafts, c = FAIL[gate][0](stanzas, tree)
    calls = []
    v = gates.evaluate(drafts + [claim(id='claim-0000000000bb')], c)   # one clean draft rides along
    assert gates.commit(v, lambda drafts, texts: calls.append(drafts) or ['written']) == []
    assert calls == []                                                  # the writer was never called


def test_a_green_run_commits_exactly_the_texts_the_round_trip_approved(stanzas, tree):
    other = PATH.replace('0000000000aa', '0000000000cc')
    v = gates.evaluate([claim(), claim(other, system='no-such-model', id='claim-0000000000cc')], ctx(stanzas, tree))
    written = gates.commit(v, lambda drafts, texts: [(d.path.as_posix(), texts[d.path.as_posix()]) for d in drafts])
    assert [p for p, _ in written] == [PATH]                           # the dangling one was dropped
    assert written[0][1] == gates.round_trip(gates.document(claim()), PATH)


# ---- the parts of each gate the table does not show ---------------------------------------------------------------

def test_caps_follow_07_s8_1s_formula():
    assert gates.cap_for('claim', 28) == 50              # max(50, min(200, 7)): the floor at Phase-1 size
    assert gates.cap_for('claim', 400) == 100            # 0.25 x 400
    assert gates.cap_for('claim', 5000) == 200           # the ceiling
    assert gates.cap_for('benchmark', 1000) == 25 and gates.cap_for('metric', 0) == 5
    with pytest.raises(gates.GateError, match='no row'):
        gates.cap_for('benchmark_version', 10)


def test_allow_bulk_lifts_the_caps(stanzas, tree):
    v = gates.evaluate([claim(id='claim-%012x' % i) for i in range(51)], ctx(stanzas, tree, allow_bulk=True))
    assert v.status == 'green' and len(v.passed) == 51


@pytest.mark.parametrize('blob, name', [
    (b'PAR1\x00\x00', 'Parquet'), (b'ARROW1\x00\x00', 'Arrow'), (b'SQLite format 3\x00', 'SQLite'),
    (b'PK\x03\x04', 'ZIP'), (b'title: a yaml file\n', None),
])
def test_metadata_only_sniffs_magic_bytes_not_extensions(tmp_path, blob, name):
    import gzip
    for label, data in (('plain', blob), ('gzipped', gzip.compress(blob))):   # one layer decompressed
        p = tmp_path / ('results-%s.yaml' % label)                            # the extension lies
        p.write_bytes(data)
        assert gates.sniff(data) == name, label
        if name:
            with pytest.raises(gates.GateError, match=name):
                gates.metadata_only_files([p.name], str(tmp_path))
        else:
            gates.metadata_only_files([p.name], str(tmp_path))


def test_a_data_file_among_the_runs_files_turns_the_run_red(tmp_path, stanzas, tree):
    (tmp_path / 'x.yaml').write_bytes(b'PAR1')
    c = ctx(stanzas, tree, files=['x.yaml'])
    c.root = str(tmp_path)
    c.tree = tree
    v = gates.evaluate([], c)
    assert v.status == 'red' and v.failures[0].gate == 'metadata-only'


@pytest.mark.parametrize('cls, path, ok', [
    ('permissive-attribution', PATH, True),
    ('share-alike', PATH, False),
    ('share-alike', 'vendor/pwc-archive/claims/x/claim-0000000000aa.yaml', True),
    ('non-commercial', PATH, False), ('no-redistribution', PATH, False), ('unlicensed', PATH, False),
    ('unlicensed', 'data/_discovery/hf-hub/cand-hf-space-x.yaml', True),   # never published (06 S1.1)
])
def test_the_licence_firewall_is_04_s9s_placement_table(cls, path, ok):
    doc = {'ingestion': {'licence_class': cls}}
    if ok:
        gates.licence_firewall(doc, path, 'permissive-attribution')
    else:
        with pytest.raises(gates.GateError, match='licence-firewall'):
            gates.licence_firewall(doc, path, 'permissive-attribution')


def test_raw_retention_is_refused_for_a_source_that_may_not_keep_bodies(stanzas, tree):
    gates.raw_retention(True, 'permissive-attribution', ['ingest/raw/epoch/benchmark_data.zip'])
    with pytest.raises(gates.GateError, match='07 S4.4'):
        gates.raw_retention(False, 'unlicensed', ['ingest/raw/hf-hub/listing.json'])
    v = gates.evaluate([claim()], ctx(stanzas, tree, raw_retainable=False, licence_class='unlicensed',
                                      retain=['ingest/raw/hf-hub/listing.json']))
    assert v.status == 'red' and {f.gate for f in v.failures} == {'licence-firewall'}


def test_a_curated_draft_is_held_to_provenance_like_any_record(stanzas, tree):
    """A record a person submitted has no ingestion block (ADR-0022). This gate is the ingest one, and it
    says so: the intake path brings its own provenance check."""
    v = gates.evaluate([claim(ingestion=None)], ctx(stanzas, tree))
    assert v.status == 'red' and 'provenance' in {f.gate for f in v.failures}


def test_a_draft_at_an_unmodelled_path_is_refused(stanzas, tree):
    v = gates.evaluate([claim(path='data/surveys/x/claim-0000000000aa.yaml')], ctx(stanzas, tree))
    assert v.status == 'red' and 'schema' in {f.gate for f in v.failures}


def test_a_draft_may_resolve_against_another_draft_of_the_same_run(stanzas, tree):
    from ingest.gates import checks
    draft_src = {'id': 'src-gate-test-only', 'kind': 'dataset'}
    docs = [('data/sources/src-gate-test-only.yaml', draft_src),
            (PATH, dict(gates.document(claim()), source='src-gate-test-only'))]
    dropped = dict(checks.referential(docs, tree, INGESTION['batch']))
    assert PATH not in dropped


# ---- the real adapters' drafts ----------------------------------------------------------------------------------

def test_hf_hub_discovery_drafts_pass_the_gates_that_apply_to_them(tree):
    """A discovery candidate meets schema (06 S1.1's shape), derived-field, metadata-only, attribution and
    round-trip; it carries no references or claim value, and the firewall lets it lie in a tree that is
    never published."""
    import json
    from datetime import datetime, timezone

    from ingest.adapters import hf_hub
    from ingest.adapters.base import Candidate, Payload
    from ingest.resolve import thaw
    fix = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
    with open(os.path.join(fix, 'resolver-snapshot.json'), encoding='utf-8') as f:
        resolver = thaw(json.load(f))
    with open(os.path.join(fix, 'spaces-leaderboard.json'), encoding='utf-8') as f:
        spaces = json.load(f)[:10]                     # the leaderboard cap's floor, at 2 in the tree
    when = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    drafts = []
    for rec in spaces:
        c = Candidate('space:' + rec['id'], 'leaderboard', 'https://huggingface.co/spaces/' + rec['id'], {})
        p = Payload(c, b'', 'application/json', 200, when, None, None, hf_hub.sha256_normalised(rec), False, doc=rec)
        drafts += hf_hub.normalise(p, resolver, hf_hub.load_crosswalk())[0]
    adapter = hf_hub.HfHub(transport=None, cache=None)
    v = gates.evaluate(drafts, gates.Context.of(adapter, tree=tree))
    assert v.status == 'green' and len(v.passed) == 10, v.failures[:3]
    # and a bulk run is capped, like Epoch's first: a leaderboard takes the benchmark row (floor 10)
    many = drafts * 2
    v = gates.evaluate([Draft(d.entity_type, d.entity_id, Path('%s-%d.yaml' % (d.path.as_posix()[:-5], i)),
                              d.payload, d.change_class, d.ingestion, 1.0) for i, d in enumerate(many)],
                       gates.Context.of(adapter, tree=tree))
    assert v.status == 'capped' and 'leaderboard 20 > 10' in v.failures[0].message


def test_the_phase_3_names_are_still_exported():
    for name in ('GateError', 'unit_guard', 'metric_definition', 'band', 'sanity_band', 'check', 'history',
                 'verification_ceiling', 'provenance', 'PROVENANCE_KEYS', 'derived_fields', 'derived_field_guard'):
        assert hasattr(gates, name), name
    assert Counter(gates.GATES)['round-trip'] == 1
