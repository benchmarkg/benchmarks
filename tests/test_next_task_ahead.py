"""next_task.py start --ahead-of-review (P3-S3-T07; the maintainer's 2026-10-05 decision to work ahead).

An `agent` task normally finishes straight to done, so it may never rest on a draft still in review. With
--ahead-of-review it may, but only on drafts in review (never on unfinished work), the drafts are recorded,
and it finishes to review so a person still signs it off -- after the drafts it rests on. Run against a copy
of the ledger through EXECUTION_TASKS_FILE, so the real one is never touched.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, '_plan', '_workflow', 'scripts', 'next_task.py')
LEDGER = os.path.join(ROOT, '_plan', 'execution', 'tasks.yaml')

TASKS = """\
phases:
  - phase: 1
    stages:
      - id: S1
        title: stage
        tasks:
          - id: T-DRAFT
            seq: 1
            title: a draft in review
            executor: agent-draft
            status: review
            depends_on: []
            verify: 'true'
            est_hours_low: 1
            est_hours_high: 1
          - id: T-BLOCKED
            seq: 2
            title: blocked work
            executor: agent
            status: blocked
            blocked_reason: waiting
            depends_on: []
            verify: 'true'
            est_hours_low: 1
            est_hours_high: 1
          - id: T-AGENT
            seq: 3
            title: an agent task on the draft
            executor: agent
            status: todo
            depends_on: [T-DRAFT]
            verify: 'true'
            est_hours_low: 1
            est_hours_high: 1
          - id: T-ON-BLOCKED
            seq: 4
            title: an agent task on blocked work
            executor: agent
            status: todo
            depends_on: [T-BLOCKED]
            verify: 'true'
            est_hours_low: 1
            est_hours_high: 1
"""


def nt(path, *args):
    env = dict(os.environ, EXECUTION_TASKS_FILE=str(path))
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)


def ledger(tmp_path):
    p = tmp_path / 'tasks.yaml'
    p.write_text(TASKS, encoding='utf-8')
    return p


def status(path, tid):
    out = nt(path, 'show', tid).stdout
    return out.split('status: ', 1)[1].split()[0]


def test_without_the_flag_an_agent_task_still_waits_on_a_draft(tmp_path):
    p = ledger(tmp_path)
    r = nt(p, 'start', 'T-AGENT')
    assert r.returncode != 0 and 'waits on T-DRAFT (review)' in r.stderr


def test_ahead_of_review_starts_it_records_the_draft_and_finishes_to_review(tmp_path):
    p = ledger(tmp_path)
    r = nt(p, 'start', 'T-AGENT', '--ahead-of-review')
    assert r.returncode == 0 and 'rests on T-DRAFT' in r.stdout
    assert 'review note: started ahead of review on T-DRAFT' in nt(p, 'show', 'T-AGENT').stdout
    assert nt(p, 'finish', 'T-AGENT', '--verify-passed').returncode == 0
    assert status(p, 'T-AGENT') == 'review'                      # not done: a person signs it off


def test_it_is_approved_only_after_the_draft_it_rests_on(tmp_path):
    p = ledger(tmp_path)
    nt(p, 'start', 'T-AGENT', '--ahead-of-review')
    nt(p, 'finish', 'T-AGENT', '--verify-passed')
    r = nt(p, 'approve', 'T-AGENT', '--by', 'someone')
    assert r.returncode != 0 and 'T-DRAFT (review)' in r.stderr
    assert nt(p, 'approve', 'T-DRAFT', '--by', 'someone').returncode == 0
    assert nt(p, 'approve', 'T-AGENT', '--by', 'someone').returncode == 0
    assert status(p, 'T-AGENT') == 'done'


def test_a_rejection_keeps_it_ahead_so_it_never_finishes_to_done(tmp_path):
    p = ledger(tmp_path)
    nt(p, 'start', 'T-AGENT', '--ahead-of-review')
    nt(p, 'finish', 'T-AGENT', '--verify-passed')
    assert nt(p, 'reject', 'T-AGENT', '--reason', 'redo it').returncode == 0
    nt(p, 'finish', 'T-AGENT', '--verify-passed')
    assert status(p, 'T-AGENT') == 'review'


def test_the_flag_never_lets_a_task_rest_on_unfinished_work(tmp_path):
    p = ledger(tmp_path)
    r = nt(p, 'start', 'T-ON-BLOCKED', '--ahead-of-review')
    assert r.returncode != 0 and 'T-BLOCKED (blocked)' in r.stderr


def test_the_real_ledger_is_untouched_by_these_tests(tmp_path):
    before = open(LEDGER, encoding='utf-8').read()
    shutil.copy(LEDGER, tmp_path / 'copy.yaml')
    assert open(LEDGER, encoding='utf-8').read() == before
