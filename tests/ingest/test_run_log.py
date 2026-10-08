"""The RunReport and the committed run log (P5-S4-T01; 07 S1.1, S9, S6.4).

The verify: `pytest tests/ingest/test_run_log.py`. Done when "A run that changed nothing still leaves a
committed record, so 'when did this adapter last actually work' is answerable from a clone." Asserted on a
synthetic adapter run through the shared runner, then on hf-hub over its committed fixture. The failure
case sits beside it: a run that fails also leaves its record, and the question skips it.
"""
import json
import os
import subprocess
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ingest.adapters import epoch, hf_hub
from ingest.adapters.base import Adapter, Candidate, Draft, Payload, RunReport, Unresolved
from ingest.http.fixture import FixtureTransport
from ingest.resolve import thaw
from ingest.runner import report as R
from ingest.runner import state as S

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HF_FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
DAY1 = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)


def at(days):
    return lambda: DAY1 + timedelta(days=days)


class Listing(Adapter):
    """Three records; fetch() returns a payload only for a key it has not seen (as an ETag would), and
    raises on a key in `fail_on`. Every payload drafts one record and one Unresolved."""
    name, version, licence, licence_class = 'listing', '0.0.1', 'CC0-1.0', 'permissive-attribution'
    attribution, expected_yield = 'Listing', (1, 10)

    def __init__(self, keys=('k:1', 'k:2', 'k:3'), fail_on=()):
        self.keys, self.fail_on = list(keys), set(fail_on)
        self.http_codes = {}

    def discover(self, state):
        for k in self.keys:
            yield Candidate(k, 'claim', None)

    def fetch(self, c, state):
        if c.source_key in self.fail_on:
            raise ConnectionError('upstream went away at %s' % c.source_key)
        seen = state.setdefault('records', {})
        if c.source_key in seen:
            self.http_codes[304] = self.http_codes.get(304, 0) + 1     # get-default: a first 304
            return None
        self.http_codes[200] = self.http_codes.get(200, 0) + 1         # get-default: a first 200
        seen[c.source_key] = 'seen'
        return Payload(c, b'x', 'text/plain', 200, DAY1, None, None, '0' * 64, c.source_key == 'k:3')

    def normalise(self, p, resolver):
        k = p.candidate.source_key
        return ([Draft('claim', None, Path('x/%s' % k), {}, 'new', {}, 1.0)],
                [Unresolved(k, 'model', 'Model ' + k, 'no-match')])


def run(tmp_path, adapter, now, **kw):
    path = str(tmp_path / 'state.json')
    return S.run(adapter, S.load(path, S.new(adapter.name, adapter.version)), path, now=now,
                 log_root=str(tmp_path), **kw)


# ---- the done_when -------------------------------------------------------------------------------------------

def test_a_run_that_changed_nothing_still_leaves_a_committed_record(tmp_path):
    first = run(tmp_path, Listing(), at(0))
    second = run(tmp_path, Listing(), at(1))
    assert (first['status'], second['status']) == ('ok', 'no-change')
    assert (first['log'], second['log']) == ('ingest/runs/listing/2026-10-08.json', 'ingest/runs/listing/2026-10-09.json')
    quiet = json.load(open(tmp_path / second['log'], encoding='utf-8'))
    assert quiet['status'] == 'no-change' and quiet['drafts'] == dict.fromkeys(R.CHANGE_CLASSES, 0)
    assert quiet['candidates_seen'] == 3 and quiet['payloads_fetched'] == 0 and quiet['http_codes'] == {'304': 3}


def test_when_did_this_adapter_last_actually_work_is_answered_from_the_files(tmp_path):
    run(tmp_path, Listing(), at(0))
    run(tmp_path, Listing(), at(1))
    worked = R.last_worked('listing', str(tmp_path))
    assert worked.status == 'no-change' and worked.finished_at == DAY1 + timedelta(days=1)
    assert [r.status for r in R.history('listing', str(tmp_path))] == ['ok', 'no-change']


