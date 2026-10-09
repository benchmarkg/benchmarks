# tests/fixtures/corpus

A data-only tree for `bench report staleness` (P5-S7-T05; 05 S7's re-verification queue), read with
`--root tests/fixtures/corpus --as-of 2026-10-09`. Each benchmark's first line says which factor of
`priority = staleness_days x volatility_weight x attention_weight` it exercises. The golden outputs are
tests/golden/reverification.json and tests/golden/reverification-issue.md. analytics/2026-08.json is
superseded by 2026-09 and analytics/2026-11.json is after as_of, so neither is read.
