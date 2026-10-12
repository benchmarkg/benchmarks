"""The schema freeze and stopping rule (b) (P1-S3-T09; 14-roadmap).

The verify, `python scripts/check_schema_churn.py --window 40`, exits 1 today by design: the schema last changed
with ADR-0024 at entry 34, and no entry has been added since. These cases run the checker over throwaway git
repositories to show the count, the window, the docstring exemption and rule (b), and the last asserts it is a
reported (non-blocking) job.
"""
import os
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHURN = os.path.join(ROOT, 'scripts', 'check_schema_churn.py')
MODULE = '"""A schema module."""\nNAME = "benchmark"\n'


def git(repo, *args):
    subprocess.run(['git', '-c', 'user.name=ci-test', '-c', 'user.email=ci-test@example.invalid', *args],
                   cwd=repo, check=True, capture_output=True, text=True)


def commit(repo, files, msg='change'):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', msg)


def entries(n, start=0):
    return {'data/benchmarks/code/bench-%03d.yaml' % i: 'id: bench-%03d\n' % i for i in range(start, start + n)}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'repo'
    r.mkdir()
    git(r, 'init', '-q', '-b', 'main')
    commit(r, dict(entries(3), **{'schema/benchmark.py': MODULE}), 'start')
    return r


def churn(repo, window):
    r = subprocess.run([sys.executable, CHURN, '--root', str(repo), '--window', str(window)],
                       capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout


def test_entries_since_the_last_schema_change_are_counted(repo):
    commit(repo, {'schema/benchmark.py': MODULE + 'TAGLINE = True\n'}, 'a schema change')
    commit(repo, entries(4, start=3), 'four entries')
    commit(repo, {'data/benchmarks/_stubs/stub.yaml': 'id: stub\n'}, 'a stub is not an entry')
    code, out = churn(repo, 5)
    assert code == 1 and '3 entries existed; 4 entries added since' in out
    assert churn(repo, 4)[0] == 0


def test_a_docstring_edit_does_not_restart_the_count(repo):
    commit(repo, {'schema/benchmark.py': MODULE + 'TAGLINE = True\n'}, 'a schema change')
    commit(repo, entries(2, start=3), 'two entries')
    commit(repo, {'schema/benchmark.py': MODULE.replace('A schema module.', 'A schema module, reworded.')
                  + 'TAGLINE = True\n'}, 'docstring only')
    code, out = churn(repo, 2)
    assert code == 0 and '2 entries added since' in out


def test_rule_b_fires_on_a_schema_change_after_entry_60(repo):
    commit(repo, entries(60, start=3), 'sixty more')
    commit(repo, {'schema/benchmark.py': MODULE + 'LATE = True\n'}, 'a late schema change')
    code, out = churn(repo, 40)
    assert code == 1 and 'STOPPING RULE (b) FIRES' in out and '63 entries existed' in out


def test_rule_b_is_quiet_before_entry_60(repo):
    commit(repo, {'schema/benchmark.py': MODULE + 'EARLY = True\n'}, 'an early schema change')
    assert 'STOPPING RULE' not in churn(repo, 40)[1]


def test_the_repository_reports_its_count():
    r = subprocess.run([sys.executable, CHURN, '--window', '40'], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode in (0, 1) and 'entries added since' in r.stdout


def test_it_is_a_reported_signal_not_a_blocking_job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = YAML(typ='safe').load(fh)['jobs']['schema-churn']
    assert job['continue-on-error'] is True
    assert [s['run'] for s in job['steps'] if 'run' in s] == [
        'uv run --locked --python "$PYTHON" python scripts/check_schema_churn.py --window 40']
