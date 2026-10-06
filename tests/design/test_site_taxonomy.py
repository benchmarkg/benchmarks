"""Tests for tools/build/site_taxonomy.py, the taxonomy terms the site's components resolve (P2-S2-T06; 09 S6.2).

FacetChip throws on a term that is not in site/src/lib/taxonomy.json, so that file has to be taxonomy/ exactly:
committed as the generator's output, carrying every facet file's every term, and the verification ladder in rank
order for VerificationBadge's segments.
"""
import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.build import site_taxonomy as S  # noqa: E402
from tools.build.tokens import load_yaml, rungs  # noqa: E402

COMMITTED = os.path.join(ROOT, S.OUT)


def committed():
    with open(COMMITTED, encoding='utf-8') as f:
        return json.load(f)


def test_the_committed_file_is_the_generators_output():
    assert not S.stale(), 'site/src/lib/taxonomy.json is stale: run `python tools/build/site_taxonomy.py`'


def test_every_facet_file_and_every_term_is_carried():
    doc = committed()
    seen = 0
    for name in sorted(os.listdir(os.path.join(ROOT, 'taxonomy'))):
        if not name.endswith('.yaml'):
            continue
        y = load_yaml(os.path.join(ROOT, 'taxonomy', name))
        if not isinstance(y, dict) or 'facet' not in y or 'terms' not in y:
            continue
        seen += 1
        assert {t['id']: t['label'] for t in y['terms']} == {k: v['label'] for k, v in doc['facets'][y['facet']].items()}
    assert seen == len(doc['facets']) >= 10


def test_the_ladder_is_in_rank_order():
    assert committed()['verification'] == rungs(ROOT) and len(rungs(ROOT)) == 7


def test_a_term_added_to_the_taxonomy_makes_the_committed_file_stale(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    (tmp_path / 'site' / 'src' / 'lib').mkdir(parents=True)
    S.write(str(tmp_path))
    assert not S.stale(str(tmp_path))
    with open(tmp_path / 'taxonomy' / 'lifecycle.yaml', 'a', encoding='utf-8') as f:
        f.write('  - id: zombie\n    label: Zombie\n    field: lifecycle\n')
    assert S.stale(str(tmp_path))
    S.write(str(tmp_path))
    with open(tmp_path / S.OUT, encoding='utf-8') as f:
        assert json.load(f)['facets']['lifecycle']['zombie'] == {'label': 'Zombie'}


def test_two_files_declaring_one_facet_is_an_error(tmp_path):
    shutil.copytree(os.path.join(ROOT, 'taxonomy'), tmp_path / 'taxonomy')
    shutil.copy(tmp_path / 'taxonomy' / 'lifecycle.yaml', tmp_path / 'taxonomy' / 'lifecycle-copy.yaml')
    with pytest.raises(ValueError, match='facet lifecycle is declared by two files'):
        S.generate(str(tmp_path))
