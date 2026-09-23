# D4 — The 19-family cascade, and the palette problem

**Status:** decided
**Date:** 2026-09-21
**Owns:** `09-design-system.md` §4.2, §4.5, §4.6, §6.1, §7.1, §7.5, §10, §13; `10-visualization.md` V1, V2, V3, V4, V9/E4, V10, URL grammar
**Depends on:** G1 (19 domain families, canonical). Does **not** depend on the capability-group vocabulary (G5), which is a separate decision; this document fixes the *row* axis of the coverage matrix and is deliberately silent on the *column* axis.

---

## 1. The decision

**Domain family is never encoded by hue. Anywhere. There is no domain-family palette, no
super-group palette, and no `--c-dom-*` token namespace.** Family is carried by position, by a
persistent text label in IBM Plex Sans Condensed, and — when the user asks "where is family X" — by
a single emphasis token applied to one family at a time against a neutral ground.

The 19 families **do** roll up into **six presentation groups**, but the roll-up's job changes
completely: it is no longer a colour key, it is an **ordering and banding device**. It fixes the row
order of the coverage matrix, the containment structure of the packed Atlas, the page order of the
Saturation Wall, and nothing else. It is a **real, ADR-governed vocabulary** living in
`taxonomy/domain_groups.yaml`, marked `display_only: true`, with machine-enforced prohibitions
against it entering the filter grammar, any derived analytics artifact, or any published coverage or
gap number.

`scripts/check_palette.py` is rewritten from "render 18 swatches and check pairwise ΔE" — a check of
a thing that will no longer exist — into a check of what the colour system actually promises: that
the **ordered** encodings (verification, headroom, coverage density) stay monotonic and separated
under three colour-vision deficiencies in both themes, that the **semantic** tokens that can share a
viewport stay mutually distinguishable across *meanings*, that no categorical encoding anywhere
exceeds six simultaneously-visible members, and that the forbidden family-colour namespace does not
reappear.

### Why this is not just "we could not find 19 colours"

The perceptual argument is real but it is the weaker of the two. The decisive argument is
**allocation**. The hue channel in this product is already fully committed to *ordered and semantic*
meanings, and every one of them carries provenance:

| Encoding | Channel spent | Section |
| --- | --- | --- |
| Verification ladder | 6-step blue lightness ramp + segment-count glyph | 09 §4.3 |
| Headroom consumed | 7-stop warm ramp | 09 §4.4 |
| Coverage density | 7-stop cool ramp | 09 §4.4 |
| Contaminated / retracted | `--c-alert` (red ~25) | 09 §4.3 |
| Comparability warning, staleness | `--c-caution` (amber ~75) | 09 §4.5 |
| Verified / passing | `--c-affirm` (green ~150) | 09 §4.5 |
| Link, visited, focus, selection | blue ~250, violet ~300, blue ~255 | 09 §4.5 |

The existing six-hue family palette collides with four of those on hue alone: amber "physical world"
against the warm headroom ramp on the same Saturation Wall page; green "life sciences" against
`--c-affirm`; rose "sociotechnical" against `--c-alert`; blue "symbolic" against the entire
verification ladder, `--c-link` and the coverage ramp. A reader on the coverage matrix would be
holding "amber means physical-world" and "amber means high headroom / caution" in the same eye at the
same time.

So the trade is not "19 distinguishable hues versus 6". It is **family identity versus provenance
identity**, and provenance wins, because provenance is the product. Colour spent making
`chemistry-materials` distinguishable from `biology-genetics` is colour taken from making
`self-reported` distinguishable from `third-party-audited`. Family, unlike verification level, has a
perfectly good non-colour encoding available — its name, which is short, memorable, translatable to
speech, printable, and already required to be on screen by 09 §4.2(c).

### The failure mode of this choice, named

**The views go monochrome and read as unfinished**, and the Atlas specifically loses the
three-second "what is this site" answer that 10 L70–72 assigns it. A grey treemap with labels is a
diagram, not a picture, and a reviewer will say so within five minutes of first render.

The mitigation is *not* to smuggle colour back in. It is that the Atlas's visual interest must come
from the two encodings that are genuinely quantitative and genuinely interesting — node size
(adoption, log-scaled) and fill level (headroom consumed) — plus the small number of alert-coloured
contaminated/retracted nodes, which will look like exactly what they are: scattered red flags across
an otherwise calm field. That is a more arresting first image than a confetti map and it is *true*.

If, on real records in Phase 1, the Atlas still reads as flat, the honest response is to demote it:
10 already calls V2 Coverage Map the "highest research value" view, and a project whose hero is the
gap matrix rather than a node cloud is a project that is advertising its actual differentiator.
Record that as the fallback rather than reopening the palette question.

**Second failure mode: label collision.** Replacing hue with text raises the label budget sharply —
19 family labels, six group labels, plus node labels in the Atlas, all above the hard 11px floor
(09 §3.2) inside a 120rem cap (09 §5.2). If they do not fit, 09 forbids shrinking them. The
scheme must therefore degrade by *density*, not size: group labels always visible, family labels
always visible in the matrix (they are row headers, they have a gutter), family labels in the Atlas
visible at default zoom only where the cluster is wide enough, otherwise on hover and always in the
adjacent family index. This is a real implementation risk and belongs in Phase 1 prototyping.

**Third failure mode: local reinvention.** With no family colour in the token set, the first
contributor who needs to tell two families apart in a one-off chart will invent a hue inline. The
lint rule in §3.6 below is what prevents that, and it is the whole reason the prohibition is
machine-checked rather than written down.

---

## 2. The scheme, in implementable detail

### 2.1 The four channels that carry domain family

**Channel 1 — position (primary).** Family is a *place*. In the Atlas, a family is a contiguous
region. In the coverage matrix, a family is a row at a fixed index. In the Saturation Wall, a family
is a titled block. Position is the strongest categorical channel available at 19 levels, it is
CVD-invariant, it survives greyscale and print, and it is the only channel that scales to 204
subdomains in the expanded view without any redesign.

Position only works if it is **stable across builds**. The row order of the matrix and the
containment order of the Atlas come from the declared order in `taxonomy/domain_groups.yaml`, never
from entry count, never alphabetically. Sorting the matrix by entry count is a *user-invoked,
URL-encoded* option, never the default: a default that reorders whenever curation adds a benchmark
is the Atlas drift failure (10 L95–130) reproduced in a table, and it destroys the spatial memory
that makes a 19-row matrix learnable.

