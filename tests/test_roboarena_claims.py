"""RoboArena's pairwise claims: an opponent, a rating-pool snapshot, the evaluator pool, the venue and the episode
protocol, and no absolute value (P3-S8-T05; 04-data-model.md S7 and S8, 12-analytics-and-trends.md S3.4).

The verify: "bench validate --tier all, plus a test asserting every claim is claim_type pairwise with a non-null
opponent and rating_pool, and that no absolute value field is set". The done-when: "Six pairwise claims exist and no
surface can be asked to rank them absolutely." That is held here as:

  1. Six claims in data/claims/roboarena/, each claim_type pairwise on roboarena-pairwise-win-rate, with an opponent
     that is another policy of the arena.
  2. The rating pool. schema/claim.py lets only a rating claim carry `rating_pool` (P3-S6-T05 recorded the gap in a
     review check on the entry), so a pairwise claim names its snapshot in `notes` and pool_of() reads it there --
     or from the field, should the schema come to allow it. The pool must be a RoboArena RatingPool holding both
     policies, dated after the last A/B evaluation the claim's Source counts and no later than the claim, and its
     board must count the very evaluations the claim's Source totals (each A/B evaluation is two policies' entries).
  3. No absolute value. The claim type is pairwise, never absolute or rating; the metric is the head-to-head win
     rate, which refuses headroom; no field holds a pool score, a progress score or a value_text; and the frozen
     upstream record is a wins-ties-losses record and nothing else. The one number is the maintainers' own win
     rate, read from that record and agreeing with the pair's record in the same response.
  4. The evaluator pool, the venue and the episode protocol, in each claim's EvalConditions: venue names the
     pair's evaluator organisations and accounts, n_samples its A/B evaluations, subset_used the pair; harness is
     the A/B protocol, cited to the paper's passage; the simulator pair answers `none` (P3-S6-T05's convention for a
     real-robot claim); every material field is answered.
  5. No surface can rank them absolutely: the six claims have six comparability keys, so 04 S8's comparison view
     refuses to plot any two together and renders a diff instead, and the metric's headroom is null. The key does
     not read `opponent`, which is why subset_used names the pair.
  6. The failure cases: a claim without an opponent, an absolute claim, a rating-metric claim, a pool that lacks a
     member or postdates the claim, and two pairs whose conditions do not name the pair (their keys collide).

Ids are content-derived (05 S2), as the files' headers say, and are recomputed here.
"""
import glob
import hashlib
import json
import os
import re
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import Organization, RatingPool  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'robotics-embodiment', 'roboarena.yaml')
SHARD = os.path.join(ROOT, 'data', 'claims', 'roboarena')
METRIC = 'roboarena-pairwise-win-rate'
POOL_REF = re.compile(r'\bpool-roboarena-\d{4}-\d{2}(?:-\d{2})?\b')
RECORD_KEYS = {'count', 'losses', 'policy', 'tie_rate', 'ties', 'win_rate', 'wins'}   # a wins-ties-losses record
BOARD_ROW = re.compile(r'"num_evals":(\d+),"open_source":\w+,"policy":"([^"]+)"')     # one policy on a weekly board
PROTOCOL = ('randomly samples two policies',
            'the evaluators do not know which policies they are evaluating',
            'the evaluator arranges the evaluation scene',
            'back-to-back until the task is completed or a fixed timeout is reached',
            'to closely match the initial conditions within this A/B policy comparison',
            'a binary, pairwise preference label that indicates which policy the evaluator preferred')


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def source(sid):
    return Source.model_validate(load(os.path.join('sources', '2026'), sid))


def system(sid):
    return System.model_validate(load('systems', sid))


def conditions(cid):
    return EvalConditions.model_validate(load('conditions', cid))


def pool(pid):
    path = os.path.join(ROOT, 'data', 'rating-pools', pid + '.yaml')
    return RatingPool.model_validate(read_yaml(path)) if os.path.exists(path) else None


@pytest.fixture(scope='module')
def roboarena():
    return load_benchmark(ENTRY)


