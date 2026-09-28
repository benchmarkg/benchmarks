#!/usr/bin/env python3
"""design/tokens.yaml -> site/src/styles/tokens.css + site/src/lib/tokens.json (P2-S2-T01; 09 S4.1, S4.5, S9, S13).

    python tools/build/tokens.py            # regenerate both files in place
    python tools/build/tokens.py --check    # exit 1 if either file differs from a fresh generation

`bench build` calls write() too, so the committed files are always the build's output and
`git diff --exit-code` over them after a build is the drift check (09 S4.1 rule 3: "Tokens are
generated data, not hand-written CSS").

What is generated rather than authored:

  - the verification ladder's ORDER. tokens.yaml authors seven lightness steps and nothing else;
    which rung each step belongs to is read from taxonomy/verification.yaml by rank (09 S4.3:
    "regenerate the token block from taxonomy/verification.yaml rather than typing it"). A ladder
    with a rung added or removed and the ramp not re-authored fails here, not in a browser.
  - the dark theme's selectors (09 S9): the OS preference unless data-theme="light", and
    data-theme="dark" regardless of it -- the same dark values in both blocks.
  - sRGB hex beside every OKLCH value in tokens.json, because the ECharts theme object cannot read
    oklch() (09 S9: "ECharts does not follow CSS custom properties"). Out-of-gamut colours are
    mapped the way CSS Color 4 maps them (chroma reduced in OKLCH until the clipped colour is within
    a just-noticeable difference) and flagged `in_gamut: false`, so the chart and the page agree.

Refused outright: any token id in the prohibited namespace ^c-(dom|domain|family|group)- (09 S4.2
decision D4). scripts/check_palette.py's group A asserts the same thing over the YAML; refusing it
here as well means a family-colour token can never reach tokens.css even with that check skipped.

Determinism: key order is the YAML's authored order in the CSS and sorted in the JSON, LF, one
trailing newline, and no clock -- two generations of one tree are byte-identical.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKENS = os.path.join('design', 'tokens.yaml')
VERIFICATION = os.path.join('taxonomy', 'verification.yaml')
CSS_OUT = os.path.join('site', 'src', 'styles', 'tokens.css')
JSON_OUT = os.path.join('site', 'src', 'lib', 'tokens.json')
FORMAT = 1
THEMES = ('light', 'dark')
PROHIBITED = re.compile(r'^c-(dom|domain|family|group)-')
TOKEN_ID = re.compile(r'^(c|seq)-[a-z0-9]+(-[a-z0-9]+)*$')
OKLCH = re.compile(r'^(\d+(?:\.\d+)?)% (\d+(?:\.\d+)?) +(\d+(?:\.\d+)?)$')
JND = 0.02                                  # CSS Color 4 gamut mapping's just-noticeable difference


class TokenError(ValueError):
    pass


# ---------------------------------------------------------------- colour maths (OKLCH -> sRGB)

def parse(value: str) -> tuple[float, float, float]:
    """'55.0% 0.19  255' -> (0.55, 0.19, 255.0). The authored text is kept verbatim for the CSS."""
    m = OKLCH.match(value.strip())
    if not m:
        raise TokenError('not an OKLCH triple "L% C H": %r' % value)
    return float(m.group(1)) / 100, float(m.group(2)), float(m.group(3))


def _linear(lch: tuple[float, float, float]) -> tuple[float, float, float]:
    L, C, h = lch
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
            -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
            -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)


def _to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def _inside(rgb, eps: float = 1e-6) -> bool:
    return all(-eps <= x <= 1 + eps for x in rgb)


def _clip(rgb) -> tuple[float, float, float]:
    return tuple(min(1.0, max(0.0, x)) for x in rgb)


def _oklab(lch) -> tuple[float, float, float]:
    L, C, h = lch
    return L, C * math.cos(math.radians(h)), C * math.sin(math.radians(h))


def linear_srgb(lch: tuple[float, float, float]) -> tuple[tuple[float, float, float], bool]:
    """Linear-light sRGB for an OKLCH colour, gamut-mapped per CSS Color 4 S13.2; and whether it was in gamut."""
    rgb = _linear(lch)
    if _inside(rgb):
        return _clip(rgb), True
    L, C, h = lch
    if L >= 1:
        return (1.0, 1.0, 1.0), False
    if L <= 0:
        return (0.0, 0.0, 0.0), False
    lo, hi = 0.0, C
    while hi - lo > 1e-4:
        mid = (lo + hi) / 2
        cand = _linear((L, mid, h))
        if _inside(cand):
            lo = mid
            continue
        clipped = _clip(cand)
        if math.dist(_to_oklab(clipped), _oklab((L, mid, h))) < JND:
            return clipped, False
        hi = mid
    return _clip(_linear((L, lo, h))), False


def _encode(x: float) -> float:
    return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055


def hex_of(rgb) -> str:
    return '#' + ''.join('%02x' % round(_encode(x) * 255) for x in rgb)


def luminance(rgb) -> float:
    """WCAG 2.x relative luminance of a linear-light sRGB triple (the Y the contrast and greyscale checks read)."""
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------- reading tokens.yaml

def load_yaml(path: str) -> Any:
    from ruamel.yaml import YAML
    with open(path, encoding='utf-8') as fh:
        return YAML(typ='safe', pure=True).load(fh)


def rungs(root: str = ROOT) -> list[str]:
    """The verification ladder's rung ids in rank order, read from taxonomy/verification.yaml."""
    ladder = load_yaml(os.path.join(root, VERIFICATION))['rungs']
    ranks = [r['rank'] for r in ladder]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise TokenError('%s: ranks must be 1..%d exactly once, got %s' % (VERIFICATION, len(ranks), ranks))
    return [r['id'] for r in sorted(ladder, key=lambda r: r['rank'])]


