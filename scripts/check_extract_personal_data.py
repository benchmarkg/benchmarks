#!/usr/bin/env python3
"""No stored Source extract carries an e-mail address, an arXiv submitter's name, an arXiv abstract page's
or HTML rendering's author list, a fixed-layout page's labelled list of people, a paper's author note or a
copyright line that names a person (04 S9; the maintainer's calls of 2026-11-18).

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
  roster     a page whose layout is fixed names nobody in its labelled list of people: an ACL Anthology paper
             page's "Editors:" field (up to " Venue:" or the end of its window) and a NeurIPS Datasets and
             Benchmarks abstract page's "Authors" list (up to " Abstract"), when what the label holds is
             name-shaped (capitalised words, initials, name particles, separators), are `[names redacted]`
             or nothing. A list a quote in data/ cites stays, as a byline does.
  affiliation an arXiv HTML rendering (arxiv.org/html/) names no author before an "Affiliation:" or
             "Affiliations:" label, the layout its byline takes ("<names> Affiliation: <institution>", repeated):
             the name-shaped words right before each label are `[names redacted]`, or there are none because the
             label opens its window or follows running text ("... more Affiliations:"). The institution stays.
             A run of names a quote in data/ cites stays, as a byline does. A run whose label a window cuts
             off ("<names> A …") has no label left to read; the curator redacts it by hand.
  author-note an extract, from any page, names no author in an author note, the fixed phrasing of the footnote
             on a paper's first page ("<names> is with <institution>", or "are with", "is also with", "are
             also with"; IEEE's form, which a two-column PDF's text interleaves with the abstract): the run of
             names right before the phrase (initials and capitalised surnames, name particles, ", " and " and ",
             read from its first initial) is `[names redacted]`, or there is none because the phrase opens its
             window or follows running text ("The dataset is with", "Team 2 is with"). The institution stays,
             and so does a run a quote in data/ cites. A run must hold an initial: a note that spells out every
             given name ("Ada Example is with") is deliberately not caught, since a capitalised phrase reads
             the same ("Copyright is with the authors"). A run whose phrase a window cuts off ("<names> are wi
             …") has no phrase left to read, and a window that opens inside a run leaves the names before its
             first initial unread; the curator redacts those by hand.
  copyright  an extract, from any page, names no person as the holder of a copyright notice: "©" (or
             "&copy;"), "Copyright (c)", "Copyright" or "(c)" before a year or a "by", and SciPost's
             "Copyright <names> et al.", which has neither. The holder is the run of words after the marks,
             the years and a "by", while each is a capitalised word, an initial, a name particle or only
             marks; when it holds two name words, one of them capitalised ("© Copyright 2023, Ada Example.",
             "Copyright (c) 2024 A. Example", "© Ada Example (2022)"), or one before "et al.", it is
             `[name redacted]`, or `[names redacted]` for several. A holder an organisation word marks
             ("Example Lab", "Example, Inc.", "The Authors", "Example Contributors"), that a connector carries
             on ("Centre for Example Vision"), or that is written in capitals or camel case ("CAPRI & ...",
             "OpenAI") stays, as do licence boilerplate ("Copyright Notice", "the copyright holders") and a
             year alone; so does a holder a quote in data/ cites. A withheld Source is read like any other,
             as every rule here reads it: its extract is stored and published all the same. Not caught: a
             holder before its mark ("Ada Example © 2024"), a person beside an organisation in one run ("Ada
             Example & Example Lab"), a one-word holder without "et al." (a surname, a handle) and a name in
             capitals. An organisation whose name reads as a given name and a surname, with no organisation
             word, is caught; a quote that cites it keeps it, as one does on main today, or ORG_WORDS gains
             its word.
  counted    an extract holding a `[... redacted]` token says how many in `quote_extract_redactions`.

The byline, roster, affiliation and author-note rules read only fixed labels and phrasing, and the copyright
rule fixed marks and the shape of a name (its lists are of organisation and boilerplate words), so they need
no list of names. A PDF's byline has no such label (its author notes, where it has them, are the author-note
rule's), nor has an HTML rendering's other than arXiv's; the sweep that redacted those matched each paper's
author names from the arXiv API, and no name is stored for a check to reuse. The other lists of
people redacted by hand (organisers, chairs, committees and team members on challenge sites; bylines on
proceedings and project pages) sit in layouts that vary from page to page, where no label rule is precise enough
to hold the line without false alarms.

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
# (the pages a roster rule reads, its label, the end of the labelled field)
ROSTERS = (
    (re.compile(r'^https?://(?:www\.)?aclanthology\.org/(?![^?#]*\.pdf\b)'), re.compile(r'\bEditors:\s*'),
     re.compile(r' Venue:')),
    (re.compile(r'^https?://datasets-benchmarks-proceedings\.neurips\.cc/paper_files/paper/\d{4}/hash/'
                r'[^/?#]*-Abstract[^/?#]*\.html$'), re.compile(r'\bAuthors\s+'), re.compile(r' Abstract\b')),
)
HTML_PAGE = re.compile(r'^https?://(?:www\.)?arxiv\.org/html/')
AFFILIATION = re.compile(r'\bAffiliations?:')
WORD = re.compile(r'\S+')
MARKS = ',;.()*†‡∗§¶&·|0123456789'               # footnote marks and separators a name may carry
PARTICLES = {'van', 'von', 'der', 'den', 'de', 'del', 'della', 'di', 'da', 'dos', 'das', 'du', 'la', 'le', 'y', 'bin',
             'al', 'and'}
AUTHOR_NOTE = re.compile(r'\b(?:is|are)(?: also)? with\b')        # "<names> are with <institution>"
INITIAL = re.compile(r'[^\W\d_]{1,2}\.(?:-?[^\W\d_]{1,2}\.)*,?')  # "A.", "B.E.", "J.-P.", "Ch.", with a comma
# A copyright notice's marks ("©", "&copy;", "Copyright", "(c)", combined: "© Copyright", "Copyright (c)",
# "Publisher Copyright: ©"), then the years before its holder ("2023,", "2015 - 2026", "2022-present", "2024.")
COPY_MARKS = re.compile(r'(?:(?:©|&copy;|&#169;|\b[Cc]opyright\b|\bCOPYRIGHT\b|\([cC]\))[\s:]*)+')
COPY_YEARS = re.compile(r'(?:\d{4}(?:\s*[-–—]\s*(?:\d{4}|present))?\s*[,.]?\s*)+')
COPY_BY = re.compile(r'by\s+')
ET_AL = re.compile(r'\s+et\s+al\b')
HOLDER_MARKS = MARKS + '"\'“”‘’'                 # ... and the quotes a holder may sit in
# Capitalised words that open what follows a holder (licence text, a site's footer), not a name.
COPY_STOP = {'the', 'all', 'permission', 'licensed', 'redistribution', 'released', 'powered', 'built', 'made',
             'created', 'designed', 'design', 'revision', 'previous', 'next', 'privacy', 'terms', 'contact', 'back',
             'published', 'version', 'this', 'see', 'use', 'some', 'website', 'on'}
# The words that make a holder an organisation, in the run or as the word that ends it ("Google LLC").
ORG_WORDS = {'inc', 'llc', 'ltd', 'limited', 'corp', 'corporation', 'co', 'company', 'gmbh', 'ag', 'sa', 'plc',
             'university', 'universität', 'université', 'universidad', 'università', 'universiteit', 'college',
             'school', 'faculty', 'department', 'institute', 'institut', 'instituto', 'academy', 'lab', 'labs',
             'laboratory', 'laboratories', 'laboratoire', 'group', 'groups', 'team', 'project', 'foundation',
             'consortium', 'collaboration', 'initiative', 'centre', 'center', 'association', 'society', 'committee',
             'council', 'agency', 'network', 'alliance', 'partners', 'trustees', 'research', 'technologies',
             'technology', 'systems', 'platforms', 'challenge', 'challenges', 'organizers', 'organisers',
             'contributors', 'authors', 'author', 'developers', 'press', 'publishing', 'media', 'studio', 'factory',
             'services', 'organization', 'organisation', 'office', 'ministry', 'government', 'programme', 'program',
             'community', 'trust', 'fund', 'museum', 'library', 'hospital'}
CONNECTORS = {'of', 'for', 'in', 'at'}           # "Centre for Robotic Vision": an organisation's name goes on


def name_shaped(text: str) -> bool:
    """Capitalised words, initials, name particles and separators only, with at least one capitalised word: what
    a list of people looks like, and what running text does not."""
    words = [w.strip(MARKS) for w in text.split()]
    words = [w for w in words if w]
    return bool(words) and any(w[0].isupper() for w in words) and all(
        w[0].isupper() or w in PARTICLES for w in words)


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


def rosters(url: str, extract: str) -> list[tuple[int, int]]:
    """The (start, end) of each labelled list of people on a fixed-layout page that still names someone."""
    out = []
    for pages, label, end in ROSTERS:
        if not pages.match(url or ''):
            continue
        for off, window in windows(extract):
            for m in label.finditer(window):
                stop = end.search(window, m.end())
                who = window[m.end():stop.start() if stop else len(window)].strip()
                if who and not who.startswith(NAMES) and name_shaped(who):
                    out.append((off + m.end(), off + m.end() + len(who)))
    return out


def affiliations(extract: str) -> list[tuple[int, int]]:
    """The (start, end) of each run of names right before an "Affiliation:" label that is not redacted: the
    words back from the label while each is capitalised, a name particle or only marks, when they hold a
    capitalised word. Lower-case running text before the label, or none, is no run."""
    out = []
    for off, window in windows(extract):
        for m in AFFILIATION.finditer(window):
            before = window[:m.start()].rstrip()
            if before.endswith(NAMES):
                continue
            words = list(WORD.finditer(before))
            k = len(words)
            while k:
                core = words[k - 1].group().strip(MARKS)
                if core and not core[0].isupper() and core not in PARTICLES:
                    break
                k -= 1
            if k < len(words) and name_shaped(before[words[k].start():]):
                out.append((off + words[k].start(), off + len(before)))
    return out


def author_notes(extract: str) -> list[tuple[int, int]]:
    """The (start, end) of each run of names right before "is with" or "are with" (an author note) that is not
    redacted: the words back from the phrase while each is capitalised, a name particle or only marks, as the
    affiliation rule reads them, except that a number ("Team 2") or a sentence's full stop ends the run; the
    run opens at its first initial and holds a capitalised word after it. Running text before the phrase, or
    none, is no run."""
    def initial(word: str) -> bool:
        return word[0].isupper() and bool(INITIAL.fullmatch(word))
    out = []
    for off, window in windows(extract):
        for m in AUTHOR_NOTE.finditer(window):
            before = window[:m.start()].rstrip()
            if before.endswith(NAMES):
                continue
            words = list(WORD.finditer(before))
            k = len(words)
            while k:
                word = words[k - 1].group()
                core = word.strip(MARKS)
                if core and not core[0].isupper() and core not in PARTICLES:
                    break                                   # running text: "The dataset is with"
                if not core and any(c.isdigit() for c in word):
                    break                                   # a number: "Team 2 is with"
                if word.endswith('.') and not initial(word):
                    break                                   # the end of the sentence before the note
                k -= 1
            while k < len(words) and not initial(words[k].group()):
                k += 1
            if any(not initial(w.group()) and name_shaped(w.group()) for w in words[k + 1:]):
                out.append((off + words[k].start(), off + len(before)))
    return out


def titled(word: str) -> bool:
    """A capitalised word as a name is written: an upper-case letter, then lower-case letters, in each part a
    hyphen or apostrophe joins ("Ada", "Jean-Pierre", "O'Example"). Capitals ("CAPRI"), capitals inside
    ("OpenAI"), digits and lone letters are not."""
    parts = [p for p in re.split(r"[-'’]", word) if p]
    return bool(parts) and any(len(p) > 1 for p in parts) and all(
        p.isalpha() and p[0].isupper() and (len(p) == 1 or p[1:].islower()) for p in parts)


def holder(window: str, pos: int) -> tuple[list, int, bool]:
    """The name words of the holder that starts at `pos`, how many are capitalised, and whether an organisation
    holds it. The run goes on while each word is a capitalised word, an initial, a name particle, a redaction
    token (read past: it holds a name's place) or only marks ("&", "(2022)"); it ends at any other word, after a
    word that ends a sentence ("Example."), or before a label ("Design:") or a word that opens what follows a
    holder (COPY_STOP). A word of ORG_WORDS in the run or ending it, or a connector before a capitalised word
    ("Centre for Robotic Vision", "Problems in Single-Cell Analysis"), makes it an organisation's."""
    def initial(word: str) -> bool:                 # "A.", "J.-P.", "Ch."; not "AI."
        return len(word) > 1 and word[0].isupper() and not word[1].isupper() and bool(INITIAL.fullmatch(word))
    names, capitalised, skip = [], 0, pos
    for w in WORD.finditer(window, pos):
        if w.start() < skip:
            continue
        token = TOKEN.match(window, w.start())
        if token:
            skip = token.end()
            continue
        word = w.group()
        core = word.strip(HOLDER_MARKS)
        if not core:
            continue
        if core.lower() in ORG_WORDS:
            return names, capitalised, True
        if core.lower() in COPY_STOP or word.endswith(':'):
            break
        if initial(word):
            names.append(w)
        elif titled(core):
            names.append(w)
            capitalised += 1
            if word.rstrip(HOLDER_MARKS.replace('.', '')).endswith('.'):
                break                                       # the end of the notice's sentence
        elif core in PARTICLES and names:
            continue
        else:
            after = WORD.search(window, w.end())
            org = core in CONNECTORS and bool(after) and titled(after.group().strip(HOLDER_MARKS))
            return names, capitalised, org
    return names, capitalised, False


def copyrights(extract: str) -> list[tuple[int, int]]:
    """The (start, end) of each copyright notice's holder that names a person and is not redacted (holder()).
    A notice is "©" (or "&copy;"), "Copyright (c)", or "Copyright" or "(c)" before a year or a "by"; its holder
    follows the marks, the years and a "by". The SciPost line "Copyright <names> et al." has neither year nor
    sign: "Copyright" before a holder that "et al." ends is a notice too. "Copyright Notice", "(c) Did you",
    "501(c)(3)" are none. A holder names a person when no organisation holds it and it has two name words, one
    of them capitalised ("Ada Example", "A. Example"), or one capitalised word before "et al."."""
    out = []
    for off, window in windows(extract):
        for m in COPY_MARKS.finditer(window):
            marks = m.group().lower()
            years = COPY_YEARS.match(window, m.end())
            pos = years.end() if years else m.end()
            by = COPY_BY.match(window, pos)
            names, capitalised, org = holder(window, by.end() if by else pos)
            if org or not capitalised:
                continue
            et_al = bool(ET_AL.match(window, names[-1].end()))
            notice = ('©' in marks or '&copy;' in marks or '&#169;' in marks or bool(years) or bool(by)
                      or ('copyright' in marks and ('(c)' in marks or et_al)))
            if notice and (len(names) >= 2 or et_al):
                out.append((off + names[0].start(), off + names[-1].end()))
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
        listed = rosters(record.get('url') or '', extract)
        if listed:
            if cited is None:
                cited = cited_quotes(root)
            listed = [s for s in listed if not quoted(extract, s, cited.get(sid) or [])]
        if listed:
            errors.append('%s: the extract names people in a labelled list %d time(s) (an ACL Anthology '
                          '"Editors:" field or a NeurIPS Datasets and Benchmarks "Authors" list); replace each '
                          'list with [names redacted]' % (sid, len(listed)))
        named = affiliations(extract) if HTML_PAGE.match(record.get('url') or '') else []
        if named:
            if cited is None:
                cited = cited_quotes(root)
            named = [s for s in named if not quoted(extract, s, cited.get(sid) or [])]
        if named:
            errors.append('%s: the extract names authors before an "Affiliation:" label %d time(s) (an arXiv HTML '
                          'byline); replace each run of names with [names redacted]' % (sid, len(named)))
        noted = author_notes(extract)
        if noted:
            if cited is None:
                cited = cited_quotes(root)
            noted = [s for s in noted if not quoted(extract, s, cited.get(sid) or [])]
        if noted:
            errors.append('%s: the extract names authors before "is with" or "are with" %d time(s) (an author '
                          'note); replace each run of names with [names redacted]' % (sid, len(noted)))
        held = copyrights(extract)
        if held:
            if cited is None:
                cited = cited_quotes(root)
            held = [s for s in held if not quoted(extract, s, cited.get(sid) or [])]
        if held:
            errors.append('%s: the extract names a person as copyright holder %d time(s) (a copyright line); '
                          'replace each name with [name redacted], or several with [names redacted]'
                          % (sid, len(held)))
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
    print('OK    no Source extract holds an e-mail address, an unredacted arXiv submitter, an arXiv abs or HTML '
          'byline, a labelled roster on a fixed-layout page, an author note or a copyright line naming a person')
    return 0


if __name__ == '__main__':
    sys.exit(main())
