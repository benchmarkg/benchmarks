"""The prioritised re-verification queue: `bench report staleness` (P5-S7-T05; 05 S7).

05 S7: "The re-verification queue is prioritised, because a flat 'oldest first' list wastes the scarcest
resource in the project":

    priority = staleness_days x volatility_weight x attention_weight

    volatility_weight:  active 1.0 | saturated 0.6 | deprecated 0.3 | dead 0.2 | retracted 0.1
    attention_weight:   1 + log10(1 + pageviews_30d)          # from privacy-preserving analytics
                        x 1.5 if the entry is cited in any published suite manifest
                        x 2.0 if any claim on it is disputed

Where each input comes from:

  staleness_days   days from curation.last_verified to `as_of`, as tools/build/freshness.py counts them (one
                   rule for the badge and the queue). An entry never verified counts from curation.added_on.
  volatility       the entry's `lifecycle`. 05 S7 weighs five values; taxonomy/lifecycle.yaml has ten lifecycle
                   terms and no `dead`. The other six are weighted beside their nearest named one, in VOLATILITY
                   below, and a lifecycle term with no weight fails the report rather than defaulting.
  pageviews_30d    the latest committed analytics/YYYY-MM.json on or before `as_of` (05 S2; 08: "a monthly
                   rollup ... committed to the repository as a non-core artifact"): the requests whose path is
                   the entry's page or under it, from its `requests_by_path`. No file: 0 for every entry, and
                   the summary says so -- attention is then 1.0 rather than a guess.
  suite manifests  suites/**/*.yaml|json, each listing `benchmarks:` as ids or {id: ...}. None is published yet.
  disputed         any claim on the entry with an open dispute in data/disputes/ (schema/dispute.py's
                   claim_is_disputed: only an `open` dispute makes a claim disputed).

`--critical` keeps only 05 S7's last row: "> 730 days on an `active` benchmark: the entry enters `bench report
staleness --critical` and an issue opens automatically". The weekly re-verification issue (freshness.yml, every
Monday at 08:07) is `issue_body()` over the top of the queue, critical entries first.

The adapter table of 07 S9 (last_success, yield, band, unresolved backlog, secret countdown) is P5-S4-T03's half
of the same report and joins it when that task lands; this module owns the entry queue.

Deterministic: rows in a fixed order, no clock (as_of defaults to the data commit's date), so a re-run gives
byte-identical output and tests/golden/reverification.json pins it.
"""
from __future__ import annotations

import glob
import json
import math
import os
from datetime import date

REPORT = 'staleness'
VOLATILITY = {
    # 05 S7's five, verbatim
    'active': 1.0, 'saturated': 0.6, 'deprecated': 0.3, 'retracted': 0.1,
    # 05 S7's `dead` is taxonomy/lifecycle.yaml's `dormant`: no activity observed for long enough
    'dormant': 0.2,
    # the vocabulary's other five, each weighted as the named term it moves like
    'proposed': 1.0,          # pre-release: its fields move at least as fast as an active entry's
    'mature': 1.0,            # maintained and stable: alive, as active
    'under-revision': 1.0,    # being reissued right now: the most volatile state there is, capped at active
    'contaminated': 0.6,      # still run and reported, its numbers no longer move the frontier: as saturated
    'superseded': 0.3,        # a successor carries the work: as deprecated (09 S4.3 renders the two alike)
}
NO_LIFECYCLE = 1.0            # a kind with no lifecycle (none is curated yet) is not discounted
SUITE_FACTOR = 1.5
DISPUTE_FACTOR = 2.0
PAGE = {'benchmarks': '/benchmarks/{id}/', 'systems': '/systems/{id}/', 'organizations': '/orgs/{id}/',
        'metrics': '/metrics/{id}/'}
ISSUE_TOP = 25                # the weekly issue lists this many; the json report carries every entry
COLUMNS = ['rank', 'id', 'kind', 'lifecycle', 'last_verified', 'staleness_days', 'volatility_weight',
           'pageviews_30d', 'in_suite', 'disputed', 'attention_weight', 'priority', 'state', 'critical']


class ReportError(ValueError):
    pass


