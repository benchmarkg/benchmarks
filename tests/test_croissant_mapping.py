"""The croissant-benchmark field-level mapping: every material field is accounted for (P4-S6-T02;
schema/croissant_benchmark.py, taxonomy/crosswalks/croissant.yaml; 04 S5, 04 S8, 08 S5.8, 05 S2 `crosswalks/`; ADR-0030).

The verify: `uv run bench schema gen --check && uv run pytest tests/test_croissant_mapping.py -q`. Done when: "Every
material field either maps or is listed as unmapped with a reason, and the schema regenerates without a diff."

04 S8: "Two claims are comparable only when they agree on benchmark version, metric, subset, and the material
condition fields." Each part of that is taken from the code that defines it, never from a list copied here, so a
field that becomes material fails this file until a term carries it or the YAML's `unmapped` gives its reason:

  conditions     the fields taxonomy/comparability-profiles.yaml makes material, as tools/build/comparability.py's
                 load_profiles() reads them, and every field a curated benchmark's resolved set holds
                 (resolve_profile, which adds the benchmark's own comparability.material_extra)
  key            the components compute() takes beside the conditions, each the Benchmark field it names
  comparability  every field of the Benchmark's comparability block (schema.benchmark.Comparability)

A field is accounted for when a term's `ours` is the field, when every key of a nested block is (EvalConditions'
`sampling`), or when an `unmapped` row names it with a reason. The mapping read is the committed YAML;
tests/build/test_croissant.py holds its `extension` to the module, and this file its `material_key`.

The schema half: the node model's condition terms accept exactly what an EvalConditions record does (the module
copies each field's type), every committed conditions record maps to a node the committed schema accepts, and
croissant-benchmark.schema.json is what `bench schema gen` renders from schema/croissant_benchmark.py.
"""
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema import croissant_benchmark as cb  # noqa: E402
from schema.benchmark import Comparability, load_benchmark  # noqa: E402
from schema.conditions import FIELDS, EvalConditions  # noqa: E402
from schema.paths import resolve, type_args  # noqa: E402
from schema.stub import curated_benchmark_files  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import codegen, comparability  # noqa: E402

MAPPING = os.path.join(ROOT, 'taxonomy', 'crosswalks', 'croissant.yaml')
CONDITIONS = os.path.join(ROOT, 'data', 'conditions')


@pytest.fixture(scope='module')
def ext() -> dict:
    return read_yaml(MAPPING)['extension']


@pytest.fixture(scope='module')
def resolutions() -> dict:
    """benchmark id -> its Resolution, for every curated benchmark (the set comparability.build() resolves)."""
    profiles = comparability.load_profiles()
    return {r.benchmark: r for r in (comparability.resolve_profile(load_benchmark(p), profiles)
                                     for p in curated_benchmark_files(ROOT))}


def nested(path: str):
    """The nested model at `path`, or None for a field that is not one."""
    models = [a for a in type_args(resolve(path)) if isinstance(a, type) and hasattr(a, 'model_fields')]
    return models[0] if len(models) == 1 else None


def unaccounted(paths, terms: list[dict], unmapped: list[dict]) -> list[str]:
    """The paths no term carries and no `unmapped` row names; a nested block counts when every key of it does."""
    carried = {r['ours'] for r in terms}
    listed = {r['ours'] for r in unmapped}

    def ok(path: str) -> bool:
        if path in carried or path in listed:
            return True
        model = nested(path)
        return model is not None and all(ok('%s.%s' % (path, f)) for f in model.model_fields)
    return sorted(p for p in paths if not ok(p))


def profile_material() -> set[str]:
    pf = comparability.load_profiles()
    return set(pf.fallback.material).union(*(p.material for p in pf.profiles))


# ---- the verify: every material field is accounted for --------------------------------------------------------

