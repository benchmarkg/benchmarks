"""The robotics cluster's per-benchmark claims: each decoded to a simulator, a simulator build and an embodiment, or a
stated reason a field is null (P3-S8-T06; 04-data-model.md S8, 01-landscape-and-positioning.md S2.5 and S10).

The verify: "bench validate --tier all, plus a test asserting each claim carries simulator, simulator_version and
hardware_platform or a stated reason each is null". The done-when: "Twelve robotics claims exist in total and each is
decodable to a specific sim build and embodiment." That is held here as:

  1. The claims. "The robotics cluster" is 01 S2.5's row (LIBERO, RoboCasa365, BEHAVIOR-1K and its challenge, Open
     X-Embodiment, ManiSkill, SimplerEnv, RoboTwin 2.0, Meta-World, RLBench, Habitat; P3-S5-T04, the task listed as a
     dependency, curated science bridge claims and defines no cluster). Outside RoboArena (P3-S8-T05's six) at least
     six claims sit on cluster benchmarks, across at least three of them, and the robotics-embodiment family holds
     at least twelve claims in all.
  2. The rule, as one function the corpus test and the failure cases share. Each claim names its EvalConditions; for
     each of simulator, simulator_version and hardware_platform the conditions carry a value, never a placeholder
     ("unknown", "n/a", "?"), or the field is null and the claim's notes state why: a sentence that begins
     "<field> null: " and cites at least one Source that exists. EvalConditions is a closed record with no field for
     a reason (schema/conditions.py), so the reason lives on the claim, where every surface that shows the claim
     shows it. The episode protocol is recorded too: harness with its harness_source, n_samples and
     selection_strategy.
  3. The decodes. Each answered field holds the token its Sources give, and every quote behind it (and behind each
     null's reason) is a substring of the cited Source's extract. Where a build is not decodable -- the 2025 BEHAVIOR
     evaluation ran on an unpublished main-branch commit, OpenVLA's LIBERO harness left robosuite unpinned -- the
     reason's quotes are checked the same way, so "unavailable" is itself a sourced finding.
  4. What the claims are: the value is in the quoted row of its Source; n_samples is the protocol's own product;
     condition_completeness clears 0.6; claims under one protocol share a comparability key (with the null field
     reported as unknown on both), claims on different embodiments never do; none counts as LLM-run.
  5. The failure cases: a null field with no reason, a placeholder in place of a null, a reason that cites no Source
     or one that does not exist, and conditions with no episode protocol -- each a record the schema accepts, which
     is why the rule has to be a test.
  6. The Sources: every new one is marked honestly (a DOI is not-required; a non-DOI body that names a person is
     withheld with a failure_reason; any other non-DOI is pending) and no extract holds an e-mail address.

Ids are content-derived (05 S2), as the files' headers say, and are recomputed here.
"""
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

FAMILY = os.path.join(ROOT, 'data', 'benchmarks', 'robotics-embodiment')
# 01 S2.5's "Robotics cluster" row, by entry id. Open X-Embodiment has no entry; the BEHAVIOR Challenge is
# behavior-1k's editions.
CLUSTER = ('libero', 'robocasa', 'behavior-1k', 'maniskill', 'simplerenv', 'robotwin', 'meta-world', 'rlbench',
           'habitat-challenge')
FIELDS = ('simulator', 'simulator_version', 'hardware_platform')
PLACEHOLDER = re.compile(r'^\s*(unknown|unk|n/?a|na|null|none given|not stated|tbd|todo|\?+|-+)\s*$', re.I)
SOURCE_ID = re.compile(r'\bsrc-[a-z0-9]+(?:-[a-z0-9]+)*\b')
REASON_FLOOR = 15                                  # words: a reason, not a shrug

