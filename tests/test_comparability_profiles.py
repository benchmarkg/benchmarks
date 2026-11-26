"""Tests for the comparability profile lookup (P3-S10-T01; 04 S8, 02 S5, S6, S12; ADR-0029).

The verify: "bench validate taxonomy/ --tier all, plus a test asserting every benchmark resolves to exactly one
profile and that fields_material_total is read from the profile rather than from a constant. Which fields are
material to a given shape is a curation judgement recorded per profile."

"Exactly one profile" is held against tools/build/comparability.py's resolution rule (P0-S4-T06, kept by
ADR-0029 D3): each (evaluation_method, subject) pair a benchmark's facets make is listed in exactly one profile row,
and the benchmark's one resolved profile is the union of the rows its pairs hit, or the row it pins. So a benchmark
resolves to exactly one profile when every one of its pairs is in exactly one row (none unlisted, none in two), the
resolution is not the fallback, and resolving it twice gives the same material set. The done_when's other two
clauses, no global material-field count in code and no waiver without a reason (and every waiver on the quality
dashboard), are tested below too.
"""
import ast
import copy
import glob
import json
import os
import re
import shutil
import sys
from datetime import date

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema import validators as semantic  # noqa: E402
from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.conditions import FIELDS  # noqa: E402
from schema.stub import curated_benchmark_files  # noqa: E402
from schema.taxonomy import ComparabilityProfileFile, read_yaml  # noqa: E402
from tools.build import comparability as comp  # noqa: E402
from tools.report import completeness, quality  # noqa: E402
from tools.validate import tiers  # noqa: E402

PROFILES = comp.load_profiles()
ENTRIES = {os.path.basename(p)[:-5]: load_benchmark(p) for p in curated_benchmark_files(ROOT)}


def bench_doc(**overrides) -> dict:
    doc = {
        'id': 'example-bench', 'name': 'Example Bench', 'tagline': 'A benchmark used in tests.',
        'domain': {'primary': 'code/repository-scale-se'},
        'learned_entrant_evidence': [{'system': 'Some Model', 'source': 'src-example', 'observed_on': '2026-09-25'}],
        'evaluation_target': 'learned-system',
        'data': {'access': 'fully-open'},
        'homepage': 'https://example.org/',
        'curation': {'added_by': 'a-curator', 'added_on': '2026-09-25', 'last_verified': '2026-09-25',
                     'sources': ['src-example']},
    }
    doc.update(copy.deepcopy(overrides))
    return doc


def bench(**overrides) -> Benchmark:
    return Benchmark.model_validate(bench_doc(**overrides))


def problems(b: Benchmark, pf=PROFILES) -> list[str]:
    """Why `b` does not resolve to exactly one profile; empty when it does."""
    rows = {}
    for p in pf.profiles:
        for pair in p.applies_to:
            rows.setdefault(tuple(pair), []).append(p.id)
    pairs = [(m, s) for m in b.evaluation_method for s in b.designed_for_subjects]
    out = ['%s x %s is in %s' % (m, s, ', '.join(rows.get((m, s), [])) or 'no profile')
           for m, s in pairs if len(rows.get((m, s), [])) != 1]
    r = comp.resolve_profile(b, pf)
    if r.basis == 'fallback':
        out.append('resolves to the fallback (%s)' % ('no listed pair' if pairs else
                                                       'no facet pair: pin comparability.profile'))
    elif not r.profiles or len(set(r.profiles)) != len(r.profiles):
        out.append('resolves to profiles %r' % (r.profiles,))
    if comp.resolve_profile(b, pf) != r:
        out.append('resolves differently on a second call')
    return out


# ---- every benchmark resolves to exactly one profile ---------------------------------------------

def test_every_benchmark_resolves_to_exactly_one_profile():
    assert ENTRIES
    bad = {bid: problems(b) for bid, b in ENTRIES.items() if problems(b)}
    assert bad == {}


@pytest.mark.parametrize('facets, expect', [
    # an unlisted pair: the vocabulary grew and the table did not
    ({'evaluation_method': ['multiple-choice'], 'designed_for_subjects': ['physical-robot-system']},
     ['multiple-choice x physical-robot-system is in no profile', 'resolves to the fallback (no listed pair)']),
    # one listed pair hides an unlisted one from the resolver, which unions what it finds; the check does not
    ({'evaluation_method': ['multiple-choice'], 'designed_for_subjects': ['base-model', 'physical-robot-system']},
     ['multiple-choice x physical-robot-system is in no profile']),
    # an empty facet makes no pair, so only a pin resolves it
    ({'evaluation_method': ['exact-match'], 'designed_for_subjects': []},
     ['resolves to the fallback (no facet pair: pin comparability.profile)']),
    ({'evaluation_method': [], 'designed_for_subjects': ['base-model'], 'comparability': {'profile': 'llm-static-text'}},
     []),
])
def test_the_check_names_what_stops_a_benchmark_resolving(facets, expect):
    assert problems(bench(**facets)) == expect


