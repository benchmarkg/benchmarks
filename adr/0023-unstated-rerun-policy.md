# ADR-0023 -- `maintainer_rerun_policy: unstated` blocks a run until a curator has read the terms

- **Status:** Proposed -- an agent draft (P8-S2-T06). It counts as decided only when a person ratifies it.
- **Date:** 2026-10-10
- **Taxonomy version:** not affected
- **Facet:** none -- an execution-layer decision on a curation field (`Benchmark.execution.maintainer_rerun_policy`)
- **Change type:** architecture decision; answers 13-execution-runners.md §10 open question 6
- **Supersedes:** --
- **Superseded by:** --
- **Enforced by:** `scripts/check_rerun_policy.py --mode block` (the default the script ships with)

## Context

13 §5.4 makes the maintainer's rerun policy a curation field with four values -- `unrestricted`,
`no-third-party-endpoints`, `contact-first`, `unstated` -- and fixes three of them: we never run
`no-third-party-endpoints`; `contact-first` waits for a recorded yes; `unrestricted` may run. For the
fourth it gives only a floor, rule 4: "`unstated` is not permission. For benchmarks with a hidden or
held-out component, the default is not to run, because the cost of being wrong is destroying a benchmark
for everyone." §10 leaves the rest open as question 6: "whether `unstated` should block *all* runs until
a curator has read the terms, which is safer and slower."

Why it matters is §5.4's own warning: every hosted-API rerun sends benchmark items to a provider that may
log, retain and train on them, and "the catalogue that refuses to host data becomes the thing that leaks
it, one API call at a time."

What the corpus says today (`scripts/check_rerun_policy.py --all`, 2026-10-10;
`docs/execution/rerun-policy-audit.md`):

- all 14 curated benchmark records are `unstated` -- no curator has read a maintainer's terms for this
  field yet;
- the runnable gate's passing set is empty, because its clauses 4 and 5 read facts the schema does not
  carry. The gate's recommended threshold is at least 70 benchmarks (13 §3.2), so the decision is about
  the run set the gate will eventually admit, not the one it admits now.

One fact about the gate decides how much the second option below buys. Clause 3 admits only
`data.access` of `fully-open` or `gated-registration`; `train-open-test-held-out` and
`private-test-server`, the two terms that record a withheld component, never pass it. So inside the
gate-passing set, rule 4's floor already holds by construction, except where a record's ground truth is
`held-out-labels` (`data.access_by_phase` is free text, so it cannot be read mechanically).

## The options

**A. `block`: `unstated` blocks every run until a curator records a policy.** A gate-passing benchmark
whose policy is `unstated` is a breach, exactly as `contact-first` without an answer is. The run set is
the benchmarks a curator has read terms for and marked `unrestricted`, or `contact-first` with a recorded
yes.

- *Cost.* One reading per benchmark before its first run: the maintainer's README, licence, terms of use
  and any statement about third-party endpoints. The estimate is 10-20 curator-minutes each, so 12-23
  curator-hours at the gate's 70, once, and 10-20 minutes for each benchmark that later enters the set.
  Recorded per benchmark, it is never paid twice.
- *Failure mode.* Slowness: the first runs wait on curation. If curation stalls, the runner runs
  nothing; it never runs the wrong thing.

**B. `hidden-only`: `unstated` blocks only where a hidden or held-out component shows.** 13 §5.4 rule 4's
floor, and no more: a gate-passing `unstated` benchmark is a breach only when its record shows a withheld
component (`data.access` of `train-open-test-held-out` or `private-test-server`, or `ground_truth_source:
held-out-labels`); every other one may run.

- *Cost.* Close to none. The script reads facts the record already carries.
- *Failure mode.* Silent and permanent. It runs a public benchmark whose maintainer would have objected
  but never wrote it down, and sends its items to a provider that may train on them. Because clause 3
  already removes nearly every record with a withheld component, B blocks almost nothing in the gate's
  set. In practice it is "run every gate-passing benchmark", with the contamination risk §5.4 exists to
  prevent. A maintainer's objection that arrives after a run cannot recall the items.

## Decision (proposed)

**A, `block`.** A gate-passing benchmark may be run only when a curator has recorded its policy as
`unrestricted`, or as `contact-first` with a recorded yes. `unstated` is treated as `contact-first` with no
answer: the runner does not run it, and the audit names it.

Why A over B:

- Rule 4's sentence, "`unstated` is not permission", reads more naturally as A. B turns it into "unstated
  is permission unless something is visibly hidden".
- The costs are not symmetric. A costs a bounded number of curator-hours, paid once per benchmark. B's
  cost lands on a benchmark maintainer and on everyone who uses that benchmark, and it cannot be undone.
- A reading of the terms is already part of curation (`code_licence`, `data.access`, the licence
  firewall), so A adds one field to a reading that happens anyway rather than a new activity.
- At today's scale it costs nothing: the passing set is empty.

## Consequences

- `scripts/check_rerun_policy.py` gains `--mode {block, hidden-only}`, defaulting to `block`, the mode
  this ADR proposes. Under `block`, every `unstated` gate-passing benchmark is a breach. Under
  `hidden-only`, only one showing a withheld component is a breach. If ratification chooses B, the
  default flips to `hidden-only` and nothing else changes. The verify,
  `check_rerun_policy.py --mode block`, exits 0 on today's gate-passing set, which is empty.
- Curation adds `execution.maintainer_rerun_policy` to what a curator reads for any benchmark heading for
  the gate's set. A curator who finds no statement records `contact-first`, which routes the benchmark to
  P8-S2-T05's correspondence, not `unrestricted`. Silence in the terms is not a yes.
- The audit document lists every `unstated` gate-passing benchmark as a breach, with the reading it is
  waiting on.

## Alternatives considered

- **Treat `unstated` as `unrestricted` for benchmarks whose licence permits redistribution.** Rejected.
  A data licence answers whether we may copy the items. It does not answer whether the maintainer wants
  them sent to a model provider's logging pipeline, and §5.4 separates exactly those two questions.
- **Write to every maintainer (make everything `contact-first`).** Rejected as a default. It is
  P8-S2-T05's workload multiplied by the whole run set, when many maintainers' terms already answer the
  question. A curator who finds no answer in the terms still routes that benchmark there.
