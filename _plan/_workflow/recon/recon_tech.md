Research complete. Here are the findings.

---

# FRONTEND / BUILD / SEARCH TECHNOLOGY — VERIFIED 2026-09-17

All versions checked live against npm registry, PyPI, GitHub API and vendor docs **on 2026-09-17**. Benchmarks marked "measured" were run locally (Node v24.11.0, Python 3.11.9) in this session.

---

## 1. STATIC SITE FRAMEWORK — **Astro 7.3.3** (keep, but the draft's version assumption is two majors stale)

**Verified facts**
- Latest: `astro@7.3.3`, published 2026-09-16. Astro 7.0 shipped 2026-06-22; 7.1 (2026-07-16), 7.2 (2026-08-06), 7.3 (2026-09-03).
- Astro 6.0 shipped Feb 2026 (beta 2026-01-13). **The draft's "Astro" almost certainly means Astro 5; you'd be skipping two majors.**
- `engines: { node: ">=22.12.0" }`. Bundles `vite@^8.0.13`, `zod@^4.5.4`, `shiki@^4.0.2`.
- `@astrojs/react@6.0.6` (2026-09-16), peer-supports React 17/18/**19**.
- Content Layer `glob()` loader natively parses **Markdown, MDX, Markdoc, JSON, YAML, TOML**. `file()` loader reads many entries from one JSON/YAML/TOML file. Collection `schema` is **optional**. Zod 4 is re-exported from `astro:content`.
- Astro 7.2 added `experimental.incrementalBuild`: routes return a `cacheKey` from `getStaticPaths()`; Astro also hashes each route's full module graph (template, layouts, components, imported assets, package code). Page is reused only when **both** match. Cache lives in `cacheDir` (default `node_modules/.astro/`). Routes without a `cacheKey` always re-render.

**Recommendation:** Astro 7.3.x, pinned exactly, with `@astrojs/react@6`, React 19, Node 22.12+ (use Node 24 LTS in CI). Turn on `experimental.incrementalBuild` and return `entry.digest` as `cacheKey` from the benchmark detail route.

**Decisive reason:** It is the only framework where the *default* is zero JS and the *exception* is an island. Your no-JS citability requirement is a first-class default rather than a discipline you have to enforce. And `file()` + `glob()` means your Python build artifact drops straight into a typed collection with no adapter code.

**Main risk — Astro 7's breaking changes are unusually sharp** (from the official v7 upgrade guide):
- New **Rust compiler** replaces the Go one and is *stricter about invalid HTML* — unclosed non-void tags are now errors.
- `compressHTML` default changed `true` → `'jsx'`. Adjacent inline elements lose the whitespace between them: `<span>a</span><em>b</em>` renders `ab`. **This will silently mangle facet-chip rows and inline provenance badges.** Set `compressHTML: true` explicitly on day one.
- **Sätteri** (Rust) replaces remark/rehype as the default Markdown processor. Any remark/rehype plugin must be ported or you reinstall `@astrojs/markdown-remark`.
- `src/fetch.ts` is now a reserved filename. Advanced routing + route caching are on by default.
- `@astrojs/db` is no longer maintained — do not plan on Astro DB.
- Vite 8 (breaks integrations depending on Vite internals).

**Build time at ~1,500 pages:** Astro's own figures — content layer is ~5x faster on Markdown, ~2x on MDX vs legacy collections, 25–50% less memory; Astro 6 generated 100 MDX pages in ~400ms. Extrapolating, 1,500 mostly-data pages is a **sub-2-minute cold build, well under Cloudflare's 20-minute build timeout**. I found **no published real-world benchmark in the 1,000–2,000 page range** — mark this **UNVERIFIED** and measure it yourself at ~200 pages during Phase 1.

**If it fails:** Eleventy 3.1.6 (v4 still alpha.10). It is slower to develop in and has no islands story, but it processes 10,000+ pages in minutes and has near-zero breaking-change risk. **Reject Next.js 16.3.5** — static export mode is a second-class citizen in a framework now organised entirely around a server, and it ships ~460KB JS baseline against Astro's ~9KB, which directly violates your no-JS readability constraint. **Reject SvelteKit** — 2.70.3 stable with 3.0.0-next.27 in flight; wrong moment, and a smaller island ecosystem. **Reject Docusaurus** — it is a docs site, not a faceted catalogue.

---

## 2. ATLAS / LARGE GRAPH — primary **sigma.js 3.0.3**, fallback **cosmos.gl 3.4.1**

**Verified inventory (all MIT):**

| Library | Latest | Published | Bundle (min) | Notes |
|---|---|---|---|---|
| `sigma` | **3.0.3** | 2026-04-30 | 183 KB min (+ `graphology` 0.26.0) | v4.0.0-**beta.6** released 2026-09-16; repo very active, only 12 open issues |
| `@cosmos.gl/graph` | **3.4.1** | 2026-08-13 | **685 KB min** / 410 KB ESM | OpenJS Foundation incubating since 2025-05-14; luma.gl/WebGL2; 1,274 stars |
| `deck.gl` | 9.4.0 | 2026-09-05 | 6.5 MB unpacked metapackage | WebGPU still **experimental, explicitly not production-recommended**; v10 tracker open |
| `pixi.js` | 8.21.0 | 2026-09-17 | 75 MB unpacked | General renderer, no graph semantics |
| `force-graph` | 1.51.4 | 2026-04-16 | — | Canvas 2D + d3-force; you don't want client-side force |
| `@antv/g6` | 5.1.1 | 2026-05-08 | 7.6 MB unpacked | Heavy, China-centric docs |
| `regl` | 2.1.1 | **2024-11-12** | — | **~22 months stale. Drop it from the plan.** |
| ChartGPU / GraphGPU (WebGPU) | — | 2026 | — | Brand new, tiny communities. **Do not bet on these.** |

**Recommendation: sigma.js 3.0.3 + graphology 0.26.0.**

**Decisive reason:** Three things matter at 1,500 nodes and sigma is the only library that has all three: (a) **built-in WebGL label rendering with collision avoidance** — an Atlas of named benchmarks is useless without labels, and cosmos.gl has *no* label API at all (I grepped its full `config.d.ts`: zero matches for "label"); (b) **`nodeReducer`/`edgeReducer`**, which is exactly the right mechanism for "filter dims non-matching nodes" without mutating the graph; (c) it is **~4x smaller** than cosmos.gl. Static positions are trivial — set `x`/`y` attributes on graphology nodes from `atlas.json`; sigma runs no layout of its own.

**Reality check the draft gets slightly wrong:** at 1,500 nodes, plain Canvas 2D would also hold 60fps. WebGL is insurance for 10k+, not a requirement at 1.5k. Don't let "we need WebGL" justify a heavy dependency.

**Main risk:** sigma v4 is in beta (4.0.0-beta.6, 2026-09-16) and will land during your build. Pin `sigma@3.0.3` and treat v4 as a deliberate later migration. Secondary risk: sigma's hit-testing is CPU-side — irrelevant at 1,500 nodes, relevant above ~50k.

**Fallback: cosmos.gl 3.4.1** — and it is a *good* fallback because its API is almost purpose-built for your V1 spec. Verified from its published type definitions:
- `enableSimulation: false` + `setPointPositions(Float32Array)` → precomputed layout, no client force sim. (Note: `setPointPositions()` auto-pauses the simulation and leaves it paused.)
- `onPointMouseOver` / `onPointMouseOut` / `onClick` with GPU hit-testing; `renderHoveredPointRing`.
- **`findPointsInPolygon(path)` and `findPointsInRect(rect)`** — your "lasso-select to send a group to the comparison workbench" for free.
- **`pointGreyoutColor` / `pointGreyoutOpacity` / `highlightedPointIndices`** — your filter-dimming interaction, native.
- `setPointClusters()` + `setClusterPositions()` — domain clustering as a layout constraint.
- `spaceToScreenPosition()` → you build the label layer as HTML overlay yourself.
- `zoomToPointByIndex`, `fitViewByPointIndices`, `setPinnedPoints`, `pointOcclusionCulling`.

Switch to cosmos.gl if you exceed ~20k nodes or decide lasso + cluster-forces are worth 500KB and hand-rolled labels.

**Reject deck.gl** for this: it is a geospatial framework whose value is layers, coordinate systems and basemap integration you will never use, and its WebGPU path is explicitly not production-ready as of v9.4.

**Accessibility fallback (neither library provides this — you must build it):** server-render the Atlas contents in Astro as a real `<ul>`/`<table>` of benchmarks grouped by domain cluster, inside the canvas container. Replace it on hydration. That gives you: works with JS off, screen-reader navigable, crawlable, and it is the same markup your citability requirement already demands.

---

## 3. ATLAS LAYOUT / DIMENSIONALITY REDUCTION — the draft's "frozen" is not a mechanism

The draft says positions are "precomputed at build time via UMAP over one-hot facet vectors **and frozen so the map is stable across builds**." *Frozen* is a wish, not an algorithm. A naive UMAP refit with one new benchmark added will rotate, reflect and topologically rearrange the entire map. This is the single most under-specified engineering decision in the draft.

**Verified library facts**
- `umap-learn` **0.5.12** (2026-04-08). `init` **explicitly accepts "A numpy array of initial embedding positions."** `transform_seed` defaults to 42. `random_state` gives bit-identical reruns but **disables multithreading** ("significantly" slower). Binary metrics available: `jaccard`, `dice`, `hamming`, `russelrao`, `rogerstanimoto`, `sokalsneath`, `yule`. **No `update()` method** — `transform()` is the only out-of-sample path. Setting `precomputed_knn` **disables `transform()` entirely**.
- `pacmap` **0.9.1** (2026-03-02). Has `random_state` (int, sets a numba global), `fit(X, init=array)`, `transform(X, basis=...)`, module-level `save()`/`load()`. Valid distances: `angular, euclidean, manhattan, hamming, dot` — **no Jaccard**. `apply_pca=True` by default (PCA to 100 dims first). **Disqualifying:** its own `transform()` docstring warns *"the `transform` method will treat the input as an additional dataset, which means the same point could be mapped into a different place."*
- `openTSNE` 1.0.4 (2025-10-27), `trimap` 1.2.0 (2026-08-20), `scikit-learn` 1.9.1 (requires Python **>=3.11**), `prince` 0.21.0 (MCA/FAMD, 2026-09-17).
- `AlignedUMAP` exists in umap-learn: `fit(list_of_datasets, relations=[...])` with `alignment_regularisation` and `alignment_window_size`. Designed for exactly this (successive overlapping slices). **Known bug: issue #575, "AlignedUMAP ignores n_components parameter."**

**Recommendation — a three-layer construction. Do not use a single algorithm.**

**Layer 1 — Freeze the input space, not the output.** Fit `TruncatedSVD(n_components=48, random_state=0)` **once** on a reference corpus, and commit `atlas/basis_v1.npz` (the components matrix + column means + the exact facet-column ordering) to git as a versioned artifact. Every build projects *every* item — old and new — through that same frozen basis: `Z = (X - mean) @ V`. This makes the 48-d space a pure deterministic function of a benchmark's facets. A new benchmark cannot move an existing one's input coordinates, ever. (Cheap sanity option: use `prince` MCA instead of SVD — it is the statistically correct linear method for multi-hot categorical data.)

**Layer 2 — Warm-start UMAP from the previous build's output.** This is the part the draft is missing and it is directly supported:
```python
init = np.empty((n, 2))
init[known_mask] = prev_coords[known_ids]          # last build's positions
init[new_mask]   = knn_centroid(Z[new_mask], Z[known_mask], prev_coords, k=8)
reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.12,
                    metric="euclidean",            # on the frozen SVD space
                    init=init, n_epochs=120,       # short — you are refining, not discovering
                    random_state=42, transform_seed=42)
coords = reducer.fit_transform(Z)
```
Short `n_epochs` on a good init means existing points barely move. Use `metric="jaccard"` directly on the raw binary facet matrix only if you skip Layer 1 — but then you lose the frozen basis, so prefer SVD + euclidean.

**Layer 3 — Procrustes-align the output, then gate on drift.** `scipy.linalg.orthogonal_procrustes` on the shared points removes residual rotation/reflection/scale. Then compute median per-point displacement vs the previous build and **fail the build if it exceeds a threshold** (e.g. 2% of the bounding-box diagonal). That converts "the map silently reshuffled" from an invisible trust failure into a CI error. Carry an explicit `atlas_layout_version` in the data; bumping it is a deliberate, announced, changelog-worthy event, exactly like a schema migration.

**Why not the alternatives:**
- **Fit-once + `transform()` forever:** superficially the obvious answer, and wrong at your timescale. The manifold never learns the new material, UMAP's `transform()` is known to over-centralise new points, and the pickled reducer binds you to a frozen `umap-learn` + `numba` + `sklearn` triple for years. It also silently breaks if anyone ever sets `precomputed_knn`.
- **PaCMAP:** better global structure than UMAP on paper, but its own docs disclaim out-of-sample stability. Disqualified by your requirement.
- **t-SNE:** no meaningful global structure, no out-of-sample map. Disqualified.
- **AlignedUMAP:** the right shape of idea, but it fits all slices jointly (cost grows every build), the `relations` bookkeeping is real work, and issue #575 is open. Keep as fallback if warm-start drift proves unacceptable.
- **Parametric UMAP:** gives a true out-of-sample function `f(x)→2D`, genuinely stable by construction — but pulls TensorFlow/Keras into CI. Not worth it for 1,500 points and two part-time people.

**Non-obvious alternative worth one afternoon of prototyping:** for a *catalogue*, a deterministic hierarchical layout (circle-pack or squarified treemap keyed on domain → subdomain → capability) is 100% stable by construction, needs no ML, no pinned numba, no drift gate, and is often more legible than a UMAP blob. Prototype both on ~200 real records and pick with your eyes. The draft's own stated failure mode — "a pretty hairball" — is much more likely with UMAP on sparse one-hot vectors than the plan assumes, because one-hot facet data has weak local neighbourhood structure for UMAP to exploit.

**Pin exactly** `umap-learn==0.5.12`, `numba`, `scikit-learn==1.9.1`, `numpy` in a lockfile, and set `PYTHONHASHSEED=0` plus a fixed input row order. UMAP is reproducible *only* with `random_state` set, and its docs do **not** guarantee cross-machine bit-identity — mark that **UNVERIFIED** and make CI the single authority that regenerates `atlas.json`.

---

## 4. CLIENT-SIDE SEMANTIC SEARCH — **static embeddings beat transformer-in-browser here, decisively**

### The measured facts that settle this

**Brute-force cosine, measured in this session (Node v24.11.0 / V8, same engine as Chrome):**

| N × dims | query time | sort | f32 bytes | int8 bytes |
|---|---|---|---|---|
| **1,500 × 384** | **0.75 ms** | 0.03 ms | 2.30 MB | 0.58 MB |
| 1,500 × 256 | 0.61 ms | 0.03 ms | 1.54 MB | 0.38 MB |
| 1,500 × 768 | 2.35 ms | 0.04 ms | 4.61 MB | 1.15 MB |
| 5,000 × 384 | 6.12 ms | 0.22 ms | 7.68 MB | 1.92 MB |
| 20,000 × 384 | 38.3 ms | 1.97 ms | 30.7 MB | 7.68 MB |

**Conclusion: ship no vector index at all.** A flat `Float32Array` + a hand-written dot-product loop answers a query in under 1ms at your size. An ANN index only starts to earn its keep past ~50k vectors.

Note a counterintuitive measured result: a naive Int8Array dot loop was **slower** (2.0ms at 1,500×384) than f32, because V8 does not auto-vectorise and the int→float conversions cost more than they save. **So: quantise to int8 for *transport* (0.58MB on the wire, ~0.4MB brotli), then dequantise once into a Float32Array at load.**

**Every in-browser vector-search library I checked is dead or unproven:**
- `voy-search` 0.6.3 — last publish **2023-09-20**
- `hnswlib-wasm` 0.8.2 — last publish **2023-07-08**
- `client-vector-search` 0.2.0 — last publish **2023-11-14**
- `altor-vec`, `VecLite`, `vectorlite-wasm` — 2026 arrivals, negligible adoption. **Do not take the dependency.**
- `@orama/orama` 3.1.18 — last publish 2025-12-19; repo active, but it is a full search engine you do not need.

### Embedding model — hard sizes pulled from the Hugging Face API

| Model | int8/q4 ONNX | tokenizer | dims |
|---|---|---|---|
| `Xenova/all-MiniLM-L6-v2` | **22.97 MB** | 0.71 MB | 384 |
| `Xenova/bge-small-en-v1.5` | 33.76 MB | 0.71 MB | 384 |
| `Xenova/gte-small` | 33.76 MB | 0.71 MB | 384 |
| `Snowflake/snowflake-arctic-embed-xs` | 22.97 MB | 0.71 MB | 384 |
| `onnx-community/embeddinggemma-300m-ONNX` | **175 MB** (q4f16) | **20.3 MB** | 768 (MRL→512/256/128) |
| `minishlab/potion-base-8M` | 30.2 MB fp32 → **~7.6 MB int8** | 0.68 MB | **256** |
| `minishlab/potion-base-4M` | 15.6 MB fp32 → **~3.9 MB int8** | 0.68 MB | 128 |

**EmbeddingGemma is disqualified.** 175 MB + a 20 MB tokenizer to answer a search box is indefensible, regardless of its MTEB crown.

Transformer-in-browser latency: MiniLM via transformers.js WASM measures **~8–12 ms per embedding on an M2 MacBook Air** — fine *after* load. The cost is the cold start: ~23 MB download plus ONNX Runtime Web init. `@huggingface/transformers` is **4.3.0** (2026-09-16); v4 made WebGPU the default backend where available and claims BERT embedding models up to 4x faster. But WebGPU is **~82–85% global support** — Safari 26+ yes, **Firefox ships it disabled by default and, as of Sept 2026, only on Windows and Apple Silicon**. So you need the WASM path anyway.

### RECOMMENDED HYBRID — three tiers, and tier 2 is the interesting one

**Tier 1 — Lexical, always on: Pagefind 1.5.2** (2026-04-12; repo pushed 2026-09-16, 5,470 stars, healthy). Use `astro-pagefind@2.0.1` (2026-07-03).

The under-used feature the draft should exploit: **Pagefind's Node API `addCustomRecord()`** takes `url`, `content`, `language`, plus `meta`, **`filters`** (key → string[]) and **`sort`**. That means you index your *validated YAML metadata directly* rather than scraping rendered HTML — your facets become Pagefind filters for free, and search never drifts from the data model. `index.getFiles()` returns the bundle in memory; `index.writeFiles()` writes to disk.

**Tier 2 — Semantic, opt-in: model2vec static embeddings, run in plain JS. No ONNX runtime.**

A model2vec model *is* an embedding matrix — encoding is tokenize → look up rows → mean-pool → normalise. There is no transformer to run. Verified: `minishlab/potion-base-8M` config is `{"model_type":"model2vec","hidden_dim":256,"tokenizer_name":"baai/bge-base-en-v1.5","normalize":true}`; 30,522 × 256 × 4B = 31.3 MB fp32, matching its published `model.safetensors`.

The missing piece just landed: **`@huggingface/tokenizers` 0.2.0** (2026-09-07) — pure JS/TS, **zero dependencies, 36 KB minified ESM**, with WordPiece + BertNormalizer (and BPE/Unigram). Verified from its published file listing and type tree.

So the whole query-time semantic stack is:

| Component | Size |
|---|---|
| `@huggingface/tokenizers` min.mjs | **36 KB** |
| `tokenizer.json` (bge-base WordPiece) | 0.68 MB |
| potion-base-8M matrix, int8, **vocab-pruned** to ~12k rows | **~3 MB** |
| 1,500 doc vectors @ 256d int8 | **0.38 MB** |
| **Total** | **~4 MB, ~1–2 ms/query, no WASM, no WebGPU, works in every browser** |

Prune the vocabulary to the top ~12k WordPiece tokens ∪ every token occurring in your corpus, map the rest to `[UNK]`. Compute the *document* embeddings in Python at build time with the full unpruned model (best quality); only the query-side matrix is pruned, and short queries degrade gracefully.

Quality cost, from the official model card: `potion-base-8M` reaches **91.96% of all-MiniLM-L6-v2's MTEB average** (51.08 vs ~55.6); `potion-retrieval-32M` scores **35.06 MTEB Retrieval vs all-MiniLM-L6-v2's 42.92** (81.7%). For "find me benchmarks about protein folding" over 1,500 curated items where lexical search runs alongside, that gap is invisible.

**Risk flag:** transformers.js maintainer xenova confirmed on **2026-04-12** (issue #970, closed) that "model2vec models that are **exported in the right way** are compatible with transformers.js." The official `minishlab/potion-*` repos carry `onnx` tags but **none carry the `transformers.js` tag**, so this is *not yet turnkey* — you will either re-export or, better, write the ~150-line JS encoder directly against `@huggingface/tokenizers` and a `Float32Array`. Mark the turnkey path **UNVERIFIED**.

**Tier 3 — Fallback if Tier 2 quality disappoints:** `@huggingface/transformers@4.3.0` + `Xenova/all-MiniLM-L6-v2` int8 (23 MB), loaded **lazily on first semantic query only**, cached in IndexedDB, behind an explicit "Enable smart search (23 MB, one time)" affordance. Never on page load.

**UX rule that makes the hybrid work:** Pagefind answers instantly on every keystroke. The semantic tier loads in the background and, once ready, *appends* a "related benchmarks you didn't type the words for" block. Semantic search is never on the critical path to a first result.

---

## 5. CHARTS — **the draft's "Observable Plot or visx" is the wrong call**

**Verified maintenance state:**
- `@observablehq/plot` **0.6.17, published 2025-02-14 — 19 months with no npm release.** The repo is not dead (last commit 2026-09-01; commits in April and May 2026) but it carries **349 open issues**. You would be pinned to an 0.6.x with 19 months of unreleased fixes. Its `pointer` transform is also documented as **incompatible with SVG serialisation**, i.e. it breaks the SSR path you need.
- `@visx/visx` **4.0.0** (2026-06-11) — first release since v3.12.0 in Nov 2024. Bursty maintenance. And visx is *low-level React primitives*: parallel coordinates, a theme river and a domain×capability matrix are all things **you build from scratch**.
- `echarts` **6.1.0** (2026-05-19), repo pushed 2026-09-16, 67,342 stars. Actively maintained.
- `vega-lite` 6.4.3 (2026-04-24) — alive but **820 open issues**, and its runtime is heavy.
- `d3` **7.9.0, published 2024-03-12** — the meta-package is 2.5 years stale (individual `d3-*` modules still move).

**I pulled ECharts 6.1.0's actual tree-shakeable export list.** It ships, as separately importable modules:

`HeatmapChart` · `ParallelChart` + `ParallelComponent` · `ThemeRiverChart` · `GraphChart` · `CustomChart` · `ScatterChart` · `LineChart` · `ChordChart` · **`MatrixComponent`** (new coordinate system in ECharts 6.0) · **`AriaComponent`** · **`BrushComponent`** · `DataZoomComponent` · `VisualMapComponent` · `TimelineComponent` · `ThumbnailComponent`

That is **four of your four required chart types built in** — heatmap (V2 Coverage Map), parallel coordinates (V5 Workbench), theme river (V4 Frontier Timeline), plus `MatrixComponent` which is a better fit for the domain×capability matrix than a bare heatmap because it lets you nest other chart types inside cells. `BrushComponent` gives you V4's "brush a time range to filter every other view" natively. Tree-shaken imports land around **80–100 KB** vs ~900 KB for a naive full import.

**Recommendation — split the problem, do not pick one library:**

**(a) Sparkline small-multiples (V3 Saturation Wall) — hand-rolled inline SVG generated at build time. Do NOT use a chart library here.** Hundreds of ECharts instances on one page is a performance disaster. A SOTA sparkline with a baseline rule and headroom shading is ~30 lines of `<path d="M...">` string generation in your Python build step. Result: zero JS, no-JS readable, instantly printable, accessible, and it satisfies your citability constraint by construction. This is the single biggest simplification available in the charting plan.

**(b) Heatmap, parallel coordinates, theme river — `echarts@6.1.0`**, tree-shaken, `SVGRenderer`, in a `client:visible` island. Use `ssr: true` + `renderToSVGString()` at build time to emit a static SVG for the no-JS/crawler path, then hydrate over it.

**(c) Per-benchmark trajectory chart on detail pages — hand-rolled SVG again**, same generator as (a). Detail pages must stay JS-free.

**Main risk:** ECharts' `aria` support is known to be buggy under SSR (issue #19191 reported SVG ARIA not working with SSR in 5.4.3; **I could not verify whether this is fixed in 6.1.0 — UNVERIFIED**). This does not matter if you follow the accessibility rule below.

**Accessible table fallback — make it a build-time invariant, not a component.** Every chart is generated from a `{rows, columns, caption, units}` object. The build emits **both** the chart and a `<table>` from that same object, and the table is the DOM element that exists without JS. Never rely on `aria-label` on an SVG, and never rely on ECharts' `aria` option. This also means your charts and your citable data can never disagree.

**Dark mode:** ECharts needs an explicit theme object (`echarts.registerTheme`) and a re-`init` on `prefers-color-scheme` change — it does not follow CSS variables. Your hand-rolled SVG *can* use `currentColor` and CSS custom properties, which is another point for doing sparklines by hand.

---

## 6. BUILD PIPELINE — Pydantic is right; the TypeScript leg and the DB artifact are both wrong

**Schema source of truth — keep Pydantic.** `pydantic` **2.13.5** (2026-08-28). `model_json_schema()` emits **JSON Schema Draft 2020-12** by default. Your cross-field validators (the human-baseline rule, the judge-model rule, the ID-reuse ledger) genuinely need imperative code, and a Python-native canonical schema matches your AI/ML contributor pool. Correct call, keep it.

**Python version: use 3.12, not 3.13.** `scikit-learn` 1.9.1 requires >=3.11; `duckdb` >=3.10; `pyarrow` 25.0.1 >=3.10; `datamodel-code-generator` 0.82.0 >=3.10. The binding constraint is the numba/umap stack, which is always the last to support a new CPython. 3.12 is the safe floor. **Pin everything in a lockfile — your Atlas layout's reproducibility depends on it.**

**JSON Schema → TypeScript — the draft's tool choice is simply wrong.**
- **`datamodel-code-generator` 0.82.0 does not emit TypeScript.** It generates Pydantic v2 models, dataclasses, TypedDict and msgspec.Struct — Python only. It is the right tool for the *inbound* direction (third-party JSON Schema → Pydantic), not for typing your frontend.
- **`json-schema-to-zod` is archived.** Repo archived **2026-06-30**, maintainer announced end of maintenance March 2026. Its last publish was 2.8.1 (2026-04-01). **Do not build on it**, even though Astro 7's Zod 4 makes it look like the natural fit.
- **Use `json-schema-to-typescript@16.0.0`** (2026-08-28; repo pushed 2026-09-07, 3,348 stars, active). Types only, no runtime validation — **which is correct**, because Pydantic already validated everything at build time. Adding Zod to the site would mean maintaining a second schema definition that can drift from the canonical one. Alternative if you need runtime converters: `quicktype@26.0.0` (2026-07-20, active) — but its output is verbose.
- **Corollary:** leave the Astro collection `schema` **undefined** (it is optional) and type the collection with the generated interface. One schema, one validator, one source of truth.

**Query artifact — drop SQLite *and* DuckDB. Both are unjustified at your data size.**

I generated a realistic 1,500-record corpus (40-ish fields, ~90-word descriptions, 3 sources each, 30 facet flags) and measured:

| Artifact | raw | gzip | brotli |
|---|---|---|---|
| **Full 1,500-record corpus JSON** | 2.76 MB | 0.77 MB | **0.52 MB** |
| **Slim facet index** (id, name, domains, capabilities, year, lifecycle) | 198 KB | **36 KB** | — |

(Real prose compresses better than my synthetic vocabulary, so treat 0.52 MB as an upper bound — expect ~0.35–0.45 MB brotli.)

Against that, the WASM engine sizes I measured from jsDelivr:

| Engine | WASM payload |
|---|---|
| `sql.js` 1.14.2 | **0.66 MB** (`sql-wasm.wasm`) |
| `@sqlite.org/sqlite-wasm` 3.53.4-build1 | **0.87 MB** (`sqlite3.wasm`) |
| `@duckdb/duckdb-wasm` | **35.66 MB** (`duckdb-eh.wasm`), 40.62 MB MVP |

**DuckDB-WASM's engine is ~70x the size of your entire dataset.** It is also in a questionable release posture: the npm `latest` tag currently points at **`1.33.1-dev57.0`, a dev build**, and the last tagged GitHub release was v1.33.0 in Dec 2025. Reject outright.

**Recommendation:**
- **Ship two JSON files, no database, no sharding.** `facets.json` (~36 KB gz) loads with the filter UI and drives instant client-side faceting over 1,500 rows. `corpus.json` (~0.5 MB br) loads lazily on entry to the Comparison Workbench. The draft's "sharded JSON bundles" solves a problem you do not have — a 0.5 MB brotli file is one HTTP request on a CDN.
- **Keep SQLite as a build-time-only artifact**, generated by Python, committed or released as a downloadable. It is enormously useful for your own analytics queries (V7 Gap Finder scoring, coverage stats) and as a **citable data release** — a `.sqlite` at a commit hash alongside the YAML is a genuinely good artefact for your "infrastructure, not a site" differentiator. It just never ships to the browser.
- **If you ever do need in-browser SQL** (say, a public query console), use `@sqlite.org/sqlite-wasm` (0.87 MB, official SQLite project, published 2026-09-08) — **not** `sql.js-httpvfs`, whose last publish was **2022-09-23**.

---

## 7. HOSTING & CI — **Cloudflare, but Workers with static assets, not Pages**

**Verified free-tier numbers (2026-09-17):**

| | Cloudflare **Workers** (static assets) | Cloudflare **Pages** | GitHub Pages | Netlify | Vercel Hobby |
|---|---|---|---|---|---|
| Static bandwidth | **unlimited** | unlimited | 100 GB/mo (soft) | 100 GB/mo | 100 GB/mo |
| Static asset requests | **free & unlimited, not billed** | unlimited | — | — | 1M edge req |
| Build minutes | **3,000/mo** | 500 **builds**/mo | 10 builds/hr (soft; N/A with custom Actions workflow) | 300/mo | 6,000/mo |
| Concurrent builds | 1 | 1 | — | — | 1 |
| Build timeout | 20 min | 20 min | — | — | — |
| File count cap | **20,000/version** | 20,000/site | — | — | — |
| Max file size | 25 MiB | 25 MiB | 1 GB site total | — | — |
| PR previews | yes | yes (unlimited concurrent) | no | yes | yes |
| Serverless later | **same Worker, no re-platform** | Pages Functions | **none** | Functions (125k inv) | 1M inv |
| **Commercial use on free tier** | yes | yes | yes | **yes** | **prohibited** |

