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
