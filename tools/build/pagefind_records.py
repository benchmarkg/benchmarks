#!/usr/bin/env python3
"""The search index's custom records, one per entity route, from validated YAML (P2-S4-T06; 08 S3.2 S12, S7.5; 10 V11).

    python tools/build/pagefind_records.py --corpus build/corpus.json                # the records document, to stdout
    python tools/build/pagefind_records.py --corpus build/corpus.json --out PATH     # or to a file

08 S3.2: "Pagefind runs in both of its modes, into one index". This module is the first mode's input, and
site/src/lib/pagefind.ts, S12, which runs at the end of every `astro build`, runs both:

  addCustomRecord()   one record per entity route, built here from validated YAML rather than scraped from the
                      page: the benchmarks, systems, organizations and metrics of the corpus the site was rendered
                      from (`bench build`'s corpus.json: every record through the four validation tiers, drafts
                      withheld), and the taxonomy terms of taxonomy/*.yaml, every file through its Pydantic model
                      (schema.taxonomy.load_taxonomy). "Facets become Pagefind `filters` for free, the index cannot
                      drift from the data model, and the search bundle stops depending on the DOM structure of the
                      templates."
  the crawl           of dist/, for the narrative pages that exist only as HTML: the /docs/ pages, the views, /api/,
                      /sources/, /freshness/, the feed. Every entity route's <body> carries data-pagefind-ignore
                      (site/src/layouts/Base.astro, `search`), so the crawl skips exactly what a record covers.

08 S7.5 Decision 2 names the indexed families: "Benchmarks, systems, organizations, metrics and taxonomy terms, plus
the narrative pages." The rest -- version-pinned views, claims tables, claim and conditions permalinks, source pages,
/browse/ -- carry data-pagefind-ignore and are in neither mode. FAMILIES is that table, and
scripts/check_pagefind_urls.py holds every built index to it.

One reading where 08 S3.2 and S7.5 differ: S3.2 lists "the taxonomy term prose" among the crawl's targets, S7.5
and this task make taxonomy terms one of the five record families. A term page is an entity route here, and its
record is the term's definition, tests, distinctions and worked examples as taxonomy/ holds them.

A record, as Pagefind's addCustomRecord() takes it (10 V11: "url, content, language, meta, filters (key -> string[])
and sort"):

  url       the route the site renders the entity at, as the pages' getStaticPaths() spell it (ROUTES, term_url)
  content   the words a reader searches for: a benchmark's name, aliases, tagline, description and maintainer and the
            labels of the terms it carries; a system's name, API identifier, developer and type; an organization's
            name, kind, roles, country and parent; a metric's name, full name, definition, units and pitfalls; a
            term's label, definition, inclusion and exclusion tests, derivation, near misses and examples. Each part
            ends as a sentence, so an excerpt reads as one
  language  'en', the one language of the one index (S12 forces the crawl to it too)
  meta      title: the entity's name, or the term's label
  filters   `type` on every record (benchmark, system, organization, metric, term; a crawled page says `page`), and
            each kind's facets. A benchmark's are the single-facet browse values (site/src/lib/browse.ts): one filter
            per browse segment -- domain, capability, evaluation-method, subject, access, lifecycle, maintainer-type,
            compute-tier and the rest -- whose values are the terms the benchmark is a member of by the rule the term
            and browse pages list members by (site/src/lib/terms.ts members()), and `org`, the published organizations
            that maintain it. So the filter {segment: [term]} selects what /browse/{segment}/{term}/ lists. A system
            has system-type, availability and org; an organization organization-kind, role and country; a metric
            value-type, optimum and domain; a term facet, status and, for a field vocabulary, field
  sort      `released`, an ISO date: a benchmark's released, a system's first_released, where the record has one

Values are ids, never labels: they are what the filter-URL grammar and the browse routes spell.

A draft preview corpus (scripts/preview_corpus.py, `"drafts": true`) is refused unless --drafts says the site build
is a preview (site/src/lib/corpus.ts holds the same line with UAIBI_SITE_DRAFTS=1). A corpus file that does not exist
is an empty corpus, as it is to the site: the records are then the taxonomy terms alone. No entry is published yet,
so the production records are the taxonomy terms and the published systems, organizations and metrics; a populated
benchmark record is tests/build/test_pagefind.py's, over the minimal fixture.

Deterministic: records sorted by url, canonical JSON (tools/build/emit.serialise), no clock.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ARTIFACT = 'pagefind-records'
FORMAT = 1
LANGUAGE = 'en'
ROUTES = {                                   # kind -> route, as src/pages/*/[id] render them
    'benchmark': '/benchmarks/%s/',
    'system': '/systems/%s/',
    'organization': '/orgs/%s/',
    'metric': '/metrics/%s/',
}
KINDS = tuple(ROUTES) + ('term',)
PAGE = 'page'                                # the `type` a crawled page carries (Base.astro)
TYPE = 'type'
ORG = 'org'                                  # /browse/org/{id}/'s segment (site/src/lib/browse.ts ORG_SEGMENT)

# 08 S7.5's route families, by URL: (family, pattern, mode, record type). `record`: a custom record, its <body> ignored
# by the crawl; `none`: in neither mode, its <body> ignored. A route no pattern matches is narrative, a crawl target.
# The unindexed families no page renders yet (claims tables, claim and conditions permalinks, source pages) are here
# so that the day one is built, it is held out of the index from its first build.
RECORD, NONE, CRAWL = 'record', 'none', 'crawl'
FAMILIES = (
    ('benchmark', r'/benchmarks/[^/]+/', RECORD, 'benchmark'),
    ('benchmark-version', r'/benchmarks/[^/]+/v/[^/]+/', NONE, None),
    ('claims-table', r'/benchmarks/[^/]+/claims/', NONE, None),
    ('system', r'/systems/[^/]+/', RECORD, 'system'),
    ('organization', r'/orgs/[^/]+/', RECORD, 'organization'),
    ('metric', r'/metrics/[^/]+/', RECORD, 'metric'),
    ('term', r'/taxonomy/[^/]+/.+/', RECORD, 'term'),
    ('claim', r'/claims/.+/', NONE, None),
    ('conditions', r'/conditions/.+/', NONE, None),
    ('source', r'/sources/.+/', NONE, None),
    ('browse', r'/browse/.+/', NONE, None),
)
NARRATIVE = ('narrative', CRAWL, PAGE)

# terms.ts FIELD: the spine facets map one-to-one onto a Benchmark field; a field vocabulary names its own `field`
SPINE_FIELD = {'capability': 'capability', 'evaluation_method': 'evaluation_method', 'subject': 'designed_for_subjects'}
DERIVED_FACETS = frozenset({'maintenance_status'})      # computed from observable signals, never curated: no members


class RecordsError(Exception):
    """The records cannot be built: S12 stops on it."""


def family(url: str) -> tuple[str, str, str | None]:
    """(family, mode, record type) of a rendered route's URL."""
    for name, pattern, mode, kind in FAMILIES:
        if re.fullmatch(pattern, url):
            return name, mode, kind
    return NARRATIVE