def _yaml(path):
    from schema.taxonomy import read_yaml
    return read_yaml(path)


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def lifecycle_terms(root: str) -> list[str]:
    """The lifecycle vocabulary: the tree's own, or the repository's for a data-only tree (a fixture corpus)."""
    path = os.path.join(root, 'taxonomy', 'lifecycle.yaml')
    doc = _yaml(path if os.path.exists(path) else os.path.join(REPO, 'taxonomy', 'lifecycle.yaml'))
    return [t['id'] for t in doc['terms'] if t.get('field', 'lifecycle') == 'lifecycle']  # get-default: a term names its field


def volatility(lifecycle: str | None) -> float:
    if lifecycle is None:
        return NO_LIFECYCLE
    if lifecycle not in VOLATILITY:
        raise ReportError('lifecycle %r has no volatility weight (05 S7); add it to VOLATILITY with its reason'
                          % lifecycle)
    return VOLATILITY[lifecycle]


def analytics(root: str, as_of: date) -> tuple[str | None, dict[str, int]]:
    """(the month read, its requests by path) from the latest analytics/YYYY-MM.json on or before as_of."""
    months = sorted(p for p in glob.glob(os.path.join(root, 'analytics', '*.json'))
                    if os.path.basename(p)[:7] <= as_of.isoformat()[:7])
    if not months:
        return None, {}
    with open(months[-1], encoding='utf-8') as f:
        doc = json.load(f)
    paths = doc.get('requests_by_path')                       # get-default: 15 C6 falls back to totals only
    return os.path.basename(months[-1])[:7], {str(k): int(v) for k, v in (paths or {}).items()}


def pageviews(kind: str, ident: str, by_path: dict[str, int]) -> int:
    page = PAGE.get(kind, '/%s/{id}/' % kind).format(id=ident)  # get-default: any other kind at /<kind>/<id>/
    return sum(n for p, n in by_path.items() if p == page or p == page.rstrip('/') or p.startswith(page))


def suite_members(root: str) -> tuple[int, set[str]]:
    """(manifests read, every benchmark id any of them lists)."""
    paths = sorted(p for ext in ('yaml', 'yml', 'json')
                   for p in glob.glob(os.path.join(root, 'suites', '**', '*.' + ext), recursive=True))
    ids: set[str] = set()
    for p in paths:
        if p.endswith('.json'):
            with open(p, encoding='utf-8') as f:
                doc = json.load(f)
        else:
            doc = _yaml(p)
        for b in (doc or {}).get('benchmarks') or []:          # get-default: a manifest may list none
            ident = b if isinstance(b, str) else (b.get('id') or b.get('benchmark')) if isinstance(b, dict) else None  # get-default: either key
            if ident:
                ids.add(str(ident).split('@', 1)[0])            # swe-bench@verified -> swe-bench (10 V10's basket)
    return len(paths), ids


def disputed_entries(root: str) -> set[str]:
    """Every entry id with a claim under an open dispute."""
    open_claims = set()
    for p in glob.glob(os.path.join(root, 'data', 'disputes', '**', '*.yaml'), recursive=True):
        d = _yaml(p)
        if isinstance(d, dict) and d.get('concerns') and d.get('status', 'open') == 'open':  # get-default: open by default (schema/dispute.py)
            open_claims.add(d['concerns'])
    if not open_claims:
        return set()
    out = set()
    for p in glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True):
        c = _yaml(p)
        if isinstance(c, dict) and c.get('id') in open_claims and c.get('benchmark'):
            out.add(c['benchmark'])
    return out


def attention(views: int, in_suite: bool, disputed: bool) -> float:
    return (1 + math.log10(1 + views)) * (SUITE_FACTOR if in_suite else 1.0) * (DISPUTE_FACTOR if disputed else 1.0)


def _staleness_days(fresh: dict, doc: dict, as_of: date) -> int:
    if fresh['days_since_verified'] is not None:
        return fresh['days_since_verified']
    from tools.build.liveness import as_date
    added = as_date(doc['curation'].get('added_on'))           # get-default: a draft may lack it
    return (as_of - added).days if added else 0


