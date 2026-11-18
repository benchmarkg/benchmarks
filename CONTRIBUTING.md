# Contributing

Most contributions to this index are one wrong value fixed or one missing benchmark added, and both
are a form on GitHub: no git, no files, no command line. You need a free GitHub account and a link
to a page that states what you are telling us. Most people need only the first section below.
Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md); a security problem goes to
the private report described in [SECURITY.md](SECURITY.md), not to an issue.

## Fix one thing

If an entry says something wrong, open the **Correction** form. On an entry's page on the site,
**Suggest a correction** opens it with the entry's id already filled in, and the small *correct*
link beside a field fills in the field as well. From anywhere else, open
[the Correction form](https://github.com/benchmarkg/benchmarks/issues/new?template=correction.yml)
and type the entry's id (for example `swe-bench`) and the field (for example `data.size`) yourself.
Then give the correct value, the URL of a page that states it, and the sentence from that page that
states it, word for word. Tick the box saying the value comes from that source and not from memory,
and submit. That is the whole contribution.

> **Screenshot placeholder: no image has been taken yet.** It is to show the Correction form as
> GitHub opens it from **Suggest a correction** on the SWE-bench page: the title already reads
> "Correction: swe-bench" and the *Entry id* box already holds `swe-bench`; below them come the
> *Field* box, an optional box for what the entry says now, the boxes for the correct value, the
> source URL and the sentence that states it, then two tick boxes and the button that submits the
> issue.

A correction is never a quiet edit. It lands as a change with its reason, the history keeps what
the entry said before, and your issue stays linked to it. If you think an entry is misleading
rather than wrong, or you speak for the benchmark or for a system it scores, the
[Dispute form](https://github.com/benchmarkg/benchmarks/issues/new?template=dispute.yml) fits
better: nothing is deleted, and your position appears beside the entry's, with its own source and
your relationship to what you dispute.

## Add a benchmark

If the index does not have a benchmark, open the
[New benchmark form](https://github.com/benchmarkg/benchmarks/issues/new?template=new-benchmark.yml).
It looks long, but most of it is optional. Seven answers are required, three you type and four you
pick from lists:

- **Benchmark name**, as its authors write it.
- **Homepage or paper URL**: the benchmark's own page, or its paper. This is the source every other
  answer must come from.
- **One-sentence description**: what an item asks and how it is scored, in at most 120 characters.
- **Primary domain**, **Capabilities measured**, **Evaluation method** and **What is evaluated**,
  picked from lists. The lists are generated from the index's controlled vocabulary, so a term
  cannot be invented by accident. If nothing fits, say so under *Anything we should know*.

Leave any optional field blank if you are not sure of it.

**Why a source URL and a quoted sentence are not optional.** An index that might be made up is
worse than no index, because a reader cannot tell which values to check. A wrong item count typed
from memory looks exactly like a right one: it sits in the same column and gets cited in the same
papers. A link plus the sentence that states the value lets a reviewer confirm a field in a minute
or two, and it is the one thing that cannot be produced from memory. That is also why a blank is
always better than a guess: a blank shows as not yet curated, a guess shows as a fact. The New
benchmark form has no box of its own for the sentence, so when you give a number or a date (the
number of items, the release date), paste the sentence that states it under *Anything we should
know*, with its link if it is on another page.

Three more forms cover the rest:
[New result claim](https://github.com/benchmarkg/benchmarks/issues/new?template=new-claim.yml), for
a score a system reached, with the conditions it was run under; the Dispute form, above; and
[Taxonomy term](https://github.com/benchmarkg/benchmarks/issues/new?template=taxonomy-term.yml), to
propose a new vocabulary term, which goes to a written decision record and two reviewers rather
than straight into the index.

## What happens next

A person reviews every contribution before anything changes in the index, and nothing you submit is
published until a curator has checked it against the sources you linked. What happens before that
review depends on the intake bot, which exists but is switched off.

**Today: a maintainer reads your issue.** The bot that validates the issue forms ships switched off:
its workflow is disabled, and it runs only once the repository variable `ISSUE_INTAKE_ENABLED` is
set to `true`, which it is not yet. So for now a maintainer reads each issue, replies on it, asks
about anything that does not check out, and opens the pull request that makes the change. The tick
box on each form saying that a bot handles the issue describes the bot as it works when it is on.

**When the bot is on.** For a new benchmark, the bot checks each answer, looks the benchmark up
under its names and aliases in case the index already has it, and validates the entry it would
write. If everything passes, it comments on your issue with the YAML it will write, in full, so you
can see exactly what would land, and then opens a pull request on a `contrib/<issue>-<id>` branch
and links it from that comment. The entry goes in as an unverified draft, outside the published
index, until a curator has checked each field against your sources and promoted it. If something
does not pass, the bot comments with the fields to fix and nothing else, labels the issue
`needs-fix` and leaves it open. Edit the issue and it checks again, replacing its own comment;
after three failed attempts it asks a maintainer to help, because by then the form is the problem,
not you. Its design budget is that first comment within 90 seconds of your submission, a target
that has not yet been measured on a real issue. For a correction, a result claim or a dispute, the
bot checks the answers in the same way and then hands the issue to a maintainer, who opens the pull
request. A taxonomy term goes to a decision record instead, and the bot opens no pull request for
it. The bot never merges anything.

**How you are credited: by the link.** The pull request for your contribution opens with "From
issue #N" and closes your issue when it merges, so the public record runs from the change to your
issue and your account. You are not added to the commit: every commit in this repository carries
only the project's own three identities, and no `Co-authored-by:` trailer names a contributor.

**How long it takes.** The targets are a maintainer's review within 72 hours of your issue, and a
median under seven days from issue to merged change. Both are targets, not measurements: the
repository holds no measurement of either yet. The seven-day median is the one we hold ourselves to,
because two people will sometimes miss 72 hours, and a promise that is routinely missed teaches
everyone to ignore it.

## Working in git

This section is for the minority who want to edit the YAML directly: bulk edits, lineage and subset
changes, schema-adjacent work, and anything the forms do not model. Everything above works without
it.

You need git, Python 3.12 and `uv`. Fork the repository on GitHub, then:

```sh
git clone https://github.com/<you>/benchmarks.git
cd benchmarks
git switch -c add-<id>
uv run bench new benchmark --id <id> --domain <family>/<subdomain> --from-source <url>
# replace every TODO from a cited source, and leave null what no source states
uv run bench fmt
uv run bench validate --changed-only
```

On Windows, set `PYTHONUTF8=1` first. `bench new` writes the entry's file from a template, with
every required field stubbed and commented, and validation fails while any placeholder remains. Commit, push the branch
to your fork, and open a pull request against `main`. In its description, quote the source
sentence for every number or date you add or change, with its URL: that is the evidence a reviewer
checks. [GOVERNANCE.md](GOVERNANCE.md#who-must-review-what) lists what each kind of change needs and
how many reviewers. Fixing a wrong number is the easiest change in the repository; a vocabulary or
schema change is deliberately the hardest, with a decision record in `adr/` and two reviewers.

Credit works as it does for an issue. Every commit on `main` carries only the project's own
identities, so your change is committed under them when it lands, and your pull request stays the
public record that it was yours.
