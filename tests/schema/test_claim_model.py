"""Tests for schema/system.py and schema/claim.py (P0-S4-T05; 04-data-model.md S7, S9, S15).

The verify: "the three C5 additions this task owns round-trip (artifact_url with
artifact_archived, provenance_snapshot, and the System training-compute fields ...), a pairwise
claim requires an opponent, and a claim with resolution_status pending is accepted with a null
value". Round-trip means: validate, dump to JSON-compatible data, write it as YAML the way a record
is stored, read it back, validate again, and get an equal model.
"""
import io
import os
import sys

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.claim import Ingestion, ProvenanceSnapshot, ResultClaim, snapshot_sha256  # noqa: E402
from schema.system import System  # noqa: E402

EPOCH_ROW = {'Model version': 'claude-opus-5-20260501_high', 'Best score (across scorers)': '0.742',
             'Release date': '2026-05-01', 'Source': 'https://epoch.ai/benchmarks'}


def yaml_round_trip(model):
    """model -> JSON-mode dict -> YAML text -> dict -> model, as a committed record would travel."""
    data = model.model_dump(mode='json', exclude_none=False)
    buf = io.StringIO()
    YAML(typ='safe', pure=True).dump(data, buf)
    back = YAML(typ='safe').load(buf.getvalue())
    return type(model).model_validate(back)


def system(**changes):
    doc = {'id': 'claude-opus-5', 'name': 'Claude Opus 5', 'organization': 'org-anthropic',
           'system_type': 'reasoning-model', 'availability': 'generally-available',
           'sources': ['src-anthropic-opus5-announcement']}
    doc.update(changes)
    return {k: v for k, v in doc.items() if v is not ...}


def claim(**changes):
    doc = {'id': 'claim-3c8e10ba55f7', 'system': 'claude-opus-5@2026-05', 'benchmark': 'swe-bench@verified',
           'metric': 'resolve-rate', 'claim_type': 'absolute', 'value': 0.742, 'date_reported': '2026-05-01',
           'reported_by': 'org-anthropic', 'verification': 'self-reported', 'source': 'src-anthropic-opus5-announcement'}
    doc.update(changes)
    return {k: v for k, v in doc.items() if v is not ...}


def snapshot(raw=EPOCH_ROW, **changes):
    doc = {'source_record_id': 'swe_bench_verified.csv#model=claude-opus-5-20260501_high&metric=best-score',
           'retrieved_at': '2026-09-16T23:14:00Z', 'content_sha256': snapshot_sha256(raw), 'raw': raw}
    doc.update(changes)
    return doc


def ingestion(**changes):
    doc = {'batch': 'ingest-epoch-2026-09-16', 'source_adapter': 'epoch-benchmarks', 'adapter_version': '0.3.1',
           'source_record_id': 'swe_bench_verified.csv#model=claude-opus-5-20260501_high&metric=best-score',
           'last_seen_upstream': '2026-09-16', 'source_url': 'https://epoch.ai/data/benchmark_data.zip',
           'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
           'source_attribution': "Epoch AI, 'Capabilities & Benchmarking'.", 'ingested_at': '2026-09-16T23:14:00Z',
           'extraction_confidence': 0.9,
           'field_provenance': {'value': 'source', 'eval_conditions.reasoning_effort': 'derived'}}
    doc.update(changes)
    return doc


# ---- the verify: the three C5 additions round-trip ----------------------------------------------

def test_artifact_url_and_artifact_archived_round_trip():
    c = ResultClaim.model_validate(claim(artifact_url='https://epoch-logs.s3.amazonaws.com/x-public/run.eval',
                                         artifact_archived=True))
    back = yaml_round_trip(c)
    assert back == c
    assert (back.artifact_url, back.artifact_archived) == ('https://epoch-logs.s3.amazonaws.com/x-public/run.eval', True)


def test_provenance_snapshot_round_trips_with_its_hash():
    c = ResultClaim.model_validate(claim(provenance_snapshot=snapshot()))
    back = yaml_round_trip(c)
    assert back == c
    assert back.provenance_snapshot.raw == EPOCH_ROW                          # the row's own mapping, verbatim
    assert back.provenance_snapshot.content_sha256 == snapshot_sha256(EPOCH_ROW)