BEHAVIOR_ROWS = 'src-behavior-challenge-2025-leaderboard'
B_EVAL = 'src-behavior-challenge-2025-evaluation-2026-11-24'
B_UPDATES = 'src-behavior-challenge-2025-updates-2026-11-24'
B_RELEASES = 'src-github-api-behavior-1k-releases-2026-11-24'
B_WINNER = 'src-arxiv-2512-06951-v2-html'
OPENVLA = 'src-arxiv-2406-09246-v3-html'
OV_README = 'src-github-openvla-readme-a793354'
OV_REQS = 'src-github-openvla-libero-requirements-a793354'
OV_UTILS = 'src-github-openvla-libero-utils-a793354'
OV_COMMITS = 'src-github-api-openvla-libero-requirements-commits-2026-11-24'
LIBERO_ENV = 'src-github-libero-env-wrapper-8f1084e'
SIMPLER = 'src-arxiv-2405-05941-v1-html'
MS2_REQS = 'src-github-maniskill2-real2sim-requirements-cd45dd2'
SUBMODULE = 'src-github-api-simplerenv-submodule-db69506'
SIM_COMMITS = 'src-github-api-simplerenv-commits-2024-05'

_BEHAVIOR = {
    'simulator': ('OmniGibson', [(B_WINNER, 'The benchmark uses OmniGibson simulation built on NVIDIA Isaac Sim')]),
    'simulator_version': (None, [
        (B_UPDATES, 'please always use the latest main branch of the BEHAVIOR-1K repo (which we will use for our '
                    'internal policy evaluation)'),
        (B_RELEASES, '"name":"BEHAVIOR-1K v3.7.1"'),
        ('src-behavior-challenge-2025', 'Submission Deadline: November 16th 11:59PM AoE, 2025'),
        (B_RELEASES, 'This is the post release of the 2025 BEHAVIOR Challenge at NeurIPS.'),
        (B_RELEASES, 'we add support for Isaac Sim 4.5')]),
    'hardware_platform': ('R1Pro', [(B_EVAL, 'OmniGibson/omnigibson/learning/configs/robot/r1pro.yaml'),
                                    (B_EVAL, 'absolute joint angles for all the robot joints (23-dim)')]),
    'protocol': [(B_EVAL, 'We will hold out 10 more instances for final evaluation.'),
                 (B_EVAL, 'we will evaluate the top-5 solutions on the leaderboard using these instances'),
                 (B_EVAL, 'You should evaluate your policy 1 time'),
                 (B_EVAL, 'Task success score: Averaged across 50 tasks.'),
                 (B_WINNER, 'private scores are computed on an additional held-out set of 10 instances per task')],
}
_LIBERO = {
    'simulator': ('robosuite', [(LIBERO_ENV, 'import robosuite as suite'), (LIBERO_ENV, 'renderer="mujoco"')]),
    'simulator_version': (None, [
        (OV_REQS, 'imageio[ffmpeg] robosuite bddl easydict'),
        (OV_COMMITS, '"message":"Add LIBERO sim eval script and instructions"'),
        (OV_COMMITS, '"message":"Pin robosuite==1.4.1 in libero_requirements.txt"'),
        (OV_README, 'Python 3.10.13, PyTorch 2.2.0, transformers 4.40.1, and flash-attn 2.5.5')]),
    'hardware_platform': ('Panda', [(LIBERO_ENV, 'robots=["Panda"]'),
                                    (OV_UTILS, 'env_args = {"bddl_file_name": task_bddl_file, "camera_heights": '
                                               'resolution, "camera_widths": resolution}')]),
    'protocol': [(OPENVLA, 'all methods are evaluated across 500 trials for each task suite'),
                 (OPENVLA, 'resulting in 1500 total trials per statistic'),
                 (OPENVLA, 'use the same initial environment configurations provided by the original LIBERO benchmark'),
                 (OV_README, 'Each success rate is the average over 3 random seeds x 500 rollouts each')],
}
_SIMPLER_BUILD = {
    'simulator': ('SAPIEN', [(SIMPLER, 'We instantiate SIMPLER on top of the SAPIEN physics simulator')]),
    'simulator_version': ('2.2.2', [(MS2_REQS, 'sapien==2.2.2'),
                                    (SUBMODULE, '"sha":"cd45dd27dc6bb26d048cb6570cdab4e3f935cc37"'),
                                    (SIM_COMMITS, '"sha":"db695066a93f774728f2ef477bdec7cf72028382"'),
                                    (SIM_COMMITS, '"date":"2024-05-09T15:19:27Z"')]),
}
# system -> (benchmark, the decode of each field and the protocol, the quoted row the value comes from, n_samples
# as the protocol's own factors)
DECODE = {
    'robot-learning-collective-behavior-2025': (
        'behavior-1k', _BEHAVIOR,
        (BEHAVIOR_ROWS, '1 Robot Learning Collective Independent Standard code report 0.1120 0.1240 0.2605 0.2599'),
        (50, 10, 1)),
    'comet-behavior-2025': (
        'behavior-1k', _BEHAVIOR,
        (BEHAVIOR_ROWS, '2 Comet NVIDIA Research Standard code report 0.1440 0.1140 0.1830 0.2514'), (50, 10, 1)),
    'openvla-7b-finetuned-libero-spatial': (
        'libero', _LIBERO, (OPENVLA, 'OpenVLA fine-tuned (ours) 84.7'), (10, 50, 3)),
    'octo-finetuned-libero-spatial': (
        'libero', _LIBERO, (OPENVLA, 'Octo fine-tuned 78.9'), (10, 50, 3)),
    'rt-1-converged': (
        'simplerenv', {**_SIMPLER_BUILD,
                       'hardware_platform': ('Google Robot', [
                           (SIMPLER, 'For the Google Robot, we adopt the following language-conditioned tasks')]),
                       'protocol': [(SIMPLER, 'yielding 25 trials per orientation and 75 trials in total'),
                                    (SIMPLER, 'we average results over four versions of robot arm and gripper colors'),
                                    (SIMPLER, 'the number of trials is multiplied by the number of tuned robot arm '
                                              'colors for the Google Robot evaluation setup')]},
        (SIMPLER, 'SIMPLER Eval (Visual Matching) RT-1 (Converged) 0.960 0.900 0.710 0.857'), (75, 4)),
    'octo-base': (
        'simplerenv', {**_SIMPLER_BUILD,
                       'hardware_platform': ('WidowX-250', [(SIMPLER, 'with WidowX-250 6DOF robot')]),
                       'protocol': [(SIMPLER, 'This creates a total of 2×12=242\\times 12=24 trials.'),
                                    (SIMPLER, 'along with the number of seeds for the Octo policies'),
                                    (SIMPLER, 'we average its success rates across three different random seeds')]},
        (SIMPLER, 'Octo-Base 0.347 0.125'), (24, 3)),
}
# Every Source this task added: (archive_status, contains_personal_data).
NEW_SOURCES = {
    B_EVAL: ('pending', False), B_UPDATES: ('pending', False),
    'src-behavior-challenge-2025-index-2026-11-24': ('withheld', True), B_RELEASES: ('withheld', True),
    B_WINNER: ('not-required', True), 'src-arxiv-2512-10071-v3-html': ('not-required', True),
    OPENVLA: ('not-required', True), OV_README: ('withheld', True), OV_REQS: ('pending', False),
    OV_UTILS: ('withheld', True), OV_COMMITS: ('withheld', True), LIBERO_ENV: ('pending', False),
    SIMPLER: ('not-required', True), SUBMODULE: ('pending', False), MS2_REQS: ('pending', False),
    SIM_COMMITS: ('withheld', True),
}
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')


