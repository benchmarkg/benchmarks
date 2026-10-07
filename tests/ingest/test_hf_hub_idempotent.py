"""The hf-hub determinism and idempotency suite (P5-S1-T06; 07 S1.4, S1.5, S7.3).

The verify: `pytest tests/ingest/test_hf_hub_idempotent.py`. Done when "Run 2 produces zero drafts, run 3
produces exactly one result-change, and run 4's deletion surfaces as gone on the following run". That is
07 S1.4's four-run matrix, run here against the committed fixture set and the resolver snapshot frozen
beside it (tests/ingest/fixtures/hf-hub/resolver-snapshot.json):

    run 1  the fixture set                    -> one draft per payload, every one `new`
    run 2  the same set, the same snapshot    -> zero drafts, status no-change, a zero-byte tree diff
    run 3  one Space with an edited value      -> exactly one draft
    run 4  one Space deleted                   -> zero drafts on this run ...
    run 5  the same set again                  -> ... and one `gone` on the next

Run 3's draft is a `field-change`, not a `result-change`: an hf-hub draft is a discovery candidate and
carries no numeric result, so 07 S6.2's NUMERIC RESULT CHANGE cannot arise from this adapter. The test
asserts that, rather than renaming the class to fit the sentence.

Two edits make the committed fixtures a set a matrix can run on. The Spaces listing's recorded first page
links to a second page the set does not hold; a run that meets that edge has not seen every record, and
07 S7.3 must not count an absence from it. So the matrix runs on a copy whose Link header is dropped,
making the recorded page the whole listing; and a test shows the uncut set counts nothing. Every run has
the network cut at the socket.
"""
import copy
import hashlib
import json
import os
import shutil
import socket
import urllib.request
from datetime import datetime, timezone

import pytest
import yaml

from ingest import emit
from ingest.adapters import hf_hub as H
from ingest.resolve import Index, freeze, thaw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'hf-hub')
SNAPSHOT = os.path.join(FIX, 'resolver-snapshot.json')
XWALK = H.load_crosswalk()
EDITED, DELETED = 5, 7             # indexes into the recorded Spaces listing
NEW_TAG = 'judge:humans'          # a crosswalk row, so the edit changes what normalise() suggests


def _snapshot():
    with open(SNAPSHOT, encoding='utf-8') as f:
        return json.load(f)


RESOLVERS = thaw(_snapshot())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('network call attempted: %r' % (a,))
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)


# ---- fixture sets -----------------------------------------------------------------------------------

def _headers_file(directory):
    return os.path.join(directory, 'spaces-leaderboard.json.headers.json')


def _rewrite_meta(directory, fn):
    with open(_headers_file(directory), encoding='utf-8') as f:
        meta = json.load(f)
    fn(meta)
    with open(_headers_file(directory), 'w', encoding='utf-8') as f:
        json.dump(meta, f)


def _set_header(meta, name, value):
    meta['headers'] = [h for h in meta['headers'] if h[0].lower() != name.lower()] + [[name, value]]


def complete_copy(directory):
    """The committed set with the Spaces listing's Link to an unrecorded page dropped."""
    shutil.copytree(FIX, directory)
    _rewrite_meta(directory, lambda m: m.update(headers=[h for h in m['headers'] if h[0] != 'Link']))
    return directory


def variant(base, directory, edit=None, etag=None, date=None):
    """A copy of fixture set `base` whose Spaces listing `edit` changes, behind a new ETag."""
    shutil.copytree(base, directory)
    path = os.path.join(directory, 'spaces-leaderboard.json')
    if edit:
        with open(path, encoding='utf-8') as f:
            spaces = json.load(f)
        edit(spaces)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(spaces, f)
    _rewrite_meta(directory, lambda m: (_set_header(m, 'ETag', etag) if etag else None,
                                        _set_header(m, 'Date', date) if date else None))
    return directory


def _recorded_spaces():
    with open(os.path.join(FIX, 'spaces-leaderboard.json'), encoding='utf-8') as f:
        return json.load(f)


SPACES = _recorded_spaces()
EDITED_KEY, DELETED_KEY = 'space:' + SPACES[EDITED]['id'], 'space:' + SPACES[DELETED]['id']


def add_tag(spaces):
    assert NEW_TAG not in spaces[EDITED]['tags']
    spaces[EDITED]['tags'].append(NEW_TAG)


