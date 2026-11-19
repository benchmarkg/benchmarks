"""DCASE as one family over its task-and-year children, and Open ASR's bound pair of metrics (P3-S6-T07;
02-taxonomy.md S11 rules 4 and 5, S12.9; 04-data-model.md S4 and S6).

The verify: "bench validate --tier all, plus a test asserting each DCASE task is a child of one family and that
WER and RTFx are bound by must_report_with". Done when: "The family/child counting convention holds for the
benchmark that most stresses it, and neither Open ASR metric can render alone."

  1. One family. DCASE is one Benchmark record; no other record, curated or stub, is a DCASE edition or task,
     because every count this project publishes is a family count (02 S11 rule 5).
  2. Each task-and-year is a child. Every subset is `dcase#<year>-task<N>`, its year an edition version of the
     family (04 S4: a re-issue with new data is a version, a parallel task within one release a subset), and
     each edition has exactly as many task subsets as the events page's totals row counts
     (src-dcase-events-2026-11-19). A track under a task stays in its task's year.
  3. Cross-year comparison is refused. Every edition is a breaking `edition` version (04 S6), the editions
     chain, `versions_basis` records the annual evaluation set from a quoted Source, the comparability key of
     one task line differs in every year, and a DCASE claim must name an edition and a subset of that edition.
  4. The family counts once in the coverage matrix: no child's domain_override reaches a family the parent does
     not already declare, and no child's capability_override adds a term the parent lacks (02 S11 rule 4: the
     parent's lists are a union over its children).
  5. The Open ASR pair. open-asr-wer and open-asr-rtfx each name the other in must_report_with, so neither can
     be rendered alone (04 S6), and the Open ASR entry lists both, WER as its headline.

The year is tied to its subset by the id alone: the Subset model has no version field, so this test is what holds
the tie (the entry's review_checks say so).
"""
import glob
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import quote_found  # noqa: E402
from schema.stub import curated_benchmark_files, stub_files  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('comparability_dcase_test', os.path.join(ROOT, 'tools', 'build', 'comparability.py'))
C = importlib.util.module_from_spec(spec)
sys.modules['comparability_dcase_test'] = C
spec.loader.exec_module(C)

DCASE = os.path.join(ROOT, 'data', 'benchmarks', 'audio-speech', 'dcase.yaml')
OPEN_ASR = os.path.join(ROOT, 'data', 'benchmarks', 'audio-speech', 'open-asr-leaderboard.yaml')
EVENTS = 'src-dcase-events-2026-11-19'
# The events page's totals row, quoted by the entry's subsets from EVENTS: tasks per edition, 2013 and 2016-2026.
TASKS_PER_EDITION = {'2013': 2, '2016': 4, '2017': 4, '2018': 5, '2019': 5, '2020': 6, '2021': 6, '2022': 6,
                     '2023': 7, '2024': 10, '2025': 6, '2026': 7}
TOTALS_QUOTE = '2013 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 Totals Tasks 2 4 4 5 5 6 6 6 7 10 6 7'
CHILD = re.compile(r'^dcase#(?P<year>\d{4})-task(?P<n>\d+)(?P<track>[a-z]?)$')
WER, RTFX = 'open-asr-wer', 'open-asr-rtfx'


@pytest.fixture(scope='module')
def dcase():
    return load_benchmark(DCASE)


@pytest.fixture(scope='module')
def raw():
    return read_yaml(DCASE)


def source(sid):
    return read_yaml(os.path.join(ROOT, 'data', 'sources', '2026', sid + '.yaml'))


def metric(mid):
    return Metric.model_validate(read_yaml(os.path.join(ROOT, 'data', 'metrics', mid + '.yaml')))


