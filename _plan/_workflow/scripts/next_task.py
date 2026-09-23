#!/usr/bin/env python3
"""
next_task.py -- the one-by-one execution loop for execution/tasks.yaml.

The backlog says what to do; this says what to do NEXT, and moves a task through the
ledger without letting the ledger lie. Run it from anywhere:

    python _plan/_workflow/scripts/next_task.py              the next ready task, in full
    python _plan/_workflow/scripts/next_task.py queue        what is ready, in flight, awaiting
                                                             review, and blocked
    python _plan/_workflow/scripts/next_task.py show ID      one task, in full

    python _plan/_workflow/scripts/next_task.py start  ID
    python _plan/_workflow/scripts/next_task.py finish ID --verify-passed
    python _plan/_workflow/scripts/next_task.py approve ID --by NAME
    python _plan/_workflow/scripts/next_task.py reject  ID --reason TEXT
    python _plan/_workflow/scripts/next_task.py block   ID --reason TEXT
    python _plan/_workflow/scripts/next_task.py unblock ID

THE LEDGER

    todo     not started
    doing    an executor has started it
    review   an agent-draft task whose artifact exists and whose verify passed, waiting for a
             person. This state is why the tool exists: without it a finished draft and a
             half-written one are indistinguishable, and the only honest record of the
             difference ends up in commit messages.
    blocked  cannot proceed; blocked_reason says why. Every human and human-gate task sits
             here until a person acts, so an unattended run moves past it instead of stopping.
    done     finished. For any task a person is involved in, signed_off_by and signed_off_on
             say who and when.

THE RULE THAT MAKES THE REVIEW GATE MEAN SOMETHING

A dependency is satisfied only by `done`. A task waiting on something in `review` is not
ready. The alternative -- letting downstream work build on an unreviewed draft -- turns
"a human must review this" into "a human may look at this later", and in a curation
project that is the difference between a catalogue and a pile of confident guesses.

The cost is that a run can reach a wall of drafts. When it does, `next` moves to the next
task whose inputs ARE done; `queue` shows exactly who is waiting on whom.

Status edits are made in place, line by line, so tasks.yaml keeps its comments, its order
and a one-line diff per transition.
"""

import argparse
import datetime
import io
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit('next_task: pyyaml is required (pip install pyyaml)')

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.dirname(os.path.dirname(HERE))
# EXECUTION_TASKS_FILE points the tool at another copy, which is how it is tested without
# touching the ledger a live run depends on.
TASKS = os.environ.get('EXECUTION_TASKS_FILE') or os.path.join(PLAN, 'execution', 'tasks.yaml')

STATUSES = ('todo', 'doing', 'review', 'blocked', 'done')
HUMAN_INVOLVED = ('agent-draft', 'human', 'human-gate')


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load():
    with io.open(TASKS, encoding='utf-8') as fh:
        doc = yaml.safe_load(fh)
    tasks = {}
    for ph in doc['phases']:
        for st in ph['stages']:
            for t in st['tasks']:
                t['_phase'] = ph['phase']
                t['_stage'] = st['id']
                t['_stage_title'] = st.get('title', '')
                tasks[t['id']] = t
    return tasks


def by_seq(tasks):
    return sorted(tasks.values(), key=lambda t: t['seq'])


def acceptable_inputs(t):
    """Which dependency states let this task START.

    An agent-draft may be drafted on a draft still in review, because a person reviews
    this one too. An agent task may not: nobody reviews agent work, so it must never
    rest on an unreviewed draft. Nothing is ever FINISHED on unfinished inputs; that
    is enforced at approve and finish, not here.
    """
    return ('done', 'review') if t['executor'] == 'agent-draft' else ('done',)


def waiting_on(t, tasks, ok=None):
    ok = ok or acceptable_inputs(t)
    return [d for d in (t.get('depends_on') or [])
            if d in tasks and tasks[d]['status'] not in ok]


