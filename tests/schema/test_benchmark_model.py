"""Tests for schema/benchmark.py (P0-S4-T03; 04-data-model.md S5, 00 S6 A5, 13 S5.4).

The verify: "the three P0-S3 entries load, the admissibility block and the execution block are
present, a benchmark with no learned_entrant_evidence is rejected, and
execution.maintainer_rerun_policy rejects a value outside {unrestricted, no-third-party-endpoints,
contact-first, unstated} while defaulting to unstated when absent".

P0-S4-T10 reconciled the model with the entries: unknown keys are now always rejected, per-field
annotations are recognised and type-checked, and the blocks that belong to another entity are
declared as deferred. Its verify: this file still passes after the additions and deletions.
"""
import glob
import os
import re
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema import benchmark as bm  # noqa: E402
from schema.benchmark import Benchmark, annotation_fields, deferred_fields, load_benchmark  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from schema.stub import curated_benchmark_files  # noqa: E402
from tools import corpus_pins  # noqa: E402

ENTRIES = curated_benchmark_files(ROOT)                   # data/benchmarks/_stubs/ holds BenchmarkStub, not Benchmark


def minimal(**changes):
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
    for path, value in changes.items():
        *parents, leaf = path.split('.')
        target = doc
        for p in parents:
            target = target.setdefault(p, {})
        if value is ...:
            target.pop(leaf, None)
        else:
            target[leaf] = value
    return doc


def rejects(doc, match=None):
    with pytest.raises(ValidationError) as e:
        Benchmark.model_validate(doc)
    if match:
        assert match in str(e.value), str(e.value)


# ---- the verify ---------------------------------------------------------------------------------

@pytest.mark.parametrize('path', ENTRIES, ids=[os.path.basename(p) for p in ENTRIES])
def test_the_three_entries_load(path):
    b = load_benchmark(path)
    # 00 S6 A5: in scope when at least one entrant is a learned system, with evidence. `mixed` is the case where
    # classical or human-led entrants compete beside learned ones.
    assert b.evaluation_target in ('learned-system', 'mixed')
    assert b.learned_entrant_evidence and all(e.source.startswith('src-') for e in b.learned_entrant_evidence)
    assert b.curation.verification_status == 'ai-drafted-unverified'


def test_the_committed_entries():
    # Every curated entry, as each change that adds entries pins them in tests/fixtures/corpus_pins/.
    pinned, _ = corpus_pins.load(ROOT)
    assert sorted(os.path.basename(p) for p in ENTRIES) == sorted(v['file'].split('/')[-1] for v in pinned.values())
    assert sorted(os.path.relpath(p, os.path.join(ROOT, 'data', 'benchmarks')).replace(os.sep, '/') for p in ENTRIES) \
        == sorted(v['file'] for v in pinned.values())


def test_the_admissibility_block_is_present():
    for f in ('learned_entrant_evidence', 'evaluation_target', 'execution_mode', 'ground_truth_source',
              'reproducible_by_third_party'):
        assert f in Benchmark.model_fields, f
    assert Benchmark.model_fields['learned_entrant_evidence'].is_required()
    assert Benchmark.model_fields['evaluation_target'].is_required()


def test_the_execution_block_is_present():
    fields = bm.Execution.model_fields
    for f in ('compute_tier', 'reproducibility_tier', 'runnable_via', 'inspect_evals_id', 'maintainer_rerun_policy',
              'est_runtime_hours', 'est_cost_usd', 'est_participant_cost_usd'):
        assert f in fields, f
    assert 'inspect_evals_available' in bm.Execution.model_computed_fields


def test_no_learned_entrant_evidence_is_rejected():
    rejects(minimal(learned_entrant_evidence=...), match='learned_entrant_evidence')
    rejects(minimal(learned_entrant_evidence=[]), match='at least 1 item')


def test_evidence_must_cite_a_source_and_a_date():
    rejects(minimal(learned_entrant_evidence=[{'system': 'M', 'observed_on': '2026-09-25'}]), match='source')
    rejects(minimal(learned_entrant_evidence=[{'system': 'M', 'source': 'a blog'}]))


@pytest.mark.parametrize('value', ['unrestricted', 'no-third-party-endpoints', 'contact-first', 'unstated'])
def test_maintainer_rerun_policy_accepts_its_four_values(value):
    b = Benchmark.model_validate(minimal(**{'execution': {'maintainer_rerun_policy': value}}))
    assert b.execution.maintainer_rerun_policy == value


