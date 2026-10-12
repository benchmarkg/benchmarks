# The escape-hatch audit of the ten stress entries

P0-S9-T05, an agent draft for a person to sign. 14-roadmap Phase 0: "a `notes` field doing structural work is the
tell" that the schema is wrong. This reads every `extra:` map and every `notes` and `curation.notes` string in the
ten stress entries (`tests/fixtures/stress-entries.yaml`), says what each carries, and whether a structured field
should carry it instead. What it found is acted on in ADR-0026 (adr/0026-review-checks-and-evidence.md) and
migration 0026, not deferred to Phase 3, as the task's step 4 requires. The maintainer chose that route on
2026-10-12.

## Method

1. `grep -rn "^ *extra:" data/ schema/` returns nothing: no entry, and no model, carries an `extra:` map.
2. Free text in the ten entries comes in three shapes:
   - `notes` and `curation.notes`, which this audit reads, all 34 of them;
   - `*_note` and `*_notes` annotations, one per field, which ADR-0001 defines as the place a field's judgement is
     explained: an annotation of a field, not a hatch beside the schema, so not audited here;
   - `*_basis` blocks, which carry a source and a quote by construction.
   `scripts/notes_field_audit.py` lays all of them out beside their neighbouring fields;
   [checkpoint/schema-findings.md](checkpoint/schema-findings.md) argued the `*_note` groups for ADR-0024.
3. Each string is judged structural (a field should hold it) or prose (it explains a judgement), and structural
   content is moved.

## What was found

Three kinds of structure, and prose:

- **Reviewer checks: structural, in every `curation.notes`.** Each `curation.notes` was nothing but a list of
  questions for the verifier, each about one field, some needing a specialist, some resting on a source and a quote
  that nothing checked. They are now `curation.review_checks[]` (ADR-0026 R1): 88 moved from the 34 curated entries,
  29 of them from these ten, plus one written from a baseline note (30 here, 89 in all).
- **Schema findings: structural, but not the entry's.** Eight entries, seven of them stress entries, appended numbered
  findings about the schema. They are about the schema, not the benchmark, and moved to
  [schema-findings-ledger.md](schema-findings-ledger.md) verbatim (ADR-0026 R2): 45 findings, 42 from these ten.
- **Quotes inside baseline and subset notes: structural.** `Baseline` had a `source` and no quote, `Subset` neither,
  and `Baseline` had no subset, so quotes and a subset id were written into notes. They are now `Baseline.evidence`,
  `Baseline.subset` and `Subset.evidence` (ADR-0026 R3, R4), and the quotes are verified.
- **Everything else: prose**, which a note is for.

## Every notes string

Chars are before and after; "removed" means the key is gone because everything in it moved.

