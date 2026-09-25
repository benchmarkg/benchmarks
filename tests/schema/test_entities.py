"""Tests for the remaining entity models (P0-S4-T07; 04-data-model.md S2, S6, S7, S9, S10; 05 S8).

The verify: "all nine models instantiate from fixtures, an unbounded metric refuses a headroom
computation, and a RatingPool without a snapshot date is rejected". The done-when: every entity type
in 04 S2 has a model that instantiates from a fixture.
"""
import copy
import glob
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.baseline import CEILING_ANCHOR, FLOOR_KINDS, Baseline, BaselineFile  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.dispute import Dispute, claim_is_disputed  # noqa: E402
from schema.entities import (Alias, AliasFile, BenchmarkVersion, IngestBatch, Leaderboard, Organization,  # noqa: E402
                             RatingPool, Subset)
from schema.metric import HeadroomNotComputable, Metric  # noqa: E402
from schema.source import Source  # noqa: E402
from schema.system import System, SystemVersion  # noqa: E402
from schema.taxonomy import load_taxonomy, read_yaml  # noqa: E402

FX = os.path.join(os.path.dirname(__file__), 'fixtures', 'entities')


def fx(name):
    return read_yaml(os.path.join(FX, name))


def rejects(model, doc, match=None):
    with pytest.raises(ValidationError) as e:
        model.model_validate(doc)
    if match:
        assert match in str(e.value), str(e.value)


def changed(doc, **changes):
    doc = copy.deepcopy(doc)
    for k, v in changes.items():
        if v is ...:
            doc.pop(k, None)
        else:
            doc[k] = v
    return doc


# ---- the verify ---------------------------------------------------------------------------------

NINE = [
    (Metric, 'metric-gdt-ts.yaml'),
    (BaselineFile, 'baselines-swe-bench.yaml'),
    (BenchmarkVersion, 'benchmark-version-swe-bench-verified.yaml'),
    (Subset, 'subset-mmlu-college-chemistry.yaml'),
    (Leaderboard, 'leaderboard-swebench-official.yaml'),
    (Organization, 'organization-princeton-nlp.yaml'),
    (RatingPool, 'rating-pool-kaggle-chess.yaml'),
    (IngestBatch, 'ingest-batch-epoch.yaml'),
    (AliasFile, 'aliases-systems.yaml'),
]


@pytest.mark.parametrize('model, name', NINE, ids=[n for _, n in NINE])
def test_the_nine_models_instantiate_from_fixtures(model, name):
    obj = model.model_validate(fx(name))
    assert obj.model_dump()


def test_the_dispute_model_instantiates_from_its_fixture():
    d = Dispute.model_validate(fx('dispute-swe-bench-verified.yaml'))
    assert d.is_standing and d.evidence and d.claim_sources


def test_an_unbounded_metric_refuses_a_headroom_computation():
    elo = Metric.model_validate(fx('metric-arena-elo.yaml'))
    with pytest.raises(HeadroomNotComputable) as e:
        elo.headroom_consumed(sota=1500, baseline=1000, ceiling=2000)
    assert e.value.reason == 'unbounded-metric'


def test_an_unbounded_metric_cannot_claim_headroom_or_a_maximum():
    doc = fx('metric-arena-elo.yaml')
    rejects(Metric, changed(doc, requires_pool=False, headroom_computable=True), match='never headroom_computable')
    rejects(Metric, changed(doc, range={'min': 0, 'max': 3000}), match='no range.max')


def test_a_rating_pool_without_a_snapshot_date_is_rejected():
    doc = fx('rating-pool-kaggle-chess.yaml')
    rejects(RatingPool, changed(doc, snapshot_date=...), match='snapshot_date')
    rejects(RatingPool, changed(doc, snapshot_date=None), match='snapshot_date')


# ---- 04 S2: every entity type has a model that instantiates from a fixture ----------------------

def _first(pattern):
    paths = sorted(glob.glob(os.path.join(ROOT, pattern), recursive=True))
    assert paths, pattern
    return read_yaml(paths[0])


