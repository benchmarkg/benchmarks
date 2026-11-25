"""Open Catalyst claims, batch 2: four OCx24 claims whose ground truth is a laboratory measurement (P3-S7-T04;
04-data-model.md S7, S8).

The verify: "bench validate --tier all, plus a test asserting the OCx24 claims carry verification
prospective-experiment and a non-null assay_protocol". The done-when: "Eight Open Catalyst claims exist and wet-lab
ground truth is distinguishable from the computational splits." Each rule is a function that returns what is wrong;
it runs on the committed claims, which must pass, and on copies broken the way the rule names, which must fail.

  1. Four claims in data/claims/oc20/ on oc20@ocx24. OCx24 is a version of the oc20 entry (P3-S6-T02), not an entry of
     its own, and its cross-validation subsets carry r-squared as their metric_override. Two are the paper's linear
     models for hydrogen evolution, leaving one composition out, which share a conditions record and a comparability
     key; two are its random forest for the H2 production rate under CO2 reduction, under the two strategies. The
     forest's pair is one (benchmark, system, metric) group over two subsets, so bench report conflicts shows no row
     for it and tests/report/test_reports.py's pin is unchanged. With batch 1's four OC20 claims, eight.
  2. A non-null assay_protocol (the verify's second half): each claim's conditions name the OCx24 paper, a DOI Source
     of the ocx24 version whose extract quotes the electrochemical protocol, and the Source the claim's subsets quote
     for that protocol. No OC20 claim's conditions name one.
  3. Wet-lab ground truth is told from the computational splits by the records alone: on every Open Catalyst claim the
     version, the subset (whose evidence quotes a laboratory protocol, or does not) and the assay_protocol agree, and
     no OCx24 claim shares a comparability key with an OC20 one. The failure cases: an OCx24 claim without an
     assay_protocol, an OC20 claim given one, and an OCx24 claim filed on an OC20 split.
  4. The rung (the verify's first half, which the sources do not support). prospective-experiment is ground truth that
     "did not exist at submission and was generated afterwards by the evaluator" (taxonomy/verification.yaml, rank 5).
     OCx24's models are fitted to its measurements and scored by cross-validation over them, and the measurements'
     summaries are public, as the oc20 entry's review check recorded before these claims existed. So
     prospective_problems() finds that evidence for every OCx24 claim, and a copy set to prospective-experiment is
     refused. What the claims hold is maintainer-verified, set by hand: the maintainers fitted, scored and reported
     each model in their own paper (the reporter, the system's organisation and the Source agree). A claim on someone
     else's model, or from a Source outside the ocx24 version, is refused.
  5. Every number is the paper's: each claim's notes quote the sentence that prints the value (`Value (<source>):
     "..."`) and, where that sentence does not name it, the strategy (`Strategy (<source>): "..."`). The quotes are in
     the claim's Source's extract, the one "R2 = x" in the value quote is the value, the one strategy named is the
     subset's, and a CO2 reduction claim's value quote and subset_used name the same product.
  6. Comparability (both of oc20's material fields answered), not LLM-run, and content-derived ids (05 S2).
"""
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.source import Source, quote_found  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import conflicts, llm_run  # noqa: E402

BID, VERSION = 'oc20', 'ocx24'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BID + '.yaml')
RUNG = 'maintainer-verified'
ASKED = 'prospective-experiment'                     # the ledger's rung, which the sources refuse (rule 4)
REPORTER = 'org-open-catalyst-project'
PAPER = 'src-arxiv-2411-11783-v1'
DOCS = 'src-github-fairchem-docs-ocx24-d733f48'
# The paper's electrochemical protocol, as the OCx24 subsets quote it: what makes their ground truth a measurement.
PROTOCOL = ('The testing process began with the electrolyzer operating at 50 mA/cm2 for 9 minutes to evaluate HER '
            'activity',
            'the CO2RR was carried out at current densities of 50, 100, 150, 200, and 300 mA/cm2 for 9 minutes each')
# What the sources say about when OCx24's ground truth existed, relative to the models scored on it.
FITTED = ('models trained on experimental data using computational descriptors as input can produce results that are '
          'predictive of held out experimental data')
CROSS_VALIDATED = ('Hold out a given sample, train on the remaining data',
                   'Hold out all samples with a given composition')
PUBLIC = 'Summaries of this data are all publicly available'

