# 18 -- API and submissions

Two surfaces that both change the project's shape, and for the same reason: they are the first
places where someone who is not a maintainer writes to, or leans on, the catalogue.

[17-packages-and-sdk.md](17-packages-and-sdk.md) covers the read path that needs nothing from us
at runtime -- static artifacts on a CDN, a package that fetches them. This document covers the two
that do: **a queryable hosted API**, and **a path by which an outsider's own result becomes a
claim in the index**.

Both are additive. The catalogue in [00-vision-and-scope.md](00-vision-and-scope.md) works with
neither, and must keep working if either is withdrawn. That is not a hedge; it is the constraint
that decides most of what follows.

---

## 1. Why a hosted API at all

The honest case against it first. The build artifacts are already public, versioned, immutable
JSON on a CDN. `facets.json` is about 36 KB at launch scale
([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4.1); a consumer who wants "all
active robotics benchmarks" can fetch it and filter in a loop. An API that answers the same
question is a service we now have to run, rate-limit, version, monitor and pay for, in a project
whose hosting model is deliberately zero-budget and whose bus factor is one.

The case for it is three queries the static artifacts genuinely cannot serve well:

1. **Joins across artifacts.** "Benchmarks in chemistry with at least one claim above 0.9 whose
   conditions include a reported temperature" touches `facets.json`, `corpus.json` and
   `claims.json` and is a query, not a filter. Making every consumer download and join three
   artifacts to ask it is a worse answer than answering it.
2. **Point lookups from constrained clients.** An agent, a notebook on a metered connection, or a
   CI job that wants one benchmark should not pull 1.7 MB of `corpus.json`.
3. **Freshness between releases.** Artifacts are cut per release. The corrections feed and
   liveness signals move continuously, and a consumer who cares about "is this benchmark still
   maintained" wants the current answer.

**So the API is a query layer over the same artifacts, and never a second database.** It reads
what the build produced. It holds no state that the git repository does not hold, with one
exception named in §4: the submission queue, which is explicitly a queue and not a source of
truth.

---

## 2. What the API is

### 2.1 Shape

**REST for retrieval, GraphQL for the joins.** Not either-or, and the split is not fashion:

- REST is the surface most consumers and every agent framework already speak, it caches at the
  CDN edge by URL, and it degrades to "fetch the static artifact" in the obvious way.
- GraphQL exists for query 1 above, where the alternative is inventing a filter dialect in REST
  query parameters and then maintaining it. It is **read-only, depth-limited and cost-limited**;
  a query that would fan out past the limit is rejected with the cost it would have incurred, not
  truncated silently.

```
GET  /api/v1/benchmarks?domain=chemistry-materials&lifecycle=active
GET  /api/v1/benchmarks/{id}
GET  /api/v1/benchmarks/{id}/claims
GET  /api/v1/claims/{id}
GET  /api/v1/compare?a={claim}&b={claim}     -> the same verdict the package returns
GET  /api/v1/taxonomy/{facet}
POST /api/graphql                            -> read-only, cost-limited
```

`/api/v1/compare` matters more than its size suggests. It is the one endpoint whose answer is a
*judgement* rather than a record, and putting it behind the same code path as the package and the
site is what stops three implementations of the comparability rule drifting apart.

### 2.2 Versioning and deprecation

`/api/v1/` is in the path, and v1 means the shape of the response, not the data version. Every
response carries the data version, the commit and the artifact hashes in a `provenance` object --
the same values [17-packages-and-sdk.md](17-packages-and-sdk.md) §2.1 exposes -- so a consumer can
always tell what it was answered from.

An endpoint is removed only after a **twelve-month** deprecation window announced in the release
feed and in a `Deprecation` header on every response. Twelve months is long for a small project,
and it is chosen deliberately: an API that breaks consumers is worse for the project's credibility
than no API, because the people it breaks are exactly the integrators the catalogue needs.

### 2.3 Limits, and what happens at them

| | Anonymous | With a free key |
| --- | --- | --- |
| Rate | 60 req/min, 10k/day | 600 req/min, 200k/day |
| GraphQL cost | 1,000 points/query | 5,000 points/query |
| Burst | Token bucket, 120 | Token bucket, 1,200 |

Over the limit returns `429` with `Retry-After` and a body naming the static artifact that answers
the same question without a limit. **The bulk path is always free and always unlimited**, because
it is a file on a CDN; the API's limits exist to stop one consumer's loop making the service
unavailable for everyone, not to meter access to the data. Anyone who finds the limits binding is
told, in the error body, to stop using the API and download the artifact.

A key is free, self-serve, and requires an email only so that a runaway client can be contacted
before it is blocked.

### 2.4 Cost, honestly

This is the part that changes the project's economics, and
[08-infrastructure-and-build.md](08-infrastructure-and-build.md) §"cost model" currently assumes a
static site with no origin.

The API runs as an edge worker over the same artifacts, with the SQLite index
([08-infrastructure-and-build.md](08-infrastructure-and-build.md) §4) attached as a read replica.
That keeps it inside a free or near-free tier at launch volumes and means there is no server to
patch. **The cost risk is not the steady state; it is a single misbehaving client or a scraper.**
Hence the limits above, a hard monthly spend cap with the same degrade-rather-than-bill behaviour
as the AI layer's cap in [11-ai-features.md](11-ai-features.md) §"G5", and a documented decision
that when the cap is hit the API returns `503` with a pointer to the artifacts **rather than
incurring the charge**.

*Risk, stated plainly: this is the first component with a recurring bill and an uptime
expectation, in a project whose survivability argument
([05-repository-and-workflow.md](05-repository-and-workflow.md) §"succession") rests on everything
being reconstructible from a git checkout. The mitigation is the one property that must never be
given up: **the API is the only component whose disappearance costs nothing but convenience.** If
it goes away, the package still works, the site still works, and the data is still citable. Any
proposal that makes the API load-bearing for any of those three should be refused on that
ground alone.*

---

## 3. Why submissions, and the shape of the risk

The catalogue's claims today come from two places: maintainers curating primary sources, and bulk
ingestion from upstreams that already do that work
([06-sourcing-and-scraping.md](06-sourcing-and-scraping.md)). Both scale with maintainer hours,
which is the binding constraint the whole roadmap is organised around.

Submissions are the only mechanism that scales with *interest* instead. Someone who ran a model
against a benchmark has a result, its conditions and its transcript already in hand; the marginal
cost of contributing it is small, and the marginal cost to us of receiving it is a review.

**And it is the single largest integrity risk the project takes on.** A catalogue whose numbers
anyone can add is a leaderboard, and leaderboards get gamed: by selective reporting, by
contaminated evaluation, by conditions quietly tuned until the number improves, and by people who
simply make it up. [01-landscape-and-positioning.md](01-landscape-and-positioning.md) is a
document about projects that died; a project that publishes a fabricated number and is caught does
not die slowly.

So the design below is not "an upload form". It is the existing verification ladder
([04-data-model.md](04-data-model.md) §7) with a new entry point, and the default answer to a
submission is **not "published"**.

---

## 4. The submission path

### 4.1 The one rule

**A submission is a proposed change to the repository, and it enters through the same door a
maintainer's change does.** There is no write path to published data that bypasses review. The
API accepts a submission, validates it, and opens a draft pull request; it does not write to
`data/`. The queue holds submissions in flight and nothing else, and losing the queue entirely
loses no published claim.

This is what makes the API non-load-bearing in the sense §2.4 requires. Git remains the source of
truth; the submission surface is a convenience over `git commit`.

### 4.2 What a submission contains

```
bench submit runs/2027-03-14-swe-bench.json
```

A `RunRecord` as produced by the local runner
([13-execution-runners.md](13-execution-runners.md)), carrying:

| Field | Why it is mandatory |
| --- | --- |
| `benchmark_id`, `metric_id` | Which number this is, in the catalogue's own vocabulary |
| `EvalConditions`, complete | A claim whose conditions are unknown cannot be compared with anything, so it would be published as an island. The submitter knows their conditions; nobody else can recover them |
| `system` identity and version | Including the provider snapshot, because "GPT-5" in March and in September are different subjects |
| `transcript_url` or attached artifact | The evidence. Without it the claim can never rise above the lowest verification rung |
| `runner_version`, `run_id`, environment digest | Reproducibility, and the thing that makes a contaminated or misconfigured batch identifiable after the fact |
| `submitter` identity | §4.4 |
| Contamination attestation | An explicit statement about training-data overlap, because the absence of the question is how contaminated numbers get published |

A submission missing any of these is rejected at the API with the field named. This is strict on
purpose: the fields are exactly what the runner already emits, so a submission produced by
`bench run` is complete by construction, and one assembled by hand has to do the work the runner
would have done.

### 4.3 What happens to it

1. **Schema and semantic validation**, the same four tiers as
   [04-data-model.md](04-data-model.md) -- at the API, synchronously, so the submitter gets the
   error immediately rather than in a review comment a week later.
2. **Automated checks**: does the transcript exist and does it hash to what the record claims;
   are the conditions internally consistent; does the number fall inside the metric's declared
   range; is it a near-duplicate of an existing claim; does it exceed the current SOTA by a margin
   that warrants a human look.
3. **A draft pull request** against a submissions branch, with the record, the checks' output and
   a filled review template.
4. **Review**, per the matrix in [05-repository-and-workflow.md](05-repository-and-workflow.md)
   §5. A claim that beats SOTA, or that comes from a first-time submitter, or that concerns a
   benchmark its own authors maintain, gets a stricter path.
5. **Merge, badged at the rung the evidence supports** -- and no higher. A self-reported result
   with a transcript is `self-reported-with-artifact`; it does not become
   `independent-reproduction` because it is well-formed.

### 4.4 Identity, and how much of it

Submissions require a GitHub identity, because the destination is a pull request and because an
account with history is a weak but real signal. It is not proof of anything, and the design does
not pretend otherwise: **the defence against a fabricated number is the transcript and the
conditions, not the identity of who sent it.**

What identity buys is accountability after the fact -- a claim can be traced, a pattern of bad
submissions can be blocked, and a correction can name who is being corrected. Every published
claim records its submitter, visibly. Anonymous submission is not offered; someone who wants to
contribute without attribution can open an issue and ask a maintainer to carry it, which puts the
maintainer's name on it instead, which is the correct allocation of responsibility.

### 4.5 Anti-gaming, concretely

| Attack | Defence |
| --- | --- |
| Fabricated number, no real run | Transcript is mandatory and is hash-checked; the record's environment digest and timing must be internally consistent |
| Contaminated evaluation | Mandatory attestation, plus the contamination signals [12-analytics-and-trends.md](12-analytics-and-trends.md) already computes; a benchmark released before a model's cutoff is flagged on the claim, permanently |
| Conditions tuned until the number improves | Conditions are part of the `comparability_key`, so a tuned run lands in a different comparison group rather than beating the original. This is the single most useful structural defence and it comes free from the existing design |
| Selective reporting -- submit the good run, discard the bad | `run_id` and the runner's batch id make a partial submission visible; the review template asks how many runs were performed. It is not fully defensible and is stated as such |
| Sybil submission at volume | Rate limits per identity, and a first-time submitter's claim always gets human review |
| Vendor submits about their own system | Recorded as a declared interest on the claim and rendered on the page. Not refused -- vendors often have the best conditions data -- but never hidden |

**The honest limit.** None of this makes a determined, competent faker impossible. What it does is
make faking expensive, make a fake identifiable after the fact, and ensure that when one is found
the correction path in [05-repository-and-workflow.md](05-repository-and-workflow.md)
§"corrections" already exists to publish it. A catalogue that claims its submissions are
unfakeable is making a claim it cannot support; this one claims they are *attributable*, which it
can.

### 4.6 What is never accepted

- A claim with no transcript and no primary-source link, at any rung.
- A benchmark's own data or test set, in any form -- the metadata-only invariant
  ([00-vision-and-scope.md](00-vision-and-scope.md) §"Not a dataset host") is unchanged.
- A new benchmark definition by API. Adding a benchmark is a taxonomy act with a classification
  judgement in it, and it goes through the issue-form path in
  [05-repository-and-workflow.md](05-repository-and-workflow.md) §6.
- Edits to another submitter's claim. Disagreement is a dispute
  ([05-repository-and-workflow.md](05-repository-and-workflow.md) §8), which renders both
  positions, rather than an overwrite.

---

## 5. What these two surfaces do not change

Stated because a widening is exactly when invariants get lost:

- **No universal score.** Neither surface exposes a ranking across a comparability boundary, and
  `/api/v1/compare` returns refusals as first-class values.
- **No hosted evaluation.** The runner in [13-execution-runners.md](13-execution-runners.md) runs
  on the submitter's machine, with the submitter's keys and the submitter's bill. We accept
  results; we do not produce them on demand for others.
- **No data hosting.** Unchanged.
- **Git is still the source of truth**, and the citable object is still the YAML at a commit.
- **Reading never requires an account.**

---

## 6. Open questions carried forward

| Question | Recommendation |
| --- | --- |
| Does GraphQL earn its maintenance, or would a richer REST filter grammar do? | Ship REST first and measure. Build GraphQL only if the join queries in §1 actually appear in logs; the endpoint is easy to add and hard to remove |
| Who reviews submissions at volume, when maintainer hours are the binding constraint? | The domain reviewer programme in [03-taxonomy-build-process.md](03-taxonomy-build-process.md) §12 is the natural pool, but it was scoped for taxonomy review, not claim review. If submission volume exceeds review capacity, submissions queue rather than auto-merge, and the backlog is published |
| Should a trusted-submitter tier exist that skips human review? | Not before there is evidence of a review bottleneck and a submitter with a clean record over a stated number of claims. Write the rule before granting the first one |
| What is the SLA, if any? | None, stated explicitly. Best-effort, with the static artifacts named as the supported path for anything that needs reliability |
