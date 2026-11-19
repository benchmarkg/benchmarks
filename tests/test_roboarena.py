"""RoboArena: rating pools, the four material environment fields and the missing absolute baseline (P3-S6-T05;
04 S7, S8, 12 S3.4).

The verify: "bench validate --tier all, plus `uv run pytest tests/test_roboarena.py -q` asserting
comparability.rating_pool_required is set, that simulator, simulator_version, hardware_platform and venue are
material on the robotics profile, that every rating-pool record carries a snapshot date, and that the absence of an
absolute-score Baseline carries a recorded reason". The done-when: "Pairwise claims are expressible with claim_type
pairwise and an opponent, and the rating pool plus snapshot date are required." That is held here as:

  - rating_pool_required is set, and without it the rating-pool-required rule blocks;
  - the four environment fields are material on roboarena's resolved profile, through the entry's
    comparability.material_extra rather than taxonomy/comparability-profiles.yaml, whose profiles change only with
    an ADR and a migration. A real-robot claim and a simulated one, or two claims from different venues, that agree
    on everything else get different comparability keys; without the fields they would collide, which is the
    failure case;
  - every RatingPool on roboarena carries its snapshot date, in its id too; its members are Systems whose backend
    ids its Source lists under that snapshot; and a pool without its date is refused;
  - the one Baseline on the headline metric has no value and records why (value_absent_reason, notes, quotes
    found in their Sources), and a Baseline with neither a value nor a reason is refused;
  - a pairwise claim with an opponent validates against the pairwise metric, and a rating claim must name a pool.

Headroom's null with reason relative-rating-only is P3-S9-T04's to assert; here only that the Metric refuses one.
"""
import dataclasses
import glob
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema import validators as V  # noqa: E402
from schema.baseline import Baseline  # noqa: E402
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import RatingPool  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'robotics-embodiment', 'roboarena.yaml')
POOLS = sorted(glob.glob(os.path.join(ROOT, 'data', 'rating-pools', 'pool-roboarena-*.yaml')))
FOUR = ('simulator', 'simulator_version', 'hardware_platform', 'venue')
SIM = ('simulator', 'simulator_version')
REAL = dict(simulator='none', simulator_version='none', hardware_platform='DROID', venue='RoboArena evaluator network',
            subset_used='full', n_samples=190)


def metric(mid):
    return Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))