ENTITY_GRAPH = {        # the boxes of 04 S2's diagram -> (model, a fixture)
    'Organization': (Organization, lambda: fx('organization-princeton-nlp.yaml')),
    'Benchmark': (Benchmark, lambda: _first('data/benchmarks/**/*.yaml')),
    'BenchmarkVersion': (BenchmarkVersion, lambda: fx('benchmark-version-swe-bench-verified.yaml')),
    'Leaderboard': (Leaderboard, lambda: fx('leaderboard-swebench-official.yaml')),
    'Subset': (Subset, lambda: fx('subset-mmlu-college-chemistry.yaml')),
    'Metric': (Metric, lambda: fx('metric-gdt-ts.yaml')),
    'System': (System, lambda: fx('system-claude-example.yaml')),
    'SystemVersion': (SystemVersion, lambda: fx('system-claude-example.yaml')['versions'][0]),
    'ResultClaim': (ResultClaim, lambda: fx('claim-swe-bench-example.yaml')),
    'Source': (Source, lambda: fx('source-example-page.yaml')),
    'RatingPool': (RatingPool, lambda: fx('rating-pool-kaggle-chess.yaml')),
    'EvalConditions': (EvalConditions, lambda: _first('tests/schema/fixtures/comparability/agentic-partial.yaml')['conditions']),
    'IngestBatch': (IngestBatch, lambda: fx('ingest-batch-epoch.yaml')),
    'Baseline': (Baseline, lambda: fx('baselines-swe-bench.yaml')[0]),
    'Alias': (Alias, lambda: fx('aliases-systems.yaml')[0]),
}


def test_the_entity_graph_is_the_one_04_s2_draws():
    text = open(os.path.join(ROOT, '_plan', '04-data-model.md'), encoding='utf-8').read()
    graph = text[text.index('## 2. Entity graph'):text.index('## 3. Identity')]
    for name in ENTITY_GRAPH:
        assert name in graph, name


@pytest.mark.parametrize('name', sorted(ENTITY_GRAPH))
def test_every_04_s2_entity_instantiates_from_a_fixture(name):
    model, load = ENTITY_GRAPH[name]
    assert model.model_validate(load())


# ---- Metric ---------------------------------------------------------------------------------------

def test_higher_is_better_is_derived_from_optimum_and_never_hand_written():
    doc = fx('metric-gdt-ts.yaml')
    assert Metric.model_validate(doc).higher_is_better is True
    assert Metric.model_validate(changed(doc, optimum='min')).higher_is_better is False
    assert Metric.model_validate(changed(doc, optimum='zero')).higher_is_better is None
    rejects(Metric, changed(doc, higher_is_better=True), match='higher_is_better')


def test_headroom_is_12_s3_1_unclamped():
    m = Metric.model_validate(fx('metric-gdt-ts.yaml'))
    assert m.headroom_consumed(sota=60, baseline=20, ceiling=100) == 0.5
    assert m.headroom_consumed(sota=82.6, baseline=0, ceiling=72.4) > 1.0            # OSWorld: anchor passed
    lower = Metric.model_validate(changed(fx('metric-gdt-ts.yaml'), optimum='min'))
    assert lower.headroom_consumed(sota=30, baseline=50, ceiling=10) == 0.5


@pytest.mark.parametrize('changes, reason', [
    ({'optimum': 'zero'}, 'lower-is-better-optimum-zero'),
    ({'value_type': 'vector'}, 'vector-valued-by-design'),
    ({'headroom_computable': False}, 'metric-not-headroom-computable'),
])
def test_headroom_refuses_with_12_s3_4_reasons(changes, reason):
    m = Metric.model_validate(changed(fx('metric-gdt-ts.yaml'), **changes))
    with pytest.raises(HeadroomNotComputable) as e:
        m.headroom_consumed(1, 0, 2)
    assert e.value.reason == reason


def test_a_pool_relative_metric_refuses_headroom():
    m = Metric.model_validate(changed(fx('metric-arena-elo.yaml'), unbounded=False, range=None))
    with pytest.raises(HeadroomNotComputable) as e:
        m.headroom_consumed(1, 0, 2)
    assert e.value.reason == 'relative-rating-only'


