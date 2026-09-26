"""Tests for the minimal `bench build` (P0-S5-T05; tools/build/artifacts.py; 05 S3, 08 S4.2).

The verify: "`bench build --out build/` exits 0 and `python -c` asserts the emitted JSON validates
against schema/generated/*.schema.json and contains zero records with curation.verification_status
ai-drafted-unverified". `problems(out_dir)` is that assertion, importable by the verify's
`python -c`; the tests run it over the committed corpus and over tests/build/fixtures/minimal/, a
corpus with one published benchmark (a three-level subset tree), two drafts -- one of which fails
tier 1 -- and published and unpublished Sources.

What "validates" means for each part of the artifacts:
  - every corpus.json entity record against its own schema/generated/<kind>.schema.json;
  - every materialised subset row: its id, parent and label against subset.schema.json, its
    resolved domain, capability and metric against the Subset override they stand in for, and its
    inherited facets against the Benchmark field they come from;
  - every facets.json value against the Benchmark field FACET_FIELDS says it projects, and equal to
    that field of the corpus.json record, so the two artifacts cannot disagree.
"""
import copy
import json
import os
import shutil
import sys

import jsonschema
import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli  # noqa: E402
from tools.build import artifacts  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
runner = CliRunner()


# ---- the verify's assertion ---------------------------------------------------------------------

def _schema(kind: str) -> dict:
    with open(os.path.join(ROOT, 'schema', 'generated', kind + '.schema.json'), encoding='utf-8') as fh:
        return json.load(fh)


def _node(schema: dict, dotted: str) -> dict:
    """The subschema for a dotted field path, following $ref and the Optional anyOf branch."""
    node = schema
    for key in dotted.split('.'):
        while True:
            if '$ref' in node:
                node = schema['$defs'][node['$ref'].rsplit('/', 1)[1]]
            elif 'properties' not in node and 'anyOf' in node:
                node = next(b for b in node['anyOf'] if '$ref' in b or 'properties' in b)
            else:
                break
        node = node['properties'][key]
    return node


def _check(schema: dict, dotted: str | None, value, where: str) -> list[str]:
    sub = schema if dotted is None else {'$defs': schema['$defs'], **_node(schema, dotted)}
    return ['%s: %s' % (where, e.message[:200]) for e in jsonschema.Draft202012Validator(sub).iter_errors(value)]


