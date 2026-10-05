"""Tests for the Epoch mapping stanzas (P3-S2-T03; 07 S2.1) and scripts/epoch_audit.py --stanzas.

The verify: "python scripts/epoch_audit.py --stanzas asserts a stanza per covered file and that each
score_column is a real header in that file." Whether the chosen column is the RIGHT one is a person's
review, recorded per stanza as reviewed_by; these tests hold what a machine can. The cases that read the
export skip where epochdl/ is absent (00 S8.1).
"""
import glob
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import epoch_audit as A  # noqa: E402
import epoch_stanzas as S  # noqa: E402
from ingest.mappings.schema import load_all  # noqa: E402

EPOCHDL = os.path.join(ROOT, 'epochdl')
needs_epoch = pytest.mark.skipif(not glob.glob(os.path.join(EPOCHDL, '*.csv')),
                                 reason='epochdl/ is not in the working tree (00 S8.1)')
STANZAS = load_all('epoch')


def test_59_committed_stanzas_load_and_none_assumes_its_scale():
    # the 59 covered files take Epoch's scale; the 21 orphans (P3-S2-T04, tests/test_orphan_stanzas.py) a URL's
    covered = [s for s in STANZAS.values() if s.scale_source == 'benchmark_metadata.csv']
    assert len(STANZAS) == 80 and len(covered) == 59
    assert sorted({s.scale for s in covered}) == [0.01, 0.1, 1.0]


def test_every_stanza_is_a_draft_until_a_person_reviews_it():
    # step 3: a reviewer handle is a person's to set; the generator never sets one
    assert all(s.reviewed_by is None for s in STANZAS.values())


def test_benchmark_refs_come_from_the_id_allocation():
    alloc = S.allocation()
    refs = {S.benchmark_ref(r) for r in alloc.values()}
    assert {s.benchmark_ref for s in STANZAS.values()} <= refs


def test_a_run_family_stanza_carries_its_logs_and_its_selection_rule():
    s = STANZAS['csv:gpqa_diamond']
    assert (s.family, s.benchmark_ref, s.score_column) == ('epoch-run', 'gpqa#diamond', 'Best score (across scorers)')
    assert s.uncertainty.column == 'stderr' and s.artifact.log_column == 'Logs' and s.date_column == 'Started at'
    assert s.conditions['selection_strategy'].const == 'best-across-scorers'


@needs_epoch
def test_the_verify_holds_over_the_export():
    problems, lines = A.check_stanzas(EPOCHDL)
    assert problems == [] and lines[0].startswith('59 covered file(s): 59 with a valid stanza')


@needs_epoch
def test_the_generator_reproduces_the_committed_stanzas():
    alloc = S.allocation()
    for m, name in S.covered(EPOCHDL):
        stanza, _, _, _ = S.draft(m, name, EPOCHDL, alloc)
        from ingest.mappings.schema import Stanza
        assert Stanza.model_validate(stanza) == STANZAS['csv:' + name[:-len('.csv')]], name


@needs_epoch
def test_no_covered_file_is_a_unit_trap():
    # Epoch's own score columns and scales put every covered file inside 0-1 (07 S2's dollars, minutes
    # and Elo are orphans, or a column the metadata does not name)
    alloc = S.allocation()
    flags = [f for m, n in S.covered(EPOCHDL) for f in S.draft(m, n, EPOCHDL, alloc)[1]]
    assert not [f for f in flags if f.startswith('UNIT')]


def test_the_check_names_a_missing_stanza_a_broken_one_and_a_wrong_column(tmp_path):
    export = tmp_path / 'export'
    export.mkdir()
    (export / 'benchmark_metadata.csv').write_text(
        'benchmark,source_file,score_column,scale\nA,a.csv,Score,1.0\nB,b.csv,Score,1.0\nC,c.csv,Score,1.0\n',
        encoding='utf-8')
    for stem in 'abc':
        (export / (stem + '.csv')).write_text('Model version,Score\nm,0.5\n', encoding='utf-8')
    maps = tmp_path / 'mappings' / 'epoch'
    maps.mkdir(parents=True)
    good = ('benchmark_ref: xx\nfamily: external-scrape\nscore_column: %s\nscale: 1.0\n'
            'scale_source: benchmark_metadata.csv\nmetric_ref: x-score\nsource_ref: src-x\n')
    (maps / 'a.yaml').write_text(good % 'Score', encoding='utf-8')
    (maps / 'b.yaml').write_text((good % 'Score').replace('scale: 1.0\n', ''), encoding='utf-8')   # no scale
    (maps / 'c.yaml').write_text(good % 'Points', encoding='utf-8')
    problems, _ = A.check_stanzas(str(export), str(tmp_path / 'mappings'))
    assert len(problems) == 2
    assert 'b.csv: the stanza does not load' in problems[0] and 'scale' in problems[0]
    assert "c.csv: score_column 'Points' is not a header" in problems[1]
    (maps / 'a.yaml').unlink()
    problems, _ = A.check_stanzas(str(export), str(tmp_path / 'mappings'))
    assert problems[0].startswith('a.csv: no stanza at ingest/mappings/epoch/a.yaml')


@needs_epoch
def test_the_generator_never_overwrites_a_reviewed_stanza(tmp_path, monkeypatch):
    rel = 'ingest/mappings/epoch/gpqa_diamond.yaml'
    path = os.path.join(ROOT, *rel.split('/'))
    before = open(path, encoding='utf-8').read()
    reviewed = before.replace('reviewed_by: null', 'reviewed_by: a-reviewer')
    monkeypatch.setattr(S, 'REPORT', str(tmp_path / 'report.md'))
    try:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(reviewed)
        assert S.main(['--dir', EPOCHDL]) == 0
        assert open(path, encoding='utf-8').read() == reviewed
    finally:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(before)
