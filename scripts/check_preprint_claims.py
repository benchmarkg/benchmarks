#!/usr/bin/env python3
"""Every number in the gap-matrix preprint reproduces from gaps.json at the commit it cites (P1-S14-T09).

14 Phase 1, "Publish the taxonomy and the gap analysis before the catalogue", has the project post a short
preprint of the domain x capability gap matrix "with our own curation confidence shown alongside density so the
gaps are not overclaimed". The ledger's done_when: "Every numeric claim in the preprint reproduces from gaps.json
at the cited commit." This reads the preprint, accounts for every digit in it, and fails on any it cannot.

    uv run python scripts/check_preprint_claims.py --preprint docs/preprints/gap-matrix.md --against build/derived/gaps.json
    uv run python scripts/check_preprint_claims.py ... --explain       # list every number and how it is accounted for

How a number is written in the preprint. Every run of digits in the file, prose, tables, headings, code and
comments alike, is exactly one of three things:

  bound    a figure of the index, <!-- gaps: PATH -->TEXT<!-- /gaps -->, the comment invisible when the Markdown
           renders. PATH selects one scalar in gaps.json: dot-separated keys, and a list element by
           [key=value,key=value] (exactly one element must match) or by [index]. TEXT must equal it: a number
           numerically (commas allowed only as thousands separators, and an integer printed as one), a string
           character for character, a boolean as true or false. An off-by-one figure fails here.
  quoted   a figure that is not the index's, <!-- quoted: SOURCE -->TEXT<!-- /quoted -->. SOURCE is a file under
           one of QUOTABLE (the plan, and the dated survey notes), and TEXT appears in it verbatim, whitespace
           collapsed, not as part of a longer number. The prose around it must say whose figure it is; this
           script checks only that the source says it.
  exempt   matched by one rule of EXEMPT, each narrow and each verified against the repository:
             heading-number  the section number of a Markdown heading outside a code fence, `## 3.` or
                             `### 3.1`, at most two digits a level, so a year in a heading is not one;
             section-ref     a cross-reference to one of the preprint's own numbered sections, `section 1.3`,
                             when a heading of the preprint carries that number;
             plan-section    a plan section cited in the repository's own form, `12 S5.3`, and only when
                             exactly one _plan/12-*.md exists and has a heading numbered 5.3 (a citation of a
                             section that does not exist is an error, not an exemption);
             repo-path       a path token naming a file that exists, from the repository root or from the
                             preprint's directory (`_plan/12-analytics-and-trends.md`);
             benchmark-id    inline code naming a benchmark the artifact holds (`uspto-50k`), from gaps.json's
                             quality_weights.

Everything else with a digit in it fails as an unbound number: an invented figure, a year, a date, a short commit
hash, a percentage worked out by hand, a constant in a code fence. Years, dates and the commit hash have no rule
of their own. The data commit and its date are bound to parameters.data_commit and parameters.as_of, and any
other year or date is quoted with its source or left out. A number spelled out in words is not extracted; the
preprint spells out only counts of its own parts (four examples, three terms), and a figure of the index is
written in digits so that this script sees it.

Two checks more, one for each of the task's steps that a script can see:

  confidence  every density figure (a bound path ending in density or normalised_density, or
              parameters.density_reference.value) has its own family's curation confidence bound in the same
              table row, list item or paragraph (a path ending in curation_confidence.value or
              factors.curation_confidence),
              so no density is ever printed without the honesty term beside it (12 S5.3);
  commit      the preprint binds parameters.data_commit, and every section (heading to heading) that prints a
              density figure binds it again, so each finding is stated as a claim about the index at that commit,
              never about the world. gaps.json must carry a full commit SHA for that to mean anything.

The preprint is pinned to one data commit. A gaps.json built at any other commit fails on the hash, by design:
build it at the cited commit (a `git worktree` of that SHA, then the bench command below in it) and point
--against at it, or re-pin the preprint at the new commit and update every figure the check then names.

Exit 0 when every number is accounted for, 1 on any finding, 2 when the preprint or the artifact is missing.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREPRINT = 'docs/preprints/gap-matrix.md'
ARTIFACT = 'build/derived/gaps.json'
MAKE = 'uv run bench gaps --grid coarse --reviewed-only --format json > %s' % ARTIFACT
QUOTABLE = ('_plan/', 'data/surveys/')
COMMIT = 'parameters.data_commit'
DENSITY_KEYS = ('density', 'normalised_density')
DENSITY_REFERENCE = 'parameters.density_reference.value'
CONFIDENCE_ENDS = ('.curation_confidence.value', '.factors.curation_confidence')
SHA = re.compile(r'[0-9a-f]{40}$')

BOUND = re.compile(r'<!--[ \t]*gaps:[ \t]*(?P<arg>[^<>\n]*?)[ \t]*-->(?P<text>[^<\n]*?)<!--[ \t]*/gaps[ \t]*-->')
QUOTED = re.compile(r'<!--[ \t]*quoted:[ \t]*(?P<arg>[^<>\n]*?)[ \t]*-->(?P<text>[^<\n]*?)<!--[ \t]*/quoted[ \t]*-->')
MARKER = re.compile(r'<!--\s*/?\s*(?:gaps|quoted)\b')
DIGITS = re.compile(r'\d+(?:[.,]\d+)*')
NUMBER = re.compile(r'-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$')
STEP = re.compile(r'\.?([^.\[\]]+)|\[([^\[\]]*)\]')
FENCE = re.compile(r'^\s*(?:```|~~~)')
HEADING = re.compile(r'^#{1,6}[ \t]')
LIST_ITEM = re.compile(r'^\s*(?:[-*+]|\d+\.)[ \t]')

# (name, regex, the group whose digits it exempts). What each one admits, and how it is verified, is in the
# module docstring; a test holds the two together.
EXEMPT = (
    ('repo-path', re.compile(r'(?<![\w/.-])((?:\.\.?/)*[\w.-]+(?:/[\w.-]+)*\.(?:md|yaml|yml|json|py))(?![\w/-])'), 1),
    ('benchmark-id', re.compile(r'`([a-z0-9][a-z0-9.+-]*)`'), 1),
    ('plan-section', re.compile(r'(?<![\w.])(\d{2}) S(\d+(?:\.\d+)*)(?![\w]|\.\d)'), 0),
    ('heading-number', re.compile(r'^(#{1,6}[ \t]+)(\d{1,2}(?:\.\d{1,2})*)(?=[.\s])', re.M), 2),
    ('section-ref', re.compile(r'(?<![\w.])([Ss]ections?[ \t]+)(\d{1,2}(?:\.\d{1,2})*)(?![\w]|\.\d)'), 2),
)
EXEMPT_RX = {name: rx for name, rx, _ in EXEMPT}


def mask(chars, start, end):
    for i in range(start, end):
        if chars[i] != '\n':
            chars[i] = ' '


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


def resolve(doc, path):
    """(value, None) for the one scalar `path` selects in `doc`, or (None, why not)."""
    pos, cur, where = 0, doc, ''
    for m in STEP.finditer(path):
        if m.start() != pos:
            break
        pos = m.end()
        key, sel = m.group(1), m.group(2)
        if key is not None:
            if not isinstance(cur, dict) or key not in cur:
                return None, '%s has no key %r' % (where or 'gaps.json', key)
            cur, where = cur[key], (where + '.' + key if where else key)
            continue
        if not isinstance(cur, list):
            return None, '%s is not a list, so [%s] selects nothing' % (where, sel)
        if sel.isdigit():
            if int(sel) >= len(cur):
                return None, '%s has %d elements, no [%s]' % (where, len(cur), sel)
            cur, where = cur[int(sel)], '%s[%s]' % (where, sel)
            continue
        conds = [c.split('=', 1) for c in sel.split(',')]
        if not sel or any(len(c) != 2 or not c[0] for c in conds):
            return None, '[%s] is neither an index nor key=value pairs' % sel
        hits = [x for x in cur if isinstance(x, dict) and all(str(x.get(k)) == v for k, v in conds)]  # get-default: an absent key matches nothing
        if len(hits) != 1:
            return None, '%d elements of %s match [%s]; a path selects exactly one' % (len(hits), where, sel)
        cur, where = hits[0], '%s[%s]' % (where, sel)
    if not path or pos != len(path):
        return None, 'cannot parse the path %r' % path
    if isinstance(cur, (dict, list)):
        return None, '%s is a %s, not one value' % (where, type(cur).__name__)
    return cur, None


def equal(text, value):
    if isinstance(value, bool):
        return text == ('true' if value else 'false')
    if value is None:
        return text == 'null'
    if isinstance(value, (int, float)):
        if not NUMBER.match(text) or (isinstance(value, int) and '.' in text):
            return False
        return float(text.replace(',', '')) == value
    return isinstance(value, str) and text == value


def family_of(path, doc):
    """The domain family a bound path is about, read off its selectors, or None."""
    if path == DENSITY_REFERENCE:
        ref = ((doc or {}).get('parameters') or {}).get('density_reference') or {}     # get-default: structure-only runs have no doc
        return ref.get('family')                                                       # get-default: as above
    fam, last_key = None, None
    for m in STEP.finditer(path):
        if m.group(1) is not None:
            last_key = m.group(1)
            continue
        conds = dict(c.split('=', 1) for c in m.group(2).split(',') if '=' in c)
        if 'family' in conds:
            fam = conds['family']
        elif last_key == 'families' and 'id' in conds:
            fam = conds['id']
    return fam


def is_density(path):
    m = re.search(r'\.([^.\[\]]+)$', path)
    return path == DENSITY_REFERENCE or bool(m and m.group(1) in DENSITY_KEYS)


def is_confidence(path):
    return path.endswith(CONFIDENCE_ENDS)


def layout(text):
    """Per line (1-based): its block (a table row, a heading, a list item, a code fence, or a paragraph) and its
    section (heading to heading)."""
    block, section, in_fence = {}, {}, False
    b, s, para = 0, 0, None
    for n, line in enumerate(text.split('\n'), 1):
        if FENCE.match(line):
            if not in_fence:
                b += 1
            in_fence = not in_fence
            block[n], section[n], para = b, s, None
            continue
        if in_fence:
            block[n], section[n] = b, s
            continue
        stripped = line.strip()
        if HEADING.match(line):
            s += 1
            b += 1
            para = None
        elif stripped.startswith('|'):
            b += 1
            para = None
        elif not stripped:
            para = None
        elif para is None or LIST_ITEM.match(line):
            b += 1
            para = b
        block[n], section[n] = b, s
    return block, section


def heading_lines(text):
    """The 1-based numbers of the heading lines outside code fences."""
    out, in_fence = set(), False
    for n, line in enumerate(text.split('\n'), 1):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and HEADING.match(line):
            out.add(n)
    return out


def quoted_ok(root, src, text):
    rel = src.replace('\\', '/')
    if not rel.startswith(QUOTABLE) or '..' in rel.split('/'):
        return 'quotes %s, which is not under %s' % (rel, ' or '.join(QUOTABLE))
    path = os.path.join(root, *rel.split('/'))
    if not os.path.isfile(path):
        return 'quotes %s, which does not exist' % rel
    with open(path, encoding='utf-8') as fh:
        body = re.sub(r'\s+', ' ', fh.read())
    want = re.sub(r'\s+', ' ', text.strip())
    if not want or not re.search(r'(?<![0-9A-Za-z])%s(?![0-9A-Za-z]|[.,][0-9])' % re.escape(want), body):
        return 'quotes %r from %s, which does not say it' % (want, rel)
    return None


def plan_section_ok(root, doc_no, sec):
    files = glob.glob(os.path.join(root, '_plan', '%s-*.md' % doc_no))
    if len(files) != 1:
        return 'cites %s S%s, but %d files match _plan/%s-*.md' % (doc_no, sec, len(files), doc_no)
    with open(files[0], encoding='utf-8') as fh:
        body = fh.read()
    if not re.search(r'^#{1,6}[ \t]+%s(?:\.|[ \t])' % re.escape(sec), body, re.M):
        return 'cites %s S%s, but %s has no heading numbered %s' % (doc_no, sec, os.path.basename(files[0]), sec)
    return None


def repo_file(root, preprint_dir, token):
    """True when `token` names a file inside the repository, read from the root or from the preprint's directory."""
    top = os.path.normcase(os.path.abspath(root))
    for base in (root, preprint_dir):
        path = os.path.normcase(os.path.abspath(os.path.join(base, *token.replace('\\', '/').split('/'))))
        if path.startswith(top + os.sep) and os.path.isfile(path):
            return True
    return False


