#!/usr/bin/env python3
"""build/derived/ingest_accounting.json: the four-rule row accounting for the Epoch bulk ingest (P3-S4-T03).

    uv run python scripts/epoch_rule_accounting.py                  # epochdl/ -> build/derived/ingest_accounting.json
    uv run python scripts/epoch_rule_accounting.py --check          # and exit 1 unless every row is accounted for
    uv run python scripts/epoch_rule_accounting.py --zip PATH       # a bundle as served, not the unpacked copy
    uv run python scripts/epoch_rule_accounting.py --batch PATH     # a named IngestBatch, not the newest Epoch one

14 Phase 3 sorts every Epoch row into exactly one of four rules, with a default for the rest:

    epoch-run-public-log    Epoch-run file, an Inspect .eval log on a -public bucket     828
    epoch-run-private-log   Epoch-run file, an Inspect .eval log on a -private bucket    459
    epoch-run-no-log        Epoch-run file, log URL blank                                263
    external-scrape         one of the external/scraped files                            5,048
    unmatched (default)     matches no rule above                                        0 expected

"Any row matching no rule is assigned self-reported with verification_rule: unmatched, and the count of
unmatched rows is published on the trust page. If that count is ever non-zero, the adapter has met a file shape
it was not built for and somebody needs to look." Here a row is unmatched when its file has no mapping stanza,
when its stanza names a log column the file does not have, or when its log URL is on neither bucket. Each
unmatched group is listed with its file and reason, and the count is written even when it is zero.

The rules classify what a row *presents*; the rung each one assigns comes from ingest/verification.py's
verification_rule (P3-S4-T01), so the two cannot disagree. A public-log row is independent-reproduction only while
its transcript answers its HEAD; an unreachable one is maintainer-verified and needs-scrutiny, and the bulk run
(P3-S4-T06) reports that split with verification.tally(). This script never touches the network.

--check fails on any unmatched row (the artifact is still written, with the count), and unless the four rules and
`unmatched` sum to the batch's claims_written. The batch is --batch, or
else the newest data/_ingest/batches/ingest-epoch-*.yaml; its per-file row counts must also match the snapshot's,
or the accounting is of a different snapshot from the one the batch ingested. Until the bulk run commits a batch
there is no claims_written, so the rules are held to the snapshot's own row counts (epoch.counts(), what that
batch will record) and the artifact says so in `claims_written_basis`.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest import verification as v  # noqa: E402

OUT = os.path.join(ROOT, 'build', 'derived', 'ingest_accounting.json')
EPOCHDL = os.path.join(ROOT, 'epochdl')
BATCHES = os.path.join(ROOT, 'data', '_ingest', 'batches')
UNMATCHED = 'unmatched'
EPOCH_PRIVATE_LOG_HOSTS = frozenset({            # the two -private buckets 04 S7 names; HEAD is never asked of them
    'epoch-benchmarks-production-private.s3.us-east-2.amazonaws.com',
    'epoch-benchmarks-staging-private.s3.us-east-2.amazonaws.com',
})
# rule -> the transcript access it implies, which verification_rule turns into a rung
RULES = {
    'epoch-run-public-log': ('epoch-run', 'public'),
    'epoch-run-private-log': ('epoch-run', 'private'),
    'epoch-run-no-log': ('epoch-run', 'absent'),
    'external-scrape': ('external-scrape', 'absent'),
}
PUBLIC_LOG_NOTE = ('independent-reproduction only while the transcript answers its HEAD; an unreachable one is '
                   'maintainer-verified and labelled needs-scrutiny (ingest/verification.py)')


def assigns(rule: str) -> str:
    """The rung a rule gives, from verification_rule; unmatched is self-reported (14 Phase 3)."""
    if rule == UNMATCHED:
        return 'self-reported'
    family, access = RULES[rule]
    return v.verification_rule(family, v.Transcript(None, access))


def structurally_private(url: str) -> bool:
    """The public check's twin: https, a -private bucket, an .eval path, no query."""
    u = urlsplit(url)
    return u.scheme == 'https' and u.netloc in EPOCH_PRIVATE_LOG_HOSTS and u.path.endswith(v.LOG_SUFFIX) and not u.query


def file_problem(stanza, headers: list[str]) -> str | None:
    """Why no row of this file can match a rule, or None."""
    if stanza is None:
        return 'no mapping stanza'
    col = stanza.artifact.log_column if stanza.artifact else None
    if stanza.family == 'epoch-run' and col is not None and col not in headers:
        return 'the stanza names log column %r, which the file does not have' % col
    return None


def classify(stanza, row: dict) -> tuple[str, str | None]:
    """(rule, reason): reason is None unless the rule is unmatched. Call only when file_problem() is None."""
    if stanza.family == 'external-scrape':
        return 'external-scrape', None             # 07 S2.3: an external row's log column is never read
    if stanza.family != 'epoch-run':
        return UNMATCHED, 'family %r has no rule' % stanza.family
    col = stanza.artifact.log_column if stanza.artifact else None
    url = (row[col] if col else '').strip()
    if not url:
        return 'epoch-run-no-log', None
    if v.structurally_public(url):
        return 'epoch-run-public-log', None
    if structurally_private(url):
        return 'epoch-run-private-log', None
    u = urlsplit(url)
    return UNMATCHED, 'log URL is on neither bucket as an .eval (%s://%s)' % (u.scheme, u.netloc)


