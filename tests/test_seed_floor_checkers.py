"""Tests for scripts/seed_progress.py and scripts/check_floor_rule.py (P1-S2-T09; 02 S3, 14 Phase 1 exit).

The verify: `python scripts/seed_progress.py --check && python scripts/check_floor_rule.py`. Done when "both
scripts run green on the current corpus and fail on a seeded violation fixture". Each fixture below copies
taxonomy/domains.yaml and 02 into a tree, writes entries, and seeds one violation.
"""
import os
import shutil
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_floor_rule as F  # noqa: E402
import seed_progress as S  # noqa: E402

FAMS, SUBS = S.vocabulary(ROOT)
BIO = SUBS['biology-genetics'][0]          # a real subdomain, whatever the vocabulary calls it
CORE = [f['id'] for f in FAMS if f.get('core') is True]
NON_CORE = [f['id'] for f in FAMS if f.get('core') is not True]


@pytest.fixture
def tree(tmp_path):
    for rel in (S.DOMAINS, F.PLAN_02):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    return tmp_path


def entry(root, ident, primary, directory=None, secondary=(), **extra):
    d = root / 'data' / 'benchmarks' / (directory or primary.split('/')[0])
    d.mkdir(parents=True, exist_ok=True)
    domain = {'primary': primary, 'secondary': list(secondary)}
    (d / (ident + '.yaml')).write_text(yaml.safe_dump(dict({'id': ident, 'domain': domain}, **extra)),
                                       encoding='utf-8')


def fill(root, family, n, start=0):
    sub = SUBS[family][0]
    for i in range(start, start + n):
        entry(root, '%s-%03d' % (family, i), sub)


def set_family(root, family, **fields):
    path = root / S.DOMAINS
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    next(t for t in doc['terms'] if t['id'] == family).update(fields)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')


def launch_ready(root):
    """A corpus that passes both launch gates: every family at its floor."""
    for f in FAMS:
        fill(root, f['id'], F.floor(f))


# ---- the verify, on the current corpus -------------------------------------------------------------

def test_verify_seed_progress_check_is_green_on_the_corpus():
    assert S.main(['--check']) == 0


def test_verify_check_floor_rule_is_green_on_the_corpus():
    assert F.main([]) == 0


def test_the_corpus_counts_what_is_in_the_family_directories_and_nothing_else():
    on_disk = [p for p in os.listdir(os.path.join(ROOT, S.BENCHMARKS)) if p != '_stubs']
    n = sum(len([x for x in os.listdir(os.path.join(ROOT, S.BENCHMARKS, d)) if x.endswith('.yaml')]) for d in on_disk)
    assert sum(S.counts().values()) == n


# ---- seed_progress: what counts ----------------------------------------------------------------------

def test_stubs_are_not_published_and_do_not_count(tree):
    entry(tree, 'casp16', BIO)
    entry(tree, 'some-stub', BIO, directory='_stubs')
    assert S.counts(str(tree)) == {'biology-genetics': 1}


def test_a_subset_of_entry_is_a_benchmark_and_counts_and_the_table_names_it(tree):
    sub = SUBS['code'][0]
    entry(tree, 'swe-bench', sub)
    entry(tree, 'swe-bench-verified', sub, lineage={'subset_of': 'swe-bench'})
    assert S.counts(str(tree))['code'] == 2
    assert '(1 declare lineage.subset_of)' in S.table(str(tree))


@pytest.mark.parametrize('seed, message', [
    (lambda t: entry(t, 'casp16', BIO, directory='physics'),
     "sits in physics/ but its domain.primary %r is biology-genetics" % BIO),
    (lambda t: entry(t, 'casp16', 'biology-genetics/no-such-subdomain'), 'is not a subdomain'),
    (lambda t: entry(t, 'casp16', BIO, directory='alchemy'), 'alchemy/ is not a domain family'),
    (lambda t: (t / 'data' / 'benchmarks' / 'physics').mkdir(parents=True) or
     (t / 'data' / 'benchmarks' / 'physics' / 'x.yaml').write_text('id: y\ndomain: {primary: %s}\n' % SUBS['physics'][0]),
     "id 'y' does not match its file name"),
    (lambda t: (t / 'data' / 'benchmarks' / 'physics').mkdir(parents=True) or
     (t / 'data' / 'benchmarks' / 'physics' / 'x.yaml').write_text('id: x\n'), 'no domain.primary'),
])
def test_seed_progress_check_fails_on_a_seeded_violation(tree, seed, message, capsys):
    seed(tree)
    assert S.main(['--root', str(tree), '--check']) == 1
    assert message in capsys.readouterr().out


