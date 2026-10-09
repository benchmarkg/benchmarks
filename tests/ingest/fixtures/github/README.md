# tests/ingest/fixtures/github

Synthetic GitHub REST responses for tests/ingest/test_github.py (P5-S5-T01), written by hand in the shape
api.github.com returns -- not captures. `fixture-org/alpha` has a licence, a homepage, topics, a CITATION.cff
(DOI under `identifiers`) and three releases (one a draft, all with release-note prose the adapter must drop);
`fixture-org/bravo` declares no licence, an empty homepage, no CITATION.cff and no releases; `fixture-org/gone`
answers 404. Every 200 carries an ETag, so a second run through FixtureTransport answers 304.
