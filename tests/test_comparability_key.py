"""The comparability_key fixture tests (P0-S9-T03; 14-roadmap Phase 0 exit criterion 3, 04 S8), and the key in the
derived build (P3-S10-T02).

The verify: "`pytest tests/test_comparability_key.py` passes all four assertions". Done when: "Exit criterion 3
is verified by a test that would fail if the key ignored a material field."

  1. two SWE-bench condition records differing only in scaffold (data/conditions/, A and B below);
  2. a key is computed for all ten stress entries;
  3. A and B give different keys, and two identical condition sets give the same key;
  4. key_unknown_count is non-zero where a material field is null.

P3-S10-T02's verify is this file too. Done when: "Two deliberately different conditions on one benchmark produce
different keys, two claims silent on the same field produce the same key with a non-zero unknown count, and the
derived-field guard still rejects these fields in any draft." Sections 5 to 8:

  5. the build writes them: a small corpus of claims through `write`, the artifact `bench build --derived` emits;
  6. the whole corpus goes through it, one row per claim under data/claims/;
  7. 04 S8's w[f] table: judge_model and scaffold weigh 2.0 from the benchmark's own facets, and weights never
     reach the key;
  8. the derived-field guard and the schema refuse all three numbers in a draft.

The two records are named by their content-derived ids (07 S1.4: `cond-` and twelve hex digits), not the
`cond-swebench-scaffold-a` the plan's task sketch used, which the EvalConditions id pattern refuses.
"""
import copy
import dataclasses
import glob
import importlib.util
import json
import hashlib
import os
import shutil
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import gates as G  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('comparability_key_test', os.path.join(ROOT, 'tools', 'build', 'comparability.py'))
C = importlib.util.module_from_spec(spec)
sys.modules['comparability_key_test'] = C
spec.loader.exec_module(C)

A, B = 'cond-e29963a458c4', 'cond-cbbb506b483b'
STRESS = os.path.join(ROOT, 'tests', 'fixtures', 'stress-entries.yaml')


def conditions(cid):
    return EvalConditions.model_validate(read_yaml(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml')))


@pytest.fixture(scope='module')
def profiles():
    return C.load_profiles()


@pytest.fixture(scope='module')
def swe(profiles):
    return C.resolve_profile(load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'code', 'swe-bench.yaml')), profiles)


def key(resolution, cond):
    return C.compute(resolution, cond, 'swe-bench@verified', 'resolved-rate', None)


# ---- 1. the two records ------------------------------------------------------------------------------

def test_verify_the_two_swe_bench_records_differ_only_in_scaffold():
    a, b = conditions(A), conditions(B)
    da, db = a.model_dump(exclude={'id'}), b.model_dump(exclude={'id'})
    assert {f for f in da if da[f] != db[f]} == {'scaffold'}
    assert (a.scaffold, b.scaffold) == ('swe-agent-gpt-4o', 'agentless-gpt-4o')


