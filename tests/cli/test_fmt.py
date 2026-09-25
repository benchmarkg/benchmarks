"""Tests for `bench fmt` and the shared YAML emitter (P0-S5-T04; tools/fmt.py; 05 S1, S9 job 1; 07 S1.5).

The verify: "`bench fmt --check` exits 0 on the committed tree and non-zero on a deliberately
re-ordered fixture; running `bench fmt` twice then `git diff --exit-code` exits 0". The fixture is
fixtures/fmt/data/metrics/accuracy.yaml; it sits under a data/ segment so it is classified as a
Metric, and outside the repository's data/ so the default `bench fmt` never touches it.
"""
import os
import shutil
import subprocess
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from ruamel.yaml import YAML  # noqa: E402

from ingest import archive_sources  # noqa: E402
from schema.benchmark import Benchmark  # noqa: E402
from schema.metric import Metric  # noqa: E402
from schema.source import Source  # noqa: E402
from tools import cli, fmt  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'fmt', 'data', 'metrics',
                       'accuracy.yaml')
runner = CliRunner()


def keys(text):
    return list(YAML(typ='safe').load(text))


# ---- the verify ---------------------------------------------------------------------------------

def test_check_exits_zero_on_the_committed_tree():
    result = runner.invoke(cli.app, ['fmt', '--check'])
    assert result.exit_code == 0, result.output
    assert 'every file is formatted' in result.output


def test_check_exits_non_zero_on_the_reordered_fixture():
    before = open(FIXTURE, encoding='utf-8').read()
    result = runner.invoke(cli.app, ['fmt', '--check', FIXTURE])
    assert result.exit_code == 1
    assert 'would reformat' in result.output and 'accuracy.yaml' in result.output
    assert open(FIXTURE, encoding='utf-8').read() == before              # --check writes nothing


def test_formatting_twice_changes_nothing_the_second_time(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'data'), tmp_path / 'data')
    os.makedirs(tmp_path / 'data' / 'metrics')
    shutil.copy(FIXTURE, tmp_path / 'data' / 'metrics' / 'accuracy.yaml')
    first, errors = fmt.run(root=str(tmp_path))
    assert errors == [] and first == ['data/metrics/accuracy.yaml']   # the committed files are formatted already
    second, errors = fmt.run(root=str(tmp_path))
    assert (second, errors) == ([], [])


def test_the_committed_tree_is_a_fixed_point_under_git():
    """The verify's own form: `bench fmt` twice, then `git diff --exit-code` over data/."""
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'data'], cwd=ROOT).returncode != 0:
        pytest.skip('data/ differs from HEAD; the fixed-point check needs a committed data/')
    for _ in range(2):
        assert runner.invoke(cli.app, ['fmt']).exit_code == 0
    assert subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'data'], cwd=ROOT,
                          capture_output=True).returncode == 0


# ---- key order ----------------------------------------------------------------------------------

def test_the_fixture_is_restored_to_the_model_order_with_its_comments():
    out = fmt.format_text(open(FIXTURE, encoding='utf-8').read(), Metric, 'fixture')
    assert keys(out) == ['id', 'name', 'definition', 'value_type', 'range', 'optimum', 'sources']
    lines = out.split('\n')
    assert lines[0].startswith('# tests/cli/fixtures/fmt')                      # the file header stays on top
    assert lines[lines.index('id: accuracy') - 1] == '# the id comes last here, and first after formatting'
    assert lines[lines.index('optimum: max') - 1] == '# about the optimum'
    assert lines[lines.index('sources:                        # eol comment on sources') + 1] == '  - src-example-page'
    assert '  max: 1.0' in lines                                               # repr(round(x, 6))
    Metric.model_validate(YAML(typ='safe').load(out))


