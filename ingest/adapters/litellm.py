#!/usr/bin/env python3
"""LiteLLM price-file system enrichment, held under the licence veto (P5-S6-T07; 06 S3.16, S1.2, 07 S5.1).

    python -m ingest.adapters.litellm --fixture tests/ingest/fixtures/system-enrichment/litellm
    bench ingest litellm --dry-run [--fixture PATH]

One GET of BerriAI/litellm's model_prices_and_context_window.json (2.7 MB on 2026-10-10) from
raw.githubusercontent.com, conditional on its ETag (06 S3.16: "the failure mode is a silent ETag change with no
content change, which costs a download and nothing else"; so a changed ETag over an unchanged hash is no change).

Each key -- a model name as LiteLLM routes it, `gpt-4o` or `openrouter/anthropic/...` -- is resolved by exact
dictionary lookup against the systems' external ids and the alias table (Index.exact); the template entry
`sample_spec` is not a model. An unmatched key is an Unresolved, a human task; a System is never created.

The veto (step 4). The repository's licence reads NOASSERTION ("Other": MIT, with an enterprise directory under its
own terms), and 06 S8.4 lists BerriAI/litellm among the questions P5-S6-T01 must settle by correspondence. Until it
does, the run holds everything it produced: no draft, no observation and no human task leaves the report
(`held`), nothing is written, and no raw body is kept (07 S4.4). The resolution still runs, so the report says
what the feed would give once the row closes.

A response that is not a mapping of model entries, or one in which no entry names a litellm_provider, is schema
drift, a hard fail.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from ingest.adapters.base import Adapter, Candidate, Payload, Unresolved  # noqa: E402
from ingest.adapters.openrouter import NetworkTransport, FetchError  # noqa: E402,F401
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

NAME = 'litellm'
VERSION = '0.1.0'
URL = 'https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json'
LICENCE = 'NOASSERTION'                  # GitHub reads the repository's licence as "Other"
LICENCE_CLASS = 'unlicensed'
ATTRIBUTION = 'BerriAI, LiteLLM model_prices_and_context_window.json (https://github.com/BerriAI/litellm)'
TEMPLATE = 'sample_spec'
VETO = ('BerriAI/litellm is an open row of 06 S8.4: until P5-S6-T01 settles it by correspondence, nothing this '
        'feed produces leaves the report (06 S1.2)')
SchemaDrift = drift.DriftError


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def fetch_prices(transport, state: dict) -> tuple[dict | None, str | None, int]:
    """(the entries, their sha256, the body's bytes), or (None, None, 0) on a 304 or an unchanged body under a
    new ETag."""
    etag = state.get('etag')                            # get-default: a cold run has none to send
    r = transport.get(URL, {'If-None-Match': etag} if etag else {})   # get-default: an HTTP GET with request headers
    if r.status == 304:
        return None, None, 0
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (URL, r.status))
    state['etag'] = header(r.headers, 'ETag')
    sha = hashlib.sha256(r.body).hexdigest()
    if sha == state.get('sha256'):                      # get-default: a cold run has no hash
        return None, None, 0                            # a silent ETag change: a download, and nothing else
    try:
        doc = json.loads(r.body)
    except ValueError as e:
        raise SchemaDrift('%s: not JSON (%s)' % (URL, e)) from None
    if not isinstance(doc, dict) or not all(isinstance(v, dict) for v in doc.values()):
        raise SchemaDrift('%s: not a mapping of model entries' % URL)
    entries = {k: v for k, v in doc.items() if k != TEMPLATE}
    if not any('litellm_provider' in v for v in entries.values()):
        raise SchemaDrift('%s: no entry names a litellm_provider; the file changed shape' % URL)
    return entries, sha, len(r.body)


def normalise(payload: Payload, resolvers: dict) -> tuple[dict | None, list[Unresolved]]:
    """(the price observation for a matched model, or None) and the human task for an unmatched one. Pure."""
    key, entry = payload.candidate.source_key, payload.doc
    hit = resolvers['system'].exact(key)
    if hit is None:
        return None, [Unresolved(
            key, 'system', key, 'no-match',
            human_task=('LiteLLM prices %r (provider %s), and no System or alias is exactly it. Write an alias only if '
                        'a result claim needs this model; the feed never creates a System (06 S3.16).'
                        % (key, entry.get('litellm_provider') or 'unnamed')))]   # get-default: the provider only labels the task
    obs = {'system': hit.entity.split(':', 1)[1], 'litellm_key': key}
    for f in ('input_cost_per_token', 'output_cost_per_token', 'max_input_tokens', 'max_output_tokens', 'mode'):
        if f in entry:
            obs[f] = entry[f]
    return obs, []


class LiteLLM(Adapter):
    name, version, licence, licence_class, attribution = NAME, VERSION, LICENCE, LICENCE_CLASS, ATTRIBUTION
    expected_yield = (0, 50)           # matched models only; most keys are routes no claim names
    tier = 2
    raw_retainable = False

    def __init__(self, transport=None, now=utcnow):
        self.transport, self.now, self.entries, self.sha, self.bytes = transport, now, None, None, 0

    def discover(self, state):
        self.entries, self.sha, self.bytes = fetch_prices(self.transport, state)
        for key in sorted(self.entries or {}):
            yield Candidate(key, 'system', None, {'entry': self.entries[key]})

    def fetch(self, candidate, state=None):
        entry = candidate.hint['entry']
        sha = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        return Payload(candidate, b'', 'application/json', 200, self.now(), None, None, sha, False, doc=entry)

    def normalise(self, payload, resolver=None):
        return normalise(payload, resolver)


def new_state() -> dict:
    return {'version': 1, 'etag': None, 'sha256': None}


def run(adapter: LiteLLM, state: dict | None = None, resolvers: dict | None = None) -> dict:
    """Fetch, check, resolve -- and hold it all under the veto. Writes nothing."""
    state = state if state is not None else new_state()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(adapter.now()), 'status': 'ok',
              'candidates_seen': 0, 'matched': 0, 'unresolved': 0, 'errors': [], 'snapshot': None,
              'drafts': {c: 0 for c in ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')},
              'held': {'observations': 0, 'unresolved': 0, 'reason': VETO}, 'observations': [], 'unresolved_items': [],
              'documents': [], 'proposals': []}
    try:
        candidates = list(adapter.discover(state))
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    except (FetchError, policy.PolicyRefusal) as e:
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(adapter.now()))
        return report
    if adapter.entries is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    if resolvers is None:
        from ingest.adapters.openrouter import resolvers_from
        resolvers = resolvers_from()
    for cand in candidates:
        report['candidates_seen'] += 1
        obs, unresolved = adapter.normalise(adapter.fetch(cand), resolvers)
        if obs is not None:
            report['matched'] += 1
            report['held']['observations'] += 1         # held: not reported, not written
        report['unresolved'] += len(unresolved)
        report['held']['unresolved'] += len(unresolved)
    report['proposals'].append('%d of %d LiteLLM keys match a System exactly; all held: %s'
                               % (report['matched'], report['candidates_seen'], VETO))
    report['snapshot'] = {'name': 'LiteLLM model prices', 'url': URL, 'retrieved_at': report['started_at'],
                          'artefact_sha256': adapter.sha, 'artefact_bytes': adapter.bytes}
    state['sha256'] = adapter.sha
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
    report = run(LiteLLM(transport), new_state())
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}, indent=2, default=str))
    return 1 if report['status'] == 'hard-fail' else 0


if __name__ == '__main__':
    sys.exit(main())
