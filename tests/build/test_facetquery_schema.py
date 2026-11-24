"""The FacetQuery JSON Schema, generated from enums.json (P6-S3-T01; tools/build/facetquery_schema.py; 11 S4, D3 S3.4).

The verify: `bench schema gen --check`. Done when: "The schema regenerates byte-identically at a fixed commit, exposes
exactly ten fields, and contains no unsupported constraint."

One block per step of the task -- the ten fields and nothing else, facet-qualified references, domain split in two
with every object closed, no unsupported constraint -- then the failures: a FacetQuery the schema or the code rules
reject, an enums.json the generator refuses, and, in a throwaway copy of the tree (tests/test_codegen.py's), the
committed file going stale when one of the ten fields' vocabularies changes and staying put when another does.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import codegen, emit  # noqa: E402
from tools.build import facetquery_schema as fq  # noqa: E402

FILE = os.path.join(ROOT, 'schema', 'generated', 'facetquery.schema.json')
JSON2TS = os.path.join(ROOT, 'site', 'node_modules', 'json-schema-to-typescript')
needs_node = pytest.mark.skipif(shutil.which('node') is None or not os.path.isdir(JSON2TS),
                                reason='node and site/node_modules (npm ci in site/) are needed for the TS step')
TEN = ('domain_family', 'domain_subdomain', 'capability', 'evaluation_method', 'subject', 'access',
       'contamination_risk', 'lifecycle', 'compute_tier', 'year_min')
YEAR = 2026


def enums() -> dict:
    return emit.nfc(emit.enums_artifact())


def committed() -> dict:
    with open(FILE, encoding='utf-8') as fh:
        return json.load(fh)


def facets_def(s: dict) -> dict:
    return s['$defs']['Facets']


def values(s: dict, slot: str) -> list[str]:
    return facets_def(s)['properties'][slot]['items']['enum']


def nodes(node, where='#'):
    """(JSON pointer, schema object) for every schema object under `node`."""
    yield where, node
    for key in ('properties', '$defs'):
        for name, sub in (node.get(key) or {}).items():
            yield from nodes(sub, '%s/%s/%s' % (where, key, name))
    if isinstance(node.get('items'), dict):
        yield from nodes(node['items'], where + '/items')
    for i, sub in enumerate(node.get('anyOf') or []):
        yield from nodes(sub, '%s/anyOf/%d' % (where, i))


def empty_facets(**set_) -> dict:
    out = {slot: [] for slot in TEN}
    out['year_min'] = None
    out.update(set_)
    return out


def example() -> dict:
    """11 S4's FacetQuery, with its bare `fully-open` qualified as step 2 requires and every slot present."""
    return {'hard': empty_facets(domain_family=['domain:medicine-health'], access=['data_properties:fully-open'],
                                 year_min=2024),
            'soft': empty_facets(capability=['capability:grounding', 'capability:context-integration']),
            'free_text_terms': ['clinical RAG', 'citation accuracy'],
            'unmapped_terms': ['production', 'latency SLO'],
            'assumptions': ["Read 'clinical assistant' as domain:medicine-health, not biology-genetics"],
            'intent': 'suite_build', 'confidence': 'high'}


# ---- the verify: byte-identical regeneration ----------------------------------------------------

def test_the_committed_file_is_what_generation_writes_byte_for_byte():
    path, content = codegen.facetquery()
    assert path == 'schema/generated/facetquery.schema.json'
    assert open(FILE, 'rb').read() == content.encode('utf-8')
    assert b'\r' not in content.encode('utf-8') and content.endswith('}\n')


def test_two_generations_are_identical_and_the_shipped_enums_json_gives_the_same_schema():
    """`bench build` writes enums.json with emit.serialise; reading that file back yields the schema codegen writes."""
    shipped = json.loads(emit.serialise(enums()).decode('utf-8'))
    assert json.dumps(fq.schema(shipped)) == json.dumps(fq.schema(enums())) == json.dumps(committed())


