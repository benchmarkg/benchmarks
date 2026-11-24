"""The search index, Pagefind in both modes into one index (P2-S4-T06; tools/build/pagefind_records.py,
site/src/lib/pagefind.ts, scripts/check_pagefind_urls.py; 08 S3.2, S7.5; 10 V11).

The verify: `bench build --out build/ && python scripts/check_pagefind_urls.py --dist dist/`. Done when: "One index
covers both modes and the check fails on any URL indexed twice or any narrative route indexed zero times."

  records   pagefind_records.build over a small corpus and the repository's taxonomy: one record per entity at its
            route, carrying its type; a benchmark's filters are the browse values it is a member of, and `org` names
            published maintainers only; one record per facet-qualified term, an id a file repeats across fields being
            one record; a draft corpus refused unless the build is a preview; an absent corpus empty
  check     check_pagefind_urls over hand-made dists and bundles, the fragments written as Pagefind 1.6.0 writes them:
            a clean one passes, and each failure the done_when names fails -- a URL indexed twice, a narrative route
            indexed zero times -- beside the others: an entity route crawled instead of recorded, an entity route with
            no record, a record with no page, an unindexed route or a redirect indexed, a <body> without its ignore, a
            narrative <body> with one, a stale fragment, a second language
  node      site/src/lib/pagefind.ts's writeIndex over a hand-made dist with the real Pagefind: records and crawl in one
            index, which the check passes; a record at a narrative URL, or an entity page that lost its ignore, is
            indexed twice and fails it; a record whose page was not rendered fails a full build and is left out of a
            BENCH_ROUTES one; and three writes of one dist are one bundle, byte for byte (08 S3.1: S12 is deterministic)
  site      the populated case, over a fixture: no entry is published yet, so the site is built over
            tests/build/fixtures/minimal (one published benchmark, one metric, one organization), S12 runs at the end of
            `astro build` and checks its own bundle, and the check is run over it again here. The benchmark's record
            carries its facets as filters, each a value whose /browse/ page the build rendered
  verify    the verify's dist (site/dist), when one has been built: the production index, which today holds the
            narrative pages, the taxonomy terms and the published systems, organizations and metrics, and no benchmark
"""
import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_pagefind_urls as C  # noqa: E402
from tools.build import artifacts, freshness, ingest_health  # noqa: E402
from tools.build import pagefind_records as R  # noqa: E402

SITE = os.path.join(ROOT, 'site')
NODE = shutil.which('node')
NPX = shutil.which('npx') or shutil.which('npx.cmd')
HAS_PAGEFIND = os.path.isdir(os.path.join(SITE, 'node_modules', 'pagefind'))
FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data if isinstance(data, bytes) else data.encode('utf-8'))


# ---- records ------------------------------------------------------------------------------------------------------

BENCH = {
    'id': 'alpha-bench', 'name': 'Alpha Bench', 'aliases': ['AlphaBench'], 'tagline': 'A benchmark for tests',
    'description': None, 'released': '2025-03-01',
    'domain': {'primary': 'code/repository-scale-se', 'secondary': ['reasoning-general/logical-deduction']},
    'capability': ['deductive-reasoning', 'knowledge-recall'], 'evaluation_method': ['execution-tests'],
    'designed_for_subjects': ['reasoning-model'], 'lifecycle': 'active',
    'data': {'access': 'fully-open', 'ceiling_anchor_type': None},
    'governance': {'maintainer': 'Alpha Lab', 'maintainers': ['org-alpha', 'org-unpublished'],
                   'independence_flags': [{'flag': 'no-known-conflict', 'source': 'src-x'}],
                   'submission_process': 'self-reported'},
    'execution': {'compute_tier': 'single-gpu', 'reproducibility_blockers': ['wet-lab']},
}
CORPUS = {'artifact': 'corpus', 'entities': {
    'benchmark': [BENCH],
    'system': [{'id': 'sys-a', 'name': 'System A', 'organization': 'org-alpha', 'system_type': 'agent-scaffold',
                'availability': 'generally-available', 'api_identifier': 'sys-a-1', 'built_on': ['base@1'],
                'first_released': '2024-01-02'}],
    'organization': [{'id': 'org-alpha', 'name': 'Alpha Lab', 'kind': 'academic', 'roles': ['evaluator'],
                      'country': 'NL', 'parent': None}],
    'metric': [{'id': 'accuracy', 'name': 'Accuracy', 'full_name': 'Share correct', 'definition': 'The share.',
                'value_type': 'ratio', 'optimum': 'max', 'domains': ['code'], 'pitfalls': None}],
    'source': [{'id': 'src-x'}]}}


