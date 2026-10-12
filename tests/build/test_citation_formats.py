"""The citation block, the export formats and the page footer (P2-S3-T07; 10 "The permanent citation URL", 08 S4.4).

The verify: `uv run pytest tests/build/test_citation_formats.py`. Done when: "All five formats render for a fixture
entry and every route's footer carries the release tag, commit SHA and build timestamp."

The site is built over the draft preview (scripts/preview_corpus.py; no entry is published yet) into build/, and
tools/build/citation.py -- which parses what was built without the site's own code -- checks it: every benchmark's
cite.bib, cite.json, cite.ris and cite.yaml parse and agree with each other and with the page, none points at an
artifact URL, and every page's footer carries the build. The failure each check exists for is shown by tampering with
a copy. Four of the five formats are here; Croissant JSON-LD is P2-S3-T06's, which waits on the S8 emitter.
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
from tools.build import citation  # noqa: E402

SITE = os.path.join(ROOT, 'site')
NPM = shutil.which('npm')
FIXTURE = 'swe-bench'


@pytest.fixture(scope='module')
def built():
    if NPM is None:
        pytest.skip('npm is not installed')
    preview = os.path.join(ROOT, 'build', 'preview')
    out = os.path.join(ROOT, 'build', 'site-cite-test')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'preview_corpus.py'), '--out', preview],
                       capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr
    env = dict(os.environ, UAIBI_CORPUS=os.path.join(preview, 'corpus.json'), UAIBI_SITE_DRAFTS='1', ASTRO_TELEMETRY_DISABLED='1')
    r = subprocess.run([NPM, 'run', 'build', '--', '--outDir', out], cwd=SITE, env=env, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', shell=os.name == 'nt')
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    with open(os.path.join(preview, 'corpus.json'), encoding='utf-8') as fh:
        return out, [b['id'] for b in json.load(fh)['entities']['benchmark']]


def read(out, *parts, binary=False):
    path = os.path.join(out, *parts)
    return open(path, 'rb').read() if binary else open(path, encoding='utf-8').read()


# ---- the verify ----------------------------------------------------------------------------------------------------

def test_verify_every_benchmarks_formats_and_every_pages_footer_hold(built):
    out, ids = built
    problems, benchmarks, pages = citation.check(out)
    assert problems == []
    assert benchmarks == len(ids) > 0
    assert pages > benchmarks                         # benchmarks, versions, systems, orgs, metrics, terms, docs, ...


def test_the_fixture_entrys_four_formats_parse_and_cite_one_thing(built):
    out, _ = built
    bib = citation.parse_bibtex(read(out, 'benchmarks', FIXTURE, 'cite.bib'))
    csl = citation.parse_csl(read(out, 'benchmarks', FIXTURE, 'cite.json'))
    ris = citation.parse_ris(read(out, 'benchmarks', FIXTURE, 'cite.ris', binary=True))
    commit, path = citation.PERMALINK.match(bib['url']).groups()
    assert path == 'data/benchmarks/code/swe-bench.yaml'
    assert bib['title'] == csl['title'] == ris['title'] == 'SWE-bench'
    assert bib['doi'] == csl['doi'] == ris['doi'] == citation.concept_doi(ROOT) is not None
    assert csl['key'] == bib['key'] == 'uaibi-swe-bench-%s' % commit[:7]
    assert read(out, 'benchmarks', FIXTURE, 'cite.yaml', binary=True) == open(os.path.join(ROOT, path), 'rb').read()
    footer = re.search(r'data-commit="([0-9a-f]{40})"', read(out, 'benchmarks', FIXTURE, 'index.html')).group(1)
    assert footer == commit                           # the page and its citation name one commit


def test_the_footer_carries_release_commit_timestamp_and_the_cache_key_sentence(built):
    out, _ = built
    for page in (('index.html',), ('benchmarks', FIXTURE, 'index.html'), ('api', 'index.html'), ('feed', 'index.html'),
                 ('taxonomy', 'capability', 'planning', 'index.html')):
        foot = re.search(r'<footer[^>]*data-build-footer[^>]*>(.*?)</footer>', read(out, *page), re.S).group(1)
        assert re.search(r'data-release', foot) and re.search(r'data-commit="[0-9a-f]{40}"', foot), page
        assert re.search(r'datetime="\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"', foot), page
        assert 'An artifact URL is a cache key, not a citation' in foot, page


# ---- each check catches the failure it exists for ---------------------------------------------------------------------

@pytest.fixture
def copy(built, tmp_path):
    """A two-page dist: the fixture entry's directory and the home page."""
    out, _ = built
    dist = tmp_path / 'dist'
    shutil.copytree(os.path.join(out, 'benchmarks', FIXTURE), dist / 'benchmarks' / FIXTURE)
    shutil.copy(os.path.join(out, 'index.html'), dist / 'index.html')
    assert citation.check(str(dist))[0] == []
    return dist


def tamper(path, old, new, count=1):
    data = path.read_bytes().decode('utf-8')
    assert data.count(old) >= count, old
    path.write_bytes(data.replace(old, new).encode('utf-8'))


def problems(dist):
    return '\n'.join(citation.check(str(dist))[0])


def test_a_format_citing_another_commit_is_caught(copy):
    bib = copy / 'benchmarks' / FIXTURE / 'cite.bib'
    commit = citation.PERMALINK.match(citation.parse_bibtex(bib.read_text(encoding='utf-8'))['url']).group(1)
    tamper(bib, '/blob/%s/' % commit, '/blob/%s/' % ('0' * 40))
    assert 'cite.json cites' in problems(copy) and 'not ' in problems(copy)


def test_a_format_pointing_at_an_artifact_url_is_caught(copy):
    path = copy / 'benchmarks' / FIXTURE / 'cite.json'
    item = json.loads(path.read_text(encoding='utf-8'))
    item[0]['note'] += ' See https://example.org/data/latest/corpus.json'
    path.write_text(json.dumps(item), encoding='utf-8')
    assert 'cite.json points at an artifact URL' in problems(copy)


def test_ris_without_crlf_and_a_drifted_yaml_are_caught(copy):
    ris = copy / 'benchmarks' / FIXTURE / 'cite.ris'
    ris.write_bytes(ris.read_bytes().replace(b'\r\n', b'\n'))
    assert 'RIS lines must end in CRLF' in problems(copy)
    ris.write_bytes(ris.read_bytes().replace(b'\n', b'\r\n'))
    tamper(copy / 'benchmarks' / FIXTURE / 'cite.yaml', 'id: swe-bench', 'id: swe-bench-edited')
    assert 'cite.yaml is not data/benchmarks/code/swe-bench.yaml' in problems(copy)


def test_a_page_without_its_footer_or_from_another_build_is_caught(copy):
    home = copy / 'index.html'
    html = home.read_text(encoding='utf-8')
    commit = re.search(r'data-commit="([0-9a-f]{40})"', html).group(1)
    home.write_text(html.replace(commit, 'f' * 40), encoding='utf-8')
    assert 'one build, but footers carry 2 commits' in problems(copy)
    home.write_text(re.sub(r'<footer[^>]*data-build-footer.*?</footer>', '', html, flags=re.S), encoding='utf-8')
    assert 'index.html: no build footer' in problems(copy)


def test_a_citation_block_without_its_format_links_is_caught(copy):
    tamper(copy / 'benchmarks' / FIXTURE / 'index.html', 'cite.ris"', 'cite-gone.ris"')
    assert 'the citation block does not link cite.ris' in problems(copy)
