#!/usr/bin/env python3
"""OpenRouter system-entity enrichment (P5-S6-T07; 06 S3.16, 07 S5.1).

    python -m ingest.adapters.openrouter --fixture tests/ingest/fixtures/system-enrichment/openrouter
    bench ingest openrouter --dry-run [--fixture PATH]

One GET of https://openrouter.ai/api/v1/models (no auth), conditional on the ETag the last run saw. The endpoint
sent none on 2026-10-10, so If-None-Match is sent only when there is one to send, and an unchanged list is told
apart by its normalised hash instead (07 S1.5): pricing is volatile and stripped before hashing, since 06 S3.16
puts prices in metrics/ only ("a price in the citable core would be wrong within a month").

A model is its canonical_slug, with every route OpenRouter lists under it: on 2026-10-10, 86 of the 458 ids were
`:batch` routes sharing their base model's slug, so the slug is the source key and an id is a route of it (ids
are unique; a repeated id is drift).

Resolution is an exact dictionary lookup (step 2; 07 S5.1: "Fuzzy matching is a crosswalk-authoring tool, not a
per-row operation"): the canonical_slug, then each route's id, against the systems' external ids and the alias table
(ingest/resolve.py's Index.exact). Nothing is normalised and nothing is parsed, because in a model list a near
miss is a different model.

What a model becomes:
  - matched: a discovery candidate under data/_discovery/openrouter/ suggesting what 06 S3.16 maps -- the
    OpenRouter id as external_ids.openrouter, hugging_face_id as external_ids.huggingface, `created` as an
    availability date (not a release date), context_length, supported_parameters (a field 06 S11 requests) --
    for a curator to promote; and its prices as a metrics observation;
  - unmatched: an Unresolved, a human task (step 3). Never a System: constraint 5, "this is not a model
    directory", so the task asks for an alias only where a result claim needs the model.

When it breaks (06 S3.16). A list more than 10% shorter than the last accepted run is a semantic anomaly: labelled
needs-scrutiny, nothing is classed gone, and the baseline stays. A response without `data`, or a model without one
of the keys read, is schema drift, a hard fail.

The licence. OpenRouter states no licence for the list; until 06 S8.4's checklist reads its terms the adapter takes
the restrictive default (unlicensed): its output is discovery candidates, observations and human tasks, never a
record in the citable core, and no raw body is kept.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from ingest.adapters.base import Adapter, Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.backoff import Response, retry  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

NAME = 'openrouter'
VERSION = '0.1.0'
URL = 'https://openrouter.ai/api/v1/models'
LICENCE = 'NOASSERTION'
LICENCE_CLASS = 'unlicensed'             # the restrictive default until 06 S8.4 reads OpenRouter's terms
ATTRIBUTION = 'OpenRouter, model list (https://openrouter.ai/api/v1/models)'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
DISCOVERY = 'data/_discovery/openrouter'
KEYS = frozenset({'id', 'canonical_slug', 'hugging_face_id', 'name', 'created', 'context_length', 'pricing',
                  'supported_parameters'})   # every key read; a model without one is drift
VOLATILE = ('pricing',)
ANOMALY_DROP = 0.10
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
SchemaDrift = drift.DriftError


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class FetchError(Exception):
    pass


class NetworkTransport:
    """GET over urllib behind the fetcher's gate."""

    def __init__(self, timeout: int = 60, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.gate = gate or policy.gate()

    def _once(self, url, headers):
        if not url.startswith('https://'):
            raise ValueError('%s: HTTPS only' % url)
        self.gate.admit(url)
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json', **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:             # a 304 comes back here
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


def canonical(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def stable(model: dict) -> dict:
    return {k: v for k, v in model.items() if k not in VOLATILE}


def fetch_models(transport, state: dict) -> list[dict] | None:
    """The model list, or None on a 304. Conditional on the ETag where the last run saw one."""
    etag = state.get('etag')                            # get-default: the endpoint may send none
    r = transport.get(URL, {'If-None-Match': etag} if etag else {})   # get-default: an HTTP GET with request headers
    if r.status == 304:
        return None
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (URL, r.status))
    state['etag'] = header(r.headers, 'ETag')
    state['bytes'] = len(r.body)
    try:
        doc = json.loads(r.body)
    except ValueError as e:
        raise SchemaDrift('%s: not JSON (%s)' % (URL, e)) from None
    models = doc.get('data') if isinstance(doc, dict) else None   # get-default: a missing key is drift, below
    if not isinstance(models, list) or not models:
        raise SchemaDrift('%s: no `data` list of models' % URL)
    for m in models:
        missing = sorted(KEYS - set(m)) if isinstance(m, dict) else sorted(KEYS)
        if missing:
            raise SchemaDrift('%s: model %s lacks %s' % (URL, m.get('id') if isinstance(m, dict) else m, missing))
    ids = [m['id'] for m in models]
    if len(set(ids)) != len(ids):
        raise SchemaDrift("%s: a model id repeats; ids are a slug's routes and must be unique" % URL)
    return models


def by_slug(models: list[dict]) -> dict[str, list[dict]]:
    """canonical_slug -> its routes, the base route (no `:` variant) first."""
    out = {}
    for m in models:
        out.setdefault(m['canonical_slug'], []).append(m)
    return {s: sorted(ms, key=lambda m: (':' in m['id'], m['id'])) for s, ms in out.items()}


def released_on(created) -> str | None:
    if isinstance(created, (int, float)) and not isinstance(created, bool) and created > 0:
        return datetime.fromtimestamp(created, timezone.utc).date().isoformat()
    return None


def normalise(payload: Payload, resolvers: dict) -> tuple[list[Draft], list[Unresolved]]:
    """A discovery candidate for a model the alias table names exactly, else a human task. Pure."""
    routes = payload.doc
    m, slug = routes[0], routes[0]['canonical_slug']
    idx = resolvers['system']
    hit = idx.exact(slug) or next((h for h in (idx.exact(r['id']) for r in routes) if h is not None), None)
    if hit is None:
        return [], [Unresolved(
            slug, 'system', slug, 'no-match',
            human_task=('OpenRouter lists %r (%s; routes %s), and no System or alias is exactly it. Write an alias in '
                        'data/aliases/systems.yaml only if a result claim needs this model -- constraint 5: this is '
                        'not a model directory, and the feed never creates a System.'
                        % (slug, m['name'][:80], ', '.join(r['id'] for r in routes))))]
    system = hit.entity.split(':', 1)[1]
    fetched = iso(payload.fetched_at)

    def suggest(field, value, rationale):
        return {'field': field, 'value': value, 'adapter': NAME, 'adapter_version': VERSION, 'source_url': URL,
                'fetched_at': fetched, 'confidence': hit.score, 'rationale': rationale}
    suggested = [suggest('external_ids.openrouter', m['id'], '06 S3.16: OpenRouter id')]
    if m['hugging_face_id']:
        suggested.append(suggest('external_ids.huggingface', m['hugging_face_id'],
                                 '06 S3.16: the free join key across OpenRouter and the Hub'))
    if released_on(m['created']):
        suggested.append(suggest('versions[].available_on', released_on(m['created']),
                                 '06 S3.16: `created` is an availability date on OpenRouter, not a release date'))
    if isinstance(m['context_length'], int) and m['context_length'] > 0:
        suggested.append(suggest('versions[].context_length', m['context_length'], '06 S3.16: context_length'))
    if m['supported_parameters']:
        suggested.append(suggest('versions[].supported_parameters', sorted(m['supported_parameters']),
                                 '06 S3.16/S11: whether temperature was settable is a comparability input'))
    body = {
        'candidate_id': 'cand-or-%s' % re.sub(r'[^a-z0-9]+', '-', slug.lower()).strip('-'),
        'discovered_via': NAME,
        'discovered_at': fetched,
        'identity': {'system': system, 'version': hit.version, 'matched_on': hit.raw, 'openrouter_id': m['id'],
                     'routes': [r['id'] for r in routes], 'canonical_slug': slug, 'name': m['name'][:280]},
        '_suggested': suggested,
    }
    ingestion = {'adapter': NAME, 'adapter_version': VERSION, 'source_url': URL, 'fetched_at': fetched,
                 'sha256_normalised': payload.sha256_normalised, 'source_licence': LICENCE,
                 'licence_class': LICENCE_CLASS, 'source_attribution': ATTRIBUTION}
    return [Draft('system', None, Path(DISCOVERY) / ('%s.yaml' % body['candidate_id']), body, 'new', ingestion,
                  hit.score, labels=['ingest:%s' % NAME])], []


class OpenRouter(Adapter):
    name, version, licence, licence_class, attribution = NAME, VERSION, LICENCE, LICENCE_CLASS, ATTRIBUTION
    expected_yield = (200, 900)         # 06 S3.16 observed 444 models; 458 on 2026-10-10
    tier = 2
    raw_retainable = False
    volatile_fields = VOLATILE

    def __init__(self, transport=None, now=utcnow):
        self.transport, self.now, self.models = transport, now, None

    def discover(self, state):
        self.models = fetch_models(self.transport, state)
        for slug, routes in sorted(by_slug(self.models or []).items()):
            yield Candidate(slug, 'system', 'https://openrouter.ai/%s' % routes[0]['id'], {'routes': routes})

    def fetch(self, candidate, state=None):
        routes = candidate.hint['routes']
        return Payload(candidate, b'', 'application/json', 200, self.now(), None, None,
                       canonical([stable(m) for m in routes]), False, doc=routes)

    def normalise(self, payload, resolver=None):
        return normalise(payload, resolver)


def new_state() -> dict:
    return {'version': 1, 'etag': None, 'bytes': None, 'count': None, 'hashes': {}}


def resolvers_from(root: str | None = None) -> dict:
    from ingest.resolve import ROOT as R, Index
    return {'system': Index.load('system', root or R)}


def run(adapter: OpenRouter, state: dict | None = None, resolvers: dict | None = None) -> dict:
    """Fetch, check, resolve. Writes nothing; `state` is updated in place for the caller to persist."""
    state = state if state is not None else new_state()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(adapter.now()), 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'unresolved': 0, 'unresolved_items': [],
              'matched': 0, 'errors': [], 'snapshot': None, 'anomalies': [], 'labels': [], 'observations': [],
              'proposals': [], 'documents': []}
    try:
        candidates = list(adapter.discover(state))
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    except (FetchError, policy.PolicyRefusal) as e:
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(adapter.now()))
        return report
    if adapter.models is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    before, now = state.get('count'), len(adapter.models)   # get-default: a cold run has no baseline
    if before and now < before * (1 - ANOMALY_DROP):
        report['anomalies'].append('the list holds %d models, down from %d (-%.0f%%); nothing is gone'
                                   % (now, before, 100 * (before - now) / before))
        report['labels'] = ['needs-scrutiny']
    if resolvers is None:
        resolvers = resolvers_from()
    hashes = {}
    for cand in candidates:
        report['candidates_seen'] += 1
        payload = adapter.fetch(cand)
        report['observations'] += [{'canonical_slug': m['canonical_slug'], 'id': m['id'], 'pricing': m['pricing']}
                                   for m in payload.doc]
        drafts, unresolved = adapter.normalise(payload, resolvers)
        for u in unresolved:
            report['unresolved'] += 1
            report['unresolved_items'].append({'source_key': u.source_key, 'field': u.field, 'human_task': u.human_task})
        for d in drafts:
            report['matched'] += 1
            hashes[cand.source_key] = payload.sha256_normalised
            held = state['hashes'].get(cand.source_key)  # get-default: a model the state has not matched before
            change = 'new' if held is None else 'no-change' if held == payload.sha256_normalised else 'field-change'
            report['drafts'][change] += 1
            if change != 'no-change':
                report['documents'].append({'path': d.path.as_posix(), 'change_class': change, **d.payload,
                                            'ingestion': d.ingestion})
    report['snapshot'] = {'name': 'OpenRouter models', 'url': URL, 'retrieved_at': report['started_at'],
                          'artefact_sha256': canonical(sorted(hashes.items())), 'artefact_bytes': state['bytes']}
    state['hashes'] = hashes
    if not report['anomalies']:
        state['count'] = now                             # an anomalous run never becomes the baseline
    report['finished_at'] = iso(adapter.now())
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture')
    a = p.parse_args(argv)
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport()
    report = run(OpenRouter(transport), new_state())
    print(json.dumps({k: v for k, v in report.items() if k not in ('documents', 'observations', 'unresolved_items')},
                     indent=2, default=str))
    return 1 if report['status'] == 'hard-fail' else 0


if __name__ == '__main__':
    sys.exit(main())
