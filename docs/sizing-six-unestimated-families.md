# Sizing the six families 02 §3 left unestimated

**P0-S10-T03, part 2. Drafted 2026-09-23 by an agent; a person must accept it (see the end).**

[02-taxonomy.md](../_plan/02-taxonomy.md) §3's seed table carries Tier-1, Tier-2 and ceiling
estimates for thirteen families and "not estimated ‡" for six: code, language, mathematics,
reasoning-general, multimodal and engineering-design. Its footnote calls those six rows "the only
part of the allocation with no external grounding" and makes sizing them a Phase 0 task. This is
that sizing.

## The result

| Family | Tier-1 (core) | Tier-1 with borderline | Tier-2 (estimate) | Ceiling (estimate) | Seed target | Seed vs Tier-1 |
| --- | --- | --- | --- | --- | --- | --- |
| code | 14 | 19 | ~40–70 | ~400–800 | 16 | **above core** (114%), below borderline |
| language | 33 | 43 | ~120–200 | ~2,000–5,000 | 14 | 42% of core |
| mathematics | 6 | 11 | ~25–45 | ~200–400 | 12 | **above both** (200% of core, 109% of borderline) |
| reasoning-general | 17 | 27 | ~50–90 | ~500–1,000 | 12 | 71% of core |
| multimodal | 25 | 39 | ~80–150 | ~1,000–2,000 | 12 | 48% of core |
| engineering-design | 22 | 25 | ~40–60 | ~80 | 12 | 55% of core |
| **Six-row total** | **117** | **164** | | | **78** | 67% of core |

**Seed targets are unchanged.** The column sums to 320 exactly as before and
`scripts/taxonomy_stats.py --check` passes. Whether any target should move is the owner's decision
(02 §3), and the two rows that need one are below.

**Tier-1 is sourced; Tier-2 and the ceiling are estimates.** Every Tier-1 family was checked
against a primary source fetched on 2026-09-23:
- 203 arXiv IDs were verified in one batch call to the arXiv export API, with each title checked.
- The rest are official sites and GitHub repositories, each of which returned HTTP 200.

Tier-2 and the ceiling rest on the registry counts below. They are stated as ranges and should be
quoted as estimates.

## What this changes in 02 §3

**Where to put it.** 02 §3 says no other document restates the per-family numbers, so these
figures belong in its table and footnotes. They are not re-typed here as a second source of
truth; this file is the evidence behind them. The owner of 02 should make these edits:

- **Fill the six "not estimated ‡" cells** from the table above.
- **Update the total row.** Tier-1 moves from "300 across 13 estimated rows" to roughly **417
  across all 19** (core), or **464** including borderline.
- **Rewrite the ‡ footnote's framing.** "320 is 242 of the recon's 300 … plus 78 entries across
  six domains nobody has sized" becomes: *78 entries against ~117 core Tier-1 families across six
  domains sized on 2026-09-23*. The footnote's warning that these rows are weaker than the other
  thirteen now holds only for the Tier-2 and ceiling estimates.
- **Correct the § footnote on engineering-design.** The miss risk it describes (fewer than twelve
  credible families) did not happen. The survey found 22 credible Tier-1 families after
  exclusions, or 25 strict ([data/surveys/engineering-design/_family-scoping.yaml](../data/surveys/engineering-design/_family-scoping.yaml)).
  So the family stays `coverage_status: surveyed`, is not muted, and no edit to
  `taxonomy/domains.yaml` is needed.
- **Drop two of its four named candidates.** AutoLabs is an application, not a benchmark.
  Blueprint-Bench 2 is a spatial-reasoning benchmark (apartment photos to floor plans), not an
  engineering-design one.

**Two rows break 02 §3's own rule.** The rule is that seed targets are adjusted down from the
Tier-1 estimates, and "nowhere else should a target equal its estimate" (only general-intelligence
is exempt).

