#!/usr/bin/env python3
"""
verify_execution.py -- structural checks for the execution backlog.

`verify_corpus.py` checks that the sixteen design documents agree with each other.
This checks the thing built from them: `_plan/execution/tasks.yaml`, the Phase /
Stage / Task backlog an agent executes one item at a time.

    python _plan/_workflow/scripts/verify_execution.py

Exit 0 if every check passes, 1 otherwise.

A backlog fails in ways a prose plan cannot, and each check below exists for one:

  * A dependency that resolves to nothing, so an agent picks up a "ready" task and
    finds its input was never created.
  * A cycle, so nothing is ever ready.
  * A forward dependency -- a Phase 2 task waiting on Phase 4 -- which silently
    reorders the roadmap.
  * Two tasks that both claim to produce the same file, so whichever runs second
    overwrites work it did not know about.
  * A `verify` that cannot fail. This is the worst one: an agent runs it, sees
    green, and records a task as done that was never done.
  * An `executor` of "agent" on work that requires judgement an agent does not
    have, which is how you get 320 confident catalogue entries nobody checked --
    the exact outcome the project exists to prevent.
"""

import io
import os
import re
import sys
from collections import Counter, defaultdict

try:
    import yaml
except ImportError:
    sys.exit('verify_execution: pyyaml is required (pip install pyyaml)')

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_DIR = os.path.dirname(os.path.dirname(HERE))
# EXECUTION_TASKS_FILE points at another copy, for testing without touching the ledger.
TASKS = os.environ.get('EXECUTION_TASKS_FILE') or os.path.join(PLAN_DIR, 'execution', 'tasks.yaml')

EXECUTORS = ('agent', 'agent-draft', 'human', 'human-gate')

TASK_ID = re.compile(r'^P(\d)-S(\d+)-T(\d+)$')
STAGE_ID = re.compile(r'^P(\d)-S(\d+)$')

# A verify string that matches one of these and contains no command is not a
# verification, it is a hope.
WEAK_VERIFY = re.compile(
    r'^\s*(review|check that it looks|confirm it looks|make sure it seems|'
    r'eyeball|sanity[- ]check|looks correct|verify manually)\b', re.I)

# Something that could plausibly be run or mechanically evaluated.
HAS_COMMAND = re.compile(
    r'`[^`]+`|\b(pytest|python|py|bench|npm|npx|pnpm|yarn|node|deno|bun|tsc|'
    r'vitest|jest|playwright|astro|vite|eslint|prettier|git|grep|rg|sed|awk|'
    r'ruff|mypy|black|make|just|curl|jq|yq|yamllint|shellcheck|pre-commit|gh|'
    r'docker|cargo|go|sqlite3|duckdb|zenodo|pagefind)\b')

# An honest statement that no machine check is possible.
HONEST_MANUAL = re.compile(
    r'\b(human|judgement|judgment|cannot be machine|not machine-verifiable|'
    r'manual|by hand|reviewer|specialist|no automated)\b', re.I)

failures = []
notes = []


def fail(check, msg):
    failures.append((check, msg))


def note(msg):
    notes.append(msg)