@pytest.mark.parametrize('value', ['restricted', 'no third-party endpoints', 'Unrestricted', '', None])
def test_maintainer_rerun_policy_rejects_anything_else(value):
    rejects(minimal(execution={'maintainer_rerun_policy': value}), match='maintainer_rerun_policy')


def test_maintainer_rerun_policy_defaults_to_unstated():
    assert Benchmark.model_validate(minimal()).execution.maintainer_rerun_policy == 'unstated'          # no block
    assert Benchmark.model_validate(minimal(execution={'compute_tier': 'single-gpu'})).execution.maintainer_rerun_policy == 'unstated'
    for path in ENTRIES:
        assert load_benchmark(path).execution.maintainer_rerun_policy == 'unstated'


# ---- the rest of the model ----------------------------------------------------------------------

@pytest.mark.parametrize('field', ['id', 'name', 'tagline', 'domain', 'evaluation_target', 'data', 'homepage', 'curation'])
def test_stub_required_fields(field):
    rejects(minimal(**{field: ...}))


@pytest.mark.parametrize('field', ['added_by', 'added_on', 'last_verified', 'sources'])
def test_stub_required_curation_fields(field):
    rejects(minimal(**{'curation.' + field: ...}))


def test_the_facets_are_closed_vocabularies_loaded_from_taxonomy():
    rejects(minimal(capability=['telepathy']))
    rejects(minimal(evaluation_method=['vibes']))
    rejects(minimal(designed_for_subjects=['oracle']))
    rejects(minimal(**{'data.access': 'open-ish'}))
    Benchmark.model_validate(minimal(capability=['planning'], evaluation_method=['execution-tests']))


def test_the_domain_must_be_a_subdomain_leaf_not_a_family():
    rejects(minimal(domain={'primary': 'code'}))                       # families are navigational only
    rejects(minimal(domain={'primary': 'code/no-such-leaf'}))
    rejects(minimal(domain={'primary': 'code/repository-scale-se', 'secondary': ['vision']}))


def test_the_vocabulary_is_read_at_import_time():
    from schema.taxonomy import load_taxonomy
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))
    assert set(bm.Capability.__args__) == {t.id for t in models['capabilities.yaml'].terms}
    assert len(bm.DomainLeaf.__args__) == sum(t.parent is not None for t in models['domains.yaml'].terms)


@pytest.mark.parametrize('doc, what', [
    (minimal(maintenance_status='actively-maintained'), 'maintenance_status'),
    (minimal(maintenance_status=None), 'maintenance_status'),       # even null: the key itself is the error
    (minimal(**{'execution': {'inspect_evals_available': True}}), 'inspect_evals_available'),
    (minimal(**{'curation.stewardship': 'current'}), 'stewardship'),
])
def test_derived_fields_may_not_be_hand_written(doc, what):
    rejects(doc, match=what)


def test_a_derived_lifecycle_term_may_not_be_hand_set():
    rejects(minimal(lifecycle='saturated'), match='derived')
    Benchmark.model_validate(minimal(lifecycle='mature'))


# ---- ADR-0024, the checkpoint revision ---------------------------------------------------------

def test_lifecycle_may_be_null_when_the_sources_do_not_show_use():
    assert Benchmark.model_validate(minimal(lifecycle=None)).lifecycle is None
    rejects(minimal(lifecycle='unobserved'))                              # null, not a new term


@pytest.mark.parametrize('key', ['license', 'license_notes'])
def test_license_is_derived_and_may_not_be_hand_written(key):
    rejects(minimal(**{key: 'MIT'}), match='derived from data.dataset_licence and execution.code_licence')


def test_license_is_computed_from_the_data_and_code_licences():
    def lic(**kw):
        return Benchmark.model_validate(minimal(**kw)).license
    assert lic() is None
    assert lic(**{'execution.code_licence': 'MIT'}) == 'MIT'
    assert lic(**{'data.dataset_licence': 'CC-BY-4.0', 'execution.code_licence': 'CC-BY-4.0'}) == 'CC-BY-4.0'
    assert lic(**{'data.dataset_licence': 'CC-BY-4.0', 'execution.code_licence': 'MIT'}) == 'data: CC-BY-4.0; code: MIT'
    assert Benchmark.model_validate(minimal(**{'execution.code_licence': 'MIT'})).model_dump()['license'] == 'MIT'


