#!/usr/bin/env python3
"""index.sqlite: the normalised corpus, built at build time and never shipped (P2-S1-T06; 08 S4.2, S2 S9; 14 Phase 2).

    bench build --out build/                    # writes build/index.sqlite beside corpus.json (not under --data-only)
    python tools/build/sqlite.py --check DIST   # exit 1 if a built site holds a SQLite file or references index.sqlite

08 S4.2: "`index.sqlite` | The whole corpus, normalised | ... | **Never shipped to the browser.** Build-time analytics +
a citable data release". 14's Phase 2 deliverables say the same: "SQLite is generated at build time for our own
analytics and as a citable release artifact, and never ships to the browser." It is built from the three S8 artifacts
the same build wrote (corpus.json, facets.json, enums.json), with Python's standard sqlite3 module, so it can say
nothing they do not.

What is in it. Every table is listed, with its source and row count, in `_tables`; `_meta` names the sha256 of each
artifact it was built from (the canonical bytes, as build-manifest.json records them), the taxonomy version and the
file's format, which is also PRAGMA user_version.

  benchmark, system,      one row per published record, keyed by `id`. A column for every field the record's model
  organization, metric,   (schema/, through tools/validate/tiers.py KINDS) types as a scalar -- a string, number, bool,
  source                  date or vocabulary Literal -- and, flattened in, every scalar field of a nested model, joined
                          with `__` (`domain__primary`, `data__access`). `record` is the whole record as canonical
                          JSON, so the file is lossless and json_extract() reaches anything the columns do not.
  <kind>__<path>          one table per list the models declare (`benchmark__aliases`, `benchmark__data__size`,
                          `benchmark__versions__errata`): `_row` (its key), `_id` (the record's id), `_parent` (the
                          `_row` of the list item it sits in, null directly under the record), `_position` (0-based),
                          then `value` for a list of scalars, or the item model's own columns, flattened the same way.
                          `_` names cannot collide with a field: pydantic does not allow a field name to start with one.
  facet_row, facet_value  facets.json: each benchmark's index row, and its seven flat facet arrays as (id, facet,
                          position, key), the key enums.json gives every term. A facet's array draws on the
                          vocabularies flat_facet_vocabulary names (data_properties on ceiling_anchor_type too), so
                          a value's term is `term JOIN flat_facet_vocabulary USING (vocabulary)` on facet and key
  subset, subset_facet    corpus.json's materialised subsets (02 S11 rule 4), each resolved facet value a row, with
                          `override` set where the subset declares the facet itself
  vocabulary, term,       enums.json: every controlled vocabulary, its terms in file order, a capability group's
  term_member,            members, and which fields and vocabularies each flat facet array is made of
  flat_facet_field, flat_facet_vocabulary
  reference               every reference a published record makes: the prefixed ids (src-, org-, cond-, ...) and the
                          unprefixed ones the validator resolves (a benchmark's metrics and lineage, a system's
                          built_on), as tools/validate/tiers.py's tier 2 reads them

What the models do not type as a scalar, a model or a list of either is not split into columns, and is in `record`:
a map keyed by vocabulary ids (`capability_basis`), a union of a value and a model (`data.access_basis`, a string or
a Basis), `metrics` (a list or a mapping), and any field a curator added beyond the model. The column set is
therefore the models', not the data's: a new curated note adds nothing to a table shape, and a table shape changes
only with schema/, which 08 S4.5 allows between majors.

Not in it: claims. 08 S4.2's corpus has "No claim records"; facet_row carries the claim-derived aggregates facets.json
does. P4-S7-T01 builds the release from this and adds its hash to build-manifest.json; nothing does so yet, so
index.sqlite is not in the manifest, whose /data/ files are the shipped ones.

Never shipped. bench build writes it into --out beside corpus.json, and nothing copies --out into the site: the site
reads build/ at build time, and only site/public/ and what Astro renders reach dist/. `write` refuses a path under
site/, where public/ would ship it. `dist_problems` (and --check) is the assertion over a built site: no file under it
is a SQLite database (by name or by its header) and none references index.sqlite -- a URL attribute, any host-less
path ending in it, or a whole string, attribute value or CSS url() naming it, in a page or any other text file. A
URL with a host is not ours (no host is fixed yet, as tools/build/manifest.py says), and prose is not a reference:
/api/ names "index.sqlite and the data tarball" as what the release archive holds.

Determinism (08 S6): built in memory in a fixed order -- records by id as corpus.json has them, list items in order,
no clock -- then written with VACUUM INTO, so two builds of one tree with one SQLite library are byte-identical. The
library's version is in the file's header, as any tool version is in the manifest.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import enum
import hashlib
import json
import os
import re
import sqlite3
import sys
import types
import typing
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

NAME = 'index.sqlite'
FORMAT = 1
MAGIC = b'SQLite format 3\x00'                        # the first 16 bytes of every SQLite database file
DB_SUFFIXES = ('.sqlite', '.sqlite3', '.db')
KINDS = ('benchmark', 'system', 'organization', 'metric', 'source')   # corpus.json's entities (artifacts.CORPUS_KINDS)
AFFINITY = {str: 'TEXT', datetime.date: 'TEXT', datetime.datetime: 'TEXT', int: 'INTEGER', bool: 'INTEGER',
            float: 'REAL'}
FACET_ROW_TYPES = {'year': 'INTEGER', 'claim_count': 'INTEGER', 'condition_completeness_max': 'REAL',
                   'headroom': 'REAL'}            # every other facets.json scalar is TEXT
SITE = os.path.join(ROOT, 'site')


class SqliteError(Exception):
    """index.sqlite cannot be built or written; `bench build` stops on it."""


# ---- the models' shapes -------------------------------------------------------------------------

def _strip(ann):
    """Annotated[X, ...] and Optional[X] -> X."""
    while True:
        origin = typing.get_origin(ann)
        if origin is typing.Annotated:
            ann = typing.get_args(ann)[0]
            continue
        if origin in (typing.Union, types.UnionType):
            args = [a for a in typing.get_args(ann) if a is not type(None)]
            if len(args) == 1:
                ann = args[0]
                continue
        return ann


def _affinity(found: set[str]) -> str:
    """One column affinity for a scalar union: its one affinity, REAL for int-or-float, else none ('')."""
    if len(found) == 1:
        return next(iter(found))
    return 'REAL' if found == {'INTEGER', 'REAL'} else ''


def scalar(ann) -> str | None:
    """The column affinity of an annotation that is a scalar ('' for a scalar of mixed affinity), else None."""
    ann = _strip(ann)
    origin = typing.get_origin(ann)
    if origin is typing.Literal:
        return _affinity({AFFINITY.get(type(v), '') for v in typing.get_args(ann)})  # get-default: a Literal of None or an enum member has no affinity
    if ann in AFFINITY:
        return AFFINITY[ann]
    if isinstance(ann, type) and issubclass(ann, enum.Enum):
        return 'TEXT' if issubclass(ann, str) else ''
    if origin in (typing.Union, types.UnionType):
        parts = [scalar(a) for a in typing.get_args(ann) if a is not type(None)]
        return None if any(p is None for p in parts) else _affinity(set(parts))
    return None


def model_of(ann):
    from pydantic import BaseModel
    ann = _strip(ann)
    return ann if isinstance(ann, type) and issubclass(ann, BaseModel) else None


@dataclasses.dataclass(frozen=True)
class Column:
    name: str                           # the path joined with `__`
    affinity: str
    path: tuple[str, ...]               # dump keys, from the table's object


@dataclasses.dataclass
class Table:
    name: str
    parent: str | None                  # None for a record table
    source: str                         # where its rows come from, for _tables
    path: tuple[str, ...] = ()          # a list table's path from its parent's object
    item: str = ''                      # a list table's items: scalar, model or both (a scalar or a model)
    value: str = ''                     # the `value` column's affinity, for scalar items
    columns: list[Column] = dataclasses.field(default_factory=list)
    children: list['Table'] = dataclasses.field(default_factory=list)


def _list_item(ann) -> tuple[str, str, type | None] | None:
    """A list annotation's items: (scalar|model|both, the scalar affinity, the model), or None if it is not one."""
    ann = _strip(ann)
    if typing.get_origin(ann) is not list or not typing.get_args(ann):
        return None
    item = _strip(typing.get_args(ann)[0])
    if scalar(item) is not None:
        return 'scalar', scalar(item), None
    if model_of(item) is not None:
        return 'model', '', model_of(item)
    if typing.get_origin(item) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(item) if a is not type(None)]
        models = [model_of(a) for a in args if model_of(a) is not None]
        scalars = [scalar(a) for a in args if model_of(a) is None]
        if len(models) == 1 and scalars and None not in scalars:
            return 'both', _affinity(set(scalars)), models[0]
    return None