def test_a_failed_run_leaves_its_record_and_the_question_skips_it(tmp_path):
    run(tmp_path, Listing(), at(0))
    failed = run(tmp_path, Listing(keys=('k:1', 'k:4'), fail_on={'k:4'}), at(1))
    assert failed['status'] == 'hard-fail' and failed['log'] == 'ingest/runs/listing/2026-10-09.json'
    log = json.load(open(tmp_path / failed['log'], encoding='utf-8'))
    assert log['status'] == 'hard-fail' and 'upstream went away at k:4' in log['errors'][0]
    assert R.last_worked('listing', str(tmp_path)).finished_at == DAY1      # the day before still answers


def test_an_adapter_that_never_worked_has_no_answer_rather_than_a_wrong_one(tmp_path):
    run(tmp_path, Listing(keys=('k:9',), fail_on={'k:9'}), at(0))
    assert R.last_worked('listing', str(tmp_path)) is None
    assert R.last_worked('never-ran', str(tmp_path)) is None


def test_a_second_run_on_the_same_day_is_kept_beside_the_first(tmp_path):
    a = run(tmp_path, Listing(), at(0))
    b = run(tmp_path, Listing(), at(0))
    c = run(tmp_path, Listing(), at(0))
    assert [a['log'], b['log'], c['log']] == ['ingest/runs/listing/2026-10-08.json',
                                              'ingest/runs/listing/2026-10-08.2.json',
                                              'ingest/runs/listing/2026-10-08.3.json']
    assert [r.status for r in R.history('listing', str(tmp_path))] == ['ok', 'no-change', 'no-change']


# ---- every 07 S1.1 field populated ---------------------------------------------------------------------------

def test_every_runreport_field_is_written_in_07_s1_1s_order(tmp_path):
    out = run(tmp_path, Listing(), at(0))
    raw = open(tmp_path / out['log'], encoding='utf-8').read()
    doc = json.loads(raw)
    assert list(doc) == [f.name for f in fields(RunReport)]
    assert doc['drafts'] == {'new': 3, 'field-change': 0, 'result-change': 0, 'metrics-only': 0, 'gone': 0,
                             'no-change': 0}
    assert doc['http_codes'] == {'200': 3} and doc['payloads_fetched'] == 3 and doc['payloads_from_cache'] == 1
    assert doc['unresolved_new'] == 3 and doc['unresolved_carried'] == 0
    assert doc['started_at'] == '2026-10-08T06:00:00Z' and len(doc['resolver_snapshot_sha256']) == 64
    assert raw.endswith('}\n') and '\r' not in raw


def test_unresolved_items_already_on_the_ledger_are_carried_not_new(tmp_path):
    from ingest import unresolved
    unresolved.record('listing', [Unresolved('k:1', 'model', 'Model k:1', 'no-match')], date(2026, 10, 1),
                      str(tmp_path))
    out = run(tmp_path, Listing(), at(0))
    doc = json.load(open(tmp_path / out['log'], encoding='utf-8'))
    assert (doc['unresolved_new'], doc['unresolved_carried']) == (2, 1)


def test_the_resolver_hash_is_the_frozen_snapshots_own():
    with open(os.path.join(HF_FIX, 'resolver-snapshot.json'), encoding='utf-8') as f:
        frozen = json.load(f)
    assert R.resolver_sha256(thaw(frozen)) == frozen['sha256']       # a thawed index map hashes as freeze() did
    assert R.resolver_sha256(frozen) == frozen['sha256']
    assert R.resolver_sha256(None) == R.resolver_sha256({})            # no resolver: one stated, stable value


