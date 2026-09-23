# 13 -- Local Evaluation Runner

Running benchmarks is the most obvious feature in a project about benchmarks, and for most of this
plan's history it was also the feature most likely to kill it. This document used to argue for
deferring it indefinitely. That argument was right about the danger and wrong about the cause, and
the correction is worth stating precisely, because everything below depends on it.

**The danger was never execution. It was whose machine and whose bill.** A service that runs
evaluations on demand converts near-zero static hosting into an unbounded compute cost and a
permanent operations obligation — the cost that paused Princeton HAL's submissions within a year of
publication. A *runner shipped inside a package*, which executes on the user's own infrastructure
with the user's own keys, has none of that: our marginal cost per evaluation is zero and stays zero
however many people run one.

So the runner is built, and it is not optional. It ships as `bench run` inside the package
described in [17-packages-and-sdk.md](17-packages-and-sdk.md) §2.5, emits a `RunRecord` the user
owns, and that record may then be submitted for review through
[18-api-and-submissions.md](18-api-and-submissions.md) §4. We accept results. We never produce them
on demand for others, and [00-vision-and-scope.md](00-vision-and-scope.md) §4 states that as a
standing non-goal.

**It is still last in build order**, and that has not changed either. The runner depends on the
package, the package depends on the catalogue, and a runner built before there is anything to run
it against is the failure mode this document was originally written to prevent. What follows —
the adapter contract, the isolation substrate, the safety and cost controls — is unchanged by the
reframing, and matters more rather than less now that the code executes on someone else's machine.

---

## 0. The gate, which now sizes the phase rather than deciding it

### 0.1 What the gate is for, after the reframing

The original gate was a go/no-go: build the execution layer only on evidence that the operating cost
was worth absorbing. **That question is closed** — with a local-first runner there is no operating
cost to absorb, so the first adapter is built unconditionally as part of the package.

The gate does not disappear, because a real cost remains and it is not compute. **It is adapter
maintenance.** Every harness this runner supports is a third-party interface that changes without
notice, and the failure mode of a runner project is a fleet of adapters nobody has time to keep
green — which publishes stale, silently-broken reruns, which is worse than publishing none.

So the gate is repurposed, and it now controls **scope rather than existence**:

> The first adapter ships with the package, unconditionally. A **second** adapter, scheduled reruns,
> and the public execution pages are built only when all three of the following are true, measured
> over the six months after public v1: (1) at least three external contributors have landed data
> through the issue form or the submission path; (2) at least one external publication cites the
> Zenodo DOI; (3) at least five unsolicited requests for reruns or verification have arrived through
> issues, email or submissions.

[14-roadmap.md](14-roadmap.md) still owns the gate's wording; this document supplies the
instruments, and the rule that an unmeasurable condition counts as failed. The instruments below are
unchanged — what they gate is narrower.

### 0.2 The instruments

| Condition (owned by 14) | Instrument | What counts, precisely |
| --- | --- | --- |
| **(1)** ≥3 external contributors landed data through the issue form | `git log` over merged commits carrying the `source:issue-form` label and trailer described in [05-repository-and-workflow.md](05-repository-and-workflow.md) §6, counting distinct non-maintainer authors | A contributor counts once regardless of how many entries they landed. Maintainers, alt accounts and anyone holding commit rights are excluded. The label already exists for attribution reasons, so the measurement is a query rather than new instrumentation |
| **(2)** ≥1 external publication cites the Zenodo DOI | Crossref `works?filter=reference.doi:<release DOI>`, plus an OpenAlex `cites:` query and a Semantic Scholar citation lookup on the same DOI | **Both enrichment APIs now need keys.** OpenAlex moved to a metered, key-required API (announced Jan 2026, enforced around 2026-02-13) and Semantic Scholar's unauthenticated tier returns 429 on the first request ([recon:sources]). Budget the keys before the measurement, not during it. Self-citation by the maintainers does not count |
| **(3)** ≥5 unsolicited rerun or verification requests | A `request:rerun` label applied at issue triage, counted from the issue list; email requests are transcribed into an issue so the count has one home | **Unsolicited** means the requester opened it unprompted. A request arriving in response to a call for requests does not count, because a gate you can generate demand for is not a gate |

**Measurement discipline.** The window is the roadmap's — six months after public v1 — and the
measurement is written down twice inside it, at each quarter boundary, as `docs/adoption/YYYY-QN.md`
containing the raw query output and the date it was run. Two recorded measurements inside one window
is what distinguishes a signal from a spike, and committing the raw output is what stops the second
measurement from being reinterpreted to fit.

> **If a condition cannot be measured, it counts as failed. An unmeasurable gate is an open gate.**

### 0.3 Corroborating signals, which are not the gate

Independent forks carrying commits not in our history, and referrer data on the `corpus.json` and
`facets.json` asset paths, are both worth recording in the same quarterly file. Neither is a gate
condition. Fork counts are noisy — most forks are bookmarks — and it is **(unverified — confirm
before relying on this)** whether Cloudflare's free-tier analytics exposes per-path referrers for
unbilled static asset requests at all. Treat them as corroboration: a written report from a
downstream consumer, or a public repository visibly reading an artifact at a commit hash, is real
evidence and belongs in the file; a fork count decides nothing.

### 0.4 Sequencing

The gate sits on top of, not instead of, the ordering: **Phases 0–6 must have shipped**
([14-roadmap.md](14-roadmap.md)), which is everything through the AI layer. If those phases succeed,
this phase is optional. If they fail, this phase cannot rescue them.

---

## 1. Why this is last

### 1.1 It is commodity work, and the incumbents are better at it than we could be

Harnesses exist. They are mature, permissively licensed, mostly actively maintained, and staffed by
people whose entire job is to keep them running.

| Harness | Scale that changes the decision | Licence | Last activity observed | What it already covers |
| --- | --- | --- | --- | --- |
| **EleutherAI `lm-evaluation-harness`**<br>`github.com/EleutherAI/lm-evaluation-harness` | 60+ benchmarks, hundreds of subtasks, all declared in an in-repo YAML task registry. An earlier draft of this document said "~227 task directories"; nobody here has counted them, so the figure is withdrawn rather than marked | MIT | active, 2026-09-14 | Classic academic LM evals; limited multimodal (`hf-multimodal`, `vllm-vlm`, `mmmu`) and defers to `lmms-eval` |
| **UK AISI Inspect + `inspect_evals`**<br>`inspect.aisi.org.uk` · `github.com/UKGovernmentBEIS/inspect_evals` | ~171 evals, reported as 129 internal / 42 external *(unverified — [recon:landscape]'s live count on 2026-09-17; nobody here has recounted it)*. Maintained by UK AI Security Institute with Arcadia Impact and the Vector Institute; framework co-developed with Meridian Labs | MIT | active, pushed 2026-09-17 | Coding, cyber, math, reasoning, knowledge, multimodal, agentic, safeguards, scheming, bias, personality, writing. The de facto frontier safety eval standard in 2026 |
| **Stanford HELM**<br>`crfm.stanford.edu/helm` | 8 leaderboard variants across text, vision, image-gen, tables, medicine, audio *(unverified — the variant list is assembled from several pages, not one authoritative index)* | MIT | **maintenance mode declared 2026-06-01** (verbatim in the repo README) | The most genuinely multi-modal academic harness — and now frozen |
| **OpenCompass**<br>`github.com/open-compass/opencompass` | 70–100+ datasets, ~400k eval questions *(unverified — self-reported in the project's own README)*; CompassKit / CompassHub / CompassRank | Apache 2.0 *(unverified — confirm before relying on this)* | active; multimodal eval deprecated 2026-04 and moved to VLMEvalKit | Chinese-ecosystem-centric, LLM-only |
| **OpenAI Evals**<br>`github.com/openai/evals` | Self-described "registry of benchmarks"; the signal is the open-issue backlog, not the count *(unverified)* | non-SPDX "Other" | 2026-04-14 | Effectively unmaintained as a catalogue |
| **MTEB**<br>`github.com/embeddings-benchmark/mteb` | Embeddings across languages and modalities | Apache 2.0 | active, pushed 2026-09-16 | The best-run single-domain example in the field |

*All figures observed 2026-09-17 via [recon:landscape]; each row names its source repository. Counts
of this kind go stale in weeks — regenerate before relying on them. Star counts and commit counts
have been deliberately removed: they are not decision-relevant, and their presence in a table is the
clearest possible signal that the table was copied rather than sourced.*

Two further movements matter to the build-versus-integrate question and are recorded so nobody
rediscovers them late. **HuggingFace LightEval** is a third generalist option, not evaluated here.
**promptfoo** — MIT core — was acquired into OpenAI's Frontier infrastructure in March 2026 with a
stated commitment to keep the core MIT and model-agnostic *(unverified — confirm before relying on
this)*; the Papers with Code precedent says single-corporate-owner is the failure mode, so it is not
a dependency to adopt lightly. The whole commercial eval-execution tier (Braintrust, LangSmith,
DeepEval, RAGAS) sells *running* evals rather than *finding* them, which makes it a distribution
channel rather than a competitor.

Beyond the generalists sit the domain harnesses: `fair-chem` for Open Catalyst and OMol25,
`matbench-discovery`'s own evaluation pipeline, Open Problems in Single-Cell Analysis (Viash/Nextflow
on Seqera, continuously re-executed so results change when the pipeline re-runs), PoseBusters as a
validity battery composed onto other benchmarks' metrics, OmniGibson/Isaac-Sim builds for BEHAVIOR,
CARLA for Bench2Drive. Each is maintained by the people who designed the measurement, and none of
them carries a licence or liveness note in this plan yet — that is curation work owed by
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), not a claim of currency made here.

**Note the boundary before reading further: every harness in that paragraph is `single-gpu` or
worse, and is therefore excluded by the §3 scope gate on compute tier alone. Integration with them
means cross-reference fields and ingested condition data — never a wrapper, and never a run. That is
a permanent boundary, not a sequencing decision.** The domain harnesses are the only credible way to
*execute* the non-language half of the index, and this project will never be the one executing it.

The decisive datum is the HELM line. Stanford CRFM — a funded lab with students, engineers and
institutional backing — built the most ambitious multi-modal evaluation harness in the field and put
it into maintenance mode on 2026-06-01. MedHELM survived only by spinning out to an independent
steward under Apache 2.0, with technical stewardship reported as Pacific AI. (Its scale is given as
121 clinical tasks, 22 subcategories and 31 datasets in [recon:landscape] and explicitly marked
*"exact task/benchmark counts UNVERIFIED"* in [recon:domains] — the two reports disagree on whether
that figure is confirmed, so treat it as unverified.) If Stanford could not sustain a generalist
harness past roughly four years, a one-to-two person catalogue team writing its own from scratch is
not a plan, it is a fantasy. The right posture toward these projects is integration and
cross-reference, never competition.

**Recommendation:** treat harnesses as upstream dependencies and as *data sources*, not as things to
replace. `lm-evaluation-harness`'s task YAMLs (`num_fewshot`, `output_type`, `metric_list`,
`dataset_path`, `doc_to_text`) are already the single best source of structured evaluation-condition
data in existence and are ingested in [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md);
`inspect_evals` gives every catalogued benchmark an `inspect_evals_id` cross-reference that makes
this index the front door to their harness. Their `/register/` folder, launched 2026-05-08, is also
the model this project already copied for its own contribution path
([05-repository-and-workflow.md](05-repository-and-workflow.md) §6) — a bot that validates an issue
submission, derives metadata and opens the PR. **Risk:** integration still creates a maintenance
surface — upstream renames tasks and our cross-references rot. Mitigate by re-deriving the
cross-reference table on every ingest run rather than hand-maintaining it.

### 1.2 It applies to a minority of the index, and the minority is the part we are *least* differentiated on

This is the sharpest form of the argument and it deserves to be stated numerically rather than
waved at. The seed corpus is **320 Tier-1 benchmark families at seed** (the canonical per-family
allocation is [02-taxonomy.md](02-taxonomy.md) §3, which owns it and is not restated here), against
[recon:domains]'s estimate of **~1,470 families worth cataloguing overall** across the thirteen
domains it surveyed. Very little of that is executable by anybody, let alone by us.

| Domain family | Why most of it cannot be re-run in a container | Concrete blockers from the inventory |
| --- | --- | --- |
| Robotics & embodiment | Physical hardware or a heavyweight pinned simulator | RoboArena runs on physical DROID robots in different rooms with double-blind pairwise human comparisons and has **no fixed task set at all** — evaluators choose their own; the A2RL Drone Championship is physical aircraft at roughly 90 mph *(figure from [recon:domains]; unverified)*, and a human FPV pilot won its Jan 2026 final; RoboCup is a tournament in a hall; the 2026 BEHAVIOR Challenge's score is **only defined inside a specific OmniGibson/Isaac-Sim build** |
| Chemistry & materials | Wet-lab ground truth, DFT-scale compute | CACHE requires you to **buy compounds from Enamine** and have them assayed, then face a medicinal-chemistry expert panel; OCx24 ties computation to real experimental measurements; the CCDC CSP Blind Test runs multi-year against unpublished experimental structures |
| Biology & genetics | Embargoed targets, ground truth that arrives years later | CASP17 releases targets on a rolling embargoed schedule, outputs **assessment papers rather than a leaderboard**, and ranks human-expert and automated-server entries in separate categories; CAFA's ground truth accumulates *after* submission; the Virtual Cell Challenge's ceiling is a real biological replicate experiment |
| Medicine & health | Gated data under agreements that forbid onward transfer | CheXpert/MIMIC-CXR/MIMIC-IV need PhysioNet credentialing, CITI training and a signed DUA; BraTS 2026 has a hidden test set under data-use agreement; HealthBench is reported as 48,562 physician-authored rubric criteria graded by a model *(unverified)* |
| Earth & climate | Data volume and a maintainer who refuses ranking | WeatherBench 2 needs ERA5 at scale and its authors explicitly say it is "a tool to compare different approaches on different aspects", not a challenge with one ranking. Its honest unit is a grid of variable × pressure level × lead time × metric |
| Games & planning | Pool-dependent ratings a rerun cannot reproduce | Kaggle Game Arena Elo comes from all-play-all at 40 games per model pair and moves when a *different* model joins the pool; rerunning produces a number not comparable to the published one |
| Society / econ / law | Ground truth that has not happened yet, or can never be published | ForecastBench resolves over months to years; SimulacraBench is scored against **unreleased UN microdata** and is unreproducible by anyone outside, ever |
| Safety & alignment | Deliberately private by design | Apollo Research's scheming suite is held out to avoid training contamination and surfaces only in vendor system cards; WMDP withholds items; Redwood's AI control evaluations are a red-team-versus-blue-team game with **no test set at all** |

#### The share of the index the runner could ever touch, derived

An argument that says "a minority" without a number is a slogan. Here is the arithmetic, built from
[02-taxonomy.md](02-taxonomy.md) §3's per-family seed allocation. **It is a family-level estimate,
not a record-level count** — the record-level count is exactly what §3.2's pre-flight query exists to
produce, and it cannot be produced before the corpus exists.

| Step | Entries | Share of the 320-entry seed |
| --- | --- | --- |
| Families that could contain hosted-API-runnable entries at all: language, mathematics, code, reasoning-general, general-intelligence, agents-tooluse, safety-alignment | **104** | 33% — the ceiling before any clause bites |
| − the §5.6 dangerous-capability carve-out, which removes essentially all of safety-alignment | **86** | 27% |
| − clause 5, "already covered by a maintained harness leaderboard publishing conditions", which removes most of language, mathematics, code and general-intelligence | **32** | 10% |
| ± minority slices of multimodal and society-econ-law that qualify, less the agents-tooluse entries needing a VM host, a simulator or local weights | **≈25–45** | **8–14%** |

At the 1,500-benchmark maturity corpus, the same share is roughly **120–210 entries**. Both figures
matter in §3.2, where they collide with the threshold.

What survives is the LLM reasoning, code and agentic cluster, plus parts of vision and audio. That
is precisely the slice where `lm-evaluation-harness`, Inspect and HELM already run everything, where
Epoch AI already publishes 828 public Inspect-AI transcripts (verified count, §2), and where every
competitor in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) already has
numbers.

**The runner's coverage is inversely correlated with the project's differentiator.** It would cost
the most effort in exactly the domains where we add the least, and it would cover almost nothing in
the domains that are the entire reason the project exists. Name the failure mode plainly: building
the runner is how a cross-domain catalogue quietly turns back into an LLM leaderboard.

### 1.3 It would consume the project

Harness maintenance is not a project, it is a treadmill. API deprecations, dependency conflicts,
container drift, OS and application version changes inside VM-based environments (OSWorld's score
moves with the Ubuntu build and the app versions), simulator builds, provider rate-limit changes,
model endpoints silently rotating underneath a fixed name. Every one of those is an interrupt that
lands on the same two people who are supposed to be curating robotics and protein benchmarks.

The mortality record in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) is worse
for execution operations than for catalogues:

- **Princeton HAL** — ICLR 2026 paper, 9 benchmarks, standardised harness, cost-controlled agent
  evaluation, accuracy-versus-cost Pareto fronts: exactly the thing a sophisticated reader would say
  we should build, and [recon:landscape]'s pick for the best existing evidence of this project's own
  "conditions as first-class data" thesis. **No longer accepting submissions; leaderboard updates
  paused**, pivoted to a reliability dashboard, within a year of publication.
- **Stanford HELM** — maintenance mode 2026-06-01, after roughly four years.
- **HuggingFace Open LLM Leaderboard** — retired 2025-03-14 after evaluating 13,000+ models, with
  the stated reason that it "was becoming obsolete and could encourage people to optimize in
  irrelevant directions."
- **BIG-bench** — archived read-only 2026-04-17. **Dynabench** — last push 2026-02-11, near-dormant
  despite MLCommons ownership. **Aider leaderboards** — reported last updated 2025-11-20
  *(unverified — confirm before relying on this)*.

These organisations had more people, more money and more focus than this project will have. They all
ran out of the thing that running evaluations consumes fastest: sustained attention.

### 1.4 The index is valuable without the runner; the runner is worthless without the index

A catalogue with zero self-produced numbers is still the only cross-domain, CC-BY, forkable,
provenanced benchmark registry in existence. A runner with no catalogue is a worse copy of Inspect.
The asymmetry is total, and it settles the ordering.

---

## 2. The one thing it buys

A **`sandboxed-rerun`** verification level: result claims this project produced itself, under
conditions it recorded mechanically rather than read off a blog post, on benchmarks anyone can
re-run from the published manifest.

That matters because the evidence base in this field is thin in a specific, measurable way.
[00-vision-and-scope.md](00-vision-and-scope.md) §8.1 owns the Epoch row count and the counting rule
that produces it (including the 80-versus-81 file resolution); the table below is the same derivation
run independently here, kept because it shows its working and because the decomposition is what the
argument needs. If the two ever disagree, `00` §8.1 wins and this table is the one to fix. The
figures were derived by a `csv.DictReader` pass over `epochdl/` on 2026-09-17 and agree, row
for row, with [recon:epoch-assets]'s independent count over the same files — two derivations, one
result. `epochdl/` is not committed to this repository, so what follows is a recorded recipe rather
than something a reader can re-run from a clone; if it is ever re-run and disagrees, the re-run
wins.

| Quantity | Value | How it was derived |
| --- | --- | --- |
| Per-benchmark CSV files | **80** | Every `*.csv` in `epochdl/` excluding `benchmark_metadata.csv` and `model_metadata.csv` |
| Total result rows | **6,598** | `csv.DictReader` row count summed across those 80 files. **No dedup applied** — this is the raw row count, and it is the same figure [recon:epoch-assets] reports |
| Epoch-run rows (files carrying a `Logs` column) | **1,550** across 14 files | `chess_puzzles`, `ebr_bench`, `frontiermath` (×4 variants), `gpqa_diamond`, `math_level_5`, `mirrorcode`, `mystery_game_puzzles`, `otis_mock_aime_2024_2025`, `simpleqa_verified`, `swe_bench_verified` |
| Rows with a populated `.eval` log URL | **1,287** | 828 public S3 + 459 private S3 |
| Epoch-run rows with a *blank* log field | **263** | 1,550 − 1,287 |
| External (non-Epoch-run) rows | **5,048** | 6,598 − 1,550 |
| **Rows with no artifact of any kind** | **5,311** | 5,048 external + 263 blank-log Epoch-run = 6,598 − 1,287 |

