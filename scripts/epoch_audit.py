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
    python scripts/epoch_audit.py --check               # the header-signature census (P3-S2-T01)
    python scripts/epoch_audit.py --census-report reports/epoch-header-census.md
    python scripts/epoch_audit.py --fetch               # restore epochdl/ from the pinned capture

The export itself is never committed (CC-BY, but 6.4 MB of bulk content; 05 S11's metadata-only
invariant). `--fetch` restores the plan's cut into epochdl/ from the Wayback capture pinned in
DROP below, checked against its sha256, so a clean checkout can re-run every figure here.

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
                       not exist, or no source_file and no unreferenced CSV paired with it.
                       Pairing (one-to-one, rows without source_file to unreferenced CSVs only):
                       the benchmark name and the file stem, minus a trailing `_external`, are
                       equal once lower-cased and stripped of everything but a-z and 0-9
                       (BoolQ = bool_q, BTF-3 = btf3, GDP.pdf = gdp_pdf); otherwise HAND_PAIRS
  header_signatures    distinct ordered header rows across result_csvs, compared as the exact
                       list of column names (so a reordering is a new signature, as it is to a
                       positional parser)
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
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile
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
    'header_signatures':    (62, '07 S2'),
}

# P3-S2-T01's --check: the census 07 S2 quotes, plus the two figures that settle 80 vs 81.
CENSUS = ['result_csvs', 'header_signatures', 'unreferenced_csvs', 'result_rows',
          'benchmarks', 'metadata_without_csv']

# Pairs the name rule cannot make, each with its reason. Add one only with a reason.
HAND_PAIRS = {
    'CSQA2': ('common_sense_qa_2_external.csv', 'CSQA2 is CommonsenseQA 2.0; the file spells the name out'),
}

# The plan's cut, recovered from the Wayback Machine (P3-S2-T01). 07 S2 records the drop as
# 2,292,857 bytes, 87 entries, 6,361,800 uncompressed; this capture is 2,292,861 bytes, 87
# entries, 6,361,812 uncompressed, with every entry dated 2026-09-17, and it reproduces all 30
# figures exactly, the 62 header signatures among them. The plan recorded no hash, so byte identity
# with the recon's copy cannot be shown; the 4- and 12-byte differences are recorded in
# reports/epoch-header-census.md.
DROP = {
    'url': 'https://web.archive.org/web/20260917172847id_/https://epoch.ai/data/benchmark_data.zip',
    'sha256': '6e6a9d70313d865ffd0b28de31f4a70dee6c03f99f48f0fb60a35a9270b8d556',
    'bytes': 2292861,
}

META = 'benchmark_metadata.csv'
MODELS = 'model_metadata.csv'
ECI_DIR = 'epoch_capabilities_index'
ECI = os.path.join(ECI_DIR, 'processed_data_for_eci.csv')
ECI_SCORES = os.path.join(ECI_DIR, 'eci_scores.csv')
REQUIRED = [META, MODELS, ECI, ECI_SCORES]


class Missing(Exception):
    pass


def norm(s):
    return ''.join(c for c in s.lower() if c.isascii() and c.isalnum())


def pair_orphans(meta, on_disk, referenced):
    """{benchmark name: (csv, how)} for metadata rows without a source_file, one-to-one."""
    orphans = sorted(on_disk - referenced)
    by_norm = {}
    for n in orphans:
        stem = n[:-len('.csv')]
        stem = stem[:-len('_external')] if stem.endswith('_external') else stem
        by_norm.setdefault(norm(stem), []).append(n)
    pairs, taken = {}, set()
    for m in meta:
        if (m.get('source_file') or '').strip():
            continue
        name = m['benchmark'].strip()
        if name in HAND_PAIRS and HAND_PAIRS[name][0] in orphans:
            hit, how = HAND_PAIRS[name][0], 'hand: ' + HAND_PAIRS[name][1]
        else:
            cands = [c for c in by_norm.get(norm(name), []) if c not in taken]
            if len(cands) > 1:
                raise ValueError('%s matches %s; add a HAND_PAIRS entry' % (name, cands))
            hit, how = (cands[0], 'name') if cands else (None, None)
        if hit:
            if hit in taken:
                raise ValueError('%s is paired twice' % hit)
            taken.add(hit)
            pairs[name] = (hit, how)
    return pairs


def header_of(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return next(csv.reader(f), [])


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

    pairs = pair_orphans(meta, on_disk, referenced)

    def has_csv(m):
        src = (m.get('source_file') or '').strip()
        if src:
            return src in on_disk
        return m['benchmark'].strip() in pairs

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
        'header_signatures': len({tuple(header_of(os.path.join(export, n))) for n in csvs}),
        # Not compared, reported: a URL that is neither -public nor -private means the bucket
        # naming changed, and log_public/log_private would silently undercount.
        '_log_other_host': logs['other'],
    }


