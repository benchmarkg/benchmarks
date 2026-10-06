"""`bench tag-gap --benchmark <id> --facet <facet> --note "<...>" --by <handle>` (P1-S2-T10; 05 S3, 03 S3.3).

05 S3: "Record, in one command, that a curator could not express something in the current vocabulary. It writes
a `taxonomy/_failures/` entry. This exists because the unmet-term rate is only real if logging costs nothing."
The task's reading of it: a facet the primary source does not answer is logged against the entry and the facet,
so the miss is data rather than a silent blank. So the default kind is `source-silent`; `--kind missing-term`
(and the other kinds of 03 S3.3's log) records a vocabulary that could not say what the source did.

The record is schema/classification.py's FailureRecord, at taxonomy/_failures/<yyyy-mm-dd>-<benchmark>-<nnn>.yaml,
the name the validator already requires. It is APPEND-ONLY: the next free number is taken, and the file is
created exclusively, so no existing record is ever rewritten -- a gap is resolved by a later record's
`resolved` block in triage, never by editing the original. The benchmark must be one the repository knows:
a curated entry, a stub, or a stress-corpus classification.
"""
from __future__ import annotations

import datetime
import glob
import os

from schema.classification import FAILURE_KINDS, FailureRecord

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = 'taxonomy/_failures'
DEFAULT_KIND = 'source-silent'


class TagGapError(Exception):
    """The gap cannot be recorded as given; nothing was written."""


def known_benchmark(benchmark: str, root: str = ROOT) -> bool:
    pats = ['data/benchmarks/**/%s.yaml' % benchmark, 'taxonomy/_corpus/classifications/%s.yaml' % benchmark]
    return any(glob.glob(os.path.join(root, p), recursive=True) for p in pats)


def next_path(benchmark: str, on: datetime.date, root: str = ROOT) -> str:
    stem = '%s-%s-' % (on.isoformat(), benchmark)
    taken = glob.glob(os.path.join(root, FAILURES, stem + '[0-9][0-9][0-9].yaml'))
    n = 1 + max((int(os.path.basename(p)[len(stem):len(stem) + 3]) for p in taken), default=0)
    return '%s/%s%03d.yaml' % (FAILURES, stem, n)


def record(benchmark: str, facet: str, note: str, by: str, kind: str = DEFAULT_KIND, blocking: bool = False,
           proposed_term: str | None = None, terms: list[str] | None = None,
           on: datetime.date | None = None, root: str = ROOT) -> dict:
    """The failure record, checked against FailureRecord. Raises TagGapError."""
    from pydantic import ValidationError
    if kind not in FAILURE_KINDS:
        raise TagGapError('--kind %s is not one of %s' % (kind, ', '.join(FAILURE_KINDS)))
    if not note or not note.strip():
        raise TagGapError('a gap says what could not be expressed: --note "..."')
    if not by or not by.strip():
        raise TagGapError('a gap names who logged it: --by <handle>')
    if not known_benchmark(benchmark, root):
        raise TagGapError('%s is no benchmark in data/benchmarks/ or taxonomy/_corpus/classifications/' % benchmark)
    rec = {'kind': kind, 'facet': facet, 'benchmark': benchmark, 'curator': by.strip(),
           'date': (on or datetime.date.today()).isoformat(), 'description': ' '.join(note.split()),
           'proposed_term': proposed_term, 'blocking': blocking, 'terms': list(terms or [])}
    try:
        FailureRecord.model_validate(rec)
    except ValidationError as e:
        raise TagGapError(' '.join(str(e).split())[:400]) from None
    return rec


def tag_gap(benchmark: str, facet: str, note: str, by: str, kind: str = DEFAULT_KIND, blocking: bool = False,
            proposed_term: str | None = None, terms: list[str] | None = None,
            on: datetime.date | None = None, root: str = ROOT) -> str:
    """Append one gap to taxonomy/_failures/; return its path. Never opens an existing file for writing."""
    from tools.fmt import dumps
    on = on or datetime.date.today()
    rec = record(benchmark, facet, note, by, kind, blocking, proposed_term, terms, on, root)
    if not rec['terms']:
        del rec['terms']
    rel = next_path(benchmark, on, root)
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'x', encoding='utf-8', newline='\n') as fh:          # 'x': an existing record is never touched
        fh.write('# %s -- bench tag-gap (05 S3, 03 S3.3)\n' % rel + dumps(rec))
    return rel
