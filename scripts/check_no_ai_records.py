#!/usr/bin/env python3
"""Check 9i: no AI-written record reaches the citable core (P0-S6-T03; 05 S9 check 9i, 11 governing rule, 15 AI1).

05 S9: "Greps every path under `data/` for `provenance: ai-worker` and for `curation.verification_status:
ai-drafted-unverified`, failing on any hit. AI drafts live in `drafts/` until a human has reviewed them." The YAML at
a commit is the citable surface (08 S4.5), so a draft under data/ is citable even though the build never publishes
it; this is what makes "nothing the model emits is ever stored in data/" a property of the repository rather than
an assertion.

    python scripts/check_no_ai_records.py              # exit 0 when data/ holds no AI-written record, 1 otherwise
    python scripts/check_no_ai_records.py --root DIR   # another tree (the tests do)

It is a grep, deliberately (15 AI1: "a grep, not an inference about identity"): a line `verification_status:
ai-drafted-unverified` or `provenance: ai-worker` in any file under data/, comments aside.

Reported, not yet blocking (the maintainer's decision of 2026-10-12): every entry in data/ is still an agent's
draft awaiting a person, so the job would hold main red until then, while the build already refuses every draft
(tools/build/artifacts.py). pr-validate.yml runs it with continue-on-error until P1-S13-T02 promotes the drafts;
tests/ci/test_no_ai_records.py fails the moment this check passes on the repository while the job is still not
blocking, so the flip cannot be forgotten.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERNS = (
    ('ai-drafted-unverified', re.compile(r'^\s*verification_status:\s*["\']?ai-drafted-unverified["\']?\s*(#.*)?$')),
    ('provenance: ai-worker', re.compile(r'^\s*(?:-\s*)?provenance:\s*["\']?ai-worker["\']?\s*(#.*)?$')),
)


def hits(root: str) -> list[tuple[str, int, str]]:
    """(path relative to root, line number, what matched) for every AI-written record marker under data/."""
    out = []
    base = os.path.join(root, 'data')
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(folder, name)
            try:
                lines = open(path, encoding='utf-8').read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue                                      # not text: no YAML marker can be in it
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            for n, line in enumerate(lines, 1):
                for label, pat in PATTERNS:
                    if pat.match(line):
                        out.append((rel, n, label))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    found = hits(a.root)
    for rel, n, label in found:
        print('BLOCKING  9i  %s:%d: %s under data/; an AI draft lives in drafts/ until a person has reviewed it'
              % (rel, n, label))
    files = len({rel for rel, _, _ in found})
    print('check_no_ai_records: %d AI-written record marker(s) in %d file(s) under data/' % (len(found), files))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
