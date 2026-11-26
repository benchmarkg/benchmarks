"""The --data-only and --routes-from-diff build modes (P2-S1-T04; tools/build/modes.py, scripts/routes_from_diff.py,
site/src/lib/bench-routes.ts; 08 S3.4, 05 S3).

The verify: `BENCH_ROUTES=/benchmarks/swe-bench/ bench build --data-only && pytest tests/build/test_routes_from_diff.py`.
Done when: "A preview build renders only the diffed routes plus the fixed narrative routes, main still renders
everything, and --data-only skips S9, S10 and SQLite."

  map        modes.plan over a small corpus and tree: a published record's page, nothing for a draft, a stub or a
             deleted record; a source to the pages citing it; a claim to its benchmark's and system's pages, a
             conditions record to its claims'; nothing for a record no page renders, a test, a document or the plan;
             everything (`*`) for a taxonomy term, a template, the schema, a build tool, CITATION.cff and a path the
             map cannot place
  git        scripts/routes_from_diff.py over a throwaway repository: `git diff --name-only base...head` mapped, a
             renamed file's two paths, a deleted claim read at the merge base, `*` for a taxonomy change, LF output
  filter     site/src/lib/bench-routes.ts in Node, against modes.py's parse and main rule on every case: unset, `*`,
             a list (a route brings what is beneath it; a file route is that file), an empty list, a build of main
             (push, schedule, dispatch) and build-preview.yml's workflow_run, which filters though its ref is main
  pages      every page with a getStaticPaths() passes its paths through onlyRoutes(), and every other page has none
  data-only  `bench build --data-only` writes the three artifacts, the hashed copies and the manifest, runs no S9 (no
             croissant-benchmark validation or documents, no index.sqlite) and no S10 (no tokens, no site taxonomy),
             removes a full build's S9 outputs from --out, and says what BENCH_ROUTES will render
  site       the site over a data-only build of the minimal fixture three times: BENCH_ROUTES unset renders every
             route; BENCH_ROUTES=/benchmarks/alpha-bench/ renders that page and what is beneath it, the fixed
             narrative routes and nothing else; and the same BENCH_ROUTES on a push to main renders every route.
             The manifest's S13 checks pass over the preview
  verify     the build/ the verify's `bench build --data-only` just wrote has no S9 output in it
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import artifacts, croissant, emit, freshness, ingest_health  # noqa: E402
from tools.build import claims as CL  # noqa: E402
from tools.build import manifest as M  # noqa: E402
from tools.build import modes  # noqa: E402

SITE = os.path.join(ROOT, 'site')
SHIPPED = sorted(emit.ARTIFACTS + CL.ARTIFACTS)      # S8's files, the claims stage's included (P3-S10-T03)
PAGES = os.path.join(SITE, 'src', 'pages')
FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
SCRIPT = os.path.join(ROOT, 'scripts', 'routes_from_diff.py')
NODE = shutil.which('node')
NPX = shutil.which('npx') or shutil.which('npx.cmd')
GITHUB = ('BENCH_ROUTES', 'GITHUB_REF', 'GITHUB_EVENT_NAME')


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(text if isinstance(text, bytes) else text.encode('utf-8'))


# ---- the map --------------------------------------------------------------------------------------------------------

CORPUS = {'entities': {
    'benchmark': [{'id': 'alpha-bench', 'curation': {'sources': ['src-a']}}],
    'system': [{'id': 'sys-a', 'sources': ['src-b']}],
    'organization': [{'id': 'org-a', 'sources': ['src-a']}],
    'metric': [{'id': 'accuracy', 'sources': []}],
    'source': [{'id': 'src-a'}, {'id': 'src-b'}],
}, 'subsets': []}
CLAIM = 'data/claims/alpha-bench/claim-000000000001.yaml'


@pytest.fixture
def tree(tmp_path):
    put(str(tmp_path / CLAIM), 'id: claim-000000000001\nbenchmark: alpha-bench@1.0\nsystem: sys-a@2026-01\n'
                               'eval_conditions: cond-000000000001\n')
    put(str(tmp_path / 'data/claims/other/claim-000000000002.yaml'),
        'id: claim-000000000002\nbenchmark: unpublished-bench\nsystem: sys-a\neval_conditions: cond-000000000009\n')
    return modes.Tree(str(tmp_path))


def routes(changed, tree):
    got = modes.plan(changed, CORPUS, tree)
    return '*' if got.everything else sorted(got.routes)


@pytest.mark.parametrize('path, expect', [
    ('data/benchmarks/code/alpha-bench.yaml', ['/benchmarks/alpha-bench/']),
    ('data/systems/sys-a.yaml', ['/systems/sys-a/']),
    ('data/organizations/org-a.yaml', ['/orgs/org-a/']),
    ('data/metrics/accuracy.yaml', ['/metrics/accuracy/']),
    ('data/benchmarks/code/beta-bench.yaml', []),                 # a draft, or deleted: no page this commit publishes
    ('data/benchmarks/_stubs/stub-bench.yaml', []),               # a stub is never published
    ('data/sources/2026/src-a.yaml', ['/benchmarks/alpha-bench/', '/orgs/org-a/']),   # the pages citing it
    ('data/sources/2026/src-b.yaml', ['/systems/sys-a/']),
    ('data/sources/2026/src-uncited.yaml', []),
    (CLAIM, ['/benchmarks/alpha-bench/', '/systems/sys-a/']),     # the pages counting it
    ('data/claims/other/claim-000000000002.yaml', ['/systems/sys-a/']),
    ('data/conditions/cond-000000000001.yaml', ['/benchmarks/alpha-bench/', '/systems/sys-a/']),
    ('data/conditions/cond-00000000000f.yaml', []),
    ('data/leaderboards/lb-x.yaml', []), ('data/disputes/dispute-x.yaml', []), ('data/surveys/x.yaml', []),
    ('tests/build/test_x.py', []), ('site/test/x.test.mjs', []), ('docs/methodology.md', []), ('_plan/08-x.md', []),
    ('README.md', []), ('taxonomy/_failures/x.yaml', []), ('scripts/check_x.py', []),
    ('taxonomy/capabilities.yaml', '*'), ('taxonomy/VERSION', '*'), ('schema/benchmark.py', '*'),
    ('site/src/views/BenchmarkDetail.astro', '*'), ('site/src/lib/bench-routes.ts', '*'), ('design/tokens.yaml', '*'),
    ('tools/build/emit.py', '*'), ('CITATION.cff', '*'), ('uv.lock', '*'), ('config/dedup.yaml', '*'),
    ('somewhere/new.txt', '*'),
])
def test_each_changed_path_maps_to_its_routes(tree, path, expect):
    assert routes([path], tree) == expect


def test_a_diff_is_the_union_and_says_why_per_path(tree):
    got = modes.plan(['data/sources/2026/src-b.yaml', 'tests/x.py', 'data/metrics/accuracy.yaml'], CORPUS, tree)
    assert got.lines() == ['/metrics/accuracy/', '/systems/sys-a/'] and not got.everything
    assert [p for p, _ in got.why] == ['data/metrics/accuracy.yaml', 'data/sources/2026/src-b.yaml', 'tests/x.py']
    assert dict(got.why)['tests/x.py'] == 'a test'
    assert modes.plan(['taxonomy/capabilities.yaml', 'tests/x.py'], CORPUS, tree).lines() == ['*']
    assert modes.plan([], CORPUS, tree).lines() == []          # the fixed narrative routes alone


# ---- the script, over git -------------------------------------------------------------------------------------------

def git(repo, *args):
    return subprocess.run(['git', '-c', 'user.name=routes-test', '-c', 'user.email=', '-c', 'commit.gpgsign=false',
                           '-c', 'core.autocrlf=false', *args], cwd=repo, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    """A repository holding the minimal fixture's data/ and a claim on main, and the corpus the fixture publishes (the
    claim is a bare one, which a build would refuse; the map reads only its benchmark and system)."""
    r = str(tmp_path / 'repo')
    shutil.copytree(os.path.join(FIXTURE, 'data'), os.path.join(r, 'data'))
    put(os.path.join(r, 'data', 'claims', 'alpha-bench', 'claim-000000000001.yaml'),
        'id: claim-000000000001\nbenchmark: alpha-bench\nsystem: sys-a\n')
    os.makedirs(os.path.join(r, 'taxonomy'))
    put(os.path.join(r, 'taxonomy', 'VERSION'), '0.0.0\n')
    git(r, 'init', '-q', '-b', 'main')
    git(r, 'add', '-A')
    git(r, 'commit', '-q', '-m', 'main')
    git(r, 'checkout', '-q', '-b', 'pr')
    corpus = artifacts.build(FIXTURE).corpus
    assert corpus['entities']['benchmark']
    put(str(tmp_path / 'corpus.json'), json.dumps(corpus))
    return SimpleNamespace(root=r, corpus=str(tmp_path / 'corpus.json'))


def run_script(repo, *args):
    return subprocess.run([sys.executable, SCRIPT, '--root', repo.root, '--base', 'main', '--corpus', repo.corpus, *args],
                          capture_output=True, cwd=ROOT)


def test_the_script_maps_a_diff_against_its_base(repo):
    path = os.path.join(repo.root, 'data', 'benchmarks', 'code', 'alpha-bench.yaml')
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    put(path, text.replace('A published benchmark used in build tests.', 'An edited tagline.'))
    put(os.path.join(repo.root, 'tests', 'test_new.py'), 'pass\n')
    git(repo.root, 'add', '-A')
    git(repo.root, 'commit', '-q', '-m', 'edit')
    r = run_script(repo, '--explain')
    assert r.returncode == 0, r.stderr
    assert r.stdout == b'/benchmarks/alpha-bench/\n'                  # LF on every platform
    assert b'tests/test_new.py  ->  a test' in r.stderr and b'1 route(s) and the fixed narrative routes' in r.stderr


def test_a_rename_maps_both_paths_and_a_deleted_claim_is_read_at_the_merge_base(repo):
    git(repo.root, 'mv', 'data/metrics/accuracy.yaml', 'data/metrics/accuracy-moved.yaml')
    git(repo.root, 'rm', '-q', 'data/claims/alpha-bench/claim-000000000001.yaml')
    git(repo.root, 'commit', '-q', '-m', 'move and delete')
    r = run_script(repo, '--explain', '--out', os.path.join(repo.root, '..', 'routes.txt'))
    assert r.returncode == 0, r.stderr
    # the old metric path is the published page (the corpus is the head's, built before the move); the claim, gone at
    # head, still names its benchmark at the merge base
    assert r.stdout.decode().splitlines() == ['/benchmarks/alpha-bench/', '/metrics/accuracy/']
    assert b'data/metrics/accuracy-moved.yaml  ->  no page' in r.stderr
    with open(os.path.join(repo.root, '..', 'routes.txt'), 'rb') as fh:
        assert fh.read() == r.stdout


def test_a_taxonomy_change_renders_everything(repo):
    put(os.path.join(repo.root, 'taxonomy', 'VERSION'), '0.0.1\n')
    git(repo.root, 'commit', '-q', '-am', 'bump')
    r = run_script(repo)
    assert r.returncode == 0 and r.stdout == b'*\n'


def test_no_corpus_or_a_bad_ref_exits_2(repo):
    r = subprocess.run([sys.executable, SCRIPT, '--root', repo.root, '--base', 'main', '--corpus', repo.corpus + '.no'],
                       capture_output=True, text=True)
    assert r.returncode == 2 and 'bench build --data-only' in r.stderr
    r = run_script(repo, '--head', 'no-such-ref')
    assert r.returncode == 2 and b'failed' in r.stderr


# ---- the filter, in Node --------------------------------------------------------------------------------------------

DRIVER = """
import { benchRoutes, mainBuild, rendered, normalise, NARRATIVE, onlyRoutes } from %s;
const [cases, probes] = [JSON.parse(process.argv[1]), JSON.parse(process.argv[2])];
const out = { narrative: NARRATIVE, cases: cases.map((env) => {
  const listed = benchRoutes(env);
  return { listed, main: mainBuild(env), rendered: probes.map((p) => rendered(p, listed)),
           kept: onlyRoutes(probes.map((p) => ({ params: { p } })), (x) => x.params.p, env).map((x) => x.params.p) };
}), normalised: probes.map(normalise) };
console.log(JSON.stringify(out));
"""
CASES = [
    {},
    {'BENCH_ROUTES': '*'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/\n*\n'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/'},
    {'BENCH_ROUTES': 'benchmarks/alpha-bench\r\n\r\n/orgs/org-a/\n/feed.xml\n/benchmarks/alpha-bench/cite.bib\n'},
    {'BENCH_ROUTES': ''},
    {'BENCH_ROUTES': '\n  \n'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'push'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'schedule'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'workflow_dispatch'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'workflow_run'},
    {'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/pull/7/merge', 'GITHUB_EVENT_NAME': 'pull_request'},
    {'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'push'},
]
PROBES = ['/benchmarks/alpha-bench/', '/benchmarks/alpha-bench/cite.bib', '/benchmarks/alpha-bench/cite.ris',
          '/benchmarks/alpha-bench/v/1.0/', '/benchmarks/alpha-bench-2/', '/benchmarks/beta-bench/', '/orgs/org-a/',
          '/systems/sys-a/', '/taxonomy/capability/planning/', '/browse/domain/code/', '/docs/methodology/',
          '/feed/corrections.xml', '/feed.xml', 'benchmarks/alpha-bench']


@pytest.fixture(scope='module')
def node():
    if NODE is None:
        pytest.skip('node is not installed')
    module = json.dumps('file:///' + os.path.join(SITE, 'src', 'lib', 'bench-routes.ts').replace('\\', '/'))
    r = subprocess.run([NODE, '--input-type=module', '-e', DRIVER % module, json.dumps(CASES), json.dumps(PROBES)],
                       capture_output=True, text=True, encoding='utf-8', cwd=SITE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_the_site_and_the_build_read_bench_routes_alike(node):
    assert node['narrative'] == ['/docs/', '/feed/']
    assert node['normalised'] == [modes.normalise(p) for p in PROBES]
    for env, got in zip(CASES, node['cases']):
        assert got['listed'] == modes.bench_routes(env), env
        assert got['main'] == modes.main_build(env), env
        listed = modes.bench_routes(env)
        python = [listed is None or modes.normalise(p).startswith(('/docs/', '/feed/')) or modes.covers(listed, p)
                  for p in PROBES]
        assert got['rendered'] == python, env
        assert got['kept'] == [p for p, keep in zip(PROBES, python) if keep], env


def test_what_each_case_renders(node):
    by = {json.dumps(env, sort_keys=True): dict(zip(PROBES, got['rendered'])) for env, got in zip(CASES, node['cases'])}

    def case(**env):
        return by[json.dumps(env, sort_keys=True)]
    for everything in (case(), case(BENCH_ROUTES='*'), case(BENCH_ROUTES='/benchmarks/alpha-bench/\n*\n'),
                       case(BENCH_ROUTES='/benchmarks/alpha-bench/', GITHUB_REF='refs/heads/main', GITHUB_EVENT_NAME='push'),
                       case(BENCH_ROUTES='/benchmarks/alpha-bench/', GITHUB_REF='refs/heads/main',
                            GITHUB_EVENT_NAME='schedule')):
        assert all(everything.values())
    one = case(BENCH_ROUTES='/benchmarks/alpha-bench/')
    assert sorted(p for p, kept in one.items() if kept) == sorted([
        '/benchmarks/alpha-bench/', '/benchmarks/alpha-bench/cite.bib', '/benchmarks/alpha-bench/cite.ris',
        '/benchmarks/alpha-bench/v/1.0/', '/docs/methodology/', '/feed/corrections.xml', 'benchmarks/alpha-bench'])
    assert one == case(BENCH_ROUTES='/benchmarks/alpha-bench/', GITHUB_REF='refs/heads/main',
                       GITHUB_EVENT_NAME='workflow_run')        # build-preview.yml: its ref is main, and it filters
    files = case(BENCH_ROUTES='benchmarks/alpha-bench\r\n\r\n/orgs/org-a/\n/feed.xml\n/benchmarks/alpha-bench/cite.bib\n')
    assert files['/orgs/org-a/'] and files['/benchmarks/alpha-bench/v/1.0/'] and not files['/systems/sys-a/']
    none = case(BENCH_ROUTES='')
    assert [p for p, kept in none.items() if kept] == ['/docs/methodology/', '/feed/corrections.xml']
    assert none == case(BENCH_ROUTES='\n  \n')


# ---- every page -----------------------------------------------------------------------------------------------------

def page_files():
    out = []
    for folder, _, names in os.walk(PAGES):
        out += [os.path.relpath(os.path.join(folder, n), PAGES).replace(os.sep, '/') for n in names]
    return sorted(out)


def test_every_getstaticpaths_filters_through_onlyroutes():
    dynamic = [p for p in page_files() if '[' in p]
    assert len(dynamic) >= 10 and 'browse/[facet]/[...term].astro' in dynamic
    for rel in page_files():
        with open(os.path.join(PAGES, *rel.split('/')), encoding='utf-8') as fh:
            text = fh.read()
        if '[' not in rel:                               # a fixed route: no parameter, so no getStaticPaths()
            assert 'getStaticPaths' not in text, rel
            continue
        assert 'getStaticPaths' in text, rel
        assert "import { onlyRoutes } from '%slib/bench-routes';" % ('../' * (rel.count('/') + 1)) in text, rel
        body = text.split('getStaticPaths', 1)[1]
        assert 'return onlyRoutes(' in body, rel
    assert 'ns/croissant-benchmark/v1/index.astro' in page_files()   # the namespace page is a fixed route


# ---- bench build --data-only ----------------------------------------------------------------------------------------

@pytest.fixture
def cli(monkeypatch):
    """`bench build` over the minimal fixture, with the S9 and S10 stages recorded rather than run where they would
    write committed files."""
    from typer.testing import CliRunner

    from tools import cli as bench
    from tools.build import site_taxonomy, sqlite, tokens
    for name in GITHUB:
        monkeypatch.delenv(name, raising=False)
    real = artifacts.build
    monkeypatch.setattr(artifacts, 'build', lambda root: real(FIXTURE))
    calls = []
    monkeypatch.setattr(tokens, 'write', lambda root: calls.append('tokens') or [])
    monkeypatch.setattr(site_taxonomy, 'write', lambda root: calls.append('site_taxonomy') or [])
    for mod, name in ((croissant, 'build'), (croissant, 'write'), (sqlite, 'write')):
        original = getattr(mod, name)
        monkeypatch.setattr(mod, name, lambda *a, _o=original, _n=name, _m=mod.__name__, **k:
                            calls.append('%s.%s' % (_m.rsplit('.', 1)[-1], _n)) or _o(*a, **k))

    def run(*args, env=None):
        calls.clear()
        r = CliRunner().invoke(bench.app, ['build', *args], env=env)
        assert r.exit_code == 0, r.output
        return SimpleNamespace(output=r.output, calls=list(calls))
    return run


def test_data_only_skips_s9_s10_and_sqlite_and_clears_a_full_builds(cli, tmp_path):
    out = str(tmp_path / 'build')
    full = cli('--out', out)
    assert full.calls == ['croissant.build', 'croissant.write', 'sqlite.write', 'tokens', 'site_taxonomy']
    assert os.path.isdir(os.path.join(out, croissant.DIR)) and os.path.exists(os.path.join(out, 'index.sqlite'))
    preview = cli('--out', out, '--data-only')
    assert preview.calls == []
    assert 'removed %s' % os.path.join(out, croissant.DIR) in preview.output
    assert 'removed %s' % os.path.join(out, 'index.sqlite') in preview.output
    assert not os.path.exists(os.path.join(out, croissant.DIR)) and not os.path.exists(os.path.join(out, 'index.sqlite'))
    assert sorted(os.listdir(out)) == sorted(list(emit.ARTIFACTS) + [CL.CLAIMS, CL.INGESTED, 'derived'] +
                                             ['build-manifest.json', 'data', 'dormancy.json'])
    m = json.loads(open(os.path.join(out, M.MANIFEST), encoding='utf-8').read())
    assert sorted(m['paths']) == SHIPPED and m['documents'] == {}
    assert '--data-only: S9 (croissant-benchmark/, index.sqlite) and S10' in preview.output
    again = cli('--out', out, '--data-only')
    assert 'removed' not in again.output                             # nothing left to clear


def test_data_only_keeps_what_a_preview_needs(cli, tmp_path):
    out = str(tmp_path / 'build')
    r = cli('--out', out, '--data-only', '--atlas')
    for name in emit.ARTIFACTS + ('dormancy.json', 'atlas.json', M.MANIFEST):
        assert os.path.exists(os.path.join(out, name)), name
    with open(os.path.join(out, 'corpus.json'), 'rb') as a:
        full = str(tmp_path / 'full')
        cli('--out', full)
        with open(os.path.join(full, 'corpus.json'), 'rb') as b:
            assert a.read() == b.read()                              # S1-S8 are the same build
    assert 'BENCH_ROUTES' not in r.output


def test_bench_build_says_what_bench_routes_will_render(cli, tmp_path):
    out = str(tmp_path / 'build')
    r = cli('--out', out, '--data-only', env={'BENCH_ROUTES': '/benchmarks/alpha-bench/\n/benchmarks/swe-bench/\n'})
    assert ('BENCH_ROUTES: the site build renders 2 listed route(s) (/benchmarks/alpha-bench/, /benchmarks/swe-bench/) '
            'and the fixed narrative routes (site/src/lib/bench-routes.ts); no record this build publishes is at '
            '/benchmarks/swe-bench/') in r.output
    r = cli('--out', out, '--data-only', env={'BENCH_ROUTES': '/benchmarks/alpha-bench/', 'GITHUB_REF': 'refs/heads/main',
                                              'GITHUB_EVENT_NAME': 'push'})
    assert 'BENCH_ROUTES: ignored, because this is a build of main, which renders every route' in r.output
    assert 'BENCH_ROUTES: every route' in cli('--out', out, '--data-only', env={'BENCH_ROUTES': '*'}).output


# ---- the site, built ------------------------------------------------------------------------------------------------

BASE = os.path.join(ROOT, 'build', 'routes-from-diff-test')
TREE = os.path.join(BASE, 'root')
FAMILIES = ('benchmarks/', 'systems/', 'orgs/', 'metrics/', 'taxonomy/', 'browse/')   # the pages with a parameter
LISTED = '/benchmarks/alpha-bench/'


def dist_files(dist):
    out = set()
    for folder, _, names in os.walk(dist):
        out |= {os.path.relpath(os.path.join(folder, n), dist).replace(os.sep, '/') for n in names}
    return out


@pytest.fixture(scope='module')
def sites():
    """`bench build --data-only`'s steps over the minimal fixture, then the site three ways. Under build/, as
    tests/build/test_artifact_urls.py builds it."""
    if not (os.path.isdir(os.path.join(SITE, 'node_modules', 'astro')) and NPX):
        pytest.skip('site/node_modules is not installed')
    shutil.rmtree(BASE, ignore_errors=True)
    shutil.copytree(os.path.join(FIXTURE, 'data'), os.path.join(TREE, 'data'))
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), os.path.join(TREE, 'taxonomy'))
    shutil.copy(os.path.join(ROOT, 'CITATION.cff'), os.path.join(TREE, 'CITATION.cff'))
    out = os.path.join(BASE, 'build')
    result = artifacts.build(TREE)
    assert not result.errors, result.errors
    M.write(out, artifacts.write(result, out), None, root=TREE)
    as_of = dt.date(2026, 11, 18)
    health = ingest_health.build(TREE, as_of)
    put(os.path.join(BASE, 'ingest-health.json'), ingest_health.serialise(health))
    put(os.path.join(BASE, 'freshness.json'), freshness.serialise(freshness.build(TREE, as_of, health)))
    put(os.path.join(BASE, 'feed-events.json'), b'[]\n')
    base_env = {k: v for k, v in os.environ.items() if k not in GITHUB + ('UAIBI_SITE_DRAFTS',)}
    base_env.update(UAIBI_CORPUS=os.path.join(out, 'corpus.json'), REPO_ROOT=TREE, BENCH_PYTHON=sys.executable,
                    INGEST_HEALTH=os.path.join(BASE, 'ingest-health.json'), FRESHNESS=os.path.join(BASE, 'freshness.json'),
                    FEED_EVENTS=os.path.join(BASE, 'feed-events.json'), ASTRO_TELEMETRY_DISABLED='1')
    built = {}
    for name, env in (('all', {}), ('preview', {'BENCH_ROUTES': LISTED + '\n'}),
                      ('main', {'BENCH_ROUTES': LISTED + '\n', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_NAME': 'push'})):
        dist = os.path.join(BASE, 'dist-' + name)
        r = subprocess.run([NPX, 'astro', 'build', '--outDir', dist], cwd=SITE, env=dict(base_env, **env),
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
        built[name] = SimpleNamespace(dist=dist, files=dist_files(dist), log=r.stdout + r.stderr)
    # the copied taxonomy/ names every display-only group id, and CI 9h (scripts/check_display_only_vocab.py) scans
    # build/; nothing reads the tree once the sites are built
    shutil.rmtree(TREE, ignore_errors=True)
    return SimpleNamespace(out=out, **built)


@pytest.mark.skipif(NPX is None, reason='npx is not installed')
def test_unset_renders_every_route_family(sites):
    files = sites.all.files
    for page in ('benchmarks/alpha-bench/index.html', 'benchmarks/alpha-bench/cite.bib', 'orgs/org-alpha-lab/index.html',
                 'metrics/accuracy/index.html', 'docs/methodology/index.html', 'feed/corrections.xml', 'index.html',
                 'api/index.html', 'ns/croissant-benchmark/v1/index.html'):
        assert page in files, page
    assert sum(f.startswith('taxonomy/') for f in files) > 100 and sum(f.startswith('browse/') for f in files) > 100
    assert '[bench-routes]' not in sites.all.log


@pytest.mark.skipif(NPX is None, reason='npx is not installed')
def test_a_preview_renders_the_listed_route_and_the_fixed_narrative_routes_only(sites):
    # dist/pagefind/ is the search index over what each build rendered (P2-S4-T06), its files named by their content,
    # so a preview's differs from a full build's by construction; tests/build/test_pagefind.py checks the index itself
    every, preview = ({f for f in s.files if not f.startswith('pagefind/')} for s in (sites.all, sites.preview))
    fixed = {'benchmarks/index.html'}         # /benchmarks/, the browse view (P2-S4-T04): a fixed route under a family
    expect = {f for f in every if not f.startswith(FAMILIES) or f in fixed or f.startswith(LISTED.lstrip('/'))}
    assert preview == expect
    assert 'benchmarks/alpha-bench/index.html' in preview and 'benchmarks/alpha-bench/cite.yaml' in preview
    assert not any(f.startswith(('orgs/', 'metrics/', 'taxonomy/', 'browse/')) for f in preview)
    assert {'docs/methodology/index.html', 'feed/corrections.xml', 'index.html', 'api/index.html'} <= preview
    assert len(preview) < len(every) / 4
    assert '[bench-routes] BENCH_ROUTES: 1 listed route(s) and the fixed narrative routes' in sites.preview.log
    manifest, problems = M.site(sites.preview.dist, sites.out)
    assert problems == [] and manifest['routes'].get('/taxonomy/') is None      # a family the preview did not render


@pytest.mark.skipif(NPX is None, reason='npx is not installed')
def test_main_renders_everything_whatever_bench_routes_says(sites):
    assert sites.main.files == sites.all.files
    assert 'every route renders (a build of main)' in sites.main.log


# ---- the verify's build ---------------------------------------------------------------------------------------------

def test_the_verifys_data_only_build_left_no_s9_output():
    out = os.path.join(ROOT, 'build')
    if not os.path.exists(os.path.join(out, M.MANIFEST)):
        pytest.skip('no build/build-manifest.json: run `uv run bench build --data-only` first, as the verify does')
    m = json.loads(open(os.path.join(out, M.MANIFEST), encoding='utf-8').read())
    if m['documents']:
        pytest.skip('the last bench build into build/ was a full one (it wrote croissant-benchmark/)')
    assert not os.path.exists(os.path.join(out, croissant.DIR)) and not os.path.exists(os.path.join(out, 'index.sqlite'))
    ingested = {n for n in m['paths'] if n.startswith(CL.INGESTED + '/')}     # one per benchmark with ingested claims
    assert sorted(set(m['paths']) - ingested) == SHIPPED
