#!/usr/bin/env python3
"""Time each entry's curation, and report the median the 20-entry checkpoint needs.

14-roadmap.md "The 20-entry checkpoint" asks for two numbers and says how they must be taken:
the median minutes per entry, "timed, per entry, with the source-reading and archiving
included", and the copilot speedup, "ten entries drafted with the F6 copilot against ten
drafted without, same curator, interleaved". Stopping rule (a) fires on the first of them
above 60 minutes. This script is the stopwatch and the arithmetic; it does not estimate.

    python scripts/curation_timer.py start ENTRY_ID --curator HANDLE --copilot on|off
    python scripts/curation_timer.py stop                 # appends one record to the ledger
    python scripts/curation_timer.py cancel               # drops the open timer, records nothing
    python scripts/curation_timer.py status
    python scripts/curation_timer.py --report [--json]    # median, quartiles, copilot split
    python scripts/curation_timer.py --self-test

The timed window. `start` goes before the first source is opened and `stop` after the entry's
Source records carry their archive stamps (archive_url, or archive_status: pending|failed).
Reading, archiving, quoting and drafting are all inside it; review by a second person is not,
because it is a different person's time. There is no pause: an interrupted entry is cancelled
and restarted, or its record overstates the work and is visible as an outlier in the report.
There is also no way to enter a duration after the fact, because "not estimated afterwards"
is the point of the measurement.

Ledger. metrics/curation-rate.jsonl, one JSON object per line, append-only:

    {"entry_id": "swe-bench", "curator": "handle", "copilot": true,
     "start": "2026-09-24T09:00:00Z", "stop": "2026-09-24T09:41:30Z", "minutes": 41.5}

`minutes` is written for the reader; --report recomputes it from start and stop and rejects a
line where the two disagree. The open timer lives in metrics/.curation-timer.json, which is
never committed.

Statistics. Median and quartiles are the inclusive (linear-interpolation) quantiles of the
per-entry minutes: statistics.quantiles(method='inclusive'), numpy's default, Excel's
QUARTILE.INC. Over one record all three are that record. The copilot split reports n and
median per arm and the ratio of the on-median to the off-median; below 1.0 the copilot is
faster. The split is printed with the curators each arm contains, because the checkpoint's
comparison is only valid for the same curator.

Exit codes: 0 ok; 1 a ledger line is malformed, or a command is used out of order (stop with no
open timer, start with one open); 2 the ledger is empty, so there is no median to report.
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, 'metrics', 'curation-rate.jsonl')
STATE = os.path.join(ROOT, 'metrics', '.curation-timer.json')
TIMESTAMP = '%Y-%m-%dT%H:%M:%SZ'
RULE_A_MINUTES = 60  # 14-roadmap.md Stopping rules (a)


class LedgerError(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def fmt(t):
    return t.strftime(TIMESTAMP)


def parse(s):
    return datetime.strptime(s, TIMESTAMP).replace(tzinfo=timezone.utc)


def start(entry_id, curator, copilot, state=STATE, now=None):
    if os.path.exists(state):
        with open(state, encoding='utf-8') as f:
            open_ = json.load(f)
        raise LedgerError('a timer is already open for %s (started %s); stop or cancel it first'
                          % (open_['entry_id'], open_['start']))
    rec = {'entry_id': entry_id, 'curator': curator, 'copilot': copilot, 'start': fmt(now or utcnow())}
    os.makedirs(os.path.dirname(state), exist_ok=True)
    with open(state, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rec, f)
    return rec


def stop(ledger=LEDGER, state=STATE, now=None):
    if not os.path.exists(state):
        raise LedgerError('no timer is open; run `start` first')
    with open(state, encoding='utf-8') as f:
        rec = json.load(f)
    end = now or utcnow()
    minutes = (end - parse(rec['start'])).total_seconds() / 60
    if minutes <= 0:
        raise LedgerError('stop (%s) is not after start (%s)' % (fmt(end), rec['start']))
    rec['stop'] = fmt(end)
    rec['minutes'] = round(minutes, 2)
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    with open(ledger, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    os.remove(state)
    return rec


def cancel(state=STATE):
    if not os.path.exists(state):
        raise LedgerError('no timer is open')
    with open(state, encoding='utf-8') as f:
        rec = json.load(f)
    os.remove(state)
    return rec


def load(ledger=LEDGER):
    """Every record in the ledger, with `minutes` recomputed from its timestamps."""
    if not os.path.exists(ledger):
        return []
    out = []
    with open(ledger, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                for k in ('entry_id', 'curator', 'copilot', 'start', 'stop'):
                    if k not in r:
                        raise LedgerError('missing %r' % k)
                if not isinstance(r['copilot'], bool):
                    raise LedgerError('copilot must be true or false, got %r' % (r['copilot'],))
                minutes = (parse(r['stop']) - parse(r['start'])).total_seconds() / 60
            except (ValueError, LedgerError) as e:
                raise LedgerError('%s:%d: %s' % (ledger, n, e))
            if minutes <= 0:
                raise LedgerError('%s:%d: stop is not after start' % (ledger, n))
            if 'minutes' in r and abs(r['minutes'] - minutes) > 0.01:
                raise LedgerError('%s:%d: minutes %s disagrees with start/stop (%.2f)'
                                  % (ledger, n, r['minutes'], minutes))
            r['minutes'] = minutes
            out.append(r)
    return out


def quartiles(xs):
    """(Q1, median, Q3), inclusive method; a single value is its own quartiles."""
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0], xs[0], xs[0]
    q1, q2, q3 = statistics.quantiles(xs, n=4, method='inclusive')
    return q1, q2, q3


def report(records):
    if not records:
        return None
    q1, med, q3 = quartiles([r['minutes'] for r in records])
    arms = {}
    for name, flag in (('on', True), ('off', False)):
        rs = [r for r in records if r['copilot'] is flag]
        arms[name] = {
            'n': len(rs),
            'median': statistics.median(r['minutes'] for r in rs) if rs else None,
            'curators': sorted({r['curator'] for r in rs}),
        }
    on, off = arms['on']['median'], arms['off']['median']
    return {
        'n': len(records),
        'median': med,
        'q1': q1,
        'q3': q3,
        'copilot': arms,
        'on_off_ratio': on / off if on is not None and off is not None else None,
        'rule_a_fires': med > RULE_A_MINUTES,
    }


def render(rep):
    lines = ['entries timed   %d' % rep['n'],
             'median          %.2f min' % rep['median'],
             'quartiles       Q1 %.2f  Q3 %.2f  (IQR %.2f)' % (rep['q1'], rep['q3'], rep['q3'] - rep['q1'])]
    for name in ('on', 'off'):
        a = rep['copilot'][name]
        med = '%.2f min' % a['median'] if a['median'] is not None else '-'
        lines.append('copilot %-3s     n %d  median %s  curators %s'
                     % (name, a['n'], med, ', '.join(a['curators']) or '-'))
    if rep['on_off_ratio'] is None:
        lines.append('on/off ratio    - (one arm is empty)')
    else:
        lines.append('on/off ratio    %.4f  (copilot %s by %.1f%%)'
                     % (rep['on_off_ratio'], 'faster' if rep['on_off_ratio'] < 1 else 'slower',
                        abs(1 - rep['on_off_ratio']) * 100))
    if rep['on_off_ratio'] is not None and rep['copilot']['on']['curators'] != rep['copilot']['off']['curators']:
        lines.append('WARNING         the two arms have different curators; the checkpoint '
                     'compares the same curator')
    if rep['rule_a_fires']:
        lines.append('STOPPING RULE (a) median exceeds %d min: re-cut the allocation before entry 21 '
                     '(14-roadmap.md Stopping rules)' % RULE_A_MINUTES)
    return '\n'.join(lines)


def self_test():
    """Round-trip one timed entry through a scratch ledger. It checks only what its author believed."""
    with tempfile.TemporaryDirectory() as d:
        ledger, state = os.path.join(d, 'l.jsonl'), os.path.join(d, 's.json')
        t0 = parse('2026-01-01T10:00:00Z')
        start('probe', 'self-test', True, state=state, now=t0)
        try:
            start('probe-2', 'self-test', False, state=state, now=t0)
            raise AssertionError('second start was accepted')
        except LedgerError:
            pass
        stop(ledger=ledger, state=state, now=parse('2026-01-01T10:45:00Z'))
        assert not os.path.exists(state)
        rep = report(load(ledger))
        assert rep['n'] == 1 and rep['median'] == 45.0, rep
    print('self-test ok')
    return 0


def main(argv=None, ledger=LEDGER, state=STATE, out=None):
    out = out or sys.stdout
    # --ledger is accepted before or after `stop`, so neither spelling silently hits the live ledger.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--ledger', default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0], parents=[common])
    p.add_argument('--report', action='store_true', help='print median, quartiles and the copilot split')
    p.add_argument('--json', action='store_true', help='with --report, print JSON')
    p.add_argument('--self-test', action='store_true')
    sub = p.add_subparsers(dest='cmd')
    s = sub.add_parser('start')
    s.add_argument('entry_id')
    s.add_argument('--curator', required=True, help='a handle, not an e-mail: the ledger is public')
    s.add_argument('--copilot', required=True, choices=['on', 'off'])
    sub.add_parser('stop', parents=[common])
    sub.add_parser('cancel')
    sub.add_parser('status')
    a = p.parse_args(argv)
    a.ledger = getattr(a, 'ledger', ledger)

    try:
        if a.self_test:
            return self_test()
        if a.report:
            rep = report(load(a.ledger))
            if rep is None:
                print('no timed entries in %s' % a.ledger, file=out)
                return 2
            print(json.dumps(rep, indent=2) if a.json else render(rep), file=out)
            return 0
        if a.cmd == 'start':
            rec = start(a.entry_id, a.curator, a.copilot == 'on', state=state)
            print('timing %s (copilot %s) from %s' % (rec['entry_id'], a.copilot, rec['start']), file=out)
        elif a.cmd == 'stop':
            rec = stop(ledger=a.ledger, state=state)
            print('%s: %.2f min, appended to %s' % (rec['entry_id'], rec['minutes'], a.ledger), file=out)
        elif a.cmd == 'cancel':
            rec = cancel(state=state)
            print('cancelled %s, nothing recorded' % rec['entry_id'], file=out)
        elif a.cmd == 'status':
            if os.path.exists(state):
                with open(state, encoding='utf-8') as f:
                    rec = json.load(f)
                mins = (utcnow() - parse(rec['start'])).total_seconds() / 60
                print('open: %s since %s (%.1f min)' % (rec['entry_id'], rec['start'], mins), file=out)
            else:
                print('no timer open', file=out)
        else:
            p.print_help(out)
        return 0
    except LedgerError as e:
        print('error: %s' % e, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
