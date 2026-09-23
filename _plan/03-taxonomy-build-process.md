# 03 -- Building and Governing the Taxonomy

[02-taxonomy.md](02-taxonomy.md) states **what** the vocabulary is. This document states **how** it
gets built, validated, governed and evolved -- and why almost every step of that process is designed
around a single observation: a classification scheme designed in the abstract always fits its
designer's home domain and breaks on everything else.

That is not a hypothetical risk here. The whole premise of this project is cross-domain breadth
([00-vision-and-scope.md](00-vision-and-scope.md)), and the people building it come from the
language-model side of the field. Left to itself, a vocabulary written by LLM-literate people will
have twelve well-separated terms for kinds of reasoning and one undifferentiated bucket called
"robotics". The recon evidence is blunt about which half matters: robotics, chemistry/materials,
biology, climate and physics together are roughly **120 Tier-1 benchmark families** by the recon's
estimate (**106** under the canonical seed allocation in [02-taxonomy.md](02-taxonomy.md) §3 -- say
which set you mean), they are the differentiating core, and **no open, citable, cross-domain
catalogue covers them at depth**. That claim is narrower than the one an earlier draft made: a closed
commercial index does carry scattered entries from these fields, so the accurate statement is about
depth, openness and provenance rather than about nobody having tried
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) owns the boundary). Either way a
taxonomy that cannot describe these fields precisely destroys the only thing the project has that
nobody else does.

So the build process is bottom-up, adversarial, logged, measured and versioned. The rest of this
document is that process in order.

---

## 1. Principles

**Bottom-up from real instances, not top-down from a mental model.** Terms earn their place by being
needed to classify a benchmark that actually exists. The test of a facet is not "is it elegant" but
"did two people independently apply it the same way to CASP17, RoboArena and WeatherBench 2".

**Inherit before you invent.** Several usable vocabularies already exist and inheriting them buys
interoperability, credibility and free reconciliation against other datasets. Inventing a
synonym for an existing term buys nothing and costs a mapping table forever.

**The failure log is the product.** Every moment where a curator could not classify something is a
higher-signal input to the next revision than any amount of armchair design. Capture those moments
mechanically or they evaporate.

**Under-tagging is recoverable; over-tagging is not.** A missing capability tag is a gap someone can
fill later. A wrong capability tag silently fills a cell in the coverage matrix that should have been
empty -- and the empty cells are the most valuable output of this project
([12-analytics-and-trends.md](12-analytics-and-trends.md)). This asymmetry drives the AI-assist rules
in §7 and the definition rules in §5.

**Friction belongs on the maintainer, never on the contributor.** The most instructive failure in the
landscape is `JonathanChavezTamales/llm-leaderboard`: a JSON-in-git, schema-validated community
benchmark catalogue with 356 stars that deprecated itself and converted into a closed website
(llm-stats.com), citing contribution friction -- PRs were too slow against per-model discussion
threads on a website. Taxonomy governance therefore has heavy internal ceremony (ADRs, migrations,
revalidation) and an almost frictionless external surface (an issue form, no git knowledge required).
See [05-repository-and-workflow.md](05-repository-and-workflow.md) for the general contribution path;
§8 here covers the taxonomy-specific variant.

---

## 2. Stage 0 -- Inherit before inventing (½ day)

Before writing a single new term, reconcile the draft vocabulary in [02-taxonomy.md](02-taxonomy.md)
against what already exists. Four sources are worth the time:

| Source | What to take | Licence posture | Risk |
| --- | --- | --- | --- |
| **HELM scenario taxonomy** (Capabilities, Safety, VHELM, HEIM, ToRR, MedHELM, AudioHELM) | The best existing cross-modality scenario vocabulary. Adopt its distinctions and cite it as taxonomy ancestry. | MIT (code) | HELM entered maintenance mode 2026-06-01, so it will not track new terms -- inherit, then diverge |
| **HuggingFace leaderboard/benchmark tag namespaces** -- `test:public`/`test:private`, `submission:manual`/`automatic`/`semiautomatic`, `judge:auto`/`function`/`vlm-judge`, `eval:code`/`generation`/`math`/`safety`, `modality:`, `language:`, `domain:`, `benchmark:official` | Near-1:1 onto our `access`, `submission_process`, `evaluation_method` and comparability fields. Counted 2026-09-17 across 1,019 `leaderboard`-tagged Spaces. | per-artifact | Self-declared by Space authors and sparsely applied -- only **12.8%** of leaderboard Spaces carry `test:*` (128 of a 1,000-Space sample; [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3 owns the count, and the "~11%" an earlier draft carried was a mis-transcription of the same counts). Use as a hint with `source: hf_space_tag` provenance, never as ground truth. Note the `language:english` / `language:English` case split; normalise. |
| **Every Eval Ever / EvalEval `eval.schema.json`** (`generation_args`, `agentic_eval_config.available_tools`, `sandbox`, `metric_config`) | Field names for shared evaluation conditions, so EEE-validated results can join our benchmark records on a stable ID. | data CC BY 4.0 / code MIT | Models results, not benchmarks -- there is no benchmark taxonomy to inherit, only condition field names |
| **Inspect Evals categories** (171 evals, reported as 129 internal / 42 external — recon:landscape's live count on 2026-09-17; [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3 owns the figure and nobody here has recounted it) | A sanity check on the agent/safety slice, plus an `inspect_evals_id` cross-reference field. | MIT | Implementation-gated and language-model-gated; a protein-structure challenge can never enter it |

**Explicitly excluded from inheritance: the Papers with Code task taxonomy.** Its
`evaluation-tables` dump (~1,500 leaderboards, 1,000+ tasks) is the largest cold-start task
vocabulary available and it is **CC-BY-SA-4.0**. ShareAlike is viral: a strict reading obliges any
derived taxonomy file to be CC-BY-SA too, which contradicts the project's CC-BY core and is the
single largest legal risk in the ingestion strategy. The settled posture is that PwC is a
*reconciliation key only* -- match names and IDs against it, then write our own definitions from
primary sources, and keep any verbatim PwC text in a segregated `vendor/pwc-archive/` tree with its own
LICENSE, excluded from the CC-BY build. This is stated again in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) because it must not be discovered at
launch.

Record the inheritance in each term's `source` field (§4). "Where did this term come from" is a
question reviewers ask, and the answer "we took it from HELM" is worth far more than "we made it up".

---

## 3. Stage 1-5 -- The bootstrapping sequence

This is the ordered, time-boxed procedure. It runs **before** bulk curation begins and before the
Epoch ingest ([05-repository-and-workflow.md](05-repository-and-workflow.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)), because retrofitting a facet
change across thousands of machine-ingested records is the kind of task that quietly consumes a
month.

| Stage | Activity | Output | Time-box |
| --- | --- | --- | --- |
| 0 | Inherit and reconcile (§2) | `source:` populated on seeded terms | 4 h |
| 1 | Seed from the draft vocabulary in [02-taxonomy.md](02-taxonomy.md) | `taxonomy/*.yaml` v0.1, definitions stubbed | 6 h |
| 2 | Assemble the **stress corpus**: 90 real benchmarks (§3.2) | `taxonomy/_corpus/stress-corpus.yaml` -- name, URL, primary paper, one-line description | 15 h |
| 3 | Classify all 90 and **log every failure** (§3.3) | 90 classification records + `taxonomy/_failures/` entries | 24 h |
| 4 | Revise: add, merge, split, redefine; write inclusion/exclusion tests | `taxonomy/*.yaml` v0.9 | 12 h |
| 5 | Inter-rater run (§6), final fixes, freeze **v1.0.0**, publish definitions, open the ADR process | tagged `taxonomy-v1.0.0`, `/taxonomy` pages live | 12 h |

**Total ≈ 73 hours.** At the plan's standing 20 h/week figure that is **3.7 calendar weeks**, and it
should be planned as the opening block of Phase 1 in [14-roadmap.md](14-roadmap.md). An earlier draft
converted the same 73 hours at 10-12 h/week and reported six to seven weeks; that rate appears
nowhere else in the plan, and two documents converting hours to weeks at different rates is how a
schedule silently doubles. **Every hours-to-weeks conversion in this plan uses 20 h/week over a
50-week year** ([00-vision-and-scope.md](00-vision-and-scope.md) §6 A2 owns the planning figure).
Note that these 73 hours are *not* inside the 175-495 person-hour curation line, and neither is
[02-taxonomy.md](02-taxonomy.md) §14's 40-110 h definition-authoring pass; both are handed to
[14-roadmap.md](14-roadmap.md) §"Effort sizing" to absorb into the project total. It is not overhead: the 90
classification records from Stage 3 are upgraded in place into the first 90 benchmark entries, so 90
of the 320-entry seed target ([02-taxonomy.md](02-taxonomy.md) §3) -- 28% of it -- is already done
when the taxonomy freezes.

### 3.2 The stress corpus: 90 benchmarks, deliberately skewed

The sample is **not representative** and must not be. Language, code, math and general reasoning are
the domains where the designers' intuitions are already reliable and where the draft vocabulary was
written; they get two entries each purely as a regression check. Everything else is over-sampled.

| Domain family | n | Named entries (all verified live 2026-09-17 in recon:domains) |
| --- | --- | --- |
| language | 2 | MMLU-Pro; a WMT/IWSLT-style MT shared task |
| mathematics | 2 | FrontierMath (tiers + Erdős); miniF2F / MINIF2F-DAFNY |
| code | 2 | SWE-bench Verified; Terminal-Bench 2.0 |
| reasoning-general | 2 | GPQA Diamond; ARC-AGI-2 |
| multimodal | 2 | MMMU-Pro; Video-MME v2 |
| **robotics-embodiment** | 8 | 2026 BEHAVIOR Challenge; LIBERO; RoboTwin 2.0; **RoboArena**; Open X-Embodiment; NAVSIM v2; CARLA Leaderboard 2.0; A2RL Drone Championship |
| **biology-genetics** | 8 | **CASP17**; CASP16 NA / RNA-Puzzles joint assessment; CAFA; ProteinGym; **Virtual Cell Challenge 2026**; Open Problems in Single-Cell Analysis; BEND; Brain-Score |
| **medicine-health** | 7 | HealthBench; MedHELM; MedAgentBench v2; BraTS 2026 cluster; two arbitrary grand-challenge.org challenges; ReXrank |
| **chemistry-materials** | 7 | Open Catalyst OC20/OC22; OMol25; **Matbench Discovery**; **CACHE Challenges**; Runs N' Poses; PoseBusters; USPTO-50k |
| **agents-tooluse** | 7 | OSWorld 2.0; τ²-bench; MLE-bench; **PaperBench**; AgentDojo; WebArena; Holistic Agent Leaderboard (HAL) |
| **physics** | 6 | The Well; SRBench 2.0; FAIR Universe HiggsML Uncertainty Challenge; CritPt; Fusion Equilibrium Challenge; Metriq / QED-C |
| **earth-climate** | 6 | **WeatherBench 2**; ChaosBench; GEO-Bench-2; Sen1Floods11; CY-Bench; LifeCLEF 2026 |
| **vision** | 6 | COCO; ScanNet++; NTIRE; VBench-2.0; DocVQA (Robust Reading Competition); Tanks and Temples |
| **safety-alignment** | 6 | Inspect Evals; AgentHarm; HarmBench; WMDP; AILuminate v1.1; Apollo Research scheming suite |
| **games-planning** | 5 | **ARC-AGI-3**; **Kaggle Game Arena**; BALROG; Atari-100k; Melting Pot |
| **audio-speech** | 5 | Open ASR Leaderboard; DCASE 2026; IWSLT 2026; AudioSet; VoxSRC (retired 2023) |
| **society-econ-law** | 5 | GDPval; LegalBench / Vals Legal Bench; **ForecastBench**; FinanceBench; SimulacraBench |
| **general-intelligence** | 4 | Humanity's Last Exam; Epoch Capabilities Index; LMArena; HELM Capabilities |

**One family is deliberately absent: `engineering-design`.** Those eighteen rows cover 18 of the 19
families in [02-taxonomy.md](02-taxonomy.md) §3, and the nineteenth is missing because the domain
recon never surveyed it -- it named four candidates and no verified set, so there is nothing to draw
a representative pair from, and filling the row with guesses is the one thing this stage exists to
prevent. Its subdomain list is instead validated by the Phase-0 scoping survey that
[02-taxonomy.md](02-taxonomy.md) §3 makes a precondition of curating the family at all, and then by
the new-family IRR rule in §6.3 -- ten entries against that family's subdomain list before curating
at volume. State the consequence rather than hiding it: the vocabulary freezes at v1.0.0 with one
family's subdomain list untested against real instances, which makes engineering-design the likeliest
candidate for an early post-freeze ADR.

The ten benchmarks in bold are the schema stress-tests identified in recon:domains, and they are in
the corpus by construction, not by chance. Each one is known in advance to break something:

| Stress test | What it breaks in the taxonomy |
| --- | --- |
| **RoboArena** | No fixed task set; the "metric" is double-blind pairwise preference across distributed physical DROID robots. Breaks `evaluation_method` (needs `pairwise-preference-elo` *and* `physical-trial` simultaneously) and `maintainer_type` (a distributed network of labs, not an org) |
| **CACHE Challenges** | Participants buy compounds from Enamine and organisers assay them. Forces `wet-lab-validation`, a participant-cost concept, and `reproducibility_tier: not-independently-reproducible` to be real rather than decorative |
| **CASP17** | Editions not versions; the output is peer-reviewed assessment papers, not a leaderboard; **human-expert and automated-server entries are ranked separately**, so the same method appears twice. Forces a human-assistance condition and breaks any assumption that a benchmark has one ranking |
| **WeatherBench 2** | Its authors explicitly refuse to be a single leaderboard. The archive's `human_baseline_type` was meaningless here (the comparator is an operational NWP supercomputer), which is one of the failures that forced the rename to `ceiling_anchor_type`. Forces a `no-aggregate-by-design` flag -- and independently validates the comparability thesis |
| **Matbench Discovery** | Models are grouped into **compliance tiers by what data they were allowed to train on**. Forces a training-data eligibility concept, i.e. a comparability key on the training side, which LLM-shaped schemas have no slot for |
| **Virtual Cell Challenge 2026** | The score's ceiling is a **real biological replicate experiment** and its floor is the cell-context mean. Broke the archive's `human_baseline_type` outright and forced the rename to `ceiling_anchor_type` with a normalisation anchor that is not "human" |
| **Kaggle Game Arena** | Unbounded Elo from all-play-all (40 games per pair). A model's rating changes when a *different* model joins. Forces rating-pool identity plus snapshot date, and a refusal rule for cross-snapshot comparison |
| **ForecastBench** | Questions have no answer at submission time; scores resolve months-to-years later. Forces `resolution_status: pending\|partial\|resolved` and splits "measured on" from "resolved as of" |
| **PaperBench** | A hierarchical rubric with ~8,316 leaf nodes, graded by an LLM judge. Forces judge model + version as a first-class evaluation condition |
| **ARC-AGI-3** | **Two official leaderboards with different legality rules** -- unmodified general-purpose API systems vs harness-permitted community entries. Forces harness legality into the comparability key |

If all ten classify without a hack, the vocabulary will survive the other 1,400. If any of them needs
a free-text escape hatch, that is the finding, and it belongs in `taxonomy/_failures/` before it
belongs in a fix.

### 3.3 Stage 3 -- classify, and record every failure

For each corpus entry the curator opens the primary source (paper, homepage, leaderboard rules) and
fills every facet. Three rules govern the pass:

1. **Source-bound.** A facet value is only permitted if the primary source supports it. "Obviously
   it tests planning" is not support.
2. **Abstention is a valid answer.** `null` plus a failure log entry is always better than a guess.
3. **Do not fix the taxonomy mid-pass.** Editing definitions while classifying contaminates the
   evidence -- you end up measuring the definitions you just wrote, not the ones you had. Log and
   move on. All revision happens in Stage 4.

Every failure is logged as a structured record, not a note:

```yaml
# taxonomy/_failures/2026-10-04-matbench-discovery-001.yaml
kind: missing-term            # missing-term | collision | two-primaries | undefined-boundary
                              # | escape-hatch-used | source-silent
facet: evaluation_method
benchmark: matbench-discovery
curator: "@curator-a"
date: 2026-10-04
description: >
  Matbench Discovery groups models into compliance tiers by what training data they were
  permitted to use. There is no facet that can express "this result is only comparable to
  results trained under the same data restriction". Tagged evaluation_method: domain-metric
  and lost the eligibility rule entirely.
proposed_term: null           # optional; a suggestion, not a decision
blocking: true                # true => v1 cannot freeze until this is resolved
```

A `blocking: true` failure means the taxonomy cannot freeze until an ADR resolves it. Everything else
is batched into the Stage 4 revision. A `collision` record whose two terms sit in *different* facet
files is not a defect. It is a homograph candidate, and it routes to `taxonomy/homographs.yaml` for a
declaration and a rationale, not to an ADR for a rename. The failure log stays in the repository permanently: it is the
provenance of the taxonomy and the single best input to every later revision (§9).

**Expected outcome, stated in advance so it can be checked.** Based on the stress-test analysis,
Stage 3 should produce on the order of 25-45 failure records, concentrated in `evaluation_method`
(composite and pass/fail-battery metrics), `ceiling_anchor_type` (anchors that are not human), and
the `robotics-embodiment`, `chemistry-materials`/`physics` boundary and `medicine-health` subdomain lists. If
Stage 3 produces fewer than ten failures, the pass was not adversarial enough and the sample should
be widened rather than the taxonomy declared correct.

---

## 4. The file format

One file per facet under `taxonomy/`, one YAML document with a small header and a `terms` list.
Files are parsed by the Pydantic schema layer ([04-data-model.md](04-data-model.md)) and every term
referenced anywhere in `data/` must resolve to a term here; an unresolved reference is a blocking CI
failure.

```yaml
# taxonomy/capabilities.yaml
facet: capability
facet_kind: flat                  # navigational | flat -- see 04 S16 FacetFile
version: 1.2.0                    # semver for this FILE; taxonomy/VERSION holds the aggregate
updated: 2026-11-03
description: >
  The underlying ability a benchmark is designed to isolate, independent of the domain it is
  situated in. Crossed with Domain, this facet produces the coverage matrix, which is why its
  terms must stay stable, mutually distinguishable, and applied sparingly.

terms:
  - id: long-horizon-execution
    label: Long-horizon execution
    status: active                # active | proposed | deprecated | retired
    introduced_in: 1.0.0
    source: own                   # own | helm | hf-tag | eee | inspect | ...
    definition: >
      The ability to carry a single task through many dependent steps, where an error at any
      step is not recoverable by the later steps and where the system must retain and act on
      state it generated itself earlier in the episode.
    inclusion_test: >
      Tag this if a single scored episode contains at least ~10 dependent actions AND failure
      at an intermediate step makes the final score unattainable.
    exclusion_test: >
      Do NOT tag this if the benchmark is scored per-item on independent items, however many
      items there are, or if the long sequence is produced in one generation without any
      environment feedback between steps.
    examples:
      - ref: osworld-2-0
        qualifies: true
        why: >
          A single GUI task runs for dozens of interdependent actions against live application
          state; an early misclick is unrecoverable.
      - ref: tau2-bench
        qualifies: true
        why: >
          Multi-turn tool-and-user interaction under a domain policy; the pass^k metric exists
          precisely because execution reliability over the whole episode is what is measured.
      - ref: humanitys-last-exam
        qualifies: false
        why: >
          NEAR MISS. Answers can be very long and involve extended chains of reasoning, but each
          of the 2,500 questions is scored independently and there is no environment state. Long
          output is not long horizon.
      - ref: mmlu-pro
        qualifies: false
        why: >
          NEAR MISS. Thousands of items, but they are independent multiple-choice questions.
          Benchmark size is not episode length.
    see_also: [planning, memory-retention, autonomy]
    not_to_be_confused_with:
      - term: planning
        distinction: >
          `planning` is about producing a correct sequence before or during acting;
          `long-horizon-execution` is about surviving the sequence. A benchmark that scores the
          plan but never executes it gets `planning` only.
      - term: memory-retention
        distinction: >
          `memory-retention` concerns information carried across episodes or across a long
          context; `long-horizon-execution` concerns state generated within one episode.

  - id: calibration-uncertainty
    label: Calibration and uncertainty
    status: active
    introduced_in: 1.0.0
    source: helm
    definition: >
      The ability to report how likely its own output is to be correct, such that the reported
      confidence matches the observed frequency of correctness.
    inclusion_test: >
      Tag this if the benchmark's scoring function consumes a confidence, a probability, a
      distribution or an interval emitted by the system under test.
    exclusion_test: >
      Do NOT tag this merely because accuracy is measured on hard items, and do NOT tag it when
      a third party computes calibration post hoc from logits the system did not intend as a
      confidence claim.
    examples:
      - ref: fair-universe-higgsml-uncertainty
        qualifies: true
        why: >
          Participants must emit confidence intervals on Higgs signal strength under systematic
          nuisance parameters; the metric is interval coverage and width, not accuracy.
      - ref: humanitys-last-exam
        qualifies: true
        why: >
          HLE reports calibration error alongside accuracy as a first-class published number.
      - ref: gpqa-diamond
        qualifies: false
        why: >
          NEAR MISS. Graduate-level difficulty and a known chance baseline, but the score is
          plain accuracy; no confidence is elicited or scored.
```

Domain terms carry two extra fields because the domain facet is the navigational spine and has two
levels. **The id form below is normative, not illustrative:** a subdomain id is always
`{parent}/{leaf}`, the leaf is unique across the entire file, and a bare family id is a navigational
node that is never assignable to `domain.primary`. CI check 9c asserts all three
([05-repository-and-workflow.md](05-repository-and-workflow.md) §9; the unassignability of a bare
family is enforced at Tier 2 referential validation in [04-data-model.md](04-data-model.md)).

```yaml
# taxonomy/domains.yaml (excerpt)
  - id: robotics-embodiment/sim2real-transfer
    label: Sim-to-real transfer
    parent: robotics-embodiment
    status: active
    introduced_in: 1.0.0
    source: own
    definition: >
      Benchmarks whose scored quantity is the degradation, or preservation, of performance when
      a policy trained or validated in simulation is executed on physical hardware.
    inclusion_test: >
      Tag as PRIMARY only if both a simulated and a physical evaluation are part of the defined
      protocol and the comparison between them is what is reported.
    exclusion_test: >
      Do NOT tag a purely simulated benchmark that merely aspires to real-world relevance, and
      do NOT tag a purely physical trial with no simulated counterpart.
    examples:
      - ref: simplerenv
        qualifies: true
        why: Built explicitly so simulated outcomes correlate with real-robot outcomes.
      - ref: robosyn-challenge-2026
        qualifies: true
        why: Sim-synthesised manipulation skills are transferred to real-world dexterity.
      - ref: libero
        qualifies: false
        why: >
          NEAR MISS. 130 manipulation tasks, widely used, but entirely in simulation with no
          physical arm in the protocol. Simulation alone is `manipulation`, not `sim2real`.
      - ref: a2rl-drone-championship
        qualifies: false
        why: >
          NEAR MISS. Fully physical racing with no simulated leg in the scored protocol.
          Physical alone is `drone-uav` + evaluation_method `physical-trial`.
```

Three supporting files complete the directory:

- `taxonomy/retired-ids.yaml` -- the never-reuse ledger. An ID that has ever been published is never
  reassigned to a different meaning, because external citations and forks resolve IDs, not labels.
- `taxonomy/homographs.yaml` -- declared collisions between a capability id and a subdomain leaf.
  Permitted, but each carries a rationale, and CI checks 9d and 9e enforce both the declaration and
  the coverage-cell consequence. See `_workflow/decisions/D3-vocabulary-namespacing.md`.
- `taxonomy/VERSION` -- the aggregate semantic version stamped into every build artifact (§10).

**The definitions are published.** `/taxonomy/<facet>/<term>` renders the definition, both tests,
every example including the near-misses, and the list of entries currently carrying the term. This is
not documentation politeness: a taxonomy nobody can read is a taxonomy nobody can apply consistently,
and an outside contributor who cannot see the exclusion test will re-derive their own. It is also the
cheapest possible demonstration to a domain reviewer that the project takes their field seriously.

---

## 5. Definition quality rules

A term is not admissible until it has all four of the following. CI enforces each one mechanically.

| Requirement | Rule | Why |
| --- | --- | --- |
| **Definition** | One sentence, present tense, naming the thing being measured. No examples inside it. | A definition that needs a paragraph is usually two terms |
| **Inclusion test** | An operational "tag this if…" a curator can apply in under a minute without domain expertise | Definitions describe; tests decide. Curators apply tests |
| **Exclusion test** | An operational "do NOT tag this if…" | Most misclassification is over-application, so the exclusion test does more work than the inclusion test |
| **≥ 2 examples, ≥ 1 of them a near-miss with `qualifies: false`** | A near-miss is an entry a reasonable person would tag with this term and which does not qualify, with the reason stated | This is the single highest-value line in the whole file |

**What these four rules cost, and a warning about the estimate that sizes them.**
[02-taxonomy.md](02-taxonomy.md) §14 sizes the full definition-authoring pass at 40-110 person-hours
for 446 term records, at 6-20 minutes per spine term and 4-10 minutes per subdomain term, and hands
that figure to [14-roadmap.md](14-roadmap.md) §"Effort sizing" to absorb. Read that rate against the
table above before planning against it: it was derived from the one-line definitions already written
in `02` §4.2, whereas this section requires **four artifacts per term**, one of which is a near-miss
with a stated reason. Four minutes does not produce a near-miss for
`chemistry-materials/crystal-structure-prediction`. The honest reading is that 40-110 h is a floor
for the Phase-0 spine slice and optimistic for the long tail, and the mitigation is the split
[02-taxonomy.md](02-taxonomy.md) §14 owns: **the 204 subdomain terms get a definition and
`status: proposed` at Phase 0, and their `examples[]` are drawn from catalogued entries in Phase 1**,
because a near-miss example for a subdomain requires a corpus that does not yet exist. `02` §14
carries the hours for each half; this section does not restate them. Do not plan the full 446 into
Phase 0.

Near-misses deserve the emphasis. Positive examples teach almost nothing -- a curator who is about to
mis-tag something is, by definition, already convinced it fits. The boundary is where drift happens,
and a stated boundary case is the only artifact that stops it. The `not_to_be_confused_with` block
does the same job for term-versus-term confusion, and every pair that appears twice in the failure
log should get one.

Additional constraints:

- **No term whose definition is "other", "general", "misc" or "multi-".** Those are abstentions
  wearing a term's clothes, and they are invisible to the coverage matrix in exactly the way a `null`
  is not. Use `null` plus a failure record.
- **No term that can only be applied by reading another term's definition first**, unless the
  relationship is declared in `not_to_be_confused_with`.
- **A term introduced to describe exactly one benchmark is a red flag**, not automatically wrong --
  `wet-lab-validation` was worth having when only CACHE needed it -- but the ADR must argue why the
  category will recur.
- **Definitions are versioned prose.** Changing a definition's meaning is a MINOR or MAJOR version
  bump and requires an ADR; fixing a typo is a PATCH (§10).

---

## 6. Inter-rater reliability

This is the step every taxonomy plan skips, and skipping it is why taxonomies rot invisibly: nobody
finds out the vocabulary is ambiguous until a year of data has been tagged inconsistently and the
coverage matrix is quietly wrong.

### 6.1 The protocol

Cheap, concrete, repeatable:

1. Draw **30 benchmarks** from the stress corpus, stratified so every domain family *present in that
   corpus* appears at least once -- that is 18 of the 19 families, `engineering-design` having no
   surveyed candidates until Phase 0 (§3.2) -- and at least 6 of the 10 stress-tests are included.
2. **Two raters classify independently**, from primary sources, with no discussion, using only the
   published definitions. Neither sees the other's answers.
3. Compute agreement **per facet**, not overall. An aggregate number hides the one broken facet,
   which is the only thing you are trying to find.
4. Produce the **disagreement list**: every item × facet where the two differ, with both values.
5. Every disagreement is triaged as a **definition defect** unless a reviewer can point to the exact
   sentence in the inclusion or exclusion test that the losing rater failed to apply. The default
   attribution is to the definition, not the rater -- because the raters are proxies for hundreds of
   future contributors who will have even less context.
6. Fix the definitions, not the data. Re-run only the affected facet.

### 6.2 Which statistic, and why

With n = 30 the choice matters more than it usually does.

| Facet kind | Statistic | Threshold | Reason |
| --- | --- | --- | --- |
| Single-valued (primary domain, lifecycle, access, refresh, contamination_risk, ceiling_anchor_type, reproducibility_tier) | **Raw percentage agreement as the headline**, Cohen's κ reported alongside with its 95% CI | ≥ 0.85 raw; κ ≥ 0.70 | κ is the statistically respectable choice but it is unstable at n = 30 over a facet with this many categories -- primary domain alone has 204 assignable values, since a primary domain is a subdomain and not a family ([02-taxonomy.md](02-taxonomy.md) §3) -- and it suffers the prevalence paradox: on a facet where 80% of entries are `active`, high raw agreement can produce an alarming κ purely from marginal skew. Publishing raw agreement as the headline with κ as a caveat is more honest than either alone |
| Multi-valued (capability, evaluation_method, secondary domains, subject_under_test, independence_flags) | **Mean per-item Jaccard index**, plus per-term F1 treating one rater as reference | ≥ 0.65 mean Jaccard; no term below 0.50 F1 | κ is undefined for multi-label sets without arbitrary binarisation. Jaccard is interpretable ("the raters agreed on two-thirds of the tags they used between them") and the per-term F1 localises the fault to a specific term, which is what you actually need |

Any facet below threshold is treated as **failing** and blocks the taxonomy freeze. Any *individual
term* below 0.50 per-term F1 is flagged for an ADR even if its facet passes overall -- one broken term
in an otherwise sound facet is the common case, and the aggregate will hide it.

Two scope notes, because these thresholds get quoted out of context. First, the **≥ 0.85 raw
agreement bar belongs to single-valued facets only** and does not apply to capability: capability is
multi-valued, so its bar is the second row's -- ≥ 0.65 mean Jaccard with no term below 0.50 F1.
Quoting the 0.85 figure at a multi-valued facet sets a bar no multi-label task meets and invites the
wrong conclusion that the vocabulary failed. Second, the **capability-group axis is derived, never
hand-tagged**: curators tag terms and the rollup to the 13 groups in
[02-taxonomy.md](02-taxonomy.md) §4.3 is computed, so groups are not rated and carry no agreement
figure of their own. Reporting one would be flattering and meaningless -- group-level agreement
exceeds term-level agreement by construction, because a mis-tag inside a group survives the collapse
and lands in the right coarse cell anyway. Per-term F1 measured *after* the rollup exists is the
number that localises the fault, and a group-level confusion matrix alongside it is what catches a
systematic bias in one high-base-rate term before it propagates into a whole published column.

### 6.3 When it re-runs

- **At v1.0.0 freeze** (Stage 5) -- blocking.
- **After any ADR that touches ≥ 3 terms in a facet, or any split** -- re-run that facet only,
  15 items, blocking before the migration merges.
- **Annually**, full 30-item run, published with the release DOI.
- **On first entry into a new domain family** -- e.g. if a Phase 3 expansion opens a `neuroscience`
  family, run that family's subdomain list against 10 entries before curating at volume.

The annual run is the one that gets skipped. Put it in the release checklist in
[14-roadmap.md](14-roadmap.md), not in someone's memory.

### 6.4 The second-rater problem, honestly

With a one-to-two-person team, "two independent raters" is often not available. There are three
options and they are not equivalent.

**Option A -- an outside human volunteer.** Best evidence, hardest to schedule. A domain reviewer
(§11) is the natural candidate: their 30-item pass doubles as the IRR run for their family. Cost: one
to two hours of someone else's time, plus coordination.

**Option B -- an LLM as second rater.** Cheap, instant, repeatable, and available for every facet on
demand.

The case *for*: the task is slot-filling into closed enums with published definitions and constrained
decoding -- closer to multi-label intent classification than to open-ended judgement. A model
disagreeing with a human is genuinely diagnostic: if a competent reader of the published definitions
lands somewhere else, the definition is probably underspecified, which is precisely the defect the
protocol exists to find. And an LLM rater can be re-run over the entire corpus after every definition
change, which no human can, giving a continuous drift signal instead of an annual snapshot.

The case *against*: three biases make an LLM-derived agreement number weaker than it looks. (i)
**Self-preference / shared-prior bias** -- if the same model family drafted the entries, human-LLM
agreement partly measures the model agreeing with itself, and ensembling or order-reversal fixes
variance but not biases shared across the judge population. (ii) **Prior contamination** -- a model
has strong opinions about what "reasoning" means that come from its training data, not from our
definitions, so it can agree with a human for the wrong reason and mask an ambiguous definition.
(iii) **It is not evidence about humans**, and IRR's entire purpose is to predict whether future human
contributors will apply the vocabulary consistently.

**Recommendation.** Use both, with different jobs and different names.

- **`irr_human`** -- the published, citable number. At least one human-human round per year, plus the
  blocking round at v1.0.0 freeze. This is what appears in the release notes and the DOI'd data.
- **`taxonomy_drift_check`** -- an LLM second-rater run, executed in CI over the whole corpus after
  every vocabulary-changing ADR and monthly thereafter. It is a **defect detector, never a quality
  claim**. Its output is a ranked list of terms where the model and the stored value disagree most
  often; those terms get definition review.
- Constraints on the drift check, carried over from the AI-layer guardrails in
  [11-ai-features.md](11-ai-features.md): the rater model must be from a **different family than the
  model used for drafting**, its outputs are never written to `data/`, the prompt contains only the
  published definitions and the primary-source text (never the existing tags), and item and option
  order is randomised on every run.
- **Never report an LLM-LLM agreement figure.** Two models from the same lineage agreeing tells you
  nothing about the definition and everything about the lineage.

The failure mode being avoided: publishing "inter-rater agreement 0.91" where both raters were
language models, which is the kind of unsourced confidence the project exists to oppose.

### 6.5 Who the human second rater actually is, and when they are asked

The protocol above, the ≥0.85 agreement gate and the blocking round at the v1.0.0 freeze all depend
on a person who does not exist yet, has no recruitment owner and no lead time. That is the shape of
dependency that fails silently at the worst moment — the freeze — so it is named here with a
recommendation rather than left to §12's reviewer programme, which is a *different* ask (a 30-item
domain pass, from someone who need not have read the vocabulary at all).

