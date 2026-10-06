"""`bench promote`, `bench resolve` and `bench tag-gap` (P1-S2-T10; 05 S3, S4, S5).

The verify: "promotion without the required evidence exits non-zero, promotion to expert-reviewed with no reviewer
is refused, resolve reproduces the hand-labelled fixture verdicts, and tag-gap appends a row without rewriting
history". Promote and tag-gap write, so they run in a temporary tree holding one real entry (paperbench) and the
two Source records it cites; the CLI tests point tools.cli at that tree.
"""
import datetime
import glob
import os
import shutil
import sys

import pytest
from typer.testing import CliRunner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools import cli, dedup, promote, resolve, tag_gap  # noqa: E402
from tools.validate import tiers  # noqa: E402

ENTRY = 'data/benchmarks/agents-tooluse/paperbench.yaml'
ABS, HTML = 'src-paperbench-arxiv-abs', 'src-paperbench-arxiv-html'
AUTHOR = 'agent (P0-S8-T07)'
TODAY = datetime.date(2026, 10, 6)
runner = CliRunner()


@pytest.fixture
def tree(tmp_path, monkeypatch):
    def put(rel):
        os.makedirs(tmp_path / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), tmp_path / rel)
    put(ENTRY)
    for sid in (ABS, HTML):
        put(os.path.relpath(glob.glob(os.path.join(ROOT, 'data', 'sources', '**', sid + '.yaml'), recursive=True)[0],
                            ROOT).replace(os.sep, '/'))
    for f in ['taxonomy/VERSION'] + [os.path.relpath(p, ROOT).replace(os.sep, '/')
                                     for p in glob.glob(os.path.join(ROOT, 'taxonomy', '*.yaml'))]:
        put(f)                                 # the vocabularies the validator reads; not the _failures/ log
    monkeypatch.setattr(cli, 'ROOT', str(tmp_path))
    return tmp_path


def status(tree):
    from schema.taxonomy import read_yaml
    return read_yaml(str(tree / ENTRY))['curation']['verification_status']


def bench(*args):
    return runner.invoke(cli.app, list(args))


def schema_findings(tree, rel):
    return [f for f in tiers.single(str(tree / rel), 'schema', str(tree)).findings if f.severity == 'error']


# ---- promote: the verify's two refusals ---------------------------------------------------------------------

@pytest.mark.parametrize('evidence, why', [
    ([], 'Missing option'),                                             # no evidence at all
    (['src-not-a-source'], 'not a Source record'),
])
def test_promotion_without_the_required_evidence_exits_non_zero(tree, evidence, why):
    args = ['promote', ENTRY, '--to', 'curator-reviewed', '--by', 'reviewer-a'] + sum([['--evidence', e] for e in evidence], [])
    r = bench(*args)
    assert r.exit_code != 0 and why in r.output
    assert status(tree) == 'ai-drafted-unverified' and not (tree / 'data' / '_curation').exists()


def test_evidence_must_be_a_source_the_record_cites(tree):
    other = tree / 'data' / 'sources' / '2026' / 'src-unrelated.yaml'
    shutil.copy(next(iter(glob.glob(str(tree / 'data' / 'sources' / '**' / (ABS + '.yaml')), recursive=True))), other)
    r = bench('promote', ENTRY, '--to', 'curator-reviewed', '--by', 'reviewer-a', '--evidence', 'src-unrelated')
    assert r.exit_code == 1 and 'not one of the sources' in r.output


def test_primary_source_verified_needs_every_cited_source_opened(tree):
    r = bench('promote', ENTRY, '--to', 'primary-source-verified', '--by', 'reviewer-a', '--evidence', ABS)
    assert r.exit_code == 1 and 'does not cover %s' % HTML in r.output
    assert status(tree) == 'ai-drafted-unverified'


def test_promotion_to_expert_reviewed_with_no_reviewer_is_refused(tree):
    r = bench('promote', ENTRY, '--to', 'expert-reviewed', '--by', 'reviewer-a', '--evidence', ABS, '--evidence', HTML)
    assert r.exit_code == 1 and 'name them with --reviewer' in r.output
    assert status(tree) == 'ai-drafted-unverified' and not (tree / 'data' / '_curation').exists()
    r = bench('promote', ENTRY, '--to', 'expert-reviewed', '--by', 'reviewer-a', '--evidence', ABS, '--evidence', HTML,
              '--reviewer', 'Dr Example, domain expert')
    assert r.exit_code == 0, r.output
    assert status(tree) == 'expert-reviewed'


# ---- promote: the other preconditions ----------------------------------------------------------------------