@pytest.mark.parametrize('cid', [A, B])
def test_each_id_is_content_derived(cid):
    raw = {k: v for k, v in read_yaml(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml')).items() if k != 'id'}
    assert cid == 'cond-%s' % hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:12]


# ---- 2. a key for every stress entry -------------------------------------------------------------------

def test_verify_a_key_is_computed_for_all_ten_stress_entries(profiles):
    entries = read_yaml(STRESS)['entries']
    assert len(entries) == 10
    for e in entries:
        r = C.resolve_profile(load_benchmark(os.path.join(ROOT, *e['path'].split('/'))), profiles)
        got = C.compute(r, None, e['id'], 'any-metric', None)
        assert len(got.comparability_key) == 16 and int(got.comparability_key, 16) >= 0, e['id']
        assert got.key_unknown_count == len(r.material), e['id']          # no conditions: every material field unknown


# ---- 3. the key moves with a material field, and only with one -------------------------------------------

def test_verify_the_two_scaffolds_give_different_keys(swe):
    assert 'scaffold' in swe.material
    assert key(swe, conditions(A)).comparability_key != key(swe, conditions(B)).comparability_key


def test_verify_identical_conditions_give_the_same_key(swe):
    a = conditions(A)
    twin = EvalConditions.model_validate(dict(a.model_dump(exclude_none=True), id='cond-000000000000'))
    assert key(swe, a).comparability_key == key(swe, twin).comparability_key       # the id is not a condition


def test_a_field_the_profile_does_not_make_material_leaves_the_key_alone(swe):
    assert 'judge_model' not in swe.material
    a = conditions(A)
    judged = EvalConditions.model_validate(dict(a.model_dump(exclude_none=True), judge_model='gpt-4o'))
    assert key(swe, a).comparability_key == key(swe, judged).comparability_key


# ---- 4. unknowns are counted -------------------------------------------------------------------------------

def test_verify_key_unknown_count_is_non_zero_where_a_material_field_is_null(swe):
    got = key(swe, conditions(A))
    assert got.key_unknown_count == len(swe.material) - 1 > 0                # only scaffold is answered
    assert 'scaffold' not in got.unknown_fields and 'shots' in got.unknown_fields
    filled = EvalConditions.model_validate(dict(conditions(A).model_dump(exclude_none=True), shots=0))
    assert key(swe, filled).key_unknown_count == got.key_unknown_count - 1


# ---- 5. the derived build writes them (P3-S10-T02) -----------------------------------------------------------

THREE = ('comparability_key', 'key_unknown_count', 'condition_completeness')      # 04 S8's three numbers
VALUES = {'comparability_key': '0123456789abcdef', 'key_unknown_count': 3, 'condition_completeness': 0.75}
SWE = os.path.join('data', 'benchmarks', 'code', 'swe-bench.yaml')
PAPERBENCH = os.path.join(ROOT, 'data', 'benchmarks', 'agents-tooluse', 'paperbench.yaml')
TWIN = 'cond-0000000000aa'        # A plus a non-material field; written only into the small corpus below


def claim_doc(n, cond_id=None, **over):
    doc = {'id': 'claim-%012x' % n, 'system': 'sys-x', 'benchmark': 'swe-bench@verified', 'metric': 'resolved-rate',
           'value': 0.5, 'date_reported': '2026-09-25', 'reported_by': 'org-x', 'verification': 'self-reported',
           'source': 'src-x'}
    if cond_id:
        doc['eval_conditions'] = cond_id
    doc.update(over)
    return doc


@pytest.fixture(scope='module')
def small(tmp_path_factory):
    """SWE-bench, the two committed condition records, A's twin, and six claims, through `write` -- the function
    `bench build --derived` calls -- into build/derived/comparability-keys.json."""
    root = tmp_path_factory.mktemp('corpus')
    for d in ('taxonomy', os.path.join('data', 'benchmarks', 'code'), os.path.join('data', 'conditions'),
              os.path.join('data', 'claims', 'swe-bench')):
        os.makedirs(root / d)
    shutil.copy(os.path.join(ROOT, 'taxonomy', 'comparability-profiles.yaml'), root / 'taxonomy')
    shutil.copy(os.path.join(ROOT, SWE), root / SWE)
    for cid in (A, B):
        shutil.copy(os.path.join(ROOT, 'data', 'conditions', cid + '.yaml'), root / 'data' / 'conditions')
    twin = dict(read_yaml(os.path.join(ROOT, 'data', 'conditions', A + '.yaml')), id=TWIN, cost_usd=12.5)
    (root / 'data' / 'conditions' / (TWIN + '.yaml')).write_text(json.dumps(twin), encoding='utf-8')
    claims = {'a': claim_doc(1, A), 'b': claim_doc(2, B), 'twin': claim_doc(3, TWIN),
              'a-other-metric': claim_doc(4, A, metric='other-rate'),
              'bare-1': claim_doc(5), 'bare-2': claim_doc(6, system='sys-y')}
    for doc in claims.values():
        (root / 'data' / 'claims' / 'swe-bench' / (doc['id'] + '.yaml')).write_text(json.dumps(doc), encoding='utf-8')
    path = C.write(str(root), str(root / C.ARTIFACT))
    with open(path, encoding='utf-8') as fh:
        out = json.load(fh)
    return root, {name: out['claims'][doc['id']] for name, doc in claims.items()}, out


def test_done_two_deliberately_different_conditions_on_one_benchmark_get_different_keys(small):
    _, got, _ = small
    assert got['a']['comparability_key'] != got['b']['comparability_key']             # only the scaffold differs
    # both are silent on the same fields, so the count is equal: it is not what tells them apart
    assert got['a']['key_unknown_count'] == got['b']['key_unknown_count'] > 0
    assert got['a']['comparability_key'] != got['a-other-metric']['comparability_key']   # the metric is in the tuple


def test_done_two_claims_silent_on_the_same_fields_share_a_key_and_a_non_zero_unknown_count(small):
    _, got, _ = small
    a, twin = got['a'], got['twin']                     # two condition records; the twin adds cost_usd, non-material
    assert a['comparability_key'] == twin['comparability_key']
    assert a['key_unknown_count'] == twin['key_unknown_count'] == len(a['unknown_fields']) > 0
    assert a['unknown_fields'] == twin['unknown_fields'] and 'shots' in a['unknown_fields']
    assert a['condition_completeness'] == twin['condition_completeness'] < 1.0
    # no condition record at all: every material field unknown, and still one key for both
    one, two = got['bare-1'], got['bare-2']
    assert one['comparability_key'] == two['comparability_key'] != a['comparability_key']
    assert one['key_unknown_count'] == two['key_unknown_count'] == one['fields_material_total'] > 0
    assert one['condition_completeness'] == 0.0


def test_the_build_adds_no_arithmetic_of_its_own(small, swe):
    _, got, _ = small
    for name, cid in (('a', A), ('b', B)):
        assert got[name] == key(swe, conditions(cid)).as_dict()
    # 04 S8's tuple for A, written out here rather than rebuilt the way the code does: one "?" per silent field
    tup = ['swe-bench@verified', 'resolved-rate', None] + ['swe-agent-gpt-4o' if f == 'scaffold' else '?'
                                                           for f in sorted(swe.material)]
    digest = hashlib.sha256(json.dumps(tup, separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
    assert got['a']['comparability_key'] == digest and got['a']['key_unknown_count'] == tup.count('?')


def test_the_artifact_is_a_function_of_the_tree(small):
    root, _, out = small
    with open(root / C.ARTIFACT, 'rb') as fh:
        assert fh.read() == C.serialise(C.build(str(root)))        # 12 S1.1 rule 4: a rebuild is byte-identical
    # a and its twin share a key, so do the two bare claims; b and the other metric stand alone
    assert out['summary'] == {'claims': 6, 'distinct_keys': 4, 'claims_sharing_a_key': 4, 'claims_with_unknowns': 6}
    assert not [k for k in out['summary'] if 'mean' in k]           # each ratio has its own denominator (04 S8)


def test_a_claim_the_build_cannot_place_fails_it_and_writes_nothing(small, tmp_path):
    root, _, _ = small
    shutil.copytree(root, tmp_path / 'c')
    stray = claim_doc(0xff, benchmark='mmlu')                          # no curated record in this corpus
    (tmp_path / 'c' / 'data' / 'claims' / 'swe-bench' / (stray['id'] + '.yaml')).write_text(json.dumps(stray),
                                                                                           encoding='utf-8')
    with pytest.raises(ValueError, match='has no record'):
        C.write(str(tmp_path / 'c'), str(tmp_path / 'out.json'))
    assert not os.path.exists(tmp_path / 'out.json')


def test_bench_build_derived_calls_the_writer():
    # the full `bench build --derived` takes minutes and tests/site/test_freshness_badge.py runs it end to end; here,
    # the derived block names this artifact and this module's writer
    with open(os.path.join(ROOT, 'tools', 'cli.py'), encoding='utf-8') as fh:
        src = fh.read()
    block = src[src.index('    if derived:\n'):src.index('# 08 S4.4 and S6.1')]
    assert "comparability.write(ROOT, str(out / 'derived' / 'comparability-keys.json'))" in block
    assert C.ARTIFACT == os.path.join('build', 'derived', 'comparability-keys.json')


# ---- 6. the whole corpus goes through it -------------------------------------------------------------------------

@pytest.fixture(scope='module')
def corpus(tmp_path_factory):
    path = C.write(ROOT, str(tmp_path_factory.mktemp('derived') / 'comparability-keys.json'))
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def test_every_claim_under_data_claims_gets_its_three_numbers(corpus):
    docs = [read_yaml(p) for p in glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)]
    by_id = {d['id']: d for d in docs}
    assert docs and len(by_id) == len(docs) and set(corpus['claims']) == set(by_id)
    assert corpus['summary']['claims'] == len(docs)
    assert corpus['summary']['distinct_keys'] == len({r['comparability_key'] for r in corpus['claims'].values()})
    for cid, row in corpus['claims'].items():
        res = corpus['profiles'][by_id[cid]['benchmark'].split('@')[0]]
        assert len(row['comparability_key']) == 16 and int(row['comparability_key'], 16) >= 0, cid
        assert row['fields_material_total'] == res['fields_material_total'], cid
        assert row['key_unknown_count'] == len(row['unknown_fields']) <= row['fields_material_total'], cid
        assert set(row['unknown_fields']) <= set(res['material']), cid
        total = sum(res['weights'][f] for f in res['material'])
        answered = sum(res['weights'][f] for f in res['material'] if f not in row['unknown_fields'])
        assert row['condition_completeness'] == (pytest.approx(answered / total) if total else None), cid


def test_every_curated_benchmark_has_its_resolution_beside_the_claims(corpus):
    from schema.stub import curated_benchmark_files
    assert set(corpus['profiles']) == {os.path.basename(p)[:-5] for p in curated_benchmark_files(ROOT)}
    for bid, res in corpus['profiles'].items():
        assert set(res['weights']) == set(res['material']), bid
        assert res['fields_material_total'] == len(res['material']), bid


# ---- 7. 04 S8's w[f] table ---------------------------------------------------------------------------------------

def bench(**overrides):
    doc = {
        'id': 'example-bench', 'name': 'Example Bench', 'tagline': 'A benchmark used in tests.',
        'domain': {'primary': 'code/repository-scale-se'},
        'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-example', 'observed_on': '2026-09-25'}],
        'evaluation_target': 'learned-system',
        'data': {'access': 'fully-open'},
        'homepage': 'https://example.org/',
        'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25',
                     'sources': ['src-example']},
    }
    doc.update(copy.deepcopy(overrides))
    return Benchmark.model_validate(doc)