def delete(spaces):
    del spaces[DELETED]


# ---- a run, and the tree it writes ---------------------------------------------------------------------

class Runner:
    """One state file, request cache and data tree, run against whichever fixture set a test names; each
    run is one day later than the last, so a date a run writes says which run wrote it."""

    def __init__(self, base, resolvers=RESOLVERS):
        self.base, self.resolvers = str(base), resolvers
        self.root, self.cache = os.path.join(self.base, 'root'), os.path.join(self.base, 'cache')
        self.state, self.day, self.dates = H.new_state(), 0, []

    def run(self, fixture, limit=None, write=True):
        self.day += 1
        when = datetime(2026, 10, self.day, 6, 0, tzinfo=timezone.utc)
        self.dates.append(when.date().isoformat())
        adapter = H.HfHub(H.FixtureTransport(fixture), H.RequestCache(self.cache), now=lambda: when)
        report, drafts, unresolved = H.cycle(adapter, self.state, self.resolvers, XWALK, self.root, limit=limit)
        if write:
            H.write(drafts, self.root)
        return report, drafts, unresolved

    def tree(self):
        return tree(self.root)

    def fork(self, base):
        """An independent copy: the same tree, cache and state, in `base`."""
        other = Runner(base, self.resolvers)
        for d in ('root', 'cache'):
            if os.path.isdir(os.path.join(self.base, d)):
                shutil.copytree(os.path.join(self.base, d), os.path.join(str(base), d))
        other.state, other.day, other.dates = copy.deepcopy(self.state), self.day, list(self.dates)
        return other


def tree(root):
    """{relative path: bytes} for every file under `root`."""
    out = {}
    for d, _, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            with open(p, 'rb') as f:
                out[os.path.relpath(p, root).replace(os.sep, '/')] = f.read()
    return out


def changed(before, after):
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))  # get-default: a file only one side has


def rel(key):
    return '%s/%s.yaml' % (H.DISCOVERY, H.candidate_id(key))


def read(root, key):
    with open(os.path.join(root, rel(key)), encoding='utf-8') as f:
        return yaml.safe_load(f)


# ---- the matrix, run once for the module ----------------------------------------------------------------

@pytest.fixture(scope='module')
def sets(tmp_path_factory):
    base = tmp_path_factory.mktemp('sets')
    complete = complete_copy(str(base / 'complete'))
    return {
        'complete': complete,
        'edited': variant(complete, str(base / 'edited'), add_tag, 'W/"edited"'),
        'deleted': variant(complete, str(base / 'deleted'), lambda s: (add_tag(s), delete(s)), 'W/"deleted"'),
    }


@pytest.fixture(scope='module')
def baseline(tmp_path_factory, sets):
    """Run 1 on the complete set: a written tree and a state every other test forks from."""
    r = Runner(tmp_path_factory.mktemp('baseline'))
    r.report, r.drafts, r.unresolved = r.run(sets['complete'])
    return r


@pytest.fixture(scope='module')
def matrix(tmp_path_factory, sets, baseline):
    r = baseline.fork(tmp_path_factory.mktemp('matrix'))
    runs = {1: (baseline.report, baseline.drafts, baseline.tree(), baseline.tree())}
    for n, name in ((2, 'complete'), (3, 'edited'), (4, 'deleted'), (5, 'deleted'), (6, 'deleted')):
        before = r.tree()
        report, drafts, _ = r.run(sets[name])
        runs[n] = (report, drafts, before, r.tree())
    r.runs = runs
    return r


# ---- the frozen resolver snapshot ------------------------------------------------------------------------

def test_a_resolver_snapshot_is_frozen_beside_the_fixture_set():
    doc = _snapshot()
    assert set(doc['indexes']) == {'benchmark', 'leaderboard'}
    assert len(doc['built_from_commit']) == 40 and len(doc['sha256']) == 64
    assert doc['indexes']['benchmark']['entries'], 'an empty snapshot would resolve nothing and prove nothing'


def test_the_snapshot_is_refused_when_its_content_does_not_match_its_hash():
    doc = _snapshot()
    doc['indexes']['benchmark']['entries'][0]['name'] = 'renamed upstream'
    with pytest.raises(ValueError, match='sha256'):
        thaw(doc)