An earlier draft of this document wrote "roughly 5,048 … with no artifact at all", which was the
*external* row count, not the no-artifact count; the 263 blank-log Epoch-run rows also have no
artifact. The reconciled figure is **5,311**, and the two numbers differ because they answer
different questions. [04-data-model.md](04-data-model.md) uses 5,048 when describing which rows land
at `self-reported`, which is correct for *that* question and should stay.

A reviewer arrived at 7,661 raw rows across 81 `*_external.csv` files. That count does not reproduce:
`epochdl/` contained 66 files matching `*_external.csv` and 80 per-benchmark CSVs in total, and a
`DictReader` pass over them yields 6,598. The likely cause is a line count including headers and
quoted embedded newlines.

> **One reconciliation owed to [04-data-model.md](04-data-model.md).** Its machine-assignment rule
> for the Epoch adapter reads "Epoch-run with a `-private` or blank log → `maintainer-verified` (459
> rows)". The rule is right and the parenthetical is wrong: `-private` is 459 rows and blank is 263,
> so the rule covers **722**. As printed, 04's three counts sum to 828 + 459 + 5,048 = 6,335, which
> is 263 short of 6,598; with 722 they sum exactly. This is the same arithmetic slip this document
> carried and fixed, and 04 owns the rule, so 04 owes the correction — before the adapter is
> written, because a rule that loses 263 rows loses them silently.

The expected mean `condition_completeness` across that corpus is around **0.10**
([recon:epoch-assets] estimates 0.05–0.15; [04-data-model.md](04-data-model.md) states the 0.10
expectation with its per-field basis and owns it). The dominant evidence class in AI evaluation is
"a vendor said so in a launch post", and the second is "a leaderboard row with no conditions
attached." These figures are ingested under the **bulk-ingest / segregate / badge-honestly policy**
stated in [04-data-model.md](04-data-model.md) §7, "Machine assignment rule for the Epoch adapter"
(a bolded run-in paragraph inside §7, not a heading — three documents cite it and it is worth
promoting to a `###`), and [05-repository-and-workflow.md](05-repository-and-workflow.md) — not mixed
into `data/claims/` proper.

Against that background, even a few dozen claims with complete material conditions, a pinned
container digest, a published per-item transcript and a published cost are a genuine contribution.
They also set a norm by example: the project's own claims should be the most completely specified
ones in the index, which is a far stronger argument for the schema than any amount of documentation.

### 2.1 Where `sandboxed-rerun` sits on the ladder — 04 owns it, and this is an objection, not an amendment

**[04-data-model.md](04-data-model.md) owns the `verification` enum and its ordering. This document
does not amend it, and an earlier version of this file was wrong to state a rival ladder.** The live
ordering is 04's:

```
1  self-reported
2  maintainer-verified
3  independent-reproduction
4  held-out-server
5  prospective-experiment
6  third-party-audited
7  sandboxed-rerun

disputed                      # a state, not a rung — carried by disputed_by[] as an overlay badge
```

Two facts a reader should have before going further. First, **[09-design-system.md](09-design-system.md)
currently defines only six `--c-verif-*` tokens, places `sandboxed-rerun` at 5, and has no token for
`prospective-experiment` at all.** That is a live drift between 04 and 09 as of 2026-09-21, it is
independent of whether this phase ever happens, and 09 owes a seventh token in 04's order. Second,
this document has a substantive objection to the ordering, which it files rather than acts on.

**The objection.** The ladder is a single total order over two independent axes, and
`sandboxed-rerun` is the record that exposes the conflation:

- **Axis A, provenance.** How well we know the number is what it says it is — who ran it, under
  which conditions, with what artifact. A sandboxed rerun maximises this axis: pinned digest,
  machine-recorded conditions, published per-item transcript.
- **Axis B, contamination control.** How well we know the system never saw the test set. A sandboxed
  rerun says **nothing whatsoever** about this axis. A held-out server proves it; a prospective
  experiment proves it more strongly still, because the ground truth did not exist at submission
  time.

Ranking `sandboxed-rerun` seventh therefore tells a reader that our own reruns carry a stronger
guarantee than a held-out server, which is false on axis B and self-flattering in a way the first
specialist to look will say so about — in public, about the project whose entire pitch is refusing
to overstate evidence.

**The narrow proposal, for 04 to accept or reject.** Keep a single ordered rank, because the UI
needs one for sorting, but stop making it carry both axes: add an orthogonal claim-level field
recording contamination control — `held_out_from_subject: true | false | unknown`, alongside the
`contamination_risk` and `contamination_evidence` fields 04 already carries on the Benchmark — and
render it beside the badge rather than inside it. Then `sandboxed-rerun` can stay at rank 7
honestly, because the badge no longer implies what it cannot support. **If 04 declines the second
field and the single order has to carry everything, then `sandboxed-rerun` belongs immediately after
`independent-reproduction`** — it is a machine-recorded special case of exactly that — **and
everything above it moves up one.**

**Disposition, so nobody has to guess.** Until 04 rules, **04's ordering stands and this document
uses it.** The objection is filed as **ADR-NN: verification ladder axes**. The nearest existing
decision-log mechanism is the ADR process in
[03-taxonomy-build-process.md](03-taxonomy-build-process.md), which is scoped to the taxonomy; if
ADRs stay taxonomy-scoped, 04 needs an equivalent log of its own, and the absence of one is itself a
small gap worth closing before Phase 0 ends. **Failure mode being avoided here:** the last document
in the set silently redefining an enum owned by the fourth is how two documents end up disagreeing
and CI ends up arbitrating a design decision nobody made.

Three loose ends, named rather than left to vanish:

| Loose end | Disposition |
| --- | --- |
| `live-arena` | Carried by the **archive** taxonomy, dropped by the current [04-data-model.md](04-data-model.md). Correct to drop: an arena rating is a *claim type and a pool-dependent metric*, not an evidence grade. It belongs in `claim_type` / `result_group`, and the ADR should say so explicitly so nobody re-adds it. Kaggle Game Arena is the worked case — a rating that moves when a different model joins the pool is not a grade of evidence about any one model |
| `physical-competition` | Same origin, same disposition. A physical competition result's evidence grade is usually `maintainer-verified` or `held-out-server`; the physicality is a `reproducibility_tier` fact, not a verification fact |
| `disputed` as a flag | **Already done in 04**, with `disputed_by[]` pointing at Sources and rendered as an overlay badge on top of whatever level the claim holds. No migration is owed by this document. If any pre-ADR record ever carried `verification: disputed`, the migration is 04's, not this phase's |

**Risk of the ladder as a whole:** users will read it as a quality ranking rather than an
evidence-type ordering. Mitigate with the inline explanation the UI already shows on hover
([09-design-system.md](09-design-system.md)), and bring 09's `--c-verif-*` token list — already one
token short — into line when the ADR lands, so the colours and the ranks cannot drift further apart.

**What `sandboxed-rerun` is not.** It is not a product, not a leaderboard, and not a claim of
authority over the benchmark's maintainer. It is an upgrade to the evidence base, and it only has
meaning once the evidence base exists.

---

## 3. The scope gate

Only benchmarks the index has already marked as runnable are eligible. From the `execution` block in
[04-data-model.md](04-data-model.md):

```yaml
execution:
  compute_tier: api-credits-only          # api-credits-only | single-gpu | multi-gpu | cluster |
                                          # specialised-hardware | wet-lab
  reproducibility_tier: fully-automatable # fully-automatable | automatable-with-simulator |
                                          # requires-eval-server | requires-human-raters |
                                          # requires-physical-experiment | requires-specialised-hardware |
                                          # not-independently-reproducible
  est_runtime_hours: {min: 2, max: 30}
  est_cost_usd: {min: 50, max: 2000}
```

**The gate is five clauses, and the count that decides the phase is taken after all five:**

```
reproducibility_tier ∈ {fully-automatable, automatable-with-simulator}
AND compute_tier == api-credits-only
AND data.access ∈ {fully-open, gated-registration}        # i.e. no credentialed-DUA access mode
AND NOT dangerous_capability_carveout                     # §5.6
AND NOT covered_by_maintained_harness_leaderboard_publishing_conditions
```

The fourth clause matters more than it looks. The dangerous-capability carve-out in §5.6 removes
Cybench, AgentDojo, AgentHarm, HarmBench, JailbreakBench, WMDP and the whole cyber-range family —
a large share of exactly the agentic and safety benchmarks that would otherwise sail through the
first three clauses. Any threshold set before subtracting them is set against the wrong population.
§1.2's arithmetic shows the fourth and fifth clauses between them taking the candidate pool from 33%
of the seed corpus to about 10%.

**The data-access clause, with the correct reason.** An earlier draft justified this clause by
saying that holding benchmark data violates hard constraint 1. That is wrong, and taken literally it
forbids the entire phase, since every rerun of every benchmark fetches the data into a container.
The correct statement:

> Benchmark data is fetched into an ephemeral container at run time, never persisted, never
> republished, and never included in any build artifact. That satisfies hard constraint 1, which is
> about hosting and redistribution, not about transient fetching. DUA-gated data is excluded for a
> different and stronger reason: a credentialed DUA (PhysioNet, BraTS, and the medical-imaging
> challenges generally) typically prohibits **onward transfer**, and sending gated items to a
> commercial inference endpoint is exactly such a transfer. We would be breaching the agreement, not
> merely holding data.

That distinction is not pedantic. The first version is a constraint we can satisfy by deleting a
directory; the second is a legal commitment we cannot satisfy at all while running against a hosted
API, and it is the reason the clause is absolute rather than a matter of care.

The satisfying part of the whole gate is that **the schema can already answer "what is runnable?"
before a single line of runner code exists.** That is a good sign the schema was designed correctly
— the execution block was never a speculative field, it was a coverage fact about the ecosystem that
happens to double as a build gate.

