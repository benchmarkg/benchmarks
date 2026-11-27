"""claims.json, claims-ingested/<benchmark_id>.json and derived/comparability.json (P3-S10-T03; tools/build/claims.py,
tools/build/comparability.py `pairwise`; 08 S4.2, S4.1, S3.2 S5, S6.1; 04 S8).

The verify: "`uv run bench build --out build/ && uv run pytest tests/build/test_claims_artifacts.py` passes: claims.json
carries no machine-ingested row, every claims-ingested file carries condition_completeness, comparability.json defers
above 40 claims per group, and claims.json is under 0.5 MB brotli". Done when: "The three artifacts build,
machine-ingested rows are segregated out of claims.json, and the size budget fails the build when exceeded."

No claim in the corpus is machine-ingested yet and every benchmark is still a draft, so the verify's own build writes
a claims.json with no rows (the last section reads it). Everything else is built over tests/fixtures/corpus-20/, the
frozen twenty-entry fixture (15 curated claims on critpt, scicode and mmlu), as the draft preview does (`drafts=True`):

  rows       each claims.json row is site/src/lib/claims.ts's ClaimRow: the claim, its conditions inlined, 04 S8's
             numbers as tools/build/comparability.py computes them, the reduced Source, the reporter
  split      a copy of the fixture with machine-ingested claims planted under data/claims/_ingested/: they reach
             claims-ingested/scicode.json, badged and carrying condition_completeness, and never claims.json or
             comparability.json; a spot-checked one is curated; one with no ingestion block is refused
  diff       comparability.json against claims.json's own rows: a pair has rows exactly when its keys differ, with at
             least one material row, "?" where a claim is silent; 40 claims are computed and 41 deferred, end to end
  refusals   the verify's failure cases, each planted in otherwise sound artifacts: a machine-ingested row in
             claims.json, a claims-ingested row without condition_completeness, a group over 40 not deferred, the
             budget exceeded -- and a domain-group id, and a comparability row naming an ingested claim
  budget     the encoder's bound, Node's measurement past it, the refusal with no Node, and `bench build` failing,
             nothing written, when the budget is exceeded
  manifest   the three registered with their hashes, claims-ingested files included, and the two tier counts
"""
import base64
import copy
import json
import os
import random
import re
import shutil
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402
from tools import cli  # noqa: E402
from tools.build import artifacts, comparability, emit  # noqa: E402
from tools.build import claims as CL  # noqa: E402
from tools.build import manifest as M  # noqa: E402

FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'corpus-20')
MINIMAL = os.path.join(ROOT, 'tests', 'build', 'fixtures', 'minimal')
CLAIMS_TS = os.path.join(ROOT, 'site', 'src', 'lib', 'claims.ts')
NODE = shutil.which('node')
needs_node = pytest.mark.skipif(NODE is None, reason='node is not on PATH; the brotli measurement needs it')
SCICODE = 'claim-0b51297ad7c5'          # a curated scicode claim in the fixture, the template for the planted ones
INGESTION = {
    'batch': 'ingest-fixture-2026-11-01', 'source_adapter': 'fixture-adapter', 'adapter_version': '1.0.0',
    'source_record_id': 'scicode:gpt-4-turbo', 'last_seen_upstream': '2026-11-01',
    'source_url': 'https://upstream.example.invalid/results.csv', 'source_licence': 'CC-BY-4.0',
    'licence_class': 'permissive-attribution', 'source_attribution': 'A fixture upstream, for this test only.',
    'ingested_at': '2026-11-01T00:00:00Z', 'extraction_confidence': 0.9, 'review_state': 'machine-ingested',
}


def read(out, name) -> dict:
    with open(os.path.join(str(out), *name.split('/')), encoding='utf-8') as fh:
        return json.load(fh)


def rows_of(artifacts_: dict) -> dict:
    return {r['claim']['id']: r for r in artifacts_[CL.CLAIMS]['claims']}


@pytest.fixture(scope='module')
def preview():
    result = artifacts.build(FIXTURE, drafts=True)
    assert result.errors == []
    return result