def test_the_table_reads_the_benchmarks_facets():
    assert C.doubled_fields(bench(evaluation_method=['rubric-graded', 'model-graded-judge'],
                                  designed_for_subjects=['agent-scaffold'])) == {'judge_model', 'scaffold'}
    # a rubric alone does not say a model grades it (taxonomy/evaluation-methods.yaml: a model-graded rubric is both)
    assert C.doubled_fields(bench(evaluation_method=['rubric-graded', 'execution-tests'],
                                  designed_for_subjects=['instruction-tuned-model'])) == set()


def test_judge_model_weighs_2_on_a_model_graded_benchmark_whatever_made_it_material(profiles):
    # a judged benchmark for hosted endpoints resolves hosted-api, which does not carry judge_model; the curator
    # adds it, and the table still doubles it
    r = C.resolve_profile(bench(evaluation_method=['model-graded-judge'],
                                designed_for_subjects=['hosted-inference-endpoint'],
                                comparability={'material_extra': ['judge_model']}), profiles)
    assert r.profiles == ('hosted-api',) and r.weights['judge_model'] == 2.0
    # the same two fields on a benchmark that is neither model-graded nor for agent scaffolds keep the default
    r = C.resolve_profile(bench(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
                                comparability={'material_extra': ['judge_model', 'scaffold']}), profiles)
    assert r.weights['judge_model'] == r.weights['scaffold'] == profiles.default_weight == 1.0


