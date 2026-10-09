"""The schema-drift hard-fail contract (P5-S4-T05; 07 S9.2, 06 S3.2).

The verify: `pytest tests/ingest/test_zero_row_drift.py`. Done when "A filter that previously returned
dozens returning zero hard-fails and opens an issue instead of committing an empty run". Asserted through
the shared runner on hf-hub, over synthetic recorded listings: a 30-Space run, then the same filter
answering an empty array. The other three rules sit beside it: the declared structure, drift found before
any candidate is handed out (so nothing is committed), and a renamed tag namespace stopping the run rather
than falling back to free-text matching.
"""
import io
import json
import os
import zipfile
from datetime import datetime, timezone

import pytest

from ingest import gates
from ingest.adapters import epoch, hf_hub
from ingest.adapters.base import Candidate, Payload
from ingest.gates import drift
from ingest.http.fixture import FixtureTransport
from ingest.runner import report as R
from ingest.runner import state as S

SPACES, DATASETS = hf_hub.LISTINGS[0].url, hf_hub.LISTINGS[1].url
WHEN = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)


def write(directory, name, url, body, etag):
    with open(os.path.join(directory, name), 'w', encoding='utf-8') as f:
        json.dump(body, f)
    with open(os.path.join(directory, name + '.headers.json'), 'w', encoding='utf-8') as f:
        json.dump({'url': url, 'status': 200, 'headers': [['Content-Type', 'application/json'],
                                                          ['Date', 'Fri, 09 Oct 2026 06:00:00 GMT'], ['ETag', etag]]}, f)


def space(i, tags=('leaderboard', 'test:public')):
    return {'id': 'org/board-%d' % i, 'tags': list(tags), 'likes': 1, 'createdAt': '2026-01-01T00:00:00.000Z'}


def dataset(i):
    return {'id': 'org/set-%d' % i, 'tags': ['benchmark:official'], 'gated': False, 'disabled': False,
            'downloads': 1, 'likes': 1, 'lastModified': '2026-01-01T00:00:00.000Z'}


def fixture(tmp_path, name, spaces, datasets):
    d = tmp_path / name
    d.mkdir()
    write(str(d), 'spaces.json', SPACES, spaces, 'W/"s-%s"' % name)
    write(str(d), 'datasets.json', DATASETS, datasets, 'W/"d-%s"' % name)
    return str(d)


class Run:
    """The shared runner over hf-hub, a state file, a run log and a sink that records what it was handed."""

    def __init__(self, tmp_path):
        self.tmp, self.path = tmp_path, str(tmp_path / 'hf-hub.json')
        self.cache = hf_hub.RequestCache(str(tmp_path / 'cache'))
        self.sunk = []

    def __call__(self, fix):
        a = hf_hub.HfHub(FixtureTransport(fix), self.cache, now=lambda: WHEN)
        return S.run(a, hf_hub.load_state(self.path), self.path, resolver={}, now=lambda: WHEN,
                     sink=lambda d, u: self.sunk.append(len(d)), log_root=str(self.tmp))

    def state(self):
        with open(self.path, encoding='utf-8') as f:
            return json.load(f)


# ---- the done_when -------------------------------------------------------------------------------------------

def test_a_filter_that_returned_dozens_returning_zero_hard_fails_and_opens_an_issue(tmp_path):
    run = Run(tmp_path)
    first = run(fixture(tmp_path, 'dozens', [space(i) for i in range(30)], [dataset(1)]))
    assert first['status'] == 'ok' and run.state()['urls'][SPACES]['rows'] == 30
    before, sunk_before = run.state(), list(run.sunk)
    second = run(fixture(tmp_path, 'empty', [], [dataset(1)]))
    assert second['status'] == 'hard-fail' and second['alerts'] == ['adapter-broken']
    assert 'returned zero rows; it previously returned 30' in second['errors'][0]
    assert second['issue']['labels'] == ['adapter-broken', 'source:hf-hub']
    assert 'previously returned 30' in second['issue']['body'] and 'committed nothing' in second['issue']['body']
    # an empty run is not committed: nothing reached the sink, and the state differs only in the failure count
    assert run.sunk == sunk_before
    after = run.state()
    assert after['consecutive_failures'] == 1
    assert {k: v for k, v in after.items() if k not in ('last_run', 'consecutive_failures')} == \
           {k: v for k, v in before.items() if k not in ('last_run', 'consecutive_failures')}
    # and the committed run log records the failure
    assert R.history('hf-hub', str(tmp_path))[-1].status == 'hard-fail'


def test_a_drifted_listing_stops_the_run_before_a_single_candidate_is_handed_out(tmp_path):
    """The datasets listing is read after the Spaces one. Were candidates handed out as each listing
    arrived, a thousand Spaces could be processed -- and checkpointed -- before the datasets listing showed
    its drift. Every listing is checked first, so the drifted run yields nothing at all."""
    run = Run(tmp_path)
    run(fixture(tmp_path, 'dozens', [space(i) for i in range(30)], [dataset(i) for i in range(12)]))
    a = hf_hub.HfHub(FixtureTransport(fixture(tmp_path, 'nodatasets', [space(i) for i in range(30)], [])),
                     run.cache, now=lambda: WHEN)
    handed = []
    with pytest.raises(drift.DriftError, match='datasets-benchmark-official returned zero rows; it previously '
                                                'returned 12'):
        for c in a.discover(hf_hub.load_state(run.path)):
            handed.append(c)
    assert handed == []


# ---- rule 1: the declared structure ------------------------------------------------------------------------------

