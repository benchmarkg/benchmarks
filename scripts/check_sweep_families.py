#!/usr/bin/env python3
"""The sweep's family list is the domain vocabulary, exactly (P1-S12-T01; 06 S6).

06 S6: "The family column is emitted from taxonomy/domains.yaml ..., and a CI check asserts that the
sweep checklist's family list is exactly the domain vocabulary. Without that check, these two
documents drift within a quarter -- which is precisely how the corpus came to carry both 'eighteen
families' and 'nineteen families' simultaneously." This is that check. It asserts:

  families   docs/sweeps/hubs.yaml has one block per family in taxonomy/domains.yaml: none missing,
             none extra, none twice. Every block is well formed (cadence, focus, hubs with a name,
             an https URL or a null one with a note, a mode), and every family has at least one hub
             of its own or a shared one.
  06 S6      the plan's cadence table lists exactly the same families, at the same cadence (and
             capped where it says capped), and its effort table's tier counts are the ones the hub
             file implies. Either side drifting fails.
  checklist  docs/sweeps/checklist.md carries 06 S6's ten-line checklist verbatim, and its cadence
             table is the one this script generates from domains.yaml and hubs.yaml.

    python scripts/check_sweep_families.py            # check; exit 0 if all hold, 1 otherwise
    python scripts/check_sweep_families.py --write    # regenerate the table in checklist.md
    python scripts/check_sweep_families.py --root DIR # run against another tree (the tests do)
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOMAINS = 'taxonomy/domains.yaml'
HUBS = 'docs/sweeps/hubs.yaml'
CHECKLIST = 'docs/sweeps/checklist.md'
PLAN_06 = '_plan/06-sourcing-and-scraping.md'

CADENCES = ('quarterly', 'semi-annual', 'annual')
FOCI = ('discovery', 'lineage', 'survey')
MODES = ('manual', 'api')
FAMILY_KEYS = {'family', 'cadence', 'capped', 'focus', 'anchor_events', 'catches', 'hubs', 'seeded_from'}
HUB_KEYS = {'name', 'url', 'mode', 'unverified', 'note'}
SHARED_KEYS = HUB_KEYS | {'cadence', 'must_not_drop', 'families'}

BEGIN = '<!-- gen: scripts/check_sweep_families.py --write; edit docs/sweeps/hubs.yaml, not this table -->'
END = '<!-- /gen -->'
CHECKBOXES = 10


def read(root, rel):
    with open(os.path.join(root, rel), encoding='utf-8') as fh:
        return fh.read()


def families(root):
    """The domain families, in domains.yaml order: the terms with no parent."""
    doc = yaml.safe_load(read(root, DOMAINS))
    return [t['id'] for t in doc['terms'] if t.get('parent') is None]


def hub_file(root):
    return yaml.safe_load(read(root, HUBS))


# ---- the hub file ---------------------------------------------------------------------------------

def check_hubs(doc, fams):
    errs = []
    blocks = doc.get('families') or []
    seen = [b.get('family') for b in blocks]
    dupes = sorted({f for f in seen if seen.count(f) > 1})
    missing = [f for f in fams if f not in seen]
    extra = [f for f in seen if f not in fams]
    if dupes:
        errs.append('hubs.yaml lists %s more than once' % ', '.join(map(str, dupes)))
    if missing:
        errs.append('hubs.yaml has no block for %s' % ', '.join(missing))
    if extra:
        errs.append('hubs.yaml names %s, which is not a family in %s' % (', '.join(map(str, extra)), DOMAINS))

    for b in blocks:
        fam = b.get('family')
        where = 'hubs.yaml %s' % fam
        unknown = set(b) - FAMILY_KEYS
        if unknown:
            errs.append('%s: unknown key %s' % (where, ', '.join(sorted(unknown))))
        if b.get('cadence') not in CADENCES:
            errs.append('%s: cadence %r is not one of %s' % (where, b.get('cadence'), ', '.join(CADENCES)))
        if b.get('focus') not in FOCI:
            errs.append('%s: focus %r is not one of %s' % (where, b.get('focus'), ', '.join(FOCI)))
        if 'capped' in b and not isinstance(b['capped'], bool):
            errs.append('%s: capped must be true or false' % where)
        for k in ('anchor_events', 'catches'):
            if not str(b.get(k) or '').strip():
                errs.append('%s: %s is empty' % (where, k))
        if not isinstance(b.get('hubs'), list):
            errs.append('%s: hubs must be a list (an empty one when only a shared hub serves it)' % where)
            continue
        errs += check_hub_list(b['hubs'], where, HUB_KEYS)

    shared = doc.get('shared_hubs') or []
    errs += check_hub_list(shared, 'hubs.yaml shared_hubs', SHARED_KEYS)
    for h in shared:
        bad = [f for f in h.get('families') or [] if f not in fams]
        if not h.get('families'):
            errs.append('hubs.yaml shared hub %r serves no family' % h.get('name'))
        if bad:
            errs.append('hubs.yaml shared hub %r names %s, not a family' % (h.get('name'), ', '.join(map(str, bad))))
        if 'cadence' in h and h['cadence'] not in CADENCES:
            errs.append('hubs.yaml shared hub %r: cadence %r is not one of %s' % (h.get('name'), h['cadence'], ', '.join(CADENCES)))

    served = {f for h in shared for f in h.get('families') or []}
    for b in blocks:
        if isinstance(b.get('hubs'), list) and not b['hubs'] and b.get('family') not in served:
            errs.append('hubs.yaml %s has no hub of its own and no shared hub serves it' % b.get('family'))
    return errs


def check_hub_list(hubs, where, keys):
    errs = []
    urls = [h.get('url') for h in hubs if isinstance(h, dict) and h.get('url')]
    for u in sorted({u for u in urls if urls.count(u) > 1}):
        errs.append('%s: %s is listed twice' % (where, u))
    for h in hubs:
        if not isinstance(h, dict):
            errs.append('%s: a hub must be a mapping, not %r' % (where, h))
            continue
        name = str(h.get('name') or '').strip()
        label = '%s hub %r' % (where, name or '?')
        if not name:
            errs.append('%s: a hub has no name' % where)
        unknown = set(h) - keys
        if unknown:
            errs.append('%s: unknown key %s' % (label, ', '.join(sorted(unknown))))
        if h.get('mode') not in MODES:
            errs.append('%s: mode %r is not one of %s' % (label, h.get('mode'), ', '.join(MODES)))
        url = h.get('url')
        if 'url' not in h:
            errs.append('%s: no url key (write url: null with a note when the page is not known)' % label)
        elif url is None:
            if not str(h.get('note') or '').strip():
                errs.append('%s: url is null and there is no note saying why' % label)
        elif not re.match(r'^https://[^\s/]+\.[^\s]+$', str(url)):
            errs.append('%s: url %r is not an https URL' % (label, url))
    return errs


# ---- 06 S6 ----------------------------------------------------------------------------------------

def _section(text, heading):
    start = text.index(heading)
    nxt = re.search(r'^#{2,3} ', text[start + len(heading):], re.M)
    return text[start:start + len(heading) + nxt.start()] if nxt else text[start:]


def _rows(section, header_prefix):
    lines = section.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(header_prefix))
    rows = []
    for line in lines[i + 2:]:
        if not line.startswith('|'):
            break
        rows.append([c.strip() for c in line.strip().strip('|').split('|')])
    return rows


def plan_cadences(text):
    """06 S6's cadence table: family -> (cadence, capped)."""
    out = []
    for cells in _rows(_section(text, '### Cadence by domain family'), '| Family | Cadence |'):
        raw = cells[1].replace('*', '').strip().lower()
        out.append((cells[0], raw.split(',')[0].strip(), 'capped' in raw))
    return out


