"""The deliberately broken adapter drill (P5-S6-T04; 07 S9.2, 14 Phase 5 exit criterion 4).

14-roadmap.md's Phase 5 exit: "A deliberately broken adapter (rename the SWE-bench script tag in a fixture)
hard-fails and opens an issue rather than silently writing nulls." 07 S9.2 names the very case: "200 OK but
<script id="leaderboard-data"> is gone from swebench.com -- Hard fail immediately. Open an adapter-broken issue."

tests/ingest/fixtures/swebench/renamed-script-tag.html is the SWE-bench fixture page with one change, the tag's id
renamed to "leaderboard-data-v2" -- the edit a site redesign makes. The page is served as https://www.swebench.com/
with a 200 and the real fixture's headers, and the adapter runs on it the way a scheduled job does: through the
shared runner (ingest/runner/state.py), with a sink that writes every draft it is handed as YAML into a data tree,
and with the run log on. The same run on the intact page is the control: there the sink writes files, so a sink
that writes none on the broken page is the adapter refusing, not a sink that never writes.

Asserted: a hard fail; the adapter-broken issue, opened once and naming the tag; zero YAML written, and nothing
handed to the sink at all, so no null-filled record reaches any branch; nothing the run fetched kept in the state
file, only the failure counted; and the run log recording the failure. ingest-lint.yml runs this file in CI.
"""
from __future__ import annotations

import json
import os
import re
import shutil

import pytest

from ingest import emit, gates
from ingest.adapters import swebench as S
from ingest.http.fixture import FixtureTransport
from ingest.runner import report as R
from ingest.runner import state as ST

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, 'tests', 'ingest', 'fixtures', 'swebench')
BROKEN = os.path.join(FIX, 'renamed-script-tag.html')
WORKFLOW = os.path.join(ROOT, '.github', 'workflows', 'ingest-lint.yml')


def _now():
    from datetime import datetime, timezone
    return datetime(2026, 10, 9, 20, 5, tzinfo=timezone.utc)


class Anything:
    """A resolver that resolves every reference, so the control run drafts every row it can."""

    class Hit:
        def __init__(self, entity):
            self.entity, self.version, self.score = entity, None, 1.0

    def __init__(self, kind):
        self.kind = kind

    def resolve(self, raw):
        slug = re.sub(r'[^a-z0-9]+', '-', raw.lower()).strip('-')
        return self.Hit('%s:%s%s' % (self.kind, 'org-' if self.kind == 'organization' else '', slug))


RESOLVERS = {k: Anything(k) for k in ('system', 'organization', 'benchmark', 'metric')}


def served(tmp_path, page: str):
    """A fixture directory serving `page` as https://www.swebench.com/, with the real fixture's headers."""
    d = tmp_path / 'served'
    d.mkdir()
    shutil.copy(page, d / 'page.html')
    shutil.copy(os.path.join(FIX, 'page.html.headers.json'), d / 'page.html.headers.json')
    return str(d)


class YamlSink:
    """The writer a scheduled run hands its drafts to: each one becomes a YAML file under `root`/data/."""

    def __init__(self, root):
        self.root, self.calls, self.written = root, [], []

    def __call__(self, drafts, unresolved):
        self.calls.append((len(drafts), len(unresolved)))
        for i, d in enumerate(drafts):
            rel = (d.path / ('claim-%06d.yaml' % (len(self.written) + i))).as_posix()
            out = os.path.join(self.root, *rel.split('/'))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'w', encoding='utf-8', newline='\n') as f:
                f.write(emit.emit(gates.document(d), rel))
        self.written += [None] * len(drafts)


def scheduled_run(tmp_path, page):
    sink = YamlSink(str(tmp_path / 'tree'))
    path = str(tmp_path / 'state' / 'swe-bench.json')
    os.makedirs(os.path.dirname(path))
    adapter = S.SweBench(FixtureTransport(served(tmp_path, page)), now=_now)
    report = ST.run(adapter, ST.load(path, ST.new(adapter.name, adapter.version)), path, resolver=RESOLVERS,
                    sink=sink, now=_now, log_root=str(tmp_path / 'tree'))
    return report, sink, path


