"""scripts/check_extract_personal_data.py: no stored extract carries an e-mail address or an arXiv submitter's name."""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_extract_personal_data as C  # noqa: E402


def source(tree, sid, extract, **extra):
    d = tree / 'data' / 'sources' / '2026'
    d.mkdir(parents=True, exist_ok=True)
    (d / ('%s.yaml' % sid)).write_text(yaml.safe_dump(dict(id=sid, quote_extract=extract, **extra)),
                                       encoding='utf-8')


@pytest.mark.parametrize('extract', [
    'Submission history From: [name redacted] [view email] [v1] Tue, 10 Oct 2023',
    'history From: [name redacted] [ view email ] [v1]',
    'Title:ARC- … view email] [v1] Sat, 17 May 2025',                     # the window starts after the name
    '[name redacted] [view email] [v1] Mon',                               # ... or at the redaction token
    'please contact the team, [email redacted], for a consultation',
    'no personal data at all',
])
def test_a_clean_extract_passes(tmp_path, extract):
    redactions = 1 if 'redacted' in extract else None
    source(tmp_path, 'src-a', extract, quote_extract_redactions=redactions)
    assert C.check(str(tmp_path)) == []


@pytest.mark.parametrize('extract, message', [
    ('Submission history From: Ada Example [view email] [v1]', 'names the arXiv submitter 1 time'),
    ('ple [ view email ] [v1] Tue', 'names the arXiv submitter 1 time'),     # a window that starts in the name
    ('write to someone@example.org with questions', 'holds 1 e-mail address'),
    ('{a,b}@example.org and c@example.ac.uk', 'holds 2 e-mail address'),
])
def test_personal_data_fails(tmp_path, extract, message):
    source(tmp_path, 'src-a', extract)
    errs = C.check(str(tmp_path))
    assert len(errs) == 1 and message in errs[0], errs


def test_a_redaction_token_needs_its_count(tmp_path):
    source(tmp_path, 'src-a', 'From: [name redacted] [view email]')
    assert 'quote_extract_redactions is unset' in C.check(str(tmp_path))[0]


def test_windows_are_read_one_at_a_time(tmp_path):
    source(tmp_path, 'src-a', 'From: [name redacted] … Someone Else [view email] [v2]', quote_extract_redactions=1)
    assert 'names the arXiv submitter 1 time' in C.check(str(tmp_path))[0]


def test_the_repository_passes():
    assert C.check(ROOT) == []


def test_pr_validate_runs_it_and_it_blocks():
    with open(os.path.join(ROOT, '.github', 'workflows', 'pr-validate.yml'), encoding='utf-8') as fh:
        job = yaml.safe_load(fh)['jobs']['extract-personal-data']
    assert 'continue-on-error' not in job and 'if' not in job
    runs = [s['run'] for s in job['steps'] if 'run' in s]
    assert runs == ['uv run --locked --python "$PYTHON" python scripts/check_extract_personal_data.py']
