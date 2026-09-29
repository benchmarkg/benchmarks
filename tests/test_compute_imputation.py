"""Imputed training compute, and the System and Organization stubs that carry it (P3-S3-T04; 04 S7, 07 S5).

VERIFY: "pytest tests/test_compute_imputation.py -q asserting every row whose upstream notes contain
"imputed" carries training_compute_estimated: true." DONE WHEN: "The entities validate, imputed compute is
flagged so 12's compute-vs-capability plots can exclude it, and no entity was created from a result row."

04 S7 names the trap: Epoch's notes separate honest arithmetic from compute "imputed ... from benchmark
scores", and the second must never be plotted against benchmark scores. The committed corpus is checked
where epochdl/ is present (it is gitignored, 00 S8.1); a synthetic export in tmp_path exercises every rule,
including the failure case, on any machine.
"""
import csv
import glob
import os
import sys

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import emit_epoch_entities as E  # noqa: E402
from schema.stub import OrganizationStub, SystemStub, stub_files  # noqa: E402
from tools.build import artifacts  # noqa: E402
from tools.validate import tiers  # noqa: E402

SAFE = YAML(typ='safe', pure=True)
HAVE_EPOCH = os.path.exists(os.path.join(E.EPOCH, 'model_metadata.csv'))
needs_epoch = pytest.mark.skipif(not HAVE_EPOCH, reason='epochdl/ is not in the working tree (00 S8.1)')


def load(path):
    with open(path, encoding='utf-8') as fh:
        return SAFE.load(fh)


SYSTEMS = {os.path.basename(p)[:-5]: load(p) for p in stub_files(ROOT, 'systems')}


# ---- the committed corpus -------------------------------------------------------------------------

@needs_epoch
def test_every_row_whose_notes_say_imputed_carries_estimated_true():
    registry = {r['model_version']: r for r in csv.DictReader(open(os.path.join(E.EPOCH, 'model_metadata.csv'),
                                                                   encoding='utf-8')) if r['model_version']}
    by_group = {g: s for s in SYSTEMS.values() for g in s['epoch']['model_groups']}
    checked = 0
    for path in sorted(glob.glob(os.path.join(E.EPOCH, '*.csv'))):
        with open(path, encoding='utf-8', errors='replace', newline='') as fh:
            rows = list(csv.DictReader(fh))
        if not rows or 'Training compute notes' not in rows[0]:
            continue
        mv = next(c for c in rows[0] if c.strip().lower() == 'model version')
        for r in rows:
            note = (r['Training compute notes'] or '').strip()
            if 'imputed' not in note.lower() and 'imputation' not in note.lower():
                continue
            stub = by_group[registry[r[mv]]['model_group']]
            assert stub['training_compute_estimated'] is True, stub['id']
            assert stub['training_compute_notes'] == note                     # verbatim
            assert stub['training_compute_flop'] > 0
            checked += 1
    assert checked > 0


@needs_epoch
def test_the_committed_stubs_are_exactly_the_emitters_output():
    files = E.emit()
    for rel, text in files.items():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
            assert fh.read() == text, rel
    held = {os.path.relpath(p, ROOT) for k in ('systems', 'organizations') for p in stub_files(ROOT, k)}
    assert held == {r for r in files if '_stubs' in r}


def test_the_five_imputed_groups_are_flagged_and_their_figures_come_from_the_notes():
    imputed = {sid: s for sid, s in SYSTEMS.items() if 'imput' in (s['training_compute_notes'] or '').lower()}
    assert sorted(imputed) == ['gemini-1-5-pro-feb-2024', 'gemini-1-5-pro-may-2024', 'gemini-1-5-pro-sept-2024',
                               'gpt-4-turbo-apr-2024', 'gpt-4-turbo-nov-2023']
    for s in imputed.values():
        assert s['training_compute_estimated'] is True and s['training_compute_from'] == 'notes'
    assert {s['training_compute_flop'] for s in imputed.values()} == {1.58e25, 2.2e25}
    # nothing else is marked estimated: whether Epoch's other figures were disclosed is the curator's call
    assert not [sid for sid, s in SYSTEMS.items() if s['training_compute_estimated'] and sid not in imputed]


def test_the_stubs_validate_unpublished_with_every_identity_awaiting_review():
    report = tiers.run(ROOT, 'all', paths=['data/systems/', 'data/organizations/'])
    assert not report.blocking
    unreviewed = {f.entity for f in report.findings if f.rule == 'stub-identity-unreviewed'}
    orgs = {os.path.basename(p)[:-5] for p in stub_files(ROOT, 'organizations')}
    assert unreviewed == set(SYSTEMS) | orgs
    result = artifacts.build(ROOT)
    published = {k: {r['id'] for r in v} for k, v in result.corpus['entities'].items()}
    assert not published['system'] & set(SYSTEMS) and not published['organization'] & orgs


def test_curated_entries_get_no_stub():
    assert 'claude-3-5-sonnet' not in SYSTEMS                               # data/systems/claude-3-5-sonnet.yaml
    assert not os.path.exists(os.path.join(ROOT, 'data', 'organizations', '_stubs', 'org-anthropic.yaml'))