### 3.1 Two fields that belong in Phase 0, not here

| Field | On | Why it earns its place immediately |
| --- | --- | --- |
| `runnable_via: [inspect \| lm_eval \| helm \| custom \| none]` | `Benchmark` | The suite-builder export in [11-ai-features.md](11-ai-features.md) needs it to say honestly "3 of 12 entries are runnable from a harness; 9 link to their own repos." Every other tool implies everything is runnable. The admission is a differentiator |
| `inspect_evals_id` | `Benchmark` | Cross-reference into UK AISI's MIT-licensed registry; derived automatically on ingest, and it makes this index the front door to their harness rather than a rival |

**Both fields belong in the Phase 0 schema, not in this phase.** `runnable_via` is required by the
suite-builder export in Phase 6 and `inspect_evals_id` is derived for free on every `inspect_evals`
ingest run. The Epoch lesson applies identically: schema additions must land before bulk ingest,
because retrofitting is painful. Adding them at Phase 7 means hand-backfilling on the order of 1,500
benchmark records. **This document proposes them; [04-data-model.md](04-data-model.md) owns them and
must ship them at Phase 0.** The same applies to `execution.maintainer_rerun_policy` (§5.4) and the
`provider_snapshot` / `provider_snapshot_available` pair (§4.5).

### 3.2 The pre-flight decision rule, with a derived threshold — and the honest answer it gives today

Before committing to the phase, run the five-clause gate query and count. The earlier draft asserted
a threshold of "~40" and conceded in its own open-questions section that the number was a judgement
rather than a measurement. Replace the assertion with a derivation.

> **The threshold is `ceil(estimated_phase_hours / 5)`** — the phase must yield at least one new
> fully-specified claim per five hours of build effort.

At the phase total estimated in §8 (**190–350 hours**), that is **38–70 gate-passing benchmarks**.
**Recommendation: use the top of the range — require ≥70.** **Reason:** every effort estimate in
this plan is a lower bound written by the people who want to do the work, and the cost of a wrong
"go" is the differentiator itself, paid in curation hours that never come back. **Risk:** a threshold
of 70 may never be met, which means the phase never happens.

**It probably is never met at seed scale, and that is worth saying out loud rather than discovering
in three years.** §1.2's derivation puts the gate-passing population at roughly **25–45 entries of
the 320-entry seed corpus**, below even the bottom of the derived threshold band. The same share
applied to the 1,500-benchmark maturity corpus gives roughly **120–210**, comfortably above 70. Two
consequences follow, and both are useful:

1. **The §3.2 threshold and the §0 adoption gate come due at the same time, years out.** Neither can
   be cleared by the seed corpus. That is worth noticing, because it means the phase is gated twice
   on the same underlying condition — the index having grown into something people use — rather than
   on two independent things that might clear separately. Nobody should plan as though one gate
   could open early.
2. **The threshold is a real gate, not a formality.** A rule the current plan visibly fails is the
   only kind worth writing down. If someone later runs the query and finds 70, the corpus has
   changed in exactly the way that makes the phase worth doing.

Writing this rule down now is the only way it survives contact with the enthusiasm of a team that
has just finished Phase 6.

---

## 4. The design, when the time comes

**Read this section as a set of constraints, not as an implementation.** By the plan's own arithmetic
the §0 gate cannot open for at least eighteen months, and every version pin, container mechanic,
storage price and log-schema assumption below was observed on 2026-09-17 and will be stale by then
([14-roadmap.md](14-roadmap.md) §"Version pins and third-party facts: as-of date" owns the corpus-wide
as-of rule). Three things here are meant to survive that: the isolation rule in §4.1, the
plan/log divergence test that depends on it, and the three-class field partition in §4.4. Those are
design decisions with consequences for the v1 schema, which is why they are written now. The ABC
signature, the `RunRecord` shape and the R2 retention table are worked examples that show the
constraints are satisfiable; re-derive them at gate time rather than implementing them as printed.

### 4.1 The adapter contract — one interface per *harness*, never per benchmark

One implementation per harness. Wrapping `lm-evaluation-harness` once covers dozens of benchmarks;
wrapping Inspect once covers up to ~171. Writing a bespoke runner per benchmark is the single
clearest path to turning this into a maintenance sink, and it is what every project that has tried
this has eventually done under pressure from a benchmark that "almost fits."

A one-line signature is a type, not a contract. The contract is this:

```python
# runner/adapters/base.py  —  Python 3.12 (pinned; see 08-infrastructure-and-build.md)
from abc import ABC, abstractmethod

class HarnessAdapter(ABC):
    name: str                       # "inspect" | "lm_eval" | ...
    harness_requirement: str        # exact pin, e.g. "inspect-ai==0.3.NN"
    container_digest: str           # "sha256:..."  — never a tag
    recovers_material_fields: frozenset[str]   # proven by the §4.4 divergence test, not asserted

    @abstractmethod
    def capabilities(self) -> set[BenchmarkId]:
        """Which catalogued benchmarks this adapter can run. Derived from the harness's own
        task registry at the pinned version, never hand-maintained."""

    @abstractmethod
    def plan(self, benchmark: BenchmarkRef, system: SystemRef,
             conditions: EvalConditions) -> HarnessInvocation:
        """Translate our intent into a harness invocation. Pure; no side effects; no network."""

    @abstractmethod
    def execute(self, invocation: HarnessInvocation, limits: RunLimits) -> RawLogPath:
        """Run the container to completion or to a limit. Returns a path to raw harness output."""

    @staticmethod                   # NOT a method — see the isolation rule below
    @abstractmethod
    def parse(log: RawLogPath) -> ParsedRun:
        """(scores, run-fact conditions, cost, per_item) read ONLY from harness output."""
```

**Process and language boundary.** The adapter is Python 3.12 running on the host; the harness runs
inside a container the adapter starts and never inside the adapter's process. The container is built
and owned by *us*, from a `Dockerfile` in the runner repository that pins the harness by version and
the base image by digest — not pulled from the harness project's own registry, because a tag we do
not control can move under a claim we have already published.

**Idempotency.** `run_id = sha256(system_ref, benchmark_ref, comparability_key, container_digest,
attempt)`, so a re-run of the same intent produces the same id and the artifact store's
content-addressing deduplicates it.

**Timeouts and resume.** A wall-clock limit per run (§5.2 layer 3) and **no resume**. A partially
executed run is discarded and re-run from zero. Resuming a partially-completed agentic benchmark
produces a number whose conditions nobody can state, which is the one thing this phase exists not to
produce.

**The isolation rule — the load-bearing part of the whole phase.** `parse()` is declared as a
`@staticmethod` so it *cannot* reach instance state, and it receives only the raw log path. It may
not read the `HarnessInvocation`, the `EvalConditions` we passed in, or anything else from the plan.
**Reason:** the failure mode is an adapter that reads its own plan back out and calls it a
measurement — a `sandboxed-rerun` claim whose conditions are just our YAML echoed back with a
`machine-recorded` badge on it. That is worse than no rerun at all, because it is a fabricated
provenance grade on a number that looks better-evidenced than everything around it.

**Plan/log divergence is a failed run, not a footnote.** After `parse()` returns, the claim builder
compares the recovered run facts against the plan that was submitted. If they disagree on any
material field — we asked for `temperature: 0` and the log says `0.7`, we asked for four epochs and
the log shows one — **no claim is emitted.** The run is recorded as a divergence incident in the
runner repository with both values. This is the only check that catches a harness silently ignoring
a parameter, which is a common and quiet failure, and it is only possible *because* `parse()` cannot
see the plan. (This is a different thing from the published-number divergence procedure in §5.5;
that one produces a claim and blocks its merge, this one produces no claim at all.)

**Adapter build order — this corrects the earlier draft.** Build **Inspect first**, not
`lm-evaluation-harness`.

| Adapter | Build order | Reason | Risk |
| --- | --- | --- | --- |
| **Inspect / `inspect_evals`** | 1st | ~171 evals, MIT, actively pushed, native sandbox support for agentic evals, and — decisively — it **emits `.eval` transcript logs natively**, which is exactly the per-item artifact the evidence model wants and exactly what makes the §4.4 isolation rule satisfiable. Integration yields the `inspect_evals_id` cross-reference as a byproduct | Inspect's own API and log schema are evolving quickly; pin the version and expect breakage on minor releases |
| **`lm-evaluation-harness`** | 2nd | Its task YAMLs are already ingested as condition data in [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), so the benchmark→task mapping already exists and the adapter is mostly plumbing | Task names drift; the mapping must be regenerated, never hand-maintained. Its log output is thinner than Inspect's, so fewer material fields are recoverable under §4.4 and `condition_completeness` will honestly be lower |
| **HELM run-specs** | Only if demand appears | Broadest modality coverage of the three | In maintenance mode since 2026-06-01 — building on a frozen dependency is a deliberate choice, not an accident |
| **`custom`** | Never as a default | Some domain harnesses have no wrapper-shaped interface | Each one is a permanent obligation. Require an explicit written justification per adapter, reviewed like a schema change |

### 4.2 The output shape

```yaml
RunRecord:
  run_id: run-2027-03-11-0007         # sha-derived; see 4.1
  system: claude-opus-5@2026-05
  benchmark: swe-bench@verified
  subset: null

  scores:                             # {metric_id: value}, plus uncertainty
    resolve-rate:
      value: 0.XXX
      uncertainty: {type: stderr, value: 0.012, n_runs: 5}

  repetition:                         # see 4.6 — not an operator choice
    n_runs: 5
    k_source: benchmark-declared      # benchmark-declared | single-run-default
    aggregation: pass^k               # the benchmark's own rule, copied not chosen

  per_item:                           # RETAINED. aggregate-only results are not auditable
    storage: external                 # see 4.3 — never in the data repo
    format: jsonl
    n_items: 500
    sha256: "..."
    url: https://<r2-bucket>/runs/<sha256-prefix>/per_item.jsonl

  conditions: cond-XXXXX              # full EvalConditions; run facts machine-recorded per 4.4,
                                      # entry facts attached by the curator per 4.4
  comparability_key: "sha256:..."     # computed from the material fields, per 04-data-model.md

  environment:
    container_digest: sha256:...      # pinned by digest, never by tag
    harness: inspect@<version>
    harness_commit: <sha>
    package_lock_sha256: "..."
    provider_endpoint: <api id>
    provider_snapshot: <id or null>
    provider_snapshot_available: true # explicit; see 4.5 — an absence, not an unknown
    provider_data_policy: <retention/training terms id or null>   # see 5.4
    hardware: <instance type or null>
    started_at / finished_at: <ISO 8601>

  cost:
    usd: 0.00
    wall_clock_hours: 0.0
    api_calls: 0
    input_tokens / output_tokens: 0
    cost_source: estimated-from-tokens  # see 5.3 — only becomes `measured` after reconciliation
    cost_reconciled_at: null            # ISO 8601 once reconciled against the provider's usage record

  interop:
    eee_schema_version: "<pinned>"      # see 4.7
```

