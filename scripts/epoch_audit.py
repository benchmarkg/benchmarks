#!/usr/bin/env python3
"""Re-derive every Epoch figure the plan quotes, from the Epoch export itself.

00-vision-and-scope.md S8.1 and 01-landscape-and-positioning.md S12 quote counts taken from
the local Epoch drop of 2026-09-16 (recon:epoch-assets). Neither document could re-run them:
the export is not in the working tree. This script is the committed reproduction 01 S12 asks
for -- "every number in this plan derived from a local artifact must name the artifact, the
filter and the date, and must be reproducible by a committed script."

    python scripts/epoch_audit.py                       # against epochdl/
    python scripts/epoch_audit.py --dir path/to/export  # against another cut
    python scripts/epoch_audit.py --expect counts.json  # compare against other expectations
    python scripts/epoch_audit.py --emit out.json       # also write the derived figures

Exit codes:
    0  every derived figure matches its expectation
    1  at least one figure differs; each difference is printed with the plan section it
       came from, so the fix is either the plan's number or this script's counting rule
    2  the export, or an artifact inside it, is missing; the message names which one

Counting rules. Each is stated because a count is only reproducible if its filter is:

  benchmarks           data records in benchmark_metadata.csv
  result_csvs          *.csv at the export root, minus benchmark_metadata.csv and
                       model_metadata.csv. epoch_capabilities_index/ is a subdirectory and is
                       never included (00 S8.1: ECI rows are a fitted latent ability, not
                       observations)
  referenced_csvs      result CSVs named by some benchmark_metadata.source_file
  metadata_without_csv benchmark_metadata rows with no CSV on disk: a source_file that does
                       not exist, or no source_file and no <slug>.csv / <slug>_external.csv
  result_rows          data records summed across result_csvs
  epoch_run_*          result CSVs whose header has `Logs` or `Log viewer` (recon family A)
  log_public/private   Epoch-run rows whose log URL -- `Logs`, else the log_file= parameter
                       of `Log viewer` -- is on a bucket whose host contains -public / -private
  log_none             Epoch-run rows with neither column filled
  log_viewer           Epoch-run rows with `Log viewer` filled
  log_bucket_only      Epoch-run rows with `Logs` filled and `Log viewer` empty
  model_*              model_metadata.csv records; distinct non-empty model_group and
                       model_version
  csv_model_versions   distinct non-empty `Model version` across all result CSVs
  eci_*                epoch_capabilities_index/processed_data_for_eci.csv records and its
                       distinct benchmark_id and model_id; eci_scores.csv records

A data record is anything the csv module yields after the header, including a row whose
fields are all empty: model_metadata.csv carries 11 such rows and 00 S8.1 counts them.
The two log decompositions come from different columns and 01 S12 quotes both; this script
derives both from one pass so a disagreement between them is visible, not argued.
"""
import argparse
import csv
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every figure the plan quotes, with where it is quoted. `None` means the plan states the
# figure only as a consequence of others and it is checked through them.
EXPECTED = {
    'benchmarks':           (81, '00 S8.1; 01 S12'),
    'result_csvs':          (80, '00 S8.1; 01 S12'),
    'referenced_csvs':      (59, '00 S8.1'),
    'unreferenced_csvs':    (21, '00 S8.1; 01 S12'),
    'metadata_without_csv': (1, '00 S8.1 (METR); 01 S12'),
    'result_rows':          (6598, '00 S8.1; 01 S12'),
    'mean_rows_per_csv':    (82.5, '00 S8.1'),
    'largest_csv':          ('gpqa_diamond.csv', '00 S8.1'),
    'largest_csv_rows':     (313, '00 S8.1'),
    'epoch_run_csvs':       (14, '01 S12'),
    'epoch_run_rows':       (1550, '01 S12'),
    'external_csvs':        (66, '01 S12'),
    'external_rows':        (5048, '01 S12'),
    'log_public':           (828, '00 S8.1; 01 S12'),
    'log_private':          (459, '01 S12'),
    'log_none':             (263, '01 S12'),
    'log_any':              (1287, '01 S12'),
    'log_viewer':           (962, '01 S12 (later recount)'),
    'log_bucket_only':      (325, '01 S12 (later recount)'),
    'log_any_pct':          (19.5, '01 S12'),
    'log_public_pct':       (12.5, '01 S12'),
    'model_rows':           (1063, '00 S8.1; 01 S12'),
    'model_groups':         (550, '00 S8.1; 01 S12'),
    'model_versions':       (1048, '00 S8.1; 01 S12'),
    'csv_model_versions':   (927, '00 S8.1; 01 S12'),
    'eci_rows':             (2760, '00 S8.1'),
    'eci_benchmarks':       (58, '00 S8.1'),
    'eci_models':           (266, '00 S8.1; 01 S12'),
    'eci_scores_rows':      (266, '01 S12 ("266 models in the ECI fit")'),
}

META = 'benchmark_metadata.csv'
MODELS = 'model_metadata.csv'
ECI_DIR = 'epoch_capabilities_index'
ECI = os.path.join(ECI_DIR, 'processed_data_for_eci.csv')
ECI_SCORES = os.path.join(ECI_DIR, 'eci_scores.csv')
REQUIRED = [META, MODELS, ECI, ECI_SCORES]


class Missing(Exception):
    pass


def read(path):
    """Header and data records of a CSV. utf-8-sig tolerates a BOM from a spreadsheet save."""
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    header, data = rows[0], rows[1:]
    return header, [dict(zip(header, r)) for r in data]


