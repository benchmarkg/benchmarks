"""Checks 9b, 9f, 9g and 9h as pr-validate.yml runs them (P0-S6-T06; 05 S9, 02 S3, 02 S4.3, 09 S4.2).

The verify: "`python scripts/taxonomy_stats.py --check && python scripts/check_display_only_vocab.py` runs as
a blocking job, and `pytest tests/ci/test_taxonomy_gates.py` asserts a perturbed seed_target, a broken
capability partition and a presentation-group id leaking into a shipped artifact each fail". The 9f and 9g
cases run scripts/taxonomy_stats.py's own checks against a copy of taxonomy/ with one thing broken; the 9h
case runs scripts/check_display_only_vocab.py over a fixture artifact directory. The last test holds the
build to step 3: facets.json names the capability_groups version it was built against.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATS = os.path.join(ROOT, 'scripts', 'taxonomy_stats.py')
DISPLAY = os.path.join(ROOT, 'scripts', 'check_display_only_vocab.py')
y = YAML()


def run(script, *args):
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, encoding='utf-8')


@pytest.fixture
def stats(tmp_path):
    """taxonomy_stats.py pointed at a copy of taxonomy/ the test may break."""
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    spec = importlib.util.spec_from_file_location('taxonomy_stats_gate_test', STATS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.TAXONOMY = str(tmp_path / 'taxonomy')
    return mod


def edit(path, fn):
    doc = y.load(open(path, encoding='utf-8'))
    fn(doc)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)


def failed(mod, check, *args):
    r = mod.Result()
    check(r, *args)
    return [name for name, _ in r.failed], r.passed


# ---- the repository passes, as a blocking job ---------------------------------------------------

def test_verify_the_repository_passes_both():
    a, b = run(STATS, '--check'), run(DISPLAY)
    assert a.returncode == 0, a.stdout
    assert b.returncode == 0, b.stdout


@pytest.mark.parametrize('key, command', [
    ('check-9b-taxonomy-stats', 'uv run --locked --python "$PYTHON" python scripts/taxonomy_stats.py --check'),
    ('check-9h-display-only', 'uv run --locked --python "$PYTHON" python scripts/check_display_only_vocab.py'),
])
def test_verify_both_run_as_blocking_jobs(key, command):
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs'][key]
    assert 'continue-on-error' not in body and 'if' not in body
    runs = [s['run'] for s in body['steps'] if 'run' in s]
    assert runs[-1] == command and all('|| true' not in r for r in runs)


def test_9h_scans_built_artifacts_not_an_empty_directory():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs']['check-9h-display-only']
    runs = [s['run'] for s in body['steps'] if 'run' in s]
    assert any('bench build --out build/' in r for r in runs[:-1])


# ---- each named failure fails --------------------------------------------------------------------

def test_verify_a_perturbed_seed_target_fails_9f(stats):
    p = os.path.join(stats.TAXONOMY, 'domains.yaml')

    def bump(doc):
        fam = next(t for t in doc['terms'] if not t.get('parent') and t.get('seed_target'))
        fam['seed_target'] += 1                                   # the total is no longer 320
    edit(p, bump)
    fams, _ = stats.domain_terms()
    names, _ = failed(stats, stats.check_9f, fams, None)
    assert names == ['9f seed total']


def test_verify_a_broken_capability_partition_fails_9g(stats):
    p = os.path.join(stats.TAXONOMY, 'capability_groups.yaml')
    edit(p, lambda doc: doc['groups'][0]['members'].pop(0))       # one capability now in no group
    names, _ = failed(stats, stats.check_9g)
    assert names == ['9g capability-group partition']


def test_a_capability_in_two_groups_fails_9g(stats):
    p = os.path.join(stats.TAXONOMY, 'capability_groups.yaml')
    edit(p, lambda doc: doc['groups'][1]['members'].append(doc['groups'][0]['members'][0]))
    names, _ = failed(stats, stats.check_9g)
    assert names == ['9g capability-group partition']


def test_the_clean_copy_passes_9f_and_9g(stats):
    fams, _ = stats.domain_terms()
    assert failed(stats, stats.check_9f, fams, None)[0] == []
    assert failed(stats, stats.check_9g)[0] == []


def test_verify_a_presentation_group_id_in_a_shipped_artifact_fails_9h(tmp_path):
    groups = y.load(open(os.path.join(ROOT, 'taxonomy', 'domain_groups.yaml'), encoding='utf-8'))['groups']
    art = tmp_path / 'build'
    (art / 'derived').mkdir(parents=True)
    (art / 'derived' / 'coverage.json').write_text(json.dumps({'rows': [{'group': groups[0]['id']}]}), encoding='utf-8')
    r = run(DISPLAY, '--artifacts', str(art))
    assert r.returncode == 1 and groups[0]['id'] in r.stdout


def test_the_layout_artifact_may_carry_group_ids(tmp_path):
    groups = y.load(open(os.path.join(ROOT, 'taxonomy', 'domain_groups.yaml'), encoding='utf-8'))['groups']
    art = tmp_path / 'build'
    art.mkdir()
    (art / 'atlas.json').write_text(json.dumps({'bands': [g['id'] for g in groups]}), encoding='utf-8')
    (art / 'facets.json').write_text(json.dumps({'benchmarks': []}), encoding='utf-8')
    assert run(DISPLAY, '--artifacts', str(art)).returncode == 0


# ---- step 3: the build records which grouping it used --------------------------------------------

def test_facets_json_names_the_vocabulary_versions_it_was_built_against():
    sys.path.insert(0, ROOT)
    from tools.build import artifacts
    from schema.taxonomy import read_yaml
    got = artifacts.vocabulary_versions(ROOT)
    assert got['capability_groups'] == str(read_yaml(os.path.join(ROOT, 'taxonomy', 'capability_groups.yaml'))['version'])
    assert got['domain_groups'] == str(read_yaml(os.path.join(ROOT, 'taxonomy', 'domain_groups.yaml'))['version'])
    with open(os.path.join(ROOT, 'taxonomy', 'VERSION'), encoding='utf-8') as fh:
        assert got['taxonomy'] == fh.read().strip()
    assert artifacts.build(ROOT).facets['vocabularies'] == got
