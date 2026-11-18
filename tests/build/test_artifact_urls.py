"""build-manifest.json and the three artifact URL namespaces (P2-S1-T05; tools/build/manifest.py; 08 S4.4, S6.1).

The verify: `bench build --out build/ && pytest tests/build/test_artifact_urls.py`. Done when: "Every HTML data
reference is content-hashed and immutable-cached, /data/latest/ redirects, and the manifest names every hashed
artifact with its hash, the commit SHA and the file count."

  hashing    manifest.write over throwaway artifacts: each one at data/<name>.<sha8>.json, byte-identical to what it
             was hashed from, named by its own sha256; a non-canonical file refused; a stale hashed file removed
  manifest   the S8 half's blocks: the commit and its timestamp, the hashes and paths, counts read from the artifacts,
             tools and inputs; and `bench build` writes it beside the artifacts it hashed
  checks     S13's checks over small hand-made dists, each failure case its done_when names: an unhashed or
             /data/latest/ reference (in an href, an island's props, a script), a stray or tampered file under
             /data/, a file under /data/latest/, a missing immutable header, a footer naming another commit, file
             counts that do not sum -- and the look-alikes that are not references (prose, an external URL)
  worker     site/worker/data-latest.ts in Node: every name the manifest gives a hashed path is a 302 to it at
             max-age=300, anything else is a 404, an unreadable manifest a 503 never cached
  site       the site built over tests/build/fixtures/minimal (one published benchmark), then S13: every page's data
             references are hashed and named, /api/ links each artifact's hashed file, dist/data/ and dist/_headers are
             what the manifest and site/public/_headers say, and the manifest names every hashed artifact with its
             hash, the commit every footer prints, and file counts that are dist's own
  verify     the build/ the verify's `bench build` just wrote: its manifest names every artifact beside it
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import artifacts, croissant, emit, freshness, ingest_health  # noqa: E402
from tools.build import manifest as M  # noqa: E402

SITE = os.path.join(ROOT, 'site')
FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
NODE = shutil.which('node')
NPX = shutil.which('npx') or shutil.which('npx.cmd')
HEAD = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def put(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data)


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


ARTIFACTS = {
    'corpus.json': {'artifact': 'corpus', 'format': 1, 'subsets': [{'id': 's'}],
                    'entities': {'benchmark': [{'id': 'b1'}, {'id': 'b2'}], 'system': [{'id': 'x'}], 'organization': [],
                                 'metric': [], 'source': []}},
    'facets.json': {'artifact': 'facets', 'format': 2, 'benchmarks': [{'claim_count': 2}, {'claim_count': 1}]},
    'enums.json': {'artifact': 'enums', 'format': 1, 'vocabularies': {}},
}


def shipped(out, docs=ARTIFACTS):
    paths = []
    for name, doc in docs.items():
        paths.append(os.path.join(out, *name.split('/')))
        put(paths[-1], emit.serialise(doc))
    return paths


@pytest.fixture
def half(tmp_path):
    """A build/ with three small artifacts and the S8 half of its manifest."""
    out = str(tmp_path / 'build')
    written = M.write(out, shipped(out))
    return SimpleNamespace(out=out, written=written, manifest=read_json(os.path.join(out, M.MANIFEST)))


# ---- hashing ------------------------------------------------------------------------------------------------------

def test_each_artifact_is_copied_under_its_own_sha8_byte_for_byte(half):
    for name in ARTIFACTS:
        with open(os.path.join(half.out, name), 'rb') as fh:
            raw = fh.read()
        digest = M.sha256(raw)
        url = '/data/%s.%s.json' % (name[:-5], digest[:8])
        assert half.manifest['artifacts'][name] == 'sha256:' + digest
        assert half.manifest['paths'][name] == url
        with open(os.path.join(half.out, *url.lstrip('/').split('/')), 'rb') as fh:
            assert fh.read() == raw
    assert sorted(os.listdir(os.path.join(half.out, 'data'))) == sorted(
        u.split('/')[-1] for u in half.manifest['paths'].values())


def test_what_is_hashed_is_the_canonical_bytes_and_anything_else_is_refused(tmp_path):
    out = str(tmp_path / 'build')
    path = os.path.join(out, 'corpus.json')
    put(path, json.dumps(ARTIFACTS['corpus.json'], indent=2).encode('utf-8'))      # valid JSON, another spelling
    with pytest.raises(M.ManifestError, match='not canonical JSON'):
        M.write(out, [path])


def test_a_nested_artifact_keeps_its_directory_and_a_bad_name_is_refused(tmp_path):
    out = str(tmp_path / 'build')
    m = read_json(M.write(out, shipped(out, {'derived/coverage.json': {'artifact': 'coverage', 'format': 1}}))[-1])
    assert m['paths']['derived/coverage.json'].startswith('/data/derived/coverage.')
    assert m['paths']['derived/coverage.json'] == M.hashed_path('derived/coverage.json',
                                                                m['artifacts']['derived/coverage.json'][len('sha256:'):])
    with pytest.raises(M.ManifestError, match='lower-case .json name'):
        M.write(out, shipped(out, {'Corpus.json': {'artifact': 'corpus'}}))


def test_a_rebuild_removes_the_hashed_files_it_no_longer_names(half):
    docs = dict(ARTIFACTS, **{'facets.json': dict(ARTIFACTS['facets.json'], benchmarks=[])})
    m = read_json(M.write(half.out, shipped(half.out, docs))[-1])
    assert m['paths']['facets.json'] != half.manifest['paths']['facets.json']
    on_disk = sorted('/data/' + n for n in os.listdir(os.path.join(half.out, 'data')))
    assert on_disk == sorted(m['paths'].values())


def test_two_writes_of_one_tree_are_byte_identical(half):
    with open(half.written[-1], 'rb') as fh:
        first = fh.read()
    M.write(half.out, shipped(half.out))
    with open(half.written[-1], 'rb') as fh:
        assert fh.read() == first


def test_out_may_not_be_the_data_tree(tmp_path):
    with pytest.raises(M.ManifestError, match='into the data tree'):
        M.write(ROOT, [])


# ---- the manifest ---------------------------------------------------------------------------------------------------

def test_the_manifest_names_the_commit_its_timestamp_and_the_build(half, monkeypatch):
    for name in ('SOURCE_DATE_EPOCH', 'UAIBI_COMMIT_SHA', 'GITHUB_SHA', 'BUILD_CLOCK', 'GITHUB_ACTIONS'):
        monkeypatch.delenv(name, raising=False)
    m = read_json(M.write(half.out, shipped(half.out))[-1])
    assert m['artifact'] == 'build-manifest' and m['index_commit'] == HEAD and m['builder'] == 'local'
    author = subprocess.run(['git', 'log', '-1', '--format=%at', HEAD], cwd=ROOT, capture_output=True, text=True).stdout
    assert m['built_at'] == dt.datetime.fromtimestamp(int(author), dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    assert m['build_clock'] is None                                       # never the wall clock (08 S6.2)
    assert m['taxonomy_version'] == artifacts.vocabulary_versions()['taxonomy']
    assert set(m['vocabularies']) == {'capability_groups', 'domain_groups'}
    assert m['formats'] == {'corpus.json': 1, 'facets.json': 2, 'enums.json': 1}
    assert m['files'] is None and m['routes'] is None                    # S13's, once the site exists
    monkeypatch.setenv('SOURCE_DATE_EPOCH', '1758412800')
    monkeypatch.setenv('UAIBI_COMMIT_SHA', 'a' * 40)
    monkeypatch.setenv('BUILD_CLOCK', '2026-11-30T03:17:00Z')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    m = read_json(M.write(half.out, shipped(half.out))[-1])
    assert (m['index_commit'], m['built_at'], m['build_clock'], m['builder']) == (
        'a' * 40, '2025-09-21T00:00:00Z', '2026-11-30T03:17:00Z', 'github-actions')
    monkeypatch.setenv('UAIBI_COMMIT_SHA', 'not-a-sha')
    with pytest.raises(M.ManifestError, match='no commit SHA'):
        M.write(half.out, shipped(half.out))


def test_counts_are_read_from_the_artifacts_themselves(half):
    assert half.manifest['counts'] == {'benchmarks': 2, 'systems': 1, 'organizations': 0, 'metrics': 0, 'sources': 0,
                                       'subsets': 1, 'claims': 3}


def test_tools_and_inputs(half):
    t = half.manifest['tools']
    assert t['python'] == '.'.join(map(str, sys.version_info[:3]))
    lock = read_json(os.path.join(SITE, 'package-lock.json'))['packages']
    assert t['pydantic'] and t['mlcroissant'] and t['astro'] == lock['node_modules/astro']['version']
    inputs = half.manifest['inputs']
    assert inputs['data_tree_sha256'] == M.tree_sha256(os.path.join(ROOT, 'data'))
    assert all(v.startswith('sha256:') and len(v) == 71 for v in inputs.values())


def test_a_tree_hash_moves_with_any_file_and_not_with_walk_order(tmp_path):
    for rel in ('b.yaml', 'a/z.yaml', 'A.yaml'):
        put(str(tmp_path / rel), b'x\n')
    before = M.tree_sha256(str(tmp_path))
    put(str(tmp_path / 'a' / 'z.yaml'), b'y\n')
    assert M.tree_sha256(str(tmp_path)) != before
    put(str(tmp_path / '__pycache__' / 'm.pyc'), b'\0')
    put(str(tmp_path / 'a' / 'z.yaml'), b'x\n')
    assert M.tree_sha256(str(tmp_path)) == before


def test_bench_build_writes_the_manifest_beside_what_it_hashed(tmp_path, monkeypatch):
    """The CLI wiring, over the minimal fixture's build so it is quick; the verify's own build is checked below."""
    from typer.testing import CliRunner

    from tools import cli
    real = artifacts.build
    monkeypatch.setattr(artifacts, 'build', lambda root: real(FIXTURE))
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path)])
    assert r.exit_code == 0, r.output
    m = read_json(str(tmp_path / M.MANIFEST))
    assert sorted(m['paths']) == sorted(emit.ARTIFACTS)
    assert m['documents']['croissant-benchmark']['files'] == len(os.listdir(tmp_path / croissant.DIR))
    for name, url in m['paths'].items():
        with open(tmp_path / name, 'rb') as a, open(os.path.join(str(tmp_path), *url.lstrip('/').split('/')), 'rb') as b:
            assert a.read() == b.read()
    assert 'content-hashed artifact(s)' in r.output


# ---- the checks -----------------------------------------------------------------------------------------------------

def footer(sha=HEAD):
    return '<footer class="site-footer" data-build-footer><p>commit <code data-commit="%s">x</code></p></footer>' % sha


def site_over(half, pages, headers=True):
    """A dist with `pages` (rel -> html) and site/public/_headers; then S13 over it."""
    dist = os.path.join(os.path.dirname(half.out), 'dist')
    for rel, text in pages.items():
        put(os.path.join(dist, *rel.split('/')), text.encode('utf-8'))
    if headers:
        shutil.copy(os.path.join(SITE, 'public', '_headers'), os.path.join(dist, '_headers'))
    return dist, M.site(dist, half.out)


def page(body, sha=HEAD):
    return '<!doctype html><html><head><title>t</title></head><body>%s%s</body></html>' % (body, footer(sha))


def test_a_site_whose_pages_reference_only_hashed_files_publishes(half):
    corpus = half.manifest['paths']['corpus.json']
    dist, (m, problems) = site_over(half, {
        'index.html': page('<a href="%s">corpus</a><p>Or curl <code>/data/latest/corpus.json</code>.</p>' % corpus),
        'api/index.html': page('<a href="..%s">rel</a><a href="https://example.org/data/latest/x.json">ext</a>'
                               '<a href="/datasets/">datasets</a>' % corpus),
    })
    assert problems == []
    assert read_json(os.path.join(dist, M.MANIFEST)) == m == read_json(os.path.join(half.out, M.MANIFEST))
    assert m['files'] == {'html': 2, 'data': 3, 'pagefind_fragments': 0, 'index_chunks': 0, 'assets': 2, 'total': 7,
                          'cap': 20000}                                   # assets: _headers and the manifest itself
    assert m['routes'] == {'/': 1, '/api/': 1}
    assert M.check(dist) == []


@pytest.mark.parametrize('body, expect', [
    ('<a href="/data/corpus.json">x</a>', '/data/corpus.json is not a hashed artifact'),
    ('<a href="/data/latest/corpus.json">x</a>', "/data/latest/corpus.json is /data/latest/, the consumers' redirect"),
    ('<a href="../data/facets.json">x</a>', '/data/facets.json is not a hashed artifact'),
    ('<a href="/data/corpus.00000000.json">x</a>', '/data/corpus.00000000.json is not a hashed artifact'),
    ('<a href="/corpus.json">x</a>', '/corpus.json names a shipped artifact unhashed'),
    ('<img srcset="/x.png 1x, /data/latest/enums.json 2x">', '/data/latest/enums.json is /data/latest/'),
    ('<astro-island props="{&quot;src&quot;:[0,&quot;/data/facets.json&quot;]}"></astro-island>',
     '/data/facets.json is not a hashed artifact'),
    ("<script type=\"module\">fetch('/data/' + name + '.json')</script>", '/data/ is not a hashed artifact'),
    ('<style>.x { background: url(/data/latest/a.json) }</style>', '/data/latest/a.json is /data/latest/'),
])
def test_an_unhashed_or_latest_data_reference_fails(half, body, expect):
    _, (_, problems) = site_over(half, {'api/index.html': page(body)})
    assert any(p.startswith('api/index.html: ') and expect in p for p in problems), problems
    assert not os.path.exists(os.path.join(os.path.dirname(half.out), 'dist', M.MANIFEST))     # nothing published


def test_a_stray_or_tampered_file_under_data_fails(half):
    dist = os.path.join(os.path.dirname(half.out), 'dist')
    put(os.path.join(dist, 'data', 'corpus.json'), b'{}\n')                      # e.g. from site/public/data/
    put(os.path.join(dist, 'data', 'latest', 'corpus.json'), b'{}\n')
    _, (_, problems) = site_over(half, {'index.html': page('')})
    assert any(p.startswith('data/corpus.json: not a hashed artifact') for p in problems), problems
    assert any(p.startswith('data/latest/: nothing may be built there') for p in problems), problems
    with open(os.path.join(half.out, M.MANIFEST), encoding='utf-8') as fh:
        m = json.load(fh)
    rel = m['paths']['enums.json'].lstrip('/')
    put(os.path.join(dist, *rel.split('/')), b'{"tampered":true}\n')
    assert any('its bytes do not hash' in p for p in M.check_data(dist, m))


def test_a_build_data_file_that_does_not_match_its_hash_fails_before_it_is_copied(half):
    rel = half.manifest['paths']['facets.json'].lstrip('/')
    put(os.path.join(half.out, *rel.split('/')), b'{}\n')
    _, (_, problems) = site_over(half, {'index.html': page('')})
    assert any(p.startswith('facets.json: build/%s does not hash' % rel) for p in problems), problems


@pytest.mark.parametrize('text, expect', [
    (None, '_headers is missing'),
    ('/data/*\n  Cache-Control: public, max-age=300\n/build-manifest.json\n  Cache-Control: public, max-age=300\n',
     "/data/* has Cache-Control 'public, max-age=300', not 'public, max-age=31536000, immutable'"),
    ('/data/*\n  Cache-Control: public, max-age=31536000, immutable\n', '/build-manifest.json has Cache-Control None'),
    ('  Cache-Control: public\n', 'is not under a URL pattern'),
])
def test_the_immutable_header_must_be_there(half, text, expect):
    dist, _ = site_over(half, {'index.html': page('')}, headers=False)
    if text is not None:
        put(os.path.join(dist, '_headers'), text.encode('utf-8'))
    assert any(expect in p for p in M.check_headers(dist)), M.check_headers(dist)


def test_the_committed_headers_are_exactly_the_three_rules():
    """The two this checks, and P4-S6-T01's /ns/* (tests/build/test_croissant_context.py)."""
    with open(os.path.join(SITE, 'public', '_headers'), encoding='utf-8') as fh:
        assert M.parse_headers(fh.read()) == {'/data/*': {'cache-control': M.IMMUTABLE},
                                              '/build-manifest.json': {'cache-control': M.SHORT_TTL},
                                              '/ns/*': {'cache-control': croissant.CONTEXT_CACHE}}


