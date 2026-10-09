# tests/ingest/fixtures/arxiv

One captured OAI-PMH window for tests/ingest/test_arxiv_oai.py (P5-S5-T04): `verb=ListRecords&set=cs&
metadataPrefix=arXivRaw&from=2026-10-06&until=2026-10-06` from https://oaipmh.arxiv.org/oai, fetched
2026-10-09 through the fetcher's gate. The full day ran past 2,600 records over at least three pages of
1,300; these two pages keep 100 of them verbatim -- the first 60 of page 1, and 40 of page 2 chosen so the
window holds new papers, revisions and metadata-only updates (20, 37 and 43). The first page's
resumptionToken is renamed `fixture-set-cs-2026-10-06-p2` and the second page's is empty, which is how
OAI-PMH ends a list. Among the revisions are v2 resubmissions of papers first posted years earlier, which
06 S3.4 says a harvest by modification datestamp brings in.

arXiv metadata is CC0 1.0 (REUSE.toml's annotation for these files).
