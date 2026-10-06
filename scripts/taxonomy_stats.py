#!/usr/bin/env python3
"""Render the taxonomy's generated tables, and check the documents against the YAML.

Counts in prose are generated, never typed (CI check 9b). This script is the generator
and, with --check, the drift detector. It also carries the seed-target assertions (9f)
and the capability-group partition assertion (9g).

    python scripts/taxonomy_stats.py              # render the tables to stdout
    python scripts/taxonomy_stats.py --check      # assert, and diff against the documents
    python scripts/taxonomy_stats.py --write      # regenerate every count in 02 from the YAML

Checks implemented here, per 05-repository-and-workflow.md S9:

  9b  taxonomy stats drift -- the term counts in 02 S14 and the allocation table in 02 S3 must
      match taxonomy/*.yaml. The S3 table is a generated block (allocation_table(), from domains.yaml
      and domain-expectations.yaml), so a hand-edit to any of its cells fails like any generated value;
      the hand-written notes table beside it must have exactly one row per family.
  9c  vocabulary id uniqueness -- ids unique within a (file, field). Four vocabulary files
      carry more than one field, and 02 S11 rule 11 scopes a value's meaning to its field:
      execution.yaml legitimately holds `wet-lab` as both a compute_tier and a
      reproducibility_blocker. A same-id-two-fields pair is permitted and is REPORTED, never
      silent. In domains.yaml every term with a parent satisfies id == "{parent}/{leaf}" and
      every leaf is unique across the WHOLE file, not merely within its parent.
  9f  seed-target integrity -- exactly one seed_target per family, none missing or doubled,
      sum == 320, every target >= 12 unless the family is under-surveyed, every core family
      >= 18 and never under-surveyed. Extends to curation_posture, which must agree with
      01 S10 -- the document that owns the doctrine assigning it.
  9g  capability-group partition -- capability_groups.yaml is a strict partition of
      capabilities.yaml.
  9d  homograph declaration -- the capability ids that equal a subdomain leaf, computed from
      capabilities.yaml and domains.yaml, equal the pairs declared in homographs.yaml exactly,
      each with a known relationship and a rationale, and a false-friend pair carries a
      not_to_be_confused_with block on both terms.

9b also checks every per-field count in 02 S14's table (a row that names one field in
backticks, such as `data.access`), not only the four facet rows, and the term count spelled out
in each field heading of 02 S7-S10 ("### `access` -- nine terms"). Every other count in 02 and
in 12 S5.1 that is derived from the vocabulary is written as a generated value,

    <!-- gen: n(S) -->204<!-- /gen -->

whose expression is evaluated over the quantities in `quantities()` (S subdomains, C capabilities,
G groups, ...). --write rewrites all of them from the YAML, which is how a count in these documents
changes: never by hand. A number that records history ("Net: 40 -> 44 terms") is not marked.

A check that cannot run yet says so on stdout and is counted as PENDING or SKIPPED. It is
never silently passed: a check nobody has seen fail is not evidence that it passes.
"""
import argparse
import io
import os
import re
import sys

try:
    from yaml import safe_load
except ImportError:            # the project environment carries ruamel, not PyYAML
    from ruamel.yaml import YAML
    safe_load = YAML(typ='safe').load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY = os.path.join(ROOT, 'taxonomy')
PLAN = os.path.join(ROOT, '_plan')

SEED_TOTAL = 320          # D2, and 02 S3's Total row
CORE_TOTAL = 144          # the seven Core families
HARD_FLOOR = 12           # 02 S3 floor rule 1
CORE_FLOOR = 18           # 02 S3 floor rule 2

FACET_FILES = ['domains', 'capabilities', 'evaluation-methods', 'subjects',
               'data-properties', 'lifecycle', 'governance', 'execution']

# 05 S9 scopes check 9c to every taxonomy/*.yaml with a terms list, which is more than the
# eight facet files: ceiling-anchors and maintenance each hold one field of a facet whose other
# fields live elsewhere, per the layout in 05 S2.
VOCAB_FILES = FACET_FILES + ['ceiling-anchors', 'maintenance']

# 02 S14 row label -> the facet file that owns it
S14_FACET = {'Capability': 'capabilities', 'Evaluation method': 'evaluation-methods',
             'Subject under test': 'subjects'}