def term_url(facet: str, term_id: str) -> str:
    """/taxonomy/{facet}/{term}/, the facet in kebab case (terms.ts facetSegment, termHref)."""
    return '/taxonomy/%s/%s/' % (facet.replace('_', '-'), term_id)


def segment(facet: str, field: str | None) -> str:
    """The browse segment of a term: the last part of its field, or its facet, in kebab case (browse.ts browseSegment)."""
    return (field or facet).split('.')[-1].replace('_', '-')


def sentence(text) -> str | None:
    """A part of a record's content, ending as a sentence; None for nothing to say."""
    if not isinstance(text, str) or not text.strip():
        return None
    text = ' '.join(text.split())
    return text if text[-1] in '.!?:;' else text + '.'


def content(parts) -> str:
    """The parts as sentences, each once (a maintainer's display name is often its organization's name)."""
    return ' '.join(dict.fromkeys(p for p in (sentence(x) for x in parts) if p))


def words(value: str) -> str:
    """An enum id as words: agent-scaffold -> agent scaffold."""
    return value.replace('-', ' ').replace('_', ' ')


def ids(value) -> list[str]:
    """A scalar or a list of ids, as a list."""
    if value is None:
        return []
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


# ---- the taxonomy ---------------------------------------------------------------------------------------------------

