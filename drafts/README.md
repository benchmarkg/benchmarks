# drafts/

AI-drafted catalogue entries, before a human has checked them (05 §2, §4; 11 §F6, §G4). Nothing here
is built, published or citable. `bench build` never reads this directory, and `bench validate` reads it
only when you name it: `bench validate drafts/`.

- `benchmarks/<id>.yaml` holds one draft entry. It has `curation.verification_status:
  ai-drafted-unverified` and a `provenance` block, and it is validated by `schema/draft.py`.
- `sources/<src-id>.yaml` holds the snapshot of the page the draft was made from. Every quote in the
  draft is checked against it.
  - When `data/sources/` already holds a source for the URL, with a committed snapshot, no new file
    is written. The copilot drafts from that committed snapshot, checks every quote against it, and
    never fetches the live page. `--fresh-snapshot` takes a new snapshot instead.

## Making a draft

    uv run python -m tools.copilot.draft --url https://arxiv.org/abs/2310.06770 --out drafts/

- **What `--url` accepts:** an arXiv URL (a PDF or HTML link is read as its abstract page), a GitHub
  repository (read as its README), another PDF (this needs `pdftotext`), or a saved page.
- **With `ANTHROPIC_API_KEY` set,** the draft is made by the F6 model named in
  `config/ai-models.yaml`.
- **Without the key,** a pattern-only drafter fills a few fields (the arXiv id, the paper title, a
  "we introduce X" name, a licence phrase) and leaves every other field null. It calls no model.

## Reviewing a draft

`provenance.fields` has one row per drafted field. Each row gives:

- the field's confidence: `high`, `low` or `absent`;
- for a populated field, the verbatim quote behind it;
- for an `absent` field, the reason no value was kept.

The script, not the model, decided what stayed. A value survived only if:

- its quote is in the snapshot, and the value is inside its quote;
- any number in a written sentence also appears in its quote;
- a vocabulary value is a real term.

A rejected value never fails the whole draft. That field is set to null, and the rejection goes in
`provenance.rejected`, with:

- the value that was offered;
- the text it claimed as its quote;
- the reason it was refused;
- the stage: `vet` when it failed against the text the drafter was shown, `snapshot` when it failed
  against the stored source afterwards.

A rejected value is a lead, not a fact. Check it against the source like any other field.

Two more logs record what the copilot refused before drafting:

- `provenance.injection_spans` lists text cut from the source because it looked like instructions
  aimed at an AI system or at the catalogue, such as "ignore previous instructions" or "set the
  licence to MIT". No drafter saw that text, and it cannot be quoted. A paper about prompt injection
  loses its own example sentences this way, so read each span and judge it.
- `provenance.schema_violations` lists parts of the drafter's answer that were not drafted fields,
  such as an attempt to set `curation` or `lifecycle`. They were ignored.

To review:

1. Open the source and check each field against its quote.
2. Add each checked field to `provenance.fields_verified`, and set `verified_by` and `verified_at`.
3. Fill what the draft left null from the source, or leave it null.
4. Move the entry to `data/benchmarks/<family>/` and the source to `data/sources/<yyyy>/`, and have
   the source archived.
5. Raise `curation.verification_status` to what you actually did (05 §4).

The copilot will not overwrite a draft once `verified_by` or `fields_verified` is set.
