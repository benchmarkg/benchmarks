"""The croissant-benchmark JSON-LD: emitted per benchmark, validated in the build (P2-S3-T06; tools/build/croissant.py;
08 S5.8, 10 "The permanent citation URL", 15 A8).

The verify: `uv run bench build --out build/ && uv run pytest tests/build/test_croissant.py`. Done when: "Every
benchmark has a JSON-LD document that passes mlcroissant base conformance and our extension schema, and a schema change
that breaks base conformance fails the build."

The documents are built over tests/fixtures/corpus-20/ (twenty frozen drafts, built as the preview builds them, so all
twenty are published) and over the build the verify's first half wrote. The failure the done_when names is shown three
ways: a document whose base type moves fails mlcroissant, a Croissant version mlcroissant does not know fails it, and
either fails `bench build` with nothing written, also when the broken document belongs to an unpublished draft. The
mapping is held to taxonomy/crosswalks/croissant.yaml, the models the generated schema comes from, and the rule that no
extension key redefines an upstream term.
"""
import copy
import json
import os
import shutil
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.benchmark import CROISSANT_TERMS, Benchmark  # noqa: E402
from schema.paths import resolve  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools import cli  # noqa: E402
from tools.build import artifacts, codegen, croissant  # noqa: E402
from tools.build.emit import Refused  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
BUILD = os.path.join(ROOT, 'build')
MAPPING = os.path.join(ROOT, 'taxonomy', 'crosswalks', 'croissant.yaml')
NODES = {'Benchmark': croissant.BenchmarkDocument, 'Task': croissant.TaskNode, 'Metric': croissant.MetricNode,
         'Protocol': croissant.ProtocolNode, 'EvalConditions': croissant.ConditionsNode,
         'Lineage': croissant.LineageNode}
runner = CliRunner()


@pytest.fixture(scope='module')
def fixture_build():
    result = artifacts.build(FIXTURE, drafts=True)
    assert result.errors == []
    return result


@pytest.fixture(scope='module')
def built(fixture_build):
    docs, problems, summary = croissant.build(fixture_build.corpus)
    assert problems == [], problems
    return docs, summary


def records(result) -> dict:
    return {b['id']: b for b in result.corpus['entities']['benchmark']}


# ---- the verify ---------------------------------------------------------------------------------------------------

def test_verify_every_benchmark_has_a_document_that_passes_both(fixture_build, built):
    docs, summary = built
    ids = sorted(records(fixture_build))
    assert len(ids) == 20
    assert sorted(docs) == sorted(['%s.jsonld' % i for i in ids] + [croissant.COLLECTION])
    assert croissant.check(docs) == ([], summary['notices'])
    assert summary['written'] == 20 and summary['mlcroissant'] == '1.1.1'


def test_verify_the_build_the_verify_wrote():
    """build/croissant-benchmark/ from `bench build --out build/`: one document per published benchmark and the
    collection, every one passing both, and nothing else in the directory."""
    corpus_path = os.path.join(BUILD, 'corpus.json')
    if not os.path.exists(corpus_path):
        pytest.skip('run `uv run bench build --out build/` first (the verify does)')
    with open(corpus_path, encoding='utf-8') as fh:
        corpus = json.load(fh)
    folder = os.path.join(BUILD, croissant.DIR)
    names = sorted(os.listdir(folder))
    assert names == sorted(['%s.jsonld' % b['id'] for b in corpus['entities']['benchmark']] + [croissant.COLLECTION])
    docs = {}
    for name in names:
        with open(os.path.join(folder, name), encoding='utf-8') as fh:
            docs[name] = json.load(fh)
    assert croissant.check(docs)[0] == []
    assert croissant.main(['--check', folder]) == 0


def test_a_document_whose_base_type_moves_fails_base_conformance(built):
    docs, _ = built
    doc = copy.deepcopy(docs['mmlu.jsonld'])
    doc['@type'] = ['cb:Benchmark', 'sc:Dataset']        # mlcroissant reads the first type as the node's
    problems, _ = croissant.check({'mmlu.jsonld': doc})
    assert any('fails Croissant base conformance' in p and 'https://schema.org/Dataset' in p for p in problems), problems


