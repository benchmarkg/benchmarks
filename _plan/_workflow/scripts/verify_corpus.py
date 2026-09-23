#!/usr/bin/env python3
"""
verify_corpus.py -- mechanical consistency checks for the _plan/ document set.

The plan's premise is that unsourced confident data destroys trust, and the corpus earned
this script the hard way: sixteen documents were drafted in parallel, each restated the
others' figures in its own prose, the copies drifted independently, and nothing detected it
until the vocabularies were counted by hand. Three different subdomain counts and two
different coarse-grid sizes were in circulation, and one document cited a section of another
that had never been written.

This is that count, automated. Run it after any edit to _plan/.

    python _plan/_workflow/scripts/verify_corpus.py

Exit code 0 if every check passes, 1 otherwise. Every check is mechanical: it either
recomputes a figure from 02-taxonomy.md, which owns the vocabularies, or verifies a
structural property. Judgement belongs in review, not here.

Counting conventions, which are the thing most easily got wrong:
  * Domain is a two-level facet, family/subdomain. 19 families.
  * Those families list 204 (family, subdomain) pairs. Since D3.5 renamed
    games-planning/puzzle-solving to puzzle-games, the pair count and the distinct-leaf-slug
    count are both 204 -- deliberately, so no sentence has to say which it means.
  * Capability has 44 terms, rolled up into 13 groups (02 section 4.3). The group axis is
    DERIVED and never tagged, so the rollup must be a strict partition.
  * "Tier-1 families" elsewhere means BENCHMARK families, per the counting convention in
    02 section 11 -- not domain families. Do not conflate the two.
"""

import io
import os
import re
import sys
from collections import Counter

PLAN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAXONOMY = os.path.join(PLAN_DIR, '02-taxonomy.md')

failures = []
notes = []


def fail(check, msg):
    failures.append((check, msg))


def note(msg):
    notes.append(msg)


def read(path):
    return io.open(path, encoding='utf-8').read()


def doc_files():
    return sorted(f for f in os.listdir(PLAN_DIR) if re.match(r'^\d\d-.*\.md$', f))


SLUG = re.compile(r'^[a-z][a-z0-9\-]*$')
TICKED = re.compile(r'`([a-z0-9][a-z0-9\-]*)`')


# ---------------------------------------------------------------------------
# Parse the canonical vocabularies out of 02-taxonomy.md.
#
# Deliberately tolerant of section renumbering: families are located by their
# heading being a bare slug, not by their position between two fixed headings.
# 02 has been restructured twice and a positional parser broke both times.
# ---------------------------------------------------------------------------

def parse_taxonomy():
    lines = read(TAXONOMY).split('\n')

    def index_of(pred, what, required=True):
        for i, l in enumerate(lines):
            if pred(l):
                return i
        if required:
            raise SystemExit('verify_corpus: cannot locate %s in 02-taxonomy.md' % what)
        return None

    dom = index_of(lambda l: re.match(r'^## 3\.', l), 'the Domain facet section')
    cap = index_of(lambda l: re.match(r'^## 4\.', l), 'the Capability facet section')

    # Families: "### <slug>" between the Domain and Capability sections.
    families, cur = {}, None
    for l in lines[dom:cap]:
        if l.startswith('### '):
            head = l[4:].strip()
            cur = head if SLUG.match(head) else None
            if cur:
                families[cur] = []
        elif cur:
            families[cur] += TICKED.findall(l)

    # Capability terms: the subsection that lists them, ending at the next one.
    t0 = index_of(lambda l: re.match(r'^### (4\.1|The terms)', l),
                  'the capability term list', required=False)
    if t0 is None:
        t0 = cap
    t1 = index_of(lambda l: l.startswith('### ') and
                  re.search(r'disambiguat', l, re.I), 'the disambiguation notes',
                  required=False)
    if t1 is None or t1 <= t0:
        t1 = next((i for i, l in enumerate(lines[t0 + 1:], t0 + 1)
                   if l.startswith('### ')), cap)
    # Only the interpunct-separated term block counts as a listing. Prose in the
    # same subsection legitimately re-mentions terms (02 section 4.1 declares the
    # four capability/subdomain homographs by name) and must not read as a dupe.
    caps = []
    for l in lines[t0:t1]:
        if '\u00b7' in l or re.match(r'^\s*`[a-z0-9\-]+`\s*$', l):
            caps += TICKED.findall(l)

    # Capability groups: the table in the "capability groups" subsection.
    g0 = index_of(lambda l: l.startswith('### ') and
                  re.search(r'capability group', l, re.I),
                  'the capability-groups section', required=False)
    groups = {}
    if g0 is not None:
        g1 = next((i for i, l in enumerate(lines[g0 + 1:], g0 + 1)
                   if re.match(r'^#{2,3} ', l)), len(lines))
        for l in lines[g0:g1]:
            if not l.startswith('|'):
                continue
            cells = [c.strip() for c in l.strip('|').split('|')]
            if len(cells) < 5 or cells[0].startswith('---') or not cells[0].isdigit():
                continue
            gid = TICKED.findall(cells[1])
            if not gid:
                continue
            groups[gid[0]] = TICKED.findall(cells[4])

    return families, caps, groups


FAMILIES, CAPS, GROUPS = parse_taxonomy()

SUB_LISTINGS = [s for v in FAMILIES.values() for s in v]
SUB_DISTINCT = sorted(set(SUB_LISTINGS))
CAP_DISTINCT = sorted(set(CAPS))

N_FAM = len(FAMILIES)
N_PAIRS = len(SUB_LISTINGS)     # (family, subdomain) pairs -- the fine row axis
N_SUB = len(SUB_DISTINCT)       # distinct leaf slugs
N_CAP = len(CAP_DISTINCT)
N_GRP = len(GROUPS)

FINE = N_PAIRS * N_CAP
COARSE = N_FAM * N_GRP


# ---------------------------------------------------------------------------
# 1. Vocabulary hygiene
# ---------------------------------------------------------------------------

def check_vocabulary_hygiene():
    dupe_subs = sorted(s for s, n in Counter(SUB_LISTINGS).items() if n > 1)
    if dupe_subs:
        fail('vocab/subdomain-in-two-families',
             'listed under more than one family, so the pair count (%d) and the distinct '
             'slug count (%d) disagree and every sentence must say which it means: %s'
             % (N_PAIRS, N_SUB, ', '.join(dupe_subs)))

    dupe_caps = sorted(c for c, n in Counter(CAPS).items() if n > 1)
    if dupe_caps:
        fail('vocab/capability-duplicates',
             'capability terms printed more than once in the term list: %s'
             % ', '.join(dupe_caps))

    collisions = sorted(set(CAP_DISTINCT) & set(SUB_DISTINCT))
    if collisions:
        note('slugs appearing as both a capability term and a subdomain leaf: %s. Per D3 '
             'these are NOT identifier collisions -- subdomain ids are family-qualified '
             'paths -- so this is informational.' % ', '.join(collisions))


# ---------------------------------------------------------------------------
# 2. The capability-group rollup must be a strict partition
#
# This is the check whose absence caused the original defect: three documents
# depended on a vocabulary nobody had written.
# ---------------------------------------------------------------------------

def check_group_partition():
    if not GROUPS:
        fail('groups/missing',
             'no capability-group vocabulary found in 02-taxonomy.md. The coarse coverage '
             'axis is undefined, and 10-visualization.md and 12-analytics-and-trends.md '
             'both depend on it')
        return

    members = [m for v in GROUPS.values() for m in v]
    seen = Counter(members)

    missing = [t for t in CAP_DISTINCT if t not in seen]
    if missing:
        fail('groups/not-a-partition',
             '%d capability term(s) belong to no group, so they vanish from every coarse '
             'coverage figure: %s' % (len(missing), ', '.join(missing)))

    dupes = sorted(t for t, n in seen.items() if n > 1)
    if dupes:
        fail('groups/not-a-partition',
             '%d term(s) appear in more than one group, so they are double-counted in '
             'every coarse coverage figure: %s' % (len(dupes), ', '.join(dupes)))

    unknown = sorted(t for t in seen if t not in CAP_DISTINCT)
    if unknown:
        fail('groups/unknown-member',
             'group members that are not capability terms: %s' % ', '.join(unknown))

    for gid in GROUPS:
        if gid in CAP_DISTINCT:
            fail('groups/id-collision',
                 'group id %r is also a capability term, making a matrix axis label '
                 'ambiguous' % gid)
        if gid in SUB_DISTINCT:
            fail('groups/id-collision',
                 'group id %r is also a subdomain leaf slug' % gid)

    sizes = [len(v) for v in GROUPS.values()]
    if sizes and min(sizes) < 2:
        note('group(s) with a single member: %s. A one-member group is a term wearing a '
             'group label and will read as a curation artefact.'
             % ', '.join(g for g, v in GROUPS.items() if len(v) < 2))


# ---------------------------------------------------------------------------
# 3. Stated counts must match the counted vocabularies
# ---------------------------------------------------------------------------

WORD_NUM = {
    'eight': 8, 'twelve': 12, 'thirteen': 13, 'eighteen': 18, 'nineteen': 19,
    'twenty': 20, 'forty': 40, 'forty-four': 44, 'forty-five': 45,
}

SUBSET_WORDS = (
    'at least', 'least ', 'more than', 'fewer than', 'less than', 'over ', 'up to ',
    'no more than', 'at most', 'minimum of', 'maximum of', 'first ',
    '≥', '≤', '>=', '<=',
    # A count scoped to something other than this taxonomy.
    'inventory of', 'reconnaissance', 'recon ', 'epoch', 'sample of', 'spread across',
    'drawn from', 'subset of', 'survey of', 'helm', 'before that rename', 'there were',
)


def is_scoped(before):
    """True if the number is a floor, a ceiling, or a count of something else.

    The corpus legitimately says ">=15 domain families with none empty" (a launch gate),
    "the domain reconnaissance inventory of 13 domain families" (an external survey's
    scope), and "before that rename there were 203" (its own changelog). None of these
    claims how large the vocabulary is, and flagging them trains the reader to ignore
    this script.

    `before` is preceding text from the whole file, not the current line: this corpus
    hard-wraps its prose, so the qualifier often sits on the line above.
    """
    return any(w in before[-80:].lower() for w in SUBSET_WORDS)


PAT_FAM = re.compile(
    r'(?<![\d,.])(\b\d{1,3}\b|eighteen|nineteen|twenty)'
    r'\*{0,2}[ \-\n]+domain[ \-\n]+famil', re.I)
PAT_CAP = re.compile(
    r'(?<![\d,.])(\b\d{1,3}\b|forty|forty-four|forty-five)'
    r'\*{0,2}[ \n]+capability[ \n]+terms?', re.I)
PAT_GRP = re.compile(
    r'(?<![\d,.])(\b\d{1,3}\b|eight|twelve|thirteen)'
    r'\*{0,2}[ \n]+capability[ \n]+groups?', re.I)
PAT_SUB = re.compile(r'(?<![\d,.])(\b\d{2,4}\b)[ \n]+subdomains?', re.I)


def _num(raw):
    raw = raw.lower()
    return WORD_NUM.get(raw, int(raw) if raw.isdigit() else None)


def check_stated_counts():
    for f in doc_files():
        text = read(os.path.join(PLAN_DIR, f))

        def at(pos):
            return text[:pos].count('\n') + 1

        for pat, expected, label, what in (
            (PAT_FAM, N_FAM, 'counts/domain-families', 'domain families'),
            (PAT_CAP, N_CAP, 'counts/capability-terms', 'capability terms'),
            (PAT_GRP, N_GRP, 'counts/capability-groups', 'capability groups'),
        ):
            for m in pat.finditer(text):
                val = _num(m.group(1))
                if val is None or val == expected or is_scoped(text[:m.start()]):
                    continue
                fail(label, '%s:%d says %s %s; 02-taxonomy.md defines %d'
                     % (f, at(m.start()), m.group(1), what, expected))

        for m in PAT_SUB.finditer(text):
            val = int(m.group(1))
            if is_scoped(text[:m.start()]):
                continue
            # "the 15 subdomains under `robotics-embodiment`" is a per-family claim.
            # A figure equal to a global total is a claim about the whole vocabulary,
            # even when a family name happens to sit next to it -- "204 subdomains:
            # language 11, mathematics 7, ..." is the corpus's own per-family gloss.
            if val in (N_SUB, N_PAIRS):
                continue
            window = text[max(0, m.start() - 120):m.end() + 60]
            named = set(fam for fam in FAMILIES if fam in window)
            if len(named) > 1:
                # Ambiguous: a per-family enumeration, not a claim about one family.
                continue
            if named:
                fam = named.pop()
                real = len(set(FAMILIES[fam]))
                if val != real:
                    fail('counts/subdomains-per-family',
                         '%s:%d says %s has %d subdomains; 02-taxonomy.md lists %d'
                         % (f, at(m.start()), fam, val, real))
                continue
            if val in (N_SUB, N_PAIRS):
                continue
            fail('counts/subdomains',
                 '%s:%d says %d subdomains; 02-taxonomy.md defines %d (family, subdomain) '
                 'pairs over %d distinct slugs'
                 % (f, at(m.start()), val, N_PAIRS, N_SUB))