def test_rows_passes_records_that_meet_the_declaration():
    e = drift.Expect('listing', frozenset({'id', 'tags'}), min_rows=2)
    recs = [{'id': 'a', 'tags': []}, {'id': 'b', 'tags': [], 'extra': 1}]
    assert drift.rows(e, recs, previous=40) is recs


@pytest.mark.parametrize('records, previous, why', [
    ({'id': 'a'}, None, 'expected a list'),
    ([], 12, 'previously returned 12'),
    ([{'id': 'a'}], None, 'at least 2'),
    ([{'id': 'a', 'tags': []}, {'id': 'b'}], None, "record b lacks \\['tags'\\]"),
])
def test_rows_refuses_what_does_not(records, previous, why):
    with pytest.raises(drift.DriftError, match=why):
        drift.rows(drift.Expect('listing', frozenset({'id', 'tags'}), min_rows=2), records, previous)


def test_zero_rows_is_drift_only_against_history_or_a_declared_minimum():
    open_ended = drift.Expect('maybe-empty', min_rows=0)
    assert drift.rows(open_ended, [], previous=None) == []         # a filter never productive may be empty
    assert drift.rows(open_ended, [], previous=0) == []
    with pytest.raises(drift.DriftError, match='previously returned 3'):
        drift.rows(open_ended, [], previous=3)                     # rule 2, with no declared minimum at all


def test_drift_is_a_gate_error_named_schema_drift():
    e = drift.DriftError('x')
    assert isinstance(e, gates.GateError) and e.gate == 'schema-drift' and e.message == 'x'
    assert hf_hub.SchemaDrift is drift.DriftError and epoch.SchemaDrift is drift.DriftError


# ---- rule 4: no fallback to free-text matching ------------------------------------------------------------------

def test_a_vanished_namespace_is_a_rename_and_stops_the_run():
    with pytest.raises(drift.DriftError, match='test carried 12 tags last run and none now'):
        drift.namespaces(drift.namespace_counts([['leaderboard'], ['testing:public']], {'test', 'judge'}),
                         {'test': 12, 'judge': 3}, 'spaces')
    drift.namespaces(drift.Counter({'test': 1}), {'test': 12}, 'spaces')        # fewer is not gone
    drift.namespaces(drift.Counter(), {'judge': drift.RENAME_MIN - 1}, 'spaces')  # too few to read as a rename
    drift.namespaces(drift.Counter({'test': 4}), None, 'spaces')                # a first run compares nothing


def test_hf_hub_stops_when_a_tag_namespace_is_renamed(tmp_path):
    run = Run(tmp_path)
    run(fixture(tmp_path, 'tagged', [space(i) for i in range(30)], [dataset(1)]))
    assert run.state()['namespace_counts']['spaces-leaderboard']['test'] == 30
    renamed = [space(i, tags=('leaderboard', 'testing:public')) for i in range(30)]
    out = run(fixture(tmp_path, 'renamed', renamed, [dataset(1)]))
    assert out['status'] == 'hard-fail' and out['alerts'] == ['adapter-broken']
    assert 'test carried 30 tags last run and none now' in out['errors'][0]


def test_an_undeclared_namespace_tag_is_never_matched_as_free_text():
    """What the stop protects: a tag in a namespace the crosswalk does not declare is an Unresolved, never a
    hint guessed from its words -- so a renamed namespace would otherwise vanish into that pile silently."""
    rec = space(1, tags=('leaderboard', 'testing:public'))
    c = Candidate('space:' + rec['id'], 'leaderboard', 'https://huggingface.co/spaces/' + rec['id'], {})
    p = Payload(c, b'', 'application/json', 200, WHEN, None, None, hf_hub.sha256_normalised(rec), False, doc=rec)
    [d], u = hf_hub.normalise(p, {}, hf_hub.load_crosswalk())
    assert not any(s.get('tag') == 'testing:public' for s in d.payload['_suggested'])   # get-default: hints without a tag
    assert [(x.reason, x.observed) for x in u if x.field == 'tags'] == [('out-of-band', 'testing:public')]


# ---- Epoch: a changed ZIP structure -------------------------------------------------------------------------------

def bundle(**files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, text in files.items():
            z.writestr(name.replace('__', '.'), text)
    return epoch.ZipBundle(buf.getvalue())


META = {'benchmark_metadata__csv': 'benchmark,source_file,score_column,scale\nX,x.csv,score,1\n',
        'model_metadata__csv': 'model_version,model_group\nm,M\n'}


@pytest.mark.parametrize('files, why', [
    (dict(META), 'no per-benchmark CSV'),
    (dict(META, benchmark_metadata__csv='benchmark,source_file,score_column,scale\n', x__csv='a\n1\n'),
     'returned 0 rows'),
])
def test_epoch_a_changed_bundle_structure_is_drift_with_an_issue(files, why):
    report = epoch.run(bundle(**files))
    assert report['status'] == 'hard-fail' and why in report['errors'][0]
    assert report['issue']['labels'] == ['adapter-broken', 'source:epoch']


def test_epoch_a_well_formed_bundle_passes():
    epoch.check_drift(bundle(**dict(META, x__csv='Model version,Score\nm,0.5\n')))


def test_the_issue_says_what_broke_and_that_nothing_was_committed():
    i = drift.issue('arxiv-oai', 'oai listing returned zero rows; it previously returned 140', '2026-10-09T06:00:00Z')
    assert i['title'] == 'adapter-broken: arxiv-oai -- schema drift'
    assert 'previously returned 140' in i['body'] and 'committed nothing' in i['body']
    assert '2026-10-09T06:00:00Z' in i['body']
