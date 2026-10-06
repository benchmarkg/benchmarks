"""The seven-day archival SLA, as one classifier (06-sourcing-and-scraping.md S7.1).

06 S7.1 softens 04 S12's tier-3 rule from an absolute to a deadline: a non-DOI Source carries
`archive_url`, OR `archive_status: pending` with `archive_requested_at` within the SLA, OR
`archive_status: failed` with a recorded reason. scripts/check_archive_coverage.py reports it over the
repository and schema/validators.py's non-doi-archive rule blocks on it, so both read this module.

Standard library only: the script's verify runs it under a bare interpreter (P1-S2-T08).
"""
import re
from datetime import datetime, timedelta, timezone

STATUSES = ('ok', 'pending', 'failed', 'not-required', 'withheld')
SLA = timedelta(days=7)


def parse_time(v):
    """A timestamp or date, as a UTC datetime; None for null."""
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if hasattr(v, 'year'):  # a date
        return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
    s = str(v).strip().replace('Z', '+00:00')
    t = datetime.fromisoformat(s) if 'T' in s else datetime.fromisoformat(s + 'T00:00:00+00:00')
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def first_ingest(r):
    times = [parse_time(r.get(k)) for k in ('fetched_at', 'accessed', 'archive_requested_at')]
    times = [t for t in times if t]
    return min(times) if times else None


def show(td):
    h = int(td.total_seconds() // 3600)
    return '%dd' % (h // 24) if h % 24 == 0 else '%dh' % h


def classify(r, now, sla=SLA, strict=False):
    """(class, detail, age); class is VIOLATION, WARNING or one of the passing classes."""
    status = r.get('archive_status')
    reason = (r.get('failure_reason') or '').strip()
    if r.get('doi'):
        return 'doi-exempt', '', None
    if r.get('archive_url'):
        if status != 'ok':
            return 'VIOLATION', 'archive_url present but archive_status is %r' % status, None
        return 'ok', '', None
    if status == 'failed':
        return ('failed', reason, None) if reason else ('VIOLATION', 'failed with no failure_reason', None)
    if status == 'withheld':        # the personal-data exemption (P0-S3-T04, ruled 2026-10-05)
        if r.get('contains_personal_data') is True and reason:                        # get-default: absent is not true
            return 'withheld', reason, None
        return 'VIOLATION', 'withheld needs contains_personal_data true and a failure_reason', None
    if status == 'pending' and r.get('archive_requested_at'):
        age = now - parse_time(r['archive_requested_at'])
        if age <= sla:
            return 'pending', 'requested %s' % r['archive_requested_at'], age
        return 'VIOLATION', 'pending since %s, past the %s SLA' % (r['archive_requested_at'], show(sla)), age
    if status == 'not-required':
        if r.get('quote_extract') is None:
            return 'not-required', '', None
        return 'VIOLATION', 'not-required on a non-DOI Source that carries a quote_extract', None
    if status not in STATUSES and status is not None:
        if reason and not strict:
            return 'WARNING', 'archive_status %r is outside 04 S9 (%s); reason: %s' % (
                status, ' | '.join(STATUSES), reason), None
        return 'VIOLATION', 'archive_status %r is outside 04 S9 (%s)' % (status, ' | '.join(STATUSES)), None
    born = first_ingest(r)
    if born is None:
        return 'VIOLATION', 'no archive attempt and no date to age it from', None
    age = now - born
    if age <= sla:
        return 'new', 'first ingest %s, no attempt yet' % re.sub(r'\+00:00$', 'Z', born.isoformat()), age
    return 'VIOLATION', 'no archive_url, pending stamp or recorded failure %s after first ingest' % show(age), age
