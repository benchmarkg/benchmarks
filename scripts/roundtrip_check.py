#!/usr/bin/env python3
"""The round-trip emitter assertion over data/ (P5-S2-T06; 07 S1.5, 05 S9).

07 S1.5 fixes one YAML emitter, "specified once and shared by `bench fmt` and every adapter" (it lives in
tools/fmt.py). An adapter writes plain values through it: floats as their canonical repr, collections in
block style, strings quoted only when YAML needs it. This check re-emits every file under data/ that way --
tools/fmt.py's style normalisation with no model, so keys stay in the file's order -- and fails on any byte
difference. A file that does not survive -- a float written `0.50`, a needlessly quoted string, a flow
list, CRLF endings -- is one whose next machine write would produce a diff nobody made, which is the
cosmetic churn 05 S1 sets out to kill. Key order is `bench fmt --check`'s concern, beside it in job 1.

    python scripts/roundtrip_check.py              # every YAML file under data/; exit 1 on any difference
    python scripts/roundtrip_check.py --root DIR   # another tree (the tests do)

It runs beside `bench fmt --check` in pr-validate.yml's job 1.
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def differences(root: str) -> list[tuple[str, str]]:
    """(path, the first differing line pair) for every file under data/ that does not round-trip."""
    sys.path.insert(0, ROOT)
    from tools import fmt
    out = []
    for rel in fmt.files(['data'], root):
        with open(os.path.join(root, rel), encoding='utf-8', newline='') as fh:
            text = fh.read()
        emitted = fmt.format_text(text, None, rel)              # style normalised, keys left in file order
        if emitted != text:
            diff = [line for line in difflib.unified_diff(text.splitlines(), emitted.splitlines(), lineterm='', n=0)
                    if line[:1] in '+-' and not line.startswith(('+++', '---'))]
            out.append((rel, ' / '.join(diff[:2]) or 'line endings or the final newline'))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    bad = differences(a.root)
    for rel, first in bad:
        print('BLOCKING  roundtrip  %s: re-emission differs (%s)' % (rel, first))
    print('roundtrip_check: %d file(s) under data/ do not survive load-then-emit' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