def plan_tiers(text):
    """06 S6's effort table: tier -> number of families, and the total."""
    tiers, total = {}, None
    for cells in _rows(_section(text, '### Effort, recomputed against'), '| Tier | Families |'):
        tier = cells[0].replace('*', '').strip().lower()
        n = int(re.match(r'\**(\d+)', cells[1]).group(1))
        if tier == 'total':
            total = n
        else:
            tiers[tier] = n
    return tiers, total


def plan_checklist(text):
    m = re.search(r'```\n(SWEEP:.*?)\n```', _section(text, '### The sweep checklist'), re.S)
    return m.group(1)


def check_plan(doc, fams, text):
    errs = []
    rows = plan_cadences(text)
    listed = [r[0] for r in rows]
    if sorted(listed) != sorted(fams) or len(listed) != len(set(listed)):
        missing = [f for f in fams if f not in listed]
        extra = [f for f in listed if f not in fams]
        twice = sorted({f for f in listed if listed.count(f) > 1})
        errs.append('06 S6 cadence table is not the domain vocabulary: missing %s, extra %s, twice %s'
                    % (missing or '-', extra or '-', twice or '-'))
    mine = {b.get('family'): b for b in doc.get('families') or []}
    for fam, cadence, capped in rows:
        b = mine.get(fam)
        if b is None:
            continue
        if b.get('cadence') != cadence:
            errs.append('%s: hubs.yaml says %s, 06 S6 says %s' % (fam, b.get('cadence'), cadence))
        if bool(b.get('capped')) != capped:
            errs.append('%s: 06 S6 %s it capped, hubs.yaml %s' % (fam, 'calls' if capped else 'does not call',
                                                                  'does' if b.get('capped') else 'does not'))
    tiers, total = plan_tiers(text)
    counts = {c: sum(1 for b in mine.values() if b.get('cadence') == c) for c in CADENCES}
    for c in CADENCES:
        if tiers.get(c) != counts[c]:
            errs.append('06 S6 effort table puts %s families in the %s tier; hubs.yaml has %d'
                        % (tiers.get(c), c, counts[c]))
    if total != len(fams):
        errs.append('06 S6 effort table totals %s families; the vocabulary has %d' % (total, len(fams)))
    return errs


