"""Tests for scripts/check_contributing_order.py (P2-S6-T07; 05-repository-and-workflow.md S6.5).

The verify: `python scripts/check_contributing_order.py`. Done when "The four H2s appear in that order, no clone or
git command appears before section 4, and a human has reviewed it because it decides whether an outsider bounces."
The human review is the maintainer's. These cases run the checker on the committed CONTRIBUTING.md, and on copies
of it with one thing broken each time, so every assertion it makes is seen to fail at least once.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'scripts', 'check_contributing_order.py')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import check_contributing_order as C  # noqa: E402

FORM = 'https://github.com/benchmarkg/benchmarks/issues/new?template=%s.yml'
MINIMAL = '\n'.join([
    '# Contributing', '',
    'No git needed for the first three sections.', '',
    '## Fix one thing', '',
    'Open [the form](%s).' % (FORM % 'correction'), '',
    '## Add a benchmark', '',
    'Open [the form](%s).' % (FORM % 'new-benchmark'), '',
    '## What happens next', '',
    'A person reads it, and the bot opens a pull request when it is on.', '',
    '## Working in git', '',
    'Path B: fork the repository, then open your own pull request.', '',
    '```sh', 'git clone https://github.com/you/benchmarks.git', '# a comment, not a heading',
    'uv run bench validate --changed-only', '```', '',
])


def committed():
    with open(os.path.join(ROOT, 'CONTRIBUTING.md'), encoding='utf-8') as fh:
        return fh.read().replace('\r\n', '\n')


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, encoding='utf-8')


def into(text, section, snippet):
    """`text` with `snippet` as a paragraph straight after the H2 `section`."""
    head = '## %s\n' % section
    assert head in text, section
    return text.replace(head, '%s\n%s\n' % (head, snippet), 1)


def problems(text):
    return C.check_text(text)


def test_verify_the_committed_contributing_holds():
    r = run()
    assert r.returncode == 0, r.stdout
    assert '0 problem(s)' in r.stdout


def test_the_committed_h2s_are_the_four_in_order():
    found, _ = C.headings(committed().split('\n'))
    assert [t for _, level, t in found if level == 2] == list(C.SECTIONS)


def test_a_minimal_document_holds_and_section_four_may_say_clone():
    assert problems(MINIMAL) == []


def test_numbered_and_emphasised_headings_are_the_same_headings():
    text = MINIMAL
    for n, s in enumerate(C.SECTIONS, 1):
        text = text.replace('## %s\n' % s, '## %d. *%s*\n' % (n, s))
    assert problems(text) == []


def swap(text, a, b):
    """`text` with the sections headed `a` and `b` (a before b, b running to the end or the next H2) exchanged."""
    lines = text.split('\n')
    h2 = [i for i, line in enumerate(lines) if line.startswith('## ')]
    ia, ib = lines.index('## ' + a), lines.index('## ' + b)
    end_a, end_b = h2[h2.index(ia) + 1], (h2[h2.index(ib) + 1] if h2.index(ib) + 1 < len(h2) else len(lines))
    return '\n'.join(lines[:ia] + lines[ib:end_b] + lines[end_a:ib] + lines[ia:end_a] + lines[end_b:])


@pytest.mark.parametrize('breaks, expect', [
    (lambda t: swap(t, 'What happens next', 'Working in git'), 'in that order'),
    (lambda t: t.replace('## Add a benchmark\n', 'Add a benchmark\n'), 'in that order'),
    (lambda t: into(t, 'What happens next', '## Credit\n'), 'in that order'),
    (lambda t: t.replace('## What happens next\n', '## What happens after\n'), 'in that order'),
    (lambda t: t.replace('## Working in git\n', '### Working in git\n'), 'in that order'),
    (lambda t: into(t, 'Add a benchmark', 'Some extra words\n---\n'), 'in that order'),
])
def test_the_sections_fail_when_broken(breaks, expect):
    for text in (committed(), MINIMAL):
        got = problems(breaks(text))
        assert any(expect in p for p in got), got


@pytest.mark.parametrize('snippet, expect', [
    ('You never need to clone anything.', 'a clone'),
    ('Cloning is not needed.', 'a clone'),
    ('Then run `git push`.', 'a git command'),
    ('Then run git\npull, and wait.', 'a git command'),
    ('Or use `gh repo fork` if you like.', 'a gh command'),
    ('Fork the repository first.', 'forking the repository'),
    ('The remote is https://github.com/benchmarkg/benchmarks.git here.', 'a git remote URL'),
    ('```bash\nls\n```', 'a shell code block'),
    ('<!-- git clone, hidden -->', 'a clone'),
])
@pytest.mark.parametrize('section', ['Fix one thing', 'Add a benchmark', 'What happens next'])
def test_no_clone_or_git_command_before_working_in_git(section, snippet, expect):
    for text in (committed(), MINIMAL):
        got = problems(into(text, section, snippet))
        assert any(expect in p for p in got), got


def test_a_clone_in_the_preamble_counts_too():
    got = problems(MINIMAL.replace('No git needed', 'No clone needed'))
    assert any('a clone' in p and 'CONTRIBUTING.md:3:' in p for p in got), got


@pytest.mark.parametrize('snippet, expect', [
    ('Prefer Path B? Read on.', 'Path B'),
    ('Or open your own pull request.', "reader's own"),
    ('A direct pull request also works.', "reader's own"),
    ('Send the pull request yourself.', "reader's own"),
    ('See [the pull requests](https://github.com/benchmarkg/benchmarks/pulls).', 'pulls, compare'),
    ('Or [edit it](https://github.com/benchmarkg/benchmarks/edit/main/data/x.yaml).', 'pulls, compare'),
    ('Run `bench new benchmark --id x`.', 'a bench command'),
])
@pytest.mark.parametrize('section', ['Fix one thing', 'Add a benchmark', 'What happens next'])
def test_the_pull_request_path_comes_only_after_the_issue_path(section, snippet, expect):
    for text in (committed(), MINIMAL):
        got = problems(into(text, section, snippet))
        assert any('the pull-request path' in p and expect in p for p in got), got


@pytest.mark.parametrize('section, form', [('Fix one thing', 'correction'), ('Add a benchmark', 'new-benchmark')])
def test_each_issue_section_links_its_form(section, form):
    for text in (committed(), MINIMAL):
        broken = text.replace('template=%s.yml' % form, 'template=%s.yaml' % form)
        got = problems(broken)
        assert any('"%s" does not link the %s issue form' % (section, form) in p for p in got), got


def test_a_form_link_in_the_wrong_section_does_not_count():
    text = MINIMAL.replace('Open [the form](%s).' % (FORM % 'correction'), 'Read on.')
    text = text.replace('A person reads it,', 'A person reads [it](%s),' % (FORM % 'correction'))
    got = problems(text)
    assert any('"Fix one thing" does not link the correction issue form' in p for p in got), got


def test_headings_in_code_fences_and_comments_are_not_headings():
    text = into(MINIMAL, 'Fix one thing', '```\n## Working in git\n```\n\n<!--\n## Working in git\n-->')
    assert problems(text) == []


def test_a_rule_after_a_fence_or_a_list_is_not_a_heading():
    text = into(MINIMAL, 'Add a benchmark', '```yaml\nid: x\n```\n---\n\n- an item\n---')
    assert problems(text) == []


def test_crlf_line_endings_read_the_same(tmp_path):
    (tmp_path / 'CONTRIBUTING.md').write_bytes(MINIMAL.replace('\n', '\r\n').encode('utf-8'))
    r = run('--root', str(tmp_path))
    assert r.returncode == 0, r.stdout


def test_a_missing_file_fails(tmp_path):
    r = run('--root', str(tmp_path))
    assert r.returncode == 1 and 'CONTRIBUTING.md: missing' in r.stdout, r.stdout


def test_a_broken_file_fails_through_the_command_line(tmp_path):
    (tmp_path / 'CONTRIBUTING.md').write_text(swap(MINIMAL, 'What happens next', 'Working in git'),
                                              encoding='utf-8')
    r = run('--root', str(tmp_path))
    assert r.returncode == 1 and 'BLOCKING  contributing' in r.stdout, r.stdout
