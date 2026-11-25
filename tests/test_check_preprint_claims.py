"""Tests for scripts/check_preprint_claims.py and docs/preprints/gap-matrix.md (P1-S14-T09; 12 S5.3-5.5, 14 Phase 1
"Publish the taxonomy and the gap analysis before the catalogue").

The verify: `python scripts/check_preprint_claims.py --preprint docs/preprints/gap-matrix.md --against
build/derived/gaps.json`. Done when "Every numeric claim in the preprint reproduces from gaps.json at the cited
commit." A small synthetic gaps.json and preprint show the check accepting bound, quoted and exempt numbers and
failing on an invented number, a figure off by one, a year, a density printed without its curation confidence and
a stale commit. The real preprint is checked for structure always, and against build/derived/gaps.json when that
artifact was built at the commit the preprint cites (it is pinned to one commit, so any other build fails on the
hash by design).
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_preprint_claims as C  # noqa: E402

SHA = ('0123456789abcdef' * 3)[:40]
PLAN = '_plan/12-analytics-and-trends.md'
CELL = 'matrix[family=biology-genetics,group=causal-and-experimental-inference]'
REAL = os.path.join(ROOT, *C.PREPRINT.split('/'))
BUILT = os.path.join(ROOT, *C.ARTIFACT.split('/'))


def doc(**over):
    d = {
        'artifact': 'gaps', 'format': 1, 'grid': 'coarse', 'reviewed_only': True,
        'axes': {'rows': {'count': 19, 'version': '0.9.0'}, 'columns': {'count': 13, 'version': '0.9.0'}},
        'cells_total': 247, 'entries': 320, 'claims_total': 0,
        'parameters': {'as_of': '2026-11-25', 'data_commit': SHA, 'min_confidence': 0.6,
                       'density_reference': {'value': 29.8353, 'family': 'vision', 'group': 'perception-space-time'},
                       'expectations': {'verified': False}},
        'families': [
            {'id': 'biology-genetics', 'entries': 25, 'curation_confidence': {'value': 0.0},
             'domain_activity': {'value': 0.2353, 'released_in_window': 4, 'dated_entries': 17}},
            {'id': 'vision', 'entries': 22, 'curation_confidence': {'value': 0.0}, 'domain_activity': {'value': 0.0526}},
        ],
        'matrix': [
            {'family': 'biology-genetics', 'group': 'causal-and-experimental-inference', 'density': 25.8825,
             'counts': {'primary': 23, 'secondary': 1},
             'factors': {'normalised_density': 0.8675, 'curation_confidence': 0.0}},
            {'family': 'biology-genetics', 'group': 'planning-and-search', 'density': 1.05,
             'counts': {'primary': 1, 'secondary': 0},
             'factors': {'normalised_density': 0.0352, 'curation_confidence': 0.0}},
            {'family': 'vision', 'group': 'perception-space-time', 'density': 29.8353,
             'counts': {'primary': 19, 'secondary': 17},
             'factors': {'normalised_density': 1.0, 'curation_confidence': 0.0}},
        ],
        'quality_weights': {'uspto-50k': {'weight': 1.0, 'applied': []}, 'arc-agi-1': {'weight': 1.0, 'applied': []}},
    }
    d.update(over)
    return d


def b(path, text):
    return '<!-- gaps: %s -->%s<!-- /gaps -->' % (path, text)


def q(src, text):
    return '<!-- quoted: %s -->%s<!-- /quoted -->' % (src, text)


ROW = '| causal | %s | %s | %s | %s |' % (
    b(CELL + '.counts.primary', '23'), b(CELL + '.density', '25.8825'),
    b(CELL + '.factors.normalised_density', '0.8675'), b(CELL + '.factors.curation_confidence', '0.0'))
GOOD = '\n'.join([
    '# A synthetic preprint',
    '',
    '> Agent draft at data commit %s, dated %s.' % (b(C.COMMIT, SHA), b('parameters.as_of', '2026-11-25')),
    '',
    '## 1. Method',
    '',
    'The grid is %s x %s, %s cells (12 S5.1), read with `_plan/12-analytics-and-trends.md`; see section 2.'
    % (b('axes.rows.count', '19'), b('axes.columns.count', '13'), b('cells_total', '247')),
    'The plan quotes %s reactions, and `uspto-50k` is one entry. Verified: %s.'
    % (q(PLAN, '50,016'), b('parameters.expectations.verified', 'false')),
    '',
    'The densest cell is at %s, with vision\'s curation confidence %s, at data commit %s.'
    % (b(C.DENSITY_REFERENCE, '29.8353'), b('families[id=vision].curation_confidence.value', '0.0'), b(C.COMMIT, SHA)),
    '',
    '## 2. A row',
    '',
    'At data commit %s, biology-genetics holds %s entries.' % (b(C.COMMIT, SHA), b('families[id=biology-genetics].entries', '25')),
    '',
    '| Group | Primary | Density | Normalised density | Curation confidence |',
    '| --- | ---: | ---: | ---: | ---: |',
    ROW,
    '',
])


def errors(text, d=None):
    return C.check(text, doc() if d is None else d, ROOT)[0]


def joined(text, d=None):
    return '\n'.join(errors(text, d))


# ---- the synthetic preprint ----------------------------------------------------------------------------------

def test_a_preprint_whose_every_number_is_accounted_for_passes():
    errs, rep = C.check(GOOD, doc(), ROOT)
    assert errs == []
    assert rep['commit'] == SHA
    assert rep['quoted'] == {PLAN: 1}
    assert rep['exempt'] == {'repo-path': 1, 'benchmark-id': 1, 'plan-section': 1, 'heading-number': 2,
                             'section-ref': 1}
    assert rep['density'] == 3


def test_an_invented_number_fails():
    out = joined(GOOD + 'Another 42 entries are on the way.\n')
    assert "'42' is not bound to gaps.json" in out


def test_an_integer_off_by_one_fails():
    bad = GOOD.replace(b('families[id=biology-genetics].entries', '25'), b('families[id=biology-genetics].entries', '26'))
    out = joined(bad)
    assert "'26' is bound to families[id=biology-genetics].entries, which gaps.json holds as 25" in out


def test_a_decimal_off_by_one_in_its_last_place_fails():
    bad = GOOD.replace(b(CELL + '.factors.normalised_density', '0.8675'), b(CELL + '.factors.normalised_density', '0.8676'))
    assert 'which gaps.json holds as 0.8675' in joined(bad)


def test_an_integer_is_printed_as_one():
    bad = GOOD.replace(b(CELL + '.counts.primary', '23'), b(CELL + '.counts.primary', '23.0'))
    assert 'which gaps.json holds as 23' in joined(bad)


def test_a_bound_path_that_selects_nothing_fails():
    bad = GOOD + 'Also %s.\n' % b('families[id=biology-genetics].phantom', '7')
    assert "has no key 'phantom'" in joined(bad)
    bad = GOOD + 'Also %s.\n' % b('matrix[family=biology-genetics].density', '1.05')
    assert '2 elements of matrix match' in joined(bad)
    bad = GOOD + 'Also %s.\n' % b('families[id=biology-genetics]', '25')
    assert 'not one value' in joined(bad)


def test_a_density_without_its_curation_confidence_beside_it_fails():
    bare = ROW.replace(' %s |' % b(CELL + '.factors.curation_confidence', '0.0'), ' - |')
    out = joined(GOOD.replace(ROW, bare))
    assert "density figure '25.8825'" in out and 'no curation confidence of biology-genetics' in out
    assert "density figure '0.8675'" in out


def test_another_familys_curation_confidence_does_not_count():
    other = ROW.replace(b(CELL + '.factors.curation_confidence', '0.0'),
                        b('families[id=vision].curation_confidence.value', '0.0'))
    assert 'no curation confidence of biology-genetics' in joined(GOOD.replace(ROW, other))


def test_a_confidence_in_the_next_paragraph_is_not_beside_it():
    split = GOOD.replace(", with vision's curation confidence", '.\n\nVision\'s curation confidence is')
    assert "density figure '29.8353'" in joined(split)


def test_a_section_that_prints_density_cites_the_commit():
    bad = GOOD.replace('At data commit %s, biology' % b(C.COMMIT, SHA), 'Here biology')
    assert 'this section prints density figures but never binds parameters.data_commit' in joined(bad)


def test_the_preprint_binds_the_commit_at_all():
    bad = GOOD.replace(b(C.COMMIT, SHA), 'a commit')
    assert 'never binds parameters.data_commit' in joined(bad)


def test_an_artifact_built_at_another_commit_fails_on_the_hash():
    out = joined(GOOD, doc(parameters=dict(doc()['parameters'], data_commit='f' * 40)))
    assert 'gaps.json was built at %s' % ('f' * 40) in out and 'git worktree add' in out


def test_an_artifact_with_no_commit_is_refused():
    assert 'carries no data commit SHA' in joined(GOOD, doc(parameters=dict(doc()['parameters'], data_commit=None)))


def test_only_the_published_artifact_is_checked_against():
    assert 'is not the published gaps.json' in joined(GOOD, doc(reviewed_only=False))
    assert 'is not the published gaps.json' in joined(GOOD, doc(grid='fine'))


def test_years_dates_and_short_hashes_have_no_exemption():
    out = joined(GOOD + 'Released in 2019, surveyed on 2026-11-05, commit %s.\n' % SHA[:8])
    for token in ('2019', '2026', '11', '05', '01234567'):
        assert "'%s' is not bound" % token in out


def test_a_year_in_a_heading_is_not_a_section_number():
    assert "'2026' is not bound" in joined(GOOD + '\n## 2026 results\n')


def test_numbers_in_a_code_fence_are_not_exempt():
    assert "'0.4' is not bound" in joined(GOOD + '\n```\nweight = 0.4\n```\n')


def test_a_quoted_figure_must_be_in_its_source_verbatim():
    assert 'which does not say it' in joined(GOOD.replace(q(PLAN, '50,016'), q(PLAN, '50,017')))
    assert 'which does not say it' in joined(GOOD.replace(q(PLAN, '50,016'), q(PLAN, '50,01')))   # part of a number
    assert 'which is not under' in joined(GOOD.replace(q(PLAN, '50,016'), q('docs/gap-matrix.md', '50,016')))
    assert 'which does not exist' in joined(GOOD.replace(q(PLAN, '50,016'), q('_plan/99-nothing.md', '50,016')))


def test_a_plan_section_must_exist():
    assert 'has no heading numbered 9.99' in joined(GOOD.replace('(12 S5.1)', '(12 S9.99)'))
    assert '0 files match _plan/99-*.md' in joined(GOOD.replace('(12 S5.1)', '(99 S5.1)'))


def test_a_section_reference_must_name_a_heading_of_the_preprint():
    assert 'refers to section 7' in joined(GOOD.replace('see section 2', 'see section 7'))


def test_a_path_or_benchmark_id_exempts_only_when_it_exists():
    assert "'99' is not bound" in joined(GOOD.replace('`_plan/12-analytics-and-trends.md`', '`_plan/99-nothing.md`'))
    assert "'42' is not bound" in joined(GOOD.replace('`uspto-50k`', '`not-a-benchmark-42`'))


def test_a_malformed_marker_fails():
    out = joined(GOOD + 'It holds <!-- gaps: entries -->320 entries.\n')
    assert 'malformed gaps or quoted marker' in out


def test_the_docstring_states_every_exemption_rule():
    for name, _, _ in C.EXEMPT:
        assert name in C.__doc__
    for word in ('bound', 'quoted', 'exempt', 'Years, dates and the commit hash have no rule', 'spelled out in words'):
        assert word in C.__doc__


def test_main_exit_codes(tmp_path, capsys):
    pre, art = tmp_path / 'p.md', tmp_path / 'gaps.json'
    pre.write_text(GOOD, encoding='utf-8')
    assert C.main(['--preprint', str(pre), '--against', str(art)]) == 2
    art.write_text(json.dumps(doc()), encoding='utf-8')
    assert C.main(['--preprint', str(pre), '--against', str(art)]) == 0
    assert 'OK' in capsys.readouterr().out
    pre.write_text(GOOD + 'And 42.\n', encoding='utf-8')
    assert C.main(['--preprint', str(pre), '--against', str(art)]) == 1
    assert C.main(['--preprint', str(tmp_path / 'none.md'), '--against', str(art)]) == 2


# ---- the preprint itself ------------------------------------------------------------------------------------

def preprint():
    with open(REAL, encoding='utf-8') as fh:
        return fh.read()


def test_the_preprint_says_it_is_an_unreviewed_agent_draft_at_the_top():
    head = preprint().split('\n## ', 1)[0].lower()
    assert 'agent draft' in head and 'not peer reviewed' in head and 'not posted' in head


def test_every_number_in_the_preprint_is_bound_quoted_or_exempt():
    errs, rep = C.check(preprint(), None, ROOT)            # structure only: no artifact at the cited commit needed
    assert errs == []
    assert rep['density'] > 0 and rep['bound'] > rep['density']


def test_the_preprint_is_pinned_to_one_commit():
    commits = set(C.cited_commits(preprint()))
    assert len(commits) == 1 and C.SHA.match(commits.pop())


def test_the_preprint_reproduces_from_the_artifact_at_its_commit():
    if not os.path.isfile(BUILT):
        pytest.skip('%s is not built; run `%s` at the cited commit' % (C.ARTIFACT, C.MAKE))
    with open(BUILT, encoding='utf-8') as fh:
        built = json.load(fh)
    cited = C.cited_commits(preprint())[0]
    if built['parameters'].get('data_commit') != cited:
        pytest.skip('%s was built at %s, the preprint cites %s' % (C.ARTIFACT, built['parameters'].get('data_commit'), cited))
    errs, rep = C.check(preprint(), built, ROOT)
    assert errs == []