- **mathematics: the target of 12 is above the Tier-1 estimate even with borderline families
  (11).** It cannot go lower, because 12 is the hard floor. The honest reading: mathematics seeds
  every Tier-1 family plus at least one Tier-2 entry. That is legitimate, but 02 should say so
  rather than implying volume, much as it already says for FrontierMath's variants.
- **code: the target of 16 is above the 14 core families.** Either count the 5 borderline families
  toward it, or move 2 entries elsewhere. language (14 against 33 core) is the obvious recipient,
  since its row is the most under-seeded relative to size.

Any change to a seed target is an edit to `taxonomy/domains.yaml` plus a regenerated table, not a
change to this file.

## How Tier-1 was decided

"Field-defining" means a benchmark family that a specialist would expect any serious catalogue to
contain. Evidence of standard-evaluation status came from four registries:
- **IE**: UK AISI Inspect Evals.
- **LM**: EleutherAI lm-evaluation-harness.
- **EP**: Epoch AI's benchmark hub.
- **HELM**: Stanford CRFM's HELM.

Where no registry lists a family, it rests on field history, and those are marked "none" in the
lists below. **They are the entries a reviewer should check first.** Two further rules applied:
- **Variants are merged per 02 §11.** For example, SWE-bench, Lite, Verified and Multimodal are
  one family.
- **Families that belong elsewhere in this taxonomy were excluded.** Agent and tool-use suites
  (Terminal-Bench, AgentBench) go to agents-tooluse. ARC-AGI, HLE and LiveBench go to
  general-intelligence. GPQA is ambiguous between knowledge and general-intelligence and is not
  counted.

The core-versus-borderline split is a judgement call, and it is the part of this sizing most open
to disagreement.

## Tier-1 families, per row

Format: name (merged variants), subdomain, primary source and first-release year, registry
evidence. "(B)" marks borderline.

### code (14 core, 5 borderline)

**Core:**
- HumanEval (+ HumanEval+). Function-synthesis. arXiv 2107.03374, 2021. IE, LM, HELM.
- MBPP (+ MBPP+). Function-synthesis. arXiv 2108.07732, 2021. IE, LM.
- SWE-bench (Lite, Verified, Multimodal). Repository-scale-se. arXiv 2310.06770, 2023. IE, EP. SWE-Bench Pro, by Scale AI, is kept separate as Tier-2.
- Aider Polyglot. Repository-scale-se. aider.chat/2024/12/21/polyglot.html, 2024. EP.
- Defects4J. Bug-repair. github.com/rjust/defects4j, 2014. None.
- APPS. Competitive-programming. arXiv 2105.09938, 2021. IE, HELM.
- CodeContests. Competitive-programming. arXiv 2203.07814, 2022. None.
- LiveCodeBench. Competitive-programming. arXiv 2403.07974, 2024. None. LiveCodeBench Pro, a different team's benchmark, is Tier-2.
- BigCodeBench. Function-synthesis. arXiv 2406.15877, 2024. IE, HELM.
- CodeXGLUE. Code-understanding. arXiv 2102.04664, 2021. LM.
- MLE-bench. ML-engineering. arXiv 2410.07095, 2024. IE.
- DS-1000. Data-science-workflows. arXiv 2211.11501, 2022. IE.
- Spider (+ 2.0). Data-science-workflows. arXiv 1809.08887, 2018. HELM.
- BIRD. Data-science-workflows. arXiv 2305.03111, 2023. HELM.

**Borderline (B):**
- CRUXEval. arXiv 2401.03065. LM.
- RE-Bench. arXiv 2411.15114.
- MultiPL-E. arXiv 2208.08227.
- KernelBench. arXiv 2502.10517. IE.
- SV-COMP. sv-comp.sosy-lab.org, 2012. It evaluates verifiers, not models.

**Subdomains with no core Tier-1:** program-verification, code-performance-optimization.

### language (33 core, 10 borderline)

