#!/usr/bin/env python3
"""The arXiv OAI-PMH adapter (P5-S5-T04; 06 S3.4, S5, S9.6; 07 S4.1, S10).

    bench ingest arxiv-oai --dry-run --from 2026-10-06 --until 2026-10-06     # live: one day of set=cs
    bench ingest arxiv-oai --dry-run --fixture tests/ingest/fixtures/arxiv --from 2026-10-06 --until 2026-10-06

What it asks. `https://oaipmh.arxiv.org/oai?verb=ListRecords&set=cs&metadataPrefix=arXivRaw&from=..&until=..`,
then each `resumptionToken` in turn, sequentially -- one window, one page at a time, through the fetcher's gate
(ingest/policy.yaml: oaipmh.arxiv.org at one request every 3 s, HTTPS only). 06 S3.4: "OAI-PMH is the right
tool for incremental harvest"; there is no cs.CL set, so the subcategories are filtered client-side from each
record header's setSpecs (`cs:cs:CL`). The default four are 06 S5's "four large CS categories".

Windows. An incremental run harvests from the persisted `last_until` (inclusive: a record seen twice is the same
candidate) to the run's `until`. A cold run with no `last_until` is a backfill, windowed by calendar month so a
failure loses at most a month (P5-S5-T04). `last_until` advances only when a window's last page has been read.

New, revised, or touched. from/until run on the MODIFICATION datestamp, "so v2 resubmissions of old papers
arrive mixed in" (06 S3.4; on 2026-10-06, 944 of the first 2,600 records in set=cs were revisions, back to
2013). arXivRaw carries every version with its date, and a record is:

    new               one version, submitted no more than LAG_DAYS before the window opens
    revision          a later version dated inside that span: an existing paper, re-submitted
    metadata-update   no version in the span: a journal reference, DOI or licence edited on an old paper
    deleted           the header says so (deletedRecord: persistent)

Only a `new` paper in a wanted subcategory becomes a discovery candidate; everything else is counted and dropped,
"or it will re-triage the same work forever" (06 S3.4). LAG_DAYS covers announcement delay: a paper submitted on
a Friday is announced, and datestamped, days later.

What a candidate holds (06 S1.1's shape, data/_discovery/arxiv/<candidate-id>.yaml): identity -- the arXiv id,
its 10.48550 DOI, title, abs URL, submission date, licence URL -- and `_suggested` category hints (06 S3.4: "a
cs.RO paper is not necessarily a robotics benchmark"). `triage` is null until the classifier (P5-S5-T07) writes
it. The abstract is not copied into the candidate: 07 S8's metadata-only gate refuses any string over 280
characters, so the candidate carries the abstract's sha256 and length, and the text stays in the raw store
(arXiv metadata is CC0, so the body is retainable), where the classifier reads it.

Failures. `badResumptionToken` mid-harvest is a soft failure: the window is retried from its start next run,
from the persisted `last_until`, never from earliestDatestamp (06 S3.4). `noRecordsMatch` is an empty window,
not an error. Any other OAI error, or a response that is not an OAI-PMH ListRecords document, is schema drift: a
hard fail.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.adapters.base import Adapter, Candidate, Draft, Payload, Unresolved  # noqa: E402,F401
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402
from ingest.http.backoff import Response, SoftFail, retry  # noqa: E402

NAME = 'arxiv-oai'
VERSION = '0.1.0'
DISCOVERED_VIA = 'arxiv-oaipmh'
ENDPOINT = 'https://oaipmh.arxiv.org/oai'
SET = 'cs'
PREFIX = 'arXivRaw'
WANTED = ('cs:cs:AI', 'cs:cs:CL', 'cs:cs:CV', 'cs:cs:LG')     # 06 S5: "the four large CS categories"
LAG_DAYS = 14
MAX_PROSE = 280                                              # ingest/gates/checks.py's metadata-only limit
DISCOVERY = 'data/_discovery/arxiv'
USER_AGENT = 'UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)'
NS = {'o': 'http://www.openarchives.org/OAI/2.0/', 'r': 'http://arxiv.org/OAI/arXivRaw/'}
KINDS = ('new', 'revision', 'metadata-update', 'deleted')
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')


class BadResumptionToken(SoftFail):
    """06 S3.4: a soft failure. The window resumes from the persisted last_until next run, never restarts."""

    def __init__(self, window):
        super().__init__('badResumptionToken in window %s..%s; the next run resumes it' % window, None, 1)
        self.window = window


# ---- the transport ----------------------------------------------------------------------------------------------

class NetworkTransport:
    """GET over urllib under 07 S4.2's retry policy, behind the fetcher's gate (which paces oaipmh.arxiv.org)."""

    def __init__(self, timeout: int = 180, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.gate = gate or policy.gate()                # 07 S10.1: ingest/policy.yaml, robots.txt, no-collect

    def _once(self, url, headers):
        if not url.startswith('https://'):
            raise ValueError('%s: arXiv is HTTPS only (06 S3.4: http:// 301s to an empty body)' % url)
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


# ---- windows ----------------------------------------------------------------------------------------------------

def windows(state: dict, until: date, backfill_from: date | None = None) -> list[tuple[date, date]]:
    """The run's windows: from last_until to `until`, or, cold, one per calendar month from `backfill_from`."""
    last = state.get('last_until')                         # get-default: a cold run has none
    if last:
        start = date.fromisoformat(last)
        return [(start, until)] if start <= until else []
    if backfill_from is None:
        return [(until, until)]
    out, d = [], backfill_from
    while d <= until:
        end = min(date(d.year, d.month, calendar.monthrange(d.year, d.month)[1]), until)
        out.append((d, end))
        d = end + timedelta(days=1)
    return out


def list_url(window: tuple[date, date], token: str | None = None) -> str:
    if token:
        return '%s?%s' % (ENDPOINT, urllib.parse.urlencode({'verb': 'ListRecords', 'resumptionToken': token}))
    return '%s?verb=ListRecords&set=%s&metadataPrefix=%s&from=%s&until=%s' % (
        ENDPOINT, SET, PREFIX, window[0].isoformat(), window[1].isoformat())


# ---- parsing ----------------------------------------------------------------------------------------------------

def _text(el, path):
    x = el.find(path, NS)
    return ' '.join(x.text.split()) if x is not None and x.text else None


def parse_page(body: bytes, url: str) -> tuple[list[dict], str | None]:
    """(the records, the next resumptionToken or None). Raises drift.DriftError on a shape that is not OAI-PMH
    ListRecords, BadResumptionToken's marker ('badResumptionToken') through the error code, and returns no
    records for noRecordsMatch."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise drift.DriftError('%s: not XML (%s)' % (url, e)) from None
    if root.tag != '{%s}OAI-PMH' % NS['o']:
        raise drift.DriftError('%s: the root element is %s, not OAI-PMH' % (url, root.tag))
    err = root.find('o:error', NS)
    if err is not None:
        code = err.get('code')
        if code == 'noRecordsMatch':
            return [], None
        if code == 'badResumptionToken':
            raise KeyError('badResumptionToken')
        raise drift.DriftError('%s: OAI-PMH error %s: %s' % (url, code, (err.text or '').strip()))
    lr = root.find('o:ListRecords', NS)
    if lr is None:
        raise drift.DriftError('%s: no ListRecords element' % url)
    records = []
    for rec in lr.findall('o:record', NS):
        h = rec.find('o:header', NS)
        if h is None or h.find('o:identifier', NS) is None or h.find('o:datestamp', NS) is None:
            raise drift.DriftError('%s: a record without its header, identifier or datestamp' % url)
        ident = h.find('o:identifier', NS).text.strip()
        out = {'oai_id': ident, 'arxiv_id': ident.rsplit(':', 1)[-1], 'datestamp': h.find('o:datestamp', NS).text.strip(),
               'sets': [s.text.strip() for s in h.findall('o:setSpec', NS)], 'deleted': h.get('status') == 'deleted'}
        raw = rec.find('o:metadata/r:arXivRaw', NS)
        if not out['deleted']:
            if raw is None:
                raise drift.DriftError('%s: record %s has no arXivRaw metadata' % (url, ident))
            versions = []
            for v in raw.findall('r:version', NS):
                when = _text(v, 'r:date')
                versions.append({'version': v.get('version'),
                                 'date': parsedate_to_datetime(when).date().isoformat() if when else None})
            if not versions or any(v['date'] is None for v in versions):
                raise drift.DriftError('%s: record %s has no dated versions' % (url, ident))
            abstract = _text(raw, 'r:abstract') or ''
            out.update({'arxiv_id': _text(raw, 'r:id') or out['arxiv_id'], 'title': _text(raw, 'r:title'),
                        'authors': _text(raw, 'r:authors'), 'categories': (_text(raw, 'r:categories') or '').split(),
                        'licence': _text(raw, 'r:license'), 'versions': versions,
                        'abstract_sha256': hashlib.sha256(abstract.encode('utf-8')).hexdigest(),
                        'abstract_chars': len(abstract)})
        records.append(out)
    tok = lr.find('o:resumptionToken', NS)
    return records, (tok.text.strip() if tok is not None and tok.text and tok.text.strip() else None)


def classify(record: dict, window_from: date, lag_days: int = LAG_DAYS) -> str:
    """new | revision | metadata-update | deleted, as the module docstring defines them."""
    if record['deleted']:
        return 'deleted'
    since = (window_from - timedelta(days=lag_days)).isoformat()
    versions = record['versions']
    if len(versions) == 1:
        return 'new' if versions[0]['date'] >= since else 'metadata-update'
    return 'revision' if versions[-1]['date'] >= since else 'metadata-update'


def wanted(record: dict, subcategories=WANTED) -> bool:
    return any(s in subcategories for s in record['sets'])


def candidate_id(arxiv_id: str) -> str:
    """2610.03818 -> cand-arxiv-2610-03818; an old-style math/0601001 -> cand-arxiv-math-0601001."""
    return 'cand-arxiv-' + re.sub(r'[^a-z0-9]+', '-', arxiv_id.lower()).strip('-')


def _short(s: str | None) -> str | None:
    return s if s is None or len(s) <= MAX_PROSE else s[:MAX_PROSE - 1] + '…'


# ---- the adapter ------------------------------------------------------------------------------------------------

def new_state() -> dict:
    return {'adapter': NAME, 'last_until': None, 'checkpoint': None}


class ArxivOai(Adapter):
    name = NAME
    version = VERSION
    licence = 'CC0-1.0'                    # 06 S3.4: "Metadata is CC0 1.0"; full content is never harvested
    licence_class = 'permissive-attribution'
    attribution = 'arXiv metadata (CC0 1.0), via the OAI-PMH interface'
    expected_yield = (10, 400)             # new papers a day in the four categories (06 S5: 509 a week in cs.CL alone)
    tier = 1                               # 06 S8.1: the fourth Tier-1 adapter

    def __init__(self, transport, until: date, backfill_from: date | None = None, subcategories=WANTED,
                 now=lambda: datetime.now(timezone.utc)):
        self.transport, self.until, self.backfill_from = transport, until, backfill_from
        self.subcategories, self.now = tuple(subcategories), now
        self.counts: Counter = Counter()
        self.pages = 0
        self.http_codes: Counter = Counter()

    def discover(self, state):
        """Every record in every window, in order, one page at a time; last_until advances per finished window."""
        for window in windows(state, self.until, self.backfill_from):
            token = None
            while True:
                url = list_url(window, token)
                r = self.transport.get(url, {})       # get-default: an HTTP GET with request headers
                self.http_codes[r.status] += 1
                self.pages += 1
                if r.status != 200:
                    raise drift.DriftError('%s answered HTTP %d' % (url, r.status))
                try:
                    records, token = parse_page(r.body, url)
                except KeyError:
                    state['checkpoint'] = None        # a token is not resumable: the window restarts, not the harvest
                    raise BadResumptionToken((window[0].isoformat(), window[1].isoformat())) from None
                fetched = self.now()
                for rec in records:
                    kind = classify(rec, window[0])
                    self.counts[kind] += 1
                    yield Candidate(rec['arxiv_id'], 'benchmark', 'https://arxiv.org/abs/' + rec['arxiv_id'],
                                    {'record': rec, 'kind': kind, 'window': [d.isoformat() for d in window],
                                     'fetched_at': fetched.strftime('%Y-%m-%dT%H:%M:%SZ')})
                state['checkpoint'] = {'window': [d.isoformat() for d in window], 'token': token} if token else None
                if not token:
                    break
            state['last_until'] = window[1].isoformat()

    def fetch(self, candidate, state=None):
        """The listing is the payload: no request per record. None for what never becomes a candidate."""
        rec, kind = candidate.hint['record'], candidate.hint['kind']
        if kind != 'new' or not wanted(rec, self.subcategories):
            if kind == 'new':
                self.counts['filtered'] += 1
            return None
        doc = json.dumps(rec, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return Payload(candidate, doc, 'application/json', 200,
                       datetime.strptime(candidate.hint['fetched_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc),
                       None, None, hashlib.sha256(doc).hexdigest(), False, doc=rec)

    def normalise(self, payload, resolver=None):
        return normalise(payload)


def normalise(payload: Payload) -> tuple[list[Draft], list[Unresolved]]:
    """A pure function of one new paper's record: its discovery candidate (06 S1.1's shape)."""
    rec = payload.doc
    aid = rec['arxiv_id']
    fetched = payload.fetched_at.strftime('%Y-%m-%dT%H:%M:%SZ')
    source_url = 'https://arxiv.org/abs/' + aid
    authors = [a.strip() for a in re.split(r',| and ', rec['authors'] or '') if a.strip()]
    doc = {
        'candidate_id': candidate_id(aid),
        'discovered_via': DISCOVERED_VIA,
        'discovered_at': fetched,
        'triage': None,                                   # P5-S5-T07's classifier writes label and rationale
        'identity': {
            'arxiv_id': aid,
            'doi': '10.48550/arXiv.' + aid,
            'url': source_url,
            'title': _short(rec['title']),
            'submitted': rec['versions'][0]['date'],
            'licence': rec['licence'],
            'abstract': {'sha256': rec['abstract_sha256'], 'chars': rec['abstract_chars'], 'in': 'ingest/raw/arxiv-oai/'},
        },
        '_suggested': [
            {'field': 'categories', 'value': rec['categories'], 'adapter': NAME, 'adapter_version': VERSION,
             'source_url': source_url, 'fetched_at': fetched, 'confidence': 0.3,
             'rationale': '06 S3.4: a category is a domain hint only'},
            {'field': 'authors', 'value': {'count': len(authors), 'first': [_short(a) for a in authors[:3]]},
             'adapter': NAME, 'adapter_version': VERSION, 'source_url': source_url, 'fetched_at': fetched,
             'confidence': 0.1, 'rationale': '06 S3.4: arXiv has no structured affiliation, so organisation hints are noisy'},
        ],
    }
    ingestion = {'adapter': NAME, 'adapter_version': VERSION, 'source_url': source_url, 'fetched_at': fetched,
                 'sha256_normalised': payload.sha256_normalised}
    path = Path(DISCOVERY) / ('%s.yaml' % doc['candidate_id'])
    return [Draft('benchmark', None, path, doc, 'new', ingestion, 1.0, labels=['ingest:arxiv-oai'])], []


# ---- one dry run ------------------------------------------------------------------------------------------------

def run(adapter: ArxivOai, state: dict | None = None, *, limit: int | None = None) -> dict:
    """Harvest the run's windows and draft a candidate per new paper in the wanted subcategories. Writes nothing."""
    state = state if state is not None else new_state()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': adapter.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
              'status': 'ok', 'candidates_seen': 0, 'drafts': {k: 0 for k in CHANGE_CLASSES}, 'unresolved': 0,
              'errors': [], 'snapshot': None, 'proposals': [], 'documents': [], 'records': {}, 'allowance': {}}
    try:
        for cand in adapter.discover(state):
            report['candidates_seen'] += 1
            payload = adapter.fetch(cand, state)
            if payload is None:
                continue
            drafts, _ = adapter.normalise(payload)
            for d in drafts:
                report['drafts'][d.change_class] += 1
                report['documents'].append({'path': str(d.path).replace(os.sep, '/'), **d.payload})
            if limit is not None and report['drafts']['new'] >= limit:
                break
    except BadResumptionToken as e:
        report['status'] = 'soft-fail'
        report['errors'].append(str(e))
    except drift.DriftError as e:
        report['status'] = 'hard-fail'
        report['errors'].append(str(e))
    report['records'] = {k: adapter.counts[k] for k in KINDS + ('filtered',)}
    report['pages'] = adapter.pages
    report['last_until'] = state.get('last_until')         # get-default: unset until a window completes
    report['proposals'] = ['%d new in %s, %d new filtered out; %d revisions and %d metadata updates not re-triaged'
                           % (report['drafts']['new'], ', '.join(adapter.subcategories), adapter.counts['filtered'],
                              adapter.counts['revision'], adapter.counts['metadata-update'])]
    if report['status'] == 'ok' and not report['drafts']['new']:
        report['status'] = 'no-change'
    report['finished_at'] = adapter.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--fixture')
    ap.add_argument('--from', dest='from_', type=date.fromisoformat, help='a cold backfill from this date, by month')
    ap.add_argument('--until', type=date.fromisoformat, default=None)
    a = ap.parse_args(argv)
    until = a.until or datetime.now(timezone.utc).date()
    if a.fixture:
        from ingest.http.fixture import FixtureTransport
        transport = FixtureTransport(a.fixture)
    else:
        transport = NetworkTransport()
    state = new_state()
    if a.from_ and a.from_ == until:
        state['last_until'] = until.isoformat()            # one window, not a backfill
    report = run(ArxivOai(transport, until, backfill_from=a.from_), state)
    print(json.dumps({k: v for k, v in report.items() if k != 'documents'}, indent=2))
    return {'ok': 0, 'no-change': 0, 'hard-fail': 1, 'soft-fail': 4}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
