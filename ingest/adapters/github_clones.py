#!/usr/bin/env python3
"""The harness and MTEB shallow-clone ingest (P5-S5-T02; 06 S3.3, 07 S1.2).

    python -m ingest.adapters.github_clones --fixture tests/ingest/fixtures/harness     # offline
    python -m ingest.adapters.github_clones                                             # live: the pinned commits
    bench ingest lm-eval-harness --dry-run [--fixture PATH]
    bench ingest mteb-results --dry-run [--fixture PATH]

06 S3.3: "The clone targets matter more than the API." Two of its three are here, each a BulkArchiveAdapter (07
S1.2): one fetch of a pinned commit, then N logical records read out of git's object store.

    lm-eval-harness   EleutherAI/lm-evaluation-harness, MIT. Every task YAML under lm_eval/tasks/<dir>/ is a
                      Candidate; its eval conditions are mapped (below) when its dataset is one we catalogue.
    mteb-results      embeddings-benchmark/results, CC0-1.0. Every result JSON under results/<model>/<revision>/ is
                      enumerated, with the model, revision and task its path names. Mapping MTEB scores to claims is
                      not this task's: the report says which tasks and how many results there are.

inspect_evals, the third clone target, is not built here: the task names two.

The fetch. A bare repository under ingest/raw/clones/ (gitignored; 07 S4 layer 3, "actions/cache for bulky
regenerable artefacts"), then `git fetch --depth 1` of the pinned commit -- GitHub serves any reachable commit by
id. Nothing is checked out: a checkout of the harness on Windows fails on its long paths, and reading the object
store (`ls-tree`, `cat-file --batch`) needs no working tree at all. The MTEB fetch is blob-less
(`--filter=blob:none`): enumerating needs the tree, about 3 MB, not 06 S3.3's ~600 MB of JSON. Its LICENSE is the
one blob fetched, by id. Lazy fetching is switched off for every git call (GIT_NO_LAZY_FETCH), so a blob the run
did not fetch is a missing object, never a silent request.

The gate. A git fetch is two requests to github.com, `GET <repo>/info/refs?service=git-upload-pack` and `POST
<repo>/git-upload-pack`; the gate admits both before git runs (ingest/policy.yaml lists github.com). GitHub's
robots.txt (read 2026-10-09) disallows `/*.git$`, `*/tarball/`, `*/zipball/`, `/*/archive/` and `/*/raw/` for
every agent, and neither smart-HTTP endpoint, so the clone URL carries no `.git` suffix and archives are never
downloaded. If GitHub disallows the endpoints, the gate refuses and the run stops.

The layout is asserted, never globbed (06 S3.3, "A clone target that changes its directory layout is a hard fail:
assert the layout, do not glob hopefully"). Each check below is a DriftError -- a hard fail that commits nothing
and opens adapter-broken (ingest/gates/drift.py) -- raised before a single candidate is handed out:

    harness   LICENSE.md is the MIT licence; lm_eval/tasks/ is a tree holding __init__.py (the TaskManager
              package); no task config lies at its top level; at least 200 task directories (06 S3.3 counted
              227; the pinned commit holds 221); every directory holds at least one task config; task names are
              unique (they are the source keys)
    mteb      LICENSE is CC0 1.0; results/ is a tree; every file under it is results/<org>__<model>/<revision>/<file>
              or results/<org>__<model>/<revision>/experiments/<variant>/<file>; at least 10 models

A task YAML is read as the harness reads it (lm_eval/tasks/_yaml_loader.py at the pin): `!function mod.fn` is kept as
the pointer "!function mod.fn" and never imported or run; `include:` (a path or a list, relative to the including
file) is loaded first and the file's own keys win; an include's task_list is dropped. A config that will not parse,
or whose include is missing, escapes lm_eval/tasks or cycles, is an Unresolved for that task, not drift.

The mapping (06 S3.3: "Harness YAML maps directly"), into one discovery candidate per task under
data/_discovery/lm-eval-harness/ (06 S1.1's shape), for a task whose dataset_path is a catalogued benchmark's
external id (04 S10 step 1, or an alias record, step 2; never a fuzzy name match: `arc` is AI2's, not ARC-AGI):

    num_fewshot                  _suggested eval_conditions.shots
    fewshot_config.sampler       _suggested eval_conditions.shot_selection: first_n is fixed, default is random
    generation_kwargs            _suggested eval_conditions.sampling.temperature, .top_p; max_gen_toks is
                                 eval_conditions.max_output_tokens
    repeats                      _suggested eval_conditions.n_samples
    (the harness itself)         _suggested eval_conditions.harness and execution.runnable_via: lm_eval
    output_type                  identity.output_type. 06 S3.3 maps it to EvalConditions.output_mode, which the
                                 schema (schema/conditions.py) does not have, so it is kept as the harness's fact
    metric_list                  identity.metrics: metric, aggregation, higher_is_better (Metric candidates)
    dataset_path, dataset_name   identity.dataset: the HF id the benchmark was matched on, its config and splits
    doc_to_text                  identity.prompt_template: a pointer (the config's URL at the pin and the key),
                                 never the template, "because the template is the repo's own copyrighted work"

Nothing is defaulted: a key the config does not state is not suggested. A task whose dataset we do not catalogue
gets no draft; the report counts them per task directory and dataset, which is the discovery signal (06 S8.1's
"1,200-1,800 candidates" come through intake's throttle, not from here).

Change classes. A bundle is unchanged -- fetch_bundle() returns None -- when the commit and the adapter version are
the ones the state last saw: the pin moves only by a reviewed change to PINS. Per task, the sha256 of its merged
config decides new, field-change or no-change; a task the state holds that the commit lacks is counted gone.
`--follow` fetches the default branch's head instead of the pin, to see what a pin bump would bring.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import posixpath  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from collections import Counter  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from ingest.adapters.base import BulkArchiveAdapter, Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.gates import drift  # noqa: E402
from ingest.http import policy  # noqa: E402

VERSION = '0.1.0'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLONES = os.path.join(ROOT, 'ingest', 'raw', 'clones')
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')
SchemaDrift = drift.DriftError


@dataclass(frozen=True)
class Target:
    """One clone target: where it is, the commit it is pinned to, and whether its blobs are fetched."""
    name: str
    repo: str                       # owner/name on github.com
    pin: str                        # the commit a run fetches unless --follow
    pinned_on: str                  # when the pin was read (the commit's own date is in the state)
    blobs: bool                     # False: a blob-less fetch; only the licence file's blob is fetched by id
    licence: str
    licence_file: str
    licence_marker: str             # a line the licence file must hold: the licence is a veto (06 S1.2)

    @property
    def url(self) -> str:
        return 'https://github.com/%s' % self.repo           # no `.git`: robots.txt disallows /*.git$

    def blob_url(self, commit: str, path: str) -> str:
        return 'https://github.com/%s/blob/%s/%s' % (self.repo, commit, path)


# The pins. Moving one is a reviewed change: run with --follow, read the report, then edit it here.
HARNESS = Target('lm-eval-harness', 'EleutherAI/lm-evaluation-harness', 'd6de81643928d653435c431bae19945d41d32520',
                 '2026-10-09', True, 'MIT', 'LICENSE.md', 'MIT License')
MTEB = Target('mteb-results', 'embeddings-benchmark/results', 'b64a5db97dfb2056207a1bc89bec0b759e169b39',
              '2026-10-09', False, 'CC0-1.0', 'LICENSE', 'CC0 1.0 Universal')
PINS = {t.name: t for t in (HARNESS, MTEB)}

TASKS_ROOT = 'lm_eval/tasks'
TASKS_MARKER = TASKS_ROOT + '/__init__.py'
MIN_TASK_DIRS = 200                 # the done_when; 06 S3.3 counted 227, the pin holds 221
IGNORED_DIRS = frozenset({'__pycache__', '.ipynb_checkpoints'})    # the harness's own _IGNORE_DIRS
MTEB_ROOT = 'results'
MIN_MODELS = 10
MODEL_DIR = re.compile(r'^[^/]+__[^/]+$')
SHOT_SELECTION = {'first_n': 'fixed', 'default': 'random'}
HARNESS_ATTRIBUTION = ('Gao et al., A framework for few-shot language model evaluation (lm-evaluation-harness), '
                       'EleutherAI, doi:10.5281/zenodo.10256836, MIT')
MTEB_ATTRIBUTION = ('MTEB results, embeddings-benchmark/results, https://github.com/embeddings-benchmark/results, '
                    'CC0-1.0')
DISCOVERY = 'data/_discovery/%s' % HARNESS.name


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     default=str).encode('utf-8')).hexdigest()


# ---- git, without a shell, a working tree or a lazy fetch ----------------------------------------------------

class GitError(Exception):
    """git failed: a fetch the network refused, or an object store that is not what the run expects."""


GIT_ENV = {'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0', 'GIT_ASKPASS': '', 'SSH_ASKPASS': ''}
GIT_CONFIG = ('-c', 'core.autocrlf=false', '-c', 'credential.helper=', '-c', 'protocol.version=2',
              '-c', 'core.longpaths=true')


def git(repo: str, *args: str, input: bytes | None = None) -> bytes:
    env = {**os.environ, **GIT_ENV}
    r = subprocess.run(['git', *GIT_CONFIG, '-C', repo, *args], input=input, capture_output=True, env=env)
    if r.returncode:
        raise GitError('git %s: %s' % (' '.join(args[:3]), r.stderr.decode('utf-8', 'replace').strip()[:400]))
    return r.stdout


def admit_fetch(gate, target: Target) -> None:
    """The two requests a smart-HTTP fetch makes, asked of the gate before git makes them."""
    gate.admit(target.url + '/info/refs?service=git-upload-pack')
    gate.admit(target.url + '/git-upload-pack')


def shallow_fetch(target: Target, dest: str, gate=None, ref: str | None = None) -> str:
    """Fetch `ref` (default the pin) at depth 1 into the bare repository `dest`; return the commit id. A blob-less
    target gets its licence file's blob by id, in a second gated fetch."""
    gate = gate or policy.gate()
    if not os.path.isdir(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        git(os.path.dirname(dest), 'init', '--bare', '--quiet', os.path.basename(dest))
        git(dest, 'remote', 'add', 'origin', target.url)
        if not target.blobs:
            git(dest, 'config', 'remote.origin.promisor', 'true')
            git(dest, 'config', 'remote.origin.partialclonefilter', 'blob:none')
    want = ref or target.pin
    admit_fetch(gate, target)
    git(dest, 'fetch', '--depth', '1', '--no-tags', '--quiet', *(() if target.blobs else ('--filter=blob:none',)),
        'origin', want)
    commit = git(dest, 'rev-parse', 'FETCH_HEAD^{commit}').decode().strip()
    if not target.blobs:
        fetch_blobs(target, dest, [git(dest, 'rev-parse', '%s:%s' % (commit, target.licence_file)).decode().strip()],
                    gate)
    return commit


def fetch_blobs(target: Target, dest: str, blob_ids: list[str], gate=None) -> None:
    """Fetch named blobs into a blob-less repository: one gated fetch for all of them."""
    if not blob_ids:
        return
    admit_fetch(gate or policy.gate(), target)
    git(dest, 'fetch', '--no-tags', '--quiet', '--no-write-fetch-head', '--filter=blob:none', 'origin', *blob_ids)


def repo_from_directory(src: str, dest: str) -> str:
    """A one-commit repository holding the files under `src`, byte for byte; returns the commit id. The fixture's
    route into the same reader the live clone uses. Author, committer and dates are fixed, so the id is too."""
    git(os.path.dirname(dest) or '.', 'init', '--quiet', os.path.basename(dest))
    work = ['--git-dir', os.path.join(dest, '.git'), '--work-tree', src]
    git(dest, *work, 'add', '--all', '.')
    stamp = '2026-10-09T00:00:00+00:00'
    env_args = ['-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid', '-c', 'commit.gpgsign=false']
    r = subprocess.run(['git', *GIT_CONFIG, *env_args, '-C', dest, *work, 'commit', '--quiet', '-m', 'fixture'],
                       capture_output=True, env={**os.environ, **GIT_ENV, 'GIT_AUTHOR_DATE': stamp,
                                                 'GIT_COMMITTER_DATE': stamp})
    if r.returncode:
        raise GitError('git commit: %s' % r.stderr.decode('utf-8', 'replace').strip()[:400])
    return git(dest, 'rev-parse', 'HEAD').decode().strip()


class Tree:
    """One commit's tree, read from the object store: every entry once, blobs on request."""

    def __init__(self, repo: str, commit: str):
        self.repo, self.commit = repo, commit
        self.entries = {}                                  # path -> (type, object id)
        for rec in git(repo, 'ls-tree', '-r', '-t', '-z', '--full-tree', commit).split(b'\0'):
            if rec:
                meta, path = rec.split(b'\t', 1)
                _, typ, oid = meta.decode().split()
                self.entries[path.decode('utf-8')] = (typ, oid)
        self._blobs: dict[str, bytes] = {}

    def is_tree(self, path: str) -> bool:
        return self.entries.get(path, (None,))[0] == 'tree'   # get-default: an absent path is not a tree

    def is_blob(self, path: str) -> bool:
        return self.entries.get(path, (None,))[0] == 'blob'   # get-default: an absent path is not a blob

    def blobs_under(self, prefix: str) -> list[str]:
        return sorted(p for p, (t, _) in self.entries.items() if t == 'blob' and p.startswith(prefix + '/'))

    def children(self, prefix: str) -> list[tuple[str, str]]:
        """(name, type) of the entries directly under `prefix`."""
        depth = prefix.count('/') + 1
        return sorted((p.rsplit('/', 1)[1], t) for p, (t, _) in self.entries.items()
                      if p.startswith(prefix + '/') and p.count('/') == depth)

    def read(self, paths) -> dict[str, bytes]:
        """The blobs at `paths`, in one `cat-file --batch`. A blob the store lacks (a blob-less fetch) is an
        error, never a lazy fetch."""
        want = [p for p in paths if p not in self._blobs]
        if want:
            ids = [self.entries[p][1] for p in want]
            out = git(self.repo, 'cat-file', '--batch', input=''.join(i + '\n' for i in ids).encode())
            i = 0
            for p, oid in zip(want, ids):
                end = out.index(b'\n', i)
                head = out[i:end].split()
                if len(head) != 3 or head[1] != b'blob':
                    raise GitError('%s (%s) is not in the object store: %s' % (p, oid, out[i:end].decode()))
                size = int(head[2])
                self._blobs[p] = out[end + 1:end + 1 + size]
                i = end + 1 + size + 1
        return {p: self._blobs[p] for p in paths}

    def listing_sha256(self) -> tuple[str, int]:
        """The tree as a canonical listing (path, type, id per line, sorted): its sha256 and its length."""
        body = ''.join('%s %s %s\n' % (p, t, o) for p, (t, o) in sorted(self.entries.items())).encode('utf-8')
        return hashlib.sha256(body).hexdigest(), len(body)


# ---- reading a task YAML the way the harness does --------------------------------------------------------------

class _Loader(yaml.SafeLoader):
    pass


def _function(loader, node):
    return '!function %s' % loader.construct_scalar(node)


_Loader.add_constructor('!function', _function)


def load_config(text: str):
    return yaml.load(text, Loader=_Loader)   # noqa: S506 -- a SafeLoader subclass: !function becomes a string


class ConfigError(Exception):
    """One task config that will not load: a per-task Unresolved, not drift."""


class Harness:
    """The task tree at one commit, parsed once."""

    def __init__(self, tree: Tree):
        self.tree = tree
        # What the harness indexes is *.yaml; an include may name any file (_default_template_yaml, _gen_yaml_2shot),
        # so those are read when a config names them.
        self.files = [p for p in tree.blobs_under(TASKS_ROOT) if p.endswith('.yaml')]
        self.text, self.raw, self.errors = {}, {}, {}
        self._load(self.files)

    def _load(self, paths) -> None:
        for p, b in self.tree.read(paths).items():
            self.text[p] = b.decode('utf-8')
            try:
                self.raw[p] = load_config(self.text[p])
            except yaml.YAMLError as e:
                self.errors[p] = 'YAML does not parse: %s' % ' '.join(str(e).split())[:200]

    def includes_read(self) -> list[str]:
        return sorted(p for p in self.text if not p.endswith('.yaml'))

    def task_configs(self) -> list[str]:
        """The files the harness indexes as tasks: *.yaml whose own `task` is a name (a list is a group)."""
        return [p for p in self.files if isinstance(self._doc(p).get('task'), str)]

    def group_configs(self) -> list[str]:
        return [p for p in self.files if isinstance(self._doc(p).get('task'), list)]

    def _doc(self, path: str) -> dict:
        doc = self.raw.get(path)              # get-default: a file that did not parse is neither task nor group
        return doc if isinstance(doc, dict) else {}

    def merged(self, path: str, stack: tuple = ()) -> tuple[dict, list[str]]:
        """(config, include chain) per _yaml_loader.load_yaml: includes first, in order, then the file's keys."""
        if path in stack:
            raise ConfigError('include cycle: %s' % ' -> '.join(stack + (path,)))
        if path not in self.text and self.tree.is_blob(path):
            self._load([path])
        if path in self.errors:
            raise ConfigError('%s: %s' % (path, self.errors[path]))
        if path not in self.raw:
            raise ConfigError('include %s is not in the tree' % path)
        cfg = self.raw[path]
        if not isinstance(cfg, dict):
            raise ConfigError('%s is not a mapping (%s)' % (path, type(cfg).__name__))
        cfg = dict(cfg)
        if 'include' not in cfg:
            return cfg, []
        includes = cfg.pop('include')
        merged, chain = {}, []
        for inc in includes if isinstance(includes, list) else [includes]:
            if not isinstance(inc, str):
                raise ConfigError('%s: include %r is not a path' % (path, inc))
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), inc))
            if not target.startswith(TASKS_ROOT + '/'):
                raise ConfigError('%s: include %s leaves %s' % (path, inc, TASKS_ROOT))
            sub, subchain = self.merged(target, stack + (path,))
            sub.pop('task_list', None)
            merged.update(sub)
            chain += subchain + [target]
        merged.update(cfg)
        return merged, chain


