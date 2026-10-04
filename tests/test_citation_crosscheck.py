"""Tests for ingest/adapters/semantic_scholar.py, the citation cross-check (P4-S2-T10; 06 S3.10-3.11, 12 S6).

These replay the responses tests/fixtures/citations/capture.py recorded on 2026-10-04, with sockets disabled. The
regression case is OpenAlex record W4387561453 (06 S3.10): SWE-bench's DOI under someone else's title, with a
count about 75 times too small. On 2026-10-04 the title it carried had changed again, to "GardenBench: ...",
and the Llama 2 record W4384918448 showed the same defect.
"""
import json
import math
import os
import socket
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.adapters import openalex  # noqa: E402
from ingest.adapters import semantic_scholar as s2  # noqa: E402
from ingest.http.backoff import Response, SoftFail  # noqa: E402
from ingest.http.fixture import FixtureTransport  # noqa: E402
from tools import cli  # noqa: E402

FIX = os.path.join(ROOT, 'tests', 'fixtures', 'citations')
S2_FIX, OA_FIX = os.path.join(FIX, 'semantic-scholar'), os.path.join(FIX, 'openalex')
SWE_BENCH, GPT_4, LLAMA_2, T5 = '2310.06770', '2303.08774', '2307.09288', '1910.10683'
PAPERS = [(a, ('src-%s' % a,)) for a in ('1910.10683', '2005.14165', '2203.15556', GPT_4, LLAMA_2, SWE_BENCH)]
runner = CliRunner()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a test reached for the network')
    monkeypatch.setattr(socket, 'socket', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)


def recorded(directory, arxiv):
    with open(os.path.join(directory, arxiv + '.body'), 'rb') as f:
        body = f.read()
    with open(os.path.join(directory, arxiv + '.body.headers.json'), encoding='utf-8') as f:
        status = json.load(f)['status']
    return json.loads(body) if status == 200 else None


def figure(arxiv):
    return s2.crosscheck(arxiv, ('src-x',), recorded(S2_FIX, arxiv), recorded(OA_FIX, arxiv), '2026-10-04')


@pytest.fixture(scope='module')
def report():
    return s2.run(FixtureTransport(S2_FIX), FixtureTransport(OA_FIX), papers=PAPERS)


# ---- the regression fixture: W4387561453 -----------------------------------------------------------------

def test_w4387561453_is_the_openalex_record_for_the_swe_bench_doi():
    oa = recorded(OA_FIX, SWE_BENCH)
    assert oa['id'] == 'https://openalex.org/W4387561453'
    assert oa['doi'] == 'https://doi.org/10.48550/arxiv.2310.06770'
    assert not s2.same_title(oa['display_name'], 'SWE-bench: Can Language Models Resolve Real-World GitHub Issues?')


def test_the_wrong_title_record_does_not_corroborate_and_the_figure_is_single_source():
    f = figure(SWE_BENCH)
    assert f.counts == {'semantic_scholar': 4090, 'openalex': 55}           # both kept, for the audit
    assert f.corroborating == ('semantic_scholar',) and f.single_source is True
    assert f.value == 4090 and f.records['openalex'] == 'https://openalex.org/W4387561453'
    assert len(f.identity_conflicts) == 1 and 'W4387561453 is titled' in f.identity_conflicts[0]


def test_had_the_titles_agreed_the_count_would_still_be_recorded_as_a_disagreement():
    # The other half of the defect, seen on its own: drop the title check and the counts are 74x apart
    s2_rec, oa_rec = recorded(S2_FIX, SWE_BENCH), recorded(OA_FIX, SWE_BENCH)
    f = s2.crosscheck(SWE_BENCH, ('src-x',), s2_rec, {**oa_rec, 'display_name': s2_rec['title']}, '2026-10-04')
    assert f.single_source is False and f.disagreement is True and f.ratio == 74.36


def test_a_second_record_with_the_same_defect_is_caught_the_same_way():
    f = figure(LLAMA_2)
    assert f.single_source is True and 'W4384918448 is titled' in f.identity_conflicts[0]


# ---- the other cases -------------------------------------------------------------------------------------

def test_a_paper_openalex_does_not_index_under_its_arxiv_doi_is_single_source():
    f = figure(GPT_4)                                      # 06 S3.10: GET /works/doi:10.48550/arXiv.2303.08774 is 404
    assert recorded(OA_FIX, GPT_4) is None
    assert f.counts['openalex'] is None and f.single_source is True and f.value == 27510 and f.ratio is None