def test_annotations_follow_their_field_and_deferred_keys_come_last():
    text = ('id: b\neditions: {current: x}\ncuration_note: n\nname: B\nlifecycle_basis: why\ntagline: t\n'
            'lifecycle: active\n')
    # curation_note annotates curation, the last field, so it sits where curation would
    assert keys(fmt.format_text(text, Benchmark)) == ['id', 'name', 'tagline', 'lifecycle', 'lifecycle_basis',
                                                       'curation_note', 'editions']


def test_annotations_of_one_field_come_in_a_fixed_order():
    text = 'id: b\nlifecycle: active\nlifecycle_quote: q\nlifecycle_note: n\nlifecycle_source: src-a\n'
    assert keys(fmt.format_text(text, Benchmark)) == ['id', 'lifecycle', 'lifecycle_note', 'lifecycle_source',
                                                       'lifecycle_quote']


def test_a_data_keyed_mapping_and_every_list_keep_their_order():
    text = 'id: b\ncapability_basis:\n  zeta: z\n  alpha: a\ncapability: [zeta, alpha]\n'
    doc = YAML(typ='safe').load(fmt.format_text(text, Benchmark))
    assert list(doc['capability_basis']) == ['zeta', 'alpha']
    assert doc['capability'] == ['zeta', 'alpha']


def test_nested_models_and_list_items_are_reordered():
    text = ('id: b\ncuration:\n  sources: [src-a]\n  added_by: me\nlearned_entrant_evidence:\n'
            '  - source: src-a\n    # about the system\n    system: S\n')
    out = fmt.format_text(text, Benchmark)
    doc = YAML(typ='safe').load(out)
    assert list(doc['curation']) == ['added_by', 'sources']
    assert list(doc['learned_entrant_evidence'][0]) == ['system', 'source']
    assert '# about the system' in out                               # placed above the item, not lost
    assert fmt.format_text(out, Benchmark) == out


def test_a_comment_that_must_open_a_top_level_list_item_is_kept():
    text = '# header\n\n- metric: m\n  # about the id\n  id: base-a\n'
    out = fmt.format_text(text, fmt.model_for('data/baselines/x.yaml'))
    assert out.startswith('# header\n') and '# about the id' in out
    assert list(YAML(typ='safe').load(out)[0]) == ['id', 'metric']
    assert fmt.format_text(out, fmt.model_for('data/baselines/x.yaml')) == out


def test_a_comment_after_a_flow_list_stays_after_it_when_the_list_turns_block():
    """RoboArena's shape: ruamel keeps the lines after a flow list on its key, and a naive block
    conversion printed the next section's header between `tags:` and its item."""
    text = 'tags: [x]          # eol\n\n# --- Curation ---\n\ncuration:\n  added_by: me\n'
    out = fmt.format_text(text, Benchmark)
    lines = out.split('\n')
    assert lines[0] == 'tags:              # eol' and lines[1] == '  - x'   # the eol comment keeps its column
    assert lines.index('# --- Curation ---') == lines.index('curation:') - 2
    assert fmt.format_text(out, Benchmark) == out


def test_a_file_with_no_model_is_restyled_but_not_reordered():
    assert fmt.format_text('zeta: [1, 2]\nalpha: 1\n', None) == 'zeta:\n  - 1\n  - 2\nalpha: 1\n'


# ---- style --------------------------------------------------------------------------------------

def test_quoting_is_normalised_but_a_string_that_needs_quotes_keeps_them():
    out = fmt.format_text('a: "plain"\nb: \'2026-09-23T18:24:26Z\'\nc: "true"\nd: \'x: y\'\n')
    assert out == "a: plain\nb: '2026-09-23T18:24:26Z'\nc: 'true'\nd: 'x: y'\n"


def test_floats_are_repr_of_round_six():
    out = fmt.format_text('a: 0.7870000000000001\nb: 1.0e-3\nc: 5.0\nd: 12\n')
    assert out == 'a: 0.787\nb: 0.001\nc: 5.0\nd: 12\n'


