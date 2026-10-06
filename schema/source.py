"""`Source`, the provenance backbone, and the quote substrate (P0-S4-T04; 04-data-model.md S9).

Every claim in the project hangs from a Source. Five of its fields are what the week-1 quote
validator needs (14-roadmap Phase 0): `licence_class` and `licence_checked_on`, which the licence
firewall keys on; `archive_url` and `archive_digest`, the capture a quote is checked against and the
digest link-rot detection compares; and `content_sha256` with `quote_extract`, the committed
normalised text that makes "this quote appears in this source" checkable at any commit without
committing the source body (05 S11's metadata-only invariant).

The normalisation is fixed, and 04 S9 says why it has to be one function: "must be identical in the
extractor and the validator, or the check silently passes on everything". `normalise()` is that
function, and the only one:

    NFC -> strip HTML/XML (tags removed, entities decoded) -> collapse every whitespace run to one
    space -> strip leading/trailing space;  casefold for comparison only (`fold`)

Three choices 04 S9's one-line pipeline leaves open, made here:
  - Entities are decoded, since `&amp;` in a stripped page would otherwise never match a quote's
    `&`. Decoding can expose markup (`&lt;b&gt;`) and stripping can expose more (`<<b>b>`), so both
    repeat until nothing changes, which is what makes `normalise` idempotent by construction.
  - A tag is `<` followed by a letter, `/`, `!` or `?`. A bare `<` in prose ("a < b") survives. A
    block-level tag becomes a space (`<p>a</p><p>b</p>` reads "a b"); an inline tag disappears
    (`<b>a</b>b` reads "ab").
  - The contents of <script> and <style> are kept as text: SWE-bench's leaderboard data is the JSON
    inside a <script> element (07 S4.1), and quotes are taken from it.

Casefolding happens only in `fold()`, at comparison, never in what is stored.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

EXTRACT_CAP = 64 * 1024  # bytes of UTF-8; 04 S9: "capped at 64 KB, METADATA NOT CONTENT"

_COMMENT = re.compile(r'<!--.*?-->', re.S)
_TAG = re.compile(r'<(/?)([A-Za-z][A-Za-z0-9:-]*)\b[^<>]*>|<[!?][^<>]*>')
_BLOCK = frozenset("""address article aside blockquote br dd div dl dt figcaption figure footer form h1 h2 h3
    h4 h5 h6 header hr li main nav ol p pre section table tbody td tfoot th thead tr ul""".split())
_WS = re.compile(r'\s+')


def _strip_markup(text: str) -> str:
    text = _COMMENT.sub(' ', text)

    def tag(m: re.Match) -> str:
        return ' ' if m.group(2) and m.group(2).lower() in _BLOCK else ''
    return _TAG.sub(tag, text)


def normalise(text: str) -> str:
    """04 S9's normalisation. Idempotent: normalise(normalise(x)) == normalise(x)."""
    prev = None
    while prev != text:
        prev = text
        text = _strip_markup(html.unescape(text))
    text = unicodedata.normalize('NFC', text)
    return _WS.sub(' ', text).strip()


def fold(text: str) -> str:
    """The comparison form: normalised, then casefolded. Never stored."""
    return normalise(text).casefold()


def extract_sha256(extract: str) -> str:
    """`content_sha256` for an extract: the sha256 of its normalised UTF-8 bytes."""
    return hashlib.sha256(normalise(extract).encode('utf-8')).hexdigest()


def quote_found(quote: str, extract: str) -> bool:
    """The quote-substring check (14-roadmap week 1): the quote appears in the source's extract."""
    q = fold(quote)
    return bool(q) and q in fold(extract)


# ---- the model --------------------------------------------------------------------------------

SourceId = Annotated[str, StringConstraints(pattern=r'^src-[a-z0-9]+(-[a-z0-9]+)*$')]
Url = Annotated[str, StringConstraints(pattern=r'^https?://\S+$')]
Doi = Annotated[str, StringConstraints(pattern=r'^10\.\d{4,9}/\S+$')]
Sha256 = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
CdxDigest = Annotated[str, StringConstraints(pattern=r'^[A-Z2-7]{32}$')]  # Wayback CDX: base32 SHA-1
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

SourceType = Literal['paper', 'preprint', 'repository', 'leaderboard-page', 'dataset-card', 'blog-post',
                     'documentation', 'dataset-export', 'personal-communication', 'regulatory-document']
