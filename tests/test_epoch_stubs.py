"""The Epoch id allocation and the benchmark stubs it emits (P3-S2-T07; 04 S3, 07 S2.4, 14 Phase 3).

VERIFY: "bench validate data/benchmarks/_stubs/ --tier all, and bench build renders zero stub pages.
Id allocation is manual under decision D3 and each id is a recorded human decision in the allocation
file." DONE WHEN: "Every Epoch benchmark has a ratified permanent id and an unfaceted stub at
verification_status: unreviewed that the published build refuses to render."

What a test can hold: every Epoch string allocated once, the named traps allocated as 04 S3 reads them,
no id a slug of an Epoch string, the stubs exactly the emitter's output, unfaceted and unpublished, and
the tier-2 rules that make an unratified id visible. What it cannot: the ratification itself, which is a
person's decision recorded in the allocation file.
"""
import csv
import io
import os
import re
import shutil
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import emit_epoch_stubs as E  # noqa: E402
from schema.stub import FACETS, AllocationFile, BenchmarkStub  # noqa: E402
from tools.build import artifacts  # noqa: E402
from tools.validate import tiers  # noqa: E402

SAFE = YAML(typ='safe', pure=True)


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return SAFE.load(fh)


ALLOC = AllocationFile.model_validate(load(E.ALLOCATION))
BY_EPOCH = {a.epoch: a for a in ALLOC.allocations}
META = list(csv.DictReader(io.StringIO(load(E.SOURCE)['quote_extract'])))
STUB_FILES = sorted(n for n in os.listdir(os.path.join(ROOT, E.STUBS)) if n.endswith('.yaml'))


def test_every_epoch_string_is_allocated_exactly_once():
    assert len(META) == 81                                   # reports/epoch-header-census.md: 81 rows
    assert [a.epoch for a in ALLOC.allocations] == [r['benchmark'] for r in META]    # the file's order
    assert all(a.rationale and a.proposed_by for a in ALLOC.allocations)


def test_the_named_traps_are_allocated_as_04_s3_reads_them():
    a = BY_EPOCH
    assert (a['GPQA diamond'].benchmark, a['GPQA diamond'].subset) == ('gpqa', 'gpqa#diamond')
    assert (a['MATH level 5'].benchmark, a['MATH level 5'].subset) == ('math', 'math#level-5')
    fm = [x for x in ALLOC.allocations if x.epoch.startswith('FrontierMath-') and x.epoch != 'FrontierMath-Erdos']
    assert len(fm) == 4 and {x.benchmark for x in fm} == {'frontiermath'}
    assert {(x.version, x.subset) for x in fm} == {('2025-02-28', 'frontiermath#tiers-1-3'),
                                                   ('2025-07-01', 'frontiermath#tier-4'),
                                                   ('v2', 'frontiermath#tiers-1-3'), ('v2', 'frontiermath#tier-4')}
    assert a['ARC AI2'].benchmark != a['ARC-AGI'].benchmark and 'arc-agi' not in a['ARC AI2'].benchmark
    assert (a['OSWorld 2.0'].benchmark, a['OSWorld 2.0'].version) == ('osworld', '2.0')
    assert a['OSWorld'].benchmark == 'osworld' and a['OSWorld'].version is None
    # P3-S3-T06: "METR and METR Time Horizons stay distinct"; 07 S5.4: "Prefix containment is not identity"
    assert (a['METR'].benchmark, a['METR Time Horizons'].benchmark) == ('metr', 'metr-time-horizons')
    assert a['SWE-Bench verified'].benchmark == 'swe-bench-verified'       # the id swe-bench.yaml's lineage declares
    assert a['ForecastBench'].existing and a['ForecastBench'].benchmark == 'forecastbench'


def test_no_id_is_a_slugified_epoch_string_that_encodes_more_than_a_benchmark():
    slug = lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')   # noqa: E731
    for x in ALLOC.allocations:
        if x.version or x.subset:
            assert x.benchmark != slug(x.epoch), x.epoch                # 04 S3: "never slugify"


