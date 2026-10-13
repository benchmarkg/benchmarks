"""The escape-hatch audit and ADR-0026 (P0-S9-T05; 14-roadmap Phase 0, "a `notes` field doing structural work is the tell").

The verify: "`grep -rn "^ *extra:" data/ schema/` returns nothing and `python -c` asserts no notes or curation.notes
field in the ten entries exceeds 200 characters." Both run here, then what ADR-0026 adds: migration 0026's parser
(the reviewer-check and schema-finding blocks, and the paragraph form with its Source and Quote), its idempotence on
the applied corpus, and the four new fields' rules.
"""
import importlib.util
import os
import re
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.baseline import Baseline  # noqa: E402
from schema.benchmark import Curation, ReviewCheck  # noqa: E402
from schema.entities import Subset  # noqa: E402
from schema.taxonomy import read_yaml  # noqa: E402

spec = importlib.util.spec_from_file_location('migration_0026', os.path.join(ROOT, 'schema', 'migrations', '0026-review-checks.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
STRESS = read_yaml(os.path.join(ROOT, 'tests', 'fixtures', 'stress-entries.yaml'))['entries']


def notes_strings(record, at=''):
    if isinstance(record, dict):
        for k, v in record.items():
            here = '%s.%s' % (at, k) if at else k
            if k == 'notes' and isinstance(v, str):
                yield here, v
            yield from notes_strings(v, here)
    elif isinstance(record, list):
        for i, v in enumerate(record):
            yield from notes_strings(v, '%s[%d]' % (at, i))


# ---- the verify -----------------------------------------------------------------------------------------------------

def test_verify_no_extra_map_in_data_or_schema():
    found = []
    for top in ('data', 'schema'):
        for folder, _, files in os.walk(os.path.join(ROOT, top)):
            for name in files:
                if not name.endswith(('.yaml', '.yml', '.py', '.json')):
                    continue
                path = os.path.join(folder, name)
                for n, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
                    if re.match(r'^ *extra:', line):
                        found.append('%s:%d' % (os.path.relpath(path, ROOT), n))
    assert found == []


def test_verify_no_notes_string_in_the_ten_stress_entries_exceeds_200_characters():
    assert len(STRESS) == 10
    long = [(e['id'], at, len(v)) for e in STRESS for at, v in notes_strings(read_yaml(os.path.join(ROOT, e['path'])))
            if len(v) > 200]
    assert long == []


def test_the_audit_has_a_row_for_every_notes_string_the_ten_held():
    audit = open(os.path.join(ROOT, 'docs', 'schema-stress-audit.md'), encoding='utf-8').read()
    for e in STRESS:
        for at, _ in notes_strings(read_yaml(os.path.join(ROOT, e['path']))):
            assert '| %s | %s |' % (e['id'], at) in audit, (e['id'], at)


# ---- migration 0026 -------------------------------------------------------------------------------------------------

LIST = """Reviewer checks (specialist):
- Whether the grid is right is a meteorology judgement; nothing here was checked
  by anyone who does forecast verification.
- physics/simulation-surrogates as a secondary domain (domain.secondary_note).

Schema findings (none worked around here):
1. Evaluation resolution is material and has no EvalConditions field.
2. secondary_axes is an enum of {cost, latency}.
"""
ONE = ('Reviewer check (governance): A researcher sits on the advisory board. Source: src-casp17-home. Quote: "John\n'
       'Jumper, Google Deepmind, London, UK" Why no flag: an advisory board is not the maintainer.')


def test_the_list_form_becomes_checks_with_fields_and_the_findings_leave():
    checks, findings, rest = M.parse(LIST)
    assert checks == [
        {'check': 'Whether the grid is right is a meteorology judgement; nothing here was checked by anyone who does '
                  'forecast verification.', 'specialist': True},
        {'check': 'physics/simulation-surrogates as a secondary domain (domain.secondary_note).',
         'field': 'domain.secondary_note', 'specialist': True},
    ]
    assert findings == ['1. Evaluation resolution is material and has no EvalConditions field.',
                        '2. secondary_axes is an enum of {cost, latency}.']
    assert rest == []


def test_the_paragraph_form_moves_its_source_and_quote_into_fields():
    [check], findings, rest = M.parse(ONE)
    assert check == {'check': 'A researcher sits on the advisory board. Why no flag: an advisory board is not the maintainer.',
                     'field': 'governance', 'source': 'src-casp17-home', 'quote': 'John Jumper, Google Deepmind, London, UK'}
    assert findings == [] and rest == []
    [scoped], _, _ = M.parse('Reviewer check (governance.independence_flags: funded-by-evaluated-party): Flag or drop.')
    assert scoped == {'check': 'funded-by-evaluated-party: Flag or drop.', 'field': 'governance.independence_flags'}


def test_other_prose_would_stay_in_the_notes():
    _, _, rest = M.parse('A paragraph that is neither.\n\n' + LIST)
    assert rest == ['A paragraph that is neither.']


def test_the_migration_is_applied_and_plans_nothing_more():
    assert M.plan(ROOT) == []


def test_no_curated_entry_keeps_a_reviewer_check_or_a_finding_in_its_notes():
    for folder, _, files in os.walk(os.path.join(ROOT, 'data', 'benchmarks')):
        if '_stubs' in folder:
            continue
        for name in files:
            notes = (read_yaml(os.path.join(folder, name)).get('curation') or {}).get('notes') or ''
            assert 'Reviewer check' not in notes and 'Schema findings' not in notes, name


# ---- the new fields -------------------------------------------------------------------------------------------------

def test_a_review_check_quoting_a_source_names_it():
    ReviewCheck.model_validate({'check': 'Is the flag right?', 'field': 'governance', 'source': 'src-a', 'quote': 'q'})
    with pytest.raises(ValidationError, match='names it'):
        ReviewCheck.model_validate({'check': 'Is the flag right?', 'quote': 'q'})
    with pytest.raises(ValidationError):
        ReviewCheck.model_validate({'check': 'x', 'field': 'baselines[0]'})          # a field is a dotted path


def test_curation_review_checks_default_to_none():
    c = Curation.model_validate({'added_by': 'a', 'added_on': '2026-10-12', 'last_verified': '2026-10-12',
                                 'sources': ['src-a']})
    assert c.review_checks == []


BASE = {'id': 'base-pb-human', 'benchmark_version': 'paperbench@2025-04', 'kind': 'human-expert-best',
        'metric': 'paperbench-replication-score', 'value': 41.4, 'source': 'src-paperbench-arxiv-html'}


def test_a_baseline_names_its_own_benchmarks_subset_and_carries_evidence():
    b = Baseline.model_validate(dict(BASE, subset='paperbench#human-baseline-3',
                                     evidence=[{'source': 'src-paperbench-arxiv-html', 'quote': 'q'}]))
    assert b.subset == 'paperbench#human-baseline-3' and b.evidence[0].source == 'src-paperbench-arxiv-html'
    with pytest.raises(ValidationError, match='is not a subset of'):
        Baseline.model_validate(dict(BASE, subset='other-bench#part'))


def test_a_subset_carries_evidence():
    s = Subset.model_validate({'id': 'arc-agi-3#public-demo', 'label': 'Public demo set',
                               'evidence': [{'source': 'src-arc-agi-3-report-arxiv', 'quote': 'q'}]})
    assert s.evidence[0].quote == 'q'
    with pytest.raises(ValidationError):
        Subset.model_validate({'id': 'arc-agi-3#x', 'label': 'x', 'evidence': [{'quote': 'no source'}]})
