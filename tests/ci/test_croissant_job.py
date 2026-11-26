"""The croissant-benchmark check, as pr-validate.yml runs it (P4-S6-T04; 08 S5.8 "Validation in CI").

The verify is `uv run python scripts/check_croissant.py --all`, and the done-when: "Every document passes both
validators in CI and a deliberately broken schema turns the job red." What the check catches, and each deliberately
broken schema and document going red, are tests/test_check_croissant.py's; this holds the job to running the check
blocking, over every document (--all), with the locked environment, then that file, so a check that stops catching a
broken schema fails the job as well. Nothing in the job may weaken TLS or reach for the network: the check is offline.
"""
import os
import re

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECK = 'uv run --locked --python "$PYTHON" python scripts/check_croissant.py --all'
RED = 'uv run --locked --python "$PYTHON" python -m pytest -q tests/test_check_croissant.py'


@pytest.fixture(scope='module')
def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['croissant-benchmark']


def test_the_job_is_blocking(job):
    assert 'continue-on-error' not in job and 'if' not in job
    for step in job['steps']:
        assert 'continue-on-error' not in step and 'if' not in step, step
        assert not re.search(r'\|\|\s*(true|:|exit 0)', step.get('run', '')), step  # get-default: a uses: step has no run


def test_it_checks_every_document_then_shows_a_broken_schema_turning_it_red(job):
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert runs == [CHECK, RED]
    assert os.path.exists(os.path.join(ROOT, 'scripts', 'check_croissant.py'))
    assert os.path.exists(os.path.join(ROOT, 'tests', 'test_check_croissant.py'))


def test_nothing_in_it_weakens_tls_or_fetches(job):
    env = dict(job.get('env') or {})                                 # get-default: the job sets no env of its own
    for step in job['steps']:
        env.update(step.get('env') or {})                            # get-default: a step without an env block
    assert not [k for k in env if re.search(r'SSL|TLS|CA_BUNDLE|HTTPS?_VERIFY|CERT', k, re.I)], env
    with open(os.path.join(ROOT, 'scripts', 'check_croissant.py'), encoding='utf-8') as fh:
        src = fh.read()
    assert not re.search(r'^\s*(import|from)\s+(urllib|http|requests|socket|ssl)\b', src, re.M)
    assert 'verify=False' not in src and '_create_unverified_context' not in src