def task_dir(path: str) -> str:
    return path.split('/')[2]


def check_harness(tree: Tree, previous: int | None = None) -> Harness:
    """The layout 06 S3.3 says to assert. DriftError, before any candidate, when it does not hold."""
    if not tree.is_blob(HARNESS.licence_file):
        raise SchemaDrift('%s: %s is gone; the licence is a veto (06 S1.2)' % (HARNESS.repo, HARNESS.licence_file))
    if HARNESS.licence_marker not in tree.read([HARNESS.licence_file])[HARNESS.licence_file].decode('utf-8', 'replace'):
        raise SchemaDrift('%s: %s no longer says %r' % (HARNESS.repo, HARNESS.licence_file, HARNESS.licence_marker))
    if not tree.is_tree(TASKS_ROOT):
        raise SchemaDrift('%s: %s/ is not a directory; the task tree moved' % (HARNESS.repo, TASKS_ROOT))
    if not tree.is_blob(TASKS_MARKER):
        raise SchemaDrift('%s: %s is gone; %s/ is no longer the TaskManager package'
                          % (HARNESS.repo, TASKS_MARKER, TASKS_ROOT))
    loose = [n for n, t in tree.children(TASKS_ROOT) if t == 'blob' and n.endswith('.yaml')]
    if loose:
        raise SchemaDrift('%s: task configs at the top of %s/ (%s): the layout is <dir>/<task>.yaml'
                          % (HARNESS.repo, TASKS_ROOT, ', '.join(loose[:5])))
    dirs = [n for n, t in tree.children(TASKS_ROOT) if t == 'tree' and n not in IGNORED_DIRS]
    drift.rows(drift.Expect('%s task directories' % HARNESS.repo, min_rows=MIN_TASK_DIRS), dirs, previous)
    h = Harness(tree)
    configs = h.task_configs()
    have = {task_dir(p) for p in configs + h.group_configs()}       # benchmarks/ holds groups only (pythia, ...)
    empty = [d for d in dirs if d not in have]
    if empty:
        raise SchemaDrift('%s: %d task director%s hold%s no task or group config: %s' % (
            HARNESS.repo, len(empty), 'y' if len(empty) == 1 else 'ies', 's' if len(empty) == 1 else '',
            ', '.join(empty[:8])))
    names = Counter(h.raw[p]['task'] for p in configs)
    dups = sorted(n for n, k in names.items() if k > 1)
    if dups:
        raise SchemaDrift('%s: task names are no longer unique (%s); they are the source keys'
                          % (HARNESS.repo, ', '.join(dups[:5])))
    return h


