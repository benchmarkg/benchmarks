"""The corpus-pinning values, one file per change: tests/fixtures/corpus_pins/<name>.yaml.

Six tests pin what the committed corpus resolves to: which entries exist (test_benchmark_model, test_artifacts,
test_semantic_rules, test_comparability's build step), each entry's comparability profiles and material fields
(test_comparability), where each entry stops in the runnable gate (test_runnable_gate), and which near-duplicate
pairs tools/dedup.py proposes (tests/dedup). They used to pin these as literals in the test modules, so every pull
request that added entries rewrote the same lines, and any two open pull requests conflicted.

Now a change that adds entries writes one file of its own here, holding only its entries' values and the
proposals they raise, and the tests compare what the code computes with the union of the files. Two pull requests
add two different files, so they merge in either order.

    python -m tools.corpus_pins write NAME ID [ID ...]   compute these entries' values into NAME.yaml
    python -m tools.corpus_pins check                    list entries no file pins, and values that drifted

Every value is computed from the code by `write`, never typed by hand. A file's name is the task (or fix) that
adds its entries; `base` holds the entries that were on main when the files were introduced. Run `write` on a
tree that also merges the other open PRs, so a near-duplicate pair across two of them is pinned too (load()).
"""
from __future__ import annotations

import glob
import importlib.util
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN_DIR = os.path.join('tests', 'fixtures', 'corpus_pins')
HEADER = ('# %s -- computed by `python -m tools.corpus_pins write`; never edit it by hand.\n'
          '# One file per change, so open pull requests never touch the same lines (tools/corpus_pins.py).\n')


def _module(name: str, rel: str, root: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, rel))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def gate_outcomes(g) -> dict[str, str]:
    """Where each entry stops in the runnable gate: 'N failed' or 'N undetermined' at the first clause it does not
    pass, or 'passed' when it clears all five."""
    out = {rid: 'passed' for rid in g.passing}
    for step in g.steps:
        for rid in step.failed:
            out[rid] = '%d failed' % step.clause.number
        for rid in step.undetermined:
            out[rid] = '%d undetermined' % step.clause.number
    return out


def compute(root: str = ROOT) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Every curated entry's values, and the proposals the near-duplicate detector makes over the corpus."""
    if root not in sys.path:
        sys.path.insert(0, root)
    from schema.benchmark import load_benchmark
    from schema.stub import curated_benchmark_files
    from tools import dedup
    comp = _module('comparability', os.path.join('tools', 'build', 'comparability.py'), root)
    gate = _module('runnable_gate', os.path.join('scripts', 'runnable_gate.py'), root)
    profiles = comp.load_profiles()
    outcomes = gate_outcomes(gate.run(gate.load(root)))
    entries = {}
    bench = os.path.join(root, 'data', 'benchmarks')
    for path in curated_benchmark_files(root):
        b = load_benchmark(path)
        r = comp.resolve_profile(b, profiles)
        entries[b.id] = {'file': os.path.relpath(path, bench).replace(os.sep, '/'), 'profiles': list(r.profiles),
                         'material': list(r.material), 'gate': outcomes[b.id]}
    cfg = dedup.load_config()
    proposals = sorted((s.a, s.b) for s, _ in dedup.candidates(dedup.corpus_records([]), cfg))
    return entries, proposals


def load(root: str = ROOT) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """The union of the pin files: entry id -> values, and the proposals. An id pinned twice is an error.

    A proposal is expected only while both of its entries are pinned. Two open PRs can add the two halves of a
    pair (BrowseComp and HealthBench share openai/simple-evals); the PR written second pins the pair, computed on
    a tree that merges the other, and the pair is expected once both have merged, whichever merges first."""
    entries, proposals, where = {}, set(), {}
    for path in sorted(glob.glob(os.path.join(root, PIN_DIR, '*.yaml'))):
        doc = yaml.safe_load(open(path, encoding='utf-8')) or {}
        for eid, values in (doc.get('entries') or {}).items():
            if eid in entries:
                raise ValueError('%s is pinned in both %s and %s' % (eid, where[eid], os.path.basename(path)))
            entries[eid], where[eid] = values, os.path.basename(path)
        proposals |= {tuple(p) for p in doc.get('proposals') or []}
    return entries, sorted(p for p in proposals if p[0] in entries and p[1] in entries)


def write(name: str, ids: list[str], root: str = ROOT) -> str:
    """Compute the values of `ids` into PIN_DIR/<name>.yaml, with every proposal that involves one of them."""
    entries, proposals = compute(root)
    missing = sorted(set(ids) - set(entries))
    if missing:
        raise SystemExit('not curated entries: %s' % ', '.join(missing))
    doc = {'entries': {i: entries[i] for i in sorted(ids)},
           'proposals': [list(p) for p in proposals if set(p) & set(ids)]}
    rel = os.path.join(PIN_DIR, name + '.yaml').replace(os.sep, '/')
    os.makedirs(os.path.join(root, PIN_DIR), exist_ok=True)
    with open(os.path.join(root, rel), 'w', encoding='utf-8', newline='\n') as f:
        f.write(HEADER % rel)
        yaml.safe_dump(doc, f, sort_keys=True, default_flow_style=None, width=118, allow_unicode=True)
    return rel


def check(root: str = ROOT) -> list[str]:
    """What the files and the code disagree on, one line each; empty when they agree."""
    got, got_p = compute(root)
    pinned, pinned_p = load(root)
    out = ['not pinned: %s' % i for i in sorted(set(got) - set(pinned))]
    out += ['pinned but not curated: %s' % i for i in sorted(set(pinned) - set(got))]
    out += ['drifted: %s %s' % (i, k) for i in sorted(set(got) & set(pinned)) for k in sorted(got[i])
            if got[i][k] != pinned[i].get(k)]
    out += ['proposal not pinned: %s %s' % p for p in sorted(set(got_p) - set(pinned_p))]
    out += ['pinned proposal not made: %s %s' % p for p in sorted(set(pinned_p) - set(got_p))]
    return out


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == 'write':
        print('wrote', write(argv[1], argv[2:]))
        return 0
    if argv == ['check']:
        problems = check()
        for p in problems:
            print(p)
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
