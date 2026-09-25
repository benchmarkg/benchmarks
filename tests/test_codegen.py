"""Tests for `bench schema gen` (P0-S5-T01; tools/cli.py, tools/build/codegen.py; 04 S12, 05 S3).

The verify: "`bench schema gen --check` exits 0 on a clean tree and exits non-zero after a Pydantic
field is added or a taxonomy/*.yaml term is edited".

The two drift cases run the CLI in a throwaway copy of the tree (schema/, taxonomy/, tools/ and the
committed artifacts), edited there, so the repository itself is never touched. The copy borrows the
repository's site/node_modules for json-schema-to-typescript.
"""
import copy
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build import codegen  # noqa: E402

JSON2TS = os.path.join(ROOT, 'site', 'node_modules', 'json-schema-to-typescript')
needs_node = pytest.mark.skipif(shutil.which('node') is None or not os.path.isdir(JSON2TS),
                                reason='node and site/node_modules (npm ci in site/) are needed for the TS step')


def bench(root, *args):
    return subprocess.run([sys.executable, os.path.join(root, 'tools', 'cli.py'), *args, '--json2ts', JSON2TS],
                          capture_output=True, text=True, encoding='utf-8', cwd=root)


@pytest.fixture
def tree(tmp_path):
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
    for d in ('schema', 'taxonomy', 'tools'):
        shutil.copytree(os.path.join(ROOT, d), tmp_path / d, ignore=ignore)
    shutil.copytree(os.path.join(ROOT, 'site', 'src', 'types'), tmp_path / 'site' / 'src' / 'types')
    return tmp_path


# ---- the verify ---------------------------------------------------------------------------------

@needs_node
def test_check_exits_zero_on_a_clean_tree():
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'cli.py'), 'schema', 'gen', '--check'],
                       capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert 'match' in r.stdout


@needs_node
def test_check_fails_after_a_pydantic_field_is_added(tree):
    assert bench(str(tree), 'schema', 'gen', '--check').returncode == 0          # the copy starts clean
    p = tree / 'schema' / 'benchmark.py'
    s = p.read_text(encoding='utf-8')
    anchor = '    release_venue: Text | None = None\n'
    assert s.count(anchor) == 1
    p.write_text(s.replace(anchor, anchor + '    release_city: Text | None = None\n'), encoding='utf-8')
    r = bench(str(tree), 'schema', 'gen', '--check')
    assert r.returncode == 1
    assert 'differs  schema/generated/benchmark.schema.json' in r.stderr
    assert 'differs  site/src/types/benchmark.d.ts' in r.stderr
    # and regenerating clears it
    assert bench(str(tree), 'schema', 'gen').returncode == 0
    assert bench(str(tree), 'schema', 'gen', '--check').returncode == 0
    assert 'release_city' in (tree / 'site' / 'src' / 'types' / 'benchmark.d.ts').read_text(encoding='utf-8')


@needs_node
def test_check_fails_after_a_taxonomy_term_is_edited(tree):
    from ruamel.yaml import YAML
    y = YAML()
    p = tree / 'taxonomy' / 'lifecycle.yaml'
    doc = y.load(p.read_text(encoding='utf-8'))
    term = next(t for t in doc['terms'] if t['field'] == 'activity' and t['id'] == 'between-rounds')
    term['id'] = 'between-editions'                     # a pre-freeze id rename, nothing references it
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)
    r = bench(str(tree), 'schema', 'gen', '--check')
    assert r.returncode == 1, r.stdout + r.stderr
    assert 'differs  schema/generated/benchmark.schema.json' in r.stderr
    gen = (tree / 'schema' / 'generated' / 'benchmark.schema.json')
    assert 'between-rounds' in gen.read_text(encoding='utf-8')             # the committed file is stale


# ---- the rest of the behaviour ------------------------------------------------------------------

@needs_node
def test_a_hand_edit_to_a_generated_file_is_drift(tree):
    p = tree / 'site' / 'src' / 'types' / 'metric.d.ts'
    p.write_text(p.read_text(encoding='utf-8') + '// tweak\n', encoding='utf-8')
    r = bench(str(tree), 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'differs  site/src/types/metric.d.ts' in r.stderr


@needs_node
def test_a_file_nothing_generates_is_stale_and_gen_removes_it(tree):
    (tree / 'schema' / 'generated' / 'human-baseline.schema.json').write_text('{}\n', encoding='utf-8')
    r = bench(str(tree), 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'stale    schema/generated/human-baseline.schema.json' in r.stderr
    bench(str(tree), 'schema', 'gen')
    assert not (tree / 'schema' / 'generated' / 'human-baseline.schema.json').exists()


@needs_node
def test_a_missing_file_is_drift(tree):
    os.remove(tree / 'site' / 'src' / 'types' / 'benchmark.d.ts')
    r = bench(str(tree), 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'missing  site/src/types/benchmark.d.ts' in r.stderr


def test_the_json_schema_is_draft_2020_12_for_every_entity():
    from schema.paths import ENTITIES
    schemas = codegen.json_schemas()
    assert sorted(schemas) == sorted(ENTITIES)
    for name, s in schemas.items():
        assert s['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
        assert s['title'] == name
        on_disk = json.load(open(os.path.join(ROOT, 'schema', 'generated', codegen.slug(name) + '.schema.json'),
                                 encoding='utf-8'))
        assert on_disk == s


def test_the_vocabularies_reach_the_schema():
    s = codegen.json_schemas()['Benchmark']
    text = json.dumps(s)
    for term in ('code/repository-scale-se', 'planning', 'model-graded-judge', 'accepting-submissions'):
        assert '"%s"' % term in text, term


def test_generation_is_deterministic():
    assert json.dumps(codegen.json_schemas(), sort_keys=False) == json.dumps(codegen.json_schemas(), sort_keys=False)


def test_the_typescript_input_keeps_model_titles_and_drops_property_titles():
    s = codegen._untitled_properties(copy.deepcopy(codegen.json_schemas()['Benchmark']))
    assert s['title'] == 'Benchmark'
    assert 'title' not in s['properties']['id']
    assert s['$defs']['Paper']['title'] == 'Paper' and 'title' not in s['$defs']['Paper']['properties']['arxiv']
    assert codegen.json_schemas()['Benchmark']['properties']['id']['title'] == 'Id'    # the JSON Schema is untouched


def test_slug():
    assert [codegen.slug(n) for n in ('Benchmark', 'ResultClaim', 'EvalConditions', 'IngestBatch')] == [
        'benchmark', 'result-claim', 'eval-conditions', 'ingest-batch']


def test_the_generated_files_are_lf_only():
    for d in (os.path.join(ROOT, 'schema', 'generated'), os.path.join(ROOT, 'site', 'src', 'types')):
        for f in os.listdir(d):
            assert b'\r' not in open(os.path.join(d, f), 'rb').read(), f
