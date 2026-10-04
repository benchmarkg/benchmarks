"""`bench report <name>` (P3-S1-T07; 05 S3). Phase 3 gates on three of 05 S3's reports, so they exist now:

    completeness   per claim: the resolved material fields, how many are populated, and condition_completeness
                   with its denominator (04 S8)
    conflicts      claims about one measurement -- benchmark, subset, metric, system -- whose values disagree,
                   with every disagreeing field named
    quality        outstanding validation warnings and tier-4 quality signals, grouped by rule

Each report is a function of the repository tree and nothing else: rows in a fixed order, no clock, no
host, so a re-run gives byte-identical output and later phases can gate on it. `render()` writes any of
them as md, json or csv (05 S3's --format).
"""
from __future__ import annotations

import csv
import io
import json

FORMATS = ('md', 'json', 'csv')


def render(report: dict, fmt: str) -> str:
    """`report` is {'report': name, 'summary': {...}, 'columns': [...], 'rows': [{...}, ...]}."""
    if fmt == 'json':
        return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    cols = report['columns']
    if fmt == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow(cols)
        for r in report['rows']:
            w.writerow([_cell(r.get(c)) for c in cols])        # get-default: a row may leave a column empty
        return buf.getvalue()
    if fmt != 'md':
        raise ValueError('format %r is not one of %s' % (fmt, ', '.join(FORMATS)))
    lines = ['# bench report %s' % report['report'], '']
    lines += ['- %s: %s' % (k, _cell(v)) for k, v in sorted(report['summary'].items())]
    lines += ['', '| %s |' % ' | '.join(cols), '|' + ' --- |' * len(cols)]
    for r in report['rows']:
        lines.append('| %s |' % ' | '.join(_cell(_short(r.get(c))).replace('|', '\\|') for c in cols))  # get-default: as above
    if not report['rows']:
        lines.append('| %s |' % ' | '.join(['(none)'] + [''] * (len(cols) - 1)))
    return '\n'.join(lines) + '\n'


MD_LIST = 20       # markdown is for reading; json and csv carry every item


def _short(v):
    if isinstance(v, (list, tuple)) and len(v) > MD_LIST:
        return list(v[:MD_LIST]) + ['... and %d more' % (len(v) - MD_LIST)]
    return v


def _cell(v) -> str:
    if v is None:
        return ''
    if isinstance(v, (list, tuple)):
        return ', '.join(_cell(x) for x in v)
    if isinstance(v, dict):
        return '; '.join('%s=%s' % (k, _cell(v[k])) for k in sorted(v))
    if isinstance(v, float):
        return repr(round(v, 6))
    return str(v)
