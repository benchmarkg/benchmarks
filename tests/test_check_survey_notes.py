"""Tests for tools/build/coverage_states.py and scripts/check_survey_notes.py (P1-S12-T08; 02 S3, 02 S11, 12 S5.4).

The verify: `bench build --derived && python scripts/check_survey_notes.py`. Done when "No coverage cell or
subdomain page renders surveyed-and-empty without a dated survey note behind it."
"""
import datetime as dt
import json
import os
import shutil
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_survey_notes as C  # noqa: E402
from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps as G  # noqa: E402

TODAY = dt.date(2026, 11, 16)
ROWS, COLS = G.axes(ROOT)
SUBS = {}
for _t in yaml.safe_load(open(os.path.join(ROOT, G.DOMAINS), encoding='utf-8'))['terms']:
    if _t.get('parent') and _t.get('status') != 'retired':
        SUBS.setdefault(_t['parent'], []).append(_t['id'])
G1, G2 = [g for g in COLS['groups'] if len(g['members']) >= 2][:2]
FAM = 'physics'                          # any family; the synthetic tree holds only what a test files


@pytest.fixture
def tree(tmp_path):
    for rel in (G.DOMAINS, G.CAPABILITIES, G.GROUPS):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    text = (tmp_path / G.DOMAINS).read_text(encoding='utf-8')            # the tree holds only what a test declares:
    (tmp_path / G.DOMAINS).write_text(text.replace('gap_placeholder: true', 'gap_placeholder: false'),
                                      encoding='utf-8')                  # phylogenetics' note is not copied
    return tmp_path


def entry(root, ident, primary, capability, secondary=()):
    d = root / 'data' / 'benchmarks' / primary.split('/')[0]
    d.mkdir(parents=True, exist_ok=True)
    (d / (ident + '.yaml')).write_text(yaml.safe_dump({
        'id': ident, 'domain': {'primary': primary, 'secondary': list(secondary)},
        'capability': list(capability)}), encoding='utf-8')


def note(root, sub, capabilities='all', **over):
    family, stem = sub.split('/')
    survey = {'family': family, 'subdomain': sub, 'conducted_on': dt.date(2026, 11, 1),
              'method': 'arXiv and GitHub searches for the subdomain', 'scope': {'capabilities': capabilities}}
    doc = {'survey': survey, 'finding': {'decision': 'surveyed-and-empty', 'note': 'Nothing found in %s.' % sub}}
    for k, v in over.items():
        part, key = k.split('__')
        if v is None:
            doc[part].pop(key, None)
        else:
            doc[part][key] = v
    d = root / 'data' / 'surveys' / family
    d.mkdir(parents=True, exist_ok=True)
    path = d / (stem + '.yaml')
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
    return path


def family_note(root, family, name='_scoping', **finding):
    d = root / 'data' / 'surveys' / family
    d.mkdir(parents=True, exist_ok=True)
    (d / (name + '.yaml')).write_text(yaml.safe_dump({
        'survey': {'family': family, 'conducted_on': dt.date(2026, 10, 1), 'method': 'a family-wide pass',
                   'scope': {'subdomains': 'all'}},
        'finding': dict(finding)}, sort_keys=False), encoding='utf-8')


def set_term(root, ident, **fields):
    path = root / G.DOMAINS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    next(t for t in doc['terms'] if t['id'] == ident).update(fields)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')


def artifact(root):
    return CS.write(str(root), str(root / 'build' / 'derived' / 'coverage-states.json'))


def run(root):
    return C.check(str(root), TODAY, str(root / 'build' / 'derived' / 'coverage-states.json'))


def page(doc, sub):
    return next(p for p in doc['subdomains'] if p['id'] == sub)


def cell(doc, family, group):
    return next(c for c in doc['cells'] if c['family'] == family and c['group'] == group)


# ---- the states ----------------------------------------------------------------------------------------------

def test_with_no_note_every_empty_page_and_cell_reads_not_yet_surveyed(tree):
    entry(tree, 'b1', SUBS[FAM][0], [G1['members'][0]])
    doc = CS.build(str(tree))
    assert page(doc, SUBS[FAM][0])['state'] == 'has-benchmarks'
    assert {p['state'] for p in doc['subdomains'] if p['id'] != SUBS[FAM][0]} == {'not-yet-surveyed'}
    assert doc['counts']['subdomains']['surveyed-and-empty'] == 0
    assert doc['counts']['cells']['surveyed-and-empty'] == 0
    assert cell(doc, FAM, G1['id'])['state'] == 'has-benchmarks'
    assert len(doc['cells']) == len(ROWS['families']) * len(COLS['groups'])
    artifact(tree)
    assert run(tree) == []


