# data/disputes/

One file per standing or closed dispute, `data/disputes/<dispute-id>.yaml`, validated by
`schema/dispute.py` (05-repository-and-workflow.md §8).

Disputes are never resolved by deletion. The contested claim stays, gains an entry in its
`disputed_by[]`, and renders with both positions visible: the claim's figure with its sources
(`claim_sources`) and the dispute's position with its own (`evidence`). A dispute is `open` until it is
`resolved-claim-corrected`, `resolved-claim-retained` or `withdrawn`, and only an open dispute makes a
claim count as disputed for the SOTA rule in 12-analytics-and-trends.md §3.3.

Removal and erasure requests are recorded here too, with the requester's identity redacted where they
ask (05 §8.1).

Every record here is published on the site's `/corrections/` page and in `/feed/corrections.xml`, open
disputes first and shown as unresolved (P3-S10-T09). The index names organisations, never individuals:
the page names whoever `raised_by` gives only when it is an `org-*` id the corpus publishes as an
organisation. Any other value, a handle, `redacted` or an unpublished id, is never printed; the page
gives the neutral role `disputant_relationship` implies ("a third party", "the evaluated party", "a
reader"). A correction whose commit carries a `Correction:` trailer naming a dispute id
(`Correction: dispute-x-2026-09`) is credited to that dispute's raiser in the same way; a correction no
record speaks for says that no reporter is recorded. A commit's author is never read for this: three
organisation accounts make every commit.
