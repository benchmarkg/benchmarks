"""Tests for the deterministic pack layout and atlas.json (P2-S5-T01; tools/atlas/pack.py, tools/atlas/emit.py; 10 V1,
08 S4.2, S5.3).

The verify: "uv run bench build --atlas --out build/ && uv run pytest tests/atlas/test_pack_deterministic.py", done
when "atlas.json carries the full field set and two runs of the pack layout are byte-identical".

No entry is published yet (05 S4), so `bench build --atlas` over the repository writes an empty atlas. These tests lay
out tests/fixtures/corpus-20/ -- P2-S1-T02's frozen twenty entries, one per domain family plus kaggle-game-arena,
three of them (critpt, scicode, mmlu) with a system's claim -- built as the draft preview builds it (`drafts=True`,
scripts/preview_corpus.py), so the frozen fixture, not the live drafts, is what they pin. The CLI test builds
tests/build/fixtures/minimal/, whose one curator-reviewed entry is published. Packing at a larger scale is tested on a
synthetic tree, and edge rules on records built here, because no two fixture entries are related.

What is asserted: byte-identical output across two runs, across two fresh interpreters with different hash seeds and
across a shuffled input order; the exact bits of one synthetic layout, pinned, which is what makes a run on another
platform that computes other bits fail; that pack.py's arithmetic is only the correctly rounded IEEE operations; the
field set; containment and spacing at every level; the radius rule and adoption_n against derived/adoption.json; the
containment order; the edge rules; the epoch, basis and method fields; the honest empty atlas; domain-group ids in
atlas.json, where 9h permits them; and `bench build --atlas` writing it.
"""
import ast
import copy
import hashlib
import json
import math
import os
import random
import subprocess
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli  # noqa: E402
from tools.atlas import emit, pack  # noqa: E402
from tools.build import adoption, artifacts  # noqa: E402
from tools.build.emit import serialise, taxonomy  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
CHECK = os.path.join(ROOT, 'scripts', 'check_display_only_vocab.py')
PACK_PY = os.path.join(ROOT, 'tools', 'atlas', 'pack.py')
TOL = 0.003           # three values each rounded to 3 places

# 10 V1's per-node fields plus 08 S4.2's `cluster`, written out here so the test pins the plan, not the emitter.
NODE = {'id', 'x', 'y', 'r', 'cluster', 'domain_primary', 'domain_group', 'lifecycle', 'headroom_consumed',
        'adoption_n', 'label', 'label_priority'}
EDGE = {'from', 'to', 'kind', 'coefficient', 'source'}
REGION = {'id', 'level', 'parent', 'label', 'x', 'y', 'r'}
ENVELOPE = {'artifact', 'format', 'layout_method', 'layout_epoch', 'basis_version', 'vocabularies', 'adoption_basis',
            'nodes', 'edges', 'regions'}
# The bits of synthetic()'s layout, as laid out when this test was written. A change to pack.py that moves one bit
# fails here; so does a platform whose arithmetic disagrees, which is the cross-platform half of the claim.
PINNED = '7f1ede3f9861f6cc0a4383d1d993aa211ee56b3485fdbd6707831643fe2ba19a'


@pytest.fixture(scope='module')
def built():
    """The fixture as the draft preview builds it, and its atlas, once."""
    result = artifacts.build(FIXTURE, drafts=True)
    assert result.errors == []
    return result, emit.build(result.corpus, FIXTURE)


def synthetic() -> pack.Node:
    """Three groups of uneven families of uneven leaves, the radii exact binary fractions: 58 leaves in all."""
    groups = []
    for g in range(3):
        families = []
        for f in range(g + 2):
            leaves = [pack.Node('g%d-f%d-l%d' % (g, f, i), r=1.0 + ((g * 7 + f * 5 + i * 3) % 9) / 4)
                      for i in range(3 + 2 * f + g)]
            families.append(pack.Node('g%d-f%d' % (g, f), padding=0.5, children=leaves))
        groups.append(pack.Node('g%d' % g, padding=2.0, children=families))
    return pack.Node('root', padding=4.0, children=groups)


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)