def layout(model, table: Table, prefix: tuple[str, ...] = (), seen: tuple = ()) -> None:
    """Add `model`'s scalar fields to `table` as columns, under `prefix`, and its lists as child tables. A model that
    contains itself is left to `record`, so the recursion ends."""
    if model in seen:
        return
    for name, info in model.model_fields.items():
        key = info.serialization_alias or info.alias or name
        path = prefix + (key,)
        if scalar(info.annotation) is not None:
            table.columns.append(Column('__'.join(path), scalar(info.annotation), path))
        elif model_of(info.annotation) is not None:
            layout(model_of(info.annotation), table, path, seen + (model,))
        elif _list_item(info.annotation) is not None:
            kind, affinity, item_model = _list_item(info.annotation)
            if item_model is not None and (item_model in seen or item_model is model):
                continue
            child = Table('%s__%s' % (table.name, '__'.join(path)), table.name, '%s.%s[]' % (table.source, '.'.join(path)),
                          path, kind, affinity)
            if item_model is not None:
                layout(item_model, child, (), seen + (model,))
            table.children.append(child)


def record_tables() -> list[Table]:
    """The record table of each corpus kind, its columns and its list tables, from the models alone."""
    from tools.validate import tiers
    models = {k.name: k.model for k in tiers.KINDS.values()}
    out = []
    for kind in KINDS:
        t = Table(kind, None, 'corpus.json entities.%s[]' % kind)
        layout(models[kind], t)
        if [c.name for c in t.columns[:1]] != ['id']:
            raise SqliteError('schema/: the %s model\'s first field is not `id`, which its table is keyed by' % kind)
        out.append(t)
    return out