def test_an_id_used_twice_fails_the_check(tree):
    entry(tree, 'dup', SUBS['physics'][0])
    entry(tree, 'dup', SUBS['code'][0])
    assert any("id 'dup' is used by 2 entries" in e for e in S.check(str(tree)))


# ---- seed_progress: the assertions later tasks call -------------------------------------------------

def test_family_assert_min(tree):
    fill(tree, 'physics', 9)
    assert S.main(['--root', str(tree), '--family', 'physics', '--assert-min', '9']) == 0
    assert S.main(['--root', str(tree), '--family', 'physics', '--assert-min', '10']) == 1


def test_assert_total_and_min_families(tree):
    for f in FAMS[:12]:
        fill(tree, f['id'], 2)
    assert S.main(['--root', str(tree), '--assert-total', '20', '--assert-min-families', '12']) == 0
    assert S.main(['--root', str(tree), '--assert-total', '25']) == 1
    assert S.main(['--root', str(tree), '--assert-min-families', '13']) == 1


def test_an_unknown_family_is_a_usage_error(tree):
    assert S.main(['--root', str(tree), '--family', 'alchemy', '--assert-min', '1']) == 2


def test_subdomain_emptiness_counts_primaries_and_writes_the_figure(tree, capsys):
    a, b = SUBS['physics'][:2]
    entry(tree, 'p1', a, secondary=[b])
    out = tree / 'emptiness.json'
    assert S.main(['--root', str(tree), '--subdomain-emptiness', '--out', str(out)]) == 0
    em = yaml.safe_load(out.read_text(encoding='utf-8'))
    pairs = sum(len(v) for v in SUBS.values())
    assert em['pairs'] == pairs and em['empty_primary'] == pairs - 1 and em['empty_with_secondary'] == pairs - 2
    assert '%d of %d' % (pairs - 1, pairs) in capsys.readouterr().out


def test_the_pair_count_is_02s():
    """02 S3: "320 seed entries over 209 (family, subdomain) pairs" is generated from the same vocabulary."""
    assert S.emptiness(ROOT)['pairs'] == sum(len(v) for v in SUBS.values())


# ---- check_floor_rule: the standing invariants ----------------------------------------------------------

def test_the_core_set_is_02s_seven():
    assert sorted(F.named_core()) == sorted(CORE) and len(CORE) == 7


def test_a_muted_core_family_fails_even_with_no_flags(tree, capsys):
    set_family(tree, 'physics', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree)]) == 1
    assert 'physics is a Core family and carries coverage_status: under-surveyed' in capsys.readouterr().out


def test_a_core_set_that_drifts_from_02_fails(tree, capsys):
    set_family(tree, 'vision', core=True)
    assert F.main(['--root', str(tree)]) == 1
    assert 'the Core set in' in capsys.readouterr().out


# ---- check_floor_rule: one family, and the muting exemption --------------------------------------------

def test_family_assert_min_satisfied(tree):
    fill(tree, 'engineering-design', 12)
    assert F.main(['--root', str(tree), '--family', 'engineering-design', '--assert-min', '12',
                   '--satisfied-or-muted']) == 0


def test_a_muted_non_core_family_passes_with_satisfied_or_muted(tree, capsys):
    set_family(tree, 'engineering-design', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree), '--family', 'engineering-design', '--assert-min', '12',
                   '--satisfied-or-muted']) == 0
    assert 'is muted' in capsys.readouterr().out


def test_a_family_neither_satisfied_nor_muted_fails(tree, capsys):
    assert F.main(['--root', str(tree), '--family', 'engineering-design', '--assert-min', '12',
                   '--satisfied-or-muted']) == 1
    assert 'and it is not muted' in capsys.readouterr().out


