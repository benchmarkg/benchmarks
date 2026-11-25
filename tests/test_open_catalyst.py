"""Open Catalyst's three generations, their hidden test splits and OCx24's wet-lab ground truth (P3-S6-T02;
04-data-model.md S6, S7; 01-landscape-and-positioning.md S10).

The verify: "bench validate --tier all, plus a test asserting each OC benchmark admits held-out-server and that OCx24
carries an assay_protocol ref". The done-when: "OCx24's wet-lab ground truth is distinguishable in the schema from the
computational splits." Each check below is a function that returns what is wrong. It runs on the committed records,
which must pass, and on a copy broken the way the verification names, which must fail, so the test also fails if a
check stops catching its case.

  1. Three generations, three BenchmarkVersions: oc20, oc22 and ocx24, each a breaking edition, none superseding
     another. A subset belongs to the version its id names (oc20#oc22-test-id is OC22's): the Subset model has no
     version field, so this test holds the tie, as tests/test_dcase_open_asr.py does for DCASE's years.
  2. Held-out-server is a level a claim on a generation can hold when the benchmark's submission process includes
     it and the generation has a hidden test subset (oc20#<version>-test...) whose evidence, its own or its parent's,
     quotes the server that scores it: a leaderboard-page Source, the quote found in that Source's extract. OC20 and
     OC22 admit it. OCx24 does not, and the sources say why: it has no test split, server or leaderboard, and the
     summaries of its measurements are public. The plan's premise that every generation admits held-out-server did
     not survive them, so for OCx24 the test asserts the recorded absence and its quoted reason, not the premise
     (the entry's header comment and review_checks).
  3. The assay_protocol ref. The schema has no version- or subset-level field for one: BenchmarkVersion and Subset
     are closed models, and assay_protocol is an EvalConditions field, set per claim. This task leaves schema/ alone,
     so the ref OCx24 carries is its version's protocol Source, src-arxiv-2411-11783-v1, cited among the version's
     sources and quoted for its testing protocol on each OCx24 reaction subset. A tripwire fails the day the schema
     gains a version-level field, so the ref moves into it.
  4. Distinguishable: no OC20 or OC22 subset quotes an OCx24 Source, no OCx24 subset quotes a server, the entry's
     data_provenance carries experimental-measurement (on the protocol's quote) beside simulation-generated, and an
     OCx24 claim never shares a comparability key with a computational one.
  5. Metrics and anchors: the nine Metric records load and the entry references them; every OC20 and OC22 metric has
     one primary ceiling at its own bound, and the OC22 floors sit on the worse side of it, on a subset of their own
     version. OCx24 has no anchors (data/baselines/oc20.yaml's header says why).
"""
import copy
import os
import re
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import FLOOR_KINDS, Baseline, BaselineFile  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.entities import BenchmarkVersion, Subset  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402

BID = 'oc20'
ENTRY = os.path.join(ROOT, 'data', 'benchmarks', 'chemistry-materials', BID + '.yaml')
BASELINES = os.path.join(ROOT, 'data', 'baselines', BID + '.yaml')
GENERATIONS = ('oc20', 'oc22', 'ocx24')
COMPUTATIONAL = ('oc20', 'oc22')
CHILD = re.compile(r'^oc20#(?P<version>oc20|oc22|ocx24)-(?P<rest>[a-z0-9][a-z0-9-]*)$')
TASK_METRICS = ('oc-s2ef-energy-mae', 'oc-s2ef-force-mae', 'oc-s2ef-force-cosine', 'oc-s2ef-efwt',
                'oc-is2re-energy-mae', 'oc-is2re-ewt', 'oc-is2rs-adwt', 'oc-is2rs-afbt')
METRICS = TASK_METRICS + ('r-squared',)

PROTOCOL = 'src-arxiv-2411-11783-v1'
# The paper's section 2.2, one sentence per reaction: what the laboratory measured, and how.
PROTOCOL_QUOTES = {
    'oc20#ocx24-her': 'The testing process began with the electrolyzer operating at 50 mA/cm2 for 9 minutes to '
                      'evaluate HER activity',
    'oc20#ocx24-co2rr': 'the CO2RR was carried out at current densities of 50, 100, 150, 200, and 300 mA/cm2 for 9 '
                        'minutes each',
}
PUBLIC = ('src-github-fairchem-docs-ocx24-d733f48', 'Summaries of this data are all publicly available')
SERVER = 'leaderboard-page'