# withheld (P0-S3-T04, ruled 2026-10-05): deliberately not captured because the body holds personal data, which a
# public Wayback capture would publish for good. It needs contains_personal_data true and a failure_reason.
ArchiveStatus = Literal['ok', 'pending', 'failed', 'not-required', 'withheld']
LicenceClass = Literal['permissive-attribution', 'share-alike', 'non-commercial', 'no-redistribution', 'unlicensed']
Provenance = Literal['primary', 'pwc-archive', 'hf_space_tag', 'vendor-doc', 'secondary']
# A Source's own reliability as a citation, weakest first (P5-S8-T02; 06 S3.18 and S7.3: "an
# un-archivable source is a fact about that source's reliability and should lower its verification
# level"; 00 S5.1: it "lowers that source's own reliability rather than stopping a contribution").
# It is NOT the ResultClaim ladder of taxonomy/verification.yaml, which grades how a number was
# produced; it grades whether the page a claim cites can still be read.
#   lost          link_status dead and no capture: the citation points at nothing (14's Phase 5 exit
#                 criterion 3 is that none exists)
#   unarchivable  archive_status failed: Save Page Now refused it, or it was dead before anyone captured it;
#                 or withheld: not captured on purpose, because the page holds personal data
#   pending       no capture yet, one requested or due (06 S7.1's seven-day SLA)
#   archived      a capture on the record, or a DOI, which needs none (04 S12)
# It is a function of the record rather than a model field: it is derived, never hand-set, so a
# failed capture lowers it without anyone remembering to, and it reads a raw record because the
# three lower rungs are exactly the records the model's strict tier-1 archive rule refuses.
RELIABILITY = ('lost', 'unarchivable', 'pending', 'archived')
Reliability = Literal['lost', 'unarchivable', 'pending', 'archived']


def reliability(record: dict) -> Reliability:
    """RELIABILITY for a Source record (a mapping, as read from data/sources/)."""
    doi, url, status = record.get('doi'), record.get('archive_url'), record.get('archive_status')  # get-default: absent is null
    if record.get('link_status') == 'dead' and not url and not doi:                               # get-default: unchecked is not dead
        return 'lost'
    if status in ('failed', 'withheld'):
        return 'unarchivable'
    return 'archived' if url or doi or status == 'not-required' else 'pending'