def test_two_records_of_the_same_paper_corroborate_and_a_gap_above_2x_is_recorded_not_resolved():
    f = figure(T5)
    assert f.corroborating == ('semantic_scholar', 'openalex') and f.single_source is False
    assert f.identity_conflicts == () and f.disagreement is True and f.ratio == 7.46
    assert f.value == 27544                               # S2's count is the value; OpenAlex's stays beside it


def test_counts_within_2x_are_not_a_disagreement():
    f = s2.crosscheck('1234.56789', (), {'paperId': 'p', 'title': 'A Paper', 'citationCount': 100,
                                         'externalIds': {'ArXiv': '1234.56789'}},
                      {'id': 'W1', 'display_name': 'A paper', 'cited_by_count': 51}, '2026-10-04')
    assert f.single_source is False and f.ratio == 1.96 and f.disagreement is False


def test_a_zero_beside_a_nonzero_count_is_a_disagreement_that_serialises():
    f = s2.crosscheck('1234.56789', (), {'paperId': 'p', 'title': 'A Paper', 'citationCount': 9},
                      {'id': 'W1', 'display_name': 'A Paper', 'cited_by_count': 0}, '2026-10-04')
    assert f.ratio == math.inf and f.disagreement is True and f.to_json()['ratio'] is None


def test_a_semantic_scholar_record_for_another_arxiv_id_does_not_count():
    f = s2.crosscheck('1234.56789', (), {'paperId': 'p', 'title': 'A Paper', 'citationCount': 9,
                                         'externalIds': {'ArXiv': '9999.99999'}},
                      {'id': 'W1', 'display_name': 'A Paper', 'cited_by_count': 8}, '2026-10-04')
    assert f.corroborating == ('openalex',) and f.single_source is True and f.value == 8


def test_no_count_from_either_aggregator_is_no_figure():
    assert s2.crosscheck('1234.56789', (), None, None, '2026-10-04') is None


def test_a_subtitle_is_the_same_title_and_a_different_title_is_not():
    assert s2.same_title('SWE-bench', 'SWE-bench: Can Language Models Resolve Real-World GitHub Issues?')
    assert not s2.same_title('SWE-bench', 'SWE-benchmarks revisited')
    assert not s2.same_title('', 'Anything')


def test_identity_maps_the_ids_and_drops_an_empty_pdf_link():
    got = s2.identity(recorded(S2_FIX, SWE_BENCH))
    assert got['arxiv'] == SWE_BENCH and got['corpus_id'] == 263829697 and got['doi'] == '10.48550/arXiv.2310.06770'
    assert s2.identity(recorded(S2_FIX, GPT_4))['pdf_url'] is None


# ---- single_source cannot be left off ---------------------------------------------------------------------

def test_single_source_is_computed_and_cannot_be_passed():
    with pytest.raises(TypeError):
        s2.CitationFigure('1', (), 'd', {'semantic_scholar': 1, 'openalex': None}, {}, ('semantic_scholar',),
                          single_source=False)


def test_a_figure_with_no_corroborating_count_cannot_be_built():
    with pytest.raises(ValueError, match='at least one'):
        s2.CitationFigure('1', (), 'd', {'semantic_scholar': None, 'openalex': None}, {}, ())
    with pytest.raises(ValueError, match='no count'):
        s2.CitationFigure('1', (), 'd', {'semantic_scholar': None, 'openalex': None}, {}, ('openalex',))


@pytest.mark.parametrize('edit, message', [
    (lambda d: d.pop('single_source'), 'states single_source'),
    (lambda d: d.update(single_source=False), 'single_source is False but 1 aggregator'),
    (lambda d: d.update(corroborating=['semantic_scholar', 'openalex']), None),   # openalex has a count: now 2
])
def test_check_figure_refuses_a_serialised_figure_whose_flag_does_not_follow(edit, message):
    d = figure(SWE_BENCH).to_json()
    edit(d)
    if message:
        with pytest.raises(ValueError, match=message):
            s2.check_figure(d)
    else:
        with pytest.raises(ValueError, match='single_source is True but 2'):
            s2.check_figure(d)


