"""Tests for scripts/notes_field_audit.py (P1-S3-T04) on a two-entry tree built in tmp_path."""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('notes_field_audit', os.path.join(ROOT, 'scripts', 'notes_field_audit.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

ALPHA = """id: alpha
data:
  access: fully-open
  access_note: Gated on Hugging Face behind a click-through.
  refresh: static
governance:
  independence_flags: []
  independence_flags_note: Not assessed.
curation:
  notes: Reviewer check.
"""
BETA = """id: beta
data:
  access: fully-open
  data_provenance:
    - expert-authored
capability:
  - perception
"""


def tree(tmp_path):
    for fam, name, text in (('vision', 'alpha', ALPHA), ('physics', 'beta', BETA)):
        d = tmp_path / 'data' / 'benchmarks' / fam
        d.mkdir(parents=True, exist_ok=True)
        (d / ('%s.yaml' % name)).write_text(text, encoding='utf-8')
    return str(tmp_path)


def test_every_note_is_listed_with_the_fields_beside_it(tmp_path):
    rep = audit.build(tree(tmp_path))
    by_path = {(n['entry'], n['path']): n for n in rep['notes']}
    assert set(by_path) == {('alpha', 'data.access_note'), ('alpha', 'governance.independence_flags_note'),
                            ('alpha', 'curation.notes')}
    beside = by_path[('alpha', 'data.access_note')]['beside']
    assert beside == {'access': 'fully-open', 'refresh': 'static'}            # notes are not each other's context
    assert by_path[('alpha', 'governance.independence_flags_note')]['beside'] == {'independence_flags': '[0 items]'}


def test_full_required_fields_left_empty_are_listed_per_entry(tmp_path):
    rep = audit.build(tree(tmp_path))
    nulls = {r['field']: {m['entry']: m['how'] for m in r['missing']} for r in rep['nulls']}
    assert nulls['capability'] == {'alpha': 'absent'}                       # absent, and the default is []
    assert nulls['governance.independence_flags'] == {'alpha': 'empty', 'beta': 'absent'}
    assert 'beta' not in nulls['data.data_provenance'] and 'alpha' in nulls['data.data_provenance']


def test_unused_fields_are_the_model_fields_no_entry_sets(tmp_path):
    rep = audit.build(tree(tmp_path))
    unused = {u['field'] for u in rep['unused']}
    assert 'capability' not in unused and 'data.access' not in unused
    assert 'data.size' in unused and 'lineage' in unused
    assert not any(u['field'] == 'maintenance_status' for u in rep['unused'])   # derived: not a model field


def test_the_json_and_text_forms_agree_and_an_empty_tree_exits_2(tmp_path, capsys):
    root = tree(tmp_path)
    assert audit.main(['--root', root, '--json']) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc['entries'] == 2 and len(doc['notes']) == 3
    assert audit.main(['--root', root, '--section', 'notes']) == 0
    assert '== notes: 3 free-text notes in 2 entries' in capsys.readouterr().out
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert audit.main(['--root', str(empty)]) == 2


def test_the_repository_corpus_audits():
    rep = audit.build(ROOT)
    assert rep['entries'] >= 20 and rep['notes'] and rep['nulls'] and rep['unused']
