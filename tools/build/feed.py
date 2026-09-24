#!/usr/bin/env python3
"""Release-feed events, derived from git history over data/ at build time (10-visualization.md V8).

    python tools/build/feed.py                  # events as JSON on stdout, newest first
    python tools/build/feed.py --out build/feed-events.json [--repo PATH]

V8: "all derived from git history over `data/` at build time rather than from a hand-maintained
changelog (hand-maintained changelogs drift and then quietly lie)". Nothing here reads a
changelog. The walk is main's first-parent line, so an event is dated to the commit that
published it, and each changed file is compared as parsed YAML against its first parent, so
formatting and comments never make an event.

The seven event types, and the exact rule for each:

  benchmark-added             a new data/benchmarks/<family>/<id>.yaml (a rename is not new)
  benchmark-updated-material  a benchmark diff that changes a MATERIAL field (below) not already
                              reported by the two more specific events -- so a lifecycle change
                              is one lifecycle-change event, not two events
  claim-added                 a new file under data/claims/; one under data/claims/_ingested/, or
                              one whose review_state is machine-ingested, carries
                              machine_ingested: true, which V8's default feed excludes
  correction                  a commit tagged `fix:` (V8) or carrying a `Correction:` trailer
                              (05 S8 builds /corrections from that trailer; the two documents name
                              the same thing two ways) that changes a value the parent already
                              published -- a value that was non-null before; filling in a null is
                              not a correction. One event per entity, listing before and after
  lifecycle-change            `lifecycle` changed between parent and commit
  deprecation-detected        `maintenance_status` moved INTO stale or abandoned (the staleness
                              threshold of taxonomy/maintenance.yaml) from any other value
  source-rot-detected         a Source's `link_status` moved to dead (06 S7.2)

MATERIAL fields: the eight facets of 02 S2 as 04 S3 spells them, plus licence, access and versions,
which V8 names. Every event also carries families[] and organisations[] (see attribute()), which
the per-domain feeds and the feed page's filters read. Everything else on a Benchmark -- description, tags, links, liveness, curation --
is cosmetic for the feed's purposes.

Dates. "Sort on the event's own date, never on ingest date": each event carries `date`, taken from
the record where the record has one -- a claim's date_reported, a benchmark's curation.added_on, a
Source's link-check stamp, the liveness check behind a maintenance verdict -- and otherwise the
commit's author date, the moment the change was made. `date_basis` says which. The commit date,
which for a machine-ingested record IS the ingest date, is kept as `published_on` and never sorted
on. Order: date descending, then commit order descending, then type and entity id.

Publication. The feed derives from all of history, but it may only announce what the site
publishes. `publishable` is false when the entity's file no longer exists at HEAD or its current
curation.verification_status is ai-drafted-unverified (14-roadmap: "Unverified entries excluded
from the build"; the site build refuses to publish them). The site's feeds read publishable events
only, so an event reappears the moment its entity is verified -- dated, as ever, by its own date.

Not derivable from git alone: V8's "automatic `saturated`" is computed by the build from claims
and is never written to data/, so it cannot appear as a lifecycle-change until the build's derived
lifecycle is itself recorded. Such transitions are out of this module's reach, and are not guessed.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

BENCHMARK = re.compile(r'^data/benchmarks/(?P<family>[^/]+)/(?P<id>[^_/][^/]*)\.yaml$')
CLAIM = re.compile(r'^data/claims/(?:.*/)?(?P<id>[^_/][^/]*)\.yaml$')
SOURCE = re.compile(r'^data/sources/(?:.*/)?(?P<id>[^_/][^/]*)\.yaml$')

MATERIAL = [
    'domain', 'capability', 'evaluation_method', 'designed_for_subjects',          # facets 1-4
    'data.access', 'data.refresh', 'data.data_provenance', 'data.contamination_risk',
    'data.ceiling_anchor_type',                                                     # facet 5
    'lifecycle', 'maintenance_status', 'maintenance_status_contested',              # facet 6
    'governance.maintainer_type', 'governance.submission_process',
    'governance.independence_flags',                                                # facet 7
    'execution.compute_tier', 'execution.reproducibility_tier',
    'execution.est_runtime_hours', 'execution.est_cost_usd',                        # facet 8
    'license', 'versions',                                                          # V8 by name
]
STALE = {'stale', 'abandoned'}
UNPUBLISHABLE = {'ai-drafted-unverified'}  # 14-roadmap: "Unverified entries excluded from the build"
FIX = re.compile(r'^fix(\([^)]*\))?!?:', re.I)
EVENT_TYPES = ('benchmark-added', 'benchmark-updated-material', 'claim-added', 'correction',
               'lifecycle-change', 'deprecation-detected', 'source-rot-detected')


def _yaml_load(text):
    try:
        from ruamel.yaml import YAML
        return YAML(typ='safe', pure=True).load(text)
    except ImportError:
        import yaml
        return yaml.safe_load(text)


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True,
                          text=True, encoding='utf-8').stdout


def load(repo, rev, path):
    try:
        text = git(repo, 'show', '%s:%s' % (rev, path))
    except subprocess.CalledProcessError:
        return None
    rec = _yaml_load(text)
    return rec if isinstance(rec, dict) else None


def get(rec, dotted):
    cur = rec
    for part in dotted.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def leaves(value, prefix=''):
    """{dotted path: scalar} for every scalar in a record; lists of scalars count as one value."""
    out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(leaves(v, '%s.%s' % (prefix, k) if prefix else str(k)))
    elif isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value):
        for i, v in enumerate(value):
            out.update(leaves(v, '%s[%d]' % (prefix, i)))
    else:
        out[prefix] = value
    return out


def as_datetime(v):
    """A UTC datetime from a YAML date, datetime or ISO string; None if it is not one."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day, tzinfo=dt.timezone.utc)
    s = str(v).strip()
    try:
        t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def jsonable(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, list):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    return v


