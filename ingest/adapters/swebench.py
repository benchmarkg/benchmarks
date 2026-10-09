#!/usr/bin/env python3
"""The SWE-bench leaderboard adapter (P5-S6-T03; 06 S3.7, 07 S1.5).

    python -m ingest.adapters.swebench --fixture tests/ingest/fixtures/swebench     # offline
    bench ingest swe-bench --dry-run [--fixture PATH]                                # through the CLI

The leaderboards are not served as data: the page at https://www.swebench.com/ inlines them as one
`<script type="application/json" id="leaderboard-data">` block (06 S3.7: "One regex plus json.loads; it is
not really a scrape"). A list of leaderboards, each `{"name", "results": [...]}`, one result per submission.

What the adapter does with it:

  fetch     one conditional GET through the fetcher's gate (ingest/policy.yaml paces www.swebench.com). The
            page sends Last-Modified and no ETag, so If-Modified-Since is the validator; a 304 is no change.
  extract   the script tag, parsed; its absence, a parse failure or fewer than five leaderboards is schema
            drift (06 S3.7 "When it breaks"), a hard fail that commits nothing.
  hash      the extracted JSON with 07 S1.5's volatile fields (`logo`, `site`) removed, canonicalised: the page
            carries rotating logos and CDN noise that would be a false change on every run. An unchanged
            hash is no change, whatever the page's bytes did.
  normalise each leaderboard is one logical record (a BulkArchiveAdapter, like Epoch's per-benchmark CSVs);
            each result in it becomes a claim draft in 07 S2.2's shape, or Unresolved records. Nothing is
            invented: a system, an organisation, a benchmark or a metric that does not resolve to a record we
            hold is a human task, and the row is dropped, never stubbed (04 S10).
  anomaly   a leaderboard, or the page, holding more than 10% fewer rows than the last accepted run is a
            semantic anomaly (06 S3.7, 07 S8.2), not a deletion: the run is labelled `needs-scrutiny`, nothing
            is classed `gone`, and the accepted counts are kept until a person looks.

The mapping (06 S3.7's table), and where this adapter departs from it:

  agent, agent_org, model_*   the System is the submission (`name`, "<agent> + <model>"), which a curated
                              System with `built_on` names; resolved, never created. agent_org reports it.
  resolved                    value, a percentage: scale 0.01, declared per leaderboard in BOARDS
  date                        date_reported
  reasoning_effort            eval_conditions.reasoning_effort, with the verbatim string as _raw (04 S8)
  cost                        eval_conditions.cost_usd (the run's total; instance_cost is that over N)
  checked                     the verification ladder: true is maintainer-verified ("Official leaderboard
                              entry with a review step", 04 S7); false, null and the string
                              "false (See README.md ...)" are self-reported; anything else is Unresolved
  logs, trajs                 artifact_url, linked and never fetched (ingest/policy.yaml forbids the bucket).
                              s3://<bucket>/<key> is written as its https virtual-hosted address
  warning                     notes, verbatim: ResultClaim.caveat is only requested (06 S11), and a publisher's
                              caveat is never dropped while its number is kept
  instance_calls              NOT eval_conditions.max_steps, which 06 S3.7 maps it to. On the page it is a mean
                              (28.853 calls an instance), not a limit: max_steps is the cap a run was allowed
                              (04 S8). Recorded absent until a field for observed steps exists
  logo, folder, site, tags,   not on a claim. `folder` is the record's key (source_record_id); `logo` and
  trajs_docent, os_*          `site` are volatile; the rest describe a System, which a curator writes

The licence. 06 S3.7 found "no licence statement" and the task says unlicensed; our own Source record for
the page, src-swebench-leaderboard (checked 2026-09-23), reads the footer's "All rights reserved" and
classes it `no-redistribution`. 04 S9: the class is read from the Source record, never a constant held
elsewhere, so this adapter declares that. Both classes may live nowhere: every draft is held by the
licence-firewall gate, nothing is written, and no raw body is kept (07 S4.4), until P5-S6-T01's
correspondence settles the terms.
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
from datetime import date, datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

from ingest import gates  # noqa: E402
from ingest.adapters.base import BulkArchiveAdapter, Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.backoff import Response, retry  # noqa: E402
from ingest.http.fixture import header  # noqa: E402

NAME = 'swe-bench'
VERSION = '0.1.0'
PAGE_URL = 'https://www.swebench.com/'
SOURCE = 'src-swebench-leaderboard'
LICENCE = 'NOASSERTION'                  # SPDX: no licence we can use; the footer reads "All rights reserved"
LICENCE_CLASS = 'no-redistribution'      # src-swebench-leaderboard's class (04 S9); see the docstring
ATTRIBUTION = 'SWE-bench Team, SWE-bench Leaderboards, https://www.swebench.com/'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, 'ingest', 'state', NAME + '.json')
TARGET = 'data/claims/_ingested/%s/' % NAME

SCRIPT = re.compile(rb'<script\b[^>]*\bid=["\']leaderboard-data["\'][^>]*>(.*?)</script>', re.S | re.I)
MIN_BOARDS = 5                           # 06 S3.7: "the leaderboard count is 5 or greater"
ANOMALY_DROP = 0.10                      # 06 S3.7: "A row count that drops by more than 10%"
VOLATILE = ('logo', 'site')              # 07 S1.5's row for swe-bench
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
# Every key 06 S3.7 maps, on every result: a missing one is drift, and the adapter never reads with a default.
ROW_KEYS = frozenset({'agent', 'agent_org', 'checked', 'cost', 'date', 'folder', 'instance_calls', 'logs', 'model_display',
                      'model_org', 'name', 'reasoning_effort', 'resolved', 'trajs', 'warning'})

# The mapping stanza, one row per leaderboard name the page uses: our benchmark and metric, and the scale of
# `resolved` (a percentage). A record named here that the tree does not hold is resolved like any other
# reference, so the row becomes a human task rather than a dangling claim.
BOARDS = {
    'Verified': {'benchmark': 'swe-bench-verified', 'metric': 'swe-bench-verified-score', 'scale': 0.01},
    'Test': {'benchmark': 'swe-bench', 'metric': 'swe-bench-score', 'scale': 0.01},
    'Lite': {'benchmark': 'swe-bench-lite', 'metric': 'swe-bench-lite-score', 'scale': 0.01},
    'Multimodal': {'benchmark': 'swe-bench-multimodal', 'metric': 'swe-bench-multimodal-score', 'scale': 0.01},
    'Multilingual': {'benchmark': 'swe-bench-multilingual', 'metric': 'swe-bench-multilingual-score', 'scale': 0.01},
}
# `checked`: the ladder rung for each value the page has been seen to carry (06 S3.7, 04 S7).
NOT_CHECKED = re.compile(r'^false\b', re.I)
S3 = re.compile(r'^s3://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])/(\S+)$')
EFFORTS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')   # schema/conditions.py's vocabulary

SchemaDrift = drift.DriftError


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class FetchError(Exception):
    """The page answered something other than 200 or 304."""


class NetworkTransport:
    """GET over urllib under 07 S4.2's retry policy, behind the fetcher's gate (which paces www.swebench.com)."""

    def __init__(self, timeout: int = 60, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.gate = gate or policy.gate()

    def _once(self, url, headers):
        if not url.startswith('https://'):
            raise ValueError('%s: the leaderboard is fetched over HTTPS only' % url)
        self.gate.admit(url)
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, **headers})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:
            return Response(e.code, list(e.headers.items()), e.read())

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


# ---- the page --------------------------------------------------------------------------------------------------

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def strip_volatile(board: dict) -> dict:
    """A leaderboard without 07 S1.5's volatile fields on its results."""
    return {**board, 'results': [{k: v for k, v in r.items() if k not in VOLATILE} for r in board['results']]}


def extract(body: bytes) -> list:
    """The leaderboards inlined in the page, checked for shape. DriftError on anything else (07 S9.2)."""
    m = SCRIPT.search(body)
    if m is None:
        raise SchemaDrift('%s: no <script id="leaderboard-data"> in the page (%d bytes)' % (PAGE_URL, len(body)))
    try:
        boards = json.loads(m.group(1))
    except ValueError as e:
        raise SchemaDrift('%s: the leaderboard-data script does not parse as JSON: %s' % (PAGE_URL, e)) from None
    if not isinstance(boards, list):
        raise SchemaDrift('leaderboard-data is a %s, not a list of leaderboards' % type(boards).__name__)
    if len(boards) < MIN_BOARDS:
        raise SchemaDrift('leaderboard-data holds %d leaderboards; 06 S3.7 expects %d or more'
                          % (len(boards), MIN_BOARDS))
    names = []
    for i, b in enumerate(boards):
        if not isinstance(b, dict) or not isinstance(b.get('name'), str) or 'results' not in b:  # get-default: shape test
            raise SchemaDrift('leaderboard %d is not {"name", "results"}' % i)
        drift.rows(drift.Expect('leaderboard %s' % b['name'], ROW_KEYS, min_rows=1), b['results'])
        folders = [r['folder'] for r in b['results']]
        if len(set(folders)) != len(folders):
            raise SchemaDrift('leaderboard %s repeats a folder: the record key is no longer unique' % b['name'])
        names.append(b['name'])
    if len(set(names)) != len(names):
        raise SchemaDrift('two leaderboards share a name: %s' % ', '.join(names))
    return boards


class Page:
    """One fetched copy of the leaderboard page: its extracted boards and their volatile-free hash."""

    def __init__(self, body: bytes, last_modified: str | None = None, retrieved_at: datetime | None = None):
        self.bytes = len(body)
        self.boards = extract(body)
        self.sha256 = hashlib.sha256(canonical([strip_volatile(b) for b in self.boards])).hexdigest()
        self.last_modified, self.retrieved_at = last_modified, retrieved_at

    def counts(self) -> dict[str, int]:
        return {b['name']: len(b['results']) for b in self.boards}

    def payload_for(self, candidate: Candidate) -> Payload:
        name = candidate.source_key.split(':', 1)[1]
        board = next(b for b in self.boards if b['name'] == name)
        canon = canonical(strip_volatile(board))
        return Payload(candidate=candidate, body=canon, content_type='application/json', http_status=200,
                       fetched_at=self.retrieved_at, etag=None, last_modified=self.last_modified,
                       sha256_normalised=hashlib.sha256(canon).hexdigest(), from_cache=False, doc=board)

    def snapshot(self, retrieved_at: str) -> dict:
        """The IngestBatch `source` block (04 S9). The sha256 is of the extracted, volatile-free JSON (07 S1.5),
        not of the page, and the byte count is the page's."""
        return {'name': 'SWE-bench Leaderboards', 'url': PAGE_URL, 'retrieved_at': retrieved_at,
                'http_etag': None, 'artefact_sha256': self.sha256, 'artefact_bytes': self.bytes}


def fetch_page(transport, state: dict, now=utcnow) -> Page | None:
    """One conditional GET. None on a 304, before anything is parsed."""
    sent = state.get('last_modified')                 # get-default: a cold run has no validator to send
    r = transport.get(PAGE_URL, {'If-Modified-Since': sent} if sent else {})  # get-default: an HTTP GET, not a lookup
    t = now()
    state['checked_at'] = iso(t)
    state['last_status'] = r.status
    if r.status == 304:
        return None
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (PAGE_URL, r.status))
    return Page(r.body, last_modified=header(r.headers, 'Last-Modified'), retrieved_at=t)


# ---- one result row -> a claim draft ----------------------------------------------------------------------------

def verification(checked):
    """The ladder rung for `checked`, or None when the value is not one the page has been seen to carry."""
    if checked is True:
        return 'maintainer-verified'
    if checked is False or checked is None or (isinstance(checked, str) and NOT_CHECKED.match(checked)):
        return 'self-reported'
    return None


def artifact(row) -> tuple[str | None, str]:
    """(artifact_url, field origin): the evaluation logs, else the trajectories; an s3:// URI as its https
    virtual-hosted address. A relative path or a false value is absent: guessing its host would be invention."""
    for key in ('logs', 'trajs'):
        v = row[key]
        if not isinstance(v, str):
            continue
        m = S3.match(v)
        if m:
            return 'https://%s.s3.amazonaws.com/%s' % (m.group(1), m.group(2)), 'derived'
        if re.match(r'^https?://\S+$', v):
            return v, 'source'
    return None, 'absent'


def conditions(row) -> tuple[dict, dict]:
    """(eval_conditions, field provenance). Null is unknown (07 S2.2); nothing is defaulted."""
    out, prov = {}, {}
    raw = row['reasoning_effort']
    if raw is not None:
        out['reasoning_effort'] = raw.lower() if isinstance(raw, str) and raw.lower() in EFFORTS else None
        out['reasoning_effort_raw'] = str(raw)
        prov['eval_conditions.reasoning_effort'] = 'source' if out['reasoning_effort'] else 'absent'
    else:
        prov['eval_conditions.reasoning_effort'] = 'absent'
    cost = row['cost']
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
        out['cost_usd'] = round(float(cost), 6)
        prov['eval_conditions.cost_usd'] = 'source'
    else:
        prov['eval_conditions.cost_usd'] = 'absent'
    prov['eval_conditions.max_steps'] = 'absent'     # instance_calls is a mean, not the cap (see the docstring)
    return out, prov


def record_id(board: str, row) -> str:
    """04 S9's content key: the leaderboard and the submission's own folder, never a row ordinal."""
    return '%s#folder=%s' % (board, row['folder'])


def normalise(payload: Payload, resolvers: dict):
    """(drafts, unresolved) for one leaderboard. Pure: it reads the payload and the frozen resolvers only.

    `resolvers` maps 'system', 'organization', 'benchmark' and 'metric' to an object whose resolve(raw) returns
    something with an `entity` ('kind:id' or None) and a `version`, as ingest/resolve.py's Index does."""
    board = payload.doc
    name = board['name']
    key = payload.candidate.source_key
    stanza = BOARDS.get(name)                        # get-default: a leaderboard the stanza does not name
    if stanza is None:
        return [], [Unresolved(
            source_key=key, field='leaderboard', observed=name, reason='no-match',
            human_task='The page has a leaderboard %r that BOARDS in ingest/adapters/swebench.py does not map. '
                       'Add its benchmark, metric and scale; %d results wait on it.' % (name, len(board['results'])))]
    missing = [(kind, stanza[kind]) for kind in ('benchmark', 'metric')
               if resolvers[kind].resolve(stanza[kind]).entity is None]
    if missing:
        return [], [Unresolved(
            source_key=key, field=kind, observed=ident, reason='no-match',
            human_task='Leaderboard %r maps to %s %r, which the tree does not hold. Write the record, or correct '
                       'BOARDS; its %d results are held until then (07 S8: dropped, not stubbed).'
                       % (name, kind, ident, len(board['results'])))
            for kind, ident in missing]

    fetched = iso(payload.fetched_at)
    drafts, unresolved, asked = [], [], set()

    def ask(u):
        if u.fingerprint not in asked:
            asked.add(u.fingerprint)
            unresolved.append(u)

    for row in board['results']:
        rid = record_id(name, row)
        hit = resolvers['system'].resolve(row['name'])
        org = resolvers['organization'].resolve(row['agent_org']) if row['agent_org'] else None
        rung = verification(row['checked'])
        if hit.entity is None:
            model = resolvers['system'].resolve(row['model_display'])
            ask(Unresolved(
                source_key=row['name'], field='claim.system', observed=row['name'], reason='no-match',
                suggestions=[(model.entity, model.score)] if model.entity else [],
                human_task='No System is %r: agent %r (by %s) on model %r (by %s). Write the System with built_on '
                           'naming the model, or an alias in data/aliases/systems.yaml; never a guess (04 S10).'
                           % (row['name'], row['agent'], row['agent_org'] or 'an unnamed organisation',
                              row['model_display'], row['model_org'] or 'an unnamed organisation')))
        if org is None or org.entity is None:
            ask(Unresolved(
                source_key=rid if not row['agent_org'] else row['agent_org'], field='claim.reported_by',
                observed=row['agent_org'] or '(null)', reason='no-match',
                human_task=('The submission %s names no agent_org, so nobody is recorded as reporting it. Find who '
                            'submitted it (the SWE-bench/experiments pull request) and write reported_by by hand.'
                            % rid) if not row['agent_org'] else
                           ('No Organization is %r. Add one, or an alias in data/aliases/organizations.yaml.'
                            % row['agent_org'])))
        if rung is None:
            ask(Unresolved(
                source_key=rid, field='claim.verification', observed=repr(row['checked']), reason='unparseable',
                human_task='`checked` is %r, a value the adapter has not seen. Say which rung it means and add it '
                           'to verification() (04 S7).' % (row['checked'],)))
        value = row['resolved']
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            ask(Unresolved(source_key=rid, field='claim.value', observed=repr(value), reason='unparseable',
                           human_task='`resolved` is not a number; read the row on the page.'))
            continue
        if hit.entity is None or org is None or org.entity is None or rung is None:
            continue                                 # no system, reporter or rung -> no claim. Never invent one.
        system = hit.entity.split(':', 1)[1] + ('@%s' % hit.version if hit.version else '')
        url, url_origin = artifact(row)
        cond, cond_prov = conditions(row)
        payload_doc = {
            'system': system,
            'benchmark': stanza['benchmark'],
            'metric': stanza['metric'],
            'claim_type': 'absolute',
            'value': round(value * stanza['scale'], 6),
            'date_reported': row['date'],
            'reported_by': org.entity.split(':', 1)[1],
            'verification': rung,
            'source': SOURCE,
            'artifact_url': url,
            'eval_conditions': cond,
        }
        if row['warning']:
            payload_doc['notes'] = 'SWE-bench marks this entry: %s' % row['warning']
        drafts.append(Draft(
            entity_type='claim', entity_id=None,     # the runner mints claim and conditions ids (07 S1.4)
            path=Path(TARGET) / stanza['benchmark'],
            payload=payload_doc,
            change_class='new',                      # the runner re-classifies against the lineage index
            ingestion={
                'batch': 'ingest-%s-%s' % (NAME, payload.fetched_at.strftime('%Y%m%d')),
                'source_adapter': NAME, 'adapter_version': VERSION,
                'source_record_id': rid,
                'last_seen_upstream': payload.fetched_at.date().isoformat(),
                'source_url': PAGE_URL, 'source_licence': LICENCE, 'licence_class': LICENCE_CLASS,
                'source_attribution': ATTRIBUTION, 'ingested_at': fetched, 'review_state': 'machine-ingested',
                'field_provenance': {'value': 'source', 'artifact_url': url_origin, 'verification': 'derived',
                                     **cond_prov},
            },
            confidence=hit.score,
            labels=['source:%s' % NAME]))
    return drafts, unresolved


class SweBench(BulkArchiveAdapter):
    """06 S3.7's adapter on 07 S1.2's contract: one page fetch, one logical record per leaderboard."""

    name, version, licence, licence_class, attribution = NAME, VERSION, LICENCE, LICENCE_CLASS, ATTRIBUTION
    expected_yield = (162, 646)          # 07 S9's seed band: 323 results x [0.5, 2.0]
    tier, source_id = 2, SOURCE           # 06 S8.2 Tier 2
    volatile_fields = VOLATILE
    raw_retainable = False                # 07 S4.4: a no-redistribution source keeps no raw body
    caps = gates.CAP_ROWS

    def __init__(self, transport=None, page: Page | None = None, now=utcnow):
        self.transport, self.bundle, self.now = transport, page, now

    def fetch_bundle(self, state: dict) -> Page | None:
        if self.bundle is not None:
            return self.bundle
        page = fetch_page(self.transport, state, self.now)
        if page is not None and page.sha256 == state.get('sha256'):   # get-default: a cold run has no hash
            return None                   # the page changed, the leaderboards did not (07 S1.5)
        return page

    def enumerate(self, page: Page):
        for b in page.boards:
            yield Candidate('board:%s' % b['name'], 'claim', PAGE_URL, {'snapshot': page.sha256})

    def normalise(self, payload: Payload, resolver=None):
        return normalise(payload, resolver)


# ---- one run --------------------------------------------------------------------------------------------------

def anomalies(counts: dict[str, int], accepted: dict[str, int] | None) -> list[str]:
    """06 S3.7 / 07 S8.2: a leaderboard, or the whole page, down by more than 10% on the last accepted run."""
    if not accepted:
        return []
    out = []
    for name, before in sorted(accepted.items()):
        now = counts.get(name, 0)                    # get-default: a leaderboard that vanished holds zero rows
        if before and now < before * (1 - ANOMALY_DROP):
            out.append('leaderboard %s holds %d results, down from %d (-%.0f%%)' % (name, now, before, 100 * (before - now) / before))
    total_before, total_now = sum(accepted.values()), sum(counts.values())
    if total_before and total_now < total_before * (1 - ANOMALY_DROP):
        out.append('the page holds %d results, down from %d (-%.0f%%)'
                   % (total_now, total_before, 100 * (total_before - total_now) / total_before))
    return out


def resolvers_from(root: str = ROOT) -> dict:
    from ingest.resolve import Index
    return {k: Index.load(k, root) for k in ('system', 'organization', 'benchmark', 'metric')}


def new_state() -> dict:
    return {'version': 1, 'last_modified': None, 'sha256': None, 'counts': None}


def run(adapter: SweBench, state: dict | None = None, resolvers: dict | None = None) -> dict:
    """Fetch, extract, check and normalise; then hold every draft to the licence firewall. Writes nothing:
    `state` is updated in place for the caller to persist."""
    state = state if state is not None else new_state()
    started = adapter.now()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(started), 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'drafts_by_board': {},
              'unresolved': 0, 'unresolved_by_field': {}, 'errors': [], 'snapshot': None, 'counts': None,
              'anomalies': [], 'labels': [], 'held': 0, 'proposals': [], 'documents': []}
    try:
        page = adapter.fetch_bundle(state)
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(NAME, e.message, report['started_at']))
        return report
    if page is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    adapter.bundle = page
    report['snapshot'] = page.snapshot(iso(page.retrieved_at or started))
    report['counts'] = page.counts()
    report['anomalies'] = anomalies(page.counts(), state.get('counts'))   # get-default: a cold run has none
    if report['anomalies']:
        report['labels'] = ['needs-scrutiny']        # 07 S8.2: the anomaly is the PR's first line; nothing is gone
    if resolvers is None:
        resolvers = resolvers_from()
    for cand in adapter.enumerate(page):
        report['candidates_seen'] += 1
        drafts, unresolved = adapter.normalise(adapter.fetch(cand), resolvers)
        report['unresolved'] += len(unresolved)
        for u in unresolved:
            report['unresolved_by_field'][u.field] = report['unresolved_by_field'].get(u.field, 0) + 1  # get-default: a count starts at 0
        board = cand.source_key.split(':', 1)[1]
        report['drafts_by_board'][board] = len(drafts)
        for d in drafts:
            report['drafts'][d.change_class] += 1
            doc = gates.document(d)
            rel = (d.path / 'claim-unminted.yaml').as_posix()
            try:
                gates.licence_firewall(doc, rel, LICENCE_CLASS)
            except gates.GateError:
                report['held'] += 1
            report['documents'].append({'path': d.path.as_posix() + '/', **doc})
    if report['held']:
        report['proposals'].append('%d claim drafts held by the licence firewall: %s is %s (04 S9), so nothing is '
                                   'written until P5-S6-T01 settles the terms' % (report['held'], SOURCE, LICENCE_CLASS))
    state['sha256'] = page.sha256
    state['last_modified'] = page.last_modified
    if not report['anomalies']:
        state['counts'] = page.counts()             # an anomalous run never becomes the new baseline
    report['finished_at'] = iso(adapter.now())
    return report


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return new_state()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture', help='a recorded-response directory in place of the network')
    a = p.parse_args(argv)
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport()
    report = run(SweBench(transport), new_state())
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}, indent=2, default=str))
    return 1 if report['status'] == 'hard-fail' else 0


if __name__ == '__main__':
    sys.exit(main())
