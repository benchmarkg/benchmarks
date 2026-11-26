"""Grand Challenge claims, batch 2: five claims from four further challenges, each on its challenge's own metric,
with the data-access gating and the training-data rule that apply (P3-S8-T04; 04-data-model.md S7,
01-landscape-and-positioning.md S10).

The verify: "bench validate --tier all; bench report completeness shows eight medicine-health claims at >= 0.6".
The done-when: "Eight medicine-health claims exist." Batch 1 (tests/test_grand_challenge_claims.py, P3-S8-T03) holds
four; this batch adds five, so nine exist. Each rule is a function that returns what is wrong; it runs on the
committed claims, which must pass, and on copies broken the way the rule names, which must fail.

The challenges. The four Grand Challenge entries batch 1 left were CAMELYON17, PI-CAI, AIROGS and the Medical
Segmentation Decathlon, with LUNA16 catalogued but outside P3-S6-T06's subset. The Decathlon is not here: its DSC
must be reported with its NSD, and its paper prints no NSD for any team. AIROGS's screening metrics come in a pair
too, so its winner's pAUC and sensitivity are two claims bound by result_group (04 S7: "the renderer will not show
one member of a group alone"); that is why four challenges give five claims. LUNA16 declared no metric, so its claim
brings luna16-cpm, which luna16 itself does not yet list (a reviewer's step: the task may not edit the entry).

  1. Five claims on four medicine-health entries hosted on Grand Challenge, none of them batch 1's.
  2. A challenge-specific metric: one of its challenge's own records, used by no other benchmark, defined from a
     source the entry cites, inside its range; never a shared record or an accuracy.
  3. Shown alone honestly: a metric that must be reported with another sits in a result_group that holds a claim on
     every partner, from the same run.
  4. The gating: the notes name the entry's data.access and quote the passage that keeps the test data from the
     team, or (LUNA16) that says there is none; held-out data makes the claim held-out-server, open labels never do.
  5. The training-data rule: each conditions record answers training_data_policy as the rule its notes quote says.
  6. The Source is a DOI'd paper, never a grand-challenge.org page: the challenge's own paper, or (PI-CAI, whose
     study paper prints no team's ranking score) the team's own paper, reported by the team. The leaderboards are
     personal data (user names, team members), withheld and never archived, whatever the ledger's "Archive each
     leaderboard" says.
  7. Every number is the paper's: every quoted passage is in the claim's Source or a Source its notes name.
  8. No handle and no person's name reaches the records (hashes, so this file names nobody either).
  9. Ids are content-derived (05 S2), every material condition is answered, none is LLM-run, none forms a
     (benchmark, system, metric) group, and the completeness report puts each at 1.0.
"""
import copy
import glob
import hashlib
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tests'))
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import Organization  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from test_grand_challenge_claims import BATCH as BATCH_1  # noqa: E402
from test_grand_challenge_claims import UNKNOWN_SINCE_ADR_0029  # noqa: E402
from test_grand_challenge_subset import GENERIC, SELECTED  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness, llm_run  # noqa: E402

