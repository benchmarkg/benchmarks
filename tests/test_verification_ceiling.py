"""The verification-ceiling, provenance and derived-field gates (P3-S4-T02; 07 S8, 04 S9).

The done-when: "A future adapter cannot promote itself above rung 3, a record with a row-ordinal
source_record_id is rejected, and no draft can carry a derived field." Each is held below against
ingest/gates/record.py, with the rest of each gate's rule.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import gates as G  # noqa: E402
from ingest.verification import Transcript  # noqa: E402

LOG = 'https://epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/abc.eval'
REACHED = Transcript(LOG, 'public', 'HTTP 200', '2026-10-06T00:00:00Z')


def ingestion(**kw):
    block = {
        'batch': 'ingest-epoch-2026-w41', 'source_adapter': 'epoch', 'adapter_version': '1.4.0',
        'source_record_id': 'swe_bench_verified.csv#model_version=glm-5.2_max&score_column=mean_score',
        'last_seen_upstream': '2026-10-06', 'source_url': 'https://epoch.ai/benchmarks',
        'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
        'source_attribution': "Epoch AI, 'Capabilities & Benchmarking'.", 'ingested_at': '2026-10-06T04:17:11Z',
        'extraction_confidence': 1.0, 'review_state': 'machine-ingested', 'field_provenance': {},
    }
    block.update(kw)
    return block


def draft(**kw):
    d = {'verification': 'maintainer-verified', 'artifact_url': None, 'value': 0.787, 'ingestion': ingestion()}
    d.update(kw)
    return d


# ---- the done-when ----------------------------------------------------------------------------------------

@pytest.mark.parametrize('rung', ['held-out-server', 'prospective-experiment', 'third-party-audited',
                                  'sandboxed-rerun'])
def test_an_adapter_cannot_promote_a_record_above_rung_3(rung):
    with pytest.raises(G.GateError, match='verification-ceiling'):
        G.verification_ceiling(draft(verification=rung, artifact_url=LOG), REACHED)


def test_not_even_when_the_taxonomy_is_edited_to_let_a_machine_assign_rung_4(tmp_path):
    from ruamel.yaml import YAML
    yaml = YAML(typ='safe', pure=True)
    with open(os.path.join(ROOT, 'taxonomy', 'verification.yaml'), encoding='utf-8') as f:
        doc = yaml.load(f)
    rung4 = next(r for r in doc['rungs'] if r['id'] == 'held-out-server')
    assert rung4['rank'] == 4 and rung4['machine_assignable'] is False
    rung4['machine_assignable'] = True                       # someone loosens the taxonomy
    (tmp_path / 'taxonomy').mkdir()
    with open(tmp_path / 'taxonomy' / 'verification.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(doc, f)
    with pytest.raises(G.GateError, match='rank 4; no ingested record goes above rank 3'):
        G.verification_ceiling(draft(verification='held-out-server', artifact_url=LOG), REACHED, str(tmp_path))


@pytest.mark.parametrize('ordinal', ['swe_bench_verified.csv#row=17', 'mmlu_external.csv#model=x&line=4',
                                     'gpqa.csv#index=3'])
def test_a_row_ordinal_source_record_id_is_rejected(ordinal):
    with pytest.raises(G.GateError, match='provenance.*row ordinal'):
        G.provenance(draft(ingestion=ingestion(source_record_id=ordinal)))


@pytest.mark.parametrize('where', [
    {'comparability_key': 'k'},
    {'condition_completeness': 0.6},
    {'headroom': 0.4},
    {'eval_conditions': {'condition_completeness': 0.6}},        # at any depth
    {'metric': {'higher_is_better': True}},
    {'extra': [{'maintenance_status': 'active'}]},
])
def test_no_draft_can_carry_a_derived_field(where):
    with pytest.raises(G.GateError, match='derived-field'):
        G.derived_field_guard(draft(**where))


# ---- the rest of each gate --------------------------------------------------------------------------------

def test_rungs_1_and_2_need_no_transcript():
    G.verification_ceiling(draft(verification='self-reported'))
    G.verification_ceiling(draft(verification='maintainer-verified'))


def test_rung_3_needs_the_transcript_reached_at_its_own_artifact_url():
    G.verification_ceiling(draft(verification='independent-reproduction', artifact_url=LOG), REACHED)
    for t in (None, Transcript(LOG, 'unreachable', 'HTTP 403'), Transcript(LOG, 'private')):
        with pytest.raises(G.GateError, match='reachable artifact_url'):
            G.verification_ceiling(draft(verification='independent-reproduction', artifact_url=LOG), t)
    with pytest.raises(G.GateError, match='is not the artifact_url'):
        G.verification_ceiling(draft(verification='independent-reproduction', artifact_url=LOG + '2'), REACHED)


def test_an_unknown_or_missing_rung_is_refused():
    for d in (draft(verification='peer-reviewed'), {'value': 1.0}):
        with pytest.raises(G.GateError, match='not a rung'):
            G.verification_ceiling(d)


def test_a_complete_ingestion_block_passes():
    G.provenance(draft())


@pytest.mark.parametrize('key', G.PROVENANCE_KEYS)
def test_every_provenance_key_must_be_present(key):
    block = ingestion()
    block.pop(key)
    with pytest.raises(G.GateError, match='lacks %s' % key):
        G.provenance(draft(ingestion=block))


def test_no_ingestion_block_at_all_is_refused():
    with pytest.raises(G.GateError, match='no ingestion block'):
        G.provenance({'value': 1.0})


def test_a_null_source_record_id_is_only_for_a_full_replace_source():
    d = draft(ingestion=ingestion(source_record_id=None))
    with pytest.raises(G.GateError, match='full-replace'):
        G.provenance(d)
    G.provenance(d, full_replace=True)


def test_a_malformed_block_is_refused_with_the_schema_reason():
    with pytest.raises(G.GateError, match='licence_class'):
        G.provenance(draft(ingestion=ingestion(licence_class='cc-by')))


def test_a_clean_draft_has_no_derived_fields():
    assert G.derived_fields(draft()) == []
    G.derived_field_guard(draft())
