"""04 S15's twenty-one pre-ingest prerequisites, asserted (P3-S1-T01).

04 S15: "every one of them must be complete before the Phase 3 Epoch adapter runs". One test per
item, each naming its field paths. A field is asserted on the GENERATED JSON Schema in
schema/generated/, which is what an external consumer and the frontend read -- not on the Pydantic
models, so a field that exists in Python but never reached the generated schema fails here.

Three kinds of item are not plain field assertions, and each is stated where it is tested:

  - Derived fields (items 13, 14, 15): `maintenance_status`, `curation.stewardship` and
    `execution.inspect_evals_available` are derived, never hand-written (04 S5). The generated
    schema is the VALIDATION schema -- what a record may contain -- so they are absent from it by
    design. Their test asserts what the schema half can: absent from the input schema, refused when
    hand-set, and where the model computes them (inspect_evals_available), computed.
  - Item 19 is asserted as schema/taxonomy.py importing and validating every vocabulary file, and
    item 21 as the ten stress entries validating against the generated JSON Schema (the task's
    own reading).
  - Rules that are procedures, not fields (item 8's "adapters never create entities", item 13's
    derivation from liveness) belong to the tasks that build them; this file asserts the schema
    they need.

What is missing is not added here (the task's step 3). Two gaps are recorded as strict xfails, so
they fail loudly the day the gap closes and the mark must be removed:

  - item 16: `EvalConditions.training_data_eligibility` is not in the schema;
  - item 21: seven of the ten stress entries (P0-S8) do not exist yet.
"""
import datetime
import glob
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
GENERATED = os.path.join(ROOT, 'schema', 'generated')
SCHEMAS = {os.path.basename(p)[:-len('.schema.json')]: json.load(open(p, encoding='utf-8'))
           for p in glob.glob(os.path.join(GENERATED, '*.schema.json'))}


# ---- reading the generated schema ---------------------------------------------------------------

def _deref(root, node):
    """Follow $ref, pick the object branch of an Optional/anyOf, and step into array items."""
    while True:
        if '$ref' in node:
            node = root['$defs'][node['$ref'].rsplit('/', 1)[-1]]
            continue
        branches = node.get('anyOf') or node.get('oneOf')
        if branches:
            objects = [b for b in (_deref(root, b) for b in branches if b.get('type') != 'null')
                       if 'properties' in b]
            if objects:
                node = objects[0]
                continue
        if node.get('type') == 'array' and isinstance(node.get('items'), dict):
            node = node['items']
            continue
        return node


def node_at(entity: str, path: str):
    """The JSON Schema node at a dotted field path on an entity's generated schema, or None."""
    schema = SCHEMAS[entity]
    node = schema
    for seg in path.split('.'):
        props = _deref(schema, node).get('properties', {})  # get-default: a JSON Schema node without properties has none
        if seg not in props:
            return None
        node = props[seg]
    return node


def enum_at(entity: str, path: str) -> set:
    node = node_at(entity, path)
    assert node is not None, '%s.%s is not in schema/generated/' % (entity, path)
    values = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if '$ref' in n:
            stack.append(SCHEMAS[entity]['$defs'][n['$ref'].rsplit('/', 1)[-1]])
        values |= set(n.get('enum', []))  # get-default: enum is an optional JSON Schema keyword
        if 'const' in n:
            values.add(n['const'])
        stack += n.get('anyOf', []) + n.get('oneOf', [])  # get-default: optional JSON Schema keywords, absent means none
        if isinstance(n.get('items'), dict):
            stack.append(n['items'])
    return values


def assert_fields(entity: str, *paths: str):
    missing = [p for p in paths if node_at(entity, p) is None]
    assert not missing, 'missing from schema/generated/%s.schema.json: %s' % (entity, ', '.join(missing))


def required(entity: str, path: str = '') -> set:
    node = SCHEMAS[entity] if not path else _deref(SCHEMAS[entity], node_at(entity, path))
    return set(_deref(SCHEMAS[entity], node).get('required', []))  # get-default: no required keyword means none required


def test_every_entity_the_items_name_has_a_generated_schema():
    assert {'result-claim', 'system', 'eval-conditions', 'ingest-batch', 'alias', 'metric', 'baseline',
            'benchmark', 'subset', 'source'} <= set(SCHEMAS)


def test_the_reader_finds_nested_and_optional_fields_and_rejects_invented_ones():
    assert node_at('result-claim', 'provenance_snapshot.raw') is not None      # Optional[model]
    assert node_at('benchmark', 'learned_entrant_evidence.source') is not None  # list[model]
    assert node_at('benchmark', 'data.no_such_field') is None


# ---- the four C5 additions ----------------------------------------------------------------------

def test_item_01_claim_artifact_url_and_artifact_archived():
    assert_fields('result-claim', 'artifact_url', 'artifact_archived')


def test_item_02_claim_provenance_snapshot():
    assert_fields('result-claim', 'provenance_snapshot', 'provenance_snapshot.source_record_id',
                  'provenance_snapshot.retrieved_at', 'provenance_snapshot.content_sha256',
                  'provenance_snapshot.raw')
    # distinct from ingestion.field_provenance (04 S7)
    assert_fields('result-claim', 'ingestion.field_provenance')


def test_item_03_system_training_compute():
    assert_fields('system', 'training_compute_flop', 'training_compute_estimated', 'training_compute_notes')


def test_item_04_reasoning_effort_enum_plus_raw_text():
    assert_fields('eval-conditions', 'reasoning_effort', 'reasoning_effort_raw')
    assert enum_at('eval-conditions', 'reasoning_effort') == {'max', 'xhigh', 'high', 'medium', 'low',
                                                               'minimal', 'none'}
    from schema.conditions import parse_reasoning_effort
    assert parse_reasoning_effort('unknown') is None                  # `unknown` -> null, not a value


# ---- everything else 04's rules depend on -------------------------------------------------------

def test_item_05_claim_serving_provider_type_resolution_group():
    assert_fields('result-claim', 'serving_provider', 'claim_type', 'resolution_status', 'result_group')
    assert {'pending', 'resolved'} <= enum_at('result-claim', 'resolution_status')


def test_item_06_claim_external_ids_eee_result_id():
    assert_fields('result-claim', 'external_ids.eee_result_id')


def test_item_07_the_ingestion_block_and_ingest_batch():
    assert_fields('result-claim', 'ingestion', 'ingestion.batch', 'ingestion.licence_class',
                  'ingestion.source_record_id', 'ingestion.last_seen_upstream')
    assert_fields('ingest-batch', 'resolver_snapshot_sha256', 'licence', 'licence.class')
    from schema import validators
    assert 'licence-placement' in validators.RULES                      # licence_class, enforced at tier 3
    # source_record_id in its stable content-key form: a row index is refused
    from schema.claim import Ingestion
    base = {'batch': 'ingest-epoch-2026-09-16', 'source_adapter': 'epoch-benchmarks', 'adapter_version': '0.3.1',
            'last_seen_upstream': '2026-09-16', 'source_url': 'https://epoch.ai/data/benchmark_data.zip',
            'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
            'source_attribution': 'Epoch AI', 'ingested_at': '2026-09-16T23:14:00Z', 'extraction_confidence': 1.0}
    Ingestion.model_validate({**base, 'source_record_id': 'gpqa-diamond:example-model'})
    with pytest.raises(ValueError, match='row'):
        Ingestion.model_validate({**base, 'source_record_id': 'benchmark_data.csv#row=17'})


def test_item_08_the_alias_tables():
    assert_fields('alias', 'alias', 'resolves_to', 'extracts', 'kind', 'confidence', 'decided_by', 'decided_on',
                  'source')
    assert enum_at('alias', 'kind') >= {'exact', 'provider-endpoint', 'legacy-name'}
    from schema.entities import AliasFile
    with pytest.raises(ValueError, match='resolves to both'):         # one resolution per verbatim string
        AliasFile.model_validate([
            {'alias': 'X', 'resolves_to': 'system:a', 'kind': 'exact', 'confidence': 'high',
             'decided_by': 'me', 'decided_on': '2026-09-25'},
            {'alias': 'X', 'resolves_to': 'system:b', 'kind': 'exact', 'confidence': 'high',
             'decided_by': 'me', 'decided_on': '2026-09-25'}])


def test_item_09_metric_headroom_fields():
    assert_fields('metric', 'optimum', 'unbounded', 'requires_pool', 'headroom_computable', 'must_report_with')


