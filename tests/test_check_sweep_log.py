"""Tests for scripts/check_sweep_log.py (P1-S12-T02; 06 S6).

The verify is `python scripts/check_sweep_log.py --families robotics-embodiment,agents-tooluse --max-age
100d`; done-when is "both families carry a dated sweep record and every entry carries a checked_at within
the cadence". Each test builds a small tree that passes, breaks one thing, and asserts the check names it.
"""
import datetime as dt

import pytest
import yaml

from scripts import check_sweep_log as csl

TODAY = dt.date(2026, 11, 10)
HUBS = {
    'version': 1,
    'families': [{'family': 'fam', 'hubs': [{'name': 'Alpha', 'url': 'https://a.example/'},
                                           {'name': 'Beta', 'url': None}]}],
    'shared_hubs': [{'name': 'Shared', 'url': 'https://s.example/', 'families': ['fam', 'other']}],
}


def hub(name, outcome='checked-no-change'):
    return {'name': name, 'url': None, 'http_status': 200, 'final_url': None, 'page_state': 'live',
            'outcome': outcome, 'entries': [], 'findings': []}


def put(root, rel, doc):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')


@pytest.fixture
def tree(tmp_path):
    put(tmp_path, csl.HUBS, HUBS)
    for i in ('one', 'two'):
        put(tmp_path, '%s/fam/%s.yaml' % (csl.BENCHMARKS, i), {'id': i, 'liveness': {'last_checked': TODAY}})
    put(tmp_path, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log())
    return tmp_path


def log(**kw):
    doc = {'version': 1, 'family': 'fam', 'date': TODAY, 'curator': 'agent (P1-S12-T02)',
           'hubs': [hub('Alpha'), hub('Beta', 'unreachable'), hub('Shared')],
           'entries': [{'id': 'one', 'outcome': 'checked-no-change'}, {'id': 'two', 'outcome': 'changed'}]}
    doc.update(kw)
    return doc


def errors(root, days=100, today=TODAY):
    return csl.check_family(str(root), 'fam', today, days)


def test_a_complete_sweep_passes(tree):
    assert errors(tree) == []
    assert csl.main(['--families', 'fam', '--today', '2026-11-10', '--root', str(tree)]) == 0


def test_a_family_never_swept_fails(tree):
    (tree / csl.LOG_DIR / '2026-11-10-fam.yaml').unlink()
    assert any('never been swept' in e for e in errors(tree))


def test_a_stale_sweep_fails_and_the_newest_log_is_the_one_read(tree):
    assert any('days old' in e for e in errors(tree, today=TODAY + dt.timedelta(days=101)))
    put(tree, '%s/2026-08-01-fam.yaml' % csl.LOG_DIR, log(date=dt.date(2026, 8, 1), hubs=[]))
    assert errors(tree) == []


def test_a_hub_never_visited_fails_and_no_change_counts(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(hubs=[hub('Alpha'), hub('Beta')]))
    errs = errors(tree)
    assert errs == ["docs/sweeps/log/2026-11-10-fam.yaml: hub 'Shared' on the checklist was never visited"]


def test_a_dropped_hub_must_leave_the_hub_list(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(hubs=[hub('Alpha'), hub('Beta', 'dropped'), hub('Shared')]))
    assert any('dropped, but' in e for e in errors(tree))
    hubs = yaml.safe_load(yaml.safe_dump(HUBS))
    hubs['families'][0]['hubs'].pop()
    put(tree, csl.HUBS, hubs)
    assert errors(tree) == []


def test_an_unlisted_hub_that_is_not_a_drop_fails(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(hubs=log()['hubs'] + [hub('Gamma')]))
    assert any("'Gamma'" in e and 'not a drop' in e for e in errors(tree))


def test_an_unknown_outcome_fails(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(hubs=[hub('Alpha', 'fine'), hub('Beta'), hub('Shared')]))
    assert any("outcome 'fine'" in e for e in errors(tree))


def test_every_entry_needs_a_row_and_a_fresh_stamp(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(entries=[{'id': 'one', 'outcome': 'checked-no-change'}]))
    assert any('entry two has no row' in e for e in errors(tree))
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log())
    put(tree, '%s/fam/two.yaml' % csl.BENCHMARKS, {'id': 'two'})
    assert any('two.yaml: no liveness.last_checked' in e for e in errors(tree))
    put(tree, '%s/fam/two.yaml' % csl.BENCHMARKS, {'id': 'two', 'liveness': {'last_checked': dt.date(2026, 1, 1)}})
    assert any('two.yaml: liveness.last_checked 2026-01-01' in e for e in errors(tree))


def test_a_row_for_a_missing_entry_fails(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR,
        log(entries=log()['entries'] + [{'id': 'ghost', 'outcome': 'checked-no-change'}]))
    assert any("'ghost': no such entry" in e for e in errors(tree))


def test_the_file_name_and_the_contents_agree(tree):
    put(tree, '%s/2026-11-10-fam.yaml' % csl.LOG_DIR, log(date=dt.date(2026, 11, 9), family='other'))
    errs = errors(tree)
    assert any("family 'other'" in e for e in errs) and any('date' in e and 'file name' in e for e in errs)


def test_max_age_takes_days():
    assert csl.max_age('100d') == 100
    with pytest.raises(Exception):
        csl.max_age('3 months')
