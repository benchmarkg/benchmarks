# 04 -- Data Model

This document specifies the entities, fields, identity rules, provenance model and validation
regime for the index. It is the most consequential document in the plan, because everything else
is downstream of it: the taxonomy ([02-taxonomy.md](02-taxonomy.md)) supplies the vocabularies that
these fields draw on, the ingestion layer ([07-ingestion-infrastructure.md](07-ingestion-infrastructure.md))
writes records against this schema, the build ([08-infrastructure-and-build.md](08-infrastructure-and-build.md))
compiles these files into two JSON artifacts, and every view
([10-visualization.md](10-visualization.md)) is a projection of these fields. A field that does not
exist here cannot be filtered, compared, charted or cited.

The schema described here is a revision of the earlier draft, not a replacement. The entity graph,
the identity rules, the verification ladder and the comparability rule all survive essentially
intact -- they were correct. What changed is that the model has now been stress-tested against two
bodies of evidence it was never tested against before: the 6,598 real result rows in the local
Epoch AI snapshot, and the ten hardest benchmarks in the non-language domains. Both broke things.
The corrections are marked where they occur.

---

## 1. Five design principles

**A record is a claim, not a fact.** Every number in this index was asserted by somebody, somewhere,
under conditions that were usually not fully described. The schema's job is to carry the assertion
together with everything needed to judge it -- who said it, when, under what conditions, with what
evidence, verified by whom. Conflicting claims about the same (system, benchmark, metric) coexist
by design and the index does not adjudicate between them. The failure mode this avoids is the one
every aggregator falls into: silently picking one number per cell because a table needs one number
per cell. The Epoch snapshot contains a live example -- `falcon-7b` on MMLU at a nominal five shots
is reported at 0.35, 0.269, 0.262, 0.262, 0.2603 and 0.239 by six different vendor papers, a 34%
relative spread. Any model that forces those into one cell has destroyed the most interesting thing
in the data.

**Null means unknown, never default.** This is the single rule with the widest blast radius. If a
paper does not say whether chain-of-thought was enabled, the field is null and the claim's
completeness score drops; it does not become `false`. Epoch's own curators write the distinction in
prose -- their notes contain `"Assuming medium based on GPT-5 being run at medium."`, `"Assuming
medium reasoning effort"`, `"Couldn't find shot count"`, `"currently pending confirmation of
thinking token length"` -- in a column filled on 5.7% of rows. We make that structural instead of
anecdotal. The failure mode: defaults launder assumptions into data, and once laundered they are
indistinguishable from measurements.

**Derived values never live in the source YAML.** `comparability_key`, `condition_completeness`,
`headroom_consumed`, the `saturated` lifecycle state, coverage counts and every trend metric are
computed at build time from the fields above them. They appear in the build artifacts and on the
site, never in a file a curator edits. A derived value written by hand is a value that rots
silently the moment its inputs change, and it destroys the auditability that is the entire point of
data-as-git.

**Ingested and curated records are separate populations and must stay separable forever.** The
ingest-versus-curate doctrine in [01-landscape-and-positioning.md](01-landscape-and-positioning.md)
is not only an editorial policy; it is a schema requirement. Machine-ingested records carry a
different provenance block, live in a different tree, sort differently, and are excluded from
comparison views below a completeness threshold. Mixing them is irreversible: once 6,598 bulk rows
are interleaved with 80 hand-curated ones, no later query can tell them apart.

**The schema must survive the hardest record, not the easiest.** A model that handles MMLU
gracefully and CASP badly is a language-model schema wearing a cross-domain label, and cross-domain
breadth is differentiator #1. Section 13 works the nastiest case in the catalogue end to end for
exactly this reason. Ten stress cases are named in
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) and every one of them must validate
before bulk curation starts.

---

## 2. Entity graph

Fourteen entity types. The four additions since the earlier draft are `Baseline` (a generalisation
of `HumanBaseline`), `IngestBatch`, `Alias` and `RatingPool`; each is justified where it is defined.

```
Organization ──maintains──────> Benchmark ──has_version──> BenchmarkVersion
     │                              │  │                          │
     │                              │  ├──hosted_on──> Leaderboard │
     │                              │  └──lineage────> Benchmark   │
     │                              │                              │
     │                              ├──contains──> Subset <────────┘
     │                              └──scored_by──> Metric
     │                                                   │
     └──releases──> System ──has_version──> SystemVersion │
                      │                          │        │
                      └──built_on──> System      │        │
                                                 v        v
                                           ResultClaim ───┘
                                        │    │     │    │
              cites──> Source <─────────┘    │     │    └──in──> RatingPool
                                             │     └──under──> EvalConditions
                                             │                      │
                                             └──from──> IngestBatch <┘

Baseline ──on──> BenchmarkVersion          Alias ──resolves_to──> (any entity)
```

Every entity is a YAML file or a record within one, addressable by a stable slug and renderable at
a permanent URL. The repository layout that holds them is in
[05-repository-and-workflow.md](05-repository-and-workflow.md).

Two relationships in that diagram deserve a note now because they are where cross-domain benchmarks
break naive schemas. `System ──built_on──> System` exists because an agent scaffold is a System and
the question every reader has is which base model was underneath it; Terminal-Bench's leaderboard
is the only source in the Epoch corpus that cleanly separates `Agent Org` from `Model Org`, and we
should model what it knows. `ResultClaim ──in──> RatingPool` exists because Elo is not a property
of a system -- it is a property of a system *within a pool at a snapshot*, and a claim that omits
the pool is meaningless.

---

## 3. Identity and stability

Citability is a hard requirement, so identifiers are permanent and never reused.

- **Format**: lowercase kebab slug. `mmlu`, `swe-bench`, `casp`, `arc-agi`, `cache-challenge`,
  `matbench-discovery`, `weatherbench-2`.
- **Domain ids are two-level**: `{family}/{subdomain}`, both lowercase kebab slugs
  (`code/repository-scale-se`). A bare family is a navigational node and is **not** assignable to
  `domain.primary` or `domain.secondary[]`. Every other facet term is a bare slug.
- **Facet-qualified reference**: `{facet}:{id}` -- `capability:planning`,
  `domain:reasoning-general/planning`. Used **only** where a term appears outside a facet-typed
  field: cross-facet `see_also`, `taxonomy/homographs.yaml`, coverage-cell and survey-note keys,
  and the AI layer's facet-translation output. A qualified value inside a facet-typed field is a
  Tier-1 failure. The facet is carried by the field name, not by a prefix on the value, so there is
  no `capability:` or `domain:` prefix anywhere in `data/`
  (see `_workflow/decisions/D3-vocabulary-namespacing.md`).
- **Versioned refs** use `@`: `mmlu@2020-09`, `swe-bench@verified`, `casp@17`, `arc-agi@2`.
- **Subset refs** use `#`: `mmlu#college-chemistry`, `video-mme#long-with-subtitles`.
- **Fully qualified claim ref**: `{system}@{sysver}/{benchmark}@{benchver}/{metric}[#{subset}]`.
  This string is what the site exposes as a copy-paste citation and what an external consumer joins
  on. It is stable across renames because every component is an id, not a name.
- **Renames** change `name`, never `id`. The old name moves to `aliases[]` and stays searchable.
- **Merges** leave a tombstone file carrying `redirects_to`, so old URLs and published citations
  keep resolving. A tombstone is a real file with a real id; it is never deleted.
- **Retirement** appends to `taxonomy/retired-ids.yaml`. CI fails any commit that reuses an id
  appearing in that ledger or in any tombstone.

### Id allocation is a human act

**Adapters may never allocate an id.** They reference existing ids or emit an unresolved record
(section 10). This is not a stylistic preference; the Epoch data makes the case concretely.
Automated slugification of Epoch's 81 benchmark names would produce, among others:

| Epoch string | What slugification produces | What is actually true |
| --- | --- | --- |
| `FrontierMath-Tier-4-2025-07-01-Private` | one benchmark | one benchmark, one tier (a subset), one dated snapshot (a version), one access mode |
| `GPQA diamond` | a benchmark | a *subset* of GPQA |
| `MATH level 5` | a benchmark | a *subset* of MATH |
| `ARC-AGI` vs `ARC AI2` | two similar benchmarks | two unrelated benchmarks sharing a prefix |
| `OSWorld` / `OSWorld 2.0` | two benchmarks | one benchmark, two versions, one of them breaking |
| `METR` / `METR Time Horizons` | two benchmarks | (unverified -- one appears to be an umbrella row with no data file; confirm before assigning ids) |

Ids are permanent. A wrong id is a permanent wrong id plus a tombstone. Ten minutes of human
judgement per benchmark is cheap against that, and there are only a few thousand benchmarks in the
world worth cataloguing.

---

## 4. The counting convention: families, editions and children

This is the highest-leverage modelling decision in the document and it has to be settled before the
first file is written, because retrofitting it means re-slugging everything.

The problem: is BraTS 2026 one benchmark or five? Is DCASE 2026 one benchmark or seven? Is CASP one
benchmark or thirty years of editions with dozens of per-category metrics? Is NTIRE one benchmark or
twenty tracks re-run annually? Get this wrong and every count the project publishes is meaningless,
including the coverage matrix that is differentiator #3.

**The rule.** A `Benchmark` is a **family**: a named, continuing evaluation effort with a stable
identity and a maintainer. Everything below it is modelled as one of three things:

| Structure | Modelled as | Test | Examples |
| --- | --- | --- | --- |
| A re-issue with new data on the same task | `BenchmarkVersion` with `version_kind: edition` | Same task definition, new items, new year | CASP16 -> CASP17, DCASE 2025 -> 2026, BraTS 2025 -> 2026, LifeCLEF editions |
| A correction or revision of the same items | `BenchmarkVersion` with `version_kind: revision` | Same items, changed contents | SWE-bench -> SWE-bench Verified, FrontierMath's June 2026 errata re-issue |
| A parallel track, task or split within one release | `Subset` | Scored separately, same release, same maintainer | DCASE's 7 tasks, BraTS's 5 sub-challenges, NTIRE's ~20 tracks, MMLU's 57 subjects, VideoMME's with/without subtitles |
| A separately maintained thing that grew out of another | a new `Benchmark` with a `lineage` link | Different maintainer, or independently versioned and cited | OSWorld -> OSWorld-Verified, SWE-bench's six forks, MedHELM after its spin-out |

**We count and publish families.** Every headline number the project quotes -- "1,240 benchmarks
indexed", the coverage matrix cells, the domain totals -- counts families, and the site says so in
the same breath. Children are counted separately and labelled as such.

The reason to publish families rather than children is adversarial: BenchmarkList claims 2,545
benchmarks and Benchmark Radar claims 14,810 raw records against ~1,283 curated. If we count
children we can trivially claim more than either, and the number will be meaningless. If we count
families and say so, our number will look smaller and be defensible. Per the recon's own estimate,
the honest ceiling is roughly 4,700 families across all domains, with ~300 genuinely field-defining
Tier-1 families -- and ~120 of those Tier-1 families sit in robotics, chemistry and materials,
biology, climate and physics, which is the differentiating core. Both of those are estimates of what
*exists*, not targets: the seed allocation against them is 106 entries in those five families out of
a canonical seed total of 320, owned by [02-taxonomy.md](02-taxonomy.md) §3 and restated nowhere
else. Say which set you mean when you quote either figure. Competing on raw count is a race we would
win dishonestly and lose on inspection.

The failure mode to avoid: a "benchmark count" that silently mixes families and children, which is
what makes every published catalogue comparison in this space uninterpretable today.

### The domain-family record

One confusable word, disambiguated once: a **benchmark family** is the entity above, a
`Benchmark`. A **domain family** is a top-level term in the Domain facet -- the nineteen of them
enumerated in [02-taxonomy.md](02-taxonomy.md) §3 -- and it is a taxonomy record, not a `Benchmark`.
The taxonomy record's shape belongs to
[03-taxonomy-build-process.md](03-taxonomy-build-process.md) §4, but four of its fields are
schema-relevant because the site filters, badges and gates on them, and a field that does not exist
here cannot be filtered:

| Field | Type | What reads it |
| --- | --- | --- |
| `seed_target` | int, >= 1 | The per-family curation allocation. Summed and gated in CI (check 9f in [05-repository-and-workflow.md](05-repository-and-workflow.md) §9, which owns the numbering; 9d is the homograph check); never restated in prose outside [02-taxonomy.md](02-taxonomy.md) §3 |
| `core` | bool | Marks the seven differentiating families, which carry a higher launch floor and no muting exemption |
| `coverage_status` | `surveyed \| under-surveyed` | The muting mechanism. `under-surveyed` drives a visible badge on every entry in the family, the family's rendering in the coverage map, and the Gap Finder's refusal to assert a gap in that row |
| `reviewer_signoff` | `none \| generalist \| domain-expert` (+ `reviewer` org/handle ref, `signed_on`) | The one hand-set input to `curation_confidence`. Scored 0 / 0.5 / 1 by the formula in [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3 |
| `curation_posture` | `hand-curate \| mixed \| ingest-then-verify` | The ingest-versus-curate doctrine, per family. [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10 owns the doctrine that assigns the value; [02-taxonomy.md](02-taxonomy.md) §3's posture column renders the same value from the same file. Gated by check 9f alongside `seed_target` |

**`curation_posture` is a field here for a specific, already-realised reason.** Two documents print
a posture label beside each of the nineteen families — `01` §10's doctrine table and `02` §3's seed
table — and until this pass they were two prose copies of the same nineteen labels with nothing
joining them. They had already drifted: medicine-health read `mixed` in one and `hand-curate` in the
other, which made `01`'s own count of "nine hand-curate, four mixed, six ingest-then-verify" fail to
reproduce from `02`'s column. That is precisely the mechanism D2 was convened to stop for the seed
numbers, one field to the right. Both tables render from `taxonomy/domains.yaml` and check 9f
extends to assert it.

**`coverage_status` and `reviewer_signoff` are two axes, not one, and collapsing them is the error
to avoid.** `coverage_status` answers *did we look*; `reviewer_signoff` answers *did somebody who
knows the field check what we found*. A family can be thoroughly surveyed by us and still unreviewed
by a specialist, and the two failure modes read completely differently to a roboticist scanning
their own row. [02-taxonomy.md](02-taxonomy.md) §3 gates on `coverage_status` and
[14-roadmap.md](14-roadmap.md) gates on reviewer sign-off; neither was modelled anywhere, which is
how two independent badge mechanisms came to be specified with no field behind either. Both are
hand-set by a curator and both are rendered rather than silently consumed -- an undisclosed thin row
is what makes a gap claim unfalsifiable, and disclosure is the only honest fix, because padding
trades a visible gap for an invisible quality failure.

**`curation_confidence` itself is derived and must never be written into the YAML**, per principle
three in §1. [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.3 owns its formula: 0.40 x
entry coverage against the per-family expectation in `taxonomy/domain-expectations.yaml`, 0.30 x the
fraction of entries verified within 180 days, 0.30 x `reviewer_signoff`. Where another document
writes `curation_confidence: unreviewed` as though it were a stored enum -- [14-roadmap.md](14-roadmap.md)
does, in its badge and gate language -- read it as shorthand for the derived score at
`reviewer_signoff: none`. The distinction matters for exactly the reason the principle exists: two of
its three inputs change every time a curator touches an entry, so a hand-written value would be
stale within a day and nobody would know.

One adjacent vocabulary is deliberately *not* a field on this record: the six-member presentation
grouping of families used for banding and ordering in the visual layer
(`taxonomy/domain_groups.yaml`, `display_only: true`). It is derived into `atlas.json` at build
time, is forbidden in `facets.json`, `corpus.json` and every `derived/*.json`, and has no filter
key, precisely so it never hardens into a third level of the navigational spine. See
`_workflow/decisions/D4-nineteen-family-cascade.md`.

---

## 5. Benchmark

The canonical entity. One file per benchmark at `data/benchmarks/{domain-family}/{id}.yaml`.

```yaml
id: swe-bench
name: SWE-bench
aliases: [SWEbench, "SWE Bench"]
tagline: Resolve real GitHub issues in large Python repositories.
description: |
  Multi-paragraph prose. What the task actually is, what it was built to measure,
  what is known about its weaknesses. Neutral register, no advocacy.

external_ids:                      # cross-registry join keys; see section 9
  epoch: "SWE-Bench verified"
  inspect_evals: swe_bench
  huggingface: princeton-nlp/SWE-bench
  papers_with_code: swe-bench      # pwc-archive provenance; see the licence firewall
  every_eval_ever: null
  benchmark_radar: null            # cross-reference only; we never ingest their content
croissant_url: https://huggingface.co/api/datasets/princeton-nlp/SWE-bench/croissant

# --- Facets (see 02-taxonomy.md) ---
domain:
  primary: code/repository-scale-se
  secondary: [agents-tooluse/software-agents, code/bug-repair]
capability: [planning, long-horizon-execution, tool-use, context-integration]
evaluation_method: [execution-tests]
designed_for_subjects: [agent-scaffold, instruction-tuned-model, full-product-pipeline]
lifecycle: active                  # `saturated` is derived, never hand-set

# --- Admissibility: the learned-entrant test (00 §6 A5, 15 §A3) ---
learned_entrant_evidence:          # >= 1 required for the entry to be in scope at all
  - {system: claude-opus-5, source: src-anthropic-opus5-announcement, observed_on: 2026-09-16}
evaluation_target: learned-system  # learned-system | numerical-method | human-population | mixed
execution_mode: automated          # automated | human-in-loop | wet-lab | physical-trial | panel
ground_truth_source: repository-tests
                                   # repository-tests | held-out-labels | simulation |
                                   # experimental | expert-panel | forecast-resolution | none
reproducible_by_third_party: true  # false for wet-lab and physical-trial benchmarks

data:
  access: fully-open
  refresh: versioned-releases
  data_provenance: [web-scraped, expert-authored]
  contamination_risk: high
  contamination_evidence: [src-2024-swebench-contamination]
  ceiling_anchor_type: none-known
  languages: [en]
  programming_languages: [python]
  modalities: [text, code]
  size: {items: 2294, unit: issues}
  submission_limit: null           # {max_submissions, period_days, per, source} -- shape fixed in 02 §7
training_data_eligibility_tiers: []   # [{id, label, rule, source}] -- Matbench Discovery, Virtual Cell

governance:
  maintainer_type: academic-lab
  maintainers: [org-princeton-nlp]
  submission_process: self-reported
  independence_flags: [no-known-conflict]

execution:
  compute_tier: api-credits-only
  reproducibility_tier: fully-automatable
  est_runtime_hours: {min: 2, max: 30}
  est_cost_usd: {min: 50, max: 2000}
  est_participant_cost_usd: null   # ranged; `basis` mandatory when non-null (CACHE, RoboCup, A2RL)
  participant_cost: null           # non-null where entry costs real money (see CACHE, section 13)
  runnable_via: [inspect]          # inspect | lm_eval | helm | custom | none -- what a runner could drive
  inspect_evals_id: swe_bench      # null when absent from UK AISI's inspect_evals
  inspect_evals_available: true    # DERIVED from `inspect_evals_id != null`; never hand-set

comparability:                     # see section 8
  profile: execution-tested-agentic
  material_extra: [scaffold, harness]
  material_waived: []
  rating_pool_required: false      # true for Elo-shaped benchmarks (Kaggle Game Arena, RoboArena)

reference_conditions: cond-7f21a4d0e9bc  # EvalConditions ref, nullable. SOTA and therefore headroom
                                         # are null when this is null -- see 02 §8's SOTA rule
aggregation_policy: official-aggregate   # official-aggregate | community-aggregate | none-by-design
headline_metric: resolve-rate            # null when aggregation_policy is none-by-design
no_legitimate_aggregate: false           # true forbids the UI rendering any single headline number
secondary_axes: []                       # subset of [cost, latency, throughput, energy, reliability]

liveness:                          # raw observations; mostly machine-refreshed; see 07
  repo_last_commit: 2026-08-19
  leaderboard_last_updated: 2026-09-12
  reproduction_script_present: true
  reproduction_script_verified: null     # null = we have not checked, not "it fails"
  last_checked: 2026-09-16

maintenance_status: actively-maintained  # DERIVED from `liveness` by 02 §8's probe protocol.
                                         # Five terms; never hand-set. `unobservable` is a real value.
maintenance_status_contested: false      # hand-set; requires the two fields below when true
contested_source: null
contested_statement_date: null

homepage: https://www.swebench.com
repository: https://github.com/princeton-nlp/SWE-bench
license: MIT
license_notes: Task data MIT; underlying repositories carry their own licenses.

versions: [...]        # see BenchmarkVersion
subsets: [...]         # see Subset
metrics: [...]         # refs into data/metrics/
leaderboards: [...]    # refs into data/leaderboards/
baselines: [...]       # see Baseline

lineage:
  supersedes: []
  superseded_by: []
  subset_of: null
  extended_by: [swe-bench-verified, swe-bench-multimodal, swe-bench-pro]
  decontaminates: null
  correlates_with: [{benchmark: livecodebench, coefficient: null, source: null}]

tags: [agentic, verifiable-reward, long-context]

ingestion: null                    # non-null only for machine-ingested records; see section 9
curation:
  added_by: <handle>
  added_on: 2026-09-16
  last_verified: 2026-09-16
  verification_status: primary-source-verified
  stewardship: current                   # current | lapsed -- see 00 §8.2; set by CI at 24 months
                                         # unverified, never by hand
  sources: [src-swebench-paper-2023, src-swebench-repo]
  confidence: high
  notes: |
    Item count is for the original split, not Verified (500) or Lite (300).
```

### Field rules and why they exist

- `tagline` is one sentence under 120 characters for a non-specialist. It is the only prose on cards
  and in the Atlas hover, so it carries disproportionate weight.
- `description` may not contain comparative or promotional language. The failure mode is entries
  becoming advocacy for benchmarks the curator likes.
- `contamination_risk` above `medium` requires at least one entry in `contamination_evidence`, and
  CI enforces it. This is constraint 4 made mechanical: contamination is the claim readers most
  want and the claim most often asserted without evidence.
- `size.unit` is free text, because benchmarks count wildly different things -- issues, images,
  episodes, protein targets, trajectories, forecast grid cells, compounds purchased, CTF challenges.
  A closed enum here was tried and abandoned in the earlier draft for good reason.
- `correlates_with` carries an optional measured coefficient and its source. Empty is fine; an
  unsourced number is not.
- `aggregation_policy: none-by-design` exists because WeatherBench 2's authors explicitly state it
  is "a tool to compare different approaches on different aspects", not a challenge with one
  ranking, and ReXrank deliberately publishes eight metrics and no aggregate. When this flag is set
  the site refuses to render a single headline number for the benchmark at all. This is the
  comparability thesis validated by other people's benchmarks, and modelling it costs one enum.
- `liveness` is differentiator (iv) in schema form. One study found 137 of 195 safety benchmarks had
  stale repositories and BetterBench found 17 of 24 had no working reproduction script; no existing
  catalogue marks benchmarks as dead. `reproduction_script_verified: null` is deliberately distinct
  from `false` -- we have not checked is not the same as it does not work.
- `participant_cost` is normally null and exists for the cases where entering the benchmark costs
  money in the physical world. CACHE requires teams to have compounds synthesised; A2RL requires a
  drone. A benchmark nobody can afford to enter has a different meaning than one anybody can run.
- `external_ids` is the interop surface. `every_eval_ever` in particular is the join key for the
  alliance described in [01-landscape-and-positioning.md](01-landscape-and-positioning.md): they
  hold the result records, we hold the benchmark entity, and a stable shared id is the whole
  mechanism. `benchmark_radar` is a cross-reference for readers only -- their content is
  CC BY-NC-SA 4.0 and must never be ingested.
- `croissant_url` points at the MLCommons Croissant record for the underlying dataset where one
  exists (HuggingFace serves one per dataset at `/api/datasets/{name}/croissant`). This field is
  also the anchor for the proposed `croissant-benchmark` extension: our Benchmark entity is designed
  to be expressible as a namespaced JSON-LD extension of Croissant, which has no
  evaluation/benchmark extension today. Note the constraint: the Croissant spec is CC BY-ND, so we
  may publish a namespaced extension but may never republish a modified spec.
- **The admissibility block** (`learned_entrant_evidence`, `evaluation_target`, `execution_mode`,
  `ground_truth_source`, `reproducible_by_third_party`) is what makes the scoping rule in
  [00-vision-and-scope.md](00-vision-and-scope.md) §6 A5 enforceable instead of tasteful. A benchmark
  is in scope when at least one entrant is a learned system **and the entry cites evidence for it**;
  `learned_entrant_evidence` is a list of `{system, source, observed_on}` and tier-3 validation fails
  an entry with an empty list. The other four fields exist because the exclusion has to be
  *recordable*: a CMIP-style numerical-methods intercomparison is out, and the reason it is out is
  `evaluation_target: numerical-method` plus an empty evidence list, not a curator's memory. Without
  this block a curator meets their first hard case around entry 60, cannot record why it was
  excluded, and the exclusion becomes an undocumented editorial judgement — which is constraint 4
  broken from the inside.
- **`reference_conditions`** is a nullable `EvalConditions` reference and is the single most
  load-bearing nullable field in the schema, because [02-taxonomy.md](02-taxonomy.md) §8's SOTA rule
  is undefined without it: no reference conditions means no SOTA, which means `headroom: null` and a
  UI that says "no reference conditions declared" rather than rendering a blank. It is a reference
  rather than an inline block so the same conditions record can be shared with the claims that meet
  it, which is how the comparison view can say *this claim is at reference conditions* mechanically.
- **`maintenance_status` is derived and `liveness` is its input**, and the two are not
  interchangeable. `liveness` holds raw observations; `maintenance_status` is the five-term verdict
  over them, computed weekly by the probe protocol [02-taxonomy.md](02-taxonomy.md) §8 owns. Neither
  is `lifecycle`, which answers a different question entirely — the instrument's standing, ten terms,
  none of them `stale`, `abandoned` or `unobservable`. The three contest fields exist because
  flipping a live benchmark to `abandoned` is a public factual claim about a third party made by an
  automated rule, and an automated death notice with no appeal path is an accusation rather than a
  disclosure. CI asserts `contested_source` and `contested_statement_date` are present whenever
  `maintenance_status_contested` is true.
- **`curation.stewardship`** is `current | lapsed` and is set mechanically, never by hand: an entry
  unverified for 24 months becomes `lapsed`, stays visible and searchable, renders "not maintained by
  this index since <date>", is excluded from the verified fraction in `curation_confidence`, and is
  excluded from published gap claims. Requested by
  [00-vision-and-scope.md](00-vision-and-scope.md) §8.2 for a reason worth repeating: the failure
  mode is not going stale, it is going stale *invisibly*, and an explicit lapsed state is the
  cheapest available defence against becoming the next Ecosystem Graphs.
- **`runnable_via` and `inspect_evals_id`** are Phase-0 fields even though the execution layer is
  deferred to the last phase. [13-execution-runners.md](13-execution-runners.md) §3.1 argues the
  case and this document owns the fields: `runnable_via` is what the suite builder reads to tell a
  user whether a benchmark can be driven by a harness they already have, which is useful with or
  without an execution layer of our own, and `inspect_evals_available` is derived from
  `inspect_evals_id` rather than hand-set so the two can never disagree.
- **`no_legitimate_aggregate` and `secondary_axes`** are a pair. The first refuses a headline number;
  the second names the axes a benchmark reports that are not the score — cost, latency, throughput,
  energy, reliability — so the comparison view can show them without inventing a composite.

### Benchmark field reference

The prose above explains *why*; this table is what the Pydantic model is written from, and it is the
table an implementer needs on day two. **Required at** distinguishes the two admissible completeness
states: `stub` is the minimum an entry may be merged at, `full` is what
[02-taxonomy.md](02-taxonomy.md) §14 requires before an entry counts toward a family's seed target.
Where a vocabulary file is named, its values are loaded at import time and become a dynamic
`Literal` (§12), so this column doubles as the dependency list for schema regeneration.

| Field | Type | Required at | Vocabulary | Default | Tier |
| --- | --- | --- | --- | --- | --- |
| `id` | slug, `^[a-z0-9][a-z0-9-]{1,62}$` | stub | — | — | 1 |
| `name` | str | stub | — | — | 1 |
| `aliases[]` | list[str] | never | — | `[]` | 1 |
| `tagline` | str, <= 120 chars | stub | — | — | 1 (4 for length) |
| `description` | str, multi-paragraph | full | — | `null` | 1 |
| `external_ids.*` | map[str, str \| null] | never | fixed key set | all `null` | 1 |
| `croissant_url` | URL \| null | never | — | `null` | 1 |
| `domain.primary` | str | stub | `taxonomy/domains.yaml`, leaf only | — | 2 |
| `domain.secondary[]` | list[str] | never | `taxonomy/domains.yaml`, leaf only | `[]` | 2 |
| `capability[]` | list[str] | full | `taxonomy/capabilities.yaml` | `[]` | 2 |
| `evaluation_method[]` | list[str] | full | `taxonomy/evaluation-methods.yaml` | `[]` | 2 |
| `designed_for_subjects[]` | list[str] | full | `taxonomy/subjects.yaml` | `[]` | 2 |
| `lifecycle` | str | stub | `taxonomy/lifecycle.yaml` (ten terms) | `active` | 1 |
| `learned_entrant_evidence[]` | list[{system, source, observed_on}] | stub, >= 1 | — | — | 3 |
| `evaluation_target` | enum | stub | inline, 4 values | — | 1 |
| `execution_mode` | enum | full | inline, 5 values | — | 1 |
| `ground_truth_source` | enum | full | inline, 7 values | — | 1 |
| `reproducible_by_third_party` | bool | full | — | — | 1 |
| `data.access` | str | stub | `taxonomy/access.yaml` | — | 1 |
| `data.refresh` | str | full | `taxonomy/refresh.yaml` | — | 1 |
| `data.data_provenance[]` | list[str] | full | `taxonomy/data-provenance.yaml` | `[]` | 2 |
| `data.contamination_risk` | str | full | `taxonomy/contamination.yaml` | `unknown` | 3 |
| `data.contamination_evidence[]` | list[Source ref] | conditional | — | `[]` | 3 |
| `data.ceiling_anchor_type` | str | full | `taxonomy/ceiling-anchors.yaml` (ten terms) | `none-known` | 1 |
| `data.size` | {items: int \| null, unit: str} | full | `unit` is free text | — | 1 |
| `data.submission_limit` | {max_submissions, period_days, per, source} \| null | never | — | `null` | 1 |
| `training_data_eligibility_tiers[]` | list[{id, label, rule, source}] | never | — | `[]` | 3 |
| `governance.maintainer_type` | str | full | `taxonomy/governance.yaml` | — | 1 |
| `governance.maintainers[]` | list[Organization ref] | full | — | `[]` | 2 |
| `governance.submission_process` | str | full | `taxonomy/submission.yaml` | — | 1 |
| `governance.independence_flags[]` | list[str] | full | `taxonomy/independence.yaml` | `[]` | 3 |
| `execution.compute_tier` | str | full | `taxonomy/compute-tiers.yaml` | — | 1 |
| `execution.reproducibility_tier` | str | full | `taxonomy/reproducibility.yaml` | — | 1 |
| `execution.est_runtime_hours` | {min, max} \| null | never | — | `null` | 1 |
| `execution.est_cost_usd` | {min, max} \| null | never | — | `null` | 1 |
| `execution.est_participant_cost_usd` | {min, max, basis} \| null | never | `basis` mandatory when non-null | `null` | 3 |
| `execution.runnable_via[]` | list[enum] | full | inline: `inspect`, `lm_eval`, `helm`, `custom`, `none` | `[none]` | 1 |
| `execution.inspect_evals_id` | str \| null | never | — | `null` | 1 |
| `execution.inspect_evals_available` | bool, **derived** | — | — | computed | 3 |
| `comparability.profile` | str | full | `taxonomy/comparability-profiles.yaml` | derived from facets | 2 |
| `comparability.material_extra[]` | list[str] | never | `EvalConditions` field names | `[]` | 3 |
| `comparability.material_waived[]` | list[{field, reason}] | never | — | `[]` | 3 |
| `comparability.rating_pool_required` | bool | full | — | `false` | 3 |
| `reference_conditions` | EvalConditions ref \| null | never | — | `null` | 2 |
| `aggregation_policy` | enum | full | inline, 3 values | `official-aggregate` | 1 |
| `headline_metric` | Metric ref \| null | conditional | — | `null` | 3 |
| `no_legitimate_aggregate` | bool | full | — | `false` | 3 |
| `secondary_axes[]` | list[enum] | never | inline, 5 values | `[]` | 1 |
| `liveness.*` | see the §5 exemplar | machine-written | — | all `null` | 1 |
| `maintenance_status` | str, **derived** | — | `taxonomy/maintenance.yaml` (five terms) | computed | 3 |
| `maintenance_status_contested` | bool | never | — | `false` | 3 |
| `contested_source` | Source ref \| null | conditional | — | `null` | 3 |
| `contested_statement_date` | date \| null | conditional | — | `null` | 3 |
| `homepage` | URL | stub | — | — | 1 |
| `repository` | URL \| null | never | — | `null` | 1 |
| `license` | SPDX str or free text | full | — | — | 1 |
| `license_notes` | str \| null | never | — | `null` | 1 |
| `versions[]` | list[BenchmarkVersion], **inline** | full | — | `[]` | 1 |
| `subsets[]` | list[Subset], **inline** | never | — | `[]` | 1 |
| `metrics[]` | list[Metric ref] | full | — | `[]` | 2 |
| `leaderboards[]` | list[Leaderboard ref] | never | — | `[]` | 2 |
| `baselines[]` | list[Baseline], **inline** | never | — | `[]` | 3 |
| `lineage.*` | refs into `Benchmark` | never | — | empty | 2 |
| `tags[]` | list[str], free text | never | — | `[]` | 4 |
| `ingestion` | the `ingestion` block \| null | machine-written | — | `null` | 3 |
| `curation.added_by` | handle | stub | — | — | 1 |
| `curation.added_on` | date | stub | — | — | 1 |
| `curation.last_verified` | date | stub | — | — | 4 |
| `curation.verification_status` | str | stub | 05 §4's six-value ladder | `ai-drafted-unverified` | 1 |
| `curation.stewardship` | enum, **derived** | — | `current \| lapsed` | `current` | 3 |
| `curation.sources[]` | list[Source ref] | stub, >= 1 | — | — | 2 |
| `curation.confidence` | enum | full | `low \| medium \| high` | `medium` | 4 |
| `curation.notes` | str \| null | never | — | `null` | 1 |

**Four conventions this table encodes, stated once so they are not re-derived per entity.**
`versions`, `subsets` and `baselines` are **inline objects** inside the benchmark file, because they
have no independent identity and a file per subset would multiply the file count for no navigational
gain; `metrics`, `leaderboards`, `Organization` and every `Source` are **id references** into their
own trees, because they are shared across benchmarks. A field marked **derived** may never appear in
a hand-written YAML file at all — tier-3 validation rejects the file rather than overwriting the
value, which is principle three in §1 made mechanical. `Required at: conditional` always means a
named tier-3 cross-field rule, never a vague "sometimes". And an omitted optional field means the
default in the table, so `bench new` emits the defaults explicitly rather than leaving keys out: an
absent key and an explicit `null` must never mean different things, because the moment they do,
every consumer has to know which one a given file used.

---

## 6. BenchmarkVersion, Subset, Metric

### BenchmarkVersion

Benchmarks change, and comparing across versions as though they were one is the most common silent
error in the ecosystem. FrontierMath makes the case unanswerable: Epoch reissued a corrected
FrontierMath on 2026-06-12 after finding errors in 42% of problems. A score reported against
"FrontierMath" without a version is now uninterpretable.

```yaml
- version: verified
  label: SWE-bench Verified
  version_kind: revision          # revision | edition | track-set
  released: 2024-08-13
  items: 500
  changes: |
    Human-validated subset; removed underspecified issues and broken test environments.
  breaking: true                  # scores not comparable to prior versions
  supersedes_version: full
  errata:
    - date: null
      scope: null
      description: null
      source: null
  frozen: true                    # false for rolling/live benchmarks
  sources: [src-openai-swebench-verified]
```

`breaking: true` is load-bearing: it is what lets the comparison workbench refuse to plot two
numbers on one axis. `errata[]` is new, added because FrontierMath forced it and because CASP,
Tox21 and several others have published post-hoc corrections that changed published standings.
`version_kind: edition` handles the CASP17 / DCASE 2026 / BraTS 2026 / LifeCLEF case where the
"version" is an annual re-competition with new data rather than a revision of the same items;
editions are always `breaking: true`.

### Subset

Benchmarks decompose, and per-subset results are where most real analysis happens. MMLU has 57
subjects, DCASE 2026 has 7 unrelated tasks, BraTS 2026 is five challenges in a trench coat, GeoBench
publishes 5 photo splits x 5 metrics, VideoMME reports 12 sub-scores.

```yaml
- id: mmlu#college-chemistry
  label: College Chemistry
  items: 100
  scored_separately: true
  domain_override: {primary: chemistry-materials/molecular-property-prediction}
  capability_override: [knowledge-recall, quantitative-reasoning]
  metric_override: null
  notes: null
```

Subsets inherit every facet from the parent and override selectively. This is what lets the coverage
map count MMLU's chemistry subject as chemistry coverage rather than pure language coverage -- a
distinction that materially changes the gap analysis, since a large fraction of apparent
"science coverage" in LLM benchmarks is actually a few dozen MCQ items inside a language benchmark.
Two levels render by default; deeper trees are permitted (BraTS edition -> sub-challenge -> lesion-wise
split is genuinely three levels) but are a smell worth reviewing.

### Metric

A separate entity because metrics are shared across benchmarks and routinely misunderstood.

```yaml
id: gdt-ts
name: GDT-TS
full_name: Global Distance Test -- Total Score
definition: |
  Percentage of residues in a predicted protein structure within defined distance
  cutoffs of the experimental structure after optimal superposition.
formula_reference: https://predictioncenter.org/casp16/doc/...
value_type: ratio            # ratio | count | duration | currency | elo | ordinal | categorical | vector | qualitative
range: {min: 0, max: 100}
unbounded: false
optimum: max                 # max | min | zero | target
higher_is_better: true       # retained for convenience; derived from `optimum`
chance_baseline: null
normalization_anchor: null   # see below
aggregation: mean-over-targets
units: percent
requires_pool: false
headroom_computable: true
must_report_with: []         # metric ids that may never be shown without this one
domains: [biology-genetics/protein-structure-prediction]
pitfalls: |
  Insensitive to local errors; high GDT-TS is compatible with functionally wrong
  side-chain placement. Not comparable across target difficulty classes.
sources: [src-gdt-definition]
```

Five fields here are new and each was forced by a specific benchmark:

- **`optimum`** replaces the assumption that higher is better. WMDP is explicitly lower-is-safer.
  BBQ's bias scores `s_AMB` and `s_DIS` have an optimum of zero, not a maximum, and are reported
  alongside accuracy. Headroom against a zero-optimal metric is a different computation and the
  build must know which it is doing.
- **`unbounded` and `requires_pool`** exist for Elo. A Kaggle Game Arena rating is unbounded, pool-
  dependent, and changes when a *different* model joins with no change to the model under test.
- **`headroom_computable: false`** is the honest exit. Headroom consumed is the only legitimate
  cross-domain axis (constraint 3), and for Elo, for unbounded human-normalised Atari scores, and
  for metrics with no defined ceiling, it simply does not exist. The site shows a hole, not an
  estimate. Filling that hole with a guess would be exactly the single-number thinking the project
  rejects.
- **`normalization_anchor`** generalises the ceiling beyond humans. The Virtual Cell Challenge 2026
  scales six metrics between the cell-context mean (floor) and *a real biological replicate
  experiment* (ceiling). WeatherBench 2's comparator is an operational NWP supercomputer. Brain-Score
  normalises by a neural noise ceiling. "Human baseline" is the common case, not the general one.
- **`must_report_with`** encodes the pairs that are lies in isolation: Open ASR's WER without RTFx
  (speed is on the leaderboard axis, so a score without hardware is meaningless), AgentDojo's utility
  without attack-success-rate, BBQ's bias without accuracy, HLE's accuracy without calibration error.
  The UI refuses to render one without the other.

`chance_baseline` and `range` are what make headroom computable at all, and they are rarely
published. The Epoch snapshot is a genuinely useful source here: 21 of its 81 benchmarks carry a
non-zero `random_baseline` (GPQA diamond 0.25, PIQA 0.5, Winogrande 0.5, HLE 0.048, Chess Puzzles
0.0496, SimpleBench 0.1667, DTBench 0.4), and three carry a measured `score_ceiling` below 1.0
(FrontierMath-2025-02-28-Private 0.57, FrontierMath-Tier-4 0.6, LMCA 0.85). Note carefully that a
`score_ceiling` is a *measurement ceiling*, not a human baseline, and conflating the two would be a
real error -- they go in different fields.

`pitfalls` renders inline wherever the metric appears. A metric's known failure modes should be
unavoidable, not buried in a footnote.

---

## 7. System, SystemVersion, ResultClaim, Baseline

### System and SystemVersion

A model, agent, pipeline, policy or team that gets evaluated. Deliberately thin: only what is needed
to interpret a result. This is not a model directory (constraint 5), and the boundary is enforced by
the "what we do not model" list in section 11.

```yaml
id: claude-opus-5
name: Claude Opus 5
organization: org-anthropic
system_type: reasoning-model         # facet 4 vocabulary; see 02-taxonomy.md
modalities_in: [text, image]
modalities_out: [text]
open_weights: false
license: proprietary
license_class: api-access            # api-access | hosted-no-api | open-unrestricted | open-restricted | open-noncommercial | unreleased
api_identifier: claude-opus-5
first_released: 2026-05-XX
built_on: []                         # non-empty for scaffolds and pipelines
parameters_disclosed: false
parameter_count: null
training_compute_disclosed: false
training_compute_flop: null
training_compute_estimated: null     # true | false | null
training_compute_notes: null
availability: generally-available    # generally-available | limited-preview | research-only |
                                    # deprecated | retired | never-released
retired_on: null                    # date the endpoint or weights stopped being obtainable
external_ids: {epoch_model_group: "Claude Opus 5"}
versions:
  - version: "2026-05"
    released: 2026-05-XX
    api_identifier: claude-opus-5-20260501
    deprecated: false
    notes: null
sources: [src-anthropic-opus5-announcement]
```

`availability` and `retired_on` exist because a result claim about a system nobody can obtain any
more is a different kind of fact from one a reader can go and reproduce this afternoon, and the
comparison view has to be able to say so. Requested by [15-open-questions.md](15-open-questions.md)
§C3 and unmodelled until this pass. `retired_on` is nullable and is required only when
`availability` is `deprecated` or `retired`; `never-released` covers the internal systems that
appear in papers and on no endpoint, which the non-LLM domains produce constantly.

`parameters_disclosed` is a distinct field from `parameter_count` because "unknown" and "not
disclosed" are different states from "small", and conflating them is exactly how speculative
parameter counts leak into indexes as fact. The same reasoning produces `training_compute_disclosed`
alongside `training_compute_flop`.

The compute fields are new, added because Epoch has them for 337 of 1,063 model rows and nobody else
publishes them in a catalogue -- they enable compute-versus-capability analysis that no other
benchmark index can do. But they carry a trap that must be modelled: Epoch's own
`Training compute notes` distinguish honest arithmetic
(`"6 FLOP / parameter / token * 22*10^9 active parameters * 36000000000000 tokens = 4.752e+24 FLOP"`)
from circular imputation
(`"Training compute imputed to be 1.58e25 FLOP from benchmark scores"`). The second kind is compute
inferred *from* benchmark scores and using it as an independent variable against benchmark scores
would be a straightforward methodological error. `training_compute_estimated: true` plus the verbatim
notes make the distinction visible, and the analytics layer
([12-analytics-and-trends.md](12-analytics-and-trends.md)) must exclude imputed values from any
compute-versus-performance plot.

Agent scaffolds are Systems with `system_type: agent-scaffold` and a populated `built_on`, because
"which base model was under the scaffold" is the first question every reader has. Human teams,
human-AI teams and classical algorithms are Systems too -- CASP ranks human-expert groups separately
from automated servers, and MLE-bench's comparator is thousands of real Kaggle competitors.

### ResultClaim

The most important entity. Not a score -- a claim that someone made about a score.

```yaml
id: claim-3c8e10ba55f7          # content-derived; see 05 §2 for the derivation
system: claude-opus-5@2026-05
benchmark: swe-bench@verified
subset: null
metric: resolve-rate
claim_type: absolute          # absolute | pairwise | rating | ordinal | qualitative
value: 0.XXX
value_text: null              # used when claim_type is ordinal/qualitative
opponent: null                # pairwise claims only
rating_pool: null             # rating claims only; ref into data/rating-pools/
uncertainty:
  type: stderr                # stderr | ci95 | ci90 | range | iqr | none
  value: 0.012
  n_runs: 5
serving_provider: null        # org ref; non-null when the number came from a third-party host
date_reported: 2026-05-XX
reported_by: org-anthropic
verification: self-reported
disputed_by: []
resolution_status: resolved   # pending | partial | resolved
resolved_as_of: null
source: src-anthropic-opus5-announcement
artifact_url: null            # transcript, .eval log, submission bundle
artifact_archived: null
provenance_snapshot: null     # the upstream record exactly as retrieved; see below
external_ids:
  eee_result_id: null         # Every Eval Ever's result id, when this claim exists there too
eval_conditions: cond-7f21a4d0e9bc
result_group: null            # binds claims that must be shown together
superseded_by: null
ingestion: null
notes: |
  Reported in launch blog post; no per-instance outputs published.
```

Six fields are new. `claim_type`, `opponent` and `rating_pool` exist because RoboArena scores
double-blind pairwise comparisons between policy pairs on physical DROID hardware with no fixed task
set, and Kaggle Game Arena publishes Elo from all-play-all with 40 games per pair. Neither is an
absolute score and forcing them into a `value` field would be a lie. `resolution_status` exists
because ForecastBench and Metaculus FutureEval ask questions whose answers do not exist at
submission time; a score there is provisional for months or years and is retroactively updated.
`artifact_url` exists because the Epoch snapshot contains 828 public Inspect-AI `.eval` logs on S3,
which is real evidence, and the earlier schema had nowhere to put it. `serving_provider` exists
because Epoch's model identifiers mix hosting into identity -- `accounts/fireworks/models/glm-4p6`,
`chutes/DeepSeek-R1-0528` -- and a number produced on a third-party host with unknown quantisation
is not the same number as one from the first-party API.

**`provenance_snapshot` is the fourth of the four C5 pre-ingest schema additions and the one most
easily confused with something that already exists.** It is *not* `ingestion.field_provenance`:
that map records which of *our* fields came from where, whereas `provenance_snapshot` is the
**upstream record frozen as retrieved**, which is what makes an ingested claim re-derivable at a
commit hash by somebody who is not us. Its shape is
`{source_record_id, retrieved_at, content_sha256, raw: <the upstream row, verbatim>}`, and for a
tabular source `raw` is the row's own key-value mapping rather than a re-serialisation of it. It
stays small — an Epoch row is a few hundred bytes — and it is the difference between "we can show
our working" and "trust us". Without it, correcting an upstream error six months later means
guessing what upstream said at ingest time. Retrofitting it across 6,598 rows is exactly the pain
C5 warns about, which is why it lands before the first adapter run, not after.

`external_ids.eee_result_id` is the claim-level counterpart of
`Benchmark.external_ids.every_eval_ever`. The alliance argument in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §14 — they own the result
registry, we own the benchmark registry — is only real if a claim can be joined in both directions,
and a benchmark-level join alone cannot say *which* of their results corresponds to which of ours.

`result_group` is how two-axis results stay honest: AgentDojo's utility and targeted-attack-success
rate, BBQ's bias and accuracy, Open ASR's WER and RTFx are each stored as separate claims bound by a
shared group id, and the renderer will not show one member of a group alone.

### The verification ladder

Ordered, rendered as a visible badge everywhere a number appears, with the rank stored once in
`taxonomy/verification.yaml` rather than re-argued per claim.

| Rank | Level | Meaning | Typical evidence |
| --- | --- | --- | --- |
| 1 | `self-reported` | The evaluated party reported it; no independent check | Launch blog, technical report |
| 2 | `maintainer-verified` | Benchmark maintainer confirmed or ran it | Official leaderboard entry with a review step |
| 3 | `independent-reproduction` | A third party re-ran it and published how | Epoch's 828 public Inspect-AI `.eval` logs |
| 4 | `held-out-server` | Scored against a test set the submitter never saw | CARLA Leaderboard, Grand Challenge type-2, FrontierMath |
| 5 | `prospective-experiment` | Ground truth did not exist at submission and was generated afterwards by the evaluator | CACHE wet-lab assays, Virtual Cell replicates, ForecastBench resolution |
| 6 | `third-party-audited` | Formal audit with published methodology | A published audit report |
| 7 | `sandboxed-rerun` | Re-run by this project's own execution layer | Deferred; see [13-execution-runners.md](13-execution-runners.md) |

**Correction to the earlier draft: `disputed` is not a rung, it is a state.** A held-out-server
number can be disputed; so can a self-reported one. Disputes are carried by `disputed_by[]`, each
entry pointing at a Source, and rendered as an overlay badge on top of whatever level the claim
holds. Modelling dispute as a level meant a disputed claim silently lost its verification
information, which is backwards.

`prospective-experiment` is new and sits above `held-out-server` because a held-out test set exists
and could in principle leak, whereas a measurement taken after submission cannot have contaminated
the submission. It is also the only rung that fits a multi-year wet-lab challenge, and it covers the
forecasting benchmarks where the world supplies the answer key.

**Default sort in every comparison view is verification rank first, then value.** Making the
strongest claim also the least verified is common, and the UI should make that visible rather than
rewarding it with the top row. The Epoch ingest makes this rule urgent rather than theoretical:
after ingestion, roughly 5,048 of our claims will be `self-reported` leaderboard scrapes and 828
will be `independent-reproduction`. A value-first sort would bury the good ones.

#### Machine assignment rule for the Epoch adapter

Encoded once in the adapter rather than per record: Epoch-run file AND `Logs` URL contains `-public` -> `independent-reproduction` with the
`.eval` URL in `artifact_url` (828 rows); Epoch-run with a `-private` or blank log ->
`maintainer-verified` (459 rows, including all of FrontierMath); everything external ->
`self-reported` (5,048 rows). Rungs 4 through 7 are never machine-assigned.

### Baseline (was HumanBaseline)

```yaml
- id: base-swebench-expert
  benchmark_version: swe-bench@verified
  kind: human-expert-average   # --- ceiling kinds, one-to-one with 02 §7's ceiling_anchor_type ---
                               # human-crowd-average | human-crowd-best | human-expert-average |
                               # human-expert-best | theoretical-maximum | measured-ceiling |
                               # experimental-replicate | operational-system | noise-ceiling
                               # --- floor kinds, which have no ceiling_anchor_type counterpart ---
                               # classical-algorithm | random-chance | field-practice-reference
  metric: resolve-rate
  value: 0.XXX
  value_absent_reason: null    # no-published-comparator | not-applicable | not-yet-measured
  n_humans: 12
  population: Professional software engineers, 3+ years Python
  time_limit: unlimited
  is_primary: true             # exactly one primary per (benchmark_version, metric)
  source: src-...
  notes: null
```

Renamed from `HumanBaseline` and generalised, because the domain recon showed the human assumption
fails constantly. WeatherBench 2's comparator is the ECMWF IFS/ENS operational model and a human
baseline is meaningless. The Virtual Cell Challenge's ceiling is a wet-lab replicate. Matbench
Discovery has no human comparator at any point. Atari-100k's human-normalised score is unbounded
above 100%. The facet is `ceiling_anchor_type` in [02-taxonomy.md](02-taxonomy.md) -- renamed from
`human_baseline_type` on 2026-09-21, because `operational-system`, `noise-ceiling`,
`experimental-replicate` and `theoretical-maximum` are not human and the old name made those
benchmarks look defective -- and it remains the benchmark-level summary used for filtering. The
entity is `Baseline` with a `kind`. `human_baseline_type` is a **forbidden identifier**: CI greps an
explicit allowlist of paths -- `data/`, `taxonomy/`, `src/`, `scripts/` -- and fails on any
occurrence. The exclusions are declared rather than accidental. `docs/`, `adr/`, `CHANGELOG.md` and
the `_plan/` documents are never scanned, because a rename has to stay explainable and the
explanation has to name the old identifier. `taxonomy/forbidden-identifiers.yaml` and
`taxonomy/retired-ids.yaml` are excluded from the scan of `taxonomy/` for the same reason: listing
dead identifiers is their job, and a naive grep over `taxonomy/` fails against the check's own
configuration file. See check 9a in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §9.

**Twelve kinds, and the split into ceilings and floors is deliberate.** Nine of them are the stored
counterpart of `ceiling_anchor_type`, the ten-term facet owned by [02-taxonomy.md](02-taxonomy.md)
§7 (`none-known`, the tenth, is the *absence* of a ceiling and is expressed here by
`value_absent_reason` rather than by a `kind`). The remaining three — `classical-algorithm`,
`random-chance`, `field-practice-reference` — are **floors**: the bottom of the meaningful scale, not
the top, which is why they are correctly absent from the ceiling facet. Two spellings changed in this
pass to close a live drift: `biological-replicate` became `experimental-replicate` to match the
facet, and `noise-ceiling` was added, without which Brain-Score — the benchmark
[02-taxonomy.md](02-taxonomy.md) §7 names as the sole reason that term exists — could not be stored
as a `Baseline` record at all. A third document should never restate either list:
**headroom computed from a vocabulary the schema cannot store is exactly the unsourced confident
number this project exists to oppose.**

Multiple baselines per benchmark are normal and often the point: ForecastBench carries both a
superforecaster and a general-public baseline, and Metaculus reports both; GPQA has PhD-expert
(~65-74%) and skilled-non-expert-with-web-access (~34%) baselines that tell very different stories.
Headroom is computed against the `is_primary` baseline and the choice is recorded and visible.

`value_absent_reason` matters more than it looks. OSWorld's published human baseline is 72.4% while
2026 top runs are 73.1-82.6% -- the human gap has inverted -- and a reader needs to know whether a
missing baseline means nobody measured it or the concept does not apply.

---

## 8. EvalConditions and the comparability rule

The crown jewel, and the field-level answer to differentiator #2. A separate entity so conditions
can be shared across claims, referenced, and diffed.

```yaml
id: cond-7f21a4d0e9bc            # content-derived; see 05 §2

# --- prompting ---
shots: 0
shot_selection: null            # fixed | random | retrieved | null
chain_of_thought: true
reasoning_effort: high          # enum: none|minimal|low|medium|high|xhigh|max, plus free text
reasoning_effort_raw: "high"    # verbatim provider string, always preserved
thinking_token_budget: 64000
prompt_template_hash: sha256:...
prompt_template_source: src-...

# --- agency and tools ---
tools_allowed: [bash, file-edit, search]     # EEE: agentic_eval_config.available_tools
scaffold: sys-anthropic-agent-harness@1.2
scaffold_source: src-...
harness: swe-bench-official@2.1
harness_source: src-...
max_steps: null
message_limit: null             # EEE: eval_limits.message_limit
token_limit: null               # EEE: eval_limits.token_limit
sandbox: docker                 # EEE: sandbox

# --- sampling and selection ---
sampling: {temperature: 1.0, top_p: null, seed: null}   # EEE: generation_config.generation_args
n_samples: 1
selection_strategy: single      # single | best-of-n | self-consistency | majority-vote |
                                # pass-at-k | pass-hat-k | avg-at-k | best-across-scorers
k: null
retries_allowed: 0
max_output_tokens: null
context_window_used: 200000

# --- grading ---
judge_model: null               # required when evaluation_method includes model-graded-judge
judge_model_version: null
judge_prompt_hash: null
grading_rubric_ref: null
human_in_loop: false
human_assistance: none          # none | permitted | required  (CASP human vs server categories)

# --- environment (non-LLM domains) ---
simulator: null                 # e.g. omnigibson
simulator_version: null         # BEHAVIOR scores are undefined outside a specific sim build
hardware_platform: null         # e.g. unitree-h1, agilex-cobot-magic, drone-a2rl-spec
venue: null                     # physical site for hardware trials
assay_protocol: src-...         # wet-lab protocol reference
lead_time: null                 # forecast horizon; material for weather and crop yield
resolution_window: null

# --- eligibility ---
eligibility_track: null         # Matbench Discovery compliance tier; ARC-AGI-3 official vs community
training_data_policy: null      # open | restricted-list | zero-shot-only | undeclared
decontamination_applied: false
subset_used: full

# --- cost and provenance of the run ---
hardware: null
wall_clock_hours: null
cost_usd: null
date_evaluated: 2026-05-XX
```

### The material fields

Two claims are comparable only when they agree on benchmark version, metric, subset, and the
**material** condition fields. Everything else -- temperature, wall-clock, cost, hardware for a
pure-accuracy metric -- is informative but non-material.

| Material field | Why it is material | Where it bites hardest |
| --- | --- | --- |
| `shots` | Changes scores by tens of points | MMLU, all classic LLM evals |
| `chain_of_thought` | Different task entirely | Reasoning benchmarks |
| `reasoning_effort` | 8-point spread on ARC-AGI within one model | Frontier LLMs |
| `tools_allowed` | CritPt goes from ~4% to ~10% with code tools | Science and agent evals |
| `scaffold`, `harness` | Terminal-Bench moves several points on harness alone | All agentic benchmarks |
| `selection_strategy`, `k`, `n_samples` | pass@1 and pass@4 are different measurements; `pass^k` is a reliability metric that averaging destroys | tau-bench, code benchmarks |
| `retries_allowed` | Silent best-of-n | Agentic |
| `judge_model` (+ version) | The judge is part of the apparatus | PaperBench (~8,316 rubric leaves), HealthBench, BixBench |
| `human_in_loop`, `human_assistance` | CASP ranks human-expert and automated-server groups separately | CASP, RNA-Puzzles |
| `subset_used` | The most common silent substitution | Everything |
| `simulator` + `simulator_version` | BEHAVIOR's score is undefined outside a specific OmniGibson/Isaac-Sim build | Robotics |
| `hardware_platform` | A policy on an H1 is not a policy on a Cobot-Magic | Robotics, drones |
| `eligibility_track` + `training_data_policy` | Matbench Discovery groups models by what they were allowed to train on; ARC-AGI-3 runs two leaderboards with different legality rules | Materials, general intelligence |
| `lead_time` | A 3-day and a 10-day forecast score are not the same number | Weather, crop yield |
| `decontamination_applied` | Changes what the number means | LLM evals on old data |

**The material set is per-benchmark-shaped, not global, and there is therefore no such number as
"the count of material fields at schema v1".** The table above is the *universe* of fields that are
material to some benchmark — sixteen rows over twenty-one field names — not a set any single
benchmark uses. `shots` is meaningless for a robotics sim benchmark; `simulator_version` is
meaningless for MMLU. Any surface that needs a denominator reads
`fields_material_total` off the benchmark's resolved profile at render time; a document that names a
constant instead has made a category error, and every percentage derived from that constant is
wrong for every benchmark whose profile is a different size. The profile is derived from the benchmark's
`evaluation_method` and `designed_for_subjects` facets via a lookup table in
`taxonomy/comparability-profiles.yaml`, with per-benchmark `comparability.material_extra[]` and
`material_waived[]` overrides. A waiver requires a reason string and shows up in the quality
dashboard, because the failure mode here is curators quietly waiving inconvenient fields until the
comparability check passes everything.

### Computing `comparability_key`

```
material  = profile(benchmark.evaluation_method, benchmark.designed_for_subjects)
            + benchmark.comparability.material_extra
            - benchmark.comparability.material_waived

tuple     = [benchmark_version, metric, subset]
            + [ canonicalise(conditions[f]) if conditions[f] is not None else "?"
                for f in sorted(material) ]

comparability_key        = sha256(json.dumps(tuple, separators=(",", ":")))[:16]
key_unknown_count        = tuple.count("?")
condition_completeness   = sum(w[f] for f in material if conditions[f] is not None)
                           / sum(w[f] for f in material)
```

Weights `w[f]` default to 1.0, with 2.0 for `judge_model` when the benchmark is model-graded and 2.0
for `scaffold` when the subject under test is an agent scaffold -- the fields whose absence does the
most damage count double.

### What the UI does with it

Three states, and the middle one is the interesting one:

1. **Same key, `key_unknown_count == 0` on both claims.** Comparable. Plot them together, silently.
2. **Same key, one or both with unknowns.** *Possibly* comparable. Plot them together with a
   persistent banner naming which material fields are unknown on which claim. Two claims that are
   both silent about chain-of-thought produce the same key, and it would be dishonest to present
   that as confirmed comparability -- they agree only in their ignorance.
3. **Different keys.** Refuse. Render a field-by-field diff of what differs instead of a chart. The
   refusal is the feature. Every competitor's instinct is the opposite: BenchmarkList's "Rosetta
   Stone method" aligns overlapping results onto one scale, Epoch's ECI fits a latent-ability IRT
   model across 58 benchmarks x 266 models, Artificial Analysis publishes an Intelligence Index. A
   catalogue whose signature behaviour is declining to rank is genuinely unoccupied ground and is
   the most defensible trust position available.

`condition_completeness` is displayed on every claim. A number whose conditions are half unknown
should look worse than a fully specified one, even when the value is higher. The honest expectation
after the Epoch ingest is a **mean around 0.10 for the LLM profiles Epoch's rows land on**, and the
basis has to be stated because the number is quoted in a dozen documents: across 6,598 rows Epoch
supplies `shots` on 19.4%, `reasoning_effort` on roughly 39% after suffix parsing, `tools_allowed`
on under 1%, and `chain_of_thought`, `retries_allowed`, `judge_model` and `human_in_loop` on 0% —
which sums to about 0.594 of a field filled per row, against a **six-field material profile**. The
denominator matters and is the thing an earlier draft left out: **`condition_completeness` is
per-profile, not global**, so the same rows score 0.054 against an eleven-field agentic profile and
0.037 against the full sixteen-row material table above. Quote the figure as "about 0.10 on a
six-field profile" or quote a profile with it; a bare 0.10 is a number nobody can check. **Approximately zero ingested claims will clear a 0.5 threshold**, and even
the best-documented external file (`deepswe_external.csv`, which has harness, reasoning effort, run
count, mean agent steps and a 95% CI) leaves five material fields null.

That number is not an embarrassment, it is the thesis. It is also why the Phase-3 target in
[14-roadmap.md](14-roadmap.md) must not be "500 claims" -- ingestion makes claim count free and
meets that target thirteen times over in one adapter run. The target has to be *"500 claims at
condition_completeness >= 0.6 with a named source and an archived URL"*, which measures our work
rather than Epoch's.

### Crosswalk to Every Eval Ever

EEE's `eval.schema.json` is CC BY 4.0 with MIT code and is our best alliance target. Where we share
a concept, we use their field name or record the mapping explicitly, so a result validated against
EEE can join our benchmark records on a stable id.

| Ours | EEE | Note |
| --- | --- | --- |
| `sampling.{temperature,top_p}`, `max_output_tokens` | `generation_config.generation_args.{temperature,top_p,max_tokens}` | Direct |
| `tools_allowed` | `agentic_eval_config.available_tools[]` | Direct |
| `message_limit`, `token_limit` | `eval_limits.{message_limit,token_limit}` | Direct |
| `sandbox` | `sandbox` (type + compose) | We store the type only; the compose file goes in `artifact_url` |
| `Metric.optimum`, `range`, `value_type` | `metric_config.{lower_is_better,min_score,max_score,score_type}` | Ours is a superset |
| `ResultClaim.source` + `reported_by` + `verification` | `source_metadata.{name,type,organization,evaluator relationship}` | Ours splits provenance from verification |
| `Benchmark.external_ids.every_eval_ever` | `evaluation_name` | The join key |

They own the result record; we own the benchmark entity. The mapping is what makes that division of
labour real rather than rhetorical.

---

## 9. Ingestion provenance

Ingestion is not a side channel, it is the majority of the records by volume, and CC-BY imposes an
attribution obligation that has to live in the data rather than in a page footer. A fork of the
repository must carry the attribution with it; a footer does not survive a fork.

### The `ingestion` block

Present on every machine-written record, null on hand-curated ones.

```yaml
ingestion:
  batch: ingest-epoch-2026-09-16          # -> data/_ingest/batches/ingest-epoch-2026-09-16.yaml
  source_adapter: epoch-benchmarks
  adapter_version: 0.3.1
  source_record_id: "swe_bench_verified.csv#model=claude-opus-5&metric=resolve-rate"
                                          # STABLE form: a content key, never a row ordinal.
                                          # See the note below -- "#row=17" is forbidden.
  last_seen_upstream: 2026-09-16          # the most recent run in which upstream still had this record
  source_url: https://epoch.ai/data/benchmark_data.zip
  source_licence: CC-BY-4.0
  licence_class: permissive-attribution   # permissive-attribution | share-alike |
                                          # non-commercial | no-redistribution | unlicensed
  source_attribution: >-
    Epoch AI, 'Capabilities & Benchmarking'. Published online at epoch.ai.
    Retrieved from 'https://epoch.ai/benchmarks' [online resource].
  ingested_at: 2026-09-16T23:14:00Z
  extraction_confidence: 0.9
  review_state: machine-ingested          # machine-ingested | spot-checked | human-reviewed | promoted
  reviewed_by: null
  reviewed_on: null
  field_provenance:
    value: source
    uncertainty: source
    eval_conditions.reasoning_effort: derived    # parsed from the model_version suffix
    eval_conditions.shots: absent
```

`review_state` is the flag the brief asks for and it has four values rather than two, because the
middle states are where the work actually happens: `machine-ingested` (written by an adapter, seen
by nobody), `spot-checked` (a human sampled the batch and approved the batch, not this record),
`human-reviewed` (a human looked at this record), `promoted` (re-derived from a primary source and
moved into the curated tree, at which point `ingestion` is retained for history but
`curation.verification_status` takes over).

`field_provenance` maps individual fields to `source` (verbatim from upstream), `derived` (computed
or parsed by the adapter), `absent` (upstream had nothing) or `curator` (a human edited this field
after ingest). Record-level provenance is not enough once a human touches one field of a
machine-ingested record, and a record that is half-scraped and half-hand-corrected with no way to
tell which is which is worse than either.

**`source_record_id` must be a content key, not a row ordinal, and this is ratified here rather than
left as a proposal in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md).** An
upstream CSV that gains a row at the top renumbers every ordinal beneath it, so `#row=17` makes the
next ingest look like thousands of deletions and thousands of insertions. The stable form is the
tuple of upstream columns that identify the record — for Epoch, file plus model version plus metric —
URL-encoded after the `#`. Adapters that genuinely cannot construct one declare
`source_record_id: null` and are restricted to full-replace semantics for that source.

**`last_seen_upstream` is how an upstream deletion becomes visible instead of silent.** A record whose
`last_seen_upstream` falls behind its batch's run date disappeared from the source, which is a fact
about the source worth surfacing — Papers with Code is the precedent for a whole corpus vanishing —
and it is never grounds for deleting our record. `IngestBatch` carries the matching
`resolver_snapshot_sha256`: the hash of the alias table as it stood when the batch ran, without which
a batch cannot be re-derived after the alias table is edited, and identity resolution is the single
largest manual cost in the ingest.

`extraction_confidence` is the adapter's own estimate, not a quality judgement -- a regex that
matched cleanly gets 1.0, a fuzzy header match gets 0.6, an LLM-classified field gets whatever the
classifier reports. It drives the review queue ordering, nothing else.

### IngestBatch

One file per adapter run that changed anything, at `data/_ingest/batches/{id}.yaml`. This is where
the licence and attribution text live once instead of 6,598 times.

```yaml
id: ingest-epoch-2026-09-16
adapter: epoch-benchmarks
adapter_version: 0.3.1
run_started: 2026-09-16T23:10:00Z
source:
  name: Epoch AI -- Capabilities & Benchmarking
  url: https://epoch.ai/data/benchmark_data.zip
  retrieved_at: 2026-09-16T23:14:00Z
  http_etag: "a95a0b35..."
  artefact_sha256: <sha256 of b.zip>
  artefact_bytes: 2292857
  upstream_version_handle: null
licence:
  spdx: CC-BY-4.0
  class: permissive-attribution
  redistribution_permitted: true
  share_alike: false
  non_commercial: false
  attribution_required: true
  attribution_text: >-
    Epoch AI, 'Capabilities & Benchmarking'. Published online at epoch.ai.
    Retrieved from 'https://epoch.ai/benchmarks' [online resource].
  source_record: src-epoch-benchmarks-2026-09
resolver_snapshot_sha256: "c4f1..."     # hash of taxonomy/aliases at run time; makes the run re-derivable
counts:
  benchmarks_seen: 81
  model_rows_seen: 1063
  claims_written: 6598
  unresolved: 0
target_tree: data/claims/_ingested/epoch/
notes: |
  Upstream publishes no DOI and no dated snapshot handle, so the retrieval timestamp plus the
  sha256 of the downloaded archive are our only immutable citation handle.
  (unverified -- confirm whether Epoch publishes a DOI'd snapshot elsewhere before citing one.)
```

The build emits `ATTRIBUTIONS.md` and a `NOTICE` file in every release by walking the batches, and
any page rendering an ingested record shows its attribution inline. That is the CC-BY obligation
discharged in a way that survives forking, because the obligation is stored where the data is.

### The licence firewall

`licence_class` is not decoration; CI enforces a placement rule from it.

| Class | Examples | Where records may live | Rule |
| --- | --- | --- | --- |
| `permissive-attribution` | Epoch (CC-BY-4.0), EEE (CC BY 4.0), lm-evaluation-harness (MIT), MTEB results (CC0) | `data/claims/_ingested/{adapter}/` and, after promotion, the CC-BY core | Attribution surfaced; free to redistribute |
| `share-alike` | Papers with Code archive (CC-BY-SA-4.0), Evaluation Cards (CC-BY-SA-4.0) | `vendor/pwc-archive/` only, quarantined | **Never enters the CC-BY core.** Must be re-derived from a primary source before promotion, and promotion replaces the field values rather than copying them |
| `non-commercial` | Benchmark Radar content (CC BY-NC-SA 4.0) | nowhere | Cross-reference by id only. Do not ingest |
| `no-redistribution` | Artificial Analysis | nowhere | Link and cite only |
| `unlicensed` | BenchmarkList, Stanford Ecosystem Graphs (no licence file) | nowhere | Facts about a benchmark may be independently re-sourced; their records may not be copied |

**Every row in that table is a reading of a third party's published terms as of 2026-09-17**, and
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8 owns the evidence, the `[M]/[D]/[E]/[U]`
grade behind each one and the outreach that resolves the unresolved ones. `licence_class` is
therefore a **field on `Source` carrying its own `licence_checked_on` date**, never a constant in the
loader: a classification that changes upstream and lives only in a plan document is a blocking CI
rule that will silently misfire, and a stale classification is a compliance failure rather than a
cosmetic one. `freshness.yml` re-opens any row whose `licence_checked_on` is more than a year old.
And the strongest word in the table needs its scope stated plainly: **`unlicensed` means "no licence
statement was found on 2026-09-17", never a claim that none exists.** BenchmarkList is a live
two-person commercial project that could publish terms tomorrow, and a plan that prints a permanent
judgement about someone else's licensing is careless about exactly the thing it claims to be careful
about.

The Papers with Code case is the single largest legal risk in the whole ingestion strategy and it
has to be decided before the first ingest, not after. The archived dump is the largest cold-start
corpus available -- 9,327 benchmarks, 5,628 datasets, 79,817 paper-code links -- and CC-BY-SA-4.0 is
viral. Mixing it into a CC-BY core would relicense the core, which destroys the "usable as
infrastructure by companies and regulators" position that is our wedge against Benchmark Radar's
NC clause. Quarantine, tag every field `provenance: pwc-archive`, and re-derive from the primary
source before promoting.

### Source, the provenance backbone

`Source` is the entity every claim in the project hangs from, it is one of the two files week 1 of
[14-roadmap.md](14-roadmap.md) asks an implementer to write, and until this pass it appeared only as
an eleven-field example inside §13's walkthrough. That is backwards: it carries the licence
classification the firewall above keys on, the archived snapshot the quote validator checks against,
and the digest that link-rot detection compares. It gets the same treatment as `Benchmark`.

```yaml
# data/sources/<yyyy>/src-swebench-paper-2023.yaml
id: src-swebench-paper-2023
type: paper                  # paper | preprint | repository | leaderboard-page | dataset-card |
                             # blog-post | documentation | dataset-export | personal-communication |
                             # regulatory-document
title: "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"
url: https://arxiv.org/abs/2310.06770
doi: 10.48550/arXiv.2310.06770
authors: [Carlos E. Jimenez, John Yang, ...]
publisher: arXiv
published: 2023-10-10        # the source's own date
accessed: 2026-09-16         # when a human read it
fetched_at: 2026-09-16T11:02:00Z   # when a machine last retrieved the bytes; distinct from `accessed`
archive_url: https://web.archive.org/web/20260916110200/https://arxiv.org/abs/2310.06770
archive_captured: 2026-09-16
archive_status: ok           # ok | pending | failed | not-required
archive_digest: "3I42H3S6NNFQ2..."  # the Wayback CDX digest, for link-rot comparison
content_sha256: "9f2c...",   # sha256 of the normalised extract below
quote_extract: |             # normalised text, capped at 64 KB, METADATA NOT CONTENT
  ...the extract the quote-substring validator matches against...
licence_class: permissive-attribution
licence_spdx: MIT
licence_checked_on: 2026-09-16
provenance: primary          # primary | pwc-archive | hf_space_tag | vendor-doc | secondary
notes: null
```

**Three field pairs that look redundant and are not.** `published` / `accessed` / `fetched_at` are
three different dates and collapsing any two loses something: the first is the source's claim about
itself, the second is when a human read it and is what `last_verified` propagates from, the third is
a machine timestamp that link-rot checking compares. `archive_url` / `archive_status` separates "we
have a capture" from "we tried and the site refused", and tier-3 validation requires a non-DOI source
to carry one or the other, never silence. `licence_class` / `licence_checked_on` is the pair the
firewall above depends on.

**`quote_extract` is how the quote-substring check becomes ten lines, and it is the one place this
schema had to choose between two of its own rules.** The validator in
[14-roadmap.md](14-roadmap.md)'s first week asserts that any quoted claim actually appears in the
archived source — which needs the source body — while [05-repository-and-workflow.md](05-repository-and-workflow.md)
§11's metadata-only invariant forbids committing bulk content and `ingest/raw/` is gitignored, so a
raw body is not reproducible at a commit hash. The resolution: **commit a normalised text extract and
its hash inside the `Source` record, never the raw body.** The extract is capped (64 KB, which holds
an abstract, a results table and its captions and is far below the 256 KB per-file cap CI job 7
enforces), it is metadata about a source rather than benchmark content, and it makes the check
reproducible by anyone at any commit. The normalisation is fixed and must be identical in the
extractor and the validator, or the check silently passes on everything:

```
NFC  ->  strip HTML/XML tags  ->  collapse all whitespace runs to one space
     ->  strip leading/trailing space  ->  casefold for comparison only
```

PDF sources extract through the same path; a source behind a paywall gets
`archive_status: not-required` with `quote_extract: null`, and a claim citing it may not be quoted,
only cited. That restriction is deliberate and it is cheaper than the alternative, which is a
validator that passes because it had nothing to compare against.

### Organization, Leaderboard and RatingPool

Three entities the §13 walkthrough uses and nothing specified. Each is deliberately thin — they exist
to be joined to, not to be browsed — and each is one file per record.

```yaml
# data/organizations/org-princeton-nlp.yaml
id: org-princeton-nlp
name: Princeton NLP
kind: academic-lab           # academic-lab | company | government-agency | non-profit |
                             # community | consortium | individual
parent: org-princeton        # null for a root organization
country: US                  # ISO 3166-1 alpha-2, for the geographic-concentration analysis in 12
homepage: https://...
ror: https://ror.org/00hx57361        # Research Organization Registry id; null for companies
wikidata: Q21578             # the two external ids that make this joinable without us owning identity
roles: [benchmark-maintainer]         # benchmark-maintainer | system-developer | evaluator | funder
sources: [src-...]
```

```yaml
# data/leaderboards/lb-swebench-official.yaml
id: lb-swebench-official
name: SWE-bench official leaderboard
host_org: org-princeton-nlp
url: https://www.swebench.com
form: live-table             # live-table | periodic-snapshot | assessment-paper | none
benchmarks: [swe-bench]
submission_process: self-reported     # same vocabulary as Benchmark.governance.submission_process
is_live: true
last_updated: 2026-09-12
archived_snapshots: [{url: "https://web.archive.org/web/...", captured: 2026-09-17}]
```

```yaml
# data/rating-pools/pool-kaggle-game-arena-chess-2026-09.yaml
id: pool-kaggle-game-arena-chess-2026-09
leaderboard: lb-kaggle-game-arena
benchmark: kaggle-game-arena@chess
snapshot_date: 2026-09-01    # a pool is a pool AT A DATE; this is part of its identity
members: [system refs]
games_per_pair: 40
rating_system: elo           # elo | bradley-terry | trueskill | glicko
anchor: null                 # the system pinned to a fixed rating, when the pool defines one
sources: [src-...]
```

`RatingPool` deserves its own file rather than a block inside a claim for the reason §2's entity
graph gives: an Elo number is a property of a system *within a pool at a snapshot*, and when a new
model joins the pool every other member's rating moves with no change to any of them. Storing the
pool separately is what lets the site refuse to compare two ratings from different snapshots, which
is the same refusal mechanism as `comparability_key` applied to a different kind of number.

---

## 10. Identity resolution

Ingestion delivers names as free strings: `GPT-4o`, `gpt-4o-2024-08-06`, `Claude 3.5 Sonnet (new)`,
`accounts/fireworks/models/glm-4p6`, `chutes/DeepSeek-R1-0528`, `amazon.nova-pro-v1:0`,
`gpt-6-astra_max`. Those strings mix three different things -- model identity, hosting provider and
reasoning effort -- into one token. Resolving them is, by the recon's own estimate, the single
largest manual cost in the Epoch ingest: roughly 550 model groups and 1,048 version strings.

**The rule: an adapter may never create an entity.** It resolves to an existing id or it writes an
unresolved record. Silent entity creation is how catalogues fill with duplicates, and the duplicates
are unrecoverable in practice because by the time anyone notices, claims point at all three copies.

### The alias table

`data/aliases/{systems,benchmarks,organizations}.yaml`. Aliases are data with provenance, not a
lookup hack.

```yaml
- alias: "accounts/fireworks/models/glm-4p6"
  resolves_to: system:glm-4-6
  extracts:
    serving_provider: org-fireworks
  kind: provider-endpoint       # exact | spelling | provider-endpoint | legacy-name | typo
  confidence: high
  decided_by: <handle>
  decided_on: 2026-09-17
  source: src-epoch-benchmarks-2026-09

- alias: "gpt-6-astra_max"
  resolves_to: system:gpt-6-astra
  extracts:
    eval_conditions.reasoning_effort: max
  kind: provider-endpoint
  confidence: high
  decided_by: <handle>
  decided_on: 2026-09-17
```

Note `extracts`. A resolution that strips information and throws it away is a bug: the `_max` suffix
is a material evaluation condition and the `accounts/fireworks/` prefix is a serving provider that
plausibly changes the number. The alias record routes the stripped parts to the fields where they
belong. This single mechanism turns Epoch's 2,402 effort-suffixed rows — **36.4% of the 6,598 result rows**
([00-vision-and-scope.md](00-vision-and-scope.md) §8.1 owns the row count) — into structured
`reasoning_effort` rather than lost context. An earlier draft said 38.9%, which implies a denominator
of 6,175 that appears nowhere in this plan; where another document quotes "~39%" it is quoting that
error.

### The procedure

```
1. external_ids exact match            -> resolve, confidence high
2. alias table exact match             -> resolve, confidence from the alias record
3. normalised-string match against name + aliases[]
      (lowercase, strip punctuation, collapse whitespace)
                                       -> resolve, confidence high
4. structured parse, in order:
      strip provider prefix   (accounts/<org>/models/, chutes/, zai-org/, together/)
      strip provider suffix   ("(Fireworks)", "(Novita)", "(Together)")
      strip effort suffix     _(max|xhigh|high|medium|low|minimal|none|unknown)$
      strip date suffix       -\d{4}-\d{2}-\d{2}$
      then retry steps 1-3 on the residue, routing every stripped part via `extracts`
5. fuzzy candidates (token-set ratio >= 0.92) -> NEVER auto-accepted.
      Emit a resolution proposal with the top 3 candidates and their scores.
6. no match                            -> unresolved record + curation task
```

`_unknown` maps to null, never to a default -- Epoch uses that suffix explicitly for rows where the
effort was not recorded.

Unresolved records land in `data/_ingest/unresolved/{adapter}/{date}.yaml` carrying the raw string,
the adapter, the source row and the top fuzzy candidates, and the workflow opens one GitHub issue
per batch (not per record -- a two-person team drowns otherwise) using the issue-form curation path
described in [05-repository-and-workflow.md](05-repository-and-workflow.md). Resolving it is a
one-line edit to the alias table plus, where needed, one new entity file.

### Near-duplicate detection, which is a different problem

Resolution merges names that mean the same thing. Deduplication merges *claims* that are the same
measurement, and it must never be automatic. In the Epoch corpus 843 rows share a `Model version`
with another row in the same file, and they fall into three kinds:

- genuinely conflicting claims from different papers -- which the schema wants to keep, both of them;
- the same run listed twice under two spellings of one source (`https://arcprize.org/leaderboard`
  and `ARC Prize Leaderboard` both appear in `arc_agi_external.csv`);
- different reasoning efforts collapsed onto one key, which is the five-row
  `claude-opus-4-6_120K` cluster on ARC-AGI where the only discriminator is a human-readable label
  (`"Claude Opus 4.6 (120K, High)"`, `"(120K, Max)"`, `"(120K, Medium)"`, `"(120K, Low)"`).

An automated dedupe would silently merge the third kind and silently duplicate the second. **Never
dedupe on ingest.** Emit every row as a separate ResultClaim, and surface a near-duplicate signature
-- same benchmark, same model version, absolute value delta under 0.005, different source spelling
-- in the quality dashboard for a human to resolve. That cluster of five is also the best single
demonstration of the project's thesis available anywhere, and it comes from a competitor's own data:
Epoch's primary key cannot distinguish five claims that differ by 8 points of score.

---

## 11. What we deliberately do not model

A schema without a stated boundary grows until it is a general-purpose ontology nobody can fill in.
These omissions are decisions, each with a reason.

| Not modelled | Why |
| --- | --- |
| Full model specifications -- architecture, layer counts, context of training, tokenizer | Constraint 5: systems exist only as subjects of result claims. Model directories already exist and are better maintained. The fields we keep are exactly the ones needed to *interpret a number* |
| Training data composition | Almost never disclosed, and what is disclosed is marketing. Where training data *eligibility* affects comparability (Matbench Discovery's compliance tiers) we model the eligibility track, not the data |
| Pricing, cost-per-token, latency tables | Volatile on a weekly basis, commercially owned, and the best sources (Artificial Analysis, OpenRouter) bar redistribution. We store per-run `cost_usd` when a source reports it, which is a measurement, not a price list |
| Per-item outputs, transcripts, predictions | Hosting them is redistribution (constraint 1) and a contamination vector. We store `artifact_url` and link |
| Dataset contents -- prompts, images, task text, answer keys | Constraint 1, absolutely. This is the bright line the whole project is built behind |
| Full leaderboard standings | We store the Leaderboard entity, its URL, its snapshot dates and archive links, plus the individual claims we curate. Mirroring standings is both a redistribution problem and an infinite curation treadmill |
| Any composite or universal score | Constraint 3. We catalogue ECI, the Artificial Analysis Intelligence Index and BenchmarkList's Rosetta Stone as ecosystem artefacts and link to them; we do not compute one |
| Editorial quality ratings | Constraint 4. We record *observable* maturity signals -- licence present, reproduction script present, repo last commit, leaderboard last update, BetterBench-style documentation facts -- and let readers weigh them. "This benchmark is bad" is not a field |
| User accounts, votes, comments, submissions | No auth in v1 (constraint 7). Contribution happens through the issue-form path and git |

The one case that will feel wrong is per-item data, because it is what a researcher most wants. The
answer is that linking to it costs nothing and hosting it ends the project; the execution layer in
[13-execution-runners.md](13-execution-runners.md) is where that question can be reopened, and only
there.

---

## 12. Schema implementation and validation

### Pipeline

Pydantic v2 is canonical. The alternative -- hand-written JSON Schema as the source of truth -- is
more language-neutral but materially worse to author and gives nowhere to put the cross-field
validation logic that carries most of this document's rules (the contamination-evidence rule, the
judge-model rule, the licence-placement rule, the id-reuse ledger). Pydantic gives ergonomic
definitions plus real validators; the generated JSON Schema preserves language neutrality for
consumers.

```
taxonomy/*.yaml ──loaded at import time──> dynamic Literal enums
        │
        v
schema/*.py            Pydantic 2.13.5 on Python 3.12
        │ model_json_schema()  -> JSON Schema Draft 2020-12
        v
schema/generated/*.schema.json                       (committed)
        │ json-schema-to-typescript@16.0.0
        v
site/src/types/*.ts                                  (committed)

data/**/*.yaml ──ruamel.yaml──> dicts ──validate──> build/{facets.json, corpus.json, ...}
                                                  (08 §4.2 owns the artifact set and its names)
```

Three corrections to the earlier draft, all measured rather than assumed:

- **`datamodel-code-generator` cannot do the TypeScript leg.** It emits Python only -- Pydantic
  models, dataclasses, TypedDict, msgspec. It is the right tool for the inbound direction
  (third-party JSON Schema -> Pydantic) and the wrong one for typing the frontend. Use
  `json-schema-to-typescript@16.0.0`.
- **The obvious Zod path is dead.** `json-schema-to-zod` was archived 2026-06-30. Do not build on
  it, even though Astro 7's Zod 4 makes it look natural. Types without runtime validation are the
  correct outcome anyway, because Pydantic already validated everything at build time and a second
  schema definition on the frontend is a second thing that can drift.
- **Python 3.12, not 3.13**, pinned in a lockfile. scikit-learn 1.9.1 requires >= 3.11 and the
  numba/UMAP stack that the Atlas layout depends on always lags new CPython.

All five pins above were verified on **2026-09-17** and re-verify with the rest of the plan's pins at
Phase 0 ([14-roadmap.md](14-roadmap.md) §"Version pins and third-party facts: as-of date" owns the
as-of statement for the whole plan). The architectural conclusions — Pydantic as canonical, Python
over Zod for runtime validation, 3.12 over 3.13 — do not depend on the exact version numbers, which
is why they are stated as conclusions and the numbers as inputs.

### `schema/taxonomy.py`, because the vocabularies need a schema too

The pipeline above has one gap that undoes its own guarantee: `taxonomy/*.yaml` is an **input** to
the canonical schema, and until this pass nothing specified the shape of that input. A taxonomy file
with a misspelled key would produce a schema that validates the corpus against the wrong vocabulary,
and CI would pass. So the taxonomy files get Pydantic models of their own, in
`schema/taxonomy.py`, written in Phase 0 alongside `schema/benchmark.py`:

| Model | Shape | Notes |
| --- | --- | --- |
| `FacetFile` | `{facet: str, facet_kind: navigational \| flat, version: semver, updated: date, description: str, terms: list[Term]}` | The header every `taxonomy/*.yaml` carries. `version` is the taxonomy version from [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §10, not the schema version |
| `Term` | `{id: slug, label: str, definition: str, inclusion_test: str, exclusion_test: str, examples: list[Example] (>= 2, >= 1 with qualifies false), not_to_be_confused_with: list[slug], source: str, status: proposed \| active \| deprecated \| retired, gap_placeholder: bool}` | The four admissibility rules in [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §5 are validators on this model, which is what makes "CI enforces each one mechanically" true |
| `DomainTerm(Term)` | adds `parent: slug \| null`, `seed_target: int`, `core: bool`, `coverage_status`, `curation_posture`, `reviewer_signoff` | Only `domains.yaml` carries these. `parent: null` marks a family, which is what tier-2's "families are navigational, not assignable" rule tests |
| `GroupFile` | `{groups: list[{id, label, members: list[slug]}], display_only: bool}` | `capability_groups.yaml` (a strict partition of the 44 terms, asserted by a validator) and `domain_groups.yaml` (`display_only: true`) |
| `HomographFile` | `{homographs: list[{slug, facets: list[str], rationale: str}]}` | Read by checks 9d and 9e |
| `ThresholdFile` | `{thresholds: map[str, float], declared_by: str, calibrated_on: date \| null}` | `taxonomy/thresholds.yaml`. Holds `frontier_floor` and `comparison_floor`; see the tier-4 rule below |
| `RetiredIdFile`, `ForbiddenIdFile` | `{ids: list[{id, retired_on, reason, replaced_by}]}` | Excluded from check 9a's own grep, for the reason §7 gives |

Ten minutes of specification that removes the only place in the design where "Pydantic is canonical,
everything is generated, CI fails on drift" does not hold.

Loading the controlled vocabularies from `taxonomy/*.yaml` at import time means a taxonomy edit
changes the generated JSON Schema, so `bench schema gen --check` must run on taxonomy changes too.
All three artifacts are committed and **CI fails if regeneration produces a diff**. The failure mode
this prevents is the schema, the JSON Schema and the frontend types drifting apart until nobody
knows which one is true.

### The four validation tiers

| Tier | What it checks | Examples | Blocking |
| --- | --- | --- | --- |
| 1 Schema | Types, enums, required fields, id format | `domain.primary` is in the closed vocabulary; `value` is a float | Yes |
| 2 Referential | Every ref resolves; no dangling ids; no reused ids | `source: src-...` exists; `system` resolves; id not in `retired-ids.yaml`; every `domain.primary` and `domain.secondary[]` value resolves to a `taxonomy/domains.yaml` term that *has* a `parent` (families are navigational, not assignable); every `capability[]` value resolves to a bare id in `taxonomy/capabilities.yaml` | Yes |
| 3 Semantic | Cross-field rules that encode this document's policies | Contamination evidence present when risk is high or confirmed; `judge_model` present when `evaluation_method` includes `model-graded-judge`; value within the metric's range; claim date not before the system's release; exactly one `is_primary` baseline per (benchmark_version, metric); `licence_class: share-alike` record is not under `data/` core; ingested record has a resolvable `ingestion.batch`; every non-DOI Source has an `archive_url` | Yes |
| 4 Quality | Signals that a record is thin, stale or unloved | Tagline over 120 chars; `last_verified` older than 12 months; `condition_completeness` below `frontier_floor`; unarchived sources; `material_waived` non-empty; benchmark with no baseline and no `value_absent_reason`; liveness `last_checked` stale | **No** -- dashboard only |

**Tier 4 is deliberately non-blocking and that is not laziness.** Making quality checks blocking
pushes curators to game them: `last_verified` gets bumped without a re-check, a waiver gets added to
silence a comparability warning, a plausible-looking baseline gets invented to clear the
"no baseline" flag. A red X produces compliance behaviour; a visible dashboard with per-curator and
per-domain trend lines produces better behaviour, because the gaps are legible to everyone and
nobody has an incentive to hide them. The quality dashboard is a first-class site view, not an
internal tool -- see [12-analytics-and-trends.md](12-analytics-and-trends.md).

**Two thresholds in the tiers above are named constants, not literals, and they live in
`taxonomy/thresholds.yaml`.** `frontier_floor` (0.3) is the completeness below which a claim is too
thin to sit on a frontier line; `comparison_floor` (0.4) is the completeness below which a
machine-ingested claim is hidden from comparison views while remaining fully visible in browse.
[12-analytics-and-trends.md](12-analytics-and-trends.md) owns both values and the reasoning that
separates them. They are constants rather than literals because a threshold typed as a number in five
documents is a threshold that gets calibrated in one of them and diverges in the other four the first
time real completeness data arrives — which is exactly when it finally matters. Anything that needs
one references it **by name**; this document deliberately prints the values once, here, and nowhere
else.

Tier 3's licence-placement rule deserves emphasis: it is the only thing standing between a CC-BY
core and an accidental relicensing event, and it must be a hard gate rather than a convention.

---

## 13. The hardest record, end to end

If the model survives the CACHE Challenges it survives everything else in the catalogue. CACHE is a
prospective computational hit-finding competition run by Conscience and the SGC Toronto: teams pick
up to 100 compounds, **the organisers buy them from Enamine and assay them in a wet lab**, the top
ten teams advance to a hit-expansion round of up to 50 follow-ups, and the outcome is an
experimental hit rate plus affinity plus physicochemical properties plus a medicinal-chemistry
expert panel's qualitative commentary. Rounds run over multiple years. It is structurally
irreproducible by a third party.

Against the earlier schema it breaks `metric` (the ground truth is a physical assay and part of the
result is prose), `access` (participation costs money in the physical world), `cycle` (multi-year,
eight rounds and counting, two phases each), `human_baseline` (there is no human comparator),
`reproducible` (no), `verification` (nobody self-reported anything -- the evaluator generated the
truth after submission), and `System` (the subject under test is a team's workflow, not a model).

Here is the whole record.

```yaml
# data/organizations/conscience.yaml
id: org-conscience
name: Conscience
type: nonprofit
country: CA
homepage: https://conscience.ai
aliases: []
---
# data/organizations/sgc-toronto.yaml
id: org-sgc-toronto
name: Structural Genomics Consortium, Toronto
type: academic-lab
parent_org: org-sgc
country: CA
---
# data/organizations/enamine.yaml
id: org-enamine
name: Enamine
type: commercial-supplier        # not an AI org; referenced only as the compound supplier
country: UA
```

```yaml
# data/benchmarks/chemistry-materials/cache-challenge.yaml
id: cache-challenge
name: CACHE Challenges
aliases: ["Critical Assessment of Computational Hit-finding Experiments"]
tagline: Prospective hit-finding, with the organisers buying and assaying the compounds you pick.
description: |
  Teams submit up to 100 purchasable compounds predicted to bind a designated protein target.
  The organisers procure the compounds from a commercial supplier and assay them in-house; the
  top-performing teams advance to a hit-expansion round of up to 50 follow-up compounds, also
  synthesised and assayed. Results are published per round as an assessment paper with a
  medicinal-chemistry expert panel's written appraisal alongside the numerical hit rates.
  Each round uses a different protein target, so rounds are not comparable with each other.

external_ids: {epoch: null, inspect_evals: null, huggingface: null}

domain:
  primary: chemistry-materials/generative-molecular-design
  secondary: [biology-genetics/drug-target-interaction, chemistry-materials/molecular-property-prediction]
capability: [search-exploration, optimization, generation-fidelity, distribution-shift-generalization]
evaluation_method: [wet-lab-validation, human-expert-eval]
designed_for_subjects: [full-product-pipeline, human-ai-team]
lifecycle: active

data:
  access: gated-registration
  refresh: periodic-recompetition
  data_provenance: [experimental-measurement]
  contamination_risk: low
  contamination_evidence: []
  ceiling_anchor_type: none-known
  modalities: [molecular-graph, protein-structure]
  size: {items: 100, unit: compounds submitted per team per round}

governance:
  maintainer_type: consortium
  maintainers: [org-conscience, org-sgc-toronto]
  submission_process: maintainer-verified
  independence_flags: [no-known-conflict]

execution:
  compute_tier: wet-lab
  reproducibility_tier: not-independently-reproducible
  est_runtime_hours: null
  est_cost_usd: null
  participant_cost:
    borne_by: organizer            # organizer | participant | shared
    supplier: org-enamine
    amount_usd: null
    notes: |
      Compound procurement and assay are funded by the organisers; participants bear only
      their own compute and staff time. (unverified -- confirm per-round funding terms.)

comparability:
  profile: wet-lab-prospective
  material_extra: [assay_protocol, target_construct, activity_threshold, human_assistance]
  material_waived:
    - field: shots
      reason: Not a prompted evaluation; no shot concept exists.
    - field: sampling
      reason: Submissions are compound lists, not sampled generations.

aggregation_policy: official-aggregate
headline_metric: experimental-hit-rate

liveness:
  repo_last_commit: null
  leaderboard_last_updated: null
  reproduction_script_present: false
  reproduction_script_verified: false
  last_checked: 2026-09-17

homepage: https://cache-challenge.org
repository: null
license: null
license_notes: |
  No dataset licence; the benchmark is a competition protocol, not a distributable dataset.

versions: [see below]
subsets: [see below]
metrics: [experimental-hit-rate, binding-affinity-kd, medchem-panel-assessment]
leaderboards: [lb-cache-round-results]
baselines: [base-cache-no-comparator]

lineage:
  supersedes: []
  superseded_by: []
  extended_by: [dream-cache-target-2035]
  correlates_with: []

tags: [prospective, wet-lab, multi-year, irreproducible]

ingestion: null
curation:
  added_by: <handle>
  added_on: 2026-09-17
  last_verified: 2026-09-17
  verification_status: primary-source-verified
  sources: [src-cache-challenge-site, src-cache-round1-results]
  confidence: medium
  notes: |
    Per-round dates are not published on the overview page.
    (unverified -- which round is currently open; confirm before publishing round status.)
```

```yaml
# BenchmarkVersion: rounds are editions, never revisions
versions:
  - version: round-1
    label: "CACHE Challenge #1"
    version_kind: edition
    released: null
    target_protein: "(per-round; recorded in the round's Source)"
    breaking: true              # different target => not comparable with any other round
    frozen: true
    resolution_lag_months: 18   # submissions to published assay results
    sources: [src-cache-round1-results]
  - version: round-8
    label: "CACHE Challenge #8"
    version_kind: edition
    breaking: true
    frozen: false
    sources: [src-cache-challenge-site]

# Subset: the two phases score differently and must not be pooled
subsets:
  - id: cache-challenge#phase-1-hit-finding
    label: Phase 1 -- hit finding
    items: 100
    scored_separately: true
    metric_override: [experimental-hit-rate]
  - id: cache-challenge#phase-2-hit-expansion
    label: Phase 2 -- hit expansion
    items: 50
    scored_separately: true
    notes: Only the top ten Phase 1 teams are eligible; the population is not the same.
```

```yaml
# data/metrics/experimental-hit-rate.yaml
id: experimental-hit-rate
name: Experimental hit rate
definition: |
  Fraction of submitted compounds that meet the round's predefined activity threshold in the
  organisers' binding assay.
value_type: ratio
range: {min: 0, max: 1}
optimum: max
chance_baseline: null
normalization_anchor: null
headroom_computable: false      # no defined ceiling; a perfect predictor's hit rate is unknown
aggregation: per-team-per-round
units: fraction
must_report_with: [medchem-panel-assessment]
pitfalls: |
  Depends entirely on the round's activity threshold and assay protocol; not comparable across
  rounds, targets or thresholds. A high hit rate on a conservative submission list is not
  evidence of a better model than a lower rate on an exploratory one.
sources: [src-cache-round1-results]
---
# data/metrics/medchem-panel-assessment.yaml
id: medchem-panel-assessment
name: Medicinal-chemistry panel assessment
value_type: qualitative
range: null
optimum: target
headroom_computable: false
aggregation: none
pitfalls: |
  Expert prose, not a score. Stored as text with the panel's composition; never rendered as a
  number and never sorted.
```

```yaml
# data/systems/teams/team-example-cache.yaml
id: team-example-cache-r1
name: "(team name as published in the round results)"
organization: org-example
system_type: human-ai-team          # NOT a model: the subject under test is a workflow
modalities_in: [protein-structure, molecular-graph]
modalities_out: [molecular-graph]
open_weights: null
built_on: [some-docking-tool, some-generative-model]   # where the write-up names components
parameters_disclosed: false
parameter_count: null
versions:
  - version: round-1
    released: null
    notes: Pipeline as submitted to Round 1; not necessarily the same as the team's later entries.
sources: [src-cache-round1-results]
```

```yaml
# data/claims/cache-challenge/claim-0xxxx.yaml
id: claim-0xxxx
system: team-example-cache-r1@round-1
benchmark: cache-challenge@round-1
subset: cache-challenge#phase-1-hit-finding
metric: experimental-hit-rate
claim_type: absolute
value: 0.XX
value_text: null
uncertainty: {type: none, value: null, n_runs: 1}
date_reported: null
reported_by: org-conscience
verification: prospective-experiment     # the evaluator generated the ground truth after submission
disputed_by: []
resolution_status: resolved
resolved_as_of: null
source: src-cache-round1-results
artifact_url: null
eval_conditions: cond-cache-r1-phase1
result_group: grp-cache-r1-team-example  # binds the hit rate to the panel assessment
ingestion: null
notes: |
  Hit rate as published in the round assessment paper. The panel's qualitative appraisal is a
  separate claim in the same result group and must be displayed alongside it.
---
id: claim-0xxxy
system: team-example-cache-r1@round-1
benchmark: cache-challenge@round-1
subset: cache-challenge#phase-1-hit-finding
metric: medchem-panel-assessment
claim_type: qualitative
value: null
value_text: |
  Verbatim quotation of the panel's written appraisal for this team, as published.
verification: prospective-experiment
result_group: grp-cache-r1-team-example
source: src-cache-round1-results
```

```yaml
# data/conditions/cond-cache-r1-phase1.yaml
id: cond-cache-r1-phase1
shots: null                     # waived by profile
chain_of_thought: null          # waived by profile
tools_allowed: null
scaffold: null
selection_strategy: null
n_samples: 100                  # compounds submitted, not generations sampled
k: null
judge_model: null
human_in_loop: true
human_assistance: permitted     # teams are humans using tools; this is material
simulator: null
hardware_platform: null
venue: "Organiser laboratory (SGC Toronto)"
assay_protocol: src-cache-round1-assay-protocol
target_construct: "(per-round protein construct as specified in the round brief)"
activity_threshold: "(per-round; see the round brief)"
eligibility_track: null
training_data_policy: undeclared
decontamination_applied: null
subset_used: full
cost_usd: null
date_evaluated: null
```

```yaml
# data/baselines/base-cache-no-comparator.yaml
- id: base-cache-no-comparator
  benchmark_version: cache-challenge@round-1
  kind: field-practice-reference
  metric: experimental-hit-rate
  value: null
  value_absent_reason: no-published-comparator
  notes: |
    Industry high-throughput-screening hit rates are sometimes quoted as an informal comparator,
    but no figure specific to this target and threshold has been published.
    (unverified -- do not display a comparator number until one is sourced.)
```

```yaml
# data/leaderboards/lb-cache-round-results.yaml
id: lb-cache-round-results
name: CACHE round results
host_org: org-conscience
url: https://cache-challenge.org
form: assessment-paper          # live-table | periodic-snapshot | assessment-paper | none
benchmarks: [cache-challenge]
submission_process: maintainer-verified
is_live: false
last_updated: null
archived_snapshots:
  - {url: "https://web.archive.org/web/...", captured: 2026-09-17}
---
# data/sources/src-cache-round1-results.yaml
id: src-cache-round1-results
type: paper
title: "(round 1 assessment paper title)"
url: https://...
doi: null
authors: [...]
published: null
accessed: 2026-09-17
archive_url: https://web.archive.org/web/...
archive_captured: 2026-09-17
```

### What this record proved, and what it changed

Nine things in this document exist because of records like this one, and every one of them would
have been a hack if discovered after bulk curation started:

`participant_cost`; `Metric.value_type: qualitative` and the rule that qualitative claims are never
sorted; `must_report_with` and `result_group`, so a hit rate is never shown without the panel's
caveats; the `prospective-experiment` verification rung; `version_kind: edition` with
`breaking: true` between rounds; `Baseline.value_absent_reason`; the environment block
(`venue`, `assay_protocol`, `target_construct`, `activity_threshold`); `human_assistance` as a
material condition; and `comparability.material_waived` with a mandatory reason, because waiving
`shots` for a wet-lab challenge is correct and waiving it for MMLU is fraud.

The one thing the model still handles awkwardly is `resolution_lag_months`: CACHE results land a
year or more after submission, so a team's entry exists as a real event with no claim attached for
most of a year. The current answer is that the claim is created when the result publishes, and the
submission itself is not modelled. That is probably right -- an unmeasured submission is not a
result -- but it means the site cannot show "who has entered round 8", which is the thing a
prospective participant most wants to know. Recorded as an open question in
[15-open-questions.md](15-open-questions.md).

### A second, shorter case: Elo, where headroom does not exist

Kaggle Game Arena rates frontier models by all-play-all with 40 games per pair across Chess, Chess
Openings, Poker, Werewolf and Four in a Row. The rating is unbounded, pool-dependent and changes
when a *different* model joins with no change to the model under test. LMArena, WebDev Arena,
TTS Arena and RoboArena are the same shape.

```yaml
# data/rating-pools/pool-kaggle-game-arena-chess-2026-09.yaml
id: pool-kaggle-game-arena-chess-2026-09
leaderboard: lb-kaggle-game-arena
game: chess
snapshot_date: 2026-09-15
participants: 24
games_per_pair: 40
rating_system: elo-all-play-all
anchor: null
source: src-kaggle-game-arena
archive_url: https://web.archive.org/web/...
---
# the claim
claim_type: rating
metric: arena-elo
value: 1XXX
rating_pool: pool-kaggle-game-arena-chess-2026-09
```

Three consequences follow mechanically and none of them requires an editorial judgement. The metric
carries `unbounded: true`, `requires_pool: true` and `headroom_computable: false`, so the site draws
no headroom bar for arena results and the cross-domain headroom axis simply has a hole there. Two
claims in different pools have different `comparability_key`s by construction, so the comparison view
refuses to plot a September rating against a June one. And the Atlas and coverage views count the
benchmark as covered while the headroom analytics skip it, with a footnote saying why.

This is what constraint 3 looks like when it is implemented rather than asserted: the honest answer
to "how much headroom is left on LMArena" is that the question is not defined, and the schema is
built so that the site says that instead of inventing a number.

---

## 14. Known limitations

Stated plainly, because a plan that hides its soft spots is the same failure as data that hides its
provenance.

- **Reasoning-effort enums are not comparable across vendors.** `high` on one provider is not `high`
  on another. We store both the enum and `reasoning_effort_raw`, and the comparability key uses the
  raw string when the vendors differ -- which means cross-vendor effort comparisons will almost
  always land in the "different keys, refuse" branch. That is correct but it will look pedantic, and
  we should expect to defend it.
- **The material-field profiles are a hypothesis until the ten stress cases pass.** The profile
  table in `taxonomy/comparability-profiles.yaml` is the most likely part of this document to be
  wrong, and it should be revised after the first fifty non-LLM benchmarks, not before.
- **Contamination evidence will be sparse.** The requirement that `contamination_risk: high` needs a
  source is right, and the practical effect is that most entries will sit at `unknown`. An honest
  `unknown` beats a confident guess, but the contamination view will look thin for a long time.
- **Multi-system results are only half modelled.** `claim_type: pairwise` with an `opponent` handles
  RoboArena and arena head-to-heads. AgentDojo's attack-method x defence matrix, Redwood's red-team
  versus blue-team control evaluations, and multi-agent benchmarks where the co-player population is
  the variable are not cleanly expressible yet. Provisional answer: the co-player or attack method
  goes in `EvalConditions` as a material field and the claim stays single-subject. Flagged for the
  first safety-domain curation pass.
- **Deep subset trees.** BraTS 2026 is an edition containing five sub-challenges each with
  lesion-wise splits, which is three levels. The model permits it; the renderer shows two. Somebody
  will have to decide what the third level looks like in the UI.
- **We inherit Epoch's dirt where we ingest it.** Mixed-type `Shots` values (`5`, `few`, `0-shot`,
  `25-shot`), mojibake in the `dtbench` and `lmca` headers where a plus-minus sign was corrupted,
  62 distinct header signatures across 80 files requiring roughly 80 small per-file column-mapping
  stanzas, score scales in dollars (`vending_bench_2` at 11181.87), minutes (`metr_time_horizons` at
  1044.78) and Elo (`webdev_arena`) that will produce silent nonsense if the default scale of 1.0 is
  applied to the 21 files with no `score_column` in Epoch's metadata. The adapter is not a generic
  parser and pretending otherwise is how the ingest quietly corrupts the corpus.

---

## 15. What has to happen before the first ingest

Retrofitting thousands of records is painful, so the following are prerequisites rather than
improvements. They are the **schema half of the Phase 0 deliverables** in
[14-roadmap.md](14-roadmap.md) and every one of them must be complete before the **Phase 3** Epoch
adapter runs — not Phase 2, which is the public static site and touches no claims schema at all:

**The four C5 additions, which are the ones C5 names by name.**

1. `ResultClaim.artifact_url` (transcript, `.eval` log or submission bundle URL) with
   `artifact_archived`.
2. `ResultClaim.provenance_snapshot` — the upstream record frozen as retrieved, `{source_record_id,
   retrieved_at, content_sha256, raw}`. Distinct from `ingestion.field_provenance`; see §7.
3. `System.training_compute_flop` with `training_compute_estimated` and the verbatim upstream notes,
   so imputed-from-benchmark-scores values can be excluded from compute-versus-capability analysis.
4. `EvalConditions.reasoning_effort` as enum-plus-raw-text, seeded from the observed Epoch vocabulary
   (`max`, `xhigh`, `high`, `medium`, `low`, `minimal`, `none`, `unknown` -> null).

**Everything else this document's own rules depend on.**

5. `ResultClaim.serving_provider`, `claim_type`, `resolution_status`, `result_group`.
6. `ResultClaim.external_ids.eee_result_id`, the claim-level join to Every Eval Ever.
7. The `ingestion` block and the `IngestBatch` entity, with `licence_class` enforced by a tier-3 CI
   rule, `source_record_id` in its stable content-key form, `last_seen_upstream`, and
   `IngestBatch.resolver_snapshot_sha256`.
8. The alias tables and the resolution procedure, with the rule that adapters never create entities.
9. `Metric.optimum`, `unbounded`, `requires_pool`, `headroom_computable`, `must_report_with`.
10. `Baseline` replacing `HumanBaseline`, with `noise-ceiling` added, `biological-replicate` renamed
    to `experimental-replicate`, and the facet rename mirrored in [02-taxonomy.md](02-taxonomy.md).
11. `Benchmark.reference_conditions` — without it §8's SOTA rule, and therefore headroom, is
    undefined.
12. The admissibility block: `learned_entrant_evidence`, `evaluation_target`, `execution_mode`,
    `ground_truth_source`, `reproducible_by_third_party`. The inclusion boundary cannot be enforced
    or audited without them.
13. `Benchmark.maintenance_status` with `maintenance_status_contested`, `contested_source` and
    `contested_statement_date`, derived from the `liveness` block.
14. `Benchmark.curation.stewardship`; `System.availability` and `System.retired_on`.
15. `Benchmark.execution.runnable_via` and `inspect_evals_id`, with `inspect_evals_available`
    derived from the second.
16. The `Benchmark` fields [02-taxonomy.md](02-taxonomy.md) §12's handoff table marks "required
    before the first YAML file": `no_legitimate_aggregate`, `secondary_axes`,
    `training_data_eligibility_tiers[]`, `data.submission_limit`,
    `execution.est_participant_cost_usd`, `comparability.rating_pool_required`,
    `EvalConditions.training_data_eligibility`, `Subset.domain_override`, and `gap_placeholder` on
    the taxonomy term record.
17. `curation_posture` on the domain-family record, with check 9f extended to it.
18. `Source` specified in full (§9), including `licence_class`, `licence_checked_on`,
    `archive_digest`, `content_sha256` and `quote_extract` — the quote-substring validator in week 1
    cannot run without the last two.
19. `schema/taxonomy.py`, so the vocabulary files that generate the schema are themselves validated.
20. `taxonomy/thresholds.yaml` declaring `frontier_floor` and `comparison_floor`, referenced by name
    everywhere else.
21. All ten stress benchmarks validating against the generated JSON Schema, in CI, as fixtures.

**Point 21 is the gate.** Ten fixture files, one per stress case, checked on every commit, is the
cheapest possible insurance against discovering in month six that the schema is
language-model-shaped.

**Why this list grew, and the rule that keeps it from growing again.** Items 2, 6, 11–17 and 19–20
were each requested by another document — [00-vision-and-scope.md](00-vision-and-scope.md) §6,
[02-taxonomy.md](02-taxonomy.md) §12's handoff table, [13-execution-runners.md](13-execution-runners.md)
§3.1, [15-open-questions.md](15-open-questions.md)'s edit register — and none of them had reached
this document. A field that one document assigns and the owning document has never seen is a field
nobody builds, and eight of them were load-bearing for rules those documents state as settled. The
rule from here: **a request for a schema field lands in this section in the same pass that states
it**, and the reviewing check is mechanical — every backticked field name in another document's
"required before first ingest" table must appear in this file, which is a grep and belongs in
`verify_corpus.py`.
