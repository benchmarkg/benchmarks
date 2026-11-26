#!/usr/bin/env python3
"""The claims artifacts tests/e2e/provenance-drilldown.spec.ts builds the site from (P3-S10-T07).

    uv run python tests/e2e/fixtures/make_claims_fixture.py --preview build/preview --out build/e2e-claims

The spec's subject is the claims the site renders, and the curated ones are real: the draft preview's claims.json
(scripts/preview_corpus.py, which writes it through tools/build/claims.py, P3-S10-T03). But no committed claim is
ingested -- there is no data/claims/_ingested/ yet and no claim carries an `ingestion` block -- so the two things the
task's done_when names for ingested claims, "the CC-BY attribution renders with every ingested claim" and a badge that
says `machine-ingested` beside its rank, would have nothing to render. So this writes the preview's artifacts again
with two constructed rows added, each a copy of a real row (the first, by id, with a number and a condition record)
given an id no real claim can have (`claim-e2e0000000NN`) and the `ingestion` block and provenance_snapshot an
adapter writes, validated as a ResultClaim:

  claim-e2e000000001   review_state spot-checked: an ingested claim a person sampled, so claims.json holds it
                       (tools/build/claims.py tier) and it gets a permalink page, with its attribution inline
  claim-e2e000000002   review_state machine-ingested: claims-ingested/<benchmark>.json holds it, and it gets no page
                       (08 S7.5 Decision 1); its benchmark's page counts it and shows its attribution

Its upstream is on the reserved .invalid domain and its attribution says it is a fixture, so neither can be taken
for a real dataset's. Each file is the stage's shape and canonical bytes (tools/build/emit.py serialise); every
`key_shared_with` is recomputed over the rows of its own file, as the stage computes it, and claims.json's
`machine_ingested` counts the file. derived/comparability.json is not written: no page reads it. It writes into its
own directory and refuses build/ and the preview's, so the artifacts a site deploys or previews from are never
these.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from schema.claim import ResultClaim, snapshot_sha256  # noqa: E402
from tools.build import claims as stage  # noqa: E402
from tools.build.emit import serialise  # noqa: E402

BATCH = 'ingest-e2e-fixture-2026-11-26'
ATTRIBUTION = ("Fixture Source, 'Constructed claims for tests/e2e/provenance-drilldown.spec.ts'. Not a dataset: "
               'retrieved from nowhere, at a reserved .invalid address.')
CONSTRUCTED = {'claim-e2e000000001': 'spot-checked', 'claim-e2e000000002': stage.MACHINE}


def constructed(base: dict, cid: str, review: str) -> dict:
    """`base`, a claims.json row, as an adapter would have written its claim, with `review` as its review state."""
    c = dict(base['claim'])
    raw = {'model': c['system'], 'metric': c['metric'], 'score': c['value']}
    key = 'fixture.csv#model=%s&metric=%s' % (c['system'], c['metric'])
    c.update(id=cid, notes='Constructed by tests/e2e/fixtures/make_claims_fixture.py from %s; not a claim.' % base['claim']['id'],
             provenance_snapshot={'source_record_id': key, 'retrieved_at': '2026-11-26T00:00:00Z',
                                  'content_sha256': snapshot_sha256(raw), 'raw': raw},
             ingestion={'batch': BATCH, 'source_adapter': 'e2e-fixture', 'adapter_version': '0.0.1', 'source_record_id': key,
                        'last_seen_upstream': '2026-11-26', 'source_url': 'https://fixture.example.invalid/claims.csv',
                        'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
                        'source_attribution': ATTRIBUTION, 'ingested_at': '2026-11-26T00:00:00Z',
                        'extraction_confidence': 0.9, 'review_state': review, 'reviewed_by': None, 'reviewed_on': None,
                        'field_provenance': {'value': 'source', 'eval_conditions.shots': 'absent'}})
    model = ResultClaim.model_validate(c)
    row = copy.deepcopy(base)
    row['claim'] = model.model_dump(mode='json', by_alias=True, exclude_computed_fields=True)
    if review == stage.MACHINE:
        row['badge'] = stage.MACHINE
    return row


def ordered(rows: list[dict]) -> list[dict]:
    """The stage's order and key counts (tools/build/claims.py stage `ordered`)."""
    out = sorted(rows, key=lambda r: r['claim']['id'].encode('utf-8'))
    keys: dict[str, int] = {}
    for r in out:
        k = r['comparability']['comparability_key']
        keys[k] = keys.get(k, 0) + 1                # get-default: a key's first row starts its count
    for r in out:
        r['key_shared_with'] = keys[r['comparability']['comparability_key']] - 1
    return out


def build(preview: dict) -> dict[str, dict]:
    if preview.get('artifact') != 'claims' or preview.get('machine_ingested'):
        raise SystemExit('make_claims_fixture: the preview claims.json is not the curated artifact with no machine-ingested '
                         'rows; this fixture adds the only ingested ones')
    bases = [r for r in preview['claims'] if r['claim'].get('value') is not None and r.get('conditions') is not None]
    if not bases:
        raise SystemExit('make_claims_fixture: the preview has no claim with a number and a condition record to copy')
    base = min(bases, key=lambda r: r['claim']['id'].encode('utf-8'))
    rows = {cid: constructed(base, cid, review) for cid, review in CONSTRUCTED.items()}
    bench = base['claim']['benchmark'].split('@')[0]
    curated = ordered([copy.deepcopy(r) for r in preview['claims']] + [rows['claim-e2e000000001']])
    machine = ordered([rows['claim-e2e000000002']])
    out = {stage.CLAIMS: dict(preview, claims=curated, machine_ingested={bench: len(machine)}),
           stage.ingested_name(bench): {'artifact': 'claims-ingested', 'format': stage.FORMATS['claims-ingested'],
                                        'benchmark': bench, 'badge': stage.MACHINE, 'claims': machine,
                                        **({'drafts': True} if preview.get('drafts') else {})}}
    # the stage's own split, read back off the rows written
    assert all(stage.row_tier(r) == stage.CURATED for r in out[stage.CLAIMS]['claims'])
    assert all(stage.row_tier(r) == stage.MACHINE for r in out[stage.ingested_name(bench)]['claims'])
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--preview', default=os.path.join(ROOT, 'build', 'preview'), help='the draft preview directory')
    p.add_argument('--out', default=os.path.join(ROOT, 'build', 'e2e-claims'), help='where to write (never build/ or the preview)')
    a = p.parse_args(argv)
    out_dir, preview_dir = os.path.abspath(a.out), os.path.abspath(a.preview)
    if out_dir in (os.path.join(ROOT, 'build'), preview_dir):
        print('make_claims_fixture: %s is what a site deploys or previews from; write the fixture to its own --out' % a.out,
              file=sys.stderr)
        return 2
    with open(os.path.join(preview_dir, stage.CLAIMS), encoding='utf-8') as fh:
        docs = build(json.load(fh))
    ingested = os.path.join(out_dir, stage.INGESTED)
    os.makedirs(ingested, exist_ok=True)
    for name in os.listdir(ingested):
        if name.endswith('.json'):
            os.remove(os.path.join(ingested, name))
    for name, doc in sorted(docs.items()):
        path = os.path.join(out_dir, *name.split('/'))
        with open(path, 'wb') as fh:
            fh.write(serialise(doc))
        print('wrote %s (%d row(s))' % (path, len(doc['claims'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
