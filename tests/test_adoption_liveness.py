"""Tests for tools/build/adoption.py, tools/build/liveness.py and scripts/snapshot_adoption.py (P4-S2-T07; 12 S6-S7).

The done-when, in two halves. The 6,598 Epoch rows cannot produce a single-day activity spike: they are read from
tests/fixtures/epoch-dates/event-dates.json -- the date each real row would carry as date_reported, per day, made
from the Epoch snapshot by make_fixture.py -- every row stamped with one ingest time, and bucketed. And both
liveness flags abstain below two observed signals.
"""
import json
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import snapshot_adoption as snap  # noqa: E402
from tools.build import adoption, liveness  # noqa: E402

EPOCH = os.path.join(ROOT, 'tests', 'fixtures', 'epoch-dates', 'event-dates.json')
INGESTED_AT = '2026-10-04T12:00:00Z'                  # one ingest run: every row lands on this day


def epoch_rows(ingested_at=INGESTED_AT):
    with open(EPOCH, encoding='utf-8') as fh:
        d = json.load(fh)
    base = {'benchmark': 'x', 'system': 's', 'reported_by': 'org-epoch-ai',
            'ingestion': {'ingested_at': ingested_at, 'review_state': 'machine-ingested'}}
    rows = [dict(base, date_reported=day) for day, n in d['dates'].items() for _ in range(n)]
    rows += [dict(base, date_reported=None) for _ in range(d['undated'])]
    return d, rows


# ---- adoption: the ingest-date trap ---------------------------------------------------------------------

def test_the_fixture_is_the_6598_epoch_rows():
    d, rows = epoch_rows()
    assert d['rows'] == len(rows) == 6598 and d['undated'] + sum(d['dates'].values()) == 6598


def test_the_6598_epoch_rows_cannot_produce_a_single_day_spike():
    d, rows = epoch_rows()
    v = adoption.velocity(rows)
    assert v['total'] == 6598 and v['dated'] == 1541 and v['undated'] == {'claims': 5057, 'share': 0.7664}
    assert sum(b['claims'] for b in v['series']) == v['dated']        # the undated are beside the series, not in it
    months = {b['month']: b['claims'] for b in v['series']}
    assert '2026-10' not in months                                    # the ingest month holds no row
    # Bucketed on ingest, one day would hold all 6,598. On their own dates no day holds more than 166 and no
    # month more than 664 -- a tenth of the rows, and every one of them dated by the run it reports.
    assert max(d['dates'].values()) == 166 and max(months.values()) == 664 < 6598 / 9


def test_the_ingest_time_changes_nothing():
    _, a = epoch_rows('2026-10-04T12:00:00Z')
    _, b = epoch_rows('2027-01-01T00:00:00Z')
    assert adoption.velocity(a) == adoption.velocity(b)


def test_a_claim_with_only_an_ingest_time_is_undated():
    v = adoption.velocity([{'ingestion': {'ingested_at': INGESTED_AT}}, {'date_reported': date(2025, 2, 1)}])
    assert v['series'] == [{'month': '2025-02', 'claims': 1}] and v['undated'] == {'claims': 1, 'share': 0.5}


def test_no_claims_is_an_empty_series_not_a_division_by_zero():
    assert adoption.velocity([]) == {'bucket': 'month', 'date_field': 'date_reported', 'series': [], 'dated': 0,
                                     'undated': {'claims': 0, 'share': None}, 'total': 0}


# ---- adoption: the artifact -----------------------------------------------------------------------------

def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


FIGURE = {'arxiv': '2310.06770', 'sources': [], 'observed_on': '2026-10-04',
          'counts': {'semantic_scholar': 4090, 'openalex': 55}, 'records': {'semantic_scholar': 'p', 'openalex': 'W'},
          'corroborating': ['semantic_scholar'], 'value': 4090, 'single_source': True, 'ratio': None,
          'disagreement': False, 'identity_conflicts': ['openalex: W is titled ...']}


