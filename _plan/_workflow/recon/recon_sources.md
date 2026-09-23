Research complete. Everything below was probed live on **2026-09-17** unless marked otherwise.

---

# SOURCING & SCRAPING CATALOGUE — Universal AI Benchmark Index

**Verification method:** live HTTP probes (curl) + doc reads. Every rate limit, endpoint and licence below was either observed in a response header/body today or read off the vendor's own page today. Anything I could not confirm is marked **UNVERIFIED**.

---

## 0. HEADLINE CHANGES SINCE MID-2025 (things a stale plan will get wrong)

1. **Papers with Code is dead.** `paperswithcode.com` now 301-redirects to `https://huggingface.co/papers/trending` (confirmed today). Retired by Meta July 2025.
2. **OpenAlex moved to metered, key-required API (announced Jan 2026, enforced ~Feb 13 2026).** Free is no longer "100k credits/day". See §3 for the headers I measured.
3. **OpenReview's API2 now returns an anti-bot challenge (HTTP 403 `ChallengeRequiredError`) to anonymous clients.** Confirmed today. Do not plan on it.
4. **HuggingFace has grown a formal leaderboard/benchmark tag taxonomy** (`test:public`, `submission:automatic`, `judge:auto`, `eval:code`, `benchmark:official`…). This is the single highest-leverage discovery surface for this project and it did not exist in this form earlier. See §2.
5. **Semantic Scholar's unauthenticated tier is effectively dead** — I got a 429 on the *first* request today.
6. **Cloudflare Workers Free gives 10 ms CPU per cron trigger.** That rules it out for scraping (see §13b).

---

## 1. arXiv

**Base:** `https://export.arxiv.org/api/query` (Atom XML) · `https://oaipmh.arxiv.org/oai` (OAI-PMH) · `https://rss.arxiv.org/rss/{cat}`

### 1a. Query API
- **Mechanism:** REST, Atom 1.0. **Must use HTTPS** — `http://export.arxiv.org/...` returns 301 and silently yields an empty body if you don't follow redirects. (I hit this; it cost me two probes.)
- **Example (verified working):**
  ```
  GET https://export.arxiv.org/api/query
      ?search_query=cat:cs.CL+AND+abs:%22benchmark%22
      &start=0&max_results=100
      &sortBy=submittedDate&sortOrder=descending
  ```
  Date-window form (verified): `submittedDate:[202609100000 TO 202609170000]`
- **Auth:** none. **Rate limit (ToU, `info.arxiv.org/help/api/tou.html`):** *"Make no more than one request every three seconds, and limit requests to a single connection at a time."*
- **Licence:** metadata is **CC0 1.0** — *"You are free to use descriptive metadata about arXiv e-prints under the terms of the Creative Commons Universal (CC0 1.0) Public Domain Declaration."* Must not represent the project as arXiv-endorsed.
- **robots.txt:** `Crawl-delay: 15`; `Allow: /abs /list /pdf /html /catchup`; `Disallow: /e-print /src /find /refs /cits /format`. Header comment: *"Indiscriminate automated downloads from this site are not permitted."*
- **Update frequency:** new announcements daily; RSS `lastBuildDate` today = `Thu, 17 Sep 2026 04:00:15 +0000`, `skipDays: Saturday, Sunday`.

### 1b. OAI-PMH (the right tool for incremental harvest)
- `https://oaipmh.arxiv.org/oai?verb=Identify` → `earliestDatestamp 2005-09-16`, `deletedRecord persistent`, `granularity YYYY-MM-DD`.
- Old `http://export.arxiv.org/oai2` 301s here.
- **Sets are coarse** — `ListSets` top-level: `cs`, `math`, `physics`, `q-bio`, `stat`, `eess`, `econ`, `q-fin` (plus `physics:astro-ph` etc.). **There is no `cs.CL` set.** BUT each record's `<header>` carries subcategory setSpecs (`cs:cs:AI`, `cs:cs:RO`), and `arXivRaw` metadata carries `<categories>cs.AI cs.RO</categories>`. So: harvest `set=cs` and filter client-side.
- **Measured volume:** `verb=ListRecords&metadataPrefix=arXivRaw&set=cs&from=2026-09-16&until=2026-09-16` → **3.1 MB, 1,157 records** for one day. Note `from`/`until` are on **datestamp (modification)**, so you get v2 resubmissions of 2013 papers mixed in — the first record I pulled was arXiv 1304.3111 from 2013.
- Policy in the Identify response: *"Metadata harvesting permitted through OAI interface"* / *"Full-content harvesting not permitted (except by special arrangement)."*

### 1c. Bulk
- Kaggle `Cornell-University/arxiv` — live today (HTTP 200). Full metadata JSON dump, refreshed periodically. Needs a Kaggle token.
- S3 requester-pays buckets exist for PDF/LaTeX **— we don't want these** (we're metadata-only).

### 1d. Benchmark-paper detection: **measured precision/recall, not guessed**
Window 2026-09-10 → 2026-09-17, categories `cs.CL ∪ cs.LG ∪ cs.CV ∪ cs.AI`:

| Filter | Papers in 7 days |
|---|---|
| (no filter) | **2,315** |
| `abs:"benchmark"` | **670** (~29% of all papers — useless alone) |
| `ti:"benchmark"` | **103** |
| `ti:"benchmark" OR ti:"bench" OR ti:"eval"` | **114** |
| cs.CL alone, no filter | 509 |

All-time `cat:cs.CL AND abs:"benchmark"` = **28,905**.

I then hand-read 40 most-recent `cs.CL AND abs:"benchmark"` titles against the regex
`\b(we (introduce|present|propose|release|construct|curate)|this paper introduces)\b.{0,120}?\b(benchmark|dataset|suite|testbed|eval)\b`:
- 13/40 flagged. On manual read, **~8 were genuine new-benchmark releases → precision ≈ 60%.**
- **≥3 genuine benchmarks were missed** (`ScienceIDE`, `TeleAntiFraud 2.0`, `Behavior2Value`) → **recall ≈ 70%.**
- Classic false positives: method papers that merely *evaluate on* benchmarks ("Dual-View Relational Learning for **Efficient Agent Benchmarking**"), and meta-analyses ("Fallacy Benchmarks **Measure** Scheme Recognition, Not Fallacy Detection").
- Title-only filtering misses `*Bench` neologisms (`ReFigBench`, `TeochewBench`) because arXiv's tokenizer doesn't split camel/compound tokens.

**Realistic expectation to write into the plan:** a keyword prefilter gives you ~100–670 candidates/week for the four big CS categories. An LLM triage pass over abstracts is mandatory. Budget **~15–95 LLM calls/day**. Expect **~60% precision / ~70% recall** from heuristics alone, and roughly **85–90% precision** after an LLM classifier with a strict rubric ("does this paper *release* an evaluation artifact, vs. use one?"). Cross-domain categories (`q-bio`, `physics.comp-ph`, `astro-ph.IM`, `cond-mat.mtrl-sci`, `eess.AS`) have far lower base rates — use `abs:` filters there, the volume is manageable.

**Populates:** `benchmarks` (name, abstract, release date, authors, domain from category), `sources` (arXiv ID → DOI `10.48550/arXiv.NNNN.NNNNN`), `organizations` (author affiliations — noisy, arXiv metadata has no structured affiliation field).
**Fragility:** very low. arXiv API has been stable for 15+ years. The only real break risk is the HTTPS/redirect trap and the 3s throttle.

---

## 2. HuggingFace Hub — **the single best source for this project**

**Base:** `https://huggingface.co/api/…` · OpenAPI spec at `https://huggingface.co/.well-known/openapi.json` (and `.md` for agents).

- **robots.txt (checked today):** `User-agent: *` / `Allow: /` — fully permissive. Sitemap at `/sitemap.xml`.
- **Auth:** none required for public read. A free `HF_TOKEN` doubles your limit and is strongly recommended.
- **Rate limits (from `huggingface.co/docs/hub/rate-limits`, "current … in September '25", fixed **5-minute** windows, per IP for anon):**

  | Plan | API | Resolvers | Pages |
  |---|---|---|---|
  | Anonymous (per IP) | **500** | 3,000 | 100 |
  | Free user | **1,000** | 5,000 | 200 |
  | PRO | 2,500 | 12,000 | 400 |
  | Enterprise | 6,000 | 50,000 | 600 |

  429 responses carry `RateLimit` and `RateLimit-Policy` headers per `draft-ietf-httpapi-ratelimit-headers`. `huggingface_hub` ≥ 1.2.0 auto-parses and sleeps exactly. **Use the library, not raw curl.**
