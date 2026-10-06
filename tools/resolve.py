"""`bench resolve [PATH...] [--threshold X] [--pairs FILE] [--json]` (P1-S2-T10; 05 S3, 11 S F7).

05 S3: "Identity resolution: surface candidate duplicates ... for human decision. It never merges by itself."
This runs tools/dedup.py's candidate rule, at config/dedup.yaml's calibrated cosine threshold (or `--threshold`),
and gives every pair it is asked about a verdict, with its score:

    distinct     no signal proposes the pair (alias, shared site, name, cosine)
    same         a signal proposes it, and the two names normalise equal
    variant-of   a signal proposes it, and the names differ (CASP14 and CASP15, GPQA and GPQA Diamond)

That split is the one the hand-labelled known-pair set was built by (tests/dedup/fixtures/build_known_pairs.py:
"a row is `same` when the names normalise equal, else `variant-of`"). On those 200 pairs this reproduces every
verdict on the pairs it proposes, and its misses are exactly config/dedup.yaml's recorded false negatives
(variant pairs below the threshold): resolve inherits the calibration, it does not re-tune it.

    bench resolve                      # every candidate pair among data/benchmarks/ (and the named paths)
    bench resolve --pairs FILE         # a pair file ({records, pairs[a, b, label?]}): a verdict per pair, and the
                                       # agreement with any labels it carries

It writes nothing. Deciding is a person's job; the alias tables and lineage are where a decision is recorded.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from tools import dedup

VERDICTS = ('same', 'variant-of', 'distinct')


@dataclass(frozen=True)
class Verdict:
    a: str
    b: str
    verdict: str
    cosine: float
    name: float
    signals: tuple[str, ...]
    label: str | None = None

    @property
    def agrees(self) -> bool | None:
        return None if self.label is None else self.label == self.verdict


def config(threshold: float | None = None) -> dict:
    cfg = dedup.load_config()
    if threshold is not None:
        if not 0 < threshold <= 1:
            raise ValueError('--threshold %s is not a cosine in (0, 1]' % threshold)
        cfg = dict(cfg, cosine_threshold=threshold)
    return cfg


def verdict(a: dedup.Record, b: dedup.Record, vectors: dedup.Vectors, cfg: dict, label: str | None = None) -> Verdict:
    s = dedup.score(a, b, vectors)
    fired = tuple(s.fires(cfg))
    if not fired:
        v = 'distinct'
    else:
        v = 'same' if dedup.normalise_name(a.name) == dedup.normalise_name(b.name) else 'variant-of'
    return Verdict(a.id, b.id, v, s.cosine, s.name, fired, label)


def resolve_corpus(paths: list[str], cfg: dict) -> list[Verdict]:
    """A verdict for every pair the candidate rule proposes among the curated entries and `paths`."""
    records = dedup.corpus_records(paths)
    vectors = dedup.Vectors(records)
    by_id = {r.id: r for r in records}
    return [verdict(by_id[s.a], by_id[s.b], vectors, cfg) for s, _ in dedup.candidates(records, cfg)]


def resolve_pairs(path: str, cfg: dict) -> list[Verdict]:
    """A verdict for every pair in a pair file, carrying the file's label where it has one."""
    records, pairs = dedup.load_pairs(path)
    vectors = dedup.Vectors(list(records.values()))
    return [verdict(records[p['a']], records[p['b']], vectors, cfg, p.get('label')) for p in pairs]  # get-default: a pair file may be unlabelled


def agreement(verdicts: list[Verdict]) -> dict:
    """label -> verdict counts, over the labelled pairs, and how many agree."""
    labelled = [v for v in verdicts if v.label is not None]
    table = Counter((v.label, v.verdict) for v in labelled)
    return {'pairs': len(labelled), 'agree': sum(v.agrees for v in labelled),
            'table': {'%s -> %s' % k: n for k, n in sorted(table.items())}}
