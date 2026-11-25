"""The CASP assessment-paper claims (P3-S8-T01; 04-data-model.md S7 and S8, 01-landscape-and-positioning.md S10).

The verify: "bench validate --tier all, plus a test asserting each source is a DOI'd assessment paper and that
server and human-expert claims carry different human_assistance values". The done-when: "Five claims exist whose
evidence is a peer-reviewed paper and whose two ranked populations are separable." 01 S10 puts CASP among the
families where nobody else holds the numbers, so they are curated by hand, from the assessors' papers in the
edition's Proteins issue rather than from the Prediction Center's ranking tables. Held here as:

  1. The five claims. data/claims/casp/ holds five, each on a CASP16 category casp declares and on a Metric record,
     inside the metric's range, across at least three categories.
  2. Each source is a DOI'd assessment paper: a `paper` with a Proteins DOI and a CASP assessment title, not a page
     of the Prediction Center's site, cited by casp and needing no archive; every passage a claim's notes quote is
     in that paper's extract, and a body that names people says so. The failure case: the Prediction Center's
     z-score table and a DOI'd paper that is not an assessment are both refused.
  3. Server and human-expert claims carry different human_assistance values: `none` on a server's, `permitted` on
     an expert group's (casp's review_checks convention), each resting on a passage that calls the group a server
     or a human group, so the two populations' values are disjoint. The failure case: an expert claim marked
     `none` is found.
  4. The populations are separable. One lab's server and human group, scored on the same eight antibody-antigen
     targets by the same count, agree on every other material field, and their comparability keys differ. The
     failure case: with the expert's human_assistance set to `none`, or with the field dropped from the material
     set, the two collide.
  5. No system is named after a person. CASP groups are often named after their lab heads, so a System takes its
     method's published name: every word of a system name is a method name, a word from a short list, or a
     number. The surnames the assessment papers use as group names are held here as hashes, so this file names
     nobody either, and none reaches the claims, their records or their Sources.
  6. Ids are content-derived (05 S2): a claim's over (benchmark, system, metric, subset, value, source,
     date_reported), a condition record's over its fields, with tools/build/comparability.py's canonicalise().
"""
import copy
import dataclasses
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
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import llm_run  # noqa: E402

CASP = os.path.join(ROOT, 'data', 'benchmarks', 'biology-genetics', 'casp.yaml')
SHARD = os.path.join(ROOT, 'data', 'claims', 'casp')
EXPERT_TYPES = frozenset({'human-ai-team', 'human-expert'})
# The passage that makes each group a server or a human group, in a Source the System cites.
POPULATION_BASIS = {
    'colabfold': ('src-casp16-overview', 'ColabFold, a server running AlphaFold2'),
    'cluspro': ('src-casp16-complex-2026-11-24', 'ClusPro (server group)'),
    'cluspro-lab-expert': ('src-casp16-complex-2026-11-24', '[name redacted] (human group from the same lab)'),
}
METHOD_NAMES = frozenset({'ColabFold', 'ClusPro'})
NAME_WORDS = frozenset({'lab', 'expert', 'group', 'server', 'CASP16'})
# sha256 (first 16 hex) of the lower-cased surnames, or surname-built group names, that the CASP16 monomer, complex
# and ligand assessments use for groups and their leads. Hashes, so that the guard names nobody.
SURNAME_HASHES = frozenset({
    '00a68fb02c76a327', '01380046d1d8e216', '12ee0558a76e208f', '16e115fa98cc285e', '211c963a9272a140',
    '2b2ee32a5b279f86', '3172951d74d9e2e0', '3abd72ec6352d608', '3f17783443a3c789', '700a18bcbf0b478c',
    '70dc47b39a5ffdfb', '71db309624124732', '7703ab16ea688763', '7829dfe67fcf5431', '95648b4276a5433d',
    'b0af954699aa3d87', 'b20a7d254bdab4ee', 'c00cbb714f0070a6', 'f7b21d4931e7b41f', 'fd5c3a80d5cf4a4a'})
CLAIM_KEYS = ('benchmark', 'system', 'metric', 'subset', 'value', 'source', 'date_reported')


def record(kind, ident):
    hits = glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    assert len(hits) == 1, (kind, ident, hits)
    return read_yaml(hits[0])


def source(sid):
    return Source.model_validate(record('sources', sid))


def system(sid):
    return System.model_validate(record('systems', sid))


def conditions(cid):
    return EvalConditions.model_validate(record('conditions', cid))


@pytest.fixture(scope='module')
def casp():
    return load_benchmark(CASP)


def claim_files():
    return sorted(glob.glob(os.path.join(SHARD, '*.yaml')))


CLAIMS = [ResultClaim.model_validate(read_yaml(p)) for p in claim_files()]
BY_SYSTEM = {}
for _c in CLAIMS:
    BY_SYSTEM.setdefault(_c.system, []).append(_c)


# ---- 1. the five claims ------------------------------------------------------------------------------------