def check_mteb(tree: Tree, previous: int | None = None) -> list[dict]:
    """MTEB's layout, asserted; returns one record per result JSON."""
    if not tree.is_blob(MTEB.licence_file):
        raise SchemaDrift('%s: %s is gone; the licence is a veto (06 S1.2)' % (MTEB.repo, MTEB.licence_file))
    if MTEB.licence_marker not in tree.read([MTEB.licence_file])[MTEB.licence_file].decode('utf-8', 'replace'):
        raise SchemaDrift('%s: %s no longer says %r' % (MTEB.repo, MTEB.licence_file, MTEB.licence_marker))
    if not tree.is_tree(MTEB_ROOT):
        raise SchemaDrift('%s: %s/ is not a directory; the results tree moved' % (MTEB.repo, MTEB_ROOT))
    out, odd = [], []
    for p in tree.blobs_under(MTEB_ROOT):
        parts = p.split('/')
        if len(parts) == 2 and not parts[1].endswith('.json'):
            continue                          # a maintainer's script beside the models (rename_and_move_over.py)
        if len(parts) == 4 and MODEL_DIR.match(parts[1]):
            variant = None
        elif len(parts) == 6 and MODEL_DIR.match(parts[1]) and parts[3] == 'experiments':
            variant = parts[4]
        else:
            odd.append(p)
            continue
        name = parts[-1]
        if name.endswith('.json') and name != 'model_meta.json':
            out.append({'path': p, 'model': parts[1].replace('__', '/', 1), 'revision': parts[2],
                        'variant': variant, 'task': name[:-len('.json')]})
    if odd:
        raise SchemaDrift('%s: %d file%s outside results/<org>__<model>/<revision>/: %s' % (
            MTEB.repo, len(odd), '' if len(odd) == 1 else 's', ', '.join(odd[:5])))
    models = sorted({r['model'] for r in out})
    drift.rows(drift.Expect('%s models with results' % MTEB.repo, min_rows=MIN_MODELS), models, previous)
    return out


