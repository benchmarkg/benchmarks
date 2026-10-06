"""The 21 orphan files, hand-mapped (P3-S2-T04; 07 S2, 14-roadmap Phase 3).

The verify: "python scripts/epoch_audit.py --stanzas reports zero unmapped files and every stanza carries a
scale_source URL. Unit correctness is a human reading of a third-party leaderboard and is recorded per
stanza, not asserted by a test." So these tests hold what a machine can: that each orphan is mapped or
blocked-upstream, that its scale came from a URL and not from Epoch's metadata row, that the status ledger
(07 S5.5) records each one as the adapter's own Unresolved item, and that no fraction metric receives a
value outside 0-1 once scaled. Cases that read the export skip where epochdl/ is absent (00 S8.1).
"""
import csv
import glob
import hashlib
import io
import os
import sys
import zipfile

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import epoch_audit as A  # noqa: E402
import epoch_stanzas as S  # noqa: E402
from ingest.mappings.schema import load_all  # noqa: E402
from schema.entities import UnresolvedStatus, UnresolvedStatusFile  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.validate.tiers import UNRESOLVED_STATUS, kind_of  # noqa: E402

EPOCHDL = os.path.join(ROOT, 'epochdl')
needs_epoch = pytest.mark.skipif(not glob.glob(os.path.join(EPOCHDL, '*.csv')),
                                 reason='epochdl/ is not in the working tree (00 S8.1)')
LEDGER = os.path.join(ROOT, 'data', '_ingest', 'unresolved', 'epoch', 'status.yaml')
ORPHANS = {
    'ale_bench_external', 'algotune_external', 'blueprint_bench_2_external', 'bool_q_external', 'btf3_external',
    'common_sense_qa_2_external', 'critpt_external', 'cursorbench_external', 'enigma_eval_external',
    'forecastbench_external', 'frontiermath_erdos', 'frontierswe_external', 'gbaeval_external', 'gdp_pdf_external',
    'live_bench_external', 'mindcube_external', 'scicode_external', 'spatialviz_bench_external',
    'vending_bench_2_external', 'video_mme_external', 'webdev_arena_external',
}
# Not fractions, so outside the 0-1 check: a rating, a speedup, dollars, an Elo, and ForecastBench's index,
# which its curated metric holds on 0-100.
NOT_FRACTIONS = {'ale_bench_external', 'algotune_external', 'vending_bench_2_external', 'webdev_arena_external',
                 'forecastbench_external'}
STANZAS = load_all('epoch')
MINE = {k[len('csv:'):]: s for k, s in STANZAS.items() if s.scale_source != 'benchmark_metadata.csv'}


def test_every_orphan_has_a_stanza_whose_scale_came_from_a_url():
    assert set(MINE) == ORPHANS
    assert all(s.scale_source.startswith('https://') for s in MINE.values())


def test_the_benchmark_refs_are_the_allocated_ones():
    alloc = S.allocation()
    assert {s.benchmark_ref for s in MINE.values()} <= {S.benchmark_ref(r) for r in alloc.values()}


def test_none_is_marked_reviewed_by_the_agent_that_drafted_it():
    assert all(s.reviewed_by is None for s in MINE.values())


def test_the_unit_traps_07_names_are_mapped_to_their_unbounded_metrics():
    assert (MINE['vending_bench_2_external'].metric_ref, MINE['vending_bench_2_external'].scale) == (
        'vending-bench-2-money-balance', 1.0)
    assert (MINE['webdev_arena_external'].metric_ref, MINE['webdev_arena_external'].scale) == ('webdev-arena-score', 1.0)
    for stem in ('vending_bench_2_external', 'webdev_arena_external'):
        metric = read_yaml(os.path.join(ROOT, 'data', 'metrics', MINE[stem].metric_ref + '.yaml'))
        assert metric['unbounded'] is True


def test_livebench_is_the_trap_epochs_metadata_hides():
    # benchmark_metadata.csv says 1.0 for LiveBench; the column is 0-100
    assert MINE['live_bench_external'].scale == 0.01


def test_forecastbench_keeps_its_curated_0_to_100_index():
    metric = read_yaml(os.path.join(ROOT, 'data', 'metrics', 'forecastbench-brier-index.yaml'))
    assert MINE['forecastbench_external'].metric_ref == 'forecastbench-brier-index'
    assert (metric['range'], MINE['forecastbench_external'].scale) == ({'min': 0, 'max': 100}, 1.0)


def test_artificial_analysis_scicode_is_not_the_curated_main_problem_metric():
    # sub-problem accuracy with background (P3-S5-T04 curated main problems without it)
    assert MINE['scicode_external'].metric_ref == 'scicode-subproblem-pass-at-1'


# ---- the status ledger (07 S5.5) ------------------------------------------------------------------------

def ledger():
    return UnresolvedStatusFile.model_validate(read_yaml(LEDGER)).root


def test_the_ledger_has_one_resolved_row_per_orphan_naming_its_stanza():
    rows = [r for r in ledger() if (r.source_key or '').startswith('csv:')]     # the ledger holds other items too
    assert {r.source_key for r in rows} == {'csv:' + o for o in ORPHANS}
    assert all(r.status == 'resolved' and r.field == '*' for r in rows)
    assert all('ingest/mappings/epoch/%s.yaml' % r.source_key[4:] in r.note for r in rows)