def source_doc(sid: str) -> dict | None:
    for d, _, files in os.walk(os.path.join(ROOT, 'data', 'sources')):
        if sid + '.yaml' in files:
            return read_yaml(os.path.join(d, sid + '.yaml'))
    return None


def quoted(ev) -> bool:
    s = source_doc(ev.source)
    return s is not None and bool(ev.quote) and quote_found(ev.quote, s.get('quote_extract') or '')


def flat(text: str) -> str:
    return ' '.join(text.split())


def version_of(subset_id: str) -> str | None:
    m = CHILD.match(subset_id)
    return m.group('version') if m else None


def chain(b: Benchmark, s: Subset) -> list:
    """The subset's evidence and its ancestors': a subsplit inherits the server its test set quotes."""
    by_id = {x.id: x for x in b.subsets}
    out = []
    while s is not None:
        out += list(s.evidence)
        s = by_id.get(s.parent) if s.parent else None
    return out


def held_out_subsets(b: Benchmark, version: str) -> list[Subset]:
    return [s for s in b.subsets if s.id.startswith('oc20#%s-test' % version)]


@pytest.fixture(scope='module')
def entry() -> Benchmark:
    return load_benchmark(ENTRY)


@pytest.fixture(scope='module')
def baselines() -> list[dict]:
    return read_yaml(BASELINES)


# ---- the checks -----------------------------------------------------------------------------------------------

def version_problems(b: Benchmark) -> list[str]:
    """Three breaking editions, none superseding another, and every subset tied by its id to one of them."""
    out = []
    tags = [v.version for v in b.versions]
    if tags != list(GENERATIONS):
        out.append('versions are %s, not %s' % (tags, list(GENERATIONS)))
    for v in b.versions:
        if v.version_kind != 'edition' or not v.breaking:
            out.append('%s is not a breaking edition' % v.version)
        if v.supersedes_version or v.superseded_by:
            out.append('%s supersedes or is superseded; the generations run side by side' % v.version)
        if not v.sources:
            out.append('%s cites no source' % v.version)
    out += ['subset %s names no version' % s.id for s in b.subsets if version_of(s.id) is None]
    out += ['subset %s has a parent of another version' % s.id for s in b.subsets
            if s.parent and version_of(s.parent) != version_of(s.id)]
    for g in GENERATIONS:
        if not any(version_of(s.id) == g for s in b.subsets):
            out.append('%s has no subset' % g)
    return out


def held_out_problems(b: Benchmark, version: str) -> list[str]:
    """Why a claim on this generation could not hold held-out-server: the benchmark takes no server submissions, the
    generation has no hidden test subset, or a test subset names no server that scores it."""
    out = []
    procs = b.governance.submission_process
    procs = procs if isinstance(procs, list) else [procs]
    if 'held-out-server' not in procs:
        out.append('%s: governance.submission_process lacks held-out-server' % version)
    tests = held_out_subsets(b, version)
    if not tests:
        return out + ['%s: no hidden test subset' % version]
    for s in tests:
        evidence = chain(b, s)
        out += ['%s: %s quotes %s, which its extract does not hold: %r' % (version, s.id, ev.source, ev.quote)
                for ev in evidence if not quoted(ev)]
        if not any((source_doc(ev.source) or {}).get('type') == SERVER and quoted(ev) for ev in evidence):
            out.append('%s: %s names no server that scores it' % (version, s.id))
    return out


def assay_protocol_problems(b: Benchmark) -> list[str]:
    """OCx24's assay_protocol ref, held where the schema allows: its version cites the protocol Source, and each of
    its reaction subsets quotes that Source's testing protocol."""
    versions = {v.version: v for v in b.versions}
    if 'ocx24' not in versions:
        return ['no ocx24 version']
    out = []
    if PROTOCOL not in versions['ocx24'].sources:
        out.append('the ocx24 version does not cite its protocol Source %s' % PROTOCOL)
    by_id = {s.id: s for s in b.subsets}
    for sid, protocol in PROTOCOL_QUOTES.items():
        s = by_id.get(sid)
        if s is None:
            out.append('%s is missing' % sid)
            continue
        hits = [ev for ev in s.evidence if ev.source == PROTOCOL and ev.quote and flat(ev.quote) == protocol]
        if not hits:
            out.append('%s does not quote the testing protocol from %s' % (sid, PROTOCOL))
        elif not all(quoted(ev) for ev in hits):
            out.append('%s: the protocol quote is not in %s\'s extract' % (sid, PROTOCOL))
    for s in b.subsets:
        if version_of(s.id) == 'ocx24' and not any(ev.source == PROTOCOL for ev in chain(b, s)):
            out.append('%s carries no protocol evidence, its own or its parent\'s' % s.id)
    return out