def test_a_croissant_version_mlcroissant_does_not_know_fails_base_conformance(built):
    docs, _ = built
    doc = copy.deepcopy(docs['mmlu.jsonld'])
    doc['conformsTo'] = ['http://mlcommons.org/croissant/9.9', croissant.EXTENSION_VERSION]
    problems, _ = croissant.check({'mmlu.jsonld': doc})
    assert any('fails Croissant base conformance' in p and 'conformsTo' in p for p in problems), problems


def test_a_change_that_breaks_base_conformance_fails_bench_build_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    good = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'good')])
    assert good.exit_code == 0, good.output
    assert sorted(os.listdir(tmp_path / 'good' / croissant.DIR)) == ['_collection.jsonld', 'alpha-bench.jsonld']
    real = croissant.benchmark_document

    def moved(b, metrics, ctx):
        doc = real(b, metrics, ctx)
        doc['@type'] = list(reversed(doc['@type']))
        return doc
    monkeypatch.setattr(croissant, 'benchmark_document', moved)
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'bad')])
    assert res.exit_code == 1 and 'croissant-benchmark problem(s); nothing written' in res.output
    assert 'alpha-bench.jsonld: fails Croissant base conformance' in res.output
    assert not (tmp_path / 'bad').exists()


def test_an_unpublished_drafts_broken_document_fails_the_build_too(monkeypatch, tmp_path):
    """No entry is published yet, so the drafts are what holds a mapping change to base conformance in CI."""
    result = artifacts.build(MINIMAL)
    assert list(result.withheld) == ['beta-bench'] and [b['id'] for b in result.corpus['entities']['benchmark']] == [
        'alpha-bench']
    real = croissant.benchmark_document

    def broken_beta(b, metrics, ctx):
        doc = real(b, metrics, ctx)
        if b['id'] == 'beta-bench':
            doc['conformsTo'] = ['http://mlcommons.org/croissant/9.9', croissant.EXTENSION_VERSION]
        return doc
    monkeypatch.setattr(croissant, 'benchmark_document', broken_beta)
    docs, problems, _ = croissant.build(result.corpus, result.withheld)
    assert problems and all(p.startswith('beta-bench.jsonld: ') for p in problems), problems
    assert 'beta-bench.jsonld' not in docs                     # validated, never written
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'out')])
    assert res.exit_code == 1 and not (tmp_path / 'out').exists()


def test_a_key_the_extension_schema_does_not_declare_fails_it(built):
    docs, _ = built
    doc = copy.deepcopy(docs['mmlu.jsonld'])
    doc['metrics'][0]['higherIsBetter'] = True
    problems, _ = croissant.check({'mmlu.jsonld': doc})
    assert any(croissant.SCHEMA in p and '/metrics/0' in p and 'higherIsBetter' in p for p in problems), problems


def test_mlcroissant_warnings_other_than_recommended_properties_fail(monkeypatch, built):
    docs, _ = built
    real = croissant.base_problems
    monkeypatch.setattr(croissant, 'base_problems', lambda doc: real({**doc, 'version': '2026-11'}))
    problems, _ = croissant.check({'mmlu.jsonld': docs['mmlu.jsonld']})
    assert any('MAJOR.MINOR.PATCH' in p for p in problems), problems


# ---- the namespace and the context --------------------------------------------------------------------------------

def test_the_context_keeps_every_upstream_term_and_adds_only_ours(built):
    docs, _ = built
    ctx = docs['mmlu.jsonld']['@context']
    upstream = dict(croissant.upstream_context())
    assert {k: ctx[k] for k in upstream} == upstream               # nothing upstream is dropped or changed
    ours = set(ctx) - set(upstream)
    assert ours == {croissant.PREFIX} | set(croissant.TERMS)
    assert ctx[croissant.PREFIX] == croissant.NAMESPACE == 'https://host.invalid/ns/croissant-benchmark/v1#'
    assert all(ctx[t] == 'cb:%s' % t for t in croissant.TERMS)
    assert not ours & croissant.schema_org_terms()
    for group in ('tasks', 'metrics', 'protocol', 'conditions', 'lineage'):   # 08 S5.8's five
        assert group in ctx


@pytest.mark.parametrize('key, where', [('headline', 'schema.org'), ('source', 'the Croissant context')])
def test_an_extension_key_that_would_redefine_an_upstream_term_is_refused(monkeypatch, key, where):
    monkeypatch.setitem(croissant.TERMS, key, ('Metric', None))
    with pytest.raises(Refused) as e:
        croissant.context()
    assert 'extension key %s is already an upstream term (%s)' % (key, where) in str(e.value)


