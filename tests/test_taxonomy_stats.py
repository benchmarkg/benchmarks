"""scripts/taxonomy_stats.py: check 9d, the per-field 9b rows, and the 02 count sync (P1-S1-T07)."""
import copy
import os
import sys

import pytest
from pydantic import ValidationError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, ROOT)
import taxonomy_stats as T  # noqa: E402
from schema.taxonomy import FieldTerm  # noqa: E402


def run(check, *args):
    r = T.Result()
    check(r, *args)
    return r


def test_the_committed_taxonomy_passes_9d_and_the_count_sync():
    doc = T.plan_doc('02-taxonomy.md')
    assert not run(T.check_9d).failed
    assert not run(T.check_9b_fields, doc).failed
    assert not run(T.check_9b_document, doc).failed


def test_9d_fails_on_an_undeclared_and_on_a_stale_homograph(monkeypatch):
    real = T.load_facet
    hom = copy.deepcopy(real('homographs'))
    dropped = hom['entries'].pop(0)
    hom['entries'].append(dict(dropped, capability='capability:not-a-term', domain='domain:language/not-a-leaf'))
    monkeypatch.setattr(T, 'load_facet', lambda n: hom if n == 'homographs' else real(n))
    r = run(T.check_9d)
    assert r.failed and 'undeclared' in r.failed[0][1] and 'no longer computed' in r.failed[0][1]


def test_a_hand_edited_count_is_caught_and_written_back():
    doc = T.plan_doc('02-taxonomy.md')
    m = T.HEADING.search(doc)                                     # the first counted heading, whatever it says
    wrong = 'twenty' if m.group(3) != 'twenty' else 'nineteen'
    edited = doc[:m.start(3)] + wrong + doc[m.end(3):]
    assert run(T.check_9b_document, edited).failed
    assert T.sync_02(edited) == doc


def test_a_field_term_states_both_tests_or_neither():
    base = {'id': 'fully-open', 'label': 'Fully open', 'status': 'proposed', 'introduced_in': '1.0.0',
            'field': 'data.access', 'definition': 'Every split is public.'}
    FieldTerm.model_validate(base)
    FieldTerm.model_validate(dict(base, inclusion_test='Tag this if every split is public.',
                                  exclusion_test='Do NOT tag this if any split is gated.'))
    with pytest.raises(ValidationError, match='both'):
        FieldTerm.model_validate(dict(base, inclusion_test='Tag this if every split is public.'))
    with pytest.raises(ValidationError, match='operational'):
        FieldTerm.model_validate(dict(base, inclusion_test='Every split is public.',
                                      exclusion_test='Do NOT tag this if any split is gated.'))


# ---- 02 S3, the allocation table (P1-S1-T09) ---------------------------------------------------------------

def s3_row(doc, family):
    """(start, end) of `family`'s row in 02 S3's generated allocation table."""
    at = doc.index(T.S3_HEADER)
    start = doc.index('\n| %s | ' % family, at) + 1
    return start, doc.index('\n', start)


@pytest.mark.parametrize('family, cell, replacement', [
    ('physics', '| **18** |', '| **19** |'),                  # a seed target
    ('physics', '| 10 |', '| 11 |'),                          # the subdomain count
    ('code', '| not estimated ‡ |', '| 40 |'),          # inventing the estimate 02 S3 does not have
    ('vision', '| surveyed |', '| under-surveyed |'),         # coverage status
    ('vision', '| `hand-curate` |', '| `mixed` |'),           # posture
])
def test_a_hand_edited_02_s3_row_fails_and_a_regenerated_one_passes(family, cell, replacement):
    doc = T.plan_doc('02-taxonomy.md')
    a, b = s3_row(doc, family)
    row = doc[a:b]
    assert cell in row, row
    edited = doc[:a] + row.replace(cell, replacement, 1) + doc[b:]
    assert run(T.check_9b_document, edited).failed
    assert T.sync_02(edited) == doc                                # --write puts it back
    assert not run(T.check_9b_document, T.sync_02(edited)).failed


def test_the_02_s3_table_is_the_yaml_row_for_row():
    fams, subs = T.domain_terms()
    exp = T.expectations()
    rows = T._table_after(T.render_seed_table(fams, subs), T.S3_HEADER)
    assert set(rows) == {f['id'] for f in fams}
    for f in fams:
        cells = rows[f['id']]
        assert int(cells[1]) == sum(1 for s in subs if s['parent'] == f['id'])
        assert cells[3].startswith('**%d**' % f['seed_target'])
        assert cells[5] == f['coverage_status'] and cells[6] == '`%s`' % f['curation_posture']
        e = exp[f['id']]
        assert cells[2] == (str(e['tier1_expectation']) if e['sized'] else 'not estimated ‡')


def test_an_unsized_family_stays_not_estimated_and_never_gets_a_number():
    fams, subs = T.domain_terms()
    exp = T.expectations()
    unsized = sorted(f for f, e in exp.items() if not e['sized'])
    assert unsized == ['code', 'engineering-design', 'language', 'mathematics', 'multimodal', 'reasoning-general']
    table = T.render_seed_table(fams, subs, {k: v for k, v in exp.items() if k != 'physics'})   # no row at all
    assert '| physics | 10 | not estimated ‡ |' in table
    assert '| **280 across 12 estimated rows** |' in table


def test_the_dagger_is_computed_seed_equal_to_its_estimate():
    fams, subs = T.domain_terms()
    marked = [f for f, c in T._table_after(T.render_seed_table(fams, subs), T.S3_HEADER).items() if '†' in c[3]]
    assert sorted(marked) == ['audio-speech', 'general-intelligence', 'robotics-embodiment']


def test_the_hand_written_notes_table_must_have_one_row_per_family():
    doc = T.plan_doc('02-taxonomy.md')
    fams, _ = T.domain_terms()
    assert not run(T.check_9b_seed, fams, doc).failed
    at = doc.index(T.S3_NOTES_HEADER)
    start = doc.index('\n| physics | ', at) + 1
    dropped = doc[:start] + doc[doc.index('\n', start) + 1:]
    r = run(T.check_9b_seed, fams, dropped)
    assert r.failed and "no row for ['physics']" in r.failed[0][1]
    extra = doc[:start] + '| telepathy | 1 | 2 | Hand-curate. |\n' + doc[start:]
    r = run(T.check_9b_seed, fams, extra)
    assert r.failed and "['telepathy'], which is not a family" in r.failed[0][1]
