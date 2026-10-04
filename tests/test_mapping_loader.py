"""Tests for ingest/mappings/schema.py, the mapping stanza and its loader (P3-S2-T02; 07 S2.1, S8).

The verify: "A stanza omitting `scale` is rejected by the loader rather than defaulted to 1.0."
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ingest.mappings import schema as m  # noqa: E402

# 07 S2.1's example stanza, with the two fields this task adds to it
EXAMPLE = """\
benchmark_ref: swe-bench@verified
family: epoch-run
score_column: "Best score (across scorers)"
scale: 1.0
scale_source: benchmark_metadata.csv
metric_ref: resolve-rate
source_ref: src-epoch-benchmark-data
uncertainty:
  column: stderr
  type: stderr
artifact:
  log_column: "Logs"
  viewer_column: "Log viewer"
date_column: "Started at"
conditions:
  reasoning_effort: { from: model_version_suffix }
  selection_strategy: { const: best-across-scorers, k: null }
"""


def stanza(tmp_path, stem, text):
    d = tmp_path / 'epoch'
    d.mkdir(exist_ok=True)
    (d / (stem + '.yaml')).write_text(text, encoding='utf-8')
    return str(tmp_path)


def without(text, key):
    return ''.join(line for line in text.splitlines(True) if not line.startswith(key + ':'))


def test_07_s2_1s_example_loads(tmp_path):
    s = m.load_mapping('epoch', 'csv:swe_bench_verified', stanza(tmp_path, 'swe_bench_verified', EXAMPLE))
    assert (s.benchmark_ref, s.score_column, s.scale, s.metric_ref) == (
        'swe-bench@verified', 'Best score (across scorers)', 1.0, 'resolve-rate')
    assert s.conditions['reasoning_effort'].from_ == 'model_version_suffix'
    assert s.conditions['selection_strategy'].const == 'best-across-scorers'
    assert s.uncertainty.type == 'stderr' and s.artifact.log_column == 'Logs'


def test_a_stanza_omitting_scale_is_rejected_not_defaulted(tmp_path):
    root = stanza(tmp_path, 'swe_bench_verified', without(EXAMPLE, 'scale'))
    with pytest.raises(m.MappingError, match=r'swe_bench_verified\.yaml.*scale.*[Ff]ield required'):
        m.load_mapping('epoch', 'csv:swe_bench_verified', root)
    assert m.Stanza.model_fields['scale'].is_required()      # no default anywhere to fall back on


@pytest.mark.parametrize('value', ['null', '0.5', '100', '-1.0', '"one"', 'true', "'1.0'"])
def test_a_scale_must_be_one_of_07s_three(tmp_path, value):
    root = stanza(tmp_path, 'x', EXAMPLE.replace('scale: 1.0', 'scale: %s' % value))
    with pytest.raises(m.MappingError, match='scale'):
        m.load_mapping('epoch', 'csv:x', root)


@pytest.mark.parametrize('value', ['1.0', '0.1', '0.01', '1'])
def test_the_three_scales_load(tmp_path, value):
    root = stanza(tmp_path, 'x', EXAMPLE.replace('scale: 1.0', 'scale: %s' % value))
    assert m.load_mapping('epoch', 'csv:x', root).scale == float(value)


def test_scale_source_is_required_and_is_the_metadata_file_or_a_url(tmp_path):
    with pytest.raises(m.MappingError, match='scale_source'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', without(EXAMPLE, 'scale_source')))
    with pytest.raises(m.MappingError, match='the URL the scale was read from'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', EXAMPLE.replace(
            'scale_source: benchmark_metadata.csv', 'scale_source: I checked it')))
    orphan = EXAMPLE.replace('scale_source: benchmark_metadata.csv',
                             'scale_source: https://example.org/leaderboard')        # an orphan's (P3-S2-T04)
    assert m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', orphan)).scale_source.startswith('https://')


@pytest.mark.parametrize('field', ['benchmark_ref', 'family', 'score_column', 'metric_ref', 'source_ref'])
def test_the_other_required_fields(tmp_path, field):
    with pytest.raises(m.MappingError, match=field):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', without(EXAMPLE, field)))


def test_an_unknown_key_is_rejected(tmp_path):
    with pytest.raises(m.MappingError, match='Extra inputs are not permitted'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', EXAMPLE + 'default_scale: 1.0\n'))


def test_a_condition_must_name_an_eval_conditions_field(tmp_path):
    text = EXAMPLE + '  reasoning_budget: { const: high }\n'
    with pytest.raises(m.MappingError, match='not EvalConditions fields: reasoning_budget'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', text))


@pytest.mark.parametrize('rule, why', [
    ('{ from: model_version_suffix, const: high }', 'exactly one'),
    ('{ k: 3 }', 'exactly one'),
    ('{ from: column }', '`column` goes with'),
    ('{ const: high, column: Effort }', '`column` goes with'),
])
def test_a_condition_rule_is_from_a_rule_or_a_constant(tmp_path, rule, why):
    text = EXAMPLE.replace('reasoning_effort: { from: model_version_suffix }', 'reasoning_effort: %s' % rule)
    with pytest.raises(m.MappingError, match=why):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', text))


def test_a_condition_can_come_from_a_named_column(tmp_path):
    text = EXAMPLE.replace('reasoning_effort: { from: model_version_suffix }',
                           'reasoning_effort: { from: column, column: Effort }')
    assert m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', text)).conditions['reasoning_effort'].column == 'Effort'


def test_a_benchmark_ref_may_name_a_version_or_a_subset(tmp_path):
    for ref in ('gpqa#diamond', 'swe-bench@verified', 'frontiermath@v2#tiers-1-3'):
        text = EXAMPLE.replace('benchmark_ref: swe-bench@verified', 'benchmark_ref: %s' % ref)
        assert m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', text)).benchmark_ref == ref
    with pytest.raises(m.MappingError, match='benchmark_ref'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', EXAMPLE.replace(
            'benchmark_ref: swe-bench@verified', 'benchmark_ref: "SWE-bench Verified"')))


# ---- the loader -----------------------------------------------------------------------------------------

def test_no_stanza_is_none_so_the_adapter_records_an_unresolved(tmp_path):
    assert m.load_mapping('epoch', 'csv:not_mapped_yet', str(tmp_path)) is None


@pytest.mark.parametrize('key', ['bench:GPQA diamond', 'csv:', 'csv:../escape', 'csv:_id_allocation'])
def test_only_a_csv_candidate_has_a_stanza(tmp_path, key):
    with pytest.raises(m.MappingError, match='only a csv:<file stem> candidate is mapped'):
        m.load_mapping('epoch', key, str(tmp_path))


def test_a_file_that_is_not_a_mapping_names_itself(tmp_path):
    with pytest.raises(m.MappingError, match=r'x\.yaml'):
        m.load_mapping('epoch', 'csv:x', stanza(tmp_path, 'x', '- a list\n- not a stanza\n'))


def test_load_all_skips_the_allocation_and_keys_by_source_key(tmp_path):
    root = stanza(tmp_path, 'swe_bench_verified', EXAMPLE)
    stanza(tmp_path, 'gpqa_diamond', EXAMPLE.replace('swe-bench@verified', 'gpqa#diamond'))
    (tmp_path / 'epoch' / '_id_allocation.yaml').write_text('not: a stanza\n', encoding='utf-8')
    got = m.load_all('epoch', root)
    assert sorted(got) == ['csv:gpqa_diamond', 'csv:swe_bench_verified']
    assert m.load_all('nobody', root) == {}


def test_the_committed_epoch_mappings_all_load():
    # today only the id allocation, which is not a stanza; P3-S2-T03 and T04 add the ~80 stanzas
    m.load_all('epoch')