def deps_done(t, tasks):
    return not waiting_on(t, tasks)


def unreviewed_inputs(t, tasks):
    return [d for d in (t.get('depends_on') or [])
            if d in tasks and tasks[d]['status'] == 'review']


def downstream_drafts(tid, tasks):
    """Drafts in flight that rest, directly or transitively, on this task."""
    out, frontier = [], [tid]
    while frontier:
        cur = frontier.pop()
        for t in tasks.values():
            if cur in (t.get('depends_on') or []) and t['status'] in ('doing', 'review') \
                    and t['id'] not in out:
                out.append(t['id'])
                frontier.append(t['id'])
    return sorted(out, key=lambda x: tasks[x]['seq'])


def ready(tasks, include_human=False):
    """Tasks that can start now: status todo and every dependency acceptable."""
    out = []
    for t in by_seq(tasks):
        if t['status'] != 'todo' or not deps_done(t, tasks):
            continue
        if t['executor'] in ('human', 'human-gate') and not include_human:
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# In-place ledger edits
# ---------------------------------------------------------------------------

LEDGER_KEYS = ('status', 'signed_off_by', 'signed_off_on', 'blocked_reason',
               'review_note')


def _block_bounds(lines, tid):
    start = None
    pat = re.compile(r'^(\s*)- id: %s\s*$' % re.escape(tid))
    for i, l in enumerate(lines):
        m = pat.match(l)
        if m:
            start, indent = i, len(m.group(1))
            break
    if start is None:
        sys.exit('next_task: no task %s in tasks.yaml' % tid)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        l = lines[j]
        if not l.strip():
            continue
        lead = len(l) - len(l.lstrip(' '))
        if lead <= indent:          # the next list item or an outer key
            end = j
            break
    return start, end, indent + 2


def _q(v):
    s = str(v)
    if re.search(r'[:#\'"\[\]{},&*!|>%@`]|^\s|\s$', s) or s == '':
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def set_ledger(tid, **fields):
    """Rewrite the ledger keys of one task, leaving every other line untouched.

    Pass a value of None to remove a key.
    """
    with io.open(TASKS, encoding='utf-8', newline='') as fh:
        text = fh.read()
    nl = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(nl)
    start, end, ind = _block_bounds(lines, tid)
    pad = ' ' * ind

    block = lines[start:end]
    keep = []
    status_at = None
    for i, l in enumerate(block):
        m = re.match(r'^%s(%s):' % (pad, '|'.join(LEDGER_KEYS)), l)
        if m and i > 0:
            if m.group(1) == 'status':
                status_at = len(keep)
                keep.append(None)          # placeholder, refilled below
            continue
        keep.append(l)
    if status_at is None:
        sys.exit('next_task: %s has no status line' % tid)

    current = {k: v for k, v in _current_ledger(block, pad).items()}
    current.update(fields)

    ledger = ['%sstatus: %s' % (pad, current['status'])]
    for k in LEDGER_KEYS[1:]:
        if current.get(k) not in (None, ''):
            ledger.append('%s%s: %s' % (pad, k, _q(current[k])))

    new_block = keep[:status_at] + ledger + keep[status_at + 1:]
    lines[start:end] = new_block
    with io.open(TASKS, 'w', encoding='utf-8', newline='') as fh:
        fh.write(nl.join(lines))