TASK = 'P3-S8-T04'
BATCH = ('camelyon17', 'pi-cai', 'airogs', 'luna16')
COUNTS = {'camelyon17': 1, 'pi-cai': 1, 'airogs': 2, 'luna16': 1}
# challenge -> its own metric records; luna16 had none before this batch
OWN = {bid: SELECTED[bid][2] for bid in ('camelyon17', 'pi-cai', 'airogs')}
OWN['luna16'] = {'luna16-cpm'}
# challenge -> (its entry's data.access, a phrase of the passage that keeps the test data away or says it is open)
GATING = {
    'camelyon17': ('train-open-test-held-out', 'These slides are not annotated and not labelled'),
    'pi-cai': ('private-test-server', 'ensures that any image used for evaluation remains truly unseen'),
    'airogs': ('private-test-server', 'The test set was and still is closed'),
    'luna16': ('fully-open', 'the evaluation of the algorithms is performed on the same data set'),
}
HELD_OUT = frozenset({'private-test-server', 'train-open-test-held-out'})
# challenge -> (training_data_policy, a phrase of the rule the notes quote)
RULES = {
    'camelyon17': ('restricted-list', 'participants were not allowed to use other data sources'),
    'pi-cai': ('open', 'They can also use external datasets to train their AI algorithms'),
    'airogs': ('restricted-list', 'teams were not permitted to use additional fundus image training data'),
    'luna16': ('open', 'was not used as training data'),
}
TEAM_PAPER = frozenset({'pi-cai'})
GATED = re.compile(r'Gating \(data\.access ([a-z-]+)\)')
QUOTED = re.compile(r'"([^"]+)"')
NAMED = re.compile(r'\b(src-[a-z0-9-]*[a-z0-9])\)')
GC_HOST = 'grand-challenge.org'
CLAIM_KEYS = ('benchmark', 'system', 'metric', 'subset', 'value', 'source', 'date_reported')
# sha256 (first 16 hex) of personal names and handles the four papers print beside the passages cited: CAMELYON17's
# author notes, Z-SSMNet's byline and code handle, a team named for a person in AIROGS's robustness results, and
# LUNA16's citation surnames. Hashes, so that the guard names nobody.
NAME_HASHES = frozenset({
    'bb3d2cb864baef9e', '8152427968df69bb', '2da35120ab2f72d1', '2a590cb845f75477', 'bae7459ddecc7d48',
    'c44d6502f0ec8601', '4922f2e1689c62b2', '875c51d561be38e4', '826452ef690a352b', '361e8f12f9249f66',
    'd26d1b476ba7dac5', '76cd81a90d0b22fa', '6dac61e9b887ee67', '0c41667401b76934'})


def record(kind, ident):
    hits = glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    assert len(hits) == 1, (kind, ident, hits)
    return read_yaml(hits[0])


def source(sid):
    return Source.model_validate(record('sources', sid))


def entry_doc(bid):
    return read_yaml(os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml'))


def claim_files(bid):
    return sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', bid, '*.yaml')))


def bench_id(ref):
    return ref.split('@')[0]


CLAIMS = {bid: [ResultClaim.model_validate(read_yaml(p)) for p in claim_files(bid)] for bid in BATCH}
ALL = [c for cs in CLAIMS.values() for c in cs]
CORPUS = [ResultClaim.model_validate(read_yaml(p))
          for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True))]


def one(bid, metric=None):
    return next(c for c in CLAIMS[bid] if metric is None or c.metric == metric)


@pytest.fixture(scope='module')
def entries():
    return {bid: entry_doc(bid) for bid in BATCH}


@pytest.fixture(scope='module')
def metrics():
    mids = {c.metric for c in ALL} | {p for c in ALL for p in record('metrics', c.metric).get('must_report_with') or []}
    return {m: record('metrics', m) for m in mids}


@pytest.fixture(scope='module')
def declared_by():
    """metric id -> the benchmarks that declare it (metrics, a subset's metric_override, headline_metric) or carry a
    claim on it, across the whole corpus."""
    out = {}
    for p in glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True):
        doc = read_yaml(p) or {}
        if not isinstance(doc, dict) or 'id' not in doc:
            continue
        refs = list(doc.get('metrics') or []) + [doc.get('headline_metric')]
        refs += [s.get('metric_override') for s in doc.get('subsets') or [] if isinstance(s, dict)]
        for m in filter(None, refs):
            out.setdefault(m, set()).add(doc['id'])
    for c in CORPUS:
        out.setdefault(c.metric, set()).add(bench_id(c.benchmark))
    return out


def pool(claim):
    """The extracts a claim's quotes may come from: its own Source and every Source its notes name."""
    ids = [claim.source] + [s for s in NAMED.findall(claim.notes or '') if s != claim.source]
    return {sid: source(sid).quote_extract for sid in ids}


def in_pool(quote, extracts):
    return any(quote_found(quote, x) for x in extracts.values())


# ---- the rules ---------------------------------------------------------------------------------------------------

