"""The headroom-null guards (P0-S9-T02; 14-roadmap Phase 0 exit criterion 2, 02 S8, 12 S3.1, S3.4).

The verify: "None and no exception for the three named cases, and a rejection for a hand-set value on an
unbounded metric. Both assertions run against schema/validators.py, which is the only headroom machinery
Phase 0 builds". Headroom itself is computed by P3-S9-T02; nothing here asserts a computed value. What Phase 0
claims is the null path: for WeatherBench 2 (no ranking by design), Kaggle Game Arena (an unbounded Elo) and
RoboArena (pairwise preference, no absolute score), headroom is null, the rules say nothing and raise
nothing, and the metric layer refuses to produce a number, naming 12 S3.4's reason instead of erroring.
"""
import copy
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema import validators as V  # noqa: E402
from schema.benchmark import Benchmark  # noqa: E402
from schema.metric import HeadroomNotComputable, Metric  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

THE_THREE = ('weatherbench-2', 'kaggle-game-arena', 'roboarena')


@pytest.fixture(scope='module')
def corpus():
    return V.load_corpus(ROOT)


def only(corpus, bid, headroom):
    """The corpus narrowed to one benchmark, with the build's derived headroom set as given."""
    c = copy.copy(corpus)
    c.benchmarks = {bid: corpus.benchmarks[bid]}
    c.derived = {bid: {'headroom': headroom}}
    return c


# ---- the null path: None, and no exception -------------------------------------------------------

@pytest.mark.parametrize('bid', THE_THREE)
def test_verify_headroom_is_none_and_the_rules_raise_nothing(corpus, bid):
    assert bid in corpus.benchmarks
    assert bid not in corpus.derived or corpus.derived[bid]['headroom'] is None   # Phase 0 computes none
    c = only(corpus, bid, None)
    assert V.validate(c, only='headroom-guard-4') == []
    V.validate(c)                                  # every tier-3 rule over the entry, and none of them raises


def test_weatherbench_2_has_no_aggregate_to_take_headroom_of(corpus):
    b = corpus.benchmarks['weatherbench-2']
    assert b.no_legitimate_aggregate is True and b.headline_metric is None


def test_kaggle_game_arenas_elo_refuses_a_number_and_names_the_reason(corpus):
    elo = corpus.metrics[corpus.benchmarks['kaggle-game-arena'].headline_metric]
    assert elo.unbounded and elo.requires_pool and not elo.headroom_computable
    assert elo.headroom_null_reason() == 'unbounded-metric'
    with pytest.raises(HeadroomNotComputable) as e:
        elo.headroom_consumed(sota=1500.0, baseline=1000.0, ceiling=2000.0)
    assert e.value.reason == 'unbounded-metric'


def test_roboarena_is_pairwise_so_headroom_is_null_by_construction(corpus):
    b = corpus.benchmarks['roboarena']
    assert 'pairwise-preference-elo' in b.evaluation_method and b.data.ceiling_anchor_type == 'none-known'


# ---- null is not the same as an error, and a number is caught -----------------------------------------

@pytest.mark.parametrize('bid', ('kaggle-game-arena', 'roboarena'))
def test_a_number_where_headroom_must_be_null_blocks(corpus, bid):
    [f] = V.validate(only(corpus, bid, 0.4), only='headroom-guard-4')
    assert f.severity == 'blocking' and 'headroom is null by construction' in f.message


# ---- a hand-set headroom on an unbounded metric is a tier-1 failure -----------------------------------

def test_verify_an_unbounded_metric_marked_headroom_computable_is_rejected():
    doc = read_yaml(os.path.join(ROOT, 'data', 'metrics', 'game-arena-elo.yaml'))
    Metric.model_validate(doc)                                       # as committed: valid
    doc['headroom_computable'] = True
    with pytest.raises(ValidationError, match='an unbounded metric is never headroom_computable'):
        Metric.model_validate(doc)


def test_a_hand_written_headroom_on_the_entry_is_rejected():
    path = [os.path.join(d, 'kaggle-game-arena.yaml') for d, _, files in os.walk(os.path.join(ROOT, 'data', 'benchmarks'))
            if 'kaggle-game-arena.yaml' in files and '_stubs' not in d][0]
    doc = read_yaml(path)
    Benchmark.model_validate(doc)
    doc['headroom'] = 0.42                                            # derived by the build, never written by hand
    with pytest.raises(ValidationError, match='headroom'):
        Benchmark.model_validate(doc)
