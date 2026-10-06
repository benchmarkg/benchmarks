#!/usr/bin/env python3
"""The blocking WCAG contrast gate over design/tokens.yaml (P2-S2-T02; 09 S4.6, S13).

    python scripts/check_contrast.py --tokens design/tokens.yaml       # exit 1 on any failure
    python scripts/check_contrast.py --tokens design/tokens.yaml -v    # every pair, not only the failures

09 S4.6: "scripts/check_contrast.py reads tokens.yaml, computes WCAG contrast for every declared ink-on-surface
pair in both themes, and fails the build below threshold." The pairs are tokens.yaml's `contrast_pairs:`, each
with a `kind` whose floor is read from `thresholds.contrast` (text 4.5:1 and large text 3:1, SC 1.4.3; non-text
3:1, SC 1.4.11), never a constant here. Colours go through tools/build/tokens.py's OKLCH -> sRGB mapping, the one
the generated CSS and the ECharts hex share, so the gate measures the colour a screen shows. Contrast is WCAG
2.x's (L1 + 0.05) / (L2 + 0.05), compared unrounded: 4.49 is below 4.5.

`contrast_waivers:` lists known failures a person has accepted until the values are re-authored. A waived pair
prints WAIVED and passes; the build still fails when a waived pair measures worse than its recorded `measured`,
when a waiver no longer fails (it is stale: delete it), or when a waiver names a pair no `contrast_pairs` entry
declares. So the waivers can only shrink.

09 S4.6 splits the checks: this one owns text contrast and the declared non-text pairs; scripts/check_palette.py
(P2-S2-T03) owns CVD simulation and cross-meaning separation. The --c-emphasis pair is asserted in both.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.build import tokens as T  # noqa: E402

KINDS = {'text': 'SC 1.4.3', 'large_text': 'SC 1.4.3', 'non_text': 'SC 1.4.11'}
SLACK = 0.005                 # `measured` is recorded to two places; a waived pair is worse below measured - this


class ContrastError(Exception):
    """tokens.yaml's contrast blocks are malformed: a missing token, an unknown kind, an undeclared waiver."""


@dataclass(frozen=True)
class Result:
    fg: str
    on: str
    theme: str
    kind: str
    ratio: float
    floor: float
    waiver: dict | None = None

    @property
    def passes(self) -> bool:
        return self.ratio >= self.floor


def contrast(y1: float, y2: float) -> float:
    hi, lo = max(y1, y2), min(y1, y2)
    return (hi + 0.05) / (lo + 0.05)


def luminances(groups: list[dict]) -> dict[str, dict[str, float]]:
    """{theme: {token id: WCAG relative luminance}}, refs followed to the token they alias."""
    rows = {r['id']: r for g in groups for r in g['rows']}

    def value(tid, theme, seen=()):
        r = rows[tid]
        if r.get('ref'):
            if tid in seen:
                raise ContrastError('%s: a ref cycle' % tid)
            return value(r['ref'], theme, seen + (tid,))
        return T.luminance(T.linear_srgb(T.parse(r[theme]))[0])
    return {theme: {tid: value(tid, theme) for tid in rows} for theme in T.THEMES}


def pairs(spec: dict, groups: list[dict]) -> list[tuple[str, str, str]]:
    """(fg, on, kind) for every declared pair, ramps expanded to their steps."""
    known = {r['id'] for g in groups for r in g['rows']}
    steps = {g['id']: [r['id'] for r in g['steps']] for g in groups if g['ramp']}
    out = []
    for i, p in enumerate(spec.get('contrast_pairs') or []):
        if p['kind'] not in KINDS:
            raise ContrastError('contrast_pairs[%d]: kind %r is not one of %s' % (i, p['kind'], ', '.join(KINDS)))
        fg = p['fg']
        if isinstance(fg, dict):
            if fg['ramp'] not in steps:
                raise ContrastError('contrast_pairs[%d]: %s is not a ramp group' % (i, fg['ramp']))
            fgs = steps[fg['ramp']]
        else:
            fgs = [fg]
        for tid in fgs + list(p['on']):
            if tid not in known:
                raise ContrastError('contrast_pairs[%d] names %s, which is not a token' % (i, tid))
        out += [(f, on, p['kind']) for f in fgs for on in p['on']]
    if not out:
        raise ContrastError('tokens.yaml declares no contrast_pairs: there is nothing to check')
    return out


def check(spec: dict, root: str = ROOT) -> tuple[list[Result], list[str]]:
    """(every pair's result in both themes, the failures as messages). Raises ContrastError on a malformed block."""
    groups = T.resolve(spec, root)
    floors = spec['thresholds']['contrast']
    lum = luminances(groups)
    declared = pairs(spec, groups)
    waivers = {}
    for w in spec.get('contrast_waivers') or []:
        key = (w['fg'], w['on'], w['theme'])
        if not any(d[:2] == key[:2] for d in declared) or w['theme'] not in T.THEMES:
            raise ContrastError('contrast_waivers names %s on %s (%s), which no contrast_pairs entry declares'
                                % key)
        waivers[key] = w
    results, failures = [], []
    for theme in T.THEMES:
        for fg, on, kind in declared:
            r = Result(fg, on, theme, kind, contrast(lum[theme][fg], lum[theme][on]), floors[kind],
                       waivers.get((fg, on, theme)))   # get-default: most pairs have no waiver
            results.append(r)
            what = '%s %s on %s %.2f:1, %s floor %.1f:1 (%s)' % (theme, fg, on, r.ratio, kind, r.floor, KINDS[kind])
            if r.waiver is None:
                if not r.passes:
                    failures.append(what)
            elif r.passes:
                failures.append('%s, but it is waived: the waiver is stale, delete it' % what)
            elif r.ratio < r.waiver['measured'] - SLACK:
                failures.append('%s, worse than its waiver\'s %.2f:1' % (what, r.waiver['measured']))
    return results, failures


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--tokens', default=os.path.join(ROOT, T.TOKENS))
    p.add_argument('--root', default=ROOT, help='the tree whose taxonomy/verification.yaml orders the ramp')
    p.add_argument('-v', '--verbose', action='store_true')
    a = p.parse_args(argv)
    try:
        results, failures = check(T.load_yaml(a.tokens), a.root)
    except (ContrastError, T.TokenError, KeyError, TypeError) as e:
        print('check_contrast: error %s' % (e,), file=sys.stderr)
        return 1
    for r in results:
        state = 'WAIVED' if r.waiver and not r.passes else 'ok' if r.passes else 'FAIL'
        if a.verbose or state != 'ok':
            print('  %-6s %-5s %-16s on %-16s %6.2f:1  (%s >= %.1f)' % (state, r.theme, r.fg, r.on, r.ratio,
                                                                     r.kind, r.floor))
    for f in failures:
        print('check_contrast: FAIL %s' % f, file=sys.stderr)
    waived = sum(1 for r in results if r.waiver and not r.passes)
    print('check_contrast: %d pairs x %d themes = %d checks; %d failed, %d waived'
          % (len(results) // len(T.THEMES), len(T.THEMES), len(results), len(failures), waived))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