def test_a_footer_naming_another_commit_fails(half):
    _, (_, problems) = site_over(half, {'index.html': page('', sha='b' * 40)})
    assert problems == ['index.html: its footer names commit %s, the manifest %s' % ('b' * 40, HEAD)]


def test_file_counts_must_sum_and_be_recounted(half):
    dist, (m, problems) = site_over(half, {'index.html': page('')})
    assert problems == []
    assert M.check_files(dict(m, files=dict(m['files'], total=m['files']['total'] + 1)))[0].startswith('files: html, data')
    assert 'over the 2-file cap' in M.check_files(dict(m, files=dict(m['files'], cap=2)))[-1]
    put(os.path.join(dist, 'extra.css'), b'x')
    assert any(p.startswith('the manifest counts files') for p in M.check(dist))
    assert M.check_files(half.manifest) == ['the manifest has no file counts; S13 (--site) writes them']


def test_the_command_line(half, capsys):
    dist = os.path.join(os.path.dirname(half.out), 'dist')
    put(os.path.join(dist, 'index.html'), page('').encode('utf-8'))
    shutil.copy(os.path.join(SITE, 'public', '_headers'), os.path.join(dist, '_headers'))
    assert M.main(['--check', dist]) == 1 and 'run --site first' in capsys.readouterr().out
    assert M.main(['--site', dist, '--build', half.out]) == 0
    assert '0 problem(s); wrote' in capsys.readouterr().out
    assert M.main(['--check', dist]) == 0