def source(sid):
    return Source.model_validate(read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml')))


def system(sid):
    return System.model_validate(read_yaml(os.path.join(ROOT, 'data', 'systems', sid + '.yaml')))


@pytest.fixture(scope='module')
def roboarena():
    return load_benchmark(ENTRY)


# ---- the rating pool is required --------------------------------------------------------------------

def test_rating_pool_required_is_set(roboarena):
    assert 'pairwise-preference-elo' in roboarena.evaluation_method
    assert roboarena.comparability.rating_pool_required is True
    assert V.validate(V.Corpus(benchmarks={'roboarena': roboarena}), only='rating-pool-required') == []


def test_without_it_the_rating_pool_rule_blocks(roboarena):
    """The failure case: a pairwise benchmark that stops requiring a pool is refused."""
    unpooled = roboarena.model_copy(update={'comparability': roboarena.comparability.model_copy(
        update={'rating_pool_required': False})})
    [f] = V.validate(V.Corpus(benchmarks={'roboarena': unpooled}), only='rating-pool-required')
    assert f.severity == 'blocking' and f.auto_fix == 'comparability.rating_pool_required = true'


# ---- the four environment fields --------------------------------------------------------------------

def test_the_four_environment_fields_are_material(roboarena):
    r = comp.resolve_profile(roboarena)
    assert set(FOUR) <= set(r.material)
    assert set(FOUR) <= set(roboarena.comparability.material_extra)
    assert all(r.weights[f] == 1.0 for f in FOUR)


def test_the_simulator_pair_comes_from_the_entry_not_the_vocabulary(roboarena):
    """taxonomy/comparability-profiles.yaml is untouched: without the entry's material_extra the facets' profile
    (physical-trial) leaves the simulator pair out, and hardware_platform and venue stay."""
    r = comp.resolve_profile(roboarena)
    assert r.basis == 'facets' and r.profiles == ('physical-trial',)
    bare = roboarena.model_copy(update={'comparability': roboarena.comparability.model_copy(
        update={'material_extra': []})})
    plain = comp.resolve_profile(bare)
    assert not set(SIM) & set(plain.material)
    assert {'hardware_platform', 'venue'} <= set(plain.material)


def _key(resolution, **changes):
    cond = EvalConditions(id='cond-0123456789ab', **{**REAL, **changes})
    return comp.compute(resolution, cond, 'roboarena', 'roboarena-rating', None)


def test_a_simulated_and_a_real_robot_claim_never_share_a_key(roboarena):
    r = comp.resolve_profile(roboarena)
    real, sim = _key(r), _key(r, simulator='a simulated DROID scene', simulator_version='1')
    assert real.comparability_key != sim.comparability_key
    assert real.key_unknown_count == sim.key_unknown_count == 0 and real.condition_completeness == 1.0


def test_two_venues_or_two_bodies_never_share_a_key(roboarena):
    r = comp.resolve_profile(roboarena)
    assert _key(r).comparability_key != _key(r, venue='one evaluator organisation').comparability_key
    assert _key(r).comparability_key != _key(r, hardware_platform='another arm').comparability_key


def test_without_the_fields_the_claims_would_collide(roboarena):
    """The failure case: drop the environment fields from the material set and the claims become one key."""
    r = comp.resolve_profile(roboarena)
    blind = dataclasses.replace(r, material=tuple(f for f in r.material if f not in FOUR),
                                weights={f: w for f, w in r.weights.items() if f not in FOUR})
    sim = dict(simulator='a simulated DROID scene', simulator_version='1')
    assert _key(blind).comparability_key == _key(blind, **sim).comparability_key
    assert _key(blind).comparability_key == _key(blind, venue='one evaluator organisation').comparability_key


# ---- the rating pools -------------------------------------------------------------------------------

def pools():
    return sorted((RatingPool.model_validate(read_yaml(p)) for p in POOLS), key=lambda p: p.snapshot_date)


def test_there_are_pools_and_each_carries_its_snapshot_date():
    assert len(POOLS) >= 2
    for path in POOLS:
        p = RatingPool.model_validate(read_yaml(path))
        assert os.path.basename(path) == p.id + '.yaml'
        assert p.benchmark == 'roboarena' and p.rating_system == 'bradley-terry'
        d = p.snapshot_date.isoformat()
        assert p.id.endswith('-' + d) or p.id.endswith('-' + d[:7])
    assert len({p.snapshot_date for p in pools()}) == len(POOLS)      # one pool per date


@pytest.mark.parametrize('path', POOLS, ids=os.path.basename)
def test_each_pools_members_are_systems_its_source_lists_under_that_snapshot(path):
    p = RatingPool.model_validate(read_yaml(path))
    header = '"policy_count":%d,"snapshot_at":"%s' % (len(p.members), p.snapshot_date.isoformat())
    extracts = [source(sid).quote_extract or '' for sid in p.sources]
    [extract] = [x for x in extracts if quote_found(header, x)]       # the Source that holds this snapshot
    for sid in p.members:
        s = system(sid)
        assert s.system_type == 'physical-robot-system'
        backend = s.external_ids['roboarena_policy']
        assert '"policy":"%s"' % backend in extract, (sid, backend)


def test_the_pool_moves_between_snapshots():
    early, late = pools()[0], pools()[-1]
    assert early.snapshot_date < late.snapshot_date
    assert set(early.members) < set(late.members)           # five policies joined between the two


def test_a_pool_without_its_snapshot_date_is_refused():
    """The failure case: the date is part of the pool's identity, so it is required and the id carries it."""
    doc = read_yaml(POOLS[-1])
    RatingPool.model_validate(doc)
    with pytest.raises(ValidationError, match='snapshot_date'):
        RatingPool.model_validate({k: v for k, v in doc.items() if k != 'snapshot_date'})
    with pytest.raises(ValidationError, match='carries its snapshot date'):
        RatingPool.model_validate({**doc, 'snapshot_date': '2026-11-09'})


# ---- the missing absolute baseline ------------------------------------------------------------------

def test_the_headline_metric_is_pool_relative(roboarena):
    assert roboarena.headline_metric == 'roboarena-rating'
    assert roboarena.metrics == ['roboarena-rating', 'roboarena-pairwise-win-rate']
    m = metric('roboarena-rating')
    assert m.requires_pool and m.unbounded and m.value_type == 'elo' and not m.headroom_computable
    assert m.range is None or m.range.max is None                    # no top is stated on a pool-relative scale
    # The null itself; which of 12 S3.4's two reasons it carries (headroom_null_reason() reads `unbounded` first,
    # where P3-S9-T04 expects relative-rating-only) is P3-S9-T04's to settle, and a review check on the entry.
    assert m.headroom_null_reason() in ('unbounded-metric', 'relative-rating-only')


def test_no_absolute_baseline_exists_and_the_reason_is_recorded(roboarena):
    assert not glob.glob(os.path.join(ROOT, 'data', 'baselines', 'roboarena.yaml'))
    assert all(b.value is None for b in roboarena.baselines)     # no absolute-score anchor anywhere
    [b] = [b for b in roboarena.baselines if b.metric == roboarena.headline_metric]
    assert b.value_absent_reason == 'not-applicable' and b.is_primary
    assert b.ceiling_anchor_type is not None                    # the absent thing is a ceiling, not a floor
    assert 'relative-rating-only' in b.notes and 'pool' in b.notes
    assert b.evidence
    for ev in b.evidence:
        assert quote_found(ev.quote, source(ev.source).quote_extract), ev.source
    assert roboarena.data.ceiling_anchor_type == 'none-known'


def test_a_baseline_without_value_or_reason_is_refused():
    """The failure case: an absent value with no reason says nothing about why."""
    doc = {'id': 'base-roboarena-x', 'benchmark_version': 'roboarena', 'kind': 'theoretical-maximum',
           'metric': 'roboarena-rating'}
    with pytest.raises(ValidationError, match='value or a value_absent_reason'):
        Baseline.model_validate(doc)
    Baseline.model_validate({**doc, 'value_absent_reason': 'not-applicable'})


# ---- pairwise and rating claims ---------------------------------------------------------------------

def claim(**changes):
    doc = {'id': 'claim-0a1b2c3d4e5f', 'system': 'dreamzero', 'benchmark': 'roboarena', 'metric': 'roboarena-rating',
           'claim_type': 'rating', 'value': 1735, 'rating_pool': 'pool-roboarena-2026-11-16',
           'date_reported': '2026-11-16', 'reported_by': 'org-roboarena', 'verification': 'maintainer-verified',
           'source': 'src-roboarena-api-leaderboard-history-2026-11-19'}
    doc.update(changes)
    return {k: v for k, v in doc.items() if v is not ...}


def test_a_rating_claim_names_its_pool():
    ResultClaim.model_validate(claim())
    with pytest.raises(ValidationError, match='rating_pool'):
        ResultClaim.model_validate(claim(rating_pool=...))


def test_a_pairwise_claim_is_expressible_with_an_opponent():
    m = metric('roboarena-pairwise-win-rate')
    assert m.value_type == 'ratio' and m.range.min == 0 and m.range.max == 100 and not m.headroom_computable
    pairwise = dict(claim_type='pairwise', metric=m.id, value=60.0, opponent='pi05-droid', rating_pool=...)
    ResultClaim.model_validate(claim(**pairwise))
    with pytest.raises(ValidationError, match='requires an opponent'):
        ResultClaim.model_validate(claim(**{**pairwise, 'opponent': ...}))
    with pytest.raises(ValidationError, match='rating claims only'):
        ResultClaim.model_validate(claim(**{**pairwise, 'rating_pool': 'pool-roboarena-2026-11-16'}))