def load(kind, ident):
    return read_yaml(os.path.join(ROOT, 'data', kind, ident + '.yaml'))


def source_raw(sid):
    path = os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml')
    return read_yaml(path) if os.path.exists(path) else None


def source(sid):
    return Source.model_validate(source_raw(sid))


def extract(sid):
    return source(sid).quote_extract or ''


def conditions(cid):
    return EvalConditions.model_validate(load('conditions', cid))


def benchmark(bid):
    return load_benchmark(os.path.join(FAMILY, bid + '.yaml'))


def family_claims():
    """(repo-relative path, ResultClaim) for every claim under data/claims/ on a robotics-embodiment benchmark."""
    family = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(FAMILY, '*.yaml'))}
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        raw = read_yaml(p)
        if isinstance(raw, dict) and str(raw.get('benchmark', '')).partition('@')[0] in family:
            out.append((os.path.relpath(p, ROOT).replace(os.sep, '/'), ResultClaim.model_validate(raw)))
    return out


FAMILY_CLAIMS = family_claims()
CLAIMS = [c for _, c in FAMILY_CLAIMS if c.benchmark.partition('@')[0] in CLUSTER]


# ---- the rule, as one function the corpus test and the failure cases share ------------------------------------

def reason_for(notes, field):
    """The stated reason `field` is null: the text after "<field> null: " up to the next such marker or the end."""
    others = '|'.join(re.escape(f) for f in FIELDS)
    m = re.search(r'(?<![a-z_])%s null: (.*?)(?=(?<![a-z_])(?:%s) null: |\Z)' % (re.escape(field), others),
                  notes or '', re.S)
    return m.group(1).strip() if m else None