**Understanding:**
- GLUE / SuperGLUE. arXiv 1804.07461, 1905.00537. LM, EP.
- MMLU (MMLU-Pro, MMMLU, Global-MMLU, MMLU-Redux). arXiv 2009.03300, 2020. IE, LM, EP, HELM, OLL. Arguably a knowledge family.
- SQuAD (+ 2.0). arXiv 1606.05250, 2016. IE, LM.
- DROP. arXiv 1903.00161, 2019. IE, LM.
- LAMBADA. arXiv 1606.06031, 2016. LM, EP.
- SNLI / MultiNLI. arXiv 1508.05326, 1704.05426. LM.

**Generation:**
- IFEval. arXiv 2311.07911, 2023. IE, LM, HELM, OLL.
- TruthfulQA. arXiv 2109.07958, 2021. IE, LM, HELM. Arguably safety-alignment.

**Dialogue:**
- MT-Bench. arXiv 2306.05685, 2023.
- Chatbot Arena / LMArena. arXiv 2403.04132, 2024.
- AlpacaEval (+ LC). github.com/tatsu-lab/alpaca_eval, 2023.
- MultiWOZ. arXiv 1810.00278, 2018.

**Summarization:**
- CNN/DailyMail. arXiv 1506.03340, 2015. LM, HELM.
- XSum. arXiv 1808.08745, 2018. HELM.

**Translation and multilingual:**
- WMT shared tasks. statmt.org, from 2006. LM, HELM.
- FLORES (-101, -200). arXiv 2106.03193, 2021.
- XNLI. arXiv 1809.05053, 2018. LM.
- XTREME (+ R). arXiv 2003.11080, 2020.
- TyDi QA. arXiv 2003.05002, 2020. LM.

**Long-context:**
- Needle-in-a-Haystack. github.com/gkamradt, 2023. IE.
- RULER. arXiv 2404.06654, 2024. LM.
- LongBench (+ v2). arXiv 2308.14508, 2023. LM.
- SCROLLS (+ ZeroSCROLLS). arXiv 2201.03533, 2022. LM.

**Retrieval-qa:**
- Natural Questions. ACL Anthology Q19-1026, 2019. LM, HELM.
- TriviaQA. arXiv 1705.03551, 2017. LM, EP.
- HotpotQA. arXiv 1809.09600, 2018.
- MS MARCO. arXiv 1611.09268, 2016. HELM.
- BEIR. arXiv 2104.08663, 2021.
- MTEB. arXiv 2210.07316, 2022.

**Information-extraction:**
- CoNLL-2003. arXiv cs/0306050, 2003.
- OntoNotes 5.0. LDC2013T19, 2013.
- ACE 2005. LDC2006T06, 2006.
- TACRED. nlp.stanford.edu, 2017.

**Borderline (B):** RACE, PersonaChat, Belebele, MasakhaNER, Long Range Arena, InfiniteBench,
SimpleQA, DocRED, WritingPrompts, Arena-Hard.

**Subdomain with no core Tier-1:** creative-writing.

### mathematics (6 core, 5 borderline)

**Core:**
- GSM8K (MGSM, GSM-Symbolic, GSM8K-Platinum, GSM-Plus). Arithmetic. arXiv 2110.14168, 2021. IE, LM, EP, HELM.
- MATH (MATH-500, MATH Level 5). Competition-math. arXiv 2103.03874, 2021. IE, LM, EP, HELM, OLL.
- AIME (yearly editions). Competition-math. The contest's page (maa.org) does not state a first year, so none is recorded. IE, LM, EP.
- miniF2F. Formal-theorem-proving. arXiv 2109.00110, 2021.
- PutnamBench. Formal-theorem-proving. arXiv 2407.11214, 2024.
- FrontierMath (Tiers 1–3, Tier 4, v2, Erdős). Research-level-math. arXiv 2411.04872, 2024. EP.

**Borderline (B):** ProofNet, DeepMind Mathematics Dataset, OlympiadBench, Omni-MATH, MathArena.

**Subdomains with no Tier-1:** applied-modeling, proof-verification. NL4Opt, which the
engineering-design survey turned up, is a candidate for applied-modeling.