class Result(object):
    def __init__(self):
        self.failed = []
        self.pending = []
        self.skipped = []
        self.passed = []

    def ok(self, name, detail=''):
        self.passed.append(name)
        print('  PASS    %-34s %s' % (name, detail))

    def fail(self, name, detail):
        self.failed.append((name, detail))
        print('  FAIL    %-34s %s' % (name, detail))

    def pend(self, name, detail):
        self.pending.append((name, detail))
        print('  PENDING %-34s %s' % (name, detail))

    def skip(self, name, detail):
        self.skipped.append((name, detail))
        print('  SKIP    %-34s %s' % (name, detail))


def load_facet(name):
    path = os.path.join(TAXONOMY, name + '.yaml')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return safe_load(fh)


def domain_terms():
    d = load_facet('domains')
    terms = d.get('terms') or []
    fams = [t for t in terms if t.get('parent') is None]
    subs = [t for t in terms if t.get('parent') is not None]
    return fams, subs


# ---------------------------------------------------------------- rendering

def expectations():
    """family -> its taxonomy/domain-expectations.yaml row (the recon's Tier-1 estimate, or unsized)."""
    d = load_facet('domain-expectations') or {}
    return {e['family']: e for e in d.get('expectations') or []}


S3_HEADER = '| Family | Subdomains | Tier-1 (field-defining) | Seed target | Core? | Coverage | Posture |'
S3_NOTES_HEADER = '| Family | Tier-2 (worth an entry) | Ceiling | The curation difficulty that sets the posture |'


def render_seed_table(fams, subs=None, exp=None):
    """02 S3's allocation table, every cell from the YAML (P1-S1-T09): one row per family, by seed target then id.

    Subdomains is the family's subdomain count in domains.yaml; Tier-1 is domain-expectations.yaml's estimate,
    or `not estimated \u2021` for a family nobody sized -- never a number the YAML does not hold; Seed target,
    Core?, Coverage and Posture are the family's own fields. \u2020 marks every seed target equal to its Tier-1
    estimate, computed rather than typed (02 S3's \u2020 note). The recon's Tier-2 and Ceiling estimates and the
    prose behind each posture are in no YAML, so they stay in the hand-written table that follows this one."""
    subs = subs if subs is not None else domain_terms()[1]
    exp = exp if exp is not None else expectations()
    rows = sorted(fams, key=lambda f: (-f['seed_target'], f['id']))
    n_sub = {f['id']: sum(1 for s in subs if s['parent'] == f['id']) for f in fams}
    out = [S3_HEADER, '| --- | --- | --- | --- | --- | --- | --- |']
    for f in rows:
        e = exp.get(f['id'])                     # get-default: a family with no expectation row is unsized
        sized = e is not None and e['sized']
        tier1 = str(e['tier1_expectation']) if sized else 'not estimated \u2021'
        dagger = ' \u2020' if sized and e['tier1_expectation'] == f['seed_target'] else ''
        out.append('| %s | %d | %s | **%d**%s | %s | %s | `%s` |' % (
            f['id'], n_sub[f['id']], tier1, f['seed_target'], dagger, '**Y**' if f['core'] else 'N',
            f['coverage_status'], f['curation_posture']))
    sized = [exp[f['id']] for f in rows if f['id'] in exp and exp[f['id']]['sized']]
    out.append('| **Total** | **%d** | **%d across %d estimated rows** | **%d** | **%d in Core** | | |' % (
        sum(n_sub.values()), sum(e['tier1_expectation'] for e in sized), len(sized),
        sum(f['seed_target'] for f in rows), sum(f['seed_target'] for f in rows if f['core'])))
    return '\n'.join(out)


def render_counts():
    fams, subs = domain_terms()
    out = ['| Facet | Terms |', '| --- | --- |',
           '| 1 Domain | %d families / %d (family, subdomain) pairs |' % (len(fams), len(subs))]
    for label, fname in sorted(S14_FACET.items()):
        d = load_facet(fname)
        n = len((d or {}).get('terms') or [])
        out.append('| %s | %d |' % (label, n))
    for fname in FACET_FILES:
        if fname in ('domains',) or fname in S14_FACET.values():
            continue
        d = load_facet(fname)
        out.append('| %s | %d |' % (fname, len((d or {}).get('terms') or [])))
    return '\n'.join(out)


# ---------------------------------------------------------------- document parsing

