# 05 -- Repository Layout and Curation Workflow

This document specifies the physical shape of the project: what lives where, how a change gets in,
who checks it, what CI enforces, and what happens to all of it when the maintainers stop. It is the
operational counterpart to [04-data-model.md](04-data-model.md), which defines *what* a record
contains, and to [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) and
[07-ingestion-infrastructure.md](07-ingestion-infrastructure.md), which define where records come
from.

One finding from the 2026-09-17 landscape reconnaissance shapes almost everything below, so it goes
first. **Every prior cross-domain AI benchmark catalogue has died within 12--24 months, and none died
of insufficient ambition.** Stanford CRFM's Ecosystem Graphs -- structured catalogue as files in git
plus a static site, which is precisely the architecture proposed here -- last pushed 2025-01-24,
carries **no licence at all**, has 274 stars and zero open issues, and is still cited as a live data
source by 2025--26 research while twenty months stale. Papers with Code, the largest attempt ever
made (9,327 benchmarks), was sunset by Meta on 2025-07-24 and its benchmark layer was never
replaced. `JonathanChavezTamales/llm-leaderboard` -- a JSON-in-git, schema-validated community
benchmark catalogue with 356 stars and 40 forks -- **deprecated itself and converted into a closed
website** (llm-stats.com), and the stated reason was contribution friction: pull requests were too
slow compared with per-model discussion threads on a site.

The architecture is not the risk. The curation treadmill and the contribution path are the risk.
Three design decisions follow, and they are load-bearing throughout this document:

1. **CC-BY + DOI + forkable-at-commit from day one**, with a written succession policy. Ecosystem
   Graphs could not be rescued by anybody because it had no licence.
2. **Contributing must not require a pull request.** A PR-only workflow is a documented cause of
   death for exactly this kind of project.
3. **Automate ingestion from permissive sources; hand-curate only where hand-curation is the
   differentiator** -- the cross-domain taxonomy, the evaluation conditions, the gap matrix, and the
   non-LLM domains.

---

## 1. Data as git

The index lives as YAML files in version control. The database is a **build artifact**, never the
source of truth. This is the transparency mechanism, not a cost-saving measure, and it is worth
stating why in full because it is the property that everything else in the positioning
([01-landscape-and-positioning.md](01-landscape-and-positioning.md)) rests on.

- **Every change is a diff with an author, a date, and a reviewable rationale.** A number changing
  from 0.412 to 0.487 is a commit with a message, a source link, and a person's name attached. On a
  website backed by a database, that same change is invisible.
- **Any claim can be audited backwards.** `git log --follow data/claims/swe-bench/` is the complete
  provenance history of every number this index has ever published about SWE-bench, including the
  wrong ones.
- **Outside experts correct entries by editing one readable file.** A protein-structure
  crystallographer who spots an error in our CASP entry does not need to understand our stack; they
  need to understand one 80-line YAML file.
- **There is no privileged mutation path.** The maintainers change data the same way a stranger
  does -- a commit on a branch, reviewed. Nobody can quietly change a number, including us. This is
  the single strongest answer to "why should I trust you", and it is unavailable to BenchmarkList,
  llm-stats, BenchLM or any other closed operator in the space.
- **The dataset is forkable and citable at a commit hash.** A paper can cite
  `uaibi@a1b2c3d` and a reader can reconstruct exactly what the index said that day.

### The honest cost

Git is a terrible database and pretending otherwise is how this design fails.

| Cost | Consequence | Mitigation |
| --- | --- | --- |
| No transactional writes | A rename that touches 40 files can land half-applied if a PR is partially merged | CI validates referential integrity on the merged tree, not on the diff; `main` is protected and squash-merged so a PR is one atomic commit |
| No concurrent editing | Two curators editing the same benchmark produce a conflict | One entity per file, narrow file scope; `bench claim` and `bench new` allocate content-derived IDs so there is never a shared counter to contend on |
| Merge conflicts on hot files | `taxonomy/*.yaml` and any index file are contention points | Taxonomy changes go through ADRs and are rare by design; there are **no index files** -- the build derives every index, so nothing aggregates by hand |
| Cosmetic diffs | Two editors' YAML formatting differ, producing noise that hides real changes | `bench fmt` normalises key order, quoting, line width and list style; CI fails on any file `bench fmt` would change |
| No referential integrity at write time | A claim can reference a benchmark that does not exist | CI's referential tier catches it before merge; this is a review-latency cost, not a correctness one |
| Review latency | A contributor waits hours or days for a human | The issue-form path (§6) removes git from the contributor's side entirely; batch ingest PRs remove it from the bot's side |

The mitigation that matters most is **one entity per file with narrow scope**. A repository of 10,000
small files is entirely comfortable for git; a repository of 40 large files that everyone edits is
not. Every layout decision below follows from that.

### One repository, not two

Recommendation: **a single repository** containing data, schema, tools, ingestion adapters and site.

The reason is succession. The thing we want a stranger to be able to fork in 2029 is not "the data"
-- it is the data plus the schema that validates it plus the build that renders it plus the
documented procedure for running both. Splitting those across repos means a fork gets one of them.
It is also what [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md) requires: scrapers
run as GitHub Actions cron **in the data repo itself**, because the runner then already has
`GITHUB_TOKEN`, `git`, and PR-creation rights against the YAML it writes, with no deploy step and no
secret-syncing.

The risk is that site churn pollutes the data history and makes `git log` less useful as an audit
trail. Three mitigations: path-scoped `CODEOWNERS`; the convention that data commits never touch
code and vice versa (CI warns on mixed commits); and a published **data-only mirror** (`uaibi-data`)
produced by a filtered push of `data/`, `taxonomy/` and `schema/` on every release, for consumers
who want the citable core without the frontend.

---

## 2. Repository layout

