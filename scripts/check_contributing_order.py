#!/usr/bin/env python3
"""CONTRIBUTING.md presents the issue path before the pull-request path (P2-S6-T07; 05-repository-and-workflow.md
S6.5, S6).

05 S6.5: "CONTRIBUTING.md is short and has four sections, in this order. Order matters because most readers stop
after the first ... (4) Working in git, for the minority who want Path B, which is the only section that mentions
a clone. If section 4 appears before section 3, the document has recreated the barrier it exists to remove." 05 S6
says why the order is the point: a PR-only workflow is a documented cause of death for this kind of catalogue, and
every contributor who bounces off git is an argument for closing it. So this asserts:

  sections    exactly four H2 headings, in this order: Fix one thing, Add a benchmark, What happens next, Working
              in git. A leading number ("1.") is allowed. A `##` line inside a code fence or an HTML comment is not
              a heading; a setext heading (a line of text underlined with --- or ===) is one.
  no-git      nothing before the Working in git heading mentions a clone or gives a git command: the word clone in
              any form, `git <subcommand>` (also across a line break), a `gh` command, a shell code block, forking
              the repository, or a git remote URL. "No git" in prose is fine; `git clone` is not, not even to say
              it is not needed.
  issue-path  the issue path is presented first: Fix one thing links the correction form and Add a benchmark the
              new-benchmark form (an issues/new?template=<form>.yml URL), and nothing before Working in git
              presents the pull-request path: Path B, a direct or "your own" pull request, a link to the
              repository's pulls, compare, fork or edit pages, or a `bench` command.

Everything before the Working in git heading is scanned as one text, prose, code and comments alike, so a hidden
`git clone` counts as much as a visible one.

    python scripts/check_contributing_order.py              # P2-S6-T07's verify: exit 0 if it holds, 1 otherwise
    python scripts/check_contributing_order.py --root DIR   # another tree (the tests do)

What it cannot check is the third condition of the task's done_when, that a person has reviewed the document
because it decides whether an outsider bounces. That review is the maintainer's.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = 'CONTRIBUTING.md'
SECTIONS = ('Fix one thing', 'Add a benchmark', 'What happens next', 'Working in git')
GIT_SECTION = SECTIONS[-1]
# The issue-path sections and the form each must link (.github/ISSUE_TEMPLATE/, P2-S6-T02).
FORM_LINKS = {'Fix one thing': 'correction.yml', 'Add a benchmark': 'new-benchmark.yml'}

FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})[ \t]*([^\s`]*)')
ATX = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$')
SETEXT = re.compile(r'^ {0,3}(=+|-+)[ \t]*$')
NOT_PARAGRAPH = re.compile(r'^(?: {4,}|\t| {0,3}(?:>|[-*+][ \t]|\d+[.)][ \t]|\||#{1,6}(?:[ \t]|$)|`{3,}|~{3,}|<))')
NUMBER = re.compile(r'^(?:section[ \t]+)?\d+[ \t]*[.):][ \t]*', re.I)
SHELL = frozenset({'sh', 'bash', 'shell', 'console', 'zsh', 'fish', 'powershell', 'pwsh', 'ps1', 'bat', 'cmd'})
GIT_SUBCOMMANDS = ('add am apply bisect blame branch checkout cherry-pick clean clone commit config diff fetch init '
                   'log merge mv pull push rebase remote reset restore revert rm show stash status submodule switch '
                   'tag worktree').split()
BENCH_COMMANDS = ('new fmt validate build promote migrate resolve ingest report schema check-links tag-gap '
                  'gaps').split()

NO_GIT = (
    ('a clone', re.compile(r'\bclon(?:e|es|ed|ing)\b', re.I)),
    ('a git command', re.compile(r'\bgit\s+(?:%s)\b' % '|'.join(map(re.escape, GIT_SUBCOMMANDS)), re.I)),
    ('a gh command', re.compile(r'\bgh\s+(?:repo|pr|issue|auth|api|browse)\b')),
    ('forking the repository', re.compile(r'\bfork(?:s|ed|ing)?\s+(?:the|this|our|your)\s+repo', re.I)),
    ('a git remote URL', re.compile(r'[\w-]\.git\b|\bgit@[\w.-]+:', re.I)),
)
PR_PATH = (
    ('Path B', re.compile(r'\bPath\s+B\b')),
    ('a pull request of the reader\'s own',
     re.compile(r'\b(?:your|your\s+own|direct)\s+pull\s+requests?\b|\bpull\s+requests?\s+yourself\b', re.I)),
    ('a link to the pulls, compare, fork or edit pages',
     re.compile(r'github\.com/[\w.-]+/[\w.-]+/(?:pulls?|compare|fork|edit|new/main)\b', re.I)),
    ('a bench command', re.compile(r'\bbench\s+(?:%s)\b' % '|'.join(map(re.escape, BENCH_COMMANDS)))),
)


def normalise(heading: str) -> str:
    """A heading's words for comparison: no emphasis or code marks, no leading section number, no closing
    punctuation, one space between words, case folded."""
    text = re.sub(r'[*_`]', '', heading)
    text = NUMBER.sub('', text.strip())
    return ' '.join(text.rstrip(' .:').split()).casefold()


def headings(lines: list[str]) -> tuple[list[tuple[int, int, str]], list[tuple[int, str]]]:
    """([(line index, level, text)] for every heading outside a fence or HTML comment, [(line index, info string)]
    for every opening code fence)."""
    out, fences = [], []
    fence = None                                         # the open fence's marker, or None
    comment = False
    structural = set()                                   # lines no setext underline can turn into a heading
    for i, line in enumerate(lines):
        if fence is not None:
            structural.add(i)
            m = FENCE.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2):
                fence = None
            continue
        if comment:
            structural.add(i)
            comment = '-->' not in line
            continue
        m = FENCE.match(line)
        if m:
            structural.add(i)
            fence = m.group(1)
            fences.append((i, m.group(2).casefold()))
            continue
        if line.lstrip().startswith('<!--'):
            structural.add(i)
            comment = '-->' not in line
            continue
        m = ATX.match(line)
        if m:
            structural.add(i)
            out.append((i, len(m.group(1)), (m.group(2) or '').strip()))
            continue
        m = SETEXT.match(line)
        if m and i > 0 and i - 1 not in structural:
            prev = lines[i - 1]
            if prev.strip() and not NOT_PARAGRAPH.match(prev):
                structural.add(i)
                out.append((i - 1, 1 if m.group(1)[0] == '=' else 2, prev.strip()))
    return out, fences


def line_of(text: str, offset: int) -> int:
    return text.count('\n', 0, offset) + 1


def check_text(text: str, name: str = FILE) -> list[str]:
    lines = text.split('\n')
    found, fences = headings(lines)
    h2 = [(i, t) for i, level, t in found if level == 2]
    out = []

    # sections: exactly the four, in order
    got = [normalise(t) for _, t in h2]
    want = [normalise(s) for s in SECTIONS]
    if got != want:
        out.append('%s: the H2 headings must be exactly %s, in that order; found %s'
                   % (name, ', '.join(SECTIONS), ', '.join(t for _, t in h2) or 'none'))

    # where Working in git starts: everything before it is the issue path
    starts = [i for i, t in h2 if normalise(t) == normalise(GIT_SECTION)]
    boundary = starts[0] if starts else len(lines)
    before = '\n'.join(lines[:boundary])

    # no-git
    for what, pattern in NO_GIT:
        for m in pattern.finditer(before):
            out.append('%s:%d: %s (%r) before "%s"; only that section may mention a clone or give a git command'
                       % (name, line_of(before, m.start()), what, ' '.join(m.group(0).split()), GIT_SECTION))
    for i, info in fences:
        if i < boundary and (info in SHELL or info.startswith('shell-')):
            out.append('%s:%d: a shell code block (```%s) before "%s"' % (name, i + 1, info, GIT_SECTION))

    # issue-path: the forms first, the pull-request path only in Working in git
    for section, form in FORM_LINKS.items():
        spans = [k for k, (_, t) in enumerate(h2) if normalise(t) == normalise(section)]
        if not spans:
            continue                                     # reported under sections
        k = spans[0]
        start, end = h2[k][0], h2[k + 1][0] if k + 1 < len(h2) else len(lines)
        body = '\n'.join(lines[start:end])
        link = re.compile(r'/issues/new\?(?:[^\s)>"\']*&)?template=%s(?![\w.-])' % re.escape(form))
        if not link.search(body):
            out.append('%s:%d: "%s" does not link the %s issue form (issues/new?template=%s)'
                       % (name, start + 1, section, form[:-4], form))
    for what, pattern in PR_PATH:
        for m in pattern.finditer(before):
            out.append('%s:%d: the pull-request path (%s: %r) before "%s"; the issue path comes first'
                       % (name, line_of(before, m.start()), what, ' '.join(m.group(0).split()), GIT_SECTION))
    return out


def check(root: str) -> list[str]:
    path = os.path.join(root, FILE)
    if not os.path.exists(path):
        return ['%s: missing' % FILE]
    with open(path, encoding='utf-8') as fh:
        return check_text(fh.read().replace('\r\n', '\n'))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    bad = check(a.root)
    for line in bad:
        print('BLOCKING  contributing  %s' % line)
    print('check_contributing_order: %d section(s) expected, %d problem(s)' % (len(SECTIONS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
