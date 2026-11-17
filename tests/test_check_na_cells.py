"""Tests for scripts/check_na_cells.py and the not-applicable state in tools/build/coverage_states.py (P1-S12-T09;
12 S5.4, 03 S7.1, 02 S4.3).

The verify: `bench build --derived && python scripts/check_na_cells.py`. Done when "Every NA cell carries a
rationale and leaves both sides of every coverage percentage."
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
import check_na_cells as C  # noqa: E402
from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps as G  # noqa: E402

TODAY = dt.date(2026, 11, 16)
ROWS, COLS = G.axes(ROOT)
FAMS = [f['id'] for f in ROWS['families']]
GROUPS = [g['id'] for g in COLS['groups']]
MEMBERS = {g['id']: g['members'] for g in COLS['groups']}
SUBS = {}
for _t in yaml.safe_load(open(os.path.join(ROOT, G.DOMAINS), encoding='utf-8'))['terms']:
    if _t.get('parent') and _t.get('status') != 'retired':
        SUBS.setdefault(_t['parent'], []).append(_t['id'])
FAM, G1, G2 = 'physics', GROUPS[0], GROUPS[1]
WHY = 'A benchmark of this shape would be coherent here.'


@pytest.fixture
def tree(tmp_path):
    for rel in (G.DOMAINS, G.CAPABILITIES, G.GROUPS):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    text = (tmp_path / G.DOMAINS).read_text(encoding='utf-8')            # no placeholder: its note is not copied
    (tmp_path / G.DOMAINS).write_text(text.replace('gap_placeholder: true', 'gap_placeholder: false'),
                                      encoding='utf-8')
    entry(tmp_path, 'b1', SUBS[FAM][0], [MEMBERS[G1][0]])
    return tmp_path


def entry(root, ident, primary, capability, secondary=()):
    d = root / 'data' / 'benchmarks' / primary.split('/')[0]
    d.mkdir(parents=True, exist_ok=True)
    (d / (ident + '.yaml')).write_text(yaml.safe_dump({
        'id': ident, 'domain': {'primary': primary, 'secondary': list(secondary)},
        'capability': list(capability)}), encoding='utf-8')


def item(family, group, verdict='applicable', **over):
    out = {'family': family, 'group': group, 'verdict': verdict, 'rationale': WHY, 'declared_by': 'a curator',
           'declared_on': dt.date(2026, 11, 1)}
    out.update(over)
    return {k: v for k, v in out.items() if v is not None}


def triage(root, declared=(), skip=(), extra=()):
    """One row per cell: `declared` not-applicable, the rest applicable, `skip` left out, `extra` appended."""
    rows = [item(f, g, 'not-applicable' if (f, g) in declared else 'applicable')
            for f in FAMS for g in GROUPS if (f, g) not in skip]
    doc = {'version': '0.1.0', 'updated': dt.date(2026, 11, 1), 'accepted_by': None, 'cells': rows + list(extra)}
    path = root / CS.NOT_APPLICABLE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')
    return doc


def edit(root, change):
    """Apply `change` to the triage file's document and write it back."""
    path = root / CS.NOT_APPLICABLE
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    change(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding='utf-8')


def row(doc, family, group):
    return next(r for r in doc['cells'] if r['family'] == family and r['group'] == group)


def artifact(root):
    return CS.write(str(root), str(root / 'build' / 'derived' / 'coverage-states.json'))


def run(root):
    return C.check(str(root), TODAY, str(root / 'build' / 'derived' / 'coverage-states.json'))


def cell(doc, family, group):
    return next(c for c in doc['cells'] if c['family'] == family and c['group'] == group)


# ---- the declared state and the coverage figures -------------------------------------------------------------

