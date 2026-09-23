# 17 -- Packages and SDK

The catalogue described in [00-vision-and-scope.md](00-vision-and-scope.md) through
[16-execution-plan.md](16-execution-plan.md) is a website and a git repository. This document
decides the third surface: **an installable package** that puts the same data and the same
refusals inside someone else's program.

It exists because the audiences in [00-vision-and-scope.md](00-vision-and-scope.md) §3 do not
work in a browser. An AI engineer choosing an evaluation suite is in a terminal or a notebook; a
researcher assembling a comparison is writing a script; an agent answering "which benchmarks test
long-horizon tool use in robotics" is calling a tool, not scrolling a page. A catalogue reachable
only through HTML is a catalogue those three read once and never integrate.

**The governing rule is that the package is the same object as the site.** Both are built from the
YAML at a commit; both carry the same `comparability_key`; both refuse to rank claims whose
conditions differ. If the package would answer a question differently from the website, the
package is wrong. This is not a style preference -- it is what makes the citation in a paper and
the call in a script refer to the same thing.

---

## 1. What the package is, and what it is not

**It is a client for a published dataset.** The catalogue's build artifacts
([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.2) are already static JSON
and SQLite under a versioned URL namespace. The package fetches them, caches them, and gives them
types, query methods and the comparability logic. Everything it knows, a determined user could
get with `curl` and `jq`; the package exists so they do not have to, and so that the
comparability rules travel with the data instead of being re-implemented, differently, by every
consumer.

**It is not a second source of truth.** The package holds no benchmark facts of its own. It ships
no bundled snapshot of the corpus beyond a small offline fixture for its own tests. A pinned
package version resolves to a pinned *data* version, and the two are stated separately, because
a bug fix in the client must not look like a change in the data.

**It is not a wrapper around a service we operate.** Its default mode reads static artifacts over
HTTPS from the CDN that already serves the site. The hosted API in
[18-api-and-submissions.md](18-api-and-submissions.md) is an *additional* transport, not a
dependency: the package works with the API unreachable, and says so rather than failing.

### 1.1 The three package artifacts

| Artifact | Registry | What it is |
| --- | --- | --- |
| `benchindex` | PyPI | The library and the `bench` CLI. The primary surface, because Python is where the stated audiences already are |
| `benchindex-mcp` | PyPI | The MCP server, shipped separately so that installing the library does not pull in a server stack, and so the server can version independently of the client |
| `bench` | Homebrew / uv tool | A thin distribution convenience over the same wheel, for people who want the CLI without a project virtualenv |

**A JavaScript client is deliberately not in this list.**
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4 already generates TypeScript
types from the Pydantic models and commits them, so a TypeScript consumer has the *types* today
and can fetch the same static JSON in ten lines. Publishing and maintaining a second client
doubles the surface on which the package and the site can disagree, and the audience that would
use it -- web developers embedding the catalogue -- is not one of the three this project is
for. *Risk: if an embedding ecosystem does appear, this decision has to be revisited, and the
generated types mean the cost of reversing it is a client, not a redesign.*

---

## 2. The public API surface

The hardest decision in a package is not what it does; it is what it promises. Everything named
in this section is covered by the versioning policy in §4. Everything not named in it is private
and may change in a patch release, whatever its visibility in Python.

### 2.1 Reading the catalogue

```python
from benchindex import Index

idx = Index()                          # latest published release
idx = Index(version="2027.3.1")        # a pinned data release
idx = Index(commit="a1b2c3d")          # the citable thing: YAML at a commit
idx = Index(path="./my-fork")          # a local checkout or a fork

bench = idx.benchmark("swe-bench")
bench.domain, bench.capabilities, bench.lifecycle
bench.conditions_material                # which fields matter for THIS benchmark
bench.claims()                           # ResultClaims, each with its EvalConditions
```

`Index()` with no argument resolves the latest release and caches it under the platform cache
directory. **The resolution is recorded, not silent**: `idx.provenance` returns the data version,
the commit, the artifact hashes and the fetch time, and every object carries a back-reference to
it. A number that reaches a paper must be able to say where it came from without the author
having to remember.

### 2.2 Search and facets

```python
idx.search(domain="robotics-embodiment", capability="long-horizon-planning")
idx.search(text="protein structure", lifecycle="active")
idx.facets()                             # the eight vocabularies, as enums
```

Facet values are typed enums generated from `taxonomy/*.yaml`, so a misspelled capability is an
error at call time rather than an empty result set. This matters more than it looks: the common
failure of a faceted API is that a typo returns zero rows and the caller concludes the catalogue
is empty.

### 2.3 Comparison, and the refusals

This is the part that justifies the package existing at all.

```python
a, b = idx.claim("claim-a"), idx.claim("claim-b")
idx.comparable(a, b)      # -> Comparable | Incomparable(reason, differing_fields)
idx.compare([a, b, c])    # -> groups by comparability_key, never one ranking
```

`comparable()` returns a value, never a bare boolean, and the `Incomparable` case names which
material fields differ. The six categorical refusals in
[10-visualization.md](10-visualization.md) §"the generic key" are enforced here, not just in the
UI: a pool-relative rating compared across snapshots, a reliability metric averaged across `k`, a
vector-valued result collapsed to a scalar, two leaderboards with different legality rules,
different training-data eligibility tiers, and unresolved ground truth.

**`compare()` has no `force=True`.** There is no argument that makes it return a ranking across a
key boundary. A caller who wants to ignore the refusal can read the claims and sort them
themselves, and will have written that decision down in their own code, where a reviewer can see
it. *Risk: some users will do exactly that and publish the result. The package cannot prevent
it; what it can do is refuse to be the thing that is cited for it.*

### 2.4 Suite assembly

```python
suite = idx.suite(need="agentic coding, long-horizon, public test set")
suite.benchmarks, suite.rationale, suite.recommended_conditions
suite.export("manifest.yaml")
```

Deterministic selection over the facets, as in
[11-ai-features.md](11-ai-features.md) §"suite assembly". The AI layer, where it is enabled, only
annotates a set that this code selected. The package's default is the deterministic path with no
model call and no network beyond the artifact fetch.

### 2.5 The CLI

The CLI is the same API with a terminal in front of it, and its surface is the one declared in
[05-repository-and-workflow.md](05-repository-and-workflow.md) §3 -- that block remains the only
specification, and this document adds to it rather than inventing beside it.

```
bench search --domain robotics-embodiment --capability long-horizon-planning
bench show swe-bench --format json
bench compare claim-a claim-b
bench suite --need "agentic coding" --export manifest.yaml
bench run swe-bench --model <id> --out runs/        # see 13-execution-runners.md
bench submit runs/2027-03-14.json                   # see 18-api-and-submissions.md
```

**Two commands are new to the public CLI and one is a rename.** `bench run` and `bench submit`
arrive with the runner and the submission path respectively. The repository-maintenance
subcommands that [05-repository-and-workflow.md](05-repository-and-workflow.md) §3 declares --
`validate`, `promote`, `migrate`, `ingest`, `release` and the rest -- stay in the wheel but are
hidden from `bench --help` unless the working directory is a catalogue checkout. A contributor
needs them; someone who ran `pip install` to look up a benchmark should not have to read past
them.

---

## 3. The offline and air-gapped story

A researcher on a cluster without egress is a real case, and it is the case where a catalogue
that silently degrades does the most damage.

- `Index(path=...)` reads a local checkout with no network at all.
- `bench cache warm` fetches every artifact for a pinned version and reports its total size.
- With the cache cold and the network unreachable, `Index()` **raises** with the URL it could not
  reach and the `bench cache warm` command that would fix it. It does not fall back to a stale
  cache silently, and it does not return an empty catalogue.
- `idx.provenance.stale_by` exposes the age of the cached data so a caller can decide.

*Risk: raising rather than degrading will annoy someone whose CI has flaky egress. That is the
intended trade. The alternative failure -- a script that quietly compares against a nine-month-old
corpus and publishes the number -- is the one this project exists to prevent.*

---

## 4. Versioning, and the two version numbers

The package and the data version independently, and conflating them is the mistake this section
exists to prevent.

| | Scheme | Meaning of a change |
| --- | --- | --- |
| **Package** | SemVer (`1.4.2`) | Major: a documented API in §2 changed or was removed. Minor: new capability, nothing removed. Patch: bug fix, no API change |
| **Data** | Calendar (`2027.3.1`) | A catalogue release. Content changes; the schema may add fields, and never removes one without a migration and an ADR ([04-data-model.md](04-data-model.md) §12) |

`benchindex.__version__` and `idx.provenance.data_version` are separate values and both appear in
`bench --version`. A citation needs the data version and the commit; a bug report needs the
package version.

**Compatibility runs one way.** A package release declares the minimum data-schema version it
understands and refuses, loudly, to read anything older. Reading *newer* data is allowed and
unknown fields are preserved but not typed, so a catalogue release does not brick every installed
client the day it ships. The alternative -- pinning the client to an exact schema -- produces the
failure where nobody upgrades the data because it would break their scripts.

**Deprecation.** A public API removal needs one minor release emitting `DeprecationWarning` with
the replacement named, then removal in the next major. Anything shipped without that sequence is
a bug, not a decision.

---

## 5. The MCP server

The stated audience includes agents, and an agent is a first-class consumer rather than a novelty:
"find me benchmarks for X" and "are these two numbers comparable" are exactly the questions the
catalogue answers and exactly the questions an agent gets wrong when it answers them from its own
weights.

`benchindex-mcp` exposes a small, deliberately un-clever tool set:

| Tool | Returns |
| --- | --- |
| `find_benchmarks` | Facet-filtered benchmark list with ids, names and one-line descriptions |
| `get_benchmark` | One benchmark's full record, including which conditions are material to it |
| `get_claims` | Result claims for a benchmark, each with its conditions and verification rung |
| `check_comparable` | The `Comparable` / `Incomparable` verdict, with the differing fields named |
| `assemble_suite` | A deterministic suite for a stated need, with its rationale |

**The server returns data, never prose conclusions.** It does not have a `which_model_is_best`
tool, and `check_comparable` returns a verdict with its reasons rather than a recommendation. The
rule from [11-ai-features.md](11-ai-features.md) -- the AI layer is a lens and never a source --
applies with more force here, because the caller is a model that will present whatever it gets as
fact.

Every tool result carries the data version and commit in its payload, so an agent that quotes a
number has the provenance available to quote with it. *Risk: it will often not quote it. Carrying
it is still the difference between an unattributed number and an unattributable one.*

---

## 6. Repository layout and the packaging boundary

[05-repository-and-workflow.md](05-repository-and-workflow.md) §2 owns the repository layout. The
package does not get a second repository -- a split repo means the client and the artifacts drift,
which is the failure this whole corpus is organised against. It gets a directory and a build
target:

```
packages/
  benchindex/            the library and CLI wheel
    src/benchindex/
      index.py           Index, resolution, caching, provenance
      models.py          re-exported from schema/, never redefined
      compare.py         comparability + the six refusals
      suite.py           deterministic assembly
      runner/            local evaluation (13-execution-runners.md)
      cli/               the public subcommands
    tests/
  benchindex-mcp/        the MCP server wheel
```

**`models.py` re-exports the canonical Pydantic models from `schema/`; it never redefines them.**
A second definition of `Benchmark` is the same defect as a second copy of a number in the prose,
and it fails the same way. CI asserts that every public model in the package is the identical
object from `schema/`.

The wheel ships no data. It ships the generated JSON Schema for validation and a fixture corpus
of about twenty entries for its own tests, which is also what makes `Index(path=...)` testable
without a network.

---

## 7. Release and supply chain

Releases are cut from a tag by CI, never from a laptop, using PyPI **Trusted Publishing** so no
long-lived token exists to leak. Wheels are built reproducibly and their hashes recorded in the
release notes alongside the data-release hashes that
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §"build manifest" already emits.

The package is signed, attested with provenance, and its dependency set is kept deliberately
small: `pydantic`, `httpx`, `pyyaml`, and `platformdirs` for the cache. **The CLI's pretty output
is optional.** A dependency that only makes a table look nicer is a dependency that can break an
install on a cluster, and the plain output path is the one CI tests.

*Risk, stated plainly: a package is a supply-chain artifact and this project is small. If
maintenance lapses, an abandoned package with a stale pin is worse than no package, because it
keeps answering. `SUCCESSION.md` ([05-repository-and-workflow.md](05-repository-and-workflow.md)
§"succession") gains a package clause: the dormancy trigger yanks nothing, but it publishes a
final release whose import emits a warning naming the last date the data was verified.*

---

## 8. What the package deliberately does not do

- **It does not host or mirror benchmark data.** The metadata-only invariant in
  [00-vision-and-scope.md](00-vision-and-scope.md) §"Not a dataset host" applies unchanged.
  `bench run` fetches a benchmark's data from that benchmark's own distribution, under that
  benchmark's own licence, to the user's own disk.
- **It does not compute a universal score**, and has no API that could be mistaken for one.
- **It does not author benchmarks.** Suite assembly selects from what exists.
- **It does not phone home.** No telemetry, no usage beacon, no anonymous statistics. Adoption is
  measured from registry download counts and from citations, which are public, coarse and
  sufficient.
- **It does not require an account.** Reading the catalogue needs no key. Submission
  ([18-api-and-submissions.md](18-api-and-submissions.md)) needs an identity; reading never does.

---

## 9. Open questions carried forward

These go to [15-open-questions.md](15-open-questions.md) with a recommendation, so nothing here
blocks starting.

| Question | Recommendation |
| --- | --- |
| Package name on PyPI -- is `benchindex` available, and does it collide with the project name chosen in [15-open-questions.md](15-open-questions.md)? | Reserve the name at the same time as the domain, before Phase 0 ends. Availability across PyPI, npm and GitHub is already a stated input to the naming decision |
| Does the CLI ship the maintenance subcommands to every user, or only inside a checkout? | Hide them outside a checkout, as §2.5 says. Revisit if contributors report friction |
| Minimum supported Python | 3.11, one below the 3.12 the repository pins, so a consumer on an older cluster image is not excluded |
| Does the MCP server get its own release cadence? | Yes, separate wheel and separate version. It will change with the MCP spec, which moves faster than the catalogue |