**Per-item results are not optional.** The whole field is drifting toward metrics that an aggregate
destroys: τ²-bench's headline is `pass^k`, the fraction of tasks solved in *all* k independent
trials, and averaging annihilates it; ReXrank publishes 8 metrics and deliberately no aggregate;
VBench's honest unit is a 16-dimension vector; BBQ is a pair of numbers whose optimum is zero;
WeatherBench 2's is a grid of variable × pressure level × lead time × metric; Matbench Discovery is
stability F1 plus energy MAE plus phonons plus κ_SRME plus MD stability. A runner that stores only
the headline number produces a claim nobody can audit and cannot recompute into the shape a
specialist needs.

### 4.3 Write-back through the normal review path; artifacts in R2

Two rules, both load-bearing.

**No privileged mutation path.** A run produces a `ResultClaim` plus an `EvalConditions` record as
YAML, and opens a pull request exactly as the ingestion bots in
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) do. A human reviews it. A
machine-generated claim gets the same scrutiny as a hand-curated one, and the runner has no write
access to `data/` that a contributor does not have. This is hard constraint 6 and it is not
negotiable for convenience: the moment the project's own tooling has a back door into the corpus,
the corpus stops being auditable and the citability claim becomes a marketing line.

**Artifacts live outside the repo, in Cloudflare R2.** Per-item JSONL, `.eval` logs and raw harness
output go to a content-addressed R2 bucket; the claim carries `artifact_url` plus a `sha256`.

**Recommendation: R2, not GitHub Releases.** **Reason:** zero egress fees (the artifact is meant to
be fetched and verified by strangers, and an egress-billed store makes verification something we pay
for per curious reader), it sits in the same Cloudflare account as the Workers hosting in
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) so there is one bill and one set of
credentials, and content-addressed keys fall out of the storage model rather than being bolted on.
GitHub Releases would be zero new dependencies but caps individual files at 2 GB, has no
content-addressing, and turns artifact integrity into a tag-discipline problem. **Risk:** a second
Cloudflare service in a plan that already puts hosting and the AI Worker there, and a storage bill
that grows monotonically for as long as the project exists. **Note that 08 does not currently
provision R2** — it is listed as a precondition in §9 and is new scope for that document, not an
existing capability this phase can assume.

**Retention policy, because "keep everything" is not a policy and the bill is real:**

| Artifact class | Retention | Reason |
| --- | --- | --- |
| Per-item JSONL (the auditable artifact) | **Indefinite** | This is the evidence. Deleting it retroactively downgrades every claim that points at it |
| Raw harness logs and full agent transcripts | **12 months, then pruned** | Hundreds of megabytes per SWE-bench Verified agent run. The `sha256` and the `RunRecord` survive the prune, so the claim's integrity statement stays checkable even when the blob is gone; the page says "artifact pruned YYYY-MM-DD, hash retained" rather than 404ing silently |
| Container images | Digest recorded, image not stored by us | The digest is the evidence; re-pulling is the reader's job and ours |

**A stated monthly storage cap, published on the spend page.** When the cap is reached, **new runs
are blocked** — the system never silently deletes evidence to make room for more evidence. Set the
initial cap at **100 GB**, which at R2's standard-storage price of roughly $0.015/GB-month
*(unverified — confirm current pricing before relying on this)* is on the order of $1.50/month and
is a rounding error against inference spend. Storage appears as a line on the §6 spend page next to
inference, because an artifact bill that exceeds the inference bill is exactly the sort of thing a
project that publishes other people's costs should not discover in public.

### 4.4 Conditions are recorded, never assumed — and here is the mechanism

The earlier draft asserted that "every material condition field is captured from the actual run, not
inferred from documentation" and never said by what mechanism. That assertion is the load-bearing
claim of the entire phase, so it needs one.

#### Three classes of material field, and who is allowed to answer each

[04-data-model.md](04-data-model.md) is explicit that the material set is **per-benchmark-shaped**,
derived from `taxonomy/comparability-profiles.yaml` via the benchmark's `evaluation_method` and
`designed_for_subjects` facets, with per-benchmark `material_extra[]` and `material_waived[]`
overrides. Within whatever profile applies, every material field falls into exactly one of three
classes:

| Class | Who answers it | Examples from 04's material-field table |
| --- | --- | --- |
| **Run fact** | `parse()`, from the harness log only | `shots`, `chain_of_thought`, `reasoning_effort`, `tools_allowed`, `scaffold`, `harness`, `selection_strategy`, `k`, `n_samples`, `retries_allowed`, `judge_model`, `subset_used`, `simulator`, `simulator_version`, and `human_in_loop` (structurally `false` — the container has no interactive channel and the recorded solver chain contains no human solver) |
| **Entry fact** | The curator, from the `System` and `Benchmark` records, **never** from the log | `training_data_policy`, `eligibility_track`, and `decontamination_applied` wherever it is a property of the system's training rather than of the task's preprocessing |
| **Absence-answerable** | Either, with an explicit companion boolean — see §4.5 | `provider_snapshot` / `provider_snapshot_available` |

**This partition is what makes the §8 exit criterion of `condition_completeness == 1.0` achievable
at all.** The earlier draft named `training_data_policy` among "fields Inspect does not give us,
which stay null and cost us completeness" — and then required 1.0. Both could not be true. They
reconcile once you notice those fields are not run facts: no harness could ever recover what a model
was allowed to train on, because the harness was not there. They are answered at curation time from
the publisher's own statement, or recorded as an explicit "not disclosed by the publisher" value,
which is an answer.

**CI asserts the partition is total.** For every comparability profile, every material field appears
in exactly one class; a field in two classes, or in none, fails the build. Without that check the
partition is a paragraph, and a paragraph is what lets a field quietly become nobody's job.

#### Proving `recovers_material_fields` rather than asserting it

**The mechanism is `parse()`'s blindness (§4.1) plus a golden divergence test in CI.**

```
For each run-fact field F in adapter.recovers_material_fields:
    invocation_A = plan(benchmark, system, conditions with F = value_1)
    invocation_B = plan(benchmark, system, conditions with F = value_2)   # differs ONLY in F
    log_A = execute(invocation_A, limits);  log_B = execute(invocation_B, limits)
    cond_A = parse(log_A);                  cond_B = parse(log_B)

    ASSERT cond_A[F] == value_1 and cond_B[F] == value_2
    ASSERT cond_A and cond_B differ in F and in no other material field
```

Any field that fails either assertion is **removed from `recovers_material_fields`** and recorded as
`null` on every claim the adapter produces, which then penalises `condition_completeness` honestly.
The test runs against cheap, tiny benchmark slices on every adapter change and on every pinned
harness version bump; a fixture-based variant (recorded logs, no API calls) runs on every PR, so the
expensive form stays out of the inner loop.

#### Inspect `.eval` log → `EvalConditions` mapping

*(unverified — confirm against a pinned `inspect-ai` version before writing the adapter. The
`.eval`-side field names come from Inspect's published log structure as summarised in
[recon:landscape] and [recon:ai-features], not from a log this team has parsed, and Inspect's schema
has been moving. Our-side names follow [04-data-model.md](04-data-model.md) §"The material fields"
and its EEE crosswalk.)*

| `.eval` log field | Maps to | Note |
| --- | --- | --- |
| `eval.model`, `eval.model_base_url` | System resolution + `environment.provider_endpoint` | Not a condition; it identifies the subject |
| `eval.model_args` | `provider_snapshot` where the provider exposes one; otherwise provider-specific args | The most likely place a dated snapshot id appears |
| `eval.config.epochs`, `eval.config.epochs_reducer` | `n_samples` / `k` and `selection_strategy` | The `pass^k` / `pass@k` distinction lives here |
| `eval.config.message_limit`, `token_limit`, `time_limit` | `message_limit`, `token_limit` (04's names; EEE's `eval_limits.*`) | Material for agentic benchmarks |
| `eval.config.max_connections`, `max_samples` | *(not recorded)* | Throughput, not a condition |
| `eval.task_args` | `subset_used`, `shots` where the task exposes it | Task-specific; the mapping is per-task and must come from the task definition, not a guess |
| `plan.steps[].solver` + params | `scaffold`, `chain_of_thought`, `tools_allowed`, `retries_allowed`, and the structural `human_in_loop: false` | The solver chain *is* the scaffold; this is the field Inspect gives us that nothing else does |
| `plan.config` (GenerateConfig) | `sampling.temperature`, `top_p`, `max_output_tokens`, `reasoning_effort` | `reasoning_effort` as the enum-plus-free-text 04 defines, whose starting vocabulary came from Epoch's observed `max/xhigh/high/medium/low/minimal/none` |
| `eval.sandbox` | `sandbox` type; the compose file goes to the artifact store | Matches 04's existing EEE alignment, which stores the type and links the compose file |
| `eval.packages`, `eval.revision` | `harness`, `harness_commit` | |
| `results.scores[].name / scorer / reducer / metrics` | `metric`, `judge_model` where the scorer is model-graded | PaperBench-shaped benchmarks live or die on this row, and 04 weights `judge_model` at 2.0 for exactly this reason |
| `stats.started_at / completed_at`, `stats.model_usage` | `cost.wall_clock_hours`, `input_tokens`, `output_tokens` | Feeds `estimated-from-tokens` before reconciliation (§5.3) |

