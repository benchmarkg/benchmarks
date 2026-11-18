# The gap matrix

**The matrix asserts no gap until families are reviewed.** A gap claim needs a domain family that a
reviewer has signed off (`reviewer_signoff` in `taxonomy/domains.yaml`), and no family has one yet. So
every one of the 247 cells carries the refusal "insufficient curation confidence to assert a gap", with
its four factors shown beside it, and `gaps.json` publishes no gap claim. This page describes how the
matrix is computed. While every family is unsigned, read it as a map of what has not been reviewed. It
says nothing about what the field lacks. A test (`tests/test_gap_matrix.py`) fails on the day a family
is signed, so this paragraph cannot stay out of date.

This is P1-S14-T08: the domain x capability-group gap matrix at the seed corpus, the matrix that
[14-roadmap.md](../_plan/14-roadmap.md) Phase 1 has the gap-matrix preprint describe "with our own
curation confidence shown alongside density so the gaps are not overclaimed".

## How gaps.json is produced

`build/` is not committed. The artifact is regenerated from the tree, then checked:

```sh
uv run bench gaps --grid coarse --reviewed-only --format json > build/derived/gaps.json
uv run python scripts/check_gap_claims.py
```

(On Windows, set `PYTHONUTF8=1` first.) `uv run bench gaps --reviewed-only` without `--format json`
prints the same document as Markdown. The artifact records the parameters it was computed under:
`as_of` (the data commit's date, as `tools/build/liveness.py` uses it, so a build is a function of the
commit), `data_commit` (its SHA), `min_confidence`, every window, weight and multiplier, and the
`capability_groups.yaml` version on every cell. A claim in it is a claim about the index at that commit,
not about the world.

`tools/build/gaps.py` computes the matrix. `tools/build/coverage_states.py` decides each cell's state
(has-benchmarks, surveyed-and-empty, not-yet-surveyed, not-applicable) and `gaps.py` reads that state
rather than deciding it again.

## The grid

The matrix uses the coarse grid only: the 19 domain families of `taxonomy/domains.yaml` crossed with the
13 capability groups of `taxonomy/capability_groups.yaml`, 247 cells. `--grid fine` exits non-zero. The
fine grid may never publish a gap claim ([12-analytics-and-trends.md](../_plan/12-analytics-and-trends.md)
S5.1), because at the seed most of its cells are empty by arithmetic.

The matrix shows every family, signed or not, because 14 Phase 4 has an unreviewed domain render the
refusal "in every cell" so that it reads as unknown rather than as empty. `--reviewed-only` limits the
coverage cells (`cells`) and the claims (`claims`) to signed families. It does not hide a refused cell.

## The four factors, beside the score

12 S5.3's score is the product of four factors:

```
gap_score = (1 - normalised_density) x domain_activity x capability_salience x curation_confidence
```

Every cell publishes all four factors next to the score. A reader who weighs them differently can
re-derive a ranking from the same JSON. `formula` in the artifact restates each definition below.

- **normalised_density**: 12 S5.2's density over the densest applicable cell's density
  (`parameters.density_reference`). Density sums `domain_weight x quality_weight` over the benchmarks
  that match the cell, counting each benchmark once at its heaviest match. A primary-domain match weighs
  1.0, a secondary 0.5, and a subset whose `domain_override` puts it in another family 0.5.
  `quality_weight` multiplies whichever of 12 S5.2's multipliers apply and is clamped to [0.5, 1.5]:
  - verified (primary-source-verified or above): x1.2
  - machine-ingested: x0.7
  - an activity signal within 18 months: x1.1
  - no activity signal for 18 months, read on two observed signals as liveness does: x0.8
  - a human baseline: x1.1
  - a sourced release date: x1.05

  `quality_weights` lists every benchmark's weight and the multipliers it took. Each cell also publishes
  its integer counts (primary, secondary, subset-derived) and its `weighted_count`, which is 02 S11 rule
  1's `n_primary + 0.5 x n_secondary` with subsets added.
- **domain_activity**: the family's release velocity. Of its entries that have a release date, it is the
  share released in the 24 months to `as_of`. It is a share within the family, not a count, because a
  count would measure our allocation and how freely each field names its benchmarks (12 S9.5).
  Publication velocity, the other half of 12 S5.3's wording, is not measured: the index holds no
  publication counts per family.
- **capability_salience**: how often the capability is measured anywhere else. Of the benchmarks whose
  primary family is another one, it is the share that carries a term of the group.
- **curation_confidence**, the honesty term (12 S5.3):
  `0.40 x min(1, reviewed entries / expected Tier-1 families) + 0.30 x (share of the family's entries
  verified within 180 days) + 0.30 x reviewer_signoff`. The sign-off scores 0 for none, 0.5 for a
  generalist and 1 for a domain expert. The denominator comes from `taxonomy/domain-expectations.yaml`.
  The six unsized families fall back to their seed targets, and each one is marked `unsized`. **Only
  reviewed entries count**: those at `curator-reviewed` or above on the
  [05-repository-and-workflow.md](../_plan/05-repository-and-workflow.md) S4 ladder. A draft that no
  person has opened cannot raise our confidence. While every entry is an agent draft, the term is 0 in
  every family.