def plan_doc(name):
    p = os.path.join(PLAN, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as fh:
        return fh.read()


POSTURE_RE = re.compile(r'\b(hand-curate|mixed|ingest-then-verify)\b', re.I)


def _table_after(text, header):
    """The family rows of the markdown table whose header line is `header`: family -> its cells."""
    at = text.find(header)
    if at < 0:
        return {}
    out = {}
    for line in text[at:].split('\n')[2:]:
        if not line.startswith('| '):
            break
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if re.match(r'^[a-z][a-z-]+$', cells[0]):
            out[cells[0]] = cells
    return out


def parse_02_s3(text):
    """family -> (seed_target, core, posture) from 02 S3's allocation table."""
    out = {}
    for fam, cells in _table_after(text, S3_HEADER).items():
        m = re.search(r'\*\*(\d+)\*\*', cells[3])
        pm = POSTURE_RE.search(cells[6])
        if m:
            out[fam] = (int(m.group(1)), cells[4].replace('*', '').strip().upper() == 'Y',
                        pm.group(1).lower() if pm else None)
    return out


def parse_02_s3_notes(text):
    """The families of 02 S3's hand-written notes table (Tier-2, Ceiling, the difficulty prose)."""
    return set(_table_after(text, S3_NOTES_HEADER))


def parse_01_s10(text):
    """family -> posture from 01 S10, the document that OWNS the doctrine."""
    out = {}
    for line in text.split('\n'):
        if not line.startswith('| ') or line.startswith('| ---'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 4:
            continue
        fam = cells[0]
        if not re.match(r'^[a-z][a-z-]+$', fam):
            continue
        pm = POSTURE_RE.search(cells[2])
        if pm:
            out[fam] = pm.group(1).lower()
    return out


def parse_02_s14(text):
    """02 S14 row label -> declared term count."""
    out = {}
    for line in text.split('\n'):
        if not line.startswith('| ') or line.startswith('| ---'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 5:
            continue
        m = re.match(r'^\d+\s+(.+)$', cells[0])
        if not m:
            continue
        label = m.group(1).strip()
        if label == 'Domain':
            fm = re.search(r'(\d+)\s+families\s*/\s*(\d+)', cells[2])
            if fm:
                out['Domain'] = (int(fm.group(1)), int(fm.group(2)))
            continue
        if cells[2].isdigit():
            out[label] = int(cells[2])
    return out


# ---------------------------------------------------------------- checks

ROOT_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_-]*):', re.M)


def check_no_duplicate_root_key(r):
    """A duplicate root key in a YAML mapping is silently resolved to the LAST one.

    taxonomy/subjects.yaml carried `terms:` twice and PyYAML kept the second, so 581 lines of
    a superseded draft sat in the file unread while every count check passed against the half
    that loaded. Nothing that reads the PARSED document can see this, which is why this check
    reads the raw text.

    It was found by a mutation test whose mutation landed in the dead half and changed
    nothing. A check nobody has seen fail is not evidence that it passes -- and neither is a
    suite that is green against a file it is only half reading.
    """
    bad = []
    checked = 0
    for fname in sorted(os.listdir(TAXONOMY)):
        if not fname.endswith('.yaml'):
            continue
        checked += 1
        raw = io.open(os.path.join(TAXONOMY, fname), encoding='utf-8').read()
        keys = ROOT_KEY.findall(raw)
        dupe = sorted(set(k for k in keys if keys.count(k) > 1))
        if dupe:
            bad.append('%s: %s' % (fname, dupe))
    if bad:
        return r.fail('9c no duplicate root key', '; '.join(bad))
    r.ok('9c no duplicate root key', '%d files, every root key appears once' % checked)


def check_9c_all_facets(r):
    """9c applies within EVERY taxonomy vocabulary file, not just domains.yaml.

    Scoped to (file, field) rather than to the file. Four of these files carry several fields,
    and 02 S11 rule 11 scopes a value's meaning to its field -- "the field name says which
    vocabulary a value belongs to". execution.yaml holds `wet-lab` as both a compute_tier and a
    reproducibility_blocker, which 02 S10's changelog introduces as a deliberate pair.

    Where a file holds one field, or no term declares one, the whole file is a single scope and
    the behaviour is exactly what it was.
    """
    bad, shared, checked = [], [], 0
    for name in VOCAB_FILES:
        d = load_facet(name)
        terms = (d or {}).get('terms') or []
        if not terms:
            continue
        checked += 1
        groups = {}
        for t in terms:
            groups.setdefault(t.get('field') or '', []).append(t['id'])
        for field, ids in sorted(groups.items()):
            dupe = sorted(set(i for i in ids if ids.count(i) > 1))
            if dupe:
                bad.append('%s.yaml%s: %s'
                           % (name, ('/' + field) if field else '', dupe))
        # The same id in two fields of one file is permitted. Report it: a permitted collision
        # nobody can see is the same failure as an undeclared one.
        for i in sorted(set(x for ids in groups.values() for x in ids)):
            fs = sorted(f for f, ids in groups.items() if i in ids)
            if len(fs) > 1:
                shared.append('%s %s' % (i, '/'.join(f.split('.')[-1] for f in fs)))
    if bad:
        return r.fail('9c id uniqueness per field', '; '.join(bad))
    detail = '%d vocabulary files, no duplicate id within a field' % checked
    if shared:
        detail += '; cross-field by design: %s' % ', '.join(shared)
    r.ok('9c id uniqueness per field', detail)


def check_9c(r, fams, subs):
    ids = [t['id'] for t in fams + subs]
    dupe = sorted(set(i for i in ids if ids.count(i) > 1))
    if dupe:
        return r.fail('9c id uniqueness', 'duplicate ids: %s' % dupe)
    bad = [s['id'] for s in subs if s['id'] != '%s/%s' % (s['parent'], s['id'].split('/')[-1])]
    if bad:
        return r.fail('9c id == parent/leaf', 'mismatched: %s' % bad[:5])
    leaves = [s['id'].split('/')[-1] for s in subs]
    coll = sorted(set(l for l in leaves if leaves.count(l) > 1))
    if coll:
        return r.fail('9c leaf uniqueness', 'leaf under two families: %s' % coll)
    r.ok('9c vocabulary id uniqueness', '%d ids, %d leaves, all distinct' % (len(ids), len(leaves)))


def check_9f(r, fams, posture_owner):
    names = [f['id'] for f in fams]
    if len(set(names)) != len(names):
        return r.fail('9f one record per family', 'duplicated: %s' % sorted(
            set(n for n in names if names.count(n) > 1)))
    missing = [f['id'] for f in fams if 'seed_target' not in f]
    if missing:
        return r.fail('9f seed_target present', 'missing on: %s' % missing)
    total = sum(f['seed_target'] for f in fams)
    if total != SEED_TOTAL:
        return r.fail('9f seed total', 'sum is %d, canonical total is %d' % (total, SEED_TOTAL))
    for f in fams:
        if f['seed_target'] < HARD_FLOOR and f.get('coverage_status') != 'under-surveyed':
            return r.fail('9f hard floor', '%s at %d with coverage_status=%s' % (
                f['id'], f['seed_target'], f.get('coverage_status')))
    core = [f for f in fams if f.get('core') is True]
    for f in core:
        if f['seed_target'] < CORE_FLOOR:
            return r.fail('9f core floor', '%s at %d, below %d' % (f['id'], f['seed_target'], CORE_FLOOR))
        if f.get('coverage_status') == 'under-surveyed':
            return r.fail('9f core not muted', '%s carries under-surveyed' % f['id'])
    ctotal = sum(f['seed_target'] for f in core)
    if ctotal != CORE_TOTAL:
        return r.fail('9f core total', 'core sum is %d, want %d' % (ctotal, CORE_TOTAL))
    r.ok('9f seed-target integrity', '%d families, sum %d, core %d = %d' % (
        len(fams), total, len(core), ctotal))

    if posture_owner is None:
        return r.skip('9f curation_posture vs 01 S10', '_plan/01-landscape-and-positioning.md '
                                                       'not present in this tree')
    drift = []
    for f in fams:
        want = posture_owner.get(f['id'])
        if want and want != f.get('curation_posture'):
            drift.append('%s: yaml=%s, 01 S10=%s' % (f['id'], f.get('curation_posture'), want))
    if drift:
        return r.fail('9f curation_posture vs 01 S10', '; '.join(drift))
    r.ok('9f curation_posture vs 01 S10', '%d families agree with the owning document'
         % len(posture_owner))


def check_9g(r):
    groups = load_facet('capability_groups')
    caps = load_facet('capabilities')
    if groups is None:
        return r.skip('9g capability-group partition',
                      'taxonomy/capability_groups.yaml absent; created by P0-S1-T04')
    cap_ids = set(t['id'] for t in (caps or {}).get('terms') or [])
    if not cap_ids:
        return r.pend('9g capability-group partition',
                      'capabilities.yaml has no terms yet; authored in P0-S2-T01')
    # capability_groups.yaml is not a facet file: its records live under `groups`, not `terms`,
    # because nothing in data/ references a group id and the rollup is derived, never tagged.
    grecs = groups.get('groups') or []
    if not grecs:
        return r.fail('9g capability-group partition',
                      'capability_groups.yaml has no `groups` list')
    seen, dupes, unknown = set(), [], []
    for g in grecs:
        for m in g.get('members') or []:
            if m in seen:
                dupes.append(m)
            seen.add(m)
            if m not in cap_ids:
                unknown.append(m)
    problems = []
    if dupes:
        problems.append('listed twice: %s' % sorted(set(dupes)))
    if unknown:
        problems.append('unknown members: %s' % sorted(set(unknown)))
    uncovered = sorted(cap_ids - seen)
    if uncovered:
        problems.append('capabilities in no group: %s' % uncovered)
    gids = set(g['id'] for g in grecs)
    if len(gids) != len(grecs):
        problems.append('duplicate group id')
    fams, subs = domain_terms()
    collide = gids & (cap_ids | set(f['id'] for f in fams)
                      | set(s['id'].split('/')[-1] for s in subs))
    if collide:
        problems.append('group id collides with a capability, family or leaf: %s' % sorted(collide))
    if problems:
        return r.fail('9g capability-group partition', '; '.join(problems))
    r.ok('9g capability-group partition', '%d groups partition %d capabilities'
         % (len(gids), len(cap_ids)))


def check_9d(r):
    caps = load_facet('capabilities')
    hom = load_facet('homographs')
    if hom is None:
        return r.skip('9d homograph declaration', 'taxonomy/homographs.yaml absent; created by P0-S1-T06')
    fams, subs = domain_terms()
    cap_terms = {t['id']: t for t in (caps or {}).get('terms') or []}
    sub_terms = {s['id']: s for s in subs}
    computed = {('capability:%s' % s['id'].split('/')[-1], 'domain:%s' % s['id'])
                for s in subs if s['id'].split('/')[-1] in cap_terms}
    entries = hom.get('entries') or []
    declared = {(e.get('capability'), e.get('domain')) for e in entries}
    problems = []
    if computed - declared:
        problems.append('undeclared: %s' % sorted('%s = %s' % p for p in computed - declared))
    if declared - computed:
        problems.append('declared but no longer computed: %s' % sorted('%s = %s' % p for p in declared - computed))
    for e in entries:
        if e.get('relationship') not in ('same-concept-two-facets', 'false-friend'):
            problems.append('%s: unknown relationship %r' % (e.get('capability'), e.get('relationship')))
        if not (e.get('rationale') or '').strip():
            problems.append('%s: no rationale' % e.get('capability'))
        if e.get('relationship') == 'false-friend':
            cap = cap_terms.get((e.get('capability') or ':').split(':', 1)[1], {})
            sub = sub_terms.get((e.get('domain') or ':').split(':', 1)[1], {})
            if not cap.get('not_to_be_confused_with') or not sub.get('not_to_be_confused_with'):
                problems.append('%s: a false-friend needs not_to_be_confused_with on both terms' % e.get('capability'))
    if problems:
        return r.fail('9d homograph declaration', '; '.join(problems))
    r.ok('9d homograph declaration', '%d computed, %d declared, equal' % (len(computed), len(declared)))


def field_counts():
    """field name -> term count, over every vocabulary file (a term's `field`, else the file's facet)."""
    out = {}
    for fname in VOCAB_FILES:
        d = load_facet(fname) or {}
        for t in d.get('terms') or []:
            f = t.get('field') or d.get('facet')
            out[f] = out.get(f, 0) + 1
    return out


def parse_02_s14_fields(text):
    """02 S14 rows that name one field in backticks and give a numeric count: field -> count."""
    out = {}
    for line in text.split('\n'):
        if not line.startswith('| ') or line.startswith('| ---'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 5 or not cells[2].isdigit():
            continue
        m = re.fullmatch(r'`([a-z_.]+)(?:\[\])?`', cells[1])
        if m:
            out[m.group(1)] = int(cells[2])
    return out


def check_9b_fields(r, doc02):
    if doc02 is None:
        return r.skip('9b per-field counts vs 02 S14', '_plan/02-taxonomy.md not present in this tree')
    declared = parse_02_s14_fields(doc02)
    have = field_counts()
    aliases = {'capability': 'capability', 'evaluation_method': 'evaluation_method',
               'designed_for_subjects': 'subject', 'lifecycle': 'lifecycle', 'activity': 'activity'}
    wrong = []
    for field, want in sorted(declared.items()):
        got = have.get(aliases.get(field, field))
        if got is None:
            wrong.append('%s: no vocabulary file defines it' % field)
        elif got != want:
            wrong.append('%s: yaml has %d, 02 S14 declares %d' % (field, got, want))
    if wrong:
        return r.fail('9b per-field counts vs 02 S14', '; '.join(wrong))
    r.ok('9b per-field counts vs 02 S14', '%d field rows agree' % len(declared))


NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen',
                'nineteen', 'twenty']
HEADING = re.compile(r'^(### `([a-z_]+)(?:\[\])?` — .*?\b)(' + '|'.join(NUMBER_WORDS) + r')( terms\b)', re.M)
S14_ROW = re.compile(r'^\| (?P<a>[^|]*)\| (?P<b>[^|]*)\| (?P<n>[^|]*?) \| (?P<rest>.*)$', re.M)


def _field_for(name, have):
    """A heading's short field name (`access`) -> the full field (`data.access`)."""
    hits = [f for f in have if f == name or f.endswith('.' + name)]
    return hits[0] if len(hits) == 1 else None


def sync_02(text):
    """02 with every generated count rewritten from the YAML; unchanged text if already in sync."""
    fams, subs = domain_terms()
    have = field_counts()
    groups = len((load_facet('capability_groups') or {}).get('groups') or [])
    aliases = {'capability': 'capability', 'evaluation_method': 'evaluation_method',
               'designed_for_subjects': 'subject'}
    start = text.find('\n## 14.')
    end = text.find('\n## ', start + 5)
    head, s14, tail = text[:start], text[start:end if end != -1 else len(text)], text[end if end != -1 else len(text):]

    def row(m):
        a, b, n = m.group('a'), m.group('b'), m.group('n')
        if a.strip() == '1 Domain':
            n = re.sub(r'\d+ families / \d+', '%d families / %d' % (len(fams), len(subs)), n)
        elif 'capability group rollup' in b and n.strip().isdigit():
            n = str(groups)
        else:
            fm = re.fullmatch(r'`([a-z_.]+)(?:\[\])?`', b.strip())
            if fm and n.strip().isdigit():
                got = have.get(aliases.get(fm.group(1), fm.group(1)))
                if got is not None:
                    n = str(got)
        return '| %s| %s| %s | %s' % (a, b, n, m.group('rest'))

    s14 = S14_ROW.sub(row, s14)

    def heading(m):
        full = _field_for(m.group(2), have)
        if full is None or have[full] >= len(NUMBER_WORDS):
            return m.group(0)
        return m.group(1) + NUMBER_WORDS[have[full]] + m.group(4)

    return sync_markers(HEADING.sub(heading, head) + s14 + HEADING.sub(heading, tail))


GEN = re.compile(r'<!-- gen: (.+?) -->(.*?)<!-- /gen -->', re.S)
GENERATED_DOCS = ['02-taxonomy.md', '12-analytics-and-trends.md']


def _half_up(x, places=0):
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-places)
    return Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP)


