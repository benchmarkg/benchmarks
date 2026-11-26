"""The constructed dispute records tests/e2e/corrections.spec.ts builds the site from (P3-S10-T09; 05 S8).

The root playwright.config.ts points the site at tests/e2e/fixtures/disputes/ with UAIBI_DISPUTES. The page reads
them as it reads data/disputes/, through site/src/lib/corrections.ts, which checks only what it renders; bench
validate holds data/disputes/ to schema/dispute.py, and this holds the fixtures to it too, so the e2e test never
passes over a record the real data could not contain. It also holds the fixtures to what the spec needs from them:
every status, a raiser the page must name and raisers it must not, and the one dispute the feed fixture's correction
names in its Correction: trailer.
"""
import json
import os

import pytest
from ruamel.yaml import YAML

from schema.dispute import Dispute

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(ROOT, 'tests', 'e2e', 'fixtures')
DIR = os.path.join(FIXTURES, 'disputes')
FILES = sorted(n for n in os.listdir(DIR) if n.endswith('.yaml'))


def load(name):
    with open(os.path.join(DIR, name), encoding='utf-8') as f:
        return YAML(typ='safe', pure=True).load(f)


@pytest.mark.parametrize('name', FILES)
def test_each_fixture_is_a_valid_dispute_named_by_its_id(name):
    d = Dispute.model_validate(load(name))
    assert name == '%s.yaml' % d.id
    assert d.position.startswith('A constructed position'), 'a fixture says it is constructed'


def test_the_fixtures_cover_what_the_spec_asserts():
    ds = [Dispute.model_validate(load(n)) for n in FILES]
    assert {d.status for d in ds} == {'open', 'resolved-claim-corrected', 'resolved-claim-retained', 'withdrawn'}
    assert sum(d.is_standing for d in ds) >= 2
    raisers = {d.raised_by for d in ds}
    assert 'redacted' in raisers and any(r.startswith('org-') for r in raisers)
    assert any(not r.startswith('org-') and r != 'redacted' for r in raisers)
    with open(os.path.join(FIXTURES, 'feed-events.json'), encoding='utf-8') as f:
        named = {i for e in json.load(f) if e['type'] == 'correction' for i in e.get('disputes', [])}
    assert named and named <= {d.id for d in ds}, 'every dispute a fixture correction names is a fixture'
