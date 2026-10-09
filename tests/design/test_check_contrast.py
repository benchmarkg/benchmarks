"""Tests for scripts/check_contrast.py, the blocking WCAG contrast gate (P2-S2-T02; 09 S4.6, S13).

The done-when: "Every declared pair is checked in both themes against its SC threshold and a fixture token below
4.5:1 fails the script." Fixtures are the real design/tokens.yaml with one thing changed, so they stay in step
with it.
"""
import copy
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_contrast as C  # noqa: E402
from tools.build import tokens as T  # noqa: E402

TOKENS = os.path.join(ROOT, 'design', 'tokens.yaml')
SPEC = T.load_yaml(TOKENS)


def spec():
    return copy.deepcopy(SPEC)


def token(doc, tid):
    for g in doc['groups']:
        if tid in (g.get('tokens') or {}):
            return g['tokens'][tid]
    raise KeyError(tid)


def dump(doc, path):
    from ruamel.yaml import YAML
    with open(path, 'w', encoding='utf-8') as f:
        YAML(typ='safe', pure=True).dump(doc, f)
    return str(path)


def result(results, fg, on, theme):
    [r] = [r for r in results if (r.fg, r.on, r.theme) == (fg, on, theme)]
    return r


# ---- the done-when -----------------------------------------------------------------------------------------

def test_the_real_tokens_pass_with_only_the_eight_recorded_waivers():
    results, failures = C.check(spec())
    assert failures == []
    waived = sorted((r.theme, r.fg, r.on) for r in results if r.waiver and not r.passes)
    assert waived == [('dark', 'c-border', 'c-bg'), ('dark', 'c-border-strong', 'c-bg'),
                      ('light', 'c-absent-hatch', 'c-bg'), ('light', 'c-absent-rule', 'c-bg'),
                      ('light', 'c-border', 'c-bg'), ('light', 'c-border-strong', 'c-bg'),
                      ('light', 'c-emphasis', 'c-ink-faint'), ('light', 'c-verif-1', 'c-bg')]
    assert all(r.passes for r in results if not r.waiver)


def test_every_declared_pair_is_checked_in_both_themes_against_its_kinds_floor():
    results, _ = C.check(spec())
    declared = C.pairs(SPEC, T.resolve(SPEC))
    assert len(declared) == 48 and len(results) == 96          # 40 of 09 S4.6's, 8 of the freshness badge's (05 S7)
    assert {(r.fg, r.on, r.kind) for r in results if r.theme == 'light'} == set(declared)
    assert {(r.fg, r.on, r.kind) for r in results if r.theme == 'dark'} == set(declared)
    floors = SPEC['thresholds']['contrast']
    assert all(r.floor == floors[r.kind] for r in results)
    assert {r.floor for r in results if r.kind == 'text'} == {4.5}
    assert {r.floor for r in results if r.kind in ('large_text', 'non_text')} == {3.0}


def test_a_fixture_token_below_4_5_fails_the_script(tmp_path, capsys):
    doc = spec()
    token(doc, 'c-ink-muted')['light'] = '62.0% 0.012 250'      # 46% -> 62%: about 3.5:1 on --c-bg
    assert C.main(['--tokens', dump(doc, tmp_path / 'tokens.yaml')]) == 1
    err = capsys.readouterr().err
    assert 'FAIL light c-ink-muted on c-bg 3.' in err and 'text floor 4.5:1 (SC 1.4.3)' in err
    assert C.main(['--tokens', TOKENS]) == 0


# ---- the floors --------------------------------------------------------------------------------------------

def test_just_under_the_floor_fails_unrounded():
    assert C.Result('a', 'b', 'light', 'text', 4.499, 4.5).passes is False
    assert C.Result('a', 'b', 'light', 'text', 4.5, 4.5).passes is True
    assert C.contrast(1.0, 0.0) == pytest.approx(21.0) and C.contrast(0.0, 1.0) == pytest.approx(21.0)


def test_the_faint_ink_passes_as_large_text_and_fails_as_body_text():
    doc = spec()
    assert C.check(doc)[1] == []
    next(p for p in doc['contrast_pairs'] if p['fg'] == 'c-ink-faint')['kind'] = 'text'
    _, failures = C.check(doc)
    assert any('c-ink-faint on c-bg' in f and 'text floor 4.5' in f for f in failures)