def problems(claim, cond):
    """Why a cluster claim breaks P3-S8-T06's rule; empty when it holds."""
    if cond is None:
        return ['names no EvalConditions']
    out = []
    for f in FIELDS:
        v = getattr(cond, f)
        if v is not None:
            if PLACEHOLDER.match(v):
                out.append('%s is the placeholder %r, a null in disguise' % (f, v))
            continue
        why = reason_for(claim.notes, f)
        if why is None:
            out.append('%s is null with no stated reason ("%s null: ..." in the notes)' % (f, f))
            continue
        if len(why.split()) < REASON_FLOOR:
            out.append('%s null: the reason is under %d words' % (f, REASON_FLOOR))
        cited = set(SOURCE_ID.findall(why))
        if not cited:
            out.append('%s null: the reason cites no Source' % f)
        missing = sorted(s for s in cited if source_raw(s) is None)
        if missing:
            out.append('%s null: the reason cites Sources that do not exist (%s)' % (f, ', '.join(missing)))
    if not (cond.harness and cond.harness_source and source_raw(cond.harness_source) is not None):
        out.append('no episode protocol: harness and an existing harness_source')
    if cond.n_samples is None or cond.selection_strategy is None:
        out.append('no episode count or selection strategy')
    return out


# ---- 1. the claims --------------------------------------------------------------------------------------------

def test_six_claims_across_three_cluster_benchmarks_and_twelve_robotics_claims_in_all():
    assert len(CLAIMS) >= 6 and len({c.benchmark.partition('@')[0] for c in CLAIMS}) >= 3
    assert {c.system for c in CLAIMS} >= set(DECODE)
    assert len(FAMILY_CLAIMS) >= 12
    assert sum(c.benchmark.partition('@')[0] == 'roboarena' for _, c in FAMILY_CLAIMS) >= 6     # P3-S8-T05's
    for rel, c in FAMILY_CLAIMS:
        assert rel.startswith('data/claims/%s/' % c.benchmark.partition('@')[0]), rel


# ---- 2. the verify: each field answered, or a stated reason it is null ----------------------------------------

@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_verify_simulator_build_and_embodiment_or_a_stated_reason(claim):
    assert claim.eval_conditions is not None
    assert problems(claim, conditions(claim.eval_conditions)) == []


# ---- 3. the decodes -------------------------------------------------------------------------------------------

def claim_of(system):
    [c] = [c for c in CLAIMS if c.system == system]
    return c


@pytest.mark.parametrize('system', sorted(DECODE))
def test_each_field_is_the_token_its_sources_give_or_a_sourced_null(system):
    bench, decode, _, _ = DECODE[system]
    claim = claim_of(system)
    assert claim.benchmark.partition('@')[0] == bench
    cond = conditions(claim.eval_conditions)
    for f in FIELDS:
        token, quotes = decode[f]
        if token is None:
            assert getattr(cond, f) is None, f
            why = reason_for(claim.notes, f)
            for sid, _ in quotes:
                assert sid in why, '%s null: the reason does not cite %s' % (f, sid)
        else:
            assert token in getattr(cond, f), (f, getattr(cond, f))
        for sid, q in quotes:
            assert quote_found(q, extract(sid)), (f, sid, q)
    for sid, q in decode['protocol']:
        assert quote_found(q, extract(sid)), (sid, q)
    assert cond.harness_source in {sid for sid, _ in decode['protocol']}


