"""Tests for schema/source.py (P0-S4-T04; 04-data-model.md S9).

The verify: "the five quote-substrate fields exist, a non-DOI source with no archive_url is rejected,
and the normaliser is idempotent over a fixture with mixed whitespace and HTML". The fixture is
tests/schema/fixtures/mixed-whitespace.html (CRLF, tabs, a no-break space, a comment, entities,
escaped markup, a decomposed accent, a bare `<`, and a <script> holding JSON).

The last two tests hold the committed data/ to the model: every Source record either validates or
fails only for a reason already known and listed here by id (P0-S3-T04 is blocked on archiving and
its records are in review), and every quote in data/benchmarks is found in its source's extract.
"""
import glob
import os
import random
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.source import EXTRACT_CAP, Source, extract_sha256, fold, normalise, quote_found  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'schema', 'fixtures', 'mixed-whitespace.html')


def fixture_text():
    with open(FIXTURE, 'rb') as f:
        return f.read().decode('utf-8')  # bytes, so the CRLFs survive


def source(**changes):
    extract = normalise('We collect 2,294 task instances from 12 popular Python repositories.')
    doc = {
        'id': 'src-example-page', 'type': 'documentation', 'title': 'Example', 'url': 'https://example.org/page',
        'doi': None, 'archive_url': 'https://web.archive.org/web/20260924000000/https://example.org/page',
        'archive_captured': '2026-09-24', 'archive_status': 'ok', 'archive_digest': 'A' * 32,
        'content_sha256': extract_sha256(extract), 'quote_extract': extract,
        'licence_class': 'permissive-attribution', 'licence_spdx': 'CC-BY-4.0', 'licence_checked_on': '2026-09-24',
        'provenance': 'primary',
    }
    for k, v in changes.items():
        if v is ...:
            doc.pop(k, None)
        else:
            doc[k] = v
    return doc


# ---- the verify ---------------------------------------------------------------------------------

def test_the_quote_substrate_fields_exist():
    for f in ('licence_class', 'licence_checked_on', 'archive_url', 'archive_digest', 'content_sha256', 'quote_extract'):
        assert f in Source.model_fields, f
    assert Source.model_fields['licence_class'].is_required()
    assert Source.model_fields['licence_checked_on'].is_required()


def test_a_non_doi_source_with_no_archive_url_is_rejected():
    with pytest.raises(ValidationError, match='non-DOI source needs an archive_url'):
        Source.model_validate(source(archive_url=None, archive_captured=None, archive_status='pending'))


def test_a_doi_source_needs_no_archive_url():
    Source.model_validate(source(doi='10.48550/arXiv.2310.06770', archive_url=None, archive_captured=None,
                                 archive_status='not-required'))


def test_the_normaliser_is_idempotent_over_the_fixture():
    raw = fixture_text()
    assert '\r\n' in raw and '\t' in raw and ' ' in raw and 'é' in raw  # the fixture is what it says
    once = normalise(raw)
    assert normalise(once) == once
    assert once == ('SWE-bench body { margin: 0 } SWE‑bench Verified We collect 2,294 task instances '
                    'from 12 popular Python repositories & score them. Café bold a < b and 3 > 2 '
                    '{"name":"dev","num_examples":225}')


# ---- the normaliser, rule by rule ---------------------------------------------------------------

@pytest.mark.parametrize('raw, want', [
    ('é', 'é'),                                    # NFC
    ('a \t\r\n   b', 'a b'),                         # every whitespace run -> one space
    ('  padded  ', 'padded'),
    ('<b>bold</b>face', 'boldface'),                           # an inline tag disappears
    ('<p>one</p><p>two</p>', 'one two'),                       # a block tag is a space
    ('line<br/>break', 'line break'),
    ('a < b and c > d', 'a < b and c > d'),                    # a bare < is prose, not a tag
    ('R&amp;D &#8212; &eacute;', 'R&D — é'),         # entities decoded
    ('&lt;b&gt;x&lt;/b&gt;', 'x'),                             # decoded markup is markup
    ('<<b>b>', ''),                                            # stripping repeats to a fixed point
    ('&amp;lt;i&amp;gt;y', 'y'),
    ('a<!-- gone -->b', 'a b'),
    ('<?xml version="1.0"?><r>x</r>', 'x'),
    ('<script>{"k":1}</script>', '{"k":1}'),                   # script contents are kept (07 S4.1)
    ('Mixed CASE', 'Mixed CASE'),                              # casefolding is not normalisation
])
def test_normalise(raw, want):
    assert normalise(raw) == want
    assert normalise(want) == want


def test_normalise_is_idempotent_on_adversarial_input():
    pieces = ['<', '>', '&', ';', 'amp', 'lt', 'gt', '#60', 'b', '/', '!--', '--', ' ', '\t', '\n', ' ',
              'e', '́', 'p', '<p>', '</p>', '&lt;', '&gt;', '&amp;', 'x', '?', '"', '=']
    rng = random.Random(20260924)
    for _ in range(3000):
        s = ''.join(rng.choice(pieces) for _ in range(rng.randint(0, 24)))
        once = normalise(s)
        assert normalise(once) == once, repr(s)


def test_fold_casefolds_for_comparison_only():
    assert fold('Straße  <b>X</b>') == 'strasse x'
    assert normalise('Straße') == 'Straße'