@pytest.fixture(scope='module')
def doc():
    return R.build(CORPUS)


def by_url(d):
    return {r['url']: r for r in d['records']}


def test_one_record_per_entity_at_its_route_with_its_type(doc):
    got = by_url(doc)
    for url, kind, title in (('/benchmarks/alpha-bench/', 'benchmark', 'Alpha Bench'),
                             ('/systems/sys-a/', 'system', 'System A'), ('/orgs/org-alpha/', 'organization', 'Alpha Lab'),
                             ('/metrics/accuracy/', 'metric', 'Accuracy')):
        r = got[url]
        assert r['filters']['type'] == [kind] and r['meta'] == {'title': title} and r['language'] == 'en'
        assert R.family(url) == (kind, R.RECORD, kind)
    assert doc['counts']['benchmark'] == doc['counts']['system'] == doc['counts']['organization'] == 1
    assert [r['url'] for r in doc['records']] == sorted(got, key=lambda u: u.encode('utf-8'))
    assert doc['artifact'] == 'pagefind-records' and doc['drafts'] is False and doc['language'] == 'en'


def test_a_benchmarks_filters_are_the_browse_values_it_is_a_member_of(doc):
    f = by_url(doc)['/benchmarks/alpha-bench/']['filters']
    assert f == {
        'type': ['benchmark'],
        'domain': ['code', 'code/repository-scale-se', 'reasoning-general', 'reasoning-general/logical-deduction'],
        'capability': ['deductive-reasoning', 'knowledge-recall'],
        'evaluation-method': ['execution-tests'], 'subject': ['reasoning-model'], 'lifecycle': ['active'],
        'access': ['fully-open'], 'independence-flags': ['no-known-conflict'], 'submission-process': ['self-reported'],
        'compute-tier': ['single-gpu'], 'reproducibility-blockers': ['wet-lab'],
        'org': ['org-alpha'],                          # org-unpublished maintains it too, but has no page
    }
    r = by_url(doc)['/benchmarks/alpha-bench/']
    assert r['sort'] == {'released': '2025-03-01'}
    for words in ('Alpha Bench.', 'AlphaBench.', 'A benchmark for tests.', 'Alpha Lab.',
                  'Capability: Knowledge recall, Deductive reasoning.'):          # in taxonomy order
        assert words in r['content'], words
    assert r['content'].count('Alpha Lab.') == 1                        # the display name and the org, said once


def test_the_other_kinds_carry_their_own_facets(doc):
    got = by_url(doc)
    assert got['/systems/sys-a/']['filters'] == {'type': ['system'], 'system-type': ['agent-scaffold'],
                                                 'availability': ['generally-available'], 'org': ['org-alpha']}
    assert 'by Alpha Lab.' in got['/systems/sys-a/']['content']
    assert got['/orgs/org-alpha/']['filters'] == {'type': ['organization'], 'organization-kind': ['academic'],
                                                  'role': ['evaluator'], 'country': ['NL']}
    assert got['/metrics/accuracy/']['filters'] == {'type': ['metric'], 'value-type': ['ratio'], 'optimum': ['max'],
                                                    'domain': ['code']}


def test_one_record_per_facet_qualified_term_and_a_repeated_id_is_one(doc):
    from schema.taxonomy import read_yaml
    expected = set()
    for name in os.listdir(os.path.join(ROOT, 'taxonomy')):
        if name.endswith('.yaml'):
            raw = read_yaml(os.path.join(ROOT, 'taxonomy', name))
            if isinstance(raw, dict) and isinstance(raw.get('facet'), str) and isinstance(raw.get('terms'), list):
                expected |= {R.term_url(raw['facet'], t['id']) for t in raw['terms']}
    terms = {r['url'] for r in doc['records'] if r['filters']['type'] == ['term']}
    assert terms == expected and doc['counts']['term'] == len(expected)
    wet = by_url(doc)['/taxonomy/execution/wet-lab/']                 # a compute tier and a reproducibility blocker
    assert wet['filters']['field'] == ['compute-tier', 'reproducibility-blockers']
    assert wet['filters']['facet'] == ['execution'] and wet['meta']['title']
    family = by_url(doc)['/taxonomy/domain/code/']                    # a spine facet: no field
    assert sorted(family['filters']) == ['facet', 'status', 'type'] and family['filters']['facet'] == ['domain']
    subdomain = by_url(doc)['/taxonomy/domain/code/repository-scale-se/']
    assert R.family(subdomain['url']) == ('term', R.RECORD, 'term') and subdomain['content'].startswith(
        subdomain['meta']['title'] + '. Domain term.')