VALUE = re.compile(r'Value \((src-[a-z0-9-]+)\): "([^"]+)"')
STRATEGY = re.compile(r'Strategy \((src-[a-z0-9-]+)\): "([^"]+)"')
R2 = re.compile(r'R2 = (-?[0-9.]+)')
STRATEGIES = re.compile(r'\b(LOO|LOCO)\b')
PRODUCTS = re.compile(r'\b(H2|CO|CH4|C2H4)\b')


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def source(sid):
    return Source.model_validate(load(os.path.join('sources', '2026'), sid))


def conditions(claim):
    return EvalConditions.model_validate(load('conditions', claim.eval_conditions)) if claim.eval_conditions else None


def system(claim):
    return System.model_validate(load('systems', claim.system))


def oc_claims():
    """(repo-relative path, claim) for every claim on oc20, any version, wherever it lives."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict) and str(raw.get('benchmark', '')).partition('@')[0] == BID:
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), ResultClaim.model_validate(raw)))
    return out


ALL = oc_claims()
PATHS = {c.id: rel for rel, c in ALL}
CLAIMS = [c for _, c in ALL if c.benchmark == '%s@%s' % (BID, VERSION)]
OTHERS = [c for _, c in ALL if c.benchmark != '%s@%s' % (BID, VERSION)]


@pytest.fixture(scope='module')
def entry():
    return load_benchmark(ENTRY)


# ---- the rules ------------------------------------------------------------------------------------------------

def chain(subset_id, b):
    """The evidence of a subset and of every ancestor, and the ancestors' ids (the subset's own first)."""
    by_id = {s.id: s for s in b.subsets}
    s, evidence, ids = by_id.get(subset_id), [], []
    while s is not None:
        evidence += list(s.evidence)
        ids.append(s.id)
        s = by_id.get(s.parent) if s.parent else None
    return evidence, ids


def version_sources(b, version=VERSION):
    return set(next(v for v in b.versions if v.version == version).sources)


def measured(claim, b):
    """The Source of the laboratory protocol the claim's subset quotes, or None when its ground truth is computed."""
    for ev in chain(claim.subset, b)[0]:
        if ev.quote in PROTOCOL and quote_found(ev.quote, source(ev.source).quote_extract or ''):
            return ev.source
    return None


def ground_truth_problems(claim, cond, b):
    """Why the claim's record does not say plainly whether its ground truth is a measurement or a computation."""
    out = []
    version = claim.benchmark.partition('@')[2]
    lab = measured(claim, b)
    protocol = cond.assay_protocol if cond is not None else None
    if (version == VERSION) != (lab is not None):
        out.append('%s on %s: the version says %s, the subset %s' % (
            claim.subset, claim.benchmark, 'measured' if version == VERSION else 'computed',
            'measured' if lab else 'computed'))
    if lab is not None and protocol is None:
        out.append('%s is a laboratory measurement but its conditions name no assay_protocol' % claim.subset)
    if lab is None and protocol is not None:
        out.append('%s is computed but its conditions name the assay_protocol %s' % (claim.subset, protocol))
    if protocol is not None:
        src = source(protocol)
        if not any(quote_found(q, src.quote_extract or '') for q in PROTOCOL):
            out.append('assay_protocol %s quotes no laboratory protocol' % protocol)
        if protocol not in version_sources(b):
            out.append('assay_protocol %s is not a source of %s@%s' % (protocol, BID, VERSION))
        if lab is not None and lab != protocol:
            out.append('assay_protocol %s is not %s, the Source the subset quotes its protocol from' % (protocol, lab))
    return out


def prospective_problems(claim, b):
    """Why the claim's ground truth was not generated after its prediction (rank 5): the quotes, in its subset's
    evidence and its Source, saying the model was cross-validated on the measurements or fitted to them, or that they
    were public. Empty when no source read says so, which alone would not make a claim prospective."""
    evidence = [ev for ev in chain(claim.subset, b)[0] if quote_found(ev.quote, source(ev.source).quote_extract or '')]
    out = ['%s is scored by cross-validation over the measurements the model trains on: "%s"' % (claim.subset, q)
           for q in CROSS_VALIDATED if any(q in ev.quote for ev in evidence)]
    if any(PUBLIC in ev.quote for ev in evidence):
        out.append('the measurements were public: "%s"' % PUBLIC)
    if quote_found(FITTED, source(claim.source).quote_extract or ''):
        out.append('the model is trained on the measurements: "%s"' % FITTED)
    return out


