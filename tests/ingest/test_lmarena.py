"""The LMArena adapter (P5-S6-T02; 06 S3.6, 04 S2).

Verified against tests/ingest/fixtures/lmarena/: LMArena's own rows (CC-BY-4.0) for five arenas at dataset commit
e16f902, pruned by make_fixture.py and served the way the Hub serves them -- the metadata with blob hashes, then
each file's resolve URL answering 302 to the CDN.

  - the done_when: style-control variants are distinct entities -- their own Leaderboard, RatingPool and Metric --
    with distinct comparability keys, computed by the build's own compute(); and no rating claim exists without
    its pool and snapshot: every claim names a pool drafted in the same run, whose id and snapshot_date carry the
    claim's date;
  - the cap: `overall` only, top 25 per arena; vote counts go to the report's observations, never onto a claim;
    `full` (the per-battle history) is never requested;
  - the failure cases: a pool with fewer than two resolved members drafts no pool and no claim; a renamed rating
    column, or an `overall` category with two publish dates, is drift, a hard fail; a licence tag that is not
    cc-by-4.0 is a veto; a file that does not hash to its metadata is refused; a vanished arena is a lifecycle
    review that keeps its last snapshot; Agent Arena's IPS scores have no stanza and become one human task each;
  - every request asks the gate, the CDN host included, before anything is sent.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from ingest.adapters import lmarena as L
from ingest.http import policy as P
from ingest.http.fixture import FixtureTransport
from ingest.mappings.schema import load_all
from ingest.resolve import Entry, Index
from schema.claim import ResultClaim
from schema.entities import Leaderboard, RatingPool
from schema.metric import Metric
from tools.build import comparability as CMP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'lmarena')
COMMIT = 'e16f9023298691b4596eca61b4e31161dff31200'


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)


def rows(arena):
    return pq.read_table(os.path.join(FIX, arena + '.parquet')).to_pylist()


def overall(arena):
    return sorted((r for r in rows(arena) if r['category'] == 'overall'), key=lambda r: r['rank'])


def system_id(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def resolvers(arenas=('text', 'text_style_control', 'webdev', 'video_edit'), top=40):
    """A frozen resolver holding every model the fixture's rated arenas name in their top rows."""
    names = {r['model_name'] for a in arenas for r in overall(a)[:top]}
    return {'system': Index('system', [Entry(system_id(n), n) for n in sorted(names)])}


def run(fix=FIX, state=None, res=None, transport=None):
    adapter = L.LMArena(transport or FixtureTransport(fix), now=_now, stanzas=load_all('lmarena'))
    return L.run(adapter, state if state is not None else L.new_state(), res or resolvers())


@pytest.fixture(scope='module')
def report():
    return run()


def body(d):
    return {k: v for k, v in d.items() if k not in ('path', 'entity_type', 'entity_id')}


# ---- the fixture ---------------------------------------------------------------------------------------------

def test_the_fixture_serves_what_its_metadata_names():
    with open(os.path.join(FIX, 'api.json'), encoding='utf-8') as f:
        meta = json.load(f)
    assert meta['sha'] == COMMIT and 'license:cc-by-4.0' in meta['tags']
    latest = {s['rfilename'].split('/')[0]: s['lfs']['sha256'] for s in meta['siblings']
              if s['rfilename'].endswith('/latest-00000-of-00001.parquet')}
    assert sorted(latest) == ['agent', 'text', 'text_style_control', 'video_edit', 'webdev']
    for arena, sha in latest.items():
        with open(os.path.join(FIX, arena + '.parquet'), 'rb') as f:
            assert hashlib.sha256(f.read()).hexdigest() == sha


# ---- the done_when ---------------------------------------------------------------------------------------------

def test_style_control_is_its_own_leaderboard_pool_and_metric(report):
    assert report['status'] == 'ok', report['errors']
    lbs = {d['id']: d for d in report['documents'] if d['entity_type'] == 'leaderboard'}
    pools = {d['id']: d for d in report['documents'] if d['entity_type'] == 'rating_pool'}
    metrics = {d['id']: d for d in report['documents'] if d['entity_type'] == 'metric'}
    assert {'lb-lmarena-text', 'lb-lmarena-text-style-control'} <= set(lbs)
    assert {'pool-lmarena-text-2026-10-08', 'pool-lmarena-text-style-control-2026-10-08'} <= set(pools)
    assert {'lmarena-text-score', 'lmarena-text-style-control-score'} <= set(metrics)
    assert pools['pool-lmarena-text-style-control-2026-10-08']['leaderboard'] == 'lb-lmarena-text-style-control'
    assert lbs['lb-lmarena-text']['benchmarks'] == lbs['lb-lmarena-text-style-control']['benchmarks'] == ['lmarena-text']
    assert lbs['lb-lmarena-text-style-control']['name'] == 'LMArena Text Arena (style control)'