def plant(root, cid, rel_dir, **over):
    """A copy of the scicode template claim as `cid` under data/claims/<rel_dir>/, with `over` applied."""
    doc = read_yaml(os.path.join(FIXTURE, 'data', 'claims', 'scicode', SCICODE + '.yaml'))
    doc.update(id=cid, **over)
    doc = {k: v for k, v in doc.items() if v is not None}
    path = os.path.join(str(root), 'data', 'claims', *rel_dir.split('/'), cid + '.yaml')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, ensure_ascii=False))
    return doc


INGESTED_A, INGESTED_B, SPOT = 'claim-00000000a001', 'claim-00000000a002', 'claim-00000000a003'


@pytest.fixture(scope='module')
def planted(tmp_path_factory):
    """The fixture plus two machine-ingested scicode claims (one with no condition record), and a spot-checked one."""
    root = tmp_path_factory.mktemp('planted') / 'root'
    shutil.copytree(FIXTURE, root)
    plant(root, INGESTED_A, '_ingested/fixture/scicode', value=0.02, ingestion=INGESTION)
    plant(root, INGESTED_B, '_ingested/fixture/scicode', value=0.03, eval_conditions=None,
          ingestion=dict(INGESTION, source_record_id='scicode:another-model'))
    plant(root, SPOT, '_ingested/fixture/scicode', value=0.04,
          ingestion=dict(INGESTION, source_record_id='scicode:a-third-model', review_state='spot-checked'))
    result = artifacts.build(str(root), drafts=True)
    assert result.errors == []
    return root, result


# ---- the rows ----------------------------------------------------------------------------------------------------

def claim_row_keys() -> set[str]:
    """The fields of site/src/lib/claims.ts ClaimRow, the shape the provenance drill-down reads."""
    with open(CLAIMS_TS, encoding='utf-8') as fh:
        body = re.search(r'export interface ClaimRow \{(.*?)\n\}', fh.read(), re.S).group(1)
    return set(re.findall(r'^\s+(\w+):', body, re.M))


def test_every_curated_claim_on_a_published_benchmark_is_a_claim_row(preview):
    got = preview.claims[CL.CLAIMS]
    fixture_claims = {os.path.basename(p)[:-5] for d, _, ns in os.walk(os.path.join(FIXTURE, 'data', 'claims'))
                      for p in (os.path.join(d, n) for n in ns)}
    assert len(fixture_claims) == 15 and set(rows_of(preview.claims)) == fixture_claims
    assert (got['artifact'], got['format'], got['tier'], got['machine_ingested'], got['drafts']) == \
        ('claims', 1, 'curated', {}, True)
    ids = [r['claim']['id'] for r in got['claims']]
    assert ids == sorted(ids, key=lambda i: i.encode('utf-8'))
    assert {k for r in got['claims'] for k in r} == claim_row_keys() == \
        {'claim', 'conditions', 'comparability', 'material', 'weights', 'key_shared_with', 'source', 'reporter', 'pool'}
    assert all(r['pool'] is None for r in got['claims'])           # no fixture claim is a rating


