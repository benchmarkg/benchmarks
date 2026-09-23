# D1 -- The capability-group vocabulary

- **Status:** Decided
- **Date:** 2026-09-21
- **Owns:** the capability-group vocabulary, canonically enumerated in `02-taxonomy.md` §4.3 and
  stored as `taxonomy/capability_groups.yaml`. It is the **coarse (column) axis** of the coverage
  matrix.
- **Depends on:** G3 (44 capability terms, canonical). Silent on the **row** axis, which is
  [D4](D4-nineteen-family-cascade.md).
- **Serves:** differentiator 3, coverage and gap analysis. Every ruling below is justified by what
  it does to the interpretability of a coverage cell.

---

## 1. The problem this closes

Until 2026-09-21 this vocabulary **did not exist anywhere in the corpus**, and three documents
depended on it. `12-analytics-and-trends.md` asserted "19 domain families x 12 capability groups
= 228" and cited `02-taxonomy.md` §4.3 by name for an enumeration "by id, label and member terms";
there is no §4.3. `10-visualization.md` independently asserted "~8 capability groups (144 cells)".
`03-taxonomy-build-process.md` assumed a rollup existed without saying what it was.

Three vocabularies were proposed independently -- from construct validity, from inter-annotator
agreement at the curator's desk, and backwards from what makes an empty cell defensible -- then
scored and synthesised. All three proposals were mechanically valid partitions.

| Proposal | Groups | Sizes | Partition |
| --- | --- | --- | --- |
| cognitive | 12 | 3-6 | valid |
| curator | 11 | 3-6 | valid |
| gapmap | 12 | 2-5 | valid |
| **synthesised (this document)** | **13** | **3-4** | **valid** |

---

## 2. The decision

**13 capability groups**, a strict partition of all 44 capability terms, each term in
exactly one group. The coarse coverage grid is therefore **19 domain families x 13 capability groups = 247 cells**, replacing the 228 asserted in
`12-analytics-and-trends.md` and the 144 asserted in `10-visualization.md`.

Neither 12 nor 8 was adopted. 12 was a number nobody had derived; 8 was a HELM-shaped default
whose failure is not unreadability but that its gap output falls to near zero exactly when the
corpus becomes good enough to support gap claims (§4).

### Verification, run against this file

```
groups                        : 13
members, total                : 44 / 44
group sizes                   : 4, 3, 4, 4, 4, 3, 3, 3, 4, 3, 3, 3, 3
terms missing from any group  : none
terms in more than one group  : none
members not in the vocabulary : none
group id colliding with a term: none
```

Re-run this check with `scripts/verify_corpus.py` after any edit. A rollup that is not a partition
silently double-counts or drops benchmarks in every published coverage figure.

---

## 3. The vocabulary

Ready to paste into `02-taxonomy.md` as §4.3, and to serialise as
`taxonomy/capability_groups.yaml`. The `definition` field is published on the site.

| # | id | label | n | member terms |
| --- | --- | --- | --- | --- |
| 1 | `knowledge-and-memory` | Knowledge & memory | 4 | `knowledge-recall` · `factual-precision` · `memory-retention` · `context-integration` |
| 2 | `formal-quantitative-reasoning` | Formal & quantitative | 3 | `deductive-reasoning` · `quantitative-reasoning` · `constraint-satisfaction` |
| 3 | `abstraction-and-analogy` | Abstraction & analogy | 4 | `abstraction` · `inductive-reasoning` · `analogical-reasoning` · `compositional-generalization` |
| 4 | `causal-and-experimental-inference` | Causal & experimental | 4 | `abductive-reasoning` · `causal-reasoning` · `hypothesis-generation` · `experimental-design` |
| 5 | `perception-space-time` | Signal, space & time | 4 | `perception` · `grounding` · `spatial-reasoning` · `temporal-reasoning` |
| 6 | `planning-and-search` | Planning & search | 3 | `planning` · `search-exploration` · `optimization` |
| 7 | `action-and-execution` | Action & execution | 3 | `sensorimotor-control` · `tool-use` · `long-horizon-execution` |
| 8 | `controlled-generation` | Controlled generation | 3 | `generation-fidelity` · `creativity-novelty` · `instruction-following` |
| 9 | `conduct-and-cooperation` | Conduct & cooperation | 4 | `collaboration` · `communication` · `honesty` · `harm-avoidance` |
| 10 | `learning-and-transfer` | Learning & transfer | 3 | `sample-efficiency` · `continual-learning` · `transfer-learning` |
| 11 | `robustness-and-stability` | Shift & robustness | 3 | `distribution-shift-generalization` · `adversarial-robustness` · `reliability-consistency` |
| 12 | `uncertainty-and-self-monitoring` | Uncertainty handling | 3 | `calibration-uncertainty` · `probabilistic-forecasting` · `self-correction` |
| 13 | `autonomy-and-oversight` | Autonomy & oversight | 3 | `autonomy` · `self-improvement` · `situational-awareness` |