def test_every_field_a_comparability_profile_makes_material_is_accounted_for(ext):
    material = profile_material()
    assert 'subset_used' in material and len(material) >= 30                   # the fallback's floor, and 0.3.0's
    assert unaccounted({'EvalConditions.%s' % f for f in material}, ext['terms'], ext['unmapped']) == []


def test_every_field_a_curated_benchmark_resolves_as_material_is_accounted_for(ext, resolutions):
    """material_extra makes a field material for one benchmark: that is material too (resolve_profile)."""
    by_field = {}
    for bid, r in resolutions.items():
        for f in r.material:
            by_field.setdefault(f, []).append(bid)
    assert len(resolutions) >= 300
    missing = unaccounted({'EvalConditions.%s' % f for f in by_field}, ext['terms'], ext['unmapped'])
    assert missing == [], ['%s (material on %s)' % (p, ', '.join(by_field[p.split('.', 1)[1]][:3])) for p in missing]


def test_the_keys_benchmark_side_is_the_one_compute_takes_and_is_accounted_for(ext):
    params = list(inspect.signature(comparability.compute).parameters)
    assert params[:2] == ['resolution', 'conditions']
    assert list(ext['material_key']) == params[2:] == list(cb.MATERIAL_KEY)     # benchmark_version, metric, subset
    assert ext['material_key'] == cb.MATERIAL_KEY
    for path in cb.MATERIAL_KEY.values():
        resolve(path)
    assert unaccounted(cb.MATERIAL_KEY.values(), ext['terms'], ext['unmapped']) == []
    listed = {r['ours'] for r in ext['unmapped']}
    assert not listed & set(cb.MATERIAL_KEY.values())          # each key component is carried, not just listed


def test_the_benchmarks_comparability_block_is_accounted_for(ext):
    fields = {'Benchmark.comparability.%s' % f for f in Comparability.model_fields}
    assert unaccounted(fields | {'Benchmark.reference_conditions'}, ext['terms'], ext['unmapped']) == []


def test_every_evalconditions_field_is_accounted_for_material_or_not(ext):
    """Total, so a field that becomes material through a curator's material_extra is already covered."""
    assert unaccounted({'EvalConditions.%s' % f for f in FIELDS}, ext['terms'], ext['unmapped']) == []


def test_a_field_that_becomes_material_fails_until_mapped_or_listed(ext):
    terms = [r for r in ext['terms'] if r['ours'] != 'EvalConditions.shots']
    material = {'EvalConditions.%s' % f for f in profile_material()}
    assert unaccounted(material, terms, ext['unmapped']) == ['EvalConditions.shots']
    listed = ext['unmapped'] + [{'ours': 'EvalConditions.shots', 'reason': 'a reason'}]
    assert unaccounted(material, terms, listed) == []
    one_key_short = [r for r in ext['terms'] if r['ours'] != 'EvalConditions.sampling.seed']
    assert unaccounted({'EvalConditions.sampling'}, one_key_short, ext['unmapped']) == ['EvalConditions.sampling']


def test_every_unmapped_row_has_a_reason_and_names_a_field_no_term_carries(ext):
    carried = {r['ours'] for r in ext['terms']}
    for r in ext['unmapped']:
        resolve(r['ours'])
        assert isinstance(r['reason'], str) and len(r['reason'].split()) >= 5, r
        assert r['ours'] not in carried, r
    assert len({r['ours'] for r in ext['unmapped']}) == len(ext['unmapped'])


def test_the_counts_adr_0030_reports(ext):
    """50 condition terms over 48 fields, 85 terms in all, and four condition fields unmapped."""
    assert len(cb.CONDITION_TERMS) == 50 and len(cb.TERMS) == 85
    assert len({cb.TERMS[t][1].split('.')[1] for t in cb.CONDITION_TERMS}) == 48
    assert sorted(r['ours'] for r in ext['unmapped'] if r['ours'].startswith('EvalConditions.')) == [
        'EvalConditions.harness_source', 'EvalConditions.prompt_template_source',
        'EvalConditions.reasoning_effort_raw', 'EvalConditions.scaffold_source']


