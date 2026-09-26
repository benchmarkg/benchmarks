"""Tests for .github/workflows/pr-validate.yml (P0-S6-T01; 05 S9 checks 1-4, 04 S12).

The verify: "`pytest tests/ci/test_pr_validate_matrix.py` asserts jobs 1 to 4 exist and are all
blocking, and `gh workflow run pr-validate.yml` passes on main while failing a branch carrying a
deliberately broken enum value". The first half is the structural tests below. The second half runs
on GitHub; what can be checked here is the same thing in miniature -- each job's own command, read
out of the workflow, run against a throwaway git repository whose main is clean and whose branch
breaks an enum -- plus a strict xfail recording that the real main does not pass yet.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.validate import tiers  # noqa: E402

WORKFLOW = os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml')
BASE = os.path.join(ROOT, 'tests', 'cli', 'fixtures', 'validate', 'base')
BENCH = 'data/benchmarks/code/example-bench.yaml'
# 05 S9's table: job number -> (the check, the command its step must run)
CHECKS = {
    1: ('fmt', 'bench fmt --check'),
    2: ('schema', 'bench validate --tier schema $SCOPE'),
    3: ('ref', 'bench validate --tier ref $SCOPE'),
    4: ('semantic', 'bench validate --tier semantic $SCOPE'),
}


@pytest.fixture(scope='module')
def wf():
    with open(WORKFLOW, encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)


def job(wf, n):
    [(key, body)] = [(k, v) for k, v in wf['jobs'].items() if k.startswith('check-%d-' % n)]
    return key, body


def runs(body):
    return [s['run'] for s in body['steps'] if 'run' in s]


def triggers(wf):
    return wf['on']                         # ruamel reads YAML 1.2, where `on` is a string, not True


# ---- jobs 1 to 4 exist and are all blocking -----------------------------------------------------

def test_verify_jobs_1_to_4_exist_and_run_their_check(wf):
    for n, (check, command) in CHECKS.items():
        key, body = job(wf, n)
        assert key == 'check-%d-%s' % (n, check) and body['name'].startswith('%d ' % n)
        assert any(r.endswith(command) for r in runs(body)), (key, runs(body))


def test_verify_every_job_is_blocking(wf):
    for n in CHECKS:
        key, body = job(wf, n)
        assert 'continue-on-error' not in body, key
        assert 'if' not in body, '%s may be skipped' % key
        for step in body['steps']:
            assert 'continue-on-error' not in step and 'if' not in step, (key, step)
            assert not re.search(r'\|\|\s*(true|:|exit 0)', step.get('run', '')), (key, step['run'])  # get-default: a uses: step has no run


def test_it_runs_on_every_pull_request_and_on_main(wf):
    on = triggers(wf)
    assert 'pull_request' in on and on['pull_request'] in (None, {}), 'no paths or branches filter on pull_request'
    assert on['push'] == {'branches': ['main']}


def test_pull_requests_run_changed_only_and_main_runs_everything(wf):
    assert wf['env']['SCOPE'] == "${{ github.event_name == 'pull_request' && '--changed-only' || '' }}"
    for n in (2, 3, 4):
        key, body = job(wf, n)
        [checkout] = [s for s in body['steps'] if s.get('uses', '').startswith('actions/checkout@')]  # get-default: a run: step has no uses
        assert checkout['with']['fetch-depth'] == 0, '%s needs history for the merge base' % key


def test_the_python_is_the_lockfiles(wf):
    with open(os.path.join(ROOT, 'uv.lock'), encoding='utf-8') as fh:
        pinned = re.search(r'^requires-python = "==(\d+\.\d+)\.\*"$', fh.read(), re.M).group(1)
    assert wf['env']['PYTHON'] == pinned
    for n in CHECKS:
        for r in runs(job(wf, n)[1]):
            assert r.startswith('uv run --locked --python "$PYTHON" '), r


def test_actions_are_pinned_by_commit_sha(wf):
    for key, body in wf['jobs'].items():
        for step in body['steps']:
            if 'uses' in step:
                assert re.fullmatch(r'[\w./-]+@[0-9a-f]{40}', step['uses']), (key, step['uses'])


# ---- the same commands, on a main that passes and a branch that breaks an enum ------------------

def _git(repo, *args):
    subprocess.run(['git', '-c', 'user.name=ci-test', '-c', 'user.email=ci-test@example.invalid', *args],
                   cwd=repo, check=True, capture_output=True, text=True)


def _tier(command: str) -> str:
    return re.search(r'--tier (\w+)', command).group(1)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """The validate base fixture (clean at every tier) committed on main, then a branch `pr` that
    changes evaluation_target to a value the enum does not have."""
    root = tmp_path / 'repo'
    shutil.copytree(BASE, root)
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '-A')
    _git(root, 'commit', '-q', '-m', 'clean corpus')
    _git(root, 'switch', '-q', '-c', 'pr')
    path = root / BENCH
    text = path.read_text(encoding='utf-8')
    assert text.count('evaluation_target: learned-system') == 1
    path.write_text(text.replace('evaluation_target: learned-system', 'evaluation_target: learned-sistem'),
                    encoding='utf-8', newline='\n')
    _git(root, 'commit', '-q', '-am', 'break an enum')
    monkeypatch.setenv('GITHUB_BASE_REF', 'main')
    return root


def _validate_jobs(wf, root, event):
    """Each of checks 2-4 as the workflow runs it for `event`: its tier, and --changed-only when
    SCOPE expands to it. Returns job key -> blocking findings."""
    scope = '--changed-only' if event == 'pull_request' else ''
    out = {}
    for n in (2, 3, 4):
        key, body = job(wf, n)
        [cmd] = [r for r in runs(body) if 'bench validate' in r]
        cmd = cmd.replace('$SCOPE', scope)
        report = tiers.run(str(root), _tier(cmd), changed_only='--changed-only' in cmd)
        out[key] = report.blocking
    return out


def test_verify_the_pull_request_path_fails_a_branch_with_a_broken_enum(wf, repo):
    blocking = _validate_jobs(wf, repo, 'pull_request')
    assert [f.path for f in blocking['check-2-schema']] == [BENCH]
    assert 'evaluation_target' in blocking['check-2-schema'][0].message


def test_verify_the_main_path_passes_on_a_clean_main(wf, repo):
    _git(repo, 'switch', '-q', 'main')
    assert _validate_jobs(wf, repo, 'push') == {'check-2-schema': [], 'check-3-ref': [], 'check-4-semantic': []}


def test_a_break_already_on_main_is_left_to_mains_full_run(wf, repo):
    """--changed-only reports on what a pull request changed: a break that reached main some other
    way does not fail an unrelated PR, and main's full run is what catches it."""
    _git(repo, 'switch', '-q', 'main')
    _git(repo, 'merge', '-q', '--ff-only', 'pr')                        # the break is now on main
    _git(repo, 'switch', '-q', '-c', 'pr2')
    metric = repo / 'data' / 'metrics' / 'accuracy.yaml'
    metric.write_text(metric.read_text(encoding='utf-8').replace('name: Accuracy', 'name: Top-1 Accuracy'),
                      encoding='utf-8', newline='\n')
    _git(repo, 'commit', '-q', '-am', 'an unrelated edit')
    assert all(v == [] for v in _validate_jobs(wf, repo, 'pull_request').values())
    _git(repo, 'switch', '-q', 'main')
    assert [f.path for f in _validate_jobs(wf, repo, 'push')['check-2-schema']] == [BENCH]


@pytest.mark.xfail(strict=True, reason=(
    "The real main does not pass checks 2 and 4 yet: P0-S3-T04's draft Source records are unarchived "
    "(no Wayback keys) and fail tier 1 and tier 3's non-doi-archive rule. When they are archived this "
    "passes, and strict=True turns that into a failure so the xfail is removed."))
def test_the_repository_main_passes_checks_2_to_4(wf):
    for n in (2, 3, 4):
        key, body = job(wf, n)
        [cmd] = [r for r in runs(body) if 'bench validate' in r]
        assert tiers.run(ROOT, _tier(cmd)).blocking == [], key
