#!/usr/bin/env python3
"""Emit data/benchmarks/_stubs/ from the Epoch id allocation (P3-S2-T07; 07 S2.4, 14 Phase 3, 04 S3).

    python scripts/emit_epoch_stubs.py            # write one stub per new benchmark id
    python scripts/emit_epoch_stubs.py --check    # exit 1 if any stub differs from a fresh emission

Two inputs, both committed:
  - ingest/mappings/epoch/_id_allocation.yaml -- the ids, one row per Epoch `benchmark` string, each a
    human decision once ratified (04 S3: "Adapters may never allocate an id"; this script allocates
    nothing, it copies the allocation);
  - data/sources/2026/src-epoch-benchmark-data.yaml -- Epoch's benchmark_metadata.csv, verbatim, from the
    archived export. The stubs carry only what that file states, so they are reproducible without the
    gitignored epochdl/.

A stub per benchmark id the allocation marks new (`existing: false`), holding every Epoch row mapped to
it (schema/stub.py says why the rows are kept per row). Its name is the allocation's `name` where one
row sets it -- for a benchmark whose Epoch strings each carry a version or subset -- and otherwise its one
Epoch string; the other strings become aliases. Numbers are copied as Epoch wrote them
(0.3333333333333333 stays so), and nothing is inferred: no homepage, no facet, no description.
"""
from __future__ import annotations

import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ruamel.yaml import YAML  # noqa: E402

from schema.stub import FACETS, AllocationFile, BenchmarkStub  # noqa: E402
from tools import fmt  # noqa: E402

ALLOCATION = os.path.join('ingest', 'mappings', 'epoch', '_id_allocation.yaml')
SOURCE = os.path.join('data', 'sources', '2026', 'src-epoch-benchmark-data.yaml')
STUBS = os.path.join('data', 'benchmarks', '_stubs')
ADDED_BY = 'agent (P3-S2-T07)'


def _load(path: str):
    with open(path, encoding='utf-8') as fh:
        return YAML(typ='safe', pure=True).load(fh)


def _number(text: str, rounded: list[str]):
    """Epoch's number as Epoch wrote it (0.57 stays 0.57, 1.0 stays 1.0). bench fmt refuses a float with
    digits past the sixth decimal place, so one of those -- Epoch's 1/3 and 1/6 baselines -- is rounded
    to six and named in `rounded`, which the stub's notes report; the verbatim value stays in the source."""
    if not text.strip():
        return None
    if '.' in text and len(text.split('.')[1]) > 6:
        rounded.append(text)
        text = repr(round(float(text), 6))
    return fmt.emitter().load('v: %s\n' % text)['v']


def _row(meta: dict, alloc, rounded: list[str]) -> dict:
    return {
        'benchmark': meta['benchmark'],
        'version': alloc.version,
        'subset': alloc.subset,
        'in_eci': {'True': True, 'False': False}[meta['in_eci']],
        'source_file': meta['source_file'] or None,
        'score_column': meta['score_column'] or None,
        'released': meta['release_date'] or None,
        'chance_baseline': _number(meta['random_baseline'], rounded),
        'score_ceiling': _number(meta['score_ceiling'], rounded),
        'superseded_by': meta['superseded_by'] or None,
    }


def emit(root: str = ROOT) -> dict[str, str]:
    """{stub path relative to root: file text} for every new benchmark id in the allocation."""
    alloc = AllocationFile.model_validate(_load(os.path.join(root, ALLOCATION)))
    source = _load(os.path.join(root, SOURCE))
    if source['id'] != alloc.source:
        raise SystemExit('%s cites %s, but %s holds %s' % (ALLOCATION, alloc.source, SOURCE, source['id']))
    meta = {r['benchmark']: r for r in csv.DictReader(io.StringIO(source['quote_extract']))}
    if set(meta) != {a.epoch for a in alloc.allocations}:
        raise SystemExit('the allocation and benchmark_metadata.csv disagree on the Epoch strings: %s'
                         % sorted(set(meta) ^ {a.epoch for a in alloc.allocations}))
    by_id: dict[str, list] = {}
    for a in alloc.allocations:
        if not a.existing:
            by_id.setdefault(a.benchmark, []).append(a)
    out = {}
    for bid, rows in sorted(by_id.items()):
        names = {a.name for a in rows if a.name}
        if len(names) > 1:
            raise SystemExit('%s: the allocation gives it two names, %s' % (bid, sorted(names)))
        if not names and len(rows) > 1:
            raise SystemExit('%s: %d Epoch strings and no `name` on any row' % (bid, len(rows)))
        derived = bool(names)
        name = names.pop() if names else rows[0].epoch
        single = len(rows) == 1 and rows[0].version is None and rows[0].subset is None
        stub = {
            'id': bid,
            'name': name,
            'aliases': [a.epoch for a in rows if a.epoch != name],
            'released': (meta[rows[0].epoch]['release_date'] or None) if single else None,
            'homepage': None,
        }
        rounded: list[str] = []
        stub['epoch'] = [_row(meta[a.epoch], a, rounded) for a in rows]
        stub.update({f: None for f in FACETS})
        notes = []
        if derived:
            notes.append('Name is the Epoch strings\' common part; each string\'s own version or subset is on its row.')
        if rounded:
            notes.append('Rounded to six decimal places (bench fmt\'s float rule) from Epoch\'s %s; the verbatim '
                         'value is in the source.' % ', '.join(rounded))
        stub['curation'] = {
            'added_by': ADDED_BY, 'added_on': alloc.added_on.isoformat(), 'verification_status': 'unreviewed',
            'sources': [alloc.source], 'notes': ' '.join(notes) or None,
        }
        BenchmarkStub.model_validate(_load_text(fmt.dumps(stub)))
        head = ('# data/benchmarks/_stubs/%s.yaml -- GENERATED by scripts/emit_epoch_stubs.py from\n'
                '# ingest/mappings/epoch/_id_allocation.yaml and src-epoch-benchmark-data (P3-S2-T07; 07 S2.4).\n'
                '# An unfaceted stub: never published. Promote it to data/benchmarks/<family>/%s.yaml when a\n'
                '# curator assigns its facets from the benchmark\'s own sources.\n' % (bid, bid))
        out[os.path.join(STUBS, bid + '.yaml')] = head + fmt.dumps(stub)
    return out


def _load_text(text: str):
    return YAML(typ='safe', pure=True).load(text)


def main(argv: list[str]) -> int:
    files = emit()
    stale = [rel for rel, text in files.items()
             if not os.path.exists(os.path.join(ROOT, rel))
             or open(os.path.join(ROOT, rel), encoding='utf-8').read() != text]
    orphans = sorted(set(os.path.join(STUBS, n) for n in os.listdir(os.path.join(ROOT, STUBS))
                         if n.endswith('.yaml')) - set(files)) if os.path.isdir(os.path.join(ROOT, STUBS)) else []
    if '--check' in argv:
        for rel in stale:
            print('stale   %s' % rel, file=sys.stderr)
        for rel in orphans:
            print('orphan  %s: no allocation row names it' % rel, file=sys.stderr)
        return 1 if stale or orphans else 0
    os.makedirs(os.path.join(ROOT, STUBS), exist_ok=True)
    for rel in stale:
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(files[rel])
    for rel in orphans:
        print('orphan  %s: no allocation row names it; not deleted' % rel, file=sys.stderr)
    print('emit_epoch_stubs: %d stub(s), %d written' % (len(files), len(stale)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
