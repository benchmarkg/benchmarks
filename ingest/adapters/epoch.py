#!/usr/bin/env python3
"""The Epoch AI adapter, phase 0: the conditional bundle fetch (P3-S1-T03; 07 S2, S2.2).

    python -m ingest.adapters.epoch --fixture tests/fixtures/epoch       # offline, zero network
    python -m ingest.adapters.epoch --fixture DIR --state ingest/state/epoch.json

Epoch publishes everything as one ZIP at https://epoch.ai/data/benchmark_data.zip (CC-BY-4.0). It
serves an ETag on it and NO Last-Modified (07 S2.2: observed "a95a0b35dd410ad483b45f53e3725590"), so
If-None-Match is the only conditional mechanism and If-Modified-Since is never sent. A 304 returns
None before any byte is parsed: nothing changed, so there is nothing to read.

A 200 becomes a ZipBundle. Its sha256 and byte count are the citable snapshot handle: the same two
numbers an IngestBatch records as source.artefact_sha256 and source.artefact_bytes (04 S9), so
`ZipBundle.snapshot()` returns exactly that block, and fetch_bundle() keeps it in the state file
beside the ETag it came with.

`Epoch` is 07 S1.2's BulkArchiveAdapter (P5-S1-T08): fetch_bundle() is the one network call,
enumerate() lists the logical records (one per metadata row, one per per-benchmark CSV), fetch() slices
the bundle into a Payload (ZipBundle.payload_for) and normalise(payload, resolver) is pure. What it does
not do yet, by 07 S11.3's staging: no live transport, and normalise() drafts nothing until the mapping
stanzas are wired in, so every per-benchmark CSV is an Unresolved asking for its stanza.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    # Run as a file, sys.path[0] is ingest/adapters/; put the repository root there so `ingest` imports.
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import posixpath  # noqa: E402
import re  # noqa: E402
import zipfile  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from collections import Counter  # noqa: E402

from ingest import gates  # noqa: E402
from ingest.adapters.base import BulkArchiveAdapter, Candidate, Payload, Unresolved  # noqa: E402
from ingest.http.fixture import FixtureMiss, FixtureTransport, header  # noqa: E402

NAME = 'epoch'
VERSION = '0.1.0'
ZIP_URL = 'https://epoch.ai/data/benchmark_data.zip'
LICENCE = 'CC-BY-4.0'
LICENCE_CLASS = 'permissive-attribution'
METADATA_CSVS = frozenset({'benchmark_metadata.csv', 'model_metadata.csv'})
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, 'ingest', 'state', 'epoch.json')


class FetchError(Exception):
    """The bundle request answered something other than 200 or 304."""


class BundleError(Exception):
    """The bytes are not a readable bundle."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ZipBundle:
    """One fetched copy of the bundle. Hashing happens here, on the bytes as served."""

    def __init__(self, body: bytes, etag: str | None = None, retrieved_at: datetime | None = None):
        self.body = body
        self.bytes = len(body)
        self.sha256 = hashlib.sha256(body).hexdigest()
        self.etag = etag
        self.retrieved_at = retrieved_at     # set by whoever fetched it; run() stamps a bundle that has none
        try:
            self._zip = zipfile.ZipFile(io.BytesIO(body))
        except zipfile.BadZipFile as e:
            raise BundleError('not a ZIP (%d bytes, sha256 %s): %s' % (self.bytes, self.sha256, e)) from e

    def names(self) -> list[str]:
        """Every file in the bundle, by its path inside it; directories are not entries."""
        return sorted(i.filename for i in self._zip.infolist() if not i.is_dir())

    def read_text(self, name: str) -> str:
        """UTF-8, strictly: a byte that is not UTF-8 is an error to see, not a character to guess."""
        try:
            return self._zip.read(name).decode('utf-8-sig')
        except KeyError:
            raise BundleError('%s is not in the bundle' % name) from None

    def read_csv(self, name: str) -> tuple[list[str], list[dict[str, str]]]:
        """(headers, rows), every cell the string the file holds; '' stays '' (07 S2: null is unknown,
        and only a mapping stanza may say what an empty cell means)."""
        reader = csv.DictReader(io.StringIO(self.read_text(name), newline=''))
        rows = list(reader)
        return list(reader.fieldnames or []), rows

    def per_benchmark_csvs(self) -> list[str]:
        """The stems of the top-level per-benchmark CSVs: every top-level .csv except the two metadata
        files, whether or not a metadata row names it (07 S2: 21 are orphans, and all are mapped)."""
        return sorted(posixpath.splitext(n)[0] for n in self.names()
                      if '/' not in n and n.endswith('.csv') and n not in METADATA_CSVS)

    def payload_for(self, candidate: Candidate) -> Payload:
        """07 S1.2's slice: the Payload for one logical record, parsed, with no network. A per-benchmark
        CSV carries its headers and rows; a metadata row carries itself as `doc`. The hash is of the
        record's canonical form (07 S1.5): for a CSV the header row plus its rows sorted, so a
        regenerated export that only reorders rows hashes the same."""
        kind, key = candidate.source_key.split(':', 1)
        if kind == 'csv':
            name = key + '.csv'
            headers, rows = self.read_csv(name)
            body, content_type, doc = self._zip.read(name), 'text/csv', None
            canon = [headers, sorted([r[h] for h in headers] for r in rows)]
        elif kind == 'bench':
            doc = {k: v for k, v in candidate.hint.items() if k != 'snapshot'}
            headers = rows = None
            body, content_type = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode('utf-8'), 'application/json'
            canon = doc
        else:
            raise BundleError('%s names no record of this bundle' % candidate.source_key)
        sha = hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
                             .encode('utf-8')).hexdigest()
        return Payload(candidate=candidate, body=body, content_type=content_type, http_status=200,
                       fetched_at=self.retrieved_at, etag=self.etag, last_modified=None, sha256_normalised=sha,
                       from_cache=False, headers=headers, rows=rows, doc=doc)

    def snapshot(self, retrieved_at: datetime | str, url: str = ZIP_URL) -> dict:
        """The IngestBatch `source` block (04 S9) that cites this copy."""
        at = retrieved_at if isinstance(retrieved_at, str) else iso(retrieved_at)
        return {'name': 'Epoch AI -- Capabilities & Benchmarking', 'url': url, 'retrieved_at': at,
                'http_etag': self.etag, 'artefact_sha256': self.sha256, 'artefact_bytes': self.bytes}