@pytest.mark.parametrize('over, why', [
    ({'status': 'fine'}, 'status'),
    ({'drafts': {'renamed': 1}}, 'change class'),
    ({'resolver_snapshot_sha256': 'abc'}, 'sha256'),
    ({'candidates_seen': -1}, 'counts'),
    ({'finished_at': DAY1 - timedelta(seconds=1)}, 'before it started'),
])
def test_a_malformed_report_is_refused_not_written(over, why):
    kw = dict(adapter='x', adapter_version='0.1.0', started_at=DAY1, finished_at=DAY1, status='ok', http_codes={},
              candidates_seen=0, payloads_fetched=0, payloads_from_cache=0, drafts={}, unresolved_new=0,
              unresolved_carried=0, resolver_snapshot_sha256='0' * 64)
    kw.update(over)
    with pytest.raises(R.ReportError, match=why):
        R.build(**kw)


def test_a_log_round_trips_and_a_truncated_one_is_refused(tmp_path):
    out = run(tmp_path, Listing(), at(0))
    doc = json.load(open(tmp_path / out['log'], encoding='utf-8'))
    assert R.as_dict(R.from_dict(doc)) == doc
    doc.pop('http_codes')
    with pytest.raises(R.ReportError, match='http_codes'):
        R.from_dict(doc)


# ---- a real adapter --------------------------------------------------------------------------------------------

def test_hf_hub_twice_on_its_fixture_logs_both_runs(tmp_path):
    with open(os.path.join(HF_FIX, 'resolver-snapshot.json'), encoding='utf-8') as f:
        frozen = json.load(f)
    resolver, cache, path = thaw(frozen), hf_hub.RequestCache(str(tmp_path / 'cache')), str(tmp_path / 'st.json')

    def go(day):
        a = hf_hub.HfHub(FixtureTransport(HF_FIX), cache, now=at(day))
        return S.run(a, hf_hub.load_state(path), path, resolver=resolver, now=at(day), log_root=str(tmp_path))
    go(0)
    go(1)
    first, second = R.history('hf-hub', str(tmp_path))
    assert first.status == 'ok' and first.drafts['new'] == 1001 and first.http_codes == {200: 3}
    # the two listings answer 304; the dataset detail is short-circuited on lastModified, never requested
    assert second.status == 'no-change' and sum(second.drafts.values()) == 0 and second.http_codes == {304: 2}
    assert first.resolver_snapshot_sha256 == second.resolver_snapshot_sha256 == frozen['sha256']
    assert R.last_worked('hf-hub', str(tmp_path)) == second


# ---- where the files go ---------------------------------------------------------------------------------------

def test_run_logs_and_state_are_export_ignored_and_committed():
    """07 S6.4 (a): outside the citable tree, never in a release tarball, and not gitignored."""
    def attr(p):
        return subprocess.run(['git', '-C', ROOT, 'check-attr', 'export-ignore', p], capture_output=True,
                              text=True, check=True).stdout.strip().rsplit(': ', 1)[-1]
    def ignored(p):
        return subprocess.run(['git', '-C', ROOT, 'check-ignore', '-q', p], check=False).returncode == 0
    assert attr('ingest/runs/hf-hub/2026-10-08.json') == 'set' and attr('ingest/state/hf-hub.json') == 'set'
    assert attr('data/benchmarks/x/y.yaml') == 'unspecified'
    assert not ignored('ingest/runs/hf-hub/2026-10-08.json')


def test_the_raw_artifact_keeps_8_runs_and_no_body_a_licence_bars():
    rr = R.build(adapter='hf-hub', adapter_version='0.1.0', started_at=DAY1, finished_at=DAY1, status='ok',
                 http_codes={}, candidates_seen=0, payloads_fetched=0, payloads_from_cache=0, drafts={},
                 unresolved_new=0, unresolved_carried=0, resolver_snapshot_sha256='0' * 64)
    hf = R.raw_artifact(hf_hub.HfHub, rr)
    assert hf['retention-days'] == 8 and hf['path'] == 'ingest/raw/hf-hub/'
    assert hf['exclude'] == ['**/*.body', '**/*.body.gz']           # unlicensed class: headers and hashes only
    ep = R.raw_artifact(epoch.Epoch, rr, cadence_days=7)
    assert ep['retention-days'] == 56 and ep['exclude'] == []        # CC-BY: the body may be kept
