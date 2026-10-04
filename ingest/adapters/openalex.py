#!/usr/bin/env python3
"""The OpenAlex adapter: institution and ROR resolution for Organization records (P4-S2-T06; 06 S3.10, 12 S6).

    bench ingest openalex --dry-run --limit 20                        # live, OPENALEX_API_KEY from the env
    bench ingest openalex --dry-run --fixture tests/fixtures/openalex  # offline, recorded responses

06 S3.10's conclusion bounds what this adapter is for: "use OpenAlex for institution/ROR resolution and topic
concepts, where it is genuinely good", and never for titles or citation counts (a live probe found a record with
the right DOI, the wrong title and a count off by orders of magnitude). So it reads one thing: for each curated
Organization with no `ror`, the OpenAlex institution of the same name, and proposes that institution's ROR id,
Wikidata id and country as a patch to the record.

It proposes a patch only when exactly one institution's name -- its display_name without OpenAlex's trailing
"(Country)", or one of its alternative names or acronyms -- equals the organisation's name once normalised
(ingest/resolve.py's rule). Anything else is an Unresolved: several equal names, or none, with the top
institutions offered as suggestions and never applied (04 S10). A field the record already holds is never
overwritten; a disagreement with it is reported, not resolved.

The allowance, measured with a key on 2026-10-04 (P4-S2-T06's step 2; 06 S3.10 had three numbers):
X-RateLimit-Limit 10000 credits a day, X-RateLimit-Limit-USD 1. A singleton lookup by id cost 0; a filtered
list call and a search call each cost 10 credits ($0.001) -- search is not dearer than a list, whatever the
docs say. So ~1,000 list calls a day, which this adapter spends one per organisation. Every run records the
X-RateLimit-* headers of its last response in its report, so a change in the meter shows up on the next run.

The key (OPENALEX_API_KEY) is added inside the network transport and nowhere else: URLs in reports, fixtures and
errors never carry it. Without a key the API still answers, on a smaller budget.
"""
from __future__ import annotations

import glob
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ingest.adapters.base import Draft, Unresolved
from ingest.http.backoff import Response, retry
from ingest.resolve import normalise

NAME = 'openalex'
VERSION = '0.1.0'
API = 'https://api.openalex.org'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
LICENCE = 'CC0-1.0'
MIN_INTERVAL = 0.2          # seconds between requests: polite, and far inside any per-second limit
PER_PAGE = 5
# Only the fields this adapter reads: the same 10 credits, a fraction of the bytes
SELECT = 'id,display_name,display_name_alternatives,display_name_acronyms,ror,ids,country_code'
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_COUNTRY_TAIL = re.compile(r'\s*\([^()]*\)\s*$')


