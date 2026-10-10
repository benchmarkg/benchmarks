#!/usr/bin/env python3
"""The HELM adapter, behind the licence veto (P5-S6-T05; 06 S3.5, S1.2, 07 S4.4).

    python -m ingest.adapters.helm --fixture tests/ingest/fixtures/helm     # offline
    bench ingest helm --dry-run [--fixture PATH]

HELM publishes everything in an anonymous, listable GCS bucket, crfm-helm-public, one prefix per suite (lite,
classic, mmlu, medhelm, ...), each with benchmark_output/releases/v<x.y.z>/. 06 S3.5 calls run_specs.json "the
prize": every run's adapter_spec, the evaluation conditions almost nobody else publishes.

The licence. HELM's code is Apache-2.0; the bucket's data states no licence, and "a publicly readable bucket is
permission to read, not automatically permission to redistribute". Until CRFM answers in writing (P5-S6-T01), 06
S3.5 lets the adapter be built and run with its output in data/_discovery/helm/ under 06 S1.2's veto. So:

  - no score is read: runs.json, the score rows, is never requested, so no HELM number exists to reach the
    citable core;
  - every draft is a discovery candidate under data/_discovery/helm/ (never published, built or counted);
  - licence_class is unlicensed and raw_retainable is False (07 S4.4): no body is kept in the raw store;
  - HELM's prompt text -- instructions, prefixes, suffixes -- is never copied; only condition values are.

The fetch, listing first (step 1). For each suite: list its releases, take the newest by version, list that
release's objects, and compare run_specs.json's generation and size with the state before downloading it. An
unchanged object is not fetched. A download is by generation (an immutable object version), and its size and MD5
must match the listing; HELM stores run_specs.json gzip-encoded, so the bytes are checked as stored, then
decompressed. A suite with no releases/ prefix is data, not an error (06 S3.5); a 403 on the bucket is a
hard fail ("the access model changed and the licence conversation just became urgent").

The key set (step 2). Every run spec's adapter_spec key set must be one of KEY_SETS, the five shapes the bucket
held on 2026-10-10 (HELM versions add keys over time; `classic`, the oldest, predates model_deployment and the
chain-of-thought keys). Anything else -- which is what a rename looks like -- is schema drift, a hard fail: "a key
computed from silently-missing fields is worse than no key at all". A mapped key that a known older shape lacks is
recorded as unknown (null), never defaulted. So is the run spec's own top-level key set.

The mapping (step 3, 06 S3.5's table), one discovery candidate per (suite, scenario class):

    max_train_instances            EvalConditions.shots
    chain_of_thought_prefix        EvalConditions.chain_of_thought: "" is a KNOWN off (false), not a null;
                                   a missing key is unknown (null)
    temperature                    EvalConditions.sampling.temperature
    num_outputs                    EvalConditions.n_samples
    max_eval_instances             EvalConditions.subset_used, "first N evaluation instances" -- 06 S3.5's
                                   subset_size, which the schema does not have; material either way
    method                         kept as `method`: 06 S3.5's output_mode, which the schema does not have
    model_deployment               ResultClaim.serving_provider: the deployment's host, where it is not the model's
                                   own organisation (a first-party API is no serving provider)
    model                          the System a claim would name, kept raw (nothing is resolved in discovery)
    metric_specs[].args.names      Metric refs
    scenario_spec.class_name       Benchmark.external_ids.helm_scenario
    num_train_trials, num_trials   kept as facts; EvalConditions has no field for them

Each distinct condition set is validated as an EvalConditions record (its id content-derived, 07 S1.4) and listed
with the runs that used it. Step 4's other half -- moving these out of discovery -- waits on P5-S6-T01.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import base64  # noqa: E402
import gzip  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from collections import Counter  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from ingest.adapters.base import BulkArchiveAdapter, Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.backoff import Response, retry  # noqa: E402

NAME = 'helm'
VERSION = '0.1.0'
BUCKET = 'crfm-helm-public'
API = 'https://storage.googleapis.com/storage/v1/b/%s/o' % BUCKET
LICENCE = 'NOASSERTION'                  # the bucket's data states no licence (06 S3.5)
LICENCE_CLASS = 'unlicensed'
ATTRIBUTION = 'Stanford CRFM, Holistic Evaluation of Language Models (HELM), gs://crfm-helm-public, https://crfm.stanford.edu/helm/'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
DISCOVERY = 'data/_discovery/helm'
RELEASES = 'benchmark_output/releases/'
RUN_SPECS = 'run_specs.json'
STALE_DAYS = 183                         # 06 S3.5: "no new release for two quarters" is a fact worth surfacing
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
SchemaDrift = drift.DriftError

_BASE = ('chain_of_thought_prefix', 'chain_of_thought_suffix', 'global_prefix', 'global_suffix', 'input_prefix',
         'input_suffix', 'instance_prefix', 'instructions', 'max_eval_instances', 'max_tokens', 'max_train_instances',
         'method', 'model', 'model_deployment', 'multi_label', 'num_outputs', 'num_train_trials', 'num_trials',
         'output_prefix', 'output_suffix', 'reference_prefix', 'reference_suffix', 'sample_train', 'stop_sequences',
         'substitutions', 'temperature')
# Every adapter_spec key set the bucket held on 2026-10-10, by the suites that carried it.
KEY_SETS = {
    frozenset(_BASE): 'lite, medhelm, safety, seahelm, torr and nine more (26 keys)',
    frozenset(_BASE) | {'output_mapping_pattern', 'reference_prefix_characters'}: 'arabic, arabic-enterprise (28 keys)',
    frozenset(_BASE) | {'eval_splits'}: 'mmlu (27 keys)',
    frozenset(_BASE) - {'chain_of_thought_prefix', 'chain_of_thought_suffix'}: 'cleva, finance, instruct (24 keys)',
    frozenset(_BASE) - {'chain_of_thought_prefix', 'chain_of_thought_suffix', 'global_suffix', 'model_deployment',
                        'num_trials'}: 'classic v0.4.0 (21 keys)',
}
TOP_KEY_SETS = (frozenset({'name', 'scenario_spec', 'adapter_spec', 'metric_specs', 'data_augmenter_spec', 'groups'}),
                frozenset({'name', 'scenario_spec', 'adapter_spec', 'metric_specs', 'data_augmenter_spec', 'groups',
                           'annotators'}))
# The keys the mapping reads, present in every known shape. The others it reads are present in some.
MAPPED = ('max_train_instances', 'temperature', 'num_outputs', 'max_eval_instances', 'method', 'model')
VERSION_PREFIX = re.compile(r'/v(\d+)\.(\d+)\.(\d+)/$')
SHORT = 80                              # a scenario argument longer than this is prose, not an identifier


class FetchError(Exception):
    """A request answered something the adapter cannot use, or bytes that do not match their listing."""


class Forbidden(Exception):
    """403 on the bucket: 06 S3.5's hard fail."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---- the transport ----------------------------------------------------------------------------------------------

