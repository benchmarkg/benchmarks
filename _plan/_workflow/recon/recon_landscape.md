Research complete. Writing up findings.

---

# COMPETITIVE / ADJACENT LANDSCAPE — Universal AI Benchmark Index

All entries verified live on **2026-09-17** unless marked UNVERIFIED. Format: **Name** | URL | operator | coverage | type | API/bulk | licence | freshness | *what it does NOT do that we would*.

## ⚠️ HEADLINE FINDING (read first)

**Two projects launched in the last 14 months are近 the exact concept.** Neither existed in most training data:

1. **BenchmarkList** (benchmarklist.com) — launched **2026-07-15**, 2,545 benchmarks, cross-domain, closed.
2. **Benchmark Radar** (benchmark-radar.org) — arXiv tech report **2026-09-10** (2609.11115), open source, CC BY-NC-SA.

Plus **Every Eval Ever** (EvalEval Coalition: HuggingFace + Edinburgh + EleutherAI), arXiv 2606.14516, CC BY 4.0, 2,273 benchmarks / 22,235 models. The "nobody has done this" premise is **no longer true as stated** — but all three have exploitable gaps (below).

---

## 1. LIVE LLM LEADERBOARDS & EVAL SERVICES

**Arena (ex-LMArena / Chatbot Arena)** | arena.ai (lmarena.ai 301-redirects) | Arena Intelligence Inc. | 13 leaderboards: Agent, Text, WebDev, Image-to-WebDev, Text-to-Image, Image Edit, Text-to-Video, Image-to-Video, Video Edit, Vision, Document, Search; 696 models in Text | **leaderboard** | **YES — HF `lmarena-ai/leaderboard-dataset`, 2.36M rows / 117MB, snapshots** | **CC-BY-4.0** | updated 2026-09-15 | *Human-preference Elo only; no benchmark metadata, no non-language-model domains, no eval-condition schema.*
> Funding: $100M May 2025 (~$600M val), **$150M Series A Jan 2026** (~$1.7B val, Felicis + UC Investments). Renamed to Arena **2026-01-28**.

**Artificial Analysis** | artificialanalysis.ai | private co. | 30+ evals; Intelligence/Coding/Agentic/Math/Openness/Multilingual indices; text, image, video, speech, music | **leaderboard + index** | **YES — Data API** (`/language/models/free`, media endpoints, measurements, CritPt) | **Attribution required all tiers; redistribution needs commercial contract. NOT open.** Free tier **100 req/24h** (one page said 1,000/day — conflicting, treat as UNVERIFIED) | live | *Proprietary composite scores; no catalogue of benchmarks it doesn't run; redistribution blocked.*

