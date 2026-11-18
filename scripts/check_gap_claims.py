#!/usr/bin/env python3
"""Every published gap claim comes from the coarse grid, counts reviewed entries only, and names its survey notes (P1-S14-T08).

12 S5.1: the coarse grid is "the only one permitted to produce published gap claims". 12 S5.4: "Only category 1
is published as a gap", and category 3, "We have not curated it yet", is "excluded from published gap claims
entirely". 14 Phase 4: a domain without a reviewer's sign-off "renders 'insufficient curation confidence to assert
a gap' in every cell". tools/build/gaps.py decides all of that into build/derived/gaps.json; this re-reads the
tree and checks what was published, without trusting the artifact's own account of itself:

  document  gaps.json exists, is the coarse grid, was made --reviewed-only at a min_confidence no lower than
            tools/build/gaps.py's floor, and is what the emitter makes of this tree at its recorded as_of (a stale
            artifact fails). Its coverage cells hold no unsigned family.
  matrix    every one of the 19 x 13 coarse cells appears once, with all four factors of 12 S5.3 beside its score
            (numbers in [0, 1], or null where the factor cannot be computed), the score equal to the factors'
            product, and the capability_groups version of taxonomy/capability_groups.yaml. A refused cell says
            why; every cell of a family taxonomy/domains.yaml leaves unsigned is refused with "insufficient
            curation confidence to assert a gap". A cell is asserted exactly when `claims` lists it.
  claims    each one is from the coarse grid; its family is signed in taxonomy/domains.yaml and not
            under-surveyed; it counts reviewed entries only (its curation confidence's entry term is the family's
            entries at curator-reviewed or above, recounted here, and no entry of the corpus, reviewed or not,
            sits in the cell at any weight); it names its survey notes, and each is a dated subdomain note of
            that family, accepted by a person, finding the subdomain surveyed-and-empty for every term of the
            group, the notes together covering every live subdomain of the family; its cell is triaged
            applicable in an accepted triage; and its curation confidence reaches min_confidence.

While no family is signed, the only correct artifact asserts nothing: every cell refused, `claims` empty.

    uv run bench gaps --grid coarse --reviewed-only --format json > build/derived/gaps.json   # the verify,
    uv run python scripts/check_gap_claims.py                                                 # both halves
    python scripts/check_gap_claims.py --root DIR --gaps PATH                                 # the tests
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.build import coverage_states as CS  # noqa: E402
from tools.build import gaps  # noqa: E402

ARTIFACT = 'build/derived/gaps.json'
MAKE = 'uv run bench gaps --grid coarse --reviewed-only --format json > %s' % ARTIFACT


def load(root, rel):
    with open(os.path.join(root, *rel.split('/')), encoding='utf-8') as fh:
        return yaml.safe_load(fh)


class Tree:
    """What the claims are checked against, read from the YAML rather than from the artifact."""

    def __init__(self, root):
        self.root = root
        terms = load(root, gaps.DOMAINS)['terms']
        self.families = {t['id']: t for t in terms if t.get('parent') is None and t.get('status') != 'retired'}  # get-default: optional keys
        self.subdomains = {f: {t['id'] for t in terms if t.get('parent') == f and t.get('status') != 'retired'}  # get-default: as above
                           for f in self.families}
        groups = load(root, gaps.GROUPS)
        self.groups_version = str(groups['version'])
        self.members = {g['id']: list(g['members']) for g in groups['groups']}
        self.group_of = {t: g for g, ts in self.members.items() for t in ts}
        self.entries = gaps.published(root)
        path = os.path.join(root, *CS.NOT_APPLICABLE.split('/'))
        triage = load(root, CS.NOT_APPLICABLE) if os.path.exists(path) else {}
        triage = triage if isinstance(triage, dict) else {}
        self.triage_accepted = triage.get('accepted_by')
        self.verdicts = {}
        for row in triage.get('cells') or []:                                          # get-default: no file, no triage
            if isinstance(row, dict):
                self.verdicts.setdefault((row.get('family'), row.get('group')), row.get('verdict'))

    def signoff(self, family):
        return (self.families.get(family) or {}).get('reviewer_signoff') or gaps.UNREVIEWED  # get-default: unset is unreviewed

    def occupants(self, family, group):
        """Every entry matching the cell at any weight: primary, secondary, or a subset overridden into it."""
        out = []
        for b in self.entries:
            dom = b.get('domain') or {}                                                # get-default: validated elsewhere
            caps = set(b.get('capability') or [])                                      # get-default: a stub may carry none
            fams = {(dom.get('primary') or '').split('/', 1)[0]} | {s.split('/', 1)[0] for s in dom.get('secondary') or []}  # get-default: as above
            hit = family in fams and any(self.group_of.get(t) == group for t in caps)
            for s in b.get('subsets') or []:                                           # get-default: optional list
                over = s.get('domain_override') or {}                                  # get-default: optional override
                if (over.get('primary') or '').split('/', 1)[0] == family:             # get-default: as above
                    sub_caps = s['capability_override'] if s.get('capability_override') is not None else caps
                    hit = hit or any(self.group_of.get(t) == group for t in sub_caps)
            if hit:
                out.append(b['id'])
        return out

    def reviewed(self, family):
        return sum(1 for b in self.entries if ((b.get('domain') or {}).get('primary') or '').split('/', 1)[0] == family  # get-default: as above
                   and (b.get('curation') or {}).get('verification_status') in gaps.REVIEWED)  # get-default: as above


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_cell(c, where, tree, signed):
    errs = []
    f = c.get('factors')
    if not isinstance(f, dict) or sorted(f) != sorted(gaps.FACTORS):
        return ['%s: carries factors %r, not the four of 12 S5.3 (%s)' % (where, sorted(f) if isinstance(f, dict) else f,
                                                                          ', '.join(gaps.FACTORS))]
    for k in gaps.FACTORS:
        if f[k] is not None and not (number(f[k]) and 0 <= f[k] <= 1):
            errs.append('%s: factor %s is %r, not a number in [0, 1]' % (where, k, f[k]))
    for k in ('normalised_density', 'curation_confidence'):
        if f[k] is None:
            errs.append('%s: factor %s is null; it is computable for every cell' % (where, k))
    if errs:
        return errs
    if all(f[k] is not None for k in gaps.FACTORS) and c.get('state') != CS.NA:
        want = round((1 - f['normalised_density']) * f['domain_activity'] * f['capability_salience']
                     * f['curation_confidence'], 6)
        if not number(c.get('gap_score')) or abs(c['gap_score'] - want) > 1e-9:
            errs.append('%s: gap_score %r is not the product of its four factors, %r' % (where, c.get('gap_score'), want))
    elif c.get('gap_score') is not None:
        errs.append('%s: gap_score %r without four computable factors on an applicable cell' % (where, c['gap_score']))
    if c.get('capability_groups_version') != tree.groups_version:
        errs.append('%s: capability_groups version %r is not %s\'s, %s'
                    % (where, c.get('capability_groups_version'), gaps.GROUPS, tree.groups_version))
    if c.get('gap_claim') not in (gaps.ASSERTED, gaps.REFUSED):
        errs.append('%s: gap_claim %r is neither %s nor %s' % (where, c.get('gap_claim'), gaps.ASSERTED, gaps.REFUSED))
    elif c['gap_claim'] == gaps.REFUSED and not (isinstance(c.get('gap_claim_refusal'), str) and c['gap_claim_refusal'].strip()):
        errs.append('%s: refused without saying why' % where)
    if c.get('family') not in signed and not (c.get('gap_claim') == gaps.REFUSED and str(c.get('gap_claim_refusal')).startswith(gaps.INSUFFICIENT)):
        errs.append('%s: %s is unsigned in %s, so the cell reads "%s"; it reads %r, %r'
                    % (where, c.get('family'), gaps.DOMAINS, gaps.INSUFFICIENT, c.get('gap_claim'), c.get('gap_claim_refusal')))
    return errs


def check_claim(c, where, tree, doc):
    errs = []
    fam, group = c.get('family'), c.get('group')
    if c.get('grid') != 'coarse':
        errs.append('%s: from the %r grid; only the coarse grid may publish a gap claim (12 S5.1)' % (where, c.get('grid')))
    if fam not in tree.families or group not in tree.members:
        return errs + ['%s: (%r, %r) is not a cell of the coarse grid' % (where, fam, group)]
    if tree.signoff(fam) == gaps.UNREVIEWED:
        errs.append('%s: %s is unsigned in %s (reviewer_signoff: none); an unreviewed family asserts no gap (14 '
                    'Phase 1, "The honest gate")' % (where, fam, gaps.DOMAINS))
    if tree.families[fam].get('coverage_status') == gaps.MUTED:
        errs.append('%s: %s is under-surveyed; no gap is asserted in its row (02 S3)' % (where, fam))
    occupants = tree.occupants(fam, group)
    if occupants:
        errs.append('%s: the index holds %s in the cell; a gap is claimed only of an empty cell' % (where, ', '.join(occupants)))
    cov = ((c.get('curation_confidence') or {}).get('entry_coverage') or {})          # get-default: checked just below
    n = tree.reviewed(fam)
    if cov.get('reviewed_entries') != n or not (number(cov.get('expected')) and cov['expected'] > 0) or cov.get(
            'value') != round(min(1.0, n / cov['expected']), gaps.PLACES):
        errs.append('%s: its curation confidence counts %r entries over %r; %s has %d reviewed entries (%s), and only '
                    'reviewed entries count' % (where, cov.get('reviewed_entries'), cov.get('expected'), fam, n,
                                                ', '.join(gaps.REVIEWED)))
    conf = (c.get('factors') or {}).get('curation_confidence')                        # get-default: checked as a cell
    if not number(conf) or conf < doc['parameters']['min_confidence']:
        errs.append('%s: curation_confidence %r is below min_confidence %r' % (where, conf, doc['parameters']['min_confidence']))
    verdict = tree.verdicts.get((fam, group))
    if verdict != CS.APPLICABLE or not (isinstance(tree.triage_accepted, str) and tree.triage_accepted.strip()):
        errs.append('%s: triaged %r in %s, accepted by %r; a claim needs the cell triaged applicable and the triage '
                    'accepted by a person (03 S7.1)' % (where, verdict, CS.NOT_APPLICABLE, tree.triage_accepted))
    errs += check_notes(c, where, tree)
    return errs


def check_notes(c, where, tree):
    fam, members = c['family'], tree.members[c['group']]
    named = [n.get('note') if isinstance(n, dict) else n for n in c.get('survey_notes') or []]  # get-default: checked here
    if not named:
        return ['%s: names no survey note; a claim names the survey notes behind it (02 S11 rule 6)' % where]
    errs, covered = [], set()
    for rel in named:
        if not isinstance(rel, str) or not rel.startswith('%s/%s/' % (CS.SURVEYS, fam)) or not rel.endswith('.yaml'):
            errs.append('%s: survey note %r is not a note of %s under %s/%s/' % (where, rel, fam, CS.SURVEYS, fam))
            continue
        if os.path.basename(rel).startswith('_'):
            errs.append('%s: %s is a family-level note, which never makes a cell empty' % (where, rel))
            continue
        if not os.path.exists(os.path.join(tree.root, *rel.split('/'))):
            errs.append('%s: survey note %s does not exist' % (where, rel))
            continue
        doc = load(tree.root, rel)
        survey = doc.get('survey') if isinstance(doc, dict) and isinstance(doc.get('survey'), dict) else {}
        finding = doc.get('finding') if isinstance(doc, dict) and isinstance(doc.get('finding'), dict) else {}
        scope = survey.get('scope') if isinstance(survey.get('scope'), dict) else {}
        caps = scope.get('capabilities')
        sub = '%s/%s' % (fam, os.path.basename(rel)[:-5])
        if not isinstance(survey.get('conducted_on'), dt.date):
            errs.append('%s: survey note %s is undated' % (where, rel))
        if finding.get('decision') != CS.EMPTY:
            errs.append('%s: survey note %s decides %r, not %s' % (where, rel, finding.get('decision'), CS.EMPTY))
        if caps != CS.ALL and not (isinstance(caps, list) and set(members) <= set(caps)):
            errs.append('%s: survey note %s covers %r, not every term of %s' % (where, rel, caps, c['group']))
        if not (isinstance(survey.get('accepted_by'), str) and survey['accepted_by'].strip()):
            errs.append('%s: survey note %s is accepted by nobody; a person accepts a finding before it publishes'
                        % (where, rel))
        covered.add(sub)
    left = sorted(tree.subdomains[fam] - covered)
    if left:
        errs.append('%s: no survey note covers %s, so the cell is not surveyed-and-empty' % (where, ', '.join(left)))
    return errs


def check(root, path):
    if not os.path.exists(path):
        return ['%s does not exist: run `%s` first' % (path, MAKE)], None
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    errs = []
    if doc.get('grid') != 'coarse':
        errs.append('gaps.json is the %r grid; only the coarse grid may publish a gap claim (12 S5.1)' % doc.get('grid'))
    if doc.get('reviewed_only') is not True:
        errs.append('gaps.json was not made --reviewed-only; the published artifact is (05 S3, 00 S7.1 criterion S3)')
    params = doc.get('parameters') if isinstance(doc.get('parameters'), dict) else {}
    floor = params.get('min_confidence')
    if not number(floor) or floor < gaps.MIN_CONFIDENCE:
        errs.append('gaps.json was made at min_confidence %r, below the floor %.2f' % (floor, gaps.MIN_CONFIDENCE))
    tree = Tree(root)
    signed = {f for f in tree.families if tree.signoff(f) != gaps.UNREVIEWED}
    if doc.get('grid') == 'coarse' and number(floor) and isinstance(params.get('as_of'), str):
        try:
            again = json.loads(json.dumps(gaps.emit('coarse', root, doc.get('reviewed_only') is True, floor,
                                                    dt.date.fromisoformat(params['as_of']))))
        except ValueError as e:
            again = {'error': str(e)}
        if again != doc:
            errs.append('%s is stale: it is not what tools/build/gaps.py makes of this tree at as_of %s; run `%s`'
                        % (path, params['as_of'], MAKE))
    errs += ['coverage cell (%s, %s) belongs to unsigned %s' % (c.get('family'), c.get('group'), c.get('family'))
             for c in doc.get('cells') or [] if c.get('family') not in signed]
    cells = doc.get('matrix') or []
    seen = [(c.get('family'), c.get('group')) for c in cells]
    want = [(f, g) for f in tree.families for g in tree.members]
    if sorted(seen, key=str) != sorted(want, key=str):
        errs.append('the matrix holds %d cells, %d distinct; the coarse grid is %d x %d = %d, each once'
                    % (len(seen), len(set(seen)), len(tree.families), len(tree.members), len(want)))
    for c in cells:
        errs += check_cell(c, 'cell (%s, %s)' % (c.get('family'), c.get('group')), tree, signed)
    claims = doc.get('claims') or []
    asserted = {(c.get('family'), c.get('group')) for c in cells if c.get('gap_claim') == gaps.ASSERTED}
    claimed = {(c.get('family'), c.get('group')) for c in claims}
    if asserted != claimed:
        errs.append('the matrix asserts %s but the claims are %s' % (sorted(asserted), sorted(claimed)))
    for c in claims:
        where = 'claim (%s, %s)' % (c.get('family'), c.get('group'))
        errs += check_cell(c, where, tree, signed) + check_claim(c, where, tree, doc)
    if doc.get('claims_total') != len(claims):
        errs.append('claims_total %r is not the %d claims listed' % (doc.get('claims_total'), len(claims)))
    return errs, doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT, help='the repository root (default: this checkout)')
    ap.add_argument('--gaps', default=None, help='default: <root>/%s' % ARTIFACT)
    a = ap.parse_args(argv)
    errs, doc = check(a.root, a.gaps or os.path.join(a.root, *ARTIFACT.split('/')))
    if errs:
        print('\n'.join('FAIL  ' + e for e in errs))
        print('%d problem(s)' % len(errs))
        return 1
    cells = doc['matrix']
    refused = [c for c in cells if c['gap_claim'] == gaps.REFUSED]
    print('OK    %d gap claim(s) published, all from the coarse grid, each counting reviewed entries only and naming '
          'its survey notes' % len(doc['claims']))
    print('      %d of %d families review-backed; %d of %d cells refused, %d of them with "%s"'
          % (doc['review_backed']['families'], doc['review_backed']['of'], len(refused), len(cells),
             sum(1 for c in refused if c['gap_claim_refusal'].startswith(gaps.INSUFFICIENT)), gaps.INSUFFICIENT))
    print('      as of %s (data commit %s), capability_groups v%s, min_confidence %.2f'
          % (doc['parameters']['as_of'], doc['parameters']['data_commit'], doc['axes']['columns']['version'],
             doc['parameters']['min_confidence']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