def commits(repo):
    """Main's first-parent commits touching data/, oldest first: (sha, parent, author date, commit date, message)."""
    shas = git(repo, 'log', '--first-parent', '--reverse', '--format=%H', '--', 'data/').split()
    out = []
    for sha in shas:
        meta = git(repo, 'show', '-s', '--format=%P%x1f%aI%x1f%cI%x1f%B', sha)
        parents, author, committed, body = meta.split('\x1f', 3)
        parent = parents.split()[0] if parents.split() else EMPTY_TREE
        out.append((sha, parent, as_datetime(author), as_datetime(committed), body.strip()))
    return out


def changes(repo, parent, sha):
    """[(status, old_path, new_path)] under data/, renames detected."""
    raw = git(repo, 'diff-tree', '-r', '-M', '--no-commit-id', '--name-status', parent, sha, '--', 'data/')
    out = []
    for line in raw.splitlines():
        parts = line.split('\t')
        st = parts[0][0]
        if st == 'R':
            out.append(('R', parts[1], parts[2]))
        elif st in 'AMD':
            out.append((st, parts[1], parts[1]))
    return out


def is_correction(message):
    subject = message.splitlines()[0] if message else ''
    return bool(FIX.match(subject)) or bool(re.search(r'^Correction:', message, re.M))


def own_date(kind, rec, fallback):
    """(datetime, basis) -- the record's own date when it has one, else the author date."""
    candidates = {
        'benchmark-added': [('curation.added_on', 'curation.added_on')],
        'claim-added': [('date_reported', 'date_reported')],
        'source-rot-detected': [('link_checked_at', 'link_checked_at'), ('checked_at', 'checked_at')],
        'deprecation-detected': [('liveness.last_checked', 'liveness.last_checked')],
    }.get(kind, [])
    for path, basis in candidates:
        t = as_datetime(get(rec or {}, path))
        if t:
            return t, basis
    return fallback, 'author-date'


def benchmark_index(repo, rev='HEAD'):
    """{benchmark id: (family, [maintainer org ids])} from the benchmark files at `rev`."""
    try:
        paths = git(repo, 'ls-tree', '-r', '--name-only', rev, '--', 'data/benchmarks/').split()
    except subprocess.CalledProcessError:
        return {}
    out = {}
    for path in paths:
        m = BENCHMARK.match(path)
        if not m:
            continue
        rec = load(repo, rev, path) or {}
        maint = get(rec, 'governance.maintainers') or []
        out[rec.get('id') or m.group('id')] = (m.group('family'), [str(x) for x in maint if x])
    return out