**Fields Inspect does not give us as run facts**, and what happens to each: `training_data_policy`
and `eligibility_track` are **entry facts** answered by the curator; `decontamination_applied` is a
run fact only where the task itself performs decontamination and records it, and an entry fact
otherwise; `provider_snapshot` is **absence-answerable** (§4.5). Naming them here is the point — an
adapter that quietly filled any of them from our own YAML would pass every test and publish a lie.

The counter-example this exists to refute is the ecosystem norm of `null` fields and prose notes like
Epoch's `"Assuming medium based on GPT-5 being run at medium"` or `"Couldn't find shot count"` — the
latter appearing on a column filled for 5.7% of rows.

### 4.5 The fundamental limit, and how the schema should handle an absence

A `sandboxed-rerun` against a hosted API is reproducible only to the extent that the endpoint is. An
API model identifier is not a fixed artifact: providers update, quantise, re-route and re-tune behind
a stable name, and a rerun six months later can differ with no way to attribute the change to the
model versus the harness.

The earlier draft said to record `null` where a provider exposes no dated snapshot and "let
`condition_completeness` take the hit" — while §8 simultaneously required *every* self-produced claim
to reach completeness 1.0. Those two statements cannot both be true. **Decided here.**

> **`provider_snapshot` is material but conditionally satisfiable.** Add it, and its companion
> **`provider_snapshot_available: true | false`**, to the hosted-API comparability profile in
> `taxonomy/comparability-profiles.yaml` — not to a global material set, since neither field means
> anything for a robotics simulator benchmark. A run against a provider that publishes no dated
> snapshot records `false` explicitly, and that counts as *complete*, because the field was
> answered. A `null` does not count, because `null` means nobody looked.
>
> **The schema penalises unknowns, not absences.**

That works inside 04's existing formula without changing it: `condition_completeness` sums the
weights of material fields where `conditions[f] is not None`, and `false` is not `None`. The one
sentence above is worth more than the paragraph around it and should appear in
[04-data-model.md](04-data-model.md)'s `condition_completeness` section verbatim. It generalises:
wherever a material field can be genuinely inapplicable rather than merely unrecorded, the schema
gets an explicit `*_available` or `*_applicable` companion rather than overloading `null` with two
meanings. Overloading `null` is how a completeness score stops measuring anything.

This is a real ceiling on the authority of the whole verification level and it belongs on the methods
page, not in a critic's review. Open-weights systems evaluated from a pinned model hash do not have
this problem, which is a genuine argument for weighting the first adapters toward open-weights
systems — but that pushes toward `single-gpu`/`multi-gpu` compute tiers, which the scope gate
excludes. The honest resolution is to accept the ceiling, document it, and prefer providers that
publish snapshot identifiers.

### 4.6 Repetition policy

The earlier draft showed `n_runs: 5` in an example and never said where five came from. Policy:

- **`n_runs = 1` by default.** Repetition is expensive and most benchmarks do not require it.
- **Where the benchmark declares a metric requiring *k* independent trials** — τ²-bench's `pass^k`,
  any `pass@k` with sampling, any reliability metric — **`k` is read from the `Benchmark` entity, not
  chosen by the operator.** `repetition.k_source` records which of the two happened.
- **`n_runs` and the aggregation rule are material fields**, mapping onto the existing
  `selection_strategy` / `k` / `n_samples` material set in [04-data-model.md](04-data-model.md), and
  they feed `comparability_key`. A mean of five samples and a single sample are not comparable
  numbers and the key must say so.
- **The cost ceiling is checked against `n_runs × est_cost_usd.max` before the run starts**, not
  discovered during it (§5.2).

### 4.7 Interoperability with Every Eval Ever, costed honestly

[04-data-model.md](04-data-model.md) §"Crosswalk to Every Eval Ever" owns the field mapping and it is
not restated here. What this phase adds is the serialisation: the `RunRecord` should also serialise
to EEE's `eval.schema.json`, including `detailed_evaluation_results` as instance-level JSONL — the
one field our per-item artifact populates and that almost no other source in the landscape can
*(unverified — confirm against `eval.schema.json` at a pinned version; the field name comes from
[recon:landscape], not from the schema file)*.

**Reason:** a run that validates against EEE can be contributed upstream to the result registry we
have positioned ourselves as the benchmark-registry counterpart to. They own the result record; we
own the benchmark entity. That turns every run into an alliance deposit instead of a private
artifact.

**What it actually costs.** An earlier draft said "roughly zero marginal cost", which is the kind of
optimism this plan punishes elsewhere. The honest figure: **one serialiser, roughly 8–16 hours, plus
a recurring check whenever their schema version changes.** Small, but not free, and it is a
dependency on a project with its own half-life. Three requirements follow:

1. `interop.eee_schema_version` is recorded **inside every `RunRecord`**, so a future reader knows
   which contract the serialisation satisfied.
2. A **vendored copy of `eval.schema.json`** lives in the runner repository at a pinned version, and
   a CI conformance test validates a fixture `RunRecord` against it.
3. A quarterly check for upstream schema drift, on the same cadence as the source-adapter freshness
   sweep in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md), so drift surfaces as a
   failing test rather than as a rejected upstream contribution.

---

## 5. Isolation, safety and cost control

### 5.1 Environment integrity

**Containerised, pinned by digest.** Never by tag. The container digest, harness commit and lockfile
hash all appear in the `RunRecord`. A run whose environment cannot be reconstructed is not evidence.

**Network egress allowlist.** No network beyond declared model endpoints and declared benchmark
assets. This is partly integrity (an agent that can reach the open web on a benchmark that assumes it
cannot is running a different benchmark) and partly containment.

**Secrets never in the data repo.** The scrapers in
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) run as GitHub Actions cron *in the
data repo itself*, which is correct for them — the runner must not inherit that arrangement. Runner
credentials belong in a separate repository or a protected environment with required reviewers, with
a token scope that cannot write to `data/`. **Reason:** the scraper token's blast radius is a bad PR;
a runner token's blast radius is a provider bill.

### 5.2 Cost ceilings: a stack, not a check

"Enforced in the runner" is not a mechanism. A runner cannot enforce a ceiling on an agent loop whose
token consumption it does not observe in real time, many harnesses surface spend only at the end, and
a ceiling enforced only inside a process that can itself crash is a ceiling that fails exactly when
it is needed. The arithmetic is not hypothetical:

- SWE-bench Verified is catalogued at `est_cost_usd: {min: 50, max: 2000}` for a single system.
- τ²-bench's `pass^k` requires *k* independent trials, so cost multiplies by *k* before anything else
  (§4.6).