@needs_node
def test_verify_bench_schema_gen_check_passes():
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'cli.py'), 'schema', 'gen', '--check'],
                       capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert r.returncode == 0, r.stderr


# ---- step 1: the ten declared fields, no other vocabulary ---------------------------------------

def test_facets_expose_exactly_the_ten_fields_and_hard_and_soft_share_them():
    s = committed()
    assert tuple(fq.FIELDS) == TEN
    assert tuple(facets_def(s)['properties']) == TEN
    assert s['properties']['hard'] == s['properties']['soft'] == {'$ref': '#/$defs/Facets'}
    assert list(s['$defs']) == ['Facets']
    assert list(s['properties']) == ['hard', 'soft', 'free_text_terms', 'unmapped_terms', 'assumptions', 'intent',
                                     'confidence']
    assert s['properties']['intent']['enum'] == ['suite_build', 'lookup', 'compare', 'ecosystem_question',
                                                 'out_of_scope']
    assert s['properties']['confidence']['enum'] == ['high', 'low']


def test_each_slot_holds_exactly_its_vocabulary_field_and_nothing_else():
    e, s = enums(), committed()
    vocab = e['vocabularies']
    live = lambda name: [t for t in vocab[name]['terms'] if t['status'] != 'retired']   # noqa: E731
    want = {
        'domain_family': ['domain:' + t['id'] for t in live('domain') if t['parent'] is None],
        'domain_subdomain': ['domain:' + t['id'] for t in live('domain') if t['parent'] is not None],
        'capability': ['capability:' + t['id'] for t in live('capability')],
        'evaluation_method': ['evaluation_method:' + t['id'] for t in live('evaluation_method')],
        'subject': ['subject:' + t['id'] for t in live('subject')],
        'access': ['data_properties:' + t['id'] for t in live('data_properties') if t['field'] == 'data.access'],
        'contamination_risk': ['data_properties:' + t['id'] for t in live('data_properties')
                               if t['field'] == 'data.contamination_risk'],
        'lifecycle': ['lifecycle:' + t['id'] for t in live('lifecycle') if t['field'] == 'lifecycle'],
        'compute_tier': ['execution:' + t['id'] for t in live('execution') if t['field'] == 'execution.compute_tier'],
    }
    for slot, expected in want.items():
        assert values(s, slot) == expected and expected, slot
    assert len(values(s, 'domain_family')) == 19            # D4's nineteen families


def test_the_other_controlled_vocabularies_stay_out():
    text = open(FILE, encoding='utf-8').read()
    for name in ('capability_group', 'governance', 'ceiling_anchor_type', 'maintenance_status', 'verification'):
        assert '"%s:' % name not in text, name
    # the field vocabularies the ten draw on: only their slots' fields are in, so refresh, provenance, activity and
    # the other three execution fields are out (an id one of them shares with a kept field, wet-lab, is the kept one)
    vocab, in_schema = enums()['vocabularies'], {v for slot in TEN[:-1] for v in values(committed(), slot)}
    slot_fields = set(fq.FIELDS.values())
    for name in ('data_properties', 'lifecycle', 'execution'):
        kept = {t['id'] for t in vocab[name]['terms'] if (name, t['field']) in slot_fields}
        dropped = {t['id'] for t in vocab[name]['terms'] if (name, t['field']) not in slot_fields} - kept
        assert dropped and not {'%s:%s' % (name, i) for i in dropped} & in_schema, name
    assert '"data_properties:static"' not in text and '"lifecycle:accepting-submissions"' not in text


def test_a_retired_term_is_left_out_and_a_deprecated_one_kept():
    e = enums()
    terms = e['vocabularies']['capability']['terms']
    terms[0]['status'], terms[1]['status'] = 'retired', 'deprecated'
    got = values(fq.schema(e), 'capability')
    assert 'capability:' + terms[0]['id'] not in got and 'capability:' + terms[1]['id'] in got


