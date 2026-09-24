"""Tests for scripts/throughput_report.py over the synthetic histories in tests/fixtures/throughput/.

Each *.history file is replayed into a real git repository in tmp_path, one commit per line with
that line's committer date, so the report's own `git log` parsing is what is under test. The live
repository cannot serve: its only entries are the Phase-0 stress cases, so rule (c) there is an
artifact of when those landed (P1-S2-T07's verify says why).
"""
import importlib.util
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, 'tests', 'fixtures', 'throughput')
AS_OF = '2026-02-04'  # a Wednesday in ISO week 2026-W06; W02-W05 are the four complete weeks

spec = importlib.util.spec_from_file_location('throughput_report', os.path.join(ROOT, 'scripts', 'throughput_report.py'))
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)


def git(repo, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME='fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, env=env)


def commit_adding(repo, when, paths, msg='add'):
    for p in paths:
        f = repo / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('id: %s\n' % f.stem, encoding='utf-8')
        git(repo, 'add', p)
    git(repo, 'commit', '-q', '-m', msg, when=when)


def replay(tmp_path, name):
    repo = tmp_path / name
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'config', 'commit.gpgsign', 'false')
    rows = []
    for line in open(os.path.join(FIXTURES, name + '.history'), encoding='utf-8'):
        if line.strip() and not line.startswith('#'):
            when, *paths = line.split()
            rows.append((when, paths))
    for when, paths in sorted(rows):
        commit_adding(repo, when, paths)
    return repo


def test_check_fires_rule_c_on_the_below_history(tmp_path, capsys):
    repo = replay(tmp_path, 'below')
    assert tr.main(['--repo', str(repo), '--as-of', AS_OF, '--check']) == 1
    out = capsys.readouterr().out
    assert 'STOPPING RULE (c)' in out
    assert '2026-01-05: 3, 2026-01-12: 4, 2026-01-19: 2, 2026-01-26: 4' in out


def test_check_is_silent_on_the_above_history(tmp_path, capsys):
    repo = replay(tmp_path, 'above')
    assert tr.main(['--repo', str(repo), '--as-of', AS_OF, '--check']) == 0
    assert 'STOPPING RULE' not in capsys.readouterr().out


def test_the_partial_current_week_and_non_entries_are_not_counted(tmp_path):
    repo = replay(tmp_path, 'below')
    weeks = dict(tr.weekly(tr.merged_entries(str(repo)), tr.date.fromisoformat(AS_OF)))
    assert [weeks[tr.date(2026, 1, d)] for d in (5, 12, 19, 26)] == [3, 4, 2, 4]  # _family-scoping.yaml excluded
    assert weeks[tr.date(2026, 2, 2)] == 9  # shown in the table, but never judged


def test_rendering_twice_is_byte_identical(tmp_path):
    repo = replay(tmp_path, 'below')
    a, b = tmp_path / 'a.md', tmp_path / 'b.md'
    tr.main(['--repo', str(repo), '--as-of', AS_OF, '--out', str(a)])
    tr.main(['--repo', str(repo), '--as-of', AS_OF, '--out', str(b)])
    assert a.read_bytes() == b.read_bytes()
    text = a.read_text(encoding='utf-8')
    assert '**Rule (c): FIRES.**' in text and '(mean 3.25 a week)' in text
    assert '| 2026-W06 | 2026-02-02 | 9 | 22 |' in text


def test_a_merge_counts_once_on_the_day_it_lands_on_main(tmp_path):
    repo = tmp_path / 'merge'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    commit_adding(repo, '2026-01-05T09:00:00Z', ['README'])
    git(repo, 'checkout', '-q', '-b', 'curation')
    commit_adding(repo, '2026-01-06T09:00:00Z', ['data/benchmarks/code/x.yaml'])  # W02 on the branch
    git(repo, 'checkout', '-q', 'main')
    git(repo, 'merge', '-q', '--no-ff', '-m', 'merge', 'curation', when='2026-01-13T09:00:00Z')  # W03 on main
    first = tr.merged_entries(str(repo))
    assert list(first) == ['data/benchmarks/code/x.yaml']
    assert first['data/benchmarks/code/x.yaml'].date() == tr.date(2026, 1, 13)


def test_a_rename_is_not_a_new_entry(tmp_path):
    repo = tmp_path / 'rename'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    commit_adding(repo, '2026-01-06T09:00:00Z', ['data/benchmarks/code/old.yaml'])
    (repo / 'data/benchmarks/physics').mkdir(parents=True)
    git(repo, 'mv', 'data/benchmarks/code/old.yaml', 'data/benchmarks/physics/old.yaml')
    git(repo, 'commit', '-q', '-m', 'move', when='2026-01-20T09:00:00Z')
    assert len(tr.merged_entries(str(repo))) == 1


def test_fewer_than_four_complete_weeks_never_fires(tmp_path, capsys):
    repo = tmp_path / 'young'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    commit_adding(repo, '2026-01-27T09:00:00Z', ['data/benchmarks/code/a.yaml'])
    assert tr.main(['--repo', str(repo), '--as-of', AS_OF, '--check']) == 0
    assert 'not yet assessable, 1 of 4' in capsys.readouterr().out


@pytest.mark.parametrize('counts, fires', [((4, 4, 4, 4), True), ((4, 4, 4, 5), False), ((0, 0, 0, 12), False)])
def test_the_rule_is_each_week_below_five_not_the_mean(counts, fires):
    mondays = [tr.date(2026, 1, d) for d in (5, 12, 19, 26)]
    weeks = list(zip(mondays, counts)) + [(tr.date(2026, 2, 2), 0)]
    assert (tr.verdict(weeks, tr.date.fromisoformat(AS_OF))[0] == 'fires') is fires