def _check_id(tid: str, seen: dict[str, str], where: str) -> None:
    if PROHIBITED.match(tid):
        raise TokenError('%s: %s is in the prohibited family-colour namespace (09 S4.2, D4): domain family is '
                         'encoded by position, label and band, never by hue' % (where, tid))
    if not TOKEN_ID.match(tid):
        raise TokenError('%s: %r is not a token id (c-* or seq-*, lowercase, hyphenated)' % (where, tid))
    if tid in seen:
        raise TokenError('%s: %s is declared twice (first in %s)' % (where, tid, seen[tid]))
    seen[tid] = where


def resolve(spec: dict, root: str = ROOT) -> list[dict]:
    """tokens.yaml's groups, each expanded to ordered rows {id, light, dark, ref, note, dark_note, rung}."""
    ladder = rungs(root)
    seen: dict[str, str] = {}
    groups = []
    for g in spec['groups']:
        rows = []
        ramp = g.get('ramp')
        if ramp:
            n = len(ramp['light'])
            if len(ramp['dark']) != n:
                raise TokenError('ramp %s: %d light steps but %d dark' % (g['id'], n, len(ramp['dark'])))
            names = [None] * n
            if ramp.get('order_from') == VERIFICATION.replace(os.sep, '/'):
                if n != len(ladder):
                    raise TokenError('ramp %s: %d steps authored but %s has %d rungs; re-author the ramp'
                                     % (g['id'], n, VERIFICATION, len(ladder)))
                names = ladder
            start = ramp.get('start', 1)
            for i in range(n):
                rows.append({'id': '%s-%d' % (ramp['prefix'], start + i), 'light': ramp['light'][i],
                             'dark': ramp['dark'][i], 'rung': names[i], 'note': names[i]})
        for tid, t in (g.get('tokens') or {}).items():
            rows.append({'id': tid, 'light': t.get('light'), 'dark': t.get('dark'), 'ref': t.get('ref'),
                         'note': t.get('note'), 'dark_note': t.get('dark_note')})
        for r in rows:
            _check_id(r['id'], seen, g['id'])
            if r.get('ref'):
                if r['light'] or r['dark']:
                    raise TokenError('%s: a ref token carries no values of its own' % r['id'])
            else:
                for theme in THEMES:
                    if not r[theme]:
                        raise TokenError('%s: no %s value; dark is authored per role, never inverted (09 S9)'
                                         % (r['id'], theme))
                    parse(r[theme])
        steps = [r for r in rows if r.get('rung', False) is not False]
        groups.append({'id': g['id'], 'title': g['title'], 'rows': rows, 'ramp': ramp, 'steps': steps})
    for g in groups:
        for r in g['rows']:
            if r.get('ref') and r['ref'] not in seen:
                raise TokenError('%s refers to %s, which is not a token' % (r['id'], r['ref']))
    _check_references(spec, seen, {g['id'] for g in groups if g['ramp']})
    return groups


def _check_references(spec: dict, tokens: dict, ramps: set[str]) -> None:
    """Every token and ramp the gate blocks name exists, so a typo there fails the build, not a check later."""
    named = []
    for sid, s in (spec.get('categorical_sets') or {}).items():
        if len(s['members']) > spec['thresholds']['categorical_max_members']:
            raise TokenError('categorical set %s has %d members; the cap is %d (09 S4.2 group B)'
                             % (sid, len(s['members']), spec['thresholds']['categorical_max_members']))
        named += [('categorical set %s' % sid, m['token']) for m in s['members']]
    named += [('absence state %s' % k, v['token']) for k, v in (spec.get('absence_states') or {}).items()]
    co = spec.get('co_occurrence') or {}
    meanings = co.get('meanings') or {}
    for mid, m in meanings.items():
        named += [('meaning %s' % mid, t) for t in m.get('tokens', [])]
        if m.get('ramp') and m['ramp'] not in ramps:
            raise TokenError('meaning %s names ramp %s, which is not a ramp group' % (mid, m['ramp']))
    for p in co.get('named_pairs') or []:
        named += [('named pair', t) for t in p['pair']]
    for where, tid in named:
        if tid not in tokens:
            raise TokenError('%s names %s, which is not a token' % (where, tid))
    for vid, v in (co.get('views') or {}).items():
        for mid in v['meanings']:
            if mid not in meanings:
                raise TokenError('view %s names meaning %s, which co_occurrence.meanings does not declare' % (vid, mid))


