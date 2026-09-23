# 09 -- Design System

This document specifies the **visual language**: type, colour, space, components, chart conventions,
accessibility, theming, voice. [10-visualization.md](10-visualization.md) specifies the **views** —
the Atlas, the Coverage Map, the Saturation Wall, the Workbench — and assumes everything defined
here. The split is deliberate and should be kept clean: if a decision is about what a surface
*shows*, it belongs in 10; if it is about how any surface *looks and behaves*, it belongs here. When
the two documents disagree, this one wins on rendering and 10 wins on content.

Vocabularies referenced throughout (domain families, lifecycle, verification ladder, condition
fields) are defined in [02-taxonomy.md](02-taxonomy.md) and [04-data-model.md](04-data-model.md).
Build and hosting constraints come from [08-infrastructure-and-build.md](08-infrastructure-and-build.md).

**As-of, stated once.** The version-dependent behaviour and third-party licence terms cited in this
document — IBM Plex's SIL OFL 1.1, Astro 7's `compressHTML` default, ECharts 6.1.0's SSR/ARIA
behaviour, and Artificial Analysis's redistribution terms — were verified on **2026-09-17** and
re-verify with the rest of the pins at Phase 0
([14-roadmap.md](14-roadmap.md) §"Version pins and third-party facts: as-of date" owns the as-of rule
for the whole plan). Licence terms and their evidence grades are owned by
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8; this document cites them and never
becomes a second record of them.

---

## 1. The design stance

This is a **reference instrument**, not a marketing site. The nearest reference points are a
well-made scientific atlas, a field guide, and a good API documentation site: dense where density
serves the reader, calm everywhere else, and completely uninterested in impressing anyone. A visitor
arrives with a question — *what measures long-horizon autonomy in robotics?*, *is this number
comparable to that one?*, *what is nobody measuring?* — and the design's only job is to get out of
the way of the answer while making its provenance impossible to miss. The site should feel like
something a working researcher would keep a tab open on for a year, and like something a regulator
could cite without embarrassment.

Every later decision in this document follows from that stance, and most of them are subtractive.
There is no hero illustration, no stock photography, no gradient banner, no product screenshot, no
animated counter, no testimonial, no logo wall, no dark-glassmorphic anything. The hero of the
landing page is data. The brand mark is the project wordmark set in the mono face; the favicon is a
single monochrome glyph. Skipping brand design work is a positive decision, not a deferral: for a
catalogue whose entire value proposition is "you can audit this", a startup logotype makes it read
*less* credible, not more. The visual budget goes into typography, contrast, and the honesty of the
data marks.

The failure mode to avoid is **the dashboard aesthetic** — rounded cards with drop shadows, six
accent colours, a big number in a coloured tile, sparklines used as decoration. It is the default
output of every UI library and it is exactly wrong here, because it optimises for the impression of
insight rather than the transmission of evidence. The second failure mode is its opposite: an
undesigned wall of default-serif tables that nobody can read for more than ninety seconds. Density
without craft is not rigour.

---

## 2. The three rules that govern every surface

These come from the project's premises, not from taste. Each is restated below as a **component
requirement** — something a contributor cannot accidentally violate, because the component system
does not offer the violating path.

### Rule 1 — Provenance travels with every number

Verification level and condition completeness are never separated from the value they describe. Not
in a tooltip only, not in a footnote, not on a detail page you can navigate to.

**Component requirement.** *There is no primitive that renders a bare metric value.* The only
renderer for a number-with-meaning is `<ValueCell>`, whose required props are
`{ value, metric_id, verification, condition_completeness, claim_id }`. It throws at build time if
any is missing. A contributor who wants to put a number on a page must therefore also decide what
its provenance is, which is precisely the discipline the project is selling. Raw numbers that are
*not* claims — counts of benchmarks, file sizes, dates — use `<Stat>`, which is visually distinct
(no badge slot, different weight) so the two can never be confused.

### Rule 2 — The UI refuses to rank what is not comparable

When assembled values span more than one `comparability_key`, the interface shows the difference
instead of an ordering. It does not quietly sort anyway with a caveat underneath.

**Component requirement.** `<ComparisonGrid>` requires a `comparability_key` on every cell. When the
set of keys in a column has cardinality > 1, the column's sort control is rendered **disabled with
an explanatory label** ("Sorting disabled — 3 condition sets in this column"), never hidden. Hiding
it teaches the user nothing; disabling it with a reason teaches them the whole thesis in one glance.
The adjacent affordance is `<ComparabilityBanner>`, which renders the field-level diff. This is the
one place in the system where a control is deliberately less capable than the user expects, and the
copy must carry the reason.

### Rule 3 — Absence renders as strongly as presence

Empty coverage cells, missing human baselines, unreported uncertainty and unknown condition fields
are drawn, not omitted. The empty cells of the coverage matrix are the most valuable output of this
project; they cannot be whitespace.

**Component requirement.** Every cell renderer has a mandatory `renderAbsent` branch, and a CI lint
(`scripts/lint_absence.mjs`) fails the build on `{value || ''}`, `?? ''`, `?? '—'` and
`{value && <…>}` patterns anywhere under `site/src/components/`. Absence has a dedicated visual
token (§7.4) and a typed vocabulary of four distinct states (§11.2). A blank cell in this site means
a bug, not a gap.

---

## 3. Typography

### 3.1 The type stack

**Recommendation: the IBM Plex superfamily** — IBM Plex Sans, IBM Plex Mono, and IBM Plex Sans
Condensed. All are SIL Open Font License 1.1, which permits web embedding, subsetting and
redistribution without a licence fee or a tracking pixel.

The reason for a superfamily rather than a best-of-breed pairing is that this site mixes running
prose, dense tables, identifiers, YAML fragments and chart axis labels *within a single viewport*
constantly. A matched family gives one set of vertical metrics, one italic design, one numeral
design and one licensing decision. Plex in particular reads as an engineering instrument rather than
a consumer product, has genuinely good tabular figures, and its Condensed cut solves a real problem
we will otherwise hack around: axis labels on a 19 × 44 matrix, and on the 204-subdomain expanded
view ([02-taxonomy.md](02-taxonomy.md) owns both counts). The Condensed cut is load-bearing rather
than convenient, and more so since D4: because domain family is never colour-encoded (§4.2), the
family label *is* the encoding, so a 21-character slug like `robotics-embodiment` has to fit a matrix
row gutter at `--fs-xs` without truncation and without dropping below the 11px floor (§3.2).
(IBM Plex ships variable builds —
`IBMPlexSansVar-Roman` and friends — from the v6.x releases; *unverified — confirm the exact
variable file names and axes before wiring the build*. Static WOFF2 weights are the fallback and are
entirely adequate.)

**No serif in v1.** A serif body face is tempting for the long-form methodology and entry prose, and
IBM Plex Serif is sitting right there. Reject it anyway: entry pages interleave prose with chips,
badges, tables and inline code, and switching family mid-page produces visual noise that reads as
inconsistency rather than hierarchy. Hold Plex Serif in reserve for standalone essay pages (the
methodology, the taxonomy rationale) if those grow long enough to justify a third font download.

**Reject Google Fonts as a delivery mechanism** (self-host instead) — see §12.1 for why.

```css
--font-sans: "IBM Plex Sans", "Plex Fallback", system-ui, -apple-system,
             "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--font-mono: "IBM Plex Mono", "Plex Mono Fallback", ui-monospace, SFMono-Regular,
             "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
--font-cond: "IBM Plex Sans Condensed", "IBM Plex Sans", system-ui, sans-serif;
```

`"Plex Fallback"` is not a downloaded font — it is a metric-adjusted `@font-face` alias over the
local system face, used to kill layout shift. See §12.2.

**Where each face is used.**

| Face | Used for | Never used for |
| --- | --- | --- |
| Plex Sans | All prose, headings, UI labels, chip text, table body | Identifiers, hashes, YAML |
| Plex Mono | Entity IDs (`bench-swe-bench`, `cond-00042`), commit SHAs, metric keys, YAML/code blocks, the `comparability_key` prefix, the wordmark | Running prose, table body text |
| Plex Sans Condensed | Matrix and heatmap axis labels, dense chart tick labels only | Anything a user reads as a sentence |

The mono/sans split is load-bearing rather than decorative: it is how a reader tells a *thing you can
look up* from a *thing someone wrote*. Every value that appears verbatim in the YAML renders in mono.

### 3.2 Scale

A modular scale at roughly a minor third in the middle, compressed at the small end where legibility
governs and stretched at the top where hierarchy governs. All values in `rem` so that browser text
sizing and 200% zoom work (WCAG 2.2 SC 1.4.4). **No `px` font sizes anywhere in the stylesheet** —
lint enforced.

```css
--fs-2xs:  0.6875rem;  /* 11px  chart tick labels, badge glyph labels — the hard floor */
--fs-xs:   0.75rem;    /* 12px  chip text, table meta, footnotes, provenance line */
--fs-sm:   0.875rem;   /* 14px  dense table body, facet lists, form controls */
--fs-base: 1rem;       /* 16px  entry prose, default */
--fs-md:   1.125rem;   /* 18px  lead paragraph, benchmark tagline */
--fs-lg:   1.375rem;   /* 22px  h3 */
--fs-xl:   1.75rem;    /* 28px  h2 */
--fs-2xl:  2.25rem;    /* 36px  h1 / page title */
--fs-3xl:  3rem;       /* 48px  reserved: one figure per landing page, used sparingly */
```

**11px is an absolute floor**, including inside SVG charts, and a lint check walks the built SVG to
enforce it. The temptation to go to 9px on a matrix axis is constant and must be refused; if labels
do not fit at 11px the matrix is too dense for that viewport and should change representation (§10).

### 3.3 Line length, line height, rhythm

```css
--lh-tight:  1.2;   /* headings, --fs-lg and above */
--lh-dense:  1.35;  /* table rows, chip rows, list items */
--lh-ui:     1.45;  /* labels, captions, form text */
--lh-prose:  1.65;  /* running prose at --fs-base */
--measure-prose: 68ch;  /* target */
--measure-max:   74ch;  /* hard cap */
```

Long-form prose is capped at 68ch and never exceeds 74ch, including inside the entry page's main
column. Dense views (tables, matrices, the workbench) are explicitly exempt — a table constrained to
68ch is a worse table. Headings above `--fs-lg` get `text-wrap: balance`; prose paragraphs get
`text-wrap: pretty` where supported (progressive enhancement, no fallback needed).

WCAG 2.2 SC 1.4.12 (Text Spacing) requires the layout to survive line-height 1.5, paragraph spacing
2×, letter-spacing 0.12em and word-spacing 0.16em applied by the user. The practical consequence:
**no fixed-height containers around text**, ever — chips, badges and table cells size from content
with `min-block-size`, not `block-size`.

### 3.4 Numerals — the detail that matters most

This is a site made of numbers arranged in columns, and proportional figures in a column of results
are a genuine readability defect, not a nicety.

```css
/* Global default: proportional, in prose. */
body { font-variant-numeric: proportional-nums; }

/* Everywhere a number can be compared vertically or is an identifier. */
.tabular, td, th, .value-cell, .meter, .stat, code, kbd, samp, .mono {
  font-variant-numeric: tabular-nums slashed-zero;
  font-feature-settings: "tnum" 1, "zero" 1;
}
```

Rules:

- **Tabular figures in every table cell, every chart axis label, every meter readout, every ID.**
  Proportional figures only in running sentences.
- **Slashed zero wherever a string might be transcribed** — IDs, hashes, commit SHAs, metric keys.
  A reader copying `cond-00042` out of a screenshot should not have to guess.
- Numbers never change width when they change value. This is also a performance requirement: with
  tabular figures, a value update cannot reflow a column, which removes a whole class of CLS
  (§12.3).
- Minus signs use U+2212 (`−`), not a hyphen, in all rendered numeric output. The build's formatter
  handles this; contributors never type it.

---

## 4. Colour

### 4.1 Principles before palette

Tokens are defined **semantically** (`--c-ink-muted`, `--c-verif-3`, `--c-absent-hatch`) and never by
hue (`--blue-500`). A stylesheet full of hue names is a stylesheet where nobody can change the dark
theme without breaking meaning, and where the same blue ends up carrying four unrelated ideas.

Three hard rules:

1. **Colour is never the sole carrier of meaning** (WCAG 2.2 SC 1.4.1). Every encoded state also has
   a text label, a glyph, a position, or a fill pattern. Verification level gets a segment-count
   glyph. Absence gets a hatch. Lifecycle gets a word.
2. **Raw colour literals are forbidden in component CSS.** A lint check fails the build on any
   `#rrggbb`, `rgb(`, `hsl(` or bare `oklch(` outside `tokens.css`. A new colour requires a new
   token, which requires a reason in the commit message.
3. **Tokens are generated data, not hand-written CSS.** `design/tokens.yaml` → `tokens.css` +
   `tokens.json` (for the chart code) via the same Python build that produces everything else. The
   design system is therefore diffable, reviewable and forkable on exactly the same terms as the
   catalogue (see [05-repository-and-workflow.md](05-repository-and-workflow.md)).

Colours are authored in **OKLCH**. The reason is practical, not fashionable: the seven-step
verification ladder (§4.3) and the two sequential ramps (§4.4) depend on lightness steps being
perceptually even, which is exactly what OKLCH gives and HSL does not. (The earlier version of this
paragraph justified OKLCH by the grouped-lightness trick used for domain families; that trick no
longer exists — see §4.2 — and the ramps carry the argument on their own.) A second reason now
matters as much: the CI check in §4.2 asserts monotonicity, adjacent-step size and end-to-end range
directly in OKLCH L, so the authoring space and the checking space are the same space, and a token
nobody can measure is a token nobody can review. OKLCH has been baseline-available in browsers since
2023; no fallback layer is warranted in 2026.

### 4.2 Domain family — why it is not colour-encoded

There are **19 domain families** ([02-taxonomy.md](02-taxonomy.md) §3 owns the list). **Domain family
is never encoded by hue. Anywhere.** There is no domain-family palette, no super-group palette, and no
`--c-dom-*` token namespace (decision
[D4](_workflow/decisions/D4-nineteen-family-cascade.md)).

The perceptual argument for that is real but it is the weaker of the two. No 19-category qualitative
palette is safely distinguishable: the practical ceiling for reliable categorical identification by
hue is around 8 colours for normal colour vision and materially fewer under the common colour-vision
deficiencies — deuteranomaly alone affects roughly 6% of men. An earlier version of this section
conceded exactly that and then specified an 18-swatch palette anyway, which is the tell that the
premise was never followed to its conclusion.

The decisive argument is **allocation**. The hue channel in this product is already fully committed to
*ordered and semantic* meanings, and every one of them carries provenance:

| Encoding | Channel already spent | Section |
| --- | --- | --- |
| Verification ladder | 6-step blue lightness ramp + segment-count glyph | §4.3 |
| Headroom consumed | 7-stop warm ramp | §4.4 |
| Coverage density | 7-stop cool ramp | §4.4 |
| Contaminated / retracted | `--c-alert` (red ~25) | §4.3 |
| Comparability warning, staleness | `--c-caution` (amber ~75) | §4.5 |
| Verified / passing | `--c-affirm` (green ~150) | §4.5 |
| Link, visited, focus, selection | blue ~250, violet ~300, blue ~255 | §4.5 |

The retired six-hue family palette collided with four of those on hue alone: amber "physical world"
against the warm headroom ramp on the same Saturation Wall page; green "life sciences" against
`--c-affirm`; rose "sociotechnical" against `--c-alert`; blue "symbolic" against the entire
verification ladder, `--c-link` and the coverage ramp. A reader on the coverage matrix would have been
holding "amber means physical-world" and "amber means high headroom / caution" in the same eye at the
same time. So the trade is not "19 distinguishable hues versus 6" — it is **family identity versus
provenance identity**, and provenance wins, because provenance is the product. Colour spent making
`chemistry-materials` distinguishable from `biology-genetics` is colour taken from making
`self-reported` distinguishable from `third-party-audited`. Family, unlike verification level, has a
perfectly good non-colour encoding available: its name, which is short, memorable, speakable,
printable, and already required to be on screen by channel (b) below.

**The failure mode of this choice, named.** The views go monochrome and read as unfinished, and the
Atlas specifically loses the three-second "what is this site" answer that
[10-visualization.md](10-visualization.md) assigns it. A grey treemap with labels is a diagram, not a
picture, and a reviewer will say so within five minutes of first render. The mitigation is *not* to
smuggle colour back in: the Atlas's visual interest must come from the two encodings that are
genuinely quantitative — node size (adoption, log-scaled) and fill level (headroom consumed) — plus
the small number of alert-coloured contaminated/retracted nodes, which will look like exactly what
they are, scattered red flags across an otherwise calm field. If on real records in Phase 1 the Atlas
still reads flat, the honest response is to demote it and let the coverage matrix be the hero, not to
reopen the palette question.

**Four channels carry family, none of them hue.**

**(a) Position, the primary channel.** Family is a *place*: a contiguous region in the Atlas, a row at
a fixed index in the coverage matrix, a titled block in the Saturation Wall. Position is the strongest
categorical channel available at 19 levels, it is CVD-invariant, it survives greyscale and print, and
it is the only channel that scales to the 204 subdomains of the expanded view without redesign. It
works only if it is **stable across builds**: row order and containment order come from the declared
order in `taxonomy/domain_groups.yaml`, never from entry count and never alphabetically. Sorting by
entry count is a user-invoked, URL-encoded option, never the default — a default that reorders
whenever curation adds a benchmark is the Atlas layout-drift failure reproduced in a table, and it
destroys the spatial memory that makes a 19-row matrix learnable.

The 19 families roll up into **six presentation groups**, and the roll-up's job is **ordering and
banding, not colour**. It fixes the row order of the coverage matrix, the containment structure of the
packed Atlas and the page order of the Saturation Wall, and nothing else.

| # | Group id | Label | Families, in declared order |
| --- | --- | --- | --- |
| 1 | `symbolic-formal` | Symbolic and formal | `language` · `mathematics` · `code` |
| 2 | `reasoning-general-ability` | Reasoning and general ability | `reasoning-general` · `general-intelligence` · `games-planning` |
| 3 | `perception-generation` | Perception and generation | `vision` · `audio-speech` · `multimodal` |
| 4 | `physical-engineered` | Physical and engineered systems | `robotics-embodiment` · `physics` · `engineering-design` · `earth-climate` |
| 5 | `life-health` | Life and health sciences | `chemistry-materials` · `biology-genetics` · `medicine-health` |
| 6 | `society-safety` | Society and safety | `agents-tooluse` · `safety-alignment` · `society-econ-law` |

Group order top-to-bottom (and outside-in in the Atlas) is the numbered order above: formal → general
reasoning → perception → physical → life → society. It runs roughly from the most abstract substrate
to the most embedded-in-the-world, which is a defensible reading order and, more importantly, a
*fixed* one. Group 4 has four members and the rest have three; `engineering-design` is the family the
old table silently omitted, which is how an 18-row table outlived a 19-family taxonomy. Under a colour
scheme its addition would have meant a fourth lightness step at a ~0.09 L interval, below the reliable
discrimination floor at mark size. Under an ordering scheme it means nothing at all — which is itself
an argument for the ordering scheme.

**Membership disputes are now cheap**, and that is the main non-obvious benefit. Whether
`games-planning` belongs with reasoning or with agents is arguable; under the old scheme that argument
determined a benchmark's colour and therefore its apparent kinship in the hero view. Under this scheme
it determines which of two adjacent rows it sits between. Demoting the roll-up from colour key to
ordering key converts a class of unresolvable design arguments into a class of trivial ones.

> **Guard rail, reversed from the previous draft.** The grouping is **a real vocabulary**, at
> `taxonomy/domain_groups.yaml`, under the same ADR governance as every other vocabulary, flagged
> `display_only: true`. The previous instruction — record it in `design/tokens.yaml` with a warning in
> a comment — was the worst available option and is withdrawn. A grouping that determines the row
> order and band structure of the two highest-value views is load-bearing, and putting it in a design
> file with no ADR, no changelog and no CI relationship to the family list is exactly the arrangement
> that produced the 18/19 discrepancy: the palette table had no mechanical link to the domain
> vocabulary, so when `engineering-design` was added, nothing failed. Four properties are enforced:
> **(1) total partition** — every family in `taxonomy/domains.yaml` in exactly one group, no group
> member that is not a family, so adding a 20th family without assigning it a group fails CI in the
> same commit; **(2) no filter key** — the URL grammar has no key for it and adding one requires an
> ADR superseding D4; **(3) not in analytics** — permitted in `atlas.json` as a derived display field
> and in rendered HTML, forbidden in `facets.json`, `corpus.json`, `derived/coverage.json`,
> `derived/gaps.json`, `derived/ecosystem.json`, the exported `suite.yaml` and the Croissant JSON-LD,
> because every coverage percentage, density figure, gap score and curation-confidence value is
> computed over families and subdomains, never over groups; **(4) never in a claim sentence** — no
> rendered sentence of the form "N benchmarks measure X in *Life and health sciences*". Properties 1
> and 3 are mechanically checked by `scripts/check_display_only_vocab.py`
> ([05-repository-and-workflow.md](05-repository-and-workflow.md) owns the CI list); property 4 is a
> review rule, restated in §11. The reason for the harder governance path: a display-only grouping
> that leaks into a published gap claim is a data-integrity failure invisible in the diff, and a
> specialist who disputes the grouping has then invalidated the finding without touching the data.
> Governance is cheaper than that retraction.

**(b) The label, always present.** The family label spelled in full, in Plex Sans Condensed at
`--fs-xs` or above, `--c-ink` for row headers and `--c-ink-muted` for card metadata. Never
abbreviated, never truncated with an ellipsis, never replaced by a code. *Two-letter family codes
(`RB`, `CM`, `BG`) were considered and rejected:* a 19-code cipher is the same memorisation burden as
19 hues with none of the pre-attentive benefit, and in a reference work a reader must not have to
decode a label.

**(c) The band, for grouping.** A hairline `--c-border` rule between presentation groups with the
group name in the left gutter at `--fs-sm` `--c-ink-muted`. This replaces the "the amber region is
physical-world stuff" first-order read, and replaces it with something better: a label you can read
aloud, in greyscale, at 11px, under every CVD, on paper.

**(d) Emphasis — focus-plus-context, one family at a time, never nineteen-at-once.** The default state
of the Atlas and the Coverage Map is **a single neutral ink**, with structure carried by position and
density. Selecting or hovering a family raises exactly that family to full ink and drops everything
else to `--c-ink-faint`, marked with a single new token, `--c-emphasis`, used as a 2px rule or outline
and never as a fill on a cell whose fill already carries density. sigma.js's `nodeReducer` (see
[08-infrastructure-and-build.md](08-infrastructure-and-build.md)) is exactly this mechanism in the
Atlas and costs nothing; everywhere else it is a class toggle with no JS recomputation (§12.3). **One
emphasis token, not 19** — the answer to "where is `chemistry-materials`" is a highlight, not a
memorised colour, and a highlight answers it faster and more certainly than a hue ever did. The
failure mode this avoids is the confetti map, where nineteen hues at 40% opacity produce a decorative
blur that answers no question; it is the single most common way a project like this ends up with a
beautiful screenshot and an unusable view.

**Hue is never applied.** Every domain mark carries its label, inline, on hover/focus, or through the
family index placed adjacent in reading order. Under `forced-colors: active`, in greyscale and in
print, **nothing about family is lost, because nothing about family was in colour** — a claim the old
palette could not make, and the clearest single piece of evidence that this scheme is better than a
palette.

**Second failure mode: label collision.** Replacing hue with text raises the label budget sharply — 19
family labels, six group labels, plus Atlas node labels, all above the hard 11px floor (§3.2) inside a
120rem cap (§5.2). If they do not fit, §3.2 forbids shrinking them, so the scheme degrades by
*density*, not size: group labels always visible; family labels always visible in the matrix, where
they are row headers with a gutter; family labels in the Atlas visible at default zoom only where the
cluster is wide enough, otherwise on hover and always in the adjacent family index. This is a real
implementation risk and belongs in Phase 1 prototyping. The binding constraint on the default
coverage view is now the *column* axis rather than the row axis — 19 rows is a comfortable table
height — and whether 13 horizontal tick labels (all under 22 characters; the vocabulary is owned by
[02-taxonomy.md](02-taxonomy.md) §4.3) render without rotation at laptop width in ECharts
`MatrixComponent` is *(unverified — confirm against the render before freezing the default view)*.

**Third failure mode: local reinvention.** With no family colour in the token set, the first
contributor who needs to tell two families apart in a one-off chart will invent a hue inline. That is
why the prohibition is machine-checked rather than merely written down (§13, `lint_tokens.mjs`).

**CI check.** `scripts/check_palette.py` is rewritten — **and deliberately not renamed**; it is
referenced here, in §13 and in the CI config, and renaming it buys nothing and creates three more
edits. Its old job was to render 18 swatches and check pairwise ΔE, which is a check of a thing that
no longer exists. It now reads `design/tokens.yaml`, resolves both themes, and runs six assertion
groups against four CVD simulations (deuteranopia, deuteranomaly at severity 50 — the common case,
not the textbook one — protanopia, tritanopia; `colorspacious` for CVD and CAM02-UCS ΔE, `coloraide`
for OKLCH → sRGB). Severity 50 is included deliberately, because a palette tuned only for full
dichromacy can still fail the far more common anomalous trichromacy; whether `colorspacious`'s
Machado-style model is well calibrated at intermediate severities is *(unverified — confirm before
relying on this)*. Six assertion groups:

| # | Asserts | Why it exists |
| --- | --- | --- |
| **A** | No token id matches `^c-(dom\|domain\|family\|group)-` | The assertion that makes D4 durable. Without it, the first contributor who needs two families told apart reinvents a hue inline |
| **B** | `categorical_sets:` capped at **6 members**, each declaring a non-empty `redundant_channel` (`glyph`, `pattern`, `label`, `position`, `count`), pairwise ΔE ≥ 15 within a set | Enforces §4.1 rule 1 rather than merely stating it |
| **C** | Ordered ramps strictly monotonic in perceived lightness, adjacent step ≥ 0.055 L, end-to-end range ≥ 0.45 L | The verification ramp is exempt from the range assertion and marked `primary_channel: count`, because its range is 0.32 L — which is exactly why §4.3 gives it a segment glyph as its primary channel. The exemption carries its reason so nobody "fixes" it by stretching a ramp whose colour job is secondary |
| **D** | Cross-meaning separation: a `co_occurrence:` block declares which meaning-groups share a viewport, and every cross-group pair is ≥ ΔE 15 **or** ≥ 0.10 apart in OKLCH L **or** pattern-distinguished | This is the check that replaces the retired pairwise-family check, and the three-way alternation is why it can express what a single ΔE could not |
| **E** | Non-text contrast at §4.6's values, including `--c-emphasis` against both `--c-bg` and `--c-ink-faint` | The emphasis token is the one that collides with `--c-link-visited` |
| **F** | Greyscale and `forced-colors` survivability: every cross-meaning pair ≥ 1.4:1 in CIE Y or pattern-distinguished; every categorical member and absence state declares a pattern or glyph | Print and high-contrast mode are reading modes, not edge cases |

Thresholds live in `tokens.yaml` under a `thresholds:` key rather than as constants in the script —
a number in a script is a number nobody can find — and every computed value is written to
`build/reports/palette.json`, so the thresholds are auditable rather than folkloric. **The ΔE floor
of 15 is empirical and uncalibrated:** start there, calibrate against real renders in Phase 2, and
record the result in `tokens.yaml` rather than guessing it twice. One trap worth naming, because it
is the obvious wrong test: ΔE between *adjacent* stops of a sequential ramp must never be asserted —
adjacent stops are supposed to be similar, and monotonicity plus step size plus range is the correct
family of tests.

### 4.3 Verification, lifecycle and ingestion provenance

**Verification** is `ResultClaim.verification`, an ordered ladder of **seven** levels plus one
off-ladder state. [04-data-model.md](04-data-model.md) §7 owns the enum and its rank numbers, which
are stored in `taxonomy/verification.yaml`; the order below is read from there and is reproduced
here only because the encoding depends on the rank:

`self-reported` (1) → `maintainer-verified` (2) → `independent-reproduction` (3) →
`held-out-server` (4) → `prospective-experiment` (5) → `third-party-audited` (6) →
`sandboxed-rerun` (7), with `disputed` orthogonal to all of them.

Encoding: a **seven-segment glyph** (filled bars, like a signal meter) reading 1–7, plus a single
neutral-to-confident lightness ramp, plus the level name as accessible text. Three redundant channels
— count, shape, colour — and the count survives greyscale printing, 11px rendering and every form of
CVD. `disputed` is **not** an eighth bar; it is a distinct outlined warning glyph that overlays the
badge, because it is a different axis and rendering it as "level 8" would imply it is better than a
sandboxed rerun.

Two notes on the ladder, because an earlier draft of this document got both wrong and the errors
were only caught by [13-execution-runners.md](13-execution-runners.md) reading it against `04`.
First, **`prospective-experiment` is a rung and needs a token**: it is where CACHE, the Virtual Cell
Challenge and ForecastBench sit — three of the ten stress entries and the heart of the non-LLM half
of the map — and a differentiating family with no badge colour is a differentiator that does not
render. Second, **`sandboxed-rerun` is rank 7, above `third-party-audited` at 6**, per `04`'s stated
argument that a held-out set can in principle leak while a post-hoc rerun under recorded conditions
cannot. The earlier draft transposed them, which rendered a claim this project produced itself as
*less* verified than one it audited. The ordering is not ours to choose here; regenerate the token
block from `taxonomy/verification.yaml` rather than typing it, and the next rung added to the ladder
will not reproduce this defect ([05-repository-and-workflow.md](05-repository-and-workflow.md) §9,
check 9b).

**A separate axis, and the confusion to avoid.** `ResultClaim.verification` (this ladder) and
`curation.verification_status` (the six-value curation ladder owned by
[05-repository-and-workflow.md](05-repository-and-workflow.md) §4) are two different fields with two
different vocabularies and two different marks. Nothing in the product may order them against each
other, and no sentence anywhere should read "`curator-verified` or better" — that value does not
exist on either ladder.

**Curation provenance** is a *separate* axis and needs its own mark. Per the settled Epoch decision
([01-landscape-and-positioning.md](01-landscape-and-positioning.md)), bulk-ingested claims carry
`curation.verification_status: machine-ingested`, and there will be roughly 6,598 of them against
50–80 hand-curated LLM claims. The design consequence is blunt: **a machine-ingested record must
never be stylable into looking equivalent to a human-reviewed one.** It gets a dotted-outline chip
reading `machine-ingested`, `--c-ink-muted` text, and no accent colour. The visual hierarchy has to
match the epistemic hierarchy or the whole bulk-ingest strategy becomes the thing that damages
credibility rather than the thing that provides coverage.

**Lifecycle** has ten terms (`proposed` `active` `mature` `saturated` `under-revision` `contaminated`
`superseded` `deprecated` `retracted` `dormant`; [02-taxonomy.md](02-taxonomy.md) §8 owns the
vocabulary) and the decision here is to **colour only three of them**. If all ten are coloured, none
of them is signal. Specifically:

| Lifecycle | Treatment | Reason |
| --- | --- | --- |
| `active`, `mature` | Neutral chip, `--c-ink` on `--c-surface` | The normal case deserves no attention |
| `proposed`, `dormant` | Muted chip, `--c-ink-muted`, no fill | Low-confidence, not alarming |
| `saturated` | Top stop of the headroom ramp | Consistent with the headroom encoding everywhere else |
| `superseded`, `deprecated` | Muted chip + `→` glyph linking the successor | The useful information is *what replaced it* |
| `under-revision` | Neutral chip + `!` glyph + the revision's date and a link to its errata | An instability flag, not a stop sign: the benchmark is alive and maintained and its current numbers are temporarily untrustworthy. FrontierMath's 2026-06-12 reissue, which corrected errors in 42% of problems, is the case that forced the term |
| `contaminated`, `retracted` | `--c-alert` fill + warning glyph + required evidence link | The only two states that should stop a reader |

Note the `→` treatment on `superseded`/`deprecated`: benchmark lineage and supersession is one of the
genuinely unoccupied differentiators (OSWorld → OSWorld-Verified + OSWorld 2.0; Terminal-Bench 2.0 and
2.1 concurrent; SWE-bench's six forks), so the chip does real work by pointing rather than merely
labelling.

### 4.4 The two sequential scales

Two ramps, deliberately in **different hue families**, because they appear on adjacent views and must
never be misread for one another.

**Headroom consumed** (the only legitimate cross-domain axis) runs 0 → 1 on a **warm ramp**, 7 stops,
monotonic in OKLCH lightness. Design notes:

- Do **not** use a diverging red–green ramp. There is no meaningful midpoint in headroom, and
  red–green is the worst possible CVD case.
- `> 1.0` is a real value — a system exceeding a stated human ceiling — and must **not** be clamped
  silently. It gets a dedicated over-ceiling treatment (the top stop plus a hatched overlay and a `▲`
  marker) and a tooltip explaining what the ceiling was.
- A benchmark with `ceiling_anchor_type: none-known` has **no headroom value at all**. It renders in
  the absent token (§4.5), not at 0 and not at the ramp's lightest stop. Rendering "unknown headroom"
  as "zero headroom consumed" would invert the meaning.

**Coverage density** runs on a **cool neutral ramp**, and carries the most important special case in
the whole colour system:

| Coverage state | Rendering |
| --- | --- |
| Zero benchmarks | **Hatched fill** (45° 2px lines, `--c-absent-hatch`) + `0` label, *not* the lightest ramp stop |
| 1–2 benchmarks ("thin") | Lightest ramp stop + count |
| 3+ | Ramp by density + count |
| Not applicable (cell is meaningless for this pair) | Dotted border, no fill, `n/a` |
| Not yet curated (curation gap, not field gap) | Diagonal slash pattern + `?` |

The distinction between the last three rows is the honesty requirement from the archived plan made
literal: an empty cell may mean nobody measures it, or that the taxonomy does not describe the field
well, or that curation has not reached it yet, and **the reader must be able to tell which without
reading a caption**. The hatch on zero is what makes absence render as strongly as presence rather
than as the pale end of a gradient the eye skips.

**The 45° hatch belongs to zero coverage and to nothing else.** Since §4.2 removed hue from the
family axis, patterns carry more load in this matrix than they used to, and a second hatch would
break the one vocabulary that must stay unambiguous (Rule 3). Two hatches are not distinguishable at
cell size. So the per-cell diagonal-hatch overlay that [10-visualization.md](10-visualization.md)
independently allocated to *low curation confidence* is withdrawn: curation confidence keeps its
row-gutter bar and its tooltip sentence, and where a per-cell mark is genuinely needed it is a 4px
`--c-ink-faint` triangular tick in the cell's top-right corner — a different shape class, with no
possible confusion with the three absence patterns. The density ramp is also now the **only** colour
in the plot area, which is the payoff of not colouring families.

### 4.5 The token set

```css
:root {
  color-scheme: light dark;

  /* ---------- neutrals: surface and ink ---------- */
  --c-bg:             oklch(99.0% 0.003 250);
  --c-surface:        oklch(97.4% 0.005 250);
  --c-surface-sunken: oklch(95.2% 0.006 250);
  --c-border:         oklch(88.0% 0.008 250);   /* 3:1 vs --c-bg: non-text contrast, SC 1.4.11 */
  --c-border-strong:  oklch(74.0% 0.010 250);
  --c-ink:            oklch(22.0% 0.012 250);   /* ≥ 12:1 on --c-bg */
  --c-ink-muted:      oklch(46.0% 0.012 250);   /* ≥ 4.5:1 on --c-bg — smallest body text OK */
  --c-ink-faint:      oklch(62.0% 0.010 250);   /* ≥ 3:1 — NON-TEXT and large text only */

  /* ---------- interaction ---------- */
  --c-link:           oklch(45.0% 0.15  250);
  --c-link-visited:   oklch(42.0% 0.12  300);
  --c-focus:          oklch(55.0% 0.19  255);   /* ≥ 3:1 vs bg AND vs the focused element */
  --c-select-bg:      oklch(93.0% 0.05  250);

  /* ---------- semantic states ---------- */
  --c-alert:          oklch(52.0% 0.17   25);   /* contaminated / retracted / hard error */
  --c-alert-bg:       oklch(96.0% 0.03   25);
  --c-caution:        oklch(58.0% 0.13   75);   /* comparability warning, staleness */
  --c-caution-bg:     oklch(96.5% 0.035  75);
  --c-affirm:         oklch(48.0% 0.11  150);   /* used sparingly: verified, archived, passing */

  /* ---------- verification ladder (7 ordered steps) ----------
     Generated from taxonomy/verification.yaml by lint_tokens.mjs; do not hand-edit
     the order. Rank and name are 04 §7's; only the lightness ramp is ours. */
  --c-verif-1: oklch(70% 0.020 250);  /* self-reported           */
  --c-verif-2: oklch(65% 0.035 250);  /* maintainer-verified     */
  --c-verif-3: oklch(60% 0.050 250);  /* independent-reproduction*/
  --c-verif-4: oklch(55% 0.070 250);  /* held-out-server         */
  --c-verif-5: oklch(49% 0.090 250);  /* prospective-experiment  */
  --c-verif-6: oklch(43% 0.105 250);  /* third-party-audited     */
  --c-verif-7: oklch(37% 0.120 250);  /* sandboxed-rerun         */
  --c-verif-disputed: var(--c-alert);

  /* ---------- sequential: headroom consumed (warm) ---------- */
  --seq-head-0: oklch(96% 0.030 85);
  --seq-head-1: oklch(90% 0.060 80);
  --seq-head-2: oklch(83% 0.095 74);
  --seq-head-3: oklch(75% 0.125 66);
  --seq-head-4: oklch(66% 0.145 55);
  --seq-head-5: oklch(55% 0.150 42);
  --seq-head-6: oklch(43% 0.140 32);

  /* ---------- sequential: coverage density (cool) ---------- */
  --seq-cov-0: oklch(96% 0.012 235);
  --seq-cov-1: oklch(90% 0.030 235);
  --seq-cov-2: oklch(82% 0.050 235);
  --seq-cov-3: oklch(72% 0.070 238);
  --seq-cov-4: oklch(61% 0.085 242);
  --seq-cov-5: oklch(49% 0.095 246);
  --seq-cov-6: oklch(37% 0.090 250);

  /* ---------- absence ---------- */
  --c-absent-ink:   var(--c-ink-faint);
  --c-absent-hatch: oklch(80% 0.008 250);
  --c-absent-rule:  oklch(70% 0.010 250);

  /* ---------- emphasis: one selected family/row/cluster at a time ---------- */
  --c-emphasis:    oklch(48.0% 0.16 300);   /* ≥ 3:1 vs --c-bg AND vs --c-ink-faint (SC 1.4.11) */
  --c-emphasis-bg: oklch(95.0% 0.035 300);  /* row-tint only where no density fill is present */

  /* ---------- PROHIBITED NAMESPACE ----------------------------------------
     There is no --c-dom-* / --c-family-* / --c-group-* token and there must
     not be one. Domain family is encoded by position, label and band; see
     §4.2. scripts/check_palette.py fails the build if this namespace returns.
     ------------------------------------------------------------------------ */
}
```

Hue ~300 for emphasis is chosen deliberately: it is the one region of the wheel not already carrying
an ordered meaning (blue ~250 verification/link/coverage, amber ~65–85 headroom/caution, green ~150
affirm, red ~25 alert). It does collide with `--c-link-visited` (violet ~300) at similar lightness, so
that pair is named explicitly in the cross-meaning check (§4.2 group D) — and if it fails calibration,
**move emphasis to ~330 rather than moving any ordered ramp.** Both emphasis tokens are re-authored
for dark, not inverted (§9); `--c-emphasis` lands near `oklch(78% 0.14 300)` there, with the exact
value set by the contrast check rather than by hand.

### 4.6 Contrast requirements

Target: **WCAG 2.2 Level AA**, with AAA taken where it is free (body ink is comfortably above 7:1).

| Requirement | SC | Applies to |
| --- | --- | --- |
| 4.5:1 | 1.4.3 | All body text, chip text, table cells, badge labels, axis tick labels |
| 3:1 | 1.4.3 | Large text only (≥ 24px, or ≥ 18.66px bold) |
| 3:1 | 1.4.11 | Borders, chart marks, meter segments, focus rings, the hatch against its ground |
| 3:1 | 1.4.11 | The emphasis rule or outline, against both `--c-bg` and the dimmed `--c-ink-faint` ground |
| — | 1.4.1 | Every colour-encoded state also carries a glyph, label or pattern |

`--c-ink-faint` is **never** used for body text. It is for rules, disabled-state borders and
dimmed-out-of-filter marks. A lint rule enforces this by selector.

**CI check.** `scripts/check_contrast.py` reads `tokens.yaml`, computes WCAG contrast for every
declared ink-on-surface pair in both themes, and fails the build below threshold. This runs on every
commit, which is the only way a token set stays compliant after six months of small changes.

**The two checks are deliberately split, and stay split:** `check_contrast.py` owns text contrast;
`check_palette.py` (§4.2) owns non-text marks, CVD simulation and cross-meaning separation. Two fast
focused checks report better than one slow one, and the `--c-emphasis` pair is asserted in both
because the emphasis mechanism fails silently if it fails at all.

---

## 5. Layout, spacing and grid

### 5.1 Spacing scale

A 4px base, expressed in rem, deliberately short — a long scale invites inconsistency.

```css
--sp-0:  0;
--sp-05: 0.125rem;  /*  2px  hairline gaps inside badges */
--sp-1:  0.25rem;   /*  4px  */
--sp-2:  0.5rem;    /*  8px  chip padding, cell padding-inline */
--sp-3:  0.75rem;   /* 12px  */
--sp-4:  1rem;      /* 16px  default block rhythm, page gutter (mobile) */
--sp-6:  1.5rem;    /* 24px  grid gutter, section spacing */
--sp-8:  2rem;      /* 32px  */
--sp-12: 3rem;      /* 48px  major section break */
--sp-16: 4rem;      /* 64px  */
--sp-24: 6rem;      /* 96px  page-level top/bottom only */
```

### 5.2 Containers

```css
--w-prose: 68ch;    /* long-form reading column */
--w-entry: 68rem;   /* 1088px — entry page: prose column + metadata rail */
--w-dense: 90rem;   /* 1440px — tables, workbench, list views */
--w-wide:  120rem;  /* 1920px — Atlas / matrix hard ceiling; gutters beyond */
```

Full-bleed is available for the Atlas and the Coverage Map only, capped at `--w-wide` so that the
matrix does not become a 3,000px stretch on an ultrawide monitor where axis labels drift out of reach
of their rows.

### 5.3 Breakpoints and grid

```css
--bp-sm:  35rem;   /*  560px  */
--bp-md:  51rem;   /*  816px  entry page gains its metadata rail */
--bp-lg:  69rem;   /* 1104px  dense tables gain their full column set */
--bp-xl:  87rem;   /* 1392px  workbench shows plot and table side by side */
```

A 12-column grid with `--sp-6` gutters applies at `--bp-lg` and above. Below that, layouts are
single-column with `--sp-4` page gutters.

**Use container queries for components, not media queries.** A benchmark card appears in the entry
page's 20rem rail, in a 3-across grid, and in a full-width list; `@container (inline-size > 24rem)`
is the correct predicate and viewport width is the wrong one. Container queries have been baseline
since 2023 and there is no reason to hand-roll around them. Media queries remain correct for
*page-level* decisions — which representation a dense view uses (§10).

Entry page template at `--bp-md` and above:

```css
.entry {
  display: grid;
  grid-template-columns: [prose] minmax(0, var(--w-prose)) [rail] 20rem;
  gap: var(--sp-8);
}
```

---

## 6. Component inventory

Each component below states what data it needs and what it must never do. The "never" column is the
important one — it is where the three rules become mechanical.

### 6.1 `<BenchmarkCard>`

The unit of every list, grid and search result.

**Needs:** `id`, `name`, `tagline`, `primary_domain`, up to 3 `capabilities`, `lifecycle`,
`year_released`, `headroom_consumed | null`, `claim_count`, `last_verified_at`.

**Layout:** name (Plex Sans, `--fs-md`, semibold) + the family label in Plex Sans Condensed
(`--fs-xs`, `--c-ink-muted`) followed by the subdomain, on one line — there is no domain swatch
(§4.2); tagline
at `--fs-sm` `--c-ink-muted`, clamped to 2 lines with `line-clamp`; a chip row at `--fs-xs`; a
right-aligned headroom bar; a footer line with claim count and staleness.

**Never:** show a headroom bar when `ceiling_anchor_type` is `none-known` (render the absent token
and the reason). Never show a metric value on a card — cards carry *identity and shape*, not results;
a number on a card is a number without room for its provenance, which violates Rule 1.

### 6.2 `<FacetChip>`

**Needs:** `facet`, `term_id`, `label`, `state` (`static | filter-available | filter-active`),
optional `count`.

**Spec:** `min-block-size: 1.5rem` (24px, satisfying SC 2.5.8 Target Size Minimum); 1.75rem at coarse
pointers via `@media (pointer: coarse)`. `--fs-xs`, `--sp-2` inline padding, 3px radius (not a pill —
pills read as tags on a blog; a slightly-rounded rectangle reads as a field value). Active filter
chips get a filled ground **and** a `×` affordance; the fill alone is not the signal.

**Never:** invent a term. Every chip's `term_id` must resolve in `taxonomy/`; a chip with an
unresolvable term is a build failure, because a stale chip silently breaks the coverage analysis.
Never render more than 6 chips before a `+N more` disclosure.

> **Astro 7 hazard, owned by this document.** `compressHTML` defaults to `'jsx'` in Astro 7 and
> **removes the whitespace between adjacent inline elements** — a row of `<FacetChip>` spans will
> render as `visionmultimodalvqa`. Set `compressHTML: true` explicitly in `astro.config.mjs` on day
> one. This is recorded here rather than only in
> [08-infrastructure-and-build.md](08-infrastructure-and-build.md) because the symptom appears as a
> design bug and will otherwise be debugged as one.

### 6.3 `<VerificationBadge>`

**Needs:** `verification` (enum), `disputed` (bool), `disputed_by[]`.

**Spec:** seven-segment glyph + level name, one segment per rank in `taxonomy/verification.yaml`
(§4.3). At `--fs-2xs` in table cells the name abbreviates to a
2-letter code with the full name in the accessible name, never as a `title` attribute alone (titles
are invisible to touch and unreliable to screen readers). `disputed` overlays a warning glyph and
links to `disputed_by`.

**Never:** render without a level. There is no "unknown verification" — a claim whose verification is
unrecorded is a schema violation, not a rendering case.

### 6.4 `<ConditionMeter>`

**Needs:** `condition_completeness` (0–1), `fields_specified`, `fields_material_total`.

**Spec:** a **discrete segmented meter**, not a continuous bar, with one segment per material field
in this benchmark's comparability profile. Reason: `condition_completeness` is a ratio over a small
integer field count, and a continuous bar implies a precision the quantity does not have. The
segment count is read from `fields_material_total` at render time and is **not** a constant in this
document: [04-data-model.md](04-data-model.md) §8 owns the material-field set and states that it is
per-benchmark-shaped rather than global, so a schema-level "11 fields" would be a category error and
would go stale the first time a profile changed. The popover carries the literal readout — "7 of 11
material condition fields specified" — plus the list of which are unknown. Cap the rendered segments
at twelve and fall back to a fraction label above that, so a wide profile does not produce an
unreadable comb.

Expect this component to read near-empty on most of the corpus: the bulk-ingested Epoch rows have a
mean completeness around **0.10**. That is the correct and intended appearance. The meter is not a
score to be optimised; it is the visible cost of cheap data.

**Never:** round up. Never hide itself when completeness is low. Never colour low completeness as an
error — low completeness is a fact about the source, not a fault of the record.

### 6.5 `<ValueCell>` with provenance popover

The most important component in the system, and the one that makes the transparency claim real rather
than rhetorical.

**Needs:** `value`, `metric_id`, `unit`, `verification`, `condition_completeness`, `claim_id`,
`comparability_key`, `uncertainty`, `source_id`, `date_reported`.

**Spec:** value in tabular mono-adjacent figures, verification badge inline after it, condition meter
below at `--fs-2xs`. The whole cell is a `<button>` that opens a popover containing: the source with
its archive link, the reporter, the date, the full `EvalConditions` record with unknown fields shown
as unknown, and a permalink to the claim at the current commit SHA.

The popover must satisfy **SC 1.4.13 (Content on Hover or Focus)**: dismissible with `Escape` without
moving focus, hoverable (the pointer can travel into it without it closing), and persistent until
dismissed. Use the native Popover API with `popover="auto"` and CSS anchor positioning where
available, with a small JS fallback — not a third-party floating-UI dependency, which would cost more
than the whole rest of the site's JS.

**Never:** render the value without the badge and meter, in any breakpoint, in any density mode.
There is no "compact mode" that drops provenance. If space is short, the *value* wraps to a second
line; provenance does not get cut.

### 6.6 `<SourceCitation>`

**Needs:** `source_id`, `title`, `publisher`, `url`, `archive_url | null`, `retrieved_at`,
`source_type`.

**Spec:** title as the link; publisher and date in `--c-ink-muted` `--fs-xs`; a separate small
`archive` link with a 🗄-equivalent glyph. Where `archive_url` is null, render `not archived` in the
absent token — visibly, because unarchived sources are a known decay risk and one of the project's
own quality metrics.

**Never:** render a link without `retrieved_at`. Never present an archive link as if it were the
primary source, and never present a primary source as if it had been archived when it has not.

Artificial Analysis data is a specific case: their terms permit attribution but contractually bar
redistribution. The citation component therefore has a `link_only: true` mode that renders the
citation and the link but no excerpted value. Enforced in the data layer, surfaced here.

### 6.7 `<Staleness>`

**Needs:** `last_verified_at`, `entity_kind`, optional `upstream_last_changed_at`.

**Spec:** a small dot-plus-text mark with four bands (`fresh` < 90d, `ageing` 90–365d, `stale`
> 365d, `unverified since creation`). Always shows the absolute ISO date; the relative phrasing is
secondary (§11.3).

**Why this component exists at all.** Every prior cross-domain catalogue died of staleness and none of
them showed it. Stanford's Ecosystem Graphs is still cited as a data source while 20 months stale —
its *design* never admitted that. One study found 137 of 195 safety benchmarks had stale repositories;
BetterBench found 17 of 24 had no working reproduction scripts. Rendering our own decay is both an
honesty requirement and the single strongest differentiator available in a category defined by silent
rot. It must be visible on entry pages by default, not behind a disclosure.

**Never:** hide when stale. Never compute freshness from the *file's* git mtime — that measures
editing, not verification.

### 6.8 `<ComparabilityBanner>`

**Needs:** the set of `comparability_key`s in scope, and the field-level diff the build computed.

**Spec:** a `--c-caution` banner above the affected view, naming exactly which material fields differ,
as a table (field · value in set A · value in set B · …). Two actions offered: *restrict to one
condition set* (with the dropped-claim count shown) or *proceed with every affected cell flagged*.
There is no third option that silently proceeds.

**Never:** editorialise. The banner states what differs; it never says one set is better. Never use
`--c-alert` — non-comparability is a fact about the data, not an error by the user.

### 6.9 `<Absent>` — the absence token

**Needs:** `state` (one of four, §11.2) and optionally `reason`.

**Spec:** `∅` in `--c-absent-ink` plus the state word at `--fs-xs`. In a chart, an absent value is
drawn in a dedicated lane below the axis so it *occupies space*. In a matrix cell, it is the hatch. In
a table cell, it is the glyph plus word.

**Never:** render as an empty string, a blank cell, a dash, or zero. An em dash is ambiguous with a
range dash and a minus sign and is therefore banned from this role.

### 6.10 `<EmptyState>`

**Needs:** `context` (`search | filter | domain-page | coverage-cell`), `applied_filters`, optional
`suggestions[]`.

**Spec:** three sentences maximum: what happened, what it means, one action. A filter empty-state
lists the applied filters as removable chips and offers the single most-constraining one to drop.

**The most important empty state in the product** is *a coverage cell with no benchmarks*, and it is
not an error — it is the answer. It renders as a finding: "No benchmark in the index measures
`calibration-uncertainty` in `robotics-embodiment`." plus the curation-coverage caveat for that
domain, plus the nearest partial matches. Cross-ref [12-analytics-and-trends.md](12-analytics-and-trends.md).

**Never:** apologise, use an illustration, or say "Oops".

### 6.11 `<Skeleton>` and loading

**Spec:** skeletons only where content genuinely arrives late — the corpus fetch for the Workbench,
the semantic-search tier, the AI panel. Skeleton blocks match the final element's exact box so no
shift occurs. A skeleton **animates only when `prefers-reduced-motion` is `no-preference`**; otherwise
it is a static tinted block.

**Never** put a skeleton on a statically rendered page. Entry pages, list pages and taxonomy pages
arrive complete; a skeleton there is a lie about the architecture. If a skeleton appears on a detail
page in development, something has been moved to the client that should not have been.

### 6.12 `<ChartFigure>` and the table-fallback disclosure

Every chart in the site is produced from a single `{ rows, columns, caption, units, notes }` object,
and the build emits **both** the chart and a `<table>` from it. This is a build-time invariant, not a
component convention: the chart and the citable data cannot disagree because they are the same
object.

**Server-rendered DOM order:** `<figure>` → `<figcaption>` → `<table>`. On hydration, the island
inserts the chart *before* the table and wraps the table in `<details><summary>Show data table (N
rows)</summary>`. With JavaScript off, the table is the page. This satisfies the no-JS requirement,
the screen-reader requirement and the crawler requirement with one mechanism.

**Never** rely on `aria-label` on an SVG, and **never** rely on ECharts' own `aria` option — its
SSR + ARIA behaviour has a known open issue (#19191, reported against 5.4.3; whether it is fixed in
6.1.0 is a Phase-0 check owned by [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
§5.4, and is not carried as an open item here as well). The rule above makes that irrelevant, which
is the point of making it a build invariant rather than a component setting.

### 6.13 `<CiteThis>`

**Needs:** `entity_id`, `commit_sha`, `release_doi | null`, `retrieved_at`.

**Spec:** a bordered block at the foot of every entry page and every analysis view offering BibTeX,
APA, a plain permalink at the commit SHA, and a link to the raw YAML at that SHA. It is a component
rather than a footer string because citability is a differentiator and needs to look like a feature.

### 6.14 `<Contribute>`

**Needs:** `entity_id`, `entity_kind`, the issue-form URL template.

**Spec:** present on every entry page. The **primary** action is "Suggest a correction", which opens a
pre-filled GitHub **issue form** — not a pull request. A secondary, smaller "Edit the YAML" link
serves power users.

**Why this is a design decision and not a workflow one.** The most instructive failure in the
landscape is `JonathanChavezTamales/llm-leaderboard`: a JSON-in-git, schema-validated community
catalogue with 356 stars that deprecated itself and converted into a closed website, stating
contribution friction — PRs being too slow versus per-entry discussion threads — as the reason. If the
most prominent contribution affordance on the page is a PR link, we have reproduced that failure in
the interface layer regardless of what the workflow document says. The issue-form path must be the
visually primary one. See [05-repository-and-workflow.md](05-repository-and-workflow.md).

### 6.15 `<AiPanel>`

**Needs:** the deterministic result set, the facet query, `unmapped_terms[]`, the model's prose,
and per-sentence citation bindings.

**Spec:** the AI layer is **a lens, never a source**, and the container must make that structurally
visible. Order within the panel is fixed: (1) the **editable facet query** as chips, with a
per-constraint "loosen" toggle; (2) the deterministic result list or the computed table; (3) the
model's prose, in a visually subordinate block labelled *generated summary of the results above*,
with every factual sentence carrying an inline citation chip. Unmapped terms render as "I ignored:
…". Any numeric quantity inside the prose is rendered by `<Stat>` or `<ValueCell>` from the computed
value, never from model output.

**Never:** put the prose above the data. Never style the AI block with an accent, a gradient or a
sparkle glyph — it is the least authoritative content on the page and should look it. Never let the
panel's absence change the layout: with the Worker offline the deterministic result list occupies the
same box with a one-line notice. Cross-ref [11-ai-features.md](11-ai-features.md).

---

## 7. Data-visualisation conventions

Shared across every chart, whether hand-rolled SVG or an ECharts island.

### 7.1 Axes, gridlines, marks

- One gridline direction only — the one you read values along. Gridlines at `--c-border`, 1px,
  behind marks, never in front.
- The baseline axis at `--c-border-strong`. No axis box, no ticks longer than 4px, no minor ticks.
- **No 3D, no gradients-as-decoration, no drop shadows on marks, no rounded bar caps.**
- The y-axis starts at the **metric's defined floor**, not at zero by reflex. For a 4-option
  multiple-choice benchmark, zero is misleading and 0.25 is the meaningful floor — so the **chance
  baseline is drawn as a labelled rule**, and the human baseline as a second, heavier labelled rule.
  Cross-ref [12-analytics-and-trends.md](12-analytics-and-trends.md) for how both are derived.
- Any axis truncation carries a visible axis-break marker. Silent truncation is banned.
- Hue carries at most **6 series**. Beyond six, direct-label and grey the rest. **Domain family is
  never one of those series** (§4.2), and neither is organisation — a twelve-organisation categorical
  scale is the same violation wearing a different label, so the Frontier Timeline direct-labels its
  top six by release count and greys the rest (see [10-visualization.md](10-visualization.md) V4).

### 7.2 Uncertainty

The data model records `uncertainty: { type: stderr | ci95 | range | none, value, n_runs }`. Each
renders differently and none is ever inferred:

| `type` | Mark |
| --- | --- |
| `ci95` | Capped whisker, labelled "95% CI" in the legend |
| `stderr` | Lighter band at ±1 SE, labelled "±1 SE — not a confidence interval" |
| `range` | Bar spanning min–max with the reported point marked inside it |
| `none` | Point drawn with a **dotted outline and no whisker**, legend entry "no uncertainty reported" |

**Never draw a whisker that was not reported.** A plausible-looking error bar computed from nothing is
worse than no error bar, because it reads as rigour.

### 7.3 Self-reported versus verified

- A **verified** point is a filled mark.
- A **self-reported** point is an open mark: unfilled, 1.5px stroke.
- A **disputed** point carries a strike glyph and is clickable to the dispute.
- A **line segment whose right-hand endpoint is self-reported is dashed.** This is how the Saturation
  Wall shows that a frontier is being set by an unverified claim, which is the common case and the
  one most worth seeing.
- **Machine-ingested** claims are drawn at reduced opacity with a dotted outline and are **excluded by
  default from comparison views**, while remaining visible in browse and trajectory views. This is the
  rendering half of the settled Epoch policy: bulk data provides coverage without polluting
  comparison.

### 7.4 Unknowns, zeros and non-applicables

Three genuinely different things, three renderings, never collapsed:

| State | In a table | In a chart | In a matrix |
| --- | --- | --- | --- |
| Value is genuinely zero | `0` (tabular) | Mark at zero | Lightest ramp stop + `0` |
| Value not reported / not curated | `∅ not reported` | Mark in the **unknown lane below the axis** | Slash pattern + `?` |
| Field not applicable here | `n/a` in `--c-ink-faint` | Omitted, with a legend note of how many | Dotted border, no fill |

The **unknown lane** is the non-obvious one and is worth the implementation cost: a thin band below
the plot area where unknowns are drawn as small open marks at their x-position. It converts "seven
claims exist but three have no reported value" from invisible into a visible third of the evidence.

### 7.5 Small multiples

For the Saturation Wall (hundreds of sparklines, generated as build-time SVG rather than chart-library
instances):

- Cell 128 × 32 CSS px at `--bp-lg`+; minimum 96 × 28; 1–2 per row below `--bp-sm`.
- Maximum 8 per row at `--bp-lg`.
- **Uniform y-domain within a domain _family_.** When a family's y-domain differs from the global
  one, that is stated in the block header, not left for the reader to infer. ("Domain-family group"
  was ambiguous between the two levels once the presentation groups became a real vocabulary; the
  rule is per family.)
- **Blocks are ordered and banded by presentation group** (§4.2), each block titled with the family
  name and each group preceded by a group heading. No colour: strokes stay `currentColor`.
- The human baseline is a horizontal rule; headroom is a shaded region; a benchmark with no known
  baseline shows the trajectory, no shading, and a one-line reason.
- `currentColor` and CSS custom properties throughout, so dark mode is free and printing works.

### 7.6 Motion

No animation on load, ever. Transitions only on user-initiated state change, ≤ 200ms, ease-out.
Nothing auto-advances, auto-rotates or auto-plays. Under `prefers-reduced-motion: reduce`, all
transitions collapse to 0ms and the Atlas zoom becomes an instant jump.

---

## 8. Accessibility

WCAG 2.2 Level AA is the target, treated as a **first-pass requirement**. The reason is not
compliance theatre: the accessible path and the no-JS citable path and the crawlable path are
substantially the same artefact, so building it once early is cheaper than retrofitting it three
times. The Atlas's screen-reader fallback *is* its responsive fallback *is* its no-JS rendering.

### 8.1 The 2.2-specific criteria that actually bite

| SC | Consequence here |
| --- | --- |
| **2.5.7 Dragging Movements** | **The Atlas lasso-select must have a non-drag equivalent.** The archived plan's "lasso-select to send a group to the workbench" is not sufficient on its own. Decision: the *filter* is the primary selection mechanism ("select all N currently visible"), with per-node "add to selection" via keyboard or click; lasso is a shortcut, never the only path. |
| **2.5.8 Target Size (Minimum)** | 24 × 24 CSS px minimum for chips, badges, table row actions, legend toggles. Atlas nodes are exempt as essential presentation, and the list view is their conforming alternative. |
| **2.4.11 Focus Not Obscured** | Sticky table headers and the sticky filter bar must not cover a focused row. Implemented with `scroll-margin-block-start` equal to the sticky stack height, plus a test. |
| **1.4.13 Content on Hover or Focus** | The provenance popover must be dismissible, hoverable and persistent (§6.5). |
| **3.3.7 / 3.3.8** | N/A by construction — v1 has no auth and no forms that re-enter data (hard constraint 7). Record it as N/A rather than silently omitting it. |
| **1.4.12 Text Spacing** | No fixed-height text containers (§3.3). |

### 8.2 Keyboard

Every interactive view is fully operable from the keyboard, including the four dense ones.

- **Atlas.** A roving `tabindex` over a linearised node list ordered by domain cluster then name,
  with the six presentation-group headings as the first level of the roving order and the 19 family
  headings as the second. `Tab` moves between clusters; arrow keys move within a cluster; `Enter`
  opens the entry; `Space` toggles selection; `/` focuses search. The canvas itself is
  `aria-hidden="true"` — it is a picture of the list, not a separate thing. **That linearised list
  *is* the Atlas legend** (§4.2: there is no colour key, so the legend is a 19-row family index with
  group headings, counts and a per-row highlight toggle). One component serves four requirements —
  legend, no-JS fallback, screen-reader linearisation and roving-tabindex target — and zero colour
  swatches.
- **Coverage matrix.** A real grid: `role="grid"`, arrow keys move by cell, `Home`/`End` by row,
  `Ctrl+Home` to origin. The cell's accessible name is "domain × capability: N benchmarks".
- **Workbench.** Standard table semantics plus `Escape` to close any popover. Horizontally scrolling
  table containers get `tabindex="0"` so keyboard users can scroll them — a common and consequential
  omission.
- **Skip link** to main content on every page; a second skip link past the filter rail on list pages.

### 8.3 Focus

```css
:focus-visible {
  outline: 2px solid var(--c-focus);
  outline-offset: 2px;
  border-radius: 2px;
}
```

`outline: none` is banned by lint. The focus colour must clear 3:1 against both the element and its
surroundings (SC 1.4.11), which is why `--c-focus` is a dedicated token rather than reusing
`--c-link`.

### 8.4 Screen readers in data-dense views

**The table is the accessible representation. Full stop.** Charts get `role="img"` plus
`aria-labelledby` pointing at the `<figcaption>` and `aria-describedby` pointing at a one-sentence
summary the build computes from the same data object — for example: *"SOTA rose from 0.34 to 0.71
across 9 claims between 2023-03 and 2026-08; human expert baseline 0.92; 4 of 9 claims are
self-reported."* That sentence is generated by code from structured fields, never written by hand and
never written by a model, and it is the single highest-value accessibility feature in the plan because
it also serves search engines and anyone skimming.

No `aria-live` on charts or on filter results. Filter changes announce once, politely, through a
single dedicated status region ("312 benchmarks match"), debounced at 500ms.

### 8.5 Preference media queries

- `prefers-reduced-motion: reduce` → §7.6.
- `prefers-contrast: more` → borders promote to `--c-ink-muted`, subtle surface fills drop to
  `--c-bg`, chip grounds become outlines.
- `forced-colors: active` (Windows High Contrast) → chips and badges must keep their glyph and text;
  no state may depend on `background-color` alone. Test explicitly; this mode is where
  colour-only encodings fail loudest. **Domain family survives this mode intact by construction,
  because it never used colour** (§4.2) — worth writing down, because it is the one categorical
  encoding in the system that needs no forced-colors fallback at all.

### 8.6 No-JS

Fully readable and navigable without JavaScript: entry pages, list and browse pages, taxonomy pages,
the coverage matrix (as its table), the Atlas (as its grouped list), every chart (as its table), the
release feed, and all citation blocks. Search degrades to links into the browse-by-facet pages.

`<noscript>` is **not** the strategy. The default output is the working thing and JavaScript is
additive; a `<noscript>` block is an admission that the real page is the JS one.

---

## 9. Dark mode

Dark is a **first-class theme with its own authored and tested tokens**, not an inversion. Three
things break under naive inversion and each needs a deliberate decision.

1. **Chroma behaves differently.** Large dark fills need *less* chroma to avoid vibrating; small marks
   and text need *more* to stay legible. The dark token set therefore adjusts chroma per role, not
   globally.
2. **Sequential ramps must be re-authored, not flipped.** In light mode "more value = darker ink". In
   dark mode "more value = brighter". A mechanical inversion of the light ramp would preserve the hex
   relationships and destroy the reading.
3. **Shadows do not work.** Elevation in dark mode comes from surface lightness steps and borders.

```css
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* … dark tokens … */ }
}
:root[data-theme="dark"] { /* … same dark tokens … */ }
```

```css
/* Representative dark values */
--c-bg:             oklch(16.0% 0.012 250);   /* not #000 — pure black haloes under light text */
--c-surface:        oklch(20.0% 0.014 250);
--c-surface-sunken: oklch(13.5% 0.010 250);
--c-border:         oklch(30.0% 0.016 250);
--c-border-strong:  oklch(42.0% 0.018 250);
--c-ink:            oklch(92.0% 0.008 250);   /* not #fff */
--c-ink-muted:      oklch(72.0% 0.012 250);
--c-ink-faint:      oklch(55.0% 0.012 250);
--c-link:           oklch(78.0% 0.13  250);
--c-focus:          oklch(80.0% 0.16  255);

/* Headroom ramp re-authored dark→bright, not inverted */
--seq-head-0: oklch(26% 0.030 85);
--seq-head-6: oklch(88% 0.150 60);
```

A useful side effect of §4.2: deleting the family palette removes **18 tokens** (six hues × three
steps) from the dark theme's re-authoring and re-testing burden. The dark theme's remaining colour
work is three sequential ramps — verification, headroom, coverage — plus the semantic states, the
interaction tokens and the two emphasis tokens. That is a real reduction in the most error-prone part
of theming, and it is a cost that was being paid for an encoding we are no longer using.

**The theme toggle is three-state** — *system / light / dark* — persisted in `localStorage`, defaulting
to system. Reason: a two-state toggle silently overrides the OS preference forever after one
accidental click.

**ECharts does not follow CSS custom properties.** It needs an explicit theme object via
`echarts.registerTheme` and a re-`init` on the `prefers-color-scheme` change event. This is a concrete
implementation task with a named risk — a flash of wrong-theme chart on load — mitigated by emitting
the SSR SVG in the *neutral* token set and swapping on hydration. The hand-rolled SVG sparklines use
`currentColor` and `var()` and follow the theme for free, which is one more reason they are hand-rolled
(§7.5).

**The theme class is written before first paint** by a four-line inline script in `<head>`. This is the
only render-blocking script the site allows, and the justification is specific: a flash of the wrong
theme on a reference site read in a dark room is a real defect, and the alternative (CSS-only
`light-dark()` with no manual override) loses the three-state toggle.

---

## 10. Responsive strategy

Be decisive: **some dense views should change representation rather than shrink.** Pretending
everything is fluid produces four broken views instead of four honest ones.

| View | ≥ `--bp-lg` | Phone (< `--bp-md`) | Reason |
| --- | --- | --- | --- |
| **Atlas** | WebGL map, 1,500 nodes | **Replaced** by the grouped list (the same server-rendered markup that is its a11y and no-JS fallback), with a note: "The map view needs a wider screen." | A 1,500-node map in a 390px viewport with finger-sized hit targets is not a degraded map, it is a broken one — and we already own a good alternative because accessibility forced us to build it. This is the clearest case of a11y work paying for responsive work. |
| **Coverage matrix** | 19 × 13 heatmap — 19 domain families × 13 capability groups, 247 cells; the group vocabulary is owned by [02-taxonomy.md](02-taxonomy.md) §4.3 — banded by presentation group | **Replaced** by a ranked gap list, plus a per-family drill-down showing capability coverage as a bar list | On a phone the matrix's value is the *ranking*, not the picture. The Gap Finder representation is strictly more useful at that size. |
| **Comparison workbench** | Table + parallel coordinates side by side at `--bp-xl` | **Parallel coordinates dropped entirely.** Table becomes one card per system, stacked, each listing its benchmark rows. Capped at 3 systems with "compare more on a wider screen". | The point is cell-to-cell comparison; an 8-column horizontally-scrolling table defeats it, and parallel coordinates below ~600px are unreadable. |
| **Saturation wall** | 8 sparklines per row | 1–2 per row, unchanged otherwise | The one dense view that is naturally responsive, because it was already small multiples. |
| **Frontier timeline** | Two-band time river with brush | Single band (benchmarks only) with a date-range select instead of a brush | Brushing needs a pointer; the `2.5.7` non-drag alternative is the same control. |
| **Entry page** | Prose column + metadata rail | Single column; the rail becomes a **compact fact strip above the prose**, not a collapsed disclosure below it | On a phone the facts are usually why you arrived. |
| **Browse and search** (V11) | Facet rail left, results right, counts live | Facet rail collapses into a **sticky "Filters (3)" sheet** opened from a bar above the results; the results list is the page and never moves under the user. Applied facets stay visible as a horizontally scrollable chip row below the bar, each chip individually removable. | This is the workhorse view and the one most phone sessions will land in, so it is the view that must not be an afterthought. Facets are a *refinement* on a phone rather than a browsing spine, and a permanently visible rail costs the results half the viewport. The failure mode being avoided is the one every faceted catalogue ships: filters that are applied but invisible, so a user reads an empty result set as "this project has no data" rather than as "you have three filters on". |

**Mobile performance budgets, because the landing page is not where phone users land.** A phone
session usually starts at a *detail page* reached from a search engine, so the landing-page budget in
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §8 does not cover the common case.
Two budgets are added there and named here because this document owns what has to render: the
**entry page interactive in under 2.0 s on mid-tier mobile over 4G with no JavaScript required for
first meaning**, and **V11 first result painted in under 2.5 s** on the same profile. Both are
achievable by construction — the entry page's required JS is 0 KB and V11's is ≤ 60 KB — which is
the point of having required them. What is not yet known is the traffic split, and guessing it would
be inventing a number: instrument the share of sessions that begin on an entry page in the first
quarter after launch ([08](08-infrastructure-and-build.md) §10 owns the log-derived, no-beacon
analytics), and revisit the budget ordering once it is measured rather than assumed.

General table behaviour below `--bp-lg`: `overflow-x: auto` on a `tabindex="0"` container, sticky first
column, a visible scroll shadow, and a column-priority order so that the least important columns are
the ones off-screen. Never a "responsive table" that reflows each row into a definition list — it
destroys the vertical comparison that is the entire reason for a table of numbers.

---

## 11. Voice and content design

### 11.1 Register

Neutral, third person, present tense. Describe; do not praise. The site has no opinions about
benchmarks, only evidence-linked statements about them (hard constraint 4).

Banned from all descriptive prose: *impressive, landmark, groundbreaking, revolutionary, powerful,
seamless, robust, leverage, utilise, cutting-edge, best-in-class, game-changing.* "State-of-the-art"
is permitted **only** as the noun phrase for the current frontier value, never as an adjective.
"Best" is banned entirely; the correct phrasing is *"highest reported value under these conditions"*.

Sentence case for every heading, button, chip and label. Title Case reads as marketing and degrades at
`--fs-xs`.

**A presentation group never appears in a claim sentence.** This is property 4 of the `display_only`
grouping in §4.2, and it is the one property no script can check, so it is a review rule stated here:
every rendered sentence that asserts coverage, a gap, a count or a percentage names a **domain family
or a subdomain**, never one of the six groups. "No benchmark in the index measures
`calibration-uncertainty` in *Life and health sciences*" is forbidden prose even though the
underlying cells are real, because its denominator is built from an ordering device rather than from
the taxonomy, and a specialist who disputes the grouping has then invalidated the finding without
touching the data. The gap-narration template in [10-visualization.md](10-visualization.md), reused
verbatim by [11-ai-features.md](11-ai-features.md), is already written this way; the rule exists so it
stays that way when someone adds a sentence by hand.

### 11.2 The four absence phrases — a typed vocabulary

Four distinct data states, four fixed phrases, never interchanged. This is microcopy as a type system
and it is one of the most useful things in this document:

| Phrase | Means | Typical cause |
| --- | --- | --- |
| **not reported** | The source did not state it | A launch blog post with no eval conditions |
| **not recorded** | The source may state it; we have not curated it | Curation backlog |
| **not applicable** | The field is meaningless for this entity | `judge_model` on an execution-tests benchmark |
| **unknown** | Reserved for **material condition fields** specifically | A `null` in `shots` or `selection_strategy` |

`unknown` is deliberately narrow because in the data model `null` in a material field means *unknown,
not default*, and that distinction drives `condition_completeness` and the comparability key. Using
"unknown" loosely would blunt the one word that carries technical weight.

Contributor-facing guidance and the schema field descriptions use the same four words, so the YAML,
the validation messages and the rendered page agree.

### 11.3 Uncertainty and disputes

Uncertainty about *our own* data is phrased as a fact about curation, not a hedge: *"Conditions for
this claim are not recorded (2 of 11 material fields specified, where 11 is this benchmark's
`fields_material_total`)."* Never *"we think"*, never
*"approximately"* applied to a value we did not compute.

Disputes are presented, never adjudicated. The template:

> Anthropic reports 0.712 (self-reported, 2026-05-04). The SWE-bench maintainers report 0.648 under
> re-run conditions (independent-reproduction, 2026-06-18). Material conditions differ in:
> `n_samples`, `selection_strategy`, `retries_allowed`.

The first two sentences are data. **The third sentence is computed**, not written — it is the
field-level diff rendered as prose. A human curator never writes a sentence asserting why two numbers
differ; they record the claims and the machine states the difference. That is the mechanism by which
the site stays non-editorial while still being useful.

### 11.4 Numbers and dates

- **Locale is fixed to `en`**, not the visitor's locale. A citable reference must not render
  differently for different readers; a screenshot has to mean one thing.
- Decimal point, comma thousands separator at ≥ 10,000.
- **Show the metric in its native form.** If the benchmark reports 0–1, render `0.712`; do not silently
  convert to `71.2%`. Unit conversion is a transformation of someone else's data and needs a reason.
- **Precision is the source's precision.** If the source gave two significant figures, render two.
  Trailing zeros are meaningful and preserved. Never render more digits than were reported.
- Dates are **ISO 8601** (`2026-09-17`) in every data context, wrapped in `<time datetime>`. Prose may
  use "17 September 2026". Relative time ("3 months ago") is only ever a *supplement* to a visible
  absolute date — a reference work read in 2030 must not tell the reader something happened "3 months
  ago".
- System and organisation names render exactly as the vendor writes them, with no auto-title-casing and
  no normalisation of internal capitalisation.

### 11.5 Errors and empties

Three sentences maximum: what happened, what it means, one action. No apologies, no humour, no
illustrations, no "Oops". For the AI layer specifically, the degraded state is a plain one-line
notice — *"AI rationale unavailable — showing deterministic facet search."* — with the results
unchanged beneath it.

---

## 12. Performance of design

The design must not be the reason the 2s interactive budget is missed. Three disciplines.

### 12.1 Font loading

- **Self-host WOFF2.** No Google Fonts, no third-party font CDN. Reasons: a render-blocking connection
  to a third party on every page load, a privacy exposure on a site that has no accounts and should
  collect nothing, and a dependency that can change under us. Fonts are committed assets served from
  the same origin.
- **Subset aggressively** to Latin plus the specific glyphs the system uses: `∅ → ± ≥ ≤ × ▲ ▼ − ·
  §`. Budget: **≤ 120 KB total for all faces**, which two subset variable faces plus a subset mono
  comfortably meets.
- **Preload exactly two files** — the sans and the mono — with
  `<link rel="preload" as="font" type="font/woff2" crossorigin>`. Do **not** preload the condensed
  face; it is used only on two views and can arrive late.
- `font-display: swap`.

### 12.2 CLS

- **Metric-compatible fallback faces.** Declare a local-only `@font-face` alias with `size-adjust`,
  `ascent-override` and `descent-override` tuned to match Plex, and place it second in the stack.
  This is what makes `swap` safe. (*The exact override percentages must be measured with a fallback-font
  generator against the shipped subsets — unverified; do not copy values from a blog post.*)
- Every chart container and image has an explicit `aspect-ratio`. The chart island hydrates into a box
  the server-rendered table already sized.
- Badges, meters and chips have fixed inline sizes so a late value cannot reflow a table row.
- Tabular figures (§3.4) mean a value change never changes a column's width.
- The theme class is set before first paint (§9), so no theme flash.

### 12.3 CSS discipline

- **No CSS framework.** Budget: **≤ 20 KB gzipped total CSS**, inlined in `<head>` while it fits
  within the first TCP congestion window (~14 KB), linked beyond that. A utility framework that ships
  150–200 KB would eat the entire budget the data was supposed to spend.
- No runtime CSS-in-JS. No client-side style recalculation on filter — filtering toggles a class or a
  `data-` attribute and CSS does the rest.
- No layout that requires JavaScript to be correct. If the JS never loads, nothing is misaligned —
  only less interactive.
- Icons are inline SVG in a sprite, never an icon font. An icon font is a render-blocking download that
  fails into meaningless glyphs and reads as garbage to screen readers.

---

## 13. Governance of the design system

The tokens live in `design/tokens.yaml` and are generated into `site/src/styles/tokens.css` and
`site/src/lib/tokens.json` (consumed by the ECharts theme and the SVG generators) by the same Python
build that generates everything else. The design system is therefore diffable, reviewable, forkable
and citable on exactly the same terms as the catalogue — which is the correct posture for a project
whose central claim is that the whole artefact is auditable.

CI gates, all fast and all blocking:

| Check | Fails on |
| --- | --- |
| `check_contrast.py` | Any declared ink-on-surface pair below its WCAG 2.2 AA threshold, in either theme |
| `check_palette.py` | A family-colour token reappearing; a categorical set above 6 members or missing a redundant channel; a non-monotonic or under-stepped ordered ramp; two co-occurring tokens of *different meaning* below the ΔE floor, the lightness floor and the pattern exemption — under deuteranopia / deuteranomaly-50 / protanopia / tritanopia in both themes |
| `lint_tokens.mjs` | Raw colour literals outside `tokens.css`; `px` font sizes; `outline: none`; any component CSS rule keyed on `[data-domain-family]` or `[data-domain-group]` that sets `color`, `background`, `background-color`, `fill` or `stroke` |
| `lint_absence.mjs` | `{v \|\| ''}`, `?? ''`, `?? '—'` and truthiness-guarded value renders under `components/` |
| `lint_svg.mjs` | Any text node in built SVG below 11px |
| Axe / Pa11y over a fixed page sample | Any WCAG 2.2 AA violation on the 8 archetype pages |

Adding a colour requires a token and a reason in the commit message. Adding a font weight requires
deleting one. Adding a component requires filling in its "never" row in §6 — a component whose
constraints are not stated is a component that will be misused within a month.

**What this document does not decide**, recorded in [15-open-questions.md](15-open-questions.md): the
exact ΔE threshold for the CVD gate, now scoped to **cross-meaning pairs** rather than to family
swatches, since there are no family swatches; whether IBM Plex's variable builds are usable for our
subsets or whether static weights are required; whether a print stylesheet is worth building in v1;
and whether the emphasis mechanism needs a **group-level** mode in addition to the family-level one
(§4.2 channel d), which should be answered by watching people use the Phase 1 prototype rather than
by argument. The old open question — whether the six-group domain colouring should be exposed as a
user-selectable grouping in the Atlas legend, with the acknowledged risk that it starts being cited
as a taxonomy level — is **closed**: there is no six-group colouring, the grouping is exposed as
banding and as the Atlas family index, and it is a governed `display_only` vocabulary rather than an
ungoverned colour key.
