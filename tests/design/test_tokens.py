"""design/tokens.yaml and what tools/build/tokens.py generates from it (P2-S2-T01; 09 S4.1, S4.5, S9, S13).

The verify is `bench build --out build/ && git diff --exit-code` over the two generated files, which
holds them to the build's output. These tests hold the rest of the done-when:
  - the light set is 09 S4.5's code block, value for value, and the dark set carries every one of
    09 S9's representative values -- read from the plan document, not retyped here;
  - both themes are authored for every token (none inverted, none missing), and the three ordered
    ramps run light-to-dark in light and dark-to-bright in dark;
  - the verification ramp's order is generated from taxonomy/verification.yaml: reordering the
    ladder reorders the rung names on the stops, and a ladder the ramp no longer fits fails;
  - the thresholds / categorical_sets / co_occurrence blocks exist and name real tokens;
  - the prohibited --c-dom-* namespace is absent and cannot be generated.
The human review of the dark values is the one part no test can do.
"""
import json
import os
import re
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import tokens as T  # noqa: E402

SPEC = os.path.join(ROOT, '_plan', '09-design-system.md')
DECL = re.compile(r'--([a-z0-9-]+):\s*(oklch\(([^)]*)\)|var\(--([a-z0-9-]+)\))')
# Groups a later task added beyond 09 S4.5's block, each with the section that asked for it: their values are not
# 09 S4.5's to transcribe, and the verbatim test holds everything else to it.
BEYOND_S4_5 = {'freshness': '05 S7 and 06 S3.0 (P5-S7-T04)'}


def spec_block(heading: str) -> str:
    """The first ```css block under a 09-design-system.md heading."""
    text = open(SPEC, encoding='utf-8').read()
    section = text[text.index(heading):]
    return re.search(r'```css\n(.*?)```', section, re.S).group(1)


def declarations(css: str) -> dict[str, str]:
    """{token id: normalised value} for every custom property in a CSS text; the last one wins."""
    out = {}
    for m in DECL.finditer(css):
        out[m.group(1)] = ('oklch(%s)' % ' '.join(m.group(3).split())) if m.group(3) else 'var(--%s)' % m.group(4)
    return out


@pytest.fixture(scope='module')
def built():
    files = T.generate(ROOT)
    return files[T.CSS_OUT].decode('utf-8'), json.loads(files[T.JSON_OUT])


def light_block(css: str) -> str:
    return css[css.index(':root {'):css.index(':root[data-theme="light"]')]


def dark_blocks(css: str) -> tuple[str, str]:
    media = css[css.index('@media (prefers-color-scheme: dark)'):css.index(':root[data-theme="dark"]')]
    forced = css[css.index(':root[data-theme="dark"]'):]
    return media, forced


def test_the_committed_files_are_the_generators_output():
    assert T.stale(ROOT) == []


def test_the_light_set_is_09_s4_5_value_for_value(built):
    css, _ = built
    beyond = {tid for g in T.resolve(T.load_yaml(os.path.join(ROOT, T.TOKENS)), ROOT) if g['id'] in BEYOND_S4_5
              for tid in (r['id'] for r in g['rows'])}
    light = {k: v for k, v in declarations(light_block(css)).items() if k not in beyond}
    assert light == declarations(spec_block('### 4.5 The token set'))
    assert beyond and not beyond & set(declarations(spec_block('### 4.5 The token set')))


def test_the_dark_set_carries_every_09_s9_representative_value(built):
    css, _ = built
    spec = declarations(spec_block('```css\n/* Representative dark values */').replace('```css\n', '', 0))
    media, forced = dark_blocks(css)
    for block in (media, forced):
        got = declarations(block)
        assert {k: got[k] for k in spec} == spec


def test_both_dark_blocks_are_the_same_values_and_every_token_has_both_themes(built):
    css, data = built
    media, forced = dark_blocks(css)
    assert declarations(media) == declarations(forced)
    light = declarations(light_block(css))
    assert set(declarations(media)) == set(light)
    assert set(data['themes']['light']) == set(data['themes']['dark']) == set(light)
    spec = T.load_yaml(os.path.join(ROOT, T.TOKENS))
    for g in T.resolve(spec, ROOT):
        for r in g['rows']:
            assert r.get('ref') or (r['light'] and r['dark']), r['id']
    inverted = [t for t, v in data['themes']['dark'].items()
                if 'ref' not in v and abs(v['l'] - (1 - data['themes']['light'][t]['l'])) < 1e-9
                and v['c'] == data['themes']['light'][t]['c'] and v['h'] == data['themes']['light'][t]['h']]
    assert inverted == []                                   # 09 S9: authored, not a mechanical flip


@pytest.mark.parametrize('ramp', ['verification', 'headroom', 'coverage'])
def test_the_ramps_run_to_darker_in_light_and_to_brighter_in_dark(built, ramp):
    _, data = built
    ids = data['ramps'][ramp]['tokens']
    assert len(ids) == 7
    light = [data['themes']['light'][t]['l'] for t in ids]
    dark = [data['themes']['dark'][t]['l'] for t in ids]
    assert all(a > b for a, b in zip(light, light[1:])), light
    assert all(a < b for a, b in zip(dark, dark[1:])), dark


