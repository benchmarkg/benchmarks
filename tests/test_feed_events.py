"""Tests for tools/build/feed.py: every V8 event type, derived from a real git history built here.

The history is written commit by commit into tmp_path, so what is under test is the module's own
walk of `git log` and `git diff-tree` -- not a mock of it.
"""
import importlib.util
import os
import subprocess
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('feed', os.path.join(ROOT, 'tools', 'build', 'feed.py'))
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)

BENCH = 'data/benchmarks/code/demo-bench.yaml'
SOURCE = 'data/sources/2026/src-demo.yaml'

BENCH_V1 = """\
id: demo-bench
name: Demo Bench
description: A benchmark used only by this test.
domain:
  primary: code/repository-scale-se
  secondary: []
capability: [planning]
evaluation_method: [execution-tests]
designed_for_subjects: [agent-scaffold]
lifecycle: active
maintenance_status: actively-maintained
data:
  access: fully-open
  contamination_risk: medium
license: MIT
tags: [demo]
curation:
  added_on: 2026-01-02
"""

# Same record, cosmetically different: comments, key order, flow vs block style, quoting,
# a reworded description and a new tag. None of it is material.
BENCH_COSMETIC = """\
# a comment the feed must not see
id: "demo-bench"
name: Demo Bench
description: >
  A benchmark used only by this test, reworded.
tags:
  - demo
  - reworded
capability:
  - planning
evaluation_method: ["execution-tests"]
designed_for_subjects: [agent-scaffold]
domain: {primary: code/repository-scale-se, secondary: []}
data: {contamination_risk: medium, access: fully-open}
lifecycle: active
maintenance_status: actively-maintained
license: 'MIT'
curation:
  added_on: 2026-01-02
"""


def git(repo, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@example.invalid',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@example.invalid')
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout


def write(repo, path, text):
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(textwrap.dedent(text), encoding='utf-8')
    git(repo, 'add', path)


def commit(repo, msg, when):
    git(repo, 'commit', '-q', '-m', msg, when=when)


def replace(text, old, new):
    assert old in text, old
    return text.replace(old, new)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'repo'
    r.mkdir()
    git(r, 'init', '-q', '-b', 'main')
    git(r, 'config', 'commit.gpgsign', 'false')
    return r


def events(repo, kind=None):
    ev = feed.derive(str(repo))
    return [e for e in ev if kind is None or e['type'] == kind]


def test_benchmark_added_is_dated_by_the_record_not_the_commit(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add demo-bench', '2026-03-01T10:00:00Z')
    [e] = events(repo)
    assert (e['type'], e['entity'], e['family']) == ('benchmark-added', 'demo-bench', 'code')
    assert (e['date'], e['date_basis']) == ('2026-01-02T00:00:00Z', 'curation.added_on')
    assert e['published_on'] == '2026-03-01T10:00:00Z'


def test_a_cosmetic_diff_produces_no_material_update_event(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, BENCH, BENCH_COSMETIC)
    commit(repo, 'reformat and reword', '2026-03-02T10:00:00Z')
    assert [e['type'] for e in events(repo)] == ['benchmark-added']


@pytest.mark.parametrize('old, new, field', [
    ('capability: [planning]', 'capability: [planning, tool-use]', 'capability'),
    ('  access: fully-open', '  access: gated-registration', 'data.access'),
    ('license: MIT', 'license: Apache-2.0', 'license'),
    ('tags: [demo]', 'tags: [demo]\nversions: [{id: v2}]', 'versions'),
    ('  contamination_risk: medium', '  contamination_risk: high', 'data.contamination_risk'),
])
def test_a_material_diff_produces_one_material_update_event(repo, old, new, field):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, BENCH, replace(BENCH_V1, old, new))
    commit(repo, 'update', '2026-03-02T10:00:00Z')
    [e] = events(repo, 'benchmark-updated-material')
    assert e['fields'] == [field]


def test_lifecycle_change_is_reported_once_not_twice(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, BENCH, replace(BENCH_V1, 'lifecycle: active', 'lifecycle: superseded'))
    commit(repo, 'superseded by v2', '2026-03-02T10:00:00Z')
    [e] = events(repo, 'lifecycle-change')
    assert (e['before'], e['after']) == ('active', 'superseded')
    assert events(repo, 'benchmark-updated-material') == []


