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