def test_a_draft_corpus_is_refused_unless_the_build_is_a_preview(tmp_path):
    path = str(tmp_path / 'corpus.json')
    put(path, json.dumps(dict(CORPUS, drafts=True)))
    with pytest.raises(R.RecordsError, match='draft preview'):
        R.read_corpus(path)
    assert R.build(R.read_corpus(path, drafts=True))['drafts'] is True
    put(path, json.dumps({'artifact': 'facets'}))
    with pytest.raises(R.RecordsError, match='not the corpus artifact'):
        R.read_corpus(path)


def test_an_absent_corpus_is_empty_and_leaves_the_terms(tmp_path):
    d = R.build(R.read_corpus(str(tmp_path / 'missing.json')))
    assert {r['filters']['type'][0] for r in d['records']} == {'term'}


def test_two_records_at_one_url_are_refused():
    twice = {'artifact': 'corpus', 'entities': {'metric': CORPUS['entities']['metric'] * 2}}
    with pytest.raises(R.RecordsError, match='/metrics/accuracy/'):
        R.build(twice)


def test_the_command_line_writes_the_canonical_document(tmp_path, capsys):
    corpus, out = str(tmp_path / 'corpus.json'), str(tmp_path / 'records.json')
    put(corpus, json.dumps(CORPUS))
    assert R.main(['--corpus', corpus, '--out', out]) == 0
    with open(out, 'rb') as fh:
        raw = fh.read()
    assert raw == R.serialise(R.build(CORPUS))
    put(corpus, json.dumps(dict(CORPUS, drafts=True)))
    assert R.main(['--corpus', corpus]) == 1 and 'draft preview' in capsys.readouterr().err


@pytest.mark.parametrize('url, expect', [
    ('/', 'narrative'), ('/docs/methodology/', 'narrative'), ('/benchmarks/', 'narrative'), ('/sources/', 'narrative'),
    ('/benchmarks/x/', 'benchmark'), ('/benchmarks/x/v/1.0/', 'benchmark-version'), ('/benchmarks/x/claims/', 'claims-table'),
    ('/taxonomy/domain/code/repo-se/', 'term'), ('/browse/org/org-a/', 'browse'), ('/sources/src-a/', 'source'),
    ('/claims/c-1/', 'claim'), ('/conditions/cond-1/', 'conditions'), ('/orgs/org-a/', 'organization'),
])
def test_families_are_08_s7_5s_table(url, expect):
    assert R.family(url)[0] == expect


# ---- the check ----------------------------------------------------------------------------------------------------

def page(search='crawl', redirect=None, body='<main><h1>A page</h1><p>Some words to index.</p></main>'):
    if redirect:
        return ('<!doctype html><title>Redirecting to: %s</title><meta http-equiv="refresh" content="0;url=%s">'
                '<meta name="robots" content="noindex"><body><a href="%s">Redirecting</a></body>') % ((redirect,) * 3)
    head = '<meta data-pagefind-filter="type[content]" content="page" />' if search == 'crawl' else ''
    ignore = '' if search == 'crawl' else ' data-pagefind-ignore="all"'
    return '<!doctype html><html lang="en"><head><title>T</title>%s</head><body%s>%s</body></html>' % (head, ignore, body)


PAGES = {
    'index.html': page(), 'docs/method/index.html': page(),
    'benchmarks/alpha/index.html': page('record'), 'taxonomy/capability/planning/index.html': page('record'),
    'browse/capability/planning/index.html': page('none'), 'methodology/index.html': page(redirect='/docs/method/'),
    '_astro/x.css': 'body{}',
}
GOOD = [('/', 'page'), ('/docs/method/', 'page'), ('/benchmarks/alpha/', 'benchmark'),
        ('/taxonomy/capability/planning/', 'term')]


