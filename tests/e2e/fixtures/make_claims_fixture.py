#!/usr/bin/env python3
"""The claims artifacts tests/e2e/provenance-drilldown.spec.ts, comparability-states.spec.ts, v5-workbench.spec.ts and
v5-refusals.spec.ts build the site from (P3-S10-T07, P3-S10-T04, P3-S10-T05, P3-S10-T06).

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
`machine_ingested` counts the file.

derived/comparability.json (P3-S10-T04: the benchmark page's comparisons read it beside claims.json) is computed again
by the stage's own `comparability.pairwise` over this claims.json's rows, the constructed curated one included, so its
groups are exactly the file's (tools/build/claims.py `diff_problems` is run on it). Each row's facts are rebuilt from
the row itself -- its claim and inlined conditions validated again as ResultClaim and EvalConditions, its benchmark's
resolved `material` set -- and each rebuilt key must be the row's own, so the diff is the one the stage would write.
The constructed claim copies the first real row with a number and a condition record, so it joins that row's
(benchmark, metric) group under the same key: one more claim of a condition set that is already there, not a state the
preview lacks (the preview's claims already show all three of 04 S8's states). It writes into its own directory and
refuses build/ and the preview's, so the artifacts a site deploys or previews from are never these.

P3-S10-T06: 10 V5's six categorical refusals (site/src/lib/refusals.ts). Three have real claims in the preview --
Matbench Discovery's F1 under two compliance tiers, ForecastBench's Brier scores pending, partial and resolved,
WeatherBench 2's RMSE and CRPS over several dimensions -- and three have none: no committed claim is a rating (a
`claim_type: rating` with a `rating_pool`), none is under pass^k, and ARC-AGI-3 has no claim at all. So REFUSAL_ROWS
constructs them, each on the benchmark 10 V5 names, except that RoboArena's two real rating pools (data/rating-pools/,
2026-06-10 and 2026-11-16) stand in for Kaggle Game Arena, which has one:

  claim-e2e000000003..05   RoboArena ratings in its two pools, all under one constructed condition record that answers
                           every material field: one comparability key and nothing unknown, so the key alone would show
                           them together, silently (04 S8's state 1) -- the confidently wrong number 10 V5 means
  claim-e2e000000006..08   tau-bench under pass^k, k 1 for two systems and k 8 for one, on two constructed condition
                           records; the metric id `e2e-pass-hat-k` is constructed too, since the corpus has no tau-bench
                           Metric record
  claim-e2e000000009..0b   ARC-AGI-3's RHAE on its two real leaderboards' own condition records (data/leaderboards/: the
                           verified board's cond-6e8ba4ad92b4 and the community board's cond-ff37311df041)

Each is a ResultClaim with an invented value, an ingestion block (review_state spot-checked, so claims.json holds it, as
claim-e2e000000001) whose attribution says, wherever the row renders, that it is a fixture, a source and a reporter
that name no record (`src-e2e-fixture`, `org-e2e-fixture`; the row's `source` is null), and the comparability numbers
tools/build/comparability.py computes over its benchmark's own resolved profile and its condition record, so the key,
the unknowns and derived/comparability.json's rows are the ones the stage would write.
"""
from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from schema.benchmark import load_benchmark  # noqa: E402
from schema.claim import ResultClaim, snapshot_sha256  # noqa: E402
from schema.conditions import EvalConditions  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.build import claims as stage  # noqa: E402
from tools.build import comparability  # noqa: E402
from tools.build.emit import nfc, serialise  # noqa: E402

BATCH = 'ingest-e2e-fixture-2026-11-26'
ATTRIBUTION = ("Fixture Source, 'Constructed claims for tests/e2e/provenance-drilldown.spec.ts'. Not a dataset: "
               'retrieved from nowhere, at a reserved .invalid address.')
CONSTRUCTED = {'claim-e2e000000001': 'spot-checked', 'claim-e2e000000002': stage.MACHINE}

# P3-S10-T06 (module docstring): the refusals the preview has no claim for.
REFUSAL_BATCH = 'ingest-e2e-refusals-2026-11-26'
REFUSAL_ATTRIBUTION = ("Fixture Source, 'Constructed claims for tests/e2e/v5-refusals.spec.ts'. Not a dataset: every value "
                       'is invented, retrieved from nowhere, at a reserved .invalid address.')
