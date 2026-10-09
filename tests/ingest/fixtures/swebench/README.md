# SWE-bench leaderboard fixture (synthetic)

`page.html` and `page.html.headers.json` are what `make_fixture.py` writes, byte for byte;
`tests/ingest/test_swebench.py` regenerates them and fails if they differ.

**Why synthetic.** The leaderboard page at https://www.swebench.com/ ends "All rights reserved", and our
Source record for it (`data/sources/2026/src-swebench-leaderboard.yaml`) classes it `no-redistribution`.
04 S9 lets a record of that class live nowhere, so a capture of the page may not be committed, not even
here. The adapter was checked against a live capture held only on the developer's machine. The
comparison is in the P5-S6-T03 pull request.

**What is real about it.** The shape:
- five leaderboards holding 13, 24, 180, 84 and 22 results: 06 S3.7's 323, which the live page still
  held on 2026-10-09;
- every key a real result carries, including the optional `mini-swe-agent_version` and
  `per_instance_details`;
- the same mix of types:
  - `agent_org` null on about a third of rows;
  - `checked` true, false, null, or the string `false (See README.md for info on how to get your
    results verified)`;
  - `cost`, `instance_cost` and `instance_calls` (a float mean) null on most rows;
  - `logs` and `trajs` as `s3://swe-bench-submissions/...`, a relative path, `false` or null;
  - `logo` a list or null;
- the inline `<script type="application/json" id="leaderboard-data">` the adapter extracts.

**What is invented.** Everything else: every agent, organisation, model, date, score, folder and URL.
The first four Verified rows are pinned, so the tests can name each case:
1. a checked submission with a warning, a cost and an effort;
2. one with no `agent_org`;
3. one with an unusable log link and an off-vocabulary effort;
4. one whose `checked` is a value the adapter has never seen.

The logo paths in the page carry a salt, so a test can rotate them, as the real page's CDN does, without
changing the leaderboards.
