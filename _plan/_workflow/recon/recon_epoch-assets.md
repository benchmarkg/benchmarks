Local reconnaissance complete. Findings below.

---

# EPOCH AI DATASET — LOCAL ASSET RECON

Location: `E:\AI\_Project\Project (intelligence-benchmark)\benchmarks\epochdl\`
88 files total: 80 per-benchmark CSVs + `benchmark_metadata.csv` + `model_metadata.csv` + `README.md` + `b.zip` + 4 files in `epoch_capabilities_index/`.

Note: the project's own planning docs have moved to `E:\AI\_Project\Project (intelligence-benchmark)\benchmarks\_plan\_archive\` (00-overview through 08-open-questions). I read `_archive/02-data-model.md` and `_archive/01-taxonomy.md` so that answer (a) is field-exact against the real schema.

---

## 1. LICENSING AND CITATION (verbatim from `epochdl/README.md`)

The file is 582 bytes, complete text:

```
## Licensing
Epoch AI's data is free to use, distribute, and reproduce provided the source and authors are credited under the [Creative Commons Attribution license](https://creativecommons.org/licenses/by/4.0/).

### Citation
```
Epoch AI, 'Capabilities & Benchmarking'. Published online at epoch.ai. Retrieved from 'https://epoch.ai/benchmarks' [online resource].
```

### BibTeX Citation
```
@misc{EpochLLMBenchmarkingHub2024,
  title = {{Capabilities & Benchmarking}},
  author = {{Epoch AI}},
  year = {2026},
  month = {09},
  url = {https://epoch.ai/benchmarks}
}
```
```

Practical read: CC-BY-4.0, attribution to "Epoch AI", canonical URL `https://epoch.ai/benchmarks`. No share-alike, no non-commercial clause — **redistribution inside our repo is permitted**, including modified/derived form, provided credit is given. The BibTeX key says `2024` but `year = {2026}, month = {09}`; the download is dated 2026-09-16. Note there is **no explicit per-file or per-row provenance statement** in the README, and no version/DOI for the snapshot — we must record our own retrieval date and file hashes because the upstream has no immutable citation handle. UNVERIFIED: whether Epoch publishes a DOI or dated snapshot elsewhere (not determinable from local files).

---

## 2. `benchmark_metadata.csv` — COMPLETE

**81 data rows** (82 lines incl. header). 9 columns:

`benchmark, in_eci, source_file, score_column, scale, random_baseline, score_ceiling, release_date, superseded_by`

Example rows:

```
GPQA diamond,True,gpqa_diamond.csv,Best score (across scorers),1.0,0.25,1.0,2023-11-20,
FrontierMath-2025-02-28-Private,True,frontiermath.csv,Best score (across scorers),1.0,0.0,0.57,2025-02-28,FrontierMath-Tiers-1-3-v2-Private
SWE-Bench verified,True,swe_bench_verified.csv,Best score (across scorers),1.0,0.0,1.0,2024-08-13,
Aider polyglot,True,aider_polyglot_external.csv,Percent correct,0.01,0.0,1.0,2024-12-21,
Lech Mazur Writing,True,lech_mazur_writing_external.csv,Mean score,0.1,0.0,1.0,2025-01-31,
CursorBench,False,,,1.0,0.0,1.0,2026-03-11,
```

Facts:
- `in_eci` True = 59, False = 22.
- `source_file` is populated **only for the 59 ECI benchmarks**. 21 CSVs on disk are not referenced by any metadata row (`ale_bench`, `algotune`, `blueprint_bench_2`, `bool_q`, `btf3`, `common_sense_qa_2`, `critpt`, `cursorbench`, `enigma_eval`, `forecastbench`, `frontiermath_erdos`, `frontierswe`, `gbaeval`, `gdp_pdf`, `live_bench`, `mindcube`, `scicode`, `spatialviz_bench`, `vending_bench_2`, `video_mme`, `webdev_arena`). Reverse: one metadata row (`METR`, release 2025-03-18) has **no CSV on disk** — distinct from `METR Time Horizons` which does.
- `scale` ∈ {`1.0`, `0.01`, `0.1`} — a multiplier to normalise the raw score column to 0–1. `0.01` for percent-scale benchmarks (Aider polyglot, OSWorld, LMCA); `0.1` for Lech Mazur Writing (0–10 scale).
- `random_baseline` non-zero on 21 benchmarks (e.g. GPQA diamond 0.25, PIQA 0.5, Winogrande 0.5, HLE 0.048, Chess Puzzles 0.0496, Mystery Game Puzzles 0.0922, SimpleBench 0.1667, DTBench 0.4).
- `score_ceiling` < 1.0 on only 3: FrontierMath-2025-02-28-Private 0.57, FrontierMath-Tier-4-2025-07-01-Private 0.6, LMCA 0.85.
- `superseded_by` filled on only 2 rows (both FrontierMath lineage).
- `release_date` missing on exactly one benchmark: BTF-3.

**This file is directly the seed for our `Benchmark` + `Metric` + lineage fields.** See (a).

---

## 3. `model_metadata.csv` — COMPLETE

**1,063 data rows** (1,064 lines). 8 columns:

`model_version, model_group, date, display_name, organization, country, accessibility, training_compute_flop`

Fill rates (of 1,063):

| column | filled | % |
|---|---|---|
| model_version | 1,049 | 98% |
| model_group | 1,052 | 98% |
| date | 1,037 | 97% |
| display_name | 493 | **46%** |
| organization | 936 | 88% |
| country | 935 | 87% |
| accessibility | 912 | 85% |
| training_compute_flop | 337 | **31%** |

11 rows are entirely blank; several more are partial stubs (e.g. `,,Gemini 2.0 Flash Thinking (Jan 2025),2025-01-21,,,,` — model_group + date only). The file is **not clean**; an adapter must tolerate holes.

Example rows:

```
accounts/fireworks/models/glm-4p6,GLM-4.6,2025-09-30,GLM-4.6 (Fireworks),"Z.ai (Zhipu AI),Tsinghua University",China,Open weights (unrestricted),4.42e+24
accounts/fireworks/models/kimi-k2-thinking,Kimi K2 Thinking,2025-11-06,Kimi K2 Thinking (Fireworks),Moonshot,China,Open weights (restricted use),4.2e+24
chutes/DeepSeek-R1-0528,DeepSeek-R1 (May 2025),2025-05-28,DeepSeek-R1 (May 2025),DeepSeek,China,Open weights (unrestricted),4.020010000000001e+24
zai-org/glm-5,GLM-5,2026-02-11,GLM-5 (Novita),Z.ai (Zhipu AI),China,Open weights (unrestricted),6.84e+24
accounts/fireworks/models/qwen3-235b-a22b-thinking-2507,Qwen3-235B-A22B-Thinking (Jul 2025),2025-07-25,Qwen3-235B-A22B-Thinking-2507,Alibaba,China,Open weights (unrestricted),4.752e+24
```