### reasoning-general (17 core, 10 borderline)

**Commonsense:**
- HellaSwag (+ SWAG). arXiv 1905.07830, 2019. IE, LM, EP, HELM.
- WinoGrande. arXiv 1907.10641, 2019. IE, LM, EP.
- Winograd Schema Challenge. 2011. LM.
- PIQA. arXiv 1911.11641, 2019. IE, LM, EP, HELM.
- CommonsenseQA (+ CSQA2). arXiv 1811.00937, 2018. IE, LM, EP.
- Social IQa. arXiv 1904.09728, 2019. LM, HELM.
- ARC (AI2). arXiv 1803.05457, 2018. IE, LM, EP.

**Logical-deduction:**
- BIG-bench (BBH, BBEH). arXiv 2206.04615, 2022. IE, LM, EP, HELM, OLL.
- LogiQA (+ 2.0). arXiv 2007.08124, 2020. LM.
- bAbI. arXiv 1502.05698, 2015. LM, HELM.
- MuSR. arXiv 2310.16049, 2023. IE, LM, OLL.

**Causal-inference:**
- COPA. 2011. LM.

**Abstraction-induction:**
- PGM. arXiv 1807.04225, 2018.
- RAVEN. arXiv 1903.02741, 2019.

**Planning:**
- PlanBench. arXiv 2206.10498, 2022.
- International Planning Competition. icaps-conference.org, from 1998. It evaluates planners, not models.

**Theory-of-mind:**
- ToMi. ACL Anthology D19-1598, 2019.

**Borderline (B):** OpenBookQA, ReClor, FOLIO, ProofWriter/RuleTaker, CLadder, Tübingen pairs,
MC-TACO, TempEval, BigToM, FANToM.

**Subdomains with no core Tier-1:** temporal-reasoning, spatial-reasoning, counterfactual,
puzzle-solving. Blueprint-Bench 2, rejected from engineering-design, is a spatial-reasoning
candidate.

### multimodal (25 core, 14 borderline)

**Visual-qa:**
- VQA (v1, v2). arXiv 1505.00468, 2015. HELM.
- GQA. arXiv 1902.09506, 2019. HELM.
- OK-VQA (+ A-OKVQA). arXiv 1906.00067, 2019. HELM.
- TextVQA. arXiv 1904.08920, 2019.
- MMMU (+ Pro). arXiv 2311.16502, 2023. IE, LM, HELM.
- MathVista. arXiv 2310.02255, 2023. IE, HELM.
- MMBench. arXiv 2307.06281, 2023.
- MME. arXiv 2306.13394, 2023. HELM.
- POPE. arXiv 2305.10355, 2023. HELM.

**Visual-grounding:**
- RefCOCO family. arXiv 1608.00272, 1511.02283.

**Chart-diagram-understanding:**
- ChartQA. arXiv 2203.10244, 2022. LM.
- DocVQA (+ InfographicVQA). arXiv 2007.00398, 2020. IE.
- AI2D. arXiv 1603.07396, 2016.

**Video-language:**
- MSR-VTT. 2016. HELM.
- ActivityNet Captions. arXiv 1705.00754, 2017.
- Video-MME. arXiv 2405.21075, 2024. EP.

**Audio-language:**
- LibriSpeech. openslr.org/12, 2015. HELM.
- Common Voice. arXiv 1912.06670, 2019. LM, HELM.
- FLEURS. arXiv 2205.12446, 2022. HELM.
- CoVoST 2. arXiv 2007.10310, 2020. HELM.
- AudioCaps. ACL Anthology N19-1011, 2019. HELM.

**Generation:**
- GenEval. arXiv 2310.11513, 2023.
- VBench. arXiv 2311.17982, 2023.

**Cross-modal-retrieval:**
- MS COCO (+ Captions). arXiv 1405.0312, 2014. HELM.
- Flickr30k (+ Entities). ACL Anthology Q14-1006, 2014. HELM.

