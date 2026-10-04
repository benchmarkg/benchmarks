"""Tests for ingest/batch.py, the IngestBatch record (P3-S1-T04; 04 S9, 07 S1.3).

The verify is `bench validate data/_ingest/batches/ --tier all`, and DONE WHEN: "A dry run writes a
batch file that validates and carries every field 04 S9 lists, including resolver_snapshot_sha256".
A dry run here writes into a temporary tree, never into data/: a batch is committed only for a run
that changed something (04 S9), and phase 0 writes no claims. Everything runs with sockets disabled.
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
from ingest import batch  # noqa: E402
from ingest.adapters import epoch  # noqa: E402
from ingest.http.fixture import FixtureTransport  # noqa: E402
from schema.entities import IngestBatch  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
META = json.load(open(os.path.join(FIX, 'benchmark_data.zip.headers.json'), encoding='utf-8'))
STARTED = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)
FETCHED = datetime(2026, 10, 4, 12, 0, 5, tzinfo=timezone.utc)
EPOCHDL = os.path.join(ROOT, 'epochdl')
needs_epoch = pytest.mark.skipif(not glob.glob(os.path.join(EPOCHDL, '*.csv')),
                                 reason='epochdl/ is not in the working tree (00 S8.1)')


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def bundle():
    return epoch.fetch_bundle(FixtureTransport(FIX), {}, now=lambda: FETCHED)


def dry_run(root):
    return batch.write(batch.epoch_batch(bundle(), STARTED, FETCHED, str(root)), str(root))


def test_a_dry_run_writes_a_batch_carrying_every_04_s9_field(tmp_path):
    rel = dry_run(tmp_path)
    assert rel == 'data/_ingest/batches/ingest-epoch-2026-10-04.yaml'
    from schema.taxonomy import read_yaml
    doc = read_yaml(str(tmp_path / rel))
    b = IngestBatch.model_validate(doc)
    assert set(IngestBatch.model_fields) - set(doc) == set()            # every field, notes included
    assert (b.source.http_etag, b.source.artefact_sha256, b.source.artefact_bytes) == (
        '"f1x7ure0e7a9000000000000000000a1"', META['body_sha256'], META['body_bytes'])
    assert b.source.retrieved_at == FETCHED and b.run_started == STARTED
    assert b.resolver_snapshot_sha256 == batch.resolver_snapshot_sha256(str(tmp_path))
    assert b.licence.spdx == 'CC-BY-4.0' and b.licence.source_record == 'src-epoch-benchmark-data'
    assert b.counts == {'files_seen': 6, 'per_benchmark_csvs': 2, 'benchmarks_seen': 2, 'model_rows_seen': 1,
                        'rows_example_bench': 2, 'rows_example_orphan_external': 1, 'claims_written': 0,
                        'unresolved': 0}
    assert b.target_tree == 'data/claims/_ingested/epoch/'


def test_the_written_file_is_already_formatted(tmp_path):
    from tools import fmt
    rel = dry_run(tmp_path)
    text = (tmp_path / rel).read_text(encoding='utf-8')
    assert fmt.format_text(text, fmt.model_for(rel), rel) == text                     # header comment kept


def test_the_batch_validates_at_every_tier_against_the_repository():
    # the verify's own check, run on a dry run's file in the repository's corpus: the licence's
    # source_record must resolve there (tier 2), which a temporary tree cannot show
    from tools.validate import tiers
    rel = 'data/_ingest/batches/ingest-epoch-2026-10-04.yaml'
    path = os.path.join(ROOT, *rel.split('/'))
    assert not os.path.exists(path), 'a committed batch would be overwritten'
    try:
        batch.write(batch.epoch_batch(bundle(), STARTED, FETCHED, ROOT), ROOT)
        report = tiers.run(ROOT, 'all', paths=[rel])
        mine = [f for f in report.findings if f.path == rel]
        assert [f for f in mine if f.severity == 'blocking'] == [], mine
    finally:
        os.remove(path)
        if not os.listdir(os.path.dirname(path)):
            os.rmdir(os.path.dirname(path))


def test_the_attribution_is_the_readmes_citation_verbatim():
    assert batch.epoch_batch(bundle(), STARTED, FETCHED, ROOT)['licence']['attribution_text'] == (
        'Example Lab, ‘Example Benchmarks’. Retrieved from ‘https://example.org/benchmarks’ '
        '[online resource].')


def test_a_readme_without_a_citation_is_an_error_not_a_remembered_string():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('README.md', '## Licensing\nCC-BY.\n')
    with pytest.raises(epoch.BundleError, match='no Citation block'):
        epoch.attribution(epoch.ZipBundle(buf.getvalue()))


# ---- resolver_snapshot_sha256 ------------------------------------------------------------------------

def table(root, name, text):
    p = root / 'data' / 'aliases' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def test_with_no_alias_tables_the_snapshot_hash_is_defined(tmp_path):
    assert batch.resolver_snapshot_sha256(str(tmp_path)) == hashlib.sha256(b'{}').hexdigest()


def test_the_snapshot_hash_follows_every_alias_table(tmp_path):
    table(tmp_path, 'systems.yaml', '- alias: GPT-4o\n  id: gpt-4o\n')
    one = batch.resolver_snapshot_sha256(str(tmp_path))
    assert one == batch.resolver_snapshot_sha256(str(tmp_path))                    # stable
    table(tmp_path, 'systems.yaml', '- alias: GPT-4o\n  id: gpt-4o-2024-05-13\n')
    two = batch.resolver_snapshot_sha256(str(tmp_path))
    table(tmp_path, 'benchmarks.yaml', '[]\n')
    three = batch.resolver_snapshot_sha256(str(tmp_path))
    assert len({one, two, three}) == 3                                               # an edit, an addition
    (tmp_path / 'data' / 'aliases' / 'benchmarks.yaml').rename(tmp_path / 'data' / 'aliases' / 'benches.yaml')
    assert batch.resolver_snapshot_sha256(str(tmp_path)) != three                    # a rename too


# ---- ids and writing --------------------------------------------------------------------------------

def test_a_second_run_the_same_day_gets_its_own_id(tmp_path):
    assert dry_run(tmp_path).endswith('ingest-epoch-2026-10-04.yaml')
    assert dry_run(tmp_path).endswith('ingest-epoch-2026-10-04-2.yaml')
    assert dry_run(tmp_path).endswith('ingest-epoch-2026-10-04-3.yaml')


def test_a_batch_file_is_never_overwritten(tmp_path):
    doc = batch.epoch_batch(bundle(), STARTED, FETCHED, str(tmp_path))
    batch.write(doc, str(tmp_path))
    with pytest.raises(FileExistsError, match='never reused'):
        batch.write(doc, str(tmp_path))


def test_a_run_that_wrote_claims_says_so():
    doc = batch.epoch_batch(bundle(), STARTED, FETCHED, ROOT, written={'claims_written': 3, 'unresolved': 1})
    assert (doc['counts']['claims_written'], doc['counts']['unresolved']) == (3, 1)


def test_the_cli_dry_run_writes_into_the_tree_it_is_given(tmp_path, capsys):
    assert batch.main(['--fixture', FIX, '--root', str(tmp_path)]) == 0
    written = glob.glob(str(tmp_path / 'data' / '_ingest' / 'batches' / '*.yaml'))
    assert len(written) == 1 and 'batch: wrote data/_ingest/batches/' in capsys.readouterr().out


@needs_epoch
def test_the_real_snapshot_makes_a_valid_batch(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(glob.glob(os.path.join(EPOCHDL, '**', '*'), recursive=True)):
            if os.path.isfile(path):
                z.write(path, os.path.relpath(path, EPOCHDL).replace(os.sep, '/'))
    b = epoch.ZipBundle(buf.getvalue(), etag='"local"')
    doc = batch.epoch_batch(b, STARTED, FETCHED, str(tmp_path))
    IngestBatch.model_validate(doc)                       # rows_frontiermath_tier_4: digits in a count key
    assert doc['counts']['benchmarks_seen'] == 81 and doc['counts']['per_benchmark_csvs'] == 80
    assert doc['licence']['attribution_text'] == (
        "Epoch AI, ‘Capabilities & Benchmarking’. Published online at epoch.ai. "
        "Retrieved from ‘https://epoch.ai/benchmarks’ [online resource].")
