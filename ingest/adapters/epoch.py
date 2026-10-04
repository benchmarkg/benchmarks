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

What this does not do yet, by 07 S11.3's staging ("phase 0 of ingestion is a single script ... run
by hand, --fixture only ... no ABC"): no live transport, no candidates, no normalise(). The mapping
stanzas (P3-S2), the resolver (P3-S3) and the emitter (P3-S1-T05) come next, and the Adapter ABC is
P5-S1-T08's.
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

    def __init__(self, body: bytes, etag: str | None = None):
        self.body = body
        self.bytes = len(body)
        self.sha256 = hashlib.sha256(body).hexdigest()
        self.etag = etag
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
    at = iso(now())
    state['checked_at'] = at
    state['last_status'] = r.status
    if r.status == 304:
        return None
    if r.status != 200:
        raise FetchError('%s answered HTTP %d' % (ZIP_URL, r.status))
    etag = header(r.headers, 'ETag')
    bundle = ZipBundle(r.body, etag=etag)
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
