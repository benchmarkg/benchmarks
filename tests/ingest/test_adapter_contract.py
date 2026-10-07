"""The extracted Adapter ABC, and adapters 1 and 2 on it (P5-S1-T08; 07 S1.1, S1.2, S11.5).

The verify: `pytest tests/ingest/`. Done when "Both adapters run on the shared contract with no change to any
fixture or golden output". The golden outputs this branch leaves untouched are pinned where they already
were: the hf-hub matrix and replay (test_hf_hub_idempotent.py), the hf-hub normaliser over 1,000 Spaces
(test_hf_hub_normalise.py), the Epoch orphan ledger's committed fingerprints (tests/test_orphan_stanzas.py)
and the bench ingest report (tests/cli/test_bench_ingest.py). This file covers the contract itself: what a
subclass must declare, what the bundle adapter guarantees, and that each adapter honours both.
"""
import builtins
import csv
import io
import os
import socket
import urllib.request
import zipfile
from datetime import datetime, timezone

import pytest

from ingest.adapters import base, epoch, hf_hub
from ingest.adapters.base import Adapter, AdapterDeclarationError, BulkArchiveAdapter, Candidate, Payload
from ingest.http.fixture import FixtureTransport

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EPOCH_FIX = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
WHEN = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def declared(**over):
    """The class attributes of a lawful adapter, with `over` changed or (as None) removed."""
    attrs = {'name': 'example', 'version': '0.1.0', 'licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
             'attribution': 'Example Source', 'expected_yield': (1, 10),
             'discover': lambda self, state: iter(()), 'fetch': lambda self, c, state: None,
             'normalise': lambda self, p, r: ([], [])}
    attrs.update(over)
    return {k: v for k, v in attrs.items() if v is not None}


# ---- the ABC: what a concrete adapter must declare (07 S1.1) --------------------------------------------------

def test_a_lawful_adapter_defines_and_instantiates():
    cls = type('Example', (Adapter,), declared())
    a = cls()
    assert isinstance(a, Adapter) and a.raw_retainable is True and a.politeness is None and dict(a.caps) == {}


@pytest.mark.parametrize('missing', base.DECLARED)
def test_an_adapter_missing_a_declaration_is_refused_when_defined(missing):
    with pytest.raises(AdapterDeclarationError, match=missing):
        type('Example', (Adapter,), declared(**{missing: None}))


def test_an_adapter_with_an_empty_licence_is_refused():
    with pytest.raises(AdapterDeclarationError, match='no licence'):
        type('Example', (Adapter,), declared(licence=''))


def test_a_licence_class_outside_the_firewall_is_refused():
    with pytest.raises(AdapterDeclarationError, match='licence_class'):
        type('Example', (Adapter,), declared(licence_class='mostly-fine'))


@pytest.mark.parametrize('cls', sorted(base.NOT_RETAINABLE))
def test_a_restricted_source_may_not_retain_its_raw_body(cls):
    """07 S4.4: raw_retainable = False for share-alike, non-commercial, no-redistribution and unlicensed."""
    with pytest.raises(AdapterDeclarationError, match='raw_retainable'):
        type('Example', (Adapter,), declared(licence_class=cls))
    type('Example', (Adapter,), declared(licence_class=cls, raw_retainable=False))


def test_an_expected_yield_that_is_not_a_band_is_refused():
    with pytest.raises(AdapterDeclarationError, match='expected_yield'):
        type('Example', (Adapter,), declared(expected_yield=(10, 1)))


def test_an_abstract_intermediate_class_is_not_checked_and_cannot_be_instantiated():
    partial = type('Partial', (Adapter,), {'discover': lambda self, s: iter(())})   # declares nothing
    with pytest.raises(TypeError):
        partial()


def test_checkpoint_and_finalise_default_to_the_in_memory_state():
    a = type('Example', (Adapter,), declared())()
    state = {}
    cursor = {'page': 3}
    a.checkpoint(state, cursor)
    cursor['page'] = 4
    assert state['checkpoint'] == {'page': 3}                 # a copy: the caller's cursor moving does not move it
    a.finalise(state, {'status': 'ok'})
    assert state['checkpoint'] is None


