#!/usr/bin/env python3
"""No page or coverage cell reads surveyed-and-empty without a dated survey note behind it (P1-S12-T08).

02 S3's empty-subdomain rule: "`not-yet-surveyed` is the default ... `surveyed-and-empty` requires a dated
survey note ... There is no third rendering and no silent blank." 02 S11 rule 6 says the same of the coverage
matrix, and 12 S5.4 publishes only "nobody measures it" as a gap. tools/build/coverage_states.py decides the
states into build/derived/coverage-states.json; this checks the notes it reads and the artifact it wrote.

  notes      every data/surveys/<family>/<name>.yaml is well formed: `survey.family` is its directory and a
             family in taxonomy/domains.yaml; `survey.conducted_on` is a date, not after today; `survey.method`
             says what was searched; `survey.scope` says how far. A subdomain note (<subdomain>.yaml) names
             its own subdomain, a live term of the family, carries `scope.capabilities` (`all`, or capability
             terms) and `finding.decision: surveyed-and-empty`. A family-level note (_<name>.yaml) carries
             `scope.subdomains` (`all`, or the family's subdomains) and cannot decide a page or cell empty.
  claims     no subdomain note's finding is contradicted by the corpus: no published entry, primary or
             secondary, sits in the subdomain carrying a capability the note's scope says is empty. When
             one is curated there, the note gets a dated follow-up or is retired; it is never left asserting
             a gap that has closed.
  placeholders  every `gap_placeholder: true` subdomain has a note covering all capabilities: it exists to
             read surveyed-and-empty (02 S11 rule 8).
  muted      every family carrying `coverage_status: under-surveyed` has a family-level note with its date
             and scope, and none of its cells reads surveyed-and-empty: no gap claim publishes in that row
             (02 S3, "the Gap Finder refusing to assert any gap in that row").
  artifact   build/derived/coverage-states.json exists, is what the builder makes of this tree (so a stale
             artifact fails), and every page or cell in it that reads surveyed-and-empty cites notes that
             exist, are subdomain notes with an empty finding and a date, and belong to its family.

    bench build --derived && python scripts/check_survey_notes.py          # P1-S12-T08's verify
    python scripts/check_survey_notes.py --root DIR --today 2026-11-16     # the tests
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps  # noqa: E402

ARTIFACT = 'build/derived/coverage-states.json'


def load(path):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def vocab(root):
    """(families {id: term}, subdomains {family: {id}}, capability terms)."""
    terms = load(os.path.join(root, *gaps.DOMAINS.split('/')))['terms']
    fams = {t['id']: t for t in terms if t.get('parent') is None and t.get('status') != 'retired'}  # get-default: optional keys
    subs = {f: set() for f in fams}
    for t in terms:
        if t.get('parent') in fams and t.get('status') != 'retired':                             # get-default: as above
            subs[t['parent']].add(t['id'])
    caps = {t['id'] for t in load(os.path.join(root, *gaps.CAPABILITIES.split('/')))['terms']}
    return fams, subs, caps


def check_note(path, rel, fams, subs, caps, today):
    errs = []
    family, stem = rel.split('/')[2], os.path.basename(rel)[:-5]
    doc = load(path)
    survey = doc.get('survey') if isinstance(doc, dict) else None
    if not isinstance(survey, dict):
        return ['%s: no `survey` mapping' % rel]
    finding = doc.get('finding') if isinstance(doc.get('finding'), dict) else {}
    if family not in fams:
        errs.append('%s: %s is not a domain family in %s' % (rel, family, gaps.DOMAINS))
    if survey.get('family') != family:
        errs.append('%s: survey.family %r is not its directory, %s' % (rel, survey.get('family'), family))
    when = survey.get('conducted_on')
    if not isinstance(when, dt.date):
        errs.append('%s: survey.conducted_on %r is not a date (YYYY-MM-DD)' % (rel, when))
    elif when > today:
        errs.append('%s: survey.conducted_on %s is after today, %s' % (rel, when, today))
    if not isinstance(survey.get('method'), str) or not survey['method'].strip():
        errs.append('%s: survey.method is empty: a note says what was searched' % rel)
    scope = survey.get('scope')
    if not isinstance(scope, dict):
        return errs + ['%s: no survey.scope: a note says how far its search went' % rel]
    if stem.startswith('_'):
        cover = scope.get('subdomains')
        if cover != CS.ALL and not (isinstance(cover, list) and cover and set(cover) <= subs.get(family, set())):
            errs.append('%s: scope.subdomains must be `all` or subdomains of %s, not %r' % (rel, family, cover))
        if finding.get('decision') == CS.EMPTY:
            errs.append('%s: a family-level note cannot decide anything empty; file one note per subdomain' % rel)
        return errs
    sub = '%s/%s' % (family, stem)
    if survey.get('subdomain') != sub:
        errs.append('%s: survey.subdomain %r is not the file it is in, %s' % (rel, survey.get('subdomain'), sub))
    if sub not in subs.get(family, set()):
        errs.append('%s: %s is not a live subdomain in %s' % (rel, sub, gaps.DOMAINS))
    cover = scope.get('capabilities')
    if cover != CS.ALL and not (isinstance(cover, list) and cover and set(cover) <= caps):
        errs.append('%s: scope.capabilities must be `all` or capability terms, not %r' % (rel, cover))
    if finding.get('decision') != CS.EMPTY:
        errs.append('%s: finding.decision is %r; a subdomain note records %s (a survey that found candidates is '
                    'curation backlog, not a note)' % (rel, finding.get('decision'), CS.EMPTY))
    return errs


def check_claims(root, notes):
    """A subdomain note's empty finding against the published corpus."""
    errs = []
    entries = gaps.published(root)
    for n in notes:
        if not n['subdomain'] or n['decision'] != CS.EMPTY:
            continue
        caps = n['capabilities']
        for b in entries:
            dom = b.get('domain') or {}                                                    # get-default: validated elsewhere
            if n['subdomain'] != dom.get('primary') and n['subdomain'] not in (dom.get('secondary') or []):  # get-default: as above
                continue
            hit = list(b.get('capability') or []) if caps == CS.ALL else \
                [t for t in b.get('capability') or [] if isinstance(caps, list) and t in caps]  # get-default: a stub may carry none
            if caps == CS.ALL or hit:
                errs.append('%s: says %s is surveyed-and-empty%s, but %s is filed there%s; add a dated follow-up '
                            'or retire the note' % (n['path'], n['subdomain'],
                                                    '' if caps == CS.ALL else ' for %s' % ', '.join(caps),
                                                    b.get('id'), ' with %s' % ', '.join(hit) if hit else ''))
    return errs


