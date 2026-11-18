"""Tests for the gap matrix in tools/build/gaps.py and scripts/check_gap_claims.py (P1-S14-T08; 12 S5.1-5.4,
02 S4.3, 14 Phase 4 "The Gap Finder ships restricted, not ungated").

The verify: `bench gaps --grid coarse --reviewed-only --format json > build/derived/gaps.json && python
scripts/check_gap_claims.py`. Done when "Every published cell carries all four factors, its capability_groups
version, and no unreviewed family appears." Each factor is reproduced by hand on a synthetic tree; one synthetic
family is made claimable (signed, surveyed, triaged, reviewed entries) so the checker is seen to accept a claim
from the coarse grid with its survey notes and to refuse one from the fine grid or an unreviewed family; and the
corpus as it is, where no family is signed, asserts nothing.
"""
import datetime as dt
import json
import os
import shutil
import sys

import pytest
import yaml
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_gap_claims as C  # noqa: E402
from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps as G  # noqa: E402
from tools.cli import app  # noqa: E402

AS_OF = dt.date(2026, 11, 18)
ROWS, COLS = G.axes(ROOT)
GROUPS = [g['id'] for g in COLS['groups']]
MEMBERS = {g['id']: g['members'] for g in COLS['groups']}
SUBS = {}
for _t in yaml.safe_load(open(os.path.join(ROOT, G.DOMAINS), encoding='utf-8'))['terms']:
    if _t.get('parent') and _t.get('status') != 'retired':
        SUBS.setdefault(_t['parent'], []).append(_t['id'])
FAM = 'engineering-design'               # the claimable family: any would do, this one has the fewest subdomains
GROUP, OTHER = GROUPS[0], GROUPS[1]      # the claimed cell's group, and what the family's own entries measure
T_GROUP, T_OTHER = MEMBERS[GROUP][0], MEMBERS[OTHER][0]
NOT_ANY = [g for g in GROUPS if g not in (GROUP, OTHER)][0]


@pytest.fixture
def tree(tmp_path):
    for rel in (G.DOMAINS, G.CAPABILITIES, G.GROUPS, G.EXPECTATIONS):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    return tmp_path


def entry(root, ident, family, capability, secondary=(), status='ai-drafted-unverified', **fields):
    d = root / 'data' / 'benchmarks' / family
    d.mkdir(parents=True, exist_ok=True)
    rec = {'id': ident, 'domain': {'primary': SUBS[family][0], 'secondary': [SUBS[f][0] for f in secondary]},
           'capability': list(capability), 'curation': {'verification_status': status}}
    if 'last_verified' in fields:
        rec['curation']['last_verified'] = fields.pop('last_verified')
    rec.update(fields)
    (d / (ident + '.yaml')).write_text(yaml.safe_dump(rec, sort_keys=False), encoding='utf-8')


def set_term(root, ident, **fields):
    path = root / G.DOMAINS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    next(t for t in doc['terms'] if t['id'] == ident).update(fields)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')


def sign(root, family, value='domain-expert'):
    set_term(root, family, reviewer_signoff=value, reviewer='a domain reviewer', signed_on=dt.date(2026, 11, 1))


def expect(root, family, n):
    path = root / G.EXPECTATIONS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    row = next(r for r in doc['expectations'] if r['family'] == family)
    row.clear()
    row.update(family=family, tier1_expectation=n, sized=True, denominator_source='fixture')
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')


def note(root, sub, capabilities=None, accepted_by='a domain reviewer'):
    family, stem = sub.split('/')
    d = root / 'data' / 'surveys' / family
    d.mkdir(parents=True, exist_ok=True)
    path = d / (stem + '.yaml')
    path.write_text(yaml.safe_dump({
        'survey': {'family': family, 'subdomain': sub, 'conducted_on': dt.date(2026, 11, 1),
                   'method': 'registry and arXiv searches for the subdomain',
                   'scope': {'capabilities': capabilities or MEMBERS[GROUP]}, 'accepted_by': accepted_by},
        'finding': {'decision': 'surveyed-and-empty', 'note': 'Nothing found in %s.' % sub}}, sort_keys=False),
        encoding='utf-8')
    return path


