#!/usr/bin/env python3
"""Every validation warning is resolved or carries a recorded triage decision (P1-S13-T04; 04 S12, 14 Phase 1 exit).

Phase 1 exits on "Zero validation errors; quality warnings triaged rather than suppressed." Tier 4 never blocks
(04 S12: a red X breeds compliance, a visible dashboard better behaviour), and tier 3's warnings do not block
either, so neither says whether anybody looked. data/_analysis/warning-triage.yaml is where somebody did: one
row per decision, naming its `rule`, the `decision` (accepted: the signal is right and stays; deferred: a named
`owner` -- a ledger task or a pull request -- will clear it), a `reason`, `decided_by` and `decided_on`, and the
`findings` it covers, one line each by `entity` (plus `detail` where the rule fires more than once per entity
or its subject can change, and an optional per-line `note`). No rule is switched off: a warning that is not
listed fails here, so a new one is triaged, not absorbed by a blanket row.

Reads the validator's JSON on stdin and asserts:

  errors     the report carries zero blocking findings.
  shape      every row and line is well formed: a known decision, an owner on a deferral, a reason, who
             decided and a date not after today; no line twice.
  triaged    every warning and quality finding matches a line, by (rule, entity, detail).

A line no finding matches is a warning resolved since it was triaged. It is listed, and fails only under
--strict, so a fix never waits on the triage file.

    bench validate --tier all --json | python scripts/check_warnings_triaged.py              # the verify
    bench validate --tier all --json | python scripts/check_warnings_triaged.py --markdown   # the table
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TRIAGE = 'data/_analysis/warning-triage.yaml'
DECISIONS = ('accepted', 'deferred')
TRIAGED = ('warning', 'quality')                 # the severities triaged here; `blocking` is an error
ROW_REQUIRED = {'rule', 'decision', 'reason', 'decided_by', 'decided_on', 'findings'}
ROW_OPTIONAL = {'owner'}
LINE_REQUIRED = {'entity'}
LINE_OPTIONAL = {'detail', 'note'}


def _subset(msg):
    m = re.match(r'^(\S+) replaces (\S+) with fewer terms, dropping (.*): confirm the drop$', msg)
    return m and '%s %s: %s' % m.groups()


def _waived(msg):
    return ', '.join(re.findall(r'(?:waived: |\), )([a-z_]+) \(', msg)) or None


def _submission(msg):
    m = re.search(r"submission_process (\[[^\]]*\]|unset)", msg)
    return m and ', '.join(sorted(re.findall(r"'([^']+)'", m.group(1)))) or (m and m.group(1))


def _archive(msg):
    m = re.match(r'^archive_status (\S+?)(?::|$)', msg)
    return m and m.group(1)


# The rules whose lines carry a `detail`: one that fires more than once per entity (a subset, a field), or whose
# subject can change under a decision (the waived fields, the submission process, the archive state). A decision
# is about that subject; when it changes the line no longer matches and the new state is triaged afresh.
DETAIL = {
    'subset-drops-terms': _subset,
    'material-waived': _waived,
    'private-server-submission': _submission,
    'unarchived-source': _archive,
}


def detail(finding):
    fn = DETAIL.get(finding.get('rule'))
    return fn(finding.get('message') or '') if fn else None


def key(rule, entity, det):
    return (rule, entity, det)


def show(k):
    return '%s %s%s' % (k[0], k[1], ' [%s]' % k[2] if k[2] else '')


def load(root):
    path = os.path.join(root, *TRIAGE.split('/'))
    if not os.path.exists(path):
        return None, ['%s does not exist' % TRIAGE]
    with open(path, encoding='utf-8') as fh:
        doc = yaml.safe_load(fh)
    rows = doc.get('decisions') if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return None, ['%s: needs a list `decisions`' % TRIAGE]
    return rows, []


def lines(rows, today):
    """({(rule, entity, detail): (row index, decision)}, errors) over the triage rows."""
    errs, out = [], {}
    for i, row in enumerate(rows):
        where = '%s decisions[%d]' % (TRIAGE, i)
        if not isinstance(row, dict):
            errs.append('%s is not a mapping' % where)
            continue
        where = '%s (%s)' % (where, row.get('rule'))
        if not ROW_REQUIRED <= set(row) <= ROW_REQUIRED | ROW_OPTIONAL:
            errs.append('%s: keys must be %s, optionally %s; not %s' % (where, sorted(ROW_REQUIRED),
                                                                       sorted(ROW_OPTIONAL), sorted(row)))
        if row.get('decision') not in DECISIONS:
            errs.append('%s: decision %r is not one of %s' % (where, row.get('decision'), ', '.join(DECISIONS)))
        if row.get('decision') == 'deferred' and not (isinstance(row.get('owner'), str) and row['owner'].strip()):
            errs.append('%s: a deferral names its owner, the task or pull request that clears it' % where)
        if not (isinstance(row.get('reason'), str) and row['reason'].strip()):
            errs.append('%s: no reason' % where)
        if not (isinstance(row.get('decided_by'), str) and row['decided_by'].strip()):
            errs.append('%s: no decided_by: a triage decision names who made it' % where)
        when = row.get('decided_on')
        if not isinstance(when, dt.date):
            errs.append('%s: decided_on %r is not a date' % (where, when))
        elif when > today:
            errs.append('%s: decided_on %s is after today, %s' % (where, when, today))
        found = row.get('findings')
        if not (isinstance(found, list) and found):
            errs.append('%s: `findings` lists the lines the decision covers' % where)
            continue
        for j, line in enumerate(found):
            at = '%s findings[%d]' % (where, j)
            if not (isinstance(line, dict) and LINE_REQUIRED <= set(line) <= LINE_REQUIRED | LINE_OPTIONAL):
                errs.append('%s: a line is {entity, optionally detail and note}, not %r' % (at, line))
                continue
            if (row.get('rule') in DETAIL) != ('detail' in line):
                errs.append('%s: %s' % (at, 'rule %s lines carry a detail' % row.get('rule')
                                        if row.get('rule') in DETAIL else 'rule %s lines carry no detail'
                                        % row.get('rule')))
            k = key(row.get('rule'), line['entity'], line.get('detail'))
            if k in out:
                errs.append('%s: %s is already triaged by decisions[%d]' % (at, show(k), out[k][0]))
                continue
            out[k] = (i, row.get('decision'))
    return out, errs


def check(report, rows, today, strict=False):
    """(errors, resolved lines, {rule: Counter}) for a validator report against the triage rows."""
    errs = []
    if report.get('blocking') or report.get('exit_code'):
        bad = [f for f in report.get('findings', []) if f.get('severity') not in TRIAGED]
        errs.append('%d blocking finding(s): "Zero validation errors" is the exit criterion' % len(bad)
                    if bad else 'the validator exited %s' % report.get('exit_code'))
        errs += ['  %s %s: %s' % (f.get('rule'), f.get('entity'), f.get('message')) for f in bad[:20]]
    decided, shape = lines(rows, today)
    errs += shape
    tally = collections.defaultdict(collections.Counter)
    hit = set()
    for f in report.get('findings', []):
        if f.get('severity') not in TRIAGED:
            continue
        k = key(f.get('rule'), f.get('entity'), detail(f))
        rule = '%s/%s' % (f.get('tier'), f.get('rule'))
        tally[rule]['findings'] += 1
        if k in decided:
            hit.add(k)
            tally[rule][decided[k][1]] += 1
        else:
            tally[rule]['untriaged'] += 1
            errs.append('untriaged: %s: %s' % (show(k), f.get('message')))
    resolved = sorted(k for k in decided if k not in hit)
    if strict:
        errs += ['resolved, still listed: %s (drop the line from %s)' % (show(k), TRIAGE) for k in resolved]
    return errs, resolved, tally


def table(tally):
    out = ['| Tier/rule | Findings | Accepted | Deferred | Untriaged |', '| --- | ---: | ---: | ---: | ---: |']
    total = collections.Counter()
    for rule in sorted(tally, key=lambda r: (r.split('/')[0], r)):
        c = tally[rule]
        total.update(c)
        out.append('| %s | %d | %d | %d | %d |' % (rule, c['findings'], c['accepted'], c['deferred'], c['untriaged']))
    out.append('| **total** | **%d** | **%d** | **%d** | **%d** |' % (total['findings'], total['accepted'],
                                                                      total['deferred'], total['untriaged']))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--today', type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date(),
                    help='YYYY-MM-DD (default: today in UTC, as CI runs)')
    ap.add_argument('--strict', action='store_true', help='also fail on a triaged line no finding matches any more')
    ap.add_argument('--markdown', action='store_true', help='print the accounting as a Markdown table')
    a = ap.parse_args(argv)
    try:
        report = json.load(sys.stdin)
    except ValueError as e:
        print('FAIL  stdin is not the JSON of `bench validate --tier all --json`: %s' % e)
        return 2
    rows, errs = load(a.root)
    if rows is not None:
        errs, resolved, tally = check(report, rows, a.today, a.strict)
    if errs:
        for e in errs:
            print('FAIL  ' + e)
        print('%d problem(s)' % sum(1 for e in errs if not e.startswith('  ')))
        return 1
    if a.markdown:
        print('\n'.join(table(tally)))
    for k in resolved:
        print('note  resolved since triaged: %s' % show(k))
    n = sum(c['findings'] for c in tally.values())
    print('OK    0 blocking; %d warning and quality findings, every one triaged (%d accepted, %d deferred); '
          '%d triaged line(s) resolved since' % (n, sum(c['accepted'] for c in tally.values()),
                                                 sum(c['deferred'] for c in tally.values()), len(resolved)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