def attribute(ev, rec, index):
    """families[] and organisations[] for the feed's per-domain feeds and its organisation filter.

    A benchmark event: its own family and governance.maintainers. A claim: its benchmark's family
    (the `@version` suffix of `benchmark` is dropped) and `reported_by`. A Source: the families of
    the benchmarks in its `cited_by`. The current tree is the lookup, so a benchmark that moved
    family is filed where it is now.
    """
    rec = rec or {}
    fams, orgs = set(), set()
    b = BENCHMARK.match(ev['path'])
    if b:  # every event on a benchmark file, corrections included, is filed under that benchmark
        fams.add(b.group('family'))
        orgs.update(str(x) for x in (get(rec, 'governance.maintainers') or []) if x)
    refs = []
    if rec.get('benchmark'):
        refs.append(str(rec['benchmark']).split('@', 1)[0])
    refs += [str(x) for x in (rec.get('cited_by') or [])]
    for ref in refs:
        if ref in index:
            fams.add(index[ref][0])
    if rec.get('reported_by'):
        orgs.add(str(rec['reported_by']))
    ev['families'] = sorted(fams)
    ev['organisations'] = sorted(orgs)


def derive(repo=ROOT):
    events = []
    index = benchmark_index(repo)
    for order, (sha, parent, authored, committed, message) in enumerate(commits(repo)):
        correction = is_correction(message)

        def emit(kind, entity, path, rec, **extra):
            when, basis = own_date(kind, rec, authored)
            events.append({
                'id': 'ev-' + hashlib.sha1(('%s|%s|%s' % (kind, sha, path)).encode()).hexdigest()[:12],
                'type': kind, 'entity': entity, 'path': path, 'date': iso(when), 'date_basis': basis,
                'published_on': iso(committed), 'commit': sha, 'order': order,
                'subject': message.splitlines()[0] if message else '', **extra})
            attribute(events[-1], rec, index)

        for status, old_path, new_path in changes(repo, parent, sha):
            if status == 'D':
                continue
            new = load(repo, sha, new_path)
            old = load(repo, parent, old_path) if status in 'MR' else None
            if new is None:
                continue
            b, c, s = BENCHMARK.match(new_path), CLAIM.match(new_path), SOURCE.match(new_path)
            if b:
                entity = new.get('id') or b.group('id')
                if status == 'A':
                    emit('benchmark-added', entity, new_path, new, family=b.group('family'))
                else:
                    reported = set()
                    if get(old, 'lifecycle') != get(new, 'lifecycle'):
                        emit('lifecycle-change', entity, new_path, new, family=b.group('family'),
                             before=jsonable(get(old, 'lifecycle')), after=jsonable(get(new, 'lifecycle')))
                        reported.add('lifecycle')
                    was, now = get(old, 'maintenance_status'), get(new, 'maintenance_status')
                    if now in STALE and was not in STALE:
                        emit('deprecation-detected', entity, new_path, new, family=b.group('family'),
                             before=was, after=now)
                        reported.add('maintenance_status')
                    material = [f for f in MATERIAL if f not in reported and get(old, f) != get(new, f)]
                    if material:
                        emit('benchmark-updated-material', entity, new_path, new, family=b.group('family'),
                             fields=material)
            elif c and status == 'A':
                machine = new_path.startswith('data/claims/_ingested/') or \
                    get(new, 'review_state') == 'machine-ingested' or \
                    get(new, 'ingestion.review_state') == 'machine-ingested'
                emit('claim-added', new.get('id') or c.group('id'), new_path, new,
                     benchmark=new.get('benchmark'), machine_ingested=bool(machine))
            elif s and status in 'MR':
                if get(new, 'link_status') == 'dead' and get(old, 'link_status') != 'dead':
                    emit('source-rot-detected', new.get('id') or s.group('id'), new_path, new,
                         before=get(old, 'link_status'), after='dead')
            if correction and status in 'MR' and old is not None:
                before, after = leaves(old), leaves(new)
                changed = [{'field': k, 'before': jsonable(before[k]), 'after': jsonable(after.get(k))}
                           for k in sorted(before) if before[k] is not None and after.get(k) != before[k]]
                if changed:
                    emit('correction', new.get('id') or os.path.splitext(os.path.basename(new_path))[0],
                         new_path, new, changes=changed)
    heads = {}
    for ev in events:
        if ev['path'] not in heads:
            rec = load(repo, 'HEAD', ev['path'])
            heads[ev['path']] = rec is not None and get(rec, 'curation.verification_status') not in UNPUBLISHABLE
        ev['publishable'] = heads[ev['path']]
    events.sort(key=lambda e: (e['type'], e['entity']))
    events.sort(key=lambda e: (e['date'], e['order']), reverse=True)  # stable: ties keep type, entity order
    return events


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--repo', default=ROOT)
    p.add_argument('--out', help='write the events here (JSON); default stdout')
    a = p.parse_args(argv)
    text = json.dumps(derive(a.repo), indent=2, ensure_ascii=False) + '\n'
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