# ---- the Worker -----------------------------------------------------------------------------------------------------

DRIVER = """
import { latest, readManifest } from %s;
const manifest = JSON.parse(process.argv[1]);
const out = {};
for (const path of JSON.parse(process.argv[2])) {
  const r = latest(new URL('https://index.example' + path), manifest);
  out[path] = r == null ? null : [r.status, r.headers.get('Location'), r.headers.get('Cache-Control')];
}
const assets = (status, body) => ({ fetch: async (req) => {
  out.fetched = new URL(req.url).pathname;
  return new Response(body, { status });
} });
const at = new URL('https://index.example/data/latest/corpus.json');
out.read = await readManifest(assets(200, JSON.stringify(manifest)), at);
out.missing = await readManifest(assets(404, 'no'), at);
out.garbage = await readManifest(assets(200, '{"artifact":"corpus"}'), at);
const none = latest(at, null);
out.none = [none.status, none.headers.get('Cache-Control')];
console.log(JSON.stringify(out));
"""


def run_worker(manifest, paths):
    module = json.dumps('file:///' + os.path.join(SITE, 'worker', 'data-latest.ts').replace('\\', '/'))
    r = subprocess.run([NODE, '--input-type=module', '-e', DRIVER % module, json.dumps(manifest), json.dumps(paths)],
                       capture_output=True, text=True, encoding='utf-8', cwd=SITE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason='node is not installed')
