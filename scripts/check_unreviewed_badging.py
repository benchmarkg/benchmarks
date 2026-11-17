#!/usr/bin/env python3
"""Every unsigned family is badged on its entries, marked in the coverage map and silent in the gap output (P1-S4-T08).

14 Phase 1, "The honest gate": "every entry in that family renders a visible `curation_confidence: unreviewed`
badge, the domain is marked unreviewed in the coverage map, and the Gap Finder refuses to assert a gap in it.
Shipping unreviewed is permitted; shipping unreviewed *silently* is not." A family is unsigned while its
taxonomy/domains.yaml term carries `reviewer_signoff: none` (or none at all). This asserts the three together:

  entries   site/src/lib/taxonomy.json is current and carries every family's sign-off, which the entry page reads;
            and, in a built site (--dist), every entry page of an unsigned family carries the badge
            (data-curation-confidence="unreviewed") and no page of a signed family does.
  coverage  build/derived/coverage-states.json's family rows, as tools/build/coverage_states.py builds them: an
            unsigned family reads curation_confidence unreviewed and gap_claims refused, a signed one reviewed.
  gaps      `bench gaps --grid coarse` refuses every cell and family row of an unsigned family, "insufficient
            curation confidence to assert a gap", and --reviewed-only emits none of them.

No entry is published yet (all are agent drafts, 05 S4), so a site built over build/corpus.json has no entry
pages; check a draft preview, which renders them all (scripts/preview_corpus.py):

    uv run python scripts/preview_corpus.py --out build/preview
    cd site && UAIBI_CORPUS=../build/preview/corpus.json UAIBI_SITE_DRAFTS=1 npx astro build --outDir ../build/preview-site
    python scripts/check_unreviewed_badging.py --dist build/preview-site

Without --dist the entry pages are not read, and the output says so.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BADGE = 'data-curation-confidence="unreviewed"'


def families(root):
    """{family id: reviewer_signoff} from taxonomy/domains.yaml, unset read as none."""
    from tools.build import gaps
    rows, _ = gaps.axes(root)
    return {f['id']: f.get('reviewer_signoff') or gaps.UNREVIEWED for f in rows['families']}  # get-default: unset is unreviewed


def entries(root):
    """{entry id: family} for the published-or-draft entries (not _stubs/), by the family of domain.primary."""
    from tools.build import gaps
    return {b['id']: ((b.get('domain') or {}).get('primary') or '').split('/', 1)[0]  # get-default: validated elsewhere
            for b in gaps.published(root)}


def check_taxonomy(root, signed):
    from tools.build import site_taxonomy
    if site_taxonomy.stale(root):
        return ['%s is stale: regenerate it with `python tools/build/site_taxonomy.py`' % site_taxonomy.OUT]
    with open(os.path.join(root, site_taxonomy.OUT), encoding='utf-8') as fh:
        terms = json.load(fh)['facets']['domain']
    return ['%s: family %s carries reviewer_signoff %r, not %r' % (site_taxonomy.OUT, f, terms.get(f, {}).get(
        'reviewer_signoff'), s) for f, s in sorted(signed.items()) if terms.get(f, {}).get('reviewer_signoff') != s]


def check_pages(dist, signed, fam_of):
    """(errors, pages read): the badge on exactly the pages of unsigned families."""
    errs, n = [], 0
    for bid, fam in sorted(fam_of.items()):
        path = os.path.join(dist, 'benchmarks', bid, 'index.html')
        if not os.path.exists(path):
            errs.append('%s: no page at %s; build a draft preview (see --help), which renders every entry' % (bid, path))
            continue
        n += 1
        with open(path, encoding='utf-8') as fh:
            html = fh.read()
        if signed.get(fam) == 'none' and BADGE not in html:
            errs.append('%s: its family %s is unsigned, but the page carries no %s badge' % (bid, fam, BADGE))
        elif signed.get(fam) != 'none' and BADGE in html:
            errs.append('%s: its family %s is signed (%s), but the page carries the unreviewed badge'
                        % (bid, fam, signed.get(fam)))
    return errs, n


def check_coverage(root, signed):
    from tools.build import coverage_states, gaps
    errs = []
    rows = {f['id']: f for f in coverage_states.build(root)['families']}
    for fam, s in sorted(signed.items()):
        f = rows.get(fam)
        if f is None:
            errs.append('coverage map: family %s has no row' % fam)
        elif s == 'none' and not (f.get('curation_confidence') == 'unreviewed' and f.get('gap_claims') == 'refused'
                                  and gaps.INSUFFICIENT in (f.get('gap_claims_refusal') or '')):
            errs.append('coverage map: family %s is unsigned but reads curation_confidence %r, gap_claims %r'
                        % (fam, f.get('curation_confidence'), f.get('gap_claims')))
        elif s != 'none' and f.get('curation_confidence') != 'reviewed':
            errs.append('coverage map: family %s is signed (%s) but reads curation_confidence %r'
                        % (fam, s, f.get('curation_confidence')))
    return errs


def check_gaps(root, signed):
    from tools.build import gaps
    errs = []
    doc = gaps.coarse(root)
    for c in doc['cells']:
        if signed.get(c['family']) == 'none' and not (
                c.get('gap_claim') == 'refused' and gaps.INSUFFICIENT in (c.get('gap_claim_refusal') or '')):
            errs.append('bench gaps: cell (%s, %s) of unsigned %s is not refused' % (c['family'], c['group'],
                                                                                    c['family']))
    for f in doc['families']:
        if signed.get(f['id']) == 'none' and f.get('gap_claims') != 'refused':
            errs.append('bench gaps: family %s is unsigned, but its gap_claims is %r' % (f['id'], f.get('gap_claims')))
    leaked = [c for c in gaps.coarse(root, reviewed_only=True)['cells'] if c.get('reviewer_signoff') == 'none']
    errs += ['bench gaps --reviewed-only: cell (%s, %s) belongs to an unsigned family' % (c['family'], c['group'])
             for c in leaked]
    return errs, sum(1 for c in doc['cells'] if signed.get(c['family']) == 'none')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--dist', help='a built site to read the entry pages from (a draft preview renders them all)')
    a = ap.parse_args(argv)
    signed = families(a.root)
    fam_of = entries(a.root)
    errs = check_taxonomy(a.root, signed)
    pages = None
    if a.dist:
        more, pages = check_pages(a.dist, signed, fam_of)
        errs += more
    errs += check_coverage(a.root, signed)
    more, cells = check_gaps(a.root, signed)
    errs += more
    for e in errs:
        print('FAIL  ' + e)
    if errs:
        print('%d problem(s)' % len(errs))
        return 1
    unsigned = sum(1 for s in signed.values() if s == 'none')
    print('OK    %d of %d families unsigned; %s; the coverage map marks each unreviewed with gap claims refused; '
          'bench gaps refuses all %d of their non-empty cells' % (
              unsigned, len(signed), 'the badge is right on all %d entry pages read' % pages if pages is not None
              else 'entry pages not read (no --dist), but the site taxonomy carries every sign-off', cells))
    return 0


if __name__ == '__main__':
    sys.exit(main())