# ---------------------------------------------------------------------------
# 3b. Values that were once true and are now wrong must not come back
#
# Added after the arithmetic audit found 203 restated as current in a document
# that was written before D3.5 landed. The count checks above only catch a
# number in the shape "<N> subdomains"; this catches it in any shape, including
# "the vocabulary of bare subdomain slugs currently holds 203".
#
# Every entry is a value the corpus genuinely used before 2026-09-21. The
# corpus is allowed to NAME them when explaining what changed -- is_scoped()
# carries the "before that rename", "the earlier draft" and "superseded"
# exemptions -- but never to assert them as current.
# ---------------------------------------------------------------------------

STALE_VALUES = (
    ('174', 'subdomain', 'subdomain count from the pre-2026-09-21 draft'),
    ('198', 'subdomain', 'subdomain count from the pre-2026-09-21 draft'),
    ('203', 'subdomain', 'distinct-slug count before D3.5 renamed puzzle-solving'),
    ('205', 'subdomain', 'subdomain listing count from the original draft'),
    ('6,960', 'cell', 'fine grid computed as 174 x 40'),
    ('8,712', 'cell', 'fine grid computed as 198 x 44'),
    ('228', 'cell', 'coarse grid computed on 12 capability groups'),
    ('144', 'cell', 'coarse grid computed on 18 families x 8 groups'),
    ('308', 'seed', 'seed total before D2 settled it at 320'),
    ('333', 'seed', 'per-family column sum before D2 rebuilt the table'),
)

STALE_EXEMPT = (
    'before that rename', 'earlier draft', 'previous draft', 'supersed',
    'used to', 'no longer', 'was ', 'were ', 'formerly', 'stale', 'pre-d',
    'the archive', 'archived', 'replac', 'corrected', 'not ', 'asserted',
    'rather than', 'instead of', 'wrongly', 'incorrectly', 'error', 'drop',
    'the old', 'previously', 'originally', 'overturn', 'obsolete', 'd1 ',
)


def check_stale_values():
    for f in doc_files():
        text = read(os.path.join(PLAN_DIR, f))
        low = text.lower()
        for val, keyword, why in STALE_VALUES:
            start = 0
            while True:
                i = text.find(val, start)
                if i < 0:
                    break
                start = i + 1
                # Must be a standalone number, not part of a longer one.
                before_ch = text[i - 1] if i else ' '
                after_ch = text[i + len(val)] if i + len(val) < len(text) else ' '
                if before_ch.isdigit() or before_ch in '.,' or after_ch.isdigit():
                    continue
                window = low[max(0, i - 110):i + 110]
                if keyword not in window:
                    continue
                if any(w in low[max(0, i - 260):i + 160] for w in STALE_EXEMPT):
                    continue
                if is_scoped(text[:i]):
                    continue
                fail('stale/superseded-value',
                     '%s:%d asserts %s near "%s" -- that is the %s'
                     % (f, text[:i].count('\n') + 1, val, keyword, why))


# ---------------------------------------------------------------------------
# 4. Matrix arithmetic must be the product of the real vocabularies
# ---------------------------------------------------------------------------

