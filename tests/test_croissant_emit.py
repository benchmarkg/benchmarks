"""S9 emits one croissant-benchmark document per benchmark and a collection, all from the committed mapping (P4-S6-T03;
tools/build/croissant.py; 08 S5.8 "Emission", 08 S3.1 S9; ADR-0030 D6).

The verify: `uv run bench build && test $(ls build/croissant-benchmark/*.jsonld | wc -l) -ge 290`. Done when: "One
document emits per benchmark plus a collection document, all from the committed mapping and none hand-written."

No entry is published yet -- every committed benchmark is an ai-drafted-unverified draft, and 05 S4 publishes none of
those -- so `bench build` writes the collection alone into build/croissant-benchmark/, and validates every draft's
document without writing it. The count the verify asks for is therefore read where the drafts are emitted: the draft
build (artifacts.build(drafts=True), what scripts/preview_corpus.py writes into build/preview/croissant-benchmark/),
in memory here, and from the preview's directory when it has been written. Nothing is published to make the number.

  verify        over the drafts: one document per benchmark, at least 290, and the collection; build/'s directory and
                the preview's, when written, hold exactly what the file-count assertion says
  the mapping   every value a document carries is the record's, read along the term's path in TERMS: the versions,
                the subsets, the resolved material set as condition terms in the key's order, the rating-pool flag,
                and the reference conditions record's value for every condition term; no node carries a key the
                mapping does not name; the build refuses a mapping the committed YAML does not state, a reference no
                record answers and a material field no term carries; an answered empty list survives
  hand-written  no .jsonld is committed except the published context, an upstream fixture and P4-S6-T05's worked
                examples (docs/croissant-benchmark/examples/, the emitter's own output for three entries, which
                tests/test_check_croissant.py holds to the extension), and each document is exactly what the emitter
                makes of its record
  release       the documents are S9's release artifacts, not page assets: never under /data/ or in the manifest's
                `paths`; release_payload lists them after the file-count assertion, which `bench build` (through the
                manifest) and S13 enforce; the detail page and cite.jsonld read the one file the build wrote
"""
import copy
import json
import os
import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import CROISSANT_TERMS, Benchmark  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools import cli  # noqa: E402
from tools.build import artifacts, comparability, croissant  # noqa: E402
from tools.build import manifest as M  # noqa: E402
from tools.build.emit import Refused  # noqa: E402

MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
BUILD = os.path.join(ROOT, 'build')
PREVIEW = os.path.join(BUILD, 'preview')
FLOOR = 290                                              # the verify's `-ge 290`
CONDITION_TERMS = croissant.CONDITION_TERMS
runner = CliRunner()


@pytest.fixture(scope='module')
def drafts():
    """The draft build: every benchmark that passes tier 1, drafts included, as the preview builds it."""
    result = artifacts.build(ROOT, drafts=True)
    assert result.errors == [], result.errors[:5]
    return result


@pytest.fixture(scope='module')
def emitted(drafts):
    docs, held = croissant.documents(drafts.corpus, drafts.withheld, drafts.conditions)
    assert held == {}                                    # a draft build publishes every draft, so none is withheld
    return docs


def benchmarks(result) -> dict:
    return {b['id']: b for b in result.corpus['entities']['benchmark']}


def walk(record: dict, term: str):
    """The record's value for a condition term, read along the term's `ours` path in the committed mapping."""
    v = record
    for seg in read_terms()[term][1].split('.')[1:]:
        v = v[seg] if isinstance(v, dict) else None
    return v


_TERMS = {}


def read_terms() -> dict:
    """taxonomy/crosswalks/croissant.yaml's `extension.terms`, read from the file, not from the module."""
    if not _TERMS:
        _TERMS.update({r['term']: (r['on'], r['ours'])
                       for r in read_yaml(os.path.join(ROOT, croissant.MAPPING))['extension']['terms']})
    return _TERMS


