"""The CAMEO claims, each pinned to a stated evaluation window (P3-S8-T02; 04-data-model.md S7 and S8).

The verify: "bench validate --tier all, plus a test asserting every CAMEO claim carries an explicit evaluation window
and an archived snapshot URL". The done-when: "Five claims exist, none of which means "current"." CAMEO is a rolling
board: a score is an average over a date range and a server set the reader picks (cameo's refresh_basis), so a
number without its window means "whatever the board says today". cameo3d.org computes those averages in a
server action the page posts, which no archive can capture, and its per-target pages carry the servers' contact
addresses; so each claim reads its window from a table that reproduces a CAMEO comparison over stated dates, on a
PubMed Central table page that names no person and can be archived. Held here as:

  1. The five claims: absolute lDDT on the frozen CAMEO 3D version (cameo@cameo-3d), reported by CAMEO, held-out,
     dated by their paper, not by their window.
  2. Every claim carries an explicit evaluation window: its conditions' subset_used opens with "<first date> to
     <last date>", a closed range of at least a week that ends before date_reported, whose two dates its Source
     states, and nothing in it reads as "current". The failure cases: a window-less subset, an open "latest" one,
     dates the Source does not state, and a window that closes after the claim was reported.
  3. Every claim carries an archived snapshot URL: its Source has archive_status ok and an archive_url that is a
     Wayback capture of its own url, and names no person. The three Sources are pending for the lead's archiver,
     so this test fails until they are captured. What holds now: each Source can be archived (no DOI, no person,
     pending or ok, no address in its extract). The failure cases: a DOI paper, a withheld page, a pending page,
     and a capture of another URL.
  4. Every number is its table's: the passages a claim's notes quote are in its Source's extract, one of them is
     the system's row, and the value is that row's average lDDT moved from CAMEO's 0-100 scale to the metric's
     fraction, digit for digit.
  5. The window is what separates the claims: claims sharing a window and server set share a comparability key,
     the three windows give three keys, and with the window taken out of subset_used all five collide.
  6. Ids are content-derived (05 S2): a claim's over (benchmark, system, metric, subset, value, source,
     date_reported), a condition record's over its fields, with tools/build/comparability.py's canonicalise().
"""
import copy
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import Organization  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, fold, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import llm_run  # noqa: E402

CAMEO = os.path.join(ROOT, 'data', 'benchmarks', 'biology-genetics', 'cameo.yaml')
SHARD = os.path.join(ROOT, 'data', 'claims', 'cameo')
CLAIM_KEYS = ('benchmark', 'system', 'metric', 'subset', 'value', 'source', 'date_reported')
WINDOW = re.compile(r'^(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})\b')
NOW_WORDS = re.compile(r'\b(current|currently|latest|to date|now|today|live|rolling)\b', re.I)
WAYBACK = re.compile(r'^https://web\.archive\.org/web/\d{14}/(\S+)$')
ADDRESS = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b')
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')


def record(kind, ident):
    hits = glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    assert len(hits) == 1, (kind, ident, hits)
    return read_yaml(hits[0])


def source(sid):
    return Source.model_validate(record('sources', sid))


def conditions(cid):
    return EvalConditions.model_validate(record('conditions', cid))


def claim_files():
    return sorted(glob.glob(os.path.join(SHARD, '*.yaml')))


CLAIMS = [ResultClaim.model_validate(read_yaml(p)) for p in claim_files()]


@pytest.fixture(scope='module')
def cameo():
    return load_benchmark(CAMEO)


# ---- 1. the five claims ------------------------------------------------------------------------------------

def test_five_claims_on_the_frozen_cameo_3d_version_and_the_lddt_record(cameo):
    assert len(CLAIMS) == 5
    [version] = [v for v in cameo.versions if v.version == 'cameo-3d']
    assert version.frozen is True and version.superseded_by == 'complexes'   # not the board as it runs today
    lddt = Metric.model_validate(record('metrics', 'lddt'))
    for c in CLAIMS:
        assert (c.benchmark, c.subset, c.metric, c.claim_type) == ('cameo@cameo-3d', None, 'lddt', 'absolute'), c.id
        assert lddt.range.min <= c.value <= lddt.range.max, c.id
    assert len({c.system for c in CLAIMS}) == 5                         # no (benchmark, system, metric) group forms


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_each_claim_is_cameos_held_out_score_dated_by_its_paper(claim):
    assert (claim.reported_by, claim.verification) == ('org-cameo', 'held-out-server')
    Organization.model_validate(record('organizations', claim.reported_by))
    System.model_validate(record('systems', claim.system))
    assert claim.date_reported == source(claim.source).published
    assert llm_run.llm_run(claim.system) is False
    assert claim.superseded_by is None and claim.result_group is None