Each cell carries curation confidence beside its density, so a thin row of ours cannot be misread as a
gap in the field. Each family row in `families` breaks the confidence into its three terms and their
inputs.

Drafts still count as presence. A cell that holds any entry is occupied, whatever that entry's
verification status. Dropping an entry because it is unreviewed would empty a cell that is in fact
measured, and an empty cell is exactly what the matrix exists to report (02 S11 rule 2).

## When a cell is asserted as a gap

A cell is asserted only when it is 12 S5.4's category 1, "nobody measures it". All of the following must
hold:

1. the family is signed and not under-surveyed;
2. the cell is triaged `applicable` in `taxonomy/_triage/not-applicable.yaml`, and a person has accepted
   that triage (its `accepted_by`);
3. no benchmark matches the cell at any weight: primary, secondary or subset-derived;
4. dated survey notes in `data/surveys/<family>/` cover every live subdomain of the family for every term
   of the group, so the cell reads surveyed-and-empty, and a person has accepted each note
   (`survey.accepted_by`);
5. curation_confidence is at least `--min-confidence` (0.6 by default, the threshold 00 S7.1's criterion
   S3 runs at);
6. other families measure the group (capability_salience > 0), and the family has released something in
   the window (domain_activity > 0).

Every other cell is refused. `gap_claim_refusal` gives the first reason, and `withheld` lists every
reason. Each cell of an unsigned family leads with "insufficient curation confidence to assert a gap".

What is excluded, and how:

- **Unreviewed families**: by condition 1, in every cell.
- **Category 3**, "we have not curated it yet": an empty cell that fails any condition. It is marked
  `"empty": "not-yet-curated"` and stays visible in the matrix as backlog.
- **Category 2**, "the taxonomy does not describe this field well": the evidence 12 S5.4 names is a
  reviewer flagging the cell as miscut. No such flag has a record anywhere yet, so the emitter cannot
  see one. Until it can, the reviewer's sign-off and the accepted triage (conditions 1 and 2) are the
  only places a miscut cell is caught.
- **Not-applicable cells** leave the grid. They have no score and are never asserted.
- **The fine grid**: it is never computed.

A claim (`claims`) carries its cell, its family's curation-confidence breakdown, the survey notes behind
it with their dates and who accepted them, and a sentence that states it as a claim about the index at
the data commit.

## What scripts/check_gap_claims.py asserts

The script re-reads the tree. It does not take the artifact's own account of itself.

- `gaps.json` is the coarse grid, made `--reviewed-only` at a `min_confidence` no lower than 0.6, and is
  what the emitter makes of the tree at its recorded `as_of`, so a stale artifact fails. Its coverage
  cells hold no unsigned family.
- Every one of the 247 cells appears once, with all four factors in [0, 1] (null only where a factor
  cannot be computed), its score equal to the product of those factors, and the current
  `capability_groups.yaml` version. A refused cell says why. Every cell of an unsigned family is refused
  with "insufficient curation confidence to assert a gap". A cell is asserted exactly when `claims`
  lists it.
- Every claim comes from the coarse grid and from a family signed in `taxonomy/domains.yaml`. It counts
  reviewed entries only: its entry term is recounted from the tree, and no entry, reviewed or not, sits
  in its cell. It names its survey notes, and each one exists, is dated, was accepted by a person and
  finds its subdomain surveyed-and-empty for the group. Together the notes cover every subdomain of the
  family. The claim's cell is triaged applicable in an accepted triage, and its curation confidence
  reaches `min_confidence`.

`tests/test_gap_matrix.py` builds a synthetic family that meets every condition. On that fixture it
shows the check accepting the claim from the coarse grid with its survey notes, and refusing it once the
claim is moved to the fine grid, once the family is unsigned, or once the claim loses its notes, its
reviewed entries or its accepted triage. On the corpus as it is, the test shows every cell refused and
no claim made.

## Open decisions

These are recorded for a person to decide. None of them changes today's output, which asserts nothing.

- `MIN_CONFIDENCE = 0.6` lives in `tools/build/gaps.py`, not in `taxonomy/thresholds.yaml`, because this
  task does not change the taxonomy files.
- The 24-month velocity window is this task's choice. 12 S5.3 names release velocity but gives no
  window.
- A benchmark matched only through a subset override makes a cell occupied here. Coverage-states does
  not count subset presence when it decides a cell's state (02 S11 rule 1 says "presence at any
  weight"), so a cell can read not-yet-surveyed there while holding a subset-derived match here.
- Requiring a person's acceptance on the survey notes and on the triage (conditions 2 and 4) goes beyond
  what coverage-states requires for surveyed-and-empty. It follows the notes' own rule that "a person
  must accept the finding before it changes anything".