# ---- the rules, on a synthetic export --------------------------------------------------------------

REGISTRY = ['model_version,model_group,date,display_name,organization,country,accessibility,training_compute_flop',
            ',,,,,,,',                                                     # line 2: blank -> Unresolved
            ',Orphan Group,2025-01-01,,,,,',                                 # line 3: no version -> Unresolved
            'imp-1,Imputed (May 2024),2024-05-14,,Acme,United States of America,API access,',
            'imp-2,Imputed (Sept 2024),2024-09-24,,Acme,United States of America,API access,',
            'arith-1,Arithmetic,2025-01-20,,Acme Labs,China,Open weights (unrestricted),3.5e+24',
            'case-a,Sonar,2025-01-01,,Acme,,API access,',
            'case-b,sonar,2025-02-01,,Acme,,API access,',
            'joint-1,Joint,2025-03-01,,"Acme,Beta University",,,']
RESULTS = ['Model version,Score,Training compute notes',
           'imp-1,0.5,Training compute imputed to be 1.58e25 FLOP from benchmark scores.',
           'imp-2,0.6,Training compute estimated to be 2.2e25 FLOP using benchmark imputation.',
           'arith-1,0.7,"3.29e24 + 1.8e23 = 3.47e24, round to 3.5e24"',
           'not-in-registry,0.9,Training compute imputed to be 9e25 FLOP from benchmark scores.']


@pytest.fixture
def synthetic(tmp_path):
    epoch, root = tmp_path / 'epochdl', tmp_path / 'repo'
    epoch.mkdir()
    (root / 'data' / 'systems').mkdir(parents=True)
    (root / 'data' / 'organizations').mkdir(parents=True)
    (epoch / 'model_metadata.csv').write_text('\n'.join(REGISTRY) + '\n', encoding='utf-8')
    (epoch / 'some_benchmark_external.csv').write_text('\n'.join(RESULTS) + '\n', encoding='utf-8')
    files = E.emit(str(epoch), str(root))
    stubs = {os.path.basename(p)[:-5]: SAFE.load(t) for p, t in files.items() if '_stubs' in p}
    return files, stubs


def test_imputed_notes_flag_the_figure_and_arithmetic_notes_do_not(synthetic):
    _, stubs = synthetic
    for sid, flop in (('imputed-may-2024', 1.58e25), ('imputed-sept-2024', 2.2e25)):
        s = stubs[sid]
        assert (s['training_compute_flop'], s['training_compute_estimated'], s['training_compute_from']) == \
            (flop, True, 'notes')
    a = stubs['arithmetic']
    assert (a['training_compute_flop'], a['training_compute_estimated'], a['training_compute_from']) == \
        (3.5e24, None, 'model_metadata')
    assert a['training_compute_notes'].startswith('3.29e24 + 1.8e23')


def test_no_entity_comes_from_a_result_row_and_unidentifiable_rows_are_unresolved(synthetic):
    files, stubs = synthetic
    assert not [s for s in stubs.values() if 'not-in-registry' in str(s)]   # the result-only string makes nothing
    unresolved = SAFE.load(files[E.UNRESOLVED])
    assert [(u['source_key'], u['observed']) for u in unresolved] == [('model_metadata.csv#row-2', ''),
                                                                     ('model_metadata.csv#row-3', 'Orphan Group')]
    assert 'orphan-group' not in stubs


def test_case_only_spellings_are_one_stub_and_joint_organisations_split(synthetic):
    _, stubs = synthetic
    assert stubs['sonar']['aliases'] == ['sonar'] and len(stubs['sonar']['epoch']['versions']) == 2
    assert 'differing only in case' in stubs['sonar']['identity']['note']
    assert stubs['joint']['organizations'] == ['org-acme', 'org-beta-university']
    assert {'org-acme', 'org-acme-labs', 'org-beta-university'} <= set(stubs)
    assert 'Acme Labs' in stubs['org-acme']['identity']['note']            # a near-name to review
    assert 'imputed-sept-2024' in stubs['imputed-may-2024']['identity']['note']   # likely versions of one system


def test_the_model_refuses_imputed_compute_that_is_not_marked_estimated():
    """The failure case: imputed notes with estimated anything but true must not load."""
    base = dict(SYSTEMS['gpt-4-turbo-nov-2023'])
    for bad in (None, False):
        with pytest.raises(ValidationError, match='imputed'):
            SystemStub.model_validate({**base, 'training_compute_estimated': bad})
    with pytest.raises(ValidationError, match='from the notes'):
        SystemStub.model_validate({**base, 'training_compute_notes': 'Estimated from parameters and tokens.'})
    SystemStub.model_validate(base)


def test_a_stub_with_a_fact_epoch_does_not_state_is_not_a_stub():
    with pytest.raises(ValidationError):
        SystemStub.model_validate({**SYSTEMS['gpt-4-turbo-nov-2023'], 'availability': 'generally-available'})
    org = load(stub_files(ROOT, 'organizations')[0])
    with pytest.raises(ValidationError):
        OrganizationStub.model_validate({**org, 'kind': 'company'})
