#!/usr/bin/env python3
"""build/derived/adoption.json: who uses each benchmark, and when they said so (P4-S2-T07; 12 S6, S1).

    python tools/build/adoption.py --out build/derived/adoption.json [--root PATH]

A pure function of the tree (12 S1.1): data/ and metrics/ in, one JSON file out, no network and no clock,
so two builds of one tree are byte-identical. It consumes both claim tiers (12 S1.3: "a machine-ingested
claim still proves that somebody evaluated something on that benchmark").

Per benchmark, 12 S6's table:

  systems, organisations   distinct System entities with a claim, distinct `reported_by`
  reporting_velocity       claims per month, bucketed by the claim's own `date_reported` -- never by
                           `ingestion.ingested_at`, which this module does not read. A claim with no
                           date_reported is counted in a visible `undated` bucket with its share, and
                           kept out of the series (12 S6, "the ingest-date trap": 6,598 Epoch rows
                           bucketed on ingest would be one fictitious spike; only ~23% carry a date)
  citations                the paper's figure from metrics/citations.jsonl when one is there, carried
                           with its single_source and disagreement flags (12 S6; P4-S2-T10)
  repository, dataset      the latest weekly snapshot in metrics/adoption-counters.jsonl
                           (scripts/snapshot_adoption.py): stars and forks, downloads and likes, each
                           with the date it was observed -- an observed counter, not curated data

and the same velocity over every claim, field-wide. Counters and citations are read from metrics/, which
is outside the citable core (12 S6); nothing here is written back into data/ (12 S1.1 rule 1).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
FORMAT = 1
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}')
COUNTERS = os.path.join('metrics', 'adoption-counters.jsonl')
CITATIONS = os.path.join('metrics', 'citations.jsonl')


def entity(ref: str | None) -> str | None:
    """'gpt-5@2025-08-07' -> 'gpt-5'; 'forecastbench#tournament' -> 'forecastbench'."""
    return re.split(r'[@#]', ref, maxsplit=1)[0] if isinstance(ref, str) and ref else None


def event_month(claim: dict) -> str | None:
    """The claim's own date, as YYYY-MM, or None. Only `date_reported` is read (12 S6)."""
    value = claim.get('date_reported')                   # get-default: an ingested row may have none (04 S11)
    text = value.isoformat() if hasattr(value, 'isoformat') else str(value or '')
    return text[:7] if DATE.match(text) else None


def velocity(claims) -> dict:
    """Claims per month on their own date, the undated bucket beside the series, never inside it."""
    months, undated, total = Counter(), 0, 0
    for c in claims:
        total += 1
        m = event_month(c)
        if m is None:
            undated += 1
        else:
            months[m] += 1
    return {'bucket': 'month', 'date_field': 'date_reported',
            'series': [{'month': m, 'claims': months[m]} for m in sorted(months)],
            'dated': total - undated,
            'undated': {'claims': undated, 'share': round(undated / total, 4) if total else None},
            'total': total}


def load_claims(root: str) -> list[dict]:
    """Every claim file under data/claims/, both tiers, read raw: a row the model would refuse for a missing
    date is still a row somebody evaluated, and it lands in `undated`."""
    from schema.taxonomy import read_yaml
    out = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        rec = read_yaml(path)
        if isinstance(rec, dict) and rec.get('benchmark'):              # get-default: skip a non-claim file
            out.append(rec)
    return out


def benchmarks(root: str) -> dict[str, dict]:
    """Curated benchmark records by id: data/benchmarks/<family>/, not the _stubs/."""
    from schema.taxonomy import read_yaml
    out = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.path.basename(os.path.dirname(path)).startswith('_'):
            continue
        rec = read_yaml(path)
        out[rec['id']] = rec
    return out


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def latest_counters(root: str) -> dict[str, dict]:
    """benchmark id -> its most recent snapshot line (ties on a date: the later line)."""
    latest = {}
    for row in read_jsonl(os.path.join(root, COUNTERS)):
        prev = latest.get(row['benchmark'])
        if prev is None or row['observed_on'] >= prev['observed_on']:
            latest[row['benchmark']] = row
    return latest


def paper_arxiv(b: dict) -> str | None:
    return (b.get('external_ids') or {}).get('arxiv') or (b.get('paper') or {}).get('arxiv')  # get-default: optional


def latest_citations(root: str) -> dict[str, dict]:
    """arXiv id -> its most recent citation figure, re-checked: one without a valid single_source is refused."""
    from ingest.adapters.semantic_scholar import check_figure
    latest = {}
    for fig in read_jsonl(os.path.join(root, CITATIONS)):
        check_figure(fig)
        prev = latest.get(fig['arxiv'])
        if prev is None or fig['observed_on'] >= prev['observed_on']:
            latest[fig['arxiv']] = fig
    return latest


def build(root: str = ROOT) -> dict:
    claims = load_claims(root)
    by_benchmark: dict[str, list[dict]] = defaultdict(list)
    for c in claims:
        by_benchmark[entity(c['benchmark'])].append(c)
    curated = benchmarks(root)
    counters, citations = latest_counters(root), latest_citations(root)
    rows = []
    for bid in sorted(set(curated) | set(by_benchmark)):
        cs = by_benchmark.get(bid, [])                 # get-default: a curated benchmark with no claims
        arxiv = paper_arxiv(curated.get(bid, {}))      # get-default: claims on an uncurated benchmark id
        fig = citations.get(arxiv) if arxiv else None
        snap = counters.get(bid) or {}
        rows.append({
            'id': bid,
            'curated': bid in curated,
            'claims': len(cs),
            'systems': len({entity(c.get('system')) for c in cs} - {None}),           # get-default: as read
            'organisations': len({c.get('reported_by') for c in cs} - {None}),       # get-default: as read
            'reporting_velocity': velocity(cs),
            'citations': None if fig is None else {
                'arxiv': arxiv, 'value': fig['value'], 'single_source': fig['single_source'],
                'disagreement': fig['disagreement'], 'counts': fig['counts'], 'observed_on': fig['observed_on']},
            'repository': snap.get('github'),          # get-default: no snapshot yet is null, not zero
            'dataset': snap.get('huggingface'),        # get-default: as above
            'counters_observed_on': snap.get('observed_on'),                          # get-default: as above
        })
    return {'artifact': 'adoption', 'format': FORMAT,
            'tiers': ['curated', 'machine-ingested'],
            'field': {'claims': len(claims), 'benchmarks_with_claims': len(by_benchmark),
                      'systems': len({entity(c.get('system')) for c in claims} - {None}),     # get-default: as read
                      'organisations': len({c.get('reported_by') for c in claims} - {None}),  # get-default: as read
                      'reporting_velocity': velocity(claims)},
            'benchmarks': rows}


def serialise(artifact: dict) -> bytes:
    from tools.build.artifacts import nfc, serialise as dump
    return dump(nfc(artifact))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--out', default=None, help='write here; default stdout')
    a = ap.parse_args(argv)
    body = serialise(build(a.root))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'wb') as fh:
            fh.write(body)
    else:
        sys.stdout.buffer.write(body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