def test_a_pair_in_two_profiles_is_refused():
    doc = read_yaml(comp.PROFILES_PATH)
    doc['profiles'][0]['applies_to'].append(list(doc['profiles'][1]['applies_to'][0]))
    with pytest.raises(ValidationError, match='more than one profile'):
        ComparabilityProfileFile.model_validate(doc)


def test_a_pair_in_two_rows_fails_the_check_even_where_the_schema_is_bypassed():
    pf = PROFILES.model_copy(deep=True)
    pf.profiles[0].applies_to.append(('execution-tests', 'agent-scaffold'))       # agentic's
    got = problems(bench(evaluation_method=['execution-tests'], designed_for_subjects=['agent-scaffold']), pf)
    assert got == ['execution-tests x agent-scaffold is in %s, agentic' % pf.profiles[0].id]


def test_only_entries_with_no_facet_pair_pin_a_profile_they_do_not_already_resolve():
    for bid, b in ENTRIES.items():
        if b.comparability.profile is None:
            continue
        pairs = {(m, s) for m in b.evaluation_method for s in b.designed_for_subjects}
        unpinned = comp.resolve_profile(b.model_copy(update={'comparability': b.comparability.model_copy(
            update={'profile': None})}))
        assert not pairs or b.comparability.profile in unpinned.profiles, bid


# ---- fields_material_total is read from the profile ----------------------------------------------

def expected_material(b: Benchmark, doc: dict) -> set:
    """The material set derived straight from the profile file's YAML, not through the resolver."""
    rows = doc['profiles']
    if b.comparability.profile:
        base = set(next(p['material'] for p in rows if p['id'] == b.comparability.profile))
    else:
        pairs = {(m, s) for m in b.evaluation_method for s in b.designed_for_subjects}
        base = {f for p in rows if pairs & {tuple(x) for x in p['applies_to']} for f in p['material']}
    return (base | set(b.comparability.material_extra)) - {w.field for w in b.comparability.material_waived}


def test_fields_material_total_counts_the_resolved_profile():
    doc = read_yaml(comp.PROFILES_PATH)
    totals = set()
    for bid, b in ENTRIES.items():
        r = comp.resolve_profile(b, PROFILES)
        assert set(r.material) == expected_material(b, doc), bid
        assert r.fields_material_total == len(r.material) > 0, bid
        totals.add(r.fields_material_total)
    assert len(totals) > 5            # per-benchmark sizes, not one number (04 S8)


def test_editing_a_profile_moves_fields_material_total_everywhere_it_is_read(tmp_path):
    for d in ('taxonomy', os.path.join('data', 'benchmarks'), os.path.join('data', 'claims'),
              os.path.join('data', 'conditions')):
        shutil.copytree(os.path.join(ROOT, d), tmp_path / d)
    before = comp.build(ROOT)
    path = tmp_path / 'taxonomy' / 'comparability-profiles.yaml'
    text = path.read_text(encoding='utf-8')
    marker = '  - id: trained-model\n'
    head, tail = text.split(marker)
    path.write_text(head + marker + tail.replace('    material:\n', '    material:\n      - hardware\n', 1),
                    encoding='utf-8')
    after = comp.build(str(tmp_path))
    on_row = {bid for bid, r in before['profiles'].items() if 'trained-model' in r['profiles']}
    assert on_row and len(on_row) < len(before['profiles'])
    for bid, r in before['profiles'].items():
        grew = bid in on_row and 'hardware' not in r['material']
        assert after['profiles'][bid]['fields_material_total'] == r['fields_material_total'] + grew, bid
    # the claims' denominators follow, in the build and in `bench report completeness`
    rows = completeness.build(str(tmp_path))['rows']
    assert rows
    for row in rows:
        assert row['fields_material_total'] == after['profiles'][row['benchmark'].split('@')[0]]['fields_material_total']
    assert any(row['benchmark'].split('@')[0] in on_row for row in rows)


CODE_DIRS = ('tools', 'scripts', 'schema', 'ingest')


def code_files():
    for d in CODE_DIRS:
        yield from sorted(glob.glob(os.path.join(ROOT, d, '**', '*.py'), recursive=True))


