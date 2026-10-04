"""Write tests/fixtures/epoch-dates/event-dates.json from the local Epoch snapshot (P4-S2-T07).

    python tests/fixtures/epoch-dates/make_fixture.py        # reads epochdl/, which is gitignored

The date each of Epoch's 6,598 result rows would carry as `date_reported`, exactly as 07 S11's
normaliser takes it -- parse_date(row[stanza.date_column]) -- counted per day, with the rows that have
no date column, or an empty one, counted as undated. `Release date` is the model's release, not when
the result was reported, so it never stands in. Only the counts are kept: no row, score or model name.
The data is Epoch AI's (CC-BY-4.0), as REUSE.toml records.
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from ingest.mappings.schema import load_all  # noqa: E402

SKIP = ('benchmark_metadata.csv', 'model_metadata.csv')


def main():
    stanzas = load_all('epoch')
    days, undated, rows, files = collections.Counter(), 0, 0, 0
    for name in sorted(os.listdir(os.path.join(ROOT, 'epochdl'))):
        if not name.endswith('.csv') or name in SKIP:
            continue
        files += 1
        stanza = stanzas.get('csv:' + name[:-len('.csv')])     # get-default: a file with no stanza has no date
        column = stanza.date_column if stanza else None
        with open(os.path.join(ROOT, 'epochdl', name), encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                rows += 1
                value = (row.get(column) or '').strip() if column else ''   # get-default: a row may lack the column
                if value:
                    days[value[:10]] += 1
                else:
                    undated += 1
    out = {'source': 'Epoch AI benchmark data (CC-BY-4.0), the local epochdl/ snapshot',
           'rule': 'parse_date(row[stanza.date_column]) per 07 S11; Release date never stands in',
           'files': files, 'rows': rows, 'undated': undated, 'dates': dict(sorted(days.items()))}
    with open(os.path.join(HERE, 'event-dates.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1)
        fh.write('\n')
    print('%d files, %d rows, %d dated on %d days, %d undated' % (files, rows, sum(days.values()), len(days), undated))


if __name__ == '__main__':
    main()
