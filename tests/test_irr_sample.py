"""Tests for taxonomy/_irr/sample.yaml and scripts/irr_sample.py (P1-S14-T01; 03 S6.1).

The verify: the four done_when properties are re-derived here from the sample and the stress corpus, without the
script -- 30 items, all 18 corpus families present, at least 6 of the 10 stress tests, no stored tags -- and
`scripts/irr_sample.py --check` is shown to fail on a mutated copy for each of the four, with that property's own
message, so its drift comparison alone cannot be what catches them.
"""
import collections
import os
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, 'taxonomy', '_irr', 'sample.yaml')
SCRIPT = os.path.join(ROOT, 'scripts', 'irr_sample.py')
CORPUS = yaml.safe_load(open(os.path.join(ROOT, 'taxonomy', '_corpus', 'stress-corpus.yaml'),
                             encoding='utf-8'))['entries']
BY_ID = {x['id']: x for x in CORPUS}
TAGS = {'domain_family', 'stress_test', 'allocation_slot', 'description', 'flags', 'domain', 'capability',
        'evaluation_method', 'designed_for_subjects', 'lifecycle', 'facets'}


def sample():
    with open(SAMPLE, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


# ---- the four properties, re-derived -------------------------------------------------------------------------

def test_thirty_distinct_corpus_items():
    ids = [x['id'] for x in sample()['items']]
    assert len(ids) == 30 == len(set(ids)) and set(ids) <= set(BY_ID)


def test_every_corpus_family_appears():
    families = {x['domain_family'] for x in CORPUS}
    assert len(families) == 18 and 'engineering-design' not in families                 # 03 S6.1: 18 of 19
    assert {BY_ID[x['id']]['domain_family'] for x in sample()['items']} == families


def test_at_least_six_of_the_ten_stress_tests():
    assert sum(1 for x in CORPUS if x.get('stress_test') is True) == 10
    assert sum(1 for x in sample()['items'] if BY_ID[x['id']].get('stress_test') is True) >= 6


def test_no_stored_tags_ship_with_an_item():
    for item in sample()['items']:
        assert set(item) == {'id', 'name', 'links'}, item['id']
        assert not set(item) & TAGS
        assert all(set(link) <= {'kind', 'url', 'arxiv_id', 'doi'} for link in item['links'])
        assert item['links'] and all(link['url'].startswith('http') for link in item['links'])


def test_options_carry_definitions_and_no_examples():
    doc = sample()
    for name, options in doc['vocabularies'].items():
        assert options, name
        for o in options:
            assert {'id', 'label', 'definition'} <= set(o) <= {'id', 'label', 'definition', 'inclusion_test',
                                                               'exclusion_test'}, (name, o['id'])
    assert 'saturated' not in {o['id'] for o in doc['vocabularies']['lifecycle']}         # derived, never tagged
    assert {f['vocabulary'] for f in doc['facets']} == set(doc['vocabularies'])


def test_the_item_and_option_orders_are_shuffled():
    doc = sample()
    ids = [x['id'] for x in doc['items']]
    assert ids != sorted(ids)
    caps = [o['id'] for o in doc['vocabularies']['capabilities']]
    assert caps != sorted(caps)


# ---- --check against mutated copies --------------------------------------------------------------------------

def check(path):
    r = subprocess.run([sys.executable, SCRIPT, '--check', '--sample', str(path)], capture_output=True, text=True,
                       encoding='utf-8')
    return r.returncode, r.stdout


def one_item_short(doc):
    doc['items'].pop()


def one_family_dropped(doc):
    count = collections.Counter(BY_ID[x['id']]['domain_family'] for x in doc['items'])
    i, item = next((i, x) for i, x in enumerate(doc['items'])
                   if count[BY_ID[x['id']]['domain_family']] == 1 and not BY_ID[x['id']].get('stress_test'))
    held = {x['id'] for x in doc['items']}
    other = next(x for x in CORPUS if x['id'] not in held and not x.get('stress_test')
                 and count[x['domain_family']] > 1)
    doc['items'][i] = {'id': other['id'], 'name': other['name'], 'links': item['links']}


def one_stress_test_short(doc):
    held = {x['id'] for x in doc['items']}
    while sum(1 for x in doc['items'] if BY_ID[x['id']].get('stress_test')) >= 6:
        i, item = next((i, x) for i, x in enumerate(doc['items']) if BY_ID[x['id']].get('stress_test'))
        fam = BY_ID[item['id']]['domain_family']
        swap = next(x for x in CORPUS if x['id'] not in held and not x.get('stress_test')
                    and x['domain_family'] == fam)
        held.add(swap['id'])
        doc['items'][i] = {'id': swap['id'], 'name': swap['name'], 'links': item['links']}


def one_tag_restored(doc):
    doc['items'][0]['domain_family'] = BY_ID[doc['items'][0]['id']]['domain_family']


@pytest.mark.parametrize('mutate, message', [
    (one_item_short, '29 items, not 30'),
    (one_family_dropped, 'corpus families missing from the sample'),
    (one_stress_test_short, '5 stress tests, fewer than 6'),
    (one_tag_restored, 'carries a stored tag'),
], ids=['item-short', 'family-dropped', 'stress-short', 'tag-restored'])
def test_check_fails_on_each_mutation(tmp_path, mutate, message):
    doc = sample()
    mutate(doc)
    path = tmp_path / 'sample.yaml'
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')
    code, out = check(path)
    assert code != 0 and message in out, out


def test_check_passes_on_the_committed_sample(tmp_path):
    copy = tmp_path / 'sample.yaml'
    copy.write_bytes(open(SAMPLE, 'rb').read())
    assert check(copy) == (0, check(SAMPLE)[1]) and check(SAMPLE)[0] == 0