**Channel 2 — the label (always present).** The family label, spelled in full, in Plex Sans
Condensed at `--fs-xs` or above, in `--c-ink` for row headers and `--c-ink-muted` for card metadata.
Never abbreviated, never truncated with an ellipsis, never replaced by a code.

*Two-letter family codes (`RB`, `CM`, `BG`) were considered and rejected.* A 19-code cipher is the
same memorisation burden as 19 hues with none of the pre-attentive benefit, and in a reference work
a reader must not have to decode a label. `robotics-embodiment` is 21 characters; the Condensed face
exists in this design system (09 §3.1) precisely to make labels of that length fit in a matrix
gutter.

**Channel 3 — the band (grouping).** A hairline `--c-border` rule between presentation groups, with
the group name in the left gutter at `--fs-sm` `--c-ink-muted`. This is what replaces the
"the amber region is physical-world stuff" first-order read, and it replaces it with something
better: a label you can read aloud, in greyscale, at 11px, under every CVD, on paper.

**Channel 4 — emphasis (interactive, one family at a time).** Selecting or hovering a family raises
exactly that family to full ink and drops everything else to `--c-ink-faint`, using sigma's
`nodeReducer` in the Atlas and a class toggle everywhere else (no JS recomputation — 09 §12.3).
The emphasised set is marked with a single new token, `--c-emphasis`, used as a 2px rule or outline,
never as a fill on a cell whose fill already carries density.

One emphasis token, not 19. The answer to "where is chemistry-materials" is a highlight, not a
memorised colour, and a highlight answers it faster and more certainly than a hue ever did.

### 2.2 The presentation-group vocabulary

Six groups, 19 families, a strict partition. Renamed from 09's current table to reflect that
membership is now about *adjacency for ordering*, not about hue families.

| # | Group id | Label | Families, in declared order |
| --- | --- | --- | --- |
| 1 | `symbolic-formal` | Symbolic and formal | `language` · `mathematics` · `code` |
| 2 | `reasoning-general-ability` | Reasoning and general ability | `reasoning-general` · `general-intelligence` · `games-planning` |
| 3 | `perception-generation` | Perception and generation | `vision` · `audio-speech` · `multimodal` |
| 4 | `physical-engineered` | Physical and engineered systems | `robotics-embodiment` · `physics` · `engineering-design` · `earth-climate` |
| 5 | `life-health` | Life and health sciences | `chemistry-materials` · `biology-genetics` · `medicine-health` |
| 6 | `society-safety` | Society and safety | `agents-tooluse` · `safety-alignment` · `society-econ-law` |

Three changes against the table currently at 09 L252–259, all forced by G1:

- **`engineering-design` is added**, to `physical-engineered`. It is the family the existing table
  silently omits, which is how an 18-row table survived a 19-family taxonomy for this long. Its
  subdomains (`cad-geometry-generation`, `circuit-eda`, `structural-mechanical-design`,
  `process-control-optimization`, `experimental-apparatus-design`, `lab-automation-execution`) are
  the design and control of physical artefacts; `physical-engineered` is the only defensible home.
  Group 4 therefore has four members and the others have three. Under a colour scheme that would
  have meant a fourth lightness step at a ~0.09 L interval, below the reliable discrimination floor
  at mark size. Under an ordering scheme it means nothing at all — which is itself an argument for
  the ordering scheme.
- **`chemistry` → `chemistry-materials`.** The current table uses the pre-rename slug (02 §3
  changelog), so it would not have resolved against `taxonomy/domain.yaml` even at 18.
- **The `Hue` column is deleted.** There is no hue.

**Group order** (top to bottom in the matrix, left to right / outside in in the Atlas) is the numbered
order above: formal → general reasoning → perception → physical → life → society. It runs roughly
from the most abstract substrate to the most embedded-in-the-world, which is a defensible reading
order and, more importantly, a *fixed* one.

**Membership disputes are now cheap.** Whether `games-planning` belongs with reasoning or with
agents is arguable; under the old scheme that argument determined a benchmark's colour and therefore
its apparent kinship in the hero view. Under this scheme it determines which of two adjacent rows it
sits between. Demoting the roll-up from colour key to ordering key converts a class of
unresolvable design arguments into a class of trivial ones. State that in 09; it is the main
non-obvious benefit.

### 2.3 Governance: a real vocabulary, display-only, machine-fenced

The current guard rail (09 L264–268) says the grouping is "a presentation device only", must not
appear in `taxonomy/`, and should be recorded in `design/tokens.yaml` "with that warning in a
comment". **That is the worst available option and it must be reversed.** A grouping that determines
the row order and band structure of the two highest-value views is load-bearing. Putting it in a
design file with no ADR, no changelog, no definitions and no CI relationship to the family list is
exactly the arrangement that produced the 18/19 discrepancy this decision exists to clean up: the
palette table had no mechanical link to the domain vocabulary, so when `engineering-design` was added
nothing failed.

**Decision: it is a real vocabulary, under the same ADR governance as every other vocabulary, at
`taxonomy/domain_groups.yaml`**, with a `display_only: true` flag and four enforced properties:

1. **Total partition.** Every family in `taxonomy/domain.yaml` appears in exactly one group; no group
   contains a slug that is not a family. Adding a 20th family without assigning it a group fails CI
   in the same commit. This is the check that closes the root cause.
2. **No filter key.** The URL grammar (10 L963–976) has no key for it, and adding one requires an
   ADR that supersedes this decision. A user can filter by family; there is no `?g=life-health`.
3. **Not in analytics.** The group id may appear in `atlas.json` (as a derived display field) and in
   rendered HTML. It is forbidden in `facets.json`, `corpus.json`, `derived/coverage.json`,
   `derived/gaps.json`, `derived/ecosystem.json`, the exported `suite.yaml`, and the Croissant
   JSON-LD. Every coverage percentage, density figure, gap score and curation-confidence value is
   computed over families and subdomains, never over groups.
4. **Never in a claim sentence.** No rendered sentence of the form "N benchmarks measure X in
   *Life and health sciences*". The gap-narration template (10 L276–280, reused verbatim by
   11-ai-features) names a family or a subdomain, never a group.

Properties 1 and 3 are checkable and should be; a new eight-line `scripts/check_display_only_vocab.py`
asserting the partition and grepping the derived JSON artifacts for group ids is sufficient. It
belongs in the CI list in `05-repository-and-workflow.md` alongside the other vocabulary checks —
**flagged for whoever owns 05**, since this document does not edit it.

Property 4 is not mechanically checkable and is therefore a review rule stated in 09 §11.

The reason to take the harder governance path rather than the lighter one: a display-only grouping
that leaks into a published gap claim is a data-integrity failure that is invisible in the diff. If
someone aggregates the coverage matrix to six rows and publishes "nobody measures
`calibration-uncertainty` in the life sciences", that sentence has a denominator built from an
ungoverned, undocumented, uncited grouping, and a specialist who disputes the grouping has
invalidated the finding without touching the data. Governance is cheaper than that retraction.

### 2.4 Token changes

**Delete** the entire `--c-dom-*` block (09 L424–429): six hues × three steps, eighteen tokens plus
the generating comment.

**Add** two tokens and one comment fence:

```css
  /* ---------- emphasis: one selected family/row/cluster at a time ---------- */
  --c-emphasis:    oklch(48.0% 0.16 300);   /* ≥ 3:1 vs --c-bg AND vs --c-ink-faint (SC 1.4.11) */
  --c-emphasis-bg: oklch(95.0% 0.035 300);  /* row-tint only where no density fill is present */

  /* ---------- PROHIBITED NAMESPACE ----------------------------------------
     There is no --c-dom-* / --c-family-* / --c-group-* token and there must
     not be one. Domain family is encoded by position, label and band; see
     §4.2. scripts/check_palette.py fails the build if this namespace returns.
     ------------------------------------------------------------------------ */
```

Hue ~300 for emphasis is chosen deliberately: it is the one region of the wheel not already carrying
an ordered meaning (blue ~250 verification/link/coverage, amber ~65–85 headroom/caution, green ~150
affirm, red ~25 alert). It collides with `--c-link-visited` (violet ~300) at similar lightness, so
the CI check in §3 must include that pair — and if it fails calibration, move emphasis to ~330
rather than moving any ordered ramp.

Dark theme: both tokens re-authored, not inverted (09 §9). `--c-emphasis` in dark lands near
`oklch(78% 0.14 300)`; the exact value is set by the contrast check, not by hand.

A useful side effect worth recording in 09 §9: deleting the family tokens removes 18 of the tokens
the dark theme had to re-author and re-test. The dark theme's remaining colour work is three
sequential ramps plus the semantic states.

### 2.5 The Atlas (V1), concretely

Default state, packed layout (10 L165–177 already recommends packed for v1 and this scheme
strengthens that recommendation, because banding needs a deterministic containment structure that a
UMAP embedding cannot guarantee):

- **Two-level squarified treemap**: six group rectangles, each containing its 3–4 family rectangles.
  Rectangle areas from benchmark count, so `vision` and `medicine-health` are visibly large and
  `engineering-design` is visibly small — which is an honest statement about the index and doubles as
  a curation-coverage signal. The current keying "domain → subdomain → capability" (10 L166) becomes
  **group → family → subdomain**; capability is a facet, not a containment level, and having it in a
  containment chain was a quiet third-hierarchy problem of its own.
- **Ground:** `--c-bg`. Family and group rectangles have no fill, only `--c-border` outlines at 1px
  (family) and `--c-border-strong` at 1px (group).
- **Labels:** group name at `--fs-sm` `--c-ink` in the rectangle's top-left; family name at `--fs-xs`
  Plex Sans Condensed `--c-ink-muted` in each family rectangle's top-left. Where a family rectangle
  is too narrow for its label at 11px, the label moves to a leader line into the margin; it never
  shrinks and never disappears.
- **Nodes:** neutral `--c-ink-muted` outline, size = adoption (log), **fill level** = headroom
  consumed. Colour appears on a node in exactly two cases: `contaminated` and `retracted` take
  `--c-alert`, and `saturated` takes the top stop of the headroom ramp (which is what "full" already
  means). All other lifecycle states are neutral. **This corrects a direct 09/10 conflict**: 10 L81
  currently says node colour is lifecycle across all nine terms, while 09 §4.3 colours only three of
  nine, for the stated reason that nine coloured states means none of them is signal. 09 wins on
  rendering (09 L8). Without this correction the scheme just moves the 19-hue problem to a 9-hue
  problem.
- **The legend is a family index, not a colour key.** A 19-row list beside the map: group headings,
  family label, benchmark count, and a highlight toggle per row. This one artefact is simultaneously
  the legend, the no-JS grouped list (10 L207–211), the screen-reader linearisation and the roving-
  tabindex target (09 §8.2). Four requirements, one component, zero colour swatches.
- **Emphasis:** hovering or selecting a family (on the map or in the index) applies `--c-emphasis` to
  that family's rectangle outline and keeps its nodes at full ink and label; every other node drops to
  `--c-ink-faint` and loses its label via `nodeReducer`. Filtering never moves a node (10 L186–189),
  unchanged.

If the embedded UMAP layout later earns its place through the legibility gate, the banding degrades
to convex-hull outlines per family plus a group-level hull, same labels, same emphasis behaviour,
same legend. Nothing else changes — which is another argument for a scheme whose only spatial
requirement is "same-family things are near each other", a property the gate already measures
(`neighbourhood_purity`, `domain_silhouette`, 10 L155–161).

### 2.6 The coverage matrix (V2), concretely

- **19 rows, one per family**, in the declared group order, banded: a 1px `--c-border` rule between
  groups and the group label in the left gutter at `--fs-sm` `--c-ink-muted`, set vertically or in a
  dedicated 6rem gutter column. Row height is uniform; groups are separated by `--sp-2`, not by a
  blank row.
- **Row header:** family label, Plex Sans Condensed, `--fs-sm`, `--c-ink`, left-aligned, plus the
  family's curation-confidence bar in the header gutter (10 L272). The header is a link to
  `/browse/domain/{family}/`.
- **Columns:** capability, at the resolution set by the capability-group decision (G5). This
  document asserts the row count is 19 and says nothing about the column count, except that the
  binding legibility constraint on the default view is now the *column* axis, because 19 rows is a
  comfortable table height and the row axis is no longer in question.
- **The only colour in the plot area is the cool coverage-density ramp.** This is the payoff. Under
  the old scheme the matrix would have carried coloured row headers competing with density fills, and
  10 L273 already forbids the obvious resolution (a bivariate choropleth multiplying density by
  something else). With family carried by position and text, the colour channel in the most valuable
  view in the product has exactly one meaning.
- **Cell states unchanged** (09 §4.4, 10 L253–256): zero = 45° 2px hatch in `--c-absent-hatch` plus a
  `0` label; 1–2 = lightest ramp stop plus count; 3+ = ramp plus count; not-applicable = dotted
  border, no fill, `n/a`; not-yet-curated = diagonal slash plus `?`.
- **Resolve the hatch collision.** 09 §4.4 allocates the 45° hatch to *zero coverage*; 10 L271–274
  independently allocates a "diagonal hatch overlay" to *low curation confidence*. Two hatches in one
  matrix at cell size are not distinguishable, and the absence vocabulary is the one vocabulary that
  must stay unambiguous (Rule 3). Under this scheme patterns carry more load than before, so the
  collision must be resolved now: **curation confidence keeps the row-gutter bar and the tooltip
  sentence and loses its per-cell overlay**, replaced where a per-cell mark is genuinely needed by a
  4px `--c-ink-faint` triangular tick in the cell's top-right corner. Different shape class, no
  confusion with the absence patterns.
- **Emphasis:** hovering a row applies a 2px `--c-emphasis` left rule and sets the row header
  semibold. **It never changes a cell fill** — the fill is the density read and corrupting it during
  hover would make the view lie on hover. Column emphasis behaves identically at the top.
- **Expanded view:** clicking a family expands that family's row into its subdomains (11–18 rows for
  the large families) in place, indented under the family header, same ramp, same rules. The group
  band stays. No colour is introduced at the subdomain level either; at 204 subdomains the question
  does not even arise.
- **No-JS table:** a real `<table>` where each presentation group is a `<tbody>` carrying
  `<th scope="rowgroup">` with the group label, and each family row a `<th scope="row">` with the
  family label. The banding is thereby not a visual affectation but the accessible structure of the
  table, and a screen reader announces "Life and health sciences, biology-genetics, causal-reasoning:
  4 benchmarks". This is the clearest single piece of evidence that the scheme is better than a
  palette: a colour band has no accessible expression at all.

### 2.7 The other places all 19 are simultaneously visible

**V3 Saturation Wall** (10 L312–318). Grouped by family, blocks ordered by the declared group order,
each block titled with the family name and each group preceded by a group heading. Sparkline strokes
stay `currentColor`; the uniform-y-domain-within-a-group rule (09 §7.5) now unambiguously means
*domain family*, and the group heading states it when a family's y-domain differs from the global
one. No change of substance, but 09 §7.5's wording must say family, not "domain-family group", which
is now ambiguous between the two levels.

**V4 Frontier Timeline** (10 L388–390, L414–417). The "stacked-stream underlay showing release volume
by domain over time" is a 19-band ThemeRiver, which is a 19-category colour encoding by another
name — and a 19-band theme river is an unreadable chart at any palette. **Replace it with a
small-multiples strip set: one filled area strip per family, 19 strips, shared x axis, one neutral
fill, direct-labelled, ordered and banded by group.** This is strictly more readable than a
19-band river, it is consistent with V3's small-multiples approach, it needs no categorical colour,
and it drops `ThemeRiverChart` from the ECharts import set.

Same section, adjacent and required for the same reason: the two release bands are "coloured by
organisation" with colour "capped at the top twelve organisations plus other" (10 L415–417). Twelve
categorical hues directly contradicts 09 L768 ("Hue carries at most 6 series. Beyond six,
direct-label and grey the rest"), which is the general form of the rule this decision applies to
families. Fix it the same way: marks are neutral, the top six organisations by release count are
direct-labelled, the rest are grey and labelled on hover and in the table. *This is adjacent to D4's
remit rather than inside it, but it is the same perceptual limit and it is a live contradiction
between the two documents, so it is listed in §5.*

**V9/E4 Domain attention flow** (10 L707, L739). An organisations → domains chord diagram at 19
domain arcs plus N organisation arcs is the worst case in the document: it needs a categorical colour
per arc and it is hard to read even when it has one. **Replace the chord with an organisation ×
family heatmap** using the same cool density ramp and the same banded 19-row structure as V2. It
answers E4's stated question — "where is measurement effort going" — with magnitude, which is the
actual quantity of interest, and it reuses V2's machinery, its ECharts imports, its no-JS table
generator and its accessibility structure. The loss is real and should be stated: a chord shows
bilateral flow and the heatmap does not, so "which organisations moved between domains" is answered by
the year slider stepping the heatmap rather than by a ribbon. `ChordChart` drops from the ECharts
import set.

**V10 Suite Builder mini-matrix** (10 L787–790). A miniature of V2 restricted to the basket: same 19
banded rows, same ramp, covered cells filled, target cells outlined in `--c-emphasis`. Families with
no basket entries render as empty banded rows rather than being omitted — omitting them would make
absence look like completeness, which is the exact failure the "Not covered" panel exists to prevent.
Where vertical space forbids 19 rows, collapse to the groups **visually only**, and label the
collapsed rows "4 families, 0 entries" rather than printing a group-level coverage number.

**V6 Benchmark cards and detail pages.** `<BenchmarkCard>` currently specifies a "domain swatch/label
lockup" (09 L528). The swatch is deleted; the lockup becomes the family label in Plex Sans Condensed
`--fs-xs` `--c-ink-muted`, followed by the subdomain. Facet chips are already colourless
(`<FacetChip>`, 09 §6.2) and need no change.

---

## 3. The rewritten CI check

`scripts/check_palette.py` — **keep the filename.** It is referenced in 09 §4.2, 09 §13 and the CI
config; renaming it to something more accurate buys nothing and creates three more edits. Change its
docstring to "colour-system invariants" and leave the path alone. Do not rename it.

The check reads `design/tokens.yaml`, resolves both themes, and runs six assertion groups. It writes
`build/reports/palette.json` with every computed number so the thresholds are auditable rather than
folkloric, and exits non-zero naming each failure as `(token_a, token_b, theme, simulation, measured,
threshold)`.

All thresholds live in `tokens.yaml` under a `thresholds:` key, not as constants in the script. A
number in a script is a number nobody can find; a number in the token file is reviewable in the same
diff as the colours it governs.

### Dependencies and method

`colorspacious` for CVD simulation and CAM02-UCS ΔE; `coloraide` (or equivalent) for OKLCH → sRGB
conversion. Simulations, each applied to both themes:

```python
CVD = [
  {"name": "sRGB1+CVD", "cvd_type": "deuteranomaly", "severity": 100},  # deuteranopia
  {"name": "sRGB1+CVD", "cvd_type": "deuteranomaly", "severity":  50},  # the common case, ~6% of men
  {"name": "sRGB1+CVD", "cvd_type": "protanomaly",   "severity": 100},  # protanopia
  {"name": "sRGB1+CVD", "cvd_type": "tritanomaly",   "severity": 100},  # tritanopia
]
```

Severity 50 deuteranomaly is included deliberately: full dichromacy is the standard test and the rare
case, and a palette tuned only for severity 100 can still fail the far more common anomalous
trichromacy. *(Whether `colorspacious`'s anomaly model is well calibrated at severity 50 is
unverified — confirm before relying on this; it is a Machado-style model and the intermediate
severities are interpolations.)*

### Group A — the prohibited namespace

Fail if any token id in `tokens.yaml` matches `^c-(dom|domain|family|group)-`, in either theme. Fail
with the message: "Domain family is not colour-encoded (09 §4.2, decision D4). Encode it by position,
label or band."

This is the assertion that makes the decision durable. Everything else in this document is prose
somebody can quietly ignore; this line fails the build.

### Group B — categorical sets are declared and bounded

`tokens.yaml` gains a `categorical_sets:` block. Every set that renders as simultaneously-visible
categories declares its members and, per member, a `redundant_channel` (one of `glyph`, `pattern`,
`label`, `position`, `count`). Assertions:

- No set has more than **6** members. This mechanises 09 §7.1.
- Every member declares a non-empty `redundant_channel`. This mechanises 09 §4.1 rule 1 — colour is
  never the sole carrier of meaning — which is currently a sentence nothing enforces.
- Pairwise within each set: CAM02-UCS ΔE ≥ `thresholds.delta_e_categorical` (start **15**) under every
  simulation in both themes.

After this decision the only categorical sets remaining are small: the three coloured lifecycle states,
and whatever V4 and V9 declare for their direct-labelled series. That is the point.

### Group C — ordered ramps stay ordered

For each of `verif-1..6`, `seq-head-0..6`, `seq-cov-0..6`, in both themes and under every simulation:

- **Monotonic** in perceived lightness, strictly, in the declared direction. Lightness is largely
  CVD-invariant but the tritanomaly model perturbs it, so assert it rather than assume it.
- **Adjacent step delta** ≥ `thresholds.ramp_step_l` (start **0.055** in OKLCH L, i.e. 5.5 percentage
  points). The current declared ramps sit at 0.06–0.12, so this passes today with margin.
- **End-to-end range** ≥ `thresholds.ramp_range_l` (start **0.45**). The current coverage ramp is
  0.96 → 0.37 = 0.59; headroom is 0.96 → 0.43 = 0.53; verification is 0.70 → 0.38 = 0.32 and
  **fails**. That is a genuine finding, not a threshold to relax: a six-step ramp across 0.32 L gives
  0.064 per step, which is right at the floor, which is precisely why 09 §4.3 gives verification a
  segment-count glyph as its primary channel. Resolution: mark the verification ramp
  `primary_channel: count` in `tokens.yaml` and exempt it from the range assertion while keeping it
  under the step assertion. Record the exemption in the token file with the reason, so the next person
  does not "fix" it by stretching a ramp whose job is secondary.

ΔE between *adjacent* stops of a sequential ramp is the wrong test and must not be used: adjacent
stops of a ramp are supposed to be similar. Monotonicity plus step size plus range is the correct
family of tests, and the old check's single ΔE floor could not express it.

### Group D — cross-meaning separation (the check that replaces the old one)

The failure this actually guards against is not "two family colours look alike" — there are no family
colours now. It is **two different meanings wearing the same colour in one viewport**, which is a live
risk in this token set: `--c-caution` (amber ~75) against `--seq-head-3/4` (amber ~66/55);
`--c-affirm` (green ~150) against nothing yet but against any future green; `--c-emphasis` (violet
~300) against `--c-link-visited` (violet ~300); `--c-link` (blue ~250) against `--seq-cov-4/5` (blue
~242/246) and against `--c-verif-4/5`.

`tokens.yaml` gains a `co_occurrence:` block listing which meaning-groups can share a viewport — for
example `[coverage-ramp, semantic-states, interaction, absence]` for the coverage matrix,
`[headroom-ramp, verification-ramp, semantic-states, interaction]` for the Saturation Wall and the
entry page. For every pair of tokens drawn from *different* meaning-groups that co-occur:

- CAM02-UCS ΔE ≥ `thresholds.delta_e_cross_meaning` (start **15**) under every simulation, both themes.
- **Or** OKLCH L difference ≥ 0.10, **or** both tokens declare distinct `pattern` values. The
  disjunction is deliberate: two tokens that differ strongly in lightness, or that are separated by
  hatch versus solid, are distinguishable in greyscale and in print, which is the property that
  actually matters for a document someone will print or cite.

15 is provisional and must be calibrated against real renders in Phase 2 (this was already an open
question in 09 §13 and stays open, now scoped to cross-meaning pairs). Record the calibrated value in
`tokens.yaml`; do not guess it twice.

### Group E — contrast, at the values 09 §4.6 already commits to

Computed with the WCAG 2.x relative-luminance formula on the sRGB rendering of each token, both themes:

- Body text, chip text, table cells, badge labels, axis tick labels on their declared grounds: **≥ 4.5:1**.
- Large text (≥ 24px, or ≥ 18.66px bold): **≥ 3:1**.
- Non-text: borders, chart marks, meter segments, ramp stops against `--c-bg` and against
  `--c-surface`, the absence hatch against its ground, the focus ring against both the element and its
  surround: **≥ 3:1**.
- `--c-emphasis` against `--c-bg` **and** against `--c-ink-faint` (the dimmed ground it must be seen
  against): **≥ 3:1** each. This pair is new and is the one the emphasis mechanism depends on
  entirely; if it fails, the whole focus-plus-context scheme fails silently.
- `--c-ink-faint` is asserted **never** to appear in a text-role declaration. Currently a lint-by-
  selector rule (09 L445); assert it here too, in the token file, where the role is declared.

`check_contrast.py` already exists and already covers ink-on-surface pairs (09 §4.6). Keep the split:
`check_contrast.py` owns text contrast, `check_palette.py` owns non-text marks, CVD and cross-meaning
separation. Do not merge them; two fast focused checks report better than one slow one.

### Group F — greyscale and forced-colors survivability

- Convert every token to CIE Y only. Every cross-meaning pair from Group D must retain a greyscale
  contrast ratio ≥ **1.4:1** or declare distinct patterns. This is the print check, and the
  Saturation Wall and the coverage matrix will be printed.
- Assert that every `categorical_sets` member and every absence state declares a `pattern` or `glyph`,
  because under `forced-colors: active` (09 §8.5) all declared colour is discarded by the OS. The
  scheme has an unusual property worth stating in 09: **because domain family is never colour-encoded,
  forced-colors mode loses nothing about family at all.** That is a claim the old palette could not
  make, and it should be written down where the next person can find it.

### Exact pass condition

The build passes when, for both the light and dark token sets, under all four CVD simulations:

1. no token id matches the prohibited family/group namespace;
2. every declared categorical set has ≤ 6 members, every member declares a redundant channel, and all
   within-set pairs are ≥ ΔE 15 (CAM02-UCS);
3. every ordered ramp is strictly monotonic in lightness, with adjacent steps ≥ 0.055 L and total
   range ≥ 0.45 L except where the ramp declares `primary_channel: count`;
4. every cross-meaning co-occurring pair is ≥ ΔE 15, or ≥ 0.10 L apart, or pattern-distinguished;
5. every declared text pair ≥ 4.5:1 (≥ 3:1 large), every non-text mark ≥ 3:1 against its declared
   grounds, and `--c-emphasis` ≥ 3:1 against both `--c-bg` and `--c-ink-faint`;
6. every cross-meaning pair is ≥ 1.4:1 in greyscale or pattern-distinguished, and every categorical
   member and absence state declares a pattern or glyph.

Runtime should be well under a second — a few hundred token pairs, four simulations, two themes.
There is no rendering step, no screenshot and no image diff; the old check's word "renders" was
doing no work and the new one should not inherit it.

---

## 4. Reasoning, and the alternatives rejected

**A 19-hue qualitative palette.** Rejected without ceremony: it does not exist. The practical ceiling
for reliable categorical identification by hue is around eight for normal colour vision and materially
fewer under deuteranomaly, and 09 already concedes that 18 fails. Nineteen is strictly worse. The only
thing worth adding is that the concession was never followed to its conclusion — 09 conceded the
premise and then specified a palette anyway.

**Keep the six-hue super-group palette, add a seventh hue or a fourth lightness step.** This is the
tempting option, the one that requires the least editing, and it is the one to argue against hardest.
Three reasons. (i) **Arithmetic.** Nineteen does not fit 6×3. A fourth step in `physical-engineered`
compresses that hue's lightness interval from ~0.125 to ~0.09, which is unreliable at node size and at
the 11px label floor, and a seventh hue puts two hue families within ~35° of each other, which fails
under deuteranopia before any tuning begins. (ii) **Allocation** — the collision table in §1. Hue in
this product is already spent on five ordered meanings that carry provenance, and family competes with
all of them. (iii) **Epistemics.** A colour legend that groups families is read as a level of the
taxonomy. 09's own guard rail says so, and 09's own §13 records "the risk is that it starts being
cited as a taxonomy level" as an unresolved worry. A scheme whose stated risk is "it may corrupt the
data model" should not be the default scheme; it should be the rejected one.

**Direct labelling with no colour encoding at all, and nothing else.** This is most of the
recommendation and it is right as far as it goes, but taken alone it under-specifies two jobs:
"where is family X in this view" (answered by emphasis, channel 4) and "which families belong
together" (answered by banding, channel 3). Labels alone give a 19-row matrix with no visual
structure, which is legible but not *learnable*. Position and banding are what make it learnable.

**Interactive highlight-on-hover against a neutral ground, and nothing else.** Insufficient alone for
the opposite reason: it answers "where is family X" excellently and "what is the shape of this field"
not at all, and the latter is V1's entire stated purpose (10 L70–72) and the reason the Atlas is the
hero. It also fails without JavaScript, on paper, and in a screenshot in someone's paper — three
contexts this project has explicitly committed to serving (09 §8.6, 10 L21–27). It is a necessary
channel, not a sufficient scheme.

**Colour reserved entirely for non-categorical encodings, family carried by text.** Accepted; this is
the recommendation, augmented with position, banding and emphasis so that the two jobs above are
covered.

**Pattern or texture per family.** Nineteen hatch angles and dot densities. Rejected: texture is less
discriminable than hue above roughly four categories, it moirés at node size and at matrix cell size,
it renders unpredictably at fractional device pixel ratios, and — decisively — the pattern channel is
already allocated to the absence vocabulary (hatch = zero, slash = not curated, dotted = not
applicable, 09 §4.4). Absence rendering is Rule 3 and the one vocabulary that must never be
ambiguous. Spending patterns on family would break it.

**A pictogram per family.** Nineteen icons. Rejected: it is a recurring design project with no
in-house designer and a 1–2 person part-time team; `reasoning-general` and `general-intelligence`
cannot be drawn distinguishably, nor can `physics` and `chemistry-materials`; 09 §12.3 constrains
icons to an inline SVG sprite with a tight budget; and icons are a second cipher for the same reason
two-letter codes are. The glyph budget in this system is already committed to meaning-bearing marks
(∅, ▲, →, the verification segments, the disputed warning).

**Let the user choose the encoding.** A settings panel offering "colour by family / by lifecycle / by
headroom". Rejected: it makes every screenshot ambiguous and every shared URL a different picture,
which contradicts the fixed-locale, one-screenshot-means-one-thing posture at 09 §11.4. The one
sanctioned variable encoding is the V2 measure toggle (raw count / weighted density / claim density),
and it is sanctioned because the toggle's state is in the URL and stated in the caption.

**What this decision does not decide.** The capability-group vocabulary (G5) and therefore the column
count of the default coverage view; the calibrated ΔE thresholds, which need real renders in Phase 2;
whether the Atlas ships packed or embedded, which 10 defers to Phase 1 against real records; and
whether the emphasis mechanism needs a group-level highlight in addition to the family-level one,
which should be answered by watching people use the prototype rather than by argument.

---

## 5. EDITS REQUIRED, BY FILE AND LINE

Line numbers are against the files as of 2026-09-21. Edits are listed in file order. Where another
decision owns an overlapping number correction, it is marked.

### `09-design-system.md`

| Line(s) | Edit |
| --- | --- |
| **104** | "axis labels on an 18 × 40 matrix" → "axis labels on a 19 × 44 matrix, and on the 204-subdomain expanded view". *(G1/G2/G3 number correction; also load-bearing here because the Condensed face is now the primary family-label carrier — say so.)* |
| **239** | Heading "### 4.2 Domain family — the 18-category problem, stated honestly" → "### 4.2 Domain family — why it is not colour-encoded". |
| **241–245** | Replace wholesale. New text states: there are 19 domain families; no qualitative palette at that cardinality is safely distinguishable, but the decisive reason is allocation, not perception — the hue channel is already fully committed to five ordered and semantic meanings that carry provenance (list them, per §1 of this decision). Domain family is therefore encoded by position, label, band and emphasis, and there is no domain-family palette. |
| **247** | "The strategy is three-part." → "Four channels carry family, none of them hue." |
| **249–262** | Delete the "(a) Group to six, vary lightness within the group" heading, paragraph and table (including its `Hue` column). Replace with the four-channel description (§2.1) and the presentation-group table from §2.2 of this decision — six groups, 19 families, `engineering-design` added to `physical-engineered`, `chemistry` → `chemistry-materials`, no `Hue` column, an explicit "declared order, build-stable, never sorted by entry count" note. |
| **264–268** | Replace the guard rail block. New text: the grouping is a **real vocabulary** at `taxonomy/domain_groups.yaml` under ADR governance, flagged `display_only: true`, with the four enforced properties from §2.3 (total partition; no filter key; forbidden in every derived analytics artifact except `atlas.json`; never in a rendered claim sentence). Explicitly reverse the current instruction to record it in `design/tokens.yaml` — and state the root cause: the palette table had no mechanical link to the family list, which is why an 18-row table outlived a 19-family taxonomy. |
| **270–276** | Relabel "(b)" as the primary mechanism rather than one of three. "eighteen-at-once" → "nineteen-at-once"; "eighteen hues at 40% opacity" → "nineteen hues at 40% opacity". Add the `--c-emphasis` token by name and state that exactly one family is emphasised at a time. |
| **278–280** | "(c) Hue is never the identifier" → "(c) Hue is never applied". Delete the final sentence "A user who cannot distinguish amber from green loses nothing except speed" — there is no amber or green to distinguish, and the sentence now understates the position. Replace with: under `forced-colors: active`, in greyscale and in print, nothing about family is lost, because nothing about family was in colour. |
| **282–286** | Replace the entire CI-check paragraph with a pointer to the rewritten check and a one-paragraph summary of its six assertion groups (§3). Keep the sentence that the ΔE threshold is empirical and must be calibrated in Phase 2, rescoped to cross-meaning pairs. Keep the filename `scripts/check_palette.py`; state explicitly that it is not renamed. |
| **424–429** | Delete the `--c-dom-symbolic-1/2/3` declarations and the generating comment. Insert the `--c-emphasis` / `--c-emphasis-bg` tokens and the PROHIBITED NAMESPACE comment fence, verbatim from §2.4. |
| **438–443** | In the §4.6 contrast table, add one row: `| 3:1 | 1.4.11 | the emphasis rule or outline, against both --c-bg and the dimmed --c-ink-faint ground |`. |
| **~449 (end of §4.6)** | Add one sentence delimiting the two checks: `check_contrast.py` owns text contrast; `check_palette.py` owns non-text marks, CVD simulation and cross-meaning separation. |
| **528** | `<BenchmarkCard>` layout: "name … + domain swatch/label lockup on one line" → "name … + family label in Plex Sans Condensed on one line". Delete "swatch". |
| **768** | §7.1 "Hue carries at most 6 series." Keep, and append: "Domain family is never one of those series (§4.2), and neither is organisation — see 10 V4." |
| **819–820** | §7.5: "Uniform y-domain within a domain-family group" → "Uniform y-domain within a domain **family**", and add that Saturation Wall blocks are ordered and banded by presentation group with the group name as a heading, no colour. |
| **855–857** | §8.2 Atlas keyboard: add that the linearised node list *is* the family index that serves as the legend, and that it carries the group headings as the first level of the roving order. |
| **898–900** | §8.5 `forced-colors: active`: add one sentence recording that family encoding survives this mode intact by construction, because it never used colour. |
| **~946–948** | §9 dark mode: add one sentence noting that deleting the 18 family tokens removes them from the dark theme's re-authoring and re-testing burden, leaving three ramps plus the semantic states. |
| **977** | §10 responsive table, Coverage matrix row: "18 × ~40 heatmap" → "19 × capability-group heatmap, banded by presentation group". The phone replacement (ranked gap list + per-family drill-down) is unchanged and correct. |
| **1123** | §13 CI table, `check_palette.py` row: "Two co-occurring swatches below the ΔE floor under deuteranopia / protanopia / tritanopia" → "A family-colour token reappearing; a categorical set above 6 members or missing a redundant channel; a non-monotonic or under-stepped ordered ramp; two co-occurring tokens of *different meaning* below the ΔE floor, the lightness floor and the pattern exemption, under deuteranopia / deuteranomaly-50 / protanopia / tritanopia in both themes". |
| **1124** | §13 CI table, `lint_tokens.mjs` row: append a fourth failure condition — "any component CSS rule keyed on `[data-domain-family]` or `[data-domain-group]` that sets `color`, `background`, `background-color`, `fill` or `stroke`". This is the regression guard that stops family colour being reinvented locally. |
| **1133–1137** | §13 "What this document does not decide": keep the ΔE item, rescoped to cross-meaning pairs. **Delete** the clause "and whether the six-group domain colouring should ever be exposed as a user-selectable grouping in the Atlas legend (the answer is probably yes, and the risk is that it starts being cited as a taxonomy level)" — answered by this decision: there is no six-group colouring, the grouping is exposed as banding and as the Atlas family index, and it is governed. Replace with the residual question: whether emphasis needs a group-level mode in addition to the family-level one. |

### `10-visualization.md`

| Line(s) | Edit |
| --- | --- |
| **46** | ECharts import list: `ThemeRiverChart` and `ChordChart` are no longer required (see V4 and E4 below). Remove both from the "ships …" enumeration or mark them as available-but-unused; the "four of our four required chart types are built in" claim survives either way. |
| **77–79** | V1 Position: add that the packed layout's containment is **group → family → subdomain**, and that group and family regions carry hairline outlines and labels rather than fills. |
| **81–84** | V1 Node colour: **correct the 09/10 conflict.** Replace "lifecycle status (nine terms listed)" with: nodes are neutral; fill level carries headroom consumed; colour appears only for `contaminated` / `retracted` (`--c-alert`) and `saturated` (top headroom stop), per 09 §4.3, which colours three of nine lifecycle terms on the grounds that nine coloured states means none is signal. Keep the existing and correct "fill carries the second variable, never two quantities in one ramp" sentence. |
| **89–93** | `atlas.json` record: add `domain_group` to the field list, with an inline note that it is derived at build time from `taxonomy/domain_groups.yaml`, is display-only, and is forbidden in `facets.json`, `corpus.json` and every `derived/*.json`. |
| **166** | Packed layout keying "domain -> subdomain -> capability" → "group -> family -> subdomain". Capability is a facet and does not belong in a containment chain. |
| **171–177** | Recommendation paragraph: add one sentence that the banding scheme (D4) strengthens the packed-first recommendation, because banding needs deterministic containment that an embedding cannot guarantee, and that if the embedded layout later passes the gate the banding degrades to per-family and per-group convex hulls with the same labels and the same emphasis behaviour. |
| **186–189** | Filter dimming: name the tokens — matching nodes keep `--c-ink`/`--c-emphasis`, non-matching drop to `--c-ink-faint`. |
| **207–211** | No-JS grouped list: state that this one artefact is simultaneously the no-JS fallback, the screen-reader linearisation, the roving-tabindex target **and the Atlas legend** — a 19-row family index with group headings, counts and per-row highlight toggles. There is no colour legend. |
| **221–222** | V2 Form: "Rows are domain terms" → "Rows are the 19 domain families, in the declared presentation-group order, banded by group with a `<th scope=\"rowgroup\">` per band; row order is build-stable and never sorted by entry count by default". |
| **233–234** | "eighteen domain families containing roughly 174 subdomains, and about forty capability terms" → nineteen / 204 / 44. *(G1/G2/G3 — owned by the number-correction agents; flagged here because the sentence is in this decision's blast radius.)* |
| **235** | "around **6,960 cells**" → 8,976. *(G4 — owned elsewhere.)* |
| **241–242** | "**18 domain families x ~8 capability groups (144 cells)**" → 19 rows is authoritative from this decision; the column count and the existence of a capability-group vocabulary are **not** and must be resolved by the capability-group decision (G5). Edit to assert 19 rows and leave the column count as an explicit forward reference rather than asserting ~8. |
| **253–256** | Three-cell-states table: unchanged, but add a sentence above it that the density ramp is now the only colour in the plot area, because family is carried by position and text. |
| **271–274** | **Resolve the hatch collision.** Curation confidence loses its per-cell diagonal-hatch overlay (which collides with 09 §4.4's hatch-means-zero) and keeps the row-gutter bar and the tooltip sentence; where a per-cell mark is needed, use a 4px `--c-ink-faint` corner tick. State the reason: the absence pattern vocabulary must stay unambiguous, and two hatches are not distinguishable at cell size. |
| **282–288** | Interactions: add row and column emphasis — a 2px `--c-emphasis` rule plus semibold header on hover/focus, and the hard rule that emphasis never alters a cell fill. Add the family-expands-to-subdomains behaviour with the group band retained. |
| **304–306** | No-JS table: specify `<tbody>` per presentation group with `<th scope="rowgroup">` carrying the group label, and `<th scope="row">` carrying the family label, so the banding has an accessible expression. |
| **315** | V3 "grouped by domain" → "grouped by family, with families ordered and banded by presentation group, each block titled". |
| **388–390** | V4: **replace the stacked-stream/ThemeRiver domain underlay** with a small-multiples strip set — one filled area strip per family (19), shared x axis, single neutral fill, direct-labelled, ordered and banded by group. State the reason: a 19-band theme river is a 19-category colour encoding and is unreadable at that cardinality regardless of palette. |
| **414–417** | V4 Implementation: drop `ThemeRiverChart`. Replace the "colour capped at the top twelve organisations plus other" rule — twelve categorical hues contradicts 09 L768's six-series cap — with neutral marks plus direct labels on the top six by release count, the rest grey and labelled on hover and in the table. *(Adjacent to D4's remit; listed because it is a live contradiction between 09 and 10 arising from the same perceptual limit.)* |
| **707** | V9 E4: **replace the ChordChart** with an organisation × family heatmap on the coverage-density ramp, sharing V2's banded 19-row structure, with the year slider stepping the heatmap. State the loss explicitly: bilateral flow is not shown; magnitude is, and magnitude is what "where is measurement effort going" asks for. |
| **739–741** | V9 Implementation: `ChordChart` → `HeatmapChart` for E4. |
| **765, 787–790** | V10: the mini-matrix is a V2 miniature with the same 19 banded rows and the same ramp; target cells outlined in `--c-emphasis`; families with zero basket entries render as empty rows rather than being omitted; where space forbids 19 rows, collapse visually to groups and label collapsed rows "N families, 0 entries" — never print a group-level coverage number. |
| **963–976** | URL grammar: add an explicit line under `Rules:` — "there is no key for the presentation group; it is a display-only vocabulary and is not filterable (see D4)". |
| **1030, 1035** | Performance budget: the V4 and V9 ECharts import sets shrink by `ThemeRiverChart` and `ChordChart` respectively. Do not invent new numbers; note that the budgets are unchanged or lower and remeasure in Phase 1. |
| **1108–1116 (open questions)** | Item 3 ("Coverage-map default resolution — 18 families x 8 capability groups") → the row axis is settled at 19 families by D4; only the column axis remains open, pending the capability-group decision. |

### Cross-file, flagged for other owners

- **`05-repository-and-workflow.md`** — add `scripts/check_display_only_vocab.py` to the CI list:
  asserts `taxonomy/domain_groups.yaml` is a total partition over `taxonomy/domain.yaml`'s families,
  and greps `facets.json`, `corpus.json`, `derived/coverage.json`, `derived/gaps.json`,
  `derived/ecosystem.json` and the Croissant JSON-LD for group ids, failing on any hit. Note for the
  owner of check 9c (G8): the group ids are a **third** vocabulary namespace and must be disjoint from
  both capability ids and subdomain slugs; the six ids proposed here (`symbolic-formal`,
  `reasoning-general-ability`, `perception-generation`, `physical-engineered`, `life-health`,
  `society-safety`) were chosen to collide with neither, but the disjointness assertion should cover
  all three sets, not two.
- **`15-open-questions.md`** — remove the "should the six-group domain colouring be exposed as a
  user-selectable grouping" question (answered); rescope the ΔE-threshold question to cross-meaning
  pairs; add "does emphasis need a group-level mode".
- **`02-taxonomy.md`** — no edit required. This decision deliberately does not touch the taxonomy; the
  presentation groups are a new sibling file, not a new level of the spine.
