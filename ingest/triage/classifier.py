#!/usr/bin/env python3
"""The arXiv triage classifier (P5-S5-T07; 06 S5.2, 11 S5).

    python -m ingest.triage.classifier --dry-run              # what would be sent, and its batch price
    python -m ingest.triage.classifier --submit               # one Message Batch for every untriaged candidate
    python -m ingest.triage.classifier --collect BATCH_ID     # write each result onto its candidate
    python -m ingest.triage.classifier --collect BATCH_ID --wait

The question. 06 S5.2: one rubric whose single question is "does this paper release an evaluation artifact, or
merely use one?" (ingest/triage/rubric.md, versioned by its first line and its sha256). The answer is
constrained output: a JSON object with exactly `label` (one of 06 S1.1's four), `rationale` and `score`.

What it may write, and where -- 06 S5.2's governing rule, "The AI layer is a lens, never a source":

  - only `triage` on a candidate under data/_discovery/: label and rationale from the model, its score (a ranking
    signal only, `score_status: unmeasured`, until P5-S5-T08 measures it), and the provenance this module adds
    -- the classifier's model id, the prompt version, when it decided, and expires_at (06 S1.1: discovered_at
    plus 90 days);
  - never a schema field, a domain, a capability or a description. An output carrying any key beyond the three
    is refused whole, as is a label outside the enum, an empty rationale, or a score outside [0, 1]; the
    candidate is left untouched and triages again next run;
  - never anything outside data/_discovery/: write() refuses the path before it opens a file.

The model and the call. The model id is config/ai-models.yaml's row whose `used_by` names `triage` (11 S5: "Every
prompt, cost estimator and eval run reads from it"); today claude-haiku-4-5, which 06 S5.2 chose. Its tentative
retirement floor is 2026-10-15, so the config check warns: moving the row is the maintainer's decision, and this
module follows it without a code change. Requests go through the Message Batches API -- triage is not
latency-sensitive and a batch is half price both ways -- and run without thinking: 06 S5.2 calls the task
"classification-shaped, constrained output, no thinking".

No prompt caching. 06 S5.2: "Say so in the adapter, or someone will add caching and wonder why the bill does not
move." The cacheable prefix is the rubric, a few hundred tokens; Haiku 4.5's minimum cacheable prefix is 4,096
(config/ai-models.yaml's min_cacheable_tokens). A cache write would never be read, so none is requested.

The input. Title and abstract only. A candidate holds its abstract's sha256, not its text (07 S8's 280-character
metadata-only limit); the text comes from the raw store, ingest/raw/arxiv-oai/abstracts/<sha256>.txt, and a text
that does not hash to the candidate's sha256 is refused rather than classified.

The SDK (`anthropic`, the optional `triage` extra) is imported only when the API is called, so the tests run a
fake client through the same code and nothing here needs a key to import.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import copy  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = os.path.join(ROOT, 'ingest', 'triage', 'rubric.md')
CONFIG = os.path.join(ROOT, 'config', 'ai-models.yaml')
ABSTRACTS = os.path.join(ROOT, 'ingest', 'raw', 'arxiv-oai', 'abstracts')
STATE = os.path.join(ROOT, 'ingest', 'state', 'triage.json')
DISCOVERY = 'data/_discovery/'
CANDIDATES = 'data/_discovery/arxiv'
USER = 'triage'                               # config/ai-models.yaml's used_by tag for this classifier

LABELS = ('likely-benchmark', 'uses-benchmark', 'survey', 'unclear')    # 06 S1.1's triage.label vocabulary
OUTPUT_KEYS = ('label', 'rationale', 'score')
MAX_RATIONALE = 280                           # 07 S8's metadata-only limit on any string in a draft
MAX_TOKENS = 512                              # ~120 output tokens expected (06 S5.2); a cut answer is refused
EXPIRY_DAYS = 90                              # 06 S1.1 / S5.4: a candidate expires discovered_at + 90 days
CUSTOM_ID = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')     # the Batches API's custom_id alphabet
SCHEMA = {
    'type': 'object',
    'properties': {
        'label': {'type': 'string', 'enum': list(LABELS)},
        'rationale': {'type': 'string'},
        'score': {'type': 'number'},
    },
    'required': list(OUTPUT_KEYS),
    'additionalProperties': False,
}


class TriageError(Exception):
    """A configuration or input the classifier will not run on."""


class Rejected(Exception):
    """One answer the classifier will not write: the candidate stays untriaged."""


# ---- configuration -------------------------------------------------------------------------------------------

def model_row(path: str = CONFIG) -> dict:
    """The one config/ai-models.yaml model whose used_by names the classifier."""
    from schema.taxonomy import read_yaml
    rows = [m for m in read_yaml(path)['models'] if USER in (m.get('used_by') or [])]   # get-default: a row may name no user
    if len(rows) != 1:
        raise TriageError('%s: %d models are used_by %s; exactly one must be' % (path, len(rows), USER))
    row = rows[0]
    if row['status'] != 'active':
        raise TriageError('%s is %s; 11 S5 moves the triage row before it is called' % (row['id'], row['status']))
    return row


def rubric(path: str = RUBRIC) -> tuple[str, str]:
    """(the rubric text, its version: the declared name plus the first 12 hex of its sha256)."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    m = re.match(r'<!-- rubric: ([a-z0-9.-]+) -->\n', text)
    if not m:
        raise TriageError('%s does not declare its version on its first line' % path)
    body = text[m.end():]
    return body, '%s+%s' % (m.group(1), hashlib.sha256(body.encode('utf-8')).hexdigest()[:12])