def test_the_same_system_in_the_two_variants_has_two_comparability_keys(report):
    claims = [d for d in report['documents'] if d['entity_type'] == 'claim']
    by = {}
    for c in claims:
        by.setdefault(c['system'], {})[c['metric']] = c
    both = [s for s, m in by.items() if {'lmarena-text-score', 'lmarena-text-style-control-score'} <= set(m)]
    assert len(both) >= 20
    fallback = CMP.load_profiles().fallback
    res = CMP.Resolution(benchmark='lmarena-text', basis='fallback', profiles=(), material=tuple(sorted(fallback.material)),
                         weights={f: 1.0 for f in fallback.material})
    for s in both:
        raw, styled = by[s]['lmarena-text-score'], by[s]['lmarena-text-style-control-score']
        k1 = CMP.compute(res, None, raw['benchmark'], raw['metric'], None).comparability_key
        k2 = CMP.compute(res, None, styled['benchmark'], styled['metric'], None).comparability_key
        assert raw['benchmark'] == styled['benchmark'] and k1 != k2
    # what a flag on the parent would have done: one metric, one key, and the two would be ranked together
    assert CMP.compute(res, None, 'lmarena-text', 'lmarena-text-score', None).comparability_key == \
        CMP.compute(res, None, 'lmarena-text', 'lmarena-text-score', None).comparability_key


def test_no_rating_claim_exists_without_its_pool_and_snapshot(report):
    pools = {d['id']: d for d in report['documents'] if d['entity_type'] == 'rating_pool'}
    claims = [d for d in report['documents'] if d['entity_type'] == 'claim']
    assert claims
    for c in claims:
        assert c['claim_type'] == 'rating' and c['rating_pool'] in pools
        pool = pools[c['rating_pool']]
        assert c['rating_pool'].endswith('-' + c['date_reported']) and pool['snapshot_date'] == c['date_reported']
        assert c['system'] in pool['members'] and pool['benchmark'] == c['benchmark']


def test_every_draft_validates_as_its_entity(report):
    for d in report['documents']:
        b = body(d)
        if d['entity_type'] == 'claim':
            ResultClaim.model_validate({'id': 'claim-000000000000', **b})
        elif d['entity_type'] == 'rating_pool':
            RatingPool.model_validate(b)
        elif d['entity_type'] == 'leaderboard':
            Leaderboard.model_validate(b)
        elif d['entity_type'] == 'metric':
            m = Metric.model_validate(b)
            assert m.unbounded and m.requires_pool and not m.headroom_computable and m.value_type == 'elo'
        else:
            raise AssertionError(d['entity_type'])


def test_a_claim_maps_06_s3_6s_columns(report):
    top = overall('text')[0]
    (c,) = [d for d in report['documents'] if d['entity_type'] == 'claim' and d['metric'] == 'lmarena-text-score'
            and d['system'] == system_id(top['model_name'])]
    assert c['value'] == round(top['rating'], 6)
    assert c['uncertainty'] == {'type': 'ci95', 'value': [round(top['rating_lower'], 6), round(top['rating_upper'], 6)]}
    assert c['verification'] == 'maintainer-verified' and c['reported_by'] == 'org-lmarena'
    assert c['source'] == 'src-lmarena-leaderboard-dataset' and c['date_reported'] == '2026-10-08'
    rid = c['ingestion']['source_record_id']
    assert rid.startswith('text#category=overall&leaderboard_publish_date=2026-10-08&model_name=')
    assert 'rank' not in rid and 'vote' not in json.dumps(c)
    assert c['ingestion']['source_url'] == '%s/blob/%s/text/latest-00000-of-00001.parquet' % (L.HOME, COMMIT)