def test_epochs_random_baseline_and_score_ceiling_have_their_own_fields():
    doc = changed(fx('metric-gdt-ts.yaml'), range={'min': 0, 'max': 1}, chance_baseline=0.25, score_ceiling=0.57)
    m = Metric.model_validate(doc)
    assert (m.chance_baseline, m.score_ceiling) == (0.25, 0.57)
    rejects(Metric, changed(doc, score_ceiling=1.2), match='outside the range')
    rejects(Metric, changed(doc, random_baseline=0.25), match='random_baseline')      # one spelling


def test_metric_rules():
    doc = fx('metric-gdt-ts.yaml')
    rejects(Metric, changed(doc, optimum='target'), match='optimum_target')
    Metric.model_validate(changed(doc, optimum='target', optimum_target=50))
    rejects(Metric, changed(doc, must_report_with=['gdt-ts']), match='itself')
    rejects(Metric, changed(doc, sources=[]))
    rejects(Metric, changed(doc, value_type='percentage'))
    rejects(Metric, changed(doc, domains=['biology-genetics']))                   # a family, not a leaf


# ---- Baseline -------------------------------------------------------------------------------------

def test_baseline_kinds_are_nine_ceilings_and_three_floors():
    models, _ = load_taxonomy(os.path.join(ROOT, 'taxonomy'))
    facet = {t.id for t in models['ceiling-anchors.yaml'].terms}
    assert set(CEILING_ANCHOR.values()) == facet - {'none-known'}
    assert len(CEILING_ANCHOR) == 9 and len(FLOOR_KINDS) == 3
    assert not set(FLOOR_KINDS) & set(CEILING_ANCHOR)
    assert 'noise-ceiling' in CEILING_ANCHOR and 'experimental-replicate' in CEILING_ANCHOR
    rejects(Baseline, changed(fx('baselines-swe-bench.yaml')[0], kind='biological-replicate'))


def test_a_baseline_has_a_value_or_a_reason_exactly_one():
    b = fx('baselines-swe-bench.yaml')[0]
    rejects(Baseline, changed(b, value=None), match='exactly one')
    rejects(Baseline, changed(b, value_absent_reason='not-applicable'), match='exactly one')
    rejects(Baseline, changed(b, source=None), match='source')
    rejects(Baseline, changed(b, kind='operational-system'), match='n_humans')


def test_exactly_one_primary_per_version_and_metric():
    file = fx('baselines-swe-bench.yaml')
    two = copy.deepcopy(file)
    two[1]['is_primary'] = True
    rejects(BaselineFile, two, match='exactly one is_primary')
    none = copy.deepcopy(file)
    none[0]['is_primary'] = False
    rejects(BaselineFile, none, match='found 0')


def test_baseline_reports_its_anchor_type():
    bs = BaselineFile.model_validate(fx('baselines-swe-bench.yaml')).root
    assert [(b.ceiling_anchor_type, b.is_floor) for b in bs] == [
        ('expert-average', False), (None, True), ('theoretical-maximum', False)]


# ---- BenchmarkVersion and Subset, alone and inline on a Benchmark -------------------------------

def test_an_edition_is_always_breaking():
    v = fx('benchmark-version-swe-bench-verified.yaml')
    rejects(BenchmarkVersion, changed(v, version_kind='edition', breaking=False), match='always breaking')
    rejects(BenchmarkVersion, changed(v, superseded_by='verified'), match='itself')
    rejects(BenchmarkVersion, changed(v, errata=[{'date': None, 'scope': None, 'description': None, 'source': None}]))
    BenchmarkVersion.model_validate(changed(v, superseded_by='verified-2', errata=[
        {'date': '2026-06-12', 'description': 'Corrected 42% of problems.', 'source': 'src-x'}]))


