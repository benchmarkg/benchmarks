# D2 — Seed-target arithmetic and the per-family floor

**Status:** decided, 2026-09-21. Supersedes every seed-total and floor statement currently in the
corpus. Scope: the seed total, its per-family distribution, the floor rule, engineering-design, and
the effort and calendar figures that fall out of them. Out of scope, and left to the taxonomy and
matrix decisions: the subdomain count, the capability-term count, the capability-group vocabulary,
and the matrix cell arithmetic.

---

## The decision

**The canonical seed total is exactly 320 entries across 19 domain families, owned by
`02-taxonomy.md` §3, whose "Curation targets per family" table is the single per-family allocation
in the corpus and sums to 320 by construction; `14-roadmap.md` deletes its duplicate allocation
table and quotes three derived gates instead — 320 targeted, 290 as the launch gate, 144 in the
seven Core families with a gate of 130.** The tilde goes: "~300" is exactly how 300, 308 and 333
coexisted across three documents for three revisions, because a number with a tilde in front of it
is never checked against a column sum. The floor becomes three explicit numbers with three
different jobs instead of two numbers both called "the floor": **12 is the hard launch gate**
(CI-enforced, no family ships below it), **18 is the Core-family launch gate** (unchanged, the
seven differentiating families), and **15 is the specialist-credibility target every family reaches
by v1.x** — that is what the recon's "below roughly 15 a specialist spots the gaps" claim actually
supports, since it describes when a reviewer stops finding holes, not when it is safe to publish.
A family that cannot reach its floor ships **muted**: `coverage_status: under-surveyed` on the
family, the badge on every entry, and the Gap Finder refusing to assert a gap in that row — reusing
the mechanism `14-roadmap.md` already defines for unreviewed domains, because the only reason the
floor exists is that a thin row makes a gap claim unfalsifiable, and disclosure fixes that where
padding does not. **engineering-design is raised from 8 to 12 and funded** (6–18 person-hours),
conditional on a 1–2 hour scoping survey in Phase 0 rather than Phase 1, with muting as the stated
fallback if the field turns out not to hold twelve credible Tier-1 families; it is not cut, because
`02-taxonomy.md`'s own changelog already argued the case — CadEval, AutoLabs, Learn2Design and the
EDA/CAD cluster have no honest parent, and a family that does not exist is invisible to the gap
matrix that is differentiator 3. The **five-family "~40 combined" row is dissolved into five
explicit rows totalling 66**, because a combined row is precisely where a floor violation hides:
40 across five families averages 8, below both candidate floors, and nobody noticed for three
revisions. The consequences are a curation line of **175–495 person-hours** (was 150–450), a
project total of **490–1,080 hours**, **24–54 weeks at 20 h/week**, a Phase 1 of **9–25 weeks**
(was 8–22) and a headline of **six to thirteen months** (was six to twelve) — of which roughly two
of the three added weeks at the high end come not from engineering-design but from doing the
arithmetic on the 308 the roadmap already claimed and never re-derived.

### The canonical numbers, for quoting

| Quantity | Value | Kind |
| --- | --- | --- |
| Seed total | **320** | Target. Equals the §3 column sum, by CI check. |
| Launch gate | **290** | Blocking. 90.6% of target, the same slack ratio as the old 280/308. |
| Core seven target | **144** | Target. Sum of the seven `Core: Y` rows. |
| Core seven gate | **130** | Blocking. Unchanged. |
| Hard per-family floor | **12** | Blocking at launch, unless the family is muted. |
| Core per-family floor | **18** | Blocking at launch. No muting exemption. |
| Credibility target | **15** | Aspiration, every family, by v1.x. Not a launch gate. |
| Families, all non-empty | **19 of 19** | Blocking. |
| Floor-respecting minimum index | **270** | Derived: 126 Core + 144 non-Core. Binds the re-cut rule. |

---

## The corrected per-family table, ready to paste into `02-taxonomy.md` §3

Replaces lines 268–297 in full. It is one table carrying both the evidence columns (from the recon)
and the allocation columns (previously duplicated in `14-roadmap.md`), so that no second copy of
these nineteen numbers exists anywhere.

---8<--- BEGIN REPLACEMENT FOR 02-taxonomy.md L268–L297 ---8<---

### Curation targets per family