class NetworkTransport:
    """GET over urllib behind the fetcher's gate (ingest/policy.yaml paces storage.googleapis.com)."""

    def __init__(self, timeout: int = 120, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.gate = gate or policy.gate()

    def _once(self, url, headers):
        if not url.startswith('https://'):
            raise ValueError('%s: the bucket is read over HTTPS only' % url)
        self.gate.admit(url)
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


def list_url(prefix: str, token: str | None = None) -> str:
    q = [('prefix', prefix), ('delimiter', '/')] + ([('pageToken', token)] if token else [])
    return '%s?%s' % (API, urllib.parse.urlencode(q))


def media_url(name: str, generation: str) -> str:
    return '%s/%s?alt=media&generation=%s' % (API, urllib.parse.quote(name, safe=''), generation)


def _json(transport, url: str):
    r = transport.get(url, {})                              # get-default: an HTTP GET with request headers
    if r.status == 403:
        raise Forbidden('%s answered 403: the bucket\'s access model changed (06 S3.5)' % url)
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (url, r.status))
    return json.loads(r.body)


def listing(transport, prefix: str) -> tuple[list[str], list[dict]]:
    """(sub-prefixes, objects) directly under `prefix`, every page."""
    prefixes, items, token = [], [], None
    while True:
        doc = _json(transport, list_url(prefix, token))
        prefixes += doc.get('prefixes') or []               # get-default: a listing with no sub-prefixes omits the key
        items += doc.get('items') or []                     # get-default: as above, for objects
        token = doc.get('nextPageToken')                    # get-default: the last page carries none
        if not token:
            return prefixes, items


