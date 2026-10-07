"""Tests for tools/build/gaps.py and `bench gaps` (P1-S2-T11; 12 S5.1-5.3, 02 S4.3, 05 S3).

The verify: "`uv run bench gaps --grid coarse --reviewed-only --format json` emits only non-empty cells, and
`uv run pytest tests/test_gaps_coarse.py` passes, including that --grid fine exits non-zero".
"""
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
from tools.build import gaps as G  # noqa: E402
from tools.cli import app  # noqa: E402

ROWS, COLS = G.axes(ROOT)
GROUP_OF = {t: g['id'] for g in COLS['groups'] for t in g['members']}
MEMBERS = {g['id']: g['members'] for g in COLS['groups']}
SUBS = {}
for t in yaml.safe_load(open(os.path.join(ROOT, G.DOMAINS), encoding='utf-8'))['terms']:
    if t.get('parent'):
        SUBS.setdefault(t['parent'], []).append(t['id'])


def two_groups():
    """Two different groups, and two terms from the first."""
    g1, g2 = [g for g in COLS['groups'] if len(g['members']) >= 2][:2]
    return g1['id'], g1['members'][:2], g2['id'], g2['members'][0]


@pytest.fixture
def tree(tmp_path):
    for rel in (G.DOMAINS, G.CAPABILITIES, G.GROUPS):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    return tmp_path


def entry(root, ident, family, capability, secondary=(), directory=None):
    d = root / 'data' / 'benchmarks' / (directory or family)
    d.mkdir(parents=True, exist_ok=True)
    (d / (ident + '.yaml')).write_text(yaml.safe_dump({
        'id': ident, 'domain': {'primary': SUBS[family][0], 'secondary': [SUBS[f][0] for f in secondary]},
        'capability': list(capability)}), encoding='utf-8')


def sign(root, family, value='generalist'):
    path = root / G.DOMAINS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    next(t for t in doc['terms'] if t['id'] == family)['reviewer_signoff'] = value
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')


def cell(doc, family, group):
    return next((c for c in doc['cells'] if c['family'] == family and c['group'] == group), None)


# ---- the verify ---------------------------------------------------------------------------------------------

def run(*args):
    return CliRunner().invoke(app, ['gaps', *args])


def test_verify_coarse_reviewed_only_json_emits_only_non_empty_cells():
    res = run('--grid', 'coarse', '--reviewed-only', '--format', 'json')
    assert res.exit_code == 0, res.output
    doc = json.loads(res.output)
    assert doc['grid'] == 'coarse' and doc['reviewed_only'] is True
    assert all(c['entries'] + c['secondary_entries'] > 0 for c in doc['cells'])
    assert not [c for c in doc['cells'] if c['reviewer_signoff'] == 'none']


def test_verify_the_fine_grid_exits_non_zero():
    res = run('--grid', 'fine', '--format', 'json')
    assert res.exit_code != 0
    assert '12 S5.1' in res.output and 'refused' in res.output


def test_the_whole_corpus_emits_only_non_empty_cells_and_every_cell_decomposes_by_term():
    doc = json.loads(run('--format', 'json').output)
    assert doc['cells'] and doc['cells_emitted'] == len(doc['cells'])
    for c in doc['cells']:
        assert c['entries'] + c['secondary_entries'] > 0
        assert list(c['terms']) == MEMBERS[c['group']] == list(c['secondary_terms'])
        assert (c['entries'] > 0) == (sum(c['terms'].values()) > 0)
        assert (c['secondary_entries'] > 0) == (sum(c['secondary_terms'].values()) > 0)


def test_the_grid_is_the_vocabularies_19_by_13():
    doc = G.emit()
    assert doc['cells_total'] == len(ROWS['families']) * len(COLS['groups']) == 19 * 13
    assert doc['axes']['rows']['count'] == 19 and doc['axes']['columns']['count'] == 13


def test_the_fine_refusal_reads_its_size_from_the_vocabulary():
    import taxonomy_stats as T
    q = T.quantities()
    assert G.fine_size() == (q['S'], q['C'])
    with pytest.raises(G.GridRefused, match='%d cells' % (q['S'] * q['C'])):
        G.emit('fine')


def test_every_vocabulary_version_is_cited():
    ax = G.emit()['axes']
    assert ax['rows']['version'] and ax['columns']['version'] and ax['columns']['terms_version']


def test_the_published_count_is_seed_progress_s():
    import seed_progress
    assert G.emit()['entries'] == sum(seed_progress.counts().values())


def test_no_gap_score_yet():
    doc = G.emit()
    assert not any(k in c for c in doc['cells'] for k in ('gap_score', 'curation_confidence', 'density'))
    assert 'Phase 4' in doc['not_yet']