**This table is the canonical seed allocation for the whole plan.** Its "Seed target" column sums to
**320**, that is the seed total, and no other document restates the per-family numbers — they link
here. The Tier-1/Tier-2/Ceiling columns are the domain recon's estimates, grounded in what was found
on 2026-09-17, not measured counts; the Seed target column is our allocation, adjusted down from the
estimates by the non-duplication doctrine in
[01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10. "Families" means the
counting convention defined in §11 — DCASE is one family with seven children, not seven benchmarks.
The table is generated from `taxonomy/domains.yaml` by `scripts/taxonomy_stats.py` and checked in CI
([05-repository-and-workflow.md](05-repository-and-workflow.md) §9, check 9d); do not hand-edit the
numbers without editing the YAML.

| Family | Tier-1 (field-defining) | Tier-2 (worth an entry) | Ceiling | Seed target | Core? | Posture, and the curation difficulty that sets it |
| --- | --- | --- | --- | --- | --- | --- |
| robotics-embodiment | 25 | 120 | ~400 | **25** | **Y** | Hand-curate. Very high — no central hub exists anywhere, and the simulator build version dominates the result |
| biology-genetics | 30 | 150 | ~450 | **25** | **Y** | Hand-curate. Very high — CASP/CAFA/CAGI decompose into 100+ children, so the family/child convention lives or dies here |
| vision | 35 | 250 | ~1,000+ | **22** | N | Hand-curate, **capped**. Highest long tail in the project: CVPR/ICCV/ECCV emit 50–100 tracks a year. Cap deliberately or it eats the project |
| medicine-health | 25 | 200 | ~700+ | **20** | **Y** | Hand-curate + Grand Challenge API. Highest raw volume; 264 challenges on grand-challenge.org alone. Cap at families |
| chemistry-materials | 25 | 110 | ~300 | **20** | **Y** | Hand-curate. High — wet-lab and DFT level-of-theory conditions must be captured |
| agents-tooluse | 30 | 120 | ~400 | **20** | N | Mixed. Fastest-growing and most harness-sensitive; Epoch and Benchmark Radar cover part, the harness sensitivity is ours |
| physics | 20 | 70 | ~200 | **18** | **Y** | Hand-curate. High — fragmented by subfield, almost no shared vocabulary |
| earth-climate | 20 | 80 | ~250 | **18** | **Y** | Hand-curate. Medium-high — needs lead-time and spatial-resolution fields |
| audio-speech | 18 | 70 | ~200 | **18** | **Y** | Hand-curate. Medium — DCASE alone is 7 tasks × ~12 years |
| safety-alignment | 25 | 120 | ~350 | **18** | N | Mixed. High — Inspect Evals implements 100+; many private by design, recorded as entries with `access: private` |
| code | not estimated ‡ | — | — | **16** | N | Ingest-then-verify. Epoch, EEE and SWE-bench's own JSON carry the numbers; we add lineage and scaffold conditions |
| language | not estimated ‡ | — | — | **14** | N | Ingest-then-verify. The single most duplicated area in the landscape — catalogue richly, curate claims almost not at all |
| society-econ-law | 20 | 90 | ~250 | **14** | N | Mixed. Medium — many private/commercial test sets |
| games-planning | 15 | 60 | ~150 | **12** | N | Ingest-then-verify. Elo and unbounded metrics need special handling more than they need volume |
| general-intelligence | 12 | 30 | ~60 | **12** † | N | Ingest-then-verify. Low volume, high scrutiny |
| multimodal | not estimated ‡ | — | — | **12** | N | Hand-curate. Overlaps vision; keep the boundary rule in §11 |
| mathematics | not estimated ‡ | — | — | **12** | N | Ingest-then-verify. FrontierMath's four variants make the lineage case better than the volume case |
| reasoning-general | not estimated ‡ | — | — | **12** | N | Ingest-then-verify. Same |
| engineering-design | not estimated ‡ *(unverified — confirm before relying on this)* | — | — | **12** § | N | Hand-curate. Unknown difficulty; the recon never surveyed it as a family. Phase-0 scoping survey required before curation starts |
| **Total** | **300 across 13 estimated rows** | **~1,470** | **~4,700** | **320** | **144 in Core** | |

† **general-intelligence is the only row targeting 100% of its Tier-1 estimate**, deliberately: the
recon puts the whole field at twelve field-defining families (ARC-AGI's three generations, HLE,
GPQA, SimpleBench, BIG-bench's remnant, MMLU-Pro and a handful more). It is the one domain small
enough to sweep completely, and sweeping it completely is cheap and demonstrates the counting
convention works. Nowhere else should a target equal its estimate.

‡ **not estimated.** The domain recon's count table covers **thirteen** families totalling ~300
Tier-1 and does not size code, language, mathematics, reasoning-general, multimodal or
engineering-design at all. Those six rows (78 entries) are **our own estimates and are weaker than
the other thirteen**. Say so when quoting the total: 320 is *242 of the recon's 300 estimated Tier-1
families across thirteen domains (81%), plus 78 entries across six domains nobody has sized.* Sizing
those six is a Phase 0 task, not a Phase 5 one, because it is the only part of the allocation with
no external grounding.

§ **engineering-design carries the highest miss risk of any row.** The recon named four candidates
(CadEval, AutoLabs, Learn2Design 2026, Blueprint-Bench 2) and asserted an EDA/CAD cluster it never
enumerated. If the Phase-0 scoping survey finds fewer than twelve credible Tier-1 families, the
family ships **muted** under the floor rule below rather than padded to twelve.

**The floor rule.** Three numbers, three jobs, and they are not interchangeable:

1. **Hard floor, 12 entries, blocking at launch.** No family ships below twelve. Below twelve the
   row cannot support a gap claim: an empty cell is indistinguishable from a cell nobody looked at,
   and unfalsifiable gap claims are the one failure that would discredit differentiator 3.
2. **Core floor, 18 entries, blocking at launch, no exemption.** The seven Core families —
   robotics-embodiment, biology-genetics, chemistry-materials, medicine-health, physics,
   earth-climate, audio-speech — are the product. A specialist scanning their own field with
   eighteen entries says "yes, you got my field right"; with six they close the tab.
3. **Credibility target, 15 entries, every family, by v1.x.** This is what the recon's "below
   roughly fifteen a specialist spots the gaps immediately" actually measures: the point at which a
   reviewer stops finding holes. It is an aspiration with a ratchet (no family goes backwards), not
   a launch gate, and calling it a floor is what produced two contradictory floors in the first
   place. Six families launch at 12–14 and are below it; that is accepted, because every one of
   them is an ingest-then-verify family where a competitor already holds the ground and specialist
   credibility is not what the row is for.

**The muting exemption, and it is the only one.** A family that cannot reach its floor ships with
`coverage_status: under-surveyed` in `taxonomy/domains.yaml`, a visible badge on every entry in it,
that status shown in the coverage map, and **the Gap Finder refusing to assert any gap in that
row**. This is the same mechanism [14-roadmap.md](14-roadmap.md) already defines for unreviewed
domains, and it exists because the honest response to a thin family is disclosure, not padding —
padding trades a visible gap for an invisible quality failure, which is the worse trade. Muting is
not available to the seven Core families: a muted Core family means the project has lost its
differentiator and should re-plan, not badge.

**The effort this buys.** A fully sourced entry is realistically 30–90 minutes with heavy AI
assistance and 2–3 hours for the ten stress cases, so 320 entries is **175–495 person-hours** — one
part-time person for roughly nine to twenty-five weeks at 20 h/week, and that single line is
half the project. The non-LLM differentiating core (robotics, chemistry-materials, biology,
earth-climate, physics) is about **120 Tier-1 families** by the recon's estimate and **106 by this
allocation**; the seven-family Core set above is 163 estimated and 144 targeted. Both figures are
in circulation — say which set you mean.

---8<--- END REPLACEMENT ---8<---

---

## Reasoning

### Why 320 and not 300, 308 or 333

Four numbers were in play and only two of them were ever the product of a decision. **333** is the
column sum of `02`'s table, which nobody had computed; the document's own prose said ~300 on the
line below it. **~300** is the recon's estimate of how many Tier-1 families *exist* across the
thirteen domains it surveyed — an evidence figure that was silently promoted to a target, which is
why it never matched any allocation. **308** is the only considered number in the corpus: it is the
sum of `14-roadmap.md`'s allocation table, which took the recon estimates, applied the
non-duplication doctrine, respected a 12/18 floor and landed on 18 rows. **320 is 308 plus
engineering-design at the floor**, and nothing else changed.

Choosing the roadmap's distribution over the taxonomy's is not arbitrary. `02`'s seed column is the
recon's Tier-1 estimate lightly shaved (vision 35→30, biology 30→30) with no doctrine applied;
`14`'s is the same evidence adjusted by an argument — cap vision because its long tail eats the
project, hold agents and safety down because Epoch and Benchmark Radar already cover them, raise
earth-climate and audio-speech to 18 because they are Core. That argument is worth keeping, and it
happens to produce the number the rest of the roadmap is written against.

The headline is stated without a tilde on purpose. Every drift in this cluster was licensed by
approximation: a reader who sees "~300" above a table summing to 333 does not experience a
contradiction, and neither does a reader who sees "~308" next to "18 of 18" when the taxonomy has
nineteen families. An exact number next to a column sum is checkable in five seconds, and check 9d
below makes it checkable in zero.

### Why 02 owns it, and why 14's table goes

The divergence had one cause: the same nineteen numbers existed in two documents, and only one was
maintained. Any fix that leaves two copies will recur, so there is one table and the other document
links to it.

`02-taxonomy.md` gets it, for three reasons. The seed target is a per-family property of the Domain
vocabulary and belongs next to the vocabulary; the evidence columns it sits beside (Tier-1, Tier-2,
ceiling) are already there and are the justification for the allocation; and `02` is already the
document whose counts CI regenerates from `taxonomy/*.yaml` (check 9b), so the same machinery
extends to cover the allocation with one more assertion instead of a new mechanism.

The cost, stated plainly: a roadmap reader must now follow a link to see the per-family split, and
`14-roadmap.md` declares itself canonical for phase-scoped numbers, which a seed target arguably is.
That is why `14` keeps the three numbers it actually gates on (320 / 290 / 144-with-a-130-gate) in
prose, and loses only the nineteen-row table. Quoting three derived scalars is maintainable;
duplicating nineteen is not.

### Why the floor splits into three and not two

The brief allows 15 and 12 to coexist if one is a gate and the other an aspiration. They can, but
not in the direction the documents imply. `02` derives 15 from specialist credibility — the recon's
claim is about when a reviewer stops spotting gaps, which is a statement about quality of
impression, not about publishability. `14` uses 12 as a mechanical exit criterion. Making 15 the
gate would fail six families at launch (games-planning, general-intelligence, multimodal,
mathematics, reasoning-general, engineering-design all target 12; language and society-econ-law
target 14) and would add 26 entries of curation in exactly the families where the project has
decided not to compete. Making 12 the aspiration and 15 the gate is backwards. So: 12 gates, 15
aspires, 18 gates the Core seven, and each is labelled with which it is.

The failure mode this closes is specific and near-certain otherwise: at launch, with 291 entries and
general-intelligence at 13, someone opens `02`, reads "below roughly 15 … discount the whole index",
opens `14`, reads "none below 12", and the launch decision becomes an argument about which sentence
is binding. Two numbers both called "the floor" guarantee that argument. Naming the job of each
number removes it.

### Why engineering-design is funded rather than cut, kept thin, or merged

**Cut from the seed** is the tempting option and the wrong one. `02`'s changelog already made the
argument for creating the family: CadEval, AutoLabs, Learn2Design 2026 and the EDA/CAD cluster have
no honest parent, filing them under `physics` or `code` is the false-parent problem faceting exists
to avoid, and "a family that does not exist is invisible". Cutting it would also break the "every
family non-empty" gate, reduce the launch family count to 18 and thereby re-entrench the stale "18"
that `G1` is trying to kill across the corpus. The one honest argument for cutting — that we have
never surveyed it — is an argument for surveying it, not for deleting it, and the survey is two
hours.

**Keep it at 8 with an exemption** fails because 8 is not a decision, it is a leftover: it was
written in the same document as the 15-entry floor and violates it, which is how we know nobody
chose it. And an exemption granted at planning time to a family nobody has looked at is an
exemption granted for no reason. The muting mechanism exists for evidence that arrives later, after
the survey, not for evidence we declined to gather.

**Merge it** recreates exactly the problem the family was created to solve. Into `code`? CAD
geometry generation scored by Chamfer distance is not software engineering. Into `physics`? Circuit
EDA is not physics. Into `robotics-embodiment`? `lab-automation-execution` is arguably at home
there, but `circuit-eda` and `structural-mechanical-design` are not, so a merge splits the family
across three false parents and deletes the one genuinely novel row in the coverage matrix.

**Raise to 12 and fund it** costs 6–18 person-hours — 0.3 to 0.9 weeks at the planning intensity,
which is inside the rounding error of a 24–54 week schedule. The honest risk is that the field does
not hold twelve credible Tier-1 families and the curator pads. Two mitigations, both cheap: the
scoping survey moves to **Phase 0**, before any curation, so the number is evidenced before it is
committed; and if the survey comes back short, the family ships muted with a disclosed
`coverage_status` rather than padded. Note the second-order benefit — a muted engineering-design row
in the published coverage matrix is itself a finding: "nobody has built a benchmark index for
engineering design, and here is the evidence we looked".

### Does the per-family table cover all 19 families exactly once?

**`02-taxonomy.md` §3: yes, technically — 19 families, none missing, none double-counted — but only
because five of them share one row.** The table has fifteen printed rows: thirteen named families,
one combined row covering `language, mathematics, code, reasoning-general, multimodal`, and
`engineering-design`. 13 + 5 + 1 = 19, and every family in `G1`'s list appears exactly once. The
column sums to 333 (25+30+25+30+25+25+20+20+20+20+18+15+12+40+8).

The combined row is nonetheless the structural defect in the table, and it is worth naming because
it explains how `G7` survived review. Forty entries across five families averages **eight per
family** — below the 12 floor and below the 15 floor, for five of the nineteen families at once.
The violation is arithmetically present and visually absent, because no cell in the table ever
displays the number 8 for those rows. `14-roadmap.md` had already implicitly rejected it by
allocating those five families 16/14/12/12/12 = 66 individually, a 26-entry difference nobody
reconciled. The corrected table above dissolves the combined row, which is the single largest change
in this decision and accounts for most of the gap between 02's distribution and the canonical one.

**`14-roadmap.md` L408–428: no — `engineering-design` is missing entirely.** That table has
eighteen rows and sums to exactly 308, which is why the roadmap consistently says "18 of 18 domain
families" and why the stale eighteens in `G1` are not a typo but a coherent, wrong, whole-document
world-view. The 25-entry difference between the two tables decomposes exactly: −5 biology, −5
medicine, −8 vision, −5 chemistry, −5 agents, −2 safety, −2 physics, −2 earth-climate, −6 society,
−3 games, +26 on the five dissolved rows, −8 engineering-design = −25, and 333 − 25 = 308. The two
tables are reconcilable; they were simply never reconciled.

### Two contradictions found while doing the arithmetic, both inside D2's scope

**The re-cut-to-200 stopping rule is arithmetically impossible under its own floor rule.**
`14-roadmap.md` stopping rule (a) says: if the measured per-entry median at the 20-entry checkpoint
exceeds 60 minutes, re-cut the allocation to ~200 entries, "preserve the Core seven and the floor
rule". Those instructions cannot both be followed. Seven Core families at their floor of 18 is 126
entries; twelve non-Core families at their floor of 12 is 144; the minimum legal index is therefore
**270**, and it was 276 under the old 18-family table, so the rule was never satisfiable even before
engineering-design. Worse, the rule's own worked example ("language/reasoning/mathematics to 8
each") violates the 12 floor explicitly, in the same document that declares it. The fix is to set
the re-cut target to **270** and note that the path there is fully determined: take vision 22→12,
agents 20→12, safety 18→12, code 16→12, language 14→12, society-econ-law 14→12 (−32), then
robotics 25→18, biology 25→18, medicine 20→18, chemistry 20→18 (−18), for exactly 270 = 126 Core +
144 non-Core. Below 270, the floor rule cannot be preserved and families must be muted or dropped —
which is a re-plan, not a re-cut, and should say so.

**The 8–22 week Phase 1 was never derived from 308.** It is the recon's 150–450 hours for *300*
entries divided by 20, carried over unchanged when the total became 308. At 308 entries the honest
high end was already 477 h and 24 weeks. Of the roughly three weeks the high end moves in this
decision, about two are this correction and about one is engineering-design. Say that when the
roadmap's headline changes, or the change will be attributed to the wrong cause and argued about.

### The effort consequence, recomputed

Method, stated so it can be rechecked: 320 entries, of which ten are the named stress cases at 2–3 h
and 310 are ordinary entries at 30–90 min.

- Low: (310 × 0.5 h) + (10 × 2 h) = 155 + 20 = **175 h**
- High: (310 × 1.5 h) + (10 × 3 h) = 465 + 30 = **495 h**

That replaces the 150–450 h curation row. Holding every other row in the effort table unchanged
(they sum to 315 h low and 585 h high), the project total to public v1 becomes **490–1,080 h**, and
at the 20 h/week planning figure that is **24.5–54 weeks — six to twelve and a half months**.

Phase 1, which is the curation phase, moves from 8–22 weeks to **9–25 weeks** (175 h / 20 = 8.75;
495 / 20 = 24.75). The serial sum of Phases 0–4 moves from 25–54 weeks to **26–57 weeks**, so the
headline becomes **six to thirteen months**. The two-person split, recomputed by the same loose
method the original used — Phase 0 participation (3–6 wk) plus the curator's own load (275–690 h of
total curation at 20 h/week = 14–35 wk) plus Phase 4 (3–5 wk) — becomes **20–46 weeks, five to
eleven months** (derived, not measured; the original 20–40 was also derived).

Curation across all three curation rows becomes **275–690 h, 56–64% of the total** at both ends,
replacing 250–645 h and 54–62%. The engineering total is unchanged at **185–330 h**; nothing in
this decision touches it, and that is the point — the long pole got longer and the site did not.

One calibration figure worth adding to the roadmap, because it is what the 20-entry checkpoint will
actually be measured against: **at exactly 60 minutes per entry — the trigger value in stopping rule
(a) — the 320-entry seed is about 340 h, or 17 weeks of curation alone.**

---

## EDITS REQUIRED, BY FILE AND LINE

Line numbers are as of 2026-09-21 and will drift as other decisions land. Where a decision is
sequenced after another that changes the same region, it is flagged. All replacement text for
`14-roadmap.md` uses that document's `--` convention; `02` uses `—`.

### `02-taxonomy.md` — owner of the canonical table

| Line(s) | Change |
| --- | --- |
| **268–297** | **Replace the whole block** (heading `### Curation targets per family`, its preamble, the fifteen-row table, and the "Seed release target" paragraph) with the replacement text above, between the `BEGIN`/`END` markers. This dissolves the five-family combined row into five rows, raises engineering-design 8→12, changes twelve other seed values to the roadmap's allocation, adds the `Core?` and posture columns, adds the three-tier floor rule and the muting exemption, and states the total as **320**. |
| **292** | (Inside the replaced block.) The sentence "Below roughly 15 entries in a family, a specialist from that field will spot the gaps immediately and discount the whole index" must **not** survive as an unqualified floor. It reappears in the replacement as floor rule item 3, labelled a v1.x credibility target. |
| **290** | (Inside the replaced block.) engineering-design's seed target 8 → **12**, and the "not estimated *(unverified)*" marker on Tier-1 is **kept** — it is still true. |
| **246** | No change to the changelog cell, but note for the editor: its sentence "this family is thin at seed and will look weak. Accepted" is now backed by a funded target and a Phase-0 survey, so append: ` The Phase-0 scoping survey and the muting fallback in the floor rule below are what make that acceptance falsifiable.` |
| 240 | **Do not edit as part of D2.** "Nineteen families, 205 subdomains" belongs to the taxonomy-count decision. D2 assumes the 19 stands. |

### `14-roadmap.md` — loses the duplicate table, keeps the gates

| Line(s) | Change |
| --- | --- |
| **37** | `six to twelve months` → `six to thirteen months`. |
| **41** | Replace `three hundred entries is therefore **150--450 person-hours** ([00-vision-and-scope.md](00-vision-and-scope.md) §8 and [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §11 both carry the same range)` with `the canonical seed total of **320 entries** ([02-taxonomy.md](02-taxonomy.md) §3) is therefore **175--495 person-hours**, taking the ten stress entries at 2--3 h (00 §8 and 01 §11 carry the same per-entry rate against the recon's older 300-entry figure)`. |
| **56** | `puts it at **six to twelve**` → `puts it at **six to thirteen**`. |
| **59--61** | Replace `a credible cross-domain seed at ~300 Tier-1 benchmark families, ~20--35 per domain, because below roughly fifteen entries in a domain a specialist from that domain spots the gaps immediately` with `a credible cross-domain seed at **320 Tier-1 benchmark families**, 12--25 per family ([02-taxonomy.md](02-taxonomy.md) §3), with a hard floor of 12 at launch and 18 for the seven Core families; fifteen is the credibility target every family reaches by v1.x, not a launch gate`. |
| **103** | Phase 1 row: `~308 benchmarks across all 18 domain families` → `320 benchmarks across all 19 domain families`; size column `8--22 wk` → `9--25 wk`. |
| **111** | `25--54 calendar weeks -- six to twelve months` → `26--57 calendar weeks -- six to thirteen months`. |
| **114** | `roughly 20--40 weeks` → `roughly 20--46 weeks`; the parenthetical elsewhere reading "five to nine months" becomes "five to eleven months". |
| **127** | `v1 ships at ~308 families with a floor of 280` → `v1 ships at 320 families with a launch gate of 290`. |
| **128** | `` `00`'s "Phase 2 (first public build)" column -- 300 families `` → `` `00`'s "Phase 2 (first public build)" column -- corrected to 320 families by D2 ``. |
| **378** | `the six to twelve months in which this project is invisible` → `six to thirteen months`. |
| **385** | `eighteen domain families` → `nineteen domain families`. |
| **386** | `as it stands at ~300 entries` → `as it stands at the seed corpus (320 targeted)`. |
| **397--428** | **Delete the `### Per-domain-family curation allocation` heading, its two introductory paragraphs, and the entire eighteen-row table.** Replace with: `### Per-domain-family curation allocation` / blank / `**The allocation lives in [02-taxonomy.md](02-taxonomy.md) §3 and is not restated here** -- one table, generated from ` + "`taxonomy/domains.yaml`" + `, because two copies of nineteen numbers is exactly how this plan came to carry three different seed totals. What this document gates on: **320 entries targeted, 290 as the launch gate; 144 across the seven Core families, 130 as the gate; no family below 12, no Core family below 18.** The **Core seven** are robotics-embodiment, biology-genetics, chemistry-materials, medicine-health, physics, earth-climate and audio-speech -- every other gate in this document that says "the seven" means exactly these, and the non-duplication doctrine in [01-landscape-and-positioning.md](01-landscape-and-positioning.md) §10 is what sets each family's posture.` |
| **430--436** | Keep footnote † (general-intelligence) **or** delete it as now duplicated in `02` §3. Recommended: delete from `14`, since it is already in the replacement table's notes. |
| **437--443** | Footnote ‡: `covers **thirteen** domains` stays; `The targets in those five rows (66 entries)` → `those six rows (78 entries)`; `the 308 figure is *242 of the recon's 300 estimated Tier-1 families across thirteen domains (81%), plus 66 entries in five domains nobody has sized*` → `the 320 figure is *242 ... (81%), plus 78 entries across six domains nobody has sized*`; `Sizing those five is a Phase 1 task` → `Sizing those six is a Phase 0 task`. |
| **445--448** | Replace the `**Floor rule:**` paragraph with a pointer: `**Floor rule:** three numbers with three jobs -- 12 is the hard launch gate, 18 is the Core-family launch gate, 15 is the v1.x credibility target every family reaches eventually. A family that cannot reach its floor ships muted (` + "`coverage_status: under-surveyed`" + `, badged entries, Gap Finder silent on that row); muting is not available to the Core seven. Stated in full in [02-taxonomy.md](02-taxonomy.md) §3.` |
| **449--455** | The "Reconciling the ~120 figure" paragraph: `144 targeted` stays correct; add that the five-domain set is **106 targeted** under the canonical allocation against the recon's ~120 estimated. |
| **465** | `~308 benchmark entries, every domain family non-empty, floor rule respected, Core families at 18+` → `320 benchmark entries, all 19 domain families non-empty, floor rule respected, Core families at 18+`. |
| **482** | `**>=280 benchmarks** (308 targeted); 18 of 18 domain families populated; none below 12.` → `**>=290 benchmarks** (320 targeted); 19 of 19 domain families populated; none below 12 unless muted under the floor rule.` |
| **484** | In the Core-seven list, `chemistry` → `chemistry-materials` (canonical slug, so the gate is machine-checkable). |
| **860** | `how many of eighteen domains are review-backed` → `how many of nineteen domains`. |
| **1163** | `**25--54 weeks** (six to twelve months)` → `**26--57 weeks** (six to thirteen months)`. |
| **1164** | `**20--40 weeks** (five to nine months)` → `**20--46 weeks** (five to eleven months)`. |
| **1182** | `| Benchmark entry curation (~308 entries) | **150--450** |` → `| Benchmark entry curation (320 entries) | **175--495** |`; basis cell unchanged (`30--90 min per entry ... plus 10 stress entries at 2--3 h`) — it is now actually the method used. |
| **1194** | `| **Total** | **~465--1,035 h** | **23--52 weeks at 20 h/week -- six to twelve months** |` → `| **Total** | **~490--1,080 h** | **24--54 weeks at 20 h/week -- six to twelve and a half months** |`. |
| **1196** | `**Curation is 250--645 hours, or 54--62% of the total** ` → `**Curation is 275--690 hours, or 56--64% of the total** `. |
| **1206** | `465 h is 23 weeks and 1,035 h is 52 weeks -- five and a half to twelve months` → `490 h is 24.5 weeks and 1,080 h is 54 weeks -- six to twelve and a half months`. |
| **1207** | `The phase table's serial sum (25--54 weeks)` → `(26--57 weeks)`. |
| **1219--1225** | Stopping rule (a): `re-cut the allocation table down to ~200 entries` → `~270 entries`, and replace the worked cut `(vision from 22 to 14, language/reasoning/mathematics to 8 each, code to 10, agents to 14)` with `(vision 22-->12, agents 20-->12, safety-alignment 18-->12, code 16-->12, language 14-->12, society-econ-law 14-->12, then robotics 25-->18, biology 25-->18, medicine 20-->18, chemistry-materials 20-->18)`. Add: `**270 is the arithmetic minimum of a 19-family index that obeys both floors** -- 126 in the Core seven at 18 each plus 144 in the twelve non-Core families at 12 each. Below 270 the floor rule cannot be preserved and families must be muted or dropped, which is a re-plan, not a re-cut.` Also change `a 300-entry plan quietly running 50% over` → `a 320-entry plan quietly running 50% over`. |
| **1266** | `- [ ] >=280 benchmarks across 18 of 18 domain families, none below 12 entries (308 targeted).` → `- [ ] >=290 benchmarks across 19 of 19 domain families, none below 12 entries, or muted under the floor rule (320 targeted).` |
| **1268** | In the launch-checklist Core-seven list, `chemistry` → `chemistry-materials`. |

### `00-vision-and-scope.md`

| Line(s) | Change |
| --- | --- |
| **567** | Clarify evidence vs target: `The per-domain research estimate is **~300 Tier-1 (field-defining) families, ...**` → append ` That is an estimate of what **exists** across the thirteen surveyed domains, not a target; the seed target is 320 ([02-taxonomy.md](02-taxonomy.md) §3).` |
| **573** | Scale table, "Benchmark families" row, Phase 2 column: `300` → `320`. |
| **575** | "Domains represented, non-empty" row: all three cells `18 of 18` → `19 of 19`. |
| **593--594** | `Three hundred entries is therefore **150–450 person-hours** — roughly one part-time person for 4–8 months.` → `The 320-entry seed target is therefore **175–495 person-hours** — roughly one part-time person for nine to twenty-five weeks at 20 h/week.` |
| **679** | `what makes 300 entries a part-time project` → `what makes 320 entries a part-time project`. |
| **689** | `breadth proof — ~300 Tier-1 families with every domain non-empty` → `breadth proof — the 320-family seed with all 19 domains non-empty ([02-taxonomy.md](02-taxonomy.md) §3)`. |
| 611 | `the Phase-2 corpus at 300` → `at 320`. Cosmetic; the artifact-size arithmetic does not move materially at +6.7%, but say 320 for consistency. |

### `01-landscape-and-positioning.md`

| Line(s) | Change |
| --- | --- |
| **492--494** | `a seed release of roughly **300 Tier-1 benchmark families, 20-35 per domain, every domain non-empty**, because below about 15 per domain a specialist spots the gaps immediately` → `a seed release of **320 Tier-1 benchmark families, 12-25 per family, all 19 domains non-empty** ([02-taxonomy.md](02-taxonomy.md) §3), with a hard floor of 12 at launch; fifteen per family is the credibility target by v1.x, which is what "a specialist spots the gaps immediately" actually measures`. |
| **496** | `so 300 entries is roughly **150-450 person-hours** -- one part-time person for four to eight months` → `so 320 entries is roughly **175-495 person-hours** -- one part-time person for nine to twenty-five weeks at 20 h/week`. |

### `03-taxonomy-build-process.md`

| Line(s) | Change |
| --- | --- |
| **807--809** | Replace `the recon is explicit about the bar: **below roughly 15 entries per domain a specialist will spot the gaps immediately**, and the seed target of ~20-35 Tier-1 families per domain is chosen precisely so a reviewer from any one field can scan it and say "yes, you got my field right"` with `the recon is explicit about the bar: **below roughly 15 entries per family a specialist will spot the gaps immediately**. Fifteen is therefore the credibility target every family reaches by v1.x, not the launch gate -- the launch gate is 12, and 18 for the seven Core families ([02-taxonomy.md](02-taxonomy.md) §3). The Core families are seeded at 18-25 precisely so a reviewer from one of those fields can scan it and say "yes, you got my field right"; the ingest-then-verify families launch at 12-16 and are knowingly below the credibility bar.` |
| 492 | **Not a D2 edit.** `18 domain families and roughly 40 capability terms ... ~720 cells` belongs to the matrix/capability-group decision. Flagged only so it is not missed there. |

### `05-repository-and-workflow.md` — the check that stops this recurring

| Line(s) | Change |
| --- | --- |
| **after 709** | Insert a new row in the `pr-validate.yml` table, after check 9c: `| 9d | **Seed-target integrity** | Yes | ` + "`python scripts/taxonomy_stats.py --check`" + ` also asserts, against ` + "`taxonomy/domains.yaml`" + `: exactly one ` + "`seed_target`" + ` per domain family with no family missing and none listed twice; the sum equals the canonical seed total (320); every target >= 12 unless that family carries ` + "`coverage_status: under-surveyed`" + `; every family with ` + "`core: true`" + ` is >= 18 and carries no ` + "`under-surveyed`" + ` status; and the rendered table in [02-taxonomy.md](02-taxonomy.md) §3 matches the YAML byte for byte. Three documents carried three different seed totals because nineteen numbers lived in two hand-maintained tables |` |
| **111** | `taxonomy/domains.yaml` comment: note that the file now also carries `seed_target`, `core` and `coverage_status` per family. |

### `04-data-model.md` — the one schema consequence

| Line(s) | Change |
| --- | --- |
| **new** | The muting mechanism needs a home. Add to the domain-family record in `taxonomy/domains.yaml`: `seed_target: int` (>= 1), `core: bool`, and `coverage_status: surveyed \| under-surveyed`. `under-surveyed` is what the badge, the coverage map and the Gap Finder read. **Dependency to flag:** `14-roadmap.md` already relies on a per-domain `curation_confidence: unreviewed` badge that is not modelled in `04` either; the two are different axes (did we look vs did a specialist check) and both belong on the family record. That gap pre-dates D2 and should be resolved by whoever owns `04`. |
| 174 | `~300 genuinely field-defining` — leave. It is the recon's existence estimate, correctly used. |

### Consistency-only edits (no reasoning change)

| File | Line | Change |
| --- | --- | --- |
| `06-sourcing-and-scraping.md` | 931 | `the seed-release target of roughly 300 Tier-1 families with every domain non-empty` → `the seed-release target of 320 Tier-1 families with all 19 domains non-empty ([02-taxonomy.md](02-taxonomy.md) §3)`. |
| `12-analytics-and-trends.md` | 293 | `At the seed target of ~300 Tier-1 benchmark families ... at most ~900 occupied (domain, capability) pairs` → `At the seed target of 320 ... at most ~960 occupied pairs`. **Sequencing:** the "at least 87% empty" figure on L295 depends on the matrix cell count, which the matrix decision owns; recompute it there against 960, not here. |
| `12-analytics-and-trends.md` | 997 | `Seed corpus at ~300 Tier-1 families` → `Seed corpus at 320 Tier-1 families`. |
| `12-analytics-and-trends.md` | 1000 | `` `cohort_v1` above ~300 entries `` → `above 320 entries`. |
| `13-execution-runners.md` | 103 | `roughly **300 Tier-1 benchmark families and ~1,470 worth-cataloguing families overall**` → `**320 Tier-1 benchmark families at seed and ~1,470 worth cataloguing overall**`. |
| `08-infrastructure-and-build.md` | 802 | `Launch (~300 entries, low traffic)` → `Launch (320 entries, low traffic)`. Cosmetic; the cost model does not move at +6.7%. |
| `10-visualization.md` | — | **No D2 edit.** Its `~300 nodes` at `14`:584 and its own scale figures belong to the visualization/matrix decision. |

### Sequencing notes for whoever executes this

1. Do `02-taxonomy.md` L268–297 first. Every other edit quotes numbers from it.
2. `14-roadmap.md` L397–428 is a deletion of ~32 lines; every `14` line number after 428 shifts by
   roughly −25 once it lands. Apply the `14` edits **from the bottom of the file upwards** (1268
   first, 37 last) or re-grep after each.
3. The 18→19 family-count edits listed here (`00`:575, `14`:103, 385, 482, 860, 1266) are the ones
   D2 forces because engineering-design stays in the seed. The remaining stale eighteens in `G1`
   (`03`:492, `09`:241, `10`:234, 241, and the `14` matrix lines) belong to the taxonomy and matrix
   decisions — do not fold them into this pass, or two decisions will edit the same lines.
4. Check 9d cannot go green until `taxonomy/domains.yaml` carries the three new fields and
   `scripts/taxonomy_stats.py` is extended. Land the document edits first and the check in Phase 0
   with the rest of the CI, but do not let it slip past Phase 0 — the whole point is that the next
   revision of these numbers is checked by a machine rather than by a reader who trusts a tilde.
