# Version pins and third-party limits

Every pin the plan names, checked against its registry or vendor page on the date in
`verified_on`. The plan's own values were checked on 2026-09-17
([14-roadmap.md](../_plan/14-roadmap.md) §"Version pins and third-party facts: as-of date");
this file is the Phase 0 re-check that block asks for, written by P0-S4-T01.

**How to read a row.** `pinned` is what the plan and `pyproject.toml` / `uv.lock` use.
`observed` is what the registry reported as current on `verified_on`. Where they differ the
status is **moved**, and the pin is *not* changed here: a moved pin is a decision for the
document that owns it (the `owner` column), which is where the reasoning lives. Registry values
come from the JSON APIs named in `source`, not from memory or a third-party tracker.

## Pins named by 14-roadmap and the P0-S4-T01 task

| pin | owner | pinned | observed | observed published | source | verified_on | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| python | 04 §12, 08 §5 | 3.12 (minor); env ran 3.12.12 | 3.12.14 newest patch; 3.12 is `security` phase, EOL 2028-10 | -- | python.org/ftp/python/ index; peps.python.org/api/release-cycle.json | 2026-09-23 | ok (minor); see note 1 |
| pydantic | 04 §12, 08 §5.6 | 2.13.5 | 2.13.5 | 2026-08-28 | pypi.org/pypi/pydantic/json | 2026-09-23 | ok |
| json-schema-to-typescript | 04 §12, 08 §5.6 | 16.0.0 | 16.0.0 | 2026-08-28 | registry.npmjs.org/json-schema-to-typescript | 2026-09-23 | ok |
| astro | 08 §5.1 | 7.3.3 | **7.3.4** | 2026-09-22 | registry.npmjs.org/astro | 2026-09-23 | **moved** (patch) |
| node | 08 §5.1 | >=22.12 | Astro 7.3.3 and 7.3.4 both declare `engines.node >=22.12.0`; newest v22 is v22.23.3 (maintenance LTS "Jod", EOL 2027-04-30); active LTS is v24.21.0 "Krypton" | 2026-09-23 (v22.23.3) | nodejs.org/dist/index.json; github.com/nodejs/Release schedule.json | 2026-09-23 | ok; see note 2 |
| pagefind | 08 §5.5 | 1.5.2 | 1.5.2 | 2026-04-12 | registry.npmjs.org/pagefind | 2026-09-23 | ok |
| echarts | 10 §Technology decisions | 6.1.0 | 6.1.0 | 2026-05-19 | registry.npmjs.org/echarts | 2026-09-23 | ok |
| sigma.js | 10 §Technology decisions | 3.0.3 | 3.0.3 (`beta` tag 4.0.0-beta.6) | 2026-04-30 | registry.npmjs.org/sigma | 2026-09-23 | ok |
| cosmos.gl | 10 §Technology decisions | 3.4.1 | **3.4.2** (`beta` tag 3.5.0-beta.2) | 2026-09-21 | registry.npmjs.org/@cosmos.gl/graph | 2026-09-23 | **moved** (patch) |
| scikit-learn | 04 §12, 08 §5.3 | 1.9.1 | 1.9.1 (`requires_python >=3.11`) | 2026-09-10 | pypi.org/pypi/scikit-learn/json | 2026-09-23 | ok |
| cloudflare-workers-free-tier | 08 §7.6 | 100,000 requests/day; 10 ms CPU/request | Free: "Requests 100,000/day", "CPU time 10 ms"; page "Last updated Sep 5, 2026" | 2026-09-05 | developers.cloudflare.com/workers/platform/limits/ | 2026-09-23 | ok |
| anthropic-tier-caps | 08 §7.6, 11 §5 | Start $500, Build $1,000, Scale $200,000 per month; Start 1,000 RPM and 2M ITPM | "Usage tier Monthly spend cap Start $500 USD Build $1,000 USD Scale $200,000 USD"; Custom has no cap; Start tier Opus 5.5 row: 1,000 RPM, 2,000,000 ITPM | -- | docs.anthropic.com/en/api/rate-limits | 2026-09-23 | ok; see note 3 |