def wet_lab_problems(b: Benchmark) -> list[str]:
    """OCx24's measured ground truth kept apart from the DFT splits."""
    out = []
    ocx24 = set(next(v for v in b.versions if v.version == 'ocx24').sources)
    for s in b.subsets:
        v = version_of(s.id)
        if v in COMPUTATIONAL and any(ev.source in ocx24 for ev in s.evidence):
            out.append('%s, a computational split, quotes an OCx24 Source' % s.id)
        if v == 'ocx24' and any((source_doc(ev.source) or {}).get('type') == SERVER for ev in chain(b, s)):
            out.append('%s, a measured target, quotes a scoring server' % s.id)
    provenance = set(b.data.data_provenance)
    for term in ('simulation-generated', 'experimental-measurement'):
        if term not in provenance:
            out.append('data.data_provenance lacks %s' % term)
    basis = (b.data.model_extra or {}).get('data_provenance_basis') or {}
    if basis.get('source') != PROTOCOL or not basis.get('quote') or \
            not quote_found(basis['quote'], (source_doc(PROTOCOL) or {}).get('quote_extract') or ''):
        out.append('data_provenance_basis does not quote the protocol for experimental-measurement')
    return out


def baseline_problems(raw: list[dict], b: Benchmark) -> list[str]:
    """Each OC20 and OC22 metric: one primary, a theoretical-maximum ceiling at the metric's own bound; every floor on a
    subset of its own version and on the worse side of the ceiling; every quote in its Source's extract."""
    out = []
    records = []
    for d in raw:
        try:
            records.append(Baseline.model_validate(d))
        except ValidationError as e:
            out.append('%s: %s' % (d.get('id'), e.errors()[0]['msg']))
    subsets = {s.id for s in b.subsets}
    for x in records:
        bench, _, version = x.benchmark_version.partition('@')
        if bench != BID or version not in COMPUTATIONAL:
            out.append('%s is on %s; only OC20 and OC22 have anchors' % (x.id, x.benchmark_version))
        if x.metric not in TASK_METRICS:
            out.append('%s is on %s, not a task metric' % (x.id, x.metric))
        if x.subset is not None and (x.subset not in subsets or version_of(x.subset) != version):
            out.append('%s sits on %s, not a subset of %s' % (x.id, x.subset, x.benchmark_version))
        if x.source and source_doc(x.source) is None:
            out.append('%s cites %s, which is not under data/sources/' % (x.id, x.source))
        out += ['%s: quote not in %s: %r' % (x.id, ev.source, ev.quote) for ev in x.evidence if not quoted(ev)]
        if not x.evidence:
            out.append('%s carries no quoted evidence' % x.id)
    for version in COMPUTATIONAL:
        for mid in TASK_METRICS:
            m = Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))
            bound = m.range.min if m.optimum == 'min' else m.range.max
            mine = [x for x in records if x.benchmark_version == '%s@%s' % (BID, version) and x.metric == mid]
            primary = [x for x in mine if x.is_primary]
            if len(primary) != 1:
                out.append('%s@%s / %s: %d primary baselines' % (BID, version, mid, len(primary)))
                continue
            ceiling = primary[0]
            if ceiling.kind != 'theoretical-maximum' or ceiling.value != bound:
                out.append('%s: the primary is not the bound %s as a theoretical maximum' % (ceiling.id, bound))
            for f in (x for x in mine if x.kind in FLOOR_KINDS):
                worse = f.value > ceiling.value if m.optimum == 'min' else f.value < ceiling.value
                if f.value is None or not worse:
                    out.append('%s is not on the worse side of its ceiling' % f.id)
    return out


# ---- 1. three generations ----------------------------------------------------------------------------------------

def test_the_three_generations_are_breaking_editions_and_own_their_subsets(entry):
    assert version_problems(entry) == []
    basis = read_yaml(ENTRY)['versions_basis']
    assert quote_found(basis['quote'], source_doc(basis['source'])['quote_extract'])
    assert {v.version: v.released.isoformat() for v in entry.versions} == {
        'oc20': '2020-10-20', 'oc22': '2022-06-17', 'ocx24': '2024-11-18'}