def test_a_curated_draft_may_carry_no_ingestion_block():
    """ADR-0022: a record a person submitted is curated, not ingested (04 S9)."""
    d = base.Draft('benchmark', None, 'data/benchmarks/x/y.yaml', {}, 'new', None, 1.0)
    assert d.ingestion is None


# ---- the bundle adapter (07 S1.2) ------------------------------------------------------------------------------

class Bundle:
    def __init__(self, records):
        self.records = records

    def payload_for(self, c):
        return Payload(c, self.records[c.source_key], 'text/plain', 200, WHEN, None, None, '0' * 64, False)


def bundle_adapter(bundle, fetched):
    def fetch_bundle(self, state):
        fetched.append(state)
        return bundle
    return type('Bundled', (BulkArchiveAdapter,), declared(
        discover=None, fetch=None, fetch_bundle=fetch_bundle,
        enumerate=lambda self, b: (Candidate(k, 'claim', None) for k in sorted(b.records))))()


def test_a_bundle_adapter_fetches_once_and_slices_the_bundle_per_candidate():
    fetched = []
    a = bundle_adapter(Bundle({'r:1': b'one', 'r:2': b'two'}), fetched)
    out = [a.fetch(c, None).body for c in a.discover({})]
    assert out == [b'one', b'two'] and len(fetched) == 1


def test_a_bundle_adapter_with_nothing_fetched_discovers_nothing():
    assert list(bundle_adapter(None, []).discover({})) == []


# ---- adapter 1: Epoch on BulkArchiveAdapter ---------------------------------------------------------------------

def test_epoch_is_a_bundle_adapter_with_07s_declarations():
    assert issubclass(epoch.Epoch, BulkArchiveAdapter)
    assert (epoch.Epoch.name, epoch.Epoch.licence, epoch.Epoch.licence_class) == ('epoch', 'CC-BY-4.0',
                                                                                    'permissive-attribution')
    assert epoch.Epoch.expected_yield == (41, 162) and epoch.Epoch.caps is epoch.CAPS
    assert epoch.Epoch.raw_retainable is True and tuple(epoch.Epoch.volatile_fields) == ()


def test_epoch_fetch_bundle_is_the_only_request_a_run_makes():
    t = FixtureTransport(EPOCH_FIX)
    a = epoch.Epoch(t, now=lambda: WHEN)
    payloads = [a.fetch(c, None) for c in a.discover({})]
    assert len(t.requests) == 1 and len(payloads) == 4
    assert [p.content_type for p in payloads] == ['application/json'] * 2 + ['text/csv'] * 2
    assert all(p.fetched_at == WHEN and p.etag == a.bundle.etag for p in payloads)


def test_epoch_a_second_discover_with_the_etag_is_a_304_and_nothing():
    t, state = FixtureTransport(EPOCH_FIX), {}
    a = epoch.Epoch(t, now=lambda: WHEN)
    list(a.discover(state))
    assert list(a.discover(state)) == [] and a.bundle is None
    assert t.requests[-1][1] == {'If-None-Match': state['etags'][epoch.ZIP_URL]}


def test_epoch_reads_its_attribution_from_the_bundle_never_from_memory():
    a = epoch.Epoch(FixtureTransport(EPOCH_FIX), now=lambda: WHEN)
    with pytest.raises(epoch.BundleError):
        _ = a.attribution
    list(a.discover({}))
    assert a.attribution == epoch.attribution(a.bundle)


def test_epoch_from_a_directory_or_a_transport_never_both():
    with pytest.raises(ValueError):
        epoch.Epoch(FixtureTransport(EPOCH_FIX), directory=EPOCH_FIX)
    with pytest.raises(epoch.FetchError):
        epoch.Epoch().fetch_bundle({})