### Definitions

**`knowledge-and-memory` -- Knowledge & memory**
Isolates whether the information a task needs is available and correctly held at the moment of use, whether it sits in the system's parameters or is supplied in its context.

**`formal-quantitative-reasoning` -- Formal & quantitative**
Isolates conclusions that follow necessarily from stated rules, numbers or constraints and are checkable against them -- proof, calculation and constraint compliance rather than explanation.

**`abstraction-and-analogy` -- Abstraction & analogy**
Isolates rules and representations not present in the surface form of the input: abstraction of a representation, induction of a rule from examples, analogical mapping, and recombination of known primitives in unseen arrangements.

**`causal-and-experimental-inference` -- Causal & experimental**
Isolates reasoning about why something happened and what would happen under intervention: abduction to the best explanation, causal inference, generation of candidate hypotheses, and design of the experiment that would discriminate between them.

**`perception-space-time` -- Signal, space & time**
Isolates extracting structure from a raw sensory or simulated signal and situating it among referents, locations and instants, in perceived and in described worlds alike.

**`planning-and-search` -- Planning & search**
Isolates production of a solution over a space of options against an objective -- plan construction, exploration of the option space, and optimisation -- where the score is a property of the solution rather than of a rollout.

**`action-and-execution` -- Action & execution**
Isolates closed-loop acting on an external environment over time: motor control of a physical or simulated body, invocation of external tools and APIs, and execution sustained across many steps, scored by what the run achieved.

**`controlled-generation` -- Controlled generation**
Isolates production of an open-ended artefact against an externally specified target -- a reference, a rubric or a stated instruction -- where the score is a judgement about the artefact rather than a discrete decision.

**`conduct-and-cooperation` -- Conduct & cooperation**
Isolates how the system behaves toward other parties when behaviour rather than accuracy is what is scored: cooperation with another agent or human, informativeness toward a recipient, truthfulness, and refusal to cause harm.

**`learning-and-transfer` -- Learning & transfer**
Isolates change in performance as a function of experience -- how much data is needed, whether learning accumulates across episodes without forgetting, and whether it carries to a new task or embodiment -- measured as a difference or a slope, never as a single score.

**`robustness-and-stability` -- Shift & robustness**
Isolates retention of performance when the evaluation condition changes rather than whether it is achievable once: under shifted inputs, under deliberate attack, and under nothing but repetition of the identical task.

**`uncertainty-and-self-monitoring` -- Uncertainty handling**
Isolates the quality of stated uncertainty and error detection rather than of the point estimate: confidence that matches accuracy, probability assigned to events whose truth value does not yet exist, and revision of an output once evidence indicates it is wrong.

**`autonomy-and-oversight` -- Autonomy & oversight**
Isolates capacity and propensity to operate, persist or improve outside direct supervision, including recognising that it is being evaluated and behaving differently because of it.

