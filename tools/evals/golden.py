"""The golden set as the harness reads it: evals/golden/, its composition checked, its held-out items chosen (P6-S3-T09;
11-ai-features.md S7 "The golden set", "Grading and cadence").

The four splits are scripts/check_golden_composition.py's (P6-S3-T08), and so is every rule about them: the harness
loads the set through that script's load_set() and refuses to grade while its check() reports anything, so a gold
label of the wrong shape, an entry id that is no file under data/benchmarks/, or a label set while `labelled_by` names
no one stops a run before a number is computed. evals/golden/identity_resolution.yaml is another task's calibration
set (07 S5.3) and not a split.

A labelled item is one whose `gold` is set. The drafts hold none: every gold label is null until a person sets it,
because an agent-written label makes the evaluation circular (P6-S3-T08). An item without a label is never scored, not
even as a zero.

The holdout (`--holdout N`, 11 S7: "Hold out a 30-item test split that is scored but never used for prompt tuning, and
publish train and test separately"). N items are the test split, the rest train. The choice is a pure function of the
item ids, so the same items stay held out from run to run and nobody chooses them: N is shared out over the selected
splits in proportion to their sizes (largest remainder, ties to the earlier split in SPLITS), and within a split the
items with the lowest sha256 of their id are taken. Growing a split moves an item into the test split only when its
hash ranks it there, never by hand.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join('scripts', 'check_golden_composition.py')
GOLDEN = 'evals/golden'


class GoldenError(Exception):
    """The golden set cannot be graded as it stands; `errors` says why, one line each."""

    def __init__(self, errors: list[str]):
        super().__init__('\n'.join(errors))
        self.errors = errors


@lru_cache(maxsize=None)
def composition(root: str = ROOT):
    """scripts/check_golden_composition.py as a module (it is a script, not a package member)."""
    path = os.path.join(root, CHECKER)
    spec = importlib.util.spec_from_file_location('check_golden_composition', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault('check_golden_composition', module)
    spec.loader.exec_module(module)
    return module


SPLITS = composition().SPLITS            # nl_search, facet_translation, suite_build, abstention


def load(root: str = ROOT) -> tuple[dict, object]:
    """(split -> its document, the composition check's Context), or GoldenError naming every problem."""
    comp = composition()
    docs, errors = comp.load_set(root)
    if errors:
        raise GoldenError(errors)
    ctx = comp.load_context(root)
    errors = comp.check(docs, ctx)
    if errors:
        raise GoldenError(['%s: %s' % (GOLDEN, e) for e in errors])
    return docs, ctx


def labelled(doc: dict) -> list[dict]:
    return [it for it in doc['items'] if it['gold'] is not None]


def population(item: dict) -> str:
    """11 S7: generated items and the rest are "scored separately and both published"."""
    return 'generated' if item['provenance'] == 'generated' else 'not-generated'


def rank(ident: str) -> str:
    return hashlib.sha256(ident.encode('utf-8')).hexdigest()


def holdout(docs: dict, splits: list[str], n: int) -> list[str]:
    """The ids of the N held-out items over `splits` (module docstring), sorted; ValueError when N is out of range."""
    sizes = {s: len(docs[s]['items']) for s in splits}
    total = sum(sizes.values())
    if not 0 <= n <= total:
        raise ValueError('--holdout %d: the selected split(s) hold %d item(s)' % (n, total))
    if n == 0:
        return []
    shares = {s: n * sizes[s] / total for s in splits}
    take = {s: int(shares[s]) for s in splits}
    left = n - sum(take.values())
    for s in sorted(splits, key=lambda s: (-(shares[s] - take[s]), SPLITS.index(s)))[:left]:
        take[s] += 1
    out = []
    for s in splits:
        out += sorted((it['id'] for it in docs[s]['items']), key=rank)[:take[s]]
    return sorted(out)
