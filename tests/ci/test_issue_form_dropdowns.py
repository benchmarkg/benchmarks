"""The issue-form dropdowns are generated from taxonomy/ and cannot drift (P2-S6-T01; 05 S6).

The verify: `python scripts/gen_issue_forms.py --check`. Done when: "Regeneration produces no diff and CI fails
if it would, so the form cannot drift from the controlled vocabulary." The cases run the script against a copy
of taxonomy/ and a fixture form: stale options fail --check, generation fixes them, the options are exactly the
vocabulary's live terms, and a vocabulary change makes a committed form stale again.
"""
import os
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, 'scripts', 'gen_issue_forms.py')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import gen_issue_forms as G  # noqa: E402

FORM = """name: New benchmark
description: Add a benchmark we do not have
body:
  # the generated dropdowns keep their own comments and every other key
  - type: input
    id: name
    attributes:
      label: Benchmark name
    validations:
      required: true
  - type: dropdown
    id: primary-domain
    attributes:
      label: Primary domain
      options:
        - stale (code/old-leaf)
    validations:
      required: true
  - type: dropdown
    id: capabilities
    attributes:
      label: Capabilities measured
      multiple: true
      options:
        - stale (old-term)
  - type: dropdown
    id: what-is-evaluated
    attributes:
      label: What is evaluated
      options:
        - model
        - agent scaffold
"""


def run(*args):
    return subprocess.run([sys.executable, GEN, *args], capture_output=True, text=True, encoding='utf-8')


@pytest.fixture
def tree(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    forms = tmp_path / '.github' / 'ISSUE_TEMPLATE'
    forms.mkdir(parents=True)
    (forms / 'new-benchmark.yml').write_text(FORM, encoding='utf-8', newline='\n')
    (forms / 'config.yml').write_text('blank_issues_enabled: false\n', encoding='utf-8', newline='\n')
    return tmp_path


def form(tree):
    return YAML(typ='safe').load((tree / '.github' / 'ISSUE_TEMPLATE' / 'new-benchmark.yml').read_text(encoding='utf-8'))


def dropdown(doc, ident):
    [item] = [i for i in doc['body'] if i.get('id') == ident]
    return item['attributes']['options']


def test_verify_the_repository_has_no_drift():
    r = run('--check')
    assert r.returncode == 0, r.stdout


def test_stale_options_fail_the_check_and_generation_fixes_them(tree):
    r = run('--root', str(tree), '--check')
    assert r.returncode == 1 and '.github/ISSUE_TEMPLATE/new-benchmark.yml' in r.stdout
    assert run('--root', str(tree)).returncode == 0
    assert run('--root', str(tree), '--check').returncode == 0


def test_the_options_are_the_vocabularys_live_terms(tree):
    run('--root', str(tree))
    doc = form(tree)
    y = YAML(typ='safe')
    domains = y.load((tree / 'taxonomy' / 'domains.yaml').read_text(encoding='utf-8'))['terms']
    caps = y.load((tree / 'taxonomy' / 'capabilities.yaml').read_text(encoding='utf-8'))['terms']
    want_d = [t['id'] for t in domains if t.get('parent') and t.get('status') != 'retired']
    want_c = [t['id'] for t in caps if t.get('status') != 'retired']
    got_d = [o.rsplit('(', 1)[1].rstrip(')') for o in dropdown(doc, 'primary-domain')]
    got_c = [o.rsplit('(', 1)[1].rstrip(')') for o in dropdown(doc, 'capabilities')]
    assert got_d == want_d and got_c == want_c
    assert all('/' in d for d in got_d)                             # families are navigational, never offered


def test_only_the_generated_dropdowns_change(tree):
    before = form(tree)
    run('--root', str(tree))
    after = form(tree)
    assert dropdown(after, 'what-is-evaluated') == dropdown(before, 'what-is-evaluated')
    assert [i['id'] for i in after['body']] == [i['id'] for i in before['body']]
    assert '# the generated dropdowns keep their own comments' in \
        (tree / '.github' / 'ISSUE_TEMPLATE' / 'new-benchmark.yml').read_text(encoding='utf-8')
    assert (tree / '.github' / 'ISSUE_TEMPLATE' / 'config.yml').read_text(encoding='utf-8') == 'blank_issues_enabled: false\n'


def test_a_vocabulary_change_makes_a_committed_form_stale(tree):
    run('--root', str(tree))
    p = tree / 'taxonomy' / 'capabilities.yaml'
    y = YAML()
    doc = y.load(p.read_text(encoding='utf-8'))
    doc['terms'].append({'id': 'brand-new-capability', 'label': 'Brand new capability', 'status': 'active'})
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)
    r = run('--root', str(tree), '--check')
    assert r.returncode == 1 and 'new-benchmark.yml' in r.stdout


def test_a_retired_term_is_never_offered(tree):
    p = tree / 'taxonomy' / 'capabilities.yaml'
    y = YAML()
    doc = y.load(p.read_text(encoding='utf-8'))
    retired = doc['terms'][0]['id']
    doc['terms'][0]['status'] = 'retired'
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)
    assert not any(o.endswith('(%s)' % retired) for o in G.option_sets(str(tree))['capabilities'])


def test_it_runs_in_job_5():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = YAML(typ='safe').load(fh)['jobs']['check-5-codegen']
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert 'uv run --locked --python "$PYTHON" python scripts/gen_issue_forms.py --check' in runs
