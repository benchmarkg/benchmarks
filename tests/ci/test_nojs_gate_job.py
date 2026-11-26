"""The no-JS render gate, as pr-validate.yml runs it (P2-S8-T02; 10 "Performance budget", 08 S8.3).

The verify is `cd site && npx playwright test tests/nojs.spec.ts --project=nojs`, and one step "Treat a regression
here as a citability regression and fail the job." What the gate checks, and the doctored pages it must go red on,
are site/tests/nojs.spec.ts's; this holds the size-budgets job to running it, blocking (test_size_budgets_job.py
holds every step of that job to that), over the draft-preview build the job already makes rather than a second
one, and holds scripts/route_fallback_map.json to naming every route family of scripts/route_groups.json.
"""
import json
import os
import re

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = 'npx playwright test tests/nojs.spec.ts --project=nojs'


@pytest.fixture(scope='module')
def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['size-budgets']


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_job_runs_the_gate_over_the_build_it_already_made(job):
    steps = job['steps']

    def at(run, where=None):
        [i] = [i for i, s in enumerate(steps) if s.get('run') == run and s.get('working-directory') == where]
        return i

    build = at('npx astro build', 'site')
    playwright = at('npm ci --ignore-scripts')                       # the root's, where @playwright/test is pinned
    browser = at('npx playwright install --with-deps --only-shell chromium')
    gate = at(GATE, 'site')
    assert build < playwright < browser < gate < at('npx size-limit', 'site')
    assert steps[gate]['env'] == {'UAIBI_SITE_BUILT': '1'}
    builds = [s['run'] for s in steps if 'run' in s and re.search(r'astro build|npm run build', s['run'])]
    assert builds == ['npx astro build'], 'the preview is built once, for both gates'


def test_the_config_previews_that_build_and_runs_the_spec_with_javascript_off():
    config = read('site', 'playwright.config.ts')
    assert "const BUILT = process.env.UAIBI_SITE_BUILT === '1';" in config
    assert re.search(r"command: \(BUILT \? '' : 'uv run python \.\./scripts/preview_corpus\.py", config)
    assert "{ name: 'nojs', testMatch: NOJS, use: { javaScriptEnabled: false } }" in config
    [nojs] = re.findall(r'^const NOJS = /(.+)/;$', config, re.M)
    assert re.search(nojs, 'tests/nojs.spec.ts') and re.search(nojs, 'tests/detail-nojs.spec.ts')


def test_the_fallback_map_names_every_route_family_in_order():
    groups = json.loads(read('scripts', 'route_groups.json'))
    fallbacks = json.loads(read('scripts', 'route_fallback_map.json'))
    assert [e['route'] for e in fallbacks['families']] == [f['route'] for g in groups['groups'] for f in g['families']]
    for e in fallbacks['families']:
        assert sum(k in e for k in ('selector', 'redirect', 'pending')) == 1, e
        assert 'selector' not in e or e['element'] in fallbacks['kinds'], e