def test_muting_without_the_flag_does_not_exempt(tree):
    set_family(tree, 'engineering-design', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree), '--family', 'engineering-design', '--assert-min', '12']) == 1


def test_a_core_family_is_never_exempted_by_muting(tree, capsys):
    set_family(tree, 'audio-speech', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree), '--family', 'audio-speech', '--assert-min', '18',
                   '--satisfied-or-muted']) == 1
    out = capsys.readouterr().out
    assert 'muting cannot exempt it' in out and 'audio-speech is a Core family' in out


def test_family_without_assert_min_reports_against_the_floor_and_passes(tree, capsys):
    fill(tree, 'engineering-design', 3)
    assert F.main(['--root', str(tree), '--family', 'engineering-design']) == 0
    assert 'engineering-design' in capsys.readouterr().out


def test_usage_errors(tree):
    with pytest.raises(SystemExit):
        F.main(['--root', str(tree), '--assert-min', '3'])
    with pytest.raises(SystemExit):
        F.main(['--root', str(tree), '--family', 'physics', '--satisfied-or-muted'])
    assert F.main(['--root', str(tree), '--family', 'alchemy']) == 2


# ---- check_floor_rule: the launch gates ----------------------------------------------------------------

def test_a_launch_ready_corpus_passes_both_gates(tree):
    launch_ready(tree)
    total = sum(F.floor(f) for f in FAMS)
    core = sum(F.floor(f) for f in FAMS if f.get('core') is True)
    assert F.main(['--root', str(tree), '--assert-total', str(total), '--assert-core', str(core)]) == 0


def test_an_empty_family_fails_the_total_gate_even_when_muted(tree, capsys):
    launch_ready(tree)
    shutil.rmtree(tree / 'data' / 'benchmarks' / 'engineering-design')
    set_family(tree, 'engineering-design', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree), '--assert-total', '1']) == 1
    assert 'engineering-design has no published entry' in capsys.readouterr().out


def test_a_thin_unmuted_family_fails_the_total_gate_and_muting_releases_it(tree, capsys):
    launch_ready(tree)
    shutil.rmtree(tree / 'data' / 'benchmarks' / 'multimodal')
    fill(tree, 'multimodal', 5)
    assert F.main(['--root', str(tree), '--assert-total', '1']) == 1
    assert 'multimodal has 5, below the hard floor of 12, and is not muted' in capsys.readouterr().out
    set_family(tree, 'multimodal', coverage_status='under-surveyed')
    assert F.main(['--root', str(tree), '--assert-total', '1']) == 0


def test_the_total_gate_counts(tree):
    launch_ready(tree)
    assert F.main(['--root', str(tree), '--assert-total', str(sum(S.counts(str(tree)).values()) + 1)]) == 1


def test_a_core_family_below_18_fails_the_core_gate(tree, capsys):
    launch_ready(tree)
    shutil.rmtree(tree / 'data' / 'benchmarks' / 'physics')
    fill(tree, 'physics', 17)
    assert F.main(['--root', str(tree), '--core-only', '--assert-core', '1']) == 1
    assert 'physics (Core) has 17, below the Core floor of 18' in capsys.readouterr().out


def test_the_core_gate_counts_only_the_core_seven(tree):
    launch_ready(tree)
    fill(tree, NON_CORE[0], 200, start=100)
    core_total = sum(S.counts(str(tree))[f] for f in CORE)
    assert F.main(['--root', str(tree), '--core-only', '--assert-core', str(core_total)]) == 0
    assert F.main(['--root', str(tree), '--core-only', '--assert-core', str(core_total + 1)]) == 1


def test_core_only_ignores_a_thin_non_core_family(tree):
    for f in CORE:
        fill(tree, f, F.CORE_FLOOR)
    assert F.main(['--root', str(tree), '--core-only', '--assert-total', '1']) == 0
    assert F.main(['--root', str(tree), '--assert-total', '1']) == 1


def test_the_floors_are_the_ones_9f_holds_the_targets_to():
    import taxonomy_stats
    assert (F.HARD_FLOOR, F.CORE_FLOOR) == (taxonomy_stats.HARD_FLOOR, taxonomy_stats.CORE_FLOOR) == (12, 18)


def test_one_implementation_of_the_count():
    assert F.S.counts is S.counts