def newest(prefixes: list[str]) -> str | None:
    versions = [(tuple(int(x) for x in m.groups()), p) for p in prefixes if (m := VERSION_PREFIX.search(p))]
    return max(versions)[1] if versions else None


# ---- the bundle --------------------------------------------------------------------------------------------------

def check_specs(suite: str, specs) -> None:
    """Step 2: every run spec's top-level and adapter_spec key sets are known ones, before anything is read."""
    if not isinstance(specs, list) or not specs:
        raise SchemaDrift('%s/%s: not a non-empty list of run specs' % (suite, RUN_SPECS))
    for s in specs:
        if not isinstance(s, dict) or frozenset(s) not in TOP_KEY_SETS:
            got = sorted(s) if isinstance(s, dict) else type(s).__name__
            raise SchemaDrift('%s/%s: a run spec\'s keys are %s, not a known set' % (suite, RUN_SPECS, got))
        keys = frozenset(s['adapter_spec'])
        if keys not in KEY_SETS:
            near = min(KEY_SETS, key=lambda k: len(k ^ keys))
            raise SchemaDrift('%s/%s: run spec %s has an adapter_spec key set HELM has not published before -- '
                              'missing %s, new %s (nearest: %s). A renamed key would write nulls into '
                              'comparability_key; read HELM\'s changelog and add the set to KEY_SETS (06 S3.5).'
                              % (suite, RUN_SPECS, s['name'], sorted(near - keys), sorted(keys - near), KEY_SETS[near]))


