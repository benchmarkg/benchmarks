"""Checks 9, 9a, 9c, 9d and 9e (P0-S6-T05; 05 S9).

The verify: "`python scripts/check_identifiers.py && python scripts/check_homographs.py` exits 0, and
`pytest tests/ci/test_identifier_checks.py` asserts a reused retired id, a resurrected forbidden identifier,
a duplicate leaf slug, an undeclared homograph and a mis-flagged tautological cell each fail". Each case
copies the repository's taxonomy/ into a throwaway tree, breaks one thing, and runs the script there.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDS = os.path.join(ROOT, 'scripts', 'check_identifiers.py')
HOMS = os.path.join(ROOT, 'scripts', 'check_homographs.py')
y = YAML()


def run(script, *args):
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, encoding='utf-8')


@pytest.fixture
def tree(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    (tmp_path / 'data' / 'benchmarks' / 'code').mkdir(parents=True)
    (tmp_path / 'data' / 'benchmarks' / 'code' / 'example-bench.yaml').write_text('id: example-bench\n', encoding='utf-8')
    (tmp_path / 'tools').mkdir()
    return tmp_path


def edit(path, fn):
    doc = y.load(path.read_text(encoding='utf-8'))
    fn(doc)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)


def homograph_entries(tree):
    return y.load((tree / 'taxonomy' / 'homographs.yaml').read_text(encoding='utf-8'))['entries']


# ---- the repository passes ----------------------------------------------------------------------

def test_verify_the_repository_passes_both():
    a, b = run(IDS), run(HOMS)
    assert a.returncode == 0, a.stdout
    assert b.returncode == 0, b.stdout


def test_a_clean_copy_passes(tree):
    assert run(IDS, '--root', str(tree)).returncode == 0
    assert run(HOMS, '--root', str(tree)).returncode == 0


# ---- each named failure fails --------------------------------------------------------------------

def test_verify_a_reused_retired_id_fails(tree):
    def retire(doc):
        doc['retired'] = [{'id': 'capability:deductive-reasoning', 'retired_on': '2026-10-01',
                           'reason': 'a test retires a live term'}]
    edit(tree / 'taxonomy' / 'retired-ids.yaml', retire)
    r = run(IDS, '--root', str(tree))
    assert r.returncode == 1 and 'capability:deductive-reasoning is a live taxonomy term again' in r.stdout


def test_a_retired_id_reused_as_a_record_id_fails(tree):
    def retire(doc):
        doc['retired'] = [{'id': 'example-bench', 'retired_on': '2026-10-01', 'reason': 'retired, then reused'}]
    edit(tree / 'taxonomy' / 'retired-ids.yaml', retire)
    r = run(IDS, '--root', str(tree))
    assert r.returncode == 1 and 'example-bench is reused as a record id' in r.stdout


def test_verify_a_resurrected_forbidden_identifier_fails(tree):
    old = y.load((tree / 'taxonomy' / 'forbidden-identifiers.yaml').read_text(encoding='utf-8'))['forbidden'][0]['identifier']
    (tree / 'tools' / 'emit.py').write_text("FIELD = '%s'\n" % old, encoding='utf-8')
    r = run(IDS, '--root', str(tree))
    assert r.returncode == 1 and 'tools/emit.py:1 %s' % old in r.stdout


def test_the_ledgers_and_unscanned_paths_may_name_it(tree):
    old = y.load((tree / 'taxonomy' / 'forbidden-identifiers.yaml').read_text(encoding='utf-8'))['forbidden'][0]['identifier']
    for rel in ('docs/rename.md', 'adr/0099-rename.md', '_plan/notes.md', 'CHANGELOG.md'):
        p = tree / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('renamed from %s\n' % old, encoding='utf-8')
    (tree / 'tools' / 'ok.py').write_text("FIELD = '%s_v2'\n" % old, encoding='utf-8')     # not the whole word
    assert run(IDS, '--root', str(tree)).returncode == 0


def test_verify_a_duplicate_leaf_slug_fails(tree):
    def dupe(doc):
        subs = [t for t in doc['terms'] if t.get('parent')]
        donor = subs[0]
        other = next(t['id'] for t in doc['terms'] if not t.get('parent') and t['id'] != donor['parent'])
        leaf = donor['id'].split('/', 1)[1]
        clone = dict(donor)
        clone['id'], clone['parent'] = '%s/%s' % (other, leaf), other
        doc['terms'].append(clone)
    edit(tree / 'taxonomy' / 'domains.yaml', dupe)
    r = run(IDS, '--root', str(tree))
    assert r.returncode == 1 and 'leaf under two families' in r.stdout


def test_a_badly_formed_id_fails_the_grammar(tree):
    def bad(doc):
        doc['terms'][0]['id'] = 'Deductive_Reasoning'
    edit(tree / 'taxonomy' / 'capabilities.yaml', bad)
    r = run(IDS, '--root', str(tree))
    assert r.returncode == 1 and '9c id grammar' in r.stdout


def test_verify_an_undeclared_homograph_fails(tree):
    edit(tree / 'taxonomy' / 'homographs.yaml', lambda doc: doc['entries'].pop(0))
    r = run(HOMS, '--root', str(tree))
    assert r.returncode == 1 and 'undeclared' in r.stdout


def coverage(tree, cells):
    p = tree / 'build' / 'derived' / 'coverage.json'
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'fine': {'cells': [dict(c, degenerate='tautological-homograph') for c in cells]}}),
                 encoding='utf-8')
    return p


def declared(tree):
    return [{'subdomain': e['domain'], 'capability': e['capability']} for e in homograph_entries(tree)
            if e['relationship'] == 'same-concept-two-facets']


def test_9e_is_pending_until_coverage_is_built(tree):
    r = run(HOMS, '--root', str(tree))
    assert r.returncode == 0 and 'PENDING 9e tautological cells' in r.stdout


def test_9e_passes_when_the_flags_equal_the_declarations(tree):
    coverage(tree, declared(tree))
    r = run(HOMS, '--root', str(tree))
    assert r.returncode == 0 and 'PASS    9e tautological cells' in r.stdout


def test_verify_a_mis_flagged_tautological_cell_fails(tree):
    cells = declared(tree)
    coverage(tree, cells[1:] + [{'subdomain': 'domain:code/repository-scale-se', 'capability': 'capability:planning'}])
    r = run(HOMS, '--root', str(tree))
    assert r.returncode == 1 and 'not flagged' in r.stdout and 'flagged but not declared' in r.stdout


# ---- the jobs ------------------------------------------------------------------------------------

@pytest.mark.parametrize('key, script', [('check-9-identifiers', 'check_identifiers.py'),
                                         ('check-9d-homographs', 'check_homographs.py')])
def test_both_checks_run_as_blocking_jobs(key, script):
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        body = YAML(typ='safe').load(fh)['jobs'][key]
    assert 'continue-on-error' not in body and 'if' not in body
    [run_] = [s['run'] for s in body['steps'] if 'run' in s]
    assert run_ == 'uv run --locked --python "$PYTHON" python scripts/' + script