def triage(root, cells, accepted_by='a curator'):
    path = root / CS.NOT_APPLICABLE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({'version': '0.1.0', 'updated': dt.date(2026, 11, 1), 'accepted_by': accepted_by,
                                    'cells': [{'family': f, 'group': g, 'verdict': v, 'rationale': 'A fixture.',
                                               'declared_by': 'fixture', 'declared_on': dt.date(2026, 11, 1)}
                                              for f, g, v in cells]}, sort_keys=False), encoding='utf-8')


def reviewed_pair(root, status='primary-source-verified', released=AS_OF - dt.timedelta(days=100)):
    for i in (1, 2):
        entry(root, 'ed%d' % i, FAM, [T_OTHER], status=status, last_verified=AS_OF - dt.timedelta(days=30),
              released=released)


def claimable(root):
    """FAM x GROUP meets every condition of a claim: FAM signed by a domain expert, its two entries reviewed and
    verified (curation confidence 1.0), every subdomain surveyed empty for GROUP's terms by an accepted note, the
    cell triaged applicable in an accepted triage, and GROUP measured in another family."""
    sign(root, FAM)
    expect(root, FAM, 2)
    reviewed_pair(root)
    entry(root, 'elsewhere', 'physics', [T_GROUP], released=AS_OF - dt.timedelta(days=50))
    for sub in SUBS[FAM]:
        note(root, sub)
    triage(root, [(FAM, GROUP, 'applicable')])


def emit(root, **kw):
    return G.emit(root=str(root), as_of=AS_OF, **kw)


def cell(doc, family, group):
    return next(c for c in doc['matrix'] if c['family'] == family and c['group'] == group)


def write(root, doc):
    path = root / 'build' / 'derived' / 'gaps.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding='utf-8')
    return path


def check(root, doc):
    return C.check(str(root), str(write(root, doc)))[0]


# ---- the matrix: every cell, four factors, the version -------------------------------------------------------

def test_every_coarse_cell_carries_the_four_factors_and_the_groups_version(tree):
    entry(tree, 'b1', 'physics', [T_GROUP])
    doc = emit(tree)
    assert len(doc['matrix']) == len(ROWS['families']) * len(COLS['groups']) == 247
    assert len({(c['family'], c['group']) for c in doc['matrix']}) == 247
    for c in doc['matrix']:
        assert list(c['factors']) == list(G.FACTORS)
        assert c['capability_groups_version'] == COLS['version'] == doc['axes']['columns']['version']
    assert doc['formula'] and doc['parameters']['min_confidence'] == G.MIN_CONFIDENCE


def test_reviewed_only_narrows_the_coverage_cells_and_the_claims_never_the_refusals(tree):
    entry(tree, 'b1', 'physics', [T_GROUP])
    doc = emit(tree, reviewed_only=True)
    assert doc['cells'] == [] and doc['claims'] == []
    assert len(doc['matrix']) == 247 and {c['gap_claim'] for c in doc['matrix']} == {G.REFUSED}


def test_an_unsigned_family_reads_insufficient_in_every_cell_its_factors_beside_it(tree):
    entry(tree, 'b1', 'physics', [T_GROUP], released=AS_OF)
    for c in emit(tree)['matrix']:
        assert c['gap_claim'] == G.REFUSED and c['gap_claim_refusal'].startswith(G.INSUFFICIENT)
        assert c['withheld'][0] == 'unreviewed-family'
        assert c['factors']['curation_confidence'] is not None and c['factors']['normalised_density'] is not None


# ---- density (12 S5.2) ---------------------------------------------------------------------------------------