def test_the_undecodable_builds_are_findings_not_gaps():
    """Two builds cannot be decoded, and the reason is itself in the Sources: the 2025 BEHAVIOR organisers ran
    an unpublished main-branch commit, and OpenVLA's LIBERO harness listed robosuite with no version until a commit
    three months after the paper (2024-09-05 -> 2024-12-04). SimplerEnv's build is decoded to its pin."""
    b = extract(B_RELEASES)
    assert quote_found('"published_at":"2025-09-12T23:38:25Z"', b)          # v3.7.1, before the deadline
    assert quote_found('"published_at":"2025-12-15T19:07:59Z"', b)          # v3.7.2, after the challenge
    c = extract(OV_COMMITS)
    assert quote_found('"date":"2024-09-05T03:06:55Z"},"message":"Add LIBERO sim eval script', c)
    assert quote_found('"date":"2024-12-04T23:21:37Z"},"message":"Pin robosuite==1.4.1', c)
    assert source(OV_REQS).quote_extract == 'imageio[ffmpeg] robosuite bddl easydict cloudpickle gym'
    assert 'db695066a93f774728f2ef477bdec7cf72028382' in source(SUBMODULE).url
    for system in ('rt-1-converged', 'octo-base'):
        assert conditions(claim_of(system).eval_conditions).simulator_version == \
            'SAPIEN 2.2.2 (ManiSkill2_real2sim cd45dd2)'


# ---- 4. what the claims are -----------------------------------------------------------------------------------

@pytest.mark.parametrize('system', sorted(DECODE))
def test_the_value_is_the_quoted_row_and_n_samples_the_protocols_product(system):
    _, _, (sid, row), factors = DECODE[system]
    claim = claim_of(system)
    assert claim.source == sid and quote_found(row, extract(sid))
    assert row.split()[-1] == ('%g' % claim.value if claim.value >= 1 else '%.4g' % claim.value) or \
        row.endswith(('%.3f' % claim.value, '%.4f' % claim.value)), (row, claim.value)
    n = 1
    for x in factors:
        n *= x
    assert conditions(claim.eval_conditions).n_samples == n
    m = Metric.model_validate(load('metrics', claim.metric))
    assert m.range.min <= claim.value <= m.range.max and m.optimum == 'max'
    assert System.model_validate(load('systems', claim.system)).system_type == 'rl-policy'
    assert llm_run.llm_run(claim.system) is False                       # it counts toward the non-LLM claims
    org = Organization.model_validate(load('organizations', claim.reported_by))
    assert 'evaluator' in org.roles


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_condition_completeness_and_the_unknowns_are_named(claim):
    b = benchmark(claim.benchmark.partition('@')[0])
    cond = conditions(claim.eval_conditions)
    c = comp.compute_for_claim(claim, comp.resolve_profile(b), cond)
    assert c.condition_completeness >= 0.6
    assert set(c.unknown_fields) == {f for f in FIELDS if getattr(cond, f) is None}


def test_one_protocol_one_key_two_embodiments_two_keys():
    """The BEHAVIOR pair and the LIBERO pair each ran under one protocol, so each shares a key, and the null
    simulator_version is the unknown both carry (04 S8's middle state: plotted together with a banner). The two
    SimplerEnv claims differ in embodiment and task, so their keys differ and the view refuses to rank them."""
    def key(system):
        c = claim_of(system)
        r = comp.resolve_profile(benchmark(c.benchmark.partition('@')[0]))
        return comp.compute_for_claim(c, r, conditions(c.eval_conditions))
    for a, b in (('robot-learning-collective-behavior-2025', 'comet-behavior-2025'),
                 ('openvla-7b-finetuned-libero-spatial', 'octo-finetuned-libero-spatial')):
        ka, kb = key(a), key(b)
        assert ka.comparability_key == kb.comparability_key
        assert ka.unknown_fields == kb.unknown_fields == ('simulator_version',)
    g, w = key('rt-1-converged'), key('octo-base')
    assert g.comparability_key != w.comparability_key and g.key_unknown_count == w.key_unknown_count == 0
    assert conditions(claim_of('rt-1-converged').eval_conditions).hardware_platform != \
        conditions(claim_of('octo-base').eval_conditions).hardware_platform


# ---- 5. the failure cases -------------------------------------------------------------------------------------