# ---- the bundles ---------------------------------------------------------------------------------------------

class CloneBundle:
    """One fetched commit of one target: its tree, the citable handle, and the state the layout check took."""

    def __init__(self, target: Target, tree: Tree, retrieved_at: datetime, cites: str | None = None):
        self.target, self.tree, self.retrieved_at = target, tree, retrieved_at
        # The commit every URL and the state name: the one fetched, or for a fixture the pin it is a pruned copy
        # of (its own one-commit repository's id exists nowhere upstream). tree.commit is what is read.
        self.commit = cites or tree.commit
        self.sha256, self.bytes = tree.listing_sha256()

    def snapshot(self) -> dict:
        """The IngestBatch `source` block (04 S9): the commit, and the sha256 of its canonical tree listing."""
        return {'name': self.target.repo, 'url': self.target.url, 'retrieved_at': iso(self.retrieved_at),
                'commit': self.commit, 'artefact_sha256': self.sha256, 'artefact_bytes': self.bytes}


class HarnessBundle(CloneBundle):
    def __init__(self, tree: Tree, retrieved_at: datetime, previous: int | None = None, cites: str | None = None):
        super().__init__(HARNESS, tree, retrieved_at, cites)
        self.harness = check_harness(tree, previous)
        self.configs = self.harness.task_configs()

    def counts(self) -> dict[str, int]:
        h = self.harness
        return {'task_dirs': len({task_dir(p) for p in self.configs}), 'task_configs': len(self.configs),
                'group_configs': len(h.group_configs()), 'yaml_files': len(h.files), 'unparseable': len(h.errors)}

    def payload_for(self, candidate: Candidate) -> Payload:
        """The merged config of one task, with no network. The hash is of the merged config, so a template edit
        that changes what a task means changes its hash, and a comment-only edit does not."""
        path = candidate.hint['path']
        try:
            cfg, chain = self.harness.merged(path)
            error = None
        except ConfigError as e:
            cfg, chain, error = None, [], str(e)
        doc = {'path': path, 'task': candidate.source_key.split(':', 1)[1], 'task_dir': task_dir(path),
               'commit': self.commit, 'config': cfg, 'includes': chain, 'error': error}
        return Payload(candidate=candidate, body=self.harness.text[path].encode('utf-8'),
                       content_type='application/yaml', http_status=200, fetched_at=self.retrieved_at, etag=None,
                       last_modified=None, sha256_normalised=sha256_json({'config': cfg, 'error': error}),
                       from_cache=False, doc=doc)


class MtebBundle(CloneBundle):
    def __init__(self, tree: Tree, retrieved_at: datetime, previous: int | None = None, cites: str | None = None):
        super().__init__(MTEB, tree, retrieved_at, cites)
        self.results = check_mteb(tree, previous)

    def counts(self) -> dict[str, int]:
        r = self.results
        return {'models': len({x['model'] for x in r}),
                'model_revisions': len({(x['model'], x['revision']) for x in r}), 'result_files': len(r), 'tasks': len({x['task'] for x in r}),
                'experiment_results': sum(1 for x in r if x['variant'])}

    def payload_for(self, candidate: Candidate) -> Payload:
        """What the path says: the result's model, revision, variant and task. The JSON itself is not read."""
        doc = dict(candidate.hint)
        return Payload(candidate=candidate, body=b'', content_type='application/json', http_status=200,
                       fetched_at=self.retrieved_at, etag=None, last_modified=None, sha256_normalised=sha256_json(doc),
                       from_cache=False, doc=doc)


# ---- the mapping ---------------------------------------------------------------------------------------------

def _int(v, low: int) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= low else None


def _num(v) -> float | None:
    return round(float(v), 6) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def suggestions(cfg: dict) -> tuple[list[tuple[str, object, str]], list[tuple[str, object]]]:
    """(field, value, rationale) for each condition the config states, and (key, value) for each it states in a
    form the mapping cannot read. Nothing absent is suggested."""
    out, bad = [], []
    shots = cfg.get('num_fewshot')
    if shots is not None:
        if _int(shots, 0) is None:
            bad.append(('num_fewshot', shots))
        else:
            out.append(('eval_conditions.shots', shots, 'num_fewshot'))
    fc = cfg.get('fewshot_config')
    sampler = fc.get('sampler') if isinstance(fc, dict) else None
    if sampler in SHOT_SELECTION:
        out.append(('eval_conditions.shot_selection', SHOT_SELECTION[sampler], 'fewshot_config.sampler: %s' % sampler))
    gk = cfg.get('generation_kwargs')
    if isinstance(gk, dict):
        for key, field in (('temperature', 'eval_conditions.sampling.temperature'),
                           ('top_p', 'eval_conditions.sampling.top_p')):
            if key in gk:
                v = _num(gk[key])
                if v is None or (key == 'top_p' and not 0 < v <= 1):
                    bad.append(('generation_kwargs.%s' % key, gk[key]))
                else:
                    out.append((field, v, 'generation_kwargs.%s' % key))
        if 'max_gen_toks' in gk:
            if _int(gk['max_gen_toks'], 1) is None:
                bad.append(('generation_kwargs.max_gen_toks', gk['max_gen_toks']))
            else:
                out.append(('eval_conditions.max_output_tokens', gk['max_gen_toks'], 'generation_kwargs.max_gen_toks'))
    reps = cfg.get('repeats')
    if reps is not None:
        if _int(reps, 1) is None:
            bad.append(('repeats', reps))
        else:
            out.append(('eval_conditions.n_samples', reps, 'repeats'))
    return out, bad