def test_a_row_inlines_its_conditions_and_carries_the_builds_own_arithmetic(preview):
    from schema.benchmark import load_benchmark
    from schema.claim import ResultClaim
    from schema.conditions import EvalConditions
    profiles = comparability.load_profiles()
    for cid, row in rows_of(preview.claims).items():
        claim = ResultClaim.model_validate(row['claim'])
        bench = claim.benchmark.split('@')[0]
        path = [os.path.join(d, n) for d, _, ns in os.walk(os.path.join(FIXTURE, 'data', 'benchmarks')) for n in ns
                if n == bench + '.yaml'][0]
        res = comparability.resolve_profile(load_benchmark(path), profiles)
        cond = read_yaml(os.path.join(FIXTURE, 'data', 'conditions', claim.eval_conditions + '.yaml'))
        model = EvalConditions.model_validate(cond)
        assert row['conditions'] == CL.dump(model), cid
        assert row['comparability'] == comparability.compute_for_claim(claim, res, model).as_dict(), cid
        assert row['material'] == list(res.material) and row['weights'] == res.weights, cid
        # 08 S4.2's "plus comparability_key, artifact_url, provenance_snapshot and source refs"
        assert {'artifact_url', 'provenance_snapshot', 'source', 'disputed_by'} <= set(row['claim'])
        source = [read_yaml(os.path.join(d, n)) for d, _, ns in os.walk(os.path.join(FIXTURE, 'data', 'sources'))
                  for n in ns if n == claim.source + '.yaml'][0]
        assert row['source']['id'] == claim.source and row['source']['url'] == source['url'], cid
        assert set(row['source']) == set(CL.SOURCE_FIELDS)
        assert row['reporter']['id'] == claim.reported_by
    keys = [r['comparability']['comparability_key'] for r in preview.claims[CL.CLAIMS]['claims']]
    for r in preview.claims[CL.CLAIMS]['claims']:
        assert r['key_shared_with'] == keys.count(r['comparability']['comparability_key']) - 1


def test_the_reporter_is_named_from_the_published_organizations(preview):
    names = {o['id']: o.get('name') for o in preview.corpus['entities']['organization']}
    for row in preview.claims[CL.CLAIMS]['claims']:
        assert row['reporter']['name'] == names.get(row['reporter']['id'])


def test_a_claim_on_an_unpublished_benchmark_is_in_no_artifact():
    published = artifacts.build(FIXTURE)                   # drafts are not published, so neither are their claims
    assert published.errors == [] and published.claims[CL.CLAIMS]['claims'] == []
    assert published.claims[CL.DIFF]['groups'] == [] and 'drafts' not in published.claims[CL.CLAIMS]


# ---- the split -----------------------------------------------------------------------------------------------------

def test_machine_ingested_claims_are_segregated_badged_and_carry_condition_completeness(planted):
    _, result = planted
    name = CL.ingested_name('scicode')
    assert sorted(result.claims) == sorted([CL.CLAIMS, CL.DIFF, name])
    doc = result.claims[name]
    assert (doc['artifact'], doc['benchmark'], doc['badge']) == ('claims-ingested', 'scicode', 'machine-ingested')
    assert [r['claim']['id'] for r in doc['claims']] == [INGESTED_A, INGESTED_B]
    for r in doc['claims']:
        assert r['badge'] == 'machine-ingested' and r['claim']['ingestion']['review_state'] == 'machine-ingested'
        assert isinstance(r['comparability']['condition_completeness'], float)
    bare = doc['claims'][1]                                 # no condition record: every material field unknown
    assert bare['conditions'] is None and bare['comparability']['condition_completeness'] == 0.0
    assert bare['comparability']['key_unknown_count'] == bare['comparability']['fields_material_total'] > 0
    assert result.claims[CL.CLAIMS]['machine_ingested'] == {'scicode': 2}


def test_claims_json_carries_no_machine_ingested_row_and_a_reviewed_one_is_curated(planted):
    _, result = planted
    curated = rows_of(result.claims)
    assert INGESTED_A not in curated and INGESTED_B not in curated
    assert curated[SPOT]['claim']['ingestion']['review_state'] == 'spot-checked' and 'badge' not in curated[SPOT]
    assert all(CL.row_tier(r) == 'curated' for r in curated.values())


def test_no_comparison_artifact_names_an_ingested_claim(planted):
    _, result = planted
    diff = result.claims[CL.DIFF]
    named = {x for g in diff['groups'] for r in g['rows'] or [] for x in (r['a'], r['b'])}
    assert named and not named & {INGESTED_A, INGESTED_B}
    scicode = [g for g in diff['groups'] if g['benchmark'] == 'scicode'][0]
    assert scicode['claims'] == 6                           # the five curated and the spot-checked one, not the two
    assert scicode['keys'] == 1 and scicode['rows'] == []   # all six ran under one condition record


