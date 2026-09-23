# 06 -- Sourcing: What to Scrape and From Where

This document is the **source catalogue**: which sources exist, what each one is actually worth,
what its terms permit, what it costs a curator, and what we do when it breaks. Its companion
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) covers **how the scrapers run** --
the adapter contract, scheduling, state, conditional requests, identity resolution, dedup, draft
PRs, backoff, and the fetcher's enforcement of the policies set here. The split is deliberate: this
document is WHAT and WHY, that one is HOW. Where this document states a source's limit, that one
states our budget against it.

---

## How to read the numbers in this document

The previous revision opened with a blanket assurance that everything below was measured. That is a
trust-me clause in a plan whose thesis is that trust-me clauses destroy catalogues, and it is
withdrawn. Every quantitative claim now carries its own marker:

| Marker | Meaning |
| --- | --- |
| `[M]` | Observed in a live HTTP response on **2026-09-17** by the sourcing recon |
| `[D]` | Read off the vendor's own documentation or terms page on **2026-09-17**, not observed in a response |
| `[E]` | Our estimate or derivation, with the method stated inline |
| `[U]` | Unverified -- confirm before relying on this |

`[D]` is weaker than `[M]`, and the distinction matters: a documented rate limit is what the vendor
says it will do, and several vendors below are currently doing something else. `[M]` is provisional
in the other direction -- a single observation from one IP on one day.

**The probe log.** Each `[M]` value is to be backed by one line in `ingest/probes/2026-09-17.jsonl`
keyed `<source>.<field>`, carrying URL, method, status, the relevant response headers and the
timestamp. That file is a **Phase-0 deliverable**, reconstructed from the sourcing recon report, and
the rule attached to it is unforgiving: **any value in this document whose probe line cannot be
reconstructed is demoted to `[U]` at that point.** Without the log, a reader in three months cannot
tell an observation from a recollection, which is the exact failure this project exists to oppose.

**The expiry rule.** Rate limits, endpoints, auth requirements and licence tags rot faster than this
document will be revised. Three of them changed in the nine months before it was written -- OpenAlex
went metered, Semantic Scholar's anonymous pool died, OpenReview grew a bot challenge. So every row
in the master catalogue carries a `measured_at` in `ingest/sources.yaml`, and `make verify-sources`
re-probes every endpoint there, compares status code, auth requirement and any `X-RateLimit-*` or
`RateLimit` header against the recorded value, and writes `ingest/probes/<date>.jsonl`. CI runs it
**monthly** and opens one issue listing every drift. Without that job this document is accurate for
about six weeks; with it, drift becomes a dated issue instead of a silent wrong answer. It is about
forty HTTP requests and costs nothing.

Facts that could not be confirmed keep their `(unverified -- confirm before relying on this)`
marker when they are copied into code comments, adapter docstrings or the public About page.

---

## 1. The sourcing philosophy

**We automate discovery aggressively and field population conservatively.**

That single sentence constrains every decision in this document, so it is worth stating why.

Discovery -- finding out that a benchmark named `CY-Bench` exists, that it lives at
`cybench.agml.org`, that it was announced in a paper, that its repo was pushed three weeks ago -- is
cheap to automate, cheap to verify, and safe to get wrong. A false positive costs a curator ninety
seconds of reading a title and a classifier rationale. A false negative costs nothing that a second
discovery pass will not recover. The output of discovery is a **triage queue**, not data.

Field population -- deciding that CY-Bench belongs to the earth-climate family, that its primary
metric is NRMSE under leave-one-year-out with an explicit in-season lead time, that its licence is
permissive, that its score is not comparable across lead times -- is the opposite. It is expensive
to automate correctly, expensive to verify, and damaging to get wrong, because a wrong field is
indistinguishable from a right one at read time.

The distinction that actually holds is not between complete and incomplete data. **It is between
visible incompleteness and invisible wrongness.** Incompleteness is survivable when it is visible: a
null renders as "not curated", and a reader adjusts. A wrong field is not survivable, because a
reader who finds one silently wrong field has no way to know which of the other nineteen are wrong,
and reasonably stops trusting all of them. That is why this plan will happily publish 6,598 thin
machine-ingested Epoch claims at roughly 0.10 mean condition completeness -- badged, segregated and
excluded from comparison views -- and will refuse a single unsigned interpretive field. The earlier
draft claimed that "an index that is 95% correct is roughly 0% as useful", which was rhetoric
dressed as arithmetic and was contradicted by the Epoch decision on the page after it. This is the
defensible version, and it reconciles §1 with §3.1.

So the rule the adapters enforce:

> **An adapter may write identity and link fields automatically. It may not write interpretive
> fields into the citable core.** Interpretive output goes into a `_suggested` block on a draft
> record in the discovery tree, which a human promotes, edits or deletes. Promotion is the human's
> signature on the field.

| Class | Examples | Who writes it | Where it lands |
| --- | --- | --- | --- |
| Identity | canonical name, aliases, homepage, repo URL, arXiv ID, DOI, HF dataset ID | Adapter, directly | Draft record in `data/_discovery/` |
| Link and provenance | `source_url`, `retrieved_at`, `archive_url`, `adapter_version`, upstream licence tag | Adapter, directly, and required by CI | Draft record and `IngestBatch` |
| Observable signal | GitHub stars, HF downloads, `pushed_at`, leaderboard row counts, release dates | Adapter, directly | `metrics/`, outside the citable core |
| Numeric result claims | scores, stderr, run dates | Adapter | `data/claims/_ingested/<source>/`, badged `machine-ingested` |
| Interpretive | domain and capability facets, metric semantics, contamination status, saturation, lifecycle, material eval conditions | **Human only**, from a `_suggested` draft | `data/benchmarks/<family>/` after review |

The second half of the philosophy: **knowing that an entry needs attention is most of the value;
guessing its contents is most of the risk.** A scraper that reports "the SWE-bench Verified
leaderboard gained 14 rows and one row's score changed by 9 points" has done its entire job. A
scraper that decides what those rows mean has exceeded its mandate. This is why the catalogue's most
valuable automated output is not new records at all -- it is **change detection on records we
already have**, which keeps the index from dying the slow death catalogued in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §3, where every prior
cross-domain attempt went stale while still looking alive.

The failure mode to avoid is the firehose. Benchmark Radar ingests 37 sources into 14,810 raw
records and curates roughly 1,283 of them; the gap between those two numbers is where credibility
leaks out. We should be the opposite shape: fewer sources, each fully understood, each producing
records a human has signed. Two mechanisms make that enforceable rather than aspirational. The first
is the volume policy in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §8 --
**no machine-generated benchmark entity is ever published**, so the published benchmark count is by
construction the hand-reviewed count. The second is the capacity model in §5.4, which throttles
discovery to what a human can actually clear, because a queue nobody clears is a firehose with
better manners.

### 1.1 The `_suggested` mechanism, specified

The previous draft stated this rule in one sentence and left five questions unanswered, which made
it unenforceable. It is the load-bearing safety rule of the whole document, so here it is as a
specification.

**Where it lives.** Never in `data/benchmarks/`. A draft candidate is a file at
`data/_discovery/<source>/<candidate-id>.yaml`, in the tree that
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §8 Rule 1 excludes from
`facets.json`, from `corpus.json`, from Pagefind and from every count on the site. The citable
artifact therefore never contains a machine suggestion, and no diff on `data/benchmarks/` is
polluted by one.

**Its shape.** Per-field, not flat, because a bare value carries no way to judge it:

```yaml
# data/_discovery/arxiv/cand-2609-11492-cy-bench.yaml
candidate_id: cand-2609-11492-cy-bench
discovered_via: arxiv-oaipmh
discovered_at: 2026-09-18T06:41:00Z
triage:
  label: likely-benchmark          # likely-benchmark | uses-benchmark | survey | unclear
  rationale: "Abstract says 'we release CY-Bench, a benchmark for subnational crop yield'."
  classifier: claude-haiku-4-5
  classifier_prompt_version: triage-v3
  score: 0.91
  expires_at: 2026-12-17           # discovered_at + 90 days; see 5.4
identity:                          # adapter-written, no signature needed
  name: CY-Bench
  homepage: https://cybench.agml.org
  arxiv_id: "2609.11492"
_suggested:
  - field: domain.primary
    value: earth-climate/agriculture-yield
    adapter: arxiv-triage
    adapter_version: 0.2.1
    source_url: https://arxiv.org/abs/2609.11492
    fetched_at: 2026-09-18T06:41:00Z
    rationale: "Abstract names 'subnational crop yield forecasting' across 28 countries."
    confidence: 0.7
```

**What promotion means, mechanically.** `bench promote <candidate-id>` moves accepted values into a
new or existing file under `data/benchmarks/<family>/`, writes `curation.promoted_by` (the curator's
GitHub handle) and `curation.promoted_at`, sets `ingestion.field_provenance.<field>: curator` per
[04-data-model.md](04-data-model.md) §9, and leaves the candidate file in place with
`triage.outcome: promoted`, so the discovery decision itself is auditable. A curator who edits a
value before promoting gets `curator` provenance on it too -- the signature is on the value that
landed, not on the adapter's guess.

**Two CI checks, because content alone cannot distinguish a human facet from a bot facet.** A domain
slug written by a curator and one written by an adapter are byte-identical, so the check has to be
on authorship and on declared provenance, not on the string:

- **Check A (authorship).** Any commit whose author is the bot account and whose diff touches
  anything outside `data/_discovery/**`, `data/claims/_ingested/**`, `data/_ingest/**` and
  `metrics/**` fails the build. It is a path allowlist keyed on committer identity and it is three
  lines of CI.
- **Check B (declared provenance).** For every published `Benchmark`, every field named in
  `schema/interpretive_fields.yaml` must carry `ingestion.field_provenance.<field>: curator`, or
  `ingestion` must be null (a hand-authored record). The interpretive field list lives in exactly
  one file so that CI, the `_suggested` validator and the table above cannot drift apart.

Check A catches the bot writing directly. Check B catches a human pasting a `_suggested` block in
wholesale without reading it, which is the more likely failure and the harder one to see in review.
Both are routed to [05-repository-and-workflow.md](05-repository-and-workflow.md) §9 as additions to
the CI suite.

**What happens to a suggestion nobody promotes.** It expires with its candidate, on the 90-day rule
in §5.4. It never renders on the site, greyed or otherwise, because a rendered machine suggestion is
a published machine-generated field wearing a hat.

### 1.2 Licence cleanliness is a veto, not a sort key

The previous draft claimed sources were ordered "by licence cleanliness first, transport stability
second", then produced a build order that put GitHub -- where roughly 30% of benchmark repos declare
no licence at all `[M]` -- above arXiv, which is CC0 with a decade-stable API, and put LMArena's
CC-BY-4.0 parquet in the second wave. The stated criterion did not produce the stated order, which
means the criterion was decoration. Worse, HELM and Papers with Code were *gated* on licence
resolution while SWE-bench, Grand Challenge, Codabench, EvalAI, the small statics and every domain
hub were scheduled with an unresolved licence and no gate at all.

**The honest criterion, which §8 now uses: differentiator impact first, transport stability second,
with licence cleanliness as a veto applied uniformly.** A source that is technically easy and
legally ambiguous is not merely lower-ranked; its output is blocked from the published artifact
until the ambiguity is resolved, because an engineering problem can be fixed with engineering and a
licence problem can only be fixed by re-deriving every field it touched.

The veto is a mechanism, not an intention:

- An adapter **may be built** against a source whose terms are unresolved. Building it is how we
  learn what the data contains, and a built adapter is what makes the licence question concrete
  enough to ask a maintainer.
- Its output lands **only** in `data/_discovery/<source>/` (benchmark candidates) or in
  `data/claims/_ingested/<source>/` marked `licence_class: unlicensed` (claims).
  [04-data-model.md](04-data-model.md) §9's licence firewall already refuses to let an `unlicensed`
  or `share-alike` record into the CC-BY core.
- A record **cannot be promoted** while `IngestBatch.licence.spdx` is null. One tier-3 assertion,
  applied identically to every source in the table.
- The **licence-resolution checklist** in §8.4 carries one row per unresolved source, the question,
  who to ask, and a target date.

### 1.3 Capacity governs cadence

The third principle, and the one the previous draft omitted entirely: **discovery runs at the rate a
curator can clear it, not at the rate the sources can produce it.** Every prior cross-domain
catalogue died of the curation treadmill rather than of architecture, and a plan that sizes its
scrapers by yield and its curators by hope is a plan to join them. The capacity model, the WIP cap,
the expiry policy and the stub tier are in §5.4, and they are the numbers that bind everything else
in this document.

---

## 2. Master source catalogue

Fragility is judged as: **low** = static files or a decade-stable API, breaks loudly; **medium** = a
live API that could change shape, or an HTML structure we depend on; **high** = terms, pricing or
access model actively changed in the last 12 months, or an anti-bot layer is present.

`measured_at` is 2026-09-17 for every row; the column is omitted here for width and is carried
per-row in `ingest/sources.yaml`, which is what `make verify-sources` reads.

| Source | What it gives us | Access mechanism | Auth | Rate limit | Licence | ToS posture on automated access | Cadence | Fragility | Populates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Epoch AI** | 81 benchmarks with `random_baseline`, `score_ceiling`, `superseded_by`; 390 models with org, country, training FLOP; 6,598 result rows, 42.7% carrying an uncertainty figure `[M]` | Static ZIP + CSV over HTTPS | None | None stated `[D]`; poll weekly on ETag | **CC-BY 4.0** `[M]`, verbatim in the ZIP's README | `/data/` not disallowed; `/inspect-viewer/` and FrontierMath problems explicitly disallowed `[M]` | Page said "Updated Sep. 17, 2026"; no stated schedule `[U]` | Low | Benchmark, System, Organization, ResultClaim |
| **HuggingFace Hub** | Dataset/model/Space metadata, the `benchmark:*` and `leaderboard` tag taxonomy, Croissant JSON-LD per dataset, `paperswithcode_id` join key | REST `huggingface.co/api/*`, OpenAPI at `/.well-known/openapi.json` | None (free token doubles limits) | Anon 500 API calls / 5 min per IP; free user 1,000; PRO 2,500 `[D]` | Per-artifact; API access permissive | `robots.txt: Allow: /` `[M]`; documented public API with published tiers | Continuous | Low (API), medium (tags) | Benchmark, Leaderboard, System, Organization, adoption signal |
| **GitHub** | Repo metadata, topics, SPDX licence, `pushed_at` liveness, release tags, CITATION.cff; and via clone, the eval-harness YAML corpora | REST v3 + GraphQL; `git clone --depth 1` | PAT strongly recommended | Unauth 60/hr core `[M]`, 10/min search `[M]`; PAT 5,000/hr, 30/min search `[D]`; Actions `GITHUB_TOKEN` only 1,000/hr/repo `[D]` | Repo metadata factual; README text under each repo's own licence | ToS-sanctioned; robots.txt explicitly directs bots to the API `[M]` | Continuous | Low | Benchmark, EvalConditions, Organization, maintenance signal |
| **arXiv** | New-benchmark discovery, abstracts, authors, arXiv-to-DOI | Query API `export.arxiv.org/api/query`; OAI-PMH `oaipmh.arxiv.org/oai`; RSS | None | ToU 1 request / 3 s, single connection `[D]`; HTML `Crawl-delay: 15` `[M]` | **Metadata CC0 1.0** `[D]` | Metadata harvesting explicitly permitted; full-content harvesting not `[M]` | Daily announcements, `skipDays: Sat, Sun` `[M]` | Low | Benchmark (draft), Source, Organization (noisy) |
| **HELM public bucket** | 26 suites `[M]` including `robo-reward-bench`, `medhelm`, `finance`, `audio`, `vhelm`; `run_specs.json` with shots, CoT flag, temperature, retries, deployment | Anonymous GCS bucket `crfm-helm-public`, XML and JSON listing | None | None observed `[M]` | Code Apache-2.0; **bucket data licence `[U]`** | Public bucket, listable | Per release (`lite` at v1.13.0 `[M]`) | Medium | EvalConditions, ResultClaim, Benchmark |
| **LMArena / Arena** | 13+ arenas of human-preference leaderboard snapshots, incl. agent, search, document, video; style-control variants | HF dataset `lmarena-ai/leaderboard-dataset`, parquet | None | HF limits | **CC-BY-4.0** `[M]` (HF repo tag) | Hosted for download; `arena.ai robots.txt: Allow: /` `[M]` | Snapshot; last modified 2026-09-16 `[M]` | Low | Leaderboard, ResultClaim, System, RatingPool |
| **Every Eval Ever** | 2,273 benchmarks, 22,235 models, 31 eval formats, and the `eval.schema.json` field names we adopt | HF `evaleval/EEE_datastore` + GitHub `evaleval/every_eval_ever` | None | HF limits | **Data CC BY 4.0, code MIT** `[D]` | Published for reuse; PR-based contribution with a `validate` CLI | Active (659 commits `[M]`) | Low | Field-name alignment, ResultClaim cross-reference, alliance |
| **SWE-bench** | 5 leaderboards, 323 result claims `[M]` with `agent`, `agent_org`, `reasoning_effort`, `instance_calls`, `cost`, `checked` | JSON inlined in the page as `<script id="leaderboard-data">` | None | None stated; self-throttle | `[U]` -- no licence statement found | No robots prohibition observed `[M]` | Continuous | Medium | ResultClaim, EvalConditions, System |
| **Grand Challenge** | 264 medical-imaging challenges `[M]` with status, dates, submission types and `publications[]` | REST `grand-challenge.org/api/v1/challenges/` | None | None documented; self-throttle to 1 req / 2 s | `[U]` | Open public API, no anti-bot `[M]` | Rolling; challenges open into 2027 | Low | Benchmark, Source, Organization |
| **Papers with Code archive** | 9,327 benchmarks, 5,628 datasets, 79,817 paper-code links, `evaluation-tables` (2.25k rows `[M]`) -- the largest cold-start corpus available | HF org `pwc-archive`, dataset downloads | None | HF limits | **CC-BY-SA-4.0 (viral)**; basis is the HF repo tag `[M]` -- see §3.9 | Frozen snapshot, published for reuse | Frozen at ~Sept 2025 | Low (frozen) | **Identifier crosswalk only** -- no content committed |
| **inspect_evals (UK AISI)** | 171 evals `[M]` with derived metadata; `inspect_evals_id` cross-reference and a runnability flag; the `/register/` flow we copy | GitHub repo | PAT | GitHub limits | **MIT** `[M]` | Public repo | Pushed 2026-09-17 `[M]` | Low | Benchmark cross-ref, EvalConditions |
| **MTEB results** | ~600 MB of embedding-benchmark result JSON across 1,000+ tasks | `git clone --depth 1 github.com/embeddings-benchmark/results` | PAT | GitHub limits | **CC0-1.0** `[M]` | Public repo | Daily; pushed 2026-09-16 `[M]` | Low | ResultClaim, Benchmark |
| **OpenAlex** | Institution/ROR resolution, venue, OA status, topic concepts | REST `api.openalex.org`; free monthly S3 snapshot | **Key now effectively required** | Measured unauth 1,000 credits/day, $0.10/day budget `[M]`; docs disagree -- see §3.10 | **CC0** `[D]` | Polite pool via `mailto`; metered API | Monthly snapshot | **High** (pricing changed mid-2026; docs disagree with live behaviour) | Organization, Source, topic tags -- **citation counts flagged** |
| **Semantic Scholar** | arXiv-to-paper identity resolution (better than OpenAlex), cleaner citation counts, `tldr` | REST `api.semanticscholar.org/graph/v1`; S2AG/S2ORC bulk | **Key required in practice** | Unauth pool 429s on first request `[M]`; with key, documented 1 RPS `[D]` | API License Agreement; corpora ODC-BY 1.0 `[U]` for 2026 | Key form published; unauth tier globally contended | Continuous | Medium | Source, citation counts |
| **Crossref** | DOI to metadata resolution | REST `api.crossref.org` | None (polite pool via `mailto`) | Polite pool `[D]` | Metadata open | Explicitly bot-friendly | Continuous | Low | Source |
| **DataCite** | arXiv and Zenodo DOI metadata | REST `api.datacite.org/dois` | None | Not measured | Metadata open | Public API | Continuous | Medium (response schema `[U]`) | Source |
| **Zenodo** | DOIs and `conceptdoi` (version-independent) for benchmark releases; also where we mint our own DOI | REST `zenodo.org/api/records` | None for read | Not measured | Per-record | Public API `[M]` | Continuous | Low | Source, Benchmark version lineage |
| **NeurIPS D&B proceedings** | 497 accepted benchmark/dataset papers in 2025 `[M]`, with mandated Croissant metadata | Static HTML `proceedings.neurips.cc/paper_files/paper/{year}` + per-paper JSON/bib | None | Self-throttle | Proceedings terms `[U]` | Static index pages, no anti-bot `[M]` | Annual, December | Low | Benchmark, Source |
| **OpenReview API2** | Would give D&B submissions and reviews | REST `api2.openreview.net` | Anonymous **blocked** | n/a | n/a | **Returns HTTP 403 `ChallengeRequiredError` to anonymous clients** `[M]` | n/a | High | Nothing -- do not build |
| **Codabench** | 1,498 public competitions `[M]`, filtered to a few hundred candidates per §3.14 | REST `codabench.org/api/competitions/` | None for catalogue | Not documented; self-throttle | `[U]` | Open API; results endpoint admin-only `[M]` | Rolling | Medium | Benchmark discovery only |
| **EvalAI** | 1,053 challenges `[M]`, filtered per §3.14 | REST `eval.ai/api/challenges/challenge/all/all/all` | None for catalogue | Not documented | `[U]` | Open API; leaderboard endpoint returns "not public" `[M]` | Rolling | Medium | Benchmark discovery only |
| **Kaggle** | Competitions and datasets, Croissant export; hosts ARC Prize, Image Matching, BirdCLEF, Game Arena | REST `kaggle.com/api/v1/*`, CLI | **Required** (`kaggle.json`) | **Not publicly documented `[U]`** | Per-competition | ToS restricts bulk scraping `[D]` | Rolling | Medium | Benchmark discovery, second wave |
| **OpenRouter** | 444 models `[M]` with pricing, context, modalities, `hugging_face_id` join key | REST `openrouter.ai/api/v1/models` | None | Not measured | **CC BY 4.0** `[D]` | Public documented API | Continuous | Low | System |
| **LiteLLM price file** | 2,591,466 bytes `[M]` of model pricing and context windows, ETag present | `raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` | None | GitHub raw limits | Repo MIT; file-specific `[U]` | Public repo | Continuous | Low | System |
| **Vendor release feeds** | Model announcements | OpenAI `openai.com/news/rss.xml` `[M]`; Google `blog.google/rss/` `[M]`; **Anthropic has no RSS** (both candidate URLs 404 `[M]`) | None | n/a | Press content | Public feeds | Continuous | Medium | System (human-confirmed) |
| **Artificial Analysis** | 30+ evals across text, image, video, speech, music | REST `artificialanalysis.ai/api/v2` | **`x-api-key` required** `[M]` | Free 100 req / 24 h `[D]`; one page said 1,000/day -- conflicting `[U]` | **Attribution required all tiers; redistribution requires a contract** `[D]` | `robots.txt: Allow: /` `[M]` | Continuous | High (legal, not technical) | **Link-out only; never ingested** |
| **Wayback SPN2 + CDX** | Permanent archive URLs for every non-DOI source | `POST web.archive.org/save`; `GET web.archive.org/cdx/search/cdx` | `Authorization: LOW key:secret` for SPN2 | Auth 12 concurrent / 100,000 per day; anon 6 / 4,000; 10x per URL per day `[U]` -- from IA's spec doc, not re-read live | IA terms | Published API for exactly this purpose | On ingest + scheduled re-check | Medium | `archive_url` on every Source |
| **Community submission (issue form)** | Benchmark existence, author-supplied links, corrections -- the class no scraper reaches | GitHub issue template -> validation bot -> auto-PR ([05-repository-and-workflow.md](05-repository-and-workflow.md) §6) | None for the contributor | n/a | **Contributor grants CC-BY-4.0 on submit** -- see §3.20 | Ours | Continuous | Low | Benchmark draft, Source, correction |
| **Small static leaderboards** | EvalPlus `evalplus.github.io/results.json` (34,305 bytes `[M]`); LiveBench dated CSVs (9,893 bytes `[M]`); OGB HTML tables | Static files / HTML | None | Self-throttle | Per-project, mostly `[U]` | No prohibitions observed | Irregular | Low to medium | ResultClaim |
| **Domain challenge hubs** | CASP/CAMEO, Matbench Discovery, Open Catalyst, WeatherBench 2, GEO-Bench 2, DCASE, LifeCLEF, ARC Prize, robotics cluster | Mostly HTML; Matbench Discovery has `/api`, `/data/sets` and RSS `[D]` | None | Be generous -- small academic servers | Mostly `[U]` | Mostly no stated policy | Annual to biennial cycles | High (structurally) | Benchmark -- **manual sweep, §6** |
| **DrivenData** | Competitions | -- | -- | -- | -- | **`robots.txt` disallows `/*/leaderboard_partial` and `/competitions/search/`** `[M]` | -- | -- | **Manual curation only; never scraped** |
| **BenchmarkList / Benchmark Radar** | Competitor catalogues | -- | -- | -- | No licence / CC BY-NC-SA 4.0 | -- | -- | -- | **Never ingested -- see §4 and §9** |

