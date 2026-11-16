#!/usr/bin/env python3
"""Every coarse cell is triaged, and every not-applicable one leaves both sides of every coverage figure (P1-S12-T09).

12 S5.4: "A cell can be declared not applicable -- the question it asks is incoherent for that family -- and a
declared cell leaves both the numerator and the denominator of every coverage figure". 03 S7.1: "every coarse
cell must be triaged as applicable or not applicable before any gap claim publishes", and "A cell declared
not-applicable carries the declaring curator, the date and a one-line reason". The triage is
taxonomy/_triage/not-applicable.yaml, one row per coarse cell; tools/build/coverage_states.py applies it. This
asserts:

  shape      the file holds `version`, `updated`, `accepted_by` and `cells`, and every row names a family of
             taxonomy/domains.yaml and a group of taxonomy/capability_groups.yaml, a `verdict` (applicable or
             not-applicable), a rationale of one sentence, a `declared_by` and a `declared_on` date not after
             today.
  triaged    every cell of the grid has exactly one row: "before any gap claim publishes". A new family or
             group adds cells, and the pull request that adds it triages them.
  evidence   no not-applicable cell is occupied: an entry in it, primary or secondary, shows its question is
             coherent, and the verdict is withdrawn (03 S7.1, "reversible when a field moves").
  no blanket chemistry-materials x autonomy-and-oversight is never declared (02 S4.3, 12 S5.4: "autonomous
             laboratories make [it] a live and informative cell"); no group is declared in a majority of the
             families, which would be a column declared by rule rather than cell by cell; and no family has
             every group declared.
  artifact   build/derived/coverage-states.json is what the builder makes of this tree, every declared cell
             in it reads not-applicable with its rationale and no other cell does, and its coverage figures,
             overall and per family, count has-benchmarks cells over the cells left after the declared ones.

    bench build --derived && python scripts/check_na_cells.py          # P1-S12-T09's verify
    python scripts/check_na_cells.py --root DIR --today 2026-11-16     # the tests
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps  # noqa: E402

ARTIFACT = 'build/derived/coverage-states.json'
DOC_KEYS = {'version', 'updated', 'accepted_by', 'cells'}
ROW_KEYS = {'family', 'group', 'verdict', 'rationale', 'declared_by', 'declared_on'}
SEMVER = re.compile(r'^\d+\.\d+\.\d+$')
NEVER_DECLARED = {('chemistry-materials', 'autonomy-and-oversight')}   # 02 S4.3, 03 S7.1, 12 S5.4
SECOND_SENTENCE = re.compile(r'[.!?]\s+[A-Z]')


def load(path):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def one_sentence(text):
    return isinstance(text, str) and text.strip().endswith('.') and not SECOND_SENTENCE.search(text.strip()[:-1])


def check_file(root, today):
    """(errors, {cell: verdict}) for the triage file; a cell listed twice keeps its first row."""
    path = os.path.join(root, *CS.NOT_APPLICABLE.split('/'))
    if not os.path.exists(path):
        return ['%s does not exist: every coarse cell must be triaged (03 S7.1)' % CS.NOT_APPLICABLE], {}
    doc = load(path)
    if not isinstance(doc, dict) or not isinstance(doc.get('cells'), list):
        return ['%s: needs a list `cells`, one row per coarse cell' % CS.NOT_APPLICABLE], {}
    errs = []
    if set(doc) != DOC_KEYS:
        errs.append('%s: keys must be %s, not %s' % (CS.NOT_APPLICABLE, sorted(DOC_KEYS), sorted(doc)))
    if not isinstance(doc.get('version'), str) or not SEMVER.match(doc['version']):
        errs.append('%s: version %r is not semver' % (CS.NOT_APPLICABLE, doc.get('version')))
    if not isinstance(doc.get('updated'), dt.date) or doc['updated'] > today:
        errs.append('%s: updated %r is not a date on or before today' % (CS.NOT_APPLICABLE, doc.get('updated')))
    if doc.get('accepted_by') is not None and (not isinstance(doc['accepted_by'], str) or not doc['accepted_by'].strip()):
        errs.append('%s: accepted_by is null or names who accepted the triage' % CS.NOT_APPLICABLE)
    rows, cols = gaps.axes(root)
    fams, grps = {f['id'] for f in rows['families']}, {g['id'] for g in cols['groups']}
    seen = {}
    for i, row in enumerate(doc['cells']):
        where = '%s cells[%d]' % (CS.NOT_APPLICABLE, i)
        if not isinstance(row, dict):
            errs.append('%s is not a mapping' % where)
            continue
        cell = (row.get('family'), row.get('group'))
        where = '%s (%s, %s)' % (where, cell[0], cell[1])
        if set(row) != ROW_KEYS:
            errs.append('%s: keys must be %s, not %s' % (where, sorted(ROW_KEYS), sorted(row)))
        if cell[0] not in fams:
            errs.append('%s: %r is not a family in %s' % (where, cell[0], gaps.DOMAINS))
        if cell[1] not in grps:
            errs.append('%s: %r is not a group in %s' % (where, cell[1], gaps.GROUPS))
        if row.get('verdict') not in CS.VERDICTS:
            errs.append('%s: verdict %r is not one of %s' % (where, row.get('verdict'), ', '.join(CS.VERDICTS)))
        if cell in seen:
            errs.append('%s: the cell already has a row; one row per cell' % where)
        seen.setdefault(cell, row.get('verdict'))
        if not one_sentence(row.get('rationale')):
            errs.append('%s: the rationale must be one sentence ending in a full stop' % where)
        if not isinstance(row.get('declared_by'), str) or not row['declared_by'].strip():
            errs.append('%s: no declared_by: a verdict names its curator' % where)
        when = row.get('declared_on')
        if not isinstance(when, dt.date):
            errs.append('%s: declared_on %r is not a date (YYYY-MM-DD)' % (where, when))
        elif when > today:
            errs.append('%s: declared_on %s is after today, %s' % (where, when, today))
    return errs, seen


def check(root, today, artifact):
    errs, verdicts = check_file(root, today)
    rows, cols = gaps.axes(root)
    occupied = {(c['family'], c['group']) for c in gaps.coarse(root)['cells']}
    declared = {c for c, verdict in verdicts.items() if verdict == CS.NA}
    for cell in sorted(declared & occupied):
        errs.append('(%s, %s) is declared not-applicable, but an entry occupies it: its question is coherent, so '
                    'withdraw the verdict' % cell)
    for cell in sorted(declared & NEVER_DECLARED):
        errs.append('(%s, %s) is declared not-applicable; 02 S4.3 names it as the live cell the triage must not '
                    'declare' % cell)
    nfam = len(rows['families'])
    for g in cols['groups']:
        n = sum(1 for c in declared if c[1] == g['id'])
        if n * 2 > nfam:
            errs.append('%s is declared not-applicable in %d of %d families: that is a column declared by rule, '
                        'not cell by cell (03 S7.1, "not a blanket by column")' % (g['id'], n, nfam))
    for f in rows['families']:
        if all((f['id'], g['id']) in declared for g in cols['groups']):
            errs.append('%s has every group declared not-applicable' % f['id'])
    for f in rows['families']:
        for g in cols['groups']:
            if (f['id'], g['id']) not in verdicts:
                errs.append('(%s, %s) is untriaged: give it a row with a verdict in %s'
                            % (f['id'], g['id'], CS.NOT_APPLICABLE))
    return errs + check_artifact(root, artifact, declared)


def check_artifact(root, path, declared):
    if not os.path.exists(path):
        return ['%s does not exist: run `bench build --derived` first' % os.path.relpath(path, root)]
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    errs = []
    if doc != json.loads(CS.serialise(CS.build(root))):
        errs.append('%s is stale: it is not what tools/build/coverage_states.py makes of this tree; run '
                    '`bench build --derived` again' % os.path.relpath(path, root))
    cells = doc.get('cells') or []
    for c in cells:
        cell = (c.get('family'), c.get('group'))
        if cell in declared and (c.get('state') != CS.NA or not one_sentence(c.get('rationale'))):
            errs.append('cell (%s, %s) is declared but the artifact reads %r without its rationale'
                        % (cell[0], cell[1], c.get('state')))
        if cell not in declared and c.get('state') == CS.NA:
            errs.append('cell (%s, %s) reads not-applicable without a declaration' % cell)

    def figure(subset):
        na = sum(1 for c in subset if c.get('state') == CS.NA)
        hit = sum(1 for c in subset if c.get('state') == 'has-benchmarks')
        den = len(subset) - na
        return {'cells': len(subset), 'not_applicable': na, 'denominator': den, 'has_benchmarks': hit,
                'percent': round(100.0 * hit / den, 1) if den else None}

    if doc.get('coverage') != figure(cells):
        errs.append('the overall coverage figure %r is not has-benchmarks over the cells left after the declared '
                    'ones, %r' % (doc.get('coverage'), figure(cells)))
    for f in doc.get('families') or []:
        want = figure([c for c in cells if c.get('family') == f.get('id')])
        if f.get('coverage') != want:
            errs.append('%s: coverage %r should be %r' % (f.get('id'), f.get('coverage'), want))
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
    cov = doc['coverage']
    print('OK    %d coarse cells triaged: %d not-applicable, %d applicable (%d occupied, %d empty)'
          % (cov['cells'], cov['not_applicable'], cov['cells'] - cov['not_applicable'], cov['has_benchmarks'],
             cov['cells'] - cov['not_applicable'] - cov['has_benchmarks']))
    print('      coverage %d of %d cells, %s%%, with the declared cells out of both sides'
          % (cov['has_benchmarks'], cov['denominator'], cov['percent']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