def test_density_weighs_primary_1_secondary_and_subset_half_once_per_benchmark(tree):
    entry(tree, 'p', 'physics', [T_GROUP, MEMBERS[GROUP][1]])                      # two terms, one group: once
    entry(tree, 's', 'earth-climate', [T_GROUP], secondary=['physics'])
    entry(tree, 'u', 'chemistry-materials', [T_OTHER], subsets=[{
        'id': 'u#x', 'label': 'x', 'domain_override': {'primary': SUBS['physics'][1]}, 'capability_override': [T_GROUP]}])
    entry(tree, 'v', 'vision', [T_GROUP], subsets=[{'id': 'v#y', 'label': 'y',
                                                    'domain_override': {'primary': SUBS['physics'][0]}}])  # inherits
    doc = emit(tree)
    c = cell(doc, 'physics', GROUP)
    assert c['counts'] == {'primary': 1, 'secondary': 1, 'subset_derived': 2}
    assert (c['benchmarks'], c['secondary_benchmarks'], c['subset_benchmarks']) == (['p'], ['s'], ['u', 'v'])
    assert c['weighted_count'] == c['density'] == 1.0 + 0.5 + 0.5 + 0.5
    assert cell(doc, 'physics', OTHER)['counts']['subset_derived'] == 0                 # the override replaced it
    cov = next(x for x in doc['cells'] if x['family'] == 'physics' and x['group'] == GROUP)
    assert (cov['entries'], cov['secondary_entries']) == (1, 1)                        # the same as the coverage cell


@pytest.mark.parametrize('fields, weight, applied', [
    ({}, 1.0, []),
    ({'curation': {'verification_status': 'primary-source-verified'}}, 1.2, ['verified']),
    ({'curation': {'verification_status': 'maintainer-confirmed'}}, 1.2, ['verified']),
    ({'curation': {'verification_status': 'curator-reviewed'}}, 1.0, []),
    ({'curation': {'verification_status': 'machine-ingested'}}, 0.7, ['machine-ingested']),
    ({'liveness': {'repo_last_commit': dt.date(2026, 1, 5)}}, 1.1, ['active-in-18-months']),
    ({'liveness': {'repo_last_commit': dt.date(2024, 1, 5)}}, 1.0, []),             # one quiet signal is not evidence
    ({'liveness': {'repo_last_commit': dt.date(2024, 1, 5), 'leaderboard_last_updated': dt.date(2024, 3, 1)}},
     0.8, ['quiet-for-18-months']),
    ({'data': {'ceiling_anchor_type': 'expert-average'}}, 1.1, ['human-baseline']),
    ({'data': {'ceiling_anchor_type': 'theoretical-maximum'}}, 1.0, []),
    ({'baselines': [{'kind': 'human-crowd-average', 'value': 0.8}]}, 1.1, ['human-baseline']),
    ({'baselines': [{'kind': 'human-crowd-average', 'value': None}]}, 1.0, []),
    ({'released': dt.date(2023, 1, 1), 'released_source': 'src-x'}, 1.05, ['sourced-release-date']),
    ({'released': dt.date(2023, 1, 1)}, 1.0, []),
    ({'curation': {'verification_status': 'primary-source-verified'}, 'liveness': {'repo_last_commit': dt.date(2026, 6, 1)},
      'data': {'ceiling_anchor_type': 'crowd-best'}, 'released': dt.date(2023, 1, 1), 'released_source': 'src-x'},
     1.5, ['verified', 'active-in-18-months', 'human-baseline', 'sourced-release-date']),   # 1.5246, clamped
    ({'curation': {'verification_status': 'machine-ingested'},
      'liveness': {'repo_last_commit': dt.date(2023, 1, 1), 'leaderboard_last_updated': dt.date(2023, 1, 1)}},
     0.56, ['machine-ingested', 'quiet-for-18-months']),
])
def test_the_quality_weight_multiplies_12_s5_2_s_multipliers_and_clamps(fields, weight, applied):
    assert G.quality(dict(fields), None, AS_OF) == (weight, applied)


def test_a_snapshot_s_push_date_is_activity_as_liveness_reads_it():
    b = {'liveness': {'repo_last_commit': dt.date(2023, 1, 1)}}
    assert G.quality(b, {'github': {'pushed_at': '2026-10-04T17:08:44Z'}}, AS_OF)[1] == ['active-in-18-months']


