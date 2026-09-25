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
| uv | 05 §3 (named, not versioned) | 0.9.17 (installed here) | **0.12.18** | -- | pypi.org/pypi/uv/json | 2026-09-23 | **moved**; see note 1 |
| typer | 05 §3 (named, not versioned) | 0.27.2 | 0.27.2 | 2026-08-28 | pypi.org/pypi/typer/json | 2026-09-25 | ok (first pin, P0-S5-T01) |
| hatchling (build backend) | P0-S5-T01, for the `bench` entry point | 1.32.4 | 1.32.4 | -- | pypi.org/pypi/hatchling/json | 2026-09-25 | ok (first pin) |

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