def walk(t: Table):
    yield t
    for c in t.children:
        yield from walk(c)


# ---- building -----------------------------------------------------------------------------------

def q(name: str) -> str:
    return '"%s"' % name.replace('"', '""')


def canonical(x) -> str:
    """08 S6's canonical JSON (emit.serialise) without its trailing newline."""
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha256(doc: dict) -> str:
    from tools.build import emit
    return 'sha256:' + hashlib.sha256(emit.serialise(doc)).hexdigest()


def dig(obj, path: tuple[str, ...]):
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def cell(value, where: str):
    """A scalar as SQLite stores it; anything else means a model and its dump disagree."""
    if value is None or isinstance(value, (str, int, float)):
        return value
    raise SqliteError('%s: %r is typed as a scalar by its model, but is not one' % (where, value))


class Writer:
    """The tables and rows, in the order they are created and inserted."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self.tables: list[tuple[str, str | None, str]] = []    # (name, parent, source), for _tables
        self.rows: dict[str, int] = {}

    def create(self, name: str, columns: list[tuple[str, str]], parent: str | None, source: str, key: str = ''):
        cols = ['%s %s' % (q(n), a) if a else q(n) for n, a in columns] + ([key] if key else [])
        self.con.execute('CREATE TABLE %s (%s)' % (q(name), ', '.join(cols)))
        self.tables.append((name, parent, source))
        self.rows[name] = 0

    def insert(self, name: str, rows: list[tuple]):
        if rows:
            self.con.executemany('INSERT INTO %s VALUES (%s)' % (q(name), ', '.join('?' * len(rows[0]))), rows)
        self.rows[name] += len(rows)

    def index(self, name: str, *columns: str):
        self.con.execute('CREATE INDEX %s ON %s (%s)' % (q('%s.%s' % (name, '+'.join(columns))), q(name),
                                                          ', '.join(q(c) for c in columns)))


def _create_list(w: Writer, t: Table):
    cols = [('_row', 'INTEGER PRIMARY KEY'), ('_id', 'TEXT NOT NULL'), ('_parent', 'INTEGER'),
            ('_position', 'INTEGER NOT NULL')]
    cols += [('value', t.value)] if t.item in ('scalar', 'both') else []
    w.create(t.name, cols + [(c.name, c.affinity) for c in t.columns], t.parent, t.source)
    for c in t.children:
        _create_list(w, c)


def _fill_lists(t: Table, obj: dict, ident: str, parent_row: int | None, rows: dict[str, list], where: str):
    for child in t.children:
        items = dig(obj, child.path)
        if items is None:
            continue
        if not isinstance(items, list):
            raise SqliteError('%s.%s: the model declares a list, but the record holds %r'
                              % (where, '.'.join(child.path), items))
        for i, item in enumerate(items):
            here = '%s.%s[%d]' % (where, '.'.join(child.path), i)
            row_id = len(rows[child.name]) + 1
            row = [row_id, ident, parent_row, i]
            if child.item in ('scalar', 'both'):
                row.append(None if isinstance(item, dict) else cell(item, here))
            if child.item == 'model' and not isinstance(item, dict):
                raise SqliteError('%s: the model declares a record here, but the list holds %r' % (here, item))
            fields = item if isinstance(item, dict) else {}
            row += [cell(dig(fields, c.path), '%s.%s' % (here, '.'.join(c.path))) for c in child.columns]
            rows[child.name].append(tuple(row))
            if isinstance(item, dict):
                _fill_lists(child, item, ident, row_id, rows, here)


def _records(w: Writer, entities: dict[str, list[dict]]):
    for t in record_tables():
        w.create(t.name, [(c.name, c.affinity) for c in t.columns] + [('record', 'TEXT NOT NULL')], None, t.source,
                 'PRIMARY KEY ("id")')
        for c in t.children:
            _create_list(w, c)
        rows: dict[str, list] = {x.name: [] for x in walk(t)}
        for rec in entities[t.name]:
            where = '%s %s' % (t.name, rec['id'])
            rows[t.name].append(tuple(cell(dig(rec, c.path), '%s.%s' % (where, '.'.join(c.path))) for c in t.columns)
                                + (canonical(rec),))
            _fill_lists(t, rec, rec['id'], None, rows, where)
        for x in walk(t):
            w.insert(x.name, rows[x.name])
            if x.parent is not None:
                w.index(x.name, '_id')
                w.index(x.name, '_parent')


def _facets(w: Writer, facets: dict):
    from tools.build import emit
    scalars = [k for k in emit.FACET_ROW if k not in ('aliases', 'facets')]
    w.create('facet_row', [(k, FACET_ROW_TYPES.get(k, 'TEXT')) for k in scalars], 'benchmark',   # get-default: a facets.json scalar not listed there is text
             'facets.json benchmarks[]', 'PRIMARY KEY ("id")')
    w.create('facet_value', [('id', 'TEXT NOT NULL'), ('facet', 'TEXT NOT NULL'), ('position', 'INTEGER NOT NULL'),
                             ('key', 'TEXT NOT NULL')], 'facet_row', 'facets.json benchmarks[].facets.*[]',
             'PRIMARY KEY ("id", "facet", "position")')
    w.insert('facet_row', [tuple(cell(r[k], 'facets.json %s.%s' % (r['id'], k)) for k in scalars)
                           for r in facets['benchmarks']])
    w.insert('facet_value', [(r['id'], facet, i, key) for r in facets['benchmarks']
                             for facet, keys in r['facets'].items() for i, key in enumerate(keys)])
    w.index('facet_value', 'facet', 'key')


def _subsets(w: Writer, subsets: list[dict]):
    w.create('subset', [('benchmark', 'TEXT NOT NULL'), ('id', 'TEXT NOT NULL'), ('parent', 'TEXT'),
                        ('label', 'TEXT'), ('depth', 'INTEGER')], 'benchmark', 'corpus.json subsets[]',
             'PRIMARY KEY ("benchmark", "id")')
    w.create('subset_facet', [('benchmark', 'TEXT NOT NULL'), ('subset', 'TEXT NOT NULL'), ('facet', 'TEXT NOT NULL'),
                              ('position', 'INTEGER NOT NULL'), ('value', 'TEXT'), ('override', 'INTEGER NOT NULL')],
             'subset', 'corpus.json subsets[].facets', 'PRIMARY KEY ("benchmark", "subset", "facet", "position")')
    rows, values = [], []
    for s in subsets:
        rows.append((s['benchmark'], s['id'], s['parent'], s['label'], s['depth']))
        for facet, v in s['facets'].items():
            parts = [('%s.%s' % (facet, k), sub) for k, sub in v.items()] if isinstance(v, dict) else [(facet, v)]
            for name, sub in parts:
                for i, item in enumerate(sub if isinstance(sub, list) else [] if sub is None else [sub]):
                    values.append((s['benchmark'], s['id'], name, i, cell(item, 'subset %s.%s' % (s['id'], name)),
                                   int(facet in s['overrides'])))
    w.insert('subset', rows)
    w.insert('subset_facet', values)


def _enums(w: Writer, enums: dict):
    w.create('vocabulary', [('name', 'TEXT NOT NULL'), ('file', 'TEXT'), ('facet_kind', 'TEXT'), ('version', 'TEXT'),
                            ('gloss', 'TEXT')], None, 'enums.json vocabularies', 'PRIMARY KEY ("name")')
    term_cols = ('id', 'key', 'label', 'status', 'gloss', 'field', 'parent', 'rank', 'machine_assignable')
    w.create('term', [('vocabulary', 'TEXT NOT NULL'), ('position', 'INTEGER NOT NULL')]
             + [(c, 'INTEGER' if c in ('rank', 'machine_assignable') else 'TEXT') for c in term_cols],
             'vocabulary', 'enums.json vocabularies.*.terms[]', 'PRIMARY KEY ("vocabulary", "position")')
    w.create('term_member', [('vocabulary', 'TEXT NOT NULL'), ('term', 'TEXT NOT NULL'), ('position', 'INTEGER NOT NULL'),
                             ('member', 'TEXT NOT NULL')], 'term', 'enums.json vocabularies.*.terms[].members[]',
             'PRIMARY KEY ("vocabulary", "term", "position")')
    w.create('flat_facet_field', [('facet', 'TEXT NOT NULL'), ('position', 'INTEGER NOT NULL'), ('field', 'TEXT NOT NULL')],
             None, 'enums.json flat_facets.*.fields[]', 'PRIMARY KEY ("facet", "position")')
    w.create('flat_facet_vocabulary', [('facet', 'TEXT NOT NULL'), ('position', 'INTEGER NOT NULL'),
                                       ('vocabulary', 'TEXT NOT NULL')], None, 'enums.json flat_facets.*.vocabularies[]',
             'PRIMARY KEY ("facet", "position")')
    vocab = enums['vocabularies']
    w.insert('vocabulary', [(n, v['file'], v['facet_kind'], v['version'], v['gloss']) for n, v in vocab.items()])
    w.insert('term', [(n, i) + tuple(cell(t.get(c), 'enums.json %s.%s' % (n, t['id'])) for c in term_cols)
                      for n, v in vocab.items() for i, t in enumerate(v['terms'])])
    w.insert('term_member', [(n, t['id'], i, m) for n, v in vocab.items() for t in v['terms']
                             for i, m in enumerate(t.get('members') or [])])
    w.insert('flat_facet_field', [(f, i, x) for f, v in enums['flat_facets'].items() for i, x in enumerate(v['fields'])])
    w.insert('flat_facet_vocabulary', [(f, i, x) for f, v in enums['flat_facets'].items()
                                       for i, x in enumerate(v['vocabularies'])])
    w.index('term', 'key')


def references(kind: str, rec: dict) -> list[tuple[str, str, str]]:
    """(field, target kind, target) for every reference one published record makes, in tier 2's terms."""
    from tools.validate import tiers
    model = {k.name: k for k in tiers.KINDS.values()}[kind]
    seen: dict[tuple, None] = {}
    for field, value, target in tiers._walk_prefixed(rec, ''):
        seen[(field, target, value)] = None
    for field, target, value in tiers._typed_refs(tiers.Record('', '', model, rec, None, True)):
        seen[(field, target, value)] = None
    return list(seen)


