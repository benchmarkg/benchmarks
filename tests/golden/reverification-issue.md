Weekly re-verification queue, as of 2026-10-09.

Ordered by `priority = staleness_days x volatility_weight x attention_weight (05 S7)`. Re-verifying an entry means opening its cited sources and confirming its fields, then setting `curation.last_verified` (05 S7).

- entries: 9 (red 5, amber 1)
- critical, more than 730 days on an active entry: 1
- attention from: analytics/2026-09.json
- published suite manifests: 1

## Critical

- [ ] `alpha` (active), last verified 2024-09-01, 768 days: `data/benchmarks/fixture/alpha.yaml`

## Queue

| # | entry | lifecycle | last verified | days | volatility | attention | priority |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | `beta` | saturated | 2025-08-30 | 405 | 0.6 | 4.0 | 972.0 |
| 2 | `alpha` | active | 2024-09-01 | 768 | 1.0 | 1.0 | 768.0 |
| 3 | `gamma` | active | 2026-03-01 | 222 | 1.0 | 3.0 | 666.0 |
| 4 | `delta` | deprecated | 2023-01-01 | 1377 | 0.3 | 1.0 | 413.1 |
| 5 | `zeta` | retracted | 2022-10-09 | 1461 | 0.1 | 1.0 | 146.1 |
| 6 | `theta` | under-revision | 2026-06-01 | 130 | 1.0 | 1.0 | 130.0 |
| 7 | `eta` | dormant | 2025-04-01 | 556 | 0.2 | 1.0 | 111.2 |
| 8 | `iota` | active | 2026-07-01 | 100 | 1.0 | 1.0 | 100.0 |
| 9 | `epsilon` | active | 2026-09-29 | 10 | 1.0 | 6.0 | 60.0 |
