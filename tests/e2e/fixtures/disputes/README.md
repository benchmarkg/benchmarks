# tests/e2e/fixtures/disputes/

Constructed dispute records for `tests/e2e/corrections.spec.ts` (P3-S10-T09). The root
`playwright.config.ts` points the site at this directory with `UAIBI_DISPUTES`, in place of
`data/disputes/`, which holds no dispute yet; nothing here is published.

None of these disputes was raised by anyone. Each position says it is constructed. Two name an
organisation the draft preview publishes, so the page's rule for naming a reporter (an `org-*` id the
corpus publishes as an organisation, never one of kind `individual`) has something to render. Every
other raiser must render as a neutral role: a published record of kind `individual`, `redacted`, an
`org-*` id the corpus does not publish, and a value that is no organisation id at all.
`tests/site/test_dispute_fixtures.py` holds every file to `schema/dispute.py`.
