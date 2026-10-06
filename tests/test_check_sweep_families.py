"""Tests for scripts/check_sweep_families.py (P1-S12-T01; 06 S6).

The verify is `python scripts/check_sweep_families.py`; done-when is "the hub file's family list equals
the domain vocabulary exactly and the checklist is committed". Each test below builds a copy of the four
files the check reads, breaks one thing, and asserts the check names it.
"""
import os
import shutil

import pytest
import yaml

from scripts import check_sweep_families as csf

FILES = (csf.DOMAINS, csf.HUBS, csf.CHECKLIST, csf.PLAN_06)


@pytest.fixture
def tree(tmp_path):
    for rel in FILES:
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(csf.ROOT, rel), tmp_path / rel)
    return tmp_path


def errors(root):
    return csf.run(str(root))[2]


def edit_yaml(root, rel, fn):
    path = root / rel
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    fn(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')


def edit_text(root, rel, old, new):
    path = root / rel
    text = path.read_text(encoding='utf-8')
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')


def block(doc, family):
    return next(b for b in doc['families'] if b['family'] == family)


# ---- the verify ----------------------------------------------------------------------------------

def test_verify_the_repository_passes():
    assert csf.main(['--root', csf.ROOT]) == 0


def test_the_hub_file_lists_every_family_exactly_once():
    fams = csf.families(csf.ROOT)
    listed = [b['family'] for b in csf.hub_file(csf.ROOT)['families']]
    assert sorted(listed) == sorted(fams) and len(listed) == len(set(listed)) == len(fams)


def test_a_copied_tree_passes(tree):
    assert errors(tree) == []


# ---- the family list is the vocabulary, exactly -----------------------------------------------------

def test_a_family_missing_from_the_hub_file_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: d['families'].remove(block(d, 'physics')))
    assert any('no block for physics' in e for e in errors(tree))


def test_a_family_the_vocabulary_does_not_have_fails(tree):
    def add(d):
        extra = dict(block(d, 'physics'), family='alchemy')
        extra['hubs'] = [{'name': 'Philosopher', 'url': 'https://example.org/stone', 'mode': 'manual'}]
        d['families'].append(extra)
    edit_yaml(tree, csf.HUBS, add)
    assert any('alchemy, which is not a family' in e for e in errors(tree))


def test_a_family_listed_twice_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: d['families'].append(dict(block(d, 'code'), hubs=[])))
    assert any('lists code more than once' in e for e in errors(tree))


def test_a_twentieth_family_in_the_taxonomy_fails_in_the_same_commit(tree):
    edit_yaml(tree, csf.DOMAINS, lambda d: d['terms'].append(
        {'id': 'oceanography', 'label': 'Oceanography', 'parent': None, 'status': 'active'}))
    errs = errors(tree)
    assert any('no block for oceanography' in e for e in errs)
    assert any('06 S6 cadence table is not the domain vocabulary' in e for e in errs)
    assert any('effort table totals 19 families; the vocabulary has 20' in e for e in errs)


def test_subdomains_are_not_families():
    assert all('/' not in f for f in csf.families(csf.ROOT))


# ---- 06 S6 agrees -----------------------------------------------------------------------------------

def test_a_cadence_that_disagrees_with_06_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'physics').update(cadence='quarterly'))
    errs = errors(tree)
    assert any('physics: hubs.yaml says quarterly, 06 S6 says semi-annual' in e for e in errs)
    assert any('puts 5 families in the quarterly tier; hubs.yaml has 6' in e for e in errs)


def test_06_dropping_a_family_from_its_table_fails(tree):
    text = (tree / csf.PLAN_06).read_text(encoding='utf-8')
    row = next(l for l in text.splitlines() if l.startswith('| reasoning-general |'))
    edit_text(tree, csf.PLAN_06, row + '\n', '')
    assert any("missing ['reasoning-general']" in e for e in errors(tree))


def test_uncapping_vision_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'vision').pop('capped'))
    assert any('vision: 06 S6 calls it capped, hubs.yaml does not' in e for e in errors(tree))


def test_an_effort_table_that_miscounts_a_tier_fails(tree):
    edit_text(tree, csf.PLAN_06, '| Annual | 5 (', '| Annual | 4 (')
    assert any('puts 4 families in the annual tier; hubs.yaml has 5' in e for e in errors(tree))


def test_the_plan_parsers_read_what_06_says():
    text = open(os.path.join(csf.ROOT, csf.PLAN_06), encoding='utf-8').read()
    rows = {f: (c, capped) for f, c, capped in csf.plan_cadences(text)}
    assert rows['vision'] == ('quarterly', True)
    assert rows['engineering-design'] == ('annual', False)
    assert rows['audio-speech'] == ('semi-annual', False)
    assert csf.plan_tiers(text) == ({'quarterly': 5, 'semi-annual': 9, 'annual': 5}, 19)


# ---- the checklist is committed, and its table generated -------------------------------------------

def test_the_checklist_has_ten_lines_and_matches_06():
    text = open(os.path.join(csf.ROOT, csf.CHECKLIST), encoding='utf-8').read()
    plan = open(os.path.join(csf.ROOT, csf.PLAN_06), encoding='utf-8').read()
    body = csf.plan_checklist(plan)
    assert body in text
    assert sum(1 for l in body.splitlines() if l.strip().startswith('[ ]')) == csf.CHECKBOXES