def test_subset_overrides_are_vocabulary_checked():
    s = fx('subset-mmlu-college-chemistry.yaml')
    rejects(Subset, changed(s, id='college-chemistry'))
    rejects(Subset, changed(s, domain_override={'primary': 'chemistry-materials'}))
    rejects(Subset, changed(s, capability_override=['telepathy']))
    rejects(Subset, changed(s, parent='other#x'), match='another benchmark')


def _entry(**changes):
    doc = read_yaml(os.path.join(ROOT, 'data', 'benchmarks', 'code', 'swe-bench.yaml'))
    doc.update(copy.deepcopy(changes))
    return doc


def test_inline_versions_subsets_and_baselines_are_the_new_models():
    b = Benchmark.model_validate(_entry(
        versions=[{'version': 'full'}, fx('benchmark-version-swe-bench-verified.yaml')],
        subsets=[{'id': 'swe-bench#django', 'label': 'Django'}],
        baselines=[fx('baselines-swe-bench.yaml')[0]]))
    assert isinstance(b.versions[1], BenchmarkVersion) and isinstance(b.subsets[0], Subset)
    assert isinstance(b.baselines[0], Baseline)
    for path in glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True):
        load_benchmark(path)                                                     # the entries still load


@pytest.mark.parametrize('changes, match', [
    ({'versions': [fx('benchmark-version-swe-bench-verified.yaml')]}, 'not listed'),          # supersedes 'full'
    ({'versions': [{'version': 'a'}, {'version': 'a'}]}, 'twice'),
    ({'subsets': [{'id': 'mmlu#x', 'label': 'X'}]}, 'another benchmark'),
    ({'subsets': [{'id': 'swe-bench#x', 'label': 'X', 'parent': 'swe-bench#y'}]}, 'not listed'),
    ({'baselines': [changed(fx('baselines-swe-bench.yaml')[0], benchmark_version='mmlu@1')]}, 'is on mmlu@1'),
])
def test_inline_entities_belong_to_their_benchmark(changes, match):
    rejects(Benchmark, _entry(**changes), match=match)


# ---- Organization, Leaderboard, RatingPool ------------------------------------------------------

@pytest.mark.parametrize('changes', [
    {'country': 'USA'}, {'ror': 'https://ror.org/xyz'}, {'wikidata': '21578'}, {'kind': 'startup'},
    {'parent': 'org-princeton-nlp'}, {'roles': ['sponsor']}, {'sources': []},
])
def test_organization_rules(changes):
    rejects(Organization, changed(fx('organization-princeton-nlp.yaml'), **changes))


def test_leaderboard_rules():
    lb = fx('leaderboard-swebench-official.yaml')
    rejects(Leaderboard, changed(lb, submission_process='honour-system'))
    rejects(Leaderboard, changed(lb, form='assessment-paper'), match='not live')
    rejects(Leaderboard, changed(lb, benchmarks=[]))
    Leaderboard.model_validate(changed(lb, form='assessment-paper', is_live=False))


def test_a_pool_is_a_pool_at_a_date():
    doc = fx('rating-pool-kaggle-chess.yaml')
    rejects(RatingPool, changed(doc, snapshot_date='2026-06-01'), match='carries its snapshot date')
    RatingPool.model_validate(changed(doc, id='pool-kaggle-game-arena-chess-2026-09-01'))
    rejects(RatingPool, changed(doc, anchor='model-z'), match='not a member')
    rejects(RatingPool, changed(doc, members=['model-a@1']))
    rejects(RatingPool, changed(doc, members=['model-a@1', 'model-a@1']), match='twice')
    rejects(RatingPool, changed(doc, rating_system='elo-all-play-all'))


# ---- IngestBatch and Alias ----------------------------------------------------------------------

def test_the_licence_block_is_coherent():
    doc = fx('ingest-batch-epoch.yaml')
    b = IngestBatch.model_validate(doc)
    assert b.licence.class_ == 'permissive-attribution'
    assert b.model_dump(by_alias=True)['licence']['class'] == 'permissive-attribution'
    for lic, match in [({'attribution_text': None}, 'attribution_text'),
                       ({'class': 'share-alike'}, 'share_alike'),
                       ({'class': 'no-redistribution'}, 'redistribution_permitted'),
                       ({'class': 'public-domain'}, None)]:
        d = copy.deepcopy(doc)
        d['licence'].update(lic)
        rejects(IngestBatch, d, match=match)