def test_scaffold_weighs_2_where_the_subject_is_an_agent_scaffold(profiles):
    # PaperBench is judged and designed for agent scaffolds; scaffold reaches it through material_extra, not the
    # agentic row, and weighed 1.0 before the table was read off the facets
    r = C.resolve_profile(load_benchmark(PAPERBENCH), profiles)
    assert 'agentic' not in r.profiles and 'scaffold' in r.extra
    assert r.weights['scaffold'] == r.weights['judge_model'] == 2.0
    assert {w for f, w in r.weights.items() if f not in C.DOUBLED} == {1.0}


def test_a_doubled_field_counts_twice_in_completeness_and_never_in_the_key(profiles):
    r = C.resolve_profile(load_benchmark(PAPERBENCH), profiles)
    flat = dataclasses.replace(r, weights={f: 1.0 for f in r.weights})
    total = sum(r.weights.values())
    scaffold_only = EvalConditions.model_validate({'id': 'cond-0000000000ab', 'scaffold': 'basic-agent'})
    subset_only = EvalConditions.model_validate({'id': 'cond-0000000000ac', 'subset_used': 'full'})
    s = C.compute(r, scaffold_only, 'paperbench', 'replication-score', None)
    u = C.compute(r, subset_only, 'paperbench', 'replication-score', None)
    assert s.condition_completeness == pytest.approx(2.0 / total)
    assert u.condition_completeness == pytest.approx(1.0 / total)
    assert s.key_unknown_count == u.key_unknown_count == r.fields_material_total - 1
    for cond in (scaffold_only, subset_only):
        weighted = C.compute(r, cond, 'paperbench', 'replication-score', None)
        unweighted = C.compute(flat, cond, 'paperbench', 'replication-score', None)
        assert (weighted.comparability_key, weighted.key_unknown_count) == \
            (unweighted.comparability_key, unweighted.key_unknown_count)
    assert C.compute(flat, scaffold_only, 'paperbench', 'replication-score', None).condition_completeness == \
        pytest.approx(1.0 / len(r.material))