**Epoch AI Benchmarking Hub + ECI** | epoch.ai/benchmarks, epoch.ai/eci | Epoch AI (non-profit) | **80 benchmarks, 390 models**; math, SWE, agentic, games, multimodal, long-context, science, world knowledge, writing. **Language/agent only — no robotics/protein/weather/materials** | **registry + leaderboard, runs some evals itself (via Inspect)** | **YES — CSV/ZIP download + Python client; `benchmark_data.zip`, `eci_scores.csv`, `benchmarks.json`** | **CC-BY** | **updated 2026-09-17** | *80 benchmarks vs our target scope; LLM-centric; composite index (ECI) is the thing we explicitly refuse to build.*
> **User already has this locally at `E:\AI\_Project\Project (intelligence-benchmark)\benchmarks\epochdl\`** — 85 files, `benchmark_metadata.csv` schema: `benchmark,in_eci,source_file,score_column,scale,random_baseline,score_ceiling,release_date,superseded_by`. Per-benchmark CSVs carry `Model version, mean_score, Best score (across scorers), Release date, Organization, Country, Training compute (FLOP), stderr, Log viewer, Logs, Started at, id`. **Note `superseded_by` — Epoch has already begun modelling benchmark lineage. Validates our versioning differentiator.**

**LiveBench** | livebench.ai | Colin White et al., sponsored by **Abacus.AI**; ICLR 2025 Spotlight | 7 categories / 23 tasks: reasoning, coding, agentic coding, math, data analysis, language, instruction following | **leaderboard (contamination-limited, monthly refresh)** | GitHub `LiveBench/LiveBench` | check repo (UNVERIFIED exact licence) | latest release **2026-06-25** | *Single benchmark family; no catalogue function.*

**Vals AI** | vals.ai | Vals AI Inc. — founders **Rayan Krishnan, Langston Nashold** (Stanford); **$40M Series A 2026-08-13 led by a16z at $400M val**; $5M seed Apr 2024 (8VC, Bloomberg Beta, Sequoia, Pear) | 25+ benchmarks: finance, legal, medical, tax, SWE, math; partners incl. Harvard Medical School, Code for America | **eval service + public leaderboard** | results public; **no API/download observed** | not stated | Sep 2026 | *Runs its own private evals as a commercial moat; will never catalogue competitors' benchmarks.*

**Scale SEAL / Scale Labs** | labs.scale.com/leaderboard (scale.com/leaderboard 308-redirects) | Scale Inc. | 20+ benchmarks across Agentic (DrugDiscoveryBench, SWE Atlas, SWE-Bench Pro, MCP Atlas), Frontier reasoning (HLE, MultiChallenge, EnigmaEval, TutorBench), Safety (PropensityBench, MASK, Fortress), audio, finance/legal, multilingual | **leaderboard** | **no download; private prompt sets; "models featured only the FIRST TIME an org encounters the prompts"** | closed | active (GPT-6 Astra, Fable-5.1 listed) | *Deliberately unreproducible by design — we can only ever link to it.*

**SWE-bench** | swebench.com | Princeton/Stanford academic team | variants: original, **Verified, Lite, Multimodal, Multilingual, Pro**; "Bash Only" is a leaderboard filter not a variant | **leaderboard + dataset family** | GitHub/HF | UNVERIFIED | active | *One task family; the fork proliferation is precisely the versioning problem we'd model.*

**Aider leaderboards** | aider.chat/docs/leaderboards | Paul Gauthier | polyglot (225 Exercism exercises / 6 langs), code editing, refactoring | leaderboard | in Aider GitHub repo | UNVERIFIED | **last updated 2025-11-20 — ~10 months stale** | *Effectively frozen; a stale-source case study.*

**OpenRouter rankings** | openrouter.ai/rankings | OpenRouter | **usage/token share, NOT benchmarks**: weekly usage, top models by task, cost/session, latency, context length, tool calling | **usage leaderboard** | **YES — Data API, JSON** | **CC BY 4.0** | **2026-09-16** | *Measures adoption not capability — genuinely complementary signal we could embed.*

**HuggingFace Open LLM Leaderboard** | huggingface.co/spaces/open-llm-leaderboard | HuggingFace | v1 archived **June 2024**; **v2 retired March 2025** after 13,000+ models | **ARCHIVED leaderboard** | historical results still loadable via `datasets` | Apache/HF terms | **DEAD since 2025-03-14** | *n/a — cautionary tale, see §5.*

**Also found (secondary aggregators, all closed/thin):** BenchLM.ai (439 LLM evals, knowledge/coding/math only, no API/licence, v5.5 methodology 2026-09-04); llm-stats.com (300+ models, ~9 benchmarks; its git predecessor **deprecated** — see §5); lmmarketcap.com (Analyxa LLC, 21 benchmarks / 161 models, `llms.txt` + `llms-full.txt`, **© all rights reserved**, updated hourly); smplmark.org (smplkit.com; ~100 benchmarks but mostly **hardware/DB/HPC** — CPU, GPU, SPEC, ClickBench, TPC — plus some ML; has an API reference); pricepertoken.com; benchmarkingagents.com; codesota.com (Kacper Wikiel / Fabryka, Warsaw — explicit PWC-successor positioning, "readable by humans, callable by agents").

---

## 2. EVAL HARNESSES / FRAMEWORKS

**EleutherAI lm-evaluation-harness** | github.com/EleutherAI/lm-evaluation-harness | EleutherAI | 60+ academic benchmarks, hundreds of subtasks; **YAML task registry**; limited multimodal (`hf-multimodal`, `vllm-vlm`, `mmmu`) — defers to `lmms-eval` | **harness** | YAML task configs in-repo | **MIT** | active (4,122 commits) | *Harness not catalogue; no metadata about benchmarks it doesn't implement.*

**UK AISI Inspect + inspect_evals** | inspect.aisi.org.uk, github.com/UKGovernmentBEIS/inspect_evals | **UK AI Security Institute + Arcadia Impact + Vector Institute** (framework co-developed w/ Meridian Labs) | **171 evals (129 internal / 42 external)**; coding, cyber, math, reasoning, knowledge, multimodal, agentic, safeguards, scheming, bias, personality, writing | **harness + REGISTRY** | **`/register/` folder launched 2026-05-08 — GitHub-issue submission, bot validates and DERIVES EVAL METADATA, auto-PR** | **MIT** | **pushed 2026-09-17, 674★** | *Only evals implemented in Inspect; no non-language domains; no cross-domain taxonomy or coverage analysis.* **← closest institutional analogue to our curation model, and MIT-licensed.**

**Stanford HELM** | crfm.stanford.edu/helm | Stanford CRFM | **Variants: HELM Capabilities, HELM Safety, VHELM (vision-language), HELM Classic, HEIM (text-to-image), The Mighty ToRR (tables), MedHELM, AudioHELM** (+ Lite, Instruct, LegalHELM, AirHELM referenced) | harness + leaderboards | JSON results; `crfm-helm` on PyPI | **MIT** | **⚠️ "HELM entered maintenance mode on June 1, 2026"** (verbatim from repo README) | *Maintenance mode; language+vision+audio only; no robotics/science domains.* **MedHELM spun out 2026 as independent community project, Apache 2.0, technical stewardship by Pacific AI — 121 clinical tasks / 22 subcategories / 31 datasets / 5 categories.**

**OpenCompass** | github.com/open-compass/opencompass, rank.opencompass.org.cn | Shanghai AI Lab | 70–100+ datasets, ~400k eval questions; **CompassKit / CompassHub (benchmark browser) / CompassRank (leaderboard)** | harness + hub + leaderboard | GitHub | Apache 2.0 (UNVERIFIED) | active — RawPromptTemplate Mar 2026; **multimodal eval deprecated Apr 2026, moved to VLMEvalKit** | *CompassHub is a benchmark browser but Chinese-ecosystem-centric and LLM-only.*

**OpenAI Evals** | github.com/openai/evals | OpenAI | self-described "open-source **registry of benchmarks**" | harness + registry | GitHub | "Other" (non-SPDX) | **pushed 2026-04-14, 19,469★, 340 open issues** | *Registry of evals runnable in their format; effectively unmaintained as a catalogue.*

**MTEB** | github.com/embeddings-benchmark/mteb | community | embeddings across languages **and modalities** | harness + leaderboard | GitHub + HF | **Apache-2.0** | **pushed 2026-09-16, 3,425★** | *Embeddings only — but the best-run single-domain example to imitate.*

**Others:** LightEval (HuggingFace, harness); **BIG-bench — GitHub ARCHIVED 2026-04-17, read-only**; promptfoo (MIT core; **acquired into OpenAI Frontier infrastructure March 2026**, committed to keep core MIT + model-agnostic); Braintrust (eval-first, 10k free scores then $2.50/1k); LangSmith ($39/seat, LangChain/LangGraph tracing); DeepEval; RAGAS. *All of these are test-execution infrastructure — they sell running evals, not finding them. Very low overlap; potential distribution partners.*

---

## 3. DATASET / PAPER REGISTRIES

**Papers with Code — ✅ CONFIRMED DEAD** | paperswithcode.com | Meta AI Research (acquired Dec 2019) | **Sunset 2025-07-24**; domain now **301s to huggingface.co/papers/trending**. HF CTO Julien Chaumond announced Meta partnership the following day. | was catalogue+leaderboard | **archive live: github.com/paperswithcode/paperswithcode-data + sota-extractor** — 5 files: papers-with-abstracts, links-between-papers-and-code, **evaluation-tables**, methods, datasets | **CC-BY-SA-4.0 ⚠️ VIRAL/SHARE-ALIKE** | **frozen. Final scale: 9,327 benchmarks / 5,628 datasets / 79,817 paper↔code links / 1,000+ tasks** | *Was the closest thing to a universal benchmark index; now frozen. Its corpse is our best cold-start seed — with a licence quarantine.*

**HuggingFace Hub** | huggingface.co | HuggingFace | datasets, models, Spaces leaderboards, Daily/Trending Papers | registry | **YES — free public `huggingface.co/api` (no token); `/api/datasets/{name}/croissant` returns Croissant JSON-LD per dataset** | per-artifact | live | *No benchmark-vs-dataset distinction, no eval conditions, no cross-domain taxonomy. `OpenEvals/every-leaderboards` Space unifies only 11 HF benchmarks.*

**OpenAlex** | openalex.org | OurResearch | ~250M works, incl. arXiv/Zenodo/PubMed/Crossref/ORCID/ROR/DOAJ/Unpaywall | registry | **YES — API + monthly full AWS S3 snapshot** | **CC0** ⭐ | monthly | *Papers not benchmarks — but free citation/venue/author enrichment at zero licence risk.*

**Codabench** | codabench.org | **Université Paris-Saclay (community lead), LISN staff admin**; successor to CodaLab (Microsoft+Stanford 2013, ChaLearn 2014) | **1,498 public competitions, 80,406 users, 722,037 submissions**; supports "inverted benchmarks" | competition platform | **YES — `/api/docs/`**, open source github.com/codalab/codabench | UNVERIFIED | v1.31.2, 50k users as of Feb 2026; CodaLab Competitions v1.6 still at codalab.lisn.fr | *Hosts competitions; no cross-competition metadata layer or discovery.*

**EvalAI** | eval.ai | CloudCV | challenges across CV/NLP/RL | competition platform | open source | UNVERIFIED | **page returned EMPTY on fetch — liveness UNVERIFIED, flag for manual check** | *n/a*

**Also:** Kaggle (competitions + datasets, Croissant export), Zenodo (DOI minting — relevant to our own DOI plan), Semantic Scholar (API under S2 ToS, **not** CC0 — prefer OpenAlex), OpenML (**fetch returned title only — counts/licence UNVERIFIED**; known REST API + Croissant download button).

---

## 4. DOMAIN-SPECIFIC HUBS OUTSIDE LANGUAGE

*(This is where every LLM-centric competitor thins out — our核心 opportunity.)*

| Entity | URL | Operator | Coverage | Type | API/bulk | Licence | Freshness | Doesn't do |
|---|---|---|---|---|---|---|---|---|
| **Matbench Discovery** | matbench-discovery.materialsproject.org | **Janosh Riebesell** + MIT/EPFL/Samsung contributors | materials: crystal discovery, geometry opt., phonons, MD, diatomics; **43 eligible models**; CPS composite (F1 50% / RMSD 10% / κ 40%) | leaderboard w/ rich model metadata (training sets, params, checkpoints, org, refs, submission dates) | **YES — `/api`, `/data/sets`, GitHub, RSS** | © 2022 J. Riebesell, terms UNVERIFIED | **2026-09-13** | one domain; no cross-domain vocabulary |
| **Therapeutics Data Commons** | tdcommons.ai | Harvard (MIMS) | drug discovery: ADMET, DrugCombo, Docking, DTI DG, single-cell DTI, protein-peptide binding, counterfactual, clinical trial outcome | registry + leaderboards | **YES — Python lib, 3-line dataset retrieval** | not stated | latest papers 2022–23; **freshness UNVERIFIED, possibly stale** | biomedicine only |
| **WeatherBench 2** | sites.research.google/gr/weatherbench | Google Research | medium-range (1–15d) forecasting; ~25 models (IFS HRES/ENS, GraphCast, Pangu, FuXi, Aurora, NeuralGCM, GenCast, Stormer) | benchmark framework + scorecards | **YES — cloud-optimized ERA5 + baselines, GitHub, readthedocs** | UNVERIFIED | scorecards show 2022 data | weather only |
| **Open Catalyst (OC20/OC22/ODAC)** | opencatalystproject.org | Meta FAIR Chemistry (`fairchem`) | electrocatalysts, oxides, MOFs; S2EF/IS2RE tasks; OC22 ~500k DFT relaxations | leaderboard + eval server | eval server; leaderboard JSON | UNVERIFIED | active | chemistry only |
| **Grand Challenge** | grand-challenge.org | **DIAG Nijmegen** | **264 medical-imaging challenges**, 2025–2027 | competition platform | **YES — API docs + schema + dev portal** | © 2012-2026, licence UNVERIFIED | very active (2026 challenges open, deadlines into 2027) | medical imaging only; no cross-domain layer |
| **CASP / CAMEO** | predictioncenter.org, cameo3d.org | Prediction Center / SIB | protein structure; CAMEO = **weekly automated** 3D/ligand-binding/quality-estimation; CASP = biennial | competition / continuous eval | web | academic | **CASP17 target call open for 2026**; CASP16 (2024) showed plateau; 2026 priorities: non-homologous RNA/DNA, protein-nucleic acid complexes, conformational ensembles | structural bio only; invisible to all LLM catalogues |
| **GEO-Bench 2** | thealliance.ai | **AI Alliance** | geospatial FMs: classification, segmentation, detection, regression; full-finetune + frozen-encoder tracks | leaderboard | GitHub (`the-ai-alliance/geo-bench-vlm`) | UNVERIFIED | 2026 active | remote sensing only |
| **Waymo Open Dataset** | waymo.com/open | Waymo | AV: interaction prediction, sim agents, scenario generation, vision-based E2E driving | dataset + leaderboards | GitHub | Waymo licence (non-commercial research) | **no formal Challenges in 2026, but leaderboards remain open** | driving only |
| **Robotics** | — | fragmented | LIBERO (130 tasks / 4 suites), RoboCasa365 (365 tasks, 2500 kitchens, 600h human + 1600h synthetic demos), BEHAVIOR-1K, Open X-Embodiment (22 robot types, 527 skills), ManiSkill, SimplerEnv, RoboTwin 2.0, Meta-World, RLBench, Habitat, DuoBench | **NO CENTRAL HUB** | per-project | per-project | active research | **⭐ Genuinely unindexed — highest-value greenfield** |
| **Formal math** | — | fragmented | miniF2F (488 Lean 4 problems, SOTA 80.74% Kimina-Prover Preview), PutnamBench (**672 problems as of Jan 2026**, Lean 4 + Isabelle), CombiBench, FATE (open provers: ~50% FATE-M, 3% FATE-H, **0% FATE-X**), Construction-Verification | scattered leaderboards | GitHub | per-project | active | no unified index |
| **Dynabench** | dynabench.org | **MLCommons** (migrated from Facebook Research) | dynamic adversarial data collection; DADC, DataPerf, Flores, **BabyLM (5th community)** | platform | GitHub `mlcommons/dynabench` | **MIT** | **pushed 2026-02-11, only 29★, 14 open issues — low activity, not archived** | near-dormant |
| **Audio/other** | — | — | SUPERB, AV-SUPERB | — | — | — | **SUPERB 2026 leaderboard status UNVERIFIED** | — |

---

## 5. PRIOR ART — BENCHMARK CATALOGUE / REGISTRY ATTEMPTS ⭐ *(most important section)*

### Currently live and directly competitive

**① BenchmarkList** | benchmarklist.com | **David Tsong (@davidtsong) + Winston (@3vzro)** — small indie team, no org | **launched 2026-07-15** | **2,545 benchmarks, 1,604 providers, 24,074 models** | **catalogue + leaderboard + "Experimental Capability Index" (ECI) using a "Rosetta Stone method" aligning overlapping benchmark results onto a shared scale** | **NO API, NO bulk download, NO licence stated, not open source** | active daily |
- **Methodology (from /about, verbatim):** "finding public benchmark sources, then scraping or parsing leaderboards, model cards, system cards, launch posts, papers, GitHub repos, CSVs, APIs" → timestamped snapshots.
- **Facets:** 11 primary abilities + 40+ subcategories (Issue Resolution, Image + Spatial, Function Calling…).
- **Cross-domain: YES, real.** Verified entries include **Open Catalyst OC22** (78 models, 6 metrics, "Imported" from official leaderboard JSON) and **GEO-Bench 2**. Claims coverage of "coding agents, robotics, biology, healthcare, energy analytics."
- **Per-benchmark fields observed:** description, category (e.g. Materials), abilities (Reasoning+Knowledge), release date, model count, metric count, external links (website, leaderboard JSON, methodology), score provenance ("Imported"), last-update timestamp.
- **Missing per-benchmark:** paper/dataset DOI, **licence**, creator/organization attribution, task count, and **any evaluation-conditions modelling**.
- **⚠️ Data-quality signal:** its OC22 page lists "Release Date: **May 28, 2026**" — OC22 is a 2022 dataset. Likely an import date mislabelled as release date. Suggests automated ingestion without curation review. *(One observation only — treat as indicative, not proven.)*
- ***Doesn't do:*** no open licence, no export, no provenance to raw fields, no eval-conditions/comparability model, no coverage-gap analysis, no forkability. **It is a closed product; we are public infrastructure.**

**② Benchmark Radar** | benchmark-radar.org, github.com/ktwu01/benchmark-radar | **Koutian Wu + 7 co-authors** (Zhou, Shang, Wang, Han, Wang, Xu) | **arXiv 2609.11115, submitted 2026-09-10, rev. 09-13** | **14,810+ raw records; BUT the curated core is 1,283 source records from 4 benchmark catalogs, with 12,916 numeric observations across 790 records** | catalogue + search + daily feed + CLI + Pareto/saturation analysis | **37 sources: 13 connectors** (arXiv, GitHub search/orgs/releases, HF datasets/spaces/papers, Crossref, OpenAlex, OpenReview, Kaggle, Zenodo, Semantic Scholar, Brave, HN) **+ 24 first-party lab feeds** (OpenAI, Google/DeepMind, Meta, Microsoft, AWS, Apple, NVIDIA, HF, Ai2, Mistral, Together, Sakana, Qwen, Ollama, Stability, Nomic, Replicate, IBM, Databricks, LangChain, Meituan) + secondary from OpenCompass Hub, Artificial Analysis, LLM Stats | **Code MIT; content/data CC BY-NC-SA 4.0 ⚠️ NON-COMMERCIAL + SHARE-ALIKE** | **daily**, ~160★, 917 commits |
- Hosted on **GitHub Pages (static)**, ZIP dataset + HF dataset repo + RSS + `npx skills add` CLI. (`/radar.json` 404s — download path is elsewhere.)
- **LLM-centric.** README/abstract name LLM eval, agentic/tool-use, coding, reasoning, safety, "domain-specific evaluations" — **no robotics, protein, climate, materials**.
- ***Doesn't do:*** NC licence blocks commercial/institutional reuse and makes it un-citable-as-infrastructure; it is a **discovery firehose** (arXiv/GitHub/HF signals) rather than a curated cross-domain catalogue; no eval-conditions schema; no coverage-gap matrix.

**③ Every Eval Ever / EvalEval Coalition** | evalevalai.com, github.com/evaleval/every_eval_ever, HF `evaleval/EEE_datastore` | **Coalition hosted by HuggingFace + University of Edinburgh + EleutherAI**; 48 authors led by **Jan Batzner**, incl. **Stella Biderman, Arman Cohan, Leshem Choshen** | arXiv 2606.14516, **2026-06-12** | **22,235 models, 2,273 unique benchmarks, 31 evaluation formats** | **schema + community datastore of RESULTS** | PR-based contribution w/ adapters + `validate` CLI | **Data CC BY 4.0; code MIT** ⭐ | 659 commits, 117★, 49 forks |
- **Schema (`eval.schema.json`) top-level:** `source_metadata` (name, type, organization, evaluator relationship), `model_id`, `evaluation_name`, `generation_config.generation_args` (`temperature`, `top_p`, `max_tokens`, **`agentic_eval_config.available_tools[]`**, `eval_limits.message_limit/token_limit`, **`sandbox` type + Docker compose**), `evaluation_results[]` (`metric_config`: `lower_is_better`, `score_type`, `min_score`, `max_score`, uncertainty; `score_details`), `detailed_evaluation_results` (instance-level JSONL).
- **Scrapes:** Chatbot Arena, HF Open LLM Leaderboard v2, AlpacaEval, HELM (Classic/Capabilities/Instruct/Lite/MMLU), LiveCodeBench Pro, RewardBench, Global MMLU Lite.
- ***Doesn't do:*** **it models RESULTS, not BENCHMARKS.** No benchmark-entity catalogue with domain taxonomy, no non-language domains, no coverage-gap analysis, no "refuse to rank" UI. **This is our most important complement, not competitor.**

**④ Evaluation Cards** | arXiv 2606.09809, 2026-06-08 | **Avijit Ghosh, Anka Reuel, Jenny Chim + 45 others** (EvalEval) | monitoring across **5,816 models, 635 benchmarks, 101,843 results** | consolidates benchmark metadata + eval-run data + model info; **four interpretive signals: reproducibility, documentation completeness, provenance/risk, SCORE COMPARABILITY** | **CC-BY-SA 4.0** | schema derived from 52 papers + stakeholder interviews | *⚠️ "score comparability" directly overlaps our comparability_key. But it's a reporting/scoring overlay on results, not a cross-domain benchmark catalogue.*

**⑤ Epoch AI benchmark registry** — see §1. 80 benchmarks, CC-BY, best-quality data, narrowest scope.

**⑥ Evidently AI LLM benchmarks database** | evidentlyai.com/llm-evaluation-benchmarks-datasets | Evidently AI (commercial OSS eval tool) | **250 LLM benchmarks/datasets** | catalogue | no API/download | not stated, "belongs to respective parties" | **published 2024-12-10, LAST UPDATED 2025-07-31 — 14 months stale** | *Marketing content-asset for an eval product; LLM-only; abandoned.* **Notably used as a data source by the "Emergent evaluation hubs" paper — meaning stale data is propagating into research.**

**⑦ BetterBench** | betterbench.stanford.edu | Stanford (Anka Reuel et al.), NeurIPS 2024 Spotlight, arXiv 2411.12990 | **only 24 benchmarks** (16 foundation-model + 8 non-FM) assessed on **46 criteria across 4 lifecycle stages** (design, implementation, documentation, maintenance) | **quality-assessment registry** ("living repository") | no download observed | not stated | **no visible updates since 2024 — effectively stale** | *Quality scores, not discovery; 24 benchmarks. Finding: **17/24 benchmarks had no easy-to-run reproduction scripts**.* **Their 46-criterion rubric is the best available prior art for a quality/maturity field in our schema.**

**⑧ AISafetyBenchExplorer** | arXiv 2604.12875 | Abiodun A. Solanke | **195 AI safety benchmarks 2018–2026**; multi-sheet schema (benchmark-level metadata, metric-level definitions, benchmark-paper metadata, repository activity) + complexity taxonomy | **⚠️ SUBMITTED 2026-04-14, WITHDRAWN 2026-04-23** ("institutional affiliation compliance matter under review"); no PDF available | — | **Findings still valuable: 137/195 stale GitHub repos, 96/195 stale HF datasets, 165/195 English-only, only 7 "Popular" tier.** |

**⑨ OECD Catalogue of Tools & Metrics for Trustworthy AI** | oecd.ai/en/catalogue | OECD | governance tools + trustworthiness metrics (fairness, robustness, explainability) — **NOT capability benchmarks** | catalogue | web | **explicit disclaimer: "not vetted or endorsed by the OECD"; tools are "solely those of the originating authors"** | open submissions, deadline 2026-06-05 | *Governance/assurance tools, not capability evaluations. Adjacent, non-competing; a possible credibility partner.* (Separate: **OECD.AI Index**, Feb 2026, 28 national-capability indicators — unrelated.)

**⑩ Government/institutional** — **No centralized public benchmark registry exists at NIST/CAISI or UK AISI.** CAISI uses 16 benchmarks × 35 models internally (incl. non-public CTF-Archive-Diamond (285 CTF challenges), PortBench, FrontierScience) and published **NIST AI 800-2 ipd, "Practices for Automated Benchmark Evaluations of Language Models"** (Jan 2026). International Network for Advanced AI Measurement (founded Nov 2024, 10 countries) published consensus areas Feb 2026. UK announced a **Centre for AI Measurement at NPL (Jan 2026)**. **EU AI Act:** GPAI transparency duties + AI Office enforcement live **2026-08-02**; systemic-risk models (>10²⁵ FLOP) must evaluate "using standard benchmarks and state-of-the-art tests" — **but no registry defines which. That is a live, unfilled regulatory need.**

**⑪ Stanford HAI AI Index 2026** (7th ed.) — annual PDF report, not a queryable registry. Ch.2 Technical Performance. *Complementary; a citation target, not a competitor.*

**⑫ "Awesome" GitHub lists** — panilya/awesome-ai-benchmarks (100+), BenchGecko/awesome-llm-benchmarks (updated Mar 2026), tatn/awesome-ai-benchmarks, benchflow-ai/awesome-evals (443 links), leoncuhk/awesome-llm-bench (daily-syncs top-10 from benchlm.ai), brandonhimpfen/..., VyetGokyra/awaresome_LLM_eval_benchmark (a fork of Evidently's 250). *Unstructured markdown, no schema, no facets, high decay. Zero real competition but they own SEO.*

**⑬ MLCommons Croissant — ⭐ THE STANDARDS GAP** | github.com/mlcommons/croissant | MLCommons Datasets WG Task Force; co-chairs **Omar Benjelloun (Google), Elena Simperl (KCL), Joaquin Vanschoren (TU/e)** | schema.org-based JSON-LD for ML datasets: metadata + resources + structure + ML semantics; RAI extension | **Adopted by HuggingFace (auto JSON-LD per dataset), Kaggle (export), OpenML (download button), Google Dataset Search (crawls+indexes), TFDS (CroissantBuilder)** | **Spec CC BY-ND 4.0; implementation Apache 2.0** | 899★, 125 forks | **⚠️ NO BENCHMARK/EVALUATION EXTENSION EXISTS.** *Croissant describes datasets. A benchmark ≠ a dataset (it adds tasks, metrics, splits, protocols, conditions). **The `croissant-benchmark` extension is unclaimed, standards-blessed ground with a ready-made distribution channel into Google Dataset Search.***

---

## (a) TOP 8 HIGHEST-OVERLAP SERVICES + PRECISE BOUNDARY

**1. BenchmarkList** (benchmarklist.com) — *overlap ~75%, the single biggest threat.* Same ambition (largest cross-domain benchmark DB), 2 months' head start, already has OC22/GEO-Bench.
> **Boundary: be the OPEN, CITABLE, FORKABLE one.** They are closed: no licence, no API, no export, no repo, 2-person proprietary scrape. Draw the line at **provenance + licence + forkability**: every field in our YAML carries `source_url` + `retrieved_at` + `verified_by`; the whole index is CC-BY at a commit hash with a DOI. Never compete on raw count — compete on *"you can audit, cite, fork, and rebuild this; you cannot do any of those with BenchmarkList."* Also refuse their "Rosetta Stone" cross-benchmark alignment — that is exactly the single-number ranking we reject, and it is our sharpest philosophical contrast.

**2. Benchmark Radar** (benchmark-radar.org) — *overlap ~70%.* Open, static-hosted, daily, git-backed — architecturally almost identical to the plan.
> **Boundary: CURATION vs DISCOVERY, and CC-BY vs CC-BY-NC-SA.** They ingest 37 firehose sources into 14,810 raw records but curate only ~1,283/790. We should be explicitly the opposite: fewer entries, each hand-verified, each with structured eval conditions and domain taxonomy. And their **NC clause is their fatal flaw for institutional adoption** — a company, a regulator, or a commercial eval vendor cannot build on CC-BY-NC-SA. **Our CC-BY is the wedge.** Consider a `radar_id` cross-reference field for interop — but do not ingest their content (licence incompatible with CC-BY).

**3. Every Eval Ever / EvalEval Coalition** — *overlap ~45%, but mostly complementary and the best alliance target.*
> **Boundary: we own the BENCHMARK entity, they own the RESULT record.** Their schema has no benchmark-level catalogue: no domain taxonomy, no modality, no dataset licence, no maintenance status, no cross-domain vocabulary. Adopt their `eval.schema.json` field names for the conditions we share (`generation_args`, `agentic_eval_config.available_tools`, `sandbox`, `metric_config`) so a result validated against EEE can join to our benchmark record on a stable ID. **Explicitly propose ourselves as the benchmark-registry counterpart to their result-registry** — HF/EleutherAI/Edinburgh backing plus CC-BY 4.0 makes this a genuine partnership, not a collision. Highest-leverage single relationship in the landscape.

**4. Epoch AI Benchmarking Hub** — *overlap ~40% on data model, 0% on scope.*
> **Boundary: they go DEEP on 80 language/agent benchmarks with their own runs; we go BROAD across all domains with zero runs.** Never re-derive their numbers — **ingest them under CC-BY with attribution** (already downloaded locally). Explicitly cede "authoritative frontier-LLM capability trends + ECI" to Epoch and link out. Adopt and generalise their `superseded_by` column into a full lineage/version model. Position: *"Epoch tells you how good models are on 80 frontier benchmarks. We tell you which 5,000 benchmarks exist, in every field, and whether their numbers are comparable at all."*

**5. Papers with Code archive** — *overlap ~60% conceptually, 0% operationally (dead).*
> **Boundary: we are the living successor with a licence firewall.** Use the frozen dump as cold-start seed for benchmark names/tasks/datasets/paper links — but **CC-BY-SA-4.0 is viral**: keep PWC-derived text in a segregated `sources/pwc/` tree, flag every field `provenance: pwc-archive`, and either re-derive from primary sources before promoting to the CC-BY core or ship that subset dual-licensed. **Get this decision into the plan explicitly — it is the single largest legal risk in the whole ingestion strategy.**

**6. Artificial Analysis** — *overlap ~35%.* Commercially strongest, 30+ evals, multimodal, has a real API.
> **Boundary: they run and sell evals; we catalogue and never run.** Their data **cannot be redistributed** without a commercial contract — so link out, cite, never mirror. Complement them by cataloguing the ~95% of benchmarks they don't run, and by recording eval conditions for benchmarks where their methodology differs from the benchmark authors'.

**7. Inspect / inspect_evals (UK AISI)** — *overlap ~35% and rising fast since the May 2026 `/register/` launch.*
> **Boundary: they register RUNNABLE Inspect implementations; we register benchmarks regardless of whether code exists.** Their registry is implementation-gated and language-model-gated — a protein-structure challenge or a weather benchmark can never enter it. Add an `inspect_evals_id` field so a user can jump from our catalogue to a runnable eval; that makes us the front door to their harness rather than a rival. MIT licence makes ingestion trivial.

**8. HELM (Stanford CRFM)** — *overlap ~30%, declining.* Was the closest thing to a multi-domain holistic evaluation framework.
> **Boundary: maintenance mode since 2026-06-01 — take over the map, not the measurement.** HELM's scenario taxonomy across Capabilities/Safety/VHELM/HEIM/ToRR/MedHELM/AudioHELM is the best existing cross-modality vocabulary; adopt and extend it rather than inventing one. Cite HELM as taxonomy ancestry (good-faith credibility with CRFM). Track MedHELM's community spin-out (Apache 2.0, Pacific AI stewardship) as the model for how a domain vertical can outlive its parent.

*Just outside the top 8:* LMArena/Arena (CC-BY data, human-preference only), Vals AI ($40M a16z-funded, private evals), Scale Labs (deliberately unreproducible), Codabench/Grand Challenge (competition hosting, no metadata layer), OpenCompass CompassHub (China-ecosystem benchmark browser).

---

## (b) CLEAREST UNOCCUPIED GROUND

Ranked by defensibility × evidence strength:

**1. Non-language domains, at depth, on one map.** ✅ Strongest claim, and it survives contact with the new competitors. Epoch = 80 LLM/agent benchmarks. Benchmark Radar = LLM-centric by its own abstract. EEE = LLM leaderboard scrapes. BenchLM = knowledge/coding/math only. Evidently = LLM-only. HELM = language+vision+audio, now frozen. Only BenchmarkList has genuine non-LLM entries and they are **thin, unattributed, unlicensed, and show date-quality errors**. Meanwhile **CASP/CAMEO, Grand Challenge (264 challenges), Matbench Discovery, Open Catalyst, WeatherBench 2, GEO-Bench, and the entire robotics cluster (LIBERO/RoboCasa365/BEHAVIOR-1K/Open X-Embodiment/ManiSkill) appear in NO cross-domain catalogue at all.** **Robotics is the single largest unindexed field.**

**2. A Croissant extension for benchmarks.** MLCommons Croissant is the adopted ML-metadata standard (HF, Kaggle, OpenML, TFDS, Google Dataset Search) and **has no evaluation/benchmark extension**. Publishing `croissant-benchmark` — dataset + tasks + metrics + splits + protocol + conditions — converts us from "another website" into a **standard**, with Google Dataset Search as free distribution and MLCommons as an institutional home. Highest strategic leverage per unit of effort in this entire report.

**3. Benchmark lineage, versioning and supersession.** Live evidence of chaos: **OSWorld → OSWorld-Verified + OSWorld 2.0** (two live benchmarks, one name); **Terminal-Bench 2.0 and 2.1 leaderboards running concurrently with a 3rd generation at a different domain**; SWE-bench → Verified/Lite/Multimodal/Multilingual/Pro; FrontierMath tiers 1-3 v2 / tier-4 / tier-4-v2 / Erdős; HELM's 8 variants; miniF2F → MINIF2F-DAFNY. **Epoch needed a `superseded_by` column and BenchmarkList/Radar have nothing equivalent.** Nobody models identity, fork lineage, or "which version is this score from." This is a real, painful, currently-unsolved problem — and it's pure metadata, exactly our lane.

**4. Comparability as a refusal mechanism.** EEE and Evaluation Cards record conditions and score comparability *on results*. Nobody attaches a computed `comparability_key` to the **benchmark definition** and then **refuses to render a ranking** when keys differ. Every competitor's instinct is the opposite — BenchmarkList built a "Rosetta Stone" to force non-comparable scores onto one scale; Epoch built ECI; Artificial Analysis built the Intelligence Index. **A catalogue whose signature UI behaviour is declining to rank is genuinely unoccupied, and it's the most defensible trust position available.**

**5. Liveness / deprecation signalling.** AISafetyBenchExplorer measured **137/195 stale GitHub repos and 96/195 stale HF datasets** in safety alone; BetterBench found **17/24 benchmarks had no working reproduction scripts**; arXiv 2507.06434 argues benchmarks must be actively deprecated. Every catalogue lists benchmarks as if all are alive. **A `maintenance_status` field driven by observable repo/dataset/leaderboard signals — "this benchmark is dead" — exists nowhere.**

**6. Coverage/gap matrix as a living artifact.** Papers do this once and freeze (e.g. arXiv 2605.16282 found **zero benchmark coverage for evading human oversight, self-replication, and AI R&D capabilities**; behavioural benchmarks clustered in 34/40 sandboxed, 26/40 constrained-tool, 28/40 rule-based). **No live, queryable domain × capability coverage surface exists.** Directly serves the user's "analyze the ecosystem" priority.

**7. The regulatory vacuum.** EU AI Act GPAI obligations became enforceable **2026-08-02** and require evaluation "using standard benchmarks and state-of-the-art tests" — **with no registry defining what qualifies.** NIST AI 800-2 (ipd) and the 10-country International Network are writing practices, not catalogues. OECD's catalogue covers governance tools, explicitly disclaims vetting, and excludes capability benchmarks. **A neutral, sourced, CC-BY benchmark registry is the obvious missing reference artifact — and a credible route to institutional adoption and funding.**

**8. Permissive licensing.** Benchmark Radar = CC BY-NC-SA. PWC archive = CC BY-SA. Evaluation Cards = CC BY-SA. BenchmarkList/BenchLM/llm-stats/lmmarketcap = closed. Artificial Analysis = no redistribution. **Plain CC-BY is nearly unoccupied** (only Epoch, LMArena, OpenRouter, EEE) — and it's the only licence under which companies, regulators and commercial eval vendors can actually build. Cheap to claim, hard for incumbents to retrofit.

---

## (c) INGESTIBLE SOURCES — permissive licence + API/bulk data

**Tier 1 — ingest immediately, clean licences:**

| Source | What you get | Access | Licence | Notes |
|---|---|---|---|---|
| **Epoch AI** | 80 benchmarks, 390 models, `benchmark_metadata.csv` (incl. `superseded_by`, `random_baseline`, `score_ceiling`, `scale`), per-benchmark score CSVs w/ org, country, training FLOP, stderr, log links | CSV/ZIP + Python client | **CC-BY** | **already on disk at `epochdl/` — 85 files. Best-quality data in the landscape. Start here.** |
| **Every Eval Ever** | 2,273 benchmarks, 22,235 models, 31 formats, full eval-conditions schema | HF `evaleval/EEE_datastore` + GitHub | **Data CC BY 4.0 / code MIT** | Adopt their field names; also the key partnership |
| **inspect_evals** | 171 evals w/ bot-derived metadata, `/register/` entries, categories, sample counts | GitHub | **MIT** | Gives `inspect_evals_id` cross-ref + runnability flag |
| **Arena (LMArena)** | 2.36M rows of leaderboard snapshots across 13 arenas (text, vision, search, document, code, image/video gen, agent) | HF `lmarena-ai/leaderboard-dataset` | **CC-BY-4.0** | Updated 2026-09-15 |
| **OpenRouter** | usage/token share, cost-per-session, latency, tool-calling, context | Data API (JSON) | **CC BY 4.0** | Adoption signal nobody else pairs with benchmarks |
| **OpenAlex** | ~250M works: citations, venues, authors, institutions | API + monthly full AWS S3 snapshot | **CC0** | Zero licence risk; powers "who makes benchmarks / trends / org analysis" |
| **HuggingFace Hub** | dataset/model/Space metadata + **Croissant JSON-LD per dataset** (`/api/datasets/{name}/croissant`) | free public API, **no token** | per-artifact | Auto-populates dataset licence + size fields |
| **MLCommons Croissant** | the schema itself | GitHub | **spec CC BY-ND 4.0 / impl Apache 2.0** | ⚠️ **ND = no derivatives.** You may *extend* via a separate namespaced extension; you may **not** publish a modified spec. Get this right. |
| **Codabench** | 1,498 competitions | `/api/docs/` | verify | Competition-domain coverage |
| **Grand Challenge** | 264 medical-imaging challenges | API + schema | verify | Best single source of non-LLM medical benchmarks |
| **Matbench Discovery** | 43 models w/ rich metadata | `/api`, `/data/sets`, GitHub, RSS | verify | Materials domain |

**Tier 2 — high value, licence hazard (quarantine required):**

| Source | Value | Hazard |
|---|---|---|
| **Papers with Code archive** (`paperswithcode/paperswithcode-data`) | **9,327 benchmarks, 5,628 datasets, 79,817 paper↔code links, evaluation tables** — by far the largest cold-start corpus available | **CC-BY-SA-4.0 — viral.** Segregate, tag `provenance: pwc-archive`, re-derive from primary sources before promoting into the CC-BY core, or dual-license that subtree. **Decide before first ingest, not after.** |
| **Evaluation Cards** (arXiv 2606.09809) | comparability/reproducibility signal design over 635 benchmarks | **CC-BY-SA 4.0** — same problem. Reimplement the *ideas* from the paper; don't copy the data. |
| **BetterBench** 46-criterion rubric | best benchmark-quality rubric in existence | licence not stated — cite and reimplement, don't copy |

**Do NOT ingest:** Benchmark Radar (CC BY-NC-SA — incompatible with CC-BY), BenchmarkList (no licence, no API, ToS risk — scraping a competitor's proprietary DB is both legally and reputationally wrong for a trust-first project), Artificial Analysis (attribution OK, **redistribution contractually barred**), BenchLM.ai / llm-stats.com / lmmarketcap.com (closed/ARR), Scale Labs (private prompt sets), Semantic Scholar (S2 ToS — use OpenAlex instead).

---

## (d) PRIOR CROSS-DOMAIN CATALOGUE ATTEMPTS THAT FAILED OR WENT STALE ⭐

*The most valuable intelligence here. The pattern is brutal and consistent.*

**1. Stanford CRFM Ecosystem Graphs — the closest architectural precedent, and it is dead.**
`github.com/stanford-crfm/ecosystem-graphs` · **last push 2025-01-24 · NO LICENCE · 274★ · 0 open issues** (zero issues on a 20-month-dead repo = nobody is even asking). Structured asset catalogue (models/datasets/applications) maintained as files in git with a static site — **the exact architecture proposed here**, from a well-resourced Stanford lab. It still gets cited as a data source by 2025-26 research (e.g. the "Emergent evaluation hubs" paper, arXiv 2510.01286, used it as one of two proxies) **while being 20 months stale** — so stale curation is actively propagating errors into the literature.
> **Lesson: the architecture is not the risk; the curation treadmill is. And it had no licence, so nobody could fork it when the lab moved on.** Ship with CC-BY + an explicit succession/fork story from day one, and make ingestion automated enough that a 2-person team can survive attention loss.

**2. Papers with Code — the biggest, best-funded attempt, killed by its owner.**
Sunset **2025-07-24** under Meta AI Research (acquired Dec 2019). 9,327 benchmarks, 5,628 datasets, 79,817 paper↔code links, 1,000+ tasks, CC-BY-SA. Domain now redirects to `huggingface.co/papers/trending`; HF announced a Meta partnership the next day, but **Trending Papers is a paper feed, not a benchmark catalogue — the leaderboard/benchmark layer was simply not replaced.**
> **Lesson: corporate ownership is the failure mode.** It didn't die of staleness — it died because a single owner deprioritised it. This is the strongest possible argument for CC-BY-data-in-git with a DOI: had PWC been forkable infrastructure rather than a Meta property, the community would have continued it. **Make "what happens when we stop" an explicit, documented part of the plan.** It is also why the successor slot is currently open (CodeSOTA and HF Trending Papers are both partial).

**3. `JonathanChavezTamales/llm-leaderboard` — git-backed catalogue that abandoned git.**
356★, 40 forks, JSON-Schema-validated `data/` tree (models, providers, benchmarks, organizations, licenses) + `schemas/`. README now: *"This repository is now depracated and won't be getting any new updates."* Redirected to **llm-stats.com — a closed website with no repo and no licence.**
> **Lesson: the most instructive failure of all. A community JSON-in-git benchmark catalogue with real traction converted itself into a proprietary site.** The stated reason was contribution friction — PRs were too slow versus per-model/per-benchmark discussion threads on a website. **Design the contribution path for non-git contributors from day one** (issue-form → bot-validated → auto-PR, exactly as UK AISI's `/register/` does) or the same gravity will pull this project the same way.

**4. Stanford HELM — maintenance mode.**
*"HELM entered maintenance mode on June 1, 2026"* (verbatim, repo README). 8 leaderboard variants across text, vision, image-gen, tables, medicine, audio — the most genuinely multi-modal academic evaluation effort — now frozen. **MedHELM survived by spinning out** into an independent community project (Apache 2.0, technical stewardship by Pacific AI, 121 clinical tasks, new Q2-2026 leaderboard with 9 frontier models).
> **Lesson: academic evaluation infrastructure has a ~3-4 year half-life tied to grant cycles and student turnover. The vertical that found an industry steward lived; the parent didn't.** Plan for per-domain stewards rather than one central curator.

**5. HuggingFace Open LLM Leaderboard — retired at peak.**
v1 archived June 2024; **v2 retired 2025-03-14** after evaluating 13,000+ models. Stated reason: as capabilities shifted to reasoning/assistants, it *"was becoming obsolete and could encourage people to optimize in irrelevant directions."*
> **Lesson: the most-used leaderboard in open-source AI killed itself for being actively harmful to the field. Our refusal to build a universal ranking is validated by the biggest ranking operator's own exit rationale — quote this.**

**6. BIG-bench — archived 2026-04-17.** 200+ collaborative tasks, Google-led, now read-only. BIG-Bench Hard near-saturated. *Lesson: even 450-author mega-collaborations go read-only; benchmark saturation is a lifecycle stage our schema must represent.*

**7. Evidently AI's 250-benchmark database** — published 2024-12-10, **last updated 2025-07-31**. A commercial eval vendor's content-marketing asset, abandoned after ~7 months. *Lesson: catalogues built as lead-gen for an adjacent product are always deprioritised. Our catalogue must be the product.*

**8. BetterBench (Stanford)** — NeurIPS 2024 Spotlight, billed a *"living repository,"* still showing **24 benchmarks** with no visible updates. *Lesson: "living repository" claimed at paper-publication time is the single least reliable signal in this space — treat every competitor's freshness claim as UNVERIFIED until observed.*

**9. AISafetyBenchExplorer** — arXiv 2604.12875, submitted 2026-04-14, **withdrawn 2026-04-23** over an institutional-affiliation compliance matter. 195 safety benchmarks, no PDF, no public data. *Lesson: solo-authored catalogues carry institutional/governance fragility on top of curation fragility. Its finding that **137/195 repos were stale** is itself the best evidence for our `maintenance_status` field.*

**10. Princeton HAL (Holistic Agent Leaderboard)** — ICLR 2026 paper, 9 benchmarks, cost-controlled agent evaluation. **No longer accepting submissions; leaderboard updates paused**, pivoted to a reliability dashboard. *Lesson: even fresh, well-published, actively-funded evaluation infrastructure stops accepting submissions within a year of publication.*

**11. Aider leaderboards** — last updated 2025-11-20 (~10 months). **12. Dynabench** (MLCommons) — last push 2026-02-11, 29★, near-dormant despite institutional ownership.

### The pattern, stated plainly
> **Every cross-domain AI catalogue attempt to date has died within 12–24 months, and none died of insufficient ambition.** They died of (i) manual-curation load exceeding a small team, (ii) single-owner deprioritisation (PWC, HELM, Open LLM Leaderboard), (iii) contribution friction pushing maintainers to closed websites (llm-leaderboard → llm-stats), or (iv) no licence, making rescue-by-fork impossible (Ecosystem Graphs).
>
> **The three design decisions that follow directly:** (1) **CC-BY + DOI + forkable-at-commit from day one** — so failure is survivable rather than terminal, which is itself the differentiator against BenchmarkList and Benchmark Radar; (2) **bot-validated issue-form contribution** (copy UK AISI's `/register/`) so contributing never requires a PR; (3) **automate ingestion from the Tier-1 CC-BY/CC0 sources and hand-curate only the cross-domain taxonomy, eval conditions, and gap matrix** — because the curation treadmill, not the architecture, is what kills these projects, and hand-curation must be spent only where it is the actual differentiator.

---

## EXPLICIT UNCERTAINTIES / UNVERIFIED

- **EvalAI** (eval.ai) returned an empty page — **liveness, challenge count and licence all UNVERIFIED.** Manual check needed.
- **OpenML** and **livebench.ai** homepages returned title-only on fetch — current counts/licence **UNVERIFIED** (LiveBench details came from GitHub/search, not the site).
- **Therapeutics Data Commons** freshness **UNVERIFIED** — latest papers cited are 2022–23; may be stale.
- **WeatherBench 2** scorecards show 2022 data; current update cadence **UNVERIFIED**.
- **SUPERB** 2026 leaderboard status **UNVERIFIED** (only AV-SUPERB surfaced).
- **Licences UNVERIFIED** for: Codabench, Grand Challenge, Matbench Discovery, Open Catalyst, GEO-Bench, WeatherBench 2, SWE-bench, LiveBench, Aider, BetterBench.
- **Artificial Analysis free-tier rate limit conflicts** between two pages (100 req/24h vs 1,000/day) — confirm before depending on it.
- **BenchmarkList's OC22 "release date 2026-05-28"** anomaly is a **single observation**; suggestive of import-date/release-date conflation but not proven as a systemic quality problem.
- **Benchmark Radar record counts differ between its README (14,810+) and its arXiv abstract (1,283 source records / 790 scored)** — I report both; the discrepancy is real and is itself the basis of the "firehose vs curated" positioning, but the exact curated figure should be re-checked.
- Several cited arXiv IDs (2606.14516, 2606.09809, 2609.11115, 2604.12875, 2608.06202, 2605.16282) postdate my training cutoff; **all were verified live today via arxiv.org**, but I could not independently assess their peer-review standing.
- I did **not** find any evidence of a government-run benchmark registry at NIST/CAISI, UK AISI, or the EU AI Office. Absence of evidence after targeted searching — but not proof of absence.