# ---- 2. every claim carries an explicit evaluation window ----------------------------------------------------

def stated(day, extract):
    """Whether a Source's extract states `day`, in ISO form (with the hyphens or en dashes tables use) or as
    "D Month YYYY"."""
    iso = day.isoformat()
    forms = (iso, iso.replace('-', '–', 1), iso.replace('-', '–'), '%d %s %d' % (day.day, MONTHS[day.month - 1],
                                                                                    day.year))
    text = fold(extract or '')
    return any(fold(f) in text for f in forms)


def window(cond):
    m = WINDOW.match(cond.subset_used or '')
    return (dt.date.fromisoformat(m.group(1)), dt.date.fromisoformat(m.group(2))) if m else None


def window_problems(claim, cond, src):
    """Why a claim's evaluation window is not explicit and fixed (empty when it is)."""
    w = window(cond)
    if w is None:
        return ['no evaluation window']
    start, end = w
    out = []
    if (end - start).days < 6:
        out.append('a window under a week')
    if end >= claim.date_reported:
        out.append('the window does not close before date_reported')
    out += ['%s is not stated in %s' % (d, src.id) for d in (start, end) if not stated(d, src.quote_extract)]
    if NOW_WORDS.search(cond.subset_used):
        out.append('reads as current')
    return out


def by_record(c):
    return conditions(c.eval_conditions)


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_every_claim_carries_an_explicit_evaluation_window(claim):
    assert window_problems(claim, by_record(claim), source(claim.source)) == []


def test_verify_a_missing_open_unstated_or_late_window_is_refused():
    c = CLAIMS[0]
    cond, src = by_record(c), source(c.source)
    rest = cond.subset_used.split(':', 1)[1]

    def swap(text):
        return cond.model_copy(update={'subset_used': text})
    assert window_problems(c, swap('the 172-target common subset' + rest), src) == ['no evaluation window']
    assert window_problems(c, swap(cond.subset_used + ', the latest weeks'), src) == ['reads as current']
    assert window_problems(c, swap('2024-01-06 to 2025-06-14:' + rest), src) == [
        'the window does not close before date_reported', '2024-01-06 is not stated in %s' % src.id,
        '2025-06-14 is not stated in %s' % src.id]
    late = c.model_copy(update={'date_reported': window(cond)[1]})
    assert window_problems(late, cond, src) == ['the window does not close before date_reported']


def test_the_window_is_not_date_reported():
    """The windows close months before their papers appear, so date_reported alone would misdate every claim."""
    for c in CLAIMS:
        assert (c.date_reported - window(by_record(c))[1]).days > 60, c.id
    assert len({window(by_record(c)) for c in CLAIMS}) == 3


# ---- 3. every claim carries an archived snapshot URL ---------------------------------------------------------

def snapshot_problems(s):
    """Why a Source is not an archived snapshot of the page a claim reads (empty when it is one)."""
    out = []
    if s.doi:
        out.append('a DOI, not a snapshot')
    if s.archive_status != 'ok':
        out.append('archive_status %s' % s.archive_status)
    m = WAYBACK.match(s.archive_url or '')
    if not s.archive_url:
        out.append('no archive_url')
    elif not m or m.group(1).rstrip('/') != s.url.rstrip('/'):
        out.append('archive_url is not a capture of %s' % s.url)
    if s.contains_personal_data is not False:
        out.append('names people')
    return out


def archivable_problems(s):
    """Why a Source could never become such a snapshot (empty when the lead's archiver can capture it)."""
    out = []
    if s.doi:
        out.append('a DOI')
    if s.contains_personal_data is not False or s.archive_status == 'withheld':
        out.append('withheld for personal data')
    if s.archive_status not in ('pending', 'ok'):
        out.append('archive_status %s' % s.archive_status)
    if ADDRESS.search(s.quote_extract or ''):
        out.append('an address in the extract')
    return out


SOURCE_IDS = sorted({c.source for c in CLAIMS})


@pytest.mark.parametrize('sid', SOURCE_IDS)
def test_verify_every_claim_carries_an_archived_snapshot_url(sid):
    """Fails until the lead's archiver has captured the pending table pages; then each holds its window."""
    assert snapshot_problems(source(sid)) == []


@pytest.mark.parametrize('sid', SOURCE_IDS)
def test_each_source_is_a_page_the_archiver_can_capture(sid):
    s = source(sid)
    assert archivable_problems(s) == []
    assert s.archive_status in ('pending', 'ok') and s.failure_reason is None and 'cameo' in s.cited_by
    assert s.url.startswith('https://pmc.ncbi.nlm.nih.gov/articles/PMC') and '/table/' in s.url


