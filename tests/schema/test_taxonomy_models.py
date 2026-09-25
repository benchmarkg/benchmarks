"""Tests for schema/taxonomy.py (P0-S4-T02; 04-data-model.md S12, 03 S4-S5, 02 S11).

The verify: "every taxonomy/*.yaml loads into its model, and a fixture with a misspelled key or a
term missing its exclusion_test fails". Both fixtures are in tests/schema/fixtures/; the rest of
the rules are tested on small in-memory documents built from the real files.
"""
import copy
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema import taxonomy as tx  # noqa: E402

TAXONOMY = os.path.join(ROOT, 'taxonomy')
FIX = os.path.join(ROOT, 'tests', 'schema', 'fixtures')
PRE = {'taxonomy_version': '0.1.0'}


def real(name):
    return tx.read_yaml(os.path.join(TAXONOMY, name))


def ctx(version='0.1.0', **extra):
    return {'taxonomy_version': version, 'warnings': [], **extra}


def capability_file(**term_changes):
    doc = real('capabilities.yaml')
    doc['terms'] = [copy.deepcopy(doc['terms'][0])]
    doc['terms'][0].pop('see_also', None)
    doc['terms'][0].pop('not_to_be_confused_with', None)
    for k, v in term_changes.items():
        if v is None:
            doc['terms'][0].pop(k, None)
        else:
            doc['terms'][0][k] = v
    return doc


def fails(name, doc, context=None, match=None):
    with pytest.raises((ValidationError, ValueError)) as e:
        tx.validate_file(name, doc, context if context is not None else ctx())
    if match:
        assert match in str(e.value), str(e.value)
    return str(e.value)


# ---- the verify ---------------------------------------------------------------------------------

def test_every_taxonomy_file_loads_into_its_model():
    models, warnings = tx.load_taxonomy(TAXONOMY)
    on_disk = sorted(n for n in os.listdir(TAXONOMY) if n.endswith('.yaml'))
    assert sorted(models) == on_disk == sorted(tx.FILES)
    for name, obj in models.items():
        assert isinstance(obj, tx.FILES[name][0]), name
    # The counts 02 S14 fixes, read back through the models.
    assert len(models['capabilities.yaml'].terms) == 44
    assert len(models['evaluation-methods.yaml'].terms) == 27
    assert len(models['subjects.yaml'].terms) == 18
    doms = models['domains.yaml'].terms
    assert (sum(t.parent is None for t in doms), sum(t.parent is not None for t in doms)) == (19, 204)


def test_the_misspelled_key_fixture_fails():
    msg = fails('capabilities.yaml', tx.read_yaml(os.path.join(FIX, 'misspelled-key.yaml')))
    assert 'exclusion_tset' in msg and 'Extra inputs are not permitted' in msg


def test_the_missing_exclusion_test_fixture_fails():
    fails('capabilities.yaml', tx.read_yaml(os.path.join(FIX, 'missing-exclusion-test.yaml')),
          match='needs an exclusion_test')


def test_the_warnings_are_the_pre_freeze_empty_examples_and_the_shared_id():
    _, warnings = tx.load_taxonomy(TAXONOMY)
    shared = [w for w in warnings if 'defined in 2 fields' in w]
    assert shared == [w for w in warnings if w.startswith('execution.yaml') and 'wet-lab' in w and 'fields' in w]
    rest = [w for w in warnings if w not in shared]
    assert rest and all('permitted while taxonomy/VERSION < 1.0.0' in w for w in rest)
    # The spine files carry their examples already; only field vocabularies warn.
    assert not any(w.split(':')[0] in ('capabilities.yaml', 'evaluation-methods.yaml', 'subjects.yaml', 'domains.yaml')
                   for w in rest)


# ---- misspellings anywhere are errors -----------------------------------------------------------

