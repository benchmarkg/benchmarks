"""Tests for scripts/epoch_audit.py against the synthetic cut in tests/fixtures/epochdl-mini/.

epochdl/ is not in the working tree (00 S8.1, 01 S12), so on the real tree only the exit-2
branch runs. These tests are what keep the counting logic from shipping untested.
"""
import importlib.util
import json
import os
import shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'epochdl-mini')
EXPECTED = os.path.join(FIXTURE, 'expected.json')

spec = importlib.util.spec_from_file_location('epoch_audit', os.path.join(ROOT, 'scripts', 'epoch_audit.py'))
epoch_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epoch_audit)


@pytest.fixture
def cut(tmp_path):
    """A writable copy of the fixture, so a test can edit it without touching the tree."""
    dst = tmp_path / 'epochdl-mini'
    shutil.copytree(FIXTURE, dst)
    return dst


def test_rederivation_reproduces_the_hand_counts():
    got = epoch_audit.derive(FIXTURE)
    with open(EXPECTED, encoding='utf-8') as f:
        want = json.load(f)
    assert {k: got[k] for k in want} == want


def test_every_plan_figure_has_a_hand_count():
    # A figure the plan quotes but the fixture never exercises is a figure nobody tested.
    with open(EXPECTED, encoding='utf-8') as f:
        assert set(json.load(f)) == set(epoch_audit.EXPECTED)


def test_exit_0_when_everything_matches(capsys):
    assert epoch_audit.main(['--dir', FIXTURE, '--expect', EXPECTED]) == 0
    assert '30 of 30 figures match' in capsys.readouterr().out


def test_exit_1_when_one_row_is_edited(cut, capsys):
    path = cut / 'gpqa_diamond.csv'
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    path.write_text(''.join(lines[:-1]), encoding='utf-8')   # drop the last data row
    assert epoch_audit.main(['--dir', str(cut), '--expect', EXPECTED]) == 1
    out = capsys.readouterr().out
    assert 'DIFF result_rows' in out and 'expected 12' in out


def test_exit_1_when_a_log_url_changes_bucket(cut):
    # Row 3 of gpqa_diamond.csv is public bucket-only; moving it to a private bucket must
    # move one count from log_public to log_private and nothing else.
    path = cut / 'gpqa_diamond.csv'
    text = path.read_text(encoding='utf-8').replace('fixture-public.s3.example.invalid/inspect_ai_logs/fx03',
                                                    'fixture-private.s3.example.invalid/inspect_ai_logs/fx03')
    path.write_text(text, encoding='utf-8')
    got = epoch_audit.derive(str(cut))
    assert (got['log_public'], got['log_private'], got['log_any']) == (3, 3, 6)
    assert epoch_audit.main(['--dir', str(cut), '--expect', EXPECTED]) == 1


def test_exit_2_names_an_absent_directory(tmp_path, capsys):
    missing = tmp_path / 'no-such-export'
    assert epoch_audit.main(['--dir', str(missing)]) == 2
    assert str(missing) in capsys.readouterr().err


def test_exit_2_names_a_missing_artifact(cut, capsys):
    (cut / 'model_metadata.csv').unlink()
    assert epoch_audit.main(['--dir', str(cut), '--expect', EXPECTED]) == 2
    assert 'model_metadata.csv is missing' in capsys.readouterr().err


def test_plan_expectations_are_the_default(capsys):
    # Without --expect the fixture is judged against the plan's figures and must fail.
    assert epoch_audit.main(['--dir', FIXTURE]) == 1
    assert 'expected 6598 (00 S8.1; 01 S12)' in capsys.readouterr().out


def test_eci_files_are_never_counted_as_results():
    got = epoch_audit.derive(FIXTURE)
    assert got['result_csvs'] == 3 and got['eci_rows'] == 4


def test_emit_writes_the_derived_figures(tmp_path):
    out = tmp_path / 'counts.json'
    epoch_audit.main(['--dir', FIXTURE, '--expect', EXPECTED, '--emit', str(out)])
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['result_rows'] == 12 and data['dir'] == FIXTURE


# ---- P3-S2-T01: the header-signature census --------------------------------------------------

def test_pairing_by_normalised_name_and_by_hand():
    meta = [{'benchmark': b, 'source_file': s} for b, s in (
        ('GPQA diamond', 'gpqa_diamond.csv'), ('BoolQ', ''), ('BTF-3', ''), ('GDP.pdf', ''),
        ('CSQA2', ''), ('METR', ''))]
    on_disk = {'gpqa_diamond.csv', 'bool_q_external.csv', 'btf3_external.csv', 'gdp_pdf_external.csv',
               'common_sense_qa_2_external.csv', 'stray_external.csv'}
    pairs = epoch_audit.pair_orphans(meta, on_disk, {'gpqa_diamond.csv'})
    assert {k: v[0] for k, v in pairs.items()} == {
        'BoolQ': 'bool_q_external.csv', 'BTF-3': 'btf3_external.csv', 'GDP.pdf': 'gdp_pdf_external.csv',
        'CSQA2': 'common_sense_qa_2_external.csv'}
    assert pairs['CSQA2'][1].startswith('hand: ')
    assert 'METR' not in pairs  # no CSV: the one row the plan's 80-vs-81 comes down to


def test_a_csv_claimed_by_two_rows_is_refused():
    meta = [{'benchmark': 'Foo Bar', 'source_file': ''}, {'benchmark': 'foo-bar', 'source_file': ''}]
    pairs = epoch_audit.pair_orphans(meta, {'foo_bar_external.csv'}, set())
    assert list(pairs) == ['Foo Bar']  # first come; the second finds nothing left to take


def test_an_orphan_paired_by_name_is_not_a_row_without_csv(cut):
    with open(cut / 'benchmark_metadata.csv', 'a', encoding='utf-8', newline='') as f:
        f.write('MMLU,False,,,,,,2020-09-07,\n')
    got = epoch_audit.derive(str(cut))
    assert got['benchmarks'] == 4 and got['metadata_without_csv'] == 1  # still only METR


def test_check_compares_only_the_census_figures(capsys):
    assert epoch_audit.main(['--dir', FIXTURE, '--check']) == 1  # a 3-CSV fixture is not the 80-CSV drop
    lines = [l for l in capsys.readouterr().out.splitlines() if l.startswith(('ok', 'DIFF'))]
    assert sorted(l.split()[1] for l in lines) == sorted(epoch_audit.CENSUS)


def test_census_report_is_deterministic_and_names_non_ascii_headers(cut, tmp_path):
    with open(cut / 'mmlu_external.csv', encoding='utf-8') as f:
        body = f.read()
    (cut / 'mmlu_external.csv').write_text(body.replace('EM,', 'EM 95% CI (±),', 1), encoding='utf-8')
    a, b = tmp_path / 'a.md', tmp_path / 'b.md'
    epoch_audit.main(['--dir', str(cut), '--census-report', str(a), '--expect', EXPECTED])
    epoch_audit.main(['--dir', str(cut), '--census-report', str(b), '--expect', EXPECTED])
    assert a.read_bytes() == b.read_bytes()
    text = a.read_text(encoding='utf-8')
    assert '| `mmlu_external.csv` | `±` U+00B1 | yes | `Â±` |' in text
    assert '## The 2 header signatures' in text and 'Unpaired rows: `METR`.' in text