def claim_problems(c: dict) -> list[str]:
    """Why a claim on DCASE breaks the family/child rule, if it does: it must name an edition (dcase@<year>)
    and a task-and-year subset of that same edition, never the family alone (P3-S8-T07 builds on this)."""
    bench, subset = c.get('benchmark') or '', c.get('subset')
    ident, _, version = bench.partition('@')
    if ident != 'dcase':
        return []
    out = []
    if not version:
        out.append('names the DCASE family, not an edition')
    m = CHILD.match(subset or '')
    if m is None:
        out.append('names no task-and-year subset (%r)' % subset)
    elif version and m['year'] != version:
        out.append('pairs edition %s with a %s subset, a cross-year comparison' % (version, m['year']))
    return out


# ---- 1. one family ------------------------------------------------------------------------------------

def test_dcase_is_one_benchmark_record(dcase):
    assert dcase.id == 'dcase'
    paths = curated_benchmark_files(ROOT) + stub_files(ROOT, 'benchmarks')
    others = []
    for p in paths:
        r = read_yaml(p)
        if not isinstance(r, dict) or r.get('id') == 'dcase':
            continue
        names = [r.get('name') or ''] + [a for a in r.get('aliases') or [] if isinstance(a, str)]
        if str(r.get('id', '')).startswith('dcase') or any(re.search(r'\bDCASE\b', n) for n in names):
            others.append(os.path.relpath(p, ROOT))
    assert others == [], 'a DCASE edition or task filed as its own benchmark: %s' % others
    assert len([p for p in curated_benchmark_files(ROOT) if read_yaml(p).get('id') == 'dcase']) == 1


# ---- 2. each task-and-year is a child of its edition ---------------------------------------------------

def test_every_subset_is_a_task_and_year_child_of_an_edition(dcase):
    editions = {v.version for v in dcase.versions}
    by_id = {s.id: s for s in dcase.subsets}
    for s in dcase.subsets:
        m = CHILD.match(s.id)
        assert m, '%s is not dcase#<year>-task<N>' % s.id
        assert m['year'] in editions, '%s: no edition %s' % (s.id, m['year'])
        assert s.label.startswith('%s Task %s,' % (m['year'], m['n'])), s.id
        if s.parent is None:
            assert m['track'] == '', '%s: a track letter on a top-level task' % s.id
        else:
            p = CHILD.match(s.parent)
            assert p and (p['year'], p['n'], p['track']) == (m['year'], m['n'], ''), \
                '%s sits under %s, another task or year' % (s.id, s.parent)
            assert by_id[s.parent].parent is None


def test_each_edition_has_the_tasks_its_totals_row_counts(dcase):
    tasks = {}
    for s in dcase.subsets:
        m = CHILD.match(s.id)
        if s.parent is None:
            tasks.setdefault(m['year'], []).append(int(m['n']))
    assert {y: sorted(n) for y, n in tasks.items()} == {y: list(range(1, k + 1)) for y, k in TASKS_PER_EDITION.items()}
    assert sum(len(n) for n in tasks.values()) == 68
    assert quote_found(TOTALS_QUOTE, source(EVENTS)['quote_extract'])


def test_the_earlier_children_cite_the_events_page(dcase):
    for s in dcase.subsets:
        if CHILD.match(s.id)['year'] != '2026':
            assert [e.source for e in s.evidence] == [EVENTS], s.id


# ---- 3. cross-year comparison is refused --------------------------------------------------------------

def test_every_edition_is_a_breaking_edition_and_they_chain(dcase):
    vs = dcase.versions
    assert [v.version for v in vs] == sorted(TASKS_PER_EDITION)
    for v in vs:
        assert (v.version_kind, v.breaking) == ('edition', True), v.version
        assert EVENTS in v.sources, v.version
    for older, newer in zip(vs, vs[1:]):
        assert (older.superseded_by, newer.supersedes_version) == (newer.version, older.version)


def test_versions_basis_records_the_annual_evaluation_set(raw):
    basis = raw['versions_basis']
    assert 'evaluation set' in basis['reason'] and 'breaking' in basis['reason']
    assert quote_found(basis['quote'], source(basis['source'])['quote_extract'])