def facet_files(root: str = ROOT) -> list[tuple[str, list]]:
    """[(facet, [term model, ...])] for every taxonomy file that declares `facet:` and `terms:`, by file name -- the
    files site/src/lib/terms.ts renders a page per term of -- each validated through schema.taxonomy."""
    from schema.taxonomy import TaxonomyError, load_taxonomy
    try:
        models, _ = load_taxonomy(os.path.join(root, 'taxonomy'))
    except TaxonomyError as e:
        raise RecordsError('taxonomy/ does not validate, so no term record is built from it:\n  %s'
                           % '\n  '.join(e.errors)) from e
    out = []
    for name in sorted(models):
        facet, terms = getattr(models[name], 'facet', None), getattr(models[name], 'terms', None)
        if isinstance(facet, str) and isinstance(terms, list):
            out.append((facet, terms))
    return out


def term_records(files: list[tuple[str, list]]) -> list[dict]:
    """One record per facet-qualified term id: an id a file repeats across fields is one page with every sense (9c)."""
    out = []
    for facet, terms in files:
        senses: dict[str, list] = {}
        for t in terms:
            senses.setdefault(t.id, []).append(t)
        for term_id, group in senses.items():
            parts = []
            for t in group:
                field = getattr(t, 'field', None)
                parts += [t.label, '%s term%s' % (words(facet).capitalize(), ', field %s' % field if field else ''),
                          t.definition, getattr(t, 'inclusion_test', None), getattr(t, 'exclusion_test', None),
                          getattr(t, 'derivation', None)]
                parts += ['Not to be confused with %s: %s' % (c.term, c.distinction)
                          for c in getattr(t, 'not_to_be_confused_with', [])]
                parts += ['%s %s: %s' % ('Example' if e.qualifies else 'Near miss', e.ref, e.why) for e in t.examples]
            filters = {TYPE: ['term'], 'facet': [facet.replace('_', '-')],
                       'status': sorted({t.status for t in group})}
            fields = sorted({segment(facet, t.field) for t in group if getattr(t, 'field', None)})
            if fields:
                filters['field'] = fields
            out.append({'url': term_url(facet, term_id), 'content': content(parts), 'language': LANGUAGE,
                        'meta': {'title': group[0].label}, 'filters': filters})
    return out


# ---- the entities ---------------------------------------------------------------------------------------------------

def at(record, dotted: str):
    """record's value at a dotted field path (terms.ts at)."""
    for key in dotted.split('.'):
        record = record.get(key) if isinstance(record, dict) else None
    return record


def carries(benchmark: dict, facet: str, term) -> bool:
    """terms.ts members(): whether `benchmark` is a member of `term`'s page."""
    if facet in DERIVED_FACETS:
        return False
    if facet == 'domain':
        domain = benchmark.get('domain') or {}
        hit = (lambda d: d == term.id or d.startswith(term.id + '/'))
        return any(hit(d) for d in ids(domain.get('primary')) + ids(domain.get('secondary')))
    field = SPINE_FIELD.get(facet) or getattr(term, 'field', None)
    if field is None:
        return False
    value = at(benchmark, field)
    values = value if isinstance(value, list) else [] if value is None else [value]
    return any((v.get('flag') if isinstance(v, dict) else v) == term.id for v in values)


