#!/usr/bin/env python3
"""IngestBatch records: data/_ingest/batches/<id>.yaml (P3-S1-T04; 04 S9, 07 S1.3).

One file per adapter run that changed anything. It is where a source's licence and attribution live
once instead of once per record, and what every ingested record's `ingestion.batch` names. It carries:

  source     where the bytes came from and the handle that cites them: the ETag, and the sha256 and
             byte count of the archive as served (ingest/adapters/epoch.py's ZipBundle.snapshot)
  licence    the 04 S9 licence block, with the attribution text copied verbatim from the source
  resolver_snapshot_sha256
             the hash of the alias tables as they stood when the run began, without which a run cannot
             be re-derived once the tables are edited (04 S9, 07 S1.3)
  counts     what the run saw and wrote, including each upstream file's row count

    python -m ingest.batch --fixture tests/fixtures/epoch              # dry run: writes the batch file
    python -m ingest.batch --fixture tests/fixtures/epoch --root DIR   # into another tree

Phase 0 has no live transport and writes no claims (07 S11.3), so the batch a dry run writes records
claims_written: 0. Such a file is for checking, not for committing: 04 S9 keeps a batch only for a
run that changed something, and the first one arrives with the first real ingest.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    # Run as a file, sys.path[0] is ingest/; put the repository root there instead, or ingest/http/
    # would shadow the standard library's `http`, which urllib imports.
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import argparse  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCHES = 'data/_ingest/batches'
ALIASES = 'data/aliases'


def resolver_snapshot_sha256(root: str = ROOT) -> str:
    """The sha256 of the alias tables as they stand: sorted canonical JSON of {path: sha256 of the
    file's bytes} over data/aliases/**/*.yaml. With no tables yet it is the hash of `{}`, so it is
    defined, and it changes the moment any table does. 07 S1.3's Resolver (P3-S3) snapshots more --
    entity names and aliases, the lineage index, the taxonomy enums -- and records its own hash here
    once it exists; the alias tables are the part 04 S9 names."""
    tables = {}
    for p in sorted(glob.glob(os.path.join(root, ALIASES, '**', '*.yaml'), recursive=True)):
        with open(p, 'rb') as f:
            tables[os.path.relpath(p, root).replace(os.sep, '/')] = hashlib.sha256(f.read()).hexdigest()
    canon = json.dumps(tables, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def batch_id(adapter: str, run_started: datetime, root: str = ROOT) -> str:
    """ingest-<adapter>-<date>, with -2, -3 ... for a second run that day: an id is never reused."""
    base = 'ingest-%s-%s' % (adapter, run_started.astimezone(timezone.utc).date().isoformat())
    n, bid = 1, base
    while os.path.exists(os.path.join(root, BATCHES, bid + '.yaml')):
        n += 1
        bid = '%s-%d' % (base, n)
    return bid


def build(*, adapter: str, adapter_version: str, run_started: datetime, source: dict, licence: dict,
          counts: dict, target_tree: str, root: str = ROOT, notes: str | None = None) -> dict:
    """The batch record, checked against schema/entities.py's IngestBatch before anyone writes it."""
    from schema.entities import IngestBatch
    doc = {
        'id': batch_id(adapter, run_started, root),
        'adapter': adapter,
        'adapter_version': adapter_version,
        'run_started': run_started.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': source,
        'licence': licence,
        'resolver_snapshot_sha256': resolver_snapshot_sha256(root),
        'counts': counts,
        'target_tree': target_tree,
        'notes': notes,
    }
    IngestBatch.model_validate(doc)
    return doc


def write(doc: dict, root: str = ROOT) -> str:
    """Write through ingest/emit.py, the adapters' side of the one YAML emitter (07 S1.5)."""
    from ingest import emit
    rel = '%s/%s.yaml' % (BATCHES, doc['id'])
    if os.path.exists(os.path.join(root, *rel.split('/'))):
        raise FileExistsError('%s exists: a batch id is never reused' % rel)
    return emit.write(doc, rel, root, header='%s -- written by ingest/batch.py (04 S9)' % rel)


# ---- Epoch ----------------------------------------------------------------------------------------

EPOCH_SOURCE_RECORD = 'src-epoch-benchmark-data'
EPOCH_TARGET = 'data/claims/_ingested/epoch/'
EPOCH_NOTES = ('Upstream publishes no DOI and no dated snapshot handle, so the retrieval timestamp and '
               'the sha256 of the archive as served are the only immutable citation handle (04 S9).')


def epoch_batch(bundle, run_started: datetime, retrieved_at: datetime, root: str = ROOT,
                written: dict | None = None) -> dict:
    """The IngestBatch for one Epoch bundle. `written` adds what the run wrote (claims_written,
    unresolved); a phase-0 dry run writes nothing, and says so with zeros."""
    from ingest.adapters import epoch
    counts = dict(epoch.counts(bundle), claims_written=0, unresolved=0)
    counts.update(written or {})
    licence = {'spdx': epoch.LICENCE, 'class': epoch.LICENCE_CLASS, 'redistribution_permitted': True,
               'share_alike': False, 'non_commercial': False, 'attribution_required': True,
               'attribution_text': epoch.attribution(bundle), 'source_record': EPOCH_SOURCE_RECORD}
    return build(adapter=epoch.NAME, adapter_version=epoch.VERSION, run_started=run_started,
                 source=bundle.snapshot(retrieved_at), licence=licence, counts=counts,
                 target_tree=EPOCH_TARGET, root=root, notes=EPOCH_NOTES)


def main(argv=None) -> int:
    from ingest.adapters import epoch
    from ingest.http.fixture import FixtureTransport
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--fixture', required=True, help='a recorded-response directory; phase 0 has no live mode')
    p.add_argument('--root', default=ROOT, help='the tree to write data/_ingest/batches/ into')
    a = p.parse_args(argv)
    started = datetime.now(timezone.utc).replace(microsecond=0)
    bundle = epoch.fetch_bundle(FixtureTransport(a.fixture), {})    # a fresh state: always a full fetch
    if bundle is None:
        print('batch: the fixture answered 304; nothing to record', file=sys.stderr)
        return 1
    rel = write(epoch_batch(bundle, started, datetime.now(timezone.utc).replace(microsecond=0), a.root), a.root)
    print('batch: wrote %s' % rel)
    return 0


if __name__ == '__main__':
    sys.exit(main())