def test_latest_is_a_302_to_the_hashed_file_at_five_minutes(half):
    manifest = dict(half.manifest, paths=dict(half.manifest['paths'], **{
        'derived/coverage.json': '/data/derived/coverage.0123abcd.json',
        'loop.json': '/data/latest/loop.json',                            # never a redirect into latest/ itself
        'other.json': '/data/corpus.0123abcd.json'}))                     # nor to another artifact's file
    got = run_worker(manifest, ['/data/latest/corpus.json', '/data/latest/facets.json', '/data/latest/enums.json',
                                '/data/latest/derived/coverage.json', '/data/latest/loop.json', '/data/latest/other.json',
                                '/data/latest/nope.json', '/data/latest/', '/data/latest/__proto__',
                                half.manifest['paths']['corpus.json'], '/benchmarks/x/'])
    for name, url in half.manifest['paths'].items():
        assert got['/data/latest/' + name] == [302, 'https://index.example' + url, 'public, max-age=300']
    assert got['/data/latest/derived/coverage.json'][:2] == [302, 'https://index.example/data/derived/coverage.0123abcd.json']
    for path in ('/data/latest/loop.json', '/data/latest/other.json', '/data/latest/nope.json', '/data/latest/',
                 '/data/latest/__proto__'):
        assert got[path] == [404, None, 'public, max-age=300'], path
    assert got[half.manifest['paths']['corpus.json']] is None and got['/benchmarks/x/'] is None   # not its namespace
    assert got['none'] == [503, 'no-store']
    assert got['fetched'] == '/build-manifest.json'
    assert got['read'] == manifest and got['missing'] is None and got['garbage'] is None


