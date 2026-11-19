"""The preview build modes: --data-only, and --routes-from-diff's entity-to-route map (P2-S1-T04; 08 S3.4, 05 S3).

    bench build --data-only --out build/                     # the preview build: no S9, no S10, no SQLite
    python scripts/routes_from_diff.py --base origin/main     # BENCH_ROUTES for that diff, one route per line
    BENCH_ROUTES="$(python scripts/routes_from_diff.py --base origin/main)" npm run build   # (in site/)

08 S3.4 names both as what keeps a 1-5 file PR's preview inside its budget whatever Astro's experimental incremental
build does: "**Build `--routes-from-diff` in Phase 2 whether or not `incrementalBuild` works**, because a preview that
renders only the changed routes is also the preview a reviewer wants to read."

--data-only. 08 S3.4: "A `--data-only` build mode that skips S9 release artifacts, S10 codegen and the SQLite emission
entirely. Those are needed for a release, not for a preview." What each is in `bench build` today (SKIPPED):

  S9    the release artifacts 08 S2 lists for it: the croissant-benchmark JSON-LD, its mlcroissant and extension-schema
        validation included, and index.sqlite, the SQLite emission (P2-S1-T06). corpus.csv.zip, its third, is
        P4-S7-T01's and not built yet. A preview page then carries no JSON-LD and has no cite.jsonld, which is what
        site/src/lib/croissant.ts renders when a build wrote none.
  S10   the generators `bench build` runs into committed source: site/src/styles/tokens.css and site/src/lib/tokens.json
        (09 S13) and site/src/lib/taxonomy.json (P2-S2-T06). A preview reads the committed copies, which are what the
        PR under review carries; `bench schema gen`, the rest of S10, is its own command and never ran inside the build.

Everything else runs: S1-S8, the content-hashed artifacts and the build half of the manifest S13 completes,
dormancy.json, and --derived and --atlas when asked for. A data-only build into an --out that a full build used first
removes that build's S9 outputs (`clear`), so the directory never pairs this build's corpus with another build's
documents or database, and the manifest's `documents` block, read from the directory, is empty: a data-only build's
manifest shows that it shipped no release artifact.

--routes-from-diff. 08 S3.4: "A small integration reads `BENCH_ROUTES`, a newline-separated list of route paths
computed by mapping `git diff --name-only <base>...<head>` through the entity-to-route map, and every
`getStaticPaths()` filters to that list plus the fixed narrative routes. ... `main` always renders everything."
scripts/routes_from_diff.py runs the diff, `plan` below is the map, and site/src/lib/bench-routes.ts is the filter.
The map, one changed path at a time, against the corpus the same commit publishes (build/corpus.json):

  data/benchmarks/**/<id>.yaml    /benchmarks/<id>/, which brings everything beneath it: its citation files and its
  data/systems/<id>.yaml          superseded versions. /systems/<id>/, /orgs/<id>/, /metrics/<id>/ likewise.
  data/organizations/<id>.yaml    A record the commit does not publish (a draft, a stub, a deleted file) has no
  data/metrics/<id>.yaml          page, so it adds no route.
  data/sources/**/<id>.yaml       the page of every published record that cites it: a source renders as an anchored
                                  block on each (08 S7.5 Decision 4), never as a page of its own
  data/claims/**/<id>.yaml        its benchmark's and its system's pages, which count it; a deleted claim is read at
                                  the merge base, so the pages that counted it re-render
  data/conditions/<id>.yaml       the pages of every claim that names it, as above
  any other data/ record          nothing: no page renders a leaderboard, rating pool, dispute, alias, baselines
                                  file, ingest batch or survey record of its own (the fixed narrative routes, which
                                  aggregate data/, always render)
  taxonomy/ (not _corpus/,        everything (`*`): 08 S3.3, "Taxonomy term added | Everything" and "Pydantic schema
  _failures/), schema/, tools/,   changed | ... then everything"; a template, a style, the design tokens or a build
  site/ (not its tests), design/, tool can change any page; CITATION.cff is every page's citation block; pyproject.toml
  CITATION.cff, pyproject.toml,   and uv.lock are the toolchain
  uv.lock
  tests, docs/, the plan, ADRs,   nothing: no route reads them, or the fixed narrative routes render them (docs/'s
  scripts/, ingest/, ...          three pages are /docs/{slug}/)
  anything else                   everything: a path the map cannot place re-renders every route rather than none

What BENCH_ROUTES holds: one route per line, sorted. `*` alone means every route. An empty list is a valid preview,
the fixed narrative routes only, for a diff no page renders. A route ending in `/` brings the routes beneath it; one
ending in a file name is that file. Unset, the site renders everything, and a build of main itself -- a push to it,
its scheduled rebuild, a manual run -- renders everything whatever BENCH_ROUTES says (`main_build`; bench-routes.ts
holds the same rule, and tests/build/test_routes_from_diff.py holds the two to each other). build-preview.yml runs on
workflow_run with GITHUB_REF on main too (08 S7.4), which is why the rule reads the event and not only the ref.

On Windows under Git Bash, MSYS rewrites an environment value that looks like a POSIX path before it reaches a native
program (`/benchmarks/x/` arrives as `C:/Program Files/Git/benchmarks/x/`), so a local preview there sets
MSYS_NO_PATHCONV=1; CI's Linux runners do not rewrite. `bench build`'s note prints the routes it was handed, which
makes a rewritten value visible.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

EVERYTHING = '*'
SKIPPED = {
    'S9': ('croissant-benchmark/', 'index.sqlite'),
    'S10': ('site/src/styles/tokens.css', 'site/src/lib/tokens.json', 'site/src/lib/taxonomy.json'),
}
S9_OUTPUTS = ('croissant-benchmark', 'index.sqlite')         # under --out: what `clear` removes
ENTITY_ROUTES = {'benchmark': '/benchmarks/%s/', 'system': '/systems/%s/', 'organization': '/orgs/%s/',
                 'metric': '/metrics/%s/'}
MAIN_REF = 'refs/heads/main'
MAIN_EVENTS = frozenset({'push', 'schedule', 'workflow_dispatch'})   # a build of the branch's own head
# A changed path no route reads, beyond the fixed narrative routes that always render: prefix -> why.
NO_ROUTE = {
    'tests/': 'a test', 'site/test/': 'a site test', 'site/tests/': 'a site test', '_plan/': 'the plan',
    'adr/': 'an ADR', '.github/': 'a workflow', 'scripts/': 'a script the build does not run', 'evals/': 'an eval',
    'metrics/': 'a curation metric', 'reports/': 'a report', 'drafts/': 'an AI draft, never published',
    'ingest/': 'ingestion, whose output is data/', 'vendor/': 'vendor/, never in a CC-BY artifact (08 S3.2)',
    'docs/': 'a document; /docs/{slug}/ is a fixed narrative route', 'LICENSES/': 'a licence text',
    'taxonomy/_corpus/': 'a classification record', 'taxonomy/_failures/': 'a tag-gap record',
    'README.md': 'a repository document', 'CONTRIBUTING.md': 'a repository document',
    'CHANGELOG.md': 'a repository document', 'CODE_OF_CONDUCT.md': 'a repository document',
    'GOVERNANCE.md': 'a repository document', 'SECURITY.md': 'a repository document',
    'SUCCESSION.md': 'a repository document', 'LICENSE-CODE': 'a licence text', 'LICENSE-DATA': 'a licence text',
    'REUSE.toml': 'licence metadata', '.gitignore': 'git configuration', '.gitattributes': 'git configuration',
    'package.json': 'the repository-root e2e harness', 'package-lock.json': 'the repository-root e2e harness',
    'playwright.config.ts': 'the repository-root e2e harness',
}
# A changed path every route may read: prefix -> why. Checked after NO_ROUTE, whose entries are more specific.
ALL_ROUTES = {
    'taxonomy/': 'a vocabulary change re-renders everything (08 S3.3)',
    'schema/': 'a schema change re-renders everything (08 S3.3)',
    'site/': 'a template, style or site library change re-renders every route (08 S3.3)',
    'design/': 'the design tokens are on every page', 'tools/': 'a build tool can change any artifact',
    'CITATION.cff': "every page's citation block reads it", 'pyproject.toml': 'the toolchain', 'uv.lock': 'the toolchain',
}


# ---- --data-only ---------------------------------------------------------------------------------------------------

def clear(out_dir: str) -> list[str]:
    """Remove the S9 outputs a previous full build left in `out_dir`; the paths removed."""
    removed = []
    for name in S9_OUTPUTS:
        path = os.path.join(out_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
        else:
            continue
        removed.append(path)
    return removed


# ---- BENCH_ROUTES --------------------------------------------------------------------------------------------------

def normalise(route: str) -> str:
    """A route as the filter compares it: rooted, and ending in `/` unless its last segment names a file."""
    route = '/' + route.strip().lstrip('/')
    return route if route.endswith('/') or '.' in route.rsplit('/', 1)[-1] else route + '/'


def main_build(env) -> bool:
    """A build of main itself, which renders everything whatever BENCH_ROUTES says (bench-routes.ts mainBuild)."""
    return env.get('GITHUB_REF') == MAIN_REF and env.get('GITHUB_EVENT_NAME') in MAIN_EVENTS


def bench_routes(env=os.environ) -> list[str] | None:
    """The routes BENCH_ROUTES restricts a site build to, sorted; None when the build renders everything."""
    text = env.get('BENCH_ROUTES')
    if text is None or main_build(env):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return None if EVERYTHING in lines else sorted({normalise(line) for line in lines})


def covers(listed: list[str], route: str) -> bool:
    """Whether a site build restricted to `listed` renders `route` (narrative routes aside)."""
    route = normalise(route)
    return any(route == r or (r.endswith('/') and route.startswith(r)) for r in listed)


def published_routes(corpus: dict) -> set[str]:
    """The page of every published record that has one."""
    return {pattern % rec['id'] for kind, pattern in ENTITY_ROUTES.items() for rec in corpus['entities'][kind]}


def note(env, corpus: dict) -> str | None:
    """`bench build`'s line about BENCH_ROUTES, when it is set: what the site build will render."""
    if env.get('BENCH_ROUTES') is None:
        return None
    if main_build(env):
        return 'BENCH_ROUTES: ignored, because this is a build of main, which renders every route'
    listed = bench_routes(env)
    if listed is None:
        return 'BENCH_ROUTES: every route'
    pages = published_routes(corpus)
    family = tuple(p.split('%s')[0] for p in ENTITY_ROUTES.values())
    unpublished = [r for r in listed if r.startswith(family) and not any(covers([r], p) for p in pages)]
    return ('BENCH_ROUTES: the site build renders %d listed route(s)%s and the fixed narrative routes '
            '(site/src/lib/bench-routes.ts)%s'
            % (len(listed), ' (%s)' % ', '.join(listed) if 0 < len(listed) <= 5 else '',
               '; no record this build publishes is at %s' % ', '.join(unpublished) if unpublished else ''))