def _pointer(v) -> dict | None:
    """What kind of thing doc_to_text is, never what it says."""
    if v is None:
        return None
    if isinstance(v, str) and v.startswith('!function '):
        return {'kind': 'function', 'ref': v[len('!function '):]}
    if isinstance(v, str) and '{{' in v:
        return {'kind': 'template'}
    return {'kind': 'field' if isinstance(v, str) else type(v).__name__}


def _metrics(cfg: dict) -> list[dict]:
    out = []
    for m in cfg.get('metric_list') or []:
        if isinstance(m, dict) and 'metric' in m:
            agg, better = m.get('aggregation'), m.get('higher_is_better')
            out.append({'metric': str(m['metric']), 'aggregation': None if agg is None else str(agg),
                        'higher_is_better': better if isinstance(better, bool) else None})
    return out


def normalise_task(payload: Payload, resolvers: dict) -> tuple[list[Draft], list[Unresolved]]:
    """One discovery candidate for a task whose dataset is a catalogued benchmark, else nothing. Pure: the payload
    and the frozen resolvers only."""
    doc = payload.doc
    key, path = payload.candidate.source_key, doc['path']
    url = HARNESS.blob_url(doc['commit'], path)
    if doc['error']:
        return [], [Unresolved(key, 'config', path, 'unparseable',
                               human_task='%s at %s does not load as the harness loads it: %s. Read it; if the harness '
                                          'itself cannot load it, nothing is lost.' % (doc['task'], url, doc['error']))]
    cfg = doc['config']
    dataset = cfg.get('dataset_path')
    if not isinstance(dataset, str):
        return [], []
    hit = resolvers['benchmark'].resolve(dataset)
    if hit.entity is None or hit.step not in (1, 2):
        return [], []
    benchmark = hit.entity.split(':', 1)[1]
    fetched = iso(payload.fetched_at)
    found, bad = suggestions(cfg)
    found += [('eval_conditions.harness', 'lm-evaluation-harness', 'the harness this config belongs to'),
              ('execution.runnable_via', ['lm_eval'], 'lm-evaluation-harness task %s' % doc['task'])]

    def suggest(field, value, rationale):
        return {'field': field, 'value': value, 'adapter': HARNESS.name, 'adapter_version': VERSION, 'source_url': url,
                'fetched_at': fetched, 'confidence': hit.score,
                'rationale': '%s at %s (06 S3.3); the harness default, not what any run used'
                             % (rationale, doc['commit'][:12])}
    splits = {k: cfg.get('%s_split' % k) for k in ('training', 'validation', 'test', 'fewshot')}
    pointer = _pointer(cfg.get('doc_to_text'))
    body = {
        'candidate_id': candidate_id(doc['task']),
        'discovered_via': HARNESS.name,
        'discovered_at': fetched,
        'identity': {
            'benchmark': benchmark,
            'harness': 'lm-evaluation-harness',
            'repository': HARNESS.url,
            'commit': doc['commit'],
            'task': doc['task'],
            'task_dir': doc['task_dir'],
            'config_url': url,
            'includes': [HARNESS.blob_url(doc['commit'], p) for p in doc['includes']],
            'task_version': None if not isinstance(cfg.get('metadata'), dict) or cfg['metadata'].get('version') is None
            else str(cfg['metadata']['version']),
            'dataset': {'huggingface': dataset, 'config': None if cfg.get('dataset_name') is None else str(cfg['dataset_name']),
                        'splits': {k: None if v is None else str(v) for k, v in splits.items()}},
            'output_type': None if cfg.get('output_type') is None else str(cfg['output_type']),
            'metrics': _metrics(cfg),
            'prompt_template': None if pointer is None else {'source': url, 'key': 'doc_to_text', **pointer},
        },
        '_suggested': [suggest(f, v, r) for f, v, r in found],
    }
    unresolved = [Unresolved(key, 'config.%s' % k, repr(v), 'unparseable',
                             human_task='%s states %s as %r, which is not the type the harness documents; read %s and '
                                        'say what it means.' % (doc['task'], k, v, url)) for k, v in bad]
    ingestion = {'adapter': HARNESS.name, 'adapter_version': VERSION, 'source_url': url, 'fetched_at': fetched,
                 'sha256_normalised': payload.sha256_normalised, 'source_licence': HARNESS.licence,
                 'licence_class': 'permissive-attribution', 'source_attribution': HARNESS_ATTRIBUTION}
    return [Draft('conditions', None, Path(DISCOVERY) / ('%s.yaml' % body['candidate_id']), body, 'new', ingestion,
                  hit.score, labels=['ingest:%s' % HARNESS.name])], unresolved


