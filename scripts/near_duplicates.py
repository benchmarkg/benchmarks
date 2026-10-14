#!/usr/bin/env python3
"""build/derived/near_duplicates.json: the near-duplicate signature, computed and never acted on (P3-S4-T04; 04 S10).

    uv run python scripts/near_duplicates.py                # epochdl/ and data/claims/ -> the artifact
    uv run python scripts/near_duplicates.py --zip PATH     # a bundle as served, not the unpacked copy
    uv run python scripts/near_duplicates.py --no-snapshot  # data/claims/ alone, where epochdl/ is absent

07 S5.6: "Never deduplicate at ingest. Emit every source row as a separate ResultClaim and surface suspected
duplicates as a report, not a merge." 04 S10 owns the signature:

    same benchmark  AND  same model version  AND  |delta value| < 0.005  AND  different Source spelling

It is computed pairwise within two populations, never across them:

  epoch   every row of every per-benchmark CSV in the Epoch snapshot. The benchmark is the file's mapping stanza
          (benchmark_ref and metric_ref, so two metrics of one benchmark are two measurements); the model version
          is the `Model version` cell as written; the value is the stanza's score column times its scale, the
          number the claim would carry; and the spelling is the `Source` cell. A file with no Source column, or a
          row whose cell is blank, names no spelling and is never half of a pair: a missing source is not a
          second spelling of one. A file with no stanza is listed, not guessed at (07 S8: no default scale).
  claims  every ResultClaim under data/claims/ with a value that is not superseded. The benchmark is (benchmark,
          subset, metric, opponent), the model version is `system` with its @version, and the spelling is
          `source`, the Source id.

The case it is built for is in arc_agi_external.csv: Claude Opus 4.6 (120K, High) at 0.94, once with Source
`https://arcprize.org/leaderboard` and once with `ARC Prize Leaderboard`. The same model version has three more
rows, Max 0.93, Medium 0.92 and Low 0.86, told apart only by a label. A dedupe keyed on model and benchmark would
collapse all five; the signature pairs only the two spellings of the High run.

Nothing here merges, drops or picks between claims. Each match is a pair of row references for a person to
resolve, and the artifact counts every row it read. Exit codes: 0 written; 2 the snapshot is missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, 'build', 'derived', 'near_duplicates.json')
EPOCHDL = os.path.join(ROOT, 'epochdl')
DELTA = 0.005                   # 04 S10: "absolute value delta under 0.005", strictly under
MODEL_VERSION = 'Model version'
SOURCE, SOURCE_LINK, NAME, ROW_ID = 'Source', 'Source link', 'Name', 'id'
SIGNATURE = ('same benchmark AND same model version AND |delta value| < %s AND different Source spelling (04 S10)'
             % DELTA)


def _number(cell: str) -> float | None:
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


def pairs(rows: list[dict]) -> list[tuple[dict, dict]]:
    """Every pair within one group (one benchmark and model version) that the signature fires on. A row is a
    dict with `value` and `spelling`; a row with no value or no spelling is never half of a pair."""
    rows = [r for r in rows if r['value'] is not None and r['spelling']]
    return [(a, b) for a, b in combinations(rows, 2)
            if a['spelling'] != b['spelling'] and abs(a['value'] - b['value']) < DELTA]


def _match(population: str, key: dict, a: dict, b: dict) -> dict:
    """One match. For a snapshot pair it also names every other column whose cells differ (Shots, Notes, Name),
    which is often what a person needs to resolve it; the signature itself never reads them."""
    match = {'population': population, **key, 'delta': round(abs(a['value'] - b['value']), 6)}
    if 'cells' in a:
        ca, cb = a['cells'], b['cells']
        match['differing_columns'] = sorted(c for c in set(ca) | set(cb) if c not in (ROW_ID, SOURCE)
                                            and (ca.get(c) or '').strip() != (cb.get(c) or '').strip())
    match['rows'] = [{k: v for k, v in r.items() if k not in ('spelling', 'cells')} | {'source': r['spelling']}
                     for r in (a, b)]
    return match


def epoch_rows(bundle, stanzas: dict) -> tuple[dict, list[str], int]:
    """The snapshot's rows grouped by (benchmark_ref, metric_ref, model version), the files with no stanza, and
    the total row count. The row reference is the file, the row's ordinal among its file's data rows and
    Epoch's own record id."""
    groups, unmapped, total = defaultdict(list), [], 0
    for stem in bundle.per_benchmark_csvs():
        headers, rows = bundle.read_csv(stem + '.csv')
        total += len(rows)
        stanza = stanzas.get('csv:' + stem)         # get-default: a file with no stanza is listed, not guessed at
        if stanza is None or stanza.score_column not in headers:
            unmapped.append(stem + '.csv')
            continue
        for i, row in enumerate(rows, 1):
            version = (row.get(MODEL_VERSION) or '').strip()
            if not version:
                continue                            # a blank model version is the same as no other
            score = _number(row.get(stanza.score_column))
            groups[stanza.benchmark_ref, stanza.metric_ref, version].append({
                'file': stem + '.csv', 'row': i, 'id': row.get(ROW_ID) or None, 'name': row.get(NAME) or None,
                'score': row.get(stanza.score_column),
                'value': None if score is None else score * stanza.scale,
                'spelling': (row.get(SOURCE) or '').strip(),
                'source_link': (row.get(SOURCE_LINK) or '').strip() or None, 'cells': row})
    return groups, unmapped, total


