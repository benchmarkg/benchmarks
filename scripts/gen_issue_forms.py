#!/usr/bin/env python3
"""Generate the issue-form dropdown options from taxonomy/*.yaml (P2-S6-T01; 05 S6, 05 S9).

05 S6: "The dropdown options are generated from `taxonomy/*.yaml` by CI, and CI fails if regeneration produces
a diff -- the same rule already settled for Pydantic -> JSON Schema -> TypeScript. The contribution form can
therefore never drift from the controlled vocabulary, which is the usual way a form becomes a second, informal
taxonomy."

A form in .github/ISSUE_TEMPLATE/ names a generated dropdown by its `id`; this script owns that dropdown's
`attributes.options` and nothing else in the file:

  primary-domain      every live subdomain of taxonomy/domains.yaml (a family is not assignable, 04 S3)
  secondary-domains   the same set, for the multiple-choice field
  capabilities        every live term of taxonomy/capabilities.yaml
  evaluation-method   every live term of taxonomy/evaluation-methods.yaml
  subjects            every live term of taxonomy/subjects.yaml
  facet               every facet a vocabulary file declares (taxonomy-term.yml asks which one a term is for)

An option reads `<label> (<id>)`: the label for the contributor, the id for issue-intake.yml, which takes the
text in the last parentheses. Retired terms are never offered; a deprecated one still is, until it is retired.

    python scripts/gen_issue_forms.py            # rewrite the generated options in every form
    python scripts/gen_issue_forms.py --check    # write nothing; exit 1 if any form would change
    python scripts/gen_issue_forms.py --root DIR # another tree (the tests do)

It runs in pr-validate.yml's job 5, beside the JSON Schema and TypeScript legs of the codegen check.
"""
from __future__ import annotations

import argparse
import glob
import io
import os
import sys

from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = os.path.join('.github', 'ISSUE_TEMPLATE')
FACET_FILES = ('domains', 'capabilities', 'evaluation-methods', 'subjects', 'data-properties', 'lifecycle',
               'governance', 'execution', 'ceiling-anchors', 'maintenance')


def _load(root: str, name: str) -> dict:
    with open(os.path.join(root, 'taxonomy', name + '.yaml'), encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh) or {}


def _live(terms):
    return [t for t in terms or [] if t.get('status') != 'retired']


def option(term: dict) -> str:
    return '%s (%s)' % (' '.join(str(term.get('label') or term['id']).split()), term['id'])


def option_sets(root: str = ROOT) -> dict[str, list[str]]:
    """Dropdown id -> its options, in the vocabulary's own order."""
    subdomains = [option(t) for t in _live(_load(root, 'domains').get('terms')) if t.get('parent')]
    out = {
        'primary-domain': subdomains,
        'secondary-domains': list(subdomains),
        'capabilities': [option(t) for t in _live(_load(root, 'capabilities').get('terms'))],
        'evaluation-method': [option(t) for t in _live(_load(root, 'evaluation-methods').get('terms'))],
        'subjects': [option(t) for t in _live(_load(root, 'subjects').get('terms'))],
    }
    facets = []
    for name in FACET_FILES:
        path = os.path.join(root, 'taxonomy', name + '.yaml')
        if os.path.exists(path):
            facet = _load(root, name).get('facet')
            if facet and facet not in facets:
                facets.append(facet)
    out['facet'] = facets
    return out


def forms(root: str) -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(root, FORMS, '*.yml')) if os.path.basename(p) != 'config.yml')


def _yaml() -> YAML:
    y = YAML()
    y.width = 4096                       # an option is one line, however long its label
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def render(path: str, sets: dict[str, list[str]]) -> tuple[str, str, list[str]]:
    """(the file's text, its text with generated options, the generated dropdown ids it carries)."""
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    y = _yaml()
    doc = y.load(text)
    ids = []
    for item in (doc or {}).get('body') or []:
        if item.get('type') == 'dropdown' and item.get('id') in sets:
            ids.append(item['id'])
            item.setdefault('attributes', {})['options'] = list(sets[item['id']])
    buf = io.StringIO()
    y.dump(doc, buf)
    return text, buf.getvalue(), ids


def run(root: str = ROOT, check: bool = False) -> tuple[list[str], int]:
    """(the forms whose generated options are stale, the number of forms read)."""
    sets = option_sets(root)
    stale, paths = [], forms(root)
    for path in paths:
        text, new, ids = render(path, sets)
        if ids and new != text:
            stale.append(os.path.relpath(path, root).replace(os.sep, '/'))
            if not check:
                with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(new)
    return stale, len(paths)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--check', action='store_true')
    a = p.parse_args(argv)
    stale, n = run(a.root, a.check)
    sizes = ', '.join('%s %d' % (k, len(v)) for k, v in option_sets(a.root).items())
    if a.check:
        for rel in stale:
            print('BLOCKING  issue-forms  %s: its generated dropdown options differ from taxonomy/; run '
                  '`python scripts/gen_issue_forms.py`' % rel)
        print('gen_issue_forms --check: %d form(s) read, %d stale (option sets: %s)' % (n, len(stale), sizes))
        return 1 if stale else 0
    print('gen_issue_forms: %d form(s) read, %d rewritten (option sets: %s)' % (n, len(stale), sizes))
    return 0


if __name__ == '__main__':
    sys.exit(main())