def _references(w: Writer, entities: dict[str, list[dict]]):
    w.create('reference', [('kind', 'TEXT NOT NULL'), ('id', 'TEXT NOT NULL'), ('field', 'TEXT NOT NULL'),
                           ('target_kind', 'TEXT NOT NULL'), ('target', 'TEXT NOT NULL')], None,
             'corpus.json entities: each record\'s references (tools/validate/tiers.py)',
             'PRIMARY KEY ("kind", "id", "field", "target_kind", "target")')
    w.insert('reference', [(kind, rec['id']) + ref for kind in KINDS for rec in entities[kind]
                           for ref in references(kind, rec)])
    w.index('reference', 'target_kind', 'target')


def build(artifacts: dict[str, dict]) -> sqlite3.Connection:
    """index.sqlite in memory, from the three S8 artifacts (file name -> artifact)."""
    missing = [n for n in ('corpus.json', 'facets.json', 'enums.json') if not artifacts.get(n)]
    if missing:
        raise SqliteError('index.sqlite is built from the S8 artifacts, and %s was not built' % ', '.join(missing))
    corpus, facets, enums = artifacts['corpus.json'], artifacts['facets.json'], artifacts['enums.json']
    con = sqlite3.connect(':memory:')
    con.execute('PRAGMA page_size = 4096')
    con.execute("PRAGMA encoding = 'UTF-8'")
    con.execute('PRAGMA user_version = %d' % FORMAT)
    w = Writer(con)
    w.create('_meta', [('key', 'TEXT NOT NULL'), ('value', 'TEXT')], None, 'this file', 'PRIMARY KEY ("key")')
    w.create('_tables', [('name', 'TEXT NOT NULL'), ('parent', 'TEXT'), ('source', 'TEXT NOT NULL'),
                         ('rows', 'INTEGER NOT NULL')], None, 'this file', 'PRIMARY KEY ("name")')
    with con:
        _records(w, corpus['entities'])
        _subsets(w, corpus['subsets'])
        _facets(w, facets)
        _enums(w, enums)
        _references(w, corpus['entities'])
        w.insert('_meta', [('artifact', 'index'), ('format', str(FORMAT)),
                           ('corpus.json', sha256(corpus)), ('facets.json', sha256(facets)), ('enums.json', sha256(enums)),
                           ('formats', canonical({n: d.get('format') for n, d in sorted(artifacts.items())})),
                           ('taxonomy', enums['taxonomy']), ('drafts', 'true' if corpus.get('drafts') else 'false'),
                           ('served', 'never to a browser (08 S4.2): build-time analytics and the release archive')])
        listing = [(name, parent, source, len(w.tables) if name == '_tables' else w.rows[name])
                   for name, parent, source in w.tables]
        w.insert('_tables', listing)
    return con


def write(artifacts: dict[str, dict], path: str) -> str:
    """Build index.sqlite and write it to `path`, which may not be under site/: public/ is copied into dist/, and
    anything else there is the site's source. A draft preview's corpus is refused: 05 S4 never publishes a draft, and
    this is a release artifact."""
    full = os.path.realpath(path)
    if full == os.path.realpath(SITE) or full.startswith(os.path.realpath(SITE) + os.sep):
        raise SqliteError('%s is under site/, from where it could reach dist/; index.sqlite never ships (08 S4.2)' % path)
    if (artifacts.get('corpus.json') or {}).get('drafts'):
        raise SqliteError('corpus.json is a draft preview (scripts/preview_corpus.py); index.sqlite is a release '
                          'artifact and holds no ai-drafted-unverified entry (05 S4)')
    con = build(artifacts)
    os.makedirs(os.path.dirname(full) or '.', exist_ok=True)
    tmp = full + '.tmp'
    if os.path.exists(tmp):
        os.remove(tmp)
    try:
        con.execute('VACUUM INTO ?', (tmp,))
    finally:
        con.close()
    os.replace(tmp, full)
    return path


# ---- never shipped ------------------------------------------------------------------------------

URL_ATTRS = frozenset({'href', 'src', 'srcset', 'imagesrcset', 'action', 'formaction', 'poster', 'data', 'cite',
                       'background', 'manifest', 'content'})