def check_artifact(root, path, fams, notes):
    errs = []
    if not os.path.exists(path):
        return ['%s does not exist: run `bench build --derived` first' % os.path.relpath(path, root)]
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    if doc != json.loads(CS.serialise(CS.build(root))):
        errs.append('%s is stale: it is not what tools/build/coverage_states.py makes of this tree; '
                    'run `bench build --derived` again' % os.path.relpath(path, root))
    good = {n['path']: n for n in notes if n['subdomain'] and n['decision'] == CS.EMPTY and n['conducted_on']}
    muted = {f for f, t in fams.items() if t.get('coverage_status') == CS.MUTED}
    for p in doc.get('subdomains') or []:
        if p.get('state') != CS.EMPTY:
            continue
        s = p.get('survey') or {}
        n = good.get(s.get('note'))
        if not n or n['subdomain'] != p.get('id') or not s.get('conducted_on'):
            errs.append('subdomain page %s reads %s without a dated note of its own behind it (cites %r)'
                        % (p.get('id'), CS.EMPTY, s.get('note')))
    for c in doc.get('cells') or []:
        if c.get('state') != CS.EMPTY:
            continue
        where = '(%s, %s)' % (c.get('family'), c.get('group'))
        if c.get('family') in muted:
            errs.append('cell %s reads %s, but %s is under-surveyed: no gap claim in that row'
                        % (where, CS.EMPTY, c.get('family')))
        cited = c.get('survey_notes') or []
        if not cited or any(x not in good or good[x]['family'] != c.get('family') for x in cited):
            errs.append('cell %s reads %s without dated subdomain notes of its family behind it (cites %r)'
                        % (where, CS.EMPTY, cited))
    return errs


def check(root, today, artifact):
    fams, subs, caps = vocab(root)
    errs = []
    for path in sorted(glob.glob(os.path.join(root, *CS.SURVEYS.split('/'), '*', '*.yaml'))):
        errs += check_note(path, os.path.relpath(path, root).replace(os.sep, '/'), fams, subs, caps, today)
    notes = CS.notes(root)
    errs += check_claims(root, notes)
    noted = {n['subdomain'] for n in notes if n['subdomain'] and n['decision'] == CS.EMPTY and n['capabilities'] == CS.ALL}
    terms = load(os.path.join(root, *gaps.DOMAINS.split('/')))['terms']
    for t in terms:
        if t.get('gap_placeholder') is True and t['id'] not in noted:                           # get-default: optional flag
            errs.append('%s is a gap_placeholder with no survey note covering all capabilities at %s/%s.yaml'
                        % (t['id'], CS.SURVEYS, t['id']))
    for f, t in fams.items():
        if t.get('coverage_status') == CS.MUTED and not any(n['family'] == f and n['subdomain'] is None for n in notes):
            errs.append('%s carries coverage_status: under-surveyed and has no family-level survey note '
                        '(%s/%s/_<name>.yaml) with its date and scope' % (f, CS.SURVEYS, f))
    errs += check_artifact(root, artifact, fams, notes)
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT, help='the repository root (default: this checkout)')
    ap.add_argument('--today', type=dt.date.fromisoformat, default=dt.date.today(), help='YYYY-MM-DD')
    ap.add_argument('--artifact', default=None, help='default: <root>/%s' % ARTIFACT)
    a = ap.parse_args(argv)
    artifact = a.artifact or os.path.join(a.root, *ARTIFACT.split('/'))
    errs = check(a.root, a.today, artifact)
    if errs:
        print('\n'.join('FAIL  ' + e for e in errs))
        print('%d problem(s)' % len(errs))
        return 1
    with open(artifact, encoding='utf-8') as fh:
        doc = json.load(fh)
    notes = doc['notes']
    print('OK    %d survey notes (%d subdomain, %d family-level)'
          % (len(notes), sum(1 for n in notes if n['subdomain']), sum(1 for n in notes if not n['subdomain'])))
    for kind in ('subdomains', 'cells'):
        print('      %s: %s' % ('subdomain pages' if kind == 'subdomains' else 'coarse cells',
                                ', '.join('%d %s' % (doc['counts'][kind][s], s) for s in CS.STATES)))
    empty = [p['id'] for p in doc['subdomains'] if p['state'] == 'not-yet-surveyed']
    if empty:
        print('      not yet surveyed, with no entry: %s' % ', '.join(empty))
    return 0


if __name__ == '__main__':
    sys.exit(main())