def _current_ledger(block, pad):
    """Read the existing ledger keys straight off this task's own lines."""
    out = {}
    for l in block[1:]:
        m = re.match(r'^%s(%s):\s?(.*)$' % (pad, '|'.join(LEDGER_KEYS)), l)
        if m:
            out[m.group(1)] = yaml.safe_load(m.group(2)) if m.group(2).strip() else None
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def show(t, tasks):
    w = sys.stdout.write
    w('\n%s  (seq %d)  %s\n' % (t['id'], t['seq'], t['title']))
    w('  phase %s / %s -- %s\n' % (t['_phase'], t['_stage'], t['_stage_title']))
    w('  executor: %s    status: %s    estimate: %g-%g h\n'
      % (t['executor'], t['status'], t['est_hours_low'], t['est_hours_high']))
    if t.get('signed_off_by'):
        w('  signed off: %s on %s\n' % (t['signed_off_by'], t.get('signed_off_on')))
    if t.get('blocked_reason'):
        w('  blocked: %s\n' % t['blocked_reason'])
    if t.get('review_note'):
        w('  review note: %s\n' % t['review_note'])

    deps = t.get('depends_on') or []
    if deps:
        w('\n  DEPENDS ON\n')
        for d in deps:
            w('    %-14s %s\n' % (d, tasks[d]['status'] if d in tasks else '(missing)'))

    for label, key in (('READ FIRST', 'reads'), ('STEPS', 'steps'),
                       ('CREATES', 'produces'), ('EDITS', 'modifies')):
        vals = t.get(key) or []
        if vals:
            w('\n  %s\n' % label)
            for i, v in enumerate(vals, 1):
                w(('    %d. %s\n' % (i, v)) if key == 'steps' else ('    - %s\n' % v))

    w('\n  VERIFY\n    %s\n' % str(t['verify']).strip().replace('\n', '\n    '))
    w('\n  DONE WHEN\n    %s\n\n' % str(t['done_when']).strip())

    if t['executor'] == 'agent':
        w('  When verify passes:  next_task.py finish %s --verify-passed\n' % t['id'])
    elif t['executor'] == 'agent-draft':
        w('  When verify passes:  next_task.py finish %s --verify-passed\n' % t['id'])
        w('  That moves it to REVIEW, not done. A person then runs:\n')
        w('                       next_task.py approve %s --by NAME\n' % t['id'])
    else:
        w('  This needs a person. An agent should not attempt it. It can be marked:\n')
        w('                       next_task.py block %s --reason "awaiting <who>"\n' % t['id'])
        w('  and a person closes it with:  next_task.py approve %s --by NAME\n' % t['id'])


def cmd_next(tasks, args):
    doing = [t for t in by_seq(tasks) if t['status'] == 'doing']
    if doing and not args.skip_doing:
        t = doing[0]
        sys.stdout.write('A task is already in progress; finish it before starting another '
                         '(or pass --skip-doing):\n')
        show(t, tasks)
        return 0
    r = ready(tasks, include_human=args.include_human)
    if not r:
        sys.stdout.write('Nothing is ready.\n')
        cmd_queue(tasks, args)
        return 1
    show(r[0], tasks)
    if len(r) > 1:
        sys.stdout.write('  (%d other tasks are also ready; next in seq: %s)\n'
                         % (len(r) - 1, ', '.join(t['id'] for t in r[1:6])))
    return 0