def test_one_task_line_never_shares_a_key_across_years(dcase):
    r = C.resolve_profile(dcase, C.load_profiles())
    keys = {C.compute(r, None, 'dcase@%s' % y, 'any-metric', 'dcase#%s-task1' % y).comparability_key
            for y in TASKS_PER_EDITION}
    assert len(keys) == len(TASKS_PER_EDITION)
    same = C.compute(r, None, 'dcase@2025', 'any-metric', 'dcase#2025-task1').comparability_key
    assert same in keys                                    # the key is a function of its inputs, not of the call


def test_a_dcase_claim_names_an_edition_and_its_own_years_child():
    assert claim_problems({'benchmark': 'dcase@2025', 'subset': 'dcase#2025-task2'}) == []
    assert claim_problems({'benchmark': 'dcase', 'subset': 'dcase#2025-task2'}) == \
        ['names the DCASE family, not an edition']
    assert claim_problems({'benchmark': 'dcase@2026', 'subset': None}) == ["names no task-and-year subset (None)"]
    assert claim_problems({'benchmark': 'dcase@2026', 'subset': 'dcase#2025-task1'}) == \
        ['pairs edition 2026 with a 2025 subset, a cross-year comparison']
    assert claim_problems({'benchmark': 'open-asr-leaderboard@2026-11-06', 'subset': None}) == []


def test_the_corpus_holds_no_dcase_claim_that_breaks_the_rule():
    bad = {}
    for p in glob.glob(os.path.join(ROOT, 'data', 'claims', '**', '*.yaml'), recursive=True):
        c = read_yaml(p)
        if isinstance(c, dict) and claim_problems(c):
            bad[os.path.relpath(p, ROOT)] = claim_problems(c)
    assert bad == {}


# ---- 4. the family counts once ------------------------------------------------------------------------

def test_no_child_reaches_beyond_the_family_lists(dcase):
    leaves = {dcase.domain.primary, *dcase.domain.secondary}
    families = {leaf.split('/')[0] for leaf in leaves}
    caps = set(dcase.capability)
    for s in dcase.subsets:
        if s.domain_override is not None:
            got = {s.domain_override.primary, *s.domain_override.secondary}
            assert got <= leaves, '%s: %s is not in the family domain' % (s.id, sorted(got - leaves))
            assert {g.split('/')[0] for g in got} <= families         # so gaps.py adds no cell for it
        if s.capability_override is not None:
            assert set(s.capability_override) <= caps, '%s adds %s' % (s.id, sorted(set(s.capability_override) - caps))


# ---- 5. the Open ASR pair -----------------------------------------------------------------------------

def test_wer_and_rtfx_are_bound_both_ways():
    wer, rtfx = metric(WER), metric(RTFX)
    assert RTFX in wer.must_report_with and WER in rtfx.must_report_with
    for m in (wer, rtfx):                                  # neither renders alone: each has a partner that resolves
        partners = [metric(p) for p in m.must_report_with]
        assert partners and all(p.id != m.id for p in partners)


def test_the_pair_reads_as_the_board_reports_it():
    wer, rtfx = metric(WER), metric(RTFX)
    assert (wer.optimum, wer.higher_is_better, wer.range.min, wer.range.max) == ('min', False, 0, None)
    assert (rtfx.optimum, rtfx.higher_is_better, rtfx.unbounded, rtfx.headroom_computable) == ('max', True, True, False)
    assert rtfx.headroom_null_reason() == 'unbounded-metric'
    assert wer.domains == rtfx.domains == ['audio-speech/speech-recognition']


def test_the_open_asr_entry_lists_the_pair():
    b = load_benchmark(OPEN_ASR)
    assert b.metrics == [WER, RTFX]
    assert b.headline_metric == WER
    assert 'throughput' in b.secondary_axes                # RTFx is the board's throughput axis