@pytest.mark.parametrize('to, why', [
    ('machine-ingested', 'only an ingestion adapter'),
    ('ai-drafted-unverified', 'never makes a record a draft'),
    ('peer-reviewed', 'not a rung of the ladder'),
])
def test_promotion_is_only_up_the_ladder_to_a_rung_a_person_can_give(tree, to, why):
    r = bench('promote', ENTRY, '--to', to, '--by', 'reviewer-a', '--evidence', ABS)
    assert r.exit_code == 1 and why in r.output


def test_the_author_cannot_promote_their_own_record(tree):
    r = bench('promote', ENTRY, '--to', 'curator-reviewed', '--by', AUTHOR, '--evidence', ABS)
    assert r.exit_code == 1 and 'not the author' in r.output


def test_promote_never_lowers_or_repeats(tree):
    assert bench('promote', ENTRY, '--to', 'curator-reviewed', '--by', 'reviewer-a', '--evidence', ABS).exit_code == 0
    for to in ('curator-reviewed',):
        r = bench('promote', ENTRY, '--to', to, '--by', 'reviewer-b', '--evidence', ABS)
        assert r.exit_code == 1 and 'promote only raises it' in r.output


def test_a_draft_is_not_promoted_in_place(tree):
    with pytest.raises(promote.PromotionError, match='leaves drafts/ in a reviewed PR'):
        promote.plan('drafts/benchmarks/x.yaml', 'curator-reviewed', [ABS], 'reviewer-a', root=str(tree))


def test_a_promotion_changes_two_lines_and_records_who_when_and_against_what(tree):
    before = (tree / ENTRY).read_text(encoding='utf-8').split('\n')
    written = promote.promote([ENTRY], 'curator-reviewed', [ABS], 'reviewer-a', note='read it', root=str(tree), today=TODAY)
    rec = 'data/_curation/promotions/2026-10-06-paperbench-001.yaml'
    assert written == [rec, ENTRY]
    after = (tree / ENTRY).read_text(encoding='utf-8').split('\n')
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and changed == [
        ('  last_verified: 2026-09-27', '  last_verified: 2026-10-06'),
        ('  verification_status: ai-drafted-unverified', '  verification_status: curator-reviewed')]
    from schema.taxonomy import read_yaml
    doc = read_yaml(str(tree / rec))
    assert (doc['from'], doc['to'], doc['by'], str(doc['on']), doc['evidence'], doc['note']) == \
        ('ai-drafted-unverified', 'curator-reviewed', 'reviewer-a', '2026-10-06', [ABS], 'read it')
    assert schema_findings(tree, rec) == [] and schema_findings(tree, ENTRY) == []


def test_the_promotion_log_is_append_only(tree):
    promote.promote([ENTRY], 'curator-reviewed', [ABS], 'reviewer-a', root=str(tree), today=TODAY)
    first = (tree / 'data/_curation/promotions/2026-10-06-paperbench-001.yaml').read_bytes()
    promote.promote([ENTRY], 'primary-source-verified', [ABS, HTML], 'reviewer-b', root=str(tree), today=TODAY)
    assert (tree / 'data/_curation/promotions/2026-10-06-paperbench-001.yaml').read_bytes() == first
    assert (tree / 'data/_curation/promotions/2026-10-06-paperbench-002.yaml').exists()
    assert status(tree) == 'primary-source-verified'


def test_one_refusal_among_several_paths_writes_nothing(tree):
    with pytest.raises(promote.PromotionError):
        promote.promote([ENTRY, 'data/benchmarks/nope.yaml'], 'curator-reviewed', [ABS], 'reviewer-a', root=str(tree))
    assert status(tree) == 'ai-drafted-unverified' and not (tree / 'data' / '_curation').exists()


def test_a_promotion_record_is_held_to_its_name_by_the_validator(tree):
    promote.promote([ENTRY], 'curator-reviewed', [ABS], 'reviewer-a', root=str(tree), today=TODAY)
    src = tree / 'data/_curation/promotions/2026-10-06-paperbench-001.yaml'
    bad = tree / 'data/_curation/promotions/2026-10-07-paperbench-001.yaml'
    shutil.copy(src, bad)
    assert any('is named for' in f.message for f in tiers.single(str(bad), 'schema', str(tree)).findings)


# ---- resolve ------------------------------------------------------------------------------------------------