```
uaibi/
├── README.md                      # What this is, how to cite it, how to contribute, the DOI badge
├── CITATION.cff                   # Machine-readable citation; GitHub renders "Cite this repository"
├── LICENSE-DATA                   # CC-BY-4.0 — applies to data/, taxonomy/, docs/, evals/golden/
├── LICENSE-CODE                   # MIT — applies to tools/, ingest/, schema/, site/, build scripts
├── REUSE.toml                     # Per-path SPDX licence map; machine-checkable, CI-enforced
├── GOVERNANCE.md                  # Maintainers, decision process, how disputes are decided
├── SUCCESSION.md                  # What happens when we stop (§10). Root, not docs/ — sixteen
│                                  # references across the plan point at the root path, and a
│                                  # succession document a successor cannot find is not one
├── CONTRIBUTING.md                # Both contribution paths; the ten-minute walkthrough (§6.5)
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md                   # Schema and taxonomy changes only — data changes live in git log
│
├── taxonomy/                      # Controlled vocabularies — the closed enums. See 02-taxonomy.md
│   ├── domains.yaml               # The navigational spine: two levels, hierarchical. Also carries
│   │                              # seed_target, core and coverage_status per family — the fields
│   │                              # the seed-target check (9f) and the muting rule read
│   ├── capabilities.yaml          # Flat, multi-valued
│   ├── capability_groups.yaml     # The coarse (column) axis of the coverage matrix: a partition of
│   │                              # capabilities.yaml, enumerated in 02-taxonomy.md §4.3. CI 9g
│   ├── domain_groups.yaml         # Presentation groups over the domain families. display_only:
│   │                              # true — ordering and banding only, never a filter key. CI 9h
│   ├── evaluation-methods.yaml
│   ├── subjects.yaml              # What kind of thing is being evaluated
│   ├── data-properties.yaml       # Access, refresh, contamination posture, provenance
│   ├── lifecycle.yaml             # Ten terms; 02 §8 owns the vocabulary and this comment does not
│   │                              # restate it. `saturated` is derived, never hand-set
│   ├── governance.yaml            # Maintainer type, submission process, independence flags
│   ├── execution.yaml             # Compute tier, reproducibility tier
│   ├── homographs.yaml            # Declared capability↔subdomain word collisions; CI 9d/9e
│   ├── forbidden-identifiers.yaml # Renamed field names that must never reappear; CI 9a
│   ├── retired-ids.yaml           # Never-reuse ledger; CI enforces against it
│   ├── ceiling-anchors.yaml       # ceiling_anchor_type, ten terms. 02 §7
│   ├── maintenance.yaml           # maintenance_status, five terms, derived. 02 §8
│   ├── verification.yaml          # The seven-rung claim verification ladder AND ITS RANKS. 04 §7.
│   │                              # Load-bearing: 09's colour ramp is generated from this file
│   ├── comparability-profiles.yaml  # evaluation_method × subjects → material field set. 04 §8
│   ├── domain-expectations.yaml   # Per-family entry expectation, an input to curation_confidence. 12 §5.3
│   ├── thresholds.yaml            # frontier_floor = 0.3, comparison_floor = 0.4. 12 owns the values;
│   │                              # every other document references them BY NAME, never by value
│   ├── VERSION                    # Aggregate semver, stamped into every build artifact
│   ├── _failures/                 # Structured classification-failure log (03 §3.3)
│   ├── _corpus/                   # The 90-benchmark taxonomy stress corpus (03 §3)
│   │   └── stress-corpus.yaml
│   └── crosswalks/                # Our terms ↔ other people's vocabularies
│       ├── helm.yaml              # HELM scenario taxonomy (adopted as ancestry, see 03)
│       ├── hf-tags.yaml           # HuggingFace test:/submission:/judge:/eval: tag namespaces
│       ├── eee.yaml               # Every Eval Ever field names (generation_args, sandbox, …)
│       ├── inspect-evals.yaml     # UK AISI inspect_evals IDs
│       ├── croissant.yaml         # Our Benchmark fields ↔ the proposed croissant-benchmark
│       │                          # namespaced extension. 08 §5.8 emits from it
│       └── pwc.yaml               # Papers with Code task/dataset IDs — KEYS ONLY, no prose
│
├── data/                          # The citable core. CC-BY-4.0. One entity per file.
│   ├── benchmarks/<domain-family>/<id>.yaml
│   ├── systems/<org-slug>/<id>.yaml
│   ├── organizations/<id>.yaml
│   ├── metrics/<id>.yaml
│   ├── leaderboards/<id>.yaml
│   ├── conditions/<cond-id>.yaml          # EvalConditions — shareable, referenced by claims
│   ├── baselines/<benchmark-id>.yaml      # Baseline records (04 §7; renamed from HumanBaseline)
│   ├── sources/<yyyy>/<src-id>.yaml       # The provenance backbone; archive_url mandatory for non-DOI
│   ├── claims/<benchmark-id>/<claim-id>.yaml
│   ├── claims/_ingested/<source>/<benchmark-id>/<claim-id>.yaml
│   │                                      # Bulk machine-ingested claims. Segregated by policy (§4)
│   ├── surveys/<domain-family>/<subdomain>.yaml
│   │                                      # Dated per-capability survey notes: the only thing that
│   │                                      # lets a coverage cell read `surveyed-and-empty`. One file
│   │                                      # per subdomain, not per cell — 204 files, not 8,976
│   ├── disputes/<dispute-id>.yaml         # Standing disputes; render both positions (§8)
│   ├── tombstones/<id>.yaml               # Merged/retired IDs with redirects_to — keeps citations alive
│   ├── _ingest/batches/<id>.yaml          # IngestBatch records. 04 §9 owns the entity and this path;
│   │                                      # `ingest/manifests/` below is the adapter's own run log,
│   │                                      # which is a different thing and is NOT citable
│   ├── _discovery/                        # Unresolved discovery candidates awaiting triage (06 §5)
│   └── _analysis/                         # One-off measurement outputs, e.g.
│                                          # overlap-<service>-<date>.yaml (01 §4). NOT part of the
│                                          # citable core; excluded from every build artifact
│
├── vendor/                        # Inbound material under a licence incompatible with our core.
│   └── pwc-archive/               # Papers with Code dump: CC-BY-SA-4.0, VIRAL.
│       ├── LICENSE                # CC-BY-SA-4.0, verbatim
│       ├── README.md              # What may and may not be done with this tree
│       └── keys/                  # Name↔ID reconciliation keys only. No descriptions, no prose.
│
├── drafts/                        # AI-drafted entries at curation.verification_status:
│                                  # ai-drafted-unverified, before a human has looked. Never built,
│                                  # never published, never citable. CI check 9i (§9)
│
├── design/                        # tokens.yaml and the design-system source. See 09 §13
│
├── metrics/                       # Adoption counters: github_stars, hf_downloads, arxiv_citations.
│                                  # Bot-written, auto-merged, timestamped. NOT part of the citable core.
│
├── analytics/<yyyy>-<mm>.json     # Monthly aggregate usage counts, committed. No beacon, no
│                                  # per-visitor record, no third-party script. See 08
│
├── schema/                        # Pydantic v2 is canonical. See 04-data-model.md
│   ├── benchmark.py system.py claim.py conditions.py source.py taxonomy.py …
│   ├── generated/*.schema.json    # Committed build artifact; CI fails if regeneration diffs
│   └── migrations/<nnnn>-<slug>.py
│
├── ingest/                        # Scraper adapters and their state. See 06 and 07.
│   ├── adapters/<source>.py       # One module per source; declares licence, rate limit, robots policy
│   ├── state/<source>.json        # {etag, last_modified, sha256, last_fetched, last_changed} — committed
│   ├── runs/<source>/<date>.json  # {status, http_codes, records_seen, records_changed, errors[]} — committed
│   ├── manifests/<source>-<date>.yaml   # The adapter's own run log. NOT the IngestBatch record,
│   │                                    # which is citable and lives at data/_ingest/batches/<id>.yaml
│   └── raw/                       # Last raw response, gzipped and capped — gitignored, kept as CI artifact
│
├── tools/                         # The `bench` CLI (Python 3.12, Typer). See §3.
│   ├── cli.py
│   └── validate/ build/ ingest/ resolve/ report/ atlas/ release/ suite/
│
├── scripts/                       # Checkers whose only caller is CI, kept out of the `bench`
│   │                              # surface because a contributor never runs them. See §9
│   ├── taxonomy_stats.py          # Regenerates every typed count, the seed-target table and the
│   │                              # capability-group partition assertion; CI 9b, 9f, 9g
│   ├── check_display_only_vocab.py  # Presentation-group containment; CI 9h
│   ├── epoch_audit.py             # Re-counts the Epoch drop from the CSVs. Phase-0 deliverable (01 §12)
│   ├── overlap_sample.py          # Draws and scores the 50-family overlap sample. Phase-0 (01 §4)
│   └── …                          # The design-system checkers are specified in 09 §13
│
├── atlas/                         # Layout stability artifacts. CI is the ONLY authority that writes these.
│   ├── basis_v1.npz               # Frozen TruncatedSVD basis: components, column means, facet ordering
│   ├── prev.json                  # Previous build's 2-D positions, for Procrustes alignment + drift gate
│   └── atlas_epoch.yaml           # The layout-epoch ledger: epoch number, reason, triggering PR.
│                                  # Bumping it is the only sanctioned way to accept a drift-gate
│                                  # failure. 08 §5.3.1 owns the mechanism
│
├── build/                         # Generated. Gitignored. THE ARTIFACT SET IS NOT LISTED HERE.
│                                  # [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
│                                  # §4.2 owns every build artifact, its filename and its size
│                                  # budget. Two documents listing the same artifacts is how
│                                  # `facets.json` and `index.json` came to be the same file under
│                                  # two names. The boundary, stated once: **this document owns
│                                  # everything a contributor can edit; 08 owns everything the build
│                                  # writes.**
│
├── site/                          # Astro 7.3.x + React 19 islands. See 08, 09 and 10.
│   ├── src/pages/ components/ views/ islands/
│   ├── src/types/                 # Generated from JSON Schema by json-schema-to-typescript@16
│   └── worker/                    # Cloudflare Worker: the AI layer's only server-side component (11)
│
├── evals/                         # Golden sets for the AI layer. See 11-ai-features.md
│   ├── golden/{nl_search,facet_translation,suite_build,abstention}.yaml   # ~150 hand-labelled items
│   └── results/<date>-<commit>.json   # Published; rendered as a public trend page
│
├── docs/                          # Public methodology; rendered on the site, not just for developers
│   ├── methodology.md provenance.md comparability.md corrections.md
│   ├── reproduce.md               # Rebuild from a clean machine. Tested monthly by CI.
│   ├── attribution.md             # GENERATED from data/sources/ — never hand-edited
│   └── succession.md              # What happens when we stop (§10)
│
├── adr/                           # Architecture Decision Records: NNNN-<slug>.md
│
├── .github/
│   ├── ISSUE_TEMPLATE/            # The default contribution path (§6). Dropdowns GENERATED from taxonomy/
│   │   ├── new-benchmark.yml correction.yml new-claim.yml dispute.yml taxonomy-term.yml
│   │   └── config.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── CODEOWNERS                 # Path-scoped; domain stewards own their domain families
│   └── workflows/                 # See §9. THIS IS THE COMPLETE INVENTORY — 08 §7.3 keeps only
│       │                          # the hosting-specific behaviour (workflow_run vs pull_request,
│       │                          # the GITHUB_TOKEN hazard, the 60-day inactivity disable) and
│       │                          # links here for the list
│       ├── pr-validate.yml        # Every PR: schema, referential, semantic, codegen drift
│       ├── build-preview.yml      # Per-PR preview deployment
│       ├── codegen-check.yml      # JSON Schema + TS regeneration produces no diff
│       ├── deploy.yml release.yml reproduce.yml evals.yml
│       ├── atlas-drift.yml        # The layout drift gate; CI is the only writer of atlas.json
│       ├── linkrot.yml limits-check.yml restore-drill.yml
│       ├── issue-intake.yml       # The validation bot
│       ├── promote-ingest.yml     # Promotes a reviewed ingest batch out of _ingested/
│       ├── codeowners-lapse.yml   # Reassigns a domain family whose steward has gone quiet (§6)
│       ├── ingest-static.yml ingest-hub.yml ingest-arxiv.yml ingest-leaderboards.yml
│       ├── archive-sources.yml freshness.yml health-check.yml
│
└── _plan/                         # This planning document set. Gitignored; never published.
```

### File naming and identity conventions

| Thing | Convention | Example |
| --- | --- | --- |
| Entity file | `<id>.yaml`, id is a lowercase kebab slug | `data/benchmarks/code/swe-bench.yaml` |
| Benchmark id | Stable slug, never renamed, never reused | `swe-bench`, `casp-protein-structure` |
| Versioned ref | `<id>@<version>` | `swe-bench@verified`, `arc-agi@2` |
| Organization id | `org-<slug>` | `org-princeton-nlp` |
| Source id | `src-<org>-<slug>-<yyyy>` | `src-anthropic-opus5-announcement-2026` |
| Conditions id | `cond-<12 hex>` — **content-derived** from the canonical JSON of the material fields | `cond-9f21ab04c7de` |
| Claim id | `claim-<12 hex>` — content-derived from (benchmark@ver, system@ver, metric, subset, value, source, date_reported) | `claim-3c8e10ba55f7` |
| Domain family dir | First segment of `domain.primary` | `data/benchmarks/robotics-embodiment/`, `.../biology-genetics/` |

Two of those deserve their reason stated, because they are changes from the earlier draft's
sequential `claim-00042` scheme.

**Content-derived IDs remove the only shared mutable resource in the repository.** A global
monotonic counter is a hot file that every contributor and every bot must read-modify-write, which
guarantees merge conflicts exactly when throughput is highest -- during a 6,598-row bulk ingest. A
hash over the claim's identifying content has three further benefits: re-running an adapter is
idempotent (the same row produces the same filename, so a no-op ingest produces a zero-line diff);
two curators who independently enter the same evaluation conditions produce the same `cond-` file
and deduplicate for free, which is exactly the behaviour EvalConditions-as-a-shared-entity wants;
and an ID collision is a *signal* (someone entered the same claim twice) rather than a bug. The cost
is that IDs are not human-memorable. Mitigation: the site's canonical claim URL is a readable
`/claim/<benchmark>/<system>/<metric>` path that resolves to the hashed file, and `bench diff`
prints human labels, never bare hashes.

**`data/claims/` is sharded by benchmark id, and bulk ingests are sharded again by source.** At
target scale, claims are the only entity type with more than a few thousand members: the local Epoch
AI download alone is roughly 6,598 result rows across 81 benchmarks. One directory per benchmark
keeps any single directory small enough for GitHub's file browser to remain usable and keeps a
"re-verify SWE-bench" task to a single `git add` path. The `_ingested/<source>/` prefix is not
cosmetic -- it is the mechanism by which machine-ingested claims stay out of comparison views (§4).

---

## 3. The `bench` CLI