**Borderline (B):** CLEVR, ScienceQA, MM-Vet, SEED-Bench, CharXiv, EgoSchema, NExT-QA, MVBench,
Clotho, SUPERB, MMAU, T2I-CompBench, PartiPrompts, DrawBench.

**Subdomain with no Tier-1:** any-to-any-generation.

**Boundary note:** five of the audio-language entries are speech benchmarks, and 02 §11 rule 12
places pure ASR in audio-speech. **Classification decision for the reviewer:** decide whether
LibriSpeech, Common Voice, FLEURS and CoVoST 2 are multimodal at all. If they move to
audio-speech, multimodal falls to about 21 core families.

### engineering-design (22 core, 25 strict)

The full survey, with URLs, evidence grades, rejected candidates and scoping concerns, is in
[data/surveys/engineering-design/_family-scoping.yaml](../data/surveys/engineering-design/_family-scoping.yaml).
By subdomain (strict count):
- circuit-eda: 8
- cad-geometry-generation: 4
- structural-mechanical-design: 5
- process-control-optimization: 3
- experimental-apparatus-design: 1
- lab-automation-execution: 4

## Registry counts behind the Tier-2 and ceiling estimates

All taken on 2026-09-23. They can be reproduced from the URL and the counting rule given for each.

| Registry | Count | How |
| --- | --- | --- |
| Inspect Evals | 129 in-repo evals: Coding 21, Knowledge 22, Reasoning 20, Safeguards 21, Cybersecurity 13, Assistants 10, **Mathematics 7**, Scheming 6, **Multimodal 5**, Bias 2, Personality 1, Writing 1; plus 42 `register/*/eval.yaml` files with no `group:` | `src/inspect_evals/*/eval.yaml` from the git tree API, tallied on `group:` |
| lm-evaluation-harness | 221 top-level task folders; 201 rows in the tasks README table | `lm_eval/tasks` via the GitHub contents API |
| HELM | 173 non-test `*_scenario.py`; subfolders vision_language 30, audio_language 29, image_generation 18 | `src/helm/benchmark/scenarios` via the GitHub contents API |
| Epoch AI | `benchmark_metadata.csv` has **87** rows (59 `in_eci`) | epoch.ai/data/benchmark_data.zip |
| arXiv titles containing "benchmark" | cs.SE 782; code/coding/programming/software 641; cs.CL 4,695; "reasoning" 1,077 (all families); multimodal 1,949; mathematics 160 | arXiv search. **Upper-bound signal only:** it counts non-benchmark papers and misses datasets not titled that way |

**The Epoch row matters beyond this task.** The plan's Epoch figures (00 §8.1, 01 §12) come from
the 2026-09-16 drop, which had **81** metadata rows. Today's export has **87** and is publicly
downloadable. `scripts/epoch_audit.py` can therefore run against a current export today. It would
report differences, because it is a newer snapshot, and those differences are the drift since the
plan was written.

## Unverified, and what a reviewer should check

- **No primary source was fetched for these candidates**, and none is counted:
  - HMMT and IMO as evaluations
  - SWE-bench Multilingual
  - MRCR
  - Fiction.LiveBench and ProofBench
  - HumanEval-X
  - WebNLG and E2E NLG
  - DSTC
  - VizWiz
  - Winoground
  - ReferItGame
  - Kinetics
  - AudioSet
  - Dynamic-SUPERB
  - VoiceBench
  - NYT Connections
- **Model cards were not fetched,** so "reported in frontier model cards" is not used as evidence
  anywhere. It would probably promote several borderline families.
- **Check the "none"-evidence Tier-1 entries first.** They rest on field history alone: Defects4J,
  CodeContests, MT-Bench, HotpotQA, BEIR, MultiWOZ and the information-extraction corpora.

## Acceptance

This is `agent-draft`. A person accepts it with
`python _plan/_workflow/scripts/next_task.py approve P0-S10-T03 --by NAME` after checking the
engineering-design finding (22 credible, not muted) and the two seed-rule exceptions above.