def test_size_is_a_list_of_rows_headline_first():
    rows = [{'count': 3001, 'unit': 'sentences', 'subset': 'dev and devtest', 'source': 'src-example'},
            {'count': 1012, 'unit': 'sentences', 'subset': 'devtest', 'source': 'src-example', 'quote': 'q'}]
    b = Benchmark.model_validate(minimal(**{'data.size': rows, 'data.languages': ['English']}))
    assert [r.count for r in b.data.size] == [3001, 1012] and b.data.languages == ['English']
    assert Benchmark.model_validate(minimal(**{'data.size': None})).data.size is None
    rejects(minimal(**{'data.size': {'n_items': {'value': 1, 'source': 'src-example'}}}))     # the old shape
    rejects(minimal(**{'data.size': [{'count': 1, 'source': 'src-example'}]}), match='unit')


def test_history_records_dated_changes_under_their_yaml_keys():
    item = {'date': '2026-01-31', 'event': 'channel-closed', 'field': 'execution.submission_channel',
            'from': 'EvalAI challenge 712', 'source': 'src-example', 'quote': 'q'}
    [h] = Benchmark.model_validate(minimal(history=[item, ])).history
    assert (str(h.date_), h.from_, h.to) == ('2026-01-31', 'EvalAI challenge 712', None)
    Benchmark.model_validate(minimal(history=[{**item, 'date': '2026-01'}]))         # a month will do
    Benchmark.model_validate(minimal(history=[{k: v for k, v in item.items() if k != 'date'}]))   # undated
    rejects(minimal(history=[{**item, 'event': 'moved-somewhere'}]))
    rejects(minimal(history=[{**item, 'field': 'Execution Channel'}]))


def test_the_other_additions():
    b = Benchmark.model_validate(minimal(
        as_used=[{'protocol': 'Accuracy on the public validation split.', 'split': 'validation', 'source': 'src-example'}],
        paper={'title': 'T', 'doi': '10.1021/acscatal.0c04525', 'source': 'src-example'},
        ground_truth_source='formal-verifier', aggregation_policy='unknown',
        **{'governance.independence_assessed': False}))
    assert b.as_used[0].split == 'validation' and b.paper.doi.startswith('10.1021/')
    assert b.governance.independence_assessed is False
    Benchmark.model_validate(minimal(ground_truth_source='released-classifier'))
    rejects(minimal(paper={'title': 'T', 'doi': 'doi:10.1021/x', 'source': 'src-example'}), match='doi')


def test_the_user_simulator_condition_needs_its_model_for_a_version():
    from schema.conditions import EvalConditions
    EvalConditions.model_validate({'id': 'cond-0123456789ab', 'user_simulator': 'gpt-4o', 'user_simulator_version': '2024-08-06'})
    with pytest.raises(ValidationError, match='user_simulator_version without user_simulator'):
        EvalConditions.model_validate({'id': 'cond-0123456789ab', 'user_simulator_version': '2024-08-06'})


def test_inspect_evals_available_is_derived_from_the_id():
    assert Benchmark.model_validate(minimal(execution={'inspect_evals_id': 'swe_bench'})).execution.inspect_evals_available
    assert not Benchmark.model_validate(minimal()).execution.inspect_evals_available
    assert Benchmark.model_validate(minimal()).model_dump()['execution']['inspect_evals_available'] is False


def test_the_02_s12_handoff_fields():
    for f in ('no_legitimate_aggregate', 'secondary_axes', 'training_data_eligibility_tiers'):
        assert f in Benchmark.model_fields
    assert 'submission_limit' in bm.Data.model_fields
    assert 'est_participant_cost_usd' in bm.Execution.model_fields
    assert 'rating_pool_required' in bm.Comparability.model_fields
    rejects(minimal(secondary_axes=['vibes']))
    rejects(minimal(execution={'est_participant_cost_usd': {'min': 0, 'max': 10}}), match='basis')
    rejects(minimal(execution={'est_runtime_hours': {'min': 5, 'max': 1}}), match='above max')
    Benchmark.model_validate(minimal(**{'data.submission_limit': {'max_submissions': 5, 'period_days': 30, 'per': 'team',
                                                                   'source': 'src-example'}}))


def test_external_ids_is_a_fixed_key_set():
    rejects(minimal(external_ids={'doi': '10.1234/x'}), match='Extra inputs')
    assert Benchmark.model_validate(minimal(external_ids={'arxiv': '2310.06770'})).external_ids.arxiv == '2310.06770'
    assert Benchmark.model_validate(minimal()).external_ids.every_eval_ever is None


def test_defaults_match_04_s5():
    b = Benchmark.model_validate(minimal())
    # ADR-0024: lifecycle defaults to null, not `active`; an omitted lifecycle asserts nothing.
    assert (b.lifecycle, b.data.contamination_risk, b.data.ceiling_anchor_type) == (None, 'unknown', 'none-known')
    assert (b.execution.runnable_via, b.aggregation_policy, b.curation.confidence) == (['none'], 'official-aggregate', 'medium')
    assert (b.aliases, b.capability, b.tags, b.comparability.rating_pool_required) == ([], [], [], False)