# ---- the cap -----------------------------------------------------------------------------------------------------

def test_overall_only_top_25_and_votes_only_as_observations(report):
    claims = [d for d in report['documents'] if d['entity_type'] == 'claim']
    per = {}
    for c in claims:
        per[c['metric']] = per.get(c['metric'], 0) + 1
    assert per['lmarena-text-score'] == 25 and per['lmarena-text-style-control-score'] == 25
    assert per['lmarena-video-edit-score'] == 10                      # an arena under the cap keeps every row
    assert report['arenas']['video_edit']['roster'] == 10 and report['arenas']['text']['roster'] == 30
    coding = {r['model_name'] for r in rows('text') if r['category'] == 'coding'}
    assert coding                                                      # the other category is in the file ...
    obs = [o for o in report['observations'] if o['arena'] == 'text']
    assert len(obs) == 25 and all(isinstance(o['votes'], float) for o in obs)  # ... and only overall's 25 are read


def test_full_is_never_requested(tmp_path):
    asked = []

    class Recording(FixtureTransport):
        def get(self, url, headers):
            asked.append(url)
            return super().get(url, headers)
    run(transport=Recording(FIX))
    assert asked[0] == L.API and len(asked) == 1 + 2 * 5
    assert not any('full-' in u for u in asked)


def test_agent_arenas_ips_scores_wait_for_a_person(report):
    (u,) = [u for u in report['unresolved_items'] if u['source_key'] == 'arena:agent']
    assert u['field'] == 'stanza' and 'IPS scores' in u['human_task']
    assert report['arenas']['agent']['scoring'] == 'ips'
    assert not any('agent' in d['path'] for d in report['documents'])


# ---- the failure cases -----------------------------------------------------------------------------------------

def test_a_pool_of_fewer_than_two_resolved_members_drafts_nothing():
    one = overall('video_edit')[0]['model_name']
    rep = run(res={'system': Index('system', [Entry(system_id(one), one)])})
    assert rep['status'] == 'ok' and not [d for d in rep['documents'] if 'video-edit' in d['path']]
    (u,) = [u for u in rep['unresolved_items'] if u['field'] == 'rating_pool' and u['source_key'] == 'arena:video_edit']
    assert '1 of its top 25 resolve' in u['human_task'] and 'no pool, so no rating claim' in u['human_task']
    assert not [d for d in rep['documents'] if d['entity_type'] == 'claim']


def rewrite(tmp_path, arena, table):
    """A copy of the fixture whose `arena` file is `table`, with the metadata's hash and the CDN URL to match."""
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    data = buf.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    (d / (arena + '.parquet')).write_bytes(data)
    cdn = 'https://us.aws.cdn.hf.co/xet-bridge-us/fixture/%s' % sha
    for name, update in ((arena + '.parquet.headers.json', lambda h: h.update(url=cdn)),
                         (arena + '.resolve.headers.json', lambda h: h.update(headers=[['Location', cdn]]))):
        h = json.loads((d / name).read_text(encoding='utf-8'))
        update(h)
        (d / name).write_text(json.dumps(h), encoding='utf-8')
    meta = json.loads((d / 'api.json').read_text(encoding='utf-8'))
    for s in meta['siblings']:
        if s['rfilename'] == '%s/latest-00000-of-00001.parquet' % arena:
            s['lfs']['sha256'] = sha
    (d / 'api.json').write_text(json.dumps(meta), encoding='utf-8')
    return str(d)


def test_a_renamed_rating_column_is_drift_a_hard_fail(tmp_path):
    t = pq.read_table(os.path.join(FIX, 'text.parquet'))
    renamed = t.rename_columns(['arena_score' if c == 'rating' else c for c in t.column_names])
    rep = run(rewrite(tmp_path, 'text', renamed))
    assert rep['status'] == 'hard-fail' and rep['documents'] == []
    assert 'neither the Arena Score schema' in rep['errors'][0]
    assert rep['issue']['labels'] == ['adapter-broken', 'source:lmarena']


def test_two_publish_dates_in_overall_is_drift(tmp_path):
    t = pq.read_table(os.path.join(FIX, 'webdev.parquet')).to_pylist()
    t[0]['leaderboard_publish_date'] = '2026-09-01'
    rep = run(rewrite(tmp_path, 'webdev', pa.Table.from_pylist(t, schema=pq.read_schema(os.path.join(FIX, 'webdev.parquet')))))
    assert rep['status'] == 'hard-fail' and 'carries 2 publish dates' in rep['errors'][0]


