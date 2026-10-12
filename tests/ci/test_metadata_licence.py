"""Checks 7 and 8: the metadata-only invariant and the licence firewall (P0-S6-T04; 05 S9).

The verify: "`python scripts/check_metadata_only.py` exits 1 on a fixture .parquet under data/ and on a
300 KB YAML; `python scripts/check_licence_firewall.py` exits 1 on a fixture commit moving vendor/ content
into data/ with no trailer". Both scripts run here against throwaway trees and git repositories, and the
repository itself passes both. The last tests hold pr-validate.yml's jobs 7 and 8 to being blocking.
"""
import os
import re
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(ROOT, 'scripts', 'check_metadata_only.py')
FIREWALL = os.path.join(ROOT, 'scripts', 'check_licence_firewall.py')
VENDOR_LINE = 'description: A long line of share-alike prose that the archive wrote and we may not copy.'


def run(script, *args):
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, encoding='utf-8')


# ---- check 7 ------------------------------------------------------------------------------------

def tree(tmp_path, files):
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body if isinstance(body, bytes) else body.encode('utf-8'))
    return str(tmp_path)


def test_verify_a_parquet_under_data_fails(tmp_path):
    r = run(META, '--root', tree(tmp_path, {'data/benchmarks/x.yaml': 'id: x\n', 'data/items/test.parquet': b'PAR1'}))
    assert r.returncode == 1 and 'data/items/test.parquet: a dataset file (.parquet)' in r.stdout


def test_verify_a_300_kb_yaml_fails(tmp_path):
    r = run(META, '--root', tree(tmp_path, {'data/sources/big.yaml': 'x: ' + 'a' * (300 * 1024) + '\n'}))
    assert r.returncode == 1 and 'over the 256 KB limit' in r.stdout


@pytest.mark.parametrize('name', ['rows.jsonl', 'table.csv', 'arrays.npz', 'dump.zip', 'dump.tar.gz'])
def test_every_dataset_and_archive_suffix_fails(tmp_path, name):
    assert run(META, '--root', tree(tmp_path, {'data/x/' + name: b'x'})).returncode == 1


def test_files_outside_data_and_small_yaml_pass(tmp_path):
    r = run(META, '--root', tree(tmp_path, {'data/benchmarks/x.yaml': 'id: x\n', 'tests/fixtures/rows.csv': 'a,b\n',
                                             'vendor/pwc/papers.jsonl': '{}\n'}))
    assert r.returncode == 0, r.stdout


def test_the_repository_passes_check_7():
    r = run(META)
    assert r.returncode == 0, r.stdout


# ---- check 8 ------------------------------------------------------------------------------------

def git(repo, *args):
    return subprocess.run(['git', '-c', 'user.name=ci-test', '-c', 'user.email=ci-test@example.invalid', *args],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """main: a vendor/ file and an unrelated data/ file."""
    r = tmp_path / 'repo'
    (r / 'vendor' / 'pwc').mkdir(parents=True)
    (r / 'data' / 'benchmarks').mkdir(parents=True)
    (r / 'vendor' / 'pwc' / 'paper.yaml').write_text('id: paper\n' + VENDOR_LINE + '\n', encoding='utf-8')
    (r / 'data' / 'benchmarks' / 'other.yaml').write_text('id: other\naccess: fully-open\n', encoding='utf-8')
    git(r, 'init', '-q', '-b', 'main')
    git(r, 'add', '-A')
    git(r, 'commit', '-q', '-m', 'main')
    git(r, 'switch', '-q', '-c', 'pr')
    return r


def firewall(repo):
    return run(FIREWALL, '--root', str(repo), '--base', 'main')


def test_verify_a_move_from_vendor_to_data_without_a_trailer_fails(repo):
    git(repo, 'mv', 'vendor/pwc/paper.yaml', 'data/benchmarks/paper.yaml')
    git(repo, 'commit', '-q', '-m', 'promote the paper')
    r = firewall(repo)
    assert r.returncode == 1 and 'vendor/pwc/paper.yaml -> data/benchmarks/paper.yaml' in r.stdout
    assert 'no Re-derived-from: trailer' in r.stdout


def test_a_copied_line_counts_as_moved_content(repo):
    p = repo / 'data' / 'benchmarks' / 'other.yaml'
    p.write_text(p.read_text(encoding='utf-8') + VENDOR_LINE + '\n', encoding='utf-8')
    git(repo, 'commit', '-q', '-am', 'borrow a description')
    r = firewall(repo)
    assert r.returncode == 1 and 'line copied into data/benchmarks/other.yaml' in r.stdout


def test_a_trailer_naming_a_primary_source_passes(repo):
    git(repo, 'mv', 'vendor/pwc/paper.yaml', 'data/benchmarks/paper.yaml')
    git(repo, 'commit', '-q', '-m', 'promote the paper\n\nRe-derived-from: src-arxiv-2310-06770')
    assert firewall(repo).returncode == 0


def test_a_trailer_that_names_no_source_fails(repo):
    git(repo, 'mv', 'vendor/pwc/paper.yaml', 'data/benchmarks/paper.yaml')
    git(repo, 'commit', '-q', '-m', 'promote the paper\n\nRe-derived-from: the archive, checked by hand')
    r = firewall(repo)
    assert r.returncode == 1 and 'does not name a primary source' in r.stdout


def test_shared_vocabulary_and_unrelated_commits_pass(repo):
    p = repo / 'data' / 'benchmarks' / 'new.yaml'
    p.write_text('id: new\naccess: fully-open\n', encoding='utf-8')                  # short lines are not content
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'a new entry')
    assert firewall(repo).returncode == 0


def test_every_commit_in_the_range_is_read(repo):
    git(repo, 'mv', 'vendor/pwc/paper.yaml', 'data/benchmarks/paper.yaml')
    git(repo, 'commit', '-q', '-m', 'promote the paper')
    (repo / 'README.md').write_text('later\n', encoding='utf-8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'a later, innocent commit')
    assert firewall(repo).returncode == 1                                           # not only the tip
    assert run(FIREWALL, '--root', str(repo)).returncode == 0                      # the tip alone is clean


def test_the_repository_head_passes_check_8():
    r = run(FIREWALL)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- the jobs ------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def jobs():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']


@pytest.mark.parametrize('key, script', [('check-7-metadata-only', 'check_metadata_only.py'),
                                         ('check-8-licence-firewall', 'check_licence_firewall.py')])
def test_jobs_7_and_8_run_their_check_and_block(jobs, key, script):
    body = jobs[key]
    assert body['name'].startswith(key.split('-')[1] + ' ')
    assert 'continue-on-error' not in body and 'if' not in body
    [run_] = [s['run'] for s in body['steps'] if 'run' in s]
    assert run_.startswith('uv run --locked --python "$PYTHON" python scripts/' + script)
    assert not re.search(r'\|\|\s*(true|:|exit 0)', run_)


def test_job_8_reads_the_history(jobs):
    [checkout] = [s for s in jobs['check-8-licence-firewall']['steps'] if s.get('uses', '').startswith('actions/checkout@')]  # get-default: a run: step has no uses
    assert checkout['with']['fetch-depth'] == 0
    assert 'origin/{0}' in jobs['check-8-licence-firewall']['env']['FIREWALL_BASE']