# ---- the site, built ------------------------------------------------------------------------------------------------

needs_site = pytest.mark.skipif(not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and NPX),
                                reason='site/node_modules is not installed')
BASE = os.path.join(ROOT, 'build', 'artifact-urls-test')
TREE = os.path.join(BASE, 'root')


def astro(out, dist):
    """`astro build` over the build in `out`, with TREE as the repository the site reads raw records and the taxonomy
    from. The page inputs a full build computes from the whole repository -- freshness, ingest health, the feed -- are
    the fixture's, which `built` writes into BASE."""
    env = dict(os.environ, UAIBI_CORPUS=os.path.join(out, 'corpus.json'), REPO_ROOT=TREE, BENCH_PYTHON=sys.executable,
               INGEST_HEALTH=os.path.join(BASE, 'ingest-health.json'), FRESHNESS=os.path.join(BASE, 'freshness.json'),
               FEED_EVENTS=os.path.join(BASE, 'feed-events.json'), ASTRO_TELEMETRY_DISABLED='1')
    env.pop('UAIBI_SITE_DRAFTS', None)
    return subprocess.run([NPX, 'astro', 'build', '--outDir', dist], cwd=SITE, env=env, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=1800)


@pytest.fixture(scope='module')
def built():
    """`bench build`'s steps over the minimal fixture (one published benchmark), the site over that, then S13. TREE is
    the fixture's data/ beside the repository's taxonomy/ and CITATION.cff, because the site reads each record's own
    YAML for its cite.yaml; it sits inside the checkout, so the footer's `git rev-parse` names this commit. Everything
    is under build/ (the repository's volume and gitignored: astro cannot move files across drives,
    astro.config.mjs), and the site build depends on nothing but the fixture, so it is quick."""
    if not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and NPX):
        pytest.skip('site/node_modules is not installed')
    shutil.rmtree(BASE, ignore_errors=True)
    shutil.copytree(os.path.join(FIXTURE, 'data'), os.path.join(TREE, 'data'))
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), os.path.join(TREE, 'taxonomy'))
    shutil.copy(os.path.join(ROOT, 'CITATION.cff'), os.path.join(TREE, 'CITATION.cff'))
    out, dist = os.path.join(BASE, 'build'), os.path.join(BASE, 'dist')
    result = artifacts.build(TREE)
    assert not result.errors, result.errors
    documents, problems, _ = croissant.build(result.corpus, result.withheld)
    assert not problems, problems
    written = artifacts.write(result, out)
    croissant.write(documents, os.path.join(out, croissant.DIR))
    M.write(out, written, os.path.join(out, croissant.DIR), root=TREE)
    half = read_json(os.path.join(out, M.MANIFEST))
    as_of = dt.date(2026, 11, 18)
    health = ingest_health.build(TREE, as_of)
    put(os.path.join(BASE, 'ingest-health.json'), ingest_health.serialise(health))
    put(os.path.join(BASE, 'freshness.json'), freshness.serialise(freshness.build(TREE, as_of, health)))
    put(os.path.join(BASE, 'feed-events.json'), b'[]\n')
    r = astro(out, dist)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    manifest, problems = M.site(dist, out)
    return SimpleNamespace(out=out, dist=dist, half=half, manifest=manifest, problems=problems, corpus=result.corpus)


