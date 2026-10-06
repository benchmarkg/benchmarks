"""Tests for scripts/epoch_rule_accounting.py, the four-rule row accounting (P3-S4-T03; 14 Phase 3, 07 S2.3).

The done-when: "The four rules account for every row, the sum equals the batch total, and the unmatched count is
published even when it is zero." Bundles here are built in memory, with stand-in stanzas; the last tests run over
the real snapshot in epochdl/ (gitignored, so skipped where it is absent). Nothing reaches the network.
"""
import io
import json
import os
import socket
import sys
import zipfile
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import epoch_rule_accounting as A  # noqa: E402
from ingest.adapters import epoch  # noqa: E402

PUB = 'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/a.eval'
STAGING = 'https://epoch-benchmarks-staging-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/b.eval'
PRIV = 'https://epoch-benchmarks-production-private.s3.us-east-2.amazonaws.com/inspect_ai_logs/c.eval'
PRIV_STAGING = 'https://epoch-benchmarks-staging-private.s3.us-east-2.amazonaws.com/inspect_ai_logs/d.eval'
META = {'benchmark_metadata.csv': 'benchmark,source_file,score_column,scale\n',
        'model_metadata.csv': 'model_version,model_group\n'}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def bundle(files):
    """A bundle from {stem: [log cells]} (a 'Logs' column) or {stem: int} (that many rows, no log column)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, text in META.items():
            z.writestr(name, text)
        for stem, cells in files.items():
            if isinstance(cells, int):
                z.writestr(stem + '.csv', 'Model version,Score\n' + ''.join('m%d,0.5\n' % i for i in range(cells)))
            else:
                z.writestr(stem + '.csv', 'Model version,Logs\n' + ''.join('m%d,%s\n' % i for i in enumerate(cells)))
    return epoch.ZipBundle(buf.getvalue())


def stanza(family, log_column=None):
    return SimpleNamespace(family=family, artifact=SimpleNamespace(log_column=log_column) if log_column else None)


RUN, EXT = stanza('epoch-run', 'Logs'), stanza('external-scrape')


def by_rule(acc):
    return {r['rule']: r['rows'] for r in acc['rules']}


# ---- the four rules and the default -----------------------------------------------------------------------

def test_each_row_lands_in_exactly_one_of_the_four_rules():
    b = bundle({'run': [PUB, STAGING, PRIV, PRIV_STAGING, '', '  '], 'ext': 3, 'run_nolog': 2})
    acc = A.account(b, {'csv:run': RUN, 'csv:ext': EXT, 'csv:run_nolog': stanza('epoch-run')})
    assert by_rule(acc) == {'epoch-run-public-log': 2, 'epoch-run-private-log': 2, 'epoch-run-no-log': 4,
                            'external-scrape': 3, 'unmatched': 0}
    assert acc['total'] == 11 and acc['unmatched'] == 0 and acc['unmatched_rows'] == []


def test_the_rung_each_rule_assigns_is_the_verification_rules_own():
    acc = A.account(bundle({}), {})
    assert {r['rule']: r['assigns'] for r in acc['rules']} == {
        'epoch-run-public-log': 'independent-reproduction', 'epoch-run-private-log': 'maintainer-verified',
        'epoch-run-no-log': 'maintainer-verified', 'external-scrape': 'self-reported', 'unmatched': 'self-reported'}
    assert 'HEAD' in acc['rules'][0]['note']


def test_an_external_rows_log_column_is_never_read():
    acc = A.account(bundle({'ext': [PUB, 'junk']}), {'csv:ext': stanza('external-scrape', 'Logs')})
    assert by_rule(acc)['external-scrape'] == 2


@pytest.mark.parametrize('url, why', [
    ('https://example.org/logs/a.eval', 'neither bucket'),
    ('https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/a.json', 'neither bucket'),
    ('http://epoch-benchmarks-production-private.s3.us-east-2.amazonaws.com/c.eval', 'neither bucket'),
    ('https://evil.example/epoch-benchmarks-production-public/a.eval', 'neither bucket'),
    (PRIV + '?x=1', 'neither bucket'),
])
def test_a_log_url_on_neither_bucket_is_unmatched_not_guessed(url, why):
    acc = A.account(bundle({'run': [url, PUB]}), {'csv:run': RUN})
    assert acc['unmatched'] == 1 and by_rule(acc)['epoch-run-public-log'] == 1
    [u] = acc['unmatched_rows']
    assert u['file'] == 'run.csv' and u['rows'] == 1 and why in u['reason']


def test_a_file_with_no_stanza_or_a_missing_log_column_is_unmatched_whole():
    b = bundle({'orphan': 4, 'run': 2})
    acc = A.account(b, {'csv:run': RUN})                    # run.csv has no 'Logs' column
    assert acc['unmatched'] == 6 and acc['total'] == 6
    assert [(u['file'], u['rows']) for u in acc['unmatched_rows']] == [('orphan.csv', 4), ('run.csv', 2)]
    assert 'no mapping stanza' in acc['unmatched_rows'][0]['reason']
    assert "log column 'Logs'" in acc['unmatched_rows'][1]['reason']


def test_the_unmatched_count_is_published_even_when_it_is_zero(tmp_path):
    acc = A.account(bundle({'ext': 2}), {'csv:ext': EXT})
    assert A.balance(acc, None) == []
    out = tmp_path / 'ingest_accounting.json'
    out.write_text(json.dumps(acc))
    doc = json.loads(out.read_text())
    assert doc['unmatched'] == 0 and doc['rules'][-1] == {'rule': 'unmatched', 'assigns': 'self-reported',
                                                          'rows': 0, 'files': 0}


# ---- the balance against the batch ------------------------------------------------------------------------

def batch_doc(claims_written, **rows):
    return {'id': 'ingest-epoch-2026-10-06', 'counts': dict({'files_seen': 9, 'claims_written': claims_written},
                                                            **{'rows_' + k: n for k, n in rows.items()})}


def test_without_a_batch_the_rules_are_held_to_the_snapshots_rows_and_say_so():
    acc = A.account(bundle({'ext': 2, 'run': ['', PUB]}), {'csv:ext': EXT, 'csv:run': RUN})
    assert A.balance(acc, None) == []
    assert acc['claims_written'] == 4 and acc['balanced'] and 'no Epoch IngestBatch' in acc['claims_written_basis']
    assert 'rows_per_file' not in acc


def test_the_rules_must_sum_to_the_batchs_claims_written():
    acc = A.account(bundle({'ext': 2, 'run': ['', PUB]}), {'csv:ext': EXT, 'csv:run': RUN})
    assert A.balance(acc, batch_doc(4, ext=2, run=2)) == []
    assert acc['claims_written_basis'] == 'batch ingest-epoch-2026-10-06'
    acc = A.account(bundle({'ext': 2, 'run': ['', PUB]}), {'csv:ext': EXT, 'csv:run': RUN})
    [fail] = A.balance(acc, batch_doc(3, ext=2, run=2))      # the run wrote one claim fewer than there are rows
    assert 'account for 4 rows but claims_written is 3' in fail and not acc['balanced']


def test_a_batch_of_another_snapshot_is_refused():
    acc = A.account(bundle({'ext': 2, 'run': ['', PUB]}), {'csv:ext': EXT, 'csv:run': RUN})
    fails = A.balance(acc, batch_doc(4, ext=3, run=1))
    assert len(fails) == 1 and 'different snapshot' in fails[0] and '(ext, run)' in fails[0]
    acc = A.account(bundle({'ext': 2}), {'csv:ext': EXT})
    assert 'different snapshot' in A.balance(acc, batch_doc(2, ext=2, gone=0))[0]


def test_any_unmatched_row_fails_the_check_even_when_the_sum_balances():
    acc = A.account(bundle({'orphan': 1}), {})
    [fail] = A.balance(acc, None)
    assert acc['balanced'] and '1 rows match none of the four rules' in fail


def test_the_newest_batch_is_by_date_then_by_run_number(tmp_path):
    assert A.newest_batch(str(tmp_path)) is None
    for n in ('ingest-epoch-2026-10-05.yaml', 'ingest-epoch-2026-10-06-2.yaml', 'ingest-epoch-2026-10-06-10.yaml',
              'ingest-epoch-2026-10-06.yaml', 'ingest-hf-hub-2026-12-01.yaml', 'ingest-epoch-notes.yaml'):
        (tmp_path / n).write_text('{}')
    assert os.path.basename(A.newest_batch(str(tmp_path))) == 'ingest-epoch-2026-10-06-10.yaml'


def test_main_writes_the_artifact_and_check_fails_on_the_fixtures_unmapped_files(tmp_path, capsys):
    out = tmp_path / 'derived' / 'ingest_accounting.json'
    fixture = os.path.join(ROOT, 'tests', 'fixtures', 'epoch', 'benchmark_data.zip')
    args = ['--zip', fixture, '--out', str(out)]
    assert A.main(args) == 0                                  # without --check it reports, it does not fail
    assert A.main(args + ['--check']) == 1                    # the fixture's two files have no stanza
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert doc['unmatched'] == doc['total'] == 3 and 'FAIL 3 rows match none' in capsys.readouterr().err


def test_main_balances_against_a_named_batch(tmp_path):
    fixture = os.path.join(ROOT, 'tests', 'fixtures', 'epoch', 'benchmark_data.zip')
    path = tmp_path / 'ingest-epoch-2026-10-06.yaml'
    path.write_text(json.dumps(batch_doc(3, example_bench=2, example_orphan_external=1)))
    out = tmp_path / 'a.json'
    A.main(['--zip', fixture, '--out', str(out), '--batch', str(path)])
    doc = json.loads(out.read_text(encoding='utf-8'))
    assert doc['claims_written'] == 3 and doc['balanced'] and doc['claims_written_basis'].startswith('batch ')


# ---- the real snapshot ------------------------------------------------------------------------------------

EPOCHDL = os.path.join(ROOT, 'epochdl')
needs_epoch = pytest.mark.skipif(not os.path.isdir(EPOCHDL), reason='epochdl/ (the Epoch snapshot) is gitignored')


@needs_epoch
def test_the_real_snapshot_is_accounted_for_by_the_four_rules_exactly():
    from ingest.mappings.schema import load_all
    acc = A.account(epoch.bundle_from_directory(EPOCHDL), load_all('epoch'))
    assert A.balance(acc, None) == []
    # 14 Phase 3's table, row for row: 828 + 459 + 263 + 5,048 = 6,598, and 0 unmatched
    assert by_rule(acc) == {'epoch-run-public-log': 828, 'epoch-run-private-log': 459, 'epoch-run-no-log': 263,
                            'external-scrape': 5048, 'unmatched': 0}
    assert acc['total'] == acc['claims_written'] == 6598
    counts = epoch.counts(epoch.bundle_from_directory(EPOCHDL))
    assert acc['claims_written'] == sum(n for k, n in counts.items() if k.startswith('rows_'))


@needs_epoch
def test_the_verify_command_passes_on_the_real_snapshot(tmp_path):
    assert A.main(['--check', '--out', str(tmp_path / 'a.json')]) == 0