# ---------------------------------------------------------------- generation

def _value(row: dict, theme: str) -> str:
    return 'var(--%s)' % row['ref'] if row.get('ref') else 'oklch(%s)' % ' '.join(row[theme].split())


def _block(groups: list[dict], theme: str, indent: str) -> list[str]:
    out = []
    for g in groups:
        out.append('')
        out.append('%s/* ---------- %s ---------- */' % (indent, g['title']))
        width = max(len(r['id']) for r in g['rows']) + 3
        for r in g['rows']:
            line = '%s%s %s;' % (indent, ('--%s:' % r['id']).ljust(width), _value(r, theme))
            # S4.5's comments describe the light values; a dark line carries its own note or the rung's name
            note = r.get('note') if theme == 'light' else r.get('dark_note') or r.get('rung')
            if note:
                line = '%s  /* %s */' % (line.ljust(len(indent) + width + 26), note)
            out.append(line)
    return out


def css(groups: list[dict], spec: dict) -> str:
    head = [
        '/* site/src/styles/tokens.css -- GENERATED by tools/build/tokens.py from design/tokens.yaml',
        ' * and taxonomy/verification.yaml. Do not edit: change the YAML and run `bench build`.',
        ' * 09-design-system.md S4.5 (the light set) and S9 (dark, authored per role, not inverted).',
        ' */',
        '',
        ':root {',
        '  color-scheme: light dark;',
    ]
    body = _block(groups, 'light', '  ')
    prohibited = ['', '  /* ---------- PROHIBITED NAMESPACE ----------------------------------------']
    prohibited += ['     %s' % line for line in spec['prohibited_namespace'].strip().splitlines()]
    prohibited += ['     ------------------------------------------------------------------------ */', '}']
    dark = _block(groups, 'dark', '    ')
    dark_again = _block(groups, 'dark', '  ')
    tail = [
        '',
        ':root[data-theme="light"] {',
        '  color-scheme: light;',
        '}',
        '',
        '@media (prefers-color-scheme: dark) {',
        '  :root:not([data-theme="light"]) {',
        '    color-scheme: dark;',
    ] + dark + [
        '  }',
        '}',
        '',
        ':root[data-theme="dark"] {',
        '  color-scheme: dark;',
    ] + dark_again + ['}']
    return '\n'.join(head + body + prohibited + tail) + '\n'


def _entry(row: dict, theme: str, flat: dict[str, dict]) -> dict:
    if row.get('ref'):
        target = dict(flat[row['ref']])
        target['ref'] = row['ref']
        return target
    lch = parse(row[theme])
    rgb, ok = linear_srgb(lch)
    return {'oklch': _value(row, theme), 'l': lch[0], 'c': lch[1], 'h': lch[2], 'hex': hex_of(rgb),
            'in_gamut': ok, 'luminance': round(luminance(rgb), 6)}


def data(groups: list[dict]) -> dict:
    themes = {}
    for theme in THEMES:
        flat: dict[str, dict] = {}
        rows = [r for g in groups for r in g['rows']]
        for r in rows:
            if not r.get('ref'):
                flat[r['id']] = _entry(r, theme, flat)
        for r in rows:
            if r.get('ref'):
                flat[r['id']] = _entry(r, theme, flat)
        themes[theme] = flat
    ramps = {}
    for g in groups:
        if g['ramp']:
            entry = {'tokens': [r['id'] for r in g['steps']]}
            if any(r['rung'] for r in g['steps']):
                entry['rungs'] = [r['rung'] for r in g['steps']]
            for key in ('primary_channel', 'order_from'):
                if g['ramp'].get(key):
                    entry[key] = g['ramp'][key]
            ramps[g['id']] = entry
    return {'artifact': 'tokens', 'format': FORMAT, 'sources': [TOKENS.replace(os.sep, '/'),
            VERIFICATION.replace(os.sep, '/')], 'themes': themes, 'ramps': ramps}


def generate(root: str = ROOT) -> dict[str, bytes]:
    """{relative path: bytes} for tokens.css and tokens.json, from the tree at root."""
    spec = load_yaml(os.path.join(root, TOKENS))
    groups = resolve(spec, root)
    return {CSS_OUT: css(groups, spec).encode('utf-8'),
            JSON_OUT: (json.dumps(data(groups), ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode('utf-8')}


def write(root: str = ROOT) -> list[str]:
    written = []
    for rel, blob in generate(root).items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(blob)
        written.append(rel)
    return written


def stale(root: str = ROOT) -> list[str]:
    """The generated files that differ from a fresh generation (missing counts as differing)."""
    out = []
    for rel, blob in generate(root).items():
        path = os.path.join(root, rel)
        if not os.path.exists(path) or open(path, 'rb').read() != blob:
            out.append(rel)
    return out


def main(argv: list[str]) -> int:
    try:
        if '--check' in argv:
            bad = stale()
            for rel in bad:
                print('stale  %s: regenerate with `python tools/build/tokens.py`' % rel, file=sys.stderr)
            return 1 if bad else 0
        for rel in write():
            print('wrote %s' % rel)
        return 0
    except TokenError as e:
        print('error  %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