def test_a_declared_cell_reads_not_applicable_and_leaves_both_sides_of_the_figures(tree):
    triage(tree, declared={(FAM, G2)})
    doc = CS.build(str(tree))
    c = cell(doc, FAM, G2)
    assert (c['state'], c['triage'], c['rationale']) == ('not-applicable', 'not-applicable', WHY)
    assert (cell(doc, FAM, G1)['triage'], cell(doc, FAM, G1)['rationale']) == ('applicable', WHY)
    n = len(FAMS) * len(GROUPS)
    assert doc['coverage'] == {'cells': n, 'not_applicable': 1, 'denominator': n - 1, 'has_benchmarks': 1,
                               'percent': round(100.0 / (n - 1), 1)}
    fam = next(f for f in doc['families'] if f['id'] == FAM)['coverage']
    assert fam == {'cells': len(GROUPS), 'not_applicable': 1, 'denominator': len(GROUPS) - 1, 'has_benchmarks': 1,
                   'percent': round(100.0 / (len(GROUPS) - 1), 1)}
    assert doc['counts']['cells']['not-applicable'] == 1 and doc['counts']['cells_untriaged'] == 0
    artifact(tree)
    assert run(tree) == []


def test_without_a_declaration_the_figures_count_every_cell(tree):
    triage(tree)
    doc = CS.build(str(tree))
    assert doc['coverage']['denominator'] == len(FAMS) * len(GROUPS) and doc['coverage']['not_applicable'] == 0
    artifact(tree)
    assert run(tree) == []


def test_a_declared_cell_never_reads_surveyed_and_empty(tree):
    for sub in SUBS[FAM]:
        d = tree / 'data' / 'surveys' / FAM
        d.mkdir(parents=True, exist_ok=True)
        (d / (sub.split('/')[1] + '.yaml')).write_text(yaml.safe_dump({
            'survey': {'family': FAM, 'subdomain': sub, 'conducted_on': dt.date(2026, 11, 1), 'method': 'searched',
                       'scope': {'capabilities': 'all'}},
            'finding': {'decision': 'surveyed-and-empty'}}), encoding='utf-8')
    triage(tree, declared={(FAM, G2)})
    doc = CS.build(str(tree))
    assert cell(doc, FAM, G2)['state'] == 'not-applicable'
    assert cell(doc, FAM, GROUPS[2])['state'] == 'surveyed-and-empty'


# ---- evidence and blankets -----------------------------------------------------------------------------------

def test_an_occupied_cell_cannot_be_declared(tree):
    triage(tree, declared={(FAM, G1)})
    artifact(tree)
    errs = run(tree)
    assert any('(%s, %s) is declared not-applicable, but an entry occupies it' % (FAM, G1) in e for e in errs), errs
    c = cell(CS.build(str(tree)), FAM, G1)
    assert (c['state'], c['triage']) == ('has-benchmarks', 'not-applicable')      # presence wins; the row shows


def test_a_secondary_entry_is_occupation_too(tree):
    triage(tree, declared={('biology-genetics', G2)})
    entry(tree, 'b2', SUBS['safety-alignment'][0], [MEMBERS[G2][0]], secondary=[SUBS['biology-genetics'][0]])
    artifact(tree)
    assert any('(biology-genetics, %s) is declared not-applicable, but an entry occupies it' % G2 in e
               for e in run(tree))


def test_chemistry_autonomy_is_never_declared(tree):
    triage(tree, declared={('chemistry-materials', 'autonomy-and-oversight')})
    artifact(tree)
    assert any('02 S4.3 names it as the live cell' in e for e in run(tree))


def test_a_column_declared_by_rule_fails(tree):
    many = [f for f in FAMS if f != FAM]
    half = len(FAMS) // 2
    triage(tree, declared={(f, G2) for f in many[:half]})
    artifact(tree)
    assert run(tree) == []
    triage(tree, declared={(f, G2) for f in many[:half + 1]})
    artifact(tree)
    assert any('%s is declared not-applicable in %d of %d families' % (G2, half + 1, len(FAMS)) in e for e in run(tree))


def test_a_family_with_every_group_declared_fails(tree):
    triage(tree, declared={('engineering-design', g) for g in GROUPS})
    artifact(tree)
    assert any('engineering-design has every group declared not-applicable' in e for e in run(tree))


@pytest.mark.parametrize('missing', [('vision', G2), (FAM, G1)], ids=['empty', 'occupied'])
def test_every_cell_must_be_triaged(tree, missing):
    triage(tree, skip={missing})
    artifact(tree)
    assert any('(%s, %s) is untriaged' % missing in e for e in run(tree))
    assert cell(CS.build(str(tree)), *missing)['triage'] is None


def test_the_triage_file_must_exist(tree):
    artifact(tree)
    assert any('taxonomy/_triage/not-applicable.yaml does not exist' in e for e in run(tree))


