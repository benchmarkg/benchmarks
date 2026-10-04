#!/usr/bin/env python3
"""How an adapter writes YAML, and the round-trip determinism gate (P3-S1-T05; 07 S1.5, S8).

07 S1.5: "YAML emission is specified once and shared by `bench fmt` and every adapter, because two
emitters produce two formats and the diff noise hides real changes." The emitter is tools/fmt.py's
(P0-S5-T04): the Pydantic model's key order, quoting only where YAML needs it, width 100, block
style, floats as repr(round(x, 6)), LF and one final newline. This module adds no second emitter.
It is the adapter's side of that one: an adapter holds plain Python data (a Draft's payload, an
IngestBatch), and `emit()` turns it into exactly the text `bench fmt` would leave alone.

    emit(doc, rel)       the canonical text for `doc` written at repo-relative `rel`
    write(doc, rel)      that text on disk; an existing file is never overwritten unless asked
    roundtrip(paths)     07 S8's gate: every file re-emits to a zero-byte diff

    python -m ingest.emit --check data/claims/_ingested/      # the gate over the files a run touched

Why the gate exists (07 S1.5): "a float formatted two ways produces two different claim- ids for the
same measurement". Whatever an adapter writes must come back byte-identical when it is read and
written again, or the next run's diff is noise and the claim id it hashes moves.
"""
from __future__ import annotations

import os
import sys

if __name__ == '__main__' and not __package__:
    # Run as a file, sys.path[0] is ingest/; put the repository root there instead, or ingest/http/
    # would shadow the standard library's `http`.
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import argparse  # noqa: E402

from ruamel.yaml import YAML  # noqa: E402
from ruamel.yaml.scalarstring import LiteralScalarString, ScalarString  # noqa: E402

from tools import fmt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAFE = YAML(typ='safe', pure=True)
FOLD_RISK = 80          # a backslash-bearing string longer than this is written as a literal block


def _literal_ok(s: str) -> bool:
    """A literal block holds `s` exactly: no carriage return, no control character but newline and
    tab, and no line ending in whitespace, which the emitter's tidy pass would strip."""
    return (all(c in '\n\t' or ord(c) >= 32 for c in s) and '\r' not in s
            and all(line == line.rstrip() for line in s.split('\n')))


def _prepare(x, name: str):
    """Plain data as the emitter should receive it. Two things the emitter cannot be trusted with:
      - a float with real digits past the sixth place: the float representer rounds silently, so the
        refusal `bench fmt` applies (fmt._rounded) is applied here, before anything is written;
      - a long string with a backslash in it: ruamel 0.18's double-quoted style can fold a line straight
        after an escaped backslash without the escape a line end needs, and the break reads back as a
        space -- a changed value (seen on an Epoch page's `\\`\\`\\`` runs). A literal block never folds,
        so such a string is written as one, which is also how the committed corpus holds them."""
    if isinstance(x, dict):
        return {k: _prepare(v, name) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_prepare(v, name) for v in x]
    if isinstance(x, float):
        fmt._rounded(x, name)
        return x
    if isinstance(x, str) and not isinstance(x, ScalarString) and '\\' in x and len(x) > FOLD_RISK \
            and _literal_ok(x):
        return LiteralScalarString(x)
    return x


def _expected(x):
    """What `x` reads back as from correctly emitted text: floats to six places, tuples as lists."""
    if isinstance(x, dict):
        return {k: _expected(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_expected(v) for v in x]
    if isinstance(x, float) and x == x:
        return round(x, 6)
    return x


def emit(doc, rel: str) -> str:
    """The text `doc` is written as at `rel` (repo-relative, forward slashes): the path picks the
    entity model whose field order the keys take. The text must read back to exactly `doc` -- floats
    stripped of noise and nothing else -- or fmt.FmtError is raised and nothing is written."""
    text = fmt.format_text(fmt.dumps(_prepare(doc, rel)), fmt.model_for(rel), rel)
    if SAFE.load(text) != _expected(doc):
        raise fmt.FmtError('%s: the emitted text does not read back as the data given; not written' % rel)
    return text


def reemit(text: str, rel: str) -> str:
    """`text` through the emitter again, comments kept: the round trip the gate compares."""
    return fmt.format_text(text, fmt.model_for(rel), rel)


def write(doc, rel: str, root: str = ROOT, header: str | None = None, replace: bool = False) -> str:
    """Write `doc` at `rel` under `root`; `header` becomes a first comment line. An existing file is
    an error unless `replace`: an adapter that means to change a record says so."""
    path = os.path.join(root, *rel.split('/'))
    if os.path.exists(path) and not replace:
        raise FileExistsError('%s exists; pass replace=True to rewrite it' % rel)
    text = emit(doc, rel)
    if header:
        text = '# %s\n%s' % (header, text)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return rel


def roundtrip(paths=None, root: str = ROOT) -> list[tuple[str, str]]:
    """07 S8's round-trip determinism gate: (file, why) for every YAML file under `paths` (default:
    data/) that does not re-emit to the same bytes. An empty list passes."""
    out = []
    for rel in fmt.files(paths or fmt.DEFAULT_PATHS, root):
        with open(os.path.join(root, *rel.split('/')), 'rb') as f:
            raw = f.read()
        try:
            text = raw.decode('utf-8')
            again = reemit(text, rel)
        except (UnicodeDecodeError, fmt.FmtError, ValueError) as e:
            out.append((rel, '%s: %s' % (type(e).__name__, e)))
            continue
        if again.encode('utf-8') != raw:
            out.append((rel, 're-emitting changes it (%d bytes -> %d)' % (len(raw), len(again.encode('utf-8')))))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('paths', nargs='*', help='files or directories (default: data/)')
    p.add_argument('--check', action='store_true', help='the gate: exit 1 if any file does not round-trip')
    p.add_argument('--root', default=ROOT, help='the tree the paths lie in (default: this repository)')
    a = p.parse_args(argv)
    bad = roundtrip(a.paths or None, a.root)
    for rel, why in bad:
        print('%s: %s' % (rel, why))
    print('round-trip: %d file(s) do not re-emit byte-identically' % len(bad) if bad
          else 'round-trip: every file re-emits byte-identically')
    return 1 if (bad and a.check) else 0


if __name__ == '__main__':
    sys.exit(main())