def raw_claims():
    """(repo-relative path, raw mapping) for every claim under data/claims/ on roboarena, wherever it lives."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict) and str(raw.get('benchmark', '')).partition('@')[0] == 'roboarena':
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), raw))
    return out


CLAIMS = [ResultClaim.model_validate(raw) for _, raw in raw_claims()]


# ---- the rule, as one function the corpus test and the failure cases share -----------------------------------

def pool_of(claim):
    """The claim's rating-pool id: the field when the schema lets a pairwise claim carry it, else the one pool id
    its notes name (the place P3-S6-T05's review check left for it). None when there is not exactly one."""
    if claim.rating_pool is not None:
        return claim.rating_pool
    found = set(POOL_REF.findall(claim.notes or ''))
    return found.pop() if len(found) == 1 else None


def board(p):
    """{backend id: num_evals} for the pool's snapshot, read from the Source that holds it."""
    header = '"policy_count":%d,"snapshot_at":"%s' % (len(p.members), p.snapshot_date.isoformat())
    for sid in p.sources:
        x = source(sid).quote_extract or ''
        at = x.find(header)
        if at < 0:
            continue
        start = x.rfind('{"board":[', 0, at)
        rows = x[start:at]
        assert ' … ' not in rows, '%s: the snapshot\'s board is cut by a window in %s' % (p.id, sid)
        return {m.group(2): int(m.group(1)) for m in BOARD_ROW.finditer(rows)}
    return None


def counted(extract):
    """(total A/B evaluations, date of the last) as the transparency summary states them."""
    total = re.search(r'"total_evals":(\d+)', extract)
    last = re.search(r'"generated_at":"[^"]+","last_eval_at":"(\d{4}-\d{2}-\d{2})', extract)
    return (int(total.group(1)) if total else None), (last.group(1) if last else None)


def problems(claim, metrics=None):
    """Why a RoboArena claim breaks P3-S8-T05's rule; empty when it holds."""
    out = []
    if claim.claim_type != 'pairwise':
        out.append('claim_type %s: a RoboArena claim here is pairwise, never absolute' % claim.claim_type)
    if claim.opponent is None or claim.opponent.split('@')[0] == claim.system.split('@')[0]:
        out.append('no opponent other than the system itself')
    if claim.metric != METRIC:
        out.append('metric %s is not the head-to-head win rate' % claim.metric)
    m = (metrics or {}).get(claim.metric) or Metric.model_validate(load('metrics', claim.metric))
    if m.headroom_computable or m.headroom_null_reason() is None:
        out.append('metric %s would carry headroom' % m.id)
    if claim.value_text is not None or claim.uncertainty is not None:
        out.append('a second value beside the head-to-head rate')
    pid = pool_of(claim)
    p = pool(pid) if pid else None
    if p is None:
        out.append('names no RoboArena rating pool that exists (%s)' % pid)
    else:
        if p.benchmark.partition('@')[0] != 'roboarena':
            out.append('%s is not a RoboArena pool' % p.id)
        missing = sorted({claim.system, claim.opponent or ''} - set(p.members))
        if missing:
            out.append('%s lacks %s' % (p.id, ', '.join(missing)))
        if p.snapshot_date > claim.date_reported:
            out.append('%s postdates the claim (%s)' % (p.id, claim.date_reported))
        total, last = counted(source(claim.source).quote_extract or '')
        if last is None or p.snapshot_date.isoformat() < last:
            out.append('%s predates the last A/B evaluation the claim\'s Source counts (%s)' % (p.id, last))
        rows = board(p)
        if rows is None or total is None or sum(rows.values()) != 2 * total:
            out.append('%s does not rate the %s A/B evaluations the claim\'s Source counts' % (p.id, total))
    return out


# ---- 1. six pairwise claims -----------------------------------------------------------------------------------

def test_six_pairwise_claims_in_the_shard():
    paths = [rel for rel, _ in raw_claims()]
    assert len(CLAIMS) == 6
    assert all(rel.startswith('data/claims/roboarena/') for rel in paths), paths
    assert len({(c.system, c.opponent) for c in CLAIMS}) == 6
    assert len({frozenset((c.system, c.opponent)) for c in CLAIMS}) == 6          # no pair stated from both sides


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_every_claim_is_pairwise_with_an_opponent_and_a_rating_pool(claim):
    assert claim.claim_type == 'pairwise' and claim.metric == METRIC
    assert claim.opponent is not None and claim.opponent != claim.system
    for sid in (claim.system, claim.opponent):
        assert system(sid).system_type == 'physical-robot-system'
    assert pool_of(claim) is not None, 'the claim names no rating pool'
    assert problems(claim) == []


def test_the_pool_is_in_notes_only_because_the_schema_refuses_it_on_a_pairwise_claim():
    """The gap, stated. When schema/claim.py lets a pairwise claim carry rating_pool this fails: move each claim's
    pool from its notes into the field, and drop this test."""
    doc = read_yaml(os.path.join(SHARD, CLAIMS[0].id + '.yaml'))
    assert doc['rating_pool'] is None
    with pytest.raises(ValidationError, match='rating claims only'):
        ResultClaim.model_validate({**doc, 'rating_pool': pool_of(CLAIMS[0])})


# ---- 3. no absolute value ---------------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_no_absolute_value_field_is_set(claim, roboarena):
    assert claim.claim_type not in ('absolute', 'rating')
    m = Metric.model_validate(load('metrics', claim.metric))
    assert not m.headroom_computable and m.headroom_null_reason() is not None and not m.requires_pool
    assert claim.metric != roboarena.headline_metric                       # never the pool score
    assert claim.value_text is None and claim.uncertainty is None
    snap = claim.provenance_snapshot
    assert snap is not None and set(snap.raw) == RECORD_KEYS              # a wins-ties-losses record, nothing else
    assert all(b.value is None for b in roboarena.baselines)              # and no absolute anchor beside it


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_the_value_is_the_maintainers_record_and_agrees_with_the_pair(claim):
    raw = claim.provenance_snapshot.raw
    assert claim.value == raw['win_rate'] == round(100 * raw['wins'] / (raw['wins'] + raw['losses']), 1)
    assert 0 <= claim.value <= 100
    extract = source(claim.source).quote_extract
    assert quote_found(json.dumps(raw, sort_keys=True, separators=(',', ':')), extract)
    owner = re.fullmatch(r'transparency_summary#policy=([^&]+)&opponent=([^&]+)', snap_id(claim))
    assert owner, snap_id(claim)
    mine, theirs = owner.groups()
    assert system(claim.system).external_ids['roboarena_policy'] == mine
    assert system(claim.opponent).external_ids['roboarena_policy'] == theirs == raw['policy']
    pair = pair_record(extract, mine, theirs)
    side = 'policy1' if pair['policy1'] == mine else 'policy2'
    other = 'policy2' if side == 'policy1' else 'policy1'
    assert (pair['count'], pair[side + '_wins'], pair[other + '_wins'], pair['ties']) == \
        (raw['count'], raw['wins'], raw['losses'], raw['ties'])


def snap_id(claim):
    return claim.provenance_snapshot.source_record_id


def pair_record(extract, a, b):
    """The pair's head-to-head record in the transparency summary's extract, whichever side is policy1."""
    for m in re.finditer(r'\{"count":\d+,"evaluator_count":[^{}]*\}', extract):
        rec = json.loads(m.group(0))
        if {rec['policy1'], rec['policy2']} == {a, b}:
            return rec
    raise AssertionError('no pair record for %s and %s' % (a, b))


# ---- 4. the evaluator pool, the venue and the episode protocol ---------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_the_evaluator_pool_venue_and_episode_protocol_are_recorded(claim, roboarena):
    cond = conditions(claim.eval_conditions)
    mine, theirs = re.fullmatch(r'transparency_summary#policy=([^&]+)&opponent=([^&]+)', snap_id(claim)).groups()
    pair = pair_record(source(claim.source).quote_extract, mine, theirs)
    assert cond.hardware_platform == 'DROID'
    assert (cond.simulator, cond.simulator_version) == ('none', 'none')
    assert 'evaluator organisations' in cond.venue and 'evaluator accounts' in cond.venue
    assert '%d evaluator organisations' % pair['lab_count'] in cond.venue
    assert '(%d evaluator accounts)' % pair['evaluator_count'] in cond.venue
    assert cond.n_samples == pair['count']
    assert mine in cond.subset_used and theirs in cond.subset_used and str(pair['count']) in cond.subset_used
    assert cond.human_in_loop is True
    assert cond.harness and 'back-to-back' in cond.harness and 'timeout' in cond.harness
    paper = source(cond.harness_source)
    assert paper.doi == '10.48550/arXiv.2506.18123'
    for q in PROTOCOL:
        assert quote_found(q, paper.quote_extract), q
    r = comp.resolve_profile(roboarena)
    c = comp.compute_for_claim(claim, r, cond)
    assert c.key_unknown_count == 0 and c.condition_completeness == 1.0


# ---- 5. no surface can rank them absolutely -----------------------------------------------------------------------

def test_no_two_pairs_share_a_comparability_key(roboarena):
    r = comp.resolve_profile(roboarena)
    keys = {comp.compute_for_claim(c, r, conditions(c.eval_conditions)).comparability_key for c in CLAIMS}
    assert len(keys) == len(CLAIMS)


# ---- 6. the failure cases ------------------------------------------------------------------------------------------

def test_a_claim_without_an_opponent_is_refused_and_an_absolute_one_is_caught():
    doc = read_yaml(os.path.join(SHARD, CLAIMS[0].id + '.yaml'))
    with pytest.raises(ValidationError, match='requires an opponent'):
        ResultClaim.model_validate({k: v for k, v in doc.items() if k != 'opponent'})
    # an absolute claim is a valid ResultClaim, which is why the rule has to be a test
    absolute = ResultClaim.model_validate({**{k: v for k, v in doc.items() if k != 'opponent'},
                                           'claim_type': 'absolute'})
    assert any('never absolute' in p for p in problems(absolute))
    assert any('no opponent' in p for p in problems(absolute))
    rated = ResultClaim.model_validate({**{k: v for k, v in doc.items() if k != 'opponent'}, 'claim_type': 'rating',
                                        'metric': 'roboarena-rating', 'value': 1735, 'rating_pool': pool_of(CLAIMS[0])})
    found = problems(rated)
    assert any('never absolute' in p for p in found) and any('not the head-to-head' in p for p in found)


def test_a_pool_that_lacks_a_member_or_postdates_the_claim_is_caught():
    [apricot] = [c for c in CLAIMS if c.system == 'apricot']
    early = apricot.model_copy(update={'notes': apricot.notes.replace(pool_of(apricot), 'pool-roboarena-2026-06-10')})
    found = problems(early)
    assert any('lacks apricot' in p for p in found), found                 # it joined after the first snapshot
    assert any('predates the last A/B evaluation' in p for p in found), found
    assert any('does not rate' in p for p in found), found
    late = apricot.model_copy(update={'date_reported': apricot.date_reported.replace(month=11, day=1)})
    assert any('postdates the claim' in p for p in problems(late))
    nameless = apricot.model_copy(update={'notes': 'no pool named'})
    assert any('names no RoboArena rating pool' in p for p in problems(nameless))


def test_without_the_pair_in_its_conditions_two_win_rates_would_share_a_key(roboarena):
    """The failure case for ranking: the key reads benchmark, metric, subset and the material conditions, never the
    opponent. Two pairs whose conditions said only 'every A/B evaluation' would get one key, and the comparison view
    would plot -- and sort -- their win rates as if they measured the same thing."""
    r = comp.resolve_profile(roboarena)
    a, b = CLAIMS[0], CLAIMS[1]
    generic = dict(hardware_platform='DROID', simulator='none', simulator_version='none', n_samples=36,
                   venue='the RoboArena evaluator network', subset_used='counted public A/B evaluations')
    ca = EvalConditions(id='cond-0123456789ab', **generic)
    assert comp.compute_for_claim(a, r, ca).comparability_key == comp.compute_for_claim(b, r, ca).comparability_key
    assert a.opponent != b.opponent


# ---- the records' identity and provenance ------------------------------------------------------------------------

def _content_id(prefix, d):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8'))
                      .hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_ids_are_content_derived(claim, roboarena):
    key = {'benchmark': claim.benchmark, 'system': claim.system, 'metric': claim.metric, 'subset': claim.subset,
           'value': claim.value, 'source': claim.source, 'date_reported': claim.date_reported.isoformat()}
    assert claim.id == _content_id('claim', key)
    cond = conditions(claim.eval_conditions)
    material = comp.resolve_profile(roboarena).material
    assert cond.id == _content_id('cond', {f: comp.canonicalise(cond.value(f)) for f in material})


def test_the_reporter_and_the_sources():
    org = Organization.model_validate(load('organizations', 'org-roboarena'))
    assert {c.reported_by for c in CLAIMS} == {org.id} and 'evaluator' in org.roles
    assert {c.verification for c in CLAIMS} == {'maintainer-verified'}
    for sid in {c.source for c in CLAIMS}:
        s = source(sid)
        # the body lists evaluator accounts by e-mail address: withheld from archiving, and none in the extract
        assert s.contains_personal_data is True and s.archive_status == 'withheld' and s.failure_reason
        assert '@' not in s.quote_extract
    for sid in {conditions(c.eval_conditions).harness_source for c in CLAIMS}:
        s = source(sid)
        assert s.doi and s.archive_status == 'not-required' and s.contains_personal_data is True   # a byline
