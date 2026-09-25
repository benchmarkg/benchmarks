"""Tests for scripts/check_model_config_freshness.py over config/ai-models.yaml (P6-S2-T01).

The committed config must pass; each failure the checker names is produced by editing a copy.
"""
import copy
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_model_config_freshness as ck  # noqa: E402

TODAY = date(2026, 9, 24)
PLAN_IDS = ck.plan_models(ck.PLAN_11)


@pytest.fixture
def cfg():
    return copy.deepcopy(ck.load(ck.CONFIG))


def model(cfg, mid):
    return next(m for m in cfg['models'] if m['id'] == mid)


def fact(cfg, fid):
    return next(f for f in cfg['facts'] if f['id'] == fid)


def run(cfg, today=TODAY):
    return ck.check(cfg, today, PLAN_IDS)


def test_the_committed_config_passes(cfg):
    errors, warnings = run(cfg)
    assert errors == []


def test_the_cli_passes_and_only_warns():
    assert ck.main(['--today', '2026-09-24']) == 0
    assert ck.main(['--today', '2026-09-24', '--strict']) == 1  # the unconfirmed rate card is a warning


def test_every_row_has_a_source_and_a_date(cfg):
    for r in cfg['models'] + cfg['facts']:
        assert all(u.startswith('https://') for u in ck.urls(r)), r['id']
        assert ck.as_date(r['verified_on']) is not None, r['id']


def test_the_plan_models_are_all_present(cfg):
    assert set(PLAN_IDS) == {'claude-haiku-4-5', 'claude-sonnet-5', 'claude-opus-5'}
    assert set(PLAN_IDS) <= {m['id'] for m in cfg['models']}


def test_the_task_asks_for_these_rows(cfg):
    ids = {f['id'] for f in cfg['facts']}
    # step 2: Cloudflare quotas, Turnstile limits, the rate-limit binding's period constraint
    assert {'cloudflare-workers-free', 'cloudflare-turnstile-free', 'cloudflare-rate-limit-binding'} <= ids
    assert fact(cfg, 'cloudflare-rate-limit-binding')['value']['period_seconds_allowed'] == [10, 60]
    # step 3: the structured-output feature lists, next to the prices
    assert {'structured-outputs-supported', 'structured-outputs-unsupported'} <= ids


@pytest.mark.parametrize('field', ['source_url', 'verified_on'])
def test_a_row_without_source_or_date_fails(cfg, field):
    del model(cfg, 'claude-sonnet-5')[field]
    assert any('claude-sonnet-5' in e for e in run(cfg)[0])


def test_a_plain_http_source_fails(cfg):
    fact(cfg, 'anthropic-batch')['source_url'] = 'http://example.com/'
    assert any('not an https URL' in e for e in run(cfg)[0])


def test_a_future_date_fails(cfg):
    model(cfg, 'claude-opus-5')['verified_on'] = date(2027, 1, 1)
    assert any('in the future' in e for e in run(cfg)[0])


@pytest.mark.parametrize('field, bad', [
    ('batch_output', 5.00),        # Haiku 4.5 batch output is 2.50: a transcription slip
    ('cache_write_5m', 1.00),
    ('cache_write_1h', 1.25),
    ('cache_read', 0.20),
])
def test_a_price_that_contradicts_the_rate_card_arithmetic_fails(cfg, field, bad):
    model(cfg, 'claude-haiku-4-5')['price_usd_per_mtok'][field] = bad
    assert any(e.startswith('claude-haiku-4-5: %s' % field) for e in run(cfg)[0])


def test_the_cache_read_exception_is_honoured(cfg):
    # Opus 5.5's read is 0.05x, not 0.1x; the default multiplier would call $0.20 wrong.
    assert model(cfg, 'claude-opus-5-5')['price_usd_per_mtok']['cache_read'] == 0.20
    del fact(cfg, 'anthropic-cache-multipliers')['value']['cache_read_exceptions']['claude-opus-5-5']
    assert any(e.startswith('claude-opus-5-5: cache_read') for e in run(cfg)[0])


def test_a_missing_price_fails(cfg):
    del model(cfg, 'claude-sonnet-5')['price_usd_per_mtok']['batch_input']
    assert any('missing or negative prices: batch_input' in e for e in run(cfg)[0])


def test_a_model_the_plan_uses_but_the_config_lacks_fails(cfg):
    cfg['models'] = [m for m in cfg['models'] if m['id'] != 'claude-opus-5']
    assert any('claude-opus-5: named in 11 S5' in e for e in run(cfg)[0])


def test_a_retired_model_in_use_fails(cfg):
    model(cfg, 'claude-sonnet-5')['status'] = 'retired'
    errors = run(cfg)[0]
    assert any('retired, and still used' in e for e in errors)


def test_a_duplicate_id_fails(cfg):
    cfg['facts'].append(copy.deepcopy(fact(cfg, 'anthropic-batch')))
    assert any('used more than once' in e for e in run(cfg)[0])


def test_a_stale_row_warns_and_does_not_fail(cfg):
    errors, warnings = run(cfg, today=date(2027, 1, 15))
    assert errors == []
    assert sum('days old' in w for w in warnings) == len(cfg['models']) + len(cfg['facts'])


def test_a_fresh_row_does_not_warn(cfg):
    assert not any('days old' in w for w in run(cfg)[1])


def test_an_unconfirmed_rate_card_warns_and_a_confirmed_one_does_not(cfg):
    assert any(w.startswith('human_confirmation') for w in run(cfg)[1])
    cfg['human_confirmation']['prices_and_tier_caps'] = {'confirmed_by': 'reviewer', 'confirmed_on': date(2026, 9, 24)}
    assert not any(w.startswith('human_confirmation') for w in run(cfg)[1])


def test_a_near_retirement_floor_on_a_model_in_use_warns(cfg):
    warnings = run(cfg)[1]
    assert any(w.startswith('claude-haiku-4-5: used by') for w in warnings)
    # An unused model near its floor is not the plan's problem.
    assert not any(w.startswith('claude-fable-5-1') for w in warnings)


def test_github_actions_gets_annotations(monkeypatch, capsys):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    ck.main(['--today', '2026-09-24'])
    out = capsys.readouterr().out
    assert '::warning file=config/ai-models.yaml::human_confirmation' in out
