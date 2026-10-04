# The adoption gate's instruments

- **Task:** P8-S1-T01 (13-execution-runners.md §0.2; the conditions are 14-roadmap.md's)
- **Recorded:** 2026-09-29. Every query below was run on that date; the results quoted are that
  day's, and they are a smoke test of the instrument, not a measurement.
- **Status:** the keys exist and work. The quarterly measurements themselves are
  `docs/adoption/YYYY-QN.md`, twice inside the six-month window after public v1, each carrying the
  raw query output and the date it was run (13 §0.2, "Measurement discipline").

> If a condition cannot be measured, it counts as failed. An unmeasurable gate is an open gate. (13 §0.2)

## The secrets

| Secret | Service | Acquired | Limit | Where it is held |
| --- | --- | --- | --- | --- |
| `OPENALEX_API_KEY` | OpenAlex (metered, key required since about 2026-02-13) | 2026-09-29 | metered per key | Windows Credential Manager (`uaibi`); repository Actions secret: **to set** |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar Academic Graph | 2026-09-29 | 1 request per second, across all endpoints | Windows Credential Manager (`uaibi`); repository Actions secret: **to set** |

Neither key is needed for conditions (1) and (3), which read this repository, or for DataCite,
which needs no key.

**The OpenAlex allowance, measured with the key on 2026-10-04** (P4-S2-T06; 06 §3.10 had three
conflicting figures): `X-RateLimit-Limit` 10,000 credits a day, `X-RateLimit-Limit-USD` 1. A singleton
lookup by id cost 0; a filtered list call and a search call each cost 10 credits ($0.001), so search is
not dearer than a list. That is about 1,000 list or search calls a day, beside free id lookups. Every
`bench ingest openalex` run reports the `X-RateLimit-*` headers it last saw, so a change in the meter
shows up on the next run.

The task's verification names the repository `<org>/uaibi`; the repository is `benchmarkg/benchmarks`:

```
gh secret list --repo benchmarkg/benchmarks | grep -E '^(OPENALEX|SEMANTIC_SCHOLAR)_API_KEY'
```

## The DOIs

A citation can name the concept DOI or a version DOI, so condition (2) queries every one of them.

| | DOI |
| --- | --- |
| Concept | `10.5281/zenodo.23045827` |
| v0.1.0 | `10.5281/zenodo.23045828` |

`docs/releasing.md` lists each new version's DOI; add it to the table above when it is minted.

## Condition (1): at least 3 external contributors landed data through the issue form

**Instrument.** The pull requests the intake bot opens are labelled `source:issue-form`, and the
contributor is credited in a `Co-authored-by:` trailer on the commit (05 §6, steps 3 and 5), so the
contributor is in the trailer, not the PR author (the bot).

```
gh pr list --repo benchmarkg/benchmarks --state merged --label source:issue-form --limit 1000 \
  --json number,mergeCommit --jq '.[].mergeCommit.oid' |
while read sha; do
  git log -1 --format='%(trailers:key=Co-authored-by,valueonly)' "$sha"
done | sed '/^$/d' | sort -u
```

**What counts.** Each distinct contributor once. Remove every account that holds commit rights on
the day of the measurement, and every maintainer or alt account:

```
gh api repos/benchmarkg/benchmarks/collaborators --jq '.[].login'
```

On 2026-09-29 those were `tatra-labs`, `advancedintelligence`, `intelligence-benchmark` and
`uaibi-bot`. The co-author trailers the maintainers put on their own commits
(`advancedintelligence`, `tatra-labs`) are not issue-form contributions and are excluded by the
label filter as well as by this list.

**2026-09-29:** the query returns no pull requests: neither the intake bot (P2-S6) nor the `source:issue-form` label exists yet.

## Condition (2): at least 1 external publication cites the Zenodo DOI

Three instruments, all run for every DOI in the table above. A citing work by a maintainer does not
count (self-citation).

**OpenAlex.** Resolve the DOI to an OpenAlex work, then count the works that cite it.

```
GET https://api.openalex.org/works/doi:10.5281/zenodo.23045827?api_key=$OPENALEX_API_KEY
    -> "id": "https://openalex.org/W..."
GET https://api.openalex.org/works?filter=cites:W...&per_page=200&api_key=$OPENALEX_API_KEY
    -> meta.count, results[].authorships (for the self-citation check)
```

**DataCite.** A Zenodo DOI is a DataCite DOI, and DataCite counts citations of it from reference
links, including the reference lists that Crossref members deposit.

```
GET https://api.datacite.org/dois/10.5281/zenodo.23045827
    -> data.attributes.citationCount, data.relationships.citations.data[] (the citing DOIs)
```

**Semantic Scholar.** One request per second.

```
GET https://api.semanticscholar.org/graph/v1/paper/DOI:10.5281/zenodo.23045827/citations?fields=title,authors,externalIds&limit=1000
    header x-api-key: $SEMANTIC_SCHOLAR_API_KEY
```

**Correction to 13 §0.2: the Crossref query does not exist.** The plan names Crossref
`works?filter=reference.doi:<release DOI>`. On 2026-09-29 Crossref answered it with HTTP 400,
`filter-not-available`, for our DOIs and for a control DOI alike: its public API has no filter on
a work's references, and its cited-by service is for Crossref members only. DataCite above replaces
it. It is the registry of record for a Zenodo DOI, and its citation links take in the Crossref
reference lists the plan's query was reaching for. 13 §0.2 should say so; this file is where the
instrument stands until it does.

**2026-09-29, the smoke test:**

| Instrument | Our DOIs | Control | Reading |
| --- | --- | --- | --- |
| OpenAlex | HTTP 404, both | `10.48550/arXiv.2310.06770` (SWE-bench) resolves to `W4387561453`, and `cites:` counts 54 | The query works; OpenAlex has not indexed a DOI minted today |
| DataCite | both `findable`, `citationCount` 0 | The most-cited Zenodo DOI, `10.5281/zenodo.10680266`, reads 9,576 | The query works; nothing cites us yet |
| Semantic Scholar | HTTP 404 "Paper … not found", both | `arXiv:2310.06770` returns its record, 3,976 citations | The key works. Semantic Scholar indexes papers and may never index a dataset DOI; if it has not by the first measurement, this instrument records **not indexed**, never zero |
| Crossref | HTTP 400 `filter-not-available` | the same | The plan's query cannot be run; see the correction above |

## Condition (3): at least 5 unsolicited rerun or verification requests

**Instrument.** Triage labels each rerun or verification request `request:rerun`; a request that
arrives by e-mail is transcribed into an issue first, so the count has one home.

```
gh issue list --repo benchmarkg/benchmarks --label request:rerun --state all --limit 1000 \
  --json number,author,createdAt,title
```

**What counts.** Only unsolicited requests: the requester opened the issue unprompted. One that
answers a call for requests does not count ("a gate you can generate demand for is not a gate").
Unsolicited is a triage judgement, so the triager records it on the issue when applying the label,
and the measurement copies each counted issue's number into its raw output.

**2026-09-29:** the `request:rerun` label does not exist yet; the query returns nothing.