def test_the_validator_reads_status_yaml_as_the_ledger_not_as_a_batch():
    assert kind_of('data/_ingest/unresolved/epoch/status.yaml') is UNRESOLVED_STATUS
    assert kind_of('data/_ingest/unresolved/epoch/2026-09-28.yaml').name == 'unresolved'


ROW = dict(fingerprint='0' * 16, observed='x.csv', field='*', status='open', first_seen='2026-10-01',
           last_seen='2026-10-02', occurrences=1)


def test_a_blocked_item_says_why_and_when():
    with pytest.raises(ValidationError, match='says why'):
        UnresolvedStatus.model_validate({**ROW, 'status': 'blocked-upstream', 'decided_on': '2026-10-02'})
    with pytest.raises(ValidationError, match='decided_on'):
        UnresolvedStatus.model_validate({**ROW, 'status': 'blocked-upstream', 'note': 'no public leaderboard'})
    UnresolvedStatus.model_validate({**ROW, 'status': 'blocked-upstream', 'note': 'no public leaderboard',
                                     'decided_on': '2026-10-02'})


def test_a_ledger_row_is_checked_against_its_source_key_and_its_dates():
    with pytest.raises(ValidationError, match='fingerprint'):
        UnresolvedStatus.model_validate({**ROW, 'source_key': 'csv:x'})
    with pytest.raises(ValidationError, match='before first_seen'):
        UnresolvedStatus.model_validate({**ROW, 'last_seen': '2026-09-30'})
    with pytest.raises(ValidationError, match='two rows'):
        UnresolvedStatusFile.model_validate([ROW, ROW])


# ---- over the export --------------------------------------------------------------------------------------

@needs_epoch
def test_the_verify_holds_over_the_export():
    problems, lines = A.check_stanzas(EPOCHDL)
    assert problems == []
    assert '21 orphan file(s): 21 hand-mapped, 0 blocked-upstream, 0 unmapped' in lines


@needs_epoch
def test_each_ledger_row_is_the_adapters_own_unresolved_item():
    from ingest.adapters.base import Candidate
    from ingest.adapters.epoch import ZipBundle, normalise
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for o in ORPHANS:
            z.write(os.path.join(EPOCHDL, o + '.csv'), o + '.csv')
    bundle = ZipBundle(buf.getvalue())
    for r in (r for r in ledger() if (r.source_key or "").startswith("csv:")):   # the orphan rows
        _, [u] = normalise(Candidate(r.source_key, 'claim', None, {}), bundle)
        assert (u.fingerprint, u.observed) == (r.fingerprint, r.observed), r.source_key


@needs_epoch
@pytest.mark.parametrize('stem', sorted(ORPHANS - NOT_FRACTIONS))
def test_a_fraction_metric_gets_values_inside_0_1_once_scaled(stem):
    s = MINE[stem]
    with open(os.path.join(EPOCHDL, stem + '.csv'), encoding='utf-8', newline='') as f:
        cells = [r[s.score_column].strip() for r in csv.DictReader(f)]
    values = [float(c) * s.scale for c in cells if c]
    assert values and 0 <= min(values) and max(values) <= 1.0


# ---- the check itself, on a fixture -----------------------------------------------------------------------

GOOD = ('benchmark_ref: xx\nfamily: external-scrape\nscore_column: Score\nscale: 1.0\n'
        'scale_source: %s\nmetric_ref: x-score\nsource_ref: src-x\n')


def test_the_check_tells_mapped_blocked_and_unmapped_apart(tmp_path):
    # a: mapped from a URL; b: an orphan's scale taken from the metadata; c: blocked-upstream; d: nothing
    export = tmp_path / 'export'
    export.mkdir()
    (export / 'benchmark_metadata.csv').write_text('benchmark,source_file,score_column,scale\n', encoding='utf-8')
    for stem in 'abcd':
        (export / (stem + '.csv')).write_text('Model version,Score\nm,0.5\n', encoding='utf-8')
    maps = tmp_path / 'mappings' / 'epoch'
    maps.mkdir(parents=True)
    (maps / 'a.yaml').write_text(GOOD % 'https://example.org/leaderboard', encoding='utf-8')
    (maps / 'b.yaml').write_text(GOOD % 'benchmark_metadata.csv', encoding='utf-8')
    status = tmp_path / 'status.yaml'
    status.write_text(
        '- fingerprint: %s\n  source_key: csv:c\n  observed: x\n  field: "*"\n  status: blocked-upstream\n'
        '  first_seen: 2026-10-05\n  last_seen: 2026-10-05\n  occurrences: 1\n  note: no public leaderboard\n'
        '  decided_on: 2026-10-05\n' % hashlib.sha256(b'csv:c|*|x').hexdigest()[:16], encoding='utf-8')
    problems, lines = A.check_orphans(str(export), str(tmp_path / 'mappings'), [], str(status))
    assert lines == ['4 orphan file(s): 2 hand-mapped, 1 blocked-upstream, 1 unmapped']
    assert len(problems) == 2
    assert problems[0].startswith("b.csv: an orphan's scale cannot come from benchmark_metadata.csv")
    assert problems[1].startswith('d.csv: an orphan with no stanza and no blocked-upstream row')
