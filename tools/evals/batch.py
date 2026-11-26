"""The Batch API run: the seam where the model-dependent half of the evaluation plugs in (P6-S3-T09; 11-ai-features.md
S7 "Grading and cadence", S5).

11 S7: "Run the full set through the Batch API on every prompt-version change, model-ID change, taxonomy change, schema
change, or index rebuild that crosses a size threshold." What that run produces, per split:

  nl_search, facet_translation, abstention   F1's FacetQuery for the query (11 S4 step 1): for nl_search the facet
                                             query that filters and boosts the fused retrieval, for facet_translation
                                             the output macro-F1, over-constraint and the enum canary score, for
                                             abstention the intent and confidence the refusal contract reads.
  suite_build                                F2's synthesis over the retrieved entries (11 S2 F2).

What is built here:

  - every model id comes from config/ai-models.yaml by the `used_by` tag of 11 S5's table (F1, F2, self-eval-judge),
    never from a literal, and a row that is not `active` is refused (as ingest/triage/classifier.py does for triage);
  - `f1_request` shapes one Message Batches request per item: custom_id the item id, which golden ids already satisfy
    (^[a-zA-Z0-9_-]{1,64}$); params the model, MAX_TOKENS, the F1 system prompt, the query as the only user turn, and
    output_config.format the FacetQuery JSON Schema (schema/generated/facetquery.schema.json, P6-S3-T01). No thinking:
    11 S4 makes F1 one bounded extraction call, and the F1 row (claude-haiku-4-5) takes only budget_tokens. No
    sampling parameter, which API version 2026-10-21 answers with a 400 on every model; none of the four a batch
    refuses (stream, speed, fallbacks, max_tokens 0); no cache_control, because batch cache hits are best-effort and
    the F1 row's minimum cacheable prefix is 4,096 tokens;
  - the three HTTP calls over urllib, as tools/copilot/draft.py makes its one, so the harness depends on no SDK:
    POST /v1/messages/batches, GET /v1/messages/batches/{id} until processing_status is `ended`, and GET
    /v1/messages/batches/{id}/results, a JSONL file whose lines come back in any order and are matched by custom_id.
    The transport is injectable, so tests/evals/test_eval_harness.py holds the shapes with a fake and no test ever
    calls the API;
  - `parse_results` reads each line's result: `succeeded` with a message whose stop_reason is checked before its text
    is parsed (a refusal or max_tokens may not match the schema at all, 11 S6 G1), or errored, canceled or expired.

The API facts (endpoints, headers, custom_id's pattern, the result types, the parameters a batch refuses) were read
off https://platform.claude.com/docs/en/build-with-claude/batch-processing on 2026-11-25.

What refuses, and why the run refuses today with or without a key (`refusals`):

  - no ANTHROPIC_API_KEY in the environment. No key exists for this project yet; the run never asks for one and never
    reads one from anywhere but the environment;
  - no F1 prompt. The F1 call's system prompt has not been written (the F1 worker and its post-validator are
    P6-S3-T04's and P6-S3-T05's), and a run with an invented prompt would evaluate a prompt nobody ships;
  - no F2 synthesis for suite_build (P6-S5), and no rationale for the judge to score (`--judge`, P6-S6-T03's
    tools/evals/judge.py; 11 S7: a judge score never gates).

So the deterministic configurations are graded and published, and every model-dependent metric is reported as not
run, with these reasons, rather than as a number.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join('config', 'ai-models.yaml')
SCHEMA = os.path.join('schema', 'generated', 'facetquery.schema.json')
API_URL = 'https://api.anthropic.com/v1/messages/batches'
API_VERSION = '2026-10-21'
KEY = 'ANTHROPIC_API_KEY'
CUSTOM_ID = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
MAX_TOKENS = 4096                    # a FacetQuery is a few hundred tokens; the cap only guards a runaway answer
REFUSED_PARAMS = ('stream', 'speed', 'fallbacks', 'temperature', 'top_p', 'top_k')
RESULT_TYPES = ('succeeded', 'errored', 'canceled', 'expired')
FEATURE = {'nl_search': 'F1', 'facet_translation': 'F1', 'abstention': 'F1', 'suite_build': 'F2'}
JUDGE = 'self-eval-judge'
NOT_BUILT = {
    'F1': 'no F1 prompt exists to evaluate: the F1 call and its post-validator are P6-S3-T04 and P6-S3-T05, and a run '
          'with a prompt written here would grade a prompt nobody ships',
    'F2': 'no F2 synthesis exists to evaluate: the suite builder\'s synthesis is P6-S5',
    JUDGE: 'nothing to judge: the judge scores F2 rationales, which do not exist yet, and its harness is P6-S6-T03\'s '
           'tools/evals/judge.py; a judge score never gates (11 S7)',
}


class BatchError(Exception):
    """The run cannot be shaped or sent; the message says why."""


def model_for(user: str, root: str = ROOT) -> str:
    """The one active config/ai-models.yaml model whose used_by names `user` (11 S5: "Every prompt, cost estimator and
    eval run reads from it")."""
    from schema.taxonomy import read_yaml
    rows = [m for m in read_yaml(os.path.join(root, CONFIG))['models'] if user in (m.get('used_by') or [])]  # get-default: a row may name no user
    if len(rows) != 1:
        raise BatchError('%s names %d models used_by %s; exactly one must be' % (CONFIG, len(rows), user))
    if rows[0]['status'] != 'active':
        raise BatchError('%s is %s; 11 S5 moves the %s row before it is called' % (rows[0]['id'], rows[0]['status'],
                                                                                   user))
    return rows[0]['id']


def facetquery_schema(root: str = ROOT) -> dict:
    with open(os.path.join(root, SCHEMA), encoding='utf-8') as fh:
        return json.load(fh)


# ---- the requests -------------------------------------------------------------------------------------------------

def f1_request(item: dict, model: str, system: str, schema: dict) -> dict:
    """One Message Batches request for one golden item (module docstring)."""
    if not CUSTOM_ID.match(item['id']):
        raise BatchError('%r is not a valid custom_id (^[a-zA-Z0-9_-]{1,64}$)' % item['id'])
    return {'custom_id': item['id'], 'params': {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': system,
        'messages': [{'role': 'user', 'content': item['query']}],
        'output_config': {'format': {'type': 'json_schema', 'schema': schema}},
    }}


def body(requests: list[dict]) -> dict:
    """The POST body, refusing duplicate custom_ids and any parameter a batch or API version 2026-10-21 rejects."""
    ids = [r['custom_id'] for r in requests]
    if len(set(ids)) != len(ids):
        raise BatchError('a custom_id repeats: every request in a batch needs its own')
    bad = sorted({p for r in requests for p in REFUSED_PARAMS if p in r['params']})
    if bad or any(r['params'].get('max_tokens', 0) < 1 for r in requests):   # get-default: a missing cap is refused like 0
        raise BatchError('a batch request may not set %s, and needs max_tokens >= 1' % ', '.join(bad or REFUSED_PARAMS))
    return {'requests': requests}


# ---- what refuses ---------------------------------------------------------------------------------------------------

@dataclass
class Status:
    """Whether the model-dependent run can go, and if not every reason, per feature."""
    key: bool
    models: dict[str, str]           # feature -> model id, or the BatchError text
    refusals: dict[str, list[str]]   # feature -> reasons; empty when it can run

    def as_dict(self) -> dict:
        return {'ran': False, 'api_key_present': self.key, 'models': self.models, 'not_run': self.refusals}


def status(features: list[str], env: dict | None = None, root: str = ROOT,
           built: dict[str, bool] | None = None) -> Status:
    """For each feature, its model from config/ai-models.yaml and every reason it cannot run now. `built` says which
    features have a prompt or harness to evaluate; none has today (NOT_BUILT)."""
    env = os.environ if env is None else env
    built = built or {}
    key = bool(env.get(KEY))                           # get-default: an unset key is the usual case
    models, refusals = {}, {}
    for f in features:
        reasons = [] if key else ['%s is not set: the Batch API run needs a key, and none exists for this project yet'
                                  % KEY]
        try:
            models[f] = model_for(f, root)
        except BatchError as e:
            models[f] = str(e)
            reasons.append(str(e))
        if not built.get(f):                           # get-default: a feature not named is not built
            reasons.append(NOT_BUILT[f])
        refusals[f] = reasons
    return Status(key, models, refusals)


# ---- the transport ----------------------------------------------------------------------------------------------

class Transport:
    """The Message Batches HTTP calls over urllib. `opener` is injectable: the tests pass a fake."""

    def __init__(self, key: str, opener=None):
        if not key:
            raise BatchError('%s is not set' % KEY)
        self.key, self.opener = key, opener or urllib.request.urlopen

    def call(self, method: str, url: str, payload: dict | None = None) -> bytes:
        from ingest.http.policy import refuse
        refuse(url)                                    # 07 S10.1: no-collect and forbidden hold for every code path
        headers = {'x-api-key': self.key, 'anthropic-version': API_VERSION}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['content-type'] = 'application/json'
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with self.opener(req, timeout=120) as r:
            return r.read()


def submit(requests: list[dict], transport: Transport) -> dict:
    return json.loads(transport.call('POST', API_URL, body(requests)))


def wait(batch_id: str, transport: Transport, poll_seconds: float = 60, sleep=time.sleep) -> dict:
    """Poll until processing_status is `ended` (in_progress and canceling are the other two)."""
    while True:
        batch = json.loads(transport.call('GET', '%s/%s' % (API_URL, batch_id)))
        if batch['processing_status'] == 'ended':
            return batch
        sleep(poll_seconds)


def results(batch_id: str, transport: Transport) -> dict[str, dict]:
    return parse_results(transport.call('GET', '%s/%s/results' % (API_URL, batch_id)).decode('utf-8'))


def parse_results(jsonl: str) -> dict[str, dict]:
    """custom_id -> {type, output (the parsed JSON answer) or error}, from the results file's lines in any order."""
    out = {}
    for line in jsonl.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rid, result = row['custom_id'], row['result']
        if result['type'] not in RESULT_TYPES:
            raise BatchError('%s: unknown result type %r' % (rid, result['type']))
        entry = {'type': result['type']}
        if result['type'] == 'succeeded':
            msg = result['message']
            if msg['stop_reason'] in ('refusal', 'max_tokens'):    # check before parsing (11 S6 G1)
                entry.update(type='errored', error='stop_reason %s' % msg['stop_reason'])
            else:
                text = ''.join(b['text'] for b in msg['content'] if b['type'] == 'text')
                try:
                    entry['output'] = json.loads(text)
                except ValueError as e:
                    entry.update(type='errored', error='the answer is not JSON: %s' % e)
        elif result['type'] == 'errored':
            entry['error'] = json.dumps(result['error'], sort_keys=True)
        out[rid] = entry
    return out