def fetch_bundle(transport, state: dict, now=utcnow) -> ZipBundle | None:
    """One conditional GET. None on a 304, before anything is parsed; else the bundle, with the ETag
    and the snapshot handle recorded in `state`. Only If-None-Match is ever sent (07 S2.2)."""
    etags = state.setdefault('etags', {})
    sent = etags.get(ZIP_URL)
    headers = {'If-None-Match': sent} if sent else {}
    r = transport.get(ZIP_URL, headers)  # get-default: an HTTP GET with request headers, not a lookup
    t = now()
    at = iso(t)
    state['checked_at'] = at
    state['last_status'] = r.status
    if r.status == 304:
        return None
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (ZIP_URL, r.status))
    etag = header(r.headers, 'ETag')
    bundle = ZipBundle(r.body, etag=etag, retrieved_at=t)
    if etag:
        etags[ZIP_URL] = etag
    else:
        etags.pop(ZIP_URL, None)        # no validator to send next time; the next run fetches in full
    state['snapshot'] = bundle.snapshot(at)
    return bundle


# ---- what an IngestBatch says about this bundle (P3-S1-T04) ----------------------------------------

_CITATION = re.compile(r'^#+\s*Citation\s*\n+```[^\n]*\n(.*?)\n```', re.M | re.S)


