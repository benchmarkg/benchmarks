"""The FormPayload spike (P5-S1-T07; 07 S12, 05 S6). The decision it feeds is adr/0022-formpayload-reuse.md.

07 S12's assumption to test: "a `FormPayload` can substitute for `Payload` in `normalise()`, because
`normalise()` takes no network and no clock, so a human-submitted form is just another payload shape. If it
holds, the validation bot reuses the gates, the resolver and the PR generator for free."

The spike, in three steps, and the code for it lives here rather than in ingest/: it is a probe of the
contract before P5-S1-T08 extracts the Adapter ABC, not the intake bot (P2-S6-T04 builds that).

  1. Construct a FormPayload from an issue-form submission: a `new-benchmark.yml` issue body exactly as
     GitHub renders a form (`### <label>`, the answer, `_No response_` for a blank, `- [X]` for a box).
  2. Pass it through a normalise() with 07 S1.1's signature and purity, and through the existing gates
     (ingest/gates/) unchanged.
  3. Assert what holds and what does not, both ways, so the ADR's verdict is a test result.

The verdict the assertions below pin:

  HOLDS   the Payload dataclass carries a form with no change; normalise() stays pure and byte-identical;
          the frozen resolver catches a submission for a benchmark we hold; Unresolved carries the
          field-level error 05 S6's bot must post; the derived-field guard and the sanity band apply as is.
  FAILS   the provenance gate refuses every form draft (no `ingestion` block: a form record is curated,
          not ingested, 04 S9); the unit guard refuses every form claim (no mapping stanza); and a form
          draft's path lies outside 06 S1.1 Check A's bot allowlist.
"""
import builtins
import difflib
import hashlib
import json
import os
import random
import re
import socket
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from ingest import gates
from ingest.adapters.base import Candidate, Draft, Payload, Unresolved
from ingest.resolve import thaw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAPSHOT = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub', 'resolver-snapshot.json')
with open(SNAPSHOT, encoding='utf-8') as _f:
    RESOLVERS = thaw(json.load(_f))
ADAPTER, VERSION = 'issue-form', '0.0.0-spike'
NO_RESPONSE = '_No response_'
CHECK_A = ('data/_discovery/', 'data/claims/_ingested/', 'data/_ingest/', 'metrics/')   # 06 S1.1 Check A


def _terms(name):
    with open(os.path.join(ROOT, 'taxonomy', name), encoding='utf-8') as f:
        return [t for t in yaml.safe_load(f)['terms'] if t.get('status') != 'retired']   # get-default: status is optional


DOMAINS = [t['id'] for t in _terms('domains.yaml') if t.get('parent')]                  # get-default: a family has none
CAPABILITIES = [t['id'] for t in _terms('capabilities.yaml')]
METHODS = [t['id'] for t in _terms('evaluation-methods.yaml')]

# 05 S6's new-benchmark.yml labels, in its order: label -> the record field it fills (None: read by the bot
# but not a record field). P2-S6-T02 writes the form itself; these labels are 05's verbatim.
LABELS = {
    'Benchmark name': 'name',
    'Homepage or paper URL': 'homepage',
    'One-sentence description': 'tagline',
    'Primary domain': 'domain.primary',
    'Secondary domains': 'domain.secondary',
    'Capabilities measured': 'capability',
    'Evaluation method': 'evaluation_method',
    'What is evaluated': 'evaluation_target',
    'Repository URL': 'repository',
    'Dataset or task-data URL': 'dataset_url',
    'Licence': 'license',
    'Number of items, and unit': None,
    'Maintaining organisation': None,
    'Release date': 'released',
    'Leaderboard URL': 'leaderboard_url',
    'Is this a version or fork of an existing benchmark?': None,
    'Anything we should know': None,
}
MULTI = {'domain.secondary', 'capability', 'evaluation_method'}
ATTESTATIONS = ('Every field above is supported by the linked sources; I have not filled anything from memory',
                'I understand this index links to data and never hosts it')
VOCAB = {'domain.primary': DOMAINS, 'domain.secondary': DOMAINS, 'capability': CAPABILITIES,
         'evaluation_method': METHODS}


# ---- step 1: the submission, and the FormPayload ------------------------------------------------------------

def render(answers, checked=(True, True)):
    """An issue body as GitHub renders a submitted issue form."""
    parts = []
    for label in LABELS:
        v = answers.get(label)                                   # get-default: an unanswered field
        if isinstance(v, (list, tuple)):
            v = ', '.join(v)
        parts.append('### %s\n\n%s' % (label, v if v else NO_RESPONSE))
    parts.append('### Attestations\n\n' + '\n'.join('- [%s] %s' % ('X' if c else ' ', a)
                                                     for a, c in zip(ATTESTATIONS, checked)))
    return '\n\n'.join(parts) + '\n'


def answers(**over):
    base = {'Benchmark name': 'Tide Gauge Bench', 'Homepage or paper URL': 'https://example.org/tide-gauge-bench',
            'One-sentence description': 'Forecasting hourly sea level at 200 tide gauges.',
            'Primary domain': DOMAINS[0], 'Capabilities measured': [CAPABILITIES[0]],
            'Evaluation method': [METHODS[0]], 'What is evaluated': 'model', 'Licence': 'CC-BY-4.0',
            'Release date': '2026-08-01'}
    base.update(over)
    return base


def issue(body, number=412, updated='2026-10-07T09:00:00Z', user='a-contributor'):
    """The parts of a GitHub `issues` event the bot reads."""
    return {'number': number, 'html_url': 'https://github.com/benchmarkg/benchmarks/issues/%d' % number,
            'body': body, 'updated_at': updated, 'user': {'login': user}}


def parse_form(body):
    """{label: answer or None} and the attestation boxes, from a rendered form body."""
    fields, boxes = {}, {}
    for block in re.split(r'^### ', body, flags=re.M)[1:]:
        label, _, rest = block.partition('\n')
        value = rest.strip()
        if label == 'Attestations':
            boxes = {m.group(2): m.group(1) == 'X' for m in re.finditer(r'^- \[( |X)\] (.+)$', value, re.M)}
        else:
            fields[label] = None if value in ('', NO_RESPONSE) else value
    return fields, boxes


def form_payload(event):
    """07 S1.1's Payload, built from an issue event: no fetch, so the HTTP fields carry placeholders."""
    fields, boxes = parse_form(event['body'])
    doc = {'fields': fields, 'attestations': boxes, 'submitter': event['user']['login']}
    canon = json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    c = Candidate('issue:%d' % event['number'], 'benchmark', event['html_url'], {'form': 'new-benchmark.yml'})
    return Payload(candidate=c, body=event['body'].encode('utf-8'), content_type='text/markdown', http_status=200,
                   fetched_at=datetime.fromisoformat(event['updated_at'].replace('Z', '+00:00')),
                   etag=None, last_modified=None,
                   sha256_normalised=hashlib.sha256(canon.encode('utf-8')).hexdigest(), from_cache=False, doc=doc)


# ---- step 2: normalise(), with 07 S1.1's signature and purity --------------------------------------------------

def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _error(source_key, field, observed, reason, task, suggestions=()):
    return Unresolved(source_key=source_key, field=field, observed=observed, reason=reason,
                      suggestions=list(suggestions), human_task=task)


def normalise(payload, resolvers):
    """(drafts, unresolved) for one form submission. Pure, as 07 S1.1 requires: no clock, no network, no
    randomness, no file. An Unresolved here is a field-level error for the contributor (05 S6, "on failure"),
    phrased as an instruction, and any one of them means no draft: the bot never opens a broken PR."""
    key, doc = payload.candidate.source_key, payload.doc
    f, problems, record = doc['fields'], [], {}
    for attestation in ATTESTATIONS:
        if not doc['attestations'].get(attestation):                         # get-default: an absent box is unticked
            problems.append(_error(key, 'attestations', attestation, 'policy',
                                   'Tick "%s" -- the form cannot be accepted without it.' % attestation))
    for label, path in LABELS.items():
        value = f.get(label)                                                 # get-default: a label the body lacks
        if path is None or value is None:
            continue
        if path in MULTI:
            value = [v.strip() for v in value.split(',') if v.strip()]
        for v in (value if isinstance(value, list) else [value]) if path in VOCAB else []:
            if v not in VOCAB[path]:
                near = difflib.get_close_matches(v, VOCAB[path], n=3, cutoff=0.6)
                problems.append(_error(key, label, v, 'no-match',
                                       '%s `%s` is not in the vocabulary.%s' % (
                                           label, v, ' Did you mean `%s`?' % '`, `'.join(near) if near else ''),
                                       [(n, 1.0) for n in near]))
        record[path] = value
    for required in ('Benchmark name', 'Homepage or paper URL', 'One-sentence description', 'Primary domain'):
        if f.get(required) is None:                                          # get-default: as above
            problems.append(_error(key, required, '', 'policy', '%s is required.' % required))
    held = resolvers['benchmark'].resolve(f['Benchmark name']).entity if f.get('Benchmark name') else None  # get-default: as above
    if held:
        problems.append(_error(key, 'Benchmark name', f['Benchmark name'], 'policy',
                               'We already hold this benchmark as `%s`. To change it, use the correction form '
                               'instead.' % held, [(held, 1.0)]))
    if problems:
        return [], problems
    nested = {}
    for path, value in record.items():
        head, _, tail = path.partition('.')
        if tail:
            nested.setdefault(head, {})[tail] = value
        else:
            nested[head] = value
    nested['curation'] = {'verification_status': 'ai-drafted-unverified', 'submitted_by': doc['submitter'],
                          'submitted_via': payload.candidate.url}
    family = nested['domain']['primary'].split('/')[0]
    draft = Draft(entity_type='benchmark', entity_id=None,
                  path=Path('data/benchmarks/%s/%s.yaml' % (family, _slug(f['Benchmark name']))),
                  payload=nested, change_class='new',
                  ingestion=None,          # a form record is curated, not ingested: 04 S9's block does not apply
                  confidence=1.0, labels=['source:issue-form', 'verification:curator-review-needed'])
    return [draft], []


# ---- step 3a: what holds --------------------------------------------------------------------------------------

def test_a_form_submission_is_a_payload_with_no_change_to_the_dataclass():
    p = form_payload(issue(render(answers())))
    assert type(p) is Payload and p.candidate.source_key == 'issue:412'
    assert p.doc['fields']['Benchmark name'] == 'Tide Gauge Bench'
    assert p.doc['attestations'] == dict.fromkeys(ATTESTATIONS, True)
    # what does not carry over: four of Payload's fields describe an HTTP fetch and have nothing to hold
    assert (p.http_status, p.etag, p.last_modified, p.from_cache) == (200, None, None, False)


def test_a_valid_submission_normalises_to_one_draft_and_nothing_unresolved():
    [d], u = normalise(form_payload(issue(render(answers()))), RESOLVERS)
    assert u == []
    assert d.entity_id is None                                   # the adapter never mints an id (07 S1.1)
    assert d.payload['domain'] == {'primary': DOMAINS[0]} and d.payload['capability'] == [CAPABILITIES[0]]
    assert d.payload['curation']['verification_status'] == 'ai-drafted-unverified'   # 05 S6 step 4
    assert d.path.as_posix() == 'data/benchmarks/%s/tide-gauge-bench.yaml' % DOMAINS[0].split('/')[0]


def test_normalise_is_pure_for_a_form_payload(monkeypatch):
    payloads = [form_payload(issue(render(answers(**{'Benchmark name': 'Bench %d' % i})), number=i))
                for i in range(20)]
    expected = [normalise(p, RESOLVERS) for p in payloads]

    def refuse(*a, **k):
        raise AssertionError('normalise() reached outside its arguments: %r' % (a,))
    for target, name in ((time, 'time'), (time, 'monotonic'), (random, 'random'), (socket, 'create_connection'),
                         (urllib.request, 'urlopen'), (builtins, 'open')):
        monkeypatch.setattr(target, name, refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    assert [normalise(p, RESOLVERS) for p in payloads] == expected


def test_an_edit_that_changes_nothing_is_the_same_payload_hash_and_the_same_draft():
    """05 S6: the bot re-runs on every edit. An edit that leaves the answers alone moves only the event
    time, so the hash 07 S1.5 diffs on is unchanged and the draft is identical."""
    body = render(answers())
    a, b = form_payload(issue(body)), form_payload(issue(body, updated='2026-10-08T17:30:00Z'))
    assert a.sha256_normalised == b.sha256_normalised
    assert normalise(a, RESOLVERS) == normalise(b, RESOLVERS)


def test_the_frozen_resolver_catches_a_submission_for_a_benchmark_we_hold():
    held = json.load(open(SNAPSHOT, encoding='utf-8'))['indexes']['benchmark']['entries'][0]
    drafts, u = normalise(form_payload(issue(render(answers(**{'Benchmark name': held['name']})))), RESOLVERS)
    assert drafts == []
    assert [(x.reason, x.suggestions) for x in u] == [('policy', [('benchmark:%s' % held['id'], 1.0)])]
    assert 'correction form' in u[0].human_task


def test_an_unresolved_is_the_field_level_error_05_asks_the_bot_to_post():
    typo = DOMAINS[0][:-1] + ('x' if DOMAINS[0][-1] != 'x' else 'y')
    drafts, u = normalise(form_payload(issue(render(answers(**{'Primary domain': typo})))), RESOLVERS)
    assert drafts == []                                           # 05 S6: never a broken PR
    [e] = u
    assert e.reason == 'no-match' and e.field == 'Primary domain' and e.suggestions[0][0] == DOMAINS[0]
    assert e.human_task.startswith('Primary domain `%s` is not in the vocabulary. Did you mean `%s`' % (typo, DOMAINS[0]))
    assert 'Traceback' not in e.human_task and 'ValidationError' not in e.human_task
    assert len(e.fingerprint) == 16                               # stable across re-runs: the comment it replaces


def test_an_unticked_attestation_and_a_missing_required_field_are_refused():
    body = render(answers(**{'One-sentence description': None}), checked=(True, False))
    drafts, u = normalise(form_payload(issue(body)), RESOLVERS)
    assert drafts == []
    assert sorted((x.field, x.reason) for x in u) == [('One-sentence description', 'policy'), ('attestations', 'policy')]


def test_the_derived_field_guard_applies_unchanged():
    [d], _ = normalise(form_payload(issue(render(answers()))), RESOLVERS)
    gates.derived_field_guard(d.payload)                          # passes: a form cannot set a derived field
    with pytest.raises(gates.GateError, match='derived-field'):
        gates.derived_field_guard(dict(d.payload, headroom=0.4))


def test_the_sanity_band_applies_unchanged_to_a_submitted_value():
    """A new-claim.yml value meets the same band an ingested one does: it needs only the value and a Metric.
    The check carries over; its message does not -- it sends the reader to an adapter's mapping stanza,
    which a contributor has never seen, so the bot must reword it before posting (05 S6: field-level only)."""
    class Metric:
        id = 'accuracy'
        range = type('R', (), {'min': 0.0, 'max': 1.0})()
        unbounded, value_type, chance_baseline, score_ceiling = False, 'proportion', None, None
    assert gates.sanity_band(0.7, Metric, 'issue:413') is None
    refused = gates.sanity_band(70.0, Metric, 'issue:413')                        # a percentage in a 0-1 field
    assert refused.reason == 'unparseable' and 'stanza' in refused.human_task


# ---- step 3b: what does not hold -- the failure case the verification names --------------------------------------

def test_the_provenance_gate_refuses_every_form_draft():
    """07 S8: "Every record carries a complete ingestion block". A form record is curated, not ingested
    (04 S9: ingestion is "machine-written"; 06 S1.1 Check B: `ingestion` null means hand-authored), so it has
    none, and inventing one (a batch, an adapter licence class) would mislabel a contributor's record as a
    machine's. The gate cannot be reused unchanged."""
    [d], _ = normalise(form_payload(issue(render(answers()))), RESOLVERS)
    with pytest.raises(gates.GateError, match='no ingestion block'):
        gates.provenance(d.payload)


def test_the_unit_guard_refuses_every_form_claim():
    """07 S8's unit guard reads the adapter's mapping stanza for the scale. A contributor's claim has no
    stanza -- the form states its own unit -- so the guard refuses it outright."""
    with pytest.raises(gates.GateError):
        gates.unit_guard(ADAPTER, 'issue:413')


def test_a_form_draft_lies_outside_check_a_s_bot_allowlist():
    """06 S1.1 Check A fails any bot-authored commit outside four trees. The intake bot's PR writes
    data/benchmarks/ (05 S6; 08: "the issue-form bot's PR is the one bot-authored path"), so Check A needs
    that path as a named exception, not the adapter allowlist."""
    [d], _ = normalise(form_payload(issue(render(answers()))), RESOLVERS)
    assert not d.path.as_posix().startswith(CHECK_A)