# ---- docs/sweeps/checklist.md ---------------------------------------------------------------------

def render_table(doc, fams):
    """The cadence table: one row per family, by tier, then in domains.yaml order."""
    shared = doc.get('shared_hubs') or []
    by = {b['family']: b for b in doc['families']}
    order = sorted(fams, key=lambda f: (CADENCES.index(by[f]['cadence']), fams.index(f)))
    lines = ['| Family | Cadence | Focus | Hubs | Anchor events |', '| --- | --- | --- | --- | --- |']
    for f in order:
        b = by[f]
        n_shared = sum(1 for h in shared if f in h['families'])
        hubs = str(len(b['hubs'])) + (' + %d shared' % n_shared if n_shared else '')
        cadence = b['cadence'] + (', capped' if b.get('capped') else '')
        lines.append('| %s | %s | %s | %s | %s |' % (f, cadence, b['focus'], hubs, b['anchor_events'].strip()))
    counts = [(c, sum(1 for b in by.values() if b['cadence'] == c)) for c in CADENCES]
    lines += ['', '%s: %d families.' % (', '.join('%s %d' % (c.capitalize() if i == 0 else c, n)
                                                for i, (c, n) in enumerate(counts)), len(fams))]
    return '\n'.join(lines)


def generated_block(text):
    if BEGIN not in text or END not in text.split(BEGIN, 1)[1]:
        return None
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip('\n')


def check_checklist(doc, fams, text, plan):
    errs = []
    m = re.search(r'```\n(SWEEP:.*?)\n```', text, re.S)
    if not m:
        errs.append('checklist.md has no fenced SWEEP: checklist')
    else:
        boxes = [l for l in m.group(1).splitlines() if l.strip().startswith('[ ]')]
        if len(boxes) != CHECKBOXES:
            errs.append('checklist.md has %d checklist lines, not %d' % (len(boxes), CHECKBOXES))
        if m.group(1) != plan_checklist(plan):
            errs.append("checklist.md's checklist is not 06 S6's, line for line")
    block = generated_block(text)
    if block is None:
        errs.append('checklist.md has no generated cadence table (run --write)')
    elif block != render_table(doc, fams):
        errs.append("checklist.md's cadence table is stale or hand-edited (run --write)")
    return errs


def write_checklist(root, doc, fams):
    path = os.path.join(root, CHECKLIST)
    text = read(root, CHECKLIST)
    if generated_block(text) is None:
        raise SystemExit('%s has no %s ... %s markers to write between' % (CHECKLIST, BEGIN, END))
    head, rest = text.split(BEGIN, 1)
    tail = rest.split(END, 1)[1]
    new = head + BEGIN + '\n' + render_table(doc, fams) + '\n' + END + tail
    if new != text:
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(new)
    return new != text


def run(root):
    fams = families(root)
    doc = hub_file(root)
    errs = check_hubs(doc, fams)
    plan = read(root, PLAN_06)
    errs += check_plan(doc, fams, plan)
    if not any(e.startswith('hubs.yaml') for e in errs):  # the table renders only from a well-formed file
        errs += check_checklist(doc, fams, read(root, CHECKLIST), plan)
    return fams, doc, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT, help='the repository root (default: this checkout)')
    ap.add_argument('--write', action='store_true', help="regenerate checklist.md's cadence table")
    a = ap.parse_args(argv)
    if a.write:
        fams, doc = families(a.root), hub_file(a.root)
        errs = check_hubs(doc, fams)
        if errs:
            print('\n'.join('FAIL  ' + e for e in errs))
            return 1
        print('%s %s' % (CHECKLIST, 'rewritten' if write_checklist(a.root, doc, fams) else 'already current'))
    fams, doc, errs = run(a.root)
    if errs:
        print('\n'.join('FAIL  ' + e for e in errs))
        print('%d problem(s)' % len(errs))
        return 1
    n_hubs = sum(len(b['hubs']) for b in doc['families']) + len(doc.get('shared_hubs') or [])
    print('OK    %d families in %s, %s and 06 S6; %d hubs; checklist.md current'
          % (len(fams), DOMAINS, HUBS, n_hubs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
