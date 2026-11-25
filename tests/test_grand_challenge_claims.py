"""Grand Challenge claims, batch 1: four claims from four challenges, each on its challenge's own metric and with
the data-access gating that applies (P3-S8-T03; 04-data-model.md S7, 01-landscape-and-positioning.md S10).

The verify: "bench validate --tier all, plus a test asserting each claim references a challenge-specific metric
rather than a generic accuracy". The done-when: "Four medicine-health claims exist across four challenges." 01 S10
puts medicine-health in the mixed posture: Grand Challenge's catalogue is discovery, and the Tier-1 entries and their
claims are curated by hand. Each rule is a function that returns what is wrong; it runs on the committed claims, which
must pass, and on copies broken the way the rule names, which must fail, so the test also fails if a rule stops
catching its case.

Where the claims live. The ledger names data/claims/grand-challenge/, but the validator reads a claim only under
data/claims/<benchmark id>/ (as tests/test_grand_challenge_subset.py explains for the entries), so each claim sits
beside its challenge: stoic2021, conic, kits and midog, four of P3-S6-T06's SELECTED challenges. They were chosen
because their ranking metrics stand alone (no must_report_with partner, so one claim per challenge renders honestly;
AIROGS's and the Decathlon's metrics come in pairs) and because their papers state the result, the run and the
gating in passages that name no one. Each claim is its challenge's winning final-phase entry, as the challenge's
own results paper reports it; the leaderboards list user names and team members and back no claim here.

  1. Four claims, one per challenge, each on a medicine-health entry of the subset.
  2. A challenge-specific metric (the verify): the claim's metric is one of its challenge's own Metric records
     (SELECTED), declared by no other benchmark and used by no other benchmark's claim, defined from a source the
     entry cites, inside its range, and the metric_override of the claim's subset where it names one; never a shared
     record (GENERIC) or an accuracy. The failure cases: a shared F1, another challenge's metric, an accuracy, a
     metric another benchmark also declares, and a subset whose override is another metric.
  3. Shown alone honestly: no metric here must be reported with another; an AIROGS pAUC claim alone would be refused.
  4. The gating: each claim's notes name its entry's data.access and quote the passage, in the claim's own Source,
     that keeps the test data from the team; the rung is held-out-server because of it. The failure cases: the
     wrong gating named, no gating recorded, and a gating passage that is not in the Source.
  5. The Source is the challenge's own results paper: a DOI'd preprint, not a grand-challenge.org page, of the same
     DOI as a paper its entry cites, cited by the challenge, needing no archive, and marked as naming people.
  6. Every number is the paper's: every passage the notes quote is in the Source's extract, and the value is in one.
  7. No team handle and no submitter's name reaches the claims, their records or their Sources (hashes, so this
     file names nobody either); the systems are named for team names that are not people's, or for their method.
  8. Ids are content-derived (05 S2), every material condition is answered, no claim is LLM-run, and none forms a
     (benchmark, system, metric) group with another claim.
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
from test_grand_challenge_subset import GENERIC, SELECTED  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import llm_run  # noqa: E402

TASK = 'P3-S8-T03'
BATCH = ('stoic2021', 'conic', 'kits', 'midog')
# challenge -> (its entry's data.access, a phrase of the passage in the claim's Source that keeps the test data away)
GATING = {
    'stoic2021': ('private-test-server', 'could not be downloaded by participants at any point'),
    'conic': ('private-test-server', 'which were then used to process the test images in the cloud'),
    'kits': ('train-open-test-held-out', 'the test imaging was released (without labels)'),
    'midog': ('private-test-server', 'The participants had no access to any of the test images during the challenge'),
}
HELD_OUT = frozenset({'private-test-server', 'train-open-test-held-out'})
GATED = re.compile(r'Gating \(data\.access ([a-z-]+)\)')
QUOTED = re.compile(r'"([^"]+)"')
GC_HOST = 'grand-challenge.org'
CLAIM_KEYS = ('benchmark', 'system', 'metric', 'subset', 'value', 'source', 'date_reported')
# sha256 (first 16 hex) of the team handles and submitters' names the four papers print beside the passages cited:
# STOIC2021's results table and repository handles, MIDOG 2021's team column, KiTS19's section 5.1 byline and the
# KiTS19 paper's contact line. Hashes, so that the guard names nobody.
NAME_HASHES = frozenset({
    '288393048318c181', 'aa76d267777dfd63', '6a734f27b69f88ef', 'de4e44ef726a174d', '69bde5c13108c379',
    '035ed6398a6cb622', '22b135cda4da5751', 'd9e320604e69e2b9', 'b4012c3c4c01e33b', '09dbbea9f4cdb945',
    '6050ba508a248146', '74b9d119ddaf3508'})


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


CLAIMS = {bid: [ResultClaim.model_validate(read_yaml(p)) for p in claim_files(bid)] for bid in BATCH}
CORPUS = [ResultClaim.model_validate(read_yaml(p))
          for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True))]


def bench_id(ref):
    return ref.split('@')[0]


@pytest.fixture(scope='module')
def entries():
    return {bid: entry_doc(bid) for bid in BATCH}


@pytest.fixture(scope='module')
def metrics():
    return {c.metric: read_yaml(os.path.join(ROOT, 'data', 'metrics', c.metric + '.yaml'))
            for cs in CLAIMS.values() for c in cs}


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


# ---- the rules ---------------------------------------------------------------------------------------------------

def metric_problems(claim, entry, metrics, declared_by):
    """Why a claim's metric is not its challenge's own definition (empty when it is)."""
    bid = bench_id(claim.benchmark)
    m = metrics.get(claim.metric)
    if m is None:
        return ['%s has no Metric record' % claim.metric]
    Metric.model_validate(m)
    out = []
    if claim.metric not in SELECTED[bid][2] or claim.metric not in (entry.get('metrics') or []):
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


def lone_problems(claim, metrics):
    """A claim shown alone is honest only if its metric needs no partner, or its result_group holds one."""
    partners = (metrics.get(claim.metric) or {}).get('must_report_with') or []
    if partners and claim.result_group is None:
        return ['%s must be reported with %s, and the claim names no result_group'
                % (claim.metric, ', '.join(partners))]
    return []


def gating_problems(claim, entry, src):
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
        out.append('the notes quote no passage that keeps the test data away')
    elif not all(quote_found(q, src.quote_extract) for q in passages):
        out.append("the gating passage is not in %s's extract" % src.id)
    if access in HELD_OUT and claim.verification != 'held-out-server':
        out.append('a %s claim is %s, not held-out-server' % (access, claim.verification))
    return out


def source_problems(sid, bid, entry):
    """Why a claim's Source is not its challenge's own results paper (empty when it is)."""
    s = source(sid)
    out = []
    if s.type not in ('paper', 'preprint'):
        out.append('a %s, not a paper' % s.type)
    if not s.doi:
        out.append('no DOI')
    if GC_HOST in s.url:
        out.append('a page on %s' % GC_HOST)
    cited = {source(x).doi for x in (entry.get('curation') or {}).get('sources') or []} - {None}
    if s.doi not in cited:
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


# ---- 1. four claims across four challenges -----------------------------------------------------------------------

def test_four_medicine_health_claims_across_four_challenges(entries):
    assert {bid: len(cs) for bid, cs in CLAIMS.items()} == {bid: 1 for bid in BATCH}
    for bid, [c] in CLAIMS.items():
        assert bid in SELECTED and bench_id(c.benchmark) == bid, c.id
        b = load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml'))
        assert b.domain.primary.startswith('medicine-health/')
        if '@' in c.benchmark:
            assert c.benchmark.split('@')[1] in {v.version for v in b.versions}, c.id
    assert len({c.metric for cs in CLAIMS.values() for c in cs}) == 4


# ---- 2. a challenge-specific metric (the verify) -------------------------------------------------------------------

@pytest.mark.parametrize('bid', BATCH)
def test_verify_each_claim_references_its_challenges_own_metric(bid, entries, metrics, declared_by):
    [claim] = CLAIMS[bid]
    assert metric_problems(claim, entries[bid], metrics, declared_by) == []


def test_verify_a_shared_f1_or_another_challenges_metric_is_refused(entries, metrics, declared_by):
    [midog] = CLAIMS['midog']
    shared = dict(metrics, **{'f1-score': read_yaml(os.path.join(ROOT, 'data', 'metrics', 'f1-score.yaml'))})
    got = metric_problems(midog.model_copy(update={'metric': 'f1-score'}), entries['midog'], shared, declared_by)
    assert "f1-score is not one of midog's own metrics" in got
    assert 'f1-score is a generic record or an accuracy' in got
    assert 'f1-score is defined from no source midog cites' in got
    [conic] = CLAIMS['conic']
    borrowed = conic.model_copy(update={'metric': 'midog-2021-f1', 'subset': None})
    got = metric_problems(borrowed, entries['conic'], metrics, declared_by)
    assert "midog-2021-f1 is not one of conic's own metrics" in got
    assert 'midog-2021-f1 is also used by midog' in got


def test_verify_an_accuracy_is_refused(entries, metrics, declared_by):
    [stoic] = CLAIMS['stoic2021']
    accuracy = dict(metrics['stoic2021-severity-auc'], id='stoic2021-accuracy', name='Accuracy',
                    full_name='Share of correctly classified scans')
    got = metric_problems(stoic.model_copy(update={'metric': 'stoic2021-accuracy'}), entries['stoic2021'],
                          dict(metrics, **{'stoic2021-accuracy': accuracy}), declared_by)
    assert got == ["stoic2021-accuracy is not one of stoic2021's own metrics",
                   'stoic2021-accuracy is a generic record or an accuracy']


def test_verify_a_metric_another_benchmark_declares_is_refused(entries, metrics, declared_by):
    [kits] = CLAIMS['kits']
    shared = {m: set(b) for m, b in declared_by.items()}
    shared[kits.metric] |= {'camelyon17'}
    assert metric_problems(kits, entries['kits'], metrics, shared) == \
        ['kits19-kidney-tumour-dice is also used by camelyon17']


def test_verify_a_subset_scored_on_another_metric_is_refused(entries, metrics, declared_by):
    [conic] = CLAIMS['conic']
    r2 = read_yaml(os.path.join(ROOT, 'data', 'metrics', 'conic-multiclass-r2.yaml'))
    got = metric_problems(conic.model_copy(update={'metric': 'conic-multiclass-r2'}), entries['conic'],
                          dict(metrics, **{'conic-multiclass-r2': r2}), declared_by)
    assert got == ["conic#segmentation-classification's metric is conic-mpq-plus, not conic-multiclass-r2"]


# ---- 3. shown alone honestly ---------------------------------------------------------------------------------------

def test_no_claim_needs_a_partner_metric(metrics):
    assert [p for cs in CLAIMS.values() for c in cs for p in lone_problems(c, metrics)] == []
    assert all(c.result_group is None for cs in CLAIMS.values() for c in cs)


def test_a_paired_metric_alone_is_refused(metrics):
    [stoic] = CLAIMS['stoic2021']
    pauc = read_yaml(os.path.join(ROOT, 'data', 'metrics', 'airogs-screening-pauc.yaml'))
    alone = stoic.model_copy(update={'benchmark': 'airogs', 'metric': 'airogs-screening-pauc'})
    assert lone_problems(alone, {'airogs-screening-pauc': pauc}) == [
        'airogs-screening-pauc must be reported with airogs-screening-sensitivity, and the claim names no '
        'result_group']


# ---- 4. the gating -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('bid', BATCH)
def test_each_claim_records_the_gating_that_applies(bid, entries):
    [claim] = CLAIMS[bid]
    assert gating_problems(claim, entries[bid], source(claim.source)) == []


def test_the_batch_spans_two_gating_regimes(entries):
    assert {entries[b]['data']['access'] for b in BATCH} == HELD_OUT


def test_a_wrong_missing_or_unsourced_gating_is_refused(entries):
    [kits] = CLAIMS['kits']
    src = source(kits.source)
    wrong = kits.model_copy(update={'notes': kits.notes.replace('data.access train-open-test-held-out',
                                                                'data.access private-test-server')})
    assert gating_problems(wrong, entries['kits'], src) == \
        ['the notes record data.access private-test-server, the entry train-open-test-held-out']
    bare = kits.model_copy(update={'notes': 'Section 5.1, the first-place submission.'})
    assert gating_problems(bare, entries['kits'], src) == \
        ['the notes record no gating', 'the notes quote no passage that keeps the test data away']
    [stoic] = CLAIMS['stoic2021']
    invented = stoic.model_copy(update={'notes': stoic.notes.replace(
        'could not be downloaded by participants at any point', 'could not be downloaded by participants until 2023')})
    found = gating_problems(invented, entries['stoic2021'], source(stoic.source))
    assert found == ['the notes quote no passage that keeps the test data away']
    moved = stoic.model_copy(update={'notes': stoic.notes.replace(
        'at all times and could not be downloaded', 'at all times, and it could not be downloaded')})
    assert gating_problems(moved, entries['stoic2021'], source(stoic.source)) == \
        ["the gating passage is not in %s's extract" % stoic.source]
    self_reported = stoic.model_copy(update={'verification': 'self-reported'})
    assert gating_problems(self_reported, entries['stoic2021'], source(stoic.source)) == \
        ['a private-test-server claim is self-reported, not held-out-server']


# ---- 5. the Source is the challenge's own results paper ------------------------------------------------------------

@pytest.mark.parametrize('bid', BATCH)
def test_each_source_is_the_challenges_own_paper(bid, entries):
    [claim] = CLAIMS[bid]
    assert source_problems(claim.source, bid, entries[bid]) == []
    s = source(claim.source)
    assert s.drafted_by == 'agent (%s)' % TASK and str(s.accessed) == '2026-11-25'
    assert s.contains_personal_data is True and s.failure_reason is None      # bylines, kept out of the windows
    assert '@' not in s.quote_extract and 'affiliation:' not in s.quote_extract.lower()


def test_a_grand_challenge_page_or_a_leaderboard_is_refused(entries):
    assert source_problems('src-gc-stoic2021-home', 'stoic2021', entries['stoic2021']) == [
        'a documentation, not a paper', 'no DOI', 'a page on grand-challenge.org', 'not the paper stoic2021 cites',
        'archive_status withheld']
    assert source_problems('src-camelyon17-statistics-2026-11', 'conic', entries['conic']) == [
        'a leaderboard-page, not a paper', 'no DOI', 'a page on grand-challenge.org', 'not the paper conic cites',
        'not cited by conic', 'archive_status withheld']


# ---- 6. every number is the paper's --------------------------------------------------------------------------------

@pytest.mark.parametrize('bid', BATCH)
def test_every_passage_the_notes_quote_is_in_the_paper_and_holds_the_value(bid):
    [claim] = CLAIMS[bid]
    quotes = QUOTED.findall(claim.notes)
    extract = source(claim.source).quote_extract
    assert len(quotes) >= 4
    assert [q for q in quotes if not quote_found(q, extract)] == []
    assert any(('%g' % claim.value) in q for q in quotes)
    assert claim.date_reported == source(claim.source).published
    if claim.uncertainty:
        low, high = claim.uncertainty.value
        assert any('%g-%g' % (low, high) in q for q in quotes)


# ---- 7. no handle and no submitter's name --------------------------------------------------------------------------

def touched_files():
    out = []
    for bid in BATCH:
        out += claim_files(bid)
        for c in CLAIMS[bid]:
            for kind, ident in (('systems', c.system), ('conditions', c.eval_conditions),
                                ('organizations', c.reported_by), ('sources', c.source)):
                out += glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    return sorted(set(out))


def test_no_handle_or_submitter_name_reaches_the_records():
    hits = {}
    for p in touched_files():
        with open(p, encoding='utf-8') as fh:
            found = names_in(fh.read())
        if found:
            hits[os.path.relpath(p, ROOT)] = len(found)
    assert hits == {}
    assert len(touched_files()) == 4 * 5


def test_the_name_guard_bites():
    probe = frozenset({hashlib.sha256(b'someone.x').hexdigest()[:16], hashlib.sha256(b'surname-two').hexdigest()[:16]})
    assert names_in('the team someone.x, then Surname-Two', probe) == ['someone.x', 'surname-two']
    assert names_in('the team Code 1055', probe) == []


# ---- 8. identity, conditions and the partition ---------------------------------------------------------------------

@pytest.mark.parametrize('bid', BATCH)
def test_ids_are_content_derived_and_every_material_condition_is_answered(bid):
    [path] = claim_files(bid)
    raw = read_yaml(path)
    canon = json.dumps([comp.canonicalise(raw.get(k)) for k in CLAIM_KEYS], separators=(',', ':'))
    assert raw['id'] == 'claim-' + hashlib.sha256(canon.encode('utf-8')).hexdigest()[:12]
    assert os.path.basename(path) == raw['id'] + '.yaml'
    cond = copy.deepcopy(record('conditions', raw['eval_conditions']))
    cid = cond.pop('id')
    body = json.dumps({k: comp.canonicalise(v) for k, v in cond.items()}, sort_keys=True, separators=(',', ':'))
    assert cid == 'cond-' + hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]
    b = load_benchmark(os.path.join(ROOT, 'data', 'benchmarks', 'medicine-health', bid + '.yaml'))
    [claim] = CLAIMS[bid]
    conditions = EvalConditions.model_validate(record('conditions', cid))
    got = comp.compute_for_claim(claim, comp.resolve_profile(b), conditions)
    assert got.condition_completeness == 1.0 and not got.unknown_fields


@pytest.mark.parametrize('bid', BATCH)
def test_each_claim_is_a_held_out_non_llm_result_its_organisers_reported(bid):
    [claim] = CLAIMS[bid]
    assert claim.verification == 'held-out-server' and claim.claim_type == 'absolute'
    Organization.model_validate(record('organizations', claim.reported_by))
    s = System.model_validate(record('systems', claim.system))
    assert s.system_type == 'domain-specialist-model' and claim.source in s.sources
    assert llm_run.llm_run(claim.system) is False                       # it counts toward the non-LLM claims
    assert claim.superseded_by is None and claim.ingestion is None


def test_no_claim_forms_a_group_with_another():
    keys = [(bench_id(c.benchmark), c.system, c.metric) for c in CORPUS]
    for cs in CLAIMS.values():
        for c in cs:
            assert keys.count((bench_id(c.benchmark), c.system, c.metric)) == 1, c.id