# ---- step 2: facet-qualified references, never bare slugs ---------------------------------------

def test_every_facet_value_is_a_facet_qualified_reference():
    s = committed()
    fqr = re.compile(r'^[a-z_]+:[a-z0-9/-]+$')                 # D3 S3.1
    bare = {t['id'] for v in enums()['vocabularies'].values() for t in v['terms']}
    for slot in TEN[:-1]:
        for v in values(s, slot):
            assert fqr.match(v) and v not in bare, (slot, v)


def test_the_four_homographs_are_qualified_on_both_sides():
    s = committed()
    entries = read_yaml(os.path.join(ROOT, 'taxonomy', 'homographs.yaml'))['entries']
    assert len(entries) == 4
    for h in entries:
        assert h['capability'] in values(s, 'capability'), h['capability']
        assert h['domain'] in values(s, 'domain_subdomain'), h['domain']
    assert 'capability:planning' in values(s, 'capability')
    assert 'domain:reasoning-general/planning' in values(s, 'domain_subdomain')


def test_a_slot_disambiguates_an_id_its_vocabulary_repeats_across_fields():
    """execution.yaml's `wet-lab` is a compute tier and a blocker; only the tier is in compute_tier, and its
    enums.json key is the field-qualified spelling facets.json writes."""
    assert 'execution:wet-lab' in values(committed(), 'compute_tier')
    [tier] = [t for t in enums()['vocabularies']['execution']['terms']
              if t['id'] == 'wet-lab' and t['field'] == 'execution.compute_tier']
    assert tier['key'] == 'execution.compute_tier:wet-lab'


# ---- step 3: domain split in two, every object closed -------------------------------------------

def test_domain_is_split_into_family_and_subdomain():
    s = committed()
    families, subdomains = values(s, 'domain_family'), values(s, 'domain_subdomain')
    assert all('/' not in v for v in families) and all('/' in v for v in subdomains)
    assert {v.split('/')[0] for v in subdomains} <= set(families)
    assert not set(families) & set(subdomains)


def test_every_object_has_additional_properties_false_and_no_optional_property():
    objects = [(w, n) for w, n in nodes(committed()) if n.get('type') == 'object' or 'properties' in n]
    assert len(objects) == 2                                   # the FacetQuery and $defs/Facets
    for where, n in objects:
        assert n['additionalProperties'] is False, where
        assert n['required'] == list(n['properties']), where


def test_the_schema_is_within_the_documented_complexity_limits():
    """config/ai-models.yaml's structured-outputs limits: optional parameters and union-typed parameters, counted
    across the request, with $defs/Facets counted once per $ref (hard and soft)."""
    cfg = read_yaml(os.path.join(ROOT, 'config', 'ai-models.yaml'))
    [row] = [f for f in cfg['facts'] if f['id'] == 'structured-outputs-behaviour']
    limits = row['value']['limits']
    s = committed()
    uses = {'Facets': sum(1 for _, n in nodes(s) if n.get('$ref') == '#/$defs/Facets')}
    assert uses == {'Facets': 2}
    weight = lambda where: uses['Facets'] if where.startswith('#/$defs/Facets') else 1   # noqa: E731
    unions = sum(weight(w) for w, n in nodes(s) if isinstance(n.get('type'), list) or 'anyOf' in n)
    optional = sum(weight(w) * len(set(n.get('properties') or {}) - set(n.get('required') or []))
                   for w, n in nodes(s))
    assert optional == 0 <= limits['optional_parameters']
    assert unions == 2 <= limits['union_type_parameters']


# ---- step 4: no unsupported constraint ----------------------------------------------------------

def test_no_unsupported_keyword_anywhere():
    s = committed()
    assert fq.audit(s) == []
    for where, n in nodes(s):
        assert set(n) <= fq.ALLOWED_KEYWORDS, (where, set(n) - fq.ALLOWED_KEYWORDS)
    text = open(FILE, encoding='utf-8').read()
    for keyword in ('minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf', 'minLength',
                    'maxLength', 'maxItems', 'uniqueItems', 'pattern', 'oneOf', '$schema', '$comment', 'minItems'):
        assert '"%s":' % keyword not in text, keyword
    assert set(fq.CODE_ENFORCED) == {'minimum', 'maximum', 'minLength', 'uniqueItems'}