def cmd_queue(tasks, args):
    w = sys.stdout.write
    counts = {s: 0 for s in STATUSES}
    for t in tasks.values():
        counts[t['status']] = counts.get(t['status'], 0) + 1
    total = len(tasks)
    w('\nledger: %s   (%d of %d done, %.1f%%)\n'
      % ('  '.join('%s=%d' % (s, counts.get(s, 0)) for s in STATUSES),
         counts['done'], total, 100.0 * counts['done'] / total))

    def section(title, items, fmt):
        w('\n%s (%d)\n' % (title, len(items)))
        for t in items[:args.limit]:
            w(fmt(t))
        if len(items) > args.limit:
            w('    ... %d more\n' % (len(items) - args.limit))

    line = lambda t: '    %4d  %-12s %-11s %s\n' % (t['seq'], t['id'], t['executor'], t['title'][:60])

    section('IN PROGRESS', [t for t in by_seq(tasks) if t['status'] == 'doing'], line)

    # Review in seq order: a draft whose inputs are all done can be approved now;
    # one resting on another draft must wait for that draft first.
    rev = [t for t in by_seq(tasks) if t['status'] == 'review']
    now = [t for t in rev if not waiting_on(t, tasks, ok=('done',))]
    later = [t for t in rev if waiting_on(t, tasks, ok=('done',))]
    section('AWAITING REVIEW, can be approved now -- `approve ID --by NAME`', now, line)
    section('AWAITING REVIEW, resting on another unreviewed draft -- approve its inputs first',
            later,
            lambda t: line(t) + '          rests on: %s\n'
            % ', '.join(unreviewed_inputs(t, tasks)))
    section('BLOCKED',
            [t for t in by_seq(tasks) if t['status'] == 'blocked'],
            lambda t: line(t) + '          reason: %s\n' % (t.get('blocked_reason') or '(none given)'))
    section('READY FOR AN AGENT', ready(tasks), line)
    section('READY FOR A PERSON',
            [t for t in ready(tasks, include_human=True) if t['executor'] in ('human', 'human-gate')],
            line)

    # What is the review queue actually holding up?
    held = {}
    for t in by_seq(tasks):
        if t['status'] != 'todo':
            continue
        for d in waiting_on(t, tasks):
            if tasks[d]['status'] in ('review', 'blocked'):
                held.setdefault(d, []).append(t['id'])
    if held:
        w('\nWHAT THE REVIEW AND BLOCKED QUEUES ARE HOLDING UP\n')
        for d in sorted(held, key=lambda x: tasks[x]['seq']):
            w('    %-12s (%s) blocks %d: %s\n'
              % (d, tasks[d]['status'], len(held[d]), ', '.join(held[d][:6])
                 + (' ...' if len(held[d]) > 6 else '')))
    w('\n')
    return 0


def today():
    return datetime.date.today().isoformat()


def need(t, *allowed):
    if t['status'] not in allowed:
        sys.exit('next_task: %s is %s; this transition needs it to be %s'
                 % (t['id'], t['status'], ' or '.join(allowed)))


def cmd_start(tasks, args):
    t = tasks[args.id]
    need(t, 'todo')
    if t['executor'] in ('human', 'human-gate'):
        sys.exit('next_task: %s is executor=%s -- a person does this. Use `block %s '
                 '--reason ...` to park it, or `approve` once it is done.'
                 % (t['id'], t['executor'], t['id']))
    w = waiting_on(t, tasks)
    if w:
        sys.exit('next_task: %s is not ready; it waits on %s'
                 % (t['id'], ', '.join('%s (%s)' % (d, tasks[d]['status']) for d in w)))
    set_ledger(t['id'], status='doing')
    print('%s -> doing' % t['id'])
    return 0


def cmd_finish(tasks, args):
    t = tasks[args.id]
    need(t, 'doing')
    if not args.verify_passed:
        sys.exit('next_task: run the task\'s verify first, then pass --verify-passed.\n'
                 '  verify: %s' % str(t['verify']).strip())
    if t['executor'] == 'agent':
        set_ledger(t['id'], status='done', review_note=None, blocked_reason=None)
        print('%s -> done' % t['id'])
    elif t['executor'] == 'agent-draft':
        set_ledger(t['id'], status='review', blocked_reason=None)
        print('%s -> review. It is NOT done until a person runs: approve %s --by NAME'
              % (t['id'], t['id']))
    else:
        sys.exit('next_task: %s is executor=%s; a person closes it with approve'
                 % (t['id'], t['executor']))
    return 0


