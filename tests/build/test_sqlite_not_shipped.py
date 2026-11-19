"""index.sqlite, built at build time and never shipped (P2-S1-T06; tools/build/sqlite.py; 08 S4.2, 14 Phase 2).

The verify: `bench build --out build/ && pytest tests/build/test_sqlite_not_shipped.py`. Done when: "build/index.sqlite
exists and no file under dist/ references it."

  tables     over the minimal fixture's artifacts (one published benchmark with a three-level subset tree): one row
             per published record keyed by id, `record` its canonical JSON; scalar fields as columns, a nested model's
             flattened; lists as child tables keyed back to their record and their parent item; facets.json's
             arrays joining enums.json's terms; the materialised subsets; the references; and _meta and _tables
             describing the file. The column set is the models': a curated extra adds no column
  drafts     the same over every record in data/, drafts included, built in memory and never written: each record
             round-trips, and each list table holds exactly the items its source path walks to in corpus.json
  file       two writes are byte-identical; a path under site/ and a draft corpus are refused
  build      `bench build` writes index.sqlite beside the artifacts it is built from, and neither under data/ nor in
             the manifest
  dist       the check over small hand-made dists: a SQLite file (by name or by header) and each kind of reference
             fail -- a URL attribute, a relative path, a fetch in a script, an island's props, CSS url(), a JS
             module, a _redirects line -- and the look-alikes do not: /api/'s prose, an attribute that is prose, an
             external URL to a release asset, a JSON key, another file's name
  site       the site built over the fixture with index.sqlite beside its corpus: no file under dist/ is or names it,
             /api/ still says what the release archive holds, and the manifest's S13 checks still pass
  verify     the build/ the verify's `bench build` just wrote: index.sqlite is there, built from build/corpus.json
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import artifacts, croissant, emit, freshness, ingest_health  # noqa: E402
from tools.build import manifest as M  # noqa: E402
from tools.build import sqlite as S  # noqa: E402

SITE = os.path.join(ROOT, 'site')
FIXTURE = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
NPX = shutil.which('npx') or shutil.which('npx.cmd')


def put(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data)


def docs(result):
    return {'corpus.json': result.corpus, 'facets.json': result.facets, 'enums.json': result.enums}


def rows(con, sql, *args):
    return con.execute(sql, args).fetchall()


@pytest.fixture(scope='module')
def minimal():
    result = artifacts.build(FIXTURE)
    assert not result.errors, result.errors
    return SimpleNamespace(result=result, con=S.build(docs(result)))


# ---- the tables -----------------------------------------------------------------------------------------------------

def test_one_row_per_published_record_keyed_by_id_with_its_canonical_json(minimal):
    for kind in S.KINDS:
        records = minimal.result.corpus['entities'][kind]
        got = rows(minimal.con, 'SELECT id, record FROM %s ORDER BY rowid' % kind)
        assert [i for i, _ in got] == [r['id'] for r in records], kind
        assert [json.loads(r) for _, r in got] == records, kind
    assert rows(minimal.con, 'SELECT id FROM benchmark') == [('alpha-bench',)]       # the drafts are left out


def test_scalar_fields_are_columns_and_a_nested_models_are_flattened_in(minimal):
    cols = [r[1] for r in rows(minimal.con, 'PRAGMA table_info(benchmark)')]
    assert cols[0] == 'id' and cols[-1] == 'record'
    assert {'name', 'tagline', 'released', 'lifecycle', 'headline_metric', 'domain__primary', 'data__access',
            'curation__verification_status'} <= set(cols)
    assert 'aliases' not in cols and 'capability_basis' not in cols      # a list is a table; a map stays in `record`
    got = rows(minimal.con, 'SELECT name, released, domain__primary, data__access, curation__verification_status '
                            'FROM benchmark')
    assert got == [('Alpha Bench', '2025-03-01', 'code/repository-scale-se', 'fully-open', 'curator-reviewed')]
    types = {r[1]: r[2] for r in rows(minimal.con, 'PRAGMA table_info(metric)')}
    assert types['id'] == 'TEXT' and types['range__min'] in ('REAL', '') and types['record'] == 'TEXT'


def test_lists_are_tables_keyed_to_their_record_and_their_parent_item(minimal):
    assert rows(minimal.con, 'SELECT _id, _parent, _position, value FROM benchmark__aliases') == \
        [('alpha-bench', None, 0, 'AlphaBench')]
    assert rows(minimal.con, 'SELECT value FROM benchmark__domain__secondary') == [('reasoning-general/logical-deduction',)]
    assert rows(minimal.con, 'SELECT _position, value FROM benchmark__capability ORDER BY _position') == \
        [(0, 'deductive-reasoning'), (1, 'knowledge-recall')]
    subsets = rows(minimal.con, 'SELECT _row, id, parent, domain_override__primary FROM benchmark__subsets '
                                'ORDER BY _position')
    assert [s[1:] for s in subsets] == [('alpha-bench#chem', None, 'chemistry-materials/reaction-prediction'),
                                        ('alpha-bench#chem-hard', 'alpha-bench#chem', None), ('alpha-bench#plain', None, None)]
    hard = subsets[1][0]                         # a list inside a list item is keyed to that item's _row
    assert rows(minimal.con, 'SELECT _id, _parent, value FROM benchmark__subsets__capability_override') == \
        [('alpha-bench', hard, 'deductive-reasoning')]
    assert rows(minimal.con, 'SELECT system, source FROM benchmark__learned_entrant_evidence') == \
        [('Some Model', 'src-alpha-paper')]


def test_the_column_set_is_the_models_not_the_datas(minimal):
    """A curated extra (Benchmark allows them) changes `record` and nothing else; the shape moves only with schema/."""
    corpus = json.loads(json.dumps(minimal.result.corpus))
    corpus['entities']['benchmark'][0]['aliases_note'] = 'A curated note beyond the model.'
    con = S.build(dict(docs(minimal.result), **{'corpus.json': corpus}))
    shape = 'SELECT name, sql FROM sqlite_master ORDER BY name'
    assert rows(con, shape) == rows(minimal.con, shape)
    assert json.loads(rows(con, 'SELECT record FROM benchmark')[0][0])['aliases_note'].startswith('A curated note')


def test_facet_values_join_their_terms_and_subsets_and_references_are_rows(minimal):
    r = minimal.result
    facet = r.facets['benchmarks'][0]
    assert rows(minimal.con, 'SELECT id, domain, subdomain, year, lifecycle, claim_count FROM facet_row') == \
        [('alpha-bench', facet['domain'], facet['subdomain'], facet['year'], facet['lifecycle'], facet['claim_count'])]
    assert sorted(rows(minimal.con, 'SELECT facet, key FROM facet_value')) == \
        sorted((f, k) for f, keys in facet['facets'].items() for k in keys)
    assert rows(minimal.con, 'SELECT count(*) FROM facet_value v WHERE NOT EXISTS (SELECT 1 FROM flat_facet_vocabulary f '
                             'JOIN term t ON t.vocabulary = f.vocabulary AND t.key = v.key WHERE f.facet = v.facet)') == [(0,)]
    vocab = r.enums['vocabularies']
    assert rows(minimal.con, 'SELECT count(*) FROM term') == [(sum(len(v['terms']) for v in vocab.values()),)]
    assert rows(minimal.con, 'SELECT count(*) FROM term_member') == \
        [(sum(len(t.get('members') or []) for v in vocab.values() for t in v['terms']),)]
    assert rows(minimal.con, 'SELECT benchmark, id, parent, depth FROM subset ORDER BY id') == \
        [(s['benchmark'], s['id'], s['parent'], s['depth']) for s in sorted(r.corpus['subsets'], key=lambda s: s['id'])]
    chem = rows(minimal.con, "SELECT facet, value, override FROM subset_facet WHERE subset = 'alpha-bench#chem-hard' "
                             "AND facet IN ('domain.primary', 'capability')")
    assert chem == [('domain.primary', 'chemistry-materials/reaction-prediction', 0), ('capability', 'deductive-reasoning', 1)]
    cited = {(kind, rec['id'], sid) for kind in S.KINDS for rec in r.corpus['entities'][kind]
             for sid in artifacts.cited_sources(rec)}
    assert set(rows(minimal.con, "SELECT kind, id, target FROM reference WHERE target_kind = 'source'")) == cited
    assert ('benchmark', 'alpha-bench', 'metrics', 'metric', 'accuracy') in rows(minimal.con, 'SELECT * FROM reference')


def test_meta_and_tables_describe_the_file(minimal):
    meta = dict(rows(minimal.con, 'SELECT key, value FROM _meta'))
    for name, doc in docs(minimal.result).items():
        assert meta[name] == 'sha256:' + M.sha256(emit.serialise(doc))
    assert meta['format'] == str(S.FORMAT) == str(rows(minimal.con, 'PRAGMA user_version')[0][0])
    assert meta['taxonomy'] == minimal.result.enums['taxonomy'] and meta['drafts'] == 'false'
    listed = dict(rows(minimal.con, 'SELECT name, rows FROM _tables'))
    assert set(listed) == {n for (n,) in rows(minimal.con, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    for name, n in listed.items():
        assert rows(minimal.con, 'SELECT count(*) FROM %s' % S.q(name)) == [(n,)], name


# ---- every record in data/, drafts included -------------------------------------------------------------------------

def walk_source(corpus: dict, source: str) -> int:
    """How many items a _tables source path ('corpus.json entities.benchmark[].data.size[]') walks to: an independent
    count of what the table must hold."""
    path = source.split(' ', 1)[1]
    head, _, rest = path.partition('[]')
    level = [corpus]
    for key in head.split('.'):
        level = [x[key] for x in level]
    level = [item for x in level for item in x]
    for step in [s for s in rest.split('[]') if s]:
        nxt = []
        for x in level:
            for key in step.strip('.').split('.'):
                x = x.get(key) if isinstance(x, dict) else None
            nxt += x if isinstance(x, list) else []
        level = nxt
    return len(level)


@pytest.fixture(scope='module')
def everything():
    result = artifacts.build(ROOT, drafts=True)
    assert not result.errors, result.errors
    return SimpleNamespace(result=result, con=S.build(docs(result)))


def test_every_record_in_data_normalises_and_round_trips(everything):
    corpus = everything.result.corpus
    assert corpus['entities']['benchmark'], 'no benchmark in data/, so this would pass vacuously'
    for kind in S.KINDS:
        got = rows(everything.con, 'SELECT record FROM %s ORDER BY rowid' % kind)
        assert [json.loads(r) for (r,) in got] == corpus['entities'][kind], kind
    listed = rows(everything.con, "SELECT name, source, rows FROM _tables WHERE source LIKE 'corpus.json entities.%[]%'")
    assert len(listed) > 40
    for name, source, n in listed:                  # every record table and every list table
        assert walk_source(corpus, source) == n, (name, source)


def test_the_draft_preview_corpus_is_never_written(everything, tmp_path):
    with pytest.raises(S.SqliteError, match='draft preview'):
        S.write(docs(everything.result), str(tmp_path / S.NAME))
    assert not os.path.exists(tmp_path / S.NAME)


# ---- the file -------------------------------------------------------------------------------------------------------

def test_two_writes_are_byte_identical_and_a_sqlite_database(minimal, tmp_path):
    a, b = S.write(docs(minimal.result), str(tmp_path / 'a' / S.NAME)), S.write(docs(minimal.result), str(tmp_path / 'b.sqlite'))
    with open(a, 'rb') as x, open(b, 'rb') as y:
        raw = x.read()
        assert raw == y.read() and raw.startswith(S.MAGIC)
    con = sqlite3.connect(a)
    assert rows(con, 'PRAGMA integrity_check') == [('ok',)] and rows(con, 'SELECT id FROM benchmark') == [('alpha-bench',)]
    con.close()
    assert not os.path.exists(a + '.tmp')


def test_a_path_under_site_is_refused(minimal):
    for path in (os.path.join(SITE, 'public', S.NAME), os.path.join(SITE, 'dist', S.NAME), SITE):
        with pytest.raises(S.SqliteError, match='under site/'):
            S.write(docs(minimal.result), path)
    assert not os.path.exists(os.path.join(SITE, 'public', S.NAME))


def test_a_missing_artifact_is_refused(minimal):
    with pytest.raises(S.SqliteError, match='facets.json was not built'):
        S.build(dict(docs(minimal.result), **{'facets.json': {}}))


# ---- bench build ----------------------------------------------------------------------------------------------------

def test_bench_build_writes_it_beside_the_artifacts_and_not_into_data_or_the_manifest(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from tools import cli
    real = artifacts.build
    monkeypatch.setattr(artifacts, 'build', lambda root: real(FIXTURE))
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert 'wrote %s' % (tmp_path / S.NAME) in r.output
    with open(tmp_path / S.NAME, 'rb') as fh:
        assert fh.read(16) == S.MAGIC
    m = json.loads((tmp_path / M.MANIFEST).read_text(encoding='utf-8'))
    assert S.NAME not in m['paths'] and S.NAME not in m['artifacts']
    assert not [n for n in os.listdir(tmp_path / 'data') if n.endswith(S.DB_SUFFIXES)]
    con = sqlite3.connect(str(tmp_path / S.NAME))
    assert dict(rows(con, 'SELECT key, value FROM _meta'))['corpus.json'] == m['artifacts']['corpus.json']
    con.close()


# ---- the check over a dist ------------------------------------------------------------------------------------------

PAGE = '<!doctype html><html><head><title>t</title></head><body>%s</body></html>'


def dist_with(tmp_path, files: dict) -> str:
    dist = str(tmp_path / 'dist')
    for rel, text in files.items():
        put(os.path.join(dist, *rel.split('/')), text if isinstance(text, bytes) else text.encode('utf-8'))
    return dist


@pytest.mark.parametrize('rel, body, expect', [
    ('index.html', PAGE % '<a href="/index.sqlite">the database</a>', 'references /index.sqlite'),
    ('docs/x/index.html', PAGE % '<link rel="preload" href="../../index.sqlite">', 'references ../../index.sqlite'),
    ('index.html', PAGE % '<script>fetch("index.sqlite").then(r => r)</script>', 'references index.sqlite'),
    ('index.html', PAGE % '<astro-island props="{&quot;db&quot;:[0,&quot;/data/index.sqlite?v=1&quot;]}"></astro-island>',
     'references /data/index.sqlite?v=1'),
    ('index.html', PAGE % '<div data-db="index.sqlite"></div>', 'references index.sqlite'),
    ('index.html', PAGE % '<style>.x { background: url(index.sqlite) }</style>', 'references index.sqlite'),
    ('_astro/island.js', 'const db = await import("./index.sqlite");', 'references ./index.sqlite'),
    ('_redirects', '/db /index.sqlite 302\n', 'references /index.sqlite'),
])
def test_a_reference_in_any_file_fails(tmp_path, rel, body, expect):
    problems = S.dist_problems(dist_with(tmp_path, {rel: body}))
    assert len(problems) == 1 and problems[0].startswith(rel + ': ' + expect), problems


@pytest.mark.parametrize('name', [S.NAME, 'data/corpus.sqlite3', 'assets/renamed.bin'])
def test_a_sqlite_file_fails_by_name_or_by_header(tmp_path, name):
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE t (x)')
    con.execute('VACUUM INTO ?', (str(tmp_path / 'db'),))
    with open(tmp_path / 'db', 'rb') as fh:
        raw = fh.read()
    problems = S.dist_problems(dist_with(tmp_path, {name: raw}))
    assert problems == ['%s: a SQLite database file under the site; index.sqlite never ships (08 S4.2)' % name]


def test_the_look_alikes_are_not_references(tmp_path):
    dist = dist_with(tmp_path, {
        'api/index.html': PAGE % ('<tr data-artifact="index.sqlite and the data tarball"><th><code>index.sqlite and the '
                                  'data tarball</code></th></tr><p>Run your own query against index.sqlite.</p>'
                                  '<a href="https://github.com/o/r/releases/download/v1.0.0/index.sqlite">release</a>'),
        'build-manifest.json': '{"artifacts":{"index.sqlite":"sha256:00"}}\n',
        'feed.json': '{"items":[{"title":"index.sqlite is generated at build time"}]}\n',
        '_astro/x.js': 'const a = "other.sqlite"; const b = "index.sqlite3"; // see index.sqlite',
        'fonts/x.woff2': b'\x00\x01index.sqlite\xff\xfe',
    })
    assert S.dist_problems(dist) == []


def test_the_command_line(tmp_path, capsys):
    clean = dist_with(tmp_path, {'index.html': PAGE % 'nothing'})
    assert S.main(['--check', clean]) == 0 and 'no SQLite file' in capsys.readouterr().out
    put(os.path.join(clean, 'index.html'), (PAGE % '<a href="/index.sqlite">x</a>').encode('utf-8'))
    assert S.main(['--check', clean]) == 1 and 'BLOCKING  sqlite  index.html: references /index.sqlite' in capsys.readouterr().out


def test_the_sites_public_files_ship_no_database():
    """site/public/ is copied into dist/ verbatim, so it is where a database would leak from without any page."""
    assert S.dist_problems(os.path.join(SITE, 'public')) == []


# ---- the site, built ------------------------------------------------------------------------------------------------

BASE = os.path.join(ROOT, 'build', 'sqlite-not-shipped-test')
TREE = os.path.join(BASE, 'root')


@pytest.fixture(scope='module')
def built():
    """`bench build`'s steps over the minimal fixture, index.sqlite included, then the site over that build with the
    database beside the corpus it reads, then S13. As tests/build/test_artifact_urls.py builds it, under build/."""
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
    S.write(docs(result), os.path.join(out, S.NAME))
    M.write(out, written, os.path.join(out, croissant.DIR), root=TREE)
    as_of = dt.date(2026, 11, 18)
    health = ingest_health.build(TREE, as_of)
    put(os.path.join(BASE, 'ingest-health.json'), ingest_health.serialise(health))
    put(os.path.join(BASE, 'freshness.json'), freshness.serialise(freshness.build(TREE, as_of, health)))
    put(os.path.join(BASE, 'feed-events.json'), b'[]\n')
    env = dict(os.environ, UAIBI_CORPUS=os.path.join(out, 'corpus.json'), REPO_ROOT=TREE, BENCH_PYTHON=sys.executable,
               INGEST_HEALTH=os.path.join(BASE, 'ingest-health.json'), FRESHNESS=os.path.join(BASE, 'freshness.json'),
               FEED_EVENTS=os.path.join(BASE, 'feed-events.json'), ASTRO_TELEMETRY_DISABLED='1')
    env.pop('UAIBI_SITE_DRAFTS', None)
    env.pop('BENCH_ROUTES', None)
    r = subprocess.run([NPX, 'astro', 'build', '--outDir', dist], cwd=SITE, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=1800)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    manifest, problems = M.site(dist, out)
    # the copied taxonomy/ names every display-only group id, and CI 9h (scripts/check_display_only_vocab.py) scans
    # build/; nothing reads the tree once the site is built
    shutil.rmtree(TREE, ignore_errors=True)
    return SimpleNamespace(out=out, dist=dist, manifest=manifest, problems=problems)


def test_no_file_under_dist_is_or_references_index_sqlite(built):
    assert os.path.exists(os.path.join(built.out, S.NAME))          # it was there, beside the corpus the site read
    every = [os.path.join(d, n) for d, _, ns in os.walk(built.dist) for n in ns]
    assert len(every) > 100 and not [p for p in every if p.endswith(S.DB_SUFFIXES)]
    assert S.dist_problems(built.dist) == []
    with open(os.path.join(built.dist, 'api', 'index.html'), encoding='utf-8') as fh:
        api = fh.read()
    assert 'data-artifact="index.sqlite and the data tarball"' in api   # named for people, so the check is not vacuous
    assert not re.search(r'(?:href|src)="[^"]*index\.sqlite', api)


def test_the_manifests_site_checks_still_pass(built):
    assert built.problems == []
    assert M.check(built.dist) == []
    assert S.NAME not in json.dumps(built.manifest)


# ---- the verify's build ---------------------------------------------------------------------------------------------

def test_the_verifys_bench_build_wrote_index_sqlite_from_its_corpus():
    out = os.path.join(ROOT, 'build')
    if not os.path.exists(os.path.join(out, M.MANIFEST)):
        pytest.skip('no build/build-manifest.json: run `uv run bench build --out build/` first, as the verify does')
    m = json.loads(open(os.path.join(out, M.MANIFEST), encoding='utf-8').read())
    if not m['documents']:
        pytest.skip('the last bench build into build/ wrote no S9 release artifact (croissant-benchmark/), so no '
                    'index.sqlite either; run `uv run bench build --out build/`, as the verify does')
    path = os.path.join(out, S.NAME)
    assert os.path.exists(path), 'bench build wrote S9 but no build/index.sqlite'
    con = sqlite3.connect(path)
    meta = dict(rows(con, 'SELECT key, value FROM _meta'))
    con.close()
    assert meta['corpus.json'] == m['artifacts']['corpus.json']
    assert S.NAME not in os.listdir(os.path.join(out, 'data'))