@pytest.mark.parametrize('inject, expect', [
    (lambda s: s['$defs']['Facets']['properties']['year_min'].update(minimum=1950), 'minimum is not a keyword'),
    (lambda s: s['properties']['free_text_terms']['items'].update(minLength=1), 'minLength is not a keyword'),
    (lambda s: s['properties']['unmapped_terms'].update(uniqueItems=True), 'uniqueItems is not a keyword'),
    (lambda s: s.update({'$schema': codegen.DRAFT}), '$schema is not a keyword'),
    (lambda s: s['properties']['assumptions'].update(minItems=2), 'minItems 2'),
    (lambda s: s['$defs']['Facets'].update(additionalProperties=True), 'without additionalProperties: false'),
    (lambda s: s['$defs']['Facets']['required'].remove('year_min'), 'optional properties year_min'),
    (lambda s: s['properties']['hard'].update({'$ref': 'https://example.org/facets.json'}), "is not to this"),
])
def test_audit_catches_each_unsupported_construct(inject, expect):
    s = copy.deepcopy(committed())
    inject(s)
    problems = fq.audit(s)
    assert len(problems) == 1 and expect in problems[0], problems


# ---- a FacetQuery: what the schema rejects, and what code rejects instead -----------------------

def test_the_plan_example_is_a_valid_facetquery():
    s = committed()
    Draft202012Validator.check_schema(s)
    assert fq.violations(example(), s, YEAR) == []


@pytest.mark.parametrize('edit, expect', [
    (lambda q: q['soft'].update(capability=['planning']), "'planning' is not one of"),            # a bare slug
    (lambda q: q['hard'].update(domain_family=['domain:reasoning-general/planning']), 'is not one of'),
    (lambda q: q['hard'].update(domain_subdomain=['domain:medicine-health']), 'is not one of'),
    (lambda q: q['hard'].update(governance=['governance:academic-lab']), 'Additional properties'),
    (lambda q: q['hard'].pop('lifecycle'), "'lifecycle' is a required property"),
    (lambda q: q.pop('unmapped_terms'), "'unmapped_terms' is a required property"),
    (lambda q: q.update(confidence='medium'), "'medium' is not one of"),
    (lambda q: q['hard'].update(year_min='2024'), "is not of type 'integer', 'null'"),
])
def test_the_schema_rejects(edit, expect):
    q = example()
    edit(q)
    got = fq.violations(q, committed(), YEAR)
    assert len(got) == 1 and expect in got[0], got


@pytest.mark.parametrize('edit, expect', [
    (lambda q: q['hard'].update(year_min=24), '24 is outside 1950..2026 (minimum)'),
    (lambda q: q['soft'].update(year_min=YEAR + 1), '2027 is outside 1950..2026 (maximum)'),
    (lambda q: q['unmapped_terms'].append('  '), 'unmapped_terms/2: a blank string (minLength)'),
    (lambda q: q['soft']['capability'].append('capability:grounding'), 'appears more than once (uniqueItems)'),
])
def test_code_enforces_what_the_schema_cannot_say(edit, expect):
    q = example()
    edit(q)
    assert Draft202012Validator(committed()).is_valid(q)       # the schema lets it through
    got = fq.violations(q, committed(), YEAR)
    assert len(got) == 1 and expect in got[0], got


# ---- the generator refuses a broken enums.json --------------------------------------------------

