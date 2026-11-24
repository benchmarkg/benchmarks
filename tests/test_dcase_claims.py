"""The DCASE claims, each on a task-and-year child and never on the family (P3-S8-T07; 04-data-model.md S4 and S7,
02-taxonomy.md S11 rule 5).

The verify: "bench validate --tier all, plus a test asserting no claim references the DCASE family node". Done
when: "Four claims exist and the family/child convention is enforced by a test rather than by care."

Nothing else enforces it. A claim whose benchmark is the bare `dcase` is a valid ResultClaim, and the reference
tier resolves it, because `dcase` is a curated benchmark; the Subset model has no version field either, so a claim
pairing dcase@2026 with a 2025 subset passes both too (the entry's review_checks say so). This test is the rule:

  1. The four claims. data/claims/dcase/ holds four, across at least two tasks and two editions.
  2. No claim names the family. Every claim anywhere under data/claims/ whose benchmark is DCASE names an edition
     (dcase@<year>) and a task-and-year subset of that same edition that the entry declares, and lives in
     data/claims/dcase/ (05's sharding by benchmark id). tests/test_dcase_open_asr.py's claim_problems() is the
     rule; this adds the entry's declarations and the shard.
  3. The failure case: a claim on the family node, or on another year's child, written into a corpus copy, is
     found -- and it is a ResultClaim the schema accepts, which is why the test has to be the guard.
  4. What the claims are: non-LLM subjects, reported by the DCASE organisers on their held-out evaluation sets,
     on metrics that range over the values, and the two Task 2 claims, one task line a year apart, never share a
     comparability key.
  5. No person is named. DCASE submission labels begin with the corresponding author's surname; no label, and no
     unredacted row, reaches the claims, their systems or the extracts of the Sources they cite.
"""
import copy
import glob
import importlib.util
import os
import re
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.system import System  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.report import llm_run  # noqa: E402


def _module(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


C = _module('comparability_dcase_claims', os.path.join('tools', 'build', 'comparability.py'))
RULE = _module('dcase_family_rule', os.path.join('tests', 'test_dcase_open_asr.py'))

DCASE = os.path.join(ROOT, 'data', 'benchmarks', 'audio-speech', 'dcase.yaml')
SHARD = os.path.join('data', 'claims', 'dcase')
# A DCASE submission label: <surname>_<institution>_task<N>_<index>, the shape of `Surname_JKU_task1_4`.
LABEL = re.compile(r'\b[A-Z][A-Za-z-]+_[A-Za-z0-9-]+_[Tt]ask\d+[a-z]?_\d\b')


@pytest.fixture(scope='module')
def dcase():
    return load_benchmark(DCASE)


def read_claims(root):
    """(repo-relative path, raw mapping) for every claim file under root/data/claims/."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict):
            out.append((os.path.relpath(p, root).replace(os.sep, '/'), raw))
    return out


def family_problems(rel, raw, dcase):
    """Why a claim breaks DCASE's family/child rule, if it does (empty for a claim on another benchmark)."""
    if (raw.get('benchmark') or '').partition('@')[0] != 'dcase':
        return []
    out = list(RULE.claim_problems(raw))
    version = raw['benchmark'].partition('@')[2]
    if version and version not in {v.version for v in dcase.versions}:
        out.append('names edition %s, which the entry does not declare' % version)
    subset = raw.get('subset')
    if subset and subset not in {s.id for s in dcase.subsets}:
        out.append('names subset %s, which the entry does not declare' % subset)
    if not rel.startswith(SHARD.replace(os.sep, '/') + '/'):
        out.append('lives outside %s' % SHARD.replace(os.sep, '/'))
    return out


def corpus_problems(root, dcase):
    return {rel: p for rel, raw in read_claims(root) if (p := family_problems(rel, raw, dcase))}


def dcase_claims():
    return [ResultClaim.model_validate(raw) for rel, raw in read_claims(ROOT) if rel.startswith('data/claims/dcase/')]


CLAIMS = dcase_claims()


# ---- 1. the four claims ------------------------------------------------------------------------------------

def test_four_claims_across_two_tasks_and_two_editions():
    assert len(CLAIMS) == 4
    children = {c.subset for c in CLAIMS}
    years = {c.benchmark.partition('@')[2] for c in CLAIMS}
    tasks = {RULE.CHILD.match(s)['n'] for s in children}
    assert len(children) == 4 and len(years) >= 2 and len(tasks) >= 2, (children, years, tasks)


# ---- 2. no claim names the family --------------------------------------------------------------------------

def test_verify_no_claim_references_the_dcase_family_node(dcase):
    assert corpus_problems(ROOT, dcase) == {}


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_each_claim_names_an_edition_and_its_own_years_declared_child(claim, dcase):
    ident, _, version = claim.benchmark.partition('@')
    m = RULE.CHILD.match(claim.subset or '')
    assert (ident, bool(version), bool(m)) == ('dcase', True, True), claim.id
    assert m['year'] == version, claim.id
    assert version in {v.version for v in dcase.versions}
    assert claim.subset in {s.id for s in dcase.subsets}


# ---- 3. the failure case -----------------------------------------------------------------------------------

def write_claim(root, rel, raw):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(raw, sort_keys=False), encoding='utf-8')