**The recommendation: the first human second rater is the first recruited domain reviewer, asked at
recruitment time rather than at freeze time.** Concretely:

- **Owner.** The same person who runs the reviewer outreach in §12 and
  [14-roadmap.md](14-roadmap.md)'s recruitment block. This is one extra sentence in an email already
  being sent, not a second programme.
- **The ask, stated in the recruitment email.** "Two asks, not one: a 30-item pass over your family's
  entries, and a 40-item blind re-classification against the published definitions. The second takes
  about ninety minutes and is what lets us publish an agreement number that is about humans." Asking
  for both up front costs nothing; asking for the second one later costs a whole second round of
  outreach at the point where the freeze is already blocked.
- **Lead time.** Eight weeks from first contact, on the outreach programme's own observed pattern of
  slow academic reply cycles. The freeze round must therefore be initiated **two months before** the
  v1.0.0 freeze date, which puts it in the middle of Stage 3, not at Stage 5.
- **Effort.** 2–4 hours of our time per round (drawing the sample, preparing the blind instrument,
  computing the statistic, writing up the disagreements) plus 1.5–2 hours of theirs. It belongs in
  [14-roadmap.md](14-roadmap.md)'s reviewer-liaison row rather than as a new line.
- **The fallback, pre-committed, because this is the dependency most likely to fail.** If no human
  rater is secured by the freeze date, **the freeze proceeds and the release publishes
  `irr_human: null` with the reason and the date**, alongside the `taxonomy_drift_check` figure
  clearly labelled as an LLM-vs-stored-value defect count and explicitly *not* an agreement
  statistic. Shipping without the number is recoverable; shipping an LLM-LLM figure under the name
  "inter-rater agreement" is not, because it will be quoted back at the project forever.

