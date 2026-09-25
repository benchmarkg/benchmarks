"""`bench fmt [paths...] [--check]` and the project's YAML emitter (P0-S5-T04; 05 S1, S3, S9 job 1; 07 S1.5).

    bench fmt                   # normalise every YAML file under data/ in place
    bench fmt data/sources/     # or only these files or directories
    bench fmt --check           # write nothing; exit 1 if any file would change (05 S9 job 1)

05 S1's cosmetic-diff mitigation: "`bench fmt` normalises key order, quoting, line width and list
style; CI fails on any file `bench fmt` would change". 07 S1.5 fixes the emitter, "specified once and
shared by `bench fmt` and every adapter" -- it names the module tools/emit.py; it lives here, the one
module this task creates, and an adapter imports `emitter()` and `dumps()` from tools.fmt.

  - ruamel.yaml round-trip, width 100, allow_unicode, preserve_quotes False: a string is quoted only
    when YAML needs it, so two editors' quoting habits converge;
  - block style for every non-empty mapping and sequence (`[]` and `{}` stay flow, which is the only
    way to write them), indented mapping 2 / sequence 4 / offset 2, the style the corpus already uses;
  - key order is the Pydantic model's field order (07: "not alphabetical and not insertion order").
    An annotation (`<field>_note|_notes|_caveat|_basis|_source|_quote`) follows the field it qualifies;
    deferred and other keys the model does not declare follow the fields, in their original order.
    Keys of a data-keyed mapping (`capability_basis`, a deferred dict) keep their order. A file with
    no entity model (data/surveys/, data/tombstones/) is normalised in style but not reordered;
  - floats as repr(round(x, 6)), `null` for None, LF, no trailing whitespace, exactly one final newline.
    Rounding strips float noise (0.7870000000000001 -> 0.787); a float with real digits past the
    sixth decimal place is refused rather than rounded, because that rounding would change the data.

Comments move with the key they precede. ruamel stores a comment on the value BEFORE it, so a reorder
first lifts each key's leading comment lines off its predecessor, then re-attaches them to whatever
precedes the key in the new order. The lines that open a mapping stay at its head: at the top of a
file they are the file header, not the first key's. A key that moves to the front of a list item's
mapping takes its comment above the item. A flow collection written in block style takes the lines
that followed it to after its last item, where ruamel had kept them on its key. Two guards run on every file before anything is
written, and a failure is an error, never a silent write: the data must load identically before and
after (formatting never changes a value), and every comment line must still be present.
"""
from __future__ import annotations

import inspect
import io
import os
import types
import typing
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, RootModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.scalarbool import ScalarBoolean
from ruamel.yaml.scalarfloat import ScalarFloat
from ruamel.yaml.scalarint import ScalarInt
from ruamel.yaml.scalarstring import FoldedScalarString, LiteralScalarString
from ruamel.yaml.tokens import CommentToken

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATHS = ('data',)


class FmtError(ValueError):
    pass


# ---- the emitter (07 S1.5) ----------------------------------------------------------------------

def _float(representer, x: float):
    if x != x:
        return representer.represent_scalar('tag:yaml.org,2002:float', '.nan')
    if x in (float('inf'), float('-inf')):
        return representer.represent_scalar('tag:yaml.org,2002:float', '.inf' if x > 0 else '-.inf')
    return representer.represent_scalar('tag:yaml.org,2002:float', repr(round(x, 6)))


def _none(representer, _):
    return representer.represent_scalar('tag:yaml.org,2002:null', 'null')


def emitter() -> YAML:
    y = YAML()
    y.default_flow_style = False
    y.allow_unicode = True
    y.width = 100
    y.preserve_quotes = False
    y.indent(mapping=2, sequence=4, offset=2)
    y.representer.add_representer(float, _float)
    y.representer.add_representer(type(None), _none)
    return y


def dumps(node) -> str:
    buf = io.StringIO()
    emitter().dump(node, buf)
    return _tidy(buf.getvalue())


def _tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.replace('\r\n', '\n').split('\n')]
    return '\n'.join(lines).rstrip('\n') + '\n'


# ---- which model a node is ----------------------------------------------------------------------

def shapes(tp) -> list[tuple]:
    """The container shapes an annotation admits: ('model', M), ('list', inner) or ('dict', inner)."""
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        return shapes(typing.get_args(tp)[0])
    if origin in (typing.Union, types.UnionType):
        return [s for a in typing.get_args(tp) for s in shapes(a)]
    if origin is list:
        return [('list', shapes(typing.get_args(tp)[0]))]
    if origin is dict:
        return [('dict', shapes(typing.get_args(tp)[1]))]
    if inspect.isclass(tp) and issubclass(tp, RootModel):
        return shapes(tp.model_fields['root'].annotation)
    if inspect.isclass(tp) and issubclass(tp, BaseModel):
        return [('model', tp)]
    return []


def _keys_of(model) -> list[str]:
    return [f.alias or name for name, f in model.model_fields.items()]