def fragment(url, kind):
    doc = {'url': url, 'content': 'words', 'word_count': 1, 'filters': {} if kind is None else {'type': [kind]},
           'meta': {'title': url}, 'anchors': []}
    return gzip.compress(C.SIGNATURE + json.dumps(doc).encode('utf-8'))


def bundle(dist, entries, pages=None, count=None, languages=('en',)):
    for rel, text in (pages or PAGES).items():
        put(os.path.join(dist, *rel.split('/')), text)
    for i, (url, kind) in enumerate(entries):
        put(os.path.join(dist, C.BUNDLE, C.FRAGMENTS, 'en_%07x.pf_fragment' % i), fragment(url, kind))
    n = len(entries) if count is None else count
    entry = {'version': '1.6.0', 'languages': {lang: {'hash': lang, 'wasm': lang, 'page_count': n if lang == 'en' else 0}
                                               for lang in languages}}
    put(os.path.join(dist, C.BUNDLE, C.ENTRY), json.dumps(entry))
    return dist


def test_a_clean_index_passes_and_says_what_it_holds(tmp_path):
    problems, s = C.check(bundle(str(tmp_path / 'dist'), GOOD))
    assert problems == []
    assert s == {'indexed': 4, 'routes': 5, 'records': {'benchmark': 1, 'term': 1}, 'narrative': 2, 'unindexed': 1,
                 'redirects': 1}


def test_a_narrative_page_without_base_is_a_crawl_too(tmp_path):
    """A page with its own shell carries no `type` filter unless it says so (feed/index.astro does): absent is the crawl."""
    problems, _ = C.check(bundle(str(tmp_path / 'dist'), GOOD[:1] + [('/docs/method/', None)] + GOOD[2:]))
    assert problems == []


@pytest.mark.parametrize('entries, pages, expect', [
    (GOOD + [('/docs/method/', 'page')], None, '/docs/method/: indexed 2 times'),                      # the done_when
    (GOOD + [('/benchmarks/alpha/', 'benchmark')], None, '/benchmarks/alpha/: indexed 2 times'),
    ([e for e in GOOD if e[0] != '/docs/method/'], None, '/docs/method/: a narrative route indexed zero times'),
    ([e for e in GOOD if e[0] != '/'], None, '/: a narrative route indexed zero times'),
    ([e if e[0] != '/benchmarks/alpha/' else (e[0], 'page') for e in GOOD], None,
     '/benchmarks/alpha/: a benchmark route indexed as page, not by its benchmark record'),
    ([e for e in GOOD if e[1] != 'term'], None, '/taxonomy/capability/planning/: a term route indexed zero times'),
    (GOOD + [('/systems/ghost/', 'system')], None, '/systems/ghost/: indexed, but no page renders it'),
    (GOOD + [('/browse/capability/planning/', 'page')], None, 'which 08 S7.5 Decision 2 leaves out of the index'),
    (GOOD + [('/methodology/', 'page')], None, '/methodology/: a redirect (methodology/index.html), indexed 1'),
    ([e if e[0] != '/docs/method/' else (e[0], 'metric') for e in GOOD], None,
     "/docs/method/: a narrative route indexed as metric, which is a record's type"),
    (GOOD, dict(PAGES, **{'benchmarks/alpha/index.html': page()}),
     '/benchmarks/alpha/: a benchmark route whose <body> lacks data-pagefind-ignore'),
    (GOOD, dict(PAGES, **{'browse/capability/planning/index.html': page()}),
     '/browse/capability/planning/: a browse route whose <body> lacks data-pagefind-ignore'),
    (GOOD, dict(PAGES, **{'docs/method/index.html': page('none')}),
     '/docs/method/: a narrative route whose <body> carries data-pagefind-ignore'),
])
def test_each_failure_fails(tmp_path, entries, pages, expect):
    problems, _ = C.check(bundle(str(tmp_path / 'dist'), entries, pages))
    assert any(expect in p for p in problems), problems


