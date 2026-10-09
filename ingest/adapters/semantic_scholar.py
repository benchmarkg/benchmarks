#!/usr/bin/env python3
"""The Semantic Scholar adapter, and the citation cross-check against OpenAlex (P4-S2-T10; 06 S3.10-3.11, 12 S6).

    bench ingest semantic-scholar --dry-run --limit 20     # live; SEMANTIC_SCHOLAR_API_KEY, OPENALEX_API_KEY
    bench ingest semantic-scholar --dry-run --fixture tests/fixtures/citations

06 S3.11's split: Semantic Scholar for arXiv-to-paper identity, the half OpenAlex resolves worst, and OpenAlex
for institutions (ingest/adapters/openalex.py). Citation counts come from both and are cross-checked. For every
arXiv paper a Source record cites (a Source whose doi is arXiv's 10.48550/arXiv.<id>), one Semantic Scholar
lookup by arXiv id and one OpenAlex lookup by DOI -- a singleton, which costs OpenAlex 0 credits -- give at most
two counts, and crosscheck() turns them into one CitationFigure:

  - Two counts corroborate each other only when both records are the same paper: Semantic Scholar's arXiv id is
    ours, and OpenAlex's title agrees with Semantic Scholar's. OpenAlex record W4387561453 is why the title is
    compared: it carries SWE-bench's DOI and someone else's title, and a count about 75 times too small
    (06 S3.10; the regression fixture in tests/test_citation_crosscheck.py).
  - A figure only one aggregator supports is `single_source: true` (12 S6: rendered with a visible
    "single source, unverified" marker). CitationFigure refuses to be built otherwise, and check_figure()
    refuses a serialised one, so a single-aggregator figure cannot be emitted without the flag.
  - Two counts more than 2x apart are `disagreement: true`: recorded, not resolved (06 S3.11).
  - The figure's `value` is Semantic Scholar's count when it has one -- 06 S3.11's "generally cleaner citation
    counts" -- and OpenAlex's otherwise; both counts are kept beside it.

What the first full live run found (2026-10-04, all 44 arXiv papers the Source records cite). 39 have a count
from both aggregators under the same title; 38 of them differ by more than 2x and the 39th is 0 from both. In 31
OpenAlex is lower by 2.9x to 135x, and in 6 more it reads 0 against Semantic Scholar's 1 to 430: its record under
the arXiv DOI appears to count only citations of the preprint record. The one the other way is Semantic
Scholar's: 0 for DeepSeek-V3 (2412.19437) against OpenAlex's 268, so preferring Semantic Scholar's count is a
default, not a verdict, and `disagreement` is what says so. One more OpenAlex record had W4387561453's defect --
W4384918448 is Llama 2's DOI under an ICU-simulation paper's title -- and OpenAlex had nothing under three
papers' arXiv DOIs (GPT-4 among them), so 5 of the 44 figures are single-source.

Counts are metrics, not curated data: they belong in metrics/ (12 S6), outside the DOI'd release, and are the
'metrics-only' change class. `tldr` is never requested (06 S3.11: a generated summary is never a citable field).

Keys. SEMANTIC_SCHOLAR_API_KEY travels in the x-api-key header and OPENALEX_API_KEY is appended to the URL, both
inside the network transports and nowhere else, so recorded URLs, reports and errors never carry either.
Semantic Scholar's keyed limit is 1 request a second on all endpoints (06 S3.11); its responses carry no
rate-limit headers, so the transport spaces requests itself.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ingest.adapters import openalex
from ingest.http import policy
from ingest.http.backoff import Response, SoftFail, retry
from ingest.resolve import normalise

NAME = 'semantic-scholar'
VERSION = '0.1.0'
API = 'https://api.semanticscholar.org/graph/v1'
USER_AGENT = openalex.USER_AGENT
MIN_INTERVAL = 1.05         # seconds: the keyed limit is 1 RPS on all endpoints (06 S3.11)
FIELDS = 'paperId,title,year,venue,citationCount,externalIds,openAccessPdf'
DISAGREEMENT = 2.0          # 06 S3.11: "a disagreement above 2x is recorded, not resolved"
CHANGE_CLASSES = openalex.CHANGE_CLASSES
AGGREGATORS = ('semantic_scholar', 'openalex')
ROOT = openalex.ROOT
_ARXIV_DOI = re.compile(r'10\.48550/arxiv\.(\d{4}\.\d{4,5})', re.I)


class NetworkTransport:
    """GET over urllib with 07 S4.2's retry policy, one request a second. The key goes in a header, here only."""

    def __init__(self, key: str | None = None, timeout: int = 60, clock=time.monotonic, sleep=time.sleep, gate=None):
        self.key, self.timeout, self.clock, self.sleep = key, timeout, clock, sleep
        self.gate = gate or policy.gate()                # 07 S10.1: ingest/policy.yaml, robots.txt, no-collect
        self._not_before = 0.0

    def _once(self, url, headers):
        self.gate.admit(url)
        wait = self._not_before - self.clock()
        if wait > 0:
            self.sleep(wait)
        sent = {'User-Agent': USER_AGENT, 'Accept': 'application/json', **headers}
        if self.key:
            sent['x-api-key'] = self.key
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=sent), timeout=self.timeout) as r:
                resp = Response(r.status, list(r.headers.items()), r.read())
        except urllib.error.HTTPError as e:
            resp = Response(e.code, list(e.headers.items()), e.read())
        resp.received_at = self.clock()
        self._not_before = resp.received_at + MIN_INTERVAL
        return resp

    def get(self, url, headers):
        return retry(lambda: self._once(url, headers), clock=self.clock, sleep=self.sleep)