def test_a_thawed_index_resolves_exactly_as_the_index_it_froze():
    live = {k: Index.load(k) for k in ('benchmark', 'leaderboard')}
    thawed = thaw(freeze(['benchmark', 'leaderboard'], ROOT, 'x' * 40))
    for kind, index in live.items():
        probes = [s for e in index.entries.values() for s in (e.id, e.name, *e.aliases, *e.external_ids) if s]
        probes += [a.alias for a in index.alias_records]
        assert probes
        for s in probes:
            assert thawed[kind].resolve(s) == index.resolve(s), s


def test_the_matrix_reads_the_snapshot_not_the_tree():
    """The runner's resolvers come from the frozen file: data/ can move on without moving these drafts."""
    assert RESOLVERS['benchmark'].snapshot() == _snapshot()['indexes']['benchmark']


# ---- the done_when: 07 S1.4's four-run matrix --------------------------------------------------------------

def test_run_1_drafts_every_payload_as_new(matrix):
    report, drafts, _, after = matrix.runs[1]
    assert report['status'] == 'ok' and report['complete'] is True
    assert len(drafts) == report['payloads_fetched'] == len(SPACES) + 1     # 1,000 Spaces and openai/gsm8k
    assert {d.change_class for d in drafts} == {'new'} and report['drafts'] == {'new': len(drafts)}
    assert sorted(after) == sorted(d.path.as_posix() for d in drafts)
    assert all(p.startswith(H.DISCOVERY + '/') for p in after)


def test_run_2_produces_zero_drafts_and_a_zero_byte_diff(matrix):
    report, drafts, before, after = matrix.runs[2]
    assert drafts == [] and report['drafts'] == {} and report['status'] == 'no-change'
    assert report['payloads_fetched'] == 0 and report['complete'] is True
    assert changed(before, after) == []


def test_run_3_produces_exactly_one_draft_for_the_one_edited_value(matrix):
    report, drafts, before, after = matrix.runs[3]
    assert [(d.ingestion['source_record_id'], d.change_class) for d in drafts] == [(EDITED_KEY, 'field-change')]
    assert report['drafts'] == {'field-change': 1}
    assert changed(before, after) == [rel(EDITED_KEY)]
    assert any(s.get('tag') == NEW_TAG for s in drafts[0].payload['_suggested'])   # get-default: a dataset hint has no tag


def test_no_hf_hub_draft_is_ever_a_result_change(matrix):
    """hf-hub drafts carry no numeric result; 07 S6.2's result class is a claim's, never this adapter's."""
    assert all(d.change_class != 'result-change' for _, drafts, _, _ in matrix.runs.values() for d in drafts)


def test_run_4_deletion_produces_zero_drafts_and_one_absence(matrix):
    report, drafts, before, after = matrix.runs[4]
    assert drafts == [] and report['status'] == 'no-change'
    assert report['absent'] == [DELETED_KEY] and report['gone'] == []
    assert changed(before, after) == []


def test_run_4_deletion_surfaces_as_gone_on_the_following_run(matrix):
    report, drafts, before, after = matrix.runs[5]
    assert [(d.ingestion['source_record_id'], d.change_class) for d in drafts] == [(DELETED_KEY, 'gone')]
    assert report['drafts'] == {'gone': 1} and report['gone'] == [DELETED_KEY]
    assert {'ingest:gone', 'needs-scrutiny'} <= set(drafts[0].labels)
    # one changed record, not a corpus-wide diff, and never a deletion (07 S7.3)
    assert changed(before, after) == [rel(DELETED_KEY)] and rel(DELETED_KEY) in after


def test_the_gone_record_changes_only_its_last_seen_date_to_the_last_run_that_listed_it(matrix):
    _, _, before, after = matrix.runs[5]
    old, new = (yaml.safe_load(t[rel(DELETED_KEY)]) for t in (before, after))
    last_listed = matrix.dates[2]                                  # run 3, the last run whose listing held it
    assert new['ingestion'].pop('last_seen_upstream') == last_listed
    old['ingestion'].pop('last_seen_upstream')
    assert new == old
    diff = [a for a, b in zip(before[rel(DELETED_KEY)].splitlines(), after[rel(DELETED_KEY)].splitlines()) if a != b]
    assert diff == [b"  last_seen_upstream: '2026-09-24'"]         # the one line that moved


