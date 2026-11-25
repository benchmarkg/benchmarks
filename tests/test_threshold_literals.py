"""No completeness floor is typed as a number outside taxonomy/thresholds.yaml (P4-S1-T07; 12 S1.4, 04 S12, ADR-0028).

12 S1.4: "No document restates these values." A floor typed as a number anywhere else is the copy that stays behind at
the next recalibration. The scan reads every text file in the code, the tests, the plan and the docs, and flags a
floor's name followed, across at most a few non-word characters, by a decimal between 0 and 1: an assignment, a YAML
key, a parenthesis or a table cell. A section reference after the name is above 1, so it passes.

Exempt: taxonomy/thresholds.yaml, the one home; _plan/execution/, the ledger, which quotes the verify's own grep; and
the dated records -- adr/ (immutable once merged, 03 S8) and CHANGELOG.md -- whose figures record a decision at its
date rather than copy the live value. The cases below are built from thresholds.yaml's own values, so this file holds
no literal either.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402

SCANNED = ('tools', 'scripts', 'schema', 'ingest', 'evals', 'config', 'taxonomy', 'tests', 'site/src', 'docs', '_plan',
           'data/_analysis')
EXEMPT = ('taxonomy/thresholds.yaml', '_plan/execution/', 'adr/', 'CHANGELOG.md')
SKIP_DIRS = {'node_modules', '__pycache__', '.venv', 'dist', '.astro'}
TEXT = ('.py', '.ts', '.tsx', '.js', '.mjs', '.astro', '.md', '.yaml', '.yml', '.json', '.toml', '.txt', '.html',
        '.css', '.cff')
LITERAL = re.compile(r'\b(frontier_floor|comparison_floor)\b[^\w\n]{0,12}?(\d*\.\d+)')


def floors() -> dict:
    return read_yaml(os.path.join(ROOT, 'taxonomy', 'thresholds.yaml'))['thresholds']


def literals(text: str) -> list[tuple[str, str]]:
    """(name, number) for every floor name followed by a decimal in [0, 1]."""
    return [(m.group(1), m.group(2)) for m in LITERAL.finditer(text) if float(m.group(2)) <= 1]


def scanned_files() -> list[str]:
    out = [f for f in os.listdir(ROOT) if f.endswith(('.md', '.cff')) and os.path.isfile(os.path.join(ROOT, f))]
    for top in SCANNED:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, top)):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            out += [os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, '/')
                    for f in filenames if f.endswith(TEXT)]
    return sorted(f for f in out if not f.startswith(EXEMPT))


@pytest.mark.parametrize('form', ['%s = %s', '%s: %s', '`%s` (%s)', '| `%s` | **%s** |', '`%s` %s + more'])
def test_the_scan_catches_each_way_a_value_gets_typed(form):
    for name, value in floors().items():
        for spelled in ('%s' % value, '%.2f' % value):
            assert literals(form % (name, spelled)) == [(name, spelled)], form % (name, spelled)


def test_a_section_reference_after_a_name_is_not_a_value():
    for name in floors():
        assert literals('`%s` (12 §1.4)' % name) == []
        assert literals('%s, 04 §12' % name) == []
        assert literals("'%s'] = 1.5" % name) == []         # out of range: a validation test's bad value


def test_no_floor_value_is_typed_outside_thresholds_yaml():
    hits = []
    for rel in scanned_files():
        with open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace') as fh:
            for n, line in enumerate(fh, 1):
                hits += ['%s:%d: %s %s' % (rel, n, name, number) for name, number in literals(line)]
    assert not hits, 'a completeness floor typed as a number; reference it by name (12 S1.4):\n' + '\n'.join(hits)
