# tests/ingest/fixtures/liveness

Synthetic inputs for tests/ingest/test_liveness.py (P5-S7-T01) and for the fixture dry run of
ingest/liveness.py, written by hand: no benchmark, host or response here is real.

- `root/` is a stand-in repository tree. `data/benchmarks/` holds five records with only the fields
  the probe reads. `metrics/liveness/` holds three earlier weeks for `bravo-cold`.
- `http/` holds recorded responses in ingest/http/fixture.py's format (`<name>` and
  `<name>.headers.json`), keyed by URL. A URL it does not hold raises FixtureMiss, and a robots.txt
  it does not hold answers 404.

The five benchmarks, as of 2026-11-23:

| Benchmark | What it shows |
| --- | --- |
| `alpha-live` | A push 22 days old, a fresh dataset, a readable board and a live homepage: `actively-maintained`. |
| `bravo-cold` | An archived repository last pushed 2024-06-01, a dataset last modified 2024-05-20, a board whose fingerprint has not changed since our first observation on 2025-09-29, and a homepage on its fourth consecutive 404. The result is `abandoned`, and every signal has been cold for twelve months, so it gets the one proposal. Its repository answers 304 to the ETag recorded in its history. |
| `charlie-blocked` | A homepage behind an anti-bot challenge and a board whose robots.txt disallows us: `unobservable`, never dead. |
| `delta-contested` | A repository silent since 2023. The computed `abandoned` is withheld by the 30-day quarantine on its first observation, and no proposal is opened because `maintenance_status_contested` is set. |
| `echo-quiet` | A push 357 days old and a curated board date 368 days old: `slow`, and not cold for twelve months. |

The fingerprint in bravo-cold's history is the one `ingest.liveness.fingerprint` computes from
`http/bravo-board.html`. The tests pin that equality, so a change to the normalisation shows up as a
test failure, not as an apparent change on the board.
