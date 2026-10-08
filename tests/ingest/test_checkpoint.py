"""The state layer, the cursor and the checkpoint (P5-S2-T02; 07 S1.1, S3.2, S4).

The verify: `pytest tests/ingest/test_checkpoint.py`. Done when "A run stopped at the wall clock writes a
cursor, exits partial, and the next run resumes rather than restarts." That is asserted on a synthetic
adapter, where every count is exact, and then on both real adapters: hf-hub over its committed fixture and
Epoch over its recorded bundle. The failure cases sit beside it: a run that dies mid-way keeps nothing it
fetched after its last checkpoint, and a checkpoint key that is no longer listed restarts the run instead
of skipping it.
"""
import json
import os
import socket
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.adapters import epoch, hf_hub
from ingest.adapters.base import Adapter, Candidate, Draft, Payload
from ingest.http.fixture import FixtureTransport
from ingest.resolve import thaw
from ingest.runner import state as S

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HF_FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
EPOCH_FIX = os.path.join(ROOT, 'tests', 'fixtures', 'epoch')
WHEN = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('network call attempted: %r' % (a,))
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)


class Tick:
    """A wall clock that moves `step` seconds every time it is read. run() reads it once at the start
    and once after each candidate, so after candidate i the run has been going i * step seconds."""

    def __init__(self, step=1.0):
        self.t, self.step = 0.0, step

    def __call__(self):
        t, self.t = self.t, self.t + self.step
        return t


class Listing(Adapter):
    """A synthetic source of `keys`. fetch() records each key it fetches in the state, as hf-hub records
    a payload's hash, and fails on any key in `fail_on`."""
    name, version, licence, licence_class = 'listing', '0.0.1', 'CC0-1.0', 'permissive-attribution'
    attribution, expected_yield = 'Listing', (1, 1000)

    def __init__(self, keys, fail_on=()):
        self.keys, self.fail_on, self.fetched = list(keys), set(fail_on), []
        self.checkpoints = []

    def discover(self, state):
        for k in self.keys:
            yield Candidate(k, 'claim', None)

    def fetch(self, c, state):
        if c.source_key in self.fail_on:
            raise ConnectionError('upstream went away at %s' % c.source_key)
        self.fetched.append(c.source_key)
        state.setdefault('records', {})[c.source_key] = 'seen'
        return Payload(c, c.source_key.encode(), 'text/plain', 200, WHEN, None, None, '0' * 64, False)

    def normalise(self, p, resolver):
        return [Draft('claim', None, Path('x/%s' % p.candidate.source_key), {'k': p.candidate.source_key},
                      'new', {}, 1.0)], []

    def checkpoint(self, state, cursor):
        self.checkpoints.append(dict(cursor))
        super().checkpoint(state, cursor)


def keys(n):
    return ['k:%04d' % i for i in range(n)]


class Sink:
    def __init__(self):
        self.batches = []

    def __call__(self, drafts, unresolved):
        self.batches.append([d.payload['k'] for d in drafts])

    @property
    def keys(self):
        return [k for b in self.batches for k in b]


def fresh(tmp_path, name='listing'):
    path = str(tmp_path / ('%s.json' % name))
    return path, S.load(path, S.new(name, '0.0.1'))


# ---- the done_when ----------------------------------------------------------------------------------------

def test_a_run_stopped_at_the_wall_clock_writes_a_cursor_and_exits_partial(tmp_path):
    path, state = fresh(tmp_path)
    sink = Sink()
    report = S.run(Listing(keys(150)), state, path, sink=sink, max_runtime=100, clock=Tick(), now=lambda: WHEN)
    assert report['status'] == 'partial' and report['open_pr'] is False
    assert report['processed'] == 80                                   # 80% of a 100-second budget, 1 s each
    on_disk = json.load(open(path, encoding='utf-8'))
    assert on_disk['checkpoint'] == {'after': 'k:0079', 'done': 80, 'run_started': '2026-10-08T06:00:00Z'}
    assert sink.keys == keys(80) and len(on_disk['records']) == 80     # what was fetched was also written
    assert on_disk['yield_history'] == []                              # a partial run is not a yield


def test_the_next_run_resumes_rather_than_restarts(tmp_path):
    path, state = fresh(tmp_path)
    S.run(Listing(keys(150)), state, path, sink=Sink(), max_runtime=100, clock=Tick(), now=lambda: WHEN)
    adapter, sink = Listing(keys(150)), Sink()
    report = S.run(adapter, S.load(path, S.new('listing', '0.0.1')), path, sink=sink, now=lambda: WHEN)
    assert report['status'] == 'ok' and report['resumed_from'] == 'k:0079' and report['passed_over'] == 80
    assert adapter.fetched == keys(150)[80:] and sink.keys == keys(150)[80:]   # nothing fetched twice
    on_disk = json.load(open(path, encoding='utf-8'))
    assert on_disk['checkpoint'] is None and on_disk['yield_history'] == [150]  # the whole run's yield