def build(root: str, as_of: date | None = None, critical: bool = False) -> dict:
    from tools.build import freshness as F
    from tools.build import ingest_health as H
    as_of = as_of or H.commit_date(root)
    terms = lifecycle_terms(root)
    unweighted = [t for t in terms if t not in VOLATILITY]
    if unweighted:
        raise ReportError('taxonomy/lifecycle.yaml terms with no volatility weight: %s' % ', '.join(unweighted))
    month, by_path = analytics(root, as_of)
    n_suites, suites = suite_members(root)
    disputed = disputed_entries(root)
    rows = []
    for rel, doc in F.entries(root):
        fresh = F.entry(rel, doc, {}, as_of)                   # source freshness plays no part in the formula
        days = _staleness_days(fresh, doc, as_of)
        vol = volatility(fresh['lifecycle'])
        views = pageviews(fresh['kind'], fresh['id'], by_path)
        in_suite, is_disputed = fresh['id'] in suites, fresh['id'] in disputed
        att = attention(views, in_suite, is_disputed)
        rows.append({
            'id': fresh['id'], 'kind': fresh['kind'], 'lifecycle': fresh['lifecycle'],
            'last_verified': fresh['last_verified'], 'staleness_days': days, 'volatility_weight': vol,
            'pageviews_30d': views, 'in_suite': in_suite, 'disputed': is_disputed,
            'attention_weight': round(att, 6), 'priority': round(days * vol * att, 4),
            'state': fresh['state'], 'critical': fresh['critical'], 'path': rel,
        })
    rows.sort(key=lambda r: (-r['priority'], -r['staleness_days'], r['id']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    shown = [r for r in rows if r['critical']] if critical else rows
    return {
        'report': REPORT + (' --critical' if critical else ''),
        'summary': {
            'as_of': as_of.isoformat(), 'entries': len(rows), 'shown': len(shown),
            'critical': sum(r['critical'] for r in rows),
            'red': sum(r['state'] == 'red' for r in rows), 'amber': sum(r['state'] == 'amber' for r in rows),
            'formula': 'priority = staleness_days x volatility_weight x attention_weight (05 S7)',
            'analytics_month': month,
            'analytics_note': None if month else 'no analytics/YYYY-MM.json committed: pageviews_30d is 0 for every entry',
            'suite_manifests': n_suites,
            'critical_after_days': F.CRITICAL_AFTER,
        },
        'columns': COLUMNS,
        'rows': [{c: r[c] for c in COLUMNS + ['path']} for r in shown],
    }


def issue_body(report: dict, top: int = ISSUE_TOP) -> str:
    """The weekly re-verification issue (freshness.yml): critical entries in full, then the top of the queue."""
    s, rows = report['summary'], report['rows']
    crit = [r for r in rows if r['critical']]
    out = ['Weekly re-verification queue, as of %s.' % s['as_of'], '',
           'Ordered by `%s`. Re-verifying an entry means opening its cited sources and confirming its fields, '
           'then setting `curation.last_verified` (05 S7).' % s['formula'], '',
           '- entries: %d (red %d, amber %d)' % (s['entries'], s['red'], s['amber']),
           '- critical, more than %d days on an active entry: %d' % (s['critical_after_days'], s['critical']),
           '- attention from: %s' % ('analytics/%s.json' % s['analytics_month'] if s['analytics_month']
                                     else 'no committed analytics yet, so every entry weighs 1.0'),
           '- published suite manifests: %d' % s['suite_manifests'], '']
    if crit:
        out += ['## Critical', '']
        out += ['- [ ] `%s` (%s), last verified %s, %d days: `%s`' % (r['id'], r['lifecycle'], r['last_verified'],
                                                                   r['staleness_days'], r['path']) for r in crit]
        out.append('')
    out += ['## Queue', '', '| # | entry | lifecycle | last verified | days | volatility | attention | priority |',
            '| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |']
    for r in rows[:top]:
        out.append('| %d | `%s` | %s | %s | %d | %s | %s | %s |' % (
            r['rank'], r['id'], r['lifecycle'] or 'not recorded', r['last_verified'] or 'never',
            r['staleness_days'], r['volatility_weight'], r['attention_weight'], r['priority']))
    if len(rows) > top:
        out.append('')
        out.append('%d more in `bench report staleness --format json`.' % (len(rows) - top))
    return '\n'.join(out) + '\n'
