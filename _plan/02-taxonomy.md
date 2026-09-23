# 02 -- Taxonomy

This document defines the eight facets and their controlled vocabularies. It is the most
consequential document in the plan, because the taxonomy is the only part of the system that cannot
be regenerated. Code can be rewritten, the site can be redesigned, the build artifacts are
disposable — but a thousand benchmarks tagged against a vocabulary that turns out to be wrong is a
thousand entries that have to be re-read by a human. The failure mode to avoid is taxonomy churn
after curation has begun: every time a term is added, split or merged, every existing entry becomes
a candidate for re-tagging, and the coverage matrix — the project's headline output — silently
misreports until the retro-tag pass is finished.

The vocabularies here supersede the version in the archive. Where they differ, this document is
correct and the changes are listed with reasons in a changelog at the end of each facet. All eight
facets carry one.

**This document owns four things and nothing else claims them:** the eight facet vocabularies, the
capability-group rollup (§4.3, settled by decision D1), the per-family seed allocation (§3, settled
by decision D2), and the cross-cutting tagging rules (§11). Numbers owned elsewhere are linked, not
restated — the defect this revision exists to remove was every document keeping its own prose copy
of the same figure and the copies drifting apart.

**The term lists and counts in §§3–10 and §14 are generated.** They are rendered from
`taxonomy/*.yaml` by `scripts/taxonomy_stats.py` and checked byte-for-byte in CI (check 9b, and
check 9f for the seed allocation — [05-repository-and-workflow.md](05-repository-and-workflow.md)
§9, which owns the check numbering; 9d is the homograph check). Hand-editing a term list or a count in this file fails the build. Edit the YAML.

Positioning, non-duplication and the ingest-versus-curate doctrine are in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md). How the taxonomy is built,
tested, governed and evolved — ADRs, inter-curator agreement testing, the retro-tag protocol — is in
[03-taxonomy-build-process.md](03-taxonomy-build-process.md). The entities these facets hang off are
in [04-data-model.md](04-data-model.md). The derived metrics that consume them are in
[12-analytics-and-trends.md](12-analytics-and-trends.md).

Four questions this document used to answer inconsistently were adjudicated on 2026-09-21 and are
now settled. They are cited below as **D1** (the capability-group vocabulary), **D2** (the seed total
and the per-family floor), **D3** (identifier namespacing and the `puzzle-solving` duplication) and
**D4** (what encodes a domain family now there are nineteen). Their decision records are in
`_workflow/decisions/`.

---

## 0. Why the taxonomy is the product

Three of the four differentiators are taxonomy, not software.

**Cross-domain breadth at depth** is a claim about vocabulary before it is a claim about entry
count. A catalogue that files Matbench Discovery under "Other" has not indexed materials science, it
has stored a link. The vocabulary is what turns 1,500 scattered entries into a map.

**Coverage and gap analysis** is literally the Domain facet crossed with the Capability facet. The
empty cells are the most valuable output of the project, and an empty cell is only meaningful if the
two terms that define it are stable, defined, and applied consistently. If `abstraction` and
`inductive-reasoning` overlap, every cell in those two rows is noise.

**Comparability as a refusal mechanism** starts with the Evaluation Method facet, which is what tells
a reader whether a number is a unit test result, a rubric aggregate assigned by a language model, or
an Elo rating whose meaning depends on which other systems happened to be in the pool that week.

Only the fourth — citable data at a commit hash — is infrastructure rather than vocabulary.

The ingestion evidence makes the point sharply. Epoch AI's `benchmark_metadata.csv` has nine columns
(`benchmark, in_eci, source_file, score_column, scale, random_baseline, score_ceiling, release_date,
superseded_by`) and **not one of them is a facet** (counted from the local `epochdl/` files;
recon:epoch-assets, 2026-09-17). Roughly 30 of the ~45 `Benchmark` fields in
[04-data-model.md](04-data-model.md) have to be authored by hand for every ingested record. That is
not a gap in Epoch's data — Epoch built a results archive and built it well — it is the precise
shape of the work nobody else is doing. Every hour spent on the taxonomy is spent on the part of the
project that cannot be scraped.

---

## 1. Why faceted and not hierarchical

A single hierarchy cannot classify benchmarks, and the proof is not abstract. Try to place these:

- **CASP** is structural biology *and* prediction *and* wet-lab validated — its ground truth is an
  unreleased experimental structure, its assessors publish peer-reviewed papers rather than a
  leaderboard, and human-expert groups are ranked in a separate category from automated servers.
- **ARC-AGI** is visual *and* abstract reasoning *and* general intelligence, and ARC-AGI-3 is also an
  interactive game environment.
- **RLBench** is robotics *and* vision *and* simulated.
- **Open Catalyst OCx24** is a computational chemistry benchmark whose ground truth is a wet-lab
  measurement (arXiv 2411.11783).
- **GeoBench** is photo geolocation: vision, geospatial reasoning, and a language-model evaluation at
  the same time.
- **The Speech Accessibility Project Challenge 2** (NeurIPS 2026) is speech recognition, medicine,
  and gated human-subject data.
- **BirdCLEF+ 2026** is bioacoustics, ecology, and audio event classification.
- **MLE-bench** is machine-learning engineering, agentic tool use, and — because its medal thresholds
  come from real Kaggle leaderboards — a human-comparison battery.

Every one of these forces a tree to pick a false primary parent and then fight the exceptions
forever. The exceptions are not rare; in the non-language half of the map they are the majority.

The design is therefore **faceted classification**:

- **Domain** is the navigational spine. Two levels, `family/subdomain`, used for the site's primary
  browse structure and for clustering in the Atlas view ([10-visualization.md](10-visualization.md)).
  A benchmark has exactly one *primary* domain and any number of *secondary* domains.
- **Seven further facets** are flat, multi-valued and orthogonal. They drive filtering, the coverage
  matrix, and the comparability warnings.

### Prior art, and what we take from it

We are not the first to write a vocabulary here and the plan should say so.

| Source | What it is | What we take |
| --- | --- | --- |
| **Stanford HELM** scenario taxonomy (Capabilities, Safety, VHELM, HEIM, ToRR, MedHELM, AudioHELM) | The best existing cross-modality evaluation vocabulary. Entered maintenance mode 2026-06-01 (recon:landscape, verified 2026-09-17). | Ancestry for the Capability and Evaluation Method facets. Cite it; extend rather than reinvent. |
| **BenchmarkList** (benchmarklist.com) | A closed commercial catalogue. Its public interface presented 11 primary abilities plus 40+ flat subcategories as observed on 2026-09-17 (recon:landscape). There is no API and no export, so that is a reading of a rendered interface rather than a count of a vocabulary — *(unverified — confirm before relying on this)*. | Evidence that a flat ability list at roughly our Capability scale is workable in production. We do not copy terms from a closed product. |
| **Every Eval Ever** `eval.schema.json` | Result-level schema: `generation_config.generation_args`, `agentic_eval_config.available_tools[]`, `sandbox`, `metric_config`. Data CC BY 4.0, code MIT (arXiv 2606.14516). | Field *names* for shared evaluation conditions, so an EEE-validated result can join our benchmark record on a stable ID. The field-by-field crosswalk is at the end of §5, and that table is where the alliance case is actually made rather than asserted. |
| **MLCommons Croissant** | The adopted ML *dataset* metadata standard. No benchmark/evaluation extension exists. Spec is CC BY-ND. | Dataset-level structure, which we deliberately do not duplicate. Our facets describe the benchmark; Croissant describes its data. |
| **BetterBench** (24 benchmarks, 46 criteria, 4 lifecycle stages; arXiv 2411.12990) | The best prior art on benchmark quality assessment. Its published set has stood at 24 assessed benchmarks and no additions were observed after 2024 *(unverified — recon:landscape found no visible update surface; confirm before relying on this)*. | The lifecycle-stage framing behind Facets 6 and 8. We link to their assessments rather than issuing our own quality scores — see §13. |

The BetterBench row is worded carefully on purpose. "Stale" is a judgement; "no additions observed
after 2024, and we could not find an update surface" is an observation with a date attached. §9
forbids the project from making the first kind of statement about a benchmark, and §13 makes
BetterBench the link target for the entire quality question — asserting editorially that our own
chosen authority is dead would be both rude and self-undermining. The same standard is turned on us
by the contested-status rule in §8.

### The cost of facets, and how it is paid

Facets are more work per entry than a tree, and the honest number is larger than the one the earlier
draft gave. A `full` entry requires values across **nineteen controlled vocabularies spread over
about twenty vocabulary-valued fields** (§14 lists every one), plus sourcing for the contamination
and independence flags, plus range estimates that each carry a mandatory `basis` string, plus two
`examples[]` if the entry is the first use of any term. A `stub` requires **three**:
`domain.primary`, `lifecycle` and a homepage URL. Twenty decisions per entry is how a catalogue
stalls at 120 entries; three is how it does not.

The mitigation is **progressive tagging**, mapped onto the validation tiers in
[04-data-model.md](04-data-model.md). A `stub` is enough to be findable and enough to occupy a
position on the coverage matrix's row axis. A `full` entry requires all eight facets and sourced
fields. The site renders both, with the completeness state visible.

**The seed target is 70% `full`.** That is a decision, not an observation, and it belongs here
because it is an input to arithmetic another document publishes: D1's capability-group occupancy
figures assume 224 of the 320 seed entries reach `full`. The split that produces it is **the seven
Core families at 100% `full` (144 entries) plus 45% of the twelve non-Core families (80 of 176)**,
giving 224 `full` and 96 `stub`. The reason for that shape rather than an even 70% everywhere is the
non-duplication doctrine: the Core seven are where hand-curated conditions *are* the differentiator,
while an ingest-then-verify family delivers more value as twelve findable stubs than as six fully
tagged entries. The risk, stated so it can be checked: if the Core seven slip below 100% `full`,
every coverage figure D1 derives moves, and the response is to re-derive them, not to keep
publishing the old ones.

The failure mode progressive tagging avoids is the one that killed every catalogue in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md): a schema so demanding that
nothing gets added, followed by 20 months of no commits.

---

## 2. The eight facets at a glance

| # | Facet | Cardinality | Required at | Primarily drives |
| --- | --- | --- | --- | --- |
| 1 | **Domain** | 1 primary + n secondary | stub | Browse spine, Atlas clusters, coverage matrix rows |
| 2 | **Capability** | multi-valued, plus a derived 13-group rollup (§4.3) | full | Coverage matrix columns |
| 3 | **Evaluation method** | multi-valued | full | Comparability warnings, trust badges |
| 4 | **Subject under test** | multi-valued (designed-for) | full | Comparability refusal, claim validation |
| 5 | **Data properties** | 5 independent fields | full | Contamination signalling, headroom availability |
| 6 | **Lifecycle** | 3 independent fields (1 partly derived, 1 fully derived) + a contest flag | stub (`lifecycle` only) | Saturation wall, dead-benchmark signalling |
| 7 | **Governance and host** | 3 independent fields | full | Ecosystem analysis, independence disclosure |
| 8 | **Execution cost and reproducibility** | 3 fields + ranged estimates | full | Suite builder, deferred runner layer |

All vocabularies are **closed enums** stored as YAML in `taxonomy/` and validated in CI. Adding a
term requires an ADR ([03-taxonomy-build-process.md](03-taxonomy-build-process.md)). This friction is
deliberate: an open vocabulary degrades into synonyms within months and destroys the coverage
analysis. The pressure-release valve is the free-text `tags[]` field on `Benchmark`, which is
searchable, is never validated, and is **explicitly excluded from the coverage matrix**. When a
curator wants a word the enum does not have, it goes in `tags[]` and the ADR conversation happens
later, with evidence from how often the tag was used.

---
## 3. Facet 1 — Domain (the spine)

Two levels: `family/subdomain`. Exactly one primary. Secondaries unlimited but each one should be a
domain in which a specialist would expect to find this benchmark when browsing. A bare family is a
navigational node and is **not** assignable to `domain.primary` or `domain.secondary[]` (D3; see
§11 rule 11).

> The term lists in this section and in §§4–10 are rendered from `taxonomy/*.yaml` by
> `scripts/taxonomy_stats.py`. Edit the YAML, not this file; CI check 9b fails on any diff.

### language
`understanding` · `generation` · `dialogue` · `summarization` · `translation` · `multilingual` ·
`low-resource-languages` · `long-context` · `retrieval-qa` · `information-extraction` ·
`creative-writing`

### mathematics
`arithmetic` · `competition-math` · `formal-theorem-proving` · `symbolic-manipulation` ·
`applied-modeling` · `research-level-math` · `proof-verification`

### code
`function-synthesis` · `repository-scale-se` · `bug-repair` · `competitive-programming` ·
`code-understanding` · `program-verification` · `ml-engineering` · `data-science-workflows` ·
`code-performance-optimization`

### reasoning-general
`commonsense` · `logical-deduction` · `causal-inference` · `abstraction-induction` ·
`temporal-reasoning` · `spatial-reasoning` · `planning` · `theory-of-mind` · `counterfactual` ·
`puzzle-solving`

### vision
`classification` · `detection` · `segmentation` · `video-understanding` · `3d-reconstruction` ·
`novel-view-synthesis` · `multi-view-stereo` · `image-matching-correspondence` ·
`image-restoration-enhancement` · `depth-geometry` · `driving-perception-3d` · `image-generation` ·
`video-generation` · `document-understanding` · `ocr-handwriting` · `medical-imaging-cv`

### audio-speech
`speech-recognition` · `speech-synthesis` · `speaker-tasks` · `speech-translation` ·
`music-generation` · `music-understanding` · `audio-event-understanding` ·
`audio-event-detection-localization` · `machine-condition-monitoring` · `bioacoustics`

### multimodal
`visual-qa` · `visual-grounding` · `chart-diagram-understanding` · `video-language` ·
`audio-language` · `any-to-any-generation` · `cross-modal-retrieval`

### robotics-embodiment
`manipulation` · `dexterous-manipulation` · `bimanual-manipulation` · `locomotion` ·
`whole-body-humanoid-control` · `navigation` · `mobile-manipulation` · `continuous-control` ·
`sim2real-transfer` · `cross-embodiment-transfer` · `human-robot-interaction` ·
`autonomous-driving-planning` · `drone-uav` · `embodied-instruction-following` · `tactile-sensing`

### physics
`simulation-surrogates` · `fluid-dynamics` · `particle-physics` · `astrophysics-cosmology` ·
`condensed-matter` · `quantum-systems` · `optics-photonics` · `symbolic-regression-discovery` ·
`plasma-fusion` · `physics-reasoning`

### chemistry-materials
`molecular-property-prediction` · `reaction-prediction` · `retrosynthesis` ·
`generative-molecular-design` · `catalysis` · `spectroscopy-interpretation` ·
`crystal-structure-prediction` · `crystal-stability-discovery` · `force-fields-potentials` ·
`drug-discovery-admet` · `experimental-hit-finding` · `lab-automation-protocols`

### biology-genetics
`protein-structure-prediction` · `nucleic-acid-structure` · `protein-function-prediction` ·
`protein-fitness-prediction` · `protein-design` · `protein-protein-interaction` ·
`protein-ligand-cofolding` · `genomics-variant-effect` · `regulatory-genomics` · `transcriptomics` ·
`single-cell-analysis` · `perturbation-response-prediction` · `drug-target-interaction` ·
`systems-biology` · `phylogenetics` · `bioinformatics-analysis` · `neuroscience-decoding` ·
`brain-model-alignment`

### medicine-health
`clinical-qa` · `clinical-dialogue` · `diagnosis-triage` · `medical-imaging-diagnostic` ·
`medical-imaging-segmentation` · `radiology-report-generation` · `ehr-prediction` ·
`clinical-agent-workflows` · `biomedical-literature` · `treatment-planning` · `medical-safety` ·
`mental-health`

### earth-climate
`weather-forecasting` · `climate-projection` · `remote-sensing` · `geospatial-reasoning` ·
`hazard-prediction` · `ecology-biodiversity` · `agriculture` · `energy-systems`

### games-planning
`board-games` · `card-imperfect-information` · `video-games` · `real-time-strategy` ·
`puzzle-games` · `open-ended-environments` · `procedural-generalization` · `game-theory` ·
`multi-agent-social`

### agents-tooluse
`web-navigation` · `computer-use-gui` · `tool-api-calling` · `multi-agent-coordination` ·
`long-horizon-autonomy` · `research-agents` · `software-agents` · `negotiation` ·
`operating-system-tasks` · `cybersecurity-offense-defense`

### safety-alignment
`harmlessness-refusal` · `agentic-harm` · `honesty-truthfulness` · `sycophancy` ·
`jailbreak-robustness` · `prompt-injection` · `bias-fairness` · `privacy-memorization` ·
`unlearning-knowledge-removal` · `dangerous-capability-evals` · `deception-scheming` ·
`evaluation-awareness` · `control-oversight` · `interpretability-probes` · `sandbagging` ·
`value-alignment`

### general-intelligence
`abstraction-generalization` · `novel-task-acquisition` · `human-comparison-batteries` ·
`meta-learning` · `open-ended-discovery` · `compositional-generalization` · `agi-composite-suites`

### society-econ-law
`economically-valuable-work` · `finance-forecasting` · `financial-analysis` ·
`trading-market-interaction` · `legal-reasoning` · `legal-document` · `economics-simulation` ·
`education-tutoring` · `policy-analysis` · `social-simulation` · `forecasting-prediction-markets`

### engineering-design
`cad-geometry-generation` · `circuit-eda` · `structural-mechanical-design` ·
`process-control-optimization` · `experimental-apparatus-design` · `lab-automation-execution`

### How the Domain facet is counted, and which number to quote

Domain is a two-level facet, so it has two legitimate sizes and the convention has to travel with
the number:

- **204 `(family, subdomain)` pairs.** This is the navigational spine and the row axis of the
  coverage matrix. A pair is a position a user can browse to and a row a gap claim can be made
  about.
- **204 distinct leaf slugs**, after D3.5's rename of `games-planning/puzzle-solving` to
  `games-planning/puzzle-games`. Before that rename there were 203, because one slug sat under two
  families; D3.5 exists to make the two counts equal so that nobody has to remember which one a
  given sentence means.

**Nineteen families, 204 subdomains.** Per-family subdomain counts, which sum to 204: language 11,
mathematics 7, code 9, reasoning-general 10, vision 16, audio-speech 10, multimodal 7,
robotics-embodiment 15, physics 10, chemistry-materials 12, biology-genetics 18, medicine-health 12,
earth-climate 8, games-planning 9, agents-tooluse 10, safety-alignment 16, general-intelligence 7,
society-econ-law 11, engineering-design 6.

The fine coverage grid is therefore **204 × 44 = 8,976 cells** — on pairs, which is the right
convention because `reasoning-general/puzzle-solving` and `games-planning/puzzle-games` are
different browse positions and a gap in one is not a gap in the other. On bare distinct slugs it is
the same 8,976 after the rename. The coarse grid, which is the only grid permitted to publish gap
claims, is 19 × 13 = 247 cells (§4.3, and
[12-analytics-and-trends.md](12-analytics-and-trends.md) for what is published from it).

### Domain changelog against the archive

The audit was run against the domain reconnaissance inventory of 13 domain families and roughly 200
named benchmarks, and against the 81 Epoch benchmarks whose domain mapping is already known
(recon:domains and recon:epoch-assets, both 2026-09-17).