def test_item_10_baseline_replaces_human_baseline():
    assert 'human-baseline' not in SCHEMAS
    assert not any('HumanBaseline' in json.dumps(s) for s in SCHEMAS.values())
    kinds = enum_at('baseline', 'kind')
    assert {'noise-ceiling', 'experimental-replicate'} <= kinds and 'biological-replicate' not in kinds
    # the facet rename, mirrored: human_baseline_type -> ceiling_anchor_type (02 S7)
    assert_fields('benchmark', 'data.ceiling_anchor_type')
    assert not any('human_baseline_type' in json.dumps(s) for s in SCHEMAS.values())
    anchors = enum_at('benchmark', 'data.ceiling_anchor_type')
    assert {'noise-ceiling', 'experimental-replicate'} <= anchors and 'biological-replicate' not in anchors


def test_item_11_benchmark_reference_conditions():
    assert_fields('benchmark', 'reference_conditions')


def test_item_12_the_admissibility_block():
    assert_fields('benchmark', 'learned_entrant_evidence', 'evaluation_target', 'execution_mode',
                  'ground_truth_source', 'reproducible_by_third_party')
    assert {'learned_entrant_evidence', 'evaluation_target'} <= required('benchmark')


def _refuses(path: str, value):
    """True when the Benchmark model refuses `path` hand-set on a valid record."""
    from pydantic import ValidationError

    from schema.benchmark import Benchmark
    doc = json.loads(json.dumps(_BASE))
    *parents, leaf = path.split('.')
    target = doc
    for p in parents:
        target = target.setdefault(p, {})
    target[leaf] = value
    try:
        Benchmark.model_validate(doc)
    except ValidationError:
        return True
    return False


_BASE = {
    'id': 'example-bench', 'name': 'Example Bench', 'tagline': 'A benchmark used in tests.',
    'domain': {'primary': 'code/repository-scale-se'},
    'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-x', 'observed_on': '2026-09-25'}],
    'evaluation_target': 'learned-system', 'data': {'access': 'fully-open'}, 'homepage': 'https://example.org/',
    'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25',
                 'sources': ['src-x']},
}


def test_the_base_record_is_valid_so_a_refusal_means_the_field():
    from schema.benchmark import Benchmark
    Benchmark.model_validate(_BASE)


def test_item_13_maintenance_status_and_the_contested_triple():
    assert_fields('benchmark', 'maintenance_status_contested', 'contested_source', 'contested_statement_date',
                  'liveness', 'liveness.repo_last_commit', 'liveness.leaderboard_last_updated',
                  'liveness.last_checked')
    # maintenance_status is derived from liveness: not an input field, refused when hand-set, and its
    # vocabulary is a validated taxonomy file
    assert node_at('benchmark', 'maintenance_status') is None
    assert _refuses('maintenance_status', 'active')
    from schema.taxonomy import load_taxonomy
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))
    assert models['maintenance.yaml'].terms


def test_item_14_stewardship_and_system_availability():
    assert node_at('benchmark', 'curation.stewardship') is None        # derived: set by CI at 24 months
    assert _refuses('curation.stewardship', 'current')
    assert_fields('system', 'availability', 'retired_on')


def test_item_15_runnable_via_and_inspect_evals():
    assert_fields('benchmark', 'execution.runnable_via', 'execution.inspect_evals_id')
    assert node_at('benchmark', 'execution.inspect_evals_available') is None   # derived from inspect_evals_id
    assert _refuses('execution.inspect_evals_available', True)
    from schema.benchmark import Benchmark
    doc = json.loads(json.dumps(_BASE))
    doc['execution'] = {'inspect_evals_id': 'swe_bench'}
    assert Benchmark.model_validate(doc).execution.inspect_evals_available is True
    assert Benchmark.model_validate(_BASE).execution.inspect_evals_available is False


def test_item_16_the_02_s12_handoff_fields():
    assert_fields('benchmark', 'no_legitimate_aggregate', 'secondary_axes', 'training_data_eligibility_tiers',
                  'data.submission_limit', 'execution.est_participant_cost_usd',
                  'comparability.rating_pool_required')
    assert_fields('subset', 'domain_override')
    from schema.taxonomy import Term
    assert 'gap_placeholder' in Term.model_fields                        # on the taxonomy term record


@pytest.mark.xfail(strict=True, reason='04 S15 item 16 / 02 S12 handoff: EvalConditions.training_data_eligibility '
                   'is not in the schema. Blocking issue raised by P3-S1-T01; not added here (step 3). Remove this '
                   'mark when the field lands.')