Controlled vocabularies:
- `accessibility` (7 values): `API access` 491 · `Open weights (unrestricted)` 249 · *(blank)* 151 · `Open weights (restricted use)` 120 · `Open weights (non-commercial)` 28 · `Unreleased` 13 · `Hosted access (no API)` 11.
- `country`: `United States of America` 611 · `China` 254 · *(blank)* 128 · `France` 51 · `United Arab Emirates` 5 · `Canada` 3 · `United Kingdom` 3 · plus comma-joined multi-country values (`France,United States of America`, `Hong Kong,China`).
- `organization`: 70 distinct, comma-joined for joint work (`Z.ai (Zhipu AI),Tsinghua University`, `DeepSeek,Peking University`, `Google DeepMind,Google`). Top: OpenAI 210, Anthropic 144, Alibaba 106, Google DeepMind 91, DeepSeek 57, Mistral AI 51, Meta AI 44, xAI 35.
- `model_group`: **550 distinct** — this is Epoch's System-level identity; `model_version` (1,048 distinct keys) is the SystemVersion/deployment-endpoint level. One `model_group` maps to many `model_version` rows (provider routing: `(Fireworks)`, `(Novita)`, `(Together)` in `display_name`).

---

## 4. `epoch_capabilities_index/`

### `eci_scores.csv` — 266 rows, 11 cols
`Model, Display name, eci, eci_ci_low, eci_ci_high, date, Organization, Country (of organization), Model accessibility, Accessibility group, model_versions`

```
GPT-6 Astra,GPT-6 Astra,166.31,163.0,171.88,2026-09-03,OpenAI,United States of America,API access,Closed weights,
Claude Fable 5.1,Claude Fable 5.1,164.47,161.36,168.28,2026-09-01,Anthropic,United States of America,API access,Closed weights,
Claude Fable 5,Claude Fable 5,163.27,160.54,167.1,2026-06-09,Anthropic,United States of America,API access,Closed weights,
```
`model_versions` is **empty in all 266 rows** — the join back to `model_version` is broken in this export. `Accessibility group` is a 2-value rollup (`Closed weights` / open).

### `edi_scores.csv` — 58 rows, 5 cols
`benchmark_name, is_anchor, benchmark_release_date, edi, estimated_slope_scaled`
```
TriviaQA,False,2017-05-09,57.32175017525712,0.02084559575483598
LAMBADA,False,2016-06-20,58.22406541809232,0.0209547124967683
PIQA,False,2019-11-26,86.22048708869679,0.02206550895865236
```
EDI = "Epoch Difficulty Index", benchmark difficulty on the same latent scale as ECI. Range 57.32 (TriviaQA) → 183.28. Exactly **one anchor benchmark: Winogrande**.

### `processed_data_for_eci.csv` — 2,760 rows, 10 cols
`model_id, benchmark_id, performance, benchmark, benchmark_release_date, model, model_version, Model, date, source`
```
m1,b1,0.605,Lech Mazur Writing,2025-01-31,Amazon Nova Pro,amazon.nova-pro-v1:0,Amazon Nova Pro,2024-12-03,lechmazur/writing Github repository
m1,b2,0.7599999999999999,MMLU,2020-09-07,Amazon Nova Pro,amazon.nova-pro-v1:0,Amazon Nova Pro,2024-12-03,Stanford CRFM Leaderboard
m1,b3,0.017,The Agent Company,2024-12-18,Amazon Nova Pro,amazon.nova-pro-v1:0,Amazon Nova Pro,2024-12-03,TheAgentCompany experiment results github
```
58 benchmarks × 266 models, 567 distinct `model_version`. **This is the single most ingestion-friendly file in the whole bundle**: one row = one normalised (model, benchmark, score) with a `source` string. 74 distinct `source` values, but **1,204 of 2,760 rows (43.6%) have a blank source** — those are Epoch's own in-house runs.

### `eci_bootstraps.json` — 3.81 MB
Top-level keys: `num_samples` (500), `eci_scaled` (true), `ci_level` (0.9), `anchors`, `scaling`, `model`, `benchmark`.
- `anchors`: `{model_low: "Claude 3.5 Sonnet", eci_low: 130.0, model_high: "GPT-5", eci_high: 150.0}`
- `scaling`: `per_sample_a`, `per_sample_b` (500 each) — the affine map from latent ability to the 130/150 anchored scale.
- `model`: `ids`, `names` (266), `capability_samples` = 500 × 266 matrix.
- `benchmark`: `ids`, `names` (58), `difficulty_samples` = 500 × 58, `slope_samples` = 500 × 58.

**What ECI is**: a 2-parameter IRT / Rasch-style latent-ability model. Each benchmark has a *difficulty* and a *discrimination slope*; each model has a latent *capability*; observed pass rates are fit jointly across the 58-benchmark × 266-model sparse matrix. The latent scale is affinely anchored so Claude 3.5 Sonnet = 130 and GPT-5 = 150 (IQ-like scaling). 500 bootstrap resamples give the 90% CIs in `eci_ci_low/high`. EDI is the benchmark-difficulty parameter on the same scale.

**Direct relevance to us: ECI is precisely the "single-number universal AI score" our project has a hard constraint against.** We can cite it as an ecosystem artefact and link to it; we must not adopt it as a ranking. Its existence is also a useful differentiator argument — Epoch built the composite; we build the comparability guardrail.

---

## 5. PER-BENCHMARK CSVs — SCHEMA

**80 files, 6,598 total data rows**, mean 82.5 rows/file. Largest: `gpqa_diamond.csv` 313, `otis_mock_aime_2024_2025.csv` 290, `mmlu_external.csv` 249, `arc_agi_external.csv` 247, `gsm8k_external.csv` 235, `arc_agi_2_external.csv` 227, `chess_puzzles.csv` 222, `bool_q_external.csv` 206. Smallest: `frontiermath_erdos.csv` 5, `mindcube_external.csv` 5, `mirrorcode.csv` 8, `spatialviz_bench_external.csv` 8, `frontierswe_external.csv` 9.

### The common schema — 6 universal columns, present in all 80 files

```
Model version | Release date | Organization | Country | Training compute (FLOP) | Training compute notes
```
Fill: Model version 93%, Release date 92%, Organization 89%, Country 89%, Training compute (FLOP) **32%**, Training compute notes 44%.

Near-universal: `id` (62 files, 100% filled within them), `Name` (51 files, 96%), `Notes` (58 files, **only 5% filled**), `Source` (52 files, 95%), `Source link` (32 files, 87%).

### Two distinct file families

**(A) Epoch-run, 14 files, 1,550 rows** — identified by the presence of `Logs` / `Log viewer`. Fixed 13-column schema:
```
Model version | mean_score | Best score (across scorers) | Release date | Organization | Country |
Training compute (FLOP) | Training compute notes | stderr | Log viewer | Logs | Started at | id
```
Files: `chess_puzzles`, `ebr_bench`, `frontiermath`, `frontiermath_erdos`, `frontiermath_tier_4`, `frontiermath_tier_4_v2`, `frontiermath_tiers_1_3_v2`, `gpqa_diamond`, `math_level_5`, `mirrorcode`, `mystery_game_puzzles`, `otis_mock_aime_2024_2025`, `simpleqa_verified`, `swe_bench_verified`.

These carry **stderr on 99% of rows**, a run `id` (e.g. `4AfhcmYVNrw6gM5u8CQsyy`), an ISO `Started at` timestamp, and an Inspect-AI `.eval` log URL. Log accessibility: **828 public** (`epoch-benchmarks-{production,staging}-public.s3.us-east-2.amazonaws.com`), **459 private** (`...-private...`, incl. all FrontierMath), **263 blank**. These 828 are the closest thing in the whole corpus to `sandboxed-rerun`-grade evidence.

Example (`swe_bench_verified.csv`):
```
Model version = glm-5.2_max | mean_score = 0.787 | Best score (across scorers) = 0.787
Release date = 2026-06-16 | Organization = Z.ai (Zhipu AI) | Country = China
stderr = 0.018656911901656907
Log viewer = https://logs.epoch.ai/inspect-viewer/36231d6d/viewer.html?log_file=...4AfhcmYVNrw6gM5u8CQsyy.eval
Logs = https://epoch-benchmarks-staging-public.s3.us-east-2.amazonaws.com/inspect_ai_logs/4AfhcmYVNrw6gM5u8CQsyy.eval
Started at = 2026-06-25T13:13:06.902Z | id = 4AfhcmYVNrw6gM5u8CQsyy
```

**(B) External/scraped, 66 files, 5,048 rows** — 62 distinct header signatures across 80 files, i.e. **the per-benchmark tail is almost entirely bespoke**. The 6 universal columns plus a benchmark-specific score column named after the leaderboard's own label, plus arbitrary extras.

Score-column names are all different — this is the divergence point. `benchmark_metadata.score_column` is the pointer (only for the 59 ECI benchmarks); the other 21 files require manual mapping.

### Divergence examples (12+ sampled)

| file | rows | cols | score col | notable extras |
|---|---|---|---|---|
| `swe_bench_verified.csv` | 35 | 13 | `mean_score` / `Best score (across scorers)` | stderr, Logs, Started at |
| `frontiermath.csv` | 101 | 13 | same | logs all **private** S3 |
| `gpqa_diamond.csv` | 313 | 13 | same | 179/313 model_versions carry no effort suffix |
| `hle_external.csv` | 51 | 12 | `Accuracy` | `Accuracy Standard Error`, **`Calibration Error`** |
| `arc_agi_2_external.csv` | 227 | 11 | `Score` | `Cost per task`; conditions only in free-text `Name` |
| `os_world_external.csv` | 58 | 13 | `Score` (percent, scale 0.01) | **`Agent`** (`claude-sonnet-4-6 (100 steps)`), `Trajectories`, `Date added`; row 1 has no Model version at all |
| `vending_bench_2_external.csv` | 60 | 9 | `Score` (**dollars**, 11181.87 — not 0–1) | nothing else; leanest file |
| `metr_time_horizons_external.csv` | 50 | 16 | `Time horizon` (minutes) + `average_score` | `CI_high`, `CI_low`, `Time Horizon (80%)`, **`METR version`** (`METR-Horizon-v1.1`) |
| `video_mme_external.csv` | 50 | 20 | `Overall (no subtitles)` | 12 sub-scores (short/medium/long × ±subtitles), **`Frames`** |
| `weirdml_external.csv` | 171 | 14 | `Accuracy` | `Cost per run`, `Median code length (lines)`, `Accuracy SE` |
| `lech_mazur_writing_external.csv` | 49 | 11 | `Mean score` (0–10) | `ID` instead of `id`; Notes pin a **git commit** `80b7f17` |
| `chess_puzzles.csv` | 222 | 13 | `mean_score` | Epoch-run family |
| `terminalbench_external.csv` | 204 | 18 | `Accuracy mean` | **`Agent`, `Agent Org`, `Model Org`**, `Run date`, `Created` — the only file that cleanly separates scaffold-org from model-org |
| `mmlu_external.csv` | 249 | 13 | `EM` | **`Shots`** |
| `balrog_external.csv` | 36 | **26** | `Average progress` | 6 sub-environments × (progress + SE) |
| `geobench_external.csv` | 32 | **36** | `ACW Country %` | 5 photo-splits × 5 metrics, **`Tools`**, `Refusal` rates |
| `forecastbench_external.csv` | 81 | 26 | `Overall score` | `Better than superforecaster median?`, `Superforecaster p-value` — **contains a human baseline comparison** |
| `exploitbench_external.csv` | 20 | 20 | `Mean capability` | `T1..T5 reach`, `Autonudge`, `Harness`, `Envs`, `Episodes`, `Spend` |
| `deepswe_external.csv` | 69 | 18 | `Pass@1` | `Pass@4`, **`Harness`**, **`Reasoning effort`**, `Runs`, `Mean agent steps`, `95% CI half-width` |
| `osworld_2_external.csv` | 16 | 16 | `Binary accuracy` | **`Tool setting`**, **`Step budget`**, `Reasoning` |
| `cursorbench_external.csv` | 74 | 15 | `Score` | **`Reasoning level`**, `Tokens per task`, `Steps per task` |
| `gso_external.csv` | 38 | 16 | `Score OPT@1` | **`Scaffold`**, `OPT@1 (hack-adjusted)` — reward-hacking correction |
| `spatialviz_bench_external.csv` | 8 | 15 | `Overall score` | **`Prompting`** |
| `btf3_external.csv` | 10 | 15 | `Pooled score` | `Binary Brier`, `Numeric RPS`, **`Harness`** |
| `gbaeval_external.csv` | 23 | 25 | `Overall score` | **`Candidate SHA-256`**, `Wall-clock hours`, `Has WASM`, `Build failed` |
| `aider_polyglot_external.csv` | 77 | 16 | `Percent correct` | **`Edit format`**, `Time per case (seconds)`, `Date of evaluation` |

---

## 6. BENCHMARK LIST AND DOMAIN CLASSIFICATION

All 81 `benchmark_metadata` entries, mapped onto the `_plan` taxonomy families. Entries marked **[UNVERIFIED]** are ones I could not identify from the local data beyond column names — classification is inferred from sub-score column names only and must not be written into the repo without a source check.

**mathematics (9)** — FrontierMath-2025-02-28-Private, FrontierMath-Tier-4-2025-07-01-Private, FrontierMath-Tiers-1-3-v2-Private, FrontierMath-Tier-4-v2-Private, FrontierMath-Erdos (all `research-level-math`); MATH level 5, OTIS Mock AIME 2024-2025 (`competition-math`); GSM8K (`arithmetic`); ProofBench (`formal-theorem-proving`, Lean, vals.ai, notes mention `sorry/admit` rejection)

**code (13)** — SWE-Bench verified, DeepSWE, FrontierSWE, CursorBench (`repository-scale-se`); Aider polyglot, SciCode, AlgoTune, MirrorCode [UNVERIFIED], FrontierCode (`function-synthesis`); ALE-Bench (`competitive-programming`, AtCoder-style); GSO-Bench (code performance optimization); WeirdML, PostTrainBench [UNVERIFIED] (`ml-engineering`); WebDev Arena (`function-synthesis` + human-preference Elo)

**language (9)** — MMLU, TriviaQA, BoolQ, SuperGLUE, ANLI, LAMBADA, Winogrande (`understanding`/`retrieval-qa`); Fiction.LiveBench (`long-context`, 11 context-length sub-scores 0→192k); Lech Mazur Writing (`generation`, LLM-judged 0–10); SimpleQA Verified (`retrieval-qa`, secondary `safety-alignment/honesty-truthfulness`)

