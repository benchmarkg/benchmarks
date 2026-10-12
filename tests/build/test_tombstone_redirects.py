"""Version-pinned pages and tombstone redirects: a published citation URL cannot stop resolving (P2-S3-T08).

The verify: `uv run pytest tests/build/test_tombstone_redirects.py`. Done when: "Every superseded version has a
page, every tombstoned id 301s to its target, and current editions are not rendered as their own files."

  redirects   tools/build/redirects.py over throwaway trees: each tombstone becomes one 301 from its route to its
              target's (chains collapsed), and the four ways a citation could stop resolving are refused. The
              committed site/worker/redirects.json is what the generator writes today.
  worker      site/worker/redirects.ts, run in Node over a generated table: every tombstoned path 301s to its
              target with the rest of the path and the query kept, and a live path is left alone.
  versions    the site built over the draft preview (scripts/preview_corpus.py), into build/: a page for every
              superseded version, none for a current version or edition, and the two pages linked both ways.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import redirects  # noqa: E402

SITE = os.path.join(ROOT, 'site')
NODE = shutil.which('node')
NPM = shutil.which('npm')


def write(root, rel, text):
    path = os.path.join(root, *rel.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


@pytest.fixture
def tree(tmp_path):
    root = str(tmp_path / 'root')
    write(root, 'data/benchmarks/code/new-bench.yaml', 'id: new-bench\n')
    write(root, 'data/metrics/accuracy.yaml', 'id: accuracy\n')
    write(root, 'data/systems/sys-b.yaml', 'id: sys-b\n')
    write(root, 'data/tombstones/old-bench.yaml', 'id: old-bench\nredirects_to: new-bench\n')
    write(root, 'data/tombstones/older-bench.yaml', 'id: older-bench\nredirects_to: old-bench\n')     # a chain
    write(root, 'data/tombstones/acc.yaml', 'id: acc\nredirects_to: accuracy\n')
    write(root, 'data/tombstones/sys-a.yaml', 'id: sys-a\nredirects_to: sys-b\n')
    return root


# ---- the table ------------------------------------------------------------------------------------------------

def test_every_tombstone_is_one_301_to_its_targets_route(tree):
    assert redirects.build(tree)['redirects'] == [
        {'from': '/metrics/acc/', 'to': '/metrics/accuracy/', 'status': 301},
        {'from': '/benchmarks/old-bench/', 'to': '/benchmarks/new-bench/', 'status': 301},
        {'from': '/benchmarks/older-bench/', 'to': '/benchmarks/new-bench/', 'status': 301},      # one hop, not two
        {'from': '/systems/sys-a/', 'to': '/systems/sys-b/', 'status': 301},
    ]


@pytest.mark.parametrize('rel, text, expect', [
    ('data/tombstones/gone.yaml', 'id: gone\nredirects_to: null\n', 'gone is tombstoned with no redirects_to'),
    ('data/tombstones/gone.yaml', 'id: gone\nredirects_to: nowhere\n', 'gone redirects to nowhere, which is no'),
    ('data/tombstones/new-bench.yaml', 'id: new-bench\nredirects_to: old-bench\n', 'new-bench is tombstoned but still has a live record'),
    ('data/tombstones/loop-a.yaml', 'id: loop-a\nredirects_to: loop-b\n', 'tombstone cycle'),
])
def test_a_citation_that_could_not_resolve_is_refused(tree, rel, text, expect):
    write(tree, rel, text)
    if 'loop-a' in rel:
        write(tree, 'data/tombstones/loop-b.yaml', 'id: loop-b\nredirects_to: loop-a\n')
    with pytest.raises(redirects.RedirectError, match=expect):
        redirects.build(tree)


def test_the_committed_table_is_what_the_tombstones_say():
    assert redirects.main(['--check']) == 0


# ---- the Worker ---------------------------------------------------------------------------------------------------

DRIVER = """
import { redirect } from %s;
const table = JSON.parse(process.argv[1]);
const out = {};
for (const path of JSON.parse(process.argv[2])) {
  const r = redirect(new URL('https://index.example' + path), table);
  out[path] = r == null ? null : [r.status, r.headers.get('Location')];
}
console.log(JSON.stringify(out));
"""


def run_worker(table, paths):
    module = json.dumps('file:///' + os.path.join(SITE, 'worker', 'redirects.ts').replace('\\', '/'))
    r = subprocess.run([NODE, '--input-type=module', '-e', DRIVER % module, json.dumps(table), json.dumps(paths)],
                       capture_output=True, text=True, encoding='utf-8', cwd=SITE)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason='node is not installed')
def test_the_worker_301s_every_tombstoned_path_and_keeps_the_rest(tree):
    table = redirects.build(tree)
    got = run_worker(table, ['/benchmarks/old-bench/', '/benchmarks/older-bench', '/benchmarks/old-bench/v/2024/?ref=x',
                             '/metrics/acc/', '/systems/sys-a/', '/benchmarks/new-bench/', '/benchmarks/old-bench-2/'])
    assert got == {
        '/benchmarks/old-bench/': [301, 'https://index.example/benchmarks/new-bench/'],
        '/benchmarks/older-bench': [301, 'https://index.example/benchmarks/new-bench/'],
        '/benchmarks/old-bench/v/2024/?ref=x': [301, 'https://index.example/benchmarks/new-bench/v/2024/?ref=x'],
        '/metrics/acc/': [301, 'https://index.example/metrics/accuracy/'],
        '/systems/sys-a/': [301, 'https://index.example/systems/sys-b/'],
        '/benchmarks/new-bench/': None,                     # a live page is never redirected
        '/benchmarks/old-bench-2/': None,                   # a prefix of another id is not a match
    }
    for row in table['redirects']:                          # every row, exactly its target
        assert run_worker(table, [row['from']])[row['from']] == [301, 'https://index.example' + row['to']]


# ---- the version pages --------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def built():
    """The site over the draft preview, built into build/ (same volume as the repository, and gitignored)."""
    if NPM is None:
        pytest.skip('npm is not installed')
    preview = os.path.join(ROOT, 'build', 'preview')
    out = os.path.join(ROOT, 'build', 'site-versions-test')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'preview_corpus.py'), '--out', preview],
                       capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr
    env = dict(os.environ, UAIBI_CORPUS=os.path.join(preview, 'corpus.json'), UAIBI_SITE_DRAFTS='1',
               ASTRO_TELEMETRY_DISABLED='1')
    r = subprocess.run([NPM, 'run', 'build', '--', '--outDir', out], cwd=SITE, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', shell=os.name == 'nt')
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    with open(os.path.join(preview, 'corpus.json'), encoding='utf-8') as fh:
        corpus = json.load(fh)
    return out, corpus['entities']['benchmark']


def page(out, *parts):
    path = os.path.join(out, *parts, 'index.html')
    return open(path, encoding='utf-8').read() if os.path.exists(path) else None


def test_every_superseded_version_has_a_page_and_no_current_version_does(built):
    out, benchmarks = built
    superseded = [(b['id'], v['version']) for b in benchmarks for v in b['versions'] if v['superseded_by']]
    current = [(b['id'], v['version']) for b in benchmarks for v in b['versions'] if not v['superseded_by']]
    assert superseded, 'the preview has no superseded version, so this would pass vacuously'
    assert any(v['version_kind'] == 'edition' and not v['superseded_by'] for b in benchmarks for v in b['versions'])
    for bid, ver in superseded:
        assert page(out, 'benchmarks', bid, 'v', ver) is not None, '%s@%s has no page' % (bid, ver)
    for bid, ver in current:
        assert page(out, 'benchmarks', bid, 'v', ver) is None, '%s@%s is current and must not be a file' % (bid, ver)
    made = sorted((b, v) for b in os.listdir(os.path.join(out, 'benchmarks'))
                  if os.path.isdir(os.path.join(out, 'benchmarks', b, 'v'))
                  for v in os.listdir(os.path.join(out, 'benchmarks', b, 'v')))
    assert made == sorted(superseded)


def test_the_version_page_and_the_benchmark_page_link_each_other(built):
    out, benchmarks = built
    for b in benchmarks:
        parent = page(out, 'benchmarks', b['id'])
        for v in b['versions']:
            assert 'data-version="%s"' % v['version'] in parent                  # every version on the parent page
            if not v['superseded_by']:
                continue
            assert 'href="/benchmarks/%s/v/%s/"' % (b['id'], v['version']) in parent
            pinned = page(out, 'benchmarks', b['id'], 'v', v['version'])
            assert 'data-superseded' in pinned and 'href="/benchmarks/%s/"' % b['id'] in pinned
            assert re.search(r'<code[^>]*>%s</code>' % re.escape(v['superseded_by']), pinned)  # names its successor
            assert pinned.count('<script') == 1                                   # the pre-paint line only
