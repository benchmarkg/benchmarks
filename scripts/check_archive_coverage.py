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

`withheld` is the personal-data exemption (ruled 2026-10-05, P0-S3-T04): a body that lists people's
e-mail addresses is not captured, because a Wayback copy would publish them for good. It passes when
the record says contains_personal_data: true and gives its failure_reason, and is a VIOLATION
otherwise. Any other status outside the vocabulary (ok | pending | failed | not-required | withheld)
is a WARNING when it carries a failure_reason, and a VIOLATION under --strict.

--require-one-per-entry adds P1-S13-T03's assertion: every curated entry (data/benchmarks/<family>/*.yaml,
not _stubs/) cites at least one Source that carries a DOI or an archive_url ("archived"). An entry with none
passes only when one of its Sources failed or was withheld with a recorded reason ("recorded", the task's
"or a recorded failure reason"), and is listed so. Anything else, an entry whose Sources are all pending or
new, fails. A cited Source is any string in the entry that is a whole Source id, wherever it sits: `source`,
`sources`, a `*_source` field or an evidence row.

    python scripts/check_archive_coverage.py --require-one-per-entry      # P1-S13-T03's verify

Exit 0 when there are no violations, 1 otherwise; the oldest violation is printed first.
"""
import argparse
import glob
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# The classifier is shared with schema/validators.py's non-doi-archive rule; stdlib only, like this script.
from schema.archive_sla import STATUSES, classify, first_ingest, parse_time, show  # noqa: E402,F401


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


SRC_ID = re.compile(r'^src-[a-z0-9]+(?:-[a-z0-9]+)*$')
ARCHIVED = ('doi-exempt', 'ok')
RECORDED = ('failed', 'withheld')


def cited(node, out=None):
    """Every Source id an entry cites, wherever it sits."""
    out = set() if out is None else out
    if isinstance(node, dict):
        for v in node.values():
            cited(v, out)
    elif isinstance(node, list):
        for v in node:
            cited(v, out)
    elif isinstance(node, str) and SRC_ID.match(node):
        out.add(node)
    return out


def load_entries(root=ROOT):
    """(entry id, Source ids it cites) for every curated entry, not the stubs."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)).startswith('_'):
            continue
        with open(path, encoding='utf-8') as f:
            rec = _yaml_load(f)
        if isinstance(rec, dict) and rec.get('id'):
            out.append((rec['id'], cited(rec)))
    return out


def per_entry(entries, classes):
    """[(entry id, state, detail)]: archived, recorded or MISSING (06 S7.1, P1-S13-T03)."""
    out = []
    for eid, sids in entries:
        got = {sid: classes[sid] for sid in sids if sid in classes}
        if any(c in ARCHIVED for c in got.values()):
            out.append((eid, 'archived', ''))
        elif any(c in RECORDED for c in got.values()):
            out.append((eid, 'recorded', ', '.join(sorted(sid for sid, c in got.items() if c in RECORDED))))
        else:
            out.append((eid, 'MISSING', 'cites %s' % (', '.join('%s (%s)' % kv for kv in sorted(got.items()))
                                                      or 'no Source record')))
    return out


def load_sources(root=ROOT):
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '*', '*.yaml'))):
        with open(path, encoding='utf-8') as f:
            rec = _yaml_load(f)
        if isinstance(rec, dict) and rec.get('id'):
            out.append(Source(path, rec))
    return out






def parse_age(s):
    m = re.fullmatch(r'(\d+)([dh])', s)
    if not m:
        raise argparse.ArgumentTypeError('age is <n>d or <n>h, e.g. 7d')
    n = int(m.group(1))
    return timedelta(days=n) if m.group(2) == 'd' else timedelta(hours=n)






def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--max-pending-age', type=parse_age, default=timedelta(days=7))
    p.add_argument('--now', type=parse_time, default=None, help='evaluate as of this UTC time')
    p.add_argument('--strict', action='store_true', help='a status outside 04 S9 is a violation')
    p.add_argument('-v', '--verbose', action='store_true', help='list every Source, not only problems')
    p.add_argument('--require-one-per-entry', action='store_true',
                   help='also assert every entry cites a Source with a DOI or an archive_url (P1-S13-T03)')
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
    if not a.require_one_per_entry:
        return 1 if bad else 0
    entries = per_entry(load_entries(a.root), {sid: cls for sid, cls, _, _ in rows})
    missing = [e for e in entries if e[1] == 'MISSING']
    for eid, state, detail in missing + [e for e in entries if e[1] == 'recorded']:
        print('%-9s %s: %s' % (state, eid, detail))
    print('%d entries: %d with a DOI-bearing or archived Source, %d with only a recorded failure reason, %d with '
          'neither' % (len(entries), sum(1 for e in entries if e[1] == 'archived'),
                       sum(1 for e in entries if e[1] == 'recorded'), len(missing)))
    return 1 if bad or missing else 0


if __name__ == '__main__':
    sys.exit(main())