- **Pagination:** cursor in `Link: <…&cursor=…>; rel="next"`. `limit` up to 1000 works (verified). `full=true` inflates the payload heavily.

### 2a. The benchmark/leaderboard tag taxonomy — **this is the differentiator gift**
`GET /api/spaces?filter=leaderboard&limit=1000` paginated → **1,019 Spaces** tagged `leaderboard` (counted today). Empirically enumerated tag vocabulary from the first 1,000:

| Namespace | Values (count in sample) |
|---|---|
| `test:` | `public` (110), `private` (18) |
| `submission:` | `manual` (39), `automatic` (27), `semiautomatic` (10) |
| `judge:` | `auto` (73), `function` (17), (`vlm-judge` 4) |
| `eval:` | `code` (76), `generation` (47), `math` (30), `safety` (15) |
| `modality:` | `text` (79) |
| `language:` | `english` (29 + 22 cased variant), `polish` (6), `japanese` (4), `korean` (4)… |
| `domain:` | `financial` (10) |
| free tags | `benchmark` (92), `evaluation` (42), `arena` (7), `agents` (7), `rag` (4), `chemistry` (5), `ocr` (7), `asr` (13) |

**This maps almost 1:1 onto the project's `comparability_key` and `leaderboards` entity.** `test:public` vs `test:private` is contamination-status. `judge:auto` is the judge-model field. `submission:automatic` is the verification posture. Import the vocabulary rather than inventing one.

Note the `language:english` / `language:English` case split — normalisation needed.

**Caveat:** the taxonomy is *self-declared by Space authors* and sparsely applied (only ~11% of leaderboard Spaces carry `test:*`). Treat as a hint with a `source: hf_space_tag` provenance stamp, never as ground truth.

### 2b. Dataset-side tags
- `?filter=benchmark:official` → **47 datasets** (top by downloads: `openai/gsm8k` 1.25M dl, `TIGER-Lab/MMLU-Pro` 246k, `harborframework/terminal-bench-2.1` 132k, `Idavidrein/gpqa` 128k, `harborframework/terminal-bench-3.0` 128k).
- `?filter=benchmark:eval-yaml` → **48 datasets**. `benchmark:community` → 0.
- `?filter=croissant` → 203.

**High precision, low recall — a curated seed list, not a discovery mechanism.** Use it to bootstrap and to cross-check.

### 2c. Per-dataset detail
`GET /api/datasets/{owner}/{name}?full=true` returns: `lastModified`, `downloads` (30-day), `likes`, `tags[]` (incl. `license:mit`, `arxiv:2110.14168`, `size_categories:`, `modality:`, `task_categories:`), `cardData` (the YAML front-matter of the dataset card), `description`, `siblings[]` (file list), `gated`, `disabled`, and — still present — **`paperswithcode_id`** (e.g. `"gsm8k"`), which lets you join HF ⇄ the PwC archive dumps.

`GET /api/datasets/{id}/croissant` → **MLCommons Croissant JSON-LD** (verified 200 on `openai/gsm8k`). Same standard NeurIPS D&B now mandates. Good normalisation target.

### 2d. Other endpoints verified today
- `/api/models?sort=createdAt&direction=-1&limit=N` — model firehose (returns models created minutes ago).
- `/api/daily_papers?limit=N` — the successor to PwC "Trending Papers"; returns paper id, authors (with claimed/verified HF user links), etc.
- `/api/collections/{namespace}/{slug}` — e.g. `clefourrier/leaderboards-and-benchmarks-64f99d2e11e92ca5568a7cce` → **79 curated leaderboard items**, lastUpdated 2026-03-02.
- `/api/spaces?search=leaderboard&sort=likes&direction=-1` — top by likes today: `open-llm-leaderboard/open_llm_leaderboard` (14,112 likes), `mteb/leaderboard` (7,673), `lmarena-ai/arena-leaderboard` (4,993), `DontPlanToEnd/UGI-Leaderboard` (2,056), `bigcode/bigcode-models-leaderboard` (1,519).

**Populates:** `benchmarks` (name, url, licence, size, modality, task category, arXiv link), `leaderboards` (Space + its tags), `result claims` (via leaderboard result datasets, e.g. `open-llm-leaderboard/results`, `open-llm-leaderboard/contents`), `systems` (models), `organizations` (HF orgs), adoption signal (`downloads`, `likes`).
**Fragility:** low for the API shape; **medium for tags** (author-controlled, can vanish). The `benchmark:*` tag namespace is new and could be renamed.

---

## 3. OpenAlex — **re-plan this; it is now metered**

**Base:** `https://api.openalex.org`

**Measured today, unauthenticated, from a clean IP:**
```
X-RateLimit-Limit: 1000            # credits/day
X-RateLimit-Limit-USD: 0.1         # $0.10/day budget
X-RateLimit-Remaining: 999
X-RateLimit-Cost-USD: 0.0001       # a /works?filter= list call
X-RateLimit-Cost-USD: 0.001        # a *.search: call
X-RateLimit-Prepaid-Remaining-USD: 0
X-RateLimit-Reset: 50992           # seconds
```
So **unauthenticated ≈ 1,000 list calls/day or 100 search calls/day.**

**Documentation is inconsistent — flag this in the plan:**
- The OpenAlex **blog** ("New Features and Usage-Based Pricing") says: API key required for all requests; keys free, ~30s to obtain; **$1/day free** = unlimited singleton lookups, 10,000 list/filter calls, 1,000 search calls, 100 PDF/XML downloads. Costs: singleton $0, list/filter $0.0001, search $0.001, PDF/XML $0.01.
- The **docs repo** (`ourresearch/openalex-docs`, stale) still says 100,000 credits/day free, 100 req/s, no key needed.
- **My live measurement (no key): $0.10/day, 1,000 credits.** ⇒ **Get a free API key. It is a 10× budget difference.**

Credit table from docs: singleton 1, list 10, content 100, vector 1,000, text/aboutness 1,000.

**Polite pool:** `?mailto=you@example.com` or a `User-Agent` with contact info. Still honoured.

**Bulk snapshot remains free** — "all 480M works, all the metadata — free to download, share, remix". That is the correct ingestion path for us (see tiering).

### arXiv → OpenAlex resolution: **it is unreliable, and I have proof**
- `GET /works/doi:10.48550/arXiv.2303.08774` → **404**. `?filter=doi:10.48550/arxiv.2303.08774` → **0 results**. (GPT-4 Technical Report is not indexed under its arXiv DOI; a title search maps it to `W4327810158` with an unrelated DOI `10.4230/lipics.cosit.2024.11`.)
- Worse — record **`W4387561453`** has:
  - `doi: https://doi.org/10.48550/arxiv.2310.06770` ✅ (the real SWE-bench paper)
  - `authorships: Jimenez, Carlos E.; John Yang; Alexander Wettig; Shunyu Yao; Kexin Pei` ✅
  - `publication_date: 2023-10-10` ✅
  - `display_name: "Persistent memory for AI coding agents: a pre-registered SWE-bench Verified benchmark"` ❌ **wrong title**
  - `cited_by_count: 53` ❌ **off by orders of magnitude** for SWE-bench

**Conclusion for the plan:** OpenAlex is usable for *topic/concept* tagging and for finding peer-reviewed venue versions, but **its citation counts for arXiv preprints are not trustworthy and its titles can be corrupted**. Never surface an OpenAlex citation count as a headline "influence" number without a second source. This is exactly the kind of quietly-wrong data that would destroy the index's credibility.

**Populates:** `citations` (with a caveat flag), `sources` (venue, DOI, OA status), `organizations` (`institutions` with ROR IDs — this part *is* good), topic/concept tags for the coverage matrix.
**Fragility:** **high right now** — pricing model changed mid-flight in 2026 and docs disagree with live behaviour.

---

## 4. Semantic Scholar (S2 / Academic Graph)

