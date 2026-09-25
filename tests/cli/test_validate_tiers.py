"""Tests for `bench validate` (P0-S5-T02; tools/validate/tiers.py, tools/cli.py; 04 S12, 05 S3).

The verify: "`bench validate --tier all --json` exits 0 over the committed corpus, and `pytest
tests/cli/test_validate_tiers.py` asserts each of tiers 1 to 3 fails its own fixture, tier 4 never
changes the exit code, and --single loads no corpus".

The fixtures are directory trees under fixtures/validate/: `base/` is a small corpus clean at every
tier, and each `tierN/` holds the one file that replaces base's benchmark with a record failing tier
N and only tier N. A case is base copied into tmp_path with the overlay copied over it.
"""
import datetime
import json
import os
import shutil
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli  # noqa: E402
from tools.validate import tiers  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'validate')
TODAY = datetime.date(2026, 9, 25)
BENCH = 'data/benchmarks/code/example-bench.yaml'
runner = CliRunner()


def tree(tmp_path, overlay=None):
    shutil.copytree(os.path.join(FIXTURES, 'base'), tmp_path, dirs_exist_ok=True)
    if overlay:
        shutil.copytree(os.path.join(FIXTURES, overlay), tmp_path, dirs_exist_ok=True)
    return str(tmp_path)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def by_tier(report):
    out = {t: [] for t in tiers.TIERS}
    for f in report.findings:
        out[f.tier].append(f)
    return out


# ---- the verify ---------------------------------------------------------------------------------

def test_the_base_fixture_is_clean_at_every_tier(tmp_path):
    r = tiers.run(tree(tmp_path), today=TODAY)
    assert r.findings == [] and r.exit_code == 0


@pytest.mark.parametrize('tier', [1, 2, 3])
def test_each_blocking_tier_fails_its_own_fixture_and_only_its_own(tmp_path, tier):
    r = tiers.run(tree(tmp_path, 'tier%d' % tier), today=TODAY)
    found = by_tier(r)
    assert found[tier] and all(f.blocks for f in found[tier]), found[tier]
    assert [f for t in (1, 2, 3) if t != tier for f in found[t]] == []
    assert r.exit_code == 1
    # and the tier selected on its own still fails it, while the other blocking tiers pass it
    assert tiers.run(tree(tmp_path, 'tier%d' % tier), tiers.TIERS[tier], today=TODAY).exit_code == 1
    for other in {1, 2, 3} - {tier}:
        assert tiers.run(str(tmp_path), tiers.TIERS[other], today=TODAY).exit_code == 0


@pytest.mark.parametrize('overlay', [None, 'tier1', 'tier2', 'tier3', 'tier4'])
def test_tier_4_never_changes_the_exit_code(tmp_path, overlay):
    root = tree(tmp_path, overlay)
    with_quality = tiers.run(root, 'all', today=TODAY)
    without = tiers.run(root, ['schema', 'ref', 'semantic'], today=TODAY)
    assert with_quality.exit_code == without.exit_code
    assert tiers.run(root, 'quality', today=TODAY).exit_code == 0


def test_the_tier_4_fixture_reports_signals_and_exits_zero(tmp_path):
    r = tiers.run(tree(tmp_path, 'tier4'), today=TODAY)
    assert {f.rule for f in r.findings} == {'tagline-length', 'last-verified-stale'}
    assert all(f.tier == 4 and f.severity == 'quality' and not f.blocks for f in r.findings)
    assert r.exit_code == 0
    result = runner.invoke(cli.app, ['validate', '--single', '--json', os.path.join(str(tmp_path), BENCH)])
    assert result.exit_code == 0 and json.loads(result.stdout)['quality'] == 2


def test_a_quality_finding_cannot_block_even_if_mislabelled():
    f = tiers.Finding(4, 'tagline-length', 'blocking', 'x', None, 'a tier-4 finding someone marked blocking')
    assert not f.blocks
    assert tiers.Report((1, 2, 3, 4), 'all', 1, [f]).exit_code == 0


