#!/usr/bin/env python3
"""Fail on `.get()` with a default anywhere under ingest/ (P5-S4-T06; 07 S9.2).

    python scripts/check_no_get_default.py ingest/
    python scripts/check_no_get_default.py ingest/ tools/ingest/some_file.py

07 S9.2, schema drift: "Hard fail immediately. ... Assert structure explicitly; never `.get()` with
a default. This is the class that silently corrupts data if swallowed." A `.get('key', 0)` on an
upstream payload turns a renamed field into a plausible zero that flows into a PR looking like
data. This lint makes the rule mechanical: every call `X.get(a, b)` or `X.get(a, default=b)` is a
failure unless the line says why it is not reading upstream structure.

The opt-out is a comment on any line the call spans:

    entry = state['urls'].get(url, {})  # get-default: our own state; an unseen URL has no entry

`get-default:` followed by a reason of at least three words. A bare marker, or one with a one-word
reason, is itself a failure: the point is that a reviewer can read why, not that the lint goes
quiet. What the lint cannot tell apart, and so asks the author to say: a mapping lookup on the
adapter's own state or constants (legitimate), a non-mapping method that happens to be called
`get` with two arguments -- an HTTP client's `get(url, headers)` (legitimate) -- and a lookup on
an upstream payload (never legitimate: assert the key, or raise SchemaDrift).

Not flagged: `.get(key)` with no default. It returns None, which is loud in a way a default is
not -- `None` fails the schema, a 0 or an empty string passes it. `getattr(x, name, default)` and
`dict.setdefault` are outside this rule as 07 states it.

Exit codes: 0 clean; 1 a violation, or a file that does not parse (it cannot be vouched for);
2 a path that does not exist.
"""
import argparse
import ast
import io
import os
import re
import sys
import tokenize

MARKER = re.compile(r'#\s*get-default:\s*(.*)$')
MIN_REASON_WORDS = 3


def comments(source):
    """{line number: comment text} for every comment in the file."""
    out = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            out[tok.start[0]] = tok.string
    return out


def get_with_default(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get'
            and (len(node.args) >= 2 or any(k.arg == 'default' for k in node.keywords)))


def check_source(source, path):
    """[(line, col, message)] for one file's text."""
    try:
        tree = ast.parse(source, filename=path)
        notes = comments(source)
    except (SyntaxError, tokenize.TokenError) as e:
        return [(getattr(e, 'lineno', 0) or 0, 0, 'does not parse, so it cannot be checked: %s' % e)]
    lines = source.splitlines()
    found = []
    for node in ast.walk(tree):
        if not get_with_default(node):
            continue
        span = range(node.lineno, (node.end_lineno or node.lineno) + 1)
        marks = [MARKER.search(notes[n]) for n in span if n in notes and MARKER.search(notes[n])]
        if any(len(m.group(1).split()) >= MIN_REASON_WORDS for m in marks):
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ''
        if marks:
            msg = 'get-default opt-out needs a reason of at least %d words: %s' % (MIN_REASON_WORDS, snippet)
        else:
            msg = '.get() with a default -- assert the structure, or say why with `# get-default: <reason>`: %s' % snippet
        found.append((node.lineno, node.col_offset + 1, msg))
    return sorted(found)


def python_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for d, dirs, files in os.walk(p):
            dirs[:] = sorted(x for x in dirs if x not in ('__pycache__', '.venv', 'node_modules') and not x.startswith('.'))
            for f in sorted(files):
                if f.endswith('.py'):
                    yield os.path.join(d, f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('paths', nargs='+', help='files or directories to scan (the CI step passes ingest/)')
    a = ap.parse_args(argv)
    missing = [p for p in a.paths if not os.path.exists(p)]
    if missing:
        print('check_no_get_default: no such path: %s' % ', '.join(missing), file=sys.stderr)
        return 2
    n_files = n_bad = 0
    for path in python_files(a.paths):
        n_files += 1
        with open(path, encoding='utf-8') as f:
            source = f.read()
        for line, col, msg in check_source(source, path):
            n_bad += 1
            print('%s:%d:%d: %s' % (path.replace(os.sep, '/'), line, col, msg))
    print('check_no_get_default: %d file(s), %d violation(s)' % (n_files, n_bad))
    return 1 if n_bad else 0


if __name__ == '__main__':
    sys.exit(main())
