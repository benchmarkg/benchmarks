#!/usr/bin/env python3
"""The five-clause runnable gate over the corpus (P8-S1-T06; 13-execution-runners.md S3, S1.2, S5.6).

    python scripts/runnable_gate.py [--root .] [--threshold 70] [--json]

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

Exit codes: 0 always when the query runs (the gate reports; it does not block anything); 2 on a
file that does not parse, or a clause vocabulary term that no longer exists in taxonomy/.
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


def threshold_for(phase_hours: float) -> int:
    """13 S3.2: ceil(estimated_phase_hours / 5) -- one fully-specified claim per five hours of build."""
    return math.ceil(phase_hours / 5)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--threshold', type=int, default=None,
                   help='compare the count against a threshold; 13 S3.2 recommends 70 (ceil(350 h / 5))')
    p.add_argument('--json', action='store_true')
    a = p.parse_args(argv)
    try:
        gate = run(load(a.root), a.threshold)
    except Exception as e:                                  # a parse error or a stale gate term
        print('runnable_gate: %s' % e, file=sys.stderr)
        return 2
    print(json.dumps(gate.as_dict(), indent=2) if a.json else gate.table())
    return 0


if __name__ == '__main__':
    sys.exit(main())
