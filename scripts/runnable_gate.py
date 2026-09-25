#!/usr/bin/env python3
"""The five-clause runnable gate over the corpus (P8-S1-T06; 13-execution-runners.md S3, S1.2, S5.6).

    python scripts/runnable_gate.py [--root .] [--threshold 70] [--json]
    python scripts/runnable_gate.py --write docs/adoption/runnable-gate-<date>.md   # publish (P8-S1-T07)
    python scripts/runnable_gate.py --check docs/adoption/runnable-gate-<date>.md   # does it still reproduce?

13 S3: "The gate is five clauses, and the count that decides the phase is taken after all five":

    1. reproducibility_tier in {fully-automatable, automatable-with-simulator}
    2. compute_tier == api-credits-only
    3. data.access in {fully-open, gated-registration}      # no credentialed-DUA access mode
    4. NOT dangerous_capability_carveout                     # S5.6
    5. NOT covered_by_maintained_harness_leaderboard_publishing_conditions

The clauses run in that order, each over the survivors of the one before, and the report gives the
per-clause attrition as well as the final count. The order matters to the attrition, not to the final
count: "a threshold set before the carve-out is set against the wrong population" (S3).

Every clause answers pass, fail or UNDETERMINED. An undetermined record -- the field is null, absent,
or not a value the clause knows -- is excluded from the survivors and counted in its own column. It
is never passed. The gate exists to be hard to clear (S3.2: "the cost of a wrong 'go' is the
differentiator itself"), so a missing fact must lower the count, visibly, never raise it.

Clauses 4 and 5 read facts the schema does not carry yet. 13 S5.6 names the carve-out by benchmark
(Cybench, AgentDojo, AgentHarm, HarmBench, JailbreakBench, WMDP, ABC-Bench, the cyber-range family)
and by kind ("offensive-security, dual-use or hazardous-knowledge"). S1.2 sizes clause 5 per family.
No field or vocabulary term records either fact per benchmark, and deriving them from domains would
be a mapping this script invented (Cybench is not filed under safety-alignment). So they are read as
two booleans on the record's execution block, `execution.dangerous_capability_carveout` and
`execution.covered_by_maintained_harness_leaderboard`, and are undetermined wherever absent -- today,
everywhere, because 04 has not added them and the Benchmark model refuses keys it does not declare.
Until it does, the gate cannot pass any record, and the report says why.

Records are read as raw YAML, not through the Benchmark model: the gate is a query over whatever the
corpus holds, and a record that fails validation still has the facts it states. It lives in scripts/,
not on the `bench` surface, because 05 S3's block is the CLI's only specification (the task's step 3).

Publishing (P8-S1-T07). `--write` puts the query text, the threshold band, the count and the
per-clause attrition into a Markdown file between two marker comments, and leaves everything outside
the markers alone -- that is where a person writes the clause-5 sanity check. `--check` regenerates
the block from the corpus and compares it byte for byte: "the committed count reproduces from the
committed query". The block carries no date or commit, so it stays reproducible after it is committed.

Exit codes: 0 when the query runs (the gate reports; it does not block anything) and, with --check,
the published block reproduces; 1 when it does not; 2 on a file that does not parse, a clause
vocabulary term that no longer exists in taxonomy/, or a --check file with no generated block.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PASS, FAIL, UNDETERMINED = 'pass', 'fail', 'undetermined'

REPRODUCIBLE = ('fully-automatable', 'automatable-with-simulator')
API_ONLY = 'api-credits-only'
OPEN_ACCESS = ('fully-open', 'gated-registration')
CARVEOUT_KEY = 'dangerous_capability_carveout'
COVERED_KEY = 'covered_by_maintained_harness_leaderboard'


def _at(record: dict, *path):
    node = record
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _member(value, allowed, vocabulary) -> str:
    """pass if `value` is one of `allowed`; fail if it is another live term; else undetermined."""
    if value in allowed:
        return PASS
    if isinstance(value, str) and value in vocabulary:
        return FAIL
    return UNDETERMINED


def _not_flag(value) -> str:
    """For a NOT clause over a boolean fact: false passes, true fails, anything else is unknown."""
    if value is False:
        return PASS
    if value is True:
        return FAIL
    return UNDETERMINED


@dataclass(frozen=True)
class Clause:
    number: int
    name: str
    field: str
    test: Callable[[dict, dict], str]      # (record, vocabularies) -> pass | fail | undetermined


CLAUSES = (
    Clause(1, 'reproducibility_tier in {fully-automatable, automatable-with-simulator}',
           'execution.reproducibility_tier',
           lambda r, v: _member(_at(r, 'execution', 'reproducibility_tier'), REPRODUCIBLE, v['reproducibility_tier'])),
    Clause(2, 'compute_tier == api-credits-only', 'execution.compute_tier',
           lambda r, v: _member(_at(r, 'execution', 'compute_tier'), (API_ONLY,), v['compute_tier'])),
    Clause(3, 'data.access in {fully-open, gated-registration}', 'data.access',
           lambda r, v: _member(_at(r, 'data', 'access'), OPEN_ACCESS, v['access'])),
    Clause(4, 'NOT dangerous_capability_carveout (13 S5.6)', 'execution.' + CARVEOUT_KEY,
           lambda r, v: _not_flag(_at(r, 'execution', CARVEOUT_KEY))),
    Clause(5, 'NOT covered_by_maintained_harness_leaderboard_publishing_conditions', 'execution.' + COVERED_KEY,
           lambda r, v: _not_flag(_at(r, 'execution', COVERED_KEY))),
)


def vocabularies() -> dict[str, set[str]]:
    """The live terms of the three vocabulary-valued clauses, read from the schema (so from
    taxonomy/). A clause's pass values must still be terms: a rename fails here, not silently."""
    from schema.paths import resolve, vocabulary
    v = {'reproducibility_tier': vocabulary(resolve('Benchmark.execution.reproducibility_tier')),
         'compute_tier': vocabulary(resolve('Benchmark.execution.compute_tier')),
         'access': vocabulary(resolve('Benchmark.data.access'))}
    stale = sorted(set(REPRODUCIBLE) - v['reproducibility_tier']) + sorted({API_ONLY} - v['compute_tier']) + \
        sorted(set(OPEN_ACCESS) - v['access'])
    if stale:
        raise ValueError('gate terms no longer in taxonomy/: %s' % ', '.join(stale))
    return v