def metric_problems(claim, entry, metrics, declared_by):
    """Why a claim's metric is not its challenge's own definition (empty when it is)."""
    bid = bench_id(claim.benchmark)
    m = metrics.get(claim.metric)
    if m is None:
        return ['%s has no Metric record' % claim.metric]
    Metric.model_validate(m)
    out = []
    declared = entry.get('metrics') or []
    if claim.metric not in OWN[bid] or (declared and claim.metric not in declared):
        out.append("%s is not one of %s's own metrics" % (claim.metric, bid))
    if claim.metric in GENERIC or 'accuracy' in ('%s %s %s' % (claim.metric, m['name'], m.get('full_name'))).lower():
        out.append('%s is a generic record or an accuracy' % claim.metric)
    others = sorted(declared_by.get(claim.metric, set()) - {bid})
    if others:
        out.append('%s is also used by %s' % (claim.metric, ', '.join(others)))
    cited = set((entry.get('curation') or {}).get('sources') or [])
    if not set(m.get('sources') or []) & cited:
        out.append('%s is defined from no source %s cites' % (claim.metric, bid))
    rng = m.get('range') or {}
    low, high = rng.get('min'), rng.get('max')
    if not ((low is None or claim.value >= low) and (high is None or claim.value <= high)):
        out.append('%s lies outside the range of %s' % (claim.value, claim.metric))
    if claim.subset:
        sub = next((s for s in entry.get('subsets') or [] if s['id'] == claim.subset), None)
        if sub is None:
            out.append('%s is not a subset of %s' % (claim.subset, bid))
        elif sub.get('metric_override') not in (None, claim.metric):
            out.append("%s's metric is %s, not %s" % (claim.subset, sub['metric_override'], claim.metric))
    return out


def lone_problems(claim, corpus, metrics):
    """A claim whose metric must be reported with others is honest only in a result_group that holds a claim on
    every partner, from the same run (system, benchmark, subset, source and conditions)."""
    partners = (metrics.get(claim.metric) or {}).get('must_report_with') or []
    if not partners:
        return []
    if claim.result_group is None:
        return ['%s must be reported with %s, and the claim names no result_group'
                % (claim.metric, ', '.join(partners))]
    out = []
    run = ('system', 'benchmark', 'subset', 'source', 'eval_conditions')
    for p in partners:
        mates = [x for x in corpus if x.result_group == claim.result_group and x.metric == p and x.id != claim.id]
        if not mates:
            out.append('its result_group %s holds no %s claim' % (claim.result_group, p))
        elif not all(getattr(x, k) == getattr(claim, k) for x in mates for k in run):
            out.append('its %s partner in %s is another run' % (p, claim.result_group))
    return out


def gating_problems(claim, entry):
    """Why a claim does not record the gating that applies to it (empty when it does)."""
    bid = bench_id(claim.benchmark)
    want, phrase = GATING[bid]
    access = (entry.get('data') or {}).get('access')
    notes = claim.notes or ''
    out = []
    if access != want:
        out.append('%s now has data.access %s, not %s' % (bid, access, want))
    named = GATED.search(notes)
    if named is None:
        out.append('the notes record no gating')
    elif named.group(1) != access:
        out.append('the notes record data.access %s, the entry %s' % (named.group(1), access))
    passages = [q for q in QUOTED.findall(notes) if phrase.casefold() in q.casefold()]
    if not passages:
        out.append('the notes quote no passage on who sees the test data')
    elif not all(in_pool(q, pool(claim)) for q in passages):
        out.append('the gating passage is in no Source the claim cites')
    if access in HELD_OUT and claim.verification != 'held-out-server':
        out.append('a %s claim is %s, not held-out-server' % (access, claim.verification))
    if access not in HELD_OUT and claim.verification == 'held-out-server':
        out.append('a %s claim cannot be held-out-server: its labels are public' % access)
    return out


def rule_problems(claim, conditions):
    """Why the claim's conditions do not answer the training-data rule its notes quote (empty when they do)."""
    bid = bench_id(claim.benchmark)
    want, phrase = RULES[bid]
    out = []
    if conditions.training_data_policy != want:
        out.append('training_data_policy is %s, not %s' % (conditions.training_data_policy, want))
    passages = [q for q in QUOTED.findall(claim.notes or '') if phrase.casefold() in q.casefold()]
    if not passages:
        out.append('the notes quote no training-data rule')
    elif not all(in_pool(q, pool(claim)) for q in passages):
        out.append('the training-data passage is in no Source the claim cites')
    return out


