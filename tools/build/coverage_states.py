#!/usr/bin/env python3
"""build/derived/coverage-states.json: the empty-or-not state of every subdomain page and coarse cell (P1-S12-T08, -T09).

    python tools/build/coverage_states.py --out build/derived/coverage-states.json [--root PATH]
    bench build --derived                                   # writes it with the other derived artifacts

02 S11 rule 6: "the coverage matrix has three cell states, not two: has-benchmarks, surveyed-and-empty, and
not-yet-surveyed ... A cell becomes surveyed-and-empty only when a curator has recorded a dated survey note".
02 S3 gives the Domain browse spine the same three states: "not-yet-surveyed is the default ...
surveyed-and-empty requires a dated survey note ... There is no third rendering and no silent blank." This
artifact is where both are decided, once, so that a subdomain page or a coverage cell can only read the state
written here.

The survey notes are data/surveys/<family>/<subdomain>.yaml (05 S2: "Dated per-capability survey notes: the
only thing that lets a coverage cell read surveyed-and-empty. One file per subdomain, not per cell"). A note's
`survey.scope.capabilities` is `all` or a list of capability terms: the fine cells (that subdomain x those
terms) its search covered, and `finding.decision: surveyed-and-empty` says it found nothing in them. Files
named `_<name>.yaml` are family-level surveys (scoping passes, cluster surveys); they date a family's survey
but never make a cell or a page read empty, because a family-wide pass that found candidates is curation
backlog, not a finding (12 S5.4 category 3).

The states, decided in this order:

  has-benchmarks       any published entry is there, primary or secondary. 02 S11 rule 1: "Cell state is
                       determined by presence at any weight", so one secondary entry is enough.
  surveyed-and-empty   nothing is there, and dated notes cover it: a SUBDOMAIN PAGE needs its own note with
                       capabilities `all`; a COARSE CELL (family x capability group) needs, for every live
                       subdomain of the family, a note whose capabilities include every term of the group,
                       since the cell is the union of those fine cells. A cell in a family that carries
                       `coverage_status: under-surveyed` never reads empty: 02 S3 has the Gap Finder "refusing
                       to assert any gap in that row".
  not-yet-surveyed     everything else, including a family-level survey that found candidates nobody has
                       curated yet.

A coarse cell has a fourth state, which 12 S5.4 calls "not a kind of empty at all" (P1-S12-T09):

  not-applicable       taxonomy/_triage/not-applicable.yaml gives the cell the verdict not-applicable: its
                       question is incoherent for the family. It is decided after has-benchmarks (an occupied
                       cell is applicable by evidence, and scripts/check_na_cells.py fails the verdict) and before
                       the survey states. A declared cell "leaves both the numerator and the denominator of every
                       coverage figure" (12 S5.4), so `coverage` below counts has-benchmarks cells over the cells
                       that are not declared. No coarse cell is tautological (12 S5.1: no family slug is a
                       capability term), so nothing else leaves the denominator.

Every cell also carries its `triage` and `rationale` (03 S7.1: "every coarse cell must be triaged as applicable
or not applicable before any gap claim publishes"): the verdict and the one-sentence reason of the cell's row in
the triage file, or null for a cell the file does not list.

Published entries are scripts/seed_progress.py's (and tools/build/gaps.py's): every Benchmark file under
data/benchmarks/<family>/, not _stubs/. The artifact has no clock in it: it is a function of the tree.
scripts/check_survey_notes.py checks the notes and that this artifact is current.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

FORMAT = 1
ARTIFACT = os.path.join('build', 'derived', 'coverage-states.json')
SURVEYS = 'data/surveys'
NOT_APPLICABLE = 'taxonomy/_triage/not-applicable.yaml'      # a record, not a vocabulary: see its header
STATES = ('has-benchmarks', 'surveyed-and-empty', 'not-yet-surveyed')
CELL_STATES = STATES + ('not-applicable',)
EMPTY = 'surveyed-and-empty'
NA = 'not-applicable'
APPLICABLE = 'applicable'
VERDICTS = (APPLICABLE, NA)
ALL = 'all'
MUTED = 'under-surveyed'


def _load(path: str):
    import yaml
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def notes(root: str = ROOT) -> list[dict]:
    """Every survey note, as {path, family, subdomain (None for a family-level note), conducted_on, decision,
    capabilities, subdomains, summary}, sorted by path. The family and subdomain come from the path, so a note
    can only speak for the page it is filed under; scripts/check_survey_notes.py asserts the note says the
    same, and the rest of its shape. This reads what is there and leaves a malformed field as None."""
    out = []
    for full in sorted(glob.glob(os.path.join(root, *SURVEYS.split('/'), '*', '*.yaml'))):
        rel = os.path.relpath(full, root).replace(os.sep, '/')
        doc = _load(full)
        doc = doc if isinstance(doc, dict) else {}
        survey = doc.get('survey') if isinstance(doc.get('survey'), dict) else {}
        finding = doc.get('finding') if isinstance(doc.get('finding'), dict) else {}
        scope = survey.get('scope') if isinstance(survey.get('scope'), dict) else {}
        when = survey.get('conducted_on')
        out.append({
            'path': rel,
            'family': rel.split('/')[2],
            'subdomain': None if os.path.basename(rel).startswith('_') else '%s/%s' % (rel.split('/')[2], os.path.basename(rel)[:-5]),
            'conducted_on': when.isoformat() if isinstance(when, date) else None,      # not a date: undated
            'decision': finding.get('decision'),
            'capabilities': scope.get('capabilities'),
            'subdomains': scope.get('subdomains'),
            'summary': finding.get('note'),
        })
    return out


def covers(note: dict, terms) -> bool:
    """Whether an empty-finding subdomain note covers every capability term in `terms`."""
    caps = note['capabilities']
    if note['decision'] != EMPTY or note['subdomain'] is None or not note['conducted_on']:
        return False
    return caps == ALL or (isinstance(caps, list) and set(terms) <= set(caps))


def triage(root: str = ROOT) -> dict:
    """{(family, group): row} for every row of the triage file; the first row wins a duplicated cell. No file is
    no triage; scripts/check_na_cells.py asserts the file's shape."""
    path = os.path.join(root, *NOT_APPLICABLE.split('/'))
    doc = _load(path) if os.path.exists(path) else {}
    doc = doc if isinstance(doc, dict) else {}
    out = {}
    for row in doc.get('cells') or []:                                                 # get-default: checked there
        if isinstance(row, dict):
            out.setdefault((row.get('family'), row.get('group')), row)
    return out