def quantities():
    """The names a generated value may use."""
    import math
    fams, subs = domain_terms()
    load = lambda n: len((load_facet(n) or {}).get('terms') or [])  # noqa: E731
    groups = (load_facet('capability_groups') or {}).get('groups') or []
    field_files = ['data-properties', 'ceiling-anchors', 'lifecycle', 'maintenance', 'governance', 'execution']
    sub_of = {f['id']: sum(1 for s in subs if s['parent'] == f['id']) for f in fams}
    seed_of = {f['id']: f['seed_target'] for f in fams}
    homographs = len((load_facet('homographs') or {}).get('entries') or [])

    def n(x):
        return '{:,}'.format(int(x))

    def w(x):
        x = int(x)
        if x < len(NUMBER_WORDS):
            return NUMBER_WORDS[x]
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'][x // 10]
        return tens + ('-' + NUMBER_WORDS[x % 10] if x % 10 else '')

    def W(x):
        return w(x).capitalize()

    def r2(x):
        return str(_half_up(x, 2))

    def r1(x):
        return str(_half_up(x, 1))

    def pct(x):
        return str(_half_up(100 * x))

    def hrs(terms, minutes):
        return str(_half_up(terms * minutes / 60))

    def allocation_table():
        """02 S3's allocation table as a generated block (P1-S1-T09): a hand-edit to any cell fails 9b."""
        return '\n' + render_seed_table(fams, subs) + '\n'

    def groups_table():
        rows = ['| # | id | label | n | member terms |', '| --- | --- | --- | --- | --- |']
        for i, g in enumerate(groups, 1):
            rows.append('| %d | `%s` | %s | %d | %s |' % (
                i, g['id'], g['label'], len(g['members']), ' \u00b7 '.join('`%s`' % m for m in g['members'])))
        return '\n' + '\n'.join(rows) + '\n'

    def density_sentence():
        """02 S3: the six families with the fewest seed entries per subdomain and the three with the most."""
        rows = sorted((seed_of[f] / sub_of[f], f) for f in sub_of)

        def fmt(fams, first):
            groups = []
            for f in fams:
                if groups and (seed_of[groups[-1][0]], sub_of[groups[-1][0]]) == (seed_of[f], sub_of[f]):
                    groups[-1].append(f)
                else:
                    groups.append([f])
            out = []
            for i, g in enumerate(groups):
                a, b = seed_of[g[0]], sub_of[g[0]]
                unit = (' entries', ' subdomains') if first and i == 0 else ('', '')
                out.append('%s (%d%s over %d%s, %s)' % (' and '.join(g), a, unit[0], b, unit[1], r2(a / b)))
            return ', '.join(out[:-1]) + ' and ' + out[-1] if len(out) > 1 else out[0]

        thin = [f for _, f in rows[:6]]
        fat = [f for _, f in reversed(rows[-3:])]
        return 'The thinnest rows by construction are %s; the fattest are %s.' % (fmt(thin, True), fmt(fat, False))

    S, C = len(subs), load('capabilities')
    return dict(F=len(fams), S=S, L=len({s['id'].split('/')[-1] for s in subs}), C=C, G=len(groups),
                M=load('evaluation-methods'), U=load('subjects'), X=sum(load(f) for f in field_files),
                H=homographs, SEED=sum(seed_of.values()), sub=sub_of.__getitem__, seed=seed_of.__getitem__,
                exp=math.exp, int=int, float=float, n=n, w=w, W=W, r1=r1, r2=r2, pct=pct, hrs=hrs,
                groups_table=groups_table, density_sentence=density_sentence, allocation_table=allocation_table)


