# 15 -- Open Questions

This is the decisions register. It exists so that no decision in this plan is made twice, and so
that no decision is made silently.

Every question below carries four parts:

1. **The question**, stated so it has an answer rather than a discussion.
2. **Why it matters** — what breaks, or what gets more expensive, if it is decided badly or late.
3. **A recommendation**, so that work proceeds today without waiting for a meeting. Nothing here is
   a blocker. A question with a recommendation is a default, not a stop.
4. **If overturned** — which documents change. A decision whose blast radius is unknown is a
   decision nobody will dare revisit, and a plan full of those calcifies within a month.

Questions are grouped by *when the decision is needed*, not by topic. Topic grouping produces a
register that is pleasant to read and impossible to act on; date grouping produces a queue. That
grouping is only true if it is enforced, so three questions that previously sat in the
longer-horizon section against Phase-0 and Phase-1 deadlines have been moved into the sections their
deadlines name, and every row in the index now carries the date its recommendation last changed and
the **trigger** that should cause it to be looked at again. A register with no per-row date is how
four of this plan's numbers drifted apart across six documents before anyone noticed.

**Two labelling notes, because they matter for reading.** First, the AI-phase questions are labelled
`AI1`–`AI4`, not `D1`–`D4`: `D1`–`D4` now name the four adjudicated decisions of 2026-09-21
(`_workflow/decisions/`), and a register whose own labels collide with the decision set it must not
relitigate is a trap. Second, one document owns each fact. Where a number belongs to another
document, this register states it once with the owner named, or links instead of restating. Every
drift this plan has suffered came from a second copy of a number in somebody else's prose.

The failure mode this document is written against is the one that kills planning documents
generally: a list of concerns with no defaults, which quietly becomes a list of excuses for not
starting. Each recommendation below is live and should be treated as the current decision until
someone writes down a better one.

**On ADRs, corrected.** An earlier revision of this file promised an ADR in `adr/` for every
answered decision. Twenty-six ADRs is real work nobody has costed, and writing them would come out
of the curation budget that is already the binding constraint
([14-roadmap.md](14-roadmap.md) effort table). **This table is the record until public v1.** ADRs
start only for decisions *overturned* after the first DOI'd release — at that point an ADR is
earning its keep, because the thing it documents is a change to a citable artifact rather than a
restatement of a plan nobody has acted on yet. The four adjudicated decisions in
`_workflow/decisions/` are the template for what an ADR should look like when the time comes.

---

## Index

`Decided` is the date the recommendation last changed. `Next review` is a **trigger**, not a date,
because a date nobody owns is a date nobody honours.

**Not every row here is equally open, and reading them as though they were is how this register gets
too long to finish.** Most carry a recommendation, a trigger and a blast radius, and are therefore
*decisions with a review condition* rather than live arguments — A4, A5, A6, A8, C3, C4, C6 and the
whole of section F are in that state, and the right way to read them is "settled, here is what would
reopen it". The genuinely unresolved ones, where a reasonable person could still choose differently
today and the plan would change materially, are **A1, A2, A10, A11, A12, B1, B4, B6, C5, C7, AI2 and
AI4**. If you are reading this register to decide something, read those twelve. If you are reading it
to check that something was decided, use the table.

| # | Question | Needed by | Decided | Next review (trigger) | Recommendation in one line |
| --- | --- | --- | --- | --- | --- |
| A1 | Separate project, or contribute to an existing one? | Phase 0 | 2026-09-21 | EvalEval ships a benchmark-entity schema | Separate, with a written interop contract with Every Eval Ever |
| A2 | Public from commit one, or curate privately first? | Phase 0 | 2026-09-21 | Phase 1 exit bar met | Repo public from commit one; site gated until the Phase 1 exit bar in `14` |
| A3 | What counts as an "AI benchmark"? | Phase 0 | 2026-09-21 | A curator hits three undecidable cases in one week | The learned-entrant test, with evidence recorded per entry |
| A4 | Data and code licensing | Phase 0 | 2026-09-17 | A competitor relicenses (see E5) | CC-BY-4.0 for data and taxonomy, MIT for tools and site |
| A5 | The Papers with Code CC-BY-SA firewall | Before first ingest | 2026-09-21 | Legal review, or a PwC relicence | Quarantine in `vendor/pwc-archive/`, reconciliation key only, CI-enforced |
| A6 | Name, domain, identifier permanence, DOI | Phase 0 | 2026-09-21 | Availability check fails on the chosen set | Evalmap, pending a four-surface availability check; slug IDs plus aliases; concept DOI at v0.1 |
| A7 | How far to adopt Every Eval Ever's schema | Phase 0 | 2026-09-21 | EEE ships a breaking schema change | Adopt their field names verbatim; do not embed their schema |
| A8 | A Croissant benchmark extension? | Phase 0 design, post-v1 proposal | 2026-09-21 | Public v1 ships | Build the mapping now; propose after public v1, not at 500 entries |
| A9 | What we owe when an upstream source sunsets | Before the first adapter | 2026-09-21 | Any Tier-1 source announces a sunset | Freeze, flag, keep raw, re-derive the top 50 by a computable rule |
| A10 | The legal and financial vehicle | Before the first payment | 2026-09-21 | Any single payment over $500, or a grant offer | Personal out-of-pocket under a $750/yr cap; fiscal host on trigger |
| A11 | Governance beyond one maintainer | Before the repo goes public | 2026-09-21 | The first outside contributor asks for write access | Staged ladder, domain CODEOWNERS with a lapse rule, two admins minimum |
| A12 | One evidence-grade vocabulary, and does it become a field? | Before the first ingest | 2026-09-22 | A second adapter needs to set a provenance grade | Converge the *schema* on `06`'s four-level scheme; leave the prose alone |
| B1 | Breadth versus per-entry depth | Phase 1 | 2026-09-21 | The 20-entry checkpoint | Depth bar per entry plus the canonical allocation in `02` §3; no new count |
| B2 | Historical coverage | Phase 1 | 2026-09-17 | A trend view looks like dots rather than lines | 2022 onward in full, ≤5 anchor claims per domain family |
| B3 | Domain expert reviewers | Phase 1 | 2026-09-17 | Three asks produce no reviewer | Three domains, named credit, co-authorship offer |
| B4 | Second annotator; is an LLM rater legitimate? | Phase 1 | 2026-09-21 | `03`'s per-term IRR F1 floor is breached | Yes as a defect detector, never as the published number; buy the human |
| B5 | Depth of ingestion from Epoch and CC-BY peers | Phase 1 onward | 2026-09-17 | Epoch changes licence, format or cadence | Bulk, badged, segregated; source contract written before first ingest |
| B6 | Non-English and non-Western benchmarks | Phase 1, before the gap matrix is published | 2026-09-22 | The Gap Finder asserts a gap in a row where the Chinese-language ecosystem is active | English-first, said out loud and measured; OpenCompass at Tier 2; one reviewer on a stated trigger |
| C1 | Vendor-submitted claims | Phase 3 | 2026-09-17 | A vendor claim without an artifact reaches a comparison view | Accept, badge, exclude artifact-less ones from comparison |
| C2 | Bibliographic data source | Phase 3 | 2026-09-17 | OpenAlex metering changes again | OpenAlex bulk for institutions, S2 keyed for identity |
| C3 | Systems that no longer exist | Phase 3 | 2026-09-21 | A retired model's claim appears in "current SOTA" | `System.availability` orthogonal to `open_weights`; out of SOTA, in trajectories |
| C4 | When may an ingested claim enter comparison? | Phase 3 | 2026-09-21 | The real `condition_completeness` distribution is measured | `comparison_floor` 0.4 + `maintainer-verified` + an archived source |
| C5 | Sustainability and succession | Before public v1 | 2026-09-21 | Six months with no commit to `data/` | `SUCCESSION.md`, a prepaid domain, and an automatic staleness banner |
| C6 | Do we run analytics at all, and if so what? | Before public v1 | 2026-09-21 | Anyone asks for a metric the aggregate feed cannot answer | Server-side aggregate only, no beacon, no cookies, published publicly |
| C7 | The response to a legal threat over a published signal | Before public v1 | 2026-09-21 | The first letter arrives | Evidence inline, dispute not deletion, counsel identified in advance |
| AI1 | Does the AI layer justify one serverless function? | Before the AI phase | 2026-09-21 | A build artifact ever depends on a Worker response | Yes, under four conditions enforced by access control and branch protection |
| AI2 | Where does the query embedding happen? | Before the AI phase | 2026-09-21 | The JS encoder exceeds two days of work | Client-side static embeddings primary; Worker-side Voyage is fallback #1 |
| AI3 | Do we publish our own AI eval, test split included? | Before the AI phase | 2026-09-21 | The fresh fraction on the trend page drops below half | Publish everything; the set is contaminated by publication and we say so |
| AI4 | Suite assembly versus authoring benchmarks | Before the AI phase | 2026-09-17 | All three revisit conditions hold at once | Assembly only; authoring needs a data host we will not be |
| E1 | Ingestion aggressiveness | Ongoing | 2026-09-17 | A hallucinated field reaches `main` | Discovery aggressive, field population conservative |
| E2 | Should the index host anything? | Standing | 2026-09-21 | Someone proposes a service with an uptime obligation | Static artifacts plus an MCP server; no uptime obligation, ever |
| E3 | Sponsorship and institutional affiliation | Before accepting anything | 2026-09-17 | An offer arrives | Only money that cannot buy inclusion; publish `funding.yaml` |
| E4 | Publication and outreach at v1; an academic paper? | Before public v1 | 2026-09-21 | The corpus passes 500 entries | Technical report at v1; the D&B paper is a post-v1 question |
| E5 | What if a competitor relicenses to CC-BY? | Watch continuously | 2026-09-17 | A licence file changes on either site | Ingest them and shift the pitch to conditions and depth |
| F | Items handed here by other documents | Various | 2026-09-22 | Per row | See [section F](#f-items-handed-here-by-other-documents) |

---

## A. Blocking before Phase 0, or before the first public commit

These must be settled before the first schema commit, the first ingest run, or the moment the
repository becomes visible, because each is cheap now and expensive to retrofit across hundreds of
files. The section is large for one specific reason: [A2](#a2-public-from-commit-one-or-curate-privately-to-the-phase-1-exit-bar-first)
makes the repository public from the first commit, which pulls the licence, the name, the governance
ladder and the money question forward into Phase 0.

### A1. Given three adjacent projects launched in the last 14 months, is a separate project still the right vehicle?

**The question.** Should this be a new project at all, or should the effort go into an existing
one — most plausibly Every Eval Ever (EvalEval Coalition: HuggingFace, University of Edinburgh,
EleutherAI; arXiv 2606.14516; 22,235 models, 2,273 benchmarks; data CC BY 4.0, code MIT)?

**Why it matters.** The founding premise of the earlier draft — that nobody had built a
cross-domain benchmark catalogue — is false as stated, and the plan's credibility depends on
saying so plainly. BenchmarkList (launched 2026-07-15; 2,545 benchmarks, 1,604 providers, 24,074
models) is genuinely cross-domain and closed. Benchmark Radar (benchmark-radar.org, arXiv
2609.11115, 2026-09-10) is open-source, daily-updating, 37 ingestion sources — but LLM-centric by
its own abstract and content-licensed CC BY-NC-SA 4.0. Every Eval Ever is the closest in spirit and
the most permissively licensed. Starting a fourth project in an occupied field needs a reason
better than preference.

**Recommendation: a separate project, with a written interop contract rather than a merge.** The
reason is structural, not territorial. Every Eval Ever models *results*; this project models
*benchmarks*. Their `eval.schema.json` has no benchmark-entity catalogue: no domain taxonomy, no
modality, no dataset licence, no lifecycle or liveness model, no lineage. Folding a
benchmark-entity catalogue into a result registry subordinates the taxonomy work — the actual long
pole — to somebody else's roadmap and release cadence. The right move is to be explicitly the
benchmark-registry counterpart to their result-registry, adopt their field names where the data
overlaps (see [A7](#a7-how-far-do-we-adopt-every-eval-evers-schema-vocabulary)), carry a
claim-level cross-reference, and propose the pairing to them directly at public v1. This is the
highest-leverage single relationship in the landscape and it costs nothing to offer.

The contrary case deserves recording: if EvalEval adds a benchmark-entity schema with a domain
taxonomy before this project ships anything public, the differentiator collapses to the non-language
domains alone and a merge becomes the honest answer.

**If overturned:** [01-landscape-and-positioning.md](01-landscape-and-positioning.md) is rewritten,
[00-vision-and-scope.md](00-vision-and-scope.md) changes its framing, and
[14-roadmap.md](14-roadmap.md) becomes a contribution plan rather than a build plan.

### A2. Public from commit one, or curate privately to the Phase 1 exit bar first?

**The question.** The archive asked "public project or internal R&D tool?" That is answered — every
differentiator in this plan (CC-BY, a DOI, forkability at a commit hash, an issue-form contribution
path) presupposes a public artifact, and an internal-only version would not be worth building. The
live question is narrower and harder: does the repository go public on day one, or at the Phase 1
exit?

**Why it matters.** Two forces pull in opposite directions. Publishing early is how the succession
story becomes real rather than aspirational, it establishes priority in an occupied field, and it
is the only way an outside contributor can appear before the maintainer's attention runs out.
Publishing early also means launching against BenchmarkList's 2,545 entries with perhaps twenty of
our own, in a field where the first comparison anyone makes is a count — a comparison we lose and
must never enter.

**Recommendation: repository public from commit one; the site gated until the Phase 1 exit bar.**
Put the YAML, the schema and the taxonomy in a public repo immediately with a `STATUS: pre-alpha,
not yet a usable index` in the README. Do not deploy a public site, do not announce, and do not
appear in a launch feed until **the Phase 1 exit bar in [14-roadmap.md](14-roadmap.md) is met —
≥290 entries, all 19 domain families non-empty or muted under the floor rule, ≥130 entries across
the seven Core families, every entry `primary-source-verified` or better, every entry carrying at
least one archived source.** Those are `14`'s gates, derived from the canonical allocation in
[02-taxonomy.md](02-taxonomy.md) §3 and settled in `_workflow/decisions/D2-seed-targets-and-floor.md`;
this register does not hold a second copy of them and any figure here that disagrees with `14` is
wrong by construction. An earlier revision of this file said "≥150 benchmarks, ≥15 domain families,
none empty", which was both a different plan and internally incoherent — if none are empty the
count is 19 of 19, not 15.

This gets the licence, the fork path and the audit trail in place from the start — the specific
things Ecosystem Graphs lacked and could not be rescued for — while denying anyone the chance to
evaluate the project at its thinnest.

The failure mode to avoid is the opposite of the obvious one. It is not that someone steals the
idea; the idea is visibly already taken three times over. It is that the project gets its one
first impression at twenty entries.

**If overturned:** [14-roadmap.md](14-roadmap.md) phase gates,
[05-repository-and-workflow.md](05-repository-and-workflow.md) launch sequencing.

### A3. What counts as an "AI benchmark"?

**The question.** Where exactly is the boundary of the corpus? The archive's answer — "any
benchmark used to evaluate a system that performs a task requiring intelligence, regardless of
method" — is directionally right and operationally useless, because it does not tell a curator
what to do with a specific artifact at 11pm.

**Why it matters.** This is the single biggest lever on corpus size and therefore on curation cost.
The boundary bites hardest exactly where the differentiator lives. Physics, chemistry and climate
are full of intercomparisons that are called benchmarks and contain no AI at all: PDE solver
comparisons, model intercomparison projects, numerical-methods shootouts. Including them multiplies
the corpus and serves nobody. Excluding them carelessly deletes PDEBench, The Well (15 TB, 16
physics simulation datasets, Polymathic AI / Flatiron) and SRBench, which are the physics entries
an AI engineer actually wants. Meanwhile the domain research surfaced several artifacts that break
the definition from the other side: Metriq and the QED-C application-oriented quantum benchmarks,
where the system under test is *hardware*; RoboCup and the A2RL Drone Championship, which are
physical tournaments with no dataset; CACHE and the CCDC CSP blind test, where the ground truth is
generated in a wet lab after submission; and Open X-Embodiment, which is a dataset whose
"results" are produced per-lab on each lab's own robots and are therefore not comparable at all.

**Recommendation: the learned-entrant test, with the evidence recorded per entry.** A benchmark is
in scope if at least one entrant, submission or leaderboard row is a learned system, and the entry
records a citation for that. This is mechanical, auditable, and it puts the burden where it
belongs: on evidence, not on the curator's taste. Three refinements make it work in practice:

| Case | Decision | Mechanism |
| --- | --- | --- |
| Numerical-methods intercomparison with no learned entrant (CMIP-style) | Out | No `learned_entrant_evidence` → not admissible |
| Physics/chemistry surrogate benchmarks (PDEBench, The Well, Matbench Discovery, OC20/OC22) | In | Learned entrants are the point of the benchmark |
| Hardware or system benchmarks (Metriq, QED-C, MLPerf Inference) | In, flagged | `evaluation_target: system_efficiency`, never `capability`; excluded from headroom and from capability comparison |
| Physical tournaments (RoboCup, A2RL, CARLA Leaderboard 2.0) | In | `execution_mode: physical`; no dataset link is not a validation failure |
| Wet-lab-validated challenges (CACHE, CSP blind test, OCx24) | In | `ground_truth_source: experimental`; `reproducible_by_third_party: false` |
| Datasets that are not benchmarks (Open X-Embodiment) | Out as a benchmark | Catalogued as a `resource` linked from the benchmarks that use it; carries no claims |
| Human cognitive test batteries | In only where AI systems have been evaluated against them | Same learned-entrant evidence rule |

**All five field names in that table are new and exist nowhere in the schema yet.**
`learned_entrant_evidence`, `evaluation_target`, `execution_mode`, `ground_truth_source` and
`reproducible_by_third_party` appear nowhere in [04-data-model.md](04-data-model.md) or anywhere
else in this plan — a grep across all sixteen documents returns only this file. They are **new
fields on `Benchmark`, to be added to [04-data-model.md](04-data-model.md) §15 before the first
ingest**, alongside the eight prerequisites already listed there. Stating that plainly is the point:
an admissibility rule that references fields nobody has modelled is an admissibility rule that will
be enforced by taste. Sketch, for `04`'s owner to refine:

```yaml
admissibility:
  learned_entrant_evidence:          # required for a non-stub Benchmark
    source: src-oc22-leaderboard     # ref into data/sources/
    quote: "GemNet-OC ... MAE 0.213 eV"
    retrieved_at: 2026-09-17
  evaluation_target: capability      # capability | system_efficiency | hardware
  execution_mode: dataset            # dataset | simulator | physical | hybrid
  ground_truth_source: annotated     # annotated | computed | experimental | held-out-server | human-judgement
  reproducible_by_third_party: true  # true | false | null (unknown, which is not false)
```

The `evaluation_target` split is the important one and it is new. A benchmark measuring throughput
per watt and a benchmark measuring reasoning are both legitimately "AI benchmarks", and both belong
in a catalogue an engineer searches — but letting them share an axis would produce exactly the
category error this project exists to prevent. `evaluation_target: system_efficiency` is what
excludes MLPerf Inference from headroom without excluding it from search.

**If overturned:** [02-taxonomy.md](02-taxonomy.md) vocabularies,
[04-data-model.md](04-data-model.md) §15 and the admissibility validators, Phase 1 curation targets
in [14-roadmap.md](14-roadmap.md), and the scale estimates in
[00-vision-and-scope.md](00-vision-and-scope.md).

### A4. Data and code licensing.

**The question.** What licence covers `data/` and `taxonomy/`, and what covers `tools/` and
`site/`?

**Why it matters.** Three things now hang off this that did not hang off it when the archive was
written. First, survivability: Stanford CRFM's Ecosystem Graphs — the exact architecture proposed
here, from a well-resourced lab — has been dead since 2025-01-24 with 274 stars, zero open issues
and **no licence**, which is precisely why nobody could fork it when the lab moved on. Second,
differentiation: BenchmarkList states no licence at all and offers no API or bulk download;
Benchmark Radar's content is CC BY-NC-SA 4.0, which blocks the commercial, institutional and
regulatory reuse that would make it infrastructure. Third, adoption: plain CC-BY is nearly
unoccupied in this space — **the only CC-BY holders the 2026-09-17 landscape recon found were Epoch
AI, Arena/LMArena, OpenRouter and Every Eval Ever** (`_workflow/recon/recon_landscape.md`; that is
the set one researcher found in one pass, not a proven exhaustive list) — and it is the only licence
under which a company, a regulator or a commercial eval vendor can build.

**Recommendation: CC-BY-4.0 for `data/` and `taxonomy/`; MIT for `tools/` and `site/`.** No
ShareAlike, no NonCommercial, no exceptions, and the `LICENSE` files land in the first commit
rather than "before launch". Avoid ShareAlike specifically because it is the clause that makes
Benchmark Radar unusable as infrastructure, and avoid NonCommercial because the institutional
adoption path (EU AI Act GPAI obligations became enforceable 2026-08-02 and require evaluation
"using standard benchmarks and state-of-the-art tests" with no registry defining what qualifies)
runs entirely through organisations that a NonCommercial clause excludes.

The risk worth stating: CC-BY is the cheapest of our differentiators to copy. See
[E5](#e5-what-do-we-do-if-a-competitor-relicenses-to-cc-by).

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md),
[01-landscape-and-positioning.md](01-landscape-and-positioning.md), and every attribution surface
in [08-infrastructure-and-build.md](08-infrastructure-and-build.md).

### A5. The Papers with Code CC-BY-SA firewall.

**The question.** Papers with Code is dead (sunset 2025-07-24; `paperswithcode.com` 301-redirects
to `huggingface.co/papers/trending`). Its archive survives on HuggingFace under the `pwc-archive`
org, at a final scale of 9,327 benchmarks and 79,817 paper-code links; the per-repository row counts
and their retrieval dates are tabulated in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), which owns them, and every repository is
tagged **`cc-by-sa-4.0`**. It is the largest cold-start corpus available anywhere. Do we ingest it,
quarantine it, or refuse it?

**Why it matters.** This is the single largest legal risk in the whole ingestion strategy, and it
must be decided *before* the first ingest rather than discovered at launch. ShareAlike is viral: on
a strict reading, incorporating PwC's task taxonomy or evaluation-table rows into our YAML obliges
the derivative to be CC-BY-SA, which directly contradicts
[A4](#a4-data-and-code-licensing) and would forfeit the licensing differentiator that most of the
positioning rests on. The temptation is enormous, because 9,327 benchmarks is roughly thirty times
the canonical seed target ([02-taxonomy.md](02-taxonomy.md) §3) and it is sitting there in a single
download.

**Recommendation: quarantine, and use it as a reconciliation key only.** Concretely:

- PwC-derived content lives in **`vendor/pwc-archive/`** with its own `LICENSE` file naming
  CC-BY-SA-4.0. That tree is excluded from the CC-BY core and from the published build artifacts.
- The only thing that crosses the firewall is a *fact re-derived from a primary source*: a curator
  uses PwC to learn that a benchmark exists and what it is called, then writes the entry from the
  paper, the repo or the leaderboard, with its own `source_url` and `retrieved_at`.
- Every field carries `provenance`, and a CI rule fails the build if any field whose provenance
  includes `pwc-archive` appears in a published artifact. The invariant is mechanical, not a matter
  of curator discipline.
- Names, identifiers and the bare fact of a benchmark's existence are plausibly uncopyrightable
  facts rather than protectable expression *(unverified — this is a layperson's reading and should
  have a lawyer's confirmation before it is relied on as the basis for anything load-bearing)*.
  The recommendation does not depend on that reading holding, which is the point of making it a
  reconciliation key rather than a content source.

**The path collision, named and settled here because this is the right place to record it.** Four
spellings of the quarantine tree are in circulation: `vendor/pwc-archive/`
([05-repository-and-workflow.md](05-repository-and-workflow.md) §2 layout and §11 legal posture),
`vendor/pwc/` ([06-sourcing-and-scraping.md](06-sourcing-and-scraping.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)), `sources/pwc-archive/`
([04-data-model.md](04-data-model.md) licence-firewall table) and `sources/pwc/` (the landscape
recon). **`vendor/pwc-archive/` wins**, for two reasons: `05` owns the repository layout and its
directory tree is the one a curator actually reads, and `sources/` already means Source *entities* in
this schema, so a `sources/pwc*/` tree would collide with a modelled entity type in the one place
where a mechanical CI rule has to be unambiguous. Required edits: `06`, `07` and `04` adopt
`vendor/pwc-archive/`.

The alternative — dual-licensing the whole index CC-BY-SA — buys 9,327 seed entries at the cost of
the only licensing position in the field that is both defensible and unoccupied. It is not worth
it, and it would put us in the same box as Benchmark Radar.

**If overturned:** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) source catalogue,
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) adapter order,
[05-repository-and-workflow.md](05-repository-and-workflow.md) layout and legal posture,
[04-data-model.md](04-data-model.md) licence firewall, and the whole of
[A4](#a4-data-and-code-licensing).

### A6. Name, domain, identifier permanence, and DOI.

**The question.** What is the project called, at what domain, under what GitHub org, with what entity
ID scheme, and when is the first DOI minted?

**Why it matters.** IDs and URLs are the one thing in the system that cannot be changed later
without breaking everything downstream of a citation. This project's whole value proposition is
that a specific claim can be cited at a specific version — so a renumbering event is not an
inconvenience, it is a credibility failure. And the name is not a cosmetic tail-end decision: every
outreach action in [E4](#e4-publication-and-outreach-at-public-v1-and-do-we-want-an-academic-paper)
addresses people *by* the project's name, the `funding.yaml` URL in
[E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation) needs a domain, the JSON-LD
namespace in [A8](#a8-do-we-commit-to-publishing-a-croissant-benchmark-extension-and-when) is
`https://<our-domain>/ns/...`, and the Zenodo DOI carries the name in its title forever.

**Recommendation.** Five parts, and the first is a name rather than a procedure.

**1. The name: `Evalmap`.** Domain `evalmap.org` (with `evalmap.dev` held as the docs/dev alias),
GitHub org `evalmap`, JSON-LD namespace `https://evalmap.org/ns/croissant-benchmark/v1`.
**Availability is UNCHECKED as of 2026-09-21 on all four surfaces and must be checked before
anything is registered** — registrar lookup for `.org` and `.dev`, an HTTP status check on
`github.com/evalmap`, a text search of the USPTO and UKIPO trademark registers, and a search of
arXiv plus the HuggingFace, npm and PyPI namespaces for an existing project of that name. The
reasons for the pick: it names differentiator 3 (the coverage and gap map) rather than a count, which
is the one comparison we must never enter; it is one word and seven letters, survives being said
aloud, and does not pattern-match to "Benchmark <noun>" the way BenchmarkList and Benchmark Radar
do; and "eval" is the word the field actually uses. The risk, stated: "eval" is heavily used
(EvalEval, EvalPlus, EvalScope), so a trademark or namespace collision is genuinely possible, which
is exactly why the check precedes the registration.

| Rank | Name | Domain | GitHub org | Checked? |
| --- | --- | --- | --- | --- |
| 1 | **Evalmap** | `evalmap.org` + `evalmap.dev` | `evalmap` | **No — as of 2026-09-21** |
| 2 | Benchmark Atlas | `benchmarkatlas.org` | `benchmark-atlas` | No |
| 3 | The Benchmark Index | `benchmarkindex.org` | `benchmark-index` | No — and closest to BenchmarkList, so highest confusion risk |

**2. The fallback rule: take the whole set or move down the list.** If the `.org`, the GitHub org,
or a clear trademark conflict fails for candidate 1, move to candidate 2 *in full* rather than
mixing (`evalmap.org` with an org handle called something else is a project whose citations
disagree with its repository). Do not mint the DOI, publish the JSON-LD namespace, or write the name
into `CITATION.cff` until the set is secured. **Name the failure mode: the DOI is minted against a
name whose org handle is squatted**, after which either the citation or the repository URL has to
change — and this question's own argument is that a renumbering-class event is a credibility
failure, not an inconvenience.

**3. Stable slug IDs with an alias table**, e.g. `bench:swe-bench-verified`. Never numeric, never
renumbered. Renames go into `aliases[]` and the old slug keeps resolving forever with a 301. The
benchmark lineage problem makes this non-negotiable: OSWorld became OSWorld-Verified *and*
OSWorld 2.0; Terminal-Bench 2.0 and 2.1 ran concurrently; SWE-bench has six forks; FrontierMath
has four variants; HELM has eight. A scheme that cannot express "this is a different benchmark
with almost the same name" will corrupt claims within a month. The on-disk identifier form for
taxonomy terms is settled separately in `_workflow/decisions/D3-vocabulary-namespacing.md` —
family-qualified subdomain paths, bare capability slugs, the facet carried by the field name.

**4. Mint the Zenodo DOI at v0.1, not v1.0.** Zenodo issues a `conceptdoi` (version-independent)
alongside the per-release DOI — verified live on `zenodo.org/api/records`. Minting early costs
nothing and means every early fork is citable, which is the succession story working as designed
rather than as a promise. The depositor of record is named in `SUCCESSION.md` — see
[A10](#a10-what-is-the-legal-and-financial-vehicle).

**5. `CITATION.cff` in the repo root** from the first commit, and a per-entry citation string on
every benchmark page that includes the commit SHA.

**If overturned:** [04-data-model.md](04-data-model.md) identity section,
[05-repository-and-workflow.md](05-repository-and-workflow.md),
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) URL scheme, and every document
containing the string `<our-domain>`.

### A7. How far do we adopt Every Eval Ever's schema vocabulary?

**The question.** Three options: (i) join on IDs only and name our fields as we please; (ii) adopt
their field *names* for the conditions we share; (iii) embed their schema as a sub-object and
validate against it.

**Why it matters.** Joinability across the two registries is the entire value of the alliance in
[A1](#a1-given-three-adjacent-projects-launched-in-the-last-14-months-is-a-separate-project-still-the-right-vehicle).
A result validated against `eval.schema.json` should be able to attach to our benchmark record
without a translation table that somebody has to maintain. But their schema is theirs; it will
change on their schedule, and embedding it means importing their breaking changes into our
validation.

**Recommendation: option (ii) — adopt their field names verbatim for the fields we share, and do
not embed their schema.** Use `generation_args` (with `temperature`, `top_p`, `max_tokens`),
`agentic_eval_config.available_tools`, `sandbox`, and `metric_config` (`lower_is_better`,
`score_type`, `min_score`, `max_score`) exactly as they spell them, even where our own naming
instinct differs. Pin the EEE schema version we aligned to in the docs, and add a CI test that
validates a sample of our `EvalConditions` records against their published schema so divergence
surfaces as a test failure rather than as a surprise in eighteen months.

**On the cross-reference field, precisely.** The benchmark-level join key **already exists**:
`Benchmark.external_ids.every_eval_ever` ([04-data-model.md](04-data-model.md) §5, described there
as "the interop surface"). What does not exist is a *claim-level* pointer, and one is needed,
because the whole point of the alliance is that their result record and our claim record describe
the same measurement. That is a **new field, `ResultClaim.external_ids.eee_result_id`, to be added
to [04-data-model.md](04-data-model.md) §15 before the first ingest** — cheap now, painful across
thousands of ingested rows later. Nothing else in this section is new.

Adopting somebody else's naming for aesthetic loss and interoperability gain is almost always the
right trade in metadata work, and it is nearly always resisted. Note that it will feel wrong at
least twice during Phase 0; do it anyway.

**If overturned:** [04-data-model.md](04-data-model.md) `EvalConditions` and §15,
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) alliance section.

### A8. Do we commit to publishing a Croissant benchmark extension, and when?

**The question.** MLCommons Croissant is the adopted ML-dataset metadata standard — HuggingFace
emits it per dataset at `/api/datasets/{id}/croissant`, Kaggle exports it, OpenML offers it, TFDS
builds it, Google Dataset Search crawls it — and it has **no evaluation or benchmark extension**.
A benchmark is not a dataset: it adds tasks, metrics, splits, protocols and conditions. Do we claim
that ground, and when?

**Why it matters.** This is the highest strategic leverage per unit of effort in the entire
landscape analysis. Publishing `croissant-benchmark` converts the project from "another website"
into a standard with an institutional home and free distribution through Google Dataset Search. It
is also a standards-body commitment made by a one-to-two-person part-time team, which is exactly
the kind of obligation that eats the curation budget that is already the binding constraint. And
there is a licensing trap: the Croissant *spec* is CC BY-ND 4.0 — no derivatives — so we may
publish a separate, namespaced extension but must never republish a modified spec.

**Recommendation: split the commitment. Design for it in Phase 0; emit in Phase 2; propose after
public v1.** The sizing is not this document's to invent —
[14-roadmap.md](14-roadmap.md) budgets the mapping, the namespaced context, three worked examples
and the MLCommons issue at **10–20 hours** and owns that figure. What this register adds is the
mapping sketch, because the hard part *is* the mapping and a proposal without one is a slide deck.

**The mapping sketch.** Mapped against the Croissant specification as published at
`mlcommons.org/croissant` and read on 2026-09-17 *(the exact spec version is unverified — pin the
version string and re-read it before emitting anything, because a mapping against an unnamed version
is not testable)*. Committed as `croissant/mapping.yaml` so it is a fixture rather than prose.

| Our field | Croissant target | Status |
| --- | --- | --- |
| `Benchmark.name`, `.aliases[]` | `sc:name`, `sc:alternateName` | Direct |
| `Benchmark.description`, `.tagline` | `sc:description` | Direct |
| `Benchmark.homepage`, `.repository` | `sc:url`, `sc:sameAs` | Direct |
| `Benchmark.license` (the *dataset's* licence, never ours) | `sc:license` | Direct — and the commonest emitter bug, because our own CC-BY is a different fact |
| Citation string, DOI | `sc:citeAs`, `sc:identifier` | Direct |
| `BenchmarkVersion.version` | `sc:version` | Direct |
| `Subset` / splits | `cr:RecordSet` + `cr:Field` | Direct where the subset is a data split; **not** where it is a task variant |
| Dataset files and mirrors | `cr:FileObject` / `cr:FileSet` | Direct, and pointer-only — we never host the bytes ([E2](#e2-should-the-index-host-anything)) |
| `Metric` (`optimum`, `unbounded`, range, `lower_is_better`) | **no slot** → `cb:Metric` | **New, ours.** Croissant describes fields, not scores |
| `EvalConditions` + `comparability_key` | **no slot** → `cb:EvalConditions`, `cb:comparabilityKey` | **New, ours.** A protocol is not data, and this is the whole differentiator |
| Task and protocol (`evaluation_target`, `execution_mode`, `ground_truth_source`) | **no slot** → `cb:Task` | **New, ours.** See [A3](#a3-what-counts-as-an-ai-benchmark) |
| `lineage.supersedes` / `superseded_by` | **no slot** → `cb:supersedes`, `cb:supersededBy` | **New, ours.** Nobody models lineage; Epoch needed a `superseded_by` column and stopped there |
| `ResultClaim`, `Baseline` | **deliberately not mapped** | Out of scope for the extension. Results belong to Every Eval Ever's registry ([A1](#a1-given-three-adjacent-projects-launched-in-the-last-14-months-is-a-separate-project-still-the-right-vehicle)) |

So the extension introduces **four new classes and two new properties** under a `cb:` namespace we
own, and reuses `sc:` and `cr:` for everything that already has a home. That is a small enough
surface to propose and a large enough one to be worth proposing. Emit `croissant.jsonld` per
benchmark from the Phase 2 build as an unofficial namespaced extension, and say plainly on the
methodology page that it is unofficial.

**On when to approach MLCommons: after public v1, not at 500 entries.** An earlier revision of this
file set the bar at "≥500 entries across ≥15 domain families", which is a bar v1 does not clear —
the canonical v1 target is 320 entries across 19 families ([02-taxonomy.md](02-taxonomy.md) §3), and
500–700 families is `00`'s twelve-month steady state, not the launch
([14-roadmap.md](14-roadmap.md) §"Which document is canonical for scale"). Setting an unreachable
bar is how a deliverable silently becomes "never". **The real bar is: public v1 shipped, the emitter
running over the whole corpus, three worked examples from three genuinely different domains (one
language, one robotics, one chemistry — a standard demonstrated only on the easy case is not a
standard), and at least one external contributor.** Do not approach the MLCommons Datasets WG
(co-chairs Omar Benjelloun, Elena Simperl, Joaquin Vanschoren, per
`_workflow/recon/recon_landscape.md` on 2026-09-17 — *unverified; confirm the current co-chairs
before writing to anyone*) before that. A standards proposal from a project with a corpus and a
working emitter is a fait accompli the working group can adopt cheaply.

Whether MLCommons would accept such an extension at all is **unverified — confirm before relying on
this**; the observation is only that the slot is empty.

**If overturned:** [04-data-model.md](04-data-model.md) field naming,
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) build outputs,
[14-roadmap.md](14-roadmap.md) Phase 4 and post-v1 phases.

### A9. What is our commitment if an upstream source we depend on sunsets?

*Deadline: before the first adapter ships, which makes this a sibling of
[A5](#a5-the-papers-with-code-cc-by-sa-firewall) rather than a longer-horizon item. It sat in the
longer-horizon section for one revision, which is how a pre-Phase-1 decision gets read last.*

**The question.** Papers with Code was the largest and best-funded attempt in this space and it was
switched off by its owner on 2025-07-24, with 9,327 benchmarks and 79,817 paper-code links. It did
not die of staleness. What do we owe our readers when that happens to a source we depend on?

**Why it matters.** Every adapter creates a dependency, and a dependency with no stated failure
behaviour will fail silently. The specific harm is that a sunset source's data does not disappear
from our index — it freezes, keeps rendering, and keeps looking current. Stanford's Ecosystem
Graphs is still cited as a data source by 2025–26 research while twenty months stale, which means
stale curation is actively propagating errors into the literature. That is the harm to avoid.

**Recommendation: a written source-continuity policy, four commitments.**

1. **Keep the raw.** Every adapter stores its last raw response gzipped under `_ingest/raw/`. A
   sunset must not erase what we already fetched.
2. **Evidence outlives the source.** Every ingested field carries `source_url` *and* `wayback_url`.
   Archiving is a mandate, not an enhancement — via Save Page Now 2 with
   `if_not_archived_within` as the idempotency key, and the CDX API (never the Availability API,
   which returned 429 on a single cold request) for existence checks.
3. **Freeze visibly, never delete.** On sunset, the `source` record flips to `status: sunset` with
   a date, its records freeze at their last snapshot, and every field derived from it renders a
   "source sunset <date>" marker. Deleting the data would be the easy move and it destroys the
   historical record; leaving it unmarked would be dishonest.
4. **Re-derive the top of the tail, by a rule the plan can actually compute.** Commit to
   re-deriving, from primary sources, the top **50** affected entries within one release cycle of the
   sunset, ranked by `inbound_source_refs + claim_count`, with Core-family membership
   ([02-taxonomy.md](02-taxonomy.md) §3) as the tiebreak. An earlier revision ranked by *page views*,
   which the site cannot measure — there is no auth, no accounts, and the analytics posture was
   itself unasked until [C6](#c6-do-we-run-analytics-at-all-and-if-so-what). Request counts, if
   C6's aggregate feed exists, are a second tiebreak and never the primary key, because a commitment
   whose input might not exist is not a commitment.

The reverse obligation, which is
[C5](#c5-sustainability-and-the-succession-story), is the same policy pointed at ourselves.

**If overturned:** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) state and archival.

### A10. What is the legal and financial vehicle?

*New. Three recommendations in this register spend money and none of them said whose.*

**The question.** Is this personal out-of-pocket spending, a fiscally hosted project, or an
incorporated entity — and who is the Zenodo depositor of record?

**Why it matters.** [B4](#b4-who-is-the-second-annotator-and-is-an-llm-second-rater-legitimate)
says to buy a human annotator. [E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation)
permits paid domain-expert review contracts and contemplates grants. [C5](#c5-sustainability-and-the-succession-story)
requires a domain that outlives the maintainer's attention, which is a recurring renewal cost by
definition. An unincorporated individual generally cannot receive a UKRI or foundation grant or sign
a review contract *(unverified — this varies by funder and jurisdiction and should be checked against
a specific funder's terms before anything is applied for)*, and a Zenodo deposit keyed to a personal
email address is a succession problem waiting to happen. Meanwhile `E3` rules out the funders most
likely to say yes and `C5` concludes the realistic path is reduced scope plus an institutional home.
Leaving all of that implicit is how a project discovers in month nine that it cannot accept the one
offer it gets.

**Recommendation: personal out-of-pocket for v1, under a stated annual cap, with a trigger-gated
step to a fiscal host.**

**The cap: $750 per year of recurring spend, plus a one-off annotator cost of roughly $400 in
Phase 1.** Itemised so the cap is falsifiable rather than decorative:

| Item | Cost | Note |
| --- | --- | --- |
| Domain, `.org` + `.dev` | ~$15–40/yr each; prepay 10 years once (see [C5](#c5-sustainability-and-the-succession-story)) | *Unverified — registrar-dependent; price it at registration* |
| Hosting | $0, rising to $60/yr if the paid Workers plan is needed | Static asset requests are unbilled; the $5/month plan is an AI-layer cost ([08-infrastructure-and-build.md](08-infrastructure-and-build.md)) |
| Embedding | $0 | [AI2](#ai2-where-does-the-query-embedding-happen-the-reports-disagree) makes the query encoder client-side and static; the Voyage fallback's first 200M tokens are free ([11-ai-features.md](11-ai-features.md)) |
| AI layer | Small at 1,000 queries/month, steep above that | [11-ai-features.md](11-ai-features.md) §*Monthly budget* owns the figures and their derivation; do not restate them here |
| Annotator | ~$400, one off | ~20 hours at a graduate-student rate ([B4](#b4-who-is-the-second-annotator-and-is-an-llm-second-rater-legitimate)) |

The honest read of that table is that **the AI layer is what breaks the cap, not the catalogue.**
Everything required to publish and cite the index costs on the order of a domain renewal. That is
worth saying out loud, because it means the cap constrains an optional phase rather than the
project, and it is the strongest available argument that this is a survivable part-time commitment.

**The trigger for a fiscal host:** the first time any single payment exceeds $500, any recurring
monthly cost exceeds $60, or a grant or contract is offered. Candidates, in the order they would be
approached: Open Collective (fiscal hosting for open-source collectives), a NumFOCUS-style
affiliated-project route for scientific open source, or the legal entity attached to whichever
institutional home [C5](#c5-sustainability-and-the-succession-story) lands. **All three are
unverified as to eligibility for a data-catalogue project — confirm before applying**, and confirm
before promising a funder anything.

**Do not incorporate for v1.** A limited company or a charitable entity costs registration money and
annual filing time drawn from the same budget as curation, and it buys nothing until there is money
to receive or a contract to sign. Incorporation is what the fiscal host defers, not what it replaces.

**The depositor of record** is the founding maintainer, named in `SUCCESSION.md` by GitHub handle
**and ORCID**, with the ORCID registered in Phase 0 — it is free, it takes five minutes, and it is
the difference between a DOI keyed to a persistent researcher identifier and one keyed to an email
address that will change.

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md) succession and
releases, [E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation),
[C5](#c5-sustainability-and-the-succession-story).

### A11. Governance beyond one maintainer: what happens when the first outside contributor wants commit rights?

*Deadline: before the repository becomes public, which under [A2](#a2-public-from-commit-one-or-curate-privately-to-the-phase-1-exit-bar-first)
is the first commit. A governance policy written after the first dispute reads as though it was
written about that person.*

**The question.** Someone contributes fourteen good robotics entries and asks for write access.
What is the answer, and who decides?

**Why it matters.** The first governance dispute is the worst possible time to write a governance
policy. And the survival evidence points hard in one direction: HELM entered maintenance mode on
2026-06-01, while MedHELM survived by spinning out to an independent steward with its own licence
and its own technical stewardship. Per-domain stewards are not a nice-to-have; they are the
structure that outlives the founder's attention.

**Recommendation: a four-rung ladder, written before it is needed, plus three standing rules.**

| Rung | Earned by | Grants |
| --- | --- | --- |
| Contributor | Nothing — the issue form needs no account privileges | Submit entries and corrections |
| Triage | 5 merged substantive contributions | Label, close, request changes. No write access to `data/` |
| Domain maintainer | 15 merged contributions in one family | CODEOWNERS write on `data/benchmarks/<family>/` |
| Admin | Explicit invitation only | Everything |

The three standing rules:

1. **A minimum of two admins at all times** once a second person exists — bus-factor-of-one is
   listed as a risk in the roadmap and a single admin account makes it unmitigable.
2. **A written tie-break**: the founding maintainer decides in year one; thereafter a documented
   rough-consensus process with the tie-break naming a person, not a procedure.
3. **CODEOWNERS entries lapse, reversibly and automatically.** A `CODEOWNERS` line for a family
   whose steward has merged nothing in **6 months** lapses to the admin. The mechanism is a monthly
   scheduled workflow, `codeowners-lapse.yml`, that opens a PR moving the line, labels it
   `governance:lapse`, @-mentions the steward, and leaves a **14-day** objection window before it
   can merge; re-instatement is one merged contribution plus a one-line PR. **Name the failure mode:
   a domain steward with `CODEOWNERS` write on `data/benchmarks/robotics/` goes dark, and that
   family's entries can no longer be reviewed without them** — the exact single-point-of-failure the
   two-admins rule exists to prevent, one level down, and the rung most likely to hit it because a
   domain steward is by construction the only person who knows that field. The rule is written into
   the ladder *before* the first steward is appointed, which is the only time it can be written
   without being about somebody.

Add a Code of Conduct in the first commit for the same reason as the licence: it is trivial now and
it is contentious later.

Note what this is not. It is not a reason to keep contribution friction high; the opposite is
already settled. The contribution path must not require a pull request — the most instructive
failure in this space is `JonathanChavezTamales/llm-leaderboard`, a JSON-in-git schema-validated
community benchmark catalogue with 356 stars that **deprecated itself and converted into a closed
website**, stating contribution friction as the reason. The ladder governs write access; the issue
form governs participation, and those are different things.

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md) governance,
[14-roadmap.md](14-roadmap.md) risk register.

### A12. Should the plan converge on one evidence-grade vocabulary, and should it become a schema field?

**The question.** The corpus currently carries **four incompatible vocabularies for the same idea** —
how well we know a stated fact. [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) uses a
four-level grade, `[M]` observed in a live response / `[D]` documented by the vendor / `[E]` derived /
`[U]` unchecked. [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) uses
`[recon <date>, measured]` / `[recon <date>, vendor docs]` / `(unverified — confirm before relying on
this)`, which is the same three distinctions with the date inline.
[00-vision-and-scope.md](00-vision-and-scope.md) §11 uses a three-tier ladder — `re-derived here` /
`recon-observed` / `reported, not re-verified` — for a different purpose, auditing its own claims.
Everything else uses the bare `(unverified — …)` marker, which collapses all of the above into one
bit. Do we converge, and if so does the winner become `Source.provenance.evidence_grade` on the data
model?

**Why it matters.** Each of the four is internally coherent, so nothing is *wrong* today. Two things
are nonetheless expensive. A reader moving between documents cannot tell whether `06`'s `[D]` is
stronger or weaker than `07`'s `(unverified)` without reading two legends. And more seriously, a
curator implementing `Source.licence_class` or any other provenance-bearing field has three
vocabularies to choose from and no rule for choosing — which means the choice gets made per adapter,
and the corpus ends up with a provenance column whose values are not comparable. The `[D]`/`[M]`
distinction in particular — *what the vendor says it will do* versus *what it actually did* — is
genuinely valuable, is the distinction that most often turns out to matter in an ingest, and exists
nowhere else in the corpus.

**Recommendation: converge the *schema* before the first ingest, on `06`'s four-level scheme; do not
converge the *prose* at all.** Add `evidence_grade: measured | documented | derived | unchecked` to
the `Source` record in [04-data-model.md](04-data-model.md), alongside the `licence_checked_on` date
that the licence firewall needs for the same reason, and make every adapter set it. `06`'s scheme
wins because it is the most expressive of the four, because it is the one that has to reach the
product anyway (a reader looking at a benchmark page wants to know whether a licence was read off a
page or inferred), and because `06` already has a mechanism rather than a promise behind it: its
probe-log rule demotes any value whose probe line cannot be reconstructed to `[U]` at that point.

Deliberately **not** converging the plan documents: that would touch all sixteen, it would buy a
consistency nobody is currently confused by — each legend sits next to its own use — and the hours
come out of the binding constraint. `00` §11's ladder in particular should stay as it is, because it
is auditing this plan's own claims rather than grading a third party's, which is a different job.

**Why it is here rather than in E.** The schema half is cheap now and expensive in six months: adding
an enum to `Source` before the first ingest is minutes, and backfilling it across thousands of
ingested records is the same retrofit problem C5 already warns about for `provenance_snapshot`.

**If overturned:** [04-data-model.md](04-data-model.md) `Source`,
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) adapter contract,
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8 if the grades change meaning.

---

## B. Needed during Phase 1

### B1. Breadth target versus per-entry depth.

**The question.** The seed *count* is settled: 320 entries across 19 domain families, allocated
per-family in [02-taxonomy.md](02-taxonomy.md) §3 and gated in
[14-roadmap.md](14-roadmap.md), under `_workflow/decisions/D2-seed-targets-and-floor.md`. What is
**not** settled, and is what Phase 1 actually has to decide, is two things: **the depth bar a single
entry must clear to count toward that total**, and **the split between hand-curated entities and
machine-ingested records**.

**Why it matters.** The count survives contact with the ingestion strategy; the *metric* does not.
Epoch AI's bundle alone delivers 81 benchmarks and roughly 6,598 result rows from one adapter run
(the landscape recon counts 80 files in the bundle against the summary's 81 benchmarks — reconcile
at ingest), free, under CC-BY. Once ingestion is in the plan, counting entries or claims measures
the adapter, not the work. Meanwhile BenchmarkList has 2,545 benchmarks and Benchmark Radar has
14,810 raw records. Any count comparison is lost before it starts, which is why the number that
matters is a **quality-gated** one.

**Recommendation: the canonical allocation in [02-taxonomy.md](02-taxonomy.md) §3, which this
document does not restate, plus a depth bar expressed entirely in fields that already exist.** An
entry counts toward the 320 only when all of the following hold, each of them checkable in CI
without a new metric:

- `curation.verification_status` is `primary-source-verified` or better
  ([05-repository-and-workflow.md](05-repository-and-workflow.md) §4 owns the vocabulary);
- at least one `Source` with a resolving `archive_url`;
- every one of the eight facets either populated or explicitly null **with a reason** — a blank and
  a considered "not applicable" are different facts and the schema already distinguishes them;
- `lifecycle` set, licence recorded, at least one `Metric` with `optimum` and `unbounded` resolved;
- the admissibility evidence from [A3](#a3-what-counts-as-an-ai-benchmark).

An earlier revision proposed "N benchmarks at curation completeness ≥ X". There is no
`curation_completeness` field anywhere in this plan and inventing one would be a third completeness
score next to `condition_completeness`. The bar above needs no new field.

**On the split: unlimited machine-ingested records in the segregated tree, and no ingested record
counts toward the 320.** The two trees answer different questions — bulk ingestion buys *coverage*,
which is exactly what the user asked for, and hand curation buys *comparison*, which is where
credibility lives ([B5](#b5-how-deeply-do-we-ingest-from-epoch-ai-and-similar-cc-by-sources-and-what-is-the-contract-with-a-source-we-do-not-control),
[C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view)).

**And retire the "≥60% non-language" target.** Under the canonical allocation, language and code
together are 30 of 320 entries, so the index is 91% non-language *by construction*: the target is
satisfied before any work is done and therefore measures nothing. The gate that does measure
something is `14`'s **≥130 entries across the seven Core families** (robotics-embodiment,
biology-genetics, chemistry-materials, medicine-health, physics, earth-climate, audio-speech),
against a target of 144 — those are the families where hand curation has no substitute and no
competitor.

Revisit at the 20-entry checkpoint, which remains the highest-leverage moment in the project: it is
where the measured per-entry median either confirms the depth bar or triggers `14`'s re-cut rule.

**If overturned:** [14-roadmap.md](14-roadmap.md) exit criteria,
[02-taxonomy.md](02-taxonomy.md) §3 allocation,
[12-analytics-and-trends.md](12-analytics-and-trends.md) coverage denominators.

### B2. Historical coverage of systems and claims.

**The question.** How far back do claims go?

**Why it matters.** The saturation and velocity charts need enough history to show a shape, and a
benchmark with three data points is a dot, not a trajectory. Full historical backfill is a large
cost for limited present-day value.

**Recommendation: 2022 onward in full; at most five *anchor* claims per domain family before
that.** The cost calculus changed in one direction only. For language and code, history is now
nearly free — Epoch's per-benchmark CSVs reach well back (`mmlu_external.csv` 249 rows,
`arc_agi_external.csv` 247, `gsm8k_external.csv` 235; **counted from `epochdl/` by the Epoch-assets
recon on 2026-09-17**, and note that `epochdl/` is not present in the current working tree, so
re-count after downloading rather than trusting these three figures). For everything else it is
entirely hand work: CASP rounds, Matbench, TrackML (retired as a competition, still cited — a useful
dead-benchmark test case), the CCDC CSP blind test cycles. So spend the history budget on anchors
that establish a trajectory and nothing more: AlexNet on ImageNet (2012), AlphaFold2 at CASP14
(2020), CASP13 (2018), and their equivalents per family. Cap it at five and enforce the cap, because
historical backfill is the most enjoyable and least valuable curation work available and it will
absorb unlimited time.

**If overturned:** [12-analytics-and-trends.md](12-analytics-and-trends.md) time-to-saturation and
velocity, [14-roadmap.md](14-roadmap.md) Phase 3 sizing.

### B3. Domain expert reviewers: who, and what do we offer them?

**The question.** Who reviews robotics, structural biology and climate entries, and why would they?

**Why it matters.** An hour of expert attention per domain catches errors that weeks of careful
reading will not, and the non-language domains are precisely where the maintainer cannot self-check
and where the differentiator lives. It is also the most effective early outreach available: the
person who reviews your robotics entries is the person who tells the robotics community you exist.

**Recommendation: three domains in Phase 1 — robotics, structural biology, climate/earth — chosen
because they are the three the maintainer cannot check alone.** The domain research names the
communities to approach: CoRL, RSS, ICRA/IROS and the CVPR Embodied AI Workshop for robotics; the
CASP/CAMEO Prediction Center and SIB for structure; NeurIPS ML4PS and the HEP ML Living Review for
physics (itself a direct precedent for a curated index and worth studying); NeurIPS AI4Science, ACS
CINF and RSC *Digital Discovery* for chemistry; MICCAI via Grand Challenge for medical imaging.

What we offer, in order of what actually works: a named `reviewed_by` credit in the YAML and on the
rendered page, at a commit hash, permanently; an offer of co-authorship on the eventual data paper
or technical report (see [E4](#e4-publication-and-outreach-at-public-v1-and-do-we-want-an-academic-paper));
and a review task that is bounded and specific — "here are fourteen robotics entries, tell us what
is wrong" — rather than an open-ended invitation to collaborate. The failure mode is asking a busy
researcher for unbounded engagement; the fix is to ask for exactly one hour and mean it. A reviewer's
pass also doubles as that family's `irr_human` run
([03-taxonomy-build-process.md](03-taxonomy-build-process.md) §6), which is the cheapest way to
convert an hour of goodwill into two artifacts.

Budget for the possibility that this simply does not work: see
[B4](#b4-who-is-the-second-annotator-and-is-an-llm-second-rater-legitimate). The exit criterion in
`14` already accepts the failure case honestly — either a named specialist has signed off on three
unfamiliar domains, or every unsigned domain carries `curation_confidence: unreviewed` on every
entry and in the coverage map. Both are acceptable exits; silence is not.

**If overturned:** [03-taxonomy-build-process.md](03-taxonomy-build-process.md) review process,
[14-roadmap.md](14-roadmap.md) Phase 1.

### B4. Who is the second annotator, and is an LLM second-rater legitimate?

**The question.** Inter-rater reliability on the taxonomy requires two raters. With a one-person
team, who is the second, and can a model be one of them?

**Why it matters.** A published inter-rater reliability number is what separates a taxonomy from
one person's opinions, and it is the first thing a reviewer will ask for
([E4](#e4-publication-and-outreach-at-public-v1-and-do-we-want-an-academic-paper)). It is also the
easiest number in the whole project to fake without noticing. The specific failure mode, which
deserves a name because it will otherwise happen: **self-agreement laundering** — the same model
that drafted the entry is asked to rate it, agrees with itself, and the agreement is reported as
reliability. The AI-features research is blunt about the mechanism: judges exhibit position bias,
verbosity bias and self-preference bias, and ensembling or order-reversal fixes variance but *not*
biases shared across the judge population.

**Recommendation: yes, an LLM second-rater is legitimate — as a defect detector, never as the
published number.** The protocol, the sample sizes and the metric names belong to
[03-taxonomy-build-process.md](03-taxonomy-build-process.md) §6, which owns them and already draws
exactly the distinction this question needs: **`irr_human`** is the published, citable number, run
human-to-human on `03`'s sample; **`taxonomy_drift_check`** is the LLM run, executed in CI over the
whole corpus after every vocabulary-changing ADR, whose output is a ranked list of terms where the
model and the stored value disagree most often. It is a defect detector, never a quality claim, and
an LLM-to-LLM agreement figure is never reported at all. Do not restate `03`'s sample sizes or its
per-term floor here; an earlier revision of this file quoted a 40-entry human subset and
Krippendorff's alpha, neither of which matches `03`, which is precisely how two documents end up
publishing two reliability methodologies.

What this register decides is the part `03` cannot: **who the human is, and what it costs.**

**Buy the human.** Recruit one paid part-time annotator for roughly twenty hours total — a
graduate-student rate, on the order of **$400** — to do the human-to-human round. This is the
cheapest credibility purchase anywhere in the plan, and trying to avoid it is how the taxonomy ends
up with no defensible reliability claim at all. It is also the largest single line in
[A10](#a10-what-is-the-legal-and-financial-vehicle)'s Phase-1 budget, and it is charged there
rather than being left as an unowned intention. The fallback if no annotator can be recruited is a
domain reviewer's pass doubling as the run ([B3](#b3-domain-expert-reviewers-who-and-what-do-we-offer-them));
the fallback to *that* is publishing `taxonomy_drift_check` alone, clearly labelled as not an IRR
figure, which is a worse outcome and must be labelled as one rather than quietly relabelled.

**If overturned:** [03-taxonomy-build-process.md](03-taxonomy-build-process.md) governance and
IRR methodology, [11-ai-features.md](11-ai-features.md) evaluation section,
[A10](#a10-what-is-the-legal-and-financial-vehicle) budget.

### B5. How deeply do we ingest from Epoch AI and similar CC-BY sources, and what is the contract with a source we do not control?

*Deadline: before the first Epoch ingest, which is Phase 1 onward rather than longer-horizon.*

**The question.** The depth question is settled (ingest in bulk, badge honestly, segregate,
hand-curate a small adversarially-chosen set — see
[C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view)). The open part is
the **contract**: what do we owe the source, and what do we owe a reader, when the data is not ours
and we cannot control when it changes?

**Why it matters.** Attribution is cheap to comply with and expensive to be caught violating.
Freshness is worse: an ingested claim that silently ages looks identical to a fresh one, and a
reader who cannot tell has been misled by omission. Epoch's licence is unambiguous — "free to use,
distribute, and reproduce provided the source and authors are credited under the Creative Commons
Attribution license" — but the bundle has no DOI, no version handle and **no per-row provenance
statement**, and 2,613 of its 6,598 rows carry no `Source` value at all
(`_workflow/recon/recon_epoch-assets.md`, counted 2026-09-17).

**Recommendation: a written three-part contract, in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), before the first ingest.**

- **Attribution.** A machine-generated `/attributions` page built from the `sources` entity, so it
  cannot drift from what was actually ingested. Per-record attribution, not just per-file: a blanket
  credit tells the reader where the *file* came from, not where the *number* came from, and for
  roughly 40% of Epoch's rows the answer to the second question is genuinely unknown and must be
  shown as unknown.
- **Freshness.** Weekly conditional GET on `https://epoch.ai/data/benchmark_data.zip` using the
  **ETag** — there is no `Last-Modified` header on that resource, so ETag is the only mechanism
  *(measured by the sourcing recon on 2026-09-17; re-check before relying on it, because a
  disappearing ETag would break the poll silently)*. Every ingested claim carries
  `provenance_snapshot` so a re-ingest supersedes rather than duplicates. Every ingested claim
  renders its snapshot date. If the poll fails for 30 days, the badge changes automatically to
  "upstream unchecked since <date>".
- **Deference.** Never re-derive Epoch's numbers, and explicitly cede authoritative frontier-LLM
  capability trends to them with a link. Honour their `robots.txt`, which disallows
  `/inspect-viewer/` and `/frontiermath/tiers-1-4/benchmark-problems` with the stated reason "to
  avoid contaminating training datasets" — a rule that aligns exactly with this project's own
  anti-contamination ethic, and which it would be a reputational own-goal to breach.

One sub-question worth answering now: **do we ingest Epoch's ECI?** No. Catalogue the Epoch
Capabilities Index as a composite-index *entity* with a note that this project does not compute or
endorse cross-benchmark composites, and link to it. Ingesting its scores as claims would import the
single-number ranking we reject through the back door.

The one-line version of the whole policy, worth keeping: Epoch gives us the numbers for free; it
does not give us the conditions, the facets, the provenance grade, or any domain outside LLMs —
which is precisely the list of things this project exists to provide. Zero of its 81 benchmarks
touch robotics, chemistry, biology, medicine, climate, materials or audio.

**If overturned:** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md),
[04-data-model.md](04-data-model.md) provenance fields.

### B6. What is our position on non-English and non-Western benchmarks, and how do we stop our own sourcing bias being published as the field's gaps?

**The question.** [00-vision-and-scope.md](00-vision-and-scope.md) §6 records assumption **A9 —
English-language primary sourcing** — and hands the question to this register. It has not been
answered here until now. (A pointer note, because the numbering misleads: `00`'s A9 resolves to *this*
entry, B6, not to this register's [A9](#a9-what-is-our-commitment-if-an-upstream-source-we-depend-on-sunsets),
which is about upstream sunsets. The two documents share an A-numbering namespace for different
questions and `00` §6's pointer should name B6 explicitly.) Concretely: does the catalogue index
Chinese, Japanese, Korean, Russian and European-language benchmark ecosystems, and if not, what does
the site say about that?

**Why it matters, and it is the sharpest version of a failure this plan already names elsewhere.**
The pitch is "any benchmark in any domain". The flagship output is a coverage and gap matrix. Put
those together with an English-first source catalogue and the project publishes **its own language
bias as the field's gaps** — the exact error [12-analytics-and-trends.md](12-analytics-and-trends.md)
§5.4 category 3 exists to prevent, arriving through a channel `curation_confidence` does not
currently measure. A Chinese-speaking reviewer who opens the reasoning or agents rows and finds no
CompassHub entries does not conclude that our coverage is English-first; they conclude the index is
unserious, and they are not wrong to.

The evidence that this is real rather than hypothetical is already in the corpus and undrawn:
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3 records HuggingFace `language:` tag
counts across leaderboard Spaces (english 29 + 22, polish 6, japanese 4, korean 4) and states no
conclusion; OpenCompass appears exactly once in sixteen documents, in
[13-execution-runners.md](13-execution-runners.md) §1.1 as a *harness*, and is in neither `06`'s
master source catalogue nor its "sources we will not build" table — so it is currently neither
included nor excluded, which is the one state a source catalogue must never leave a source in.

**Recommendation, in four parts, none of which is "index everything".**

1. **Say it on the site, in the methodology page and on the gap matrix itself.** The v1 caveat is:
   *"Sourcing is English-first. Non-English benchmark ecosystems — principally the Chinese-language
   ecosystem around OpenCompass/CompassHub — are under-indexed, and gap claims in rows where that
   ecosystem is active are suppressed rather than asserted."* An honest, dated, specific statement of
   a limitation costs nothing and is the difference between a bias and a lie.
2. **Make it measurable rather than confessed.** Add a `source_language` observation to the entry's
   provenance and report the language distribution of the corpus on the hygiene dashboard beside the
   machine-ingested share ([12-analytics-and-trends.md](12-analytics-and-trends.md) §8). A stated bias
   with no number attached is a disclaimer; with a number it is a metric that can improve.
3. **Put OpenCompass/CompassHub in the source catalogue, at Tier 2, with one adapter.** It is the
   single highest-yield non-English surface, it is Apache-2.0 *(unverified — the licence is
   self-reported in the project's own README and must be confirmed before ingest)*, and one adapter is
   a bounded cost against an unbounded credibility exposure. If it is decided against instead, it goes
   in `06`'s "will not build" table **with the reason**, because an unlisted source is an
   undocumented editorial judgement, which is constraint 4 broken from the inside.
4. **The reviewer trigger:** recruit a reviewer who reads Chinese at the same point the Gap Finder
   first asserts a gap in a row where the Chinese-language ecosystem is active. Not before — it is one
   more three-month lead time on a list that already has seven — and not after, because that is the
   moment the bias becomes a published claim rather than a private shortfall.

**What this deliberately does not do.** It does not promise parity, and it does not open a
translation workstream. Sizing the whole of part 3 is one adapter plus one reviewer; sizing "index the
non-English world properly" is a second project, and pretending otherwise is how a scope statement
becomes decorative.

**If overturned:** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) source catalogue and
the "will not build" table, [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3
`curation_confidence` and §8 hygiene metrics, [00-vision-and-scope.md](00-vision-and-scope.md) §6
assumption A9.

---

## C. Needed by Phase 3, or before public v1

### C1. Accepting vendor-submitted claims.

**The question.** Do we accept result claims submitted by the organisation that built the system?

**Why it matters.** Refusing them creates gaps, because for many frontier systems the vendor's own
report is the only public number. Accepting them uncritically turns the index into a marketing
channel, which is the failure mode that would end its usefulness fastest.

**Recommendation: accept them, badge them `self-reported`, hold them to the same sourcing and
conditions requirements as anything else — and add one hard rule the archive did not have.** A
vendor-submitted claim with no `artifact_url` (transcript or log) and no archived source may be
listed in browse views but never enters a comparison view. The verification ladder and
`independence_flags` already do the work an access policy would do worse; the artifact rule is what
stops "trust us" from sitting next to a reproducible number as though they were peers.

Note the case where we can do nothing: Scale's SEAL leaderboards use private prompt sets and state
that models are featured only the first time an organisation encounters the prompts
(`_workflow/recon/recon_landscape.md`, read 2026-09-17 — *unverified; confirm the current wording on
their site before quoting it publicly*). That is deliberately unreproducible by design, and the
correct response is to link out and say so on the entry, not to launder it into a claim.

**If overturned:** [04-data-model.md](04-data-model.md) verification ladder,
[10-visualization.md](10-visualization.md) comparison workbench filters.

### C2. Bibliographic data source.

**The question.** OpenAlex, Semantic Scholar, or Crossref — for what?

**Why it matters.** Citation counts and venue data feed the ecosystem analysis and the "who builds
benchmarks" views, and a quietly wrong number there is exactly the kind of failure that destroys a
trust-based index. The archive's answer (OpenAlex, for licensing simplicity) is now only half
right, because the ground moved.

**Recommendation: split the job three ways, and never surface a single-aggregator citation count as
a headline number.**

| Job | Source | Why |
| --- | --- | --- |
| Institution and ROR resolution, topic concepts | **OpenAlex bulk snapshot** | CC0, free, "download, share, remix"; the institutions data is the good part |
| arXiv → paper identity resolution | **Semantic Scholar, with a key** | Native `arXiv:` external ID; no DOI guessing |
| DOI → metadata | **Crossref**, with `mailto` | Polite pool, no key |
| Discovery | **Neither** | `query.title=SWE-bench` on Crossref returns 23,851 results, topped by *"SWE-bench Goes Live!"* |

Three live corrections the plan must carry. OpenAlex moved to a metered, key-required API
(announced Jan 2026, enforced around 2026-02-13); a live unauthenticated measurement returned
`X-RateLimit-Limit: 1000` credits and `X-RateLimit-Limit-USD: 0.1` per day, while OpenAlex's own
blog states $1/day with a free key and their docs repo still says 100,000 credits/day — **three
different numbers, so get a key and measure before sizing anything (unverified)**. Semantic
Scholar's unauthenticated tier is effectively dead (429 on a first cold request); the keyed
introductory limit is 1 RPS, which backfills 5,000 benchmark papers in about 90 minutes and is fine
for a cron and useless for a page view. The S2 bulk-dataset licence is documented as ODC-BY 1.0 but
that is **unverified for 2026 — read it before ingesting bulk**.

And the reason for the "never a headline number" rule, which is worth repeating in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) verbatim: OpenAlex record `W4387561453`
carries the correct SWE-bench DOI, the correct authors and the correct publication date, with a
**wrong title** and a `cited_by_count` of 53 — off by orders of magnitude. Any figure from a single
aggregator renders with a visible "single source, unverified" marker.

**If overturned:** [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md),
[12-analytics-and-trends.md](12-analytics-and-trends.md) ecosystem metrics.

### C3. Handling systems that no longer exist.

**The question.** Deprecated API models cannot be re-verified. What happens to their claims?

**Why it matters.** Historical accuracy and current relevance are different jobs, and conflating
them produces either a SOTA table full of models nobody can call, or trajectory charts with holes
in them.

**Recommendation: retain with an explicit availability state, exclude from "current SOTA", keep in
trajectories — and model availability as a *temporal* fact orthogonal to the access facts `04`
already carries.** An earlier revision proposed a three-value `system_status` of `available`,
`api_retired`, `weights_available`. That collapses two axes that [04-data-model.md](04-data-model.md)
deliberately keeps apart: `System.open_weights` and `System.license_class`
(`api-access | hosted-no-api | open-unrestricted | open-restricted | open-noncommercial | unreleased`)
already say *how* a system can be obtained. What is missing is only *whether it still can be*, and
a third status field that re-encodes licence class is the drift this pass exists to remove.

**New field: `System.availability: available | retired | unknown`, plus `retired_on: date`**, to be
added to [04-data-model.md](04-data-model.md) §15. It is orthogonal to `open_weights` and
`license_class`, and the property the analytics layer actually needs is *derived* rather than stored:

```
reproducible_today = (availability == available) or (open_weights == true)
```

That derivation is the whole reason the axes must stay separate — a retired API model is
unreproducible while a retired *product* with open weights is still fully reproducible, and one
status field cannot express both. `SystemVersion.deprecated` stays as the per-version fact;
`availability` is the system-level rollup. Epoch's `model_metadata.csv` carries an `accessibility`
column that seeds `license_class`, not `availability`, and conflating the two at ingest is the
specific mistake to avoid.

The same question applies to benchmarks, and there the answer is a differentiator rather than a
housekeeping rule — but it uses the fields that already exist: **`lifecycle`**
(`proposed · active · mature · saturated · under-revision · contaminated · superseded · deprecated ·
retracted · dormant`, [02-taxonomy.md](02-taxonomy.md) Facet 6) driven by the observable
**`liveness`** block in [04-data-model.md](04-data-model.md) (`repo_last_commit`,
`leaderboard_last_updated`, `reproduction_script_present`, `reproduction_script_verified`,
`last_checked`) — **and, between the two, `maintenance_status`, which an earlier revision of this
entry wrongly declared not to be a field.** The withdrawal is recorded in the edits table below. The
three are a chain, not competitors: `liveness` is the raw observation, `maintenance_status`
(`actively-maintained · slow · stale · abandoned · unobservable`,
[02-taxonomy.md](02-taxonomy.md) §8) is the derived verdict over it, and `lifecycle` is the
instrument's standing, which is a different question and contains none of those five terms. The one
edit that follows is to [04-data-model.md](04-data-model.md), which carries the `liveness` block and
should carry the derived field too.

The evidence that nobody else does this is strong: one study found 137 of 195 safety benchmarks had
stale GitHub repos and 96 of 195 had stale HuggingFace datasets, and BetterBench found 17 of 24
assessed benchmarks had no easy-to-run reproduction scripts. The safety-benchmark figures come from
**arXiv 2604.12875, which was withdrawn on 2026-04-23** — the measurements survive and are cited on
that basis by both [01-landscape-and-positioning.md](01-landscape-and-positioning.md) and
[12-analytics-and-trends.md](12-analytics-and-trends.md), which owns the citation, and a withdrawn
preprint is exactly the kind of source this project must cite with its status attached rather than
laundered. No catalogue the landscape reconnaissance examined marks a benchmark as dead
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1 states how far that claim is
supported and what one counterexample would do to it).

**If overturned:** [04-data-model.md](04-data-model.md) System entity and §15,
[12-analytics-and-trends.md](12-analytics-and-trends.md) SOTA definitions.

### C4. At what threshold may a machine-ingested claim enter a comparison view?

**The question.** New, and forced by the Epoch decision. Bulk-ingested claims are visible and
searchable by design. When are they allowed to be *compared*?

**Why it matters.** This is where the credibility of the whole project is decided in a single
constant. Set it too low and the comparison workbench becomes a leaderboard aggregator built on
6,598 rows of "number, model, benchmark, no conditions" — which is the artifact this project
explicitly said it would not build. Set it correctly and the workbench will look nearly empty at
launch, which is uncomfortable and correct.

**Recommendation: `condition_completeness ≥ comparison_floor` AND verification at
`maintainer-verified` (rung 2) or better AND a resolvable archived source.**

Two corrections to the earlier revision, both of which made this rule unimplementable as written.

**First, the verification rung.** The earlier text required `reported-with-source`, which is not a
rung of anything. [04-data-model.md](04-data-model.md) §*The verification ladder* defines seven:
`self-reported` (1), `maintainer-verified` (2), `independent-reproduction` (3), `held-out-server`
(4), `prospective-experiment` (5), `third-party-audited` (6), `sandboxed-rerun` (7, deferred). The
constant this document calls "where the credibility of the whole project is decided" was pointing at
a level that does not exist. It is **`maintainer-verified`**: rung 1 is the evaluated party's own
word, which is precisely what a comparison view must not treat as comparable, and rung 2 is the
lowest rung at which someone other than the claimant has stood behind the number.

**Second, there are two completeness constants, not one, and they were drifting.** Four values were
in circulation for the same field: 0.3 for the frontier line
([12-analytics-and-trends.md](12-analytics-and-trends.md) §3.3), 0.35 for hiding machine-ingested
claims in comparison views ([05-repository-and-workflow.md](05-repository-and-workflow.md) open
items and [10-visualization.md](10-visualization.md)), 0.4 here, and a rhetorical 0.5 in
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md). **Decision: two named constants
with two different jobs, stored once in `taxonomy/thresholds.yaml` and documented canonically in
[12-analytics-and-trends.md](12-analytics-and-trends.md), which already owns the derived-metric
defaults and publishes them on the page:**

| Constant | Value | Job |
| --- | --- | --- |
| `frontier_floor` | **0.3** | Minimum completeness for a claim to contribute to a SOTA/frontier series. A trend line tolerates thinner conditions because it is a shape, not a comparison |
| `comparison_floor` | **0.4** | Minimum completeness for a claim to enter a side-by-side comparison view. Higher, because a comparison asserts that two numbers mean the same thing |

`05`'s and `10`'s 0.35 becomes `comparison_floor` and is therefore 0.4; `07`'s 0.5 becomes a
reference to `comparison_floor` rather than a fourth number. **Status:**
[12-analytics-and-trends.md](12-analytics-and-trends.md) §1.4 now declares both constants, names
`taxonomy/thresholds.yaml` as their home, states why they differ and schedules their recalibration at
~200 hand-curated claims, and [11-ai-features.md](11-ai-features.md)'s F5 gate references
`comparison_floor` by name. Still outstanding: `04`'s tier-4 quality warning still carries a literal
0.3, and `05`, `07` and `10` still carry literals. See the edits table below. The reason for two
constants rather than one is worth stating because "just pick one" is the tempting answer: a single
constant would either let thin claims into comparison or delete most of the frontier lines, and
those are different mistakes with different costs.

Expect that essentially none of the Epoch rows qualify — their expected mean completeness is around
0.10, and across all 6,598 rows the fields `chain_of_thought`, `shot_selection`, `temperature`,
`top_p`, `seed`, `retries_allowed`, `judge_model` and `decontamination_applied` have **zero
coverage** (`_workflow/recon/recon_epoch-assets.md`, 2026-09-17). That is the honest outcome, and
the fix is curation, not a lower bar.

The mitigation for the empty-workbench problem is already settled elsewhere and is worth restating
here because it is what makes this threshold survivable: hand-curate 50–80 LLM claims chosen
*adversarially* rather than representatively — one model family across several reasoning efforts
fully specified, one benchmark where sources disagree with every source archived, one benchmark
across several scaffolds. That single cluster demonstrates the entire thesis in ten seconds, and
bulk data cannot do it at any volume. `14`'s Phase 3 gate is the number that matters here: **≥130
claims at `condition_completeness` ≥ 0.6, each with a named source and an archived URL, of which
≥60 are from non-LLM domains** ([14-roadmap.md](14-roadmap.md) Phase 3 exit). Note that 0.6 is
deliberately *above* `comparison_floor`: the gate is a statement about the quality of our own
curation, while `comparison_floor` is the admission rule for everything including ingested rows.
The archived plan's "500 result claims" is dead, and `14` says why in terms — a single adapter run
clears it thirteen times over, so it measures download speed rather than work. Two documents still
carry the archived 500 ([04-data-model.md](04-data-model.md),
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md)) and should point at `14`'s
restatement instead.

**If overturned:** [04-data-model.md](04-data-model.md),
[10-visualization.md](10-visualization.md) comparison workbench,
[12-analytics-and-trends.md](12-analytics-and-trends.md) trust metrics and threshold declarations,
[05-repository-and-workflow.md](05-repository-and-workflow.md) and
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).

### C5. Sustainability and the succession story.

*Deadline: before public v1. Moved here from the longer-horizon section, where a pre-v1 deliverable
does not belong.*

**The question.** Static hosting is nearly free; curation time is not. What is the plan for the day
attention runs out — and what does the artifact do on its own after that?

**Why it matters.** This is not a risk-register line. It is a design input, and it is the most
important piece of intelligence in the whole landscape analysis. Every cross-domain AI catalogue
attempt to date has died within 12–24 months: Ecosystem Graphs (dead 2025-01, no licence, therefore
unforkable); Papers with Code (killed by its owner, benchmark layer never replaced); llm-leaderboard
(converted to a closed site over contribution friction); HELM (maintenance mode 2026-06-01);
HuggingFace's Open LLM Leaderboard (retired 2025-03-14 after 13,000+ models, with the stated reason
that it "was becoming obsolete and could encourage people to optimize in irrelevant directions");
BIG-bench (archived 2026-04-17); Evidently's 250-benchmark database (abandoned after seven months as
a lead-gen asset); BetterBench (still 24 benchmarks, still calling itself a "living repository");
Princeton HAL (submissions paused within a year of publication). Academic evaluation infrastructure
has roughly a three-to-four-year half-life tied to grant cycles and student turnover.

**Recommendation: write `SUCCESSION.md` in the first month, prepay the domain, and make staleness
automatic.**

The document states literally what happens when we stop: the repository stays public and CC-BY; the
last release's Zenodo DOI remains citable forever; a dated `STATUS: unmaintained since
YYYY-MM-DD` file is committed and rendered site-wide by the build; and a named list of fork-ready
successors (per-domain maintainers first) is maintained alongside it. It also names the **depositor
of record** by GitHub handle and ORCID ([A10](#a10-what-is-the-legal-and-financial-vehicle)),
because a DOI whose depositor cannot be identified is a DOI nobody can transfer.

**Prepay the domain for the longest term the registrar offers — ten years for `.org`** — and record
the expiry date in `SUCCESSION.md`. This is the single succession commitment that can be *funded
now* rather than promised, and it costs a hundred-odd dollars once
([A10](#a10-what-is-the-legal-and-financial-vehicle)). "The domain is pointed at the GitHub
repository rather than left to lapse into a squatter" is otherwise a promise that by construction
requires attention from someone who has stopped paying attention, which is not a plan. State the
fallback plainly too: when the prepayment does run out, the citable artifact is the Zenodo DOI and
the GitHub (plus Codeberg mirror and Software Heritage) copies, none of which depend on the domain —
which is why `CITATION.cff` cites the DOI and not the URL.

The operational half matters more than the document, because by definition nobody will be there to
act on the document. **The site must go stale visibly, by itself.** Build rule: if the newest commit
touching `data/` is older than 180 days, the build renders a site-wide staleness banner with the
date, automatically, with no human action required. Per-entry, the same principle already exists as
`last_verified` and the re-verification queue. A catalogue that rots silently is worse than no
catalogue, because it launders staleness into apparent authority — and Ecosystem Graphs proves the
harm is not hypothetical.

On funding: decide before Phase 4 rather than after burnout. The options are a grant, an
institutional home, or deliberately reduced scope, and all three work. Drifting without choosing
does not. Given [E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation) and
[A10](#a10-what-is-the-legal-and-financial-vehicle), the realistic path is reduced scope plus an
institutional home, and the plan should be sized for that rather than for a grant that may not
arrive.

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md),
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) staleness rules,
[14-roadmap.md](14-roadmap.md) risk register.

### C6. Do we run analytics at all, and if so what?

*New. It was an unasked question underneath a commitment that could not be honoured.*

**The question.** Does the site collect any usage data, and if so what, stored where, disclosed how?

**Why it matters.** Three things depend on the answer and one of them already assumed it.
[A9](#a9-what-is-our-commitment-if-an-upstream-source-we-depend-on-sunsets) previously committed to
re-deriving "the entries with the highest page views", which the site cannot measure — there is no
auth, no accounts, and no analytics anywhere in the plan. Separately,
[E4](#e4-publication-and-outreach-at-public-v1-and-do-we-want-an-academic-paper) will want to know
whether anyone is reading the thing, and [E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation)
commits us to publishing independence disclosures about ourselves. A project that publishes
`independence_flags` about other people's evaluations and runs undisclosed telemetry has spent
exactly the credibility it is trying to accumulate.

**Recommendation: yes, minimal server-side aggregate analytics; no client beacon, no cookies, no
per-visitor identifiers, no third-party script; published publicly.**

The mechanism, concretely: take the request metrics the Cloudflare Workers account already produces
for the hosting decision in [08-infrastructure-and-build.md](08-infrastructure-and-build.md), export
them monthly, and **commit them to the repository as `analytics/YYYY-MM.json`** containing only
total requests, requests per path prefix, the top 20 referrer hosts, and country-level counts.
Render them at `/independence` beside `funding.yaml`. Nothing is stored per visitor, so there is
nothing to leak, nothing to subpoena and nothing to disclose beyond the file itself.

Three explicit refusals. **No Google Analytics or equivalent**, because a third-party tracker on a
reference site is the cheapest possible way to lose the trust position. **No Cloudflare Web
Analytics beacon either**, despite being free and cookieless: it is a client-side script, and it
would be the first third-party JavaScript on a site whose citable pages are specified to ship zero
JavaScript ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.3). **No
per-visitor identifier of any kind**, including hashed IPs.

*Unverified: whether Workers Static Assets exposes per-path request counts on the free plan —
confirm in the Cloudflare dashboard before promising the per-path breakdown, and fall back to
total-requests-only if it does not.*

The consequence for [A9](#a9-what-is-our-commitment-if-an-upstream-source-we-depend-on-sunsets) is
already applied there: the re-derivation queue is ranked by inbound source references and claim
count, which the build computes, and request counts are a tiebreak at most. The general rule this
question establishes: **a commitment whose input the plan cannot compute is not a commitment.**

The honest cost: aggregate counts cannot tell us which *entry* someone found useful, only which
path prefix was requested, so we will never have the reader-level insight a tracker would give. That
is accepted, and it is the same trade as [E3](#e3-do-we-accept-sponsorship-or-institutional-affiliation) —
hold ourselves to a visibly stricter standard than we apply to others.

**If overturned:** [08-infrastructure-and-build.md](08-infrastructure-and-build.md) hosting and
artifacts, [05-repository-and-workflow.md](05-repository-and-workflow.md) repository layout,
[09-design-system.md](09-design-system.md) (a beacon would change the zero-JS guarantee).

### C7. What is the response to a legal threat over a published liveness, contamination or independence signal?

*New. The project publishes evidence-linked claims about third parties and had no stated answer for
the day one of them objects in writing.*

**The question.** A vendor's or a benchmark maintainer's counsel writes to a two-person project with
no legal budget, objecting to `lifecycle: dormant`, a contamination flag, an
`independence_flags` entry or a saturation finding. Who decides what happens, and what is the
standing answer?

**Why it matters.** Publishing `lifecycle: deprecated` about somebody's benchmark, or a
contamination risk about somebody's evaluation, is the differentiator
([C3](#c3-handling-systems-that-no-longer-exist)) — and it is also the thing most likely to generate
a letter. The failure mode is not the letter; it is the *panic*. A project with no pre-committed
response deletes the entry, and a silent deletion is indistinguishable from a correction, which
destroys the audit trail that is the entire architecture. The second failure mode is looking for a
lawyer with a deadline running.

**Recommendation: five pre-committed rules, and one contact found in advance.**

1. **Every liveness, contamination and independence signal must cite an observable artifact and
   render its evidence inline.** Not "dead" but `liveness.repo_last_commit: 2024-03-11`, with the
   URL and the fetch timestamp on the page. A rendered observation with its source attached is a
   much harder thing to object to than an adjective, and the schema already stores exactly that. The
   derived word (`dormant`) is always shown next to the dates that produced it.
2. **The standing answer to a complaint is "submit a dispute; we will render your position beside
   ours."** The mechanism exists and is settled:
   [05-repository-and-workflow.md](05-repository-and-workflow.md) §8 — `dispute.yml`,
   `data/disputes/`, both positions rendered, `disputant_relationship` shown, never resolved by
   deletion, and an evaluated party treated exactly like a stranger.
3. **Nothing is deleted under threat without a written rationale committed to the repository.** If
   we were wrong, the fix is a commit with a `Correction:` trailer, which appears on `/corrections`
   with what it said before. If we were right, the dispute renders. There is no third path, and
   "quietly remove it and hope" is the path that ends the project's usefulness.
4. **Disputes and their outcomes are logged publicly**, including the ones we lose. A dispute log
   with no adverse outcomes in it is a dispute log nobody believes.
5. **Identify one pro-bono or academic counsel contact before public v1.** Candidate routes: a
   university law clinic with a technology-law practice; the referral routes that open-data and
   free-software organisations maintain; or the legal contact attached to whichever institutional
   home [C5](#c5-sustainability-and-the-succession-story) pursues. **All three are unverified as to
   availability for a project of this shape — confirm one before v1**, because the failure mode is
   finding counsel under a deadline, and that is a search that takes weeks when you have days.

**Who decides:** the founding maintainer in year one, per
[A11](#a11-governance-beyond-one-maintainer-what-happens-when-the-first-outside-contributor-wants-commit-rights)'s
tie-break, and the decision is recorded as an ADR whichever way it goes — this is precisely the
class of decision that earns an ADR under this document's revised ADR policy.

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md) §8 and §11 legal
posture, [12-analytics-and-trends.md](12-analytics-and-trends.md) liveness and contamination
metrics, [00-vision-and-scope.md](00-vision-and-scope.md) principles.

---

## AI. Needed before the AI phase

*Labelled `AI1`–`AI4` rather than `D1`–`D4`, because `D1`–`D4` name the four adjudicated decisions
of 2026-09-21 in `_workflow/decisions/` and must not be shadowed.*

### AI1. Does the AI layer justify breaking the pure-static constraint with a single serverless function?

**The question.** The architecture is static-first with near-zero operating cost, no auth and no
accounts. The AI layer needs an API key that cannot ship in a bundle. Do we add one serverless
function, or do we refuse and keep the site purely static?

**Why it matters.** This is a genuine architectural fork with real consequences, and it is the kind
of decision that is made casually and regretted structurally. Once there is a server, there is a
temptation to move retrieval behind it, then to cache "enriched" fields, then to write model output
back into the store — at which point unsourced data is in the corpus and the project's premise is
dead. The fully server-side alternative does not merely cost more; it changes what people cite from
"the YAML at a commit" to "whatever the server had".

**Recommendation: yes, one Cloudflare Worker — under four conditions, each enforced by a mechanism
rather than by a promise.**

1. **The AI layer cannot write to `data/`, as an access-control fact and a branch-protection fact.**
   Two mechanical statements, because an earlier revision said "CI asserts a human committer for
   every path under `data/`", which is both the wrong layer and actively broken: the settled
   contribution path has the **bot** author every issue-form commit under `data/` with a
   `Co-authored-by: <contributor>` trailer ([05-repository-and-workflow.md](05-repository-and-workflow.md)
   §6), so a human-committer assertion would fail every single one of them. What actually holds:
   **(i)** the Worker's service account has no write credential to the data repository at all — it is
   issued a read-only token, which is an access-control fact, not a check that can be skipped; and
   **(ii)** every pull request touching `data/` requires one human approval under branch protection
   with no bot bypass, which `05` §6 already specifies. The ingestion adapters and the issue-form
   bot are permitted authors; the AI Worker is not an author at all. The CI check that *is*
   checkable, and should be added: **no path under `data/` may carry `provenance: ai-worker`**, which
   is a grep, not an inference about identity.
2. **Every AI response carries a footer** with `model_id`, `prompt_version` hash, **`index_commit`
   SHA**, the facet query JSON, and the retrieved entry IDs.
3. **The permalink encodes the query, not the answer**, so a durable URL replays deterministic
   retrieval with the prose as a disposable overlay.
4. **AI prose is explicitly marked non-citable**; the citable, DOI'd object remains the YAML at a
   commit.

Two facts make this cheaper than it sounds. The hosting decision already moved to Cloudflare
Workers with static assets for unrelated reasons (static asset requests are unbilled, and GitHub
Pages has no serverless path), so the marginal *operational* cost of the Worker is close to zero —
the cost being paid here is conceptual. And Worker CPU time is reported to exclude time awaiting
`fetch`, so a 20-second model call costs almost nothing in CPU and the $5/month plan lasts far
longer than intuition suggests *(measured by the AI-features recon on 2026-09-17 against
Cloudflare's published billing model; unverified — confirm against current Workers pricing before
sizing on it)*.

**On cost, one sentence and a pointer, because a second copy of a cost table is a second copy that
drifts.** The AI layer runs on the order of **$23/month at 1,000 queries, rising to roughly
$1,786/month at 100,000 before caching**; the per-feature token tables, the model IDs, the traffic
model and the cached figures live in [11-ai-features.md](11-ai-features.md) §*Monthly budget*,
which owns them, and `11` itself marks its totals unverified and notes that its own architecture
section and cost table disagree by 10–20%. One constraint is worth carrying because it is a hard
ceiling rather than an estimate: **the Anthropic Console's account tier imposes a monthly spend cap,
reported as $500 on the Start tier and $1,000 on Build** — *this figure appears only in
`_workflow/recon/recon_ai-features.md` and in `11`, is not documented in the API reference material
available to this pass, and is therefore unverified; confirm the account tier's spend cap in the
Console before enabling synthesis at volume.* Set a self-imposed spend limit below whatever the tier
cap turns out to be, and note that [A10](#a10-what-is-the-legal-and-financial-vehicle)'s $750/year
cap binds long before any tier cap does.

**The trigger for revisiting.** If the Worker is ever required to render a benchmark page, or if
any build artifact depends on a Worker response, the fork has been crossed and must be reverted
before anything else ships. That is the tripwire; write it into the CI description so it is checked
rather than remembered. The site must remain fully useful, readable and citable with the AI layer
entirely switched off — degrading to facet filtering plus lexical search, never to an error.

**If overturned:** [11-ai-features.md](11-ai-features.md) architecture,
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) hosting,
[00-vision-and-scope.md](00-vision-and-scope.md) principles,
[05-repository-and-workflow.md](05-repository-and-workflow.md) CI and branch protection.

### AI2. Where does the query embedding happen? (The reports disagree.)

**The question.** Semantic search needs the query embedded in the same space as the corpus. Does
that happen in the browser or in the Worker?

**Why it matters.** It determines whether semantic search survives the Worker being down, and it
determines whether a first-time visitor downloads tens of megabytes to use a search box.

**This is a point where two research inputs conflict, and the conflict is recorded rather than
resolved by preference.** The technology correction says to use static embeddings (model2vec /
potion-style) rather than running a transformer in the browser. The AI-features research reached
the same conclusion about transformers — `Xenova/all-MiniLM-L6-v2` at roughly 23 MB quantised and
`bge-small-en-v1.5` at roughly 33 MB are real UX costs even with IndexedDB caching *(sizes
unverified — secondary sources; measure before committing)* — but found that **no JS or browser
package for model2vec exists** as of 2026-09-17, only Python and Rust, and therefore recommended
embedding the query server-side with Voyage `voyage-4-lite`. Both agree on what *not* to do. They
disagree on what replaces it: a hand-ported static-embedding lookup in JavaScript, versus a Worker
call.

**Recommendation: client-side static embeddings as the primary path; Worker-side Voyage as
fallback #1; lazy MiniLM as fallback #2.** This matches [11-ai-features.md](11-ai-features.md)
§*The embedding decision*, which **owns** this call and resolved it this way, and
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5, which lists Worker-side Voyage
as the fallback in its technology table. An earlier revision of this register recommended the
opposite, and it was wrong on the argument, not merely out of step:

- **The deciding argument is the governing rule, not cost or latency.** A Worker-side query encoder
  makes dense retrieval *unavailable offline*, and the AI layer's governing rule requires that
  retrieval work with the Worker entirely offline. With static embeddings, both the document matrix
  and the query encoder are static artifacts at a commit hash, so semantic retrieval is
  bit-reproducible by a third party with nothing but the repository — the same property we demand of
  the data, which is the whole point of the project.
- **It is not unbudgeted.** `11` sizes the encoder at roughly 150 lines of JavaScript against
  `@huggingface/tokenizers` and a `Float32Array` — "a day of work, not a project" — and schedules it
  in the AI-0 step at 1–2 days, with a measured stack (36 KB tokenizer, pruned `potion-base-8M` int8
  at ~3 MB, 1,500 × 256 int8 document matrix at 0.38 MB, ~1–2 ms per query). Calling it unbudgeted
  was the factual error that produced the wrong recommendation.
- **The Voyage fallback is more expensive than it looks**, which is the second reason not to make it
  primary: it needs a *second* corpus matrix (1,500 × 512 int8, ~0.77 MB) because query and document
  embeddings must come from the same model, and mixing spaces returns garbage silently rather than
  erroring.

Do not restate Voyage's per-query price here. The two recon reports quote two different figures for
it ($0.0000006 in the architecture section, $0.0000008 in the cost table of the same document), and
`11` §*The embedding decision* owns the number and the pricing terms.

Two guardrails, unchanged and both still right:

- The always-on floor is facet filtering plus MiniSearch BM25 (5.9 kB gzipped, per
  [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5, which owns the pin and the
  size), which needs no network and no model. When anything above it is unavailable, search degrades
  from hybrid to lexical, not from working to broken.
- Commit the embedding model ID **and the exact input text used per entry** alongside the matrix,
  so the corpus can be re-embedded with a different model without re-deriving the inputs. This is
  the dependency hedge, and it applies to the static model too: a pruned `potion` matrix is a
  third-party artifact like any other.

And the thing neither report disputes, worth restating because it saves real work: at 1,500 entries
brute-force cosine over a `Float32Array` measures **0.61 ms at our 256 dimensions** (0.75 ms at 384,
the recon's conservative headline). Do not ship HNSW, a vector index, or a vector database. A typed
array and a loop is both the correct engineering answer at this scale and the auditable one. Note the
counterintuitive half, because getting it backwards costs three times the query budget: **the int8
dot loop is *slower*, at 2.0 ms**, because V8 does not auto-vectorise and the int-to-float conversions
cost more than they save. **int8 is a transport format only** — quantise for the wire, dequantise once
into a `Float32Array` at load ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5
owns all three timings).

**Trigger to build the Voyage path:** the JS encoder exceeds two days of work, or the turnkey
model2vec export path (transformers.js issue #970, closed 2026-04-12, *unverified*) turns out not to
produce a usable matrix. Then Voyage ships as an *enhancement* alongside the static path, never as
the floor.

**If overturned:** [11-ai-features.md](11-ai-features.md) retrieval pipeline,
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) build artifacts and technology
table.

### AI3. Do we publish our own AI layer's evaluation, including the test split?

**The question.** A benchmark index whose own AI layer is benchmarked is an obvious move. Do we do
it, and do we publish the held-out split?

**Why it matters.** It is the cheapest credibility artifact available and it dogfoods the schema —
if the schema cannot describe our own evaluation, it is not good enough. The tension is that a
*public* test split can be optimised against, which is the exact contamination problem this index
exists to document, and a *private* test split contradicts the transparency posture that the whole
project sells.

**Recommendation: build it, publish everything including the test split, and be honest about what
rotation can and cannot do.** Ship the golden set as a first-class CC-BY versioned artifact in the
repo, with an entry in the index describing itself. Roughly 150 items in four splits:

| Split | n | Primary metric | Target |
| --- | --- | --- | --- |
| `nl_search` | 60 | Recall@20 on grade-3 items | ≥ 0.90 |
| `facet_translation` | 40 | per-facet macro-F1 | ≥ 0.85 |
| | | over-constraint rate | ≤ 0.05 |
| | | **enum-hallucination rate (canary)** | **= 0.000** |
| `suite_build` | 30 | must-include coverage | ≥ 0.85 |
| | | **forbidden-inclusion rate** (deprecated / contaminated / licence-incompatible) | **= 0.000** |
| `abstention` | 20 | correct-abstention rate | ≥ 0.95 |

Run the full set through the Batch API (a 50% discount on synchronous pricing) on every
prompt-version, model-ID, schema or index change — about $7.50 synchronous, about $4 batched per
run, per [11-ai-features.md](11-ai-features.md), which owns the figure. Publish results as
`evals/<date>-<commit>.json` with a public trend page.

**On the split question, stated plainly rather than dressed as a control.** Publish it all. And say
this in the artifact, in these terms: **our own eval set is permanently contaminated by publication.
The rotation log exists so a reader can see which items are fresh, not to prevent optimisation
against the set.** An earlier revision presented "rotate ten items per quarter" as a mechanism that
makes optimisation "decay on a known schedule". Ten of 150 per quarter is a 3.75-year full refresh —
longer than the plan's own horizon, and slower than any plausible optimisation. Presenting it as a
defence was the kind of unsourced confidence this project exists to oppose.

Given that, the rotation rate is set by what makes the *freshness label* meaningful rather than by
what would make the set clean:

- **Rotate 15 items per quarter** (60/year, ≈2.5-year full refresh on a 150-item set), with the
  rotation log committed.
- Every item carries `added_in` and `retired_in`, so **the fresh fraction is computable and printed
  on the trend page** next to every score. A reader can then discount the figure by exactly the
  amount the contamination warrants, which is the only honest thing on offer.
- **The labelling cost, stated because a rotation policy with no cost attached is a policy that
  stops in quarter two — and stated with its mix, because the cost is a function of the mix and an
  earlier draft gave a range no mix reproduces.** Rates: 10–20 minutes per `nl_search` or
  `facet_translation` item, 30–45 minutes per `suite_build` item. **Rotate in the splits' own
  proportions** — the set is 100 cheap items and 30 `suite_build` items out of 130 scored splits, so
  15 rotated items is **12 cheap plus 3 `suite_build`**: `12 × 10 min + 3 × 30 min = 3.5 h` at the
  low end and `12 × 20 min + 3 × 45 min = 6.25 h` at the high. So **3.5–6.5 hours per quarter,
  14–26 hours per year.** Rotating in proportion is also the right policy on its own terms: rotating
  the cheap items preferentially would make the fresh fraction look healthy while the expensive split
  — the one that actually tests the flagship feature — never turned over. That cost is charged to the
  AI phase, not to curation.
- **Who labels:** the maintainer. The model may propose candidate queries and must never produce the
  gold label — the same rule as [AI1](#ai1-does-the-ai-layer-justify-breaking-the-pure-static-constraint-with-a-single-serverless-function)
  condition 1 and the governing rule that the model never produces a number.
- `11` additionally holds out a 30-item test split that is scored but never used for prompt tuning,
  and publishes train and test separately so hill-climbing is visible on the trend page. That is
  `11`'s rule and it stands; publishing the split is not the same as tuning against it.

Note the honest caveat the project must publish about itself: the judge is a Claude model and so is
the generator, so self-preference bias is present and unmeasured. Only deterministic metrics gate a
release; the LLM-judged rationale-quality score is reported and never used as a gate.

**If overturned:** [11-ai-features.md](11-ai-features.md) evaluation,
[14-roadmap.md](14-roadmap.md) AI-phase exit criteria.

### AI4. The custom-benchmark fork: suite assembly, or authoring new benchmarks?

**The question.** The user's phrase was "users can build their own custom benchmark". That has two
readings. **Suite assembly**: help someone select the right set of *existing* benchmarks for their
system and export a manifest with links and recommended conditions. **Authoring**: help someone
create new benchmark tasks and data. Which do we build?

**Why it matters.** They look adjacent and are not. Authoring requires hosting or at least
versioning task data, which breaks hard constraint 1 (never host or redistribute benchmark
datasets) and with it the licensing shield that makes every other ambiguity in the ingestion
strategy dissolve. It also requires a contamination-control story — private splits, a submission
server, held-out answers — which is a different product with an on-call obligation attached, and it
inherits a per-task licensing liability we would have no way to discharge.

**Recommendation: suite assembly, and only suite assembly, for v1.** Concretely: a ranked set of
8–14 existing benchmarks for a stated need, each with why it is in, what it does *not* cover,
recommended conditions, a **computed** cost and runtime estimate, and a mandatory "Not covered"
section. Exported as `suite.yaml` in our own CC-BY schema — entry IDs plus the index commit SHA
plus recommended conditions plus comparability keys — with adapters emitting Inspect AI task names,
`lm-evaluation-harness` `--tasks` strings, HELM run-specs, and a plain README with links and
licence notes.

The honest part of the export is the differentiating part: most cross-domain benchmarks have no
harness implementation at all, so every entry carries `runnable_via: [inspect|lm_eval|helm|custom|
none]` and the export header says "3 of 12 runnable from a harness; 9 link to their own repos".
Every other tool in this space implies everything is runnable. Admitting otherwise is a feature.

**What would have to change to revisit authoring.** Three things, all of them: (i) an institutional
host willing to own the data-hosting liability and the licensing review; (ii) the execution layer
in [13-execution-runners.md](13-execution-runners.md) shipped and in real use; (iii) a written
contamination policy for authored items. Until all three hold, authoring stays out.

There is a middle option worth recording and not building: a **benchmark *spec*** artifact — a YAML
that describes a benchmark somebody else builds and hosts, containing no data. That is metadata and
sits comfortably inside constraint 1. It is a deferred idea, not a v1 feature, and it should not be
started before the core index has outside contributors.

**If overturned:** [11-ai-features.md](11-ai-features.md) feature set,
[00-vision-and-scope.md](00-vision-and-scope.md) non-goals,
[13-execution-runners.md](13-execution-runners.md) scope.

---

## E. Longer-horizon and standing

*What remains here is genuinely open-ended or continuously watched. Everything with a phase deadline
has been moved into the phase section that names it.*

### E1. Ingestion aggressiveness.

**The question.** How much automated drafting is acceptable, given that a hallucinated field is
worse than a missing one?

**Why it matters.** The curation treadmill, not the architecture, is what kills projects like this.
Every cross-domain catalogue attempt to date has died within 12–24 months, and none died of
insufficient ambition. But automating field population rather than discovery is how a catalogue
becomes confidently wrong at scale, which is a faster death than staleness.

**Recommendation: automate *discovery* aggressively and *field population* conservatively — the
archive's answer, now with numbers behind it.** Knowing that an entry needs attention is most of
the value; guessing its contents is most of the risk.

On the discovery side, the measured reality: an arXiv keyword prefilter over `cs.CL ∪ cs.LG ∪
cs.CV ∪ cs.AI` yields roughly 100–670 candidates per week (670 papers matched `abs:"benchmark"` in
a 7-day window, which is 29% of all papers in those categories — useless alone; `ti:"benchmark"`
gives 103). Hand-checking 40 titles against a release-verb regex measured **precision ≈ 60% and
recall ≈ 70%**, missing `*Bench` neologisms because arXiv's tokeniser does not split compound
tokens. An LLM triage pass over abstracts is therefore mandatory and gets to roughly 85–90%
precision, at a budget of about 15–95 LLM calls per day. (All of these are the sourcing recon's own
measurements from 2026-09-17 and are owned by
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md); they are a single week's sample and
should be re-measured once the adapter runs.)

On the population side, four rules: numeric result changes are *always* human-reviewed; one PR per
source per run, never one per benchmark, or a two-person team drowns; the PR body is the review
surface, with a rendered diff table the reviewer can approve without opening a file; and exactly
one class auto-merges — pure adoption counters (`github_stars`, `hf_downloads`) into a separate
`metrics/` tree that is *not* part of the citable CC-BY core.

**If overturned:** [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md),
[05-repository-and-workflow.md](05-repository-and-workflow.md) review policy.

### E2. Should the index host anything?

**The question.** This recurs the moment the project has credibility: a leaderboard of record, a
submission portal, an API, a mirror of a dataset "just this once".

**Why it matters.** Each is a different product with a maintenance obligation attached, and each
one is proposed by a reasonable person for a good reason. The constraint that protects the project
is the one that looks most restrictive: metadata and links only, never data. It is simultaneously
the licensing shield (every ambiguity in the ingestion strategy dissolves if we only ever store
facts and links) and the contamination posture.

**Recommendation: we publish static artifacts and an MCP server over them, and we run no service
with an uptime obligation.** The refusal is about *obligations*, not file counts — an earlier
revision said "two static files and an MCP server. Nothing else", which forbade artifacts the plan
already publishes, including the Croissant emitter that
[A8](#a8-do-we-commit-to-publishing-a-croissant-benchmark-extension-and-when) recommends. What is
actually published is [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2's
artifact table — `facets.json`, `corpus.json`, `atlas.json`, `derived/*.json`, `enums.json`,
`vectors.i8.bin` plus its meta, the generated JSON Schemas, and per tagged release `index.sqlite`,
`corpus.csv.zip` and `croissant-benchmark/*` — mirrored to a Hugging Face dataset repo as a second
distribution channel. `08` owns that list and the filenames; this document does not keep a second
copy of them, which is also why the slim facet index is called `facets.json` here and not
`index.json`.

What the refusal actually rules out, stated as obligations:

- **no submission portal** — that is a leaderboard service;
- **no leaderboard of record** — that is running evaluations;
- **no dataset mirror, at all** — that is constraint 1;
- **no query backend** — nothing whose downtime makes a page unreadable or a number uncitable;
- **no execution service** before the deferred phase in
  [13-execution-runners.md](13-execution-runners.md).

The measured artifact sizes make the "API" question almost vacuous: the full corpus at target scale
is 2.76 MB raw and 0.52 MB brotli-compressed, and the slim facet index is 36 KB gzipped. Publishing
those at versioned, stable URLs *is* a read-only JSON API and requires no code. Add an MCP server
over the same static artifact — facet search plus entry fetch — which is the cheapest possible way
to serve the "AI insight" wish at scale: other people's agents do the synthesis, we supply the
ground truth. The one serverless function in
[AI1](#ai1-does-the-ai-layer-justify-breaking-the-pure-static-constraint-with-a-single-serverless-function)
is not an exception to the no-uptime-obligation rule, because the site is specified to remain fully
useful with it switched off.

Make the dataset-mirror rule mechanical rather than a matter of discipline. CI rejects any committed
`.parquet`, `.jsonl`, `.csv` or similar **under `data/`**, and rejects any YAML field exceeding a
fixed character count of copied prose. Note the one thing this deliberately does not catch:
`corpus.csv.zip` is a *release artifact built from* `data/`, not a file in it, so the rule and the
release set do not collide. The invariant is worth enforcing in code precisely because the person
who breaks it will have a good reason.

**If overturned:** [00-vision-and-scope.md](00-vision-and-scope.md) non-goals,
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) artifacts,
[11-ai-features.md](11-ai-features.md) MCP surface.

### E3. Do we accept sponsorship or institutional affiliation?

**The question.** The index publishes independence disclosures about other people's evaluations.
What do we accept, and what do we disclose about ourselves?

**Why it matters.** The asymmetry is the whole point. A project that flags `independence_flags` on
a vendor's self-reported claim and then takes money from a lab whose models it indexes has spent
its credibility on its operating budget. And the most likely funders in this space — frontier labs
and commercial eval vendors — are exactly the parties whose independence the index is built to
assess.

**Recommendation: accept only money that cannot buy inclusion, prominence or wording, and publish
every penny of it.**

Acceptable: infrastructure credits (Cloudflare, an embedding provider, compute); unrestricted
grants from non-commercial funders (philanthropic foundations, EU/UKRI-type public research
funding); and paid domain-expert review contracts where the reviewer is named in the entry and the
payer is named next to them.

Refused, in any form: payment from any organisation whose systems or benchmarks appear in the
index. No sponsored listings, no paid expedited review, no "featured benchmark", no
sponsor-suggested taxonomy terms, no advisory seats in exchange for funding.

Published: a `funding.yaml` in the repo listing every source, amount band and date, rendered at
`/independence` alongside the analytics feed from
[C6](#c6-do-we-run-analytics-at-all-and-if-so-what). We hold ourselves to a visibly stricter
standard than we apply to others, and the asymmetry is deliberate — it is the cheapest possible
demonstration that the disclosure fields mean something.

On institutional affiliation specifically: seek a **non-commercial** home, and only after public
v1 — MLCommons via the Croissant extension route
([A8](#a8-do-we-commit-to-publishing-a-croissant-benchmark-extension-and-when)), an academic group,
or a standards body. A commercial steward is not automatically disqualifying (MedHELM's spinout to
an independent commercial steward is the working counter-example), but the terms must be written
before the conversation, not during it. Whether an unincorporated project can receive a given
grant or sign a given contract at all is [A10](#a10-what-is-the-legal-and-financial-vehicle)'s
question, and it must be answered before an application, not after an offer.

The cost of this policy, stated plainly because it is real: it rules out the funders most likely to
say yes, and makes [C5](#c5-sustainability-and-the-succession-story) harder. That is accepted
deliberately.

**If overturned:** [05-repository-and-workflow.md](05-repository-and-workflow.md) legal and
independence posture, [00-vision-and-scope.md](00-vision-and-scope.md) principles.

### E4. Publication and outreach at public v1, and do we want an academic paper?

**The question.** How does anyone find out this exists, and does the project want a peer-reviewed
paper?

**Why it matters.** The paper question is not a vanity question, and it should not be decided by
whether a paper would be nice. A NeurIPS Datasets & Benchmarks submission **materially changes the
evaluation burden**: reviewers will want inter-rater reliability figures, a stated coverage
methodology, a comparison table against BenchmarkList, Benchmark Radar, Every Eval Ever and Epoch,
and a reproducibility statement. It converts [B4](#b4-who-is-the-second-annotator-and-is-an-llm-second-rater-legitimate)
from "good practice" into "required", and it costs three to four weeks of one person's time at a
point in the schedule where that time is the scarcest resource in the project.

**Recommendation: an arXiv technical report plus the Zenodo DOI at v1. The D&B paper is a post-v1
question, and the honest answer at v1 is "no".** The bar for a D&B submission is ≥500 entries, all
19 domain families non-empty, and a published `irr_human` figure. **The canonical v1 corpus is 320
entries ([02-taxonomy.md](02-taxonomy.md) §3), so the bar is not met at v1 by construction** — 500
to 700 families is `00`'s twelve-month steady state, reached in the post-v1 ingestion-at-scale phase
([14-roadmap.md](14-roadmap.md) §"Which document is canonical for scale"). Saying that directly is
better than leaving the recommendation to be inferred from a threshold nobody checked against the
seed target. The bar stays as the **trigger**: when the corpus passes 500 entries with the IRR
figure published, this question reopens.

Outreach at v1, in priority order, each sized, and none of it a launch post about how many entries
we have. The rows below sum to **6.5–11 person-days** — an earlier draft printed 6–10, narrowing its
own table by eye at both ends. That is the number that matters: at 20 h/week it is **two and a half
to four and a half weeks**, and it competes directly with curation.
[14-roadmap.md](14-roadmap.md) §Effort carries the whole programme as a cross-cutting effort row at
**52–88 h**. It is distinct from `14`'s "Reviewer recruitment and liaison" row, which is
[B3](#b3-domain-expert-reviewers-who-and-what-do-we-offer-them)'s specialist-reviewer workstream and
appears nowhere below; the two are separate people, separate asks and separate calendars.

| # | Action | Size | Why it is in this order |
| --- | --- | --- | --- |
| 1 | **Propose the registry pairing to EvalEval / Every Eval Ever** — the benchmark-registry counterpart to their result-registry | 1–2 days (a written proposal plus a worked join example) | HuggingFace, Edinburgh and EleutherAI backing plus CC BY 4.0 on both sides makes this a partnership rather than a collision. Highest-value single contact in the landscape |
| 2 | **Offer `inspect_evals_id` cross-references to UK AISI** | 0.5–1 day | Makes us the front door to their harness rather than a rival. Their `/register/` (launched 2026-05-08) is also the model we copied for the contribution path, and saying so is good manners and good positioning |
| 3 | **Offer `croissant-benchmark` to the MLCommons Datasets WG** | Inside `14`'s 10–20 h Croissant budget; no separate cost | Per [A8](#a8-do-we-commit-to-publishing-a-croissant-benchmark-extension-and-when) — the issue is filed once the emitter and three cross-domain examples exist |
| 4 | **One post per unindexed domain, robotics first** | 0.5 day each, 2–3 days for the first tranche | Robotics is the single largest unindexed field and the differentiator is legible there in thirty seconds. A generalist launch post is where it is invisible |
| 5 | **The arXiv technical report** | 3–5 days (shorter than a D&B paper's 3–4 weeks, and it buys most of the citability that matters) | This is the v1 publication. It carries the coverage methodology, the gap matrix and the IRR figure if there is one |

**File the regulatory angle as a note, not a product claim.** EU AI Act GPAI obligations became
enforceable 2026-08-02 and require evaluation "using standard benchmarks and state-of-the-art
tests" with no registry defining what qualifies. That is a real unfilled need and a credible route
to institutional adoption — but claiming to *be* the reference registry before anyone has asked us
to is exactly the unsourced confidence this project opposes.

For the record, on the venue if the trigger ever fires: the NeurIPS Datasets & Benchmarks Track had
**1,995 submissions and 497 accepted in 2025**, and **mandates Croissant metadata and persistent
public hosting**, both of which this project would already satisfy — a meaningful advantage over a
typical submission. Both facts come from `_workflow/recon/recon_sources.md` as of 2026-09-17 and are
**unverified — confirm the acceptance figures and the current submission requirements against the
call for papers before planning around them.**

Explicitly do not: enter a count comparison, publish a composite index, or position against
BenchmarkList on size.

**If overturned:** [01-landscape-and-positioning.md](01-landscape-and-positioning.md),
[14-roadmap.md](14-roadmap.md) public-v1 deliverables,
[03-taxonomy-build-process.md](03-taxonomy-build-process.md) IRR requirements.

### E5. What do we do if a competitor relicenses to CC-BY?

**The question.** Benchmark Radar's content is CC BY-NC-SA 4.0 today. BenchmarkList has no stated
licence today. Either could change in an afternoon. What happens to the positioning if one does?

**Why it matters.** Because it is a stress test of what the differentiator actually is. Of the four
claimed differentiators, the open licence is by far the cheapest for an incumbent to copy — it is a
one-line change to a text file. If the plan's identity rests on being the open one, the plan's
identity can be deleted by a competitor's commit.

**Recommendation: treat the licence as table stakes, not as the moat, and pre-commit to the
response.** The expensive, slow-to-copy assets are the cross-domain taxonomy, the evaluation-
conditions schema with a computed comparability key, the lineage and supersession model, the
liveness signalling, and the live gap matrix. Those are curation labour, and curation labour is the
thing no leaderboard company wants to do because it does not convert into a ranking.

The pre-committed response, so it does not have to be argued about under pressure: **if Benchmark
Radar relicenses to CC-BY, ingest them the same week** — they become a Tier-1 source with 37
ingestion connectors' worth of discovery for free, which is a straightforward win — and shift the
public positioning entirely onto evaluation conditions and non-language depth, which their own
abstract concedes they do not cover. If BenchmarkList opens, the response is the same and the
conditions differentiator matters even more, because their "Rosetta Stone" cross-benchmark
alignment is philosophically opposite to a comparability key that refuses to rank.

The one thing not to do is to race them on entry count, in either direction.

**If overturned:** [01-landscape-and-positioning.md](01-landscape-and-positioning.md),
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) source tiering.

---

## F. Items handed here by other documents

Ten documents end with a list of things they explicitly hand to this register, and until this
revision none of them were recorded here. The count was eight until 2026-09-22: `17` §9 and `18` §6
each carry a "carried forward" table that says in its own opening line that these go to this
register, and neither had been routed. A handoff both ends agree on and neither performs is the
quietest way for a decision to go missing. They are listed compactly rather than expanded into the
four-part form, because each is a narrow technical call whose owning document already carries the
context — and because a register that expands every handoff into a full entry becomes a document
nobody finishes. Each row names the owner, so the recommendation can be moved into the owning
document when it is acted on.

| From | Item | Recommendation | Trigger |
| --- | --- | --- | --- |
| `05` §Open items | The data-only mirror: filtered push or a split repository with the monorepo as a submodule? | Filtered push, for simplicity, until somebody asks for the other | A consumer asks for a data-only clone |
| `05` §Open items | Does `verification_status: maintainer-confirmed` require identity verification, with no auth in v1? | Require the confirmation to come from an account linked to the benchmark's own repository, or a message from a domain-matching address, recorded as a Source | The first maintainer confirmation arrives |
| `05` §Open items | Accepting entries for benchmarks the contributor maintains | Accept, always mark, always display — `governance.independence_flags` exists for exactly this | First such submission |
| `07` §12 | The HELM GCS data licence is unverified: Apache-2.0 code, no visible data licence | Email CRFM and get it in writing; until then store derived structured facts plus a link, never bulk | Before the HELM adapter ships |
| `07` §12 | Should `conflicts_with` link across *sources* for the same run (the ARC Prize duplicate-spelling case)? | Report-only signal in v1; promote to a modelled edge only if it recurs across more than three sources | Third occurrence |
| `08` §13 | Astro build time at 1,000–2,000 pages is unmeasured | Measure at ~200 entries in Phase 1, before committing to the performance budgets | 200-entry checkpoint |
| `08` §13 | UMAP cross-machine bit-identity is undocumented | CI is the sole authority for `atlas.json`; ship the deterministic pack layout first | Any atlas drift-gate failure |
| `08` §13 | ECharts SSR + ARIA (issue #19191) status in 6.1.0 | Irrelevant if the build-both-chart-and-table rule holds; verify anyway | Phase 2 |
| `08` §13 | Whether to ever ship in-browser SQL | Only for a public query console, and then `@sqlite.org/sqlite-wasm` (0.87 MB), never DuckDB-WASM (35.66 MB) | Someone asks for a query console |
| `08` §13 | GitHub Actions attestation format for build provenance | **Unverified** — confirm before advertising it anywhere | Before the provenance claim appears on the site |
| `08` §13 | Sharding and file-cap trigger validation | Re-measure `facets.json`, `corpus.json`, `claims.json` and the per-version file count at 1,000 real entries; the ~4,300 / ~6,250 / ~3,000 / ~2,900-entry triggers are all extrapolated ([08](08-infrastructure-and-build.md) §4.1, §7.5, which replaced an earlier eyeballed "4,500–5,000 for two triggers at once") | 1,000 entries |
| `09` §13 | The exact ΔE threshold for the colour-vision-deficiency gate | Set it for **cross-meaning pairs only** — two tokens that can share a viewport and mean different things. `D4` removed the 19-swatch family palette, so a pairwise ΔE floor across a family palette is now a check of something that does not exist | Phase 2, when `check_palette.py` is written |
| `09` §13 | Whether IBM Plex variable builds are usable for our subsets, or static weights are required | Measure both at subset time; prefer static weights if the variable build exceeds the font budget | Phase 2 |
| `09` §13 | Is a print stylesheet worth building in v1? | Yes, minimally — a citable reference page that prints badly undercuts the "infrastructure" claim; one stylesheet, detail pages only | Phase 2 |
| `09` §13 | Should the six-group domain colouring be user-selectable in the Atlas legend? | **Answered — no.** `D4` makes the presentation groups an ordering and banding device, `display_only: true`, forbidden from the filter grammar and from every derived artifact. There is no colour legend to expose | Closed |
| `10` (new, per `D4`) | Does emphasis need a **group-level** mode — "highlight all of life-health" rather than one family at a time? | Probably yes, and it is cheap: the same single emphasis token applied to a group's rows. The risk to guard is that a group-level highlight starts being read as a taxonomy level, which `D4` forbids; so the affordance must be labelled as a display grouping and must not appear in the URL grammar | Phase 2 Atlas build |
| `10` §Open questions | Atlas layout mode for v1: packed by default, or embedded from the start? | Packed-first; decide against real records in Phase 1, not in advance | 200-entry checkpoint |
| `10` §Open questions | Legibility gate thresholds (`neighbourhood_purity ≥ 0.60`, `domain_silhouette ≥ 0.15`) | Placeholders; calibrate on ~200 entries | Same checkpoint |
| `10` §Open questions | Coverage-map default resolution | **Settled by the decision set:** 19 families (`D4`) × 13 capability groups (`D1`) = 247 coarse cells, and `02-taxonomy.md` §4.3 owns the group enumeration. The fine grid is 204 (family, subdomain) pairs × 44 capability terms = 8,976 cells, exploration-only behind a null-model banner | Closed |
| `10` §Open questions | Does the Comparison Workbench need a server-rendered path? | No for v1. The static suite-report degradation is sufficient, and building SSR is real work; the citability compromise is confined to exactly one view and every underlying claim has a static page | Revisit if a citation of a workbench state is ever requested |
| `12` §9 | Regulatory-alignment coverage (mapping benchmarks to EU AI Act obligations) | **Do not produce our own mapping.** Either link a credentialed third party's published mapping with attribution, or leave the cell empty. An uncredentialed legal interpretation would hand a regulator a reason to distrust everything else on the site | A credible published mapping appears, or counsel is available ([C7](#c7-what-is-the-response-to-a-legal-threat-over-a-published-liveness-contamination-or-independence-signal)) |
| `12` | Domain expectation denominators — what "complete coverage" of a domain even means | Use the domain recon's Tier-1 estimates as the denominator and **render the denominator with its source and its uncertainty**, never a bare percentage. A coverage percentage with a guessed denominator is the single easiest way to publish a confident falsehood | Phase 4 coverage view |
| `13` §10 | Five deferred execution-layer questions — items 1–4 and 6: gate query yield, per-key spend caps, provider ToS for automated benchmarking, Inspect `.eval` schema stability, `maintainer_rerun_policy: unstated` default | All stay with `13`, which is the optional final phase and may never be built. Two are marked **unverified** there and must be confirmed per provider before any run | Phase 7 evidence gate |
| `11` §8 (Privacy) | Anthropic's data-retention terms for our account tier | **Unverified and unasked.** Confirm before any user query text leaves the browser, and state the answer on the AI-layer methodology page — a project that publishes provenance owes its own users the same | Before the AI layer ships |
| `13` §10 | Contribute `RunRecord`s upstream to Every Eval Ever? (item 5) | Yes — 8–16 h of serialiser plus a recurring drift check, and it buys the best alliance in the landscape. Decide it *with* them, not at them. Listed separately because `13` §10 carries seven items and this table previously routed only five | After [E4](#e4-publication-and-outreach-at-public-v1-and-do-we-want-an-academic-paper) item 1 |
| `17` §9 | Package name on PyPI — is `benchindex` available, and does it collide with the project name chosen in [A6](#a6-name-domain-identifier-permanence-and-doi)? | Reserve the name at the same time as the domain, before Phase 0 ends. Availability across PyPI, npm and GitHub is already a stated input to the naming decision, so this is one more surface on an existing check, not a new decision | With A6's four-surface availability check, before Phase 0 ends |
| `17` §9 | Does the CLI ship the maintenance subcommands to every user, or only inside a checkout? | Hide them outside a checkout, per `17` §2.5. Revisit if contributors report friction | A contributor reports friction |
| `17` §9 | Minimum supported Python | 3.11 — one below the 3.12 the repository pins, so a consumer on an older cluster image is not excluded. Note this is a *consumer* floor and does not relax the repository's own 3.12 pin, which the Atlas layout's reproducibility depends on ([05](05-repository-and-workflow.md) §3) | Phase 7, when the package is built; or sooner if a dependency raises its floor |
| `17` §9 | Does the MCP server get its own release cadence? | Yes — separate wheel, separate version. It will change with the MCP spec, which moves faster than the catalogue | Phase 7, at the first MCP server release |
| `18` §6 | Does GraphQL earn its maintenance, or would a richer REST filter grammar do? | Ship REST first and measure. Build GraphQL only if the join queries in `18` §1 actually appear in logs; the endpoint is easy to add and hard to remove | The join queries appear in request logs |
| `18` §6 | Who reviews submissions at volume, when maintainer hours are the binding constraint? | The domain reviewer programme in [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §12 is the natural pool, but it was scoped for taxonomy review, not claim review. If submission volume exceeds review capacity, submissions **queue rather than auto-merge**, and the backlog is published. This is the same constraint as [C5](#c5-sustainability-and-the-succession-story) seen from the intake side | Submission volume exceeds review capacity for four consecutive weeks |
| `18` §6 | Should a trusted-submitter tier exist that skips human review? | Not before there is evidence of a review bottleneck *and* a submitter with a clean record over a stated number of claims. Write the rule before granting the first one, or the first grant becomes the rule | The review bottleneck above is evidenced |
| `18` §6 | What is the SLA on the hosted API, if any? | **None, stated explicitly.** Best-effort, with the static artifacts named as the supported path for anything that needs reliability. This is [E2](#e2-should-the-index-host-anything)'s no-uptime-obligation rule applied to the API surface, and the API's own page must say so | At API launch, on the API's landing page |
| `13` §10 | Who runs the runner if the founders stop? (item 7) | `SUCCESSION.md` should say explicitly that the execution layer is **not** part of what a fork inherits. The data is the asset; a runner a fork feels obliged to keep alive makes the fork look harder than it is. MedHELM's spin-out is the working model | With [C5](#c5-sustainability-and-the-succession-story), before public v1 |

---

## Edits this register requires in other documents

Applying the decisions above changes other files. Listed so they are not lost in prose — **and each
row now carries a status, because the previous version of this table was a list of thirteen edits of
which eleven had never landed, which is worse than no list at all: it reads as decided and is not.**

Statuses are `landed` (verified present in the target), `pending <owner>` (agreed, not yet written
into the target) and `withdrawn` (the instruction was wrong; the reversal is recorded in the
*Answered* table below). A row stays here until it is `landed`, and the intended mechanical check is
that every backticked identifier in this table appears in the file the row names — see the note after
the table.

| File | Edit | From | Status (2026-09-22) |
| --- | --- | --- | --- |
| [04-data-model.md](04-data-model.md) §15 | Add `Benchmark.learned_entrant_evidence`, `.evaluation_target`, `.execution_mode`, `.ground_truth_source`, `.reproducible_by_third_party` | [A3](#a3-what-counts-as-an-ai-benchmark) | **pending `04`** — highest priority in the table. The inclusion boundary is a settled assumption in `00` §6 A5 and a scoping rule with no field is a scoping rule nobody can enforce or audit |
| [04-data-model.md](04-data-model.md) §15 | Add `ResultClaim.external_ids.eee_result_id` | [A7](#a7-how-far-do-we-adopt-every-eval-evers-schema-vocabulary) | **pending `04`** |
| [04-data-model.md](04-data-model.md) §15 | Add `System.availability` and `System.retired_on`; do **not** add a `system_status` field | [C3](#c3-handling-systems-that-no-longer-exist) | **pending `04`** |
| [04-data-model.md](04-data-model.md) §5, §7, §15 | Add `Benchmark.reference_conditions` (an `EvalConditions` ref, nullable — headroom is `null` without it) and `ResultClaim.provenance_snapshot` (one of the four C5 pre-ingest additions, and the only one still missing) | `02` §8's SOTA rule; C5 | **pending `04`** — `provenance_snapshot` is named as mandatory by eight documents and defined by none. It is not the same object as `field_provenance` |
| [04-data-model.md](04-data-model.md) §5 | Add `Benchmark.execution.runnable_via` and `.inspect_evals_id`, which `13` §3.1 assigns to Phase 0 and names `04` as owner | `13` §3.1 | **pending `04`**; `14` Phase 0 deliverables now list them |
| [04-data-model.md](04-data-model.md) §5 | Carry `maintenance_status` and its `_contested` siblings as a derived field with the `liveness` block named as its input | superseding the withdrawn row below | **pending `04`** |
| [04-data-model.md](04-data-model.md) licence firewall | `sources/pwc-archive/` → `vendor/pwc-archive/`. Not a spelling difference: `05` §2 puts `data/sources/` inside the CC-BY core, so the stale path reads as an instruction to put viral CC-BY-SA content into the licensed tree | [A5](#a5-the-papers-with-code-cc-by-sa-firewall) | **pending `04`** |
| [04-data-model.md](04-data-model.md) tier-4 quality rules, ResultClaim | Reference `frontier_floor` rather than a literal 0.3; drop the archived "500 claims" target in favour of `14`'s restatement | [C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view) | **pending `04`** |
| [12-analytics-and-trends.md](12-analytics-and-trends.md) | Declare `frontier_floor = 0.3` and `comparison_floor = 0.4` as the two named constants, stored in `taxonomy/thresholds.yaml` | [C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view) | **landed** — `12` §1.4, which now owns both, states why they differ, and schedules their recalibration |
| [05-repository-and-workflow.md](05-repository-and-workflow.md), [10-visualization.md](10-visualization.md) | The 0.35 hide-in-comparison threshold becomes `comparison_floor`, by name not value | [C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view) | **pending `05`, `10`**; `11` F5's copy of the same literal is **landed** |
| [05-repository-and-workflow.md](05-repository-and-workflow.md) §9 | Add the CI check: no path under `data/` may carry `provenance: ai-worker`. Do **not** add a human-committer assertion | [AI1](#ai1-does-the-ai-layer-justify-breaking-the-pure-static-constraint-with-a-single-serverless-function) | **pending `05`** — this check is the mechanical enforcement of "nothing the model emits is ever stored in `data/`". Without it that rule is an assertion rather than a property |
| [05-repository-and-workflow.md](05-repository-and-workflow.md) §6 | Add the `codeowners-lapse.yml` rule to the governance ladder | [A11](#a11-governance-beyond-one-maintainer-what-happens-when-the-first-outside-contributor-wants-commit-rights) | **pending `05`** |
| [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) | `vendor/pwc/` → `vendor/pwc-archive/`; `07`'s 0.5 completeness bar becomes `comparison_floor` | [A5](#a5-the-papers-with-code-cc-by-sa-firewall), [C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view) | **partly landed** — the path is correct in both; `07`'s 0.5 bar is still a literal. `03` and `08` still say `vendor/pwc/` and were never on this list |
| [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) | Replace the archived "500 claims" target with a pointer to `14`'s Phase 3 gate | [C4](#c4-at-what-threshold-may-a-machine-ingested-claim-enter-a-comparison-view) | **landed vacuously** — `07` carries no such target; `04` does, and carries the correction inline |
| [08-infrastructure-and-build.md](08-infrastructure-and-build.md) | Add `analytics/YYYY-MM.json` as a committed, non-core artifact and state the no-beacon rule | [C6](#c6-do-we-run-analytics-at-all-and-if-so-what) | **pending `08`** |
| ~~`01`, `02`, `06`, `14`~~ | ~~`maintenance_status` is not a field; use `lifecycle` plus the `liveness` block~~ | [C3](#c3-handling-systems-that-no-longer-exist) | **WITHDRAWN 2026-09-22** — see below |

**The withdrawn row, recorded rather than deleted.** C3's instruction that `maintenance_status` "is
not a field" was wrong, and the documents that ignored it were right. `lifecycle` and
`maintenance_status` are not substitutes: `liveness` is the raw evidence (repo push dates, dataset
modification, reproduction-script presence), `maintenance_status` is the five-term verdict derived
from it (`actively-maintained` · `slow` · `stale` · `abandoned` · `unobservable`), and `lifecycle`'s
ten terms contain none of `stale`, `abandoned` or `unobservable` and cannot express either. The
`unobservable` term in particular exists for a specific reason — without it CASP is reported as
`stale`, which is false and would discredit the liveness feature on its first specialist reader,
which is differentiator (iv) dying on contact with a domain expert.
[02-taxonomy.md](02-taxonomy.md) §8 owns the vocabulary and its derivation, and thirty-six lines of
worked vocabulary beat one line of register prose. The follow-on is that `04` must carry the field;
that is the row four above this note. **`00`, `01`, `02`, `06` and `14` need no edit.**

**The check that would stop this table rotting again.** Extend `verify_corpus.py` so that every
backticked identifier, path and filename in this table must appear in the file the row names, and so
that a row still marked `pending` after a revision pass is reported. The table's value is entirely in
being current; a list of required edits that nobody reconciles is a second, competing record of what
the plan says.

---

## Answered, recorded so they are not relitigated

Decisions already made. Each has a document that records it. If you find yourself re-arguing one of
these, the correct move is to write down what changed and supersede it explicitly — not to change
the code and let the document rot. Per the note at the top of this file, this table *is* the record
until public v1; ADRs begin only for decisions overturned after the first DOI'd release.

### The four adjudicated decisions of 2026-09-21

These are the four questions the corpus most recently contradicted itself on, adjudicated by a
dedicated panel with full decision documents on disk. They are listed first because the risk they
carry is specifically silent relitigation: each of them replaced numbers that several documents had
been restating in their own words for three revisions.

| Decision | What it settles | Owned by | Decision document |
| --- | --- | --- | --- |
| **D1 — capability groups** | 13 capability groups as a strict partition of all 44 capability terms; the coarse coverage grid is 19 × 13 = 247 cells, replacing an asserted 228 and an asserted 144 | [02-taxonomy.md](02-taxonomy.md) §4.3 owns the enumeration; `taxonomy/capability_groups.yaml` stores it | `_workflow/decisions/D1-capability-groups.md` |
| **D2 — seed targets and the floor** | 320 seed entries across 19 families, 290 launch gate, 144 in the Core seven with a gate of 130; three floor numbers with three jobs (12 hard, 18 Core, 15 credibility by v1.x) and the muting exemption | [02-taxonomy.md](02-taxonomy.md) §3 owns the per-family allocation; [14-roadmap.md](14-roadmap.md) owns the derived gates | `_workflow/decisions/D2-seed-targets-and-floor.md` |
| **D3 — vocabulary namespacing** | Family-qualified subdomain paths, bare capability slugs, the facet carried by the field name; the four capability/subdomain homographs stay and the four tautological cells are marked; `games-planning/puzzle-solving` → `puzzle-games`; CI check 9c rewritten into 9c/9d/9e | [04-data-model.md](04-data-model.md) identity and [05-repository-and-workflow.md](05-repository-and-workflow.md) §9 | `_workflow/decisions/D3-vocabulary-namespacing.md` |
| **D4 — the 19-family cascade** | Domain family is never encoded by hue, anywhere; the six presentation groups are an ordering and banding device, `display_only: true`, forbidden from the filter grammar and every derived artifact; `check_palette.py` rewritten to check ordered and semantic encodings instead of 19 swatches | [09-design-system.md](09-design-system.md) and [10-visualization.md](10-visualization.md) | `_workflow/decisions/D4-nineteen-family-cascade.md` |

### Everything else

| Decision | Recorded in |
| --- | --- |
| Faceted classification, not a hierarchy: one Domain spine plus seven flat orthogonal facets | [02-taxonomy.md](02-taxonomy.md) |
| Data as git: YAML, one entity per file, no privileged mutation path; the database is a build artifact | [05-repository-and-workflow.md](05-repository-and-workflow.md) |
| Pydantic v2 canonical → JSON Schema generated → TypeScript via `json-schema-to-typescript@16.0.0`; all three committed, CI fails on a regeneration diff | [04-data-model.md](04-data-model.md), [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| `EvalConditions` is a separate, shareable, referenceable entity | [04-data-model.md](04-data-model.md) |
| `comparability_key` as a **refusal** mechanism — the UI declines to rank non-comparable numbers and shows a field-level diff instead | [04-data-model.md](04-data-model.md), [10-visualization.md](10-visualization.md) |
| No universal score; headroom consumed is the only legitimate cross-domain axis | [12-analytics-and-trends.md](12-analytics-and-trends.md) |
| Never host or redistribute benchmark datasets; metadata and links only | [00-vision-and-scope.md](00-vision-and-scope.md) |
| Two unsharded JSON artifacts, not the earlier sharded scheme (measured: 2.76 MB raw / 0.52 MB brotli full corpus; 36 KB gzipped slim index). Sharding was overturned by measurement | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| SQLite is a build-time-only artifact and a per-release data product; DuckDB-WASM rejected (35.66 MB engine, ~70× the dataset) | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| Astro 7.3.3, Node ≥ 22.12; `compressHTML` set explicitly because the `'jsx'` default eats whitespace between inline elements such as facet chips | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| ECharts 6.1.0 for the heavy views plus hand-rolled build-time SVG for sparkline small-multiples; Observable Plot rejected (no npm release since 2025-02-14, 349 open issues, pointer transform breaks SVG serialisation) | [10-visualization.md](10-visualization.md) |
| Sigma.js 3.0.3 primary for the Atlas, cosmos.gl 3.4.1 fallback; regl and deck.gl rejected | [10-visualization.md](10-visualization.md) |
| Atlas layout stability: frozen SVD basis, UMAP warm start via `init=<ndarray>`, Procrustes alignment between builds, CI drift gate — and CI is the **sole** authority that writes `atlas.json`, because UMAP reproducibility holds across runs but not across machines | [08-infrastructure-and-build.md](08-infrastructure-and-build.md), [10-visualization.md](10-visualization.md) |
| Python 3.12, not 3.13 — scikit-learn 1.9.1 needs ≥ 3.11 and the numba/UMAP stack lags new CPython; layout reproducibility depends on the pin | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| Cloudflare Workers with static assets, not Pages and not GitHub Pages (static asset requests unbilled; GitHub Pages has no serverless path) | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) |
| Brute-force cosine over a `Float32Array`, dequantised at load from an int8 transport format (measured 0.61 ms at 1,500 × 256, our configuration; 0.75 ms at 384; the int8 dot loop is *slower* at 2.0 ms). No HNSW, no vector index, no vector database | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §5.5 owns the timings; [11-ai-features.md](11-ai-features.md) owns the pipeline |
| Static embeddings, client-side, as the primary query-encoding path; Worker-side Voyage and lazy MiniLM as ordered fallbacks | [11-ai-features.md](11-ai-features.md), and [AI2](#ai2-where-does-the-query-embedding-happen-the-reports-disagree) |
| Pagefind for lexical search, indexing YAML directly via `addCustomRecord()` | [08-infrastructure-and-build.md](08-infrastructure-and-build.md), [11-ai-features.md](11-ai-features.md) |
| Contribution must **not** require a pull request: GitHub issue form → validation bot → auto-generated PR → human review, modelled on UK AISI's `inspect_evals` `/register/` (2026-05-08). The PR path stays for power users, and the bot is a permitted author under `data/` with `Co-authored-by` attribution | [05-repository-and-workflow.md](05-repository-and-workflow.md) §6 |
| Branch protection on `main` requires one human approval and the passing validation check, with no bot bypass | [05-repository-and-workflow.md](05-repository-and-workflow.md) §6 |
| **Corrections and disputes:** anyone, including evaluated parties, disputes via `dispute.yml`; a dispute is never resolved by deletion; both positions render with their sources; `disputant_relationship` is shown; corrections are published at `/corrections` from commit trailers | [05-repository-and-workflow.md](05-repository-and-workflow.md) §8, and [C7](#c7-what-is-the-response-to-a-legal-threat-over-a-published-liveness-contamination-or-independence-signal) |
| CC-BY + DOI + forkable-at-commit from day one, with a documented succession story | [05-repository-and-workflow.md](05-repository-and-workflow.md) |
| Scrapers run as GitHub Actions cron in the data repo itself (Cloudflare Workers Free gives 10 ms CPU per cron trigger, which disqualifies it); odd-offset schedules, idempotent jobs, a fine-grained PAT rather than the 1,000/hr ambient `GITHUB_TOKEN` | [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) |
| Result-claim curation is tiered by existing coverage: ingest or link where a mainstream leaderboard already maintains the numbers; hand-curate where nobody else has them (robotics, chemistry, climate, protein, formal proof) | [01-landscape-and-positioning.md](01-landscape-and-positioning.md), [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) |
| Epoch AI is an attributed ingestion source, not something to re-curate: ingest in bulk to `data/claims/_ingested/epoch/`, badge honestly, segregate from `data/claims/`, hand-curate 50–80 adversarially-chosen claims | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md), [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) |
| Schema prerequisites **before** the first ingest — eight items, owned and enumerated in one place | [04-data-model.md](04-data-model.md) §15, plus the three fields this register adds ([A3](#a3-what-counts-as-an-ai-benchmark), [A7](#a7-how-far-do-we-adopt-every-eval-evers-schema-vocabulary), [C3](#c3-handling-systems-that-no-longer-exist)) |
| Do not ingest Benchmark Radar (CC BY-NC-SA, incompatible with CC-BY); do not mirror Artificial Analysis (attribution permitted, redistribution contractually barred) — link and cite only | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) |
| The AI layer is a lens, never a source: deterministic client-side retrieval, nothing model-generated is ever stored in `data/` or citable, and **the model never produces a number** | [11-ai-features.md](11-ai-features.md) |
| "Build your own custom benchmark" means **suite assembly** — selecting existing benchmarks and exporting a manifest. Authoring new benchmark tasks or data is out of scope for v1 | [11-ai-features.md](11-ai-features.md), [AI4](#ai4-the-custom-benchmark-fork-suite-assembly-or-authoring-new-benchmarks) |
| The execution/runner layer is deferred to the last phase and is optional | [13-execution-runners.md](13-execution-runners.md) |
| The `ceiling_anchor_type` rename (from `human_baseline_type`) landed; the old name is never a live field name again | [02-taxonomy.md](02-taxonomy.md), [04-data-model.md](04-data-model.md) |
| **Reversal, 2026-09-22:** `maintenance_status` **is** a field. This register's C3 previously instructed four documents to remove it; the instruction was wrong and is withdrawn. `liveness` is the evidence, `maintenance_status` is the derived five-term verdict, and `lifecycle`'s ten terms can express neither. The consequence is an addition to `04`, not a deletion from `02` | [02-taxonomy.md](02-taxonomy.md) §8 owns the vocabulary; see the withdrawn row above |
| **Reversal, 2026-09-22:** the `Baseline` entity's `kind` enum and the `ceiling_anchor_type` facet are the only two ceiling vocabularies. `12` §3.2 previously printed a third of its own invention (`replicate-experiment`, `measurement-ceiling`) and has been reduced to citing the owners. The reciprocal question it created — whether an operational forecast is a floor or a ceiling — is settled as **ceiling**, per `02` §7's WeatherBench 2 record | [02-taxonomy.md](02-taxonomy.md) §7, [04-data-model.md](04-data-model.md) §7, [12-analytics-and-trends.md](12-analytics-and-trends.md) §3.2 |
| Public, community-contributable, not an internal tool — superseded by [A2](#a2-public-from-commit-one-or-curate-privately-to-the-phase-1-exit-bar-first), which narrows the question to *when* | [00-vision-and-scope.md](00-vision-and-scope.md) |

---

*Reading order and the rest of the document set: [README.md](README.md). What this register decides
against: [00-vision-and-scope.md](00-vision-and-scope.md) principles and non-goals.*