def test_an_ingested_path_with_no_ingestion_block_is_refused(planted, tmp_path):
    root, _ = planted
    shutil.copytree(root, tmp_path / 'root')
    plant(tmp_path / 'root', 'claim-00000000a004', '_ingested/fixture/scicode', value=0.05)
    errors = artifacts.build(str(tmp_path / 'root'), drafts=True).errors
    assert any('claim-00000000a004' in e and 'no ingestion block' in e for e in errors), errors


def test_a_claim_citing_a_source_nobody_holds_is_refused(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / 'root')
    plant(tmp_path / 'root', 'claim-00000000a005', 'scicode', source='src-nobody-holds-this')
    errors = artifacts.build(str(tmp_path / 'root'), drafts=True).errors
    assert any('src-nobody-holds-this' in e and 'no data/sources/ file holds it' in e for e in errors), errors


POOL = 'pool-scicode-fixture-2026-11'      # dated to the month, as an id may be; the record holds the day


def pool_record(root, **over) -> dict:
    doc = dict({'id': POOL, 'benchmark': 'scicode', 'snapshot_date': '2026-11-03', 'members': ['gpt-4o', 'o3'],
                'rating_system': 'elo', 'sources': [read_yaml(os.path.join(FIXTURE, 'data', 'claims', 'scicode',
                                                                         SCICODE + '.yaml'))['source']]}, **over)
    path = os.path.join(str(root), 'data', 'rating-pools', doc['id'] + '.yaml')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(doc, ensure_ascii=False))
    return doc


def test_a_rating_row_inlines_its_pool_record_and_every_other_row_names_none(tmp_path):
    """10 V5's rating-pool refusal needs "matching `rating_pool_id` + snapshot date": the date is the record's."""
    shutil.copytree(FIXTURE, tmp_path / 'root')
    pool_record(tmp_path / 'root')
    plant(tmp_path / 'root', 'claim-00000000a006', 'scicode', claim_type='rating', rating_pool=POOL, value=1210.0)
    result = artifacts.build(str(tmp_path / 'root'), drafts=True)
    assert result.errors == []
    rows = rows_of(result.claims)
    assert rows['claim-00000000a006']['pool'] == {'id': POOL, 'snapshot_date': '2026-11-03'}
    assert all(r['pool'] is None for cid, r in rows.items() if cid != 'claim-00000000a006')


def test_a_rating_naming_a_pool_nobody_holds_or_a_broken_one_is_refused(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / 'root')
    plant(tmp_path / 'root', 'claim-00000000a007', 'scicode', claim_type='rating', rating_pool=POOL, value=1210.0)
    errors = artifacts.build(str(tmp_path / 'root'), drafts=True).errors
    assert any('claim-00000000a007' in e and POOL in e and 'no data/rating-pools/ file holds it' in e for e in errors), errors
    pool_record(tmp_path / 'root', members=['gpt-4o'])                     # RatingPool needs two members: tier 1 fails
    errors = artifacts.build(str(tmp_path / 'root'), drafts=True).errors
    assert any('claim-00000000a007' in e and 'it fails tier 1' in e for e in errors), errors


# ---- the pairwise diff ---------------------------------------------------------------------------------------------

def test_a_pair_has_rows_exactly_when_its_keys_differ(preview):
    rows = rows_of(preview.claims)
    diff = preview.claims[CL.DIFF]
    assert (diff['artifact'], diff['defer_above'], diff['unknown'], diff['severities']) == \
        ('comparability', 40, '?', ['material', 'informative'])
    groups = {}
    for cid, r in rows.items():
        groups.setdefault((r['claim']['benchmark'].split('@')[0], r['claim']['metric']), []).append(cid)
    assert {(g['benchmark'], g['metric']): g['claims'] for g in diff['groups']} == \
        {k: len(v) for k, v in groups.items()}
    for g in diff['groups']:
        members = sorted(groups[(g['benchmark'], g['metric'])], key=lambda i: i.encode('utf-8'))
        key = {c: rows[c]['comparability']['comparability_key'] for c in members}
        differing = {(a, b) for i, a in enumerate(members) for b in members[i + 1:] if key[a] != key[b]}
        assert g['diff_status'] == 'computed' and g['keys'] == len(set(key.values())) and g['pairs'] == len(differing)
        assert {(r['a'], r['b']) for r in g['rows']} == differing
        for a, b in differing:
            assert any(r['severity'] == 'material' for r in g['rows'] if (r['a'], r['b']) == (a, b)), (a, b)
    assert diff['summary']['rows'] == sum(len(g['rows']) for g in diff['groups']) > 0