def test_every_figure_the_run_emits_passes_the_check(report):
    assert report['figures'] and all(s2.check_figure(d) is None for d in report['figures'])
    assert {d['arxiv'] for d in report['figures'] if d['single_source']} == {GPT_4, LLAMA_2, SWE_BENCH}


# ---- the run, the keys, the statuses ----------------------------------------------------------------------

def test_the_recorded_run(report):
    assert report['status'] == 'ok' and report['errors'] == [] and report['unresolved'] == 0
    assert report['candidates_seen'] == 6 and report['drafts']['metrics-only'] == 6
    assert sum(report['drafts'].values()) == 6
    assert report['allowance']['X-RateLimit-Cost-USD'] == '0'      # a singleton lookup by DOI is free


def test_candidates_are_the_distinct_arxiv_dois_of_the_source_records():
    got = dict(s2.candidates(ROOT))
    assert SWE_BENCH in got and set(got[SWE_BENCH]) >= {'src-swebench-arxiv-abs', 'src-swebench-arxiv-html'}
    assert all(len(set(v)) == len(v) for v in got.values()) and list(got) == sorted(got)


def test_no_url_carries_a_key():
    assert 'key' not in s2.paper_url(SWE_BENCH) and 'key' not in openalex.work_url(s2.arxiv_doi(SWE_BENCH))
    assert 'tldr' not in s2.paper_url(SWE_BENCH)                   # 06 S3.11: a generated summary is never asked for
    for d in (S2_FIX, OA_FIX):
        for n in os.listdir(d):
            if n.endswith('.headers.json'):
                assert 'key' not in json.load(open(os.path.join(d, n), encoding='utf-8'))['url']


def test_the_semantic_scholar_key_travels_in_a_header_and_requests_are_a_second_apart(monkeypatch):
    seen, clock = [], [0.0]

    class Answer:
        status, headers = 200, {}

        def read(self):
            return b'{}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen.append((req.full_url, req.get_header('X-api-key')))
        return Answer()
    monkeypatch.setattr(s2.urllib.request, 'urlopen', fake_urlopen)
    slept = []
    t = s2.NetworkTransport('k3y', clock=lambda: clock[0], sleep=slept.append)
    t.get(s2.paper_url(SWE_BENCH), {})
    t.get(s2.paper_url(GPT_4), {})
    assert [k for _, k in seen] == ['k3y', 'k3y'] and all('k3y' not in u for u, _ in seen)
    assert slept == [s2.MIN_INTERVAL]


class Fixed:
    def __init__(self, status):
        self.r = Response(status, [], b'{}')

    def get(self, url, headers):
        return self.r


class Exhausted:
    def get(self, url, headers):
        raise SoftFail('429 after 3 attempts', Response(429, [], b''), 3)


def test_a_rate_limit_that_outlasts_the_retries_is_a_soft_fail():
    report = s2.run(Exhausted(), Fixed(200), papers=PAPERS)
    assert report['status'] == 'soft-fail' and report['candidates_seen'] == 1
    assert report['errors'] == ['arXiv 1910.10683: Semantic Scholar answered 429 after 3 attempts; the next run resumes']
    assert s2.run(Fixed(200), Exhausted(), papers=PAPERS)['errors'][0].startswith('arXiv 1910.10683: OpenAlex answered')


def test_a_refused_key_is_a_hard_fail_with_a_human_action():
    report = s2.run(Fixed(403), Fixed(200), papers=PAPERS)
    assert report['status'] == 'hard-fail' and 'refused or revoked' in report['errors'][0]


def test_openalex_institution_run_turns_an_exhausted_retry_into_a_soft_fail():
    report = openalex.run(Exhausted())
    assert report['status'] == 'soft-fail' and 'daily budget' in report['errors'][0]


def test_the_command_replays_the_fixtures(monkeypatch):
    monkeypatch.setattr(s2, 'candidates', lambda root=None: iter(PAPERS))
    r = runner.invoke(cli.app, ['ingest', 'semantic-scholar', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 0, r.output
    assert 'metrics-only  6' in r.output and 'W4387561453 is titled' in r.output and '[single source]' in r.output


def test_no_network_without_a_fixture_exits_2():
    r = runner.invoke(cli.app, ['ingest', 'semantic-scholar', '--dry-run', '--no-network'])
    assert r.exit_code == 2 and 'needs --fixture' in r.output
