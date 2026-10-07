"""The coarse-grid gap emitter behind `bench gaps` (P1-S2-T11; 12 S5.1-5.3, 02 S4.3, 05 S3).

12 S5.1: "two grid resolutions, with the coarse one as the default and the only one permitted to produce
published gap claims". The coarse grid is the 19 domain families of taxonomy/domains.yaml crossed with the
13 capability groups of taxonomy/capability_groups.yaml, 247 cells. The fine grid ((family, subdomain) pairs
x capability terms) is refused here outright: at the seed it is mostly empty by arithmetic, so an empty fine
cell is the grid's default state, not a finding.

What a cell counts, per 12 S5.1:
  - BENCHMARKS PER GROUP, NOT TAGS. A published entry occupies the cell (its primary family, g) once for every
    capability group g its terms roll up into, however many of g's terms it carries, so the coarse total is
    not the row sum of the fine grid.
  - every cell DECOMPOSES ITS COUNT BY MEMBER TERM, zeros included, never the group total alone: a group can
    read "covered" while most of its terms sit at zero underneath it.
  - secondary domains are counted apart (`secondary_entries`, decomposed in `secondary_terms`), never folded
    into `entries`: 12 S5.2 weighs a secondary match at 0.5, and that weighting is the density's, Phase 4's.

Only non-empty cells are emitted (sparse). Every cell carries both axes' vocabulary (the family and group
ids and labels, the group's member terms) and its family's coverage_status and reviewer_signoff, and the
document carries the three vocabulary versions, because 12 S5.1 requires the capability_groups version to be
cited with every coverage figure.

--reviewed-only keeps the families a reviewer has signed (reviewer_signoff other than `none`), which is what
00 S7.1's success criterion S3 runs over. Not here, by the task's own scope (step 4): the gap score, its
weights, curation_confidence, --min-confidence and the publishability gate. Phase 4 extends this emitter.

What counts as a published entry is scripts/seed_progress.py's rule, restated (a test holds the two equal):
every Benchmark file under data/benchmarks/<family>/, not _stubs/.
"""
from __future__ import annotations

import glob
import os
from collections import Counter, defaultdict

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOMAINS = 'taxonomy/domains.yaml'
CAPABILITIES = 'taxonomy/capabilities.yaml'
GROUPS = 'taxonomy/capability_groups.yaml'
NOT_PUBLISHED = ('_stubs',)
UNREVIEWED = 'none'


class GridRefused(Exception):
    """The fine grid: 12 S5.1 forbids a gap claim from it, and Phase 1 does not emit it at all."""


def _load(root: str, rel: str):
    with open(os.path.join(root, *rel.split('/')), encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def axes(root: str = ROOT) -> tuple[dict, dict]:
    domains, groups = _load(root, DOMAINS), _load(root, GROUPS)
    fams = [t for t in domains['terms'] if t.get('parent') is None and t.get('status') != 'retired']  # get-default: optional keys on a term
    return ({'version': str(domains['version']), 'families': fams},
            {'version': str(groups['version']), 'groups': groups['groups'],
             'terms_version': str(_load(root, CAPABILITIES)['version'])})


def published(root: str = ROOT) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)) not in NOT_PUBLISHED:
            with open(path, encoding='utf-8') as fh:
                out.append(yaml.safe_load(fh))
    return out