def test_a_material_row_says_unknown_exactly_where_the_claim_is_silent(preview):
    rows = rows_of(preview.claims)
    for g in preview.claims[CL.DIFF]['groups']:
        for r in g['rows']:
            for side, val in (('a', r['a_val']), ('b', r['b_val'])):
                row = rows[r[side]]
                if r['field'] == 'benchmark_version':
                    assert val == row['claim']['benchmark']
                elif r['field'] == 'subset':
                    assert val == row['claim']['subset']
                elif r['severity'] == 'material':
                    assert r['field'] in row['material']
                    assert (val == '?') == (r['field'] in row['comparability']['unknown_fields'])
                else:
                    assert r['field'] not in row['material']
            assert json.dumps(r['a_val']) != json.dumps(r['b_val'])


def facts(cid, key, **values):
    f = {'benchmark_version': ('b', 'material'), 'subset': (None, 'material'),
         'shots': (values.get('shots', '?'), 'material'), 'cost_usd': (values.get('cost_usd', '?'), 'informative')}
    return comparability.ClaimFacts(id=cid, benchmark='b', metric='m', comparability_key=key, facts=f)


def test_pairwise_rows_severities_and_order():
    got = comparability.pairwise([facts('claim-b', 'k2', shots=5, cost_usd=1.0), facts('claim-a', 'k1', cost_usd=2.0),
                                  facts('claim-c', 'k1', shots='?', cost_usd=3.0)])
    (g,) = got['groups']
    assert (g['claims'], g['keys'], g['pairs'], g['diff_status']) == (3, 2, 2, 'computed')   # a and c share k1
    assert [(r['a'], r['b'], r['field'], r['a_val'], r['b_val'], r['severity']) for r in g['rows']] == [
        ('claim-a', 'claim-b', 'shots', '?', 5, 'material'),
        ('claim-a', 'claim-b', 'cost_usd', 2.0, 1.0, 'informative'),
        ('claim-b', 'claim-c', 'shots', 5, '?', 'material'),
        ('claim-b', 'claim-c', 'cost_usd', 1.0, 3.0, 'informative')]


@pytest.mark.parametrize('n, status', [(1, 'computed'), (40, 'computed'), (41, 'deferred'), (200, 'deferred')])
def test_the_diff_is_deferred_above_40_claims_per_group(n, status):
    got = comparability.pairwise([facts('claim-%03d' % i, 'k%d' % (i % 3), shots=i % 3) for i in range(n)])
    (g,) = got['groups']
    assert (g['claims'], g['diff_status']) == (n, status)
    assert (g['rows'] is None) == (status == 'deferred')           # not computed, never an empty "no differences"
    assert g['pairs'] == n * (n - 1) // 2 - sum(k * (k - 1) // 2 for k in (len(range(r, n, 3)) for r in range(3)))
    assert got['summary']['deferred'] == (status == 'deferred')


def test_forty_claims_are_computed_and_forty_one_deferred_through_the_build(tmp_path):
    """mmlu's group grows to 40 claims and scicode's to 41, planted as curated claims across three condition sets."""
    shutil.copytree(FIXTURE, tmp_path / 'root')
    conds = ['cond-6173a6a331a4', 'cond-f8f67b1a0082', None]
    for i in range(38):
        plant(tmp_path / 'root', 'claim-0000000b%04d' % i, 'mmlu', benchmark='mmlu', metric='mmlu-score', value=i / 100,
              eval_conditions=conds[i % 3])
    for i in range(36):
        plant(tmp_path / 'root', 'claim-0000000c%04d' % i, 'scicode', value=i / 100,
              eval_conditions=None if i % 2 else 'cond-eb8b56103434')
    result = artifacts.build(str(tmp_path / 'root'), drafts=True)
    assert result.errors == []
    groups = {g['benchmark']: g for g in result.claims[CL.DIFF]['groups']}
    assert (groups['mmlu']['claims'], groups['mmlu']['diff_status']) == (40, 'computed') and groups['mmlu']['rows']
    assert (groups['scicode']['claims'], groups['scicode']['diff_status'], groups['scicode']['rows']) == \
        (41, 'deferred', None)
    # 5 + 18 under scicode's one condition record, 18 under none: two keys, and the pairs are counted, though not diffed
    assert groups['scicode']['keys'] == 2 and groups['scicode']['pairs'] == 23 * 18