def html(dist, *parts):
    with open(os.path.join(dist, *parts, 'index.html'), encoding='utf-8') as fh:
        return fh.read()


@needs_site
def test_s13_passes_over_the_built_site_and_publishes_the_manifest(built):
    assert built.problems == []
    assert read_json(os.path.join(built.dist, M.MANIFEST)) == built.manifest == read_json(os.path.join(built.out, M.MANIFEST))
    assert M.check(built.dist) == []


@needs_site
def test_the_manifest_names_every_hashed_artifact_its_hash_the_commit_and_the_file_count(built):
    m = built.manifest
    assert sorted(m['paths']) == sorted(m['artifacts']) == sorted(emit.ARTIFACTS)
    for name, url in m['paths'].items():
        with open(os.path.join(built.dist, *url.lstrip('/').split('/')), 'rb') as fh:
            digest = M.sha256(fh.read())
        assert m['artifacts'][name] == 'sha256:' + digest and url == M.hashed_path(name, digest)
    assert m['index_commit'] == HEAD
    every = [os.path.join(d, n) for d, _, ns in os.walk(built.dist) for n in ns]
    assert m['files']['total'] == len(every) == sum(m['files'][k] for k in M.FILE_KEYS) and m['files']['cap'] == 20000
    assert m['files']['html'] == sum(1 for p in every if p.endswith('.html')) == sum(m['routes'].values())
    assert m['routes']['/benchmarks/'] >= 1 and m['tools']['node']
    assert {k: v for k, v in m.items() if k not in ('files', 'routes', 'tools')} == \
        {k: v for k, v in built.half.items() if k not in ('files', 'routes', 'tools')}       # S13 adds, never rewrites
    assert m['counts']['benchmarks'] == len(built.corpus['entities']['benchmark']) == 1