def global_counts(source: str) -> list[str]:
    """A material-field count or list written into code: `fields_material_total` (or a `*material*` name) given a
    number literal, or a literal list of four or more EvalConditions field names."""
    out = []
    for node in ast.walk(ast.parse(source)):
        pairs = []
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            pairs = [(t.id if isinstance(t, ast.Name) else getattr(t, 'attr', None), node.value) for t in targets]
        elif isinstance(node, ast.keyword):
            pairs = [(node.arg, node.value)]
        elif isinstance(node, ast.Dict):
            pairs = [(k.value if isinstance(k, ast.Constant) else None, v) for k, v in zip(node.keys, node.values)]
        for name, value in pairs:
            if isinstance(name, str) and 'material' in name.lower() and isinstance(value, ast.Constant) \
                    and isinstance(value.value, int) and not isinstance(value.value, bool):
                out.append('line %d: %s = %r' % (node.lineno, name, value.value))
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            names = [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(names) >= 4 and len(names) == len(node.elts) and set(names) <= set(FIELDS):
                out.append('line %d: a literal list of condition fields %s' % (node.lineno, names))
    return out


def test_no_code_carries_a_global_material_field_count():
    found = {os.path.relpath(p, ROOT): global_counts(open(p, encoding='utf-8').read()) for p in code_files()}
    assert {k: v for k, v in found.items() if v} == {}


@pytest.mark.parametrize('source', [
    'MATERIAL_FIELDS = 16\n',
    'row = {"fields_material_total": 11}\n',
    'render(fields_material_total=6)\n',
    'MATERIAL = ["shots", "chain_of_thought", "reasoning_effort", "tools_allowed"]\n',
])
def test_the_scan_catches_a_count_or_a_list(source):
    assert global_counts(source)


def test_the_scan_passes_a_count_read_off_the_resolution():
    assert global_counts('total = resolution.fields_material_total\nn = len(material)\nk = 3\n') == []


# ---- the basis is recorded per profile -----------------------------------------------------------

def test_every_profile_records_its_basis():
    lines = open(comp.PROFILES_PATH, encoding='utf-8').read().split('\n')
    seen = []
    for i, line in enumerate(lines):
        m = re.match(r'^  - id: ([a-z0-9-]+)$', line)
        if not m:
            continue
        j = i - 1
        while j >= 0 and lines[j].startswith('  #'):
            j -= 1
        block = '\n'.join(lines[j + 1:i])
        assert '# Basis:' in block, m.group(1)
        seen.append(m.group(1))
    assert seen == [p.id for p in PROFILES.profiles]


# ---- waivers: a reason each, and every one on the quality dashboard --------------------------------

WAIVERS = sorted((bid, w.field, w.reason) for bid, b in ENTRIES.items() for w in b.comparability.material_waived)


def test_no_waiver_exists_without_a_reason():
    assert WAIVERS
    assert all(reason.strip() for _, _, reason in WAIVERS)


def test_every_waiver_is_a_tier_4_finding_naming_its_field_and_reason():
    corpus = semantic.Corpus(benchmarks=dict(ENTRIES))
    found = {f.entity: f.message for f in tiers.quality_tier(corpus, tiers._taxonomy(ROOT), date.today())
             if f.rule == 'material-waived'}
    assert set(found) == {bid for bid, _, _ in WAIVERS}
    for bid, field, reason in WAIVERS:
        assert '%s (%s)' % (field, reason) in found[bid], (bid, field)


def test_the_quality_report_lists_every_waiver(monkeypatch):
    F = tiers.Finding
    fake = tiers.Report(tiers=(1, 2, 3, 4), scope='all', files=1, findings=[
        F(4, 'material-waived', 'quality', bid, None, 'm') for bid in sorted({b for b, _, _ in WAIVERS})])
    monkeypatch.setattr(tiers, 'run', lambda root: fake)
    rep = quality.build(ROOT)
    [row] = [r for r in rep['rows'] if r['rule'] == 'material-waived']
    stray = {(bid, f) for bid, b in ENTRIES.items() for f in comp.resolve_profile(b, PROFILES).stray_waivers}
    assert row['detail'] == ['%s: %s (%s)%s' % (bid, field, ' '.join(reason.split()),
                                                ' [not material]' if (bid, field) in stray else '')
                             for bid, field, reason in WAIVERS]
    assert rep['summary']['material_waivers'] == len(WAIVERS)
    assert 'detail' in rep['columns']


def test_a_waiver_of_a_field_that_was_not_material_is_marked_on_the_dashboard(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    (tmp_path / 'data' / 'benchmarks' / 'code').mkdir(parents=True)
    doc = bench_doc(evaluation_method=['multiple-choice'], designed_for_subjects=['base-model'],
                    comparability={'material_waived': [{'field': 'simulator', 'reason': 'No simulator.'},
                                                       {'field': 'shots', 'reason': 'Zero-shot by design.'}]})
    (tmp_path / 'data' / 'benchmarks' / 'code' / 'example-bench.yaml').write_text(json.dumps(doc), encoding='utf-8')
    assert quality.waivers(str(tmp_path)) == [
        {'benchmark': 'example-bench', 'field': 'shots', 'reason': 'Zero-shot by design.', 'material': True},
        {'benchmark': 'example-bench', 'field': 'simulator', 'reason': 'No simulator.', 'material': False}]