class Source(BaseModel):
    """04 S9's Source. Unknown keys are errors.

    The fields after `notes` are not in 04 S9's example record. `archive_requested_at` and
    `failure_reason` are written by ingest/archive_sources.py (P1-S2-T08; 06 S7.3); `cited_by` is
    read by tools/build/feed.py. The rest were introduced by P0-S3-T04's draft Source records to
    describe what their extracts are, and are modelled so those records load; whether they stay is
    that draft's review, and 04 S9 should list whichever do.
    """
    model_config = ConfigDict(extra='forbid', frozen=True)

    id: SourceId
    type: SourceType
    title: Text | None = None   # an API endpoint (a JSON body) has no title
    url: Url
    doi: Doi | None = None
    authors: list[Text] | None = None
    publisher: Text | None = None
    published: date | None = None        # the source's own date
    accessed: date | None = None         # when a human read it
    fetched_at: datetime | None = None   # when a machine last retrieved the bytes
    archive_url: Url | None = None
    archive_captured: date | None = None
    archive_status: ArchiveStatus
    archive_digest: CdxDigest | None = None
    content_sha256: Sha256 | None = None
    quote_extract: str | None = None
    licence_class: LicenceClass
    licence_spdx: Text | None = None
    licence_checked_on: date
    provenance: Provenance
    notes: str | None = None

    archive_requested_at: datetime | None = None
    failure_reason: Text | None = None
    cited_by: list[Text] = Field(default_factory=list)
    content_bytes: int | None = Field(default=None, ge=0)
    quote_extract_mode: Literal['full', 'windows'] | None = None
    quote_extract_basis: Literal['normalised-text', 'raw-body'] | None = None
    quote_extract_sha256: Sha256 | None = None
    quote_extract_redactions: int | None = Field(default=None, ge=0)
    licence_basis: Text | None = None
    contains_personal_data: bool | None = None
    drafted_by: Text | None = None
    # A dead URL a curator replaced with a live copy of the same document (P5-S8-T02). The id, derived from
    # the original link, stays; this says which link it was, so a scaffold that meets it again knows the record.
    repointed_from: Url | None = None

    # The link-rot re-check (06 S7.2; P5-S8-T01, tools/check_links.py writes them). `body_sha256` is
    # the accepted digest of the page -- the first check's, or the one a curator accepted after a
    # `changed` -- and a check never moves it; `link_changed_sha256` is what the page reads now when
    # it differs, kept until a curator accepts or rejects it.
    link_status: Literal['live', 'changed', 'suspect', 'dead'] | None = None
    link_checked_at: datetime | None = None
    link_detail: Text | None = None
    body_sha256: Sha256 | None = None
    link_changed_sha256: Sha256 | None = None

    QUOTE_FIELDS: ClassVar[tuple[str, ...]] = (
        'licence_class', 'licence_checked_on', 'archive_url', 'archive_digest', 'content_sha256', 'quote_extract')

    @model_validator(mode='after')
    def _archive(self):
        # 04 S12 tier 3 as 06 S7.1 softens it: a non-DOI Source with no archive_url says why -- pending,
        # failed with its reason, or not-required and never quoted (04 S9's paywall case). The seven-day
        # deadline on pending needs a clock, so it is tier 3's (schema/archive_sla.py), not the model's.
        if self.doi is None and not self.archive_url and not (
                self.archive_status in ('pending', 'failed', 'withheld')
                or (self.archive_status == 'not-required' and self.quote_extract is None)):
            raise ValueError('%s: a non-DOI source needs an archive_url, or archive_status pending, failed or '
                             'withheld (06 S7.1, 04 S12 tier 3); archive_status %s' % (self.id, self.archive_status))
        if self.archive_status == 'withheld' and not (self.contains_personal_data is True and self.failure_reason
                                                      and not self.archive_url):
            raise ValueError('%s: withheld is for a body holding personal data: it needs contains_personal_data '
                             'true, a failure_reason, and no archive_url' % self.id)
        if self.archive_status == 'ok' and not (self.archive_url and self.archive_captured):
            raise ValueError('%s: archive_status ok needs archive_url and archive_captured' % self.id)
        if self.archive_url and self.archive_status in ('pending', 'failed'):
            raise ValueError('%s: an archive_url with archive_status %s' % (self.id, self.archive_status))
        if self.archive_status == 'failed' and not self.failure_reason:
            raise ValueError('%s: a failed capture states its failure_reason (06 S7.3)' % self.id)
        return self

    @model_validator(mode='after')
    def _link(self):
        if (self.link_status is None) != (self.link_checked_at is None):
            raise ValueError('%s: link_status and link_checked_at are set together' % self.id)
        if (self.link_status == 'changed') != (self.link_changed_sha256 is not None):
            raise ValueError('%s: link_changed_sha256 is set exactly when link_status is changed' % self.id)
        return self

    @model_validator(mode='after')
    def _extract(self):
        q = self.quote_extract
        if q is None:
            if self.content_sha256 is not None and self.quote_extract_mode != 'windows':
                raise ValueError('%s: content_sha256 with no quote_extract to hash' % self.id)
            return self
        if len(q.encode('utf-8')) > EXTRACT_CAP:
            raise ValueError('%s: quote_extract is %d bytes, over the 64 KB cap (04 S9)' % (self.id, len(q.encode('utf-8'))))
        if self.quote_extract_basis == 'raw-body':
            return self  # a raw body is kept as fetched; quote_found() normalises both sides anyway
        if normalise(q) != q:
            raise ValueError('%s: quote_extract is not in normalised form -- store normalise(text) (04 S9)' % self.id)
        if self.content_sha256 is None:
            raise ValueError('%s: a quote_extract needs its content_sha256 (04 S9)' % self.id)
        if self.quote_extract_redactions:
            # A redacted extract is no longer the fetched text: content_sha256 stays the body's hash,
            # and the extract carries its own, as a windows extract does.
            if self.quote_extract_sha256 is None:
                raise ValueError('%s: a redacted quote_extract needs its own quote_extract_sha256' % self.id)
        elif self.quote_extract_mode in (None, 'full') and self.content_sha256 != extract_sha256(q):
            raise ValueError('%s: content_sha256 is not the sha256 of the normalised extract (04 S9)' % self.id)
        if self.quote_extract_sha256 is not None and self.quote_extract_sha256 != extract_sha256(q):
            raise ValueError('%s: quote_extract_sha256 does not match the extract' % self.id)
        return self