@pytest.fixture
def no_corpus(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('--single loaded the corpus')
    monkeypatch.setattr(tiers, 'discover', refuse)
    monkeypatch.setattr(tiers, 'load', refuse)
    monkeypatch.setattr(tiers, 'index', refuse)


@pytest.mark.parametrize('overlay, code', [(None, 0), ('tier1', 1), ('tier3', 1), ('tier4', 0)])
def test_single_answers_without_loading_a_corpus(tmp_path, no_corpus, overlay, code):
    path = os.path.join(tree(tmp_path, overlay), BENCH)
    result = runner.invoke(cli.app, ['validate', '--single', '--json', path])
    assert result.exit_code == code, result.stdout
    report = json.loads(result.stdout)
    assert report['scope'] == 'single' and report['files'] == 1
    assert report['not_checked'], 'what --single could not check is listed, not silently passed'


def test_the_no_corpus_guard_is_real(tmp_path, no_corpus):
    with pytest.raises(AssertionError, match='loaded the corpus'):
        tiers.run(tree(tmp_path))


def test_single_does_not_see_a_dangling_reference_and_says_so(tmp_path, no_corpus):
    """Tier 2's cross-record check needs the corpus; --single reports it as not checked."""
    r = tiers.single(os.path.join(tree(tmp_path, 'tier2'), BENCH), today=TODAY)
    assert r.exit_code == 0 and any('tier 2' in n for n in r.not_checked)


def test_single_still_checks_taxonomy_references(tmp_path, no_corpus):
    root = tree(tmp_path)
    p = os.path.join(root, BENCH)
    text = open(p, encoding='utf-8').read().replace('  primary: code/repository-scale-se',
                                                     '  primary: code/repository-scale-se\n  secondary: [code]')
    write(root, BENCH, text)
    r = tiers.single(p, today=TODAY)
    assert any(f.tier == 2 and f.rule == 'taxonomy-ref' and 'navigational' in f.message for f in r.findings)


def test_the_committed_corpus_runs_every_tier_and_emits_json():
    result = runner.invoke(cli.app, ['validate', '--tier', 'all', '--json'])
    report = json.loads(result.stdout)
    assert report['tiers'] == ['schema', 'ref', 'semantic', 'quality']
    assert result.exit_code == report['exit_code']
    assert report['files'] >= 39
    assert 'data/surveys/engineering-design/_family-scoping.yaml' in report['unmodelled']
    for f in report['findings']:
        assert set(f) == {'tier', 'tier_name', 'rule', 'severity', 'entity', 'path', 'message', 'auto_fix', 'related'}


@pytest.mark.xfail(strict=True, reason='P0-S3-T04 is blocked: 23 non-DOI sources have no archive_url and 4 more '
                   'fail their extract checks; RoboArena lacks comparability.rating_pool_required. Remove this '
                   'mark when the corpus is clean -- strict, so a clean corpus fails here until it is.')
def test_the_committed_corpus_exits_zero():
    result = runner.invoke(cli.app, ['validate', '--tier', 'all', '--json'])
    assert result.exit_code == 0, [f['entity'] + ': ' + f['rule'] for f in json.loads(result.stdout)['findings']
                                   if f['severity'] == 'blocking']


def test_every_committed_corpus_blocker_is_a_known_one():
    """Until the xfail above is lifted: nothing blocks the committed corpus except P0-S3-T04's draft
    sources and RoboArena's missing rating_pool_required. A new blocker fails here."""
    r = tiers.run(ROOT)
    for f in r.blocking:
        known = (f.path or '').startswith('data/sources/') and f.rule in ('schema', 'non-doi-archive') \
            or (f.entity, f.rule) == ('roboarena', 'rating-pool-required')
        assert known, str(f)
    assert by_tier(r)[2] == []                            # every reference in the corpus resolves


# ---- tier 1 -------------------------------------------------------------------------------------

def test_a_file_named_for_another_id_fails_tier_1(tmp_path):
    root = tree(tmp_path)
    shutil.move(os.path.join(root, BENCH), os.path.join(root, 'data/benchmarks/code/other.yaml'))
    r = tiers.run(root, 'schema', today=TODAY)
    assert [f.rule for f in r.findings] == ['file-name'] and 'holds id example-bench' in r.findings[0].message


def test_a_benchmark_outside_its_family_directory_fails_tier_1(tmp_path):
    root = tree(tmp_path)
    os.makedirs(os.path.join(root, 'data/benchmarks/robotics-embodiment'))
    shutil.move(os.path.join(root, BENCH), os.path.join(root, 'data/benchmarks/robotics-embodiment/example-bench.yaml'))
    assert [f.rule for f in tiers.run(root, 'schema').findings] == ['file-name']


def test_yaml_that_does_not_parse_fails_tier_1(tmp_path):
    root = tree(tmp_path)
    write(root, 'data/metrics/broken.yaml', 'id: broken\nid: twice\n')     # ruamel rejects a duplicate key
    r = tiers.run(root, 'schema')
    assert [(f.rule, f.entity) for f in r.findings] == [('yaml', 'broken')] and r.exit_code == 1


def test_a_file_no_kind_claims_fails_tier_1_and_an_unmodelled_one_is_listed(tmp_path):
    root = tree(tmp_path)
    write(root, 'data/stray/thing.yaml', 'id: thing\n')
    write(root, 'data/surveys/code/repository-scale-se.yaml', 'survey: {}\n')
    r = tiers.run(root)
    assert [(f.rule, f.path) for f in r.findings] == [('unknown-path', 'data/stray/thing.yaml')]
    assert r.unmodelled == ['data/surveys/code/repository-scale-se.yaml']


# ---- tier 2 -------------------------------------------------------------------------------------

CLAIM = """\
id: claim-0123456789ab
system: example-model
benchmark: example-bench
metric: accuracy
value: 0.5
date_reported: 2026-09-01
reported_by: org-example
verification: self-reported
source: src-example-page
"""
SYSTEM = """\
id: example-model
name: Example Model
organization: org-example
system_type: reasoning-model
availability: generally-available
sources: [src-example-page]
"""
ORG = """\
id: org-example
name: Example Org
kind: company
sources: [src-example-page]
"""


def with_claim(root):
    write(root, 'data/claims/example-bench/claim-0123456789ab.yaml', CLAIM)
    write(root, 'data/systems/example/example-model.yaml', SYSTEM)
    write(root, 'data/organizations/org-example.yaml', ORG)
    return root


def test_a_claim_with_every_record_it_names_resolves(tmp_path):
    r = tiers.run(with_claim(tree(tmp_path)), ['schema', 'ref', 'semantic'], today=TODAY)
    assert r.findings == []


@pytest.mark.parametrize('missing, message', [
    ('data/systems/example/example-model.yaml', 'system: no system record example-model'),
    ('data/organizations/org-example.yaml', 'reported_by: no organization record org-example'),
    ('data/metrics/accuracy.yaml', 'metric: no metric record accuracy'),
])
def test_a_claim_naming_a_missing_record_fails_tier_2(tmp_path, missing, message):
    root = with_claim(tree(tmp_path))
    os.remove(os.path.join(root, missing))
    msgs = [f.message for f in tiers.run(root, 'ref').findings if f.entity == 'claim-0123456789ab']
    assert message in msgs


def test_an_undeclared_version_fails_tier_2(tmp_path):
    root = with_claim(tree(tmp_path))
    write(root, BENCH, open(os.path.join(root, BENCH), encoding='utf-8').read() + 'versions:\n  - version: "1"\n'
          '    released: 2026-01-01\n    breaking: false\n')
    text = CLAIM.replace('benchmark: example-bench', 'benchmark: example-bench@2')
    write(root, 'data/claims/example-bench/claim-0123456789ab.yaml', text)
    msgs = [f.message for f in tiers.run(root, 'ref').findings]
    assert 'benchmark: example-bench declares no version 2' in msgs


def test_the_same_id_in_two_files_fails_tier_2(tmp_path):
    root = tree(tmp_path)
    write(root, 'data/metrics/accuracy-copy.yaml', open(os.path.join(root, 'data/metrics/accuracy.yaml'),
                                                         encoding='utf-8').read())
    r = tiers.run(root, 'ref')
    assert [f.rule for f in r.findings] == ['duplicate-id'] and r.exit_code == 1


def test_a_tombstone_resolves_only_with_a_redirect(tmp_path):
    root = tree(tmp_path)
    os.remove(os.path.join(root, 'data/metrics/accuracy.yaml'))
    write(root, 'data/tombstones/accuracy.yaml', 'id: accuracy\nredirects_to: null\n')
    assert any('tombstoned with no redirects_to' in f.message for f in tiers.run(root, 'ref').findings)
    write(root, 'data/tombstones/accuracy.yaml', 'id: accuracy\nredirects_to: exact-match\n')
    assert tiers.run(root, 'ref').findings == []


def test_a_retired_id_reused_as_a_record_fails_tier_2(tmp_path):
    root = tree(tmp_path)
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), os.path.join(root, 'taxonomy'))
    retired = tiers.read_yaml(os.path.join(root, 'taxonomy', 'retired-ids.yaml'))
    retired['retired'] = (retired['retired'] or []) + [{
        'id': 'accuracy', 'retired_on': '2026-09-01', 'reason': 'a test retirement', 'replaced_by': None}]
    write(root, 'taxonomy/retired-ids.yaml', json.dumps(retired, default=str))
    r = tiers.run(root, 'ref')
    assert [(f.rule, f.entity) for f in r.findings] == [('retired-id-ledger', 'accuracy')]


