# Taxonomy drift check

`scripts/taxonomy_drift_check.py` is the `taxonomy_drift_check` of
[03-taxonomy-build-process.md](../_plan/03-taxonomy-build-process.md) §6.4, Option B (P1-S14-T03). A
language model from a different family than the one that drafted the entries re-classifies benchmarks
from the published definitions. The script then lists the terms where the model and the stored value
disagree, most often first. Those terms get definition review.

## What it is, and what it is not

It is a **defect detector**. A row of `metrics/taxonomy-drift.json` says: on these items, a model that
read this term's inclusion and exclusion tests disagreed with the stored value. That points at a
definition to re-read, in the same spirit as 03 §6.1 step 5, where a disagreement is a definition
defect by default.

It is **not an agreement statistic**, and it is not inter-rater reliability. The file holds counts
only: no kappa, no Jaccard, no F1, no percentage. `--check` fails a file that carries any of them. The
published, citable number is `irr_human` (03 §6.4, §6.5), and nothing from this file may be quoted in
its place. Three things limit what a row means (03 §6.4):

- The model is not a human, so its disagreement says nothing about how future contributors will tag.
- The model cannot open the links. It classifies from the benchmark's name and what it knows of the
  sources the links identify, so its priors can stand in for our definitions. A row is a lead, not a
  verdict.
- When the model says it does not know a benchmark well enough (`insufficient_information`), that
  item is listed under `not_compared` and is not counted.

## How a run works

- **Items.** `--scope irr`, the default, rates the 30 items of the blind instrument,
  `taxonomy/_irr/sample.yaml` (P1-S14-T01), against the Stage-3 classifications that the instrument
  hides. `--scope corpus` rates every curated entry under `data/benchmarks/` against its own facet
  fields.
- **The prompt.** It holds the published definitions of the facet's terms: label, definition,
  inclusion test and exclusion test, with no examples. It also holds the item's name and its
  primary-source links (home page, paper, arXiv id, DOI), and nothing else. The stored tags never
  appear in it. The script asserts this on every request before anything is sent (`blind()`), and the
  tests assert it again.
- **Order.** Item order, option order and request order are shuffled from `--seed`. If no seed is
  given, a fresh one is drawn. Either way the seed is recorded, so the run can be reproduced.
- **Answers.** The response schema lets the model answer only with the option ids it was shown. Code
  checks each answer again on the way in. An answer that is off the vocabulary, malformed or truncated
  is listed under `not_compared` and is never repaired.
- **Output.** `ranked` lists one row per (facet, term) with `defects`, split into `stored_not_chosen`
  and `chosen_not_stored`. Each row lists its items with both values. `not_compared` gives each
  item and facet that was left out, and why. `run` records the provider, model, date, seed, scope,
  `prompt_sha256` and `requests_sha256`. Output never goes under `data/` or `taxonomy/`.

## The state today

No run has been made. A run needs an OpenAI or Gemini API key, and none exists yet. Until one does,
`metrics/taxonomy-drift.json` does not exist and `python scripts/taxonomy_drift_check.py --check`
fails (exit 1). This is by design: a fake run never becomes the metric. `--check` refuses provider
`fake`, and a fake run may not write the default path.

## How to run it

The key goes in the Windows Credential Manager under service `uaibi`, with user name
`OPENAI_API_KEY` (or `GEMINI_API_KEY`). Set a spending cap on the provider's side first. The script
reads the key only from the environment variable of its own process, and never prints it.

**1. Dry run.** This reads no key and makes no network call. It writes the exact request bodies to a
scratch file and prints the request count, the prompt size and the output-token ceiling, so the run can
be priced first:

```sh
uv run python scripts/taxonomy_drift_check.py --provider openai --model MODEL --dry-run --out-prompts SCRATCH/drift-prompts.jsonl
```

At taxonomy 0.9.0, the IRR scope is 330 requests (30 items × 11 vocabularies) and about 1.4 million
input tokens.

**2. The IRR run, first.** The maintainer's rule is that the first live run covers only the 30-item
IRR sample. The key is loaded into the child process only, never into the shell:

```sh
uv run --with keyring python -c "import os,runpy,sys,keyring; os.environ['OPENAI_API_KEY']=keyring.get_password('uaibi','OPENAI_API_KEY'); sys.argv=['taxonomy_drift_check.py','--provider','openai','--model','MODEL','--max-requests','360']; runpy.run_path('scripts/taxonomy_drift_check.py', run_name='__main__')"
```

For Gemini, use `GEMINI_API_KEY` in both places and `--provider gemini`. Set `PYTHONUTF8=1` on
Windows. A model whose name says Claude or Anthropic is refused.

**3. Check, then commit.** Run `uv run python scripts/taxonomy_drift_check.py --check`, then commit
`metrics/taxonomy-drift.json` in a pull request like any other metric.

**4. The whole corpus, later.** Add `--scope corpus`. The script refuses a live corpus run until
`--out` holds a checked live run, which is the IRR run from step 2. A corpus run is roughly ten times
the IRR run; the dry run prints the exact figures.

## The cost cap

- `--max-requests` is required for a live run, and it is a hard cap. The plan is counted first, and
  the run is refused if it needs more requests than the cap. Every attempt, retries included, counts
  against the cap, and no attempt is made past it. Give it about 10% headroom over the plan for
  retries. A run that the cap stops short is still written, with `run.complete: false` (exit 4), and
  `--check` fails it.
- `--max-output-tokens` (default 4096) caps each answer, so output tokens are at most requests ×
  cap. An answer cut off at the cap is not compared. If many are, raise the cap.
- The provider-side spending cap is the backstop for both.

A key the provider refuses, an unknown model or a rejected schema stops the run at once with the
HTTP status and the provider's error code, and nothing is written (exit 3). Rate limits and server
errors are retried, honouring `Retry-After`. The request formats follow the providers' documented
APIs: OpenAI Chat Completions with a strict `json_schema`, and Gemini `generateContent` with a
`responseSchema`. They have not been run against the live endpoints, so the first IRR run is also
their first test.
