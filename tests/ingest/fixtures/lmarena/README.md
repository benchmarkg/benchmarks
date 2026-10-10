# LMArena fixture

The responses the LMArena adapter (`ingest/adapters/lmarena.py`) asks for, for five arenas of
`lmarena-ai/leaderboard-dataset` at commit `e16f902` (2026-10-10), in `ingest/http/fixture.py`'s format.
`make_fixture.py` wrote them from a live download; it says how.

**What is real.** Every row in every parquet is LMArena's, verbatim (CC-BY-4.0; REUSE.toml): the top 30 of the
`overall` category by rank, and for text, text_style_control and webdev the top 5 of one other category. The
metadata (`api.json`) is the Hub's own response with its siblings cut to these five arenas.

**What is not.** The parquet bytes are pyarrow's re-encoding of the pruned rows, so each file's LFS sha256 and size
in `api.json` were recomputed to match them, and the CDN URL each resolve URL redirects to is named by that hash
(the live one is a signed URL that expires).

The five: `text` and `text_style_control` (the style-control pair), `webdev` (the existing `webdev-arena`
benchmark and metric), `video_edit` (10 rows upstream, under the cap of 25) and `agent` (the IPS schema).
