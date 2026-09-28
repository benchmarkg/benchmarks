# ADR-0020 -- The Stage 4 revision: taxonomy 0.1.0 -> 0.9.0

- **Status:** Proposed
- **Date:** 2026-09-28
- **Taxonomy version:** 0.1.0 -> 0.9.0
- **Facet:** all eight
- **Change type:** a batch of adds and redefinitions (03 §8.1: MINOR each). No term is renamed,
  merged, split, deprecated or retired. The one id changed, `entrant-relative-ranking`, is new in this
  batch.
- **Supersedes:** --
- **Superseded by:** --
- **Applied:** taxonomy 0.9.0, P1-S1-T07. The retro-tag plan is P1-S1-T08.

## Context

Triage (P1-S1-T06) sent 579 of the 624 Stage-3 failure records to the Stage 4 revision, listed in
`taxonomy/_failures/stage-4-revision-list.md`. ADR-0014 to ADR-0019 decide the other 45. 03 §8.3
batches proposals and requires a written answer for every one, accepted or not. 02 §11 rule 9 requires
an ADR and a retro-tag plan for every added term. This ADR is both for the batch, and its appendix is
the written answer for each group in the list.

The revision followed eight rules:

1. **Only adds and redefinitions.** A rename, merge, split or retirement is MAJOR and out of scope.
2. **Accept a proposed term only if it recurs** across at least three distinct benchmarks, after
   synonymous proposals are merged, or if it resolves an escape hatch that clearly recurs (03 §5's
   red flag for a one-benchmark term). Everything else is rejected or deferred, with a reason.
3. **Every new or revised term meets 03 §5:**
   - a one-sentence definition;
   - an operational inclusion test and an operational exclusion test;
   - at least two examples, one of them a near miss.
4. **Collisions.** A pair that collides in two or more records gets `not_to_be_confused_with` on
   both terms, plus a tie-break. A collision caused by a single-valued field describing a layered
   benchmark gets a stated precedence rule instead, saying which layer the field describes.
5. **Taxonomy examples that contradict their term's tests, or the benchmark's sources, are
   corrected.**
6. **`source-silent` failures need no vocabulary change.**
7. **No undeclared homograph** (check 9d).
8. **One file group per curator**, so no two edits could conflict.

## Decision

**22 terms are added.** 176 existing terms are clarified: tests, examples and
`not_to_be_confused_with` blocks, and for some a revised definition. None is removed.

| Facet file | Added | Clarified |
| --- | --- | --- |
| capabilities | `scientific-prediction` (ADR-0014) | 22 |
| domains | `general-intelligence/multi-subject-knowledge-exams` (ADR-0015); `medicine-health/clinical-task-suites`, `agents-tooluse/agent-evaluation-suites`, `games-planning/multi-game-suites` (ADR-0016); `general-intelligence/open-preference-arenas` (ADR-0018) | 46 |
| evaluation-methods | `classification-metric`, `environment-state-check`, `numeric-tolerance-match`, `entrant-relative-ranking` | 24 |
| subjects | `model-in-benchmark-harness`, `task-specific-supervised-model`, `attack-or-intervention-method` | 14 |
| data-properties | `curated-public-database`, `inherited-from-constituents` (provenance) | 22 |
| ceiling-anchors | -- | 7 |
| lifecycle | `no-submission-channel`, `results-pending` (activity); `dormant` and `mature` redefined per ADR-0019 | 11 |
| governance | `maintainer-run`, `literature-only`, `open-source-gated`, `maintainer-scored-predictions` (submission process); `grader-from-evaluated-party` (independence) | 15 |
| execution | -- | 15 |

**Precedence rules for single-valued fields.** Each is written into the tests of the terms it
touches, and the appendix states each in full.
- `data.access` describes the evaluation data behind the headline score, and withholding decides
  before a gate.
- `data.refresh` describes the family and the set behind the headline score.
- `data.ceiling_anchor_type` records the headline metric's anchor. A scale that cannot have an
  anchor is `none-known`, with the reason carried on the Metric and Baseline.
- `execution.compute_tier` describes one official score for one new system. A requirement the
  protocol imposes outranks the cost of serving the system under test.
- `execution.reproducibility_tier`: the most restrictive tier any part of the headline needs decides.
- `governance.maintainer_type` names the party that holds and publishes the artefact.
  `conference-workshop` covers a challenge whose organisers change each edition.
- `lifecycle` and `activity` describe the entry as catalogued. An edition has its own standing, and
  originator inactivity alone is `maintenance_status` evidence, not `dormant`.
- `domain.primary` follows the benchmark's claim over its protocol or metric. For software, the grader
  decides between `code` and `agents-tooluse`.

**Notable refusals.**
- **`inference-efficiency` is rejected.** 02 §4.4 retired `efficiency-compute` and
  `efficiency-latency` for these very benchmarks. It replaced them with the benchmark field
  `secondary_axes: [cost, latency, throughput, energy, reliability]`, and the five records that
  proposed the term are expressed there.
- **`embargoed-until-release` is rejected.** 02 §12.1, §12.4 and §12.8 read CASP, CACHE and
  ForecastBench by their data once the round is released.
- **`hosted-judge-dependency` is deferred.** It recurs in eight records, but 02 §11 and
  `schema/validators.py` forbid any blocker except `licence-restriction` beside `fully-automatable`.
  Seven of the eight are otherwise `fully-automatable`, so it needs an ADR amending that rule first
  (see Open questions).
- **A generic "reasoning" capability is rejected** (03 §5: no "general" terms), and so is a
  `general-capability-factor`.

## Consequences

- **Counts.** Every count in 02 and in 12 §5.1 that is derived from the vocabulary is now generated.
  `scripts/taxonomy_stats.py --write` rewrites them, and `--check` (9b) fails on drift. The new
  totals:
  - the fine grid is 209 × 45 = 9,405 cells;
  - the coarse grid is unchanged at 19 × 13 = 247, because no family and no group was added;
  - the group `causal-and-experimental-inference` gains `scientific-prediction`, so
    `capability_groups.yaml` moves to 0.9.0.
- **Re-classification (P1-S1-T08).**
  - P1-S1-T08 re-runs every field this batch touched over the 90 corpus items: every field that
    gained a term, and every field whose terms gained a precedence rule or a changed definition.
  - The appendix lists the values each curator expects to move. Examples: luna16 to
    `medicine-health/medical-imaging-diagnostic`; posebusters' domain without an escape hatch;
    bench's lifecycle to `superseded`.
- **Corpus scope.** The three out-of-scope entries (ADR-0017) are flagged in
  `taxonomy/_corpus/stress-corpus.yaml` and are excluded from the re-run.

## Open questions, carried forward

1. **The blocker/tier rule.** 02 §11 blocks any reproducibility blocker beside `fully-automatable`
   except `licence-restriction`. 02 §12.5 and §12.8 contradict it (`live-world-state` beside
   `fully-automatable`), and `hosted-judge-dependency` needs it relaxed. One ADR amending that rule
   settles both.
2. **Legality-matrix rows for the new activity terms.** `active` + `no-submission-channel` and
   `active` + `results-pending` are legal. Whether `dormant`, `deprecated` or `retracted` +
   `results-pending` should block the way `accepting-submissions` does is not yet decided. 02 §11 and
   `schema/validators.py` need the answer.
3. **Evidence of use.** Can independent papers show that a benchmark is still in use? This is a
   classification-evidence ruling, not a vocabulary one, and it decides whether uspto-50k, Atari-100k,
   HarmBench and AudioSet read `active` or abstain. They no longer read `dormant` either way.
4. **Cases the batch could not settle:**
   - HAL's lifecycle: paused pending a successor, which no term fits.
   - LegalBench's primary domain: its claim and its task majority disagree.
   - Whether DREAM x CACHE is an edition of CACHE.
5. **Example refs that are not corpus ids** in the older examples (`tau2-bench`, `terminal-bench`,
   `arc-agi`, `vbench`, and more). Every example added in this batch uses a corpus id. Two corpus ids
   are themselves defective (`bench` for τ²-Bench, `humanity-s-last-exam`).
6. **02's per-facet term listings** (§4.1, §5, §6 and the lists under §7-§10) still enumerate the
   0.1.0 terms. The counts are generated, but the listings are prose, and they now trail the YAML.
7. **Counts in the other plan documents** (00, 01, 03, 05, 09, 10, 11 and 14 cite 204, 44 and 8,976).
   Check 9b's scope is 02 and 12, so these were not regenerated.
8. **02 contradicts itself on `wet-lab`.** The §10 changelog cites CASP for it, while §12.1 records
   CASP as `cluster`.

## Alternatives considered

- **One ADR per added term.** Rejected. 03 §8.3 batches proposals precisely so that one migration and
  one IRR run serve the batch, and 22 ADRs would repeat one retro-tag plan 22 times.
- **Accept every recurring proposal, including those 02 already decided against.** Rejected for
  `inference-efficiency` and `embargoed-until-release`, whose absence is deliberate in 02.
- **Leave the counts in 02 hand-typed and correct them by hand.** Rejected. The task forbids it, and
  it is how 02 came to carry wrong totals before (§14).

## Appendix: the written answer for every Stage 4 group

The five sections below are the curators' disposition tables. Each row is one group heading of the
Stage 4 revision list: an Added, Clarified, Example fixed, Rejected, Deferred or No-action answer, with
its reason.

### Disposition: capability (`taxonomy/capabilities.yaml`, `taxonomy/capability_groups.yaml`)

#### `capability` (46)

Files: `taxonomy/capabilities.yaml`, `taxonomy/capability_groups.yaml`. There were 44 terms and
there are now 45: `scientific-prediction` (ADR-0014). The groups file
still has 13 groups and check 9g passes ("13 groups partition 45 capabilities").

| Group (as in the list) | Records | Disposition |
|---|---|---|
| missing-term | 11 | Mixed, no term added; see the five sub-rows. Several records name two gaps, so the sub-row counts add up to more than 11 |
| &nbsp;&nbsp;missing-term: a "reasoning" claim that names no form (mmlu-pro-002, mmmu-pro-002, humanity-s-last-exam-002, helm-capabilities-001 for GPQA, swe-bench-verified-002, bench-002, financebench-001 for "logical reasoning") | 7 | **Rejected**: this does recur, but the only term that would cover it is a catch-all "reasoning" term, and 03 §5 bans "general" terms because they are abstentions dressed as terms. Such a term would also soak up every reasoning benchmark and empty the specific reasoning columns. The curator keeps the specific terms that pass their tests and records the unnamed claim in `curation.notes` |
| &nbsp;&nbsp;missing-term: engineering competence (swe-bench-verified-002, mle-bench-002, paperbench-002) | 3 | **Rejected**: this belongs in another facet. Software, ML and research engineering are what the benchmark covers, which is the domain axis (`code/repository-scale-se`, `code/ml-engineering`, `agents-tooluse/research-agents`). The capability axis is orthogonal to domain (02 §4) |
| &nbsp;&nbsp;missing-term: retrieval from a large corpus (financebench-001) | 1 | **Rejected**: one benchmark. The domain `language/retrieval-qa` and the subject `retrieval-augmented-system` already express it |
| &nbsp;&nbsp;missing-term: dialogue (helm-capabilities-001 for WildBench) and legal issue-spotting, rhetorical function and explanation quality (legalbench-vals-legal-bench-003) | 2 | **Rejected**: each is one benchmark, and each has a domain leaf that expresses it (`language/dialogue`, `society-econ-law/legal-reasoning`) |
| &nbsp;&nbsp;missing-term: goal inference and world-model building (arc-agi-3-002) | 1 | **Deferred**: one benchmark. Revisit if Phase 1 finds more interactive benchmarks that score an inferred goal or a world model |
| undefined-boundary | 11 | Clarified or example fixed; see the five sub-rows |
| &nbsp;&nbsp;undefined-boundary: `planning` vs interactive games (arc-agi-3-003, balrog-002, kaggle-game-arena-002) | 3 | **Clarified**: `planning`'s inclusion test now says that in an interactive episode with an explicit goal or objective, the executed action sequence is the plan, and its cost or outcome scores it, provided the source claims planning. The exclusion test now removes benchmarks that score an artifact the rollout produced (patch, document, answer). **Example fixed**: the kaggle-game-arena `why` was rewritten against the new test, and the swe-bench-verified near miss was reworded to match it |
| &nbsp;&nbsp;undefined-boundary: `long-horizon-execution` with partial credit (2026-behavior-challenge-001, balrog-003) | 2 | **Clarified**: the inclusion test now reads "makes full success on the episode unattainable", and says outright that partial credit for progress does not disqualify a benchmark |
| &nbsp;&nbsp;undefined-boundary: examples that contradict the term's tests or the sources (carla-leaderboard-2-0-002, gdpval-001, healthbench-002, libero-002, rexrank-001) | 5 | **Example fixed**: CARLA for `reliability-consistency`, GDPval for `autonomy`, HealthBench and ReXrank for `communication`, and LIBERO for `grounding` are now near misses, and in-scope positives replace them. The tests are unchanged, because widening `communication` to cover audience-appropriateness would over-tag (02 §11 rule 2) |
| &nbsp;&nbsp;undefined-boundary: mixed-motive games (melting-pot-001) | 1 | **Clarified**: `collaboration`'s exclusion test now carries a tie-break. A mixed-motive setting qualifies when the source claims cooperation and the score includes a joint outcome, and a zero-sum game does not. **Example fixed**: kaggle-game-arena was a near miss and is now qualifying, because its classification tags the Werewolf team board. lmarena is the new near miss |
| Proposed: `inference-efficiency` | 5 | **Rejected** (lead). 02 §4.4 retired `efficiency-compute` and `efficiency-latency` as capabilities for these very cases (Open ASR RTFx, HAL cost fronts) and replaced them with the benchmark field `secondary_axes: [cost, latency, throughput, energy, reliability]`; re-adding the concept under a new id would reverse that decision. The agent drafted the term; the lead removed it. |
| collision between `distribution-shift-generalization`, `transfer-learning` | 4 | **Clarified**: tie-break sentences are in both terms' tests, and `not_to_be_confused_with` is on both. The precedence rule the four records point to is this: if the task and its label set are unchanged and only the inputs move (site, population, machine, disease, recording conditions), tag `distribution-shift-generalization`, whatever the source calls it. `transfer-learning` is redefined to "one task, embodiment or environment to a different one", which drops "or distribution", the overlap that caused the collision. **Example fixed**: the positive `open-x-embodiment` was replaced by `libero`, and `brats-2026-cluster` was added as a near miss for `transfer-learning` |
| Proposed: `cross-lingual-transfer` | 2 | **Rejected**: two benchmarks, and the translation case is in the domain `language/translation`. The recurring escape hatch closes with a **Clarified** `generation-fidelity`: its inclusion test now says the target may be the source whose content the output must preserve, which is how human ESA and MQM grading works. wmt25-general-mt-shared-task was added as a positive |
| Proposed: `biological-fidelity` | 1 | **Deferred**: one benchmark. The domain leaf `biology-genetics/brain-model-alignment` already places it. Revisit if more neural-predictivity benchmarks are catalogued |
| Proposed: `covert-goal-pursuit` | 1 | **Deferred**: one benchmark in the corpus. The domain `safety-alignment/deception-scheming` places it. It should be settled together with the `situational-awareness` rename ADR (02 §4.2, D1 risk 10), which reshapes the same frontier-risk column |
| Proposed: `cross-query-consistency` | 1 | **Rejected**: one benchmark, and the vocabulary separates it from `reliability-consistency` on purpose (the inputs change between probes). video-mme-v2 was added as a near miss for `reliability-consistency` to record the boundary |
| Proposed: `general-capability-factor` | 1 | **Rejected**: 03 §5 bans "general" terms. The composite shape is carried by the domain `general-intelligence/agi-composite-suites` (ADR-0016) |
| Proposed: `human-preference-alignment` | 1 | **Rejected**: one benchmark. The arena shape is carried by the domain leaf `general-intelligence/open-preference-arenas` (ADR-0018) and by the evaluation method |
| Proposed: `output-diversity` | 1 | **Deferred**: one benchmark. `creativity-novelty`'s exclusion test deliberately leaves out variety that has no usefulness criterion. Revisit if Phase 1 generative benchmarks repeat the mode-coverage claim |
| Proposed: `population-response-modelling` | 1 | **Deferred**: one benchmark. The domain `society-econ-law/social-simulation` places it. Revisit when more silicon-sampling benchmarks are catalogued |
| Proposed: `representation-quality` | 1 | **Deferred**: needs more corpus evidence. geo-bench-2-002 names the same gap, adaptation of a pretrained representation, which makes two benchmarks, still below three. Phase 1 will catalogue many foundation-model probing suites |
| source-silent | 1 | No action: the sources were silent, not the vocabulary (medhelm-002) |
| undefined-boundary between `abstraction`, `compositional-generalization` | 1 | **Clarified**: `compositional-generalization`'s inclusion test now covers sources that do not enumerate their primitives. It is tagged only on a claim that held-out items combine rules already shown, and never where the source says they introduce new mechanics |
| undefined-boundary between `distribution-shift-generalization`, `spatial-reasoning`, `transfer-learning` | 1 | **Example fixed**: geo-bench-2 is now a near miss for `spatial-reasoning` (positive: balrog) and for `distribution-shift-generalization` (positive: fusion-equilibrium-challenge). `adversarial-robustness`'s geo-bench-2 near miss rested on a false premise and was replaced by fusion-equilibrium-challenge. The adaptation-of-pretraining gap is **Deferred** with `representation-quality` |
| undefined-boundary between `distribution-shift-generalization`, `transfer-learning` | 1 | **Clarified**: `distribution-shift-generalization`'s inclusion test now accepts a benchmark that reports scores on deliberately held-out inputs (for example unseen cell lines) as its own condition, with or without an in-distribution score beside it. The tie-break above assigns virtual-cell-challenge-2026 to it |
| undefined-boundary between `planning`, `sensorimotor-control` | 1 | **Clarified**: `sensorimotor-control`'s exclusion test now carries a tie-break. When the entrant supplies only a trajectory and a fixed controller of the benchmark's tracks it in a non-reactive simulation, tag `planning`. navsim-v2 was added as a `planning` positive |

