"""Tests for scripts/check_no_get_default.py (P5-S4-T06; 07 S9.2).

The done_when: "The script exits 0 on the tree and 1 on a seeded violation". Both are run here
exactly as CI runs them, as a subprocess; the rule's edges are tested on source text directly.
"""
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from check_no_get_default import check_source, main  # noqa: E402

SCRIPT = os.path.join(ROOT, 'scripts', 'check_no_get_default.py')
SEEDED = os.path.join(ROOT, 'tests', 'fixtures', 'get-default', 'seeded')
WORKFLOW = os.path.join(ROOT, '.github', 'workflows', 'ingest-lint.yml')


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, cwd=ROOT)


def lint(src):
    return check_source(textwrap.dedent(src), 'x.py')


def test_the_tree_is_clean():
    r = cli('ingest/')
    assert r.returncode == 0, r.stdout
    assert '0 violation(s)' in r.stdout


def test_the_seeded_violation_fails():
    r = cli(SEEDED)
    assert r.returncode == 1
    assert "adapter.py:11:" in r.stdout and "row.get('Score', 0.0)" in r.stdout
    assert '1 violation(s)' in r.stdout


def test_the_tree_plus_the_seed_still_fails():
    assert cli('ingest/', SEEDED).returncode == 1


@pytest.mark.parametrize('src', [
    "x = row.get('a', 0)",
    "x = row.get('a', None)",               # an explicit None is still a default carried
    "x = row.get('a', default=0)",
    "x = self.payload['doc'].get('a', [])",
    "x = f(row.get('a', ''))",
    "x = row.get(\n    'a',\n    0,\n)",
])
def test_a_default_is_flagged(src):
    assert len(lint(src)) == 1


@pytest.mark.parametrize('src', [
    "x = row.get('a')",                     # None fails the schema; a default passes it
    "x = row['a']",
    "x = get('a', 0)",                      # a bare function, not a mapping method
    "x = getattr(row, 'a', 0)",
    "x = row.setdefault('a', 0)",
    "x = 'row.get(a, 0)'",                  # text, not a call
    "# row.get('a', 0) in a comment",
])
def test_no_default_is_not_flagged(src):
    assert lint(src) == []


def test_an_opt_out_with_a_reason_passes():
    assert lint("x = state.get(url, {})  # get-default: our own state; an unseen URL has no entry") == []


def test_an_opt_out_on_any_line_of_the_call_counts():
    assert lint("""\
        r = client.get(
            url,
            headers,  # get-default: an HTTP GET with request headers, not a lookup
        )
    """) == []


@pytest.mark.parametrize('comment', ['# get-default:', '# get-default: fine', '# get-default: ok then'])
def test_an_opt_out_without_a_real_reason_fails(comment):
    found = lint("x = row.get('a', 0)  " + comment)
    assert len(found) == 1 and 'needs a reason' in found[0][2]


def test_an_opt_out_on_another_line_does_not_count():
    assert len(lint("# get-default: our own state file here\nx = row.get('a', 0)")) == 1


def test_every_call_on_a_line_is_checked():
    assert len(lint("x = (a.get('k', 0), b.get('k', 1))")) == 2


def test_a_file_that_does_not_parse_fails(tmp_path):
    (tmp_path / 'broken.py').write_text('def f(:\n', encoding='utf-8')
    assert main([str(tmp_path)]) == 1


def test_a_missing_path_is_a_usage_error():
    assert cli('no/such/dir').returncode == 2


def test_pycache_is_not_scanned(tmp_path):
    (tmp_path / '__pycache__').mkdir()
    (tmp_path / '__pycache__' / 'x.py').write_text("row.get('a', 0)\n", encoding='utf-8')
    assert main([str(tmp_path)]) == 0


def test_the_ci_step_is_blocking():
    with open(WORKFLOW, encoding='utf-8') as f:
        text = f.read()
    try:
        from ruamel.yaml import YAML
        wf = YAML(typ='safe').load(text)
    except ImportError:
        import yaml
        wf = yaml.safe_load(text)
    triggers = wf.get('on') or wf.get(True)  # PyYAML reads the bare key `on` as True
    assert 'pull_request' in triggers and 'paths' not in (triggers['pull_request'] or {})
    job = wf['jobs']['structure-lint']
    assert not job.get('continue-on-error')
    steps = [s for s in job['steps'] if 'check_no_get_default.py' in s.get('run', '')]
    assert len(steps) == 1
    assert steps[0]['run'].strip() == 'python3 scripts/check_no_get_default.py ingest/'
    assert not steps[0].get('continue-on-error')