# ---- shape ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('over, message', [
    ({'rationale': None}, 'one sentence'),
    ({'rationale': 'No full stop'}, 'one sentence'),
    ({'rationale': 'Two sentences. Not one.'}, 'one sentence'),
    ({'declared_by': ' '}, 'no declared_by'),
    ({'declared_on': '2026-11'}, 'is not a date'),
    ({'declared_on': dt.date(2026, 12, 1)}, 'is after today'),
    ({'family': 'no-such-family'}, 'is not a family'),
    ({'group': 'no-such-group'}, 'is not a group'),
    ({'verdict': 'maybe'}, 'is not one of applicable, not-applicable'),
    ({'verdict': None}, 'keys must be'),
    ({'note': 'extra'}, 'keys must be'),
])
def test_a_malformed_row_fails(tree, over, message):
    triage(tree, declared={(FAM, G2)})

    def change(doc):
        r = row(doc, FAM, G2)
        r.update(over)
        for k in [k for k, v in r.items() if v is None]:
            del r[k]
    edit(tree, change)
    artifact(tree)
    assert any(message in e for e in run(tree)), run(tree)


@pytest.mark.parametrize('over, message', [
    ({'version': 1}, 'is not semver'),
    ({'updated': dt.date(2026, 12, 1)}, 'is not a date on or before today'),
    ({'accepted_by': ' '}, 'accepted_by is null or names'),
    ({'note': 'extra'}, 'keys must be'),
])
def test_a_malformed_file_fails(tree, over, message):
    triage(tree)
    edit(tree, lambda doc: doc.update(over))
    artifact(tree)
    assert any(message in e for e in run(tree)), run(tree)


def test_a_file_without_cells_fails(tree):
    triage(tree)
    edit(tree, lambda doc: doc.pop('cells'))
    artifact(tree)
    assert any('needs a list `cells`' in e for e in run(tree))


def test_a_rationale_may_cite_a_section_number(tree):
    triage(tree, declared={(FAM, G2)})
    edit(tree, lambda doc: row(doc, FAM, G2).update(
        rationale='Kept as 02 S4.3 and 12 S5.4 describe, e.g. for laboratories.'))
    artifact(tree)
    assert run(tree) == []


def test_a_cell_listed_twice_fails(tree):
    triage(tree, declared={(FAM, G2)}, extra=[item(FAM, G2)])
    artifact(tree)
    assert any('the cell already has a row' in e for e in run(tree))
    assert cell(CS.build(str(tree)), FAM, G2)['state'] == 'not-applicable'       # the first row wins


# ---- the artifact --------------------------------------------------------------------------------------------

def test_a_missing_or_stale_artifact_fails(tree):
    triage(tree)
    assert any('run `bench build --derived` first' in e for e in run(tree))
    artifact(tree)
    triage(tree, declared={(FAM, G2)})
    assert any('is stale' in e for e in run(tree))


def test_a_forged_state_or_figure_is_caught(tree):
    triage(tree)
    path = artifact(tree)
    doc = json.load(open(path, encoding='utf-8'))
    cell(doc, 'vision', G2)['state'] = 'not-applicable'
    doc['coverage']['denominator'] += 5
    json.dump(doc, open(path, 'w', encoding='utf-8'))
    errs = run(tree)
    assert any('cell (vision, %s) reads not-applicable without a declaration' % G2 in e for e in errs)
    assert any('the overall coverage figure' in e for e in errs)


def test_the_repository_passes(tmp_path):
    out = CS.write(ROOT, str(tmp_path / 'coverage-states.json'))
    assert C.check(ROOT, TODAY, out) == []
    doc = json.load(open(out, encoding='utf-8'))
    assert doc['counts']['cells_untriaged'] == 0
    assert all(c['triage'] in CS.VERDICTS and c['rationale'] for c in doc['cells'])
    assert cell(doc, 'chemistry-materials', 'autonomy-and-oversight')['triage'] == 'applicable'
    rows = yaml.safe_load(open(os.path.join(ROOT, CS.NOT_APPLICABLE), encoding='utf-8'))['cells']
    assert len(rows) == len(FAMS) * len(GROUPS) == 247                         # P4-S1-T02's "exactly 247 rows"