# ---- the request ---------------------------------------------------------------------------------------------

def request_params(model: str, system: str, title: str, abstract: str) -> dict:
    """One Messages request: the rubric as the system prompt, the title and abstract as the only user content.
    No cache_control (see the module docstring), no thinking, constrained output."""
    return {
        'model': model,
        'max_tokens': MAX_TOKENS,
        'system': system,
        'messages': [{'role': 'user', 'content': 'Title: %s\n\nAbstract: %s' % (title, abstract)}],
        'output_config': {'format': {'type': 'json_schema', 'schema': SCHEMA}},
    }


def abstract_for(identity: dict, store: str = ABSTRACTS) -> str:
    """The abstract text the candidate names by sha256, read from the raw store and checked against it."""
    want = identity['abstract']['sha256']
    path = os.path.join(store, want + '.txt')
    if not os.path.exists(path):
        raise Rejected('no abstract %s in %s' % (want[:12], store))
    with open(path, encoding='utf-8') as f:
        text = f.read()
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != want:
        raise Rejected('the stored abstract does not hash to %s' % want[:12])
    return text


def in_discovery(rel: str) -> bool:
    rel = rel.replace(os.sep, '/')
    return rel.startswith(DISCOVERY) and '..' not in rel.split('/')


def candidates(root: str = ROOT, tree: str = CANDIDATES) -> list[tuple[str, dict]]:
    """(repo-relative path, document) for every candidate file in the tree, sorted."""
    from schema.taxonomy import read_yaml
    out = []
    for path in sorted(glob.glob(os.path.join(root, *tree.split('/'), '*.yaml'))):
        rel = os.path.relpath(path, root).replace(os.sep, '/')
        out.append((rel, read_yaml(path)))
    return out


def build(cands, model: str, system: str, store: str = ABSTRACTS, again: bool = False):
    """(requests, skipped): one batch request per untriaged candidate whose abstract is in the store."""
    requests, skipped = [], []
    for rel, doc in cands:
        if not in_discovery(rel):
            skipped.append((rel, 'not under %s' % DISCOVERY))
            continue
        if doc.get('triage') and not again:                  # get-default: an arXiv candidate carries triage: null
            continue
        cid = doc['candidate_id']
        if not CUSTOM_ID.match(cid):
            skipped.append((rel, 'candidate_id %r is not a batch custom_id' % cid))
            continue
        try:
            text = abstract_for(doc['identity'], store)
        except Rejected as e:
            skipped.append((rel, str(e)))
            continue
        requests.append({'custom_id': cid, 'params': request_params(model, system, doc['identity']['title'], text)})
    return requests, skipped


# ---- the answer ----------------------------------------------------------------------------------------------

def parse(text: str) -> dict:
    """The model's answer, or Rejected. Exactly the three keys, each of its type; nothing else is read."""
    try:
        out = json.loads(text)
    except (TypeError, ValueError) as e:
        raise Rejected('not JSON: %s' % e) from None
    if not isinstance(out, dict):
        raise Rejected('not an object')
    if sorted(out) != sorted(OUTPUT_KEYS):
        raise Rejected('keys %s, not exactly %s: the model writes no other field' % (sorted(out), list(OUTPUT_KEYS)))
    if out['label'] not in LABELS:
        raise Rejected('label %r is not one of %s' % (out['label'], ', '.join(LABELS)))
    if not isinstance(out['rationale'], str) or not out['rationale'].strip():
        raise Rejected('no rationale')
    score = out['score']
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise Rejected('score %r is not in [0, 1]' % (score,))
    rationale = ' '.join(out['rationale'].split())
    if len(rationale) > MAX_RATIONALE:
        rationale = rationale[:MAX_RATIONALE - 1] + '…'
    return {'label': out['label'], 'rationale': rationale, 'score': round(float(score), 3)}


def message_text(message) -> str:
    """The text of a finished answer; a refusal, a cut answer or no text is Rejected."""
    if message.stop_reason != 'end_turn':
        raise Rejected('stop_reason %s' % message.stop_reason)
    texts = [b.text for b in message.content if b.type == 'text']
    if len(texts) != 1:
        raise Rejected('%d text blocks' % len(texts))
    return texts[0]