# ---- the refusals: the verify's failure cases ----------------------------------------------------------------------

def refused(artifacts_) -> str:
    with pytest.raises(emit.Refused) as e:
        CL.refuse(artifacts_)
    return '\n'.join(e.value.errors)


def test_sound_artifacts_pass(planted):
    CL.refuse(planted[1].claims)


def test_refused_a_machine_ingested_row_leaking_into_claims_json(planted):
    docs = copy.deepcopy(planted[1].claims)
    leak = copy.deepcopy(docs[CL.ingested_name('scicode')]['claims'][0])
    docs[CL.CLAIMS]['claims'].append(leak)
    assert 'claims.json: claims[%d] (%s) is machine-ingested' % (len(docs[CL.CLAIMS]['claims']) - 1, INGESTED_A) \
        in refused(docs)
    leak.pop('badge')                                       # unbadged, the claim's own review_state still gives it away
    assert 'is machine-ingested' in refused(docs)


def test_refused_a_claims_ingested_file_without_condition_completeness(planted):
    docs = copy.deepcopy(planted[1].claims)
    del docs[CL.ingested_name('scicode')]['claims'][1]['comparability']['condition_completeness']
    want = 'claims-ingested/scicode.json: claims[1] (%s) carries no condition_completeness' % INGESTED_B
    assert want in refused(docs)


def test_refused_an_unbadged_or_misfiled_claims_ingested_file(planted):
    docs = copy.deepcopy(planted[1].claims)
    docs[CL.ingested_name('scicode')]['badge'] = None
    assert 'not a badged claims-ingested file' in refused(docs)
    docs = copy.deepcopy(planted[1].claims)
    docs[CL.ingested_name('mmlu')] = docs.pop(CL.ingested_name('scicode'))
    text = refused(docs)
    assert 'not a badged claims-ingested file for benchmark mmlu' in text and 'a claim on another benchmark' in text


def test_refused_a_group_over_40_claims_that_is_not_deferred(preview):
    docs = copy.deepcopy(preview.claims)
    group = docs[CL.DIFF]['groups'][0]
    group['claims'] = 41
    assert 'holds 41 claims, above 40, but is computed rather than deferred with no rows' in refused(docs)


def test_refused_a_comparability_row_naming_a_claim_claims_json_does_not_hold(planted):
    docs = copy.deepcopy(planted[1].claims)
    rows = [g for g in docs[CL.DIFF]['groups'] if g['rows']][0]['rows']
    rows[0]['b'] = INGESTED_A
    assert 'names %s, which claims.json does not hold' % INGESTED_A in refused(docs)


def test_refused_a_display_only_group_id(preview):
    docs = copy.deepcopy(preview.claims)
    gid = read_yaml(os.path.join(ROOT, 'taxonomy', 'domain_groups.yaml'))['groups'][0]['id']
    docs[CL.CLAIMS]['claims'][0]['claim']['notes'] = 'filed under %s' % gid
    assert 'carries the display-only domain-group id %s' % gid in refused(docs)


def test_write_refuses_too_and_writes_nothing(preview, tmp_path):
    docs = copy.deepcopy(preview.claims)
    docs[CL.DIFF]['groups'][0]['diff_status'] = 'deferred'
    with pytest.raises(emit.Refused):
        CL.write(docs, str(tmp_path))
    assert os.listdir(tmp_path) == []


# ---- the size budget -----------------------------------------------------------------------------------------------