def _drafts(x, where=''):
    if isinstance(x, dict):
        if x.get('verification_status') == artifacts.DRAFT and where.endswith('curation'):
            yield where
        for k, v in x.items():
            yield from _drafts(v, '%s.%s' % (where, k) if where else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _drafts(v, '%s[%d]' % (where, i))


def problems(out_dir: str) -> list[str]:
    """Everything wrong with the artifacts in `out_dir`; empty means the verify's assertion holds."""
    with open(os.path.join(out_dir, 'corpus.json'), encoding='utf-8') as fh:
        corpus = json.load(fh)
    with open(os.path.join(out_dir, 'facets.json'), encoding='utf-8') as fh:
        facets = json.load(fh)
    out = []
    if sorted(corpus['entities']) != sorted(artifacts.CORPUS_KINDS):
        out.append('corpus.json entities are %s, not %s' % (sorted(corpus['entities']), sorted(artifacts.CORPUS_KINDS)))
    for kind, records in corpus['entities'].items():
        schema = _schema(kind)
        for r in records:
            out += _check(schema, None, r, '%s %s' % (kind, r.get('id')))
    bench, subset = _schema('benchmark'), _schema('subset')
    for row in corpus['subsets']:
        where = 'subset %s' % row['id']
        for key in ('id', 'parent', 'label'):
            out += _check(subset, key, row[key], '%s.%s' % (where, key))
        if sorted(row['facets']) != sorted(artifacts.SUBSET_FACETS):
            out.append('%s: facets %s, not %s' % (where, sorted(row['facets']), sorted(artifacts.SUBSET_FACETS)))
            continue
        for facet, (override, inherited) in artifacts.SUBSET_FACETS.items():
            schema, path = (subset, override) if override else (bench, inherited)
            out += _check(schema, path, row['facets'][facet], '%s.facets.%s' % (where, facet))
    records = {b['id']: b for b in corpus['entities']['benchmark']}
    if sorted(r['id'] for r in facets['benchmarks']) != sorted(records):
        out.append('facets.json and corpus.json hold different benchmarks')
    for row in facets['benchmarks']:
        b = records.get(row['id'])
        for key, path in artifacts.FACET_FIELDS.items():
            out += _check(bench, path, row[key], 'facets %s.%s' % (row['id'], key))
            if b is not None and row[key] != artifacts.at(b, path):
                out.append('facets %s.%s differs from corpus.json %s' % (row['id'], key, path))
        if b is not None and (row['domain'], row['year']) != (b['domain']['primary'].split('/')[0],
                                                              int(b['released'][:4]) if b['released'] else None):
            out.append('facets %s: domain or year is not derived from the corpus record' % row['id'])
    out += ['%s is %s' % (w, artifacts.DRAFT) for w in _drafts({'corpus': corpus, 'facets': facets})]
    return out


# ---- helpers ------------------------------------------------------------------------------------

@pytest.fixture
def tree(tmp_path):
    """A writable copy of the fixture corpus."""
    shutil.copytree(FIXTURE, tmp_path / 'root')
    return tmp_path / 'root'


def edit(tree, rel, old, new):
    path = tree / rel
    text = path.read_text(encoding='utf-8')
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def built(root, out):
    result = artifacts.build(str(root))
    assert result.errors == []
    artifacts.write(result, str(out))
    return result


ALPHA = 'data/benchmarks/code/alpha-bench.yaml'


# ---- the verify ---------------------------------------------------------------------------------

def test_verify_bench_build_over_the_committed_corpus(tmp_path):
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'build')])
    assert res.exit_code == 0, res.output
    assert problems(str(tmp_path / 'build')) == []


def test_verify_over_the_fixture_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', FIXTURE)
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'build')])
    assert res.exit_code == 0, res.output
    assert 'published 1 benchmark, 0 system, 1 organization, 1 metric, 1 source; 3 subset(s)' in res.output
    assert problems(str(tmp_path / 'build')) == []


# ---- what is published --------------------------------------------------------------------------

def test_drafts_and_their_uncited_sources_are_excluded(tmp_path):
    result = built(FIXTURE, tmp_path)
    ids = {k: [r['id'] for r in v] for k, v in result.corpus['entities'].items()}
    assert ids == {'benchmark': ['alpha-bench'], 'system': [], 'organization': ['org-alpha-lab'],
                   'metric': ['accuracy'], 'source': ['src-alpha-paper']}
    assert sorted((i, reason) for _, i, reason in result.excluded) == [
        ('beta-bench', 'ai-drafted-unverified'),
        ('gamma-bench', 'ai-drafted-unverified (and fails tier 1)'),
        ('src-beta-page', 'no published record cites it'),
        ('src-orphan-draft', 'no published record cites it'),
    ]
    text = (tmp_path / 'corpus.json').read_text(encoding='utf-8') + (tmp_path / 'facets.json').read_text(encoding='utf-8')
    for absent in ('beta-bench', 'gamma-bench', 'src-beta-page', 'src-orphan-draft', artifacts.DRAFT):
        assert absent not in text


def test_the_committed_corpus_publishes_no_draft_and_no_draft_source():
    result = artifacts.build(ROOT)
    assert result.errors == []
    drafts = [i for _, i, r in result.excluded if r.startswith(artifacts.DRAFT)]
    assert sorted(drafts) == ['casp', 'roboarena', 'swe-bench']   # every committed entry is still a draft
    assert result.corpus['entities']['benchmark'] == [] and result.corpus['entities']['source'] == []


def test_a_status_absent_from_the_file_is_the_model_default_and_so_a_draft(tree, tmp_path):
    edit(tree, ALPHA, '  verification_status: curator-reviewed\n', '')
    assert artifacts.build(str(tree)).corpus['entities']['benchmark'] == []