# ---- unknown keys, annotations and deferred blocks (P0-S4-T10) ---------------------------------

def test_unknown_keys_are_rejected_including_a_misspelling():
    rejects(minimal(taglne='a typo'), match='taglne')
    rejects(minimal(**{'data.acess': 'fully-open'}), match='acess')
    rejects(minimal(summary='x'), match='summary')                       # the entries' name, now description
    rejects(minimal(**{'curation.drafted_note': 'z'}), match='drafted_note')


def test_an_annotation_is_accepted_only_beside_the_field_it_annotates():
    b = Benchmark.model_validate(minimal(lifecycle_note='x', **{'data.access_source': 'src-x', 'data.access_note': 'y'}))
    assert annotation_fields(b) == ['data.access_note', 'data.access_source', 'lifecycle_note']
    rejects(minimal(lifecyle_note='x'), match='lifecyle_note')                  # annotates no field
    rejects(minimal(**{'data.contamination_source': 'src-x'}), match='contamination_source')   # the field is contamination_risk
    rejects(minimal(**{'data.access_source': 'a blog'}), match='annotation')     # not a Source id
    rejects(minimal(**{'data.access_quote': '  '}), match='annotation')          # empty text
    Benchmark.model_validate(minimal(activity_basis={'newest_submission': '2025-12-19', 'source': 'src-x'}))
    rejects(minimal(activity_basis={'newest': '2025-12-19'}), match='annotation')


def test_every_entry_loads_with_no_unknown_key():
    for path in ENTRIES:
        load_benchmark(path)                                              # an unknown key would raise


def test_every_entry_deferred_key_is_declared_by_its_block():
    for path in ENTRIES:
        for d in deferred_fields(load_benchmark(path)):
            if d.startswith('curation.sources[].'):
                assert d.split('.')[-1] in bm.InlineSource.DEFERRED, d
            elif d.startswith('scale.'):
                assert d.startswith('scale.live_'), d
            else:
                assert d in Benchmark.DEFERRED, d


def test_the_reconciled_shapes_still_check_their_values():
    ok = minimal(governance={'submission_process': ['self-reported', 'maintainer-verified'],
                             'independence_flags': [{'flag': 'funded-by-evaluated-party', 'source': 'src-x'}]},
                 **{'data.contamination_evidence': [{'source': 'src-x', 'stance': 'supports', 'quote': 'q'}]})
    Benchmark.model_validate(ok)
    rejects(minimal(governance={'submission_process': ['self-reported', 'honour-system']}))
    rejects(minimal(governance={'independence_flags': [{'flag': 'no-such-flag'}]}))
    rejects(minimal(governance={'independence_flags': [{'flag': 'funded-by-evaluated-party', 'reviewer_check': 'x'}]}))
    rejects(minimal(**{'data.contamination_evidence': [{'source': 'src-x', 'stance': 'maybe'}]}))
    rejects(minimal(**{'curation.sources': [{'url': 'https://example.org'}]}), match='id')
    rejects(minimal(activity='assessment-in-progress'), match='activity')      # not in taxonomy/lifecycle.yaml
    rejects(minimal(execution={'reproducibility_blockers': ['blindness']}))
    rejects(minimal(execution={'harness_availability': 'maybe'}))


def test_a_term_is_assigned_or_rejected_never_both():
    Benchmark.model_validate(minimal(capability=['planning'],
                                     capability_considered_and_rejected=[{'term': 'tool-use', 'reason': 'No tools.'}]))
    rejects(minimal(capability=['planning'], capability_considered_and_rejected=[{'term': 'planning', 'reason': 'r'}]),
            match='both assigned')
    rejects(minimal(capability_considered_and_rejected=[{'term': 'telepathy', 'reason': 'r'}]), match='not a capability')
    rejects(minimal(domain_considered_and_rejected=[{'term': 'code/repository-scale-se', 'reason': 'r'}]),
            match='both assigned')
    rejects(minimal(designed_for_subjects_considered_and_rejected=[{'term': 'oracle', 'reason': 'r'}]))


def test_capability_basis_justifies_only_assigned_terms():
    Benchmark.model_validate(minimal(capability=['planning'], capability_basis={'planning': 'The task is a plan.'}))
    Benchmark.model_validate(minimal(capability=['planning'],
                                     capability_basis={'planning': {'reason': 'r', 'source': 'src-x', 'quote': 'q'}}))
    rejects(minimal(capability=['planning'], capability_basis={'tool-use': 'r'}), match='not assigned')