# ---- the verify, over the drafts ------------------------------------------------------------------------------------

def test_verify_one_document_per_benchmark_and_the_collection_at_least_290(drafts, emitted):
    ids = sorted(benchmarks(drafts))
    assert len(ids) >= FLOOR, len(ids)
    assert sorted(emitted) == sorted(['%s.jsonld' % i for i in ids] + [croissant.COLLECTION])
    assert croissant.names(drafts.corpus) == sorted(emitted, key=lambda n: n.encode('utf-8'))
    assert [p['benchmarkId'] for p in emitted[croissant.COLLECTION]['hasPart']] == ids
    assert all(emitted['%s.jsonld' % i]['benchmarkId'] == i for i in ids)


def test_verify_every_draft_document_passes_the_extension_schema_and_those_with_conditions_mlcroissant(emitted):
    """`bench build` runs both validators over every draft; here the extension schema over all of them, and
    mlcroissant over each document that carries condition values, the part this task adds."""
    validator = croissant.schema_validators()['BenchmarkDocument']
    for name, doc in emitted.items():
        if name != croissant.COLLECTION:
            assert list(validator.iter_errors(doc)) == [], name
    carrying = {n: d for n, d in emitted.items() if set(d.get('conditions', {})) & set(CONDITION_TERMS)}
    assert len(carrying) >= 3                         # paperbench, virtual-cell-challenge, weatherbench-2
    assert croissant.check(carrying)[0] == []


def test_verify_the_written_directories_hold_what_the_file_count_assertion_says():
    """build/ from the verify's `bench build`, and build/preview/ from scripts/preview_corpus.py, when written."""
    seen = 0
    for out in (BUILD, PREVIEW):
        folder, corpus_path = os.path.join(out, croissant.DIR), os.path.join(out, 'corpus.json')
        if not (os.path.isdir(folder) and os.path.exists(corpus_path)):
            continue
        with open(corpus_path, encoding='utf-8') as fh:
            corpus = json.load(fh)
        assert croissant.count_problems(folder, corpus) == [], out
        assert len(croissant.release_payload(folder, corpus)) == len(corpus['entities']['benchmark']) + 1
        if corpus.get('drafts'):                       # the preview: every draft that passes tier 1
            assert len(corpus['entities']['benchmark']) >= FLOOR
        seen += 1
    if not seen:
        pytest.skip('run `uv run bench build` or `uv run python scripts/preview_corpus.py --out build/preview` first')


# ---- every value from the mapping -----------------------------------------------------------------------------------

def test_the_module_emits_through_the_committed_mapping():
    assert read_terms() == croissant.TERMS
    assert croissant.mapping_problems() == []


def test_versions_subsets_and_the_rating_pool_flag_are_the_records(drafts, emitted):
    for bid, b in benchmarks(drafts).items():
        doc = emitted['%s.jsonld' % bid]
        assert doc.get('benchmarkVersions', []) == [v['version'] for v in b['versions']], bid
        assert doc['protocol'].get('subsets', []) == [s['id'] for s in b['subsets']], bid
        assert doc['conditions']['ratingPoolRequired'] is b['comparability']['rating_pool_required'], bid
    assert any(len(emitted['%s.jsonld' % i].get('benchmarkVersions', [])) > 1 for i in benchmarks(drafts))
    assert any(emitted['%s.jsonld' % i]['protocol'].get('subsets') for i in benchmarks(drafts))


def test_material_fields_are_the_resolved_set_in_the_keys_order_as_the_mapping_names_them(drafts, emitted):
    profiles = comparability.load_profiles()
    by_field = {}
    for term, (on, ours) in read_terms().items():
        if on == 'EvalConditions' and ours and ours.startswith('EvalConditions.'):
            by_field.setdefault(ours.split('.')[1], []).append(term)
    sizes = set()
    for bid, b in benchmarks(drafts).items():
        material = comparability.resolve_profile(Benchmark.model_validate(b), profiles).material
        want = [t for f in material for t in by_field[f]]
        assert emitted['%s.jsonld' % bid]['conditions'].get('materialFields', []) == want, bid
        sizes.add(len(want))
    assert len(sizes) > 1 and max(sizes) >= 8                  # the sets differ per benchmark (04 S8), never one list