class NetworkTransport:
    """GET over urllib with 07 S4.2's retry policy. The API key is appended here, and only here."""

    def __init__(self, key: str | None = None, timeout: int = 60, clock=time.monotonic, sleep=time.sleep):
        self.key, self.timeout, self.clock, self.sleep = key, timeout, clock, sleep
        self._not_before = 0.0

    def _once(self, url, headers):
        wait = self._not_before - self.clock()
        if wait > 0:
            self.sleep(wait)
        full = url + ('&' if '?' in url else '?') + urllib.parse.urlencode({'api_key': self.key}) if self.key else url
        req = urllib.request.Request(full, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json', **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        self._not_before = resp.received_at + MIN_INTERVAL
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


def institutions_url(name: str) -> str:
    """The one list call per organisation (10 credits): institutions whose display name matches."""
    return '%s/institutions?%s' % (API, urllib.parse.urlencode(
        {'filter': 'display_name.search:%s' % name.replace(',', ' '), 'per-page': PER_PAGE, 'select': SELECT}))


def candidates(root: str = ROOT):
    """(org id, name, record) for every curated Organization with no ror (stubs are not enriched)."""
    from schema.taxonomy import read_yaml
    for path in sorted(glob.glob(os.path.join(root, 'data', 'organizations', '*.yaml'))):
        rec = read_yaml(path)
        if not rec.get('ror'):
            yield rec['id'], rec['name'], rec


def labels(inst: dict) -> set[str]:
    """The names an institution answers to, normalised: display name with and without its "(Country)" tail,
    alternatives and acronyms."""
    names = [inst.get('display_name') or '', _COUNTRY_TAIL.sub('', inst.get('display_name') or '')]
    names += list(inst.get('display_name_alternatives') or []) + list(inst.get('display_name_acronyms') or [])
    return {normalise(n) for n in names if n}


def patch_from(inst: dict) -> dict:
    """The Organization fields an institution supplies: ror, wikidata (a Q-id) and country (ISO alpha-2)."""
    out = {}
    if inst.get('ror'):
        out['ror'] = inst['ror']
    wd = ((inst.get('ids') or {}).get('wikidata') or '').rstrip('/').rsplit('/', 1)[-1]  # get-default: optional ids
    if re.fullmatch(r'Q[1-9]\d*', wd):
        out['wikidata'] = wd
    if re.fullmatch(r'[A-Z]{2}', inst.get('country_code') or ''):
        out['country'] = inst['country_code']
    return out


def normalise_org(org_id: str, name: str, record: dict, results: list[dict]):
    """(drafts, unresolved) for one organisation, from the institutions OpenAlex returned for its name."""
    want = normalise(name)
    exact = [i for i in results if want in labels(i)]
    suggestions = [(i.get('ror') or i.get('id'), 1.0 if i in exact else 0.0) for i in results[:3]]
    if len(exact) != 1:
        reason = 'ambiguous-match' if exact else 'no-match'
        return [], [Unresolved(
            source_key='org:%s' % org_id, field='organization.ror', observed=name, reason=reason,
            suggestions=suggestions,
            human_task=('%d OpenAlex institutions are named %r; set ror on data/organizations/%s.yaml by hand '
                        '(06 S3.10)' % (len(exact), name, org_id)) if exact else
                       ('No OpenAlex institution is named %r; set ror by hand from ror.org, or leave it null '
                        '(06 S3.10)' % (name,)))]
    inst = exact[0]
    patch = patch_from(inst)
    clashes = {k: (record.get(k), v) for k, v in patch.items() if record.get(k) not in (None, v)}
    patch = {k: v for k, v in patch.items() if record.get(k) is None}
    unresolved = [Unresolved(
        source_key='org:%s' % org_id, field='organization.%s' % k, observed=str(v[1]), reason='policy',
        human_task='%s holds %s %r and OpenAlex says %r; a curator decides (a held field is never overwritten)'
                   % (org_id, k, v[0], v[1])) for k, v in sorted(clashes.items())]
    if not patch:
        return [], unresolved
    return [Draft('organization', org_id, Path('data/organizations/%s.yaml' % org_id),
                  patch, 'field-change',
                  {'source_adapter': NAME, 'adapter_version': VERSION, 'source_url': inst.get('id'),
                   'source_licence': LICENCE, 'source_record_id': inst.get('id'),
                   'matched_display_name': inst.get('display_name')},
                  1.0)], unresolved


def validate_patch(draft, record: dict) -> str | None:
    from pydantic import ValidationError

    from schema.entities import Organization
    try:
        Organization.model_validate({**record, **draft.payload})
    except ValidationError as e:
        return 'organization %s: %s' % (draft.entity_id, ' '.join(str(e).split())[:300])
    return None


def run(transport, *, limit: int | None = None, root: str = ROOT, now=lambda: datetime.now(timezone.utc)) -> dict:
    """One dry run: candidates, one list call each, proposals. Writes nothing."""
    started = now().strftime('%Y-%m-%dT%H:%M:%SZ')
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': started, 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'unresolved': 0, 'errors': [],
              'snapshot': None, 'proposals': [], 'allowance': {}}
    for i, (org_id, name, record) in enumerate(candidates(root)):
        if limit is not None and i >= limit:
            break
        report['candidates_seen'] += 1
        r = transport.get(institutions_url(name), {})  # get-default: an HTTP GET with request headers, not a lookup
        report['allowance'] = {k: v for k, v in (r.headers.items() if hasattr(r.headers, 'items') else r.headers)
                               if k.lower().startswith('x-ratelimit')}
        if r.status == 429:
            report['status'] = 'soft-fail'
            report['errors'].append('429 from OpenAlex: the daily budget is spent; the next run resumes (06 S3.10)')
            break
        if r.status != 200:
            report['status'] = 'hard-fail'
            report['errors'].append('%s: HTTP %d' % (institutions_url(name), r.status))
            break
        results = json.loads(r.body).get('results') or []
        drafts, unresolved = normalise_org(org_id, name, record, results)
        report['unresolved'] += len(unresolved)
        for d in drafts:
            report['drafts'][d.change_class] += 1
            why = validate_patch(d, record)
            if why:
                report['errors'].append('invalid draft: %s' % why)
            report['proposals'].append('%s -> %r (%s): %s' % (
                org_id, d.ingestion['matched_display_name'], d.ingestion['source_record_id'],
                ', '.join('%s=%s' % kv for kv in sorted(d.payload.items()))))
        for u in unresolved:
            report['proposals'].append('%s: unresolved (%s) %s' % (org_id, u.reason, u.human_task))
    if report['errors'] and report['status'] == 'ok':
        report['status'] = 'hard-fail'
    elif report['status'] == 'ok' and not any(report['drafts'].values()):
        report['status'] = 'no-change'
    report['finished_at'] = now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return report


def key_from_env() -> str | None:
    return os.environ.get('OPENALEX_API_KEY') or None
