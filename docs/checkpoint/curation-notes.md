# 20-entry checkpoint: running curation notes

Written as each entry is curated (P1-S3-T01, P1-S3-T02 step 4: "as it happens, not afterwards"), for the
schema review in P1-S3-T04. Each note says what was awkward, what the workaround was, and whether a
`notes` field ended up carrying something that should have been structured.

The curator for every entry below is an agent ("agent (P1-S3-T01)" in `metrics/curation-rate.jsonl`).
It is the same curator throughout, so the alternation still controls for learning. But its minutes are
not a person's minutes, and P1-S3-T03 should say so before it uses them as the effort table's rate.
"Copilot on" means the F6 copilot's extractive drafter (`tools/copilot/draft.py --drafter extractive`).
That is the only drafter that runs without an API key. It gives the title, ids and dates, and drafts no
facets, so the copilot arm measures a weak copilot.

## Entries 1-10 at a glance (written after entry 10, for P1-S3-T03 and T04)

| # | entry | family | copilot | minutes |
| --- | --- | --- | --- | --- |
| 1 | superb | audio-speech | on | 10.0 |
| 2 | coco | vision | off | 16.8 |
| 3 | medqa | medicine-health | on | 8.6 |
| 4 | oc20 | chemistry-materials | off | 10.8 |
| 5 | proteingym | biology-genetics | on | 7.3 |
| 6 | libero | robotics-embodiment | off | 4.7 |
| 7 | the-well | physics | on | 5.4 |
| 8 | minif2f | mathematics | off | 5.0 |
| 9 | harmbench | safety-alignment | on | 3.5 |
| 10 | mmmu | multimodal | off | 6.1 |

Median 6.7 minutes over ten. With the copilot, 7.3 (n = 5); without, 6.1 (n = 5). The order effect is larger
than either. Minutes fall with position (the first two took 10-17, the last four 3.5-6), and the alternation
gives each arm the same positions only roughly. T03 should model position, not compare medians. Four caveats
belong with the numbers:

- The curator is an agent. Its minutes measure tool and network latency as much as reading, and a person's will
  be several times longer.
- The copilot is the extractive drafter. Over five entries it filled 1-5 of 24 fields, always the cheapest
  (title, ids, date, repository). It did not draft a single facet. The measured "speedup" is of this drafter,
  not of an LLM copilot.
- Archiving is inside the window, and Wayback's latency varied from seconds to minutes. Entry 4 was stopped
  before tooling work on the archiver (see below).
- Stage 3 records (failure logs) were read for COCO and consulted when choosing terms; the Stage 3
  classification records were not read before writing. Entries whose Stage 3 failures were open (the-well,
  harmbench) cite them instead of logging duplicates.

The findings that recur, most consequential first:

1. **`lifecycle` cannot say "not observed".** The vocabulary says leave it null; the schema requires a value
   and defaults to `active` (the-well). An omitted field silently asserts the benchmark is in use.
2. **Designed protocol and actual use diverge** (medqa: open-book designed, closed-book used; libero: lifelong
   designed, multitask used). `capability` and `designed_for_subjects` follow the design, and nothing records
   the dominant use.
3. **Hand-overs have no structure.** Submission servers moved or closed (coco, oc20, mmmu), maintainership moved
   by fork (minif2f), and access changed on a date (mmmu). `submission_channel`, `maintainer` and
   `data.access` each hold one value.
4. **Empty lists cannot say "unknown".** `independence_flags: []` and `submission_process: []` meant "not
   assessed" in some entries and "none" in others, distinguished only by a note.
5. **Board-less benchmarks need a literature search for liveness.** Five of ten have no leaderboard. Current
   use was evidenced by others' abstracts (libero, minif2f, harmbench, mmmu), and was not found for the-well.
6. **Script-rendered sites.** Six of ten benchmark sites or boards render by script and were read through
   their fragments, API records or app text, or not at all.