def rung_problems(claim, rel, b, sys_record=None):
    """Why the claim may not hold the rung it holds, as P3-S7-T04 sets it."""
    out = []
    if claim.verification == ASKED:
        why = prospective_problems(claim, b)
        if why:
            out.append('prospective-experiment, but the ground truth predates the model: ' + '; '.join(why))
    if claim.verification != RUNG:
        out.append('verification %s, not %s' % (claim.verification, RUNG))
    if claim.ingestion is not None or '/_ingested/' in '/' + rel:
        out.append('the verification was written by an adapter, not set by hand')
    sys_record = sys_record or system(claim)
    if claim.reported_by != REPORTER:
        out.append('reported by %s, not the maintainers (%s)' % (claim.reported_by, REPORTER))
    if sys_record.organization != REPORTER:
        out.append('%s is %s\'s, not the maintainers\', so they did not run it'
                   % (sys_record.id, sys_record.organization))
    if claim.source not in version_sources(b):
        out.append('%s is not a source of %s@%s, the maintainers\' own paper' % (claim.source, BID, VERSION))
    return out


def number_problems(claim, cond):
    """Why the claim's value is not the number the paper prints for its model, strategy and target."""
    values = VALUE.findall(claim.notes or '')
    if len(values) != 1:
        return ['the notes quote %d value sentences, not one' % len(values)]
    sid, quote = values[0]
    out = []
    if sid != claim.source:
        out.append('the value is quoted from %s, not the claim\'s Source %s' % (sid, claim.source))
    if not quote_found(quote, source(sid).quote_extract or ''):
        out.append('the value quote is not in %s' % sid)
    printed = R2.findall(quote)
    if len(printed) != 1:
        out.append('the value quote prints %d R2 values, not one' % len(printed))
    elif float(printed[0]) != claim.value:
        out.append('value %s is not the printed %s' % (claim.value, printed[0]))
    quotes = [quote] + [q for s, q in STRATEGY.findall(claim.notes) if quote_found(q, source(s).quote_extract or '')]
    named = {t for q in quotes for t in STRATEGIES.findall(q)}
    want = claim.subset.rsplit('-', 1)[-1].upper()               # oc20#ocx24-her-loco -> LOCO
    if named != {want}:
        out.append('the quotes name the strategy %s, the subset %s' % (sorted(named), want))
    if '-co2rr-' in claim.subset:
        said, used = PRODUCTS.findall(quote), PRODUCTS.findall(cond.subset_used or '') if cond else []
        if len(said) != 1 or used != said:
            out.append('the value quote names the product %s, subset_used %s' % (said, used))
    return out


# ---- 1. four claims, eight in all ----------------------------------------------------------------------------------

def test_four_ocx24_claims_eight_open_catalyst_claims():
    assert len(CLAIMS) == 4 and len(ALL) == 8
    assert Counter(c.benchmark for c in OTHERS) == {'oc20@oc20': 4}
    assert all(PATHS[c.id].startswith('data/claims/oc20/') for c in CLAIMS)
    assert {c.metric for c in CLAIMS} == {'r-squared'} and {c.claim_type for c in CLAIMS} == {'absolute'}
    assert sorted(c.subset for c in CLAIMS) == ['oc20#ocx24-co2rr-loco', 'oc20#ocx24-co2rr-loo',
                                                'oc20#ocx24-her-loco', 'oc20#ocx24-her-loco']
    assert {c.reported_by for c in CLAIMS} == {REPORTER} and {c.source for c in CLAIMS} == {PAPER}