def test_a_stale_fragment_or_a_second_language_fails(tmp_path):
    problems, _ = C.check(bundle(str(tmp_path / 'a'), GOOD, count=3))
    assert any('counts 3 indexed page(s), but fragment/ holds 4' in p for p in problems), problems
    problems, _ = C.check(bundle(str(tmp_path / 'b'), GOOD, languages=('en', 'unknown')))
    assert any("languages ['en', 'unknown'], not one index in 'en'" in p for p in problems), problems
    dist = bundle(str(tmp_path / 'c'), GOOD)
    put(os.path.join(dist, C.BUNDLE, C.FRAGMENTS, 'en_zz.pf_fragment'), gzip.compress(b'{"url": "/"}'))
    put(os.path.join(dist, C.BUNDLE, C.ENTRY), json.dumps({'languages': {'en': {'page_count': 5}}}))
    assert any('no pagefind_dcd signature' in p for p in C.check(dist)[0])


def test_the_command_line(tmp_path, capsys):
    assert C.main(['--dist', str(tmp_path / 'nothing')]) == 2
    put(str(tmp_path / 'bare' / 'index.html'), page())
    assert C.main(['--dist', str(tmp_path / 'bare')]) == 2 and 'S12' in capsys.readouterr().out
    assert C.main(['--dist', bundle(str(tmp_path / 'ok'), GOOD)]) == 0
    assert '4 indexed URL(s) over 5 route(s): 2 record(s) (1 benchmark, 1 term), 2 narrative' in capsys.readouterr().out
    assert C.main(['--dist', bundle(str(tmp_path / 'bad'), GOOD + [('/', 'page')])]) == 1
    assert 'BLOCKING  pagefind  /: indexed 2 times' in capsys.readouterr().out


# ---- site/src/lib/pagefind.ts, with the real Pagefind ---------------------------------------------------------------

needs_pagefind = pytest.mark.skipif(not (NODE and HAS_PAGEFIND), reason='node or site/node_modules/pagefind missing')

DRIVER = """
import { readFileSync } from 'node:fs';
import { parseRecords, writeIndex, checkIndex } from %s;
const [dist, records, restricted, check] = process.argv.slice(1);
try {
  const s = await writeIndex(dist, parseRecords(readFileSync(records, 'utf8')), restricted === '1');
  const out = { summary: s };
  if (check === '1') { try { out.check = checkIndex(dist); } catch (e) { out.checkError = String(e.message); } }
  console.log(JSON.stringify(out));
} catch (e) {
  console.log(JSON.stringify({ error: String(e.message) }));
}
"""


def write_index(dist, records, restricted=False, check=False):
    """lib/pagefind.ts writeIndex over `dist` with `records` (a list of record dicts); its JSON result."""
    path = os.path.join(os.path.dirname(dist), 'records.json')
    put(path, json.dumps({'artifact': 'pagefind-records', 'format': 1, 'language': 'en', 'drafts': False,
                          'counts': {}, 'records': records}))
    module = json.dumps('file:///' + os.path.join(SITE, 'src', 'lib', 'pagefind.ts').replace('\\', '/'))
    r = subprocess.run([NODE, '--input-type=module', '-e', DRIVER % module, dist, path, '1' if restricted else '0',
                        '1' if check else '0'], capture_output=True, text=True, encoding='utf-8', cwd=SITE,
                       env=dict(os.environ, BENCH_PYTHON=sys.executable), timeout=300)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def record(url, kind, words='record words'):
    return {'url': url, 'content': words, 'language': 'en', 'meta': {'title': url}, 'filters': {'type': [kind]}}


RECORDS = [record('/benchmarks/alpha/', 'benchmark', 'Alpha benchmark words'),
           record('/taxonomy/capability/planning/', 'term', 'Planning term words')]


def site_dir(tmp_path, name='dist'):
    dist = str(tmp_path / name)
    for rel, text in PAGES.items():
        put(os.path.join(dist, *rel.split('/')), text)
    return dist


@needs_pagefind
def test_records_and_the_crawl_go_into_one_index_that_the_check_passes(tmp_path):
    dist = site_dir(tmp_path)
    put(os.path.join(dist, 'pagefind', 'fragment', 'en_stale.pf_fragment'), b'left by an earlier build')
    got = write_index(dist, RECORDS, check=True)
    assert got['summary']['records'] == 2 and got['summary']['skipped'] == []
    assert 'checkError' not in got, got.get('checkError')
    assert '0 problem(s)' in got['check']
    problems, s = C.check(dist)
    assert problems == [] and s['records'] == {'benchmark': 1, 'term': 1} and s['narrative'] == 2
    found, _ = C.fragments(dist)
    assert sorted(f['url'] for f in found) == ['/', '/benchmarks/alpha/', '/docs/method/', '/taxonomy/capability/planning/']
    crawled = next(f for f in found if f['url'] == '/docs/method/')
    assert crawled['filters'] == {'type': ['page']} and 'Some words to index.' in crawled['content']
    assert not os.path.exists(os.path.join(dist, 'pagefind', 'fragment', 'en_stale.pf_fragment'))
    with open(os.path.join(dist, 'pagefind', 'pagefind-entry.json'), encoding='utf-8') as fh:
        assert list(json.load(fh)['languages']) == ['en']