This is the same posture [00-vision-and-scope.md](00-vision-and-scope.md) §7.3 takes toward reviewer
dependence generally: an unanswered email costs a visible `null` and a badge, never a schedule slip
and never a fabricated number.

---

## 7. AI-assisted classification, and its strict limits

AI assistance is expected and necessary -- the canonical seed target of 320 entries
([02-taxonomy.md](02-taxonomy.md) §3), at the planning rate of 30-90 minutes per entry with the ten
stress cases at 2-3 hours, is **175-495 person-hours**, and that number only works with drafting
help. (The rate is an estimate from the domain reconnaissance, never a measurement;
[14-roadmap.md](14-roadmap.md) §"Effort sizing" owns it and carries the checkpoint that will replace
it with a measurement.) The rule is narrow and
absolute.

> **A model may PROPOSE facet assignments. An assignment is not valid until a human has confirmed it
> against the primary source.** Proposals live in `curation.verification_status:
> ai-drafted-unverified`, are excluded from the published build entirely, and a human promotes them
> only after opening each cited source and confirming each field against it.

This mirrors the general drafting rule in [05-repository-and-workflow.md](05-repository-and-workflow.md),
but the taxonomy case is stricter, and the reason is specific to this project.

### 7.1 Why over-tagging is catastrophic here