def test_a_null_with_no_reason_is_caught_and_the_schema_accepts_it():
    claim = claim_of('openvla-7b-finetuned-libero-spatial')
    cond = conditions(claim.eval_conditions)
    bare = claim.model_copy(update={'notes': claim.notes.split('simulator_version null:')[0]})
    assert any('simulator_version is null with no stated reason' in p for p in problems(bare, cond))
    hardware = EvalConditions.model_validate({**cond.model_dump(exclude_none=True), 'hardware_platform': None})
    assert any('hardware_platform is null with no stated reason' in p for p in problems(claim, hardware))


def test_a_placeholder_in_place_of_a_null_is_caught():
    claim = claim_of('comet-behavior-2025')
    cond = conditions(claim.eval_conditions)
    for fake in ('unknown', 'N/A', '?', 'TBD'):
        disguised = EvalConditions.model_validate({**cond.model_dump(exclude_none=True), 'simulator_version': fake})
        assert any('placeholder' in p for p in problems(claim, disguised)), fake


def test_a_reason_that_cites_no_source_or_a_missing_one_is_caught():
    claim = claim_of('robot-learning-collective-behavior-2025')
    cond = conditions(claim.eval_conditions)
    head = claim.notes.split('simulator_version null:')[0]
    shrug = claim.model_copy(update={'notes': head + 'simulator_version null: the organisers never said which '
                                                     'build they used for the hidden instances, so nobody can know.'})
    assert any('cites no Source' in p for p in problems(shrug, cond))
    ghost = claim.model_copy(update={'notes': head + 'simulator_version null: the build is named nowhere in the '
                                                     'organisers\' pages or the tags of the repository '
                                                     '(src-behavior-made-up-page).'})
    assert any('do not exist' in p for p in problems(ghost, cond))
    terse = claim.model_copy(update={'notes': head + 'simulator_version null: not stated (%s).' % B_UPDATES})
    assert any('under %d words' % REASON_FLOOR in p for p in problems(terse, cond))


def test_conditions_without_an_episode_protocol_are_caught():
    claim = claim_of('octo-base')
    cond = conditions(claim.eval_conditions)
    bare = EvalConditions.model_validate({k: v for k, v in cond.model_dump(exclude_none=True).items()
                                          if k not in ('harness', 'harness_source', 'n_samples')})
    found = problems(claim, bare)
    assert any('no episode protocol' in p for p in found) and any('no episode count' in p for p in found)
    assert problems(claim, None) == ['names no EvalConditions']


# ---- 6. the Sources and the records' identity -----------------------------------------------------------------

@pytest.mark.parametrize('sid', sorted(NEW_SOURCES))
def test_every_new_source_is_marked_honestly(sid):
    status, personal = NEW_SOURCES[sid]
    s = source(sid)
    assert s.contains_personal_data is personal
    assert s.accessed.isoformat() == '2026-11-24' and s.drafted_by == 'agent (P3-S8-T06)'
    if s.doi:
        assert s.archive_status == status == 'not-required' and s.doi.startswith('10.48550/arXiv.')
    elif personal:
        assert s.archive_status == status == 'withheld' and s.failure_reason and not s.archive_url
    elif s.archive_status == 'ok':                   # the archiver has captured it since
        assert status == 'pending' and s.archive_url and s.archive_captured
    else:
        assert s.archive_status == status == 'pending' and s.archive_url is None
    assert not EMAIL.search(s.quote_extract or '')
    assert '[view email' not in (s.quote_extract or '')


def _content_id(prefix, d):
    return '%s-%s' % (prefix, hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8'))
                      .hexdigest()[:12])


@pytest.mark.parametrize('claim', CLAIMS, ids=lambda c: c.id)
def test_ids_are_content_derived(claim):
    key = {'benchmark': claim.benchmark, 'system': claim.system, 'metric': claim.metric, 'subset': claim.subset,
           'value': claim.value, 'source': claim.source, 'date_reported': claim.date_reported.isoformat()}
    assert claim.id == _content_id('claim', key)
    cond = conditions(claim.eval_conditions)
    material = comp.resolve_profile(benchmark(claim.benchmark.partition('@')[0])).material
    assert cond.id == _content_id('cond', {f: comp.canonicalise(cond.value(f)) for f in material})
