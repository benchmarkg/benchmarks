# 10 -- Visualization and Interaction

## Design stance

The index is a map of a territory nobody has mapped in one piece. The visual design should make the
*shape* of the field legible before any individual number is read: where benchmarks cluster, where
they are absent, what is solved, what is moving, and who is doing the measuring.

Three rules govern every view. They are not style preferences; they are the product.

1. **Show provenance at the point of the number.** Verification level and condition completeness
   travel with every value, always. There is no view anywhere in the site where a bare number
   appears alone.
2. **Refuse to rank what is not comparable.** When a user assembles a view spanning multiple
   `comparability_key` values, the UI shows the difference rather than a silent ordering. Refusal is
   the signature behaviour of this product ([01-landscape-and-positioning.md](01-landscape-and-positioning.md)),
   and it has to be visible in the interface, not just stated in an about page.
3. **Absence renders as strongly as presence.** Empty cells, missing baselines, unknown conditions
   and dead leaderboards are drawn, not omitted.

A fourth rule follows from the mortality analysis in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md): **every view must survive the
project.** Stanford CRFM's Ecosystem Graphs is the closest architectural precedent to this plan --
a structured catalogue as files in git with a static site -- and its last push was 2025-01-24, with
no licence, 274 stars and zero open issues. It is still cited as a live data source by 2025-26
research. If a view only works as a running service, it dies when we do. Every view here therefore
has a defined degraded form that is a static file: a table, a list, or an SVG.

Accessibility and dark mode are not a later pass. Colour is never the sole carrier of meaning --
verification level gets a shape and a badge as well as a hue -- and **every chart is generated from
a `{rows, columns, caption, units}` object from which the build emits both the chart and a
`<table>`**. The table is the element that exists without JavaScript. This is a build-time
invariant, not a component convention, which means the charts and the citable data cannot disagree.
Visual language, colour tokens, type scale, badge geometry and the dark-mode token strategy live in
[09-design-system.md](09-design-system.md) and are not restated here.

---

## Technology decisions that shape every view

These were measured or read off a registry, not chosen by taste. **Every version number, release
date, bundle size, open-issue count and "last published" date in this document was observed by the
technology reconnaissance on 2026-09-17 and is expected to have moved.** They are reasons for a
decision, not facts the design depends on; re-verify each against its registry when the lockfile is
written ([14-roadmap.md](14-roadmap.md) §"Version pins and third-party facts: as-of date" owns the
as-of rule for the whole plan). Where a figure here is a recon estimate rather than an observation
-- the ~80--100 KB tree-shaken ECharts bundle is the one that matters -- it is marked at use. The
load-bearing conclusions are:

| Decision | Choice | Why | Main risk |
| --- | --- | --- | --- |
| Heavy interactive charts | **ECharts 6.1.0** (2026-05-19), tree-shaken, `SVGRenderer` | Ships `HeatmapChart`, `MatrixComponent`, `ParallelChart`+`ParallelComponent`, `GraphChart`, `CustomChart`, `BrushComponent`, `DataZoomComponent`, `VisualMapComponent`, `AriaComponent` as separately importable modules -- four of our four required chart types are built in. Tree-shaken imports land at ~80--100 KB against ~900 KB for a naive full import *(recon estimate from module sizes, 2026-09-17; [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.4 owns the figure and measures the real tree-shaken bundle in Phase 2)*. `ThemeRiverChart` and `ChordChart` also ship and were in an earlier draft's import set; both are **available but unused** -- V4's domain underlay and V9's E4 were rewritten because a nineteen-category colour encoding is unreadable at any palette (see V4 and V9/E4 below). | Needs an explicit `echarts.registerTheme` object and a re-`init` on `prefers-color-scheme` change; it does not follow CSS custom properties. ECharts' SSR+ARIA handling had a known bug (#19191 in 5.4.3); whether it is fixed in 6.1.0 is a Phase-0 check owned by [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.4 and is not restated as an open item here, though the chart-plus-table invariant makes it moot either way. |
| Sparklines and detail-page trajectories | **Hand-rolled inline SVG generated at build time in Python** | Hundreds of chart instances on one page is a performance disaster. A SOTA sparkline with a baseline rule and headroom shading is roughly thirty lines of `<path d="M...">` string generation. Zero JS, no-JS readable, printable, accessible, and it can use `currentColor` and CSS custom properties so dark mode is free. | None material. This is the single biggest simplification available in the charting plan. |
| Atlas graph renderer | **sigma.js 3.0.3** (2026-04-30, 183 KB min) + **graphology 0.26.0** | It is the only candidate with all three of: built-in WebGL label rendering with collision avoidance; `nodeReducer`/`edgeReducer` for filter-dimming without mutating the graph; and a small bundle. Static positions are trivial -- set `x`/`y` on graphology nodes from `atlas.json`; sigma runs no layout itself. | sigma v4.0.0-beta.6 landed 2026-09-16 and will go stable during our build. **Pin `sigma@3.0.3`** and treat v4 as a deliberate later migration. |
| Atlas fallback | **cosmos.gl 3.4.1** (685 KB min) | Its API is nearly purpose-built for V1: `enableSimulation: false` + `setPointPositions(Float32Array)`, `findPointsInPolygon()`, `pointGreyoutColor`/`highlightedPointIndices`, `setPointClusters()`. | **No label API at all** -- verified by grepping its published type definitions, zero matches for "label". That disqualifies it as primary for a map of *named* benchmarks. Switch only above ~20k nodes. |
| Rejected | Observable Plot, visx, deck.gl, regl, D3 meta-package | Plot's last npm release was **2025-02-14** -- nineteen months -- with 349 open issues, and its `pointer` transform is documented as incompatible with SVG serialisation, which breaks the SSR path we need. visx 4.0.0 is low-level React primitives: parallel coordinates, a theme river and a domain-capability matrix would all be hand-built. deck.gl is a 6.5 MB geospatial framework with WebGPU explicitly non-production. `regl` was last published **2024-11-12** and is a WebGL abstraction, not a graph library. | -- |

Two more constraints propagate into every view:

- **The whole dataset is two unsharded JSON files.** Measured at target scale: the full
  1,500-record corpus is 2.76 MB raw / 0.77 MB gzip / **0.52 MB brotli**, and a slim facet index
  (id, name, domains, capabilities, year, lifecycle) is 198 KB raw / **36 KB gzipped**. Real prose
  compresses better than the synthetic test vocabulary, so 0.52 MB is an upper bound; expect
  0.35--0.45 MB. `facets.json` loads with the filter UI; `corpus.json` loads lazily on entry to the
  workbench. No sharding, no database in the browser. DuckDB-WASM's engine alone is 35.66 MB,
  roughly seventy times the dataset.
- **Astro 7.3.3 changed `compressHTML` to default to `'jsx'`**, which removes whitespace between
  adjacent inline elements: `<span>a</span><em>b</em>` renders as `ab`. This will silently mangle
  facet-chip rows and inline provenance badges, which appear in nearly every view below. Set
  `compressHTML: true` explicitly on day one. See [08-infrastructure-and-build.md](08-infrastructure-and-build.md).

---

## V1 -- Benchmark Atlas *(hero view)*

**Purpose.** See the entire field at once and understand its structure without reading. This is the
view that answers "what is this site" in three seconds, and the view that makes cross-domain breadth
a visible fact rather than a claim in a paragraph.

**Form.** A 2D embedded map. Every benchmark family is a node.

- **Position**: clustered by primary domain, with intra-cluster placement from facet similarity
  (capability plus evaluation-method vectors), precomputed at build time and written to
  `atlas.json`. The client never runs a layout algorithm. In the packed layout -- the v1 default --
  containment is **presentation group -> domain family -> subdomain**, and group and family regions
  carry hairline outlines and permanent text labels rather than fills. Domain family is never
  encoded by hue in this document or anywhere else in the product; it is carried by position, by a
  label, by the group band and by a single emphasis token applied to one family at a time
  ([09-design-system.md](09-design-system.md) §4.2).
- **Node size**: adoption -- distinct systems with claims, log-scaled. A benchmark nobody reports
  on is a small dot regardless of how good its paper was.
- **Node colour**: **nodes are neutral** -- a `--c-ink-muted` outline -- and **saturation renders as
  fill level rather than hue**, so a benchmark at 90% headroom consumed looks 90% full. Colour
  appears on a node in exactly two cases: `contaminated` and `retracted` take `--c-alert`, and
  `saturated` takes the top stop of the headroom ramp, which is what a full fill already means. The
  remaining seven lifecycle terms (`proposed`, `active`, `mature`, `under-revision`, `superseded`,
  `deprecated`, `dormant`) are neutral and are read from the label, the filter and the detail panel.
  [02-taxonomy.md](02-taxonomy.md) §8 owns the ten-term vocabulary and this document does not restate
  it. This corrects an earlier draft of this document, which coloured every lifecycle term;
  [09-design-system.md](09-design-system.md) §4.3 colours three of ten on the stated grounds that
  ten coloured states means none of them is signal, and 09 wins on rendering questions.
  `under-revision` is deliberately in the neutral set even though it is a warning state: it is an
  instability flag rather than a stop sign, and the moment a fourth colour is spent on it the
  three that matter stop being legible. It is surfaced instead by the filter and by a detail-panel
  banner. Fill
  carries the second variable. Never two quantities in one ramp.
- **Edges**: lineage (`supersedes`, `extends`, `subset_of`, `decontaminates`) drawn solid; measured
  correlation drawn dashed, and *only* where `correlates_with.coefficient` has a source. An
  unsourced correlation edge is not drawn at all.

**Data consumed.** `atlas.json`: `{id, x, y, r, domain_primary, domain_group, lifecycle,
headroom_consumed, adoption_n, label, label_priority}` per node plus an edge list `{from, to, kind,
coefficient, source}`. `domain_group` is derived at build time from `taxonomy/domain_groups.yaml`,
is display-only, and is **forbidden in `facets.json`, `corpus.json` and every `derived/*.json`** --
it orders and bands this one view and never enters the filter grammar, a coverage percentage or a
gap claim. The domain reconnaissance puts the realistic ceiling at ~4,700 families across the
thirteen surveyed domains; [00-vision-and-scope.md](00-vision-and-scope.md) §8 owns the corpus-shape
figures this view is sized against, and this document does not restate them. The render is budgeted
against the 1,500-node measurement in [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
§4.1, which is the plan's upper working scale rather than a forecast; `atlas.json` at 1,500 nodes is
well under 200 KB uncompressed.

### Layout stability: the hardest engineering problem in this plan

The earlier draft said positions were "frozen so the map is stable across builds." *Frozen* is a
wish, not an algorithm. A naive UMAP refit with one benchmark added will rotate, reflect and
topologically rearrange the whole map, and a map that reshuffles between builds is worse than no
map -- it destroys the spatial memory that is the only reason a map beats a list.

The mechanism is three layers, and all three are required:

1. **Freeze the input space, not the output.** Fit `TruncatedSVD(n_components=48, random_state=0)`
   once on a reference corpus and commit `atlas/basis_v1.npz` (components matrix, column means, and
   the exact facet-column ordering) to git as a versioned artifact. Every build projects every item
   -- old and new -- through that same basis: `Z = (X - mean) @ V`. A new benchmark can then never
   move an existing benchmark's input coordinates. (`prince` 0.21.0 MCA is the statistically
   correct linear method for multi-hot categorical data and is a cheap sanity alternative.)
2. **Warm-start UMAP from the previous build's output.**

   ```python
   init = np.empty((n, 2))
   init[known_mask] = prev_coords[known_ids]                       # last build's positions
   init[new_mask]   = knn_centroid(Z[new_mask], Z[known_mask], prev_coords, k=8)
   reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.12,
                       metric="euclidean",        # on the frozen SVD space
                       init=init, n_epochs=120,   # short: refining, not discovering
                       random_state=42, transform_seed=42)
   coords = reducer.fit_transform(Z)
   ```

   `umap.UMAP(init=<ndarray>)` explicitly accepts "a numpy array of initial embedding positions".
   Short epochs on a good init mean existing points barely move.
3. **Procrustes-align the output, then gate on drift.** `scipy.linalg.orthogonal_procrustes` over
   the shared points removes residual rotation, reflection and scale. Then compute median per-point
   displacement against the previous build and **fail the build if it exceeds 2% of the bounding-box
   diagonal**. That turns "the map silently reshuffled" from an invisible trust failure into a CI
   error. A legitimate re-layout is not an error, so the gate needs an escape valve: `atlas.json`
   carries `layout_epoch: N`, and a commit that also adds an entry to `atlas_epoch.yaml` -- with a
   `reason` string and the triggering PR number -- re-bases the reference positions and clears the
   gate. Bumping the epoch is a deliberate, announced, changelog-worthy event, exactly like a schema
   migration, and only a human may write `atlas_epoch.yaml`. The ledger and its rendering rule are
   specified in [14-roadmap.md](14-roadmap.md) Phase 2 and carried in the artifact by
   [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2 and §5.3; this replaces the
   bare `atlas_layout_version` integer an earlier draft carried, which recorded that the map moved
   but never why.

Pin `umap-learn==0.5.12`, `scikit-learn==1.9.1`, numba and numpy in a lockfile on **Python 3.12**,
set `PYTHONHASHSEED=0` and fix the input row order. UMAP guarantees reproducibility across runs with
`random_state` set, but **its documentation does not guarantee bit-identity across machines
(unverified -- confirm before relying on this)**, so CI is the sole authority that regenerates
`atlas.json`; a developer's local run is a preview, never a commit.

Rejected alternatives, with reasons: fit-once-then-`transform()`-forever never learns new material,
over-centralises new points, and pickles us to a frozen umap/numba/sklearn triple for years (and
silently breaks if anyone sets `precomputed_knn`, which disables `transform()` entirely). PaCMAP
0.9.1 has better global structure on paper but **its own `transform()` docstring warns that "the
same point could be mapped into a different place"** -- disqualified by our stability requirement,
and it has no Jaccard metric. t-SNE has no meaningful global structure and no out-of-sample map.
`AlignedUMAP` is the right shape of idea but fits all slices jointly (cost grows every build) and
has open bug #575, "AlignedUMAP ignores n_components parameter"; keep it as the fallback if
warm-start drift proves unacceptable. Parametric UMAP gives a genuine out-of-sample function but
pulls TensorFlow into CI for 1,500 points.

### The legibility gate -- build both layouts, let the data pick

One-hot facet vectors have weak local neighbourhood structure for UMAP to exploit, so the archive's
own stated failure mode -- a pretty hairball -- is *more* likely here than the draft assumed. The
answer is not to tune until it looks nice. It is to make legibility a measured, gated property:

```
neighbourhood_purity  = median over nodes of (fraction of 10 nearest 2D neighbours
                        sharing the node's primary domain family)
domain_silhouette     = silhouette score of the 2D coords labelled by domain family

gate: neighbourhood_purity >= 0.60  AND  domain_silhouette >= 0.15
```

Both thresholds are provisional and must be calibrated against roughly 200 real records in Phase 1
before they are treated as binding. If the embedded layout fails the gate, **the build emits a
deterministic hierarchical layout instead** -- squarified treemap or circle packing keyed on
presentation group -> domain family -> subdomain, capability having no place in a containment chain
because it is a facet -- and records `atlas_layout_mode: packed` in the artifact. That
layout is 100% stable by construction, needs no ML, no pinned numba and no drift gate, and for a
*catalogue* it is frequently more legible than a UMAP blob. Prototype both on real records in Phase
1 and pick with your eyes plus the gate.

**Recommendation: ship the packed layout as the v1 default and let the embedded layout earn its
place by passing the gate.** Reason: the packed layout cannot fail, cannot drift, and cannot produce
a hairball, and the hero view is the worst place in the product to carry an unsolved engineering
risk. Risk of this choice: a treemap reads as a taxonomy diagram rather than a discovery surface,
and loses the "benchmarks that are not in the same domain but measure the same thing sit near each
other" insight, which is one of the more interesting things the facet data can show. That insight is
worth having, which is why the embedded layout stays in the plan rather than being cut.

The banding scheme strengthens the packed-first recommendation on a second, independent ground:
banding needs a deterministic containment structure and a UMAP embedding cannot guarantee one. If
the embedded layout later earns its place by passing the gate, the banding degrades to per-family
and per-group convex-hull outlines with the same labels and the same emphasis behaviour, and
nothing else changes -- which is itself an argument for a scheme whose only spatial requirement is
"same-family things are near each other", the property the gate already measures.

**Interactions.**

- **Hover** -> a tagline card: name, tagline (the one-sentence, sub-120-character field from
  [04-data-model.md](04-data-model.md)), primary domain, lifecycle, headroom, adoption count.
- **Click** -> opens the detail panel *beside* the map without losing map position. The panel is a
  summary; "open full page" navigates to the canonical URL.
- **Filter** by any facet. **Filtering never moves a node.** This corrects the archive's "smooth
  re-layout": positions are semantic, and moving them on filter destroys the spatial memory that
  justifies the view. Non-matching nodes drop to `--c-ink-faint` and lose their labels via sigma's
  `nodeReducer`; matching nodes stay at `--c-ink`, and the emphasised family's region outline takes
  `--c-emphasis`. The *camera* may animate to fit the matching set;
  the nodes do not move.
- **Lasso-select** -> send the selection to the Comparison Workbench (V5) or the Suite Builder
  (V10). sigma has no built-in lasso, so this is a canvas overlay plus a point-in-polygon test
  against `graphToViewport` coordinates -- roughly sixty lines. cosmos.gl would give it free via
  `findPointsInPolygon()`, which is the main argument for the fallback.
- **Search** highlights in place rather than navigating away.
- **Toggle "unsaturated only"** to see the live frontier; toggle "dead only" to see the graveyard
  (see V9 -- no catalogue currently marks benchmarks as dead).

**Implementation.** sigma.js 3.0.3 in a `client:visible` island. A reality check worth recording:
**at 1,500 nodes plain Canvas 2D would also hold 60 fps.** WebGL here is insurance for 10k+, not a
requirement. Do not let "we need WebGL" justify a heavier dependency later.

**Failure mode to avoid.** A pretty hairball. If the clustering does not produce visually obvious
domain structure, the facet vectors are wrong and should be fixed -- or the layout switched to
packed -- rather than prettified around. The gate above is what makes this a decision the build
makes rather than an argument the team has.

**Without JavaScript.** Astro server-renders, inside the canvas container, a real `<ul>` of
benchmarks grouped by domain cluster with counts per group, replaced on hydration. Neither sigma nor
cosmos.gl provides this; we build it. It works with JS off, is screen-reader navigable, is
crawlable, and it is the same markup the citability requirement already demands -- so it costs
nothing extra.

**And it is also the legend.** This one artefact is simultaneously the no-JS fallback, the
screen-reader linearisation, the roving-tabindex target ([09-design-system.md](09-design-system.md)
§8.2) **and the Atlas legend**: a nineteen-row family index beside the map, carrying the six
presentation-group headings as its first level, the family label, the benchmark count and a
highlight toggle per row. Four requirements, one component, and **no colour swatches at all** --
there is no colour key, because there is no family colour to key. Selecting a row emphasises that
family on the map and dims the rest; the group headings are the only place the presentation grouping
is named on screen, and it is never given a count of its own.

---

## V2 -- Coverage Map *(highest research value)*

**Purpose.** Show where measurement exists and, far more importantly, where it does not. Nothing
else in the ecosystem answers "what is nobody measuring?" -- BenchmarkList, Benchmark Radar and
Every Eval Ever all index what exists. The empty cells are the most valuable output of this project.

**Form.** A Domain x Capability matrix. Rows are the **19 domain families**, in the declared
presentation-group order, banded by group with a `<th scope="rowgroup">` per band. Row order comes
from `taxonomy/domain_groups.yaml` and is **build-stable: it is never sorted by entry count by
default**. Sorting by count is a user-invoked, URL-encoded option, because a default order that
rearranges whenever curation adds a benchmark is the Atlas drift failure reproduced in a table, and
it destroys the spatial memory that makes a nineteen-row matrix learnable. Columns are capability
groups -- the coarse rollup of the capability terms, enumerated in
[02-taxonomy.md](02-taxonomy.md) §4.3 and not restated here. Cell intensity is coverage density:

```
density = sum over benchmarks, weighted:
            primary domain match     x 1.0
            secondary domain match   x 0.4
            subset-derived match     x 0.4
          x quality_weight (0.5-1.5 from verification status, maintenance, baseline presence)
```

### Resolution: the full matrix is too sparse to read, and this is arithmetic, not taste

The taxonomy has **19 domain families** containing **204 (family, subdomain) pairs**, and **44
capability terms**; [02-taxonomy.md](02-taxonomy.md) owns all three counts. The matrix is indexed by
the 204 pairs rather than by bare subdomain slugs, because its rows are navigational positions:
`reasoning-general/puzzle-solving` and `games-planning/puzzle-games` are two rows, not one. The full
subdomain x capability matrix is therefore **204 x 44 = 8,976 cells**, and most of them are empty
for arithmetic reasons that have nothing to do with how well anyone curates.
[12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1 owns the emptiness figures, derives
them from the measured 4.2-capability-tag rate, and this document deliberately does not restate the
derivation: **the fine grid is at least 85% empty at the 320-entry seed and still roughly 30% empty
at the plan's 1,500-family working scale.** (The earlier draft of this document carried "89% empty",
which was stale twice over -- it was computed at a superseded corpus size *and* at the
three-tags-per-benchmark rate D1 replaced. Two documents restating one percentage is how that
happened, so only one of them states it now.) A view whose default state is unreadable will be
interpreted as "this project has no data", which is why the fine grid is drill-down only and never
the landing state.

**The default view is therefore 19 domain families x 13 capability groups = 247 cells.** The
capability-group vocabulary -- a strict partition of the 44 terms into 13 groups -- is enumerated in
[02-taxonomy.md](02-taxonomy.md) §4.3 and is deliberately not restated here; note that the group
axis is **derived and never hand-tagged**, so curators tag terms and the rollup is computed. At 1,500
benchmarks and the 3.3-group rollup collapse factor that
[12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1 owns and derives, the coarse grid
carries ~4,950 incidences over 247 cells, a mean of **~20 per cell** -- readable at a glance on a
laptop, and far enough above one that an empty coarse cell is a finding rather than noise. At the
320-entry seed ([02-taxonomy.md](02-taxonomy.md) §3) the same arithmetic gives a mean of ~3.0 with
70% of entries at `full` completeness and ~4.3 if every one of them reaches it, which is why the
coarse grid is the only grid permitted to publish gap claims and why the Gap Finder waits for
domain-reviewer sign-off. Thirteen columns rather than eight is a deliberate choice against a
HELM-shaped default: a coarse cell is empty at maturity only when every member term is a structural
zero for that family, so an eight-column grid would preserve only about a third of the absolute gap
surface that thirteen columns do, and its gap output would fall to near zero exactly when the corpus
finally becomes good enough to support gap claims. Clicking a family expands it to that family's subdomains x the full 44 capability terms --
ECharts' `MatrixComponent`, new in ECharts 6.0, exists precisely to nest a sub-chart inside a cell,
which is why it beats a bare `HeatmapChart` here. Three levels are available but only two are
rendered by default.

**Open, to be settled at first render:** whether 13 horizontal tick labels fit without rotation at
laptop width in ECharts `MatrixComponent`. This is a decision we have not made yet, not a claim
about the world, so it does not take the provenance marker
([07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) §3.1 owns that distinction). All
13 group labels are under 22 characters, so it should fit; the binding legibility constraint on this
view is now the column axis, because nineteen rows is a comfortable table height and the row axis is
no longer in question.

### Three cell states, not two

Empty is ambiguous, and the ambiguity is the whole risk of this view. Note what makes these states
legible at all: **the density ramp is the only colour in the plot area.** Domain family is carried by
position and text, so the one colour channel in the most valuable view in the product has exactly one
meaning, and the absence vocabulary gets the whole pattern channel to itself.

| State | Meaning | Rendering |
| --- | --- | --- |
| Measured | Benchmarks exist and are curated | Fill ramp by density |
| **Not applicable** | The taxonomy marks this pair as incoherent (`speech-synthesis` x `formal-proof-check`) | Distinct neutral, no ramp, excluded from all gap scoring and from the denominator of every coverage percentage |
| Empty | Applicable, and we hold zero entries | Zero fill, **plus the curation overlay below** |
| **Tautological** *(an annotation, not a fourth state)* | Row and column carry the same word, because a capability shares a slug with this subdomain's leaf (declared in `taxonomy/homographs.yaml`). Occupied by construction: full reports the tagging convention, empty reports that the row is empty | Hatched fill at full density, labelled on hover, excluded from gap ranking and from both sides of every coverage percentage. Distinct from **Not applicable**, which renders neutral-blank because the question is incoherent -- here the question is coherent and the answer is guaranteed |

Four cells at present -- `planning`, `spatial-reasoning`, `temporal-reasoning` and
`compositional-generalization` are each both a capability term and a subdomain leaf -- all in the
fine grid, none in the coarse grid, which is the only grid that publishes gap claims. CI check 9e
asserts that the flagged set matches the declarations in `taxonomy/homographs.yaml`. Tautology is an
annotation on a cell rather than a state of one: the cell still has a density, and the annotation
says the density carries no information. One residual rendering conflict to settle at first render:
a hatched fill is also how [09-design-system.md](09-design-system.md) §4.4 draws *zero coverage*, so
the tautological mark must differ in angle or carry its own glyph rather than relying on density
alone. **Open, to be settled at first render, before the cell vocabulary is frozen.**

Declaring `not-applicable` pairs is taxonomy work, not visualization work
([03-taxonomy-build-process.md](03-taxonomy-build-process.md)), but the view cannot be honest
without it. Absent that declaration, a matrix that is 85% empty at seed
([12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1) -- and structurally meaningless in
much of that emptiness -- communicates a false finding.

### The honesty requirement

An empty cell may mean nobody measures it, or that the taxonomy describes the field badly, or that
our curation has not reached it. **A curation gap must never be readable as a field gap.** Two
mechanisms, both mandatory:

1. **Curation coverage renders alongside density, never fused into it.** Density is the fill ramp.
   `curation_confidence` -- computed from entry count, recency of verification and whether a domain
   expert has reviewed the domain ([12-analytics-and-trends.md](12-analytics-and-trends.md)) --
   renders as **a dedicated confidence bar in the row-header gutter plus a sentence in every cell
   tooltip**. Two quantities, two channels. A bivariate choropleth that multiplies density hue by
   curation lightness is the tempting move and it is wrong: nobody reads it correctly, and the one
   thing this view must not do is be misread.

   **An earlier draft gave low-confidence cells a diagonal hatch overlay, and that is withdrawn.**
   It collided with the absence vocabulary in [09-design-system.md](09-design-system.md) §4.4, which
   allocates a 45-degree hatch to *zero coverage*, a diagonal slash to *not yet curated* and a
   dotted border to *not applicable*. Two hatches in one matrix are not distinguishable at cell
   size, and absence rendering is the one vocabulary that must never be ambiguous -- the more so now
   that patterns carry load the family palette used to carry. Where a per-cell mark for low
   confidence is genuinely needed, use a 4px `--c-ink-faint` triangular tick in the cell's top-right
   corner: a different shape class, with no confusion against the absence patterns.
2. **Every cell's tooltip and detail panel states the claim about the index, not about the world**:
   "As of index commit `8f3c9a1`, this index holds 0 entries for chemistry/catalysis x
   calibration-uncertainty. Curation confidence for chemistry: 0.42 (17 entries, last domain review
   never)." The same sentence template is reused verbatim by the AI gap-narration feature in
   [11-ai-features.md](11-ai-features.md), for the same reason.

**Interactions.** Click a cell -> list its benchmarks (or, when empty, the nearest partial coverage:
benchmarks in the same row, or the same column in an adjacent domain). Toggle the measure between
raw count, quality-weighted density, and **claim density** -- a cell can contain benchmarks that
nobody actually runs, which is a different and equally interesting kind of emptiness. Overlay
"activity in the last 24 months" to distinguish genuinely empty cells from newly filling ones.
Flip to the ranked list (V7) for people who want the answer rather than the picture. Brush a
rectangle of cells -> send that benchmark set to the Suite Builder.

**Row and column emphasis, and the one hard rule about it.** Hovering or focusing a row applies a 2px
`--c-emphasis` left rule and sets the row header semibold; a column behaves identically at the top.
**Emphasis never alters a cell fill.** The fill is the density read, and corrupting it on hover would
make the view lie exactly when someone is inspecting it. Clicking a family expands that row into its
subdomains in place, indented under the family header -- 6 to 18 rows depending on the family, per the
per-family counts in [02-taxonomy.md](02-taxonomy.md) §3 -- with the same ramp, the same cell states
and the group band retained. No colour is introduced at the subdomain level either; at 204 subdomains
the question does not arise.

**Implementation.** ECharts `MatrixComponent` + `HeatmapChart` + `VisualMapComponent` +
`BrushComponent`, `SVGRenderer`, `ssr: true` with `renderToSVGString()` at build time so the static
SVG is in the HTML before hydration.

**Failure mode to avoid.** Publishing a gap finding that is really a curation finding. The
reconnaissance identified four gaps that survive that test today and are publishable on day one --
phylogenetics has no standing benchmark; education and tutoring have no public leaderboard, only
learning-gain RCTs; human-comparison psychometric batteries have no canonical benchmark; and
retrosynthesis has a canonical *dataset* (USPTO-50k, 50,016 atom-mapped reactions) but **no
canonical leaderboard**, which is why 2026 papers report mutually inconsistent top-1 numbers on the
same 5,007-reaction test set (RxnNano 75.1% type-unknown against RETROSPECT 55.0% top-1 / 86.2%
top-10). That last one is the cleanest possible illustration of what this index exists to fix and
should be a worked example on the page.

**Without JavaScript.** The matrix is emitted as a real `<table>` with `scope`d headers, one
`<td>` per cell carrying the count and a `data-density` attribute, with the SSR SVG above it. Both
come from the same `{rows, columns, caption, units}` object. **Each presentation group is a
`<tbody>` carrying `<th scope="rowgroup">` with the group label, and each family row a
`<th scope="row">` with the family label**, so the banding is not a visual affectation but the
accessible structure of the table: a screen reader announces "Life and health sciences,
biology-genetics, causal and experimental: 4 benchmarks". This is the clearest single piece of
evidence that carrying family by position and text beats carrying it by colour -- a colour band has
no accessible expression at all.

---

## V3 -- Saturation Wall

**Purpose.** See at a glance which parts of AI are solved and which are open.

**Form.** Small multiples: one sparkline per benchmark, SOTA over time, human baseline as a
horizontal rule, headroom shaded. Dozens to hundreds on screen at once, **grouped by domain family,
with families ordered and banded by presentation group, each block titled with the family name and
each group preceded by a group heading**. A wall of
these communicates the state of the field faster than any prose summary -- whole domains where every
line has flattened against the ceiling, beside domains where lines are still climbing steeply or
have barely started.

**Data consumed.** Per benchmark: the ordered claim series above the verification threshold, the
designated `primary_baseline`, the metric's `range` and `chance_baseline`, and:

```
headroom_consumed = (SOTA - baseline) / (ceiling - baseline)

saturation_level:  emerging  headroom < 0.25
                   contested 0.25 <= headroom < 0.75
                   closing   0.75 <= headroom < 0.95
                   saturated headroom >= 0.95
```

**Implementation. Hand-rolled inline SVG generated at build time. Do not use a chart library here.**
Hundreds of ECharts instances on one page is a performance disaster; a sparkline with a baseline
rule and headroom shading is about thirty lines of path-string generation in the Python build step.
Recommended tile geometry is 160 x 44 px with a 4px gutter, which fits roughly 200 tiles above the
fold-plus-one-scroll on a laptop. Strokes use `currentColor` and CSS custom properties, so dark mode
needs no second code path and no re-`init`. Result: zero JS, no-JS readable, printable, accessible,
and citable by construction.

**Data honesty -- the part that distinguishes this from every other saturation chart.**

- Points are individual result claims, never a smoothed curve. The step function is the truth.
- **A frontier segment set by a `self-reported` claim renders differently** from one set by a
  `maintainer-verified`, `held-out-server` or `independent-reproduction` claim: dashed stroke,
  hollow point marker. The verification ladder is in [04-data-model.md](04-data-model.md) and the
  badge geometry in [09-design-system.md](09-design-system.md).
- Benchmarks with `ceiling_anchor_type: none-known` show the trajectory with **no shading at all**
  and a one-line reason. This is common in exactly the domains we differentiate on -- across the
  robotics inventory almost nothing has a human baseline, and WeatherBench 2's comparator is an
  operational NWP supercomputer model rather than a person.
- Where the ceiling is not human, say what it is. The Virtual Cell Challenge 2026 normalises each of
  its six metrics between the cell-context mean and **a real biological replicate experiment**; the
  "100%" anchor is a wet-lab measurement. Atari-100k's human-normalised score is **unbounded above
  100%**. The shading must not imply a person is the ceiling when the data says otherwise.
- Metrics where lower is better (WMDP accuracy on hazardous knowledge; BBQ's bias scores, whose
  optimum is zero and which are a *pair* of numbers, s_AMB and s_DIS) invert the shading and carry
  an explicit "lower is better" marker.
- Benchmarks flagged **no aggregate by design** are excluded from the wall and listed separately.
  WeatherBench 2's authors state plainly that it is "a tool to compare different approaches on
  different aspects", not a challenge with one ranking, and ReXrank deliberately publishes eight
  metrics with no aggregate. Manufacturing a sparkline for these would be exactly the
  false-comparability failure the project exists to oppose.

**Interactions.** Sort by headroom remaining, by saturation velocity (change in headroom per month
over a trailing window), or by age. Filter to unsaturated only. Hover any point for the underlying
claim with its verification badge and condition-completeness meter. Click through to the
benchmark's full trajectory on its detail page.

**Failure mode to avoid.** A wall of confident-looking curves built from self-reported numbers with
half their conditions unknown. Machine-ingested claims from the Epoch bulk ingestion have a mean
`condition_completeness` around 0.10; they belong in browse and coverage, not in a frontier line.
The wall therefore computes SOTA at a stated verification threshold, defaulting to
`maintainer-verified` and above, shows that threshold on the page, and lets the reader lower it.

**Without JavaScript.** Fully static already. Sorting degrades to a set of pre-rendered
`/saturation/?sort=headroom|velocity|age` pages; the default sort renders at `/saturation/`.

---

## V4 -- Frontier Timeline

**Purpose.** Track releases, hosts and direction of travel, and make visible the relationship
between the two: benchmarks appearing in response to capability jumps, capabilities saturating
benchmarks. That relationship is the actual story of the field, and it is currently told only in
prose essays.

**Form.** A horizontal time river. System releases on an upper band, benchmark releases on a lower
band. Marks on both bands are **neutral**: the top six organisations by release count are
direct-labelled and everything else is grey, labelled on hover and in the accompanying table, per the
six-series hue cap in [09-design-system.md](09-design-system.md) §7.1.

Beneath, **a small-multiples strip set showing release volume by domain family over time: one filled
area strip per family, nineteen strips, a shared x axis, a single neutral fill, direct-labelled, and
ordered and banded by presentation group.** This replaces the stacked-stream/ThemeRiver underlay an
earlier draft specified, and the reason is the same perceptual limit that removed the family palette:
a nineteen-band theme river is a nineteen-category colour encoding under another name, and it is
unreadable at that cardinality whatever palette it is given. The strip set is strictly more readable,
consistent with V3's small-multiples treatment, and needs no categorical colour at all.

**Interactions.**

- **Brush a time range** -> filters every other view in the session. ECharts' `BrushComponent`
  provides this natively; the brushed range is written into the URL so the filtered state is
  shareable (see the URL scheme below).
- **Click a release** -> all its claims.
- **Filter** by organisation or domain.
- **Benchmark-lifespan overlay**: each benchmark drawn as a bar from release to first claim at
  >= 0.95 headroom. This is the chart that makes the shortening of release-to-saturation visible,
  and it is likely the single most communicative image the project can produce. Cybench went from
  17.5% at launch to frontier models at ~93% in 2026; OSWorld's 72.4% human baseline has been
  *passed*, with top-5 2026 runs at 73.1--82.6%; GPQA Diamond saturated in 2026 against a PhD-expert
  baseline of ~65--74%.

**The survivorship problem, drawn.** Time-to-saturation is computable only for benchmarks that
saturated. Plotting only those produces a confidently wrong trend. The lifespan overlay therefore
draws unsaturated benchmarks as **open-ended bars with an arrow terminal** on the same axis, and the
view reports the censored count in the caption: "N of M benchmarks released in 2024 have not
saturated and are drawn as open bars." A survival-analysis treatment is the statistically correct
answer and is deferred to [12-analytics-and-trends.md](12-analytics-and-trends.md); the open bar is
the honest minimum.

**Implementation.** ECharts `custom` series on a time axis for the two bands (a scatter with a
categorical y-band and per-point symbol sizing), `BrushComponent` for range brushing,
`DataZoomComponent` for zoom. The nineteen family strips are build-time SVG from the same generator
as V3, so **`ThemeRiverChart` drops out of the import set entirely**. Colour carries no organisation:
marks are neutral, the top **six** organisations by release count are direct-labelled, the rest are
grey and named on hover and in the table. The earlier "top twelve plus other" rule is withdrawn --
twelve categorical hues contradicts the six-series cap in
[09-design-system.md](09-design-system.md) §7.1, and categorical palettes stop being distinguishable
well below twelve. The organisation dimension is better explored in V9 anyway.

**Failure mode to avoid.** Reading our curation history as the field's history. If we curated 2024
heavily and 2019 thinly, "benchmarks released per year" is a picture of our backfill, not of the
field. Every count-over-time series in this view carries the **curation-coverage series for the same
years as a muted second line**, and shares are preferred over counts wherever a share is meaningful.
This rule applies with equal force to V9 and is stated once here.

**Without JavaScript.** A static SVG of the two bands at default zoom, plus the underlying table of
releases by year and organisation. Brushing is a JS enhancement; the pre-rendered `?from=&to=`
year-range pages cover the common cases.

---

## V5 -- Comparison Workbench

**Purpose.** Compare systems across benchmarks honestly -- which mostly means declining to compare
them, loudly and with reasons.

**Form.** A user-assembled N systems x M benchmarks grid: a table as the primary surface, a parallel
coordinates plot as the secondary one. Assembled from a lasso in V1, a brush in V2, a selection in
V11, or a pasted list of IDs.

**Data consumed.** `corpus.json` (0.52 MB brotli, lazy-loaded on entry to this view -- the only
place in the site that needs it), specifically ResultClaims with their EvalConditions, verification
level, `condition_completeness`, `comparability_key` and `artifact_url`.

**The distinguishing feature: comparability enforcement.** Two claims are comparable only when they
share benchmark version, metric and subset, plus the material condition fields: `shots`,
`chain_of_thought`, `tools_allowed`, `selection_strategy`, `k`, `n_samples`, `retries_allowed`,
`judge_model`, `human_in_loop`, `subset_used`. The build hashes exactly those into
`comparability_key`.

When an assembled view spans multiple keys, a banner names precisely which material fields differ,
as a field-by-field diff table:

```
3 condition groups in this view. Differences:

  field             group A            group B            group C      severity
  ---------------   ----------------   ----------------   ----------   --------
  tools_allowed     [bash, edit]       []                 [bash, edit]  material
  selection_strategy single            single             best-of-8     material
  judge_model       null (unknown)     gpt-5.2            null          material
  scaffold          anthropic-harness  none               swe-agent@1.4 informative

  [ Restrict to group A  -- drops 14 of 31 claims ]
  [ Proceed, flagging every affected cell ]
```

Two options, both explicit, neither silent. The count of dropped claims is always shown -- silently
dropping data to make a chart look clean is the exact behaviour this view exists to prevent.

**Beyond the generic key, six categorical refusals.** These come straight from the domain
reconnaissance's schema stress tests and each one is a case where a naive comparison table produces
a confidently wrong number:

| Situation | Example | Behaviour |
| --- | --- | --- |
| Pool-relative rating compared across snapshots | Kaggle Game Arena Elo, 40 games per pair; a model's rating moves when a *different* model joins the pool | Refuse. Require matching `rating_pool_id` + snapshot date; otherwise render side by side with no shared axis |
| Reliability metric averaged | tau-squared-bench `pass^k` -- fraction of tasks solved in *all* k trials | Refuse to average across k. `pass^1` and `pass^8` are different metrics |
| Vector-valued result collapsed | VBench's 16+ dimensions; ReXrank's eight metrics with no published aggregate | Render as a small-multiple row or radar, never a scalar. Honour the `no_legitimate_aggregate` flag |
| Different leaderboard legality rules | ARC-AGI-3's Official (unmodified general-purpose API systems) vs Community (harnesses permitted) leaderboards | Treat harness legality as a material condition; the two leaderboards never merge |
| Different training-data eligibility | Matbench Discovery's compliance tiers restrict what a model was allowed to train on | Group by compliance tier. This is a comparability key on the *training* side, which most LLM-shaped schemas have no slot for |
| Unresolved ground truth | ForecastBench and Metaculus FutureEval resolve months to years after submission | Show `resolution_status: pending / partial / resolved` and never plot pending against resolved |

**Default sort is verification level before value.** Making the strongest claim also the least
verified is common, and the UI should surface that rather than reward it with the top row.
**Condition completeness renders as a small meter in every cell.** **Unknown material conditions
draw as an explicit marker, never as a blank and never as an assumed default** -- `null` in a
material field means unknown, not zero-shot, not no-tools.

Machine-ingested claims (the bulk Epoch ingestion, `curation.verification_status: machine-ingested`,
mean completeness ~0.10) are **hidden by default in this view below `comparison_floor`**, the named
threshold declared in `taxonomy/thresholds.yaml` and owned by
[12-analytics-and-trends.md](12-analytics-and-trends.md) -- referenced by name rather than by value,
because a threshold typed as a literal in five documents is a threshold that will be calibrated in
one of them. There is a visible "N machine-ingested claims hidden -- show them" control. They remain fully
visible in browse and count fully toward coverage. Bulk data provides coverage; it must not pollute
comparison, which is where credibility lives.

**Normalisation.** Three modes: raw metric value, percentile within the benchmark's claim set, or
headroom consumed. **Headroom is the only mode permitted to plot across domains**, and selecting it
while spanning domains is allowed precisely because that axis was designed for it. The caveats
travel with the number on the page, not in a methodology appendix: headroom assumes linearity
between anchors, which is usually false since the last 5% of a benchmark is far harder than the
first 5%, and it is sensitive to the choice of ceiling.

**Implementation.** ECharts `ParallelChart` + `ParallelComponent` for the plot; the table is plain
HTML with client-side sort. Each axis in the parallel plot is a benchmark; each polyline a system;
lines are dashed where any cell in that row spans condition groups.

**Failure mode to avoid.** Becoming a prettier leaderboard. If the most common outcome of using this
view is a clean ranking, the enforcement is too weak. The intended most common outcome is a user
learning that the two numbers they wanted to compare were produced under different conditions, and
seeing exactly which.

**Without JavaScript.** The workbench is inherently interactive, but a URL carrying a full selection
renders server-side as a static table with the comparability banner and diff already computed --
because the comparability computation is deterministic and happens at build time for any selection
the URL encodes. Parallel coordinates are JS-only; the table is not.

---

## V6 -- Benchmark Detail Page

The canonical, citable, permanently-URL'd page per benchmark. **Static-rendered, zero JavaScript
required to read it.** This is the page that gets cited, archived, crawled and quoted; every other
view is a route to it.

**Full contents, in order:**

1. Name, aliases, tagline, lifecycle badge, headroom meter, adoption count.
2. Description -- neutral prose, no comparative or promotional language.
3. Facet chips, each linking to the corresponding filtered browse view. *(Note the Astro
   `compressHTML` trap: chips are adjacent inline elements and will be glued together unless
   `compressHTML: true` is set explicitly.)*
4. Version history with `breaking: true` markers. FrontierMath makes the case: Epoch reissued a
   corrected version on **2026-06-12 after finding errors in 42% of problems**, so a score against
   "FrontierMath" without a version is now meaningless. Errata are first-class here, not a footnote.
5. Subsets, with per-subset facet overrides shown.
6. Metrics, each with its `range`, `chance_baseline`, `higher_is_better`, aggregation, units and
   **`pitfalls` rendered inline** -- a metric's known failure modes should be unavoidable, not
   buried. GDT-TS is insensitive to local errors; COCO's AP is a composite over IoU .50:.05:.95.
7. Human baselines, all of them, with the designated `primary_baseline` marked and the population,
   n, and time limit stated.
8. Leaderboard links **with snapshot dates and a liveness indicator**. Leaderboards die constantly:
   Aider's was last updated 2025-11-20, roughly ten months stale; the HuggingFace Open LLM
   Leaderboard was retired 2025-03-14.
9. The SOTA trajectory chart -- same hand-rolled SVG generator as V3, at larger size.
10. The claims table, sorted by verification then value, each row with its provenance drill-down.
11. Lineage graph -- supersedes, superseded-by, subset-of, extends, decontaminates -- rendered as a
    small static SVG. Lineage is one of the genuinely unoccupied differentiators: OSWorld ->
    OSWorld-Verified + OSWorld 2.0, Terminal-Bench 2.0 and 2.1 concurrent, SWE-bench's six forks,
    FrontierMath's four variants, HELM's eight. Nobody else models supersession -- see
    [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 for exactly how far that
    claim is supported and what would retire it.
12. Governance and independence flags, with evidence links.
13. Licence, access model, and gating notes (CheXpert/MIMIC require PhysioNet credentialing, CITI
    training and a signed DUA -- that is an access class, not a footnote).
14. Execution cost estimates: `compute_tier`, `reproducibility_tier`, `est_runtime_hours`,
    `est_cost_usd`, `est_api_calls`, all range-typed.
15. **Maintenance status**, driven by observable signals: days since last repo push, days since
    leaderboard update, dataset availability. This field exists in no other catalogue
   ([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 states how far that
   negative claim is supported). One study of
    195 safety benchmarks found **137 with stale GitHub repos and 96 with stale HuggingFace
    datasets**; BetterBench found **17 of 24 benchmarks had no working reproduction scripts**.
16. Full source list with archive links and accessed dates.
17. Curation footer: who added it, when, when last verified, how stale that is, and the
    `verification_status`.
18. **Citation block** -- see the URL scheme below.

### The provenance drill-down

This is the single most important interaction in the product. It is what makes the transparency
claim real rather than rhetorical, and the implementation choice matters:

**Every number on the page is wrapped in a native `<details>` element.** The `<summary>` is the
number plus its verification badge and completeness meter. Opening it -- one click, no navigation,
**no JavaScript** -- reveals a definition list:

```
0.XXX  [maintainer-verified]  [conditions 8/10]
  v
  source              SWE-bench Verified leaderboard (src-swebench-lb-2026-05)
                      accessed 2026-05-14 | archived 2026-05-14 (web.archive.org/...)
  date reported       2026-05-12
  reported by         org-princeton-nlp
  verification        maintainer-verified
  comparability_key   c4f19a2e  (3 other claims share this key)
  artifact            transcripts: https://... (2,294 per-instance logs)
  provenance snapshot ingested 2026-05-14 from leaderboard row 7, raw value 0.XXX
  conditions          shots 0 | CoT true | reasoning_effort high | tools [bash, file-edit]
                      scaffold swe-agent@1.4 | n_samples 1 | selection single | retries 0
                      judge_model (n/a) | subset_used full | human_in_loop false
                      temperature 1.0 | seed (unknown) | max_output_tokens (unknown)
  unknown fields      seed, max_output_tokens
```

Unknown fields are listed *as a set*, so a reader sees the shape of what is missing rather than
scanning for blanks. `artifact_url` and `provenance_snapshot` are schema fields added specifically
before bulk ingestion began, because retrofitting thousands of records is painful.

With JavaScript, the `<details>` is progressively enhanced into a side panel with two extra
affordances: "diff this claim against another" (opens the V5 diff on exactly two claims) and "copy
citation". Without JavaScript, the native disclosure still works completely. Building the primary
interaction on a native HTML element rather than a JS component is what lets the most important
interaction in the product also be the most durable.

**Failure mode to avoid.** A detail page so long that nobody reaches the provenance. The page uses
progressive disclosure within itself -- sections 1--9 are the readable article; 10--17 are
collapsed-by-default `<details>` sections with counts in their summaries ("Claims (47)", "Sources
(12)"). Collapsed, not absent: the counts are visible without opening, and the collapsed content is
still in the HTML, so it is crawlable, printable and searchable by the browser's own find.

---

## V7 -- Gap Finder

**Purpose.** The Coverage Map inverted: a ranked worklist for a researcher deciding what to work on
next, or a funder deciding what to fund.

**Form.** A ranked list of (domain, capability) pairs with no or thin measurement, scored by:

```
gap_score = (1 - normalized_density)
          x domain_activity       (publication/release velocity in that domain)
          x capability_salience   (how often that capability is measured elsewhere)
          x curation_confidence   (how thoroughly this project has covered the domain)
```

That last factor is the honesty term. Without it, every under-curated domain looks like a research
gap and the Gap Finder becomes a map of the maintainers' blind spots presented as a map of the
field's.

**Each row carries:** the cell, its score, **the score's components shown separately** so a reader
can see whether a high score came from genuine absence or from high domain activity, a prose
explanation of why the cell is considered a gap, the adjacent benchmarks that partially cover it,
and an explicit curation-confidence caveat. Rows below a curation-confidence floor are shown in a
separate "we have not looked hard enough here" section rather than mixed into the findings --
because they are a statement about us, not about the field.

**Interactions.** Filter by domain, by capability, by minimum curation confidence. Sort by any
component. "Show only cells where curation confidence > 0.7" is the honest-findings view and should
be one click. Export the list as CSV and as JSON with the index commit SHA embedded.

**Implementation.** Fully static -- the scoring happens in the Python build and lands in
`build/derived/gaps.json`. No chart library. The list is a table.

**The AI relationship.** [11-ai-features.md](11-ai-features.md) adds a 100-word research-direction
brief per interesting cell, precomputed offline via the Batch API for roughly 200 cells, shipped as
static text and regenerated monthly. Zero runtime cost, zero runtime risk, and every brief is headed
with the "As of index commit `abc123`, this index contains 0 entries for..." template -- a claim
about the index, never about the world. With the AI layer off, the cell shows the computed
components and the adjacent-coverage list, which is the substance anyway.

**Failure mode to avoid.** Publishing a confident gap that a specialist can refute in one reply.
Before a gap is promoted from the raw list to a highlighted finding, it needs a domain reviewer's
sign-off recorded in `curation`. The four day-one publishable gaps named under V2 have that
property; most cells will not.

---

## V8 -- Release Feed

**Purpose.** This is the retention surface -- the reason someone returns weekly rather than visiting
once. It is cheap to build on data already present and should not be deferred past the phase that
ships the detail pages.

**Form.** Reverse-chronological stream, filterable by domain, organisation and event type.

**Event types**, all derived from git history over `data/` at build time rather than from a
hand-maintained changelog (hand-maintained changelogs drift and then quietly lie):

| Event | Trigger |
| --- | --- |
| `benchmark-added` | New file under `data/benchmarks/` |
| `benchmark-updated-material` | A diff touching facets, lifecycle, licence, access or versions |
| `claim-added` | New ResultClaim |
| `correction` | A commit tagged `fix:` touching a previously published value |
| `lifecycle-change` | Derived lifecycle transition, including automatic `saturated` |
| `deprecation-detected` | Maintenance signals crossed the staleness threshold |
| `source-rot-detected` | A scheduled liveness check found a dead source URL |

**Formats.** `/feed.xml` (Atom), `/feed.json` (JSON Feed 1.1), plus per-domain feeds at
`/feed/{domain-family}.xml` and **a separate corrections feed at `/feed/corrections.xml`**.

The corrections feed is a deliberate trust instrument, not a technicality. The index publishes its
own dispute rate and correction rate ([12-analytics-and-trends.md](12-analytics-and-trends.md)); a
reference that never publishes corrections is not error-free, it is unaudited. Making corrections a
first-class, separately subscribable stream is the cheapest available demonstration that we mean it.

**Failure mode to avoid.** A feed dominated by bot noise. Machine-ingested claims arriving in bulk
would swamp everything a human curator did. The default feed therefore **excludes
`machine-ingested` events**, which live at `/feed/ingest.xml` for anyone who wants them.

**Without JavaScript.** Fully static. The feed *is* files.

---

## V9 -- Ecosystem View *(new)*

**Purpose.** Answer the user's request to "analyze/view the current ecosystem (systems, benchmark
makers, managing orgs, trends)". The unit of analysis here is the **organisation**, not the model
and not the benchmark. Nothing in the landscape does this: BenchmarkList counts 1,604 providers but
exposed no analysis through its public interface as of 2026-09-17 (no API exists, so that is a
reading of a rendered UI rather than of a schema), Benchmark Radar is discovery-focused and
LLM-centric by its own abstract, and Every Eval Ever models results rather than benchmark
governance. [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 states how far
each of those negative claims is supported and what a single counterexample would do to it.

**Form.** A dashboard of six charts plus an organisation profile page type.

| # | Chart | Form | What it answers |
| --- | --- | --- | --- |
| E1 | Who builds benchmarks | 100% stacked area, new benchmarks per year by `maintainer_type` | Is the field's measurement infrastructure moving from academic labs to industry labs? |
| E2 | Evaluation-method drift | 100% stacked area, share of new benchmarks by `evaluation_method` per year | The rise of `model-graded-judge` against `execution-tests` and `human-expert-eval`. One of the most consequential quiet shifts in the field, currently unquantified anywhere |
| E3 | Access trend | Stacked area, share of new benchmarks that are `private-test-server` or `generated-on-demand` | The field's response to contamination, measured rather than asserted |
| E4 | Domain attention flow | **Organisation x domain-family heatmap** on the same cool coverage-density ramp and the same banded nineteen-row structure as V2, with a year slider stepping the heatmap | Where is measurement effort going? The chord diagram an earlier draft specified is withdrawn: nineteen domain arcs plus N organisation arcs is the worst case in this document -- it needs a categorical colour per arc and is hard to read even when it has one. The loss is real and stated: a chord shows bilateral flow and a heatmap does not, so "which organisations moved between domains" is answered by stepping the year slider rather than by a ribbon. Magnitude is what the question actually asks for, and reusing V2 brings its ECharts imports, its no-JS table generator and its accessibility structure for free |
| E5 | Independence exposure | Scatter: per organisation, benchmarks maintained (x) against claims reported on benchmarks they maintain (y), point size = adoption of those benchmarks | Disclosure of the structural conflict, drawn |
| E6 | Leaderboard liveness | Bar of days-since-update per hosted leaderboard, with a dead-line threshold rule | Which parts of the published record are no longer being maintained |

**The organisation profile page** (`/orgs/{id}/`): benchmarks maintained, systems released, claims
reported and their verification mix, the contamination exposure of that org's evidence base
(fraction of claims on `high` or `confirmed` contamination-risk benchmarks -- a property of the
*evidence*, never an accusation against the system), independence flags with evidence links, and
the domains they operate in.

**The independence analysis is DISCLOSURE, never accusation.** This must be true in the interface,
not only in the policy document. Concretely:

- E5 has **no ranking, no "conflict score", and no red colour**. It is a scatter with labels. The
  reader sees that a lab built the benchmark its own model tops and weighs it themselves.
- Every `independence_flags` value on screen is a link to its evidence source. A flag with no
  evidence source fails CI and therefore cannot render.
- The neutral term `no-known-conflict` renders with the same visual weight as the others. "No known
  conflict" is a statement about our knowledge, not a clean bill of health, and the tooltip says so.
- The page carries a standing note that maintainers competing on their own benchmarks is normal and
  often unavoidable in a field where the people who can build a good benchmark are the people
  working on the problem -- and that the point of recording it is that readers can see it, not that
  anyone should be embarrassed.

**Failure mode to avoid, stated twice because it is the real risk here.** (a) Turning disclosure
into a league table of shame; the design rules above are the mitigation. (b) **Reading our curation
history as the field's history.** If our 2019 coverage is thin and our 2025 coverage is rich, E1--E3
draw our backfill curve and label it a trend. Every time series in this view therefore plots the
curation-coverage series for the same years as a muted second line, prefers shares to counts, and
carries the index commit SHA in the caption. A trend line drawn from a curation artifact is exactly
the unsourced confidence this project exists to oppose, and it would be *our* unsourced confidence.

**Implementation.** ECharts `HeatmapChart` + `VisualMapComponent` for E4 -- the same modules, ramp
and table generator as V2, so **`ChordChart` drops out of the import set** -- `LineChart`/stacked
area for E1--E3, `ScatterChart` for E5, plain bars for E6; `TimelineComponent` for the year slider. All SSR'd to SVG
at build time. The organisation profile page is static and JS-free like V6.

**Without JavaScript.** Six static SVGs plus their six tables. The year slider degrades to
pre-rendered per-year pages for the last ten years.

---

## V10 -- Suite Builder *(new)*

**Purpose.** The user-facing surface for "build their own custom benchmark [suite]". The settled
interpretation is **suite assembly**: helping someone select the right set of *existing* benchmarks
for their system and export a manifest with links and recommended conditions. Authoring new
benchmark tasks or data is explicitly out of scope for v1 -- it would require hosting data and
contradicts the project's first constraint.

**Two words, used precisely throughout.** The **basket** is the working selection inside the page --
mutable, URL-encoded, thrown away when the tab closes. The **suite manifest** is what the basket
exports: a `suite.yaml` with pinned versions, links and recommended conditions, owned by
[11-ai-features.md](11-ai-features.md) F3. They are genuinely different objects, which is why they
have different names; the failure mode to avoid is a UI that pretends a scratch selection and a
citable export are the same thing, so that a user cites something they were still editing.

**This section specifies the non-AI version, and the non-AI version ships first.** The AI layer in
[11-ai-features.md](11-ai-features.md) sits on top of it as an accelerator that fills a starting
basket from a need statement. With the AI switched off, everything below still works.

**Form.** A three-pane working surface.

```
+-- FILTER / SEARCH -----+-- BASKET (7) ------------+-- ANALYSIS --------------+
| facet panel (V11)      | SWE-bench @verified   x  | COVERAGE                 |
| search box             | Terminal-Bench @2.0   x  |  [ mini domain x cap     |
| results, add-to-basket | tau2-bench @retail    x  |    matrix, selected      |
|                        | OSWorld @verified     x  |    cells highlighted ]   |
|                        | AgentDojo             x  |                          |
|                        | GAIA @2               x  | REDUNDANCY               |
|                        | Cybench               x  |  2 pairs flagged         |
|                        |                          |                          |
|                        | [ + from lasso (V1) ]    | COST      $340 - $2,800  |
|                        | [ + from cell (V2) ]     |  from 5 of 7 entries     |
|                        |                          | RUNTIME   12 - 96 h      |
|                        |                          |  from 6 of 7 entries     |
|                        |                          |                          |
|                        |                          | NOT COVERED              |
|                        |                          |  multilingual            |
|                        |                          |  calibration-uncertainty |
|                        |                          |                          |
|                        |                          | [ Export manifest ]      |
+------------------------+--------------------------+--------------------------+
```

**The four computed panels, all in JavaScript from structured fields, none from a model:**

1. **Aggregate coverage.** A miniature of the V2 matrix restricted to the basket: the same nineteen
   banded family rows in the same declared order, the same density ramp, covered cells filled and the
   user's stated target cells (if any) outlined in `--c-emphasis`. **Families with no basket entries
   render as empty banded rows rather than being omitted** -- omitting them would make absence look
   like completeness, which is the exact failure the "Not covered" panel exists to prevent. Where
   vertical space forbids nineteen rows, the rows collapse to the six presentation groups *visually
   only*, and a collapsed row is labelled "4 families, 0 entries" rather than carrying a group-level
   coverage number: the grouping is display-only and must never appear in a coverage figure or a
   claim sentence. This makes the suite's shape visible rather than its length.
2. **Redundancy.** Two benchmarks flagged as redundant when they occupy the same (subdomain,
   capability) cell *or* carry a `correlates_with` edge with a sourced coefficient above 0.8. The
   panel says which and shows the source; it never says "remove this one".
3. **Cost and runtime.** Sum of `est_cost_usd` and `est_runtime_hours` ranges, presented as ranges
   because the underlying fields are ranges. **Entries with null estimates are counted and named**:
   "computed from 5 of 7 entries; SWE-bench and AgentDojo have no cost estimate curated." A total
   that silently omits two entries is worse than no total.
4. **Not covered.** A mandatory section listing target capabilities and domains for which the basket
   contains nothing. This is the panel that prevents the worst failure mode -- absence looking like
   completeness.

**Export.** `suite.yaml` in our own CC-BY schema: entry IDs, version pins, **the index commit SHA**,
recommended evaluation conditions per entry, and the `comparability_key` each recommendation
implies. Adapters generate: Inspect AI task lists (`inspect_evals` package names), EleutherAI
`lm-evaluation-harness` `--tasks` strings with task YAML stubs, HELM run-specs, and a plain
`README.md` with links and licence notes.

**The export is honest about runnability.** Every entry carries
`runnable_via: [inspect | lm_eval | helm | custom | none]`, and the export header states the count:
"3 of 12 runnable from a standard harness; 9 link to their own repositories." Most of a cross-domain
catalogue -- protein structure, weather, materials, formal proof, anything requiring a simulator,
wet lab or physical robot -- has no harness implementation and never will. CACHE requires
participants to *buy compounds from Enamine and have them assayed*; the BEHAVIOR Challenge's score
is only defined inside a specific OmniGibson/Isaac-Sim build; A2RL is a physical drone race. Saying
so is a differentiator, not a weakness: every other tool in this space implies everything is
runnable.

**Basket persistence.** The basket lives in the URL (`/suite/?b=swe-bench@verified,terminal-bench@2.0,...`)
and is mirrored to `localStorage` for convenience. The URL is the source of truth, so a suite is
shareable, citable and reproducible without any server state -- consistent with the no-auth,
no-accounts posture.

**Failure mode to avoid.** Recommending a benchmark whose licence forbids the user's use, or one
that is deprecated, superseded or known-contaminated. **These are hard code filters with a visible
"excluded N entries because..." panel, not model judgement** -- and they apply identically whether
the basket was assembled by hand or by the AI accelerator.

**Without JavaScript.** The basket and analysis panels are inherently interactive. Degraded path: a
URL with a `?b=` list renders server-side as a static suite report -- the coverage table, redundancy
list, cost range with its omissions named, the not-covered list, and a copy-pasteable `suite.yaml`
in a `<pre>` block. Everything except live editing survives.

---

## V11 -- Search and Browse

**Purpose.** The workhorse. Most sessions start here and many never leave.

**Form.** A filter panel beside a result list, with a search box above both.

**The filter panel.**

- Facet counts are computed live from `facets.json` (36 KB gzipped, 1,500 rows) on every filter
  change. At this size a full recount is a sub-millisecond loop over a typed array; no index
  structure is required.
- **Zero-count terms are shown and disabled, never hidden.** Hiding them hides the gap, and the gaps
  are the product. A capability term with zero benchmarks in the current domain filter is exactly
  the information a researcher came for.
- Selected terms appear as a chip row above the results, each removable. *(Astro's
  `compressHTML: 'jsx'` default will glue these chips together -- set `compressHTML: true`.)*
- Every facet group is collapsible, with the taxonomy definition for each term available on hover
  and in full at `/taxonomy/{facet}/{term}/`. A taxonomy nobody can read is a taxonomy nobody can
  apply consistently.
- A "curation confidence" indicator sits at the top of the panel for whatever domain is currently
  filtered, so a thin result list is never mistaken for a thin field.

**Search: three tiers, and the ordering rule matters more than the tiers.**

| Tier | Technology | Size | Latency | When |
| --- | --- | --- | --- | --- |
| 1. Lexical | **Pagefind 1.5.2** via `astro-pagefind@2.0.1` | index chunks ~40 KB each, fragments 1--10 KB per page | instant, per keystroke | Always on |
| 2. Facet | In-memory scan of `facets.json` | 36 KB gz | sub-ms | Always on |
| 3. Semantic | Static embeddings, plain JS, no ONNX runtime | ~4 MB total | 1--2 ms/query | Opt-in, background-loaded |

Tier 1 uses **Pagefind's Node API `addCustomRecord()`**, which takes `url`, `content`, `language`,
`meta`, `filters` (key -> string[]) and `sort`. That means we index the validated YAML directly
rather than scraping rendered HTML: our facets become Pagefind filters for free, and search can
never drift from the data model.

Tier 3's whole stack is `@huggingface/tokenizers` 0.2.0 (pure JS, zero dependencies, 36 KB minified
ESM) plus a `potion-base-8M`-style model2vec matrix quantised to int8 and vocabulary-pruned to
~12k rows (~3 MB), plus 1,500 document vectors at 256 dimensions int8 (0.38 MB). A model2vec model
*is* an embedding matrix -- tokenize, look up rows, mean-pool, normalise -- so there is no
transformer to run, no WASM and no WebGPU. **Measured: brute-force cosine over a `Float32Array`
takes 0.61 ms at our shipped 1,500 x 256, and 0.75 ms at 1,500 x 384 as a conservative upper bound**
([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5 owns the timings and the
dimension decision). Ship no vector index, no HNSW and no vector database; an ANN index starts to
earn its keep past roughly 50,000 vectors, and the in-browser vector libraries the technology
reconnaissance surveyed on 2026-09-17 had all last published in 2023 -- a survey of the obvious
candidates, not an exhaustive search, and decoration on a decision the 0.61 ms measurement already
settles. Note one counterintuitive measurement: a naive `Int8Array` dot loop was *slower* than f32
(2.0 ms against 0.75 ms at 384) because V8 does not auto-vectorise, so int8 is a transport format
only -- dequantise once into a `Float32Array` at load. The turnkey model2vec-in-JS path is
**unverified -- confirm before relying on this**; budget for writing the roughly 150-line encoder
directly.

**The ordering rule that makes the hybrid work: Pagefind answers on every keystroke; the semantic
tier loads in the background and, once ready, *appends* a "related benchmarks you did not type the
words for" block.** Semantic search is never on the critical path to a first result. When both are
present, fuse with reciprocal rank fusion at k=60.

**Failure mode to avoid.** A search box that feels slow because it is waiting for the clever tier.
The measured budget is a first lexical result under 100 ms, always, with the semantic block arriving
whenever it arrives.

**Without JavaScript.** Pre-rendered browse pages exist for every single-term filter:
`/browse/domain/{family}/{subdomain}/`, `/browse/capability/{term}/`,
`/browse/evaluation-method/{term}/`, `/browse/lifecycle/{term}/`, `/browse/access/{term}/`,
`/browse/org/{id}/`. That is a few hundred static pages -- comfortably inside the file budget
discussed below -- and it gives crawlers, archives and text browsers a complete route to every
entry. Multi-term combinations require JavaScript, which is an acceptable line: a single-facet page
is a browsable index, a five-facet intersection is a query.

---

## Progressive disclosure

Three depths, everywhere, and **both extremes reachable within two clicks of the landing page**:

1. **Glance** -- Atlas, Coverage Map, Saturation Wall, Ecosystem dashboard. No reading required.
   Answers "what is the shape of this field".
2. **Scan** -- filtered lists, benchmark cards, comparison tables, the gap worklist, the release
   feed. Answers "which ones are relevant to me".
3. **Study** -- detail pages, claim provenance, evaluation conditions, sources, archived snapshots.
   Answers "should I believe this number".

A researcher evaluating trustworthiness needs depth 3. Someone orienting in an unfamiliar domain
needs depth 1. Both are one click from the landing page and two from anywhere. The mechanism that
makes depth 3 cheap is the native `<details>` drill-down in V6 -- depth is an expansion, not a
navigation, so nobody loses their place getting to it.

The corresponding rule for authors: **every view states what it is a view *of*.** Each page carries
the index commit SHA, the entry count behind the view, and the verification threshold in use. A
chart that does not say what it excluded is a chart that can be quoted against us.

---

## Information architecture and URL scheme

URLs are part of the data contract. They appear in citations, in exported manifests, in the AI
layer's permalinks and in other people's papers. They change only with redirects.

```
/                                    landing
/atlas/                              V1
/coverage/                           V2
/saturation/                         V3
/timeline/                           V4
/compare/                            V5
/gaps/                               V7
/feed/  /feed.xml  /feed.json        V8  (+ /feed/{domain}.xml, /feed/corrections.xml, /feed/ingest.xml)
/ecosystem/                          V9
/suite/                              V10
/benchmarks/                         V11 faceted browse
/browse/{facet}/{term}/              pre-rendered single-facet pages (no-JS path)
/methodology/                        how every published figure is computed (02 §11 rule 1)
/trust/                              the staleness, verification and archive record (00 §7.1 S9)

/benchmarks/{id}/                    V6 canonical detail page
/benchmarks/{id}/v/{version}/        version-pinned detail view
/benchmarks/{id}/claims/             full claims table
/claims/{claim-id}/                  single-claim permalink (the provenance drill-down, standalone)
/conditions/{cond-id}/               a shared EvalConditions record
/systems/{id}/                       a system, as the subject of claims (not a model directory)
/orgs/{id}/                          V9 organisation profile
/metrics/{id}/                       metric definition, range, pitfalls
/taxonomy/{facet}/{term}/            term definition, examples, member benchmarks
/sources/{src-id}/                   a source with its archive link and liveness state
```

### The two pages other documents commit us to

`/methodology/` and `/trust/` are not views in the V-numbered sense and were missing from this
scheme until 2026-09-22, although two other documents make testable commitments about their
contents. They are listed here because a commitment with no URL is a commitment nobody can check.

**`/methodology/`** carries, at minimum: the `density = n_primary + 0.5 × n_secondary` formula and
the weighted-benchmark-count label ([02-taxonomy.md](02-taxonomy.md) §11 rule 1, which requires it
"rendered on the methodology page next to every figure derived from it"); the refusal-to-rank
statement ([12-analytics-and-trends.md](12-analytics-and-trends.md), "belongs on the methodology
page verbatim"); the coverage denominators with their sources and uncertainty; and the taxonomy
definitions. Every figure elsewhere on the site that derives from a published convention links to
the anchor here that defines it.

**`/trust/`** carries the five quantities success criterion S9 in
[00-vision-and-scope.md](00-vision-and-scope.md) §7.1 names: the count of entries unverified for
more than 12 months, the verification mix, mean condition completeness, the failed-archive count
with reasons, and per-source last-successful-fetch dates. S9 is a *test*, not an aspiration, and
it cannot pass against a page that does not exist.

Both are static, both render with JavaScript off, and both take the record-page budget below.

### Filter state encoding

Filter state lives in the query string, canonically ordered so that one selection always produces
exactly one URL. Canonicalisation matters for three reasons: shareable links deduplicate, the
Workers KV cache in [11-ai-features.md](11-ai-features.md) can key on the URL, and a URL in a paper
resolves to the same view a year later.

```
/benchmarks/?c=planning,tool-use&d=robotics-embodiment%2Fmanipulation&em=simulation-rollout
            &hr=0.0-0.8&lc=active,mature&q=bimanual&sort=headroom&v=1

  Rules: keys sorted alphabetically; values sorted within each key; values comma-joined;
         omitted key == no constraint; v=1 is the filter-grammar version.
         There is no key for the presentation group. It is a display-only vocabulary that
         orders and bands views and is not filterable; a user filters by family via `d`.
         Adding a group key requires an ADR.

  d   domain (family or family/subdomain)     lc  lifecycle
  c   capability                              acc access
  em  evaluation_method                       mt  maintainer_type
  s   subject_under_test                      sp  submission_process
  ct  compute_tier                            rt  reproducibility_tier
  hr  headroom range (min-max)                yr  release year range
  q   free-text query                         sort  sort key
  b   basket (suite builder)                  ver   verification threshold
```

Unknown keys are ignored rather than erroring, and unknown *values* render as a visible "ignored
filter: `c=nonexistent-term`" notice. Silent ignoring is how a shared link quietly shows the wrong
thing.

### The permanent citation URL

The live site is always HEAD. The citable object is the YAML at a commit, plus a DOI per release.
Every detail page carries a citation block:

```
Universal AI Benchmark Index. "SWE-bench" [benchmark/swe-bench].
Release v2026.09.1, commit 8f3c9a1e, DOI 10.5281/zenodo.XXXXXXX.
https://<host>/benchmarks/swe-bench/  (accessed 2026-09-17)

  Data at this commit:  https://github.com/<org>/<repo>/blob/8f3c9a1e/data/benchmarks/code/swe-bench.yaml
  Release archive:      https://doi.org/10.5281/zenodo.XXXXXXX
  Formats:              [BibTeX] [CSL-JSON] [RIS] [raw YAML] [Croissant-benchmark JSON-LD]
```

**We do not host frozen historical copies of the site.** The reason is concrete: Cloudflare caps a
deployment at 20,000 files per version, and Pagefind creates one `.pf_fragment` per indexed page
with no fragment-bundling option in 1.5.2 (it exists only as unmerged PR #1020). At 1,500
benchmarks we are at roughly 1,500 HTML + 1,500 fragments + ~30 index chunks + assets, about 3,100
files -- fine. At 10,000 benchmarks that is ~20,200 files and we hit the cap exactly. Multiplying
that by a snapshot per release is not affordable. Durable citation is therefore served by the git
tag plus the Zenodo record, which is both cheaper and more honest: the archived artifact is the
data, not a rendering of it.

Every page footer prints the release tag, commit SHA and build timestamp. A page that cannot tell
you which version of the data produced it is not a citable page.

**Croissant.** Each detail page also emits `croissant-benchmark` JSON-LD in a `<script>` tag. MLCommons
Croissant is the adopted ML-dataset metadata standard -- HuggingFace, Kaggle, OpenML, TFDS and
Google Dataset Search all consume it -- and it has **no evaluation or benchmark extension**.
Publishing a namespaced extension gets us free distribution through Google Dataset Search and
converts the project from a website into a standard. Note the constraint: the Croissant *spec* is
CC BY-ND, so we may publish a namespaced extension but must never republish a modified spec. See
[01-landscape-and-positioning.md](01-landscape-and-positioning.md).

---

## Performance budget

Budgets are per route, enforced in CI as a size gate that fails the build, not as a dashboard
somebody checks occasionally.

| View | JS shipped | Data fetched | Interaction target | Basis |
| --- | --- | --- | --- | --- |
| Landing | <= 40 KB | facets.json 36 KB gz | Interactive < 2 s, mid-range laptop | Astro's ~9 KB baseline plus the filter island |
| V11 Browse | <= 60 KB | facets.json + Pagefind chunks | Filter apply < 16 ms (one frame) over 1,500 rows; first lexical result < 100 ms | Measured: full scan of 1,500 rows is sub-ms |
| V1 Atlas | <= 260 KB (sigma 183 KB + graphology) | atlas.json < 200 KB | 60 fps pan/zoom/filter at 1,500 nodes | sigma is WebGL; Canvas 2D would also hold 60 fps at this size |
| V2 Coverage | <= 100 KB (ECharts tree-shaken) | derived/coverage.json | SSR SVG visible at first paint; hydration < 300 ms | ECharts tree-shaken measured at ~80--100 KB vs ~900 KB naive |
| V3 Saturation Wall | **0 KB** | none beyond HTML | Static | Build-time SVG; ~200 tiles per page |
| V4 Timeline | <= 100 KB | derived/saturation.json | Brush response < 50 ms | ECharts Brush + DataZoom; `ThemeRiverChart` dropped and the nineteen family strips are build-time SVG, so the shipped set is unchanged or smaller -- remeasure in Phase 1 rather than inventing a new number |
| V5 Workbench | <= 120 KB | **corpus.json 0.52 MB brotli, lazy** | Parallel-coordinates render < 200 ms at <= 40 series | Measured corpus: 2.76 MB raw / 0.77 MB gzip / 0.52 MB brotli |
| V6 Detail | **0 KB required** | none | Readable with JS off; HTML <= 60 KB | `<details>` drill-down is native |
| V7 Gaps | 0 KB required | derived/gaps.json | Static table | -- |
| V8 Feed | 0 KB | none | Static | -- |
| V9 Ecosystem | <= 120 KB | derived/ecosystem.json | SSR SVGs at first paint | Six charts, one ECharts instance each; `ChordChart` dropped in favour of the `HeatmapChart` already imported for V2, so the budget is unchanged or lower -- remeasure in Phase 1 |
| V10 Suite | <= 80 KB | reuses facets.json + corpus.json | Recompute panels < 50 ms per basket change | -- |
| Record pages | **0 KB required** | none | Readable with JS off; HTML <= 60 KB | `/orgs/{id}/`, `/systems/{id}/`, `/metrics/{id}/`, `/claims/{claim-id}/`, `/conditions/{cond-id}/`, `/sources/{src-id}/`, `/taxonomy/{facet}/{term}/`, `/browse/{facet}/{term}/`, `/benchmarks/{id}/claims/`, `/benchmarks/{id}/v/{version}/`. Same shape as V6 -- a static record with no island -- so they take V6's budget rather than a separately invented one. The org profile is tables, flags and links; its charts live on V9 |
| `/methodology/`, `/trust/` | **0 KB required** | `derived/trust.json` for `/trust/` | Readable with JS off | Static prose and tables. Both are commitments made by other documents (`00` §7.1 S9, `02` §11 rule 1) and neither had a route until 2026-09-22 |
| Semantic tier | +40 KB code | ~4 MB model + vectors, **lazy, opt-in** | 1--2 ms per query | Measured 0.61 ms at 1,500 x 256, the shipped configuration (08 §5.5); 0.75 ms at 384 is the conservative upper bound |

**Three CI gates enforce this rather than trusting discipline:**

1. **Route size gate** -- per-route JS and HTML budgets from the table above; exceeding one fails
   the build. **It also fails when a route in the URL scheme above maps to no row in that table**,
   which is the half that was missing: the table is indexed by view and the gate is indexed by
   route, so ten record routes had no budget and the gate passed over them silently. A gate whose
   subject list is shorter than the thing it gates is not a gate.
2. **No-JS render gate** -- every route is rendered with JavaScript disabled and asserted to contain
   its required fallback element (the table, list or SVG). A regression here is a citability
   regression, which is a product regression.
3. **Atlas drift gate** -- median per-node displacement against the previous build under 2% of the
   bounding-box diagonal, plus the legibility gate.

Build-time budget: Astro's content layer is roughly 5x faster on Markdown than legacy collections,
and Astro 6 generated 100 MDX pages in about 400 ms; extrapolating, 1,500 mostly-data pages should
be a sub-two-minute cold build, well inside Cloudflare's 20-minute timeout. **No published
real-world benchmark exists in the 1,000--2,000 page range (unverified -- confirm before relying on
this); measure at ~200 pages in Phase 1.** Astro 7.2's `experimental.incrementalBuild` with
`entry.digest` returned as `cacheKey` from the benchmark detail route is the mitigation if it
disappoints.

---

## What we deliberately do not build

Naming the non-goals is as load-bearing as naming the views, because each of these is something a
reasonable person will ask for and each would damage the product.

- **A universal AI score.** No cross-benchmark composite, no "Rosetta Stone" alignment of
  overlapping results onto one scale, no capability index. Every competitor's instinct is to build
  one -- BenchmarkList's Experimental Capability Index, Epoch's ECI, Artificial Analysis's
  Intelligence Index. Headroom consumed is the only shared axis, and it measures position between
  two anchors defined *inside* a domain, not difficulty or importance. The strongest external
  validation of this position came from the biggest ranking operator in open-source AI: HuggingFace
  retired its Open LLM Leaderboard on 2025-03-14 after 13,000+ models, stating that it "was becoming
  obsolete and could encourage people to optimize in irrelevant directions."
- **A leaderboard we run.** We do not execute evaluations in v1. The execution layer is deferred and
  optional ([13-execution-runners.md](13-execution-runners.md)).
- **A model directory.** Systems have pages only because claims need subjects. No model cards, no
  pricing tables, no "best model for X".
- **Predicted or imputed numbers.** No filling a missing cell with a regression, no estimating a
  score on a benchmark a system never ran, no model-generated values anywhere. The AI layer is a
  lens, never a source, and it never produces a number.
- **Animated transitions as decoration.** Motion is used for exactly two things: camera moves in the
  Atlas, and expanding a disclosure. Everything else is instant. A reference work that animates is a
  reference work that is slow.
- **3D anything.** A 3D atlas would be more impressive and less readable. Occlusion is not a feature.
- **User accounts, saved searches, comments and voting.** No auth in v1, by constraint. The URL is
  the saved state; the git repository is the comment thread.
- **Real-time updates.** The site rebuilds on data change. A benchmark index does not need websockets.
- **A chatbot as the front door.** The AI layer is additive and must degrade gracefully; the site
  stays fully useful, readable and citable with it entirely switched off
  ([11-ai-features.md](11-ai-features.md)).
- **In-browser SQL.** Rejected on measurement: DuckDB-WASM's engine is 35.66 MB against a 0.52 MB
  dataset, and its npm `latest` tag pointed at a dev build on 2026-09-17. SQLite stays a build-time-only
  artifact, published as a downloadable release asset -- which is genuinely useful as citable data,
  and never ships to a browser. If a public query console is ever wanted,
  `@sqlite.org/sqlite-wasm` (0.87 MB) is the choice, not `sql.js-httpvfs` (last published
  2022-09-23).

The through-line: every one of these would make the site look more capable and make the index less
trustworthy. The product is the trust.

---

## Open questions carried to [15-open-questions.md](15-open-questions.md)

1. **Atlas layout mode for v1** -- packed by default with embedded as an earned upgrade, or embedded
   from the start? The recommendation above is packed-first; the decision should be made against
   real records in Phase 1, not in advance.
2. **Legibility gate thresholds** -- `neighbourhood_purity >= 0.60` and `domain_silhouette >= 0.15`
   are placeholders requiring calibration on ~200 entries.
3. **Coverage-map default resolution -- settled, and no longer an open question.** The row axis is
   the 19 domain families in declared presentation-group order, and the column axis is the 13
   capability groups enumerated in [02-taxonomy.md](02-taxonomy.md) §4.3, for 247 cells. Both were
   adjudicated on 2026-09-21. What remains is a rendering question rather than a design one:
   **open, to be settled at first render** -- whether 13 horizontal tick labels fit without rotation
   at laptop width in ECharts `MatrixComponent`, and where the labels go if they do not.
4. **Machine-ingested completeness threshold** -- `comparison_floor`, the value at which a
   machine-ingested claim is hidden from comparison views, is a judgement call that should be
   calibrated once the real distribution of `condition_completeness` is measured rather than
   estimated. The constant lives in `taxonomy/thresholds.yaml` and its value is owned by
   [12-analytics-and-trends.md](12-analytics-and-trends.md); this view references it by name so that
   calibration is a one-file change.
5. **Whether the Comparison Workbench needs a server-rendered path at all**, or whether the static
   suite-report degradation is sufficient. Building the SSR path is real work; skipping it is a
   citability compromise in exactly one view.
