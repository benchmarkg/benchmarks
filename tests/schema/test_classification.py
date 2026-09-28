"""schema/classification.py and tools/validate/classifications.py: the Stage-3 records (P1-S1-T03; 03 S3.3).

The task's VERIFY: `bench validate taxonomy/_corpus/classifications/ --tier all` over at least 30
records. DONE WHEN: "30 classification records validate and every abstention has a matching failure
record". Each rule below is shown failing its own case, and the committed records are shown passing.
"""
import copy
import glob
import os
import sys

import io
import shutil

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from schema.classification import FIELDS, Classification, FailureRecord  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402
from tools.validate import tiers  # noqa: E402


def dump(x) -> str:
    from ruamel.yaml import YAML
    buf = io.StringIO()
    YAML(typ='safe', pure=True).dump(x, buf)
    return buf.getvalue()

CLS = os.path.join(ROOT, 'taxonomy', '_corpus', 'classifications')
FAILS = os.path.join(ROOT, 'taxonomy', '_failures')
SINGLE = [f for f, (_, multi) in FIELDS.items() if not multi]


def _value(field):
    vocab, _ = FIELDS[field]
    return {'value': vocab[0], 'source': 'paper', 'quote': 'a quote'}


def record(**over):
    """A minimal valid record: every field one quoted value, except one abstention."""
    facets = {f: [_value(f)] for f in FIELDS}
    facets['lifecycle'] = [{'value': 'active', 'source': 'paper', 'quote': 'q'}]
    facets['data.refresh'] = [{'value': None, 'failure': '2026-09-28-mmlu-pro-003'}]
    rec = {'id': 'mmlu-pro', 'corpus_item': 1, 'curator': 'someone', 'classified_on': '2026-09-28',
           'taxonomy_version': '0.1.0', 'sources': {'paper': 'https://arxiv.org/abs/2406.01574'}, 'facets': facets}
    rec.update(over)
    return rec


def failure(**over):
    f = {'kind': 'source-silent', 'facet': 'data.refresh', 'benchmark': 'mmlu-pro', 'curator': 'someone',
         'date': '2026-09-28', 'description': 'the sources say nothing', 'blocking': False,
         'classification': 'mmlu-pro'}
    f.update(over)
    return f


# ---- the model ------------------------------------------------------------------------------------

def test_a_minimal_record_validates():
    m = Classification.model_validate(record())
    assert m.abstentions() == ['data.refresh'] and m.failures() == [('data.refresh', '2026-09-28-mmlu-pro-003')]
    assert len(FIELDS) == 19


def edited(fn):
    r = record()
    fn(r)
    return r


@pytest.mark.parametrize('rec, message', [
    (edited(lambda r: r['facets'].pop('capability')), 'missing capability'),
    (edited(lambda r: r['facets'].update({'tags': []})), 'unknown tags'),
    (edited(lambda r: r['facets'].update({'capability': []})), 'capability: empty'),
    (edited(lambda r: r['facets'].update({'data.access': [_value('data.access'), _value('data.access')]})),
     'single-valued'),
    (edited(lambda r: r['facets'].update({'capability': [{'value': 'telepathy', 'source': 'paper', 'quote': 'q'}]})),
     "'telepathy' is not a term of capability"),
    (edited(lambda r: r['facets'].update({'capability': [{'value': 'knowledge-recall'}]})), 'source-bound'),
    (edited(lambda r: r['facets'].update({'capability': [{'value': 'knowledge-recall', 'source': 'site',
                                                           'quote': 'q'}]})), "source 'site' is not a key"),
    (edited(lambda r: r['facets'].update({'data.refresh': [{'value': None}]})), 'names the failure record'),
    (edited(lambda r: r['facets'].update({'capability': [_value('capability'), {'value': None,
                                                                                'failure': '2026-09-28-mmlu-pro-009'}]})),
     "only assignment"),
    (edited(lambda r: r['facets'].update({'lifecycle': [{'value': 'saturated', 'source': 'paper', 'quote': 'q'}]})),
     'never hand-set'),
    (edited(lambda r: r['facets'].update({'activity': [{'value': 'unknown'}]})), 'states what is known'),
    (edited(lambda r: r['facets'].update({'domain.primary': [{'value': 'language', 'source': 'paper',
                                                              'quote': 'q'}]})), "'language' is not a term"),
])
def test_each_rule_refuses_its_case(rec, message):
    with pytest.raises(ValidationError, match=message):
        Classification.model_validate(rec)


def test_empty_is_a_classification_only_where_none_applies():
    r = record()
    r['facets']['domain.secondary'] = []
    r['facets']['execution.reproducibility_blockers'] = []
    Classification.model_validate(r)


def test_an_epistemic_term_needs_a_note_not_a_quote():
    r = record()
    r['facets']['data.contamination_risk'] = [{'value': 'unknown', 'note': 'nobody has assessed it'}]
    r['facets']['data.ceiling_anchor_type'] = [{'value': 'none-known', 'note': 'no human baseline reported'}]
    Classification.model_validate(r)