```yaml
# taxonomy/capability_groups.yaml
# A partition of taxonomy/capability.yaml. CI asserts every capability term appears
# in exactly one group. Moving a term between groups requires an ADR (02 §11 rule 9),
# because it re-shapes every published gap claim in both columns without changing any
# benchmark record.
version: 1.0.0
groups:
  - id: knowledge-and-memory
    label: "Knowledge & memory"
    definition: >-
      Isolates whether the information a task needs is available and correctly held at the
      moment of use, whether it sits in the system's parameters or is supplied in its
      context.
    members:
      - knowledge-recall
      - factual-precision
      - memory-retention
      - context-integration
  - id: formal-quantitative-reasoning
    label: "Formal & quantitative"
    definition: >-
      Isolates conclusions that follow necessarily from stated rules, numbers or constraints
      and are checkable against them -- proof, calculation and constraint compliance rather
      than explanation.
    members:
      - deductive-reasoning
      - quantitative-reasoning
      - constraint-satisfaction
  - id: abstraction-and-analogy
    label: "Abstraction & analogy"
    definition: >-
      Isolates rules and representations not present in the surface form of the input:
      abstraction of a representation, induction of a rule from examples, analogical
      mapping, and recombination of known primitives in unseen arrangements.
    members:
      - abstraction
      - inductive-reasoning
      - analogical-reasoning
      - compositional-generalization
  - id: causal-and-experimental-inference
    label: "Causal & experimental"
    definition: >-
      Isolates reasoning about why something happened and what would happen under
      intervention: abduction to the best explanation, causal inference, generation of
      candidate hypotheses, and design of the experiment that would discriminate between
      them.
    members:
      - abductive-reasoning
      - causal-reasoning
      - hypothesis-generation
      - experimental-design
  - id: perception-space-time
    label: "Signal, space & time"
    definition: >-
      Isolates extracting structure from a raw sensory or simulated signal and situating it
      among referents, locations and instants, in perceived and in described worlds alike.
    members:
      - perception
      - grounding
      - spatial-reasoning
      - temporal-reasoning
  - id: planning-and-search
    label: "Planning & search"
    definition: >-
      Isolates production of a solution over a space of options against an objective -- plan
      construction, exploration of the option space, and optimisation -- where the score is
      a property of the solution rather than of a rollout.
    members:
      - planning
      - search-exploration
      - optimization
  - id: action-and-execution
    label: "Action & execution"
    definition: >-
      Isolates closed-loop acting on an external environment over time: motor control of a
      physical or simulated body, invocation of external tools and APIs, and execution
      sustained across many steps, scored by what the run achieved.
    members:
      - sensorimotor-control
      - tool-use
      - long-horizon-execution
  - id: controlled-generation
    label: "Controlled generation"
    definition: >-
      Isolates production of an open-ended artefact against an externally specified target
      -- a reference, a rubric or a stated instruction -- where the score is a judgement
      about the artefact rather than a discrete decision.
    members:
      - generation-fidelity
      - creativity-novelty
      - instruction-following
  - id: conduct-and-cooperation
    label: "Conduct & cooperation"
    definition: >-
      Isolates how the system behaves toward other parties when behaviour rather than
      accuracy is what is scored: cooperation with another agent or human, informativeness
      toward a recipient, truthfulness, and refusal to cause harm.
    members:
      - collaboration
      - communication
      - honesty
      - harm-avoidance
  - id: learning-and-transfer
    label: "Learning & transfer"
    definition: >-
      Isolates change in performance as a function of experience -- how much data is needed,
      whether learning accumulates across episodes without forgetting, and whether it
      carries to a new task or embodiment -- measured as a difference or a slope, never as a
      single score.
    members:
      - sample-efficiency
      - continual-learning
      - transfer-learning
  - id: robustness-and-stability
    label: "Shift & robustness"
    definition: >-
      Isolates retention of performance when the evaluation condition changes rather than
      whether it is achievable once: under shifted inputs, under deliberate attack, and
      under nothing but repetition of the identical task.
    members:
      - distribution-shift-generalization
      - adversarial-robustness
      - reliability-consistency
  - id: uncertainty-and-self-monitoring
    label: "Uncertainty handling"
    definition: >-
      Isolates the quality of stated uncertainty and error detection rather than of the
      point estimate: confidence that matches accuracy, probability assigned to events whose
      truth value does not yet exist, and revision of an output once evidence indicates it
      is wrong.
    members:
      - calibration-uncertainty
      - probabilistic-forecasting
      - self-correction
  - id: autonomy-and-oversight
    label: "Autonomy & oversight"
    definition: >-
      Isolates capacity and propensity to operate, persist or improve outside direct
      supervision, including recognising that it is being evaluated and behaving differently
      because of it.
    members:
      - autonomy
      - self-improvement
      - situational-awareness
```

---

## 4. Why 13 groups: the density argument

Grid: 19 domain families x 13 groups = 247 coarse cells, against a corrected fine grid of 204 x 44 = 8,976.

