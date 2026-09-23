# 01 -- Landscape and Positioning

This document exists because of one sentence from the project owner: *"Currently several benchmark
services are running -- especially LM benchmarks so it is very important to avoid repetition."*
That is the right instinct, and it is more urgent than it looks. Between July and September 2026,
three projects launched into ground that an earlier draft of this plan described as empty. A plan
that claims unoccupied territory which is visibly occupied is exactly the unsourced confidence this
project exists to oppose. So this document does six things: it maps the ecosystem by shape rather
than by name, dissects why every prior cross-domain catalogue has died and what the survivors had
in common, defines what "overlap" means before quoting any overlap number, draws a precise boundary
against each high-overlap service, states the legal theory under which a curator may record a fact
at all, and converts all of that into an operational rule a curator can apply before spending an
hour on any entry.

Everything below was verified live on 2026-09-17 unless marked otherwise. Facts carried over from
the reconnaissance reports keep their uncertainty markers; where two reports disagreed, both
figures appear and the disagreement is named. **Every statement in this document about a named
project is a snapshot of a live service on that date, never a permanent property of it** — the
services described here are actively developed by people who can falsify any of these sentences in
an afternoon, and §1.9 states exactly how far the negative claims are supported.

**The rule this document holds itself to.** Every number here derived from a local artifact names
the artifact, the filter that produced it and the date. Every number derived from a judgement says
so. A claim that cannot be recomputed is the thing this project exists to oppose, and a positioning
document that quotes seven percentages by assertion has already lost the argument it is trying to
make. Where a figure is owned by another document, it is linked rather than restated -- the failure
mode that produced three different seed totals across three documents was everybody paraphrasing
everybody else's arithmetic.

---

## 1. The headline correction

The earlier draft rested on a premise that is false as stated. Three projects now occupy adjacent
or overlapping ground, all launched after most model training data was collected, which is why the
premise survived so long unexamined.

| Project | Launched | Scale | Access | Licence | Overlap band (§4) |
| --- | --- | --- | --- | --- | --- |
| **BenchmarkList** (benchmarklist.com) | 2026-07-15 | 2,545 benchmarks, 1,604 providers, 24,074 models | No API, no bulk download, no repository | **None stated** | **High** |
| **Benchmark Radar** (benchmark-radar.org, arXiv 2609.11115) | 2026-09-10 | 14,810 raw records; ~1,283 curated source records, 12,916 numeric observations across 790 records | GitHub Pages, ZIP, HF dataset, RSS, CLI | Code MIT, **content CC BY-NC-SA 4.0** | **High** |
| **Every Eval Ever / EvalEval** (arXiv 2606.14516) | 2026-06-12 | 22,235 models, 2,273 benchmarks, 31 evaluation formats | HF `evaleval/EEE_datastore`, GitHub, `validate` CLI | **Data CC BY 4.0, code MIT** | **Complementary** |

BenchmarkList is genuinely cross-domain -- verified entries include Open Catalyst OC22 (78 models,
six metrics, imported from the official leaderboard JSON) and GEO-Bench 2 -- and is built by a
two-person indie team with no institutional affiliation. It is also entirely closed, and its
signature feature is an "Experimental Capability Index" built with a "Rosetta Stone method" that
aligns overlapping benchmark results onto a single scale. That is precisely the universal ranking
this project refuses to build.

Benchmark Radar is architecturally almost identical to this plan -- static site on GitHub Pages,
git-backed, daily updates, 37 ingestion sources (13 API connectors plus 24 first-party lab feeds).
Its content licence is CC BY-NC-SA 4.0, which blocks commercial and institutional reuse and makes
it unusable as infrastructure by a company, a regulator, or a commercial eval vendor. It is also
LLM-centric by its own abstract: no robotics, no protein structure, no climate, no materials.
**Do not ingest its content.** The share-alike clause is incompatible with a CC-BY core.

Every Eval Ever is the important one, and it is not a competitor. It models *results*, not
*benchmarks*: there is no benchmark-entity catalogue, no domain taxonomy, no non-language domains.
It is backed by HuggingFace, the University of Edinburgh and EleutherAI, with 48 authors. It is the
best alliance target in the landscape, and §14 says what to do about it.

**The honest version of the pitch.** The unoccupied ground is narrower and more specific than "a
cross-domain catalogue", and it is genuinely still there:

1. **Non-language domains at depth.** Robotics is the single largest unindexed field. CASP/CAMEO,
   Grand Challenge (264 medical-imaging challenges), Matbench Discovery, Open Catalyst,
   WeatherBench 2, GEO-Bench 2 and the entire robotics cluster appear in **no** cross-domain
   catalogue at depth.
2. **Benchmark lineage, versioning and supersession.** OSWorld became OSWorld-Verified *and*
   OSWorld 2.0; Terminal-Bench 2.0 and 2.1 run concurrently; SWE-bench has six variants;
   FrontierMath has four live variants; HELM has eight. Epoch needed a `superseded_by` column and
   filled it on two rows out of 81. Nobody else models it — see §1.9 for exactly how far that
   claim is supported.
3. **Comparability as a refusal mechanism.** Every competitor's instinct is to force
   non-comparable numbers onto one scale. A catalogue whose signature behaviour is *declining to
   rank* is unoccupied ground and the most defensible trust position available.
4. **Liveness and deprecation signalling.** One study found 137 of 195 safety benchmarks had stale
   GitHub repositories; BetterBench found 17 of 24 benchmarks had no working reproduction scripts.
   No catalogue marks a benchmark as dead (§1.9).
5. **A live coverage/gap matrix.** Papers do this once and freeze. The grid itself is owned by
   [12-analytics-and-trends.md](12-analytics-and-trends.md): a coarse 19 x 13 = 247 cells and a
   fine 204 x 44 = 8,976 cells, where 204 is the count of (family, subdomain) pairs and 44 the
   count of capability terms ([02-taxonomy.md](02-taxonomy.md) §3 and §4 own both vocabularies).
6. **The regulatory vacuum.** EU AI Act GPAI obligations became enforceable 2026-08-02 and require
   evaluation "using standard benchmarks and state-of-the-art tests" -- with no registry defining
   what qualifies.
7. **Plain CC-BY.** Nearly unoccupied, and the only licence under which companies, regulators and
   commercial eval vendors can build.
8. **A Croissant benchmark extension.** MLCommons Croissant is the adopted ML-dataset metadata
   standard (HuggingFace, Kaggle, OpenML, TFDS, Google Dataset Search) and has no
   evaluation/benchmark extension. Scoped, sized and scheduled in
   [15-open-questions.md](15-open-questions.md) A8; discussed as a defensibility argument in §13,
   where its main risk is also named.

### 1.9 The four negative claims, and exactly how far they are supported

Four of the eight items above are **negative claims about a live ecosystem** — assertions that
nobody else does something. Negative claims are the most quotable sentences a positioning document
produces and the easiest to falsify, and this project's entire premise is that a confident
unsourced claim destroys trust. So this subsection states the evidence behind each one, once, and
every other document in the plan links here rather than re-hedging in its own words. **Six
documents restating a hedge is six hedges that drift; one owning statement is one.**

| Claim | Where it is used | The evidence, precisely | What would retire it |
| --- | --- | --- | --- |
| **No catalogue marks benchmarks as dead** (liveness and deprecation signalling) | §1 item 4; `02` §8; `07`; `08`; `12`; `14` | The landscape reconnaissance examined roughly a dozen catalogues on 2026-09-17 and found no liveness, staleness or deprecation field surfaced in any of them | One catalogue shipping a maintenance or deprecation field, or one being found to hold one we did not see |
| **Nobody else models supersession or lineage** | §1 item 2; `10` V-detail; `07` | Same survey, same date. Epoch's own export is the strongest counter-evidence *for* the claim, not against it: it needed a `superseded_by` column and filled it on 2 rows of 81 | Any catalogue exposing a supersession edge between two benchmark records |
| **Nothing in the landscape publishes ecosystem or governance analysis** | §1 item 5; `10` V9 | Same survey. BenchmarkList counts 1,604 providers and exposes no analysis over them **through its public interface**; it has no API, so nothing further can be checked | A published provider-level or governance-level analysis from any of the named services |
| **No live coverage/gap matrix exists** | §1 item 5; `12` §5 | Same survey, plus the observation that the academic surveys which do produce coverage matrices publish them once and do not update them | Any catalogue publishing a re-derived coverage matrix on a schedule |

**The three limits on all four, stated plainly.** First, the evidence is *an absence observed across
roughly a dozen catalogues on one day, not a proof that none exists* (unverified — confirm before
relying on this); the survey was not exhaustive and no such survey can be. Second, two of the three
services with the most overlap were inspected **through a rendered web interface**: BenchmarkList has
no API, no export and no schema we can read, so "it does not model supersession" is an inference from
a web page rather than a reading of a data model. Third, Benchmark Radar *does* ship an inspectable
schema through its HuggingFace dataset and CLI, and **nothing in this plan records that anyone read
it** — that is a concrete, cheap piece of verification that should happen in Phase 0, and until it
does, every claim above is weaker with respect to Benchmark Radar than with respect to the others.

**The falsification rule, pre-committed.** One counterexample retires a claim. When a claim is
retired it is struck from this table with the date and the counterexample named, not quietly
reworded, and every document linking here inherits the retraction automatically because it carries
the link rather than the sentence. All four are re-checked at every quarterly release as part of the
landscape sweep, and the check is a named line item rather than an intention. The failure mode being
avoided is the one this project exists to oppose: **a plan that claims unoccupied ground that is
visibly occupied is exactly the unsourced confidence the index is built to replace**, and the two
named competitors are the two parties most motivated to check.

---

## 2. The ecosystem mapped by shape

Names change; shapes determine overlap. Six shapes cover everything found. For each, the question
is not "who is in it" but "what can this shape structurally never do", because that is where our
work has to live.

### 2.1 Live leaderboards and scoring services

| Service | Operator | Coverage | Data access | Licence | Freshness |
| --- | --- | --- | --- | --- | --- |
| **Arena** (ex-LMArena; arena.ai) | Arena Intelligence Inc. (*$150M Series A Jan 2026, ~$1.7B valuation -- unverified, confirm before relying on this*) | 13 leaderboards (Text 696 models, Agent, Vision, WebDev, Search, Document, image/video gen) | HF `lmarena-ai/leaderboard-dataset`, 2.36M rows / 117 MB, parquet per arena | **CC-BY-4.0** | 2026-09-16 |
| **Artificial Analysis** | private company | 30+ evals; Intelligence/Coding/Agentic/Math/Openness indices; text, image, video, speech, music | Data API | Attribution required all tiers; **redistribution requires a commercial contract** | live |
| **Epoch AI Benchmarking Hub + ECI** | Epoch AI (non-profit) | 81 benchmarks in `benchmark_metadata.csv`; hub advertises 390 models; LLM/agent only | CSV/ZIP + Python client (`benchmark_data.zip`) | **CC-BY** | 2026-09-17 |
| **Scale SEAL / Scale Labs** | Scale Inc. | 20+ benchmarks (agentic, frontier reasoning, safety, audio, finance/legal) | None; private prompt sets; models featured "only the first time an org encounters the prompts" | Closed | active |
| **Vals AI** | Vals AI Inc. (*$40M Series A 2026-08-13, ~$400M valuation -- unverified, confirm before relying on this*) | 25+ domain evals (finance, legal, medical, tax, SWE, math) | Results public, no API observed | Not stated | Sep 2026 |
| **LiveBench** | academic team, sponsored by Abacus.AI | 7 categories / 23 tasks, contamination-limited monthly refresh | GitHub, dated CSVs | UNVERIFIED | release 2026-06-25 |
| **SWE-bench** | Princeton/Stanford | 5 leaderboards, 323 result claims (Verified 180, Lite 84, Test 24, Multimodal 22, Multilingual 13) | JSON inlined in page HTML | UNVERIFIED | active |
| **Aider** | single maintainer | polyglot, editing, refactoring | In repo | UNVERIFIED | **2025-11-20 -- ~10 months stale** |
| **OpenRouter rankings** | OpenRouter | Usage/token share, not capability | Data API (JSON) | **CC BY 4.0** | 2026-09-16 |