@dataclass
class Step:
    clause: Clause
    entering: int
    failed: list[str] = field(default_factory=list)
    undetermined: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.entering - len(self.failed) - len(self.undetermined)

    def as_dict(self) -> dict:
        return {'clause': self.clause.number, 'name': self.clause.name, 'field': self.clause.field,
                'entering': self.entering, 'failed': len(self.failed), 'undetermined': len(self.undetermined),
                'remaining': self.remaining, 'failed_ids': self.failed, 'undetermined_ids': self.undetermined}


@dataclass
class Gate:
    total: int
    steps: list[Step]
    passing: list[str]
    threshold: int | None = None

    @property
    def count(self) -> int:
        return len(self.passing)

    def as_dict(self) -> dict:
        return {'total': self.total, 'count': self.count, 'passing': self.passing, 'threshold': self.threshold,
                'meets_threshold': None if self.threshold is None else self.count >= self.threshold,
                'steps': [s.as_dict() for s in self.steps]}

    def table(self) -> str:
        lines = ['runnable gate (13 S3) over %d benchmark record(s)' % self.total, '',
                 '| # | clause | entering | failed | undetermined | remaining |',
                 '| --- | --- | --- | --- | --- | --- |']
        for s in self.steps:
            lines.append('| %d | %s | %d | %d | %d | %d |' % (s.clause.number, s.clause.name, s.entering,
                                                             len(s.failed), len(s.undetermined), s.remaining))
        lines += ['', 'passing all five: %d%s' % (self.count, (' (%s)' % ', '.join(self.passing)) if self.passing else '')]
        if self.threshold is not None:
            lines.append('threshold %d (13 S3.2): %s' % (self.threshold, 'met' if self.count >= self.threshold
                                                          else 'not met'))
        blind = [s for s in self.steps if s.clause.number in (4, 5) and s.undetermined]
        if blind:
            lines.append('%s undetermined on %s record(s): the carve-out and harness-coverage facts are not '
                         'schema fields yet, so a curated record cannot state them (see the module docstring)'
                         % ('clause %d is' % blind[0].clause.number if len(blind) == 1 else 'clauses 4 and 5 are',
                            ' + '.join(str(len(s.undetermined)) for s in blind)))
        return '\n'.join(lines)


