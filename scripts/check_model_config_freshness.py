#!/usr/bin/env python3
"""Check config/ai-models.yaml: every row sourced and dated, prices internally consistent, and a
CI warning when anything is stale (P6-S2-T01; 11-ai-features.md S5).

    python scripts/check_model_config_freshness.py              # the CI step
    python scripts/check_model_config_freshness.py --strict     # warnings fail too
    python scripts/check_model_config_freshness.py --online     # also find each quote on its source

Failures (exit 1) -- the file cannot be trusted as it stands:
  - a row (each `models` and `facts` entry) without an https `source_url` or a `verified_on` date,
    or dated in the future, or an id used twice;
  - a model without every price, or a price that contradicts the rate card's own arithmetic:
    batch is 50% of base, a 5-minute cache write 1.25x input, a 1-hour write 2x, and a cache read
    the multiplier the `anthropic-cache-multipliers` row states for that model;
  - a model 11 S5's "Recommended model per feature" table names that is missing here, or retired.

Warnings (exit 0; `::warning::` annotations under GitHub Actions) -- true today, due for a look:
  - a row whose `verified_on` is older than `stale_after_days`;
  - `human_confirmation` not yet filled in: the budget rests on prices a person has not re-read;
  - a model in use whose `retirement_not_before` is within 90 days, or which is deprecated.
"""
import argparse
import html
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, 'config', 'ai-models.yaml')
PLAN_11 = os.path.join(ROOT, '_plan', '11-ai-features.md')
PRICES = ('input', 'output', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'batch_input', 'batch_output')
STATUSES = {'active', 'deprecated', 'retired'}
RETIREMENT_WINDOW = 90  # days
UA = 'UAIBI/0.1 (+https://github.com/intelligence-benchmark/benchmarks)'


