#!/usr/bin/env python3
"""render_execution_plan.py -- generate 16-execution-plan.md from execution/tasks.yaml.

The backlog is the single owner of every task fact, exactly as 02-taxonomy.md owns
the vocabularies. This renders the human-readable view of it. Do not hand-edit
16-execution-plan.md; edit tasks.yaml and re-run:

    python _plan/_workflow/scripts/render_execution_plan.py

--check re-renders and exits 1 if the committed document differs, which is what CI runs.
"""
import io
import os
import sys
import collections

try:
    import yaml
except ImportError:
    sys.exit('render_execution_plan: pyyaml is required (pip install pyyaml)')

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.dirname(os.path.dirname(HERE))
TASKS = os.path.join(PLAN, 'execution', 'tasks.yaml')
OUT = os.path.join(PLAN, '16-execution-plan.md')

EXEC_LABEL = {'agent': 'A', 'agent-draft': 'A-d', 'human': 'H', 'human-gate': 'gate'}


def esc(s):
    return str(s).replace('|', '\\|').strip()


def hrs(lo, hi):
    fmt = lambda x: '%g' % x
    return fmt(lo) if lo == hi else '%s-%s' % (fmt(lo), fmt(hi))


def build():
    doc = yaml.safe_load(io.open(TASKS, encoding='utf-8'))
    phases = doc['phases']

    o = []
    w = o.append

    w('# 16 -- Execution Plan')
    w('')
    w('[14-roadmap.md](14-roadmap.md) says what order to build in and why, in prose, at the level of')
    w('phases. This document is the same plan decomposed until every item is small enough for one')
    w('person or one agent to pick up, finish, and prove finished without asking anyone what was')
    w('meant. It is the execution surface; 14 remains the reasoning.')
    w('')
    w('**This document is generated.** `execution/tasks.yaml` is the single owner of every task fact,')
    w('the same way [02-taxonomy.md](02-taxonomy.md) owns the vocabularies. Edit the YAML and re-run')
    w('`_workflow/scripts/render_execution_plan.py`; do not hand-edit this file.')
    w('')
    w('---')
    w('')
    w('## 1. How to execute this')
    w('')
    w('Work in ascending `seq`. That field is a topological sort of `depends_on`, so when a task comes')
    w('up, every input it names has already been produced. **Document order is not safe to execute** --')
    w('it is grouped by stage for reading, and seven tasks sit before something they depend on. `seq`')
    w('exists precisely so that grouping and ordering do not have to be the same thing.')
    w('')
    w('For each task in turn: read the documents in `reads`, do the `steps`, then run the `verify`')
    w('command. Set `status: done` only when that command has actually run and passed. Everything else')
    w('in the backlog is description; `verify` is the only thing that decides whether a task is')
    w('finished, and a task recorded done without it is worse than a task not started, because nothing')
    w('downstream will re-check it.')
    w('')
    w('### The four executors')
    w('')
    w('| Value | Who | What it means |')
    w('| --- | --- | --- |')
    w('| `agent` | An agent, alone | Does it end to end and verifies it. No review needed before the '
      'next task starts. |')
    w('| `agent-draft` | An agent, then a person | The agent produces the artifact; a human must review '
      'it before it counts as done. Almost all curation is this: an agent can find and format an entry, '
      'but whether the classification is *right* is the judgement this project exists to get right. |')
    w('| `human` | A person | Needs an account, a signature, a credential action or a legal reading. An '
      'agent cannot do it, and pretending otherwise strands the pipeline. |')
    w('| `human-gate` | A person | A decision that stops the pipeline until it is answered. Produces no '
      'artifact. |')
    w('')
    w('### The ledger')
    w('')
    w('`status` is the execution ledger, one of `todo`, `doing`, `blocked`, `done`. It is the only field')
    w('an executor writes. `produces` names the paths a task **creates** -- exactly one task may create')
    w('any given path -- and `modifies` names paths it edits that another task created. A task that only')
    w('edits has an empty `produces`, which is legitimate and common for shared files like the CI')
    w('workflow, which accumulates jobs from tasks across five phases.')
    w('')
    w('---')
    w('')
    w('## 2. The shape of the work')
    w('')
    w('| Phase | Title | Stages | Tasks | Hours | `agent` | `agent-draft` | `human` | `human-gate` |')
    w('| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')

    glo = ghi = 0.0
    gs = gt = 0
    gex = collections.Counter()
    for p in phases:
        ts = [t for s in p['stages'] for t in s['tasks']]
        lo = sum(t['est_hours_low'] for t in ts)
        hi = sum(t['est_hours_high'] for t in ts)
        ex = collections.Counter(t['executor'] for t in ts)
        gex.update(ex)
        glo += lo
        ghi += hi
        gs += len(p['stages'])
        gt += len(ts)
        w('| **%s** | %s | %d | %d | %s | %d | %d | %d | %d |'
          % (p['phase'], esc(p['phase_title']), len(p['stages']), len(ts), hrs(lo, hi),
             ex['agent'], ex['agent-draft'], ex['human'], ex['human-gate']))
    w('| | **Total** | **%d** | **%d** | **%s** | **%d** | **%d** | **%d** | **%d** |'
      % (gs, gt, hrs(glo, ghi), gex['agent'], gex['agent-draft'], gex['human'], gex['human-gate']))
    w('')

    v1lo = sum(t['est_hours_low'] for p in phases if p['phase'] <= 4
               for s in p['stages'] for t in s['tasks'])
    v1hi = sum(t['est_hours_high'] for p in phases if p['phase'] <= 4
               for s in p['stages'] for t in s['tasks'])
    w('At the [14-roadmap.md](14-roadmap.md) planning figure of 20 hours a week, the whole backlog is')
    w('**%.0f-%.0f weeks**. Phases 0-4, which is everything up to public v1, are **%s hours**.'
      % (glo / 20.0, ghi / 20.0, hrs(v1lo, v1hi)))
    w('')
    w('**These numbers are larger than the roadmap’s, and that is the expected direction.** 14 sizes')
    w('phases top-down from the shape of the work; this document sums them bottom-up from %d' % gt)
    w('individually estimated items, and bottom-up decomposition characteristically lands above a')
    w('top-down estimate because it makes visible the work that prose elides. Treat the gap as an input')
    w('to planning -- it says the roadmap is optimistic by roughly this factor -- rather than as a')
    w('defect in either document. The two have deliberately not been reconciled: forcing them to agree')
    w('would destroy the only independent check available on either.')
    w('')
    p1 = collections.Counter(t['executor'] for s in phases[1]['stages'] for t in s['tasks'])
    w('The `agent-draft` count is the honest constraint on how fast this can go. %d of %d tasks need a'
      % (gex['agent-draft'], gt))
    w('human to review the artifact before it counts, and %d more need a human to do them outright.'
      % (gex['human'] + gex['human-gate']))
    w('Phase 1 alone is %d `agent-draft` against %d `agent`, which is the true shape of a curation'
      % (p1['agent-draft'], p1['agent']))
    w('phase: the bottleneck is review capacity, not generation.')
    w('')

    for p in phases:
        ts = [t for s in p['stages'] for t in s['tasks']]
        lo = sum(t['est_hours_low'] for t in ts)
        hi = sum(t['est_hours_high'] for t in ts)
        w('---')
        w('')
        w('## Phase %s -- %s' % (p['phase'], esc(p['phase_title'])))
        w('')
        w('*%d stages, %d tasks, %s hours.*' % (len(p['stages']), len(ts), hrs(lo, hi)))
        w('')
        for label, key in (('Goal', 'phase_goal'),
                           ('Entry condition', 'entry_condition'),
                           ('Exit gate', 'exit_gate'),
                           ('Parallelism', 'parallelisable')):
            if p.get(key):
                w('**%s.** %s' % (label, str(p[key]).strip()))
                w('')
        for s in p['stages']:
            slo = sum(t['est_hours_low'] for t in s['tasks'])
            shi = sum(t['est_hours_high'] for t in s['tasks'])
            w('### %s -- %s' % (s['id'], esc(s['title'])))
            w('')
            if s.get('goal'):
                w(str(s['goal']).strip())
                w('')
            w('*%d tasks, %s hours.*' % (len(s['tasks']), hrs(slo, shi)))
            w('')
            w('| seq | Task | Title | Who | Hours | Waits on |')
            w('| ---: | --- | --- | --- | ---: | --- |')
            for t in s['tasks']:
                deps = ', '.join('`%s`' % d for d in (t.get('depends_on') or [])) or '--'
                w('| %d | `%s` | %s | %s | %s | %s |'
                  % (t['seq'], t['id'], esc(t['title']), EXEC_LABEL[t['executor']],
                     hrs(t['est_hours_low'], t['est_hours_high']), deps))
            w('')

    w('---')
    w('')
    w('## 3. Checking the backlog')
    w('')
    w('```')
    w('python _plan/_workflow/scripts/verify_execution.py')
    w('```')
    w('')
    w('It enforces the properties that make one-by-one execution safe. Each has been violated by this')
    w('backlog at least once:')
    w('')
    w('- every `depends_on` resolves to a real task, and no task waits on a later phase;')
    w('- the dependency graph is acyclic, so something is always ready;')
    w('- exactly one task creates each path, and every task that modifies a path waits on its creator;')
    w('- every file named in a `verify` command is built by the task itself or by one of its ancestors')
    w('  -- the check against a verification that fails with `command not found`;')
    w('- `seq` is a contiguous 1..N and never places a task before one of its dependencies;')
    w('- no `verify` is a weak one that cannot fail, and an `agent` task either names a runnable command')
    w('  or says why no machine check is possible.')
    w('')
    w('```')
    w('python _plan/_workflow/scripts/render_execution_plan.py --check')
    w('```')
    w('')
    w('re-renders this document from the backlog and fails if the committed copy has drifted.')
    w('')

    text = '\n'.join(o)
    return text if text.endswith('\n') else text + '\n'


def main():
    text = build()
    if '--check' in sys.argv:
        cur = io.open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
        if cur != text:
            print('render_execution_plan: 16-execution-plan.md is out of date; '
                  're-run without --check')
            return 1
        print('render_execution_plan: 16-execution-plan.md is up to date')
        return 0
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(text)
    print('render_execution_plan: wrote %s (%.0f KB)'
          % (os.path.basename(OUT), len(text.encode('utf-8')) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