def test_batch_rules():
    doc = fx('ingest-batch-epoch.yaml')
    rejects(IngestBatch, changed(doc, resolver_snapshot_sha256='c4f1...'))
    rejects(IngestBatch, changed(doc, target_tree='claims/'))
    rejects(IngestBatch, changed(doc, counts={'claims_written': -1}))
    rejects(IngestBatch, changed(doc, adapter_version='v0.3'))


def test_an_alias_routes_what_it_strips_to_fields_that_exist():
    a = fx('aliases-systems.yaml')
    assert Alias.model_validate(a[1]).entity == ('system', 'gpt-6-astra')
    rejects(Alias, changed(a[1], extracts={'eval_conditions.effort': 'max'}), match='do not exist')
    rejects(Alias, changed(a[1], extracts={'eval_conditions.reasoning_effort': 'unknown'}), match='not in the enum')
    rejects(Alias, changed(a[0], extracts={'serving_provider': 'Fireworks'}), match='organization id')
    rejects(Alias, changed(a[0], resolves_to='glm-4-6'))
    rejects(Alias, changed(a[0], resolves_to='metric:gdt-ts'))


def test_one_resolution_per_alias_string():
    a = fx('aliases-systems.yaml')
    rejects(AliasFile, a + [changed(a[0], resolves_to='system:glm-5')], match='resolves to both')
    rejects(AliasFile, a + [a[0]], match='twice')


# ---- Dispute --------------------------------------------------------------------------------------

def test_a_dispute_states_both_positions_with_their_sources():
    d = fx('dispute-swe-bench-verified.yaml')
    rejects(Dispute, changed(d, evidence=[]))
    rejects(Dispute, changed(d, claim_sources=...))
    rejects(Dispute, changed(d, position=' '))
    rejects(Dispute, changed(d, disputant_relationship='competitor'))


def test_the_dispute_lifecycle():
    d = fx('dispute-swe-bench-verified.yaml')
    rejects(Dispute, changed(d, resolved_on='2026-09-20'), match='open dispute')
    rejects(Dispute, changed(d, status='resolved-claim-retained'), match='needs resolved_on')
    rejects(Dispute, changed(d, status='withdrawn', resolved_on='2026-09-01'), match='before raised_on')
    rejects(Dispute, changed(d, status='withdrawn', resolved_on='2026-09-20', our_response=None), match='our_response')
    rejects(Dispute, changed(d, status='resolved-claim-corrected', resolved_on='2026-09-20'), match='corrected_by')
    rejects(Dispute, changed(d, corrected_by='claim-000000000001'), match='corrected_by')
    Dispute.model_validate(changed(d, status='resolved-claim-corrected', resolved_on='2026-09-20',
                                   corrected_by='claim-000000000001'))


@pytest.mark.parametrize('status, disputed', [('open', True), ('resolved-claim-retained', False),
                                              ('resolved-claim-corrected', False), ('withdrawn', False)])
def test_the_sota_rule_reads_only_an_open_dispute_as_disputed(status, disputed):
    extra = {} if status == 'open' else {'resolved_on': '2026-09-20'}
    if status == 'resolved-claim-corrected':
        extra['corrected_by'] = 'claim-000000000001'
    d = Dispute.model_validate(changed(fx('dispute-swe-bench-verified.yaml'), status=status, **extra))
    assert d.is_standing is disputed
    assert claim_is_disputed('claim-3c8e10ba55f7', [d]) is disputed
    assert claim_is_disputed('claim-000000000009', [d]) is False


def test_data_disputes_exists_and_holds_only_valid_disputes():
    path = os.path.join(ROOT, 'data', 'disputes')
    assert os.path.isdir(path)
    for p in glob.glob(os.path.join(path, '*.yaml')):
        Dispute.model_validate(read_yaml(p))