def _zip(rows, header=('Model version', 'Score')):
    buf = io.BytesIO()
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow(header)
    w.writerows(rows)
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('b.csv', out.getvalue())
    return epoch.ZipBundle(buf.getvalue(), retrieved_at=WHEN)


def test_epoch_payload_hash_ignores_row_order_and_sees_a_changed_value():
    """07 S1.5: a regenerated export that only reorders rows is not a change; an edited score is."""
    c = Candidate('csv:b', 'claim', None, {})
    a = _zip([('m1', '0.5'), ('m2', '0.7')]).payload_for(c)
    b = _zip([('m2', '0.7'), ('m1', '0.5')]).payload_for(c)
    e = _zip([('m1', '0.5'), ('m2', '0.71')]).payload_for(c)
    assert a.sha256_normalised == b.sha256_normalised != e.sha256_normalised


def test_epoch_a_key_naming_no_record_is_an_error():
    with pytest.raises(epoch.BundleError):
        _zip([]).payload_for(Candidate('zip:b', 'claim', None, {}))


def test_epoch_normalise_is_pure_and_reads_only_the_payload(monkeypatch):
    a = epoch.Epoch(FixtureTransport(EPOCH_FIX), now=lambda: WHEN)
    payloads = [a.fetch(c, None) for c in a.discover({})]
    expected = [a.normalise(p, None) for p in payloads]
    a.bundle = None                                          # the bundle is gone: the payload must suffice

    def refuse(*x, **k):
        raise AssertionError('normalise() reached outside its arguments')
    for target, name in ((builtins, 'open'), (socket, 'create_connection'), (urllib.request, 'urlopen'),
                         (zipfile, 'ZipFile')):
        monkeypatch.setattr(target, name, refuse)
    assert [a.normalise(p, None) for p in payloads] == expected
    assert sum(len(u) for _, u in expected) == 2             # the two CSVs, each awaiting its stanza


def test_epoch_run_goes_through_the_adapter():
    with open(os.path.join(EPOCH_FIX, 'benchmark_data.zip'), 'rb') as f:
        bundle = epoch.ZipBundle(f.read())
    seen = []

    def normaliser(payload, resolver):
        seen.append((type(payload), payload.candidate.source_key, resolver))
        return [], []
    report = epoch.run(bundle, normaliser=normaliser, resolver='the resolver', now=lambda: WHEN)
    assert report['candidates_seen'] == 4 and {t for t, _, _ in seen} == {Payload}
    assert {r for _, _, r in seen} == {'the resolver'} and bundle.retrieved_at == WHEN


# ---- adapter 2: hf-hub on Adapter -------------------------------------------------------------------------------

def test_hf_hub_is_an_adapter_with_07s_declarations():
    assert issubclass(hf_hub.HfHub, Adapter) and not issubclass(hf_hub.HfHub, BulkArchiveAdapter)
    assert hf_hub.HfHub.expected_yield == (512, 2048)
    # per-record licences (06 S9.3): the adapter's own class is the conservative default, so no raw body
    assert hf_hub.HfHub.licence_class == 'unlicensed' and hf_hub.HfHub.raw_retainable is False
    assert tuple(hf_hub.HfHub.volatile_fields) == hf_hub.VOLATILE_FIELDS


def test_hf_hub_normalise_through_the_adapter_is_the_module_function():
    from ingest.resolve import Index
    rec = {'id': 'org/board', 'tags': ['leaderboard', 'judge:auto'], 'likes': 1, 'createdAt': '2026-01-01T00:00:00Z'}
    c = Candidate('space:org/board', 'leaderboard', 'https://huggingface.co/spaces/org/board', {})
    p = Payload(c, b'', 'application/json', 200, WHEN, None, None, hf_hub.sha256_normalised(rec), False, doc=rec)
    resolver = {'benchmark': Index('benchmark', []), 'leaderboard': Index('leaderboard', [])}
    a = hf_hub.HfHub(transport=None, cache=None)
    assert a.normalise(p, resolver) == hf_hub.normalise(p, resolver, hf_hub.load_crosswalk())
