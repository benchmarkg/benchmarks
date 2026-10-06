#!/usr/bin/env python3
"""The palette gate over design/tokens.yaml: assertion groups A-F under four CVD simulations (P2-S2-T03; 09 S4.2).

    python scripts/check_palette.py --tokens design/tokens.yaml --report build/reports/palette.json

09 S4.2 rewrites this script (and keeps its name): it reads tokens.yaml, resolves both themes, and runs six
assertion groups in normal vision and under the four simulations `thresholds.cvd` lists -- deuteranopia,
deuteranomaly at severity 50, protanopia, tritanopia (colorspacious's Machado model; CAM02-UCS for delta-E):

  A  no token id in the family-colour namespace ^c-(dom|domain|family|group)- (D4)
  B  categorical_sets: at most categorical_max_members, each with a redundant_channel; pairwise delta-E >= floor
  C  every ordered ramp strictly monotonic in perceived lightness (OKLab L after the simulation), adjacent
     step >= ramp.min_adjacent_step, end to end >= ramp.min_range unless the ramp is exempt_from: range.
     Delta-E between adjacent stops is never asserted (09 S4.2: adjacent stops are meant to be similar)
  D  co_occurrence: every pair of tokens from two meanings sharing a view, and every named pair, is
     >= delta_e_floor apart, or >= lightness_floor apart in OKLCH L, or pattern-distinguished
  E  non-text contrast at 09 S4.6's floor: tokens.yaml's non_text contrast_pairs, which include --c-emphasis
     against --c-bg and --c-ink-faint, measured on the simulated colours
  F  greyscale and forced-colors survivability: every cross-meaning pair of D >= greyscale_y_ratio_floor in
     CIE Y or pattern-distinguished; every categorical member's redundant_channel and every absence state's
     pattern is one that survives greyscale and forced-colors (glyph, pattern, or label -- 09 S4.2 (b) is the
     label carrying family in exactly those modes)

Every threshold is read from tokens.yaml's `thresholds:`, never a constant here, and every computed value goes
to the report. What fails the build (the maintainer's call, 2026-10-06):

  - A, C, E, and the structural halves of B and F block now;
  - B's delta-E, D, and F's greyscale pairs rest on floors tokens.yaml marks `status: uncalibrated`
    (delta_e_floor, greyscale_y_ratio_floor). While a floor says so, its failures are computed and reported,
    and do not fail the build; once P2-S2-T08 records a calibrated value they block.

A blocking failure can be waived: group C's in `palette_waivers:` (by ramp, theme and assertion), group E's in
the `contrast_waivers:` that scripts/check_contrast.py also reads. A group C waiver fails the build when the
ramp measures worse than its `measured` in any vision, when it no longer fails anywhere (delete it), or when it
names no such ramp. E reports a waived pair as waived in every vision; whether that waiver is stale or worse is
check_contrast.py's to decide, in normal vision, so the two gates cannot disagree about it.

Colours go through tools/build/tokens.py's OKLCH -> sRGB mapping, the one the generated CSS and the ECharts hex
share, rather than a second converter: a gate that measured a different colour from the one shipped would
measure the wrong thing.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from tools.build import tokens as T  # noqa: E402

REPORT = os.path.join(ROOT, 'build', 'reports', 'palette.json')
GROUPS = {
    'A': 'no family-colour namespace',
    'B': 'categorical sets: cap, redundant channel, pairwise delta-E',
    'C': 'ordered ramps: monotonic lightness, step, range',
    'D': 'cross-meaning separation',
    'E': 'non-text contrast',
    'F': 'greyscale and forced-colors survivability',
}
CHANNELS = ('glyph', 'pattern', 'label', 'position', 'count')      # 09 S4.2 group B
SURVIVING = ('glyph', 'pattern', 'label')                          # group F: what greyscale and forced-colors keep
FULL = {'deuteranopia': 'deuteranomaly', 'protanopia': 'protanomaly', 'tritanopia': 'tritanomaly'}
NORMAL = 'normal'
STEP_SLACK = 0.0005           # palette_waivers record L to three places


class PaletteError(Exception):
    """tokens.yaml cannot be checked: a malformed threshold, an unknown simulation, a waiver for no ramp."""


def cvd(name: str) -> dict | None:
    """colorspacious's CVD space for one of thresholds.cvd's names: 'deuteranopia', or '<type>-<severity>'."""
    if name == NORMAL:
        return None
    if name in FULL:
        return {'name': 'sRGB1+CVD', 'cvd_type': FULL[name], 'severity': 100}
    m = re.fullmatch(r'(deuteranomaly|protanomaly|tritanomaly)-(\d{1,3})', name)
    if not m or not 0 < int(m.group(2)) <= 100:
        raise PaletteError('thresholds.cvd: %r is not a simulation (deuteranopia, protanopia, tritanopia, or '
                           '<deuteranomaly|protanomaly|tritanomaly>-<1..100>)' % name)
    return {'name': 'sRGB1+CVD', 'cvd_type': m.group(1), 'severity': int(m.group(2))}


def floor(th: dict, key: str) -> tuple[float, bool]:
    """(value, calibrated) for a threshold written as {value, status}."""
    t = th[key]
    if not isinstance(t, dict) or 'value' not in t or 'status' not in t:
        raise PaletteError('thresholds.%s must be {value, status}' % key)
    return float(t['value']), t['status'] != 'uncalibrated'


# ---- colour ---------------------------------------------------------------------------------------------

def _decode(x: float) -> float:
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


class Colours:
    """One theme's tokens under one vision: sRGB, CAM02-UCS, OKLab L and WCAG Y, refs followed."""

    def __init__(self, groups: list[dict], theme: str, vision: str):
        import numpy as np
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)     # colorspacious 1.1.2's docstrings, on first import
            import colorspacious as cs
        rows = {r['id']: r for g in groups for r in g['rows']}

        def base(tid):
            while rows[tid].get('ref'):
                tid = rows[tid]['ref']
            return tid
        self.ids = list(rows)
        rgb = np.array([[T._encode(x) for x in T.linear_srgb(T.parse(rows[base(t)][theme]))[0]] for t in self.ids])
        space = cvd(vision)
        if space is not None:
            rgb = np.clip(cs.cspace_convert(rgb, space, 'sRGB1'), 0, 1)
        ucs = cs.cspace_convert(rgb, 'sRGB1', 'CAM02-UCS')
        self.ucs = {t: ucs[i] for i, t in enumerate(self.ids)}
        lin = [[_decode(float(x)) for x in row] for row in rgb]
        self.l = {t: T._to_oklab(lin[i])[0] for i, t in enumerate(self.ids)}
        self.y = {t: T.luminance(lin[i]) for i, t in enumerate(self.ids)}

    def delta_e(self, a: str, b: str) -> float:
        import numpy as np
        return float(np.linalg.norm(self.ucs[a] - self.ucs[b]))

    def ratio(self, a: str, b: str) -> float:
        ya, yb = self.y[a], self.y[b]
        return (max(ya, yb) + 0.05) / (min(ya, yb) + 0.05)