7. **Personal data beside cited facts** (contact lines in papers and READMEs, organiser handles in API
   records) needed narrow windows and a forbid-list in the extract builder, in five entries.
8. **Vocabulary ids that hide their scope** (`any-to-any-generation` for captioning, `rl-policy` for behaviour
   cloning, `simulation-surrogates` beside `fluid-dynamics`) cost two wrong first choices and one wrong gap
   record.
9. **The forecasting profile fires on surrogates.** The facet pair statistical-fit x scientific-surrogate-model
   resolves `forecasting`, so OC20 and The Well each had to waive lead_time and resolution_window, as
   Matbench Discovery and the Virtual Cell Challenge already did. That makes four waivers of the same two
   fields. The rule, not the entries, is wrong, and P1-S3-T04 should say so. The corpus tests surfaced it,
   not validation.
10. **`bench fmt` is a gate the curation loop never ran.** Entries written at 115 columns passed validation, then
   failed the fmt test. The formatter rewraps folded paragraphs but keeps their old breaks, which leaves orphan
   words. Each folded block had to be joined and reformatted. The curation tools should end with `bench fmt`.
11. **Key spellings are learned from errors.** `<field>_basis` and `<field>_note`, and `{flag, source, quote}`
   for an evidenced independence flag. The validator names the bad key, not the expected one.

## 1. superb (audio-speech; copilot on; 10.0 min)

- **The homepage did not answer** (superbbenchmark.org, 2026-10-10). Without it, `lifecycle` and `activity`
  rest on a 2021 paper. `activity: unknown` exists; `lifecycle` has no unknown, so it is `active` with a
  basis that says it was not read. A lifecycle that is unread looks the same as one that was checked.
- **`aggregation_policy` has no unknown.** The paper reports ten tasks separately and says nothing about
  an aggregate. The field was left at its default, and the reviewer note had to explain why. This is a
  structural gap: `curation.notes` is doing the work.
- **No audio-speech suite leaf.** ADR-0016 gives in-family suite subdomains to some families. Audio-speech
  has none, so a ten-task suite takes its largest group (4 of 10) as primary. Intent classification,
  slot filling and emotion recognition have no leaf at all. Logged: `taxonomy/_failures/2026-10-10-superb-001`.
- **`designed_for_subjects` cannot express a frozen encoder scored through trained probes.** Left
  empty. Logged: `2026-10-10-superb-002`. The same shape will recur for MTEB, BEND and linear-probe vision
  suites.
- **Per-constituent access.** `data.access` is one value for a suite whose constituents differ: IEMOCAP
  and VoxCeleb1 have their own terms. There is no per-constituent access, so the doubt sits in a note.
- **The PDF's contact line sits next to the release sentence.** The quote that names the leaderboard had
  to be moved off the first page, so the windowed extract would not pull in the authors' e-mail line.
  The extract builder now refuses an e-mail address. Nothing in the schema needed to change.
- **`comparability.material_extra`.** Picking `eligibility_track` for the constrained/unconstrained tracks
  took a reading of the vocabulary. `subset_used` was tried first and was wrong.

## 2. coco (vision; copilot off; 16.8 min)

- **Stage 3 had been here.** Six `taxonomy/_failures/` records on COCO, four of them since resolved by ADR or
  term revision, said where the hard calls were (lifecycle after the challenge ended, composite vs. one
  swept metric, maintainer type, subjects). Reading them is not copilot help. But it made this entry
  faster than a first-contact entry, and the two arms should be compared with that in mind. SUPERB had no
  Stage 3 records.
- **The site is script-rendered.** cocodataset.org loads each tab from `dataset/<tab>.htm`, so the Source is
  the fragment URL, not the URL a reader sees (`/#guidelines`). Nothing in the Source model says "rendered
  at X, fetched from Y". It went in `notes`.