# ---- 8. no draft carries them ------------------------------------------------------------------------------------

@pytest.mark.parametrize('field', THREE)
def test_done_the_derived_field_guard_still_rejects_each_number_in_any_draft(field):
    draft = claim_doc(7, A)
    G.derived_field_guard(draft)                                          # the clean draft passes
    for where in ({field: VALUES[field]},                                  # on the claim
                  {'eval_conditions': {'id': A, field: VALUES[field]}},    # inside inlined conditions
                  {'notes_extra': [{field: VALUES[field]}]}):              # at any depth
        with pytest.raises(G.GateError, match='derived-field.*%s' % field):
            G.derived_field_guard(dict(draft, **where))


@pytest.mark.parametrize('field', THREE)
def test_the_schema_refuses_them_on_a_claim_and_on_a_condition_record(field):
    with pytest.raises(ValidationError, match=field):
        ResultClaim.model_validate(dict(claim_doc(7, A), **{field: VALUES[field]}))
    with pytest.raises(ValidationError, match=field):
        EvalConditions.model_validate({'id': A, field: VALUES[field]})


def test_every_number_the_build_writes_on_a_claim_is_one_the_guard_knows(small):
    _, got, _ = small
    for row in got.values():
        assert set(THREE) <= set(row)
    assert set(THREE) <= G.DERIVED_FIELDS