def benchmark_ids(doc, root):
    if doc is not None:
        return set((doc.get('quality_weights') or {}))                                  # get-default: checked as a finding below
    return {os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))
            if os.path.basename(os.path.dirname(p)) != '_stubs'}


def check(text, doc, root=ROOT, preprint_dir=None):
    """(findings, report) for the preprint `text` against the gaps.json document `doc`. With doc None the values
    are not compared (the structure-only run a test makes when no artifact at the cited commit is at hand)."""
    errs, explain, bound = [], [], []
    quoted, exempt = Counter(), Counter()
    preprint_dir = preprint_dir or os.path.join(root, *os.path.dirname(PREPRINT).split('/'))
    if doc is not None:
        if doc.get('artifact') != 'gaps' or doc.get('grid') != 'coarse' or doc.get('reviewed_only') is not True:
            errs.append('--against is not the published gaps.json, the coarse grid made --reviewed-only (artifact %r, '
                        'grid %r, reviewed_only %r); run `%s`'
                        % (doc.get('artifact'), doc.get('grid'), doc.get('reviewed_only'), MAKE))
        if not (isinstance(doc.get('parameters'), dict) and SHA.match(str(doc['parameters'].get('data_commit')))):
            errs.append('gaps.json carries no data commit SHA, so no figure in it is a claim about the index at a commit; '
                        'build it in a git checkout')
    chars = list(text)

    for m in BOUND.finditer(text):
        path, shown, n = m.group('arg').strip(), m.group('text'), line_of(text, m.start())
        bound.append((n, path, shown))
        explain.append((n, shown, 'bound to %s' % path))
        mask(chars, m.start(), m.end())
        if doc is None:
            continue
        value, why = resolve(doc, path)
        if why:
            errs.append('line %d: %r is bound to %s, which selects nothing: %s' % (n, shown, path, why))
        elif not equal(shown, value):
            msg = 'line %d: %r is bound to %s, which gaps.json holds as %s' % (n, shown, path, json.dumps(value))
            if path == COMMIT:
                msg += ('. The preprint cites commit %s and gaps.json was built at %s: build gaps.json at the cited '
                        'commit (`git worktree add <dir> %s`, then `%s` there) and pass it with --against, or re-pin the '
                        'preprint' % (shown, value, shown, MAKE))
            errs.append(msg)

    for m in QUOTED.finditer(text):
        src, shown, n = m.group('arg').strip(), m.group('text'), line_of(text, m.start())
        why = quoted_ok(root, src, shown)
        if why:
            errs.append('line %d: %s' % (n, why))
        quoted[src.replace('\\', '/')] += 1
        explain.append((n, shown, 'quoted from %s' % src))
        mask(chars, m.start(), m.end())

    masked = ''.join(chars)
    for m in MARKER.finditer(masked):
        errs.append('line %d: a malformed gaps or quoted marker; write <!-- gaps: PATH -->TEXT<!-- /gaps --> or '
                    '<!-- quoted: SOURCE -->TEXT<!-- /quoted --> on one line' % line_of(masked, m.start()))
        mask(chars, m.start(), m.end())

    ids = benchmark_ids(doc, root)
    headings = heading_lines(text)
    lines = text.split('\n')
    own = {m.group(2) for m in (EXEMPT_RX['heading-number'].match(lines[n - 1]) for n in headings) if m}
    for name, rx, group in EXEMPT:
        masked = ''.join(chars)
        matches = _heading_matches(rx, masked, headings) if name == 'heading-number' else rx.finditer(masked)
        for m in matches:
            token, n = m.group(group), line_of(masked, m.start())
            if not DIGITS.search(token):
                continue
            if name == 'repo-path':
                if not repo_file(root, preprint_dir, token):
                    continue
            elif name == 'benchmark-id' and token not in ids:
                continue
            elif name == 'plan-section':
                why = plan_section_ok(root, m.group(1), m.group(2))
                if why:
                    errs.append('line %d: %s' % (n, why))
            elif name == 'section-ref' and token not in own:
                errs.append('line %d: refers to section %s, which no heading of the preprint carries' % (n, token))
            exempt[name] += 1
            explain.append((n, token, 'exempt: %s' % name))
            mask(chars, m.start(group), m.end(group))

    masked = ''.join(chars)
    for m in DIGITS.finditer(masked):
        n = line_of(masked, m.start())
        errs.append('line %d: %r is not bound to gaps.json, quoted with its source, or exempt by a stated rule: %s'
                    % (n, m.group(0), lines[n - 1].strip()[:160]))

    block, section = layout(text)
    commits = [b for b in bound if b[1] == COMMIT]
    if not commits:
        errs.append('the preprint never binds %s, so no finding in it is tied to a commit' % COMMIT)
    density = [b for b in bound if is_density(b[1])]
    confidence = defaultdict(set)
    for n, path, _ in bound:
        if is_confidence(path):
            confidence[block[n]].add(family_of(path, doc))
    for n, path, shown in density:
        fam = family_of(path, doc)
        here = confidence.get(block[n], set())
        if not here or (fam is not None and fam not in here):
            errs.append('line %d: density figure %r (%s) has no curation confidence of %s beside it in the same row or '
                        'paragraph (12 S5.3: confidence is printed beside every density figure)'
                        % (n, shown, path, fam or 'its family'))
    cited = {section[n] for n, _, _ in commits}
    for sec in sorted({section[n] for n, _, _ in density} - cited):
        first = min(n for n, _, _ in density if section[n] == sec)
        errs.append('line %d: this section prints density figures but never binds %s; state each finding as a claim '
                    'about the index at that commit' % (first, COMMIT))

    report = {'bound': len(bound), 'paths': len({p for _, p, _ in bound}), 'quoted': dict(quoted),
              'exempt': dict(exempt), 'density': len(density), 'sections': len({section[n] for n, _, _ in density}),
              'commit': commits[0][2] if commits else None, 'explain': sorted(explain)}
    return errs, report


