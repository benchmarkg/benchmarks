# The bot identity: `uaibi-bot`

- **Tasks:** P2-S6-T03 and the bot half of P5-S3-T01 (07-ingestion-infrastructure.md §6.1;
  08-infrastructure-and-build.md §7.3)
- **Recorded:** 2026-09-29

## What exists

| | |
| --- | --- |
| Account | [`uaibi-bot`](https://github.com/uaibi-bot), a machine user created 2026-09-29 |
| Membership | member of the `benchmarkg` organization, with **Write** on `benchmarkg/benchmarks` and nothing else |
| Token | fine-grained personal access token, resource owner `benchmarkg`, repository `benchmarks` only |
| Permissions | Contents: read and write; Pull requests: read and write; Metadata: read (implicit) |
| Created / expires | 2026-09-29 / **2026-12-28** (90 days) |
| Secret | `UAIBI_BOT_PAT`, a repository Actions secret (to set: see below) |
| Checked | 2026-09-29: the token authenticates as `uaibi-bot`, and has push access to `benchmarkg/benchmarks` and no admin |

The repository moved from the personal account `intelligence-benchmark` to the `benchmarkg`
organization on 2026-09-29 for exactly this: a fine-grained token can only be scoped to a
repository owned by the token's own account or by an organization it belongs to, so a
collaborator on a personal repository could hold nothing narrower than a classic token that
reaches every repository the bot can.

## Why not `GITHUB_TOKEN`

A pull request opened with the workflow's ambient `GITHUB_TOKEN` does not run other workflows
unattended. GitHub creates its `pull_request` runs in an approval-required state, and someone with
write access must start them from an "Approve workflows to run" banner (07 §6.1, checked
2026-09-24). Every ingest PR depends on `pr-validate.yml` running on it without a human, because
branch protection is to require that check. With the ambient token, each bot PR would wait for a
click before its checks even started: a second approval step on every ingest PR, and an easy one to
click through without reading. A PAT, or a GitHub App installation token, avoids that, and those are
the two routes GitHub's documentation names.

This is still an assumption until a bot-opened PR is seen to trigger `pr-validate.yml`: P5-S3-T01's
verification (`gh pr view <n> --json statusCheckRollup` returns a non-empty check list). It cannot
be run while the repository's workflows are switched off (since 2026-09-25).

## The expiry, which fails silently

An organization's fine-grained tokens must expire. `benchmarkg` blocks any over 366 days, and it
blocks rather than warns. An expired token shows up as an authentication failure inside a
scheduled job, not as an error anyone sees (07 §6.1). So:

1. The expiry date is in `ingest/state/secrets.json`, which the staleness report reads (07 §9), so
   it counts down rather than lapsing.
2. **Renew before 2026-12-14**, two weeks ahead. Signed in as `uaibi-bot`: Settings → Developer
   settings → Fine-grained tokens → the token → Regenerate. Then run
   `gh secret set UAIBI_BOT_PAT --repo benchmarkg/benchmarks` and update the dates in
   `ingest/state/secrets.json`.

## Migrating to a GitHub App

Move to a GitHub App installation token when the PAT's rate limit or its renewal round becomes the
cost. The App gets 5,000 to 12,500 requests an hour and has no expiry to renew (07 §6.1). The path:

1. Create a GitHub App owned by `benchmarkg`, with repository permissions Contents: read and write
   and Pull requests: read and write, and no webhook.
2. Install it on `benchmarkg/benchmarks` only.
3. Store the App ID and its private key as repository secrets, and mint an installation token in
   each job (for example with `actions/create-github-app-token`, pinned by SHA as 08 §6 requires).
4. Replace `secrets.UAIBI_BOT_PAT` in `archive-sources.yml`, `linkrot.yml` and the ingest workflows
   with that token, confirm a bot PR still triggers `pr-validate.yml`, then revoke the PAT.

Commits then carry the App's identity (`<app>[bot]`) instead of `uaibi-bot`. That keeps bot commits
separable from human curation in `git log`, which is the first reason 07 §6.1 gives for a bot identity.

## Not done yet

- `UAIBI_BOT_PAT` is not yet a repository secret; a maintainer sets it.
- `main` has no branch protection or ruleset. 07 §6.1's design assumes branch protection requires
  `pr-validate.yml`, and that is P0-S6's to set up once the workflows are switched back on.
- No ruleset yet limits which branches the bot may push to (the intake bot's `contrib/*`, the
  ingest jobs' `ingest/*`). A fine-grained token cannot do that; a ruleset can.