##### ADR parts applied

- **ADR-0014**: `scientific-prediction` is added with the ADR's YAML as written (after `hypothesis-generation`) and put in group `causal-and-experimental-inference`. Check 9g is green. Two cross-references to it were added: the `generation-fidelity` exclusion test and the `optimization` near miss for open-catalyst-oc20-oc22.
- **ADR-0017 decision item 4**: every `inspect-evals` example (`adversarial-robustness`, `situational-awareness`, `honesty`, `harm-avoidance`) and every `open-x-embodiment` example (`continual-learning`, and `transfer-learning` too, under the same rule) is removed and replaced by an in-scope entry the term is tagged on.

##### Group placement for the lead to ratify

- (`inference-efficiency` was drafted into `learning-and-transfer` and then removed with the term; the groups are unchanged apart from `scientific-prediction`.)

##### Examples fixed (term, ref, old verdict, new verdict)

| Term | Ref | Old | New |
|---|---|---|---|
| spatial-reasoning | geo-bench-2 | true | false (near miss); balrog added, true |
| grounding | osworld-2-0 | true | false (near miss) |
| grounding | libero | true | false (near miss); dcase-2026 added, true |
| planning | kaggle-game-arena | true | true (`why` rewritten to the new test) |
| planning | swe-bench-verified | false | false (`why` reworded); navsim-v2 added, true |
| long-horizon-execution | osworld-2-0 | true | true (`why` rewritten: it described OSWorld 1.0) |
| long-horizon-execution | tau2-bench | true | false (near miss); terminal-bench-2-0 added, true |
| optimization | open-catalyst → open-catalyst-oc20-oc22 | true | false (near miss: `scientific-prediction`) |
| memory-retention | tau2-bench | true | false (near miss); arc-agi-3 added, true |
| sample-efficiency | proteingym | true | false (near miss, per proteingym-001); arc-agi-3 added, true |
| continual-learning | open-x-embodiment | true | removed (ADR-0017); libero and dcase-2026 added, true |
| distribution-shift-generalization | geo-bench-2 | true | false (near miss); fusion-equilibrium-challenge added, true |
| transfer-learning | open-x-embodiment | true | removed (ADR-0017); libero added, true; brats-2026-cluster added, false |
| adversarial-robustness | inspect-evals | true | removed (ADR-0017); agentdojo added, true |
| adversarial-robustness | geo-bench-2 | false | removed (false premise); fusion-equilibrium-challenge added, false |
| reliability-consistency | carla-leaderboard-2-0 | true | false (near miss); critpt added, true; video-mme-v2 added, false |
| self-correction | swe-bench-verified | true | false (near miss, per its classification note) |
| collaboration | kaggle-game-arena | false | true (Werewolf team board, per its classification); lmarena added, false |
| communication | healthbench | true | false (near miss) |
| communication | rexrank | true | false (near miss); tau2-bench added, true |
| situational-awareness | inspect-evals | true | removed (ADR-0017); apollo-research-scheming-suite added, true |
| honesty | inspect-evals | true | removed (ADR-0017); apollo-research-scheming-suite added, true |
| harm-avoidance | inspect-evals | true | removed (ADR-0017); agentharm added, true |
| autonomy | gdpval | true | false (near miss); mle-bench added, true |
| generation-fidelity | (new) wmt25-general-mt-shared-task | -- | true |

### Disposition: domain (`taxonomy/domains.yaml`)

The five ADR subdomains take the domain vocabulary from 204 to 209 pairs (19 families; 209 leaves,
all distinct). Check 9b's domain row and the "every count in 02" row fail until the lead
regenerates 02. Checks 9c, 9d and 9f pass, and seed targets are unchanged (sum 320, core 144).
`bench validate taxonomy/ --tier all` reports 0 blocking.

Two precedence rules recur below, and the tests now state both:
- **Claim over protocol, and claim over metric.** When a benchmark passes two families' tests,
  its own claim decides the primary. This covers general-intelligence vs games-planning, and
  medicine-health or earth-climate vs vision, where Dice, FROC and IoU never decide.
- **Grader over harness.** For code vs agents-tooluse, the family is decided by what the grader
  checks: software the entrant wrote (tests on a patch, or what the software computes) is code;
  a machine's end state is agents-tooluse. This is decided per benchmark, not per task.