TOKEN = re.compile(r'[^\s"\'`<>()\\,;{}\[\]|^]*index\.sqlite(?![\w])[^\s"\'`<>()\\,;{}\[\]|^]*')
QUOTES = '"\'`'


def _ours(token: str) -> str | None:
    """The host-less path `token` names, when its last segment is index.sqlite; None otherwise."""
    parts = urlsplit(token)
    if parts.scheme or parts.netloc:
        return None
    path = unquote(parts.path)
    return path if path.rsplit('/', 1)[-1] == NAME else None


def text_refs(text: str) -> list[str]:
    """Every reference to index.sqlite in a text: a host-less path ending in it, or a whole quoted string or CSS url()
    that is its bare name (not an object key: `"index.sqlite": ...`)."""
    out = []
    for m in TOKEN.finditer(text):
        path = _ours(m.group(0))
        if path is None:
            continue
        before, after = text[m.start() - 1:m.start()] if m.start() else '', text[m.end():m.end() + 1]
        whole = bool(before) and before in QUOTES and after == before and not re.match(r'\s*:', text[m.end() + 1:])
        url = re.search(r'url\(\s*["\']?$', text[max(0, m.start() - 8):m.start()]) is not None
        if '/' in path or whole or url:
            out.append(m.group(0))
    return out