def run(records: dict[str, dict], threshold: int | None = None, vocab: dict | None = None) -> Gate:
    """The five clauses in order over {id: raw record}."""
    vocab = vocab or vocabularies()
    survivors = sorted(records)
    steps = []
    for clause in CLAUSES:
        step = Step(clause, len(survivors))
        kept = []
        for rid in survivors:
            verdict = clause.test(records[rid], vocab)
            if verdict == PASS:
                kept.append(rid)
            elif verdict == FAIL:
                step.failed.append(rid)
            else:
                step.undetermined.append(rid)
        steps.append(step)
        survivors = kept
    return Gate(len(records), steps, survivors, threshold)


def load(root: str) -> dict[str, dict]:
    from schema.taxonomy import read_yaml
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '**', '*.yaml'), recursive=True)):
        doc = read_yaml(path)
        if not isinstance(doc, dict):
            raise ValueError('%s is not a mapping' % path)
        rid = doc['id'] if isinstance(doc.get('id'), str) else os.path.basename(path)[:-5]
        out[rid] = doc
    return out


PHASE_HOURS = (190, 350)            # 13 S8: "Phase total: 190-350 h", bottom-up
BEGIN = '<!-- runnable-gate:begin -- generated by scripts/runnable_gate.py --write; --check reproduces it -->'
END = '<!-- runnable-gate:end -->'


def threshold_for(phase_hours: float) -> int:
    """13 S3.2: ceil(estimated_phase_hours / 5) -- one fully-specified claim per five hours of build."""
    return math.ceil(phase_hours / 5)


def _ids(ids) -> str:
    return ', '.join('`%s`' % x for x in sorted(ids)) or '--'


def published_block(g: Gate) -> str:
    """The generated section of docs/adoption/runnable-gate-<date>.md. Deterministic: no date, no
    commit, ids sorted, so --check compares it byte for byte."""
    lo, hi = (threshold_for(h) for h in PHASE_HOURS)
    lines = [BEGIN, '', '### The query', '',
             'Five clauses, in this order, each over the survivors of the one before (13 §3). A record whose',
             'fact is missing or not a known term is **undetermined**: excluded, counted, never passed.', '',
             '```']
    lines += ['%d. %s   [%s]' % (c.number, c.name, c.field) for c in CLAUSES]
    lines += ['```', '', '### The threshold', '',
              "`ceil(estimated_phase_hours / 5)` over 13 §8's %d–%d h gives **%d–%d**. Recommended: **≥ %d**,"
              % (PHASE_HOURS[0], PHASE_HOURS[1], lo, hi, hi),
              'the top of the band (13 §3.2).', '',
              '### The count', '',
              '**%d of %d** benchmark record(s) pass all five clauses: %s. Against the recommended ≥ %d: **%s**.'
              % (g.count, g.total, _ids(g.passing) if g.passing else 'none', hi,
                 'met' if g.count >= hi else 'not met'), '',
              '### Per-clause attrition', '',
              '| # | clause | entering | failed | undetermined | remaining |',
              '| --- | --- | --- | --- | --- | --- |']
    for st in g.steps:
        lines.append('| %d | %s | %d | %d | %d | %d |' % (st.clause.number, st.clause.name, st.entering,
                                                         len(st.failed), len(st.undetermined), st.remaining))
    lines += ['', 'Which records stopped where:', '']
    lines += ['- clause %d: failed %s; undetermined %s' % (st.clause.number, _ids(st.failed), _ids(st.undetermined))
              for st in g.steps]
    c5 = g.steps[4]
    lines += ['', '### Clause-5 exclusions, for the human sample', '',
              ('%d record(s) excluded by clause 5 as already covered: %s.' % (len(c5.failed), _ids(c5.failed))
               if c5.failed else 'None: no record reached clause 5 with the fact stated, so there is nothing to '
               'sample yet.'), '', END]
    return '\n'.join(lines) + '\n'


