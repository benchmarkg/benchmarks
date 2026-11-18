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
00 S7.1's success criterion S3 runs over. P1-S2-T11 stopped at the counts; the score came with P1-S14-T08.

The gap matrix (P1-S14-T08; 12 S5.2-5.4, 14 Phase 4 "The Gap Finder ships restricted, not ungated"). `emit()`
adds to the coverage cells a `matrix` of all 247 coarse cells and the `claims` published from it, which
`bench gaps --grid coarse --reviewed-only --format json > build/derived/gaps.json` writes and
scripts/check_gap_claims.py checks (docs/gap-matrix.md is the reader's account):

  - every cell carries the four factors of 12 S5.3 BESIDE the score, never the product alone, so a reader who
    weighs them differently can re-derive a ranking from the same JSON: normalised_density (12 S5.2's
    quality-weighted density over the densest applicable cell's), domain_activity, capability_salience and
    curation_confidence, with the capability_groups version it was computed under. `formula` and `parameters`
    say how each is computed and from what; every window, weight and threshold is recorded beside the numbers
    (12 S10 rule 6), and `quality_weights` gives each benchmark's density weight;
  - curation_confidence sits beside density in every cell, so a thin row of ours never reads as a field's gap.
    Its entry term counts REVIEWED ENTRIES ONLY (curator-reviewed or above, 05 S4): an agent draft no person
    has opened cannot raise our confidence. Presence counts every entry, drafts included, because dropping
    one would empty a cell that is measured, and an empty cell is the product (02 S11 rule 2);
  - a cell is ASSERTED as a gap only when it is 12 S5.4's category 1: the family is signed and not
    under-surveyed, the cell is triaged applicable in an accepted triage, no benchmark matches it at any
    weight, dated survey notes a person accepted cover every subdomain of the family for the group's terms
    (surveyed-and-empty, tools/build/coverage_states.py), curation_confidence reaches --min-confidence, the
    group is measured in other families and the family has released in the window. Every other cell is
    REFUSED and says why (`gap_claim_refusal`, the first reason; `withheld`, all of them). An unsigned
    family's cells lead with "insufficient curation confidence to assert a gap", in every cell (14 Phase 4).
    Category 2 (a reviewer flags the cell as miscut) has no record anywhere yet, so the emitter cannot see
    it; category 3 is every other empty cell. The matrix renders every family, signed or not: --reviewed-only
    narrows the coverage cells and the claims, never what is shown as refused.

The Gap Finder refusal (P1-S4-T08; 14 Phase 1 "The honest gate": "the Gap Finder refuses to assert a gap in
it"): every family and every cell says whether a gap claim may be made from it, `gap_claim(s)` refused or
permitted, and a refusal says why. A family no reviewer has signed is refused with 14 Phase 4's words,
"insufficient curation confidence to assert a gap"; an under-surveyed one is refused too (02 S3: "the Gap
Finder refusing to assert any gap in that row"). Permitted is not a claim: Phase 1 asserts no gap anywhere.

What counts as a published entry is scripts/seed_progress.py's rule, restated (a test holds the two equal):
every Benchmark file under data/benchmarks/<family>/, not _stubs/.
"""
from __future__ import annotations

import glob
import os
import subprocess
from collections import Counter, defaultdict
from datetime import date

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOMAINS = 'taxonomy/domains.yaml'
CAPABILITIES = 'taxonomy/capabilities.yaml'
GROUPS = 'taxonomy/capability_groups.yaml'
NOT_PUBLISHED = ('_stubs',)
UNREVIEWED = 'none'
MUTED = 'under-surveyed'
INSUFFICIENT = 'insufficient curation confidence to assert a gap'

# ---- the gap matrix's parameters (P1-S14-T08), every one recorded in the artifact beside the numbers (12 S10 rule 6)
FORMAT = 1
EXPECTATIONS = 'taxonomy/domain-expectations.yaml'
MIN_CONFIDENCE = 0.6        # 00 S7.1 criterion S3 runs `bench gaps --grid coarse --min-confidence 0.6 --reviewed-only`
FACTORS = ('normalised_density', 'domain_activity', 'capability_salience', 'curation_confidence')   # 12 S5.3
REVIEWED = ('curator-reviewed', 'primary-source-verified', 'expert-reviewed', 'maintainer-confirmed')  # 05 S4: a person read it
VERIFIED = REVIEWED[1:]     # 05 S4: a person confirmed each field against its sources (12 S5.2's x1.2, 12 S5.3's verified)
SIGNOFF = {'none': 0.0, 'generalist': 0.5, 'domain-expert': 1.0}                                      # 12 S5.3
CONFIDENCE_WEIGHTS = (('entry_coverage', 0.40), ('verified_fraction', 0.30), ('reviewer_signoff', 0.30))  # 12 S5.3
VERIFIED_WITHIN_DAYS = 180                                                                             # 12 S5.3
DOMAIN_WEIGHT = {'primary': 1.0, 'secondary': 0.5, 'subset': 0.5}                     # 12 S5.2; 02 S11 rules 1 and 4
QUALITY = {'verified': 1.2, 'machine-ingested': 0.7, 'active-in-18-months': 1.1, 'quiet-for-18-months': 0.8,
           'human-baseline': 1.1, 'sourced-release-date': 1.05}                                       # 12 S5.2
QUALITY_CLAMP = (0.5, 1.5)                                                                             # 12 S5.2
ACTIVITY_MONTHS = 18                                                                                   # 12 S5.2
VELOCITY_MONTHS = 24        # domain_activity's window: 12 S5.3 names "release velocity" and gives no window
HUMAN_ANCHORS = ('crowd-average', 'crowd-best', 'expert-average', 'expert-best')  # schema/baseline.py's human-* kinds
ASSERTED, REFUSED = 'asserted', 'refused'
CATEGORY_1, CATEGORY_3 = 'nobody-measures-it', 'not-yet-curated'                                       # 12 S5.4
PLACES = 4
FORMULA = {
    'gap_score': '(1 - normalised_density) x domain_activity x capability_salience x curation_confidence, the four '
                 'published factors multiplied as rounded and the product rounded to 6 places (12 S5.3); null for a '
                 'not-applicable cell or where a factor cannot be computed',
    'density': 'SUM over the benchmarks matching the cell of domain_weight x quality_weight. domain_weight: primary '
               '1.0, secondary 0.5, subset-derived 0.5 (a subset whose domain_override puts it in another family; '
               'a benchmark counts once, at its heaviest match). quality_weight: the product of the multipliers in '
               'parameters.quality_multipliers that apply, clamped to parameters.quality_clamp (12 S5.2). '
               'weighted_count is the same sum with every quality_weight 1 (02 S11 rule 1)',
    'normalised_density': "the cell's density over the densest applicable cell's (parameters.density_reference)",
    'domain_activity': "release velocity: of the family's entries with a release date, the share released in the "
                       'velocity window to as_of. Publication velocity is not measured: the index holds no per-family '
                       'publication counts',
    'capability_salience': 'of the benchmarks whose primary family is another, the share carrying a term of the '
                           'group: how often the capability is measured anywhere else (12 S5.3)',
    'curation_confidence': '0.40 x min(1, reviewed entries / expected Tier-1 families) + 0.30 x the share of the '
                           "family's entries verified within 180 days of as_of + 0.30 x reviewer_signoff (none 0, "
                           'generalist 0.5, domain-expert 1), from the three terms as rounded (12 S5.3). Reviewed '
                           'entries are those at curator-reviewed or above, verified ones at primary-source-verified '
                           'or above (05 S4); an unsized family divides by its seed target and says so',
    'claim': 'asserted only for 12 S5.4 category 1: the family is signed and not under-surveyed, the cell is triaged '
             'applicable in an accepted triage, no benchmark matches it at any weight, dated survey notes a person '
             'accepted cover every subdomain of the family for the group (surveyed-and-empty), curation_confidence '
             '>= min_confidence, capability_salience > 0 and domain_activity > 0. Category 2 (a reviewer flags the '
             'cell as miscut) has no record yet and the emitter cannot see it; category 3 is every other empty cell',
}


class GridRefused(Exception):
    """The fine grid: 12 S5.1 forbids a gap claim from it, and Phase 1 does not emit it at all."""


def refusal(family: dict) -> str | None:
    """Why no gap may be asserted in `family`'s row, or None when one may (14 Phase 1, 02 S3)."""
    if (family.get('reviewer_signoff') or UNREVIEWED) == UNREVIEWED:                   # get-default: unset is unreviewed
        return '%s: no reviewer has signed off on %s (reviewer_signoff: none)' % (INSUFFICIENT, family['id'])
    if family.get('coverage_status') == MUTED:                                         # get-default: unset is not muted
        return '%s is under-surveyed: no gap is asserted in its row (02 S3)' % family['id']
    return None


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


def coarse(root: str = ROOT, reviewed_only: bool = False, entries: list[dict] | None = None) -> dict:
    """The coverage cells. `entries` is published(root) when the caller has already read it (the matrix has)."""
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
    for b in published(root) if entries is None else entries:
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
                'gap_claim': 'refused' if refusal(f) else 'permitted',
                'gap_claim_refusal': refusal(f),
            })
    families = [{'id': f['id'], 'label': f['label'], 'core': f.get('core') is True,     # get-default: core is false unless stated
                 'coverage_status': f.get('coverage_status'),                           # get-default: as above
                 'reviewer_signoff': f.get('reviewer_signoff') or UNREVIEWED,           # get-default: as above
                 'gap_claims': 'refused' if refusal(f) else 'permitted',
                 'gap_claims_refusal': refusal(f),
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
        'not_yet': 'These cells are counts: the gap score, its four factors and the claims are the matrix\'s '
                   '(P1-S14-T08), and an empty cell here is not a gap claim. Phase 4 adds the claim-density toggle, '
                   'the fine grid\'s null-model banner, a record for a reviewer\'s miscut flag (12 S5.4 category 2) '
                   'and the Gap Finder view (12 S5.2-5.4, 10 V7)',
        'families': families,
        'cells': cells,
    }


def fine_size(root: str = ROOT) -> tuple[int, int]:
    """(family, subdomain) pairs and capability terms, read from the vocabulary, never typed."""
    rows, cols = axes(root)
    fams = {f['id'] for f in rows['families']}
    pairs = sum(1 for t in _load(root, DOMAINS)['terms'] if t.get('parent') in fams and t.get('status') != 'retired')  # get-default: optional keys on a term
    return pairs, sum(len(g['members']) for g in cols['groups'])


# ---- the gap matrix (P1-S14-T08) -------------------------------------------------------------------------------

def data_commit(root: str) -> tuple[date, str | None]:
    """(as_of, commit): the data commit's date and SHA, tools/build/liveness.py's convention, so a build is a
    function of the commit (12 S1.1 rule 4). Outside a git checkout (a test's synthetic tree): today and None."""
    if not os.path.exists(os.path.join(root, '.git')):
        return date.today(), None
    from tools.build.liveness import commit_date
    sha = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
    return commit_date(root), sha.stdout.strip()


def expectations(root: str = ROOT) -> tuple[dict, dict]:
    """({family: {expected, unsized, source}}, the file's provenance). 12 S5.3's denominator; an unsized family
    falls back to its seed target and is marked, never presented as a coverage fraction of what exists."""
    doc = _load(root, EXPECTATIONS)
    out = {}
    for row in doc['expectations']:
        sized = row.get('sized') is True                                               # get-default: unsized unless stated
        n = row['tier1_expectation'] if sized else row['fallback_value']
        if not isinstance(n, int) or n < 1:
            raise ValueError('%s: %s expects %r Tier-1 families; a denominator is a positive integer'
                             % (EXPECTATIONS, row['family'], n))
        out[row['family']] = {'expected': n, 'unsized': not sized,
                              'source': row.get('denominator_source') if sized else 'seed_target (fallback)'}  # get-default: provenance as written
    return out, {'vocabulary': EXPECTATIONS, 'version': str(doc['version']), 'estimated_on': str(doc['estimated_on']),
                 'verified': doc['verified']}


def _groups(terms, group_of: dict, who) -> set:
    unknown = [t for t in terms if t not in group_of]
    if unknown:
        raise ValueError('%s: capability %s is in no group of %s' % (who, unknown, GROUPS))
    return {group_of[t] for t in terms}


def _status(b: dict):
    return (b.get('curation') or {}).get('verification_status')                       # get-default: a stub may carry none


def activity(b: dict, snap: dict | None) -> tuple:
    """The three activity dates tools/build/liveness.py observes: repo push, dataset change, leaderboard change."""
    from tools.build.liveness import as_date
    live = b.get('liveness') or {}                                                     # get-default: unobserved is empty
    gh = (snap or {}).get('github') or {}                                              # get-default: no snapshot, no signal
    hf = (snap or {}).get('huggingface') or {}                                         # get-default: as above
    return (as_date(gh.get('pushed_at')) or as_date(live.get('repo_last_commit')),
            as_date(hf.get('lastModified')), as_date(live.get('leaderboard_last_updated')))


def human_baseline(b: dict) -> bool:
    """A human comparator is recorded: a human ceiling anchor, or a human-* Baseline with a value."""
    if (b.get('data') or {}).get('ceiling_anchor_type') in HUMAN_ANCHORS:              # get-default: optional block
        return True
    return any(str(x.get('kind') or '').startswith('human-') and x.get('value') is not None
               for x in b.get('baselines') or [])                                      # get-default: optional list


def quality(b: dict, snap: dict | None, as_of: date) -> tuple[float, list[str]]:
    """12 S5.2's quality_weight for one benchmark, and the multipliers it applied, by name. An activity signal
    inside 18 months is activity; silence counts only on liveness.py's two observed signals, since one quiet
    signal is not evidence of anything; with neither, no multiplier."""
    from tools.build.liveness import MIN_SIGNALS, add_months
    applied = []
    if _status(b) in VERIFIED:
        applied.append('verified')
    elif _status(b) == 'machine-ingested':
        applied.append('machine-ingested')
    seen = [d for d in activity(b, snap) if d is not None]
    if any(add_months(d, ACTIVITY_MONTHS) > as_of for d in seen):
        applied.append('active-in-18-months')
    elif len(seen) >= MIN_SIGNALS:
        applied.append('quiet-for-18-months')
    if human_baseline(b):
        applied.append('human-baseline')
    if b.get('released') and b.get('released_source'):
        applied.append('sourced-release-date')
    w = 1.0
    for name in applied:
        w *= QUALITY[name]
    return round(min(max(w, QUALITY_CLAMP[0]), QUALITY_CLAMP[1]), PLACES), applied


def curation_confidence(family: dict, entries: list[dict], expected: dict, as_of: date) -> dict:
    """12 S5.3's honesty term for one family, with its three terms and their inputs beside it."""
    from tools.build.coverage_states import UNREVIEWED_BADGE
    from tools.build.liveness import as_date
    signoff = family.get('reviewer_signoff') or UNREVIEWED                             # get-default: unset is unreviewed
    if signoff not in SIGNOFF:
        raise ValueError('%s: reviewer_signoff %r is not one of %s' % (family['id'], signoff, ', '.join(SIGNOFF)))
    reviewed = [b for b in entries if _status(b) in REVIEWED]
    verified = [b for b in entries if _status(b) in VERIFIED and as_date((b.get('curation') or {}).get('last_verified'))  # get-default: as above
                and (as_of - as_date(b['curation']['last_verified'])).days <= VERIFIED_WITHIN_DAYS]
    terms = {'entry_coverage': round(min(1.0, len(reviewed) / expected['expected']), PLACES),
             'verified_fraction': round(len(verified) / len(entries), PLACES) if entries else 0.0,
             'reviewer_signoff': SIGNOFF[signoff]}
    return {
        'value': round(sum(w * terms[k] for k, w in CONFIDENCE_WEIGHTS), PLACES),
        'badge': UNREVIEWED_BADGE if signoff == UNREVIEWED else 'reviewed',
        'entry_coverage': {'value': terms['entry_coverage'], 'reviewed_entries': len(reviewed), 'entries': len(entries),
                           'expected': expected['expected'], 'unsized': expected['unsized'],
                           'denominator_source': expected['source']},
        'verified_fraction': {'value': terms['verified_fraction'], 'verified_within_days': len(verified),
                              'entries': len(entries)},
        'reviewer_signoff': {'value': terms['reviewer_signoff'], 'signoff': signoff},
    }


def domain_activity(entries: list[dict], as_of: date) -> dict:
    """Release velocity: the share of the family's dated entries released in the window. A share within the
    family, not a count, because counts measure our allocation and how freely each field names things (12 S9.5)."""
    from tools.build.liveness import add_months, as_date
    dated = [d for d in (as_date(b.get('released')) for b in entries) if d]
    recent = [d for d in dated if add_months(d, VELOCITY_MONTHS) > as_of]
    return {'value': round(len(recent) / len(dated), PLACES) if dated else None,
            'released_in_window': len(recent), 'dated_entries': len(dated), 'undated_entries': len(entries) - len(dated)}


def gap_matrix(root: str, entries: list[dict], min_confidence: float, as_of: date | None,
               reviewed_only: bool) -> tuple[dict, dict]:
    """(the matrix's part of the document, {family: its curation_confidence and domain_activity})."""
    from tools.build import coverage_states as CS
    from tools.build.adoption import latest_counters
    rows, cols = axes(root)
    default_as_of, commit = data_commit(root)
    as_of = as_of or default_as_of
    group_of = {t: g['id'] for g in cols['groups'] for t in g['members']}
    expected, provenance = expectations(root)
    missing = [f['id'] for f in rows['families'] if f['id'] not in expected]
    if missing:
        raise ValueError('%s has no row for %s' % (EXPECTATIONS, ', '.join(missing)))
    states = CS.build(root, entries)
    state_of = {(c['family'], c['group']): c for c in states['cells']}
    triage_path = os.path.join(root, *CS.NOT_APPLICABLE.split('/'))
    triage_doc = _load(root, CS.NOT_APPLICABLE) if os.path.exists(triage_path) else None
    triage_accepted = triage_doc.get('accepted_by') if isinstance(triage_doc, dict) else None
    snaps = latest_counters(root)

    fam_of, groups_of, weights = {}, {}, {}
    match = defaultdict(dict)                   # (family, group) -> {benchmark: primary | secondary | subset}
    for b in entries:
        bid = b['id']
        dom = b.get('domain') or {}                                                    # get-default: validated elsewhere
        fam = (dom.get('primary') or '').split('/', 1)[0]                              # get-default: as above
        gs = _groups(b.get('capability') or [], group_of, bid)                         # get-default: a stub may carry none
        fam_of[bid], groups_of[bid] = fam, gs
        for g in gs:
            match[(fam, g)][bid] = 'primary'
        secs = {s.split('/', 1)[0] for s in dom.get('secondary') or []} - {fam}        # get-default: as above
        for f2 in secs:
            for g in gs:
                match[(f2, g)].setdefault(bid, 'secondary')
        for s in b.get('subsets') or []:                                               # get-default: optional list
            f3 = ((s.get('domain_override') or {}).get('primary') or '').split('/', 1)[0]  # get-default: optional override
            if not f3 or f3 == fam or f3 in secs:
                continue                        # the benchmark's own match already covers its union of terms
            caps = s['capability_override'] if s.get('capability_override') is not None else b.get('capability') or []  # get-default: 02 S11 rule 4, override replaces
            for g in _groups(caps, group_of, s.get('id')):
                match[(f3, g)].setdefault(bid, 'subset')
        w, applied = quality(b, snaps.get(bid), as_of)
        weights[bid] = {'weight': w, 'applied': applied}

    keys = [(f['id'], g['id']) for f in rows['families'] for g in cols['groups']]
    density = {k: round(sum(DOMAIN_WEIGHT[kind] * weights[b]['weight'] for b, kind in match[k].items()), PLACES)
               for k in keys}
    ref_key = None
    for k in keys:
        if state_of[k]['state'] != CS.NA and (ref_key is None or density[k] > density[ref_key]):
            ref_key = k
    ref = density[ref_key] if ref_key else 0.0

    by_family = defaultdict(list)
    for b in entries:
        by_family[fam_of[b['id']]].append(b)
    per_family = {f['id']: {'curation_confidence': curation_confidence(f, by_family[f['id']], expected[f['id']], as_of),
                            'domain_activity': domain_activity(by_family[f['id']], as_of)} for f in rows['families']}
    carrying = Counter(g for bid in groups_of for g in groups_of[bid])
    carrying_in = Counter((fam_of[bid], g) for bid in groups_of for g in groups_of[bid])
    held = Counter(fam_of.values())
    accepted = {}

    def note_accepted(path):
        if path not in accepted:
            doc = _load(root, path)
            survey = doc.get('survey') if isinstance(doc, dict) else None
            who = survey.get('accepted_by') if isinstance(survey, dict) else None
            accepted[path] = who if isinstance(who, str) and who.strip() else None
        return accepted[path]

    cells = []
    for f in rows['families']:
        fid, why_not_row = f['id'], refusal(f)
        conf, act = per_family[fid]['curation_confidence']['value'], per_family[fid]['domain_activity']['value']
        for g in cols['groups']:
            key, st, m = (fid, g['id']), state_of[(fid, g['id'])], match[(fid, g['id'])]
            kinds = Counter(m.values())
            elsewhere = len(entries) - held[fid]
            sal = round((carrying[g['id']] - carrying_in[key]) / elsewhere, PLACES) if elsewhere else None
            nd = round(density[key] / ref, PLACES) if ref else 0.0
            factors = {'normalised_density': nd, 'domain_activity': act, 'capability_salience': sal,
                       'curation_confidence': conf}
            na = st['state'] == CS.NA
            score = None if na or any(v is None for v in factors.values()) else round((1 - nd) * act * sal * conf, 6)
            withheld = []
            if why_not_row:
                withheld.append(('unreviewed-family' if (f.get('reviewer_signoff') or UNREVIEWED) == UNREVIEWED  # get-default: as above
                                 else 'under-surveyed-family', why_not_row))
            if na:
                withheld.append(('not-applicable', 'declared not-applicable in %s: the cell leaves the grid and every '
                                 'coverage figure (12 S5.4)' % CS.NOT_APPLICABLE))
            elif st['triage'] is None:
                withheld.append(('untriaged', 'not triaged in %s: every coarse cell is triaged before any gap claim '
                                 'publishes (03 S7.1)' % CS.NOT_APPLICABLE))
            elif not (isinstance(triage_accepted, str) and triage_accepted.strip()):
                withheld.append(('triage-not-accepted', 'the triage in %s is an agent draft no person has accepted'
                                 % CS.NOT_APPLICABLE))
            if m:
                withheld.append(('occupied', 'occupied: %d primary, %d secondary, %d subset-derived; a gap is asserted '
                                 'only of an empty cell behind a survey note (12 S5.4 category 1)'
                                 % (kinds['primary'], kinds['secondary'], kinds['subset'])))
            elif not na and st['state'] != CS.EMPTY:
                withheld.append(('not-yet-surveyed', 'not yet surveyed: no dated survey note covers every subdomain of '
                                 '%s for the terms of %s (12 S5.4 category 3)' % (fid, g['id'])))
            elif st['state'] == CS.EMPTY and not all(note_accepted(p) for p in st['survey_notes']):
                withheld.append(('survey-note-not-accepted', 'a survey note behind it is an agent draft no person has '
                                 'accepted: %s' % ', '.join(p for p in st['survey_notes'] if not note_accepted(p))))
            if conf < min_confidence:
                withheld.append(('below-min-confidence', '%s: curation_confidence %.4f is below %.2f (12 S5.4 '
                                 'category 3)' % (INSUFFICIENT, conf, min_confidence)))
            if not sal:
                withheld.append(('measured-nowhere-else', 'no other family measures %s, so nothing shows the '
                                 'capability is measurable (12 S5.4 category 1)' % g['id']))
            if not act:
                withheld.append(('family-inactive', '%s released nothing dated in the %d months to %s'
                                 % (fid, VELOCITY_MONTHS, as_of.isoformat())))
            cells.append({
                'family': fid, 'group': g['id'], 'capability_groups_version': cols['version'],
                'state': st['state'], 'triage': st['triage'],
                'counts': {'primary': kinds['primary'], 'secondary': kinds['secondary'], 'subset_derived': kinds['subset']},
                'benchmarks': sorted(b for b, k in m.items() if k == 'primary'),
                'secondary_benchmarks': sorted(b for b, k in m.items() if k == 'secondary'),
                'subset_benchmarks': sorted(b for b, k in m.items() if k == 'subset'),
                'weighted_count': round(sum(DOMAIN_WEIGHT[k] for k in m.values()), PLACES),
                'density': density[key],
                'factors': factors,
                'capability_salience_inputs': {'carrying': carrying[g['id']] - carrying_in[key], 'elsewhere': elsewhere},
                'gap_score': score,
                'empty': None if m or na else CATEGORY_3 if withheld else CATEGORY_1,
                'survey_notes': list(st['survey_notes']),
                'gap_claim': REFUSED if withheld else ASSERTED,
                'gap_claim_refusal': withheld[0][1] if withheld else None,
                'withheld': [code for code, _ in withheld],
            })

    notes = {n['path']: n for n in states['notes']}
    in_scope = {f['id'] for f in rows['families']
                if not reviewed_only or (f.get('reviewer_signoff') or UNREVIEWED) != UNREVIEWED}  # get-default: as above
    claims = []
    for c in cells:
        if c['gap_claim'] != ASSERTED or c['family'] not in in_scope:
            continue
        claims.append(dict(
            c, grid='coarse', **per_family[c['family']],
            survey_notes=[{'note': p, 'conducted_on': notes[p]['conducted_on'], 'accepted_by': note_accepted(p)}
                          for p in c['survey_notes']],
            statement='As of data commit %s (%s), this index holds no benchmark in %s x %s at any weight, primary, '
                      'secondary or subset-derived, and dated survey notes a person accepted cover every subdomain '
                      'of %s for the group\'s terms. A claim about the index at that commit, not about the world.'
                      % (commit or 'none', as_of.isoformat(), c['family'], c['group'], c['family'])))
    claims.sort(key=lambda c: -c['gap_score'])
    signed = [f['id'] for f in rows['families'] if (f.get('reviewer_signoff') or UNREVIEWED) != UNREVIEWED]  # get-default: as above
    if not signed:
        statement = ('The matrix asserts no gap until families are reviewed: 0 of %d domain families are '
                     'review-backed, so every cell carries "%s", its four factors shown beside it (14 Phase 4).'
                     % (len(rows['families']), INSUFFICIENT))
    else:
        statement = ('%d of %d domain families are review-backed; every cell of the other %d carries "%s". %d gap '
                     'claim(s) asserted, each from the coarse grid behind its survey notes; every other cell is '
                     'refused and says why.' % (len(signed), len(rows['families']), len(rows['families']) - len(signed),
                                               INSUFFICIENT, len(claims)))
    return {
        'statement': statement,
        'review_backed': {'families': len(signed), 'of': len(rows['families']), 'signed': signed},
        'parameters': {
            'as_of': as_of.isoformat(), 'data_commit': commit, 'min_confidence': min_confidence,
            'reviewed_rungs': list(REVIEWED), 'verified_rungs': list(VERIFIED),
            'verified_within_days': VERIFIED_WITHIN_DAYS, 'activity_window_months': ACTIVITY_MONTHS,
            'velocity_window_months': VELOCITY_MONTHS, 'domain_weight': dict(DOMAIN_WEIGHT),
            'quality_multipliers': dict(QUALITY), 'quality_clamp': list(QUALITY_CLAMP),
            'curation_confidence_weights': dict(CONFIDENCE_WEIGHTS), 'reviewer_signoff_scores': dict(SIGNOFF),
            'density_reference': {'value': ref, 'family': ref_key[0] if ref_key else None,
                                  'group': ref_key[1] if ref_key else None},
            'expectations': provenance,
        },
        'formula': dict(FORMULA),
        'claims_total': len(claims),
        'claims': claims,
        'matrix': cells,
        'quality_weights': {bid: weights[bid] for bid in sorted(weights)},
    }, per_family


def emit(grid: str = 'coarse', root: str = ROOT, reviewed_only: bool = False,
         min_confidence: float = MIN_CONFIDENCE, as_of: date | None = None) -> dict:
    """gaps.json: the coverage cells, the gap matrix over every coarse cell, and the claims published from it."""
    if grid == 'fine':
        pairs, terms = fine_size(root)
        raise GridRefused(
            'the fine grid (%d (family, subdomain) pairs x %d capability terms = %d cells) is refused: 12 S5.1 '
            'permits only the coarse grid to produce a gap claim, and at the seed most fine cells are empty by '
            'arithmetic, so an empty one is not a finding. Use --grid coarse.' % (pairs, terms, pairs * terms))
    if grid != 'coarse':
        raise ValueError('--grid is coarse or fine, not %r' % grid)
    if isinstance(min_confidence, bool) or not isinstance(min_confidence, (int, float)) or not 0 <= min_confidence <= 1:
        raise ValueError('--min-confidence is a number in [0, 1], not %r' % (min_confidence,))
    entries = published(root)
    doc = coarse(root, reviewed_only, entries)
    extra, per_family = gap_matrix(root, entries, float(min_confidence), as_of, reviewed_only)
    for f in doc['families']:
        f.update(per_family[f['id']])
    return {'artifact': 'gaps', 'format': FORMAT, **doc, **extra}


def markdown(doc: dict) -> str:
    return _coverage_markdown(doc) + (_matrix_markdown(doc) if 'matrix' in doc else '')


def _matrix_markdown(doc: dict) -> str:
    p = doc['parameters']
    lines = ['', '## Gap matrix (12 S5.3)', '', doc['statement'], '',
             'As of %s (data commit %s). A claim needs curation_confidence >= %.2f. Columns: %s v%s.'
             % (p['as_of'], (p['data_commit'] or 'none')[:12], p['min_confidence'], doc['axes']['columns']['vocabulary'],
                doc['axes']['columns']['version']), '',
             '| Family | Signed | Curation confidence | Reviewed / expected | Verified | Sign-off | Domain activity '
             '| Cells asserted |', '| --- | --- | ---: | --- | ---: | ---: | --- | ---: |']
    for f in doc['families']:
        cc, act = f['curation_confidence'], f['domain_activity']
        cov = cc['entry_coverage']
        lines.append('| %s | %s | %.4f | %d / %d%s (%d held) | %.4f | %.1f | %s | %d of %d |' % (
            f['id'], 'no' if f['reviewer_signoff'] == UNREVIEWED else f['reviewer_signoff'], cc['value'],
            cov['reviewed_entries'], cov['expected'], ', unsized' if cov['unsized'] else '', cov['entries'],
            cc['verified_fraction']['value'], cc['reviewer_signoff']['value'],
            '-' if act['value'] is None else '%.4f (%d of %d dated)' % (act['value'], act['released_in_window'],
                                                                         act['dated_entries']),
            sum(1 for c in doc['matrix'] if c['family'] == f['id'] and c['gap_claim'] == ASSERTED),
            sum(1 for c in doc['matrix'] if c['family'] == f['id'])))
    lines.append('')
    if not doc['claims']:
        lines.append('No gap claim is asserted. Every cell is refused; its `gap_claim_refusal` and `withheld` say why.')
        return '\n'.join(lines) + '\n'
    lines += ['| Family | Group | Gap score | Normalised density | Domain activity | Capability salience '
              '| Curation confidence | Survey notes |', '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for c in doc['claims']:
        x = c['factors']
        lines.append('| %s | %s | %.6f | %.4f | %.4f | %.4f | %.4f | %s |' % (
            c['family'], c['group'], c['gap_score'], x['normalised_density'], x['domain_activity'],
            x['capability_salience'], x['curation_confidence'], ', '.join(n['note'] for n in c['survey_notes'])))
    return '\n'.join(lines) + '\n'


def _coverage_markdown(doc: dict) -> str:
    lines = ['# Coverage, coarse grid (%s)' % ('reviewed families only' if doc['reviewed_only'] else 'all families'), '',
             '%d published entries; %d of %d cells in scope are non-empty. Rows: %s v%s. Columns: %s v%s.'
             % (doc['entries'], doc['cells_emitted'], doc['cells_in_scope'], doc['axes']['rows']['vocabulary'],
                doc['axes']['rows']['version'], doc['axes']['columns']['vocabulary'],
                doc['axes']['columns']['version']), '', doc['not_yet'] + '.', '']
    refused = [f for f in doc['families'] if f['in_scope'] and f['gap_claims'] == 'refused']
    if refused:
        lines += ['Gap claims refused in %d of %d families in scope: %s.'
                  % (len(refused), sum(1 for f in doc['families'] if f['in_scope']),
                     '; '.join('%s (%s)' % (f['id'], 'unreviewed' if f['reviewer_signoff'] == UNREVIEWED
                                            else 'under-surveyed') for f in refused))
                  + ' An unreviewed family has %s.' % INSUFFICIENT, '']
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