def test_a_failure_record_is_03s_block():
    FailureRecord.model_validate(failure())
    with pytest.raises(ValidationError, match='not a classified field'):
        FailureRecord.model_validate(failure(facet='vibes'))
    with pytest.raises(ValidationError, match='at least two'):
        FailureRecord.model_validate(failure(kind='collision', terms=['single-gpu']))
    with pytest.raises(ValidationError):
        FailureRecord.model_validate(failure(kind='mood'))


# ---- the cross-record rules, over a fixture tree -----------------------------------------------------

def tree(tmp_path, records, failures):
    root = tmp_path / 'root'
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), root / 'taxonomy',
                    ignore=shutil.ignore_patterns('_corpus', '_failures', 'crosswalks'))
    (root / 'taxonomy' / '_corpus' / 'classifications').mkdir(parents=True)
    (root / 'taxonomy' / '_failures').mkdir(parents=True)
    (root / 'data').mkdir()
    (root / 'taxonomy' / '_corpus' / 'stress-corpus.yaml').write_text(dump(
        {'entries': [{'id': 'mmlu-pro'}, {'id': 'wmt25'}]}), encoding='utf-8')
    for r in records:
        (root / 'taxonomy' / '_corpus' / 'classifications' / ('%s.yaml' % r['id'])).write_text(
            dump(r), encoding='utf-8')
    for name, f in failures.items():
        (root / 'taxonomy' / '_failures' / ('%s.yaml' % name)).write_text(dump(f), encoding='utf-8')
    return root


def rules(root):
    report = tiers.run(str(root), 'all', paths=[str(root / 'taxonomy' / '_corpus' / 'classifications'),
                                                  str(root / 'taxonomy' / '_failures')])
    return sorted({f.rule for f in report.findings if f.blocks}), report


def test_a_consistent_pair_validates(tmp_path):
    found, report = rules(tree(tmp_path, [record()], {'2026-09-28-mmlu-pro-003': failure()}))
    assert found == [] and report.exit_code == 0 and report.files == 2


def test_an_abstention_whose_failure_is_missing_fails(tmp_path):
    found, _ = rules(tree(tmp_path, [record()], {}))
    assert found == ['abstention-logged', 'failure-ref']


def test_a_failure_about_another_field_does_not_match(tmp_path):
    found, _ = rules(tree(tmp_path, [record()], {'2026-09-28-mmlu-pro-003': failure(facet='lifecycle')}))
    assert 'failure-ref' in found and 'abstention-logged' not in found


def test_an_uncited_failure_fails(tmp_path):
    found, _ = rules(tree(tmp_path, [record()], {'2026-09-28-mmlu-pro-003': failure(),
                                                 '2026-09-28-mmlu-pro-004': failure(facet='lifecycle')}))
    assert found == ['failure-uncited']


def test_an_entry_not_in_the_corpus_or_at_the_wrong_position_fails(tmp_path):
    other = record(id='gpqa-diamond')
    found, _ = rules(tree(tmp_path / 'a', [other], {'2026-09-28-mmlu-pro-003': failure()}))
    assert 'classification-entry' in found
    moved = record(corpus_item=2)
    found, _ = rules(tree(tmp_path / 'b', [moved], {'2026-09-28-mmlu-pro-003': failure()}))
    assert found == ['classification-entry']


def test_a_failure_file_is_named_for_its_date_and_benchmark(tmp_path):
    r = record()
    r['facets']['data.refresh'] = [{'value': None, 'failure': '2026-09-27-mmlu-pro-003'}]
    found, _ = rules(tree(tmp_path, [r], {'2026-09-27-mmlu-pro-003': failure()}))
    assert 'file-name' in found


def test_a_record_file_is_named_for_its_id(tmp_path):
    root = tree(tmp_path, [], {'2026-09-28-mmlu-pro-003': failure()})
    (root / 'taxonomy' / '_corpus' / 'classifications' / 'wrong.yaml').write_text(dump(record()),
                                                                                  encoding='utf-8')
    found, _ = rules(root)
    assert 'file-name' in found


# ---- the committed records -----------------------------------------------------------------------------

def test_the_committed_records_validate_and_every_abstention_is_logged():
    files = sorted(glob.glob(os.path.join(CLS, '*.yaml')))
    assert len(files) >= 30
    report = tiers.run(ROOT, 'all', paths=['taxonomy/_corpus/classifications', 'taxonomy/_failures'])
    assert [str(f) for f in report.blocking] == []
    fails = {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(FAILS, '*.yaml'))}
    for p in files:
        m = Classification.model_validate(read_yaml(p))
        cited = {fid for field, fid in m.failures()}
        assert cited <= fails, m.id
        for field in m.abstentions():
            assert any(f == field and fid in fails for f, fid in m.failures()), (m.id, field)


def test_the_committed_records_are_items_1_to_30():
    items = sorted(read_yaml(p)['corpus_item'] for p in glob.glob(os.path.join(CLS, '*.yaml')))
    assert items[:30] == list(range(1, 31))


def test_a_proposed_term_is_not_read_as_an_entity_reference(tmp_path):
    found, _ = rules(tree(tmp_path, [record()], {'2026-09-28-mmlu-pro-003': failure(proposed_term='pool-relative-ranking')}))
    assert found == []
