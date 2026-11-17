#!/usr/bin/env python3
"""CI check 9h -- presentation-group containment.

Two assertions, from 09-design-system.md §4.2 properties 1 and 3:

  1. TOTAL PARTITION. Every domain family in taxonomy/domains.yaml belongs to exactly one
     group in taxonomy/domain_groups.yaml, and no group member is anything other than a
     family. Adding a 20th family without assigning it a group fails in the same commit.

  3. NOT IN ANALYTICS. No presentation-group id appears in any shipped artifact.
     build/atlas.json is the single permitted consumer, because banding is a layout
     property. Every coverage percentage, density figure, gap score and curation-confidence
     value is computed over families and subdomains, never over groups.

The three artifacts the S8 emitter writes -- corpus.json, facets.json and enums.json
(tools/build/emit.py, P2-S1-T02; 08 S3.2 obliges it to refuse a group id) -- are parsed and
every key and string value walked, so a hit names its JSON path rather than line 1 of a
one-line file; a file that does not parse is a failure, since it cannot be vouched for. Every
other artifact is scanned line by line. Both use one rule, a group id as a whole token, which
is also the emitter's, so a build the emitter accepts passes here. Each of the three is
reported by name, scanned or absent: an absent one is NOT RUN, never a pass.

That rule is only sound while no group id equals an id another vocabulary defines (a term, a
subdomain leaf, a capability group, a rung, a profile): such a term's every legitimate use
would read as a leak. So a collision is itself a failure, naming the file, as the emitter's is.

A display-only grouping that leaks into a published gap claim is a data-integrity failure
invisible in the diff: a specialist who disputes the grouping has then invalidated the
finding without touching the data.

    python scripts/check_display_only_vocab.py
    python scripts/check_display_only_vocab.py --artifacts <dir>   # scan a fixture instead

Exit 0 if both hold, 1 otherwise. If there are no artifacts to scan -- which is the normal
state until the first build -- the containment assertion reports NOT RUN and says so loudly.
It is never reported as a pass.
"""
import argparse
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY = os.path.join(ROOT, 'taxonomy')
BUILD = os.path.join(ROOT, 'build')

# The one artifact permitted to carry a group id, per 09 §4.2 property 3.
PERMITTED = {'atlas.json'}

# Artifacts the grouping is explicitly forbidden from, named so a missing one is visible
# rather than silently unscanned. 08 §4.2 owns the shipped-artifact list; these are the
# subset 09 §4.2 and 05 §9h name by hand.
NAMED_FORBIDDEN = [
    'facets.json',
    'corpus.json',
    'enums.json',
    'derived/coverage.json',
    'derived/gaps.json',
    'derived/ecosystem.json',
    'suite.yaml',
    'croissant.jsonld',
]

SCAN_SUFFIXES = ('.json', '.jsonld', '.yaml', '.yml')

# The S8 emitter's artifacts (08 S4.2; tools/build/emit.py ARTIFACTS), at the top of the artifact directory.
EMITTED = ('corpus.json', 'facets.json', 'enums.json')


def display_path(path):
    """relpath raises across Windows drive letters, which a fixture on another drive hits."""
    try:
        return os.path.relpath(path, ROOT).replace(os.sep, '/')
    except ValueError:
        return path.replace(os.sep, '/')


def load(path):
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def token_re(ids):
    """Match a group id only as a whole token.

    A bare substring search is wrong in both directions here: `reasoning-general-ability`
    contains the family slug `reasoning-general`, and a future group id could sit inside a
    longer identifier. Bounding on the id characters keeps the check from firing on a
    family slug that merely shares a prefix with a group id.
    """
    alt = '|'.join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    return re.compile(r'(?<![A-Za-z0-9_-])(%s)(?![A-Za-z0-9_-])' % alt)


def vocabulary_ids(taxonomy_dir):
    """{id: [files]} for every id a taxonomy file other than domain_groups.yaml defines: terms (and
    each subdomain's leaf), groups, rungs and profiles."""
    out = {}
    for fn in sorted(os.listdir(taxonomy_dir)):
        if not fn.endswith('.yaml') or fn == 'domain_groups.yaml':
            continue
        doc = load(os.path.join(taxonomy_dir, fn))
        if not isinstance(doc, dict):
            continue
        for key in ('terms', 'groups', 'rungs', 'profiles'):
            for item in doc.get(key) or []:
                ident = item.get('id') if isinstance(item, dict) else None
                if isinstance(ident, str):
                    for i in {ident, ident.split('/')[-1]}:
                        out.setdefault(i, []).append(fn)
    return out


def check_homonyms(gids, taxonomy_dir):
    """A group id that is also another vocabulary's id makes the containment scan unsound."""
    ids = vocabulary_ids(taxonomy_dir)
    return ['group id %s is also an id in %s, so no scan can tell the group from that term'
            % (g, ', '.join('taxonomy/' + f for f in sorted(set(ids[g])))) for g in sorted(gids) if g in ids]


