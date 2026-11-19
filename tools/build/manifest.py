#!/usr/bin/env python3
"""build-manifest.json and the three artifact URL namespaces (P2-S1-T05; 08 S4.4, S6, S6.1, S3.1 S13, S7.5).

    bench build --out build/                              # S8: hash the shipped artifacts; build/build-manifest.json
    python tools/build/manifest.py --site site/dist       # S13, after `astro build`: complete, check and publish it
    python tools/build/manifest.py --check site/dist      # check a dist S13 already completed; write nothing

08 S4.4: "Immutable caching wants hashed filenames. Citation wants stable ones." Three namespaces, one job each:

  /data/<name>.<sha8>.json   the site's own fetches, content-hashed. site/public/_headers gives /data/* `public,
                             max-age=31536000, immutable`, which is only true because nothing else is ever there
  /data/latest/<name>.json   a 302 to the current hashed file, max-age=300, for notebooks and curl:
                             site/worker/data-latest.ts, reading this build's /build-manifest.json. No file is ever
                             built under it, so a request there is always an asset miss, which is where the Worker runs
  /build-manifest.json       the stable URL, short TTL (_headers: max-age=300), naming every hashed artifact

The HTML references only the hashed form (site/src/lib/manifest.ts dataHref is the one way a page writes a /data/
URL), so a deploy can never serve a page against a stale artifact; S13 asserts it over every page. An artifact URL is
a cache key, not a citation: the footer says so, and permanent citation is the git tag and the DOI (08 S4.4).

Two halves, because 08 S3.1 hashes in S8 and writes the manifest in S13, over dist/, once the site exists:

  `write` (bench build, S8)  every shipped artifact the build wrote this run -- today emit.ARTIFACTS, corpus.json,
                             facets.json and enums.json; a stage that emits another 08 S4.2 JSON artifact passes it
                             too -- is hashed and copied to build/data/<name>.<sha8>.json, and build/build-manifest.json
                             gets every block except the site's, `files` and `routes`, which are null. A hashed file
                             this build does not name is removed from build/data/.
  `site` (S13, --site)       copies build/data/ into dist/data/, counts dist/ into `files` and `routes`, adds the node
                             that built the site, runs CHECKS, and only when they all hold writes dist/build-manifest.json
                             and the completed build/build-manifest.json (which P2-S7-T04's budget check reads). Nothing
                             wires it to a deploy yet: the workflows are off, and the deploy job is a later task's.

What is hashed (08 S6): sha256 over the uncompressed canonical JSON bytes -- UTF-8, sorted keys, compact separators,
no ASCII escaping, one trailing newline -- which are exactly the bytes emit.serialise writes. `write` refuses a file
that is not canonical, so the hash attests the canonical form, not one spelling of it; compression is the CDN's,
after hashing. sha8 is the first eight hex digits. The hashed copy is byte-identical to build/<name>.

The manifest is 08 S6.1's block, with these decisions:

  index_commit    UAIBI_COMMIT_SHA, else GITHUB_SHA, else `git rev-parse HEAD`: site/src/lib/release.ts's order, so the
                  manifest and every page footer name one commit, which S13 checks
  built_at        SOURCE_DATE_EPOCH, else the commit's author timestamp; never the wall clock (08 S6.2)
  build_clock     BUILD_CLOCK as CI injects it, else null: never cited, outside `bench verify` (08 S6.2, S6.3)
  builder         github-actions under GITHUB_ACTIONS, else local: CI is the only authority for a published build
  taxonomy_version, vocabularies   artifacts.vocabulary_versions(), which P0-S6-T06 left for this manifest to carry
  formats         each shipped artifact's envelope `format`. There is no schema_version: nothing in schema/ defines
                  one, and until something does, 08 S4.5's "the schema version travels with the data" is the
                  per-artifact format a consumer pins (defining one is a schema/ change, not this task's)
  tools           python and the installed version of every pyproject dependency; the locked version
                  (site/package-lock.json) of every site dependency; and node, added by S13, which ran the site build
  inputs          data_tree_sha256 (the data root the build read), taxonomy_sha256, schema_sha256: tree_sha256
  artifacts       name -> "sha256:<64 hex>", as 08 S6.1 writes it
  paths           name -> "/data/<name>.<sha8>.json": what the HTML references and /data/latest/ redirects to
  documents       croissant-benchmark/: its tree hash and file count. The documents are served at their own stable
                  citation URLs (/benchmarks/{id}/cite.jsonld), not under /data/, but `bench verify` diffs them (S6.3)
  counts          published entities by kind, materialised subsets, and the claims on published benchmarks (both
                  tiers, facets.json's claim_count basis), all read from the shipped artifacts themselves
  files           S13's: html, data, pagefind_fragments, index_chunks, assets, total, cap (Cloudflare's 20,000 files
                  per version, 08 S7.5). The five counts must sum to total, and S13 asserts it (08 S6.1)
  routes          S13's: HTML pages by route family, 08 S7.5's table, summing to files.html

atlas.json, which `bench build --atlas` writes (P2-S5-T01), is hashed and named like the other shipped artifacts;
its envelope carries layout_method, layout_epoch and basis_version.

Not here, each because nothing builds it yet: atlas_reproducibility, quality (no S4 stage computes the completeness
means), and the S9 release hashes (index.sqlite, P4-S7-T01).

CHECKS, run by S13 before anything is published, and by --check:

  data      dist/data/ holds exactly the manifest's hashed files, each hashing to its recorded sha256 under the name
            that sha256 gives; nothing is under dist/data/latest/, where a file would shadow the redirect and be
            cached as immutable
  headers   dist/_headers gives /data/* the immutable header and /build-manifest.json the short TTL. That the CDN
            honours them is a property of the deployed site, which 08 S6.3 leaves to a check against a preview
            deployment, not to the build
  html      every data reference in every page is a hashed file the manifest names. A data reference is a URL in a URL
            attribute (href, src, srcset, ...) resolved against the page, or a root-relative /data/... string in any
            attribute value or <script> or <style> body: an island's props, an inline fetch, a CSS url(). One into
            /data/ must be in `paths`; /data/latest/ is refused (it is the consumers' redirect, not the site's);
            and a URL attribute naming a shipped artifact unhashed anywhere else (/corpus.json) is refused. Prose is
            not a reference: /api/ documents /data/latest/<name>.json in text, for people to type. A URL with a host
            is external, because astro.config.mjs fixes no `site`, so the site has no host of its own yet
  commit    every page footer's commit is the manifest's index_commit
  files     the counts sum to total, total is under the cap, routes sum to html; --check also recounts dist/
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from html.parser import HTMLParser
from importlib import metadata
from urllib.parse import unquote, urljoin, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import emit  # noqa: E402

MANIFEST = 'build-manifest.json'
FORMAT = 1
DATA = '/data/'
LATEST = '/data/latest/'
IMMUTABLE = 'public, max-age=31536000, immutable'     # 08 S4.4, the hashed namespace
SHORT_TTL = 'public, max-age=300'                     # 08 S4.4, the manifest (and the Worker's 302)
CAP = 20000                                           # Cloudflare's files per version (08 S7.1, S7.5)
FILE_KEYS = ('html', 'data', 'pagefind_fragments', 'index_chunks', 'assets')
NAME = re.compile(r'^(?:[a-z0-9-]+/)*[a-z0-9-]+\.json$')
URL_ATTRS = frozenset({'href', 'src', 'srcset', 'imagesrcset', 'action', 'formaction', 'poster', 'data', 'cite',
                       'background', 'manifest'})
ROOT_RELATIVE = re.compile(r'(?<![\w.~:/%-])(/data(?:/[^\s"\'<>()\\,;`{}\[\]]*)?)(?![\w.-])')
COMMIT = re.compile(r'^[0-9a-f]{40}$')
SKIP_DIRS = frozenset({'__pycache__'})


class ManifestError(Exception):
    """The manifest cannot be written: `bench build` and S13 stop on it."""


# ---- hashing ------------------------------------------------------------------------------------

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hashed_path(name: str, digest: str) -> str:
    """'corpus.json', its sha256 hex -> '/data/corpus.<sha8>.json'."""
    return '%s%s.%s.json' % (DATA, name[:-len('.json')], digest[:8])


def tree_sha256(top: str) -> str | None:
    """One hash for a directory: sha256 over `<posix path>\\0<sha256 of its bytes>\\n` per file, in UTF-8 byte order of
    the path (08 S6: never the filesystem's order). Python caches are not inputs. None when the directory is absent."""
    if not os.path.isdir(top):
        return None
    files = []
    for folder, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        files += [os.path.relpath(os.path.join(folder, n), top).replace(os.sep, '/') for n in names
                  if not n.endswith('.pyc')]
    h = hashlib.sha256()
    for rel in sorted(files, key=lambda r: r.encode('utf-8')):
        with open(os.path.join(top, *rel.split('/')), 'rb') as fh:
            h.update(b'%s\0%s\n' % (rel.encode('utf-8'), sha256(fh.read()).encode('ascii')))
    return 'sha256:' + h.hexdigest()


def tree_files(top: str) -> int:
    return sum(len(names) for _, _, names in os.walk(top))


# ---- the build's identity -----------------------------------------------------------------------

def git(*args: str) -> str | None:
    try:
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    except OSError:
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def commit() -> str:
    sha = os.environ.get('UAIBI_COMMIT_SHA') or os.environ.get('GITHUB_SHA') or git('rev-parse', 'HEAD')
    if not sha or not COMMIT.match(sha):
        raise ManifestError('no commit SHA (got %r); set UAIBI_COMMIT_SHA outside a git checkout. The manifest names the '
                            'commit every artifact came from (08 S6.1)' % sha)
    return sha


def built_at(sha: str) -> str:
    """SOURCE_DATE_EPOCH, else the commit's author timestamp, as ISO 8601 to the second in UTC (08 S6.1, S6.2)."""
    stamp = os.environ.get('SOURCE_DATE_EPOCH') or git('log', '-1', '--format=%at', sha)
    if not stamp or not stamp.isdigit():
        raise ManifestError('no SOURCE_DATE_EPOCH, and git cannot date commit %s; built_at is the commit\'s timestamp, '
                            'never the wall clock (08 S6.2)' % sha)
    return dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def tools() -> dict[str, str | None]:
    """python, every pyproject dependency as installed, and every site dependency as locked."""
    out: dict[str, str | None] = {'python': platform.python_version()}
    with open(os.path.join(ROOT, 'pyproject.toml'), 'rb') as fh:
        for spec in tomllib.load(fh)['project']['dependencies']:
            name = re.split(r'[\s=<>!~;\[]', spec, maxsplit=1)[0]
            try:
                out[name] = metadata.version(name)
            except metadata.PackageNotFoundError:
                out[name] = None
    site = os.path.join(ROOT, 'site')
    if os.path.exists(os.path.join(site, 'package-lock.json')):
        with open(os.path.join(site, 'package.json'), encoding='utf-8') as fh:
            wanted = sorted(json.load(fh).get('dependencies', {}))     # get-default: a package may declare none
        with open(os.path.join(site, 'package-lock.json'), encoding='utf-8') as fh:
            locked = json.load(fh)['packages']
        for name in wanted:
            out[name] = locked.get('node_modules/' + name, {}).get('version')   # get-default: an unlocked one is null
    return out


def node_version() -> str | None:
    node = shutil.which('node')
    if node is None:
        return None
    r = subprocess.run([node, '--version'], capture_output=True, text=True, encoding='utf-8')
    return r.stdout.strip().lstrip('v') or None if r.returncode == 0 else None


# ---- S8: bench build ----------------------------------------------------------------------------

def counts(docs: dict[str, dict]) -> dict[str, int]:
    out = {}
    corpus, facets = docs.get('corpus.json'), docs.get('facets.json')
    if corpus is not None:
        out.update({kind + 's': len(records) for kind, records in corpus['entities'].items()})
        out['subsets'] = len(corpus['subsets'])
    if facets is not None:
        out['claims'] = sum(r['claim_count'] for r in facets['benchmarks'])
    return out


def write(out_dir: str, shipped: list[str], documents: str | None = None, root: str = ROOT) -> list[str]:
    """Hash each of `shipped` (paths under `out_dir`), copy it to out_dir/data/<name>.<sha8>.json, and write
    out_dir/build-manifest.json; `documents` is the croissant-benchmark directory, `root` the data root the build read.
    Returns the paths written."""
    data_dir = os.path.join(out_dir, 'data')
    if os.path.realpath(data_dir) in {os.path.realpath(os.path.join(r, 'data')) for r in (root, ROOT)}:
        raise ManifestError('--out %s would put the hashed artifacts into the data tree itself' % out_dir)
    entries = {}
    for path in shipped:
        name = os.path.relpath(os.path.abspath(path), os.path.abspath(out_dir)).replace(os.sep, '/')
        if not NAME.match(name):
            raise ManifestError('%s: a shipped artifact is a lower-case .json name under --out, not %r' % (path, name))
        with open(path, 'rb') as fh:
            raw = fh.read()
        doc = json.loads(raw)
        if emit.serialise(doc) != raw:
            raise ManifestError('%s is not canonical JSON, so its sha256 would attest one spelling of it (08 S6)' % path)
        entries[name] = (raw, sha256(raw), doc)
    keep = {hashed_path(name, digest)[len(DATA):] for name, (_, digest, _) in entries.items()}
    if os.path.isdir(data_dir):
        for folder, _, names in os.walk(data_dir, topdown=False):
            for n in names:
                if os.path.relpath(os.path.join(folder, n), data_dir).replace(os.sep, '/') not in keep:
                    os.remove(os.path.join(folder, n))
            if folder != data_dir and not os.listdir(folder):
                os.rmdir(folder)
    written = []
    for name, (raw, digest, _) in sorted(entries.items()):
        target = os.path.join(data_dir, *hashed_path(name, digest)[len(DATA):].split('/'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as fh:
            fh.write(raw)
        written.append(target)
    manifest = build_half({name: (digest, doc) for name, (_, digest, doc) in entries.items()}, documents, root)
    path = os.path.join(out_dir, MANIFEST)
    with open(path, 'wb') as fh:
        fh.write(emit.serialise(manifest))
    return written + [path]


def build_half(entries: dict[str, tuple[str, dict]], documents: str | None, root: str) -> dict:
    from tools.build.artifacts import vocabulary_versions
    sha = commit()
    vocab = vocabulary_versions(ROOT)
    return {
        'artifact': 'build-manifest', 'format': FORMAT,
        'index_commit': sha, 'built_at': built_at(sha), 'build_clock': os.environ.get('BUILD_CLOCK') or None,
        'builder': 'github-actions' if os.environ.get('GITHUB_ACTIONS') == 'true' else 'local',
        'taxonomy_version': vocab.pop('taxonomy'), 'vocabularies': vocab,
        'formats': {name: doc.get('format') for name, (_, doc) in entries.items()},   # null for an unenveloped one
        'tools': tools(),
        'inputs': {'data_tree_sha256': tree_sha256(os.path.join(root, 'data')),
                   'taxonomy_sha256': tree_sha256(os.path.join(ROOT, 'taxonomy')),
                   'schema_sha256': tree_sha256(os.path.join(ROOT, 'schema'))},
        'artifacts': {name: 'sha256:' + digest for name, (digest, _) in entries.items()},
        'paths': {name: hashed_path(name, digest) for name, (digest, _) in entries.items()},
        'documents': ({os.path.basename(os.path.normpath(documents)): {'sha256': tree_sha256(documents),
                                                                         'files': tree_files(documents)}}
                      if documents and os.path.isdir(documents) else {}),
        'counts': counts({name: doc for name, (_, doc) in entries.items()}),
        'files': None, 'routes': None,             # S13's, once the site exists
    }


# ---- S13: the site ------------------------------------------------------------------------------

def load(path: str, first: str = '`uv run bench build`') -> dict:
    if not os.path.exists(path):
        raise ManifestError('%s does not exist; run %s first' % (path, first))
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or doc.get('artifact') != 'build-manifest' or not isinstance(doc.get('paths'), dict):
        raise ManifestError('%s is not the manifest this module writes' % path)
    return doc


def walk(dist: str) -> list[str]:
    out = []
    for folder, _, names in os.walk(dist):
        out += [os.path.relpath(os.path.join(folder, n), dist).replace(os.sep, '/') for n in names]
    return sorted(out, key=lambda r: r.encode('utf-8'))


def count(dist: str) -> tuple[dict[str, int], dict[str, int]]:
    """(files, routes) for a dist that holds, or is about to hold, its build-manifest.json."""
    files = dict.fromkeys(FILE_KEYS, 0)
    routes: dict[str, int] = {}
    for rel in sorted(set(walk(dist)) | {MANIFEST}):
        parts = rel.split('/')
        if rel.endswith('.html'):
            files['html'] += 1
            family = '/%s/' % parts[0] if len(parts) > 1 else '/'
            routes[family] = routes.get(family, 0) + 1      # get-default: a family's first page starts its count
        elif parts[0] == 'data':
            files['data'] += 1
        elif rel.endswith('.pf_fragment'):
            files['pagefind_fragments'] += 1
        elif rel.endswith('.pf_index'):
            files['index_chunks'] += 1
        else:
            files['assets'] += 1
    files['total'] = sum(files[k] for k in FILE_KEYS)
    files['cap'] = CAP
    return files, dict(sorted(routes.items()))


def site(dist: str, build_dir: str = os.path.join(ROOT, 'build')) -> tuple[dict, list[str]]:
    """S13: put build/data/ into dist/data/, complete the manifest, check it; publish only if every check holds."""
    manifest = load(os.path.join(build_dir, MANIFEST))
    problems = []
    for name, url in sorted(manifest['paths'].items()):
        rel = url[len(DATA):]
        src = os.path.join(build_dir, 'data', *rel.split('/'))
        if not os.path.exists(src):
            problems.append('%s: build/data/%s is missing; rerun `uv run bench build`' % (name, rel))
            continue
        with open(src, 'rb') as fh:
            raw = fh.read()
        recorded = manifest['artifacts'].get(name)
        if 'sha256:' + sha256(raw) != recorded:
            problems.append('%s: build/data/%s does not hash to the manifest\'s %s' % (name, rel, recorded))
            continue
        target = os.path.join(dist, 'data', *rel.split('/'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'wb') as fh:
            fh.write(raw)
    manifest = dict(manifest, tools=dict(manifest['tools'], node=node_version()))
    manifest['files'], manifest['routes'] = count(dist)
    problems += check(dist, manifest)
    if not problems:
        for path in (os.path.join(dist, MANIFEST), os.path.join(build_dir, MANIFEST)):
            with open(path, 'wb') as fh:
                fh.write(emit.serialise(manifest))
    return manifest, problems


def check(dist: str, manifest: dict | None = None) -> list[str]:
    """Every CHECK over a dist. With no `manifest`, dist's own, and its file counts are recounted."""
    problems = []
    if manifest is None:
        manifest = load(os.path.join(dist, MANIFEST), 'tools/build/manifest.py --site')
        files, routes = count(dist)
        if (manifest.get('files'), manifest.get('routes')) != (files, routes):      # a build half has neither
            problems.append('the manifest counts files %s and routes %s, but dist holds %s and %s'
                            % (manifest.get('files'), manifest.get('routes'), files, routes))
    return (problems + check_data(dist, manifest) + check_headers(dist) + check_html(dist, manifest)
            + check_files(manifest))


def check_data(dist: str, manifest: dict) -> list[str]:
    problems, expected = [], {}
    for name, url in sorted(manifest['paths'].items()):
        digest = (manifest['artifacts'].get(name) or '')[len('sha256:'):]   # a path with no hash fails below
        if not digest or url != hashed_path(name, digest):
            problems.append('%s: the manifest gives it path %s, which is not the hashed name its sha256 gives' % (name, url))
        expected[url[len(DATA):]] = digest
    top = os.path.join(dist, 'data')
    found = set(walk(top)) if os.path.isdir(top) else set()
    for rel in sorted(found - set(expected)):
        problems.append('data/%s: not a hashed artifact the manifest names, but everything under /data/ is served as '
                        'immutable (site/public/_headers)' % rel)
    for rel in sorted(set(expected) - found):
        problems.append('data/%s: the manifest names it, but dist does not hold it' % rel)
    for rel in sorted(found & set(expected)):
        with open(os.path.join(top, *rel.split('/')), 'rb') as fh:
            if sha256(fh.read()) != expected[rel]:
                problems.append('data/%s: its bytes do not hash to the manifest\'s sha256' % rel)
    if os.path.exists(os.path.join(top, 'latest')):
        problems.append('data/latest/: nothing may be built there; the Worker answers it (site/worker/data-latest.ts), '
                        'and a file would shadow the redirect and be cached as immutable')
    return problems


def parse_headers(text: str) -> dict[str, dict[str, str]]:
    """Cloudflare's _headers: a URL pattern at the margin, then its indented `Name: value` lines; `#` is a comment."""
    rules: dict[str, dict[str, str]] = {}
    current = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line[0].isspace():
            current = rules.setdefault(line.strip(), {})
        elif current is not None and ':' in line:
            key, _, value = line.strip().partition(':')
            current[key.strip().lower()] = value.strip()
        else:
            raise ValueError('%r is not under a URL pattern' % line)
    return rules


def check_headers(dist: str) -> list[str]:
    path = os.path.join(dist, '_headers')
    if not os.path.exists(path):
        return ['_headers is missing (site/public/_headers), so nothing marks /data/ immutable']
    try:
        with open(path, encoding='utf-8') as fh:
            rules = parse_headers(fh.read())
    except ValueError as e:
        return ['_headers: %s' % e]
    out = []
    for pattern, want in (('/data/*', IMMUTABLE), ('/' + MANIFEST, SHORT_TTL)):
        got = rules.get(pattern, {}).get('cache-control')               # get-default: an absent rule is reported
        if got != want:
            out.append('_headers: %s has Cache-Control %r, not %r (08 S4.4)' % (pattern, got, want))
    return out


class _Refs(HTMLParser):
    """The URL attributes, and every other attribute value and script or style body, of one page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []
        self.raw: list[str] = []
        self._in: str | None = None

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value is None:
                continue
            if key in URL_ATTRS:
                self.urls += [c.strip().split()[0] for c in value.split(',') if c.strip()] if key.endswith('srcset') \
                    else [value.strip()]
            self.raw.append(value)
        if tag in ('script', 'style'):
            self._in = tag

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self._in = None

    def handle_endtag(self, tag):
        if tag == self._in:
            self._in = None

    def handle_data(self, data):
        if self._in is not None:
            self.raw.append(data)


def page_url(rel: str) -> str:
    """'api/index.html' -> '/api/'; '404.html' -> '/404.html'."""
    return '/' + (rel[:-len('index.html')] if rel == 'index.html' or rel.endswith('/index.html') else rel)


def data_problem(path: str, hashed: set[str], unhashed: set[str], strict_names: bool) -> str | None:
    path = unquote(path)
    if path == '/data' or path.startswith(DATA):
        if path.rstrip('/') == LATEST.rstrip('/') or path.startswith(LATEST):
            return ('%s is /data/latest/, the consumers\' redirect; the site references the hashed form only (08 S4.4)'
                    % path)
        if path not in hashed:
            return '%s is not a hashed artifact this build\'s manifest names' % path
        return None
    if strict_names and path.rsplit('/', 1)[-1] in unhashed:
        return '%s names a shipped artifact unhashed; reference this build\'s /data/ file instead' % path
    return None


def check_html(dist: str, manifest: dict) -> list[str]:
    hashed = set(manifest['paths'].values())
    unhashed = {name.rsplit('/', 1)[-1] for name in manifest['paths']}
    problems = []
    for rel in walk(dist):
        if not rel.endswith('.html'):
            continue
        with open(os.path.join(dist, *rel.split('/')), encoding='utf-8') as fh:
            page = fh.read()
        refs = _Refs()
        refs.feed(page)
        refs.close()
        base = page_url(rel)
        found = []
        for url in refs.urls:
            parts = urlsplit(urljoin(base, url))
            if not parts.scheme and not parts.netloc:            # a host is external: no `site` is fixed yet
                found.append((parts.path, True))
        for text in refs.raw:
            found += [(urlsplit(m.group(1)).path, False) for m in ROOT_RELATIVE.finditer(text)]
        seen = set()
        for path, strict in found:
            why = data_problem(path, hashed, unhashed, strict)
            if why and why not in seen:
                seen.add(why)
                problems.append('%s: %s' % (rel, why))
        commits = set(re.findall(r'<footer[^>]*data-build-footer[^>]*>.*?data-commit="([0-9a-f]{40})"', page, re.S))
        if commits - {manifest['index_commit']}:
            problems.append('%s: its footer names commit %s, the manifest %s'
                            % (rel, ', '.join(sorted(commits)), manifest['index_commit']))
    return problems


def check_files(manifest: dict) -> list[str]:
    files, routes = manifest.get('files'), manifest.get('routes')       # a build half has neither
    if not isinstance(files, dict) or not isinstance(routes, dict):
        return ['the manifest has no file counts; S13 (--site) writes them']
    out = []
    if any(not isinstance(files.get(k), int) for k in FILE_KEYS + ('total', 'cap')):
        return ['files %s: every count is an integer' % files]
    if sum(files[k] for k in FILE_KEYS) != files['total']:
        out.append('files: %s sum to %d, not total %d (08 S6.1)'
                   % (', '.join(FILE_KEYS), sum(files[k] for k in FILE_KEYS), files['total']))
    if files['total'] > files['cap']:
        out.append('files: %d files, over the %d-file cap per version (08 S7.5)' % (files['total'], files['cap']))
    if sum(routes.values()) != files['html']:
        out.append('routes: %d pages by family, but files.html is %d' % (sum(routes.values()), files['html']))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--site', metavar='DIST', help='S13: complete and publish the manifest into a built site')
    mode.add_argument('--check', metavar='DIST', help='check a site S13 already completed; write nothing')
    p.add_argument('--build', default=os.path.join(ROOT, 'build'), help='bench build\'s --out (default: build/)')
    a = p.parse_args(argv)
    try:
        if a.site:
            manifest, problems = site(a.site, a.build)
        else:
            manifest, problems = load(os.path.join(a.check, MANIFEST), '--site'), check(a.check)
    except ManifestError as e:
        print('BLOCKING  manifest  %s' % e)
        return 1
    for line in problems:
        print('BLOCKING  manifest  %s' % line)
    files = manifest.get('files') or {}                                 # a build half has none
    print('manifest: %d hashed artifact(s), commit %s, %s file(s) of %s; %d problem(s)%s'
          % (len(manifest['paths']), manifest['index_commit'][:12], files.get('total'), files.get('cap'), len(problems),
             '' if problems or not a.site else '; wrote %s' % os.path.join(a.site, MANIFEST)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
