"""Tests for ingest/adapters/base.py, the adapter contract's data types (P3-S1-T02; 07 S1.1).

The verify: the five dataclasses are frozen, and Unresolved.fingerprint is stable across runs. There is
no assertion that the Adapter ABC is absent: P5-S1-T08 adds it to the same file (07 S11.3), and a
permanent negative assertion here would turn that task red.
"""
import dataclasses
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import base  # noqa: E402
from ingest.adapters.base import Candidate, Draft, Payload, RunReport, Unresolved  # noqa: E402

T = datetime(2026, 9, 16, 23, 14, tzinfo=timezone.utc)
CAND = Candidate('gpqa-diamond:example-model', 'claim', 'https://epoch.ai/data/benchmark_data.zip')
EXAMPLES = {
    Candidate: CAND,
    Payload: Payload(CAND, b'{}', 'application/json', 200, T, None, None, '0' * 64, False),
    Unresolved: Unresolved('gpqa-diamond:example-model', 'model', 'Example Model (high)', 'no-match'),
    Draft: Draft('claim', None, Path('data/claims/_ingested/x.yaml'), {}, 'new', {}, 1.0),
    RunReport: RunReport('epoch', '0.3.1', T, T, 'ok', {200: 1}, 1, 1, 0, {'new': 1}, 0, 0, '0' * 64, [], []),
}


@pytest.mark.parametrize('cls', list(EXAMPLES), ids=lambda c: c.__name__)
def test_the_five_dataclasses_are_frozen(cls):
    assert dataclasses.is_dataclass(cls) and cls.__dataclass_params__.frozen
    obj = EXAMPLES[cls]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, dataclasses.fields(cls)[0].name, None)


def test_the_fields_are_07_s1_1s():
    names = {cls.__name__: [f.name for f in dataclasses.fields(cls)] for cls in EXAMPLES}
    assert names['Candidate'] == ['source_key', 'kind', 'url', 'hint']
    assert names['Payload'] == ['candidate', 'body', 'content_type', 'http_status', 'fetched_at', 'etag',
                                'last_modified', 'sha256_normalised', 'from_cache', 'headers', 'rows', 'doc']
    assert names['Unresolved'] == ['source_key', 'field', 'observed', 'reason', 'suggestions', 'human_task']
    assert names['Draft'] == ['entity_type', 'entity_id', 'path', 'payload', 'change_class', 'ingestion',
                              'confidence', 'labels']
    assert names['RunReport'] == ['adapter', 'adapter_version', 'started_at', 'finished_at', 'status', 'http_codes',
                                  'candidates_seen', 'payloads_fetched', 'payloads_from_cache', 'drafts',
                                  'unresolved_new', 'unresolved_carried', 'resolver_snapshot_sha256', 'errors',
                                  'notes']


def test_default_lists_are_not_shared():
    a = Unresolved('k', 'f', 'o', 'policy')
    b = Unresolved('k', 'f', 'o', 'policy')
    a.suggestions.append(('x', 0.5))
    assert b.suggestions == []


# ---- Unresolved.fingerprint ------------------------------------------------------------------------

U = EXAMPLES[Unresolved]
WANT = hashlib.sha256(b'gpqa-diamond:example-model|model|Example Model (high)').hexdigest()[:16]


def test_the_fingerprint_is_sha256_of_key_field_observed():
    assert U.fingerprint == WANT and len(WANT) == 16


def test_the_fingerprint_reads_only_key_field_and_observed():
    # a new suggestion, a reworded task or a re-classified reason is the same item in the ledger (07 S5.4)
    other = Unresolved(U.source_key, U.field, U.observed, 'ambiguous-match', [('example-model', 0.91)],
                       'Map "Example Model (high)" to a system id.')
    assert other.fingerprint == U.fingerprint
    for changed in (dataclasses.replace(U, source_key='gpqa-diamond:other'), dataclasses.replace(U, field='org'),
                    dataclasses.replace(U, observed='Example Model (low)')):
        assert changed.fingerprint != U.fingerprint


@pytest.mark.parametrize('seed', ['0', '1', '12345'])
def test_the_fingerprint_is_the_same_in_a_fresh_interpreter(seed):
    # str hashing is salted per process; a fingerprint built on hash() would differ here
    code = ('import sys; sys.path.insert(0, %r)\n'
            'from ingest.adapters.base import Unresolved\n'
            'print(Unresolved(%r, %r, %r, "no-match").fingerprint)' % (ROOT, U.source_key, U.field, U.observed))
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True,
                         env=dict(os.environ, PYTHONHASHSEED=seed)).stdout.strip()
    assert out == WANT


def test_the_fingerprint_is_the_one_a_committed_unresolved_record_must_carry():
    from schema.entities import UnresolvedRecord
    rec = UnresolvedRecord.model_validate({
        'source_key': U.source_key, 'field': U.field, 'observed': U.observed, 'reason': U.reason,
        'human_task': 'Map it.', 'fingerprint': U.fingerprint})
    assert rec.fingerprint == U.fingerprint


def test_the_hf_hub_adapter_uses_these_types():
    from ingest.adapters import hf_hub
    assert hf_hub.Candidate is base.Candidate and hf_hub.Payload is base.Payload