def test_item_16_eval_conditions_training_data_eligibility():
    assert_fields('eval-conditions', 'training_data_eligibility')


def test_item_17_curation_posture_on_the_domain_family_record():
    from schema.taxonomy import DomainTerm, load_taxonomy
    assert 'curation_posture' in DomainTerm.model_fields and 'curation_posture' in DomainTerm.FAMILY_FIELDS
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))
    families = [t for t in models['domains.yaml'].terms if not t.parent]
    assert len(families) == 19 and all(t.curation_posture for t in families)
    # check 9f extended to it: taxonomy_stats.py checks curation_posture against 01 S10
    stats = open(os.path.join(ROOT, 'scripts', 'taxonomy_stats.py'), encoding='utf-8').read()
    assert re.search(r"9f curation_posture", stats)


def test_item_18_source_in_full():
    assert_fields('source', 'licence_class', 'licence_checked_on', 'archive_url', 'archive_digest',
                  'content_sha256', 'quote_extract')
    assert {'licence_class', 'licence_checked_on'} <= required('source')


def test_item_19_schema_taxonomy_validates_every_vocabulary_file():
    from schema.taxonomy import load_taxonomy
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))   # raises TaxonomyError listing every failure
    on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'taxonomy', '*.yaml'))}
    assert set(models) == on_disk, 'a vocabulary file schema/taxonomy.py does not validate: %s' % (
        sorted(on_disk - set(models)))


def test_item_20_thresholds_declared_by_name():
    from schema.taxonomy import ThresholdFile, read_yaml
    t = ThresholdFile.model_validate(read_yaml(os.path.join(ROOT, 'taxonomy', 'thresholds.yaml')))
    assert {'frontier_floor', 'comparison_floor'} <= set(t.thresholds)


# ---- item 21: the ten stress entries against the generated JSON Schema ---------------------------

# 14-roadmap.md's stress-test entry table. Ids are allocated by the curator (04 S3), so an entry is
# matched by its name.
STRESS = ('SWE-bench', 'CASP', 'RoboArena', 'WeatherBench 2', 'Matbench Discovery', 'ARC-AGI-3',
          'Virtual Cell Challenge', 'Kaggle Game Arena', 'ForecastBench', 'PaperBench')


def _json(x):
    """YAML's dates as the ISO strings JSON Schema's `format: date` expects."""
    if isinstance(x, dict):
        return {str(k): _json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_json(v) for v in x]
    if isinstance(x, (datetime.date, datetime.datetime)):
        return x.isoformat()
    return x


def stress_entries() -> dict:
    from schema.taxonomy import read_yaml
    found = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True)):
        doc = read_yaml(p)
        names = [doc.get('name', '')] + list(doc.get('aliases') or [])  # get-default: a stub may lack a name; it matches nothing
        for s in STRESS:
            if any(n.lower().startswith(s.lower()) for n in names if isinstance(n, str)):
                found[s] = (p, doc)
    return found


def test_item_21_every_stress_entry_present_validates_against_the_generated_schema():
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(SCHEMAS['benchmark'])
    found = stress_entries()
    assert {'SWE-bench', 'CASP', 'RoboArena'} <= set(found)              # the three P0-S3 entries
    for name, (path, doc) in found.items():
        errors = sorted(validator.iter_errors(_json(doc)), key=lambda e: list(e.absolute_path))
        assert not errors, '%s (%s): %s' % (name, os.path.relpath(path, ROOT), [
            ('.'.join(map(str, e.absolute_path)), e.message[:120]) for e in errors[:5]])


def test_item_21_the_generated_schema_rejects_a_broken_entry():
    from jsonschema import Draft202012Validator
    path, doc = stress_entries()['SWE-bench']
    broken = _json(doc)
    broken['domain']['primary'] = 'code/no-such-subdomain'
    assert list(Draft202012Validator(SCHEMAS['benchmark']).iter_errors(broken))


@pytest.mark.xfail(strict=True, reason='04 S15 item 21: seven of the ten stress entries do not exist yet (P0-S8-T01..T07, '
                   'then P0-S9-T01 wires them as CI fixtures). Blocking issue raised by P3-S1-T01. Remove this mark '
                   'when all ten are in data/benchmarks/.')
def test_item_21_all_ten_stress_entries_exist():
    missing = [s for s in STRESS if s not in stress_entries()]
    assert not missing, 'stress entries not yet curated: %s' % ', '.join(missing)
