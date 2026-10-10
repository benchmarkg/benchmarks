"""Tests for scripts/check_triage_sample.py (P5-S5-T05; 06 S5.1-5.2).

The done_when: "The check confirms the sample is uniform over the full window and is not conditioned on the regex
hit set, which is the only way recall gets a denominator." A synthetic frame of 3,000 papers, one in ten a regex
hit, is sampled the way --draw samples; then each way a sample can lie about its denominator is seeded and must
fail. The committed sample is checked as CI checks it.
"""
import copy
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_triage_sample as C  # noqa: E402

SCRIPT = os.path.join(ROOT, 'scripts', 'check_triage_sample.py')
START, END = '2026-09-10', '2026-09-16'


def frame(n=3000):
    out = {}
    for i in range(n):
        ident = '2609.%05d' % i
        hit = i % 10 == 0
        out[ident] = {'v1': '2026-09-%02d' % (10 + i % 7), 'categories': [('cs.CL', 'cs.LG', 'cs.CV', 'cs.AI')[i % 4], 'stat.ML'],
                      'title': 'Paper %d' % i,
                      'abstract': ('We introduce Thing-%d, a benchmark for things.' % i) if hit else ('We study method %d.' % i)}
    return out


def doc(seed=7, fr=None):
    from datetime import date
    fr = fr or frame()
    h = {'frame': fr, 'records': 9000, 'complete_list_size': None, 'last_page_token': None, 'pages': 7, 'deleted': 3,
         'request': 'verb=ListRecords&set=cs&metadataPrefix=arXivRaw&from=2026-09-10&until=2026-10-09'}
    return C.build(h, date.fromisoformat(START), date.fromisoformat(END), seed, '2026-10-09T23:00:00Z')


def test_a_uniform_sample_of_the_whole_window_passes():
    d = doc()
    assert C.check(d) == []
    assert d['denominator'] == 3000 and len(d['sample']) == 200
    assert 5 <= C.hits(d['sample']) <= 40                       # about one in ten, as in the frame


def test_the_draw_is_the_seeds_and_nothing_else():
    ids = sorted(frame())
    assert C.draw(7, ids) == C.draw(7, list(reversed(ids)))     # order of the listing does not matter
    assert C.draw(7, ids) != C.draw(8, ids)


def test_a_sample_drawn_from_the_regex_hit_set_fails():
    fr = frame()
    d = doc(fr=fr)
    hit_ids = [i for i in sorted(fr) if C.REGEX.search(fr[i]['abstract'])]
    d['sample'] = [{'arxiv_id': i, 'title': fr[i]['title'], 'abstract': fr[i]['abstract']} for i in C.draw(7, hit_ids)]
    errs = C.check(d)
    assert any('not the 200 ids seed 7 selects from the whole listing' in e for e in errs)
    assert any('flags all 200 sampled abstracts' in e for e in errs)


def test_a_frame_that_is_the_hit_set_fails_even_when_the_draw_is_honest():
    fr = {i: v for i, v in frame().items() if C.REGEX.search(v['abstract'])}
    d = doc(fr=fr)
    assert any('flags all 200 sampled abstracts' in e for e in C.check(d))


def test_a_sample_that_does_not_match_its_seed_fails():
    d = doc()
    d['seed'] = 8
    assert any('was not drawn uniformly from the full window' in e for e in C.check(d))


def test_a_verdict_attached_to_an_item_fails():
    d = doc()
    d['sample'][0]['regex_hit'] = True
    assert any('carry regex_hit' in e for e in C.check(d))


@pytest.mark.parametrize('mutate, says', [
    (lambda d: d['harvest'].update(last_page_token='skip=1300'), 'did not run to the end of the list'),
    (lambda d: d['harvest'].pop('last_page_token'), 'did not run to the end of the list'),
    (lambda d: d['harvest'].update(complete_list_size=9001), 'read 9000 records of the 9001'),
    (lambda d: d.update(denominator=2999), 'the denominator is 2999'),
    (lambda d: d['listing'].append(d['listing'][0]), 'more than once'),
    (lambda d: d['listing'].append('2608.99999 2026-08-30 cs.CL'), 'outside the window'),
    (lambda d: d['listing'].append('2609.99999 2026-09-12 math.CO'), 'outside the window or the four categories'),
    (lambda d: d['window'].update(categories=['cs.CL']), "not 06 S5.1's four"),
    (lambda d: d['sample'].pop(), 'holds 199 items'),
    (lambda d: d.pop('seed'), 'does not record seed'),
])
def test_each_way_a_sample_can_misstate_its_denominator_fails(mutate, says):
    d = copy.deepcopy(doc())
    mutate(d)
    errs = C.check(d)
    assert any(says in e for e in errs), errs


def test_the_written_file_round_trips(tmp_path):
    d = doc()
    path = tmp_path / 'sample-2026-10-09.yaml'
    C.write(d, str(path))
    r = subprocess.run([sys.executable, SCRIPT, str(path)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout
    assert '200 of 3000 papers' in r.stdout
    assert path.read_text(encoding='utf-8').startswith('# The 200-abstract labelling sample')


def test_the_committed_sample_passes():
    r = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout
