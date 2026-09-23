# 07 -- Ingestion Infrastructure

[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) decides *what* we pull and under what
licence. This document decides *how* the pulling runs: the code contract every adapter implements,
where the jobs execute, where "what I already saw" is stored, how output reaches the repository,
how ingested entities are matched to existing ones, and how we find out that a scraper quietly
stopped working three weeks ago.

The framing that matters most is the last one. Every cross-domain benchmark catalogue built so far
died within 12--24 months ([01-landscape-and-positioning.md](01-landscape-and-positioning.md)
carries the mortality analysis), and the cause was almost never architecture. Stanford's Ecosystem
Graphs was the exact architecture proposed here -- structured records in git plus a static site --
from a well-resourced lab, and its last push was 2025-01-24. It did not fall over technically. It
stopped being fed. So the purpose of ingestion infrastructure in this project is not throughput. It
is **to move the curation treadmill off the human's desk for the parts a machine can do honestly,
and to make it loudly visible when the machine stops**.

## What this document owns, and what it does not

The corpus-wide failure that produced the last revision pass was every document restating the same
fact in its own words until the copies drifted. Ingestion sits at the junction of five other
documents, so the boundary is drawn here first and referred to rather than repeated.

| Fact | Owner | What 07 does with it |
| --- | --- | --- |
| The `ingestion` block, `IngestBatch`, the licence firewall, the verification ladder, the identity-resolution *procedure* | [04-data-model.md](04-data-model.md) §9--10 | Implements them. Never redefines a field name |
| Repository layout, file-naming and identity conventions, CI check list, review matrix, contribution paths, corrections and disputes, freshness display | [05-repository-and-workflow.md](05-repository-and-workflow.md) | Implements them. The cron table lives there too |
| Per-source endpoints, rate limits, licences, legal posture, tiered build order | [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) | Links. §10 here budgets *our* usage against those limits, it does not restate them |
| Build artifacts, sizes and performance budgets | [08-infrastructure-and-build.md](08-infrastructure-and-build.md) | §11.4 states what the ingested tree costs those artifacts |
| Effort totals, phase gates, claim targets | [14-roadmap.md](14-roadmap.md) | §11.3 splits the two roadmap rows that fund ingestion. It adds no new total |
| The adapter contract, the runner, state, identity-resolution *scoring*, PR generation, quality gates, observability | **This document** | -- |

Five rules govern everything below. They are stated once and then assumed.

1. **Ingestion drafts; humans merge.** No adapter writes to `data/` on `main`. There are exactly
   three bounded exceptions, all outside the citable data tree, all enumerated in §6.4. Nothing
   else, ever.
2. **An adapter that cannot resolve something says so.** It never guesses, never defaults, never
   fills a field to make a record look complete. `null` means *unknown*, not *default* -- a
   schema-level rule from [04-data-model.md](04-data-model.md), and the adapters are where it is
   either honoured or silently violated. An adapter may never create an entity; it resolves to an
   existing id or it writes an unresolved record.
3. **Ingested data is segregated and badged.** Machine-ingested claims live under
   `data/claims/_ingested/<source>/<benchmark-id>/` and carry `ingestion.review_state:
   machine-ingested`. They are never mixed into hand-curated claims. This is the settled Epoch
   policy and it generalises to every bulk source.
4. **Adapters write source fields, never derived ones.** `comparability_key`,
   `condition_completeness` and headroom are computed by the build from the stored fields
   ([04-data-model.md](04-data-model.md) §5). An adapter computes completeness only to *report* it
   -- in the PR body and in the gates -- and never writes it into YAML. A derived value in a source
   file is a value that will silently disagree with the build.
5. **Silent failure is the enemy, not loud failure.** A hard crash with an open issue is a good
   outcome. A 200 OK that returns an empty list for a month is the outcome that kills the project,
   because staleness propagates into the literature -- Ecosystem Graphs was still being cited as a
   data source twenty months after it froze.

---

## 1. The adapter contract

One interface, implemented once per source. The point of a contract rather than eleven bespoke
scripts is not elegance; it is that the runner, the state layer, the politeness layer, the quality
gates, the run log and the PR generator are written once and every adapter inherits them. A
two-person team cannot afford eleven scrapers each with its own idea of what a retry is.

The contract has five parts: `discover()` enumerates what exists, `fetch()` retrieves it with
conditional caching, `normalise()` turns a payload into draft entities, `checkpoint()` lets a long
run survive being killed, and everything the adapter could not resolve comes back as structured
`Unresolved` records rather than log lines. That last part is the one most scraping code omits and
it is the one that decides whether a human can actually action the output.

A warning about sequencing, which §11.3 makes concrete: **this contract should be extracted when
the third adapter is written, not before.** A contract generalised from one instance is a guess.
What follows is the target shape, and adapter #1 is a plain script that hits it by hand.

### 1.1 The base classes

```python
# ingest/adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

ChangeClass = Literal[
    "new", "field-change", "result-change", "metrics-only", "gone", "no-change"
]
EntityType = Literal[
    "benchmark", "benchmark_version", "system", "organization",
    "metric", "leaderboard", "source", "claim", "conditions",
]


@dataclass(frozen=True)
class Candidate:
    """One thing the source claims exists.

    Cheap for API sources: no payload fetched yet. For bundle-shaped sources the bundle has
    already been fetched once and the candidate names a logical record inside it -- see
    BulkArchiveAdapter below, which is the honest name for roughly half our sources.
    """
    source_key: str                       # the SOURCE's own stable identifier, verbatim, UNIQUE
    kind: EntityType
    url: str | None                       # canonical upstream URL (provenance + archiving)
    hint: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Payload:
    candidate: Candidate
    body: bytes
    content_type: str
    http_status: int
    fetched_at: datetime
    etag: str | None
    last_modified: str | None
    sha256_normalised: str                # hash of the NORMALISED body -- see §1.5
    from_cache: bool

    # Parsed views. Populated by the adapter's own parse step so that normalise() never
    # re-parses and never sees raw bytes. For a CSV record: headers + rows. For JSON: doc.
    headers: Sequence[str] | None = None
    rows: Sequence[dict[str, str]] | None = None
    doc: Any | None = None


@dataclass
class Unresolved:
    """Something the adapter saw, partly understood, and refuses to guess about."""
    source_key: str
    field: str
    observed: str
    reason: Literal["no-match", "ambiguous-match", "unparseable", "out-of-band", "policy"]
    suggestions: list[tuple[str, float]] = field(default_factory=list)   # (entity_id, score)
    human_task: str = ""                  # phrased as an instruction, not a complaint

    @property
    def fingerprint(self) -> str:
        """Stable identity across runs. Drives the lifecycle ledger in §5.4."""
        return sha256_hex(f"{self.source_key}|{self.field}|{self.observed}")[:16]


@dataclass
class Draft:
    """A proposed entity or entity patch, already shaped like our YAML."""
    entity_type: EntityType
    entity_id: str | None                 # None = the runner mints it (§1.4); adapters never do
    path: Path
    payload: dict[str, Any]
    change_class: ChangeClass
    ingestion: dict[str, Any]             # the `ingestion` block owned by 04-data-model.md §9
    confidence: float                     # 0..1; written to ingestion.extraction_confidence
    labels: list[str] = field(default_factory=list)   # PR labels this draft demands


@dataclass
class RunReport:
    adapter: str
    adapter_version: str
    started_at: datetime
    finished_at: datetime
    status: Literal["ok", "no-change", "partial", "soft-fail", "hard-fail", "capped"]
    http_codes: dict[int, int]
    candidates_seen: int
    payloads_fetched: int
    payloads_from_cache: int
    drafts: dict[ChangeClass, int]
    unresolved_new: int
    unresolved_carried: int
    resolver_snapshot_sha256: str
    errors: list[str]
    notes: list[str]


class Adapter(ABC):
    name: str                             # "epoch", "hf-hub", "arxiv-oai", ...
    version: str                          # bump on ANY change to normalise(); stamped per record
    licence: str                          # SPDX id or URL. CI rejects an adapter with none.
    licence_class: str                    # 04 §9 firewall: permissive-attribution | share-alike |
                                          # non-commercial | no-redistribution | unlicensed
    attribution: str                      # the exact credit line this source requires
    politeness: "HostPolicy"              # token bucket + robots cache, enforced by the fetcher
    expected_yield: tuple[int, int]       # seed band for a new adapter; adaptive after 8 runs (§9)
    volatile_fields: Sequence[str] = ()   # stripped before hashing -- see §1.5
    raw_retainable: bool = True           # False when the licence bars us keeping the body (§4.4)
    caps: dict[EntityType, int] = {}      # per-entity-type draft caps; defaults in §8

    @abstractmethod
    def discover(self, state: "SourceState") -> Iterator[Candidate]:
        """Enumerate what the source says exists, using the persisted cursor."""

    @abstractmethod
    def fetch(self, candidate: Candidate, state: "SourceState") -> Payload | None:
        """Return None on a 304 / unchanged hash. Must go through self.politeness."""

    @abstractmethod
    def normalise(
        self, payload: Payload, resolver: "Resolver"
    ) -> tuple[list[Draft], list[Unresolved]]:
        """Pure function of (payload, resolver snapshot). No network, no clock, no randomness."""

    def checkpoint(self, state: "SourceState", cursor: dict[str, Any]) -> None:
        """Persist a mid-run cursor. Called by the runner every N candidates and at --max-runtime.
        Default writes ingest/state/<name>.json in place; overriding is rarely needed."""

    def finalise(self, state: "SourceState", report: RunReport) -> None:
        """Persist cursors and write ingest/runs/<name>/<date>.json."""
```

Four design choices in there deserve their reason.

**`normalise()` is a pure function.** No network calls, no `datetime.now()`, no randomness. The
timestamp arrives on the `Payload`; the entity lookup arrives on the `Resolver`. This is what makes
ingestion testable: a saved payload fixture plus a frozen resolver snapshot must produce a
byte-identical draft set forever, and CI can assert exactly that. The failure mode it prevents is
the one where an adapter's output silently changes because an upstream entity got renamed, and
nobody can reproduce last month's PR to find out why.

**`entity_id` may be `None`.** Adapters propose entities but never name them. Benchmark IDs are
permanent and never reused ([05-repository-and-workflow.md](05-repository-and-workflow.md) file
conventions), and the Epoch data alone contains four name traps that would defeat any slugifier:
`MATH level 5` is a subset of MATH, `GPQA diamond` is a subset of GPQA,
`FrontierMath-Tier-4-2025-07-01-Private` encodes benchmark + tier + snapshot date + access mode in
one string, and `ARC AI2` and `ARC-AGI` are unrelated benchmarks that share a prefix. A wrong
permanent ID is a mistake you live with for years. **Claim and conditions ids are different**: they
are content-derived and therefore mintable by machine, which §1.4 covers.

**`confidence` is the adapter's own score, not a quality score.** It answers "how sure is this
parser that it read the source correctly", it lands in `ingestion.extraction_confidence`, and it is
distinct from `condition_completeness` (how much of the material condition set is populated) and
from `verification` (how good the evidence is). Conflating the three is how catalogues end up
presenting a confidently-parsed rumour as a verified fact. §5.3 gives the formula, because an
unexplained score is a number-shaped guess.

**`checkpoint()` exists because `finalise()` runs at the end and jobs get killed.** A run stopped
at a wall clock without a checkpoint hook loses everything it did, and the next run restarts from
the same cursor and dies at the same place. The runner calls `checkpoint()` every 200 candidates
and once at 80% of `--max-runtime`, then exits with `status: partial`. A `partial` run is a normal
outcome, not an error: it commits its state file, opens no PR, and the next scheduled run resumes.

### 1.2 Bundle-shaped sources

Roughly half the sources in [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) are not
"N addressable URLs". They are *one archive fetch plus N logical records inside it*: the Epoch ZIP
(87 entries), the LMArena parquet set, the MTEB results clone, the `lm-evaluation-harness` task
tree, the HELM per-release object set. Forcing those through a per-candidate `fetch()` produces an
adapter that lies about its own shape -- which is exactly what the previous draft of this document
did, and the critic was right to catch it.

```python
class BulkArchiveAdapter(Adapter):
    """One bundle fetch, then N logical records. fetch() is implemented here, once."""

    @abstractmethod
    def fetch_bundle(self, state: "SourceState") -> "Bundle | None":
        """One conditional GET/clone. Return None on 304 or unchanged content hash."""

    @abstractmethod
    def enumerate(self, bundle: "Bundle") -> Iterator[Candidate]:
        """Logical records inside the bundle. Each source_key must be UNIQUE."""

    def discover(self, state):
        self._bundle = self.fetch_bundle(state)
        if self._bundle is None:
            return iter(())
        return self.enumerate(self._bundle)

    def fetch(self, candidate, state) -> Payload | None:
        """No network. Slices the already-fetched bundle and parses it into a Payload view."""
        return self._bundle.payload_for(candidate)
```

`Bundle` carries the archive bytes, its `sha256` (the citable snapshot handle), and a parse
registry mapping file extensions to parsers. The rule that makes this safe: **`fetch_bundle()` is
the only method in a bundle adapter that touches the network**, so `--fixture` swaps one call and
the whole adapter runs offline, which is how the Epoch adapter is developed against `epochdl/`.

### 1.3 The `Resolver`, and how a snapshot is frozen

The reproducibility guarantee in `normalise()` rests entirely on the resolver, so it needs a
definition rather than a mention.

```python
class Resolver(Protocol):
    """A frozen, read-only view of the entity graph at one commit. Built once per run."""

    snapshot_sha256: str
    built_from_commit: str

    def system(self, raw: str) -> tuple[str | None, float]:
        """Apply 04 §10 steps 1-4. Returns (entity_id, score) or (None, score)."""

    def benchmark(self, raw: str) -> tuple[str | None, float]: ...
    def organization(self, raw: str) -> tuple[str | None, float]: ...

    def candidates(self, kind: EntityType, raw: str, top: int = 3) -> list[tuple[str, float]]:
        """Step 5 fuzzy proposals. NEVER auto-accepted (04 §10)."""

    def claims(self, **key: Any) -> list["ClaimRef"]:
        """Existing claims matching a partial identity key. Used for conflict detection."""

    def lineage_index(self) -> dict[str, "ClaimRef"]:
        """lineage_key -> existing claim. The differ's join table (§1.4)."""
```

It is built at run start by walking the data tree at `HEAD` and serialising four things:
`data/aliases/{systems,benchmarks,organizations}.yaml`, every entity's `id` + `name` + `aliases[]`
+ `external_ids`, the claim lineage index, and the taxonomy enums. At target scale that is a few
hundred kilobytes gzipped, written to `ingest/state/resolver-snapshot.json.gz` and **not committed**
-- it is regenerable from the commit, and committing it would produce a large diff on every run for
no informational gain. What *is* recorded is its `sha256`, in the `RunReport` and once per batch in
the `IngestBatch` record.

That last point is a proposed one-field addition to `IngestBatch`
(`resolver_snapshot_sha256`), which [04-data-model.md](04-data-model.md) §9 owns. It is batch-level
rather than record-level precisely so it costs one line per run rather than 6,598.

Given the snapshot hash and the raw payload, the CI test the purity claim exists to enable can
actually be written:

```
bench ingest replay epoch 2026-09-17 --resolver-snapshot <sha256>
    assert output == the drafts committed by that run's PR, byte for byte
```

### 1.4 Idempotency: the claim id and the lineage key

This is the hole that would have destroyed the second Epoch run. Without a stable key, a single
changed row in the ZIP re-emits all 6,598 drafts as `new`, the cap fires, and nothing recognises
6,597 of them as already present.

[05-repository-and-workflow.md](05-repository-and-workflow.md) owns the answer and it is already
the right one: **`claim-<12 hex>`, content-derived from (benchmark@version, system@version, metric,
subset, value, source, date_reported)**, written as
`data/claims/_ingested/<source>/<benchmark-id>/<claim-id>.yaml`. Conditions ids are derived the
same way from the canonical JSON of the material condition fields. Re-running an adapter over
unchanged input therefore produces the same filenames with the same content, and a no-op ingest is
a zero-line diff.

Two consequences the ingestion side has to handle explicitly, because they are not obvious from the
convention alone.

**`value` is in the key, so a corrected number is a different file.** That is correct behaviour --
a content-addressed name must not lie about its content -- but it means the differ cannot see
`0.787 -> 0.791` by filename. The runner therefore also computes a **lineage key**, which is the
same tuple *minus* `value`:

```python
lineage_key = blake2b(
    canonical_json({
        "benchmark": "swe-bench@verified",
        "system":    "glm-5-2@2026-06-16",
        "metric":    "resolve-rate",
        "subset":    None,
        "source":    "src-epoch-benchmarks-2026-09",
        "date_reported": "2026-06-25",
    }).encode(),
    digest_size=8,
).hexdigest()
```

The lineage key is **never stored**. Every input is already a field on the claim, so the resolver
rebuilds the whole index from the tree at run start. The differ then joins in two passes: exact
filename match (idempotent no-op), then lineage-key match with a different `value`
(`change_class: result-change`, old file superseded per §7.2). A lineage key with no match at all
is genuinely `new`; an existing lineage key with no incoming match for two consecutive runs is
`gone` (§7.3).

**`ingestion.source_record_id` must not be a row number.** [04-data-model.md](04-data-model.md) §9
gives the example `"swe_bench_verified.csv#row=17"`. Row order in a regenerated upstream export is
not stable, so that identifier changes when nothing else did. The ingest-side form is the source's
own discriminators: `"swe_bench_verified.csv#model_version=glm-5.2_max&score_column=mean_score"`.
This is a refinement to a field 04 owns and should be reflected there.

**The CI test that proves it works**, and which must exist before the first bulk run:

```
tests/ingest/test_epoch_idempotent.py
  run 1 against the frozen epochdl fixture -> 6,598 drafts, all `new`
  run 2 against the same fixture, same resolver snapshot -> 0 drafts, status `no-change`
  run 3 against a fixture with one edited score -> exactly 1 draft, class `result-change`
  run 4 against a fixture with one deleted row -> 0 drafts on this run, 1 `gone` on the next
```

### 1.5 Determinism: hashing and YAML emission

Two unspecified constants in the previous draft were both places where the whole point is
mechanical enforcement, so both get a number.

**`sha256_normalised` is the hash of the payload after the adapter's declared `volatile_fields` are
removed and the remainder is canonicalised** -- JSON with sorted keys and no whitespace, or for CSV
the header row plus rows sorted by the source's own key. Volatility is per-adapter and declared on
the class, because it is a property of the source, not of the format:

| Adapter | `volatile_fields` | Why |
| --- | --- | --- |
| `epoch` | -- | The ZIP is byte-stable between publications |
| `hf-hub` | `downloads`, `likes`, `downloadsAllTime`, `_id` | Counters move hourly; they belong in `metrics/`, not in a change signal |
| `swe-bench` | `logo`, `site` | CDN paths rotate daily on an unchanged leaderboard |
| `github` | `pushed_at` on list endpoints, `stargazers_count`, `forks_count` | Same reasoning |
| `grand-challenge` | `logo` | Same |

**YAML emission is specified once and shared by `bench fmt` and every adapter**, because two
emitters produce two formats and the diff noise hides real changes:

```python
# tools/emit.py -- the only YAML writer in the project
yaml = ruamel.yaml.YAML()
yaml.default_flow_style = False
yaml.allow_unicode = True
yaml.width = 100
yaml.preserve_quotes = False
# Key order is the Pydantic model's field order, not alphabetical and not insertion order.
# Floats are emitted as repr(round(x, 6)); 0.7870000000000001 must never reach a file.
# Line endings LF. No trailing whitespace. Files end with exactly one newline.
```

CI check 1 (`bench fmt --check`, owned by [05-repository-and-workflow.md](05-repository-and-workflow.md)
§9) already fails on any file the emitter would rewrite. The addition ingestion needs is a
**round-trip assertion**: re-emitting every file under `data/` produces a zero-byte diff. Without
it, a float formatted two ways produces two different `claim-` ids for the same measurement, which
would silently break §1.4.

### 1.6 The CLI surface

```
bench ingest <adapter> [--dry-run] [--since DATE] [--limit N] [--no-network]
                       [--allow-bulk] [--fixture PATH] [--max-runtime SECONDS] [--max-drafts N]
bench ingest --all --report-only
bench ingest replay <adapter> <run-date> [--resolver-snapshot SHA]
bench ingest recompute <adapter> --from-version X   # re-normalise already-merged records (§7.2)
bench ingest state <adapter> [--reset-cursor]
bench ingest unresolved <adapter> [--status open|resolved|wontfix|blocked-upstream]
```

`bench ingest replay` is the one that pays for itself. When a parser turns out to have been subtly
wrong for a fortnight, the fix is a re-normalise rather than a re-scrape of a rate-limited source.
§4.4 covers where the raw bodies live and which sources are not allowed to have them kept.

**This block is the sole declaration of the `bench ingest` surface.**
[05-repository-and-workflow.md](05-repository-and-workflow.md) §3, which owns the rest of the CLI,
carries a one-line summary and a pointer here rather than a second copy of these flags. Until
2026-09-22 it carried a second copy and the two had diverged: §3 listed `--limit` and
`--no-network`, which this block did not, while this block listed `--allow-bulk`, `--fixture`,
`--max-runtime`, `--max-drafts` and all five subcommands, which §3 did not. Neither list was a
superset, and the task that builds the subcommand asks for flags from both.

The four that need a sentence: `--limit N` caps records *processed* and is the fast path for
developing an adapter against a live source; `--max-drafts N` caps records *written*, which is the
400-draft PR cap in §12 and is a different number for a different reason. `--no-network` forbids
the network and fails if an adapter reaches for it, which is what makes the prohibition testable;
`--fixture PATH` supplies recorded bytes in its place. The two are complementary and CI uses both.

---

## 2. Worked adapter: Epoch AI

The Epoch adapter is built first. It has the best value-per-line ratio in the catalogue: CC-BY-4.0
with no share-alike and no non-commercial clause, static file transport, ETag-conditional, 2,292,857
bytes on the wire (6,361,800 uncompressed, 87 entries), and it yields 81 benchmarks, 1,063 model
rows (550 distinct `model_group` values, 1,048 distinct `model_version` values) and 6,598 result
rows across 80 per-benchmark CSVs. ([00-vision-and-scope.md](00-vision-and-scope.md) §8.1 owns the
6,598 count and the counting rule behind the 80/81 discrepancy; of the 1,048 distinct
`model_version` strings, 927 actually appear in a result row and are the crosswalk population --
§5.2.) It is also already on disk at `epochdl/`, so it can be developed entirely offline against a
fixture.

It is also the adapter that teaches every lesson the others need, because the Epoch corpus is dirty
in instructive ways: **62 distinct header signatures across 80 CSV files**, 21 CSVs that no metadata
row references, one metadata row (`METR`) with no CSV, a `Score` column denominated in dollars in
`vending_bench_2_external.csv` (11,181.87), a `Time horizon` column in minutes in
`metr_time_horizons_external.csv` (1,044.78), an Elo in `webdev_arena`, a 0--10 scale in
`lech_mazur_writing_external.csv`, and a mojibake byte where `±` should be in the headers of
`dtbench_external.csv` and `lmca_external.csv`.

The honest consequence: **there is no generic CSV parser for this source.** The adapter is a thin
engine plus roughly 80 small per-file mapping stanzas. [14-roadmap.md](14-roadmap.md) budgets the
whole thing, stanzas included, and settles that all 21 orphan files are hand-mapped rather than
skipped. Attempting a clever universal parser is how you get silent unit errors in production.

### 2.1 A mapping stanza

```yaml
# ingest/mappings/epoch/swe_bench_verified.yaml
benchmark_ref: swe-bench@verified          # allocated by a human, once, never by the adapter
family: epoch-run                          # vs. external-scrape; decides the verification rule
score_column: "Best score (across scorers)"
scale: 1.0                                 # from benchmark_metadata.csv where present
metric_ref: resolve-rate
uncertainty:
  column: stderr
  type: stderr
artifact:
  log_column: "Logs"                       # -> ResultClaim.artifact_url
  viewer_column: "Log viewer"
date_column: "Started at"
conditions:
  reasoning_effort: { from: model_version_suffix }
  selection_strategy: { const: best-across-scorers, k: null }
# Everything not listed here is null. Null means unknown.
```

### 2.2 The adapter

```python
# ingest/adapters/epoch.py  (abridged: the parts that carry a decision)
EFFORT_SUFFIX = re.compile(r"_(max|xhigh|high|medium|low|minimal|none|unknown)$")
ZIP_URL = "https://epoch.ai/data/benchmark_data.zip"
EPOCH_LOG_HOSTS = frozenset({
    "epoch-benchmarks-production-public.s3.us-east-2.amazonaws.com",
    "epoch-benchmarks-staging-public.s3.us-east-2.amazonaws.com",
})


class EpochAdapter(BulkArchiveAdapter):
    name = "epoch"
    version = "1.4.0"
    licence = "CC-BY-4.0"
    licence_class = "permissive-attribution"
    attribution = ("Epoch AI, 'Capabilities & Benchmarking'. Published online at epoch.ai. "
                   "Retrieved from 'https://epoch.ai/benchmarks' [online resource].")
    expected_yield = (60, 140)             # seed band; 81 observed 2026-09-16. Adaptive after 8 runs
    caps = {"claim": 200, "benchmark": 25, "system": 100, "organization": 25}
    volatile_fields = ()
    raw_retainable = True                  # CC-BY, no SA, no NC -> we may keep the body

    def fetch_bundle(self, state):
        # One conditional GET. Epoch serves NO Last-Modified header on the ZIP, only an ETag
        # (observed: "a95a0b35dd410ad483b45f53e3725590"). If-None-Match is the only mechanism.
        r = self.politeness.get(ZIP_URL, if_none_match=state.etag(ZIP_URL))
        if r.status == 304:
            return None
        return ZipBundle(r.body)           # .sha256 is the citable snapshot handle

    def enumerate(self, bundle):
        meta = bundle.read_csv("benchmark_metadata.csv")          # 81 rows
        for row in meta:
            yield Candidate(source_key=f"bench:{row['benchmark']}", kind="benchmark",
                            url="https://epoch.ai/benchmarks",
                            hint=dict(row) | {"snapshot": bundle.sha256})
        for stem in bundle.per_benchmark_csvs():                  # 80 files; 21 orphaned
            yield Candidate(source_key=f"csv:{stem}", kind="claim", url=None,
                            hint={"snapshot": bundle.sha256})

    def normalise(self, payload, resolver):
        drafts, unresolved = [], []
        mapping = load_mapping(self.name, payload.candidate.source_key)
        if mapping is None:
            unresolved.append(Unresolved(
                source_key=payload.candidate.source_key, field="*",
                observed=f"{len(payload.rows)} rows, headers={payload.headers!r}",
                reason="no-match",
                human_task="Write ingest/mappings/epoch/<file>.yaml: score column, unit, scale, "
                           "metric ref, uncertainty column. Do NOT assume scale=1.0.",
            ))
            return drafts, unresolved

        for row in payload.rows:
            sysref, score = resolver.system(row["Model version"])
            if sysref is None:
                unresolved.append(Unresolved(
                    source_key=row["Model version"], field="claim.system",
                    observed=row["Model version"], reason="no-match",
                    suggestions=resolver.candidates("system", row["Model version"], top=3),
                    human_task="Add an entry to data/aliases/systems.yaml with `extracts` for "
                               "the serving provider and any effort suffix (04 §10).",
                ))
                continue                       # no system ref -> no claim. Never invent one.

            raw = parse_float(row[mapping.score_column])
            value = raw * mapping.scale        # scale in {1.0, 0.01, 0.1}; NEVER defaulted
            effort = m.group(1) if (m := EFFORT_SUFFIX.search(row["Model version"])) else None
            transcript = transcript_evidence(row.get(mapping.artifact.log_column))

            drafts.append(Draft(
                entity_type="claim",
                entity_id=None,                # the runner mints claim ids (§1.4)
                path=Path(f"data/claims/_ingested/epoch/{slug(mapping.benchmark_ref)}/"),
                payload={
                    "benchmark": mapping.benchmark_ref,
                    "system": sysref,
                    "metric": mapping.metric_ref,
                    "claim_type": "absolute",
                    "value": value,
                    "uncertainty": read_uncertainty(row, mapping),
                    "date_reported": parse_date(row.get(mapping.date_column)),
                    "source": mapping.source_ref,
                    "artifact_url": transcript.url,
                    "artifact_archived": None,
                    "verification": verification_rule(mapping.family, transcript),
                    "eval_conditions": {
                        # `_unknown` maps to null, NOT to a default. This distinction is the
                        # whole point of the schema.
                        "reasoning_effort": None if effort in (None, "unknown") else effort,
                        "shots": normalise_shots(row.get("Shots")),   # "5", "few", "25-shot", 64
                        "selection_strategy": mapping.conditions.selection_strategy,
                        # chain_of_thought, judge_model, temperature, retries_allowed,
                        # human_in_loop, shot_selection: absent from all 6,598 rows -> null
                    },
                    # NOTE: no condition_completeness here. It is derived (rule 4, 04 §5).
                },
                change_class="new",            # the runner re-classifies against the lineage index
                ingestion={
                    "batch": self.batch_id,
                    "source_adapter": self.name,
                    "adapter_version": self.version,
                    "source_record_id": (f"{payload.candidate.source_key}"
                                         f"#model_version={row['Model version']}"
                                         f"&score_column={mapping.score_column}"),
                    "source_url": row.get("Source link") or "https://epoch.ai/benchmarks",
                    "source_licence": self.licence,
                    "licence_class": self.licence_class,
                    "source_attribution": self.attribution,
                    "ingested_at": payload.fetched_at.isoformat(),
                    "review_state": "machine-ingested",
                    "field_provenance": {
                        "value": "source",
                        "uncertainty": "source" if read_uncertainty(row, mapping) else "absent",
                        "eval_conditions.reasoning_effort": "derived" if effort else "absent",
                        "eval_conditions.shots": "source" if row.get("Shots") else "absent",
                    },
                },
                confidence=0.95 if mapping.family == "epoch-run" else 0.85,
                labels=["needs-scrutiny"] if transcript.access == "unreachable" else [],
            ))
        return drafts, unresolved
```

### 2.3 The verification rule, and why it is a structural check

[04-data-model.md](04-data-model.md) §7 owns the verification ladder and settles the Epoch
assignment: Epoch-run file with a public Inspect-AI log -> `independent-reproduction` (828 rows);
Epoch-run with a private or blank log -> `maintainer-verified` (459 + 263 rows); everything external
-> `self-reported` (5,048 rows). Rungs 4 through 7 are never machine-assigned.

The critique argued that no machine should be able to assign rung 3, and that a substring test for
`-public` on an S3 URL is a thin basis for the top grade an adapter can give. **The second half of
that is right and the first half is declined**, for a reason worth stating: the ladder grades *who
produced the number and what evidence exists*, not whether a curator has personally opened the
evidence. Epoch is a third party that re-ran the eval and published the transcript, which is the
literal definition of rung 3. Whether a human has looked is a different axis and the schema already
carries it separately, in `ingestion.review_state`. Collapsing the two would make the ladder mean
"a human checked this", which it does not, and would leave us with no way to say "third-party
reproduction, transcript published, nobody here has opened it" -- which is precisely what 828 of
these rows are.

What does change is the test. A substring is replaced by a structural check, and the result is
recorded rather than asserted:

```python
@dataclass(frozen=True)
class Transcript:
    url: str | None
    access: Literal["public", "private", "absent", "unreachable"]


def transcript_evidence(log_url: str | None) -> Transcript:
    """Structural, not a substring on a URL. Host allowlist + extension + one HEAD."""
    if not log_url:
        return Transcript(None, "absent")
    u = urlsplit(log_url)
    if u.netloc not in EPOCH_LOG_HOSTS or not u.path.endswith(".eval"):
        return Transcript(log_url, "private")
    # HEAD is cached in ingest/state/epoch.json keyed by URL; re-checked every 30 days.
    return Transcript(log_url, "public" if head_ok(log_url) else "unreachable")


def verification_rule(family: str, t: Transcript) -> str:
    """Encoded once in the adapter, not copied into 6,598 records."""
    if family == "epoch-run" and t.access == "public":
        return "independent-reproduction"     # 828 rows, transcript URL stored in artifact_url
    if family == "epoch-run":
        return "maintainer-verified"          # 459 private + 263 blank + any unreachable
    return "self-reported"                    # 5,048 external scrape rows
```

Three consequences are then enforced by gates in §8 rather than by good intentions:

- **A machine may not assign rungs 4--7.** The gate refuses any ingested record above
  `independent-reproduction`, so a future adapter cannot quietly promote itself.
- **`independent-reproduction` requires a reachable `artifact_url`.** No transcript, no rung 3. An
  `unreachable` HEAD downgrades to `maintainer-verified` and labels the PR `needs-scrutiny`, which
  is also our link-rot detector for the 828.
- **Verification rank and review state render together, always.** A rung-3 badge next to a
  `machine-ingested` badge is honest and legible; either alone is not.

Curator sampling closes the loop cheaply: **ten transcripts per bulk batch, opened by a human,
recorded in `ingestion.review_state: spot-checked` on those ten.** If any of the ten does not
contain what the rule assumes, the whole batch drops to `self-reported` pending investigation. Ten
minutes of work against 828 records is the right ratio, and [14-roadmap.md](14-roadmap.md)'s exit
criterion that all 6,598 rows are accounted for by the four rules with a published `unmatched` count
is what makes the sampling checkable from outside.

### 2.4 Three things this adapter deliberately does not do

**It does not deduplicate.** 843 rows share a `Model version` with another row in the same file.
Some are genuinely conflicting claims from different papers, some are the same run listed twice
under two spellings of one source, some are different reasoning efforts collapsed onto one key.
Automated dedup would silently destroy the first category. See §5.5.

**It does not compute `condition_completeness` into the record.** It computes it for the PR body
and the gates, and the build computes it for display (rule 4). The material condition fields are
almost entirely absent: `shots` appears in 14 of 80 files and is filled on 1,283 of 6,598 rows
(19.4%) with mixed types (`5`, `few`, `0-shot`, `25-shot`, `64`); `tools_allowed` under 1%;
`chain_of_thought`, `judge_model`, `retries_allowed`, `human_in_loop`, `selection_strategy` and
`temperature` are at **0% across all 6,598 rows** (only the first five of those are material;
`temperature` is listed because it is absent, not because its absence costs completeness --
[04-data-model.md](04-data-model.md) §8 owns which fields are material). The expected mean is around **0.10**, and the
build publishes that number rather than hiding it. That number is the argument for the project, not
an embarrassment.

**It does not create benchmark facets.** All 81 Epoch benchmarks are LLM-centric. Mapped onto the
nineteen domain families ([02-taxonomy.md](02-taxonomy.md) §3 owns the enumeration) they touch
thirteen, and **six families have zero Epoch coverage**: audio-speech, robotics-embodiment,
chemistry-materials, biology-genetics, medicine-health and earth-climate. (GeoBench is a
photo-geolocation benchmark with an earth-climate secondary reading; counting it as coverage of
earth-climate would be generous. *(unverified -- the recon classified Epoch's 81 entries from
column names alone and flagged ten as unidentifiable; confirm before quoting the family split.)*)
Benchmark drafts are therefore stubs with `id`, `name`, `aliases`, `release_date`, `homepage`,
`chance_baseline`, `score_ceiling` and `superseded_by`, every facet `null`, withheld from the
published build until a human assigns domain facets. An unfaceted benchmark is invisible to the
coverage matrix anyway ([12-analytics-and-trends.md](12-analytics-and-trends.md)).

---

## 3. Where it runs

**GitHub Actions cron, in the data repository itself.** This is not close, and the alternatives
lose for reasons worth recording so nobody relitigates them at month nine.

| Option | Verdict | Why |
| --- | --- | --- |
| **GitHub Actions cron** | **Chosen** | The scraper lives beside the YAML it writes. Runner already has `git`, a token and PR rights. No deploy step, no secret syncing, no separate state store. Free minutes on public repos |
| Cloudflare Workers cron | Disqualified | Free plan gives **10 ms CPU per cron trigger**, 5 triggers per account, 50 subrequests per invocation; paid gives 30 s for sub-hourly crons `[recon 2026-09-17, vendor docs]`. You cannot parse HELM's 3.93 MB `runs.json` in 10 ms. Workers remain right for the AI layer ([11-ai-features.md](11-ai-features.md)); they are wrong for ingestion |
| Small VPS | Disqualified | A machine to patch, monitor and pay for, in a project whose premise is near-zero ops and whose team is 1--2 people part-time. The first unattended `apt upgrade` failure costs more than the whole scraper saved |
| Run locally | Disqualified as the primary path | Works exactly until the laptop is shut, and the resulting silence is invisible. Keep it as the *development and rescue* path -- every adapter must run identically via `bench ingest <name> --fixture` |

### 3.1 Provenance tags on every platform number

Every number in §3, §4 and §10 is a claim about a third party's service and is expected to rot. The
previous draft marked three of them and left twenty unmarked, which made the unmarked ones read as
verified -- the exact unsourced confidence this project exists to oppose. The convention, applied
from here on:

| Tag | Meaning |
| --- | --- |
| `[recon 2026-09-17, measured]` | Observed in a live response header or body during the reconnaissance |
| `[recon 2026-09-17, vendor docs]` | Read off the vendor's own documentation page on that date |
| `(unverified -- confirm before relying on this)` | Believed true, not checked by us, no source in hand |
| `**Open, to be settled at <event>**` | **Not a claim about the world at all** -- a decision this project has not yet made. There is no source to have in hand and nobody to confirm with. Never use the unverified marker for one of these: doing so devalues every real provenance marker in the corpus, because a reader who checks one and finds a to-do stops trusting the rest |

### 3.2 Practical limits, and what to do when a job hits one

- **Job timeout on GitHub-hosted runners** *(unverified -- confirm before relying on this; it is
  documented as 6 hours per job and 35 days per workflow, but the recon did not re-check it)*. No
  adapter should come near it. If one does, the fix is not a longer timeout: it is a narrower
  `--since` window plus the `checkpoint()` hook from §1.1, so the next scheduled run resumes rather
  than restarts. arXiv OAI-PMH is the realistic candidate -- one day of `set=cs` is 3.1 MB and
  1,157 records `[recon 2026-09-17, measured]`, so a cold backfill must be windowed by month, not
  attempted in one pass.
- **Minimum cron interval is 5 minutes** `[recon 2026-09-17, vendor docs]`. Irrelevant: our cadences
  are daily and weekly.
- **Scheduled runs are delayed under load and queued jobs may be dropped** `[recon 2026-09-17,
  vendor docs]` -- GitHub says so in those words. Two consequences: never schedule on the hour
  (`0 * * * *` is the most contended slot on the platform), and make every run idempotent so a
  dropped run is a non-event rather than a gap. §1.4 is what makes idempotence real.
- **Scheduled workflows in a public repo auto-disable after 60 days with no repository activity**
  `[recon 2026-09-17, vendor docs]`. Our scrapers open PRs, which is activity, so this is
  self-sustaining in the normal case -- but the failure mode is circular: if the crons stop, the
  activity stops, which keeps them stopped. The `health-check.yml` canary in §9 exists for this and
  carries a `workflow_dispatch` trigger so a human can restart it in one click.
- **Token limits.** The ambient `GITHUB_TOKEN` is **1,000 requests/hour per repository**
  `[recon 2026-09-17, vendor docs]`. For the GitHub-metadata crawl, mint a fine-grained PAT
  (**5,000/hour** core, **30/minute** search `[recon 2026-09-17, vendor docs]`) and store it as
  `GH_API_TOKEN`. Secondary limits apply regardless: <=100 concurrent requests, <=900 points/minute
  `[recon 2026-09-17, vendor docs]`. `If-None-Match` 304s do not count against the core limit
  `[recon 2026-09-17, vendor docs]`, which is the single most important optimisation in the GitHub
  adapter.
- **Secrets**: `HF_TOKEN` (free tier, doubling the limit from 500 to 1,000 API requests per
  5-minute window `[recon 2026-09-17, vendor docs]`), `GH_API_TOKEN`, `IA_SPN_KEY`/`IA_SPN_SECRET`
  for Wayback, `OPENALEX_KEY`, `S2_API_KEY`, and the AI-triage key. All repository secrets, none in
  adapter code, and every adapter must degrade to a soft-fail with a clear message when its secret
  is absent rather than crashing with a traceback that leaks a header.
- **Concurrency**: sources run *sequentially within a workflow* and workflows run in parallel with
  each other. Never fan out concurrent requests at one host. Use `concurrency: group: ingest-<name>`
  with `cancel-in-progress: false` so a slow run is never clipped by the next schedule.

### 3.3 Fetch cadence is not review cadence

This is the correction that matters most in this section, and the previous draft got it wrong in a
way that reproduced the failure it had just finished diagnosing.

[05-repository-and-workflow.md](05-repository-and-workflow.md) §9 owns the schedule: four ingest
workflows plus archival, freshness and health checks, three of them daily. Combined with "one PR
per source per run" that is roughly **28 pull requests a week**, each requiring one human approval
with no bot bypass. Against that, the review budget: [14-roadmap.md](14-roadmap.md) assumes
**20 h/week combined** across the team, §11.2 allocates **20%** of curator time to reviewing ingest
PRs, and a rendered ingest PR takes about **20 minutes** to review properly. That is 4 h/week, or
**12 PRs/week as an absolute ceiling**, and the ceiling assumes the reviewer does nothing else with
that time. 28 is 2.3x over.

The named failure mode: **a reviewer facing 28 PRs a week approves without reading, which is
auto-merge with extra steps.** `JonathanChavezTamales/llm-leaderboard` died of contribution
friction; this is the same disease pointed inward, and it is worse, because the friction falls on
the two people who cannot leave.

**Decision: decouple fetch cadence from review cadence.** The crons stay exactly as
[05-repository-and-workflow.md](05-repository-and-workflow.md) has them -- daily fetching is cheap
(most runs are 304s), keeps state warm, and detects breakage within a day. What changes is where the
output goes:

- Each adapter commits its daily output to a **long-lived weekly branch**,
  `ingest/<adapter>/<iso-year>-W<week>`, one commit per run, with the run record and state file in
  the same commit.
- On Friday `05 15 * * 5`, a `promote-ingest.yml` job opens **one pull request per adapter per
  week** from that branch, with a body that aggregates the week's runs (§6.3).
- **Two escalations open a PR the same day**: a `result-change` that conflicts with an existing
  claim (§7.1), and a run whose gates produced an `adapter-broken` condition. Both are things a
  human wants to see within 24 hours, and both are rare.
- Target: **<=6 ingest PRs per week**, roughly 2 h of review, leaving the other 2 h of the 20% for
  the unresolved queue (§5.4). Six adapters at one weekly PR each lands exactly on budget.

The risk of weekly batching, stated plainly: a parser bug lives for up to seven days before a human
sees it, and a week's commits on one branch are harder to bisect than a day's. Both are mitigated by
the gates in §8 running on **every daily run**, not just at promotion -- a red gate never reaches
the branch. What the weekly PR batches is *review*, not *validation*.

---

## 4. State between runs

This is the part every scraping plan underestimates, and the underestimation is always the same:
state gets left in a CI cache, which is invisible, uneditable, non-diffable, and evicted -- GitHub
Actions caches are evicted after 7 days idle `[recon 2026-09-17, vendor docs]`. A project whose
entire thesis is auditability cannot have its "what have I already seen" living somewhere nobody can
read.

**Three layers, no database.**

**Layer 1 -- the repository is the canonical state.** The YAML files *are* the record of what we
know. `git log` is the audit trail. Do not build a second source of truth; the moment the state
store and the repo disagree, you have to decide which one is right, and there is no principled
answer.

**Layer 2 -- HTTP cache metadata in a committed per-adapter JSON**, at `ingest/state/<adapter>.json`
([05-repository-and-workflow.md](05-repository-and-workflow.md) §2 owns the path). Small (a few KB),
diffable, and a change to it is itself reviewable in the same PR as the data it produced. This is
the cursor.

```json
{
  "adapter": "epoch",
  "adapter_version": "1.4.0",
  "last_run": "2026-09-17T04:17:09Z",
  "last_success": "2026-09-17T04:17:09Z",
  "last_change": "2026-09-16T04:17:41Z",
  "consecutive_failures": 0,
  "cursor": { "type": "etag-only", "note": "epoch.ai serves no Last-Modified on the ZIP" },
  "checkpoint": null,
  "urls": {
    "https://epoch.ai/data/benchmark_data.zip": {
      "etag": "\"a95a0b35dd410ad483b45f53e3725590\"",
      "last_modified": null,
      "sha256_normalised": "…",
      "bytes": 2292857,
      "last_fetched": "2026-09-17T04:17:11Z",
      "last_changed": "2026-09-16T23:14:02Z"
    }
  },
  "absences": { "claim:mmlu|falcon-7b|em|src-xgen-report": 1 },
  "transcript_head_cache": { "…/4AfhcmYVNrw6gM5u8CQsyy.eval": ["200", "2026-09-17"] },
  "yield_history": [81, 81, 81, 80, 79, 79, 81, 81]
}
```

`absences` is the consecutive-absence counter behind the `gone` class (§7.3). It lives here rather
than on the records because a daily disappearance check that rewrote 6,598 YAML files would produce
a daily 6,598-file diff for zero information. Only when a counter reaches 2 does one record change.

**Layer 3 -- `actions/cache` for bulky regenerable artefacts only**: the shallow clones, the
unpacked Epoch ZIP, the HF request cache, the resolver snapshot. Keyed on content hash. **Never put
anything unrecoverable here.** If a cache eviction can lose information, it belongs in layer 2.

### 4.1 Conditional requests, per source

They genuinely differ, and getting this wrong means either hammering a small academic server or
missing updates entirely. All mechanisms below are `[recon 2026-09-17, measured]` unless tagged
otherwise.

| Source | Mechanism | Note |
| --- | --- | --- |
| Epoch ZIP | `If-None-Match` only | **No `Last-Modified` header.** ETag is the only handle |
| `raw.githubusercontent.com` (LiteLLM) | ETag | Present and verified |
| GitHub API | `If-None-Match` | 304s do not count against the rate limit `[recon 2026-09-17, vendor docs]` -- essential at 5,000/hr |
| HuggingFace API | ETag on list endpoints (`W/"64f-OXh…"`), plus short-circuit on `lastModified` in the payload before fetching detail | See §4.3 on the library's sleep behaviour |
| HELM GCS | Diff the release-prefix object listing (`generation` + `size`) before downloading any 3.93 MB blob | Licence on the data is **unverified** -- see [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3.5 and §12 here |
| arXiv OAI-PMH | Native `from`/`until` incremental; persist the last successful `until` | `from`/`until` are on **modification** datestamp, so v2 resubmissions of old papers appear in a "today" window |
| SWE-bench | `sha256` the extracted `<script id="leaderboard-data">` JSON, **not** the page | The page carries rotating logos and CDN noise that change the page hash daily |
| OpenAlex | Never poll. Free bulk snapshot (CC0) + targeted singleton lookups, which cost 0 credits | Metered since ~2026-02-13; see §10 |
| Wayback | `if_not_archived_within=30d` does server-side dedup; CDX `digest` reveals whether content actually changed | Do **not** use the Availability API -- it returned 429 on a single cold request |

**Universal rule: hash the *normalised* payload (§1.5) and skip the entire downstream pipeline on a
match.** Most runs should be no-ops that write nothing but a run record. An ingestion system whose
normal output is "no change" is working correctly; one that opens a PR every day is either watching
a genuinely live source or hashing the wrong thing -- and the `volatile_fields` table in §1.5 is
the list of ways the second happens.

### 4.2 Backoff

Exponential with full jitter on 429 and 5xx, three attempts, then soft-fail the job. Never retry a
4xx other than 429. **Never retry a 403 at all**: on OpenReview a 403 is an anti-bot
`ChallengeRequiredError` `[recon 2026-09-17, measured]`, and retrying an anti-bot challenge is a
materially different legal posture from ignoring a `robots.txt` line.

### 4.3 One library assumption, and its fallback

The recon reports that `huggingface_hub` >= 1.2.0 parses `RateLimit` / `RateLimit-Policy` headers
(which follow `draft-ietf-httpapi-ratelimit-headers`) and sleeps exactly the stated interval
`[recon 2026-09-17, vendor docs]`. We did not observe that behaviour ourselves
*(unverified -- confirm before relying on this)*. A design that silently depends on an unchecked
library capability fails silently, so: our own `RateLimit` header parser is implemented in the
fetcher regardless, the library's sleep is treated as an optimisation rather than the mechanism, and
a CI test asserts that a synthetic 429 with `RateLimit-Reset: 12` produces a 12-second wait
irrespective of which layer performed it.

### 4.4 The raw store, and the licence rule that governs it

`bench ingest replay` needs the raw body. [05-repository-and-workflow.md](05-repository-and-workflow.md)
§2 settles where it lives: `ingest/raw/` is **gitignored and retained as a CI artifact**, not
committed. That is the right call and it closes a hole the previous draft of this document opened --
committing upstream bodies would make the repository a redistribution channel for exactly the
material hard constraint 1 forbids, walking straight past the gate built to enforce it.

Three rules complete it.

- **Retention: the last 8 runs per adapter**, uploaded with `actions/upload-artifact`. The default
  artifact retention is 90 days *(unverified -- confirm before relying on this; it is configurable
  per repository)*, which comfortably covers eight weekly runs and eight daily ones. Beyond that,
  replay means re-fetch.
- **Licence-aware retention.** `raw_retainable = False` on any adapter whose `licence_class` is
  `share-alike`, `non-commercial`, `no-redistribution` or `unlicensed`, and on HELM until its data
  licence is answered. For those sources we keep only `sha256`, `Content-Length`, the response
  headers and **our own parsed intermediate** -- derived structured facts, which is what we are
  permitted to hold. Replay for a licence-unclear source means re-fetch, and the adapter says so in
  its run record rather than failing mysteriously.
- **The metadata-only gate sniffs, it does not match extensions.** `runs.json.gz` and
  `results.parquet.gz` sail past a check on `.parquet`/`.jsonl`/`.arrow`. The gate decompresses one
  layer and inspects magic bytes (`PAR1`, Arrow's `ARROW1`, SQLite's header string, ZIP's `PK\x03\x04`)
  before deciding. §8 carries the gate.

---

## 5. Identity resolution and deduplication

This is where ingestion actually fails. Not at the HTTP layer -- at the moment the adapter has a
string like `accounts/fireworks/models/glm-4p6` and has to decide which of 550 systems that is.

**[04-data-model.md](04-data-model.md) §10 owns the resolution procedure**: exact `external_ids`,
then the alias table, then normalised-string match, then a structured parse that strips provider
prefixes/suffixes, effort suffixes and date tails while routing every stripped part through the
alias record's `extracts` block, then fuzzy candidates at token-set ratio >= 0.92 which are **never
auto-accepted**, then an unresolved record. The alias table lives at
`data/aliases/{systems,benchmarks,organizations}.yaml` and every entry carries a source and a
decider.

What this document adds is the three things 04 leaves to the implementation: when fuzzy matching
runs at all, how the score is computed and calibrated, and what happens to an unresolved item over
time.

### 5.1 Fuzzy matching is a crosswalk-authoring tool, not a per-row operation

The Epoch corpus makes the point by itself: **all 927 distinct `Model version` strings in the
per-benchmark CSVs join to `model_metadata.csv` at 100%** `[recon 2026-09-17, measured]`. Identity
is *solved within the source and unsolved across sources*. Running a fuzzy matcher over 6,598 rows
every week to rediscover 927 answers a human already gave is both wasteful and dangerous -- it
reintroduces the possibility of a different answer on a different run, which destroys the
reproducibility claim in §1.3.

**The rule: for any source with a stable internal identifier, fuzzy matching runs once, when a
crosswalk entry is first created. Steady-state resolution is an exact dictionary lookup against
`data/aliases/` and emits no confidence at all.** Epoch is such a source. So are HuggingFace
(`owner/name`), GitHub (`owner/repo`), OpenRouter (`canonical_slug`) and Grand Challenge (`slug`).

Fuzzy matching is for sources that publish free-text names: arXiv tables, leaderboard HTML, paper
abstracts, vendor blog posts. **That is where the review cost of the fuzzy band will actually
land**, and sizing it against Epoch -- as the previous draft implicitly did -- overstated it by
roughly two orders of magnitude while understating it for the sources where it bites.

### 5.2 Model-name normalisation, worked

A `model_version` string encodes, in one token, up to four things: hosting provider, model identity,
reasoning effort, and context configuration. The pipeline peels them apart in the fixed order 04 §10
specifies, and each stripped part is routed to a field rather than discarded.

```
raw:        accounts/fireworks/models/qwen3-235b-a22b-thinking-2507
  strip provider prefix   accounts/fireworks/models/
    -> extracts.serving_provider: org-fireworks
  -> qwen3-235b-a22b-thinking-2507
  -> System: qwen3-235b-a22b-thinking   SystemVersion: 2507        EXACT via alias table

raw:        chutes/DeepSeek-R1-0528
  -> extracts.serving_provider: org-chutes | System: deepseek-r1 | SystemVersion: 0528   EXACT

raw:        amazon.nova-pro-v1:0
  -> extracts.serving_provider: org-aws-bedrock | System: amazon-nova-pro | Version: v1:0  EXACT

raw:        gpt-6-astra_max
  strip effort suffix  _(max|xhigh|high|medium|low|minimal|none|unknown)$
  -> System: gpt-6-astra | extracts.eval_conditions.reasoning_effort: max    EXACT
  # 2,402 of the 6,598 rows (36.4%) carry this suffix. `_unknown` maps to NULL, never to a
  # default. (An earlier draft printed 38.9%, which implies a denominator of 6,175 that appears
  # nowhere; 00 §8.1 owns the 6,598 row count and its counting rule.)

raw:        claude-opus-4-6_120K
  -> System: claude-opus-4-6 | "120K" is a context window OR a thinking budget, and the
     adapter does not know which.                                 UNRESOLVED -> human task
  # This is the single most instructive row in the corpus: five claims share this key at five
  # different reasoning efforts (0.94 / 0.94 / 0.93 / 0.92 / 0.86) and the only discriminator
  # is a free-text `Name` column.
```

The crosswalk is not optional and it is the single largest manual cost in the whole Epoch ingest:
roughly **550 model groups and 927 version strings** -- 927, not the 1,048 distinct strings in
`model_metadata.csv`, because 121 of those never appear in a result row and need no crosswalk
([00-vision-and-scope.md](00-vision-and-scope.md) §8.1 owns the counting rule). Budget it honestly
rather than pretending a
regex covers it. The good news is that it is a one-time cost with a long tail: new model versions
arrive at a handful per week and each is a one-line alias entry.

### 5.3 The confidence score, and how it gets calibrated

A threshold on an uncalibrated score is a number-shaped guess, so the score is stated as a formula
and the thresholds are not trusted until it has been checked against labels.

```python
def match_confidence(cand: Candidate, entity: Entity, ctx: MatchContext) -> float:
    return (
        0.50 * (rapidfuzz.fuzz.token_set_ratio(cand.norm, entity.norm) / 100.0)
      + 0.20 * float(ctx.org_agrees)            # source's org string resolves to entity.organization
      + 0.20 * float(ctx.date_plausible)        # |release_date(source) - entity.first_released| <= 120d
      + 0.10 * float(ctx.alias_exact)           # an alias matched exactly before normalisation
    )
```

Weights are a starting point, not a result. **Before the thresholds are used in anger, 100 pairs are
hand-labelled** -- 50 drawn from the score band 0.80--0.95 and 50 uniformly -- and the weights are
adjusted until precision at the auto-propose threshold is above 0.95 on the labelled set. The
labelled set is committed at `evals/golden/identity_resolution.yaml` alongside the AI layer's golden
sets ([11-ai-features.md](11-ai-features.md) §"Evaluating our own AI features" owns that
directory), so the calibration is
reproducible and the next person can re-run it after the weights drift.

How the score is used, which follows 04 §10 rather than restating a competing band table:

| Situation | Action |
| --- | --- |
| Steps 1--3 of 04 §10 match (external id, alias, normalised string) | Resolve. No confidence emitted; the alias record carries the human's own `confidence` field |
| Step 4 structured parse then re-match at steps 1--3 | Resolve. The `extracts` block routes the stripped parts |
| Step 5: best fuzzy candidate scores >= 0.92 | **Propose, never accept.** The run emits an `Unresolved` with `reason: ambiguous-match` and the top 3 candidates with scores, and the dependent record is dropped from this run's drafts |
| No candidate >= 0.92 | `Unresolved` with `reason: no-match`, suggestions empty or weak, and a `human_task` |

The rule stated plainly: **below the bar, the record becomes a human task, not a new entity.** The
failure mode this prevents is the one that destroyed the usefulness of several prior catalogues --
duplicate near-identical entities accumulating until the coverage matrix counts `ARC-AGI` twice and
the gap analysis, which is the project's most valuable output, becomes noise.

### 5.4 Benchmark-name aliasing, and why it is worse

Benchmarks have lineage, and lineage is the thing nobody else models
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) differentiator ii). Every alias
entry is a claim about identity and belongs in the alias table with a source, not in a lookup table
nobody can audit.

| Observed string | Correct resolution | Why a matcher fails |
| --- | --- | --- |
| `GPQA diamond` | Subset of `gpqa` | A subset, not a benchmark; needs `subset`, not a new entity |
| `MATH level 5` | Subset of `math` | Same |
| `FrontierMath-Tiers-1-3-v2-Private` | `frontiermath`, version `tiers-1-3-v2`, access `private` | Four facts in one string |
| `OSWorld` / `OSWorld 2.0` | Two `BenchmarkVersion`s, or two benchmarks -- a human decides | Epoch models breaking changes by creating a new row, which loses the relation |
| `ARC AI2` vs `ARC-AGI` | **Unrelated benchmarks** | Shared prefix, near-identical after normalisation. Token-set fuzzy matching scores these high and is wrong |
| `METR` vs `METR Time Horizons` | Distinct rows; one has no CSV at all | Prefix containment is not identity |

### 5.5 The unresolved lifecycle

Without this, the same items reappear in every PR until the reviewer stops reading that section --
the exact mechanism §8 names for warnings, applied to the largest output surface the adapter has.
`normalise()` is pure and stateless, so next week's run regenerates `claude-opus-4-6_120K`
identically, forever.

[04-data-model.md](04-data-model.md) §10 puts the unresolved *records* at
`data/_ingest/unresolved/{adapter}/{date}.yaml`, one file per batch. This document adds the
**status ledger** beside them, at `data/_ingest/unresolved/{adapter}/status.yaml`, keyed by the
`Unresolved.fingerprint` from §1.1:

```yaml
# data/_ingest/unresolved/epoch/status.yaml
- fingerprint: 9c21ab04c7de1f80
  observed: "claude-opus-4-6_120K"
  field: eval_conditions.thinking_token_budget
  status: open              # open | resolved | wontfix | blocked-upstream | superseded
  first_seen: 2026-09-17
  last_seen: 2026-11-21
  occurrences: 5
  note: null
  decided_by: null
  decided_on: null

- fingerprint: 31f0a7bb90c4e215
  observed: "apex_agents_external.csv"
  field: "*"
  status: blocked-upstream
  first_seen: 2026-09-17
  last_seen: 2026-11-21
  occurrences: 10
  note: "No public leaderboard for APEX-Agents; score column and unit undeterminable.
         Re-check when the paper appears."
  decided_by: <handle>
  decided_on: 2026-09-24
```

The runner diffs each run's unresolved set against the ledger. The PR body shows **new** items in
full and carried-over items as a single line -- "4 carried over, oldest 65 days, see
`data/_ingest/unresolved/epoch/status.yaml`". `wontfix` and `blocked-upstream` items are suppressed
from the PR body entirely and surface only in the report below. A `resolved` item that reappears
flips back to `open` and is shown in full, because the resolution evidently did not hold.

**Open unresolved items older than 90 days get their own band in the staleness report (§9).** A
growing unresolved backlog is a slow-motion version of the silent failure §9 exists to catch: the
adapter runs, the PRs land, and the fraction of the source we actually understand quietly shrinks.

### 5.6 Deduplication

**Never deduplicate at ingest.** Emit every source row as a separate `ResultClaim` and surface
suspected duplicates as a report, not a merge. [04-data-model.md](04-data-model.md) §10 owns the
near-duplicate signature; the ingestion side simply computes it and writes it to the quality
dashboard:

```
same benchmark  AND  same model_version  AND  |Δvalue| < 0.005  AND  different Source spelling
```

That fires on exactly the real case in `arc_agi_external.csv`, where `https://arcprize.org/leaderboard`
and `ARC Prize Leaderboard` are two spellings of one source for one run. It does *not* fire on the
five genuinely distinct `claude-opus-4-6_120K` rows at different reasoning efforts (0.94, 0.94, 0.93,
0.92, 0.86), which an automated deduper keyed on model + benchmark would happily collapse into one --
destroying the single best demonstration of why this project exists.

---

## 6. The output path

**Adapters produce draft pull requests. Never direct commits to the citable data tree.**

### 6.1 Bot identity

A dedicated machine account, `uaibi-bot`, holding a **fine-grained PAT** scoped to `contents:write`
and `pull_requests:write` on the data repository only. Two reasons, and the second one is
load-bearing in a way the first is not:

1. It keeps bot commits attributable and separable in `git log` from human curation, which matters
   when someone forks the dataset and wants to know which records a person actually looked at.
2. **A pull request created with the ambient `GITHUB_TOKEN` does not trigger other workflows**
   *(unverified -- confirm before relying on this; it is long-standing documented GitHub Actions
   behaviour intended to prevent recursive runs)*. Our entire gate story depends on
   `pr-validate.yml` running **on the bot's PR**, and branch protection requires that check to be
   green. If the behaviour is as described and we used the ambient token, every bot PR would sit
   forever with no checks and a greyed-out merge button, and the symptom would look like a branch
   protection misconfiguration rather than a token choice. Using the PAT avoids it. §9 adds a canary
   that alerts if any open `ingest:*` PR has zero check runs, so that if the assumption is wrong in
   either direction we find out in a week rather than a quarter.

Risk, and it is real: **fine-grained PATs expire** (documented maximum one year *(unverified --
confirm before relying on this)*) **and the expiry presents as a silent authentication failure, not
an error a human sees.** Put the token's expiry date into the staleness report in §9 so it becomes a
countdown rather than an outage. Migrate to a GitHub App installation (5,000--12,500/hr
`[recon 2026-09-17, vendor docs]`, no expiry treadmill) if and when the rate limits bite; there is
no reason to pay that setup cost on day one.

### 6.2 Change classification

```
fetch -> normalise -> diff against current YAML (filename, then lineage key) -> classify
  ├─ NEW entity            -> branch, label ingest:new,     human review required
  ├─ FIELD CHANGE          -> branch, label ingest:update,  before/after table in the body
  ├─ NUMERIC RESULT CHANGE -> branch, label ingest:result,  ALWAYS human-reviewed, same-day PR
  ├─ GONE upstream         -> branch, label ingest:gone,    NEVER deletes our record (§7.3)
  ├─ METRICS ONLY          -> metrics/ tree, auto-merge permitted (§6.4)
  └─ NO CHANGE             -> write the run record, no data change, no PR
```

Branch naming: `ingest/<adapter>/<iso-year>-W<week>`, accumulating daily commits, promoted to a PR
on Friday (§3.3). Same-day escalation branches are `ingest/<adapter>/<date>-urgent`.

### 6.3 The PR body is the review surface

The reviewer should be able to approve or reject **without opening a single file**. That is the
design target, and it is achievable because the adapter already knows everything the reviewer needs.

```markdown
## ingest/epoch/2026-W38 · adapter v1.4.0 · 5 runs (Mon–Fri)

**Source** Epoch AI — Capabilities & Benchmarking (CC-BY-4.0, permissive-attribution)
**Latest fetch** 2026-09-17T04:17:11Z · ETag `"a95a0b35…"` · snapshot sha256 `9f2c…` · 2,292,857 B
**Resolver snapshot** `b71e…` (built from `main` at `4d1c8a9`)
**Attribution** Epoch AI, 'Capabilities & Benchmarking'. Published online at epoch.ai.

### What changed
| Entity | Field | Old | New | Source | Archive |
|---|---|---|---|---|---|
| sys/glm-5-2 | versions[] | — | `glm-5.2_max` | epoch.ai/benchmarks | web.archive.org/… |
| claim/swe-bench@verified/3c8e10ba55f7 | value | — | 0.787 ± 0.0187 | epoch.ai/benchmarks | … |
| claim/arc-agi/9d02ffa1c3b7 | value | 0.920 | 0.931 | arcprize.org/leaderboard | … |

Totals: 3 new · 11 field changes · 42 result claims · 1 gone · 0 deletions

### What the adapter could NOT resolve
**New this week (2)**
| Observed | Field | Reason | Top suggestions | Human task |
|---|---|---|---|---|
| `zai-org/glm-5.3` | claim.system | no-match | glm-5.2 (0.88) | Add an alias entry with `extracts.serving_provider`. |
| `cl_bench_life.csv` | * | no-match | — | Write the mapping stanza; score column and unit unknown. |

**Carried over: 4** (oldest 65 days) → `data/_ingest/unresolved/epoch/status.yaml`
**Suppressed:** 3 `wontfix` / 1 `blocked-upstream`

### What a human must check before merging
- [ ] The `arc-agi` value moved 0.920 → 0.931 at the same lineage key — upstream correction or parse bug?
- [ ] `vending_bench_2` values are DOLLARS, not a 0–1 rate — confirm the metric ref is right
- [ ] Ten transcript spot-checks for this batch (§2.3) — 10/10 opened, 10/10 matched
- [ ] No facet fields were populated by the machine (should be 0)

### Gates
schema ✅ · referential ✅ · provenance ✅ · sanity-band ✅ (0 outliers) · unit-guard ✅
caps ✅ (claims 56/200 · benchmarks 3/25) · verification-ceiling ✅ · attribution ✅
metadata-only ✅ (magic-byte sniff, 0 hits) · licence-firewall ✅
condition_completeness on this batch (computed, not stored): mean **0.11**, max 0.38
```

### 6.4 Labels, review, and the three exceptions to rule 1

Labels: `ingest:new`, `ingest:update`, `ingest:result`, `ingest:gone`, `ingest:metrics`,
`ingest:correction`, `needs-scrutiny`, `adapter-broken`, and `source:<name>`. Branch protection on
`main` requires one approval plus the green `pr-validate.yml` check,
**with no bot bypass** ([05-repository-and-workflow.md](05-repository-and-workflow.md) §5 owns the
review matrix). That last clause is what makes "fully auditable" a fact rather than a slogan; a
bypass exists to be used at 11pm on a Friday.

Rule 1 says adapters do not write to `main`. There are exactly three exceptions, each bounded:

**(a) Run logs and state files commit directly to `main` under `ingest/**`.** These are
`ingest/state/<adapter>.json` and `ingest/runs/<adapter>/<date>.json`. They are outside the citable
data tree, they are protected by a CODEOWNERS path rule so a human edit still gets reviewed, and
they carry `export-ignore` in `.gitattributes` so they never enter a release tarball. The
justification is circular otherwise: the run log is the evidence that the run happened, and putting
it behind a review queue means a failed run has no record until someone approves the record of its
failure.

**(b) Adoption counters auto-merge into `metrics/**`, licensed CC0.** Pure counters --
`github_stars`, `hf_downloads`, `hf_likes`, `arxiv_citations` -- are high-frequency, low-stakes, and
reviewing them would train the reviewer to rubber-stamp everything. The tree is schema-constrained
to numeric fields only, is excluded from every citable artefact, and is listed in `.zenodoignore`
and `.gitattributes export-ignore` so the DOI'd release mechanically cannot contain it. A
compromised adapter can write numbers there and nothing else.

The shape of that tree matters more than it looks. Two options, with the arithmetic that decides
them at the 1,500-benchmark target scale:

| Option | Write pattern | Annual growth |
| --- | --- | --- |
| Per-entity file, updated daily | 1,500 files rewritten per day; 547,500 blob revisions/year | Loose objects plus tree churn; a `git clone` degrades noticeably within a year. Rejected |
| **One append-only JSONL per ISO week** | One new file, ~1,500 lines of ~80 bytes | **~120 KB/week, ~6.2 MB/year.** Chosen |

So: `metrics/adoption/<yyyy>-W<ww>.jsonl`, appended once per week by `ingest-hub.yml`, never
rewritten. The site reads the last N weeks for a sparkline; the analytics layer reads the whole
directory. At Phase-1 scale (a few hundred benchmarks) it is 16 KB/week.

**(c) Nothing else, ever.** No adapter writes to `data/`, `taxonomy/`, `schema/` or `site/` outside
a reviewed pull request.

**The rule, stated plainly: ingestion never auto-merges into the published, citable build.**

---

## 7. Conflicts, corrections, and disappearance

### 7.1 Conflicting claims: both coexist, and nothing is stored

When an ingested claim disagrees with one already in the index, **we do not overwrite, and we do not
adjudicate**. Both coexist. This is a schema position, not an ingestion convenience: the index's
signature behaviour is declining to rank things that are not comparable, and the same discipline
applies to declining to pick a winner between two sourced numbers
([12-analytics-and-trends.md](12-analytics-and-trends.md) §12, "Analyses we will not publish",
owns the display side).

The canonical case is in the Epoch corpus already. `mmlu_external.csv`, model `falcon-7b`, all at a
nominal 5 shots `[recon 2026-09-17, measured]`:

| Value | Source |
| --- | --- |
| 0.35 | Falcon2-11B Technical Report -- arxiv.org/abs/2407.14885 |
| 0.262 | Llama 2 paper -- arxiv.org/abs/2307.09288 |
| 0.262 | Qwen Technical Report -- arxiv.org/pdf/2309.16609 |
| 0.2603 | Baichuan 2 -- arxiv.org/abs/2309.10305 |
| 0.269 | XGen-7B Technical Report (2-shot) -- arxiv.org/abs/2309.03450 |
| 0.239 | XGen-7B Technical Report (0-shot) -- arxiv.org/abs/2309.03450 |

A 34% relative spread on the same model and benchmark from four vendors' papers. Epoch stores all
six and does not adjudicate. So do we -- but with structure, because two of those six differ by a
*stated* shot count and the rest differ for reasons nobody recorded.

**Decision: there is no stored conflict edge.** The previous draft proposed a `conflicts_with` field
on `ResultClaim` written by the adapter and closed symmetrically at build time. That is deleted, for
three reasons. A stored forward edge is a hand-maintained back-reference waiting to go stale. The
information is already fully derivable: a conflict is any group of claims sharing
`(benchmark@version, system@version, metric, subset)` with differing values, which the build
computes in one pass over the claim set. And a stored edge is an assertion by the index that two
numbers are *about the same thing*, which is an identity judgement -- exactly the kind of call our
signature behaviour is to decline without evidence.

What the adapter does instead is smaller and entirely mechanical:

```python
existing = resolver.claims(benchmark=bm, system=sys, metric=metric, subset=subset)
if existing and not any(numerically_equal(c.value, value, tol=1e-9) for c in existing):
    draft.change_class = "new"                 # a NEW claim, never a patch to the old one
    draft.labels.append("needs-scrutiny")
    report.notes.append(
        f"{bm}/{sys}/{metric}: new value {value} alongside {len(existing)} existing "
        f"({', '.join(str(c.value) for c in existing)}). Not adjudicated."
    )
```

Two properties are load-bearing. A conflict is **never** a reason to suppress either claim --
suppression would be an editorial judgement, which constraint 4 forbids. And a conflict *is* a
reason to escalate to a same-day PR (§3.3), because a new number that disagrees with an existing one
is either genuine news or a parsing bug, and those are the two cases a human distinguishes in
seconds and a machine cannot.

### 7.2 Corrections to data that has already merged

`bench ingest replay` fixes a bad parser *before* merge. This is what happens when adapter v1.3.0
mis-scaled a column, 400 claims are already on `main`, and one of them is inside a DOI'd release.
The sanity band in §8 exists precisely because we expect this, so the correction path is not
optional.

```
bench ingest recompute epoch --from-version 1.3.0 --to-version 1.4.0
```

This re-normalises every already-merged record whose `ingestion.adapter_version` falls in the range,
against the stored raw payload where the licence allows it (§4.4) and a re-fetch where it does not,
and opens **one `ingest:correction` PR** with a before/after table and the reason.

**The mechanism is withdraw-and-supersede, never edit in place.** Claim ids are content-derived from
a tuple that includes `value` (§1.4), so editing a value in place would leave the filename lying
about its content -- and a `corrections[]` array on the record would force the id to be computed
from a non-identifying subset, which reintroduces the mutable-key problem the content-addressed
scheme exists to remove. Instead:

- The corrected claim is written as a **new file** at its own content-derived id.
- The old file gains `superseded_by: claim-<new id>` and stays where it is. The build renders it
  struck through with the correction reason; the reverse edge is derived, never stored twice.
- The commit carries a `Correction:` trailer, which is what
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §8 generates the public
  `/corrections` page from. That page is the honesty surface and it costs one trailer per commit.

**Retraction, where there is no replacement**, uses machinery that already exists rather than a new
field: the claim file is removed from the working tree and a tombstone appears at
`data/tombstones/<claim-id>.yaml` carrying the reason, the date, the adapter version that produced
it, and `redirects_to: null`. The claim remains resolvable at every commit that contained it, which
is exactly what "citable at a commit hash" means, and the tombstone is what keeps an old citation
from 404-ing on the live site.

The one case where an ingested record *updates* rather than being superseded is a pure upstream
correction from the same source at the same lineage key: that is a `result-change`, it carries both
values in the PR body, and the superseded value survives in `git log` forever -- which is the whole
reason the data is in git.

### 7.3 Disappearance upstream

`ChangeClass` includes `gone`, and this is where
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) differentiator (iv) --
liveness and deprecation signalling -- is actually produced rather than asserted. One study found
137 of 195 safety benchmarks had stale repositories and BetterBench found 17 of 24 had no working
reproduction scripts; **no catalogue marks benchmarks as dead**
([01-landscape-and-positioning.md](01-landscape-and-positioning.md) §1.9 states how far that negative
claim is supported and what would retire it). The reason is that nobody stores
what they saw last time, so nobody can tell when something stopped being there.

The rule: **an upstream disappearance never deletes our record.**

1. A lineage key present in the previous run's record set and absent from this one increments
   `absences` in `ingest/state/<adapter>.json`. Nothing else happens. One absence is a pagination
   glitch, a partial export, or a 500 the retry swallowed.
2. At **two consecutive absences**, the runner writes `ingestion.last_seen_upstream: <date>` onto
   that one record, classifies it `gone`, and labels the PR `ingest:gone` with `needs-scrutiny`.
   (`ingestion.last_seen_upstream` is a proposed one-field addition to the block
   [04-data-model.md](04-data-model.md) §9 owns.)
3. A record marked `gone` is still published, still citable, and still counted. What changes is that
   the site renders "no longer listed on the upstream leaderboard as of <date>" beside it.
4. Benchmark-level death is a separate, slower judgement that
   [05-repository-and-workflow.md](05-repository-and-workflow.md) §7 owns: observable signals go
   cold for twelve months, a bot proposes `lifecycle: dead`, and two humans confirm. Ingestion
   supplies the signals; it does not make the call.

This is worth paying for because it is the only one of the four differentiators that ingestion
produces *directly* rather than merely feeding. Epoch ships one ETag over the whole archive, so a
retracted result is invisible unless you diff the record set -- which §1.4 already makes us do.

---

## 8. Quality gates

Every gate runs in CI on **every daily run**, before anything reaches the weekly branch, and a red
gate means no commit rather than a commit with a warning. A warning in a PR body is a thing humans
learn to scroll past.

| Gate | Check | Failure response |
| --- | --- | --- |
| **Schema** | Pydantic v2 validation of every draft against the canonical models | Hard fail. No commit |
| **Referential** | Every `benchmark`, `system`, `metric`, `organization`, `source`, `conditions` ref resolves to an existing file; every taxonomy value is in the controlled vocabulary at the facet-qualified id ([05-repository-and-workflow.md](05-repository-and-workflow.md) check 9c) | Hard fail. Unresolvable refs become `Unresolved` records and the dependent record is dropped, not stubbed |
| **Provenance** | Every record carries a complete `ingestion` block: `batch`, `source_adapter`, `adapter_version`, `source_record_id`, `source_url`, `source_licence`, `licence_class`, `source_attribution`, `ingested_at`, `review_state`, `field_provenance`; and, for non-DOI sources, a queued `archive_url` | Hard fail. A record without provenance must never merge |
| **Verification ceiling** | No ingested record above `independent-reproduction` (rank 3). Rank 3 additionally requires a reachable `artifact_url` | Hard fail. Downgrade + `needs-scrutiny` for the unreachable case (§2.3) |
| **Derived-field guard** | No draft contains `comparability_key`, `condition_completeness`, `headroom` or any other build-derived field | Hard fail. Rule 4 made mechanical |
| **Sanity band** | After scaling, `value` lies within `[chance_baseline − 0.02, score_ceiling + 0.02]` where both are known; otherwise within `Metric.range`; for `Metric.unbounded: true` within ±5σ of the metric's existing claim distribution | Reject the row, emit `Unresolved(reason="unparseable")`. This is the gate that catches the dollars-in-a-0–1-field class of bug |
| **Metric definition** | The referenced `Metric` declares **either** a `range`, **or** `unbounded: true` with a `value_type`, **or** `value_type: qualitative`. A numeric claim against a metric with none of the three is refused | Hard fail. Elo, dollars and minutes -- all three present in the Epoch corpus -- must be modelled before they are ingested, not discovered at 2am |
| **Unit guard** | A claim whose mapping stanza has no explicit `scale` is refused. There is no default | Hard fail -- refusing to guess is the point |
| **Caps** | Per entity type, `cap = max(floor, min(ceiling, 0.25 × existing_files_of_that_type))`. See below | Status `capped`: write the run record, open an **issue** with the diff summary, commit nothing |
| **Metadata-only** | Decompress one layer and sniff magic bytes (`PAR1`, `ARROW1`, `SQLite format 3`, `PK\x03\x04`, gzip) anywhere under `data/` **or `ingest/raw/`**; reject any single YAML string field over **280 characters** of copied prose | Hard fail. Hard constraint 1 made mechanical rather than aspirational |
| **Attribution** | The adapter's `attribution` string is present on every record and the generated `docs/attribution.md` regenerates cleanly | Hard fail |
| **Licence firewall** | The source's `licence_class` is on the allowlist for the target tree ([04-data-model.md](04-data-model.md) §9). CC-BY-SA content may only land under `vendor/pwc-archive/`, never in the CC-BY core. Also applies to `ingest/raw/` retention (§4.4) | Hard fail |
| **Round-trip determinism** | Re-emitting every touched file with the §1.5 emitter produces a zero-byte diff | Hard fail |

### 8.1 The caps, and why "whichever is smaller" was wrong

The previous draft said "<= 200 changed files **and** <= 25% of the affected tree, whichever is
smaller". At Phase-1 scale -- 40 benchmarks, 120 claims -- 25% is 30 files, so any meaningful ingest
run would be `capped` and would open an issue instead of doing its job. The cold-start period is
exactly when you most want ingestion working. A percentage cap is a *growth-rate* guard and is
meaningless below a few hundred records, so it needs a floor. And a single global number is the
wrong shape anyway: 200 changed claim files is routine, 200 changed *benchmark* files is always a
bug.

| Entity type | Floor | Ceiling | Reasoning |
| --- | --- | --- | --- |
| `claim` | 50 | 200 | Bulk is the normal case; the first Epoch run is a deliberate exception |
| `benchmark` | 10 | 25 | New benchmarks arrive at a handful per week from every source combined |
| `system` | 25 | 100 | Model releases cluster; a 100-model week is plausible after a big launch |
| `organization` | 5 | 25 | Organisations are nearly static |
| `metric` | 5 | 20 | A 20-metric run means the parser invented metrics |
| `source` | 50 | 200 | One source per claim in the worst case |
| `conditions` | 50 | 200 | Shared entities; often fewer than claims, never more |

The cap deserves its own sentence, because it is the gate that saves the project from its own
automation: **a runaway adapter that opens a 400-file PR is worse than one that opens none.** A
400-file PR does not get reviewed; it gets merged tired or closed and forgotten, and either outcome
destroys the review discipline that everything else depends on. The first Epoch bulk run
legitimately exceeds the cap -- 6,598 claims -- and is run once, by hand, with `--allow-bulk`, as a
deliberate one-off with its own dedicated review, its own commit message and its own `IngestBatch`
record. After that the cap is absolute.

### 8.2 The semantic-anomaly rule

If more than 20% of an adapter's records changed in one run, or any benchmark's top reported score
moved by more than 30 percentage points, the run escalates to a same-day PR with `needs-scrutiny`,
auto-merge is blocked, and the anomaly is stated in the first line of the body. Both are almost
always parser bugs. Occasionally one is real news, which is exactly the thing a human should see.

---

## 9. Observability on a zero-budget stack

The failure this section exists to catch: **the arXiv adapter has silently returned zero results for
three weeks.** Not a crash -- a clean exit, a green checkmark, and nothing in the PR queue. Nobody
notices, because "no PRs this week" looks identical to "no new benchmarks this week". Three months
later the index is stale and the staleness is invisible, which is precisely the Ecosystem Graphs
failure: still cited, twenty months frozen, actively propagating errors.

Four mechanisms, all free, three of them committed to the repo and the fourth published to the site.

**1. A committed run log.** Every adapter run writes `ingest/runs/<adapter>/<YYYY-MM-DD>.json` --
the `RunReport` from §1.1 -- and commits it even when nothing else changed (exception (a) in §6.4).
This is the monitoring system and it costs nothing. Because it is in git, "when did this adapter
last actually work" is answerable by anyone with a clone, including a future maintainer who inherits
the project, which is part of the succession story in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §10.

**2. A staleness report.** `bench report staleness` renders, and `health-check.yml` publishes to a
single rolling GitHub issue every Monday:

```
adapter          last_success  last_change  yield  band        unresolved>90d  status
epoch            2026-09-17    2026-09-16      81  41–162                   1  ok
hf-hub           2026-09-17    2026-09-17   1,019  512–2,048                0  ok
arxiv-oai        2026-09-16    2026-08-24       0  15–200 (seed)            0  ⚠ ZERO YIELD 23d
helm             2026-09-11    2026-08-02       3  1–30 (seed)              2  ok
swe-bench        2026-09-17    2026-09-14     323  162–648                  0  ok
grand-challenge  2026-09-17    2026-09-05     264  132–528                  7  ⚠ UNRESOLVED BACKLOG
--
open ingest PRs with zero check runs: 0
secrets: GH_API_TOKEN expires 2027-03-04 (168 days)
```

**3. Bands that adapt, because a band that never changes gets muted.** The previous draft
hard-coded `expected_yield` per adapter. A healthy growing source outgrows its band, alerts forever,
and is silenced -- after which the adapter is unmonitored and nobody remembers. The rule:

```
band = trailing_median(last 8 successful runs) × [0.5, 2.0]
     floored by the hand-written seed band until 8 runs exist
plus an absolute guard: yield == 0 while trailing_median > 0  ->  alert immediately, always
```

The zero-guard is the important half. Zero results from arXiv is not an error condition in any HTTP
sense -- it is only detectable as a yield anomaly, and it is the single most likely way this
pipeline dies quietly. The adapter author writes the seed band while they still remember what normal
looks like; after eight runs the data takes over.

**4. A scheduled canary that opens an issue.** `health-check.yml` runs on `schedule` and
`workflow_dispatch` and opens (or updates) an issue labelled `adapter-broken` when any of these
holds: an adapter's `last_success` is older than twice its declared cadence; its yield has been
outside the band for two consecutive runs, or is zero against a non-zero median; an open `ingest:*`
PR has zero check runs (the §6.1 token trap); an adapter's open unresolved items older than 90 days
exceed 5; or a secret expires within 60 days. Because the canary is itself a scheduled workflow it
can also fail silently -- so it is the one job that additionally writes its heartbeat into the
weekly digest issue's **title**, where a human sees the date without opening anything.

### 9.1 Publish the freshness, do not just alert on it

The staleness report above is maintainer-facing, and the canary's self-monitoring ultimately reduces
to "a human sees a date in an issue title". That is the same trust posture Ecosystem Graphs had: its
staleness was invisible *to its readers*, which is why it kept being cited twenty months after it
froze.

**Recommendation: publish it.** The build reads `ingest/state/*.json` and emits
`build/derived/ingest-health.json` -- per source: last successful fetch, last content change,
current record count, licence class and attribution -- and the site renders a per-source freshness
strip on the provenance page and a one-line freshness badge on every entry whose fields came from
that source. [05-repository-and-workflow.md](05-repository-and-workflow.md) §7 already displays
per-entry `last_verified`; this is the same honesty applied to the machine half of the corpus, and
it needs a line in [10-visualization.md](10-visualization.md) (it is closest to V6 Detail and V8
Feed) and a token in [09-design-system.md](09-design-system.md) to own the badge states.

It turns the alarm into a product feature, it makes staleness visible to the people most likely to
be misled rather than only to the two people most likely to stop looking, and it is the direct
expression of differentiator (iv). Cost: one derived artifact of a few kilobytes and one component.

### 9.2 Three failure classes, three responses

| Class | Example | Response |
| --- | --- | --- |
| **Transport** | Timeout, 5xx, 429 | Retry ×3 with jitter, then soft-fail, log, **no commit**. Alert only after **3 consecutive** failed runs -- otherwise you get weekend noise and learn to ignore the channel |
| **Schema drift** | 200 OK but `<script id="leaderboard-data">` is gone from swebench.com | **Hard fail immediately.** Open an `adapter-broken` issue. Assert structure explicitly; never `.get()` with a default. This is the class that silently corrupts data if swallowed |
| **Semantic anomaly** | >20% of records changed, or SOTA moved >30 points | Same-day PR, label `needs-scrutiny`, block auto-merge, state the anomaly in line one |

Alerting channel is GitHub Issues plus the repository's notification email. A two-person part-time
team does not need PagerDuty; it needs one weekly digest it actually reads.

---

## 10. Cost and rate-limit budgeting

Monetary cost is near zero by design. The budget that actually binds is requests-per-window against
hosts, several of which are small academic servers.

**[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §9 owns the per-source limits, the
licences and the legal posture, and the operating rules for every adapter.** What follows is only
our *usage budget* against them, which is this document's to set, plus the enforcement mechanism.

| Source | Our budget per run | Note |
| --- | --- | --- |
| Epoch AI | 1 conditional GET/week | ~2.3 MB, usually a 304 |
| arXiv OAI-PMH | 1 day-window/run, 1 req/3 s | One `set=cs` day = 3.1 MB, 1,157 records `[recon 2026-09-17, measured]` |
| HuggingFace | ~1 req/s with `HF_TOKEN`, <=2,000 req/run | Under the 1,000-per-5-minute free-token ceiling by ~3x |
| GitHub API | <=2,000 req/run, `If-None-Match` everywhere | 304s are free; the ambient token's 1,000/hr/repo is not enough |
| OpenAlex | Bulk CC0 snapshot + singleton lookups only. Never poll | Three published numbers disagree (§12). Get a key and measure before sizing anything |
| Semantic Scholar | <=3,000 lookups/run ≈ 50 min at 1 RPS | Key turnaround time is **unverified** |
| Wayback SPN2 | <=500 saves/day, `if_not_archived_within=30d` | Use CDX for existence checks; the Availability API 429s on a cold request |
| Grand Challenge / Codabench / EvalAI | **1 req / 2 s, deliberately over-throttled** | Being the project that took down the CASP server is a reputational injury no licence protects against |
| Artificial Analysis | **Zero.** Link out only | Redistribution contractually barred (terms read 2026-09-17; [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §8 owns the reading and its as-of date) |
| LLM triage (arXiv) | ~15--95 calls/day `[recon 2026-09-17, measured]` | See below |

**The one line item with a monetary cost.** arXiv triage at the upper bound of 95 calls/day, with a
rubric-plus-abstract prompt of roughly 1,200 input tokens and ~50 output tokens per call, is about
**42M input and 1.7M output tokens per year**. At `claude-haiku-4-5`'s published rate card -- which
[11-ai-features.md](11-ai-features.md) §"Model selection and cost" owns and this document does not
restate -- that is on the
order of **$50/year**, falling further with prompt caching of the rubric. It is the only recurring
cost in the entire ingestion stack, and it buys the difference between ~60% precision from keyword
heuristics and ~85--90% from a classifier `[recon 2026-09-17, measured]`.

### 10.1 Enforcement, not discipline

The politeness policy itself belongs to [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md)
§9. Three implementation rules make it real rather than aspirational, and they belong here because
they are properties of the fetcher:

- **Per-host token buckets are a property of the HTTP client, not of the adapter.** A rate limit
  that depends on every adapter author remembering it will be violated by the eleventh adapter.
  `HostPolicy` is constructed from a single `ingest/policy.yaml` and the fetcher refuses to issue a
  request for a host with no policy entry.
- **`robots.txt` is fetched, cached per host per run, and honoured by the fetcher.** It must be
  *structurally impossible* for any code path to reach `drivendata.org/*/leaderboard_partial`,
  `epoch.ai/inspect-viewer/` or `epoch.ai/frontiermath/tiers-1-4/benchmark-problems`. Epoch's stated
  reason for that last exclusion is "to avoid contaminating training datasets", which is our own
  ethic pointed back at us; violating it would be an own-goal no amount of licence compliance
  repairs.
- **The `no-collect` list is read by the fetcher at start-up.** Any maintainer who asks us to stop
  collecting from their site gets an entry, and the fetcher refuses the host outright. A project
  asking the field to trust its provenance cannot argue with the field about consent.

---

## 11. What ingestion actually saves

Be honest about this, because over-claiming here is how a plan sets a team up to be demoralised at
month four.

**Ingestion does not remove curation work. It retargets it from "find and type" to "verify and
resolve".** The volume of records goes up by a factor of ten or more; the hours go down by
considerably less, and the remaining hours are spent on harder, more judgement-heavy tasks.

### 11.1 The Epoch case, quantified

| Entity | Fields Epoch fills directly | Fields we must author | Machine share |
| --- | --- | --- | --- |
| `Benchmark` | ~7 of ~45 (`name`, `aliases`, `release_date`, `homepage`, `chance_baseline`, `score_ceiling`, `superseded_by`) | ~30 of ~45, including **every facet** | ~15% |
| `System` | 8 columns at 85--98% fill, plus `training_compute_flop` at 31% | `system_type`, modalities, parameter count, `built_on`, sources | ~55% |
| `Organization` | `name`, `country` for 70 orgs | `type`, `homepage`, `parent_org`, aliases; splitting comma-joined values | ~40% |
| `ResultClaim` | `value`, `system`, `benchmark`, `metric`; uncertainty on 42.7% of rows; a source on 60.4% | verification beyond the coarse rule, archival, conflict review | ~70% |
| `EvalConditions` | `shots` on 19.4% of rows, `reasoning_effort` on 36.4% (2,402 of 6,598; §5.2), everything else ≈0% | **~90% of the material fields** | **~10%** |
| `Baseline` | Essentially nothing (ForecastBench superforecaster columns, GDPval win rates) | ~99% | ~1% |

Read the last three rows together and the picture is clear. **Ingestion makes claim count free and
makes condition completeness expensive.** One Epoch adapter run delivers 6,598 claims of which the
subset clearing `comparison_floor` -- the named completeness threshold declared in
`taxonomy/thresholds.yaml` and owned by [12-analytics-and-trends.md](12-analytics-and-trends.md), and
referenced here by name rather than by value so there is not a fourth number for one bar -- is
**approximately zero**. Even the best-documented file in the corpus (`deepswe_external.csv`, carrying
Harness, Reasoning effort, Runs, mean agent steps and a 95% CI half-width) leaves five *material*
fields null: `chain_of_thought`, `judge_model`, `tools_allowed`, `selection_strategy` and
`retries_allowed`. (An earlier draft named `temperature` and `shot_selection` here. Neither is in
[04-data-model.md](04-data-model.md) §8's material set -- `temperature` is expressly non-material and
the field is `selection_strategy` -- and naming a non-material field as a completeness gap overstates
the problem in the one place the plan is arguing for honesty about it.)

That is why [14-roadmap.md](14-roadmap.md) states the Phase-3 gate as hand-curated claims at
`condition_completeness >= 0.6` with a named source and an archived URL, with a floor on the non-LLM
share, rather than as a raw claim count. A count target of 500 is met **thirteen** times over by a
download (6,598 ÷ 500 = 13.2; [04-data-model.md](04-data-model.md) §7 derives this and owns it); it
measures our bandwidth, not our work.

### 11.2 What ingestion costs the curator, as rows of the one steady-state budget

**[06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §5.4(a) owns the steady-state
allocation of the curator's week.** An earlier revision of this section held a rival allocation of
the same twenty hours — five activities, five percentages, summing correctly to 100% and sharing no
line item with `06`'s table. Two complete budgets for one week is worse than one imperfect budget,
because a reader can add them together and neither document can say which is wrong. So this table
gives the *ingestion-attributable* hours and names the row of `06` §5.4(a) that each one lives in.

| Ingestion activity | h/week | Lives in `06` §5.4(a) as | Notes |
| --- | --- | --- | --- |
| Reviewing ingest PRs | ~1.5 | Review, disputes, correspondence | ~6 PRs/week at ~20 min (§3.3). Should fall as adapters stabilise and mapping stanzas accumulate |
| Resolving `Unresolved` records (aliases, ambiguous identity, mapping stanzas) | 2-4 | Identity resolution on ingested records | The Epoch system crosswalk alone is ~550 groups and 927 version strings (§5.2) |
| Assigning facets to ingested benchmark stubs | ~1.5 | Triage and intake | 100% human; no machine share exists. This is differentiator 3's input |
| Hand-curating non-LLM domains | 4 | Claims and conditions | Where there is no adapter, no competitor, and no substitute |
| Adapter maintenance and schema-drift repair | 0.7-2 | Adapter maintenance and schema-drift repair | Lumpy: near zero for months, then a day when a page changes |
| **Ingestion-attributable total** | **9.7-13** | | Roughly half the curator's week |

**Read that total before reading anything else in this document.** Ingestion is sold as the thing
that saves curator time, and on this plan's own numbers it consumes about half of it. That is not an
argument against building it — the alternative is hand-writing 6,598 claims — but it is the argument
for the tiering in §11.3 and for `06` §4's refusal to build adapters nobody needs. **An adapter is
not free once it exists; it is a standing subscription paid in the scarcest resource the project
has.**

The honest one-line summary: ingestion buys **coverage** -- which is exactly what the user asked
for, a great searchable collection -- and it buys almost none of **comparability**, which is where
the project's credibility lives. It is worth building for the first reason and must never be
mistaken for progress on the second.

### 11.3 What this costs to build, and the smallest version that ships

The previous draft estimated curator time carefully and its own engineering time not at all, which
is the classic way a framework eats the project it was meant to serve. What §1--§9 specifies is: an
ABC plus runner, a fetcher with per-host token buckets and robots caching, a state layer, a resolver
with snapshotting, a differ with a lineage index, a YAML emitter, thirteen quality gates, a PR
generator with a rendered body, a replay and recompute mechanism, a CLI with seven verbs, a canary,
a staleness reporter, and then the adapters.

[14-roadmap.md](14-roadmap.md) owns the effort totals and this document adds none. What it adds is
the **internal split of the two roadmap rows that fund ingestion** -- "Schema, taxonomy, CLI, CI"
and "Epoch adapter, ~80 column stanzas, 21 orphan hand-maps" -- so that a reader can see whether the
framework fits inside them:

| Component | Person-days | Note |
| --- | --- | --- |
| Fetcher: token buckets, robots cache, conditional requests, backoff | 1.5--2 | The reusable core; every adapter depends on it |
| State layer + cursor + checkpoint | 0.5--1 | Small, and the part everyone skips |
| Resolver + snapshot + lineage index | 1--1.5 | The reproducibility guarantee lives here |
| Differ + YAML emitter + round-trip test | 1--1.5 | Determinism is cheap now and expensive later |
| Quality gates (13) | 2 | Mostly thin; the sanity band and magic-byte sniff carry the weight |
| PR generator + rendered body + weekly promotion | 1--2 | The review surface is the product for the maintainer |
| Canary + staleness report + adaptive bands | 1 | |
| ABC extraction and refactor of adapters 1--2 onto it | 1--2 | Paid once, at adapter #3 |
| **Framework subtotal** | **9--13** | ~20--26 h at 2 h/day, which fits inside the roadmap's CLI/CI row only if the staging below is followed |
| Epoch adapter engine | 1--1.5 | |
| ~80 mapping stanzas + 21 orphan hand-maps | 3--5 | [14-roadmap.md](14-roadmap.md) owns this estimate; the orphans are 5--10 h of it |

**Phase 0 of ingestion is a single script, and that is a decision, not a concession.** Before any of
the above exists:

```
ingest/epoch.py            one file, run by hand from a laptop, --fixture only
                           writes YAML through the shared emitter
                           runs schema validation, the unit guard, the sanity band and the caps
                           no cron, no canary, no replay, no PR bot, no ABC
```

That script produces the first bulk ingest, which is a hand-run one-off under `--allow-bulk` anyway,
and it is the thing that discovers what the contract should look like. **The `Adapter` ABC gets
extracted when the third adapter is written**, because a contract generalised from one instance is a
guess and a contract generalised from two is usually a guess about the third. Adapter #2 is
HuggingFace Hub, which is API-shaped rather than bundle-shaped, so the pair spans both families
before anything is abstracted.

The named failure mode: **the framework becomes the project.** The brief's own mortality analysis
says these catalogues die of the curation treadmill, not of missing infrastructure, and a team of
two that spends its first eight weeks building an ingestion framework has spent them not curating.
The staging above front-loads exactly the parts that would be painful to retrofit -- content-derived
ids, the YAML emitter, the caps and the sanity band -- and defers everything else.

### 11.4 What the ingested tree costs the build

[08-infrastructure-and-build.md](08-infrastructure-and-build.md) settled two unsharded JSON
artifacts on a measurement of a 1,500-*benchmark* corpus: 2.76 MB raw / 0.52 MB brotli for
`corpus.json`, 36 KB gzipped for the slim facet index. Ingestion adds 6,598 claims from one adapter
alone, so it is fair to ask whether that decision survives its own success.

It does, because of how the artifacts are scoped, and this is worth writing down rather than
assuming:

- **`facets.json`: zero new bytes.** Machine-ingested claims never appear individually. They affect
  three integers already in the record -- `claim_count`, `verification_max`,
  `condition_completeness_max` -- and the last two are deliberately *maxima*, so a heap of thin
  ingested claims cannot inflate them.
- **`corpus.json`: zero new bytes.** [08-infrastructure-and-build.md](08-infrastructure-and-build.md)
  §4.2 defines it as every published field of every entity **except claim-level detail**. The
  measurement it was made against therefore stands. (Note in passing: 08 and 10 call the slim
  artifact `facets.json` while 04 and 05 call it `index.json`. 08 owns build artifacts; the other
  two should be corrected.)
- **Static pages: bounded by decision, not by luck.** We do **not** generate 6,598 claim pages. A
  benchmark's claims render inside its own page, with `_ingested` claims in a collapsed, paginated
  table behind a `<details>`. At Epoch's distribution -- mean 82.5 rows per benchmark, largest
  `gpqa_diamond.csv` at 313 -- the worst single page carries ~313 rows of a compact table, which is
  well inside the 60 KB HTML budget [10-visualization.md](10-visualization.md) sets for V6 Detail.
- **`index.sqlite`: +2.5--3.0 MB**, on the order of 6,598 × ~450 bytes of normalised claim and
  conditions rows. It never ships to a browser; it is a build-time analytics store and a release
  download.
- **Attribution is interned by construction.** The 300-byte Epoch citation string lives once, in the
  `IngestBatch` record ([04-data-model.md](04-data-model.md) §9), not 6,598 times. Storing it
  per-record would have added ~2 MB of pure repetition -- which is the mistake this observation
  exists to prevent, not one we are making.

**Add a build-time budget assertion** so this stays true rather than being true today:
`bench build` fails if `corpus.json` exceeds 1.5 MB brotli or `facets.json` exceeds 150 KB gzipped
(the sharding triggers 08 §4.1 already defines), and additionally prints the ingested-claim count
and the largest generated page in the build manifest so a regression is visible in the diff.

### 11.5 Build order

1. **Epoch** -- local, CC-BY, static, ETag-conditional. A single script (§11.3), ~80 mapping
   stanzas, all 21 orphans hand-mapped. Everything else is calibrated against what this one teaches.
2. **HuggingFace Hub** -- best discovery surface in existence, API-shaped rather than bundle-shaped,
   and the `test:*` / `judge:*` / `submission:*` / `eval:*` tag taxonomy imports into our conditions
   crosswalk (`taxonomy/crosswalks/hf-tags.yaml`) rather than being invented. Treat the tags as
   hints with a provenance stamp: only **12.8%** of sampled leaderboard Spaces carry `test:*`
   ([06-sourcing-and-scraping.md](06-sourcing-and-scraping.md) §3.2 owns the census and the counts
   behind it; an earlier draft here said 11%, which was a mis-transcription).
3. **Extract the `Adapter` ABC here**, with adapters #1 and #2 refactored onto it, plus the one-hour
   spike in §12 on whether a form payload can substitute for a fetched one.
4. **GitHub metadata + shallow clones** of `lm-evaluation-harness` (227 task directories of YAML
   with `num_fewshot`, `output_type`, `metric_list`) and `embeddings-benchmark/results` (CC0). This
   is where `comparability_key` gets real values instead of nulls.
5. **arXiv OAI-PMH + LLM triage** -- accept ~60% precision from heuristics and pay ~$50/year for a
   classifier to reach ~85--90%.
6. **Grand Challenge** -- 264 medical-imaging challenges with publication links, from one clean REST
   endpoint. The cheapest route to non-LLM domain breadth in the entire catalogue, and it lands in
   one of the six domain families Epoch does not touch at all.

Everything after that is [06-sourcing-and-scraping.md](06-sourcing-and-scraping.md)'s Tier 2, and
each of those adapters is 30--100 lines once this contract exists.

---

## 12. What this document does not settle

Three of these previously appeared here as surveys with no recommendation, against this document's
own framing. All now carry a pick.

- **The Papers with Code archive licence.** `pwc-archive/*` on HuggingFace is **CC-BY-SA-4.0**
  `[recon 2026-09-17, measured]`, and ShareAlike is viral. Ingesting its `evaluation-tables` (2.25k
  rows) into a CC-BY core is the single largest legal risk in the ingestion strategy.
  **Recommendation: quarantine in `vendor/pwc-archive/keys/` with its own LICENSE, use it as a
  reconciliation key only, re-derive descriptions from primary sources before promotion.** The
  licence firewall in [04-data-model.md](04-data-model.md) §9 encodes it and the §8 gate enforces
  it. **Decide before first ingest, not at launch.**
- **The HELM GCS data licence is unverified.** The code is Apache-2.0; the bucket's data carries no
  visible licence, and public readability is permission to read, not to redistribute.
  **Recommendation: email `crfm-help@stanford.edu` and get it in writing; until then set
  `raw_retainable = False` on the HELM adapter and store only derived structured facts plus a
  link.** The `run_specs.json` eval conditions are arguably uncopyrightable facts, but "arguably" is
  not a foundation for a trust-based index.
- **Whether conflict edges should ever link across *sources* for the same underlying run** -- the
  ARC Prize duplicate-spelling case. **Recommendation: report-only, and §7.1 now implements that.**
  A cross-source link asserts that two rows describe the same run, which is an identity judgement,
  and the index's signature behaviour is declining to make exactly that kind of call without
  evidence. The near-duplicate signature surfaces the candidates; a human writes the alias entry or
  does not.
- **Whether the issue-form contribution path can reuse this contract.**
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §6 owns the path; the dependency
  runs the other way. **The concrete assumption to test: a `FormPayload` can substitute for
  `Payload` in `normalise()`, because `normalise()` takes no network and no clock, so a
  human-submitted form is just another payload shape.** If it holds, the validation bot reuses the
  gates, the resolver and the PR generator for free. **Assigned as a one-hour spike before the ABC
  is extracted** (step 3 of §11.5), because discovering it after the contract hardens means either a
  second pipeline or a refactor.
- **Three schema additions this document proposes and 04 must ratify**, all small and all
  batch-or-record scoped rather than requiring a mass rewrite: `IngestBatch.resolver_snapshot_sha256`
  (§1.3), `ingestion.last_seen_upstream` (§7.3), and the stable form of `ingestion.source_record_id`
  (§1.4). None of the three changes an existing field's meaning. **They are due a decision before the
  first adapter run, and a proposal that lives only in the document proposing it is a proposal that
  gets lost** — so each one belongs in `04` §15's pre-ingest list or in
  [15-open-questions.md](15-open-questions.md)'s register with an owner and a phase, and this
  document tracks nothing on their behalf.
- **Three naming conflicts this document surfaced, now adjudicated, recorded here only so the
  reasoning is not lost.** They are settled in the owning documents and this list is not a second
  record of the truth — an earlier revision carried them as a standing "found and did not fix"
  register, which survived two revision passes and became exactly that.
  - `IngestBatch` file path: **`data/_ingest/batches/<id>.yaml`**, because
    [04-data-model.md](04-data-model.md) owns the entity and a file path is part of an entity's
    identity. The `ingest/manifests/…` and `data/_ingest/epoch-<date>/…` spellings are retired.
  - The slim build artifact is **`facets.json`**, because
    [08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2 owns everything the build
    writes. `index.json` is retired.
  - Claim ids are the content-derived **`claim-<12 hex>`** form from
    [05-repository-and-workflow.md](05-repository-and-workflow.md) §2, which this document's dedup
    and identity machinery depends on; the sequential `claim-NNNNN` form is retired.