def bits(root: pack.Node) -> str:
    lines = ['%s %s %s %s' % (n.id, n.x.hex(), n.y.hex(), n.r.hex()) for n in walk(root)]
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()


def gap(a, b) -> float:
    """The distance between two circles' edges; negative when they overlap."""
    return math.sqrt((a['x'] - b['x']) ** 2 + (a['y'] - b['y']) ** 2) - a['r'] - b['r']


def slack(child, parent) -> float:
    """How far inside its parent a circle sits; negative when it pokes out."""
    return parent['r'] - math.sqrt((child['x'] - parent['x']) ** 2 + (child['y'] - parent['y']) ** 2) - child['r']


def circle(n: pack.Node) -> dict:
    return {'x': n.x, 'y': n.y, 'r': n.r}


# ---- byte-identical across runs, interpreters, input orders and platforms ------------------------------------------

def test_two_runs_are_byte_identical(built):
    result, atlas = built
    again = emit.build(copy.deepcopy(result.corpus), FIXTURE)
    assert serialise(again) == serialise(atlas)
    assert serialise(atlas).endswith(b'\n') and b'\r' not in serialise(atlas)


def test_fresh_interpreters_with_different_hash_seeds_agree(built, tmp_path):
    result, atlas = built
    corpus = tmp_path / 'corpus.json'
    corpus.write_bytes(serialise(result.corpus))
    code = ('import hashlib, json, sys; sys.path.insert(0, sys.argv[1]); from tools.atlas import emit; '
            'corpus = json.load(open(sys.argv[2], encoding="utf-8")); '
            'print(hashlib.sha256(emit.serialise(emit.build(corpus, sys.argv[3]))).hexdigest())')
    digests = set()
    for seed in ('0', '2026'):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONUTF8='1')
        out = subprocess.run([sys.executable, '-c', code, ROOT, str(corpus), FIXTURE], capture_output=True, text=True,
                             env=env, check=True)
        digests.add(out.stdout.strip())
    assert digests == {hashlib.sha256(serialise(atlas)).hexdigest()}


def test_input_order_never_reaches_the_bytes(built):
    """The fixture, and the fixture with two unclaimed copies of every entry beside it -- so that every subdomain
    holds several benchmarks and adoption ties are broken -- each laid out from a shuffled record order."""
    result, atlas = built
    crowded = copy.deepcopy(result.corpus)
    for b in result.corpus['entities']['benchmark']:
        for n in (1, 2):
            crowded['entities']['benchmark'].append(dict(copy.deepcopy(b), id='%s-copy-%d' % (b['id'], n)))
    crowded_bytes = serialise(emit.build(crowded, FIXTURE))
    rng = random.Random(20261118)
    for corpus, expect in ((result.corpus, serialise(atlas)), (crowded, crowded_bytes)):
        shuffled = copy.deepcopy(corpus)
        rng.shuffle(shuffled['entities']['benchmark'])
        for b in shuffled['entities']['benchmark']:
            for v in (b['lineage'] or {}).values():
                if isinstance(v, list):
                    rng.shuffle(v)
        assert serialise(emit.build(shuffled, FIXTURE)) == expect
    assert len(json.loads(crowded_bytes)['nodes']) == 60


def test_the_layout_of_a_fixed_tree_is_pinned_bit_for_bit():
    a, b = pack.pack(synthetic()), pack.pack(synthetic())
    assert bits(a) == bits(b) == PINNED


def test_pack_uses_only_correctly_rounded_arithmetic():
    """The cross-platform claim in pack.py's docstring, held to the code: math.sqrt is its only math function, and it
    never raises to a power, sums floats with sum(), or reaches for randomness, hashing or a clock."""
    with open(PACK_PY, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported - {'annotations', 'dataclass', 'field'} == {'math'} and modules == {'__future__', 'dataclasses'}
    assert {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name) and n.value.id == 'math'} == {'sqrt'}
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, ast.Pow)]
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {'sum', 'pow', 'hash', 'round', 'id', 'set', 'frozenset'}


# ---- the field set ----------------------------------------------------------------------------------------------

