"""Tests for the unreviewed badge and the Gap Finder refusal (P1-S4-T08; 14 Phase 1 "The honest gate").

The verify: `python scripts/check_unreviewed_badging.py && bench gaps --grid coarse --reviewed-only --format json |
python -c "...assert not [c for c in g['cells'] if c.get('reviewer_signoff')=='none']"`. Done when "Every unsigned
family is badged on entry, on the coverage map, and is silent in the gap output." The three halves are tested on a
copied taxonomy with one family signed, the page half on a stand-in built site, and the repository as it is.
"""
import os
import shutil
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_unreviewed_badging as U  # noqa: E402
from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps as G  # noqa: E402

ROWS, COLS = G.axes(ROOT)
TERM = COLS['groups'][0]['members'][0]
SUBS = {}
for t in yaml.safe_load(open(os.path.join(ROOT, G.DOMAINS), encoding='utf-8'))['terms']:
    if t.get('parent'):
        SUBS.setdefault(t['parent'], []).append(t['id'])


@pytest.fixture
def tree(tmp_path):
    for rel in (G.DOMAINS, G.CAPABILITIES, G.GROUPS):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    for ident, family in (('b1', 'physics'), ('b2', 'earth-climate')):
        d = tmp_path / 'data' / 'benchmarks' / family
        d.mkdir(parents=True, exist_ok=True)
        (d / (ident + '.yaml')).write_text(yaml.safe_dump({'id': ident, 'domain': {'primary': SUBS[family][0]},
                                                           'capability': [TERM]}), encoding='utf-8')
    path = tmp_path / G.DOMAINS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    fam = next(t for t in doc['terms'] if t['id'] == 'physics')
    fam.update(reviewer_signoff='generalist', reviewer='a reviewer', signed_on='2026-11-17')
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')
    return tmp_path


# ---- the refusal ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('family, refused', [
    ({'id': 'x', 'reviewer_signoff': 'none'}, G.INSUFFICIENT),
    ({'id': 'x'}, G.INSUFFICIENT),                                              # unset is unreviewed
    ({'id': 'x', 'reviewer_signoff': 'none', 'coverage_status': 'under-surveyed'}, G.INSUFFICIENT),
    ({'id': 'x', 'reviewer_signoff': 'generalist', 'coverage_status': 'under-surveyed'}, 'under-surveyed'),
    ({'id': 'x', 'reviewer_signoff': 'domain-expert'}, None),
])
def test_why_a_row_is_refused(family, refused):
    got = G.refusal(family)
    assert got is None if refused is None else refused in got


def test_an_unsigned_family_is_refused_in_every_cell_and_a_signed_one_is_not(tree):
    doc = G.coarse(str(tree))
    cells = {c['family']: c for c in doc['cells']}
    assert cells['earth-climate']['gap_claim'] == 'refused'
    assert cells['earth-climate']['gap_claim_refusal'].startswith(G.INSUFFICIENT)
    assert cells['physics']['gap_claim'] == 'permitted' and cells['physics']['gap_claim_refusal'] is None
    fams = {f['id']: f for f in doc['families']}
    assert fams['earth-climate']['gap_claims'] == 'refused' and fams['physics']['gap_claims'] == 'permitted'
    assert 'earth-climate (unreviewed)' in G.markdown(doc) and 'physics (' not in G.markdown(doc)
    assert [c['family'] for c in G.coarse(str(tree), reviewed_only=True)['cells']] == ['physics']


def test_the_coverage_map_marks_the_unsigned_family_unreviewed(tree):
    fams = {f['id']: f for f in CS.build(str(tree))['families']}
    assert fams['earth-climate']['curation_confidence'] == 'unreviewed'
    assert fams['earth-climate']['gap_claims'] == 'refused'
    assert G.INSUFFICIENT in fams['earth-climate']['gap_claims_refusal']
    assert fams['physics']['curation_confidence'] == 'reviewed' and fams['physics']['reviewer_signoff'] == 'generalist'
    assert fams['physics']['gap_claims'] == 'permitted'
    signed = U.families(str(tree))
    assert U.check_coverage(str(tree), signed) == [] and U.check_gaps(str(tree), signed)[0] == []


def test_a_coverage_row_that_forgets_the_mark_fails(tree, monkeypatch):
    real = CS.build

    def forgetful(root):
        doc = real(root)
        for f in doc['families']:
            f['curation_confidence'] = 'reviewed'
        return doc
    monkeypatch.setattr(CS, 'build', forgetful)
    errs = U.check_coverage(str(tree), U.families(str(tree)))
    assert any('family earth-climate is unsigned but reads curation_confidence' in e for e in errs)


# ---- the entry pages ----------------------------------------------------------------------------------------

def page(dist, ident, badge):
    d = dist / 'benchmarks' / ident
    d.mkdir(parents=True, exist_ok=True)
    (d / 'index.html').write_text('<main><h1>%s</h1>%s</main>' % (
        ident, '<p class="unreviewed" %s>Curation confidence: unreviewed.</p>' % U.BADGE if badge else ''),
        encoding='utf-8')


def test_the_badge_is_on_exactly_the_unsigned_familys_pages(tmp_path):
    signed, fam_of = {'physics': 'generalist', 'earth-climate': 'none'}, {'b1': 'physics', 'b2': 'earth-climate'}
    page(tmp_path, 'b1', False)
    page(tmp_path, 'b2', True)
    assert U.check_pages(str(tmp_path), signed, fam_of) == ([], 2)


@pytest.mark.parametrize('b1, b2, message', [
    (False, False, 'b2: its family earth-climate is unsigned, but the page carries no'),
    (True, True, 'b1: its family physics is signed (generalist), but the page carries the unreviewed badge'),
    (False, None, 'b2: no page at'),
])
def test_a_wrong_or_missing_page_fails(tmp_path, b1, b2, message):
    signed, fam_of = {'physics': 'generalist', 'earth-climate': 'none'}, {'b1': 'physics', 'b2': 'earth-climate'}
    page(tmp_path, 'b1', b1)
    if b2 is not None:
        page(tmp_path, 'b2', b2)
    errs, _ = U.check_pages(str(tmp_path), signed, fam_of)
    assert any(message in e for e in errs), errs


def test_the_site_taxonomy_carries_every_familys_signoff():
    from tools.build import site_taxonomy
    doc = yaml.safe_load(site_taxonomy.generate(ROOT))
    fams = {f['id']: f.get('reviewer_signoff') or 'none' for f in ROWS['families']}
    assert {k: v['reviewer_signoff'] for k, v in doc['facets']['domain'].items() if 'reviewer_signoff' in v} == fams


# ---- the repository ----------------------------------------------------------------------------------------

def test_the_repository_passes(capsys):
    assert U.main(['--root', ROOT]) == 0
    assert 'entry pages not read (no --dist)' in capsys.readouterr().out