def test_gone_is_emitted_once_not_on_every_later_run(matrix):
    _, drafts, before, after = matrix.runs[6]
    assert drafts == [] and changed(before, after) == []
    assert matrix.state['absences'] == {DELETED_KEY: 3}


# ---- determinism: byte-identical output across repeated runs ----------------------------------------------

def test_repeated_runs_from_scratch_write_byte_identical_trees(tmp_path, sets, baseline):
    again = Runner(tmp_path)
    _, drafts, unresolved = again.run(sets['complete'])
    assert again.tree() == baseline.tree()
    assert [H.document(d) for d in drafts] == [H.document(d) for d in baseline.drafts]   # same drafts, same order
    assert [u.fingerprint for u in unresolved] == [u.fingerprint for u in baseline.unresolved]
    digest = lambda t: hashlib.sha256(b''.join(k.encode() + v for k, v in sorted(t.items()))).hexdigest()  # noqa: E731
    assert digest(again.tree()) == digest(baseline.tree())


def test_a_run_that_lost_its_state_replays_to_zero_drafts(tmp_path, sets, baseline):
    """Every payload is fetched again a month later and normalised again: the stamps move, the content does
    not, so nothing is written. This is the corpus-wide rewrite 07 S1.4 exists to prevent."""
    later = variant(sets['complete'], str(tmp_path / 'later'), date='Sat, 24 Oct 2026 15:22:26 GMT')
    r = baseline.fork(tmp_path / 'fork')
    r.state = H.new_state()
    before = r.tree()
    report, drafts, _ = r.run(later)
    assert report['payloads_fetched'] == len(SPACES) + 1
    assert drafts == [] and report['drafts'] == {'no-change': len(SPACES) + 1} and report['status'] == 'no-change'
    assert changed(before, r.tree()) == []


def test_the_failure_case_a_normalise_that_reads_the_clock_breaks_the_replay(tmp_path, sets, baseline, monkeypatch):
    """The replay check has teeth: a normalise() that leaks the run's time into the content rewrites
    every candidate, and the assertion run 2 relies on fails."""
    real = H.normalise
    tick = iter(range(10 ** 6))

    def leaky(payload, resolvers, xwalk):
        drafts, unresolved = real(payload, resolvers, xwalk)
        for d in drafts:
            d.payload['identity']['seen'] = next(tick)
        return drafts, unresolved
    monkeypatch.setattr(H, 'normalise', leaky)
    r = baseline.fork(tmp_path / 'fork')
    r.state = H.new_state()
    report, drafts, _ = r.run(sets['complete'], write=False)
    assert len(drafts) == len(SPACES) + 1 and report['drafts'] == {'field-change': len(SPACES) + 1}


def test_volatile_counters_moving_is_zero_drafts(tmp_path, sets, baseline):
    def bump(spaces):
        for s in spaces:
            s['likes'] += 7
            s['trendingScore'] = s.get('trendingScore', 0) + 3   # get-default: not every Space carries it
    r = baseline.fork(tmp_path / 'fork')
    report, drafts, _ = r.run(variant(sets['complete'], str(tmp_path / 'counters'), bump, 'W/"counters"'))
    assert report['http_codes'] == {'200': 1, '304': 1} and drafts == [] and report['status'] == 'no-change'


# ---- absences: only a complete enumeration may count one (07 S7.3) -----------------------------------------