---

## 3. Per-source detail

Each subsection follows the same shape: **endpoints, an example request, what we extract, the
mapping to our schema, the known pitfalls, and what we do when it breaks.** The previous draft
promised that contract and honoured it for six of eighteen subsections; twelve had no failure
response, and all but three listed source fields without ever saying where they land. A field list
is not a mapping. The mapping is where the work and the disagreements are, and an adapter without a
documented failure response becomes an adapter that silently writes nulls, which is the mechanism by
which catalogues rot while looking healthy.

Where a source field has no home in [04-data-model.md](04-data-model.md), the mapping block says so
explicitly -- either `-> drop` with a reason, or `-> request` with a pointer to §11. Silently
orphaning a field is how a schema gap becomes a data-loss event nobody notices for a year.

### 3.0 Adapter health is a published field

Before any individual source: the prescription throughout this document is "hard fail, open
`adapter-broken`". For a one-to-two-person part-time team, an `adapter-broken` issue is a thing that
sits for a quarter while the site keeps serving the last good ingest and looking healthy. That is
precisely the Ecosystem Graphs failure this plan cites disapprovingly -- twenty months stale, still
used as a data source in 2025-26 research. A plan that applies the staleness critique to everyone
except itself has not learned the lesson.

So adapter health is not an internal alarm. It is a published field, and the SLO is stated in
public:

- Every `Source` and every adapter carries `last_successful_run`, `last_content_change` and
  `adapter_status` (`ok | degraded | broken | retired`).
- The build derives a per-record `source_freshness` and renders a "last verified" badge on any
  record whose sole live source has not refreshed in more than 90 days. The mechanism -- the
  `build/derived/ingest-health.json` artifact and the per-source freshness strip -- is owned by
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §9.1; the per-entry
  `curation.last_verified` display is owned by
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §7. This document owns only the
  policy that source health is public.
- A public `/sources` page is generated from the same data: one row per source, its licence, its
  attribution, its last successful fetch and its current status.

**The SLO, stated plainly and published on that page:** *a broken Tier-1 adapter is fixed within two
weeks or every record depending on it is badged stale; a broken Tier-2 adapter is badged at 30 days;
a retired adapter's records keep their last-known values with a permanent "source retired" badge and
a link to the archived snapshot.* We publish our own rot. It is the cheapest honesty mechanism
available and it converts the project's largest self-risk into the differentiator that
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1 calls liveness signalling --
the thing no catalogue the landscape recon examined provides (an absence observed across roughly a
dozen catalogues, not a proof that none exists -- unverified, confirm before relying on this).

### 3.1 Epoch AI -- build this adapter first

**Endpoints.** Static files, no API:

```
GET https://epoch.ai/data/benchmark_data.zip        # ~2.3 MB, Content-Type: application/zip  [M]
GET https://epoch.ai/data/notable_ai_models.csv     # 2,254,959 bytes  [M]
GET https://epoch.ai/data/large_scale_ai_models.csv # 1,107,528 bytes  [M]
```

The ZIP returned `ETag: "a95a0b35dd410ad483b45f53e3725590"` and **no `Last-Modified` header** `[M]`,
so conditional fetching must use `If-None-Match` only. A local unpacked copy already exists at
`epochdl/` (87 entries) and is the working baseline.

**What we extract.** `benchmark_metadata.csv` gives 81 benchmarks with columns `benchmark, in_eci,
source_file, score_column, scale, random_baseline, score_ceiling, release_date, superseded_by` `[M]`.
`model_metadata.csv` gives `model_version, model_group, date, display_name, organization, country,
accessibility, training_compute_flop` `[M]`. Eighty per-benchmark CSVs hold **6,598 rows**, mean
82.5 rows per file `[M]`.

**Mapping.**

| Epoch field | Ours | Note |
| --- | --- | --- |
| `benchmark` | `Benchmark.external_ids.epoch` | **Never** the id. The string conflates benchmark, tier, snapshot and access mode (`FrontierMath-Tier-4-2025-07-01-Private`). Id allocation stays manual per [04-data-model.md](04-data-model.md) §3 |
| `random_baseline`, `score_ceiling` | `Baseline` records | The two anchors headroom needs ([12-analytics-and-trends.md](12-analytics-and-trends.md)). `score_ceiling` is a *measurement* ceiling, not a human baseline; conflating them would be a real error |
| `superseded_by` | `Benchmark` lineage edge | Epoch needing this column is independent evidence that supersession is a real unsolved modelling problem |
| `scale`, `score_column` | `Metric.range`, `Metric.id` | |
| `Model version` | `System` + `SystemVersion` + `EvalConditions.reasoning_effort` | A three-way split from one string. **927** distinct `model_version` strings appear in the benchmark CSVs and all 927 join internally to `model_metadata.csv` `[M]`, so the crosswalk population is 927. (`model_metadata.csv` itself carries 1,048 distinct strings; the extra 121 never appear in a result row and need no crosswalk. [00-vision-and-scope.md](00-vision-and-scope.md) §8.1 owns the counting rule that separates the two.) The single largest manual cost in the ingest |
| `mean_score`, `Best score (across scorers)` | Two separate `ResultClaim`s, the second `claim_type: best-of` | Never averaged together |
| `stderr`, `* SE`, `95% CI low/high`, `Overall std dev` | `ResultClaim.uncertainty.{type,value}` | Present on **2,819 of 6,598 rows = 42.7%** `[M]`. 62 distinct header signatures across 80 files means roughly 80 small per-file mapping stanzas, not a generic parser `[M]` |
| `Shots` | `EvalConditions.shots` | In 14 of 80 files, filled on 1,283 of 6,598 rows = **19.4%** `[M]`; values dirty (`5`, `few`, `0-shot`, `25-shot`) |
| `Logs`, `Log viewer` | `ResultClaim.artifact_url` | **828 public, 459 private, 263 blank** `[M]`. The 828 public Inspect `.eval` logs are the closest thing in the corpus to rerunnable evidence |
| `Source`, `Source link` | `ResultClaim.source` -> a `Source` record | Filled on 3,985 of 6,598 = 60.4% `[M]`; for the 1,550 Epoch-run rows the source is Epoch itself |
| `Training compute (FLOP)`, notes | `System.training_compute_flop` + `training_compute_estimated` + notes | Schema addition, §11 |
| `organization`, `country` | `Organization` refs | Comma-joined for joint work; must be split. `Google DeepMind` and `Google` appear separately *and* jointly -- a `parent_org` relation we have to author |
| `in_eci`, `eci_scores.csv`, `edi_scores.csv`, `eci_bootstraps.json` | **-> drop** | ECI is a single-number latent-ability index. Constraint 3 forbids us shipping one; ingesting someone else's would be the same error with a citation |
| `model_versions` in `large_scale_ai_models.csv` | **-> drop** | Empty in all 266 rows `[M]`; the join is broken in this export |

**Pitfalls.** The `epochai` PyPI client reads Airtable and requires you to duplicate their base into
your own workspace with a personal access token, because Airtable does not permit public API access
`[D]`. That duplicate goes stale the moment they edit theirs, so it is not an ingestion path -- use
the ZIP. Epoch's `robots.txt` disallows `/inspect-viewer/` and
`/frontiermath/tiers-1-4/benchmark-problems`, with the stated reason of avoiding training-set
contamination `[M]`; honour it, both because it is right and because violating it would be a
reputational own-goal for a project whose stated ethics include not contributing to contamination.
Never dedupe on ingest: 843 rows share a `Model version` with another row in the same file `[M]`, and
those are a mix of genuine conflicting claims (which the schema wants), the same run listed twice
under two spellings of one source, and different reasoning efforts collapsed onto one key. An
automated dedupe will silently merge distinct claims or silently duplicate identical ones.

**When it breaks.** A 404 or a changed ZIP structure is a hard failure: open `adapter-broken`, do
not write a PR, keep serving the last good ingest, and flip `adapter_status` so §3.0's badge fires at
14 days. Because the data is CC-BY and already on disk, an Epoch outage never degrades the site -- it
freezes one tree. A changed column header in one of the 80 per-file stanzas is the likelier failure
and must also be a hard fail: assert the expected header set per file, never `.get()` with a default.

**Policy (settled).** Epoch rows land in `data/claims/_ingested/epoch/` with
`curation.verification_status: machine-ingested`, an honestly computed `condition_completeness`
(expect a mean around 0.10 -- Epoch publishes scores, not conditions `[M]`), and full provenance.
They are never mixed into `data/claims/` proper. Browse views show them; comparison views hide them
below a completeness threshold. Benchmark rows become **stubs only**, unpublished until a human
assigns facets. Four schema fields must exist before the first ingest, because retrofitting 6,598
rows is miserable: `ResultClaim.artifact_url`, `ResultClaim.provenance_snapshot`,
`System.training_compute_flop` with an `estimated` flag, and `EvalConditions.reasoning_effort` as
enum-plus-free-text. [04-data-model.md](04-data-model.md) §15 carries the full pre-ingest list.

### 3.2 HuggingFace Hub -- the single best live source

**Endpoints.**

```
GET https://huggingface.co/api/spaces?filter=leaderboard&limit=1000
GET https://huggingface.co/api/datasets?filter=benchmark:official
GET https://huggingface.co/api/datasets/{owner}/{name}?full=true
GET https://huggingface.co/api/datasets/{owner}/{name}/croissant
GET https://huggingface.co/api/models?sort=createdAt&direction=-1&limit=100
GET https://huggingface.co/api/daily_papers?limit=100
GET https://huggingface.co/api/collections/{namespace}/{slug}
```

**Rate limits** `[D]`, in fixed 5-minute windows, per IP for anonymous clients: anonymous 500 API
calls, free user 1,000, PRO 2,500, Enterprise 6,000. 429s carry `RateLimit` and `RateLimit-Policy`
headers per `draft-ietf-httpapi-ratelimit-headers` `[D]`, and `huggingface_hub` is documented as
parsing them and sleeping exactly; the `>= 1.2.0` version floor comes from the recon's doc read
rather than from a changelog diff (unverified -- confirm before pinning). **Use the library, not raw
HTTP.** Pagination is a cursor in the `Link: ...; rel="next"` header `[M]`; `limit=1000` works `[M]`;
`full=true` inflates payloads heavily, so fetch listings slim and detail selectively.

**The tag taxonomy is the gift.** `?filter=leaderboard` on Spaces returned **1,019** results `[M]`.
Enumerating tags across the first 1,000 produced a vocabulary that maps almost one-to-one onto our
`comparability_key` and `Leaderboard` entity:

| Namespace | Observed values (count in the 1,000-Space sample) `[M]` |
| --- | --- |
| `test:` | `public` (110), `private` (18) |
| `submission:` | `manual` (39), `automatic` (27), `semiautomatic` (10) |
| `judge:` | `auto` (73), `function` (17), `vlm-judge` (4) |
| `eval:` | `code` (76), `generation` (47), `math` (30), `safety` (15) |
| `modality:` | `text` (79) |
| `language:` | `english` (29, plus 22 under a cased variant), `polish` (6), `japanese` (4), `korean` (4) |
| `domain:` | `financial` (10) |
| free tags | `benchmark` (92), `evaluation` (42), `asr` (13), `arena` (7), `agents` (7), `ocr` (7), `chemistry` (5), `rag` (4) |

**Mapping.**

| HF field | Ours |
| --- | --- |
| `test:public` / `test:private` | `Benchmark.data.access` and contamination posture -- as a `_suggested` hint, never directly |
| `submission:*` | `Leaderboard.submission_process` |
| `judge:auto` / `judge:function` / `judge:vlm-judge` | `EvalConditions.judge_model` presence and kind |
| `eval:*`, `modality:*`, `language:*`, `domain:*` | `_suggested` facet hints, `source: hf_space_tag` |
| dataset tag `license:*` | `Benchmark.data.licence`, carried through verbatim |
| dataset tag `arxiv:NNNN.NNNNN` | `Benchmark.external_ids.arxiv` -> `Source` |
| `paperswithcode_id` | `Benchmark.external_ids.papers_with_code` -- the free join key to the PwC archive |
| `lastModified` | `metrics/` liveness signal |
| `downloads` (30-day), `likes` | `metrics/` adoption series -- a 30-day window, **not** cumulative, so we store our own series |
| `gated`, `disabled` | `Benchmark.data.access: credentialed`; `disabled` proposes lifecycle `withdrawn` |
| `cardData` (YAML front matter) | `_suggested` only -- it is author prose, not fact |
| `/croissant` JSON-LD | `Benchmark.croissant_url`, and the normalisation target for the `croissant-benchmark` extension |
| `siblings[]` file list | **-> drop.** File lists describe dataset contents, and we do not model contents |

Two caveats, both material. The tags are self-declared by Space authors and sparsely applied --
**128 of the 1,000 sampled Spaces carried any `test:*` tag -- 12.8%** `[M]` (the previous draft said
11%, a mis-transcription of the same counts; this section owns the figure and every other document
should cite it rather than restate it). So they are hints stamped `source: hf_space_tag`,
never ground truth. And `language:english` / `language:English` appear as distinct values `[M]`, so
normalisation is mandatory.

**Dataset-side filters.** `?filter=benchmark:official` returned **47 datasets** `[M]`, led by
`openai/gsm8k` (1.25M downloads), `TIGER-Lab/MMLU-Pro` (246k), `harborframework/terminal-bench-2.1`
(132k), `Idavidrein/gpqa` (128k). `?filter=benchmark:eval-yaml` returned 48; `benchmark:community`
returned 0; `?filter=croissant` returned 203 `[M]`. These are **high precision, low recall** -- a
curated seed list and a cross-check, not a discovery mechanism.

**Pitfalls.** The `benchmark:*` namespace is new and could be renamed or deprecated; pin the adapter
to fail loudly rather than silently returning zero rows. `gated: true` datasets are a real access
class (PhysioNet-style credentialing, DUAs) and must be modelled, not skipped.

**When it breaks.** A zero-row response from a filter that previously returned dozens is schema
drift, not an empty result: hard fail, open `adapter-broken`, assert structure explicitly. A 429
storm is a soft failure -- back off on the `RateLimit` header and resume next run. If the tag
namespace is renamed, the adapter must stop rather than fall back to free-text matching, because a
silent fallback converts a high-precision seed list into a low-precision one with no visible change.

### 3.3 GitHub -- metadata, liveness, and the eval-conditions corpus

**Rate limits.** Unauthenticated 60/hr core and 10/min search `[M]`; a personal access token gives
5,000/hr core and 30/min search `[D]`; the ambient `GITHUB_TOKEN` inside Actions gives only
**1,000/hr per repository** `[D]`, which is the gotcha that will bite anyone who assumes the runner
token is enough. Mint a fine-grained PAT and store it as a repo secret. Secondary limits: at most
100 concurrent requests and 900 points/min `[D]`.

`If-None-Match` 304s are documented as **not counting against the limit** `[D]`, and that single
documented claim is the entire justification for calling a weekly sweep of a few thousand repos
affordable. It is therefore the first thing `make verify-sources` checks, with a scripted probe that
issues 100 conditional requests and compares `X-RateLimit-Remaining` before and after. If the
documentation is wrong, the sweep cadence drops from weekly to monthly and the budget in
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §10 is wrong by a factor of four --
which is worth ten minutes of verification.

**Mapping.**

| GitHub field | Ours |
| --- | --- |
| `pushed_at` | `metrics/` liveness -> the observable behind `Benchmark.lifecycle: dead`, proposed by bot and confirmed by two humans |
| `license.spdx_id` | `Benchmark.code_licence`; `null` is a *value*, not a missing field |
| `stargazers_count`, `forks_count`, `subscribers_count` | `metrics/` adoption series, snapshotted weekly |
| `created_at` | `Benchmark.release_date` candidate, `_suggested` only -- a repo predates a release as often as not |
| `topics[]` | `_suggested` facet hints |
| `homepage` | `Benchmark.homepage` |
| `CITATION.cff` | `Source` record, and the one place a repo states how it wants to be cited |
| release tags | `BenchmarkVersion` candidates |
| README prose | **-> drop.** Store README-derived *facts*, never README *text*: roughly 30% of benchmark repos declare no licence at all (`SWE-bench/experiments` returned `license: null` `[M]`), so the prose is unlicensed by default, and that rule is what keeps our CC-BY core clean |