def source_problems(claim, entry):
    """Why a claim's Source is not a paper fit to carry it (empty when it is)."""
    bid = bench_id(claim.benchmark)
    s = source(claim.source)
    out = []
    if s.type not in ('paper', 'preprint'):
        out.append('a %s, not a paper' % s.type)
    if not s.doi:
        out.append('no DOI')
    if GC_HOST in s.url:
        out.append('a page on %s' % GC_HOST)
    cited = {source(x).doi for x in (entry.get('curation') or {}).get('sources') or []} - {None}
    if bid in TEAM_PAPER:
        team = System.model_validate(record('systems', claim.system)).organization
        if team is None or claim.reported_by != team:
            out.append("a team's paper reported by %s, not by the team" % claim.reported_by)
    elif s.doi not in cited:
        out.append('not the paper %s cites' % bid)
    if bid not in s.cited_by:
        out.append('not cited by %s' % bid)
    if s.archive_status != 'not-required':
        out.append('archive_status %s' % s.archive_status)
    return out


def names_in(text, hashes=NAME_HASHES):
    low = text.lower()
    tokens = set(re.findall(r'[a-z0-9]+(?:[.\-][a-z0-9]+)*', low)) | set(re.findall(r'[a-z0-9]+', low))
    return sorted(t for t in tokens if hashlib.sha256(t.encode('utf-8')).hexdigest()[:16] in hashes)


# ---- 1. five claims on four further challenges --------------------------------------------------------------------

def test_five_medicine_health_claims_on_four_further_challenges():
    assert {bid: len(cs) for bid, cs in CLAIMS.items()} == COUNTS
    assert not set(BATCH) & set(BATCH_1)
    for bid, cs in CLAIMS.items():
        b = load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml'))
        assert b.domain.primary.startswith('medicine-health/') and GC_HOST in (b.homepage or '')
        for c in cs:
            assert bench_id(c.benchmark) == bid, c.id
            if '@' in c.benchmark:
                assert c.benchmark.split('@')[1] in {v.version for v in b.versions}, c.id
    assert len({c.metric for c in ALL}) == 5


def test_the_done_when_eight_medicine_health_claims_exist():
    medicine = [c for c in CORPUS if c.benchmark and os.path.exists(os.path.join(
        ROOT, 'data', 'benchmarks', 'medicine-health', bench_id(c.benchmark) + '.yaml'))]
    assert len(medicine) >= 8
    assert {bench_id(c.benchmark) for c in medicine} >= set(BATCH) | {bench_id(b) for b in BATCH_1}


# ---- 2. a challenge-specific metric -------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_each_claim_references_its_challenges_own_metric(claim, entries, metrics, declared_by):
    assert metric_problems(claim, entries[bench_id(claim.benchmark)], metrics, declared_by) == []


def test_luna16_cpm_is_new_and_not_yet_declared_by_its_entry(entries, metrics):
    assert not entries['luna16'].get('metrics')                        # a reviewer adds it to the entry
    m = Metric.model_validate(metrics['luna16-cpm'])
    assert (m.range.min, m.range.max, m.optimum) == (0, 1, 'max') and not m.must_report_with


def test_a_shared_or_borrowed_metric_or_an_accuracy_is_refused(entries, metrics, declared_by):
    cam = one('camelyon17')
    shared = dict(metrics, **{'f1-score': record('metrics', 'f1-score')})
    got = metric_problems(cam.model_copy(update={'metric': 'f1-score'}), entries['camelyon17'], shared, declared_by)
    assert "f1-score is not one of camelyon17's own metrics" in got
    assert 'f1-score is a generic record or an accuracy' in got
    luna = one('luna16')
    borrowed = luna.model_copy(update={'metric': 'camelyon17-pn-stage-kappa', 'subset': None})
    got = metric_problems(borrowed, entries['luna16'], metrics, declared_by)
    assert got == ["camelyon17-pn-stage-kappa is not one of luna16's own metrics",
                   'camelyon17-pn-stage-kappa is also used by camelyon17',
                   'camelyon17-pn-stage-kappa is defined from no source luna16 cites']
    accuracy = dict(metrics['pi-cai-ranking-score'], id='pi-cai-accuracy', name='Accuracy')
    got = metric_problems(one('pi-cai').model_copy(update={'metric': 'pi-cai-accuracy'}), entries['pi-cai'],
                          dict(metrics, **{'pi-cai-accuracy': accuracy}), declared_by)
    assert got == ["pi-cai-accuracy is not one of pi-cai's own metrics",
                   'pi-cai-accuracy is a generic record or an accuracy']
    outside = one('pi-cai').model_copy(update={'value': 1.2, 'subset': 'pi-cai#nowhere'})
    assert metric_problems(outside, entries['pi-cai'], metrics, declared_by) == [
        '1.2 lies outside the range of pi-cai-ranking-score', 'pi-cai#nowhere is not a subset of pi-cai']