class Bucket:
    """One run: each suite's newest release, its run_specs.json where that changed, and what was not there."""

    def __init__(self, suites: dict, retrieved_at: datetime, no_releases: list[str], unchanged: list[str]):
        self.suites, self.retrieved_at = suites, retrieved_at
        self.no_releases, self.unchanged = no_releases, unchanged

    def groups(self) -> dict[str, list[dict]]:
        """'<suite>/<scenario class>' -> its run specs."""
        out = {}
        for suite, s in sorted(self.suites.items()):
            for spec in s['specs']:
                out.setdefault('%s/%s' % (suite, spec['scenario_spec']['class_name']), []).append(spec)
        return out

    def payload_for(self, candidate: Candidate) -> Payload:
        suite, cls = candidate.source_key.split(':', 1)[1].split('/', 1)
        s = self.suites[suite]
        specs = [x for x in s['specs'] if x['scenario_spec']['class_name'] == cls]
        doc = {'suite': suite, 'release': s['release'], 'class_name': cls, 'specs': specs, 'object': s['object']}
        canon = json.dumps(specs, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return Payload(candidate=candidate, body=b'', content_type='application/json', http_status=200,
                       fetched_at=self.retrieved_at, etag=None, last_modified=None,
                       sha256_normalised=hashlib.sha256(canon).hexdigest(), from_cache=False, doc=doc)

    def snapshot(self) -> dict:
        objs = {s['object']['name']: s['object']['generation'] for s in self.suites.values()}
        return {'name': 'gs://%s' % BUCKET, 'url': 'https://storage.googleapis.com/%s/' % BUCKET,
                'retrieved_at': iso(self.retrieved_at),
                'artefact_sha256': hashlib.sha256(json.dumps(sorted(objs.items())).encode()).hexdigest(),
                'artefact_bytes': sum(int(s['object']['size']) for s in self.suites.values())}


def fetch_bucket(transport, state: dict, now=utcnow) -> Bucket | None:
    """Steps 1 and 2. None when no suite's newest run_specs.json moved."""
    suites_seen = state.setdefault('objects', {})
    roots, _ = listing(transport, '')
    suites, no_releases, unchanged = {}, [], []
    liveness = state.setdefault('liveness', {})
    for root in sorted(roots):
        suite = root.rstrip('/')
        releases, _ = listing(transport, root + RELEASES)
        latest = newest(releases)
        if latest is None:
            no_releases.append(suite)                       # 06 S3.5: a missing release prefix is data
            continue
        _, items = listing(transport, latest)
        spec = next((i for i in items if i['name'] == latest + RUN_SPECS), None)
        if spec is None:
            no_releases.append(suite)
            continue
        liveness[suite] = {'release': latest[len(root + RELEASES):].strip('/'),
                           'updated': max(i['updated'] for i in items)[:10]}
        held = suites_seen.get(spec['name'])                # get-default: an object the state has not seen
        if held == [spec['generation'], spec['size']]:
            unchanged.append(suite)
            continue
        r = transport.get(media_url(spec['name'], spec['generation']), {})   # get-default: an HTTP GET, not a lookup
        if r.status == 403:
            raise Forbidden('%s answered 403 (06 S3.5)' % spec['name'])
        if r.status != 200:
            raise FetchError('%s answered HTTP %d' % (spec['name'], r.status))
        if len(r.body) != int(spec['size']) or base64.b64encode(hashlib.md5(r.body).digest()).decode() != spec['md5Hash']:
            raise FetchError('%s generation %s does not match its listing (size or MD5)' % (spec['name'], spec['generation']))
        body = r.body
        if spec.get('contentEncoding') == 'gzip':          # get-default: most objects carry no content encoding
            body = gzip.decompress(body)                    # stored gzipped; the size and MD5 are of what is stored
        specs = json.loads(body)
        check_specs(suite, specs)
        suites[suite] = {'release': liveness[suite]['release'], 'specs': specs,
                         'object': {'name': spec['name'], 'generation': spec['generation'], 'size': spec['size']}}
    if not suites:
        return None
    return Bucket(suites, now(), no_releases, unchanged)


# ---- the mapping -------------------------------------------------------------------------------------------------

def conditions(a: dict) -> dict:
    """One run's EvalConditions fields. A key the shape lacks is unknown (absent here), never defaulted."""
    out = {}
    if isinstance(a['max_train_instances'], int) and a['max_train_instances'] >= 0:
        out['shots'] = a['max_train_instances']
    if 'chain_of_thought_prefix' in a:
        out['chain_of_thought'] = a['chain_of_thought_prefix'] != ''        # "" is a known off, not a null
    if isinstance(a['temperature'], (int, float)) and not isinstance(a['temperature'], bool) and a['temperature'] >= 0:
        out['sampling'] = {'temperature': float(a['temperature'])}
    if isinstance(a['num_outputs'], int) and a['num_outputs'] >= 1:
        out['n_samples'] = a['num_outputs']
    if isinstance(a['max_eval_instances'], int) and a['max_eval_instances'] >= 1:
        out['subset_used'] = 'first %d evaluation instances (HELM max_eval_instances)' % a['max_eval_instances']
    return out


def conditions_id(fields: dict) -> str:
    """07 S1.4: a conditions id is content-derived, so a machine may mint it."""
    canon = json.dumps(fields, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'cond-%s' % hashlib.sha256(canon).hexdigest()[:12]


def serving_provider(a: dict) -> str | None:
    """The deployment's host where it is not the model's own organisation; None when unknown or first-party."""
    dep = a.get('model_deployment')                         # get-default: the 21-key shape has no model_deployment
    if not isinstance(dep, str) or '/' not in dep:
        return None
    host, owner = dep.split('/', 1)[0], str(a['model']).split('/', 1)[0]
    return None if host == owner else host


def normalise(payload: Payload) -> tuple[list[Draft], list[Unresolved]]:
    """One discovery candidate for a (suite, scenario class). Pure: the payload only."""
    from schema.conditions import EvalConditions
    doc = payload.doc
    key, cls, specs = payload.candidate.source_key, doc['class_name'], doc['specs']
    sets, unresolved = {}, []
    methods, evals, models, metrics, hosts, trials = Counter(), Counter(), set(), set(), Counter(), Counter()
    for s in specs:
        a = s['adapter_spec']
        fields = conditions(a)
        cid = conditions_id(fields)
        try:
            EvalConditions.model_validate({'id': cid, **fields})
        except Exception as e:                              # pydantic's ValidationError, whatever the field
            unresolved.append(Unresolved(s['name'], 'eval_conditions', json.dumps(fields, sort_keys=True), 'unparseable',
                                         human_task='HELM run %s maps to conditions that do not validate: %s'
                                                    % (s['name'], ' '.join(str(e).split())[:200])))
            continue
        entry = sets.setdefault(cid, {'id': cid, **fields, 'runs': 0})
        entry['runs'] += 1
        methods[a['method']] += 1
        evals[a['max_eval_instances']] += 1
        trials['%s/%s' % (a['num_train_trials'], a.get('num_trials'))] += 1   # get-default: the 21-key shape has no num_trials
        models.add(str(a['model']))
        host = serving_provider(a)
        if host:
            hosts[host] += 1
        for m in s['metric_specs']:
            for n in (m.get('args') or {}).get('names') or []:              # get-default: a metric spec may take no args
                metrics.add(str(n))
    fetched = iso(payload.fetched_at)
    url = 'https://storage.googleapis.com/%s/%s' % (BUCKET, doc['object']['name'])
    args = sorted({'%s=%s' % (k, v) for s in specs for k, v in (s['scenario_spec'].get('args') or {}).items()   # get-default: a scenario may take no args
                   if isinstance(v, (str, int, float, bool)) and len(str(v)) <= SHORT})

    def suggest(field, value, rationale):
        return {'field': field, 'value': value, 'adapter': NAME, 'adapter_version': VERSION, 'source_url': url,
                'fetched_at': fetched, 'confidence': 0.5, 'rationale': rationale}
    body = {
        'candidate_id': candidate_id(doc['suite'], cls),
        'discovered_via': NAME,
        'discovered_at': fetched,
        'identity': {
            'suite': doc['suite'],
            'release': doc['release'],
            'scenario_class': cls,
            'scenario_args': args[:40],
            'run_specs': {'url': url, 'generation': doc['object']['generation']},
            'runs': len(specs),
            'models': len(models),
            'metrics': sorted(metrics),
            'methods': dict(sorted(methods.items())),
            'max_eval_instances': {str(k): v for k, v in sorted(evals.items(), key=lambda kv: str(kv[0]))},
            'train_trials_and_trials': dict(sorted(trials.items())),
            'serving_providers': dict(sorted(hosts.items())),
            'conditions': [sets[c] for c in sorted(sets)],
            'licence': 'open: no HELM score is read until P5-S6-T01 settles the terms (06 S3.5)',
        },
        '_suggested': [
            suggest('external_ids.helm_scenario', cls, '06 S3.5: scenario_spec.class_name'),
            suggest('execution.runnable_via', ['helm'], 'HELM runs this scenario'),
        ],
    }
    ingestion = {'adapter': NAME, 'adapter_version': VERSION, 'source_url': url, 'fetched_at': fetched,
                 'sha256_normalised': payload.sha256_normalised, 'source_licence': LICENCE,
                 'licence_class': LICENCE_CLASS, 'source_attribution': ATTRIBUTION}
    return [Draft('conditions', None, Path(DISCOVERY) / ('%s.yaml' % body['candidate_id']), body, 'new', ingestion,
                  1.0, labels=['ingest:%s' % NAME])], unresolved


def candidate_id(suite: str, cls: str) -> str:
    """lite + helm.benchmark.scenarios.commonsense_scenario.OpenBookQA -> cand-helm-lite-commonsense-openbookqa."""
    parts = cls.split('.')
    short = '-'.join(p for p in (parts[-2].removesuffix('_scenario') if len(parts) > 1 else '', parts[-1]) if p)
    return 'cand-helm-%s-%s' % (re.sub(r'[^a-z0-9]+', '-', suite.lower()).strip('-'),
                                re.sub(r'[^a-z0-9]+', '-', short.lower()).strip('-'))


class Helm(BulkArchiveAdapter):
    """06 S3.5's adapter on 07 S1.2's contract: listings, then the changed run_specs.json, one record per scenario."""

    name, version, licence, licence_class, attribution = NAME, VERSION, LICENCE, LICENCE_CLASS, ATTRIBUTION
    expected_yield = (20, 400)       # scenario classes across the released suites
    tier = 2                          # 06 S8.2: second wave
    raw_retainable = False            # 07 S4.4: an unlicensed source keeps no raw body

    def __init__(self, transport=None, now=utcnow):
        self.transport, self.now, self.bundle = transport, now, None

    def fetch_bundle(self, state: dict) -> Bucket | None:
        return fetch_bucket(self.transport, state, self.now)

    def enumerate(self, bucket: Bucket):
        for key in sorted(bucket.groups()):
            yield Candidate('helm:%s' % key, 'conditions', None, {})

    def normalise(self, payload, resolver=None):
        return normalise(payload)


# ---- one run -------------------------------------------------------------------------------------------------------

def new_state() -> dict:
    return {'version': 1, 'objects': {}, 'liveness': {}}


def run(adapter: Helm, state: dict | None = None) -> dict:
    """List, diff, fetch the changed run specs, check them, normalise. Writes nothing; `state` is updated in place."""
    state = state if state is not None else new_state()
    started = adapter.now()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(started), 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'unresolved': 0, 'unresolved_items': [],
              'errors': [], 'snapshot': None, 'suites': {}, 'no_releases': [], 'unchanged': [], 'liveness': {},
              'proposals': [], 'documents': []}
    try:
        bucket = adapter.fetch_bundle(state)
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    except (Forbidden, FetchError, policy.PolicyRefusal) as e:
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(adapter.now()))
        return report
    report['liveness'] = dict(state['liveness'])
    stale = (started - timedelta(days=STALE_DAYS)).date().isoformat()
    report['proposals'] += ['%s: newest release %s, last written %s, over two quarters ago -- a liveness fact '
                            '(06 S3.5), not a scraper bug' % (s, v['release'], v['updated'])
                            for s, v in sorted(state['liveness'].items()) if v['updated'] < stale]
    if bucket is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    adapter.bundle = bucket
    report['snapshot'] = bucket.snapshot()
    report['no_releases'], report['unchanged'] = bucket.no_releases, bucket.unchanged
    for suite, s in sorted(bucket.suites.items()):
        report['suites'][suite] = {'release': s['release'], 'run_specs': len(s['specs']),
                                   'key_sets': sorted({KEY_SETS[frozenset(x['adapter_spec'])] for x in s['specs']})}
    for cand in adapter.enumerate(bucket):
        report['candidates_seen'] += 1
        drafts, unresolved = adapter.normalise(adapter.fetch(cand))
        for u in unresolved:
            report['unresolved'] += 1
            report['unresolved_items'].append({'source_key': u.source_key, 'field': u.field, 'human_task': u.human_task})
        for d in drafts:
            report['drafts'][d.change_class] += 1
            report['documents'].append({'path': d.path.as_posix(), **d.payload, 'ingestion': d.ingestion})
    for suite, s in bucket.suites.items():
        state['objects'][s['object']['name']] = [s['object']['generation'], s['object']['size']]
    report['finished_at'] = iso(adapter.now())
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture', help='a recorded-response directory in place of the network')
    a = p.parse_args(argv)
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport()
    report = run(Helm(transport), new_state())
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}, indent=2, default=str))
    return 1 if report['status'] == 'hard-fail' else 0


if __name__ == '__main__':
    sys.exit(main())
