"""Tests for `bench migrate` (P0-S5-T07; tools/migrate.py, schema/migrations/; 03 S9, 05 S3).

The verify: "`bench migrate 0000 --dry-run` prints a zero-row plan and exits 0, and `pytest
tests/cli/test_migrate.py` asserts --apply is refused when no matching ADR file exists and that a
split migration refuses to run unattended". Everything but the 0000 test runs against a temporary
root (a copy of the validate base fixture) and a temporary migrations directory, with cli.ROOT and
migrate.MIGRATIONS patched, so nothing in the repository's data/ or adr/ is touched.
"""
import os
import shutil
import sys
import textwrap

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.migrations import SENTINEL_PREFIX, sentinel, term_rows  # noqa: E402
from tools import cli, fmt, migrate  # noqa: E402

BASE = os.path.join(ROOT, 'tests', 'cli', 'fixtures', 'validate', 'base')
BENCH = 'data/benchmarks/code/example-bench.yaml'
OLD, NEW = 'code/repository-scale-se', 'code/bug-repair'
runner = CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch):
    root, migrations = tmp_path / 'root', tmp_path / 'migrations'
    shutil.copytree(BASE, root)
    (root / 'adr').mkdir()
    migrations.mkdir()
    monkeypatch.setattr(cli, 'ROOT', str(root))
    monkeypatch.setattr(migrate, 'MIGRATIONS', str(migrations))
    monkeypatch.delenv('CI', raising=False)
    return root, migrations


def script(migrations, name, kind, body):
    (migrations / name).write_text(textwrap.dedent('''\
        from schema.migrations import Row, sentinel, term_rows
        KIND = %r
        SUMMARY = 'a test migration'
        def plan(root):
        ''') % kind + textwrap.indent(textwrap.dedent(body), '    '), encoding='utf-8')


def adr(root, number, slug='a-decision'):
    (root / 'adr' / ('%s-%s.md' % (number, slug))).write_text(
        '# ADR-%s -- a decision\n\n- **Status:** Accepted\n' % number, encoding='utf-8')


def merge(migrations, number='0027'):
    script(migrations, '%s-merge-repo-scale.py' % number, 'merge', 'return term_rows(root, %r, %r)' % (OLD, NEW))


def split(migrations, number='0028', new='sentinel(%r)' % OLD):
    script(migrations, '%s-split-repo-scale.py' % number, 'split',
           'return [Row(r.path, r.at, r.old, %s) for r in term_rows(root, %r, "x")]' % (new, OLD))


def invoke(*args, **kw):
    return runner.invoke(cli.app, ['migrate', *args], **kw)


def text(root, rel=BENCH):
    return (root / rel).read_text(encoding='utf-8')


# ---- the verify ---------------------------------------------------------------------------------

def test_verify_0000_dry_run_prints_a_zero_row_plan_and_exits_0():
    res = invoke('0000', '--dry-run')
    assert res.exit_code == 0, res.output
    assert 'plan: 0 row(s) in 0 file(s)' in res.output and 'dry run: nothing written' in res.output


def test_verify_apply_is_refused_without_a_matching_adr(env):
    root, migrations = env
    merge(migrations)
    before = text(root)
    res = invoke('0027', '--apply')
    assert res.exit_code == 1 and 'has no ADR' in res.output and 'adr/0027-*.md' in res.output
    assert text(root) == before


def test_verify_the_repository_0000_apply_is_refused():
    res = invoke('0000', '--apply')
    assert res.exit_code == 1 and 'has no ADR' in res.output


def test_verify_a_split_refuses_to_run_unattended(env):
    root, migrations = env
    split(migrations)
    adr(root, '0028')
    before = text(root)
    res = invoke('0028', '--apply')                  # CliRunner's stdin is not a terminal
    assert res.exit_code == 1 and 'never applies unattended' in res.output and 'not a terminal' in res.output
    assert text(root) == before


def test_verify_a_split_refuses_in_ci_even_at_a_terminal(env, monkeypatch):
    root, migrations = env
    split(migrations)
    adr(root, '0028')
    monkeypatch.setattr(sys, 'stdin', type('Tty', (), {'isatty': lambda self: True})())
    monkeypatch.setenv('CI', 'true')
    assert migrate.unattended() == 'CI is set'
    with pytest.raises(migrate.MigrateError, match='never applies unattended'):
        migrate.apply(migrate.find('0028'), str(root), confirm=lambda m, rows: True)
    assert SENTINEL_PREFIX not in text(root)


# ---- dry run and apply --------------------------------------------------------------------------

def test_no_flag_is_a_dry_run(env):
    root, migrations = env
    merge(migrations)
    before = text(root)
    res = invoke('0027')
    assert res.exit_code == 0 and 'plan: 1 row(s) in 1 file(s)' in res.output
    assert "%s  domain.primary: %r -> %r" % (BENCH, OLD, NEW) in res.output
    assert text(root) == before