def test_a_dated_note_makes_its_page_surveyed_and_empty_and_renders_its_summary(tree):
    sub = SUBS[FAM][1]
    note(tree, sub)
    doc = CS.build(str(tree))
    p = page(doc, sub)
    assert p['state'] == 'surveyed-and-empty'
    assert p['survey'] == {'note': 'data/surveys/%s.yaml' % sub, 'conducted_on': '2026-11-01',
                           'summary': 'Nothing found in %s.' % sub}
    artifact(tree)
    assert run(tree) == []


def test_one_secondary_entry_makes_a_page_has_benchmarks(tree):
    """02 S11 rule 1: "Cell state is determined by presence at any weight"."""
    sub = SUBS[FAM][1]
    entry(tree, 'b1', SUBS['vision'][0], [G1['members'][0]], secondary=[sub])
    p = page(CS.build(str(tree)), sub)
    assert (p['state'], p['primary'], p['secondary']) == ('has-benchmarks', 0, 1)


def test_a_note_contradicted_by_an_entry_fails(tree):
    sub = SUBS[FAM][1]
    note(tree, sub)
    entry(tree, 'b1', SUBS['vision'][0], [G1['members'][0]], secondary=[sub])
    artifact(tree)
    errs = run(tree)
    assert any('says %s is surveyed-and-empty' % sub in e and 'b1 is filed there' in e for e in errs), errs
    assert page(CS.build(str(tree)), sub)['state'] == 'has-benchmarks'      # presence wins, never the note


def test_a_per_capability_note_holds_beside_entries_that_test_something_else(tree):
    sub = SUBS[FAM][0]
    entry(tree, 'b1', sub, [G1['members'][0]])
    note(tree, sub, capabilities=list(G2['members']))
    artifact(tree)
    assert run(tree) == []
    assert page(CS.build(str(tree)), sub)['state'] == 'has-benchmarks'
    note(tree, sub, capabilities=[G1['members'][0]])
    artifact(tree)
    assert any('for %s' % G1['members'][0] in e for e in run(tree))


# ---- note shape ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize('over, message', [
    ({'survey__conducted_on': None}, 'is not a date'),
    ({'survey__conducted_on': '2026-11'}, 'is not a date'),
    ({'survey__conducted_on': dt.date(2026, 12, 1)}, 'is after today'),
    ({'survey__method': ' '}, 'survey.method is empty'),
    ({'survey__scope': None}, 'no survey.scope'),
    ({'survey__family': 'vision'}, 'is not its directory'),
    ({'finding__decision': 'candidates-found'}, 'curation backlog, not a note'),
])
def test_a_note_without_its_date_method_scope_or_finding_fails(tree, over, message):
    sub = SUBS[FAM][1]
    note(tree, sub, **over)
    artifact(tree)
    assert any(message in e for e in run(tree)), run(tree)


@pytest.mark.parametrize('over', [{'survey__conducted_on': None}, {'survey__conducted_on': '2026-11'},
                                  {'survey__scope': None}, {'finding__decision': 'candidates-found'}])
def test_an_undated_unscoped_or_undecided_note_never_empties_its_page(tree, over):
    sub = SUBS[FAM][1]
    note(tree, sub, **over)
    assert page(CS.build(str(tree)), sub)['state'] == 'not-yet-surveyed'


def test_unknown_capabilities_in_a_scope_fail(tree):
    note(tree, SUBS[FAM][1], capabilities=['no-such-capability'])
    artifact(tree)
    assert any('scope.capabilities must be' in e for e in run(tree))


def test_a_note_speaks_only_for_the_page_it_is_filed_under(tree):
    a, b = SUBS[FAM][1], SUBS[FAM][2]
    note(tree, a, survey__subdomain=b)
    doc = CS.build(str(tree))
    assert page(doc, a)['state'] == 'surveyed-and-empty' and page(doc, b)['state'] == 'not-yet-surveyed'
    artifact(tree)
    assert any('is not the file it is in' in e for e in run(tree))


def test_a_note_for_a_subdomain_that_does_not_exist_fails(tree):
    note(tree, '%s/no-such-subdomain' % FAM)
    artifact(tree)
    assert any('is not a live subdomain' in e for e in run(tree))