def test_a_licence_tag_that_is_not_cc_by_is_a_veto(tmp_path):
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    meta = json.loads((d / 'api.json').read_text(encoding='utf-8'))
    meta['tags'] = [t if not t.startswith('license:') else 'license:cc-by-nc-4.0' for t in meta['tags']]
    (d / 'api.json').write_text(json.dumps(meta), encoding='utf-8')
    rep = run(str(d))
    assert rep['status'] == 'hard-fail' and rep['errors'][0].startswith('LicenceVeto')
    assert 'license:cc-by-nc-4.0' in rep['errors'][0] and rep['documents'] == []


def test_a_file_that_does_not_hash_to_its_metadata_is_refused(tmp_path):
    d = tmp_path / 'fix'
    shutil.copytree(FIX, d)
    (d / 'text.parquet').write_bytes((d / 'text.parquet').read_bytes() + b'\0')
    rep = run(str(d))
    assert rep['status'] == 'hard-fail' and 'does not hash to the sha256 its metadata names' in rep['errors'][0]


def test_an_unchanged_commit_is_no_change_and_an_unchanged_file_is_not_fetched():
    state = L.new_state()
    run(state=state)
    assert state['commit'] == COMMIT and state['arenas']['text']['date'] == '2026-10-08'
    assert run(state=state)['status'] == 'no-change'
    state['commit'] = 'an-older-commit'
    asked = []

    class Recording(FixtureTransport):
        def get(self, url, headers):
            asked.append(url)
            return super().get(url, headers)
    rep = run(state=state, transport=Recording(FIX))
    assert asked == [L.API] and rep['candidates_seen'] == 0     # every file's hash is the one the state holds


def test_a_vanished_arena_is_a_lifecycle_review_and_keeps_its_last_snapshot():
    state = L.new_state()
    run(state=state)
    state['commit'] = 'an-older-commit'
    state['arenas']['search'] = {'sha256': '0' * 64, 'date': '2026-08-24'}
    rep = run(state=state)
    (u,) = [u for u in rep['unresolved_items'] if u['source_key'] == 'arena:search']
    assert u['reason'] == 'out-of-band' and 'lineage event' in u['human_task'] and '2026-08-24' in u['human_task']
    assert rep['drafts']['gone'] == 1 and state['arenas']['search']['date'] == '2026-08-24'


# ---- the network -----------------------------------------------------------------------------------------------

def test_every_request_asks_the_gate_first_and_the_cdn_host_is_listed():
    asked = []

    class Refusing:
        def admit(self, url):
            asked.append(url)
            raise P.Forbidden(url, 'refused in this test')
    rep = L.run(L.LMArena(L.NetworkTransport(gate=Refusing())), L.new_state(), resolvers())
    assert rep['status'] == 'hard-fail' and asked == [L.API]
    with pytest.raises(ValueError, match='HTTPS only'):
        L.NetworkTransport(gate=Refusing()).get('http://huggingface.co/api/datasets/x', {})
    pol = P.Policy.load()
    assert 'us.aws.cdn.hf.co' in pol.hosts and 'huggingface.co' in pol.hosts


def test_a_redirect_is_followed_by_the_adapter_not_by_urllib():
    calls = []

    class Hops:
        def get(self, url, headers):
            calls.append(url)
            from ingest.http.backoff import Response
            if len(calls) == 1:
                return Response(302, [('Location', 'https://us.aws.cdn.hf.co/x')], b'')
            return Response(200, [], b'bytes')
    assert L.download(Hops(), 'https://huggingface.co/datasets/x/resolve/c/a/f') == b'bytes'
    assert calls == ['https://huggingface.co/datasets/x/resolve/c/a/f', 'https://us.aws.cdn.hf.co/x']


def test_bench_ingest_lmarena_over_the_fixture():
    from tools import cli
    r = CliRunner().invoke(cli.app, ['ingest', 'lmarena', '--dry-run', '--fixture', FIX])
    assert r.exit_code == 0, r.output
    assert 'ingest lmarena %s: ok' % L.VERSION in r.output and 'arenas        agent=ips' in r.output
