#!/usr/bin/env python3
"""Check 7, the metadata-only invariant (P0-S6-T04; 05 S9, 05 S11).

05 S9: "Reject any `.parquet`, `.jsonl`, `.csv`, `.npz` or archive file under `data/`; reject any file in
`data/` over 256 KB. ... This makes 'we never host datasets' a mechanical fact rather than a promise." The
repository holds metadata about benchmarks, never their items: a dataset file, or a YAML file grown big
enough to be one, is refused wherever it sits under data/.

    python scripts/check_metadata_only.py              # check data/; exit 0 if clean, 1 otherwise
    python scripts/check_metadata_only.py --root DIR   # another tree (the tests do)

05 S9's third clause, "reject any single prose field over N characters", names no N; it is not checked
here until the plan sets one.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 256 * 1024
DATASET_SUFFIXES = ('.parquet', '.jsonl', '.csv', '.npz')
ARCHIVE_SUFFIXES = ('.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.7z', '.rar', '.zst', '.lz4')


def findings(root: str) -> list[str]:
    out = []
    base = os.path.join(root, 'data')
    for d, _, files in os.walk(base):
        for f in sorted(files):
            full = os.path.join(d, f)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            low = f.lower()
            if low.endswith(DATASET_SUFFIXES):
                out.append('%s: a dataset file (%s) under data/; the repository holds metadata, never items'
                           % (rel, os.path.splitext(low)[1]))
            elif low.endswith(ARCHIVE_SUFFIXES):
                out.append('%s: an archive under data/' % rel)
            size = os.path.getsize(full)
            if size > MAX_BYTES:
                out.append('%s: %d bytes, over the 256 KB limit for a data/ file' % (rel, size))
    return sorted(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    bad = findings(a.root)
    for line in bad:
        print('BLOCKING  7/metadata-only  %s' % line)
    print('check_metadata_only: %d finding(s) under data/' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