def load():
    if not os.path.exists(TASKS):
        sys.exit('verify_execution: %s does not exist yet' % TASKS)
    with io.open(TASKS, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


DOC = load()
PHASES = DOC.get('phases') or []

TASKS_BY_ID = {}
ORDER = []          # task ids in document order
PHASE_OF = {}
STAGE_OF = {}

for ph in PHASES:
    pn = ph.get('phase')
    for st in (ph.get('stages') or []):
        for t in (st.get('tasks') or []):
            tid = t.get('id')
            ORDER.append(tid)
            if tid in TASKS_BY_ID:
                fail('ids/duplicate', 'task id %r appears more than once' % tid)
                continue
            TASKS_BY_ID[tid] = t
            PHASE_OF[tid] = pn
            STAGE_OF[tid] = st.get('id')


# ---------------------------------------------------------------------------

def check_shape():
    required = ('id', 'title', 'executor', 'depends_on', 'reads', 'steps',
                'produces', 'verify', 'done_when')
    # 'modifies' is optional: a task that only creates new files has none.
    for tid, t in TASKS_BY_ID.items():
        for f in required:
            if f not in t:
                fail('shape/missing-field', '%s has no %r field' % (tid, f))
            elif t[f] in (None, '', []):
                if f == 'depends_on':
                    continue          # legitimately empty for a ready task
                if f == 'produces':
                    # Three kinds of task legitimately create no new file:
                    # a gate, whose output is a decision; a human credential or
                    # account action, whose output must never be in the repo;
                    # and a task that only edits files another task created.
                    if t.get('executor') in ('human-gate', 'human'):
                        continue
                    if t.get('modifies'):
                        continue
                fail('shape/empty-field', '%s has an empty %r' % (tid, f))


def check_ids():
    for tid in TASKS_BY_ID:
        m = TASK_ID.match(tid or '')
        if not m:
            fail('ids/format',
                 '%r is not of the form P<phase>-S<stage>-T<nn>' % tid)
            continue
        if int(m.group(1)) != PHASE_OF[tid]:
            fail('ids/phase-mismatch',
                 '%s sits in phase %s' % (tid, PHASE_OF[tid]))
        if STAGE_OF[tid] != 'P%s-S%s' % (m.group(1), m.group(2)):
            fail('ids/stage-mismatch',
                 '%s sits in stage %s' % (tid, STAGE_OF[tid]))

    for ph in PHASES:
        for st in (ph.get('stages') or []):
            if not STAGE_ID.match(st.get('id') or ''):
                fail('ids/stage-format',
                     '%r is not of the form P<phase>-S<n>' % st.get('id'))


def check_dependencies():
    for tid, t in TASKS_BY_ID.items():
        for d in (t.get('depends_on') or []):
            if d not in TASKS_BY_ID:
                fail('deps/unresolved',
                     '%s depends on %r, which is not a task' % (tid, d))
                continue
            if d == tid:
                fail('deps/self', '%s depends on itself' % tid)
                continue
            if PHASE_OF[d] > PHASE_OF[tid]:
                fail('deps/forward',
                     '%s (phase %s) depends on %s (phase %s) -- a task cannot wait '
                     'on a later phase' % (tid, PHASE_OF[tid], d, PHASE_OF[d]))


def check_acyclic():
    """Kahn's algorithm. Report the tasks left over, which are the cycle."""
    indeg = {t: 0 for t in TASKS_BY_ID}
    out = defaultdict(list)
    for tid, t in TASKS_BY_ID.items():
        for d in (t.get('depends_on') or []):
            if d in TASKS_BY_ID:
                out[d].append(tid)
                indeg[tid] += 1

    queue = [t for t, n in indeg.items() if n == 0]
    seen = 0
    while queue:
        cur = queue.pop()
        seen += 1
        for nxt in out[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if seen != len(TASKS_BY_ID):
        stuck = sorted(t for t, n in indeg.items() if n > 0)
        fail('deps/cycle',
             'the dependency graph has a cycle; %d task(s) can never become '
             'ready: %s' % (len(stuck), ', '.join(stuck[:12])))


def _ancestors(tid):
    """Every task this one transitively waits on."""
    seen, stack = set(), list(TASKS_BY_ID[tid].get('depends_on') or [])
    while stack:
        d = stack.pop()
        if d in seen or d not in TASKS_BY_ID:
            continue
        seen.add(d)
        stack.extend(TASKS_BY_ID[d].get('depends_on') or [])
    return seen


def check_produces_ownership():
    """Exactly one task may CREATE a path; any number may MODIFY it afterwards.

    A CI workflow file legitimately accumulates jobs from a dozen tasks across
    five phases, so requiring a dependency chain between all of them would be
    wrong -- it would serialise work that is genuinely independent. What must
    hold is weaker and more useful: the file has one creator, and everyone who
    modifies it waits on that creator. Two tasks both claiming to CREATE one
    path is a real collision: whichever runs second destroys the first.
    """
    creators = defaultdict(list)
    modifiers = defaultdict(list)
    for tid, t in TASKS_BY_ID.items():
        for p in (t.get('produces') or []):
            creators[str(p).strip()].append(tid)
        for p in (t.get('modifies') or []):
            modifiers[str(p).strip()].append(tid)

    for path, tids in sorted(creators.items()):
        if len(tids) > 1:
            fail('produces/two-creators',
                 '%r is created by %d tasks (%s). Exactly one may create it; the '
                 'rest must list it under modifies and depend on the creator'
                 % (path, len(tids), ', '.join(sorted(tids))))

    for path, tids in sorted(modifiers.items()):
        if path not in creators:
            fail('produces/modified-but-never-created',
                 '%r is modified by %s but no task creates it'
                 % (path, ', '.join(sorted(tids))))
            continue
        creator = creators[path][0]
        for tid in sorted(tids):
            if tid == creator:
                continue
            if creator not in _ancestors(tid):
                fail('produces/modify-before-create',
                     '%s modifies %r but does not depend on %s, which creates it'
                     % (tid, path, creator))


def check_reads():
    docs = set(f for f in os.listdir(PLAN_DIR) if f.endswith('.md'))
    for tid, t in TASKS_BY_ID.items():
        for r in (t.get('reads') or []):
            head = str(r).strip().split()[0].strip('`,')
            if head.endswith('.md') and head not in docs:
                fail('reads/missing-doc',
                     '%s reads %r, which is not a document in _plan/' % (tid, head))


def check_executors():
    for tid, t in TASKS_BY_ID.items():
        ex = t.get('executor')
        if ex not in EXECUTORS:
            fail('executor/unknown',
                 '%s has executor %r; allowed: %s' % (tid, ex, ', '.join(EXECUTORS)))


def check_verify():
    for tid, t in TASKS_BY_ID.items():
        v = (t.get('verify') or '').strip()
        ex = t.get('executor')
        if not v:
            fail('verify/empty', '%s has no verification' % tid)
            continue
        if WEAK_VERIFY.match(v) and not HAS_COMMAND.search(v):
            fail('verify/weak',
                 '%s verifies with %r -- that cannot fail, so an agent will record '
                 'the task done without doing it' % (tid, v[:70]))
            continue
        if ex in ('agent', 'agent-draft'):
            if not HAS_COMMAND.search(v) and not HONEST_MANUAL.search(v):
                fail('verify/no-command',
                     '%s is executor=%s but its verification names no runnable '
                     'command and does not say why one is impossible: %r'
                     % (tid, ex, v[:70]))


VERIFY_PATH = re.compile(
    r'(?<![A-Za-z0-9_/-])'
    r'((?:packages/[A-Za-z0-9_-]+/)?'
    r'(?:scripts|tools|src|ingest|tests?|evals|runner|site/src|site/tests?)/'
    r'[A-Za-z0-9_./-]+\.(?:py|ts|mjs|js))\b')

# `cd site && npx playwright test tests/a11y.spec.ts` names site/tests/a11y.spec.ts, not
# tests/a11y.spec.ts. Resolving it against the repository root is how P2-S8-T03 passed this
# check while producing a file at a third path that its own verify could never have found.
# The leading [`"'] matters: a verify written as "`cd site && ...`" is a segment whose
# first character is a backtick, and without this the cd is missed and every relative
# path after it silently resolves against the repository root again.
CD_SEGMENT = re.compile(r'^[\s`"\']*cd\s+([A-Za-z0-9_./-]+)\s*$')


def verify_paths(cmd):
    """Yield every path a verify command names, resolved against any `cd` that precedes it."""
    cwd = ''
    for segment in re.split(r'&&|\|\||;', cmd or ''):
        m = CD_SEGMENT.match(segment)
        if m:
            target = m.group(1)
            cwd = '' if target in ('..', '-') else target.strip('/')
            continue
        for path in VERIFY_PATH.findall(segment):
            yield '%s/%s' % (cwd, path) if cwd and not path.startswith(cwd + '/') else path


def check_verify_inputs():
    """A verify command may only run something that already exists.

    This is the `command not found` check. A task whose verification invokes a
    script no earlier task builds is worse than a task with no verification: an
    agent runs it, the shell fails for a reason that has nothing to do with the
    work, and the failure gets read as flaky rather than as unfinished.
    """
    creators = {}
    for tid in ORDER:
        for p in (TASKS_BY_ID[tid].get('produces') or []):
            creators.setdefault(str(p).strip(), tid)

    for tid in ORDER:
        t = TASKS_BY_ID[tid]
        for path in sorted(set(verify_paths(t.get('verify') or ''))):
            owner = creators.get(path)
            if owner is None:
                fail('verify/unbuilt-script',
                     '%s verifies by running %r, which no task creates'
                     % (tid, path))
            elif owner != tid and owner not in _ancestors(tid):
                fail('verify/unbuilt-script',
                     '%s verifies by running %r, which %s creates -- but %s does '
                     'not wait on it' % (tid, path, owner, tid))


BENCH_USE = re.compile(r'\bbench ((?:schema )?[a-z][a-z-]*)')
BENCH_VERB = re.compile(r'\b(?:build|implement|wire|scaffold|extend)\b', re.I)


def _subcommands_built_by(blob):
    """Every bench subcommand named in a sentence that also carries a build verb.

    Sentence-scoped rather than window-scoped, because one step legitimately says
    'Implement bench search, bench show, bench compare and bench suite' and a fixed
    character window only ever reached the first of them.
    """
    out = set()
    for sentence in blob.split('.'):
        if BENCH_VERB.search(sentence):
            out.update(BENCH_USE.findall(sentence))
    return out


def check_cli_surface():
    """A bench subcommand must be built before a verify runs it.

    05 S3 declares the CLI surface, and declaring is not building. This backlog
    shipped `bench tag-gap` into the steps of 41 curation tasks with no task
    anywhere that writes it, and `bench gaps` into Phase 1 with its only builder
    in Phase 4. Both fail at the shell, which reads as a broken environment
    rather than as a plan that forgot something.
    """
    builders = {}
    for tid in ORDER:
        t = TASKS_BY_ID[tid]
        blob = ' '.join(str(x) for x in (t.get('steps') or [])) + ' ' + (t.get('title') or '')
        for sub in _subcommands_built_by(blob):
            builders.setdefault(sub, tid)

    for tid in ORDER:
        t = TASKS_BY_ID[tid]
        for sub in sorted(set(BENCH_USE.findall(t.get('verify') or ''))):
            owner = builders.get(sub)
            if owner is None:
                fail('cli/unbuilt-subcommand',
                     '%s verifies by running `bench %s`, which no task builds'
                     % (tid, sub))
            elif owner != tid and owner not in _ancestors(tid):
                fail('cli/unbuilt-subcommand',
                     '%s verifies by running `bench %s`, which %s builds -- but %s '
                     'does not wait on it' % (tid, sub, owner, tid))


def check_seq():
    """`seq` is the order an agent works in, so it must be a real topological sort."""
    seqs = {}
    for tid, t in TASKS_BY_ID.items():
        if 'seq' not in t:
            fail('seq/missing', '%s has no seq' % tid)
            continue
        if not isinstance(t['seq'], int):
            fail('seq/non-integer', '%s has a non-integer seq %r' % (tid, t['seq']))
            continue
        seqs[tid] = t['seq']

    if len(seqs) != len(TASKS_BY_ID):
        return
    if sorted(seqs.values()) != list(range(1, len(seqs) + 1)):
        dupes = [s for s, n in Counter(seqs.values()).items() if n > 1]
        fail('seq/not-contiguous',
             'seq must be 1..%d with no gaps or repeats; repeated: %s'
             % (len(seqs), sorted(dupes)[:8] or 'none'))
        return
    for tid, t in TASKS_BY_ID.items():
        for d in (t.get('depends_on') or []):
            if d in seqs and seqs[d] > seqs[tid]:
                fail('seq/violates-deps',
                     '%s is seq %d but depends on %s at seq %d -- an agent working '
                     'in seq order would reach it before its input exists'
                     % (tid, seqs[tid], d, seqs[d]))


def check_effort():
    """Task hours should be in the same world as the phase estimate they sit under."""
    for ph in PHASES:
        lo = hi = 0.0
        n = 0
        for st in (ph.get('stages') or []):
            for t in (st.get('tasks') or []):
                try:
                    lo += float(t.get('est_hours_low') or 0)
                    hi += float(t.get('est_hours_high') or 0)
                    n += 1
                except (TypeError, ValueError):
                    fail('effort/non-numeric',
                         '%s has a non-numeric hour estimate' % t.get('id'))
        if n and hi < lo:
            fail('effort/inverted',
                 'phase %s sums to %g-%g hours, high below low'
                 % (ph.get('phase'), lo, hi))


# ---------------------------------------------------------------------------

STATUSES = ('todo', 'doing', 'review', 'blocked', 'done')
HUMAN_INVOLVED = ('agent-draft', 'human', 'human-gate')


def check_ledger():
    """The ledger must not claim more than has happened.

    Added after an unattended run drafted seven agent-draft tasks, committed them as
    "(DRAFT)" and left them `doing`, because the ledger had no state for "finished,
    awaiting a person". The difference between a finished draft and a half-written
    one ended up recorded only in commit messages. `review` is that state, and
    next_task.py is the tool that moves tasks through it.
    """
    for tid, t in TASKS_BY_ID.items():
        st = t.get('status')
        ex = t.get('executor')
        if st not in STATUSES:
            fail('ledger/unknown-status',
                 '%s has status %r; allowed: %s' % (tid, st, ', '.join(STATUSES)))
            continue

        if st == 'review' and ex != 'agent-draft':
            fail('ledger/review-wrong-executor',
                 '%s is in review but executor=%s; only agent-draft tasks are '
                 'reviewed' % (tid, ex))

        if st == 'blocked' and not t.get('blocked_reason'):
            fail('ledger/blocked-without-reason',
                 '%s is blocked with no blocked_reason, so nobody can unblock it' % tid)

        if st == 'done' and ex in HUMAN_INVOLVED:
            if not t.get('signed_off_by') or not t.get('signed_off_on'):
                fail('ledger/done-without-signoff',
                     '%s is executor=%s and done, but has no signed_off_by and '
                     'signed_off_on. A person must be named, or the review gate is '
                     'decoration' % (tid, ex))

        # What a task's inputs must be, for the state it is in:
        #   done                    every input done. Nothing is finished on
        #                           unfinished inputs, which forces review in
        #                           dependency order.
        #   agent, doing            every input done. Agent work is never reviewed,
        #                           so it must never rest on an unreviewed draft.
        #   agent-draft, doing or   every input done OR in review. Drafting on a
        #   review                  draft is allowed because a person reviews this
        #                           one too; the cost is rework if the lower draft
        #                           is rejected, and next_task.py `queue` shows it.
        if st in ('doing', 'review', 'done'):
            ok = ('done', 'review') if (ex == 'agent-draft' and st != 'done') else ('done',)
            pending = [d for d in (t.get('depends_on') or [])
                       if d in TASKS_BY_ID and TASKS_BY_ID[d].get('status') not in ok]
            if pending:
                fail('ledger/ahead-of-inputs',
                     '%s is %s but depends on %s, which %s not %s'
                     % (tid, st,
                        ', '.join('%s (%s)' % (d, TASKS_BY_ID[d].get('status'))
                                  for d in pending),
                        'is' if len(pending) == 1 else 'are',
                        ' or '.join(ok)))


def summary():
    print('verify_execution: %s' % TASKS)
    print('  %d phases, %d stages, %d tasks'
          % (len(PHASES),
             sum(len(p.get('stages') or []) for p in PHASES),
             len(TASKS_BY_ID)))

    ex = Counter(t.get('executor') for t in TASKS_BY_ID.values())
    print('  executor split: %s'
          % ', '.join('%s=%d' % (k, ex[k]) for k in EXECUTORS if ex.get(k)))

    stc = Counter(t.get('status') for t in TASKS_BY_ID.values())
    print('  ledger: %s   (next task: python _plan/_workflow/scripts/next_task.py)'
          % ', '.join('%s=%d' % (k, stc[k]) for k in STATUSES if stc.get(k)))

    touched = set()
    for t in TASKS_BY_ID.values():
        touched.update(str(p).strip() for p in (t.get('produces') or []))
        touched.update(str(p).strip() for p in (t.get('modifies') or []))
    print('  distinct repository paths touched: %d' % len(touched))

    seqs = [t.get('seq') for t in TASKS_BY_ID.values() if isinstance(t.get('seq'), int)]
    if seqs:
        print('  execution order: seq %d..%d' % (min(seqs), max(seqs)))

    ready = sorted(t for t, v in TASKS_BY_ID.items()
                   if not (v.get('depends_on') or []))
    print('  ready with no dependencies: %d' % len(ready))
    if ready:
        print('    first few: %s' % ', '.join(ready[:6]))

    print()
    print('  %-6s %-42s %5s %6s %-22s' % ('phase', 'title', 'tasks', 'hours', 'executors'))
    grand_lo = grand_hi = 0.0
    for ph in PHASES:
        lo = hi = 0.0
        tasks = []
        for st in (ph.get('stages') or []):
            tasks.extend(st.get('tasks') or [])
        for t in tasks:
            lo += float(t.get('est_hours_low') or 0)
            hi += float(t.get('est_hours_high') or 0)
        grand_lo += lo
        grand_hi += hi
        pex = Counter(t.get('executor') for t in tasks)
        print('  %-6s %-42s %5d %6s %-22s'
              % (ph.get('phase'), (ph.get('phase_title') or '')[:42], len(tasks),
                 '%g-%g' % (lo, hi),
                 ' '.join('%s:%d' % (k[0] + k[-1], pex[k]) for k in EXECUTORS if pex.get(k))))
    print('  %-6s %-42s %5d %6s' % ('', 'TOTAL', len(TASKS_BY_ID),
                                    '%g-%g' % (grand_lo, grand_hi)))
    print('    at 20 h/week: %.0f-%.0f weeks' % (grand_lo / 20.0, grand_hi / 20.0))


CHECKS = (
    check_shape, check_ids, check_dependencies, check_acyclic,
    check_produces_ownership, check_reads, check_executors, check_verify,
    check_verify_inputs, check_cli_surface, check_seq, check_effort,
    check_ledger,
)


def main():
    for c in CHECKS:
        c()

    summary()

    if notes:
        print('\nNOTES (not failures):')
        for n in notes:
            print('  - %s' % n)

    if failures:
        by = defaultdict(list)
        for check, msg in failures:
            by[check].append(msg)
        print('\n%d FAILURES across %d checks:' % (len(failures), len(by)))
        for check in sorted(by):
            print('\n  [%s]' % check)
            for msg in by[check]:
                print('    %s' % msg)
        return 1

    print('\nAll checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