def test_machine_ingested_is_not_a_draft(tree):
    edit(tree, ALPHA, 'verification_status: curator-reviewed', 'verification_status: machine-ingested')
    assert [b['id'] for b in artifacts.build(str(tree)).corpus['entities']['benchmark']] == ['alpha-bench']


def test_records_carry_every_field_and_no_computed_field(tmp_path):
    from schema.benchmark import Benchmark
    from schema.metric import Metric
    result = built(FIXTURE, tmp_path)
    alpha = result.corpus['entities']['benchmark'][0]
    assert set(alpha) == {f.alias or n for n, f in Benchmark.model_fields.items()}
    metric = result.corpus['entities']['metric'][0]
    assert set(Metric.model_computed_fields) and not set(Metric.model_computed_fields) & set(metric)
    assert [s['id'] for s in alpha['subsets']] == ['alpha-bench#chem', 'alpha-bench#chem-hard', 'alpha-bench#plain']
    assert alpha['subsets'][2]['domain_override'] is None     # the curated record stays sparse


# ---- subsets are materialised -------------------------------------------------------------------

def test_subset_facets_are_materialised_field_by_field(tmp_path):
    rows = {r['id']: r for r in built(FIXTURE, tmp_path).corpus['subsets']}
    chem, hard, plain = rows['alpha-bench#chem'], rows['alpha-bench#chem-hard'], rows['alpha-bench#plain']
    assert chem['overrides'] == ['domain'] and chem['depth'] == 1
    assert chem['facets']['domain'] == {'primary': 'chemistry-materials/reaction-prediction', 'secondary': []}
    assert chem['facets']['capability'] == ['deductive-reasoning', 'knowledge-recall']      # inherited
    # Two levels down: the domain comes from the parent subset, not the benchmark.
    assert hard['overrides'] == ['capability', 'metric'] and hard['depth'] == 2 and hard['parent'] == 'alpha-bench#chem'
    assert hard['facets']['domain']['primary'] == 'chemistry-materials/reaction-prediction'
    assert hard['facets']['capability'] == ['deductive-reasoning']          # replace, not union
    assert hard['facets']['metric'] == 'exact-accuracy'
    assert plain['overrides'] == []
    assert plain['facets'] == {'domain': {'primary': 'code/repository-scale-se',
                                          'secondary': ['reasoning-general/logical-deduction']},
                               'capability': ['deductive-reasoning', 'knowledge-recall'], 'metric': 'accuracy',
                               'evaluation_method': ['execution-tests'], 'designed_for_subjects': ['reasoning-model'],
                               'lifecycle': 'active'}


def test_no_subset_row_needs_its_parent_chain(tmp_path):
    for row in built(FIXTURE, tmp_path).corpus['subsets']:
        assert sorted(row['facets']) == sorted(artifacts.SUBSET_FACETS)
        assert all(v is not None for k, v in row['facets'].items() if k != 'metric')


def test_a_subset_parent_cycle_fails_the_build(tree):
    edit(tree, ALPHA, '    label: Chemistry\n', '    label: Chemistry\n    parent: alpha-bench#chem-hard\n')
    result = artifacts.build(str(tree))
    assert any('parent cycle' in e for e in result.errors)
    assert result.corpus == {}


# ---- the build refuses what it would publish broken ---------------------------------------------