- **The evaluation server moved twice.** The site still links competitions.codalab.org. CodaLab suspended
  that host, and the COCO pages there point to codalab.lisn.upsaclay.fr. `execution.submission_channel` (an
  Evidence) holds one quote; the move went in a `_note`. A dated history of channel moves would be
  structured, and it recurs for every CodaLab-hosted benchmark.
- **One `activity` for a family of tracks.** Box, mask, keypoint, stuff, panoptic and DensePose each have a
  server. Only the box server was read, and `activity` takes one value. Per-track activity would need
  subsets with their own lifecycle.
- **The tier and the admissibility flag disagree in plain reading.** `reproducibility_tier:
  not-independently-reproducible` (only the maintainers' server scores test-dev) sits next to
  `reproducible_by_third_party: true` (anyone can run a detector and submit). Each is right by its own
  definition. A reader of the card will see a contradiction; the tier's name says more than its test.
- **`submission_limit` has no quote.** It is a closed shape with a `source` only, so "5 per day" cannot be
  checked by the quote validator. Its sentence was added to the extract by hand.
- **A term I could not find by its name.** I logged "no captioning subdomain" and then deleted the record:
  `multimodal/any-to-any-generation` ("Generating output in one modality from input in another") covers
  image captioning. Its id reads like any-to-any models, not like captioning, and a list of ids is how a
  curator scans the vocabulary. The validator caught it only indirectly: Stage 3's classification record
  already used the term, and an uncited failure on a classified benchmark blocks. Pose estimation was
  already open from Stage 3.
- **Personal data in the page next to the cited fact.** The CodaLab page prints the organiser's account
  name beside the phase dates. The extract builder needed a narrower window and a forbid-list. That is the
  same problem as SUPERB's contact line, now on a web page.

## 3. medqa (medicine-health; copilot on; 8.6 min)

- **The copilot saved almost nothing.** It drafted 3 fields (title, arXiv id, date) and left 21 absent, and
  it set `curation.added_by` to the git user, not the curator. The minutes on this entry are reading,
  judgement and Sources, the same as without it.
- **Capability depends on the protocol.** The paper defines MedQA as open-domain QA over a released
  textbook collection. Almost every result since answers closed-book. knowledge-recall and
  context-integration are each right for one protocol, and `capability` is one list (logged:
  `2026-10-10-medqa-001`). `comparability.material_extra: tools_allowed` was the nearest way to say "with
  or without the corpus", and it is a stretch.
- **`designed_for_subjects` against use.** The design is retrieval-augmented. The use is instruction-tuned
  models prompted closed-book. The field asks about design, so the entry follows the paper. A reader
  looking for "benchmarks used on chat models" will not find MedQA by this facet.
- **`saturated` cannot be set, and nothing derives it yet.** A third-party board (Vals AI) archived MedQA as
  saturated, with the top three at about 96.4-96.5% on four options (headroom about 0.95). The schema
  rightly refuses a hand-set saturated. Without a ResultClaim the derivation has nothing to run on, so the
  entry says "active" and puts the saturation evidence in a basis. P1-S3-T04 should note that lifecycle
  stays stale until claims exist.
- **A third party's board as the only current evidence.** The maintainers publish no results. The only 2026
  evidence of use is Vals AI's re-run, which may be a perturbed variant ("bias evaluation"). There is no
  field for "evidence of use comes from a variant", so it is a reviewer check.
- **Data licence unknown, code licence known.** `dataset_licence: null` with a note. The code licence came
  from GitHub's API, not a quotable page, so `code_licence` has no Source. That is the same gap as COCO's
  code licence.
- **Huge script-and-style pages.** The Vals page is 470 KB, 450 KB of it inline CSS and JS. `normalise()`
  keeps script and style text, so a windowed extract around a quote can be all CSS. I stripped `<script>`
  and `<style>` before normalising and said so in the Source's notes. The project's normaliser has no such
  mode, so this Source's `content_sha256` is not reproducible by `normalise(raw)`.

## 4. oc20 (chemistry-materials; copilot off; 10.8 min)

- **The leaderboard moved, and the project's own site still points to the old one.** The EvalAI challenge
  ended on 2026-01-31, with every phase inactive. FAIR Chemistry's Hugging Face board now scores OC20.
  opencatalystproject.org's leaderboard page still links "the OC20 evaluation server". Only the API record
  and a Gradio app's text module showed this, because both boards render by script. This is the second entry
  out of four whose submission channel moved hosts (COCO: CodaLab to LISN).
- **Family or member.** Stage 3 classified "Open Catalyst (OC20/OC22)" as one corpus item. OC20 and OC22 have
  separate tasks, splits and boards, so the entry is OC20 alone, with a different id from the Stage 3 record
  (`open-catalyst-oc20-oc22`). Nothing links the two. The project-level grouping (Open Catalyst: OC20, OC22,
  OpenDAC) has no home; `lineage` may hold it, and P1-S3-T04 should say whether it should.
- **No field for the paper's journal DOI.** `external_ids` is a closed set, and `paper` holds an arXiv id only.
  OC20's paper is published in ACS Catalysis, and the DOI went into `released_note`.
- **Challenge-year test sets.** EvalAI held dated test-challenge splits (2021, 2022, and a 2023
  adsorption-energy set) beside the fixed test splits. Choosing between `versioned-releases` and `static`
  depends on whether those count as the benchmark's content. Recorded as a reviewer check.
- **Independence could not be read.** The maintainers build models for these tasks (UMA has an "oc20" head).
  Whether those models are ranked on the board decides `maintainer-competes-on-own-benchmark`, and the board
  renders by script. Left empty with a note. "Not assessed" and "none" look the same in `[]`. That is the
  third entry where `independence_flags: []` carries a note to say which one it means.
- **Two personal identifiers next to cited facts again.** The organiser's account name sits in EvalAI's
  record beside the dates, and a maintainer's e-mail sits in the board's submission notes. Narrow windows
  were needed for both.
- **Archiving the home page took longer than writing the entry.** Wayback already held a capture from
  2026-10-02. CDX answers intermittently (200, a 503 "Temporarily Offline" page, 200, a 60 s timeout, on
  four lookups of the URL), so the archiver missed it, and SPN2 refused the new capture as a duplicate four
  times. The timer was stopped before the tooling work. The archiver now asks CDX once more on a 5xx (a
  separate commit). The capture was recorded with the archiver's own writer, from a CDX answer read by hand.

## 5. proteingym (biology-genetics; copilot on; 7.3 min)

- **The copilot drafted one field, the name, from a phrase fragment ("we introduce ProteinGym,").** Its
  snapshot of the bioRxiv page did save a fetch: bioRxiv often refuses scripted requests, and the snapshot
  gave the posting date. It is the only copilot output that went into an entry so far.
- **A README did most of the work.** The repository README states the scope, metrics, aggregation,
  releases, contribution rules and licence in one MIT-licensed page. The fastest entries are the ones whose
  maintainers wrote such a page. The paper was needed only for the cross-validation schemes and ClinVar.
- **The site renders by script into an empty root.** It is the fourth benchmark site of five that does
  (COCO, OC20's boards, Vals AI's styles, ProteinGym). The leaderboard itself was never read for any of
  them.
- **`independence_flags` takes an object, not a term,** when the flag needs evidence
  (`{flag, source, quote}`), and the validator refuses a bare term. The `_source`/`_quote` sibling pattern
  that works elsewhere is refused here. Two shapes for "a term with its evidence" in one schema.
- **The same flag, judged differently on entry 1.** Applying `maintainer-competes-on-own-benchmark` here
  (the Marks Lab's models are ranked) showed that SUPERB's authors' models (Mockingjay, TERA, and HuBERT,
  which has SUPERB co-authors) are the same case. SUPERB was left empty with a note, and it is now
  corrected. An agent curator drifts too. A per-flag checklist in the vocabulary ("are any ranked systems
  the maintainers' own?") would make this a lookup.
- **`aggregation_policy` has a basis only under the `_policy_basis` spelling.** `aggregation_basis` is
  refused. The rule (`<field>_basis`) is regular, but nothing tells a curator it is the rule. Errors name
  the key, not the expected spelling.

## 6. libero (robotics-embodiment; copilot off; 4.7 min)

- **Designed protocol and actual use diverge, as with MedQA.** The paper's protocol is lifelong: tasks in
  sequence, scored by FWT, NBT and AUC. Almost every result since (vision-language-action models) is
  multitask success rate per suite, which is near saturation (97.1% average for OpenVLA-OFT, 2025). The
  capability (`continual-learning`) is right for the first and wrong for the second. Two benchmarks out
  of six now need "protocol as used" beside "protocol as designed". `subsets` can carry a suite, but
  nothing carries a protocol.
- **Evidence of use comes from a user's paper.** There is no leaderboard, and the maintainers' repository
  was last pushed in March 2025. `lifecycle: active` rests on a third party's abstract. There is no field
  for "most-cited recent result", so it sits in `lifecycle_basis` and `learned_entrant_evidence`.
- **`activity: no-submission-channel` has to prove an absence.** The quote is the site's navigation bar
  (paper, code, docs, datasets, no leaderboard). A quote can show what is there; it cannot show that
  nothing else is. COCO and MedQA had the same problem.
- **`rl-policy` for behaviour-cloned policies.** The term's name says reinforcement learning, and its test
  covers any learned controller. The id misleads, like `any-to-any-generation` for captioning.
- **The README carried the licences per component** (code MIT, data CC-BY-4.0) in one table. `code_licence`
  and `dataset_licence` took them directly, with quotes. This is the first entry where both licence fields
  are filled from one quotable source.

## 7. the-well (physics; copilot on; 5.4 min)

- **The vocabulary and the schema disagree on an unknown lifecycle.** dormant's exclusion test says "Where
  the sources show only that inactivity and are silent on current use, leave the field null and log it."
  The schema refuses null, and `lifecycle` defaults to `active`. `unknown` exists in lifecycle.yaml but
  only `activity` accepts it. So the entry says `active`, with a basis that says it was not observed. This
  is a schema defect for P1-S3-T04, and the most important one so far: a curator who omits the field gets
  `active` silently.
- **"Is anyone still using it?" is a literature search.** For a benchmark with no board, current use is
  shown only by others' papers. One arXiv API query did not find one. The project has no tool for "papers
  that report results on X". Ingestion (P5) may supply it later through claims, and until then lifecycle
  is guessed for every board-less benchmark.
- **A leaf I nearly missed again.** I first wrote `physics/fluid-dynamics` and then found
  `physics/simulation-surrogates`, which is exactly this benchmark. Picking a domain leaf means scanning
  228 ids, and the right one is easy to miss when the family has a natural "topic" leaf beside a "method"
  leaf. COCO's captioning was the same mistake.
- **Contact lines in a new form.** The README's contact line is `{rohana,mmccabe}@...`, which the extract
  builder's e-mail pattern does not match. A forbid-list on `@` caught it. The project's own personal-data
  check should be tested on brace-grouped addresses.
- **The copilot gave four fields** (title, arXiv id, date, repository), all correct and all the cheapest
  ones.

## 8. minif2f (mathematics; copilot off; 5.0 min)

- **Maintainership moved by fork.** OpenAI's repository is archived. Meta's fork maintains the statements,
  fixes them, adds informal versions, and refuses new proofs to limit contamination. `governance.maintainer`
  is one value and `homepage`/`repository` are one URL each. Nothing records "originally X, now Y". It is
  the third entry with a hand-over (COCO's server, OC20's board).
- **Versioning by commit.** The original froze v1 in a branch. The fork asks users to cite "the version you
  used by commit or date". `versions` could hold v1, but not the fork's moving state. `versioned-releases`
  fits only because a commit is a pin.
- **Ground truth with no reference answer.** A proof assistant's verdict is the truth. `ground_truth_source`
  has `none`, which reads as "no ground truth" rather than "the checker is the ground truth". Formal
  benchmarks need their own value.
- **Contamination was easy to evidence for once.** The fork's README states the concern, and the original
  publishes proofs beside test statements. `high` with two evidence items, the first entry where the
  sources settled it.
- **Stage 3's corpus item combined two benchmarks** (miniF2F and miniF2F-Dafny), like OC20/OC22. That is
  the third Stage 3 combination split at curation. Corpus ids and entry ids now differ for both.
- **No paper PDF was needed.** Two READMEs and an abstract gave everything quoted. The fastest entries
  (LIBERO, miniF2F, The Well) are the ones whose maintainers wrote a full README.

## 9. harmbench (safety-alignment; copilot on; 3.5 min)

- **Current use came from one API query this time.** An arXiv search for "HarmBench", newest first, gave
  five 2026 papers reporting on it. The Well's search found none. The difference is the name: "HarmBench"
  is a unique token, and "the Well" is two common words. Any automated liveness check by literature will
  miss benchmarks with ordinary names.
- **`submission_process: []` stands for "not known".** The site renders by script and the README describes
  no route, so neither `literature-only` nor `maintainer-run` could be justified. An empty list cannot say
  "unknown" as opposed to "none". The same ambiguity as `independence_flags: []`, now on a second field.
- **Two subjects, both legitimate.** HarmBench ranks attacks across models and models across attacks.
  `designed_for_subjects` took both (`attack-or-intervention-method` and `instruction-tuned-model`), which
  its test allows. The aggregate ranks two kinds of entrant, and `aggregation_policy` is one value for
  both.
- **The scorer is a released classifier, so `model-derived-metric`, not `model-graded-judge`.** The two
  terms' exclusion tests settle it cleanly. The classifier's version is a comparability condition
  (`judge_model`), although the vocabulary says it is not a judge. The condition's name and the term
  disagree.
- **The maintainers' own defence is ranked.** R2D2 is in the paper's own figures, so the flag applies, with
  a figure label as its quote. This is the third application of `maintainer-competes-on-own-benchmark`
  (after SUPERB and ProteinGym), each found in a different kind of evidence.

## 10. mmmu (multimodal; copilot off; 6.1 min)

- **Access changed mid-life.** Test answers were withheld behind EvalAI until 2026-02-11 and released on
  2026-02-12. `data.access` is now `fully-open`, contamination is `high` (the release is the route), and
  `activity` is `closed`. Every claim made before February 2026 was scored on a held-out set, and every
  claim since on a public one. `access_by_phase` exists for CASP's edition phases but is not shaped for "until
  this date". A dated access history, or the date as a claim condition, is needed to compare across that line.
- **The same EvalAI story as OC20, with a different ending.** OC20 moved its board to Hugging Face. MMMU
  closed its server and published the answers. Both are recorded only as notes and quotes. `submission_channel`
  holds one Evidence, not a history.
- **Human experts are entrants here.** College seniors answered their own subjects' questions and sit on the
  leaderboard. `designed_for_subjects: human-expert` and `ceiling_anchor_type: expert-average` both apply,
  from one source. Whether seniors count as "credentialed" is a reviewer check the vocabulary leaves open.
- **Notes need `<field>_note`, as with `_basis`.** `ceiling_anchor_note` was refused, and
  `ceiling_anchor_type_note` passed. It is the same rule as `aggregation_policy_basis`, and the error again
  named only the key.
- **The family again.** MMMU-Pro and Video-MMMU sit on MMMU's site and README. Stage 3 classified MMMU-Pro, not
  MMMU. The entry is MMMU alone, so the family has no record yet.

# Entries 11-20 (P1-S3-T02)

Same curator ("agent (P1-S3-T02)" in the timing ledger, the same agent as entries 1-10), and the same protocol.
The alternation continues: odd entries with the copilot, even without.

## 11. flores (language; copilot on; 8.7 min)

- **A gated dataset card hides the facts it would state.** FLORES+ is distributed through a Hugging Face
  dataset with automatic gating. Reading the card means accepting its terms with the user's account, and that
  was not done. The public API record gave the gate, the licence (CC-BY-SA-4.0), the splits and the last
  change. A JSON record is now the Source for `data.access` and `dataset_licence`.
- **A family with three editions and a change of hands.** FLORES-101 and FLORES-200 came from Meta AI.
  FLORES+ is OLDI's, a community initiative that takes new languages. One entry carries all three, and
  `governance.maintainer` names the current holder only. It is the fourth hand-over in eleven entries.
- **The hidden test split disappeared.** FLORES-101 kept its test split for an evaluation server. FLORES+
  publishes dev and devtest only, so devtest became the de facto test. `access` and `ground_truth_source`
  describe the family. Neither can say "the split results are reported on changed from held-out to public".
- **Names next to the cited sentence.** OLDI's home page lists its organisers right after the sentence on
  FLORES+, so the window had to shrink to three characters. That is the extract builder's sixth
  personal-data case.

## 12. humaneval (code; copilot off; 4.7 min)

- **No capability for writing programs.** The capability vocabulary has reasoning, knowledge, perception and
  agency terms but nothing for "produce a correct program from a specification". HumanEval's capability is
  left empty and the gap is logged (`2026-10-10-humaneval-001`). Every function-synthesis benchmark will hit
  it. The SWE-bench entries used `context-integration`, which fits repository-scale work but not a
  self-contained function.
- **"Body" is the reference solution, and it is published.** The paper lists each problem's "function
  signature, docstring, body, and several unit tests". The released file therefore contains the answers,
  and contamination is `high` on the paper's own words, the same reading as miniF2F's published proofs.
- **`base-model` is right for the design and wrong for the use.** The harness's stop sequences show the
  protocol is raw continuation. Most results since 2023 are from instruction-tuned models through variant
  prompts. This is the third entry where designed and used subjects differ.
- **A forbid-list that blocked a metric name.** Forbidding `@` (added for brace-form addresses) caught "pass@k".
  A text filter for personal data needs real address patterns, not a character.

## 13. tau-bench (agents-tooluse; copilot on; 6.2 min)

- **Three versions in two repositories.** τ-bench's own repository says its tasks are outdated and points to
  tau2-bench, which now holds τ³-bench. The maintainers publish a grading change with "results produced with
  tau2-bench < 1.0.1 are not comparable with >= 1.0.1". One family entry with `versioned-releases` fits, and
  `harness` as a comparability field carries the version. The repository move is only in notes.
- **The simulated user changes the score and has no field.** Every run pairs the agent with a user played by
  an LLM (`--user-llm`). The comparability conditions have `judge_model`, but the simulator is not a judge.
  Stage 3's eight `hosted-judge-dependency` proposals cover the reproducibility side (a hosted model in the
  loop). The comparability side has no proposal yet.
- **The subject terms already name this benchmark.** `model-in-benchmark-harness` cites "the default tau-bench
  agent" as its own example, so standard and custom tracks map to two terms directly. The vocabulary was
  written against the stress corpus, and entries from that corpus are faster to tag.
- **`reliability-consistency` has a clear test** (pass^k). It is the first entry where a capability is
  decided by the metric's definition alone.

## 14. climatebench (earth-climate; copilot off; 5.6 min)

- **The publisher refused the paper.** JAMES (Wiley) answered 403 to a scripted request for the open-access
  PDF. Crossref's record carries the abstract, the CC-BY licence and the date, so a registry record is the
  paper's Source. Anything beyond the abstract came from the README and the data record.
- **A successor announced a week ago.** ClimateBench v2 (arXiv, 2026-10-03, same first author) takes in v1's
  emulation task as one of its tiers, with a different design. Calling v1 "superseded" a week after v2's
  preprint is premature, and calling it "active" ignores v2. The vocabulary has no "successor announced"
  state; `under-revision` is for the content the entry names being reissued, which this is not quite.
- **The forecasting profile again.** The same waiver pair (lead_time, resolution_window) is needed for the
  fifth time. The rule should not fire on simulation surrogates.
- **ORCID and affiliation beside the creator's name.** The Zenodo record puts the creator's name, ORCID and
  affiliation in one JSON object, so the maintainer quote needed an 8-character window and a forbid on
  "orcid".
- **One person's account.** The repository and the data record belong to one researcher, so
  `maintainer_type: individual`. That is the key-person risk the term exists for, even for a benchmark with
  an institutional paper.

## 15. circuitnet (engineering-design; copilot on; 6.1 min)

- **A dataset with tasks, not a benchmark with a board.** CircuitNet calls itself a dataset. It earns a
  benchmark entry because its tasks have fixed metrics and learned entrants. The line between "dataset" and
  "benchmark" is the admissibility test (A5), and it was easy to apply here.
- **`scientific-prediction` stretched to engineering.** Its definition names physical, chemical, biological
  and Earth systems. Predicting a chip layout's congestion or IR drop is predicting a physical system's state,
  but an engineered one. The capability vocabulary has nothing for "predict a design's downstream property",
  so the stretch is flagged in the basis rather than logged.
- **Metric per task, borrowed from prior methods.** CircuitNet scores each task with "the same evaluation
  metrics as in the original studies". `evaluation_method` takes the union, and the per-task metrics would
  belong on Metric entities and subsets.
- **No fixed split in the sources.** The code's configuration chooses the split, and neither the paper nor
  the README states it. `contamination_risk` stays unknown for want of a scored split.

## 16. nle (games-planning; copilot off; 4.3 min)

- **The second move to a personal account and back to an organisation.** facebookresearch/nle is archived and
  says "find NLE at its new home" in one person's account, which GitHub now redirects to the NetHack-LE
  organisation. It is the sixth hand-over in sixteen entries. `governance.maintainer` names the current holder,
  and the history is a note.
- **The vocabulary names this benchmark in its examples.** `episodic-return` cites "NetHack in-game score", and
  `rl-policy`'s test already covers prompted language agents scored in RL environments. As with τ-bench, the
  stress corpus shaped the terms, and entries from it go faster.
- **A competition run on the environment.** The 2021 NetHack Challenge used NLE, with its own rules and board. It
  is an `Event` or its own entry, and the line between the two is not obvious to a curator. It was left out and
  flagged.
- **Low contamination for the right reason.** Scored episodes are generated from seeds at evaluation and do not
  exist beforehand. Of sixteen entries, this is the first `low` that the structure settles outright.

## 17. folio (reasoning-general; copilot on; 6.0 min)

- **A promised leaderboard that never came.** Since 2022 the README has said "A leaderboard will be releeased soon
  to obtain your results on the unreleased test set." The test split was never released and no server exists, so
  the designed headline cannot be produced, and every published number is on the public validation split. The
  schema can say `private-test-set` and `not-independently-reproducible`. It cannot say "the field reports a
  different split from the one the benchmark designates". `comparability.subset_used` carries it per claim, and
  the entry needs it as a fact.
- **Two licences for one dataset.** GitHub says CC-BY-SA-4.0 (v0.0), and Hugging Face says MIT (v2). Neither
  licence text was read. `dataset_licence` is one value; the entry records the GitHub one and notes the
  conflict.
- **A rule I did not know about.** `harness_availability: none` must come with the `no-reference-implementation`
  blocker, and the validator offered the fix. This was the first cross-field rule met through an error rather
  than read in advance.
