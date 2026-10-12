# tests/fixtures/ai-provenance/

The trees tests/test_ai_provenance.py builds throwaway git repositories from (P1-S2-T04). They are not data: nothing
here is under the repository's own data/, so neither the build nor check 9i reads them.

- `clean/` is the control: a reviewed benchmark and its source. The checker passes on it when a person commits it.
- `draft/` adds a record with `curation.verification_status: ai-drafted-unverified` under data/, which check 9i fails.
- The bot-committer case is `clean/` committed by `uaibi-ai-worker[bot]`, which the committer check fails; the same
  tree committed by the issue-form bot with a `Co-authored-by:` trailer, or with an `ingest:` subject, passes.