def test_the_stubs_are_exactly_the_emitters_output():
    files = E.emit(ROOT)
    assert sorted(os.path.basename(p) for p in files) == STUB_FILES
    for rel, text in files.items():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
            assert fh.read() == text, rel
    new = {a.benchmark for a in ALLOC.allocations if not a.existing}
    assert len(files) == len(new) == 74   # 76 less mmlu (P3-S5-T02) and swe-bench-verified (P3-S5-T03), promoted


@pytest.mark.parametrize('name', STUB_FILES)
def test_each_stub_is_unfaceted_and_unreviewed(name):
    raw = load(os.path.join(E.STUBS, name))
    stub = BenchmarkStub.model_validate(raw)
    assert all(f in raw and raw[f] is None for f in FACETS)             # present, and null
    assert stub.curation.verification_status == 'unreviewed'
    assert stub.curation.sources == ['src-epoch-benchmark-data'] and stub.homepage is None


def test_a_stub_with_a_facet_is_not_a_stub():
    raw = load(os.path.join(E.STUBS, 'gsm8k.yaml'))
    raw['domain'] = {'primary': 'mathematics/arithmetic-word-problems'}
    with pytest.raises(Exception):
        BenchmarkStub.model_validate(raw)


def test_the_build_publishes_no_stub():
    result = artifacts.build(ROOT)
    assert not result.errors
    stub_ids = {n[:-5] for n in STUB_FILES}
    published = {b['id'] for b in result.corpus['entities']['benchmark']}
    assert not published & stub_ids
    assert sorted(i for _, i, why in result.excluded if why == artifacts.STUB) == sorted(stub_ids)


def test_the_stubs_validate_and_signal_until_each_id_is_ratified():
    report = tiers.run(ROOT, 'all', paths=[E.STUBS])
    assert not report.blocking
    signalled = [f for f in report.findings if f.rule == 'stub-unratified']
    assert {f.entity for f in signalled} == {n[:-5] for n in STUB_FILES}   # every id is still a proposal
    assert {(f.tier, f.severity) for f in signalled} == {(4, 'quality')}    # a pending human step, not a broken ref


def _record(tmp_path, stub_id, body):
    p = tmp_path / 'data' / 'benchmarks' / '_stubs' / (stub_id + '.yaml')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding='utf-8')
    return tiers._read(str(p), 'data/benchmarks/_stubs/%s.yaml' % stub_id)


def test_a_stub_may_not_shadow_a_curated_benchmark(tmp_path):
    with open(os.path.join(ROOT, E.STUBS, 'anli.yaml'), encoding='utf-8') as fh:
        body = fh.read().replace('id: anli', 'id: forecastbench')
    rec = _record(tmp_path, 'forecastbench', body)
    findings = tiers.stub_tier(tiers.load(ROOT) + [rec], ROOT)
    assert any(f.rule == 'stub-shadows-benchmark' and f.blocks and f.entity == 'forecastbench' for f in findings)


def test_ratifying_a_row_clears_its_warning(tmp_path):
    dst = tmp_path / E.ALLOCATION
    dst.parent.mkdir(parents=True)
    shutil.copy(os.path.join(ROOT, E.ALLOCATION), dst)
    text = dst.read_text(encoding='utf-8')
    anli = text.index('  - epoch: ANLI\n')
    head, tail = text[:anli], text[anli:]
    tail = tail.replace('    ratified_by: null\n    ratified_on: null\n',
                        "    ratified_by: a-curator\n    ratified_on: '2026-09-29'\n", 1)
    dst.write_text(head + tail, encoding='utf-8')
    findings = tiers.stub_tier(tiers.load(ROOT), str(tmp_path))
    unratified = {f.entity for f in findings if f.rule == 'stub-unratified'}
    assert 'anli' not in unratified and 'gsm8k' in unratified
    assert not [f for f in findings if f.blocks]


def test_a_stub_the_allocation_does_not_name_blocks(tmp_path):
    body = open(os.path.join(ROOT, E.STUBS, 'anli.yaml'), encoding='utf-8').read().replace('id: anli', 'id: anli-two')
    findings = tiers.stub_tier(tiers.load(ROOT) + [_record(tmp_path, 'anli-two', body)], ROOT)
    assert any(f.rule == 'stub-allocation' and f.blocks and f.entity == 'anli-two' for f in findings)