# ---- the checker ----------------------------------------------------------------------------------------

class Run:
    def __init__(self, spec: dict, root: str = ROOT):
        self.spec, self.root = spec, root
        self.th = spec['thresholds']
        self.visions = [NORMAL] + list(self.th['cvd'])
        for v in self.visions:
            cvd(v)
        self.de_floor, self.de_calibrated = floor(self.th, 'delta_e_floor')
        self.y_floor, self.y_calibrated = floor(self.th, 'greyscale_y_ratio_floor')
        self.findings: list[dict] = []
        self.values: dict = {}
        self.checks = {g: 0 for g in GROUPS}

    def find(self, group, theme, vision, subject, message, blocking=True, waived=None):
        self.findings.append({'group': group, 'theme': theme, 'vision': vision, 'subject': subject,
                              'message': message, 'blocking': blocking, 'waived': waived})

    # A (and B's cap, in structural()): before anything resolves, because tools/build/tokens.py refuses both
    def group_a(self) -> bool:
        ids = []
        for g in self.spec['groups']:
            ids += list((g.get('tokens') or {}))
            if g.get('ramp'):
                ids.append(g['ramp']['prefix'] + '-*')
        bad = [t for t in ids if T.PROHIBITED.match(t)]
        self.checks['A'] += len(ids)
        for t in bad:
            for theme in T.THEMES:
                for v in self.visions:
                    self.find('A', theme, v, t, '%s is in the prohibited family-colour namespace (09 S4.2, D4)' % t)
        return not bad

    def structural(self) -> None:
        """B's cap and channels, F's survivable channels: the same in every theme and vision, checked once."""
        cap = self.th['categorical_max_members']
        for sid, s in (self.spec.get('categorical_sets') or {}).items():
            self.checks['B'] += 1
            if len(s['members']) > cap:
                self.find('B', None, None, sid, '%d members; the cap is %d' % (len(s['members']), cap))
                self.findings[-1]['assertion'] = 'cap'
            for m in s['members']:
                self.checks['B'] += 1
                self.checks['F'] += 1
                ch = m.get('redundant_channel')               # get-default: a missing channel is the failure
                if ch not in CHANNELS:
                    self.find('B', None, None, m['token'], 'redundant_channel %r is not one of %s'
                              % (ch, ', '.join(CHANNELS)))
                if ch not in SURVIVING:
                    self.find('F', None, None, m['token'], 'redundant_channel %r does not survive greyscale and '
                              'forced-colors (needs %s)' % (ch, ', '.join(SURVIVING)))
        for state, a in (self.spec.get('absence_states') or {}).items():
            self.checks['F'] += 1
            if not a.get('pattern'):                           # get-default: a missing pattern is the failure
                self.find('F', None, None, state, 'absence state declares no pattern or glyph')

    def cell(self, groups: list[dict], theme: str, vision: str) -> None:
        c = Colours(groups, theme, vision)
        out = self.values.setdefault(theme, {}).setdefault(vision, {})
        steps = {g['id']: [r['id'] for r in g['steps']] for g in groups if g['ramp']}
        ramps = {g['id']: g['ramp'] for g in groups if g['ramp']}

        # B: pairwise delta-E within each categorical set
        out['B'] = {}
        for sid, s in (self.spec.get('categorical_sets') or {}).items():
            for a, b in itertools.combinations([m['token'] for m in s['members']], 2):
                d = c.delta_e(a, b)
                self.checks['B'] += 1
                out['B']['%s|%s' % (a, b)] = round(d, 3)
                if d < self.de_floor:
                    self.find('B', theme, vision, '%s|%s' % (a, b),
                              'delta-E %.1f < %g in set %s' % (d, self.de_floor, sid), blocking=self.de_calibrated)

        # C: ordered ramps
        out['C'] = {}
        rt = self.th['ramp']
        for rid, ids in steps.items():
            ls = [c.l[t] for t in ids]
            diffs = [b - a for a, b in zip(ls, ls[1:])]
            step, rng = min(abs(d) for d in diffs), abs(ls[-1] - ls[0])
            mono = all(d > 0 for d in diffs) or all(d < 0 for d in diffs)
            exempt = (ramps[rid].get('exempt_from') or {})
            out['C'][rid] = {'l': [round(x, 4) for x in ls], 'min_adjacent_step': round(step, 4),
                             'range': round(rng, 4), 'monotonic': mono}
            self.checks['C'] += 3
            if not mono:
                self.ramp_fail(rid, theme, vision, 'monotonic', None, 'not strictly monotonic in perceived lightness')
            if step < rt['min_adjacent_step']:
                self.ramp_fail(rid, theme, vision, 'min_adjacent_step', step,
                               'adjacent step %.3f L < %g' % (step, rt['min_adjacent_step']))
            if rng < rt['min_range'] and 'range' not in exempt:
                self.ramp_fail(rid, theme, vision, 'min_range', rng, 'range %.3f L < %g' % (rng, rt['min_range']))

        # D and F: the cross-meaning pairs
        co = self.spec.get('co_occurrence') or {}
        meanings = co.get('meanings') or {}

        def toks(m):
            return steps[m['ramp']] if m.get('ramp') else m['tokens']
        pairs: dict[tuple[str, str], dict] = {}
        for vid, view in (co.get('views') or {}).items():
            for m1, m2 in itertools.combinations(view['meanings'], 2):
                pattern = bool(meanings[m1].get('pattern_distinguished') or meanings[m2].get('pattern_distinguished'))
                for a in toks(meanings[m1]):
                    for b in toks(meanings[m2]):
                        p = pairs.setdefault(tuple(sorted((a, b))), {'views': set(), 'pattern': True})
                        p['views'].add(vid)
                        p['pattern'] = p['pattern'] and pattern    # told apart by pattern in every view it is in
        for np_ in co.get('named_pairs') or []:
            p = pairs.setdefault(tuple(sorted(np_['pair'])), {'views': set(), 'pattern': False})
            p['views'].add('named-pair')
            p['pattern'] = False                                   # a named pair is asserted on colour, always
        out['D'], out['F'] = {}, {}
        for (a, b), p in sorted(pairs.items()):
            key = '%s|%s' % (a, b)
            d, dl, y = c.delta_e(a, b), abs(c.l[a] - c.l[b]), c.ratio(a, b)
            self.checks['D'] += 1
            self.checks['F'] += 1
            out['D'][key] = {'delta_e': round(d, 3), 'delta_l': round(dl, 4), 'pattern': p['pattern'],
                             'views': sorted(p['views'])}
            out['F'][key] = {'y_ratio': round(y, 4), 'pattern': p['pattern']}
            if p['pattern']:
                continue
            if d < self.de_floor and dl < self.th['lightness_floor']:
                self.find('D', theme, vision, key, 'delta-E %.1f < %g and delta-L %.3f < %g (%s)'
                          % (d, self.de_floor, dl, self.th['lightness_floor'], ', '.join(sorted(p['views']))),
                          blocking=self.de_calibrated)
            if y < self.y_floor:
                self.find('F', theme, vision, key, 'greyscale Y ratio %.2f < %g (%s)'
                          % (y, self.y_floor, ', '.join(sorted(p['views']))), blocking=self.y_calibrated)

        # E: non-text contrast on the simulated colours
        import check_contrast
        waivers = {(w['fg'], w['on'], w['theme']) for w in self.spec.get('contrast_waivers') or []}
        out['E'] = {}
        floor_e = self.th['contrast']['non_text']
        for fg, on, kind in check_contrast.pairs(self.spec, groups):
            if kind != 'non_text':
                continue
            r = c.ratio(fg, on)
            self.checks['E'] += 1
            out['E']['%s|%s' % (fg, on)] = round(r, 4)
            if r < floor_e:
                waived = 'contrast_waivers' if (fg, on, theme) in waivers else None
                self.find('E', theme, vision, '%s|%s' % (fg, on), 'non-text contrast %.2f:1 < %g:1' % (r, floor_e),
                          waived=waived)

    def ramp_fail(self, rid, theme, vision, assertion, measured, message):
        self.find('C', theme, vision, rid, message, waived=None)
        self.findings[-1].update(assertion=assertion, measured=measured)

    def apply_ramp_waivers(self, ramp_ids: set[str]) -> None:
        """Mark each C failure a palette_waivers entry covers; fail the stale, the worse and the unknown."""
        for w in self.spec.get('palette_waivers') or []:
            if w['group'] != 'C' or w['ramp'] not in ramp_ids or w['theme'] not in T.THEMES:
                raise PaletteError('palette_waivers names %s %s (%s), which is no ramp of group C'
                                   % (w['group'], w['ramp'], w['theme']))
            hit = [f for f in self.findings if f['group'] == 'C' and f['subject'] == w['ramp']
                   and f['theme'] == w['theme'] and f.get('assertion') == w['assertion']]
            if not hit:
                self.find('C', w['theme'], None, w['ramp'], 'the %s waiver no longer fails in any vision: it is '
                          'stale, delete it' % w['assertion'])
            for f in hit:
                if f['measured'] is not None and f['measured'] < w['measured'] - STEP_SLACK:
                    f['message'] += ", worse than its waiver's %.3f" % w['measured']
                else:
                    f['waived'] = 'palette_waivers'

    def run(self) -> None:
        ok = self.group_a()
        self.structural()
        if not ok or any(f['group'] == 'B' and f.get('assertion') == 'cap' for f in self.findings):
            return                      # tools/build/tokens.py refuses to resolve either; the colour groups cannot run
        groups = T.resolve(self.spec, self.root)
        for theme in T.THEMES:
            for v in self.visions:
                self.cell(groups, theme, v)
        self.apply_ramp_waivers({g['id'] for g in groups if g['ramp']})

    def failures(self) -> list[dict]:
        return [f for f in self.findings if f['blocking'] and not f['waived']]

    def report(self) -> dict:
        gates = {}
        for g, title in GROUPS.items():
            mine = [f for f in self.findings if f['group'] == g]
            gates[g] = {'title': title, 'checks': self.checks[g],
                        'failed': sum(1 for f in mine if f['blocking'] and not f['waived']),
                        'reported': sum(1 for f in mine if not f['blocking']),
                        'waived': sum(1 for f in mine if f['waived'])}
        return {'artifact': 'palette-report', 'source': T.TOKENS.replace(os.sep, '/'), 'themes': list(T.THEMES),
                'visions': self.visions, 'thresholds': self.th,
                'blocking': {'delta_e_floor': self.de_calibrated, 'greyscale_y_ratio_floor': self.y_calibrated},
                'groups': gates, 'passed': not self.failures(), 'findings': self.findings, 'values': self.values}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--tokens', default=os.path.join(ROOT, T.TOKENS))
    p.add_argument('--report', default=REPORT)
    p.add_argument('--root', default=ROOT, help='the tree whose taxonomy/verification.yaml orders the ramp')
    p.add_argument('-v', '--verbose', action='store_true', help='print the reported (non-blocking) findings too')
    a = p.parse_args(argv)
    try:
        r = Run(T.load_yaml(a.tokens), a.root)
        r.run()
    except (PaletteError, T.TokenError, KeyError, TypeError) as e:
        print('check_palette: error %s' % (e,), file=sys.stderr)
        return 1
    doc = r.report()
    os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
    with open(a.report, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, indent=1, sort_keys=True, default=sorted)
        f.write('\n')
    for f in r.findings:
        state = 'WAIVED' if f['waived'] else 'FAIL' if f['blocking'] else 'report'
        if state != 'report' or a.verbose:
            print('  %-6s %s %-5s %-16s %s: %s' % (state, f['group'], f['theme'] or 'both', f['vision'] or 'all',
                                                   f['subject'], f['message']))
    for g, s in doc['groups'].items():
        print('  group %s %-58s %5d checks  %3d failed  %4d reported  %3d waived'
              % (g, s['title'], s['checks'], s['failed'], s['reported'], s['waived']))
    for f in r.failures():
        print('check_palette: FAIL group %s %s %s %s: %s' % (f['group'], f['theme'] or 'both', f['vision'] or 'all',
                                                             f['subject'], f['message']), file=sys.stderr)
    print('check_palette: %s; wrote %s' % ('passed' if doc['passed'] else '%d blocking failure(s)' % len(r.failures()),
                                           a.report))
    return 0 if doc['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