def test_dry_run_and_apply_are_exclusive(env):
    assert invoke('0000', '--dry-run', '--apply').exit_code == 2


def test_a_merge_applies_with_its_adr_and_keeps_the_file_formatted(env):
    root, migrations = env
    merge(migrations)
    adr(root, '0027', 'merge-repo-scale')
    comments = [line for line in text(root).splitlines() if line.lstrip().startswith('#')]
    res = invoke('0027', '--apply')
    assert res.exit_code == 0, res.output
    assert 'adr/0027-merge-repo-scale.md (Status: Accepted)' in res.output and 'wrote %s' % BENCH in res.output
    after = text(root)
    assert 'primary: %s' % NEW in after and OLD not in after
    assert [line for line in after.splitlines() if line.lstrip().startswith('#')] == comments
    assert fmt.format_text(after, fmt.model_for(BENCH)) == after          # still what `bench fmt` writes
    assert invoke('0027').output.count('plan: 0 row(s)') == 1              # applied: nothing left to do


def test_the_adr_must_be_unique(env):
    root, migrations = env
    merge(migrations)
    adr(root, '0027', 'one')
    adr(root, '0027', 'two')
    res = invoke('0027', '--apply')
    assert res.exit_code == 1 and '2 ADR files are numbered 0027' in res.output


# ---- splits -------------------------------------------------------------------------------------

def test_a_split_plan_writes_only_sentinels(env):
    root, migrations = env
    split(migrations)
    res = invoke('0028', '--dry-run')
    assert res.exit_code == 0 and repr(sentinel(OLD)) in res.output and 'needs a human at a terminal' in res.output


def test_a_split_that_guesses_is_refused_even_as_a_dry_run(env):
    root, migrations = env
    split(migrations, new=repr('code/bug-repair'))
    res = invoke('0028', '--dry-run')
    assert res.exit_code == 1 and 'which is a guess' in res.output


def test_an_attended_split_needs_the_number_typed_and_then_writes_sentinels(env, monkeypatch):
    root, migrations = env
    split(migrations)
    adr(root, '0028')
    monkeypatch.setattr(migrate, 'unattended', lambda: None)
    res = invoke('0028', '--apply', input='yes\n')
    assert res.exit_code == 1 and 'was not confirmed' in res.output and SENTINEL_PREFIX not in text(root)
    res = invoke('0028', '--apply', input='0028\n')
    assert res.exit_code == 0, res.output
    assert 'primary: %s' % sentinel(OLD) in text(root) and 'open the tracking issue' in res.output


# ---- the convention and the plan are checked ----------------------------------------------------

@pytest.mark.parametrize('number, files, expect', [
    ('27', [], 'four digits'),
    ('0027', [], 'no migration file(s) match'),
    ('0027', ['0027-a.py', '0027-b.py'], '2 migration file(s) match'),
])
def test_finding_a_migration(env, number, files, expect):
    _, migrations = env
    for f in files:
        script(migrations, f, 'noop', 'return []')
    res = invoke(number)
    assert res.exit_code == 1 and expect in res.output


@pytest.mark.parametrize('kind, body, expect', [
    ('shuffle', 'return []', 'needs KIND'),
    ('noop', 'return term_rows(root, %r, %r)' % (OLD, NEW), 'is a noop, and its plan changes 1 value'),
    ('merge', 'return [Row("../outside.yaml", ("id",), "a", "b")]', 'not a root-relative path'),
    ('merge', 'return ["not a row"]', 'not a Row'),
])
def test_a_malformed_migration_is_refused(env, kind, body, expect):
    _, migrations = env
    script(migrations, '0027-bad.py', kind, body)
    res = invoke('0027')
    assert res.exit_code == 1 and expect in res.output


def test_a_stale_plan_writes_nothing(env):
    """Two files, the second row stale: the first file is not written either."""
    root, migrations = env
    script(migrations, '0027-stale.py', 'merge', '''\
        rows = term_rows(root, %r, %r)
        return rows + [Row('data/metrics/accuracy.yaml', ('name',), 'Not Accuracy', 'Acc')]
        ''' % (OLD, NEW))
    adr(root, '0027')
    before = text(root)
    res = invoke('0027', '--apply')
    assert res.exit_code == 1 and 'the plan is stale' in res.output
    assert text(root) == before


def test_term_rows_finds_every_whole_value_occurrence(env):
    root, _ = env
    rows = term_rows(str(root), OLD, NEW)
    assert [(r.path, r.at) for r in rows] == [(BENCH, ('domain', 'primary'))]
    assert term_rows(str(root), 'code', 'x') == []           # a whole value, never a substring


def test_the_repository_0000_is_a_valid_noop():
    m = migrate.find('0000')
    assert m.kind == 'noop' and m.plan(ROOT) == []