@needs_pagefind
def test_a_record_at_a_narrative_url_is_indexed_twice_and_fails(tmp_path):
    dist = site_dir(tmp_path)
    got = write_index(dist, RECORDS + [record('/docs/method/', 'metric')], check=True)
    assert '/docs/method/: indexed 2 times' in got['checkError']
    problems, _ = C.check(dist)
    assert any(p.startswith('/docs/method/: indexed 2 times') for p in problems), problems


@needs_pagefind
def test_an_entity_page_that_lost_its_ignore_is_indexed_twice_and_fails(tmp_path):
    dist = site_dir(tmp_path)
    put(os.path.join(dist, 'benchmarks', 'alpha', 'index.html'), page())          # crawled as well as recorded
    assert write_index(dist, RECORDS)['summary']['records'] == 2
    problems, _ = C.check(dist)
    assert any(p.startswith('/benchmarks/alpha/: indexed 2 times') for p in problems), problems
    assert any('lacks data-pagefind-ignore' in p for p in problems), problems


@needs_pagefind
def test_two_writes_of_one_dist_are_one_bundle_byte_for_byte(tmp_path):
    """08 S3.1 lists S12 as deterministic. Pagefind 1.5.2 failed this (its filter files came out in another order on
    every run); 1.6.0 passes it, which is why the site pins 1.6.0 (docs/pins.md note 6)."""
    records = RECORDS + [record('/taxonomy/domain/code/%d/' % i, 'term') for i in range(30)]
    for r in records:
        r['filters'].update({'facet': ['f%d' % (len(r['url']) % 7), 'g'], 'status': ['active', 'proposed']})
    pages = dict(PAGES, **{'taxonomy/domain/code/%d/index.html' % i: page('record') for i in range(30)})
    digests = []
    for name in ('a', 'b', 'c'):
        dist = str(tmp_path / name)
        for rel, text in pages.items():
            put(os.path.join(dist, *rel.split('/')), text)
        write_index(dist, records)
        bundle, files = os.path.join(dist, 'pagefind'), []
        for d, _, ns in os.walk(bundle):
            for n in ns:
                with open(os.path.join(d, n), 'rb') as fh:
                    files.append((os.path.relpath(os.path.join(d, n), bundle).replace(os.sep, '/'), fh.read()))
        digests.append(sorted(files))
    assert digests[0] == digests[1] == digests[2]
    assert any(rel.startswith('filter') for rel, _ in digests[0])


@needs_pagefind
def test_a_record_without_its_page_fails_a_full_build_and_is_skipped_in_a_bench_routes_one(tmp_path):
    ghost = RECORDS + [record('/systems/ghost/', 'system')]
    got = write_index(site_dir(tmp_path, 'full'), ghost)
    assert 'name a route this build did not render, e.g. /systems/ghost/' in got['error']
    got = write_index(site_dir(tmp_path, 'preview'), ghost, restricted=True)
    assert got['summary']['skipped'] == ['/systems/ghost/'] and got['summary']['records'] == 2
    assert C.check(str(tmp_path / 'preview'))[0] == []


# ---- the populated case: the site built over the minimal fixture ----------------------------------------------------

BASE = os.path.join(ROOT, 'build', 'pagefind-test')
TREE = os.path.join(BASE, 'root')