**Base:** `https://api.semanticscholar.org/graph/v1`

- **Tested today unauthenticated:** `GET /paper/arXiv:2310.06770?fields=title,year,citationCount,externalIds,openAccessPdf` → **HTTP 429 on the first request**: `{"message": "Too Many Requests. Please wait and try again or apply for a key…"}`. The unauthenticated pool is documented as "1000 requests per second **shared among all unauthenticated users**" — i.e. globally contended and practically unusable.
- **With a key:** documented introductory limit **1 RPS on all endpoints**. Key request form at `https://www.semanticscholar.org/product/api#api-key-form`; arrives by email. Turnaround **UNVERIFIED** (community reports days-to-weeks; I did not confirm).
- **What it adds over OpenAlex:** (a) native `arXiv:` ID lookup as a first-class external ID — no DOI guessing; (b) `tldr` auto-summaries; (c) generally cleaner citation counts; (d) **S2AG / S2ORC bulk datasets** (Datasets API) which are the sane path at our scale.
- **Licence:** S2 Datasets carry an **API License Agreement** at `semanticscholar.org/product/api/license`; the released corpora are **ODC-BY 1.0** — **UNVERIFIED for 2026**, check before redistributing derived fields. Attribution required.
- **Populates:** `citations`, `sources`, arXiv↔DOI↔venue resolution.
- **Fragility:** medium. 1 RPS means a full backfill of 5,000 benchmark papers takes ~1.5 hours — fine. Real-time lookups per page view: no.

**Recommendation: use S2 for arXiv→paper identity resolution (better than OpenAlex), use OpenAlex for institution/ROR and topic concepts, and cite both.**

---

## 5. Papers with Code — **dead, but the corpse is licensed and useful**

- `https://paperswithcode.com/` → **301 → `https://huggingface.co/papers/trending`** (confirmed today). Retired by Meta, July 2025.
- **Archive lives at the HuggingFace org `pwc-archive`.** Verified via `GET https://huggingface.co/api/datasets?author=pwc-archive&full=true`:

| Dataset | Rows | Last modified | Licence tag |
|---|---|---|---|
| `pwc-archive/papers-with-abstracts` | 576k | **2026-08-17** | `cc-by-sa-4.0` |
| `pwc-archive/links-between-paper-and-code` | 300k | 2025-09-10 | `cc-by-sa-4.0` |
| `pwc-archive/datasets` | 15k | 2025-09-10 | `cc-by-sa-4.0` |
| `pwc-archive/methods` | 8.73k | 2025-09-10 | `cc-by-sa-4.0` |
| **`pwc-archive/evaluation-tables`** | **2.25k** | 2025-09-13 | `cc-by-sa-4.0` |
| `pwc-archive/files` | 338 | 2025-09-14 | `cc-by-sa-4.0` |
| `pwc-archive/pwc-paper-redirects` | 70 | 2025-12-12 | `cc` |