The live probe of `SWE-bench/SWE-bench` returned 5,863 stars, 972 forks, MIT, created 2023-10-04,
pushed 2026-09-02, topics `["benchmark","language-model","software-engineering"]`, homepage
`https://www.swebench.com` `[M]`.

`pushed_at` is the single most valuable field in this document that nobody else uses. It is the
observable behind liveness -- the "this benchmark is dead" signal quantified by the withdrawn
AISafetyBenchExplorer study at 137 of 195 safety benchmarks having stale repos, and by BetterBench at
17 of 24 benchmarks having no working reproduction scripts.

**The clone targets matter more than the API.** Three repos, cloned shallow, are worth more than any
number of API calls:

| Repo | Stars `[M]` | Licence | Last push `[M]` | Why |
| --- | --- | --- | --- | --- |
| `EleutherAI/lm-evaluation-harness` | 14,007 | MIT | 2026-09-14 | **227 task directories** of YAML carrying `num_fewshot`, `output_type`, `metric_list`, `dataset_path`, `doc_to_text` -- machine-readable eval conditions for hundreds of benchmarks |
| `embeddings-benchmark/results` | 61 | **CC0-1.0** | 2026-09-16 | ~600 MB of MTEB result JSON, public domain, daily |
| `UKGovernmentBEIS/inspect_evals` | 674 | MIT | 2026-09-17 | 171 evals; gives `inspect_evals_id` and a runnability flag; their `/register/` flow is the model for our own contribution path |

Harness YAML maps directly: `num_fewshot -> EvalConditions.shots`, `output_type ->
EvalConditions.output_mode`, `metric_list -> Metric`, `dataset_path ->
Benchmark.external_ids.huggingface`, `doc_to_text -> EvalConditions.prompt_template_source` -- a
pointer, never the template text, because the template is the repo's own copyrighted work.
`lm-evaluation-harness` is arguably the best single source of structured evaluation-condition data in
existence: MIT, one clone, and it populates `comparability_key` fields that would otherwise be null
forever.

**Pitfalls.** Do not build star-history: `Accept: application/vnd.github.star+json` on `/stargazers`
requires auth and paginates at 100 per page over the entire star list `[M]`, which is 50 requests for
a 5,000-star repo. Snapshot `stargazers_count` once a week instead and accumulate the curve
ourselves; it costs one request and gives the same series going forward.

**When it breaks.** Rate-limit exhaustion is a soft failure: back off, resume next run. A 404 on a
repo we have catalogued is **signal, not error** -- the benchmark's home disappeared, so it raises a
lifecycle review rather than being swallowed. A clone target that changes its directory layout is a
hard fail: assert the layout, do not glob hopefully.

### 3.4 arXiv -- discovery, and the honest limits of it

**Endpoints.** Query API `https://export.arxiv.org/api/query` (Atom 1.0); OAI-PMH
`https://oaipmh.arxiv.org/oai`; RSS `https://rss.arxiv.org/rss/{cat}`. **HTTPS is mandatory** -- the
`http://` form 301s and yields an empty body if redirects are not followed `[M]`, which cost the
recon two probes and will cost us a debugging afternoon if it is not written down.

```
GET https://export.arxiv.org/api/query
    ?search_query=cat:cs.CL+AND+abs:%22benchmark%22
    &start=0&max_results=100
    &sortBy=submittedDate&sortOrder=descending
```

Date-window form, verified `[M]`: `submittedDate:[202609100000 TO 202609170000]`.

**OAI-PMH is the right tool for incremental harvest.** `verb=Identify` reports `earliestDatestamp
2005-09-16`, `deletedRecord persistent`, `granularity YYYY-MM-DD` `[M]`. Sets are coarse -- the top
level is `cs`, `math`, `physics`, `q-bio`, `stat`, `eess`, `econ`, `q-fin`, and **there is no `cs.CL`
set** `[M]` -- but each record's header carries subcategory setSpecs (`cs:cs:AI`, `cs:cs:RO`) and
`arXivRaw` carries `<categories>`. So harvest `set=cs` and filter client-side. One day of `set=cs`
was measured at **3.1 MB and 1,157 records** `[M]`. Note that `from`/`until` operate on the
modification datestamp, so v2 resubmissions of old papers arrive mixed in -- the first record pulled
in the probe was arXiv 1304.3111 from 2013 `[M]`. The adapter must distinguish "new paper" from
"revised paper" or it will re-triage the same work forever.

**Mapping.**

| arXiv field | Ours |
| --- | --- |
| `id`, `10.48550/arXiv.*` | `Benchmark.external_ids.arxiv` and a `Source` with `doi` |
| `title`, `summary`, `published`, `updated` | Triage-candidate fields. `summary` is **never** copied into `Benchmark.description`; we write our own from the paper |
| `author[]` | `_suggested` organization hints. arXiv has no structured affiliation field, so this is noisy by construction |
| `categories` | `_suggested` domain hint only. A `cs.RO` paper is not necessarily a robotics benchmark |
| everything else | **-> drop.** We are metadata-only |

**Licence.** Metadata is **CC0 1.0** `[D]`. Full-content harvesting is not permitted; `/e-print`,
`/src`, `/find`, `/refs` and `/cits` are disallowed in robots.txt, whose header comment reads
"Indiscriminate automated downloads from this site are not permitted" `[M]`. We are metadata-only by
charter, so this costs us nothing -- and it belongs on the About page, because it is a differentiator
against catalogues that mirror content.

**Discovery precision and recall are in §5**, because the numbers apply to the whole discovery
programme rather than to arXiv alone.