def test_a_fourth_version_or_a_superseding_one_fails(entry):
    extra = BenchmarkVersion(version='oc25', version_kind='edition', breaking=True, sources=[PROTOCOL])
    chained = [entry.versions[0].model_copy(update={'superseded_by': 'oc22'})] + list(entry.versions[1:])
    assert version_problems(entry.model_copy(update={'versions': list(entry.versions) + [extra]})) == \
        ["versions are ['oc20', 'oc22', 'ocx24', 'oc25'], not ['oc20', 'oc22', 'ocx24']"]
    assert version_problems(entry.model_copy(update={'versions': chained})) == \
        ['oc20 supersedes or is superseded; the generations run side by side']


def test_a_subset_that_names_no_version_fails(entry):
    stray = Subset(id='oc20#test-id', label='a split of no generation')
    assert version_problems(entry.model_copy(update={'subsets': list(entry.subsets) + [stray]})) == \
        ['subset oc20#test-id names no version']


# ---- 2. held-out-server --------------------------------------------------------------------------------------------

@pytest.mark.parametrize('version', COMPUTATIONAL)
def test_verify_each_computational_generation_admits_held_out_server(entry, version):
    assert held_out_problems(entry, version) == []
    assert held_out_subsets(entry, version)


def test_the_oc20_test_set_has_its_four_subsplits_and_three_challenge_sets(entry):
    kids = sorted(s.id for s in entry.subsets if s.parent == 'oc20#oc20-test')
    assert kids == ['oc20#oc20-test-id', 'oc20#oc20-test-ood-ads', 'oc20#oc20-test-ood-both', 'oc20#oc20-test-ood-cat']
    assert {'oc20#oc20-test-challenge-%d' % y for y in (2021, 2022, 2023)} <= {s.id for s in entry.subsets}
    assert sorted(s.id for s in entry.subsets if s.parent == 'oc20#oc22-test') == \
        ['oc20#oc22-test-id', 'oc20#oc22-test-ood']


def test_oc20s_labels_are_quoted_as_withheld_and_oc22s_are_an_open_check(entry):
    """OC20's paper says its test labels are not released. No source read says so of OC22, whose held-out-server rests
    on its evaluation server; the entry leaves that to a reviewer rather than asserting it."""
    oc20 = next(s for s in entry.subsets if s.id == 'oc20#oc20-test')
    assert any(ev.quote == 'Ground truth test data is not publicly released' and quoted(ev) for ev in oc20.evidence)
    assert any('OC22' in c.check and 'withheld' in c.check for c in entry.curation.review_checks)


def test_verify_ocx24_does_not_admit_held_out_server_and_the_entry_says_why(entry):
    """The premise that failed: OCx24 has no hidden split. The absence is recorded, not an omission: each of its
    reaction subsets quotes that the measurement summaries are public."""
    assert held_out_problems(entry, 'ocx24') == ['ocx24: no hidden test subset']
    for sid in PROTOCOL_QUOTES:
        s = next(x for x in entry.subsets if x.id == sid)
        assert any((ev.source, flat(ev.quote)) == PUBLIC and quoted(ev) for ev in s.evidence), sid


def test_without_server_submissions_no_generation_admits_held_out_server(entry):
    gov = entry.governance.model_copy(update={'submission_process': ['maintainer-run']})
    broken = entry.model_copy(update={'governance': gov})
    for version in COMPUTATIONAL:
        assert '%s: governance.submission_process lacks held-out-server' % version in held_out_problems(broken, version)


def test_an_oc22_test_set_without_its_server_fails(entry):
    subsets = []
    for s in entry.subsets:
        if s.id == 'oc20#oc22-test':
            s = s.model_copy(update={'evidence': [ev for ev in s.evidence if source_doc(ev.source)['type'] != SERVER]})
        subsets.append(s)
    assert held_out_problems(entry.model_copy(update={'subsets': subsets}), 'oc22') == [
        'oc22: oc20#oc22-test names no server that scores it',
        'oc22: oc20#oc22-test-id names no server that scores it',
        'oc22: oc20#oc22-test-ood names no server that scores it']