One Python 3.12 Typer application, installed with `pipx install -e tools/` or run through `uv run
bench`. Pin the toolchain in a lockfile; the Atlas layout's reproducibility depends on it, and
`scikit-learn` 1.9.1's `>=3.11` floor plus the numba/UMAP stack's lag behind new CPython is why
3.12 rather than 3.13. Every version number in this document was verified on **2026-09-17** and
re-verifies with the rest of the plan's pins at Phase 0 ([14-roadmap.md](14-roadmap.md)
§"Version pins and third-party facts: as-of date" owns the as-of statement;
[04-data-model.md](04-data-model.md) §12 records the toolchain reasoning).

```
# Authoring
bench new <entity> --id <id> [--domain <d>] [--from-source <url>] [--template <name>]
bench fmt [paths…] [--check]
bench claim --benchmark <ref> --system <ref> --metric <id> --value <v> --source <src-id>

# Validation
bench validate [paths…] [--tier schema|ref|semantic|quality|all] [--changed-only] [--single] [--json]
bench schema gen [--check]
bench check-links [--changed-only] [--archive-missing] [--timeout 20]
bench archive <src-id…> [--all-missing] [--if-not-archived-within 30d]

# Ingestion
bench ingest <adapter> [--dry-run] [--since <date>] [--limit N] [--no-network]
bench resolve [--candidates] [--threshold 0.85] [--apply <mapping.yaml>]
bench promote <path…> --to <verification_status> --evidence <src-id>

# Build
bench build [--derived] [--embed] [--atlas] [--out build/]
bench embed [--model potion-base-8m] [--quantize int8]
bench atlas [--basis atlas/basis_v1.npz] [--warm-start atlas/prev.json] [--drift-gate 0.02]

# Taxonomy maintenance
bench migrate <nnnn> [--dry-run|--apply]
bench tag-gap --benchmark <id> --facet <facet> --note "<what could not be expressed>"

# Reporting and release
bench report staleness|coverage|quality|conflicts|attribution|completeness|taxonomy-health
            [--format md|json|csv]
bench gaps [--grid coarse|fine] [--min-confidence <f>] [--reviewed-only] [--format md|json]
bench verify --commit <sha>
bench diff <ref>..<ref> [--entity benchmark|claim|…] [--format md]
bench suite --need <file.yaml> [--export manifest.json|manifest.yaml]
bench eval [--split <name>|all] [--report] [--judge] [--holdout N]
bench release --version <x.y.z> [--dry-run]
```