def test_five_claims_on_declared_casp16_categories_and_metric_records(casp):
    assert len(CLAIMS) == 5
    subsets = {s.id for s in casp.subsets}
    for c in CLAIMS:
        assert c.benchmark == 'casp@casp16' and c.subset in subsets, c.id
        m = Metric.model_validate(record('metrics', c.metric))
        assert c.claim_type == 'absolute' and m.range.min <= c.value <= (m.range.max or c.value), c.id
    assert len({c.subset for c in CLAIMS}) >= 3
    assert len({c.metric for c in CLAIMS}) >= 4


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_each_claim_is_a_held_out_casp_result_reported_on_its_papers_date(claim):
    assert (claim.reported_by, claim.verification) == ('org-casp', 'held-out-server')
    Organization.model_validate(record('organizations', claim.reported_by))
    assert claim.date_reported == source(claim.source).published
    assert llm_run.llm_run(claim.system) is False                       # it counts toward the non-LLM claims
    assert claim.superseded_by is None and claim.result_group is None


# ---- 2. each source is a DOI'd assessment paper ------------------------------------------------------------

def source_problems(sid):
    """Why a claim's Source is not a DOI'd CASP assessment paper (empty when it is one)."""
    s = source(sid)
    out = []
    if s.type != 'paper':
        out.append('a %s, not a paper' % s.type)
    if not (s.doi or '').startswith('10.1002/prot.'):
        out.append('no Proteins DOI')
    title = (s.title or '').lower()
    if 'assessment' not in title or 'casp' not in title:
        out.append('not a CASP assessment')
    if 'predictioncenter.org' in s.url:
        out.append("a page of the Prediction Center's site")
    if 'casp' not in s.cited_by:
        out.append('not cited by casp')
    if s.archive_status != 'not-required':
        out.append('archive_status %s' % s.archive_status)
    return out


def test_verify_each_source_is_a_doid_assessment_paper():
    assert {c.source: source_problems(c.source) for c in CLAIMS} == {c.source: [] for c in CLAIMS}
    assert len({c.source for c in CLAIMS}) == 3                         # the monomer, complex and ligand papers


def test_verify_a_table_or_a_non_assessment_paper_is_refused():
    assert source_problems('src-casp16-zscores') == [
        'a leaderboard-page, not a paper', 'no Proteins DOI', 'not a CASP assessment',
        "a page of the Prediction Center's site", 'archive_status ok']
    assert source_problems('src-plosone-dockq-2016') == ['no Proteins DOI', 'not a CASP assessment',
                                                        'not cited by casp']


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_every_passage_a_claims_notes_quote_is_in_its_paper(claim):
    quotes = re.findall(r'"([^"]+)"', claim.notes or '')
    assert len(quotes) >= 4, claim.id
    extract = source(claim.source).quote_extract
    assert [q for q in quotes if not quote_found(q, extract)] == []


@pytest.mark.parametrize('sid', sorted({c.source for c in CLAIMS}))
def test_each_paper_says_its_body_names_people_and_counts_its_redactions(sid):
    s = source(sid)
    assert s.contains_personal_data is True and s.failure_reason is None
    assert s.quote_extract_redactions == s.quote_extract.count('[name redacted]')


# ---- 3. server and human-expert claims carry different human_assistance values -------------------------------

def population(system_id):
    return 'expert' if system(system_id).system_type in EXPERT_TYPES else 'server'


def assistance_problems(claims, cond_of):
    """Claims whose human_assistance is not their population's: `none` for a server, `permitted` for an expert."""
    want = {'server': 'none', 'expert': 'permitted'}
    return {c.id: '%s claim has human_assistance %s' % (population(c.system), cond_of(c).human_assistance)
            for c in claims if cond_of(c).human_assistance != want[population(c.system)]}


def by_record(c):
    return conditions(c.eval_conditions)


def test_verify_server_and_expert_claims_carry_different_human_assistance_values():
    assert assistance_problems(CLAIMS, by_record) == {}
    values = {p: {by_record(c).human_assistance for c in CLAIMS if population(c.system) == p}
              for p in ('server', 'expert')}
    assert values == {'server': {'none'}, 'expert': {'permitted'}}


def test_verify_an_expert_claim_marked_none_is_found():
    [expert] = [c for c in CLAIMS if population(c.system) == 'expert']
    marked = by_record(expert).model_copy(update={'human_assistance': 'none'})
    got = assistance_problems(CLAIMS, lambda c: marked if c.id == expert.id else by_record(c))
    assert got == {expert.id: 'expert claim has human_assistance none'}


@pytest.mark.parametrize('sid', sorted(POPULATION_BASIS))
def test_each_groups_population_rests_on_a_passage_it_cites(sid):
    src, quote = POPULATION_BASIS[sid]
    assert src in system(sid).sources and quote_found(quote, source(src).quote_extract)
    assert ('server' in quote) == (population(sid) == 'server')


# ---- 4. the two populations are separable ------------------------------------------------------------------