def test_the_verification_order_is_read_from_the_taxonomy(built):
    css, data = built
    ladder = T.rungs(ROOT)
    assert data['ramps']['verification']['rungs'] == ladder
    assert data['ramps']['verification']['primary_channel'] == 'count'
    assert ladder.index('sandboxed-rerun') == 6 and ladder.index('third-party-audited') == 5   # 09 S4.3
    for rank, rung in enumerate(ladder, 1):
        assert re.search(r'--c-verif-%d: +oklch\([^)]*\); +/\* %s \*/' % (rank, rung), css)


def _tree(tmp_path, tokens_edit=None, ladder_edit=None):
    for rel, edit in ((T.TOKENS, tokens_edit), (T.VERIFICATION, ladder_edit)):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), dst)
        if edit:
            dst.write_text(edit(dst.read_text(encoding='utf-8')), encoding='utf-8')
    return str(tmp_path)


def test_reordering_the_ladder_reorders_the_ramp_without_touching_tokens_yaml(tmp_path):
    swap = lambda s: s.replace('  - rank: 6\n', '  - rank: X\n').replace('  - rank: 7\n', '  - rank: 6\n') \
        .replace('  - rank: X\n', '  - rank: 7\n')           # noqa: E731
    root = _tree(tmp_path, ladder_edit=swap)
    data = json.loads(T.generate(root)[T.JSON_OUT])
    assert data['ramps']['verification']['rungs'][5:] == ['sandboxed-rerun', 'third-party-audited']
    here = json.loads(T.generate(ROOT)[T.JSON_OUT])
    assert data['themes']['light']['c-verif-7'] == here['themes']['light']['c-verif-7']   # the stop keeps its colour


def test_a_ladder_the_ramp_no_longer_fits_fails_the_build(tmp_path):
    extra = lambda s: s + '  - rank: 8\n    id: a-new-rung\n    meaning: x\n'   # noqa: E731
    with pytest.raises(T.TokenError, match='7 steps authored but .* has 8 rungs'):
        T.generate(_tree(tmp_path, ladder_edit=extra))


@pytest.mark.parametrize('tid', ['c-dom-code', 'c-domain-physics', 'c-family-vision', 'c-group-life-health'])
def test_the_prohibited_namespace_cannot_be_generated(tmp_path, tid):
    head = "  - id: absence\n    title: absence\n    tokens:\n"
    token = "      " + tid + ":\n        light: '60% 0.1 150'\n        dark: '70% 0.1 150'\n"
    add = lambda s: s.replace(head, head + token)           # noqa: E731
    with pytest.raises(T.TokenError, match='prohibited family-colour namespace'):
        T.generate(_tree(tmp_path, tokens_edit=add))


def test_no_family_colour_token_is_generated(built):
    css, data = built
    assert not re.search(r'--c-(dom|domain|family|group)-', css.replace('--c-dom-* / --c-family-* / --c-group-*', ''))
    assert not [t for t in data['themes']['light'] if T.PROHIBITED.match(t)]


def test_the_gate_blocks_exist_and_name_real_tokens():
    spec = T.load_yaml(os.path.join(ROOT, T.TOKENS))
    th = spec['thresholds']
    assert th['delta_e_floor']['value'] == 15 and th['delta_e_floor']['status'] == 'uncalibrated'
    assert th['ramp'] == {'min_adjacent_step': 0.055, 'min_range': 0.45}
    assert th['contrast'] == {'text': 4.5, 'large_text': 3.0, 'non_text': 3.0}
    assert th['cvd'] == ['deuteranopia', 'deuteranomaly-50', 'protanopia', 'tritanopia']
    for s in spec['categorical_sets'].values():
        assert len(s['members']) <= th['categorical_max_members']
        assert all(m['redundant_channel'] for m in s['members'])
    assert all(a['pattern'] for a in spec['absence_states'].values())
    co = spec['co_occurrence']
    assert {'c-emphasis', 'c-link-visited'} == set(co['named_pairs'][0]['pair'])
    assert co['views'] and all(v['meanings'] for v in co['views'].values())


def test_a_block_naming_a_missing_token_fails(tmp_path):
    typo = lambda s: s.replace('      - token: c-affirm\n', '      - token: c-afirm\n')   # noqa: E731
    with pytest.raises(T.TokenError, match='categorical set semantic-states names c-afirm'):
        T.generate(_tree(tmp_path, tokens_edit=typo))


def test_srgb_conversion_matches_known_colours():
    white, ok = T.linear_srgb((1.0, 0.0, 0.0))
    assert ok and T.hex_of(white) == '#ffffff'
    red, _ = T.linear_srgb((0.627955, 0.257683, 29.2339))       # CSS Color 4's oklch() of sRGB red
    assert T.hex_of(red) == '#ff0000'
    grey, ok = T.linear_srgb(T.parse('59.987% 0 0'))           # sRGB #808080
    assert ok and T.hex_of(grey) == '#808080' and abs(T.luminance(grey) - 0.2159) < 1e-3
    mapped, ok = T.linear_srgb(T.parse('88% 0.150 60'))        # 09 S9's dark --seq-head-6: outside sRGB
    assert not ok and all(0 <= x <= 1 for x in mapped)
