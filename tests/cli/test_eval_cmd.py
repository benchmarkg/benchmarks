"""`bench eval` (P6-S3-T09; 05 S3, 11 S7). The task's verify is `bench eval --split all --report`.

Over the repository every gold label is still null (P6-S3-T08), so the verify must say plainly that nothing can be
graded, print no number and write no results file. The retrieval half is replaced by two tiny synthetic
configurations over a three-entry corpus, so the test does not spend the minutes a full catalogue build takes;
tests/evals/test_eval_harness.py runs the real configurations' code and grades a synthetic labelled fixture.
"""
import glob
import os
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli  # noqa: E402
from tools.evals import retrieval  # noqa: E402

runner = CliRunner()
RESULTS = os.path.join(ROOT, 'evals', 'results', '*.json')


@pytest.fixture
def offline(monkeypatch):
    """No key, and a three-entry corpus with two configurations that rank it the same way for every query."""
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    corpus = retrieval.Corpus(rows=[{'id': i, 'name': i, 'aliases': [], 'editions': []} for i in ('a', 'b', 'c')],
                              records={}, drafts=True)
    monkeypatch.setattr(retrieval, 'build_corpus', lambda root: corpus)

    def runs(c, queries, root):
        ranked = {q: [(0, 1.0), (1, 0.5)] for q in queries}
        return [retrieval.Run('lexical', ranked=ranked), retrieval.Run('dense', reason='no model in this test')]
    monkeypatch.setattr(retrieval, 'runs', runs)


def test_the_verify_says_nothing_can_be_graded_and_prints_no_number(offline):
    before = set(glob.glob(RESULTS))
    r = runner.invoke(cli.app, ['eval', '--split', 'all', '--report'])
    assert r.exit_code == 0, r.output
    assert 'Nothing can be graded yet. 0 of 40 gold labels are set' in r.output
    assert '## Metrics' not in r.output and 'recall@20 |' not in r.output and 'eval: wrote' not in r.output
    assert '## The pool to grade' in r.output and '- nl_search-01 (2): a, b' in r.output
    assert 'ANTHROPIC_API_KEY is not set' in r.output and 'claude-' in r.output       # the model ids, from the config
    assert set(glob.glob(RESULTS)) == before


def test_without_report_it_prints_a_summary(offline):
    r = runner.invoke(cli.app, ['eval'])
    assert r.exit_code == 0, r.output
    assert r.output.startswith('eval: golden set v0') and 'Nothing can be graded yet' in r.output
    assert 'configurations lexical ran, dense not run' in r.output


def test_a_split_without_entries_to_pool_builds_no_corpus(monkeypatch):
    def boom(root):
        raise AssertionError('facet_translation pools nothing, so nothing is built')
    monkeypatch.setattr(retrieval, 'build_corpus', boom)
    r = runner.invoke(cli.app, ['eval', '--split', 'facet_translation', '--report', '--judge'])
    assert r.exit_code == 0, r.output
    assert 'Nothing can be graded yet. 0 of 12' in r.output and '## The pool to grade' not in r.output
    assert '--judge, self-eval-judge' in r.output


@pytest.mark.parametrize('args', [['--split', 'everything'], ['--split', 'abstention', '--holdout', '4'],
                                  ['--holdout', '-1']])
def test_usage_errors_exit_2(args, offline):
    r = runner.invoke(cli.app, ['eval', *args])
    assert r.exit_code == 2, r.output