@pytest.mark.parametrize('compute', [
    {'training_compute_disclosed': True, 'training_compute_flop': 4.752e24, 'training_compute_estimated': False},
    {'training_compute_flop': 4.752e24, 'training_compute_estimated': True,
     'training_compute_notes': '6 FLOP / parameter / token * 22*10^9 active parameters * 36000000000000 tokens = 4.752e+24 FLOP'},
    {'training_compute_flop': 1.58e25, 'training_compute_estimated': True,
     'training_compute_notes': 'Training compute imputed to be 1.58e25 FLOP from benchmark scores'},
])
def test_the_system_training_compute_fields_round_trip(compute):
    s = System.model_validate(system(**compute))
    back = yaml_round_trip(s)
    assert back == s
    for k, v in compute.items():
        assert getattr(back, k) == v, k


# ---- the verify: pairwise and pending -----------------------------------------------------------

def test_a_pairwise_claim_requires_an_opponent():
    with pytest.raises(ValidationError, match='requires an opponent'):
        ResultClaim.model_validate(claim(claim_type='pairwise', value=0.61))
    ok = ResultClaim.model_validate(claim(claim_type='pairwise', value=0.61, opponent='gpt-6@2026-06'))
    assert ok.opponent == 'gpt-6@2026-06'


def test_a_pending_claim_is_accepted_with_a_null_value():
    c = ResultClaim.model_validate(claim(value=None, resolution_status='pending', benchmark='forecastbench'))
    assert (c.value, c.resolution_status) == (None, 'pending')
    assert yaml_round_trip(c) == c


@pytest.mark.parametrize('status', ['partial', 'resolved'])
def test_a_resolved_or_partial_claim_needs_its_value(status):
    with pytest.raises(ValidationError, match='needs a value'):
        ResultClaim.model_validate(claim(value=None, resolution_status=status))


# ---- claim shapes -------------------------------------------------------------------------------

def test_only_a_pairwise_claim_names_an_opponent():
    with pytest.raises(ValidationError, match='pairwise claims only'):
        ResultClaim.model_validate(claim(opponent='gpt-6'))


def test_a_system_is_not_its_own_opponent():
    with pytest.raises(ValidationError, match='own opponent'):
        ResultClaim.model_validate(claim(claim_type='pairwise', value=0.5, opponent='claude-opus-5@2026-01'))


def test_a_rating_claim_names_its_pool_and_only_it_does():
    with pytest.raises(ValidationError, match='rating_pool'):
        ResultClaim.model_validate(claim(claim_type='rating', value=1735, benchmark='roboarena', metric='bt-rating'))
    ResultClaim.model_validate(claim(claim_type='rating', value=1735, benchmark='roboarena', metric='bt-rating',
                                     rating_pool='pool-roboarena-2026-09-23'))
    with pytest.raises(ValidationError, match='rating claims only'):
        ResultClaim.model_validate(claim(rating_pool='pool-roboarena-2026-09-23'))


def test_ordinal_and_qualitative_claims():
    ResultClaim.model_validate(claim(claim_type='ordinal', value=None, value_text='rank 1 of 56 groups'))
    ResultClaim.model_validate(claim(claim_type='qualitative', value=None, value_text='passed the audit'))
    with pytest.raises(ValidationError, match='needs value_text'):
        ResultClaim.model_validate(claim(claim_type='qualitative', value=None))
    with pytest.raises(ValidationError, match='no numeric value'):
        ResultClaim.model_validate(claim(claim_type='qualitative', value=1.0, value_text='x'))


def test_the_interop_and_c5_fields_exist():
    fields = ResultClaim.model_fields
    for f in ('serving_provider', 'claim_type', 'resolution_status', 'result_group', 'artifact_url',
              'artifact_archived', 'provenance_snapshot', 'ingestion', 'external_ids'):
        assert f in fields, f
    c = ResultClaim.model_validate(claim(external_ids={'eee_result_id': 'eee-123'}, serving_provider='org-fireworks',
                                         result_group='agentdojo-2026-05'))
    assert yaml_round_trip(c).external_ids.eee_result_id == 'eee-123'


