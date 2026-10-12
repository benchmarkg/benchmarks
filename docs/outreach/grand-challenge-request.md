# Grand Challenge: the permission request

The message to Radboud UMC DIAG, who run grand-challenge.org, asking whether this project may read the
challenge list through their REST API and republish the metadata as structured facts. Status: agent-drafted
for P5-S6-T06; **the maintainer sends it**, through the site's contact form or to the DIAG team, and records
the answer.

## Why it is needed

- 06 §3.8 plans an adapter over `https://grand-challenge.org/api/v1/challenges/`: 264 medical-imaging
  challenges with status, dates, submission types and publications, the cheapest route to non-LLM breadth.
- The site's robots.txt disallows `/api/` for every user agent (read 2026-10-09 and again 2026-10-12), and
  the project's fetch gate honours robots.txt, so P5-S6-T06 is blocked.
- 06 §8.4 already lists Grand Challenge on the licence checklist: "Terms for automated collection and
  redistribution of challenge metadata", to ask Radboud UMC DIAG. This message asks both questions at once.

## The message

> **Subject:** Permission to read the challenges API for an open benchmark catalogue
>
> Hello,
>
> We maintain an open, citable catalogue of AI benchmarks across scientific and engineering fields
> (https://github.com/benchmarkg/benchmarks). Medical imaging is one of its largest families, and Grand
> Challenge is the best record of it: each challenge's status, dates, submission types and publications.
>
> Your robots.txt disallows `/api/` for all crawlers, so we have not read the API, and we would like to
> ask before we do. Two questions:
>
> 1. **May we read `/api/v1/challenges/`?** One paged pass over the public challenge list, at most one
>    request every two seconds, never in parallel, about once a month, identified by the user agent
>    `UAIBI/0.1 (+https://github.com/benchmarkg/benchmarks)`. We back off on any error and never retry a
>    server error quickly. If you would prefer a different route (a periodic export, a different endpoint,
>    or another schedule), we will use that instead.
> 2. **May we republish the metadata as structured facts?** For each challenge we would record its title,
>    URL, status, dates, submission types and the publications it lists (as citations), linking back to the
>    challenge page and attributing Grand Challenge. We would not copy descriptions, logos or any
>    participant data, and we write our own text. The catalogue's data is published under CC BY 4.0. If
>    some of these fields should not be republished, please tell us which.
>
> If the answer is no, we will curate the challenges by hand from the public pages instead, and cite them.
>
> Thank you for running Grand Challenge.
>
> [Name]
> for the benchmark catalogue, https://github.com/benchmarkg/benchmarks

## After the answer

- **Yes to both:** record the reply as quoted text in `ingest/sources.yaml` (06 §8.4) and unblock P5-S6-T06
  (`next_task.py unblock P5-S6-T06`). The fetch gate (`ingest/http/policy.py`) treats robots.txt as
  absolute and has no exemption today, so the adapter's task also adds one: a written-permission entry in
  `ingest/policy.yaml` for `grand-challenge.org/api/v1/challenges/` that cites the quoted reply. The adapter
  keeps the 2-second throttle whatever the reply says.
- **Yes to reading, no or partly to republishing:** the adapter writes only the fields the reply allows; the
  rest stay `_suggested` for a curator.
- **No, or no reply after four weeks:** P5-S6-T06 stays blocked, and medical-imaging challenges are curated
  by hand from their public pages, which robots.txt allows.
