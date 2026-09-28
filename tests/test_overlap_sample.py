"""scripts/overlap_sample.py: the seeded overlap sample and its two committed files (P0-S10-T01; 01 S4).

The task's verification: the sampler is seeded and reproducible; every row carries checked_by and an
evidence_url that `bench check-links` resolves; and the run is void if a reviewer's independent
re-run of ten rows disagrees with any of them. The lookups themselves are a judgement and are not
re-made here. The resolution check is the only one that needs the network, so it runs when
BENCH_NETWORK=1 and is skipped otherwise; the structural half runs always.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import overlap_sample as o  # noqa: E402
from tools import links  # noqa: E402

ON = '2026-09-27'
FILES = [o.out_path(ROOT, s.key, ON) for s in o.SERVICES]


def _docs():
    return [o.load(p) for p in FILES]


@pytest.fixture(scope='module')
def frame():
    return o.build_frame(ROOT)


@pytest.fixture(scope='module')
def targets():
    return o.seed_targets(o._yaml(ROOT, o.DOMAINS))


# ---- the frame and the draw -----------------------------------------------------------------------

def test_the_frame_covers_every_domain_family_and_names_each_family_once(frame, targets):
    assert set(frame) == set(targets) and len(targets) == 19 and sum(targets.values()) == 320
    alloc = o.allocate(targets, 50)
    for d, members in frame.items():
        assert len(members) >= alloc[d], d
    keys = [o.family_key(f.name) for fs in frame.values() for f in fs]
    assert len(keys) == len(set(keys))                      # one stratum per family
    names = {f.name for fs in frame.values() for f in fs}
    assert not names & set(o.NOT_FAMILIES)                  # gaps, headings, platforms are not families
    assert o.build_frame(ROOT) == frame and o.frame_sha256(o.build_frame(ROOT)) == o.frame_sha256(frame)


def test_versions_and_renamings_are_one_family():
    assert o.family_key('Video-MME v2') == o.family_key('VideoMME')
    assert o.family_key('Terminal-Bench 2.0') == o.family_key('Terminal-Bench')
    assert o.family_key('FrontierMath (tiers + Erdős)') == o.family_key('FrontierMath-Tier-4-v2-Private')
    assert o.family_key('MMLU-Pro') != o.family_key('MMLU')


def test_the_allocation_is_proportional_to_the_seed_targets(targets):
    alloc = o.allocate(targets, 50)
    assert sum(alloc.values()) == 50
    for d, k in alloc.items():
        assert abs(k - 50 * targets[d] / 320) < 1, d
    assert alloc['robotics-embodiment'] == alloc['biology-genetics'] == 4
    assert o.allocate({'a': 1, 'b': 1, 'c': 1}, 2) == {'a': 1, 'b': 1, 'c': 0}      # ties by name


def test_the_sampler_is_seeded_and_reproducible(frame, targets):
    one = o.draw(frame, targets, 50, o.SEED)
    assert one == o.draw(frame, targets, 50, o.SEED)
    assert len(one) == 50 == len({f.id for f in one})
    assert one != o.draw(frame, targets, 50, o.SEED + 1)
    ids = [f.id for f in one]
    review = o.review_sample(ids, o.SEED)
    assert review == o.review_sample(ids, o.SEED) and len(review) == 10 and set(review) <= set(ids)
    assert review != o.review_sample(ids, o.SEED + 1)


def test_a_stratum_smaller_than_its_allocation_is_refused():
    fam = o.Family('x', 'X', 'a', 'test')
    with pytest.raises(SystemExit, match='2 draws allocated, 1 families'):
        o.draw({'a': [fam]}, {'a': 1}, 2, 1)


def test_the_committed_files_are_this_draw_over_this_frame(frame, targets):
    drawn = [f.id for f in o.draw(frame, targets, 50, o.SEED)]
    for doc in _docs():
        assert [r['family'] for r in doc['rows']] == drawn, doc['service']
        assert doc['sample']['frame_sha256'] == o.frame_sha256(frame)
        assert doc['sample']['seed'] == o.SEED and doc['sample']['n'] == 50
        assert [a['family'] for a in doc['review']['rerun']] == o.review_sample(drawn, o.SEED)


def test_the_interval_is_wilsons():
    assert o.wilson(0, 50) == (0.0, pytest.approx(0.0714, abs=1e-4))
    assert o.wilson(25, 50) == (pytest.approx(0.3664, abs=1e-4), pytest.approx(0.6336, abs=1e-4))
    assert o.wilson(50, 50)[1] == pytest.approx(1.0)


# ---- the rows ---------------------------------------------------------------------------------------

def test_every_row_carries_checked_by_and_an_evidence_url_check_links_walks():
    for path, doc in zip(FILES, _docs()):
        rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
        assert o.check_rows(doc['rows']) == [], rel
        walked = {lk.url for lk in links.collect(ROOT, [rel]) if lk.where.endswith('.evidence_url')}
        assert len(doc['rows']) == 50
        for r in doc['rows']:
            assert r['checked_by'] and r['checked_on'] == ON
            assert r['evidence_url'] in walked
            assert r['basis'] in ('search-proposal', 'checker-override')
            if r['basis'] == 'checker-override':
                assert r['note'], r['family']
        assert rel in links.files(ROOT)                     # bench check-links reads data/_analysis/


@pytest.mark.skipif(os.environ.get('BENCH_NETWORK') != '1', reason='resolves 100 URLs; set BENCH_NETWORK=1')
def test_every_evidence_url_resolves_through_check_links():
    resolver = links.Resolver(timeout=30)
    for doc in _docs():
        for r in doc['rows']:
            cls, detail = links.classify(r['evidence_url'], resolver.get(r['evidence_url']))
            assert cls in ('live', 'redirected'), (r['family'], detail)


def test_a_row_without_its_checker_or_its_url_is_refused():
    good = {'family': 'f', 'present': True, 'matched': {'id': 'x', 'name': 'X'},
            'evidence_url': 'https://example.org/x', 'checked_by': 'someone', 'checked_on': ON}
    assert o.check_rows([good]) == []
    assert o.check_rows([dict(good, checked_by=None)]) == ['f: checked_by missing']
    assert o.check_rows([dict(good, evidence_url='')]) == ['f: evidence_url missing']
    assert o.check_rows([dict(good, evidence_url='see notes')]) == ['f: evidence_url is not a URL']
    assert o.check_rows([dict(good, present='yes')]) == ['f: present missing']
    assert o.check_rows([dict(good, matched=None)]) == ['f: present with no matched entry']


# ---- the review: the failure case the verification names -----------------------------------------------

def _reviewed(answers):
    doc = json.loads(json.dumps(_docs()[0]))
    by = {r['family']: r['present'] for r in doc['rows']}
    doc['review']['rerun'] = [{'family': f, 'present': answers(f, by[f])} for f in
                              [a['family'] for a in doc['review']['rerun']]]
    doc['result'] = o.summarise(doc)
    doc['review']['status'] = o.review_status(doc)
    return doc


def test_the_run_is_pending_until_the_reviewer_answers_all_ten():
    for doc in _docs():
        assert doc['review']['status'] == 'pending' and len(doc['review']['rerun']) == 10
    assert _reviewed(lambda f, v: None)['review']['status'] == 'pending'


def test_the_run_is_void_if_any_reviewer_answer_disagrees():
    agree = _reviewed(lambda f, v: v)
    assert agree['review']['status'] == 'confirmed'
    assert '95% interval' in o.line(agree)
    first = agree['review']['rerun'][0]['family']
    void = _reviewed(lambda f, v: (not v) if f == first else v)
    assert void['review']['status'] == 'void'
    assert 'VOID' in o.line(void) and 'interval' not in o.line(void)


# ---- the lookups, against canned answers --------------------------------------------------------------

class Canned:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def json(self, url):
        self.asked.append(url)
        for key, value in self.answers.items():
            if key in url:
                return value
        return {'data': []}


def _hit(bid, name):
    return {'benchmark_id': bid, 'name': name, 'urls': {'page': 'https://benchmarklist.com/benchmarks/%s/' % bid}}


def test_a_full_text_hit_is_not_the_family():
    assert o._is_family('LIBERO', 'LIBERO') and o._is_family('LIBERO', 'LIBERO-Long')
    assert o._is_family('CADBench', 'CADBench: A Multimodal Benchmark for AI-Assisted CAD Program Generation')
    assert not o._is_family('LIBERO', 'WatchAct: A Benchmark ... with an executable LIBERO task')
    # The rule proposes; it cannot decide. It takes 'ForecastBench-Sim' for ForecastBench, an unrelated
    # benchmark, and the committed row says so as a checker override.
    assert o._is_family('ForecastBench', 'ForecastBench-Sim (FBSim)')
    row = next(r for r in _docs()[0]['rows'] if r['family'] == 'forecastbench')
    assert row['present'] is False and row['basis'] == 'checker-override'
    http = Canned({'query=LIBERO': {'data': [_hit('watchact', 'WatchAct: an executable LIBERO task')]}})
    got = o.BenchmarkList(http).lookup(o.Family('libero', 'LIBERO', 'robotics-embodiment', 'test'))
    assert not got.present and got.evidence_url == o.BenchmarkList.FIND % 'LIBERO' and got.candidates


def test_benchmarklist_records_the_entry_page_when_present():
    http = Canned({'query=Open%20Catalyst&': {'data': [_hit('oc20', 'Open Catalyst OC20')]}})
    fam = o.Family('open-catalyst-oc20', 'Open Catalyst: OC20', 'chemistry-materials', 'test', ('OC22',))
    got = o.BenchmarkList(http).lookup(fam)
    assert got.present and got.matched == {'id': 'oc20', 'name': 'Open Catalyst OC20'}
    assert got.evidence_url == 'https://benchmarklist.com/benchmarks/oc20/'
    assert got.queries == ['Open Catalyst: OC20', 'Open Catalyst']


def test_radar_search_follows_the_sites_rule_and_links_the_benchmark_page():
    recs = [{'name': 'MMLU-Pro-Extended', 'slug': 'b'}, {'name': 'MMLU', 'slug': 'a'},
            {'name': 'KMMLU', 'slug': 'c'}, {'name': 'Other', 'aliases': ['MMLU Redux'], 'slug': 'd'}]
    assert [r['slug'] for r in o.BenchmarkRadar.search(recs, 'mmlu')] == ['a', 'd', 'b', 'c']
    radar = o.BenchmarkRadar(Canned({'benchmark-index': {'benchmarks': recs}}))
    got = radar.lookup(o.Family('mmlu', 'MMLU', 'language', 'test'))
    assert got.present and got.evidence_url == 'https://benchmark-radar.org/benchmarks/a/'
    miss = radar.lookup(o.Family('libero', 'LIBERO', 'robotics-embodiment', 'test'))
    assert not miss.present and miss.evidence_url == 'https://benchmark-radar.org/benchmarks/?bq=LIBERO'


def test_the_query_list_is_what_a_person_types():
    fam = o.Family('hle', "Humanity's Last Exam (HLE)", 'general-intelligence', 'test')
    assert o.queries(fam) == ["Humanity's Last Exam", 'HLE']
    assert o.queries(o.Family('ntire', 'NTIRE (CVPR)', 'vision', 'test')) == ['NTIRE']


# ---- a re-run keeps the judgements ---------------------------------------------------------------------

class Fixed:
    """A service whose every lookup answers `present`, and counts how often it was asked."""
    key, title, url, method = 'fixed', 'Fixed', 'https://example.org/', 'canned'
    calls = 0

    def __init__(self, http):
        pass

    def lookup(self, fam):
        Fixed.calls += 1
        return o.Lookup(False, 'https://example.org/search?q=%s' % fam.id, [fam.name])


def test_a_rerun_keeps_recorded_rows_and_refresh_discards_them(tmp_path):
    Fixed.calls = 0
    first = o.run(ROOT, 50, o.SEED, ON, services=[Fixed], out_root=str(tmp_path))[0]
    assert Fixed.calls == 50 and first['result']['present'] == 0
    path = o.out_path(str(tmp_path), 'fixed', ON)
    doc = o.load(path)
    doc['rows'][0].update(present=True, matched={'id': 'x', 'name': 'X'}, basis='checker-override', note='found')
    o.write(path, doc, str(tmp_path))
    again = o.run(ROOT, 50, o.SEED, ON, services=[Fixed], out_root=str(tmp_path))[0]
    assert Fixed.calls == 50 and again['result']['present'] == 1
    assert again['rows'][0]['note'] == 'found'
    fresh = o.run(ROOT, 50, o.SEED, ON, refresh=True, services=[Fixed], out_root=str(tmp_path))[0]
    assert Fixed.calls == 100 and fresh['result']['present'] == 0


def test_the_summary_prints_each_proportion_with_its_interval(capsys):
    assert o.main(['--summary', '--date', ON]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [ln.split()[0] for ln in out] == ['benchmarklist', 'benchmark-radar']
    assert all('/50 = ' in ln and '95% interval [' in ln and '(Wilson)' in ln for ln in out)