def test_a_family_level_note_never_empties_a_page_or_a_cell(tree):
    family_note(tree, FAM)
    doc = CS.build(str(tree))
    assert {p['state'] for p in doc['subdomains'] if p['family'] == FAM} == {'not-yet-surveyed'}
    artifact(tree)
    assert run(tree) == []
    family_note(tree, FAM, decision='surveyed-and-empty')
    artifact(tree)
    assert any('a family-level note cannot decide anything empty' in e for e in run(tree))


# ---- placeholders, muting, cells -----------------------------------------------------------------------------

def test_a_gap_placeholder_needs_a_note_covering_all_capabilities(tree):
    sub = SUBS[FAM][1]
    set_term(tree, sub, gap_placeholder=True)
    artifact(tree)
    assert any('%s is a gap_placeholder' % sub in e for e in run(tree))
    note(tree, sub, capabilities=list(G1['members']))
    artifact(tree)
    assert any('%s is a gap_placeholder' % sub in e for e in run(tree))
    note(tree, sub)
    artifact(tree)
    assert run(tree) == []


def test_a_cell_reads_empty_only_when_every_subdomain_of_its_family_is_noted(tree):
    for sub in SUBS[FAM]:
        note(tree, sub, capabilities=list(G1['members']))
    doc = CS.build(str(tree))
    c = cell(doc, FAM, G1['id'])
    assert c['state'] == 'surveyed-and-empty'
    assert c['survey_notes'] == sorted('data/surveys/%s.yaml' % s for s in SUBS[FAM])
    assert cell(doc, FAM, G2['id'])['state'] == 'not-yet-surveyed'        # its terms were not searched
    assert {page(doc, s)['state'] for s in SUBS[FAM]} == {'not-yet-surveyed'}  # pages need `all`
    artifact(tree)
    assert run(tree) == []
    os.remove(tree / 'data' / 'surveys' / ('%s.yaml' % SUBS[FAM][0]))
    assert cell(CS.build(str(tree)), FAM, G1['id'])['state'] == 'not-yet-surveyed'


def test_an_under_surveyed_family_needs_a_dated_family_note_and_refuses_every_gap(tree):
    for sub in SUBS[FAM]:
        note(tree, sub)
    set_term(tree, FAM, coverage_status='under-surveyed')
    doc = CS.build(str(tree))
    fam = next(f for f in doc['families'] if f['id'] == FAM)
    assert fam['gap_claims'] == 'refused'
    assert {c['state'] for c in doc['cells'] if c['family'] == FAM} == {'not-yet-surveyed'}
    assert {page(doc, s)['state'] for s in SUBS[FAM]} == {'surveyed-and-empty'}   # the pages keep their notes
    artifact(tree)
    assert any('%s carries coverage_status: under-surveyed' % FAM in e for e in run(tree))
    family_note(tree, FAM)
    artifact(tree)
    assert run(tree) == []


# ---- the artifact --------------------------------------------------------------------------------------------

def test_a_missing_or_stale_artifact_fails(tree):
    assert any('run `bench build --derived` first' in e for e in run(tree))
    artifact(tree)
    note(tree, SUBS[FAM][1])
    assert any('is stale' in e for e in run(tree))


def test_a_forged_empty_state_is_caught(tree):
    path = artifact(tree)
    doc = json.load(open(path, encoding='utf-8'))
    page(doc, SUBS[FAM][1])['state'] = 'surveyed-and-empty'
    cell(doc, FAM, G1['id'])['state'] = 'surveyed-and-empty'
    json.dump(doc, open(path, 'w', encoding='utf-8'))
    errs = run(tree)
    assert any('subdomain page %s reads surveyed-and-empty without a dated note' % SUBS[FAM][1] in e for e in errs)
    assert any('cell (%s, %s) reads surveyed-and-empty without' % (FAM, G1['id']) in e for e in errs)


def test_the_repository_passes_and_phylogenetics_reads_surveyed_and_empty(tmp_path):
    out = CS.write(ROOT, str(tmp_path / 'coverage-states.json'))
    assert C.check(ROOT, TODAY, out) == []
    doc = json.load(open(out, encoding='utf-8'))
    p = page(doc, 'biology-genetics/phylogenetics')
    assert p['state'] == 'surveyed-and-empty' and p['gap_placeholder'] is True
    assert p['survey']['conducted_on'] == '2026-11-05'
    assert CS.serialise(CS.build(ROOT)) == CS.serialise(CS.build(ROOT))   # a function of the tree, no clock