def labels_by_segment(benchmark: dict, files: list[tuple[str, list]]) -> dict[str, list]:
    """segment -> [term model, ...] the benchmark carries, in taxonomy file and term order."""
    out: dict[str, list] = {}
    for facet, terms in files:
        for t in terms:
            if carries(benchmark, facet, t):
                out.setdefault(segment(facet, getattr(t, 'field', None)), []).append(t)
    return out


def benchmark_record(b: dict, files, orgs: dict[str, dict]) -> dict:
    carried = labels_by_segment(b, files)
    gov = b.get('governance') or {}
    maintainers = [o for o in ids(gov.get('maintainers')) if o in orgs]
    parts = [b['name'], 'Benchmark', ', '.join(ids(b.get('aliases'))), b.get('tagline'), b.get('description'),
             gov.get('maintainer'), ', '.join(orgs[o]['name'] for o in maintainers)]
    parts += ['%s: %s' % (words(seg).capitalize(), ', '.join(t.label for t in ts)) for seg, ts in carried.items()]
    filters = {TYPE: ['benchmark']}
    for seg, ts in carried.items():
        filters[seg] = sorted({t.id for t in ts})
    if maintainers:
        filters[ORG] = sorted(set(maintainers))
    record = {'url': ROUTES['benchmark'] % b['id'], 'content': content(parts), 'language': LANGUAGE,
              'meta': {'title': b['name']}, 'filters': filters}
    if b.get('released'):
        record['sort'] = {'released': str(b['released'])}
    return record


def system_record(s: dict, orgs: dict[str, dict]) -> dict:
    org = orgs.get(s.get('organization') or '')
    parts = [s['name'], 'System', s.get('api_identifier'), 'by %s' % org['name'] if org else None,
             words(s['system_type']) if s.get('system_type') else None,
             words(s['availability']) if s.get('availability') else None,
             'Built on %s' % ', '.join(ids(s.get('built_on'))) if s.get('built_on') else None]
    filters = {TYPE: ['system']}
    for key, field in (('system-type', 'system_type'), ('availability', 'availability')):
        if s.get(field):
            filters[key] = [s[field]]
    if org:
        filters[ORG] = [org['id']]
    record = {'url': ROUTES['system'] % s['id'], 'content': content(parts), 'language': LANGUAGE,
              'meta': {'title': s['name']}, 'filters': filters}
    if s.get('first_released'):
        record['sort'] = {'released': str(s['first_released'])}
    return record


def organization_record(o: dict, orgs: dict[str, dict]) -> dict:
    parent = orgs.get(o.get('parent') or '')
    roles = ids(o.get('roles'))
    parts = [o['name'], 'Organization', words(o['kind']) if o.get('kind') else None,
             ', '.join(words(r) for r in roles) if roles else None, o.get('country'),
             'Part of %s' % parent['name'] if parent else None]
    filters = {TYPE: ['organization']}
    if o.get('kind'):
        filters['organization-kind'] = [o['kind']]
    if roles:
        filters['role'] = sorted(set(roles))
    if o.get('country'):
        filters['country'] = [o['country']]
    return {'url': ROUTES['organization'] % o['id'], 'content': content(parts), 'language': LANGUAGE,
            'meta': {'title': o['name']}, 'filters': filters}


def metric_record(m: dict) -> dict:
    parts = [m['name'], 'Metric', m.get('full_name'), m.get('definition'), m.get('units'),
             m.get('aggregation') if isinstance(m.get('aggregation'), str) else None,
             m.get('pitfalls')]
    filters = {TYPE: ['metric']}
    for key, field in (('value-type', 'value_type'), ('optimum', 'optimum')):
        if isinstance(m.get(field), str):
            filters[key] = [m[field]]
    if ids(m.get('domains')):
        filters['domain'] = sorted(set(ids(m['domains'])))
    return {'url': ROUTES['metric'] % m['id'], 'content': content(parts), 'language': LANGUAGE,
            'meta': {'title': m['name']}, 'filters': filters}