def _pick(node: CommentedMap, candidates: list) -> type[BaseModel]:
    """The candidate model that declares the most of the node's keys (the first on a tie)."""
    return max(candidates, key=lambda m: len(set(map(str, node)) & set(_keys_of(m))))


def canonical_order(model, keys: list) -> list:
    from schema.benchmark import _ANNOTATION_KEY, ANNOTATIONS
    fields = _keys_of(model)
    rank = list(ANNOTATIONS)
    out = []
    for f in fields:
        if f in keys:
            out.append(f)
        notes = [k for k in keys if str(k) not in fields and (m := _ANNOTATION_KEY.match(str(k)))
                 and m.group('field') == f]
        out += sorted(notes, key=lambda k: rank.index(_ANNOTATION_KEY.match(str(k)).group('kind')))
    return out + [k for k in keys if k not in out]


# ---- comments -----------------------------------------------------------------------------------

@dataclass
class Slot:
    """Where ruamel keeps the comment lines that follow one value."""
    container: CommentedMap | CommentedSeq
    key: typing.Any
    index: int                          # 2 in a mapping's item, 0 in a sequence's

    @property
    def block_scalar(self) -> bool:     # a literal or folded value consumes its newline: no eol part
        return isinstance(self.container[self.key], (LiteralScalarString, FoldedScalarString))

    def get(self) -> str | None:
        item = self.container.ca.items.get(self.key)
        tok = item[self.index] if item and len(item) > self.index else None
        return tok.value if isinstance(tok, CommentToken) else None

    def set(self, value: str | None):
        item = self.container.ca.items.get(self.key)
        if value is None:
            if item and isinstance(item[self.index], CommentToken):
                item[self.index] = None
            return
        if item is None:
            item = self.container.ca.items[self.key] = [None, None, None, None]
        tok = item[self.index]
        if isinstance(tok, CommentToken):
            tok.value = value
        else:
            item[self.index] = CommentToken(value, CommentMark(0), None)

    def split(self) -> tuple[str, str]:
        """(this value's own end-of-line part, the full lines after it)."""
        v = self.get()
        if not v:
            return '', ''
        if self.block_scalar:
            return '', v
        first, _, rest = v.partition('\n')
        return first + '\n', rest

    def append(self, lines: str):
        if not lines:
            return
        eol, rest = self.split()
        if self.block_scalar:
            self.set(rest + lines)
        else:
            self.set((eol or '\n') + rest + lines)


def tail(container, key) -> Slot:
    v = container[key]
    if isinstance(v, CommentedMap) and len(v):
        return tail(v, list(v)[-1])
    if isinstance(v, CommentedSeq) and len(v):
        return tail(v, len(v) - 1)
    return Slot(container, key, 2 if isinstance(container, CommentedMap) else 0)


def _top_head(node: CommentedMap | CommentedSeq):
    """Comment lines at the top of the file, after its header."""
    def put(lines: str):
        if node.ca.comment is None:
            node.ca.comment = [None, []]
        while len(node.ca.comment) < 2:
            node.ca.comment.append([])
        node.ca.comment[1] = (node.ca.comment[1] or []) + [CommentToken(lines, CommentMark(0), None)]
    return put


def _child_head(parent, pkey, parent_head):
    """How to put comment lines above the node at parent[pkey]: after `key:` in a mapping; for a
    list item, after the item before it, or above the list for its first item."""
    def put(lines: str):
        if isinstance(parent, CommentedMap):
            Slot(parent, pkey, 2).append(lines)
        elif pkey > 0:
            tail(parent, pkey - 1).append(lines)
        else:
            parent_head(lines)
    return put


def reorder(node: CommentedMap, order: list, head):
    """`head(lines)` puts comment lines above the node, for a key that becomes its first."""
    old = list(node)
    if old == order:
        return
    leads, trailing = {}, ''
    for i, k in enumerate(old):
        slot = tail(node, k)
        eol, rest = slot.split()
        slot.set(eol if eol.strip() else None)
        if i + 1 < len(old):
            leads[old[i + 1]] = rest
        else:
            trailing = rest
    for k in order:
        node.move_to_end(k)
    for i, k in enumerate(order):
        lead = leads.get(k, '')  # get-default: our own map; the original first key has no lifted lead
        if i == 0:
            if lead:
                head(lead)
        else:
            tail(node, order[i - 1]).append(lead)
    tail(node, order[-1]).append(trailing)


def comment_lines(node) -> Counter:
    """Every comment line in a round-trip tree, stripped: what the comment guard compares."""
    out: Counter = Counter()
    seen = set()

    def tokens(x):
        if isinstance(x, CommentToken):
            yield x
        elif isinstance(x, list):
            for y in x:
                yield from tokens(y)

    def walk(n):
        if not isinstance(n, (CommentedMap, CommentedSeq)):
            return
        ca = n.ca
        for t in list(tokens(ca.comment)) + [t for item in ca.items.values() for t in tokens(item)] + \
                list(tokens(getattr(ca, 'end', None))):
            if id(t) not in seen:
                seen.add(id(t))
                out.update(s.strip() for s in t.value.split('\n') if s.strip().startswith('#'))
        for v in (n.values() if isinstance(n, CommentedMap) else n):
            walk(v)
    walk(node)
    return out


