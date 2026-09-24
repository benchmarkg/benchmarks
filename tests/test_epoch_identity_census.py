"""Tests for scripts/epoch_identity_census.py over tests/fixtures/epochdl-mini/.

Hand counts, read off the fixture files (see that directory's README for the rows):
  model_groups 5 (Model A-E; the all-blank row has none)
  registry_versions 5 (model-a_high, model-a_low, model-b, model-c, model-e)
  result_versions 8 (a_high, a_low, b, c, d, e, f, g; mmlu's blank version is excluded)
  result_versions_joined 5, unused_registry 0 -- d, f and g are in results but not the registry
  org_strings 1 and organisations 1 (Fixture Org); effort_suffix_rows 4
  (gpqa a_high + a_low, swe a_high, mmlu a_high)
"""
import importlib.util
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'epochdl-mini')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
spec = importlib.util.spec_from_file_location('epoch_identity_census',
                                              os.path.join(ROOT, 'scripts', 'epoch_identity_census.py'))
eic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eic)

HAND = {'model_groups': 5, 'registry_versions': 5, 'result_versions': 8, 'result_versions_joined': 5,
        'unused_registry': 0, 'org_strings': 1, 'organisations': 1, 'effort_suffix_rows': 4}


def test_the_census_reproduces_the_hand_counts():
    c = eic.census(FIXTURE)
    assert c['figures'] == HAND
    assert c['unjoined'] == ['model-d', 'model-f', 'model-g']


def test_every_plan_figure_has_a_hand_count():
    assert set(HAND) == set(eic.EXPECTED)


def test_a_joint_organization_is_one_string_but_two_organisations(tmp_path):
    cut = tmp_path / 'cut'
    shutil.copytree(FIXTURE, cut)
    p = cut / 'model_metadata.csv'
    p.write_text(p.read_text(encoding='utf-8').replace(
        'model-e,Model E,2026-01-01,Model E,Fixture Org,', 'model-e,Model E,2026-01-01,Model E,"Fixture Org,Second Lab",'),
        encoding='utf-8')
    c = eic.census(str(cut))
    assert (c['figures']['org_strings'], c['figures']['organisations']) == (2, 2)
    assert c['split_only'] == ['Second Lab'] and c['joint_strings'] == [('Fixture Org,Second Lab', 1)]


def test_check_fails_when_a_figure_moves(capsys):
    assert eic.main(['--dir', FIXTURE, '--check']) == 1  # the fixture is not the 1,063-row registry
    assert 'DIFF model_groups' in capsys.readouterr().out


def test_a_missing_export_exits_2(tmp_path, capsys):
    assert eic.main(['--dir', str(tmp_path / 'nope'), '--check']) == 2
    assert 'epoch_audit.py --fetch' in capsys.readouterr().err


def test_the_report_is_deterministic(tmp_path):
    a, b = tmp_path / 'a.md', tmp_path / 'b.md'
    eic.main(['--dir', FIXTURE, '--report', str(a)])
    eic.main(['--dir', FIXTURE, '--report', str(b)])
    assert a.read_bytes() == b.read_bytes()
