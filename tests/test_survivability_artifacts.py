"""The survivability artifacts exist (P0-S7-T04; 05 S10, SUCCESSION.md).

The verify's second half: "the artifact test asserts LICENSE-DATA, LICENSE-CODE, REUSE.toml, CITATION.cff and
SUCCESSION.md all exist". A fork can continue the project only if these are present and say something, so
each must be a non-empty file at the repository root.
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS = ('LICENSE-DATA', 'LICENSE-CODE', 'REUSE.toml', 'CITATION.cff', 'SUCCESSION.md')


@pytest.mark.parametrize('name', ARTIFACTS)
def test_verify_the_survivability_artifact_exists_and_is_not_empty(name):
    path = os.path.join(ROOT, name)
    assert os.path.isfile(path), name
    with open(path, encoding='utf-8') as fh:
        assert fh.read().strip(), '%s is empty' % name


def test_succession_names_both_dormancy_triggers():
    with open(os.path.join(ROOT, 'SUCCESSION.md'), encoding='utf-8') as fh:
        text = fh.read()
    assert 'At 90 days without a human commit to `data/`' in text
    assert 'At 180 days without a human commit to `data/`' in text