def yaml_files(root):
    return sorted(os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/')
                  for d, _, fs in os.walk(root) for f in fs if f.endswith('.yaml'))


# ---- the fixture ------------------------------------------------------------------------------------------------

def test_the_broken_page_is_the_fixture_with_only_the_tag_renamed():
    with open(os.path.join(FIX, 'page.html'), 'rb') as f:
        intact = f.read()
    with open(BROKEN, 'rb') as f:
        broken = f.read()
    assert intact.count(b'id="leaderboard-data"') == 1
    assert broken == intact.replace(b'id="leaderboard-data"', b'id="leaderboard-data-v2"')
    assert b'id="leaderboard-data"' not in broken and b'leaderboard-data-v2' in broken


# ---- the control: the intact page writes -------------------------------------------------------------------------

def test_the_control_run_on_the_intact_page_writes_yaml(tmp_path):
    report, sink, _ = scheduled_run(tmp_path, os.path.join(FIX, 'page.html'))
    assert report['status'] == 'ok' and report['drafts'] > 0 and report['open_pr'] is True
    assert len(yaml_files(str(tmp_path / 'tree' / 'data'))) == report['drafts']


# ---- the drill -----------------------------------------------------------------------------------------------------

@pytest.fixture
def drill(tmp_path):
    return (*scheduled_run(tmp_path, BROKEN), tmp_path)


def test_the_renamed_tag_is_a_hard_fail_that_opens_adapter_broken(drill):
    report, _, _, _ = drill
    assert report['status'] == 'hard-fail' and report['open_pr'] is False
    assert report['errors'] == ['DriftError: schema-drift: https://www.swebench.com/: no <script id="leaderboard-data"> '
                                'in the page (282736 bytes)']
    assert report['alerts'] == ['adapter-broken']
    issue = report['issue']
    assert issue['title'] == 'adapter-broken: swe-bench -- schema drift'
    assert issue['labels'] == ['adapter-broken', 'source:swe-bench']
    assert 'leaderboard-data' in issue['body'] and 'committed nothing' in issue['body']


def test_no_yaml_is_written_and_nothing_reaches_the_sink(drill):
    report, sink, _, tmp_path = drill
    assert sink.calls == [] and sink.written == []
    assert yaml_files(str(tmp_path / 'tree' / 'data')) == []
    assert report['drafts'] == 0 and report['unresolved'] == 0 and report['candidates_seen'] == 0


def test_the_state_keeps_nothing_the_run_fetched_only_the_failure(drill):
    report, _, path, _ = drill
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    assert state['consecutive_failures'] == 1 and state['last_success'] is None
    assert state.get('sha256') is None and state.get('counts') is None and state['urls'] == {}   # get-default: absent is kept nothing
    assert state['checkpoint'] is None


def test_the_run_log_records_the_failure(drill):
    report, _, _, tmp_path = drill
    runs = R.history('swe-bench', str(tmp_path / 'tree'))
    assert [r.status for r in runs] == ['hard-fail'] and report['log']
    assert R.last_worked('swe-bench', str(tmp_path / 'tree')) is None


def test_the_adapters_own_dry_run_fails_the_same_way(tmp_path):
    report = S.run(S.SweBench(FixtureTransport(served(tmp_path, BROKEN)), now=_now), S.new_state(), RESOLVERS)
    assert report['status'] == 'hard-fail' and report['documents'] == [] and report['held'] == 0
    assert report['issue']['labels'] == ['adapter-broken', 'source:swe-bench']


def test_ci_runs_the_drill():
    with open(WORKFLOW, encoding='utf-8') as f:
        text = f.read()
    assert 'tests/ingest/test_breakage_swebench.py' in text
