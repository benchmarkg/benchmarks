# Quality triage

Phase 1 exits on "Zero validation errors; quality warnings triaged rather than suppressed"
([14-roadmap.md](../_plan/14-roadmap.md), Phase 1 exit criteria). Tier 4 never blocks, and that is
deliberate ([04-data-model.md](../_plan/04-data-model.md) S12: a red X breeds compliance, a visible
dashboard better behaviour). Tier 3's warnings do not block either. So neither tier, on its own, shows
whether anybody looked. This page and
[data/_analysis/warning-triage.yaml](../data/_analysis/warning-triage.yaml) record that somebody did
(P1-S13-T04).

```sh
bench validate --tier all --json | python scripts/check_warnings_triaged.py              # the verify
bench validate --tier all --json | python scripts/check_warnings_triaged.py --markdown   # the table below
```

## How a warning is triaged

Every warning and quality finding is either **fixed** in the data, or listed in the triage file under
a decision:

- **accepted:** the signal is right and stays on the dashboard;
- **deferred:** a named `owner` clears it, either a ledger task or a pull request.

Each decision carries a `reason`, `decided_by` and `decided_on`. It lists its findings line by line by
`entity`. A line adds a `detail` where the rule fires more than once per entity, or where the rule's
subject can change: the subset and its dropped terms, the waived fields, the submission process, the
archive state. A line may also add a `note` that says why for that line.

No rule is switched off. A finding that matches no line fails the check, and so does a blocking
finding. A decision covers one subject, so when that subject changes (a subset drops another term, a
Source moves from pending to failed), the old line stops matching and the new state is triaged
afresh.

A line that no longer matches any finding is a warning resolved since its triage. The check lists it
and fails only under `--strict`, so a fix never has to wait on the triage file.

A new entry adds findings of its own (no-baseline, for one). The pull request that adds the entry also
adds the triage lines, the same way it updates the corpus pins.

## The account, 2026-11-17

`bench validate --tier all --json` on main at a36fb3d (after the sweeps, #183-#201) reported
**0 blocking findings, 157 tier-3 warnings and 1,001 tier-4 quality signals: 1,158 in all**.

This pull request fixes 16 of them, and the other 1,142 are triaged:

<!-- gen: bench validate --tier all --json | python scripts/check_warnings_triaged.py --markdown -->
| Tier/rule | Findings | Accepted | Deferred | Untriaged |
| --- | ---: | ---: | ---: | ---: |
| 3/lifecycle-unobserved | 4 | 4 | 0 | 0 |
| 3/private-server-submission | 23 | 23 | 0 | 0 |
| 3/reference-grader | 38 | 0 | 38 | 0 |
| 3/subset-drops-terms | 87 | 85 | 2 | 0 |
| 4/condition-completeness | 10 | 10 | 0 | 0 |
| 4/liveness-stale | 13 | 0 | 13 | 0 |
| 4/material-waived | 11 | 11 | 0 | 0 |
| 4/no-baseline | 306 | 0 | 306 | 0 |
| 4/stub-identity-unreviewed | 592 | 0 | 592 | 0 |
| 4/stub-unratified | 44 | 0 | 44 | 0 |
| 4/unarchived-source | 14 | 11 | 3 | 0 |
| **total** | **1142** | **144** | **998** | **0** |
<!-- /gen -->

### Fixed (16)

| Rule | Was | Fix |
| --- | ---: | --- |
| tagline-length | 3 | Shortened the taglines of mmmu, proteingym and the-well to fit the 120-character card. |
| unarchived-source | 8 | These 8 Sources carry an arXiv DOI but still said `pending`. The record dates from a 2026-09-23 Save Page Now refusal, made before their DOIs were recorded. A DOI Source is exempt from archiving, so they now read `not-required`, like the other 1,238 DOI Sources. |
| subset-drops-terms | 5 | A review of all 92 subset capability overrides found 9 wrongly dropped terms. Seven are restored here. Five of those subsets now match their parent and inherit its terms (digital-typhoon reanalysis and cross-basin, guacamol goal-directed, hanabi ad-hoc, test-of-time tot-semantic). In the other two (big-bench-hard date-understanding, livebench mathematics), a restored term narrows the drop but other terms stay dropped, so they are triaged with a new detail. |

### Accepted (144)

- **subset-drops-terms (85):** every remaining drop was checked against the published definitions of the
  dropped terms. Each line says why the subset does not exercise them.
- **private-server-submission (23):** a private test set does not imply a submission server. The
  results come from the maintainer running every model (`maintainer-run`), from organisers re-running
  entrants' code (`sandboxed-rerun`), from live votes (`live-arena`), or only from papers
  (`literature-only`). Each line says which.
- **lifecycle-unobserved (4):** `lifecycle` is null because the sources read do not show whether the
  benchmark is in use. Each entry already has the source-silent failure record the rule asks for.
- **material-waived (11):** each waiver states on the entry why a material comparability field does not
  apply.
- **condition-completeness (10):** these claims were chosen adversarially for their thin conditions
  (P3-S5-T02, T03). Keeping them off frontier lines is exactly what the rule is for.
- **unarchived-source (11):** Save Page Now failed with a recorded reason: the origin blocks the
  crawler, the page is gone, it only redirects, or the host is refused. 06 S7.3 keeps such a capture
  as `failed` rather than retrying it forever.

### Deferred (998), by owner

| Rule | Findings | Owner |
| --- | ---: | --- |
| stub-identity-unreviewed | 592 | P3-S3-T04: whether each generated System stub is one system is a human review recorded per file. |
| no-baseline | 306 | P3-S6 and P4-S2-T05, which draft Baselines from primary sources once the Metric records exist. Writing them now would invent the baseline 04 S12 warns against. |
| stub-unratified | 44 | P3-S2-T07: a person ratifies each proposed id (04 S3). |
| reference-grader | 38 | Phase 3. The grader at reference conditions belongs on an EvalConditions record shared with that benchmark's claims (P3-S5, P3-S7, and P3-S9-T01's SOTA rule). The rule turns blocking when an entry reaches full verification. |
| liveness-stale | 13 | The first annual sweeps of the two families no ledger task covers: #202 (engineering-design, 1 entry) and #204 (general-intelligence, 12). |
| subset-drops-terms | 2 | #203. The physionet-challenge 2024 tasks score real scans against synthetic training images, but the cited Source's extract left that section out, so #203 re-reads it into the extract and restores the term. |
| unarchived-source | 3 | The archiver, for 2: src-epoch-benchmarks-gpqa-diamond after the 24-hour re-capture window (16:30 UTC on 2026-11-17), and src-sceneparsing-csail-eval after a transient 503. A follow-up, for 1: re-point src-livebench-ai-main-js at the current script bundle. |

## Who decided

Every decision here is agent-drafted (`decided_by: agent (P1-S13-T04)`), because P1-S13-T04's
executor is agent-draft. A person accepts or amends each decision when reviewing the pull request.
