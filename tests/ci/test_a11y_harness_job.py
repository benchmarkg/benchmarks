"""The accessibility harness, as pr-validate.yml runs it (P2-S8-T03; 09 S8, S13; 14 Phase 2 exit criterion 8).

The verify is `cd site && npx playwright test tests/a11y.spec.ts`, and the done-when: "The harness runs axe-core and
pa11y over all eight archetypes in light, dark, forced-colors and prefers-contrast more, and fails the job on any
violation." What the harness checks, and the new violation it must go red on, are site/tests/a11y.spec.ts's; this holds
the size-budgets job to running it, blocking (test_size_budgets_job.py holds every step of that job to that), over the
draft-preview build the job already makes, with its data files in place, and holds the files it reads to their shape:
the eight archetypes and four modes, a baseline that names nothing else, and the two tools pinned where @playwright/test
is, with puppeteer told never to download a browser of its own.
"""
import json
import os
import re

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HARNESS = 'npx playwright test tests/a11y.spec.ts'
EIGHT = ['landing', 'benchmark-detail', 'taxonomy-term', 'browse', 'atlas', 'methodology', 'search', 'contribute']
FOUR = ['light', 'dark', 'forced-colors', 'contrast-more']


@pytest.fixture(scope='module')
def job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh)['jobs']['size-budgets']


def read_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return json.load(fh)


def test_the_job_runs_the_harness_over_the_build_it_already_made(job):
    steps = job['steps']

    def at(run, where=None):
        [i] = [i for i, s in enumerate(steps) if s.get('run') == run and s.get('working-directory') == where]
        return i

    build = at('npx astro build', 'site')
    data = at('uv run --locked --python "$PYTHON" python tools/build/manifest.py --site site/dist --build build/preview')
    root = at('npm ci --ignore-scripts')                              # the root's: @playwright/test, axe, pa11y
    browser = at('npx playwright install --with-deps --only-shell chromium')
    harness = at(HARNESS, 'site')
    assert build < data < harness, 'the pages run with JavaScript on, so the hashed data files are in dist/ first'
    assert root < browser < harness < at('npx size-limit', 'site')
    assert steps[harness]['env'] == {'UAIBI_SITE_BUILT': '1'}
    builds = [s['run'] for s in steps if 'run' in s and re.search(r'astro build|npm run build', s['run'])]
    assert builds == ['npx astro build'], 'the preview is built once, for every gate of the job'
    installs = [s['run'] for s in steps if 'playwright install' in s.get('run', '')]
    assert installs == ['npx playwright install --with-deps --only-shell chromium'], 'pa11y drives the same browser'
    assert job['steps'][0]['with']['fetch-depth'] == 0, 'the baseline is compared with the one on the base branch'


def test_the_tools_are_pinned_beside_playwright_and_puppeteer_downloads_nothing():
    pkg = read_json('package.json')
    dev = pkg['devDependencies']
    for name in ('@playwright/test', '@axe-core/playwright', 'pa11y'):
        assert re.fullmatch(r'\d+\.\d+\.\d+', dev[name]), (name, dev[name])
    assert pkg['puppeteer'] == {'skipDownload': True}
    lock = read_json('package-lock.json')['packages']
    assert lock['']['devDependencies'] == dev
    for name in ('@axe-core/playwright', 'pa11y'):
        assert lock['node_modules/' + name]['version'] == dev[name], name
    site = read_json('site', 'package.json')
    assert site['scripts']['test:a11y'] == 'node test/a11y/run.mjs'
    assert not {'@axe-core/playwright', 'pa11y', 'puppeteer'} & set(site.get('devDependencies', {}) | site['dependencies'])


def test_the_archetypes_are_the_eight_in_the_four_modes_and_the_baseline_names_nothing_else():
    spec = read_json('site', 'test', 'a11y', 'archetypes.json')
    assert [a['name'] for a in spec['archetypes']] == EIGHT
    assert list(spec['modes']) == FOUR
    assert spec['modes']['dark']['colorScheme'] == 'dark' and spec['modes']['forced-colors']['forcedColors'] == 'active'
    assert spec['modes']['contrast-more']['contrast'] == 'more'
    assert 'wcag22aa' in spec['standard']['axe'] and spec['standard']['pa11y'] == 'WCAG2AA'
    groups = read_json('scripts', 'route_groups.json')
    families = [f['route'] for g in groups['groups'] for f in g['families']]
    fallbacks = {e['route']: e for e in read_json('scripts', 'route_fallback_map.json')['families']}
    for a in spec['archetypes']:
        assert a['family'] in families, a
        assert 'selector' in fallbacks[a['family']], 'the page is known by its family element: %s' % a['name']
    baseline = read_json('site', 'test', 'a11y', 'baseline.json')
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', baseline['recorded'])
    for name, modes in baseline['known'].items():
        assert name in EIGHT and set(modes) <= set(FOUR), (name, list(modes))
        for keys in modes.values():
            assert keys == sorted(set(keys)) and all(re.fullmatch(r'(axe|pa11y) \S+ \S+', k) for k in keys), keys
