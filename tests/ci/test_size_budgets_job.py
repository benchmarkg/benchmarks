"""The size gate, as pr-validate.yml runs it (P2-S8-T01; 08 S8.1, 10 "Performance budget").

The verify is `cd site && npx size-limit`, and the done-when: "All three budgets are enforced per route group and
the fixture that adds JS to a detail route turns the job red." What the gate measures, and the fixture going red,
are site/test/size-budgets.test.mjs's; this holds the job to running them blocking, over a build that has detail
pages in it: the draft preview's, since no entry is published yet and a build over build/corpus.json has none.
"""
import os
import re

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope='module')
def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['size-budgets']


def test_the_job_is_blocking(job):
    assert 'continue-on-error' not in job and 'if' not in job
    for step in job['steps']:
        assert 'continue-on-error' not in step and 'if' not in step, step
        assert not re.search(r'\|\|\s*(true|:|exit 0)', step.get('run', '')), step  # get-default: a uses: step has no run


def test_it_builds_over_the_draft_preview_then_runs_size_limit_and_the_fixture(job):
    runs = [s.get('run', '') for s in job['steps']]                  # get-default: a uses: step has no run
    preview = runs.index('uv run --locked --python "$PYTHON" python scripts/preview_corpus.py --out build/preview')
    build = runs.index('npx astro build')
    gate = runs.index('npx size-limit')
    fixture = runs.index('node --test test/size-budgets.test.mjs')
    assert preview < build < gate < fixture == len(runs) - 1
    env = job['steps'][build]['env']
    assert env['UAIBI_CORPUS'] == '../build/preview/corpus.json' and env['UAIBI_SITE_DRAFTS'] == '1'
    assert env['BENCH_PYTHON'].endswith('/.venv/bin/python')
    for i in (build, gate, fixture):
        assert job['steps'][i]['working-directory'] == 'site', runs[i]
    assert job['steps'][0]['with']['fetch-depth'] == 0                # tools/build/feed.py walks the history


def test_the_config_size_limit_finds_is_the_one_that_reads_the_route_groups():
    # size-limit's config search tries .size-limit.json before .size-limit.js: one beside it would shadow the gate.
    site = os.path.join(ROOT, 'site')
    assert not os.path.exists(os.path.join(site, '.size-limit.json')) and not os.path.exists(os.path.join(ROOT, '.size-limit.json'))
    with open(os.path.join(site, 'package.json'), encoding='utf-8') as fh:
        assert '"size-limit":' not in fh.read().split('"devDependencies"')[0], 'a size-limit key in package.json comes first too'
    with open(os.path.join(site, '.size-limit.js'), encoding='utf-8') as fh:
        assert "from '../scripts/route_groups.mjs'" in fh.read()