| Change | Reason |
| --- | --- |
| **New family `engineering-design`** | CadEval (OpenSCAD generation scored by Chamfer/Hausdorff geometric tolerance), AutoLabs (natural language → executable liquid-handler protocol, F1 > 0.89 against expert procedures, *Sci Rep* 2026), Learn2Design 2026 (optimise the experimental design of gravitational-wave detectors), Smart Buildings Challenge (NeurIPS 2026) and the whole EDA/CAD cluster had no home (recon:domains, 2026-09-17). Filing them under `physics` or `code` is exactly the false-parent problem faceting exists to avoid. Risk: this family is thin at seed and will look weak. Accepted — an honestly thin family is a gap-matrix finding, and a family that does not exist is invisible. The Phase-0 scoping survey and the muting fallback in the floor rule below are what make that acceptance falsifiable. |
| **`chemistry` → `chemistry-materials`; `materials-science` removed from `physics`** | Matbench Discovery, Open Catalyst and OMol25 were classifiable two ways. The archive had `physics/materials-science` and `chemistry/crystal-structure-prediction` competing for the same entries. One home, named for both communities. |
| **Added `chemistry-materials/crystal-stability-discovery`** | Matbench Discovery is not crystal *structure* prediction (CCDC CSP Blind Test) — it is stability screening over the 256k-structure WBM test set with F1, energy MAE, phonons, κ_SRME and MD stability (recon:domains, 2026-09-17). Different task, different community, different metric family. |
| **Moved `drug-discovery-admet` from biology to chemistry-materials; added `experimental-hit-finding`** | TDC's 22 ADMET datasets are molecular property prediction. CACHE's prospective hit-finding — pick ≤100 compounds, organisers buy them from Enamine and assay them — is a distinct task with a wet-lab ground truth and no equivalent anywhere else in the vocabulary. |
| **Split `biology/protein-function-prediction` into `protein-function-prediction` + `protein-fitness-prediction`** | CAFA predicts GO terms and waits years for annotations to accrue. ProteinGym scores 200+ deep mutational scanning assays by Spearman ρ. Conflating them makes the biology row of the coverage matrix meaningless. |
| **Added `biology/nucleic-acid-structure`** | CASP16's nucleic-acid assessment (42 NA targets, 65 groups from 46 labs, base-pair and stacking-aware scores; recon:domains, 2026-09-17) and RNA-Puzzles are not protein structure prediction and are a declared CASP17 priority. |
| **Added `biology/perturbation-response-prediction`** | Virtual Cell Challenge 2026 (zero-shot CRISPRi knockdown response in six unseen cell lines) and Open Problems OP3 (146 compounds) were falling into the catch-all `single-cell-analysis`. |
| **Added `biology/brain-model-alignment`, kept `neuroscience-decoding`** | Brain-Score (ceiling-normalised model-to-brain similarity on primate V1/V2/V4/IT) and Algonauts (Pearson r on held-out fMRI) measure alignment; FALCON measures decoding. Opposite directions. |
| **Added `biology/bioinformatics-analysis`** | BixBench (53 real analysis scenarios requiring multi-step Jupyter execution) and LAB-Bench/LABBench2 (2,457 questions across 8 categories of practical research work; recon:domains, 2026-09-17). Secondary tag `agents-tooluse/research-agents`. |
| **`biology/phylogenetics` kept although empty** | The domain recon found no standing phylogenetics benchmark; comparisons are simulation-based and per-paper. The term stays precisely so the gap matrix can show the hole, and it is declared as a gap-matrix placeholder in `taxonomy/domains.yaml` rather than left as an accident (see the empty-subdomain rule below). A vocabulary that only contains terms with entries cannot express absence, which is the project's headline output. |
| **Split driving: `robotics/autonomous-driving` → `autonomous-driving-planning`; new `vision/driving-perception-3d`** | nuScenes NDS and CARLA Driving Score (route completion × infraction penalty) share the word "driving" and nothing else. CARLA Leaderboard 2.0 SOTA was ≈6% success on secret routes as of 2026-09-17 (recon:domains); nuScenes detection is a mature perception metric. One subdomain containing both destroys any saturation reading. |
| **Added `robotics/whole-body-humanoid-control`, `bimanual-manipulation`, `cross-embodiment-transfer`, `continuous-control`** | HumanoidBench (27–31 whole-body tasks, Unitree H1 + Shadow Hands); RoboTwin 2.0 (50 tasks × 5 embodiments, 731 objects); Open X-Embodiment / AnyBody; MuJoCo-Gymnasium continuous control, which had no home at all and is one of the oldest live benchmark families in the field (all recon:domains, 2026-09-17). |
| **Added `physics/physics-reasoning`; removed `materials-science`** | CritPt (71 research-level challenges written by 50+ active researchers, ≈40 h review each, best base model ≈4%; recon:domains, 2026-09-17) and QuantiPhy are physics *reasoning* evaluated on language models, not simulation surrogates. |
| **Added vision `novel-view-synthesis`, `multi-view-stereo`, `image-matching-correspondence`, `image-restoration-enhancement`** | ScanNet++ and 3DReflecNet (NVS); DTU / Tanks and Temples / ETH3D (MVS with hidden ground truth); the CVPR Image Matching Challenge and RoCo-Spring; and NTIRE, which alone emits roughly 20 restoration tracks per year (recon:domains, 2026-09-17). The archive had a single `3d-reconstruction` term absorbing four distinct literatures. |
| **Added audio `audio-event-detection-localization`, `machine-condition-monitoring`, `bioacoustics`** | DCASE 2026 is seven unrelated tasks under one name, including noise-aware unsupervised anomalous sound detection for machine condition monitoring and semantic acoustic imaging for SELD. BirdCLEF+ is bioacoustics with an ecology secondary. |
| **Added medicine `clinical-dialogue`, `medical-imaging-segmentation`, `radiology-report-generation`, `clinical-agent-workflows`** | HealthBench (5,000 multi-turn conversations, 48,562 physician-authored rubric criteria, built with 262 board-certified physicians; recon:domains, 2026-09-17) is not `clinical-qa`. BraTS 2026 is a cluster of five segmentation challenges with lesion-wise Dice/HD95. ReXrank reports 8 report-generation metrics and deliberately publishes no aggregate. MedAgentBench v2 (300 physician-written tasks against a FHIR EHR with 700,000+ data elements; arXiv 2501.14654, *NEJM AI*), AgentClinic and ClinEnv are stateful agent environments. |
| **Added `earth-climate/energy-systems`** | Smart Buildings Challenge (NeurIPS 2026) is real-world building energy optimisation — a control task, not a prediction task. |
| **Added `society-econ-law/economically-valuable-work` and `trading-market-interaction`** | GDPval (1,320 tasks, 44 occupations, top 9 US GDP sectors, blinded expert pairwise grading; arXiv 2510.04374) and the Remote Labor Index had no term. BizFinBench.v2's "online" tasks run against live market platforms. |
| **Added `code/code-performance-optimization`** | GSO-Bench and AlgoTune measure speedup, not correctness. Different ceiling, different headroom behaviour (unbounded). |
| **Added safety `agentic-harm`, `evaluation-awareness`, `unlearning-knowledge-removal`** | AgentHarm scores task *completion* across 11 harm categories rather than output toxicity; OS-Harm does the same for computer-use agents. Evaluation awareness is a 2026 measurement category (Apollo Research reported the highest evaluation-awareness rate they had seen for a model referred to as "Muse Spark" — vendor identity *(unverified — confirm before relying on this)*; LURE is explicitly designed not to look like a benchmark). WMDP doubles as an unlearning benchmark where lower is safer. |
| **`games-planning/puzzle-solving` → `games-planning/puzzle-games`** | The slug appeared under both `reasoning-general` and `games-planning`, which generates two identically-labelled options in the same generated dropdown and splits one coverage row into two thin ones — the failure the capability facet already fixed by merging `ood-generalization` and `distribution-shift-robustness`. The discriminant is the protocol, not the topic: a posed problem with a submitted answer is `reasoning-general/puzzle-solving`; an interactive episode against a responding environment is `games-planning/puzzle-games`. Both homes stay populated — Epoch's `chess_puzzles` and `mystery_game_puzzles` are one of each. See `_workflow/decisions/D3-vocabulary-namespacing.md`. |
| **Rejected: a `robot-competition` subdomain** | RoboCup and the A2RL Drone Championship are physical competitions, but "physical competition" is already expressed by `evaluation_method: physical-trial` and `submission_process: physical-competition`. Adding it to Domain would duplicate two other facets and blur the robotics row. This is the discipline that keeps the spine navigational rather than descriptive. |

### Curation targets per family

**This table is the canonical seed allocation for the whole plan.** Its "Seed target" column sums to
**320**, that is the seed total, and no other document restates the per-family numbers — they link
here. The Tier-1/Tier-2/Ceiling columns are the domain recon's estimates, grounded in what was found
on 2026-09-17, not measured counts; the Seed target column is our allocation, adjusted down from the
estimates by the non-duplication doctrine in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10. "Families" means the
counting convention defined in §11 — DCASE is one family with seven children, not seven benchmarks.
The table is generated from `taxonomy/domains.yaml` by `scripts/taxonomy_stats.py` and checked in CI
([05-repository-and-workflow.md](05-repository-and-workflow.md) §9, check 9f); do not hand-edit the
numbers without editing the YAML.

| Family | Tier-1 (field-defining) | Tier-2 (worth an entry) | Ceiling | Seed target | Core? | Posture, and the curation difficulty that sets it |
| --- | --- | --- | --- | --- | --- | --- |
| robotics-embodiment | 25 | 120 | ~400 | **25** | **Y** | Hand-curate. Very high — no central hub exists anywhere, and the simulator build version dominates the result |
| biology-genetics | 30 | 150 | ~450 | **25** | **Y** | Hand-curate. Very high — CASP/CAFA/CAGI decompose into 100+ children, so the family/child convention lives or dies here |
| vision | 35 | 250 | ~1,000+ | **22** | N | Hand-curate, **capped**. Highest long tail in the project: CVPR/ICCV/ECCV emit 50–100 tracks a year. Cap deliberately or it eats the project |
| medicine-health | 25 | 200 | ~700+ | **20** | **Y** | **Mixed.** Grand Challenge's public API carries discovery; facets and Tier-1 entries are hand-curated. Highest raw volume; 264 challenges on grand-challenge.org alone. Cap at families |
| chemistry-materials | 25 | 110 | ~300 | **20** | **Y** | Hand-curate. High — wet-lab and DFT level-of-theory conditions must be captured |
| agents-tooluse | 30 | 120 | ~400 | **20** | N | Mixed. Fastest-growing and most harness-sensitive; Epoch and Benchmark Radar cover part, the harness sensitivity is ours |
| physics | 20 | 70 | ~200 | **18** | **Y** | Hand-curate. High — fragmented by subfield, almost no shared vocabulary |
| earth-climate | 20 | 80 | ~250 | **18** | **Y** | Hand-curate. Medium-high — needs lead-time and spatial-resolution fields |
| audio-speech | 18 | 70 | ~200 | **18** | **Y** | Hand-curate. Medium — DCASE alone is 7 tasks × ~12 years |
| safety-alignment | 25 | 120 | ~350 | **18** | N | Mixed. High — Inspect Evals implements 100+; many private by design, recorded as entries with `access: private` |
| code | not estimated ‡ | — | — | **16** | N | Ingest-then-verify. Epoch, EEE and SWE-bench's own JSON carry the numbers; we add lineage and scaffold conditions |
| language | not estimated ‡ | — | — | **14** | N | Ingest-then-verify. The single most duplicated area in the landscape — catalogue richly, curate claims almost not at all |
| society-econ-law | 20 | 90 | ~250 | **14** | N | Mixed. Medium — many private/commercial test sets |
| games-planning | 15 | 60 | ~150 | **12** | N | Ingest-then-verify. Elo and unbounded metrics need special handling more than they need volume |
| general-intelligence | 12 | 30 | ~60 | **12** † | N | Ingest-then-verify. Low volume, high scrutiny |
| multimodal | not estimated ‡ | — | — | **12** | N | Hand-curate. Overlaps vision; keep the boundary rule in §11 |
| mathematics | not estimated ‡ | — | — | **12** | N | Ingest-then-verify. FrontierMath's four variants make the lineage case better than the volume case |
| reasoning-general | not estimated ‡ | — | — | **12** | N | Ingest-then-verify. Same |
| engineering-design | not estimated ‡ *(unverified — confirm before relying on this)* | — | — | **12** § | N | Hand-curate. Unknown difficulty; the recon never surveyed it as a family. Phase-0 scoping survey required before curation starts |
| **Total** | **300 across 13 estimated rows** | **~1,470** | **4,710** | **320** | **144 in Core** | |