# constructed condition records, beside the real ones REFUSAL_ROWS names by id
REFUSAL_CONDITIONS = {
    # RoboArena's material fields (physical-trial profile), every one answered, so its ratings share one key, unknown-free
    'cond-e2e0000000a1': {'hardware_platform': 'DROID', 'n_samples': 100, 'simulator': 'none', 'simulator_version': 'none',
                          'subset_used': 'all-policies board', 'venue': 'the RoboArena evaluator network'},
    'cond-e2e0000000b1': {'selection_strategy': 'pass-hat-k', 'k': 1, 'n_samples': 8, 'harness': 'tau-bench', 'subset_used': 'retail'},
    'cond-e2e0000000b8': {'selection_strategy': 'pass-hat-k', 'k': 8, 'n_samples': 8, 'harness': 'tau-bench', 'subset_used': 'retail'},
}
# id, system, benchmark, metric, value, the claim's other fields, its condition record, the refusal it is for
REFUSAL_ROWS = [
    ('claim-e2e000000003', 'dreamzero', 'roboarena', 'roboarena-rating', 1210.0,
     {'claim_type': 'rating', 'rating_pool': 'pool-roboarena-2026-06-10'}, 'cond-e2e0000000a1', 'rating-pool'),
    ('claim-e2e000000004', 'dreamzero', 'roboarena', 'roboarena-rating', 1185.0,
     {'claim_type': 'rating', 'rating_pool': 'pool-roboarena-2026-11-16'}, 'cond-e2e0000000a1', 'rating-pool'),
    ('claim-e2e000000005', 'pi05-droid', 'roboarena', 'roboarena-rating', 1102.0,
     {'claim_type': 'rating', 'rating_pool': 'pool-roboarena-2026-11-16'}, 'cond-e2e0000000a1', 'rating-pool'),
    ('claim-e2e000000006', 'claude-opus-4-5', 'tau-bench', 'e2e-pass-hat-k', 0.71, {}, 'cond-e2e0000000b1', 'pass-hat-k'),
    ('claim-e2e000000007', 'gpt-5-2', 'tau-bench', 'e2e-pass-hat-k', 0.64, {}, 'cond-e2e0000000b1', 'pass-hat-k'),
    ('claim-e2e000000008', 'claude-opus-4-5', 'tau-bench', 'e2e-pass-hat-k', 0.38, {}, 'cond-e2e0000000b8', 'pass-hat-k'),
    ('claim-e2e000000009', 'gpt-5-2', 'arc-agi-3', 'rhae', 1.5, {}, 'cond-6e8ba4ad92b4', 'legality-track'),
    ('claim-e2e00000000a', 'gpt-5-2', 'arc-agi-3', 'rhae', 6.0, {}, 'cond-ff37311df041', 'legality-track'),
    ('claim-e2e00000000b', 'o3', 'arc-agi-3', 'rhae', 4.0, {}, 'cond-ff37311df041', 'legality-track'),
]


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


def conditions_record(cid: str) -> EvalConditions:
    """A constructed condition record of REFUSAL_CONDITIONS, or the real one data/conditions/ holds under `cid`."""
    if cid in REFUSAL_CONDITIONS:
        return EvalConditions.model_validate(dict(REFUSAL_CONDITIONS[cid], id=cid))
    return EvalConditions.model_validate(read_yaml(os.path.join(ROOT, 'data', 'conditions', '%s.yaml' % cid)))