| Command | One line |
| --- | --- |
| `new` | Scaffold an entity file from a template with every required field stubbed and commented |
| `fmt` | Normalise YAML key order, quoting and line width; `--check` is the CI gate against cosmetic diffs |
| `claim` | Scaffold a ResultClaim plus its EvalConditions, computing both content-derived IDs |
| `validate` | The four validation tiers from [04-data-model.md](04-data-model.md); `--changed-only` for fast PR runs; `--single` validates one file with no corpus load, which is what the issue-intake bot calls and is why it answers in about a minute rather than in a full build |
| `schema gen` | Regenerate `schema/generated/*.schema.json` and `site/src/types/*.ts` from the Pydantic models. `--check` fails if regeneration produces a diff, and it must run on `taxonomy/` changes too, because the vocabularies become dynamic `Literal` enums at import time ([04-data-model.md](04-data-model.md) §12) |
| `migrate` | Apply a taxonomy migration script from `schema/migrations/<nnnn>-<slug>.py` across the corpus. `--dry-run` reports only, and its output is attached to the ADR's PR; `--apply` writes. Splits are never automatic ([03-taxonomy-build-process.md](03-taxonomy-build-process.md) §9) |
| `tag-gap` | Record, in one command, that a curator could not express something in the current vocabulary. It writes a `taxonomy/_failures/` entry. This exists because the unmet-term rate is only real if logging costs nothing |
| `gaps` | Emit `build/derived/gaps.json` over the coarse 19 × 13 grid with every input factor exposed. `--reviewed-only` and `--min-confidence` are what make success criterion S3 in [00-vision-and-scope.md](00-vision-and-scope.md) §7.1 a runnable test rather than an aspiration. The fine grid is available for internal inspection and **may never publish a gap claim** |
| `verify` | Given a commit SHA, rebuild from that commit on a clean tree and assert the artifacts match byte for byte. This is success criterion S6's mechanism and the thing `reproduce.yml` runs on a schedule |
| `check-links` | HTTP-check every `url` in the touched files; report rot; optionally queue archiving |
| `archive` | Wayback SPN2 capture (`POST https://web.archive.org/save`, `Authorization: LOW <key>:<secret>`), using `if_not_archived_within` as the idempotency key; existence checks go through the CDX API, never the Availability API, which returned 429 on a single cold request during reconnaissance |
| `ingest` | Run one source adapter; `--dry-run` prints the diff it would write and exits non-zero on schema drift |
| `resolve` | Identity resolution: surface candidate duplicates (same benchmark under two names, near-duplicate claims) for **human** decision. It never merges by itself |
| `promote` | Raise a record's `verification_status`, recording who, when, and against which evidence |
| `build` | Emit the shipped JSON artifacts plus SQLite and the derived tables ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2 owns the artifact set) |
| `embed` | Compute static (model2vec/potion-style) embeddings and quantise to int8 |
| `atlas` | Compute Atlas positions through the frozen SVD basis with a warm start and a Procrustes drift gate |
| `report` | The operational dashboards: staleness queue, coverage matrix, quality flags, conflicting claims, generated attribution page, condition-completeness distribution, and taxonomy health (term discrimination, unmet-term rate, per-term IRR, tag density, orphan rate, churn — [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §11 defines each and its threshold) |
| `diff` | A human-readable data changelog between two refs -- the input to release notes and the `/changes` feed |
| `suite` | Deterministic suite assembly: given a stated need, select benchmarks and export a manifest with links and recommended conditions. The AI layer in [11-ai-features.md](11-ai-features.md) calls this; it does not replace it |
| `eval` | Run the AI-layer golden set and report the retrieval and judge metrics with their intervals. `--judge` scores against the held-out human labels. It exists so the self-evaluation in [11-ai-features.md](11-ai-features.md) is a command anyone can re-run, not a number we publish about ourselves |
| `release` | Tag, generate release notes from `bench diff`, build the data tarball and SQLite, and trigger the Zenodo DOI |

**This code block is the CLI's only specification, and that has a consequence worth stating.** A
command that is not in it is a command nobody builds. Five subcommands, one `report` subject and one
flag were being invoked by [00-vision-and-scope.md](00-vision-and-scope.md),
[03-taxonomy-build-process.md](03-taxonomy-build-process.md),
[04-data-model.md](04-data-model.md) and [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
as though they existed here, and they did not. The rule from here: **other documents add to this
surface, they never invent on it**, and the mechanical check is a grep — every `bench <subcommand>`
appearing anywhere in the plan must appear in this block.

### Why `bench new` matters more than it looks

A template that stubs every required field with an inline comment explaining it is how curation
quality stays consistent across contributors. It is the cheapest quality intervention available and
it is the one most often skipped.

```yaml
# bench new benchmark --id libero --domain robotics-embodiment/manipulation
id: libero
name:                    # Official name, exactly as the maintainers write it. Not our paraphrase.
aliases: []              # Every other spelling in the wild. Searchable. Include the paper's name.
tagline:                 # ONE sentence, <120 chars, for a non-specialist. Shown on cards and Atlas hover.
description: |           # Neutral register. What the task is, what it measures, known weaknesses.
                         # No comparative or promotional language — CI flags "state-of-the-art",
                         # "the gold standard", "best-in-class".

domain:
  primary: robotics-embodiment/manipulation   # Exactly one. From taxonomy/domains.yaml. The navigational spine.
  secondary: []                    # Zero or more. Use when a benchmark genuinely straddles fields.
capability: []           # Multi-valued, from taxonomy/capabilities.yaml. What ability is under test?

data:
  contamination_risk:    # none|low|medium|high|unknown. ABOVE `medium` REQUIRES contamination_evidence.
  contamination_evidence: []       # Source IDs. CI enforces this pairing — no assertion without evidence.
  size:
    items:               # Integer. If unknown, leave null. NEVER estimate. A null renders as "not curated";
                         # a guess renders as a fact, and that is the failure this project exists to prevent.
    unit:                # Free text: issues, images, episodes, targets, trajectories, grid-cells.

curation:
  added_by:              # Your handle.
  last_verified:         # Today, ISO date. The date YOU opened the sources, not the date you copied a field.
  verification_status: ai-drafted-unverified   # See §4. Entries at this level are NOT published.
  sources: []            # At least one. No field may be filled from memory or inference.
```

The comments do three jobs at once: they teach the taxonomy at the moment of use, they state the
null-versus-guess rule where it is about to be violated, and they make the review checklist
self-documenting. Contributors who never read `CONTRIBUTING.md` still meet the rules.

---

## 4. The curation doctrine

### The sourcing rule

**No field without a source.** Every entry cites at least one primary source. Every result claim
cites exactly one. Curators may not fill fields from memory or inference.

This rule exists because the failure mode for an AI-assisted index is not obvious error -- it is
plausible, well-formatted, confidently wrong data that launders a guess into apparent authority. A
hallucinated item count in a YAML file looks exactly like a correct one. It renders in the same
typeface, sorts in the same column, and gets cited in the same papers. **An index that might be
hallucinated is worse than no index**, because a reader has no way to tell which fields to check.

The rule has a corollary that curators find harder than the rule itself: **`null` is a valid,
respectable answer, and it is always better than a plausible number.** The UI renders a null as
"not curated" and the coverage report counts it as missing work. That is the correct outcome. The
recon report on the AI layer names the equivalent failure precisely: a cost estimate computed from a
null `n_items` renders as "unknown -- `n_items` not curated", never as a guess, and a suite total is
annotated "computed from 9 of 12 entries".

### AI-assisted drafting is allowed, expected, and marked

Drafting entries with model assistance is not merely permitted, it is the plan -- a two-person team
cannot curate several thousand benchmarks otherwise. The requirement is that the machine's output is
never mistaken for a human's verification.

| `curation.verification_status` | Meaning | Published? |
| --- | --- | --- |
| `ai-drafted-unverified` | A model wrote it from cited sources; no human has opened those sources | **No. Excluded from the build entirely.** |
| `machine-ingested` | Written by an ingestion adapter from a structured source under a known licence | Yes, badged, and excluded from comparison views below a completeness threshold |
| `curator-reviewed` | A human read it and it is internally coherent; not every field re-checked against source | Yes, badged |
| `primary-source-verified` | A human opened each cited source and confirmed each factual field against it | Yes |
| `expert-reviewed` | A domain expert outside the core team reviewed it | Yes, badged |
| `maintainer-confirmed` | The benchmark's own maintainers signed off | Yes, badged |

Two enforcement rules make the ladder real rather than decorative:

- **`ai-drafted-unverified` entries never reach the published build.** Not greyed out, not behind a
  toggle -- absent. CI enforces this as a blocking gate on `main`. The moment unverified drafts are
  publishable "just for coverage", the ladder is theatre and the number-count metric has quietly
  become the goal.
- **Numeric fields require the source quoted in the PR body.** Item counts, dates, baselines,
  ceilings, scores. Not linked -- quoted, as text, with the URL. This takes a curator fifteen extra
  seconds and it is the single highest-yield review mechanism in the workflow, because it is
  impossible to do while hallucinating.

### Ingest versus hand-curate: where the labour goes

The tiering is settled and is the concrete mechanism for the user's "avoid repetition" requirement.
Where a mainstream leaderboard already maintains the numbers -- which is most LLM benchmarks -- we
catalogue the benchmark richly and ingest or link rather than hand-curating claims. Where nobody
else has numbers -- robotics, chemistry, climate, protein structure, formal proof -- we curate
claims ourselves. [01-landscape-and-positioning.md](01-landscape-and-positioning.md) argues the
policy; this section specifies what it means for the tree.

The Epoch AI decision is the worked example and it is settled. The local `epochdl/` snapshot is 81
benchmarks, 390 models and roughly 6,598 result rows under CC-BY, of which **zero touch robotics,
chemistry, biology, medicine, climate, materials or audio**. Policy:

1. **Ingest all rows** into `data/claims/_ingested/epoch/`, each carrying `provenance:
   epoch-2026-09-16`, a verification level assigned by rule, an honestly computed
   `condition_completeness` (expect a mean around **0.10**), and `curation.verification_status:
   machine-ingested`. Do **not** mix them into `data/claims/` proper.
2. **Default sort and filter on verification and completeness.** Comparison views hide
   machine-ingested claims below the completeness threshold; browse and search views still show
   them. The bulk data then provides *coverage* -- a great searchable collection, which is exactly
   what the user asked for -- without polluting *comparison*, which is where credibility lives.
3. **Hand-curate 50--80 LLM claims, chosen adversarially rather than representatively**: one model
   family across several reasoning efforts fully specified; one benchmark where multiple sources
   disagree, with all sources archived; one benchmark across several scaffolds; and the
   science-adjacent benchmarks that bridge to the non-LLM half of the map.
4. **Spend everything else on the non-LLM domains**, where hand-curation has no substitute and no
   competitor.

The directory boundary between `data/claims/` and `data/claims/_ingested/` is therefore not
housekeeping -- it is the structural expression of the project's entire quality argument. A reviewer
who cannot tell at a glance whether a number was verified by a person cannot review. A path prefix
tells them.

---

## 5. The review matrix

| Change | Reviewers | Required evidence |
| --- | --- | --- |
| Typo, formatting, link fix | 0 (self-merge by any maintainer) | none |
| Adoption counters into `metrics/` | 0 (bot auto-merge) | adapter run record |
| New benchmark entry | 1 | Sources opened and checked; numeric fields quoted in the PR body |
| Result claim (hand-curated) | 1 | Source link verified and archived; `condition_completeness` stated in the PR |
| Bulk ingest PR (`ingest:new`, `ingest:update`) | 1 | Rendered before/after table in the PR body; adapter version; response hash |
| Numeric result change from ingest (`ingest:result`) | 1, **always human** | Old value, new value, source URL, Wayback URL, fetch timestamp |
| `verification_status` promotion | 1, not the author | The evidence cited in `bench promote --evidence` |
| Contamination flag (`contamination_risk` above `medium`) | 2 | A published, linked, archived evidence source |
| Lifecycle → `retracted` / `disputed` / `dead` | 2 | Public rationale in the PR body; the observable signal (dead repo, withdrawn paper, maintainer statement) |
| Human baseline addition | 2 | Methodology of the baseline, n, population, time limit |
| Taxonomy term addition or gloss change | 2 + ADR | See [03-taxonomy-build-process.md](03-taxonomy-build-process.md) |
| Moving a capability term between groups in `capability_groups.yaml` | 2 + ADR | The re-shaped gap claims, named. Nothing in `data/` references a group id, so this touches no benchmark record and would otherwise look like a one-reviewer edit -- while silently changing every published coverage figure in both affected columns ([02-taxonomy.md](02-taxonomy.md) §11 rule 9) |
| Schema change | 2 + ADR + migration script + full revalidation | Regenerated JSON Schema and TS types committed in the same PR |
| Licence, governance or succession change | 2, both named maintainers | ADR |

Taxonomy and schema changes are deliberately the hardest things to do in this repository. An open
vocabulary degrades into synonyms within months and silently destroys the coverage analysis, which
is one of the project's most valuable outputs -- a gap matrix built on `code-generation`,
`code_generation` and `program synthesis` as three distinct terms is worse than no gap matrix,
because it looks authoritative.

The asymmetry is deliberate in the other direction too: **fixing a wrong number is the easiest
change in the repository, and adding a new vocabulary term is one of the hardest.** A project that
gets this backwards accumulates errors while debating terminology.

---

## 6. Contribution paths

This section is load-bearing. `JonathanChavezTamales/llm-leaderboard` was a git-backed,
schema-validated community benchmark catalogue with 356 stars and 40 forks. It deprecated itself and
became a closed website, and the stated reason was that pull requests were too slow compared with
per-model discussion threads on a site. **A PR-only workflow is a documented cause of death for
exactly this kind of project.** The gravity is real: every contributor who bounces off a git
workflow is a data point arguing for a CMS, and enough of them will eventually win the argument.

So there are two paths, and the default is not the PR.

### Path A (default): the issue form

Modelled directly on UK AISI's `inspect_evals` `/register/` mechanism, launched **2026-05-08** in
`github.com/UKGovernmentBEIS/inspect_evals` (MIT, 674 stars, 171 evals), where a GitHub issue
submission is validated by a bot which derives the eval metadata and opens the PR itself. It is the
closest institutional analogue to our curation model and it works.

Five forms live in `.github/ISSUE_TEMPLATE/`:

| Form | Purpose |
| --- | --- |
| `new-benchmark.yml` | Add a benchmark we do not have |
| `correction.yml` | Fix a wrong field on an existing entry |
| `new-claim.yml` | Add a result claim with its conditions |
| `dispute.yml` | Contest an entry without asking for deletion (§8) |
| `taxonomy-term.yml` | Propose a vocabulary term; routes to the ADR process, never auto-PRs |

`new-benchmark.yml` field list, as it appears to a contributor:

```yaml
- Benchmark name                     (input, required)
- Homepage or paper URL              (input, required, validated as a URL)
- One-sentence description           (input, required, ≤120 chars)
- Primary domain                     (dropdown, required — options GENERATED from taxonomy/domains.yaml)
- Secondary domains                  (dropdown, multiple, optional)
- Capabilities measured              (dropdown, multiple, required)
- Evaluation method                  (dropdown, multiple, required)
- What is evaluated                  (dropdown — model / agent scaffold / full pipeline / other)
- Repository URL                     (input, optional)
- Dataset or task-data URL           (input, optional)
- Licence                            (dropdown + "other/unknown")
- Number of items, and unit          (input, optional — "leave blank if you are not sure" in the hint)
- Maintaining organisation           (input, optional)
- Release date                       (input, optional, ISO)
- Leaderboard URL                    (input, optional)
- Is this a version or fork of an existing benchmark?  (input, optional — the lineage hook)
- Anything we should know            (textarea, optional — contamination, saturation, known problems)
- [ ] Every field above is supported by the linked sources; I have not filled anything from memory
- [ ] I understand this index links to data and never hosts it
```

Two mechanical details that keep the form honest:

- **The dropdown options are generated from `taxonomy/*.yaml` by CI**, and CI fails if regeneration
  produces a diff -- the same rule already settled for Pydantic → JSON Schema → TypeScript. The
  contribution form can therefore never drift from the controlled vocabulary, which is the usual way
  a form becomes a second, informal taxonomy.
- **Every entry page on the site carries a "Suggest a correction" link** that deep-links to
  `correction.yml` with the entity id and the field pre-filled through query parameters. (GitHub
  supports query-parameter prefill for issue-form fields by id; behaviour for dropdowns and
  checkboxes is more limited -- *unverified, confirm before relying on this* -- so the entity id goes
  in a plain text input as the fallback.)

### The validation bot

`issue-intake.yml` runs on `issues: [opened, edited]` for issues carrying a form label.

**On success**, within about a minute, the bot:

1. Parses the form body into a draft entity and runs `bench validate --tier schema,ref,semantic`.
2. Comments on the issue with the **rendered YAML it intends to write**, in a fenced block, so the
   contributor can see exactly what will land.
3. Opens a pull request on branch `contrib/<issue-number>-<slug>`, titled after the entry, with the
   issue linked and closed-on-merge, labelled `source:issue-form` and
   `verification:curator-review-needed`.
4. Sets `curation.verification_status: ai-drafted-unverified` unless the submitter is a recognised
   maintainer of the benchmark, in which case it sets `maintainer-confirmed` pending review.
5. Adds `Co-authored-by: <contributor>` to the commit. This matters more than it sounds: it means an
   issue-form contributor appears in `git log`, in GitHub's contributor graph, and in the release
   notes as a real contributor to a CC-BY dataset. Academic contributors care about this, it costs
   one trailer line, and it is the reason to prefer a bot-authored PR over a bot-authored direct
   commit.
6. Comments once more with the PR link and a plain-language statement of what happens next and
   roughly when.

**On failure**, the bot:

1. Comments with **field-level errors only** -- "Primary domain `robotics-embodiment/grasping` is
   not in the vocabulary. Did you mean `robotics-embodiment/manipulation`? The full list is here:
   <link>." Never a stack trace, never a raw Pydantic error dump.
2. Labels the issue `needs-fix` and **leaves it open**. It does not close it, does not
   ask the contributor to start over, and does not open a broken PR.
3. Re-runs automatically when the issue body is edited, and replaces its own previous comment rather
   than appending, so the thread stays one comment long.
4. After three failed attempts, adds `needs-human` and pings the domain steward from `CODEOWNERS`.
   A contributor who has tried three times is not the problem; the form is.

The bot **never merges**. Branch protection on `main` requires one human approval and the passing
validation check, with no bot bypass. That constraint is what makes "fully auditable" true rather
than aspirational, and it is worth the latency.

### Path B: the direct pull request

For power users, maintainers, bulk edits and anything the form does not model (lineage
restructuring, subset definitions, schema-adjacent work). `bench new`, `bench fmt`, `bench validate
--changed-only`, push, open PR. The PR template asks for exactly the evidence the review matrix
requires, including the quoted source text for numeric fields.

### Path C: bot ingest PRs

Adapters open their own PRs -- one per source per run, batched, never one per benchmark. Details are
in [07-ingestion-infrastructure.md](07-ingestion-infrastructure.md); the workflow-relevant rules are
that the PR body is the review surface (a rendered table of entity, field, old → new, source URL,
Wayback URL, fetch timestamp, plus the raw response hash), that numeric result changes are always
human-reviewed, and that exactly one class of change auto-merges: adoption counters into `metrics/`,
which sit outside the citable CC-BY core precisely so that auto-merge is safe there.

### The ten-minute walkthrough

The target: **an outside expert fixes one wrong number in under ten minutes, with no git knowledge
required.** Concretely, a crystallographer notices our CASP entry lists the wrong number of targets.

1. On the benchmark page, they click **"Suggest a correction"** next to the field. *(~5 seconds)*
2. GitHub opens `correction.yml` with the entity id and field name pre-filled. They sign in or
   create a free account. *(~60 seconds, once, ever)*
3. They enter the correct value, paste the URL of the CASP17 target list, and paste the sentence
   from it that states the number. *(~3 minutes)*
4. They submit. The bot validates, comments with the exact YAML change it will make, and opens PR
   #412 with them as co-author. *(~60 seconds, unattended)*
5. A maintainer opens the PR, clicks the source link, reads the quoted sentence, approves, merges.
   *(~2 minutes of maintainer time, within the stated 72-hour target)*
6. The next deploy rebuilds the site. The entry shows the corrected value, a fresh `last_verified`
   date, and the contributor's name in the entry's history. The change appears on `/corrections`
   and in the release notes.

Elapsed contributor effort: about four minutes, of which none required a clone, a branch, a YAML
file or a command line. That is the number to protect. If it ever creeps past ten minutes, the
project is on the llm-leaderboard trajectory and the response is to fix the form, not to exhort
contributors to learn git.

### 6.5 `CONTRIBUTING.md`, and the curator handbook that is not the same document

The walkthrough above is for the **outsider who fixes one field**. It is the right first experience
and it is the mechanism against the llm-leaderboard failure. It is not, however, what the person who
writes three hundred entries needs, and the plan has until now named `CONTRIBUTING.md` as a filename
and specified nothing inside it. That is a conspicuous gap in the document that owns the project's
stated cause-of-death countermeasure: the mortality record says the curation treadmill kills these
projects, and a treadmill with no onboarding path has exactly one person who can walk it.

**`CONTRIBUTING.md` is short and has four sections, in this order.** Order matters because most
readers stop after the first: (1) *Fix one thing* — the correction issue form, with a screenshot,
two paragraphs, no git; (2) *Add a benchmark* — the `new-benchmark.yml` form, what the four required
fields are and why a source URL plus a quoted sentence is non-negotiable; (3) *What happens next* —
the bot's one-minute turnaround, the rendered-YAML comment, the `Co-authored-by:` trailer, the
72-hour review target and the honest 7-day median; (4) *Working in git*, for the minority who want
Path B, which is the only section that mentions a clone. If section 4 appears before section 3, the
document has recreated the barrier it exists to remove.

**The curator handbook is a different artifact and lives at `docs/curating.md`.** It teaches
judgement, not fields — `bench new`'s template comments already teach fields, and they do it well.
Its spine is **one entry curated end to end, in full, with the reasoning shown**: a mid-difficulty
non-LLM benchmark rather than an easy one, showing where the curator stopped and looked something
up, which two facets they hesitated over and why, what they left `null` and why leaving it `null`
was correct, and the `tag-gap` they filed when the vocabulary could not express something. Around
that spine sit five short rules that only make sense once you have seen the worked case: when to
stop researching (the 90-minute ceiling, and that an entry at `stub` in the corpus beats a perfect
entry in a branch); when `null` is the right answer and why estimating is worse than admitting;
how to read a leaderboard page adversarially; when to file a `tag-gap` instead of forcing a term;
and how to tell a benchmark family from its children, which is the single most common early mistake
and the one that silently corrupts every published count.

**What a contributor gets back, stated because retention is not automatic.** The `Co-authored-by:`
trailer is real but thin. Four things cost us nothing and compound: every contributor is named in
the release notes and in `CITATION.cff`'s contributor list, so a release DOI cites them; the
`/corrections` page names who reported each fix, which is a public, linkable record of having
improved a cited dataset; a domain reviewer's sign-off renders on every entry in their family with
their name and ORCID; and the taxonomy-plus-gap-matrix preprint at the end of Phase 1 carries
contributors as named authors on the same basis. Academic contributors are paid in citable credit,
and this project can mint that at no cost — which is the only currency it has.

**The `CODEOWNERS` trigger, pre-committed so it is not a judgement call.** A contributor who has had
**three substantive merges in one domain family** is offered path-scoped `CODEOWNERS` ownership of
that family. Three rather than one, because the offer has to mean something; scoped to the family
rather than the repository, because per-domain stewardship is the structure §10 point 6 argues for
and MedHELM is the case that worked. `codeowners-lapse.yml` (CI check 9j) closes the loop at the
other end: a steward who has not touched their path in 180 days gets an issue proposing
reassignment, because a `CODEOWNERS` entry pointing at someone who has stopped answering routes
every PR in that family into silence, which is worse than no entry at all.

**The second rater has a recruitment path and it is not here.**
[03-taxonomy-build-process.md](03-taxonomy-build-process.md) §6.5 owns it, because the ask is bundled
into reviewer recruitment rather than into contribution.

### 6.6 What this section costs, honestly

`CONTRIBUTING.md` is 2–3 hours. The curator handbook is **6–10 hours**, because the worked entry has
to be a real entry curated in public rather than a description of one, and it should be written
*after* the first twenty entries, not before — a handbook written before anyone has curated at scale
teaches the process the author imagined. Both belong in [14-roadmap.md](14-roadmap.md)'s effort
table; neither is currently in it. The failure mode being named: **the documents that would keep a
two-person team curating past month four are the ones that get deferred**, because they are the only
deliverables with no visible artifact on the site, and deferring them is exactly the asymmetry that
produced Ecosystem Graphs — a well-designed architecture with nobody left to feed it.

---

## 7. Freshness

Every entry carries `curation.last_verified` -- the date a human last opened the cited sources and
confirmed the fields, not the date a field was last touched. The build computes staleness and **the
site displays it on every entry**: "Last verified 14 months ago."

Staleness is displayed rather than hidden precisely because the alternative -- a confident-looking
entry that is silently three years out of date -- is the most common way reference sites lose trust.
This is not hypothetical. Ecosystem Graphs is twenty months stale and still being used as a data
source in 2025--26 research; Evidently AI's 250-benchmark database was last updated 2025-07-31 and is
cited by a 2026 paper; BetterBench calls itself a "living repository" and still shows 24 benchmarks.
None of those sites tells a reader they are stale. **A visible staleness badge is the cheapest
honesty mechanism in the entire design, and it is the one nobody else ships.**

The re-verification queue is prioritised, because a flat "oldest first" list wastes the scarcest
resource in the project:

```
priority = staleness_days × volatility_weight × attention_weight

volatility_weight:  active 1.0 | saturated 0.6 | deprecated 0.3 | dead 0.2 | retracted 0.1
attention_weight:   1 + log10(1 + pageviews_30d)          # from privacy-preserving analytics
                    × 1.5 if the entry is cited in any published suite manifest
                    × 2.0 if any claim on it is disputed
```

Display thresholds, applied by the build and visible in the UI:

| Age of `last_verified` | Treatment |
| --- | --- |
| < 180 days | Neutral text |
| 180--365 days | Amber badge |
| > 365 days | Red badge, "not verified in over a year", demoted below fresher entries in default sort |
| > 730 days on an `active` benchmark | The entry enters `bench report staleness --critical` and an issue opens automatically |

Liveness signalling is the related differentiator and it is cheap: one study found **137 of 195**
safety benchmarks had stale GitHub repos and **96 of 195** had stale HuggingFace datasets, and
BetterBench found **17 of 24** benchmarks had no working reproduction scripts. Nobody marks
benchmarks as dead. The weekly `health-check.yml` job records observable signals -- repo last-push
date, dataset last-modified, leaderboard last-updated, HTTP status -- into `metrics/`, and a
benchmark whose every signal has been cold for twelve months is proposed for `lifecycle: dead` by
bot and confirmed by two humans. The signal is observable and linked; the classification is human.

---

## 8. Corrections and disputes

Anyone -- including benchmark maintainers and the organisations whose systems are being evaluated --
can dispute an entry through `dispute.yml`. Three rules govern what happens next.

**Disputes are never resolved by deletion.** A disputed claim gains an entry in `disputed_by[]`, a
file appears in `data/disputes/`, and the claim renders with both positions visible: the original
number with its source, and the dispute with its source. The reader decides. Deleting a contested
number converts a public disagreement into a private one and destroys the audit trail that is the
entire point of the architecture.

**If the index is wrong, the fix is a commit with a rationale**, and history preserves what was
previously shown. We do not quietly edit. A `/corrections` page, generated from commits touching
`data/` that carry a `Correction:` trailer, lists every substantive correction with the date, the
entity, what it said before, what it says now, and who reported it. Visible error-correction is what
distinguishes a reference from a marketing page, and it is a standing invitation to the people best
placed to catch our errors.

**A dispute from an evaluated party gets the same treatment as one from a stranger.** The dispute
record carries `disputant_relationship: evaluated-party | benchmark-maintainer | third-party |
unknown` and the site shows it. An organisation contesting its own score is useful information, and
so is the fact that it is the one contesting.

The dispute file is small:

```yaml
id: dispute-swe-bench-verified-2026-09
concerns: claim-3c8e10ba55f7
raised_by: org-example-lab
disputant_relationship: evaluated-party
raised_on: 2026-09-14
position: |
  The cited figure was obtained with a scaffold not described in the source, and the
  benchmark's own harness reports a materially different number.
evidence: [src-example-lab-response-2026]
our_response: |
  Claim retained, annotated, and a second claim added from the harness output.
  Both render with their conditions.
status: open        # open | resolved-claim-corrected | resolved-claim-retained | withdrawn
```

### 8.1 When the request is removal rather than correction

The three rules above cover a *factual* dispute. They do not cover the request the plan is actually
most likely to receive from a lawyer: **take our entry down.** That request is not a dispute, it
cannot be answered with `disputed_by[]`, and answering it badly — either way — is expensive. So the
answer is pre-committed here rather than improvised under pressure, which is the same posture
[15-open-questions.md](15-open-questions.md) §C7 takes to legal threats generally.

**Entries are not deleted, and the reason is structural rather than defiant.** A catalogue that
removes entries on request is a catalogue whose absences are uninterpretable: every empty cell in
the coverage matrix becomes ambiguous between "nobody measures this", "we have not surveyed it" and
"somebody asked us to remove it", and the gap matrix is the project's most valuable output precisely
because its empty cells mean something. Removal would also make the corpus non-reproducible at a
commit hash, which is the citability guarantee the whole architecture exists to provide.

**What we will do instead, in escalating order, and each of these is a real remedy:** correct any
field that is wrong, with the correction visible on `/corrections`; add the maintainer's own
statement, rendered first and dated, through the `maintenance_status_contested` mechanism
([02-taxonomy.md](02-taxonomy.md) §8) or a dispute record; mark the entry `lifecycle: retracted` or
`deprecated` where the maintainer has withdrawn the benchmark itself, which is a real state with a
real rendering; and, where a specific field is genuinely not ours to publish, remove that field
while the entry remains. The one thing we do not do is make the record disappear.

**Personal data is severable, and is severed on request without argument.** The repository holds
three kinds of personal data and it is worth naming them rather than discovering them during a
subject-access request: contributor handles and `Co-authored-by:` trailers in git history; author
names on `Source` records; and named domain reviewers with their ORCIDs. The position: reviewer
names and ORCIDs are published with explicit consent and are withdrawn on request, from the current
data and from the next release, with the sign-off downgraded to `generalist` and the entry's
`reviewer_signoff` recomputed. Source author names are bibliographic metadata, published for the
same reason a citation carries them, and are not removed. Git history is not rewritten, because
rewriting it breaks every commit hash anyone has cited; a contributor who asks to be
de-identified going forward gets that, and the history stands. Say all of this in `SECURITY.md` and
in a `/privacy` page **before** anyone asks, because a position invented in response to a request
reads as a position invented to suit the requester.

**The contact route, published.** A `contact@` address on the site and in `SECURITY.md`, not a
personal inbox; a stated **acknowledgement within 5 working days** and a **substantive response
within 20**; and the commitment that every removal or erasure request and its outcome is recorded
in `data/disputes/` with the requester's identity redacted where they ask. Publishing a slow,
honoured response time is better than publishing a fast one that is missed, for the same reason S5's
correction criterion is written at a 7-day median rather than the 72-hour goal.

**`SECURITY.md` covers three things and no more:** how to report a vulnerability in the site or the
bot (the same contact address, with a 90-day coordinated-disclosure window); the statement that the
issue-intake bot parses untrusted input and therefore never runs contributor-supplied code, never
interpolates issue text into a shell, and opens PRs with a token scoped to a single branch prefix —
a bot that reads untrusted issue bodies and opens pull requests is a privilege-escalation surface and
it is the one part of the supply chain that is uniquely ours; and where to send a removal or
personal-data request, pointing back here.

---

## 9. Continuous integration

CI is the only thing standing between a two-person team and a corpus that slowly stops meaning what
it says. It runs in **GitHub Actions**, which is free with unlimited minutes for public repositories
on standard runners, and deploys to **Cloudflare Workers with static assets** via `wrangler deploy`
(see [08-infrastructure-and-build.md](08-infrastructure-and-build.md) for why Workers rather than
Pages or GitHub Pages).

### On every pull request (`pr-validate.yml`)

| # | Job | Blocking | Notes |
| --- | --- | --- | --- |
| 1 | `bench fmt --check` | Yes | Kills cosmetic diffs before they become merge conflicts |
| 2 | Schema validation (Pydantic) | Yes | |
| 3 | Referential validation | Yes | Every `id` referenced exists; no reference into `tombstones/` without a redirect |
| 4 | Semantic validation | Yes | Cross-field rules: contamination evidence, judge-model presence, breaking-version flags |
| 5 | **Codegen drift check** | Yes | Regenerate JSON Schema from Pydantic and TS from JSON Schema (`json-schema-to-typescript@16.0.0`); fail on any diff. Also regenerates the issue-form dropdowns from `taxonomy/` |
| 6 | **`verification_status` gate** | Yes | No `ai-drafted-unverified` record may reach `main`'s published build |
| 7 | **Metadata-only invariant** | Yes | Reject any `.parquet`, `.jsonl`, `.csv`, `.npz` or archive file under `data/`; reject any file in `data/` over 256 KB; reject any single prose field over N characters. This makes "we never host datasets" a mechanical fact rather than a promise |
| 8 | **Licence firewall** | Yes | Reject any commit that moves content out of `vendor/` into `data/` without a `Re-derived-from:` trailer naming a primary source |
| 9 | ID-reuse check | Yes | Against `taxonomy/retired-ids.yaml` |
| 9a | **Forbidden-identifier grep** | Yes | `taxonomy/forbidden-identifiers.yaml` lists renamed field names that must never reappear. The scanned set is an explicit **allowlist of paths** -- `data/`, `taxonomy/`, `tools/`, `schema/`, `ingest/`, `scripts/` -- minus `taxonomy/forbidden-identifiers.yaml` and `taxonomy/retired-ids.yaml`, which list dead identifiers by construction and which a naive grep over `taxonomy/` fails against. `docs/`, `adr/`, `CHANGELOG.md` and `_plan/` are never scanned, and that is a declared exemption rather than an omission: a rename must stay explainable, and the explanation has to name the old identifier. First entry: `human_baseline_type`, renamed to `ceiling_anchor_type` on 2026-09-21 ([02-taxonomy.md](02-taxonomy.md) §7) |
| 9b | **Taxonomy stats drift check** | Yes | `python scripts/taxonomy_stats.py --check` regenerates the vocabulary summary table and every term count in [02-taxonomy.md](02-taxonomy.md) §14 and [12-analytics-and-trends.md](12-analytics-and-trends.md) §5.1 from `taxonomy/*.yaml`; fail on any diff. Counts in prose are generated, never typed |
| 9c | **Vocabulary id uniqueness** | Yes | Within each `taxonomy/*.yaml`: `id` is unique across `terms[]` **including `deprecated` and `retired` terms**. In `domains.yaml`: every term with a `parent` satisfies `id == f"{parent}/{leaf}"`, every term without one is a family, and **`leaf` is unique across the whole file, not merely within its parent** -- a leaf under two families renders two dropdown options with the same label and splits one coverage row into two thin ones. Across files, the facet-qualified id `{facet}:{id}` is unique by construction; assert it rather than assume it. All ids match the grammar in [04-data-model.md](04-data-model.md) §2 |
| 9d | **Homograph declaration** | Yes | A *homograph* is a capability `id` equal to the leaf segment of a subdomain `id` -- today `planning`, `spatial-reasoning`, `temporal-reasoning`, `compositional-generalization`. These are permitted: the Capability facet is orthogonal to Domain by design and the same word is the honest name on both axes. **Undeclared ones are not.** Every computed homograph must appear in `taxonomy/homographs.yaml` with `capability`, `domain`, `relationship` (`same-concept-two-facets` \| `false-friend`) and a one-sentence `rationale`; and every declared entry must still compute, because an allowlist that outlives its entries rots into blanket permission to collide. A `false-friend` entry additionally requires a `not_to_be_confused_with` block on both terms |
| 9e | **Tautological coverage cells** | Yes | For each `same-concept-two-facets` homograph, the fine-grid cell (subdomain `F/X`, capability `X`) is occupied by construction and yields no gap finding in either direction -- full reports the tagging convention, empty reports that the row is empty. `bench build --derived` must emit `degenerate: tautological-homograph` on exactly those cells in `build/derived/coverage.json`; the fine-grid renderer hatches them and excludes them from gap ranking and from both the numerator and the denominator of every coverage percentage ([10-visualization.md](10-visualization.md) §"Three cell states"). Assert the flagged set equals the `same-concept-two-facets` declarations -- currently 4 cells of 8,976 |
| 9f | **Seed-target integrity** | Yes | `python scripts/taxonomy_stats.py --check` also asserts, against `taxonomy/domains.yaml`: exactly one `seed_target` per domain family with no family missing and none listed twice; the sum equals the canonical seed total (320); every target >= 12 unless that family carries `coverage_status: under-surveyed`; every family with `core: true` is >= 18 and carries no `under-surveyed` status; and the rendered table in [02-taxonomy.md](02-taxonomy.md) §3 matches the YAML byte for byte. Three documents carried three different seed totals because nineteen numbers lived in two hand-maintained tables |
| 9g | **Capability-group partition** | Yes | `python scripts/taxonomy_stats.py --check` also asserts that `taxonomy/capability_groups.yaml` is a strict partition of `taxonomy/capabilities.yaml`: every capability term is in exactly one group, no member is unknown, no member is listed twice, and no group id equals a capability id, a subdomain leaf or a domain-family slug. The group `version` is recorded in `build/derived/manifest.json` and cited with every published coverage figure, so a re-grouping is attributable even though nothing in `data/` references a group id. A rollup that is not a partition silently double-counts or drops benchmarks in every coverage figure the site publishes -- and the absence of this check is why the coarse axis was cited by two documents and enumerated by neither ([02-taxonomy.md](02-taxonomy.md) §4.3 owns the enumeration) |
| 9h | **Display-only vocabulary containment** | Yes | `scripts/check_display_only_vocab.py` asserts `taxonomy/domain_groups.yaml` is a total partition over the domain families in `taxonomy/domains.yaml`, and greps every shipped JSON artifact ([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2 owns the list), `build/derived/coverage.json`, `build/derived/gaps.json`, `build/derived/ecosystem.json` and the Croissant JSON-LD for presentation-group ids, failing on any hit. `build/atlas.json` is the single permitted consumer, because banding is a layout property. The grouping orders and bands the views; it is not a filter key and no published coverage or gap number may be computed over it ([09-design-system.md](09-design-system.md) §4.2, [10-visualization.md](10-visualization.md) V1/V2) |
| 10 | Link check on changed sources | Yes on 4xx for new links | 5xx and timeouts warn rather than fail; the open web is unreliable and a flaky CI gets disabled |
| 11 | Archive capture | Yes for new non-DOI sources | `bench archive` via Wayback SPN2 with `if_not_archived_within=30d`; writes `archive_url` back into the source file on the branch |
| 12 | Quality report | No | PR comment: condition-completeness distribution, staleness of touched entries, near-duplicate candidates from `bench resolve --candidates` |
| 13 | Build | Yes | `bench build --derived`; fail on any build error. Atlas is **not** regenerated on PRs |
| 14 | Preview deploy | No | A Workers preview URL per PR |

**Why 9c was rewritten, because it is the instructive one.** The earlier version asserted `not
(set(capability ids) & set(subdomain slugs))`, and it could never have passed: `planning`,
`spatial-reasoning`, `temporal-reasoning` and `compositional-generalization` are terms in both the
Capability vocabulary and the Domain spine. Worse, it would still have been the wrong check after
the collisions were removed, because it compared capability *ids* against subdomain *leaf segments*,
and a leaf segment is not an identifier -- `planning` is the tail of `reasoning-general/planning`
the way `verified` is the tail of `swe-bench@verified`. Subdomain ids are family-qualified paths, so
the two id sets are already disjoint and have been since the Domain facet acquired two levels. The
named failure mode is **a CI assertion rewriting the taxonomy**: the only way to make the old check
green was to rename four terms that name the same concept seen through two facets, which is exactly
what a faceted classification is for. So the assertion is now correctly scoped (9c), the homographs
are permitted but must be declared with a rationale (9d), and the four fine-grid cells where the
same word is both row and column are marked as occupied-by-construction rather than counted as
evidence (9e). Full reasoning in `_workflow/decisions/D3-vocabulary-namespacing.md`.

**Numbering, stated once so the cross-references resolve.** Two decisions landed on 2026-09-21 and
both claimed the label `9d`. The homograph numbering wins it, because `9d` and `9e` are cited by
[02-taxonomy.md](02-taxonomy.md) §11, [03-taxonomy-build-process.md](03-taxonomy-build-process.md)
§4 and [10-visualization.md](10-visualization.md); the seed-target check is therefore **9f**, and
every citation of it elsewhere now says 9f. (An earlier revision of this paragraph instead told the
reader to mentally substitute 9f wherever another document said 9d. That is not a fix — it is a
permanent tax on every future reader, and it is the same agreeing-by-footnote arrangement that
drifts again on the next pass. The four wrong citations were corrected instead.) Group ids are a *third*
vocabulary namespace and are checked in **9g** rather than by widening 9d, because a group id
colliding with a capability term would put a tautological cell in the **coarse** grid, which unlike
the fine grid does publish gap claims -- a different and more damaging failure than the four fine
cells 9e exists to mark.

| 9i | **No AI-written record reaches the citable core** | Yes | Greps every path under `data/` for `provenance: ai-worker` and for `curation.verification_status: ai-drafted-unverified`, failing on any hit. AI drafts live in `drafts/` until a human has reviewed them. This is the mechanical enforcement of the governing rule in [11-ai-features.md](11-ai-features.md) — *nothing the model emits is ever stored in `data/`* — and without it that rule is an assertion rather than a property of the repository |
| 9j | **Steward lapse** | No — opens an issue | `codeowners-lapse.yml`: for each path-scoped owner in `CODEOWNERS`, if no review or commit from that handle has touched their path in 180 days, open an issue proposing reassignment and mark the family `reviewer_signoff: none` until it is resolved. A `CODEOWNERS` entry for someone who has stopped answering is worse than no entry, because it routes every PR into silence |

Three of these checks need data before they can go green: 9f needs `seed_target`, `core`,
`coverage_status` and `curation_posture` in `taxonomy/domains.yaml`, 9g needs
`taxonomy/capability_groups.yaml`, and 9h needs `taxonomy/domain_groups.yaml`. All three land in Phase 0 with the rest of CI and must not slip
past it. The point of each is that the next revision of these numbers is checked by a machine rather
than by a reader who trusts a tilde.

### Scheduled

Schedules use odd offsets, never `0 * * * *`. GitHub states that scheduled workflows can be delayed
or dropped under high load, and the top of the hour is the worst-contended slot. Every job is
idempotent so a dropped run is harmless.

| Workflow | Cron | Does |
| --- | --- | --- |
| `ingest-static.yml` | `17 4 * * 1` | Epoch ZIP/CSV, LiteLLM, EvalPlus, LiveBench, MTEB, lm-evaluation-harness task YAML |
| `ingest-hub.yml` | `23 5 * * *` | HuggingFace datasets, Spaces (the `leaderboard` tag set), models |
| `ingest-arxiv.yml` | `41 6 * * 1-5` | OAI-PMH delta on `set=cs` plus LLM triage |
| `ingest-leaderboards.yml` | `11 7 * * *` | HELM releases, SWE-bench, LMArena, Grand Challenge |
| `archive-sources.yml` | `31 3 * * *` | SPN2 capture for any source lacking `archive_url`; CDX digest check for content drift |
| `freshness.yml` | `7 8 * * 1` | Full link-rot sweep, staleness report, leaderboard-liveness check, opens the weekly re-verification issue |
| `health-check.yml` | `0 9 * * 1` | Canary: assert every adapter ran within N days; open an issue if not. Also a `workflow_dispatch` canary, because **public-repo scheduled workflows are automatically disabled after 60 days without repository activity** |
| `evals.yml` | On prompt/model/schema/index change | Golden-set run for the AI layer via the Batch API; writes `evals/results/<date>-<commit>.json` |
| `reproduce.yml` | `13 2 1 * *` | Clean-machine rebuild from `docs/reproduce.md` with nothing cached. This is the succession test (§10) and success criterion S7 in [00-vision-and-scope.md](00-vision-and-scope.md) §7.1, which states the cadence as monthly. **Monthly, not weekly**: this document owns the workflow inventory and its cadences, and where [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §7.3 said weekly under the name `reproducibility.yml` it was describing the same job under a second name. The filename is `reproduce.yml`, matching `docs/reproduce.md` |
| `release.yml` | On tag | Build data tarball + SQLite, generate notes from `bench diff`, push the Zenodo DOI, sync the data-only mirror |

### The atlas exception

`build/atlas.json` is written by **CI only**, on `main`, never on a PR and never from a developer's
machine. UMAP reproducibility is guaranteed across runs but *not* across machines (*unverified
across machines -- treat CI as the sole authority*), so a locally generated layout would silently
differ. The job projects through the committed frozen SVD basis, warm-starts from
`atlas/prev.json`, applies a Procrustes alignment, and **fails the build if median per-point
displacement exceeds 2% of the bounding-box diagonal**. That turns "the map silently reshuffled"
from an invisible trust failure into a CI error. See [10-visualization.md](10-visualization.md).

---

## 10. Releases, citation, and succession

### Releases and DOI

Quarterly tagged releases, each producing: a git tag, `bench diff`-generated release notes, a
`data.tar.gz` of `data/` + `taxonomy/` + `schema/generated/`, `index.sqlite`, and the two JSON build
artifacts. GitHub's Zenodo integration mints a DOI per release and a **concept DOI** that always
resolves to the latest version -- the same versioned/version-independent DOI pair Zenodo exposes as
`doi` and `conceptdoi`. `CITATION.cff` at the repository root gives GitHub's "Cite this repository"
button something correct to render, and the site's every entry page carries a "cite this entry" block
with the entity id, the concept DOI, and the current commit SHA.

Citability is not vanity. It is the mechanism by which this becomes infrastructure rather than a
website, and it is the property that makes a fork a continuation rather than a copy.

### What happens when we stop

Write this down before it matters, because the projects that did not write it down could not be
rescued. `SUCCESSION.md` — at the repository root, where a successor will look — states, publicly:

1. **The licence permits a fork without asking anyone.** Data and taxonomy are CC-BY-4.0; code is
   MIT. There is no clause, no NC, no SA, and no "contact us". Ecosystem Graphs had none of this and
   is therefore unrescuable -- 274 people starred a dataset nobody is legally clear to continue.
2. **Every release is citable and downloadable independently of us.** A DOI'd Zenodo record survives
   the GitHub organisation, the domain and the maintainers.
3. **Mirrors exist and are automatic.** GitHub is primary; a Codeberg mirror and a HuggingFace
   dataset repo mirror are pushed on every release; public GitHub repositories are archived by
   Software Heritage (*unverified whether this happens automatically for all repos or requires a
   save request -- submit one explicitly rather than assuming*).
4. **The build is documented and tested.** `docs/reproduce.md` specifies pinned versions (Python
   3.12, Node 22.12+, Astro 7.3.x, the exact `umap-learn` / `scikit-learn` / `numba` pins) and
   `reproduce.yml` rebuilds the whole site monthly on a clean runner with no cache. A build
   procedure that is not tested is a build procedure that does not exist, and it is how "you can
   just fork it" turns out to be false at exactly the moment it is needed.
5. **Dormancy is announced by the repository itself, automatically, and succession comes before the
   banner.** The build reads the date of the last human commit to `data/`. **At 90 days
   `SUCCESSION.md` is invoked**: a `Maintainer succession` issue is opened and pinned, the README
   carries the notice, the steward list is contacted, and the search begins. **At 180 days the
   site-wide staleness banner turns on** — *"This index has not been curated since <date>. Data
   older than that should be checked against primary sources."* — driven by the same commit
   timestamp. The order is deliberate and it was settled in this pass against an earlier draft that
   had the two reversed: the steward search has to start while the data is still worth taking on,
   whereas the banner is a public admission that it already is not. [14-roadmap.md](14-roadmap.md),
   [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §14 and
   [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §12.2 all already used 180 days
   for the banner; this document was the outlier. Both triggers are tested in CI with a fake clock,
   because an untested dormancy trigger is a promise rather than a mechanism, and this is the direct
   answer to Ecosystem Graphs — **a stale banner is enormously better than silent staleness**,
   because silent staleness propagates errors into other people's published research.
6. **Per-domain stewards, not one central curator.** `CODEOWNERS` is path-scoped so a robotics
   steward owns `data/benchmarks/robotics-embodiment/`. HELM entered maintenance mode on 2026-06-01 and MedHELM
   survived by spinning out to an independent steward (Apache 2.0, technical stewardship by Pacific
   AI). The vertical that found a steward lived; the parent did not. Design for that outcome from
   the start rather than discovering it.
7. **A named handover intent, and this document owns the list.** If the maintainers stop, the
   stated intent is to transfer the repository and domain to an institutional steward. The list, in
   priority order and maintained here rather than restated in
   [00-vision-and-scope.md](00-vision-and-scope.md) or
   [01-landscape-and-positioning.md](01-landscape-and-positioning.md): **per-domain stewards first**
   on the MedHELM model, because the vertical that found a steward lived and the parent did not;
   then **MLCommons** (which already owns Dynabench and Croissant, and would be the natural home for
   a `croissant-benchmark` extension); then **the EvalEval coalition** (HuggingFace, University of
   Edinburgh and EleutherAI jointly), whose result registry is the complement to this benchmark
   registry; then **a university group**. Three documents previously carried three slightly
   different lists, which is how a succession plan becomes unactionable. Failing all of that, to leave the final release DOI'd, the banner visible and
   the licence permissive. There is no scenario in which the data goes private, and no scenario in
   which it goes quiet without saying so.

Papers with Code died because a single corporate owner deprioritised it, and 9,327 benchmarks went
with it. Points 1--3 are what make that failure mode survivable here. Points 4--6 are what make it
less likely.

---

## 11. Legal posture

The charter constraint -- **metadata and links only, never the data** -- is not merely an ethical
position about contamination. It is the strongest legal shield available, and nearly every licensing
ambiguity in the ingestion catalogue dissolves the moment the answer to "what did you copy?" is
"facts and a URL". CI job 7 is what makes that true mechanically rather than aspirationally.

**Attribution obligations inherited from ingested sources.** Several Tier-1 sources are CC-BY, which
is cheap to comply with and expensive to be caught violating. `docs/attribution.md` is **generated**
from `data/sources/` by `bench report attribution` so it can never drift from what was actually
ingested, and it is rendered as a public `/attributions` page.

**Licences, their evidence grades and their as-of dates are owned by
[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8, read on 2026-09-17.** The table below
is a convenience summary of the **resolved** rows only, and it is not a complete picture of the
source catalogue: `06` §8 grades every licence `[M]` (observed in a live response), `[D]` (the
vendor's own documentation), `[E]` (derived) or `[U]` (unresolved), and several Tier-1 sources —
HELM's bucket data, SWE-bench, Grand Challenge and Codabench among them — are still `[U]` with an
outreach action scheduled against each. Do not treat this list as exhaustive and **do not update it
here** — update `06`, which carries the evidence, and let this table follow.

| Source | Licence | Our obligation |
| --- | --- | --- |
| Epoch AI benchmark data | CC-BY-4.0 | Credit "Epoch AI, *Capabilities & Benchmarking*, epoch.ai" on every derived view and in the attributions page. Record our own retrieval date and file hashes -- upstream publishes no DOI or dated snapshot |
| LMArena leaderboard dataset | CC-BY-4.0 | Attribution |
| OpenRouter rankings | CC-BY-4.0 | Attribution |
| Every Eval Ever | Data CC BY 4.0, code MIT | Attribution; crosswalk their `eval.schema.json` field names in `taxonomy/crosswalks/eee.yaml` ([04-data-model.md](04-data-model.md) §8 owns our field names) |
| arXiv metadata | CC0 | None required. Do it anyway. Must not imply arXiv endorsement |
| MTEB results | CC0 | Courtesy |
| inspect_evals | MIT | Attribution in the crosswalk file |
| HuggingFace Hub | Per-artifact | Carry each dataset's own `license:` tag through into our record |

**Quarantined and prohibited inbound material.** Same rule: `06` §8 owns the evidence and the date,
and every classification below is a reading of a third party's published terms on 2026-09-17, not a
permanent property of that party. A licence classification that changes upstream while living only
in a plan document is a CI rule that will silently misfire, which is why the class and its
`licence_checked_on` date are fields on `Source` ([04-data-model.md](04-data-model.md) §9) rather
than constants in the loader.

- **Papers with Code archive (CC-BY-SA-4.0)** is the single largest legal risk in the whole
  ingestion strategy, because ShareAlike is viral and a strict reading would force our entire
  derivative to CC-BY-SA. Settled posture: it lives in `vendor/pwc-archive/` with its own `LICENSE`,
  it is used as a **reconciliation key only** (name and ID matching), descriptions are re-written
  from the primary paper, and CI job 8 blocks any move from `vendor/` into `data/` without a
  `Re-derived-from:` trailer. Decide this before first ingest, not after.
- **Benchmark Radar content (CC BY-NC-SA 4.0)** -- do not ingest. The NC clause is incompatible with
  our CC-BY core. A `radar_id` cross-reference field for interop is fine; their content is not.
- **Artificial Analysis** -- attribution permitted across all tiers, **redistribution contractually
  barred**. Link and cite, never mirror.
- **Evaluation Cards (CC-BY-SA 4.0)** -- reimplement the ideas, never copy the data.
- **MLCommons Croissant spec (CC BY-ND 4.0)** -- No Derivatives. We may publish a separately
  namespaced `croissant-benchmark` extension; we may **never** republish a modified spec.
- **`robots.txt` and anti-bot measures are honoured by the fetcher, not by developer discipline.**
  Epoch disallows `/inspect-viewer/` and its FrontierMath problem pages with the stated reason "to
  avoid contaminating training datasets" -- which is our own ethic, so complying is free and
  violating would be a reputational own-goal. DrivenData disallows its leaderboard endpoints.
  OpenReview's API2 now serves an active bot challenge; **we do not build a bypass**, because
  circumventing an anti-bot measure is a materially different legal posture from ignoring a
  `robots.txt` line.

**Nominative use.** Benchmark names, organisation names and logos are used nominatively to identify
the things being catalogued. No endorsement is implied or claimed, and the site says so. Logos are
linked from the source's own URL where possible rather than copied.

**Per-entry licence fields are displayed**, because "can I actually use this" is a question the index
should answer and almost no catalogue does. `license` and `license_notes` appear on every benchmark
page and are a filterable facet, and the suite builder hard-filters on licence compatibility rather
than leaving it to a model's judgement.

**Propagating wrong numbers is not a legal risk but an existential one**, and the mitigation is
structural: every numeric claim carries `source_url`, `fetched_at` and `archive_url`, and any figure
sourced from a single aggregator renders with a visible "single source, unverified" marker. An
aggregator's number is never presented as the benchmark's own.

---

## 12. Licensing our own outputs

| Path | Licence | SPDX |
| --- | --- | --- |
| `data/`, `taxonomy/`, `docs/`, `evals/golden/` | **CC-BY-4.0** | `CC-BY-4.0` |
| `tools/`, `ingest/`, `schema/`, `site/`, workflows | **MIT** | `MIT` |
| `vendor/pwc-archive/` | CC-BY-SA-4.0 (inherited) | `CC-BY-SA-4.0` |
| `metrics/` | CC0 | `CC0-1.0` |
| `croissant-benchmark` extension (separate repo) | CC-BY-4.0 | `CC-BY-4.0` |

A `REUSE.toml` maps paths to SPDX identifiers and CI checks it, so the licensing is machine-readable
rather than a paragraph in a README that nobody can act on.

**Why CC-BY for the data, and specifically why not ShareAlike.** CC-BY makes the index citable and
reusable, which is what turns it into infrastructure rather than a website. ShareAlike would block
exactly the adoption that matters: a company embedding our facet vocabulary in an internal eval
tool, a regulator referencing the registry in guidance, a commercial eval vendor building a product
on top. The landscape is unusually clear on this point -- Benchmark Radar is CC BY-NC-SA, the Papers
with Code archive is CC BY-SA, Evaluation Cards is CC BY-SA, BenchmarkList and llm-stats are closed,
and Artificial Analysis bars redistribution. **Plain CC-BY is nearly unoccupied ground, it is the
only licence under which companies, regulators and commercial vendors can actually build, it is
cheap for us to claim and hard for incumbents to retrofit** -- and it is simultaneously the
survival mechanism from §10. The same decision does two jobs.

The risk, stated honestly: CC-BY permits a well-funded competitor to ingest the entire index and
ship a closed product over it, with nothing owed but attribution. That is a real cost and we accept
it. The moat is not the data snapshot; it is the curation cadence, the provenance chain, the
comparability machinery and the community -- none of which fork cleanly. A competitor who takes the
data still has to keep it true.

**Why MIT rather than Apache-2.0 for the code.** Apache-2.0's explicit patent grant is the better
instrument in the abstract, and if this project ever produced a patentable mechanism the calculus
would change. It does not: this is a schema, a validator, a static-site build and some scrapers. MIT
is what every adjacent project in this ecosystem uses -- `inspect_evals`, Every Eval Ever's code,
`lm-evaluation-harness`, HELM, Dynabench -- and matching the neighbourhood removes a friction we get
nothing for. Recorded as an ADR so it can be revisited rather than re-argued.

---

## Open items

Carried to [15-open-questions.md](15-open-questions.md):

- **Settled, and moved off this list.** The `condition_completeness` threshold below which
  machine-ingested claims are hidden in comparison views is the named constant **`comparison_floor`**,
  declared in `taxonomy/thresholds.yaml` and owned by
  [12-analytics-and-trends.md](12-analytics-and-trends.md), currently 0.4. Every surface references
  it by name, never by value, so calibrating it is one edit rather than five. The 0.35 this document
  and [10-visualization.md](10-visualization.md) previously carried was a literal in two places and a
  different literal in two more; that is the state a named constant exists to prevent.
- Whether the **data-only mirror** should be a filtered push or a genuine split repository with the
  monorepo as a submodule. Recommendation: filtered push, for simplicity, until someone asks for the
  other.
- Whether `verification_status: maintainer-confirmed` requires **identity verification** of the
  claimant, and by what mechanism given no auth and no accounts in v1. Recommendation: require the
  confirmation to come from an account linked to the benchmark's own repository or a message from a
  domain-matching address, recorded as a source.
- Whether to accept contributions of **entries for benchmarks the contributor maintains** without a
  conflict-of-interest marker. Recommendation: accept, always mark, and display it -- the
  `governance.independence_flags` field already exists for this.