def account(bundle, stanzas: dict) -> dict:
    """Every row of every per-benchmark CSV in `bundle`, by rule. `stanzas` maps 'csv:<stem>' to its stanza."""
    rows_by_rule, files_by_rule = Counter(), defaultdict(set)
    unmatched = Counter()
    per_file = {}
    for stem in bundle.per_benchmark_csvs():
        headers, rows = bundle.read_csv(stem + '.csv')
        stanza = stanzas.get('csv:' + stem)        # get-default: a file with no stanza is unmatched, not skipped
        problem = file_problem(stanza, headers)
        counts = Counter()
        for row in rows:
            rule, reason = (UNMATCHED, problem) if problem else classify(stanza, row)
            counts[rule] += 1
            if rule == UNMATCHED:
                unmatched[stem, reason] += 1
        for rule, n in counts.items():
            rows_by_rule[rule] += n
            files_by_rule[rule].add(stem)
        per_file[stem] = len(rows)
    rules = [{'rule': r, 'assigns': assigns(r), 'rows': rows_by_rule[r], 'files': len(files_by_rule[r])}
             for r in [*RULES, UNMATCHED]]
    rules[0]['note'] = PUBLIC_LOG_NOTE
    return {
        'adapter': 'epoch',
        'snapshot': {'artefact_sha256': bundle.sha256, 'artefact_bytes': bundle.bytes},
        'rules': rules,
        'unmatched': rows_by_rule[UNMATCHED],
        'unmatched_rows': [{'file': f + '.csv', 'reason': why, 'rows': n} for (f, why), n in sorted(unmatched.items())],
        'total': sum(rows_by_rule.values()),
        'rows_per_file': per_file,
    }


# ---- the batch it must balance against --------------------------------------------------------------------

def newest_batch(folder: str = BATCHES) -> str | None:
    """The newest ingest-epoch-<date>[-n].yaml: by date, then by n (a plain sort puts -10 before -2)."""
    def key(p):
        m = re.match(r'ingest-epoch-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.yaml$', os.path.basename(p))
        return (m.group(1), int(m.group(2) or 1)) if m else None
    found = [p for p in glob.glob(os.path.join(folder, 'ingest-epoch-*.yaml')) if key(p)]
    return max(found, key=key) if found else None


def balance(acc: dict, batch: dict | None) -> list[str]:
    """Fill in claims_written and its basis; return what fails --check."""
    rows = acc.pop('rows_per_file')
    failures = []
    if batch is None:
        acc['claims_written'] = sum(rows.values())
        acc['claims_written_basis'] = 'snapshot rows: no Epoch IngestBatch is committed yet'
    else:
        counts = batch['counts']
        acc['claims_written'] = counts['claims_written']
        acc['claims_written_basis'] = 'batch %s' % batch['id']
        recorded = {k[len('rows_'):]: n for k, n in counts.items() if k.startswith('rows_')}
        if recorded != rows:
            differ = sorted(f for f in set(recorded) | set(rows)
                            if f not in recorded or f not in rows or recorded[f] != rows[f])
            failures.append('batch %s recorded other files or row counts than this snapshot has (%s): the accounting '
                            'is of a different snapshot' % (batch['id'], ', '.join(differ[:5])))
    acc['balanced'] = acc['total'] == acc['claims_written']
    if acc['unmatched']:
        failures.append('%d rows match none of the four rules: the adapter has met a file shape it was not built '
                        'for (see unmatched_rows)' % acc['unmatched'])
    if not acc['balanced']:
        failures.append('the rules account for %d rows but claims_written is %d (%s)'
                        % (acc['total'], acc['claims_written'], acc['claims_written_basis']))
    return failures


def shown(path: str) -> str:
    """A path relative to the repository when it is inside it, else as given (relpath fails across drives)."""
    full = os.path.abspath(path)
    return os.path.relpath(full, ROOT) if full.startswith(ROOT + os.sep) else path


def load_bundle(zip_path: str | None, snapshot: str):
    from ingest.adapters import epoch
    if zip_path:
        with open(zip_path, 'rb') as f:
            return epoch.ZipBundle(f.read())
    if not glob.glob(os.path.join(snapshot, '*.csv')):
        raise SystemExit('rule-accounting: %s holds no Epoch snapshot; restore it with '
                         '`python scripts/epoch_audit.py --fetch`, or pass --zip' % shown(snapshot))
    return epoch.bundle_from_directory(snapshot)


def main(argv=None) -> int:
    from ingest.mappings.schema import load_all
    from schema.taxonomy import read_yaml
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', action='store_true', help='exit 1 unless every row is accounted for and the sum balances')
    p.add_argument('--snapshot', default=EPOCHDL, help='an unpacked bundle (default: epochdl/)')
    p.add_argument('--zip', help='a bundle as served, instead of --snapshot')
    p.add_argument('--batch', help='the IngestBatch to balance against (default: the newest Epoch one, if any)')
    p.add_argument('--out', default=OUT)
    a = p.parse_args(argv)

    acc = account(load_bundle(a.zip, a.snapshot), load_all('epoch'))
    path = a.batch or newest_batch()
    failures = balance(acc, read_yaml(path) if path else None)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(acc, f, indent=2)
        f.write('\n')

    for r in acc['rules']:
        print('  %-22s %6d rows  %3d files  -> %s' % (r['rule'], r['rows'], r['files'], r['assigns']))
    print('  %-22s %6d rows' % ('total', acc['total']))
    for u in acc['unmatched_rows']:
        print('  unmatched: %s, %d rows: %s' % (u['file'], u['rows'], u['reason']))
    print('rule-accounting: wrote %s; claims_written %d (%s)'
          % (shown(a.out), acc['claims_written'], acc['claims_written_basis']))
    for msg in failures:
        print('rule-accounting: FAIL %s' % msg, file=sys.stderr)
    return 1 if a.check and failures else 0


if __name__ == '__main__':
    sys.exit(main())