def coarse(root: str = ROOT, reviewed_only: bool = False) -> dict:
    rows, cols = axes(root)
    group_of = {t: g['id'] for g in cols['groups'] for t in g['members']}
    fam_by_id = {f['id']: f for f in rows['families']}
    in_scope = {f['id'] for f in rows['families']
                if not reviewed_only or (f.get('reviewer_signoff') or UNREVIEWED) != UNREVIEWED}  # get-default: unset is unreviewed

    primary = defaultdict(set)                  # (family, group) -> benchmark ids, by primary domain
    secondary = defaultdict(set)                # (family, group) -> benchmark ids, by a secondary domain only
    terms = defaultdict(Counter)                # (family, group) -> term -> primary benchmarks carrying it
    sec_terms = defaultdict(Counter)            # the same, for the secondary-domain benchmarks
    per_family = Counter()
    for b in published(root):
        dom = b.get('domain') or {}                                                    # get-default: validated elsewhere
        fam = (dom.get('primary') or '').split('/', 1)[0]                              # get-default: as above
        tags = list(b.get('capability') or [])                                          # get-default: a stub may carry none
        unknown = [t for t in tags if t not in group_of]
        if unknown:
            raise ValueError('%s: capability %s is in no group of %s' % (b.get('id'), unknown, GROUPS))  # get-default: the id is for the message only
        per_family[fam] += 1
        for g in {group_of[t] for t in tags}:
            primary[(fam, g)].add(b['id'])
        for t in tags:
            terms[(fam, group_of[t])][t] += 1
        for f2 in {s.split('/', 1)[0] for s in dom.get('secondary') or []} - {fam}:     # get-default: as above
            for g in {group_of[t] for t in tags}:
                secondary[(f2, g)].add(b['id'])
            for t in tags:
                sec_terms[(f2, group_of[t])][t] += 1

    cells = []
    for f in rows['families']:
        if f['id'] not in in_scope:
            continue
        for g in cols['groups']:
            key = (f['id'], g['id'])
            if not primary[key] and not secondary[key]:
                continue
            cells.append({
                'family': f['id'], 'family_label': f['label'],
                'group': g['id'], 'group_label': g['label'],
                'entries': len(primary[key]),
                'benchmarks': sorted(primary[key]),
                'secondary_entries': len(secondary[key]),
                'secondary_benchmarks': sorted(secondary[key]),
                'secondary_terms': {t: sec_terms[key][t] for t in g['members']},
                'terms': {t: terms[key][t] for t in g['members']},
                'coverage_status': f.get('coverage_status'),                           # get-default: reported as written
                'reviewer_signoff': f.get('reviewer_signoff') or UNREVIEWED,           # get-default: unset is unreviewed
            })
    families = [{'id': f['id'], 'label': f['label'], 'core': f.get('core') is True,     # get-default: core is false unless stated
                 'coverage_status': f.get('coverage_status'),                           # get-default: as above
                 'reviewer_signoff': f.get('reviewer_signoff') or UNREVIEWED,           # get-default: as above
                 'entries': per_family[f['id']], 'in_scope': f['id'] in in_scope,
                 'non_empty_cells': sum(1 for c in cells if c['family'] == f['id'])}
                for f in rows['families']]
    return {
        'grid': 'coarse',
        'reviewed_only': reviewed_only,
        'axes': {
            'rows': {'facet': 'domain family', 'vocabulary': DOMAINS, 'version': rows['version'],
                     'count': len(rows['families'])},
            'columns': {'facet': 'capability group', 'vocabulary': GROUPS, 'version': cols['version'],
                        'count': len(cols['groups']), 'terms_vocabulary': CAPABILITIES,
                        'terms_version': cols['terms_version']},
        },
        'cells_total': len(rows['families']) * len(cols['groups']),
        'cells_in_scope': len(in_scope) * len(cols['groups']),
        'cells_emitted': len(cells),
        'entries': sum(per_family.values()),
        'counting': 'benchmarks per (primary family, capability group), not tags; terms decompose each count; '
                    'secondary domains counted apart (12 S5.1-5.2)',
        'not_yet': 'gap_score, its weights, curation_confidence and the publishability gate are Phase 4 '
                   '(12 S5.3); an empty cell here is not a gap claim',
        'families': families,
        'cells': cells,
    }


def fine_size(root: str = ROOT) -> tuple[int, int]:
    """(family, subdomain) pairs and capability terms, read from the vocabulary, never typed."""
    rows, cols = axes(root)
    fams = {f['id'] for f in rows['families']}
    pairs = sum(1 for t in _load(root, DOMAINS)['terms'] if t.get('parent') in fams and t.get('status') != 'retired')  # get-default: optional keys on a term
    return pairs, sum(len(g['members']) for g in cols['groups'])


def emit(grid: str = 'coarse', root: str = ROOT, reviewed_only: bool = False) -> dict:
    if grid == 'fine':
        pairs, terms = fine_size(root)
        raise GridRefused(
            'the fine grid (%d (family, subdomain) pairs x %d capability terms = %d cells) is refused: 12 S5.1 '
            'permits only the coarse grid to produce a gap claim, and at the seed most fine cells are empty by '
            'arithmetic, so an empty one is not a finding. Use --grid coarse.' % (pairs, terms, pairs * terms))
    if grid != 'coarse':
        raise ValueError('--grid is coarse or fine, not %r' % grid)
    return coarse(root, reviewed_only)


def markdown(doc: dict) -> str:
    lines = ['# Coverage, coarse grid (%s)' % ('reviewed families only' if doc['reviewed_only'] else 'all families'), '',
             '%d published entries; %d of %d cells in scope are non-empty. Rows: %s v%s. Columns: %s v%s.'
             % (doc['entries'], doc['cells_emitted'], doc['cells_in_scope'], doc['axes']['rows']['vocabulary'],
                doc['axes']['rows']['version'], doc['axes']['columns']['vocabulary'],
                doc['axes']['columns']['version']), '', doc['not_yet'] + '.', '']
    if not doc['cells']:
        lines.append('No non-empty cell is in scope.' + (
            ' Every family has reviewer_signoff: none.' if doc['reviewed_only'] and not any(
                f['in_scope'] for f in doc['families']) else ''))
        return '\n'.join(lines) + '\n'
    lines += ['| Family | Group | Entries | Secondary | Terms (non-zero) |', '| --- | --- | ---: | ---: | --- |']
    for c in doc['cells']:
        nz = ', '.join('%s %d' % (t, n) for t, n in c['terms'].items() if n)
        sec = ', '.join('%s %d' % (t, n) for t, n in c['secondary_terms'].items() if n)
        both = '; '.join(x for x in (nz, 'secondary: ' + sec if sec else '') if x) or '-'
        lines.append('| %s | %s | %d | %d | %s |' % (c['family'], c['group'], c['entries'], c['secondary_entries'], both))
    return '\n'.join(lines) + '\n'