def _block_of(text: str) -> str | None:
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < i:
        return None
    return text[i:j + len(END)] + '\n'


def write(path: str, g: Gate, preamble: str, postscript: str) -> None:
    """Replace the generated block in `path`, or create the file around it."""
    block = published_block(g)
    if os.path.exists(path):
        text = open(path, encoding='utf-8').read()
        old = _block_of(text)
        if old is None:
            raise ValueError('%s exists and has no generated block to replace' % path)
        text = text.replace(old, block)
    else:
        text = preamble + '\n' + block + '\n' + postscript
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def check(path: str, g: Gate) -> list[str]:
    """Differences between the published block and a fresh run; empty when it reproduces."""
    old = _block_of(open(path, encoding='utf-8').read())
    if old is None:
        raise ValueError('%s has no generated block between %s and %s' % (path, BEGIN, END))
    new = published_block(g)
    if old == new:
        return []
    import difflib
    return list(difflib.unified_diff(old.splitlines(), new.splitlines(), 'published', 'reproduced', lineterm=''))


PREAMBLE = """# The runnable gate, run on {date}

- **Task:** P8-S1-T07 (13-execution-runners.md §3.2, §8)
- **Query:** `scripts/runnable_gate.py`. The generated block below reproduces with
  `python scripts/runnable_gate.py --check {path}`
- **Status:** agent draft. The count is mechanical; the clause-5 sample is a human judgement.
"""

POSTSCRIPT = """## Human sanity check of clause-5 exclusions

<!-- 13 §3 clause 5 is a judgement: does the upstream leaderboard publish its run conditions? A person
samples the clause-5 exclusions listed above and records what they checked here. `--write` never
touches anything outside the generated block. -->

- **Checked by:** --
- **Sample:** --
- **Finding:** --
"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--threshold', type=int, default=None,
                   help='compare the count against a threshold; 13 S3.2 recommends 70 (ceil(350 h / 5))')
    p.add_argument('--json', action='store_true')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--write', metavar='DOC', help='publish the count, query and attrition into DOC')
    mode.add_argument('--check', metavar='DOC', help="exit 1 unless DOC's published block reproduces")
    a = p.parse_args(argv)
    try:
        gate = run(load(a.root), a.threshold)
        if a.check:
            diff = check(a.check, gate)
            if diff:
                print('runnable_gate --check: %s no longer reproduces from the query\n%s'
                      % (a.check, '\n'.join(diff)), file=sys.stderr)
                return 1
            print('runnable_gate --check: %s reproduces (%d of %d pass)' % (a.check, gate.count, gate.total))
            return 0
        if a.write:
            import datetime
            write(a.write, gate, PREAMBLE.format(date=datetime.date.today().isoformat(), path=a.write), POSTSCRIPT)
            print('runnable_gate: wrote %s (%d of %d pass)' % (a.write, gate.count, gate.total))
            return 0
    except Exception as e:                                  # a parse error, a stale gate term, no block
        print('runnable_gate: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(gate.as_dict(), indent=2) if a.json else gate.table())
    return 0


if __name__ == '__main__':
    sys.exit(main())