# ---- 3. shown alone honestly --------------------------------------------------------------------------------------

def test_every_paired_metric_sits_in_a_group_with_its_partner(metrics):
    assert [p for c in ALL for p in lone_problems(c, CORPUS, metrics)] == []
    groups = {c.result_group for c in ALL} - {None}
    assert groups == {'airogs-final-test-pumch-eye'}
    assert sorted(c.id for c in CORPUS if c.result_group in groups) == sorted(c.id for c in CLAIMS['airogs'])
    assert all(c.result_group is None for c in ALL if bench_id(c.benchmark) != 'airogs')


def test_a_lone_or_mismatched_pair_member_is_refused(metrics):
    pauc = one('airogs', 'airogs-screening-pauc')
    assert lone_problems(pauc.model_copy(update={'result_group': None}), CORPUS, metrics) == [
        'airogs-screening-pauc must be reported with airogs-screening-sensitivity, and the claim names no '
        'result_group']
    rest = [c for c in CORPUS if c.metric != 'airogs-screening-sensitivity']
    assert lone_problems(pauc, rest, metrics) == [
        'its result_group airogs-final-test-pumch-eye holds no airogs-screening-sensitivity claim']
    sens = one('airogs', 'airogs-screening-sensitivity')
    other_run = [c if c.id != sens.id else c.model_copy(update={'system': 'some-other-team'}) for c in CORPUS]
    assert lone_problems(pauc, other_run, metrics) == [
        'its airogs-screening-sensitivity partner in airogs-final-test-pumch-eye is another run']


# ---- 4. the gating -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_each_claim_records_the_gating_that_applies(claim, entries):
    assert gating_problems(claim, entries[bench_id(claim.benchmark)]) == []


def test_the_batch_spans_three_gating_regimes(entries):
    assert {entries[b]['data']['access'] for b in BATCH} == HELD_OUT | {'fully-open'}
    assert one('luna16').verification == 'maintainer-verified'


def test_a_wrong_missing_unsourced_or_overclaimed_gating_is_refused(entries):
    cam = one('camelyon17')
    wrong = cam.model_copy(update={'notes': cam.notes.replace('data.access train-open-test-held-out',
                                                              'data.access private-test-server')})
    assert gating_problems(wrong, entries['camelyon17']) == \
        ['the notes record data.access private-test-server, the entry train-open-test-held-out']
    bare = cam.model_copy(update={'notes': 'The best team.'})
    assert gating_problems(bare, entries['camelyon17']) == \
        ['the notes record no gating', 'the notes quote no passage on who sees the test data']
    unnamed = cam.model_copy(update={'notes': cam.notes.replace('(src-camelyon17-data)', '(the data page)')})
    assert gating_problems(unnamed, entries['camelyon17']) == ['the gating passage is in no Source the claim cites']
    picai = one('pi-cai')
    assert gating_problems(picai.model_copy(update={'verification': 'self-reported'}), entries['pi-cai']) == \
        ['a private-test-server claim is self-reported, not held-out-server']
    luna = one('luna16')
    assert gating_problems(luna.model_copy(update={'verification': 'held-out-server'}), entries['luna16']) == \
        ['a fully-open claim cannot be held-out-server: its labels are public']


# ---- 5. the training-data rule -------------------------------------------------------------------------------------

def conditions_of(claim):
    return EvalConditions.model_validate(record('conditions', claim.eval_conditions))


@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_each_claims_conditions_answer_the_rule_its_notes_quote(claim):
    assert rule_problems(claim, conditions_of(claim)) == []