def log_bucket(row):
    url = (row.get('Logs') or '').strip()
    if not url:
        viewer = (row.get('Log viewer') or '').strip()
        if viewer:
            url = (parse_qs(urlparse(viewer).query).get('log_file') or [''])[0]
    host = urlparse(url).netloc
    if '-public' in host:
        return 'public'
    if '-private' in host:
        return 'private'
    return 'other' if url else None


def derive(export):
    if not os.path.isdir(export):
        raise Missing('export directory %s does not exist' % export)
    for rel in REQUIRED:
        if not os.path.isfile(os.path.join(export, rel)):
            raise Missing('%s is missing from %s' % (rel, export))

    _, meta = read(os.path.join(export, META))
    csvs = sorted(n for n in os.listdir(export)
                  if n.endswith('.csv') and n not in (META, MODELS)
                  and os.path.isfile(os.path.join(export, n)))
    on_disk = set(csvs)
    referenced = {m['source_file'].strip() for m in meta if (m.get('source_file') or '').strip()}

    def has_csv(m):
        src = (m.get('source_file') or '').strip()
        if src:
            return src in on_disk
        slug = m['benchmark'].strip().lower().replace(' ', '_').replace('-', '_')
        return slug + '.csv' in on_disk or slug + '_external.csv' in on_disk

    rows_per = {}
    run_csvs, run_rows = 0, 0
    logs = {'public': 0, 'private': 0, 'other': 0, None: 0}
    viewer = bucket_only = 0
    versions_in_csvs = set()
    for name in csvs:
        header, data = read(os.path.join(export, name))
        rows_per[name] = len(data)
        versions_in_csvs.update(r['Model version'].strip() for r in data
                                if (r.get('Model version') or '').strip())
        if 'Logs' in header or 'Log viewer' in header:
            run_csvs += 1
            run_rows += len(data)
            for r in data:
                logs[log_bucket(r)] += 1
                v = bool((r.get('Log viewer') or '').strip())
                b = bool((r.get('Logs') or '').strip())
                viewer += v
                bucket_only += b and not v

    _, models = read(os.path.join(export, MODELS))
    _, eci = read(os.path.join(export, ECI))
    _, eci_scores = read(os.path.join(export, ECI_SCORES))

    total = sum(rows_per.values())
    largest = max(rows_per, key=lambda n: (rows_per[n], n)) if rows_per else None
    log_any = logs['public'] + logs['private'] + logs['other']
    return {
        'benchmarks': len(meta),
        'result_csvs': len(csvs),
        'referenced_csvs': len(referenced & on_disk),
        'unreferenced_csvs': len(on_disk - referenced),
        'metadata_without_csv': sum(1 for m in meta if not has_csv(m)),
        'result_rows': total,
        'mean_rows_per_csv': round(total / len(csvs), 1) if csvs else 0.0,
        'largest_csv': largest,
        'largest_csv_rows': rows_per.get(largest, 0),
        'epoch_run_csvs': run_csvs,
        'epoch_run_rows': run_rows,
        'external_csvs': len(csvs) - run_csvs,
        'external_rows': total - run_rows,
        'log_public': logs['public'],
        'log_private': logs['private'],
        'log_none': logs[None],
        'log_any': log_any,
        'log_viewer': viewer,
        'log_bucket_only': bucket_only,
        'log_any_pct': round(100 * log_any / total, 1) if total else 0.0,
        'log_public_pct': round(100 * logs['public'] / total, 1) if total else 0.0,
        'model_rows': len(models),
        'model_groups': len({m['model_group'].strip() for m in models if (m.get('model_group') or '').strip()}),
        'model_versions': len({m['model_version'].strip() for m in models if (m.get('model_version') or '').strip()}),
        'csv_model_versions': len(versions_in_csvs),
        'eci_rows': len(eci),
        'eci_benchmarks': len({r['benchmark_id'] for r in eci if r.get('benchmark_id')}),
        'eci_models': len({r['model_id'] for r in eci if r.get('model_id')}),
        'eci_scores_rows': len(eci_scores),
        # Not compared, reported: a URL that is neither -public nor -private means the bucket
        # naming changed, and log_public/log_private would silently undercount.
        '_log_other_host': logs['other'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--dir', default='epochdl', help='the export to audit (default: epochdl/)')
    ap.add_argument('--expect', help='JSON of {figure: value} to compare against instead of the plan')
    ap.add_argument('--emit', help='also write the derived figures to this JSON file')
    a = ap.parse_args(argv)

    try:
        got = derive(a.dir)
    except Missing as e:
        print('epoch_audit: cannot audit -- %s.' % e, file=sys.stderr)
        print('  00 S8.1 and 01 S12 record that epochdl/ is not in the working tree; point --dir'
              ' at a copy of the 2026-09-16 export to re-derive the plan\'s figures.', file=sys.stderr)
        return 2

    if a.expect:
        with open(a.expect, encoding='utf-8') as f:
            expected = {k: (v, a.expect) for k, v in json.load(f).items()}
    else:
        expected = EXPECTED

    if a.emit:
        with open(a.emit, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'dir': a.dir, **got}, f, indent=2)
            f.write('\n')

    bad = 0
    for key, (want, where) in expected.items():
        have = got.get(key)
        ok = have == want
        bad += not ok
        print(('%-4s %-22s %-18s %s' % ('ok' if ok else 'DIFF', key, have,
                                        '' if ok else 'expected %s (%s)' % (want, where))).rstrip())
    if got['_log_other_host']:
        print('note %d log URLs are on a host that is neither -public nor -private'
              % got['_log_other_host'])
    print('%d of %d figures match' % (len(expected) - bad, len(expected)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