def attribution(bundle: ZipBundle) -> str:
    """The credit line the bundle's own README asks for, verbatim: its "Citation" block. 07 S2.2's
    copy straightens the quotes; the README's are curly, and the README is the source. A README with no
    citation block is an error, never a fallback to a remembered string."""
    m = _CITATION.search(bundle.read_text('README.md'))
    if not m or not m.group(1).strip():
        raise BundleError('README.md has no Citation block to take the attribution from')
    return m.group(1).strip()


def counts(bundle: ZipBundle) -> dict[str, int]:
    """An IngestBatch's counts for this bundle: what the metadata files hold, how many per-benchmark
    CSVs there are, and each one's row count as rows_<file stem>."""
    out = {'files_seen': len(bundle.names()), 'per_benchmark_csvs': len(bundle.per_benchmark_csvs()),
           'benchmarks_seen': len(bundle.read_csv('benchmark_metadata.csv')[1]),
           'model_rows_seen': len(bundle.read_csv('model_metadata.csv')[1])}
    for stem in bundle.per_benchmark_csvs():
        out['rows_' + stem] = len(bundle.read_csv(stem + '.csv')[1])
    return out


def bundle_from_directory(path: str) -> ZipBundle:
    """A bundle from an unpacked copy on disk (epochdl/, 07 S2: "already on disk ... so it can be
    developed entirely offline"). Zipped in memory in sorted order with a fixed timestamp, so the same
    files give the same sha256; it has no ETag, because nothing served it."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, _, names in sorted(os.walk(path)):
            for n in sorted(names):
                full = os.path.join(d, n)
                info = zipfile.ZipInfo(os.path.relpath(full, path).replace(os.sep, '/'), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(full, 'rb') as f:
                    z.writestr(info, f.read())
    return ZipBundle(buf.getvalue())


# ---- one run (P3-S1-T06; 07 S1.6, S6.2, S8.1) ------------------------------------------------------

# 07 S8.1's ceilings: drafts of one entity type past these need --allow-bulk (the first Epoch run is
# the deliberate exception: 6,598 claims, by hand, once).
CAPS = gates.CAP_ROWS      # 07 S8.1's (floor, ceiling) per entity type, applied by ingest/gates (P5-S2-T05)
# What the engine reads from the two metadata files. A missing file, a missing column or zero rows is
# schema drift (06 S3.2 "When it breaks"): a hard fail, never a quiet empty run.
REQUIRED = {'benchmark_metadata.csv': ('benchmark', 'source_file', 'score_column', 'scale'),
            'model_metadata.csv': ('model_version', 'model_group')}
CHANGE_CLASSES = ('new', 'field-change', 'result-change', 'gone', 'metrics-only', 'no-change')


# The bundle is not shaped the way the engine reads it: ingest/gates/drift.py's hard fail (P5-S4-T05).
SchemaDrift = gates.drift.DriftError
# 07 S9.2 rule 1, declared: each metadata file's required columns, and at least one row.
EXPECT = {name: gates.drift.Expect(name, frozenset(cols), min_rows=1) for name, cols in REQUIRED.items()}


def check_drift(bundle: ZipBundle) -> None:
    """06 S3.1: "A 404 or a changed ZIP structure is a hard failure". Each metadata file is present, has its
    columns and at least one row, and the bundle still holds per-benchmark CSVs at its top level."""
    for name, expect in EXPECT.items():
        if name not in bundle.names():
            raise SchemaDrift('%s is missing from the bundle' % name)
        headers, rows = bundle.read_csv(name)
        missing = [c for c in REQUIRED[name] if c not in headers]
        if missing:
            raise SchemaDrift('%s has no %s column (headers: %s)' % (name, ', '.join(missing), ', '.join(headers)))
        gates.drift.rows(expect, rows)
    if not bundle.per_benchmark_csvs():
        raise SchemaDrift('the bundle holds no per-benchmark CSV at its top level: its structure changed')


def candidates(bundle: ZipBundle):
    """07 S2.2's enumerate(): one Candidate per metadata row, one per per-benchmark CSV (orphans too)."""
    for row in bundle.read_csv('benchmark_metadata.csv')[1]:
        yield Candidate('bench:%s' % row['benchmark'], 'benchmark', 'https://epoch.ai/benchmarks',
                        dict(row, snapshot=bundle.sha256))
    for stem in bundle.per_benchmark_csvs():
        yield Candidate('csv:%s' % stem, 'claim', None, {'snapshot': bundle.sha256})