def test_a_float_with_real_digits_past_six_places_is_refused_not_rounded():
    with pytest.raises(fmt.FmtError, match='more than six decimal places'):
        fmt.format_text('a: 1.0e-7\n', name='x.yaml')
    with pytest.raises(fmt.FmtError, match='more than six decimal places'):
        fmt.format_text('a: 0.1234567\n', name='x.yaml')


def test_lists_are_block_and_empty_containers_stay_flow():
    assert fmt.format_text('a: [x, y]\nb: []\nc: {}\nd: {k: v}\n') == 'a:\n  - x\n  - y\nb: []\nc: {}\nd:\n  k: v\n'


def test_nulls_line_width_whitespace_and_the_final_newline():
    long = 'word ' * 30
    out = fmt.format_text('a: ~\nb:    %s   \r\nc: x\n\n\n' % long)
    assert out.startswith('a: null\nb: word')
    assert max(len(line) for line in out.split('\n')) <= 100
    assert '\r' not in out and not any(line != line.rstrip() for line in out.split('\n'))
    assert out.endswith('c: x\n') and not out.endswith('\n\n')


def test_a_literal_block_is_kept_byte_for_byte():
    text = 'quote_extract: |-\n  line one\n    indented  two\n  # not a comment, content\n'
    assert fmt.format_text(text) == text


# ---- the guards ---------------------------------------------------------------------------------

def test_a_change_of_value_is_refused(monkeypatch):
    monkeypatch.setattr(fmt, 'dumps', lambda node: 'a: 2\n')
    with pytest.raises(fmt.FmtError, match='would change the data'):
        fmt.format_text('a: 1\n', name='x.yaml')


def test_a_lost_comment_is_refused(monkeypatch):
    real = fmt.dumps
    monkeypatch.setattr(fmt, 'dumps', lambda node: real(node).replace('# keep me\n', ''))
    with pytest.raises(fmt.FmtError, match='lose or duplicate a comment'):
        fmt.format_text('a: 1\n# keep me\nb: 2\n', name='x.yaml')


def test_run_reports_a_refusal_and_writes_nothing(tmp_path, monkeypatch):
    (tmp_path / 'data').mkdir()
    p = tmp_path / 'data' / 'x.yaml'
    p.write_text('b: [1]\na: 1\n', encoding='utf-8')
    monkeypatch.setattr(fmt, 'dumps', lambda node: 'b: 9\n')
    changed, errors = fmt.run(root=str(tmp_path))
    assert changed == [] and 'would change the data' in errors[0]
    assert p.read_text(encoding='utf-8') == 'b: [1]\na: 1\n'
    result = runner.invoke(cli.app, ['fmt', str(p)])
    assert result.exit_code == 1


# ---- the archiver shares the emitter ------------------------------------------------------------

def test_the_archiver_rewrite_leaves_a_formatted_file_and_clears_a_wrapped_value(tmp_path):
    src = os.path.join(ROOT, 'data', 'sources', '2026', 'src-swebench-readme.yaml')
    p = tmp_path / 'data' / 'sources' / '2026' / 'src-swebench-readme.yaml'
    p.parent.mkdir(parents=True)
    shutil.copy(src, p)
    assert '\n  anonymous request' in p.read_text(encoding='utf-8')             # failure_reason spans two lines
    archive_sources.rewrite(str(p), {'archive_status': 'ok', 'failure_reason': None,
                                     'archive_url': 'https://web.archive.org/web/20261001000000/https://x.org/'})
    text = p.read_text(encoding='utf-8')
    doc = YAML(typ='safe').load(text)
    assert doc['failure_reason'] is None and doc['archive_status'] == 'ok'
    assert 'anonymous request' not in text                        # the old continuation line is gone
    assert fmt.format_text(text, Source) == text                  # and the file is what `bench fmt` writes
    assert text.startswith('# data/sources/2026/src-swebench-readme.yaml')