def json_hits(x, pattern, where=''):
    """(JSON path, group id) for every key and string value of `x` carrying a group id as a token."""
    out = []
    if isinstance(x, str):
        out += [(where or '<root>', m.group(1)) for m in pattern.finditer(x)]
    elif isinstance(x, dict):
        for k, v in x.items():
            path = '%s.%s' % (where, k) if where else k
            out += [(path + ' (key)', m.group(1)) for m in pattern.finditer(k)]
            out += json_hits(v, pattern, path)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out += json_hits(v, pattern, '%s[%d]' % (where, i))
    return out


def check_partition(groups, families):
    problems = []
    seen = {}
    for g in groups:
        gid = g.get('id')
        for m in g.get('members') or []:
            if m in seen:
                problems.append('%s is in both %s and %s' % (m, seen[m], gid))
            seen[m] = gid
            if m not in families:
                problems.append('%s is a member of %s but is not a domain family' % (m, gid))
    unassigned = sorted(families - set(seen))
    if unassigned:
        problems.append('families in no group: %s' % unassigned)
    gids = [g.get('id') for g in groups]
    if len(set(gids)) != len(gids):
        problems.append('duplicate group id')
    collide = set(gids) & families
    if collide:
        problems.append('group id equals a family slug: %s' % sorted(collide))
    return problems


def scan_artifacts(root, pattern):
    """Return (hits, files_scanned). A hit is (relpath, group_id, where), `where` being a JSON path in
    one of the EMITTED artifacts and `line N` elsewhere; an EMITTED artifact that does not parse is a
    hit with group_id None and `where` saying so."""
    hits, scanned = [], []
    if not os.path.isdir(root):
        return hits, scanned
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if not fn.endswith(SCAN_SUFFIXES):
                continue
            if fn in PERMITTED:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            scanned.append(rel)
            if rel in EMITTED:
                try:
                    with open(full, encoding='utf-8') as fh:
                        doc = json.load(fh)
                except (OSError, ValueError) as e:
                    hits.append((rel, None, 'does not parse: %s' % e))
                    continue
                hits += [(rel, gid, path) for path, gid in json_hits(doc, pattern)]
                continue
            with open(full, encoding='utf-8', errors='replace') as fh:
                for n, line in enumerate(fh, 1):
                    for m in pattern.finditer(line):
                        hits.append((rel, m.group(1), 'line %d' % n))
    return hits, scanned


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--artifacts', default=BUILD,
                    help='directory of built artifacts to scan (default: build/)')
    args = ap.parse_args()

    gf = load(os.path.join(TAXONOMY, 'domain_groups.yaml'))
    df = load(os.path.join(TAXONOMY, 'domains.yaml'))
    families = set(t['id'] for t in (df.get('terms') or []) if t.get('parent') is None)
    groups = gf.get('groups') or []

    failures = []
    print('check_display_only_vocab (CI 9h)')
    print('  taxonomy/domain_groups.yaml: %d groups over %d families\n' % (len(groups), len(families)))

    # --- the flag itself
    if gf.get('display_only') is not True:
        failures.append('domain_groups.yaml does not carry display_only: true')
        print('  FAIL    display_only flag')
    else:
        print('  PASS    display_only flag                  true')

    # --- property 1
    problems = check_partition(groups, families)
    if problems:
        failures.extend(problems)
        print('  FAIL    total partition                    %s' % '; '.join(problems))
    else:
        print('  PASS    total partition                    %d families, each in exactly one group'
              % len(families))

    # --- property 3
    gids = set(g.get('id') for g in groups if g.get('id'))
    homonyms = check_homonyms(gids, TAXONOMY)
    if homonyms:
        failures.extend(homonyms)
        print('  FAIL    group ids are unambiguous          %s' % '; '.join(homonyms))
    else:
        print('  PASS    group ids are unambiguous          no group id is another vocabulary\'s id')
    hits, scanned = scan_artifacts(args.artifacts, token_re(gids))
    where = display_path(args.artifacts)
    if not scanned:
        print('  NOT RUN containment in artifacts           nothing to scan under %s/' % where)
        print('          The build has not run yet, so property 3 is UNTESTED here. This is')
        print('          not a pass. It becomes enforceable once bench build writes artifacts.')
        missing = [p for p in NAMED_FORBIDDEN
                   if not os.path.exists(os.path.join(args.artifacts, p))]
        print('          Named artifacts still absent: %d of %d' % (len(missing), len(NAMED_FORBIDDEN)))
    elif hits:
        for rel, gid, at in hits[:20]:
            failures.append('%s: %s' % (rel, at) if gid is None else '%s %s carries the group id %s' % (rel, at, gid))
            print('  FAIL    containment in artifacts           %s %s%s' % (rel, at, '' if gid is None else ' -> ' + gid))
        if len(hits) > 20:
            print('          ... and %d more' % (len(hits) - 20))
    else:
        print('  PASS    containment in artifacts           %d artifacts scanned, no group id'
              % len(scanned))
        print('          permitted and skipped: %s' % ', '.join(sorted(PERMITTED)))
    if scanned:
        for name in EMITTED:
            if name not in scanned:
                print('  NOT RUN %-34s absent from %s/, so unscanned: not a pass' % (name, where))
            elif not any(h[0] == name for h in hits):
                print('  PASS    %-34s parsed, every key and string value walked' % name)

    if failures:
        print('\nFAILED (%d):' % len(failures))
        for f in failures:
            print('  %s' % f)
        return 1
    print('\n  OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
