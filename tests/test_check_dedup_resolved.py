"""Tests for scripts/check_dedup_resolved.py and data/_analysis/dedup-verdicts.yaml (P1-S13-T05; 11 S F7, 05 S3).

The verify: `bench resolve --candidates --threshold 0.88 && python scripts/check_dedup_resolved.py`. Done when "No
unresolved candidate pair remains above the calibrated threshold." The synthetic cases pass the candidate list in,
so they test the verdict rules without the scorer; the last case runs the scorer over the repository.
"""
import datetime as dt
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_dedup_resolved as C  # noqa: E402

TODAY = dt.date(2026, 11, 27)


def entry(root, family, ident, lineage=None):
    d = root / 'data' / 'benchmarks' / family
    d.mkdir(parents=True, exist_ok=True)
    doc = {'id': ident, 'name': ident.upper()}
    if lineage:
        doc['lineage'] = lineage
    (d / (ident + '.yaml')).write_text(yaml.safe_dump(doc), encoding='utf-8')


def row(a, b, verdict='distinct', **over):
    out = {'pair': [a, b], 'signal': 'name', 'verdict': verdict, 'reason': 'They are different datasets.',
           'decided_by': 'a curator', 'decided_on': dt.date(2026, 11, 1)}
    out.update(over)
    return {k: v for k, v in out.items() if v is not None}


def verdicts(root, rows):
    path = root / 'data' / '_analysis' / 'dedup-verdicts.yaml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'version': 1, 'threshold': 0.88, 'pairs': rows}, sort_keys=False),
                    encoding='utf-8')


@pytest.fixture
def tree(tmp_path):
    entry(tmp_path, 'code', 'alpha')
    entry(tmp_path, 'code', 'alpha-pro')
    entry(tmp_path, 'language', 'beta')
    entry(tmp_path, '_stubs', 'gamma')
    return tmp_path


def test_every_candidate_adjudicated_passes(tree):
    verdicts(tree, [row('alpha', 'beta'), row('alpha-pro', 'alpha')])
    assert C.check(str(tree), TODAY, [('alpha', 'beta'), ('alpha', 'alpha-pro')]) == []


def test_a_candidate_with_no_verdict_fails(tree):
    verdicts(tree, [row('alpha', 'beta')])
    errs = C.check(str(tree), TODAY, [('alpha', 'beta'), ('alpha', 'alpha-pro')])
    assert errs == ['(alpha, alpha-pro) is a candidate pair with no verdict in data/_analysis/dedup-verdicts.yaml: '
                    'adjudicate it']


def test_a_pair_is_matched_in_either_order_and_listed_once(tree):
    verdicts(tree, [row('beta', 'alpha'), row('alpha', 'beta')])
    errs = C.check(str(tree), TODAY, [('alpha', 'beta')])
    assert len(errs) == 1 and 'the pair already has a row' in errs[0]


def test_a_variant_needs_a_lineage_edge(tree):
    verdicts(tree, [row('alpha-pro', 'alpha', 'variant-of', expressed_as='alpha lineage.extended_by')])
    assert any('no lineage edge links the two entries' in e for e in C.check(str(tree), TODAY, []))
    entry(tree, 'code', 'alpha', lineage={'extended_by': ['alpha-pro']})
    assert C.check(str(tree), TODAY, []) == []


def test_a_variant_edge_may_sit_on_either_entry(tree):
    entry(tree, 'code', 'alpha-pro', lineage={'forks': [{'id': 'alpha'}]})
    verdicts(tree, [row('alpha', 'alpha-pro', 'variant-of')])
    assert C.check(str(tree), TODAY, []) == []


def test_same_needs_a_tombstone(tree):
    verdicts(tree, [row('alpha', 'beta', 'same')])
    assert any('neither id has a tombstone' in e for e in C.check(str(tree), TODAY, []))
    grave = tree / 'data' / 'tombstones'
    grave.mkdir(parents=True)
    (grave / 'beta.yaml').write_text('id: beta\n', encoding='utf-8')
    assert C.check(str(tree), TODAY, []) == []


@pytest.mark.parametrize('over, message', [
    ({'verdict': 'maybe'}, "verdict 'maybe' is not one of same, variant-of, distinct"),
    ({'reason': 'Two sentences. Not one.'}, 'one sentence'),
    ({'reason': None}, 'keys must be'),
    ({'decided_by': ' '}, 'no decided_by'),
    ({'decided_on': '2026-11'}, 'is not a date'),
    ({'decided_on': dt.date(2026, 12, 1)}, 'is after today'),
    ({'note': 'extra'}, 'keys must be'),
])
def test_a_malformed_row_fails(tree, over, message):
    verdicts(tree, [row('alpha', 'beta', **over)])
    errs = C.check(str(tree), TODAY, [('alpha', 'beta')])
    assert any(message in e for e in errs), errs


@pytest.mark.parametrize('pair, message', [
    (['alpha', 'alpha'], 'must name two different ids'),
    (['alpha'], 'must name two different ids'),
    (['alpha', 'gamma'], 'gamma is not a curated entry'),               # a stub is not adjudicated here
    (['alpha', 'nope'], 'nope is not a curated entry'),
])
def test_a_row_must_name_two_curated_entries(tree, pair, message):
    r = row('alpha', 'beta')
    r['pair'] = pair
    verdicts(tree, [r])
    assert any(message in e for e in C.check(str(tree), TODAY, []))


def test_no_verdict_file_fails(tree):
    assert C.check(str(tree), TODAY, []) == ['data/_analysis/dedup-verdicts.yaml does not exist']


def test_the_repository_passes():
    assert C.check(ROOT, TODAY, C.proposed(0.88)) == []
    rows = yaml.safe_load(open(os.path.join(ROOT, C.VERDICTS), encoding='utf-8'))['pairs']
    assert {tuple(sorted(r['pair'])) for r in rows} >= set(C.proposed(0.88))


def test_pr_validate_runs_it_as_a_blocking_job():
    """The maintainer's call of 2026-11-18: an unadjudicated pair fails the pull request."""
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = yaml.safe_load(fh)['jobs']['dedup-resolved']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert runs == ['uv run --locked --python "$PYTHON" python scripts/check_dedup_resolved.py']