def normalise(payload: Payload, resolver=None):
    """(drafts, unresolved) for one payload -- 07 S1.1's pure function, phase 0's mapping: before the
    stanzas are wired in. A benchmark row is already allocated an id in
    ingest/mappings/epoch/_id_allocation.yaml (P3-S2-T07), so it drafts nothing. A per-benchmark CSV
    has no stanza applied yet, so it is Unresolved, exactly as 07 S2.2's normalise() treats a CSV with
    no mapping: a person writes the stanza; nothing assumes a scale. It reads only the payload's parsed
    views; the resolver is unused until a stanza names a system or a benchmark to resolve."""
    candidate = payload.candidate
    if candidate.kind != 'claim':
        return [], []
    stem = candidate.source_key.split(':', 1)[1]
    headers, rows = list(payload.headers), payload.rows
    return [], [Unresolved(
        source_key=candidate.source_key, field='*', observed='%d rows, headers=%r' % (len(rows), headers),
        reason='no-match',
        human_task='Write ingest/mappings/epoch/%s.yaml: score column, unit, scale, metric ref, '
                   'uncertainty column. Do NOT assume scale=1.0.' % stem)]


def validate_draft(draft) -> str | None:
    """Why `draft` would not load as its entity, or None: ingest/gates' schema gate, which holds a draft to
    the model its path names, as `bench validate` holds the file. A draft that fails is a hard fail (07 S8)."""
    try:
        gates.schema(gates.document(draft), draft.path.as_posix())
    except gates.GateError as e:
        return '%s %s: %s' % (draft.entity_type, draft.entity_id or '(unminted)', str(e).split(': ', 2)[-1][:300])
    return None


class Epoch(BulkArchiveAdapter):
    """07 S2's adapter on 07 S1.2's contract. A transport (a fixture, in phase 0) or an unpacked snapshot
    directory (epochdl/) supplies the bundle, or the caller hands one in as `bundle`; nothing else touches
    the source."""

    name, version, licence, licence_class = NAME, VERSION, LICENCE, LICENCE_CLASS
    expected_yield = (41, 162)            # 07 S9's seed band: 81 benchmarks x [0.5, 2.0]
    volatile_fields = ()                  # 07 S1.5: the ZIP is byte-stable between publications
    caps = CAPS

    def __init__(self, transport=None, directory: str | None = None, bundle: ZipBundle | None = None, now=utcnow):
        if transport is not None and directory is not None:
            raise ValueError('an Epoch adapter reads from a transport or a directory, not both')
        self.transport, self.directory, self.bundle, self.now = transport, directory, bundle, now

    @property
    def attribution(self) -> str:
        """The README's own Citation block, verbatim: read from the bundle, never remembered."""
        if self.bundle is None:
            raise BundleError('no bundle has been fetched to read the attribution from')
        return attribution(self.bundle)

    def fetch_bundle(self, state: dict) -> ZipBundle | None:
        if self.directory is not None:
            bundle = bundle_from_directory(self.directory)
            bundle.retrieved_at = self.now()
            return bundle
        if self.transport is None:
            raise FetchError('this Epoch adapter was given neither a transport nor a directory to fetch from')
        if state.get('checkpoint'):           # get-default: a phase-0 state file has no checkpoint key
            # A partial run stopped inside this bundle: its ETag would answer 304 and the resume would
            # find nothing to finish. An unfinished bundle is fetched whole (ingest/runner/state.py).
            state.setdefault('etags', {}).pop(ZIP_URL, None)
        return fetch_bundle(self.transport, state, self.now)

    def enumerate(self, bundle: ZipBundle):
        return candidates(bundle)

    def normalise(self, payload: Payload, resolver=None):
        return normalise(payload, resolver)       # the module function, looked up at call time