def the_pair():
    [server] = [c for c in BY_SYSTEM['cluspro'] if c.metric == 'dockq-acceptable-targets']
    [expert] = BY_SYSTEM['cluspro-lab-expert']
    return server, expert


def key(resolution, claim, cond):
    return comp.compute_for_claim(claim, resolution, cond).comparability_key


def test_verify_one_labs_server_and_expert_group_never_share_a_key(casp):
    r = comp.resolve_profile(casp)
    server, expert = the_pair()
    s, e = by_record(server), by_record(expert)
    assert (server.benchmark, server.metric, server.subset) == (expert.benchmark, expert.metric, expert.subset)
    differing = {f for f in r.material if s.value(f) != e.value(f)}
    assert differing == {'human_assistance'}                     # the one field between them
    assert key(r, server, s) != key(r, expert, e)
    assert (server.value, expert.value) == (3, 5)


def test_verify_without_human_assistance_the_pair_collides(casp):
    """The failure case, twice: the expert's record written `none`, and the field dropped from the material set."""
    r = comp.resolve_profile(casp)
    server, expert = the_pair()
    s, e = by_record(server), by_record(expert)
    assert key(r, server, s) == key(r, expert, e.model_copy(update={'human_assistance': 'none'}))
    blind = dataclasses.replace(r, material=tuple(f for f in r.material if f != 'human_assistance'),
                                weights={f: w for f, w in r.weights.items() if f != 'human_assistance'})
    assert key(blind, server, s) == key(blind, expert, e)


# ADR-0029 (P3-S10-T01) made training_data_policy material on CASP: [domain-metric, domain-specialist-model] resolves
# trained-model. No CASP source read states it, so it is unknown on every claim. The floor is held on the fields these
# claims were curated against, and the new field is named among the unknowns rather than hidden; answering it is
# claim curation.
SINCE_ADR_0029 = 'training_data_policy'


def test_every_claim_clears_the_comparison_floor_and_its_unknowns_are_named(casp):
    r = comp.resolve_profile(casp)
    curated = dataclasses.replace(r, material=tuple(f for f in r.material if f != SINCE_ADR_0029),
                                  weights={f: w for f, w in r.weights.items() if f != SINCE_ADR_0029})
    floor = read_yaml(os.path.join(ROOT, 'taxonomy', 'thresholds.yaml'))['thresholds']['comparison_floor']
    for c in CLAIMS:
        assert comp.compute_for_claim(c, curated, by_record(c)).condition_completeness >= floor, c.id
        got = comp.compute_for_claim(c, r, by_record(c))
        assert set(got.unknown_fields) <= {'assay_protocol', 'eligibility_track', 'selection_strategy',
                                           SINCE_ADR_0029}, c.id
        assert 'human_assistance' not in got.unknown_fields and 'subset_used' not in got.unknown_fields


# ---- 5. no system is named after a person ------------------------------------------------------------------

def name_problems(name):
    words = re.findall(r'[A-Za-z0-9]+', name)
    out = [w for w in words if not (w in METHOD_NAMES or w in NAME_WORDS or w.isdigit())]
    if not words or words[0] not in METHOD_NAMES:
        out.append('does not open with a method name')
    return out


def surnames(text, hashes=SURNAME_HASHES):
    return sorted({w for w in re.findall(r'[a-z]+', text.lower())
                   if hashlib.sha256(w.encode('utf-8')).hexdigest()[:16] in hashes})


@pytest.mark.parametrize('sid', sorted(BY_SYSTEM))
def test_no_system_is_named_after_a_person(sid):
    s = system(sid)
    assert name_problems(s.name) == [], s.name
    assert surnames(s.id + ' ' + s.name) == []


def touched_files():
    out = [os.path.join(SHARD, os.path.basename(p)) for p in claim_files()]
    for c in CLAIMS:
        for kind, ident in (('systems', c.system), ('conditions', c.eval_conditions), ('organizations', c.reported_by),
                            ('metrics', c.metric), ('sources', c.source)):
            out += glob.glob(os.path.join(ROOT, 'data', kind, '**', ident + '.yaml'), recursive=True)
    return sorted(set(out))


def test_no_surname_reaches_the_claims_their_records_or_their_sources():
    hits = {}
    for p in touched_files():
        with open(p, encoding='utf-8') as fh:
            found = surnames(fh.read())
        if found:
            hits[os.path.relpath(p, ROOT)] = len(found)
    assert hits == {}
    assert len(touched_files()) == 5 + 3 + 5 + 1 + 4 + 3        # claims, systems, conditions, org, metrics, sources


def test_the_guards_bite():
    assert name_problems('Surname lab server') == ['Surname', 'does not open with a method name']
    assert name_problems('ClusPro lab expert group (CASP16 group 274)') == []
    probe = frozenset({hashlib.sha256(b'placeholder').hexdigest()[:16]})
    assert surnames('the Placeholder group', probe) == ['placeholder']
    assert surnames('the [name redacted] group', probe) == []


# ---- 6. content-derived ids --------------------------------------------------------------------------------

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