def test_a_wrong_or_unquoted_rule_is_refused():
    air = one('airogs', 'airogs-screening-pauc')
    cond = conditions_of(air)
    assert rule_problems(air, cond.model_copy(update={'training_data_policy': 'open'})) == \
        ['training_data_policy is open, not restricted-list']
    assert rule_problems(air, cond.model_copy(update={'training_data_policy': None})) == \
        ['training_data_policy is None, not restricted-list']
    picai = one('pi-cai')
    moved = picai.model_copy(update={'notes': picai.notes.replace('src-picai-phases-rules', 'the rules page')})
    assert rule_problems(moved, conditions_of(picai)) == ['the training-data passage is in no Source the claim cites']


# ---- 6. the Source is a paper; the leaderboards are withheld ------------------------------------------------------

@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_each_source_is_a_paper_fit_to_carry_the_claim(claim, entries):
    assert source_problems(claim, entries[bench_id(claim.benchmark)]) == []
    s = source(claim.source)
    assert s.drafted_by == 'agent (%s)' % TASK and str(s.accessed) == '2026-11-26'
    assert s.contains_personal_data is True and s.failure_reason is None      # bylines, kept out of the windows
    assert '@' not in s.quote_extract.replace('SE@95SPS', '') and 'affiliation' not in s.quote_extract.lower()


def test_a_grand_challenge_page_a_leaderboard_or_a_borrowed_report_is_refused(entries):
    picai = one('pi-cai')
    assert source_problems(picai.model_copy(update={'source': 'src-picai-leaderboard-testing'}),
                           entries['pi-cai']) == [
        'a leaderboard-page, not a paper', 'no DOI', 'a page on grand-challenge.org', 'archive_status withheld']
    assert source_problems(picai.model_copy(update={'reported_by': 'org-luna16'}), entries['pi-cai']) == \
        ["a team's paper reported by org-luna16, not by the team"]
    cam = one('camelyon17')
    assert source_problems(cam.model_copy(update={'source': 'src-arxiv-2302-01738-v2-2026-11-26'}),
                           entries['camelyon17']) == ['not the paper camelyon17 cites', 'not cited by camelyon17']


def test_the_leaderboards_are_personal_data_withheld_never_archived(entries):
    """The ledger's "Archive each leaderboard" cannot be met: every grand-challenge.org page the four entries cite,
    the six leaderboards among them, names people, so it is withheld with a reason and has no archive."""
    pages = {s for bid in BATCH for s in entries[bid]['curation']['sources'] if GC_HOST in source(s).url}
    boards = {s for s in pages if source(s).type == 'leaderboard-page'}
    assert len(boards) == 6
    for sid in pages:
        s = source(sid)
        assert s.archive_status == 'withheld' and s.contains_personal_data is True and s.failure_reason, sid
        assert s.archive_url is None and s.archive_captured is None and s.archive_digest is None, sid
    assert not {c.source for c in ALL} & pages


# ---- 7. every number is the paper's --------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_every_passage_the_notes_quote_is_in_a_cited_source_and_holds_the_value(claim):
    quotes = QUOTED.findall(claim.notes)
    extracts = pool(claim)
    own = extracts[claim.source]
    assert len(quotes) >= 6
    assert [q for q in quotes if not in_pool(q, extracts)] == []
    assert any(('%g' % claim.value) in q and quote_found(q, own) for q in quotes)
    assert claim.date_reported == source(claim.source).published
    if claim.uncertainty:
        low, high = claim.uncertainty.value
        assert any('%.2f – %.2f' % (low, high) in q and quote_found(q, own) for q in quotes)


def test_a_number_the_paper_does_not_print_is_refused():
    luna = one('luna16')
    invented = luna.notes.replace('with a CPM of 0.811', 'with a CPM of 0.951')
    assert [q for q in QUOTED.findall(invented) if not in_pool(q, pool(luna))] == \
        ['In this track, the best score was achieved by ZNET with a CPM of 0.951.']


# ---- 8. no handle and no person's name -----------------------------------------------------------------------------

def touched_files():
    out = []
    for bid in BATCH:
        out += claim_files(bid)
        for c in CLAIMS[bid]:
            for kind, ident in (('systems', c.system), ('conditions', c.eval_conditions),
                                ('organizations', c.reported_by), ('sources', c.source), ('metrics', c.metric)):
                out += glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    return sorted(set(out))