@pytest.fixture
def tree(tmp_path):
    write(tmp_path, 'data/benchmarks/code/demo.yaml',
          'id: demo\nexternal_ids:\n  arxiv: "2310.06770"\nrepository: https://github.com/o/demo\nsources: [src-a, src-b]\n'
          'liveness:\n  leaderboard_last_updated: 2025-01-10\n  reproduction_script_present: true\n')
    write(tmp_path, 'data/benchmarks/code/quiet.yaml', 'id: quiet\n')
    write(tmp_path, 'data/benchmarks/_stubs/stub.yaml', 'id: stub\n')
    for i, (system, org, when) in enumerate([('gpt-5@2025-08-07', 'org-openai', '2025-09-01'),
                                             ('gpt-5@2025-12-11', 'org-openai', '2025-12-20'),
                                             ('claude-x', 'org-anthropic', None)]):
        write(tmp_path, 'data/claims/demo/c%d.yaml' % i,
              'id: c%d\nbenchmark: demo@v1\nsystem: %s\nreported_by: %s\ndate_reported: %s\n'
              % (i, system, org, when or 'null'))
    write(tmp_path, 'data/sources/2026/src-a.yaml', 'id: src-a\nlink_status: live\n')
    write(tmp_path, 'data/sources/2026/src-b.yaml', 'id: src-b\nlink_status: dead\n')
    rows = [{'observed_on': '2026-09-27', 'benchmark': 'demo',
             'github': {'repo': 'o/demo', 'stars': 9, 'forks': 1, 'pushed_at': '2025-01-01T00:00:00Z', 'archived': False},
             'huggingface': None},
            {'observed_on': '2026-10-04', 'benchmark': 'demo',
             'github': {'repo': 'o/demo', 'stars': 10, 'forks': 1, 'pushed_at': '2025-02-01T00:00:00Z', 'archived': False},
             'huggingface': None}]
    write(tmp_path, 'metrics/adoption-counters.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
    write(tmp_path, 'metrics/citations.jsonl', json.dumps(FIGURE) + '\n')
    return tmp_path


def test_the_artifact_counts_systems_organisations_and_carries_counters_and_citations(tree):
    a = adoption.build(str(tree))
    [demo, quiet] = a['benchmarks']                                   # the stub is not a benchmark here
    assert (demo['id'], demo['claims'], demo['systems'], demo['organisations']) == ('demo', 3, 2, 2)
    assert demo['reporting_velocity']['undated'] == {'claims': 1, 'share': 0.3333}
    assert demo['repository']['stars'] == 10 and demo['counters_observed_on'] == '2026-10-04'   # the latest week
    assert demo['citations']['value'] == 4090 and demo['citations']['single_source'] is True
    assert quiet == dict(quiet, claims=0, repository=None, dataset=None, citations=None)          # null, never zero
    assert a['field']['reporting_velocity']['dated'] == 2


def test_a_citation_figure_without_its_flag_is_refused(tree):
    bad = {k: v for k, v in FIGURE.items() if k != 'single_source'}
    write(tree, 'metrics/citations.jsonl', json.dumps(bad) + '\n')
    with pytest.raises(ValueError, match='single_source'):
        adoption.build(str(tree))


def test_two_builds_are_byte_identical_and_nothing_is_written_to_data(tree, tmp_path):
    before = sorted((p, p.read_bytes()) for p in (tree / 'data').rglob('*') if p.is_file())
    assert adoption.serialise(adoption.build(str(tree))) == adoption.serialise(adoption.build(str(tree)))
    one = liveness.build(str(tree), date(2026, 10, 4))
    assert adoption.serialise(one) == adoption.serialise(liveness.build(str(tree), date(2026, 10, 4)))
    assert sorted((p, p.read_bytes()) for p in (tree / 'data').rglob('*') if p.is_file()) == before


def test_the_real_tree_builds():
    a, l = adoption.build(ROOT), liveness.build(ROOT, date(2026, 10, 4))
    assert {b['id'] for b in a['benchmarks'] if b['curated']} == {b['id'] for b in l['benchmarks']}


# ---- liveness -------------------------------------------------------------------------------------------

def test_the_signals_are_read_and_dated(tree):
    [demo, quiet] = liveness.build(str(tree), date(2026, 10, 4))['benchmarks']
    s = demo['signals']
    assert s['days_since_repo_push'] == (date(2026, 10, 4) - date(2025, 2, 1)).days    # the latest snapshot's
    assert s['days_since_leaderboard_change'] == (date(2026, 10, 4) - date(2025, 1, 10)).days
    assert s['days_since_dataset_modified'] is None and s['has_reproduction_script'] == 'yes'
    assert s['archived_source_rot'] == {'dead': 1, 'checked': 2, 'fraction': 0.5}
    assert quiet['signals']['has_reproduction_script'] == 'not-checked' and quiet['signals']['archived_source_rot'] is None


@pytest.mark.parametrize('activity', [
    {'repo_push': None, 'dataset_modified': None, 'leaderboard_change': None},
    {'repo_push': date(2020, 1, 1), 'dataset_modified': None, 'leaderboard_change': None},
    {'repo_push': None, 'dataset_modified': None, 'leaderboard_change': date(2019, 6, 1)},
])
def test_both_flags_abstain_below_two_observed_signals(activity):
    f = liveness.flags(activity, date(2026, 10, 4))
    assert f['dormant-signal'] is None and f['likely-inactive'] is None and f['statement'] is None
    assert f['basis'].startswith('abstains: %d of 3' % sum(v is not None for v in activity.values()))


def test_one_signal_years_old_still_abstains_where_two_would_not():
    old = date(2020, 1, 1)
    assert liveness.flags({'repo_push': old, 'dataset_modified': None, 'leaderboard_change': None},
                          date(2026, 10, 4))['likely-inactive'] is None
    assert liveness.flags({'repo_push': old, 'dataset_modified': old, 'leaderboard_change': None},
                          date(2026, 10, 4))['likely-inactive'] is True


@pytest.mark.parametrize('last, dormant, inactive', [
    (date(2025, 4, 5), False, False),       # 18 months less a day
    (date(2025, 4, 4), True, False),        # exactly 18 months
    (date(2023, 10, 5), True, False),       # 36 months less a day
    (date(2023, 10, 4), True, True),        # exactly 36 months
])
def test_the_thresholds_are_18_and_36_months_of_no_activity_on_any_signal(last, dormant, inactive):
    f = liveness.flags({'repo_push': last, 'dataset_modified': date(2020, 1, 1), 'leaderboard_change': None},
                       date(2026, 10, 4))
    assert (f['dormant-signal'], f['likely-inactive']) == (dormant, inactive)
    assert f['last_activity'] == last.isoformat() and f['basis'] == 'signals checked: dataset_modified, repo_push'


def test_the_statement_names_days_and_signals_and_never_says_dead():
    f = liveness.flags({'repo_push': date(2026, 9, 4), 'dataset_modified': date(2025, 1, 1), 'leaderboard_change': None},
                       date(2026, 10, 4))
    assert f['statement'] == 'no observed activity in 30 days across 2 checked signals'
    assert 'dead' not in json.dumps(f)


def test_month_arithmetic_clamps_to_the_end_of_the_month():
    assert liveness.add_months(date(2024, 8, 31), 18) == date(2026, 2, 28)
    assert liveness.add_months(date(2022, 8, 31), 18) == date(2024, 2, 29)


def test_as_of_defaults_to_the_commit_date_not_today():
    assert liveness.build(ROOT)['as_of'] == liveness.commit_date(ROOT).isoformat()


def test_no_lifecycle_is_ever_written():
    assert 'lifecycle' not in json.dumps(liveness.build(ROOT, date(2026, 10, 4)))


# ---- the weekly snapshot --------------------------------------------------------------------------------

def fake_fetch(answers):
    seen = []

    def fetch(url, headers):
        seen.append(url)
        return answers[url]
    return fetch, seen


def test_the_snapshot_reads_github_and_hf_and_records_an_error_as_an_error(tree):
    write(tree, 'data/benchmarks/code/quiet.yaml', 'id: quiet\ndataset_url: https://huggingface.co/datasets/o/q\n')
    fetch, seen = fake_fetch({
        'https://api.github.com/repos/o/demo': (200, {'stargazers_count': 11, 'forks_count': 2,
                                                      'pushed_at': '2026-10-01T00:00:00Z', 'archived': False}),
        'https://huggingface.co/api/datasets/o/q': (404, None)})
    lines = snap.snapshot(str(tree), date(2026, 10, 12), fetch=fetch, sleep=lambda s: None)
    assert [l['benchmark'] for l in lines] == ['demo', 'quiet']
    assert lines[0]['github'] == {'repo': 'o/demo', 'stars': 11, 'forks': 2, 'pushed_at': '2026-10-01T00:00:00Z',
                                  'archived': False}
    assert lines[1]['huggingface'] == {'dataset': 'o/q', 'error': 'HTTP 404'} and lines[1]['github'] is None


def test_the_snapshot_is_weekly(tree):
    fetch, seen = fake_fetch({})
    assert snap.snapshot(str(tree), date(2026, 10, 4), fetch=fetch, sleep=lambda s: None) == [] and seen == []
    # 2026-10-04 is a Sunday, the last day of ISO week 40; the Monday after is a new week
    fetch, seen = fake_fetch({'https://api.github.com/repos/o/demo': (403, None)})
    assert len(snap.snapshot(str(tree), date(2026, 10, 5), fetch=fetch, sleep=lambda s: None)) == 1


@pytest.mark.parametrize('url, repo', [('https://github.com/SWE-bench/SWE-bench', 'SWE-bench/SWE-bench'),
                                       ('https://github.com/o/r.git', 'o/r'), ('https://github.com/o/r/', 'o/r'),
                                       ('https://github.com/o', None), ('https://gitlab.com/o/r', None)])
def test_github_repository_urls(url, repo):
    assert snap.github_repo({'repository': url}) == repo