**reasoning-general (9)** — GPQA diamond, BBH, HellaSwag (`commonsense`), PIQA (`commonsense`), OpenBookQA, CSQA2, SimpleBench, EnigmaEval (`puzzle-solving`), LMCA [UNVERIFIED — `conceptualreasoning.ai/lmca`], DTBench [UNVERIFIED — `conceptualreasoning.ai/dtbench`, has `EDT answer preference` + `CRI-rescaled score`, reads as decision-theory]

**agents-tooluse (10)** — OSWorld, OSWorld 2.0 (`computer-use-gui`); Terminal Bench (`operating-system-tasks`); The Agent Company, Vending-Bench 2, METR Time Horizons, METR (`long-horizon-autonomy`); DeepResearch Bench (`research-agents`); Cybench (`cybersecurity-offense-defense`); APEX-Agents [UNVERIFIED]

**safety-alignment (1, +2 secondary)** — ExploitBench (`dangerous-capability-evals`; secondary: Cybench, and HLE's calibration-error column)

**games-planning (4)** — Chess Puzzles (`board-games`), Mystery Game Puzzles (`puzzle-solving`), Balrog (`open-ended-environments`: BabyAI/Crafter/TextWorld/BabaIsAI/MiniHack/NetHack), GBAEval (`video-games`, Game Boy Advance, `Replay/Procedural/Audio` sub-scores)

**general-intelligence (4)** — ARC-AGI, ARC-AGI-2 (`abstraction-generalization`); HLE (`human-comparison-batteries`); LiveBench (`agi-composite-suites`: Reasoning/Coding/Math/Data-analysis/Language/IF averages)

**multimodal / vision (7)** — VideoMME (`video-language`), ScienceQA (`visual-qa`), MindCube (`spatial-reasoning`: Rotation/Among/Around), SpatialViz-Bench (`spatial-reasoning`: Mental Rotation/Folding/Visual Penetration/Mental Animation), VPCT (visual-physics), Blueprint-Bench 2 (`3d-reconstruction`, Andon Labs), GeoBench (`vision` + `earth-climate/geospatial-reasoning`, 5 photo splits)

**society-econ-law (5)** — GDPval (occupational win-rate vs human experts), Remote Labor Index, ForecastBench (`forecasting-prediction-markets`, with superforecaster p-values), BTF-3 (`forecasting`, FutureSearch, Brier + RPS), GDP.pdf [UNVERIFIED — Surge AI]

**physics (2)** — CritPt [UNVERIFIED expansion; research-physics reasoning], Surface Evolver Bench (surface-energy-minimisation simulation)

**other / engineering (1)** — CadEval (OpenSCAD generation; `Chamfer`/`Hausdorff` geometric-tolerance pass rates — spans code + vision/3d)

**unclassifiable from local data (3)** — EBR-bench [UNVERIFIED, Epoch-run, generic schema], CL-bench [UNVERIFIED; sub-scores: Domain-knowledge reasoning, Rule-system application, Procedural task execution, Empirical discovery & simulation], CL-bench Life [UNVERIFIED; sub-scores: Communication & social interactions, Fragmented information & revisions, Behavioral records & activity trails]

### LLM-centric count

**81 of 81 (100%) are LLM-centric.** Every evaluated system is a language model, a VLM, or an LLM-driven agent scaffold. Confirmation: all 62 organizations appearing in result rows are LLM labs (OpenAI 1,577 rows, Anthropic 998, Google DeepMind 622, Meta AI 521, Alibaba 479, DeepSeek 243, xAI 213, Mistral 181, Moonshot 152, Z.ai 132, TII 103, Microsoft 61).

Roughly **10 of 81 accept non-text input** (VideoMME, ScienceQA, GeoBench, MindCube, SpatialViz-Bench, VPCT, Blueprint-Bench 2, GBAEval, CadEval-output, HLE-partial) — but these are VLMs, not non-LLM systems.

**Zero coverage** of: robotics/embodiment, chemistry, biology-genetics (protein structure/design), medicine-health, earth-climate (except GeoBench photo-geolocation), audio-speech, materials science, weather, autonomous driving. **This is exactly our differentiator #1, and this dataset confirms the gap empirically rather than by assertion.** Epoch's 81 benchmarks sit inside roughly 8 of our 18 domain families and cover 0% of the natural-science and embodiment half of the map.

---

## 7. `b.zip`

2,292,857 bytes compressed, **6,361,800 bytes uncompressed, 87 entries**, all timestamped 2026-09-16 23:14. Listed read-only via Python `zipfile.namelist()` — nothing extracted.

**It is the original Epoch download bundle, and its contents are byte-for-byte the files already extracted alongside it**: `README.md`, the 80 per-benchmark CSVs, `benchmark_metadata.csv`, `model_metadata.csv`, and `epoch_capabilities_index/{eci_scores.csv, edi_scores.csv, processed_data_for_eci.csv, eci_bootstraps.json}` (87 = 83 root + 4 nested). No extra files, no hidden manifest, no license file beyond README.md. It is redundant with the extracted tree — **but keep it**: it is the only immutable, hashable artefact of the snapshot, and it is what a `Source.archive_url` equivalent should point at for the ingest provenance record. Recommend `sha256` it and record the hash in the ingest manifest. Add `epochdl/b.zip` to `.gitignore` or store via Git LFS (current `.gitignore` is 10 bytes — contents not inspected in detail, but it is nearly empty).

---

# ANALYSIS

## (a) Fields populatable DIRECTLY, entity by entity

### `Benchmark` (from `benchmark_metadata.csv` + file inspection)
| our field | source | notes |
|---|---|---|
| `id` | slugify(`benchmark`) | needs manual review; Epoch names like `FrontierMath-Tier-4-v2-Private` conflate benchmark+version |
| `name` | `benchmark` | direct |
| `aliases[]` | filename stem (`swe_bench_verified`) + Epoch name | free alias pair |
| `homepage` | modal `Source link` in the per-benchmark CSV | available for 32/80 files; e.g. `https://os-world.github.io/`, `https://arcprize.org/leaderboard`, `https://www.tbench.ai/leaderboard/terminal-bench/2.0`, `https://balrogai.com/` |
| `lineage.superseded_by` | `superseded_by` | only 2 rows populated |
| `leaderboards[]` (ref) | `Source` + `Source link` | 52 files name a leaderboard |
| `data.modalities` | inferable for ~10 | not a column; manual |

**Not present at all:** `tagline`, `description`, `domain.*`, `capability[]`, `evaluation_method[]`, `designed_for_subjects[]`, `lifecycle`, `data.access`, `data.refresh`, `data_provenance`, `contamination_risk`, `contamination_evidence`, `human_baseline_type`, `languages`, `programming_languages`, `size.items`, `size.unit`, all of `governance.*`, all of `execution.*`, `repository`, `license`, `license_notes`, `tags`, all of `curation.*`. **That is ~30 of ~45 Benchmark fields we must author ourselves.**

### `BenchmarkVersion`
| field | source |
|---|---|
| `released` | `benchmark_metadata.release_date` (80/81; BTF-3 missing) |
| `version`/`label` | partially encoded in the name (`FrontierMath-Tier-4-v2-Private`, `OSWorld 2.0`, `SWE-Bench verified`), and in row-level columns `METR version` = `METR-Horizon-v1.1`, `LiveBench Version`, ProofBench Notes `v1.1 re-grade (vals.ai, 2026-08-14)`, Lech Mazur `commit 80b7f17` |
| `supersedes_version` | `superseded_by` inverted (2 rows) |
| **`breaking`** | **absent — and this is our load-bearing field.** Epoch encodes breaking changes by creating a whole new benchmark row (FrontierMath v1 → Tiers-1-3-v2), which loses the relation |
| `items`, `changes`, `sources` | absent |

### `System` / SystemVersion (from `model_metadata.csv`)
| our field | Epoch column | coverage |
|---|---|---|
| `name` | `model_group` (550 distinct) or `display_name` | 98% / 46% |
| `api_identifier` | `model_version` | 98%, 1,048 distinct |
| `first_released` / version `released` | `date` | 97% |
| `organization` | `organization` → Org ref | 88% |
| `open_weights` | derive from `accessibility` (`Open weights (*)` → true; `API access`/`Hosted access (no API)` → false; `Unreleased` → null) | 85% |
| `license` | partially: `Open weights (unrestricted / restricted use / non-commercial)` gives a licence *class*, not an SPDX id | 85% |
| `versions[]` | `model_version` rows grouped by `model_group` | direct |
| **extra Epoch field with no home in our schema** | `training_compute_flop` (31%) + `Training compute notes` (44%) | worth adding `training_compute_flop` + `training_compute_estimated: bool` + `training_compute_notes` to `System`. The notes are explicit about estimation method: `"6 FLOP / parameter / token * 22*10^9 active parameters * 36000000000000 tokens = 4.752e+24 FLOP"` and `"Training compute imputed to be 1.58e25 FLOP from benchmark scores"` — the latter is **circular for our purposes** (compute inferred *from* benchmark scores) and must be flagged, never used as an independent covariate |

**Absent:** `system_type`, `modalities_in/out`, `parameters_disclosed`, `parameter_count`, `training_compute_disclosed` (implied by blank, but blank≠not-disclosed — 11 rows are entirely blank stubs), `built_on` for scaffolds, `sources`.

### `Organization`
`name` and `country` derivable for 70 distinct orgs. **Absent:** `id`, `type`, `homepage`, `parent_org`, `aliases`. Comma-joined multi-org values (`Z.ai (Zhipu AI),Tsinghua University`) must be split into refs. Note `Google DeepMind` vs `Google` appear as separate orgs plus a joint `Google DeepMind,Google` — a parent_org relation we'd have to author.

### `ResultClaim`
| our field | source | coverage |
|---|---|---|
| `system` | `Model version` → join to `model_metadata` | **927/927 distinct strings join exactly (100%)** |
| `benchmark` | the file | 100% |
| `metric` | the score column name + `benchmark_metadata.score_column` | 59/81 explicit |
| `value` | score column × `benchmark_metadata.scale` | 100% |
| `uncertainty.type`/`value` | `stderr`, `*Standard Error`, `* SE`, `* std dev`, `95% CI low/high`, `CI_low/CI_high`, `95% CI half-width` | **2,819/6,598 rows (42.7%)** |
| `uncertainty.n_runs` | `Runs` (deepswe), `Trajectories` (balrog/osworld, 14% filled), implied by `AVG@5`, `mean@5` | rare |
| `date_reported` | `Started at` (Epoch-run), `Run date`/`Date of evaluation`/`Date added`/`Created`/`Graded at`/`Last updated` (scattered) | ~30% |
| `source` | `Source` + `Source link` | **3,985/6,598 rows (60.4%)**; for the 1,550 Epoch-run rows the source is Epoch itself |
| `notes` | `Notes` | **264/4,670 = 5.7%** |
| `verification` | **derivable only as a coarse guess** — see (b) |
| `subset` | sub-score columns (VideoMME's 12, Balrog's 6, GeoBench's 5×5, CL-bench's 4, LiveBench's 6) | these become Subsets |

### `EvalConditions`
| our field | Epoch source | coverage |
|---|---|---|
| `shots` | `Shots` column | present in **14/80 files**, filled on **1,283/6,598 rows = 19.4%**; values are dirty: `5`, `0`, `1`, `3`, `8`, `few`, `0-shot`, `25-shot`, `10-shot`, `2-shot`, `64`, `100` — mixed int and string |
| `reasoning_effort` | (i) `model_version` suffix `_high/_max/_xhigh/_medium/_low/_minimal/_none/_unknown` on **2,402/6,169 = 38.9%** of rows; (ii) explicit `Reasoning effort` col (3 files, 168 rows), `Reasoning level` (cursorbench), `Reasoning` (osworld_2) | ~40% partial |
| `scaffold` | `Scaffold` col (2 files, 50 rows), `Agent` col (3 files, 303 rows), `Harness` col (5 files, 143 rows), `Agent Org`/`Model Org` (terminalbench only) | **<8% of rows** |
| `tools_allowed` | `Tools` (geobench only), `Tool setting` (osworld_2 only) | **<1%** |
| `thinking_token_budget` | encoded in `Name` free text (`Claude Opus 4.6 (120K, High)`) and one Note (`2048 thinking token budget`) | negligible |
| `cost_usd` | `Cost`, `Cost per task`, `Cost per run`, `Mean cost (USD)`, `Spend`, `Total cost (USD)`, `Estimated cost (USD)` | ~10% |
| `wall_clock_hours` | `Wall-clock hours` (gbaeval), `Average duration (hours)` (frontierswe), `Time per case (seconds)` (aider) | <2% |
| `max_output_tokens`/steps | `Step budget` (osworld_2), `Steps per task` (cursorbench), `Mean agent steps` (deepswe), `(100 steps)` in OSWorld `Agent` free text | <3% |
| `harness` | `Harness` (5 files), `METR version`, `LiveBench Version`, `Edit format` (aider) | <3% |
| `n_samples`/`selection_strategy`/`k` | **only encoded in the metric NAME**: `Pass@1`, `Pass@4`, `Score OPT@1`, `OPT@10`, `Score (AVG@5)`, `Best@5`, `Worst@5`, `mean@5`, `Best score (across scorers)` | never a structured field |
| `date_evaluated` | `Started at` (1,546 rows), `Run date`, `Date of evaluation`, `Graded at` | ~28% |
| `prompt_template_hash` | `Prompt` (cad_eval), `Prompting` (spatialviz), `Candidate SHA-256` (gbaeval) | <1% |

**Zero coverage anywhere in 6,598 rows:** `chain_of_thought` (boolean), `shot_selection`, `sampling.temperature`, `top_p`, `seed`, `retries_allowed`, `judge_model`, `judge_prompt_hash`, `decontamination_applied`, `human_in_loop`, `context_window_used`, `hardware`, `harness_source`, `prompt_template_source`.

### `Metric`
| our field | source |
|---|---|
| `id`/`name` | `benchmark_metadata.score_column` (59) + score column headers (80) |
| `range.min/max` | `random_baseline` → effective floor; `score_ceiling` |
| `chance_baseline` | `random_baseline` — **21 benchmarks have non-zero values, a genuinely useful and rarely-published field** |
| `higher_is_better` | true for all 81 (implied by ECI monotonic fit, not stated) |
| `units`/`aggregation` | inferable from name (`EM`, `Accuracy mean`, `Pass@1`, `Win Rate (%)`, `Average progress`) |
| `definition`, `formula_reference`, `pitfalls`, `domains`, `sources` | **absent** |

### `Source`
`Source` (52 files, 3,983 rows) and `Source link` (32 files, 2,496 rows) give `title` + `url`. 74 distinct source strings in `processed_data_for_eci.csv`. Mix of papers with arXiv URLs (`http://arxiv.org/abs/2307.09288`), leaderboards (`https://crfm.stanford.edu/helm/...`), GitHub repos, and vendor pages. **Absent:** `type` (inferable from URL pattern with ~90% accuracy), `doi`, `authors`, `published`, `accessed`, `archive_url`, `archive_captured`. Our CI rule "every non-DOI Source needs an `archive_url`" means **every one of ~74 ingested sources needs a Wayback push** — that is a concrete, automatable ingest step.

### `HumanBaseline`
**Almost entirely absent.** The only human-comparison data in 6,598 rows: `forecastbench_external.csv` columns `Better than superforecaster median?`, `Better than public median?`, `Superforecaster p-value`, `Public p-value` (81 rows), and `gdpval_external.csv` `Win Rate (%)` / `Win + tie rate (%)` which are implicitly *against human experts* (11 rows). `benchmark_metadata.score_ceiling` (0.57/0.6/0.85 on three benchmarks) is a *measurement ceiling*, not a human baseline, and conflating the two would be a real error. **Human baselines are ~99% our own work.**

---

## (b) WHAT EPOCH DOES NOT CAPTURE — our marginal contribution

**1. Evaluation conditions, quantitatively.** Against the 10 *material* fields in our comparability rule (`shots`, `chain_of_thought`, `tools_allowed`, `selection_strategy`, `k`, `n_samples`, `retries_allowed`, `judge_model`, `human_in_loop`, `subset_used`), Epoch supplies:
- `shots`: 19.4% of rows, dirty types
- `tools_allowed`: <1%
- `selection_strategy`/`k`/`n_samples`: **0% structured** — only parseable from metric names
- `chain_of_thought`, `retries_allowed`, `judge_model`, `human_in_loop`: **0%**
- `subset_used`: implicit in the file choice only

A `condition_completeness` score computed over Epoch's rows would land around **0.05–0.15 on average**. That is the number to put in the plan: *ingesting Epoch gives us 6,598 claims at ~10% condition completeness; our differentiator is raising that, not collecting more rows.*

**2. Conditions are present but unstructured — buried in free text.** The clearest example, `arc_agi_external.csv`, five rows sharing the identical `Model version` key `claude-opus-4-6_120K`:
```
Score 0.94 | Name = "Claude Opus 4.6 (120K, High)"   | Source = https://arcprize.org/leaderboard
Score 0.94 | Name = "Claude Opus 4.6 (High, 120k thinking)" | Source = ARC Prize Leaderboard
Score 0.93 | Name = "Claude Opus 4.6 (120K, Max)"    | Source = https://arcprize.org/leaderboard
Score 0.92 | Name = "Claude Opus 4.6 (120K, Medium)" | Source = https://arcprize.org/leaderboard
Score 0.86 | Name = "Claude Opus 4.6 (120K, Low)"    | Source = https://arcprize.org/leaderboard
```
Epoch's primary key **cannot distinguish these five claims** — the only discriminator is a human-readable label, and rows 1 and 2 are near-duplicates of the same underlying run from two spellings of the same source. Our `EvalConditions` + `comparability_key` resolves this exactly. This single example is the strongest argument for the project, and it comes from Epoch's own data.

**3. Conditions are frequently *assumed*, and Epoch says so in `Notes`.** Verbatim from the corpus:
- `terminalbench_external.csv`: `"Assuming medium based on GPT-5 being run at medium."`
- `vpct_external.csv`: `"Assuming medium reasoning effort"`
- `geobench_external.csv`: `"Assuming latest Flash version"`
- `cad_eval_external.csv`: `"Assuming latest version of Gemini 1.5 Pro"`
- `bbh_external.csv`: `"Couldn't find shot count"`
- `fictionlivebench_external.csv`: `"currently pending confirmation of thinking token length"`
- `live_bench_external.csv`: `"Assumed baseline 3.7 Sonnet"`
- `gdp_pdf_external.csv`: `"No model-version mapping in configs/mappings.yaml yet."`
- `piqa_external.csv`: `"Explicitly fine-tuned on it"` ← a contamination signal, recorded as an unstructured note

These are exactly the "unknown vs default" distinctions our schema makes structural. Epoch records them as prose in a column filled on **5.7% of rows**. Our `null = unknown, not default` rule plus `condition_completeness` turns each of these into a visible quality signal instead of a footnote.

**4. No verification ladder.** Epoch has no `verification` field. We can derive a floor:
- 1,550 rows from Epoch-run files, of which **828 have a public Inspect-AI `.eval` log** → credibly `independent-reproduction` (Epoch is a third party, ran it, published transcripts)
- 459 Epoch-run rows have **private** logs (all FrontierMath, some others) → `maintainer-verified` at best, unverifiable by us
- 5,048 external rows are leaderboard/paper scrapes → `self-reported` unless the leaderboard is a held-out server
That leaves the *interesting* distinctions — `held-out-server`, `third-party-audited`, `disputed` — entirely to us. FrontierMath is a private held-out set; ARC-AGI-2 has a semi-private set; SWE-bench Verified is public. Epoch does not encode this, and it is a first-order determinant of whether a number means anything.

**5. No contamination model.** `piqa`'s `"Explicitly fine-tuned on it"` note is the only contamination datum in 6,598 rows. No `contamination_risk`, no evidence refs, no `decontamination_applied`.

**6. No benchmark description, no domain facets, no capability facets, no evaluation-method facet.** `benchmark_metadata.csv` has 9 columns; **not one is a facet.** The entire coverage/gap analysis (differentiator #3) is 100% our own work — Epoch cannot produce it from what they store.

**7. No archival.** 74 distinct source strings, many bare leaderboard URLs (`https://cursor.com/cursorbench`, `https://gbaeval.com/model/claude-opus-5`, `https://osworld-v2.xlang.ai/`), zero `archive_url`. Leaderboard rot is guaranteed.

**8. Domain breadth.** 81 benchmarks across ~8 of our 18 families, 0% non-LLM systems. Differentiator #1 is untouched.

**9. Conversely — three things Epoch has that our schema currently lacks and should add:**
- `training_compute_flop` + estimation notes on `System` (337 models) — this is Epoch's distinctive asset and enables compute-vs-capability plots nobody else can do from a catalogue
- `random_baseline` per metric (21 non-zero) — makes headroom computable, which our `Metric.chance_baseline` wants and rarely gets
- Published Inspect-AI log URLs as a first-class `ResultClaim.artifact_url` — 828 public transcripts is real evidence, and our schema has no field for it

---

## (c) SUITABILITY FOR AUTOMATED INGESTION

**Verdict: yes for `System`, `Organization` and `Metric`-baseline data; yes-with-quarantine for `ResultClaim`; no for `Benchmark` facets.**

Licence is permissive (CC-BY-4.0, no SA, no NC), so redistribution in our repo is clean provided we attribute.

### What the adapter must do

1. **Snapshot provenance.** sha256 `b.zip`; write `data/_ingest/epoch-2026-09-16/manifest.yaml` with the hash, retrieval date, the verbatim citation string, and per-file row counts. Create one `Source` record `src-epoch-benchmarks-2026-09` with `type: dataset`, `url: https://epoch.ai/benchmarks`, plus a Wayback capture.

2. **Organizations first.** 70 distinct strings → split on commas → dedupe against our org registry. Manual review required for `Google DeepMind` vs `Google` vs `Google DeepMind,Google`, and for `Z.ai (Zhipu AI)` alias handling.

3. **Systems.** 1,063 rows → 550 `System` entities keyed on `model_group`, each with `versions[]` from `model_version`. Drop the 11 blank rows and the ~14 model_group-only stubs, or emit them as low-confidence. Map `accessibility` → `open_weights` + `license_class`. Carry `training_compute_flop` with an `estimated: true` flag wherever `Training compute notes` contains "imputed".

4. **Benchmarks: create stubs only.** 81 rows → 81 `Benchmark` files with `id`, `name`, `aliases`, `release_date`, `homepage`, plus `verification_status: unreviewed` and every facet `null`. Split Epoch's conflated names into Benchmark + BenchmarkVersion (the 5 FrontierMath rows are ~2 benchmarks × versions; `OSWorld` / `OSWorld 2.0`; `CL-bench` / `CL-bench Life`; `ARC-AGI` / `ARC-AGI-2`; `METR` / `METR Time Horizons`). **Do not auto-publish these to the site until a human assigns domain facets** — an unfaceted benchmark is invisible to the coverage map anyway.

5. **ResultClaims.** Per file: read `benchmark_metadata.score_column` + `scale` where available (59/81), hand-map the other 21. Normalise value = raw × scale. Attach uncertainty from whichever of the ~8 uncertainty column-name patterns is present. Parse the `model_version` effort suffix into `EvalConditions.reasoning_effort` (regex `_(max|xhigh|high|medium|low|minimal|none|unknown)$`, 2,402 hits) — and map `_unknown` to `null`, **not** to a default. Parse `Shots` into an int, routing `few`/`0-shot`/`25-shot` through a normaliser and leaving unparseable values null. Parse `Pass@1`/`AVG@5`/`Best@5`/`OPT@10` column names into `selection_strategy` + `k` + `n_samples`. Set every other material condition field to `null`.

6. **Sub-scores → Subsets.** VideoMME 12, Balrog 12, GeoBench 25, CL-bench 8, LiveBench 6, Fiction.LiveBench 11, forecastbench 3 splits, spatialviz 4, cad_eval ~12. Ingesting these multiplies claims ~2× (see (d)) but only if the parent benchmark has real Subset entities — defer to a second pass.

7. **Verification assignment.** Rule: file in the Epoch-run set AND `Logs` contains `-public` → `independent-reproduction`, with the `.eval` URL stored. Epoch-run with `-private` or blank → `maintainer-verified`. External → `self-reported`. Encode the rule in the adapter, not in each record.

8. **Archive every `Source link`** (2,496 rows, 74 distinct targets) to the Wayback Machine at ingest time.

### Pitfalls, ranked by how much damage they do

- **Conditions are the join key Epoch doesn't have.** 843 rows share a `Model version` with another row in the same file. Some are genuine conflicting claims from different papers (good — our schema wants them). Some are the *same* run listed twice under two spellings of the same source (`https://arcprize.org/leaderboard` vs `ARC Prize Leaderboard` — both appear in `arc_agi_external.csv`). Some are different reasoning efforts collapsed onto one key. **An automated dedupe will silently merge distinct claims or silently duplicate identical ones.** Mitigation: never dedupe on ingest; emit every row as a separate ResultClaim with `condition_completeness` low, and surface near-duplicates in the quality dashboard for human resolution. Concrete near-duplicate signature to flag: same benchmark + same model_version + |Δvalue| < 0.005 + different `Source` spelling.

- **Conflicting claims are real and common, and are the feature not the bug.** `mmlu_external.csv`, `falcon-7b`, all at 5 shots:
  ```
  0.35   Falcon2-11B Technical Report        http://arxiv.org/abs/2407.14885
  0.262  Llama 2 paper                       http://arxiv.org/abs/2307.09288
  0.262  Qwen Technical Report               https://arxiv.org/pdf/2309.16609
  0.2603 Baichuan 2                          http://arxiv.org/abs/2309.10305
  0.269  XGen-7B Technical Report (2-shot)   http://arxiv.org/abs/2309.03450
  0.239  XGen-7B Technical Report (0-shot)   http://arxiv.org/abs/2309.03450
  ```
  A **34% relative spread** on the same model, same benchmark, same nominal shot count, from four different vendors' papers. Use this in the plan as the canonical illustration of why ResultClaim multiplicity + comparability_key is necessary. Epoch stores all six and does not adjudicate; so should we, but with structure.

- **Model identity resolution is solved *within* Epoch, unsolved *across* sources.** All 927 distinct `Model version` strings in the benchmark CSVs join 100% to `model_metadata.csv`. But those strings are provider-endpoint slugs (`accounts/fireworks/models/glm-4p6`, `chutes/DeepSeek-R1-0528`, `amazon.nova-pro-v1:0`, `gpt-6-astra_max`) mixing **model identity, hosting provider, and reasoning effort into one token**. Mapping them to our `System` + `SystemVersion` + `EvalConditions.reasoning_effort` triple requires a hand-maintained crosswalk. Budget this: ~550 model_groups, ~1,048 version strings. It is the single largest manual cost in the ingest.

- **Benchmark identity across sources.** Epoch's `FrontierMath-Tier-4-2025-07-01-Private` is one string encoding benchmark + tier + snapshot date + access mode. `MATH level 5` is a subset of MATH. `GPQA diamond` is a subset of GPQA. `ARC AI2` and `ARC-AGI` are unrelated benchmarks sharing a prefix. Automated slugification will produce wrong IDs, and our IDs are permanent and never reused — **so benchmark ID allocation must stay manual.**

- **Score scale traps.** `vending_bench_2_external.csv` `Score` is **dollars** (11,181.87), not a rate. `metr_time_horizons_external.csv` `Time horizon` is **minutes** (1,044.78). `webdev_arena` is an **Elo** (`Arena Score`). `lech_mazur_writing` is 0–10. `aider_polyglot`/`os_world`/`lmca` are percents needing ×0.01. Blindly applying `scale` from `benchmark_metadata` covers 59/81; the other 21 will silently produce nonsense if defaulted to 1.0.

- **Encoding.** `dtbench_external.csv` and `lmca_external.csv` headers contain a mojibake byte (`CRI-rescaled score 95% CI (\xef\xbf\xbd)`) — the ± sign is corrupted. Adapter must read as UTF-8 with `errors='replace'` and normalise header names.

- **Header inconsistency.** `id` vs `ID` vs `UUID`; `Source link` vs `Source link (site from table)`; `Accuracy SE` vs `Accuracy Standard Error` vs `stderr` vs `Overall std dev` vs `95% CI half-width`. 62 distinct header signatures across 80 files means the adapter needs a **per-file column-mapping config**, roughly 80 small YAML stanzas. That is the honest cost estimate — not a generic parser.

- **Staleness.** These are files on disk with no version handle. Epoch updates continuously (new models appear within days — GPT-6 Astra dated 2026-09-03 is in a 2026-09-16 download). Our ingest must be re-runnable and diff-aware, and every ingested claim must carry the snapshot ID so a later re-ingest can supersede rather than duplicate.

- **The 21 orphan files** have no `score_column` or `scale` in metadata. Hand-map or skip.

---

## (d) CLAIM VOLUME

| quantity | count |
|---|---|
| Raw rows across 80 per-benchmark CSVs | **6,598** |
| Unique (benchmark-file, model_version) pairs | 5,351 |
| Rows from Epoch's own runs (14 files) | 1,550 |
| Rows scraped from external leaderboards/papers (66 files) | 5,048 |
| Rows with any uncertainty value | 2,819 (42.7%) |
| Rows with any Source / Source link | 3,985 (60.4%) |
| Rows with a public Inspect-AI log | 828 |
| Normalised (model, benchmark, score) rows in `processed_data_for_eci.csv` | 2,760 |
| If every secondary numeric score column also became a claim (sub-metrics/subsets) | ~13,400 |

Against the Phase-3 target of **500 claims**:

- Headline claims only (one per row): **6,598 → 13.2× the target**, i.e. Phase 3's claim quota is met **twelve times over** by a single adapter run.
- The conservative, clean subset — `processed_data_for_eci.csv`, already normalised, one score per (model, benchmark), 58 benchmarks × 266 models — is **2,760 claims → 5.5× the target**.
- The high-quality subset — Epoch-run rows with public transcripts and stderr — is **828 claims → 1.66× the target**, and these are the only ones that would earn a verification badge above `self-reported`.
- The subset meeting a plausible `condition_completeness ≥ 0.5` bar: **approximately zero**. Even the best-documented file (`deepswe_external.csv`, with Harness + Reasoning effort + Runs + steps + CI) leaves `chain_of_thought`, `judge_model`, `temperature`, `retries` and `shot_selection` null.

So the honest framing for the plan: **the 500-claim target is the wrong metric if Epoch is ingested.** Ingestion makes claim count free. The binding constraint becomes condition completeness and verification level, and the Phase-3 goal should be restated as e.g. *"500 claims at condition_completeness ≥ 0.6 with a named source and an archived URL"* — a target Epoch's data does not come close to satisfying, and which therefore still measures our actual work.

---

## (e) BLUNT JUDGEMENT: should we hand-curate LLM benchmark results at all?

### The case for NOT hand-curating (ingest and move on)

1. **Volume is decided.** 6,598 claims, free, CC-BY, one adapter. Hand-curation of LLM results would produce maybe 30–60 claims per person-week at the quality bar our schema implies. Matching Epoch's volume by hand is ~2 person-years for a 1–2-person part-time team. It will not happen.
2. **Epoch is better resourced and better positioned than us on exactly this axis.** They run their own evals with Inspect-AI, publish 828 public transcripts, and maintain 1,048 model-version mappings. We would be doing a worse job of their job.
3. **The user's own constraint says so.** "Several benchmark services are running — especially LM benchmarks — so it is VERY important to avoid repetition." Hand-curating LLM leaderboard numbers *is* the repetition.
4. **Our four differentiators are all orthogonal to result volume.** Cross-domain breadth, comparability keys, coverage gaps, citable data-at-a-commit — none of them get better by us typing GPQA scores.
5. **Every hour spent on LLM results is an hour not spent on the 10 domain families with zero coverage** — robotics, protein, chemistry, medicine, weather, materials, audio. That is the part nobody else has done.

### The case FOR hand-curating some

1. **Ingestion at ~10% condition completeness produces exactly the artefact we said we would not build.** 6,598 rows of "number, model, benchmark, no conditions" is a leaderboard aggregator. If the flagship feature is a comparability key and 90% of our claims have null material fields, the comparison workbench will refuse to compare almost everything, and the feature looks broken rather than principled.
2. **Provenance discipline is the whole trust premise.** Ingesting 2,613 rows with no `Source` at all, under our own banner, contradicts "unsourced data destroys trust" — even with a blanket Epoch attribution, because the blanket attribution tells the reader where the *file* came from, not where the *number* came from.
3. **The demo needs proof.** A handful of claims curated to full condition completeness — same benchmark, same model, different scaffolds/efforts, showing a 34%-style spread — is the one artefact that makes the comparability key legible to a visitor in ten seconds. Bulk data cannot do that.
4. **Hand-curation is how we learn the schema is wrong.** Curating 40 claims by hand will surface missing fields (`artifact_url`, `training_compute_flop`, `thinking_token_budget` as first-class) far faster than writing an adapter against a schema nobody has stress-tested.
5. **Some LLM benchmarks are our bridge to the science domains** — CritPt (physics), Surface Evolver Bench (physics), CadEval (engineering), GeoBench (geospatial), SciCode. Curating those properly serves cross-domain breadth directly.

### Recommendation

**Ingest Epoch in bulk. Hand-curate a small, deliberately chosen set. Keep the two provably separate in the repo and in the UI.**

Concretely:

1. **Ingest all 6,598 rows** into `data/claims/_ingested/epoch/`, every record carrying `provenance: epoch-2026-09-16`, `verification` assigned by the transcript rule, `condition_completeness` computed honestly (expect ~0.10 mean), and `curation.verification_status: machine-ingested`. These are visible, searchable, and clearly badged as bulk-imported. **Do not mix them into `data/claims/` proper.**

2. **Make `condition_completeness` and `verification` the default sort and the default filter**, with the UI defaulting to hiding `machine-ingested` claims below a completeness threshold in comparison views while still showing them in browse views. The bulk data then serves as *coverage* (every model, every benchmark, searchable — which is what the user asked for: "a great collection, well categorized, easy to search") without polluting *comparison* (which is where our credibility lives).

3. **Hand-curate ~50–80 LLM claims, chosen adversarially, not representatively.** Specifically: (i) the `arc_agi` `claude-opus-4-6_120K` family at 5 reasoning efforts, fully specified — this single cluster demonstrates the whole thesis; (ii) the `falcon-7b` MMLU six-way conflict with all six sources archived; (iii) SWE-bench Verified across 3–4 different scaffolds with `built_on` populated, using Terminal Bench's `Agent Org`/`Model Org` split as the model; (iv) 10–15 claims on the science-adjacent benchmarks (CritPt, Surface Evolver, CadEval, SciCode, GeoBench). Total: well under 100 claims, maybe 3–4 person-weeks.

4. **Spend everything else on the non-LLM half of the map.** Epoch's 81 benchmarks confirm the gap quantitatively: 0 of 81 touch robotics, chemistry, biology, medicine, climate, materials or audio. That is where hand-curation has no substitute and no competitor, and where the marginal value of a curator-hour is highest.

5. **Add to the schema before ingesting**, because retrofitting 6,598 records is painful: `ResultClaim.artifact_url` (transcript/log), `ResultClaim.provenance_snapshot`, `System.training_compute_flop` + `training_compute_estimated` + `training_compute_notes`, and `EvalConditions.reasoning_effort` as an enum-plus-freetext (Epoch's `max/xhigh/high/medium/low/minimal/none` vocabulary is a reasonable starting enum, drawn from 2,402 observed rows).

The one-line version for the plan: **Epoch gives us the numbers for free; it does not give us the conditions, the facets, the provenance grade, or any domain outside LLMs — which is precisely the list of things the project exists to provide.** Ingest it, badge it honestly, and let it prove by contrast why the hand-curated layer matters.