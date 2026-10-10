"""Rebuild the pruned clone fixture from the two pinned commits (P5-S5-T02).

    python tests/ingest/fixtures/harness/make_fixture.py            # reads ingest/raw/clones/, fetches MTEB blobs

Needs the two clones a live run leaves under ingest/raw/clones/ (`python -m ingest.adapters.github_clones`):
the harness with its blobs, MTEB blob-less. The MTEB files kept are fetched by id, through the gate, in one fetch.

Every kept file is the pinned commit's blob, byte for byte; nothing is edited. What is pruned, and by which rule,
is in README.md and manifest.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from ingest.adapters import github_clones as G  # noqa: E402

# Kept whatever the per-directory rule picks: the tasks the tests read by name.
NAMED_TASKS = ('arc_easy', 'gsm8k', 'hellaswag', 'mmlu_anatomy')
MTEB_MODELS = 12            # the first models in sorted order
MTEB_RESULTS = 2            # result JSONs kept per model, the first in sorted order
MTEB_MAX_BYTES = 32_000     # a larger result is skipped for the next


def harness_files(tree: G.Tree) -> tuple[list[str], dict]:
    h = G.check_harness(tree)
    by_name = {h.raw[p]['task']: p for p in h.task_configs()}
    keep = {G.HARNESS.licence_file, G.TASKS_MARKER}
    dirs = sorted({G.task_dir(p) for p in h.task_configs() + h.group_configs()})
    for d in dirs:
        configs = sorted((p for p in h.task_configs() if G.task_dir(p) == d), key=lambda p: (len(p), p))
        chosen = None
        for p in configs:
            try:
                _, chain = h.merged(p)
            except G.ConfigError:
                continue
            chosen = [p] + chain
            break
        if chosen is None:                    # a directory of groups only (benchmarks/): its shortest group config
            chosen = [sorted((p for p in h.group_configs() if G.task_dir(p) == d), key=lambda p: (len(p), p))[0]]
        keep.update(chosen)
    for name in NAMED_TASKS:
        keep.add(by_name[name])
        keep.update(h.merged(by_name[name])[1])
    full = {'task_dirs': len(dirs), 'task_configs': len(h.task_configs()), 'group_configs': len(h.group_configs()),
            'yaml_files': len(h.files)}
    return sorted(keep), full


def mteb_files(tree: G.Tree, repo: str) -> tuple[list[str], dict]:
    results = G.check_mteb(tree)
    models = sorted({r['model'] for r in results})[:MTEB_MODELS]
    keep = [G.MTEB.licence_file] + sorted(p for p in tree.blobs_under(G.MTEB_ROOT) if p.count('/') == 1)
    candidates = []
    for m in models:
        rev = sorted(r['revision'] for r in results if r['model'] == m)[0]
        base = '%s/%s/%s/' % (G.MTEB_ROOT, m.replace('/', '__', 1), rev)
        meta = base + 'model_meta.json'
        if tree.is_blob(meta):
            keep.append(meta)
        candidates.append(sorted(r['path'] for r in results if r['path'].startswith(base) and not r['variant']))
    experiment = sorted(r['path'] for r in results if r['variant'])[0]
    wanted = keep[1:] + [p for c in candidates for p in c[:MTEB_RESULTS + 3]] + [experiment]
    missing = [tree.entries[p][1] for p in wanted if not _present(repo, tree.entries[p][1])]
    G.fetch_blobs(G.MTEB, repo, missing)
    for c in candidates:
        kept = [p for p in c[:MTEB_RESULTS + 3] if len(tree.read([p])[p]) <= MTEB_MAX_BYTES][:MTEB_RESULTS]
        keep += kept
    keep.append(experiment)
    counts = {k: v for k, v in _mteb_counts(results).items()}
    return sorted(set(keep)), counts


def _mteb_counts(results) -> dict:
    return {'models': len({r['model'] for r in results}), 'result_files': len(results),
            'tasks': len({r['task'] for r in results}), 'experiment_results': sum(1 for r in results if r['variant'])}


def _present(repo: str, oid: str) -> bool:
    out = G.git(repo, 'cat-file', '--batch-check', input=(oid + '\n').encode())
    return not out.rstrip().endswith(b'missing')


def write(tree: G.Tree, files: list[str], dest: str) -> None:
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    for p, body in tree.read(files).items():
        out = os.path.join(dest, *p.split('/'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f:
            f.write(body)


def main() -> int:
    manifest = {}
    for target, build in ((G.HARNESS, harness_files), (G.MTEB, mteb_files)):
        repo = os.path.join(G.CLONES, target.name + '.git')
        tree = G.Tree(repo, target.pin)
        files, full = build(tree) if build is harness_files else build(tree, repo)
        dest = os.path.join(HERE, G.FIXTURE_DIRS[target.name])
        write(tree, files, dest)
        manifest[target.name] = {'repository': target.url, 'commit': target.pin, 'licence': target.licence,
                                 'files_kept': len(files), 'full_tree_at_the_pin': full}
    with open(os.path.join(HERE, 'manifest.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