def test_condition_values_are_the_reference_records_read_along_each_terms_path(drafts, emitted):
    carried = 0
    for bid, b in benchmarks(drafts).items():
        node = emitted['%s.jsonld' % bid]['conditions']
        ref = b['reference_conditions']
        if ref is None:
            assert not set(node) & set(CONDITION_TERMS), bid
            continue
        record = drafts.conditions[ref]
        assert node['conditionsId'] == ref
        want = {t: walk(record, t) for t in CONDITION_TERMS if walk(record, t) is not None}
        assert {t: node[t] for t in node if t in CONDITION_TERMS} == want, bid
        assert want, bid                                  # each reference record answers something
        carried += len(want)
    assert carried >= 3


def test_no_node_carries_a_key_the_mapping_does_not_name(emitted):
    terms = read_terms()
    allowed = {cls: {t for t, (on, _) in terms.items() if on == cls} for cls in croissant.CLASSES}
    for (cls, term) in croissant.REUSES:
        allowed[cls].add(term.split(':', 1)[1])
    allowed['Benchmark'] |= {t.split(':', 1)[1] for t in CROISSANT_TERMS.values()}
    nodes = {'tasks': 'Task', 'metrics': 'Metric', 'protocol': 'Protocol', 'conditions': 'EvalConditions',
             'lineage': 'Lineage'}
    for name, doc in emitted.items():
        if name == croissant.COLLECTION:
            continue
        assert set(doc) - {'@context', '@type', 'conformsTo'} <= allowed['Benchmark'], name
        for key, cls in nodes.items():
            for node in (doc.get(key) if isinstance(doc.get(key), list) else [doc.get(key)] if key in doc else []):
                assert node['@type'] == 'cb:%s' % cls and set(node) - {'@type'} <= allowed[cls], (name, key)


def test_the_build_refuses_a_mapping_the_committed_yaml_does_not_state(monkeypatch, drafts):
    monkeypatch.setitem(croissant.TERMS, 'shotCount', ('EvalConditions', 'EvalConditions.shots'))
    problems = croissant.mapping_problems()
    assert problems and 'term shotCount is None in %s' % croissant.MAPPING in problems[0]
    with pytest.raises(Refused, match='the documents are emitted from the committed mapping'):
        croissant.documents(drafts.corpus, drafts.withheld, drafts.conditions)


def test_a_reference_no_record_answers_refuses_the_build(drafts):
    vcc = benchmarks(drafts)['virtual-cell-challenge']
    assert vcc['reference_conditions'] in drafts.conditions
    without = {k: v for k, v in drafts.conditions.items() if k != vcc['reference_conditions']}
    with pytest.raises(Refused) as e:
        croissant.documents(drafts.corpus, drafts.withheld, without)
    assert e.value.errors == ['virtual-cell-challenge.jsonld: reference_conditions %s has no conditions record in this '
                              'build (no file under data/conditions/ that passes tier 1 holds it alone)'
                              % vcc['reference_conditions']]
    docs, problems, summary = croissant.build(drafts.corpus, drafts.withheld)       # no conditions passed at all
    assert docs == {} and len(problems) >= 3 and summary == {}


def test_a_material_field_no_term_carries_refuses_rather_than_publishing_a_short_set(monkeypatch, drafts):
    real = croissant.terms_for
    monkeypatch.setattr(croissant, 'terms_for', lambda f: () if f == 'shots' else real(f))
    with pytest.raises(Refused) as e:
        croissant.documents(drafts.corpus, drafts.withheld, drafts.conditions)
    assert any('material field(s) shots carry no extension term' in x for x in e.value.errors)
    assert all(x.endswith('map them') for x in e.value.errors)


