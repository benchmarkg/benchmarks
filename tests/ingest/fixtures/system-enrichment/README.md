# System-enrichment fixtures (synthetic)

`openrouter/models.json` and `litellm/prices.json`, the two responses the enrichment adapters ask for, written by
`make_fixture.py` and compared byte for byte by `tests/ingest/test_system_enrichment.py`.

**Why synthetic.** Neither feed states a licence for its data, so neither is committed. The adapters were run live
on 2026-10-10: OpenRouter listed 458 ids forming 372 models (86 `:batch` routes share a base model's
canonical_slug), none matching a System exactly yet; LiteLLM's file held 4,032 keys, 47 of them matching, all held
under the licence veto.

**What is real.** The shape: OpenRouter's `{"data": [...]}` with every key a live model carries, no ETag on the
response (as on the live endpoint), and a `:batch` route sharing its base model's slug; LiteLLM's mapping of keys to
entries, `sample_spec` included, with an ETag.

**What is invented.** Every model, organisation, price and date, chosen so each case is named: an exact external-id
match, an exact alias match, two near misses a fuzzy matcher would take, and two models no System is.