The load-bearing number is the rollup collapse factor, and I measured it rather than assuming it. Scoring this partition against the ten adversarially chosen worked classifications in 02 §12 gives distinct-group counts of 4, 4, 3, 2, 3, 4, 4, 2, 4, 3 -- mean 3.30 groups from a mean 4.2 terms, a 0.786 collapse. (The same script reproduces cognitive's 3.3 and curator's 3.1 exactly and corrects gapmap's 2.9 to 3.00.)

Seed. Capability is required at `full`, not `stub` (02 §2), so a stub occupies a domain row without tagging a column -- gapmap is right about this and the other two ignore it. At the ~300 Tier-1 families of 02 §3 with 70% at `full`: 210 x 3.30 = 693 primary-domain (family, group) incidences over 247 cells, mean 2.81. If all 300 reach `full`: 990 incidences, mean 4.01, which is what should replace §5.1's "~900 / ~3.9". At the 333 the seed table actually sums to (G6): 1,099, mean 4.45. Secondary domains at the published 0.5 weight lift all three by roughly 40%.

Maturity. 1,500 families x 3.30 = 4,950 incidences over 247 cells, mean 20.0. The fine grid for contrast carries the brief's ~6,000 incidences over 8,976 cells at mean 0.67 -- about 89% empty by arithmetic before any curation decision, which is why it stays drill-down only and why §5.1's 87% should be restated at the corrected denominator.

Mean occupancy does not discriminate 8 from 13 and it is fake precision to pretend it does; curator is right about that and the other two overstate it. Under any independence null every applicable cell fills long before maturity. Emptiness at maturity is entirely structural: a coarse cell is empty only when every member term is a structural zero for that family. That makes the discriminating quantity q^m, where q is the per-(family, term) structural-zero rate and m the group size. At q = 0.6 (my assumption, not a measurement -- unverified, confirm before relying on this), 13 groups leave 18.3% of cells empty (45 of 247); the 8-group HELM-shaped grid 10-visualization assumes leaves 9.9% (15 of its true 152 cells, not the 144 it prints, since 18 families is stale). At q = 0.7 the split is 30.3% (75 cells) against 18.3% (28 cells). Grouped members are positively correlated in their structural zeros, which lifts both figures and lifts the 13-group figure more. So 13 columns preserve roughly three times the absolute gap surface of 8 at maturity, and the 3-member floor is exactly what buys it: 0.6^3 = 0.216 against 0.6^5.5 = 0.099. The 8-column grid's failure is not unreadability -- it is that its gap output falls to near zero precisely when the corpus finally becomes good enough to support gap claims.

Row skew, not column count, dominates seed emptiness, and 13 does not fix it: vision and biology-genetics at seed 30 contribute 99 incidences at 7.6 per cell, agents-tooluse at 25 gives 6.3, games-planning at 15 gives 3.8, general-intelligence at 12 gives 3.0, and engineering-design at 8 gives 2.0 -- a row that violates both the 15-entry floor in 02 §3 and the 12-entry floor in 14-roadmap (G7) and will publish nothing until curation lifts it. That is a curation-schedule problem, not a vocabulary problem, and curation_confidence already gates it.

Two secondary costs, both small. The mandatory not-applicable triage grows from 228 to 247 declarations -- nineteen more editorial judgements, an hour of taxonomy work. And 13 horizontal tick labels at 19 rows, at the label lengths given here (all under 22 characters), should still render without rotation at laptop width in ECharts MatrixComponent (unverified -- confirm against the render before freezing the default view).

### Reconciliation with D2 (seed total)

The figures above were computed in parallel with [D2](D2-seed-targets-and-floor.md) and therefore
use the old seed numbers -- "~300 Tier-1", and 333 as the column sum. **D2 settled the canonical
seed total at 320.** Restated at 320, with the same measured collapse factor of 3.3:

| Scenario | Entries at `full` | Incidences | Cells | Mean per cell |
| --- | --- | --- | --- | --- |
| Seed, 70% at `full` | 224 | 739 | 247 | 2.99 |
| Seed, all at `full` | 320 | 1056 | 247 | 4.28 |
| Maturity | 1500 | 4950 | 247 | 20.04 |

Secondary domains at the published 0.5 weight lift all three by roughly 40%. These are the
figures `12-analytics-and-trends.md` §5.1 should carry; its current "~900 / ~3.9" was computed
against a 198-subdomain, 12-group grid that never existed. The collapse factor itself is measured
against the ten worked classifications in `02-taxonomy.md` §12 and is the weakest input here --
see risk 11.

---

## 5. Scoring of the three proposals

SCORING. I read 02 §4 and §11 and 12-analytics §5 and §10 before judging, and three of the proposals' characterisations of those documents do not survive the reading; the corrections drive the decision.

cognitive (12) -- (a) 4/5: strong cuts, but reasoning-and-inference is a container of six terms, not a construct, and it admits quantity-space-time is its weakest column. (b) 4/5: the two blurs 02 §4 actually names -- the shift/attack/repetition triad and the calibration-versus-forecasting pair -- both collapse correctly; but the six-term reasoning block buys agreement by absorbing every reasoning mis-tag, which is information loss wearing agreement's clothes. (c) 3/5: best of the three on the one claim that matters and worst on the plan's own headline term. autonomy-and-oversight makes 12-analytics §5.5's flagship day-one finding (no coverage for evading oversight, self-replication, AI R&D) a single-column claim; a six-term reasoning column makes causal-reasoning -- the term 02 §4 uses as its example of a capability recurring across chemistry, economics and medicine -- unreadable on the coarse axis, and §5.1 permits published gap claims only from the coarse axis. (d) 3/5: sizes 3-6. (e) 5/5: the most honest document of the three, including the observation that it rejected a 13th group on its own floor rather than on merit.

curator (11) -- (a) 3/5: action-and-autonomy mixes an ability (sensorimotor-control) with a propensity (autonomy), which its own maximal-versus-typical logic forbids. (b) 5/5: the best taggability reasoning available, and the only proposal that derives its hard placements systematically from 02 §4's disambiguation notes. (c) 2/5: disqualifying. Splitting autonomy, self-improvement and situational-awareness across three columns makes the project's only published capability-axis gap claim unexpressible at coarse resolution; curator names this and accepts it, which is honest but fatal for a vocabulary whose purpose is differentiator 3. (d) 3/5: sizes 3-6. (e) 5/5: uniquely notices that group-level agreement beats term-level agreement by construction, so a good rollup number can sit on top of a broken term.

gapmap (12) -- (a) 4/5: the best reasoning cut in the set. Splitting the nine reasoning terms three ways (checkable derivation / rule induction / causal-explanatory) is the only version where a specialist accepts each column as one thing; against that, autonomy-and-tool-use is five terms held together by the word "agency". (b) 3/5: weakest. It breaks 02 §4's own shift/attack/repetition triad and splits collaboration from communication, which it names as its own weakest seam. (c) 3/5: the sharpest analytic tool in the whole set -- "a column fills on its most common member" -- applied to everyone else's proposal and then failed twice in its own: tool-use fills autonomy-and-tool-use in every agent row, burying the self-replication and AI-R&D claim, and distribution-shift-generalization fills learning-and-generalisation in nearly every row, which it concedes as "12 columns but roughly 11 informative ones". (d) 2/5: worst. A 2-member column at seed reads as a curation artefact, as its own first risk admits. (e) 4/5: two load-bearing contributions (the derived-not-tagged observation, and the named fine-cell allow-list), one arithmetic slip -- its collapse factor on the ten worked classifications is 3.00, not 2.9, because it scores WeatherBench 2 at two groups when quantitative-reasoning sits in its own formal column, making three.

SKELETON AND GRAFTS. I built on gapmap's skeleton, because the reasoning split is the one structural decision that cannot be repaired by grafting: a six-term reasoning column is not a construct, and it silences causal-reasoning, the term the taxonomy itself nominates as the cross-domain exemplar. I kept gapmap's knowledge-and-memory (unanimous across all three), formal-quantitative-reasoning, abstraction-and-analogy (including compositional-generalization, on 02 §4's explicit representation/evidence/arrangement triple), causal-and-experimental-inference, and perception plus grounding plus spatial and temporal reasoning in one column.

Grafted from cognitive: autonomy-and-oversight verbatim -- the single best decision in the three proposals, because it is the only arrangement under which 12-analytics §5.5's flagship finding is a coarse-grid claim rather than a fine-grid one that §5.1 forbids publishing; conduct-and-cooperation, on the maximal-versus-typical boundary, so a disposition never shares a column with an ability; and the 3/3/3 split of the nine learning, robustness and metacognition terms, which keeps 02 §4's shift/attack/repetition triad intact against gapmap's split of it. Grafted from curator: the co-location principle -- where 02 §4 admits two terms blur, put them in one column so a fine mis-tag still lands in the right coarse cell -- which is why collaboration and communication sit together despite the gap cost, and why calibration and forecasting do; and the demand that capability_groups.yaml be versioned in build/derived/manifest.json. Grafted from gapmap: the named, ADR-approved allow-list of publishable fine cells, which is the honest remedy for the terms a rollup necessarily buries, and the observation that re-grouping triggers no retro-tag pass because nothing in data/ references a group id.

Departures from all three: no group exceeds 4 members or falls below 3 (sizes are eight 3s and five 4s, spread ratio 1.33 against cognitive's and curator's 2.0 and gapmap's 2.5); planning-and-search is cut from action-and-execution on the evidence that validates it -- deliberation is scored against a solution, execution against a rollout -- which no proposal did; and instruction-following joins controlled-generation rather than a conduct or interaction column, because IFEval-shaped scores are properties of a produced artefact, not dispositions.

GROUP COUNT: 13, not 12 and not 8. Both cognitive and gapmap weight the convenience of matching 12-analytics' already-published 228 cells. That convenience is worth zero, and this is verifiable rather than arguable: CI check 9b in 05-repository-and-workflow.md regenerates the vocabulary summary in 02 §14 and every term count in 12-analytics §5.1 from taxonomy/*.yaml and fails on any diff -- the coarse-cell count is generated, never typed. Worse, §5.1 is already wrong three independent ways (198 subdomains against the true 204; 8,712 fine cells against 8,976; "about three capability tags" against the 4.2 measured in its own §12 worked set and the "four" in 10-visualization), and §10.5 imports 10-visualization's wrong 6,960. That section is being rewritten regardless, so the group count is free of edit cost and must be decided on the merits alone.

On the merits: the 3-member floor caps the count at 14 (44 / 3 = 14.67). 13 is 14 minus the one split I refuse -- separating knowledge-recall plus factual-precision from memory-retention plus context-integration, a cleaner psychometric boundary than several cuts I did make, rejected because it yields two 2-member columns that read as curation artefacts at seed rather than as findings. 13 is therefore the largest count at which every column is a construct a specialist would accept, no column is a grab-bag, and all four claims the plan has already committed to publishing stay expressible on the coarse axis.

The failure I am trading against: I accept more false-gap noise at seed, and refuse false coverage at maturity. Seed noise is already defended -- curation_confidence renders as a hatch overlay and never fuses into density (10-visualization), 12 §5.4 separates the three kinds of empty and publishes only category 1, and 12 §13 withholds the Gap Finder until Phase 4 and domain-reviewer sign-off on half the families. Nothing defends against false coverage: a gap hidden inside a merged column produces no signal, is never checked, and quietly converts differentiator 3 into a claim about our column design. A gap claim withheld two months costs nothing; a gap claim a roboticist falsifies in ten minutes costs the differentiator.

---

## 6. Risks carried forward

These survive the synthesis. Several are inherited knowingly; where a risk was accepted rather
than solved, the text says so.

1. action-and-execution is fillable by tool-use in every agent-adjacent row, so gapmap's claim that closed-loop physical control is measured only in robotics is not expressible on the coarse axis. This is inherited knowingly from all three proposals, and it partly undoes the reason 02 §4 added sensorimotor-control at all -- that the robotics row of the coverage matrix had no column to land in. The remedy is gapmap's named fine-cell allow-list, which requires an ADR amending 12 §5.1's blanket prohibition on fine-grid claims; without it, accept the loss and say so on the methodology page.

2. conduct-and-cooperation is fillable by communication, whose base rate is carried by four existing subdomains (dialogue, clinical-dialogue, negotiation, human-robot-interaction), so honesty and harm-avoidance gaps are masked in language, medicine-health, society-econ-law and robotics-embodiment. I chose this over splitting collaboration from communication because that pair is the one seam every proposal admits is a coin flip, and a drift into a thin gap column destroys claims while a drift within a dense column does not. Consequence: the cell tooltip must break the count down by member term rather than reporting the group total.

3. robustness-and-stability carries distribution-shift-generalization, 6 of the 42 tags in the worked set and the most-applied term in the corpus. It is a floor column: dense in nearly every row, producing almost no gap claims, and it buries adversarial-robustness and reliability-consistency (tau-bench's pass^k) behind a term with several times their base rate. I kept 02 §4's own shift/attack/repetition triad over gapmap's split because breaking a documented disambiguation triad costs agreement on the corpus's own named blur, but this is the most contestable decision in the partition and should be re-examined by ADR once ~200 entries are tagged and real co-occurrence is visible.

4. quantitative-reasoning is the most over-applied term in the corpus -- 4 of the 10 worked classifications, and in CASP17 and Matbench Discovery it appears to mean little more than "the output is a number". Placing it in formal-quantitative-reasoning limits the damage, because the cell then reads "this domain has checkable numeric answers", which is true if uninformative, rather than "this domain reasons about magnitude" or "this domain handles uncertainty". The cost is that this column inflates across every science row and deductive-reasoning's own gap becomes unreadable inside it.

5. The instruction-following / constraint-satisfaction seam crosses two groups (controlled-generation and formal-quantitative-reasoning) and 02 §4 carries no disambiguation note for it, which is a gap in the fine vocabulary this rollup cannot close. Tie-break, derived from 02 §11 rule 2: tag the term the benchmark's own source claims -- IFEval claims instruction-following, PoseBusters physical validity and tau-bench policy compliance claim constraint-satisfaction. Both columns are dense, so drift moves mass without destroying a gap claim, but per-term F1 for both must be watched in the first inter-rater run.

6. compositional-generalization sits in abstraction-and-analogy on 02 §4's representation/evidence/arrangement triple, so Procgen- and Craftax-style RL generalisation benchmarks land in a column their authors would call generalisation. Inherited knowingly from gapmap; the alternative placed it in learning-and-transfer, where distribution-shift-generalization would have buried it in any case.

7. spatial-reasoning and temporal-reasoning sit in perception-space-time, and both are also reasoning-general subdomains, so purely textual spatial or temporal benchmarks will make a family look perceptually covered when it is not. The label "Signal, space & time" rather than "Perception" blunts the misreading and the definition says perceived and described worlds alike, but the fake fill in the rendered cell survives and the tooltip must decompose by member term. Both curator and gapmap flagged this; neither solved it and neither have I.

8. uncertainty-and-self-monitoring dilutes what gapmap correctly identifies as the highest-value gap column in the design, by adding self-correction to calibration and forecasting. The clinical-calibration gap now requires that medicine-health measure neither calibration nor self-correction. I accepted the dilution to avoid a 2-member column that reads as a curation artefact at seed, but gapmap's deliberate curation sweep for calibration claims is still needed before the coverage map publishes, because 02 §11 rule 2 forbids inferring the tag and benchmark authors rarely claim calibration explicitly.

9. autonomy-and-oversight and conduct-and-cooperation will read near-empty across physics, chemistry-materials, biology-genetics, earth-climate and engineering-design, and most of that emptiness is structural rather than a finding. The not-applicable declarations that 03-taxonomy-build-process.md and 10-visualization.md call mandatory are therefore a hard dependency: without them these two columns manufacture roughly twenty false gaps on day one, in exactly the rows a specialist reviewer checks first. The triage is not a blanket, though -- autonomous laboratories make chemistry-materials x autonomy-and-oversight a live and informative cell, and declaring it inapplicable would itself be an error.

10. situational-awareness means evaluation-awareness and sandbagging in this taxonomy, not an agent's awareness of its own state. Its plain-English reading points at context-integration, so a curator who has not read the definition mis-tags it into the frontier-risk column -- the one that attracts the most external scrutiny. Grouping cannot repair a misleading slug; rename by ADR before the v1.0.0 freeze. Carried forward from curator.

11. Every collapse and occupancy figure here rests on ten benchmarks chosen adversarially in 02 §12, and they are not merely a small sample but a skewed one: there is no language, code or safety-alignment benchmark among them, which are three of the densest parts of the real corpus, and instruction-following, honesty, harm-avoidance, collaboration, communication, autonomy and self-improvement appear either once or not at all. The 3.30 collapse factor could move by a third. Re-validate against real tag co-occurrence at ~200 entries at `full` completeness, before Phase 3 publishes the coverage map.

12. Group-level agreement exceeds term-level agreement by construction, so a healthy rollup figure can sit on top of a broken term. Note also that the >=0.85 raw-agreement bar is 03 §6's bar for single-valued facets and does not apply here: capability is multi-valued, the applicable bar is >=0.65 mean Jaccard with no term below 0.50 F1, and the group axis is derived and never tagged, so the only thing this partition controls is whether a fine mis-tag survives the collapse. Keep reporting per-term F1 after the rollup exists and add a group-level confusion matrix, or a systematic bias in one high-base-rate term propagates into a whole column undetected.

13. Coarse and fine density cannot be reconciled and should not be presented as if they could: a benchmark tagged four terms that all roll into one group occupies one coarse cell and four fine cells, so "how much is measured here" has two correct answers. The methodology page must state that the coarse grid counts benchmarks per group rather than tags, and that the coarse total is not the row sum of the fine grid.

14. Re-grouping requires no retro-tag pass -- nothing in data/ references a group id -- but it silently re-shapes every published gap claim in the affected columns with no change to any benchmark record. capability_groups.yaml must therefore be versioned, its version recorded in build/derived/manifest.json and cited with every coverage figure, and 02 §11 rule 9's ADR requirement must be extended from adding a term to moving a term between groups. Both curator and gapmap asked for this and both were right.

15. This vocabulary does not repair CI check 9c. All 13 ids were checked mechanically against the 44 capability terms, the 204 subdomain slugs and the 19 family slugs and collide with none, but planning, spatial-reasoning, temporal-reasoning and compositional-generalization remain in both the capability and subdomain vocabularies, so 05-repository-and-workflow.md L709's disjointness assertion still fails on day one and needs a named exemption list or axis namespacing. Add the check whose absence caused this whole defect: assert that capability_groups.yaml is a partition of capability.yaml, every term in exactly one group.

16. Adopting 13 groups is incomplete without four edits, and shipping the vocabulary without all of them leaves the contradiction it was written to close. Write 02-taxonomy.md §4.3 with this enumeration (it is cited by 12-analytics and does not exist). Correct 12-analytics §5.1 to 19 x 13 = 247 coarse cells, 204 x 44 = 8,976 fine, 4.2 capability tags per benchmark rather than "about three", ~990 occupied pairs at mean ~4.0, and ~89% fine-grid emptiness; and §10.5 to 247 coarse and 8,976 fine. Correct 10-visualization L234-241 to 19 families, 204 subdomains, 44 terms, 8,976 fine cells and a default view of 19 x 13 = 247, and close its open question 3. Confirm the 13-column render in ECharts MatrixComponent at laptop width before freezing the default view (unverified -- confirm before relying on this).

---

## 7. EDITS REQUIRED, BY FILE AND LINE

Line numbers are as of 2026-09-21 before this pass and may shift; find by content.

### `02-taxonomy.md` -- owner of the enumeration

1. **Add §4.3, the capability-group vocabulary**, from §3 of this document: the table, the
   definitions and the YAML. It is cited by `12-analytics-and-trends.md` and does not exist. This
   is the single most important edit in this decision.
2. **Remove the duplicate `causal-reasoning`** in the §4 term list (printed twice; 45 listings,
   44 distinct). The "Forty-four terms" claim is correct only after this.
3. Add a line to §4.3 stating that the group axis is **derived and never hand-tagged**: curators
   tag terms, the rollup is computed. This is what makes the >=0.85 agreement bar in
   `03-taxonomy-build-process.md` §6 inapplicable to groups (risk 12).
4. Extend §11 rule 9 so an ADR is required to **move a term between groups**, not only to add or
   remove a term (risk 14).

### `12-analytics-and-trends.md` -- largest consumer

5. §5.1: coarse grid becomes **19 x 13 = 247 cells**, not
   19 x 12 = 228. Fine grid becomes **204 x 44 = 8,976**, not 198 x 44 = 8,712.
6. §5.1: replace "~900 occupied pairs / mean ~3.9" with the D2-reconciled figures in §4 above.
7. §5.1: capability tags per benchmark is **4.2**, measured against the ten worked
   classifications, not "about three".
8. §5.1: restate fine-grid emptiness (~89%) against the corrected 8,976 denominator; the current
   87% was computed against 8,712.
9. §5.1/§10.5: remove the dangling citation of "02 §4.3" as a forward reference and cite it as an
   existing section once edit 1 lands.
10. Methodology: state that the coarse grid counts **benchmarks per group, not tags**, and that
    the coarse total is not the row sum of the fine grid (risk 13).
11. Cell tooltips must **decompose by member term**, not report the group total only
    (risks 2, 7).

### `10-visualization.md`

12. L234-243: **19** families, **204** (family, subdomain) pairs, **44** capability terms,
    **8,976** fine cells. Currently "eighteen", "~174", "about forty", "6,960" -- every figure
    in that paragraph is wrong.
13. L241: the default coverage view becomes **19 x 13 = 247 cells**, not "18 x ~8 (144)".
14. Close its open question on how many capability groups there are; it is answered here.
15. Confirm 13 horizontal tick labels render without rotation at laptop width in
    ECharts `MatrixComponent` before freezing the default view. All labels are under 22
    characters. *(unverified -- confirm before relying on this)*

### `03-taxonomy-build-process.md`

16. L492: "18 domain families and roughly 40 capability terms" becomes **19** and **44**, and the
    coverage matrix it describes is the 247-cell coarse grid.
17. L832: "the 11 subdomains under `robotics-embodiment`" -- there are **15**.
18. §6: the >=0.85 raw-agreement bar is for single-valued facets. Capability is multi-valued; the
    applicable bar is **>=0.65 mean Jaccard with no term below 0.50 F1**, and the group axis is
    derived, so it is not tagged and not scored for agreement (risk 12).

### `05-repository-and-workflow.md`

19. Add the CI check whose absence caused this defect: **`capability_groups.yaml` is a partition
    of `capability.yaml`** -- every term in exactly one group, no unknown members, no duplicates.
20. Record `capability_groups.yaml`'s **version in `build/derived/manifest.json`**, cited with
    every published coverage figure, so a re-grouping is attributable (risk 14).
21. Check 9c is **not** repaired by this decision -- see [D3](D3-vocabulary-namespacing.md),
    which rules that 9c is a category error rather than a failing check (risk 15).

### Dependency, flagged for whoever sequences the work

22. The **mandatory not-applicable triage** in `03-taxonomy-build-process.md` and
    `10-visualization.md` is a hard dependency of this vocabulary, not a nicety. Without it,
    `autonomy-and-oversight` and `conduct-and-cooperation` manufacture roughly twenty false gaps
    on day one across physics, chemistry-materials, biology-genetics, earth-climate and
    engineering-design -- the rows a specialist reviewer checks first. The triage is not a
    blanket: autonomous laboratories make chemistry-materials x autonomy-and-oversight a live and
    informative cell (risk 9).

23. Re-validate the 3.3 collapse factor against real tag co-occurrence at ~200
    entries at `full` completeness, **before Phase 3 publishes the coverage map**. It currently
    rests on ten adversarially chosen benchmarks with no language, code or safety-alignment
    representation, and could move by a third (risk 11).