def test_resolve_reproduces_the_hand_labelled_fixture_verdicts():
    cfg = resolve.config()
    verdicts = resolve.resolve_pairs(dedup.PAIRS, cfg)
    chosen = cfg['calibration']['chosen']
    assert len(verdicts) == 200
    # every pair it proposes gets its label exactly: same is same, variant-of is variant-of
    assert all(v.agrees for v in verdicts if v.verdict != 'distinct')
    # every pair labelled distinct is distinct, and its only misses are the calibration's recorded false negatives
    missed = [v for v in verdicts if not v.agrees]
    assert all(v.verdict == 'distinct' and v.label in ('same', 'variant-of') for v in missed)
    assert len(missed) == chosen['fn'] and resolve.agreement(verdicts)['agree'] == chosen['tp'] + chosen['tn']
    assert {v.label for v in verdicts if v.verdict == 'same'} == {'same'}
    assert sum(v.verdict == 'same' for v in verdicts) == cfg['calibration']['labels']['same']


def test_resolve_cli_gives_the_agreement_and_writes_nothing(tree):
    r = bench('resolve', '--pairs', dedup.PAIRS)
    assert r.exit_code == 0 and '181 of 200 labelled pairs agree at cosine 0.95' in r.output
    lines = r.output.splitlines()
    assert sum(l.startswith('same ') for l in lines) == 45 and sum(l.startswith('variant-of ') for l in lines) == 58
    assert not (tree / 'data' / '_curation').exists()


def test_a_lower_threshold_proposes_more_and_a_bad_one_is_refused():
    loose = resolve.resolve_pairs(dedup.PAIRS, resolve.config(0.10))
    calibrated = resolve.resolve_pairs(dedup.PAIRS, resolve.config())
    assert sum(v.verdict != 'distinct' for v in loose) > sum(v.verdict != 'distinct' for v in calibrated)
    assert bench('resolve', '--threshold', '1.5').exit_code == 2


def test_resolve_never_merges():
    import inspect
    src = inspect.getsource(resolve)
    assert 'open(' not in src and '.write' not in src


# ---- tag-gap ------------------------------------------------------------------------------------------------

def test_tag_gap_appends_a_row_without_rewriting_history(tree):
    r = bench('tag-gap', '--benchmark', 'paperbench', '--facet', 'data.access', '--by', 'reviewer-a',
              '--note', 'The paper does not say whether the rubrics are public.')
    assert r.exit_code == 0, r.output
    first_rel = r.output.split('wrote ')[1].strip()
    assert first_rel.startswith('taxonomy/_failures/') and first_rel.endswith('-paperbench-001.yaml')
    first = (tree / first_rel).read_bytes()
    r = bench('tag-gap', '--benchmark', 'paperbench', '--facet', 'evaluation_method', '--by', 'reviewer-a',
              '--kind', 'missing-term', '--note', 'Rubric grading by an LLM judge has no term.', '--proposed-term', 'rubric-judge')
    assert r.exit_code == 0, r.output
    assert r.output.split('wrote ')[1].strip().endswith('-paperbench-002.yaml')
    assert (tree / first_rel).read_bytes() == first                 # history is never rewritten
    assert schema_findings(tree, first_rel) == []
    from schema.taxonomy import read_yaml
    doc = read_yaml(str(tree / first_rel))
    assert (doc['kind'], doc['facet'], doc['benchmark'], doc['blocking']) == ('source-silent', 'data.access', 'paperbench', False)


def test_tag_gap_opens_no_existing_file_for_writing(tree, monkeypatch):
    rel = tag_gap.tag_gap('paperbench', 'data.access', 'one', 'reviewer-a', on=TODAY, root=str(tree))
    monkeypatch.setattr(tag_gap, 'next_path', lambda *a, **k: rel)     # a stale count must not overwrite
    with pytest.raises(FileExistsError):
        tag_gap.tag_gap('paperbench', 'data.access', 'two', 'reviewer-a', on=TODAY, root=str(tree))
    assert 'one' in (tree / rel).read_text(encoding='utf-8')


@pytest.mark.parametrize('kw, why', [
    (dict(benchmark='no-such-benchmark'), 'no benchmark'),
    (dict(facet='colour'), 'not a classified field'),
    (dict(note='   '), 'says what could not be expressed'),
    (dict(kind='vibes'), 'is not one of'),
])
def test_tag_gap_refuses_what_it_cannot_record(tree, kw, why):
    args = dict(benchmark='paperbench', facet='data.access', note='n', by='reviewer-a')
    args.update(kw)
    with pytest.raises(tag_gap.TagGapError, match=why):
        tag_gap.tag_gap(root=str(tree), **args)
    assert not (tree / 'taxonomy' / '_failures').exists()
