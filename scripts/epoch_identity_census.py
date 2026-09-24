#!/usr/bin/env python3
"""The identity population of the Epoch export, counted once and published (P3-S3-T01).

07-ingestion-infrastructure.md S5.1-5.2 sizes the Epoch crosswalk -- "roughly 550 model groups and
927 version strings", the 927 joining model_metadata.csv "at 100%", 1,048 registry strings, ~70
organisations -- and 04 S10's resolution steps are built on those numbers. This script derives
them from the export so nothing downstream re-derives them, and fails if any moves.

    python scripts/epoch_identity_census.py --check          # against epochdl/
    python scripts/epoch_identity_census.py --report reports/epoch-identity-census.md
    python scripts/epoch_audit.py --fetch                     # restores epochdl/ first, if absent

Counting rules:

  model_groups            distinct non-empty model_group in model_metadata.csv (Epoch's System)
  registry_versions       distinct non-empty model_version in model_metadata.csv
  result_versions         distinct non-empty `Model version` across the 80 per-benchmark CSVs
                          (epoch_audit.py's result_csvs; the ECI directory is never read)
  result_versions_joined  result_versions that are also registry_versions; 07 S5.1 says all
  unused_registry         registry_versions no result row uses: need no crosswalk entry (00 S8.1)
  org_strings             distinct non-empty `organization` values in model_metadata.csv, as
                          written -- `Google DeepMind,Google` is one string
  organisations           distinct names after splitting every organization value on commas and
                          trimming: the population an Organization registry has to cover
  effort_suffix_rows      result rows whose Model version ends in 07 S5.2's reasoning-effort
                          suffix, _(max|xhigh|high|medium|low|minimal|none|unknown)

The plan's "~70 organisations" is org_strings. Split, the population is organisations, and the
difference is the joint-work strings the recon names ("70 distinct strings -> split on commas").

Exit codes: 0 every figure matches; 1 a figure moved; 2 the export is missing.
"""
import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epoch_audit import META, MODELS, Missing, read  # noqa: E402

EFFORT = re.compile(r'_(max|xhigh|high|medium|low|minimal|none|unknown)$')

EXPECTED = {
    'model_groups': (550, '07 S5.2; 00 S8.1'),
    'registry_versions': (1048, '07 S5.2; 00 S8.1'),
    'result_versions': (927, '07 S5.1; 00 S8.1'),
    'result_versions_joined': (927, '07 S5.1 ("join ... at 100%")'),
    'unused_registry': (121, '07 S5.2 ("121 of those never appear in a result row")'),
    'org_strings': (70, '07 S11.1 table; recon:epoch-assets ("70 distinct")'),
    'organisations': (74, 'P3-S3-T01, this census: the 70 strings split on commas'),
    'effort_suffix_rows': (2402, '07 S5.2 ("2,402 of the 6,598 rows (36.4%)")'),
}


def census(export):
    for rel in (META, MODELS):
        if not os.path.isfile(os.path.join(export, rel)):
            raise Missing('%s is missing from %s' % (rel, export))
    _, models = read(os.path.join(export, MODELS))
    groups = {m['model_group'].strip() for m in models if (m.get('model_group') or '').strip()}
    registry = {m['model_version'].strip() for m in models if (m.get('model_version') or '').strip()}
    raw_orgs = Counter(m['organization'].strip() for m in models if (m.get('organization') or '').strip())
    split_orgs = Counter()
    for m in models:
        for part in (m.get('organization') or '').split(','):
            if part.strip():
                split_orgs[part.strip()] += 1

    versions, rows, effort = Counter(), 0, 0
    csvs = sorted(n for n in os.listdir(export)
                  if n.endswith('.csv') and n not in (META, MODELS) and os.path.isfile(os.path.join(export, n)))
    for name in csvs:
        _, data = read(os.path.join(export, name))
        for r in data:
            rows += 1
            v = (r.get('Model version') or '').strip()
            if v:
                versions[v] += 1
                effort += bool(EFFORT.search(v))
    joined = set(versions) & registry
    return {
        'figures': {
            'model_groups': len(groups),
            'registry_versions': len(registry),
            'result_versions': len(versions),
            'result_versions_joined': len(joined),
            'unused_registry': len(registry - set(versions)),
            'org_strings': len(raw_orgs),
            'organisations': len(split_orgs),
            'effort_suffix_rows': effort,
        },
        'rows': rows,
        'unjoined': sorted(set(versions) - registry),
        'joint_strings': sorted((k, v) for k, v in raw_orgs.items() if ',' in k),
        'organisations': sorted(split_orgs.items(), key=lambda kv: (-kv[1], kv[0])),
        'split_only': sorted(set(split_orgs) - set(raw_orgs)),
    }