# ---- the document ---------------------------------------------------------------------------------------------------

def read_corpus(path: str, drafts: bool = False) -> dict:
    """The corpus the site was rendered from: an absent file is an empty corpus (site/src/lib/corpus.ts)."""
    if not os.path.exists(path):
        return {'artifact': 'corpus', 'entities': {}, 'drafts': False}
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or doc.get('artifact') != 'corpus':
        raise RecordsError('%s is not the corpus artifact (artifact: %r)'
                           % (path, doc.get('artifact') if isinstance(doc, dict) else None))
    if doc.get('drafts') is True and not drafts:
        raise RecordsError('%s is a draft preview (scripts/preview_corpus.py): its ai-drafted-unverified entries are '
                           'never published (05 S4), so they get no search record unless --drafts says the site build '
                           'is a preview (UAIBI_SITE_DRAFTS=1)' % path)
    return doc


def build(corpus: dict, root: str = ROOT) -> dict:
    """The records document for `corpus` (corpus.json's shape) and root's taxonomy/."""
    entities = corpus.get('entities') or {}
    kind = lambda k: entities.get(k, [])                                  # get-default: an empty corpus has no kinds
    orgs = {o['id']: o for o in kind('organization')}
    files = facet_files(root)
    records = term_records(files)
    records += [benchmark_record(b, files, orgs) for b in kind('benchmark')]
    records += [system_record(s, orgs) for s in kind('system')]
    records += [organization_record(o, orgs) for o in orgs.values()]
    records += [metric_record(m) for m in kind('metric')]
    seen: dict[str, int] = {}
    for r in records:
        seen[r['url']] = seen.get(r['url'], 0) + 1                        # get-default: a URL's first record
    twice = sorted(u for u, n in seen.items() if n > 1)
    if twice:
        raise RecordsError('%d URL(s) would carry two records, and the index would answer twice: %s'
                           % (len(twice), ', '.join(twice)))
    for r in records:
        if family(r['url'])[1] != RECORD:
            raise RecordsError('%s is not a route of a record family (FAMILIES)' % r['url'])
    records.sort(key=lambda r: r['url'].encode('utf-8'))
    counts = dict.fromkeys(KINDS, 0)
    for r in records:
        counts[r['filters'][TYPE][0]] += 1
    return {'artifact': ARTIFACT, 'format': FORMAT, 'language': LANGUAGE, 'drafts': corpus.get('drafts') is True,
            'counts': counts, 'records': records}


def serialise(doc: dict) -> bytes:
    from tools.build.emit import serialise as canonical
    return canonical(doc)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--corpus', default=os.path.join(ROOT, 'build', 'corpus.json'),
                   help='the corpus.json the site was rendered from (default: build/corpus.json); absent is empty')
    p.add_argument('--root', default=ROOT, help='the tree whose taxonomy/ the site read (default: this checkout)')
    p.add_argument('--drafts', action='store_true', help='accept a draft preview corpus (a preview site build)')
    p.add_argument('--out', help='write the document here instead of to stdout')
    a = p.parse_args(argv)
    try:
        doc = build(read_corpus(a.corpus, a.drafts), a.root)
    except RecordsError as e:
        print('pagefind_records: %s' % e, file=sys.stderr)
        return 1
    raw = serialise(doc)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'wb') as fh:
            fh.write(raw)
        print('wrote %s (%d record(s): %s)' % (a.out, len(doc['records']),
                                               ', '.join('%d %s' % (n, k) for k, n in doc['counts'].items())),
              file=sys.stderr)
    else:
        sys.stdout.buffer.write(raw)
    return 0


if __name__ == '__main__':
    sys.exit(main())