def run(bundle: ZipBundle | None, *, limit: int | None = None, allow_bulk: bool = False,
        normaliser=None, resolver=None, now=utcnow, root: str = ROOT) -> dict:
    """One run over a fetched bundle (None: a 304, nothing changed): enumerate(), fetch() and
    normalise() through the Epoch adapter. Returns the run report: status, candidates seen, drafts by
    change class, unresolved, cap and validation errors. Writes nothing. `normaliser(payload, resolver)`
    defaults to this module's normalise(), looked up at call time."""
    normaliser = normaliser or normalise
    started = now()
    report = {'adapter': NAME, 'adapter_version': VERSION, 'started_at': iso(started), 'status': 'ok',
              'candidates_seen': 0, 'drafts': {c: 0 for c in CHANGE_CLASSES}, 'drafts_by_type': {},
              'unresolved': 0, 'errors': [], 'snapshot': bundle.snapshot(started) if bundle else None}
    if bundle is None:
        report['status'] = 'no-change'
        report['finished_at'] = iso(now())
        return report
    try:
        check_drift(bundle)
    except SchemaDrift as e:
        report.update(status='hard-fail', errors=['schema drift: %s' % e.message], finished_at=iso(now()),
                      issue=gates.drift.issue(NAME, e.message, report['started_at']))
        return report
    if bundle.retrieved_at is None:
        bundle.retrieved_at = started         # a bundle read from disk was retrieved when the run read it
    adapter = Epoch(bundle=bundle, now=now)
    for i, cand in enumerate(adapter.enumerate(bundle)):
        if limit is not None and i >= limit:
            break
        report['candidates_seen'] += 1
        drafts, unresolved = normaliser(adapter.fetch(cand), resolver)
        report['unresolved'] += len(unresolved)
        for d in drafts:
            report['drafts'][d.change_class] += 1
            report['drafts_by_type'][d.entity_type] = report['drafts_by_type'].get(d.entity_type, 0) + 1  # get-default: a count starts at 0
            why = validate_draft(d)
            if why:
                report['errors'].append('invalid draft: %s' % why)
    over = []
    if report['drafts_by_type'] and not report['errors']:
        try:
            over = gates.caps(Counter(report['drafts_by_type']), gates.Tree(root).counts(), allow_bulk)
        except gates.GateError as e:
            over = [str(e)]
    if report['errors']:
        report['status'] = 'hard-fail'
    elif over:
        report['status'] = 'capped'
        report['errors'].append('over the 07 S8.1 caps without --allow-bulk: %s' % ', '.join(over))
    elif not any(report['drafts'].values()):
        report['status'] = 'no-change'
    report['finished_at'] = iso(now())
    return report


# ---- state (07 S4 layer 2) ------------------------------------------------------------------------

def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'etags': {}}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write('\n')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture', required=True, help='a recorded-response directory; phase 0 has no live mode')
    p.add_argument('--state', default=STATE)
    p.add_argument('--dry-run', action='store_true', help='fetch and report; write no state')
    a = p.parse_args(argv)
    state = load_state(a.state)
    try:
        bundle = fetch_bundle(FixtureTransport(a.fixture), state)
    except (FixtureMiss, FetchError, BundleError) as e:
        print('epoch: %s: %s' % (type(e).__name__, e), file=sys.stderr)
        return 1
    if not a.dry_run:
        save_state(a.state, state)
    if bundle is None:
        print('epoch: 304, unchanged since ETag %s; nothing parsed' % state['etags'].get(ZIP_URL))
        return 0
    print('epoch: %d bytes, sha256 %s, ETag %s; %d files, %d per-benchmark CSVs'
          % (bundle.bytes, bundle.sha256, bundle.etag, len(bundle.names()), len(bundle.per_benchmark_csvs())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