- PaperBench grades against a hierarchical rubric reported at roughly 8,316 leaf nodes with an LLM
  judge *(unverified — the figure appears in [recon:domains] and in 04's material-field table)*;
  grading can cost more than generation, and the judge model is itself a recorded condition.
- OSWorld, Terminal-Bench 2.0 and the step-budgeted agent loops generally are benchmarks where a
  single misconfigured `retries_allowed` changes the bill by an order of magnitude.

Four layers, each catching what the one below it cannot:

| Layer | Mechanism | Catches | Does not catch |
| --- | --- | --- | --- |
| **1. Provider-side hard cap** | A **dedicated API key per run**, provisioned with a provider-side hard spend limit where the provider offers one | Everything, including our own process hanging, crashing or losing track of spend. **This is the only ceiling that holds when we are not watching** | Providers that offer no per-key hard cap — record which ones, and treat them as higher-risk in the run plan |
| **2. In-adapter token metering** | Token counters checked **between agent steps**, against `n_runs × est_cost_usd.max` computed before the run starts | Runaway agent loops, retry storms | A single enormous call that blows the budget in one request |
| **3. Wall-clock watchdog** | A supervisor outside the container kills it at a hard deadline | Hangs, deadlocks, an infinite loop that makes no API calls but burns the clock | Fast, expensive spending inside the deadline |
| **4. Monthly cap** | Enforced by **key provisioning**, not by code: a monthly budget is allocated to keys, and when it is exhausted no new key can be minted | Cumulative drift across many runs, and the "each run was fine, the month was not" failure | Nothing relevant — but it requires a human to re-provision, which is the point |

**A tripped ceiling produces a failed run record, not a partial claim.** A partially-executed
benchmark must never produce a `ResultClaim`; it produces an incident note in the runner repository
and a line on the spend page. The failure mode to avoid is a truncated run quietly becoming a low
number that someone later cites.

### 5.3 What `cost_source: measured` means

Undefined, "measured" is a word that sounds like evidence. Provider usage APIs are per-key and lag by
hours, so at the moment a `RunRecord` is written, nothing has been measured — only estimated from
token counts the harness reported.

> **`cost_source: measured` means: reconciled against the provider's usage record for that run's
> dedicated API key, within 7 days of the run.** The reconciliation timestamp is recorded in
> `cost.cost_reconciled_at`. Anything unreconciled stays `estimated-from-tokens`, permanently, and
> the spend page shows the two classes separately.

The dedicated-key-per-run design in §5.2 layer 1 is what makes this possible at all: a shared key
cannot be attributed to a run, so a shared key can never produce a `measured` cost.

### 5.4 Contamination: the runner is a leak vector, and this is the phase's sharpest tension

Hard constraint 1 has two stated rationales. The first is licensing. The second is *"avoids
contributing to test-set contamination"* — and **every hosted-API rerun transmits benchmark items to
a provider that may log them, retain them, and train on them.** A project whose founding constraint
is partly about contamination cannot build an execution layer without addressing this directly.

Four rules:

1. **Maintainer policy is respected, and it is a curation field, not a run-time judgement.** Add
   **`execution.maintainer_rerun_policy`** to the `Benchmark` schema, populated during curation from
   the benchmark's own stated terms: `unrestricted` | `no-third-party-endpoints` | `contact-first` |
   `unstated`. **We never execute a benchmark whose maintainer has asked that items not be sent to
   third-party endpoints**, and `contact-first` blocks the run until there is a recorded answer. This
   is a field on the benchmark record precisely so the decision is made once, by a curator reading
   the terms, rather than by a runner at 3am.
2. **Prefer zero-retention endpoints.** Where a provider offers zero-data-retention or
   no-training-on-input terms, use them, and record which terms applied in
   `environment.provider_data_policy`. Where they do not, that fact is on the claim.
3. **Publish where our items went.** A per-benchmark line on the methods page stating which of our
   runs transmitted items to which providers under which retention terms. Anyone worried about
   contamination of a benchmark we ran should be able to find out from us before they find out from
   a paper.
4. **`unstated` is not permission.** For benchmarks with a hidden or held-out component, the default
   is not to run, because the cost of being wrong is destroying a benchmark for everyone.

**Name the failure mode:** the catalogue that refuses to host data becomes the thing that leaks it,
one API call at a time, and finds out from somebody else's contamination paper.

### 5.5 When our number disagrees with theirs: the pre-publication notification rule

This is the most predictable incident in the phase and the earlier draft had a `disputed` flag and no
procedure. The first time a rerun lands materially below a lab's published score, that lab will
respond publicly, and the reputational outcome depends entirely on whether a process existed
beforehand. §7 rightly calls benchmark maintainers "the people whose corrections we depend on" — and
then gave them no channel.

> **Divergence threshold.** A self-produced claim that differs from a published claim on the same
> benchmark, metric and subset by **more than 2× the reported standard error**, or — where no stderr
> exists — **more than 5 percentage points absolute**, is a *divergent claim*.

The procedure for a divergent claim:

1. **Merge is blocked.** CI labels the PR `divergent-claim` and the branch protection rule requires
   the label to be cleared.
2. **A public issue is opened** in the data repository carrying the full `RunRecord`, the
   `comparability_key` diff against the published claim, and the transcript link.
3. **The benchmark maintainer and the system's publisher are notified**, with a link to that issue.
4. **A fixed waiting period of 10 working days** before merge, whatever the response.
5. **Their response is recorded on the claim** — as a `Source` and a note — whether or not it changes
   the number. A maintainer who says "your scaffold is wrong" and a maintainer who says nothing
   produce different records, and both belong on the claim.

**Name the failure mode:** the way this goes wrong is publishing a low number, being told our
scaffold was the problem, and being right about the mechanism but wrong about the conclusion — in
public, once. Ten days and an issue thread cost almost nothing; the alternative costs the project's
standing with exactly the people whose corrections the whole index depends on.

### 5.6 Dangerous-capability carve-out

The project does not execute offensive-security, dual-use or hazardous-knowledge benchmarks. It
catalogues them and links to them. That covers Cybench (reported as 40 professional CTF tasks, with
frontier models near 93% in 2026 — *unverified, confirm before relying on this*), AgentDojo (reported
as 97 user tasks and 629 security cases — *unverified*), AgentHarm, HarmBench, JailbreakBench, WMDP,
ABC-Bench and the cyber-range family.

**Reason:** running these responsibly requires a threat model, verified network isolation, a
disclosure policy and an institutional counterparty — the things UK AISI, Apollo and METR have and a
two-person catalogue does not. Getting it wrong once is unrecoverable, reputationally and possibly
legally. **Risk:** this leaves a visible hole in our own `sandboxed-rerun` coverage in the safety
domain. §1.2 sizes it: it is essentially the whole safety-alignment seed allocation, the
second-largest single subtraction in the five-clause gate. Accept it and say why on the page.
Cataloguing a benchmark and declining to run it is exactly the behaviour the project's comparability
thesis already endorses.

### 5.7 Provider terms and external standards

**Provider terms of service.** Running a benchmark suite against a commercial API may or may not sit
within a given provider's acceptable-use terms, particularly for benchmarks designed to elicit
refusals or unsafe behaviour (unverified — confirm per provider before the first run, and record the
answer on the methods page rather than assuming it).

**Standards to follow rather than invent.** [recon:landscape] records that NIST/CAISI published
**AI 800-2 ipd, "Practices for Automated Benchmark Evaluations of Language Models", January 2026**,
observed live on 2026-09-17. It is the obvious reference for run methodology. Note that `ipd` is an
initial public draft, so the final document may carry a different number and date — **check the
current designation before citing it in public.** Aligning with it costs nothing while making the
results legible to exactly the regulatory audience the EU AI Act's GPAI obligations created: those
became enforceable **2026-08-02** and require evaluation "using standard benchmarks and
state-of-the-art tests" with no registry defining what qualifies. That vacuum is one of the
project's stated reasons for existing
([01-landscape-and-positioning.md](01-landscape-and-positioning.md)). It is not a reason to run
evaluations; it is a reason for the run methodology to be legible when we do.

---

## 6. Cost honesty

**Every run publishes its cost. Aggregate spend appears on a public page.**

The index publishes other people's `est_cost_usd` and `est_runtime_hours` as first-class benchmark
fields. An index that publishes others' evaluation costs and hides its own would be inconsistent in a
way that the project's whole premise makes conspicuous.

There is a second, stronger reason. Cost has become a comparability condition in its own right, and
the field is converging on it faster than on anything else:

- ARC-AGI publishes **cost per task alongside score**.
- The Open ASR Leaderboard publishes **RTFx next to WER**, so a score without hardware is meaningless.
- Berkeley Function Calling Leaderboard v4 publishes **cost and latency alongside accuracy**.
- Ai2's AstaBench is explicitly **cost-adjusted**.
- Princeton HAL's entire contribution was **accuracy-versus-cost Pareto fronts** — and
  [recon:landscape] identifies it as the single best existing evidence for this project's
  "conditions as first-class data" differentiator.
- GDPval reports that models complete tasks roughly **100× faster and 100× cheaper** than the human
  experts they are compared against *(unverified — confirm before relying on this)*, which is half
  the finding.

A rerun that does not publish its cost is publishing an incomplete claim by the field's own emerging
norm. Put the spend page at a stable URL; include a per-benchmark and per-month breakdown, the
inference/storage split (§4.3), and the `measured` versus `estimated-from-tokens` split (§5.3); and
let it be embarrassing when it is embarrassing.

**Funding disclosure.** If compute or API credits are donated, the donor is recorded on every claim
the donation paid for, via a claim-level `funding_disclosure` field, and surfaced in the UI next to
the verification badge. **Failure mode to avoid:** a vendor donates credits, the project runs mostly
that vendor's models because they are free, and the index quietly becomes a vendor's verification arm
without anyone deciding to do that. The `governance.independence_flags` concept already exists for
benchmarks; this is the same idea applied to ourselves.

---

## 7. What is explicitly not built

| Not built | Why |
| --- | --- |
| **A hosted evaluation service** | Not a product, and it creates a permanent obligation to keep other people's runs working. That obligation is what turned HAL's leaderboard off |
| **A GPU fleet** | `api-credits-only` benchmarks first. Local-weight benchmarks only if someone donates compute, and then under the funding-disclosure rule in §6 |
| **A leaderboard-of-record** | The project verifies; it does not host competitions. Competing with benchmark maintainers converts every maintainer from a potential ally into a rival, and they are the people whose corrections we depend on |
| **Third-party *runs*** | We accept third-party **claims** through the bot-validated issue form in [05-repository-and-workflow.md](05-repository-and-workflow.md) §6, at `self-reported` or `independent-reproduction`, evidenced like any other claim. We do **not** accept third-party **runs** for the `sandboxed-rerun` level, because that level's entire meaning is that *this project* controlled and recorded the environment. Verifying someone else's container is the hosted-service obligation we are declining — and accepting submissions is the specific mechanism by which HAL, Dynabench and the Open LLM Leaderboard acquired an operational load they could not sustain |
| **Our own held-out test set** | That would make this project a benchmark maintainer — a different job with a different failure mode — and it would require hosting evaluation data, which hard constraint 1 forbids |
| **A "run on every model release" firehose** | Unbounded scope, unbounded cost, and it recreates the treadmill the deferral exists to avoid. Scheduled reruns are limited to a small, named, published high-value set |
| **Physical, wet-lab or human-rater execution** | Ever. No exceptions, no pilots, no "just once for CACHE." |
| **Offensive-security or dual-use execution** | See the carve-out in §5.6 |

---

## 8. Sequencing within the phase, its cost, and the stopping rule

| Step | Deliverable | Exit condition | Effort |
| --- | --- | --- | --- |
| 0 | Run the five-clause gate query (§3) and record the count | The count is published with its query, and the §3.2 threshold is met | **4–8 h** |
| 1 | Adapter ABC + **Inspect** wrapper covering 3–5 gate-passing benchmarks, with the §4.4 divergence test and the field-class partition check in CI | A `RunRecord` produced end-to-end with a pinned digest, a published transcript, a measured cost, and a `recovers_material_fields` set proven rather than asserted | **60–110 h** |
| 2 | Claim write-back through the normal PR review flow + R2 artifact store + integrity checks | A machine-generated `ResultClaim` merged after human review, with zero direct writes to `data/` | **30–55 h** |
| 3 | A second adapter of a genuinely different shape — a containerised agentic harness — plus the full §5.2 cost stack and per-run key provisioning | The interface generalises beyond multiple-choice without special-casing, and a deliberately runaway test run is stopped by layer 1, not by luck | **60–110 h** |
| 4 | Scheduled reruns of a small, named, published high-value set; the public spend page; the methods page; the §5.5 divergence procedure | The set is published, bounded and has an owner; the spend page is live | **35–65 h** |
| — | **STOP** | — | **Phase total: 190–350 h**, plus **3–8 h/month recurring, indefinitely** |

**Reconciled with [14-roadmap.md](14-roadmap.md), and applied there.** Its phase table previously
sized Phase 7 at **8–14 weeks**, which at the plan's own 20 h/week is 160–280 hours, against this
document's bottom-up **190–350 hours**. The ranges overlapped and the tops differed by 25%. The
bottom-up figure wins — it was built from steps rather than from a week count, and the roadmap's own
text says Phases 5–7 are "sized for information, not committed" — so `14`'s Phase 7 row now reads
**10–18 weeks**. 190 h ÷ 20 = 9.5 and 350 h ÷ 20 = 17.5; both ends are rounded outward to whole weeks
so that neither end is quietly flattered, which is the same convention `14` §Effort applies to its
own totals.

**Exit criteria for the phase as a whole:**

- ≥10 benchmarks producing `sandboxed-rerun` claims through the **normal contribution path** (this
  matches [14-roadmap.md](14-roadmap.md)'s Phase 7 exit, which owns it, and uses its wording
  deliberately: machine-generated claims will in fact arrive as pull requests, but an exit criterion
  written as "the PR path" reads as an endorsement of PR-only contribution, which is the friction
  correction C2 exists to prevent).
- ≥2 adapters, one of them agentic/containerised.
- **Every self-produced claim at `condition_completeness == 1.0` across its benchmark's material
  profile**, under §4.4's three-class partition — run facts recovered by `parse()`, entry facts
  answered by the curator, absences answered explicitly (§4.5) — with `null` counting as unanswered.
  If our own runs cannot hit 1.0 under that definition, the profile's material-field list is wrong
  and that is the finding.
- A live public spend page showing inference, storage, and the `measured` / `estimated-from-tokens`
  split.
- Zero privileged writes to `data/`, verified by the same CI that gates contributor PRs.
- The §4.4 divergence test green for every field in every adapter's `recovers_material_fields`, and
  the field-class partition check green for every comparability profile.

### 8.1 The stopping rule — and the total, not just the margin

The marginal argument is easy and it is not the one that decides the phase. At the planning rate of
**30–90 minutes** per fully sourced entry, and 2–3 hours for the hard stress-test cases,
a hundred more entries is on the order of **50–150 hours**. That rate is
[recon:domains]'s judgement and **has never been measured**;
[14-roadmap.md](14-roadmap.md) §Effort owns it, carries the confession, and carries the 20-entry
checkpoint that will replace it with a measurement. Every comparison below inherits that uncertainty,
which is why the conclusion is stated as a margin no reasonable reading closes rather than as a
number. A fifth adapter is
comfortably 40–80 hours to build plus indefinite maintenance, and it buys a handful more numbers in
the one domain cluster where every competitor already has numbers. The marginal comparison is not
close.

**The total comparison is worse, and it is the honest one.** Every figure it needs is owned by
[14-roadmap.md](14-roadmap.md)'s effort table, as recomputed by decision D2 on 2026-09-21:

| Quantity (owner: [14-roadmap.md](14-roadmap.md) §Effort) | Value |
| --- | --- |
| Whole project to public v1, phase-scoped work (its Block A) | **~490–1,080 person-hours** |
| The same, all-in, including the taxonomy authoring, discovery sweeps and outreach that run alongside every phase (its Block A + B) | **~715–1,535 h** |
| Of which hand-curation of entries and claims | **273–688 h**, 56–64% of Block A at both ends |
| The 320-entry seed corpus | **175–495 h**, i.e. a blended 33–93 minutes an entry |
| This phase (§8, bottom-up) | **190–350 h** |

Comparing like ends with like ends:

- The execution layer costs **32–39% of the phase-scoped cost of building the index** (350/1,080 and
  190/490), or **23–27% of the all-in cost** (350/1,535 and 190/715). Both framings are given because
  the smaller one is the one a proponent will reach for, and it is still not small.
- It costs **51–69% of the entire v1 hand-curation budget** (350/688 and 190/273).
- At the seed corpus's own blended rate it is **roughly 180–330 forgone curated entries** — between
  half the seed corpus and all of it. Pairing the extreme ends of both ranges instead of matching
  them, the band is 120–640.

**Say it plainly: on today's numbers, the total argues against step 1.** The phase should not happen
unless the §0 adoption gate and the §3.2 threshold both clear, and those gates exist precisely
because they are the only conditions under which this arithmetic changes — external adoption means
the claims are being used, and ≥70 gate-passing benchmarks means the yield per hour is real rather
than notional. §3.2 already shows the second gate failing at seed scale, so the realistic reading is
that this is a maturity-corpus question and not a v1.x one.

If either gate fails, the correct action is not a smaller runner. It is 180–330 more curated entries
in robotics, chemistry, climate, medicine and physics — where the differentiating core is **106
entries targeted** across robotics-embodiment, biology-genetics, chemistry-materials, physics and
earth-climate ([02-taxonomy.md](02-taxonomy.md) §3's allocation, against [recon:domains]'s estimate
that roughly 120 Tier-1 families exist there), or **144 across the seven Core families** with a
launch gate of 130 ([14-roadmap.md](14-roadmap.md)). Nobody has laid those on one map with a shared
vocabulary. Doubling that core is a better use of 190–350 hours than ten `sandboxed-rerun` claims on
LLM benchmarks, by a margin no reasonable reading of these numbers closes.

### 8.2 The kill switch

If two consecutive quarters pass in which no `sandboxed-rerun` claim is cited, refreshed or used by
anyone, archive the runner, mark the affected claims with their last-verified date, and say so on the
page. The project publishes a liveness and deprecation signal for every benchmark it catalogues
because nobody else does — [recon:landscape] records a study finding 137 of 195 safety benchmarks
with stale repositories, and BetterBench finding 17 of 24 with no working reproduction scripts.
Applying that same standard to our own infrastructure is the cheapest possible proof that the signal
means something. A project that marks other people's dead repos and hides its own is not a
trustworthy index.

---

## 9. Preconditions

Nothing here can start until these exist. Listed so the dependency is explicit rather than
discovered.

| Precondition | Owner | Must land by |
| --- | --- | --- |
| `execution.reproducibility_tier` and `compute_tier` populated across the corpus | [04-data-model.md](04-data-model.md) | Phase 0 schema; populated through curation |
| `ResultClaim.artifact_url` and `provenance_snapshot` | [04-data-model.md](04-data-model.md) | **Phase 0** — already required before the Epoch ingest |
| `Benchmark.runnable_via` and `inspect_evals_id` | [04-data-model.md](04-data-model.md), populated by [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) | **Phase 0** — see §3.1; the suite builder needs `runnable_via` at Phase 6 |
| `Benchmark.execution.maintainer_rerun_policy` | [04-data-model.md](04-data-model.md), populated during curation | **Phase 0** — see §5.4; retrofitting a policy field across ~1,500 records is the same trap |
| `provider_snapshot` + `provider_snapshot_available` in the hosted-API comparability profile, and the "penalise unknowns, not absences" rule | [04-data-model.md](04-data-model.md) | **Phase 0** — see §4.5; it changes how `condition_completeness` is computed |
| The three-class partition of material fields (run fact / entry fact / absence-answerable) and its CI totality check | [04-data-model.md](04-data-model.md), [05-repository-and-workflow.md](05-repository-and-workflow.md) | **Phase 0** — see §4.4; the §8 exit criterion is unreachable without it |
| Correction to 04's Epoch machine-assignment counts: the `-private`-or-blank rule covers **722** rows, not 459 | [04-data-model.md](04-data-model.md) | **Phase 0** — before the Epoch adapter is written; see §2 |
| ADR-NN: verification ladder axes, plus a decision log for 04 if ADRs stay taxonomy-scoped | [04-data-model.md](04-data-model.md), [03-taxonomy-build-process.md](03-taxonomy-build-process.md) | Phase 0 |
| A seventh `--c-verif-*` token in 04's order, and a colour for `prospective-experiment` | [09-design-system.md](09-design-system.md) | Phase 2 — a live drift today, independent of whether this phase ever happens |
| `comparability_key` computation in the build | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) | Phase 1 |
| Bot → auto-PR → human review pipeline | [05-repository-and-workflow.md](05-repository-and-workflow.md), [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) | Phase 2 |
| Cloudflare R2 provisioned as a content-addressed artifact store, plus a public methods/spend page. **08 does not currently cover R2; this is new scope for it** | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) | This phase, step 2 |
| OpenAlex and Semantic Scholar API keys for the §0.2 citation instrument | [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) | Before the first quarterly adoption measurement |
| Suite manifest export with `runnable_via` honesty | [11-ai-features.md](11-ai-features.md) | Phase 6 |