The coverage matrix is domain × capability, at two resolutions. The grid that publishes gap claims is
the coarse one: **19 domain families × 13 capability groups = 247 cells**, the groups being the
partition of the 44 capability terms enumerated in [02-taxonomy.md](02-taxonomy.md) §4.3. The
drill-down grid is the full one, **204 (family, subdomain) pairs × 44 terms = 8,976 cells**; both
figures and the rule that only the coarse grid publishes belong to
[12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1. In either grid the product is not the
filled cells -- every catalogue has those -- it is the **empty ones**.

"Nobody is measuring X" is the claim nobody else in the landscape can make, and the
recon confirms several are genuinely publishable on day one: phylogenetics has no standing benchmark;
education and tutoring have no public leaderboard, only learning-gain RCTs; human-comparison
psychometric batteries have no canonical benchmark; retrosynthesis has a canonical dataset
(USPTO-50k) but no canonical leaderboard, which is why 2026 papers report mutually inconsistent top-1
numbers on the same 5,007-reaction test set.

Now do the arithmetic. At 1,500 benchmarks, a human curator applying the exclusion tests will average
roughly 2-3 capability tags per benchmark (the ten adversarially chosen stress cases in
[02-taxonomy.md](02-taxonomy.md) §12 average 4.2 terms, which is the high end by construction --
they were selected to break the vocabulary, not to represent it). A model asked "which capabilities
does this benchmark test?" will cheerfully return 8, because every benchmark plausibly touches
reasoning, knowledge, instruction-following and robustness. That is 1,500 × 5 = **7,500 spurious
tag-instances**. Rolled up onto the 247-cell coarse grid that is **about thirty per cell**, so every
coarse cell fills and the one axis licensed to publish gap claims goes uniformly dense. On the
8,976-cell fine grid the same excess is only 0.84 per cell, which sounds survivable and is not:
spurious tags concentrate in the half-dozen most generic terms rather than spreading, so the fine
grid also fills exactly where the interesting emptiness was. The gap analysis returns "everything is
covered", which is both false and useless, and it is false in a way that is almost impossible to
detect after the fact because each individual tag looks defensible.

Under-tagging produces a visible, fixable hole. Over-tagging produces an invisible, confident lie.
The bias must be deliberate and it must be toward silence.

There is a symmetric obligation on the other side of the same matrix, and it is a hard dependency of
the coarse grid rather than a nicety: **every coarse cell must be triaged as applicable or not
applicable before any gap claim publishes.** The triage is taxonomy work, it belongs to this
document's process, and it is one editorial judgement per cell across 247 cells -- an hour or two,
batched by row. Skipping it manufactures roughly twenty false gaps on day one, because
`autonomy-and-oversight` and `conduct-and-cooperation` read near-empty across physics,
chemistry-materials, biology-genetics, earth-climate and engineering-design for structural reasons
rather than as findings, and those are the rows a specialist reviewer opens first. The triage is
**not** a blanket by column: autonomous laboratories make chemistry-materials × autonomy-and-oversight
a live and informative cell, and declaring it inapplicable would itself be the error. A cell declared
not-applicable carries the declaring curator, the date and a one-line reason, exactly like a failure
record, so the declaration is auditable and reversible when a field moves. This is the mechanism
[12-analytics-and-trends.md](12-analytics-and-trends.md) §5.4 depends on to separate its three kinds
of empty.

### 7.2 The rules that enforce it

1. **One term, one quote.** A proposed capability or evaluation-method tag must carry
   `evidence.quote` (a verbatim span from the primary source) and `evidence.source_id`. No quote, no
   tag. This single rule removes most model over-tagging mechanically, because the model cannot find
   a sentence in the CASP17 assessment paper that says it tests analogical reasoning.
2. **Forced abstention.** The extraction prompt explicitly instructs the model that returning an
   empty list is the correct answer when the source does not support a tag, and the prompt is
   evaluated on a golden set for abstention rate, not just accuracy.
3. **Tag-density CI gate.** The build computes mean tags-per-entry per facet. A pull request that
   raises the corpus-wide mean capability tag count above **3.5** fails CI and requires a human
   override with a written reason. The threshold is a tripwire, not a truth; it exists to make a
   drift event loud.
4. **Facet-specific soft caps.** `capability` ≤ 5, `evaluation_method` ≤ 4, secondary domains ≤ 3.
   Exceeding a cap is permitted with a one-line justification field -- WeatherBench 2 and Matbench
   Discovery legitimately need more -- but it must be typed by a human.
5. **Primary domain is never model-assigned.** It is the navigational spine, it drives the Atlas
   clustering, and it is exactly one value. A human picks it.
6. **The model never invents a term.** Constrained decoding over the closed enum only. If nothing
   fits, the model's correct output is a `missing-term` failure record (§3.3), which then feeds the
   ADR process -- turning the model into a useful proposer of vocabulary gaps without letting it
   author vocabulary.

Rule 6 is the productive inversion: the model is bad at deciding which of 44 capabilities apply, and
genuinely good at noticing that none of them do. Point it at the second job.

---

## 8. Governance: the ADR process

After the v1.0.0 freeze, the vocabulary is closed. Every change is an Architecture Decision Record in
`adr/`, numbered, immutable once merged, and superseded rather than edited.

### 8.1 Change types and requirements

| Change | Version impact | Migration script | Reviewers | IRR re-run |
| --- | --- | --- | --- | --- |
| **Add** a term | MINOR | Not required (nothing to migrate) | 2 | Only if the facet already fails threshold |
| **Redefine** a term (meaning changes) | MINOR | Required if any existing entry's correctness changes | 2 | Yes, that facet |
| **Edit** definition prose (no meaning change) | PATCH | No | 1 | No |
| **Merge** two terms | MAJOR | Required; mechanical and safe | 2 | Yes, that facet |
| **Split** a term | MAJOR | Required; **cannot be automatic** (§9) | 2 + a domain reviewer where one exists | Yes, that facet, blocking |
| **Deprecate** a term (still readable, not assignable) | MINOR | Required if any entry still uses it | 2 | No |
| **Retire** a term (removed; ID goes to `retired-ids.yaml`) | MAJOR | Required; corpus must contain zero uses | 2 | No |
| **Rename a label** (ID unchanged) | PATCH | No | 1 | No |
| **Rename a term *id*** | Before the v1.0.0 freeze: PATCH, no ledger entry. After: this is a **Retire + Add** -- MAJOR, old id appended to `retired-ids.yaml`, corpus migration required | Required after the freeze | 2 | Yes, that facet, after the freeze |

Note the asymmetry: adding is cheap, removing is expensive. That is correct -- the cost of a
redundant term is a slightly noisier filter, and the cost of removing a term in use is every external
citation to a coverage figure computed with it. The id-rename row matters for the same reason and is
easy to miss: without it the table appears to say ids can never be renamed at all, when in fact a
rename is free until the freeze and a MAJOR retire-plus-add afterwards. That asymmetry is why
`games-planning/puzzle-solving` could be renamed to `games-planning/puzzle-games` at no cost in
2026-09 (`_workflow/decisions/D3-vocabulary-namespacing.md`) and could not have been a year later.

### 8.2 The ADR template

Every figure in the worked example below is **hypothetical** — a plausible future state written to
show the template doing its job, not a plan figure. In particular the 118 robotics entries it assumes
are roughly five times the family's seed target of 25 ([02-taxonomy.md](02-taxonomy.md) §3), because
a split ADR only becomes necessary once a family is large enough for one term to dominate it. Do not
quote any number from this block.

```markdown
# ADR-0027 -- Split `robotics-embodiment/manipulation`

- **Status:** Accepted
- **Date:** 2026-11-14
- **Taxonomy version:** 1.2.0 -> 2.0.0
- **Facet:** domain
- **Change type:** split
- **Supersedes:** --
- **Superseded by:** --

## Context

`manipulation` carries 41 of 118 robotics entries -- 35% of the family, well above the
25% non-discrimination threshold in the taxonomy health report. The failure log contains 6
`undefined-boundary` records against it since v1.0.0 (2026-10-11 RoboTwin 2.0, 2026-10-19
BEHAVIOR Challenge, 2026-11-02 RoboCasa GR1, ...). Independent evidence that the distinction is
real and field-recognised: RoboTwin 2.0 defines itself as bimanual across 5 embodiments; BEHAVIOR
is explicitly mobile manipulation across 7 scenes; LIBERO is fixed-base tabletop. The per-term F1
for `manipulation` in the 2026-11 IRR run was 0.48, below the 0.50 term floor.

## Decision

Split `manipulation` into:
- `manipulation-tabletop` -- fixed-base, single-arm, workspace-bounded
- `bimanual-manipulation` -- two coordinated arms as a defined requirement of the task set
- `mobile-manipulation` -- locomotion and manipulation scored in one episode (already exists;
  its definition is tightened, not created)

`manipulation` is deprecated, not retired: it remains resolvable for citations to coverage
figures computed under v1.x.

## Consequences

- 41 entries require re-adjudication. The migration maps all of them to
  `__NEEDS_REVIEW__:manipulation` and opens one tracking issue; CI blocks publication of any
  entry still carrying the sentinel.
- Coverage figures for `robotics-embodiment` are not comparable across the v1/v2 boundary.
  The `/coverage` page will show the taxonomy version and a boundary marker on the time series.
- `dexterous-manipulation` is untouched; it remains orthogonal (it describes the end-effector
  requirement, not the base or arm count) and its `not_to_be_confused_with` gains an entry.

## Alternatives considered

- **Do nothing.** Rejected: 35% prevalence means the term no longer discriminates, and the
  coverage matrix cannot show that nobody benchmarks bimanual mobile manipulation, which is a
  publishable gap.
- **Add a separate `arm_count` field instead.** Rejected: it would apply only to robotics and
  the facets are meant to be cross-domain. Recorded in [15-open-questions.md](15-open-questions.md)
  as a candidate for a future domain-specific extension block.

## Migration

`migrations/0027_split_manipulation.py`. Dry-run output attached to the PR.

## Evidence

- taxonomy/_failures/2026-10-11-robotwin-002.yaml (and 5 others, listed)
- IRR run 2026-11: reports/irr/2026-11-domain.json
- Health report 2026-11: reports/taxonomy-health/2026-11.json
```

### 8.3 The deliberate friction, and its release valve

Two reviewers plus a migration script plus an IRR re-run is heavy for adding one word. That is the
point. An open vocabulary degrades into synonyms within months -- someone adds `agentic-reasoning`
alongside `long-horizon-execution`, both get used, neither is wrong, and the coverage matrix now
reports two half-populated cells where there should be one populated cell. Nobody notices for a year.
By then the fix is a re-adjudication of every entry that touched either term.

But friction that reaches the *contributor* is what killed llm-leaderboard. The resolution is that
the friction is entirely internal:

- **Anyone can propose a term through a GitHub issue form** -- benchmark, facet, why the existing
  terms do not fit, a source. No git, no YAML, no PR. A validation bot checks the form, looks for
  near-duplicates among existing terms and their `see_also` graphs, and files the proposal into
  `taxonomy/_proposed/`. This is modelled directly on UK AISI's `inspect_evals` `/register/` flow
  (launched 2026-05-08: GitHub issue submission, bot validates and derives metadata, auto-PR), which
  is the closest institutional analogue to this project's curation model and is MIT-licensed.
- **Proposals are batched and adjudicated quarterly**, except `blocking: true` failures, which are
  handled immediately. Batching is what makes the ceremony affordable: one IRR run and one migration
  per quarter instead of per term.
- **Every proposal gets a written answer**, accepted or not, and rejections are kept. A rejected
  proposal with a reason is a `not_to_be_confused_with` entry waiting to be written.

---

## 9. Term lifecycle and migration

Every vocabulary-changing ADR ships a migration script in `migrations/`, and the migration lands in
**the same commit** as the taxonomy change. A taxonomy edit that leaves the corpus invalid, even for
one commit, breaks `git checkout <sha> && bench validate`, which is the guarantee that makes the data
citable at a hash.

### 9.1 The rule that matters: merges are mechanical, splits are not

A **merge** is a deterministic rewrite: every occurrence of B becomes A, duplicates are collapsed,
done. A script can do it correctly and CI can verify it.

A **split** cannot be automated, and pretending otherwise is the most common way a taxonomy silently
corrupts itself. If `manipulation` becomes three terms, no rule can decide which of the 41 existing
entries is tabletop and which is bimanual without re-reading each primary source. A script that
guesses -- by keyword, by heuristic, by model -- produces 41 confident, unsourced, plausible
assignments, which is exactly the failure this project exists to oppose.

So a split migration writes a **sentinel**:

```python
# migrations/0027_split_manipulation.py
"""ADR-0027: split robotics-embodiment/manipulation.

Merges are mechanical. Splits are NOT: this migration deliberately refuses to guess.
It writes a sentinel that CI treats as a publication blocker, so the corpus stays valid
(schema-wise) while every affected entry is re-adjudicated against its primary source.
"""
from pathlib import Path
import ruamel.yaml

yaml = ruamel.yaml.YAML()          # round-trip: preserves comments and key order
OLD = "robotics-embodiment/manipulation"
SENTINEL = "__NEEDS_REVIEW__:robotics-embodiment/manipulation"

def migrate(root: Path, dry_run: bool = True) -> dict:
    touched, report = [], {"primary": 0, "secondary": 0}
    for path in (root / "data" / "benchmarks").rglob("*.yaml"):
        doc = yaml.load(path)
        changed = False
        if doc.get("domain_primary") == OLD:
            doc["domain_primary"] = SENTINEL
            report["primary"] += 1
            changed = True
        secondaries = doc.get("domain_secondary") or []
        if OLD in secondaries:
            doc["domain_secondary"] = [SENTINEL if d == OLD else d for d in secondaries]
            report["secondary"] += 1
            changed = True
        if changed:
            touched.append(path)
            if not dry_run:
                yaml.dump(doc, path)
    report["files"] = len(touched)
    report["paths"] = [str(p) for p in touched]
    return report
```

Then:

```
bench migrate 0027 --dry-run     # report only; the dry-run output is attached to the ADR's PR
bench migrate 0027 --apply
bench validate --tier all        # full-corpus revalidation, blocking
bench report taxonomy-health     # confirms the split actually improved discrimination
```

CI rules around sentinels:

- A sentinel is **schema-valid** (so `bench validate --tier schema` passes and the repo is never
  broken) but **publication-blocking** (the build refuses to emit an entry carrying one). The entry
  stays in git, disappears from the site, and returns when a human re-adjudicates it.
- The migration opens one tracking issue listing every affected file, with the count.
- A sentinel older than **60 days** escalates to a CI failure on `main`, not just a build exclusion.
  Sentinels that live forever are how a "temporary" review queue becomes permanent data loss.

### 9.2 Deprecate versus retire

`deprecated` terms remain resolvable and renderable but cannot be assigned to new entries; the term
page shows the deprecation notice and points at `deprecated_by`. `retired` terms are removed from the
facet file and their IDs are appended to `taxonomy/retired-ids.yaml`, never to be reused for a
different meaning. Reusing an ID is the one genuinely unrecoverable mistake available here: an
external fork or a citation resolves the ID, and a silently-redefined ID turns someone else's correct
analysis into a wrong one with no diff to point at.

---

## 10. Versioning the taxonomy itself

`taxonomy/VERSION` carries a semantic version. It is not decoration -- it is what makes a coverage
figure citable.

| Bump | Trigger |
| --- | --- |
| **MAJOR** | Any change that can invalidate a previously published analysis: split, merge, retire, or a redefinition that changes which entries qualify |
| **MINOR** | Additive and definition-tightening changes: new term, deprecation, new examples that change nothing already tagged |
| **PATCH** | Prose, typos, labels, `see_also` links -- anything a machine reading the corpus cannot observe |

Rules:

1. **Every derived artifact records the taxonomy version that produced it.** `coverage.json`,
   `atlas.json`, the saturation series and every published metric carry `taxonomy_version` and the
   data commit SHA. A coverage percentage without a taxonomy version is not a fact; it is a number
   with no referent.
2. **The site shows it.** The `/coverage` page header reads *"Computed under taxonomy v2.1.0 at
   commit `a4f19c3`, 2026-11-14"*, and time-series charts draw a boundary marker at every MAJOR
   bump, with a tooltip naming the ADR. A jump in a coverage series that is actually a taxonomy split
   must never look like a change in the world.
3. **Releases are tagged and DOI'd.** `taxonomy-v2.1.0` is a git tag; the quarterly data release that
   carries it gets a DOI ([08-infrastructure-and-build.md](08-infrastructure-and-build.md)). This is
   part of the survival story: Stanford CRFM's Ecosystem Graphs -- the same architecture as this
   project, from a far better-resourced lab -- went stale after 2025-01-24 with **no licence at all**,
   which made rescue-by-fork impossible while it continued to be cited as a data source 20 months
   out of date. CC-BY plus a versioned, DOI'd release is what makes our failure survivable.
4. **A compatibility note ships with every MAJOR.** One table: old term → new term(s) → whether the
   mapping is 1:1, 1:N (re-adjudication required) or N:1. Downstream users of the CC-BY data need
   this, and writing it is also the last chance to notice that the split was a bad idea.

---

## 11. Measuring taxonomy health

Published at `/taxonomy/health`, regenerated on every build, and part of the quarterly release notes.
Publishing it is deliberate: a catalogue that publishes its own vocabulary's weak points is making a
credibility claim no competitor in this landscape currently makes.

| Metric | Formula | Healthy range | Action when out of range |
| --- | --- | --- | --- |
| **Term usage count** | entries carrying term ÷ entries eligible for the facet | 1%-25% | **0 uses after two quarters:** the term describes nothing real -- deprecate, or the failure log should say why it is kept. **> 25% of the facet:** the term is not discriminating -- candidate for a split |
| **Facet fill rate** | entries with ≥ 1 non-null value ÷ all entries | > 90% for domain, lifecycle, access; > 60% for capability, evaluation_method | Low fill on a required facet means the facet is too hard to apply or the ingest path is not populating it |
| **Unmet-term rate** | `missing-term` failure records per 100 entries curated, trailing quarter | < 3 | Rising rate is the leading indicator that the vocabulary is falling behind the field. **This is the highest-signal number in the table** |
| **Co-occurrence ratio** | P(A and B) ÷ P(A or B) for every term pair in a facet | < 0.7 | Two terms that co-occur on 70%+ of the entries using either are functionally one term -- merge candidate |
| **Per-term IRR F1** | from the last IRR run (§6) | ≥ 0.50 | Below floor: definition defect, ADR required regardless of facet-level pass |
| **Tag density** | mean terms per entry per facet | capability 2.0-3.5; evaluation_method 1.0-2.5 | Above range is the over-tagging signature (§7.1); below range on a mature corpus suggests curators are avoiding a confusing facet |
| **Orphan rate** | terms with no `examples` referencing a live entry | 0 | Every term should be able to point at something real; if it cannot, its examples are aspirational |
| **Term churn** | terms added + deprecated + split, trailing year ÷ total terms | < 15%/yr after v1 | High churn means v1 froze too early; near-zero churn for two years in a field this fast probably means nobody is logging failures |

The unmet-term rate deserves its emphasis. It only exists if curators log the event, and curators only
log it if logging costs nothing. So it must be a single command:

```
bench tag-gap --benchmark robotwin-2-0 --facet domain \
  --note "bimanual dual-arm is not expressible; manipulation is too coarse"
```

That writes a `taxonomy/_failures/` record with the date, the curator, the benchmark and the facet,
and nothing else is required. Anything heavier -- a form, a discussion, an issue -- and curators will
silently pick the nearest wrong term instead, which is exactly the outcome the metric exists to
prevent.

---

## 12. The domain expert review programme

The taxonomy cannot be validated from inside the team for the domains that matter most. One hour from
a practising roboticist is worth more than a week of the curators' reading, and the recon is explicit
about the bar: **below roughly 15 entries per family a specialist will spot the gaps immediately**.
Fifteen is therefore the credibility target every family reaches by v1.x, not the launch gate -- the
launch gate is 12, and 18 for the seven Core families ([02-taxonomy.md](02-taxonomy.md) §3). The Core
families are seeded at 18-25 precisely so a reviewer from one of those fields can scan it and say
"yes, you got my field right"; the ingest-then-verify families launch at 12-16 and are knowingly below
the credibility bar.

### 12.1 Who to approach, in priority order

| Priority | Domain | Why it needs an outside reviewer | Where the reviewers are (from recon:domains) |
| --- | --- | --- | --- |
| 1 | **Robotics & embodiment** | Largest unindexed field; curation difficulty rated *very high*; the result is dominated by simulator and build version; ~40+ new named manipulation benchmarks per year, most dead within 18 months | CoRL, RSS, ICRA/IROS, CVPR Embodied AI Workshop. Stanford SVL, UT Austin RobIn, Berkeley RAIL, NVIDIA GEAR, Physical Intelligence, TRI, HKU/Shanghai AI Lab (RoboTwin), Tübingen/Geiger (driving) |
| 2 | **Biology & genetics** | *Very high* difficulty; CASP/CAFA/CAGI/DREAM alone decompose into 100+ children, so the family/child counting convention lives or dies here | ISMB/ECCB, RECOMB, MLCB, CZI Virtual Cells. Protein Structure Prediction Center (UC Davis), Marks Lab + OATML, Arc Institute, EMBL-EBI |
| 3 | **Chemistry & materials** | Wet-lab and DFT level-of-theory are conditions our LLM-shaped schema has no instinct for; Matbench Discovery's training-data compliance tiers break the comparability key | NeurIPS AI4Science, ICLR MLDD, ACS CINF, RSC *Digital Discovery*. Meta FAIR Chemistry, Materials Project (LBNL), Cambridge (Riebesell), CACHE/SGC Toronto, CCDC |
| 4 | **Medicine & health** | Highest raw volume (~700+ families); grand-challenge.org alone hosts 264 medical-imaging challenges; gated data everywhere, so the `access` facet gets its hardest test | MICCAI, CHIL, ML4H, *NEJM AI*, RSNA. Stanford CRFM/HAI, Harvard (Rajpurkar), Radboud DIAG |
| 5 | **Earth & climate** | Lead time and spatial resolution are first-class conditions; WeatherBench 2's explicit refusal to aggregate is our thesis validated in the wild and must be modelled, not flattened | Climate Informatics, NeurIPS CCAI, AGU/EGU, ECMWF. Columbia LEAP, Google Research weather team, ServiceNow/IBM (GEO-Bench), AgML/NASA Harvest |
| 6 | **Physics** | Highly fragmented by subfield with almost no shared vocabulary; quantum benchmarks evaluate *hardware*, not models, which breaks `subject_under_test` | NeurIPS ML4PS, CERN IML working group and the **HEP ML Living Review** (itself a direct precedent for a curated index), APS March Meeting, ACAT/CHEP. Polymathic AI / Flatiron |
| 7 | Audio & speech; Games & planning; Vision | Medium difficulty, but each has one structural quirk worth an hour: RTFx on the same axis as WER; unbounded pool-dependent Elo; a 1,000+ family long tail that will eat the project if not capped | INTERSPEECH/ICASSP/ISMIR/DCASE; Farama Foundation, ARC Prize Foundation; CVPR/ICCV/ECCV workshop challenge organisers |

Safety & alignment is deliberately *not* on this list for outside review in Phase 1 -- the field's own
registry, UK AISI's `inspect_evals`, is a better reference than any single reviewer and is
MIT-licensed. Reconcile against it instead.

### 12.2 The ask

Keep it small enough that the answer can be yes in one reply. The message proposes **one hour, one
domain**, with three concrete deliverables:

1. **The subdomain list.** "Here are the 15 subdomains under `robotics-embodiment`
   ([02-taxonomy.md](02-taxonomy.md) §3 holds the per-family counts). What is missing?
   What is a distinction nobody in your field actually makes? What are we calling by the wrong name?"
2. **Ten entries.** Ten fully-classified benchmarks from their field, as rendered pages. "Is any of
   this wrong? Is any of it embarrassing?"
3. **One gap question.** "Here is the row of the coverage matrix for your domain. Are these cells
   genuinely empty, or do we just not know about the work?" This one is the most valuable, because a
   false empty cell is the most damaging error the project can publish and a domain expert
   invalidates one in seconds.

What is explicitly *not* asked at first contact: ongoing maintenance, a formal advisory role, or
anything with a recurring calendar entry. That ask comes later, if at all, and it comes from the
reviewer's own interest rather than ours.

What is offered: a named credit line on the domain's taxonomy page and in `taxonomy/CONTRIBUTORS`,
co-authorship on the release DOI for reviewers who want it, CC-BY data they can use in their own
work without asking, and the ability to fork or correct anything they disagree with. For an academic,
"a citable, permissively-licensed map of my field's benchmarks, with my name on it" is a reasonable
return on an hour.

### 12.3 Why this is also the best outreach the project has

A review request is a better introduction than an announcement. It is specific, it is flattering in a
non-hollow way, it demonstrates the work already exists, and it ends with the reviewer having read
the site carefully -- which no amount of promotion achieves.

It is also **recruitment for the succession plan**. The clearest lesson in the mortality analysis is
that academic evaluation infrastructure has a roughly three-to-four-year half-life tied to grant
cycles and student turnover: HELM entered maintenance mode on 2026-06-01, and **MedHELM survived by
spinning out to an independent steward** (Apache 2.0, technical stewardship by Pacific AI, 121
clinical tasks). The vertical that found an owner lived; the parent did not. Per-domain stewards are
therefore the target end state, not a central curator, and the reviewer pool is where stewards come
from. Treat every review conversation as the first step of that, and never as a one-off favour.

Practical cadence: **two reviewers per quarter**, starting with robotics in the quarter after the
v1.0.0 freeze. Each review triggers one IRR run for that family (§6.3) and whatever ADRs the review
produces. Eight reviewers a year covers the six priority domains plus two repeats within eighteen
months, which is a realistic pace for a two-person part-time team and matches the seed-release
schedule in [14-roadmap.md](14-roadmap.md).

---

## 13. What would tell us the taxonomy is wrong

Worth stating explicitly, because a plan with no falsification criteria is a plan that will be
defended rather than corrected.

- The unmet-term rate rises for two consecutive quarters. The vocabulary is falling behind the field.
- A facet fails IRR twice on different 30-item samples after a revision. The facet is not a facet;
  it is two facets, or it is a free-text field wearing an enum's clothes.
- A domain reviewer's first reaction to the subdomain list is to reorganise it rather than extend it.
  The spine is wrong for their field and probably for its neighbours.
- The coverage matrix has almost no empty cells. Either over-tagging has happened (§7.1) or the
  capability vocabulary is too coarse to be interesting.
- More than 15% of entries carry a `__NEEDS_REVIEW__` sentinel at any time. Splits are outrunning
  re-adjudication capacity, and the honest response is to stop splitting, not to hire.

Each of these is measurable from the health report in §11, which is the point of publishing it.

---

## See also

- [02-taxonomy.md](02-taxonomy.md) -- the vocabularies this document builds and governs
- [04-data-model.md](04-data-model.md) -- how facet values attach to entities, and the validation tiers
- [05-repository-and-workflow.md](05-repository-and-workflow.md) -- the general curation workflow, review rules and the issue-form contribution path
- [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) -- source licences, including the CC-BY-SA quarantine that constrains taxonomy inheritance
- [11-ai-features.md](11-ai-features.md) -- the AI layer's governing rule and the golden-set discipline the drift check borrows
- [12-analytics-and-trends.md](12-analytics-and-trends.md) -- the coverage matrix and gap analysis this taxonomy exists to make possible
- [14-roadmap.md](14-roadmap.md) -- where the ~73-hour bootstrap and the review programme sit in the phase plan
- [15-open-questions.md](15-open-questions.md) -- unresolved calls, including domain-specific extension blocks