def test_the_encoders_bound():
    assert [CL.max_brotli_size(n) for n in (0, 1, 16383, 16384, 500_000)] == [2, 7, 16389, 16394, 500_000 + 6 + 4 * 30]


@needs_node
@pytest.mark.parametrize('kind', ['random', 'json'])
def test_node_never_exceeds_the_bound(preview, kind):
    data = random.Random(7).randbytes(70_000) if kind == 'random' else emit.serialise(preview.claims[CL.CLAIMS])
    assert 0 < CL.brotli_size(data) <= CL.max_brotli_size(len(data))


def big_claims(preview, notes: str) -> dict:
    docs = copy.deepcopy(preview.claims)
    docs[CL.CLAIMS]['claims'][0]['claim']['notes'] = notes
    return docs


def incompressible(n: int) -> str:
    return base64.b64encode(random.Random(11).randbytes(n)).decode('ascii')


@needs_node
def test_a_large_claims_json_that_compresses_is_measured_and_passes(preview):
    docs = big_claims(preview, 'the same sentence again. ' * 30_000)
    b = CL.budget(emit.serialise(docs[CL.CLAIMS]))
    assert b.raw > CL.BUDGET and b.bound > CL.BUDGET and b.brotli is not None and b.brotli < CL.BUDGET and b.within
    CL.refuse(docs)


@needs_node
def test_refused_a_claims_json_over_half_a_megabyte_brotli(preview):
    docs = big_claims(preview, incompressible(600_000))       # 800 KB of base64: six bits a character, ~600 KB brotli
    b = CL.budget(emit.serialise(docs[CL.CLAIMS]))
    assert b.brotli > CL.BUDGET and not b.within
    assert 'over the 0.5 MB brotli budget, 08 S4.1\'s trigger to shard it' in refused(docs)


def test_without_node_the_bound_still_proves_a_small_file_and_a_large_one_is_refused(preview, monkeypatch):
    monkeypatch.setattr(CL.shutil, 'which', lambda name: None)
    small = CL.budget(emit.serialise(preview.claims[CL.CLAIMS]))
    assert small.within and small.brotli is None and small.bound <= CL.BUDGET
    CL.refuse(preview.claims)
    text = refused(big_claims(preview, 'the same sentence again. ' * 30_000))
    assert 'cannot be measured: node is not on PATH' in text


def test_bench_build_fails_and_writes_nothing_when_the_budget_is_exceeded(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    monkeypatch.setattr(CL, 'BUDGET', 10)                   # any claims.json, even an empty one, is over it
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path / 'build')])
    assert r.exit_code == 1, r.output
    assert 'claims.json is' in r.output and 'nothing written' in r.output
    assert not os.path.exists(tmp_path / 'build')


# ---- writing and the manifest --------------------------------------------------------------------------------------

