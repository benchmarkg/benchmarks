"""Check 5, the codegen drift check, as pr-validate.yml runs it (P0-S6-T02; 05 S9, 04 S12).

The verify: "`pytest tests/ci/test_codegen_drift.py` asserts the workflow fails a branch where a Pydantic
field was added without regenerating, and fails a branch where only a taxonomy/*.yaml term changed".

Check 5 is job `check-5-codegen` of pr-validate.yml, not a workflow of its own: the maintainer keeps only
pr-validate enabled (2026-10-12), and schema-codegen.yml, which ran the same command alone, was folded in
here as its own header said it would be. The structural tests read the job; the drift tests run the job's
own command, read out of the workflow, in a throwaway copy of the tree (schema/, taxonomy/, tools/ and the
committed artifacts) that a "branch" has edited. tests/test_codegen.py covers `bench schema gen` itself.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOWS = os.path.join(ROOT, '.github', 'workflows')
JSON2TS = os.path.join(ROOT, 'site', 'node_modules', 'json-schema-to-typescript')
needs_node = pytest.mark.skipif(shutil.which('node') is None or not os.path.isdir(JSON2TS),
                                reason='node and site/node_modules (npm ci in site/) are needed for the TS step')


@pytest.fixture(scope='module')
def wf():
    with open(os.path.join(WORKFLOWS, 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)


@pytest.fixture(scope='module')
def job5(wf):
    [(key, body)] = [(k, v) for k, v in wf['jobs'].items() if k.startswith('check-5-')]
    assert key == 'check-5-codegen' and body['name'].startswith('5 ')
    return body


def command(job5) -> list[str]:
    """The bench arguments of the job's check step."""
    [run] = [s['run'] for s in job5['steps'] if 'bench schema gen' in s.get('run', '')]  # get-default: a uses: step has no run
    assert run.startswith('uv run --locked --python "$PYTHON" bench '), run
    return run.split(' bench ', 1)[1].split()


# ---- the job exists, blocks, and runs on every change ------------------------------------------

def test_job_5_runs_the_drift_check(job5):
    assert command(job5) == ['schema', 'gen', '--check']


def test_job_5_is_blocking(job5):
    assert 'continue-on-error' not in job5 and 'if' not in job5
    for step in job5['steps']:
        assert 'continue-on-error' not in step and 'if' not in step, step
        assert not re.search(r'\|\|\s*(true|:|exit 0)', step.get('run', '')), step['run']  # get-default: a uses: step has no run


def test_job_5_has_the_typescript_generator(job5):
    """The TS half needs node and the site lockfile's json-schema-to-typescript."""
    uses = [s['uses'] for s in job5['steps'] if 'uses' in s]
    assert any(u.startswith('actions/setup-node@') for u in uses)
    [npm] = [s for s in job5['steps'] if s.get('run', '').startswith('npm ci')]  # get-default: a uses: step has no run
    assert npm['working-directory'] == 'site'


def test_job_5_typechecks_the_site_against_the_generated_interfaces(job5):
    """P2-S1-T03: the site's code is held to src/types/ on the same pull request that regenerates it."""
    site = [s['run'] for s in job5['steps'] if s.get('working-directory') == 'site' and 'run' in s]  # get-default: a uses: step has no working-directory
    assert site == ['npm ci --ignore-scripts', 'npx astro sync', 'npx tsc --noEmit']


def test_it_runs_on_schema_and_taxonomy_changes_alike(wf):
    """No path filter: a pull request touching only taxonomy/ runs it as surely as one touching schema/."""
    on = wf['on']
    assert on['pull_request'] in (None, {}) and on['push'] == {'branches': ['main']}


def test_no_second_workflow_runs_the_same_check():
    others = [f for f in os.listdir(WORKFLOWS) if f.endswith('.yml') and f != 'pr-validate.yml'
              and 'bench schema gen' in open(os.path.join(WORKFLOWS, f), encoding='utf-8').read()]
    assert others == []


# ---- the verify: the job's command fails both kinds of drift ------------------------------------

@pytest.fixture
def tree(tmp_path):
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
    for d in ('schema', 'taxonomy', 'tools'):
        shutil.copytree(os.path.join(ROOT, d), tmp_path / d, ignore=ignore)
    shutil.copytree(os.path.join(ROOT, 'site', 'src', 'types'), tmp_path / 'site' / 'src' / 'types')
    return tmp_path


def run_job(tree, job5):
    return subprocess.run([sys.executable, os.path.join(str(tree), 'tools', 'cli.py'), *command(job5),
                           '--json2ts', JSON2TS], capture_output=True, text=True, encoding='utf-8', cwd=str(tree))


@needs_node
def test_verify_the_job_fails_a_branch_that_adds_a_field_without_regenerating(tree, job5):
    assert run_job(tree, job5).returncode == 0                                     # main: clean
    p = tree / 'schema' / 'benchmark.py'
    s = p.read_text(encoding='utf-8')
    anchor = '    release_venue: Text | None = None\n'
    assert s.count(anchor) == 1
    p.write_text(s.replace(anchor, anchor + '    release_city: Text | None = None\n'), encoding='utf-8')
    r = run_job(tree, job5)
    assert r.returncode == 1 and 'differs  schema/generated/benchmark.schema.json' in r.stderr, r.stderr


@needs_node
def test_verify_the_job_fails_a_branch_that_only_changes_a_taxonomy_term(tree, job5):
    y = YAML()
    p = tree / 'taxonomy' / 'lifecycle.yaml'
    doc = y.load(p.read_text(encoding='utf-8'))
    term = next(t for t in doc['terms'] if t['field'] == 'activity' and t['id'] == 'between-rounds')
    term['id'] = 'between-editions'                      # schema/ untouched: only the vocabulary moved
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)
    r = run_job(tree, job5)
    assert r.returncode == 1 and 'differs  schema/generated/benchmark.schema.json' in r.stderr, r.stderr
