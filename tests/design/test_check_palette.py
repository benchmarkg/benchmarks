"""Tests for scripts/check_palette.py, assertion groups A-F under four CVD simulations (P2-S2-T03; 09 S4.2).

The done-when: "All six groups run against four CVD simulations in both themes, the fixture reintroducing a
family-colour token fails group A, and every computed value is written to the report." Fixtures are the real
design/tokens.yaml with one thing changed, so they stay in step with it.
"""
import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_palette as P  # noqa: E402
from tools.build import tokens as T  # noqa: E402

TOKENS = os.path.join(ROOT, 'design', 'tokens.yaml')
SPEC = T.load_yaml(TOKENS)
CVD = ['deuteranopia', 'deuteranomaly-50', 'protanopia', 'tritanopia']


def spec():
    return copy.deepcopy(SPEC)


def run(doc):
    r = P.Run(doc)
    r.run()
    return r


def group(doc, gid):
    return next(g for g in doc['groups'] if g['id'] == gid)


def dump(doc, path):
    from ruamel.yaml import YAML
    with open(path, 'w', encoding='utf-8') as f:
        YAML(typ='safe', pure=True).dump(doc, f)
    return str(path)


def failing(r, g):
    return [f for f in r.failures() if f['group'] == g]


@pytest.fixture(scope='module')
def real():
    return run(spec())


# ---- the done-when -----------------------------------------------------------------------------------------

def test_all_six_groups_run_against_four_cvd_simulations_in_both_themes(real):
    assert real.visions == ['normal'] + CVD == ['normal'] + SPEC['thresholds']['cvd']
    for theme in ('light', 'dark'):
        assert list(real.values[theme]) == real.visions
        for v in real.visions:
            assert set(real.values[theme][v]) == {'B', 'C', 'D', 'E', 'F'}     # A is the token ids, once
            assert real.values[theme][v]['C'] and real.values[theme][v]['D'] and real.values[theme][v]['E']
    assert all(n > 0 for n in real.checks.values())


def test_the_fixture_reintroducing_a_family_colour_token_fails_group_a(tmp_path, capsys):
    doc = spec()
    group(doc, 'semantic')['tokens']['c-dom-physical'] = {'light': '60.0% 0.13 75', 'dark': '78.0% 0.13 75'}
    report = tmp_path / 'palette.json'
    assert P.main(['--tokens', dump(doc, tmp_path / 'tokens.yaml'), '--report', str(report)]) == 1
    assert 'FAIL group A' in capsys.readouterr().err
    out = json.loads(report.read_text(encoding='utf-8'))
    assert out['groups']['A']['failed'] == 10 and not out['passed']        # both themes x five visions
    assert {f['subject'] for f in out['findings']} == {'c-dom-physical'}


@pytest.mark.parametrize('tid', ['c-domain-bio', 'c-family-x', 'c-group-life'])
def test_every_prefix_of_the_namespace_fails_group_a(tid):
    doc = spec()
    group(doc, 'semantic')['tokens'][tid] = {'light': '60.0% 0.13 75', 'dark': '78.0% 0.13 75'}
    assert {f['subject'] for f in failing(run(doc), 'A')} == {tid}


def test_every_computed_value_is_written_to_the_report(tmp_path):
    report = tmp_path / 'r' / 'palette.json'
    assert P.main(['--tokens', TOKENS, '--report', str(report)]) == 0
    out = json.loads(report.read_text(encoding='utf-8'))
    assert out['passed'] and out['thresholds'] == SPEC['thresholds']
    cell = out['values']['light']['protanopia']
    assert cell['C']['verification']['l'][0] > cell['C']['verification']['l'][-1]
    assert set(cell['C']['verification']) == {'l', 'min_adjacent_step', 'range', 'monotonic'}
    assert set(cell['D']['c-emphasis|c-link-visited']) == {'delta_e', 'delta_l', 'pattern', 'views'}
    assert 'c-emphasis|c-ink-faint' in cell['E'] and 'y_ratio' in cell['F']['c-emphasis|c-link-visited']
    assert sum(g['checks'] for g in out['groups'].values()) > 8000


# ---- what blocks today, what reports (the maintainer's call, 2026-10-06) ------------------------------------

def test_the_real_tokens_pass_with_b_d_and_f_reported_not_blocking(real):
    assert real.failures() == []
    reported = {f['group'] for f in real.findings if not f['blocking']}
    assert reported == {'B', 'D', 'F'}
    assert {f['group'] for f in real.findings if f['waived']} == {'C', 'E'}


def test_the_uncalibrated_floors_block_once_calibrated():
    doc = spec()
    doc['thresholds']['delta_e_floor']['status'] = 'calibrated'
    r = run(doc)
    assert failing(r, 'B') and failing(r, 'D') and not failing(r, 'F')
    doc['thresholds']['greyscale_y_ratio_floor']['status'] = 'calibrated'
    assert failing(run(doc), 'F')


def test_the_named_pair_is_asserted_on_colour_and_fails_d_in_light(real):
    d = [f for f in real.findings if f['group'] == 'D' and f['subject'] == 'c-emphasis|c-link-visited']
    assert {(f['theme'], f['vision']) for f in d} >= {('light', 'normal')}
    assert real.values['light']['normal']['D']['c-emphasis|c-link-visited']['pattern'] is False