def test_verification_is_a_rung_and_disputed_is_not():
    with pytest.raises(ValidationError):
        ResultClaim.model_validate(claim(verification='disputed'))
    c = ResultClaim.model_validate(claim(verification='held-out-server', disputed_by=['src-a-rebuttal']))
    assert c.disputed_by == ['src-a-rebuttal']


def test_an_archived_flag_needs_an_artifact():
    with pytest.raises(ValidationError, match='artifact_archived without'):
        ResultClaim.model_validate(claim(artifact_archived=False))


def test_uncertainty_shapes():
    ResultClaim.model_validate(claim(uncertainty={'type': 'stderr', 'value': 0.012, 'n_runs': 5}))
    ResultClaim.model_validate(claim(uncertainty={'type': 'ci95', 'value': [0.70, 0.78]}))
    for bad in ({'type': 'none', 'value': 0.1}, {'type': 'ci95', 'value': [0.8, 0.7]}, {'type': 'ci95', 'value': 0.1}):
        with pytest.raises(ValidationError):
            ResultClaim.model_validate(claim(uncertainty=bad))


def test_ids_and_refs_are_checked():
    for field, bad in (('id', 'claim-xyz'), ('source', 'https://example.org'), ('eval_conditions', 'cond-1'),
                       ('reported_by', 'anthropic'), ('benchmark', 'SWE Bench')):
        with pytest.raises(ValidationError):
            ResultClaim.model_validate(claim(**{field: bad}))


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError, match='Extra inputs'):
        ResultClaim.model_validate(claim(scaffold='SWE-agent'))
    with pytest.raises(ValidationError, match='Extra inputs'):
        System.model_validate(system(params=7e9))


# ---- the snapshot and the ingestion block are different things ----------------------------------

def test_a_tampered_snapshot_fails_its_hash():
    raw = dict(EPOCH_ROW, **{'Best score (across scorers)': '0.842'})
    with pytest.raises(ValidationError, match='not the sha256 of `raw`'):
        ProvenanceSnapshot.model_validate(snapshot(raw=raw, content_sha256=snapshot_sha256(EPOCH_ROW)))


def test_the_snapshot_hash_ignores_key_order():
    assert snapshot_sha256({'a': 1, 'b': 2}) == snapshot_sha256({'b': 2, 'a': 1})


def test_ingestion_and_snapshot_are_distinct_and_both_round_trip():
    c = ResultClaim.model_validate(claim(provenance_snapshot=snapshot(), ingestion=ingestion()))
    back = yaml_round_trip(c)
    assert back == c
    # field_provenance maps OUR fields; the snapshot holds THEIR row. Neither is derivable from the other.
    assert set(back.ingestion.field_provenance) == {'value', 'eval_conditions.reasoning_effort'}
    assert set(back.provenance_snapshot.raw) == set(EPOCH_ROW)
    assert 'field_provenance' not in ProvenanceSnapshot.model_fields
    assert 'raw' not in Ingestion.model_fields


def test_a_row_ordinal_is_not_a_record_id():
    with pytest.raises(ValidationError, match='row ordinal'):
        Ingestion.model_validate(ingestion(source_record_id='swe_bench_verified.csv#row=17'))
    Ingestion.model_validate(ingestion(source_record_id=None))           # a full-replace source


# P5-S2-T08 (07 S1.4, 04 S9): the rule was the one spelling `#row=N`; every other ordinal got through.
@pytest.mark.parametrize('sid, match', [
    ('f.csv#line=17', 'row ordinal'),
    ('f.csv#index=3', 'row ordinal'),
    ('f.csv#Row=17', 'row ordinal'),
    ('f.csv#row_number=17', 'row ordinal'),
    ('f.csv#model=a&row=17', 'row ordinal'),                       # an ordinal among real discriminators
    ('f.csv#17', 'key=value'),                                      # a bare position
    ('f.csv#', 'key=value'),
    ('f.csv#model', 'key=value'),
    ('f.csv#model=a b&metric=c', 'whitespace'),                     # not URL-encoded
])
def test_every_spelling_of_a_position_is_refused(sid, match):
    with pytest.raises(ValidationError, match=match):
        Ingestion.model_validate(ingestion(source_record_id=sid))
    with pytest.raises(ValidationError, match=match):             # the snapshot names the same record
        ProvenanceSnapshot.model_validate({**snapshot(), 'source_record_id': sid})


@pytest.mark.parametrize('sid', [
    'swe_bench_verified.csv#model_version=glm-5.2_max&score_column=mean_score',   # 07 S1.4's example
    'swe_bench_verified.csv#model=claude-opus-5&metric=resolve-rate',             # 04 S9's example
    'f.csv#model=a%20b&metric=c',                                                  # URL-encoded
    'gpqa-diamond:example-model',                                                  # an upstream key of its own
    'f.csv#model_id=17',                                                           # a numeric VALUE is fine
])
def test_the_source_s_own_discriminators_are_accepted(sid):
    Ingestion.model_validate(ingestion(source_record_id=sid))
    ProvenanceSnapshot.model_validate({**snapshot(), 'source_record_id': sid})


def test_ingestion_rules():
    with pytest.raises(ValidationError, match='reviewed_by'):
        Ingestion.model_validate(ingestion(review_state='human-reviewed'))
    with pytest.raises(ValidationError):
        Ingestion.model_validate(ingestion(field_provenance={'value': 'guessed'}))
    with pytest.raises(ValidationError):
        Ingestion.model_validate(ingestion(extraction_confidence=1.2))


# ---- System rules -------------------------------------------------------------------------------

def test_compute_must_say_whether_it_is_estimated():
    with pytest.raises(ValidationError, match='whether it is estimated'):
        System.model_validate(system(training_compute_flop=1e25))


def test_an_estimate_keeps_its_notes():
    with pytest.raises(ValidationError, match='verbatim notes'):
        System.model_validate(system(training_compute_flop=1e25, training_compute_estimated=True))


def test_a_figure_neither_disclosed_nor_estimated_is_rejected():
    with pytest.raises(ValidationError, match='neither disclosed nor estimated'):
        System.model_validate(system(training_compute_flop=1e25, training_compute_estimated=False))


def test_compute_imputed_from_scores_is_flagged_for_exclusion():
    imputed = System.model_validate(system(training_compute_flop=1.58e25, training_compute_estimated=True,
                                           training_compute_notes='Training compute imputed to be 1.58e25 FLOP from benchmark scores'))
    arithmetic = System.model_validate(system(training_compute_flop=4.752e24, training_compute_estimated=True,
                                              training_compute_notes='6 FLOP / parameter / token * 22e9 * 36e12 tokens'))
    assert not imputed.compute_is_independent_of_scores()
    assert arithmetic.compute_is_independent_of_scores()


def test_an_undisclosed_parameter_count_is_null():
    with pytest.raises(ValidationError, match='parameters_disclosed'):
        System.model_validate(system(parameter_count=70_000_000_000))
    System.model_validate(system(parameter_count=70_000_000_000, parameters_disclosed=True))


@pytest.mark.parametrize('availability', ['deprecated', 'retired'])
def test_retired_on_is_required_exactly_when_retired(availability):
    with pytest.raises(ValidationError, match='needs retired_on'):
        System.model_validate(system(availability=availability))
    System.model_validate(system(availability=availability, retired_on='2026-08-05'))


def test_retired_on_on_a_live_system_is_rejected():
    with pytest.raises(ValidationError, match='retired_on on a system'):
        System.model_validate(system(retired_on='2026-08-05'))


def test_an_agent_scaffold_names_its_base():
    with pytest.raises(ValidationError, match='built on'):
        System.model_validate(system(id='swe-agent', system_type='agent-scaffold'))
    System.model_validate(system(id='swe-agent', system_type='agent-scaffold', built_on=['claude-3-7-sonnet']))


def test_human_teams_are_systems():
    System.model_validate(system(id='kozakovvajda', name='KozakovVajda', organization=None, system_type='human-expert',
                                 availability='never-released', sources=['src-casp16-complex']))


def test_system_versions_round_trip():
    s = System.model_validate(system(versions=[{'version': '2026-05', 'released': '2026-05-01',
                                                'api_identifier': 'claude-opus-5-20260501'}]))
    assert yaml_round_trip(s) == s