def candidate_id(task: str) -> str:
    """gsm8k -> cand-harness-gsm8k: a discovery candidate's id, not an entity id."""
    return 'cand-harness-%s' % re.sub(r'[^a-z0-9]+', '-', task.lower()).strip('-')


# ---- the adapters --------------------------------------------------------------------------------------------

class _Clone(BulkArchiveAdapter):
    """fetch_bundle(): the one network step. `tree_source` replaces it: a callable returning (repo, commit, cites) --
    the repository, the commit to read in it, and the upstream commit it is a copy of -- which is how the fixture
    and the tests run the same reader offline."""

    target: Target
    expected_yield = (0, 50)
    tier = 1                                  # 06 S8.1: "GitHub metadata + harness clones", Tier 1

    def __init__(self, tree_source=None, gate=None, ref: str | None = None, clones: str = CLONES, now=utcnow):
        self.tree_source, self.gate, self.ref, self.clones, self.now = tree_source, gate, ref, clones, now
        self.bundle = None

    def fetch_bundle(self, state: dict):
        if self.tree_source is not None:
            repo, commit, cites = self.tree_source()
        else:
            repo = os.path.join(self.clones, self.target.name + '.git')
            commit = cites = shallow_fetch(self.target, repo, self.gate, self.ref)
        state['checked_at'] = iso(self.now())
        if cites == state.get('commit') and VERSION == state.get('adapter_version'):    # get-default: a cold run has neither
            return None
        return self.make_bundle(Tree(repo, commit), state, cites)


class HarnessClone(_Clone):
    name, version, licence, licence_class, attribution = HARNESS.name, VERSION, HARNESS.licence, 'permissive-attribution', HARNESS_ATTRIBUTION
    target = HARNESS
    volatile_fields = ()

    def make_bundle(self, tree, state, cites):
        return HarnessBundle(tree, self.now(), (state.get('counts') or {}).get('task_dirs'), cites)   # get-default: a cold run has no counts

    def enumerate(self, bundle: HarnessBundle):
        for p in bundle.configs:
            yield Candidate('harness:%s' % bundle.harness.raw[p]['task'], 'conditions',
                            HARNESS.blob_url(bundle.commit, p), {'path': p})

    def normalise(self, payload, resolver=None):
        return normalise_task(payload, resolver)


class MtebClone(_Clone):
    name, version, licence, licence_class, attribution = MTEB.name, VERSION, MTEB.licence, 'permissive-attribution', MTEB_ATTRIBUTION
    target = MTEB

    def make_bundle(self, tree, state, cites):
        return MtebBundle(tree, self.now(), (state.get('counts') or {}).get('models'), cites)        # get-default: as above

    def enumerate(self, bundle: MtebBundle):
        for r in bundle.results:
            yield Candidate('mteb:%s' % r['path'][len(MTEB_ROOT) + 1:-len('.json')], 'claim',
                            MTEB.blob_url(bundle.commit, r['path']), dict(r))

    def normalise(self, payload, resolver=None):
        return [], []                         # enumerated only; see the docstring


ADAPTERS = {HarnessClone.name: HarnessClone, MtebClone.name: MtebClone}


# ---- one run ---------------------------------------------------------------------------------------------------

def new_state() -> dict:
    return {'version': 1, 'commit': None, 'adapter_version': None, 'counts': None, 'hashes': {}}


def resolvers_from(root: str = ROOT) -> dict:
    from ingest.resolve import Index
    return {'benchmark': Index.load('benchmark', root)}