def test_atlas_json_carries_the_full_field_set(built):
    _, atlas = built
    assert set(atlas) == ENVELOPE | {'drafts'} and atlas['drafts'] is True
    assert (atlas['artifact'], atlas['format'], atlas['layout_method']) == ('atlas', 1, 'pack')
    assert atlas['layout_epoch'] == 0 and atlas['basis_version'] is None
    assert atlas['vocabularies'] == artifacts.vocabulary_versions()
    assert atlas['adoption_basis']['tiers'] == ['curated', 'machine-ingested']
    assert len(atlas['nodes']) == 20 and all(set(n) == NODE for n in atlas['nodes'])
    assert all(set(r) == REGION for r in atlas['regions'])
    assert set(emit.NODE) == NODE and set(emit.EDGE) == EDGE and set(emit.REGION) == REGION
    ids = [n['id'] for n in atlas['nodes']]
    assert ids == sorted(ids, key=lambda i: i.encode('utf-8'))
    for n in atlas['nodes']:
        assert all(isinstance(n[k], float) and n[k] == round(n[k], 3) for k in ('x', 'y', 'r'))
        assert n['headroom_consumed'] is None and isinstance(n['adoption_n'], int)
        assert n['label'] and n['lifecycle'] in {t.id for t in taxonomy()['lifecycle.yaml'].terms} | {None}


def test_nodes_carry_their_record_and_taxonomy_values(built):
    result, atlas = built
    records = {b['id']: b for b in result.corpus['entities']['benchmark']}
    group_of = {f: g.id for g in taxonomy()['domain_groups.yaml'].groups for f in g.members}
    for n in atlas['nodes']:
        b = records[n['id']]
        assert n['domain_primary'] == b['domain']['primary']
        assert n['cluster'] == b['domain']['primary'].split('/')[0]
        assert n['domain_group'] == group_of[n['cluster']]
        assert (n['label'], n['lifecycle']) == (b['name'], b['lifecycle'])


# ---- geometry ------------------------------------------------------------------------------------------------------

def test_every_circle_sits_inside_its_region_and_apart_from_its_siblings(built):
    _, atlas = built
    pad = emit.PADDING
    regions = {(r['level'], r['id']): r for r in atlas['regions']}
    groups = [r for r in atlas['regions'] if r['level'] == 'group']
    families = [r for r in atlas['regions'] if r['level'] == 'family']
    assert {r['id'] for r in families} == {n['cluster'] for n in atlas['nodes']}
    for n in atlas['nodes']:
        assert slack(n, regions[('family', n['cluster'])]) >= pad['family'] + pad['subdomain'] - TOL
    for f in families:
        assert slack(f, regions[('group', f['parent'])]) >= pad['group'] - TOL
    for level, items, apart in (('group', groups, pad['root']), ('node', atlas['nodes'], pad['subdomain'])):
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                assert gap(a, b) >= apart - TOL, (level, a['id'], b['id'])
    for i, a in enumerate(families):
        for b in families[i + 1:]:
            if a['parent'] == b['parent']:
                assert gap(a, b) >= pad['group'] - TOL, (a['id'], b['id'])


def test_a_larger_tree_packs_without_overlap_and_inside_every_parent():
    root = pack.pack(synthetic())
    for parent in walk(root):
        for i, c in enumerate(parent.children):
            assert slack(circle(c), circle(parent)) >= parent.padding - 1e-6
            for d in parent.children[i + 1:]:
                assert gap(circle(c), circle(d)) >= parent.padding - 1e-6
    assert [n.r for n in walk(root) if not n.children] == [n.r for n in walk(synthetic()) if not n.children]


def test_siblings_are_tight_not_merely_apart():
    """Each circle after the first touches an earlier one (front-chain packing), and the parent hugs its children."""
    root = pack.pack(synthetic())
    for parent in walk(root):
        cs = parent.children
        for i in range(1, len(cs)):
            assert min(abs(gap(circle(cs[i]), circle(cs[j])) - parent.padding) for j in range(i)) < 1e-6
        if cs:
            assert min(slack(circle(c), circle(parent)) - parent.padding for c in cs) < 1e-6