def apply(doc: dict, answer: dict, model: str, version: str, decided_at: datetime) -> dict:
    """A copy of the candidate with `triage` written, and nothing else changed."""
    out = copy.deepcopy(doc)
    discovered = datetime.strptime(doc['discovered_at'], '%Y-%m-%dT%H:%M:%SZ')
    out['triage'] = {
        'label': answer['label'],
        'rationale': answer['rationale'],
        'classifier': model,
        'classifier_prompt_version': version,
        'score': answer['score'],
        'score_status': 'unmeasured: a ranking signal only until P5-S5-T08 measures precision',
        'decided_at': decided_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': (discovered + timedelta(days=EXPIRY_DAYS)).strftime('%Y-%m-%d'),
    }
    return out


def write(root: str, rel: str, doc: dict) -> None:
    """Write a candidate back, through 07 S1.5's emitter. A path outside data/_discovery/ is refused first."""
    if not in_discovery(rel):
        raise TriageError('%s is outside %s: the triage classifier writes nothing else (06 S5.2)' % (rel, DISCOVERY))
    from ingest import emit
    text = emit.emit(doc, rel)
    with open(os.path.join(root, *rel.split('/')), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


# ---- the Batches API -----------------------------------------------------------------------------------------

def client():
    try:
        import anthropic
    except ImportError:
        raise TriageError('the SDK is not installed: uv sync --extra triage') from None
    return anthropic.Anthropic()


def submit(api, requests: list[dict]) -> str:
    """One batch for all of them. Each request is the shape the SDK's Request and MessageCreateParamsNonStreaming
    TypedDicts describe -- plain dicts at run time -- so no SDK type is needed to build them."""
    batch = api.messages.batches.create(requests=[{'custom_id': r['custom_id'], 'params': r['params']}
                                                  for r in requests])
    return batch.id


def wait(api, batch_id: str, every: float = 60.0, sleep=time.sleep):
    while True:
        batch = api.messages.batches.retrieve(batch_id)
        if batch.processing_status == 'ended':
            return batch
        sleep(every)


def collect(api, batch_id: str) -> dict:
    """custom_id -> the parsed answer, or Rejected/the batch result type when there is none. Results arrive in
    any order, so they are keyed by custom_id, never by position."""
    out = {}
    for result in api.messages.batches.results(batch_id):
        kind = result.result.type
        if kind != 'succeeded':
            out[result.custom_id] = Rejected('batch result %s' % kind)
            continue
        try:
            out[result.custom_id] = parse(message_text(result.result.message))
        except Rejected as e:
            out[result.custom_id] = e
    return out


def write_back(root: str, cands, answers: dict, model: str, version: str, now: datetime) -> dict:
    """Apply every answer to its candidate and write it. Returns counts and the reasons for every refusal."""
    report = {'written': 0, 'refused': {}, 'labels': {}}
    by_id = {doc['candidate_id']: (rel, doc) for rel, doc in cands}
    for cid, answer in sorted(answers.items()):
        if cid not in by_id:
            report['refused'][cid] = 'no candidate has this id'
            continue
        if isinstance(answer, Exception):
            report['refused'][cid] = str(answer)
            continue
        rel, doc = by_id[cid]
        write(root, rel, apply(doc, answer, model, version, now))
        report['written'] += 1
        report['labels'][answer['label']] = report['labels'].get(answer['label'], 0) + 1   # get-default: a first label
    return report


def _state(path: str = STATE) -> dict:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'batches': []}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--submit', action='store_true')
    g.add_argument('--collect', metavar='BATCH_ID')
    p.add_argument('--wait', action='store_true', help='with --collect: poll until the batch has ended')
    p.add_argument('--again', action='store_true', help='re-triage candidates that already carry a label')
    a = p.parse_args(argv)
    row = model_row()
    system, version = rubric()
    cands = candidates()
    if a.collect:
        api = client()
        if a.wait:
            wait(api, a.collect)
        report = write_back(ROOT, cands, collect(api, a.collect), row['id'], version,
                            datetime.now(timezone.utc).replace(microsecond=0))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    requests, skipped = build(cands, row['id'], system, again=a.again)
    price = row['price_usd_per_mtok']
    print('%d candidates, %d to triage with %s (prompt %s), %d skipped; batch price $%s in / $%s out per MTok'
          % (len(cands), len(requests), row['id'], version, len(skipped), price['batch_input'], price['batch_output']))
    for rel, why in skipped:
        print('  skipped %s: %s' % (rel, why))
    if a.dry_run or not requests:
        return 0
    batch_id = submit(client(), requests)
    state = _state()
    state['batches'].append({'id': batch_id, 'model': row['id'], 'prompt_version': version, 'requests': len(requests),
                             'submitted_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
    with open(STATE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write('\n')
    print('submitted batch %s; collect with --collect %s --wait' % (batch_id, batch_id))
    return 0


if __name__ == '__main__':
    sys.exit(main())
