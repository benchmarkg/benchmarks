#!/usr/bin/env python3
"""The five issue forms carry what 05 S6 requires of them (P2-S6-T02; 05 S6, 05 S8).

For each form in .github/ISSUE_TEMPLATE/ it asserts:

  shape        a name, a description and a body; every input, textarea and dropdown has a stable `id`, a label
               and hint text (`description`); no id twice.
  fields       the form's required fields exist and are required. new-benchmark.yml has exactly 05 S6's field
               list, in its order.
  attestation  an `attestation` checkboxes block whose every option is required: the contributor says the
               fields come from the linked sources, not memory (new-benchmark.yml has 05 S6's two).
  bot          a `bot-disclosure` checkboxes block whose every option is required and says a bot handles the
               issue, so no form can be submitted without the contributor knowing a bot acts on it.
  routing      every form but taxonomy-term.yml carries `source:issue-form`, the label the intake bot opens a
               pull request for; taxonomy-term.yml carries `route:adr` and never `source:issue-form`, because
               a term goes to the ADR process and never auto-PRs (05 S5).

    python scripts/validate_issue_forms.py              # exit 0 if every form holds, 1 otherwise
    python scripts/validate_issue_forms.py --root DIR   # another tree (the tests do)
"""
from __future__ import annotations

import argparse
import os
import sys

from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = os.path.join('.github', 'ISSUE_TEMPLATE')
FIELD_TYPES = ('input', 'textarea', 'dropdown')

# 05 S6's new-benchmark field list, in order: (id, required).
NEW_BENCHMARK = [
    ('name', True), ('homepage', True), ('tagline', True), ('primary-domain', True), ('secondary-domains', False),
    ('capabilities', True), ('evaluation-method', True), ('what-is-evaluated', True), ('repository', False),
    ('dataset-url', False), ('licence', False), ('size', False), ('maintainer', False), ('released', False),
    ('leaderboard-url', False), ('lineage', False), ('notes', False),
]
REQUIRED = {
    'new-benchmark.yml': [i for i, req in NEW_BENCHMARK if req],
    'correction.yml': ['entity', 'field', 'correct-value', 'source-url', 'quote'],
    'new-claim.yml': ['benchmark', 'system', 'metric', 'value', 'date-reported', 'source-url', 'quote'],
    'dispute.yml': ['concerns', 'disputant-relationship', 'position', 'evidence'],
    'taxonomy-term.yml': ['facet', 'term-id', 'term-label', 'definition', 'inclusion-test', 'exclusion-test',
                          'near-miss', 'benchmarks'],
}
NEW_BENCHMARK_ATTESTATIONS = (
    'Every field above is supported by the linked sources; I have not filled anything from memory',
    'I understand this index links to data and never hosts it',
)


def load(path):
    with open(path, encoding='utf-8') as fh:
        return YAML(typ='safe').load(fh) or {}


def checkboxes(body, ident):
    found = [b for b in body if b.get('type') == 'checkboxes' and b.get('id') == ident]
    return found[0]['attributes']['options'] if found else None


def check_form(name, doc) -> list[str]:
    out = []
    for key in ('name', 'description', 'body'):
        if not doc.get(key):
            out.append('no %s' % key)
    body = doc.get('body') or []
    fields = [b for b in body if b.get('type') in FIELD_TYPES]
    ids = [b.get('id') for b in fields]
    if len(set(ids)) != len(ids) or None in ids:
        out.append('every field needs its own id: %s' % ids)
    for b in fields:
        attrs = b.get('attributes') or {}
        if not attrs.get('label'):
            out.append('%s has no label' % b.get('id'))
        if not (attrs.get('description') or '').strip():
            out.append('%s has no hint text (description)' % b.get('id'))
    required = {b.get('id') for b in fields if (b.get('validations') or {}).get('required')}
    for ident in REQUIRED[name]:
        if ident not in ids:
            out.append('missing the required field %s' % ident)
        elif ident not in required:
            out.append('%s is not marked required' % ident)
    if name == 'new-benchmark.yml':
        got = [(b.get('id'), b.get('id') in required) for b in fields]
        if got != NEW_BENCHMARK:
            out.append("the fields are not 05 S6's list in its order: %s" % [i for i, _ in got])
    attest = checkboxes(body, 'attestation')
    if not attest or not all(o.get('required') for o in attest):
        out.append('no attestation checkbox, or one that is not required')
    elif name == 'new-benchmark.yml' and tuple(o['label'] for o in attest) != NEW_BENCHMARK_ATTESTATIONS:
        out.append("the attestations are not 05 S6's two")
    bot = checkboxes(body, 'bot-disclosure')
    if not bot or not all(o.get('required') for o in bot) or not all('bot' in o.get('label', '') for o in bot):
        out.append('no required bot disclosure (a checkbox saying a bot handles the issue)')
    labels = doc.get('labels') or []
    if name == 'taxonomy-term.yml':
        if 'source:issue-form' in labels or 'route:adr' not in labels:
            out.append('a taxonomy term routes to the ADR process (route:adr) and never auto-PRs (no source:issue-form)')
    elif 'source:issue-form' not in labels:
        out.append('no source:issue-form label, so the intake bot would not pick it up')
    return out


def check(root: str) -> list[str]:
    out = []
    base = os.path.join(root, FORMS)
    for name in REQUIRED:
        path = os.path.join(base, name)
        if not os.path.exists(path):
            out.append('%s: missing' % name)
            continue
        out += ['%s: %s' % (name, p) for p in check_form(name, load(path))]
    config = os.path.join(base, 'config.yml')
    if not os.path.exists(config) or load(config).get('blank_issues_enabled') is not False:
        out.append('config.yml: blank issues must be disabled, so every issue goes through a form')
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    a = p.parse_args(argv)
    bad = check(a.root)
    for line in bad:
        print('BLOCKING  issue-forms  %s' % line)
    print('validate_issue_forms: %d form(s), %d problem(s)' % (len(REQUIRED), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