# ---- radius, adoption and order ------------------------------------------------------------------------------------

def test_radius_is_log_scaled_adoption():
    assert [emit.radius(n) for n in (0, 1, 5, 10, 100)] == [1.0, 1.693, 2.792, 3.398, 5.615]
    rs = [emit.radius(n) for n in range(0, 3000)]
    assert rs == sorted(rs) and len(set(rs)) > 2000


def test_adoption_n_is_derived_adoption_jsons_systems(built):
    _, atlas = built
    systems = {row['id']: row['systems'] for row in adoption.build(FIXTURE)['benchmarks']}
    assert {n['id']: n['adoption_n'] for n in atlas['nodes']} == {n['id']: systems[n['id']] for n in atlas['nodes']}
    assert {n['id']: n['adoption_n'] for n in atlas['nodes'] if n['adoption_n']} == {'critpt': 5, 'mmlu': 1, 'scicode': 5}
    for n in atlas['nodes']:
        assert n['r'] == emit.radius(n['adoption_n'])


def test_label_priority_ranks_by_adoption_then_id(built):
    _, atlas = built
    ranked = sorted(atlas['nodes'], key=lambda n: (-n['adoption_n'], n['id'].encode('utf-8')))
    assert [n['label_priority'] for n in ranked] == list(range(1, len(ranked) + 1))


def test_regions_follow_the_declared_group_order_and_carry_no_count(built):
    _, atlas = built
    declared = [g.id for g in taxonomy()['domain_groups.yaml'].groups]
    members = {g.id: list(g.members) for g in taxonomy()['domain_groups.yaml'].groups}
    groups = [r['id'] for r in atlas['regions'] if r['level'] == 'group']
    assert groups == [g for g in declared if g in groups] and len(groups) == 6     # corpus-20 spans every family
    for g in groups:
        fams = [r['id'] for r in atlas['regions'] if r['parent'] == g]
        assert fams == [f for f in members[g] if f in fams]
    labels = {r['id']: r['label'] for r in atlas['regions']}
    assert labels['symbolic-formal'] == 'Symbolic and formal' and labels['code'] == 'Code'
    assert atlas['regions'][0]['level'] == 'group' and atlas['regions'][0]['parent'] is None


def test_one_subdomains_benchmarks_pack_by_adoption_then_id():
    benchmarks = [{'id': i, 'domain': {'primary': 'code/bug-repair'}} for i in ('b-bench', 'a-bench', 'c-bench')]
    laid = emit.tree(benchmarks, {'a-bench': 0, 'b-bench': 0, 'c-bench': 3})
    sub = laid.children[0].children[0].children[0]
    assert sub.id == 'code/bug-repair' and [c.id for c in sub.children] == ['c-bench', 'a-bench', 'b-bench']


def test_an_unknown_subdomain_refuses():
    with pytest.raises(emit.AtlasError, match='not a subdomain'):
        emit.tree([{'id': 'x', 'domain': {'primary': 'code/no-such-subdomain'}}], {'x': 0})


# ---- edges ---------------------------------------------------------------------------------------------------------

def rec(ident, **lineage):
    return {'id': ident, 'lineage': lineage or None}


def test_lineage_edges_read_the_schema_fields_once_each():
    records = [rec('a', supersedes=['b'], subset_of='c', decontaminates='d'), rec('b', superseded_by=['a']),
               rec('c', extended_by=['e']), rec('d'), rec('e')]
    got = [(e['from'], e['to'], e['kind']) for e in emit.edges(records, {'a', 'b', 'c', 'd', 'e'})]
    assert got == [('a', 'b', 'supersedes'), ('a', 'c', 'subset_of'), ('a', 'd', 'decontaminates'),
                   ('e', 'c', 'extends')]
    assert all(e['coefficient'] is None and e['source'] is None for e in emit.edges(records, {'a', 'b', 'c', 'd', 'e'}))