def test_a_generation_stripped_of_its_test_subsets_fails(entry):
    kept = [s for s in entry.subsets if not s.id.startswith('oc20#oc20-test')]
    assert held_out_problems(entry.model_copy(update={'subsets': kept}), 'oc20') == ['oc20: no hidden test subset']


def test_a_server_quote_its_source_does_not_hold_fails(entry):
    subsets = []
    for s in entry.subsets:
        if s.id == 'oc20#oc22-test':
            ev = [e.model_copy(update={'quote': e.quote + ' and test labels are public'})
                  if source_doc(e.source)['type'] == SERVER else e for e in s.evidence]
            s = s.model_copy(update={'evidence': ev})
        subsets.append(s)
    problems = held_out_problems(entry.model_copy(update={'subsets': subsets}), 'oc22')
    assert any('which its extract does not hold' in p for p in problems)
    assert 'oc22: oc20#oc22-test names no server that scores it' in problems


# ---- 3. OCx24's assay_protocol ref ---------------------------------------------------------------------------------

def test_verify_ocx24_carries_its_assay_protocol_ref(entry):
    assert assay_protocol_problems(entry) == []
    assert source_doc(PROTOCOL)['doi'] == '10.48550/arXiv.2411.11783'


def test_the_schema_has_no_version_or_subset_level_assay_protocol():
    """The gap this task records instead of changing schema/. If this fails, the schema has gained the field: move
    OCx24's ref into it and make assay_protocol_problems read it there."""
    assert 'assay_protocol' not in BenchmarkVersion.model_fields
    assert 'assay_protocol' not in Subset.model_fields
    with pytest.raises(ValidationError, match='assay_protocol'):
        BenchmarkVersion.model_validate({'version': 'ocx24', 'assay_protocol': PROTOCOL})
    assert 'assay_protocol' in EvalConditions.model_fields          # where it lives: on each claim's conditions


def test_an_ocx24_version_without_its_protocol_source_fails(entry):
    versions = [v.model_copy(update={'sources': [s for s in v.sources if s != PROTOCOL]})
                if v.version == 'ocx24' else v for v in entry.versions]
    assert assay_protocol_problems(entry.model_copy(update={'versions': versions})) == \
        ['the ocx24 version does not cite its protocol Source %s' % PROTOCOL]


def test_a_reaction_subset_without_the_protocol_quote_fails(entry):
    subsets = [s.model_copy(update={'evidence': [ev for ev in s.evidence if ev.source != PROTOCOL]})
               if s.id == 'oc20#ocx24-her' else s for s in entry.subsets]
    assert assay_protocol_problems(entry.model_copy(update={'subsets': subsets})) == [
        'oc20#ocx24-her does not quote the testing protocol from %s' % PROTOCOL,
        'oc20#ocx24-her carries no protocol evidence, its own or its parent\'s']


# ---- 4. the wet-lab ground truth is distinguishable --------------------------------------------------------------

def test_the_wet_lab_targets_are_kept_apart_from_the_dft_splits(entry):
    assert wet_lab_problems(entry) == []
    assert entry.ground_truth_source == 'simulation'           # one value per benchmark: OC20's and OC22's (review check)


def test_a_computational_split_quoting_the_protocol_fails(entry):
    from schema.system import Evidence
    leak = Evidence(source=PROTOCOL, quote=PROTOCOL_QUOTES['oc20#ocx24-her'])
    subsets = [s.model_copy(update={'evidence': list(s.evidence) + [leak]}) if s.id == 'oc20#oc22-test-id' else s
               for s in entry.subsets]
    assert wet_lab_problems(entry.model_copy(update={'subsets': subsets})) == \
        ['oc20#oc22-test-id, a computational split, quotes an OCx24 Source']


def test_dropping_experimental_measurement_fails(entry):
    data = entry.data.model_copy(update={'data_provenance': ['simulation-generated']})
    assert wet_lab_problems(entry.model_copy(update={'data': data})) == \
        ['data.data_provenance lacks experimental-measurement']


def test_an_ocx24_claim_never_shares_a_key_with_a_computational_one(entry):
    r = comp.resolve_profile(entry)
    cond = EvalConditions(id='cond-0123456789ab', subset_used='leave one composition out', training_data_policy='open')
    ocx24 = comp.compute(r, cond, 'oc20@ocx24', 'r-squared', 'oc20#ocx24-her-loco')
    oc22 = comp.compute(r, cond, 'oc20@oc22', 'r-squared', 'oc20#ocx24-her-loco')
    assert ocx24.comparability_key != oc22.comparability_key


