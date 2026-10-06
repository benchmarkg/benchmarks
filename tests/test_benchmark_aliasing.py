"""The benchmark and organisation alias tables (P3-S3-T06; 07 S5.4, 04 S10).

The done-when: "ARC AI2 never resolves to ARC-AGI, METR and METR Time Horizons stay distinct, and subset
strings resolve to a subset rather than creating an entity." The tests below hold each, against the committed
tables and ingest/resolve.py, and show the failure each guards against: the look-alikes that a token-set
matcher scores as near or perfect matches.
"""
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import matching as M  # noqa: E402
from ingest.resolve import Index  # noqa: E402
from schema.entities import Alias, AliasFile  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

BENCH = Index.load('benchmark')
ORGS = Index.load('organization')
TABLE = AliasFile.model_validate(read_yaml(os.path.join(ROOT, 'data', 'aliases', 'benchmarks.yaml'))).root


def resolve(s):
    r = BENCH.resolve(s)
    return r.entity, r.version, r.subset


def target(ident, name):
    return M.Target(ident, (ident, name), (), (), None)


# ---- the traps -------------------------------------------------------------------------------------------

def test_arc_ai2_never_resolves_to_arc_agi():
    assert resolve('ARC AI2') == ('benchmark:ai2-arc', None, None)
    assert resolve('ARC-AGI') == ('benchmark:arc-agi-1', None, None)


def test_the_arc_trap_is_real_without_the_alias_row():
    # the failure case: to 07's token-set term the two names are near-identical, and with no alias table the
    # resolver must decline rather than guess
    assert M.name_similarity('ARC AI2', target('arc-agi-1', 'ARC-AGI'), 'set') >= 0.8
    bare = Index('benchmark', BENCH.entries.values(), ())
    assert bare.resolve('ARC AI2').entity is None and bare.resolve('ARC AI2').unresolved is not None


def test_metr_and_metr_time_horizons_stay_distinct():
    assert resolve('METR') == ('benchmark:metr', None, None)
    assert resolve('METR Time Horizons') == ('benchmark:metr-time-horizons', None, None)
    # prefix containment: a token set scores the shorter name a perfect match for the longer
    assert M.name_similarity('METR', target('metr-time-horizons', 'METR Time Horizons'), 'set') == 1.0


def test_frontiermath_erdos_is_not_frontiermath():
    assert resolve('FrontierMath-Erdos') == ('benchmark:frontiermath-erdos', None, None)


@pytest.mark.parametrize('s,subset', [('GPQA diamond', 'gpqa#diamond'), ('MATH level 5', 'math#level-5')])
def test_a_subset_string_resolves_to_the_subset_not_a_new_benchmark(s, subset):
    assert resolve(s) == ('benchmark:' + subset.split('#')[0], None, subset)


def test_no_alias_creates_an_entity_out_of_a_subset():
    # every target is the allocated benchmark, and a subset slug never appears as a benchmark id
    ids = {a.entity[1] for a in TABLE}
    assert not ids & {'gpqa-diamond', 'math-level-5', 'frontiermath-tier-4', 'frontiermath-tiers-1-3'}
    for ident in ids:
        found = [p for d in ('_stubs', *os.listdir(os.path.join(ROOT, 'data', 'benchmarks')))
                 for p in [os.path.join(ROOT, 'data', 'benchmarks', d, ident + '.yaml')] if os.path.exists(p)]
        assert found, '%s is neither a curated benchmark nor a stub' % ident


@pytest.mark.parametrize('s,version,subset', [
    ('FrontierMath-2025-02-28-Private', '2025-02-28', 'frontiermath#tiers-1-3'),
    ('FrontierMath-Tier-4-2025-07-01-Private', '2025-07-01', 'frontiermath#tier-4'),
    ('FrontierMath-Tiers-1-3-v2-Private', 'v2', 'frontiermath#tiers-1-3'),
    ('FrontierMath-Tier-4-v2-Private', 'v2', 'frontiermath#tier-4'),
])
def test_frontiermath_private_decomposes_into_benchmark_version_subset_and_access(s, version, subset):
    r = BENCH.resolve(s)
    assert (r.entity, r.version, r.subset) == ('benchmark:frontiermath', version, subset)
    assert r.extracts == {'benchmark.data.access': 'private-test-server'}


def test_osworld_2_is_a_version_held_at_medium_until_a_person_decides():
    r = BENCH.resolve('OSWorld 2.0')
    assert (r.entity, r.version, r.confidence) == ('benchmark:osworld', '2.0', 'medium')
    assert BENCH.resolve('OSWorld').version is None


def test_every_row_says_why_and_agrees_with_the_id_allocation():
    alloc = {r['epoch']: r for r in read_yaml(os.path.join(ROOT, 'ingest', 'mappings', 'epoch', '_id_allocation.yaml'))['allocations']}
    for a in TABLE:
        assert a.rationale and len(a.rationale.split()) >= 8, a.alias
        row = alloc[a.alias]
        assert (a.entity[1], a.version, a.subset) == (row['benchmark'], row['version'], row['subset']), a.alias


# ---- the schema rules this task added -------------------------------------------------------------------

ROW = dict(alias='X', kind='exact', confidence='high', decided_by='someone', decided_on='2026-10-05')


def test_only_a_benchmark_alias_names_a_version_a_subset_or_an_access_mode():
    Alias.model_validate(dict(ROW, resolves_to='benchmark:frontiermath@v2#tier-4'))
    with pytest.raises(ValidationError, match='only a benchmark alias names'):
        Alias.model_validate(dict(ROW, resolves_to='system:gpt-4o@2024-08-06'))
    with pytest.raises(ValidationError, match='only a benchmark alias routes'):
        Alias.model_validate(dict(ROW, resolves_to='system:gpt-4o', extracts={'benchmark.data.access': 'fully-open'}))
    with pytest.raises(ValidationError, match='not a data.access term'):
        Alias.model_validate(dict(ROW, resolves_to='benchmark:x', extracts={'benchmark.data.access': 'private'}))


def test_the_validator_checks_an_alias_subset_as_a_subset_reference():
    from tools.validate.tiers import Record, _typed_refs, kind_of
    rec = Record.__new__(Record)
    object.__setattr__(rec, 'kind', kind_of('data/aliases/benchmarks.yaml'))
    object.__setattr__(rec, 'raw', [{'alias': 'x', 'resolves_to': 'benchmark:frontiermath@v2#tier-4'}])
    assert list(_typed_refs(rec)) == [('resolves_to', 'benchmark', 'frontiermath@v2'),
                                      ('resolves_to', 'subset:frontiermath', 'frontiermath#tier-4')]


# ---- organisations ---------------------------------------------------------------------------------------

def test_every_organisation_alias_resolves_to_its_organisation():
    table = AliasFile.model_validate(read_yaml(os.path.join(ROOT, 'data', 'aliases', 'organizations.yaml'))).root
    for a in table:
        assert ORGS.resolve(a.alias).entity == a.resolves_to, a.alias


@pytest.mark.parametrize('s', ['Google', 'DeepMind', 'Google Research', 'Microsoft', 'Salesforce'])
def test_an_organisation_never_resolves_to_its_look_alike(s):
    # Epoch keeps Google, DeepMind, Google DeepMind and Google Research apart, and Microsoft from Microsoft
    # Research: until their own records are promoted from stubs they resolve to nothing, never to the neighbour
    assert ORGS.resolve(s).entity in (None, 'organization:org-' + s.lower().replace(' ', '-'))