@pytest.fixture(scope='module')
def built():
    """The minimal fixture's corpus (one published benchmark, its metric and its maintainer's organization), the site
    built over it, and S12 at the end of the build. TREE is the fixture's data/ beside the repository's taxonomy/ and
    CITATION.cff, inside the checkout and on its volume, as tests/build/test_artifact_urls.py builds it."""
    if not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and NPX and HAS_PAGEFIND):
        pytest.skip('site/node_modules is not installed')
    shutil.rmtree(BASE, ignore_errors=True)
    shutil.copytree(os.path.join(FIXTURE, 'data'), os.path.join(TREE, 'data'))
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), os.path.join(TREE, 'taxonomy'))
    shutil.copy(os.path.join(ROOT, 'CITATION.cff'), os.path.join(TREE, 'CITATION.cff'))
    out, dist = os.path.join(BASE, 'build'), os.path.join(BASE, 'dist')
    result = artifacts.build(TREE)
    assert not result.errors, result.errors
    artifacts.write(result, out)
    as_of = dt.date(2026, 11, 18)
    health = ingest_health.build(TREE, as_of)
    put(os.path.join(BASE, 'ingest-health.json'), ingest_health.serialise(health))
    put(os.path.join(BASE, 'freshness.json'), freshness.serialise(freshness.build(TREE, as_of, health)))
    put(os.path.join(BASE, 'feed-events.json'), b'[]\n')
    env = dict(os.environ, UAIBI_CORPUS=os.path.join(out, 'corpus.json'), REPO_ROOT=TREE, BENCH_PYTHON=sys.executable,
               INGEST_HEALTH=os.path.join(BASE, 'ingest-health.json'), FRESHNESS=os.path.join(BASE, 'freshness.json'),
               FEED_EVENTS=os.path.join(BASE, 'feed-events.json'), ASTRO_TELEMETRY_DISABLED='1')
    for name in ('UAIBI_SITE_DRAFTS', 'BENCH_ROUTES', 'UAIBI_SITE_FIXTURES'):
        env.pop(name, None)
    r = subprocess.run([NPX, 'astro', 'build', '--outDir', dist], cwd=SITE, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=1800)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return dict(dist=dist, log=r.stdout + r.stderr, corpus=result.corpus)


@pytest.mark.skipif(not (NPX and HAS_PAGEFIND), reason='site/node_modules is not installed')
def test_the_built_site_holds_one_index_that_the_check_passes(built):
    assert 'S12: ' in built['log'] and 'check_pagefind_urls: ' in built['log']        # the build ran both steps
    problems, s = C.check(built['dist'])
    assert problems == []
    entities = built['corpus']['entities']
    assert s['records']['benchmark'] == len(entities['benchmark']) == 1
    assert s['records']['metric'] == len(entities['metric']) and s['records']['organization'] == len(entities['organization'])
    assert s['records']['term'] == R.build({'artifact': 'corpus', 'entities': {}})['counts']['term']
    assert s['narrative'] >= 5 and s['unindexed'] > 0 and s['redirects'] == 1        # /methodology redirects
    assert C.main(['--dist', built['dist']]) == 0


@pytest.mark.skipif(not (NPX and HAS_PAGEFIND), reason='site/node_modules is not installed')
def test_the_benchmarks_record_carries_its_facets_and_each_is_a_rendered_browse_page(built):
    found, _ = C.fragments(built['dist'])
    alpha = next(f for f in found if f['url'] == '/benchmarks/alpha-bench/')
    assert alpha['meta']['title'] == 'Alpha Bench' and 'AlphaBench' in alpha['content']
    f = alpha['filters']
    assert f['type'] == ['benchmark'] and f['capability'] == ['deductive-reasoning', 'knowledge-recall']
    assert {'code', 'code/repository-scale-se', 'reasoning-general/logical-deduction'} <= set(f['domain'])
    pages = C.rendered(built['dist'])
    for seg, values in f.items():
        if seg != 'type':
            for v in values:
                assert '/browse/%s/%s/' % (seg, v) in pages, (seg, v)      # the filter selects what that page lists
    # a crawled page's entry is its own words: the shell's footer (release, commit) is data-pagefind-ignore
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    narrative = [x for x in found if (x['filters'].get('type') or ['page']) == ['page']]
    assert narrative and len(head) == 40
    assert not [x['url'] for x in narrative if 'no tagged release yet' in x['content'] or head[:12] in x['content']]


# ---- the verify's dist --------------------------------------------------------------------------------------------

def test_the_verifys_dist_passes_when_it_has_been_built():
    dist = os.path.join(SITE, 'dist')
    if not os.path.exists(os.path.join(dist, C.BUNDLE, C.ENTRY)):
        pytest.skip('no site/dist/pagefind/: run `uv run bench build --out build/` and `cd site && npx astro build`')
    problems, s = C.check(dist)
    assert problems == []
    assert s['narrative'] > 0 and s['records'].get('term', 0) > 0