def _heading_matches(rx, masked, headings):
    """heading-number applies to heading lines outside code fences only."""
    starts = [0]
    for line in masked.split('\n'):
        starts.append(starts[-1] + len(line) + 1)
    for n in sorted(headings):
        m = rx.match(masked, starts[n - 1])
        if m:
            yield m


def cited_commits(text):
    """The commit texts the preprint binds to parameters.data_commit (tests use it to find the pinned commit)."""
    return [m.group('text') for m in BOUND.finditer(text) if m.group('arg').strip() == COMMIT]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--preprint', default=PREPRINT, help='default: %s' % PREPRINT)
    ap.add_argument('--against', default=ARTIFACT, help='the gaps.json built at the cited commit (default: %s)' % ARTIFACT)
    ap.add_argument('--root', default=ROOT, help='the repository root the exemptions are verified against')
    ap.add_argument('--explain', action='store_true', help='list every number in the preprint and how it is accounted for')
    a = ap.parse_args(argv)
    paths = {}
    for name, p in (('preprint', a.preprint), ('artifact', a.against)):
        paths[name] = p if os.path.isabs(p) else os.path.join(a.root, *p.replace('\\', '/').split('/'))
    if not os.path.isfile(paths['preprint']):
        print('FAIL  %s does not exist' % a.preprint)
        return 2
    if not os.path.isfile(paths['artifact']):
        print('FAIL  %s does not exist: run `%s` at the commit the preprint cites' % (a.against, MAKE))
        return 2
    with open(paths['preprint'], encoding='utf-8') as fh:
        text = fh.read()
    with open(paths['artifact'], encoding='utf-8') as fh:
        doc = json.load(fh)
    errs, rep = check(text, doc, a.root, os.path.dirname(os.path.abspath(paths['preprint'])))
    if a.explain:
        for n, token, how in rep['explain']:
            print('      line %4d  %-24s %s' % (n, token if len(token) <= 24 else token[:21] + '...', how))
    if errs:
        print('\n'.join('FAIL  ' + e for e in errs))
        print('%d problem(s)' % len(errs))
        return 1
    print('OK    %d figures bound to gaps.json (%d distinct paths), each equal to its value at data commit %s (as of %s)'
          % (rep['bound'], rep['paths'], rep['commit'], doc['parameters'].get('as_of')))
    print('      %d quoted, each verbatim in its source: %s'
          % (sum(rep['quoted'].values()), ', '.join('%d from %s' % (k, s) for s, k in sorted(rep['quoted'].items())) or 'none'))
    print('      exempt by rule: %s; no other number in the file'
          % (', '.join('%d %s' % (rep['exempt'].get(name, 0), name) for name, _, _ in EXEMPT)))
    print('      %d density figures, each beside its family\'s curation confidence; the %d sections that print them '
          'each cite the commit' % (rep['density'], rep['sections']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