def test_an_answered_empty_list_is_a_value_and_survives(drafts):
    """`tools_allowed: []` says no tools; the prune that drops an empty list elsewhere must not drop it."""
    b = benchmarks(drafts)['virtual-cell-challenge']
    conditions = copy.deepcopy(drafts.conditions)
    conditions[b['reference_conditions']]['tools_allowed'] = []
    metrics = {m['id']: m for m in drafts.corpus['entities']['metric']}
    doc = croissant.benchmark_document(b, metrics, croissant.context(), conditions)
    assert doc['conditions']['toolsAllowed'] == []
    assert croissant.check({'virtual-cell-challenge.jsonld': doc})[0] == []


# ---- none hand-written ----------------------------------------------------------------------------------------------

EXAMPLES = 'docs/croissant-benchmark/examples/'   # P4-S6-T05: the emitter's output for three entries, as documentation


def test_no_jsonld_document_is_committed_but_the_context_an_upstream_fixture_and_the_worked_examples():
    r = subprocess.run(['git', '-c', 'core.longpaths=true', 'ls-files', '*.jsonld'], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8')
    if r.returncode != 0:
        pytest.skip('not a git checkout')
    committed = r.stdout.split()
    examples = [p for p in committed if p.startswith(EXAMPLES) and '/' not in p[len(EXAMPLES):]]
    assert sorted(set(committed) - set(examples)) == sorted([croissant.CONTEXT, 'tests/ingest/fixtures/hf-hub/croissant.jsonld'])


def test_each_document_is_what_the_emitter_makes_of_its_record(drafts, emitted):
    """The bytes are the record's alone: emitting one benchmark again gives the same document as the whole run."""
    metrics = {m['id']: m for m in drafts.corpus['entities']['metric']}
    ctx = croissant.context()
    for bid in ('paperbench', 'virtual-cell-challenge', 'weatherbench-2', 'mmlu'):
        b = benchmarks(drafts)[bid]
        assert croissant.benchmark_document(b, metrics, ctx, drafts.conditions) == emitted['%s.jsonld' % bid]


# ---- release artifacts, the payload and the file-count assertion ----------------------------------------------------

def test_bench_build_writes_them_as_release_artifacts_never_page_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path)])
    assert res.exit_code == 0, res.output
    m = json.loads((tmp_path / M.MANIFEST).read_text(encoding='utf-8'))
    assert m['documents']['croissant-benchmark']['files'] == m['counts']['benchmarks'] + 1 == 2
    assert not [p for p in m['paths'] if not p.endswith('.json')]             # nothing .jsonld in the hashed namespace
    assert not [n for _, _, ns in os.walk(tmp_path / 'data') for n in ns if n.endswith('.jsonld')]
    corpus = json.loads((tmp_path / 'corpus.json').read_text(encoding='utf-8'))
    assert croissant.release_payload(str(tmp_path / croissant.DIR), corpus) == [
        'croissant-benchmark/_collection.jsonld', 'croissant-benchmark/alpha-bench.jsonld']
    preview = runner.invoke(cli.app, ['build', '--data-only', '--out', str(tmp_path)])    # the preview build: no S9
    assert preview.exit_code == 0, preview.output
    assert not (tmp_path / croissant.DIR).exists()
    assert json.loads((tmp_path / M.MANIFEST).read_text(encoding='utf-8'))['documents'] == {}


