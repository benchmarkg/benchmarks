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
