#!/usr/bin/env python3
"""Render the taxonomy's generated tables, and check the documents against the YAML.

Counts in prose are generated, never typed (CI check 9b). This script is the generator
and, with --check, the drift detector. It also carries the seed-target assertions (9f)
and the capability-group partition assertion (9g).

    python scripts/taxonomy_stats.py              # render the tables to stdout
    python scripts/taxonomy_stats.py --check      # assert, and diff against the documents

Checks implemented here, per 05-repository-and-workflow.md S9:

  9b  taxonomy stats drift -- the term counts in 02 S14 and the seed table in 02 S3 must
      match taxonomy/*.yaml.
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

A check that cannot run yet says so on stdout and is counted as PENDING or SKIPPED. It is
never silently passed: a check nobody has seen fail is not evidence that it passes.
"""
import argparse
import io
import os
import re
import sys

import yaml

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
        return yaml.safe_load(fh)


def domain_terms():
    d = load_facet('domains')
    terms = d.get('terms') or []
    fams = [t for t in terms if t.get('parent') is None]
    subs = [t for t in terms if t.get('parent') is not None]
    return fams, subs


# ---------------------------------------------------------------- rendering

def render_seed_table(fams):
    """The columns of 02 S3's table that taxonomy/domains.yaml owns."""
    rows = sorted(fams, key=lambda f: (-f['seed_target'], f['id']))
    out = ['| Family | Seed target | Core? | Posture |', '| --- | --- | --- | --- |']
    for f in rows:
        out.append('| %s | **%d** | %s | %s |' % (
            f['id'], f['seed_target'], '**Y**' if f['core'] else 'N', f['curation_posture']))
    out.append('| **Total** | **%d** | **%d in Core** | |' % (
        sum(f['seed_target'] for f in rows),
        sum(f['seed_target'] for f in rows if f['core'])))
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


def parse_02_s3(text):
    """family -> (seed_target, core, posture) from 02 S3's allocation table."""
    out = {}
    for line in text.split('\n'):
        if not line.startswith('| ') or line.startswith('| ---'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 7:
            continue
        fam = cells[0]
        if not re.match(r'^[a-z][a-z-]+$', fam):
            continue
        m = re.search(r'\*\*(\d+)\*\*', cells[4])
        if not m:
            continue
        core = cells[5].replace('*', '').strip().upper() == 'Y'
        pm = POSTURE_RE.search(cells[6])
        out[fam] = (int(m.group(1)), core, pm.group(1).lower() if pm else None)
    return out


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
    if drift:
        return r.fail('9b seed table vs 02 S3', '; '.join(drift))
    r.ok('9b seed table vs 02 S3', '%d families agree on seed, core and posture' % len(declared))


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
    args = ap.parse_args()

    fams, subs = domain_terms()

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
    check_9b_seed(r, fams, doc02)
    check_9b_counts(r, fams, subs, doc02)

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