## Pins the lockfile carries that the task did not name

| pin | owner | pinned | observed | observed published | source | verified_on | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| umap-learn | 08 §5.3 | 0.5.12 | 0.5.12 | 2026-04-08 | pypi.org/pypi/umap-learn/json | 2026-09-23 | ok |
| numba | 08 §5.3 ("pin exactly", no version given) | 0.67.0 | 0.67.0 | 2026-08-11 | pypi.org/pypi/numba/json | 2026-09-23 | ok (first pin) |
| numpy | 08 §5.3 ("pin exactly", no version given) | 2.5.3 | 2.5.3 (`requires_python >=3.12`) | 2026-09-06 | pypi.org/pypi/numpy/json | 2026-09-23 | ok (first pin); see note 4 |
| ruamel.yaml | 04 §12 (named, not versioned) | 0.19.1 | 0.19.1 | 2026-01-02 | pypi.org/pypi/ruamel.yaml/json | 2026-09-23 | ok (first pin) |
| pytest (dev group) | every `uv run pytest` verify, first P4-S4-T05 | 9.1.1 | 9.1.1 (`requires_python >=3.10`) | 2026-06-19 | pypi.org/pypi/pytest/json | 2026-09-24 | ok (first pin) |
| anthropic (`triage` extra) | 06 §5.2, 11 §5 (the SDK; named, not versioned) | 1.11.0 | **1.13.0** | 2026-10-09 | pypi.org/pypi/anthropic/json | 2026-10-10 | **moved** (first pin): 1.11.0, published 2026-09-30, over 1.13.0 and 1.12.x, each under three days old when pinned |
| pyarrow (`lmarena` extra, dev group) | 06 §3.6 (LMArena's parquet; named, not versioned) | 25.0.1 | **26.0.0** | 2026-10-09 | pypi.org/pypi/pyarrow/json | 2026-10-10 | **moved** (first pin): 25.0.1, published 2026-08-10, over 26.0.0, a day old when pinned |
| js-yaml (site) | P2-S3-T05: the term pages read taxonomy/*.yaml at build time (not named by the plan) | 4.3.2 | **5.4.3** | 2026-10-05 | registry.npmjs.org/js-yaml | 2026-10-12 | **moved** (first pin): 4.3.2 (published 2026-08-26) is the major astro 7.3.3 itself depends on (`^4.3.0`, for its file() loader), so the site and Astro parse with one installed copy; 5.x is a new major |
| uv | 05 §3 (named, not versioned) | 0.9.17 (installed here) | **0.12.18** | -- | pypi.org/pypi/uv/json | 2026-09-23 | **moved**; see note 1 |
| typer | 05 §3 (named, not versioned) | 0.27.2 | 0.27.2 | 2026-08-28 | pypi.org/pypi/typer/json | 2026-09-25 | ok (first pin, P0-S5-T01) |
| hatchling (build backend) | P0-S5-T01, for the `bench` entry point | 1.32.4 | 1.32.4 | -- | pypi.org/pypi/hatchling/json | 2026-09-25 | ok (first pin) |
| jsonschema | 04 §15 item 21, first P3-S1-T01: validating fixtures against schema/generated/; since P2-S3-T06 also the croissant extension schema inside `bench build`, so a runtime dependency | 4.26.0 | 4.26.0 (`requires_python >=3.10`) | 2026-01-07 | pypi.org/pypi/jsonschema/json | 2026-09-25 | ok (first pin) |
| rapidfuzz | 07 §5.3 (named, not versioned), first P3-S3-T03: the fuzzy name term of match_confidence | 3.14.6 | 3.14.6 (`requires_python >=3.11`) | 2026-08-30 | pypi.org/pypi/rapidfuzz/json | 2026-10-06 | ok (first pin; recorded late, pinned 2026-10-05) |
| pyyaml (dev group) | first P3-S3-T07: the workflow script next_task.py, so tests/test_next_task_ahead.py runs here | 6.0.3 | 6.0.3 (`requires_python >=3.8`) | 2025-09-25 | pypi.org/pypi/pyyaml/json | 2026-10-06 | ok (first pin) |
| colorspacious (dev group) | 09 §4.2 (named, not versioned), first P2-S2-T03: CVD simulation and CAM02-UCS ΔE in scripts/check_palette.py | 1.1.2 | 1.1.2 (needs only numpy; MIT) | 2018-04-08 | pypi.org/pypi/colorspacious/json | 2026-10-06 | ok (first pin); the last release is from 2018, checked working against numpy 2.5.3 here |
| numpy (dev group) | colorspacious's dependency, P2-S2-T03 | 2.5.3 | see the numpy row above | -- | -- | 2026-10-06 | ok (same pin as the atlas extra) |
| pagefind (site) | 08 §5.5 and §3.2 S12, first installed by P2-S4-T06: the search index, built at the end of every `astro build` (site/src/lib/pagefind.ts) | **1.6.0** (08 names 1.5.2) | 1.6.0 | 2026-11-01 | registry.npmjs.org/pagefind | 2026-11-24 | ok (first install); **differs from 08's 1.5.2**, for determinism: see note 7 |
| mlcroissant | 08 §5.8 (named, not versioned), first P2-S3-T06: base-Croissant conformance of every croissant-benchmark document, inside `bench build` | 1.1.1 | 1.1.1 (no `requires_python`; the wheel declares no licence, the repository mlcommons/croissant is Apache-2.0 per api.github.com) | 2026-10-05 | pypi.org/pypi/mlcroissant/json | 2026-11-18 | ok (first pin); see note 5 |
| minisearch (site) | 08 §5.5, §5.7 (named, not versioned), first P2-S4-T02: the BM25 leg of the faceted query pipeline, site/src/islands/search/lexical.ts since P6-S1-T04 (site/src/lib/query.ts before it) | 7.2.0 | 7.2.0 (`next` tag 5.0.0-beta1, an older line; no dependencies; MIT; not deprecated) | 2025-09-16 | registry.npmjs.org/minisearch | 2026-11-24 | ok (first pin); see note 6 |
| sigma (site) | 10 §Technology decisions and 08 §5.2 ("Pin `sigma@3.0.3`"), first installed by P2-S5-T02: the Atlas island, site/src/islands/Atlas.tsx | 3.0.3 | **4.0.6** (`latest`, 2026-11-10; 4.0.0 went stable 2026-10-08; 3.0.3 is still the newest 3.x; MIT; not deprecated) | 2026-04-30 | registry.npmjs.org/sigma | 2026-11-24 | **moved** (major); kept at 3.0.3, as 08 §5.2 says: see note 8 |
| graphology (site) | 10 §Technology decisions, first installed by P2-S5-T02: the Atlas island's graph | 0.26.0 | 0.26.0 (`latest`; MIT; not deprecated) | 2025-01-26 | registry.npmjs.org/graphology | 2026-11-24 | ok (first install); see note 8 |
| size-limit (site, dev) | 08 §8.1 and 14 Phase 2 exit criteria ("Enforced by `size-limit` per route group"; named, not versioned), first installed by P2-S4-T08: the per-route size gate, site/.size-limit.js | 14.3.0 | 14.3.0 (`latest`; MIT; not deprecated; `engines.node ^22.19.0 \|\| ^24.5.0 \|\| >=26.0.0`) | 2026-10-22 | registry.npmjs.org/size-limit | 2026-11-24 | ok (first pin); see note 9 |
| @size-limit/file (site, dev) | the size-limit plugin that measures built files, first installed by P2-S4-T08 | 14.3.0 | 14.3.0 (`latest`; MIT; not deprecated; no dependencies, peer `size-limit` 14.3.0) | 2026-10-22 | registry.npmjs.org/@size-limit/file | 2026-11-24 | ok (first pin); see note 9 |

## Other pins and third-party facts the plan names

| pin | owner | pinned | observed | observed published | source | verified_on | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| graphology | 10 §Technology decisions | 0.26.0 | 0.26.0 | 2025-01-26 | registry.npmjs.org/graphology | 2026-09-23 | ok |
| datamodel-code-generator | 08 §5.6 (inbound direction only) | 0.82.0 | 0.82.0 | 2026-09-16 | pypi.org/pypi/datamodel-code-generator/json | 2026-09-23 | ok |
| json-schema-to-zod (rejected) | 04 §12, 08 §5.6 | not used | GitHub repo `archived: true`; npm latest 2.8.1 (2026-04-01) carries no `deprecated` flag | 2026-04-01 | api.github.com/repos/StefanTerdell/json-schema-to-zod | 2026-09-23 | rejection confirmed |
| cloudflare-static-assets | 08 §7.6 items 1-2 | 20,000 files/version; 25 MiB/file | Free: "Number of Static Asset files per Worker version 20,000"; "Individual Static Asset file size 25 MiB" | 2026-09-05 | developers.cloudflare.com/workers/platform/limits/ | 2026-09-23 | ok |
| benchindex (package name) | 17 §9 | wanted | PyPI 404, npm 404, GitHub repository search: 0 results | -- | pypi.org/pypi/benchindex/json; registry.npmjs.org/benchindex; api.github.com/search/repositories | 2026-09-23 | available today; not reserved |
| pypi-trusted-publishing | 17 | the release mechanism | docs.pypi.org/trusted-publishers/ returns 200 | -- | docs.pypi.org/trusted-publishers/ | 2026-09-23 | page exists; mechanism not exercised |

## Notes

1. **Python patch and uv.** `pyproject.toml` pins the minor (`>=3.12,<3.13`), not a patch. The
   installed uv (0.9.17, Dec 2025) can fetch CPython up to 3.12.12; the newest 3.12 patch on
   python.org is 3.12.14, and python-build-standalone's 2026-09-01 release ships a 3.12.14 build
   that a current uv (0.12.18) would install. Left unpinned deliberately: bumping uv on a
   contributor's machine is not this task's call, and a lockfile written by uv 0.12 may not
   read under 0.9. Decide once, with a `uv` version floor in 05 §3.
2. **Node 22 reaches end of life on 2027-04-30,** inside this project's schedule (14 puts public
   v1 well past it). The pin `>=22.12` is still what Astro declares, so it is correct as a
   floor; the build should run on Node 24 ("Krypton", active LTS until 2026-10-20, maintenance
   until 2028-04-30). A decision for 08 §5.1.
3. **Anthropic tiers.** 11 §5 marked these figures "(unverified -- confirm before relying on
   this)"; the vendor page now confirms all four. The tiers are named Start / Build / Scale /
   Custom, not numbered.
4. **numpy 2.5.3 requires Python >=3.12.** 14 names a Python 3.11 consumer floor for the
   `benchindex` package (17). Any consumer package that depends on numpy cannot honour a 3.11
   floor at this numpy; either the floor moves to 3.12 or the package keeps numpy out of its
   dependencies.

5. **mlcroissant is heavy, and it is a runtime dependency.** `bench build` validates every document
   with it, so it is in `[project] dependencies`, not an extra. 1.1.1 brought 22 packages into
   `uv.lock`: absl-py, certifi, charset-normalizer, decorator, etils, fsspec, jinja2, jsonpath-rw,
   markupsafe, mlcroissant, networkx, pandas, pandas-stubs, ply, pyparsing, python-dateutil, rdflib,
   requests, six, tzdata, urllib3 and zipp; and numpy, scipy and tqdm, which the lock already held
   for the atlas extra and the dev group, become runtime dependencies through it (scipy, numpy and
   pandas are most of the weight: about 206 MB installed for the set, scipy 108 MB, numpy 42 MB,
   pandas 39 MB, measured 2026-11-18). Importing it takes several seconds, so
   tools/build/croissant.py imports it only to validate. The extension-schema half of the check
   imports jsonschema, which moved from the dev group into `[project] dependencies` for that reason
   (the same pin, 4.26.0, still the newest on PyPI on 2026-11-18), so a `--no-dev` install builds.

6. **MiniSearch weighs what 08 §5.5 says.** 7.2.0 bundled alone (its default export, esbuild 0.28.2,
   minified ESM) is 17.7 KB, 5.9 KB gzipped and 5.3 KB brotli, measured 2026-11-24 -- the "5.9 kB
   gzip" 08 §5.5 budgets. The package is 826,513 bytes unpacked in 37 files, with no dependencies,
   so `package-lock.json` gained its one entry and nothing else. It is a runtime dependency of the
   site, but only islands/search/lexical.ts imports it (since P6-S1-T04, PR #254, which moved the
   BM25 leg there), and lib/query.ts uses that module rather than importing MiniSearch itself. No
   page or island imports either yet: the V11 browse island counts through lib/facet-index.ts,
   which has no dependency, so the island ships no MiniSearch until a view wires the pipeline in.
   The newest release is over a year old; the line has been stable since 7.0.0 (2024-07-08).
7. **Pagefind is installed at 1.6.0, not the 1.5.2 that 08 §5.5 and 10 V11 name (P2-S4-T06), and
   that is a decision for 08.** 1.5.2 (2026-04-12) was the newest release when the plan was written;
   1.6.0 (2026-11-01) is the registry's `latest` on 2026-11-24. The reason is 08 §3.1, which lists
   S12 as deterministic: measured here on 2026-11-24, 1.5.2 wrote a different bundle on every run
   over the same records (three runs of 457 records, three bundles; four runs of the same records
   and a 923-page crawl, four bundles), the fragments and index chunks agreeing and the filter
   files, the meta file and pagefind-entry.json differing, while 1.6.0 wrote one bundle, byte for
   byte, in both experiments. tests/build/test_pagefind.py holds that property. 1.6.0 also ships
   `max_fragments`, the fragment bundling of PR #1020 that 08 §7.5 lists as its fourth mitigation
   for the 20,000-file cap (left unset: scripts/check_pagefind_urls.py reads one fragment per
   indexed page and fails on a bundle that groups them), and a platform binary a quarter the size.
   Going back to 1.5.2 is a one-line change to site/package.json and its lockfile, at the cost of
   that determinism. Weight: `pagefind` itself is 38 KB unpacked, MIT, with no dependencies and no
   install script; it brings one platform binary through optionalDependencies,
   `@pagefind/<os>-<cpu>` 1.6.0, MIT, 12-14 MB unpacked (windows-x64 13.2 MB, linux-x64 13.5 MB,
   darwin-arm64 12.1 MB; 1.5.2's were about 58 MB). site/package-lock.json gains pagefind and its
   seven platform packages, and `npm ci` installs the host's one (no install script, so
   `--ignore-scripts` changes nothing). The bundle it writes into dist/pagefind/ for today's
   production build (566 records and 10 crawled pages) is about 1.3 MB in 611 files: 576 fragments,
   10 index chunks and 25 other files, most of the weight in the last group, the UI scripts and
   styles no page loads until the search box exists (P2-S4-T07). The `pagefind` row in the first
   table is P0-S4-T01's check of the plan's value on 2026-09-23.
8. **sigma is installed at 3.0.3 although 4.x is now stable, as 08 §5.2 decided (P2-S5-T02).** The
   plan pins `sigma@3.0.3` and calls v4 "a deliberate later migration with its own PR". On
   2026-11-24 the registry's `latest` is 4.0.6 (2026-11-10); 4.0.0 went stable on 2026-10-08, after
   4.0.0-beta.0 to beta.8 (08 cites beta.6). No 3.x release followed 3.0.3, so no fix in its own
   line supersedes it, and nothing in it was found broken for the Atlas (site/tests/atlas.spec.ts
   passes on it). Whether to migrate now that v4 is stable is 08 §5.2's call; until then the risk
   is the usual one for a superseded major, that a 3.x security fix may never ship. graphology
   0.26.0 is the registry's `latest`. Both are MIT, and none of the five packages below has an
   install script (graphology's `prepare` runs only in a git checkout, never from the registry
   tarball). site/package-lock.json gained exactly five: sigma 3.0.3 (970,733 bytes unpacked, 96
   files), graphology 0.26.0 (2,729,833 bytes, 30 files: four builds and their source maps), and
   their dependencies `events` 3.3.0 (2021-02-27, MIT, 82,778 bytes, a dependency of both),
   `graphology-utils` 2.5.2 (2022-04-07, MIT, 30,887 bytes, sigma's) and `graphology-types` 0.24.8
   (2024-11-22, MIT, 58,067 bytes), the TypeScript declarations both name as a peer dependency, which
   npm installs and nothing ships. Weight, bundled alone with esbuild 0.28.2 (minified ESM, measured
   2026-11-24): sigma's default export is 95.7 KB, 26.0 KB gzipped; graphology's 66.0 KB, 13.2 KB
   gzipped; the two with what the island also takes from `sigma/rendering` and `sigma/utils`
   160.3 KB, 38.7 KB gzipped, 32.5 KB brotli. The plan's "183 KB min" is the UMD bundle the package
   ships, dist/sigma.min.js (187,876 bytes, 47.5 KB gzipped), not what a bundler includes. In the
   built site (the 320-entry draft preview, 2026-11-24) the five chunks the Atlas island imports
   after hydration are 160,067 bytes, 38.1 KB gzipped, and the whole /atlas/ route, React's runtime
   included, is 118.5 KB gzipped (KB here is 1,024 bytes; gzip -9 per file), against 08 §8.1's
   120 KB: P2-S5-T02's report has the breakdown.
9. **size-limit is installed with `@size-limit/file` and no preset (P2-S4-T08).** 08 §8.1's blocking
   budgets are "deterministic, computed from artifacts", so the gate measures the built files and
   nothing else: `@size-limit/file` gzips each one (level 9) or brotlis it and sums them. Each preset
   adds a step that is not that: `@size-limit/preset-app` and `preset-big-lib` add `@size-limit/time`,
   which drives headless Chrome through estimo and puppeteer-core to time execution (the noisy kind
   of measurement 08 §8.2 keeps advisory), and `preset-small-lib` and `preset-big-lib` bundle source
   with rolldown or webpack, which would measure a bundle the site never ships. Both packages are
   development dependencies of site/, pinned exactly; `size-limit` declares
   `engines.node ^22.19.0 || ^24.5.0 || >=26.0.0`, narrower than the site's `>=22.12.0`, which
   matters only to whoever runs the gate (CI uses Node 24). site/package-lock.json gained exactly
   four packages, all MIT, none with an install script: size-limit 14.3.0 (51,273 bytes unpacked,
   19 files), @size-limit/file 14.3.0 (3,700 bytes, 5 files), and size-limit's two dependencies,
   lilconfig 3.1.5 (2026-11-09, 18,058 bytes; it finds the config file) and nanospinner 1.2.2
   (2024-12-09, 10,853 bytes; the progress line). nanospinner's one dependency, picocolors 1.1.1, was
   already in the lockfile as Astro's. The config is site/.size-limit.js, not a static
   `.size-limit.json`, because a route's files are content-hashed chunks: scripts/route_js.mjs reads
   them from the built page. A KB in it is 1,024 bytes (`KiB`), so size-limit prints the landing's
   40 KB limit as "40.96 kB", its own 1,000-byte unit. Measured on 2026-11-24, the landing ships
   963 bytes gzipped in every build state (the production build and the 320-entry draft preview):
   the theme toggle (212), the theme module it imports (594) and the pre-paint line (157). The same
   reading of the preview gives /benchmarks/ 76.9 KB and /atlas/ 118.6 KB, the second within 0.1 KB
   of note 8's figure for the same route.

## Moved pins (issue to open)

Step 5 of P0-S4-T01 asks for an issue naming every pin whose registry value has moved. The issue
text is below; it was not posted, because this repository's remote currently rejects the
working account (HTTP 403 on push) and posting is an outward action for a person to take.

> **Pins moved since the 2026-09-17 check (re-verified 2026-09-23)**
> - `astro` 7.3.3 -> 7.3.4 (published 2026-09-22), owner 08 §5.1
> - `@cosmos.gl/graph` 3.4.1 -> 3.4.2 (published 2026-09-21), owner 10 §Technology decisions
> - `uv` installed 0.9.17 vs current 0.12.18; newest CPython 3.12 patch 3.12.14 needs the newer
>   uv, owner 05 §3
>
> Both library moves are patch releases. Nothing else in docs/pins.md moved.