---

## 10. Open questions carried forward

Recorded here and in [15-open-questions.md](15-open-questions.md), whose §F routing table now carries
all seven: items 1–4 and 6 as one row deferred to the Phase 7 evidence gate, and items 5 and 7 as
rows of their own, because those two have triggers earlier than the gate — item 5 rides on `15` E4's
first outreach action and item 7 belongs with the succession story, which lands before public v1.

1. **Does the five-clause gate query ever return ≥70 entries?** §3.2 now answers this provisionally
   and unfavourably: roughly 25–45 at the 320-entry seed, roughly 120–210 at the 1,500-benchmark
   maturity corpus, both family-level estimates. The open question is the *record-level count*,
   which cannot exist before the corpus does. The rule itself is settled.
2. **Which providers offer a per-key hard spend cap**, the only cost ceiling in §5.2 that holds when
   our own process fails (unverified — confirm per provider before the first run).
3. **Provider terms of service for automated benchmarking**, especially for safety-adjacent evals
   (unverified — must be confirmed per provider before the first run).
4. **Whether Inspect's `.eval` log schema remains stable enough to depend on**, and which of the
   §4.4 mapping rows survive contact with a real log. It is the de facto standard today; standards in
   this field have a short half-life, and HELM's maintenance-mode notice is the cautionary case.
5. **Whether to contribute `RunRecord`s upstream to Every Eval Ever.** The recommendation is yes —
   it costs 8–16 hours of serialiser plus a recurring drift check (§4.7) and buys a relationship with
   the single best alliance target in the landscape — but it should be a decision made *with* them,
   not at them.
6. **What `maintainer_rerun_policy: unstated` should default to at scale.** §5.4 says do not run
   where there is a hidden component; the question is whether `unstated` should block *all* runs
   until a curator has read the terms, which is safer and slower.
7. **Who runs the runner if the founders stop.** The succession story in
   [05-repository-and-workflow.md](05-repository-and-workflow.md) covers the data. It should say
   explicitly that the execution layer is *not* part of what a fork is expected to inherit: the data
   is the asset, the runner is a convenience, and conflating them would make the fork look harder
   than it is. MedHELM's spin-out is the working model — a vertical that found its own steward
   outlived its parent — and a runner nobody inherits is a cleaner outcome than a runner a fork feels
   obliged to keep alive.