def check_matrix_arithmetic():
    pat = re.compile(r'([\d,]{3,7})[ \n]*cells', re.I)
    ok = {FINE, COARSE, N_SUB * N_CAP}
    for f in doc_files():
        text = read(os.path.join(PLAN_DIR, f))
        for m in pat.finditer(text):
            val = int(m.group(1).replace(',', ''))
            if val in ok:
                continue
            # Must be a claim about a grid. Counts of interesting, annotated or
            # sampled cells are not grid sizes and are legitimately any number.
            ctx = text[max(0, m.start() - 140):m.end() + 60].lower()
            if not re.search(r'grid|matrix|\bx\b|\u00d7', ctx):
                continue
            if re.search(r'roughly|about|approximately|~|sampled|annotated|'
                         r'interesting|brief', ctx):
                continue
            fail('matrix/cells',
                 '%s:%d states %s cells; the fine grid is %d x %d = %d and the coarse grid '
                 'is %d x %d = %d'
                 % (f, text[:m.start()].count('\n') + 1, m.group(1),
                    N_PAIRS, N_CAP, FINE, N_FAM, N_GRP, COARSE))


# ---------------------------------------------------------------------------
# 5. Per-family seed targets must sum to the stated seed total
# ---------------------------------------------------------------------------

def check_seed_targets():
    text = read(TAXONOMY)
    m = re.search(r'### Curation targets per family(.*?)(?:\n#{2,3} |\n---\n)', text, re.S)
    if not m:
        note('could not locate the "Curation targets per family" table; the seed-target '
             'sum was not checked')
        return

    rows, header = [], None
    for l in m.group(1).split('\n'):
        if not l.startswith('|') or re.match(r'^\|\s*-', l):
            continue
        cells = [c.strip() for c in l.strip('|').split('|')]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        rows.append(cells)

    if not header:
        note('the curation table has no parseable header; seed-target sum not checked')
        return

    col = next((i for i, c in enumerate(header) if 'seed' in c), None)
    if col is None:
        note('no "Seed target" column found in the curation table')
        return

    total, counted, fams = 0, 0, []
    for cells in rows:
        if col >= len(cells) or re.search(r'total', cells[0], re.I):
            continue
        nums = re.findall(r'\d+', cells[col].replace(',', ''))
        if not nums:
            continue
        total += int(nums[0])
        counted += 1
        fams.append(re.sub(r'[`*]', '', cells[0]).strip())

    if counted == 0:
        note('the seed-target column parsed no numeric rows; the table shape changed and '
             'this check needs updating')
        return

    if counted != N_FAM:
        fail('seed/row-count',
             'the curation table has %d numeric seed rows but there are %d domain '
             'families; a combined row is exactly where a floor violation hides'
             % (counted, N_FAM))

    named = set(fams) & set(FAMILIES)
    if len(named) != N_FAM:
        missing = sorted(set(FAMILIES) - named)
        if missing:
            fail('seed/missing-family',
                 'no seed-target row names these families: %s' % ', '.join(missing))

    # Collect every phrasing the corpus has used for the headline seed figure and
    # check each against the column sum. The original defect was a tilde -- "~300"
    # in prose beside a column summing to 333 -- so one pattern is not enough, and
    # a check that silently finds nothing is worse than no check at all.
    claims = set()
    patterns = (
        r'[Ss]eed (?:release )?target[^.\n]{0,60}?([\d,]{3,5})',
        r'sums to\s*\**([\d,]{3,5})',
        r'seed total[^.\n]{0,40}?([\d,]{3,5})',
        r'([\d,]{3,5})\s+seed entries',
        r'canonical seed (?:total|allocation)[^.\n]{0,60}?([\d,]{3,5})',
    )
    for pat in patterns:
        for m in re.finditer(pat, text):
            n = int(m.group(1).replace(',', ''))
            if 100 <= n <= 5000:
                claims.add((n, text[:m.start()].count('\n') + 1))

    if not claims:
        fail('seed/no-headline',
             'no headline seed figure found in 02-taxonomy.md in any recognised '
             'phrasing, so the column sum of %d across %d rows is unchecked. Either '
             'state the total in prose or teach this script the new phrasing'
             % (total, counted))
        return

    for n, line in sorted(claims):
        if n != total:
            fail('seed/total-mismatch',
                 '02-taxonomy.md:%d states a seed figure of %d but its per-family '
                 'column sums to %d across %d rows' % (line, n, total, counted))


# ---------------------------------------------------------------------------
# 6. Links, anchors and headings
# ---------------------------------------------------------------------------