def test_a_correlation_is_drawn_only_where_its_coefficient_has_a_source():
    records = [rec('a', correlates_with=[{'benchmark': 'b', 'coefficient': 0.81, 'source': 'src-x'},
                                         {'benchmark': 'c', 'coefficient': 0.5, 'source': None},
                                         {'benchmark': 'd', 'coefficient': None, 'source': 'src-y'}]),
               rec('b', correlates_with=[{'benchmark': 'a', 'coefficient': 0.81, 'source': 'src-x'}]), rec('c'), rec('d')]
    assert emit.edges(records, {'a', 'b', 'c', 'd'}) == [
        {'from': 'a', 'to': 'b', 'kind': 'correlates_with', 'coefficient': 0.81, 'source': 'src-x'}]


def test_an_edge_needs_two_nodes(built):
    records = [rec('a', supersedes=['gone', 'a'], correlates_with=[{'benchmark': 'gone', 'coefficient': 0.9,
                                                                     'source': 'src-x'}])]
    assert emit.edges(records, {'a'}) == []
    _, atlas = built
    assert atlas['edges'] == []          # mmlu's only lineage, extended_by mmlu-pro, ends on an entry not in the fixture


# ---- the epoch, the empty atlas, the display-only check, the CLI ---------------------------------------------------

def test_an_epoch_ledger_nothing_reads_refuses(tmp_path):
    assert emit.layout_epoch(str(tmp_path)) == 0
    (tmp_path / 'atlas').mkdir()
    (tmp_path / 'atlas' / 'atlas_epoch.yaml').write_text('epochs: []\n', encoding='utf-8')
    with pytest.raises(emit.AtlasError, match='atlas_epoch.yaml exists'):
        emit.layout_epoch(str(tmp_path))


def test_the_published_atlas_is_honestly_empty():
    """05 S4 publishes no draft, and every fixture entry is one: the envelope, and nothing in it."""
    published = artifacts.build(FIXTURE)
    assert published.errors == [] and published.corpus['entities']['benchmark'] == []
    atlas = emit.build(published.corpus, FIXTURE)
    assert set(atlas) == ENVELOPE and (atlas['nodes'], atlas['edges'], atlas['regions']) == ([], [], [])
    assert atlas['layout_method'] == 'pack' and atlas['layout_epoch'] == 0


def test_domain_group_ids_are_in_atlas_json_and_9h_permits_them(built, tmp_path):
    result, atlas = built
    artifacts.write(result, str(tmp_path))
    emit.write(atlas, str(tmp_path))
    groups = {g.id for g in taxonomy()['domain_groups.yaml'].groups}
    assert {n['domain_group'] for n in atlas['nodes']} == groups
    run = subprocess.run([sys.executable, CHECK, '--artifacts', str(tmp_path)], capture_output=True, text=True,
                         encoding='utf-8')
    assert run.returncode == 0, run.stdout + run.stderr


def test_bench_build_atlas_writes_it_and_twice_writes_the_same_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    runner, outs = CliRunner(), []
    for name in ('one', 'two'):
        res = runner.invoke(cli.app, ['build', '--atlas', '--out', str(tmp_path / name)])
        assert res.exit_code == 0, res.output
        assert 'atlas.json' in res.output
        outs.append((tmp_path / name / 'atlas.json').read_bytes())
    assert outs[0] == outs[1]
    atlas = json.loads(outs[0])
    assert [n['id'] for n in atlas['nodes']] == ['alpha-bench'] and 'drafts' not in atlas
    assert outs[0] == serialise(emit.build(artifacts.build(MINIMAL).corpus, MINIMAL))
    manifest = json.loads((tmp_path / 'one' / 'build-manifest.json').read_text(encoding='utf-8'))
    assert 'atlas.json' in manifest['artifacts']                 # hashed and named with the other shipped artifacts
    assert any(n.startswith('atlas.') for n in os.listdir(tmp_path / 'one' / 'data'))
    res = runner.invoke(cli.app, ['build', '--out', str(tmp_path / 'plain')])
    assert res.exit_code == 0 and not (tmp_path / 'plain' / 'atlas.json').exists()
    plain = json.loads((tmp_path / 'plain' / 'build-manifest.json').read_text(encoding='utf-8'))
    assert 'atlas.json' not in plain['artifacts']