def cmd_approve(tasks, args):
    t = tasks[args.id]
    if t['executor'] == 'agent':
        sys.exit('next_task: %s is executor=agent and needs no sign-off; use finish' % t['id'])
    if t['executor'] == 'agent-draft':
        need(t, 'review')
    else:
        need(t, 'todo', 'blocked', 'doing')
    # Nothing is finished on unfinished inputs. This is what forces review into
    # dependency order: a draft built on a draft cannot be approved first.
    w = waiting_on(t, tasks, ok=('done',))
    if w:
        sys.exit('next_task: %s cannot be signed off while its inputs are unfinished: %s\n'
                 '  approve those first, in seq order.'
                 % (t['id'], ', '.join('%s (%s)' % (d, tasks[d]['status']) for d in w)))
    if not args.by or not args.by.strip():
        sys.exit('next_task: --by NAME is required; a sign-off without a name is not one')
    set_ledger(t['id'], status='done', signed_off_by=args.by.strip(),
               signed_off_on=args.on or today(), blocked_reason=None,
               review_note=args.note)
    print('%s -> done, signed off by %s' % (t['id'], args.by.strip()))
    return 0


def cmd_reject(tasks, args):
    t = tasks[args.id]
    need(t, 'review')
    set_ledger(t['id'], status='doing', review_note=args.reason)
    print('%s -> doing, returned to the agent: %s' % (t['id'], args.reason))
    hit = downstream_drafts(t['id'], tasks)
    if hit:
        print('\n  WARNING: %d draft(s) in flight were built on this one and may need '
              'rework once it is fixed:\n    %s'
              % (len(hit), ', '.join('%s (%s)' % (x, tasks[x]['status']) for x in hit)))
        print('  Reject them too if the change invalidates them; otherwise review them '
              'after this one is approved.')
        print('  Until one or the other happens, verify_execution.py reports them as '
              'ledger/ahead-of-inputs -- correctly: they rest on a draft that was just '
              'thrown out.')
    return 0


def cmd_block(tasks, args):
    t = tasks[args.id]
    need(t, 'todo', 'doing')
    set_ledger(t['id'], status='blocked', blocked_reason=args.reason)
    print('%s -> blocked: %s' % (t['id'], args.reason))
    return 0


def cmd_unblock(tasks, args):
    t = tasks[args.id]
    need(t, 'blocked')
    set_ledger(t['id'], status='todo', blocked_reason=None)
    print('%s -> todo' % t['id'])
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd')

    p = sub.add_parser('next', help='the next ready task (default)')
    p.add_argument('--include-human', action='store_true',
                   help='also offer human and human-gate tasks')
    p.add_argument('--skip-doing', action='store_true',
                   help='offer a new task even if one is in progress')
    p.add_argument('--limit', type=int, default=12)

    p = sub.add_parser('queue', help='ready, in flight, review and blocked')
    p.add_argument('--limit', type=int, default=12)

    p = sub.add_parser('show', help='one task in full')
    p.add_argument('id')

    for name in ('start', 'unblock'):
        p = sub.add_parser(name)
        p.add_argument('id')

    p = sub.add_parser('finish', help='agent: doing -> done; agent-draft: doing -> review')
    p.add_argument('id')
    p.add_argument('--verify-passed', action='store_true',
                   help='attest that the task\'s verify was run and passed')

    p = sub.add_parser('approve', help='a person signs off: review -> done, or closes a human task')
    p.add_argument('id')
    p.add_argument('--by', required=True)
    p.add_argument('--on', help='date, default today')
    p.add_argument('--note')

    for name in ('reject', 'block'):
        p = sub.add_parser(name)
        p.add_argument('id')
        p.add_argument('--reason', required=True)

    args = ap.parse_args()
    if args.cmd is None:
        args = ap.parse_args(['next'] + sys.argv[1:])

    tasks = load()
    if getattr(args, 'id', None) and args.id not in tasks:
        sys.exit('next_task: no task %s' % args.id)

    return {
        'next': cmd_next, 'queue': cmd_queue,
        'show': lambda ts, a: show(ts[a.id], ts) or 0,
        'start': cmd_start, 'finish': cmd_finish, 'approve': cmd_approve,
        'reject': cmd_reject, 'block': cmd_block, 'unblock': cmd_unblock,
    }[args.cmd](tasks, args)


if __name__ == '__main__':
    sys.exit(main())