def test_the_upstream_context_is_the_one_mlcroissant_writes_for_the_pinned_version():
    import mlcroissant as mlc
    upstream = dict(croissant.upstream_context())
    assert upstream['@vocab'] == 'https://schema.org/' and upstream['cr'] == 'http://mlcommons.org/croissant/'
    assert mlc.Context(conforms_to=croissant.CROISSANT_VERSION).is_v1_1()
    assert {'arrayShape', 'containedIn', 'isArray'} <= set(upstream)                    # 1.1's keys


# ---- the mapping ----------------------------------------------------------------------------------------------------

def test_the_crosswalks_extension_is_the_emitters():
    ext = read_yaml(MAPPING)['extension']
    assert (ext['prefix'], ext['namespace']) == (croissant.PREFIX, croissant.NAMESPACE)
    assert ext['conforms_to'] == [croissant.CROISSANT_VERSION, croissant.EXTENSION_VERSION]
    assert tuple(ext['classes']) == croissant.CLASSES
    assert {r['term']: (r['on'], r['ours']) for r in ext['terms']} == croissant.TERMS
    assert len(ext['terms']) == len(croissant.TERMS)
    assert {(r['on'], r['term']): r['ours'] for r in ext['reuses']} == croissant.REUSES


def test_every_ours_path_resolves_on_the_models():
    ext = read_yaml(MAPPING)['extension']
    for r in ext['terms'] + ext['reuses'] + ext['unmapped']:
        if r['ours'] is not None:
            resolve(r['ours'])
    for r in ext['terms']:
        assert r['on'] in croissant.CLASSES and (r['ours'] is not None or r['on'] == 'Benchmark'), r
    assert all(r['reason'] for r in ext['unmapped'])


def test_no_benchmark_field_reuses_a_base_term_outside_croissant_terms():
    """A Benchmark field maps to a CROISSANT_TERMS row or to a cb: term, so the base crosswalk is never incomplete."""
    assert all(not ours.startswith('Benchmark.') for ours in croissant.REUSES.values())
    model = croissant.BenchmarkDocument.model_json_schema(by_alias=True)['properties']
    base = set(model) - set(croissant.TERMS) - {'@context', '@type', 'conformsTo'}
    assert base == {t.split(':', 1)[1] for t in CROISSANT_TERMS.values()}


def test_each_node_model_carries_exactly_its_classes_terms():
    for cls, model in NODES.items():
        props = set(model.model_json_schema(by_alias=True)['properties']) - {'@type', '@context', 'conformsTo'}
        mine = {t for t, (on, _) in croissant.TERMS.items() if on == cls}
        reused = {t.split(':', 1)[1] for (on, t) in croissant.REUSES if on == cls}
        if cls == 'Benchmark':
            reused = {t.split(':', 1)[1] for t in CROISSANT_TERMS.values()}
        assert props == mine | reused, cls


def test_the_base_terms_carry_the_records_values(fixture_build, built):
    docs, _ = built
    for bid, b in records(fixture_build).items():
        doc = docs['%s.jsonld' % bid]
        licence = Benchmark.model_validate(b).license
        for field, term in CROISSANT_TERMS.items():
            want = licence if field == 'license' else b[field]
            assert doc.get(term.split(':', 1)[1]) == (want if want not in (None, []) else None), (bid, field)
        assert doc['benchmarkId'] == bid and doc['tasks'][0]['evaluationTarget'] == b['evaluation_target']


def test_metrics_are_the_headline_first_then_the_records_list_joined_to_each_metric(fixture_build, built):
    docs, _ = built
    vcc = docs['virtual-cell-challenge.jsonld']['metrics']
    b = records(fixture_build)['virtual-cell-challenge']
    assert [m['identifier'] for m in vcc] == list(dict.fromkeys([b['headline_metric']] + b['metrics']))
    assert [m['isHeadline'] for m in vcc] == [True] + [False] * (len(vcc) - 1)
    metric = {m['id']: m for m in fixture_build.corpus['entities']['metric']}[b['headline_metric']]
    assert vcc[0]['name'] == metric['name'] and vcc[0]['optimum'] == metric['optimum']
    assert vcc[0]['unbounded'] is metric['unbounded']


