#!/usr/bin/env python3
"""No stored Source extract carries an e-mail address, an arXiv submitter's name or an arXiv abstract page's
author list (04 S9; the maintainer's calls of 2026-11-18).

A Source's `quote_extract` is the text the quote check reads, committed under data/ and published with the
record. Personal data sits right beside the facts it backs: contact lines in papers and READMEs, the addresses
in GitHub API JSON, the "From: <name> [view email]" line on every arXiv abstract page, and the byline above
every abstract. Curators window those out, or replace them with a `[... redacted]` token and count the token
in `quote_extract_redactions` (schema/source.py). This holds the line:

  email      no extract contains an e-mail address; it becomes `[email redacted]`.
  submitter  no "[view email" in an extract follows a name: the text between it and the "From:" before it
             (or the start of its window) is empty or `[name redacted]`.
  byline     an arXiv abs page's extract names no author: what follows each "Authors:" label (up to "View",
             "Abstract:" or the end of its window), and the names on its "..., by <names>[ and N other
             authors] View PDF" line, are `[names redacted]`, or nothing where a window ends at the label.
             A byline that is one organisation ("by Example Prize Foundation") is not a person's name and
             stays; so does one that a quote in data/ cites, since the quote check needs that text.
  counted    an extract holding a `[... redacted]` token says how many in `quote_extract_redactions`.

The byline rule reads only an abs page's fixed labels, so it needs no list of names. A PDF's or an HTML
rendering's byline has no such label; the sweep that redacted those matched each paper's author names from the
arXiv API, and no name is stored for a check to reuse.

    python scripts/check_extract_personal_data.py                  # the repository
    python scripts/check_extract_personal_data.py --root DIR       # the tests
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EMAIL = re.compile(r'(?:\{[^{}]{1,200}\}|[A-Za-z0-9._%+-]+)@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')  # and {a,b}@x
VIEW_EMAIL = re.compile(r'\[ ?view email')
TOKEN = re.compile(r'\[[a-z ]*redacted\]')
SEP = ' … '                                     # how a windows extract joins its windows
WINDOW_SEP = re.compile(r' … | \[\.\.\.\] ')    # ... and the other joiner some extracts use
ABS_PAGE = re.compile(r'^https?://(?:www\.)?arxiv\.org/abs/')
NAMES = '[names redacted]'
AUTHORS = re.compile(r'Authors:\s*')
AUTHORS_END = re.compile(r' View\b| Abstract:| Comments:| Subjects:')
BY = re.compile(r', by ((?:(?!, by ).){1,300}?)(?: and \d+ other authors?)? View PDF')
ORG_BYLINE = re.compile(r"^(?:[A-Z][\w&.'-]*\s+){0,5}(?:Team|Foundation|Consortium|Collaboration|Project|Institute|"
                        r'Initiative|Labs?|Group)$')


def submitters(extract: str) -> int:
    """How many "[view email" links in the extract follow a name that is not redacted."""
    n = 0
    for window in extract.split(SEP):
        for m in VIEW_EMAIL.finditer(window):
            before = window[:m.start()]
            name = before[before.rfind('From:') + len('From:'):] if 'From:' in before else before
            name = name.strip()
            if name and name != '[name redacted]' and not name.endswith('[name redacted]'):
                n += 1
    return n


def windows(extract: str):
    """(offset, text) of each window of an extract."""
    i = 0
    for m in WINDOW_SEP.finditer(extract):
        yield i, extract[i:m.start()]
        i = m.end()
    yield i, extract[i:]


def bylines(extract: str) -> list[tuple[int, int]]:
    """The (start, end) of each author list on an arXiv abs page's extract that still names someone."""
    out = []
    for off, window in windows(extract):
        for m in AUTHORS.finditer(window):
            end = AUTHORS_END.search(window, m.end())
            who = window[m.end():end.start() if end else len(window)].strip()
            if who and not who.startswith(NAMES) and not ORG_BYLINE.match(who):
                out.append((off + m.end(), off + m.end() + len(who)))
        for m in BY.finditer(window):
            who = m.group(1).strip()
            if who != NAMES and not ORG_BYLINE.match(who):
                out.append((off + m.start(1), off + m.end(1)))
    return out


def cited_quotes(root: str) -> dict[str, list[str]]:
    """Source id -> the quotes in data/ that cite it (tools/validate/quotes.py finds them)."""
    sys.path.insert(0, ROOT)
    from tools.validate.quotes import find
    loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
    out: dict[str, list[str]] = {}
    sources = os.path.normpath(os.path.join(root, 'data', 'sources')) + os.sep
    for path in glob.glob(os.path.join(root, 'data', '**', '*.yaml'), recursive=True):
        if os.path.normpath(path).startswith(sources):
            continue
        with open(path, encoding='utf-8') as fh:
            for q in find(yaml.load(fh, Loader=loader)):
                if q.source:
                    out.setdefault(q.source, []).append(q.text)
    return out


def quoted(extract: str, span: tuple[int, int], quotes: list[str]) -> bool:
    """Whether a quote, matched as the quote check matches it (schema/source.py fold), overlaps the span."""
    sys.path.insert(0, ROOT)
    from schema.source import fold
    low, back = [], []
    for k, ch in enumerate(extract):
        f = ch.casefold()
        low.append(f)
        back.extend([k] * len(f))
    low = ''.join(low)
    for q in quotes:
        fq = fold(q)
        i = low.find(fq) if fq else -1
        while i >= 0:
            if back[i] < span[1] and span[0] < back[i + len(fq) - 1] + 1:
                return True
            i = low.find(fq, i + 1)
    return False


def check(root: str) -> list[str]:
    errors = []
    cited = None
    for path in sorted(glob.glob(os.path.join(root, 'data', 'sources', '**', '*.yaml'), recursive=True)):
        with open(path, encoding='utf-8') as fh:
            record = yaml.safe_load(fh) or {}
        extract = record.get('quote_extract') or ''
        if not extract:
            continue
        sid = record.get('id') or os.path.basename(path)
        emails = len(EMAIL.findall(extract))
        if emails:
            errors.append('%s: the extract holds %d e-mail address(es); replace each with [email redacted]'
                          % (sid, emails))
        names = submitters(extract)
        if names:
            errors.append('%s: the extract names the arXiv submitter %d time(s); replace the name with '
                          '[name redacted]' % (sid, names))
        spans = bylines(extract) if ABS_PAGE.match(record.get('url') or '') else []
        if spans:
            if cited is None:
                cited = cited_quotes(root)
            spans = [s for s in spans if not quoted(extract, s, cited.get(sid) or [])]
        if spans:
            errors.append("%s: the extract names the paper's authors %d time(s) (an arXiv abs byline); replace "
                          'each list with [names redacted]' % (sid, len(spans)))
        tokens = len(TOKEN.findall(extract))
        if tokens and not record.get('quote_extract_redactions'):
            errors.append('%s: the extract holds %d redaction token(s) but quote_extract_redactions is unset'
                          % (sid, tokens))
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    a = ap.parse_args(argv)
    errors = check(a.root)
    for e in errors:
        print('FAIL  %s' % e)
    if errors:
        print('%d problem(s)' % len(errors))
        return 1
    print('OK    no Source extract holds an e-mail address, an unredacted arXiv submitter or an arXiv abs byline')
    return 0


if __name__ == '__main__':
    sys.exit(main())
