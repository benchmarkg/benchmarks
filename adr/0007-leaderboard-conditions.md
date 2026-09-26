# ADR-0007 -- A Leaderboard names the conditions a result must meet to be listed

- **Status:** Proposed
- **Date:** 2026-09-26
- **Taxonomy version:** not affected
- **Facet:** none. A schema change to the Leaderboard entity (04 §9)
- **Change type:** schema, additive (one optional field; no existing record changes)
- **Supersedes:** --
- **Superseded by:** --

## Context

Some benchmarks run more than one board, and the boards differ in what they allow. ARC-AGI-3 has a
Verified leaderboard, where ARC Prize runs selected commercial models itself on a Semi-Private set
with no tools and a $10,000 cap per run, and a Community leaderboard of lightly reviewed, unverified
submissions that may use their own harnesses (arcprize.org/policy). 02 §12.7 calls this "two
leaderboards with **different legality rules**", and 04 §8 already gives the rule a home:
`EvalConditions.eligibility_track` ("ARC-AGI-3 official vs community").

What was missing is the link. A Leaderboard record (04 §9) had no way to say which rules it
applies, so two boards with different rules were indistinguishable in the data, and P0-S8-T03's
verify ("two Leaderboard records with distinct eligibility_track values") could not be met.

## Decision

**`Leaderboard.conditions`: an optional reference to an EvalConditions record** holding the
conditions a result must meet to be listed on that board -- its `eligibility_track`, and whatever
of its rules map onto existing condition fields (`tools_allowed`, `n_samples`, `selection_strategy`,
`retries_allowed`, `cost_usd`, ...).

- The track is recorded once, in EvalConditions, and not duplicated as a Leaderboard field. A
  claim's own conditions and the board's conditions are the same kind of record, so whether a claim
  meets a board's rules is a field-by-field comparison, not a string match.
- A board's conditions are a floor, not a claim's conditions: fields a board leaves open (the
  harness, where a board accepts several) stay null there and are answered on each claim.

Alternatives considered: an `eligibility_track` text field on Leaderboard (simpler, but it
duplicates the value EvalConditions holds and leaves the rest of a board's rules nowhere); no schema
change, with the rules in a free-standing EvalConditions record (nothing would connect the board to
its rules).

## Consequences

- Additive: the field is optional and defaults to null, so no existing record changes and the
  migration plans no rows (schema/migrations/0007-leaderboard-conditions.py).
- Tier 2 resolves the reference like every `cond-` id.
- schema/generated/leaderboard.schema.json and site/src/types/leaderboard.d.ts are regenerated.
- First users: lb-arc-agi-3-verified and lb-arc-agi-3-community (P0-S8-T03).