def slugify(h):
    h = re.sub(r'`', '', h.strip().lower())
    h = re.sub(r'[^\w\s\-]', '', h, flags=re.UNICODE)
    return re.sub(r'\s+', '-', h.strip())


def check_links_and_headings():
    md = sorted(f for f in os.listdir(PLAN_DIR) if f.endswith('.md'))
    anchors = {}
    for f in md:
        t = read(os.path.join(PLAN_DIR, f))
        anchors[f] = set(slugify(m.group(2))
                         for m in re.finditer(r'^(#{1,6})\s+(.*)$', t, re.M))

    for f in md:
        t = read(os.path.join(PLAN_DIR, f))
        for m in re.finditer(r'\[([^\]]*)\]\(([^)\s]+)\)', t):
            tgt = m.group(2)
            if tgt.startswith(('http', 'mailto:')):
                continue
            line = t[:m.start()].count('\n') + 1
            path, _, anch = tgt.partition('#')
            path = path or f
            if not os.path.exists(os.path.join(PLAN_DIR, path)):
                fail('links/missing-file',
                     '%s:%d links to %s which does not exist' % (f, line, tgt))
                continue
            if anch and path.endswith('.md') and anch not in anchors.get(path, set()):
                fail('links/missing-anchor',
                     '%s:%d links to %s but that heading anchor does not exist'
                     % (f, line, tgt))

    for f in doc_files():
        first = read(os.path.join(PLAN_DIR, f)).split('\n', 1)[0]
        if not re.match(r'^# %s -- \S' % f[:2], first):
            fail('headings/h1-form',
                 '%s opens with %r; house style is "# %s -- Title" with two hyphens'
                 % (f, first[:60], f[:2]))


# ---------------------------------------------------------------------------
# 7. Renamed identifiers must not come back as live field names
# ---------------------------------------------------------------------------

FORBIDDEN = {
    'human_baseline_type': 'ceiling_anchor_type',
}

EXPLAINS = re.compile(
    r'renam|former|old name|retired|superseded|replaced|forbidden|no longer|used to|'
    r'before |was\b', re.I)


def check_forbidden_identifiers():
    for f in doc_files():
        text = read(os.path.join(PLAN_DIR, f))
        for old, new in FORBIDDEN.items():
            for m in re.finditer(re.escape(old), text):
                # This corpus hard-wraps, so "-- renamed from\n`old_name`" puts the
                # justification on the line above. Judge from a window.
                ctx = text[max(0, m.start() - 200):m.end() + 200]
                if new in ctx or EXPLAINS.search(ctx):
                    continue
                fail('identifiers/forbidden',
                     '%s:%d uses the retired identifier %r without naming the rename '
                     'to %r' % (f, text[:m.start()].count('\n') + 1, old, new))


# ---------------------------------------------------------------------------

CHECKS = (
    check_vocabulary_hygiene,
    check_group_partition,
    check_stated_counts,
    check_stale_values,
    check_matrix_arithmetic,
    check_seed_targets,
    check_links_and_headings,
    check_forbidden_identifiers,
)


def main():
    for c in CHECKS:
        c()

    print('verify_corpus: %d documents in %s' % (len(doc_files()), PLAN_DIR))
    print('  vocabularies owned by 02-taxonomy.md:')
    print('    %d domain families' % N_FAM)
    print('    %d (family, subdomain) pairs over %d distinct leaf slugs'
          % (N_PAIRS, N_SUB))
    print('    %d capability terms in %d groups' % (N_CAP, N_GRP))
    print('  fine grid   %d x %d = %d cells' % (N_PAIRS, N_CAP, FINE))
    print('  coarse grid %d x %d = %d cells' % (N_FAM, N_GRP, COARSE))

    if notes:
        print('\nNOTES (not failures):')
        for n in notes:
            print('  - %s' % n)

    if failures:
        by_check = {}
        for check, msg in failures:
            by_check.setdefault(check, []).append(msg)
        print('\n%d FAILURES across %d checks:' % (len(failures), len(by_check)))
        for check in sorted(by_check):
            print('\n  [%s]' % check)
            for msg in by_check[check]:
                print('    %s' % msg)
        return 1

    print('\nAll checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