**When it breaks.** The arXiv API has been in continuous service since 2008 and the recon
characterises its response shape as unbroken in that time (not independently verified -- confirm
before relying on this). The realistic failures are the HTTPS trap and throttle violations. Policy:
1 request per 3 seconds for the API and 1 per 15 seconds for anything on `arxiv.org` HTML, enforced
in the fetcher rather than by developer discipline
([07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §10.1 owns the mechanism). An
OAI-PMH `badResumptionToken` mid-harvest is a soft failure: persist the last successful `until`
datestamp and resume, never restart from `earliestDatestamp`.

### 3.5 HELM -- the richest eval-conditions data on the public internet

**Endpoints.** An anonymous, listable GCS bucket:

```
GET https://storage.googleapis.com/crfm-helm-public/?prefix=lite/benchmark_output/releases/&delimiter=/
GET https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o?prefix=...&delimiter=/
```

**26 suites** are present `[M]`, including `robo-reward-bench` (robotics), `medhelm` (medicine),
`finance`, `audio`, `heim` and `vhelm` (image and vision), `arabic`, `cleva`, `seahelm`, `thaiexam`,
`torr` and `long-context`. HELM alone delivers genuine cross-modality breadth, which is why it is
high on the second wave despite the licence question.

Per release (for example `lite/benchmark_output/releases/v1.13.0/`): `runs.json` (3.93 MB),
**`run_specs.json` (95 KB, 2,546 specs)**, `schema.json`, `groups.json`, `groups_metadata.json`,
`runs_to_run_suites.json`, `costs.json`, `summary.json` `[M]`.

**What makes `run_specs.json` the prize**, from a real record `[M]`:

```json
{"name":"commonsense:dataset=openbookqa,method=multiple_choice_joint,model=01-ai_yi-34b",
 "scenario_spec":{"class_name":"helm.benchmark.scenarios.commonsense_scenario.OpenBookQA"},
 "adapter_spec":{"method":"multiple_choice_joint","max_train_instances":5,"max_eval_instances":1000,
   "num_outputs":5,"num_train_trials":1,"temperature":0.0,"max_tokens":1,
   "chain_of_thought_prefix":"","stop_sequences":["\n"],
   "model":"01-ai/yi-34b","model_deployment":"together/yi-34b"},
 "metric_specs":[{"class_name":"...BasicMetric","args":{"names":["exact_match","quasi_exact_match"]}}]}
```

**Mapping.**

| HELM field | Ours |
| --- | --- |
| `adapter_spec.max_train_instances` | `EvalConditions.shots` |
| `adapter_spec.chain_of_thought_prefix` | `EvalConditions.chain_of_thought`. An empty string means a *known* off, not a null -- and that distinction is exactly what `condition_completeness` measures |
| `adapter_spec.temperature`, `num_outputs`, `num_train_trials` | `EvalConditions.sampling.{temperature,n,trials}` |
| `adapter_spec.method` | `EvalConditions.output_mode` |
| `adapter_spec.max_eval_instances` | `EvalConditions.subset_size` -- material, because 1,000 of 5,000 items is a different benchmark |
| `adapter_spec.model_deployment` | `ResultClaim.serving_provider` -- **which provider served the model**, a material condition almost nobody else captures |
| `metric_specs[].args.names` | `Metric` refs |
| `scenario_spec.class_name` | `Benchmark.external_ids.helm_scenario` |
| `data_augmenter_spec` | **-> request** an `EvalConditions.perturbations` field (§11). HELM's robustness perturbations change what is being measured and have no home today |
| `runs.json` score rows | `ResultClaim`, but only once the licence is resolved |

These map straight into `comparability_key`.

**The blocker is the licence.** HELM's code is Apache-2.0; the bucket's data carries no licence
statement the recon could find `[U]`. A publicly readable bucket is permission to read, not
automatically permission to redistribute. **Decision: email CRFM (`crfm-help@stanford.edu`) in
Phase 3, week 1, and get an answer in writing before ingesting any scores.** Until then the adapter
may be built and run, and its output lands in `data/_discovery/helm/` under §1.2's veto.
Eval-condition *values* are arguably uncopyrightable facts, but "arguably" is not a foundation for a
trust-based index, and being wrong here would hand every critic a free shot.

**Pitfall of a different kind.** HELM entered maintenance mode on 2026-06-01. That does not make the
data less valuable -- it makes it *more* urgent to capture, and it makes HELM the best case study for
liveness signalling. Poll the release-prefix listing; if no new release appears for two quarters,
that is a fact about the ecosystem worth surfacing, not a scraper bug.

**When it breaks.** A missing release prefix is expected and is data, not an error. A 403 on the
bucket is a hard fail -- the access model changed and the licence conversation just became urgent. A
`run_specs.json` whose `adapter_spec` keys have been renamed is the dangerous case: assert the key
set and fail, rather than writing nulls into `comparability_key`, because a key computed from
silently-missing fields is worse than no key at all.

### 3.6 LMArena / Arena

`lmarena.ai` 301-redirects to `arena.ai` `[M]`. **Do not scrape the site.** The data is published as
a HuggingFace dataset, `lmarena-ai/leaderboard-dataset`, tagged **`license:cc-by-4.0`**, last
modified 2026-09-16, roughly 36k downloads `[M]`, with `full-*.parquet` and `latest-*.parquet` per
arena: `text`, `agent`, `agent_bash_recovery_steps`, `agent_praise_complaint`, `agent_steerability`,
`agent_task_outcome_explicit`, `agent_tool_hallucination`, `document`, `document_style_control`,
`image_edit`, `image_to_video`, `search`, `search_factuality`, `search_style_control` and others
`[M]`.

**Mapping.**

| Arena field | Ours |
| --- | --- |
| arena name (`text`, `agent`, `search`, ...) | one `Leaderboard` each, and one `RatingPool` each |
| `*_style_control` variant | **a separate `Leaderboard` and `RatingPool`**, never a flag on the parent |
| model name | `System` / `SystemVersion` via the alias table |
| Elo / rating, CI | `ResultClaim.value` with `Metric.unbounded: true`, `requires_pool: true`, `headroom_computable: false` |
| snapshot date | `ResultClaim.pool_snapshot` -- mandatory |
| vote counts | `metrics/` only |
| per-battle rows in `full-*.parquet` | **-> drop from the published artifact.** [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §8 caps us at the latest snapshot, top 25 rows per arena, roughly 325 rows and 100 KB. Historic snapshots stay in git and are reachable at a commit hash, which is what data-as-git is for |

**The modelling decision this forces:** the `*_style_control` variants are a *different comparability
class* of the same underlying benchmark and must be modelled as distinct `Leaderboard` entities with
distinct comparability keys, not as one leaderboard with a flag. If we collapse them, we reproduce
exactly the error the project exists to prevent.

Arena ratings are Elo from a shifting pool, which means -- as the domains recon notes for Kaggle Game
Arena too -- a model's rating changes when a different model joins the pool, with no change to the
model. **Rating-pool identity plus snapshot date must be part of any stored Elo result**, and the UI
must refuse to compare Elo across snapshots. `RatingPool` already exists in
[04-data-model.md](04-data-model.md) §2 for exactly this, so this is a modelling constraint the
schema already honours rather than a request.

**When it breaks.** A renamed or removed arena file is a lineage event, not an error: record the
disappearance, keep the last snapshot, and raise a lifecycle review. A parquet schema change (a
renamed rating column) is a hard fail. If the HF repo's licence tag ever changes from `cc-by-4.0`,
`make verify-sources` catches it at the monthly probe and the veto in §1.2 applies from that run
onward -- previously ingested snapshots stay, because they were ingested under the licence then in
force, and the `IngestBatch` records which.

### 3.7 SWE-bench

The leaderboard data is inlined in the page as `<script id="leaderboard-data"
type="application/json">` `[M]`. One regex plus `json.loads`; it is not really a scrape. Verified:
**5 leaderboards, 323 result claims** -- Multilingual 13, Test 24, Verified 180, Lite 84,
Multimodal 22 `[M]`.

**Mapping.**

| SWE-bench field | Ours |
| --- | --- |
| `agent`, `agent_org` | `System` with `built_on` pointing at the base model -- the scaffold axis of `comparability_key` |
| `model_display`, `model_org`, `model_release_date` | `System` / `SystemVersion` |
| `reasoning_effort` | `EvalConditions.reasoning_effort` |
| `instance_calls` | **-> `EvalConditions.max_steps`**, which [04-data-model.md](04-data-model.md) §8 already carries. This is a mapping, not a schema request: an earlier draft asked for a new `max_agent_steps` field without checking, and two names for one concept would have hashed into two different `comparability_key` values depending on which adapter wrote the record -- a silent comparability failure, which is worse than a refusal because it looks like an answer. It is a material condition: an agent allowed 200 calls is not the same system as one allowed 20 |
| `cost`, `instance_cost` | `ResultClaim.cost_usd` plus `Metric.must_report_with` so a score is never shown without its cost |
| `checked` | third-party verification boolean -> the verification ladder in [04-data-model.md](04-data-model.md) §7 |
| `warning` | **-> request** `ResultClaim.caveat` (§11). Dropping a publisher's own caveat while keeping their number is the single most dishonest thing an aggregator can do |
| `os_model`, `os_system` | `System.open_weights` flags |
| `resolved` | `ResultClaim.value` |
| `trajs`, `logs` | `ResultClaim.artifact_url`. `logs` points at `s3://swe-bench-submissions/...`, **which is not anonymously listable** (403 AccessDenied `[M]`) -- link, never fetch |
| `trajs_docent` | **-> drop**, with a note: it is a viewer URL for a third-party tool, and a link to a viewer is not evidence. Revisit if Docent publishes a stable artifact format |
| `logo`, `site`, `folder`, `date`, `tags` | `logo` and `folder` **-> drop**; `site` -> `Source.url`; `date` -> `ResultClaim.claimed_on`; `tags` -> `_suggested` |

**Licence.** No statement found `[U]`. Under §1.2 the adapter may be built and its claims land in
`data/claims/_ingested/swebench/` marked `licence_class: unlicensed`, which the firewall in
[04-data-model.md](04-data-model.md) §9 keeps out of the CC-BY core. The licence question goes on
the §8.4 checklist: the maintainers are reachable and the answer is probably one email.

**When it breaks.** An `id` or attribute rename on the page breaks extraction. Monitoring is cheap:
assert the script tag exists and parses, and that the leaderboard count is 5 or greater; alert
immediately if not. Hash the extracted JSON, not the page, because the page carries rotating logos
and CDN noise that would produce a false change on every run. A row count that drops by more than
10% is a semantic anomaly, not a transport error -- open the PR labelled `needs-scrutiny` rather than
silently deleting claims.

### 3.8 Grand Challenge -- the cheapest route to non-LLM breadth

```
GET https://grand-challenge.org/api/v1/challenges/?limit=2&offset=0
```

Public REST, no auth, DRF pagination, **264 challenges** `[M]`. Fields: `api_url, url, slug, title,
description, public, status (OPEN/CLOSED), logo, submission_types, start_date, end_date,
publications[]` `[M]`.

**Mapping.**

| GC field | Ours |
| --- | --- |
| `slug` | `Benchmark.external_ids.grand_challenge` -- never our id |
| `title` | Candidate name |
| `description` | `_suggested` only. It is the organisers' prose and we write our own |
| `publications[]` | `Source` records with DOIs, **already provenanced** -- one of the few sources where an automated record arrives with its citation attached |
| `status`, `start_date`, `end_date` | `Benchmark.lifecycle` hint plus `BenchmarkVersion` edition dates |
| `submission_types` | `Leaderboard.submission_process` and `Benchmark.data.access` (a container-submission challenge is a held-out-test benchmark by construction) |
| `public` | `Benchmark.data.access` |
| `logo`, `api_url` | **-> drop** |

This single API covers medical imaging, the highest-raw-volume family in the index (the domains
recon puts the realistic ceiling above 700 families for medicine and health). It is the clearest
demonstration that **the non-LLM breadth differentiator is not all manual labour** -- some of it is
one well-chosen API call. Note the counting convention: 264 challenges is not 264 benchmark entries.
Under [04-data-model.md](04-data-model.md) §4, a BraTS-style cluster is one family with editions as
children, so the deduplicated yield is materially smaller (unverified -- the first run is what
settles it).

**Pitfall.** These are small academic servers run by Radboud UMC DIAG. Throttle to roughly one
request every two seconds and never fan out. Being the project that took down the Grand Challenge
API is a reputational injury no licence protects against.

**When it breaks.** A 5xx is a soft failure: back off hard -- harder than for a commercial API,
because a struggling academic server does not need our retries. A DRF pagination-shape change is a
hard fail. A challenge that disappears from the listing is a lifecycle event and must raise a review
rather than deleting our record: challenges close, and a closed challenge is still a benchmark.

### 3.9 Papers with Code -- dead, useful, and legally dangerous

`paperswithcode.com` 301-redirects to `https://huggingface.co/papers/trending` `[M]`. Meta sunset it
on 2025-07-24. The archive lives under the HuggingFace org `pwc-archive`:

| Dataset | Rows `[M]` | Last modified `[M]` | Licence tag `[M]` |
| --- | --- | --- | --- |
| `pwc-archive/papers-with-abstracts` | 576k | 2026-08-17 | `cc-by-sa-4.0` |
| `pwc-archive/links-between-paper-and-code` | 300k | 2025-09-10 | `cc-by-sa-4.0` |
| `pwc-archive/datasets` | 15k | 2025-09-10 | `cc-by-sa-4.0` |
| `pwc-archive/methods` | 8.73k | 2025-09-10 | `cc-by-sa-4.0` |
| **`pwc-archive/evaluation-tables`** | **2.25k** | 2025-09-13 | `cc-by-sa-4.0` |
| `pwc-archive/files` | 338 | 2025-09-14 | `cc-by-sa-4.0` |

At final scale PwC held 9,327 benchmarks and 79,817 paper-code links -- by a wide margin the largest
cold-start corpus available to anyone.

**And it is tagged CC-BY-SA-4.0, which is viral.** If PwC task-taxonomy text or evaluation-table rows
are incorporated into our YAML, a strict reading obliges the derivative to be CC-BY-SA, which
contradicts the CC-BY licensing that is itself one of our four differentiators. This is the single
largest legal risk in the entire ingestion strategy and it must be decided **before first ingest,
not after**.

**Three honesty notes before the decision, because the previous draft overstated its own footing.**

1. **The licence determination rests on HuggingFace repo tags**, and §3.2 of this same document
   states that HF tags are self-declared and are never ground truth. Reading the licence of the
   largest and riskiest corpus in the plan off exactly the signal we declare unreliable is not
   acceptable. **Prerequisite task, on the §8.4 checklist: read the archive's own `LICENSE` file and
   the Meta sunset notice, and record the quoted text in `ingest/sources.yaml`.** Until that is done
   the determination is `[U]`, and the posture below is conservative *because* it is unresolved.
2. **The previous draft's enforcement mechanism cannot work.** It proposed "a CI rule that fails the
   build if a `pwc-archive`-provenanced string appears in `data/` proper". CI cannot detect the
   provenance of a bare string. Implementing it would require shipping an exact-match index of the
   CC-BY-SA corpus -- itself arguably a derivative -- or relying on the discipline this document has
   just said it will not rely on.
3. **The EU sui generis database right** may attach to the PwC name-and-identifier set independently
   of copyright, and it is exactly that set the reconciliation posture proposes to use
   (unverified -- confirm before relying on this). **We take no position on it.** The posture below
   is designed so that the question does not need answering: our use is a matching oracle whose only
   output is identifiers, and we do not reproduce, extract or re-utilise a substantial part of the
   database in any published artifact.

**The decision, stated as a decision.** Papers with Code content **never enters the repository at
all.**

- The dump is downloaded into a **gitignored local cache** (`.cache/pwc/`) on a curator's machine or
  in an Actions job whose workspace is discarded. It is never committed, never published, never part
  of a release.
- The adapter's only output is `data/_crosswalk/pwc.csv`, whose columns are exactly
  `our_id,pwc_id,match_method,match_score`. Nothing else. `match_method` is one of `exact-name`,
  `hf-paperswithcode-id`, `arxiv-id`, `manual`.
- **CI enforces it mechanically:** every field in `data/_crosswalk/*.csv` must match
  `^[A-Za-z0-9._:/-]{1,80}$` or be a float. No spaces, no free text, no field over 80 characters.
  That is a five-line check on a regular file and it cannot be argued with, which is the whole point
  -- unlike the previous draft's rule, it is a property of the artifact rather than of the
  contributor.
- Descriptions, task-taxonomy text and evaluation-table prose are **re-derived from the primary
  paper**, which is where PwC's value never was anyway: name-matching was its strength, and the
  descriptions were not.
- `Benchmark.external_ids.papers_with_code` therefore holds an identifier and nothing else, which is
  precisely what the HF `paperswithcode_id` field already gives us for free from a CC-BY-permissive
  source.

The reason to prefer this over the quarantine tree that [04-data-model.md](04-data-model.md) §9's
licence firewall permits: a quarantine tree is a *policy* that some files must not be copied out of,
and policies leak across years and contributors. A crosswalk of identifiers is a *fact* about the
artifact that CI can assert on every commit. The cost is that we lose PwC's historic SOTA rows,
which were mostly pre-2025 and mostly duplicated by Epoch and EEE for the benchmarks anyone still
cares about. The risk we avoid is a licence change forced by discovery at launch, which is
existential. `vendor/pwc-archive/` stays reserved in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §12's path table as a licence
provision in case a future decision reverses this, but under this decision it is empty.

**When it breaks.** It cannot break -- it is frozen. The failure mode is the opposite one: the
archive being taken down, at which point the crosswalk still works because it holds identifiers we
already resolved. Archive the `pwc-archive` HF pages via SPN2 once, so the licence tag we read is
citable if the determination is ever challenged.

### 3.10 OpenAlex -- re-plan around the meter, and distrust the citations

Measured unauthenticated from a clean IP `[M]`:

```
X-RateLimit-Limit: 1000             # credits/day
X-RateLimit-Limit-USD: 0.1          # $0.10/day budget
X-RateLimit-Cost-USD: 0.0001        # a /works?filter= list call
X-RateLimit-Cost-USD: 0.001         # a *.search: call
X-RateLimit-Reset: 50992            # seconds
```

That is roughly **1,000 list calls or 100 search calls per day** unauthenticated `[M]`. The
documentation disagrees with itself and with reality: the OpenAlex blog says a free key gives $1/day
(10,000 list calls, 1,000 search calls) `[D]`; the docs repo still claims 100,000 credits/day with no
key `[D]`; the live measurement is $0.10/day `[M]`. **Three different numbers -- get a free key and
measure with it before sizing anything** `[U]`. Credit costs per the docs: singleton 1, list 10,
content 100, vector 1,000, text/aboutness 1,000 `[D]`. The polite pool via `?mailto=` is still
honoured `[D]`. The **bulk snapshot remains free and CC0** `[D]`, and that is the correct ingestion
path for us -- never poll an API for data that is published as a monthly dump.

**Mapping.**

| OpenAlex field | Ours |
| --- | --- |
| `institutions[].ror` | `Organization.ror` -- the part OpenAlex is genuinely good at |
| `primary_location.source` | `Source.venue` |
| `open_access.oa_status` | `Source.oa_status` |
| `topics[]`, `concepts[]` | `_suggested` domain hints only, never a facet |
| `cited_by_count` | `metrics/` only, rendered with a visible single-source marker -- **never** a headline influence figure |
| `display_name` | **-> drop.** See the defect below: the title field is demonstrably unreliable and we have better title sources |

**The data-quality finding is more important than the pricing.** Two verified defects `[M]`:

- `GET /works/doi:10.48550/arXiv.2303.08774` returns **404**; the GPT-4 Technical Report is not
  indexed under its arXiv DOI, and a title search maps it to `W4327810158` with an unrelated DOI.
- Record `W4387561453` has the correct SWE-bench DOI, the correct authors and the correct publication
  date, but the **wrong title** ("Persistent memory for AI coding agents: a pre-registered SWE-bench
  Verified benchmark") and a `cited_by_count` of 53, which is off by orders of magnitude.

Right DOI, right authors, wrong title, wrong count. That is exactly the shape of error a catalogue
cannot detect by inspection and exactly how a trust-based index dies. **Conclusion: use OpenAlex for
institution/ROR resolution and topic concepts, where it is genuinely good. Never surface an OpenAlex
citation count as a headline influence number without a second source, and render any
single-aggregator figure with a visible "single source, unverified" marker.**

**When it breaks.** A 429 or a zero remaining budget is a soft failure; the bulk snapshot is the
fallback and the reason we never depend on the API for anything on the critical path. A pricing
change is caught by the monthly `make verify-sources` probe reading `X-RateLimit-Limit-USD`, which is
the concrete reason that job exists.

### 3.11 Semantic Scholar

`GET /paper/arXiv:2310.06770?fields=title,year,citationCount,externalIds,openAccessPdf` returned
**HTTP 429 on the first request** from a clean IP `[M]`. The unauthenticated tier is documented as
1,000 requests per second *shared among all unauthenticated users* `[D]` -- globally contended and
practically dead. With a key the documented introductory limit is **1 RPS on all endpoints** `[D]`;
the key request form is at `https://www.semanticscholar.org/product/api#api-key-form` and arrives by
email (turnaround `[U]`).

**Mapping.**

| S2 field | Ours |
| --- | --- |
| `externalIds.ArXiv`, `.DOI`, `.CorpusId` | `Source.external_ids` -- native `arXiv:` IDs as first-class, so no DOI guessing |
| `citationCount` | `metrics/`, cross-checked against OpenAlex; a disagreement above 2x is recorded, not resolved |
| `title`, `year`, `venue` | `Source` fields |
| `tldr` | **-> drop.** It is a generated summary, and C6's rule that the model never produces a citable field applies to other people's models as well as ours |
| `openAccessPdf` | `Source.pdf_url` (a link; we never fetch or store the PDF) |

What S2 adds over OpenAlex: native arXiv IDs, generally cleaner citation counts, and the S2AG/S2ORC
bulk datasets, which are the sane path at our scale. Licence: an API License Agreement plus ODC-BY
1.0 on the released corpora `[U]` for 2026; attribution required.

**Recommendation: S2 for arXiv-to-paper identity resolution, OpenAlex for institutions and topics,
and cite both.** At 1 RPS a full backfill of 5,000 benchmark papers takes about 90 minutes `[E]`,
which is fine for a batch job and impossible for a per-page-view lookup -- another reason the site is
static and enrichment happens at build time.

**When it breaks.** A 429 with a key is a soft failure: the 1 RPS bucket refilled late; sleep and
continue. A 403 means the key was revoked, which is a hard fail with a human action attached. If the
key never arrives, the fallback is OpenAlex plus Crossref with the citation-count caveat doubled,
and the plan does not block on it.

### 3.12 Crossref, DataCite, Zenodo

- **Crossref**: `https://api.crossref.org/works?query.title=...&mailto=...`. No key; the polite pool
  rewards `mailto`. **`query.title` is a very loose match** -- `query.title=SWE-bench` returned
  23,851 results with top hits "SWE-bench Goes Live!" and "Investigating Test Overfitting on
  SWE-bench" `[M]`. Use Crossref for DOI-to-metadata resolution, **never for discovery**.
  Mapping: `DOI -> Source.doi`; `title`, `author`, `issued`, `container-title` -> `Source` fields;
  `reference[]` **-> drop** (we are not building a citation graph).
- **DataCite**: `https://api.datacite.org/dois?query=...&provider-id=arxiv`. Responds; exact response
  schema `[U]` (the recon's parse failed). arXiv's own bulk-data page names DataCite as an official
  metadata route `[D]`. Mapping is the same shape as Crossref. **When it breaks:** it is a secondary
  path for DOIs we can usually get from Crossref or Zenodo, so a failure is soft and the adapter is
  optional. Do not build it until a real gap appears.
- **Zenodo**: `https://zenodo.org/api/records?q=benchmark&size=1` returns 200 unauthenticated `[M]`,
  with `doi` and -- crucially -- **`conceptdoi`**, the version-independent DOI. Mapping:
  `conceptdoi -> Benchmark.external_ids.zenodo_concept` (identifies the benchmark across editions),
  `doi -> BenchmarkVersion.doi` (identifies one edition), `metadata.version -> BenchmarkVersion.
  label`, `files[] -> drop`. Zenodo is also where we mint our own release DOIs, per
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §10. **When it breaks:** a Zenodo
  outage blocks our own release minting, not our reading, so the response is to delay the release
  rather than to work around it.

### 3.13 NeurIPS Datasets & Benchmarks, and the OpenReview wall

The D&B track is the densest concentration of peer-reviewed benchmarks anywhere: **1,995 submissions
and 497 accepted in 2025** `[M]`, and the track mandates Croissant metadata and persistent public
hosting, so accepted papers arrive with machine-readable dataset descriptors.

**OpenReview's API2 is closed to us.**
`https://api2.openreview.net/notes?venueid=NeurIPS.cc/2025/Datasets_and_Benchmarks_Track` returns
**HTTP 403 `{"name":"ChallengeRequiredError"}`** to anonymous clients `[M]`. Their `robots.txt` only
disallows `/*?*email=` `[M]`, so this is a bot-challenge layer rather than a robots rule -- and
**circumventing an anti-bot measure is a materially different legal and ethical posture from ignoring
a robots line. We do not build a bypass.** Whether an authenticated `openreview-py` session under a
real, identified account clears the challenge is `[U]`.

**The fallback works and is better anyway.** `proceedings.neurips.cc/paper_files/paper/{year}` and
`papers.nips.cc/paper_files/paper/{year}` both return 200 `[M]`: static per-year HTML indices, very
stable, with per-paper JSON and BibTeX siblings. Scrape once a year in December.

**Mapping.** `title`, `authors`, `abstract` -> triage candidate; `bib` -> `Source`; the paper's
linked Croissant record -> `Benchmark.croissant_url`; `full_text` **-> drop**. The output is 497
triage candidates at very high precision, which under §5.4's capacity model is **eight weeks of the
annual triage budget in one December afternoon of ingestion** -- so the annual scrape must feed the
same throttled queue as everything else, not bypass it. The previous draft called it "one afternoon
of LLM-assisted triage"; that was the classifier's afternoon, not the curator's.

**When it breaks.** A changed HTML structure is a hard fail, and it is an annual job so there is a
year to fix it. If the proceedings site moves, the fallback is the NeurIPS accepted-papers page plus
the Croissant records on HuggingFace, both of which we already touch.

### 3.14 Codabench and EvalAI -- catalogue yes, results no, and filtered

- **Codabench**: `https://www.codabench.org/api/competitions/?limit=2` works unauthenticated and
  returns `id, title, created_by, owner_display_name, created_when, first_phase_start, published,
  participants_count, logo, description` `[M]`. The platform holds 1,498 public competitions, 80,406
  users and 722,037 submissions `[M]`. But `/api/competitions/{id}/results/` returns
  `{"detail":"You are not a competition admin or superuser"}` `[M]`.
- **EvalAI**: `https://eval.ai/api/challenges/challenge/all/all/all` works unauthenticated and
  returns **1,053 challenges** `[M]`, DRF-paginated; `/api/challenges/challenge/{id}/challenge_phase`
  gives `leaderboard_public`, `max_submissions_per_day` and dates `[M]`. But
  `/api/jobs/challenge_phase_split/{id}/leaderboard/` returns
  `{"error":"Sorry, the leaderboard is not public!"}` on the challenges tested `[M]`.

**Verdict on results: never attempt the leaderboards.** They are 403 and "not public". Anyone who
plans a sprint around getting numbers out of these endpoints will lose the sprint.

**Verdict on the catalogue: ingest, but filtered, because 2,551 untriaged candidates is the firehose
§1 forbids.** The previous draft said "ingest the competition catalogue as benchmark-discovery
candidates" with no filter, no precision estimate and no triage budget, against a queue that clears
60 items a week. That is 42 weeks of triage from two adapters. The filter, stated so an adapter
author can implement it:

```
accept a competition as a candidate if ANY of:
  participants_count >= 25                      # Codabench only; EvalAI does not expose it
  OR an associated publication or arXiv link is present in `description`
  OR the title/description matches the non-LLM domain vocabulary
     (robotics|protein|climate|weather|catalys|material|medical|imaging|audio|acoustic|
      genom|seismic|remote sensing|molecul|quantum|...)
  OR it is a track of a named series we already carry (NTIRE, FAIR Universe, RealPDE, ...)
```

Expected yield after filtering: **a few hundred, not 2,551** `[E]` -- the estimate is ours, from the
shape of the platforms rather than from a run, and the first run is what settles it (unverified --
confirm before relying on this). Expected precision after filtering is not estimated at all and
should not be guessed; it is measured on the first run and recorded.

**And the placement decision: both sit behind the Tier-1 exit criterion**, so they never compete with
the seed corpus for curator time. They are valuable precisely for the domains we care about -- NTIRE
tracks, FAIR Universe HiggsML and RealPDE all live on Codabench -- but as pointers to a benchmark,
not as sources of numbers, and pointers can wait.

**Mapping.** `id`/`slug` -> `external_ids`; `title` -> candidate name; `description` -> `_suggested`
and the filter input; `participants_count` -> `metrics/` and the filter input; `first_phase_start`,
dates -> `BenchmarkVersion` edition hints; `leaderboard_public` -> `Leaderboard.public`; everything
else **-> drop**. For a candidate that clears no filter: it maps to nothing and produces no record at
all, which is the cheapest possible outcome.

**When it breaks.** A DRF pagination change is a hard fail. A 5xx is soft, with the same hard backoff
as Grand Challenge -- both are small academic servers. If `participants_count` disappears, the filter
degrades to publication-and-domain only and the adapter says so in its run record rather than
silently accepting everything.

### 3.15 Kaggle

`https://www.kaggle.com/api/v1/competitions/list` returns **401 unauthenticated** `[M]`; it requires
`~/.kaggle/kaggle.json`. Rate limits are not publicly documented `[U]` and the ToS restricts bulk
scraping `[D]`. Kaggle has repositioned toward benchmarks -- its own meta description now reads
"evaluating agents, models, and frontier technology through crowdsourced benchmarks" `[M]` -- and it
hosts ARC Prize 2026, the Image Matching Challenge, BirdCLEF+, LifeCLEF tasks and Game Arena, which
is real cross-domain value.

**Placement: second wave, authenticated, conservatively rate-limited, and scoped to competitions we
have already discovered elsewhere.** Not a discovery firehose. The `Cornell-University/arxiv`
metadata dump also lives here and is a legitimate bulk backfill path for arXiv.

**Mapping.** `ref`/`title` -> `external_ids` and candidate name; `evaluationMetric` ->
`_suggested` metric hint; `deadline`, `enabledDate` -> `BenchmarkVersion` edition dates;
`teamCount` -> `metrics/`; `reward` **-> drop** (prize money is not a property of the evaluation);
Croissant export -> `Benchmark.croissant_url`. Game Arena Elo, if ever ingested, inherits the
`RatingPool` rule from §3.6 without exception.

**When it breaks.** A 401 after a working run means the token expired: hard fail with a human action.
An undocumented rate limit means we discover it by being throttled, so the policy is to run Kaggle
last in any workflow and at one request every two seconds, and to treat any 429 as a signal to halve
the rate permanently rather than to retry.

### 3.16 Model release feeds -- the System entity

| Source | Endpoint | Auth | Observed `[M]` |
| --- | --- | --- | --- |
| OpenRouter | `https://openrouter.ai/api/v1/models` | None | 200, **444 models**; `id, canonical_slug, hugging_face_id, name, created, description, context_length, architecture{...}, pricing{prompt, completion}, top_provider{...}, supported_parameters[]`; catches stealth models (`stealth/union-alpha`) |
| LiteLLM | `https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json` | None | 200, **2,591,466 bytes**, ETag present |
| Epoch | `https://epoch.ai/data/notable_ai_models.csv` | None | 200, 2.25 MB, CC-BY-4.0, training compute + org + country + accessibility |
| HuggingFace | `/api/models?sort=createdAt&direction=-1` | None | Returns models created minutes ago |
| OpenAI | `https://openai.com/news/rss.xml` | None | 200 `text/xml`, most recent item 2026-09-16 |
| Anthropic | -- | -- | **No RSS.** `anthropic.com/rss.xml` and `/news/rss.xml` both 404; release notes are HTML only |
| Google | `https://blog.google/rss/` | None | 200 `application/xml`; a firehose that needs filtering |
| Artificial Analysis | `https://artificialanalysis.ai/api/v2` | `x-api-key` | 401 unauthenticated; free tier 100 req/24h `[D]`; **attribution required at all tiers, redistribution requires a contract** `[D]` |

**Mapping.**

| Field | Ours |
| --- | --- |
| OpenRouter `id`, `canonical_slug` | `SystemVersion.id` candidate and `external_ids.openrouter` |
| OpenRouter `hugging_face_id` | `System.external_ids.huggingface` -- the free join key across OpenRouter and HF |
| OpenRouter `created` | `SystemVersion.released_on` (an availability date, not a release date -- record which) |
| OpenRouter `context_length`, `architecture.*` | `SystemVersion` capability fields |
| OpenRouter `pricing.*`, LiteLLM prices | `metrics/` only. Prices change without a model changing, and a price in the citable core would be wrong within a month |
| OpenRouter `supported_parameters[]` | **-> request** `SystemVersion.supported_parameters` (§11). It is how we know whether `temperature` was even settable for a given claim, which is a comparability input, not decoration |
| OpenRouter `top_provider.is_moderated` | **-> drop** for v1; revisit if a claim ever turns on it |
| Epoch `training_compute_flop` | `System.training_compute_flop` + `estimated` flag |
| RSS `title`, `link`, `pubDate` | Triage candidate for a `System`, human-confirmed |

**Recommendation:** build the `System` entity from **OpenRouter + Epoch `notable_ai_models.csv` + HF
models** -- all no-auth, all redistributable, with `hugging_face_id` as the join key. Use Artificial
Analysis **only as a link-out**; 100 requests a day plus an explicit "contact us for redistribution"
clause makes it legally awkward for a CC-BY index, and their numbers are a product, not a commons.
Vendor blogs get a weekly LLM-assisted digest with a human confirming each entry; RSS exists only for
OpenAI and Google, so Anthropic releases are manual (unverified whether an RSS feed exists at another
path -- confirm before relying on this).

Remember constraint 5: **this is not a model directory.** Systems exist only as the subjects of
result claims. The purpose of these feeds is to resolve "which model is this row about", not to build
a catalogue of models. If the `System` tree starts growing fields nobody's result claim needs, the
adapter has overreached.

**When it breaks.** An RSS 404 is soft and expected -- feeds move. OpenRouter returning a
significantly shorter model list is a semantic anomaly: alert, do not delete. The LiteLLM file is
2.59 MB and conditional on ETag, so the failure mode is a silent ETag change with no content change,
which costs a download and nothing else.

### 3.17 Small static leaderboards

Cheap adapters, roughly 30 lines each, worth building once the framework exists. Each maps
`model name -> System`, `score -> ResultClaim.value`, `date -> ResultClaim.claimed_on`, and whatever
condition columns exist into `EvalConditions`; everything presentational is dropped.

- **EvalPlus**: `https://evalplus.github.io/results.json` -- 200, 34,305 bytes, static JSON `[M]`.
  *When it breaks:* a 404 is a hard fail; the repo `evalplus/evalplus` is the fallback handle.
- **LiveBench**: `https://livebench.ai/table_2025_11_25.csv` -- 200, 9,893 bytes `[M]`. The site is an
  SPA and the *current* dated filename could not be extracted from it `[U]`; use the
  `LiveBench/LiveBench` GitHub repo as the handle instead of guessing filenames. *When it breaks:*
  this is the archetype of the source most likely to rot invisibly -- see §7's soft-404 rule.
- **OGB**: `ogb.stanford.edu/docs/leader_nodeprop/` -- HTML tables, stable structure, low churn, and
  the cheapest coverage of graph learning. *When it breaks:* an HTML structure change is a hard fail;
  there is no API fallback, so it degrades to a manual sweep item.
- **MTEB**: covered under GitHub above; CC0 and cloned rather than scraped.
- **Matbench Discovery**: has `/api`, `/data/sets`, a GitHub repo and RSS `[D]`, which makes it the
  one materials-domain source that is genuinely automatable (terms `[U]`). Treat it as a Tier-2
  adapter rather than a manual sweep target. *When it breaks:* fall back to the sweep entry, which
  exists anyway.

### 3.18 Wayback SavePageNow and CDX -- the archival transport

Policy is §7; the transport is here.

```
POST https://web.archive.org/save
Authorization: LOW <accesskey>:<secret>          # keys from archive.org/account/s3.php
  url=<target>&if_not_archived_within=30d&skip_first_archive=1&capture_screenshot=0
-> {"url":"...","job_id":"..."}

GET https://web.archive.org/save/status/{job_id}
GET https://web.archive.org/save/status/user     -> {"available":12,"processing":3}   [M: 401 without auth]
```

`if_not_archived_within` is the idempotency key -- it makes re-running the archiver harmless, which
matters because a dropped GitHub Actions cron run must never produce duplicate captures.

**Do not use the Availability API.** `https://archive.org/wayback/available?url=...` returned **429**
on a single cold request `[M]`. Use CDX instead, which is cheap, reliable and returns a content
digest:

```
GET https://web.archive.org/cdx/search/cdx?url=epoch.ai/data/ai-benchmarking-dashboard&output=json&limit=3
-> [["urlkey","timestamp","original","mimetype","statuscode","digest","length"], [...]]   [M]
```

The `digest` field tells us whether the content actually changed between captures, which is exactly
what the link-rot re-check needs.

Documented limits: authenticated 12 concurrent and 100,000 per day; anonymous 6 concurrent and 4,000
per day; the same URL at most 10 times per day `[U]` -- sourced from IA's public spec doc, not re-read
live.

**Mapping.** `job_id` -> `Source.archive_job_id` while pending; the resulting Wayback URL ->
`Source.archive_url`; capture timestamp -> `Source.archive_captured`; CDX `digest` ->
`Source.archive_digest`, which is what a later re-check compares against.

**When it breaks.** SPN2 refuses some URLs -- paywalls, robots-blocked hosts, JavaScript-only pages
that capture blank. A failed capture is recorded as `archive_status: failed` with the reason, not
retried forever and not silently dropped: an un-archivable source is a fact about that source's
reliability and should lower its verification level. A 429 on `/save` means the concurrency budget is
spent; the archiver is a cursor-driven rolling job (§7) precisely so that this is a pause rather than
a failure.

**Perma.cc is dropped from the plan.** Its free tier is 10 links per month and it requires an
institutional account `[D]` -- a single documentation read, which is thin evidence for a decision, so
re-check it before ever reversing this. SPN2 plus CDX discharges the archival mandate at our volume.

### 3.19 Every Eval Ever -- the most important relationship in the landscape

The previous draft gave this a table row and one line in the second wave. That badly undersold it.
Every Eval Ever (the EvalEval Coalition: HuggingFace, University of Edinburgh and EleutherAI, arXiv
2606.14516, 48 authors) is **data CC BY 4.0 and code MIT** `[D]`, holds 22,235 models, 2,273 unique
benchmarks and 31 evaluation formats `[M]`, and -- critically -- **models results, not benchmarks.**
Its schema has no benchmark-level catalogue: no domain taxonomy, no modality, no dataset licence, no
maintenance status, no cross-domain vocabulary. It is not a competitor. It is the complement, and it
is the single best alliance target available.

**Endpoints.**

```
GET https://huggingface.co/api/datasets/evaleval/EEE_datastore?full=true
git clone --depth 1 https://github.com/evaleval/every_eval_ever      # schema + validate CLI
```

**The four shared field names, adopted rather than invented.**
[04-data-model.md](04-data-model.md) §8 owns the full crosswalk table and this document does not
restate it; the four the brief names are:

| EEE (`eval.schema.json`) | Ours |
| --- | --- |
| `generation_config.generation_args.{temperature,top_p,max_tokens}` | `EvalConditions.sampling.*`, `max_output_tokens` |
| `agentic_eval_config.available_tools[]` | `EvalConditions.tools_allowed` |
| `sandbox` (type + Docker compose) | `EvalConditions.sandbox` (type only; the compose file is an `artifact_url`) |
| `metric_config.{lower_is_better,min_score,max_score,score_type}` | `Metric.{optimum,range,value_type}` |

**Field-name adoption moves out of the second wave and into the schema work before first ingest.**
Retrofitting condition field names across `data/claims/_ingested/epoch/` is the same retrofit pain
§3.1 already warns about, and it costs nothing to do first. This is a Phase-0 task, not a Phase-5
one.

**The join key, decided.** For an EEE-validated result to point at our benchmark record, one of us
must publish a stable identifier the other can carry. **Decision: we publish our benchmark slug,
resolvable as a permanent URL at `https://<project-domain>/b/<slug>`, and we ask EEE to carry it as
`uaibi_id`; we carry theirs as `Benchmark.external_ids.every_eval_ever` mapped to their
`evaluation_name`.** The reasons: a slug is human-readable, is stable under
[04-data-model.md](04-data-model.md) §3's never-reuse rule, and resolves without a resolver service
or a registration fee. A per-benchmark DOI would be better for formal citation, but minting 1,500 of
them costs money and governance we do not have in v1, and the release DOI already makes the whole
corpus citable at a commit. The risk: slugs are ours to rename when we get one wrong, and the
never-reuse rule turns a rename into an alias, so downstream consumers must follow aliases. We
mitigate that by publishing `aliases.json` in the build artifact for exactly this purpose, and by
treating a slug rename as a breaking change announced in the release notes.

**The alliance action, with a date.** *Phase 0, week 4: open an issue on
`github.com/evaleval/every_eval_ever` proposing the registry split in one paragraph -- they own the
result record, we own the benchmark entity, joined on `uaibi_id` -- with a link to our published
taxonomy and a concrete offer to carry `evaluation_name` on our side first, unilaterally, so the
proposal costs them nothing to evaluate.* Going first is the point: a registry that already carries
their identifier is a different conversation from a registry that wants theirs.

**Mapping.** `evaluation_name -> Benchmark.external_ids.every_eval_ever`; `model_id -> System` via
the alias table; `evaluation_results[] -> ResultClaim` cross-reference (we link to their record
rather than copying it, because they maintain it better than we would); `source_metadata.* ->
ResultClaim.source` plus `reported_by`; `detailed_evaluation_results` (instance-level JSONL)
**-> drop**, because instance-level outputs are benchmark content and constraint 1 forbids us
hosting it.

**When it breaks.** A schema version bump on their side is the expected failure and it is a *good*
one: pin `eval.schema.json` by commit, diff on bump, and treat a field rename as a joint decision
rather than a unilateral fix. The relationship is the asset; the adapter is incidental.

### 3.20 Community submission -- the highest-precision source in the catalogue

Humans are a source, and the previous draft left them out of the source catalogue entirely -- an odd
omission in a document that concedes there is *"no automated answer"* for benchmarks announced in a
blog post on a custom domain. HealthBench, GDPval and the ARC Prize leaderboards are all in that
class. That class is filled by people, not scrapers, and it includes the highest-value people of
all: the benchmark's own authors.

**The transport** is the issue form in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §6 Path A, modelled on UK AISI's
`inspect_evals` `/register/` (launched 2026-05-08 `[D]`): a GitHub issue template, a validation bot
that derives the record and opens the PR itself, and a human review before merge. That document owns
the form fields, the bot behaviour and the review matrix. What this document owns is that the form is
a **source** with a place in the triage queue and a licence posture.

**What the bot validates before opening a PR**, stated here because it is a sourcing constraint:

- every submitted URL resolves (a 2xx or a 3xx chain ending in 2xx) and is archived via SPN2 in the
  same run, so a community-submitted link is provenanced at the moment it arrives;
- no dataset file is attached or linked as an upload -- constraint 1 is enforced at the door, not at
  review;
- a licence field is present, even if the value is `unknown`, because `unknown` is a fact and a blank
  is a gap;
- the domain and capability values are in the controlled vocabulary, which the form's dropdowns are
  generated from.

**The licence posture, and it is a requirement, not a nicety.** The form carries a required checkbox:
*"I license this contribution under CC-BY-4.0."* The bot refuses to open a PR without it. Without
that grant, community submissions are the second licence trap after Papers with Code -- a CC-BY
corpus containing contributions nobody granted CC-BY on is not a CC-BY corpus, and the problem is
discovered at exactly the wrong moment, when someone tries to fork it. This is an inbound request to
[05-repository-and-workflow.md](05-repository-and-workflow.md) §6, whose current `new-benchmark.yml`
field list has the sourcing and no-hosting checkboxes but not this one (§11).

**Where it enters.** The same triage queue as an arXiv candidate, at the front of it. A submission
from an identified human who bothered to fill a form is higher-prior than a classifier score, and a
submission from a recognised maintainer of the benchmark is higher still -- the bot sets
`maintainer-confirmed` pending review in that case. But it is still triage, it still consumes the
capacity in §5.4, and it is still never auto-merged.

**When it breaks.** The failure mode here is not technical, it is social: **nobody submits.** That is
the documented death of `JonathanChavezTamales/llm-leaderboard`, which had 356 stars and converted
itself into a closed website because PR friction beat it. The observable is submissions per month,
published on the `/sources` page alongside adapter health, and the response to a flat line is to
shorten the form rather than to blame contributors. A contributor who bounces off the form is a data
point about the form.

### 3.21 Join keys and their coverage

The join keys are the spine of the whole sourcing strategy and the previous draft mentioned each one
once, in passing, in seven different sections. A reader could not answer "how do I know the HF
dataset, the GitHub repo, the arXiv paper and the Epoch row are the same benchmark?" -- and that
question is the difference between a catalogue and a pile. [04-data-model.md](04-data-model.md) §5
owns the `external_ids` block; this table is the sourcing view of it.

| Key | Carried by | Identifies | Coverage | Failure mode |
| --- | --- | --- | --- | --- |
| `arxiv_id` | arXiv, HF dataset tag `arxiv:*`, S2 `externalIds`, NeurIPS proceedings | Paper | High for 2023+ benchmarks; unmeasured overall `[U]` | Blog-announced and pre-arXiv benchmarks have none. A paper is not a benchmark: one paper can release three |
| `doi` | Crossref, DataCite, Zenodo, arXiv (`10.48550/arXiv.*`) | Paper or release | Near-total for peer-reviewed work | OpenAlex 404s on arXiv DOIs `[M]` -- the DOI resolves at the registrar and fails at the aggregator |
| `conceptdoi` | Zenodo only | Benchmark across editions | Only Zenodo-hosted benchmarks; a small minority `[E]` | Most benchmarks are not on Zenodo at all, so this is a bonus, never a spine |
| `huggingface` (`owner/name`) | HF, and most benchmark homepages | Dataset | 47 `benchmark:official`, 48 `benchmark:eval-yaml`, 203 croissant `[M]` | A benchmark can have many HF mirrors and forks; the canonical one is a human call |
| `hugging_face_id` | OpenRouter | **Model**, not benchmark | 444 models `[M]` | Provider-specific variants share a base-model id |
| `paperswithcode_id` | HF dataset detail, PwC archive | Benchmark or dataset | Present on HF datasets; proportion unmeasured `[U]` | Frozen at ~Sept 2025 -- nothing newer has one, and never will |
| `inspect_evals_id` | `UKGovernmentBEIS/inspect_evals` | Eval *implementation* | 171 evals `[M]` | An implementation is not a benchmark: one eval may cover a subset, and two evals may implement one benchmark differently |
| Epoch `benchmark` string | Epoch `benchmark_metadata.csv` | Benchmark **and** version, conflated | 81 `[M]` | `FrontierMath-Tier-4-2025-07-01-Private` is one string encoding benchmark, tier, snapshot date and access mode. Slugification produces wrong ids |
| Epoch `Model version` | Epoch per-benchmark CSVs | Model **and** provider **and** effort, conflated | 927 of 927 join internally `[M]`; 0% join externally without work | **927** version strings need a hand-maintained crosswalk -- not the 1,048 distinct strings in `model_metadata.csv`, 121 of which never appear in a result row (`00` §8.1 owns the distinction). The largest manual cost in the ingest |
| `every_eval_ever` (`evaluation_name`) | EEE datastore | Benchmark as named in a result | 2,273 names `[M]` | They are free-text names, not identifiers. §3.19's proposal exists to fix exactly this |
| `benchmark_radar` | Benchmark Radar | Benchmark | ~1,283 curated records | Cross-reference only; their content is CC BY-NC-SA and is never ingested |
| `helm_scenario` | HELM `run_specs.json` | Scenario class | 2,546 specs across 26 suites `[M]` | A scenario is narrower than a benchmark; several scenarios can belong to one |
| GitHub `owner/repo` | GitHub, HF `cardData`, homepages | Implementation repo | High | Forks are a lineage relation, not an identity: SWE-bench has six, and each is a different benchmark |
| Grand Challenge `slug` | Grand Challenge API | Challenge | 264 `[M]` | **No shared key with arXiv, GitHub or HF.** `publications[]` DOIs are the only bridge, and they are present on some challenges, not all |
| Domain hubs (CASP, DCASE, LifeCLEF, Matbench, OpenCatalyst, WeatherBench) | Nothing | -- | **Zero** | **No key of any kind exists.** Matching is entirely human, entirely by name and paper, and this is a standing curation cost that feeds directly into §5.4 |

**The honest summary.** Inside the LLM half of the map, identity resolution is a crosswalk-authoring
problem with good keys and a known cost. Outside it -- robotics, protein, climate, materials, audio
challenges, medical imaging -- **there is no join key at all**, and the only mechanism is a human
reading two pages and deciding they are the same thing. That is not a defect in the plan; it is the
differentiator, stated as a cost. Nobody else does it because there is no API for it.

The resolution procedure itself -- exact key match, then alias table, then fuzzy candidate
generation, then human adjudication -- is owned by
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §5, with the alias schema in
[04-data-model.md](04-data-model.md) §10. The rule that survives across both: **adapters never create
entities.** An unresolved candidate stays unresolved and visible, and a bad merge is far more
expensive than an unmerged pair.

---

## 4. Sources we will not build

Recording these with reasons is as valuable as recording the ones we will, because otherwise someone
re-discovers each of them in six months and spends a week finding out what the recon already found
out in an afternoon.

| Source | Why not |
| --- | --- |
| OpenReview anonymous API | Returns an active bot challenge `[M]`. Building a bypass is a materially different legal posture from ignoring robots.txt. Use proceedings HTML |
| Codabench / EvalAI leaderboard endpoints | 403 and "not public" `[M]`. Guaranteed wasted sprint |
| DrivenData leaderboards | `robots.txt` expressly disallows `/*/leaderboard_partial` and `/competitions/search/` `[M]`. Legal and ethical exposure with near-zero payoff. Manual only |
| GitHub `/stargazers` star history | 50 authenticated requests per popular repo for a series we can accumulate ourselves at one request per week |
| `s3://swe-bench-submissions` | 403 AccessDenied anonymously `[M]`. Link, never probe |
| Artificial Analysis as ingested data | 100 req/day and redistribution requires a contract `[D]`. Link out |
| arXiv S3 full-text buckets | Requester-pays, and we are metadata-only by charter |
| Perma.cc | 10 links/month free tier `[D]` |
| Epoch's ECI / EDI scores | Someone else's single-number ranking. Constraint 3 forbids ours; ingesting theirs is the same error with a citation |
| PwC content of any kind in the repo | See §3.9. Identifiers only, in `data/_crosswalk/pwc.csv`, CI-enforced |
| EEE `detailed_evaluation_results` | Instance-level outputs are benchmark content. Constraint 1 |
| Benchmark Radar content | CC BY-NC-SA 4.0 is incompatible with our CC-BY core. A `benchmark_radar` cross-reference field is fine; ingesting their records is not |
| BenchmarkList | No stated licence, no API, no bulk export. Scraping a competitor's proprietary database is legally and reputationally wrong for a project whose entire pitch is provenance |

### 4.1 Language coverage, and the bias this catalogue would otherwise publish as a finding

Every source in §2 is English-language or English-indexed. arXiv `cs.*`, GitHub topics, HuggingFace
Hub, HELM, Epoch, Grand Challenge, Codabench, OpenAlex -- all of them. Nothing in the catalogue
discovers a benchmark that was announced in Chinese, Japanese, Korean, Russian or Arabic and never
mirrored into an English surface.

**This is not a small omission for this project specifically, and the reason is differentiator 3.**
We publish a coverage and gap matrix, and the empty cells are advertised as the most valuable output
we have. An empty cell computed over an English-only corpus is not a statement about the field; it
is a statement about our sourcing, wearing the field's clothes. That is the single most damaging
form the "curation gap read as field gap" failure can take, because it is invisible to us and
obvious to the first reader who works in the language we did not search.

The bias is measurable rather than hypothetical. §3.2's own tag census found
`language:english` on 51 of the sampled Spaces against `polish` 6, `japanese` 4 and `korean` 4
`[M]` -- a surface that is itself English-weighted, sampled by an English-language query. That is
evidence of the shape of the bias, not its size, and nothing in the plan currently measures the
size.

**Three decisions, each with its reason.**

1. **OpenCompass / CompassHub enters the source catalogue as a Tier-3 manual sweep, not a Tier-1
   adapter, and not the "will not build" table.** It is the largest non-English-origin benchmark hub
   in the landscape and it publishes a hub of evaluation sets with an open-source harness, so
   excluding it would be indefensible; but its licence posture is unresolved `[U]`, its interface is
   not stable enough to justify adapter engineering before the seed is written, and Tier-3 is
   precisely the tier for "real, valuable, and cheaper to read twice a year than to automate"
   (§8.3). It joins the sweep checklist in §6 with a semi-annual cadence. Its licence resolution
   goes on §8.4's checklist.
2. **The gap matrix carries a language caveat until it is countered.** Every published coverage or
   gap figure states that the corpus is English-sourced and names this section. This is cheap, it is
   honest, and it is the same mechanism [10-visualization.md](10-visualization.md) already uses to
   stop a curation gap being read as a field gap. It is not a fix; it is the disclosure that has to
   exist while the fix is unbuilt.
3. **The trigger for doing something about it is a reviewer, not an adapter.** The cheapest real
   counter to an English-only corpus is one domain reviewer who reads Chinese, because a reviewer
   finds the benchmarks *and* tells us which of our existing entries mis-describe them. The trigger:
   **when the catalogue passes 500 entries, or when a sweep of OpenCompass surfaces more than
   twenty families we do not hold, recruit one Chinese-reading reviewer** on the same terms as every
   other domain reviewer ([03-taxonomy-build-process.md](03-taxonomy-build-process.md) §12). Sizing:
   one reviewer plus one sweep slot. An adapter comes after that, if at all, and only once someone
   who reads the source can tell us whether the adapter is reading it correctly.

**What we are deliberately not doing, and why.** We are not machine-translating benchmark
descriptions into English and cataloguing the result. A translated description is an unsourced
paraphrase of a primary source, and this project's whole position is that an unsourced confident
statement destroys trust faster than an absence does. An entry whose description nobody on the team
can read against its source cannot be verified by us, so it would have to carry a verification
status that says exactly that -- at which point the honest version is to leave the cell empty and
say why, which is what decision 2 does.

*The corpus-wide position statement on non-English and non-Western sourcing, including what it
implies outside this document, is an open question in [15-open-questions.md](15-open-questions.md);
what appears above is this document's sourcing decision, which is the part that is ours to make.*

---

## 5. Discovery heuristics, and an honest account of their precision

Discovery is the part of the pipeline where being wrong is cheap, so it is the part we automate
hardest. It is also the part most likely to be oversold, so here are the measured numbers with their
sample sizes attached.

### 5.1 What was actually measured

**arXiv keyword filters, measured over 2026-09-10 to 2026-09-17 across `cs.CL`, `cs.LG`, `cs.CV` and
`cs.AI`** `[M]`:

| Filter | Papers in 7 days |
| --- | --- |
| No filter | 2,315 |
| `abs:"benchmark"` | 670 (about 29% of all papers -- useless alone) |
| `ti:"benchmark"` | 103 |
| `ti:"benchmark" OR ti:"bench" OR ti:"eval"` | 114 |
| `cs.CL` alone, no filter | 509 |

All-time `cat:cs.CL AND abs:"benchmark"` is 28,905 `[M]`.

**Regex triage, hand-checked.** Running

```
\b(we (introduce|present|propose|release|construct|curate)|this paper introduces)\b
  .{0,120}?\b(benchmark|dataset|suite|testbed|eval)\b
```

over the 40 most recent `cs.CL AND abs:"benchmark"` titles flagged 13; on manual reading about 8 were
genuine new-benchmark releases `[M]`.

**Precision is approximately 60% (n=40, 13 flagged, 8 confirmed).** That is a small sample: the 95%
confidence interval on a proportion of 8/13 is roughly plus or minus 25 points, so the honest
statement is "somewhere between about 35% and 85%, best estimate 60%". Treat it as an order of
magnitude, not a number.

**Recall is unmeasured, and the previous draft's "roughly 70%" was wrong in kind, not just in
value.** At least 3 genuine benchmarks in the sample were missed (`ScienceIDE`, `TeleAntiFraud 2.0`,
`Behavior2Value`) `[M]`. Three misses noticed by eye is a *lower bound on misses*, not a denominator:
computing 8/(8+3) = 73% assumes every miss was found, which a hand-scan cannot establish. The correct
statement is: **at least 3 of the sample's positives were missed; true recall is unmeasured because
the positive set was never enumerated** (unverified -- confirm before relying on this).

The characteristic false positives are method papers that merely *evaluate on* benchmarks ("Dual-View
Relational Learning for Efficient Agent Benchmarking") and meta-analyses ("Fallacy Benchmarks Measure
Scheme Recognition, Not Fallacy Detection") `[M]`. The characteristic false negatives are `*Bench`
neologisms -- `ReFigBench`, `TeochewBench` -- because arXiv's tokenizer does not split camel-case or
compound tokens `[M]`. Any title regex must therefore include a camel-case-aware `Bench` suffix
pattern, and even then will miss names like `CritPt` and `GDPval` that carry no marker at all.

### 5.2 The LLM triage classifier, specified

An LLM triage pass over abstracts is mandatory, with a strict rubric whose single question is *"does
this paper release an evaluation artifact, or merely use one?"* The previous draft asserted 85-90%
precision after the classifier without having run one. **That target is now a target, not a result.**

**Target: precision >= 85%, measured on a hand-labelled set of 200 abstracts before the classifier is
trusted.** Labelling 200 abstracts is about two hours of work and it converts a guess into a number;
it is a Phase-0 task and a Tier-1 exit criterion (§8.1). Until it is measured, the classifier's
output is treated as a ranking signal only, and the queue is cleared in score order by a human who
reads the title regardless.

**Model and cost**, with the arithmetic shown because constraint 7 says near-zero operating cost:

| Item | Value |
| --- | --- |
| Model | `claude-haiku-4-5` -- classification-shaped, constrained output, no thinking. [11-ai-features.md](11-ai-features.md) §"Model selection and cost" owns model selection and the rate card |
| Prompt | Rubric and enum schema ~1,500 tokens, title and abstract ~600 tokens, output ~120 tokens `[E]` |
| Caching | **None.** Haiku 4.5's cache minimum is 4,096 tokens and the rubric is well under it, so a cache write would never hit. Say so in the adapter, or someone will add caching and wonder why the bill does not move |
| Batching | **Yes.** Triage is not latency-sensitive; the Batch API is 50% off both directions with a 24-hour expiry, which is far inside a daily cron |
| Volume | 15-95 calls/day for the four large CS categories `[M]`, rising to ~150/day if the cross-domain categories are added `[E]` |
| **Cost** | **$0.60 to $6 a month batched**, $1.20 to $13 sync `[E]` -- derived from 2,100 input plus 120 output tokens per call at the published Haiku 4.5 rate. It is the only recurring monetary cost in the entire ingestion stack |
| Where it runs | GitHub Actions, provider key in a repo secret. Not a Worker: Cloudflare Workers Free gives 10 ms CPU per cron trigger `[D]`, which does not parse a response, let alone a corpus |

**Two rules, and the first is C6 applied to ingestion, stated verbatim because it is the governing
rule of the whole AI layer:**

> **The AI layer is a lens, never a source.** Nothing the model emits is ever stored in `data/`, and
> nothing it emits is citable.

Concretely: **the classifier writes only `triage.label` and `triage.rationale` on a candidate in
`data/_discovery/`, and never a schema field.** It does not assign a domain, it does not assign a
capability, it does not write a description. Those are interpretive fields and §1's table says who
writes them.

**Rule two: a monthly false-negative audit, because false negatives are invisible.** A rejected paper
produces no artifact, raises no flag and is never seen again, so recall decays silently and nobody
ever finds out. Once a month, re-run the previous week's rejects at a lower threshold and hand-check
30 of them. The cost is half an hour and about $0.05; the alternative is discovering in year two that
a prompt edit quietly halved recall. Record the result in `evals/triage/<date>.json` and publish the
series, for the same reason we publish adapter health.

### 5.3 Other discovery surfaces, ranked by yield per unit of effort

1. **HuggingFace tag search** -- `?filter=benchmark:official` (47), `benchmark:eval-yaml` (48),
   `?filter=leaderboard` on Spaces (1,019), plus the curated collection
   `clefourrier/leaderboards-and-benchmarks-64f99d2e11e92ca5568a7cce` (79 items, last updated
   2026-03-02) `[M]`. Very high precision, low recall. Best used as a seed and as a cross-check on
   whether our catalogue is missing something obvious.
2. **NeurIPS D&B proceedings** -- 497 accepted papers a year `[M]`, already filtered by peer review
   for being benchmark or dataset releases. The highest-precision discovery source in existence for
   this project, and it costs one annual scrape -- but see §3.13: 497 candidates is eight weeks of
   triage capacity, so it feeds the throttled queue like everything else.
3. **HuggingFace download thresholds** -- a dataset carrying a `task_categories:` value and above,
   say, 10k monthly downloads is either a benchmark or a training set, and the distinction is a
   one-line human call. The cheapest way to find widely-used benchmarks nobody wrote a paper about.
4. **GitHub topic search** -- `topic:benchmark topic:llm sort:stars` returned **2,233 repos** `[M]`,
   led by `open-compass/opencompass` (7,449 stars), `xlang-ai/OSWorld` (3,148) and
   `beir-cellar/beir` (2,294). Vary the second topic across the domain vocabulary (`robotics`,
   `chemistry`, `medical-imaging`, `climate`, `theorem-proving`) to reach the families nobody else
   indexes. Precision is moderate; star count is a usable triage sort.
5. **Conference challenge pages** -- CVPR/ICCV/ECCV workshops emit 50-100 challenge tracks a year
   (NTIRE alone is about 20), MICCAI adds an estimated 40-60 challenges a year, DCASE re-issues 7
   tasks annually `[D, domains recon estimates]`. Not scrapeable in any general way; they belong in
   the manual sweep.
6. **Codabench and EvalAI competition catalogues** -- filtered per §3.14, behind the Tier-1 exit
   criterion, then re-pulled quarterly on the delta.
7. **Community submission** -- §3.20. Lowest volume, highest precision, and the only surface that
   reaches blog-announced benchmarks on custom domains.

**The gap nobody's heuristics close:** benchmarks announced in a blog post, living on a custom
domain, never touching arXiv, GitHub topics or HuggingFace. HealthBench, GDPval and the ARC Prize
leaderboards are all in this class. There are exactly two answers, and both are human: the manual
sweep in §6, and the submission form in §3.20.

### 5.4 Intake capacity, and what we drop

This is the section the previous draft did not have, and its absence was the single largest error in
the document. It costed discovery at "under two hours of weekly curation overhead" and sweeps at
12-20 person-days a year while omitting the only cost that matters -- turning a triage decision into
an entry. At the plan's own rate of 30-90 minutes per fully sourced entry
([14-roadmap.md](14-roadmap.md) §"Effort sizing" owns that rate and records that it has never been
measured), a hundred candidates a week at even a 15% true-positive rate is fifteen entries a week
and **7.5 to 22.5 hours** -- between four and eleven times the stated overhead -- in perpetuity, on
top of sweeps and engineering. The range is carried rather than collapsed on purpose: the earlier
draft of this passage wrote "eleven hours", which is the silent 45-minute midpoint that
[14-roadmap.md](14-roadmap.md) names as the previous plan's signature arithmetic error, and a
document cannot both diagnose that habit and practise it. That is the
curation treadmill that killed every predecessor, and the previous draft walked past it while
quoting the mortality analysis approvingly.

**So: discovery cadence is throttled to curation capacity, not run at maximum yield.** The numbers
below are this document's to own; the seed-phase effort figures belong to
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §11 and
[14-roadmap.md](14-roadmap.md) and are not restated here.

**(a) The steady-state weekly budget. This table is the single owner of the steady-state allocation
of the 20 h/week curator figure**, and every other document that needs to talk about where curator
time goes links here rather than writing its own decomposition.
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §11.2 breaks out the
ingestion-attributable subset *as rows of this table*, not as a rival allocation of the same twenty
hours. The failure mode being closed: an earlier revision had two complete, mutually exclusive
20-hour budgets in two documents, sharing no line item and agreeing on no figure, each summing
correctly to 20 — and **three plausible budgets are indistinguishable from no budget**, because the
first reader to add two of them together publishes the difference as a bug report against the plan's
arithmetic.

Post-seed, at a 20 h/week curator figure and the 50-working-week year (§6):

| Line | Hours/week | Note |
| --- | --- | --- |
| Triage and intake | **6** | Detailed in (b) and (c) below; includes assigning facets to ingested stubs, which has no machine share |
| Manual domain sweeps | **2.5-3.4** | §6's 126-169 h/year, amortised over 50 weeks |
| Re-verification queue | 4 | [05-repository-and-workflow.md](05-repository-and-workflow.md) §7 owns the prioritisation |
| Claims and conditions (the differentiator) | 4 | Where hand-curation has no substitute |
| Review, disputes, correspondence | 3 | Including community submissions and ingest-PR review |
| Identity resolution on ingested records | **2-4** | Aliases, ambiguous systems, mapping stanzas. Derived in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §11.2; the Epoch system crosswalk alone is 927 version strings |
| Adapter maintenance and schema-drift repair | **0.7-2** | 18-25 live adapters, one breakage each per quarter at 30-60 min. Lumpy: near zero for months, then a day when a page changes |
| **Total** | **22.2-26.4** | **It does not fit, and the earlier version of this table only fitted because it was missing the last two rows** |

**The overflow is the finding, so state it rather than rounding it away.** Steady-state curation as
specified needs between 22 and 26 hours a week against a 20-hour budget: between 11% and 32% more
work than capacity. The plan's central claim — that one to two part-time people can carry this — is
false at the ceiling and only just true at the floor, and it is better to know that now than to
discover it in month nine as an unexplained backlog.

Three levers, in the order they should be pulled, and the reason for that order:

1. **Cut the intake ceiling from 60 candidates a week to 40.** Triage falls from 1.5 h to 1.0 h,
   stub-writing from 1.5 h to 1.0 h and promotion from 3 h to 2 h — **2 h/week recovered**.
   Discovery yield is the most elastic quantity in the table and the least differentiating: a stub we
   never promote is the cheapest thing to have fewer of, and the unadmitted remainder stays
   searchable in `data/_discovery/` either way.
2. **Lengthen the re-verification interval from twelve months to eighteen**, taking that row from 4 h
   to ~2.7 h — **1.3 h/week recovered**. This one has a real cost: `last_verified` ages visibly on
   the site, which is exactly the signal we claim nobody else publishes. It is second rather than
   first because the cost is visible, which is an argument for it rather than against it.
3. **Drop the sweep cadence one tier across the board**, quarterly to semi-annual and so on. This is
   last because sweeps are the breadth differentiator and the first thing a tired team stops doing
   anyway; cutting them deliberately at least makes it a decision.

After levers 1 and 2 the range is **18.9-23.1 h/week**, which fits at the floor and still does not at
the ceiling. **What must not be cut is the claims-and-conditions row.** It is four hours a week and
it is the entire second differentiator; a plan that balances its budget by deleting the thing that
makes it worth doing has balanced nothing.

**(b) Triage throughput, and the intake ceiling that follows.** A triage decision is: read the title,
the classifier rationale and, when unclear, the abstract, then choose keep or drop. At **40 decisions
an hour** -- 90 seconds each, deliberately below the 60/hour the previous draft assumed, on the same
over-throttle principle applied to rate limits -- 1.5 hours a week is **60 candidates a week**.

**That 60 is the hard intake ceiling, and every discovery adapter is sized against it.** arXiv alone
yields 100-670 candidates a week at the keyword prefilter `[M]`; after a classifier at the 85% target
that is still 85-570. So the classifier emits a score, the queue admits only the **top 60 by score**,
and the remainder sit unadmitted in `data/_discovery/` -- searchable by a curator who goes looking,
invisible to the site, and never counted as backlog.

**(c) What 60 a week actually produces.**

| Stage | Rate | Weekly |
| --- | --- | --- |
| Candidates admitted | ceiling | 60 |
| Genuine evaluation-artifact releases | at the 85% precision target | ~51 |
| Clear the "worth an entry at seed scale" bar | ~35-40% `[E]` -- our estimate, to be measured at the first 200-candidate checkpoint | **~18-20** |
| Written as stubs, 5 min each | 1.5 h | ~18 |
| Promoted to full depth, 60 min each *(see the note below -- this is a point estimate inside a range)* | 3 h | **~3** |

**The 60 minutes in that last row deserves a flag, because it is doing more work than it looks.**
The plan's per-entry rate is a range of 30-90 minutes ([14-roadmap.md](14-roadmap.md) §"Effort
sizing" owns it and records that it has never been measured), and 60 is the top of the band a
*promoted stub* should sit in rather than the midpoint of the whole range — a promotion starts from
identity, a link and a domain that already exist, so it is cheaper than a cold entry. It is also,
uncomfortably, the exact value `14`'s stopping rule (a) treats as the trigger for a re-plan. If the
20-entry checkpoint measures promotion at 60 minutes or more, this funnel produces two full entries
a week rather than three and the steady-state budget in §5.4(a) needs lever 1 immediately. The
number is stated rather than hidden precisely so that the checkpoint has something to falsify.

That is **roughly 900 stubs and 150 full entries a year** from discovery. It reconciles with the
domain reconnaissance's twelve-to-eighteen-month family target -- [00-vision-and-scope.md](00-vision-and-scope.md)
§8 owns the corpus-shape figures and this document does not restate them -- but only at *stub*
depth, and that qualification matters enormously. The recon's own effort model offers "a two-tier quality model (full
curation for Tier 1, a lighter stub with name/URL/domain/status for Tier 2)"; this is that model with
numbers attached.

**(d) The stub tier, as a schema state rather than an attitude.**
[14-roadmap.md](14-roadmap.md)'s stopping rule (c) already names "Tier-2 stub mode (name, URL,
domain, status, one source)" as a documented quality tier and an escape valve with a numeric trigger.
It has no schema field, which means today it is a description of a habit. **Request (§11):
`Benchmark.curation.depth: stub | full`**, where:

- a **stub** is identity, at least one resolving and archived link, a primary domain, a lifecycle
  value and provenance. It costs about **5 minutes**. It is explicitly **not** fully facet-classified,
  it carries a visible "stub" badge, and it is **excluded from Gap Finder assertions** -- because a
  thin row makes a gap claim unfalsifiable, which is the same reasoning behind the under-surveyed
  muting rule in the seed-target decision;
- a **full** entry is the 30-90 minute record the plan costs elsewhere.

Breadth does not require depth on day one. That is the whole value of the tier, and it is why a
1,500-benchmark index is reachable by a two-person team and a 1,500-*fully-curated*-benchmark index
is not.

**(e) The WIP cap and the expiry policy.** A queue that only grows is a queue nobody opens.

- **Cap: 250 open candidates**, about four weeks of intake. Above the cap, discovery adapters stop
  admitting new candidates entirely and write `queue-full` into their run record. **A visibly stalled
  intake is a signal; a silently growing backlog is a lie.**
- **Expiry: 90 days.** An un-triaged candidate older than 90 days is closed with `triage.outcome:
  not-triaged`. It stays in `data/_discovery/` -- searchable, never published, never deleted, because
  deleting it would mean rediscovering it forever.
- **Re-discovery is a promotion signal.** A benchmark independently rediscovered by a second adapter
  after expiry re-enters the queue at the top. Something two sources found is something worth ninety
  seconds.

**(f) How this reconciles with the Tier-1 exit criterion.** The previous draft said "after Tier 1 we
should hold on the order of 300-600 benchmarks with real provenance". That is not what Tier 1
produces and the arithmetic never supported it. What Tier 1 actually produces is a **discovery
tree**: Epoch's 81 benchmark seeds, HF's 95 tagged datasets and 1,019 leaderboard Spaces, GitHub's
2,233 topic-search repos and 227 harness task directories, plus arXiv's continuous feed. Deduplicated
against each other, our estimate is **1,200-1,800 distinct benchmark candidates, of which 300-600
carry enough identity, links and licence to be stub-grade** `[E]` (unverified -- an estimate from the
source counts, not a measured dedup; the first run settles it).

**Published after Tier 1: zero**, until a human reviews them, per
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §8 Rule 1. The honest exit
criterion is therefore about the *pipeline*, not the corpus, and §8.1 states it that way.

---

## 6. The non-scraped sources, and the manual sweep programme

Some of the most valuable material in the entire index has no API, changes on an annual or biennial
cycle, and lives behind a hand-built HTML page maintained by an academic group. CASP is on a two-year
cycle with results published as peer-reviewed assessment papers. DCASE re-issues seven tasks every
year with a new evaluation set. LifeCLEF requires a CEUR-WS working-note paper before a submission is
eligible for the official ranking. BraTS is five MICCAI challenges wearing one name. None of this is
scrapeable, and **pretending otherwise is how a plan quietly becomes fiction.**

So we plan for it explicitly: a **scheduled manual sweep**, with a written checklist, a per-family
cadence, and a curator log entry that records "checked, no change" as a first-class outcome. The "no
change" record matters more than it sounds -- it is the difference between an entry that is current
and an entry that merely has not been touched, and it is precisely the distinction that Ecosystem
Graphs, BetterBench and Evidently's database all failed to make visible before they went stale.

### Cadence by domain family

**All nineteen families appear.** The previous draft's table had thirteen rows and omitted language,
code, mathematics, reasoning-general, multimodal and engineering-design -- the implicit reasoning
being that they are covered by automation, which is broadly true and was never stated, so a curator
reading the checklist would reasonably conclude those families need no sweep at all. They do, and for
a different reason: for the ingest-then-verify families the sweep target is **lineage and supersession
events**, not new benchmarks. OSWorld became OSWorld-Verified and OSWorld 2.0; Terminal-Bench 2.0 and
2.1 run concurrently; SWE-bench has six forks; FrontierMath has four variants; HELM has eight. No
adapter detects a fork; a human notices one. Benchmark lineage is differentiator (ii), and this is
where it is actually maintained.

Cadence is set by how fast the family's benchmark population turns over, not by how interesting it
is. The nineteen families are the vocabulary owned by [02-taxonomy.md](02-taxonomy.md) §3.

| Family | Cadence | Anchor events | What the sweep catches that automation does not |
| --- | --- | --- | --- |
| robotics-embodiment | **Quarterly** | CoRL (Nov), RSS (Jul), ICRA/IROS, CVPR Embodied AI workshop (Jun) | Everything. No central hub exists anywhere. The domains recon estimates 40+ new named manipulation benchmarks a year with most dying inside 18 months (its own estimate, unverified -- confirm before relying on this). Fastest-churning family in the index, and the largest unindexed field in the landscape |
| agents-tooluse | **Quarterly** | Rolling; no conference anchor | Harness and scaffold changes, and leaderboard forks that outpace papers (OSWorld, Terminal-Bench). The benchmarks are discoverable; the *versions* are not |
| vision | **Quarterly, capped** | CVPR (Jun), ICCV/ECCV, NTIRE, Image Matching Workshop | Workshop challenge tracks, which have no feed. Highest long tail of any family (ceiling above 1,000). **Cap the sweep deliberately** or this family eats the project |
| medicine-health | **Quarterly** | MICCAI (Sep/Oct), RSNA (Nov) | Grand Challenge's API covers most of it; the sweep catches BraTS-style clusters, PhysioNet gated releases and non-imaging clinical benchmarks |
| code | **Quarterly** | Rolling | **Lineage only.** SWE-bench's six forks, Terminal-Bench's concurrent 2.x line, contamination events. The numbers are ingested; the family tree is human work |
| chemistry-materials | **Semi-annual** | NeurIPS AI4Science, ACS, CACHE round announcements | Matbench Discovery is semi-automatable; CACHE runs multi-year rounds with two phases each and publishes no feed |
| biology-genetics | **Semi-annual** | CASP (biennial), CAFA, CAGI, DREAM, Virtual Cell Challenge | CAMEO runs continuous weekly automated evaluation and needs a lighter, more frequent check than the rest of the family. CASP/CAFA/CAGI decompose into 100+ children, so the family/child convention lives or dies here |
| earth-climate | **Semi-annual** | Climate Change AI workshop, AGU/EGU, LifeCLEF (CLEF, Sep) | WeatherBench 2, ChaosBench and GEO-Bench 2 move on paper cycles, not continuously |
| audio-speech | **Semi-annual** | DCASE (window Apr-Jun, results 30 Jun), INTERSPEECH, IWSLT, ISMIR | The Open ASR Leaderboard is an HF Space and is automatable; the challenge families are not. DCASE is one name for seven unrelated tasks re-issued yearly |
| physics | **Semi-annual** | NeurIPS ML4PS, ACAT/CHEP, NeurIPS competition track | Highly fragmented by subfield with almost no shared vocabulary. The HEP ML Living Review (`iml-wg.github.io/HEPML-LivingReview`) is itself a curated index and the best single sweep target |
| safety-alignment | **Semi-annual** | inspect_evals releases, AISI publications | `inspect_evals` is automatable and covers a large share; the sweep catches the private and institutional ones, and the dead repos |
| society-econ-law | **Semi-annual** | ICAIL, FAccT, Metaculus quarterly tournaments | Many benchmarks here are commercial and private; the sweep is mostly about recording that they exist and are not reproducible |
| games-planning | **Semi-annual** | NeurIPS competition track, IEEE CoG, ARC Prize milestones | Rating-pool composition changes, which silently invalidate stored Elo. ARC Prize publishes on its own schedule |
| multimodal | **Semi-annual** | CVPR, NeurIPS, vendor releases | Boundary maintenance with vision, per [02-taxonomy.md](02-taxonomy.md) §11's rule -- the sweep is as much about *reclassification* as discovery |
| language | **Annual** | ACL/EMNLP/NAACL | **Lineage and contamination only.** The single most duplicated area in the landscape; we catalogue richly and curate claims almost not at all. The sweep checks that supersession edges and contamination evidence are current |
| mathematics | **Annual** | NeurIPS, AIME/IMO cycle | **Lineage only.** FrontierMath's four variants and the annual AIME/HMMT contamination events. Volume is not the issue; version confusion is |
| reasoning-general | **Annual** | NeurIPS, ICLR | **Lineage only.** Same shape as mathematics |
| general-intelligence | **Annual** | ARC Prize, HLE updates | Low volume, high scrutiny -- roughly twelve field-defining families in total, the one family small enough to sweep completely |
| engineering-design | **Annual**, after a Phase-0 scoping survey | NeurIPS AI4Science, EDA/CAD venues | Unknown. The recon never surveyed it as a family and named only four candidates (CadEval, AutoLabs, Learn2Design, Blueprint-Bench 2) plus an unenumerated EDA/CAD cluster. The first sweep is a survey, not a check |

**The table is generated, not typed.** The family column is emitted from `taxonomy/domains.yaml` by
the same script that generates the seed-target table, and a CI check asserts that the sweep
checklist's family list is exactly the domain vocabulary. Without that check, these two documents
drift within a quarter -- which is precisely how the corpus came to carry both "eighteen families"
and "nineteen families" simultaneously.

### The sweep checklist

The checklist is a file in the repo, not a habit. Each line is a URL, an expected shape, and the
field we are checking. A sweep produces one PR per family containing every change plus a dated
"checked" stamp on every unchanged entry.

```
SWEEP: <family>            date: YYYY-MM-DD      curator: <handle>
For each hub in the family list:
  [ ] Page loads; note HTTP status and any redirect
  [ ] New edition / new cycle / new task announced since last sweep?     -> new Benchmark draft
  [ ] Existing edition superseded, forked or renamed?                    -> lineage edge, superseded_by
  [ ] Leaderboard still updating? last-result date vs last sweep         -> lifecycle
  [ ] Repo pushed_at, HF lastModified, dataset still downloadable        -> lifecycle
  [ ] Licence or access terms changed (new DUA, new gating)?             -> access fields + §1.2 veto
  [ ] Paper / assessment publication since last sweep?                   -> Source + DOI
  [ ] archive_url present and CDX digest unchanged?                      -> re-archive if changed
  [ ] Rating pool composition changed (Elo families only)?               -> new RatingPool snapshot
  [ ] If nothing changed: write checked_at, do not touch any other field
```

Representative hub list, by family, drawn from the domains recon (this is the seed; the file is
maintained, not frozen):

- **robotics-embodiment**: `behavior.stanford.edu/challenge`, `libero-project.github.io`,
  `robocasa.ai`, `robotwin-platform.github.io`, `robo-arena.github.io`, Open X-Embodiment, ManiSkill,
  SimplerEnv, Meta-World, RLBench, Habitat, BEHAVIOR-1K, DuoBench.
- **biology-genetics**: `predictioncenter.org` (CASP; CASP17 target call open for 2026),
  `cameo3d.org` (weekly automated), CAFA, CAGI, DREAM, `arcinstitute.org` (Virtual Cell Challenge),
  Open Problems.
- **medicine-health**: Grand Challenge (API, automated), BraTS cluster (Zenodo record 19714728),
  `physionet.org` (gated), `rexrank.ai`, MedHELM, `medmnist.com`.
- **chemistry-materials**: `matbench-discovery.materialsproject.org` (has `/api` and RSS),
  `opencatalystproject.org`, `cache-challenge.org`, Polaris Hub, `tdcommons.ai` (freshness `[U]`).
- **earth-climate**: `sites.research.google/gr/weatherbench`, `leap-stc.github.io/ChaosBench`,
  `github.com/ServiceNow/geo-bench`, PANGAEA, `cybench.agml.org`, `imageclef.org/LifeCLEF2026`,
  ECMWF operational scorecards.
- **physics**: `iml-wg.github.io/HEPML-LivingReview`, `fair-universe.lbl.gov`, `polymathic-ai.org`,
  CritPt, `metriq.info`, `github.com/SRI-International/QC-App-Oriented-Benchmarks`.
- **audio-speech**: `dcase.community/challenge2026`, Open ASR Leaderboard (HF Space),
  `superbbenchmark.org` (2026 status `[U]`), IWSLT proceedings, MIREX (2026 status `[U]`).
- **vision**: CVPR/ICCV/ECCV workshop challenge indices, NTIRE (Codabench),
  `image-matching-workshop.github.io`, `rrc.cvc.uab.es`, ScanNet++.
- **games-planning**: `arcprize.org/leaderboard`, Kaggle Game Arena, NeurIPS competition track,
  TextArena.
- **society-econ-law**: GDPval, LegalBench and its live Vals leaderboard, `forecastbench.org`,
  `metaculus.com/futureeval` (quarterly).
- **agents-tooluse**: OSWorld and its verified/2.0 line, Terminal-Bench 2.x, `harborframework`
  releases on HF, HAL (submissions paused), BFCL.
- **code**: SWE-bench and its six forks, SWE-bench Multilingual/Multimodal, EvalPlus, LiveCodeBench,
  BigCodeBench.
- **safety-alignment**: `inspect_evals` releases, AISI publications, Apollo Research's
  largely-private suite (recorded as `access: private` entries).
- **language / mathematics / reasoning-general / multimodal / general-intelligence**: one hub,
  `opencompass.org.cn` / CompassHub, swept semi-annually per §4.1 -- it is the only entry in this
  checklist that exists to counter the catalogue's English-language sourcing bias, so it is the one
  that must not be quietly dropped when a sweep runs late. Otherwise the sweep is a lineage pass over
  entries we already hold, driven by `superseded_by` gaps and by the version strings appearing in
  Epoch and EEE that do not match any `BenchmarkVersion` we carry.
- **engineering-design**: no hub list yet. The Phase-0 scoping survey produces the first one.

### Effort, recomputed against nineteen families

The previous draft summed thirteen families to "roughly 12-20 person-days a year". That figure is
superseded, because the family count changed and a figure derived from a corrected number must be
recomputed rather than relabelled.

| Tier | Families | Sweeps/year | Hours/sweep | Hours/year |
| --- | --- | --- | --- | --- |
| Quarterly | 5 (robotics, agents, vision, medicine, code) | 4 | 4-5 | 80-100 |
| Semi-annual | 9 (chemistry, biology, earth-climate, audio, physics, safety, society, games, multimodal) | 2 | 2-3 | 36-54 |
| Annual | 5 (language, mathematics, reasoning-general, general-intelligence, engineering-design) | 1 | 2-3 | 10-15 |
| **Total** | **19** | | | **126-169 h/year** |

**That is 16-21 person-days a year, or 2.5-3.4 hours a week** at the **50-working-week year** this
plan uses throughout -- two weeks of the calendar are assumed gone to holiday, illness and the weeks
nobody works, and stating the convention is cheaper than three documents dividing by 52, 50 and
"about a year" and then disagreeing. That is the line that appears in the weekly budget in §5.4(a). It replaces the 12-20 person-day figure that
[00-vision-and-scope.md](00-vision-and-scope.md) §8's effort table currently carries and attributes
to this section; that figure was computed against thirteen families and should be updated to
**126-169 h** there.

This is the real cost of the breadth differentiator. It is not large, but it is permanent, it never
automates away, and it is the first thing a tired team stops doing.

---

## 7. Archival is not optional

**Every `Source` that is not a DOI gets an `archive_url`, and the SLA is seven days from first
ingest.** The previous draft said "at ingestion time, not later" -- an absolute that reads well and
makes the first run of Tier 1 fail, because the arithmetic was never done. It is done below.

The reason archival matters at all is arithmetic of a different kind. Blog posts move, leaderboards
are rewritten in place, university pages are reorganised when a student graduates, and companies
delete announcements. The recon found Aider's leaderboard last updated 2025-11-20, Papers with Code
301-redirecting to a different site entirely, and `lmarena.ai` redirecting to `arena.ai` `[M]`.
Project that forward three years and an index whose citations all point at 404s is not a degraded
index; it is a worthless one, because the one thing it promised -- that every claim traces to a
source -- stopped being true.

### 7.1 The volume arithmetic, and the rolling budget

| Stage | Sources | Non-DOI, needing capture | Basis |
| --- | --- | --- | --- |
| Seed (320 entries) | ~800-1,000 | **~700-900** | 2-3 sources per entry (paper, homepage, repo, leaderboard); papers usually carry a DOI and are exempt `[E]` |
| Maturity (1,500 entries + ~900 hand-curated claims) | ~4,500-5,500 | **~3,800-4,600** | Same per-entry rate, plus ~500 distinct claim sources not shared with an entry `[E]` |

Against SPN2's documented 12 concurrent and 100,000 per day `[U]`, the binding constraint is not the
daily cap -- it is per-capture latency, which the recon did not measure. SPN2 renders the page with a
browser, so **assume 30-60 seconds per capture (unverified -- measure on the first hundred and
replace this figure)**. At 12 concurrent and 45 seconds mean, throughput is roughly **960 captures an
hour** `[E]`. The seed backlog is therefore about an hour and the maturity backlog about four and a
half -- which fits inside a 6-hour GitHub Actions job today and will not fit forever, and in any case
a single long job is the wrong shape for something whose failure mode is a 429.

**So: a rolling archival budget, not a burst.**

- **500 captures per nightly run**, matching the usage budget in
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §10, ordered **oldest-unarchived
  first**, resumable from a cursor in `ingest/state/archive.json`.
- The seed backlog clears in **two nights**; the maturity backlog in **nine** `[E]`. Neither blocks
  anything, because `archive_status: pending` is a legitimate state.
- `if_not_archived_within=30d` does server-side deduplication, so a re-run is free and a dropped cron
  costs nothing.
- The archiver is invoked **per Source, never per field**. The per-URL cap of 10 per day `[U]` is
  well above per-Source usage and instantly exceeded by per-field usage.

**The CI rule, correspondingly softened from an absolute to a deadline.**
[04-data-model.md](04-data-model.md) §12's tier-3 rule currently requires that every non-DOI `Source`
has an `archive_url`. **Request (§11): the rule becomes `archive_url` present, OR
`archive_status: pending` with `archive_requested_at` within 7 days, OR `archive_status: failed` with
a recorded reason.** As written today, the first run of the seed phase fails CI on its own success.

### 7.2 The link-rot re-check, and why HEAD does not work

A **scheduled link-rot re-check** walks every `Source` on a slow rotation sized so the whole corpus is
covered each quarter. The previous draft specified `HEAD` against the URL. That will not work, and
the document's own evidence says so: many servers return 405 to HEAD, more return 200 for soft-404s,
and SPA leaderboards return 200 with an empty shell. §3.17 already records that LiveBench is an SPA
whose current filename could not be extracted `[U]` -- so **the exact class of source most likely to
rot is the class HEAD cannot check.**

**The mechanism.**

1. `GET` with `Range: bytes=0-32767`, falling back to a plain `GET` when the server ignores `Range`
   (most do for small pages). Never `HEAD`.
2. Compare `sha256` of the fetched body against `Source.body_sha256` from the previous check, and
   query CDX for the archived copy's `digest`.
3. Apply the soft-404 heuristics **before** declaring the link live.

**Four outcomes, not three** -- the previous draft's three-outcome model had no state for "returned
200 but the content is meaningless":

| Outcome | Condition | Action |
| --- | --- | --- |
| `live` | 2xx, body passes the soft-404 heuristics, digest unchanged | Stamp `checked_at` |
| `changed` | 2xx, passes heuristics, CDX `digest` or `body_sha256` differs | Re-archive **and** flag for curator review -- a silently rewritten leaderboard is a data-integrity event, not a refresh |
| `suspect` | 2xx **and** (body under 2,048 bytes after whitespace stripping) **or** (body is an SPA shell: a single root `div` with no text node over 200 characters) **or** (title matches `/404\|not found\|page not found/i`) | `link_status: suspect`, queued for human review. **Never** `live` |
| `dead` | 4xx, 5xx after retries, DNS failure, or a redirect to an unrelated host | `link_status: dead`, keep `archive_url` as the canonical reference, raise a lifecycle review |

**Name the failure mode:** the failure here is a green link check on a page that has become an empty
React root -- the citation looks alive and points at nothing. That is worse than a 404, because a 404
is visible and this is not.

`link_status` and `archive_url` are rendered in the UI, not hidden. "This source is gone; here is the
archived copy from 2026-09-17" is a feature, and it is one no competitor offers.

### 7.3 Failure modes to design around

SPN2 refuses some URLs -- paywalls, robots-blocked hosts, JavaScript-only pages that capture blank. A
failed capture is recorded as `archive_status: failed` **with the reason**, not retried forever and
not silently dropped: an un-archivable source is a fact about that source's reliability and should
lower its verification level. The Availability API 429s on cold requests `[M]`, so existence checks go
through CDX. And a source we were asked to stop collecting from (§9) is never re-archived, because
honouring a no-collect request means stopping, not stopping visibly.

The rotation schedule itself -- which slice runs on which night, and how the cursor advances -- is
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)'s. This document sets the policy:
whole corpus each quarter, oldest first, 500 captures a night, four outcomes, seven-day SLA.

---

## 8. Tiered build order

**Ordered by differentiator impact first, transport stability second, with licence cleanliness as a
veto applied uniformly** (§1.2). The justification for each placement is the point of the tables; a
build order without reasons is a build order nobody can revise when circumstances change.

**A correction to the previous draft's calendar.** It described Tier 1 as "weeks 1-3" and Tier 2 as
"weeks 4-10", which read as project weeks and are not.
[14-roadmap.md](14-roadmap.md)'s phase table places the Epoch ingestion adapter in **Phase 3**,
ingestion at scale in **Phase 5** (post-v1), and archival among the **Phase 1** deliverables. The
tiers below are therefore expressed as *effort* plus a *phase anchor*, because a tier that claims a
calendar slot the roadmap has allocated to something else is a scheduling error waiting to be
discovered by whoever tries to execute it.

### 8.1 Tier 1 -- the first four adapters

Roughly three weeks of engineering effort. Archival (Tier 0 below) is Phase 1; Epoch is Phase 3; the
other three straddle Phase 3 and Phase 5.

| # | Adapter | Phase anchor | Why here |
| --- | --- | --- | --- |
| 0 | **Wayback SPN2 + CDX** | **Phase 1** | Not optional and not deferrable. Retrofitting `archive_url` onto records whose sources have already moved is impossible by definition, and Phase 1's own deliverables require every entry to have an archived source. Build it alongside the first hand-curated entries, not alongside the first adapter |
| 1 | **Epoch AI** ZIP + CSVs | **Phase 3** | CC-BY, static files, ETag-conditional, roughly 150 lines of Python plus ~80 per-file column stanzas. Yields 81 benchmark seeds with `random_baseline` / `score_ceiling` / `superseded_by`, ~390 systems with org, country and training FLOP, and 6,598 result claims of which 42.7% carry an uncertainty figure. Highest value per line of code in the catalogue, and the data is already on disk |
| 2 | **HuggingFace Hub** | **Phase 3-5** | No auth, permissive robots, a maintained client that handles backoff, and it hands us the eval-conditions vocabulary for free. Populates four entity types at once and is the best live discovery surface available |
| 3 | **GitHub metadata + harness clones** | **Phase 3-5** | Where `comparability_key` gets real values instead of nulls: 227 task directories of `lm-evaluation-harness` YAML, plus MTEB under CC0 and `inspect_evals` under MIT. Also delivers `pushed_at`, the input to the liveness differentiator nobody else has |
| 4 | **arXiv** (OAI-PMH delta + Query API backfill) + LLM triage | **Phase 5** | CC0 metadata, a decade-stable API, and the only continuous source of genuinely *new* benchmarks across every family. Accept the ~60% heuristic precision and pay the $0.60-$6 a month for the classifier |

**The exit criterion, restated as a property of the pipeline rather than of the corpus.** The
previous draft's "after Tier 1 we should hold 300-600 benchmarks with real provenance" was neither
achievable in three weeks nor the right thing to measure, since
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §8 Rule 1 means the published
count is the hand-reviewed count regardless of how many adapters run. Tier 1 is done when:

- [ ] **1,200-1,800 distinct benchmark candidates** sit in `data/_discovery/`, of which **300-600 are
      stub-grade** -- identity, a resolving archived link, a licence tag and provenance `[E]`
      (unverified estimate; the first run settles it).
- [ ] The **eval-conditions vocabulary is populated** from the harness YAML and the HF tag taxonomy,
      and `comparability_key` computes non-trivially for at least 100 benchmarks.
- [ ] The **triage classifier has been measured** on a hand-labelled set of 200 abstracts and reports
      precision, with the target being >= 85% (§5.2). Two hours of labelling; it converts the plan's
      only remaining guessed number into a measured one.
- [ ] **Intake is throttled** to the 60-candidate ceiling with the 250 WIP cap and 90-day expiry
      live (§5.4), and the queue depth is published.
- [ ] **Every adapter emits a run record** and `adapter_status`, and the `/sources` page renders
      (§3.0).
- [ ] **Zero machine-generated benchmark entities are published**, asserted in CI.

The number of *published* entries after Tier 1 is whatever the curator has reviewed, which at
§5.4's rates is dozens, not hundreds. The seed-release target of **320 Tier-1 families with all 19
domain families non-empty** ([02-taxonomy.md](02-taxonomy.md) §3 owns the target and its per-family
allocation; [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §11 owns its cost) is
Phase-1 hand curation, and no adapter shortens it.

### 8.2 Tier 2 -- second wave

Mostly Phase 5, with the two condition-rich sources pulled forward into Phase 3 because
`comparability_key` is a Phase-3 deliverable.

| Adapter | Placement reason |
| --- | --- |
| **Every Eval Ever field-name adoption** | **Moves out of Tier 2 into Phase 0.** It is a schema task, not an adapter, it costs an afternoon, and retrofitting condition field names across `_ingested/epoch/` afterwards is the same pain §3.1 warns about. The *adapter* and the alliance issue (§3.19) stay here |
| **HELM GCS bucket** | The richest eval-conditions data anywhere and 26 suites including robotics, medicine, finance and audio. Build it in Phase 3; its output stays in `data/_discovery/helm/` under the §1.2 veto until CRFM answers |
| **LMArena dataset** | CC-BY-4.0 parquet, 13+ arenas, the cleanest transport in the catalogue. Forces the style-control and `RatingPool` modelling early, which is good |
| **SWE-bench inline JSON** | 323 claims carrying `agent`, `reasoning_effort`, `cost` and `checked`. Small, but the best demonstration case for the comparability thesis in the LLM half of the map. Licence unresolved, so veto applies |
| **Grand Challenge API** | 264 medical-imaging challenges with publication links. The cheapest single route to non-LLM family breadth in the whole plan |
| **OpenRouter + LiteLLM + vendor RSS** | System-entity enrichment; needed before result claims can resolve to models reliably |
| **Semantic Scholar (with key)** | arXiv-to-paper identity resolution, cross-checked against OpenAlex. Gated on key turnaround, which is unverified, so it must not sit on a critical path |
| **Zenodo / Crossref** | DOI resolution, `conceptdoi` for version lineage, and minting our own release DOI. DataCite is optional and built only if a real gap appears |
| **Small statics** (EvalPlus, LiveBench, OGB, Matbench Discovery) | ~30 lines each; build them when the adapter framework makes them nearly free |
| **PwC identifier crosswalk** | Not an ingest. A local, gitignored match run emitting `data/_crosswalk/pwc.csv` (§3.9). Blocked only on reading the archive's own LICENSE file, which is a five-minute task on the §8.4 checklist |

### 8.3 Tier 3 -- manual and annual, deliberately not automated

NeurIPS D&B proceedings (annual December scrape of static HTML, then classifier-assisted triage of
497 papers **into the throttled queue**, not around it); CASP, Matbench, WeatherBench 2, OpenCompass
and the rest of the domain hubs (quarterly to annual sweeps per §6); Codabench and EvalAI competition
catalogues, filtered per §3.14 and placed **behind the Tier-1 exit criterion** so they never compete
with the seed corpus for curator time; vendor blogs as a weekly digest with human confirmation;
Kaggle under authentication and scoped to known competitions.

### 8.4 The licence-resolution checklist

This is a Phase-3 task list with owners and dates, and it is what makes §1.2's veto a mechanism
rather than an intention. Every row's answer is recorded as quoted text in `ingest/sources.yaml`,
where `make verify-sources` can re-check it.

| Source | Question | Who to ask / where to look | Target |
| --- | --- | --- | --- |
| **HELM bucket data** | May the `run_specs.json` and `runs.json` contents be redistributed as derived structured facts? | Email `crfm-help@stanford.edu` | Phase 3, week 1 |
| **Papers with Code archive** | What does the archive's own `LICENSE` file say, and what did Meta's sunset notice say? | Read both; HF tags are not evidence (§3.2) | Phase 3, week 1 |
| **SWE-bench leaderboard** | Under what terms is the inlined leaderboard JSON published? | Issue on `SWE-bench/SWE-bench` | Phase 3, week 2 |
| **Grand Challenge** | Terms for automated collection and redistribution of challenge metadata | Their contact form; Radboud UMC DIAG | Phase 3, week 2 |
| **Codabench / EvalAI** | Any data licence or automated-access terms at all? No terms page was found | Issues on their GitHub repos | Phase 5 |
| **Semantic Scholar** | Is the 2026 corpus licence still ODC-BY 1.0? | Read the current licence page | Before any bulk ingest |
| **LiteLLM price file** | Does the repo-root MIT cover this specific file? | Issue on `BerriAI/litellm` | Phase 5 |
| **Matbench Discovery, Open Catalyst, GEO-Bench, WeatherBench 2** | Licence on the leaderboard data, not the code | Repo LICENSE files, then maintainers | Phase 5 |
| **Artificial Analysis** | Which of the two published free-tier limits is correct? | Their docs, then support | Only if we ever need more than zero requests |
| **Kaggle** | Documented API rate limits | Support; undocumented today | Before the Kaggle adapter |
| **OpenCompass / CompassHub** | Under what terms is the hub's evaluation-set metadata published, and is it separable from the Apache-licensed harness? | Issue on `open-compass/opencompass`; the hub's own terms page | Phase 5, before the first sweep promotes anything (§4.1) |

Until a row is closed, the source's adapter output is confined to the discovery or ingested trees and
cannot be promoted. That is the whole rule.

### 8.5 Never

§4 lists these with reasons. The one worth repeating: **do not ingest Benchmark Radar's content or
BenchmarkList's database.** The first has an incompatible licence, the second has no licence at all,
and a project whose central claim is provenance cannot afford to be the one that scraped a
competitor.

---

## 9. Legal and ethical posture

### 9.1 The shield

**The hard constraint that we never host or redistribute benchmark data is also our strongest legal
protection.** Nearly every ambiguity in this document dissolves if we only ever store facts plus
links. That is enforced structurally, not by good intentions:
[05-repository-and-workflow.md](05-repository-and-workflow.md) §9 check 7 rejects any committed
`.parquet`, `.jsonl` or `.csv` under `data/`, rejects files over 256 KB, and rejects any single prose
field over the cap -- so "metadata only" is an invariant rather than a promise. The one `.csv` this
document adds under `data/` is `data/_crosswalk/pwc.csv`, which is exempted by name and constrained
by its own identifier-only regex (§3.9); an exemption with a tighter rule attached is the correct
shape, and an exemption without one would have been the first crack.

### 9.2 Assume no anonymous quota exists

This is the single most likely way Tier 1 fails on its first run, and the previous draft did not
mention it.

Several sources in §2 publish **per-IP** anonymous budgets -- HuggingFace's 500 API calls per
5-minute window is per IP `[D]`; Semantic Scholar's unauthenticated pool is 1,000 RPS *shared among
all unauthenticated users globally* `[D]` and was already returning 429 on a cold first request
`[M]`; arXiv's ToU limits connections rather than identities `[D]`. Per
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §3, our scrapers run as GitHub
Actions cron. **Actions runners sit on shared Azure egress ranges used by every other tenant on the
planet.** Those anonymous per-IP budgets are therefore not ours; Semantic Scholar's global pool is
already exhausted before we arrive; arXiv and OpenAlex may already be throttling that range for
reasons that have nothing to do with us.

**The operating rule: assume no anonymous quota exists.** Every adapter authenticates wherever a free
token is available, and treats anonymous access as a fallback that may be at zero on arrival.

**Week-1 task, with the request URLs, because five free keys are an afternoon and a blocked Tier 1 is
a fortnight:**

| Key | Where | Cost | Blocks |
| --- | --- | --- | --- |
| `HF_TOKEN` | `huggingface.co/settings/tokens` | Free | HF adapter throughput |
| GitHub fine-grained PAT | `github.com/settings/tokens` | Free | The GitHub adapter entirely -- the ambient `GITHUB_TOKEN` is 1,000/hr/repo |
| OpenAlex API key | Per their blog's signup, ~30 seconds `[D]` | Free | A 10x budget difference, if the blog is right |
| Semantic Scholar key | `semanticscholar.org/product/api#api-key-form` | Free, arrives by email, turnaround `[U]` | S2 entirely; request it first because it is the only one with a queue |
| Internet Archive S3 keys | `archive.org/account/s3.php` | Free | SPN2 at 12 concurrent instead of 6, and the `/save/status/user` quota endpoint |

**Name the failure mode: a green CI run that fetched nothing, because a neighbour on the same runner
IP spent the budget.** Every adapter therefore asserts a non-zero record count when it expected one,
and a zero-row response from a previously-populated endpoint is schema drift or quota exhaustion --
never an empty result (§3.2).

### 9.3 Clean sources -- automated collection permitted, redistribution fine

| Source | Terms | Attribution |
| --- | --- | --- |
| arXiv metadata | "free to use descriptive metadata ... under CC0 1.0" `[D]`; OAI "Metadata harvesting permitted" `[M]`. 1 req / 3 s; `Crawl-delay: 15` on HTML | Not legally required; do it anyway. Must not imply arXiv endorsement |
| Epoch AI | "free to use, distribute, and reproduce provided the source and authors are credited" -- CC-BY `[M]` | **Required.** Cite: Epoch AI, "Capabilities & Benchmarking", epoch.ai |
| LMArena `leaderboard-dataset` | CC-BY-4.0 on the HF repo `[M]` | Required |
| MTEB `embeddings-benchmark/results` | CC0-1.0 `[M]` | Courtesy only |
| OpenAlex bulk snapshot | CC0 `[D]` | Courtesy |
| Every Eval Ever | Data CC BY 4.0, code MIT `[D]` | Required |
| inspect_evals | MIT `[M]` | Required |
| HuggingFace Hub API | `robots.txt: Allow: /` `[M]`; documented public API with published tiers | Carry each dataset's own `license:` tag through into our record |
| GitHub API | ToS-sanctioned; robots.txt directs bots to the API `[M]` | Carry each repo's SPDX licence |
| Zenodo, Crossref, DataCite | Open public APIs, no auth, no anti-bot | Courtesy; Crossref rewards `mailto` |
| Grand Challenge, Codabench, EvalAI | Open public APIs, no anti-bot `[M]` -- **but no licence statement found `[U]`**, so §1.2's veto applies to their output until §8.4 closes those rows | Courtesy |

### 9.4 Constrained sources

- **Papers with Code archive, tagged CC-BY-SA-4.0.** The ShareAlike clause is the single biggest legal
  trap in this catalogue, and the determination currently rests on an HF repo tag, which §3.2 says is
  not evidence. Decision and mechanism in §3.9: content never enters the repository, identifiers only.
- **Artificial Analysis.** "Use of the API requires attribution across all tiers ... For
  redistribution rights or bespoke contract terms, contact the team" `[D]`. Free tier 100 req/24h
  `[D]`. Posture: link out, never ingest.
- **Semantic Scholar.** API License Agreement plus corpus licence (ODC-BY, `[U]` for 2026). Read the
  licence before bulk ingestion.
- **HELM GCS data.** Code Apache-2.0; bucket data licence `[U]`. A publicly readable bucket is
  permission to read, not to redistribute. Get an answer in writing from CRFM (§8.4), or store only
  derived facts plus a link.
- **MLCommons Croissant.** The spec is **CC BY-ND 4.0 -- no derivatives** `[D]`. We may publish a
  namespaced `croissant-benchmark` extension; we may **never** republish a modified spec. Getting this
  wrong would poison the highest-value standards play available to the project.
- **Community submissions.** Constrained by *our* terms, not someone else's: without the CC-BY grant
  checkbox in §3.20, a CC-BY corpus contains contributions nobody granted CC-BY on. That is the second
  licence trap after PwC and it is entirely within our control to avoid.

### 9.5 Hard prohibitions

These are not preferences. Crossing any of them is a plan violation.

- **DrivenData**: `robots.txt` disallows `/*/leaderboard_partial` and `/competitions/search/` `[M]`.
  Off-limits to bots. Manual curation only.
- **Epoch AI**: `robots.txt` disallows `/inspect-viewer/` and
  `/frontiermath/tiers-1-4/benchmark-problems`, with the stated reason of avoiding training-set
  contamination `[M]`. Honour it -- it is the same ethic we claim.
- **arXiv**: no full-content harvesting; `/e-print`, `/src`, `/find`, `/refs`, `/cits` disallowed
  `[M]`. We are metadata-only, so compliance is free.
- **OpenReview**: serves an active bot challenge `[M]`. **Do not build a bypass.** Use proceedings
  HTML, or an authenticated `openreview-py` session under a real, identified account.
- **Kaggle**: ToS restricts mass automated download `[D]`. Authenticate and stay narrow, or skip.
- **`s3://swe-bench-submissions`**: 403 anonymous `[M]`. Link, never probe.

### 9.6 Operating rules for every adapter

The **mechanisms** for these belong to
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §10.1 -- `HostPolicy` constructed
from a single `ingest/policy.yaml`, the fetcher refusing any host without a policy entry, the
`robots.txt` cache, the `no-collect` list read at start-up. This section owns the **policy**, and the
previous draft blurred the two by specifying token buckets, concurrency and a rotation schedule here.
The policy is:

- **One identifying User-Agent on every request**, carrying the project name and a contact URL:
  `UAIBI/0.1 (+https://<project-domain>)`. arXiv, OpenAlex and Crossref
  explicitly reward identified clients.
- **Authenticate wherever a free token exists** (§9.2), and never depend on an anonymous budget.
- **robots.txt is honoured by the fetcher itself**, not by developer discipline. It must be
  structurally impossible for a code path to reach `drivendata.org/*/leaderboard_partial`.
- **Over-throttle deliberately, and hardest against small academic servers.** The policy numbers:
  arXiv 1 req / 3 s for the API and 1 / 15 s for any `arxiv.org` HTML; HuggingFace about 1 req/s;
  GitHub with `If-None-Match` and a one-second floor; Grand Challenge, Codabench, EvalAI and
  `predictioncenter.org` at roughly 1 req / 2 s. Being the project that took down the CASP server is
  a reputational injury no licence protects against.
- **Sequential within a source, parallel only across sources.** Never fan out concurrent requests at
  one host.
- **Attribution is machine-generated.** An `/attributions` page is built from the `Source` and
  `IngestBatch` entities at build time so it cannot drift from what we actually ingested. CC-BY is
  cheap to comply with and expensive to be caught violating, and a footer does not survive a fork --
  which is why [04-data-model.md](04-data-model.md) §9 stores the attribution text with the data.
- **We will honour any maintainer's request to stop collecting from their site.** This is stated
  publicly on the About page with a contact address, the request is recorded in the repo as a
  `no-collect` entry that the fetcher reads, and compliance is immediate and unconditional -- no
  negotiation, no "but it's public data". A project asking the field to trust its provenance cannot
  simultaneously argue with the field about consent.

### 9.7 Where the real risk sits, ranked

1. **CC-BY-SA contamination from Papers with Code.** The only issue that could force a licence change
   on the whole index. Resolved by §3.9's identifier-only decision, and the residual risk is that
   someone later "helpfully" ingests the content anyway -- which is why the enforcement is a regex on
   a file rather than a paragraph in a contributing guide.
2. **Unlicensed community contributions.** Second-largest, entirely self-inflicted, and fixed by one
   checkbox (§3.20).
3. **Republishing benchmark content rather than metadata.** Mitigated structurally (§9.1).
4. **Propagating wrong numbers.** Not a legal risk; an existential one. The OpenAlex `W4387561453`
   defect -- right DOI, right authors, wrong title, citation count off by two orders of magnitude --
   is exactly how a trust-based index dies. Mitigation: every numeric claim carries `source_url`,
   `fetched_at` and `archive_url`; any figure from a single aggregator renders with a visible
   single-source marker; and no aggregator's number is ever presented as the benchmark's own.
5. **Attribution hygiene.** Machine-generated, as above.
6. **Rate-limit misbehaviour against small community servers.** Over-throttle.

---

## 10. What this document defers

- **The HELM data licence.** Blocked on a written answer from CRFM (§8.4).
- **The OpenAlex free-key budget.** Three published numbers, one measurement, no agreement. Measure
  with a real key before sizing anything (§3.10).
- **Semantic Scholar key turnaround**, which is unverified and therefore must not sit on any critical
  path (§3.11).
- **Post-filter precision for Codabench and EvalAI**, deliberately not estimated. Measured on the
  first run and recorded (§3.14).
- **SPN2 per-capture latency**, which sets the archival wall-clock. Measured on the first hundred
  captures; the 30-60 second assumption is marked unverified (§7.1).
- **The true-positive rate of the triage queue** (~35-40% assumed), measured at the first
  200-candidate checkpoint (§5.4c).
- **How the adapters run** -- scheduling, state, conditional requests, identity resolution, dedup,
  draft-PR mechanics, failure classes, backoff and alerting -- is
  [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).
- **How a human clears the triage queue** -- issue-form contribution, bot validation, review and
  merge -- is [05-repository-and-workflow.md](05-repository-and-workflow.md). Note the constraint that
  carries across: **contribution must not require a pull request.** The PR-centric workflow is the
  exact friction that converted `JonathanChavezTamales/llm-leaderboard` into a closed website, and no
  amount of good sourcing survives a contribution path nobody uses.

**Resolved in this revision, and no longer deferred:** the Papers with Code CC-BY-SA question (§3.9 --
identifiers only, content never committed, CI-enforced); the build-order criterion (§1.2 --
differentiator impact first, licence as a uniform veto); the EEE join key (§3.19 -- our slug, their
`uaibi_id`); the intake capacity model and the stub tier (§5.4).

---

## 11. Schema additions this document requires

The previous draft collected Epoch's four pre-ingest fields and then introduced at least eight more
as though they already existed. They do not. This is the inbound request list to
[04-data-model.md](04-data-model.md) and, where noted, to
[05-repository-and-workflow.md](05-repository-and-workflow.md); it is a request, not an assumption,
and an adapter that needs one is blocked until it lands.

| Field | Entity | Why sourcing needs it | Blocked without it |
| --- | --- | --- | --- |
| `curation.depth: stub \| full` | Benchmark | §5.4(d). Makes the roadmap's "Tier-2 stub mode" a schema state rather than a habit, and lets a stub be excluded from Gap Finder assertions | The whole capacity model; breadth without depth has nowhere to live |
| `link_status: live \| changed \| suspect \| dead` | Source | §7.2's four outcomes. Three of them have no home today | Link-rot re-check |
| `archive_status: ok \| pending \| failed` + `archive_requested_at` + `failure_reason` | Source | §7.1's seven-day SLA. The current tier-3 rule requires `archive_url` outright, which fails CI on the seed phase's own first run | Archival at any scale |
| `body_sha256`, `archive_digest`, `checked_at` | Source | §7.2 compares content between checks; a CDX digest alone cannot detect a change our fetch saw | Link-rot re-check |
| `adapter_status`, `last_successful_run`, `last_content_change` | Source / adapter record | §3.0's published SLO | The `/sources` health page |
| ~~`EvalConditions.max_agent_steps`~~ **withdrawn** | -- | The field exists as `EvalConditions.max_steps` in [04-data-model.md](04-data-model.md) §8. SWE-bench's `instance_calls` maps onto it directly (§3.6). Recorded here rather than deleted so that nobody re-requests it | -- |
| `EvalConditions.perturbations` | EvalConditions | HELM's `data_augmenter_spec`. Robustness perturbations change what is being measured | HELM adapter fidelity |
| `ResultClaim.caveat` | ResultClaim | SWE-bench's `warning`. Keeping a publisher's number while dropping their own caveat is the most dishonest thing an aggregator can do | SWE-bench adapter |
| `SystemVersion.supported_parameters` | SystemVersion | OpenRouter's `supported_parameters[]`. It is how we know whether `temperature` was settable for a given claim | Condition completeness on ingested claims |
| `Benchmark.external_ids.{helm_scenario, grand_challenge, zenodo_concept, openrouter}` | Benchmark / System | §3.21. Four keys in active use with no declared slot | Join-key resolution |
| `data/_crosswalk/*.csv` as a recognised path, with the identifier-only regex | Repo layout + CI | §3.9's enforcement mechanism, and the one named exemption to the no-CSV rule in §9.1 | The PwC posture |
| CI checks A and B (bot-authorship path allowlist; `field_provenance: curator` on interpretive fields) + `schema/interpretive_fields.yaml` | CI | §1.1. Without them the `_suggested` rule is unenforceable | The entire adapter safety rule |
| CC-BY-4.0 grant checkbox on `new-benchmark.yml`, enforced by the bot | Issue form | §3.20. Without it, community submissions are the second licence trap | Community submission as a source |
| `Benchmark.code_licence` distinct from `data.licence` | Benchmark | §3.3. A repo's SPDX id and a dataset's licence are different facts and 30% of repos have neither | GitHub adapter |

Two already satisfied, recorded so nobody re-requests them: **`RatingPool`** exists in
[04-data-model.md](04-data-model.md) §2, which is what §3.6's Elo snapshot requirement needs; and the
**`ingestion` block with `field_provenance` and `licence_class`** exists in §9 of the same document,
which is what §1.1 and §1.2 build on.