# ---- normalising one tree -----------------------------------------------------------------------

def _rounded(x: float, name: str = '') -> float:
    """07 S1.5's repr(round(x, 6)) strips float noise (0.7870000000000001); it must never cut real
    digits (1e-07 would become 0.0), so a rounding that moves a value by more than noise is refused."""
    r = round(x, 6)
    if x == x and abs(r - x) > 1e-9 * max(1.0, abs(x)):
        raise FmtError('%s: %r has more than six decimal places; repr(round(x, 6)) would change it' % (name, x))
    return r


def _canon(v, name=''):
    """The data with floats as the emitter writes them: what the value guard compares."""
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        return _rounded(v, name)
    if isinstance(v, dict):
        return {k: _canon(x, name) for k, x in v.items()}
    if isinstance(v, list):
        return [_canon(x, name) for x in v]
    return v


def _plain(v):
    if isinstance(v, ScalarBoolean):
        return bool(v)
    if isinstance(v, ScalarFloat):
        return float(v)
    if isinstance(v, ScalarInt):
        return int(v)
    return v


def _flow(v) -> bool:
    return isinstance(v, (CommentedMap, CommentedSeq)) and len(v) > 0 and bool(v.fa.flow_style())


def _unflow(container, key, index: int):
    """A flow collection keeps the comment lines that follow it on its parent's slot; once it is
    written in block style those lines must follow its last item instead."""
    slot = Slot(container, key, index)
    eol, rest = slot.split()
    slot.set(eol if eol.strip() else None)
    tail(container, key).append(rest)


def normalise(node, candidates: list, head=None):
    """In place: children first, so a parent's reorder finds each child's final last key."""
    head = head or _top_head(node)
    if isinstance(node, CommentedMap):
        models = [s[1] for s in candidates if s[0] == 'model']
        dicts = [s[1] for s in candidates if s[0] == 'dict']
        model = _pick(node, models) if models else None
        fields = {(f.alias or n): f for n, f in model.model_fields.items()} if model else {}
        for k in list(node):
            node[k] = _plain(node[k])
            inner = shapes(fields[k].annotation) if k in fields else (dicts[0] if dicts else [])
            flow = _flow(node[k])
            normalise(node[k], inner, _child_head(node, k, head))
            if flow:
                _unflow(node, k, 2)
        if len(node):
            node.fa.set_block_style()
        if model is not None:
            reorder(node, canonical_order(model, list(node)), head)
    elif isinstance(node, CommentedSeq):
        lists = [s[1] for s in candidates if s[0] == 'list']
        for i in range(len(node)):
            node[i] = _plain(node[i])
            flow = _flow(node[i])
            normalise(node[i], lists[0] if lists else [], _child_head(node, i, head))
            if flow:
                _unflow(node, i, 0)
        if len(node):
            node.fa.set_block_style()


def model_for(rel: str):
    from tools.validate.tiers import anchor, kind_of
    kind = kind_of(anchor(rel))
    return kind.model if kind else None


def format_text(text: str, model=None, name: str = '<text>') -> str:
    safe = YAML(typ='safe')
    before = _canon(safe.load(text), name)
    tree = emitter().load(text)
    if tree is None:
        return ''
    comments = comment_lines(tree)
    normalise(tree, shapes(model) if model is not None else [])
    out = dumps(tree)
    if safe.load(out) != before:
        raise FmtError('%s: formatting would change the data; not written' % name)
    if comment_lines(emitter().load(out)) != comments:
        raise FmtError('%s: formatting would lose or duplicate a comment; not written' % name)
    return out


# ---- files --------------------------------------------------------------------------------------

def files(paths, root: str = ROOT) -> list[str]:
    """Root-relative YAML files under each path (a file, or a directory walked recursively)."""
    out = set()
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(root, p)
        if os.path.isfile(full):
            out.add(full)
        for d, _, names in os.walk(full):
            out |= {os.path.join(d, n) for n in names if n.endswith(('.yaml', '.yml'))}
    return sorted(os.path.relpath(f, root).replace(os.sep, '/') for f in out)


def run(paths=None, check: bool = False, root: str = ROOT) -> tuple[list[str], list[str]]:
    """(files that differ from their formatted form, errors). Writes them unless `check`."""
    changed, errors = [], []
    for rel in files(paths or DEFAULT_PATHS, root):
        path = os.path.join(root, rel)
        with open(path, encoding='utf-8', newline='') as fh:
            text = fh.read()
        try:
            out = format_text(text, model_for(rel), rel)
        except FmtError as e:
            errors.append(str(e))
            continue
        except Exception as e:                                   # a file ruamel cannot read at all
            errors.append('%s: %s' % (rel, ' '.join(str(e).split())[:300]))
            continue
        if out != text:
            changed.append(rel)
            if not check:
                with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(out)
    return changed, errors