# ---- 5. metrics and anchors -----------------------------------------------------------------------------------------

@pytest.mark.parametrize('mid', METRICS)
def test_each_metric_loads_is_referenced_and_can_carry_headroom(entry, mid):
    m = Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))
    assert m.id == mid and mid in entry.metrics and m.range is not None
    assert m.headroom_null_reason() is None
    for sid in m.sources:
        assert source_doc(sid) is not None, sid


def test_ocx24_subsets_score_r_squared(entry):
    assert {s.metric_override for s in entry.subsets if version_of(s.id) == 'ocx24'} == {'r-squared'}
    assert all(s.metric_override is None for s in entry.subsets if version_of(s.id) in COMPUTATIONAL)


def test_verify_the_anchors(baselines, entry):
    BaselineFile.model_validate(baselines)
    assert baseline_problems(baselines, entry) == []
    floors = {b['id']: b['value'] for b in baselines if b['kind'] in FLOOR_KINDS}
    assert floors == {
        'base-oc20-oc22-s2ef-energy-mae-median-id': 163.424, 'base-oc20-oc22-s2ef-energy-mae-median-ood': 160.455,
        'base-oc20-oc22-is2re-energy-mae-median-id': 176.256, 'base-oc20-oc22-is2re-energy-mae-median-ood': 171.854,
        'base-oc20-oc22-is2rs-adwt-is-id': 43.39, 'base-oc20-oc22-is2rs-adwt-is-ood': 45.26}


@pytest.mark.parametrize('mid', ('oc-s2ef-energy-mae', 'oc-is2re-energy-mae', 'oc-is2rs-adwt'))
def test_headroom_runs_between_the_oc22_floor_and_ceiling(baselines, mid):
    m = Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))
    mine = [b for b in baselines if b['benchmark_version'] == 'oc20@oc22' and b['metric'] == mid]
    [ceiling] = [b['value'] for b in mine if b.get('is_primary')]
    for floor in (b['value'] for b in mine if b['kind'] in FLOOR_KINDS):
        assert m.headroom_consumed(sota=ceiling, baseline=floor, ceiling=ceiling) == pytest.approx(1.0)
        assert m.headroom_consumed(sota=floor, baseline=floor, ceiling=ceiling) == pytest.approx(0.0)


def test_an_anchor_on_ocx24_or_on_another_versions_subset_fails(baselines, entry):
    raw = copy.deepcopy(baselines)
    floor = next(b for b in raw if b['id'] == 'base-oc20-oc22-is2rs-adwt-is-id')
    floor['subset'] = 'oc20#oc20-test-id'
    ceiling = next(b for b in raw if b['id'] == 'base-oc20-oc20-s2ef-energy-mae-zero')
    raw.append(dict(ceiling, id='base-oc20-ocx24-zero', benchmark_version='oc20@ocx24'))
    problems = baseline_problems(raw, entry)
    assert 'base-oc20-oc22-is2rs-adwt-is-id sits on oc20#oc20-test-id, not a subset of oc20@oc22' in problems
    assert 'base-oc20-ocx24-zero is on oc20@ocx24; only OC20 and OC22 have anchors' in problems


def test_a_floor_above_its_ceiling_or_a_missing_primary_fails(baselines, entry):
    raw = copy.deepcopy(baselines)
    next(b for b in raw if b['id'] == 'base-oc20-oc22-is2rs-adwt-is-ood')['value'] = 100.5
    raw = [b for b in raw if b['id'] != 'base-oc20-oc20-is2rs-afbt-hundred']
    problems = baseline_problems(raw, entry)
    assert 'base-oc20-oc22-is2rs-adwt-is-ood is not on the worse side of its ceiling' in problems
    assert 'oc20@oc20 / oc-is2rs-afbt: 0 primary baselines' in problems


def test_an_anchor_quote_not_in_its_source_fails(baselines, entry):
    raw = copy.deepcopy(baselines)
    next(b for b in raw if b['id'] == 'base-oc20-oc22-is2re-energy-mae-median-id')['evidence'][0]['quote'] = \
        'Median Baseline 1.000'
    assert any(p.startswith('base-oc20-oc22-is2re-energy-mae-median-id: quote not in') for p in
               baseline_problems(raw, entry))