def test_the_generator_refuses_a_missing_vocabulary_an_empty_slot_and_a_value_outside_the_grammar():
    e = enums()
    del e['vocabularies']['execution']
    e['vocabularies']['data_properties']['terms'] = [t for t in e['vocabularies']['data_properties']['terms']
                                                     if t['field'] != 'data.access']
    e['vocabularies']['capability']['terms'][0]['id'] = 'Tool Use'
    with pytest.raises(fq.Refused) as err:
        fq.schema(e)
    errors = err.value.errors
    assert len(errors) == 3, errors
    assert "compute_tier: enums.json has no vocabulary 'execution'" in errors
    assert any(m.startswith('access: no data.access term') for m in errors)
    assert any(m.startswith("capability: 'capability:Tool Use' is not a facet-qualified reference") for m in errors)


def test_only_the_ten_fields_vocabularies_move_the_schema():
    e = enums()
    for t in e['vocabularies']['governance']['terms'] + e['vocabularies']['execution']['terms']:
        if t.get('field') != 'execution.compute_tier':
            t['id'] += '-renamed'
    assert fq.schema(e) == committed()
    e['vocabularies']['execution']['terms'][0]['id'] += '-renamed'
    assert fq.schema(e) != committed()


# ---- `bench schema gen --check` holds the committed file to taxonomy/ ---------------------------

@pytest.fixture
def tree(tmp_path):
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc')
    for d in ('schema', 'taxonomy', 'tools'):
        shutil.copytree(os.path.join(ROOT, d), tmp_path / d, ignore=ignore)
    shutil.copytree(os.path.join(ROOT, 'site', 'src', 'types'), tmp_path / 'site' / 'src' / 'types')
    shutil.copytree(os.path.join(ROOT, 'site', 'public', 'ns'), tmp_path / 'site' / 'public' / 'ns')
    return tmp_path


def bench(root, *args):
    return subprocess.run([sys.executable, os.path.join(str(root), 'tools', 'cli.py'), *args, '--json2ts', JSON2TS],
                          capture_output=True, text=True, encoding='utf-8', cwd=str(root))


def rename(tree, file, field, old, new):
    from ruamel.yaml import YAML
    y = YAML()
    p = tree / 'taxonomy' / file
    doc = y.load(p.read_text(encoding='utf-8'))
    [term] = [t for t in doc['terms'] if t['field'] == field and t['id'] == old]
    term['id'] = new
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        y.dump(doc, fh)


@needs_node
def test_check_fails_when_a_ten_field_vocabulary_changes_and_not_when_another_does(tree):
    rel = 'schema/generated/facetquery.schema.json'
    rename(tree, 'lifecycle.yaml', 'activity', 'between-rounds', 'between-editions')        # not one of the ten
    r = bench(tree, 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'differs  schema/generated/benchmark.schema.json' in r.stderr, r.stderr
    assert rel not in r.stderr
    assert bench(tree, 'schema', 'gen').returncode == 0
    rename(tree, 'execution.yaml', 'execution.compute_tier', 'provided-allocation', 'granted-allocation')
    r = bench(tree, 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'differs  %s' % rel in r.stderr, r.stderr
    assert '"execution:provided-allocation"' in (tree / rel).read_text(encoding='utf-8')   # the committed file is stale
    assert bench(tree, 'schema', 'gen').returncode == 0
    assert bench(tree, 'schema', 'gen', '--check').returncode == 0
    text = (tree / rel).read_text(encoding='utf-8')
    assert '"execution:granted-allocation"' in text and '"execution:provided-allocation"' not in text


@needs_node
def test_a_hand_edit_or_a_deleted_file_is_drift(tree):
    p = tree / 'schema' / 'generated' / 'facetquery.schema.json'
    p.write_text(p.read_text(encoding='utf-8').replace('"year_min": {', '"year_min": {\n "minimum": 1950,', 1),
                 encoding='utf-8', newline='\n')
    r = bench(tree, 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'differs  schema/generated/facetquery.schema.json' in r.stderr, r.stderr
    os.remove(p)
    r = bench(tree, 'schema', 'gen', '--check')
    assert r.returncode == 1 and 'missing  schema/generated/facetquery.schema.json' in r.stderr, r.stderr