**What this shape structurally cannot do.** A leaderboard's product is a *ranking of systems on one
axis it controls*. Its incentives run entirely toward freshness and toward the systems its audience
cares about, which in practice means frontier language models. It has no reason to describe
benchmarks it does not run, no reason to record that its own conditions differ from the benchmark
author's, and every reason to compress its axis into a single number a reader can quote. Two of the
nine above have already built exactly such a composite (Epoch's ECI, Artificial Analysis's
Intelligence Index), and a third exists outside this table in §2.6 (BenchmarkList's Rosetta Stone).
A leaderboard also cannot represent the benchmarks it has stopped running, which is why leaderboard
rot is invisible from inside a leaderboard. Finally, the commercially strongest ones are the least
reusable: Scale's prompt sets are deliberately unreproducible, and Artificial Analysis
contractually bars redistribution. We never compete with this shape on freshness. We link to it,
model it as a `Leaderboard` entity, and record what its conditions were.

### 2.2 Evaluation harnesses and frameworks

| Harness | Operator | Coverage | Data access | Licence | Freshness |
| --- | --- | --- | --- | --- | --- |
| **lm-evaluation-harness** | EleutherAI | 60+ academic benchmarks, hundreds of subtasks; 227 task directories of YAML (`num_fewshot`, `output_type`, `metric_list`) | GitHub | **MIT** | active, 4,122 commits |
| **Inspect + inspect_evals** | UK AI Security Institute + Arcadia Impact + Vector Institute | **171 evals** (129 internal, 42 external): coding, cyber, math, reasoning, multimodal, agentic, safeguards, scheming, bias | GitHub; **`/register/` issue-form submission launched 2026-05-08** | **MIT** | pushed 2026-09-17, 674 stars |
| **Stanford HELM** | Stanford CRFM | 26 suites in the public GCS bucket, incl. `robo-reward-bench`, `medhelm`, `finance`, `audio`, `vhelm`, `heim`, `torr` | Anonymous GCS bucket; `run_specs.json` = 95 KB, 2,546 specs | Code MIT/Apache-2.0; **data licence UNVERIFIED** | **maintenance mode since 2026-06-01** |
| **OpenCompass** | Shanghai AI Lab | 70-100+ datasets, ~400k eval questions; CompassHub browser + CompassRank | GitHub | Apache 2.0 (UNVERIFIED) | active; multimodal eval deprecated Apr 2026 to VLMEvalKit |
| **OpenAI Evals** | OpenAI | self-described "open-source registry of benchmarks" | GitHub | "Other" (non-SPDX) | pushed 2026-04-14; 19,469 stars, 340 open issues |
| **MTEB** | community | embeddings across languages and modalities | GitHub + HF; results repo **CC0-1.0**, ~600 MB | Apache-2.0 | pushed 2026-09-16 |
| **promptfoo / Braintrust / LangSmith / DeepEval / RAGAS** | various | test-execution infrastructure | mixed | mixed (promptfoo core MIT; *acquired into OpenAI Frontier March 2026 -- unverified, confirm before relying on this*) | active |

**What this shape structurally cannot do.** A harness catalogues what it can *run*. Its registry is
implementation-gated: an eval exists to it only once someone has written the adapter, which means a
CASP protein-structure round, a Matbench Discovery submission or a physical robot manipulation
suite can never enter one. It also carries no metadata about benchmarks it has not implemented,
and no vocabulary that spans harnesses -- `num_fewshot` in lm-evaluation-harness and
`max_train_instances` in a HELM `adapter_spec` are the same concept with different names, and
nothing in the ecosystem reconciles them. Harnesses are the *richest* source of evaluation
conditions in existence and the *worst* possible catalogue. HELM's `run_specs.json` alone contains
`max_train_instances` (shots), `chain_of_thought_prefix` (CoT on/off), `temperature`, `num_outputs`,
`num_train_trials` and `model_deployment` -- which is the comparability key, already structured,
already public. Our relationship to this shape is extraction and reconciliation, never competition.

### 2.3 Result-and-trend hubs

| Hub | Operator | Coverage | Data access | Licence | Freshness |
| --- | --- | --- | --- | --- | --- |
| **Every Eval Ever** | HuggingFace + Edinburgh + EleutherAI (EvalEval Coalition) | 22,235 models, 2,273 benchmarks, 31 formats; full result-side conditions schema | HF datastore + GitHub, PR-based with adapters and a `validate` CLI | **Data CC BY 4.0 / code MIT** | 659 commits, 117 stars |
| **Evaluation Cards** (arXiv 2606.09809) | EvalEval-affiliated group, 48 authors | 5,816 models, 635 benchmarks, 101,843 results; four interpretive signals incl. **score comparability** | paper + data | **CC-BY-SA 4.0** | 2026-06-08 |
| **Epoch ECI / EDI** | Epoch AI | 266 models, 58 benchmarks, IRT/Rasch latent-ability fit, 500 bootstraps, anchored Claude 3.5 Sonnet = 130 / GPT-5 = 150 | CSV + `eci_bootstraps.json` (3.81 MB) | **CC-BY** | 2026-09-17 |
| **Stanford HAI AI Index 2026** | Stanford HAI | annual PDF, Ch.2 Technical Performance | PDF | mixed | annual |
| **OECD Catalogue of Tools & Metrics** | OECD | governance and trustworthiness tools, **not capability benchmarks**; explicit disclaimer that entries are "not vetted or endorsed" | web | open submissions | rolling |

**What this shape structurally cannot do.** These model the *result record* and the *trend line*.
They are the closest thing to our data model, and the gap is precise: none of them has a benchmark
entity. Every Eval Ever's schema has no domain, no modality, no dataset licence, no maintenance
status and no access model -- because a result record does not need one. Evaluation Cards computes
a comparability signal *on results*, which is the right idea attached to the wrong entity: it tells
you two numbers disagree, not that the benchmark definition itself has forked. Epoch's ECI is the
clearest case: a sophisticated, well-executed latent-ability model, published under CC-BY, that is
by construction the single universal score this project rejects. The shape's structural limit is
that a result hub inherits whatever benchmark ontology its sources happen to have, and its sources
have none.

### 2.4 Dataset and paper registries

| Registry | Operator | Coverage | Data access | Licence | Freshness |
| --- | --- | --- | --- | --- | --- |
| **HuggingFace Hub** | HuggingFace | 1,019 Spaces tagged `leaderboard`; 47 datasets `benchmark:official`, 48 `benchmark:eval-yaml`, 203 `croissant` | Free public API, no token needed (anon 500 req / 5 min); `/api/datasets/{id}/croissant` | per-artifact | live |
| **OpenAlex** | OurResearch | ~250M works | API (**metered, key required since ~2026-02-13**) + monthly S3 snapshot | **CC0** | monthly |
| **Papers with Code** | Meta AI Research | 9,327 benchmarks, 5,628 datasets, 79,817 paper-code links, 1,000+ tasks | **Archive only**: HF org `pwc-archive` | **CC-BY-SA-4.0 (viral)** | **DEAD -- sunset 2025-07-24, 301s to huggingface.co/papers/trending** |
| **Codabench** | Université Paris-Saclay / LISN | 1,498 public competitions, 80,406 users, 722,037 submissions | `/api/docs/` works for the catalogue; **`/results/` returns "not a competition admin"** | UNVERIFIED | v1.31.2 |
| **EvalAI** | CloudCV | 1,053 challenges via API | catalogue yes; **leaderboard endpoints return "not public"**; homepage returned empty on fetch, liveness UNVERIFIED | UNVERIFIED | UNVERIFIED |
| **Zenodo / Crossref / DataCite** | various | DOI minting and resolution | APIs | open | live |
| **MLCommons Croissant** | MLCommons Datasets WG | the metadata standard itself; adopted by HF, Kaggle, OpenML, TFDS, Google Dataset Search | GitHub, 899 stars | **Spec CC BY-ND 4.0**, implementation Apache 2.0 | active |

**What this shape structurally cannot do.** A registry indexes *artifacts*, and a benchmark is not
an artifact -- it is a dataset plus tasks plus metrics plus splits plus a protocol plus the
conditions under which a number counts. HuggingFace has no benchmark-versus-dataset distinction at
all; its new leaderboard tag taxonomy (`test:public`, `test:private`, `submission:automatic`,
`judge:auto`, `eval:code`, `benchmark:official`) is the single highest-leverage discovery surface
available to this project, but it is self-declared by Space authors and sparsely applied. The
sparsity figure, with its derivation, because the earlier draft asserted "about 11%" and showed no
arithmetic: in the first 1,000 of the 1,019 `leaderboard`-tagged Spaces enumerated on 2026-09-17,
110 carried `test:public` and 18 carried `test:private`, so **128 of 1,000 = 12.8% carry any
`test:*` tag**; `_workflow/recon/recon_sources.md` reports the same observation as "~11%" and the
difference is unexplained. Either way it is roughly one Space in eight -- a hint with a provenance
stamp, never ground truth, and any adapter must carry `source: hf_space_tag` on every field it
derives this way. Croissant is the sharpest illustration of the shape's limit: it is the adopted
standard for describing an ML dataset and it has no concept of an evaluation. That absence is the
standards gap this project can fill, and filling it is what converts the project from a website
into infrastructure. Note the licence trap: the Croissant *spec* is CC BY-ND, so a namespaced
extension is publishable and a modified spec is not.

### 2.5 Domain-specific challenge hubs

| Hub | Operator | Coverage | Data access | Licence | Freshness |
| --- | --- | --- | --- | --- | --- |
| **Grand Challenge** | DIAG Nijmegen | **264 medical-imaging challenges**, 2025-2027 | Public REST, no auth, DRF pagination, `publications[]` included | UNVERIFIED | very active, deadlines into 2027 |
| **CASP / CAMEO** | Prediction Center / SIB | protein structure; CAMEO weekly automated, CASP biennial | web/CGI, ancient but stable | academic | CASP17 target call open |
| **Matbench Discovery** | single lead maintainer + MIT/EPFL/Samsung contributors | materials: 43 eligible models; CPS composite (F1 50% / RMSD 10% / kappa 40%) | `/api`, `/data/sets`, GitHub, RSS | UNVERIFIED | 2026-09-13 |
| **Open Catalyst (OC20/OC22/ODAC)** | Meta FAIR Chemistry | electrocatalysts, oxides, MOFs; OC22 ~500k DFT relaxations | eval server + leaderboard JSON | UNVERIFIED | active |
| **WeatherBench 2** | Google Research | medium-range forecasting, ~25 models incl. GraphCast, Pangu, Aurora, GenCast | cloud-optimised ERA5 + GitHub | UNVERIFIED | scorecards show 2022 data (cadence UNVERIFIED) |
| **Therapeutics Data Commons** | Harvard MIMS | ADMET, DTI, docking, clinical-trial outcome | Python lib | not stated | **freshness UNVERIFIED, possibly stale** |
| **GEO-Bench 2** | AI Alliance | geospatial FMs, full-finetune and frozen-encoder tracks | GitHub | UNVERIFIED | 2026 active |
| **Waymo Open Dataset** | Waymo | AV prediction, sim agents, E2E driving | GitHub | non-commercial research | no formal 2026 challenges; leaderboards open |
| **Robotics cluster** | fragmented | LIBERO (130 tasks / 4 suites), RoboCasa365, BEHAVIOR-1K, 2026 BEHAVIOR Challenge (100 tasks, deadline 2026-10-16), Open X-Embodiment (22 robot types, 527 skills), ManiSkill, SimplerEnv, RoboTwin 2.0, Meta-World, RLBench, Habitat | per-project | per-project | **no central hub of any kind** |
| **Formal math cluster** | fragmented | miniF2F (488 Lean 4 problems), PutnamBench (672 problems as of Jan 2026), CombiBench, FATE | per-project | per-project | **no unified index** |
| **Dynabench** | MLCommons | dynamic adversarial collection; DADC, DataPerf, Flores, BabyLM | GitHub, MIT | MIT | pushed 2026-02-11, 29 stars -- near-dormant |

**What this shape structurally cannot do.** These are the deepest and most rigorous evaluations in
AI, and they are invisible. A domain hub is run by and for its field: CASP's output is a set of
peer-reviewed assessment papers, not a leaderboard; WeatherBench 2's authors explicitly say it is
not a single-leaderboard challenge; Matbench Discovery groups models into tiers by *what data they
were allowed to train on*. None of them has any incentive to adopt a vocabulary shared with another
field, because their audience is inside the field. The result is that a machine-learning
practitioner outside structural biology has no route to discovering that CAMEO evaluates weekly,
and a policymaker asking "what benchmarks exist for AI in medicine" gets Grand Challenge's 264
challenges only if they already know the name. This shape is where the project's value is
concentrated, and it is also the shape that will never do this work for us. Note the licence column:
six of these eleven rows read UNVERIFIED or "not stated", and §6 says what that means operationally,
because under a naive reading of our own policy it would route the entire non-LLM programme to
LINK-only.

### 2.6 Meta-indexes and prior catalogue attempts

| Attempt | Operator | Coverage | Data access | Licence | Status |
| --- | --- | --- | --- | --- | --- |
| **BenchmarkList** | two-person indie team | 2,545 benchmarks, 1,604 providers, 24,074 models; 11 abilities + 40+ subcategories | **none** | **none stated** | live, daily, since 2026-07-15 |
| **Benchmark Radar** | eight-author academic group | 14,810 raw / ~1,283 curated | ZIP, HF, RSS, CLI | **CC BY-NC-SA 4.0** | live, daily, ~160 stars |
| **Stanford CRFM Ecosystem Graphs** | Stanford CRFM | models/datasets/applications as files in git + static site | GitHub | **NO LICENCE** | **dead: last push 2025-01-24, 274 stars, 0 open issues** |
| **Papers with Code** | Meta | 9,327 benchmarks | archive dump | CC-BY-SA-4.0 | **sunset 2025-07-24** |
| **JonathanChavezTamales/llm-leaderboard** | community | JSON-in-git, schema-validated, 356 stars, 40 forks | GitHub | open | **self-deprecated, converted to closed llm-stats.com** |
| **Evidently AI benchmark database** | Evidently AI | 250 LLM benchmarks | none | "belongs to respective parties" | **abandoned: published 2024-12-10, last updated 2025-07-31** |
| **BetterBench** | Stanford group, NeurIPS 2024 Spotlight | 24 benchmarks x 46 criteria x 4 lifecycle stages | none observed | not stated | **stale since 2024, still calls itself a "living repository"** |
| **AISafetyBenchExplorer** | solo author | 195 safety benchmarks 2018-2026 | none | n/a | **arXiv 2604.12875 withdrawn 2026-04-23; reason not verified** |
| **Princeton HAL** | Princeton | 9 agent benchmarks, cost-controlled | web | open | **submissions paused within a year of publication** |
| **"Awesome" GitHub lists** | community | 100-443 links each | markdown | mixed | high decay, but they own the search results |

**What this shape structurally cannot do.** This is the shape we are, so the honest reading is that
it has a demonstrated failure rate near 100% among attempts older than two years. The structural
limit is not capability but *metabolism*: a meta-index has to be re-verified continuously against
sources that change without telling it, and nothing about the shape generates the revenue, the
citations or the student labour that would pay for that. §3 is the post-mortem, and it is the most
important section in this document.

### 2.7 These six tables are seed data, not prose

The six tables above are, field for field, the seed content for the `Organization`, `Leaderboard`
and `Source` entities in [04-data-model.md](04-data-model.md) -- operator, coverage, data access,
licence, freshness -- and the user's own brief asked to *"analyze/view the current ecosystem
(systems, benchmark makers, managing orgs, trends)"*. Left as markdown they are a snapshot that no
build step reads, no CI re-verifies and no site surface renders, and in six months every freshness
cell will be wrong with nothing to flag it. That is precisely the Ecosystem Graphs failure diagnosed
in §3.2, reproduced inside the document that diagnoses it.

**So: the first engineering task of Phase 1 is to transcribe these tables into
`data/organizations/`, `data/leaderboards/` and `data/sources/<yyyy>/`** ([05-repository-and-workflow.md](05-repository-and-workflow.md)
owns the layout), each record carrying `source_url`, `retrieved_at: 2026-09-17` and `verified_by`.
Every `UNVERIFIED` cell becomes `licence: null` plus an open `verification_task` with the owner and
deadline from §6. From that point this document links to the rendered source catalogue and the
ecosystem views in [10-visualization.md](10-visualization.md) rather than restating them, and
staleness in these figures is detected by the same liveness checks applied to benchmarks. A
positioning document whose facts are not in the corpus is a positioning document that will be wrong
before anyone reads it.

---

## 3. Prior art: the mortality record

Has anyone tried this before? Yes, repeatedly, including from Stanford and from Meta. Of the
attempts old enough to have a verdict, none survived. None died of insufficient ambition. The
causes are specific, and each one maps to a design decision we have to make now rather than
discover later.

### 3.1 The central case study: Papers with Code

Papers with Code was the closest thing the field has had to a universal benchmark index: 9,327
benchmarks, 5,628 datasets, 79,817 paper-to-code links, 1,000+ tasks, all under CC-BY-SA-4.0 and
acquired by Meta in December 2019. It was sunset on 2025-07-24. The domain now 301-redirects to
`huggingface.co/papers/trending`, and a Meta partnership was announced by HuggingFace the following
day -- but Trending Papers is a paper feed, not a benchmark catalogue. **The benchmark and
leaderboard layer was simply never replaced.**

The instructive part is that it did not die of staleness. It was well-funded, widely used, actively
maintained and cited in thousands of papers. It died because a single corporate owner
deprioritised it. That is a failure mode no amount of curation discipline prevents, and it has one
mitigation: had Papers with Code been forkable infrastructure with a licence and a DOI rather than
a Meta property, the community would have continued it. It was CC-BY-SA, which is at least
forkable in principle -- but the *service*, the crawlers, the extraction pipeline and the domain
name were not. What survives is a frozen dump.

Two consequences for us. First, the successor slot is genuinely open; CodeSOTA and HF Trending
Papers are both partial, and the benchmark layer is unclaimed. Second, "what happens when we stop"
must be a documented, tested part of the plan, not a sentiment. Its shape is in §12 and its
mechanism in [05-repository-and-workflow.md](05-repository-and-workflow.md) and
[15-open-questions.md](15-open-questions.md) C5.

### 3.2 Ecosystem Graphs: the exact architecture, dead

`github.com/stanford-crfm/ecosystem-graphs` is a structured asset catalogue maintained as files in
git with a static site on top -- the architecture this plan proposes, built by a well-resourced
Stanford lab. Last push 2025-01-24. 274 stars. **No licence.** Zero open issues, which on a
20-month-dead repository means nobody is even asking for it to be revived. It is still cited as a
data source by 2025-26 research (for example arXiv 2510.01286 used it as one of two proxies) while
20 months stale -- so stale curation is actively propagating errors into the literature.

The lesson is sharp and has two halves. **The architecture is not the risk; the curation treadmill
is.** And **without a licence, nobody can rescue you.** A fork is the only mechanism by which a
dead catalogue comes back, and an unlicensed repository cannot be forked into anything anyone can
rely on.

### 3.3 llm-leaderboard: the most instructive failure in the set

`JonathanChavezTamales/llm-leaderboard` was a JSON-in-git, JSON-Schema-validated community
benchmark catalogue with 356 stars and 40 forks, with a `data/` tree of models, providers,
benchmarks, organizations and licenses plus a `schemas/` directory. Its README now reads: *"This
repository is now depracated and won't be getting any new updates."* It redirected users to
llm-stats.com -- a closed website with no repository and no licence.

The stated reason was contribution friction. Pull requests were too slow compared with per-model
and per-benchmark discussion threads on a website. **This is the single most important warning in
the landscape for us**, because the earlier draft of this plan was PR-centric by design. A
community catalogue with real traction converted itself into a proprietary product because git was
too much friction for its contributors, and the gravity that pulled it there will pull us the same
way unless the contribution path is designed around people who do not use git.

The answer, already settled: a bot-validated issue-form path -- GitHub issue template, validation
bot, auto-generated pull request, human review -- modelled on UK AISI's `inspect_evals` `/register/`
launched 2026-05-08, with the PR path retained for power users. This is specified in
[05-repository-and-workflow.md](05-repository-and-workflow.md) and it is not optional.

### 3.4 The rest of the graveyard

- **Stanford HELM** entered maintenance mode on 2026-06-01, verbatim from its own README, after
  building the most genuinely multi-modal academic evaluation effort in existence (26 suites).
  **MedHELM survived by spinning out** to an independent steward -- Apache 2.0, technical
  stewardship by Pacific AI, 121 clinical tasks across 22 subcategories. Academic evaluation
  infrastructure has roughly a 3-4 year half-life tied to grant cycles and student turnover. *The
  vertical that found an industry steward lived; the parent did not.* Plan for per-domain stewards
  rather than one central curator -- specified in §12.
- **HuggingFace Open LLM Leaderboard** was retired on 2025-03-14 after evaluating 13,000+ models.
  The stated reason: it *"was becoming obsolete and could encourage people to optimize in
  irrelevant directions."* The largest ranking operator in open-source AI killed its own ranking
  for being harmful to the field. Quote this whenever the no-universal-score constraint is
  questioned; it is external validation from the strongest possible source.
- **BIG-bench** was archived read-only on 2026-04-17 despite 200+ tasks and a 450-author
  collaboration. Saturation is a lifecycle stage the schema must represent.
- **Evidently AI's 250-benchmark database** was published 2024-12-10 and last updated 2025-07-31 --
  abandoned after about seven months as a content-marketing asset for an adjacent eval product. A
  catalogue built as lead generation is always the first thing deprioritised. Our catalogue must be
  the product.
- **BetterBench** was a NeurIPS 2024 Spotlight billing itself a "living repository" and still shows
  24 benchmarks. Treat every competitor's freshness claim as UNVERIFIED until observed. Its
  46-criterion rubric across four lifecycle stages is nonetheless the best prior art for a
  benchmark-quality field, and its finding that 17 of 24 benchmarks had no easy-to-run
  reproduction scripts is a load-bearing input to our `maintenance_status` design.
- **AISafetyBenchExplorer** (arXiv 2604.12875) was submitted 2026-04-14 and withdrawn 2026-04-23;
  the reason is not verified and is not stated here, because an unsourced claim about why a named
  researcher's paper was withdrawn is exactly the kind of assertion this project exists to refuse.
  Its measurements survive and matter: 137/195 stale GitHub repos, 96/195 stale HF datasets,
  165/195 English-only, only 7 in a "Popular" tier.
- **Princeton HAL** paused submissions within a year of an ICLR 2026 publication. **Dynabench** is
  near-dormant (29 stars, last push 2026-02-11) despite MLCommons ownership. **Aider's**
  leaderboards have not moved since 2025-11-20.

### 3.5 What survived, and why -- the question the graveyard does not answer

Autopsying only the dead selects for a single answer. The more useful question is what the metadata
and evaluation infrastructure that *did not* die has in common, and the tables in §2 contain the
answer:

| Survivor | Shape | Age | What depends on it |
| --- | --- | --- | --- |
| **HuggingFace Hub** | registry | since 2016 | Every training and eval pipeline in open-source AI; `datasets` and `transformers` break without it |
| **OpenAlex** | bibliographic registry | since 2022, replacing MAG | Research-tooling software, library systems, Benchmark Radar's own connectors |
| **Zenodo / DataCite / Crossref** | identifier infrastructure | decades | Every DOI resolution anywhere; citation breaks without them |
| **MLCommons Croissant** | metadata standard | since 2023 | HF, Kaggle, OpenML, TFDS emitters and Google Dataset Search crawls |
| **lm-evaluation-harness / MTEB** | harness + results repo | since 2021 / 2022 | Papers reproduce numbers by running them; a leaderboard depends on the harness |

The common factor is not licence and not architecture. **It is that each is a dependency of other
software, so somebody else's build breaks when it goes down.** Every dead example in §3.1 to §3.4
was a *destination* -- a place people visited, whose disappearance inconvenienced readers and broke
nothing. The rule this yields is the strongest available argument for the artifact-first,
join-key-first, standard-first posture recommended throughout this plan, and it is a sharper test
than "is this useful":

> **Survival correlates with being depended upon, not with being visited. Every design decision
> should ask whether it increases the number of systems that break when we stop. A stable JSON
> artifact at a versioned URL does. A DOI'd release does. A cross-reference ID other people join on
> does. A nicer facet UI does not.**

This also tempers the base rate honestly. The sample in §3.1-3.4 is selected for being
findable-because-dead, and two of the three projects in §1 are two months old and cannot yet have
died on a 12-24 month clock. The correct statement is not "everything dies" but the narrower one
below.

### 3.6 The pattern, and the three design consequences

**Every cross-domain AI catalogue attempt older than two years has died within 12-24 months**, and
none died of insufficient ambition. The causes, in order of frequency: manual-curation load
exceeding a small team; single-owner deprioritisation (Papers with Code, HELM, Open LLM
Leaderboard); contribution friction pushing maintainers to closed websites (llm-leaderboard); and
no licence, making rescue-by-fork impossible (Ecosystem Graphs).

Three decisions follow, and every other document in this plan must reflect them.

1. **CC-BY + DOI + forkable-at-commit from day one, with a documented succession story.** This is
   simultaneously the survival mechanism and the differentiator against BenchmarkList (closed) and
   Benchmark Radar (non-commercial). Failure becomes survivable rather than terminal.
2. **Contribution must not require a pull request.** Bot-validated issue forms first, PRs for power
   users. The friction that killed llm-leaderboard is a design defect, not a user problem.
3. **Automate ingestion from Tier-1 permissive sources; hand-curate only where hand-curation is the
   differentiator** -- the cross-domain taxonomy, the evaluation conditions, the gap matrix and the
   non-LLM domains. The curation treadmill, not the architecture, is what kills these projects.
   This is the doctrine in §10, and §11 is what it costs.

---

## 4. How overlap is measured

The earlier draft quoted seven overlap percentages with no definition, no denominator and no
method, in a plan whose governing rule is that numbers are computed and shown with their formula.
One of them -- "60% conceptual, 0% operational" -- was not a percentage at all. This section defines
the term once, states what is and is not measured, and downgrades the unmeasured figures to what
they actually are.

**Two different quantities, both called overlap, and they must never be mixed.**

```
entity_overlap(S)  =  | seed_set ∩ catalogued_by(S) |  /  | seed_set |

    seed_set        = our 320-entry Tier-1 seed allocation (02-taxonomy.md §3)
    catalogued_by(S)= benchmark families S carries an entry for, matched by name or alias
    reading         = "how much of what we plan to carry does S already carry"

field_overlap(S)   =  | material_fields(S) ∩ material_fields(ours) | / | material_fields(ours) |

    material_fields = the fields that make an entry useful: domain facets, licence, access model,
                      maintenance status, lineage, and the EvalConditions material set
                      (04-data-model.md §8)
    reading         = "for an entry both of us carry, how much of what we say does S also say"
```

Entity overlap is what the ranked table in §5 is about. Field overlap is why a high entity overlap
is survivable: BenchmarkList carries an OC22 entry and carries no licence, no creator attribution,
no task count and no evaluation conditions on it, so its field overlap with us on that entry is
low. Quoting only the first number is how a catalogue talks itself out of existing; quoting only
the second is how it talks itself into complacency.

**The measurement, and its honest precision.** Entity overlap is estimated by drawing 50 families
uniformly at random from the seed list and checking each for presence in the target service by name
and alias search. That sample size is cheap -- roughly two hours per service -- and its precision
must be stated rather than implied: at p ≈ 0.5 the standard error is sqrt(0.25/50) = 0.0707, so
**one standard error is about 7 percentage points and a 95% interval is roughly ±14 points.** A
50-family sample can tell "most of our set is already there" from "little of it is". It cannot tell
70% from 75%, and any document that prints those two numbers side by side as if they were different
is over-reading its own data.

**Therefore: bands, not point estimates, until the sample is run.** The figures in the earlier draft
came from the landscape reconnaissance analyst's judgement on 2026-09-17, not from a count. They are
retained below as a prior and labelled as such, and the operative column is the band.

| Service | Band | Analyst prior (2026-09-17, judgement not measurement) | What the band means here |
| --- | --- | --- | --- |
| BenchmarkList | **High** | ~75% | Same ambition, cross-domain, two months ahead. Assume most of our seed appears there in some form |
| Benchmark Radar | **High** | ~70% | High on entity, low on field -- a discovery firehose with ~1,283 curated |
| Every Eval Ever | **Complementary** | ~45% | Different entity type entirely; the intersection is benchmark *names*, not benchmark records |
| Epoch AI | **Moderate** | ~40% on data model, 0% on scope | Restated as: high field overlap on the 81 benchmarks it carries, near-zero entity overlap outside language and agents |
| Artificial Analysis | **Moderate** | ~35% | Entity overlap limited to the ~30 evals it runs |
| inspect_evals | **Moderate** | ~35% and rising | Implementation-gated: 171 evals, none outside language/agent/safety |
| Stanford HELM | **Moderate, declining** | ~30% | Frozen since 2026-06-01, so the number can only fall |
| Arena | **Low** | ~20% | One benchmark family (pairwise preference) across 13 arenas |
| Commercial leaderboards (Scale, Vals, LiveBench, BenchLM, llm-stats, lmmarketcap) | **Low** | 10-25% each | Closed; entity overlap concentrated in frontier LLM benchmarks |
| Competition platforms (Codabench, EvalAI, Grand Challenge, Kaggle) | **Low** | 10-15% | Catalogues of competitions, not of benchmarks; overlap is in the medical and science tails |
| "Awesome" lists | **Negligible substantively** | ~5% | Unstructured; they own search results, not the data |

**Scheduled as a Phase 0 task**: `scripts/overlap_sample.py` draws the 50 families, records each
lookup as a URL and a boolean with a date, writes `data/_analysis/overlap-<service>-<date>.yaml`,
and publishes the proportion with its 95% interval. Until that runs, this document prints bands.
The cost of getting this wrong is not academic: the overlap number is the single most quotable
figure in the whole positioning, and a two-person project that publishes a fabricated 75% has
handed every critic the only argument they need.

---

## 5. Overlap analysis and precise boundaries

Ranked by band and then by the analyst prior. Each boundary is stated operationally -- what we do
and what we explicitly do not do -- because "we are more comprehensive" is not a boundary, it is a
slogan.

| # | Service | Band | Boundary |
| --- | --- | --- | --- |
| 1 | **BenchmarkList** | High | They own a closed, daily-scraped cross-domain database with a cross-benchmark alignment index. We own the open one. Never compete on raw count; compete on **provenance, licence and forkability**: every field in our YAML carries `source_url`, `retrieved_at` and `verified_by`; the whole index is CC-BY at a commit hash with a DOI. We explicitly refuse the Rosetta Stone alignment -- that is the single-number ranking we reject, and it is the sharpest philosophical contrast available. We do not scrape them. |
| 2 | **Benchmark Radar** | High | They own **discovery** -- 37 firehose sources, 14,810 raw records, daily. We own **curation** -- fewer entries, each hand-verified, each with structured eval conditions and a domain taxonomy. Their CC BY-NC-SA content licence blocks exactly the institutional adopters we need, so **we do not ingest their content** and CC-BY is the wedge. Cross-reference by URL at the benchmark level, subject to the extraction rule in §14. |
| 3 | **Every Eval Ever / EvalEval** | Complementary | **We own the benchmark entity; they own the result record.** We adopt their `eval.schema.json` field names for the conditions we share (`generation_args`, `agentic_eval_config.available_tools`, `sandbox`, `metric_config`) so a result validated against EEE joins our benchmark record on a stable ID, and we propose ourselves explicitly as the benchmark-registry counterpart to their result-registry. This is the highest-leverage single relationship in the landscape. |
| 4 | **Epoch AI** | Moderate | They go deep on 81 language/agent benchmarks with their own runs; we go broad across every domain with zero runs. We **never re-derive their numbers** -- we ingest them under CC-BY with attribution, badged as machine-ingested. We cede authoritative frontier-LLM capability trends and ECI to Epoch and link out. We adopt and generalise their `superseded_by` column into a full lineage model. Positioning: *Epoch tells you how good models are on 81 frontier benchmarks; we tell you which several thousand benchmarks exist, in every field, and whether their numbers are comparable at all.* |
| 5 | **Artificial Analysis** | Moderate | They run and sell evals; we catalogue and never run. Their terms require attribution at all tiers and bar redistribution without a commercial contract, so: **link and cite, never mirror**. Settled: **we take no API dependency on them at all** -- they are a `Leaderboard` entity with manually dated standings snapshots, which makes the conflicting free-tier rate limit (100 req/24h on one page, 1,000/day on another; UNVERIFIED) irrelevant rather than a thing to resolve. |
| 6 | **Inspect / inspect_evals (UK AISI)** | Moderate and rising | They register **runnable Inspect implementations**; we register benchmarks regardless of whether code exists. Their registry is implementation-gated and language-model-gated, so a protein-structure challenge can never enter it. We add an `inspect_evals_id` field so a user jumps from our catalogue to a runnable eval, which makes us the front door to their harness rather than a rival. MIT licence makes ingestion trivial. We also copy their `/register/` contribution mechanism outright and say so. |
| 7 | **Stanford HELM** | Moderate, declining | Maintenance mode since 2026-06-01. **Take over the map, not the measurement.** HELM's scenario taxonomy across Capabilities, Safety, VHELM, HEIM, ToRR, MedHELM and AudioHELM is the best existing cross-modality vocabulary; we adopt and extend it and cite HELM as taxonomy ancestry. On the `run_specs.json` data licence: **default is do-not-ingest**; we ask Stanford CRFM once, in a GitHub issue on the HELM repository, and if there is no answer within 30 days we take only the **field names** as taxonomy ancestry -- names are not expression -- cite HELM, and never copy spec values. We track MedHELM's spin-out as the model for domain-vertical stewardship. |
| 8 | **Arena (ex-LMArena)** | Low | Arena owns live pairwise human-preference ranking for chat and 12 adjacent arenas. We model it as a `Leaderboard` entity, ingest a capped slice of its CC-BY-4.0 snapshot dataset under the volume policy in §8, snapshot its standing periodically with a date, and **never attempt to reproduce or re-derive its Elo**. Its `*_style_control` variants are a different comparability class of the same benchmark and are modelled as distinct leaderboards. |
| 9 | **Scale SEAL, Vals AI, LiveBench, BenchLM, llm-stats, lmmarketcap** | Low | All closed or semi-closed commercial leaderboards. Uniform posture: catalogue the benchmark, link the leaderboard, record the conditions where published, ingest nothing. Scale's prompt sets are deliberately unreproducible by design -- we record that fact as a `verification` property rather than treating it as a data-access problem. |
| 10 | **Codabench, EvalAI, Grand Challenge, Kaggle** | Low | Competition platforms. We ingest their **catalogues** as discovery records under §8's volume policy (Codabench 1,498 competitions, EvalAI 1,053 challenges, Grand Challenge 264 with `publications[]` included) and accept that their **leaderboards are closed** -- Codabench's `/results/` returns an admin error and EvalAI's leaderboard endpoint returns "not public". Catalogue yes, results no. Grand Challenge is the cheapest route to real non-LLM breadth in the entire source list, subject to the licence resolution in §6. |
| 11 | **"Awesome" GitHub lists** | Negligible substantively, high in search results | Zero substantive competition -- unstructured markdown, no schema, high decay -- but they own the search traffic. Posture: be listed in them, contribute entries, and make our per-benchmark pages the thing those lists link to. |

**Not a competitor, listed separately because it is a corpus rather than a service:**

| **Papers with Code archive** | **Legacy corpus, dead since 2025-07-24** | Conceptually the nearest thing to what we are building; operationally zero overlap, because a frozen dump competes with nobody. It is the largest cold-start corpus available (9,327 benchmarks) and it is CC-BY-SA-4.0, which is viral. The settled decision is in §6 and §7; the mechanics are in [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3.9. |
| --- | --- | --- |

---

## 6. What a licence does and does not restrict

Six of the eleven rows in §2.5 carry an UNVERIFIED or unstated licence, and §7's Q2 treats "no
stated licence" as incompatible. Read naively, that routes Grand Challenge, Matbench Discovery,
Open Catalyst, WeatherBench 2, GEO-Bench 2 and Therapeutics Data Commons to LINK-only, which
deletes the cheapest non-LLM breadth in the plan and most of the differentiator with it. The
resolution is that the licence question and the copyright question are not the same question, and
the plan has to say which one it is answering.

**The working theory, in three sentences.** *(Unverified -- this is a working posture for curators,
not legal advice; confirm with a qualified adviser before the first bulk ingest, and record the
answer in [15-open-questions.md](15-open-questions.md) A4.)*

1. **Individual facts are recorded regardless of the source's licence.** A benchmark's name, URL,
   release date, the name of its metric, the organisation that runs it, and whether its test set is
   public are facts. In the United States facts and the sweat-of-the-brow arrangement of them are
   not copyrightable (*Feist v. Rural Telephone*, 1991); in the EU they are unprotected as
   expression, though see point 3.
2. **Expressive content is reproduced only under a compatible licence.** Descriptions, abstracts,
   curated prose, editorial rankings and any text a human wrote to be read are expression. We write
   our own or we quote briefly with attribution; we never bulk-copy them.
3. **Bulk extraction of a substantial portion of a database is treated as licensed content
   regardless of jurisdiction.** The EU sui generis database right restricts extraction of a
   substantial part of a database even where no individual element is protected, and systematic
   repeated extraction of insubstantial parts counts. So the rule is behavioural, not doctrinal: a
   curator may record any fact they are looking at; an adapter may not systematically harvest a
   source's whole record set unless the licence permits it.

The practical consequence is a clean split a curator can apply without a lawyer: **reading a page
and recording what it says is always allowed; pointing a scraper at a source and taking all of it is
allowed only under a permissive licence.** That is what makes Grand Challenge tractable -- we may
record that challenge #212 uses a Dice score whatever their site's licence turns out to be -- and it
is also why §8's per-source caps exist, because "how much did you take" is the question that
actually determines exposure.

**The dated prerequisite, with an owner and a default.** Before any Phase 2 bulk ingest, resolve the
licence cell for **Grand Challenge, Matbench Discovery, Open Catalyst, WeatherBench 2, GEO-Bench 2
and Therapeutics Data Commons** -- six emails or six issues, roughly two hours total. This is a
Phase 0/1 task owned by the curation lead and tracked in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md). **Default on no answer within 30 days:
LINK, plus fact-level recording under point 1** -- which means we still get the entries, we still
get the facets, and we do not get the bulk catalogue dump. Record the ask and the non-answer on the
`Source` record so the decision is auditable and can be revisited when someone does reply.

---

## 7. The non-duplication policy

This is the operational answer to the owner's concern. It is a rule a curator applies **before**
spending time on anything, and it applies to every fact in the repository, not just to benchmarks.

### 7.1 The three questions

1. **Does a maintained, machine-readable source already carry this fact?** Not "does someone have
   it on a web page" -- does a source with an API, a bulk download or a git repository carry it in
   a form we can parse and re-parse.
2. **Is its licence compatible with ingestion and attribution?** Compatible means CC0, CC-BY, MIT,
   Apache-2.0 or a public-domain declaration. Incompatible means share-alike, non-commercial, no
   stated licence, or explicit redistribution restrictions. Read this together with §6: an
   incompatible licence blocks *bulk extraction and reproduction of expression*, not fact-level
   recording.
3. **Is it likely to still be maintained in two years?** Scored, not judged -- see §7.2.

### 7.2 Q3 as a score, because a judgement call is not a procedure

"Likely to still be maintained" decides INGEST-recurring versus INGEST-ONCE-AND-FREEZE, and left as
four unweighted signals it produces different answers from different curators on different days,
which makes the whole routing unreproducible. Turn it into five binary signals, +1 each, stored on
the `Source` entity as `maintenance_prognosis: {score, signals[], assessed_at}` (a schema addition
for [04-data-model.md](04-data-model.md)):

| Signal | +1 when |
| --- | --- |
| **Recent activity** | A commit or data update within 90 days of assessment |
| **Funded dependency** | A named funder, or a commercial product that would break without it |
| **Bus factor > 1** | More than one maintainer active in the last 12 months |
| **Rescuable** | A licence that permits a fork to continue (CC0, CC-BY, MIT, Apache-2.0) |
| **Already survived a transition** | It has outlived one leadership, funding or ownership change |

**Routing: score >= 3 -> INGEST recurring; 1-2 -> INGEST ONCE + FREEZE; 0 -> LINK.** Re-assess
quarterly; a source dropping below 3 automatically flips its records to `source_status: frozen` and
opens a re-derivation task. Three worked examples, scored as of 2026-09-17:

| Source | Recent | Funded | Bus > 1 | Rescuable | Survived | Score | Route |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Epoch AI** | yes (2026-09-17) | yes (non-profit, funded programme) | yes | yes (CC-BY) | yes (multi-year, renamed products) | **5** | INGEST recurring |
| **Stanford HELM** | no (maintenance mode 2026-06-01) | partly (lab-funded, deprioritised) | unclear -- scored no | yes (code Apache-2.0; data licence UNVERIFIED) | yes (survived MedHELM spin-out) | **2** | INGEST ONCE + FREEZE, and only field names until §5 row 7's licence question resolves |
| **Papers with Code archive** | no (frozen 2025) | no | no | partly (CC-BY-SA is forkable but incompatible with our core -- scored no) | no (owner killed it) | **0** | LINK / quarantine only |

The scoring is deliberately crude. Its job is not to be right about the future; it is to make two
curators reach the same routing from the same evidence, and to leave a dated record of why.

### 7.3 The decision tree

```
        A candidate fact about a benchmark, system, org, result or leaderboard
                                     |
                                     v
       +----------------------------------------------------------------+
       | Q1. Does a MAINTAINED, MACHINE-READABLE source carry this fact? |
       +------------------------------+---------------------------------+
                    no  |                          | yes
                        v                          v
             +-------------------+   +---------------------------------------+
             |      CURATE       |   | Q2. Licence permits bulk extraction   |
             |  hand work; this  |   |     and redistribution under CC-BY?   |
             |  is our core value|   +-----------------+---------------------+
             +-------------------+             yes |          | no / unclear
                                                   v          v
                          +------------------------+   +--------------------------------+
                          | Q3. maintenance_prognosis  |  LINK                          |
                          |     score (§7.2)           |  - model as Leaderboard/Source |
                          +----+-----------+-----------+  - dated standings snapshots   |
                          >=3  |       1-2 |       0      - facts recorded per §6 pt 1  |
                               v           v       \----> - never bulk-extract          |
                    +----------------+  +----------------------+  - store NO copied prose|
                    |     INGEST     |  | INGEST ONCE + FREEZE |                         |
                    |  recurring     |  | frozen snapshot hash |-------------------------+
                    |  adapter,      |  | source_status: frozen|
                    |  badged,       |  | re-derive from       |
                    |  capped by §8  |  | primary before       |
                    +----------------+  | promotion            |
                                        +----------------------+
```

### 7.4 The routes, as rules

| Route | When | What we store | What we never do |
| --- | --- | --- | --- |
| **INGEST (recurring)** | Q1 yes, Q2 yes, prognosis >= 3 | Full records in a segregated `_ingested/<source>/` tree, each with `provenance`, `retrieved_at`, a snapshot ID, a rule-assigned verification level and an honestly computed `condition_completeness`; `curation.verification_status: machine-ingested` | Mix ingested records into hand-curated trees; present them in comparison views without a badge; re-derive numbers the source already publishes; exceed the per-source cap in §8 |
| **INGEST ONCE + FREEZE** | Q1 yes, Q2 yes, prognosis 1-2 | Same, plus a frozen snapshot hash and an explicit `source_status: frozen`; entries flagged for re-derivation from primaries | Let a frozen source silently age into apparent currency |
| **LINK** | Q1 yes, Q2 no | A `Leaderboard` or `Source` entity with URL, operator, licence, access terms, and periodic dated standings snapshots recorded as claims attributed to that leaderboard; individual facts recorded per §6 point 1 | Mirror their data; copy their prose; systematically extract their record set; scrape behind a bot challenge or a robots disallow |
| **CURATE** | Q1 no | A full hand-built record with every material field either populated from a primary source or explicitly null | Fill a field from a secondary aggregator without marking it single-source-unverified |

### 7.5 Standing exceptions, each with its reason

- **Never ingest Benchmark Radar.** CC BY-NC-SA is incompatible with our CC-BY core. Link at the
  benchmark level by URL; see §14 for why a bulk-extracted `radar_id` table is a different act from
  a recorded link.
- **Never scrape BenchmarkList.** No licence, no API, and scraping a competitor's proprietary
  database is both legally exposed and reputationally wrong for a trust-first project.
- **Never redistribute Artificial Analysis, Scale or any private-prompt-set leaderboard.**
  Attribution is permitted; redistribution is contractually barred or practically impossible.
- **Papers with Code: keys only, and nothing in the published artifacts.** The archive is
  CC-BY-SA-4.0 and viral, and this is the single largest legal risk in the ingestion strategy. The
  settled posture ([06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3.9,
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §11) is a `vendor/pwc-archive/`
  tree with its own LICENSE, used as a **reconciliation key only**. This document adds the v1 scope
  rule, because "key only" was doing a lot of unexamined work: **v1 loads only the name, ID and URL
  columns of `evaluation-tables` into `vendor/pwc-archive/keys/`; no descriptions, no abstracts, no
  task prose, and nothing PwC-derived appears in `data/` or in either published JSON artifact.**
  CI job 8 already blocks promotion out of `vendor/` without a `Re-derived-from:` trailer. An
  earlier critique argued for keeping the dump entirely outside the repository; that is cleaner
  still, but it loses the ability to diff a reconciliation run against a committed key set, and the
  quarantine tree plus the field-level restriction achieves the same legal outcome with an audit
  trail.

### 7.6 The invariant that makes all of this safe

The hard constraint that we never host benchmark data is also the strongest legal shield in the
plan: almost every licence ambiguity above dissolves if we only ever store facts plus links. §9
specifies how that is enforced mechanically, because asserting it is not enforcing it.

**The failure mode to avoid** is the one Ecosystem Graphs demonstrates: an index whose entries are
silently stale still gets cited, and therefore propagates errors into the literature with our name
on them. Staleness must be visible in the data model, not merely known to the maintainers.

---

## 8. Volume policy: what is actually allowed to land

§5 proposes ingesting from sources holding, between them, 2.36M Arena rows, 6,598 Epoch rows, 1,498
Codabench competitions, 1,053 EvalAI challenges, 264 Grand Challenge challenges, 227
lm-evaluation-harness task directories, 171 inspect_evals entries and 2,546 HELM run specs. The
measured artifact budget is a 2.76 MB raw / 0.52 MB brotli corpus in two unsharded JSON files, with
revisit-and-shard triggers at 150 KB gzipped for `facets.json` and 1.5 MB brotli for
`corpus.json` ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.1 owns those
triggers and §8.1 the budget), enforced as a warn-and-open-an-issue budget rather than as a build
failure — a deploy is never blocked on size, because a blocked deploy on a data repository stops
corrections landing. Without a volume policy, the "curation over discovery" wedge against Benchmark Radar is
a slogan contradicted by our own adapter list.

**Two rules for two entity types, because they have opposite economics.**

**Rule 1 -- no machine-generated benchmark entity is ever published.** Discovery output from
Codabench, EvalAI, Grand Challenge, arXiv triage and HuggingFace tag sweeps lands in
`data/_discovery/<source>/`, a tree that is excluded from `facets.json`, from `corpus.json`, from
Pagefind and from every count on the site. A record leaves it only through human review into
`data/benchmarks/<domain-family>/`. This is the mechanism that makes curation-over-discovery
enforceable: the published benchmark count is, by construction, the hand-reviewed count. (This tree
is an addition to the layout in [05-repository-and-workflow.md](05-repository-and-workflow.md);
route it there.)

**Rule 2 -- machine-ingested result claims are published, segregated and badged.** Claims are the
opposite case: a claim is a number with a source, not an entity we invented, and 6,598 of them is
exactly the coverage the user asked for. They live in `data/claims/_ingested/<source>/`, carry
`curation.verification_status: machine-ingested`, are excluded from comparison views below the
completeness threshold and from every headline count, and are included in browse and search. The
ratio will be roughly 95:5 machine to hand and that is fine, provided it is visible.

An earlier critique proposed a single ratio invariant -- never more machine-generated entities than
hand-reviewed ones -- enforced in CI. Rule 1 is strictly stronger for benchmarks (the ratio is zero)
and a ratio rule for claims would forbid exactly the bulk coverage the Epoch decision requires, so
the two-rule split replaces it.

**Per-source caps, stated so an adapter author can implement them.**

| Source | What lands | Cap |
| --- | --- | --- |
| **Arena** | Derived leaderboard standings only, as dated claims attributed to the leaderboard | **Latest snapshot only in the published artifact; top 25 rows per arena.** 13 arenas x 25 = ~325 rows, roughly 100 KB, and constant rather than growing. Historic snapshots stay in git and are reachable at a commit hash -- which is what "data as git" is for. Never battle-level rows |
| **Epoch** | Claims only, into `data/claims/_ingested/epoch/` | All 6,598 rows; this is the settled decision. Benchmark entities derived from it are seeds for human review, not publications |
| **Codabench, EvalAI, Grand Challenge, Kaggle** | Discovery records into `data/_discovery/<source>/` | Unbounded in the discovery tree, zero in the published artifacts until reviewed |
| **HELM run_specs, lm-evaluation-harness, inspect_evals** | `EvalConditions` records and crosswalk keys | Conditions attach to benchmarks we already carry; they never create benchmark entities |
| **HuggingFace tag sweeps** | Discovery records plus per-artifact licence and download facts | Discovery tree only |

**The CI check that makes it real**, routed to
[05-repository-and-workflow.md](05-repository-and-workflow.md) §9: the build fails if any record
under `data/_discovery/` appears in `facets.json` or `corpus.json`, if any published `Benchmark`
carries `verification_status: machine-ingested`, or if either artifact exceeds its size budget. All
three are one-line assertions over the build output.

---

## 9. The metadata-only invariant, and how it is actually enforced

[05-repository-and-workflow.md](05-repository-and-workflow.md) §9 check 7 states the invariant:
reject data files under `data/`, reject files over 256 KB, reject any single prose field over N
characters. The length cap is the weak part and it is worth being blunt about why, because this
clause is described elsewhere in the plan as the strongest legal shield we have. **A character
threshold detects length, not copying.** A 400-character verbatim abstract passes it; a
900-character original description fails it. And an extension blocklist is evaded by `.csv`, `.txt`,
`.arrow` or a renamed file.

Three checks, specified so they can be implemented rather than admired:

**(a) Named per-field length caps**, not one global N: `description` <= 1,000 characters, `notes` <=
2,000, `tagline` <= 200, and `task_example` forbidden entirely as a field -- an example task item is
benchmark data, and the moment one appears in the repository the "we never host data" claim is
false.

**(b) A copy detector, which is the only check that tests the actual claim.** For any record with
`provenance.source_url`, CI reads the cached ingest snapshot (never a live fetch -- a CI job that
depends on someone else's uptime is a CI job that gets disabled) and fails on 8-gram shingle overlap
above 0.25 between our field text and the source text. The false-positive story matters or the check
gets switched off in week two: shingle overlap fires constantly on benchmark names, metric names and
boilerplate, so the check ignores any field shorter than 120 characters and maintains an allowlist
of exempt short fields (`name`, `aliases`, `metric_name`, `licence_id`). Overlap between 0.15 and
0.25 warns rather than fails.

**(c) A payload gate built as an allowlist, not a blocklist.** Any file committed under `data/`
whose extension is not `.yaml` is rejected; `.json` is permitted only under `schema/`; any file over
256 KB anywhere outside `vendor/` and `metrics/` is rejected. An allowlist cannot be evaded by
renaming.

The reason to specify this here rather than only in doc 05 is that it is a *positioning* mechanism
as much as an engineering one. The claim "we hold metadata and links, never data" is the thing that
makes a benchmark maintainer relaxed about being catalogued and a lawyer relaxed about the whole
project, and an unenforceable version of it is worse than none, because it invites the reliance it
cannot support.

---

## 10. The ingest-versus-curate doctrine

The policy above, applied to the map, produces a clear split, and that split is the concrete
mechanism for "avoid repetition". Where a mainstream leaderboard already maintains the numbers --
which is most of the LLM world -- we catalogue the benchmark richly and ingest or link the claims.
Where nobody else has numbers, we curate claims ourselves. It is also the only way a 1-2 person team
survives, and the argument for why being copied is not a loss is in §13.

**Three postures, and one machine-readable field.** The vocabulary is `hand-curate`,
`ingest-then-verify` and `mixed`. The canonical per-family value should be stored as
`curation_posture` on the domain-family record in `taxonomy/domains.yaml` -- a schema addition to
route through [04-data-model.md](04-data-model.md) §4, alongside `seed_target`, `core` and
`coverage_status` -- so that the doctrine is filterable, checkable and rendered rather than
restated. [02-taxonomy.md](02-taxonomy.md) §3 prints the same label beside each family's seed
allocation; the two are the same value read from the same file, not two prose copies.

| Domain family | Existing coverage | Posture | Reasoning |
| --- | --- | --- | --- |
| language | Saturated: Epoch, EEE, Arena, HELM, Artificial Analysis, BenchmarkList, Benchmark Radar | **ingest-then-verify** | Hand-curating these numbers is literally the repetition the owner warned against, and we would be doing a worse job of Epoch's job |
| reasoning-general | Saturated, same set | **ingest-then-verify** | Same. The contribution is facets and lineage, not numbers |
| mathematics | Saturated on numbers; FrontierMath's four live variants are unmodelled | **ingest-then-verify** | The lineage case is stronger than the volume case |
| general-intelligence | Well covered and small: ARC-AGI generations, HLE, GPQA, SimpleBench, MMLU-Pro | **ingest-then-verify** | The one family small enough to sweep completely, which makes it the cheapest demonstration that the counting convention works |
| code | Saturated: SWE-bench (323 claims with `agent`/`reasoning_effort`/`checked`), Aider, LiveBench, EvalPlus, Terminal-Bench | **ingest-then-verify** | The numbers are free; the fork chaos (six SWE-bench variants, concurrent Terminal-Bench 2.0/2.1) is unmodelled anywhere and is our differentiator |
| games-planning | Partly covered: Kaggle Game Arena, Balrog, Epoch's chess and GBA benchmarks | **ingest-then-verify** | Elo is meaningful only within one rating-pool snapshot; recording the pool and the snapshot is the value, not collecting more ratings |
| agents-tooluse | Well covered, fastest-growing, most harness-sensitive | **mixed** | Scaffold identity is the whole story and no source records it structurally; ingest the claims, hand-curate conditions on a deliberate sample |
| safety-alignment | Partly covered: inspect_evals (171 evals), HELM Safety, Scale; 137/195 repos measured stale | **mixed** | Ingest from MIT-licensed harnesses; the liveness signal is the contribution, not the scores |
| society-econ-law | Partly covered: Vals AI (commercial), ForecastBench, GDPval | **mixed** | Many test sets are private; the honest record of *that fact*, and of resolution lag, is the contribution |
| medicine-health | Grand Challenge (264 challenges, public API), MedHELM (121 clinical tasks) | **mixed** | Cheapest non-LLM breadth available and the highest raw volume (~700 nameable families); ingest the catalogue as discovery, hand-curate facets and Tier-1 entries |
| robotics-embodiment | **None.** No central hub of any kind | **hand-curate** | The single largest unindexed field. Highest priority for curator-hours |
| chemistry-materials | Single-domain only: Matbench Discovery, Open Catalyst, CACHE | **hand-curate** | Wet-lab hit rates and DFT level-of-theory conditions have no slot in any LLM-shaped schema |
| biology-genetics | Single-domain only: CASP/CAMEO, CAFA, Virtual Cell Challenge | **hand-curate** | CASP alone breaks `version`, `leaderboard`, `metric` and `evaluation_conditions`; getting it right validates the whole schema |
| earth-climate | Single-domain only: WeatherBench 2, GEO-Bench 2 | **hand-curate** | Needs lead-time and spatial-resolution fields that exist nowhere else |
| physics | Fragmented: CritPt, HEP/astro/quantum subfields with almost no shared vocabulary | **hand-curate** | No unified index exists and the field is small enough to finish |
| audio-speech | Thin and fragmenting: AudioHELM frozen, SUPERB status UNVERIFIED, DCASE is one name over seven tasks and twelve years | **hand-curate** | The family/child counting convention is load-bearing here and no source applies one |
| vision | Thin and fragmenting: HELM VHELM/HEIM frozen; CVPR/ICCV/ECCV emit 50-100 challenge tracks a year | **hand-curate, capped** | Largest long tail in the project (~1,000+ nameable families). Cap deliberately or it eats the project |
| multimodal | Overlaps vision; no dedicated index | **hand-curate** | The boundary rule against vision is the work; volume is not |
| engineering-design | **Unsurveyed.** CadEval, AutoLabs, Learn2Design and an EDA/CAD cluster with no honest parent | **hand-curate** | Nobody has surveyed it, including us; a Phase-0 scoping survey precedes curation, and a muted family in the coverage matrix is itself a publishable finding |

Nine families are hand-curate, four mixed, six ingest-then-verify. The per-family seed allocation
that this posture drives is owned by [02-taxonomy.md](02-taxonomy.md) §3 and is not restated here.

**Consequence for the result-claim targets.** The earlier draft's Phase-3 target of 500 result
claims is meaningless once Epoch is ingested: a single adapter run produces 6,598 claims at an
expected mean `condition_completeness` around 0.10, clearing the target thirteen times over without
measuring any work of ours. [14-roadmap.md](14-roadmap.md) owns the restatement and has already made
it: **>= 130 claims at `condition_completeness` >= 0.6, each with a named source and an archived
URL, of which >= 60 are from non-LLM domains**, against 110-160 hand-curated claims planned. That
bar is one essentially none of Epoch's 6,598 rows clears, which is exactly why it still measures our
own work. Do not re-derive it here; link to it.

On the LLM side the settled Epoch policy applies: ingest all rows in bulk into
`data/claims/_ingested/epoch/`, badge honestly, keep them out of `data/claims/` proper, and
hand-curate only **50-80 claims chosen adversarially rather than representatively**. The four
clusters, from `_workflow/recon/recon_epoch-assets.md`: the `arc_agi_external.csv`
`claude-opus-4-6_120K` family, five rows sharing one identical primary key at five different
reasoning efforts (this one cluster demonstrates the entire thesis); the `falcon-7b` MMLU conflict
described in §12; SWE-bench Verified across three or four scaffolds with `built_on` populated; and
10-15 science-adjacent claims (CritPt, SciCode, CadEval, GeoBench) that bridge to the non-LLM half
of the map. Details in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) and
[12-analytics-and-trends.md](12-analytics-and-trends.md).

---

## 11. What the doctrine costs, and what it buys

The doctrine is only credible if its price is stated, because the modal death of a project like this
one is discovering in month six that the seed release was costed at a third of its true price and
then quietly shrinking the domain list to hit the date -- which converts us into another LLM
catalogue, slowly, with nobody making a decision.

**The seed.** The canonical seed total is **320 entries across all 19 domain families**, with a hard
launch floor of 12 per family, 18 for the seven Core families, and 15 as the credibility target
every family reaches by v1.x -- which is what the recon's "below roughly fifteen a specialist spots
the gaps immediately" actually measures. The per-family allocation is owned by
[02-taxonomy.md](02-taxonomy.md) §3 and is not restated here.

**The cost, with its method.** At the planning rate of 30-90 minutes per fully sourced entry with
heavy AI assistance — an estimate from the domain reconnaissance, never a measurement, owned by
[14-roadmap.md](14-roadmap.md) §"Effort sizing" — and 2-3 hours for the ten named stress cases, so 320 entries is **175-495 person-hours**: (310 x 0.5 h)
+ (10 x 2 h) = 175 at the low end, (310 x 1.5 h) + (10 x 3 h) = 495 at the high end. At 20 h/week
that is one part-time person for **nine to twenty-five weeks**. [14-roadmap.md](14-roadmap.md) owns
the phase and calendar figures that follow from it.

**A recorded reservation about the uniform rate.** The 30-90 minute figure is a single rate applied
to work that plainly varies: verifying licence, access model, metric definitions, version lineage,
maintenance status, eight facet assignments and per-field provenance for a CASP round, in a field
the curator does not work in, is not the same task as doing it for MMLU-Pro. A differentiated model
(routine LLM-adjacent 30-60 min, non-LLM Tier-1 90-180 min, stress case 3-5 h) lands **somewhere in
330-720 hours depending on how the 320 entries partition across the three bands**, and no partition
this document can defend reproduces a point estimate. Two plausible ones, shown because a range
without its partition is the same error this section is arguing against: splitting on the seven Core
families (144 Tier-1 at the middle rate, 166 at the routine rate, 10 stress) gives **329-648 h**,
midpoint 488; splitting on the nine hand-curate families gives **363-716 h**, midpoint 540. Either
way the differentiated model lands nearer the top of the settled 175-495 range than its middle, and
plausibly above it. The settled range
stands; the operational conclusion is that **the high end is the planning number, not the midpoint**,
and that the 20-entry checkpoint in [14-roadmap.md](14-roadmap.md)'s stopping rule (a) -- measure
the median per-entry time, and re-cut to 270 entries if it exceeds 60 minutes -- is the mechanism
that catches this early rather than in month six. At exactly 60 minutes per entry the 320-entry seed
is about 340 hours, or 17 weeks of curation alone.

**What the differentiating core costs, computed separately** -- because the same 150-450 figure was
previously used for both the whole seed and the non-LLM core, and both could not be true. The
five-family non-LLM core (robotics-embodiment, chemistry-materials, biology-genetics, earth-climate,
physics) is **~120 Tier-1 families estimated to exist** and **106 targeted** under the canonical
allocation. Six of the ten named stress cases fall in these five families -- RoboArena, CACHE,
CASP17, WeatherBench 2, Matbench Discovery, Virtual Cell Challenge -- so the cost is (100 x
0.5-1.5 h) + (6 x 2-3 h) = **62-168 person-hours**. That is the highest-value block of curator time
in the project and it is roughly a third of the seed's cost. The seven-family Core set used as a
launch gate elsewhere is a different set again -- 163 estimated, 144 targeted -- and every document
quoting a "core" figure should say which set it means.

**What ingestion does and does not buy.** [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)
§11 quantifies this per entity, and the headline is worth repeating because over-claiming it is how
a team gets demoralised at month four: ingestion moves the `Benchmark` entity from zero to about 15%
machine-filled, and `EvalConditions` to about 10%. **Ingestion makes claim count free and makes
condition completeness expensive.** It buys coverage -- exactly what the user asked for, a great
searchable collection -- and almost none of comparability, which is where credibility lives.

---

## 12. Where we are structurally weaker

A positioning document that only lists strengths is marketing. These are real and permanent, and
each has a stated substitute.

**We will never be fresher than a live leaderboard.** Arena updates continuously; Epoch's export
dated 2026-09-16 already contained a model released 2026-09-03. Our ingestion runs on a GitHub
Actions cron and our hand-curation runs at human speed. *What we do instead:* we timestamp
everything, we show `retrieved_at` on every ingested figure, and we treat the leaderboard as the
authority we link to rather than the thing we replace. A dated snapshot that is honest about its
date is more useful than a live number with no conditions.

**We will never be more authoritative on a single benchmark than its maintainer.** The SWE-bench
team knows SWE-bench better than we ever will; so does the CASP Prediction Center about CASP.
*What we do instead:* we make the maintainer's own page the primary link, we record their stated
conditions rather than inferring, and we design the contribution path so that a maintainer
correcting their own entry is a two-minute issue form rather than a pull request.

**We cannot verify numbers we did not produce.** We do not run evaluations, by hard constraint.
Every claim we hold is either self-reported, scraped, or reproduced by a third party. *What we do
instead:* we make the verification level a first-class, visible, sortable field, and we default
comparison views to hiding claims below a completeness threshold. Our contribution is not
verification; it is making the *absence* of verification legible.

The honest reading of Epoch's own corpus is the worked example, and it is stated here with its
derivation because an epistemics argument that does not survive a recount is worse than no argument
at all. From `_workflow/recon/recon_epoch-assets.md`, counted against the `epochdl/` export dated
2026-09-16: the 80 per-benchmark CSVs hold **6,598 data rows**. Of those, **1,550 rows in 14
Epoch-run files** carry log columns, split **828 rows with a public S3 bucket URL, 459 with a
private bucket URL, and 263 with no log link at all**; the other **5,048 rows across 66 files** are
leaderboard or paper scrapes with no run artifact. A later recount of the same files split the same
1,287 log-bearing rows a different way -- **962 rows carrying an Inspect log-viewer URL and 325
carrying a storage-bucket URL only** -- so the two decompositions agree on the totals (1,287 rows
with a log, 263 without, 1,550 in the Epoch-run family) and differ only in which column they split
on. Either way: **19.5% of the rows in the best-quality public benchmark dataset in existence carry a
log link of any kind (1,287 of 6,598), and only 12.5% carry a publicly retrievable one (828 of
6,598).** We can say
that out loud; nobody else does. Two further derivations, stated because the earlier draft asserted
them flat: `benchmark_metadata.csv` carries **81 rows** while **80 per-benchmark CSVs** exist on disk
(one metadata row has no CSV, and 21 CSVs are unreferenced by any metadata row); and the hub's
advertised **390 models** does not match the export, which carries **1,063 rows in
`model_metadata.csv`, 1,048 distinct `model_version` keys, 550 distinct `model_group` identities,
927 distinct `model_version` strings inside the benchmark CSVs, and 266 models in the ECI fit** --
five different populations, none of them 390, and the discrepancy is unresolved *(unverified --
recount at ingest time)*.

Note that `epochdl/` is not currently in the working tree, so none of the figures above can be
recomputed today. That is itself the lesson: **every number in this plan derived from a local
artifact must name the artifact, the filter and the date, and must be reproducible by a committed
script.** `scripts/epoch_audit.py` is a Phase-0 deliverable, it re-derives every figure in this
paragraph, and its output is committed alongside the ingest manifest.

**We will always be smaller than the automated scrapers on raw count.** Benchmark Radar ingests
14,810 raw records; BenchmarkList claims 2,545 benchmarks and 24,074 models. *What we do instead:*
we compete on the curated number, exactly as Benchmark Radar's own gap between 14,810 raw and
~1,283 curated illustrates. §15 is honest about why saying so plainly is not sufficient.

**We have no institutional home, no grant, and no staff.** §3's mortality analysis applies to us at
least as strongly as to Stanford CRFM. *What we do instead:* CC-BY, a DOI per release, forkability
at a commit hash, an issue-form contribution path, per-domain stewardship, and a written succession
plan. We cannot make ourselves immortal; we can make our death non-fatal to the data. The succession
story is asserted repeatedly in this plan, so its shape belongs here even though the mechanism lives
in [05-repository-and-workflow.md](05-repository-and-workflow.md) and
[15-open-questions.md](15-open-questions.md) C5 -- a contributor asking "why should I put work into
your repository" is asking a positioning question:

- `SUCCESSION.md` at the repository root, written in month one, naming the data licence (CC-BY-4.0),
  the Zenodo concept DOI plus per-release versioned DOIs, and the depositor of record by handle and
  ORCID, because a DOI whose depositor cannot be identified cannot be transferred.
- A data-only export that is independent of the site code, so a successor inherits the corpus
  without inheriting our build.
- A named, maintained list of organisations pre-approached about stewardship, with per-domain
  stewards listed first because MedHELM is the case that worked. The list itself is owned by
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §"What happens when we stop" and is
  deliberately not re-listed here — three documents carrying three slightly different lists is how a
  succession plan becomes unactionable.
- **An automatic dormancy mechanism, because by definition nobody will be there to act on a
  document.** If the newest commit touching `data/` is older than **180 days**
  ([15-open-questions.md](15-open-questions.md) C5 owns the threshold), the build renders a
  site-wide staleness banner with the date, commits a dated `STATUS: unmaintained since YYYY-MM-DD`
  file, opens an issue titled "Project dormant -- seeking steward", and notifies the steward list.
  This is the single concrete thing Ecosystem Graphs lacked. Test it in CI with a fake clock; an
  untested dormancy trigger is a promise, not a mechanism.
- The domain prepaid for the longest term the registrar offers, with the expiry recorded in
  `SUCCESSION.md`, because that is the one succession commitment that can be funded now rather than
  promised.

**Per-domain stewardship is the scaling model, and it is a job, not a wish.** §3.4's MedHELM lesson
only pays off if the steward role is specified. Three lines: a steward owns one domain family's
facet vocabulary and reviews entries in it, and their authority is a path-scoped `CODEOWNERS` entry
over `data/benchmarks/<family>/` and nothing more; recruitment is "ship 20 entries in their field,
then email the benchmarks' own maintainers asking them to correct us", because being wrong in public
is the cheapest recruitment mechanism available and it doubles as the correction path; and a steward
with no review activity for two quarters is removed from `CODEOWNERS` automatically and the family
is rendered `steward: none` on the site. [15-open-questions.md](15-open-questions.md) B3 owns
recruitment and what we offer reviewers; the removal rule is new here and belongs in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §governance. Be honest about the
overhead: recruiting and coordinating even six stewards is a recurring job for a two-person team,
which is why §14 ranks it fifth rather than first.

**Our taxonomy will be wrong in every specialist's field at first.** A robotics researcher will
find our robotics facets naive; so will a structural biologist. *What we do instead:* we ship the
taxonomy as versioned, governed, publicly-diffable data with an explicit change process, and we
recruit domain reviewers rather than pretending to be them. See
[03-taxonomy-build-process.md](03-taxonomy-build-process.md).

---

## 13. Defensibility: what stops a well-resourced incumbent copying us?

Honestly: nothing stops them. The realistic question is not whether the moat is impassable but
whether crossing it is worth their while, and what happens to us if they do.

**Curation labour is the moat, and it is the kind nobody wants.** The differentiating core is 106
targeted families at **62-168 person-hours** of domain-literate work (§11 shows the arithmetic).
That work does not convert into a ranking, which is the product every incumbent actually sells.
Epoch has the resources and has spent them on 81 LLM benchmarks with its own runs -- a deliberate
depth-over-breadth choice, not an oversight. Arena has a large Series A and has spent it on 13
arenas of human preference. BenchmarkList's two people are scraping, which produces coverage but
produced an OC22 entry dated 2026-05-28 for a 2022 dataset -- one observation, indicative rather
than proven, but exactly the error class that automated breadth produces. **A cross-domain catalogue
is a bad business and a good public good**, which is why the ground is still open and why the right
owner of it is not a company.

**Taxonomy quality is harder to copy than data.** Anyone can scrape 2,500 benchmark names in a
week. Nobody can produce a facet vocabulary that a roboticist, a structural biologist and an NLP
researcher all recognise as correct without doing the reading. The stress-test set -- RoboArena's
double-blind pairwise physical evaluation, CACHE's wet-lab hit rates and compound-purchase
requirement, CASP's separately ranked human-expert and automated-server categories, WeatherBench 2's
deliberate refusal to aggregate, Matbench Discovery's training-data eligibility tiers, ForecastBench's
results that resolve months later -- is the actual barrier, and it is a reading barrier, not a
compute barrier. See [02-taxonomy.md](02-taxonomy.md).

**Being copied is partly the point.** The data is CC-BY at a commit hash with a DOI. If a
well-resourced incumbent ingests all of it and builds a better interface, the project has succeeded
at its stated purpose: the metadata layer the field lacks now exists and is being used. That is not
a loss condition. The loss condition is the data going stale with our name on it. This inverts the
usual competitive logic in a way worth stating explicitly to contributors, because it is also the
argument for why contributing here is safe: nothing anyone contributes can be enclosed later, which
is exactly what happened to llm-leaderboard's contributors when it became llm-stats.com.

**The standard is the real defensibility, and it is also the most seductive way to waste six
months.** If `croissant-benchmark` is published as a namespaced extension to MLCommons Croissant and
adopted, the project stops being a website that can be out-competed and becomes a vocabulary that
competitors consume -- with Google Dataset Search as free distribution and MLCommons as a potential
institutional home. Croissant is already adopted across HuggingFace, Kaggle, OpenML, TFDS and Google
Dataset Search, and it has no evaluation extension. The scope, the mapping sketch (four new classes
and two new properties under a `cb:` namespace), the sizing (10-20 hours, owned by
[14-roadmap.md](14-roadmap.md)) and the approach bar are settled in
[15-open-questions.md](15-open-questions.md) A8: **design for it in Phase 0, emit
`croissant.jsonld` per benchmark from the Phase 2 build as an explicitly unofficial extension, and
approach the MLCommons Datasets WG only after public v1, when the emitter runs over the whole corpus
and three worked examples from three genuinely different domains exist.** The word doing the heavy
lifting in the sentence "if it is published and adopted" is *adopted*, and whether the working group
would accept such an extension at all is **unverified**. Two constraints: the spec is CC BY-ND, so we
may publish an extension in our own namespace and must never republish a modified spec; and the
failure mode, named plainly -- *standards work is the most seductive way for a two-person team to
spend six months producing nothing a user can look at*, which is why nothing here happens before
the seed release, and why the fallback if the WG declines is that we keep the namespace and it
degrades into "our JSON-LD serialisation", which is still useful.

**What actually kills us is not competition.** It is the curation treadmill, and §3 is the evidence.
Plan accordingly.

---

## 14. Complement, do not compete

The fastest route to adoption, contributors and institutional credibility is to be *useful to the
incumbents*. [15-open-questions.md](15-open-questions.md) E4 owns the outreach programme and sizes
it at **6-10 person-days total**, which is the number that matters: at 20 h/week that is two to four
weeks competing directly with curation. Its ordering is adopted here unchanged, with two zero-cost
items promoted ahead of it because they are unilateral and cost nothing:

| # | Ask | Cost | Why it is in this position |
| --- | --- | --- | --- |
| 0a | **Send them traffic and say so.** Every benchmark page links to the maintainer's page, the paper DOI, the leaderboard carrying its numbers, and the harness that can run it | Zero -- it is the page design | Free, immediate, and the honest answer to "why should a leaderboard operator tolerate us": we increase their qualified traffic and never reproduce their ranking |
| 0b | **Cross-reference identifiers as first-class fields** | Small and unilateral | Each one makes us a join table rather than a rival. See the cut list below |
| 1 | **Propose the registry/results split to EvalEval** | 1-2 days | HuggingFace, Edinburgh and EleutherAI behind them, CC BY 4.0 on both sides, no product collision. Highest-value single contact in the landscape |
| 2 | **Offer `inspect_evals_id` cross-references to UK AISI** | 0.5-1 day | Makes us the front door to their harness. We copied their `/register/` pattern and saying so is good manners and good positioning |
| 3 | **One post per unindexed domain, robotics first** | 0.5 day each | The differentiator is legible in thirty seconds in robotics and invisible in a generalist launch post |
| 4 | **The arXiv technical report, carrying the coverage and gap matrix** | 3-5 days | See below |
| 5 | **Steward recruitment** | Recurring | Specified in §12; it is the scaling model but it cannot precede having something to steward |
| 6 | **`croissant-benchmark` to the MLCommons Datasets WG** | Inside the 10-20 h Croissant budget | Only after the emitter and three cross-domain examples exist (§13) |

**Items 5 and 6 happen only if 1-4 land.** Doing all seven at 15% each produces nothing, and that is
precisely how a two-person project with good ideas ends with a stale repository and an unpublished
draft.

**On the paper, because citation is the survival currency of this category.** Every near-survivor in
§3 ran on a citation: Benchmark Radar launched with arXiv 2609.11115, EvalEval with 2606.14516 and
48 authors, BetterBench as a NeurIPS Spotlight, HELM as a paper. The most chilling detail in §3.2 is
that Ecosystem Graphs is still cited as a data source while 20 months stale -- citation is what kept
it alive in the literature after it died in git. A purely relational adoption plan is the weakest
available channel for a project with no institutional home. The **coverage and gap matrix**
([12-analytics-and-trends.md](12-analytics-and-trends.md)) is the one output nobody else has and the
one that reads as a research contribution rather than a website launch; it is the natural companion
to Benchmark Radar's and EvalEval's reports, and it is the core of the arXiv technical report at
item 4. *The risk, stated:* a paper freezes a snapshot of a live artifact, so the report must cite a
DOI'd release tag and never the live site, or the paper becomes the Ecosystem Graphs problem with our
name on it. A NeurIPS Datasets & Benchmarks submission is a post-v1 question and the honest answer at
v1 is no -- [15-open-questions.md](15-open-questions.md) E4 explains why the bar is not met at 320
entries by construction.

**On cross-reference IDs, which were previously waved through as "cheap".** They are not cheap.
Matching "SWE-bench Verified" across eight naming conventions is the hardest recurring problem in
the plan, not a field list. So:

- **v1 carries three**: `epoch_id`, `inspect_evals_id`, `eee_id`. All three sources are CC-BY or MIT,
  all three have real payoff, and all three are things we ingest anyway.
- **Phase 3+ for the rest**: `hf_dataset_id`, `grand_challenge_id`, `croissant_url`, `pwc_id`
  (keys-only per §7.5).
- **The matching mechanism, in one sentence**, with detail deferred to
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §5: normalised-name plus
  alias-table exact match first, human confirmation for everything else, and **no fuzzy match is ever
  auto-committed**.
- **The recurring cost, stated honestly**: upstream IDs churn, so each cross-reference needs a
  quarterly re-check -- budget roughly 2 hours per source per quarter, which at three sources is
  24 hours a year of pure maintenance before any new entry is written.
- **`radar_id` is resolved rather than left contradictory.** §5 row 2 forbids ingesting Benchmark
  Radar's content while [05-repository-and-workflow.md](05-repository-and-workflow.md) §11 permits a
  `radar_id` interop field, and systematically harvesting their ID set would be extraction from a
  CC BY-NC-SA database -- the thing we forbid. The rule that reconciles them, per §6 point 3: **a
  curator or contributor may record a Benchmark Radar URL on an entry they are already looking at;
  no adapter may enumerate their IDs.** Record it as a plain `external_links` URL rather than a
  harvested ID column, and keep it out of the Phase-1 field set.

**Offer the metadata layer they lack.** Every leaderboard in §2.1 has the same hole: rich numbers
with no benchmark-level metadata. A leaderboard that wants to show licence, access model,
contamination status, version lineage and domain facets next to its scores currently has to build
that itself. Our CC-BY JSON artifact is exactly that layer, free to consume, joinable on a stable ID.

**Copy, credit and reciprocate.** We take UK AISI's `/register/` contribution pattern, BetterBench's
46-criterion quality rubric as the ancestry for our maturity fields, HELM's scenario taxonomy as
the ancestry for our modality vocabulary, Epoch's `superseded_by` as the seed of our lineage model,
and HuggingFace's `test:*` / `judge:*` / `submission:*` tag vocabulary as the seed of our conditions
vocabulary. Each is cited by name in the taxonomy documentation. Good-faith attribution to CRFM,
AISI, Stanford and HuggingFace costs nothing and is the cheapest credibility available to a project
with no institutional home.

**Fill the regulatory gap rather than claiming it.** EU AI Act GPAI obligations became enforceable
2026-08-02 and require evaluation "using standard benchmarks and state-of-the-art tests" with no
registry defining what qualifies. NIST AI 800-2 (initial public draft, January 2026) and the
ten-country International Network for Advanced AI Measurement are writing *practices*, not
catalogues. The UK announced a Centre for AI Measurement at NPL in January 2026. OECD's catalogue
covers governance tools and explicitly disclaims vetting. A neutral, sourced, CC-BY benchmark
registry is the obvious missing reference artifact. *The posture that works:* publish the data, make
it citable, and let it be used -- not claim standing we do not have. We are not a regulator and must
never present as one.

**The failure mode to avoid here** is the adversarial framing. A two-person project that positions
itself as the competitor to a well-funded company and a HuggingFace-backed coalition gets neither
contributors nor citations. The projects that survived in §3 survived by being depended upon
(§3.5), by finding a steward (MedHELM), or by being consumed by others (Croissant). All three routes
run through being useful first.

---

## 15. How this positioning fails in practice

This document is good at naming failure modes in other people's projects. Three specific ways the
strategy proposed here fails, each with the mitigation that has to be designed in rather than
noticed later.

**1. Ingestion makes us look like the thing we said we were not.** After the Epoch adapter runs,
roughly 6,600 of about 6,900 claims are LLM leaderboard scrapes. A first-time visitor lands on a site
that is ~96% language-model numbers and concludes we are a worse Epoch mirror -- which is exactly the
repetition the owner asked us to avoid, arriving through the back door of a decision made to avoid
it. *Mitigation, and it is a product decision not a comms one:* the default landing view is the
coverage and gap matrix, not a claim list; machine-ingested claims are excluded from every default
view and from every homepage count; and the headline figure we publish is **curated families per
domain**, never total rows. [10-visualization.md](10-visualization.md) owns the landing view and this
is a requirement on it.

**2. Nobody can tell 320 curated from 2,545 scraped.** §12 says we compete on the curated number and
say so plainly. Saying so plainly does not work: BenchmarkList wins every casual comparison, every
search-result snippet and every screenshot. *Mitigation:* the differentiator has to be visible on a
single page without a comparison being made. Two things do that and nothing else does -- a
per-benchmark page showing per-field provenance with a `retrieved_at` on every cell, which no
competitor can produce without doing the work, and the gap matrix, which is a shareable artifact with
no equivalent anywhere. Both are design requirements, not marketing lines.

**3. Co-founder attrition at month nine.** §3 establishes this as the modal death of the category and
§12 concedes there is no institutional home, but the specific event is worth naming: one of two
part-time people loses interest, and the other inherits both the curation treadmill and the
infrastructure. The dormancy trigger in §12 exists because this is the most likely single cause of
death, and the test of it is whether **it is executable by a stranger who has never met us** -- which
means the succession document names artifacts and licences, not people and intentions, and the banner
fires without anyone deciding it should.

---

## 16. What would falsify this positioning

Stating the conditions under which this document is wrong, so that they can be checked rather than
argued:

- **If Every Eval Ever ships a benchmark-entity catalogue with a domain taxonomy**, our overlap with
  them moves from Complementary to High and the correct response is to contribute rather than
  duplicate.
- **If BenchmarkList publishes an open licence and a bulk export**, our licence wedge largely
  disappears and the remaining differentiators are the conditions model, the lineage model and the
  gap matrix. ([15-open-questions.md](15-open-questions.md) E5 carries the fuller answer.)
- **If Benchmark Radar relicenses its content to CC-BY**, ingestion becomes possible and the right
  move is collaboration, not competition.
- **If a government registry appears** at NIST/CAISI, the EU AI Office or UK AISI, the project's
  role shifts from filling a vacuum to feeding one. That is a good outcome and should be planned
  for rather than resisted.
- **If the measured entity overlap from §4's 50-family sample comes back above 80% for any
  competitor**, the breadth claim is weaker than stated and the positioning narrows to conditions,
  lineage and licence.
- **If our own curated non-LLM count stalls below the per-family floor of 12 for two consecutive
  quarters**, the cross-domain claim is not true in practice and the positioning must be narrowed to
  the domains we actually cover. This is the internal check that matters most.

**The mechanism, because "check quarterly" with no owner is not a check.** A scheduled GitHub Action
opens an issue on the first day of each quarter titled "Quarterly landscape review", pre-populated
with this list as a task list plus the `maintenance_prognosis` re-score from §7.2 for every Tier-1
source. The issue is assigned to the curation lead and closing it requires either a dated "no change"
comment per item or a linked commit. It costs about an hour a quarter and it is the only thing that
stops this document from becoming the stale artifact it spends §3 warning about.

---

## 17. Summary

| Question | Answer |
| --- | --- |
| Is the ground empty? | No. BenchmarkList (closed), Benchmark Radar (NC-licensed) and Every Eval Ever (complementary) occupy it. Say so plainly, everywhere. |
| What is genuinely unoccupied? | Non-language domains at depth, benchmark lineage, comparability-as-refusal, liveness signalling, a live gap matrix, plain CC-BY, and a Croissant benchmark extension. |
| How much do we overlap with them? | In bands, not percentages, until the 50-family sample in §4 runs -- a sample that size carries a ±14pp 95% interval, which is why the earlier point estimates were over-read. |
| Has anyone tried and failed? | Every cross-domain catalogue older than two years. Papers with Code, Ecosystem Graphs, llm-leaderboard, HELM, Open LLM Leaderboard, BIG-bench, Evidently, BetterBench, HAL, Dynabench. Causes: curation load, single-owner deprioritisation, contribution friction, no licence. |
| What survived, and why? | HuggingFace Hub, OpenAlex, Zenodo/DataCite, Croissant, lm-evaluation-harness, MTEB -- all dependencies of other software. Survival correlates with being depended upon, not with being visited. |
| How do we avoid repetition? | The three-question procedure in §7, with Q3 scored not judged, routing every fact to INGEST / INGEST-ONCE / LINK / CURATE before any work begins -- plus the volume policy in §8 that stops discovery firehoses swamping the curated core. |
| Where does hand-curation go? | Nine of nineteen families hand-curate, four mixed, six ingest-then-verify (§10). The five-family non-LLM core is 106 targeted entries at 62-168 person-hours; the 320-entry seed is 175-495. |
| Where are we weaker? | Freshness, per-benchmark authority, verification, raw count, institutional backing, and initial taxonomy quality. Each has a stated substitute, not a denial. |
| How does this positioning fail? | Ingestion making us look like an LLM mirror; nobody being able to tell curated from scraped at a glance; co-founder attrition at month nine (§15). |
| What is the moat? | Curation labour nobody wants to spend, taxonomy quality that requires reading, and CC-BY forkability that makes being copied a success rather than a loss. |

---

*Related: [00-vision-and-scope.md](00-vision-and-scope.md) for what the project is and is not;
[02-taxonomy.md](02-taxonomy.md) §3 for the domain families, the seed allocation and the floor rule
this positioning depends on; [04-data-model.md](04-data-model.md) for the provenance, verification
and `maintenance_prognosis` fields that make the boundaries enforceable;
[05-repository-and-workflow.md](05-repository-and-workflow.md) for the issue-form contribution path,
the CI checks in §9 and the succession mechanism;
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) for the source catalogue, the licence
resolutions owed under §6 and the Papers-with-Code quarantine;
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) for how ingestion actually runs and
what it costs;
[10-visualization.md](10-visualization.md) for the ecosystem views these tables feed and the landing
view §15 constrains;
[12-analytics-and-trends.md](12-analytics-and-trends.md) for the coverage and gap matrix;
[14-roadmap.md](14-roadmap.md) for phasing, the claim gate, the effort table and the risk register;
[15-open-questions.md](15-open-questions.md) for A4 (licensing), A5 (the PwC firewall), A8
(Croissant), B3 (domain reviewers), C5 (succession) and E4 (publication and outreach).*
