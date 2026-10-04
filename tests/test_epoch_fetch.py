"""Tests for ingest/adapters/epoch.py's conditional bundle fetch (P3-S1-T03; 07 S2.2).

The verify: "A 304 returns None without parsing, the sha256 and byte count are recorded, and the whole
test runs with no network." Every test here runs against tests/fixtures/epoch/ (a synthetic bundle,
tests/fixtures/epoch/make_fixture.py) with sockets disabled. The last test reads the real snapshot in
epochdl/ when it is present and skips where it is not (00 S8.1).
"""
import glob
import hashlib
import io
import json
import os
import socket
import sys
import zipfile
from datetime import datetime, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import epoch  # noqa: E402
from ingest.http.backoff import Response  # noqa: E402
from ingest.http.fixture import FixtureTransport  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
ZIP = os.path.join(FIX, 'benchmark_data.zip')
META = json.load(open(ZIP + '.headers.json', encoding='utf-8'))
NOW = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
EPOCHDL = os.path.join(ROOT, 'epochdl')


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def fetch(transport, state):
    return epoch.fetch_bundle(transport, state, now=lambda: NOW)


def test_a_first_fetch_records_the_etag_and_the_snapshot_handle():
    t, state = FixtureTransport(FIX), {}
    bundle = fetch(t, state)
    body = open(ZIP, 'rb').read()
    assert bundle.sha256 == hashlib.sha256(body).hexdigest() == META['body_sha256']
    assert bundle.bytes == len(body) == META['body_bytes']
    assert state['etags'][epoch.ZIP_URL] == bundle.etag == '"f1x7ure0e7a9000000000000000000a1"'
    assert state['snapshot'] == {'name': 'Epoch AI -- Capabilities & Benchmarking', 'url': epoch.ZIP_URL,
                                 'retrieved_at': '2026-10-04T12:00:00Z', 'http_etag': bundle.etag,
                                 'artefact_sha256': bundle.sha256, 'artefact_bytes': bundle.bytes}
    assert state['last_status'] == 200
    assert t.requests == [(epoch.ZIP_URL, {})]          # nothing to condition on yet


def test_a_304_returns_none_without_parsing(monkeypatch):
    t, state = FixtureTransport(FIX), {}
    first = fetch(t, state)

    def never(*a, **k):
        raise AssertionError('a 304 must not be parsed')
    monkeypatch.setattr(epoch, 'ZipBundle', never)
    assert fetch(t, state) is None
    assert t.requests[-1] == (epoch.ZIP_URL, {'If-None-Match': first.etag})
    assert state['last_status'] == 304
    assert state['snapshot']['artefact_sha256'] == first.sha256    # the last 200's handle is kept


def test_only_if_none_match_is_ever_sent():
    # 07 S2.2: Epoch serves no Last-Modified, so If-Modified-Since would condition on nothing
    t, state = FixtureTransport(FIX), {}
    for _ in range(3):
        fetch(t, state)
    sent = {k.lower() for _, headers in t.requests for k in headers}
    assert sent == {'if-none-match'}


def test_a_changed_etag_fetches_the_bundle_again():
    t, state = FixtureTransport(FIX), {'etags': {epoch.ZIP_URL: '"an-older-etag"'}}
    bundle = fetch(t, state)
    assert bundle is not None and state['etags'][epoch.ZIP_URL] == bundle.etag


class Answer:
    def __init__(self, response):
        self.response = response

    def get(self, url, headers):
        return self.response


def test_a_200_without_an_etag_forgets_the_old_one():
    body = open(ZIP, 'rb').read()
    state = {'etags': {epoch.ZIP_URL: '"stale"'}}
    bundle = fetch(Answer(Response(200, [('Content-Type', 'application/zip')], body)), state)
    assert bundle.etag is None and epoch.ZIP_URL not in state['etags']
    assert state['snapshot']['http_etag'] is None


@pytest.mark.parametrize('status', [403, 404, 500])
def test_any_other_status_is_an_error_and_records_nothing(status):
    state = {}
    with pytest.raises(epoch.FetchError, match='HTTP %d' % status):
        fetch(Answer(Response(status, [], b'')), state)
    assert 'snapshot' not in state and state['last_status'] == status


def test_bytes_that_are_not_a_zip_are_refused():
    with pytest.raises(epoch.BundleError, match='not a ZIP'):
        epoch.ZipBundle(b'<html>a challenge page</html>')


def test_the_snapshot_is_an_ingest_batch_source_block():
    from schema.entities import BatchSource
    bundle = fetch(FixtureTransport(FIX), {})
    src = BatchSource.model_validate(bundle.snapshot(NOW))
    assert (src.artefact_sha256, src.artefact_bytes, src.http_etag) == (bundle.sha256, bundle.bytes, bundle.etag)


def test_the_bundle_reads_its_files_as_the_source_wrote_them():
    b = fetch(FixtureTransport(FIX), {})
    assert b.names() == ['README.md', 'benchmark_metadata.csv', 'epoch_capabilities_index/eci_scores.csv',
                         'example_bench.csv', 'example_orphan_external.csv', 'model_metadata.csv']
    assert b.per_benchmark_csvs() == ['example_bench', 'example_orphan_external']   # the orphan included
    headers, rows = b.read_csv('benchmark_metadata.csv')
    assert headers[:3] == ['benchmark', 'in_eci', 'source_file'] and len(rows) == 2
    assert rows[1]['source_file'] == '' and rows[1]['scale'] == ''    # empty stays empty: never defaulted
    with pytest.raises(epoch.BundleError, match='not in the bundle'):
        b.read_text('missing.csv')


def test_a_cell_that_is_not_utf8_is_an_error_not_a_guess():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('bad.csv', b'Model,Score \xb1 SE\nm,1\n')
    with pytest.raises(UnicodeDecodeError):
        epoch.ZipBundle(buf.getvalue()).read_csv('bad.csv')


def test_the_cli_runs_offline_and_writes_its_state(tmp_path, capsys):
    state = str(tmp_path / 'epoch.json')
    assert epoch.main(['--fixture', FIX, '--state', state]) == 0
    assert '%d bytes' % META['body_bytes'] in capsys.readouterr().out
    assert epoch.main(['--fixture', FIX, '--state', state]) == 0
    out = capsys.readouterr().out
    assert '304' in out and 'nothing parsed' in out
    assert json.load(open(state, encoding='utf-8'))['last_status'] == 304


def test_the_fixture_is_what_its_generator_builds(tmp_path, monkeypatch):
    sys.path.insert(0, FIX)
    import make_fixture
    monkeypatch.setattr(make_fixture, 'ZIP', str(tmp_path / 'benchmark_data.zip'))
    assert make_fixture.build()['body_sha256'] == META['body_sha256']


@pytest.mark.skipif(not glob.glob(os.path.join(EPOCHDL, '*.csv')), reason='epochdl/ is not in the working tree (00 S8.1)')
def test_the_real_snapshot_reads_as_07_s2_counts_it():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(glob.glob(os.path.join(EPOCHDL, '**', '*'), recursive=True)):
            if os.path.isfile(path):
                z.write(path, os.path.relpath(path, EPOCHDL).replace(os.sep, '/'))
    b = epoch.ZipBundle(buf.getvalue())
    assert len(b.names()) == 87                                    # "87 entries"
    assert len(b.per_benchmark_csvs()) == 80                       # "across 80 per-benchmark CSVs"
    assert len(b.read_csv('benchmark_metadata.csv')[1]) == 81      # "it yields 81 benchmarks"