# ---- the entity-to-route map ---------------------------------------------------------------------------------------

@dataclass
class Plan:
    """What a diff renders: `everything`, or `routes`; `why` says, per changed path, what it added and why."""
    everything: bool = False
    routes: set[str] = field(default_factory=set)
    why: list[tuple[str, str]] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [EVERYTHING] if self.everything else sorted(self.routes)


class Tree:
    """The repository as a diff sees it: `read` a record at head (or, for a deleted file, at the merge base), and
    `naming` lists the files at head under a directory whose text holds a string. Here the working tree is head;
    GitTree, which scripts/routes_from_diff.py uses, reads any two commits."""

    def __init__(self, root: str):
        self.root = root

    def text(self, rel: str) -> str | None:
        path = os.path.join(self.root, *rel.split('/'))
        if not os.path.exists(path):
            return None
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def read(self, rel: str):
        from ruamel.yaml import YAML
        text = self.text(rel)
        try:
            return YAML(typ='safe').load(text) if text is not None else None       # schema.taxonomy.read_yaml's loader
        except Exception:                       # a file that does not parse is tier 1's to report; it has no route
            return None

    def naming(self, needle: str, directory: str) -> list[str]:
        out = []
        for folder, dirs, names in os.walk(os.path.join(self.root, *directory.rstrip('/').split('/'))):
            dirs.sort()
            for n in sorted(names):
                if n.endswith('.yaml'):
                    rel = os.path.relpath(os.path.join(folder, n), self.root).replace(os.sep, '/')
                    if needle in (self.text(rel) or ''):
                        out.append(rel)
        return out


