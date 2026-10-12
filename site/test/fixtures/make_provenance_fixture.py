#!/usr/bin/env python3
"""Regenerate site/test/fixtures/provenance-claims.json, the claims the provenance drill-down is built against.

    uv run python site/test/fixtures/make_provenance_fixture.py            # write it
    uv run python site/test/fixtures/make_provenance_fixture.py --check    # exit 1 if it is stale

P2-S3-T02: "Build against a fixture claim, since real claims arrive in Phase 3." claims.json, the artifact the
detail page will read, is P3-S10-T03's. So this writes rows in that artifact's shape (site/src/lib/claims.ts) from
the claims already committed under data/claims/, with each one's EvalConditions inlined and 04 S8's numbers
computed by tools/build/comparability.py itself -- the fixture is the build's arithmetic, not a hand-written guess.

Four rows are real claims, chosen for the shapes they exercise:

  claim-7112700f8bec   ForecastBench: every material field answered, so the unknown set is empty
  claim-728956d83bee   SWE-bench Verified: 11 of 12 unknown, on a weighted profile (scaffold counts 2.0)
  claim-0b51297ad7c5   SciCode: four other claims share its comparability_key
  claim-28ad9a7a2214   MMLU: two others share its key

and one is constructed, because no committed claim was machine-ingested or links an artifact: claim-000000000001
is claim-728956d83bee with its condition record removed (every material field unknown), an artifact_url on the
reserved .invalid domain, and a provenance_snapshot of the shape an adapter writes. Its `constructed` field says
so, and it validates as a ResultClaim.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provenance-claims.json')
sys.path.insert(0, ROOT)
from schema import validators as V  # noqa: E402
from schema.claim import ResultClaim, snapshot_sha256  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('comparability_fixture', os.path.join(ROOT, 'tools', 'build', 'comparability.py'))
C = importlib.util.module_from_spec(spec)
sys.modules['comparability_fixture'] = C
spec.loader.exec_module(C)

REAL = ['claim-7112700f8bec', 'claim-728956d83bee', 'claim-0b51297ad7c5', 'claim-28ad9a7a2214']
CONSTRUCTED_FROM = 'claim-728956d83bee'
CONSTRUCTED_ID = 'claim-000000000001'
SOURCE_FIELDS = ('id', 'type', 'title', 'url', 'publisher', 'accessed', 'fetched_at', 'archive_url', 'archive_captured',
                 'archive_status', 'licence_class')


def dump(model):
    return model.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)


def benchmark_id(ref: str) -> str:
    return ref.split('@', 1)[0].split('#', 1)[0]


def org_name(org_id: str) -> str | None:
    path = os.path.join(ROOT, 'data', 'organizations', org_id + '.yaml')
    return read_yaml(path).get('name') if os.path.exists(path) else None   # get-default: a record may omit it


def row(corpus, profiles, claim, keys, constructed=None) -> dict:
    resolution = C.resolve_profile(corpus.benchmarks[benchmark_id(claim.benchmark)], profiles)
    conditions = corpus.conditions.get(claim.eval_conditions) if claim.eval_conditions else None   # get-default: a dangling ref is unknown
    comp = C.compute_for_claim(claim, resolution, conditions)
    raw = corpus.sources.get(claim.source)                                  # get-default: an unresolved source is shown as such
    return {
        'claim': dump(claim),
        'conditions': dump(conditions) if conditions is not None else None,
        'comparability': comp.as_dict(),
        'material': list(resolution.material),
        'weights': {f: resolution.weights[f] for f in resolution.material},
        'key_shared_with': keys[comp.comparability_key] - 1,
        'source': {k: (raw or {}).get(k) for k in SOURCE_FIELDS} if raw else None,
        'reporter': {'id': claim.reported_by, 'name': org_name(claim.reported_by)},
        'constructed': constructed,
    }


def build() -> dict:
    corpus = V.load_corpus(ROOT)
    profiles = C.load_profiles()
    keys: Counter = Counter()
    for claim in corpus.claims.values():
        r = C.resolve_profile(corpus.benchmarks[benchmark_id(claim.benchmark)], profiles)
        keys[C.compute_for_claim(claim, r, corpus.conditions.get(claim.eval_conditions)).comparability_key] += 1
    rows = [row(corpus, profiles, corpus.claims[cid], keys) for cid in REAL]

    base = dump(corpus.claims[CONSTRUCTED_FROM])
    snapshot_raw = {'model': base['system'], 'resolved_rate': base['value'], 'row': 7}
    ingested = ResultClaim.model_validate(dict(
        base, id=CONSTRUCTED_ID, eval_conditions=None, artifact_url='https://transcripts.example.invalid/swe-bench-verified/',
        provenance_snapshot={
            'source_record_id': 'leaderboard-row-7',
            'retrieved_at': '2026-10-01T00:00:00Z',
            'content_sha256': snapshot_sha256(snapshot_raw),
            'raw': snapshot_raw,
        }))
    keys[C.compute_for_claim(ingested, C.resolve_profile(corpus.benchmarks['swe-bench-verified'], profiles), None).comparability_key] += 1
    rows.append(row(corpus, profiles, ingested, keys, constructed=(
        'Not a committed claim: %s without its condition record, with an artifact_url on .invalid and an adapter-shaped '
        'provenance_snapshot, because no committed claim was machine-ingested or links an artifact.' % CONSTRUCTED_FROM)))
    return {'fixture': 'provenance-claims', 'generator': 'site/test/fixtures/make_provenance_fixture.py', 'rows': rows}


def serialise(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + '\n'


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', action='store_true', help='exit 1 if the committed fixture differs from a regeneration')
    a = p.parse_args(argv)
    text = serialise(build())
    if a.check:
        with open(OUT, encoding='utf-8') as fh:
            stale = fh.read() != text
        print('make_provenance_fixture: %s' % ('STALE; rerun without --check' if stale else 'up to date'))
        return 1 if stale else 0
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print('wrote %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