def paper_url(arxiv: str) -> str:
    """The Semantic Scholar paper lookup by native arXiv id: no DOI guessing (06 S3.11)."""
    return '%s/paper/arXiv:%s?%s' % (API, arxiv, urllib.parse.urlencode({'fields': FIELDS}))


def arxiv_doi(arxiv: str) -> str:
    return '10.48550/arXiv.%s' % arxiv


def candidates(root: str = ROOT):
    """(arXiv id, the Source ids that cite it), one per distinct paper, from every Source with an arXiv DOI."""
    from schema.taxonomy import read_yaml
    papers: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '**', '*.yaml'), recursive=True)):
        rec = read_yaml(path)
        m = _ARXIV_DOI.fullmatch(rec.get('doi') or '')                  # get-default: most sources have no doi
        if m:
            papers.setdefault(m.group(1), []).append(rec['id'])
    for arxiv in sorted(papers):
        yield arxiv, tuple(papers[arxiv])


def identity(paper: dict) -> dict:
    """What Semantic Scholar says the paper is (06 S3.11's mapping): its ids, title, year, venue and PDF link."""
    ids = paper.get('externalIds') or {}
    pdf = (paper.get('openAccessPdf') or {}).get('url') or None      # get-default: a paper may have no PDF
    return {'s2_paper_id': paper.get('paperId'), 'corpus_id': ids.get('CorpusId'), 'arxiv': ids.get('ArXiv'),
            'doi': ids.get('DOI'), 'title': paper.get('title'), 'year': paper.get('year'),
            'venue': paper.get('venue') or None, 'pdf_url': pdf}


def same_title(a: str | None, b: str | None) -> bool:
    """Equal once normalised, or one is the other with a subtitle: 'X' and 'X: Y' are one paper."""
    a, b = normalise(a or ''), normalise(b or '')
    return bool(a and b) and (a == b or a.startswith(b + ' ') or b.startswith(a + ' '))


@dataclass(frozen=True)
class CitationFigure:
    """One paper's citation count, as the cross-check leaves it. `single_source` is computed, never passed."""
    arxiv: str
    sources: tuple[str, ...]
    observed_on: str
    counts: dict                    # {'semantic_scholar': int | None, 'openalex': int | None}, as each reported
    records: dict                   # {'semantic_scholar': paperId | None, 'openalex': W-id | None}
    corroborating: tuple[str, ...]  # the aggregators whose count describes this paper
    value: int | None = field(init=False)
    single_source: bool = field(init=False)
    ratio: float | None = field(init=False)
    disagreement: bool = field(init=False)
    identity_conflicts: tuple[str, ...] = ()

    def __post_init__(self):
        usable = [a for a in AGGREGATORS if a in self.corroborating]
        if not usable:
            raise ValueError('%s: a figure needs at least one aggregator count' % self.arxiv)
        for a in usable:
            if not isinstance(self.counts.get(a), int):
                raise ValueError('%s: %s corroborates with no count' % (self.arxiv, a))
        vals = [self.counts[a] for a in usable]
        ratio = None
        if len(vals) == 2:
            lo, hi = min(vals), max(vals)
            ratio = round(hi / lo, 2) if lo else (1.0 if hi == 0 else math.inf)
        object.__setattr__(self, 'value', self.counts[usable[0]])
        object.__setattr__(self, 'single_source', len(usable) < 2)
        object.__setattr__(self, 'ratio', ratio)
        object.__setattr__(self, 'disagreement', ratio is not None and ratio > DISAGREEMENT)

    def to_json(self) -> dict:
        d = asdict(self)
        d['sources'], d['corroborating'] = list(self.sources), list(self.corroborating)
        d['identity_conflicts'] = list(self.identity_conflicts)
        if d['ratio'] == math.inf:
            d['ratio'] = None           # JSON has no infinity; one count was 0 and the other was not
        check_figure(d)
        return d


def check_figure(d: dict) -> None:
    """Refuse a serialised figure whose single_source flag is missing or does not follow from its counts."""
    if 'single_source' not in d:
        raise ValueError('%s: a citation figure states single_source (12 S6)' % d.get('arxiv'))
    usable = [a for a in d.get('corroborating') or [] if isinstance((d.get('counts') or {}).get(a), int)]
    if not usable:
        raise ValueError('%s: a citation figure with no aggregator count' % d.get('arxiv'))
    if d['single_source'] is not (len(usable) < 2):
        raise ValueError('%s: single_source is %r but %d aggregator(s) support the figure (%s)'
                         % (d.get('arxiv'), d['single_source'], len(usable), ', '.join(usable)))


def crosscheck(arxiv: str, sources, s2: dict | None, oa: dict | None, observed_on: str) -> CitationFigure | None:
    """One figure from what each aggregator returned for the paper (None where it had no record); None when
    neither has a count."""
    counts = {'semantic_scholar': (s2 or {}).get('citationCount'), 'openalex': (oa or {}).get('cited_by_count')}
    records = {'semantic_scholar': (s2 or {}).get('paperId'), 'openalex': (oa or {}).get('id')}
    conflicts, usable = [], []
    if s2 is not None and isinstance(counts['semantic_scholar'], int):
        got = ((s2.get('externalIds') or {}).get('ArXiv') or '')      # get-default: S2 may lack the id
        if got and got != arxiv:
            conflicts.append('semantic_scholar: arXiv %s, not %s' % (got, arxiv))
        else:
            usable.append('semantic_scholar')
    if oa is not None and isinstance(counts['openalex'], int):
        s2_title = (s2 or {}).get('title')
        if s2_title and not same_title(oa.get('display_name'), s2_title):
            conflicts.append('openalex: %s is titled %r, not %r' % (oa.get('id'), oa.get('display_name'), s2_title))
        else:
            usable.append('openalex')
    if not usable:
        return None
    return CitationFigure(arxiv, tuple(sources), observed_on, counts, records, tuple(usable),
                          identity_conflicts=tuple(conflicts))


def _json(r) -> dict | None:
    return json.loads(r.body) if r.status == 200 else None


def run(s2_transport, oa_transport, *, limit: int | None = None, papers=None, root: str = ROOT,
        now=lambda: datetime.now(timezone.utc)) -> dict:
    """One dry run: per paper, a Semantic Scholar and an OpenAlex lookup, then the cross-check. Writes nothing."""
    started = now()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': started.strftime('%Y-%m-%dT%H:%M:%SZ'),
              'status': 'ok', 'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'unresolved': 0,
              'errors': [], 'snapshot': None, 'proposals': [], 'figures': [], 'allowance': {}}
    observed_on = started.strftime('%Y-%m-%d')
    for i, (arxiv, sources) in enumerate(papers if papers is not None else candidates(root)):
        if limit is not None and i >= limit:
            break
        report['candidates_seen'] += 1
        try:
            who = 'Semantic Scholar'
            r = s2_transport.get(paper_url(arxiv), {})        # get-default: an HTTP GET with request headers
            who = 'OpenAlex'
            o = oa_transport.get(openalex.work_url(arxiv_doi(arxiv)), {})  # get-default: an HTTP GET, as above
        except SoftFail as e:
            report['status'] = 'soft-fail'
            report['errors'].append('arXiv %s: %s answered %s; the next run resumes' % (arxiv, who, e.reason))
            break
        report['allowance'] = openalex.allowance(o)
        bad = [(who, x.status) for who, x in (('Semantic Scholar', r), ('OpenAlex', o)) if x.status not in (200, 404)]
        if bad:
            report['status'] = 'hard-fail'
            refused = ' -- the key was refused or revoked; a person replaces it (06 S3.11)'
            report['errors'] += ['arXiv %s: %s HTTP %d%s' % (arxiv, who, st, refused if st in (401, 403) else '')
                                 for who, st in bad]
            break
        s2, oa = _json(r), _json(o)
        fig = crosscheck(arxiv, sources, s2, oa, observed_on)
        if fig is None:
            report['unresolved'] += 1
            report['proposals'].append('arXiv %s: no citation count from either aggregator (%s)'
                                       % (arxiv, ', '.join(sources)))
            continue
        report['drafts']['metrics-only'] += 1
        report['figures'].append(fig.to_json())
        report['proposals'].append(describe(fig))
    if report['status'] == 'ok' and not report['figures']:
        report['status'] = 'no-change'
    report['finished_at'] = now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return report


def describe(fig: CitationFigure) -> str:
    c = fig.counts
    line = 'arXiv %s: %s citations (S2 %s, OpenAlex %s)' % (fig.arxiv, fig.value, c['semantic_scholar'], c['openalex'])
    flags = (['single source'] if fig.single_source else []) + (['>2x apart'] if fig.disagreement else [])
    line += ' [%s]' % ', '.join(flags) if flags else ''
    return line + ''.join('; %s' % x for x in fig.identity_conflicts)


def key_from_env() -> str | None:
    return os.environ.get('SEMANTIC_SCHOLAR_API_KEY') or None