def render(c, export_note):
    f = c['figures']
    esc = lambda t: t.replace('|', '\\|')  # noqa: E731
    L = ['# Epoch export: identity census', '',
         '<!-- Generated by `python scripts/epoch_identity_census.py --report reports/epoch-identity-census.md`;'
         ' do not edit by hand. -->', '',
         'P3-S3-T01. The four identity populations 07-ingestion-infrastructure.md S5 sizes the Epoch',
         'crosswalk by, counted once from the export so that nothing downstream re-derives them.',
         '`--check` fails if any of them moves.', '',
         export_note, '',
         '## The counts', '',
         '| Figure | Value | Plan | Counting rule |', '| --- | ---: | --- | --- |']
    rules = {
        'model_groups': 'distinct `model_group` in `model_metadata.csv`',
        'registry_versions': 'distinct `model_version` in `model_metadata.csv`',
        'result_versions': 'distinct `Model version` across the 80 per-benchmark CSVs',
        'result_versions_joined': 'result-row versions present in the registry',
        'unused_registry': 'registry versions no result row uses (no crosswalk entry needed)',
        'org_strings': '`organization` values as written; a joint value is one string',
        'organisations': 'names after splitting every `organization` value on commas',
        'effort_suffix_rows': 'result rows whose version ends in a reasoning-effort suffix',
    }
    for k, (want, where) in EXPECTED.items():
        L.append('| `%s` | %s | %s | %s |' % (k, format(f[k], ','), esc(where), rules[k]))
    L += ['',
          '**The join is complete:** %d of %d result-row version strings are in the registry (%s).'
          % (f['result_versions_joined'], f['result_versions'],
             'none missing' if not c['unjoined'] else ', '.join(c['unjoined'])),
          'The effort suffix is on %s of %s result rows (%.1f%%).' % (
              format(f['effort_suffix_rows'], ','), format(c['rows'], ','), 100 * f['effort_suffix_rows'] / c['rows']),
          '',
          '## ~70 organisations: which 70', '',
          'The plan\'s "70" is the number of distinct `organization` **strings**. %d of them join several'
          % len(c['joint_strings']),
          'organisations with commas, so the population an Organization registry has to cover is the',
          '**%d names after splitting**. These %d names occur only inside joint strings:' % (
              f['organisations'], len(c['split_only'])), '']
    L += ['- %s' % esc(n) for n in c['split_only']]
    L += ['', 'The joint strings, with how many model rows carry each:', '',
          '| `organization` as written | Rows |', '| --- | ---: |']
    L += ['| %s | %d |' % (esc(k), v) for k, v in c['joint_strings']]
    L += ['', 'Splitting is mechanical; deciding that `Google` and `Google DeepMind`, or `Cohere` and',
          '`Cohere Labs (formerly Cohere for AI)`, are one Organization or two is the alias review',
          'recon:epoch-assets asks for, and is not made here.', '',
          '## The %d organisations' % f['organisations'], '',
          'Model rows naming each, joint values counted once per organisation named.', '',
          '| Organisation | Model rows |', '| --- | ---: |']
    L += ['| %s | %d |' % (esc(k), v) for k, v in c['organisations']]
    L.append('')
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--dir', default='epochdl')
    ap.add_argument('--check', action='store_true', help='compare every figure against EXPECTED')
    ap.add_argument('--report', metavar='PATH', help='write the census report (markdown)')
    a = ap.parse_args(argv)
    try:
        c = census(a.dir)
    except Missing as e:
        print('epoch_identity_census: cannot count -- %s. Run `python scripts/epoch_audit.py --fetch`.' % e,
              file=sys.stderr)
        return 2
    if a.report:
        note = ('Source: the Epoch export in `%s/`, restored by `python scripts/epoch_audit.py --fetch` from the'
                ' pinned capture recorded in reports/epoch-header-census.md.' % os.path.basename(os.path.normpath(a.dir)))
        with open(a.report, 'w', encoding='utf-8', newline='\n') as f:
            f.write(render(c, note))
        print('wrote %s' % a.report)
    bad = 0
    for k, (want, where) in EXPECTED.items():
        have = c['figures'][k]
        bad += have != want
        print(('%-4s %-24s %-8s %s' % ('ok' if have == want else 'DIFF', k, have,
                                       '' if have == want else 'expected %s (%s)' % (want, where))).rstrip())
    print('%d of %d figures match' % (len(EXPECTED) - bad, len(EXPECTED)))
    return 1 if (bad and (a.check or not a.report)) else 0


if __name__ == '__main__':
    sys.exit(main())