def sync_markers(text, q=None):
    q = q or quantities()
    return GEN.sub(lambda m: '<!-- gen: %s -->%s<!-- /gen -->' % (m.group(1), eval(m.group(1), {'__builtins__': {}}, q)),
                   text)


def check_9b_document(r, doc02):
    if doc02 is None:
        return r.skip('9b every count in 02', '_plan/02-taxonomy.md not present in this tree')
    new = sync_02(doc02)
    if new != doc02:
        changed = [l for l in new.split('\n') if l not in set(doc02.split('\n'))]
        return r.fail('9b every count in 02', '%d line(s) out of date, run --write: %s'
                      % (len(changed), ' / '.join(l[:60] for l in changed[:4])))
    doc12 = plan_doc('12-analytics-and-trends.md')
    if doc12 is not None and sync_markers(doc12) != doc12:
        return r.fail('9b every count in 02', '12-analytics-and-trends.md has generated values out of date, run --write')
    r.ok('9b every count in 02', 'S14, the field headings and %d generated values in 02 and 12 match the YAML'
         % (len(GEN.findall(doc02)) + len(GEN.findall(doc12 or ''))))


def check_9b_seed(r, fams, doc02):
    if doc02 is None:
        return r.skip('9b seed table vs 02 S3', '_plan/02-taxonomy.md not present in this tree')
    declared = parse_02_s3(doc02)
    if not declared:
        return r.fail('9b seed table vs 02 S3', 'no allocation table found in 02 S3')
    drift = []
    for f in fams:
        d = declared.get(f['id'])
        if d is None:
            drift.append('%s: absent from 02 S3' % f['id'])
            continue
        if d[0] != f['seed_target']:
            drift.append('%s: yaml seed=%d, doc=%d' % (f['id'], f['seed_target'], d[0]))
        if d[1] != bool(f['core']):
            drift.append('%s: yaml core=%s, doc=%s' % (f['id'], f['core'], d[1]))
        if d[2] and d[2] != f.get('curation_posture'):
            drift.append('%s: yaml posture=%s, doc=%s' % (f['id'], f.get('curation_posture'), d[2]))
    extra = sorted(set(declared) - set(f['id'] for f in fams))
    if extra:
        drift.append('in 02 S3 but not in the YAML: %s' % extra)
    notes, ids = parse_02_s3_notes(doc02), set(f['id'] for f in fams)
    if ids - notes:
        drift.append('the 02 S3 notes table has no row for %s' % sorted(ids - notes))
    if notes - ids:
        drift.append('the 02 S3 notes table has a row for %s, which is not a family' % sorted(notes - ids))
    if drift:
        return r.fail('9b seed table vs 02 S3', '; '.join(drift))
    r.ok('9b seed table vs 02 S3', '%d families agree on seed, core and posture; the notes table has a row for each'
         % len(declared))