def test_deprecation_detected_when_maintenance_crosses_into_stale(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    stale = replace(BENCH_V1, 'maintenance_status: actively-maintained',
                    'maintenance_status: stale\nliveness: {last_checked: 2026-04-10}')
    write(repo, BENCH, stale)
    commit(repo, 'probe verdict', '2026-04-12T03:31:00Z')
    [e] = events(repo, 'deprecation-detected')
    assert (e['before'], e['after'], e['date']) == ('actively-maintained', 'stale', '2026-04-10T00:00:00Z')
    write(repo, BENCH, replace(stale, 'maintenance_status: stale', 'maintenance_status: abandoned'))
    commit(repo, 'probe verdict', '2026-05-12T03:31:00Z')
    assert len(events(repo, 'deprecation-detected')) == 1  # stale -> abandoned crossed nothing new


def test_claim_added_and_machine_ingested_flag(repo):
    write(repo, 'data/claims/demo-bench/claim-aaaa.yaml', """\
        id: claim-aaaa
        benchmark: demo-bench
        date_reported: 2025-11-20
        """)
    write(repo, 'data/claims/_ingested/epoch/demo-bench/claim-bbbb.yaml', """\
        id: claim-bbbb
        benchmark: demo-bench
        date_reported: 2025-12-01
        """)
    commit(repo, 'claims', '2026-03-01T10:00:00Z')
    by_id = {e['entity']: e for e in events(repo, 'claim-added')}
    assert by_id['claim-aaaa']['machine_ingested'] is False
    assert by_id['claim-bbbb']['machine_ingested'] is True
    assert by_id['claim-aaaa']['date'] == '2025-11-20T00:00:00Z'  # its own date, not the ingest commit


def test_correction_needs_the_tag_and_a_previously_published_value(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    # A fix: that only fills in a null is not a correction ...
    write(repo, BENCH, replace(BENCH_V1, 'tags: [demo]', 'tags: [demo]\nhomepage: https://example.invalid'))
    commit(repo, 'fix: add the homepage', '2026-03-02T10:00:00Z')
    assert events(repo, 'correction') == []
    # ... an untagged change to a published value is not one either ...
    v3 = replace(BENCH_V1, 'tags: [demo]', 'tags: [demo]\nhomepage: https://example.invalid')
    write(repo, BENCH, replace(v3, 'name: Demo Bench', 'name: Demo-Bench'))
    commit(repo, 'rename display name', '2026-03-03T10:00:00Z')
    assert events(repo, 'correction') == []
    # ... and a fix: that changes one is.
    v4 = replace(replace(v3, 'name: Demo Bench', 'name: Demo-Bench'), 'license: MIT', 'license: Apache-2.0')
    write(repo, BENCH, v4)
    commit(repo, 'fix(demo-bench): licence was misread from the repo', '2026-03-04T10:00:00Z')
    [e] = events(repo, 'correction')
    assert e['changes'] == [{'field': 'license', 'before': 'MIT', 'after': 'Apache-2.0'}]


def test_a_correction_trailer_counts_as_the_tag(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, BENCH, replace(BENCH_V1, '  contamination_risk: medium', '  contamination_risk: high'))
    commit(repo, 'contamination evidence\n\nCorrection: reported by a maintainer', '2026-03-02T10:00:00Z')
    [e] = events(repo, 'correction')
    assert e['changes'][0]['field'] == 'data.contamination_risk'


def test_source_rot_detected(repo):
    write(repo, SOURCE, 'id: src-demo\nurl: https://example.invalid/x\nlink_status: live\n')
    commit(repo, 'add source', '2026-03-01T10:00:00Z')
    write(repo, SOURCE, 'id: src-demo\nurl: https://example.invalid/x\nlink_status: dead\n'
                        'link_checked_at: 2026-06-01T08:07:00Z\n')
    commit(repo, 'linkrot sweep', '2026-06-02T08:07:00Z')
    [e] = events(repo, 'source-rot-detected')
    assert (e['entity'], e['date'], e['date_basis']) == ('src-demo', '2026-06-01T08:07:00Z', 'link_checked_at')


def test_a_rename_is_not_an_addition(repo):
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    (repo / 'data/benchmarks/agents-tooluse').mkdir(parents=True)  # git mv needs the target directory
    git(repo, 'mv', BENCH, 'data/benchmarks/agents-tooluse/demo-bench.yaml')
    commit(repo, 'move family', '2026-03-02T10:00:00Z')
    assert [e['type'] for e in events(repo)] == ['benchmark-added']


def test_events_sort_on_their_own_date_not_on_commit_order(repo):
    write(repo, 'data/claims/demo-bench/claim-new.yaml', 'id: claim-new\ndate_reported: 2026-02-01\n')
    commit(repo, 'first commit', '2026-03-01T10:00:00Z')
    write(repo, 'data/claims/demo-bench/claim-old.yaml', 'id: claim-old\ndate_reported: 2024-05-05\n')
    commit(repo, 'later commit, older claim', '2026-03-05T10:00:00Z')
    assert [e['entity'] for e in events(repo)] == ['claim-new', 'claim-old']


def test_only_mains_first_parent_line_publishes(repo):
    write(repo, 'README', 'x\n')
    commit(repo, 'root', '2026-03-01T10:00:00Z')
    git(repo, 'checkout', '-q', '-b', 'topic')
    write(repo, BENCH, BENCH_V1)
    commit(repo, 'add on a branch', '2026-03-02T10:00:00Z')
    write(repo, BENCH, replace(BENCH_V1, 'license: MIT', 'license: BSD-3-Clause'))
    commit(repo, 'amend on the branch', '2026-03-03T10:00:00Z')
    git(repo, 'checkout', '-q', 'main')
    git(repo, 'merge', '-q', '--no-ff', '-m', 'merge topic', 'topic', when='2026-03-04T10:00:00Z')
    ev = events(repo)
    assert [e['type'] for e in ev] == ['benchmark-added']  # the branch's intermediate edit never published
    assert ev[0]['published_on'] == '2026-03-04T10:00:00Z'


def test_all_seven_event_types_are_covered():
    names = {n for n in globals() if n.startswith('test_')}
    assert len(feed.EVENT_TYPES) == 7
    for kind in ('benchmark_added', 'material_update', 'claim_added', 'correction', 'lifecycle_change',
                 'deprecation_detected', 'source_rot_detected'):
        assert any(kind in n for n in names), kind


def test_events_carry_families_and_organisations_for_the_feeds(repo):
    write(repo, BENCH, replace(BENCH_V1, 'license: MIT', 'license: MIT\ngovernance: {maintainers: [org-demo-lab]}'))
    write(repo, 'data/claims/demo-bench/claim-cccc.yaml',
          'id: claim-cccc\nbenchmark: demo-bench@v1\nreported_by: org-some-lab\ndate_reported: 2026-02-01\n')
    write(repo, SOURCE, 'id: src-demo\ncited_by: [demo-bench]\nlink_status: live\n')
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, SOURCE, 'id: src-demo\ncited_by: [demo-bench]\nlink_status: dead\n')
    commit(repo, 'rot', '2026-03-02T10:00:00Z')
    by_type = {e['type']: e for e in events(repo)}
    assert by_type['benchmark-added']['families'] == ['code']
    assert by_type['benchmark-added']['organisations'] == ['org-demo-lab']
    assert (by_type['claim-added']['families'], by_type['claim-added']['organisations']) == (['code'], ['org-some-lab'])
    assert by_type['source-rot-detected']['families'] == ['code']


def test_an_unverified_or_deleted_entity_is_not_publishable(repo):
    write(repo, BENCH, BENCH_V1 + '  verification_status: ai-drafted-unverified\n')
    write(repo, 'data/claims/demo-bench/claim-dddd.yaml', 'id: claim-dddd\ndate_reported: 2026-02-01\n')
    commit(repo, 'drafts', '2026-03-01T10:00:00Z')
    by_type = {e['type']: e for e in events(repo)}
    assert by_type['benchmark-added']['publishable'] is False  # still a draft at HEAD
    assert by_type['claim-added']['publishable'] is True
    write(repo, BENCH, BENCH_V1 + '  verification_status: primary-source-verified\n')
    git(repo, 'rm', '-q', 'data/claims/demo-bench/claim-dddd.yaml')
    commit(repo, 'verified; claim withdrawn', '2026-03-02T10:00:00Z')
    by_type = {e['type']: e for e in events(repo)}
    assert by_type['benchmark-added']['publishable'] is True  # verification publishes its history
    assert by_type['claim-added']['publishable'] is False     # gone at HEAD


def test_a_correction_on_a_benchmark_is_filed_under_its_family(repo):
    v1 = replace(BENCH_V1, 'license: MIT', 'license: MIT\ngovernance: {maintainers: [org-demo-lab]}')
    write(repo, BENCH, v1)
    commit(repo, 'add', '2026-03-01T10:00:00Z')
    write(repo, BENCH, replace(v1, 'license: MIT', 'license: Apache-2.0'))
    commit(repo, 'fix: licence', '2026-03-02T10:00:00Z')
    [e] = events(repo, 'correction')
    assert (e['families'], e['organisations']) == (['code'], ['org-demo-lab'])
