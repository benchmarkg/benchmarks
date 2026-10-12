"""The drafts/ boundary in CI (P1-S2-T04; 05 S9 check 9i, 15 AI1).

The verify: "`python -m pytest tests/test_ai_provenance.py` passes: against tests/fixtures/ai-provenance/ the checker
exits non-zero on a record carrying curation.verification_status: ai-drafted-unverified under data/, non-zero on a
data/ path whose last committer is a bot, and 0 on the clean tree; and the pr-validate.yml job that runs it is
asserted blocking."

Each fixture tree becomes a throwaway git repository, committed by whoever the case needs. Two carve-outs 15 AI1
settles are shown to pass: the issue-form bot's commit with its contributor's Co-authored-by trailer, and an
ingestion adapter's ingest: commit. The job's state follows the maintainer's decision of 2026-10-12, as check 9i's
does (tests/ci/test_no_ai_records.py): reported while drafts remain under data/, and asserted blocking from the
moment the check passes on the repository.
"""
import os
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, 'scripts', 'check_ai_provenance.py')
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'ai-provenance')
PERSON = ('A Curator', 'curator@example.invalid')
AI_WORKER = ('uaibi-ai-worker[bot]', 'ai-worker[bot]@users.noreply.github.com')
FORM_BOT = ('uaibi-bot', 'uaibi-bot@example.invalid')


def repo(tmp_path, *trees, author=PERSON, message='curate', trailer=None):
    root = tmp_path / 'repo'
    for tree in trees:
        shutil.copytree(os.path.join(FIXTURES, tree), root, dirs_exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
               GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1])
    run = lambda *a: subprocess.run(['git', *a], cwd=root, env=env, check=True, capture_output=True)
    run('init', '-q', '-b', 'main')
    run('add', '-A')
    run('commit', '-q', '-m', message + ('\n\nCo-authored-by: %s' % trailer if trailer else ''))
    return root


def check(root):
    r = subprocess.run([sys.executable, CHECK, '--root', str(root)], capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout


def test_verify_the_clean_tree_passes(tmp_path):
    code, out = check(repo(tmp_path, 'clean'))
    assert code == 0, out


def test_verify_an_ai_drafted_record_under_data_fails(tmp_path):
    code, out = check(repo(tmp_path, 'clean', 'draft'))
    assert code == 1 and 'data/benchmarks/code/beta-bench.yaml' in out and 'ai-drafted-unverified' in out


def test_verify_a_data_path_last_committed_by_a_bot_fails(tmp_path):
    code, out = check(repo(tmp_path, 'clean', author=AI_WORKER))
    assert code == 1
    assert 'data/benchmarks/code/alpha-bench.yaml: last committed by uaibi-ai-worker[bot]' in out
    assert 'data/sources/2026/src-alpha-paper.yaml' in out


def test_the_issue_form_bot_with_its_contributors_trailer_passes(tmp_path):
    root = repo(tmp_path, 'clean', author=FORM_BOT, message='Correction: alpha-bench',
                trailer='A Contributor <contributor@example.invalid>')
    assert check(root)[0] == 0
    assert check(repo(tmp_path / 'b', 'clean', author=FORM_BOT, message='Correction: alpha-bench'))[0] == 1


def test_an_ingestion_adapters_commit_passes(tmp_path):
    assert check(repo(tmp_path, 'clean', author=AI_WORKER, message='ingest: epoch batch 2026-10-12'))[0] == 0


def test_only_the_last_commit_to_a_path_counts(tmp_path):
    root = repo(tmp_path, 'clean', author=AI_WORKER)
    env = dict(os.environ, GIT_AUTHOR_NAME=PERSON[0], GIT_AUTHOR_EMAIL=PERSON[1], GIT_COMMITTER_NAME=PERSON[0],
               GIT_COMMITTER_EMAIL=PERSON[1])
    for rel in ('data/benchmarks/code/alpha-bench.yaml', 'data/sources/2026/src-alpha-paper.yaml'):
        with open(root / rel, 'a', encoding='utf-8') as fh:
            fh.write('# reviewed by a person\n')
    subprocess.run(['git', 'commit', '-q', '-am', 'review'], cwd=root, env=env, check=True)
    assert check(root)[0] == 0                         # a person's commit vouches for what the bot wrote


def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['check-ai-provenance']


def test_the_job_runs_the_checker_over_the_full_history():
    j = job()
    assert [s['run'] for s in j['steps'] if 'run' in s] == [
        'uv run --locked --python "$PYTHON" python scripts/check_ai_provenance.py']
    checkout = [s for s in j['steps'] if str(s.get('uses', '')).startswith('actions/checkout@')][0]
    assert checkout['with']['fetch-depth'] == 0         # the last commit per path needs the history


def test_verify_the_job_is_blocking_once_no_draft_remains():
    passes = subprocess.run([sys.executable, CHECK], capture_output=True).returncode == 0
    if passes:
        assert job().get('continue-on-error') is not True, (
            'check_ai_provenance.py passes on the repository: make check-ai-provenance blocking (drop continue-on-error)')
    else:
        assert job().get('continue-on-error') is True, 'drafts remain under data/, and the decision of 2026-10-12 reports them'