def coverage(cells: list[dict]) -> dict:
    """12 S5.4: a declared cell leaves both sides of the figure."""
    na = sum(1 for c in cells if c['state'] == NA)
    den = len(cells) - na
    hit = sum(1 for c in cells if c['state'] == 'has-benchmarks')
    return {'cells': len(cells), 'not_applicable': na, 'denominator': den, 'has_benchmarks': hit,
            'percent': round(100.0 * hit / den, 1) if den else None}


def build(root: str = ROOT) -> dict:
    from tools.build import gaps
    rows, cols = gaps.axes(root)
    domains = _load(os.path.join(root, *gaps.DOMAINS.split('/')))
    fams = {f['id']: f for f in rows['families']}
    subs = [t for t in domains['terms'] if t.get('parent') in fams and t.get('status') != 'retired']  # get-default: optional keys on a term
    subs_of = defaultdict(list)
    for t in subs:
        subs_of[t['parent']].append(t['id'])
    all_terms = [t for g in cols['groups'] for t in g['members']]

    primary, secondary = Counter(), Counter()
    for b in gaps.published(root):
        dom = b.get('domain') or {}                                                    # get-default: validated elsewhere
        p = dom.get('primary')
        primary[p] += 1
        for s in set(dom.get('secondary') or []) - {p}:                               # get-default: as above
            secondary[s] += 1

    found = notes(root)
    by_sub = defaultdict(list)
    for n in found:
        if n['subdomain']:
            by_sub[n['subdomain']].append(n)
    muted = {f for f, rec in fams.items() if rec.get('coverage_status') == MUTED}

    def survey(n):
        return {'note': n['path'], 'conducted_on': n['conducted_on']}

    pages = []
    for t in subs:
        sid = t['id']
        empty_notes = [n for n in by_sub[sid] if covers(n, all_terms)]
        if primary[sid] or secondary[sid]:
            state = 'has-benchmarks'
        elif empty_notes:
            state = EMPTY
        else:
            state = 'not-yet-surveyed'
        latest = max(empty_notes, key=lambda n: n['conducted_on']) if state == EMPTY else None
        pages.append({
            'id': sid, 'family': t['parent'], 'label': t['label'],
            'gap_placeholder': t.get('gap_placeholder') is True,                       # get-default: false unless declared
            'primary': primary[sid], 'secondary': secondary[sid],
            'state': state,
            'survey': dict(survey(latest), summary=latest['summary']) if latest else None,
        })

    occupied = {(c['family'], c['group']): c for c in gaps.coarse(root)['cells']}
    verdicts = triage(root)
    cells = []
    for f in rows['families']:
        for g in cols['groups']:
            c = occupied.get((f['id'], g['id']))
            key = (f['id'], g['id'])
            row = verdicts.get(key) or {}
            verdict = row.get('verdict') if row.get('verdict') in VERDICTS else None
            na = c is None and verdict == NA
            backing = []
            if c is None and not na and f['id'] not in muted and subs_of[f['id']]:
                per_sub = [[n for n in by_sub[s] if covers(n, g['members'])] for s in subs_of[f['id']]]
                if all(per_sub):
                    backing = sorted({n['path'] for ns in per_sub for n in ns})
            state = 'has-benchmarks' if c else NA if na else EMPTY if backing else 'not-yet-surveyed'
            cells.append({
                'family': f['id'], 'group': g['id'],
                'primary': c['entries'] if c else 0, 'secondary': c['secondary_entries'] if c else 0,
                'state': state, 'survey_notes': backing,
                'triage': verdict,
                'rationale': row.get('rationale') if verdict else None,
            })

    families = [{
        'id': f['id'], 'coverage_status': f.get('coverage_status'),                    # get-default: reported as written
        'gap_claims': 'refused' if f['id'] in muted else 'permitted',
        'survey_notes': [n['path'] for n in found if n['family'] == f['id']],
        'subdomain_states': {s: sum(1 for p in pages if p['family'] == f['id'] and p['state'] == s) for s in STATES},
        'coverage': coverage([c for c in cells if c['family'] == f['id']]),
    } for f in rows['families']]

    return {
        'artifact': 'coverage-states', 'format': FORMAT,
        'vocabularies': {'domains': rows['version'], 'capability_groups': cols['version'],
                         'capabilities': cols['terms_version']},
        'states': list(STATES),
        'cell_states': list(CELL_STATES),
        'rule': 'has-benchmarks at any weight, primary or secondary (02 S11 rule 1); a cell declared in '
                'taxonomy/_triage/not-applicable.yaml is not-applicable and leaves both sides of every coverage '
                'figure (12 S5.4); surveyed-and-empty only behind dated survey notes in data/surveys/ (02 S11 rule '
                '6, 02 S3); not-yet-surveyed otherwise. A cell in an under-surveyed family never reads '
                'surveyed-and-empty (02 S3).',
        'counts': {
            'subdomains': {s: sum(1 for p in pages if p['state'] == s) for s in STATES},
            'cells': {s: sum(1 for c in cells if c['state'] == s) for s in CELL_STATES},
            'cells_untriaged': sum(1 for c in cells if c['triage'] is None),
        },
        'coverage': coverage(cells),
        'notes': found,
        'families': families,
        'subdomains': pages,
        'cells': cells,
    }


def serialise(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + '\n').encode('utf-8')


def write(root: str = ROOT, out: str | None = None) -> str:
    path = out or os.path.join(root, ARTIFACT)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(serialise(build(root)))
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--out', default=None, help='write here; default stdout')
    a = ap.parse_args(argv)
    if a.out:
        write(a.root, a.out)
    else:
        sys.stdout.buffer.write(serialise(build(a.root)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