def load(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    try:
        from ruamel.yaml import YAML
        return YAML(typ='safe').load(text)
    except ImportError:
        import yaml
        return yaml.safe_load(text)


def as_date(v):
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def urls(row):
    u = row.get('source_url')
    return u if isinstance(u, list) else [u]


def multiplier(text):
    m = re.fullmatch(r'\s*([0-9.]+)x(?: input)?\s*', str(text))
    return float(m.group(1)) if m else None


def plan_models(path):
    """Model ids 11 S5's per-feature table names, in backticks."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    start = text.index('### Recommended model per feature')
    end = text.index('### ', start + 10)
    return sorted(set(re.findall(r'`(claude-[a-z0-9-]+)`', text[start:end])))


def check(cfg, today, plan_ids):
    errors, warnings = [], []
    if not isinstance(cfg, dict) or not cfg.get('models') or not cfg.get('facts'):
        return ['ai-models.yaml needs non-empty `models` and `facts` lists'], []
    stale_after = cfg.get('stale_after_days')
    if not isinstance(stale_after, int) or stale_after <= 0:
        errors.append('stale_after_days must be a positive integer')
        stale_after = 92
    models, facts = cfg['models'], cfg['facts']
    rows = [('model', r) for r in models] + [('fact', r) for r in facts]
    ids = [r.get('id') for _, r in rows]
    for dup in sorted({i for i in ids if ids.count(i) > 1}, key=str):
        errors.append('%s: id used more than once' % dup)

    for kind, r in rows:
        rid = r.get('id') or '<%s without id>' % kind
        for u in urls(r):
            if not (isinstance(u, str) and u.startswith('https://')):
                errors.append('%s: source_url %r is not an https URL' % (rid, u))
        d = as_date(r.get('verified_on'))
        if d is None:
            errors.append('%s: verified_on %r is not a date' % (rid, r.get('verified_on')))
        elif d > today:
            errors.append('%s: verified_on %s is in the future' % (rid, d))
        elif (today - d).days > stale_after:
            warnings.append('%s: verified_on %s is %d days old (stale after %d); re-read %s'
                            % (rid, d, (today - d).days, stale_after, urls(r)[0]))
        if kind == 'fact' and 'value' not in r:
            errors.append('%s: a fact row without a value' % rid)

    exceptions, default_read = {}, None
    mult = next((f for f in facts if f.get('id') == 'anthropic-cache-multipliers'), None)
    if mult is None:
        errors.append('anthropic-cache-multipliers: the row the cache-read check reads is missing')
    else:
        default_read = multiplier(mult['value'].get('cache_read'))
        exceptions = {k: multiplier(v) for k, v in (mult['value'].get('cache_read_exceptions') or {}).items()}

    by_id = {}
    for m in models:
        mid = m.get('id')
        by_id[mid] = m
        if m.get('status') not in STATUSES:
            errors.append('%s: status %r is not one of %s' % (mid, m.get('status'), sorted(STATUSES)))
        p = m.get('price_usd_per_mtok')
        if not isinstance(p, dict):
            errors.append('%s: no price_usd_per_mtok' % mid)
            continue
        missing = [k for k in PRICES if not isinstance(p.get(k), (int, float)) or p.get(k) < 0]
        if missing:
            errors.append('%s: missing or negative prices: %s' % (mid, ', '.join(missing)))
            continue
        if not isinstance(m.get('min_cacheable_tokens'), int) or m['min_cacheable_tokens'] <= 0:
            errors.append('%s: min_cacheable_tokens must be a positive integer' % mid)

        def expect(field, want, why):
            if abs(p[field] - want) > 1e-9:
                errors.append('%s: %s is %s but %s gives %s' % (mid, field, p[field], why, round(want, 6)))
        expect('batch_input', p['input'] * 0.5, 'the 50% batch discount')
        expect('batch_output', p['output'] * 0.5, 'the 50% batch discount')
        expect('cache_write_5m', p['input'] * 1.25, 'the 1.25x 5-minute write')
        expect('cache_write_1h', p['input'] * 2, 'the 2x 1-hour write')
        read = exceptions.get(mid, default_read)
        if read is not None:
            expect('cache_read', p['input'] * read, 'the %sx cache-read multiplier' % read)

        used = bool(m.get('used_by'))
        retire = as_date(m.get('retirement_not_before')) if m.get('retirement_not_before') else None
        if used and m.get('status') == 'retired':
            errors.append('%s: retired, and still used by %s' % (mid, ', '.join(m['used_by'])))
        elif used and m.get('status') == 'deprecated':
            warnings.append('%s: deprecated, and used by %s' % (mid, ', '.join(m['used_by'])))
        if used and retire and (retire - today).days <= RETIREMENT_WINDOW:
            warnings.append('%s: used by %s, and its retirement floor is %s (%d days); watch for a deprecation notice'
                            % (mid, ', '.join(m['used_by']), retire, (retire - today).days))

    for pid in plan_ids:
        if pid not in by_id:
            errors.append('%s: named in 11 S5 "Recommended model per feature" but has no row here' % pid)
        elif by_id[pid].get('status') == 'retired':
            errors.append('%s: named in 11 S5 but retired' % pid)

    hc = (cfg.get('human_confirmation') or {}).get('prices_and_tier_caps') or {}
    if not hc.get('confirmed_by') or not as_date(hc.get('confirmed_on')):
        warnings.append('human_confirmation: no person has yet confirmed the prices and tier caps '
                        'against the live rate card (P6-S2-T01 done_when)')
    elif (today - as_date(hc['confirmed_on'])).days > stale_after:
        warnings.append('human_confirmation: last confirmed %s, over %d days ago' % (hc['confirmed_on'], stale_after))
    return errors, warnings


def online(cfg):
    """Every `quote` must still be on one of its row's source pages."""
    errors, cache = [], {}
    for r in cfg['models'] + cfg['facts']:
        q = r.get('quote')
        if not q:
            continue
        found = False
        for u in urls(r):
            if u not in cache:
                try:
                    req = urllib.request.Request(u, headers={'User-Agent': UA})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        raw = resp.read().decode('utf-8', 'replace')
                    raw = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', raw, flags=re.S | re.I)
                    cache[u] = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', raw)))
                except OSError as e:
                    cache[u] = ''
                    errors.append('%s: %s could not be fetched: %s' % (r['id'], u, e))
            found = found or re.sub(r'\s+', ' ', q).strip() in cache[u]
        if not found:
            errors.append('%s: quote not found on its source: %r' % (r['id'], q[:70]))
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--config', default=CONFIG)
    ap.add_argument('--plan', default=PLAN_11, help='11-ai-features.md, for the per-feature model table')
    ap.add_argument('--today', type=date.fromisoformat, default=date.today())
    ap.add_argument('--strict', action='store_true', help='fail on warnings as well')
    ap.add_argument('--online', action='store_true', help='re-fetch sources and find every quote')
    a = ap.parse_args(argv)
    cfg = load(a.config)
    errors, warnings = check(cfg, a.today, plan_models(a.plan))
    if a.online and not errors:
        errors += online(cfg)
    gha = os.environ.get('GITHUB_ACTIONS') == 'true'
    for w in warnings:
        print(('::warning file=config/ai-models.yaml::%s' if gha else 'warning  %s') % w)
    for e in errors:
        print(('::error file=config/ai-models.yaml::%s' if gha else 'FAIL     %s') % e)
    n = len(cfg.get('models') or []) + len(cfg.get('facts') or []) if isinstance(cfg, dict) else 0
    print('check_model_config_freshness: %d rows, %d failure(s), %d warning(s)%s'
          % (n, len(errors), len(warnings), '; quotes re-found online' if a.online and not errors else ''))
    return 1 if errors or (a.strict and warnings) else 0


if __name__ == '__main__':
    sys.exit(main())
