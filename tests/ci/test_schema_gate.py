"""The ADR-plus-migration gate on schema diffs (P0-S6-T07; GOVERNANCE.md, 05 S5, 05 S9, 03 S9).

The verify: "`pytest tests/ci/test_schema_gate.py` asserts `python scripts/check_schema_change_gate.py` exits
1 on a branch touching schema/*.py with no ADR and no migration, exits 1 with only one of the two, and exits
0 with both". Each case is a throwaway git repository whose main holds a schema module, a vocabulary, an
ADR and a migration, and whose branch `pr` changes something.
"""
import os
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = os.path.join(ROOT, 'scripts', 'check_schema_change_gate.py')

MODULE = '''"""A schema module."""
from pydantic import BaseModel


class Benchmark(BaseModel):
    """A benchmark."""
    id: str
    name: str
'''
VOCAB = '''version: 0.9.0
terms:
  - id: planning
    label: Planning
    status: active
    definition: Choosing actions toward a goal.
'''


def git(repo, *args):
    return subprocess.run(['git', '-c', 'user.name=ci-test', '-c', 'user.email=ci-test@example.invalid', *args],
                          cwd=repo, check=True, capture_output=True, text=True).stdout


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='\n')


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'repo'
    write(r, 'schema/benchmark.py', MODULE)
    write(r, 'taxonomy/capabilities.yaml', VOCAB)
    write(r, 'adr/0007-an-old-decision.md', '# ADR-0007\n')
    write(r, 'schema/migrations/0007-an-old-decision.py', "KIND = 'noop'\n")
    git(r, 'init', '-q', '-b', 'main')
    git(r, 'add', '-A')
    git(r, 'commit', '-q', '-m', 'main')
    git(r, 'switch', '-q', '-c', 'pr')
    return r


def gate(repo):
    r = subprocess.run([sys.executable, GATE, '--root', str(repo), '--base', 'main', '--head', 'HEAD'],
                       capture_output=True, text=True, encoding='utf-8')
    return r.returncode, r.stdout


def add_field(repo):
    write(repo, 'schema/benchmark.py', MODULE + '    tagline: str | None = None\n')


def commit(repo, msg='change'):
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', msg)


# ---- the verify -----------------------------------------------------------------------------------

def test_verify_a_schema_change_with_no_adr_and_no_migration_fails(repo):
    add_field(repo)
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'schema/benchmark.py' in out
    assert 'no ADR is added' in out and 'no migration is added or edited' in out


def test_verify_an_adr_alone_fails(repo):
    add_field(repo)
    write(repo, 'adr/0024-add-tagline.md', '# ADR-0024\n')
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'no migration is added or edited' in out and 'no ADR' not in out


def test_verify_a_migration_alone_fails(repo):
    add_field(repo)
    write(repo, 'schema/migrations/0024-add-tagline.py', "KIND = 'field'\n")
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'no ADR is added' in out and 'no migration' not in out


def test_verify_both_pass(repo):
    add_field(repo)
    write(repo, 'adr/0024-add-tagline.md', '# ADR-0024\n')
    write(repo, 'schema/migrations/0024-add-tagline.py', "KIND = 'field'\n")
    commit(repo)
    code, out = gate(repo)
    assert code == 0 and 'the ADR and its migration are in the diff' in out


# ---- what counts -----------------------------------------------------------------------------------

def test_the_numbers_must_match(repo):
    add_field(repo)
    write(repo, 'adr/0024-add-tagline.md', '# ADR-0024\n')
    write(repo, 'schema/migrations/0025-add-tagline.py', "KIND = 'field'\n")
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'different numbers' in out


def test_an_old_adr_edited_does_not_count_but_an_old_migration_edited_does(repo):
    add_field(repo)
    write(repo, 'adr/0007-an-old-decision.md', '# ADR-0007, amended\n')            # edited, not added
    write(repo, 'schema/migrations/0007-an-old-decision.py', "KIND = 'field'\n")
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'no ADR is added' in out


def test_a_docstring_or_comment_edit_is_not_a_schema_change(repo):
    write(repo, 'schema/benchmark.py', MODULE.replace('"""A benchmark."""', '"""A benchmark, reworded."""')
          + '# a trailing comment\n')
    commit(repo)
    code, out = gate(repo)
    assert code == 0 and 'no schema or taxonomy change' in out


def test_a_new_term_is_a_taxonomy_change(repo):
    write(repo, 'taxonomy/capabilities.yaml', VOCAB + '  - id: tool-use\n    label: Tool use\n    status: active\n'
                                                       '    definition: Calling tools.\n')
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'taxonomy/capabilities.yaml' in out


def test_a_definition_edit_is_not(repo):
    write(repo, 'taxonomy/capabilities.yaml', VOCAB.replace('toward a goal', 'toward a stated goal'))
    commit(repo)
    assert gate(repo)[0] == 0


def test_a_profile_rule_is_a_taxonomy_change(repo):
    prof = 'version: 0.1.0\nprofiles:\n  - id: forecasting\n    material: [lead_time]\n    applies_to:\n      - [statistical-fit, base-model]\n'
    write(repo, 'taxonomy/comparability-profiles.yaml', prof)
    commit(repo, 'add profiles')
    git(repo, 'switch', '-q', 'main')
    git(repo, 'merge', '-q', '--ff-only', 'pr')
    git(repo, 'switch', '-q', '-c', 'pr2')
    write(repo, 'taxonomy/comparability-profiles.yaml', prof.replace('[statistical-fit, base-model]',
                                                                     '[statistical-fit, scientific-surrogate-model]'))
    commit(repo)
    code, out = gate(repo)
    assert code == 1 and 'taxonomy/comparability-profiles.yaml' in out


def test_files_outside_schema_and_taxonomy_never_trigger(repo):
    write(repo, 'tools/build.py', 'x = 1\n')
    write(repo, 'schema/migrations/0007-an-old-decision.py', "KIND = 'merge'\n")        # migrations are not schema
    commit(repo)
    assert gate(repo)[0] == 0


def test_the_repository_branch_passes():
    r = subprocess.run([sys.executable, GATE, '--base', 'origin/main'], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stdout + r.stderr


def test_it_runs_as_a_blocking_job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs']['check-schema-gate']
    assert 'continue-on-error' not in body and 'if' not in body
    [run] = [s['run'] for s in body['steps'] if 'run' in s]
    assert run == 'uv run --locked --python "$PYTHON" python scripts/check_schema_change_gate.py --base "$GATE_BASE"'
    [checkout] = [s for s in body['steps'] if s.get('uses', '').startswith('actions/checkout@')]  # get-default: a run: step has no uses
    assert checkout['with']['fetch-depth'] == 0