† **general-intelligence is the only row targeting 100% of its Tier-1 estimate**, deliberately: the
recon puts the whole field at twelve field-defining families (ARC-AGI's three generations, HLE,
GPQA, SimpleBench, BIG-bench's remnant, MMLU-Pro and a handful more). It is the one domain small
enough to sweep completely, and sweeping it completely is cheap and demonstrates the counting
convention works. Nowhere else should a target equal its estimate.

‡ **not estimated.** The domain recon's count table covers **thirteen** families totalling ~300
Tier-1 and does not size code, language, mathematics, reasoning-general, multimodal or
engineering-design at all. Those six rows (78 entries) are **our own estimates and are weaker than
the other thirteen**. Say so when quoting the total: 320 is *242 of the recon's 300 estimated Tier-1
families across thirteen domains (81%), plus 78 entries across six domains nobody has sized.* Sizing
those six is a Phase 0 task, not a Phase 5 one, because it is the only part of the allocation with
no external grounding.

§ **engineering-design carries the highest miss risk of any row.** The recon named four candidates
(CadEval, AutoLabs, Learn2Design 2026, Blueprint-Bench 2) and asserted an EDA/CAD cluster it never
enumerated. If the Phase-0 scoping survey finds fewer than twelve credible Tier-1 families, the
family ships **muted** under the floor rule below rather than padded to twelve.

**The floor rule.** Three numbers, three jobs, and they are not interchangeable:

1. **Hard floor, 12 entries, blocking at launch.** No family ships below twelve. Below twelve the
   row cannot support a gap claim: an empty cell is indistinguishable from a cell nobody looked at,
   and unfalsifiable gap claims are the one failure that would discredit differentiator 3.
2. **Core floor, 18 entries, blocking at launch, no exemption.** The seven Core families —
   robotics-embodiment, biology-genetics, chemistry-materials, medicine-health, physics,
   earth-climate, audio-speech — are the product. A specialist scanning their own field with
   eighteen entries says "yes, you got my field right"; with six they close the tab.
3. **Credibility target, 15 entries, every family, by v1.x.** This is what the recon's "below
   roughly fifteen a specialist spots the gaps immediately" actually measures: the point at which a
   reviewer stops finding holes. It is an aspiration with a ratchet (no family goes backwards), not
   a launch gate, and calling it a floor is what produced two contradictory floors in the first
   place. Six families launch at 12–14 and are below it; that is accepted, because every one of
   them is an ingest-then-verify family where a competitor already holds the ground and specialist
   credibility is not what the row is for.

**The muting exemption, and it is the only one.** A family that cannot reach its floor ships with
`coverage_status: under-surveyed` in `taxonomy/domains.yaml`, a visible badge on every entry in it,
that status shown in the coverage map, and **the Gap Finder refusing to assert any gap in that
row**. This is the same mechanism [14-roadmap.md](14-roadmap.md) already defines for unreviewed
domains, and it exists because the honest response to a thin family is disclosure, not padding —
padding trades a visible gap for an invisible quality failure, which is the worse trade. Muting is
not available to the seven Core families: a muted Core family means the project has lost its
differentiator and should re-plan, not badge.

**The effort this buys.** At the planning rate of 30–90 minutes per fully sourced entry — an
estimate from the domain reconnaissance, never a measurement, owned by
[14-roadmap.md](14-roadmap.md) §"Effort sizing" — and 2–3 hours for the ten stress cases, 320
entries is **175–495 person-hours** — one
part-time person for roughly nine to twenty-five weeks at 20 h/week, and that single line is
half the project. The non-LLM differentiating core (robotics, chemistry-materials, biology,
earth-climate, physics) is about **120 Tier-1 families** by the recon's estimate and **106 by this
allocation**; the seven-family Core set above is 163 estimated and 144 targeted. Both figures are
in circulation — say which set you mean.

That range covers entry curation only. The vocabulary-definition pass that has to happen alongside it
is sized separately at the end of §14, because it is work D2's range does not include and no phase
in [14-roadmap.md](14-roadmap.md) currently carries.

### The browse spine is mostly empty at launch, and that has to be designed for

Rule 6 in §11 gets the coverage *matrix* right: three cell states, and `surveyed-and-empty` requires
a dated survey note. The Domain facet needs the same treatment and the archive gave it none, which
is a real gap because Domain is the navigational spine and a subdomain page is the first thing a
specialist clicks.

The arithmetic. **320 seed entries over 204 `(family, subdomain)` pairs is a mean of 1.57 primary
entries per subdomain**, and the distribution will be far worse than the mean because benchmark
attention is concentrated. The thinnest rows by construction are safety-alignment (18 entries over
16 subdomains, 1.13), reasoning-general (12 over 10, 1.20), language and society-econ-law (14 over
11, 1.27), games-planning (12 over 9, 1.33) and vision (22 over 16, 1.38); the fattest are
earth-climate (18 over 8, 2.25), agents-tooluse (20 over 10, 2.00) and engineering-design (12 over
6, 2.00). Under a Poisson null at λ = 1.57, 21% of subdomain pages — about 43 of 204 — would be
empty even with perfectly even curation; the true figure will be higher, and 40–50% is the working
estimate *(derived from an assumed concentration, not measured — confirm against the seed corpus at
the 100-entry checkpoint)*. A specialist clicking `biology-genetics/phylogenetics`, which the
changelog above says is deliberately empty, or `vision/multi-view-stereo`, which is not, must not
get the same blank page. **A blank browse page reads as an abandoned site, not as a finding**, and
that misreading is exactly what killed the credibility of every catalogue in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §2 while it was still technically
online.

Three rules follow, and they are cheap:

1. **A subdomain page with zero entries renders the same three states the coverage matrix does.**
   `not-yet-surveyed` is the default and says so plainly ("no benchmark filed here yet; we have not
   surveyed this subdomain"). `surveyed-and-empty` requires a dated survey note in
   `taxonomy/domains.yaml` and renders it verbatim, which turns the empty page into the project's
   most distinctive output. There is no third rendering and no silent blank.
2. **Subdomain pages list secondary-domain entries as well as primary**, visually separated and
   labelled, with the weighting rule in §11 rule 1 stated on the page. This is the single largest
   reduction in apparent emptiness available and it costs nothing, because the secondaries are
   already tagged. It is also the honest thing to show: a reader browsing
   `earth-climate/geospatial-reasoning` wants GeoBench even though GeoBench's primary is vision.
3. **A subdomain still at zero entries at the v1.0.0 freeze is a decision, never an omission.** It
   is either merged into a sibling by ADR, or explicitly declared a gap-matrix placeholder in
   `taxonomy/domains.yaml` with the survey note that justifies it — which is what
   `biology-genetics/phylogenetics` already is. CI check 9b lists the zero-entry subdomains at every
   build; the freeze gate is that the list is empty of *undeclared* ones.

---
## 4. Facet 2 — Capability

What underlying ability the benchmark is trying to isolate. Orthogonal to Domain —
`causal-reasoning` appears in chemistry, economics and medicine. This facet crossed with Domain
produces the coverage matrix, which is why the terms must stay stable and mutually distinguishable.
An overlapping pair does not just add noise to two rows; it makes every gap claim in those rows
unfalsifiable.

### 4.1 The terms

**Forty-four terms.**

`knowledge-recall` · `factual-precision` · `deductive-reasoning` · `inductive-reasoning` ·
`abductive-reasoning` · `causal-reasoning` · `analogical-reasoning` · `abstraction` ·
`quantitative-reasoning` · `spatial-reasoning` · `temporal-reasoning` · `perception` ·
`sensorimotor-control` · `grounding` · `planning` · `long-horizon-execution` · `search-exploration` ·
`optimization` · `experimental-design` · `hypothesis-generation` · `generation-fidelity` ·
`creativity-novelty` · `instruction-following` · `constraint-satisfaction` · `tool-use` ·
`memory-retention` · `context-integration` · `sample-efficiency` · `continual-learning` ·
`distribution-shift-generalization` · `compositional-generalization` · `transfer-learning` ·
`adversarial-robustness` · `calibration-uncertainty` · `probabilistic-forecasting` ·
`reliability-consistency` · `self-correction` · `collaboration` · `communication` ·
`situational-awareness` · `honesty` · `harm-avoidance` · `autonomy` · `self-improvement`

**Four capability terms share a word with a subdomain leaf**: `planning`, `spatial-reasoning`,
`temporal-reasoning` and `compositional-generalization`. This is permitted and expected — the facet
is orthogonal to Domain, so the same concept is correctly named on both axes — but each pair is
declared in `taxonomy/homographs.yaml` with a rationale, and CI check 9d fails on an undeclared one.
The consequence for the coverage matrix is that the four fine-grid cells whose row and column carry
the same word are **occupied by construction**: full reports the tagging convention, empty reports
that the row is empty, and neither can produce a gap finding. This is the **tautological diagonal**,
and it is the reason the pairs are marked rather than tolerated silently — the brightest square in
the reasoning row would otherwise sit on it, and a specialist who clicks in, sees that, and
concludes the matrix is an artefact of naming would be right about that square. Check 9e marks them
and the fine-grid view excludes them from gap ranking. Four cells of 8,976, and none at all in the
coarse grid, which is the only grid that publishes gap claims. See D3.

### 4.2 Disambiguation notes for the terms most likely to blur

These go in `taxonomy/capabilities.yaml` as the `definition` field and are published on the site. A
taxonomy nobody can read is a taxonomy nobody can apply consistently.

- **`abstraction`** — deriving a rule or representation that is not present in the surface form of
  the input (ARC-AGI). **`inductive-reasoning`** — generalising a rule from a finite set of observed
  examples, where the examples are the evidence (SRBench symbolic regression, LLM-SRBench).
  **`compositional-generalization`** — recombining known primitives in unseen configurations
  (Procgen, Craftax). The test: if the benchmark's novelty is in the *representation*, it is
  abstraction; if it is in the *quantity of evidence*, it is induction; if it is in the
  *arrangement*, it is compositional.
- **`perception`** — extracting structure from a raw sensory signal (COCO AP, ScanNet++ mIoU, Open
  ASR WER). **`grounding`** — binding symbols to referents in a perceived or simulated world
  (visual grounding, embodied instruction following). Perception without language is not grounding.
- **`reliability-consistency`** — succeeding on the *same* task across repeated independent trials.
  τ-bench's `pass^k` (fraction of tasks solved in **all** k trials) is the canonical case, and
  averaging destroys it. Distinct from `adversarial-robustness` (holding up under attack) and from
  `distribution-shift-generalization` (holding up under changed inputs).
- **`calibration-uncertainty`** — the system's stated confidence matches its accuracy (HLE's
  calibration error, the FAIR Universe HiggsML interval-coverage metric).
  **`probabilistic-forecasting`** — producing a probability for a future event whose truth value does
  not yet exist (ForecastBench Brier score, Metaculus FutureEval). A well-calibrated system is not
  necessarily a good forecaster and vice versa.
- **`sensorimotor-control`** — closed-loop control of a physical or simulated body. This is the
  capability the archive vocabulary was missing entirely, which meant the entire robotics row of the
  coverage matrix had no column to land in.
- **`instruction-following`** versus **`constraint-satisfaction`** — this seam crosses two capability
  groups (§4.3) and the archive carried no note for it, which D1 flagged as a gap in the fine
  vocabulary the rollup cannot close. Tie-break, derived from §11 rule 2: **tag the term the
  benchmark's own source claims.** IFEval claims instruction-following; PoseBusters' physical
  validity battery and τ-bench's policy compliance claim constraint-satisfaction. Both columns are
  dense, so drift moves mass without destroying a gap claim, but per-term F1 for both must be
  watched in the first inter-rater run.
- **`situational-awareness`** — in this taxonomy this means **evaluation awareness and sandbagging**,
  not an agent's awareness of its own state. The plain-English reading points at
  `context-integration`, so a curator who has not read the definition mis-tags it into the
  frontier-risk column, which is the one that attracts the most external scrutiny. Grouping cannot
  repair a misleading slug: **rename by ADR before the v1.0.0 freeze** (D1 risk 10).

### 4.3 Capability groups — the coarse axis

Settled by **D1**, 2026-09-21. **This section is the canonical enumeration**; every other document
refers to it rather than restating the member lists.

**Thirteen capability groups**, a strict partition of all 44 capability terms, each term in exactly
one group. The coarse coverage grid is therefore **19 domain families × 13 capability groups = 247
cells**, against the fine grid's 204 × 44 = 8,976. The coarse grid is the only grid permitted to
publish gap claims ([12-analytics-and-trends.md](12-analytics-and-trends.md)); the fine grid is
exploration-only behind a null-model banner.

**The group axis is derived and never hand-tagged.** Curators tag terms; the rollup is computed at
build time. Nothing in `data/` ever references a group id. Two consequences follow directly: the
≥0.85 raw-agreement bar in [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §6 does not
apply to groups, because groups are not tagged and therefore cannot be disagreed about; and
re-grouping triggers no retro-tag pass, but it does silently re-shape every published gap claim in
the affected columns with no change to any benchmark record — which is why
`capability_groups.yaml` is versioned, its version is recorded in `build/derived/manifest.json`, and
moving a term between groups requires an ADR (§11 rule 9).

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

#### Definitions

**`knowledge-and-memory` — Knowledge & memory**
Isolates whether the information a task needs is available and correctly held at the moment of use,
whether it sits in the system's parameters or is supplied in its context.

**`formal-quantitative-reasoning` — Formal & quantitative**
Isolates conclusions that follow necessarily from stated rules, numbers or constraints and are
checkable against them — proof, calculation and constraint compliance rather than explanation.

**`abstraction-and-analogy` — Abstraction & analogy**
Isolates rules and representations not present in the surface form of the input: abstraction of a
representation, induction of a rule from examples, analogical mapping, and recombination of known
primitives in unseen arrangements.

**`causal-and-experimental-inference` — Causal & experimental**
Isolates reasoning about why something happened and what would happen under intervention: abduction
to the best explanation, causal inference, generation of candidate hypotheses, and design of the
experiment that would discriminate between them.

**`perception-space-time` — Signal, space & time**
Isolates extracting structure from a raw sensory or simulated signal and situating it among
referents, locations and instants, in perceived and in described worlds alike.

**`planning-and-search` — Planning & search**
Isolates production of a solution over a space of options against an objective — plan construction,
exploration of the option space, and optimisation — where the score is a property of the solution
rather than of a rollout.

**`action-and-execution` — Action & execution**
Isolates closed-loop acting on an external environment over time: motor control of a physical or
simulated body, invocation of external tools and APIs, and execution sustained across many steps,
scored by what the run achieved.

**`controlled-generation` — Controlled generation**
Isolates production of an open-ended artefact against an externally specified target — a reference, a
rubric or a stated instruction — where the score is a judgement about the artefact rather than a
discrete decision.

**`conduct-and-cooperation` — Conduct & cooperation**
Isolates how the system behaves toward other parties when behaviour rather than accuracy is what is
scored: cooperation with another agent or human, informativeness toward a recipient, truthfulness,
and refusal to cause harm.

**`learning-and-transfer` — Learning & transfer**
Isolates change in performance as a function of experience — how much data is needed, whether
learning accumulates across episodes without forgetting, and whether it carries to a new task or
embodiment — measured as a difference or a slope, never as a single score.

**`robustness-and-stability` — Shift & robustness**
Isolates retention of performance when the evaluation condition changes rather than whether it is
achievable once: under shifted inputs, under deliberate attack, and under nothing but repetition of
the identical task.

**`uncertainty-and-self-monitoring` — Uncertainty handling**
Isolates the quality of stated uncertainty and error detection rather than of the point estimate:
confidence that matches accuracy, probability assigned to events whose truth value does not yet
exist, and revision of an output once evidence indicates it is wrong.

**`autonomy-and-oversight` — Autonomy & oversight**
Isolates capacity and propensity to operate, persist or improve outside direct supervision,
including recognising that it is being evaluated and behaving differently because of it.

```yaml
# taxonomy/capability_groups.yaml
# A partition of taxonomy/capabilities.yaml. CI asserts every capability term appears
# in exactly one group. Moving a term between groups requires an ADR (§11 rule 9),
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

#### Why thirteen, and what it costs

Thirteen is the largest count at which every column is a construct a specialist would accept, no
column is a grab-bag, and all four gap claims the plan has already committed to publishing stay
expressible on the coarse axis. The 3-member floor caps the count at 14 (44 / 3 = 14.67); 13 is 14
minus the one split D1 refused — separating `knowledge-recall` + `factual-precision` from
`memory-retention` + `context-integration`, rejected because it yields two 2-member columns that
read as curation artefacts at seed rather than as findings. Neither 12 (a number nobody had derived)
nor 8 (a HELM-shaped default) was adopted; the 8-column grid's failure is not unreadability but that
its gap output falls to near zero exactly when the corpus becomes good enough to support gap claims.
D1 carries the density argument in full, including the structural-zero-rate assumption it rests on,
which is explicitly marked unverified there.

Three costs are accepted rather than solved, and they belong here because they shape what the
coverage map may claim:

- **`action-and-execution` is fillable by `tool-use` in every agent-adjacent row**, so "closed-loop
  physical control is measured only in robotics" is not expressible on the coarse axis. This partly
  undoes the reason §4.4 added `sensorimotor-control` at all. The remedy is a named, ADR-approved
  allow-list of publishable fine cells; without it, accept the loss and say so on the methodology
  page.
- **`conduct-and-cooperation` is fillable by `communication`**, whose base rate is carried by four
  subdomains (`language/dialogue`, `medicine-health/clinical-dialogue`, `agents-tooluse/negotiation`,
  `robotics-embodiment/human-robot-interaction`), so honesty and harm-avoidance gaps are masked in
  four families. **Cell tooltips must therefore decompose by member term rather than reporting the
  group total.** The same applies to `perception-space-time`, where textual spatial or temporal
  benchmarks will make a family look perceptually covered when it is not.
- **`robustness-and-stability` carries `distribution-shift-generalization`**, the most-applied term
  in the corpus, which makes it a floor column: dense in nearly every row, producing almost no gap
  claims, and burying `adversarial-robustness` and `reliability-consistency` behind a term with
  several times their base rate. D1 kept §4.2's shift/attack/repetition triad intact over splitting
  it, and names this as the most contestable decision in the partition; **re-examine by ADR once
  ~200 entries are tagged and real co-occurrence is visible.**

One hard dependency, flagged because it is not optional: the **mandatory not-applicable triage** in
[03-taxonomy-build-process.md](03-taxonomy-build-process.md) and
[10-visualization.md](10-visualization.md). Without it, `autonomy-and-oversight` and
`conduct-and-cooperation` manufacture roughly twenty false gaps on day one across physics,
chemistry-materials, biology-genetics, earth-climate and engineering-design — the rows a specialist
reviewer checks first. The triage is not a blanket: autonomous laboratories make
chemistry-materials × `autonomy-and-oversight` a live and informative cell, and declaring it
inapplicable would itself be an error.

### 4.4 Capability changelog against the archive

| Change | Reason |
| --- | --- |
| **Merged `ood-generalization` + `distribution-shift-robustness` → `distribution-shift-generalization`** | These were the same concept under two names. Two terms for one idea splits the evidence for a cell across two columns and makes both look thinner than reality. The clearest blur in the archive list. |
| **Retired `efficiency-compute` and `efficiency-latency`** | These are not abilities a benchmark isolates; they are axes a benchmark *reports alongside* its score. The Open ASR Leaderboard publishes WER and RTFx together (so a score without hardware is meaningless), BFCL v4 reports cost and latency, AstaBench is cost-adjusted, and Princeton's HAL reports accuracy-versus-cost Pareto fronts (recon:domains, 2026-09-17). Tagging these as capabilities would eventually attach them to every agentic benchmark and flatten the column. **Replaced by a benchmark-level field `secondary_axes: [cost, latency, throughput, energy, reliability]`** — see [04-data-model.md](04-data-model.md). |
| **Added `sensorimotor-control`** | No capability term covered physical or simulated control. LIBERO, HumanoidBench, RoboCasa, Bench2Drive and every MuJoCo task had nothing to tag. |
| **Added `reliability-consistency`** | τ-bench/τ²-bench `pass^k`. Also the honest column for Terminal-Bench-style harness variance and for AILuminate-style repeated sampling. |
| **Added `continual-learning`** | DCASE 2026 task 7 (domain-agnostic incremental learning); LIBERO's lifelong-learning suites; Epoch's Earthborne Rangers, where the result is a slope across repeated playthroughs rather than a point. |
| **Added `probabilistic-forecasting`** | ForecastBench, Metaculus FutureEval, BTF-3. Distinct from calibration, as above. |
| **Added `experimental-design` and `hypothesis-generation`** | Learn2Design 2026 (the submission is a designed detector, scored by simulation), CACHE (choose which 100 compounds to have assayed), AutoLabs (author an executable protocol), RealPDEBench sim-to-real. The submission is an experiment, not a prediction, and nothing in the archive list expressed that. |
| **Added `situational-awareness`** | Apollo Research's evaluation-awareness and sandbagging suite; LURE. A measured behaviour in 2026 with no column. Slug flagged for rename by ADR before freeze (§4.2). |
| **Removed a duplicate printing of `causal-reasoning`** | The archive list printed it twice — 45 listings, 44 distinct terms. The "forty-four terms" claim is correct only after the dedup (D1 edit 2). |
| **Added the 13-group rollup (§4.3)** | The coarse axis of the coverage matrix was cited by two documents and existed in neither. D1. |
| **Net: 40 → 44 terms** | Three retired or merged away, seven added. |

---
## 5. Facet 3 — Evaluation method

*How the score is produced.* The single most important facet for transparency: it tells a reader how
much weight a number deserves before they look at the number. A benchmark may carry several. Where a
benchmark has multiple tracks with materially different methods, model them as subsets rather than
flattening ([04-data-model.md](04-data-model.md)).

**Twenty-seven terms.**

| Term | Notes |
| --- | --- |
| `exact-match` | String or value equality against a reference |
| `symbolic-equivalence` | Computer-algebra equivalence, not string equality. SRBench's symbolic solution rate; FrontierMath Erdős requires Lean-verified solutions |
| `multiple-choice` | Selection among options; record the chance baseline — it is the headroom floor |
| `execution-tests` | Code run against unit tests. Verifiable, low ambiguity (SWE-bench fail-to-pass + pass-to-pass) |
| `formal-proof-check` | Machine-checked proof (Lean, Coq, Isabelle). Highest verifiability available |
| `constraint-check` | Programmatic validation of structured output. PoseBusters is the archetype: a pass/fail physical-plausibility battery routinely *composed* with another benchmark's metric |
| `simulation-rollout` | Success rate in a simulator. Record the simulator and build — BEHAVIOR's score is only defined inside a specific OmniGibson/Isaac-Sim build |
| `episodic-return` | Unbounded cumulative reward from a control episode (MuJoCo, Gymnasium, NetHack in-game score). **Headroom is undefined; these can never be marked saturated** |
| `physical-trial` | Real hardware trials. High variance, low reproducibility (A2RL lap times, RoboCup, RoboTwin's AgileX hardware track) |
| `wet-lab-validation` | Experimental validation of predictions (CACHE hit rates from real binding assays, OCx24) |
| `reference-metric` | BLEU, ROUGE, COMET, perplexity and relatives |
| `domain-metric` | GDT-TS, lDDT, DockQ, mAP, FID, CRPS, IoU, κ_SRME. Defined per `Metric` entity |
| `model-derived-metric` | The score is computed *by another model* — a detector, a CLIP-family encoder, a fine-tuned classifier. GenEval, T2I-CompBench, HarmBench's classifier, RadGraph-F1. **The scoring model's version is part of the result** |
| `statistical-fit` | Error against ground-truth measurements (RMSE, ACC, Spearman ρ) |
| `uncertainty-calibration-score` | The metric is a calibration functional, not accuracy. FAIR Universe HiggsML scores confidence-interval coverage and width under systematic nuisance parameters |
| `human-distribution-percentile` | Scored against a real human population distribution. MLE-bench's bronze/silver/gold medal thresholds come from the actual Kaggle leaderboards |
| `human-expert-eval` | Domain experts rating individual outputs |
| `human-crowd-eval` | Non-expert raters (MineRL BASALT, TTS listening tests) |
| `expert-panel-assessment` | An assessor committee producing a published judgement rather than a leaderboard. CASP's output is peer-reviewed assessment papers; CACHE includes a medicinal-chemistry panel's qualitative commentary |
| `rubric-graded` | A structured rubric aggregated into a score. HealthBench's 48,562 physician-authored criteria; PaperBench's ~8,316-leaf hierarchical rubric (both recon:domains, 2026-09-17; PaperBench arXiv 2504.01848). **Record the grader separately** — it may be human or model |
| `model-graded-judge` | A judge model issues a verdict. Judge model and version are required fields ([04-data-model.md](04-data-model.md)) |
| `pairwise-preference-elo` | Arena-style rating from A/B comparisons. Rating-pool identity and snapshot date are part of the result |
| `tournament-play` | Relative strength through play against other entrants. Kaggle Game Arena's all-play-all (40 games per pair, 20 as each colour); RoboCup placement |
| `adversarial-red-team` | Human or automated attack-success rate. The denominator moves — JailbreakBench scores drop when someone publishes a new attack, with no change to the model |
| `ordinal-grading` | The result is a grade, not a number. AILuminate's Poor / Fair / Good / Very Good / Excellent, where "Good" is defined *relative to the current state of the art* — which is why §8 sets `headroom: null` for it |
| `prospective-resolution` | Ground truth does not exist at submission and resolves later. ForecastBench, Metaculus, CAFA (annotations accrue for years). Pairs with `resolution_status` on the claim |
| `composite` | Aggregate of sub-benchmarks using different methods. NAVSIM's EPDMS is a weighted product of ~10 sub-criteria; COCO AP averages over IoU .50:.05:.95 |

### Evaluation-method changelog against the archive

Nine terms added, one renamed. Each addition traces to a specific benchmark the archive vocabulary
could not express:

| Added | Forced by |
| --- | --- |
| `symbolic-equivalence` | SRBench's symbolic solution rate — "correct" is CAS equivalence, not a number |
| `episodic-return` | MuJoCo/Gymnasium/Atari, where the metric is unbounded and headroom is undefined |
| `uncertainty-calibration-score` | FAIR Universe HiggsML — the metric is interval coverage and width |
| `human-distribution-percentile` | MLE-bench medal rates against real Kaggle leaderboards |
| `expert-panel-assessment` | CASP (assessment papers, no leaderboard) and CACHE (expert commentary) |
| `rubric-graded` | HealthBench and PaperBench. `model-graded-judge` alone loses the rubric structure |
| `ordinal-grading` | MLCommons AILuminate letter grades, relative to a moving state of the art |
| `prospective-resolution` | ForecastBench and CAFA — a published score is provisional until resolution |
| `model-derived-metric` | GenEval / T2I-CompBench / HarmBench — a scoring *model* that is not a judge |
| **Renamed** `tournament-selfplay` → `tournament-play` | Kaggle Game Arena is model-versus-model across a pool, not self-play. The archive term excluded the most prominent 2026 case |

**Scoring modes deliberately *not* added, and where they live instead.** Tournament ladders and
multi-year challenge rounds are a `refresh` value (`periodic-recompetition`), not a method. Two-axis
results with no legitimate scalar — AgentDojo's utility × targeted-attack-success-rate, BBQ's
`s_AMB`/`s_DIS` where the optimum is zero, VBench's 16-dimension vector, ReXrank's eight metrics with
no published aggregate — are a `Metric` and reporting concern: the benchmark carries multiple
`Metric` refs and a flag `no_legitimate_aggregate: true`, and the UI renders a vector. Ceiling
normalisation against a biological replicate or a neural noise ceiling is a `ceiling_anchor_type`
value in Facet 5, not a method.

### Crosswalk to Every Eval Ever, HELM and Croissant

[01-landscape-and-positioning.md](01-landscape-and-positioning.md) commits to interoperating with
Every Eval Ever's field names for shared evaluation conditions, and §11 rule 10 lists
`eee_benchmark_name` as an interop identifier. A commitment with no mapping is a sentence, so here is
the mapping.

**Crosswalk, not adoption — and the distinction is deliberate.** An earlier draft of this table said
"adopt the EEE field name directly". [04-data-model.md](04-data-model.md) owns our schema and keeps
our own names (`tools_allowed`, `max_steps`, `sampling`), recording EEE's beside them; the mapping
lives in `taxonomy/crosswalks/eee.yaml`. That satisfies the join requirement exactly as well as a
rename would — an EEE-validated result still lands on our benchmark record through a stable ID — and
it survives their next schema version, whereas a rename couples our field names to a third party's
release cadence and turns their breaking change into ours. Where this table names one of our fields,
[04-data-model.md](04-data-model.md) §8 is the spelling that governs. It spans
facets 3, 4 and 8 rather than facet 3 alone, because the interop boundary is one surface and
splitting it across three sections would guarantee three copies that drift.

Source for the EEE column: recon:landscape's reading of `eval.schema.json` on 2026-09-17 (arXiv
2606.14516). The field paths are as that report recorded them and have **not** been re-read against
the live schema — *(unverified — confirm against the published `eval.schema.json` before writing an
adapter)*.

| Our term or field | EEE `eval.schema.json` | HELM equivalent | Lossy? |
| --- | --- | --- | --- |
| `evaluation_method: exact-match`, `multiple-choice`, `reference-metric`, `statistical-fit` | `evaluation_results[].metric_config` (`score_type`, `min_score`, `max_score`, `lower_is_better`) | `metric` group (`exact_match`, `quasi_exact_match`, `bleu`) | **Lossy inbound.** EEE records the score's *shape*, not how it was produced; four of our terms collapse onto one bounded numeric `score_type` |
| `evaluation_method: execution-tests`, `constraint-check` | `metric_config` plus a non-null `generation_config.sandbox` | run-spec with a code-execution metric | Not lossy — `sandbox` presence is the discriminator |
| `evaluation_method: model-graded-judge`, `rubric-graded`, `model-derived-metric` | **no slot**; the judge or scoring model is not a schema field | `annotator` / `annotator_model_deployment` | **Lossy, and this is the largest single gap.** An EEE record cannot say which model produced the score. HELM can. This is the strongest concrete argument for our facet and the first thing to propose upstream |
| `evaluation_method: episodic-return` | `metric_config.max_score: null` | none | Lossy: unboundedness is expressible; "headroom is therefore undefined" is not |
| `evaluation_method: pairwise-preference-elo`, `tournament-play` | no slot for rating-pool identity or snapshot date | none | **Lossy.** `comparability.rating_pool_required` has no EEE counterpart, so an ingested Elo number arrives without the thing that makes it meaningful |
| `evaluation_method: wet-lab-validation`, `physical-trial`, `expert-panel-assessment`, `human-distribution-percentile` | **no slot at all** | none | **Unmappable.** EEE's schema assumes a model, a prompt and a scored generation. This is the wet-lab, physical-trial and assessment-committee end of our vocabulary, and saying plainly that it has no home in any result registry *is* the argument for being their benchmark-registry counterpart |
| `designed_for_subjects: agent-scaffold`, `multi-agent-system`, `tool-augmented-model` | presence of `generation_config.agentic_eval_config`, and `available_tools[]` non-empty | none | Lossy: EEE separates agentic from non-agentic but not scaffold from tool-augmented, which is the distinction §6 exists to enforce |
| `designed_for_subjects: base-model`, `instruction-tuned-model`, `reasoning-model`, `hosted-inference-endpoint` | `model_id` only | `model_deployment` | **Lossy.** Subject type is not modelled and must be inferred from a model id — which is precisely the category error §6 names as the most misleading on public leaderboards |
| `designed_for_subjects: human-expert`, `human-nonexpert`, `human-ai-team`, `physical-robot-system`, `rl-policy`, `classical-algorithm` | **no slot** | none | **Unmappable** |
| `EvalConditions.sampling` (temperature, top_p, max_tokens) | `generation_config.generation_args` | `AdapterSpec` | Not lossy — **crosswalked one-to-one** in `taxonomy/crosswalks/eee.yaml` |
| `EvalConditions.tools_allowed[]` | `agentic_eval_config.available_tools[]` | none | Not lossy — **crosswalked one-to-one** |
| `EvalConditions.max_steps`, `token_limit` | `eval_limits.message_limit`, `eval_limits.token_limit` | none | Not lossy — **crosswalked one-to-one** |
| `execution.reproducibility_tier`, `reproducibility_blockers[]` | `generation_config.sandbox` (type + Docker compose) partially implies `fully-automatable` | none | Lossy: `sandbox` says a container exists, not whether anyone outside the maintainer can run it. `sandbox` → `reproducibility_tier` is a one-way hint, never an assignment |
| `EvalConditions.training_data_eligibility` | **no slot** | none | **Unmappable.** Matbench Discovery's compliance tiers are a comparability constraint on the *training* side and no result schema has a place for them (§12.6) |
| `independence_flags` | `source_metadata` (evaluator organisation and its relationship to the model) | none | Lossy but genuinely overlapping — the one place EEE already models something inside our Facet 7, and the natural first field to align |
| Facet 1 in full, `data.access`, `data.contamination_risk`, `lifecycle`, `maintenance_status` | **no slot — EEE has no benchmark entity** | scenario metadata, partially | **Unmappable, and that is the alliance case in one row.** They own the result record; we own the benchmark entity |
| `eee_benchmark_name` | `evaluation_name` | `run_spec.name` | The join key. Stored verbatim including case; never normalised, because a normalised join key is a silent mis-join |
| `croissant_url` | — | — | Croissant describes the *dataset* behind a benchmark. Stored as a link, never re-encoded; see §13 |

Two things follow for the plan. First, the one-to-one rows are free and the crosswalk file should be
written in [04-data-model.md](04-data-model.md)'s Phase-0 slice, before the first `EvalConditions`
record exists — not because the names change, but because discovering a one-to-one mapping *after*
records exist invites someone to rename a condition field to match it, and renaming a condition field
invalidates every `comparability_key` already computed. Second, the
**Unmappable** rows are the concrete proposal to take to the EvalEval coalition: not "we also
catalogue benchmarks", but "here are eleven condition and identity facts your schema has no slot for,
half of them from domains your scrapers do not reach, and here is a CC-BY registry that carries
them and joins on `evaluation_name`."

---

## 6. Facet 4 — Subject under test

*What kind of thing is being evaluated.*

**Eighteen terms.**

`base-model` · `instruction-tuned-model` · `reasoning-model` · `tool-augmented-model` ·
`domain-specialist-model` · `generative-media-model` · `scientific-surrogate-model` ·
`retrieval-augmented-system` · `agent-scaffold` · `multi-agent-system` · `full-product-pipeline` ·
`hosted-inference-endpoint` · `rl-policy` · `classical-algorithm` · `physical-robot-system` ·
`human-expert` · `human-nonexpert` · `human-ai-team`

### Designed-for versus actually-evaluated

This is the distinction that makes the facet worth having. **A benchmark declares
`designed_for_subjects[]`. A `ResultClaim` declares `subject_type` — what was actually evaluated.**
They are different fields on different entities and they routinely disagree.

Conflating a bare model with an agent scaffold is the most common and most misleading category
error on public leaderboards, and it is misleading in a specific, asymmetric way: the scaffold is
almost always better, the scaffold is almost always the thing shipped by the party with an incentive
to publish, and the scaffold is almost never described. A row that reads "Model X — 68.4%" when the
run used a bespoke harness, five retries and a custom prompt template is not a lie in any individual
field; it is a lie in the omission, and no field-level validation catches it. The facet plus the
`EvalConditions` scaffold reference makes the omission mechanical to detect: when `subject_type` is
`agent-scaffold` and `EvalConditions.scaffold` is null, `condition_completeness` drops and the
comparison view separates the claim from the bare-model claims rather than ranking them together.

The evidence that this matters is not theoretical. All four items below are from recon:domains,
verified 2026-09-17:

- **ARC-AGI-3 runs two leaderboards with different legality rules** — Official (unmodified,
  general-purpose API systems) and Community (self-reported, harnesses permitted). The ARC Prize
  Foundation solved this problem by building two boards. We solve it with a facet and a
  comparability key. Either way the number means nothing without it.
- **Terminal-Bench results move several points on harness choice alone** *(direction well
  attested; the specific magnitude is unverified — confirm before relying on this)*.
- **OSWorld's stated human baseline is 72.4% and the top-5 2026 runs recorded were 73.1–82.6%** — the
  human gap has inverted, which makes it exactly the benchmark where an undeclared scaffold changes
  the headline conclusion about machine-versus-human performance. (OSWorld arXiv 2404.07972;
  OSWorld 2.0 arXiv 2606.29537.)
- **CASP ranks human-expert groups in a separate category from automated servers**, so the same
  method can appear twice with different numbers. Without `human_in_loop` in the conditions and
  `human-ai-team` in this facet, those two rows are indistinguishable.

### Subject changelog against the archive

| Added | Reason |
| --- | --- |
| `tool-augmented-model` | A model given tools but no autonomous loop is neither `instruction-tuned-model` nor `agent-scaffold`. CritPt's ≈4% base versus ≈10% with code tools is the whole gap in one benchmark (recon:domains, 2026-09-17) |
| `generative-media-model` | VBench, GenEval, TTS Arena, the Artificial Analysis image and video arenas evaluate image/video/speech generators. None of the archive's 14 terms fit, so the entire generative-media cluster had no subject type |
| `scientific-surrogate-model` | Matbench Discovery evaluates interatomic potentials; WeatherBench 2 evaluates weather emulators; The Well evaluates PDE surrogates; Open Catalyst evaluates force-field models. These are not "domain-specialist models" in the LLM sense and the distinction matters for the runner layer |
| `hosted-inference-endpoint` | Epoch's local data carries 927 distinct `Model version` strings that are provider-endpoint slugs — `accounts/fireworks/models/glm-4p6`, `chutes/DeepSeek-R1-0528`, `amazon.nova-pro-v1:0`, `gpt-6-astra_max` — mixing model identity, hosting provider and reasoning effort into one token (counted from `epochdl/`; recon:epoch-assets, 2026-09-17). What was evaluated was an endpoint, not a model. Pretending otherwise is how quantised or differently-served variants get compared as if they were the same system |

**Deliberately excluded: `hardware-device`.** Metriq and the QED-C application-oriented benchmarks
evaluate quantum *computers*. The system under test is a device, results are device-and-date
specific, and admitting them would open the whole hardware-benchmarking field (MLPerf, SPEC,
volumetric quantum benchmarks). QML *algorithm* benchmarks are in scope under `physics/quantum-systems`
with a model-shaped subject. See §13.

---

## 7. Facet 5 — Data properties

Five independent fields rather than one vocabulary.

### `access` — nine terms

`fully-open` · `train-open-test-held-out` · `gated-registration` · `credentialed-dua` ·
`private-test-server` · `invitation-only` · `restricted-dual-use` · `proprietary-closed` ·
`generated-on-demand`

- `credentialed-dua` is the PhysioNet class: CheXpert Plus, MIMIC-CXR and MIMIC-IV require
  credentialing, CITI training and a signed data-use agreement. "Open but not downloadable" is a real
  and common state that `gated-registration` understates.
- `restricted-dual-use` covers WMDP (public with some items deliberately withheld) and ABC-Bench (a
  biosecurity benchmark that responsibly *cannot* be fully public). A benchmark that should not be
  fully released is not the same as one that is commercially closed.
- `invitation-only` covers the A2RL Drone Championship (14 invited teams) and the CCDC CSP Blind
  Test.

A structured field `submission_limit` records eval-server rate limits, because a limit changes what
independent verification is possible. Its shape is fixed here so that no two curators invent two
encodings:

```yaml
submission_limit:
  max_submissions: 3        # int, required if the block is present
  period_days: 30           # int, required; 0 means "lifetime"
  per: team                 # enum: team | account | institution
  source: src-...           # required; a limit is a claim about a third party's rules
```

`null` means no limit is documented, which is not the same as no limit existing. KITTI, Cityscapes
and Argoverse 2 all cap submissions per period; the exact caps should be read from each server's own
page and dated, not copied from here.

### `refresh` — seven terms

`static` · `versioned-releases` · `rolling-live` · `continuously-generated` ·
`periodic-recompetition` · `continuously-reexecuted` · `resolves-over-time`

- `continuously-reexecuted` is Open Problems in Single-Cell Analysis: there is no frozen version, and
  results change when the Viash/Nextflow pipeline re-runs. A stored claim without a pipeline commit
  is unanchored.
- `resolves-over-time` is ForecastBench and CAFA. It pairs with the claim-level
  `resolution_status: pending | partial | resolved`.
- `periodic-recompetition` is DCASE (new eval set every year), BraTS, NTIRE, LifeCLEF and CASP.

### `data_provenance` — eleven terms

`expert-authored` · `crowd-authored` · `exam-derived` · `web-scraped` · `synthetic-procedural` ·
`model-generated` · `real-world-instrument` · `simulation-generated` · `experimental-measurement` ·
`patient-clinical-record` · `unreleasable-confidential`

`unreleasable-confidential` is SimulacraBench (evaluated against unreleased UN microdata), Apollo's
held-out scheming suite, and FrontierMath's private problem set. It is the honest label for
"structurally irreproducible by anyone outside", and it should be visible next to every number
derived from such data.

### `contamination_risk` — five terms

`low` · `medium` · `high` · `confirmed` · `unknown`

**Never asserted editorially.** `high` and `confirmed` require at least one entry in
`contamination_evidence[]` pointing at a `Source`. CI enforces this and the rule is blocking. This is
constraint 4 of the project made mechanical: the plan's own premise is that unsourced confident data
destroys trust, so the one facet most likely to attract opinion is the one where opinion is a build
failure.

Two structural notes belong in `contamination_notes`, not in the enum value:

- `generated-on-demand` and `rolling-live` benchmarks are structurally resistant and should usually
  be `low`.
- A private test set (FrontierMath, Apollo, Vals AI) lowers contamination risk and raises a different
  problem — nobody outside can verify anything. The two states must not be conflated into a single
  "trustworthy" reading. The independence flags in Facet 7 carry the other half.

### `ceiling_anchor_type` — ten terms

**Renamed from the archive's `human_baseline_type`.** Three of the terms below are not human, and the
old name made those benchmarks look defective when they are simply not human-referenced. The old
identifier is forbidden in `data/`, `taxonomy/`, `src/` and `scripts/` and is named here only to
explain the rename.

`none-known` · `crowd-average` · `crowd-best` · `expert-average` · `expert-best` ·
`theoretical-maximum` · `measured-ceiling` · `experimental-replicate` · `operational-system` ·
`noise-ceiling`

- `experimental-replicate` — the Virtual Cell Challenge 2026 scales each of its six metrics between
  the cell-context mean and *a real replicate experiment*. The "100%" anchor is an experiment, not a
  person.
- `operational-system` — WeatherBench 2's comparator is the ECMWF IFS/ENS operational forecast. Asking
  for a human baseline here is a category error.
- `noise-ceiling` — Brain-Score normalises by the noise ceiling of primate neural recordings.

Required for headroom computation ([12-analytics-and-trends.md](12-analytics-and-trends.md)). Its
absence is itself informative and must be visible rather than silently rendering headroom as null.

**This facet and `Baseline.kind` are not the same vocabulary, and the difference is deliberate.**
This is the *ceiling* side: ten terms naming what the top of the scale is anchored to. `Baseline.kind`
in [04-data-model.md](04-data-model.md) §7 is the entity enum for a stored comparator record, and it
carries three additional values — `classical-algorithm`, `random-chance` and
`field-practice-reference` — that are **floors**, not ceilings, and therefore have no place here. The
ten ceiling terms map one-to-one onto their `Baseline.kind` counterparts; `04` §7 owns that mapping
and is the spelling that governs for a stored record. Any document that computes headroom reads these
two vocabularies rather than restating either: **a headroom number computed from a vocabulary the
schema cannot store is exactly the unsourced confident number this project exists to oppose.**

### Data-properties changelog against the archive

| Change | Forced by |
| --- | --- |
| **Added `credentialed-dua`** (access) | The PhysioNet class — MIMIC-CXR, MIMIC-IV, CheXpert Plus require credentialing, CITI training and a signed DUA. "Open but not downloadable" was inexpressible |
| **Added `restricted-dual-use`** (access) | WMDP (public with items deliberately withheld) and ABC-Bench. Responsibly-withheld is not commercially-closed and conflating them misrepresents both |
| **Added `invitation-only`** (access) | A2RL Drone Championship (14 invited teams); CCDC CSP Blind Test |
| **Added `generated-on-demand`** (access) | Kaggle Game Arena and procedurally generated suites, which are contamination-resistant by construction — the value carries the reason the `contamination_risk: low` is structural rather than assessed |
| **`submission_limit` given a fixed structure** | KITTI/Cityscapes/Argoverse 2 submission caps. The archive called it "boolean-plus-integer" with no period and no unit, which is two curators inventing two encodings |
| **Added `continuously-reexecuted`** (refresh) | Open Problems in Single-Cell Analysis: no frozen version; the score moves when the Viash/Nextflow pipeline re-runs |
| **Added `resolves-over-time`** (refresh) | ForecastBench, CAFA. Pairs with claim-level `resolution_status` |
| **Added `periodic-recompetition`** (refresh) | DCASE, BraTS, NTIRE, LifeCLEF, CASP — annual editions with a fresh evaluation set, which is neither `static` nor `rolling-live` |
| **Added `experimental-measurement`, `patient-clinical-record`, `unreleasable-confidential`** (data_provenance) | Wet-lab challenges (CACHE, OCx24, CASP); PhysioNet-class clinical records; FrontierMath's and Apollo's private sets. The last is the honest label for structural irreproducibility |
| **`contamination_risk` evidence rule made blocking** | Constraint 4. The facet most likely to attract opinion is the one where opinion must be a build failure, not a style note |
| **Renamed `human_baseline_type` → `ceiling_anchor_type`** | Three of the ten anchors are not human. The old name made WeatherBench 2, Brain-Score and the Virtual Cell Challenge look defective for having a correct non-human anchor |
| **Added `experimental-replicate`, `operational-system`, `noise-ceiling`** (ceiling_anchor_type) | Virtual Cell Challenge (a real replicate experiment), WeatherBench 2 (ECMWF IFS/ENS), Brain-Score (primate neural noise ceiling) |
| **Retired: a single open/closed access boolean** | It could express neither "open but not downloadable" nor "deliberately withheld", which between them cover most of medicine and all of biosecurity |

---
## 8. Facet 6 — Lifecycle

The archive had one field. The Waymo Open Dataset Challenges break it: verified on 2026-09-17, there
is **no formal 2026 competition round, but the leaderboards remain open** (recon:domains). "Is the
benchmark alive?" and "is the competition running?" and "is anyone maintaining the code?" are three
different questions, and a single enum answers at most one. Three fields, two of them derived, plus
a contest flag.

### `lifecycle` — the instrument's standing (hand-set or derived; ten terms)

`proposed` · `active` · `mature` · `saturated` · `under-revision` · `contaminated` · `superseded` ·
`deprecated` · `retracted` · `dormant`

**`saturated` is derived, never hand-set.** From [12-analytics-and-trends.md](12-analytics-and-trends.md):

```
headroom_consumed = (SOTA − baseline) / (ceiling − baseline)

emerging   = headroom < 0.25
contested  = 0.25 ≤ headroom < 0.75
closing    = 0.75 ≤ headroom < 0.95
saturated  = headroom ≥ 0.95
```

#### Which number is SOTA

The archive gave the formula and never defined its numerator, which is a hole big enough to drive
the whole ingestion corpus through. C5 ingests roughly 6,598 Epoch result rows at
`verification_status: machine-ingested` with a mean `condition_completeness` around 0.10
(recon:epoch-assets, 2026-09-17). A naive max-over-all-claims would let one unverified scraped row
declare a benchmark `saturated`, which then hard-sets a lifecycle value on the browse spine. The rule
is therefore explicit and narrow:

> **SOTA is the highest score among claims that satisfy all three of:** (a) `ResultClaim.verification`
> at **rank 3, `independent-reproduction`, or above** on the seven-rung ladder owned by
> [04-data-model.md](04-data-model.md) §7 — stated by rank as well as by name so a future
> renumbering is caught; (b) `curation.verification_status` at **`curator-reviewed` or better** on
> the six-value curation ladder owned by
> [05-repository-and-workflow.md](05-repository-and-workflow.md) §4; and (c) a `comparability_key`
> matching the benchmark's declared `reference_conditions`. Claims at `machine-ingested` never drive
> lifecycle. They drive browse, search and coverage only.

**Why the rule names two ladders and not one.** They are two different axes and conflating them is
the failure [09-design-system.md](09-design-system.md) §4.3 gives two separate marks to prevent:
`ResultClaim.verification` grades *how the number was produced* (self-reported → maintainer-verified
→ independent-reproduction → held-out-server → prospective-experiment → third-party-audited →
sandboxed-rerun), while `curation.verification_status` grades *how hard we looked at it*
(ai-drafted-unverified → machine-ingested → curator-reviewed → primary-source-verified →
expert-reviewed → maintainer-confirmed). An earlier draft of this rule listed rungs from both
ladders in one "or better" chain and named a value, `curator-verified`, that exists on neither. That
is worth recording rather than silently fixing, because this rule gates `lifecycle: saturated`,
which gates headroom, which is the only cross-domain axis the project claims: **a nonexistent enum
value here propagates into the one number the whole site is built on.**

Two corollaries that have to be said out loud. First, **a benchmark with no `reference_conditions`
declared has no SOTA and therefore no headroom** — `headroom: null`, and the UI says "no reference
conditions declared" rather than rendering a blank. `reference_conditions` is a nullable `EvalConditions`
reference on the `Benchmark` entity, defined in [04-data-model.md](04-data-model.md) §5 and on its
§15 pre-ingest prerequisite list, and listed in §12's handoff table as required before the first
YAML file. Second, **a benchmark with plenty of claims but none that are both verified and at reference
conditions also has no headroom**, and that is the common case at launch, not an edge case. The
honest reading of an empty headroom column in the first six months is "we have not verified a
comparable claim yet", and the UI must say that rather than implying the benchmark is unmeasured.

The design consequence, and it is the point of the whole arrangement: the bulk Epoch ingest provides
**coverage** — which is exactly what the user asked for, a great searchable collection — without
polluting **comparison**, which is where credibility lives.

#### Four guards on the derivation, all load-bearing

1. **Both anchors must exist and be sourced.** `baseline` is the metric's chance baseline or a
   sourced floor; `ceiling` is the `ceiling_anchor_type` value. If either is missing, headroom is
   `null` and lifecycle stays at its hand-set value. Never impute a ceiling.
2. **Unbounded metrics can never be saturated.** Elo ratings, `episodic-return`, Atari-style
   human-normalised scores that exceed 100%, and speedup ratios have no ceiling. `headroom: null`,
   `lifecycle` unaffected, and the UI says why rather than showing a blank.
3. **A minimum claim count above the verification threshold.** One self-reported number is not
   evidence of saturation. The threshold is set in [12-analytics-and-trends.md](12-analytics-and-trends.md);
   below it, the state is `unknown`. Note what this guard does *not* do: it defends against volume,
   not against a single outlier, which is why guard 1's sourcing requirement and the SOTA rule above
   both have to hold as well.
4. **Non-cardinal scales are excluded by construction.** If `evaluation_method` contains
   `ordinal-grading`, `pairwise-preference-elo`, `tournament-play` or `episodic-return`, then
   `headroom: null` — the same treatment guard 2 gives unbounded metrics, for a different reason.
   AILuminate's "Good" is defined *relative to the current state of the art*, so headroom over that
   scale is not merely unknown, it is undefined: the ceiling moves with the numerator. Elo and
   tournament placement are pool-relative for the same reason. A claim at
   `prospective-resolution` with `resolution_status: pending` is likewise excluded from SOTA until
   it resolves.

`under-revision` is new and is forced by FrontierMath: **Epoch reissued a corrected version on
2026-06-12 after finding errors in 42% of problems** (recon:domains, verified 2026-09-17, from
epoch.ai/frontiermath). A score against "FrontierMath" without a version is now meaningless. The
lifecycle state flags the instability; the actual version break is modelled as
`BenchmarkVersion.breaking: true` in [04-data-model.md](04-data-model.md).

`contaminated` and `retracted` are hand-set and require evidence sources, same rule as
`contamination_risk`. See the cross-field consistency rules in §11 for which of the two fields is
authoritative.

### `activity` — the competition's operational state (six terms)

`accepting-submissions` · `round-scheduled` · `between-rounds` · `leaderboard-live-no-round` ·
`closed` · `unknown`

`leaderboard-live-no-round` is the Waymo state and it is common: the CARLA leaderboard is live and
brutal (SOTA ≈6% success on secret routes, recon:domains 2026-09-17); the NetHack Challenge is
dormant as a competition but alive as an environment; VoxSRC ran 2019–2023, published a
retrospective in IEEE/ACM TASLP 2024 and retired as an annual challenge while remaining heavily
cited. Without this field, all three look identical to `dormant`.

### `maintenance_status` — derived from observable signals (five terms)

`actively-maintained` · `slow` · `stale` · `abandoned` · `unobservable`

This is the closest thing the project has to unoccupied ground in a single field. No catalogue the
landscape reconnaissance examined marks a benchmark as dead
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 states exactly how far that
claim is supported and what would retire it). The evidence that benchmarks *are* dying:

- The AISafetyBenchExplorer study measured **137 of 195 safety benchmarks with stale GitHub repos and
  96 of 195 with stale HuggingFace datasets** (arXiv 2604.12875 — note this preprint was *withdrawn*
  on 2026-04-23 for an institutional-affiliation compliance matter and no PDF is available, so cite
  the finding as unverified-by-peer-review while treating the direction as credible).
- **BetterBench found 17 of 24 benchmarks had no easy-to-run reproduction scripts** (arXiv
  2411.12990).
- Stanford CRFM's Ecosystem Graphs last pushed on 2025-01-24 and is **still cited as a data source by
  2025–26 research while 20 months stale** (recon:landscape, 2026-09-17) — stale curation actively
  propagating errors into the literature.

#### Derivation rules

| Status | Rule |
| --- | --- |
| `actively-maintained` | Any observable signal dated within 180 days |
| `slow` | Most recent observable signal 180–365 days old |
| `stale` | No observable signal for 365–730 days |
| `abandoned` | No signal for 730+ days, **or** any two of {homepage dead, repo archived, leaderboard 404, dataset removed}, each confirmed under the probe protocol below |
| `unobservable` | No repo, no dataset page, no dated leaderboard, or every probe blocked |

#### The probe protocol, because a rules table is not a mechanism

The archive stopped at the table above, and a table keyed on "leaderboard update" without saying how
an update is detected is not a derivation, it is an intention. The probe contract is specified here
and **implemented in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)**, which owns
scheduling, retry and the state store. What that document must deliver is one record per signal per
probe, carrying `signal_type`, `url`, `http_method`, `http_status`, `observed_at`, `value`
(a date, a hash, or null), `consecutive_failures` and `probe_blocked: bool`. Anything less and
`maintenance_status` cannot be recomputed from the artifact, which would make it the one facet the
project cannot audit.

| Signal type | How it is read | Dated? |
| --- | --- | --- |
| Git host | `GET /repos/{owner}/{repo}` → `pushed_at`, `archived` (GitHub API; GitLab equivalent) | Yes, exactly |
| HuggingFace dataset or space | `GET /api/datasets/{id}` → `lastModified` | Yes, exactly |
| Package release | PyPI / npm / CRAN release index → latest release date | Yes, exactly |
| Dated leaderboard | An extracted date field on the page or in its JSON | Yes, exactly |
| **Undated leaderboard** | Normalise (strip scripts, styles, whitespace, ad slots), extract the result-table rows, sort them, SHA-256 the result → `leaderboard_fingerprint`, stored with `first_seen` and `last_changed` | **No — bounded only** |
| Homepage liveness | `HEAD`, falling back to `GET` on 405 | Not a date; a state |

The undated-leaderboard case is the one that matters, because it is the modal case in the non-LLM
domains, and the honest answer is uncomfortable: **a fingerprint change is an update dated at probe
time, and an unchanged fingerprint is a lower bound on staleness, never a date.** We cannot date a
change we did not observe. Therefore, until our own observation history for a benchmark exceeds 180
days, an unchanged fingerprint contributes `unobservable` rather than `stale`, and the displayed
evidence reads "unchanged since our first observation on YYYY-MM-DD" rather than implying we know
when it last moved. Publishing a staleness claim on the strength of our own short memory would be the
same unsourced confidence the project exists to oppose.

What counts as dead, stated precisely:

- **Dead** = three *consecutive* probes returning any of: DNS failure, connection refused or reset,
  TLS failure, HTTP 404, HTTP 410, or a 200 matching the soft-404 heuristic (response body under 512
  bytes containing "not found" / "no longer available", or a redirect to a site root that differs
  from the recorded canonical URL).
- **Probe-blocked, not dead** = HTTP 401, 403, 429, or a Cloudflare / anti-bot interstitial. C4
  records that OpenReview API2 already returns 403 to anonymous clients; treating 403 as death would
  mark every OpenReview-hosted benchmark abandoned on day one. A blocked probe sets
  `probe_blocked: true` and contributes `unobservable` for that signal, permanently and visibly.
- **Cadence**: weekly for `actively-maintained` and `slow`, monthly for `stale`, quarterly for
  `abandoned` and `unobservable`. A single failure never changes a status.
- **Quarantine**: any transition *toward* `abandoned` is computed but withheld for **30 days**, and
  the published value lags by that period. A transient outage or a domain renewal should not publish
  a death notice. Transitions away from `abandoned` publish immediately, because the asymmetry is
  deliberate — we are slow to say something died and fast to say it lives.

#### `unobservable` will dominate the moat, and that must not be read as death

The signals these rules depend on — GitHub commits, HuggingFace dataset revisions, package releases —
exist mainly for LLM-era benchmarks. CASP, CACHE, the grand-challenge.org challenges, DCASE, NTIRE,
LifeCLEF and the CCDC CSP Blind Test are challenge-website-only, so **`unobservable` is the expected
modal value in exactly the non-language domains the project calls its moat.** Name the failure mode
plainly: a feature sold as unoccupied ground degrades to "we don't know" precisely where it was
supposed to differentiate.

Two rules contain the damage. **The coverage map and every derived metric must treat `unobservable`
as missing data, never as a proxy for `abandoned`**, and must never let it lower a family's
completeness or liveness score — otherwise robotics and structural biology render as graveyards
because their communities do not use GitHub the way NLP does. And **`unobservable` is displayed as a
statement about our instruments, not about the benchmark**: "no dated signal we can poll; CASP
publishes assessment papers on a multi-year cycle" is the correct rendering, and it is also an
honest advertisement for the parts of the field where the LLM-era toolchain simply does not reach.

#### Contested status, because this is a public assertion about a third party

Flipping a live benchmark to `abandoned` is a factual claim about someone else's work, made by an
automated rule, on a site whose entire positioning is disclosure rather than accusation. The archive
gave that no correction path, no appeal and no state for "the maintainer says otherwise", which is
the same defect §7's contamination rule exists to prevent — and it is worse here, because the
assertion is generated rather than authored.

```yaml
maintenance_status: abandoned            # derived; always shown with its evidence
maintenance_status_contested: true       # boolean, hand-set
contested_source: src-...                # required when contested is true
contested_statement_date: 2026-08-14     # required when contested is true
```

The rule: **a maintainer's dated public statement overrides a derived signal.** When
`maintenance_status_contested` is true, the site displays the maintainer's statement first, the
derived value second and labelled as derived, and both dates. The derived value is never deleted —
the audit trail is the point — and the contest is never accepted without a `Source`, exactly like a
contamination claim. CI asserts that `contested_source` and `contested_statement_date` are present
whenever the flag is set, and the contact route for raising one is the issue form in
[05-repository-and-workflow.md](05-repository-and-workflow.md), not an email to us.

The status is displayed with its evidence — the signal dates, what was probed, and when — never as a
bare badge. "This benchmark shows no maintained signal; here is what we looked at and when" is a
factual statement. "This benchmark is bad" is an editorial one, and we do not make it.

#### A recorded disagreement: `maintenance_status` is a field, and stays one

[15-open-questions.md](15-open-questions.md) C3 carries an instruction that `maintenance_status` "is
not a field; use `lifecycle` plus the `liveness` block". **That instruction is wrong and this
document declines it, on the merits rather than on seniority**, and the disagreement is recorded here
rather than resolved by quietly deleting one side.

The three things are not substitutes, they are a chain: `liveness` (owned by
[04-data-model.md](04-data-model.md) §5) holds the **raw observations** — `repo_last_commit`,
`leaderboard_last_updated`, `reproduction_script_present`, `last_checked`; `maintenance_status` is
the **derived verdict** over those observations, with a probe protocol, a consecutive-failure
threshold and a contest mechanism; and `lifecycle` is a **different question entirely** — the
instrument's standing, ten terms, none of which is `stale`, `abandoned` or `unobservable`. Collapsing
the verdict into the observations would mean every consumer of the data re-implements the derivation
and they would not agree; collapsing it into `lifecycle` would mean asserting that a benchmark whose
repository has gone quiet is *deprecated*, which is a claim about the maintainer's intent that the
evidence does not support. Losing `unobservable` in particular would report CASP as `stale`, which is
false and, as §8 already argues, would discredit the feature on its first specialist reader.

The action is therefore on `15` C3, which should withdraw the row and record the reversal in its
"Answered" table; `04` §5 carries `maintenance_status` and the three contest fields as derived, with
`liveness` named as their input. Nothing in this document changes.

### Lifecycle changelog against the archive

| Change | Forced by |
| --- | --- |
| **Split one `status` enum into `lifecycle` + `activity` + `maintenance_status`** | Waymo Open Dataset Challenges: no 2026 round, leaderboards still open (verified 2026-09-17). One enum answers at most one of three independent questions and the archive's answer was whichever the curator happened to mean |
| **Added `activity`** (six terms) | The three-way distinction above. Without it, a live environment with a dead competition, a scheduled round, and a genuinely dormant benchmark are indistinguishable |
| **Added `leaderboard-live-no-round`** (activity) | Waymo, CARLA, the NetHack Challenge, VoxSRC. The most common state in the non-LLM half of the map and the one with no archive representation |
| **Added `maintenance_status`** (five terms, derived) | 137/195 stale safety repos (arXiv 2604.12875, withdrawn); BetterBench's 17/24 with no reproduction scripts; Ecosystem Graphs 20 months stale and still cited. No catalogue marks benchmarks as dead ([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 states exactly how far that claim is supported) |
| **Added `unobservable`** (maintenance_status) | The challenge-website domains have no pollable dated signal. Without this value the derivation would silently report `stale` for CASP, which is false and would discredit the feature on its first specialist reader |
| **Added the probe protocol and the 30-day quarantine** | The archive's rules table named signals it never operationalised. A derived public assertion needs a defined method, a consecutive-failure threshold and a defence against transient outages |
| **Added `maintenance_status_contested` + `contested_source` + `contested_statement_date`** | An automated death notice about a third party with no appeal path is an accusation, not a disclosure. Same shape as the contamination-evidence rule in §7 |
| **Added `under-revision`** (lifecycle) | FrontierMath's 2026-06-12 errata affecting 42% of problems. A benchmark can be alive, maintained and temporarily untrustworthy at the same time |
| **`saturated` made derived rather than hand-set** | A hand-set saturation flag is an editorial judgement wearing a data field's clothes. Now computed, with four guards and an explicit SOTA rule |
| **Added the SOTA selection rule and guard 4** | The formula had no defined numerator, so a single `machine-ingested` row could set a lifecycle value; and ordinal and pool-relative scales have no defined headroom at all |
| **Retired: `archived` as a lifecycle value** | It conflated `dormant` (the instrument's standing) with `closed` (the competition) and `abandoned` (the code). All three are now expressible separately, and the legality matrix in §11 says which combinations are meaningful |

---

## 9. Facet 7 — Governance and host

Who controls the benchmark and how numbers get onto its leaderboard. This is the facet that makes the
ecosystem analysis in [12-analytics-and-trends.md](12-analytics-and-trends.md) possible.

### `maintainer_type` — nine terms

`academic-lab` · `industry-lab` · `consortium` · `standards-body` · `conference-workshop` ·
`nonprofit` · `government-agency` · `individual` · `community-collective`

- `standards-body` — MLCommons (AILuminate, Dynabench), CCDC (CSP Blind Test), the wwPDB partners.
  Different failure characteristics from an academic lab: slower, more durable, more procedural.
- `conference-workshop` — NTIRE (CVPR), DCASE, MICCAI/BraTS, LifeCLEF, the CVPR Embodied AI and Image
  Matching workshops. This is a genuinely distinct governance mode: an organising committee that
  re-forms annually, with continuity dependent on individual volunteers. It is the mode most exposed
  to the roughly three-to-four-year half-life that put HELM into maintenance mode on 2026-06-01 and
  archived BIG-bench on 2026-04-17 (both recon:landscape, verified 2026-09-17).
- `community-collective` — RoboArena's distributed network of labs, the DCASE organising community.
  Distinct from `consortium`, which has a legal form.

**`unmaintained` was deleted from this vocabulary.** It is not a maintainer *type*; it is a
`maintenance_status` value wearing the wrong hat, and a benchmark does not lose its academic-lab
origin by going stale. A stale academic benchmark is `maintainer_type: academic-lab` with
`maintenance_status: stale`, which is both more informative and more accurate.

### `submission_process` — ten terms

`self-reported` · `maintainer-verified` · `sandboxed-rerun` · `held-out-server` ·
`containerized-algorithm-submission` · `assessment-committee` · `third-party-audited` ·
`live-arena` · `physical-competition` · `publication-gated`

- `containerized-algorithm-submission` — grand-challenge.org type-2 challenges take an algorithm
  container, not a prediction file. The distinction matters: you cannot overfit a leaderboard you
  cannot see, and you cannot submit at all without packaging real code.
- `assessment-committee` — CASP, CAGI and the CSP Blind Test do not have leaderboards. Their output
  is a peer-reviewed assessment.
- `publication-gated` — LifeCLEF's official ranking requires submitting a CEUR-WS working-note paper.
  A publication requirement on eligibility is a real access condition and nowhere else in the schema
  expresses it.

### `independence_flags` — multi-valued, evidence-linked, eight terms

`no-known-conflict` · `maintainer-competes-on-own-benchmark` · `funded-by-evaluated-party` ·
`prize-sponsored-by-industry` · `evaluator-sells-evaluations` · `single-evaluator-private-test-set` ·
`results-published-only-in-vendor-document` · `commercial-leaderboard-placement`

**This is presented as disclosure, never as accusation, and the plan should be blunt about why.** The
point is not that a lab benchmarking its own model is doing something wrong — it is that a reader who
does not know cannot weigh the number, and a reader who does know can. Three rules make this
mechanical rather than editorial:

1. **Every flag except `no-known-conflict` requires an evidence `Source`.** CI enforces it.
2. **`no-known-conflict` means "we looked and found none", not "there is none".** It is a statement
   about our search, and the entry records `last_verified`. An entry with no flags at all is
   different from one flagged `no-known-conflict`, and the UI shows the difference.
3. **The flag never carries a valence in the rendering.** No warning triangles, no red. A neutral
   disclosure chip with the source behind it.

Worked examples of the flags doing their job, all of them ordinary and none of them accusations:
FrontierMath is `single-evaluator-private-test-set` (Epoch holds the problems and runs the
evaluations — which is also what makes it contamination-resistant); Vals AI and Artificial Analysis
are `evaluator-sells-evaluations`; the Virtual Cell Challenge is `prize-sponsored-by-industry`
(NVIDIA, 10x Genomics and Ultima sponsor a $175k pool — recon:domains, 2026-09-17); Apollo Research's
scheming results are `results-published-only-in-vendor-document` because they surface inside model
system cards; HealthBench, GDPval, MLE-bench, PaperBench and SWE-bench Pro are all
`maintainer-competes-on-own-benchmark`, which is true of most of the strongest benchmarks in 2026 and
is exactly why saying it plainly is better than implying it.

### Governance changelog against the archive

| Change | Forced by |
| --- | --- |
| **Added `standards-body`** (maintainer_type) | MLCommons, CCDC, the wwPDB partners. Slower, more procedural and far more durable than an academic lab, which is a first-order predictor of whether a benchmark will still exist in three years |
| **Added `conference-workshop`** (maintainer_type) | NTIRE, DCASE, BraTS/MICCAI, LifeCLEF, the CVPR workshop challenges. An annually re-forming organising committee is the governance mode most exposed to the three-to-four-year academic half-life |
| **Added `community-collective`** (maintainer_type) | RoboArena's distributed lab network; the DCASE organiser community. Distinct from `consortium`, which has a legal form and a budget |
| **Deleted `unmaintained`** (maintainer_type) | Not a maintainer type. It is a `maintenance_status` value in the wrong field, and it silently erased a benchmark's origin as the price of recording its decay |
| **Added `containerized-algorithm-submission`** (submission_process) | grand-challenge.org type-2 challenges accept an algorithm container, not a prediction file — a materially stronger verification posture with no archive representation |
| **Added `assessment-committee`** (submission_process) | CASP, CAGI, CCDC CSP Blind Test. No leaderboard exists; the output is a peer-reviewed assessment, and the archive vocabulary could only express "self-reported" |
| **Added `publication-gated`** (submission_process) | LifeCLEF requires a CEUR-WS working-note paper for official ranking eligibility. A publication requirement is an access condition and nothing else in the schema carries it |
| **Added `physical-competition`** (submission_process) | RoboCup, the A2RL Drone Championship, RoboTwin's hardware track. Also the reason a `robot-competition` *domain* was rejected in §3 — the fact belongs on this facet |
| **`independence_flags` made a multi-valued, evidence-linked field** (eight terms) | The archive carried a single `independence` enum, which forced a curator to choose between two true disclosures. Every flag except `no-known-conflict` now requires a `Source`, and CI blocks without one |
| **`no-known-conflict` redefined as a statement about our search** | "We looked and found none" and "there is none" are different claims, and only the first is one we can support. The field carries `last_verified` for that reason |

---

## 10. Facet 8 — Execution cost and reproducibility

Determines what could ever be re-run ([13-execution-runners.md](13-execution-runners.md)), what the
suite builder can honestly recommend ([11-ai-features.md](11-ai-features.md)), and what independent
verification is realistic.

### `compute_tier` — twelve terms

`trivial-cpu` · `single-gpu` · `multi-gpu-node` · `cluster` · `api-credits-only` ·
`simulator-required` · `physical-hardware` · `physical-venue-entry` · `wet-lab` ·
`participant-funded-procurement` · `human-panel` · `provided-allocation`

- `participant-funded-procurement` — CACHE participants pay for compounds to be bought from Enamine
  and assayed. The cost of entry is chemicals, not GPUs.
- `physical-venue-entry` — RoboCup 2026 ran 30 June–6 July in Incheon with 3,000+ participants
  (recon:domains, verified 2026-09-17); the A2RL Drone Championship is an invitational in Abu Dhabi.
  You ship a robot.
- `provided-allocation` inverts the model: the FAIR Universe HiggsML Uncertainty Challenge *ships
  compute*, running on Codabench with a NERSC Perlmutter allocation. A benchmark that removes the
  cost barrier is a materially different proposition and should be findable as one.

### `reproducibility_tier` — six terms

`fully-automatable` · `automatable-with-simulator` · `requires-specialized-hardware` ·
`requires-human-raters` · `requires-physical-experiment` · `not-independently-reproducible`

### `reproducibility_blockers[]` — ten terms, multi-valued

`private-test-set` · `unreleasable-data` · `specific-simulator-build` · `hardware-fleet` ·
`human-raters` · `wet-lab` · `live-world-state` · `compute-scale` · `no-reference-implementation` ·
`licence-restriction`

The tier says how hard; the blockers say *why*, which is what the runner-layer scoping in
[13-execution-runners.md](13-execution-runners.md) actually needs. `specific-simulator-build` is the
BEHAVIOR Challenge case (score defined only inside one OmniGibson/Isaac-Sim build);
`no-reference-implementation` is BetterBench's 17-of-24 finding made into a field; `live-world-state`
is BizFinBench.v2's online tasks against live market platforms and ForecastBench's unresolved
questions. The implication rules that tie the tier, the blockers and `access` together are in §11 —
three fields encoding one fact is the shape of a silently inconsistent record.

### `harness_availability` — three terms

`official-harness` · `reference-implementation-only` · `none`

**`inspect-evals-port` was deleted from this enum.** It duplicated the separate `inspect_evals_id`
field, which meant the enum value and the id could disagree and nothing would catch it. Instead:

```yaml
harness_availability: reference-implementation-only   # hand-set, 3 terms
inspect_evals_id: agentharm                           # hand-set, nullable
inspect_evals_available: true                         # DERIVED: inspect_evals_id != null
```

UK AISI's `inspect_evals` is the de facto frontier safety eval standard in 2026 and is MIT-licensed;
recon:landscape recorded **171 evals (129 internal / 42 external), 674 stars, last pushed
2026-09-17**, and a `/register/` submission folder launched 2026-05-08 in which a GitHub issue is
validated by a bot that derives eval metadata and opens a PR. Those figures are a single observation
on one date and will move — *(unverified as a current figure — confirm before relying on it)*; the
structural facts (MIT licence, issue-form registration, implementation-gated scope) are what the
plan depends on. Linking into it makes us the front door to their harness rather than a rival: their
registry is implementation-gated and language-model-gated, so a protein-structure challenge or a
weather benchmark can never enter it, while ours can link out to a runnable implementation wherever
one exists. Their `/register/` flow is also the model for our own contribution path
([05-repository-and-workflow.md](05-repository-and-workflow.md)).

### Numeric estimates — always ranges, never point values

```yaml
execution:
  est_runtime_hours:        {min: 2,  max: 30,   basis: "full split, 1 concurrent worker", source: src-...}
  est_cost_usd:             {min: 50, max: 2000, basis: "frontier API pricing, no retries", source: null}
  est_api_calls:            {min: 2294, max: 11470, basis: "1–5 attempts per instance", source: null}
  est_participant_cost_usd: null   # entry fees, compound purchase, hardware shipping
```

Every estimate carries a `basis` string saying what configuration it assumes, because the
configuration *is* a condition — an estimate without its basis is the same failure mode as a score
without its conditions. `source` may be null (our own estimate) but `basis` may not. CI enforces it.

### Execution changelog against the archive

| Change | Forced by |
| --- | --- |
| **Added `participant-funded-procurement`** (compute_tier) | CACHE: participants pay Enamine to synthesise and assay the compounds they nominate. The barrier to entry is a chemistry budget, and no compute tier expressed that |
| **Added `physical-venue-entry`** (compute_tier) | RoboCup, the A2RL Drone Championship. You ship hardware to a city on a date; that is a cost class of its own |
| **Added `wet-lab`** (compute_tier) | CACHE, OCx24, CASP's experimental ground truth. Paired with the `wet-lab` blocker and `requires-physical-experiment` |
| **Added `provided-allocation`** (compute_tier) | FAIR Universe HiggsML ships compute on Codabench with a NERSC Perlmutter allocation. A benchmark that removes the cost barrier is findable as one |
| **Added `human-panel`** (compute_tier) | MineRL BASALT, TTS listening tests, GDPval's blinded expert graders. The cost is rater time, not hardware |
| **Added `reproducibility_blockers[]`** (ten terms, multi-valued) | The archive had a tier and no reason. The tier says how hard; the blockers say why, which is the only form the runner-layer scoping in [13-execution-runners.md](13-execution-runners.md) can use |
| **Added `specific-simulator-build`** (blocker) | BEHAVIOR Challenge: the score is only defined inside one OmniGibson/Isaac-Sim build, so "reproducible" without a build hash is false |
| **Added `no-reference-implementation`** (blocker) | BetterBench's 17-of-24 finding turned into a field rather than left as a citation |
| **Added `live-world-state`** (blocker) | BizFinBench.v2's online tasks against live market platforms; ForecastBench's unresolved questions; Kaggle Game Arena's moving rating pool |
| **Added `est_participant_cost_usd`** | CACHE's compound purchases, RoboCup's shipping and entry, A2RL's travel. Every other estimate assumed the only cost was ours to model |
| **Deleted `inspect-evals-port`** (harness_availability) | It duplicated `inspect_evals_id`, so the enum and the id could disagree with nothing to catch it. Replaced by a derived boolean over the id, marked derived in §14 |
| **`basis` made mandatory on every range** | An estimate without its configuration is a score without its conditions. CI blocks a range with a null `basis`, and `source` is allowed to be null precisely so that `basis` cannot be |

---
## 11. Cross-cutting rules

1. **Primary domain is exactly one.** Multi-domain benchmarks list secondaries. The Atlas clusters on
   primary. The coverage matrix counts primary at weight 1.0 and secondary at **0.5** — a decision,
   published on the methodology page, revisable by ADR. A hidden weight is an unfalsifiable
   statistic.

   The weight is narrower than it looks and the archive never said what it applied to, which made
   "2.5 benchmarks in a cell" a readable output. Three clarifications, all of them constraints on
   what may be published:

   - **The weight applies to the cell *density* metric only.** It is published under the label
     **"weighted benchmark count"**, with the formula `density = n_primary + 0.5 × n_secondary`
     rendered on the methodology page next to every figure derived from it. It is never called a
     benchmark count, because 2.5 benchmarks do not exist.
   - **Cell *state* is determined by presence at any weight.** A cell with one secondary-tagged
     benchmark and no primary is `has-benchmarks`, not `surveyed-and-empty`. Rule 6's three states
     are categorical and the weight does not enter them — otherwise a 0.5 would have to round
     somewhere, and wherever it rounded would be a silent editorial decision.
   - **Integer counts are also published, unweighted, beside the density.** "4 primary, 3 secondary"
     is what a specialist wants and it is one more column. The density exists for the heatmap's
     colour scale; the integers exist for the claim.

2. **Capability terms are never inferred.** If the benchmark's own paper or site does not claim it
   tests causal reasoning, and no cited critique claims it, the index does not assert it.
   **Under-tagging is recoverable; over-tagging silently corrupts the gap analysis** — an
   over-inclusive tag fills a cell that should be empty, and empty cells are the product. Any tag not
   traceable to a cited source must be justified in `curation.notes`.

3. **No facet value may be written to `data/` by a model.** Machine-suggested facets arrive as
   suggestions in a draft PR carrying `provenance: machine-suggested` and require human confirmation
   before merge ([07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)). This is the
   taxonomy instance of the governing rule in [11-ai-features.md](11-ai-features.md): **the AI layer
   is a lens, never a source.**

4. **Subsets inherit then override, and the override is replace, not union.** An MMLU subject
   inherits MMLU's facets and may override any of them — which is what lets the coverage matrix count
   MMLU's college-chemistry subject as chemistry coverage rather than pure language coverage, a
   distinction that materially changes the gap analysis. Deep subset trees are permitted; two levels
   render by default.

   "Override" is ambiguous in exactly the way that matters for a multi-valued field, and the archive
   left it that way. The rules:

   - **Inheritance is field-by-field replace.** If a subset declares `capability:`, its list
     *replaces* the parent's list entirely for that subset. If it does not declare the field, it
     inherits the parent's list entirely. There is no union and no merge. Union was rejected because
     it makes DCASE's seven children multiply the parent's cell occupancy sevenfold; replace was
     chosen in full knowledge of its own hazard, which is that a curator who tags one term on a
     subset has silently dropped the three inherited ones. The mitigation is mechanical: CI warns
     when a subset declares a multi-valued facet with strictly fewer terms than its parent, and the
     warning names the dropped terms so the curator confirms the drop rather than discovering it.
   - **Inherited values are materialised into the build artifact.** The YAML stays sparse and
     diffable — a subset file contains only what differs — while `build/corpus.json` carries the
     fully resolved facet block for every subset. Nothing downstream ever walks the parent chain,
     which means the coverage matrix and the facet index cannot disagree about what a subset is.
   - **A subset contributes to the coverage matrix only if it carries a `domain_override`.**
     Otherwise the family counts once, at its own primary domain. DCASE is one family occupying one
     primary cell; its tasks 2 and 5, which carry `domain_override`, each add their own cell. Without
     this rule the audio row of the matrix would report seven benchmarks where the field has one.

5. **Families and children — decide once, before the first YAML file.** A **family** is a named
   benchmark identity (DCASE, BraTS, CASP, NTIRE, LifeCLEF, Matbench Discovery). **Children** are its
   editions, tasks, tracks and splits. **All counts published by this project are family counts**, and
   the site states so on every count. Counting children instead multiplies by roughly 3–6× and again
   by the number of editions — DCASE 2026 alone is 7 tasks across ~12 years. This is the single
   highest-leverage schema decision in the project and it is also the one that makes our numbers
   non-comparable to BenchmarkList's 2,545 or Benchmark Radar's 14,810 raw records. Say so plainly
   rather than competing on a count whose denominator nobody defines.

6. **Null is not empty.** `capability: []` means *not yet tagged*. There is no way to assert "this
   benchmark tests no capability". Consequently the coverage matrix has **three cell states**, not
   two: **has-benchmarks**, **surveyed-and-empty**, and **not-yet-surveyed**. Rendering the third as
   the second would make the project's headline output a lie. A cell becomes `surveyed-and-empty`
   only when a curator has recorded a dated survey note for that (domain, capability) pair — which
   makes "nobody is measuring this" a sourced claim like every other claim in the index. The same
   three states apply to the Domain browse spine; see the empty-subdomain rule at the end of §3.

7. **Closed enums, with `tags[]` as the escape hatch.** Undefined terms are a CI failure. `tags[]` is
   free text, searchable, and excluded from the coverage matrix. This is what keeps the enums clean
   without blocking a curator mid-entry.

8. **Every enum term carries `id`, `label`, `definition` and `examples[]`** in `taxonomy/*.yaml`, and
   the definitions are published on the site. Two or more `examples[]` per term, drawn from real
   catalogued benchmarks, because a definition without examples is re-interpreted by every curator
   who reads it.

   This rule, read together with rule 7, quietly demanded that every definition and every example
   exist before `taxonomy/` would validate — roughly 433 definitions and at least 866 examples, each
   example drawn from a benchmark that does not exist in the corpus yet. That is a circular
   dependency between the vocabulary freeze and the seed curation, and it would have gated the first
   green CI run on a month of writing. It is broken as follows:

   - **While `taxonomy/VERSION < 1.0.0`, `examples: []` is permitted and produces a CI *warning*,
     not a failure.** `definition` remains mandatory from the first commit — an undefined term is
     unusable and a curator will invent a meaning for it within a day.
   - **At the v1.0.0 freeze, fewer than two examples is a hard failure.** The build gate moves from
     warning to blocking at exactly the commit that tags the freeze.
   - **A term with fewer than two examples at the freeze is retired, not shipped undefined.** A term
     nobody could find two catalogued benchmarks for is a term with no entries, and the honest
     response is to remove it from the vocabulary and record the retirement — with the single, named
     exception of gap-matrix placeholders like `biology-genetics/phylogenetics`, which exist
     precisely to have no entries and which carry a dated survey note instead of examples. CI
     recognises placeholders by an explicit `gap_placeholder: true` flag, never by inference.

   The work is sized at the end of §14, because it is real work that no phase currently carries.

9. **Adding, retiring or re-grouping a term requires an ADR *and* a retro-tag plan.** The ADR must
   name which existing entries become candidates for the change and who will re-check them. Adding a
   term without the retro-tag pass leaves the coverage matrix reporting a gap that is an artefact of
   tagging history rather than of the field. This is the real cost of vocabulary growth and it is why
   the enums are closed. Process in
   [03-taxonomy-build-process.md](03-taxonomy-build-process.md).

   **Moving a capability term between capability groups (§4.3) also requires an ADR**, and this is
   the least obvious case, which is why it is spelled out. A re-group triggers *no* retro-tag pass —
   nothing in `data/` references a group id — and it is therefore tempting to treat as free. It is
   not: it silently re-shapes every published gap claim in both the origin and destination columns
   with no change to any benchmark record and no diff in `data/` to alert a reader. The ADR is the
   only audit trail such a change can have. `capability_groups.yaml` is versioned, its version is
   recorded in `build/derived/manifest.json`, and that version is cited with every published coverage
   figure so a re-grouping is attributable after the fact.

10. **Interop identifiers are fields, not facets.** `inspect_evals_id`, `epoch_benchmark_id`,
    `eee_benchmark_name`, `radar_id` (cross-reference only — Benchmark Radar's content is CC BY-NC-SA
    and must never be ingested into our CC-BY core), `pwc_task_id` (quarantined; the Papers with Code
    archive is CC-BY-SA and viral — see [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md)),
    `croissant_url`. They make us joinable; they are not part of the vocabulary. The field-by-field
    semantics of the EEE join are in the crosswalk at the end of §5.

11. **Identifiers are facet-scoped, not globally unique.** A subdomain id is always
    `family/subdomain`, and a subdomain leaf is unique across the whole domain vocabulary, not
    merely within its family. Every other facet's ids are bare slugs, unique within their facet
    file. Two facets may share a word — the field name says which vocabulary a value belongs to —
    but every such pair is declared in `taxonomy/homographs.yaml` with a rationale, and the
    coverage cell where the two meet is marked as occupied-by-construction rather than counted
    as evidence. Where a term is referenced *outside* a facet-typed field, it is written
    facet-qualified: `capability:planning`, `domain:reasoning-general/planning`. Enforced by CI
    checks 9c–9e in [05-repository-and-workflow.md](05-repository-and-workflow.md) §9. See D3 for
    why the old check 9c — asserting that the capability ids and the subdomain *leaf segments* are
    disjoint — was a category error rather than a failing check.

### Cross-field consistency

Six fields in this taxonomy can encode overlapping facts, and the archive gave no rule about which
wins or which combinations are meaningful. That is how a record ends up internally inconsistent
without any single field being wrong: worked example §12.10 correctly sets
`access: private-test-server`, `submission_process: held-out-server` and
`private-test-set ∈ reproducibility_blockers`, which means a curator who sets two of the three has
produced a record that reads as complete and is not. Name the failure mode: **a correct record and a
silently incomplete record are indistinguishable when the redundancy is undeclared.**

The near-synonym cluster is `lifecycle` / `activity` / `maintenance_status`. The authority rule:
**`lifecycle` is the instrument's standing and is the only one of the three the browse spine and the
`superseded_by` lineage read. `activity` describes the competition; `maintenance_status` describes
the code and data. Neither ever overrides `lifecycle`, and neither is a synonym for it.** The
legality matrix, which CI checks as a triple rather than field by field:

| `lifecycle` | `activity` | `maintenance_status` | Legal? | Reading |
| --- | --- | --- | --- | --- |
| `active` | `accepting-submissions` | `actively-maintained` | Yes | The ordinary live benchmark |
| `mature` | `leaderboard-live-no-round` | `actively-maintained` | Yes | Waymo, CARLA — the most common non-LLM state |
| `active` | any | `unobservable` | Yes | The expected modal state in CASP, CACHE, DCASE, grand-challenge.org |
| `active` | `closed` | `actively-maintained` | Yes | The competition ended; the artefact is maintained and cited (VoxSRC) |
| `dormant` | `closed` | `abandoned` | Yes | Fully dead, and the one case where all three agree |
| `mature` | `between-rounds` | `slow` | Yes | An annual challenge in its off-season with a quiet repo |
| any | `accepting-submissions` | `abandoned` | **Warning + note required** | An unattended auto-submission server. Real — it happens — but a curator must say so in `curation.notes`, because the alternative reading is that one of the two fields is wrong |
| `dormant` | `accepting-submissions` | any | **Blocking** | A dormant instrument cannot be taking entries. One of the two is wrong |
| `deprecated` or `retracted` | `accepting-submissions` | any | **Blocking** | Same contradiction, with a stronger claim on the lifecycle side |
| `saturated` | any | any | **Blocking if hand-set** | Derived only (§8). A hand-set `saturated` is a Tier-1 validation failure |

The remaining implications are single-direction and CI-enforced. "Blocking" means the PR does not
merge; "auto-fix offered" means the validation bot proposes the missing value in a review comment
rather than merging it silently, because rule 3 forbids a machine writing a facet value to `data/`.

| If | Then | Severity |
| --- | --- | --- |
| `lifecycle: contaminated` | `contamination_risk ∈ {high, confirmed}` **and** `contamination_evidence[]` non-empty | Blocking |
| `contamination_risk ∈ {high, confirmed}` | at least one `contamination_evidence[]` entry pointing at a `Source` | Blocking |
| `contamination_risk ∈ {high, confirmed}` | *no* implication toward `lifecycle` | — (deliberately one-way: a benchmark can be alive, useful and known-contaminated in one split. `contamination_risk` is authoritative for the evidence; `lifecycle: contaminated` is the stronger editorial consequence and requires the risk value, not the reverse) |
| `access: private-test-server` | `private-test-set ∈ reproducibility_blockers` | Blocking, auto-fix offered |
| `access: private-test-server` | `submission_process ∈ {held-out-server, containerized-algorithm-submission, assessment-committee}` | Warning + note (a private server with `self-reported` numbers is possible and worth explaining) |
| `data_provenance` contains `unreleasable-confidential` | `unreleasable-data ∈ reproducibility_blockers` | Blocking, auto-fix offered |
| `compute_tier: wet-lab` | `wet-lab ∈ reproducibility_blockers` **and** `reproducibility_tier: requires-physical-experiment` | Blocking, auto-fix offered |
| `harness_availability: none` | `no-reference-implementation ∈ reproducibility_blockers` | Blocking, auto-fix offered |
| `reproducibility_tier: fully-automatable` | `reproducibility_blockers` empty, or every blocker listed is `licence-restriction` | Blocking |
| `evaluation_method` contains `model-graded-judge` or `rubric-graded` | the `reference_conditions` block names a grader (model + version, or "human") | Blocking at `full` |
| `evaluation_method` contains `ordinal-grading`, `pairwise-preference-elo`, `tournament-play` or `episodic-return` | `headroom` is `null` | Blocking (§8 guard 4) |
| `evaluation_method` contains `pairwise-preference-elo` or `tournament-play` | `comparability.rating_pool_required: true` | Blocking, auto-fix offered |
| any `independence_flags` value other than `no-known-conflict` | an evidence `Source` | Blocking |
| `maintenance_status_contested: true` | `contested_source` and `contested_statement_date` both present | Blocking |
| any range estimate present | `basis` non-null | Blocking |

---
## 12. Worked classifications

**Ten stress cases (§§12.1–12.10), chosen adversarially rather than representatively, plus two
controls (§§12.11–12.12) from the dense and easy half of the corpus.** If the vocabulary survives the
ten, it has survived its hardest cases — which is a weaker claim than the archive made and the
correct one. Each block shows the complete facet assignment as it would appear in
`data/benchmarks/`, followed by what it stresses.

**The stress set is deliberately skewed and must not be used to estimate tag frequency.** D1 risk 11
makes this point against its own arithmetic and it belongs here, because this document owns the set:
there is no language, code or safety-alignment benchmark among the ten, which are three of the
densest parts of the real corpus, and `instruction-following`, `honesty`, `harm-avoidance`,
`collaboration`, `communication`, `autonomy` and `self-improvement` appear once or not at all. D1's
measured capability-group collapse factor of 3.30 — which sets the 247-cell grid's occupancy figures
now propagating into [12-analytics-and-trends.md](12-analytics-and-trends.md) — rests entirely on
these ten, and D1 flags it as its weakest input. **It must be re-validated against real tag
co-occurrence at ~200 entries at `full` completeness, before Phase 3 publishes the coverage map**, and
it could move by a third.

The two controls exist to exercise the terms the ten do not, and they are **deliberately excluded
from D1's collapse-factor measurement** — adding them would change a number another document owns
without re-deriving everything downstream of it. Re-deriving is D1's job at the 200-entry
re-validation, not this document's. Even with the controls, `honesty`, `collaboration`,
`communication`, `autonomy` and `self-improvement` remain unexercised by any worked example; the
first inter-rater run must include a benchmark for each, and the obvious candidates are MASK or a
TruthfulQA descendant for honesty, τ²-bench or MultiAgentBench for collaboration and communication,
METR's time-horizon suite for autonomy, and a self-improvement suite for the last.

### 12.1 CASP17 — blind protein structure prediction

```yaml
id: casp
name: CASP
domain:
  primary: biology-genetics/protein-structure-prediction
  secondary: [biology-genetics/nucleic-acid-structure, biology-genetics/protein-protein-interaction]
capability: [perception, abstraction, quantitative-reasoning, distribution-shift-generalization]
evaluation_method: [domain-metric, expert-panel-assessment]
designed_for_subjects: [domain-specialist-model, scientific-surrogate-model, human-ai-team, human-expert]
data:
  access: gated-registration
  refresh: periodic-recompetition
  data_provenance: [experimental-measurement]
  contamination_risk: low
  contamination_notes: |
    Targets are unreleased experimental structures on a rolling embargoed schedule.
    Structurally resistant; no evidence of leakage recorded.
  ceiling_anchor_type: expert-best
lifecycle: active
activity: round-scheduled
maintenance_status: unobservable
maintenance_status_notes: |
  No pollable dated signal. CASP publishes assessment papers on a multi-year cycle and
  runs no repository or dataset page we can probe. `unobservable` here means our
  instruments do not reach it, not that nobody is maintaining it.
governance:
  maintainer_type: academic-lab
  submission_process: assessment-committee
  independence_flags: [no-known-conflict]
execution:
  compute_tier: cluster
  reproducibility_tier: requires-physical-experiment
  reproducibility_blockers: [unreleasable-data, wet-lab]
  harness_availability: none
```

**Stresses:** no leaderboard at all — the output is peer-reviewed assessment papers, which forced
`expert-panel-assessment`. Editions, not versions. Dozens of category-specific metrics (GDT_TS, lDDT,
TM-score, DockQ, ICS/IPS), each a separate `Metric` ref. Human-expert groups ranked separately from
automated servers, which is why `human-ai-team` appears in `designed_for_subjects` and
`EvalConditions.human_in_loop` is material. CASP16 found single-domain fold prediction essentially
solved while more than 30% of oligomer targets — antibody-antigen especially — remain hard
(recon:domains, 2026-09-17), so a single `lifecycle` value for the family would be wrong; saturation
lives on the subsets. It is also the canonical `maintenance_status: unobservable` case, and the one
that proves why `unobservable` must never render as `abandoned`: CASP is one of the most durable
benchmarks in science and has no signal our probes can read.

### 12.2 RoboArena — distributed real-world policy evaluation

```yaml
id: roboarena
name: RoboArena
domain:
  primary: robotics-embodiment/manipulation
  secondary: [robotics-embodiment/cross-embodiment-transfer, robotics-embodiment/sim2real-transfer]
capability: [sensorimotor-control, grounding, instruction-following, distribution-shift-generalization]
evaluation_method: [physical-trial, human-expert-eval, pairwise-preference-elo]
designed_for_subjects: [rl-policy, physical-robot-system]
data:
  access: fully-open
  refresh: rolling-live
  data_provenance: [real-world-instrument]
  contamination_risk: low
  ceiling_anchor_type: none-known
lifecycle: active
activity: accepting-submissions      # live through Dec 2026 (recon:domains, 2026-09-17)
maintenance_status: actively-maintained
comparability:
  rating_pool_required: true
governance:
  maintainer_type: community-collective
  submission_process: physical-competition
  independence_flags: [maintainer-competes-on-own-benchmark]
execution:
  compute_tier: physical-hardware
  reproducibility_tier: requires-specialized-hardware
  reproducibility_blockers: [hardware-fleet, human-raters, live-world-state]
  harness_availability: reference-implementation-only
```

**Stresses:** there is no task list — evaluators choose their own tasks and scenes, then perform
double-blind pairwise comparisons of policy pairs on DROID hardware. No absolute score exists, so the
`Metric` is relative and `ceiling_anchor_type: none-known` is correct rather than a gap. Because the
method includes `pairwise-preference-elo`, §11's consistency rules force
`comparability.rating_pool_required: true` and §8 guard 4 forces `headroom: null` — a robotics
benchmark and an LLM arena hitting the same refusal path is the clearest evidence the rule is
about the scale rather than about the field. The maintainer is a distributed network of labs, which
is what `community-collective` is for. Reproducibility is blocked three ways at once, which is
exactly what `reproducibility_blockers[]` exists to say.

### 12.3 WeatherBench 2 — medium-range global weather forecasting

```yaml
id: weatherbench-2
name: WeatherBench 2
domain:
  primary: earth-climate/weather-forecasting
  secondary: [physics/simulation-surrogates]
capability: [quantitative-reasoning, probabilistic-forecasting, calibration-uncertainty,
             distribution-shift-generalization]
evaluation_method: [statistical-fit, domain-metric]
designed_for_subjects: [scientific-surrogate-model, classical-algorithm]
data:
  access: fully-open
  refresh: versioned-releases
  data_provenance: [real-world-instrument, simulation-generated]
  contamination_risk: medium
  contamination_notes: |
    ERA5 reanalysis is public and widely used in pre-training; the 2020 evaluation year
    is fixed. Risk recorded as medium without an evidence source, therefore not escalated.
  ceiling_anchor_type: operational-system
no_legitimate_aggregate: true
lifecycle: mature
activity: leaderboard-live-no-round
maintenance_status: actively-maintained
governance:
  maintainer_type: industry-lab            # Google Research, with ECMWF
  submission_process: self-reported
  independence_flags: [maintainer-competes-on-own-benchmark]
execution:
  compute_tier: multi-gpu-node
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
```

**Stresses:** the assumption that a benchmark has a ranking at all. Its authors explicitly describe it
as "a tool to compare different approaches on different aspects", not a challenge with one ranking —
which is our comparability thesis already validated in the wild by a first-rank institution, and is
why `no_legitimate_aggregate: true` exists as a field. The score is a grid of variable × pressure
level × lead time × metric; lead time is a condition, not a facet. `ceiling_anchor_type:
operational-system` records that the comparator is the IFS/ENS operational forecast, so "no human
baseline" is a correct statement about the benchmark rather than a hole in our data. Note that
`contamination_risk: medium` with no source is legal and `high` with no source is not — the
escalation threshold is exactly where the evidence requirement starts.

### 12.4 CACHE Challenges — prospective computational hit-finding

```yaml
id: cache-challenge
name: CACHE Challenges
domain:
  primary: chemistry-materials/experimental-hit-finding
  secondary: [chemistry-materials/generative-molecular-design, biology-genetics/drug-target-interaction]
capability: [search-exploration, experimental-design, hypothesis-generation, optimization]
evaluation_method: [wet-lab-validation, expert-panel-assessment]
designed_for_subjects: [domain-specialist-model, classical-algorithm, human-ai-team]
data:
  access: gated-registration
  refresh: periodic-recompetition
  data_provenance: [experimental-measurement]
  contamination_risk: low
  ceiling_anchor_type: none-known
lifecycle: active
activity: unknown          # per-round dates not published on the overview page (unverified)
maintenance_status: unobservable
governance:
  maintainer_type: nonprofit                # Conscience / SGC Toronto
  submission_process: assessment-committee
  independence_flags: [no-known-conflict]
execution:
  compute_tier: participant-funded-procurement
  reproducibility_tier: not-independently-reproducible
  reproducibility_blockers: [wet-lab, unreleasable-data]
  est_participant_cost_usd: {min: null, max: null, basis: "compound synthesis via Enamine; not published", source: null}
  harness_availability: none
```

**Stresses:** participants pick ≤100 compounds, the organisers buy them from Enamine and assay them,
and the top-10 teams advance to a hit-expansion round of ≤50 follow-ups. The metric is an
experimental hit rate plus affinity plus physicochemical properties plus a medicinal-chemistry
panel's qualitative commentary. Multi-year cycles across eight rounds. This is the entry that forced
`participant-funded-procurement` and `experimental-hit-finding`. Which round is currently open is
**unverified — confirm before relying on this**, which is why `activity: unknown` is a legal value
rather than a guess. It is also the case that justifies allowing `min: null, max: null` on a range:
the `basis` string carries real information ("not published") even when the bounds cannot.

### 12.5 Kaggle Game Arena (Chess) — all-play-all Elo

```yaml
id: kaggle-game-arena-chess
name: Kaggle Game Arena — Chess
domain:
  primary: games-planning/board-games
  secondary: [reasoning-general/planning]
capability: [planning, search-exploration, constraint-satisfaction, long-horizon-execution]
evaluation_method: [tournament-play, pairwise-preference-elo]
designed_for_subjects: [reasoning-model, instruction-tuned-model, agent-scaffold]
data:
  access: generated-on-demand
  refresh: rolling-live
  data_provenance: [synthetic-procedural]
  contamination_risk: low
  contamination_notes: |
    Games are played, not retrieved. The Chess Openings variant samples 20 openings
    from Lichess play, which is public; recorded but not escalated.
  ceiling_anchor_type: none-known
lifecycle: active
activity: accepting-submissions      # invitational roster
maintenance_status: actively-maintained
comparability:
  rating_pool_required: true         # a result is meaningless without pool identity + snapshot date
governance:
  maintainer_type: industry-lab      # Google DeepMind + Kaggle
  submission_process: live-arena
  independence_flags: [maintainer-competes-on-own-benchmark]
execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  reproducibility_blockers: [live-world-state]
  harness_availability: official-harness
```

**Stresses:** the rating is unbounded and pool-dependent — a model's number changes when a *different*
model joins, with no change to the model. Every stored claim must therefore carry rating-pool identity
and a snapshot date, and the comparison UI refuses to compare Elo across snapshots. This is the
cleanest case for the refusal behaviour: there is no honest way to put two Elo numbers from different
pools on one axis, and a catalogue that tries is manufacturing a comparison. 40 games per model pair,
20 as each colour, is a condition, not a facet. Note that the `domain.secondary` entry
`reasoning-general/planning` combined with `capability: [planning]` lands on one of the four
tautological-diagonal cells (§4.1) — correct tagging, and a cell the fine grid excludes from gap
ranking rather than counting as evidence.

### 12.6 Matbench Discovery — ML interatomic potentials for crystal stability

```yaml
id: matbench-discovery
name: Matbench Discovery
domain:
  primary: chemistry-materials/crystal-stability-discovery
  secondary: [chemistry-materials/force-fields-potentials, physics/condensed-matter]
capability: [quantitative-reasoning, distribution-shift-generalization, transfer-learning,
             perception]
evaluation_method: [domain-metric, statistical-fit, composite]
designed_for_subjects: [scientific-surrogate-model]
data:
  access: fully-open
  refresh: rolling-live
  data_provenance: [simulation-generated]
  contamination_risk: medium
  contamination_notes: |
    Handled structurally by the benchmark's own compliance tiers rather than by us:
    models are grouped by which training data they were permitted to use.
  ceiling_anchor_type: theoretical-maximum
training_data_eligibility_tiers:            # benchmark-level: the tier vocabulary this benchmark declares
  - {id: "compliant", label: "MPtrj only"}
  - {id: "non-compliant", label: "any training data"}
  source: src-matbench-discovery-terms
lifecycle: active
activity: accepting-submissions
maintenance_status: actively-maintained
governance:
  maintainer_type: individual        # Janosh Riebesell, with Materials Project hosting
  submission_process: maintainer-verified
  independence_flags: [no-known-conflict]
execution:
  compute_tier: multi-gpu-node
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
```

**Stresses:** one benchmark is stability F1 + energy MAE + phonons + κ_SRME thermal conductivity + MD
stability + diatomic PES sanity checks (recon:domains, 2026-09-17). More importantly it groups models
into **compliance tiers by what data they were allowed to train on** — a comparability constraint on
the *training* side, which no LLM-shaped schema has a slot for. Two schema consequences, and the
second is a correction to an earlier draft:

- **`EvalConditions.training_data_eligibility`** records, per claim, which tier the run declared.
  Required before the first YAML file; carried into [04-data-model.md](04-data-model.md).
- **`training_data_eligibility_tiers[]`** records, per benchmark, the tier vocabulary the benchmark
  itself publishes. This replaces the earlier draft's `eligibility_tiers: true`, which was a boolean
  that said only "tiers exist somewhere" — undefined anywhere in the schema, unactionable in the UI,
  and pointing at a note that was never written. A boolean cannot tell a reader which tier a number
  came from, which is the only thing that makes the number comparable.

**No standings are recorded in this document.** The June 2026 leaderboard had five models within
0.02 F1 of each other, and that is exactly the kind of fact that is wrong within a quarter and that
nobody re-checks in a taxonomy document. Standings live in the claim records with a `last_verified`
date, a `comparability_key` and a declared tier, which is where a reader can see whether they are
still true. The structural point survives without them: **a ranking here is only meaningful inside a
tier**, and a cross-tier table is a manufactured comparison.

### 12.7 ARC-AGI-3 — interactive novel-environment reasoning

```yaml
id: arc-agi-3
name: ARC-AGI-3
domain:
  primary: general-intelligence/novel-task-acquisition
  secondary: [games-planning/open-ended-environments, reasoning-general/abstraction-induction,
              multimodal/visual-grounding]
capability: [abstraction, search-exploration, planning, continual-learning, sample-efficiency,
             grounding]
evaluation_method: [simulation-rollout]
designed_for_subjects: [reasoning-model, agent-scaffold, tool-augmented-model, human-nonexpert]
data:
  access: train-open-test-held-out
  refresh: versioned-releases
  data_provenance: [expert-authored, synthetic-procedural]
  contamination_risk: low
  ceiling_anchor_type: crowd-average
lifecycle: active
activity: accepting-submissions      # ARC Prize 2026 on Kaggle, $2,000,000 pool
maintenance_status: actively-maintained
governance:
  maintainer_type: nonprofit
  submission_process: held-out-server
  independence_flags: [no-known-conflict]
execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
secondary_axes: [cost]
leaderboards:
  - id: lb-arc-agi-3-official     # unmodified general-purpose API systems
  - id: lb-arc-agi-3-community    # self-reported, harnesses permitted
```

**Stresses:** two leaderboards with **different legality rules**, which is the external validation of
the Subject-under-test facet. Humans solved all environments while every frontier model scored below
1% at the 25 March 2026 launch (recon:domains, verified 2026-09-17) — **headroom consumed of
essentially zero**, which is the opposite end of the saturation wall from GPQA Diamond and is why the
lifecycle derivation in §8 has to handle both extremes rather than only the top one. Per-model scores
are deliberately not reproduced here: they move weekly, they belong in the claim records with
`last_verified` dates, and a taxonomy document is the one place in the corpus nobody will ever
re-check them. ARC-AGI publishes **cost per task alongside the score**, which is
`secondary_axes: [cost]`, not a capability — the concrete case for retiring `efficiency-compute` in
§4.4.

### 12.8 ForecastBench — prospective forecasting

```yaml
id: forecastbench
name: ForecastBench
domain:
  primary: society-econ-law/forecasting-prediction-markets
  secondary: [reasoning-general/causal-inference]
capability: [probabilistic-forecasting, calibration-uncertainty, context-integration, knowledge-recall]
evaluation_method: [prospective-resolution, statistical-fit]
designed_for_subjects: [instruction-tuned-model, reasoning-model, agent-scaffold, human-expert,
                        human-nonexpert]
data:
  access: fully-open
  refresh: resolves-over-time
  data_provenance: [real-world-instrument]
  contamination_risk: low
  contamination_notes: |
    Questions have no answer at submission time. Structurally uncontaminable, which is
    the design intent.
  ceiling_anchor_type: expert-best      # superforecasters; crowd-average also recorded
lifecycle: active
activity: accepting-submissions
maintenance_status: actively-maintained
governance:
  maintainer_type: nonprofit           # Forecasting Research Institute
  submission_process: maintainer-verified
  independence_flags: [no-known-conflict]
execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  reproducibility_blockers: [live-world-state]
  harness_availability: official-harness
```

**Stresses:** `result_is_final` is false by construction. Scores resolve months to years later and are
retroactively updated, which forced both the `prospective-resolution` method and the claim-level
`resolution_status: pending | partial | resolved` — and, per §8, a `pending` claim is excluded from
SOTA until it resolves, which is the one case where a benchmark's headline number is legitimately
withheld from the headroom calculation. It also supplies two distinct human tiers (superforecasters
and the general public), which is why `Baseline` is a repeating entity rather than a single
field. The Metaculus AI Forecasting Benchmark Tournament is a sibling worth cataloguing separately:
recon:domains recorded on 2026-09-17 that professional forecasters still beat bots head-to-head by a
large margin each season while LLMs beat the average member of the public.

### 12.9 DCASE 2026 — one name, seven tasks

```yaml
id: dcase
name: DCASE Challenge
# FAMILY record. Children: dcase-2026-t1 … dcase-2026-t7, and one set per year.
domain:
  primary: audio-speech/audio-event-understanding
  secondary: [audio-speech/audio-event-detection-localization, audio-speech/machine-condition-monitoring,
              multimodal/audio-language]
capability: [perception, distribution-shift-generalization, continual-learning, context-integration]
evaluation_method: [domain-metric, statistical-fit, composite]
designed_for_subjects: [domain-specialist-model, instruction-tuned-model]
data:
  access: fully-open
  refresh: periodic-recompetition
  data_provenance: [real-world-instrument, expert-authored]
  contamination_risk: low
  contamination_notes: |
    A fresh evaluation set is released each year (2026: released 1 June).
  ceiling_anchor_type: none-known
lifecycle: mature
activity: between-rounds             # 2026 window: 1 Apr – 15 Jun, results 30 Jun 2026
maintenance_status: unobservable
governance:
  maintainer_type: community-collective
  submission_process: maintainer-verified
  independence_flags: [no-known-conflict]
execution:
  compute_tier: single-gpu
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
subsets:
  - {id: "dcase#2026-t2", label: "Noise-aware unsupervised anomalous sound detection",
     domain_override: {primary: audio-speech/machine-condition-monitoring}}
  - {id: "dcase#2026-t5", label: "Audio-dependent question answering",
     domain_override: {primary: multimodal/audio-language}}
  # … t1, t3, t4, t6, t7 — no domain_override, so they inherit and do not add matrix cells
```

**Stresses:** the family/children rule and the inheritance rule together. One named benchmark is seven
unrelated tasks, re-issued annually with a new evaluation set, and two of the seven belong in
different domains from the parent. Under §11 rule 4, **only the two children carrying
`domain_override` contribute cells to the coverage matrix**; the other five inherit and the family
counts once. Under union-style inheritance the audio row would report seven benchmarks where the
field has one, which is the arithmetic that makes the difference between replace and union worth a
paragraph. Per-task metrics are not published on the index page and are **unverified individually —
confirm before relying on this**. Counting DCASE as 1 or as 7 or as 84 (7 tasks × ~12 years) changes
the project's headline number by two orders of magnitude, which is the whole reason for rule 5.

### 12.10 Virtual Cell Challenge 2026 — zero-shot perturbation response

```yaml
id: virtual-cell-challenge
name: Virtual Cell Challenge
domain:
  primary: biology-genetics/perturbation-response-prediction
  secondary: [biology-genetics/single-cell-analysis, biology-genetics/transcriptomics]
capability: [distribution-shift-generalization, transfer-learning, quantitative-reasoning,
             sample-efficiency]
evaluation_method: [statistical-fit, composite]
designed_for_subjects: [scientific-surrogate-model, domain-specialist-model]
data:
  access: private-test-server
  refresh: periodic-recompetition
  data_provenance: [experimental-measurement]
  contamination_risk: low
  contamination_notes: |
    Zero-shot by design: there is deliberately no challenge-specific training set,
    and the six target cell lines are unseen.
  ceiling_anchor_type: experimental-replicate
no_legitimate_aggregate: false        # six metrics, each independently normalized, then combined
lifecycle: active
activity: accepting-submissions
maintenance_status: actively-maintained
governance:
  maintainer_type: nonprofit           # Arc Institute
  submission_process: held-out-server
  independence_flags: [prize-sponsored-by-industry]
execution:
  compute_tier: multi-gpu-node
  reproducibility_tier: requires-physical-experiment
  reproducibility_blockers: [private-test-set, wet-lab]
  harness_availability: official-harness
```

**Stresses:** the ceiling is a **real biological replicate experiment** and the floor is the
cell-context mean, so "human baseline" is meaningless and `ceiling_anchor_type:
experimental-replicate` is the only honest value. Six complementary metrics, each independently
scaled between those two anchors. Zero-shot by design — `EvalConditions.training_data_eligibility` is
"none", a stronger constraint than any LLM benchmark imposes. A $175k prize pool with NVIDIA, 10x
Genomics and Ultima sponsorship and 1,800+ registrants, protocol published in *Cell*
(S0092-8674(26)00931-1) (recon:domains, 2026-09-17). This is also the record that motivated the
cross-field consistency rules in §11: `access: private-test-server`,
`submission_process: held-out-server` and `private-test-set ∈ reproducibility_blockers` all encode
the same underlying fact, and a curator who set two of the three would have produced a record that
looks complete and is not.

### 12.11 SWE-bench Verified — control case from the dense half (code)

Not a stress case. It is here because the ten above contain no language, code or safety benchmark,
which are three of the densest parts of the real corpus, and a vocabulary that only ever demonstrates
itself on hard cases has not demonstrated that it is ordinary to apply. This entry should be boring,
and the fact that it is, is the finding.

```yaml
id: swe-bench-verified
name: SWE-bench Verified
variant_of: swe-bench                 # one of six forks; lineage is the point (see 04)
domain:
  primary: code/repository-scale-se
  secondary: [agents-tooluse/software-agents, code/bug-repair]
capability: [planning, long-horizon-execution, tool-use, context-integration, constraint-satisfaction]
evaluation_method: [execution-tests]
designed_for_subjects: [agent-scaffold, tool-augmented-model, reasoning-model]
data:
  access: fully-open                  # 500 human-validated instances
  refresh: static
  data_provenance: [web-scraped, expert-authored]   # real GitHub issues, human-filtered
  contamination_risk: high
  contamination_evidence: [src-swebench-contamination-...]
  contamination_notes: |
    Instances derive from public GitHub repositories with public fix commits, and the
    set is static. Escalated to `high` on the strength of a cited source, per the §7 rule;
    `high` without a source would be a build failure.
  ceiling_anchor_type: measured-ceiling
lifecycle: mature
activity: leaderboard-live-no-round
maintenance_status: actively-maintained
governance:
  maintainer_type: academic-lab        # Princeton NLP
  submission_process: self-reported
  independence_flags: [no-known-conflict]
execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
inspect_evals_id: swe_bench
inspect_evals_available: true          # DERIVED from inspect_evals_id != null
secondary_axes: [cost]
epoch_benchmark_id: "SWE-Bench verified"
eee_benchmark_name: null               # confirm against the EEE datastore before ingest
```

**What it exercises that the ten do not:** `execution-tests` as a lone method with no judge and no
rubric — the cleanest verifiability the vocabulary can express, and the baseline against which every
`model-graded-judge` entry should be read. `contamination_risk: high` **with** evidence, which is the
escalation path §7 describes and which none of the ten needed. `variant_of`, which is the lineage
relation differentiator 2 rests on: SWE-bench has six forks (original, Verified, Lite, Multimodal,
Multilingual, Pro; recon:landscape, 2026-09-17) and treating them as one benchmark or as six
unrelated ones are both wrong. Three interop identifiers populated at once, including one left
explicitly null rather than guessed. And `capability: [tool-use, long-horizon-execution]` landing in
`action-and-execution` alongside RoboArena's `sensorimotor-control` — which is D1 risk 1 made
concrete: this cell and RoboArena's cell are the same coarse cell, and that is the resolution loss
the coarse axis accepts.

### 12.12 AgentHarm — control case from the dense half (safety)

```yaml
id: agentharm
name: AgentHarm
domain:
  primary: safety-alignment/agentic-harm
  secondary: [safety-alignment/jailbreak-robustness, agents-tooluse/tool-api-calling]
capability: [harm-avoidance, instruction-following, tool-use, long-horizon-execution,
             adversarial-robustness]
evaluation_method: [model-graded-judge, adversarial-red-team]
designed_for_subjects: [agent-scaffold, tool-augmented-model, instruction-tuned-model]
data:
  access: restricted-dual-use
  refresh: static
  data_provenance: [expert-authored]
  contamination_risk: medium
  contamination_notes: |
    Public task set with a withheld portion. Recorded as medium without an evidence
    source, therefore not escalated.
  ceiling_anchor_type: theoretical-maximum    # refusal rate has a defined 100%
lifecycle: active
activity: leaderboard-live-no-round
maintenance_status: actively-maintained
governance:
  maintainer_type: government-agency    # UK AISI, with Gray Swan
  submission_process: self-reported
  independence_flags: [no-known-conflict]
execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  reproducibility_blockers: []
  harness_availability: official-harness
inspect_evals_id: agentharm
inspect_evals_available: true
no_legitimate_aggregate: true           # harm score and refusal rate are not one number
curation:
  notes: |
    `instruction-following` is tagged on the benign control subset, which the benchmark
    publishes as a capability control — not inferred from the harmful set. Per §11 rule 2,
    a tag that needs explaining gets one.
```

**What it exercises that the ten do not:** `harm-avoidance` and `instruction-following`, two of the
terms D1 flagged as absent from the stress set, and the `conduct-and-cooperation` capability group,
which the ten never touch. `access: restricted-dual-use` on a benchmark that is neither open nor
commercially closed. `maintainer_type: government-agency`, a governance mode the ten omit entirely
and which is increasingly the frontier-safety norm. `adversarial-red-team` alongside
`model-graded-judge`, which is the two-method case where the score's denominator moves — a
JailbreakBench-style drop with no change to the model — and where `no_legitimate_aggregate: true`
applies for a different reason from WeatherBench 2's: not too many dimensions, but two dimensions
that point in opposite directions. It is also the entry that shows a `curation.notes` justification
doing its job under rule 2 rather than the rule being quoted and never exercised.

### What the twelve forced — handoff to the data model

This is a handoff, not a summary. Every row is a field that
[04-data-model.md](04-data-model.md) must carry, and the **status column is the part that matters**:
C5 establishes that schema additions land *before* the first ingest, because retrofitting thousands
of machine-ingested records is painful and retrofitting a `comparability_key` is worse — every key
already computed becomes invalid.

| Field | Owning entity in 04 | Status |
| --- | --- | --- |
| `no_legitimate_aggregate: bool` | `Benchmark` | **Required before the first YAML file.** WeatherBench 2, ReXrank, VBench, AgentHarm |
| `EvalConditions.training_data_eligibility` | `EvalConditions` | **Required before the first YAML file.** Matbench Discovery, Virtual Cell |
| `training_data_eligibility_tiers[]` + `source` | `Benchmark` | **Required before the first YAML file.** Replaces the earlier `eligibility_tiers: true`, which is deleted — a boolean cannot say which tier a number came from |
| `comparability.rating_pool_required: bool` | `Benchmark.comparability` | **Required before the first YAML file.** Kaggle Game Arena, RoboArena |
| `submission_limit: {max_submissions, period_days, per, source}` | `Benchmark.data` | **Required before the first YAML file.** Shape fixed in §7; the archive's "boolean-plus-integer" had no period and no unit |
| `est_participant_cost_usd` (ranged, `basis` mandatory) | `Benchmark.execution` | **Required before the first YAML file.** CACHE, RoboCup, A2RL |
| `reference_conditions` (an `EvalConditions` ref) | `Benchmark` | **Required before the first YAML file.** §8's SOTA rule is undefined without it |
| `maintenance_status_contested`, `contested_source`, `contested_statement_date` | `Benchmark` | **Required before the first YAML file.** New in this revision; an automated death notice needs an appeal path from day one |
| `inspect_evals_available: bool` | `Benchmark.execution` | **Derived**, from `inspect_evals_id != null`. Replaces the deleted `harness-availability: inspect-evals-port` |
| `secondary_axes: [cost, latency, throughput, energy, reliability]` | `Benchmark` | Confirm against 04 — specified in §4.4's changelog; if absent, required before the first YAML file |
| `variant_of`, `superseded_by`, `BenchmarkVersion.breaking` | `Benchmark`, `BenchmarkVersion` | Confirm against 04 — differentiator 2 rests on these; SWE-bench's six forks and FrontierMath's four variants are the test |
| `domain_override` on a subset | `BenchmarkSubset` | **Landed.** DCASE; the coverage-matrix rule in §11 rule 4 depends on it |
| `resolution_status: pending \| partial \| resolved` | `ResultClaim` | **Landed.** ForecastBench, CAFA |
| `Baseline` (the archive's `HumanBaseline`, renamed and generalised in [04-data-model.md](04-data-model.md) §7) as a repeating entity | `Benchmark` | **Landed.** ForecastBench's two human tiers |
| `seed_target: int`, `core: bool`, `coverage_status: surveyed \| under-surveyed` | domain-family record in `taxonomy/domains.yaml` | **Required before the first YAML file** (D2). The muting mechanism and CI check 9f both read them |
| `curation_posture: hand-curate \| mixed \| ingest-then-verify` | domain-family record in `taxonomy/domains.yaml` | **Required before the first YAML file.** §3's posture column and [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10's must be the same value read from the same file, not two prose copies — which is exactly how they drifted on medicine-health before this pass. Check 9f extends to it |
| `gap_placeholder: bool` | taxonomy term record | **Required before the first YAML file.** §11 rule 8's freeze gate distinguishes a placeholder from an undefined term by this flag, never by inference |
| `ResultClaim.artifact_url`, `ResultClaim.provenance_snapshot`, `System.training_compute_flop` (+ estimated flag + notes), `EvalConditions.reasoning_effort` (enum + free text) | `ResultClaim`, `System`, `EvalConditions` | **Required before the first ingest** — settled by C5, listed here so the blocking set is complete in one place |

The four "Confirm against 04" rows are the honest state of this handoff: this document knows the
field is needed and does not know whether it has landed. Whoever next edits
[04-data-model.md](04-data-model.md) should close them and change the status, rather than leaving a
reader to guess.

---
## 13. What the taxonomy deliberately does not capture

Every taxonomy has a boundary. Stating it prevents endless expansion pressure, and expansion pressure
is how a two-person project acquires a schema it cannot maintain.

**Quality or goodness ratings.** No stars, no grades, no "recommended" badge. This is constraint 4:
not an editorial opinion site. BetterBench's 46-criterion rubric exists and is good prior art; where
they have assessed a benchmark we link to their assessment rather than issuing our own. The single
exception is `maintenance_status`, which is *measured* from observable repository, dataset and
leaderboard signals under the probe protocol in §8 and displayed with the evidence — a fact about
dates, not a judgement about worth, and one a maintainer can contest on the record.

**A universal difficulty or capability scale.** Epoch's ECI (a two-parameter IRT/Rasch model; the
anchor values reported as Claude 3.5 Sonnet at 130 and GPT-5 at 150 are *(unverified — confirm
before relying on this)*) and its EDI benchmark-difficulty parameter exist, as do BenchmarkList's
"Rosetta Stone" index and the Artificial Analysis Intelligence Index. We catalogue all of them as
objects and link out. We do not build one. The HuggingFace Open LLM Leaderboard was retired on
2025-03-14 with the stated reason that it "was becoming obsolete and could encourage people to
optimize in irrelevant directions" (recon:landscape, verified 2026-09-17) — the largest ranking
operator in open-source AI killed its own ranking for being harmful to the field, and that is the
most persuasive available argument for the position.

**Model and system capability rankings.** Not a model directory (constraint 5). `System` exists only
as the subject of a result claim, and there is no facet describing how good a model is.

**Dataset-level structure.** Columns, splits, file formats, feature types and record counts are
Croissant's job. Where a HuggingFace dataset backs a benchmark we store its `croissant_url`
(`huggingface.co/api/datasets/{name}/croissant`) and link. We describe the *benchmark* — tasks,
metrics, protocol, conditions — which is precisely the layer Croissant does not have and which the
proposed `croissant-benchmark` extension would occupy. The Croissant spec is CC BY-ND, so we may
publish a namespaced extension and must never republish a modified spec.

**Task-level content.** No items, no questions, no answers, no test data, ever. Constraint 1, and
also contamination hygiene: an index that mirrors test items becomes a contamination vector.

**Hardware and device benchmarks.** Metriq, the QED-C application-oriented quantum benchmarks, MLPerf
system benchmarks and SPEC evaluate devices and systems, not models. Admitting them would roughly
double the surface area and import an entirely separate community's vocabulary. Boundary recorded;
revisit by ADR if a genuine cross-over case appears (QML *algorithm* benchmarks are already in scope).

**Training datasets as such.** Open X-Embodiment is reported as 1M+ real trajectories across 22
embodiments from 21 institutions (recon:domains, 2026-09-17) — and it is a dataset, not a benchmark:
evaluation happens per-lab on each lab's own robots, so "results" are not comparable. It enters the
index as a linked `Resource`, referenced by the benchmarks that use it, never as a benchmark with a
leaderboard. Same for LibriSpeech, Common Voice, FLEURS, ORD and PLINDER.

**Popularity.** Citation counts, GitHub stars, download counts and paper velocity are derived metrics
([12-analytics-and-trends.md](12-analytics-and-trends.md)), not facets. They change daily; a
vocabulary that encoded them would be time-dependent, and a time-dependent vocabulary cannot support
a stable coverage matrix. The same reasoning is why §12.6 and §12.7 carry no leaderboard standings:
this is the one document in the corpus that cannot be regenerated, so volatile numbers put here are
numbers nobody will ever re-check.

**Psychometric capability ontologies.** Cattell-Horn-Carroll, g-factor decompositions and their
relatives are contested in their own field and importing one would embed a theory of intelligence
into what is meant to be a factual index. The Capability facet is deliberately pragmatic and
benchmark-derived: the terms are what benchmark authors claim to measure, not what a theory says
exists. The 13-group rollup in §4.3 is a readability device over those terms, not a claim about the
structure of cognition, and D1 says so in its own scoring.

**Language and locale as a facet.** `languages[]` is an ISO-code data field, not a controlled
vocabulary requiring curatorial judgement. The interesting finding — 165 of 195 safety benchmarks are
English-only *(unverified: from the withdrawn arXiv 2604.12875)* — is an analysis output over that
field, which is where it belongs.

**Regulatory mapping.** The EU AI Act's GPAI obligations became enforceable on 2026-08-02 and require
evaluation "using standard benchmarks and state-of-the-art tests" with no registry defining what
qualifies (recon:landscape, verified 2026-09-17). That is a real opportunity and COMPL-AI (ETH Zurich
/ INSAIT / LatticeFlow, arXiv 2410.07959) is the precedent. It is deliberately **not** a facet in v1:
regulation changes on a different clock from science, and a mapping baked into the core vocabulary
would either freeze or churn. It belongs as a derived overlay built on top of stable facets. Recorded
in [15-open-questions.md](15-open-questions.md).

---

## 14. Vocabulary summary

**This table is generated.** `scripts/taxonomy_stats.py` renders it from `taxonomy/*.yaml` and CI
check 9b fails on any diff, so a hand-edited count here is a build failure rather than a slowly
propagating error. That mechanism exists because the previous revision of this section carried a
hand-typed grand total that was arithmetically wrong and had been copied forward through three
revisions. **No grand total is typed in this document.** The number is computed at build time from
the files and published on the taxonomy page beside the `taxonomy/VERSION` it was computed from;
retyping a total is how a wrong one survives.

| Facet | Field | Terms | Required at | Derived? |
| --- | --- | --- | --- | --- |
| 1 Domain | `domain.primary` / `.secondary[]` | 19 families / 204 `(family, subdomain)` pairs | stub | no |
| 2 Capability | `capability[]` | 44 | full | no |
| | *capability group rollup* (§4.3) | 13 | — | **yes**, a partition of `capability[]`; never hand-tagged |
| 3 Evaluation method | `evaluation_method[]` | 27 | full | no |
| 4 Subject under test | `designed_for_subjects[]` | 18 | full | no |
| 5 Data properties | `data.access` | 9 | full | no |
| | `data.refresh` | 7 | full | no |
| | `data.data_provenance[]` | 11 | full | no |
| | `data.contamination_risk` | 5 | full | no (evidence required above `medium`) |
| | `data.ceiling_anchor_type` | 10 | full | no |
| 6 Lifecycle | `lifecycle` | 10 | stub | partly (`saturated` only, per §8) |
| | `activity` | 6 | full | no |
| | `maintenance_status` | 5 | — | **yes**, from the §8 probe protocol |
| | `maintenance_status_contested` | boolean, not a vocabulary | — | no (hand-set, source required) |
| 7 Governance | `governance.maintainer_type` | 9 | full | no |
| | `governance.submission_process` | 10 | full | no |
| | `governance.independence_flags[]` | 8 | full | no (evidence required) |
| 8 Execution | `execution.compute_tier` | 12 | full | no |
| | `execution.reproducibility_tier` | 6 | full | no |
| | `execution.reproducibility_blockers[]` | 10 | full | no |
| | `execution.harness_availability` | 3 | full | no |
| | `execution.inspect_evals_available` | boolean, not a vocabulary | — | **yes**, from `inspect_evals_id != null` |

That is **nineteen hand-tagged vocabularies across twenty vocabulary-valued fields, plus one derived
rollup, one derived boolean (`execution.inspect_evals_available`) and one hand-set boolean
(`maintenance_status_contested`, which requires a source).** Large enough to be useful and small enough that one person can
hold the shape of it — which is the right size for a two-person project, and the reason the additions
in this document were each traced to a named benchmark that the previous vocabulary could not
express.

Two deletions since the previous revision, both because a value was in the wrong field:
`maintainer_type: unmaintained` (a `maintenance_status` value; §9) and
`harness_availability: inspect-evals-port` (a duplicate of `inspect_evals_id`, now derived; §10).

### The definition-authoring pass, sized

§11 rule 8 requires `id`, `label`, `definition` and two or more `examples[]` on every term. Nobody
had costed that, and it is not small: with 204 subdomain terms and 229 non-subdomain hand-tagged
terms (the 19 families plus the 210 facet terms in the table above), the rule demands over four
hundred definitions and over eight hundred examples. Rule 8 now breaks the circular dependency —
`examples: []` warns rather than fails while `taxonomy/VERSION < 1.0.0` — but the writing still has
to happen, and a plan that leaves it unsized is a plan whose first milestone slips for a reason
nobody predicted.

| Pass | Terms | Rate | Hours | Phase |
| --- | --- | --- | --- | --- |
| Spine vocabularies: 19 families, 44 capability, 27 evaluation-method, 18 subject | 108 | 6–20 min | **11–36** | **Phase 0**, before curation starts |
| Remaining facet terms: access, refresh, provenance, contamination, ceiling anchor, lifecycle, activity, maintenance, governance, execution | 121 | 6–20 min | **12–40** | Phase 1, front-loaded |
| Subdomain terms | 204 | 4–10 min | **14–34** | Phase 1, as the entries that supply the examples land |
| Capability groups (§4.3) | 13 | — | **0** | Already written; D1 supplies the definitions verbatim |
| **Total** | **446 term records** (= 108 + 121 + 204 + 13, this column) | | **37–110 h** | |

Call it **40–110 person-hours**. Three things follow and all three are for
[14-roadmap.md](14-roadmap.md) to absorb:

- **It is not inside D2's 175–495 person-hour curation line**, which is per-entry work and was
  derived from a per-entry rate. These are two different jobs and adding them is the only honest
  treatment.
- **The Phase-0 slice (11–36 h) is on the critical path.** Curation cannot start against an
  undefined capability or evaluation-method vocabulary without producing exactly the inter-curator
  drift that [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §6 measures. One to two
  weeks at 20 h/week, before the first benchmark entry.
- **The rest should overlap curation, not precede it**, because the examples are supposed to come
  from catalogued benchmarks and cannot exist before them. Overlapped, it adds roughly one to two
  weeks to the serial path at the midpoint; run serially it would add four, which is the argument for
  overlapping it and for the pre-1.0.0 warning rather than the hard failure.

The rates are estimates from the definitions already written in §4.2 and D1 §3, not measurements —
*(unverified — re-derive from the actual rate at the 50-term checkpoint, which is the cheapest
calibration point in the whole plan)*. The hard tail is real and worth naming: a domain-metric term
like `crystal-stability-discovery` or a safety term like `restricted-dual-use` needs a literature
read, not a sentence, and those will land at the top of the range or above it.

Next: [03-taxonomy-build-process.md](03-taxonomy-build-process.md) for how these vocabularies get
built, tested for inter-curator agreement, governed and evolved without breaking the coverage matrix.
