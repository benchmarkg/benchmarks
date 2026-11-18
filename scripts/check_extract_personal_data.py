#!/usr/bin/env python3
"""No stored Source extract carries an e-mail address or an arXiv submitter's name (04 S9; the maintainer's call
of 2026-11-18).

A Source's `quote_extract` is the text the quote check reads, committed under data/ and published with the
record. Personal data sits right beside the facts it backs: contact lines in papers and READMEs, the addresses
in GitHub API JSON, and the "From: <name> [view email]" line on every arXiv abstract page. Curators window
those out, or replace them with a `[... redacted]` token and count the token in `quote_extract_redactions`
(schema/source.py). This holds the line:

  email      no extract contains an e-mail address; it becomes `[email redacted]`.
  submitter  no "[view email" in an extract follows a name: the text between it and the "From:" before it
             (or the start of its window) is empty or `[name redacted]`.
  counted    an extract holding a `[... redacted]` token says how many in `quote_extract_redactions`.

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


def check(root: str) -> list[str]:
    errors = []
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
    print('OK    no Source extract holds an e-mail address or an unredacted arXiv submitter')
    return 0


if __name__ == '__main__':
    sys.exit(main())