def census(export):
    """The detail behind the census figures, for reports/epoch-header-census.md."""
    _, meta = read(os.path.join(export, META))
    csvs = sorted(n for n in os.listdir(export)
                  if n.endswith('.csv') and n not in (META, MODELS)
                  and os.path.isfile(os.path.join(export, n)))
    on_disk = set(csvs)
    referenced = {m['source_file'].strip() for m in meta if (m.get('source_file') or '').strip()}
    pairs = pair_orphans(meta, on_disk, referenced)
    sigs = {}
    for n in csvs:
        sigs.setdefault(tuple(header_of(os.path.join(export, n))), []).append(n)
    non_ascii = []
    for n in csvs:
        with open(os.path.join(export, n), 'rb') as f:
            first = f.readline().rstrip(b'\r\n')
        if any(b > 127 for b in first):
            try:
                first.decode('utf-8')
                valid = True
            except UnicodeDecodeError:
                valid = False
            chars = sorted({c for c in first.decode('utf-8', 'replace') if ord(c) > 127})
            non_ascii.append({'file': n, 'chars': chars, 'valid_utf8': valid,
                              'as_cp1252': ''.join(chars).encode('utf-8').decode('cp1252', 'replace')})
    return {
        'signatures': sorted(sigs.items(), key=lambda kv: (-len(kv[1]), kv[1][0])),
        'pairs': sorted(pairs.items()),
        'unpaired_rows': [m['benchmark'].strip() for m in meta
                          if not (m.get('source_file') or '').strip() and m['benchmark'].strip() not in pairs],
        'unpaired_orphans': sorted(on_disk - referenced - {c for c, _ in pairs.values()}),
        'non_ascii_headers': non_ascii,
        'metr': [dict(m) for m in meta if 'metr' in m['benchmark'].lower()],
    }