def test_a_run_that_meets_no_deadline_is_one_ok_run(tmp_path):
    path, state = fresh(tmp_path)
    report = S.run(Listing(keys(50)), state, path, sink=Sink(), max_runtime=1000, clock=Tick(), now=lambda: WHEN)
    assert report['status'] == 'ok' and report['open_pr'] is True and report['processed'] == 50
    assert state['checkpoint'] is None and state['consecutive_failures'] == 0


# ---- checkpoint every 200, and at 80% --------------------------------------------------------------------

def test_checkpoint_is_called_every_200_candidates(tmp_path):
    path, state = fresh(tmp_path)
    adapter = Listing(keys(450))
    report = S.run(adapter, state, path, sink=Sink(), now=lambda: WHEN)
    assert [c['after'] for c in adapter.checkpoints] == ['k:0199', 'k:0399'] and report['checkpoints'] == 2
    assert state['checkpoint'] is None                                 # finalise() cleared it at the end


def test_the_deadline_checkpoint_is_taken_once_and_the_run_stops(tmp_path):
    path, state = fresh(tmp_path)
    adapter = Listing(keys(1000))
    report = S.run(adapter, state, path, sink=Sink(), max_runtime=500, clock=Tick(), now=lambda: WHEN)
    assert [c['after'] for c in adapter.checkpoints] == ['k:0199', 'k:0399']   # 400 = 80% of 500
    assert report['status'] == 'partial' and report['processed'] == 400 and len(adapter.fetched) == 400


def test_drafts_reach_the_sink_before_the_state_that_covers_them_is_written(tmp_path, monkeypatch):
    events = []
    real = S.save
    monkeypatch.setattr(S, 'save', lambda p, s: (events.append(('save', len(s['records']))), real(p, s)))
    path, state = fresh(tmp_path)
    S.run(Listing(keys(450)), state, path, sink=lambda d, u: events.append(('sink', len(d))), now=lambda: WHEN)
    assert events == [('sink', 200), ('save', 200), ('sink', 200), ('save', 400), ('sink', 50), ('save', 450)]


# ---- the failure cases ----------------------------------------------------------------------------------

def test_a_failed_run_keeps_nothing_it_fetched_after_its_last_checkpoint(tmp_path):
    path, state = fresh(tmp_path)
    sink = Sink()
    report = S.run(Listing(keys(450), fail_on={'k:0250'}), state, path, sink=sink, now=lambda: WHEN)
    assert report['status'] == 'hard-fail' and 'upstream went away at k:0250' in report['errors'][0]
    on_disk = json.load(open(path, encoding='utf-8'))
    assert on_disk['checkpoint']['after'] == 'k:0199' and on_disk['consecutive_failures'] == 1
    assert sorted(on_disk['records']) == keys(200)        # 200-249 were fetched, never written, never "seen"
    assert sink.keys == keys(200) and state == on_disk    # the in-memory state is the saved one, not the lost one
    # and the next run resumes from the last safe point
    adapter = Listing(keys(450))
    report = S.run(adapter, S.load(path, S.new('listing', '0.0.1')), path, sink=Sink(), now=lambda: WHEN)
    assert report['status'] == 'ok' and adapter.fetched == keys(450)[200:]
    assert json.load(open(path, encoding='utf-8'))['consecutive_failures'] == 0


def test_a_checkpoint_key_no_longer_listed_restarts_the_run_instead_of_skipping_it(tmp_path):
    path, state = fresh(tmp_path)
    S.run(Listing(keys(150)), state, path, sink=Sink(), max_runtime=100, clock=Tick(), now=lambda: WHEN)
    gone = [k for k in keys(150) if k != 'k:0079']
    adapter = Listing(gone)
    report = S.run(adapter, S.load(path, S.new('listing', '0.0.1')), path, sink=Sink(), now=lambda: WHEN)
    assert adapter.fetched == gone and report['processed'] == len(gone)
    assert any('no longer listed' in n for n in report['notes'])


# ---- the state file (07 S4) -----------------------------------------------------------------------------

def test_a_new_state_has_every_07_s4_key_and_no_problems():
    st = S.new('x', '1.0.0')
    assert set(st) == {'adapter', 'adapter_version', 'last_run', 'last_success', 'last_change',
                       'consecutive_failures', 'cursor', 'checkpoint', 'urls', 'absences', 'yield_history'}
    assert S.problems(st) == []


@pytest.mark.parametrize('edit, why', [
    (lambda s: s.pop('absences'), 'missing absences'),
    (lambda s: s['absences'].update(x=0), 'positive integer'),
    (lambda s: s.update(yield_history=list(range(9))), 'at most 8'),
    (lambda s: s.update(checkpoint={'after': 'k'}), 'after, done and run_started'),
])
def test_problems_names_a_malformed_state(edit, why):
    st = S.new('x', '1.0.0')
    edit(st)
    assert any(why in p for p in S.problems(st))