@pytest.mark.parametrize('name, where', [
    ('capabilities.yaml', 'header'),
    ('domains.yaml', 'term'),
    ('capability_groups.yaml', 'header'),
    ('thresholds.yaml', 'header'),
    ('verification.yaml', 'header'),
    ('comparability-profiles.yaml', 'header'),
])
def test_an_unknown_key_anywhere_is_an_error(name, where):
    doc = real(name)
    if where == 'header':
        doc['descripton'] = 'typo'
    else:
        doc['terms'][0]['seed_targt'] = 3
    fails(name, doc, match='Extra inputs are not permitted')


def test_a_duplicate_yaml_key_is_an_error(tmp_path):
    p = tmp_path / 'dup.yaml'
    p.write_text('a: 1\na: 2\n', encoding='utf-8')
    with pytest.raises(Exception, match='duplicate key'):
        tx.read_yaml(str(p))


def test_a_file_without_a_model_is_an_error(tmp_path):
    for n in os.listdir(TAXONOMY):
        if n.endswith('.yaml') or n == 'VERSION':
            (tmp_path / n).write_bytes(open(os.path.join(TAXONOMY, n), 'rb').read())
    (tmp_path / 'new-facet.yaml').write_text('facet: new\n', encoding='utf-8')
    with pytest.raises(tx.TaxonomyError, match='new-facet.yaml: no model for this file'):
        tx.load_taxonomy(str(tmp_path))


def test_the_declared_facet_must_match_the_file():
    doc = real('subjects.yaml')
    doc['facet'] = 'capability'
    fails('subjects.yaml', doc, match="declares facet 'capability', expected 'subject'")


# ---- 03 S5's four admissibility rules on Term ----------------------------------------------------

def test_a_well_formed_term_passes():
    tx.validate_file('capabilities.yaml', capability_file(), ctx())


def test_rule_1_definition_is_one_sentence():
    fails('capabilities.yaml', capability_file(definition='It recalls facts. It does not look them up.'),
          match='one sentence')
    fails('capabilities.yaml', capability_file(definition='   '))


def test_rule_1_allows_abbreviations_inside_the_sentence():
    tx.validate_file('capabilities.yaml', capability_file(
        definition='The ability to recall facts, e.g. dates, without a supplied source.'), ctx())


@pytest.mark.parametrize('field', ['inclusion_test', 'exclusion_test'])
def test_rules_2_and_3_tests_are_required_on_an_active_term(field):
    fails('capabilities.yaml', capability_file(**{field: None}), match='needs an %s' % field)


def test_rules_2_and_3_tests_must_be_operational():
    fails('capabilities.yaml', capability_file(inclusion_test='Recall of facts.'), match='tag this if')
    fails('capabilities.yaml', capability_file(exclusion_test='Retrieval tasks.'), match='do NOT tag')


def test_rule_4_before_the_freeze_is_a_warning():
    c = ctx('0.1.0')
    tx.validate_file('capabilities.yaml', capability_file(examples=[]), c)
    assert any('fewer than two' in w for w in c['warnings'])


def test_rule_4_from_the_freeze_is_an_error():
    fails('capabilities.yaml', capability_file(examples=[]), ctx('1.0.0'), match='fewer than two')
    only_positive = [{'ref': 'gpqa-diamond', 'qualifies': True, 'why': 'x'},
                     {'ref': 'mmlu-pro', 'qualifies': True, 'why': 'y'}]
    fails('capabilities.yaml', capability_file(examples=only_positive), ctx('1.0.0'), match='near-miss')


def test_without_a_context_validation_is_strict():
    with pytest.raises(ValidationError, match='fewer than two'):
        tx.FacetFile.model_validate(capability_file(examples=[]))


def test_a_gap_placeholder_is_exempt_from_the_examples_rule():
    tx.validate_file('capabilities.yaml', capability_file(examples=[], gap_placeholder=True), ctx('1.0.0'))


def test_a_proposed_term_is_definition_only():
    tx.validate_file('capabilities.yaml', capability_file(status='proposed', inclusion_test=None,
                                                          exclusion_test=None, examples=[]), ctx('1.0.0'))


