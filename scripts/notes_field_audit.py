#!/usr/bin/env python3
"""The schema review's machine input (P1-S3-T04): free-text notes, empty full-required fields, unused fields.

14-roadmap's Phase 0 test says "a `notes` field doing structural work is the tell" that the schema is wrong, and
the 20-entry checkpoint's step 2 asks what the first twenty entries wrote in a notes field that should have
been structured. Whether a given note is structural or editorial is a person's judgement; this script only lays
out the material for it, deterministically, from the curated corpus:

    python scripts/notes_field_audit.py                       # the three lists, as text
    python scripts/notes_field_audit.py --json                # the same, as JSON
    python scripts/notes_field_audit.py --section notes       # one list: notes | nulls | unused
    python scripts/notes_field_audit.py --root DIR            # another tree (the tests do)

notes   Every free-text note in every curated Benchmark (data/benchmarks/<family>/*.yaml, not _stubs): a key
        named `notes`, or ending in `_note` or `_notes`, at any depth, with its dotted path, its text, and the
        fields beside it in the same mapping (their values abbreviated), because a note is judged by what it
        sits next to: a `data.access_note` beside `access: fully-open` that says "gated on Hugging Face" is
        doing structural work. `*_basis` blocks are not notes: their reason sits beside a source and a quote.
nulls   For every field 04-data-model.md's Benchmark field reference marks "Required at: full", the entries that
        leave it absent (where the table's default is none, null or an empty list), null, or empty. The table is parsed from
        _plan/04-data-model.md, so a field the table names and the model lacks (a planned field never built)
        shows as absent in every entry, which is itself a finding.
unused  Every field of the Benchmark model, and of its nested blocks one level down, that no curated entry sets
        to a non-empty value. (Derived fields are not model fields -- a file carrying one is rejected -- so
        they do not appear.)

Exit codes: 0 ok; 2 no curated entries were found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import types
import typing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELD_REFERENCE = os.path.join('_plan', '04-data-model.md')
TABLE_HEADING = '### Benchmark field reference'
NOTE_KEY = re.compile(r'^(notes|.+_notes?)$')
BRIEF = 80


def entries(root):
    """(relative path, document) for every curated Benchmark file under root, in path order."""
    sys.path.insert(0, ROOT)
    from schema.stub import curated_benchmark_files
    from schema.taxonomy import read_yaml
    out = []
    for p in sorted(curated_benchmark_files(root)):
        doc = read_yaml(p)
        if isinstance(doc, dict):
            out.append((os.path.relpath(p, root).replace(os.sep, '/'), doc))
    return out


def brief(v):
    if isinstance(v, dict):
        return '{%d keys}' % len(v)
    if isinstance(v, list):
        return '[%d items]' % len(v)
    s = ' '.join(str(v).split())
    return s if len(s) <= BRIEF else s[:BRIEF - 1] + '…'


def notes(docs):
    """Every free-text note, with its path and the fields beside it."""
    out = []

    def walk(node, path, entry):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and NOTE_KEY.match(str(k)):
                    out.append({'entry': entry, 'path': '.'.join(path + [str(k)]), 'text': ' '.join(v.split()),
                                'beside': {str(s): brief(w) for s, w in node.items()
                                           if s != k and not NOTE_KEY.match(str(s))}})
                else:
                    walk(v, path + [str(k)], entry)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)], entry)
    for rel, doc in docs:
        walk(doc, [], doc.get('id', rel))   # get-default: an id-less file is named by its path
    return out


def full_required(root):
    """[(field, has_filling_default)] for the field reference rows marked Required at: full."""
    path = os.path.join(root, FIELD_REFERENCE)
    if not os.path.exists(path):
        path = os.path.join(ROOT, FIELD_REFERENCE)
    text = open(path, encoding='utf-8').read()
    start = text.index(TABLE_HEADING)
    out = []
    for line in text[start:].split('\n')[1:]:
        if line.startswith('---') or line.startswith('## '):
            break
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 6 or not cells[0].startswith('`'):
            continue
        field = cells[0].strip('`')
        if field.endswith('.*') or not cells[2].startswith('full'):
            continue
        # Absent means the table's default: no default, null or an empty list all leave the field unfilled.
        unfilled_by_default = cells[4] in ('—', '-', '', '`null`', '`[]`')
        out.append((field.replace('[]', ''), not unfilled_by_default))
    return out


def lookup(doc, dotted):
    node = doc
    for part in dotted.split('.'):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def nulls(docs, required):
    """For each full-required field: the entries that leave it absent (no default), null, or empty."""
    out = []
    for field, has_default in required:
        missing = []
        for rel, doc in docs:
            present, v = lookup(doc, field)
            how = ('absent' if not present and not has_default else 'null' if present and v is None
                   else 'empty' if present and v in ([], {}, '') else None)
            if how:
                missing.append({'entry': doc.get('id', rel), 'how': how})   # get-default: as in notes()
        out.append({'field': field, 'default_in_table': has_default, 'missing': missing, 'of': len(docs)})
    return out


def _models(annotation):
    """The pydantic model classes inside an annotation (Optional, Union, list), not descending into lists."""
    from pydantic import BaseModel
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        return [m for a in typing.get_args(annotation) for m in _models(a)]
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return []


def schema_fields():
    """Dotted Benchmark field names, one level into nested blocks, with whether each is derived."""
    sys.path.insert(0, ROOT)
    from schema.benchmark import Benchmark
    derived = {'maintenance_status', 'curation.stewardship', 'execution.inspect_evals_available'}  # if ever modelled
    out = []
    for name, f in Benchmark.model_fields.items():
        out.append(name)
        for m in _models(f.annotation):
            out.extend('%s.%s' % (name, sub) for sub in m.model_fields)
    return [(n, n in derived) for n in out]


def unused(docs, fields):
    """The schema fields no curated entry sets to a non-empty value."""
    out = []
    for name, derived in fields:
        used = sum(1 for _, doc in docs if lookup(doc, name)[0] and lookup(doc, name)[1] not in (None, [], {}, ''))
        if not used:
            out.append({'field': name, 'derived': derived})
    return out


def build(root):
    docs = entries(root)
    return {'entries': len(docs), 'notes': notes(docs), 'nulls': nulls(docs, full_required(root)),
            'unused': unused(docs, schema_fields())}


def render(rep, section=None):
    lines = []
    if section in (None, 'notes'):
        lines.append('== notes: %d free-text notes in %d entries' % (len(rep['notes']), rep['entries']))
        for n in rep['notes']:
            lines.append('%s  %s' % (n['entry'], n['path']))
            lines.append('    text:   %s' % n['text'])
            if n['beside']:
                lines.append('    beside: %s' % '; '.join('%s=%s' % kv for kv in n['beside'].items()))
    if section in (None, 'nulls'):
        lines.append('== nulls: fields 04 requires at full, left absent, null or empty')
        for r in rep['nulls']:
            if r['missing']:
                lines.append('%s  %d of %d  %s' % (r['field'], len(r['missing']), r['of'],
                                                   ', '.join('%s (%s)' % (m['entry'], m['how']) for m in r['missing'])))
    if section in (None, 'unused'):
        lines.append('== unused: schema fields no entry sets')
        for u in rep['unused']:
            lines.append('%s%s' % (u['field'], '  (derived: never hand-written)' if u['derived'] else ''))
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--json', action='store_true')
    p.add_argument('--section', choices=('notes', 'nulls', 'unused'))
    a = p.parse_args(argv)
    rep = build(a.root)
    if not rep['entries']:
        print('no curated entries under %s' % a.root, file=sys.stderr)
        return 2
    if a.section:
        rep = {'entries': rep['entries'], a.section: rep[a.section]}
    print(json.dumps(rep, indent=2, ensure_ascii=False) if a.json else render(rep, a.section))
    return 0


if __name__ == '__main__':
    sys.exit(main())