@pytest.mark.parametrize('rel, old, new, expect', [
    (ALPHA, 'tagline: A published benchmark used in build tests.\n', '', 'would be published, but fails tier 1'),
    ('data/organizations/org-alpha-lab.yaml', 'kind: academic-lab', 'kind: a-guild', 'would be published'),
    (ALPHA, '    - src-alpha-paper\n', '    - src-alpha-paper\n    - src-nowhere\n', 'no data/sources/ file holds it'),
    (ALPHA, '    - src-alpha-paper\n', '    - src-alpha-paper\n    - src-orphan-draft\n', 'is cited by benchmark alpha-bench, but fails tier 1'),
    ('data/benchmarks/code/gamma-bench.yaml', '  sources:\n', '  verification_status: curator-reviewed\n  sources:\n',
     'gamma-bench would be published'),
])
def test_a_broken_published_record_fails_the_build_and_writes_nothing(tree, tmp_path, monkeypatch, rel, old, new, expect):
    edit(tree, rel, old, new)
    result = artifacts.build(str(tree))
    assert any(expect in e for e in result.errors), result.errors
    monkeypatch.setattr(cli, 'ROOT', str(tree))
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'out')])
    assert res.exit_code == 1 and 'nothing written' in res.output
    assert not (tmp_path / 'out').exists()


def test_a_published_file_that_does_not_parse_fails_the_build(tree):
    (tree / 'data/benchmarks/code/delta-bench.yaml').write_text('id: [unclosed\n', encoding='utf-8')
    assert any('delta-bench' in e and 'fails tier 1' in e for e in artifacts.build(str(tree)).errors)


# ---- determinism --------------------------------------------------------------------------------

def test_two_builds_are_byte_identical(tmp_path):
    built(FIXTURE, tmp_path / 'a')
    built(FIXTURE, tmp_path / 'b')
    for name in artifacts.ARTIFACTS:
        a, b = (tmp_path / 'a' / name).read_bytes(), (tmp_path / 'b' / name).read_bytes()
        assert a == b and a.endswith(b'}\n') and b'\r' not in a and a.count(b'\n') == 1


def test_keys_are_sorted_and_strings_are_nfc(tree, tmp_path):
    edit(tree, ALPHA, 'name: Alpha Bench', 'name: "Alpha Cafe\\u0301 Bench"')
    built(tree, tmp_path)
    text = (tmp_path / 'facets.json').read_text(encoding='utf-8')
    assert 'Alpha Café Bench' in text and 'é' not in text
    row = json.loads(text)['benchmarks'][0]
    assert list(row) == sorted(row)


# ---- the assertion itself catches what it exists to catch ---------------------------------------

def _tamper(tmp_path, mutate):
    built(FIXTURE, tmp_path)
    corpus = json.loads((tmp_path / 'corpus.json').read_text(encoding='utf-8'))
    facets = json.loads((tmp_path / 'facets.json').read_text(encoding='utf-8'))
    mutate(corpus, facets)
    (tmp_path / 'corpus.json').write_text(json.dumps(corpus), encoding='utf-8')
    (tmp_path / 'facets.json').write_text(json.dumps(facets), encoding='utf-8')
    return problems(str(tmp_path))


def _draft(corpus, facets):
    b = copy.deepcopy(corpus['entities']['benchmark'][0])
    b['id'], b['curation']['verification_status'] = 'leaked-draft', artifacts.DRAFT
    corpus['entities']['benchmark'].append(b)


@pytest.mark.parametrize('mutate, expect', [
    (_draft, 'is ai-drafted-unverified'),
    (lambda c, f: c['entities']['metric'][0].update(higher_is_better=True), 'metric accuracy'),
    (lambda c, f: c['entities']['benchmark'][0].update(lifecycle='undead'), 'benchmark alpha-bench'),
    (lambda c, f: c['subsets'][0]['facets'].update(capability=['telepathy']), 'subset alpha-bench#chem.facets.capability'),
    (lambda c, f: c['subsets'][0]['facets'].pop('lifecycle'), 'facets'),
    (lambda c, f: f['benchmarks'][0].update(subdomain='code'), 'facets alpha-bench.subdomain'),
    (lambda c, f: f['benchmarks'][0].update(capability=['knowledge-recall']), 'differs from corpus.json'),
    (lambda c, f: f['benchmarks'][0].update(year=1999), 'domain or year'),
    (lambda c, f: f['benchmarks'].clear(), 'different benchmarks'),
])
def test_the_assertion_catches_a_tampered_artifact(tmp_path, mutate, expect):
    found = _tamper(tmp_path, mutate)
    assert any(expect in p for p in found), found