def test_ids_are_slugs_and_unique():
    fails('capabilities.yaml', capability_file(id='Knowledge_Recall'))
    doc = capability_file()
    doc['terms'].append(copy.deepcopy(doc['terms'][0]))
    fails('capabilities.yaml', doc, match='term id used more than once')


def test_a_confusion_must_name_a_term_in_the_file():
    fails('capabilities.yaml', capability_file(not_to_be_confused_with=[{'term': 'no-such-term', 'distinction': 'x'}]),
          match="refers to 'no-such-term'")


# ---- domains.yaml -------------------------------------------------------------------------------

def domains():
    return real('domains.yaml')


def family(doc, fid='biology-genetics'):
    return next(t for t in doc['terms'] if t['id'] == fid)


@pytest.mark.parametrize('field', ['seed_target', 'core', 'coverage_status', 'curation_posture', 'reviewer_signoff'])
def test_a_family_needs_its_curation_fields(field):
    doc = domains()
    del family(doc)[field]
    fails('domains.yaml', doc, match='a domain family needs %s' % field)


def test_curation_field_values_are_closed():
    doc = domains()
    family(doc)['curation_posture'] = 'hand-curated'
    fails('domains.yaml', doc)


def test_a_reviewer_signoff_names_the_reviewer():
    doc = domains()
    family(doc)['reviewer_signoff'] = 'domain-expert'
    fails('domains.yaml', doc, match='needs reviewer and signed_on')
    family(doc).update(reviewer='a-reviewer', signed_on='2026-09-24')
    tx.validate_file('domains.yaml', doc, ctx())


def test_a_subdomain_is_parent_slash_leaf():
    doc = domains()
    sub = next(t for t in doc['terms'] if t['parent'] == 'biology-genetics')
    sub['id'] = 'chemistry-materials/' + sub['id'].split('/')[1]
    fails('domains.yaml', doc, match='{parent}/{leaf}')


def test_a_subdomain_cannot_carry_family_fields():
    doc = domains()
    next(t for t in doc['terms'] if t['parent'])['seed_target'] = 3
    fails('domains.yaml', doc, match='belong on the family')


def test_a_leaf_is_unique_across_the_whole_file():
    doc = domains()
    subs = [t for t in doc['terms'] if t['parent']]
    a = subs[0]
    b = copy.deepcopy(next(t for t in subs if t['parent'] != a['parent']))
    b['id'] = '%s/%s' % (b['parent'], a['id'].split('/')[1])  # same leaf, another family
    b.pop('not_to_be_confused_with', None)
    doc['terms'].append(b)
    fails('domains.yaml', doc, match='subdomain leaf used more than once')


def test_a_parent_must_be_a_family():
    doc = domains()
    next(t for t in doc['terms'] if t['parent'])['parent'] = 'no-such-family'
    fails('domains.yaml', doc)


def test_domains_is_navigational():
    doc = domains()
    doc['facet_kind'] = 'flat'
    fails('domains.yaml', doc)


# ---- field vocabularies -------------------------------------------------------------------------

def test_a_field_vocabulary_id_is_unique_within_its_field():
    doc = real('execution.yaml')
    dup = copy.deepcopy(doc['terms'][0])
    doc['terms'].append(dup)
    fails('execution.yaml', doc, match='(field, id) used more than once')


def test_an_id_shared_across_two_fields_is_reported_not_failed():
    c = ctx()
    tx.validate_file('execution.yaml', real('execution.yaml'), c)
    assert any("'wet-lab' is defined in 2 fields" in w for w in c['warnings'])


def test_a_derived_term_states_its_derivation():
    doc = real('lifecycle.yaml')
    t = next(t for t in doc['terms'] if t.get('derived'))
    del t['derivation']
    fails('lifecycle.yaml', doc, match='must state its derivation')


# ---- 04 S12's other models ----------------------------------------------------------------------