def test_the_new_blocks_are_closed():
    rejects(minimal(paper={'title': 'T', 'source': 'src-x', 'doi': '10.1/x'}), match='doi')
    rejects(minimal(scale={'at_publication': {'source': 'src-x', 'policies': -1}}), match='non-negative')
    rejects(minimal(scale={'at_publication': {'source': 'src-x', 'policies': 'seven'}}), match='non-negative')
    Benchmark.model_validate(minimal(scale={'at_publication': {'source': 'src-x', 'policies': 7},
                                            'live_2026_09_23': {'anything': 'deferred'}}))
    rejects(minimal(scale={'live_today': {}}), match='live_today')
    rejects(minimal(entrant_classes=[{'class': 'server'}]), match='ranked_separately')
    rejects(minimal(planned_end='December 2026'))
    rejects(minimal(**{'external_ids.arxiv': 'arXiv:2310.06770'}))


def test_the_entries_carry_the_reconciled_fields():
    by = {os.path.basename(p): load_benchmark(p) for p in ENTRIES}
    swe, casp, robo = by['swe-bench.yaml'], by['casp.yaml'], by['roboarena.yaml']
    assert swe.external_ids.arxiv == '2310.06770' and swe.data.size[0].count == 2294
    assert swe.execution.code_licence == 'MIT' and swe.lineage.role == 'root' and len(swe.lineage.variants) == 4
    assert casp.activity == 'unknown' and 'assessment-in-progress' in casp.tags
    assert 'Critical Assessment of Techniques for Protein Structure Prediction' in casp.aliases
    assert [c.class_ for c in casp.entrant_classes] == ['server', 'expert']
    assert robo.task.exists is False
    assert robo.execution.compute_tier_by_role == {'submitter': None, 'evaluator': 'physical-hardware'}
    for b in by.values():                         # ADR-0026: the reviewer checks are records, not a notes paragraph
        assert b.description and b.curation.review_checks and b.curation.notes is None


def test_croissant_terms_name_real_fields():
    for f in bm.CROISSANT_TERMS:                 # `license` is computed since ADR-0024, and serialises like a field
        assert f in Benchmark.model_fields or f in Benchmark.model_computed_fields, f
    # Where schema.org's term is the same word, the field uses it.
    for f in ('name', 'description', 'license'):
        assert bm.CROISSANT_TERMS[f] == 'sc:' + f


def test_the_entries_evidence_quotes_are_in_their_sources():
    from schema.source import quote_found
    extracts = {read_yaml(p)['id']: read_yaml(p).get('quote_extract')
                for p in glob.glob(os.path.join(ROOT, 'data', 'sources', '**', '*.yaml'), recursive=True)}
    for path in ENTRIES:
        for ev in load_benchmark(path).learned_entrant_evidence:
            assert ev.quote and quote_found(ev.quote, extracts[ev.source]), (path, ev.source)


# ---- the schema and the field-need list agree (P0-S4-T10's done-when) -----------------------------

FIELD_NEEDS = os.path.join(ROOT, 'docs', 'schema-field-needs.md')


def _table(text, heading):
    body = text.split(heading, 1)[1]
    body = body.split('\n## ', 1)[0]
    return [[c.strip() for c in line.strip().strip('|').split('|')]
            for line in body.splitlines() if line.startswith('| `')]


def field_need_resolutions():
    text = open(FIELD_NEEDS, encoding='utf-8').read()
    groups = [r[0].strip('`') for r in _table(text, '## By field group')]
    rows = {r[0].strip('`'): (r[1], re.findall(r'`([A-Z][A-Za-z]+(?:\.[a-z_]+)*)`', r[2])) for r in
            _table(text, '## Resolution (P0-S4-T10)')}
    return text, groups, rows


def test_every_field_group_has_a_resolution():
    _, groups, rows = field_need_resolutions()
    assert groups and sorted(groups) == sorted(rows)


def test_every_needed_row_resolves_to_a_schema_field():
    from schema.paths import resolve
    _, _, rows = field_need_resolutions()
    for group, (status, paths) in rows.items():
        assert status in ('needed', 'deferred', 'resolved'), (group, status)
        if status == 'needed':
            assert paths, group
        for p in paths:
            if '.' in p:
                resolve(p)                                  # raises Unresolved if the field is not there
            else:
                from schema.paths import ENTITIES
                assert p in ENTITIES, (group, p)


def test_no_unused_row_survives():
    text, _, _ = field_need_resolutions()
    assert not re.search(r'^\|[^\n]*\| (\*\*)?unused(\*\*)? \|', text, flags=re.M)