# ---- the terms: named, typed and placed as the record is ------------------------------------------------------

def test_each_condition_term_is_the_fields_name_in_camel_case():
    def camel(path):
        head, *rest = path.replace('.', '_').split('_')
        return head + ''.join(w.title() for w in rest)
    for term in cb.CONDITION_TERMS:
        on, ours = cb.TERMS[term]
        assert on == 'EvalConditions' and camel(ours.split('.', 1)[1]) == term, term
    assert cb.terms_for('sampling') == ('samplingTemperature', 'samplingTopP', 'samplingSeed')
    assert cb.terms_for('reasoning_effort') == ('reasoningEffort',) and cb.terms_for('scaffold_source') == ()


def untitled(prop: dict) -> dict:
    return {k: v for k, v in prop.items() if k != 'title'}


def test_each_condition_term_accepts_exactly_what_the_record_does():
    """The node's JSON Schema property is the record field's, title aside: one type, one set of constraints."""
    node = cb.ConditionsNode.model_json_schema(by_alias=True)['properties']
    record = EvalConditions.model_json_schema()
    sampling = record['$defs']['Sampling']['properties']
    for term in cb.CONDITION_TERMS:
        field = cb.TERMS[term][1].split('.')[1:]
        want = sampling[field[1]] if field[0] == 'sampling' else record['properties'][field[0]]
        assert untitled(node[term]) == untitled(want), term


def test_material_fields_names_condition_terms_only():
    prop = cb.ConditionsNode.model_json_schema(by_alias=True)['properties']['materialFields']
    assert prop['items']['enum'] == list(cb.CONDITION_TERMS)
    cb.ConditionsNode.model_validate({'@type': 'cb:EvalConditions', 'materialFields': ['shots', 'samplingSeed']})
    with pytest.raises(ValueError):
        cb.ConditionsNode.model_validate({'@type': 'cb:EvalConditions', 'materialFields': ['shot_count']})


def test_the_versions_and_subsets_terms_take_the_ids_a_claim_names():
    """A claim's benchmark_version and subset (the key's) name a BenchmarkVersion's tag and a Subset's id."""
    from schema.entities import BenchmarkVersion, Subset
    defs = cb.BenchmarkDocument.model_json_schema(by_alias=True)['$defs']
    versions = cb.BenchmarkDocument.model_json_schema(by_alias=True)['properties']['benchmarkVersions']['items']
    assert versions == untitled(BenchmarkVersion.model_json_schema()['properties']['version'])
    subsets = defs['ProtocolNode']['properties']['subsets']['items']
    assert subsets == untitled(Subset.model_json_schema()['properties']['id'])
    assert cb.TERMS['subsets'] == ('Protocol', 'Benchmark.subsets')
    assert cb.TERMS['benchmarkVersions'] == ('Benchmark', 'Benchmark.versions')


# ---- every committed conditions record maps onto a node the committed schema accepts ----------------------------

def node_for(c: EvalConditions) -> dict:
    """A cb:EvalConditions node built from a record through the mapping alone (what P4-S6-T03 will emit), with a
    null left out as the build leaves it out."""
    data = c.model_dump(mode='json')
    out = {'@type': 'cb:EvalConditions', 'conditionsId': c.id}
    for term in cb.CONDITION_TERMS:
        v = data
        for seg in cb.TERMS[term][1].split('.')[1:]:
            v = v[seg] if isinstance(v, dict) else None
        if v is not None:
            out[term] = v
    return out


def committed_conditions() -> list[EvalConditions]:
    out = []
    for name in sorted(os.listdir(CONDITIONS)):
        if name.endswith('.yaml'):
            out.append(EvalConditions.model_validate(read_yaml(os.path.join(CONDITIONS, name))))
    return out