**Recommendation: Cloudflare Workers with static assets, built in GitHub Actions.**

**Decisive reasons, in order:**
1. **Static asset requests are explicitly "free and unlimited" and do not count against the Workers request limit** — only requests that invoke your Worker *script* are billed. That is verbatim from Cloudflare's billing docs. An index that gets linked from Hacker News cannot generate a bill.
2. **Cloudflare's own guidance is now that new projects start on Workers, not Pages.** Workers reached feature parity with Pages for static assets, SSR and custom domains, and all new capability (Durable Objects, Cron Triggers, Queues, gradual deployments, Tail Workers, the Vite plugin) lands on Workers only. Pages remains supported with no deadline, but it is where the platform stopped investing. **The draft's "Cloudflare Pages or GitHub Pages" is the wrong pair.**
3. **Your future LLM-backed feature needs zero re-platforming.** Add a route to the same Worker; free tier gives 100,000 requests/day, 10 ms CPU per request, 50 subrequests/request, 128 MB memory. *Caveat:* if you use `run_worker_first`, matching requests consume free-tier quota and return **429** on exhaustion rather than falling back to static — so scope it to `/api/*` only.
4. **GitHub Pages is disqualified** by three things: 1 GB site cap, 100 GB/mo bandwidth, and **no serverless function path at all**, which would force exactly the re-platform you said you want to avoid.
5. **Vercel Hobby is disqualified: commercial use is prohibited.** If this index ever takes sponsorship, grants or institutional funding, you are in breach. Netlify's free tier permits commercial use but has moved to credits-based pricing that buys less than it did (bandwidth 20 credits/GB, up from 10).