| Entry | Field | Chars | What it says | Judgement | Where it went |
| --- | --- | --- | --- | --- | --- |
| swe-bench | curation.notes | 293, removed | one reviewer check on the funded-by-evaluated-party flag | structural | review_checks (1) |
| casp | curation.notes | 485, removed | one reviewer check on an advisory-board affiliation, with a source and quote | structural | review_checks (1, quote verified) |
| roboarena | curation.notes | 690, removed | two reviewer checks on maintainer affiliation and evaluator concentration, with sources | structural | review_checks (2, one quote verified) |
| weatherbench-2 | curation.notes | 2,616, removed | four specialist checks; seven schema findings | structural | review_checks (4); ledger (7) |
| matbench-discovery | curation.notes | 2,274, removed | four specialist checks; eight schema findings | structural | review_checks (4); ledger (8) |
| matbench-discovery | subsets[1].notes | 98 | the default view; items from data.size | prose | kept |
| matbench-discovery | subsets[2].notes | 80 | a separate leaderboard view, not comparable | prose | kept |
| matbench-discovery | subsets[3].notes | 88 | a third view in the 2026-06 capture | prose | kept |
| matbench-discovery | subsets[6].notes | 160 | unranked in the archived copy, ranked today | prose | kept |
| arc-agi-3 | curation.notes | 1,689, removed | three reviewer checks; five schema findings | structural | review_checks (3); ledger (5) |
| arc-agi-3 | subsets[0].notes | 47 | the Verified board's set | prose | kept |
| arc-agi-3 | subsets[1].notes | 211 → 151 | the public set, and the maintainers' quoted rule on reporting it | quote structural | evidence (1, verified); prose kept |
| arc-agi-3 | subsets[2].notes | 71 | the competition's set, run offline | prose | kept |
| virtual-cell-challenge | curation.notes | 2,223, removed | four specialist checks; eight schema findings | structural | review_checks (4); ledger (8) |
| virtual-cell-challenge | subsets[0].notes | 83 | the live panel's dates; not prize-scored | prose | kept |
| virtual-cell-challenge | subsets[1].notes | 117 | the final round's release and prize role | prose | kept |
| virtual-cell-challenge | baselines[0].notes | 326 → 158 | the replicate anchor at 1, with two quotes | quotes structural | evidence (2, verified); prose kept |
| virtual-cell-challenge | baselines[1].notes | 345 → 159 | the context-mean floor at 0, and why classical-algorithm | judgement structural | a review check on `baselines`; prose kept |
| kaggle-game-arena | curation.notes | 1,335, removed | three reviewer checks; four schema findings | structural | review_checks (3); ledger (4) |
| kaggle-game-arena | subsets[0].notes | 89 | free-form games, the headline ratings | prose | kept |
| kaggle-game-arena | subsets[1].notes | 172 | games from the 20 most popular openings | prose | kept |
| forecastbench | curation.notes | 1,254, removed | three reviewer checks; five schema findings | structural | review_checks (3); ledger (5) |
| forecastbench | subsets[0].notes | 55 | dataset questions, eight horizons | prose | kept |
| forecastbench | subsets[1].notes | 106 | market questions, scored against the crowd until resolution | prose | kept |
| forecastbench | subsets[2].notes | 145 | the human question set and where the paper scores it | prose | kept |
| forecastbench | subsets[4].notes | 82 | the ten-year horizon; no score yet | prose | kept |
| forecastbench | baselines[0].notes | 73 | the overall Brier score on the human set (Table 2) | prose | kept |
| forecastbench | baselines[1].notes | 56 | the same, for the public | prose | kept |
| forecastbench | baselines[2].notes | 178 | the leaderboard value as captured 2026-09-26, rank 1 | prose (see below) | kept |
| forecastbench | baselines[3].notes | 85 | the same capture, rank 2 | prose (see below) | kept |
| paperbench | curation.notes | 1,389, removed | four reviewer checks; five schema findings | structural | review_checks (4); ledger (5) |
| paperbench | subsets[0].notes | 259 → 199 | Code-Dev: no GPU, 85% cheaper grading, r = 0.48 with the full benchmark | figures structural | evidence (2, verified); prose kept |
| paperbench | subsets[1].notes | 142 | the 3-paper subset of the human comparison | prose | kept |
| paperbench | baselines[0].notes | 244 → 132 | the subset the baseline is on, and the recruitment | subset structural | `subset: paperbench#human-baseline-3`; prose kept |

## For the person signing

- **The verify holds.** No `extra:` map; every `notes` and `curation.notes` string in the ten entries is at most 200
  characters, the longest 199.
- **Judgements to confirm.** Two kinds of short note are kept as prose but sit near the line:
  - **Leaderboard captures.** ForecastBench's two "as captured 2026-09-26" baselines date a leaderboard value.
    `Baseline` has no field for when a value was observed; the source's capture date carries it.
  - **Subset dates.** Virtual Cell Challenge's subset dates are subset metadata that a later revision might
    structure.

  Neither is an escape hatch today, because each is one fact stated once. If you judge otherwise, each is one row in
  [schema-findings-ledger.md](schema-findings-ledger.md).
- **Not decided here.** Whether an entry may be promoted above `curator-reviewed` while it still holds review checks.
  ADR-0026 names this as a candidate semantic rule.