def test_no_handle_or_name_reaches_the_records():
    hits = {}
    for p in touched_files():
        with open(p, encoding='utf-8') as fh:
            found = names_in(fh.read())
        if found:
            hits[os.path.relpath(p, ROOT)] = len(found)
    assert hits == {}
    # 5 claims, 4 systems, 4 conditions (AIROGS's pair shares one), 4 organisations, 4 sources, 5 metrics
    assert len(touched_files()) == 5 + 4 + 4 + 4 + 4 + 5


def test_the_name_guard_bites():
    probe = frozenset({hashlib.sha256(b'someone.x').hexdigest()[:16], hashlib.sha256(b'surname-two').hexdigest()[:16]})
    assert names_in('the team someone.x, then Surname-Two', probe) == ['someone.x', 'surname-two']
    assert names_in('the team PUMCH-eye', probe) == []


# ---- 9. identity, conditions, partition and completeness ------------------------------------------------------------

@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_ids_are_content_derived_and_every_material_condition_is_answered(claim):
    bid = bench_id(claim.benchmark)
    [path] = [p for p in claim_files(bid) if os.path.basename(p) == claim.id + '.yaml']
    raw = read_yaml(path)
    canon = json.dumps([comp.canonicalise(raw.get(k)) for k in CLAIM_KEYS], separators=(',', ':'))
    assert raw['id'] == 'claim-' + hashlib.sha256(canon.encode('utf-8')).hexdigest()[:12]
    cond = copy.deepcopy(record('conditions', raw['eval_conditions']))
    cid = cond.pop('id')
    body = json.dumps({k: comp.canonicalise(v) for k, v in cond.items()}, sort_keys=True, separators=(',', ':'))
    assert cid == 'cond-' + hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]
    b = load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml'))
    got = comp.compute_for_claim(claim, comp.resolve_profile(b), EvalConditions.model_validate(record('conditions', cid)))
    assert got.unknown_fields == () or list(got.unknown_fields) == []
    assert got.condition_completeness == 1.0


@pytest.mark.parametrize('claim', ALL, ids=lambda c: c.id)
def test_each_claim_is_a_non_llm_result_its_reporter_published(claim):
    assert claim.claim_type == 'absolute' and claim.superseded_by is None and claim.ingestion is None
    Organization.model_validate(record('organizations', claim.reported_by))
    s = System.model_validate(record('systems', claim.system))
    assert s.system_type == 'domain-specialist-model' and claim.source in s.sources
    assert llm_run.llm_run(claim.system) is False                       # it counts toward the non-LLM claims


def test_no_claim_forms_a_group_with_another():
    keys = [(bench_id(c.benchmark), c.system, c.metric) for c in CORPUS]
    for c in ALL:
        assert keys.count((bench_id(c.benchmark), c.system, c.metric)) == 1, c.id


def test_verify_completeness_of_the_medicine_health_claims():
    """The verify asks for eight medicine-health claims at >= 0.6. The five here are at 1.0, and so is batch 1's
    MIDOG claim since this task curated its training-data rule. Under ADR-0029's profiles (P3-S10-T01) batch 1's
    CoNIC claim stays at 0.5 until its training_data_policy is curated (UNKNOWN_SINCE_ADR_0029), so eight of nine
    pass; whatever batch 1 still leaves unknown is the only shortfall."""
    rows = completeness.build(ROOT)['rows']
    medicine = [r for r in rows if os.path.exists(os.path.join(
        ROOT, 'data', 'benchmarks', 'medicine-health', bench_id(r['benchmark']) + '.yaml'))]
    ours = {c.id for c in ALL}
    assert {r['claim']: r['condition_completeness'] for r in medicine if r['claim'] in ours} == \
        {c: 1.0 for c in ours}
    below = {bench_id(r['benchmark']) for r in medicine if r['condition_completeness'] < 0.6}
    assert below == set(UNKNOWN_SINCE_ADR_0029)
    at_least = [r for r in medicine if r['condition_completeness'] >= 0.6]
    assert len(at_least) == len(medicine) - len(UNKNOWN_SINCE_ADR_0029)
    assert len(at_least) >= 8                                           # the verify