@needs_site
def test_every_footer_prints_the_manifests_commit(built):
    pages = [os.path.join(d, n) for d, _, ns in os.walk(built.dist) for n in ns if n.endswith('.html')]
    commits = set()
    for p in pages:
        with open(p, encoding='utf-8') as fh:
            commits |= set(re.findall(r'data-commit="([0-9a-f]{40})"', fh.read()))
    assert commits == {built.manifest['index_commit']}


@needs_site
def test_the_api_page_links_each_built_artifact_by_its_hashed_url_only(built):
    page = html(built.dist, 'api')
    for name in ('corpus.json', 'facets.json'):
        url = re.escape(built.manifest['paths'][name])
        assert re.search(r'<tr data-artifact="%s".*?yes, as <a href="%s" data-hashed[^>]*><code[^>]*>%s</code></a>'
                         % (re.escape(name), url, url), page, re.S), name
    hrefs = re.findall(r'href="(/data/[^"]*)"', page)
    assert sorted(hrefs) == sorted(built.manifest['paths'][n] for n in ('corpus.json', 'facets.json'))
    assert re.search(r'<code[^>]*>/data/latest/corpus\.json</code>', page)     # named in text, for people to type
    assert 'claims.json' not in built.manifest['paths']                        # not built, so not linked
    assert M.check_html(built.dist, built.manifest) == []