def test_a_pattern_distinguished_meaning_is_not_held_to_colour(real):
    cell = real.values['light']['normal']['D']
    assert cell['c-alert|c-verif-disputed'] == {'delta_e': 0.0, 'delta_l': 0.0, 'pattern': True,
                                                'views': ['benchmark-detail', 'comparison-table', 'saturation-wall']}
    assert not [f for f in real.findings if f['subject'] == 'c-alert|c-verif-disputed']


def test_cvd_simulation_changes_the_colours(real):
    normal, deut = (real.values['light'][v]['B']['c-alert|c-affirm'] for v in ('normal', 'deuteranopia'))
    assert normal > 15 > deut                        # red and green collapse under deuteranopia


# ---- group B -----------------------------------------------------------------------------------------------

def test_b_caps_a_categorical_set_and_requires_a_channel():
    doc = spec()
    s = doc['categorical_sets']['semantic-states']
    s['members'] += [{'token': t, 'means': 'x', 'redundant_channel': 'label'}
                     for t in ('c-link', 'c-focus', 'c-emphasis', 'c-link-visited')]
    assert any('7 members; the cap is 6' in f['message'] for f in failing(run(doc), 'B'))
    doc = spec()
    doc['categorical_sets']['semantic-states']['members'][0]['redundant_channel'] = ''
    assert any("redundant_channel '' is not one of" in f['message'] for f in failing(run(doc), 'B'))


# ---- group C -----------------------------------------------------------------------------------------------

def test_c_fails_a_ramp_that_is_not_monotonic():
    doc = spec()
    light = group(doc, 'headroom')['ramp']['light']
    light[2], light[3] = light[3], light[2]
    assert any(f['subject'] == 'headroom' and 'monotonic' in f['message'] for f in failing(run(doc), 'C'))


def test_c_honours_the_range_exemption_and_only_it():
    doc = spec()
    group(doc, 'verification')['ramp'].pop('exempt_from')
    assert any(f['subject'] == 'verification' and 'range' in f['message'] for f in failing(run(doc), 'C'))


def test_c_reads_its_floors_from_tokens_yaml():
    doc = spec()
    doc['thresholds']['ramp']['min_adjacent_step'] = 0.2
    assert {f['subject'] for f in failing(run(doc), 'C')} >= {'headroom'}


def test_a_c_waiver_that_gets_worse_fails():
    doc = spec()
    light = group(doc, 'verification')['ramp']['light']
    light[1] = '67% 0.035 250'                       # 70 -> 67: a 0.03 step
    fails = [f for f in failing(run(doc), 'C') if f['subject'] == 'verification']
    assert len(fails) == 5 and all("worse than its waiver's 0.046" in f['message'] for f in fails)  # every vision


def test_a_c_waiver_that_no_longer_fails_is_stale():
    doc = spec()
    group(doc, 'coverage')['ramp']['light'][1] = '89% 0.030 235'   # widen stops 0-1, 0.054 L under protanopia
    assert any(f['subject'] == 'coverage' and 'stale' in f['message'] for f in failing(run(doc), 'C'))


def test_a_c_waiver_for_no_ramp_is_refused():
    doc = spec()
    doc['palette_waivers'].append({'group': 'C', 'ramp': 'c-ink', 'theme': 'light', 'assertion': 'min_range',
                                   'measured': 0.1, 'reason': 'x'})
    with pytest.raises(P.PaletteError, match='no ramp of group C'):
        run(doc)


# ---- groups D, E and F -------------------------------------------------------------------------------------

def test_e_fails_an_unwaived_pair_in_every_vision():
    doc = spec()
    group(doc, 'interaction')['tokens']['c-focus']['dark'] = '30.0% 0.05 255'
    fails = [f for f in failing(run(doc), 'E') if f['subject'] == 'c-focus|c-bg']
    assert {f['vision'] for f in fails} == {'normal'} | set(CVD) and {f['theme'] for f in fails} == {'dark'}


def test_e_holds_emphasis_against_the_bg_and_the_faint_ink(real):
    assert {'c-emphasis|c-bg', 'c-emphasis|c-ink-faint'} <= set(real.values['dark']['tritanopia']['E'])


def test_f_requires_a_channel_that_survives_greyscale():
    doc = spec()
    doc['categorical_sets']['semantic-states']['members'][2]['redundant_channel'] = 'position'
    assert any('does not survive greyscale' in f['message'] for f in failing(run(doc), 'F'))
    doc = spec()
    doc['absence_states']['not-applicable']['pattern'] = ''
    assert any(f['subject'] == 'not-applicable' for f in failing(run(doc), 'F'))


# ---- malformed input ---------------------------------------------------------------------------------------

@pytest.mark.parametrize('name, ok', [('deuteranopia', True), ('protanomaly-30', True), ('tritanomaly-100', True),
                                      ('achromatopsia', False), ('deuteranomaly-0', False), ('protanomaly-101', False)])
def test_simulation_names(name, ok):
    if ok:
        assert P.cvd(name)['severity'] in (30, 100)
    else:
        with pytest.raises(P.PaletteError):
            P.cvd(name)


def test_a_floor_without_a_status_is_an_error(tmp_path, capsys):
    doc = spec()
    doc['thresholds']['delta_e_floor'] = 15
    with pytest.raises(P.PaletteError, match=r'delta_e_floor must be \{value, status\}'):
        run(doc)
    assert P.main(['--tokens', dump(doc, tmp_path / 't.yaml'), '--report', str(tmp_path / 'r.json')]) == 1
    assert 'check_palette: error' in capsys.readouterr().err