def test_the_human_anchors_are_schema_baseline_s_human_kinds():
    from schema.baseline import CEILING_ANCHOR
    assert set(G.HUMAN_ANCHORS) == {v for k, v in CEILING_ANCHOR.items() if k.startswith('human-')}


def test_normalised_density_is_over_the_densest_cell_and_recorded(tree):
    entry(tree, 'a', 'physics', [T_GROUP])
    entry(tree, 'b', 'physics', [T_GROUP])
    entry(tree, 'c', 'earth-climate', [T_GROUP])
    doc = emit(tree)
    assert doc['parameters']['density_reference'] == {'value': 2.0, 'family': 'physics', 'group': GROUP}
    assert cell(doc, 'physics', GROUP)['factors']['normalised_density'] == 1.0
    assert cell(doc, 'earth-climate', GROUP)['factors']['normalised_density'] == 0.5
    assert cell(doc, 'earth-climate', OTHER)['factors']['normalised_density'] == 0.0


# ---- domain_activity, capability_salience, curation_confidence (12 S5.3) ---------------------------------------

def test_domain_activity_is_the_share_of_dated_entries_released_in_24_months(tree):
    entry(tree, 'new', 'physics', [T_GROUP], released=AS_OF - dt.timedelta(days=100))
    entry(tree, 'old', 'physics', [T_GROUP], released=dt.date(2020, 1, 1))
    entry(tree, 'edge', 'physics', [T_GROUP], released=dt.date(2024, 11, 18))      # 24 months to the day: outside
    entry(tree, 'undated', 'physics', [T_GROUP])
    doc = emit(tree)
    act = next(f for f in doc['families'] if f['id'] == 'physics')['domain_activity']
    assert act == {'value': round(1 / 3, 4), 'released_in_window': 1, 'dated_entries': 3, 'undated_entries': 1}
    assert cell(doc, 'physics', OTHER)['factors']['domain_activity'] == round(1 / 3, 4)
    assert cell(doc, 'earth-climate', GROUP)['factors']['domain_activity'] is None     # nothing dated: no factor
    assert cell(doc, 'earth-climate', GROUP)['gap_score'] is None


def test_capability_salience_is_how_often_other_families_measure_the_group(tree):
    entry(tree, 'p', 'physics', [T_GROUP])
    entry(tree, 'e1', 'earth-climate', [T_GROUP])
    entry(tree, 'e2', 'earth-climate', [T_OTHER])
    entry(tree, 'c', 'chemistry-materials', [T_OTHER])
    doc = emit(tree)
    assert cell(doc, 'physics', GROUP)['factors']['capability_salience'] == round(1 / 3, 4)    # e1 of e1, e2, c
    assert cell(doc, 'physics', GROUP)['capability_salience_inputs'] == {'carrying': 1, 'elsewhere': 3}
    assert cell(doc, 'earth-climate', GROUP)['factors']['capability_salience'] == 0.5         # p of p, c
    assert cell(doc, 'physics', NOT_ANY)['factors']['capability_salience'] == 0.0