def test_the_file_count_assertion_refuses_a_stray_or_missing_document(tmp_path):
    result = artifacts.build(MINIMAL)
    docs, problems, _ = croissant.build(result.corpus, result.withheld, conditions=result.conditions)
    assert problems == []
    folder = str(tmp_path / croissant.DIR)
    croissant.write(docs, folder)
    assert croissant.count_problems(folder, result.corpus) == []
    (tmp_path / croissant.DIR / 'retired-bench.jsonld').write_text('{}', encoding='utf-8')
    assert croissant.count_problems(folder, result.corpus) == [
        '%s: 3 file(s), but the corpus publishes 1 benchmark(s), so 2: one document each and the collection' % folder,
        '%s: retired-bench.jsonld is not a document this build emits' % folder]
    os.remove(os.path.join(folder, 'retired-bench.jsonld'))
    os.remove(os.path.join(folder, 'alpha-bench.jsonld'))
    with pytest.raises(Refused, match='no alpha-bench.jsonld, which the build emits'):
        croissant.release_payload(folder, result.corpus)


def test_the_manifest_will_not_record_a_directory_that_fails_it(tmp_path):
    result = artifacts.build(MINIMAL)
    docs, _, _ = croissant.build(result.corpus, result.withheld, conditions=result.conditions)
    out = str(tmp_path / 'out')
    shipped = artifacts.write(result, out)
    croissant.write(docs, os.path.join(out, croissant.DIR))
    folder = os.path.join(out, croissant.DIR)
    with open(M.write(out, shipped, folder, root=MINIMAL)[-1], encoding='utf-8') as fh:
        assert json.load(fh)['documents']['croissant-benchmark']['files'] == 2
    shutil.copy(os.path.join(folder, 'alpha-bench.jsonld'), os.path.join(folder, 'beta-bench.jsonld'))
    with pytest.raises(M.ManifestError, match='the file-count assertion fails: .*beta-bench.jsonld is not a document'):
        M.write(out, shipped, folder, root=MINIMAL)


def test_s13_holds_the_recorded_count_to_the_published_benchmarks():
    files = {'html': 1, 'data': 0, 'pagefind_fragments': 0, 'index_chunks': 0, 'assets': 0, 'total': 1, 'cap': 20000}
    m = {'files': files, 'routes': {'/': 1}, 'counts': {'benchmarks': 4},
         'documents': {'croissant-benchmark': {'sha256': 'sha256:x', 'files': 5}}}
    assert M.check_files(m) == []
    m['documents']['croissant-benchmark']['files'] = 4
    assert M.check_files(m) == ['documents: croissant-benchmark holds 4 file(s), but the build published 4 '
                                'benchmark(s), so 5: one document each and the collection (08 S5.8)']
    assert M.check_files(dict(m, documents={})) == []                          # a --data-only build wrote none


def test_the_detail_page_and_cite_jsonld_read_the_one_file_the_build_wrote():
    """One emitter: the site writes no JSON-LD of its own. It reads build/croissant-benchmark/{id}.jsonld beside the
    corpus (lib/croissant.ts) and both the inline <script> and cite.jsonld take that text."""
    site = os.path.join(ROOT, 'site', 'src')

    def read(*parts):
        with open(os.path.join(site, *parts), encoding='utf-8') as fh:
            return fh.read()
    lib = read('lib', 'croissant.ts')
    assert "join(dirname(CORPUS_PATH), 'croissant-benchmark')" in lib and '`${id}.jsonld`' in lib
    detail = read('views', 'BenchmarkDetail.astro')
    assert 'const jsonld = croissantText(b.id);' in detail and 'set:html={scriptSafe(jsonld)}' in detail
    assert "ext === 'jsonld' ? croissantText(b.id)" in read('pages', 'benchmarks', '[id]', 'cite.[ext].ts')
    inlined = []
    for folder, _, files in os.walk(site):
        for n in files:
            if n.endswith(('.ts', '.astro', '.mjs')):
                with open(os.path.join(folder, n), encoding='utf-8') as fh:
                    if 'type="application/ld+json"' in fh.read().replace('<script type="application/ld+json">', ''):
                        inlined.append(n)
    assert inlined == ['BenchmarkDetail.astro']               # the one <script> of JSON-LD a page carries