def claim_rows(claims) -> dict:
    """The claims grouped by (benchmark, subset, metric, opponent, system); superseded claims are history."""
    groups = defaultdict(list)
    for c in claims:
        if c.superseded_by is None:
            groups[c.benchmark, c.subset, c.metric, c.opponent, c.system].append(
                {'claim': c.id, 'value': c.value, 'eval_conditions': c.eval_conditions,
                 'date_reported': c.date_reported.isoformat(), 'spelling': c.source})
    return groups


def find(bundle, stanzas: dict, claims) -> dict:
    """The artifact: every match in both populations, and what was read. `bundle` None skips the snapshot."""
    matches, populations = [], {}
    if bundle is not None:
        groups, unmapped, total = epoch_rows(bundle, stanzas)
        for (bench, metric, version), rows in sorted(groups.items()):
            for a, b in pairs(rows):
                matches.append(_match('epoch', {'benchmark': bench, 'metric': metric, 'model_version': version}, a, b))
        populations['epoch'] = {'snapshot': {'artefact_sha256': bundle.sha256, 'artefact_bytes': bundle.bytes},
                                'rows': total, 'files_without_stanza': unmapped}
    claims = list(claims)
    groups = claim_rows(claims)
    for (bench, subset, metric, opponent, system), rows in sorted(groups.items(), key=lambda kv: repr(kv[0])):
        for a, b in pairs(rows):
            matches.append(_match('claims', {'benchmark': bench, 'subset': subset, 'metric': metric,
                                             'opponent': opponent, 'model_version': system}, a, b))
    populations['claims'] = {'claims': len(claims)}
    return {'report': 'near-duplicates', 'signature': SIGNATURE, 'populations': populations,
            'matches': matches, 'summary': {pop: sum(1 for m in matches if m['population'] == pop)
                                            for pop in populations}}


def load_claims(root: str):
    from schema.claim import ResultClaim
    from schema.taxonomy import read_yaml
    return [ResultClaim.model_validate(read_yaml(p))
            for p in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True))]


def shown(path: str) -> str:
    """A path relative to the repository when it is inside it, else as given (relpath fails across drives)."""
    full = os.path.abspath(path)
    return os.path.relpath(full, ROOT) if full.startswith(ROOT + os.sep) else path


def load_bundle(zip_path: str | None, snapshot: str):
    from ingest.adapters import epoch
    if zip_path:
        with open(zip_path, 'rb') as f:
            return epoch.ZipBundle(f.read())
    if not glob.glob(os.path.join(snapshot, '*.csv')):
        return None
    return epoch.bundle_from_directory(snapshot)


def main(argv=None) -> int:
    from ingest.mappings.schema import load_all
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--snapshot', default=EPOCHDL, help='an unpacked bundle (default: epochdl/)')
    p.add_argument('--zip', help='a bundle as served, instead of --snapshot')
    p.add_argument('--no-snapshot', action='store_true', help='the claims alone')
    p.add_argument('--root', default=ROOT, help='the tree whose data/claims/ is read')
    p.add_argument('--out', default=OUT)
    a = p.parse_args(argv)

    bundle = None
    if not a.no_snapshot:
        bundle = load_bundle(a.zip, a.snapshot)
        if bundle is None:
            print('near-duplicates: %s holds no Epoch snapshot; restore it with `python scripts/epoch_audit.py '
                  '--fetch`, pass --zip, or run with --no-snapshot' % shown(a.snapshot), file=sys.stderr)
            return 2
    report = find(bundle, load_all('epoch') if bundle is not None else {}, load_claims(a.root))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write('\n')

    for m in report['matches']:
        print('  %s  %s  %s  delta %s: %s' % (m['population'], m['benchmark'], m['model_version'], m['delta'],
                                              ' | '.join(repr(r['source']) for r in m['rows'])))
    read = ', '.join('%s %d %s' % (pop, n.get('rows', n.get('claims')), 'rows' if 'rows' in n else 'claims')
                     for pop, n in report['populations'].items())
    print('near-duplicates: wrote %s; %d matches (%s read), none merged'
          % (shown(a.out), len(report['matches']), read))
    return 0


if __name__ == '__main__':
    sys.exit(main())