def check_9b_counts(r, fams, subs, doc02):
    if doc02 is None:
        return r.skip('9b term counts vs 02 S14', '_plan/02-taxonomy.md not present in this tree')
    declared = parse_02_s14(doc02)
    if not declared:
        return r.fail('9b term counts vs 02 S14', 'no vocabulary summary table found')
    dom = declared.get('Domain')
    if dom and dom != (len(fams), len(subs)):
        r.fail('9b domain counts vs 02 S14', 'yaml %d/%d, doc %d/%d' % (
            len(fams), len(subs), dom[0], dom[1]))
    elif dom:
        r.ok('9b domain counts vs 02 S14', '%d families / %d pairs' % (len(fams), len(subs)))
    for label, fname in sorted(S14_FACET.items()):
        want = declared.get(label)
        if want is None:
            continue
        d = load_facet(fname)
        got = len((d or {}).get('terms') or [])
        name = '9b %s count' % label.lower()
        if got == 0:
            r.pend(name, 'taxonomy/%s.yaml is empty; 02 S14 declares %d (authored in P0-S2)'
                   % (fname, want))
        elif got != want:
            r.fail(name, 'yaml has %d, 02 S14 declares %d' % (got, want))
        else:
            r.ok(name, '%d terms' % got)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true',
                    help='assert the invariants and diff the documents; exit 1 on any failure')
    ap.add_argument('--write', action='store_true',
                    help='rewrite the generated counts in _plan/02-taxonomy.md from taxonomy/*.yaml')
    args = ap.parse_args()

    fams, subs = domain_terms()

    if args.write:
        doc02 = plan_doc('02-taxonomy.md')
        new = sync_02(doc02)
        if new != doc02:
            with open(os.path.join(PLAN, '02-taxonomy.md'), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(new)
        print('02-taxonomy.md: %s' % ('counts rewritten' if new != doc02 else 'already in sync'))
        doc12 = plan_doc('12-analytics-and-trends.md')
        new12 = sync_markers(doc12)
        if new12 != doc12:
            with open(os.path.join(PLAN, '12-analytics-and-trends.md'), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(new12)
        print('12-analytics-and-trends.md: %s' % ('counts rewritten' if new12 != doc12 else 'already in sync'))
        return 0

    if not args.check:
        print('## Seed allocation (generated from taxonomy/domains.yaml)\n')
        print(render_seed_table(fams))
        print('\n## Vocabulary summary (generated from taxonomy/*.yaml)\n')
        print(render_counts())
        return 0

    doc02 = plan_doc('02-taxonomy.md')
    doc01 = plan_doc('01-landscape-and-positioning.md')
    posture_owner = parse_01_s10(doc01) if doc01 else None

    print('taxonomy_stats --check')
    print('  taxonomy/ %s' % TAXONOMY)
    print('  documents %s\n' % (PLAN if doc02 else '(not in this tree)'))

    r = Result()
    check_no_duplicate_root_key(r)
    check_9c_all_facets(r)
    check_9c(r, fams, subs)
    check_9f(r, fams, posture_owner)
    check_9g(r)
    check_9d(r)
    check_9b_seed(r, fams, doc02)
    check_9b_counts(r, fams, subs, doc02)
    check_9b_fields(r, doc02)
    check_9b_document(r, doc02)

    print('\n  %d passed, %d failed, %d pending, %d skipped'
          % (len(r.passed), len(r.failed), len(r.pending), len(r.skipped)))
    if r.pending or r.skipped:
        print('  PENDING and SKIPPED are not passes. They are checks that cannot run yet;')
        print('  each names the task that makes it runnable.')
    if r.failed:
        print('\nFAILED:')
        for name, detail in r.failed:
            print('  %s: %s' % (name, detail))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
