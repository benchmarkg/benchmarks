"""Tests for scripts/check_rerun_policy.py (P8-S2-T04; 13-execution-runners.md S5.4).

The done_when: "The script exits non-zero if any gate-passing benchmark is no-third-party-endpoints, or is
contact-first without a recorded answer." No curated record can pass the runnable gate yet (its clauses 4 and 5 read
facts the schema does not carry), so the gate and the corpus are patched here with records of each policy; the
committed audit document is checked as CI would check it.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_rerun_policy as C  # noqa: E402
import runnable_gate  # noqa: E402

SCRIPT = os.path.join(ROOT, 'scripts', 'check_rerun_policy.py')
DOC = os.path.join(ROOT, 'docs', 'execution', 'rerun-policy-audit.md')


def record(rid, policy=None):
    ex = {} if policy is None else {'maintainer_rerun_policy': policy}
    return {'id': rid, 'execution': ex}


CORPUS = {'open-bench': record('open-bench', 'unrestricted'), 'closed-bench': record('closed-bench', 'no-third-party-endpoints'),
          'ask-bench': record('ask-bench', 'contact-first'), 'quiet-bench': record('quiet-bench', 'unstated'),
          'bare-bench': record('bare-bench'), 'outside-bench': record('outside-bench', 'no-third-party-endpoints')}


@pytest.fixture
def gate(monkeypatch):
    """The gate passes whatever ids a test names; the corpus is CORPUS."""
    def use(passing, answers_text=None, tmp=None):
        monkeypatch.setattr(runnable_gate, 'load', lambda root: CORPUS)
        monkeypatch.setattr(runnable_gate, 'run', lambda records, *a, **k: runnable_gate.Gate(len(records), [], list(passing)))
        args = ['--gate-passing']
        if answers_text is not None:
            path = tmp / 'maintainer-correspondence.md'
            path.write_text(answers_text, encoding='utf-8')
            args += ['--answers', str(path)]
        return args
    return use


TABLE = ('# Maintainer correspondence\n\n| benchmark | answer | date | responder |\n| --- | --- | --- | --- |\n%s')


def test_a_clean_gate_passing_set_exits_zero(gate, capsys):
    assert C.main(gate(['open-bench', 'quiet-bench', 'bare-bench'])) == 0
    out = capsys.readouterr().out
    assert 'no breach' in out and 'unstated                   2' in out


def test_no_third_party_endpoints_in_the_gate_passing_set_exits_non_zero(gate, capsys):
    assert C.main(gate(['open-bench', 'closed-bench'])) == 1
    out = capsys.readouterr().out
    assert 'BREACH  closed-bench is no-third-party-endpoints' in out and 'outside-bench' not in out


def test_contact_first_without_a_recorded_answer_exits_non_zero(gate, capsys, tmp_path):
    assert C.main(gate(['ask-bench'])) == 1                                  # no correspondence file at all
    assert 'ask-bench is contact-first with no recorded answer' in capsys.readouterr().out
    for row in ('| ask-bench | yes |  | Jane Maintainer |', '| ask-bench | yes | 2027-03-02 |  |'):
        assert C.main(gate(['ask-bench'], TABLE % row, tmp_path)) == 1        # a yes with no date, or no responder
        assert 'no recorded answer' in capsys.readouterr().out


def test_a_recorded_no_blocks_as_surely_as_silence(gate, capsys, tmp_path):
    assert C.main(gate(['ask-bench'], TABLE % '| ask-bench | no | 2027-03-02 | Jane Maintainer |', tmp_path)) == 1
    assert 'said no on 2027-03-02 (Jane Maintainer): drop it from the run set' in capsys.readouterr().out


def test_a_recorded_yes_clears_contact_first(gate, capsys, tmp_path):
    assert C.main(gate(['ask-bench'], TABLE % '| ask-bench | yes | 2027-03-02 | Jane Maintainer (Ask Bench) |', tmp_path)) == 0


def test_a_policy_outside_the_vocabulary_is_an_error():
    with pytest.raises(ValueError, match='is not one of'):
        C.policy_of(record('x', 'maybe'))
    assert C.policy_of(record('x')) == 'unstated' and C.policy_of({'id': 'y'}) == 'unstated'


def test_every_unstated_benchmark_is_listed_for_the_adr():
    a = C.audit(CORPUS, sorted(CORPUS), {}, 'every curated benchmark')
    assert a.unstated == ['bare-bench', 'quiet-bench']
    text = C.block(a, 0, len(CORPUS), None)
    assert '- `bare-bench`' in text and '- `quiet-bench`' in text and text.startswith(C.BEGIN)


def test_the_committed_audit_reproduces():
    r = subprocess.run([sys.executable, SCRIPT, '--gate-passing', '--check', DOC], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_tree_passes_the_verify():
    r = subprocess.run([sys.executable, SCRIPT, '--gate-passing'], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout
