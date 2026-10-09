"""The arXiv OAI-PMH adapter (P5-S5-T04; 06 S3.4, S5, S9.6; 07 S10.1).

The verify: `pytest tests/ingest/test_arxiv_oai.py`. Done when "A captured window containing a v2 resubmission is
harvested, revisions are distinguished from new papers, and the throttle is enforced by the fetcher rather than
by discipline". The captured window is tests/ingest/fixtures/arxiv/: records from the 2026-10-06 set=cs harvest,
verbatim, over two pages joined by a resumptionToken. So:

  - the window is harvested page by page through the token, and last_until advances only when it ends;
  - a v2 resubmission of an old paper is a `revision`, a v1-only recent paper is `new`, and an old paper whose
    metadata changed is a `metadata-update`; only `new` papers in the wanted subcategories become candidates,
    filtered by header setSpec;
  - a candidate is 06 S1.1's shape and passes the schema and metadata-only gates: no abstract in it;
  - the 1 request / 3 s throttle is the gate's, measured on the network transport, and http:// is refused;
  - the failure case: badResumptionToken is a soft fail that resumes from the persisted last_until, never from
    earliestDatestamp; anything that is not OAI-PMH is drift, a hard fail.
"""
import os
from datetime import date, datetime, timezone

import pytest
from typer.testing import CliRunner

from ingest.adapters import arxiv_oai as A
from ingest.adapters.base import Adapter
from ingest.gates import checks
from ingest.http import policy as P
from ingest.http.backoff import Response
from ingest.http.fixture import FixtureTransport

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'arxiv')
DAY = date(2026, 10, 6)
NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)


def adapter(transport=None, until=DAY, **kw):
    return A.ArxivOai(transport or FixtureTransport(FIX), until, now=lambda: NOW, **kw)


def one_day():
    return dict(A.new_state(), last_until=DAY.isoformat())


@pytest.fixture(scope='module')
def harvest():
    t = FixtureTransport(FIX)
    state = one_day()
    a = adapter(t)
    records = [(c, a.fetch(c, state)) for c in a.discover(state)]
    return a, state, t, records


# ---- the captured window ----------------------------------------------------------------------------------------

def test_the_window_is_harvested_page_by_page_through_the_resumption_token(harvest):
    a, state, t, records = harvest
    assert [u for u, _ in t.requests] == [
        A.list_url((DAY, DAY)), 'https://oaipmh.arxiv.org/oai?verb=ListRecords&resumptionToken=fixture-set-cs-2026-10-06-p2']
    assert len(records) == 100 and a.pages == 2
    assert state['last_until'] == '2026-10-06' and state['checkpoint'] is None


def test_a_v2_resubmission_of_an_old_paper_is_a_revision_not_a_new_paper(harvest):
    _, _, _, records = harvest
    old_revised = [c for c, _ in records if c.hint['kind'] == 'revision'
                   and c.hint['record']['versions'][0]['date'] < '2025-01-01']
    assert old_revised, 'the captured window holds a resubmission of a paper first posted before 2025'
    c = old_revised[0]
    assert len(c.hint['record']['versions']) >= 2 and c.hint['record']['versions'][-1]['date'] >= '2026-09-22'
    assert dict(harvest[0].counts) == {'metadata-update': 43, 'revision': 37, 'new': 20, 'filtered': 6}


def test_only_new_papers_in_the_wanted_subcategories_become_candidates(harvest):
    _, _, _, records = harvest
    made = [(c, p) for c, p in records if p is not None]
    assert len(made) == 14
    assert all(c.hint['kind'] == 'new' and A.wanted(c.hint['record']) for c, _ in made)
    assert all(p is None for c, p in records if c.hint['kind'] != 'new')


@pytest.mark.parametrize('versions,kind', [
    ([('v1', '2026-10-02')], 'new'),
    ([('v1', '2026-09-22')], 'new'),                     # the edge of LAG_DAYS
    ([('v1', '2026-09-21')], 'metadata-update'),
    ([('v1', '2013-04-11'), ('v2', '2026-10-03')], 'revision'),
    ([('v1', '2026-09-30'), ('v2', '2026-10-05')], 'revision'),
    ([('v1', '2015-06-15'), ('v2', '2015-06-18')], 'metadata-update'),
])
def test_classify(versions, kind):
    rec = {'deleted': False, 'versions': [{'version': v, 'date': d} for v, d in versions]}
    assert A.classify(rec, DAY) == kind
    assert A.classify({'deleted': True}, DAY) == 'deleted'


def test_the_subcategory_filter_reads_the_header_setspecs():
    assert A.wanted({'sets': ['cs:cs:CL', 'stat:stat:ML']})
    assert not A.wanted({'sets': ['cs:cs:CR']})
    assert A.wanted({'sets': ['cs:cs:CR']}, subcategories=('cs:cs:CR',))


# ---- the candidates ---------------------------------------------------------------------------------------------

def test_candidates_are_06_s1_1s_shape_and_pass_the_discovery_gates(harvest):
    a, _, _, records = harvest
    for c, p in records:
        if p is None:
            continue
        [draft], unresolved = a.normalise(p)
        assert unresolved == []
        rel = str(draft.path).replace(os.sep, '/')
        assert rel == 'data/_discovery/arxiv/%s.yaml' % draft.payload['candidate_id']
        checks.schema(draft.payload, rel)
        checks.metadata_only(draft.payload, rel)        # no string over 280: the abstract is not in it
        ident = draft.payload['identity']
        assert ident['doi'] == '10.48550/arXiv.' + ident['arxiv_id'] and ident['url'].startswith('https://arxiv.org/abs/')
        assert len(ident['abstract']['sha256']) == 64 and ident['abstract']['chars'] > 0
        assert draft.payload['triage'] is None and draft.payload['discovered_via'] == 'arxiv-oaipmh'
        assert draft.change_class == 'new' and draft.entity_id is None


def test_normalise_is_a_pure_function_of_the_payload(harvest):
    _, _, _, records = harvest
    p = next(p for _, p in records if p is not None)
    assert A.normalise(p) == A.normalise(p)


def test_the_adapter_declares_cc0_metadata_and_retains_its_raw_body():
    assert issubclass(A.ArxivOai, Adapter) and A.ArxivOai.licence == 'CC0-1.0'
    assert A.ArxivOai.raw_retainable is True and A.ArxivOai.tier == 1
    assert A.candidate_id('2610.03818') == 'cand-arxiv-2610-03818'
    assert A.candidate_id('math/0601001') == 'cand-arxiv-math-0601001'


# ---- windows ----------------------------------------------------------------------------------------------------

def test_a_cold_backfill_is_windowed_by_month_and_an_incremental_run_starts_at_last_until():
    assert A.windows({}, date(2026, 3, 10), date(2026, 1, 15)) == [
        (date(2026, 1, 15), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28)), (date(2026, 3, 1), date(2026, 3, 10))]
    assert A.windows({'last_until': '2026-10-01'}, DAY) == [(date(2026, 10, 1), DAY)]
    assert A.windows({'last_until': '2026-10-07'}, DAY) == []


# ---- the throttle is the fetcher's ------------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


def test_the_throttle_is_the_gates_one_request_every_three_seconds(monkeypatch):
    import urllib.request

    pages = [open(os.path.join(FIX, n), 'rb').read() for n in ('set-cs-day.xml', 'set-cs-day-p2.xml')]
    sent = []

    class FakeHTTP:
        def __init__(self, body):
            self.status, self.headers, self.body = 200, {}, body

        def read(self, *a):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        sent.append((clock(), req.full_url))
        return FakeHTTP(pages[len(sent) - 1])
    clock = Clock()
    gate = P.Gate(P.Policy.load(), robots=lambda url, ua: (404, ''), clock=clock, sleep=clock.sleep)
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    a = adapter(A.NetworkTransport(clock=clock, sleep=clock.sleep, gate=gate))
    list(a.discover(one_day()))
    assert P.Policy.load().hosts['oaipmh.arxiv.org'].rate == pytest.approx(1 / 3, rel=1e-3)
    assert [round(b - a_, 1) for (a_, _), (b, _) in zip(sent, sent[1:])] == [3.0]   # paced by the gate, not the adapter
    assert gate.log[0] == ('https://oaipmh.arxiv.org/robots.txt', 'sent')


def test_http_is_refused_before_anything_is_sent():
    with pytest.raises(ValueError, match='HTTPS only'):
        A.NetworkTransport(gate=P.Gate(P.Policy.load(), robots=lambda u, ua: (404, ''))).get(
            'http://oaipmh.arxiv.org/oai?verb=Identify', {})


# ---- failures ---------------------------------------------------------------------------------------------------

class Scripted:
    def __init__(self, bodies):
        self.bodies, self.requests = list(bodies), []

    def get(self, url, headers):
        self.requests.append(url)
        return Response(200, [], self.bodies.pop(0))


def oai_error(code):
    return ('<?xml version="1.0" encoding="UTF-8"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            '<responseDate>2026-10-09T00:00:00Z</responseDate><request verb="ListRecords">https://oaipmh.arxiv.org/oai'
            '</request><error code="%s">x</error></OAI-PMH>' % code).encode()


def test_the_failure_case_bad_resumption_token_soft_fails_and_resumes_from_last_until():
    page1 = open(os.path.join(FIX, 'set-cs-day.xml'), 'rb').read()
    state = dict(A.new_state(), last_until='2026-10-01')
    t = Scripted([page1, oai_error('badResumptionToken')])
    report = A.run(adapter(t), state)
    assert report['status'] == 'soft-fail' and 'badResumptionToken' in report['errors'][0]
    assert state['last_until'] == '2026-10-01' and state['checkpoint'] is None     # not advanced, nothing to resume
    t2 = Scripted([oai_error('noRecordsMatch')])
    A.run(adapter(t2), state)
    assert 'from=2026-10-01&' in t2.requests[0]          # the next run resumes the window, never earliestDatestamp
    assert 'from=2005' not in t2.requests[0]


def test_no_records_match_is_an_empty_window_and_advances_last_until():
    state = dict(A.new_state(), last_until='2026-10-05')
    report = A.run(adapter(Scripted([oai_error('noRecordsMatch')])), state)
    assert report['status'] == 'no-change' and state['last_until'] == '2026-10-06'


@pytest.mark.parametrize('body', [
    b'<html><body>Service unavailable</body></html>',
    b'not xml at all',
    None,                                                # another OAI error code
    b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords><record><header>'
    b'<identifier>oai:arXiv.org:2610.00001</identifier><datestamp>2026-10-06</datestamp></header>'
    b'<metadata><arXivRaw xmlns="http://arxiv.org/OAI/arXivRaw/"><id>2610.00001</id></arXivRaw></metadata>'
    b'</record></ListRecords></OAI-PMH>',               # a record with no versions
])
def test_anything_that_is_not_oai_pmh_list_records_is_drift_a_hard_fail(body):
    report = A.run(adapter(Scripted([body or oai_error('cannotDisseminateFormat')])), one_day())
    assert report['status'] == 'hard-fail' and report['errors'][0].startswith('schema-drift')


def test_a_deleted_record_is_counted_and_never_a_candidate():
    body = (b'<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords><record><header status="deleted">'
            b'<identifier>oai:arXiv.org:2610.00002</identifier><datestamp>2026-10-06</datestamp>'
            b'<setSpec>cs:cs:CL</setSpec></header></record><resumptionToken/></ListRecords></OAI-PMH>')
    a = adapter(Scripted([body]))
    report = A.run(a, one_day())
    assert report['records']['deleted'] == 1 and report['drafts']['new'] == 0


# ---- the command line -------------------------------------------------------------------------------------------

def test_bench_ingest_arxiv_oai_over_the_fixture():
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'arxiv-oai', '--dry-run', '--fixture', FIX, '--since', '2026-10-06'])
    assert r.exit_code == 0, r.output
    assert 'new           14' in r.output and 'revision=37' in r.output and 'metadata-update=43' in r.output
    r = CliRunner().invoke(cli.app, ['ingest', 'arxiv-oai', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 2                              # a fixture needs its day
    r = CliRunner().invoke(cli.app, ['ingest', 'epoch', '--dry-run', '--since', '2026-10-06'])
    assert r.exit_code == 2                              # --since is arxiv-oai's