# ---- what a cell counts ---------------------------------------------------------------------------------------

def test_benchmarks_per_group_not_tags(tree):
    g1, (t1, t2), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1, t2])
    c = cell(G.emit(root=str(tree)), 'physics', g1)
    assert c['entries'] == 1 and c['benchmarks'] == ['b1']
    assert c['terms'][t1] == c['terms'][t2] == 1 and sum(c['terms'].values()) == 2


def test_one_benchmark_occupies_one_cell_per_group(tree):
    g1, (t1, _), g2, u = two_groups()
    entry(tree, 'b1', 'physics', [t1, u])
    doc = G.emit(root=str(tree))
    assert cell(doc, 'physics', g1)['entries'] == cell(doc, 'physics', g2)['entries'] == 1
    assert doc['cells_emitted'] == 2


def test_the_coarse_total_is_not_the_row_sum_of_the_terms(tree):
    g1, (t1, t2), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1, t2])
    entry(tree, 'b2', 'physics', [t1])
    c = cell(G.emit(root=str(tree)), 'physics', g1)
    assert c['entries'] == 2 and sum(c['terms'].values()) == 3


def test_a_secondary_domain_is_counted_apart_with_its_own_terms(tree):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1], secondary=['earth-climate'])
    doc = G.emit(root=str(tree))
    c = cell(doc, 'earth-climate', g1)
    assert c['entries'] == 0 and c['secondary_entries'] == 1 and c['secondary_benchmarks'] == ['b1']
    assert c['secondary_terms'][t1] == 1 and sum(c['terms'].values()) == 0
    assert cell(doc, 'physics', g1)['secondary_entries'] == 0


def test_a_secondary_in_the_primary_family_is_not_double_counted(tree):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1], secondary=['physics'])
    c = cell(G.emit(root=str(tree)), 'physics', g1)
    assert (c['entries'], c['secondary_entries']) == (1, 0)


def test_stubs_are_not_published(tree):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1], directory='_stubs')
    assert G.emit(root=str(tree))['cells'] == []


def test_an_entry_with_no_capability_counts_toward_its_family_and_no_cell(tree):
    entry(tree, 'b1', 'physics', [])
    doc = G.emit(root=str(tree))
    assert doc['cells'] == [] and doc['entries'] == 1
    assert next(f for f in doc['families'] if f['id'] == 'physics')['entries'] == 1


def test_a_term_in_no_group_is_an_error(tree):
    entry(tree, 'b1', 'physics', ['not-a-capability'])
    with pytest.raises(ValueError, match='in no group'):
        G.emit(root=str(tree))


# ---- --reviewed-only ----------------------------------------------------------------------------------------------

def test_reviewed_only_keeps_only_signed_families(tree):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1])
    entry(tree, 'b2', 'earth-climate', [t1])
    sign(tree, 'physics')
    doc = G.emit(root=str(tree), reviewed_only=True)
    assert [c['family'] for c in doc['cells']] == ['physics']
    assert doc['cells'][0]['reviewer_signoff'] == 'generalist'
    assert doc['cells_in_scope'] == len(COLS['groups'])
    fams = {f['id']: f for f in doc['families']}
    assert fams['physics']['in_scope'] and not fams['earth-climate']['in_scope']


def test_without_reviewed_only_every_family_is_in_scope_and_says_its_signoff(tree):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1])
    doc = G.emit(root=str(tree))
    assert doc['cells_in_scope'] == doc['cells_total']
    assert doc['cells'][0]['reviewer_signoff'] == 'none'


def test_today_no_family_is_signed_so_reviewed_only_emits_nothing_and_says_why():
    if any((f.get('reviewer_signoff') or 'none') != 'none' for f in ROWS['families']):
        pytest.skip('a family has been signed')
    res = run('--reviewed-only')
    assert res.exit_code == 0 and 'Every family has reviewer_signoff: none' in res.output


# ---- the command surface ------------------------------------------------------------------------------------------

def test_markdown_is_the_default_and_names_the_terms(tree, monkeypatch):
    g1, (t1, _), _, _ = two_groups()
    entry(tree, 'b1', 'physics', [t1])
    monkeypatch.setattr('tools.cli.ROOT', str(tree))
    res = run()
    assert res.exit_code == 0
    assert '| physics | %s | 1 | 0 | %s 1 |' % (g1, t1) in res.output


def test_a_bad_format_or_grid_is_a_usage_error():
    assert run('--format', 'csv').exit_code == 2
    assert run('--grid', 'medium').exit_code == 2
