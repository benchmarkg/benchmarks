"""Migration 0026: reviewer checks leave curation.notes for curation.review_checks (ADR-0026; P0-S9-T05).

The corpus half of ADR-0026. Every curated entry's curation.notes is, and is only, two kinds of block, which the
escape-hatch audit (docs/schema-stress-audit.md) found doing structural work in a free-text field:

  Reviewer checks   "Reviewer checks[ (specialist)]:" then "- " items, or a paragraph "Reviewer check (<scope>):
                    ...". Each becomes one curation.review_checks row: `check` is its text (line breaks folded
                    into spaces, nothing else changed); `field` is the field it names, from the scope or from an
                    item's closing parenthesis when that is a plain dotted path; `specialist` is true under a
                    "(specialist)" heading; a paragraph's "Source: <id>." and "Quote: "<text>"" move into
                    `source` and `quote`, where the quote check verifies them like any other.
  Schema findings   "Schema findings ...:" then numbered items: findings about the schema, not data about the
                    benchmark. They leave the entry; docs/schema-findings-ledger.md records every one, verbatim, with
                    its entry, and was written from the notes before this migration removed them.

Any other paragraph would stay in curation.notes; none exists. With both blocks gone the key is removed.
`plan()` parses the notes as the entry holds them, so a re-run over an applied tree plans nothing.
"""
from __future__ import annotations

import re

from schema.migrations import ABSENT, Row, entity_files

KIND = 'field'
SUMMARY = ('ADR-0026: reviewer checks move from curation.notes into curation.review_checks, and schema findings '
           'leave the entries for docs/schema-findings-ledger.md')

FIELD = re.compile(r'^[a-z_]+(\.[a-z_]+)*$')
LIST_HEAD = re.compile(r'^Reviewer checks(?:\s*\(([^)]*)\))?:\s*$')
ONE_HEAD = re.compile(r'^Reviewer check \(([^)]*)\):\s*')
FINDINGS_HEAD = re.compile(r'^Schema findings\b[^\n]*:\s*$')
SOURCE = re.compile(r'\s*Source: (src-[a-z0-9-]+)\.')
QUOTE = re.compile(r'\s*Quote: "([^"]+)"')
TAIL_FIELD = re.compile(r'\(([a-z_]+(?:\.[a-z_]+)*)\)\.?\s*$')


def fold(text: str) -> str:
    """Line breaks and the indentation after them become one space; the words are untouched."""
    return re.sub(r'\s*\n\s*', ' ', text).strip()


def split_items(block: str) -> list[str]:
    items, current = [], None
    for line in block.split('\n'):
        if line.startswith('- '):
            if current is not None:
                items.append(current)
            current = line[2:]
        elif current is not None:
            current += '\n' + line
    if current is not None:
        items.append(current)
    return [fold(i) for i in items]


def parse(notes: str) -> tuple[list[dict], list[str], list[str]]:
    """(review_checks, schema findings, paragraphs that are neither) for one curation.notes."""
    checks, findings, rest = [], [], []
    for para in re.split(r'\n\s*\n', notes.strip()):
        head, _, body = para.partition('\n')
        m = LIST_HEAD.match(head.strip())
        if m:
            specialist = 'specialist' in (m.group(1) or '')
            for item in split_items(body):
                row = {'check': item}
                tail = TAIL_FIELD.search(item)
                if tail and FIELD.match(tail.group(1)):
                    row['field'] = tail.group(1)
                if specialist:
                    row['specialist'] = True
                checks.append(row)
            continue
        m = ONE_HEAD.match(para.strip())
        if m:
            scope, text = m.group(1), fold(para.strip()[m.end():])
            field, _, term = scope.partition(':')
            row = {}
            source, quote = SOURCE.search(text), QUOTE.search(text)
            if quote:
                text = (text[:quote.start()] + text[quote.end():]).strip()
            if source:
                text = (text[:source.start()] + text[source.end():]).strip()
            row['check'] = '%s: %s' % (term.strip(), text) if term.strip() else text
            if FIELD.match(field.strip()):
                row['field'] = field.strip()
            if source:
                row['source'] = source.group(1)
            if quote:
                row['quote'] = quote.group(1)
            checks.append(row)
            continue
        if FINDINGS_HEAD.match(head.strip()):
            findings += [fold(i) for i in re.split(r'\n(?=\d+\. )', body.strip()) if i.strip()]
            continue
        rest.append(para)
    return checks, findings, rest


def plan(root: str) -> list:
    rows = []
    for rel, doc in entity_files(root, 'benchmarks'):
        if '/_stubs/' in rel or not isinstance(doc, dict):
            continue
        curation = doc.get('curation') or {}
        notes = curation.get('notes')                      # get-default: an entry with no notes plans nothing
        if not isinstance(notes, str):
            continue
        checks, findings, rest = parse(notes)
        if not checks and not findings:
            continue
        old = curation['review_checks'] if 'review_checks' in curation else ABSENT
        rows.append(Row(rel, ('curation', 'review_checks'), old, (old if old is not ABSENT else []) + checks))
        rows.append(Row(rel, ('curation', 'notes'), notes, '\n\n'.join(rest) if rest else ABSENT))
    return rows