def test_a_focus_ring_below_3_to_1_fails_as_non_text():
    doc = spec()
    token(doc, 'c-focus')['dark'] = '30.0% 0.05 255'
    failures = C.check(doc)[1]
    assert any(f.startswith('dark c-focus on c-bg') and 'non_text floor 3.0:1 (SC 1.4.11)' in f for f in failures)


def test_the_floors_are_read_from_tokens_yaml_not_hardcoded():
    doc = spec()
    doc['thresholds']['contrast']['text'] = 20.0
    failures = C.check(doc)[1]
    assert any('c-ink on c-bg' in f and 'text floor 20.0' in f for f in failures)


def test_a_ramp_pair_covers_every_step_in_the_taxonomy_order():
    results, _ = C.check(spec())
    assert sorted({r.fg for r in results if r.fg.startswith('c-verif-') and r.fg[-1].isdigit()}) == \
        ['c-verif-%d' % i for i in range(1, 8)]
    assert result(results, 'c-verif-7', 'c-bg', 'light').ratio > result(results, 'c-verif-1', 'c-bg', 'light').ratio


def test_a_ref_token_is_measured_as_the_token_it_aliases():
    doc = spec()
    doc['contrast_pairs'].append({'fg': 'c-absent-ink', 'on': ['c-bg'], 'kind': 'large_text', 'basis': 'test'})
    results, _ = C.check(doc)
    assert result(results, 'c-absent-ink', 'c-bg', 'light').ratio == result(results, 'c-ink-faint', 'c-bg', 'light').ratio


# ---- the waivers -------------------------------------------------------------------------------------------

def test_a_waived_pair_that_gets_worse_fails():
    doc = spec()
    token(doc, 'c-border')['light'] = '95.0% 0.008 250'
    failures = C.check(doc)[1]
    assert any("light c-border on c-bg" in f and "worse than its waiver's 1.39:1" in f for f in failures)


def test_a_waiver_that_no_longer_fails_is_stale():
    doc = spec()
    token(doc, 'c-absent-hatch')['light'] = '60% 0.008 250'
    [f] = C.check(doc)[1]
    assert f.startswith('light c-absent-hatch on c-bg') and f.endswith('the waiver is stale, delete it')


def test_a_waiver_covers_one_theme_only():
    doc = spec()
    token(doc, 'c-emphasis')['dark'] = '60.0% 0.080 300'           # the dark pair has no waiver
    failures = C.check(doc)[1]
    assert any(f.startswith('dark c-emphasis on c-ink-faint') and 'waive' not in f for f in failures)


def test_a_waiver_for_an_undeclared_pair_is_refused():
    doc = spec()
    doc['contrast_waivers'].append({'fg': 'c-ink', 'on': 'c-border', 'theme': 'light', 'measured': 9, 'reason': 'x'})
    with pytest.raises(C.ContrastError, match='no contrast_pairs entry declares'):
        C.check(doc)


# ---- malformed blocks --------------------------------------------------------------------------------------

@pytest.mark.parametrize('change, match', [
    (lambda d: d['contrast_pairs'].append({'fg': 'c-nope', 'on': ['c-bg'], 'kind': 'text'}), 'c-nope, which is not'),
    (lambda d: d['contrast_pairs'].append({'fg': 'c-ink', 'on': ['c-bg'], 'kind': 'huge'}), "kind 'huge'"),
    (lambda d: d['contrast_pairs'].append({'fg': {'ramp': 'c-ink'}, 'on': ['c-bg'], 'kind': 'text'}), 'not a ramp'),
    (lambda d: d.pop('contrast_pairs'), 'declares no contrast_pairs'),
])
def test_a_malformed_block_is_an_error_not_a_pass(change, match, tmp_path, capsys):
    doc = spec()
    change(doc)
    with pytest.raises(C.ContrastError, match=match):
        C.check(doc)
    assert C.main(['--tokens', dump(doc, tmp_path / 't.yaml')]) == 1
    assert 'check_contrast: error' in capsys.readouterr().err
