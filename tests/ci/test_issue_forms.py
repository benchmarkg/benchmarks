"""The five issue forms (P2-S6-T02; 05 S6, 05 S8).

The verify: `python scripts/gen_issue_forms.py --check && python scripts/validate_issue_forms.py`. These cases
run the validator on a copy of the committed forms with one thing broken each time, so every assertion it makes
is seen to fail at least once.
"""
import os
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATE = os.path.join(ROOT, 'scripts', 'validate_issue_forms.py')
GEN = os.path.join(ROOT, 'scripts', 'gen_issue_forms.py')
FORMS = ('new-benchmark.yml', 'correction.yml', 'new-claim.yml', 'dispute.yml', 'taxonomy-term.yml')
y = YAML()
y.width = 4096
y.indent(mapping=2, sequence=4, offset=2)


def run(script, *args):
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, encoding='utf-8')


@pytest.fixture
def tree(tmp_path):
    shutil.copytree(os.path.join(ROOT, '.github', 'ISSUE_TEMPLATE'), tmp_path / '.github' / 'ISSUE_TEMPLATE')
    return tmp_path


def edit(tree, name, fn):
    p = tree / '.github' / 'ISSUE_TEMPLATE' / name
    doc = y.load(p.read_text(encoding='utf-8'))
    fn(doc)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)


def item(doc, ident):
    [b] = [b for b in doc['body'] if b.get('id') == ident]
    return b


def test_verify_the_committed_forms_hold_and_their_dropdowns_are_current():
    a, b = run(GEN, '--check'), run(VALIDATE)
    assert a.returncode == 0, a.stdout
    assert b.returncode == 0, b.stdout


def test_all_five_exist_and_blank_issues_are_off():
    base = os.path.join(ROOT, '.github', 'ISSUE_TEMPLATE')
    assert sorted(f for f in os.listdir(base) if f != 'config.yml') == sorted(FORMS)
    with open(os.path.join(base, 'config.yml'), encoding='utf-8') as fh:
        assert YAML(typ='safe').load(fh)['blank_issues_enabled'] is False


@pytest.mark.parametrize('name, breaks, expect', [
    ('correction.yml', lambda d: item(d, 'quote')['validations'].update(required=False), 'quote is not marked required'),
    ('new-claim.yml', lambda d: d['body'].remove(item(d, 'source-url')), 'missing the required field source-url'),
    ('dispute.yml', lambda d: item(d, 'position')['attributes'].pop('description'), 'position has no hint text'),
    ('new-benchmark.yml', lambda d: item(d, 'attestation')['attributes']['options'].pop(1), "not 05 S6's two"),
    ('new-claim.yml', lambda d: item(d, 'attestation')['attributes']['options'][0].update(required=False),
     'no attestation checkbox'),
    ('correction.yml', lambda d: d['body'].remove(item(d, 'bot-disclosure')), 'no required bot disclosure'),
    ('dispute.yml', lambda d: item(d, 'bot-disclosure')['attributes']['options'][0].update(label='I agree'),
     'no required bot disclosure'),
    ('taxonomy-term.yml', lambda d: d['labels'].append('source:issue-form'), 'never auto-PRs'),
    ('new-benchmark.yml', lambda d: d['labels'].remove('source:issue-form'), 'no source:issue-form label'),
])
def test_each_property_fails_when_broken(tree, name, breaks, expect):
    edit(tree, name, breaks)
    r = run(VALIDATE, '--root', str(tree))
    assert r.returncode == 1 and expect in r.stdout, r.stdout


def test_the_new_benchmark_field_list_is_05s_in_its_order(tree):
    def swap(d):
        body = d['body']
        i, j = body.index(item(d, 'repository')), body.index(item(d, 'dataset-url'))
        body[i], body[j] = body[j], body[i]
    edit(tree, 'new-benchmark.yml', swap)
    r = run(VALIDATE, '--root', str(tree))
    assert r.returncode == 1 and "not 05 S6's list in its order" in r.stdout


def test_a_missing_form_fails(tree):
    (tree / '.github' / 'ISSUE_TEMPLATE' / 'dispute.yml').unlink()
    r = run(VALIDATE, '--root', str(tree))
    assert r.returncode == 1 and 'dispute.yml: missing' in r.stdout


def test_both_checks_run_in_job_5():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = YAML(typ='safe').load(fh)['jobs']['check-5-codegen']
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert 'uv run --locked --python "$PYTHON" python scripts/validate_issue_forms.py' in runs