- **`evaluation-tables` is the one you want**: ~1,500 leaderboards / 1,000+ tasks / SOTA rows, the original task taxonomy.
- **Licence confirmed: CC-BY-SA-4.0** on the HF repo tags. ⚠️ **SA is viral.** If you ingest PwC task taxonomy verbatim into your YAML, a strict reading obliges your derived taxonomy file to be CC-BY-SA too — which **conflicts with your stated CC-BY licence for the index**. Mitigation: use PwC only as a *reconciliation/seed* source (match names, then re-derive your own descriptions from primary sources), and keep any verbatim PwC text in a separately-licensed `vendor/pwc/` directory with its own LICENSE. **Get this decision into the plan explicitly — it's a real legal fork in the road.**
- The direct `huggingface.co/datasets/pwc-archive/paperswithcode-data` page 401s (that exact repo name doesn't exist); use the API listing above.
- Mirrors also exist (`World-Snapshot/papers-with-code` on GitHub, `codesota.com`) — **UNVERIFIED** provenance, don't depend on them.

**Populates:** `benchmarks` (historical long tail, pre-2025), `leaderboards`, `result claims` (historic SOTA), task taxonomy for the coverage matrix.
**Fragility:** zero — it's a frozen snapshot. That's also its weakness: **nothing after ~Sept 2025**, so it is a backfill source only.

---

## 6. GitHub API

**Base:** `https://api.github.com` (REST v3) · `https://api.github.com/graphql`

**Rate limits (verified from live headers + docs today):**

| Identity | Core | Search |
|---|---|---|
| Unauthenticated | **60/hr** (observed `X-RateLimit-Limit: 60`) | **10/min** (observed `X-RateLimit-Resource: search, Limit: 10`) |
| Personal access token | **5,000/hr** | 30/min |
| `GITHUB_TOKEN` inside Actions | **1,000/hr per repository** | — |
| GitHub App installation | 5,000 → 12,500/hr | — |

Secondary limits: **≤100 concurrent requests**, **≤900 points/min** (GET/HEAD/OPTIONS = 1 pt, POST/PATCH/PUT/DELETE = 5 pts).

⚠️ **Plan-relevant gotcha:** `GITHUB_TOKEN` in Actions is only **1,000/hr/repo**. For a crawl of a few thousand repos, mint a **fine-grained PAT (5,000/hr)** and store it as a repo secret; don't rely on the ambient token.

**Verified calls:**
- `GET /repos/SWE-bench/SWE-bench` → `stargazers_count: 5863`, `forks_count: 972`, `license.spdx_id: MIT`, `created_at: 2023-10-04`, `pushed_at: 2026-09-02`, `topics: ["benchmark","language-model","software-engineering"]`, `homepage: https://www.swebench.com`, `subscribers_count: 39`.
- `GET /search/repositories?q=topic:benchmark+topic:llm&sort=stars` → **2,233 repos**. Top: `open-compass/opencompass` (7,449★), `xlang-ai/OSWorld` (3,148★), `beir-cellar/beir` (2,294★).
- **Stars-over-time requires auth:** `Accept: application/vnd.github.star+json` on `/stargazers` → `401 Requires authentication` unauthenticated. With a PAT it works but is **paginated at 100/page over the full star list** — for a 5,000-star repo that's 50 requests. **Do not build star-history.** Instead: snapshot `stargazers_count` on every run and store the time series yourself. That's one request per repo per week and gives you the same curve going forward.
- `robots.txt` on github.com names `ClaudeBot`/`GPTBot`/`PerplexityBot` with `Crawl-delay: 1` and a narrow allow-list — **but it explicitly points automated users to the API**: *"We also provide an extensive API."* Use the API, never HTML.

**Licence/ToS:** repo *metadata* via the API is fine under the GitHub ToS (the API exists for this). README text is under each repo's own licence — 30%+ of benchmark repos declare none (e.g. `SWE-bench/experiments` returned `license: null`). **Store README-derived facts, not README prose.**

**Populates:** `benchmarks` (repo URL, licence, creation date, topics, homepage), `organizations` (owner org), adoption signal (stars/forks/watchers time series), `sources` (release tags, CITATION.cff).

**High-value specific repos (all verified today):**
| Repo | Stars | Licence | Last push | Why |
|---|---|---|---|---|
| `EleutherAI/lm-evaluation-harness` | 14,007 | MIT | 2026-09-14 | **227 task directories** of YAML with `num_fewshot`, `output_type`, `metric_list`, `dataset_path`, `doc_to_text` — machine-readable eval conditions for hundreds of benchmarks |
| `UKGovernmentBEIS/inspect_evals` | 674 | MIT | 2026-09-17 | UK AISI's eval collection; agentic/safety/cyber coverage |
| `embeddings-benchmark/results` | 61 | **CC0-1.0** | 2026-09-16 | ~600 MB of MTEB result JSON, public-domain, daily updates |
| `BerriAI/litellm` | — | MIT | — | `model_prices_and_context_window.json`, 2.59 MB, ETag present |
| `SWE-bench/experiments` | 282 | **none declared** | 2026-09-03 | SWE-bench submission trajectories — ⚠️ no licence |

**`lm-evaluation-harness` via `git clone` is arguably the best single source of structured evaluation-condition data in existence.** It is MIT, it is one clone, and it directly populates the `comparability_key`.

---

## 7. Epoch AI

**Base:** `https://epoch.ai/data/`

- **Mechanism:** static file downloads. **No public API.** The `epochai` PyPI client (`github.com/epoch-research/epochai-python`, MIT) reads the **Airtable API** — but requires *you* to duplicate their Airtable base into your own workspace and supply `AIRTABLE_BASE_ID` + `AIRTABLE_PERSONAL_ACCESS_TOKEN` with `data.records:read`/`schema.bases:read`, because *"Airtable doesn't allow public API access."* **That is not an ingestion path for an automated pipeline** — the duplicate goes stale. Use the ZIP.
- **Verified URLs:**
  - `https://epoch.ai/data/benchmark_data.zip` → **200, `Content-Type: application/zip`, `ETag: "a95a0b35dd410ad483b45f53e3725590"`**, ~2.3 MB. ⚠️ **No `Last-Modified` header** — you must use ETag for conditional GETs.
  - `https://epoch.ai/data/notable_ai_models.csv` → 200, 2,254,959 bytes
  - `https://epoch.ai/data/large_scale_ai_models.csv` → 200, 1,107,528 bytes
  - Also `ai_models.zip`, `ai_companies.zip`, `ml_hardware.zip`, `gpu_clusters.csv`, `ai_chip_*.zip`, `data_centers/data_centers.zip`
- **The local copy** at `E:\AI\_Project\Project (intelligence-benchmark)\benchmarks\epochdl\` is this ZIP unpacked (87 entries). Structure:
  - `benchmark_metadata.csv` — **81 benchmarks**, columns: `benchmark, in_eci, source_file, score_column, scale, random_baseline, score_ceiling, release_date, superseded_by`. **`random_baseline` and `score_ceiling` are exactly the normalisation fields a cross-domain index needs**, and `superseded_by` is a benchmark-lineage edge — adopt both.
  - `model_metadata.csv` — `model_version, model_group, date, display_name, organization, country, accessibility, training_compute_flop`
  - ~80 per-benchmark CSVs (`gpqa_diamond.csv`, `swe_bench_verified.csv`, `frontiermath*.csv`, `hle_external.csv`, `terminalbench_external.csv`, `os_world_external.csv`, `metr_time_horizons_external.csv`, …) with columns `Model version, mean_score, Best score (across scorers), Release date, Organization, Country, Training compute (FLOP), stderr, Log viewer, Logs, Started at, id`. The `stderr` column is gold — almost nobody else publishes uncertainty.
  - `epoch_capabilities_index/` — `eci_scores.csv`, `edi_scores.csv`, `eci_bootstraps.json`, `processed_data_for_eci.csv`
- **Licence (verbatim from the ZIP's README.md):** *"Epoch AI's data is free to use, distribute, and reproduce provided the source and authors are credited under the Creative Commons Attribution license."* Citation: `Epoch AI, "Capabilities & Benchmarking". Published online at epoch.ai.` The dashboard page adds: *"benchmark questions and answers are the property of their respective creators"* and external data *"retains its original licensing."*
- **Update cadence:** the download page says "Updated Sep. 17, 2026" — i.e. **today**. Dashboard claims **390 models / 80 benchmarks**. The freshest row in the local `gpqa_diamond.csv` is dated `2026-09-02`. **No stated cadence** — poll weekly via ETag. (UNVERIFIED: whether it's daily or event-driven.)
- **robots.txt:** `Disallow: /assets/`, `Disallow: /inspect-viewer/`, and explicitly `Disallow: /frontiermath/tiers-1-4/benchmark-problems` with the comment *"Prevent crawling of sample benchmark problems to avoid contaminating training datasets."* **`/data/` is not disallowed.** Respect the inspect-viewer exclusion — do not crawl their run logs.

**Populates:** `result claims` (with stderr!), `systems` (model + org + country + training FLOP), `organizations`, `benchmarks` (with random_baseline/ceiling/supersession).
**Fragility:** **very low.** Static files + ETag + CC-BY. **Build this adapter first — it is the highest value-per-line-of-code source in the whole list.**

---

## 8. Individual leaderboard sites — machine-readable vs HTML

### ✅ Genuinely machine-readable (build adapters)

**HELM (Stanford CRFM)** — `https://storage.googleapis.com/crfm-helm-public/`
- **Anonymous public GCS bucket, listable.** Both APIs work:
  - XML: `https://storage.googleapis.com/crfm-helm-public/?prefix=lite/benchmark_output/releases/&delimiter=/`
  - JSON: `https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o?prefix=…&delimiter=/`
- **26 suites**, verified: `air-bench, arabic, arabic-enterprise, audio, capabilities, classic, cleva, efficient_helm, ewok, finance, heim, image2struct, instruct, lite, long-context, medhelm, mmlu, mmlu-winogrande-afr, reasoning, robo-reward-bench, safety, seahelm, source_datasets, thaiexam, torr, vhelm`. Note **`robo-reward-bench`** (robotics), **`medhelm`** (medicine), **`finance`**, **`audio`**, **`heim`/`vhelm`** (image/vision) — HELM alone gives you real cross-domain breadth.
- Per release (`lite/benchmark_output/releases/v1.13.0/`): `runs.json` (3.93 MB), **`run_specs.json` (95 KB, 2,546 specs)**, `schema.json`, `groups.json`, `groups_metadata.json`, `runs_to_run_suites.json`, `costs.json`, `summary.json`.
- **`run_specs.json` is the best-structured evaluation-conditions data on the public internet.** A real record:
  ```json
  {"name":"commonsense:dataset=openbookqa,method=multiple_choice_joint,model=01-ai_yi-34b",
   "scenario_spec":{"class_name":"helm.benchmark.scenarios.commonsense_scenario.OpenBookQA"},
   "adapter_spec":{"method":"multiple_choice_joint","max_train_instances":5,"max_eval_instances":1000,
     "num_outputs":5,"num_train_trials":1,"temperature":0.0,"max_tokens":1,
     "chain_of_thought_prefix":"","stop_sequences":["\n"],
     "model":"01-ai/yi-34b","model_deployment":"together/yi-34b"},
   "metric_specs":[{"class_name":"...BasicMetric","args":{"names":["exact_match","quasi_exact_match",...]}}],
   "data_augmenter_spec":{...}}
  ```
  `max_train_instances` = **shots**. `chain_of_thought_prefix` = **CoT on/off**. `temperature`/`num_outputs`/`num_train_trials` = **sampling & retries**. `model_deployment` = **which provider served it**. Map these straight into `comparability_key`.
- **Licence: UNVERIFIED for the data.** The HELM *code* is Apache-2.0; I did not find an explicit licence on the GCS bucket. **Ask CRFM or cite-and-link rather than redistribute.**
- **Update:** per-release (v1.0.0 … v1.13.0 for `lite`). Poll the release-prefix listing.

**SWE-bench** — `https://www.swebench.com/`
- Data is **inlined in the HTML** as `<script id="leaderboard-data" type="application/json">`. Parse with one regex + `json.loads`. Not a real scrape.
- **5 leaderboards / 323 result claims** (verified): `Multilingual` 13, `Test` 24, **`Verified` 180**, `Lite` 84, `Multimodal` 22.
- Per-row fields: `agent, agent_org, checked, cost, date, folder, instance_calls, instance_cost, logo, logs, model_display, model_org, model_release_date, os_model, os_system, reasoning_effort, resolved, site, tags, trajs, trajs_docent, warning` (+ `per_instance_details` on Multilingual).
- **`agent` + `agent_org` + `reasoning_effort` + `instance_calls` is exactly the "scaffold" axis of the comparability key**, and `checked` is a third-party-verification boolean. `warning` carries caveats. `os_model`/`os_system` are open-weight flags.
- `logs` points at `s3://swe-bench-submissions/...` — **that bucket is NOT anonymously listable** (I got `403 AccessDenied`). Link, don't fetch.
- **Fragility: medium.** An id/attribute rename on the page breaks you. Cheap to monitor (assert the script tag exists; alert if not).

**LMArena** — `lmarena.ai` **301 → `arena.ai`**
- **Don't scrape the site.** `https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset` — **`license:cc-by-4.0`**, lastModified **2026-09-16**, ~36k downloads.
- Parquet per arena, each with `full-*.parquet` + `latest-*.parquet`: `text`, `agent`, `agent_bash_recovery_steps`, `agent_praise_complaint`, `agent_steerability`, `agent_task_outcome_explicit`, `agent_tool_hallucination`, `document`, `document_style_control`, `image_edit`, `image_to_video`, `search`, `search_factuality`, `search_style_control`, … The `*_style_control` variants are a *different comparability class* of the same benchmark — model them as distinct leaderboards.
- arena.ai `robots.txt`: `Allow: /`.
- **Fragility: low.** Explicit CC-BY-4.0 + HF hosting. **Best-in-class source.**

**MTEB** — `github.com/embeddings-benchmark/results`, **CC0-1.0**, ~600 MB, pushed 2026-09-16. `git clone --depth 1` weekly. ~1,000+ embedding tasks × many models.

**EvalPlus** — `https://evalplus.github.io/results.json` → **200, 34,305 bytes**. Static JSON, trivially ingestible.

**LiveBench** — `https://livebench.ai/table_2025_11_25.csv` → **200, 9,893 bytes**. Dated CSVs; `robots.txt` is `Disallow:` (i.e. allow all). You must discover the current date-stamped filename from the page (I couldn't regex the current one out of the SPA — **the filename discovery step is UNVERIFIED**; likely needs reading the JS bundle or the `LiveBench/LiveBench` GitHub repo instead).

**Grand Challenge (medical imaging / MICCAI ecosystem)** — `https://grand-challenge.org/api/v1/challenges/?limit=2&offset=0`
- **Public REST, no auth, DRF pagination. 264 challenges** (verified count). Fields: `api_url, url, slug, title, description, public, status (OPEN/CLOSED), logo, submission_types, start_date, end_date, publications[]`.
- **`publications[]` gives you the citation link for free.** This is the cleanest non-LLM-domain source in the entire catalogue and it single-handedly covers medical imaging.

### ⚠️ HTML-only or restricted
- **OGB** (`ogb.stanford.edu/docs/leader_nodeprop/`) — HTML tables. Stable structure, low churn. Graph-learning coverage.
- **Matbench** (`matbench.materialsproject.org`) — HTML; my guess at a JSON bundle 404'd. (Materials Project *does* have an API with a free key — **UNVERIFIED** whether Matbench leaderboards are in it.)
- **CASP** (`predictioncenter.org/casp16/`) — HTML/CGI, ancient, stable. Protein structure.
- **WeatherBench 2** (`sites.research.google/gr/weatherbench/`) — HTML + a GCS bucket of scorecards (**UNVERIFIED**; the GitHub repo `google-research/weatherbench2` is the better handle).
- **OpenCompass** (`opencompass.org.cn`) — HTML SPA; the `open-compass/opencompass` repo (7,449★) is the better handle.
- **Artificial Analysis** — see §10.

### ❌ Don't bother
- **Codabench results.** `https://www.codabench.org/api/competitions/?limit=2` works unauth (JSON: `id, title, created_by, owner_display_name, created_when, first_phase_start, published, participants_count, logo, description`) — **but `/api/competitions/{id}/results/` returns `{"detail":"You are not a competition admin or superuser"}`.** You get the competition catalogue, never the leaderboards. 80,406 users / 722,037 submissions on the platform. Worth ingesting as *benchmark discovery*, worthless for result claims.
- **EvalAI leaderboards.** `https://eval.ai/api/challenges/challenge/all/all/all` works unauth → **1,053 challenges**, DRF-paginated. `/api/challenges/challenge/{id}/challenge_phase` works (gives `leaderboard_public`, `max_submissions_per_day`, dates). But `/api/jobs/challenge_phase_split/{id}/leaderboard/` → `{"error":"Sorry, the leaderboard is not public!"}` on the ones I tried. Same verdict: catalogue yes, results mostly no.

---

## 9. Conferences & competitions

- **NeurIPS Datasets & Benchmarks Track** — **1,995 submissions, 497 accepted in 2025**. This is the densest concentration of *peer-reviewed* benchmarks anywhere, and the track **mandates Croissant metadata + persistent public hosting**, which means the accepted papers come with machine-readable dataset descriptors.
  - **⚠️ OpenReview API is now gated.** `https://api2.openreview.net/notes?venueid=NeurIPS.cc/2025/Datasets_and_Benchmarks_Track` → **HTTP 403 `{"name":"ChallengeRequiredError","message":"Challenge verification required (2026-09-17-…)"}`** as of today. Anonymous programmatic access is blocked. (`robots.txt` only disallows `/*?*email=`, so this is a bot-challenge layer, not a robots rule.) **UNVERIFIED** whether an authenticated OpenReview account bypasses it — likely, via the `openreview-py` client with credentials. Plan for: *manual annual export, or an authenticated client, not an anonymous cron.*
  - **Fallback that works:** `proceedings.neurips.cc/paper_files/paper/{year}` and `papers.nips.cc/paper_files/paper/{year}` both returned 200. Static HTML per-year indices, very stable, plus per-paper `.json`/`bib` siblings. Scrape once a year in December.
- **MICCAI challenges** → use **Grand Challenge API** (§8). That *is* the MICCAI challenge registry in practice.
- **Codabench / EvalAI** → catalogue only (§8).
- **Kaggle** — `https://www.kaggle.com/api/v1/competitions/list` → **401 unauthenticated.** Requires `~/.kaggle/kaggle.json` (username + key). CLI: `kaggle competitions list --search X --category Y --page N`; `kaggle datasets list`. **Rate limits are not publicly documented — UNVERIFIED.** Kaggle ToS restricts bulk scraping. Kaggle's own meta-description today reads: *"evaluating agents, models, and frontier technology through crowdsourced benchmarks"* — they have repositioned toward benchmarks, so this is worth a second look, but it's an authenticated, ToS-constrained source. **Second wave at best.**
- **DrivenData** — `https://www.drivendata.org/competitions/` is 200, but **`robots.txt` explicitly contains `Disallow: /*/leaderboard_partial` and `Disallow: /competitions/search/`.** **Do not scrape their leaderboards.** Manual curation only. Small N (~dozens of competitions) so this is fine.

---

## 10. Model-release feeds (populating the `System` entity)

| Source | Endpoint | Auth | Verified today |
|---|---|---|---|
| **OpenRouter** | `https://openrouter.ai/api/v1/models` | **none** | ✅ 200, **444 models**. Fields: `id, canonical_slug, hugging_face_id, name, created (unix), description, context_length, architecture{modality, input_modalities, output_modalities, tokenizer, instruct_type}, pricing{prompt, completion}, top_provider{context_length, max_completion_tokens, is_moderated}, supported_parameters[]`. **`hugging_face_id` is a free join key to HF.** Even catches stealth models (`stealth/union-alpha` was in the list). |
| **LiteLLM** | `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` | none | ✅ 200, **2,591,466 bytes**, `ETag` present. Repo licence MIT (**UNVERIFIED** for this specific file). |
| **Epoch `notable_ai_models.csv`** | `https://epoch.ai/data/notable_ai_models.csv` | none | ✅ 200, 2.25 MB, **CC-BY-4.0**. Training compute, org, country, accessibility. |
| **HuggingFace models** | `/api/models?sort=createdAt&direction=-1` | none | ✅ returns models created minutes ago |
| **OpenAI news RSS** | `https://openai.com/news/rss.xml` | none | ✅ 200 `text/xml`, most recent item `Wed, 16 Sep 2026` |
| **Anthropic** | — | — | ❌ **No RSS.** `anthropic.com/rss.xml` and `/news/rss.xml` both 404. `https://docs.claude.com/en/release-notes/api` is HTML-only. |
| **Google** | `https://blog.google/rss/` | none | ✅ 200 `application/xml` (firehose, needs filtering); `ai.google.dev/gemini-api/docs/changelog` HTML |
| **Artificial Analysis** | `https://artificialanalysis.ai/api/v2` | **`x-api-key` required** | ✅ unauth → `401 {"error":"API key is required"}`. Tiers: **Free 100 req/24h**, Pro 500/24h, Commercial custom (fixed 24h windows, per org+user not per key; `X-RateLimit-*` headers returned). Free tier = language-models endpoint with headline indices, median performance, input/output pricing; per-provider data is Pro+. **Attribution required at all tiers**; *"For redistribution rights … contact the team."* `robots.txt: Allow: /`. |

**Recommendation:** build the `System` entity off **OpenRouter + Epoch `notable_ai_models.csv` + HF models**, all no-auth and all redistributable. Use Artificial Analysis **only as a link-out**, not as ingested data — 100 req/day and an explicit "contact us for redistribution" clause make it legally awkward for a CC-BY index. Anthropic/OpenAI/Google blogs: manual curation with an LLM-assisted weekly digest; RSS only for OpenAI and Google.

---

## 11. Bibliographic / archival

**Wayback Machine — Save Page Now 2 (SPN2)** — this is your mandated archiving path.
- `POST https://web.archive.org/save`, header `Authorization: LOW <accesskey>:<secret>` (keys from `https://archive.org/account/s3.php`).
- Params: `url` (required), `capture_all=1`, `capture_outlinks=1`, `capture_screenshot=1`, `delay_wb_availability=1`, `force_get=1`, `skip_first_archive=1`, **`if_not_archived_within=<timedelta>`** (default 30 min — *use this, it's your idempotency key*), `outlinks_availability=1`, `email_result=1`, `js_behavior_timeout=<0-30>`, `capture_cookie`.
- Response: `{"url":"…","job_id":"…"}`. Poll `GET /save/status/{job_id}` (also `?job_ids=a,b,c`). Quota: `GET /save/status/user` → `{"available":12,"processing":3}` (**verified: 401 without auth**).
- **Limits (from IA's public SPN2 doc):** authenticated **12 concurrent / 100,000 per day**; anonymous **6 concurrent / 4,000 per day**; **same URL max 10×/day**. *(Sourced from IA's own public spec doc; I could not re-read the Google Doc body directly today — treat the exact numbers as **lightly UNVERIFIED**, but the auth mechanism and params are solid.)*
- **⚠️ The Availability API (`https://archive.org/wayback/available?url=…`) returned `429 Too Many Requests` to me on a single cold request today.** Do not use it for existence checks.
- **Use the CDX API instead** — verified working: `https://web.archive.org/cdx/search/cdx?url=epoch.ai/data/ai-benchmarking-dashboard&output=json&limit=3` → `[["urlkey","timestamp","original","mimetype","statuscode","digest","length"], ["ai,epoch)/data/…","20241127213552",…]]`. Cheap, reliable, gives you `digest` so you can tell whether content actually changed between captures.

**Crossref** — `https://api.crossref.org/works?query.title=…&mailto=you@example.com`. No key, polite pool via mailto. ✅ verified. ⚠️ **`query.title` is a very loose match**: `query.title=SWE-bench` returned **23,851 results** with the top hits being *"SWE-bench Goes Live!"* and *"Investigating Test Overfitting on SWE-bench"*. Use Crossref for **DOI → metadata** resolution, never for discovery.

**DataCite** — `https://api.datacite.org/dois?query=…&provider-id=arxiv`. Responds; exact schema **UNVERIFIED** (my parse failed). arXiv's own bulk-data page names DataCite (`provider-id = arxiv`) as an official metadata route.

**Zenodo** — `https://zenodo.org/api/records?q=benchmark&size=1` ✅ 200 unauth. Returns `doi`, **`conceptdoi`** (version-independent DOI — important for benchmark versioning), `created`, `modified`, full metadata. This is also where *you* should mint the index's own DOI.

**Perma.cc** — requires an institutional account; free tier is 10 links/month. **Not viable at our volume. Drop it from the plan; SPN2 + CDX covers the mandate.**

---

# (a) TIERED INGESTION PLAN

## Tier 1 — build these four adapters first (week 1–3)
Chosen for: explicit permissive licence × static/stable transport × direct hit on a differentiator.

1. **Epoch AI ZIP + CSVs** — `https://epoch.ai/data/benchmark_data.zip`, `notable_ai_models.csv`, `large_scale_ai_models.csv`. CC-BY-4.0, ETag-conditional, ~2 MB. Instantly gives you **81 benchmarks with `random_baseline`/`score_ceiling`/`superseded_by`**, ~390 systems with org/country/training-FLOP, and thousands of result claims **with standard errors**. *≈150 lines of Python. Highest value-per-effort in the list.*
2. **HuggingFace Hub** — `/api/datasets` (`filter=benchmark:official`, `benchmark:eval-yaml`, `croissant`), `/api/spaces?filter=leaderboard` (1,019 rows + the tag taxonomy), `/api/models`, `/api/datasets/{id}/croissant`. No auth (add a free token), permissive robots, `huggingface_hub` handles backoff. Populates `benchmarks`, `leaderboards`, `systems`, `organizations`, and **hands you the eval-conditions vocabulary for free**.
3. **GitHub repo metadata** (PAT, 5,000/hr) + **`git clone --depth 1` of `EleutherAI/lm-evaluation-harness`** (227 task dirs of YAML: `num_fewshot`, `output_type`, `metric_list`, `dataset_path`) and **`embeddings-benchmark/results`** (CC0). This is where `comparability_key` gets real data instead of nulls.
4. **arXiv** (Query API for backfill on known benchmark names; OAI-PMH `set=cs` daily delta for discovery) → **LLM triage** → **draft PR**. CC0 metadata, 15+ years stable. Accept ~60% heuristic precision and pay for an LLM classifier.

**After Tier 1 you should have on the order of 300–600 benchmarks with real provenance, plus the entire eval-conditions vocabulary.** That is a shippable v0.1.

## Tier 2 — second wave (weeks 4–10)
5. **HELM GCS bucket** — 26 suites incl. `robo-reward-bench`, `medhelm`, `finance`, `audio`, `vhelm`. `run_specs.json` is the richest eval-conditions data anywhere. *Do the licence question first.*
6. **LMArena `lmarena-ai/leaderboard-dataset`** (CC-BY-4.0 parquet, 14+ arenas incl. agent/search/video).
7. **SWE-bench inline JSON** — 323 verified result claims with `agent`/`reasoning_effort`/`cost`/`checked`.
8. **Grand Challenge API** — 264 medical-imaging challenges with publication links. Cheapest possible route to non-LLM-domain breadth.
9. **PwC archive on `pwc-archive`** — one-time historical backfill of `evaluation-tables` + `datasets`. **Resolve the CC-BY-SA viral-licence question before ingesting.**
10. **Wayback SPN2 + CDX** — archiving every non-DOI source (this is a *mandate*, so it's Tier 1 in policy terms; Tier 2 only because it depends on having sources to archive).
11. **OpenRouter + LiteLLM + OpenAI RSS** — System entity enrichment.
12. **Semantic Scholar (with key, 1 RPS)** — arXiv→paper identity + citation counts, cross-checked against OpenAlex.
13. **Zenodo + Crossref + DataCite** — DOI resolution, and minting the index's own DOI.
14. **EvalPlus / LiveBench / OGB / MTEB** static files — cheap adapters, each ~30 lines.

## Tier 3 — manual/annual, not automated
- **NeurIPS D&B proceedings** — annual December scrape of `proceedings.neurips.cc/paper_files/paper/{year}`. 497 accepted papers/year is a one-afternoon LLM-assisted curation job.
- **CASP, Matbench, WeatherBench 2, OpenCompass** — HTML, low churn, high domain value. Hand-curate + re-check quarterly.
- **Codabench / EvalAI catalogues** — pull the competition lists (1,053 + hundreds) once as *discovery candidates*; their leaderboards are closed.
- **Vendor blogs** (Anthropic, Google, Meta, Mistral, Qwen, DeepSeek) — weekly LLM digest, human confirms.

## ❌ Never bother
- **OpenReview anonymous API** — bot-challenged today. Use proceedings HTML instead.
- **Codabench / EvalAI leaderboard endpoints** — 403 / "not public". Guaranteed to waste a sprint.
- **DrivenData leaderboards** — robots-disallowed. Legal exposure with ~zero payoff.
- **GitHub `/stargazers` star-history** — 50 auth'd requests per popular repo for data you can accumulate yourself with 1 request/week.
- **Perma.cc** — 10 links/month free tier.
- **`s3://swe-bench-submissions`** — 403 anonymous.
- **Artificial Analysis as an ingested dataset** — 100 req/day + "contact us for redistribution". Link out instead.
- **Kaggle scraping** — auth'd, ToS-restricted, undocumented limits, marginal benchmark yield.
- **arXiv S3 full-text buckets** — requester-pays, and we are metadata-only by charter.

---

# (b) SCRAPING INFRASTRUCTURE

### Where it runs: **GitHub Actions cron, in the data repo itself.** Not close.
- **Cloudflare Workers is disqualified by the numbers:** Free plan gives **10 ms CPU per Cron Trigger**, **5 cron triggers per account**, **50 subrequests per invocation**. Even Paid gives 30 s (crons < 1 h) / 15 min (crons ≥ 1 h) and 250 triggers. You cannot parse a 3.9 MB `runs.json` in 10 ms.
- **A VPS is disqualified by the team size** — it's a machine you now have to patch, monitor and pay for, in a project whose whole premise is near-zero ops.
- **GitHub Actions wins because the scraper lives next to the YAML it writes.** The runner already has `GITHUB_TOKEN`, `git`, and PR-creation rights. No deploy step, no secret-syncing, no separate state store. Public repos get free minutes.
- **Known Actions caveats — write these into the plan:**
  - Minimum `schedule` interval is **5 minutes** (irrelevant; we want daily/weekly).
  - *"The `schedule` event can be delayed during periods of high loads… If the load is sufficiently high enough, some queued jobs may be dropped."* → **never schedule on `0 * * * *`**; use an odd offset like `17 4 * * *`. And make every job idempotent so a dropped run is harmless.
  - *"In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days."* → the scrapers themselves commit/open PRs, so activity is self-sustaining. But add a monthly `workflow_dispatch` canary that fails loudly if the cron hasn't fired.
  - `GITHUB_TOKEN` is only **1,000 req/hr per repo**. Store a fine-grained **PAT (5,000/hr)** as `GH_API_TOKEN` for the GitHub-crawling job.

**Suggested workflow split** (separate workflows so one failure doesn't block the rest):

| Workflow | Cron | Sources |
|---|---|---|
| `ingest-static.yml` | `17 4 * * 1` (weekly Mon) | Epoch ZIP/CSV, LiteLLM, EvalPlus, LiveBench, MTEB clone, lm-eval-harness clone |
| `ingest-hub.yml` | `23 5 * * *` (daily) | HF datasets/spaces/models/daily_papers |
| `ingest-arxiv.yml` | `41 6 * * 1-5` (weekdays) | OAI-PMH delta + LLM triage |
| `ingest-leaderboards.yml` | `11 7 * * *` | HELM releases, SWE-bench, LMArena, Grand Challenge |
| `archive-sources.yml` | `31 3 * * *` | SPN2 for any `source` lacking a `wayback_url` |
| `health-check.yml` | `0 9 * * 1` | Canary: assert each adapter ran in the last N days; open an issue if not |

### State between runs — **three layers, no database**
1. **Canonical state is the repo itself.** The YAML files *are* the state. `git log` is the audit trail. This is already your architecture; don't add a second source of truth.
2. **HTTP cache metadata in a committed `_ingest/state/{source}.json`**, holding per-URL `{etag, last_modified, sha256, last_fetched, last_changed}`. Committed alongside the data so a state change is itself reviewable. Small (a few KB per source).
3. **`actions/cache`** for the bulky, regenerable stuff only: the `git clone --depth 1` checkouts of lm-eval-harness/MTEB, the unpacked Epoch ZIP, and the HF request cache. Keyed on the content hash. Never put anything unrecoverable here — Actions caches are evicted after 7 days idle.

### Conditional requests / caching — per-source, because they differ
| Source | Mechanism |
|---|---|
| Epoch ZIP | **`If-None-Match` with the ETag** (`"a95a0b35…"`). ⚠️ **no `Last-Modified` header** — ETag only. |
| `raw.githubusercontent.com` (LiteLLM) | ETag (present, verified) |
| GitHub API | `If-None-Match` — **304s do not count against your rate limit.** Essential at 5,000/hr. |
| HF API | ETag on `/api/datasets?…` (verified `ETag: W/"64f-OXh…"`). Also short-circuit on `lastModified` in the payload before fetching detail. |
| HELM GCS | Bucket object listing gives `generation` + `size`; diff the release-prefix list before downloading any 3.9 MB blob. |
| arXiv OAI-PMH | `from`/`until` datestamps = native incremental. Persist the last successful `until`. |
| SWE-bench / HTML | `sha256` the extracted JSON block, not the page (the page has rotating logos/CDN noise). |
| OpenAlex | Never poll; use the free bulk snapshot + targeted singleton lookups (which cost $0). |
| Wayback | `if_not_archived_within=30d` param does dedup server-side; CDX `digest` tells you if content actually changed. |

**Universal rule: hash the *normalised* payload (sorted keys, stripped volatile fields) and skip the whole downstream pipeline on a match.** Most runs should be no-ops.

### Output → **draft PRs, never auto-merge**
```
scrape → normalise → diff against current YAML → classify change
  ├─ NEW entity            → PR, label `ingest:new`, requires human review
  ├─ FIELD CHANGE          → PR, label `ingest:update`, show before/after in the body
  ├─ NUMERIC RESULT CHANGE → PR, label `ingest:result`, ALWAYS human-reviewed
  └─ NO CHANGE             → exit 0, no commit
```
Mechanics:
- One branch per source per day: `ingest/epoch/2026-09-17`. `peter-evans/create-pull-request` or `gh pr create --draft`.
- **Batch, don't spam.** One PR per source per run containing all its changes, not one PR per benchmark. A 1–2 person team will drown otherwise.
- **PR body is the review surface**: a rendered diff table (entity, field, old → new, source URL, wayback URL, fetch timestamp) plus the raw response hash. The reviewer should be able to approve without opening a single file.
- **Branch protection on `main`**: require 1 approval, require the schema-validation check. No bot bypass. This is the thing that makes "fully auditable" true rather than aspirational.
- **Every ingested record carries provenance inline**: `source_url`, `source_type: api|scrape|bulk`, `fetched_at`, `wayback_url`, `adapter_version`, `extraction_confidence`. A record without provenance must fail CI.
- **Auto-merge exactly one class of change**: pure adoption counters (`github_stars`, `hf_downloads`) into a separate `metrics/` tree that is *not* part of the citable CC-BY core. Keeps the review queue sane without compromising the substantive data.

### Politeness
- A single identifying `User-Agent` on every request: `UAIBI/0.1 (+https://<your-domain>)`. Several of these services (arXiv, OpenAlex, Crossref) explicitly reward this.
- Per-host token buckets, hard-coded conservative: **arXiv 1 req / 3 s** (their ToU) or **1 / 15 s** for any `arxiv.org` HTML (their `Crawl-delay`); HF ~1 req/s (you have 500/5 min anon); GitHub with `If-None-Match` and a 1 s floor; Grand Challenge / Codabench / EvalAI ~1 req/2 s (small community servers, be generous).
- Exponential backoff with jitter on 429/5xx; **on HF, parse the `RateLimit` header and sleep exactly that long** (or just use `huggingface_hub` ≥1.2.0, which does it for you).
- `robots.txt` fetched and cached per host per run, honoured by the fetcher itself — not by developer discipline. Make it structurally impossible to hit `drivendata.org/*/leaderboard_partial`.
- Run sources **sequentially within a workflow**, parallel **across** workflows. Never fan out concurrent requests at one host.

### Failure & alerting
- **Every adapter emits a run record** to `_ingest/runs/{source}/{date}.json`: `{status, http_codes, records_seen, records_changed, duration_s, errors[]}`. Committed. This is your monitoring system and it costs nothing.
- **Three distinct failure classes, three responses:**
  1. *Transport* (timeout/5xx/429) → retry ×3, then soft-fail the job, log, **do not open a PR**. Alert only after **3 consecutive** failed runs (avoids weekend noise).
  2. *Schema drift* (200 OK but the expected field/selector is gone — e.g. SWE-bench's `<script id="leaderboard-data">` vanishes) → **hard fail immediately**, open a GitHub Issue tagged `adapter-broken`. This is the one that silently corrupts data if you swallow it. **Assert structure explicitly, don't `.get()` with a default.**
  3. *Semantic anomaly* (>20% of records changed, or a benchmark's SOTA moved by >30 points) → open the PR but label `needs-scrutiny` and **block auto-merge**.
- **Alerting channel:** GitHub Issues + the repo's own notification email. A 1–2 person team does not need PagerDuty. Add a single weekly digest issue listing every adapter's last-success date — that catches the "cron silently stopped firing" failure mode that kills most hobby scrapers.
- **Keep the last raw response per source** (gzipped, capped) under `_ingest/raw/` or in Actions artifacts so a bad parse can be re-run without re-fetching.

---

# (c) LEGAL / ETHICAL POSTURE

### Clean — automated collection explicitly permitted, redistribution fine
| Source | Terms | Attribution |
|---|---|---|
| **arXiv metadata** | *"free to use descriptive metadata … under CC0 1.0"*; OAI *"Metadata harvesting permitted"*. Rate: ≤1 req/3 s; `Crawl-delay: 15` on HTML. | Not legally required; **do it anyway**. Must **not** imply arXiv endorsement. |
| **Epoch AI** | *"free to use, distribute, and reproduce provided the source and authors are credited"* — **CC-BY-4.0**. `/data/` not robots-disallowed. | **Required.** Cite: `Epoch AI, "Capabilities & Benchmarking", epoch.ai`. |
| **LMArena `leaderboard-dataset`** | **CC-BY-4.0** on the HF repo. | Required. |
| **MTEB `embeddings-benchmark/results`** | **CC0-1.0** — public domain. | Courtesy only. |
| **OpenAlex bulk snapshot** | **CC0**; *"free to download, share, remix, and build on."* | Courtesy. |
| **HuggingFace Hub API** | `robots.txt: Allow: /`; documented public API with published rate tiers; official Python client. | Per-dataset licence varies — **carry each dataset's own `license:` tag through into your record**. |
| **GitHub API** | ToS-sanctioned; robots.txt says *"We also provide an extensive API."* Metadata (stars, topics, licence, dates) is factual. | Carry each repo's own SPDX licence. |
| **Grand Challenge, Codabench, EvalAI, Zenodo, Crossref, DataCite** | Open public APIs, no auth, no anti-bot. | Courtesy; Crossref rewards `mailto`. |

### Attribution-mandatory / redistribution-constrained
- **Papers with Code archive — `CC-BY-SA-4.0`.** ⚠️ **The ShareAlike clause is the single biggest legal trap in this catalogue.** If PwC's task taxonomy or evaluation-table rows are incorporated into your YAML, a strict reading forces the derivative to be CC-BY-SA, which **contradicts the plan's CC-BY licensing**. **Recommended posture:** treat PwC as a *reconciliation key only* — match benchmark names/IDs against it, then write your own descriptions from the primary paper. Any verbatim PwC content goes in an isolated `vendor/pwc/` directory with its own `LICENSE` file and is excluded from the CC-BY core. **Escalate this to a decision in the plan; don't let it be discovered at launch.**
- **Artificial Analysis** — *"Use of the API requires attribution across all tiers… For redistribution rights or bespoke contract terms, contact the team."* Free tier is **100 requests/24 h**. **Posture: link out, do not ingest.** Their numbers are a product, not a commons.
- **Semantic Scholar** — API License Agreement + dataset licence (ODC-BY, **UNVERIFIED for 2026**). Attribution required. Read the licence before ingesting bulk.
- **HELM GCS data** — code is Apache-2.0; **the bucket's data licence is UNVERIFIED.** Bucket is publicly readable, which is permission to *read*, not automatically to *redistribute*. **Posture: email CRFM (`crfm-help@stanford.edu`) and get it in writing, or store only derived structured facts + a link.** The `run_specs.json` eval conditions are arguably uncopyrightable facts, but "arguably" is not a foundation for a trust-based index.

### Explicit prohibitions — **do not cross these**
- **DrivenData `robots.txt`** contains `Disallow: /*/leaderboard_partial` and `Disallow: /competitions/search/`. **Their leaderboard endpoint is expressly off-limits to bots.** Manual curation only.
- **Epoch `robots.txt`** disallows `/inspect-viewer/` and `/frontiermath/tiers-1-4/benchmark-problems` with the stated reason *"to avoid contaminating training datasets."* Honour this — it aligns exactly with the index's own anti-contamination ethic, and violating it would be a reputational own-goal.
- **arXiv** — *"Indiscriminate automated downloads from this site are not permitted"*; `/e-print`, `/src`, `/ps`, `/find`, `/refs`, `/cits` disallowed. Full-content harvesting prohibited via OAI. **We are metadata-only, so this is free to comply with — say so loudly on the About page.**
- **OpenReview** now serves an active bot challenge. Circumventing an anti-bot measure is a materially different legal posture from ignoring a `robots.txt` line. **Do not build a bypass.** Use the proceedings HTML or an authenticated `openreview-py` session under a real, identified account.
- **Kaggle** — ToS restricts mass automated download. Authenticate, respect it, or skip.
- **`s3://swe-bench-submissions`** returns `403 AccessDenied`. Link to it; never probe it.

### Where the real risk sits (ranked)
1. **CC-BY-SA contamination from Papers with Code.** The only issue here that could force a licence change on the whole index. Decide before you ingest.
2. **Republishing benchmark *content* rather than metadata.** The hard constraint ("never hosts datasets") is also your strongest legal shield — *every* ambiguity above dissolves if you only ever store facts + links. Make "metadata only" a CI-enforced invariant (e.g. reject any YAML field exceeding N characters of copied prose, reject any committed `.parquet`/`.jsonl`).
3. **Propagating wrong numbers.** Not a legal risk, an existential one. The OpenAlex `W4387561453` defect I verified above — right DOI, right authors, wrong title, citation count off by ~2 orders of magnitude — is exactly the failure mode that destroys a trust-based index. **Mitigation: every numeric claim carries `source_url` + `fetched_at` + `wayback_url`, and any figure sourced from a single aggregator is rendered with a visible "unverified, single source" marker.** Never let an aggregator's number be presented as the benchmark's own.
4. **Attribution hygiene.** CC-BY is cheap to comply with and expensive to be caught violating. Build a machine-generated `/attributions` page from the `sources` entity so it can never drift from what you actually ingested.
5. **Rate-limit misbehaviour against small community servers** (Grand Challenge, Codabench, EvalAI, predictioncenter.org). These are academic groups with modest infrastructure. Being the project that DDoS'd the CASP server is a reputational injury no licence protects you from. Over-throttle deliberately.

---

## Appendix — items I could NOT verify (do not state these as fact)
- **HELM GCS data licence** (code is Apache-2.0; data unlabelled).
- **Semantic Scholar API key turnaround time** and the **current** bulk-dataset licence.
- **Kaggle API rate limits** — not publicly documented.
- **OpenAlex free-key budget:** blog says **$1/day**; my unauthenticated measurement was **$0.10/day**; the docs repo says 100,000 credits/day. Three different numbers. Measure with an actual key before sizing anything.
- **SPN2 exact concurrency/daily caps** — from IA's public spec doc (12/100,000 authenticated; 6/4,000 anonymous; 10× per URL per day), mirrored not re-read today.
- **DataCite response schema** for `provider-id=arxiv`.
- **LiveBench current CSV filename discovery** — the dated file works (`table_2025_11_25.csv`) but I could not extract the *current* filename from the SPA. Use the `LiveBench/LiveBench` GitHub repo instead.
- **Matbench / WeatherBench 2 machine-readable endpoints** — HTML confirmed, JSON not found.
- **LiteLLM `model_prices_and_context_window.json` licence** specifically (repo root is MIT).
- **Epoch AI update cadence** — the page showed "Updated Sep. 17, 2026" (today) but states no schedule.
- **Codabench / EvalAI data licence and ToS on automated access** — no terms page found.
- **Whether an authenticated OpenReview session bypasses the 2026 bot challenge.**

**Local asset already in hand:** `E:\AI\_Project\Project (intelligence-benchmark)\benchmarks\epochdl\` — the unpacked Epoch AI CC-BY bundle (87 files; `benchmark_metadata.csv` = 81 benchmarks; `model_metadata.csv`; `epoch_capabilities_index/`; `b.zip` = the original 2.29 MB archive).