def test_ocx24_is_a_version_of_oc20_with_r_squared_on_its_subsets(entry):
    assert VERSION in {v.version for v in entry.versions}
    by_id = {s.id: s for s in entry.subsets}
    assert all(by_id[c.subset].metric_override == c.metric for c in CLAIMS)
    assert not os.path.exists(os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', 'ocx24.yaml'))


def test_one_group_of_two_over_two_subsets_and_no_conflict_row():
    groups = Counter((c.benchmark, c.system, c.metric) for c in CLAIMS)
    assert sorted(groups.values()) == [1, 1, 2]
    pair = [c for c in CLAIMS if groups[(c.benchmark, c.system, c.metric)] == 2]
    assert {c.subset for c in pair} == {'oc20#ocx24-co2rr-loo', 'oc20#ocx24-co2rr-loco'}
    rows = conflicts.build(ROOT)['rows']
    assert not [r for r in rows if r['benchmark'].partition('@')[0] == BID]


# ---- 2 and 3. a non-null assay_protocol, and wet-lab told from computed ---------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_every_ocx24_claim_names_its_assay_protocol(claim, entry):
    cond = conditions(claim)
    assert cond is not None and cond.assay_protocol == PAPER
    assert measured(claim, entry) == PAPER
    assert ground_truth_problems(claim, cond, entry) == []
    src = source(PAPER)
    assert src.doi and src.archive_status == 'not-required' and src.contains_personal_data is False


@pytest.mark.parametrize('claim', OTHERS, ids=lambda c: c.id)
def test_no_computed_claim_names_one(claim, entry):
    cond = conditions(claim)
    assert cond is not None and cond.assay_protocol is None
    assert measured(claim, entry) is None
    assert ground_truth_problems(claim, cond, entry) == []


def test_wet_lab_is_told_from_computed_by_the_records_alone(entry):
    lab = {c.id for _, c in ALL if measured(c, entry) and conditions(c).assay_protocol}
    assert lab == {c.id for c in CLAIMS}


def test_a_record_that_blurs_the_two_is_caught(entry):
    ocx24, oc20 = CLAIMS[0], OTHERS[0]
    bare = conditions(ocx24).model_copy(update={'assay_protocol': None})
    assert 'no assay_protocol' in ' '.join(ground_truth_problems(ocx24, bare, entry))
    given = conditions(oc20).model_copy(update={'assay_protocol': PAPER})
    assert any('computed but its conditions name the assay_protocol' in p
               for p in ground_truth_problems(oc20, given, entry))
    filed = ocx24.model_copy(update={'subset': 'oc20#oc20-test-ood-both'})
    assert any('the version says measured, the subset computed' in p
               for p in ground_truth_problems(filed, conditions(ocx24), entry))
    elsewhere = conditions(ocx24).model_copy(update={'assay_protocol': 'src-evalai-oc20-leaderboard-1946'})
    found = ground_truth_problems(ocx24, elsewhere, entry)
    assert any('quotes no laboratory protocol' in p for p in found) and any('not a source of' in p for p in found)


# ---- 4. the rung: not prospective-experiment, maintainer-verified --------------------------------------------------

def test_the_schema_carries_the_ledger_s_rung_and_field():
    """The verify's premise holds in the schema: the rung and the field exist. The sources refuse the rung."""
    rungs = {r['id']: r for r in read_yaml(os.path.join(ROOT, 'taxonomy', 'verification.yaml'))['rungs']}
    assert (rungs[ASKED]['rank'], rungs[ASKED]['machine_assignable']) == (5, False)
    assert 'generated afterwards by the evaluator' in rungs[ASKED]['meaning']
    assert 'assay_protocol' in EvalConditions.model_fields


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_premise_ocx24_ground_truth_predates_the_model(claim, entry):
    found = prospective_problems(claim, entry)
    assert len(found) == 3, found                     # cross-validated on, public, and fitted to
    assert claim.verification != ASKED


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_every_ocx24_claim_is_maintainer_verified_set_by_hand(claim, entry):
    assert claim.verification == RUNG and claim.ingestion is None
    assert rung_problems(claim, PATHS[claim.id], entry) == []


def test_the_entry_recorded_the_refusal_before_the_claims(entry):
    checks = [r.check for r in entry.curation.review_checks]
    assert any('prospective-experiment' in c and 'P3-S7-T04' in c for c in checks)
    org = load('organizations', REPORTER)
    assert 'benchmark-maintainer' in org['roles'] and org['name'] in entry.governance.maintainer


def test_the_ledger_s_rung_and_a_wrong_reporter_are_refused(entry):
    c = CLAIMS[0]
    asked = c.model_copy(update={'verification': ASKED})
    found = rung_problems(asked, PATHS[c.id], entry)
    assert found[0].startswith('prospective-experiment, but the ground truth predates the model')
    theirs = system(c).model_copy(update={'organization': None})
    assert any("not the maintainers', so they did not run it" in p
               for p in rung_problems(c, PATHS[c.id], entry, theirs))
    assert any('not the maintainers' in p
               for p in rung_problems(c.model_copy(update={'reported_by': 'org-meta-ai'}), PATHS[c.id], entry))
    assert any('not a source of' in p for p in rung_problems(
        c.model_copy(update={'source': 'src-arxiv-2010-09990-v5'}), PATHS[c.id], entry))
    assert any('by an adapter' in p
               for p in rung_problems(c, 'data/claims/_ingested/epoch/oc20/%s.yaml' % c.id, entry))


def test_the_rule_finds_no_such_evidence_on_the_oc20_test_set(entry):
    """The evidence is OCx24's own, not a blanket refusal: OC20's held-out claims (batch 1) carry none of it."""
    assert all(prospective_problems(c, entry) == [] for c in OTHERS)


# ---- 5. every number is the paper's ------------------------------------------------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_the_value_is_the_printed_r_squared(claim):
    assert number_problems(claim, conditions(claim)) == []
    assert 0 <= claim.value <= 1


def test_a_wrong_number_strategy_or_product_is_caught():
    her = next(c for c in CLAIMS if c.subset == 'oc20#ocx24-her-loco')
    assert any('is not the printed' in p for p in number_problems(her.model_copy(update={'value': 0.61}), None))
    assert number_problems(her.model_copy(update={'notes': 'no quote'}), None) == [
        'the notes quote 0 value sentences, not one']
    moved = her.model_copy(update={'notes': her.notes.replace('R2 = 0.', 'R2 = 0.0')})
    assert any('not in %s' % PAPER in p for p in number_problems(moved, None))
    loo = her.model_copy(update={'subset': 'oc20#ocx24-her-loo'})
    assert any("the quotes name the strategy ['LOCO'], the subset LOO" in p for p in number_problems(loo, None))
    co2rr = next(c for c in CLAIMS if c.subset == 'oc20#ocx24-co2rr-loo')
    as_co = conditions(co2rr).model_copy(update={'subset_used': conditions(co2rr).subset_used.replace('H2', 'CO')})
    assert any("names the product ['H2'], subset_used ['CO']" in p for p in number_problems(co2rr, as_co))


# ---- 6. comparability, the non-LLM count, the ids ----------------------------------------------------------------

def test_keys_split_by_strategy_and_never_meet_oc20_s(entry):
    r = comp.resolve_profile(entry)
    assert set(r.material) == {'subset_used', 'training_data_policy'} and 'assay_protocol' not in r.material
    key = {}
    for _, c in ALL:
        got = comp.compute_for_claim(c, r, conditions(c))
        assert got.condition_completeness == 1.0 and got.key_unknown_count == 0, c.id
        key[c.id] = got.comparability_key
    her = {key[c.id] for c in CLAIMS if c.subset == 'oc20#ocx24-her-loco'}
    co2rr = {key[c.id] for c in CLAIMS if '-co2rr-' in c.subset}
    assert len(her) == 1 and len(co2rr) == 2
    assert not {key[c.id] for c in CLAIMS} & {key[c.id] for c in OTHERS}


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_no_claim_is_llm_run(claim):
    assert llm_run.llm_run(claim.system) is False
    assert system(claim).system_type == 'scientific-surrogate-model' and system(claim).sources == [PAPER]


def test_the_sources_are_main_s():
    """No Source is new: the paper and the documentation page P3-S6-T02 read, the second withheld (author list)."""
    docs = source(DOCS)
    assert (docs.archive_status, docs.contains_personal_data, docs.archive_url) == ('withheld', True, None)
    named = {sid for c in CLAIMS for sid in re.findall(r'src-[a-z0-9-]+[a-z0-9]', c.notes)} | {c.source for c in CLAIMS}
    assert named == {PAPER, DOCS}
    assert all(BID in source(s).cited_by for s in named)


def _content_id(prefix, d):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8'))
                      .hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_ids_are_content_derived(claim):
    key = {'benchmark': claim.benchmark, 'system': claim.system, 'metric': claim.metric, 'subset': claim.subset,
           'value': claim.value, 'source': claim.source, 'date_reported': claim.date_reported.isoformat()}
    assert claim.id == _content_id('claim', key)
    raw = {k: v for k, v in load('conditions', claim.eval_conditions).items() if k != 'id'}
    assert claim.eval_conditions == _content_id('cond', {k: comp.canonicalise(v) for k, v in raw.items()})
