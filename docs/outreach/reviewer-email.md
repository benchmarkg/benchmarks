# Reviewer outreach email

The first-contact message to a prospective domain reviewer (03 §12.2, 03 §6.5, 14-roadmap.md
"Domain reviewer recruitment starts in week 2"). Status: agent-drafted, awaiting review (P1-S4-T01).

## How to use it

- **Change one thing only: the paragraph marked `VARIABLE`.** Everything else goes out word for
  word, so every reviewer gets the same two asks and the same offer, and nothing about what we
  promised depends on who wrote that particular email.
- **The signature block** is set once for the whole programme and is not per-recipient.
- **Prerequisites before the first send.** The three things the email links to must exist for the
  recipient's family:
  - the subdomain list;
  - at least ten fully classified entries, as rendered pages;
  - that family's row of the coverage matrix.

  The roadmap wants "two or three entries in their domain already written" at the very least. The
  credit offer names `CITATION.cff`, which must exist, with a contributor list, before anyone is
  promised a place in it.
- **Who to send it to** is P1-S4-T02's list (`docs/outreach/reviewer-contacts.yaml`). Approach
  through the field's community first (a workshop organiser, a challenge's organising committee)
  and individuals second.
- **After a yes**, the 40-item instrument goes out as a separate message; it is not attached here.
  03 §6.5 puts its lead time at eight weeks, so for the freeze round, send by two months before
  the v1.0.0 freeze.

## Writing the variable paragraph

The paragraph is what stops the email reading as a form letter, so it has to be specific. Keep it
to 80–120 words and give it five parts, in this order:

1. **The greeting,** by name, at the start of the paragraph.
2. **Why them:** one concrete piece of their own work — a benchmark they maintain, a paper, a
   challenge they organised — and what in it bears on our classification. Name the work, and don't
   praise the person; praise reads as a template, and a specific reference doesn't.
3. **Their family,** named the way their field names it, not by our slug.
4. **What exists:** how many entries are already written in their field.
5. **The three links,** in the order the numbered list refers to them: subdomain list, the ten
   entries, the coverage-matrix row.

Skeleton, to be replaced whole:

> `VARIABLE` Dear [name] — [one sentence on their specific work and why it bears on this]. We have
> now written up [n] benchmarks in [the field, in its own words], and before we publish we would
> like someone who works in it to tell us where we are wrong. The three things this email asks
> about are here: [link: subdomain list], [link: ten entries], [link: coverage-matrix row].

---

**Subject:** Would you check our map of your field's AI benchmarks? About one hour

`VARIABLE` *(the personalised paragraph, as above)*

We are building an open index of AI benchmarks across every field, not only language models but
robotics, structural biology, chemistry, medicine, climate and the rest. Every entry is a plain
file in a public repository, every field in it traces to a primary source, and the whole thing is
published under CC BY 4.0. It is not a leaderboard. It never ranks results that were obtained under
different conditions, and it neither hosts benchmark data nor runs evaluations.

What we cannot do from outside your field is know whether we have it right. So we are asking a
small number of people for **one hour, on one domain**, looking at the three links above:

1. **The subdomain list.** What is missing? Which distinction does nobody in your field actually
   make? What are we calling by the wrong name?
2. **Ten entries.** Is any of this wrong? Is any of it embarrassing?
3. **One row of the coverage matrix.** Are these cells genuinely empty, or do we just not know about
   the work? This is the one we would value most: a falsely empty cell is the most damaging error we
   could publish, and someone in the field can spot one in seconds.

Comments by reply, in plain text, are all we need; no account and no git.

There is a **second ask**, and it is separate: you can say yes to the first and no to this one. It
is a **40-item blind re-classification**. We send forty benchmark descriptions and our published
definitions, without our labels, and you classify them. It takes about ninety minutes. It is what
lets us publish an agreement figure that measures people rather than a model agreeing with itself;
if we cannot find a second rater, we publish no figure at all rather than a machine one.

Neither ask comes with anything ongoing: no advisory role, no recurring meeting.

In return, and only as far as you want it:

- your name in the repository's `CITATION.cff`, so the release DOI cites you;
- your name, and your ORCID if you like, on every entry you reviewed and on your field's taxonomy
  page;
- co-authorship on the release DOI.

Everything is CC BY, so you can use any of it in your own work without asking, and correct or fork
anything you disagree with.

There is no deadline. If the answer is no, a one-line reply saying so is genuinely helpful, and so
is the name of someone better placed.

Thank you for reading this far.

[Sender name]
[Project name] · [site URL] · [contact address]