def _prefixed(path: str, table: dict[str, str]) -> str | None:
    for prefix, why in table.items():
        if path == prefix or (prefix.endswith('/') and path.startswith(prefix)):
            return why
    return None


def _claim_routes(raw, pages: set[str]) -> list[str]:
    out = []
    if isinstance(raw, dict):
        for key, pattern in (('benchmark', ENTITY_ROUTES['benchmark']), ('system', ENTITY_ROUTES['system'])):
            ref = raw.get(key)
            if isinstance(ref, str) and pattern % ref.split('@', 1)[0] in pages:
                out.append(pattern % ref.split('@', 1)[0])
    return out


def plan(changed: list[str], corpus: dict, tree: Tree) -> Plan:
    """Map changed root-relative paths through the entity-to-route map (module docstring), against `corpus`, the
    corpus.json the head commit publishes."""
    from tools.build import artifacts
    from tools.validate import tiers
    pages = published_routes(corpus)
    citers: dict[str, set[str]] = {}
    for kind, pattern in ENTITY_ROUTES.items():
        for rec in corpus['entities'][kind]:
            for sid in artifacts.cited_sources(rec):
                citers.setdefault(sid, set()).add(pattern % rec['id'])
    out = Plan()

    def add(path: str, routes, why: str):
        routes = sorted(set(routes))
        out.routes.update(routes)
        out.why.append((path, '%s: %s' % (', '.join(routes), why) if routes else why))

    for path in sorted(set(changed)):
        stem = path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        kind = tiers.kind_of(path) if path.startswith('data/') else None
        name = kind.name if kind else None
        if name in ENTITY_ROUTES:
            route = ENTITY_ROUTES[name] % stem
            add(path, [route] if route in pages else [], 'its page' if route in pages
                else 'no page: the commit does not publish %s %s' % (name, stem))
        elif name == 'source':
            add(path, citers.get(stem, ()), 'the pages that cite it' if stem in citers  # get-default: an uncited source has no citing page
                else 'no published record cites it')
        elif name == 'claim':
            add(path, _claim_routes(tree.read(path), pages), "its benchmark's and its system's pages")
        elif name == 'conditions':
            claims = tree.naming(stem, 'data/claims/')
            add(path, [r for c in claims for r in _claim_routes(tree.read(c), pages)],
                'the pages of the %d claim(s) that name it' % len(claims))
        elif path.startswith('data/'):
            add(path, [], 'no page renders %s record' % ('a %s' % name if name else 'this'))
        elif _prefixed(path, NO_ROUTE):
            add(path, [], _prefixed(path, NO_ROUTE))
        else:
            out.everything = True
            out.why.append((path, 'every route: %s' % (_prefixed(path, ALL_ROUTES)
                                                       or 'the map does not place it, so everything renders')))
    return out