def test_every_committed_conditions_record_maps_to_a_node_both_schemas_accept():
    import jsonschema
    with open(os.path.join(ROOT, cb.SCHEMA), encoding='utf-8') as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft202012Validator({'$schema': cb.DRAFT, '$defs': schema['$defs'],
                                                 '$ref': '#/$defs/ConditionsNode'})
    records = committed_conditions()
    assert len(records) >= 50
    carried = 0
    for c in records:
        node = node_for(c)
        cb.ConditionsNode.model_validate(node)
        assert list(validator.iter_errors(node)) == [], c.id
        answered = {f for f in FIELDS if getattr(c, f) is not None and cb.terms_for(f)}
        assert answered <= {cb.TERMS[t][1].split('.')[1] for t in node if t in cb.TERMS}, c.id   # nothing dropped
        carried += len(node) - 2
    assert carried > len(records)                                    # the records do say things, and they arrive


def test_a_node_the_record_would_refuse_the_schema_refuses_too():
    import jsonschema
    with open(os.path.join(ROOT, cb.SCHEMA), encoding='utf-8') as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft202012Validator({'$schema': cb.DRAFT, '$defs': schema['$defs'],
                                                 '$ref': '#/$defs/ConditionsNode'})
    for bad in ({'shots': -1}, {'reasoningEffort': 'extreme'}, {'samplingTopP': 0}, {'humanAssistance': 'some'},
                {'judgePromptHash': 'md5:abc'}, {'chainOfThought': 'perhaps'}):
        node = {'@type': 'cb:EvalConditions', **bad}
        assert list(validator.iter_errors(node)), bad
        with pytest.raises(ValueError):
            cb.ConditionsNode.model_validate(node)


# ---- the generated schema and the published context -------------------------------------------------------------

def test_the_committed_schema_is_what_bench_schema_gen_renders_from_this_module(monkeypatch):
    monkeypatch.setattr(codegen, 'typescript', lambda schemas, json2ts: {})       # the TS half needs node; not this
    rendered = codegen.render(ROOT)
    want = json.dumps(cb.json_schema(), indent=2, ensure_ascii=False) + '\n'
    assert rendered[cb.SCHEMA] == want
    with open(os.path.join(ROOT, cb.SCHEMA), encoding='utf-8', newline='') as fh:
        assert fh.read() == want
    assert json.loads(want)['$comment'].startswith('Generated by `bench schema gen` from schema/croissant_benchmark.py')
    assert 'ConditionsNode' in json.loads(want)['$defs']


def test_the_published_context_declares_every_term_and_only_gains():
    """v1 only ever gains terms (site/public/_headers caches /ns/* for a week for that reason): every term the
    extension had before P4-S6-T02 is still declared, as itself."""
    from tools.build import croissant
    with open(os.path.join(ROOT, croissant.CONTEXT), encoding='utf-8') as fh:
        [upstream, ours] = json.load(fh)['@context']
    assert upstream == cb.CROISSANT_VERSION
    assert ours == {cb.PREFIX: cb.NAMESPACE, **{t: '%s:%s' % (cb.PREFIX, t) for t in cb.TERMS}}
    before = ['benchmarkId', 'tasks', 'metrics', 'protocol', 'conditions', 'lineage', 'input', 'output', 'scoring',
              'testsHiddenFromSystem', 'evaluationTarget', 'executionMode', 'groundTruthSource', 'isHeadline',
              'valueType', 'optimum', 'optimumTarget', 'unbounded', 'submissionProcess', 'dataAccess',
              'aggregationPolicy', 'conditionsId', 'comparabilityProfile', 'lineageRole', 'supersedes',
              'isSupersededBy', 'subsetOf', 'extendedBy', 'decontaminates', 'variants', 'forks']
    assert all(ours[t] == 'cb:%s' % t for t in before)


def test_no_new_term_redefines_an_upstream_term():
    from tools.build import croissant
    croissant.context()                                    # raises Refused on any key upstream or in schema.org
    upstream = dict(croissant.upstream_context())
    assert not set(cb.TERMS) & (set(upstream) | croissant.schema_org_terms())