def test_bench_build_writes_the_three_and_the_manifest_registers_them(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'ROOT', MINIMAL)
    r = CliRunner().invoke(cli.app, ['build', '--out', str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert re.search(r'claims: 0 curated in claims\.json \([\d,]+ bytes, brotli at most [\d,]+, by the encoder\'s '
                     r'bound, budget 500,000\); 0 machine-ingested in 0 claims-ingested/ file\(s\)', r.output), r.output
    assert os.path.isdir(tmp_path / CL.INGESTED) and os.listdir(tmp_path / CL.INGESTED) == []
    m = read(tmp_path, M.MANIFEST)
    for name in CL.ARTIFACTS:
        with open(os.path.join(str(tmp_path), *name.split('/')), 'rb') as fh:
            raw = fh.read()
        digest = M.sha256(raw)
        assert m['artifacts'][name] == 'sha256:' + digest and m['paths'][name] == M.hashed_path(name, digest)
        assert m['formats'][name] == 1
    assert (m['counts']['claims_curated'], m['counts']['claims_machine_ingested']) == (0, 0)


def test_every_claims_ingested_file_is_hashed_and_the_tiers_are_counted(planted, tmp_path):
    root, result = planted
    out = str(tmp_path / 'out')
    written = artifacts.write(result, out)
    rel = sorted(os.path.relpath(p, out).replace(os.sep, '/') for p in written)
    assert rel == sorted(list(emit.ARTIFACTS) + [CL.CLAIMS, CL.DIFF, CL.ingested_name('scicode')])
    M.write(out, written, None, root=str(root))
    m = read(out, M.MANIFEST)
    name = CL.ingested_name('scicode')
    assert m['paths'][name].startswith('/data/claims-ingested/scicode.') and m['artifacts'][name].startswith('sha256:')
    c = m['counts']
    assert (c['claims_curated'], c['claims_machine_ingested']) == (len(result.claims[CL.CLAIMS]['claims']), 2)
    assert c['claims'] == c['claims_curated'] + c['claims_machine_ingested'] == 18


def test_a_rewrite_leaves_only_this_builds_claims_ingested_files(planted, preview, tmp_path):
    CL.write(planted[1].claims, str(tmp_path))
    assert os.listdir(tmp_path / CL.INGESTED) == ['scicode.json']
    CL.write(preview.claims, str(tmp_path))
    assert os.listdir(tmp_path / CL.INGESTED) == []


def test_two_builds_are_byte_identical_and_canonical(preview, tmp_path):
    again = artifacts.build(FIXTURE, drafts=True)
    first, second = CL.write(preview.claims, str(tmp_path / 'a')), CL.write(again.claims, str(tmp_path / 'b'))
    for a, b in zip(first, second):
        with open(a, 'rb') as fa, open(b, 'rb') as fb:
            raw = fa.read()
            assert raw == fb.read() and raw == emit.serialise(json.loads(raw)) and raw.count(b'\n') == 1, a


def test_the_preview_script_writes_and_hashes_them(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('preview_corpus', os.path.join(ROOT, 'scripts', 'preview_corpus.py'))
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    assert preview.main(['--root', FIXTURE, '--out', str(tmp_path)]) == 0
    m = read(tmp_path, M.MANIFEST)
    assert set(CL.ARTIFACTS) <= set(m['paths']) and len(read(tmp_path, CL.CLAIMS)['claims']) == 15


# ---- the verify's build --------------------------------------------------------------------------------------------

def test_the_verifys_bench_build():
    out = os.path.join(ROOT, 'build')
    if not os.path.exists(os.path.join(out, CL.CLAIMS)):
        pytest.skip('no build/claims.json: run `uv run bench build --out build/` first, as the verify does')
    docs = {CL.CLAIMS: read(out, CL.CLAIMS), CL.DIFF: read(out, CL.DIFF)}
    for name in sorted(os.listdir(os.path.join(out, CL.INGESTED))):
        docs['%s/%s' % (CL.INGESTED, name)] = read(out, '%s/%s' % (CL.INGESTED, name))
    # claims.json carries no machine-ingested row; every claims-ingested file carries condition_completeness
    assert not [r for r in docs[CL.CLAIMS]['claims'] if CL.row_tier(r) == 'machine-ingested']
    for name, doc in docs.items():
        if name.startswith(CL.INGESTED + '/'):
            assert doc['badge'] == 'machine-ingested'
            assert all('condition_completeness' in r['comparability'] for r in doc['claims']), name
    # comparability.json defers above 40 claims per group
    for g in docs[CL.DIFF]['groups']:
        assert (g['diff_status'] == 'deferred') == (g['claims'] > 40), g
    # claims.json is under 0.5 MB brotli: measured when Node is here, else by the encoder's bound
    with open(os.path.join(out, CL.CLAIMS), 'rb') as fh:
        raw = fh.read()
    assert (CL.brotli_size(raw) if NODE else CL.max_brotli_size(len(raw))) <= CL.BUDGET == 500_000
    CL.refuse(docs)                                          # and every other refusal holds over what was written
    m = read(out, M.MANIFEST)
    for name in docs:
        with open(os.path.join(out, *name.split('/')), 'rb') as fh:
            assert m['artifacts'][name] == 'sha256:' + M.sha256(fh.read()), name