def test_a_limited_run_counts_no_absence(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    report, _, _ = r.run(sets['deleted'], limit=10)
    assert report['status'] == 'partial' and report['complete'] is False
    assert r.state['absences'] == {} and report['absent'] == []


def test_a_run_that_meets_the_fixture_edge_counts_no_absence(tmp_path, baseline):
    """The uncut committed set links to a page it does not hold: that run has not seen every record."""
    edge = variant(FIX, str(tmp_path / 'edge'), delete, 'W/"edge"')
    r = baseline.fork(tmp_path / 'fork')
    report, _, _ = r.run(edge)
    assert report['complete'] is False and report['fixture_missing'] >= 1
    assert r.state['absences'] == {} and report['absent'] == []


def test_a_failed_run_counts_no_absence(tmp_path, sets, baseline):
    broken = variant(sets['complete'], str(tmp_path / 'broken'), lambda s: s.clear(), 'W/"empty"')
    r = baseline.fork(tmp_path / 'fork')
    report, drafts, _ = r.run(broken)
    assert report['status'] == 'hard-fail' and drafts == [] and r.state['absences'] == {}


def test_one_absence_then_listed_again_clears_the_count_and_writes_nothing(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    only_deleted = variant(sets['complete'], str(tmp_path / 'd'), delete, 'W/"d"')
    r.run(only_deleted)
    assert r.state['absences'] == {DELETED_KEY: 1}
    before = r.tree()
    _, drafts, _ = r.run(sets['complete'])
    assert r.state['absences'] == {} and drafts == [] and changed(before, r.tree()) == []
    assert 'last_seen' not in r.state['records'][DELETED_KEY]


def test_a_gone_record_listed_again_is_re_emitted_with_a_current_date(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    only_deleted = variant(sets['complete'], str(tmp_path / 'd'), delete, 'W/"d"')
    r.run(only_deleted)
    _, gone, _ = r.run(only_deleted)
    assert [d.change_class for d in gone] == ['gone']
    _, drafts, _ = r.run(sets['complete'])
    assert [(d.ingestion['source_record_id'], d.change_class) for d in drafts] == [(DELETED_KEY, 'field-change')]
    assert read(r.root, DELETED_KEY)['ingestion']['last_seen_upstream'] == '2026-09-24'   # the response's date
    assert r.state['absences'] == {}


def test_a_key_never_written_is_not_marked_gone(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    os.remove(os.path.join(r.root, rel(DELETED_KEY)))
    only_deleted = variant(sets['complete'], str(tmp_path / 'd'), delete, 'W/"d"')
    r.run(only_deleted)
    report, drafts, _ = r.run(only_deleted)
    assert report['gone'] == [DELETED_KEY] and drafts == []


# ---- a field-change keeps what is not the adapter's ----------------------------------------------------------

def test_a_field_change_keeps_a_curators_triage_and_the_discovery_date(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    path = os.path.join(r.root, rel(EDITED_KEY))
    doc = read(r.root, EDITED_KEY)
    doc = {'candidate_id': doc['candidate_id'], 'discovered_via': doc['discovered_via'],
           'discovered_at': '2026-09-01T00:00:00Z', 'triage': {'label': 'likely-benchmark', 'outcome': 'held'},
           **{k: v for k, v in doc.items() if k not in ('candidate_id', 'discovered_via', 'discovered_at')}}
    emit.write(doc, rel(EDITED_KEY), r.root, replace=True)
    _, drafts, _ = r.run(sets['edited'])
    assert [d.change_class for d in drafts] == ['field-change']
    after = read(r.root, EDITED_KEY)
    assert after['triage'] == {'label': 'likely-benchmark', 'outcome': 'held'}
    assert after['discovered_at'] == '2026-09-01T00:00:00Z'
    assert list(after)[:4] == ['candidate_id', 'discovered_via', 'discovered_at', 'triage']   # its place kept
    assert any(s.get('tag') == NEW_TAG for s in after['_suggested'])   # get-default: a dataset hint has no tag
    assert os.path.exists(path)


def test_an_unchanged_file_with_a_triage_block_is_still_no_change(tmp_path, sets, baseline):
    r = baseline.fork(tmp_path / 'fork')
    doc = dict(read(r.root, EDITED_KEY), triage={'label': 'unclear'})
    emit.write(doc, rel(EDITED_KEY), r.root, replace=True)
    r.state = H.new_state()
    report, drafts, _ = r.run(sets['complete'])
    assert drafts == [] and report['status'] == 'no-change'


# ---- the state file -----------------------------------------------------------------------------------------

def test_the_absence_counter_round_trips_through_the_state_file(tmp_path, matrix):
    path = str(tmp_path / 'state.json')
    H.save_state(path, matrix.state)
    back = H.load_state(path)
    assert back['absences'] == {DELETED_KEY: 3} and back['last_complete'] == matrix.state['last_complete']


def test_an_older_state_file_without_the_counter_still_loads(tmp_path):
    path = str(tmp_path / 'state.json')
    old = H.new_state()
    del old['absences'], old['last_complete']
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(old, f)
    back = H.load_state(path)
    assert back['absences'] == {} and back['last_complete'] is None
