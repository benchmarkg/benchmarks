"""Tests for `bench ingest` (P3-S1-T06; 07 S1.6, S6.2, S8.1).

The verify is `bench ingest epoch --dry-run --no-network --limit 50`. DONE WHEN: "The command exits 0 on a
clean dry run, prints the change-class summary, and exits non-zero when a draft fails schema
validation." Sockets are disabled throughout; the epochdl/ cases skip where it is absent (00 S8.1).
"""
import glob
import io
import os
import socket
import sys
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from ingest.adapters import epoch  # noqa: E402
from ingest.adapters.base import Draft  # noqa: E402
from tools import cli  # noqa: E402
from tools.bench import cmd_ingest  # noqa: E402

runner = CliRunner()
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
HAVE_EPOCHDL = bool(glob.glob(os.path.join(ROOT, 'epochdl', '*.csv')))
CLAIM = {'id': 'claim-0123456789ab', 'system': 'example-model', 'benchmark': 'example-bench',
         'metric': 'accuracy', 'value': 0.5, 'date_reported': '2026-09-01', 'reported_by': 'org-x',
         'verification': 'self-reported', 'source': 'src-x'}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def ingest(*args):
    return runner.invoke(cli.app, ['ingest', 'epoch', *args])


def drafting(payloads, change_class='new'):
    """A normaliser that turns every claim payload into these claim drafts."""
    def normalise(payload, resolver=None):
        if payload.candidate.kind != 'claim':
            return [], []
        return [Draft('claim', None, Path('data/claims/_ingested/epoch/'), p, change_class, {}, 1.0)
                for p in payloads], []
    return normalise


def test_a_clean_dry_run_exits_0_and_prints_every_change_class():
    r = ingest('--dry-run', '--fixture', FIX)
    assert r.exit_code == 0, r.output
    assert 'ingest epoch %s: no-change' % epoch.VERSION in r.output
    for c in CLASSES:
        assert '  %-13s 0' % c in r.output
    assert '  candidates    4' in r.output and '  unresolved    2' in r.output   # two CSVs, no stanza yet


def test_an_unmapped_csv_is_unresolved_never_a_guessed_claim():
    report = epoch.run(epoch.ZipBundle(open(os.path.join(FIX, 'benchmark_data.zip'), 'rb').read()))
    assert report['unresolved'] == 2 and sum(report['drafts'].values()) == 0
    b = epoch.ZipBundle(open(os.path.join(FIX, 'benchmark_data.zip'), 'rb').read())
    cand = next(c for c in epoch.candidates(b) if c.kind == 'claim')
    _, [u] = epoch.normalise(b.payload_for(cand))
    assert u.reason == 'no-match' and 'Do NOT assume scale=1.0' in u.human_task


def test_a_draft_that_fails_schema_validation_exits_non_zero(monkeypatch):
    monkeypatch.setattr(epoch, 'normalise', drafting([dict(CLAIM, value='not a number')]))
    r = ingest('--dry-run', '--fixture', FIX)
    assert r.exit_code == 1 and 'hard-fail' in r.output and 'invalid draft: claim' in r.output


def test_a_valid_draft_is_counted_under_its_change_class(monkeypatch):
    monkeypatch.setattr(epoch, 'normalise', drafting([CLAIM], 'result-change'))
    r = ingest('--dry-run', '--fixture', FIX)
    assert r.exit_code == 0 and ': ok' in r.output and '  result-change 2' in r.output   # one per CSV


def test_schema_drift_exits_non_zero(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('benchmark_metadata.csv', 'benchmark,source_file\nX,x.csv\n')       # no score_column, scale
        z.writestr('model_metadata.csv', 'model_version,model_group\nm,M\n')
    monkeypatch.setattr(cmd_ingest, '_source', lambda *a: (epoch.ZipBundle(buf.getvalue()), 'a drifted bundle'))
    r = ingest('--dry-run', '--no-network')
    assert r.exit_code == 1 and 'schema drift' in r.output and 'score_column, scale' in r.output


@pytest.mark.parametrize('content', ['benchmark,source_file,score_column,scale\n', None])
def test_an_empty_or_missing_metadata_file_is_drift(content):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        if content is not None:
            z.writestr('benchmark_metadata.csv', content)
        z.writestr('model_metadata.csv', 'model_version,model_group\nm,M\n')
    report = epoch.run(epoch.ZipBundle(buf.getvalue()))
    assert report['status'] == 'hard-fail' and 'schema drift' in report['errors'][0]


def test_over_the_caps_needs_allow_bulk(monkeypatch):
    many = [dict(CLAIM, id='claim-%012x' % i) for i in range(101)]               # 2 CSVs x 101 = 202 > 200
    monkeypatch.setattr(epoch, 'normalise', drafting(many))
    r = ingest('--dry-run', '--fixture', FIX)
    assert r.exit_code == 3 and 'capped' in r.output and 'claim 202 > 200' in r.output
    r = ingest('--dry-run', '--fixture', FIX, '--allow-bulk')
    assert r.exit_code == 0 and '  new           202' in r.output


def test_limit_caps_the_candidates_processed():
    r = ingest('--dry-run', '--fixture', FIX, '--limit', '3')
    assert r.exit_code == 0 and '  candidates    3' in r.output


@pytest.mark.parametrize('args, why', [
    (('--fixture', FIX), 'run with --dry-run'),                                    # writing is not built
    (('--dry-run',), 'a live fetch is not built'),                                 # the network, in phase 0
])
def test_what_phase_0_cannot_do_exits_2(args, why):
    r = ingest(*args)
    assert r.exit_code == 2 and why in r.output


def test_an_unknown_adapter_exits_2():
    r = runner.invoke(cli.app, ['ingest', 'nope', '--dry-run'])
    assert r.exit_code == 2 and "no adapter 'nope'" in r.output


def test_no_network_without_epochdl_says_to_pass_a_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(cmd_ingest, 'ROOT', str(tmp_path))
    r = ingest('--dry-run', '--no-network')
    assert r.exit_code == 2 and 'pass --fixture PATH' in r.output


def test_a_304_is_no_change(monkeypatch):
    monkeypatch.setattr(cmd_ingest, '_source', lambda *a: (None, 'a fixture that answered 304'))
    r = ingest('--dry-run', '--no-network')
    assert r.exit_code == 0 and 'no-change' in r.output and '  candidates    0' in r.output


@pytest.mark.skipif(not HAVE_EPOCHDL, reason='epochdl/ is not in the working tree (00 S8.1)')
def test_the_verify_command_over_the_local_snapshot():
    r = ingest('--dry-run', '--no-network', '--limit', '50')
    assert r.exit_code == 0, r.output
    assert 'reading epochdl/ (local snapshot)' in r.output and '  candidates    50' in r.output
    full = epoch.run(epoch.bundle_from_directory(os.path.join(ROOT, 'epochdl')))
    assert full['candidates_seen'] == 81 + 80 and full['unresolved'] == 80       # 07 S2's counts