#### `domain.primary` (39)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| undefined-boundary | 4 | **Clarified**, three of four. forecastbench: `society-econ-law`'s exclusion now keeps real-world-resolving forecasting in `forecasting-prediction-markets` whatever the topic (02 §12.8). minif2f-dafny: `mathematics/formal-theorem-proving` is redefined to "a proof assistant or automated verifier", gets tests and examples, and gets a `not_to_be_confused_with` with `code/program-verification` on both sides (the subject of the proof decides, not the tool). robotwin-2-0: `robotics-embodiment/bimanual-manipulation` is redefined and tested for the benchmark as a whole, not task by task. **Deferred**, srbench-2-0: whether symbolic regression belongs in physics or mathematics needs more corpus evidence, and moving `physics/symbolic-regression-discovery` would be a rename (MAJOR, out of scope). |
| Proposed: `biology-genetics/behavioral-alignment` | 1 | **Rejected**: one benchmark. Brain-Score's claim is brain alignment, so `brain-model-alignment` holds it, with a note on the behavioural (I2n) component. |
| Proposed: `biology-genetics/genome-annotation` | 1 | **Deferred**: needs more corpus evidence. GUE, Genomic Benchmarks and the Nucleotide Transformer tasks are not corpus entries, and `regulatory-genomics` holds four of BEND's seven tasks, a majority under ADR-0016's rule. |
| Proposed: `chemistry-materials/single-step-retrosynthesis` | 1 | **Deferred**: one benchmark, and no corpus entry would supply the near miss that a revised `retrosynthesis` needs. Expressible for now as `retrosynthesis` plus a note that USPTO-50k is single-step. |
| Proposed: `code/research-replication` | 1 | **Deferred**: one benchmark. CORE-Bench appears only as a HAL board, not as a corpus entry. `code/ml-engineering` plus a note stands. |
| Proposed: `earth-climate/subseasonal-seasonal-prediction` | 1 | **Rejected**: expressible with an existing term. `earth-climate/weather-forecasting` now has tests covering lead times up to the subseasonal-to-seasonal range, plus a `not_to_be_confused_with` for `climate-projection` (forcing scenarios decide). Lead-time range belongs in a schema field, not a term. |
| Proposed: `medicine-health/health-advice-quality` | 1 | **Deferred**: one benchmark. Whether `clinical-dialogue` should cover a single scored reply to a conversation needs a second open-ended health-advice entry. |
| Proposed: `medicine-health/medical-imaging-detection` | 1 | **Rejected** as a new term; **Clarified**. `medicine-health/medical-imaging-diagnostic` is redefined to cover detected findings as well as diagnoses, with tests and examples (camelyon17 and luna16 qualify; rexrank is the near miss). This resolves the other side of the recurring medicine vs vision two-primaries (brats, luna16). |
| Proposed: `protein-ligand-docking` | 1 | **Rejected** as a new term (merged); **Clarified**. `biology-genetics/protein-ligand-cofolding` is redefined to cover re-docking into a given protein, with tests and examples (runs-n-poses and posebusters qualify; cache-challenges is the near miss). Together with runs-n-poses and CASP17's ligand category, this covers three benchmarks. |
| Proposed: `robotics-embodiment/closed-loop-driving` | 1 | **Rejected**: one benchmark, and the distinction belongs in another facet. Closed vs open loop is a property of the evaluation protocol (`evaluation_method: simulation-rollout` for CARLA), not of the domain. |
| Proposed: `robotics-embodiment/generalist-policy-evaluation` | 1 | **Rejected**: one benchmark, and it belongs in other facets. The arena shape is carried by `evaluation_method: pairwise-preference-elo` and governance, and ADR-0018 and 02 §12.2 already file RoboArena under `manipulation`. |
| Proposed: `robotics-embodiment/lifelong-robot-learning` | 1 | **Rejected**: belongs in another facet. Forward transfer and forgetting across a task sequence is the capability `continual-learning`, and the domain stays `manipulation`. |
| collision between `agents-tooluse/computer-use-gui`, `agents-tooluse/long-horizon-autonomy` | 1 | **Clarified**. `computer-use-gui` gets tests with the tie-break (the interface is primary, the horizon secondary) and examples (osworld-2-0 qualifies; webarena is the near miss). `not_to_be_confused_with` is on both terms. |
| collision between `agents-tooluse/multi-agent-coordination`, `agents-tooluse/tool-api-calling` | 1 | **Clarified**. `tool-api-calling` gets tests (a simulated user, even one with tools, is part of the environment) and examples (bench qualifies; medagentbench-v2 and agentdojo are near misses). `not_to_be_confused_with` is on both terms. |
| collision between `agents-tooluse/software-agents`, `code/repository-scale-se` | 1 | **Clarified**. The family tests state the grader-over-harness rule, and `code` and `agents-tooluse` carry `not_to_be_confused_with` on both families. `software-agents` gets tests: primary only when the grader checks environment state, otherwise secondary (02 §12.11). Its examples: swe-bench-verified qualifies as secondary; terminal-bench-2-0 is the near miss. `not_to_be_confused_with` is on both subdomains. |
| collision between `multimodal/video-language`, `vision/video-understanding` | 1 | **Clarified**: `not_to_be_confused_with` on both. Video QA is `video-language` under 02 §11 rule 12, and `video-understanding` keeps label-scored recognition. |
| collision between `physics/fluid-dynamics`, `physics/simulation-surrogates` | 1 | **Clarified**: `not_to_be_confused_with` on both. A method-named surrogate benchmark whose claim spans several physical systems is `simulation-surrogates`; a benchmark with one physical system as its subject takes that subject's subdomain. |
| escape-hatch-used | 1 | **Clarified**. `biology-genetics/single-cell-analysis` is redefined to cover spatial omics and the other cell-level tasks, with tests and examples (open-problems qualifies; virtual-cell-challenge-2026 is the near miss). |
| two-primaries between `audio-speech/audio-event-detection-localization`, `audio-speech/audio-event-understanding`, `audio-speech/machine-condition-monitoring` | 1 | **No action**: 02 §12.9 decides DCASE's primary (`audio-event-understanding`) and carries the per-task domains as children with `domain_override`. An audio suite subdomain would need its own add ADR citing ADR-0016. |
| two-primaries between `biology-genetics/nucleic-acid-structure`, `biology-genetics/protein-ligand-cofolding`, `biology-genetics/protein-protein-interaction`, `biology-genetics/protein-structure-prediction` | 1 | **No action**: 02 §12.1 decides CASP17's primary (`protein-structure-prediction`, on the assessment's own framing). A biology suite subdomain would need its own add ADR citing ADR-0016. |
| two-primaries between `earth-climate/hazard-prediction`, `earth-climate/remote-sensing`, `vision/segmentation` | 1 | **Clarified**, together with the next row. The `earth-climate` exclusion test now says when a vision task is "generic". `remote-sensing` gets tests and examples (geo-bench-2 and sen1floods11 qualify; cy-bench is the near miss), including "mapping a hazard already visible is remote sensing, not `hazard-prediction`". `vision`'s exclusion states the same rule from its side. |
| two-primaries between `earth-climate/remote-sensing`, `vision/segmentation` | 1 | **Clarified**. This pair collides in two records (with sen1floods11), so it gets `not_to_be_confused_with` on both terms and a tie-break in `remote-sensing`'s tests: Earth-system labels or an Earth-observation claim make remote sensing primary, and the vision task secondary. |
| two-primaries between `games-planning/puzzle-games`, `general-intelligence/novel-task-acquisition` | 1 | **Clarified**. `general-intelligence`'s inclusion test says the claim decides when another family's protocol test also passes. `games-planning`'s exclusion states the same rule from its side (02 §12.7). `not_to_be_confused_with` is on both subdomains. |
| two-primaries between `general-intelligence/abstraction-generalization`, `reasoning-general/abstraction-induction` | 1 | **Clarified**. `abstraction-generalization` gets tests and examples (arc-agi-2 qualifies; arc-agi-3 is the near miss). `reasoning-general`'s exclusion now defers a general or fluid intelligence claim to `general-intelligence`. `not_to_be_confused_with` is on both. |
| two-primaries between `medicine-health/medical-imaging-segmentation`, `vision/medical-imaging-cv` | 1 | **Clarified**. This pair and the luna16 case collide in two records, so the rule is claim over metric. It is stated in the `medicine-health` and `vision` exclusions and in the tests of `medical-imaging-segmentation` (brats qualifies; luna16 is the near miss) and `medical-imaging-diagnostic`. `vision/medical-imaging-cv` is redefined to cover a vision method on medical images, with tests; both its examples are near misses, because no corpus entry qualifies. `not_to_be_confused_with` is on both. |
| two-primaries between `vision/novel-view-synthesis`, `vision/segmentation` | 1 | **Example fixed**: the `vision` family example `scannetpp` is replaced by `scannet`, with the tracks ScanNet++ actually has (see below). The primary itself needs no term change: three of five boards are NVS, so the majority reading of ADR-0016 decides it. The 3D-labels gap is scannet-002 (secondary, deferred). |
| undefined-boundary between `agents-tooluse/long-horizon-autonomy`, `code/ml-engineering` | 1 | **Clarified**. `code`'s inclusion test now admits scoring what the entrant's software computes (a trained model's predictions), so MLE-bench's CSV no longer fails it. `code` gains mle-bench as a qualifying example. `long-horizon-autonomy` carries a `not_to_be_confused_with` saying it is primary only when no interface or task subdomain applies. |
| undefined-boundary between `agents-tooluse/operating-system-tasks`, `code/repository-scale-se` | 1 | **Clarified**. The `agents-tooluse` and `code` exclusions state the grader-over-harness rule, decided per benchmark, not per task: a checked machine end state is agents-tooluse even where some tasks leave a program behind. |
| undefined-boundary between `agents-tooluse/tool-api-calling`, `safety-alignment/prompt-injection` | 1 | **Clarified**. `prompt-injection` gets tests: a security claim wins even with a utility track beside it. Its examples: agentdojo qualifies; agentharm is the near miss. `not_to_be_confused_with` is on both terms. |
| undefined-boundary between `audio-speech/bioacoustics`, `earth-climate/ecology-biodiversity`, `language/information-extraction`, `vision/classification`, `vision/detection` | 1 | **Clarified**. `earth-climate/ecology-biodiversity` is redefined to include species identification, with tests: a biodiversity claim across modalities is primary here, and a single-method task stays with its method. Examples: lifeclef-2026 qualifies; cy-bench is the near miss. It carries a `not_to_be_confused_with` for `bioacoustics`. |
| undefined-boundary between `biology-genetics/protein-ligand-cofolding`, `chemistry-materials` | 1 | **Clarified**. This pair collides in two records (with posebusters), so both family exclusion tests now draw the same line: a bound pose or affinity is biology; the molecule's own properties or assay-scored hits are chemistry. `not_to_be_confused_with` is on both terms, and on both families. `chemistry-materials` gains runs-n-poses as a near miss. |
| undefined-boundary between `general-intelligence/agi-composite-suites`, `multimodal/visual-qa` | 1 | **Clarified**, applying ADR-0015's consequence. `general-intelligence`'s exclusion sends an exam whose every item needs the image to `multimodal`. `multimodal/visual-qa` carries a `not_to_be_confused_with` for `multi-subject-knowledge-exams`: an exam with a minority of image items keeps the exam primary. |
| undefined-boundary between `multimodal/any-to-any-generation`, `vision/video-generation` | 1 | **Clarified**: `not_to_be_confused_with` on both. The benchmark's headline claim (fidelity of the video vs adherence to the prompt) decides, and the other goes secondary. |
| undefined-boundary between `multimodal/visual-qa`, `vision/document-understanding` | 1 | **Clarified**: `not_to_be_confused_with` on both. Document-image QA is `visual-qa`, and `document-understanding` keeps benchmarks scored on extracted structure or content. |
| undefined-boundary between `safety-alignment/dangerous-capability-evals`, `safety-alignment/unlearning-knowledge-removal` | 1 | **Clarified**. The `safety-alignment` definition and tests now admit hazardous capability measured as knowledge, and the family gains wmdp as a qualifying example. `not_to_be_confused_with` is on both subdomains: `dangerous-capability-evals` is primary when models are ranked as released, and unlearning when removal methods are ranked. |
| undefined-boundary between `society-econ-law/legal-document`, `society-econ-law/legal-reasoning` | 1 | **Deferred**: needs more corpus evidence. ADR-0016's majority reading would point to `legal-document` (about 117 of 162 tasks are interpretation), while the benchmark's claim points to `legal-reasoning`, and a single legal entry cannot settle which rule governs a within-family split. |

#### `domain.secondary` (8)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `audio-speech/source-separation` | 1 | **Deferred**: one benchmark task (DCASE Task 4). A second separation benchmark is needed. |
| Proposed: `biology-genetics/conformational-ensemble-prediction` | 1 | **Deferred**: one benchmark (one CASP17 category). A second ensemble benchmark is needed. |
| Proposed: `language/evaluation-metrics` | 1 | **Deferred**: one benchmark track in the corpus. The WMT metrics task is not a corpus entry. |
| Proposed: `vision/3d-scene-understanding` | 1 | **Deferred**: one benchmark (ScanNet++). S3DIS and ScanNet200 are not corpus entries. `vision/segmentation` plus a note stands. |
| Proposed: `vision/pose-estimation` | 1 | **Deferred**: one benchmark (COCO keypoints and DensePose). More corpus evidence is needed. |
| Proposed: `vision/quality-assessment` | 1 | **Deferred**: one benchmark (NTIRE tracks). More corpus evidence is needed. |
| undefined-boundary | 1 | **Deferred**: one benchmark (two of WMT25's four domains). Whether a video or screenshot source makes a translation benchmark partly multimodal needs a second multimodal-source MT entry. |
| undefined-boundary between `biology-genetics/drug-target-interaction`, `chemistry-materials/drug-discovery-admet` | 1 | **Clarified**. The `biology-genetics` exclusion no longer removes binding prediction for a drug candidate: binding a protein stays in biology, and assay-scored hits are chemistry. `drug-target-interaction` gains a `not_to_be_confused_with` for `drug-discovery-admet`, whose side already existed. |

#### ADR parts applied

- **ADR-0015**: added `general-intelligence/multi-subject-knowledge-exams`, verbatim, placed after
  `human-comparison-batteries`. The only change is that the `why` values use folded style, as the
  surrounding terms do.
- **ADR-0016**: added `medicine-health/clinical-task-suites`, `agents-tooluse/agent-evaluation-suites`
  and `games-planning/multi-game-suites`, each last in its family.
  - Each carries the shared definition and tests, with the family named.
  - Each carries a YAML comment in the definition block saying that a suite row counts suites, not
    task coverage. The multi-game term's comment also says that `evaluation_method` separates an
    arena from an environment suite.
  - The ADR gives no examples, so these were added:
    - `clinical-task-suites`: medhelm qualifies; healthbench is the near miss.
    - `agent-evaluation-suites`: holistic-agent-leaderboard-hal qualifies; webarena is the near
      miss.
    - `multi-game-suites`: kaggle-game-arena and balrog qualify; atari-100k is the near miss.
- **ADR-0018**: added `general-intelligence/open-preference-arenas`, verbatim, placed after
  `agi-composite-suites`. Its `why` values use folded style.

#### Examples fixed

| Term | Ref | Old verdict | New verdict |
|---|---|---|---|
| `vision` | `scannetpp` -> `scannet` | true ("Dense 3D scene understanding scored as reconstruction and segmentation quality") | true. The ref is now the corpus id, and the `why` is now "novel views scored against held-out DSLR photographs, and 3D semantic and instance labels scored on the laser-scan mesh". No ScanNet++ track scores reconstructed geometry (scannet-001). |
| `safety-alignment` | `humanitys-last-exam` -> `humanity-s-last-exam` | false ("scores only whether answers are correct") | false. The ref is now the corpus id. The old reason contradicted the revised tests, because WMDP also scores only correctness yet qualifies. The `why` now rests on HLE's claim, academic breadth, with hazardous items incidental (wmdp-001). |

Examples added to existing family terms, not fixes:
- `chemistry-materials`: runs-n-poses, qualifies false.
- `code`: mle-bench, qualifies true.
- `safety-alignment`: wmdp, qualifies true.

### methods-subjects: Stage 4 dispositions (P1-S1-T07)

Files: `taxonomy/evaluation-methods.yaml` (27 -> 31 terms), `taxonomy/subjects.yaml` (18 -> 21 terms).
New terms are `status: active`, `introduced_in: 1.0.0`, `source: own`. No id was renamed, removed,
merged or retired. `version:` / `updated:` headers untouched.

#### `evaluation_method` (54)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `classification-metric` | 9 | **Added** `classification-metric` (9 benchmarks: bend, brats-2026-cluster, camelyon17, dcase-2026, lifeclef-2026, matbench-discovery, medhelm, ntire, open-problems). Covers F1, precision/recall, AUROC, AUPRC, MCC, kappa, balanced/macro accuracy, ARI. Tie-breaks: plain per-item accuracy stays `exact-match`; MCC/kappa on labels beat `statistical-fit`; field-only measures (mAP over IoU, Dice, FROC) stay `domain-metric`. `not_to_be_confused_with` both ways with `exact-match`, `statistical-fit`, `domain-metric` |
| Proposed: `environment-state-check` | 7 | **Added** `environment-state-check` (agentdojo, agentharm, apollo, bench, medagentbench-v2, osworld-2-0, webarena). Admits per-checkpoint credit and checks on tool calls (agentharm). Tie-breaks against `constraint-check`, `simulation-rollout` and `execution-tests` (tests in the agent's container: code the agent wrote -> execution-tests, state it changed -> this term). `not_to_be_confused_with` both ways with `constraint-check` and `simulation-rollout`; constraint-check's exclusion now points here |
| undefined-boundary | 6 | **Example fixed** x4 and **Clarified** x2. coco-002: composite `coco` example flipped to a near miss (one metric over its own IoU/category sweep), coco added as a `domain-metric` positive, composite's exclusion now names categories, datasets and tasks scored the same way. rexrank-003: composite `rexrank` example flipped to qualifies (RadCliQ-v1 is the primary composite). gdpval-002: `human-distribution-percentile` `gdpval` example flipped to a near miss (one expert deliverable per task). healthbench-003: `human-expert-eval` `healthbench` example flipped to a near miss (physicians only meta-evaluated the grader). robotwin-2-0-002: `physical-trial` `robotwin-2-0` example flipped to a near miss, roboarena added as positive, exclusion now drops one-off hardware validation runs. atari-100k-001: **Clarified** `episodic-return` exclusion -- normalising against a constant agents exceed (human-normalised Atari) leaves the metric unbounded, so both editions are episodic-return. The "win rate against a fixed human deliverable" gap (gdpval) and "judge validated against experts" gap (healthbench) are one benchmark each: rejected, notes suffice |
| Proposed: `numeric-tolerance-match` | 2 | **Added** `numeric-tolerance-match` (critpt, financebench). Two benchmarks only, accepted on the recurring-escape-hatch argument: every benchmark with a computed real-valued answer must pick a tolerance, the two cases come from unrelated families (physics research QA, financial QA), it is the headline answer format in both, and the only alternatives were forcing `exact-match` against its own test or a human-rating term. `not_to_be_confused_with` both ways with `exact-match` |
| Proposed: `entrant-relative-ranking` | 2 | **Added** `entrant-relative-ranking`. Merges the pool-dependence half of `latent-trait-scaling` (epoch-capabilities-index-002), of `proper-scoring-rule` (forecastbench-002) and the Z-score aggregation of casp16-na-rna-002, so it covers 5 benchmarks (brats-2026-cluster, medhelm, casp16-na, epoch-capabilities-index, forecastbench). Excludes fixed-control normalisation (open-problems). `not_to_be_confused_with` both ways with `composite`, `pairwise-preference-elo`, `tournament-play` |
| collision between `model-derived-metric`, `reference-metric` | 2 | **Clarified**: COMET, BLEURT, MetricX, BERTScore moved out of reference-metric's inclusion into model-derived-metric's; reference-metric is "computed by a fixed formula"; model-derived-metric governs for the same number. `not_to_be_confused_with` now on both |
| escape-hatch-used | 2 | **Clarified** (arc-agi-3, balrog): `simulation-rollout` redefined from "success rate" to "a bounded outcome, success or partial credit, of episodes run in a simulator"; inclusion lists predicate fraction, discounted route completion and capped efficiency against a baseline, and asks for the per-episode formula on the Metric. ARC-AGI-3's paired cost axis is a Metric/reporting concern (02 S5), not a method |
| Proposed: `confidential-judge` | 1 | **Rejected**: one benchmark (ailuminate-v1-1), and it belongs in the schema (a "withheld" state for the judge-identity field), not a method term. model-graded-judge's inclusion now says the term still applies when the judge is withheld |
| Proposed: `latent-trait-scaling` | 1 | **Added** as part of `entrant-relative-ranking` (the pool-relative scale). The IRT-style fit itself is rejected: one benchmark, a Metric definition |
| Proposed: `learning-curve-transfer-metric` | 1 | **Rejected**: one benchmark (libero); the measurement is `simulation-rollout`, and FWT/NBT/AUC are Metric definitions over it |
| Proposed: `model-complexity-measure` | 1 | **Rejected**: one benchmark (srbench-2-0); an accuracy-size Pareto front is a two-axis Metric and reporting concern (02 S5 "no legitimate aggregate"), not a method |
| Proposed: `proper-scoring-rule` | 1 | **Clarified** instead of added: `uncertainty-calibration-score` redefined to "scores an emitted confidence, interval or distribution", inclusion names proper rules (CRPS, Brier, log score), and the exclusion that sent future events to `prospective-resolution` is replaced by "carries both" (timing vs scoring). forecastbench example flipped to qualifies. Pool half goes to `entrant-relative-ranking` |
| Proposed: `pseudo-simulation` | 1 | **Deferred**: one benchmark (navsim-v2); `composite` + `constraint-check` carry EPDMS; log-replay pseudo-simulation may recur in driving, needs more corpus evidence |
| Proposed: `simulation-rollout-graded` | 1 | **Clarified**: merged into the `simulation-rollout` redefinition (carla-leaderboard-2-0 added as a positive example) |
| Proposed: `simulation-rollout-partial-credit` | 1 | **Clarified**: merged into the `simulation-rollout` redefinition (2026-behavior-challenge) |
| Proposed: `simulator-reevaluation` | 1 | **Deferred**: one benchmark (open-catalyst-oc20-oc22); expressible as `domain-metric` plus a note, the DFT cost belongs to compute_tier; recurrence in materials needs evidence |
| collision between `composite`, `domain-metric`, `model-derived-metric`, `statistical-fit` | 1 | **Clarified** (brain-score): a mapping regression fitted afresh per submission is not a scoring model (model-derived-metric exclusion; brain-score added as near miss), general statistics stay `statistical-fit`, and averaging one method across benchmarks is not `composite` |
| collision between `domain-metric`, `model-derived-metric` | 1 | **Clarified** (rexrank-002, also in brain-score-003): a field-standard metric computed by a model (FID, RadGraph-F1, SembScore) is `model-derived-metric`; FID removed from domain-metric's inclusion. `not_to_be_confused_with` on both |
| collision between `domain-metric`, `statistical-fit`, `uncertainty-calibration-score` | 1 | **Clarified** (weatherbench-2-002, with chaosbench-003 = 2 records for the CRPS pair): CRPS/CRPSS go to `uncertainty-calibration-score` and leave domain-metric's inclusion; RMSE/ACC stay `statistical-fit` even when WMO/ECMWF fix their definition. `not_to_be_confused_with` domain-metric<->uncertainty-calibration-score and domain-metric<->statistical-fit on both sides; weatherbench-2 added as a u-c-s positive |
| collision between `domain-metric`, `uncertainty-calibration-score` | 1 | **Clarified** (chaosbench): as above. SpecDiv/SpecRes (new, field-specific) need no change |
| collision between `expert-panel-assessment`, `human-expert-eval` | 1 | **Clarified** (cache-challenges): a committee's collective score per participant is `expert-panel-assessment` (both tests say so) |
| collision between `formal-proof-check`, `symbolic-equivalence` | 1 | **Example fixed** + **Clarified** (frontiermath): symbolic-equivalence's FrontierMath example now rests on Tiers 1-4 SymPy, not Lean; "or proof assistant" dropped from its inclusion; exclusion sends a proof assistant's verdict to `formal-proof-check` |
| collision between `human-crowd-eval`, `human-expert-eval` | 1 | **Clarified** (wmt25): a screen on platform performance or fluency is not a domain qualification; professionally credentialed raters are `human-expert-eval` |
| collision between `model-derived-metric`, `model-graded-judge` | 1 | **Clarified** (harmbench; ailuminate-001 raises the same boundary = 2 records): a released classifier fine-tuned to a fixed label set (guard classifiers) is `model-derived-metric`; a general model prompted to grade is `model-graded-judge`. Tie-break in both tests, `not_to_be_confused_with` distinctions rewritten; harmbench added as a model-derived-metric positive |
| escape-hatch-used between `composite`, `multiple-choice` | 1 | **Rejected**: one benchmark (video-mme-v2); `multiple-choice` plus a Metric note on the group-level non-linear score records it |
| source-silent | 1 | No action: the sources were silent, not the vocabulary (virtual-cell-challenge-2026) |
| undefined-boundary between `composite`, `domain-metric` | 1 | **Clarified** (casp16-na-rna): the Z-score aggregation is `entrant-relative-ranking`; composite's exclusion makes same-method aggregation explicit; the new term's example is this benchmark |
| undefined-boundary between `constraint-check`, `formal-proof-check` | 1 | **Clarified** (minif2f-dafny): formal-proof-check's inclusion names SMT-backed program verifiers (Dafny) and treats the spec-preservation check as part of the verdict; minif2f-dafny added as positive |
| undefined-boundary between `expert-panel-assessment`, `prospective-resolution` | 1 | **Clarified** (casp17): on a benchmark, tag prospective-resolution only if the protocol guarantees the answer does not yet exist for its targets |
| undefined-boundary between `human-expert-eval`, `prospective-resolution` | 1 | **Clarified** (wmt25): post-deadline grading of submissions is not resolution; wmt25 added as a prospective-resolution near miss |
| undefined-boundary between `prospective-resolution`, `wet-lab-validation` | 1 | **Clarified** (cafa): an experiment run after the deadline independently of the predictions is `prospective-resolution`; wet-lab-validation's exclusion says so |

#### `designed_for_subjects` (49)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `model-in-benchmark-harness` | 15 | **Added** `model-in-benchmark-harness` (15 benchmarks). agent-scaffold's inclusion now requires an entrant-supplied loop and its exclusion points here; instruction-tuned-model's and tool-augmented-model's exclusions split "harness" into entrant-supplied (agent-scaffold) and benchmark-supplied (this term). `not_to_be_confused_with` both ways with `agent-scaffold`, `instruction-tuned-model`, `tool-augmented-model` |
| Proposed: `task-specific-supervised-model` | 10 | **Added** `task-specific-supervised-model` (merges `trained-perception-model`, `task-trained-ml-method`, `learned-planner`, and covers wmt25-006; 13+ benchmarks). Precedence against `domain-specialist-model`: a task defined by a scientific, clinical or engineering-design discipline (the named domain families) stays domain-specialist; general perception/language/audio tasks take this term. Covers refit-per-dataset procedures (SR, AutoML), models scored as they stand (Brain-Score), open-loop learned planners (NAVSIM), and restoration networks (vs `generative-media-model`). `not_to_be_confused_with` both ways with `domain-specialist-model` and `generative-media-model`; one-way with `rl-policy` (rl-policy's exclusion carries the reverse) |
| undefined-boundary | 6 | **Example fixed** x3 and **Clarified** x3. healthbench-004 and medhelm-005: `domain-specialist-model` examples `healthbench` and `medhelm` flipped to near misses (general frontier models only); exclusion now says the tag describes the model, not the benchmark's subject matter; rexrank, bend, geo-bench-2 added as positives. bench-005: `multi-agent-system` exclusion drops benchmark-supplied counterparts (simulated user), and the tau2-bench example flipped to a near miss (ref `bench`); melting-pot added as positive. posebusters-003 and uspto-50k-003: `classical-algorithm` tests now state that constants fitted once (empirical docking scoring function) or rules/frequencies tabulated from training data do not make a method learned; a trained model or a per-dataset structure search (SR) does; posebusters added as positive. video-mme-v2-004: `human-expert` inclusion admits construction or validation staff who sat the task, with a notes requirement |
| Proposed: `attack-or-intervention-method` | 2 | **Added** `attack-or-intervention-method` (harmbench, wmdp, and agentharm-004's second gap = 3 benchmarks). Examples harmbench, wmdp, agentharm; near miss ailuminate-v1-1 |
| Proposed: `autonomy-stack` | 1 | **Deferred**: one benchmark (carla-leaderboard-2-0); tag `rl-policy` for learned agents and `classical-algorithm` for non-learned ones (classical-algorithm no longer requires "for comparison"); hybrid modular stacks need more corpus evidence |
| Proposed: `embodied-controller-any-method` | 1 | **Rejected**: one benchmark; designed_for_subjects is multi-valued -- `rl-policy` for learned entrants plus `classical-algorithm` for TAMP entrants, now that classical-algorithm admits competing entrants |
| Proposed: `learned-planner` | 1 | **Added** as part of `task-specific-supervised-model` (open-loop learned planner); navsim-v2 added as an rl-policy near miss |
| Proposed: `learning-algorithm` | 1 | **Rejected** as a term, **Clarified**: one benchmark (libero); rl-policy's inclusion now says the policy and the learning procedure that produces it are one entrant; libero added as an rl-policy positive |
| Proposed: `named-model-any-elicitation` | 1 | **Rejected**: one benchmark (epoch-capabilities-index); a meta-index pooling other benchmarks' claims inherits their subjects, and the divergence belongs on claim-level `subject_type`, not a benchmark term |
| Proposed: `policy-on-standard-hardware` | 1 | **Rejected** as a term, **Clarified**: one benchmark (roboarena); physical-robot-system's inclusion states the precedence rule -- evaluator-owned standard hardware is still recorded as the hardware, the entrant is the policy; roboarena added as positive |
| Proposed: `pretrained-vision-backbone` | 1 | **Rejected** as a term, **Clarified**: one benchmark (geo-bench-2); fine-tuning a general backbone on a discipline's data is specialisation, so `domain-specialist-model` applies (inclusion rewritten, geo-bench-2 added as positive) |
| Proposed: `submitted-predictive-pipeline` | 1 | **Rejected**: one benchmark (simulacrabench); fitted statistical predictors are `task-specific-supervised-model`, crowd baselines `classical-algorithm`; excluding API models is an EvalConditions (network) fact |
| Proposed: `task-trained-ml-method` | 1 | **Added** as part of `task-specific-supervised-model` (refit-per-dataset procedures); srbench-2-0 is a positive example |
| Proposed: `trained-perception-model` | 1 | **Added** as part of `task-specific-supervised-model` (models trained for another task, scored as they stand); brain-score is a positive example |
| collision between `human-ai-team`, `human-expert` | 1 | **Example fixed** + **Clarified** (casp16): a human-labelled category that admits undisclosed machine help is `human-ai-team`; human-expert needs unaided humans. human-expert's `casp16` example flipped to a near miss (paperbench added as positive); human-ai-team's `casp16` why rewritten; its exclusion rephrased so CASP's separate ranking of human groups does not trip it. `not_to_be_confused_with` on both |
| collision between `retrieval-augmented-system`, `tool-augmented-model` | 1 | **Clarified** (gpqa-diamond): a single search tool the model calls itself is `tool-augmented-model`; a retriever built into the entrant is `retrieval-augmented-system`. gpqa-diamond added as a near miss; `not_to_be_confused_with` on tool-augmented-model |
| escape-hatch-used | 1 | **Added** (wmt25-006): purpose-built MT systems are `task-specific-supervised-model` (translation is a task, not a discipline) |
| undefined-boundary between `classical-algorithm`, `scientific-surrogate-model` | 1 | **Example fixed** + **Clarified** (weatherbench-2): classical-algorithm's `weatherbench-2` example flipped to qualifies (IFS HRES/ENS are scored rows; ERA5 is the truth); the tests now say a baseline that anchors a scorecard is still an entrant, and the comparator requirement is gone; fusion-equilibrium-challenge (EFIT as ground truth) is the new near miss |
| undefined-boundary between `domain-specialist-model`, `scientific-surrogate-model` | 1 | **Clarified** (virtual-cell-challenge-2026): `scientific-surrogate-model` redefined to "physical, chemical or biological process" and "laboratory assay"; general models scored against measurements they were not trained to emulate stay domain-specialist; virtual-cell added as positive |
| undefined-boundary between `human-expert`, `human-nonexpert` | 1 | **Clarified** (gpqa-diamond): expertise is judged against the benchmark's own domain; PhDs answering outside their field are `human-nonexpert` (exclusion now "a screen for expertise in the benchmark's own domain"); gpqa-diamond added as a human-nonexpert positive |

#### ADR parts applied

- None of ADR-0014 to ADR-0019 edits these two files.
- ADR-0017 respected: neither file cites `metriq-qed-c`, `inspect-evals` or `open-x-embodiment` as an
  example (none did before either). Their records (metriq-qed-c-002, inspect-evals-003) stay closed
  by the ruling; no `hardware-device` / `quantum-hardware-device` subject and no
  `inherited-from-constituent-benchmarks` method was added.

#### Examples fixed

| File | Term | Ref | Old verdict | New verdict |
|---|---|---|---|---|
| evaluation-methods | `composite` | coco | qualifies: true | qualifies: false (one metric over its own IoU/category sweep) |
| evaluation-methods | `composite` | rexrank | qualifies: false | qualifies: true (RadCliQ-v1 is the primary composite) |
| evaluation-methods | `human-distribution-percentile` | gdpval | qualifies: true | qualifies: false (single expert deliverable) |
| evaluation-methods | `human-expert-eval` | healthbench | qualifies: true | qualifies: false (physicians only meta-evaluated the model grader) |
| evaluation-methods | `physical-trial` | robotwin-2-0 | qualifies: true | qualifies: false (real-arm runs validate the data generator; protocol is simulated) |
| evaluation-methods | `symbolic-equivalence` | frontiermath -> frontiermath-tiers-erd-s | qualifies: true (Lean basis) | qualifies: true, why corrected to the Tiers 1-4 SymPy basis |
| evaluation-methods | `uncertainty-calibration-score` | forecastbench | qualifies: false | qualifies: true (Brier is a proper rule; prospective-resolution tagged beside it) -- follows the redefinition |
| subjects | `domain-specialist-model` | medhelm | qualifies: true | qualifies: false (general frontier models only) |
| subjects | `domain-specialist-model` | healthbench | qualifies: true | qualifies: false (general frontier assistants only) |
| subjects | `multi-agent-system` | tau2-bench -> bench | qualifies: true | qualifies: false (benchmark-supplied simulated user) |
| subjects | `classical-algorithm` | weatherbench-2 | qualifies: false | qualifies: true (IFS rows are scored entrants; ERA5 is the truth) |
| subjects | `human-expert` | casp16 | qualifies: true | qualifies: false (human groups are machine-assisted: human-ai-team) |
| subjects | `physical-robot-system` | robotwin-2-0 | qualifies: true | qualifies: false (same robotwin-2-0-002 finding as physical-trial) |

Also rewritten without a verdict change: human-ai-team `casp16` why; agent-scaffold `osworld-2-0` why
(entrant-supplied agent code); tool-augmented-model `tau2-bench` near miss (ref -> `bench`, why names
the new term).

#### Follow-ups for the lead

- Classification records that the clarified tests now read differently (records untouched, per the
  brief): coco/composite; brain-score/composite and model-derived-metric; chaosbench CRPSS
  (domain-metric -> uncertainty-calibration-score); forecastbench (add uncertainty-calibration-score);
  casp16-na-rna (add entrant-relative-ranking); the 7 environment-state-check benchmarks; the 9
  classification-metric benchmarks (bend and camelyon17 currently carry statistical-fit); casp16 and
  casp16-na-rna human-expert (-> human-ai-team only); weatherbench-2 classical-algorithm (now tagged);
  bench multi-agent-system (now not tagged); the 13 task-specific-supervised-model benchmarks.
- 02 S5/S6 prose counts ("Twenty-seven terms", "Eighteen terms") and 9b rows need regenerating
  (27 -> 31, 18 -> 21).

### governance-lifecycle: Stage 4 dispositions (P1-S1-T07)

Files: `taxonomy/governance.yaml`, `taxonomy/lifecycle.yaml`. Fields: `governance.submission_process`,
`lifecycle`, `governance.maintainer_type`, `activity`, `governance.independence_flags` (in the order
of the Stage 4 list).

Terms added (7): `maintainer-run`, `literature-only`, `open-source-gated`,
`maintainer-scored-predictions` (submission_process); `grader-from-evaluated-party`
(independence_flags); `no-submission-channel`, `results-pending` (activity).

Existing terms given tests, examples and `not_to_be_confused_with` (27): maintainer_type `academic-lab`,
`industry-lab`, `consortium`, `conference-workshop`, `nonprofit`, `government-agency`, `individual`,
`community-collective`; submission_process `self-reported`, `maintainer-verified`, `sandboxed-rerun`,
`held-out-server`, `publication-gated`; independence_flags `no-known-conflict`,
`funded-by-evaluated-party`; lifecycle `active`, `mature`, `superseded`, `under-revision`, `deprecated`,
`dormant`; activity `accepting-submissions`, `between-rounds`, `leaderboard-live-no-round`, `closed`,
`unknown`. Definitions were left as they were, except `dormant` and `mature` (ADR-0019).

Precedence rules for single-valued fields that describe layered benchmarks (brief rule 4), written into
the tests of the terms concerned:

- **maintainer_type: the holder.** The field names the party that holds and publishes the benchmark as
  distributed (its dataset and repository). Authors' affiliations, funders, contributors, and a partner
  that runs a results page or supplies data do not decide it. A personal-account host with no
  institution named as holder is `individual`. If nobody holds the benchmark any longer, it takes the
  originator's type and the decay goes to `maintenance_status` (02 §9). The one override is
  `conference-workshop`, which applies to a recurring challenge whose organising team re-forms each
  edition. Most records point this way: agentharm-007, wmdp-006, humanity-s-last-exam-006,
  open-catalyst-oc20-oc22-005, medagentbench-v2-006 and cy-bench-004 assigned by holder, and gpqa-diamond,
  bend and matbench-discovery name the personal-account host as the key-person risk.
- **lifecycle and activity: the entry as catalogued.** An edition or version entry takes its own
  standing, not its family's, and a family entry is `active` while any member produces results. Five of
  the six active/superseded records applied this rule (carla, iwslt, srbench, terminal-bench, wmt25).
- **lifecycle: the instrument, not its originators.** The originators' inactivity (a last commit, an
  archived repository) is `maintenance_status` evidence and is never by itself `dormant`. This is 02
  §8's three-field split.

#### `governance.submission_process` (52)

The benchmarks with no submission channel fall into **two distinct states, not five**. The records show
one real difference. In the first, the maintainer keeps a ranking or results table filled with systems
it chose and ran (FrontierMath, HLE, HELM, PaperBench's README table). In the second, no ranking exists,
and apart from the release paper's own baselines the results appear only in other people's papers
(uspto-50k, atari-100k, libero, the-well). Every paper benchmark publishes baselines, so "the maintainer
ran the only published results" cannot separate the proposals. The tie-break is whether the maintainer
keeps a ranking.

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `maintainer-run-no-submissions` | 15 | **Added**, split between the two terms below by the tie-break in their tests. Where the maintainer keeps a ranking or results table of systems it chose and ran (e.g. healthbench, helm-capabilities, medhelm, paperbench), the term is `maintainer-run`. Where only the release paper's baselines exist and others publish independently (e.g. uspto-50k, audioset, bend, posebusters, runs-n-poses, sen1floods11), it is `literature-only`. P1-S1-T08 sorts each record. |
| Proposed: `maintainer-run` | 9 | **Added** `maintainer-run`. It merges `maintainer-run`, the ranking-keeping half of `maintainer-run-no-submissions`, and the maintainer-selected routes in arc-agi-3-007, epoch-capabilities-index-007 and forecastbench-005 (15+ benchmarks). The field is multi-valued, so it is tagged beside a benchmark's other routes (webarena, bench, vbench-2-0, rexrank). `not_to_be_confused_with` links it to `maintainer-verified`, `sandboxed-rerun`, `held-out-server` and `literature-only`. |
| source-silent | 6 | No action: the sources were silent, not the vocabulary |
| Proposed: `literature-only` | 3 | **Added** `literature-only`. It merges `literature-only`, `no-results-channel`, `no-submission-channel` and the paper-only half of `maintainer-run-no-submissions`. The tests say a third party's re-running board is not the benchmark's own process (legalbench). `not_to_be_confused_with` on both sides with `self-reported` and `maintainer-run`. |
| Proposed: `open-source-gated` | 3 | **Added** `open-source-gated`. It merges `open-release-gated` (navsim-v2-009) and arc-agi-3-007's first gap, covering five benchmarks (agentdojo, arc-agi-2, arc-agi-3, osworld-2-0, navsim-v2). `not_to_be_confused_with` on both sides with `publication-gated`. |
| Proposed: `maintainer-scored-predictions` | 2 | **Added** `maintainer-scored-predictions`, which merges luna16-003's missing term. It covers three benchmarks where submitted predictions are scored by the maintainer against public labels: video-mme-v2, weatherbench-2, luna16. `not_to_be_confused_with` on both sides with `held-out-server` and `maintainer-verified`. |
| Proposed: `organiser-evaluated-submissions` | 2 | **Clarified**, no term. `held-out-server`'s tests now count organiser scoring after a deadline, and references or human judgements that do not exist at submission. The "server" is incidental; the unseen labels are what the term records. dcase-2026 and wmt25 are its examples. |
| missing-term | 2 | **Added**: arc-agi-3-007 is covered by `open-source-gated` plus `maintainer-run`, and luna16-003 by `maintainer-scored-predictions`. |
| undefined-boundary between `maintainer-verified`, `sandboxed-rerun`, `self-reported` | 2 | **Clarified**. A stated review of the result, trajectories or code makes it `maintainer-verified`, and a re-run that is possible or optional is not `sandboxed-rerun`. Tie-break in both terms' tests; cy-bench and proteingym are the examples. `not_to_be_confused_with` on all three pairs. |
| Proposed: `affiliation-gated` | 1 | **Rejected**: one benchmark (swe-bench-verified). Record the eligibility rule in a note beside `publication-gated`. |
| Proposed: `maintainer-harvested` | 1 | **Rejected**: one benchmark (epoch-capabilities-index). Its own-evaluation route is `maintainer-run`; record the harvested model-card route in a note. |
| Proposed: `no-results-channel` | 1 | **Added** as part of `literature-only`. |
| Proposed: `no-submission-channel` | 1 | **Added** as part of `literature-only`. The activity-side term of the same name is below. |
| Proposed: `open-release-gated` | 1 | **Added** as part of `open-source-gated`. |
| Proposed: `prediction-lock-before-resolution` | 1 | **Rejected**: one benchmark, and expressible with existing terms. Under the clarified `held-out-server` test, outcomes that do not exist at submission count as unseen labels (forecastbench example). The baseline board is `maintainer-run`. |
| Proposed: `remote-policy-endpoint` | 1 | **Deferred**: needs more corpus evidence. Only one record exists; it names RoboArena and RoboTwin as the same pattern, but neither logged it. |
| collision between `containerized-algorithm-submission`, `sandboxed-rerun` | 1 | **Clarified**: tie-break in `sandboxed-rerun`'s exclusion test. A container image run against data the participant never sees is `containerized-algorithm-submission`; any other code the maintainer executes, such as a plugin, script or agent, is `sandboxed-rerun` (brain-score example). With one record, no `not_to_be_confused_with` was added. |

#### `lifecycle` (44)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| source-silent | 23 | No action: the sources were silent, not the vocabulary |
| collision between `active`, `superseded` | 6 | **Clarified** by the entry-as-catalogued precedence rule, in `active`'s and `superseded`'s tests, with `not_to_be_confused_with` on both. An edition or version that a successor has replaced is `superseded` even while the family is active. bench-006 chose the family and reads `superseded` under the rule. |
| collision between `active`, `dormant` | 3 | **Clarified**: the instrument, not its originators, decides. `dormant`'s exclusion test says originator inactivity is `maintenance_status` evidence, and a community standard still in use is `active` or `mature`. Where the sources show only that inactivity, the field is null and the gap is logged. `not_to_be_confused_with` on both. The uspto-50k and atari-100k near misses are on `dormant`. |
| collision between `active`, `under-revision` | 2 | **Clarified**: `under-revision` takes precedence while a correction of the entry's own content is in progress (mle-bench). New variants beside a finalised set do not count (humanity-s-last-exam). `not_to_be_confused_with` on both. |
| Proposed: `completed-edition` | 1 | **Rejected**: expressible as `superseded` under the edition precedence rule, because a later edition replaces a completed one (casp16 example on `superseded` and `mature`). |
| Proposed: `paused` | 1 | **Deferred**: one benchmark. ADR-0019 and 02 §8 put a pause of intake in `activity`, and `closed`'s tests now cover a pause, with the stated plans in a note. A lifecycle state for "frozen pending a successor" needs a second case. HAL's lifecycle value remains open (see below). |
| collision between `active`, `deprecated`, `dormant` | 1 | **Clarified** (tanks-and-temples). An end-of-maintenance notice is not advice against use (`deprecated` exclusion) and does not by itself make the benchmark dormant (`dormant` exclusion). `not_to_be_confused_with` between `deprecated` and `dormant`. |
| collision between `active`, `dormant`, `mature` | 1 | **Clarified** (audioset): the same instrument-not-originator rule, with `not_to_be_confused_with` among all three terms. |
| collision between `deprecated`, `mature`, `superseded` | 1 | **Clarified** (coco). Replacing the competition does not supersede the instrument (`superseded` exclusion, coco near miss), and a "deprecated" label on a replaced server is not deprecation (`deprecated` exclusion, coco near miss). |
| undefined-boundary | 1 | **Clarified** by ADR-0019's `mature` sentence (healthbench-007). A maintainer that stops adding results while it keeps hosting the benchmark is `mature` if the benchmark is in use, and `activity` is `closed`. |
| undefined-boundary between `active`, `dormant` | 1 | **Clarified** (minif2f). A family entry is `active` while any member produces results (`active` inclusion test). The archived original's own standing belongs on its child record. |
| undefined-boundary between `active`, `dormant`, `mature` | 1 | **Clarified** (open-catalyst) by the same family rule; open-catalyst-oc20-oc22 is a positive example on `active`. |
| undefined-boundary between `active`, `proposed` | 1 | **Clarified** (cy-bench) in `active`'s exclusion test. If the only results are the maintainers' own release baselines and the maintainers say benchmarking has not begun, the value is `proposed`. With one record, no `not_to_be_confused_with` was added. |
| undefined-boundary between `active`, `superseded`, `under-revision` | 1 | **Clarified** (weatherbench-2). A code-base successor whose data and scores carry over is neither `superseded` nor `under-revision`; both exclusion tests say so, and weatherbench-2 is a near miss on both. |

#### `governance.maintainer_type` (33)

Nearly every group here exists because the field is single-valued and the benchmark has several
parties. Per brief rule 4, these are settled by the holder precedence rule stated at the top, not by a
new term. Pairs that overlap by definition got `not_to_be_confused_with` on both sides:
`academic-lab`/`individual`, `academic-lab`/`community-collective`, `academic-lab`/`conference-workshop`,
`community-collective`/`consortium`, `consortium`/`nonprofit` and `industry-lab`/`nonprofit`.

| Group (as in the list) | Records | Disposition |
|---|---|---|
| collision between `academic-lab`, `community-collective` | 4 | **Clarified**: holder rule plus a tie-break. `community-collective` needs a shared account with no single institution as holder, and outside contributions do not make a lab-held benchmark a collective. `not_to_be_confused_with` on both; cy-bench near miss, critpt positive. |
| source-silent | 4 | No action: the sources were silent, not the vocabulary |
| collision between `academic-lab`, `community-collective`, `government-agency` | 2 | **Clarified**: holder rule. `government-agency` needs a source stating the holder is a public body (vbench-2-0 near miss); critpt is a positive example on `community-collective`. |
| collision between `academic-lab`, `conference-workshop`, `consortium` | 2 | **Clarified**. `conference-workshop` overrides for a recurring challenge with a re-forming committee, and `consortium` needs a stated legal form. `not_to_be_confused_with` on `academic-lab`/`conference-workshop`. |
| collision between `academic-lab`, `individual` | 2 | **Clarified**: a personal-account holder is `individual` whatever the authors' university (gpqa-diamond and medagentbench-v2). `not_to_be_confused_with` on both. |
| collision between `academic-lab`, `individual`, `industry-lab` | 2 | **Clarified**: holder rule. The holder decides, not the co-authors' employers. bend's personal-account host makes it `individual`. legalbench is `academic-lab`: Hazy Research holds it, and a datasheet contact is not a holder (near miss on `individual`). |
| collision between `community-collective`, `consortium`, `nonprofit` | 2 | **Clarified**. The word "consortium" without a legal form means `community-collective`, and a nonprofit fiscal host does not make a nonprofit (open-problems and wmdp examples). `not_to_be_confused_with` on `consortium`/`community-collective` and `consortium`/`nonprofit`. |
| collision between `industry-lab`, `nonprofit` | 2 | **Clarified**. A public benefit corporation is a company, and the type is the holder's current form (apollo). Where a company and a nonprofit share a benchmark, the holder of the dataset and repository decides (humanity-s-last-exam). `not_to_be_confused_with` on both. |
| Proposed: `intergovernmental-organisation` | 1 | **Rejected**: one benchmark (simulacrabench). Under the holder rule the UN agencies are data partners, and the maintainer is the Stanford lab that hosts the competition (near miss on `government-agency`). |
| collision between `academic-lab`, `community-collective`, `consortium`, `industry-lab` | 1 | **Clarified** (coco): holder rule; `consortium` needs a stated legal form. |
| collision between `academic-lab`, `community-collective`, `nonprofit` | 1 | **Clarified** (terminal-bench): holder rule; `nonprofit` needs a stated nonprofit holder. |
| collision between `academic-lab`, `conference-workshop` | 1 | **Clarified** (ntire): the `conference-workshop` override, with ntire as a near miss on `academic-lab`. |
| collision between `academic-lab`, `government-agency`, `individual` | 1 | **Clarified** (matbench-discovery): a personal-account host is `individual` (positive example). |
| collision between `academic-lab`, `government-agency`, `nonprofit` | 1 | **Clarified** (fair-universe): holder rule; positive example on `government-agency`. |
| collision between `academic-lab`, `industry-lab` | 1 | **Clarified** (open-catalyst): holder rule; positive example on `industry-lab`. |
| collision between `community-collective`, `conference-workshop` | 1 | **Clarified** (dcase): the `conference-workshop` override, even with a standing steering group (positive example). |
| collision between `community-collective`, `consortium`, `industry-lab` | 1 | **Clarified** (geo-bench-2): `consortium` needs a stated legal form; holder rule. |
| collision between `consortium`, `nonprofit` | 1 | **Clarified** (cache-challenges): a member-governed body with a legal form is `consortium` even when that form is a nonprofit. |
| collision between `consortium`, `nonprofit`, `standards-body` | 1 | **Clarified** (ailuminate-v1-1): positive on `consortium`, near miss on `nonprofit`. `standards-body` is untouched, because its definition already needs a standards or certification organisation and the record excluded it on the sources. |
| collision between `government-agency`, `industry-lab` | 1 | **Clarified** (agentharm): holder rule; positive on `government-agency`, near miss on `industry-lab`. |
| missing-term | 1 | **Clarified** (atari-100k). An unmaintained benchmark takes its originator's type and the decay goes to `maintenance_status`. That is 02 §9's rule, now in the tests of `academic-lab` and `industry-lab`. |

#### `activity` (31)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| missing-term | 12 | **Added**. The eleven no-channel records (agentharm, apollo, audioset, bend, financebench, gdpval, healthbench, medagentbench-v2, posebusters, runs-n-poses, uspto-50k) take `no-submission-channel`; brats-2026-cluster-008 takes `results-pending`. One exception: under ADR-0019, a formal stop to adding results is `closed`, so healthbench (simple-evals stopped in July 2025) reads `closed`. |
| Proposed: `no-submission-channel` | 6 | **Added** `no-submission-channel`. The tests say a private scoring service or an on-request evaluation is not a channel (gdpval, financebench). `not_to_be_confused_with` on both sides with `closed`, `unknown` and `leaderboard-live-no-round`. |
| Proposed: `maintainer-run-ongoing` | 3 | **Added** as part of `no-submission-channel` (merged). Nobody else can enter. That the maintainer is still producing results is carried by lifecycle `active` and submission_process `maintainer-run`, so a separate activity term would duplicate them (frontiermath positive example). |
| Proposed: `submissions-paused` | 2 | **Rejected**: two benchmarks, and expressible as `closed` plus a note. `closed`'s tests now say it records that no route is open now, whether the maintainer calls it permanent or a pause, with the stated plans in a note (mle-bench and hal examples). |
| Proposed: `assessment-in-progress` | 1 | **Added** as `results-pending`. It merges casp17-006, brats-2026-cluster-008 and cache-challenges-004's reading, covering three benchmarks. `not_to_be_confused_with` on both sides with `between-rounds` and `closed`. |
| collision between `accepting-submissions`, `between-rounds`, `leaderboard-live-no-round` | 1 | **Clarified** (carla). For a benchmark that runs rounds and has none open, `leaderboard-live-no-round` takes precedence (its inclusion test; carla is a positive example). |
| collision between `accepting-submissions`, `between-rounds`, `round-scheduled` | 1 | **Clarified** (a2rl). Registration is not a submission route, so the value is `between-rounds` unless a date is announced (`round-scheduled`). a2rl is a near miss on `accepting-submissions` and a positive on `between-rounds`. |
| collision between `accepting-submissions`, `closed` | 1 | **Clarified** (srbench) by the layer rule in `closed`'s and `accepting-submissions`' tests: an edition entry frozen inside an open family is `closed`. |
| collision between `accepting-submissions`, `leaderboard-live-no-round` | 1 | **Clarified** (robotwin): the same precedence, with `not_to_be_confused_with` on both, since carla-008 is the pair's second record. |
| escape-hatch-used | 1 | **Clarified** (kaggle-game-arena). A live board that only the maintainer updates is `no-submission-channel`; `leaderboard-live-no-round`'s exclusion test says so, with kaggle-game-arena as the near miss. |
| source-silent | 1 | No action: the sources were silent, not the vocabulary |
| undefined-boundary between `accepting-submissions`, `between-rounds` | 1 | **Clarified** (cache-challenges). Numbered challenge rounds that are closed but not yet reported are `results-pending`. Whether DREAM x CACHE is an edition of the family is a 02 §11 rule 5 question that the vocabulary cannot settle (listed below). |

#### `governance.independence_flags` (31)

| Group (as in the list) | Records | Disposition |
|---|---|---|
| source-silent | 13 | No action: the sources were silent, not the vocabulary. `no-known-conflict`'s exclusion test now says to leave the field empty when the search could not be completed. |
| Proposed: `judge-model-from-evaluated-party` | 3 | **Added** `grader-from-evaluated-party`. It merges `judge-model-from-evaluated-party`, `judge-model-is-entrant`, `raters-are-entrants` and `evaluated-party-in-scoring-loop`, covering eight benchmarks: gdpval, healthbench, paperbench, helm-capabilities, medhelm, rexrank, roboarena, wmt25. Its tests say it is tagged beside `maintainer-competes-on-own-benchmark` when both hold. |
| Proposed: `judge-model-is-entrant` | 3 | **Added** as part of `grader-from-evaluated-party`. A judge that is an entrant, or an earlier snapshot of one, is the same conflict. |
| undefined-boundary between `funded-by-evaluated-party`, `no-known-conflict` | 3 | **Clarified**, with tests and `not_to_be_confused_with` on both. In-kind support from an evaluated party counts as funding: API access or credits, and compute. So does funding the publication that defines the method. A maintainer's statement of independence goes in a note. Access to an unreleased model in order to evaluate it is not by itself funding. This confirms all three records' assignments and settles helm-capabilities-006's second boundary. |
| Proposed: `evaluated-party-in-design` | 1 | **Deferred**: needs more corpus evidence. Merged with `items-curated-by-evaluated-party`, it covers two benchmarks (osworld-2-0, swe-bench-verified), one short of the threshold. |
| Proposed: `evaluated-party-in-scoring-loop` | 1 | **Added** as part of `grader-from-evaluated-party`: Cohere's judge and Cohere's raters. |
| Proposed: `evaluated-party-veto` | 1 | **Rejected**: one benchmark (ailuminate-v1-1). Record the opt-out list in a note. |
| Proposed: `items-curated-by-evaluated-party` | 1 | **Deferred**: merged with `evaluated-party-in-design` above. |
| Proposed: `raters-are-entrants` | 1 | **Added** as part of `grader-from-evaluated-party` (roboarena positive example). |
| Proposed: `sponsor-shapes-scoring` | 1 | **Rejected**: one benchmark, and no source says the sponsor is evaluated. The money is `prize-sponsored-by-industry`; record the metric collaboration in a note. |
| Proposed: `test-data-supplier-sells-to-entrants` | 1 | **Rejected**: one benchmark (open-asr-leaderboard). |
| undefined-boundary between `commercial-leaderboard-placement`, `evaluator-sells-evaluations` | 1 | **Deferred**: one record, and it turns on whether pre-release testing is paid, which is a source question. The existing definition already needs a commercial arrangement. |
| undefined-boundary between `evaluator-sells-evaluations`, `no-known-conflict` | 1 | **Deferred**: one record (apollo). Whether commissioned pre-deployment testing is selling evaluations turns on payment the sources do not state. The revised `no-known-conflict` exclusion keeps the field empty meanwhile, and `funded-by-evaluated-party` now says pre-release access alone is not funding. |

#### ADR parts applied

- **ADR-0019, `dormant`.** The ADR's added sentence is joined to the definition by a semicolon so the
  definition stays one sentence: "... should not be read as current; a formally ended competition series
  is not dormant, because its ending is recorded in `activity` and `lifecycle` keeps the instrument's
  standing." The meaning is unchanged. The tests repeat it, with voxsrc-retired-2023 as the near miss.
- **ADR-0019, `mature`.** "This includes ..." becomes a trailing clause: "... no expectation of structural
  change, including an instrument whose maintainer has ended its competition or frozen its leaderboard
  while it remains available and in use." The meaning is unchanged. `mature`'s inclusion test says to
  record the ending in `activity` (`closed`, or `leaderboard-live-no-round` for a permanent phase). The
  examples are helm-capabilities and medhelm (positive) and holistic-agent-leaderboard-hal (near miss:
  the maintainer expects structural change).
- **ADR-0019 consequences carried into activity.** `closed` covers maintenance mode and a formally
  concluded series. `no-submission-channel` defers to `closed` for a formal stop, so HELM stays `mature` +
  `closed` as the ADR intends. voxsrc-retired-2023 is a positive example on `leaderboard-live-no-round`.
- ADRs 0014 to 0018 have no parts in these two files.

#### Examples fixed

None. Every `examples:` list in both files was empty before this revision, so no existing verdict could
contradict its tests. All examples here are new, and every ref is a stress-corpus id; none is one of the
three ADR-0017 out-of-scope entries.

#### Legality matrix (02 §11) and validators

Nothing added contradicts the matrix. `schema/validators.py` needs no change. The two new activity terms
appear in no blocking row, and `dormant`'s and `deprecated`'s tests repeat the existing blocking
combinations with `accepting-submissions`. Suggested additions to 02 for the lead, since I did not edit
02:

- A row `active` | `no-submission-channel` | any | Yes | "Download-and-run, or maintainer-run with no
  outside entry (BEND, FrontierMath)", so the modal academic state is visibly legal.
- A row `active` | `results-pending` | any | Yes | "A round being scored (CASP17, BraTS)".
- Worth deciding: should `dormant`, `deprecated` or `retracted` + `results-pending` block like
  `accepting-submissions`? A round being scored implies a live instrument. If so, validators and 02 need
  a row.
- 02 §8 and §9 counts need regenerating (activity 6 to 8, submission_process 10 to 14,
  independence_flags 8 to 9). These are the expected 9b count failures.

#### Checks

- `uv run bench validate taxonomy/ --tier all`: 0 blocking, 0 warnings.
- `scripts/taxonomy_stats.py --check`: all pass except 9b count rows. Mine are activity, submission_process
  and independence_flags; the others belong to other groups.

#### Not resolved

1. **HAL's lifecycle value.** A leaderboard frozen by its maintainer pending a successor is not `mature`
   (ADR-0019) and not `active` if no results are produced. It is not yet `dormant` or `deprecated`.
   `paused` is deferred as a single case, so the field likely stays null at T08.
2. **Evidence for "still in use".** The new `active`/`dormant` tests make the instrument's use decisive.
   Whether independent papers count as sources for lifecycle is a classification-evidence ruling, not a
   vocabulary one; the P1-S1-T03 reviewer ruling excludes third-party aggregations. If they count,
   uspto-50k, atari-100k, harmbench and audioset read `active`; if not, the field is null. Either way
   they are no longer `dormant`.
3. **cache-challenges family membership.** Whether a co-branded challenge run by another organiser (DREAM
   x CACHE) is an edition of the family is a 02 §11 rule 5 question.
4. **`dormant` and `deprecated` have only near-miss examples.** No stress-corpus entry qualifies for
   either under the revised tests.
5. **One-way `not_to_be_confused_with`.** `grader-from-evaluated-party` has one pointing to
   `maintainer-competes-on-own-benchmark`, which is still definition-only. No failure record is a
   collision between the two.
6. **Values expected to move at T08 re-run:**
   - bench lifecycle: `active` to `superseded`.
   - gpqa-diamond, bend, matbench-discovery maintainer_type: `academic-lab` to `individual`.
   - cache-challenges maintainer_type: may move to `consortium`.
   - kaggle-game-arena and the-well activity: to `no-submission-channel`.
   - healthbench activity: `closed`.
   - coco lifecycle: off `superseded`.
   - casp16 lifecycle: `superseded`.
   - navsim-v2: loses `publication-gated` and gains `open-source-gated` for its 2024 listing rule.
   - The dormant community standards: see item 2.

### Stage 4 disposition: data-execution (P1-S1-T07)

Files: `taxonomy/data-properties.yaml`, `taxonomy/ceiling-anchors.yaml`, `taxonomy/execution.yaml`.
`taxonomy/maintenance.yaml` is unchanged, because no record needed it.

Summary: 2 terms added, both `data.data_provenance`: `curated-public-database` and
`inherited-from-constituents`. 44 terms clarified with tests, examples and
`not_to_be_confused_with`. No term was renamed, removed or merged. Term counts change only for
`data.data_provenance`, which goes from 11 to 13.

#### Precedence rules stated (rule 4, layered single-valued fields)

- **access.** The field describes the evaluation data behind the headline score, as an
  independent party can obtain it.
  - Withholding decides before a gate on released data: first `private-test-server` (the items
    never leave the maintainer), then `train-open-test-held-out` (inputs released, labels
    withheld).
  - A gate is tagged only when nothing is withheld: `credentialed-dua`, then
    `gated-registration`.
  - A headline that mixes open and held sets takes the most restrictive of them.
  - When there are several official copies, the least restrictive decides. A printed password or
    a no-reveal request is not a gate.
  - A blind round is judged once it has closed. For a family, the current edition decides.
  - Where it is written: tests of `fully-open`, `train-open-test-held-out`, `gated-registration`
    and `private-test-server`.
- **refresh.** The field describes the family (02 S11 rule 5) and the set behind the headline
  score. "Content" means the items, the task list, the scoring function and, for a rating, the
  pool.
  - A pin is a version label or a dated maintainer announcement.
  - `resolves-over-time` takes precedence over the edition, generation and rolling cadences.
  - `continuously-reexecuted` takes precedence over task version labels.
  - Where it is written: all seven refresh terms.
- **contamination_risk.** The field describes the content the benchmark scores and publishes,
  after the maintainer's own mitigation.
  - A route that was evidenced and then closed does not raise the value. It goes in the notes.
  - One evidenced split that is still scored makes the benchmark `high`, following 02 S11's
    "known-contaminated in one split".
  - A route evidenced for only one entrant belongs on that entrant's claims.
  - Where it is written: `low`, `medium`, `high`.
- **ceiling_anchor_type.** The field records the anchor of the headline metric that the
  benchmark's own sources read scores against.
  - The anchor still counts after systems exceed it, and headroom is then unclamped (12 S3.1).
  - Secondary metrics and other tracks go to `ceiling_by_category`.
  - A scale that cannot have an anchor is `none-known`: a pool-relative rating or
    normalisation, an unbounded metric, or a chance-level target. The reason for the absence is
    carried by `Metric` (`unbounded`, `requires_pool`, `optimum`) and by
    `Baseline.value_absent_reason`.
- **compute_tier.** The field describes one official score for one new system, and training that
  system is not part of the run.
  - A requirement the protocol imposes on every run outranks the cost of serving the system
    under test.
  - When only the serving cost is left, `api-credits-only` applies if the headline leaderboard
    accepts API-served systems.
  - `simulator-required` takes precedence over an accelerator count.
  - `provided-allocation` takes precedence over the tier and over a simulator, but only when the
    official run happens on organiser compute.
  - `participant-funded-procurement` takes precedence over `wet-lab`, as 02 S12.4 records.
  - A role split goes to `compute_tier_by_role`.
  - The records point to this rule most often. Every worked example in 02 S12 is consistent
    with it, and so is clause 2 of `scripts/runnable_gate.py`.
- **reproducibility_tier.** The field describes the headline official score, reproduced from
  scratch.
  - The most restrictive tier that any part of it needs decides, in this order:
    `not-independently-reproducible`, `requires-physical-experiment`,
    `requires-specialized-hardware`, `requires-human-raters`, `automatable-with-simulator`,
    `fully-automatable`.
  - A calibrated public sibling set does not count as reproduction, and neither does re-fitting
    a score from released outputs.
  - Conditions that cannot be repeated take the tier a fresh run needs, plus `live-world-state`.

#### `data.access`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| collision between `fully-open`, `private-test-server` | 3 | **Clarified**: the mixed-headline rule (the most restrictive set decides). `private-test-server` also covers a maintainer-run evaluation with no submission server. `not_to_be_confused_with` on both terms. open-asr-leaderboard is the near miss on `fully-open`, and brain-score is an example on `private-test-server`. |
| collision between `gated-registration`, `private-test-server`, `train-open-test-held-out` | 3 | **Clarified**: withholding precedes a gate, and items that never leave the maintainer are `private-test-server` while withheld labels alone are `train-open-test-held-out`. `not_to_be_confused_with` on all three terms. |
| Proposed: `embargoed-until-release` | 2 | **Rejected**: already expressible. The embargo is the round structure, which `data.refresh` (`periodic-recompetition`, `resolves-over-time`) and `evaluation_method` record. Access describes the data once the round has closed, which is how 02 S12.1 (CASP), S12.4 (CACHE) and S12.8 (ForecastBench) read it, and a new term would contradict all three. The rule is in `fully-open`'s inclusion test. cafa-003 raises the same question, and the same rule answers it. |
| collision between `fully-open`, `gated-registration` | 2 | **Clarified**: the least restrictive official copy decides, and a printed password or no-reveal request is not a gate. The current edition decides for a family. `not_to_be_confused_with` on both terms. gpqa-diamond is the near miss on `gated-registration`. |
| collision between `gated-registration`, `train-open-test-held-out` | 2 | **Clarified**: withheld evaluation labels take precedence over a gate on the released data, and the gate goes in the notes. `not_to_be_confused_with` on both terms, with docvqa-robust-reading-competition and omol25 as examples. |
| collision between `private-test-server`, `train-open-test-held-out` | 2 | **Clarified**: the discriminant is whether the evaluation inputs are released. `not_to_be_confused_with` on both terms, and carla-leaderboard-2-0 is the example on each side. |
| escape-hatch-used | 2 | **Clarified** `generated-on-demand`: it applies only when a program or model produces the items. Human-improvised items take the access state of their record. lmarena is the near miss. |
| Proposed: `anti-scraping-gate` | 1 | **Rejected**: one benchmark, and already expressible. A printed password is `fully-open` (the rule is in `fully-open` and `gated-registration`). |
| Proposed: `event-entry-only` | 1 | **Rejected**: one benchmark, and already expressible. 02 S7 names A2RL under `invitation-only`, and the tests of `invitation-only` and `gated-registration` now cover a competition with no distributable data. |
| Proposed: `pointer-to-third-party-media` | 1 | **Rejected**: one benchmark. It is expressible as `fully-open` with a note, and vanishing media is a reproducibility matter, not an access state. |
| Proposed: `withheld-shared-on-request` | 1 | **Rejected**: one benchmark, and already expressible. `private-test-server` was redefined to cover a maintainer-held set that the maintainer evaluates itself or on request, and case-by-case private sharing does not change that. |
| collision between `credentialed-dua`, `fully-open`, `gated-registration`, `proprietary-closed` | 1 | **Clarified**: the mixed-headline rule. MedHELM's private internal datasets are maintainer-run, so the result is `private-test-server`. |
| collision between `credentialed-dua`, `fully-open`, `private-test-server`, `train-open-test-held-out` | 1 | **Clarified**: the mixed-headline rule gives `private-test-server`, because ReXGradient is maintainer-held. |
| collision between `credentialed-dua`, `gated-registration`, `train-open-test-held-out` | 1 | **Clarified**: withholding precedes a gate, so the result is `train-open-test-held-out`. scannet is the near miss on `gated-registration`. |
| collision between `fully-open`, `private-test-server`, `proprietary-closed` | 1 | **Clarified**: the redefined `private-test-server` covers a maintainer-run set with no server. frontiermath-tiers-erd-s is an example of it, and `not_to_be_confused_with` was added between `fully-open` and `proprietary-closed`. |
| collision between `fully-open`, `private-test-server`, `restricted-dual-use` | 1 | **Clarified**: the headline rule, plus a tie-break in `private-test-server` that sends withholding for misuse risk to `restricted-dual-use`. P1-S1-T08 should re-read this record. 02 S12.12 records `restricted-dual-use` for AgentHarm, but the record found only contamination given as the reason. |
| collision between `fully-open`, `private-test-server`, `train-open-test-held-out` | 1 | **Clarified**: the headline rule, and a calibrated public set does not make the data open. |
| collision between `fully-open`, `proprietary-closed` | 1 | **Clarified**: a public sample is `fully-open` only when the headline is computed on it. gdpval is an example, and `not_to_be_confused_with` was added. |
| collision between `fully-open`, `train-open-test-held-out` | 1 | **Clarified**: the headline rule. The corpus entry's leaderboard is navhard_two_stage. |

#### `data.refresh`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| source-silent | 13 | No action: the sources were silent, not the vocabulary. |
| undefined-boundary | 8 | **Clarified**, one resolution per record:<br>- brats-2026-cluster, lifeclef-2026 and ntire: the family is `periodic-recompetition` even when some tasks reuse a set. 02 S7 names all three, and ntire and brats-2026-cluster are examples.<br>- a2rl-drone-championship: each edition of a physical competition has new trials by construction.<br>- carla-leaderboard-2-0: "content" includes scoring, so a labelled scoring change is `versioned-releases`. It is an example.<br>- libero: an unused generator leaves the content `static`. It is an example.<br>- medagentbench-v2: a task set derived by someone other than the maintainer is a separate `variant_of` entry.<br>- docvqa-robust-reading-competition: decided by the family and headline rule, and P1-S1-T08 re-reads it. |
| collision between `rolling-live`, `versioned-releases` | 4 | **Clarified**: the pin test. If every change is carried by a label or a dated announcement, the value is `versioned-releases`; otherwise it is `rolling-live`. A frozen named set beside a rolling fork is a separate entry. `not_to_be_confused_with` on both terms. The examples are kaggle-game-arena, open-asr-leaderboard and humanity-s-last-exam (near miss). |
| undefined-boundary between `static`, `versioned-releases` | 2 | **Clarified**: a dated, announced revision counts as a pin, so the value is `versioned-releases`. `not_to_be_confused_with` on both terms. wmdp is the near miss on `static` and an example on `versioned-releases`. |
| Proposed: `cutoff-relative` | 1 | **Rejected**: one benchmark. It also belongs elsewhere: the evaluated subset depends on the entrant's training cutoff, which is a claim-level condition. The contamination tests now treat a cutoff filter as a closed route, with runs-n-poses as the near miss on `high`. |
| collision between `continuously-generated`, `resolves-over-time`, `rolling-live` | 1 | **Clarified**: `resolves-over-time` takes precedence, and the cadences go in the notes. forecastbench is an example of it and the near miss on `continuously-generated`. |
| collision between `continuously-reexecuted`, `versioned-releases` | 1 | **Clarified**: `continuously-reexecuted` was redefined. The clause "there is no frozen version" is gone, and the term takes precedence over task labels. 02 S7 names Open Problems as its case. `not_to_be_confused_with` added. |
| collision between `periodic-recompetition`, `resolves-over-time` | 1 | **Clarified**: `resolves-over-time` takes precedence (02 S7 names CAFA). `not_to_be_confused_with` on both terms. |
| collision between `periodic-recompetition`, `static` | 1 | **Clarified**: an edition takes the family's value. casp16-na-rna-puzzles-joint-assessment is the near miss on `static` and an example on `periodic-recompetition`. `not_to_be_confused_with` added. |
| collision between `periodic-recompetition`, `static`, `versioned-releases` | 1 | **Clarified**: the set behind the headline decides. Challenges that sit beside a labelled dataset give `versioned-releases`. |
| collision between `periodic-recompetition`, `versioned-releases` | 1 | **Clarified**: the same rule. navsim-v2 is an example of `versioned-releases` and the near miss on `periodic-recompetition` is coco. `not_to_be_confused_with` added. |
| collision between `rolling-live`, `static`, `versioned-releases` | 1 | **Clarified**: changes made between labels give `rolling-live`, as 02 S12.6 records. matbench-discovery is an example. |
| missing-term | 1 | **Clarified**: "content" now includes the scoring function, so an unlabelled change to the metric battery is `rolling-live`. No term was added. |
| undefined-boundary between `continuously-generated`, `static` | 1 | **Clarified**: items resampled from a fixed pool leave the content `static`. fair-universe-higgsml-uncertainty-challenge is the near miss, and `not_to_be_confused_with` is on both terms. |

#### `data.data_provenance`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `curated-public-database` | 4 | **Added** `curated-public-database`. It merges `curated-database-derived` (bend-005), which makes five benchmarks: cy-bench, open-problems-in-single-cell-analysis, proteingym, uspto-50k and bend. |
| Proposed: `aggregated-existing-datasets` | 3 | **Added** `inherited-from-constituents`. It merges `aggregated-existing-datasets` and `inherited-from-constituent-benchmarks`, which makes six benchmarks. |
| Proposed: `inherited-from-constituent-benchmarks` | 3 | **Added** `inherited-from-constituents` (see above). The two proposals name one gap, and whether the constituents are datasets or benchmarks does not change what a curator records. `curated-public-database` stays a separate term, because an archive of records is not an evaluation dataset. The two carry `not_to_be_confused_with` on each other. |
| collision between `crowd-authored`, `expert-authored` | 2 | **Clarified**: the authors' prior domain skill decides, not how they were recruited. Both definitions were revised: "recruited" and "at scale" were dropped. `not_to_be_confused_with` on both terms, with terminal-bench-2-0 and osworld-2-0 as examples on each side. The value changes for both benchmarks, and P1-S1-T08 re-reads them. |
| collision between `real-world-instrument`, `simulation-generated` | 2 | **Clarified**: an observation-constrained product (reanalysis, data assimilation, a measurement-fitted reconstruction) takes both terms, as 02 S12.3 records. `not_to_be_confused_with` on both terms. The examples are weatherbench-2 and chaosbench. |
| escape-hatch-used | 2 | **Clarified** for camelyon17: real records assembled by rule take the records' provenance, not `synthetic-procedural`. It is the near miss on that term. **Rejected** a new term for mmmu-pro (one benchmark): the MMMU items take `inherited-from-constituents`, and the photographs taken for the benchmark are `real-world-instrument`. |
| Proposed: `curated-database-derived` | 1 | **Added**, merged into `curated-public-database`. |
| Proposed: `human-subject-survey-microdata` | 1 | **Rejected**: one benchmark. `unreleasable-confidential` plus a note expresses it, and the obligations to respondents are a governance matter. |
| Proposed: `live-physical-event` | 1 | **Rejected**: already expressible. The recorded trials of a live physical evaluation are `real-world-instrument`, now in its inclusion test and consistent with 02 S12.2 (RoboArena). |
| Proposed: `participant-improvised` | 1 | **Rejected**: one benchmark, and already expressible. 02 S12.2 records RoboArena as `real-world-instrument`, and the new inclusion test covers it. |
| Proposed: `reference-reconstruction` | 1 | **Rejected**, merged into the reanalysis clarification: a physics code fitted to measurements takes `simulation-generated` and `real-world-instrument` together. fusion-equilibrium-challenge is an example. |
| collision between `experimental-measurement`, `real-world-instrument` | 1 | **Clarified**: an instrument that records a designed experiment's outcome gives `experimental-measurement`. brain-score is an example of it and the near miss on `real-world-instrument`. `not_to_be_confused_with` added. |
| source-silent | 1 | No action: the sources were silent, not the vocabulary. |
| undefined-boundary | 1 | **Clarified**: a game engine is `synthetic-procedural`, not `simulation-generated`, as 02 S12.5 records. kaggle-game-arena is an example of `synthetic-procedural` and the near miss on `simulation-generated`. |

#### `data.contamination_risk`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| collision between `high`, `low` | 4 | **Clarified**, one resolution per record:<br>- cafa and casp16-na-rna-puzzles-joint-assessment: a route closed by the maintainer gives `low`, with the notes. Both are examples.<br>- posebusters: a split that is still scored and evidenced gives `high`. It is an example and the near miss on `low`. P1-S1-T08 re-reads it.<br>- runs-n-poses: a cutoff filter gives `low`. It is the near miss on `high`.<br>`not_to_be_confused_with` on both terms. |
| Proposed: `not-applicable` | 1 | **Rejected**: already expressible. A live physical trial excludes a training route, so the value is `low`, stated structurally in the notes. That is how 02 S12.2 reads RoboArena. a2rl-drone-championship is an example on `low`. |
| collision between `high`, `medium` | 1 | **Clarified**: an evidenced route that was cleaned leaves the value at `medium` when other plausible routes remain. matbench-discovery is an example, and `not_to_be_confused_with` is on both terms. |
| undefined-boundary | 1 | **Clarified**: a protocol that evaluates on the data it releases for training is an evidenced route, so the value is `high`. luna16 is an example of `high` and the near miss on `medium`. |
| undefined-boundary between `high`, `medium` | 1 | **Clarified**: a route evidenced only for one entrant belongs on that entrant's claims. weatherbench-2 is an example on `medium`. |

#### `data.ceiling_anchor_type`

No ceiling term was added. `tests/schema/test_entities.py` asserts that `CEILING_ANCHOR` (in
`schema/baseline.py`) maps one-to-one onto the facet minus `none-known`. 02 S7 also forbids
"a headroom number computed from a vocabulary the schema cannot store". Any new anchor type
therefore needs an ADR that adds the `Baseline.kind` at the same time.

| Group (as in the list) | Records | Disposition |
|---|---|---|
| undefined-boundary | 4 | **Clarified**, one resolution per record:<br>- 2026-behavior-challenge: the headline metric decides, so the value is `theoretical-maximum` and the anchors of secondary metrics go to `ceiling_by_category`. It is an example.<br>- healthbench: an exceeded expert anchor stays the anchor, so the value is `expert-average`. It is an example.<br>- gdpval: an expert reference that marks parity on a win rate gives `expert-average`.<br>- navsim-v2: a human trajectory built into the scoring function is no anchor, so the value is `theoretical-maximum`. It is the near miss on `expert-average`. |
| Proposed: `not-applicable-relative-rating` | 3 | **Rejected** as a term, because it belongs in schema fields. **Clarified** `none-known` instead, which was redefined to cover scales that cannot have an anchor. The reason is carried by `Metric.requires_pool` and `unbounded` and by `Baseline.value_absent_reason: not-applicable`, and 02 S11 already nulls headroom for ratings. 02 S12.2 and S12.5 record `none-known` for exactly this case. lmarena is an example. |
| missing-term | 3 | **Clarified**, one resolution per record:<br>- arc-agi-3: the upper-median of completers is a central statistic, so the value is `crowd-average`, as 02 S12.7 records. It is an example.<br>- kaggle-game-arena: a relative rating gives `none-known`.<br>- atari-100k: the human normaliser is an anchor, so `none-known` is ruled out. Which population the humans came from is source-silent, and the metric (`episodic-return`) nulls headroom under 02 S11. |
| Proposed: `not-applicable-unbounded-metric` | 2 | **Rejected** and **Clarified** for the same reason as `not-applicable-relative-rating`: `Metric.unbounded` carries it. scannet is an example on `none-known`. |
| Proposed: `chance-floor-target` | 1 | **Rejected**: one benchmark, and it belongs in schema fields. A lower-is-better target equal to chance is a floor, carried by `Metric.optimum` and `chance_baseline`, and the tests of `none-known` now name the case. |
| Proposed: `crowd-panel-coverage` | 1 | **Rejected**: one benchmark. The headline statistic decides (`crowd-average`), and the pooled coverage is a further `Baseline` record. arc-agi-2 is an example on `crowd-average`. |
| Proposed: `estimated-anchor` | 1 | **Rejected**: one benchmark, and it belongs on the `Baseline` record (its value and notes), not on the anchor type. It is merged with `selection-conditioned-anchor` for that reason. |
| Proposed: `expert-aggregate-forecast` | 1 | **Rejected**: one benchmark. 02 S12.8 records `expert-best` for ForecastBench's superforecasters, and the rule that an exceeded anchor stays the anchor covers the parity finding. |
| Proposed: `positive-control` | 1 | **Deferred**: it needs more corpus evidence and an ADR that adds a matching `Baseline.kind`. Together with `specialist-method-reference` it is the one real gap (a designated reference method as anchor), found in two benchmarks. The tests of `operational-system` now exclude it, so the curator abstains with a failure record until then. |
| Proposed: `reference-pool-best` | 1 | **Clarified** `none-known`: a score normalised to the best of a pool is pool-relative, so it takes `none-known`. geo-bench-2 is an example. |
| Proposed: `reference-relative-grade` | 1 | **Clarified** `none-known`: a reference system recomputed from the entrants is pool-relative. `ordinal-grading` already nulls headroom (02 S11). |
| Proposed: `selection-conditioned-anchor` | 1 | **Rejected**: one benchmark, and it belongs on the `Baseline` record. The type is right (`expert-average`), and the value's selection skew is a note. gpqa-diamond is an example. |
| Proposed: `specialist-method-reference` | 1 | **Deferred** with `positive-control` (see above). bend is the near miss on `operational-system`, which excludes published research models. |
| collision between `crowd-average`, `expert-average` | 1 | **Clarified**: recruitment for the knowledge the tasks need gives `expert-average`. webarena is the near miss on `crowd-average`. `not_to_be_confused_with` on both terms. |
| collision between `expert-average`, `expert-best`, `theoretical-maximum` | 1 | **Clarified**: professionals scored under the same protocol and exceeded by systems are still `expert-average`. wmt25-general-mt-shared-task is an example. |
| collision between `expert-average`, `noise-ceiling` | 1 | **Clarified**: agreement between annotations of the reference gives `noise-ceiling`. brats-2026-cluster is an example of it and the near miss on `expert-average`. `not_to_be_confused_with` on both terms. |
| collision between `measured-ceiling`, `theoretical-maximum` | 1 | **Clarified**: an oracle-verified bound gives `measured-ceiling`, as 02 S12.11 reads SWE-bench Verified. terminal-bench-2-0 is an example of it and the near miss on `theoretical-maximum`. P1-S1-T08 re-reads it. `not_to_be_confused_with` on both terms. |
| collision between `noise-ceiling`, `none-known` | 1 | **Clarified**: the headline track decides, and the anchors of other tracks go to `ceiling_by_category`. This is in the tests of `none-known`. |
| collision between `operational-system`, `theoretical-maximum` | 1 | **Clarified**: an incumbent whose output is the ground truth gives `theoretical-maximum`, and an incumbent scored against independent truth gives `operational-system`. fusion-equilibrium-challenge is an example of the first and the near miss on the second. `not_to_be_confused_with` on both terms. |
| escape-hatch-used | 1 | **Clarified**: a normalisation to the best of the pool is pool-relative and takes `none-known`. melting-pot is the near miss on `measured-ceiling`. |
| undefined-boundary between `operational-system`, `theoretical-maximum` | 1 | **Clarified**: an incumbent that entrants beat stays the anchor, and headroom is unclamped. weatherbench-2 is an example. |

#### `execution.compute_tier`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| source-silent | 18 | No action: the sources were silent, not the vocabulary. |
| collision between `api-credits-only`, `multi-gpu-node`, `single-gpu` | 4 | **Clarified** by the precedence rule: an API-served system under test gives `api-credits-only`, and a GPU the protocol mandates (vbench-2-0's scorer) gives `single-gpu`. The rule is in the tests of all three terms, with `not_to_be_confused_with` on each pair. |
| collision between `api-credits-only`, `single-gpu` | 4 | **Clarified** by the same rule. mle-bench and paperbench take `single-gpu`, because their GPU is mandated, and both are examples. mmlu-pro and balrog take `api-credits-only`. P1-S1-T08 re-reads paperbench. |
| collision between `simulator-required`, `single-gpu` | 3 | **Clarified**: the simulator takes precedence over the accelerator, which goes in the notes. `not_to_be_confused_with` on both terms, with 2026-behavior-challenge, libero and melting-pot as examples. |
| Proposed: `storage-heavy` | 1 | **Rejected**: one benchmark. Data volume belongs in schema fields (`data.size`, `est_runtime_hours`), not in a compute tier. |
| Proposed: `volunteer-crowd` | 1 | **Rejected**: one benchmark. The arena's rater base is recorded by `submission_process: live-arena`, the `human-raters` blocker and the reproducibility tier. |
| collision between `api-credits-only`, `multi-gpu-node` | 1 | **Clarified** by the rule. legalbench-vals-legal-bench is the near miss on `multi-gpu-node`. |
| collision between `api-credits-only`, `multi-gpu-node`, `provided-allocation` | 1 | **Clarified**: optional organiser grading does not make the tier `provided-allocation`. swe-bench-verified is an example of `api-credits-only` and the near miss on `provided-allocation`. |
| collision between `api-credits-only`, `provided-allocation` | 1 | **Clarified**: the headline board decides. arc-agi-3 is an example (02 S12.7). |
| collision between `api-credits-only`, `single-gpu`, `trivial-cpu` | 1 | **Clarified** by the rule: the official Dafny harness calls Bedrock, so the value is `api-credits-only`. |
| collision between `cluster`, `multi-gpu-node`, `single-gpu` | 1 | **Clarified** by the rule: training is excluded, and a leaderboard that accepts only local systems takes the maintainer's reference run. P1-S1-T08 re-reads it. |
| collision between `multi-gpu-node`, `simulator-required`, `single-gpu` | 1 | **Clarified**: the simulator takes precedence and training is excluded. robotwin-2-0 is the near miss on `multi-gpu-node`. |
| collision between `participant-funded-procurement`, `wet-lab` | 1 | **Clarified**: entrant-paid materials take precedence over `wet-lab`, and the assay is a blocker, as 02 S12.4 records. cache-challenges is an example. `not_to_be_confused_with` added. |
| collision between `physical-hardware`, `single-gpu` | 1 | **Clarified**: the field takes the requirement of producing the result, and `compute_tier_by_role` holds each role, as 02 S12.2 records. roboarena is an example. |
| collision between `provided-allocation`, `simulator-required` | 1 | **Clarified**: `provided-allocation` takes precedence when the organisers run the official evaluation. carla-leaderboard-2-0 is an example of it and the near miss on `simulator-required`. `not_to_be_confused_with` on both terms. |
| undefined-boundary | 1 | **Clarified**: for an index, a run means obtaining its constituents' results for a new system. This is in `api-credits-only`'s inclusion test. |

#### `execution.reproducibility_tier`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| collision between `fully-automatable`, `not-independently-reproducible` | 1 | **Clarified**: the most restrictive part of the headline decides. frontiermath-tiers-erd-s is an example. `not_to_be_confused_with` on both terms. |
| collision between `fully-automatable`, `not-independently-reproducible`, `requires-human-raters` | 1 | **Clarified**: a rater base that only the maintainer has gives `not-independently-reproducible`, and re-fitting from released votes is not reproduction. `not_to_be_confused_with` between `requires-human-raters` and `not-independently-reproducible`. |
| collision between `fully-automatable`, `requires-human-raters` | 1 | **Clarified**: hand-grading even a minority of tasks gives `requires-human-raters`. legalbench-vals-legal-bench is an example of it and the near miss on `fully-automatable`. 02 S11 already blocks the current record. |
| collision between `not-independently-reproducible`, `requires-human-raters`, `requires-specialized-hardware` | 1 | **Clarified**: conditions that cannot be repeated take the tier a fresh run needs, plus `live-world-state`, and hardware comes before raters in the order. The result is `requires-specialized-hardware`, as 02 S12.2 records. roboarena is an example. |
| undefined-boundary | 1 | **Deferred** (forecastbench): 02 S12.8 records `fully-automatable` with `live-world-state`, and 02 S11 blocks that pair. 02 S12.5 (Kaggle Game Arena) has the same conflict. It needs an ADR on the S11 rule. The same ADR should decide `hosted-judge-dependency`. |
| undefined-boundary between `fully-automatable`, `not-independently-reproducible` | 1 | **Clarified**: a calibrated public sibling set does not count as reproduction. arc-agi-2 is an example of `not-independently-reproducible` and the near miss on `fully-automatable`. |

#### `execution.reproducibility_blockers`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| Proposed: `hosted-judge-dependency` | 8 | **Deferred**, although the gap recurs (eight benchmarks, and it merges `private-scorer`). 02 S11 makes `reproducibility_tier: fully-automatable` require that every blocker is `licence-restriction`, and `schema/validators.py` enforces this as blocking. Seven of the eight benchmarks are otherwise `fully-automatable`, as is 02 S12.12 (AgentHarm, GPT-4o judge), so adding the term would force them into a tier none of them fits. It needs an ADR that adds the blocker and extends S11's allow-list. That ADR should also cover `live-world-state`, because 02 S12.5 and S12.8 already pair it with `fully-automatable`. Until then the grader is pinned where S11 already requires it: `reference_conditions` names the grader model and version. |
| source-silent | 2 | No action: the sources were silent, not the vocabulary. |
| Proposed: `one-off-physical-event` | 1 | **Rejected**: one benchmark, and already expressible. **Clarified** `live-world-state`: its definition was broadened to "conditions that keep moving or occur only once". a2rl-drone-championship is an example. |
| Proposed: `private-scorer` | 1 | **Deferred**, merged into `hosted-judge-dependency` (a model inside the scoring loop that nobody else can run). |
| Proposed: `simulator-nondeterminism` | 1 | **Rejected**: one benchmark. It is expressible as `specific-simulator-build` plus a note, and run-to-run variance is a reporting condition. 2026-behavior-challenge is the near miss on `live-world-state`. |

#### `execution.harness_availability`

| Group (as in the list) | Records | Disposition |
|---|---|---|
| source-silent | 2 | No action: the sources were silent, not the vocabulary. |
| Proposed: `designated-third-party-harness` | 1 | **Rejected**: one benchmark, and already expressible. **Clarified** `official-harness`: its definition now covers a harness the maintainer designates by name and version. wmdp is an example, and P1-S1-T08 re-reads it. |
| Proposed: `hosted-scoring-service` | 1 | **Rejected**: one benchmark, and it belongs in a schema field. **Clarified** `none`: a hosted service is not code, and it is recorded in `execution.submission_channel`. gdpval is an example. |
| escape-hatch-used | 1 | **Clarified** `reference-implementation-only`: a human testing interface or a submission client counts as code that is not the official scorer. arc-agi-2 is an example. |
| undefined-boundary | 1 | **Clarified**: the same test gives `reference-implementation-only`, as 02 S12.2 records. roboarena is an example of it and the near miss on `none`. |

#### ADR parts applied

None. ADR-0014 to ADR-0019 hold no text for `data-properties.yaml`, `ceiling-anchors.yaml`,
`execution.yaml` or `maintenance.yaml`.

#### Examples fixed

None. Every term in these three files had `examples: []` before this revision, so no existing
verdict could contradict its tests. The existing example that a failure record contradicts
(osworld-2-0's 72.4% human baseline) is in `subjects.yaml`.

#### Records whose value changes under the revised tests (for P1-S1-T08)

Each of these is also a taxonomy example:
- terminal-bench-2-0: its provenance changes to `expert-authored` and its ceiling to
  `measured-ceiling`.
- osworld-2-0: its provenance changes to `crowd-authored`.
- paperbench: its compute tier changes to `single-gpu`.
- posebusters: its contamination changes to `high`, which needs the paper as
  `contamination_evidence`.
- wmdp: its harness changes to `official-harness` and its refresh to `versioned-releases`.
- matbench-discovery: its refresh changes to `rolling-live`.
- a2rl-drone-championship: its contamination changes to `low`.
- camelyon17: `synthetic-procedural` is dropped from its provenance.
- geo-bench-2 and melting-pot: their ceiling changes to `none-known`.
- libero: its refresh changes to `static`.

The layering rules also re-decide agentharm-001, 2026-behavior-challenge-004, lmarena-007 and
weatherbench-2-009.

#### Inconsistencies found in 02 (not fixed: outside this task's files)

- **02 S11 against its own worked examples.** 02 S11 blocks `fully-automatable` beside any
  blocker except `licence-restriction`. Yet S12.5 (Kaggle Game Arena) and S12.8 (ForecastBench)
  pair `fully-automatable` with `live-world-state`. This is the root of both deferrals above.
- **Where `wet-lab` belongs.** 02 S10's changelog cites "CASP's experimental ground truth" for
  the compute tier `wet-lab`. S12.1 records CASP as `cluster`, and S12.10 records the Virtual
  Cell Challenge as `multi-gpu-node`, which reads the tier as entrant-side cost. No failure
  record in this batch forced a choice, so the `wet-lab` definition is unchanged.