**Build in GitHub Actions, deploy with `wrangler deploy`.** **GitHub Actions is free with unlimited minutes for public repositories on standard runners** (private repos: 2,000 min/mo, 500 MB artifacts, 10 GB cache). Since your repo is public by premise, your CI is free and uncapped, and you never touch Cloudflare's 3,000 build minutes. This also keeps the Python build (Pydantic validation, UMAP layout, Pagefind indexing) in an environment you fully control, which Cloudflare's build image would fight you on.

**⚠ Scaling landmine you should record now.** Cloudflare caps a version at **20,000 files**. **Pagefind creates one `.pf_fragment` file per indexed page** (typically 1–10 KB each) plus `.pf_index` chunks (~40 KB each), and **Pagefind 1.5.2 has no config option to group fragments** — I checked the full CLI option list (`site, serve, output_subdir, output_path, root_selector, exclude_selectors, include_characters, glob, force_language, keep_index_url, write_playground, verbose, quiet, silent, logfile`); fragment bundling exists only as an unmerged PR (#1020). So:
- At 1,500 benchmarks: ~1,500 HTML + ~1,500 fragments + ~30 index chunks + assets ≈ **3,100 files. Fine.**
- At **10,000 benchmarks: ~10,000 HTML + ~10,000 fragments + ~200 index ≈ 20,200 files — you hit the cap exactly.**

Mitigation when you get there: request a limit increase (Cloudflare has a form), or move to Pagefind's Node API with fewer, larger custom records, or track PR #1020.

---

## SUMMARY: WHAT I THINK THE DRAFT GETS WRONG

| # | Draft says | Verdict | Evidence |
|---|---|---|---|
| 1 | "Observable Plot or visx" | **Wrong.** Use **ECharts 6.1.0** for the four heavy charts + **hand-rolled build-time SVG** for sparklines. | Plot has had **no npm release since 2025-02-14** (19 months) with 349 open issues, and its `pointer` transform breaks SVG serialisation. visx 4.0.0 is low-level primitives — you'd hand-build parallel coords, theme river and the matrix. ECharts ships all four plus `MatrixComponent`, `BrushComponent`, `AriaComponent`, tree-shaken to ~80–100 KB. |
| 2 | "Cloudflare Pages **or** GitHub Pages" | **Wrong pair.** Use **Cloudflare Workers + static assets**. | Cloudflare's own guidance directs new projects to Workers; static asset requests are "free and unlimited" and unbilled; GitHub Pages has no serverless path (1 GB / 100 GB caps). |
| 3 | "TypeScript types generated from JSON Schema" (plan implies datamodel-code-generator) | **Wrong tool.** `datamodel-code-generator` **emits Python only**. Use **`json-schema-to-typescript@16.0.0`**. | Verified on its own README/docs. Also: **`json-schema-to-zod` was archived 2026-06-30** — the otherwise-obvious Zod path is dead. |
| 4 | "sharded JSON bundles + SQLite as build artifacts [in the browser]" | **Over-engineered.** Ship **two unsharded JSON files**; keep SQLite build-time-only. | Measured: full corpus = 2.76 MB raw / **0.52 MB brotli**; slim facet index = **36 KB gz**. DuckDB-WASM's engine alone is **35.66 MB**, ~70x the dataset, and npm `latest` is a **dev build**. |
| 5 | "UMAP … frozen so the map is stable across builds" | **Under-specified — the hardest unsolved thing in the plan.** "Frozen" is not a mechanism. Needs frozen SVD basis + `init=`-array warm start + Procrustes + a CI drift gate. | `umap.UMAP(init=<ndarray>)` is explicitly supported; PaCMAP's own docstring disclaims out-of-sample stability; AlignedUMAP has open bug #575. |
| 6 | "sigma.js, deck.gl, **or regl**" | **Narrow it.** **sigma.js 3.0.3** primary, **cosmos.gl 3.4.1** fallback. | `regl` last published **2024-11-12** and is a WebGL abstraction, not a graph library. deck.gl is a 6.5 MB geospatial framework with WebGPU still explicitly non-production. cosmos.gl has **no label API at all** (verified by grepping its type defs) — disqualifying for a *primary* choice. |
| 7 | "Pagefind" (as the whole search story) | **Incomplete, not wrong.** Add a **static-embedding semantic tier** and use Pagefind's `addCustomRecord()` to index YAML directly. | Measured: 1,500×384 brute-force cosine = **0.75 ms** — no vector index needed, and every in-browser vector lib I checked was last published in **2023**. |
| 8 | "Astro" (unversioned) | **Stale by two majors.** Astro is at **7.3.3**. | Node ≥22.12 now required; new Rust compiler rejects unclosed tags; **`compressHTML` now defaults to `'jsx'` and will eat whitespace between your inline facet chips** — set it explicitly. |
| 9 | "Python 3.12/3.13" | **Use 3.12.** | `scikit-learn` 1.9.1 requires ≥3.11; the numba/umap stack lags new CPython, and your layout reproducibility depends on pinning it. |

**Flagged UNVERIFIED:** (a) real-world Astro build time in the 1,000–2,000 page range — no published benchmark found, measure at ~200 pages in Phase 1; (b) UMAP bit-identical reproducibility *across machines* — docs guarantee it only across runs, so make CI the sole authority for `atlas.json`; (c) whether ECharts' SSR+ARIA bug (#19191) is fixed in 6.1.0 — irrelevant if you follow the build-both-chart-and-table rule; (d) turnkey model2vec support in transformers.js — the maintainer confirmed compatibility 2026-04-12 for correctly-exported models, but no official `potion-*` repo carries a `transformers.js` tag, so budget for writing the ~150-line JS encoder yourself.