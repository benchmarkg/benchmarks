"""P1-S7-T06: the Core-seven gate, asserted against the corpus as it stands (02 S3, floor rule 2; 14 Phase 1 exit).

The verify is `python scripts/check_floor_rule.py --core-only --assert-core 130`: across the seven Core families
at least 130 entries, none below the Core floor of 18, and none carrying `coverage_status: under-surveyed` ("Muting
is not available to the seven Core families"). P1-S2-T09 built the checker and tests it on seeded fixtures
(tests/test_seed_floor_checkers.py); this file holds the gate on the real tree, so a change that thins a Core family
below its floor, or mutes one, fails here by name.

The count is scripts/seed_progress.py's, the one every floor assertion reads: every entry file under a family's
directory of data/benchmarks/, whatever its review state.
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_floor_rule as F  # noqa: E402
import seed_progress as S  # noqa: E402
from taxonomy_stats import CORE_FLOOR  # noqa: E402

GATE = 130
FAMS, _ = S.vocabulary(ROOT)
CORE = sorted(f['id'] for f in FAMS if f.get('core') is True)   # get-default: core is false unless stated


def test_the_core_set_is_the_seven_02_names():
    assert len(CORE) == 7
    assert sorted(F.named_core(ROOT)) == CORE


def test_no_core_family_is_muted():
    assert [f['id'] for f in FAMS if f.get('core') is True and F.muted(f)] == []   # get-default: as above


def test_every_core_family_is_at_or_above_its_floor():
    c = S.counts(ROOT)
    below = {fam: c[fam] for fam in CORE if c[fam] < CORE_FLOOR}
    assert below == {}, below


def test_the_core_families_total_at_least_the_gate():
    c = S.counts(ROOT)
    assert sum(c[fam] for fam in CORE) >= GATE


def test_the_verify_passes(capsys):
    assert F.main(['--core-only', '--assert-core', str(GATE)]) == 0
    assert capsys.readouterr().out.startswith('OK ')


def test_a_core_family_one_below_its_floor_fails_by_name(monkeypatch, capsys):
    real = S.counts(ROOT)
    thin = min(CORE, key=lambda fam: (real[fam], fam))
    fewer = Counter(real)
    fewer[thin] = CORE_FLOOR - 1
    monkeypatch.setattr(F.S, 'counts', lambda root=None: fewer)
    assert F.main(['--core-only', '--assert-core', str(GATE)]) == 1
    out = capsys.readouterr().out
    assert '%s (Core) has %d, below the Core floor of %d' % (thin, CORE_FLOOR - 1, CORE_FLOOR) in out


def test_a_core_total_below_the_gate_fails():
    real = S.counts(ROOT)
    total = sum(real[fam] for fam in CORE)
    assert F.main(['--core-only', '--assert-core', str(total + 1)]) == 1
    assert F.main(['--core-only', '--assert-core', str(total)]) == 0
