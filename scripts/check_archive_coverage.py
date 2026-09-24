#!/usr/bin/env python3
"""Enforce the seven-day archival SLA over every Source record.

06-sourcing-and-scraping.md S7.1 softens 04 S12's tier-3 rule from an absolute to a deadline:
a non-DOI Source must carry `archive_url`, OR `archive_status: pending` with
`archive_requested_at` within the SLA, OR `archive_status: failed` with a recorded reason. A
Source nobody has tried to archive yet is within the SLA for seven days from its first ingest,
and a violation after that. DOI Sources are exempt.

    python scripts/check_archive_coverage.py                       # SLA 7d, as of now
    python scripts/check_archive_coverage.py --max-pending-age 7d
    python scripts/check_archive_coverage.py --now 2026-10-01T00:00:00Z --strict

Per non-DOI Source, first match wins:

  ok            archive_url present (archive_status must then be ok)
  failed        archive_status: failed with a non-empty failure_reason
  pending       archive_status: pending, archive_requested_at no older than the SLA
  not-required  archive_status: not-required with quote_extract null -- 04 S9's paywall case,
                citable but never quotable
  new           no attempt yet, first ingest no older than the SLA
  VIOLATION     anything else, including pending past the SLA, failed with no reason and
                not-required on a Source that is being quoted from

First ingest is the earliest of fetched_at, accessed and archive_requested_at: fetched_at alone
moves forward on every re-fetch and would let a Source age forever without ever falling due.

A status outside 04 S9's vocabulary (ok | pending | failed | not-required) is a WARNING when it
carries a failure_reason, because it is a recorded decision not to archive, and a VIOLATION
under --strict. `withheld`, written by P0-S3-T04 for a body that lists personal e-mail
addresses, is the one case today; it needs either a vocabulary entry or a ruling.

Exit 0 when there are no violations, 1 otherwise; the oldest violation is printed first.
"""
import argparse
import glob
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUSES = ('ok', 'pending', 'failed', 'not-required')


class Source:
    def __init__(self, path, record):
        self.path, self.record = path, record


def _yaml_load(f):
    # ruamel.yaml is the pinned loader (pyproject.toml); PyYAML is accepted so the check also runs
    # under a bare interpreter, as the task's verify does.
    try:
        from ruamel.yaml import YAML
        return YAML(typ='safe', pure=True).load(f)
    except ImportError:
        import yaml
        return yaml.safe_load(f)


def load_sources(root=ROOT):
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '*', '*.yaml'))):
        with open(path, encoding='utf-8') as f:
            rec = _yaml_load(f)
        if isinstance(rec, dict) and rec.get('id'):
            out.append(Source(path, rec))
    return out


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


def parse_age(s):
    m = re.fullmatch(r'(\d+)([dh])', s)
    if not m:
        raise argparse.ArgumentTypeError('age is <n>d or <n>h, e.g. 7d')
    n = int(m.group(1))
    return timedelta(days=n) if m.group(2) == 'd' else timedelta(hours=n)


def show(td):
    h = int(td.total_seconds() // 3600)
    return '%dd' % (h // 24) if h % 24 == 0 else '%dh' % h


def classify(r, now, sla, strict=False):
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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--max-pending-age', type=parse_age, default=timedelta(days=7))
    p.add_argument('--now', type=parse_time, default=None, help='evaluate as of this UTC time')
    p.add_argument('--strict', action='store_true', help='a status outside 04 S9 is a violation')
    p.add_argument('-v', '--verbose', action='store_true', help='list every Source, not only problems')
    a = p.parse_args(argv)
    now = a.now or datetime.now(timezone.utc)

    rows = [(s.record['id'],) + classify(s.record, now, a.max_pending_age, a.strict)
            for s in load_sources(a.root)]
    counts = {}
    for _, cls, _, _ in rows:
        counts[cls] = counts.get(cls, 0) + 1
    bad = sorted((r for r in rows if r[1] == 'VIOLATION'), key=lambda r: -(r[3] or timedelta(0)).total_seconds())
    for sid, cls, detail, _ in bad + [r for r in rows if r[1] == 'WARNING']:
        print('%-9s %s: %s' % (cls, sid, detail))
    if a.verbose:
        for sid, cls, detail, _ in rows:
            if cls not in ('VIOLATION', 'WARNING'):
                print('%-9s %s %s' % (cls, sid, detail))
    print('%d sources as of %s, SLA %s: %s' % (
        len(rows), now.strftime('%Y-%m-%dT%H:%M:%SZ'), show(a.max_pending_age),
        ', '.join('%s %d' % kv for kv in sorted(counts.items()))))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