def test_conditions_and_lineage_nodes_are_written_only_when_they_carry_something(fixture_build, built):
    docs, _ = built
    for bid, b in records(fixture_build).items():
        doc = docs['%s.jsonld' % bid]
        has_conditions = b['reference_conditions'] is not None or b['comparability']['profile'] is not None
        assert ('conditions' in doc) == has_conditions, bid
        if has_conditions:
            assert doc['conditions'].get('conditionsId') == b['reference_conditions']
        if 'lineage' in doc:
            L = b['lineage']
            assert doc['lineage'].get('variants', []) == [v['id'] for v in L['variants']]
            assert doc['lineage'].get('isSupersededBy', []) == L['superseded_by']
    assert 'conditions' in docs['virtual-cell-challenge.jsonld']


def test_the_collection_lists_every_document_and_cites_the_index(built):
    docs, _ = built
    coll = docs[croissant.COLLECTION]
    cff = read_yaml(os.path.join(ROOT, 'CITATION.cff'))
    assert coll['name'] == cff['title'] and cff['doi'] in coll['citeAs'] and coll['url'] == cff['repository-code']
    assert 'CC-BY-4.0' in cff['license'] and coll['license'] == croissant.DATA_LICENCE
    assert [p['@id'] for p in coll['hasPart']] == sorted(n for n in docs if n != croissant.COLLECTION)
    assert all(docs[p['@id']]['name'] == p['name'] for p in coll['hasPart'])


def test_a_document_holds_one_schema_org_dataset_node(built):
    """mlcroissant validates whichever Dataset node rdflib lists first, so a part typed sc:Dataset could make it judge a
    part, at random, instead of the collection; the extension schema refuses one."""
    docs, _ = built
    coll = copy.deepcopy(docs[croissant.COLLECTION])
    assert {p['@type'] for p in coll['hasPart']} == {'cb:Benchmark'}
    coll['hasPart'][0]['@type'] = ['sc:Dataset', 'cb:Benchmark']
    problems, _ = croissant.check({croissant.COLLECTION: coll})
    assert any(croissant.SCHEMA in p and '/hasPart/0/@type' in p for p in problems), problems


# ---- the generated schema ---------------------------------------------------------------------------------------------

def test_the_committed_schema_is_what_bench_schema_gen_renders(monkeypatch):
    monkeypatch.setattr(codegen, 'typescript', lambda schemas, json2ts: {})       # the TS half needs node; not this
    rendered = codegen.render(ROOT)[croissant.SCHEMA]
    with open(os.path.join(ROOT, croissant.SCHEMA), encoding='utf-8', newline='') as fh:
        assert fh.read() == rendered
    assert json.loads(rendered)['$schema'] == 'https://json-schema.org/draft/2020-12/schema'


def test_a_missing_schema_refuses_rather_than_skipping(tmp_path, built):
    docs, _ = built
    with pytest.raises(Refused, match='croissant-benchmark.schema.json is missing'):
        croissant.check(docs, root=str(tmp_path))


# ---- determinism and the directory ----------------------------------------------------------------------------------

def test_two_builds_are_byte_identical_and_a_stale_document_is_removed(fixture_build, built, tmp_path):
    docs, _ = built
    again, problems, _ = croissant.build(fixture_build.corpus)
    assert problems == []
    a, b = tmp_path / 'a', tmp_path / 'b'
    croissant.write(docs, str(a))
    (b).mkdir()
    (b / 'retired-bench.jsonld').write_text('{}', encoding='utf-8')
    croissant.write(again, str(b))
    assert sorted(os.listdir(a)) == sorted(os.listdir(b)) == sorted(docs)
    for name in docs:
        assert (a / name).read_bytes() == (b / name).read_bytes()
    raw = (a / 'mmlu.jsonld').read_bytes()
    assert raw.endswith(b'}\n') and b'\r' not in raw and raw.count(b'\n') == 1


def test_the_check_script_fails_a_tampered_directory(built, tmp_path):
    docs, _ = built
    croissant.write(docs, str(tmp_path))
    assert croissant.main(['--check', str(tmp_path)]) == 0
    doc = json.loads((tmp_path / 'mmlu.jsonld').read_text(encoding='utf-8'))
    doc['@type'] = 'cb:Benchmark'
    (tmp_path / 'mmlu.jsonld').write_text(json.dumps(doc), encoding='utf-8')
    assert croissant.main(['--check', str(tmp_path)]) == 1
    shutil.rmtree(tmp_path)
    tmp_path.mkdir()
    assert croissant.main(['--check', str(tmp_path)]) == 1                 # an empty directory is not a pass
