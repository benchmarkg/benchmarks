"""scripts/failure_triage.py: routing the failure log to ADRs, homographs.yaml or Stage 4 (P1-S1-T06)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from scripts import failure_triage as T  # noqa: E402

A = '2026-09-28-cafa-001'
B = '2026-09-28-cafa-002'


def adr(root, name, evidence):
    (root / 'adr').mkdir(exist_ok=True)
    (root / 'adr' / name).write_text('# ADR\n\n## Context\n\nMentions %s in prose.\n\n## Evidence\n\n%s' % (B, evidence),
                                     encoding='utf-8')


def test_an_adr_decides_the_failures_its_evidence_names(tmp_path):
    adr(tmp_path, '0014-x.md', 'Blocking:\n- taxonomy/_failures/%s.yaml\n' % A)
    assert T.adr_map(str(tmp_path)) == {A: 'adr/0014-x.md'}          # prose outside Evidence is not a routing


def test_a_not_covered_heading_keeps_its_failures_out(tmp_path):
    adr(tmp_path, '0019-x.md', 'Blocking:\n- taxonomy/_failures/%s.yaml\n\n'
                               'Non-blocking, deliberately not covered (stays in Stage 4):\n'
                               '- taxonomy/_failures/%s.yaml\n' % (A, B))
    assert T.adr_map(str(tmp_path)) == {A: 'adr/0019-x.md'}


def test_a_failure_named_by_two_adrs_is_an_error(tmp_path):
    adr(tmp_path, '0014-x.md', '- taxonomy/_failures/%s.yaml\n' % A)
    adr(tmp_path, '0015-y.md', '- taxonomy/_failures/%s.yaml\n' % A)
    with pytest.raises(SystemExit, match='both'):
        T.adr_map(str(tmp_path))


def test_routes():
    files = {'low': {'data-properties.yaml'}, 'high': {'data-properties.yaml'},
             'planning': {'capabilities.yaml'}, 'games-planning/board-games': {'domains.yaml'}}
    assert T.route_of(A, {'kind': 'missing-term'}, {A: 'adr/0014-x.md'}, files) == ('adr', 'adr/0014-x.md')
    assert T.route_of(A, {'kind': 'collision', 'terms': ['low', 'high']}, {}, files) == ('stage-4', None)
    cross = {'kind': 'collision', 'terms': ['planning', 'games-planning/board-games']}
    assert T.route_of(A, cross, {}, files) == ('homograph', None)


def test_retriage_replaces_rather_than_appends():
    text = 'kind: collision\nblocking: false\nroute: stage-4\n'
    once = T.retriaged(text, 'adr', 'adr/0014-x.md')
    assert once == 'kind: collision\nblocking: false\nroute: adr\nadr: adr/0014-x.md\n'
    assert T.retriaged(once, 'adr', 'adr/0014-x.md') == once
    assert T.retriaged(once, 'stage-4', None) == 'kind: collision\nblocking: false\nroute: stage-4\n'