class GitTree(Tree):
    """`read` at head, else at the merge base of base and head; `naming` at head. Read-only git."""

    def __init__(self, root: str, base: str, head: str):
        super().__init__(root)
        self.base, self.head = base, head
        self.merge_base = self.git('merge-base', base, head).strip()

    def git(self, *args: str) -> str:
        return subprocess.run(['git', '-c', 'core.longpaths=true', *args], cwd=self.root, capture_output=True,
                              text=True, encoding='utf-8', check=True).stdout

    def changed(self) -> list[str]:
        """`git diff --name-only <base>...<head>`, renames as a deletion and an addition so both paths are mapped."""
        out = self.git('diff', '--name-only', '--no-renames', '%s...%s' % (self.base, self.head))
        return [p for p in out.splitlines() if p]

    def text(self, rel: str) -> str | None:
        for ref in (self.head, self.merge_base):
            r = subprocess.run(['git', 'show', '%s:%s' % (ref, rel)], cwd=self.root, capture_output=True, text=True,
                               encoding='utf-8')
            if r.returncode == 0:
                return r.stdout
        return None

    def naming(self, needle: str, directory: str) -> list[str]:
        r = subprocess.run(['git', 'grep', '-l', '-F', needle, self.head, '--', directory], cwd=self.root,
                           capture_output=True, text=True, encoding='utf-8')
        if r.returncode not in (0, 1):                  # 1: no file holds it
            raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
        return sorted(line.split(':', 1)[1] for line in r.stdout.splitlines() if line.endswith('.yaml'))