# ---- tier 3 -------------------------------------------------------------------------------------

def test_tier_3_warnings_do_not_block(tmp_path):
    root = tree(tmp_path)
    text = open(os.path.join(root, BENCH), encoding='utf-8').read().replace(
        '  access: fully-open', '  access: private-test-server').replace(
        'curation:', 'execution:\n  reproducibility_blockers: [private-test-set]\ncuration:')
    write(root, BENCH, text)
    r = tiers.run(root, 'semantic', today=TODAY)
    assert [(f.rule, f.severity) for f in r.findings] == [('private-server-submission', 'warning')]
    assert r.exit_code == 0


# ---- tier 4 -------------------------------------------------------------------------------------

def test_quality_flags_thin_claims_and_missing_baselines_and_liveness(tmp_path):
    root = with_claim(tree(tmp_path))
    os.remove(os.path.join(root, 'data/baselines/example-bench.yaml'))
    later = TODAY + datetime.timedelta(days=tiers.LIVENESS_STALE_DAYS + 6)
    r = tiers.run(root, 'quality', today=later)
    rules = {f.rule: f for f in r.findings}
    assert set(rules) == {'condition-completeness', 'no-baseline', 'liveness-stale'}
    assert 'below frontier_floor (0.3)' in rules['condition-completeness'].message
    assert r.exit_code == 0


