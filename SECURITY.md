# Security

This file covers three things and no more (05-repository-and-workflow.md §8): how to report a
vulnerability, what the issue-intake bot may and may not do, and where to send a removal or
personal-data request.

**Contact:** [contact address]. We acknowledge within **5 working days** and give a substantive
response within **20**.

## Reporting a vulnerability

Report a vulnerability in the site, the build, the ingestion jobs or the bot to the contact address
above, not in a public issue. We follow a **90-day coordinated-disclosure window**: we fix, or say
publicly why we will not, within 90 days of your report, and we credit you unless you ask us not to.

## The issue-intake bot

The issue-intake bot turns an issue form into a pull request (05 §6). It reads untrusted input, and
a bot that reads untrusted issue bodies and opens pull requests is a privilege-escalation surface,
the one part of this project's supply chain that is uniquely ours. So it is built to these rules:

- It never runs code a contributor supplies, and never interpolates issue text into a shell
  command. Issue bodies are parsed as data and written as YAML.
- It proposes changes as a pull request, never a push to `main`, and a human reviews every one.
- It acts as the machine account `uaibi-bot`. Its token reaches this one repository, with contents
  and pull-request permissions only, and expires every 90 days (`docs/bot-identity.md`).

**Where things stand (2026-09-29):** the bot account and its token exist, and the intake bot
itself is not yet deployed. Two protections this design relies on are not yet in place:
protection of `main` that requires the validation check, and a ruleset limiting the bot to its own
branch prefixes. Until they are, treat a bot pull request with the same care as any contributor's.

## Removal and personal-data requests

The positions on removal, correction and personal data are set out in
05-repository-and-workflow.md §8, and in brief:

- A record is never made to disappear. A disputed fact is answered with a dated statement, a
  withdrawn benchmark is marked retracted or deprecated, and a field that is genuinely not ours to
  publish is removed while the entry stays.
- Named domain reviewers and their ORCIDs are published with consent, and withdrawn on request from
  the current data and the next release.
- Author names on Source records are bibliographic metadata, and stay.
- Git history is not rewritten, because rewriting it breaks every commit hash anyone has cited. A
  contributor who asks to be de-identified going forward is.

Send a request to the contact address above. Every removal or erasure request and its outcome is
recorded in `data/disputes/`, with the requester's identity redacted where they ask.