@needs_site
def test_a_reference_planted_in_a_built_pages_json_ld_fails(built):
    """The detail page inlines its croissant-benchmark document in a <script>, which the check reads like any other."""
    dist = os.path.join(BASE, 'dist-planted')
    shutil.rmtree(dist, ignore_errors=True)
    shutil.copytree(built.dist, dist)
    path = os.path.join(dist, 'benchmarks', 'alpha-bench', 'index.html')
    with open(path, encoding='utf-8') as fh:
        page = fh.read()
    assert page.count('<script type="application/ld+json" data-croissant>') == 1
    put(path, page.replace('<script type="application/ld+json" data-croissant>{',
                           '<script type="application/ld+json" data-croissant>{"contentUrl":"/data/latest/corpus.json",')
        .encode('utf-8'))
    assert M.check(dist) == ["benchmarks/alpha-bench/index.html: /data/latest/corpus.json is /data/latest/, the "
                             "consumers' redirect; the site references the hashed form only (08 S4.4)"]


@needs_site
def test_dist_data_and_headers_are_what_the_manifest_and_public_say(built):
    names = sorted(os.listdir(os.path.join(built.dist, 'data')))
    assert names == sorted(u.split('/')[-1] for u in built.manifest['paths'].values())
    with open(os.path.join(SITE, 'public', '_headers'), 'rb') as a, open(os.path.join(built.dist, '_headers'), 'rb') as b:
        assert a.read() == b.read()
    assert not os.path.exists(os.path.join(built.dist, 'data', 'latest'))


@needs_site
def test_a_site_built_against_another_builds_manifest_fails(built):
    """The site's own guard (src/lib/manifest.ts): a manifest whose hashes are not the artifacts beside it fails the
    site build, rather than linking a hashed file the pages were not rendered from. Through astro, because the module
    imports ./corpus, which only vite resolves; /api/ is the first page rendered, so the build stops early."""
    out = os.path.join(BASE, 'stale')
    shutil.copytree(built.out, out, dirs_exist_ok=True)
    stale = read_json(os.path.join(out, M.MANIFEST))
    stale['artifacts']['facets.json'] = 'sha256:' + '0' * 64
    put(os.path.join(out, M.MANIFEST), emit.serialise(stale))
    r = astro(out, os.path.join(BASE, 'dist-stale'))
    log = r.stdout + r.stderr
    assert r.returncode != 0 and 'records facets.json as sha256:000' in log and "the manifest is not this build's" in log


# ---- the verify's build -------------------------------------------------------------------------------------------

def test_the_verifys_bench_build_wrote_a_manifest_naming_every_artifact_beside_it():
    out = os.path.join(ROOT, 'build')
    if not os.path.exists(os.path.join(out, M.MANIFEST)):
        pytest.skip('no build/build-manifest.json: run `uv run bench build --out build/` first, as the verify does')
    m = read_json(os.path.join(out, M.MANIFEST))
    assert sorted(m['paths']) == sorted(emit.ARTIFACTS)
    for name, url in m['paths'].items():
        with open(os.path.join(out, name), 'rb') as a, open(os.path.join(out, *url.lstrip('/').split('/')), 'rb') as b:
            raw = a.read()
            assert b.read() == raw and m['artifacts'][name] == 'sha256:' + M.sha256(raw)
    assert M.COMMIT.match(m['index_commit'])
