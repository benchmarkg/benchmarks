"""The ten stress entries as permanent CI fixtures (P0-S9-T01; 14-roadmap Phase 0 exit criterion 1, 04 S15).

The verify: "`pytest tests/test_stress_entries.py` passes: all ten entries validate at --tier all with zero
errors, and the test fails if any entry is removed from the fixture set". tests/fixtures/stress-entries.yaml
names the ten entries of 14-roadmap.md's stress-test table by their live paths under data/, with every
Source each one cites. This file validates the whole corpus at --tier all once and asserts that no blocking
finding falls on any of those files; it pins the set to the roadmap's ten; and it holds the manifest to the
entries, so a Source cited later is added to the fixture set rather than silently left out of it.

pr-validate.yml runs it as a blocking job, so exit criterion 1 is a test on every commit rather than a
one-off check.
"""
import os
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.validate import tiers  # noqa: E402

MANIFEST = os.path.join(ROOT, 'tests', 'fixtures', 'stress-entries.yaml')
# 14-roadmap.md "The stress-test entry table", in its order: SWE-bench, CASP17, RoboArena, WeatherBench 2,
# Matbench Discovery, ARC-AGI-3, Virtual Cell Challenge 2026, Kaggle Game Arena, ForecastBench, PaperBench.
THE_TEN = ('swe-bench', 'casp', 'roboarena', 'weatherbench-2', 'matbench-discovery', 'arc-agi-3',
           'virtual-cell-challenge', 'kaggle-game-arena', 'forecastbench', 'paperbench')


@pytest.fixture(scope='module')
def manifest():
    return read_yaml(MANIFEST)['entries']


@pytest.fixture(scope='module')
def report():
    return tiers.run(ROOT, 'all')


def source_paths(ids):
    out = {}
    for sid in ids:
        hits = [os.path.join(d, sid + '.yaml') for d, _, files in os.walk(os.path.join(ROOT, 'data', 'sources'))
                if sid + '.yaml' in files]
        out[sid] = os.path.relpath(hits[0], ROOT).replace(os.sep, '/') if hits else None
    return out


# ---- the set is the roadmap's ten ------------------------------------------------------------------

def test_verify_the_fixture_set_is_the_roadmaps_ten(manifest):
    assert tuple(e['id'] for e in manifest) == THE_TEN


def test_verify_removing_an_entry_fails(manifest):
    """The check above is what fails; this states it against a manifest with one entry dropped."""
    shorter = [e for e in manifest if e['id'] != 'casp']
    assert tuple(e['id'] for e in shorter) != THE_TEN


@pytest.mark.parametrize('ident', THE_TEN)
def test_each_entry_is_its_live_file_and_loads(manifest, ident):
    [e] = [e for e in manifest if e['id'] == ident]
    full = os.path.join(ROOT, *e['path'].split('/'))
    assert os.path.isfile(full), e['path']
    b = load_benchmark(full)
    assert b.id == ident


@pytest.mark.parametrize('ident', THE_TEN)
def test_the_manifest_lists_every_source_the_entry_cites(manifest, ident):
    [e] = [e for e in manifest if e['id'] == ident]
    b = load_benchmark(os.path.join(ROOT, *e['path'].split('/')))
    assert e['sources'] == b.curation.source_ids()
    missing = [sid for sid, p in source_paths(e['sources']).items() if p is None]
    assert missing == [], 'cited but not under data/sources/: %s' % missing


# ---- zero errors at --tier all -----------------------------------------------------------------------

def test_verify_all_ten_and_their_sources_validate_at_tier_all_with_zero_errors(manifest, report):
    ids = {e['id'] for e in manifest}
    sources = {sid for e in manifest for sid in e['sources']}
    paths = {e['path'] for e in manifest} | {p for p in source_paths(sources).values() if p}
    hits = [f for f in report.blocking
            if f.path in paths or f.entity in ids | sources or set(f.related) & (ids | sources)]
    assert hits == [], '\n'.join('%s/%s %s: %s' % (f.tier, f.rule, f.entity, f.message) for f in hits)


def test_it_runs_as_a_blocking_job():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs']['check-stress-entries']
    assert 'continue-on-error' not in body and 'if' not in body
    [run] = [s['run'] for s in body['steps'] if 'run' in s]
    assert run == 'uv run --locked --python "$PYTHON" python -m pytest -q tests/test_stress_entries.py'