def groups_ctx():
    models, _ = tx.load_taxonomy(TAXONOMY)
    caps = [t.id for t in models['capabilities.yaml'].terms]
    doms = models['domains.yaml'].terms
    reserved = set(caps) | {t.id for t in doms if t.parent is None} | {t.id.split('/')[1] for t in doms if t.parent}
    return ctx(group_universe=caps, reserved_ids=reserved)


def test_capability_groups_are_a_strict_partition():
    tx.validate_file('capability_groups.yaml', real('capability_groups.yaml'), groups_ctx())


def test_a_capability_in_no_group_breaks_the_partition():
    doc = real('capability_groups.yaml')
    doc['groups'][0]['members'].pop()
    fails('capability_groups.yaml', doc, groups_ctx(), match='terms in no group')


def test_a_capability_in_two_groups_breaks_the_partition():
    doc = real('capability_groups.yaml')
    doc['groups'][1]['members'].append(doc['groups'][0]['members'][0])
    fails('capability_groups.yaml', doc, groups_ctx(), match='exactly one group')


def test_an_unknown_member_breaks_the_partition():
    doc = real('capability_groups.yaml')
    doc['groups'][0]['members'].append('telepathy')
    fails('capability_groups.yaml', doc, groups_ctx(), match='members that are not terms: telepathy')


def test_a_group_id_may_not_equal_a_term_leaf_or_family():
    doc = real('capability_groups.yaml')
    doc['groups'][0]['id'] = 'biology-genetics'
    fails('capability_groups.yaml', doc, groups_ctx(), match='collide')


def test_a_homograph_pairs_a_capability_with_the_same_leaf():
    doc = real('homographs.yaml')
    doc['entries'][0]['domain'] = 'domain:reasoning-general/causal-reasoning'
    fails('homographs.yaml', doc, match='must equal the subdomain leaf')
    doc = real('homographs.yaml')
    doc['entries'][0]['relationship'] = 'related'
    fails('homographs.yaml', doc)


def test_thresholds_name_both_floors_and_explain_each():
    doc = real('thresholds.yaml')
    del doc['thresholds']['comparison_floor']
    fails('thresholds.yaml', doc, match='comparison_floor')
    doc = real('thresholds.yaml')
    doc['thresholds']['frontier_floor'] = 1.5
    fails('thresholds.yaml', doc)
    doc = real('thresholds.yaml')
    doc['thresholds']['new_floor'] = 0.2
    fails('thresholds.yaml', doc, match='different keys')


def test_the_ledgers_list_each_id_once():
    doc = real('retired-ids.yaml')
    entry = {'id': 'old-term', 'retired_on': '2026-09-24', 'reason': 'merged', 'replaced_by': 'new-term'}
    doc['retired'] = [entry]
    tx.validate_file('retired-ids.yaml', doc, ctx())
    doc['retired'] = [entry, dict(entry)]
    fails('retired-ids.yaml', doc, match='retired id used more than once')
    doc = real('forbidden-identifiers.yaml')
    doc['forbidden'].append(copy.deepcopy(doc['forbidden'][0]))
    fails('forbidden-identifiers.yaml', doc, match='forbidden identifier used more than once')


def test_verification_ranks_run_without_gaps():
    doc = real('verification.yaml')
    doc['rungs'][-1]['rank'] = 9
    fails('verification.yaml', doc, match='ranks must be')


def test_a_method_subject_pair_belongs_to_one_profile():
    doc = real('comparability-profiles.yaml')
    doc['profiles'][1]['applies_to'].append(list(doc['profiles'][0]['applies_to'][0]))
    fails('comparability-profiles.yaml', doc, match='more than one profile')


def test_an_expectation_is_sized_or_states_its_fallback():
    doc = real('domain-expectations.yaml')
    unsized = next(e for e in doc['expectations'] if not e['sized'])
    del unsized['render_as']
    fails('domain-expectations.yaml', doc, match='unsized family')