def test_load_fills_keys_an_older_file_lacks_and_refuses_another_adapters_file(tmp_path):
    path = str(tmp_path / 'x.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'adapter': 'x', 'urls': {}}, f)
    assert S.problems(S.load(path, S.new('x', '1.0.0'))) == []
    with pytest.raises(ValueError, match="not 'y'"):
        S.load(path, S.new('y', '1.0.0'))


def test_save_is_atomic_sorted_and_writes_records_one_per_line(tmp_path):
    path = str(tmp_path / 'x.json')
    st = S.new('x', '1.0.0', records={'b': {'sha256': '2'}, 'a': {'sha256': '1'}})
    st['urls'] = {'https://z': {}, 'https://a': {}}
    S.save(path, st)
    text = open(path, encoding='utf-8').read()
    assert '    "a": {"sha256": "1"},\n    "b": {"sha256": "2"}\n' in text
    assert text.index('https://a') < text.index('https://z') and text.endswith('}\n')
    assert not os.path.exists(path + '.tmp') and json.loads(text) == st
    assert S.dumps(json.loads(text)) == text                                       # a round trip is a fixed point


def test_state_is_committed_and_only_regenerable_bulk_is_ignored():
    """07 S4: layer 2 is committed; layer 3 (ingest/raw/, the actions/cache content) is not."""
    assert S.path_for('hf-hub') == os.path.join(ROOT, 'ingest', 'state', 'hf-hub.json')
    def ignored(p):
        return subprocess.run(['git', '-C', ROOT, 'check-ignore', '-q', p], check=False).returncode == 0
    assert not ignored('ingest/state/hf-hub.json') and not ignored('ingest/state/epoch.json')
    assert ignored('ingest/raw/hf-hub/cache/x.json')


# ---- the real adapters -----------------------------------------------------------------------------------

class Collect:
    """A sink that records which source keys each run produced a draft or an Unresolved for."""

    def __init__(self):
        self.drafts, self.unresolved = [], []

    def __call__(self, drafts, unresolved):
        self.drafts += [d.ingestion['source_record_id'] for d in drafts]
        self.unresolved += [u.source_key for u in unresolved]


def test_hf_hub_stopped_at_the_wall_clock_resumes_on_its_fixture(tmp_path):
    with open(os.path.join(HF_FIX, 'resolver-snapshot.json'), encoding='utf-8') as f:
        resolver = thaw(json.load(f))
    path, cache, out = str(tmp_path / 'hf-hub.json'), hf_hub.RequestCache(str(tmp_path / 'cache')), Collect()

    def go(**kw):
        a = hf_hub.HfHub(FixtureTransport(HF_FIX), cache, now=lambda: WHEN)
        return S.run(a, hf_hub.load_state(path), path, resolver=resolver, sink=out, now=lambda: WHEN, **kw)
    first = go(max_runtime=1000, clock=Tick())
    assert first['status'] == 'partial' and first['processed'] == 800 and len(out.drafts) == 800
    assert hf_hub.load_state(path)['checkpoint']['done'] == 800
    second = go()
    assert second['status'] == 'ok' and second['passed_over'] == 800
    # 1,000 Spaces and the one recorded dataset detail, each drafted exactly once across the two runs
    assert len(out.drafts) == len(set(out.drafts)) == 1001
    assert hf_hub.load_state(path)['checkpoint'] is None


def test_epoch_stopped_inside_its_bundle_fetches_it_whole_and_finishes_it(tmp_path):
    path, out = str(tmp_path / 'epoch.json'), Collect()

    def go(**kw):
        t = FixtureTransport(EPOCH_FIX)
        st = S.load(path, S.new(epoch.NAME, epoch.VERSION, etags={}))
        return t, S.run(epoch.Epoch(t, now=lambda: WHEN), st, path, sink=out, now=lambda: WHEN, **kw)
    _, first = go(max_runtime=2.5, clock=Tick())               # 80% of 2.5 s: two candidates of four
    assert first['status'] == 'partial' and first['processed'] == 2
    t2, second = go()
    assert t2.requests == [(epoch.ZIP_URL, {})]                  # unconditional: a 304 would finish nothing
    assert second['status'] == 'no-change' and second['passed_over'] == 2 and second['processed'] == 2
    assert out.unresolved == ['csv:example_bench', 'csv:example_orphan_external']   # each CSV once
    t3, third = go()
    assert t3.requests[0][1] == {'If-None-Match': json.load(open(path, encoding='utf-8'))['etags'][epoch.ZIP_URL]}
    assert third['candidates_seen'] == 0                         # a finished bundle is conditional again