def test_a_dropped_checklist_line_fails(tree):
    edit_text(tree, csf.CHECKLIST, '  [ ] archive_url present and CDX digest unchanged?                      -> re-archive if changed\n', '')
    errs = errors(tree)
    assert any('9 checklist lines, not 10' in e for e in errs)
    assert any("not 06 S6's, line for line" in e for e in errs)


def test_a_hand_edited_table_fails_and_write_repairs_it(tree):
    edit_text(tree, csf.CHECKLIST, '| code | quarterly | lineage | 4 |', '| code | annual | lineage | 4 |')
    assert any('stale or hand-edited' in e for e in errors(tree))
    assert csf.main(['--root', str(tree), '--write']) == 0
    assert errors(tree) == []


def test_a_hub_file_change_makes_the_table_stale_until_written(tree):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'code')['hubs'].append(
        {'name': 'Aider polyglot', 'url': 'https://aider.chat/docs/leaderboards/', 'mode': 'manual'}))
    assert any('stale or hand-edited' in e for e in errors(tree))
    csf.main(['--root', str(tree), '--write'])
    assert '| code | quarterly | lineage | 5 |' in (tree / csf.CHECKLIST).read_text(encoding='utf-8')
    assert errors(tree) == []


def test_write_refuses_without_markers(tree):
    edit_text(tree, csf.CHECKLIST, csf.BEGIN, '')
    with pytest.raises(SystemExit):
        csf.main(['--root', str(tree), '--write'])


def test_the_table_orders_by_tier_then_vocabulary():
    doc, fams = csf.hub_file(csf.ROOT), csf.families(csf.ROOT)
    rows = [l.split('|')[1].strip() for l in csf.render_table(doc, fams).splitlines()[2:] if l.startswith('| ')]
    tier = {b['family']: csf.CADENCES.index(b['cadence']) for b in doc['families']}
    assert rows == sorted(fams, key=lambda f: (tier[f], fams.index(f)))


# ---- hub well-formedness -------------------------------------------------------------------------

@pytest.mark.parametrize('hub, message', [
    ({'name': 'X', 'url': None, 'mode': 'manual'}, 'url is null and there is no note'),
    ({'name': 'X', 'url': 'http://example.org', 'mode': 'manual'}, 'is not an https URL'),
    ({'name': 'X', 'url': 'https://example.org', 'mode': 'scrape'}, "mode 'scrape' is not one of"),
    ({'name': 'X', 'mode': 'manual'}, 'no url key'),
    ({'name': '', 'url': 'https://example.org', 'mode': 'manual'}, 'a hub has no name'),
    ({'name': 'X', 'url': 'https://example.org', 'mode': 'manual', 'nots': 'typo'}, 'unknown key nots'),
])
def test_a_malformed_hub_fails(tree, hub, message):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'physics')['hubs'].append(hub))
    assert any(message in e for e in errors(tree)), errors(tree)


def test_a_url_listed_twice_in_a_family_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'physics')['hubs'].append(dict(block(d, 'physics')['hubs'][0])))
    assert any('is listed twice' in e for e in errors(tree))


@pytest.mark.parametrize('field, value, message', [
    ('cadence', 'monthly', "cadence 'monthly' is not one of"),
    ('focus', 'vibes', "focus 'vibes' is not one of"),
    ('catches', '', 'catches is empty'),
    ('capped', 'yes', 'capped must be true or false'),
])
def test_a_malformed_family_block_fails(tree, field, value, message):
    edit_yaml(tree, csf.HUBS, lambda d: block(d, 'physics').update({field: value}))
    assert any(message in e for e in errors(tree)), errors(tree)


def test_a_family_with_no_hub_at_all_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: d['shared_hubs'][0]['families'].remove('mathematics'))
    assert any('mathematics has no hub of its own and no shared hub serves it' in e for e in errors(tree))


def test_a_shared_hub_naming_an_unknown_family_fails(tree):
    edit_yaml(tree, csf.HUBS, lambda d: d['shared_hubs'][0]['families'].append('astrology'))
    assert any('names astrology, not a family' in e for e in errors(tree))


def test_the_shared_opencompass_hub_must_not_be_dropped():
    [hub] = [h for h in csf.hub_file(csf.ROOT)['shared_hubs'] if 'opencompass' in h['url']]
    assert hub['must_not_drop'] is True and hub['cadence'] == 'semi-annual'


def test_main_exits_non_zero_on_a_failure(tree, capsys):
    edit_yaml(tree, csf.HUBS, lambda d: d['families'].remove(block(d, 'physics')))
    assert csf.main(['--root', str(tree)]) == 1
    assert 'FAIL' in capsys.readouterr().out


# ---- asserted in CI ------------------------------------------------------------------------------

def test_ci_runs_the_check_as_a_blocking_job():
    with open(os.path.join(csf.ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        wf = yaml.safe_load(fh)
    job = wf['jobs']['sweep-families']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert any(r.endswith('python scripts/check_sweep_families.py') for r in runs), runs
    assert all('||' not in r and 'continue-on-error' not in s and 'if' not in s
               for s in job['steps'] for r in [s.get('run', '')])  # get-default: a uses: step has no run