def test_curation_confidence_reproduces_by_hand_for_two_families(tree):
    sign(tree, 'physics', 'generalist')                         # physics expects 20, sized
    for i in range(3):
        entry(tree, 'v%d' % i, 'physics', [T_GROUP], status='primary-source-verified',
              last_verified=AS_OF - dt.timedelta(days=30))
    entry(tree, 'r', 'physics', [T_GROUP], status='curator-reviewed', last_verified=AS_OF - dt.timedelta(days=10))
    entry(tree, 'x', 'physics', [T_GROUP], status='expert-reviewed', last_verified=AS_OF - dt.timedelta(days=181))
    for i in range(5):
        entry(tree, 'd%d' % i, 'physics', [T_GROUP], last_verified=AS_OF)                # drafts
    sign(tree, 'code', 'domain-expert')                         # code is unsized: its seed target, 16, stands in
    entry(tree, 'm1', 'code', [T_GROUP], status='machine-ingested')
    entry(tree, 'm2', 'code', [T_GROUP], status='machine-ingested')
    doc = emit(tree)
    fams = {f['id']: f['curation_confidence'] for f in doc['families']}
    # physics: 0.40 x 5/20 (five reviewed entries) + 0.30 x 3/10 (three verified inside 180 days) + 0.30 x 0.5
    assert fams['physics']['entry_coverage'] == {'value': 0.25, 'reviewed_entries': 5, 'entries': 10, 'expected': 20,
                                                 'unsized': False, 'denominator_source': 'recon:domains'}
    assert fams['physics']['verified_fraction'] == {'value': 0.3, 'verified_within_days': 3, 'entries': 10}
    assert fams['physics']['value'] == 0.34 and fams['physics']['badge'] == 'reviewed'
    # code: 0.40 x 0/16 (machine-ingested is not reviewed) + 0.30 x 0 + 0.30 x 1
    assert fams['code']['value'] == 0.3 and fams['code']['entry_coverage']['unsized'] is True
    assert fams['code']['entry_coverage']['expected'] == 16
    assert cell(doc, 'physics', OTHER)['factors']['curation_confidence'] == 0.34


def test_agent_drafts_never_raise_curation_confidence(tree):
    for i in range(25):
        entry(tree, 'd%d' % i, 'physics', [T_GROUP], last_verified=AS_OF)
    cc = next(f for f in emit(tree)['families'] if f['id'] == 'physics')['curation_confidence']
    assert cc['value'] == 0.0 and cc['entry_coverage']['reviewed_entries'] == 0 and cc['badge'] == 'unreviewed'


def test_gap_score_is_the_product_of_the_published_factors(tree):
    sign(tree, 'physics', 'generalist')
    entry(tree, 'v', 'physics', [T_GROUP], status='primary-source-verified', last_verified=AS_OF, released=AS_OF)
    entry(tree, 'e', 'earth-climate', [T_OTHER, T_GROUP], released=AS_OF)
    doc = emit(tree)
    scored = [c for c in doc['matrix'] if c['gap_score'] is not None]
    assert scored and any(c['gap_score'] > 0 for c in scored)
    for c in scored:
        f = c['factors']
        assert c['gap_score'] == round((1 - f['normalised_density']) * f['domain_activity'] * f['capability_salience']
                                       * f['curation_confidence'], 6)


def test_a_family_missing_from_the_expectations_is_an_error(tree):
    path = tree / G.EXPECTATIONS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    doc['expectations'] = [r for r in doc['expectations'] if r['family'] != 'physics']
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
    with pytest.raises(ValueError, match='no row for physics'):
        emit(tree)


@pytest.mark.parametrize('bad', [1.5, -0.1, True, 'high'])
def test_min_confidence_is_a_number_in_0_1(tree, bad):
    with pytest.raises(ValueError, match='min-confidence'):
        emit(tree, min_confidence=bad)


# ---- the claim gate (12 S5.4 category 1) ----------------------------------------------------------------------

