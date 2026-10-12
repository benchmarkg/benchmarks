#!/usr/bin/env python3
"""Checks 9, 9a and 9c: identifiers that may never come back, and vocabulary ids that must be unique
(P0-S6-T05; 05 S9, 03 S4, 04 S2).

  9   retired-id ledger      no id in taxonomy/retired-ids.yaml is a live taxonomy term again (any status
                             but `retired`) or the id of a record under data/.
  9a  forbidden identifiers  no field name in taxonomy/forbidden-identifiers.yaml appears, as a whole word,
                             in a file under the scanned allowlist -- data/, taxonomy/, tools/, schema/,
                             ingest/, scripts/ -- minus the two ledgers, which list dead identifiers by
                             construction. docs/, adr/, CHANGELOG.md and _plan/ are never scanned: 05 S9
                             declares that exemption, because a rename has to stay explainable.
  9c  vocabulary ids         within each vocabulary file, ids are unique per field, deprecated and retired
                             terms included; in domains.yaml every subdomain is `{parent}/{leaf}` and every
                             leaf is unique across the file (scripts/taxonomy_stats.py's 9c, run here
                             against this tree); across files the facet-qualified id `{facet}:{id}` is
                             unique, asserted rather than assumed; and every id matches 04 S2's grammar.

    python scripts/check_identifiers.py              # check this tree; exit 0 if all hold, 1 otherwise
    python scripts/check_identifiers.py --root DIR   # another tree (the tests do)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNED = ('data', 'taxonomy', 'tools', 'schema', 'ingest', 'scripts')
LEDGERS = ('taxonomy/forbidden-identifiers.yaml', 'taxonomy/retired-ids.yaml')
SKIP_DIRS = {'__pycache__', 'node_modules', '.venv'}
TEXT_SUFFIXES = ('.py', '.yaml', '.yml', '.json', '.md', '.txt', '.mjs', '.js', '.ts', '.toml', '.cfg', '.csv')
ID_GRAMMAR = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')                       # 04 S2: a lowercase kebab slug
DOMAIN_GRAMMAR = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)?$')


def stats(root: str):
    """scripts/taxonomy_stats.py, pointed at `root`'s taxonomy/ (it reads a module-level path)."""
    spec = importlib.util.spec_from_file_location('taxonomy_stats_for_checks', os.path.join(ROOT, 'scripts',
                                                                                          'taxonomy_stats.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.TAXONOMY = os.path.join(root, 'taxonomy')
    return mod


def vocabularies(ts) -> list[tuple[str, dict]]:
    out = []
    for name in ts.VOCAB_FILES:
        d = ts.load_facet(name)
        if d and d.get('terms'):
            out.append((name, d))
    return out


def check_9(r, root, ts):
    ledger = ts.load_facet('retired-ids') or {}
    retired = [e['id'] for e in ledger.get('retired') or []]
    live = set()
    for _, d in vocabularies(ts):
        for t in d['terms']:
            if t.get('status') != 'retired':
                live.add(t['id'])
    records = set()
    for d, dirs, files in os.walk(os.path.join(root, 'data')):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.endswith(('.yaml', '.yml')):
                records.add(os.path.splitext(f)[0])          # a record's file is named by its id (05 S2)
    bad = []
    for rid in retired:
        bare = rid.split(':', 1)[-1]
        if bare in live:
            bad.append('%s is a live taxonomy term again' % rid)
        if bare in records:
            bad.append('%s is reused as a record id' % rid)
    if bad:
        return r.fail('9 retired-id ledger', '; '.join(bad))
    r.ok('9 retired-id ledger', '%d retired id(s), none live or reused' % len(retired))


def check_9a(r, root, ts):
    ledger = ts.load_facet('forbidden-identifiers') or {}
    names = [e['identifier'] for e in ledger.get('forbidden') or []]
    if not names:
        return r.ok('9a forbidden identifiers', 'the ledger lists none')
    pattern = re.compile(r'(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])' % '|'.join(map(re.escape, names)))
    hits = []
    for top in SCANNED:
        for d, dirs, files in os.walk(os.path.join(root, top)):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
            for f in sorted(files):
                full = os.path.join(d, f)
                rel = os.path.relpath(full, root).replace(os.sep, '/')
                if rel in LEDGERS or not f.endswith(TEXT_SUFFIXES):
                    continue
                with open(full, encoding='utf-8', errors='replace') as fh:
                    for n, line in enumerate(fh, 1):
                        m = pattern.search(line)
                        if m:
                            hits.append('%s:%d %s' % (rel, n, m.group(1)))
    if hits:
        return r.fail('9a forbidden identifiers', '; '.join(hits[:10]) + (' (+%d more)' % (len(hits) - 10)
                                                                          if len(hits) > 10 else ''))
    r.ok('9a forbidden identifiers', '%d identifier(s), none in %s' % (len(names), ', '.join(SCANNED)))


def check_9c(r, ts):
    ts.check_9c_all_facets(r)
    fams, subs = ts.domain_terms()
    ts.check_9c(r, fams, subs)
    qualified, grammar = [], []
    for name, d in vocabularies(ts):
        facet = d.get('facet') or name
        for t in d['terms']:
            qualified.append('%s:%s' % (t.get('field') or facet, t['id']))
            ok = DOMAIN_GRAMMAR if name == 'domains' else ID_GRAMMAR
            if not ok.match(str(t['id'])):
                grammar.append('%s.yaml %s' % (name, t['id']))
    dupes = sorted(q for q in set(qualified) if qualified.count(q) > 1)
    if dupes:
        r.fail('9c facet-qualified ids', 'not unique across files: %s' % dupes)
    else:
        r.ok('9c facet-qualified ids', '%d {facet}:{id} pairs, all distinct' % len(qualified))
    if grammar:
        r.fail('9c id grammar', 'not a lowercase kebab slug (04 S2): %s' % grammar[:10])
    else:
        r.ok('9c id grammar', 'every id is a lowercase kebab slug (domains: {family}/{leaf})')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    ts = stats(a.root)
    r = ts.Result()
    check_9(r, a.root, ts)
    check_9a(r, a.root, ts)
    check_9c(r, ts)
    print('check_identifiers: %d passed, %d failed' % (len(r.passed), len(r.failed)))
    return 1 if r.failed else 0


if __name__ == '__main__':
    sys.exit(main())
