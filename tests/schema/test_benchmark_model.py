"""Tests for schema/benchmark.py (P0-S4-T03; 04-data-model.md S5, 00 S6 A5, 13 S5.4).

The verify: "the three P0-S3 entries load, the admissibility block and the execution block are
present, a benchmark with no learned_entrant_evidence is rejected, and
execution.maintainer_rerun_policy rejects a value outside {unrestricted, no-third-party-endpoints,
contact-first, unstated} while defaulting to unstated when absent".
"""
import glob
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema import benchmark as bm  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark, unmodelled_fields  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

ENTRIES = sorted(glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True))


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


def rejects(doc, match=None, **ctx):
    with pytest.raises(ValidationError) as e:
        Benchmark.model_validate(doc, context=ctx or None)
    if match:
        assert match in str(e.value), str(e.value)


# ---- the verify ---------------------------------------------------------------------------------

@pytest.mark.parametrize('path', ENTRIES, ids=[os.path.basename(p) for p in ENTRIES])
def test_the_three_entries_load(path):
    b = load_benchmark(path)
    assert b.evaluation_target == 'learned-system'
    assert b.learned_entrant_evidence and all(e.source.startswith('src-') for e in b.learned_entrant_evidence)
    assert b.curation.verification_status == 'ai-drafted-unverified'


def test_there_are_three_entries():
    assert sorted(os.path.basename(p) for p in ENTRIES) == ['casp.yaml', 'roboarena.yaml', 'swe-bench.yaml']


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
    assert len(bm.DomainLeaf.__args__) == 204


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
    rejects(minimal(external_ids={'arxiv': '2310.06770'}), match='Extra inputs')
    assert Benchmark.model_validate(minimal()).external_ids.every_eval_ever is None


def test_defaults_match_04_s5():
    b = Benchmark.model_validate(minimal())
    assert (b.lifecycle, b.data.contamination_risk, b.data.ceiling_anchor_type) == ('active', 'unknown', 'none-known')
    assert (b.execution.runnable_via, b.aggregation_policy, b.curation.confidence) == (['none'], 'official-aggregate', 'medium')
    assert (b.aliases, b.capability, b.tags, b.comparability.rating_pool_required) == ([], [], [], False)


# ---- unknown keys, pending P0-S4-T10 ------------------------------------------------------------

def test_unknown_keys_are_accepted_and_listed():
    b = Benchmark.model_validate(minimal(summary='x', **{'data.access_note': 'y', 'curation.drafted_note': 'z'}))
    assert unmodelled_fields(b) == ['curation.drafted_note', 'data.access_note', 'summary']


def test_strict_mode_rejects_unknown_keys_including_a_misspelling():
    rejects(minimal(taglne='a typo'), match='taglne', strict=True)
    rejects(minimal(**{'data.acess': 'fully-open'}), match='acess', strict=True)
    Benchmark.model_validate(minimal(), context={'strict': True})


def test_every_entry_lists_its_unmodelled_fields():
    for path in ENTRIES:
        unknown = unmodelled_fields(load_benchmark(path))
        assert unknown and '_schema_findings' in unknown          # the work T10 inherits
        with pytest.raises(ValidationError):
            load_benchmark(path, strict=True)


def test_the_entry_shapes_accepted_pending_t10_still_check_their_values():
    ok = minimal(governance={'submission_process': ['self-reported', 'maintainer-verified'],
                             'independence_flags': [{'flag': 'funded-by-evaluated-party', 'source': 'src-x'}]},
                 **{'data.contamination_evidence': [{'source': 'src-x', 'stance': 'supports', 'quote': 'q'}]})
    Benchmark.model_validate(ok)
    rejects(minimal(governance={'submission_process': ['self-reported', 'honour-system']}))
    rejects(minimal(governance={'independence_flags': [{'flag': 'no-such-flag'}]}))
    rejects(minimal(**{'data.contamination_evidence': [{'source': 'src-x', 'stance': 'maybe'}]}))
    rejects(minimal(**{'curation.sources': [{'url': 'https://example.org'}]}), match='id')


def test_croissant_terms_name_real_fields():
    for f in bm.CROISSANT_TERMS:
        assert f in Benchmark.model_fields, f
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