class _Page(HTMLParser):
    """A page's URL attributes, its other attribute values, and its script and style bodies; never its prose."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []
        self.values: list[str] = []
        self.code: list[str] = []
        self._in: str | None = None

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value is None:
                continue
            if key in URL_ATTRS:
                self.urls += [c.strip().split()[0] for c in value.split(',') if c.strip()] if key.endswith('srcset') \
                    else [value.strip()]
            self.values.append(value)
        if tag in ('script', 'style'):
            self._in = tag

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self._in = None

    def handle_endtag(self, tag):
        if tag == self._in:
            self._in = None

    def handle_data(self, data):
        if self._in is not None:
            self.code.append(data)


def page_refs(html: str) -> list[str]:
    p = _Page()
    p.feed(html)
    p.close()
    out = [u for u in p.urls if _ours(u) is not None]
    for value in p.values:
        out += [value.strip()] if value.strip() == NAME else text_refs(value)
    for body in p.code:
        out += text_refs(body)
    return out


def dist_problems(dist: str) -> list[str]:
    """Every way a built site under `dist` ships index.sqlite: a SQLite file, or a file that references it."""
    if not os.path.isdir(dist):
        return ['%s is not a built site' % dist]
    problems = []
    for folder, dirs, names in os.walk(dist):
        dirs.sort()
        for n in sorted(names):
            full = os.path.join(folder, n)
            rel = os.path.relpath(full, dist).replace(os.sep, '/')
            with open(full, 'rb') as fh:
                raw = fh.read()
            if n.lower().endswith(DB_SUFFIXES) or raw.startswith(MAGIC):
                problems.append('%s: a SQLite database file under the site; index.sqlite never ships (08 S4.2)' % rel)
                continue
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                continue                            # a font, an image, a compressed search fragment: no text to refer
            refs = page_refs(text) if n.endswith('.html') else text_refs(text)
            for ref in dict.fromkeys(refs):
                problems.append('%s: references %s, which never ships (08 S4.2)' % (rel, ref))
    return problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--check', metavar='DIST', required=True, help='a built site: fail if it ships index.sqlite')
    a = p.parse_args(argv)
    problems = dist_problems(a.check)
    for line in problems:
        print('BLOCKING  sqlite  %s' % line)
    print('sqlite: %s ships %s' % (a.check, 'no SQLite file and no reference to %s' % NAME if not problems
                                   else '%d problem(s)' % len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