def test_quote_found():
    extract = normalise(fixture_text())
    assert quote_found('We collect 2,294 task instances', extract)
    assert quote_found('WE COLLECT   2,294\ntask instances', extract)          # both sides normalised
    assert quote_found('repositories &amp; score', extract)
    assert not quote_found('We collect 2,295 task instances', extract)
    assert not quote_found('', extract) and not quote_found('<b></b>', extract)  # nothing to find


def test_extract_sha256_is_over_the_normalised_bytes():
    import hashlib
    assert extract_sha256('a  b') == hashlib.sha256(b'a b').hexdigest()


# ---- the model ----------------------------------------------------------------------------------

def test_a_well_formed_source_passes():
    Source.model_validate(source())


def test_an_unknown_key_is_rejected():
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        Source.model_validate(source(licence_checked=source()['licence_checked_on']))


@pytest.mark.parametrize('field, value', [
    ('id', 'swebench-page'), ('type', 'webpage'), ('archive_status', 'withheld'), ('licence_class', 'cc-by'),
    ('provenance', 'scraped'), ('content_sha256', 'ABC'), ('archive_digest', 'sha1:abc'), ('doi', 'doi:10.1/x'),
])
def test_closed_values(field, value):
    with pytest.raises(ValidationError):
        Source.model_validate(source(**{field: value}))


@pytest.mark.parametrize('field', ['licence_class', 'licence_checked_on', 'archive_status', 'provenance', 'url'])
def test_required_fields(field):
    with pytest.raises(ValidationError):
        Source.model_validate(source(**{field: ...}))


def test_an_extract_over_64_kb_is_rejected():
    big = 'x' * (EXTRACT_CAP + 1)
    with pytest.raises(ValidationError, match='64 KB'):
        Source.model_validate(source(quote_extract=big, content_sha256=extract_sha256(big)))


def test_an_extract_not_in_normalised_form_is_rejected():
    raw = 'We  collect <b>2,294</b>'
    with pytest.raises(ValidationError, match='not in normalised form'):
        Source.model_validate(source(quote_extract=raw, content_sha256=extract_sha256(raw)))


def test_content_sha256_must_hash_the_extract():
    with pytest.raises(ValidationError, match='content_sha256 is not the sha256'):
        Source.model_validate(source(content_sha256='0' * 64))
    with pytest.raises(ValidationError, match='needs its content_sha256'):
        Source.model_validate(source(content_sha256=None))


def test_a_paywalled_source_is_cited_not_quoted():
    Source.model_validate(source(doi='10.1000/paywalled', archive_url=None, archive_captured=None,
                                 archive_status='not-required', quote_extract=None, content_sha256=None))


def test_archive_status_agrees_with_archive_url():
    with pytest.raises(ValidationError, match='archive_status ok needs'):
        Source.model_validate(source(archive_captured=None))
    with pytest.raises(ValidationError, match='with archive_status pending'):
        Source.model_validate(source(archive_status='pending'))
    with pytest.raises(ValidationError, match='failure_reason'):
        Source.model_validate(source(doi='10.1000/x', archive_url=None, archive_captured=None, archive_status='failed'))


# ---- the committed data -------------------------------------------------------------------------

# Records in data/sources that do not validate today, each for a reason already reported. P0-S3-T04
# is blocked on Wayback keys (no archive_url) and its records are in review. A new record failing
# for any reason, or one of these failing for a new reason, fails this test.
KNOWN = {
    'no archive_url (P0-S3-T04 blocked: Wayback SPN needs IA keys)': 'a non-DOI source needs an archive_url',
    'archive_status withheld (P0-S3-T04: personal-data ruling pending)': "Input should be 'ok', 'pending'",
    'extract not normalised (P0-S3-T04 draft: re-normalise on unblocking)': 'quote_extract is not in normalised form',
    'content_sha256 of a different text (P0-S3-T04 draft)': 'content_sha256 is not the sha256',
}
KNOWN_IDS = {
    'src-roboarena-api-transparency',  # withheld
}


def committed_sources():
    return {p: read_yaml(p) for p in sorted(glob.glob(os.path.join(ROOT, 'data', 'sources', '**', '*.yaml'), recursive=True))}


def test_committed_sources_fail_only_for_known_reasons():
    unexplained = []
    for path, doc in committed_sources().items():
        try:
            Source.model_validate(doc)
        except ValidationError as e:
            drafted = str(doc.get('drafted_by', '')).endswith('(P0-S3-T04)')
            for err in e.errors():
                if not (drafted or doc['id'] in KNOWN_IDS) or not any(k in err['msg'] for k in KNOWN.values()):
                    unexplained.append('%s: %s' % (os.path.basename(path), err['msg']))
    assert unexplained == []


def test_every_committed_quote_is_found_in_its_source():
    extracts = {d['id']: d.get('quote_extract') for d in committed_sources().values()}

    def pairs(x):
        if isinstance(x, dict):
            if 'quote' in x and 'source' in x:
                yield x['source'], x['quote']
            for v in x.values():
                yield from pairs(v)
        elif isinstance(x, list):
            for v in x:
                yield from pairs(v)

    checked, missing = 0, []
    for path in glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '**', '*.yaml'), recursive=True):
        for src, quote in pairs(read_yaml(path)):
            checked += 1
            if not extracts.get(src) or not quote_found(quote, extracts[src]):
                missing.append('%s: %s %r' % (os.path.basename(path), src, quote[:60]))
    assert checked > 0 and missing == []