def refusal_rows() -> list[dict]:
    """REFUSAL_ROWS as claims.json rows, each computed by the stage's own comparability code (module docstring)."""
    profiles = comparability.load_profiles()
    resolutions: dict[str, comparability.Resolution] = {}
    out = []
    for cid, system, bench, metric, value, extra, cond_id, refusal in REFUSAL_ROWS:
        if bench not in resolutions:
            hits = glob.glob(os.path.join(ROOT, 'data', 'benchmarks', '*', '%s.yaml' % bench))
            if len(hits) != 1:
                raise SystemExit('make_claims_fixture: %d records of benchmark %s' % (len(hits), bench))
            resolutions[bench] = comparability.resolve_profile(load_benchmark(hits[0]), profiles)
        res = resolutions[bench]
        cond = conditions_record(cond_id)
        raw = {'model': system, 'benchmark': bench, 'metric': metric, 'score': value, **extra}
        key = 'refusals.csv#model=%s&metric=%s&conditions=%s' % (system, metric, cond_id)
        claim = ResultClaim.model_validate(dict(
            id=cid, system=system, benchmark=bench, metric=metric, value=value, date_reported='2026-11-26',
            reported_by='org-e2e-fixture', verification='self-reported', source='src-e2e-fixture', eval_conditions=cond_id,
            notes='Constructed by tests/e2e/fixtures/make_claims_fixture.py for tests/e2e/v5-refusals.spec.ts (10 V5 refusal '
                  '%s); not a claim: its value is invented.' % refusal,
            provenance_snapshot={'source_record_id': key, 'retrieved_at': '2026-11-26T00:00:00Z',
                                 'content_sha256': snapshot_sha256(raw), 'raw': raw},
            ingestion={'batch': REFUSAL_BATCH, 'source_adapter': 'e2e-fixture', 'adapter_version': '0.0.1', 'source_record_id': key,
                       'last_seen_upstream': '2026-11-26', 'source_url': 'https://fixture.example.invalid/refusals.csv',
                       'source_licence': 'CC-BY-4.0', 'licence_class': 'permissive-attribution',
                       'source_attribution': REFUSAL_ATTRIBUTION, 'ingested_at': '2026-11-26T00:00:00Z',
                       'extraction_confidence': 0.9, 'review_state': 'spot-checked', 'reviewed_by': None, 'reviewed_on': None,
                       'field_provenance': {'value': 'source'}},
            **extra))
        out.append({'claim': claim.model_dump(mode='json', by_alias=True, exclude_computed_fields=True),
                    'conditions': cond.model_dump(mode='json', by_alias=True, exclude_computed_fields=True),
                    'comparability': comparability.compute_for_claim(claim, res, cond).as_dict(),
                    'material': list(res.material), 'weights': {f: res.weights[f] for f in res.material},
                    'source': None, 'reporter': {'id': 'org-e2e-fixture', 'name': None}})
    return out


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


def diff(rows: list[dict], drafts: bool) -> dict:
    """derived/comparability.json over claims.json's rows, as the stage computes it (module docstring)."""
    facts = []
    for r in rows:
        bench = r['claim']['benchmark'].split('@')[0]
        res = comparability.Resolution(benchmark=bench, basis='facets', profiles=(), material=tuple(r['material']),
                                       weights=dict(r['weights']))
        cond = EvalConditions.model_validate(r['conditions']) if r['conditions'] is not None else None
        f = comparability.claim_facts(ResultClaim.model_validate(r['claim']), res, cond)
        if f.comparability_key != r['comparability']['comparability_key']:
            raise SystemExit('make_claims_fixture: %s rebuilds to key %s, not its own %s'
                             % (r['claim']['id'], f.comparability_key, r['comparability']['comparability_key']))
        facts.append(f)
    out = nfc(dict(comparability.pairwise(facts), **({'drafts': True} if drafts else {})))
    problems = stage.diff_problems(out, rows)
    if problems:
        raise SystemExit('make_claims_fixture: %s' % '; '.join(problems))
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
    taken = {r['claim']['id'] for r in preview['claims']} & {cid for cid, *_ in REFUSAL_ROWS}
    if taken:
        raise SystemExit('make_claims_fixture: the preview already holds %s' % ', '.join(sorted(taken)))
    curated = ordered([copy.deepcopy(r) for r in preview['claims']] + [rows['claim-e2e000000001']] + refusal_rows())
    machine = ordered([rows['claim-e2e000000002']])
    out = {stage.CLAIMS: dict(preview, claims=curated, machine_ingested={bench: len(machine)}),
           stage.ingested_name(bench): {'artifact': 'claims-ingested', 'format': stage.FORMATS['claims-ingested'],
                                        'benchmark': bench, 'badge': stage.MACHINE, 'claims': machine,
                                        **({'drafts': True} if preview.get('drafts') else {})},
           stage.DIFF: diff(curated, bool(preview.get('drafts')))}
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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(serialise(doc))
        held = '%d group(s)' % len(doc['groups']) if name == stage.DIFF else '%d row(s)' % len(doc['claims'])
        print('wrote %s (%s)' % (path, held))
    return 0


if __name__ == '__main__':
    sys.exit(main())