def run(adapter: _Clone, state: dict | None = None, resolvers: dict | None = None, limit: int | None = None) -> dict:
    """Fetch, assert the layout, enumerate and normalise. Writes nothing: `state` is updated in place for the
    caller to persist. Drift is a hard fail that keeps nothing the run saw."""
    state = state if state is not None else new_state()
    started = adapter.now()
    report = {'adapter': adapter.name, 'adapter_version': VERSION, 'started_at': iso(started), 'status': 'ok',
              'candidates_seen': 0, 'parsed': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'unresolved': 0,
              'errors': [], 'snapshot': None, 'counts': None, 'proposals': [], 'documents': [], 'unresolved_items': []}
    try:
        bundle = adapter.fetch_bundle(state)
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(adapter.now()),
                      issue=drift.issue(adapter.name, e.message, report['started_at']))
        return report
    except (GitError, policy.PolicyRefusal) as e:
        report.update(status='hard-fail', errors=['%s: %s' % (type(e).__name__, e)], finished_at=iso(adapter.now()))
        return report
    if bundle is None:
        report.update(status='no-change', finished_at=iso(adapter.now()))
        return report
    adapter.bundle = bundle
    report['snapshot'] = bundle.snapshot()
    report['counts'] = bundle.counts()
    if adapter.ref and bundle.commit == adapter.target.pin:
        report['proposals'].append('fetched %s: it is the pin, %s; nothing to move' % (adapter.ref, bundle.commit))
    elif adapter.ref:
        report['proposals'].append('fetched %s at %s, not the pin %s: move PINS only after reading this report'
                                   % (adapter.ref, bundle.commit, adapter.target.pin))
    if resolvers is None and isinstance(adapter, HarnessClone):
        resolvers = resolvers_from()
    seen, hashes, asked = set(), {}, set()
    uncatalogued = Counter()
    by_task = Counter()
    for cand in adapter.enumerate(bundle):
        if limit is not None and report['candidates_seen'] >= limit:
            break
        report['candidates_seen'] += 1
        payload = adapter.fetch(cand)
        if isinstance(adapter, MtebClone):
            by_task[payload.doc['task']] += 1
            continue
        if payload.doc['error'] is None:
            report['parsed'] += 1
        drafts, unresolved = adapter.normalise(payload, resolvers)
        for u in unresolved:
            if u.fingerprint not in asked:
                asked.add(u.fingerprint)
                report['unresolved'] += 1
                report['unresolved_items'].append({'source_key': u.source_key, 'field': u.field, 'reason': u.reason,
                                                   'human_task': u.human_task})
        if not drafts and payload.doc['config'] is not None:
            ds = payload.doc['config'].get('dataset_path')
            uncatalogued['%s %s' % (payload.doc['task_dir'], ds if isinstance(ds, str) else '(no dataset_path)')] += 1
        for d in drafts:
            seen.add(cand.source_key)
            before = state['hashes'].get(cand.source_key)        # get-default: a task the state has not seen is new
            hashes[cand.source_key] = payload.sha256_normalised
            change = 'new' if before is None else 'no-change' if before == payload.sha256_normalised else 'field-change'
            report['drafts'][change] += 1
            if change != 'no-change':
                report['documents'].append({'path': d.path.as_posix(), 'change_class': change, **d.payload,
                                            'ingestion': d.ingestion})
    if isinstance(adapter, HarnessClone):
        report['uncatalogued'] = dict(sorted(uncatalogued.items()))
        if limit is None:
            gone = sorted(k for k in state['hashes'] if k not in seen)
            report['drafts']['gone'] = len(gone)
            report['proposals'] += ['%s: the harness no longer maps it to a catalogued benchmark' % k for k in gone]
            state['hashes'] = hashes
    else:
        report['results_by_task'] = dict(sorted(by_task.items()))
    if limit is None:                       # a partial run has not seen the commit: the next run reads it again
        state.update(commit=bundle.commit, adapter_version=VERSION, counts=bundle.counts())
    report['finished_at'] = iso(adapter.now())
    if not any(report['drafts'][c] for c in CHANGE_CLASSES if c != 'no-change') and not report['unresolved'] \
            and isinstance(adapter, HarnessClone) and report['drafts']['no-change']:
        report['status'] = 'no-change'
    return report


def fixture_source(path: str, workdir: str):
    """A tree_source over a fixture directory: a one-commit repository built from it under `workdir`, citing the
    commit the manifest beside it says the directory is a copy of (or, with no manifest, its own)."""
    name = os.path.basename(os.path.normpath(path))
    dest = os.path.join(workdir, name + '.repo')
    manifest = os.path.join(os.path.dirname(os.path.normpath(path)), 'manifest.json')
    cites = None
    if os.path.exists(manifest):
        with open(manifest, encoding='utf-8') as f:
            doc = json.load(f)
        cites = next((doc[t]['commit'] for t, d in FIXTURE_DIRS.items() if d == name and t in doc), None)

    def source():
        if not os.path.isdir(dest):
            source.commit = repo_from_directory(path, dest)
        return dest, source.commit, cites or source.commit
    return source


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('adapter', nargs='?', choices=sorted(ADAPTERS), help='one target; default both')
    p.add_argument('--fixture', help='a directory holding lm-evaluation-harness/ and mteb-results/ in place of the network')
    p.add_argument('--follow', action='store_true', help="fetch the default branch's head instead of the pin")
    p.add_argument('--limit', type=int)
    a = p.parse_args(argv)
    code = 0
    with tempfile.TemporaryDirectory() as work:
        for name in [a.adapter] if a.adapter else sorted(ADAPTERS):
            cls = ADAPTERS[name]
            src = fixture_source(os.path.join(a.fixture, FIXTURE_DIRS[name]), work) if a.fixture else None
            report = run(cls(src, ref='HEAD' if a.follow else None), new_state(), limit=a.limit)
            print(json.dumps({k: v for k, v in report.items() if k not in ('documents', 'uncatalogued', 'results_by_task')},
                             indent=2, default=str))
            code = max(code, 1 if report['status'] == 'hard-fail' else 0)
    return code


FIXTURE_DIRS = {HARNESS.name: 'lm-evaluation-harness', MTEB.name: 'mteb-results'}


if __name__ == '__main__':
    sys.exit(main())