def test_quality_flags_unarchived_sources_and_waivers(tmp_path):
    root = tree(tmp_path)
    src = os.path.join(root, 'data/sources/2026/src-example-page.yaml')
    write(root, 'data/sources/2026/src-example-page.yaml', open(src, encoding='utf-8').read().replace(
        'archive_status: ok', 'archive_status: pending'))
    write(root, BENCH, open(os.path.join(root, BENCH), encoding='utf-8').read().replace(
        'curation:', 'comparability:\n  material_waived:\n    - field: seed\n      reason: a test waiver\ncuration:'))
    rules = {f.rule for f in tiers.run(root, 'quality', today=TODAY).findings}
    assert rules == {'unarchived-source', 'material-waived'}


def test_last_verified_is_stale_after_twelve_calendar_months():
    assert tiers._months_ago(datetime.date(2026, 9, 25), 12) == datetime.date(2025, 9, 25)
    assert tiers._months_ago(datetime.date(2028, 2, 29), 12) == datetime.date(2027, 2, 28)
    assert tiers._months_ago(datetime.date(2026, 3, 31), 1) == datetime.date(2026, 2, 28)


# ---- scope: paths and --changed-only ------------------------------------------------------------

def test_paths_narrow_what_is_reported_not_what_is_read(tmp_path):
    root = tree(tmp_path, 'tier2')
    assert tiers.run(root, paths=[os.path.join(root, 'data/metrics')], today=TODAY).findings == []
    r = tiers.run(root, paths=[os.path.join(root, BENCH)], today=TODAY)
    assert [f.rule for f in r.findings] == ['dangling-ref'] and r.scope == 'paths' and r.files == 1


def test_a_deleted_source_is_reported_through_the_files_that_cite_it(tmp_path, monkeypatch):
    root = tree(tmp_path)
    os.remove(os.path.join(root, 'data/sources/2026/src-example-page.yaml'))
    monkeypatch.setattr(tiers, 'changed_files', lambda _root: {'data/sources/2026/src-example-page.yaml'})
    r = tiers.run(root, changed_only=True, today=TODAY)
    assert r.scope == 'changed-only' and r.exit_code == 1
    # the benchmark, the metric and the baselines file (reported under its file's name) all cite it
    assert {(f.entity, f.path) for f in r.findings} == {
        ('example-bench', BENCH), ('accuracy', 'data/metrics/accuracy.yaml'),
        ('example-bench', 'data/baselines/example-bench.yaml')}
    assert all(f.rule == 'dangling-ref' for f in r.findings)


def test_changed_files_reads_git(tmp_path):
    import subprocess
    root = tree(tmp_path)

    def git(*a):
        subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.org', *a], cwd=root, check=True,
                       capture_output=True)
    git('init', '-q', '-b', 'main')
    git('add', '-A')
    git('commit', '-q', '-m', 'base')
    write(root, 'data/metrics/accuracy.yaml', open(os.path.join(root, 'data/metrics/accuracy.yaml'),
                                                    encoding='utf-8').read() + 'units: ratio\n')
    write(root, 'data/metrics/new.yaml', 'id: new\n')
    assert tiers.changed_files(root) == {'data/metrics/accuracy.yaml', 'data/metrics/new.yaml'}


def test_the_cli_rejects_single_without_exactly_one_path():
    assert runner.invoke(cli.app, ['validate', '--single']).exit_code == 2
    assert runner.invoke(cli.app, ['validate', '--single', '--changed-only', BENCH]).exit_code == 2


def test_the_text_output_names_tier_rule_and_entity(tmp_path):
    result = runner.invoke(cli.app, ['validate', '--single', os.path.join(tree(tmp_path, 'tier3'), BENCH)])
    assert result.exit_code == 1
    assert 'BLOCKING 3/semantic lifecycle-triple example-bench' in result.stdout
    assert 'not checked:' in result.stdout and 'validate: schema,ref,semantic,quality over 1 file(s)' in result.stdout
