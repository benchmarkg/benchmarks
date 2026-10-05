"""F7 near-duplicate candidates and their calibrated threshold (P1-S2-T05; tools/dedup.py; 11 S F7).

DONE WHEN: "config/dedup.yaml carries a derived threshold with its precision and recall on the 200-pair
set." So these tests hold the file to a fresh calibration: the threshold, precision and recall it
carries are what `calibrate()` computes now from tests/dedup/fixtures/known-pairs.yaml, and that set is
what build_known_pairs.py produces from the repository. A hand-edited threshold, a hand-edited pair or
a drifted scorer fails here.
"""
import os
import sys
from collections import Counter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests', 'dedup', 'fixtures'))
from tools import dedup as D  # noqa: E402

CFG = D.load_config()


@pytest.fixture(scope='module')
def fresh():
    return D.calibrate(CFG)


def test_the_config_carries_a_derived_threshold_with_its_precision_and_recall_on_200_pairs(fresh):
    cal = CFG['calibration']
    assert cal['n_pairs'] == 200 and sum(cal['labels'].values()) == 200
    assert CFG['cosine_threshold'] == cal['chosen']['threshold']
    assert cal['chosen']['precision'] > D.PRECISION_FLOOR
    assert set(cal['chosen']) >= {'precision', 'recall', 'tp', 'fp', 'fn', 'tn'}
    assert CFG['scorer'] == D.SCORER                     # the threshold is read beside its scorer


def test_the_committed_calibration_is_what_a_fresh_calibration_computes(fresh):
    committed = {k: v for k, v in CFG['calibration'].items() if k != 'calibrated_on'}
    assert committed == fresh
    assert fresh['pairs_sha256'] == D.file_sha256(D.PAIRS)


def test_the_threshold_maximises_recall_subject_to_precision_above_09(fresh):
    grid = fresh['grid']
    assert [g['threshold'] for g in grid] == [round(0.80 + 0.01 * i, 2) for i in range(16)]
    ok = [g for g in grid if g['precision'] > 0.9]
    best = max(g['recall'] for g in ok)
    assert fresh['chosen']['recall'] == best
    assert fresh['chosen']['threshold'] == max(g['threshold'] for g in ok if g['recall'] == best)   # ties: higher
    for g in grid:                                        # the confusion counts add up on every row
        assert g['tp'] + g['fp'] + g['fn'] + g['tn'] == 200


def test_the_pair_set_is_what_its_builder_produces():
    import build_known_pairs as B
    records, pairs, _ = B.build()
    fixture = D.load_pairs()
    assert [r['id'] for r in records] == sorted(fixture[0])
    assert [(p['a'], p['b'], p['label']) for p in pairs] == [(p['a'], p['b'], p['label']) for p in fixture[1]]


def test_the_pair_set_is_200_unique_labelled_pairs_over_the_named_families():
    records, pairs = D.load_pairs()
    keys = [tuple(sorted((p['a'], p['b']))) for p in pairs]
    assert len(pairs) == 200 and len(set(keys)) == 200
    assert all(p['label'] in D.LABELS and p['a'] in records and p['b'] in records and p['basis'] for p in pairs)
    basis = Counter(p['basis'].split(' (')[0] for p in pairs)
    for family in ('data/benchmarks/code/swe-bench.yaml lineage', 'CASP editions', 'HELM leaderboards',
                   'FrontierMath components'):
        assert basis[family] >= 6, family              # 11 S F7's four families are all in the set
    label = {tuple(sorted((p['a'], p['b']))): p['label'] for p in pairs}
    # 11 S F7: "SWE-bench, SWE-bench Verified and SWE-bench Pro are different benchmarks" -- related, not one.
    for a, b in (('data:swe-bench', 'corpus:swe-bench-verified'), ('data:swe-bench', 'page:swe-bench-pro'),
                 ('corpus:swe-bench-verified', 'page:swe-bench-pro')):
        assert label[tuple(sorted((a, b)))] == 'variant-of'


def test_arxiv_ids_are_paths_not_file_names():
    assert D.url_key('https://arxiv.org/abs/2406.01574') == ('arxiv.org', ('abs', '2406.01574'), 'catalogue')
    assert not D.same_site('https://arxiv.org/abs/2406.01574', 'https://arxiv.org/abs/2310.06770')
    assert D.same_site('https://www.swebench.com/lite.html', 'https://www.swebench.com/verified.html')
    assert D.same_site('https://crfm.stanford.edu/helm/lite/latest/', 'https://crfm.stanford.edu/helm/safety/latest/')
    assert not D.same_site('https://epoch.ai/benchmarks/a', 'https://epoch.ai/benchmarks/b')   # a generic section
    assert not D.same_site('https://github.com/openai/mle-bench', 'https://github.com/openai/preparedness')
    assert D.same_site('https://github.com/SWE-bench/SWE-bench', 'https://github.com/SWE-bench/SWE-bench/tree/main')


def test_editions_share_a_stem_and_look_alikes_do_not():
    r = lambda n: D.Record(n, n)                          # noqa: E731
    assert D.tokens('CASP14') == {'casp', '14'} and D.stem('Terminal-Bench 2.0') == 'bench terminal'
    assert D.same_stem(r('CASP14'), r('CASP17')) and D.same_stem(r('ARC-AGI-2'), r('ARC-AGI-3'))
    assert not D.same_stem(r('MMLU-Pro'), r('MMMU-Pro')) and not D.same_stem(r('DCASE 2026'), r('LifeCLEF 2026'))


def test_candidates_are_proposals_never_merges():
    records = D.corpus_records([])
    # The curated entries are different benchmarks; swe-bench and swe-bench-verified look alike (url, name) but
    # swe-bench-verified's lineage says it is swe-bench's subset, a curator's answer, so they are not proposed.
    assert D.candidates(records, CFG) == []
    assert D.from_benchmark({'id': 'swe-bench-verified', 'lineage': {'subset_of': 'swe-bench'}}).related == {'swe-bench'}
    verified = D.Record('drafts/benchmarks/swe-bench-verified.yaml', 'SWE-bench Verified',
                        urls=['https://www.swebench.com/verified.html'])
    got = D.candidates(records + [verified], CFG)          # a draft has no lineage: proposed beside both
    assert sorted((s.a, s.b) for s, _ in got) == [('swe-bench', 'drafts/benchmarks/swe-bench-verified.yaml'),
                                                  ('swe-bench-verified', 'drafts/benchmarks/swe-bench-verified.yaml')]
    assert all({'url', 'name'} <= set(fired) for _, fired in got)
    assert len(D.corpus_records([])) == len(records)      # nothing was written or merged
