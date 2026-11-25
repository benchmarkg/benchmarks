# ADR-0028 -- `frontier_floor` and `comparison_floor` are re-affirmed, not recalibrated, against the first hand-curated distribution

- **Status:** Proposed -- an agent draft (P4-S1-T07). It counts as decided only when a person ratifies it.
- **Date:** 2026-11-25
- **Taxonomy version:** not affected (taxonomy/VERSION stays 0.9.0). taxonomy/thresholds.yaml goes 0.1.0 -> 0.1.1 with
  both values unchanged; only its description, header and `updated` date change
- **Facet:** none -- the two named completeness floors of 12-analytics-and-trends.md §1.4
- **Change type:** threshold review; both values kept. No schema change and no migration
- **Supersedes:** --
- **Superseded by:** --
- **Measured with:** `uv run bench report completeness --format json`, on main at 201f8811

## Context

12 §1.4 declares `frontier_floor` (may a claim set the SOTA line) and `comparison_floor` (may a claim be placed beside
another; the stricter of the two) as starting points, not measurements, and asks for a recalibration "once ~200
hand-curated claims exist", recorded as an ADR so that the change to every published figure is dated and attributable.
P4-S1-T07 asks for that check now, against the hand-curated claims that exist. Their values are in
taxonomy/thresholds.yaml and, by the rule this ADR enforces, in no other living document; this record names them
because a decision has to say what it decided.

**The population.** tools/report/completeness.py scores every claim under data/claims/ whose benchmark is curated; it
does not filter by tier. The tiers are told apart two ways: a machine-ingested claim lives under
data/claims/_ingested/<source>/ (tools/validate/tiers.py, tools/build/feed.py), and it carries the `ingestion` block,
which 04 §9 puts on every machine-written record and leaves null on a hand-curated one (schema/claim.py). On main today
no claim is under _ingested/ and none carries an `ingestion` block, so the report's 76 rows are exactly the
hand-curated tier. Once a bulk ingest lands the report will mix the tiers, and the next check has to filter first.

**The distribution, n = 76 claims on 18 benchmarks, 2026-11-25:**

| Statistic | condition_completeness |
| --- | --- |
| minimum | 0.125 |
| 10th percentile | 0.200 |
| 25th percentile | 0.529 -- inside a gap: no claim scores between 0.40 and 0.57, so every quartile convention lands there |
| median | 0.733 |
| 75th percentile, 90th, maximum | 1.000 |
| mean | 0.699 |
| fully specified (1.0) | 30 claims |
| at 0.40 or below | 19 claims, a quarter |
| below `frontier_floor` | 14 claims (18%), on three benchmarks |
| below `comparison_floor` | 16 claims (21%), on the same three |

Percentiles interpolate linearly between order statistics. The per-benchmark rows are under Evidence.

Four properties of the sample decide what it can show.

1. **It is small, and the benchmark is the unit.** 76 is well under ~200. Completeness barely varies inside a benchmark:
   15 of the 18 give every claim the same score, because one source's claims share one condition record and one
   material field set. The evidence is closer to 18 observations than to 76.
2. **It was chosen adversarially.** 01 and 00 set the hand-curated LLM set at 50-80 claims "chosen adversarially rather
   than representatively". The low tail is that choice: 7 of the 8 MMLU claims (P3-S5-T02, a falcon-7b conflict) and
   3 of the 4 SWE-bench Verified claims (P3-S5-T03, the scaffolds) were curated because their sources disagree and
   state few conditions, and data/_analysis/warning-triage.yaml accepts their tier-4 warnings for that reason. The
   share of the sample below a floor describes how claims were picked, not the field.
3. **The rest of the low tail is a profile artefact.** The four DCASE claims (P3-S8-T07) score 0.20 because 8 of the 10
   material fields of the profile they resolve to are prompting or forecasting fields no DCASE task has.
   warning-triage.yaml defers them to the comparability profiles' maintainers; a governed profile change would move them
   with no curation at all.
4. **Denominators run from 2 to 12 material fields.** On a two-field profile completeness can only be 0, 0.5 or 1, and
   19 of the 30 fully specified claims are on profiles of two or three fields. A single floor asks for 1 field of 2 on
   one profile and 4 of 12 on another (04 §8: compare a claim only with its own denominator). That is a property of a
   global floor, and no sample tunes it away.

**Where the floors bind once verification applies.** 12 §1.3 admits a claim to headroom, saturation or comparison only
at or above `maintainer-verified` *and* above the floor. 62 of the 76 claims, on 15 benchmarks, clear the verification
threshold. Among those 62 the only claims below either floor are the four DCASE claims. The 12 self-reported claims
below the floors (MMLU, SWE-bench Verified) are excluded by verification already, and the two claims between the
floors (0.308 and 0.375) are both self-reported. So on today's curated tier the gap between the two floors decides
nothing, and the floors themselves decide only DCASE, whose score is a profile mismatch.

**Sensitivity.** What a floor at each value would exclude:

| Floor at | Claims below | Benchmarks | Of them at or above `maintainer-verified` |
| --- | --- | --- | --- |
| 0.20 | 6 | mmlu, swe-bench-verified | 0 |
| 0.25 | 10 | + dcase | 4 (dcase) |
| 0.30 (`frontier_floor`) | 14 | the same three | 4 (dcase) |
| 0.35 | 15 | the same three | 4 (dcase) |
| 0.40 (`comparison_floor`) | 16 | the same three | 4 (dcase) |
| 0.45 to 0.55 | 19 | + casp | 7 (dcase, casp) |
| 0.60 | 23 | + weatherbench-2 | 11 |

Any `frontier_floor` in (0.25, 0.31] and any `comparison_floor` in (0.375, 0.40] split the 76 claims exactly as the
current values do. Three CASP16 claims (held-out-server, 2 of 5 wet-lab fields answered) sit exactly on
`comparison_floor`: any raise excludes them, and tests/test_casp_claims.py asserts that every CASP claim clears it.

**What the sample does not measure.** `comparison_floor`'s meaning in thresholds.yaml is about hiding *machine-ingested*
claims from comparison views, so its job is to separate the ingested tier from the curated one. The ingested tier's
mean near 0.10 (04, 12 §1.3) is an expectation from the Epoch recon, not a measurement in this repository: no
machine-ingested claim is on main. One of the two distributions the floor separates has not been measured at all.

## Decision (proposed)

**Keep both values: `frontier_floor` and `comparison_floor` stay 0.30 and 0.40, re-affirmed on 2026-11-25 against
n = 76 hand-curated claims on 18 benchmarks. They are not recalibrated, and `calibrated_on` stays null.**

- The values agree with what was measured. Both sit in the sample's low tail -- a quarter of the claims score 0.40 or
  less, the median is 0.73 -- and above the ~0.10 expected of the ingested tier. Nothing in the sample argues for moving
  either.
- Nor can the sample support any other number. What it supports are intervals, not points: everything in (0.25, 0.31]
  and (0.375, 0.40] gives identical results. Leaving those intervals means fitting a floor to one benchmark at a time
  -- DCASE's profile mismatch below, CASP16's three unknown fields above -- whose scores say more about a profile than
  about curation.
- A new value at n = 76 would look like a measurement without being one, which is the failure 12 §1.4 made these
  constants to prevent.
- `calibrated_on` stays null because the thresholds.yaml header reserves it for a calibration and forbids filling it in
  to make the file look finished. A re-affirmation on this sample is not a calibration. The basis -- n, the date and
  this ADR -- is written into the file's `description` and header instead.

## Consequences

**Effect on every published figure: none.** No value changed, so no number moves. For the record, what reads the floors
today:

- **The tier-4 `condition-completeness` warning** (`bench validate`, tools/validate/tiers.py) is the only module that
  reads either floor. It flags claims below `frontier_floor`: the same 14 before and after (7 MMLU, 3 SWE-bench
  Verified, 4 DCASE), all triaged in warning-triage.yaml (accepted for the ten adversarial claims, deferred for
  DCASE). It is non-blocking and feeds the dashboard only (04 §12, tier 4).
- **No published figure reads either floor yet.** emit.py writes `headroom: null` on every row because nothing computes
  it. There is no SOTA or frontier trace, no comparison view and no F5 narration gate (P6-S3-T07). When these are
  built they read thresholds.yaml by name, and the values they meet are the ones re-affirmed here.
- **condition_completeness itself does not depend on the floors**: the ConditionMeter, `condition_completeness_max` in
  facets.json and index.sqlite, and the completeness report are all unchanged.
- The build manifest does not record the floors yet (tools/build/manifest.py: no S4 stage computes the completeness
  means). 12 §1.3 requires it as soon as a derived figure uses them.

**The last literals are gone.** The values are now printed in taxonomy/thresholds.yaml and nowhere else. These printed
them and now name the constant and point at the file: 04 §12 (both values, in parentheses), the 05 §2 tree comment,
12 §1.4's YAML block and the §11 citation example, and three places in 15 C4 (the summary row, the constants table and
the edits table). tests/cli/test_validate_tiers.py expected the message `below frontier_floor (0.3)` and now reads the
value from the file. tests/test_threshold_literals.py fails if a floor's name is followed by a decimal between 0 and 1
anywhere in code, tests, the plan or the docs. Exempt are thresholds.yaml; the ledger, which quotes the verify's own
grep; and the dated records, adr/ and CHANGELOG.md. An ADR is immutable once merged (03 §8), so the numbers in one,
this one included, record a decision at its date and are not a live copy of the value.

**What reopens the question.** Re-run this check, and write a successor ADR whether or not a value changes, when any of
these happens:

1. **The hand-curated tier reaches ~200 claims** (12 §1.4's trigger). Count benchmarks too: completeness clusters by
   benchmark, so 200 claims on 20 benchmarks is not much more evidence than 76 on 18. This ADR suggests waiting for
   about twice today's spread as well, roughly 40 benchmarks. That is a judgement for the ratifier, not a derived
   figure.
2. **The first bulk ingest lands on main.** Measure the machine-ingested tier with the same report, filtered on the
   `ingestion` block. `comparison_floor` separates two tiers, and only one has been measured.
3. **A governed change to taxonomy/comparability-profiles.yaml** changes the material fields of a profile that curated
   claims resolve to. DCASE's is the first candidate. Completeness is a per-profile ratio and moves without any
   curation.
4. **The first consumer that publishes a figure from either floor is about to ship** (headroom §3, the SOTA trace, a
   comparison view, the F5 gate). From then on a change of floor changes published numbers.

A recalibration proper, with new values and `calibrated_on` set, needs trigger 1 met and trigger 2's measurement in
hand. It also needs a criterion. 12 §1.4 gives each floor a job but nothing to calibrate against, such as a target
share of verification-eligible curated claims to exclude or a required separation between the tiers. The
recalibrating ADR should state its criterion before it states a number.

## Alternatives considered

- **Recalibrate now to a quantile of the sample.** Rejected. The quantiles near the floors each sit on a single
  benchmark. The 10th percentile, 0.20, is DCASE's profile-capped score: lowering `frontier_floor` to it would admit the
  four claims warning-triage.yaml defers to a profile fix, which treats a profile problem as a threshold problem. The
  20th percentile, 0.375, is one self-reported MMLU claim.
- **Raise `comparison_floor` above the three CASP16 claims (0.45 to 0.55).** Rejected. Nothing in the sample says those
  held-out-server claims are too thin to compare, and the move would set the floor by one benchmark's three unknown
  fields.
- **Set `calibrated_on: 2026-11-25` to record the check.** Rejected for the reason in the Decision. A dedicated basis
  field (n, date, ADR) in thresholds.yaml would be the structured home for this record, but ThresholdFile
  (schema/taxonomy.py) forbids unknown keys, so it needs a schema change and its own ADR. A re-affirmation does not
  justify that. Left to the ratifier.
- **Defer the whole task until ~200 claims exist.** Rejected. A dated "kept, and why" costs little, it turns the next
  review into a comparison rather than a first look, and it removes the remaining literals now, before a consumer reads
  them.

## Migration

None. Both values are unchanged, and scripts/check_schema_change_gate.py reads no structure from thresholds.yaml.

## Evidence

- `uv run bench report completeness --format json`, main at 201f8811, 2026-11-25. The summary reads claims 76,
  claims_fully_specified 30, claims_with_no_answered_field 0, mean_condition_completeness 0.699047. Per benchmark (the
  profile is the one the benchmark resolves to; "fallback" is the default material set):

  | Benchmark | Claims | condition_completeness | Material fields | Profile |
  | --- | --- | --- | --- | --- |
  | arc-agi-1 | 4 | 0.800 x4 | 5 | fallback |
  | behavior-1k | 2 | 0.875 x2 | 8 | simulation |
  | casp | 5 | 0.400 x3, 0.600 x2 | 5 | wet-lab |
  | critpt | 8 | 0.667 x8 | 9 | llm-static-text |
  | dcase | 4 | 0.200 x4 | 10 | llm-static-text + forecasting |
  | fair-universe-higgsml | 2 | 1.000 x2 | 2 | fallback |
  | forecastbench | 3 | 1.000 x3 | 4 | forecasting |
  | libero | 2 | 0.857 x2 | 7 | simulation |
  | mmlu | 8 | 0.125 x3, 0.250 x4, 0.375 | 8 | llm-static-text |
  | oc20 | 4 | 1.000 x4 | 2 | surrogate-fit |
  | open-asr-leaderboard | 8 | 1.000 x8 | 3 | fallback |
  | pdebench | 3 | 1.000 x3 | 2 | surrogate-fit |
  | roboarena | 6 | 1.000 x6 | 6 | physical-trial |
  | scicode | 5 | 0.625 x5 | 8 | fallback |
  | simplerenv | 2 | 1.000 x2 | 7 | simulation |
  | swe-bench-verified | 4 | 0.154 x3, 0.308 | 12 | agentic |
  | the-well | 2 | 1.000 x2 | 3 | surrogate-fit |
  | weatherbench-2 | 4 | 0.571 x4 | 7 | forecasting + surrogate-fit + eligibility-gated |

- Verification rungs of the 76 claims: maintainer-verified 42, held-out-server 17, prospective-experiment 3,
  self-reported 14. The 16 claims below `comparison_floor` are 12 self-reported (mmlu, swe-bench-verified) and 4
  held-out-server (dcase).
- data/_analysis/warning-triage.yaml, the two `condition-completeness` entries (P1-S13-T04, 2026-11-17; P3-S8-T07,
  2026-11-24).
- tests/test_casp_claims.py, `test_every_claim_clears_the_comparison_floor_and_its_unknowns_are_named`.
- Claims batches were still in flight on 2026-11-25. This check reads main at 201f8811 and nothing else.