def test_a_cell_meeting_every_condition_is_asserted_with_its_notes_and_a_claim_about_the_index(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    assert [(c['family'], c['group']) for c in doc['claims']] == [(FAM, GROUP)] and doc['claims_total'] == 1
    claim = doc['claims'][0]
    assert claim['grid'] == 'coarse' and claim['gap_claim'] == G.ASSERTED and claim['withheld'] == []
    assert claim['empty'] == G.CATEGORY_1 and claim['gap_claim_refusal'] is None
    assert claim['factors'] == {'normalised_density': 0.0, 'domain_activity': 1.0, 'capability_salience': 1.0,
                                'curation_confidence': 1.0} and claim['gap_score'] == 1.0
    assert sorted(n['note'] for n in claim['survey_notes']) == sorted(
        '%s/%s/%s.yaml' % (CS.SURVEYS, FAM, s.split('/')[1]) for s in SUBS[FAM])
    assert all(n['accepted_by'] and n['conducted_on'] == '2026-11-01' for n in claim['survey_notes'])
    assert 'not about the world' in claim['statement']
    assert claim['curation_confidence']['entry_coverage']['reviewed_entries'] == 2
    assert doc['review_backed'] == {'families': 1, 'of': 19, 'signed': [FAM]}
    others = [c for c in doc['matrix'] if (c['family'], c['group']) != (FAM, GROUP)]
    assert {c['gap_claim'] for c in others} == {G.REFUSED}
    assert cell(doc, FAM, NOT_ANY)['withheld'][:2] == ['untriaged', 'not-yet-surveyed']   # its notes cover GROUP only
    assert G.emit(root=str(tree), as_of=AS_OF)['claims'] == doc['claims']                 # with or without the flag


def _demote(t):
    reviewed_pair(t, status='ai-drafted-unverified')


def _stale(t):
    reviewed_pair(t, released=dt.date(2020, 1, 1))


@pytest.mark.parametrize('code, breaks', [
    ('unreviewed-family', lambda t: set_term(t, FAM, reviewer_signoff='none')),
    ('under-surveyed-family', lambda t: set_term(t, FAM, coverage_status='under-surveyed')),
    ('untriaged', lambda t: triage(t, [])),
    ('triage-not-accepted', lambda t: triage(t, [(FAM, GROUP, 'applicable')], accepted_by=None)),
    ('not-yet-surveyed', lambda t: os.remove(t / CS.SURVEYS / FAM / (SUBS[FAM][-1].split('/')[1] + '.yaml'))),
    ('not-yet-surveyed', lambda t: note(t, SUBS[FAM][0], capabilities=MEMBERS[GROUP][:1])),   # not every term
    ('survey-note-not-accepted', lambda t: note(t, SUBS[FAM][0], accepted_by=None)),
    ('occupied', lambda t: entry(t, 'draft', FAM, [T_GROUP])),                                # a draft is presence
    ('occupied', lambda t: entry(t, 'sec', 'physics', [T_GROUP], secondary=[FAM])),
    ('occupied', lambda t: entry(t, 'sub', 'physics', [T_OTHER], subsets=[{
        'id': 'sub#x', 'label': 'x', 'domain_override': {'primary': SUBS[FAM][0]}, 'capability_override': [T_GROUP]}])),
    ('below-min-confidence', _demote),
    ('measured-nowhere-else', lambda t: os.remove(t / 'data' / 'benchmarks' / 'physics' / 'elsewhere.yaml')),
    ('family-inactive', _stale),
])
def test_a_cell_missing_any_condition_is_refused_and_says_which(tree, code, breaks):
    claimable(tree)
    breaks(tree)
    doc = emit(tree, reviewed_only=True)
    assert doc['claims'] == []
    c = cell(doc, FAM, GROUP)
    assert c['gap_claim'] == G.REFUSED and code in c['withheld'] and c['gap_claim_refusal']
    assert c['empty'] == (None if code == 'occupied' else G.CATEGORY_3)
    if code == 'unreviewed-family':
        assert c['gap_claim_refusal'].startswith(G.INSUFFICIENT)


def test_below_the_floor_the_refusal_names_insufficient_curation_confidence(tree):
    claimable(tree)
    _demote(tree)
    c = cell(emit(tree), FAM, GROUP)
    assert c['withheld'] == ['below-min-confidence']
    assert c['gap_claim_refusal'].startswith(G.INSUFFICIENT) and '0.3000 is below 0.60' in c['gap_claim_refusal']


# ---- scripts/check_gap_claims.py -------------------------------------------------------------------------------

def test_the_checker_accepts_a_claim_from_a_reviewed_family_on_the_coarse_grid_with_its_survey_notes(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    assert len(doc['claims']) == 1
    assert check(tree, doc) == []
    assert C.main(['--root', str(tree), '--gaps', str(write(tree, doc))]) == 0


def test_the_checker_refuses_a_claim_from_the_fine_grid(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    doc['claims'][0]['grid'] = 'fine'
    assert any("from the 'fine' grid; only the coarse grid" in e for e in check(tree, doc))
    doc['grid'] = 'fine'
    assert any("is the 'fine' grid" in e for e in check(tree, doc))
    with pytest.raises(G.GridRefused):                          # and the emitter never makes one
        G.emit('fine', root=str(tree))


def test_the_checker_refuses_a_claim_from_an_unreviewed_family(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    set_term(tree, FAM, reviewer_signoff='none')                # the sign-off withdrawn after publishing
    errs = check(tree, doc)
    assert any('%s is unsigned in %s' % (FAM, G.DOMAINS) in e for e in errs)
    assert any('is stale' in e for e in errs)


def test_the_checker_refuses_an_asserted_cell_in_an_unsigned_family(tree):
    entry(tree, 'p', 'physics', [T_OTHER], released=AS_OF)
    doc = emit(tree, reviewed_only=True)
    forged = dict(cell(doc, 'physics', GROUP), gap_claim=G.ASSERTED, gap_claim_refusal=None, withheld=[], grid='coarse')
    cell(doc, 'physics', GROUP).update(gap_claim=G.ASSERTED, gap_claim_refusal=None, withheld=[])
    doc['claims'], doc['claims_total'] = [forged], 1
    errs = check(tree, doc)
    assert any('physics is unsigned' in e and 'an unreviewed family asserts no gap' in e for e in errs)
    assert any('cell (physics, %s): physics is unsigned' % GROUP in e for e in errs)
    assert any('names no survey note' in e for e in errs)


def test_the_checker_refuses_a_claim_naming_no_survey_note_or_a_missing_one(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    first = doc['claims'][0]['survey_notes'][0]['note']
    doc['claims'][0]['survey_notes'] = []
    assert any('names no survey note' in e for e in check(tree, doc))
    doc['claims'][0]['survey_notes'] = [{'note': first}]
    assert any('no survey note covers' in e for e in check(tree, doc))
    doc = emit(tree, reviewed_only=True)
    os.remove(tree / first)
    assert any('survey note %s does not exist' % first in e for e in check(tree, doc))


def test_the_checker_refuses_a_claim_counting_unreviewed_entries(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    _demote(tree)                                               # the two entries are drafts after all
    errs = check(tree, doc)
    assert any('only reviewed entries count' in e for e in errs)
    entry(tree, 'draft', FAM, [T_GROUP])                        # and a draft in the cell is presence
    assert any('the index holds draft in the cell' in e for e in check(tree, doc))


def test_the_checker_refuses_an_unaccepted_note_or_triage_behind_a_claim(tree):
    claimable(tree)
    doc = emit(tree, reviewed_only=True)
    note(tree, SUBS[FAM][0], accepted_by=None)
    triage(tree, [(FAM, GROUP, 'applicable')], accepted_by=None)
    errs = check(tree, doc)
    assert any('is accepted by nobody' in e for e in errs)
    assert any('accepted by a person (03 S7.1)' in e for e in errs)


def test_the_checker_refuses_an_artifact_not_reviewed_only_below_the_floor_or_stale(tree):
    claimable(tree)
    assert any('not made --reviewed-only' in e for e in check(tree, emit(tree)))
    assert any('below the floor 0.60' in e for e in check(tree, emit(tree, reviewed_only=True, min_confidence=0.1)))
    doc = emit(tree, reviewed_only=True)
    entry(tree, 'late', 'physics', [T_OTHER])
    assert any('is stale' in e for e in check(tree, doc))


def test_the_checker_refuses_a_cell_without_its_four_factors_or_its_version(tree):
    entry(tree, 'p', 'physics', [T_GROUP], released=AS_OF)
    entry(tree, 'e', 'earth-climate', [T_OTHER], released=AS_OF)
    doc = emit(tree, reviewed_only=True)
    del doc['matrix'][0]['factors']['domain_activity']
    doc['matrix'][1]['capability_groups_version'] = '0.0.1'
    cell(doc, 'physics', OTHER)['gap_score'] = 0.5                 # its four factors give 0.0
    cell(doc, 'chemistry-materials', OTHER)['gap_score'] = 0.5     # nothing dated there: no score at all
    doc['matrix'].pop()
    errs = check(tree, doc)
    assert any('not the four of 12 S5.3' in e for e in errs)
    assert any("capability_groups version '0.0.1'" in e for e in errs)
    assert any('cell (physics, %s): gap_score 0.5 is not the product of its four factors' % OTHER in e for e in errs)
    assert any('cell (chemistry-materials, %s): gap_score 0.5 without four computable factors' % OTHER in e
               for e in errs)
    assert any('the matrix holds 246 cells' in e for e in errs)


def test_the_checker_says_how_to_make_a_missing_artifact(tree):
    errs, doc = C.check(str(tree), str(tree / 'build' / 'derived' / 'gaps.json'))
    assert doc is None and 'bench gaps --grid coarse --reviewed-only --format json' in errs[0]


# ---- the command --------------------------------------------------------------------------------------------------

def test_min_confidence_on_the_command_line(tree, monkeypatch):
    claimable(tree)
    monkeypatch.setattr('tools.cli.ROOT', str(tree))
    run = CliRunner().invoke
    assert run(app, ['gaps', '--min-confidence', '1.5']).exit_code == 2
    out = json.loads(run(app, ['gaps', '--reviewed-only', '--format', 'json', '--min-confidence', '0.7']).output)
    assert out['parameters']['min_confidence'] == 0.7
    md = run(app, ['gaps', '--reviewed-only']).output
    assert '## Gap matrix' in md and '| %s | %s |' % (FAM, GROUP) in md


# ---- the corpus as it is -----------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def corpus():
    return G.emit('coarse', ROOT, reviewed_only=True)


def unsigned_everywhere():
    return all((f.get('reviewer_signoff') or 'none') == 'none' for f in ROWS['families'])


def test_today_the_matrix_asserts_no_gap_and_every_cell_reads_insufficient(corpus):
    if not unsigned_everywhere():
        pytest.fail('a family is signed: this test, docs/gap-matrix.md and the report of P1-S14-T08 describe a '
                    'catalogue with none; update all three')
    assert corpus['claims'] == [] and corpus['claims_total'] == 0 and corpus['cells'] == []
    assert len(corpus['matrix']) == 247
    for c in corpus['matrix']:
        assert c['gap_claim'] == G.REFUSED and c['gap_claim_refusal'].startswith(G.INSUFFICIENT)
        assert list(c['factors']) == list(G.FACTORS) and c['capability_groups_version'] == COLS['version']
    assert corpus['statement'].startswith('The matrix asserts no gap until families are reviewed: 0 of 19')
    assert corpus['review_backed']['families'] == 0


def test_today_the_verify_passes(corpus, tmp_path):
    path = tmp_path / 'gaps.json'
    path.write_text(json.dumps(corpus, indent=1, ensure_ascii=False), encoding='utf-8')
    errs, _ = C.check(ROOT, str(path))
    assert errs == []


def test_the_counts_agree_with_the_coverage_states_artifact(corpus):
    states = {(c['family'], c['group']): c for c in CS.build(ROOT)['cells']}
    for c in corpus['matrix']:
        s = states[(c['family'], c['group'])]
        assert (c['counts']['primary'], c['counts']['secondary'], c['state']) == (s['primary'], s['secondary'], s['state'])


def test_the_page_says_the_matrix_asserts_no_gap_until_families_are_reviewed():
    with open(os.path.join(ROOT, 'docs', 'gap-matrix.md'), encoding='utf-8') as fh:
        page = fh.read()
    assert 'The matrix asserts no gap until families are reviewed.' in page
    assert G.INSUFFICIENT in page
    assert 'bench gaps --grid coarse --reviewed-only --format json > build/derived/gaps.json' in page
    if not unsigned_everywhere():
        pytest.fail('a family is signed: docs/gap-matrix.md says none is; update it')