def test_verify_fails_on_a_claim_that_references_the_family_node(tmp_path, dcase):
    good = read_yaml(os.path.join(ROOT, SHARD, CLAIMS[0].id + '.yaml'))
    write_claim(tmp_path, 'data/claims/dcase/good.yaml', good)
    assert corpus_problems(str(tmp_path), dcase) == {}

    family = dict(copy.deepcopy(good), benchmark='dcase')
    ResultClaim.model_validate(family)                         # the schema accepts it: only this test refuses it
    write_claim(tmp_path, 'data/claims/dcase/family.yaml', family)
    assert corpus_problems(str(tmp_path), dcase) == {
        'data/claims/dcase/family.yaml': ['names the DCASE family, not an edition']}


def test_verify_fails_on_the_family_with_no_subset_and_on_another_years_child(tmp_path, dcase):
    good = read_yaml(os.path.join(ROOT, SHARD, CLAIMS[0].id + '.yaml'))
    year = good['benchmark'].partition('@')[2]
    other = next(v.version for v in dcase.versions if v.version != year)
    write_claim(tmp_path, 'data/claims/dcase/bare.yaml', dict(good, benchmark='dcase', subset=None))
    write_claim(tmp_path, 'data/claims/dcase/cross.yaml', dict(good, benchmark='dcase@' + other))
    write_claim(tmp_path, 'data/claims/elsewhere/stray.yaml', good)
    write_claim(tmp_path, 'data/claims/dcase/undeclared.yaml', dict(good, subset='dcase#%s-task99' % year))
    got = corpus_problems(str(tmp_path), dcase)
    assert got['data/claims/dcase/bare.yaml'] == ['names the DCASE family, not an edition',
                                                  'names no task-and-year subset (None)']
    assert got['data/claims/dcase/cross.yaml'] == [
        'pairs edition %s with a %s subset, a cross-year comparison' % (other, year)]
    assert got['data/claims/elsewhere/stray.yaml'] == ['lives outside data/claims/dcase']
    assert got['data/claims/dcase/undeclared.yaml'] == ['names subset dcase#%s-task99, which the entry does not '
                                                        'declare' % year]


# ---- 4. what the claims are --------------------------------------------------------------------------------

def record(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_each_claim_is_a_non_llm_held_out_result_in_its_metrics_range(claim):
    system = System.model_validate(record('systems', claim.system))
    assert system.system_type == 'task-specific-supervised-model'
    assert llm_run.llm_run(claim.system) is False                       # it counts toward the non-LLM claims
    assert (claim.reported_by, claim.verification, claim.claim_type) == ('org-dcase-community', 'held-out-server',
                                                                         'absolute')
    metric = Metric.model_validate(record('metrics', claim.metric))
    assert metric.range.min <= claim.value <= metric.range.max and metric.units == 'percent'
    cond = EvalConditions.model_validate(record('conditions', claim.eval_conditions))
    assert cond.subset_used == 'evaluation dataset'
    source = record(os.path.join('sources', '2026'), claim.source)
    assert source['archive_status'] == 'withheld' and source['contains_personal_data'] is True


def test_one_task_line_a_year_apart_never_shares_a_key(dcase):
    resolution = C.resolve_profile(dcase, C.load_profiles())
    task2 = sorted((c for c in CLAIMS if c.subset.endswith('-task2')), key=lambda c: c.benchmark)
    assert [c.benchmark for c in task2] == ['dcase@2025', 'dcase@2026']
    assert task2[0].metric == task2[1].metric                              # one formula in both years
    keys = {C.compute_for_claim(c, resolution, EvalConditions.model_validate(record('conditions', c.eval_conditions)))
            .comparability_key for c in task2}
    assert len(keys) == 2


# ---- 5. no person is named ---------------------------------------------------------------------------------

def test_no_submission_label_reaches_the_claims_their_systems_or_their_extracts():
    texts = {}
    for c in CLAIMS:
        for kind, ident in (('claims/dcase', c.id), ('systems', c.system)):
            with open(os.path.join(ROOT, 'data', kind, ident + '.yaml'), encoding='utf-8') as fh:
                texts['%s/%s' % (kind, ident)] = fh.read()
        texts[c.source] = record(os.path.join('sources', '2026'), c.source)['quote_extract']
    hits = {k: LABEL.findall(v) for k, v in texts.items() if LABEL.search(v)}
    assert hits == {}
    assert LABEL.search('Surname_JKU_task1_4') and LABEL.search('Surname_GIST-HanwhaVision_task7_4')  # it bites
    assert not LABEL.search('[name redacted]_JKU_task1_4')
