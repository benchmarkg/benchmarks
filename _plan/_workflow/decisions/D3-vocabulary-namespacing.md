# D3 — Vocabulary namespacing and CI check 9c

- **Status:** Decided
- **Date:** 2026-09-21
- **Scope:** the identifier form of taxonomy terms; CI checks 9a and 9c in
  [05-repository-and-workflow.md](../../05-repository-and-workflow.md) §9; the `puzzle-solving`
  duplication; the forbidden-identifier mechanism.
- **Serves:** differentiator 3 (coverage and gap analysis). Every ruling below is justified by what
  it does to the interpretability of a coverage cell, not by tidiness.

---

## 1. The decision

**D3.1 — The on-disk identifier scheme does not change. Subdomain ids are family-qualified paths
(`reasoning-general/planning`); capability ids are bare slugs (`planning`); the facet is carried by
the field name, not by a prefix on the value.** There is no `capability:` or `domain:` prefix in
`data/`.

**D3.2 — A *facet-qualified reference* (FQR) form is defined — `capability:planning`,
`domain:reasoning-general/planning` — and is mandatory in exactly the six contexts listed in §3.4,
all of which are places where a term appears outside a facet-typed field.** It is forbidden
everywhere else.

**D3.3 — Check 9c as written is not a failing check; it is a wrong check, and it would still be
wrong after the collisions were removed.** It compares capability *ids* against subdomain *leaf
segments*. A leaf segment is not an identifier — `planning` is the tail of
`reasoning-general/planning` the way `verified` is the tail of `swe-bench@verified`. The identifier
sets are already disjoint and have been since the domain vocabulary acquired two levels. 9c asserts
a property of a projection and reports it as a property of the namespace. It is replaced by three
checks: **9c** (within-vocabulary uniqueness, correctly scoped), **9d** (a declared homograph
allowlist), **9e** (tautological coverage cells must be marked as such in the build artifact).

**D3.4 — The four capability/subdomain homographs stay. They are not renamed.** `planning`,
`spatial-reasoning`, `temporal-reasoning` and `compositional-generalization` name the same concept
seen through two facets, which is what a faceted classification is *for*. The identifier space must
accommodate the classification; letting a set-difference assertion rewrite the vocabulary would be
the CI check writing the taxonomy.

**D3.5 — No subdomain leaf may appear under two families. `games-planning/puzzle-solving` is renamed
to `games-planning/puzzle-games`; `reasoning-general/puzzle-solving` is untouched.** This is a
within-facet duplication, which is a different and genuinely harmful thing.

**D3.6 — D3 adds no entries to `taxonomy/forbidden-identifiers.yaml` and none to
`taxonomy/retired-ids.yaml`,** because the vocabulary has not been published: `taxonomy/VERSION` is
pre-`1.0.0` and the freeze is Stage 5 of
[03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) §2. The same rename after the
freeze would be a MAJOR retire-plus-add. Check 9a, however, has two live defects unrelated to D3
that must be fixed in the same pass (edits 18, 20).

### The tension, resolved rather than dodged

The brief asks whether a `planning` subdomain inside `games-planning` and a `planning` capability
are both correct and the collision meaningless, or whether this is exactly the ambiguity that makes
a coverage cell uninterpretable. **Both, and the boundary between them is sharp and small.**

Name the failure mode: **the tautological diagonal.** For a homograph leaf `X` that exists as
subdomain `F/X` and as capability `X`, the fine-grid cell `(F/X, X)` is occupied by construction.
Any benchmark a curator files under the subdomain `reasoning-general/planning` will carry
`capability: [planning]`, because the two terms were written from the same concept by the same
person on the same afternoon. That cell's density measures the tagging convention, not the field.

The damage is worse than "one noisy cell", and the reason is worth stating because it is the reason
marking them is not optional: **the cell is uninformative when full *and* uninformative when
empty.** If `(reasoning-general/planning, planning)` were empty, that would tell you the subdomain
has no entries at all — it would be reporting on the row, not on the pair. A cell that can produce
no gap finding in either direction is not a cell, and leaving it in the grid unmarked means the
brightest square in the reasoning row sits on the diagonal. A specialist who clicks into the fine
grid, sees that, and concludes the matrix is an artefact of naming will be right about that square.

Now the size of it. There are exactly **four** such cells out of 8,976 in the fine grid (§6 confirms
the arithmetic), and **zero** in the coarse grid, because no domain *family* slug collides with any
capability slug — verified mechanically: `set(capability ids) & set(family ids)` is empty. The coarse
grid is the only grid permitted to produce published gap claims
([12-analytics-and-trends.md](../../12-analytics-and-trends.md) §5.1), and the fine grid is
exploration-only behind a null-model banner. So the collision cannot reach a published gap claim
today, and cannot reach one tomorrow unless the capability-group rollup — the vocabulary that does
not yet exist, see §7 — is built carelessly.

**Therefore: mark the four cells, do not rename the four terms.** Marking is four rows of YAML and
one renderer branch. Renaming costs the things enumerated in §5.2 and buys a number that is already
correct.

---

## 2. Why the identifier scheme is already right

This is the load-bearing observation, and it is verifiable in the corpus rather than inferred.

`taxonomy/domains.yaml` stores subdomain terms with **path ids and an explicit parent**
([03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) L299–301):

```yaml
  - id: robotics-embodiment/sim2real-transfer
    label: Sim-to-real transfer
    parent: robotics-embodiment
```

`taxonomy/capabilities.yaml` stores capability terms with **bare ids**
([03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) L216–217):

```yaml
  - id: long-horizon-execution
    label: Long-horizon execution
```

And entities reference them through **differently-named fields**
([04-data-model.md](../../04-data-model.md) L207–210):

```yaml
domain:
  primary: code/repository-scale-se
  secondary: [agents-tooluse/software-agents, code/bug-repair]
capability: [planning, long-horizon-execution, tool-use, context-integration]
```

So the two id sets today are `{planning, …}` and `{reasoning-general/planning, …}`. Their
intersection is empty. **There is no identifier collision anywhere in the repository, and there
never was.** What collides is a human reading of a word, in two places: a dropdown label, and an
unqualified term in prose or in a search box.

The consequence for D3.1 is direct. Prefixing every stored value to fix a collision that does not
exist in stored values would be a rewrite of every facet block in
[02-taxonomy.md](../../02-taxonomy.md) §12 (ten worked classifications), three entity examples in
[04-data-model.md](../../04-data-model.md), the stub template in
[05-repository-and-workflow.md](../../05-repository-and-workflow.md) §4, the generated issue-form
dropdowns, the Pydantic field types, and every hand-authored YAML file for the life of the project —
in exchange for encoding in the value what the schema already encodes in the key. Duplicated
encodings drift, and when they drift you get a `capability: [domain:planning]` that validates as a
string and fails silently at query time.

There is also a small ergonomic hazard worth naming, since curators hand-edit these files. In block
sequence form the prefixed value is one space away from changing type:

```yaml
capability:
  - capability:planning      # a string
  - capability: planning     # a single-key mapping; a typo, not an error the eye catches
```

Pydantic rejects the second loudly, so this is a nuisance rather than a corruption path — but it is
a nuisance imposed on the most-edited field in the corpus for no gain.

**What qualification is genuinely needed for** is the opposite case: a term appearing where no field
types it. That is the FQR in §3.4, and the fact that it is needed in six narrow places rather than
everywhere is the whole argument for D3.1.

---

## 3. Exact on-disk representation

### 3.1 Identifier grammar

| Vocabulary | Id form | Regex | Example |
| --- | --- | --- | --- |
| Domain family | bare slug | `^[a-z0-9]+(-[a-z0-9]+)*$` | `games-planning` |
| Domain subdomain | `{parent}/{leaf}`, both slugs | `^[a-z0-9]+(-[a-z0-9]+)*/[a-z0-9]+(-[a-z0-9]+)*$` | `games-planning/board-games` |
| Every other facet term | bare slug | `^[a-z0-9]+(-[a-z0-9]+)*$` | `planning`, `execution-tests` |
| Facet-qualified reference | `{facet}:{id}` | `^[a-z_]+:[a-z0-9/-]+$` | `domain:games-planning/board-games` |

`{facet}` is the value of the `facet:` key in the term's own taxonomy file header (`facet: capability`
at [03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) S4). One source of truth for
the prefix; check 9d asserts it rather than hard-coding a list.

`domain.primary` and every member of `domain.secondary[]` **must be two-level**. A bare family is a
navigational node, not an assignable value. This is implicit in
[02-taxonomy.md](../../02-taxonomy.md) §3 ("Two levels: `family/subdomain`") and in all thirteen
worked examples; D3 makes it a schema rule so it is enforced rather than observed.

### 3.2 `taxonomy/domains.yaml` — the two puzzle terms, after the rename

```yaml
facet: domain
facet_kind: navigational
terms:
  - id: reasoning-general/puzzle-solving
    label: Puzzle solving
    parent: reasoning-general
    status: active
    introduced_in: 1.0.0
    source: own
    definition: >
      Benchmarks that pose a self-contained combinatorial or logical problem with a checkable
      answer, where the whole task is submitted as one solution rather than played out against
      an environment.
    inclusion_test: >
      Tag as PRIMARY if the item is a stated problem with a verifiable solution and the system
      under test emits the solution, not a sequence of moves scored by an environment.
    exclusion_test: >
      Do NOT tag if the benchmark runs an interactive episode in which the environment responds
      to each action; that is `games-planning/puzzle-games`.
    examples:
      - ref: zebralogic
        qualifies: true
        why: Constraint-grid puzzles; one submitted answer, checked exactly.
      - ref: epoch-chess-puzzles
        qualifies: true
        why: >
          Find the forced mate. The position is given and the answer is a move sequence
          submitted whole; no engine replies.
      - ref: epoch-mystery-game-puzzles
        qualifies: false
        why: >
          NEAR MISS. Played out interactively against a game engine, so it is
          `games-planning/puzzle-games`.
    not_to_be_confused_with:
      - term: domain:games-planning/puzzle-games
        distinction: >
          The discriminant is the protocol, not the topic: a posed problem with a submitted
          answer here, an interactive episode there. This is the same discriminant that
          separates `robotics-embodiment/autonomous-driving-planning` from
          `vision/driving-perception-3d`.

  - id: games-planning/puzzle-games
    label: Puzzle games
    parent: games-planning
    status: active
    introduced_in: 1.0.0
    source: own
    definition: >
      Benchmarks in which a puzzle-genre game environment is played interactively and the score
      is the outcome of the episode.
    inclusion_test: >
      Tag as PRIMARY if the system under test issues actions into a running puzzle environment
      that responds, and the episode outcome is what is scored.
    exclusion_test: >
      Do NOT tag a statically-posed puzzle with a single submitted answer; that is
      `reasoning-general/puzzle-solving`.
    examples:
      - ref: epoch-mystery-game-puzzles
        qualifies: true
        why: Interactive investigation episode with persistent environment state.
      - ref: baba-is-ai
        qualifies: true
        why: Rule-manipulation puzzle game played move by move in a live environment.
      - ref: zebralogic
        qualifies: false
        why: >
          NEAR MISS. Puzzle genre, but no environment and no episode; it is
          `reasoning-general/puzzle-solving`.
    not_to_be_confused_with:
      - term: domain:reasoning-general/puzzle-solving
        distinction: >
          As above, from the other side. If removing the environment would leave the task
          intact, the task was never an episode.
```

### 3.3 `taxonomy/homographs.yaml` — new file, complete contents

```yaml
# taxonomy/homographs.yaml
# Declared collisions between a capability id and the leaf segment of a subdomain id.
# These are PERMITTED. The Capability facet is orthogonal to Domain by design and the same word
# is often the honest name on both axes. What is forbidden is an UNDECLARED one: an undeclared
# homograph is a coverage cell whose occupancy nobody has reasoned about.
# Enforced by CI checks 9d and 9e (05-repository-and-workflow.md section 9).
version: 1.0.0
updated: 2026-09-21
entries:
  - capability: capability:planning
    domain: domain:reasoning-general/planning
    relationship: same-concept-two-facets
    rationale: >
      The subdomain is the literature that studies plan construction as its subject (PlanBench,
      Blocksworld, travel-planning suites). The capability is the ability wherever it is
      exercised, which is why it is also tagged on Kaggle Game Arena, on robotics manipulation
      and on long-horizon agent benchmarks. Same word, two axes, both correct.

  - capability: capability:spatial-reasoning
    domain: domain:reasoning-general/spatial-reasoning
    relationship: same-concept-two-facets
    rationale: >
      The subdomain covers benchmarks whose stated subject is spatial reasoning presented
      textually or diagrammatically. The capability is carried by entries in
      vision/3d-reconstruction, robotics-embodiment/navigation and
      earth-climate/geospatial-reasoning, none of which belong in the reasoning-general row.

  - capability: capability:temporal-reasoning
    domain: domain:reasoning-general/temporal-reasoning
    relationship: same-concept-two-facets
    rationale: >
      Same shape as spatial-reasoning. The capability lands on
      audio-speech/audio-event-detection-localization, vision/video-understanding and
      medicine-health/ehr-prediction; the subdomain is the reasoning literature specifically.

  - capability: capability:compositional-generalization
    domain: domain:general-intelligence/compositional-generalization
    relationship: same-concept-two-facets
    rationale: >
      The subdomain is the SCAN/COGS-descended literature in which recombination of primitives
      is itself the object of study. The capability is defined in 02-taxonomy.md section 4 as
      "recombining known primitives in unseen configurations" and is tagged on Procgen and
      Craftax, which are games-planning/procedural-generalization entries.
```

`relationship` is an enum: `same-concept-two-facets | false-friend`. All four current entries are
the former. The enum exists so that the first genuine false friend — a shared word with unshared
meaning — is recorded as one and gets `not_to_be_confused_with` blocks on both terms, instead of
being waved through with a copy of a rationale that does not apply to it.

**One source of truth.** Neither `capabilities.yaml` nor `domains.yaml` carries a `homograph_of`
back-reference. The site's cross-links and the two terms' rendered "see also" entries are generated
from this file by the same pass that generates the term pages. A hand-maintained back-reference on
both sides is a thing that goes stale on one side.

### 3.4 Where the FQR is mandatory — and nowhere else

1. `see_also[]` and `not_to_be_confused_with[].term` **when the referent is in a different facet
   file**. Bare within the same file, FQR across files. (`see_also: [planning, memory-retention,
   autonomy]` inside `capabilities.yaml` stays exactly as it is at
   [03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) L252.)
2. `taxonomy/homographs.yaml`, in both `capability:` and `domain:` — shown above.
3. Coverage-cell identity in `build/derived/coverage.json`, in survey notes, and in any gap-finding
   record. **Two separate fields, never one concatenated key** — a concatenated key reintroduces
   exactly the parse ambiguity the FQR removes, and a subdomain id already contains a `/`.
4. The AI layer's structured facet-translation output
   ([11-ai-features.md](../../11-ai-features.md), the `facet_translation` golden split — 40 items,
   per-facet macro-F1 ≥ 0.85). This matters more than it looks: the four homographs are precisely
   the user queries on which the translator has a coin-flip, and an unqualified `planning` in its
   output cannot be scored against the gold label at all. The golden set must contain at least one
   item per homograph with the qualified gold answer.
5. `taxonomy/_failures/*.yaml` records of `kind: collision`, where the two colliding terms must be
   named qualified so triage can tell a within-facet defect from a cross-facet homograph.
6. Site routes. `/taxonomy/<facet>/<term>` already carries the facet
   ([03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) L339), so the URL *is* an FQR
   with `/` for `:` — but note the routing consequence: a subdomain term contains a slash, so the
   route must be declared as `/taxonomy/domain/[family]/[subdomain]` explicitly or Astro will 404 on
   every subdomain term page.

Everywhere else — `domain.primary`, `domain.secondary[]`, `capability[]`, `evaluation_method[]`,
every facet-typed field in `data/`, every issue-form dropdown value — the value is **bare**, in the
form given in §3.1. An FQR inside a facet-typed field is a Tier-1 schema failure, not a stylistic
warning, because a tolerated second spelling becomes a second spelling in the corpus within a month.

### 3.5 An entity as stored — no change from today

The specimen is [02-taxonomy.md](../../02-taxonomy.md) §12.5, the only worked example that carries
the collision in both fields at once and therefore the best test of D3.1:

```yaml
id: kaggle-game-arena-chess
name: Kaggle Game Arena — Chess
domain:
  primary: games-planning/board-games
  secondary: [reasoning-general/planning]     # subdomain id: family-qualified
capability: [planning, search-exploration, constraint-satisfaction, long-horizon-execution]
                                              # capability ids: bare
```

This record is correct as written and stays as written. It asserts two different true things: a
chess specialist browsing the spine would expect to find this filed under planning, *and* the
ability the benchmark isolates includes planning. It also lands on the tautological cell
`(reasoning-general/planning, planning)` in the fine grid, which is why 9e exists.

### 3.6 Survey notes — the missing file that D3 forces into existence

[02-taxonomy.md](../../02-taxonomy.md) §11 rule 6 makes `surveyed-and-empty` conditional on "a dated
survey note for that (domain, capability) pair", and no such entity appears in the repository layout
at [05-repository-and-workflow.md](../../05-repository-and-workflow.md) §2. D3 does not own that
entity, but it owns how the pair is keyed, so the shape is pinned here and handed on:

```yaml
# data/surveys/reasoning-general/planning.yaml   — one file per SUBDOMAIN, not per cell
domain: domain:reasoning-general/planning
surveys:
  - capability: capability:spatial-reasoning
    surveyed_on: 2026-11-02
    curator: "@curator-a"
    result: empty                 # empty | found-and-entered | inconclusive
    method: >
      Searched the 2026 planning survey's reference list, the Epoch corpus and
      grand-challenge.org; no benchmark poses spatial constraints inside a plan-construction
      task.
    source: src-...
```

One file per subdomain rather than per cell keeps the count at 204 files instead of 8,976 and makes
"survey this row" a single-file task, which is the unit a curator actually works in. The pair is
keyed by two FQR fields, per §3.4 item 3.

---

## 4. The CI rows, ready to paste

Replace rows 9a and 9c in the `pr-validate.yml` table of
[05-repository-and-workflow.md](../../05-repository-and-workflow.md) §9 (L707 and L709), and insert
9d and 9e after 9c. Column order and style match the surrounding table exactly.

```
| 9a | **Forbidden-identifier grep** | Yes | `taxonomy/forbidden-identifiers.yaml` lists renamed field names that must never reappear. The scanned set is an explicit **allowlist of paths** -- `data/`, `taxonomy/`, `src/`, `scripts/` -- minus `taxonomy/forbidden-identifiers.yaml` and `taxonomy/retired-ids.yaml`, which list dead identifiers by construction and which a naive grep over `taxonomy/` fails against. `docs/`, `adr/`, `CHANGELOG.md` and `_plan/` are never scanned, and that is a declared exemption rather than an omission: a rename must stay explainable, and the explanation has to name the old identifier. First entry: `human_baseline_type`, renamed to `ceiling_anchor_type` on 2026-09-21 ([02-taxonomy.md](02-taxonomy.md) §7) |
| 9c | **Vocabulary id uniqueness** | Yes | Within each `taxonomy/*.yaml`: `id` is unique across `terms[]` **including `deprecated` and `retired` terms**. In `domains.yaml`: every term with a `parent` satisfies `id == f"{parent}/{leaf}"`, every term without one is a family, and **`leaf` is unique across the whole file, not merely within its parent** -- a leaf under two families renders two dropdown options with the same label and splits one coverage row into two thin ones. Across files, the facet-qualified id `{facet}:{id}` is unique by construction; assert it rather than assume it. All ids match the grammar in [04-data-model.md](04-data-model.md) §2 |
| 9d | **Homograph declaration** | Yes | A *homograph* is a capability `id` equal to the leaf segment of a subdomain `id` -- today `planning`, `spatial-reasoning`, `temporal-reasoning`, `compositional-generalization`. These are permitted: the Capability facet is orthogonal to Domain by design and the same word is the honest name on both axes. **Undeclared ones are not.** Every computed homograph must appear in `taxonomy/homographs.yaml` with `capability`, `domain`, `relationship` (`same-concept-two-facets` \| `false-friend`) and a one-sentence `rationale`; and every declared entry must still compute, because an allowlist that outlives its entries rots into blanket permission to collide. A `false-friend` entry additionally requires a `not_to_be_confused_with` block on both terms |
| 9e | **Tautological coverage cells** | Yes | For each `same-concept-two-facets` homograph, the fine-grid cell (subdomain `F/X`, capability `X`) is occupied by construction and yields no gap finding in either direction -- full reports the tagging convention, empty reports that the row is empty. `bench build --derived` must emit `degenerate: tautological-homograph` on exactly those cells in `build/derived/coverage.json`; the fine-grid renderer hatches them and excludes them from gap ranking and from both the numerator and the denominator of every coverage percentage ([10-visualization.md](10-visualization.md) §"Three cell states"). Assert the flagged set equals the `same-concept-two-facets` declarations -- currently 4 cells of 8,976 |
```

Satisfiability, stated so the executing agent can check it rather than trust it:

- **9c passes** the moment the D3.5 rename lands. Before it, it fails on exactly one leaf
  (`puzzle-solving`), which is the point.
- **9d passes today**, once `taxonomy/homographs.yaml` exists with the four entries in §3.3.
- **9e passes** once the build emits the flag. It is the only row that needs code rather than data,
  and it is roughly one predicate in the derived-coverage pass.

---

## 5. Reasoning, and the alternatives rejected

### 5.1 Rejected: full qualification of stored values (`capability:planning` in `data/`)

The cost is §2: every facet block in five documents, every generated dropdown, every Pydantic field
type, and every hand-authored YAML file forever. The benefit is zero, because the field name already
types the value and no ambiguity exists in stored form. It would also make the most-edited field in
the corpus longer and noisier — `capability: [capability:planning, capability:tool-use]` — on a
project whose stated long pole is curation throughput, not engineering. Rejected on cost with no
offsetting benefit; the narrow real need is met by the FQR at a fraction of the price.

### 5.2 Rejected: renaming the four capability terms to force disjointness

This is the option the brief asks to be weighed explicitly, so here is what it costs and what it
buys.

It invalidates: the count of **44** in [02-taxonomy.md](../../02-taxonomy.md) §4 and §14 and
everywhere check 9b regenerates it; the `compositional-generalization` disambiguation note in §4,
which is one of the five notes that exist precisely because those terms blur; the
`not_to_be_confused_with: planning` block on `long-horizon-execution`
([03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) L252–257), which is the single
highest-value line in that file by the document's own argument; `capability: [planning, …]` in the
Kaggle Game Arena and ARC-AGI-3 worked examples ([02-taxonomy.md](../../02-taxonomy.md) §12.5,
§12.7); `capability: [planning, …]` at [04-data-model.md](../../04-data-model.md) L210; and the
capability changelog's "Net: 40 → 44 terms" line.

What it buys is a renamed column header. And it would have to be renamed *to* something, which is
where the option dies: the alternatives to `planning` are `plan-construction` or `plan-synthesis`,
both narrower than the concept and both reading as jargon invented to satisfy a machine. **The
capability terms are the coverage matrix's column headers, read by non-specialists on a public page.
Renaming one for a mechanical reason degrades exactly the legibility the facet exists for.**

Renaming the *subdomains* instead is worse: `reasoning-general/planning` is the label a specialist
expects in the browse spine, and the spine is the navigational contract.

The deeper reason is D3.4's governing principle. These are not accidental collisions of unrelated
concepts; they are one concept correctly named on two orthogonal axes. A faceted classification that
forbids that has stopped being faceted. **The identifier space must accommodate the classification,
not the reverse.**

### 5.3 Rejected: within-vocabulary uniqueness only, with no cross-vocabulary check at all

Tempting, and §2 argues it is technically sufficient. Rejected because it loses the one thing the
broken 9c was reaching for. Left unchecked, the *fifth* homograph arrives silently: someone proposes
a capability that happens to match a subdomain leaf, or splits a subdomain into a slug that matches
a capability, and nobody notices until a reviewer finds a bright diagonal cell in their own field.
9d costs one YAML file and one set intersection, and it converts an invisible event into a PR
conversation with a rationale attached. That conversation is the deliverable; the assertion is only
the trigger.

### 5.4 Rejected for `puzzle-solving`: allowing one leaf under two families

This is genuinely arguable and it nearly won. The ids are already family-qualified, so
`reasoning-general/puzzle-solving` and `games-planning/puzzle-solving` do not collide as
identifiers; 9c could be scoped per-parent and both would stand. Three things sank it.

**One: a within-facet duplication is a different animal from a cross-facet homograph.** The
homographs are disambiguated by the field they appear in. Two identically-labelled options in the
*same* dropdown are disambiguated by nothing a curator will read. Issue-form dropdowns are generated
from `taxonomy/domains.yaml` ([05-repository-and-workflow.md](../../05-repository-and-workflow.md)
§6), so a drive-by contributor would see "Puzzle solving" twice with no visible discriminant — and
inter-rater reliability on primary domain is a blocking freeze gate at ≥ 0.85 raw agreement
([03-taxonomy-build-process.md](../../03-taxonomy-build-process.md) §6.2). A duplicated label is a
manufactured disagreement in the one facet where disagreement blocks the freeze.

**Two: it splits one coverage row into two thin ones, which is the failure mode this project has
already named and already fixed once.** The capability changelog merged `ood-generalization` and
`distribution-shift-robustness` for exactly this reason: "Two terms for one idea splits the evidence
for a cell across two columns and makes both look thinner than reality." Half the puzzle benchmarks
landing in each family makes both rows understate, and understated rows are false gaps — the exact
output differentiator 3 sells.

**Three: it contradicts 02's own arithmetic.** [02-taxonomy.md](../../02-taxonomy.md) L240 and L1382
both state a subdomain count as a count of *distinct* terms. The document does not believe it has a
multi-parented subdomain; it believes every subdomain is distinct. The duplication is a drafting
slip, not a design.

**And the house precedent is unanimous.** Every other near-collision in the domain vocabulary was
resolved by *differentiating the name*, never by duplicating one: `vision/medical-imaging-cv` beside
`medicine-health/medical-imaging-diagnostic`; `chemistry-materials/lab-automation-protocols` beside
`engineering-design/lab-automation-execution`; `robotics-embodiment/autonomous-driving-planning`
beside `vision/driving-perception-3d`. D3.5 applies the same move.

**Why `games-planning` renames, and what happens to the benchmark a curator would file under the
other one.** The reasoning-general term matches the plain reading of "puzzle solving" — a posed
problem with a checkable answer — and it sits among nine other terms naming kinds of reasoning. The
games-planning list names game *genres* (`board-games`, `card-imperfect-information`, `video-games`,
`real-time-strategy`), so `puzzle-games` is the term that fits its siblings and reads correctly in a
dropdown beside them. The discriminant published on both terms (§3.2) is the **protocol**, not the
topic: posed problem with a submitted answer → `reasoning-general/puzzle-solving`; interactive
episode against a responding environment → `games-planning/puzzle-games`. That is the same
discriminant that already separates driving-as-control from driving-as-perception, so a curator has
met it before.

Both homes stay populated, which is why this is a rename and not a deletion — the Epoch corpus alone
supplies one clear instance of each (`chess_puzzles` is a posed problem, `mystery_game_puzzles` is an
episode; [13-execution-runners.md](../../13-execution-runners.md) L176). A curator who reaches for
the wrong term hits an exclusion test that names the other one explicitly. A benchmark that is
genuinely both — a puzzle game whose scored output is a single submitted solution — takes the
interactive home as primary and the other as a secondary domain, which is what the secondary field
is for. Risk accepted: `puzzle-games` is a slightly less obvious search term than `puzzle-solving`,
so both labels must appear in the site's synonym list for search, and the rename must land before
any entry is written against the old slug (edit 36).

### 5.5 Rejected: treating the tautological cells as `not-applicable`

[10-visualization.md](../../10-visualization.md) already has a `not-applicable` cell state for pairs
the taxonomy marks as incoherent (`speech-synthesis` × `formal-proof-check`). Reusing it would be
cheap and would be wrong in a way that shows. Not-applicable renders as a neutral blank meaning "the
question does not make sense"; a tautological cell is the opposite — the question makes perfect sense
and is guaranteed answered yes. Rendering a guaranteed-full cell as a neutral blank would read as a
*gap*, which is the single worst mistake available in the gap view. The two share an exclusion rule
(out of gap ranking, out of both sides of every coverage percentage) and need different marks:
hatched-full, not neutral-blank.

---

## 6. Counts affected, verified mechanically on 2026-09-21

Counted by script over [02-taxonomy.md](../../02-taxonomy.md) L134–237. These override the briefing
figures where they differ.

- **Subdomain listings: 204**, not 205. The briefing's per-family counts (G2) sum to 204 and are
  individually correct; G2's headline "205 listings / 204 distinct" is off by one on both. Verified
  per family: language 11, mathematics 7, code 9, reasoning-general 10, vision 16, audio-speech 10,
  multimodal 7, robotics-embodiment 15, physics 10, chemistry-materials 12, biology-genetics 18,
  medicine-health 12, earth-climate 8, games-planning 9, agents-tooluse 10, safety-alignment 16,
  general-intelligence 7, society-econ-law 11, engineering-design 6.
- **Distinct leaves before D3.5: 203. After D3.5: 204.** Listings stay at 204, because the term is
  renamed, not removed. Per-family counts are unchanged, so no curation-target arithmetic moves.
- **Capability terms: 44 distinct, with no duplicate in the enumeration.** G3's "45 listings" counts
  the prose mention of `causal-reasoning` in §4's opening sentence ("Orthogonal to Domain —
  `causal-reasoning` appears in chemistry, economics and medicine"), which is an example, not a
  listing. **No edit is needed to the capability list.**
- **Fine grid: 204 × 44 = 8,976 cells**, before and after D3.5, because rows are subdomain *ids* and
  the number of ids does not change. G4's product is right; the 205 that fed it was not.
- **Homographs: 4.** Verified: `set(capability) & set(subdomain leaves)` =
  `{planning, spatial-reasoning, temporal-reasoning, compositional-generalization}`;
  `set(capability) & set(family ids)` = `{}`; and capability intersects none of `evaluation_method`
  (27 terms), `designed_for_subjects` (18) or the 131 terms of facets 5–8, and none of those
  intersect the subdomain leaves either. **The homograph problem is confined to exactly one
  vocabulary pair**, which is what makes a four-entry allowlist a proportionate response rather than
  the first step of an unbounded one.

---

## 7. Interactions with other open decisions — do not resolve these here

- **The capability-group vocabulary does not exist** (briefing G5). When it is written it becomes a
  *third* vocabulary and 9d must be extended to cover group ids against both capability ids and
  subdomain leaves. Flag it now: a group called `planning` would put a tautological cell in the
  **coarse** grid, which unlike the fine grid *does* publish gap claims, and that is the one version
  of this problem that damages the product. Recommendation to whoever owns that decision: **no
  capability-group id may equal any capability id or any subdomain leaf**, enforced by extending 9d,
  and group ids should be phrase-form (`planning-and-search`) so that accidental equality is unlikely
  rather than merely forbidden.
- **`Total controlled terms: 446`** at [02-taxonomy.md](../../02-taxonomy.md) L1402 does not add up:
  the §14 table's own rows sum to 436 today and 435 after D3.5. D3 does not edit it, because check 9b
  makes every count in §14 generated rather than typed, and the right fix is to mark it generated,
  not to retype a wrong number. Handed to the counts owner.
- **Seed-target and family-floor arithmetic** (G6, G7) is untouched by D3.
- **`data/surveys/` does not exist** although §11 rule 6 depends on it. Shape pinned in §3.6; the
  entity itself belongs to the data-model owner.
- **Stale "18 families"** (G1) appears at [14-roadmap.md](../../14-roadmap.md) L1359, inside a
  first-week instruction that D3 edits anyway, so edit 35 fixes that one instance only. The rest of
  the sweep belongs to whoever owns G1.

---

## EDITS REQUIRED, BY FILE AND LINE

Line numbers are as of 2026-09-21. Where an edit inserts lines, later numbers in the same file
shift; execute per file from the bottom up, or re-locate by the quoted anchor text.

### `02-taxonomy.md`

1. **L210** — in the `games-planning` subdomain list, change the term `` `puzzle-solving` `` to
   `` `puzzle-games` ``. The line currently reads:
   `` `puzzle-solving` · `open-ended-environments` · `procedural-generalization` · `game-theory` · ``
   **Do not touch L156**, the `reasoning-general` list, which keeps `puzzle-solving`.

2. **L240** — `Nineteen families, 205 subdomains.` → `Nineteen families, 204 subdomains.`
   (Verified: 204 listings, and 204 distinct once edit 1 lands.)

3. **After L266** — append one row to the Domain changelog table, immediately after the
   ``| **Rejected: a `robot-competition` subdomain** | …`` row:

   ```
   | **`games-planning/puzzle-solving` → `games-planning/puzzle-games`** | The slug appeared under both `reasoning-general` and `games-planning`, which generates two identically-labelled options in the same generated dropdown and splits one coverage row into two thin ones -- the failure the capability facet already fixed by merging `ood-generalization` and `distribution-shift-robustness`. The discriminant is the protocol, not the topic: a posed problem with a submitted answer is `reasoning-general/puzzle-solving`; an interactive episode against a responding environment is `games-planning/puzzle-games`. Both homes stay populated -- Epoch's `chess_puzzles` and `mystery_game_puzzles` are one of each. See `_workflow/decisions/D3-vocabulary-namespacing.md`. |
   ```

4. **L325** — `taxonomy/capability.yaml` → `taxonomy/capabilities.yaml`. Every other document uses
   the plural; this is the only singular, and it is the filename a CI check will open.

5. **After L322, immediately before the `### Disambiguation notes for the terms most likely to blur`
   heading on L323** — insert this paragraph:

   > **Four capability terms share a word with a subdomain leaf**: `planning`, `spatial-reasoning`,
   > `temporal-reasoning` and `compositional-generalization`. This is permitted and expected — the
   > facet is orthogonal to Domain, so the same concept is correctly named on both axes — but each
   > pair is declared in `taxonomy/homographs.yaml` with a rationale, and CI check 9d fails on an
   > undeclared one. The consequence for the coverage matrix is that the four fine-grid cells whose
   > row and column carry the same word are occupied by construction: full reports the tagging
   > convention, empty reports that the row is empty, and neither can produce a gap finding. Check
   > 9e marks them and the fine-grid view excludes them from gap ranking. Four cells of 8,976, and
   > none at all in the coarse grid, which is the only grid that publishes gap claims.

6. **After L853** (the end of §11 rule 10, `…they are not part of the vocabulary.`) — insert a new
   cross-cutting rule 11:

   > 11. **Identifiers are facet-scoped, not globally unique.** A subdomain id is always
   >     `family/subdomain`, and a subdomain leaf is unique across the whole domain vocabulary, not
   >     merely within its family. Every other facet's ids are bare slugs, unique within their facet
   >     file. Two facets may share a word — the field name says which vocabulary a value belongs to
   >     — but every such pair is declared in `taxonomy/homographs.yaml` with a rationale, and the
   >     coverage cell where the two meet is marked as occupied-by-construction rather than counted
   >     as evidence. Where a term is referenced *outside* a facet-typed field, it is written
   >     facet-qualified: `capability:planning`, `domain:reasoning-general/planning`. Enforced by CI
   >     checks 9c–9e in [05-repository-and-workflow.md](05-repository-and-workflow.md) §9.

7. **L1382** — the §14 Domain row: `19 families / 205 subdomains` → `19 families / 204 subdomains`.

8. **L1402** — do **not** retype `Total controlled terms: 446`. The §14 table is regenerated by
   check 9b; mark the total generated and hand the arithmetic (436 today, 435 after these edits) to
   the counts owner. Retyping a wrong total is how it stayed wrong.

### `03-taxonomy-build-process.md`

9. **After L180** (`…is batched into the Stage 4 revision.`) — append one sentence:

   > A `collision` record whose two terms sit in *different* facet files is not a defect. It is a
   > homograph candidate, and it routes to `taxonomy/homographs.yaml` for a declaration and a
   > rationale, not to an ADR for a rename.

   The `kind:` enum on L166 already contains `collision`; leave it alone.

10. **L297–298** — the lead-in to the `taxonomy/domains.yaml` excerpt currently reads `Domain terms
    carry two extra fields because the domain facet is the navigational spine and has two levels:`.
    Replace with:

    > Domain terms carry two extra fields because the domain facet is the navigational spine and has
    > two levels. **The id form below is normative, not illustrative:** a subdomain id is always
    > `{parent}/{leaf}`, the leaf is unique across the entire file, and a bare family id is a
    > navigational node that is never assignable to `domain.primary`. CI check 9c asserts all three.

11. **L336–339** — "Two supporting files complete the directory" becomes **three**; insert between
    the `retired-ids.yaml` and `VERSION` bullets:

    > - `taxonomy/homographs.yaml` — declared collisions between a capability id and a subdomain
    >   leaf. Permitted, but each carries a rationale, and CI checks 9d and 9e enforce both the
    >   declaration and the coverage-cell consequence. See
    >   `_workflow/decisions/D3-vocabulary-namespacing.md`.

12. **After L556** — add a row to the §8.1 change-type table, immediately after
    `| **Rename a label** (ID unchanged) | PATCH | No | 1 | No |`:

    ```
    | **Rename a term *id*** | Before the v1.0.0 freeze: PATCH, no ledger entry. After: this is a **Retire + Add** -- MAJOR, old id appended to `retired-ids.yaml`, corpus migration required | Required after the freeze | 2 | Yes, that facet, after the freeze |
    ```

    This row is why D3.5 is free today and would not be next year, and its absence is why the table
    currently appears to say that ids can never be renamed at all.

### `04-data-model.md`

13. **After L112** (the `- **Format**: lowercase kebab slug…` bullet) — extend the id-format list:

    > - **Domain ids are two-level**: `{family}/{subdomain}`, both lowercase kebab slugs
    >   (`code/repository-scale-se`). A bare family is a navigational node and is **not** assignable
    >   to `domain.primary` or `domain.secondary[]`. Every other facet term is a bare slug.
    > - **Facet-qualified reference**: `{facet}:{id}` — `capability:planning`,
    >   `domain:reasoning-general/planning`. Used **only** where a term appears outside a
    >   facet-typed field: cross-facet `see_also`, `taxonomy/homographs.yaml`, coverage-cell and
    >   survey-note keys, and the AI layer's facet-translation output. A qualified value inside a
    >   facet-typed field is a Tier-1 failure.

14. **L374** — `domain_override: {primary: chemistry/molecular-property-prediction}` →
    `chemistry-materials/molecular-property-prediction`. The family `chemistry` was renamed to
    `chemistry-materials` in [02-taxonomy.md](02-taxonomy.md) §3 and no longer resolves.

15. **L1182** — `primary: chemistry/generative-molecular-design` →
    `chemistry-materials/generative-molecular-design`.

16. **L1183** — in `secondary: [biology-genetics/drug-target-interaction,
    chemistry/molecular-property-prediction]`, change the second element to
    `chemistry-materials/molecular-property-prediction`.

17. **L1184** — in `capability: [search-exploration, optimization, generation-fidelity,
    ood-generalization]`, replace `ood-generalization` with `distribution-shift-generalization`. That
    term was merged away by [02-taxonomy.md](02-taxonomy.md) §4's capability changelog and no longer
    resolves. Not a D3 ruling, but it is an unresolvable id in a worked example and edit 19 makes it
    a CI failure.

18. **L633** — the exemption claim is *consistent* with how 05 words check 9a, but only by omission:
    05 lists four scanned paths and `_plan/` is simply not among them. Omission is a fragile way to
    carry a policy, because the obvious hardening instinct is to widen the grep. Replace:

    > `human_baseline_type` is a **forbidden identifier**: CI greps `data/`, `taxonomy/`, `src/` and
    > `scripts/` for it and fails on any occurrence. The plan documents are exempt, because they
    > have to be able to name the old term when explaining the rename.

    with:

    > `human_baseline_type` is a **forbidden identifier**: CI greps an explicit allowlist of paths —
    > `data/`, `taxonomy/`, `src/`, `scripts/` — and fails on any occurrence. The exclusions are
    > declared rather than accidental. `docs/`, `adr/`, `CHANGELOG.md` and the `_plan/` documents are
    > never scanned, because a rename has to stay explainable and the explanation has to name the old
    > identifier. `taxonomy/forbidden-identifiers.yaml` and `taxonomy/retired-ids.yaml` are excluded
    > from the scan of `taxonomy/` for the same reason: listing dead identifiers is their job, and a
    > naive grep over `taxonomy/` fails against the check's own configuration file. See check 9a in
    > [05-repository-and-workflow.md](05-repository-and-workflow.md) §9.

19. **L1107** (validation-tier table, Tier 2 Referential row) — add to the Examples cell:

    > every `domain.primary` and `domain.secondary[]` value resolves to a `taxonomy/domains.yaml`
    > term that *has* a `parent` (families are navigational, not assignable); every `capability[]`
    > value resolves to a bare id in `taxonomy/capabilities.yaml`

### `05-repository-and-workflow.md`

20. **L707** — replace the 9a row verbatim with the 9a row given in §4 above. This fixes two live
    defects: the check currently scans its own configuration file, and its exemption for
    prose-bearing paths exists only by omission.

21. **L709** — replace the 9c row verbatim with the 9c row given in §4 above, and insert the 9d and
    9e rows immediately after it.

22. **L111–121** (the `taxonomy/` tree) — three files and one directory referenced elsewhere in the
    corpus are missing from the layout. Add, keeping `crosswalks/` last so the box-drawing corner
    stays correct:

    ```
    │   ├── homographs.yaml            # Declared capability↔subdomain word collisions; CI 9d/9e
    │   ├── forbidden-identifiers.yaml # Renamed field names that must never reappear; CI 9a
    │   ├── VERSION                    # Aggregate semver, stamped into every build artifact
    │   ├── _failures/                 # Structured classification-failure log (03 §3.3)
    ```

    `forbidden-identifiers.yaml` is named by check 9a on L707 but has never appeared in the tree;
    `VERSION` and `_failures/` are specified in
    [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §4.

23. **After L127** (inside the `data/` tree) — add the survey entity whose absence blocks
    [02-taxonomy.md](02-taxonomy.md) §11 rule 6:

    ```
    │   ├── surveys/<domain-family>/<subdomain>.yaml
    │   │                                   # Dated per-capability survey notes: the only thing that
    │   │                                   # lets a coverage cell read `surveyed-and-empty`
    ```

24. **L319** — `primary: robotics/manipulation   # Exactly one. From taxonomy/domains.yaml…` →
    `primary: robotics-embodiment/manipulation`, comment unchanged. `robotics` is not a family;
    [02-taxonomy.md](02-taxonomy.md) §3 names it `robotics-embodiment`.

25. **In the "File naming and identity conventions" table, the `Domain family dir` row (~L230)** —
    the example reads `data/benchmarks/robotics/`; change to `data/benchmarks/robotics-embodiment/`.
    Same error as edit 24.

### `10-visualization.md`

26. **L234–235** — replace:

    > The taxonomy has eighteen domain families containing roughly 174 subdomains, and about forty
    > capability terms. The full subdomain x capability matrix is therefore around **6,960 cells**.

    with:

    > The taxonomy has nineteen domain families containing 204 subdomains, and 44 capability terms.
    > The full subdomain x capability matrix is therefore **8,976 cells**.

    Then recheck the two sentences that follow: the ~6,000-incidence estimate is unchanged, so mean
    density falls further below one and "~90% empty" becomes ~93%. Update the percentage or cut it;
    do not leave old arithmetic attached to a new denominator.

27. **L238** — `expands it to that family's subdomains x the full forty capability terms` → `44
    capability terms`.

28. **L241** — `**The default view is therefore 18 domain families x ~8 capability groups (144
    cells)**`. The family count is wrong (19) and the group count contradicts
    [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1's twelve. **D3 does not decide the
    group count.** Fix `18` → `19`, and either leave the group figure to the capability-group
    decision or mark it inline as pending it. Same treatment for L1108–1109 in the open-questions
    list.

29. **In the "Three cell states, not two" table (~L252–256)** — add a fourth row, and note in the
    surrounding prose that it is an annotation on a cell rather than a fourth state:

    ```
    | **Tautological** | Row and column carry the same word, because a capability shares a slug with this subdomain's leaf (declared in `taxonomy/homographs.yaml`). Occupied by construction: full reports the tagging convention, empty reports that the row is empty | Hatched fill at full density, labelled on hover, excluded from gap ranking and from both sides of every coverage percentage. Distinct from **Not applicable**, which renders neutral-blank because the question is incoherent -- here the question is coherent and the answer is guaranteed |
    ```

    Add after the table: *Four cells at present, all in the fine grid, none in the coarse grid. CI
    check 9e asserts that the flagged set matches the declarations in `taxonomy/homographs.yaml`.*

### `12-analytics-and-trends.md`

30. **L291–292** — `19 domain families containing 198 subdomains, and 44 capability terms. The naive
    matrix is therefore **8,712 cells**` → `204 subdomains` and `**8,976 cells**`. Recheck the "at
    least 87% of that matrix is empty by arithmetic" sentence immediately below against the new
    denominator.

31. **L309** — the fine-grid table row: `198 subdomains x 44 capability terms | 8,712` →
    `204 subdomains x 44 capability terms | 8,976`. Mean occupancy (~900 / 8,976 ≈ 0.10) is unchanged
    at two decimals.

32. **L864–865** — `The coarse grid has 228 cells and the fine grid roughly 6,960` → `8,976`, and add
    the exclusion: *minus the four tautological cells declared in `taxonomy/homographs.yaml`, which
    leave the family before any multiple-comparisons correction is applied — a cell occupied by
    construction inflates the family size without contributing a testable hypothesis.*

33. **L311** — the citation to `02-taxonomy.md §4.3` for the capability-group enumeration points at a
    section that does not exist. **Not a D3 edit.** Flagged here only because 9d must be extended to
    the group vocabulary once it is written (§7). Hand to the capability-group decision.

### `11-ai-features.md`

34. **At the `facet_translation` golden-split row (L805)** — add, in the row or in the adjacent
    paragraph: the translator's structured output uses facet-qualified references
    (`capability:planning`, `domain:reasoning-general/planning`), and the 40-item golden split must
    contain at least one item per declared homograph with the qualified gold answer. An unqualified
    `planning` in the model's output cannot be scored against the gold label at all, and those four
    words are exactly the queries on which the translator has a coin-flip.

### `14-roadmap.md`

35. **L1359** — `all 18 families` → `all 19 families`.

36. **L1359–1361, first-week item 1** — add `taxonomy/homographs.yaml` to the deliverable, and note
    that the `puzzle-games` rename must land in `domains.yaml` on the first write rather than as a
    later correction. The file is four entries and it must exist before the first `capability[]`
    value is written, because 9d fails closed and the first PR carrying a capability tag will trip
    it otherwise.

### New repository file (not a plan document)

37. **Create `taxonomy/homographs.yaml`** with the contents given verbatim in §3.3 above. Listed here
    so that edits 11, 22 and 36 have something real to point at.