def test_verify_a_doi_a_withheld_a_pending_or_a_foreign_capture_is_refused():
    paper = source('src-cameo-2025-proteins')
    assert snapshot_problems(paper) == ['a DOI, not a snapshot', 'archive_status not-required', 'no archive_url']
    assert archivable_problems(paper) == ['a DOI', 'archive_status not-required']
    page = source(SOURCE_IDS[0])
    if page.archive_status == 'pending':
        assert snapshot_problems(page) == ['archive_status pending', 'no archive_url']
    withheld = page.model_copy(update={'archive_status': 'withheld', 'contains_personal_data': True,
                                       'failure_reason': 'the body names people', 'archive_url': None})
    assert archivable_problems(withheld) == ['withheld for personal data', 'archive_status withheld']
    assert snapshot_problems(withheld) == ['archive_status withheld', 'no archive_url', 'names people']
    site = source('src-cameo-site')                                  # an archived page: its capture is its own url
    assert snapshot_problems(site) == []
    elsewhere = site.model_copy(update={'url': 'https://cameo3d.org/target/2025-01-04_00000001'})
    assert snapshot_problems(elsewhere) == ['archive_url is not a capture of %s' % elsewhere.url]


# ---- 4. every number is its table's --------------------------------------------------------------------------

def quotes(claim):
    return re.findall(r'"([^"]+)"', claim.notes or '')


def row_value(claim):
    """The average lDDT in the quoted row that opens with the system's name: the row's last number."""
    name = System.model_validate(record('systems', claim.system)).name
    [row] = [q for q in quotes(claim) if q.startswith(name + ' ')]
    return re.findall(r'\d+\.\d+', row)[-1]


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_every_passage_a_claims_notes_quote_is_in_its_source(claim):
    qs = quotes(claim)
    assert len(qs) >= 4, claim.id
    assert [q for q in qs if not quote_found(q, source(claim.source).quote_extract)] == []


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_each_value_is_its_rows_average_lddt_as_a_fraction(claim):
    assert '%.2f' % (claim.value * 100) == row_value(claim)


def test_an_unscaled_or_misread_value_is_refused():
    c = CLAIMS[0]
    assert '%.2f' % (float(row_value(c)) * 100) != row_value(c)     # left on CAMEO's 0-100 scale
    assert '%.2f' % (c.value * 100 + 0.01) != row_value(c)


# ---- 5. the window separates the claims ----------------------------------------------------------------------

def keys(resolution, cond_of):
    return {c.id: comp.compute_for_claim(c, resolution, cond_of(c)).comparability_key for c in CLAIMS}


def test_claims_share_a_key_exactly_when_they_share_a_window(cameo):
    r = comp.resolve_profile(cameo)
    assert set(r.material) == {'selection_strategy', 'subset_used'}
    got = keys(r, by_record)
    for a in CLAIMS:
        for b in CLAIMS:
            assert (got[a.id] == got[b.id]) == (a.eval_conditions == b.eval_conditions), (a.id, b.id)
    assert len(set(got.values())) == 3


def test_without_the_window_every_claim_collides(cameo):
    r = comp.resolve_profile(cameo)
    blind = keys(r, lambda c: by_record(c).model_copy(update={'subset_used': 'CAMEO 3D common subset'}))
    assert len(set(blind.values())) == 1


def test_every_claim_clears_the_comparison_floor_and_its_unknowns_are_named(cameo):
    r = comp.resolve_profile(cameo)
    floor = read_yaml(os.path.join(ROOT, 'taxonomy', 'thresholds.yaml'))['thresholds']['comparison_floor']
    for c in CLAIMS:
        got = comp.compute_for_claim(c, r, by_record(c))
        assert got.condition_completeness >= floor, c.id
        assert set(got.unknown_fields) == {'selection_strategy'}, c.id
        assert by_record(c).human_assistance == 'none'


# ---- 6. content-derived ids ----------------------------------------------------------------------------------

def test_claim_and_condition_ids_are_content_derived():
    for p in claim_files():
        raw = read_yaml(p)
        canon = json.dumps([comp.canonicalise(raw[k]) for k in CLAIM_KEYS], separators=(',', ':'))
        assert raw['id'] == 'claim-' + hashlib.sha256(canon.encode('utf-8')).hexdigest()[:12]
        assert os.path.basename(p) == raw['id'] + '.yaml'
        cond = copy.deepcopy(record('conditions', raw['eval_conditions']))
        cid = cond.pop('id')
        body = json.dumps({k: comp.canonicalise(v) for k, v in cond.items()}, sort_keys=True, separators=(',', ':'))
        assert cid == 'cond-' + hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]