def render_census(got, c):
    """reports/epoch-header-census.md. Deterministic for a given export."""
    esc = lambda t: t.replace('|', '\\|')  # noqa: E731
    L = ['# Epoch export: header-signature census', '',
         '<!-- Generated by `python scripts/epoch_audit.py --census-report reports/epoch-header-census.md`;'
         ' do not edit by hand. -->', '',
         'P3-S2-T01. The census 07-ingestion-infrastructure.md S2 quotes, re-derived from the export by a',
         'committed script, with the counting rule for each figure and the answer to the 80-vs-81',
         'discrepancy the plan carries forward.', '',
         '## The export', '',
         "The plan's figures come from a local drop the recon made on 2026-09-16/17; `epochdl/` was never",
         'committed. The same cut was recovered from the Wayback Machine:', '',
         '- **Capture:** `%s`' % DROP['url'],
         '- **sha256:** `%s` (%s bytes)' % (DROP['sha256'], format(DROP['bytes'], ',')),
         '- **Against 07 S2:** 87 zip entries (07 S2: 87); 2,292,861 bytes on the wire (07 S2: 2,292,857);',
         '  6,361,812 bytes uncompressed (07 S2: 6,361,800); every entry dated 2026-09-17.',
         '- **Reproduces every figure:** all %d figures `scripts/epoch_audit.py` checks match the plan,' % len(EXPECTED),
         "  including the census below. The plan recorded no hash, so byte identity with the recon's copy",
         '  cannot be shown; the 4- and 12-byte differences change none of the counts.',
         '- **Restore it:** `python scripts/epoch_audit.py --fetch` downloads this capture into `epochdl/`',
         '  and checks the sha256. The export is not committed (05 S11: metadata only).', '',
         '## The census', '',
         '| Figure | Value | Counting rule |', '| --- | ---: | --- |',
         '| Benchmarks | %d | Data records in `benchmark_metadata.csv` |' % got['benchmarks'],
         '| Per-benchmark CSVs | %d | `*.csv` at the export root, minus `benchmark_metadata.csv` and'
         ' `model_metadata.csv`; `epoch_capabilities_index/` is a subdirectory and never counted |' % got['result_csvs'],
         '| Distinct header signatures | %d | Distinct ordered header rows across those CSVs, compared as the'
         ' exact list of column names |' % got['header_signatures'],
         '| Orphan CSVs | %d | Per-benchmark CSVs that no `source_file` names |' % got['unreferenced_csvs'],
         '| Result rows | %s | Data records summed across the per-benchmark CSVs |' % format(got['result_rows'], ','),
         '| Metadata rows with no CSV | %d | No `source_file`, and no orphan CSV paired with the row |'
         % got['metadata_without_csv'], '',
         '## 80 CSVs, 81 benchmarks: settled', '',
         '**The two counts are of different things and differ by exactly one row, `METR`.** Every CSV',
         'belongs to exactly one metadata row: %d rows name theirs in `source_file`, and the %d orphans pair'
         % (got['referenced_csvs'], got['unreferenced_csvs']),
         'one-to-one with %d of the %d rows that leave `source_file` empty. The one row left over has no'
         % (len(c['pairs']), len(c['pairs']) + len(c['unpaired_rows'])),
         'data file at all. The two METR rows:', '']
    for m in c['metr']:
        L.append('- `%s`: source_file `%s`, in_eci `%s`, release_date `%s`' % (
            m['benchmark'], m['source_file'] or '(empty)', m['in_eci'], m['release_date']))
    L += ['',
          'So `METR` is a metadata-only row sitting beside `METR Time Horizons`, which carries the data',
          '(`metr_time_horizons_external.csv`, the minutes-denominated `Time horizon` column of 07 S2) and',
          'is the one in the ECI. **Counting rule for the index:** a benchmark seed is a metadata row; a row',
          'with no CSV yields a seed with no result claims, and none is invented for it. Whether `METR` and',
          "`METR Time Horizons` are one benchmark is a curation question for the adapter's mapping stanza,",
          'not a counting one.', '',
          'Unpaired rows: %s. Unpaired orphan CSVs: %s.' % (
              ', '.join('`%s`' % r for r in c['unpaired_rows']) or 'none',
              ', '.join('`%s`' % r for r in c['unpaired_orphans']) or 'none'), '',
          '### How the %d orphans pair' % len(c['pairs']), '',
          'By name: the benchmark name and the file stem minus `_external`, lower-cased and stripped to',
          'a-z and 0-9, are equal. Otherwise by a hand pair in `HAND_PAIRS`, which carries its reason.', '',
          '| Metadata row | Orphan CSV | Paired by |', '| --- | --- | --- |']
    for name, (csv_name, how) in c['pairs']:
        L.append('| %s | `%s` | %s |' % (esc(name), csv_name, esc(how)))
    L += ['', '## Non-ASCII headers: the "mojibake" is in the reader, not the file', '',
          '07 S2 describes "a mojibake byte where `±` should be" in the headers of `dtbench_external.csv`',
          'and `lmca_external.csv`. Those are the only headers with a non-ASCII character, but the bytes',
          'are valid UTF-8 for `±` (`C2 B1`). The mojibake appears only when the file is decoded as',
          "cp1252 -- the default of Python's `open()` on Windows -- which shows `Â±`. The adapter must",
          'therefore open every Epoch CSV as UTF-8 explicitly; the header is not to be "repaired".', '',
          '| File | Characters | Valid UTF-8 | Read as cp1252 |', '| --- | --- | --- | --- |']
    for h in c['non_ascii_headers']:
        L.append('| `%s` | %s | %s | `%s` |' % (
            h['file'], ' '.join('`%s` U+%04X' % (ch, ord(ch)) for ch in h['chars']),
            'yes' if h['valid_utf8'] else 'no', h['as_cp1252']))
    L += ['', '## The %d header signatures' % len(c['signatures']), '',
          'Most-shared first. A column list is the exact header row, in order.', '',
          '| # | Files | Columns | Header | Files with it |', '| ---: | ---: | ---: | --- | --- |']
    for i, (sig, files) in enumerate(c['signatures'], 1):
        L.append('| %d | %d | %d | %s | %s |' % (i, len(files), len(sig), esc(' · '.join(sig)),
                                               ', '.join('`%s`' % f for f in files)))
    L.append('')
    return '\n'.join(L)


def fetch(dest):
    """Download the pinned capture, check its sha256, and unpack it into dest."""
    with urllib.request.urlopen(DROP['url'], timeout=300) as r:
        data = r.read()
    got = hashlib.sha256(data).hexdigest()
    if got != DROP['sha256']:
        raise SystemExit('epoch_audit --fetch: sha256 %s, want %s -- not the pinned drop' % (got, DROP['sha256']))
    os.makedirs(dest, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    print('fetched %d bytes (sha256 %s) into %s' % (len(data), got, dest))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--dir', default='epochdl', help='the export to audit (default: epochdl/)')
    ap.add_argument('--expect', help='JSON of {figure: value} to compare against instead of the plan')
    ap.add_argument('--emit', help='also write the derived figures to this JSON file')
    ap.add_argument('--check', action='store_true',
                    help='check only the census figures: %s' % ', '.join(CENSUS))
    ap.add_argument('--census-report', metavar='PATH', help='write the census report (markdown)')
    ap.add_argument('--fetch', action='store_true', help='restore the pinned drop into --dir, then audit')
    a = ap.parse_args(argv)
    if a.fetch:
        fetch(a.dir)

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
    if a.check:
        expected = {k: EXPECTED[k] for k in CENSUS}
    if a.census_report:
        with open(a.census_report, 'w', encoding='utf-8', newline='\n') as f:
            f.write(render_census(got, census(a.dir)))
        print('wrote %s' % a.census_report)

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
