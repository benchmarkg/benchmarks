"""The issue-intake bot, step 1: an issue form in, a draft entry or field-level errors out (P2-S6-T04;
05-repository-and-workflow.md S6, Path A and "The validation bot"; 08 S3.4 and S7.3; ADR-0022).

    python -m tools.intake.parse_form --event EVENT.json [--out DIR] [--result RESULT.json]
    python -m tools.intake.parse_form --form new-benchmark --body BODY.md [--issue N] [--out DIR] [--result ...]

`--event` is the `issues` event GitHub writes to $GITHUB_EVENT_PATH. Nothing here touches the network or holds a
token: tools/intake/open_pr.py, the workflow's second step, does the GitHub side from RESULT.json, so the
untrusted issue body is parsed in a process with no credential in it.

The body. A submitted form is Markdown: `### <label>`, a blank line, then the answer; `_No response_` for a blank,
a multiple-choice dropdown's options joined by ", ", a checkbox as `- [X] <label>`. Labels and ids are read from
.github/ISSUE_TEMPLATE/<form>.yml, so the parser follows the form as scripts/gen_issue_forms.py regenerates it. A
heading the contributor deleted reads as a blank answer, and says so; text under no known heading is ignored.

Which form: the `form:<name>` label each form puts on its issue.

  new-benchmark   checked field by field, then drafted (below)
  correction, new-claim, dispute
                  checked field by field (required answers, ticked boxes, one-line inputs, https URLs, ISO
                  dates, dropdown options); a submission that passes is status `human`, which open_pr.py
                  labels needs-human for a maintainer. The bot drafts none of them yet.
  taxonomy-term   the same, and never a pull request: a term goes to an ADR (05 S5)

Where the draft goes: drafts/, not data/. Three reasons, all from the repository as it stands:

  - 05 S6 step 4 (and the task) set `curation.verification_status: ai-drafted-unverified`. Check 9i forbids that
    anywhere under data/, and it is exactly what schema/draft.py's BenchmarkDraft holds (P1-S2-T01).
  - The form cannot fill a Benchmark. `learned_entrant_evidence`, `data.access` and `evaluation_target` in the
    schema's terms are required there and the form does not ask for them (ADR-0022, "Observed"); filling them
    would be a guess recorded as a fact. A draft holds them null, says why in an `absent` evidence row, and a
    curator completes and promotes it (drafts/README.md, `bench promote`).
  - A draft is never built or published, so nothing a contributor typed is citable before a person has read
    the sources it links.

A valid submission becomes two files:

    drafts/benchmarks/<id>.yaml    a BenchmarkDraft: each answer in its field, with an evidence row quoting the
                                   answer, confidence low (no one has opened the sources yet); each field the
                                   form does not ask for null, with an absent row saying so
    drafts/sources/src-<owner>-issue-<n>-<yyyy>.yaml
                                   a SourceDraft: the issue body, normalised as 04 S9 fixes, which every quote
                                   in the draft is checked against

The id. 04 S3: a lowercase kebab slug, permanent, and allocated by a person. The bot PROPOSES one from the name
(Greek letters spelled out, other letters transliterated where Unicode can, every other run of characters one
hyphen, at most 50 characters), and a review check asks a person to confirm it. It refuses, as an error on the
name, a name that yields no id, and a name or id the index already holds: a curated benchmark or one of its
aliases (ingest.resolve over data/benchmarks/ and data/aliases/benchmarks.yaml, so `GPQA diamond` is gpqa's
subset), a tombstone, a retired id or a draft already waiting. A stub (data/benchmarks/_stubs/) is not refused:
the draft takes its id and a review check says to promote the stub with it.

Validation. The answers are checked first, field by field, so every error names a form field in words a
contributor can act on (05 S6: "field-level errors only ... never a raw Pydantic error dump"). The draft is
then rendered as `bench fmt` writes it, run through `bench validate --single --tier schema,ref,semantic`
(tiers.single, in process) and its quotes through the tier-3 quote-substring check against the snapshot. A
finding that maps to a form field is reported against that field; one that does not is the bot's own bug and
makes the result `error`, which open_pr.py reports without details and labels needs-human.

ADR-0022 (Proposed) settles the front half: the submission is an ingest.adapters.base Payload (source_key
`issue:<n>`; nothing is fetched, so its HTTP fields hold 200, None, None, False), `normalise(payload, resolver)` is
pure (no clock, network or file: the dates are the event's), a field-level error is an Unresolved (its
fingerprint stable across edits), and the duplicate check is ingest.resolve's benchmark Index. The Index is
built from a fast read of each entry's id, name, aliases, external ids and versions, so the bot stays inside
08 S3.4's 90 seconds. No submitter's name or handle is read into anything this module writes.

RESULT.json: {form, issue, status, errors, files, entity_id, title, source_id, steward_path}. `status` is
drafted | invalid | human | skipped | error; `errors` are {field, label, observed, reason, message, suggestions,
fingerprint}; `files` maps each root-relative path the pull request writes to its text.
"""
from __future__ import annotations

import argparse
import difflib
import glob
import hashlib
import json
import os
import re
import sys
import tempfile
import traceback
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ingest.adapters.base import Candidate, Draft, Payload, Unresolved  # noqa: E402
from ingest.resolve import Entry, Index  # noqa: E402

FORMS = os.path.join('.github', 'ISSUE_TEMPLATE')
KNOWN_FORMS = ('new-benchmark', 'correction', 'new-claim', 'dispute', 'taxonomy-term')
DRAFTED = ('new-benchmark',)
FIELD_TYPES = ('input', 'textarea', 'dropdown', 'checkboxes')
NO_RESPONSE = '_No response_'
TIERS = ('schema', 'ref', 'semantic')                   # the task's `bench validate --single --tier schema,ref,semantic`
PR_LABELS = ('source:issue-form', 'verification:curator-review-needed')
DRAFTED_BY = 'issue-intake bot (tools/intake/parse_form.py)'
DEFAULT_REPO = 'benchmarkg/benchmarks'
TAGLINE_MAX = 120                                       # 05 S6: "One-sentence description (input, required, <=120 chars)"
LINE_MAX = 300                                          # a one-line answer; the name and organisation are far shorter
SLUG_MAX = 50
EXTRACT_CAP = 64 * 1024

HEADING = re.compile(r'^###[ \t]+(.+?)[ \t]*$')
BOX = re.compile(r'^[ \t]*[-*][ \t]*\[([ xX])\][ \t]*(.+?)[ \t]*$', re.M)
URL = re.compile(r'^https://[^\s<>"\'`]+$')
ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
SIZE = re.compile(r'^(\d{1,3}(?:[,_ \u00a0\u202f]\d{3})+|\d+)(?:\s+(\S.*))?$')
ARXIV = re.compile(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})')
SLUG = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}$')
TERM = re.compile(r'\(([^()\s]+)\)\s*$')
TOP_KEY = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):')
HEAD_KEYS = frozenset({'id', 'name', 'aliases', 'external_ids', 'versions'})

GREEK = dict(zip('αβγδεζηθικλμνξοπρσςτυφχψω',
                 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma '
                 'sigma tau upsilon phi chi psi omega'.split()))

# The four generated vocabulary dropdowns (scripts/gen_issue_forms.py): form id -> the vocabulary and its file.
VOCAB = {'primary-domain': ('domains', 'domains.yaml'), 'secondary-domains': ('domains', 'domains.yaml'),
         'capabilities': ('capabilities', 'capabilities.yaml'),
         'evaluation-method': ('evaluation-methods', 'evaluation-methods.yaml')}
URL_FIELDS = frozenset({'homepage', 'repository', 'dataset-url', 'leaderboard-url', 'source-url'})
DATE_FIELDS = frozenset({'released', 'date-reported'})
# 05 S6's "What is evaluated" against the schema (ADR-0022, "Observed"): all three named kinds are learned systems
# (00 S6 A5), and `other` names no evaluation_target term. Only "agent scaffold" is a subject term as it stands.
TARGETS = {'model': 'learned-system', 'agent scaffold': 'learned-system', 'full pipeline': 'learned-system'}
SUBJECTS = {'agent scaffold': 'agent-scaffold'}
# The draft path a new-benchmark field fills -> the form field it comes from, for mapping a finding back.
FROM_FORM = {'name': 'name', 'tagline': 'tagline', 'external_ids.arxiv': 'homepage', 'released': 'released',
             'domain.primary': 'primary-domain', 'domain.secondary': 'secondary-domains', 'capability': 'capabilities',
             'evaluation_method': 'evaluation-method', 'designed_for_subjects': 'what-is-evaluated',
             'evaluation_target': 'what-is-evaluated', 'data.size': 'size', 'data.dataset_licence': 'licence',
             'governance.maintainer': 'maintainer', 'homepage': 'homepage', 'repository': 'repository',
             'leaderboard_url': 'leaderboard-url', 'dataset_url': 'dataset-url'}
# Why a drafted field the form does not fill is null: the note on its `absent` evidence row.
NOT_ASKED = {
    'description': 'the form asks for a one-sentence description (the tagline), not a description',
    'paper.title': "the form does not ask for the paper's title",
    'learned_entrant_evidence': 'the form does not ask which learned system has been evaluated on it (00 S6 A5)',
    'task.output': 'the form does not ask what an item asks the system to produce',
    'task.scoring': 'the form does not ask how an answer is scored beyond the evaluation method',
    'data.access': 'the form does not ask how the items are accessed',
    'execution.code_licence': ("the form asks for one licence, recorded as data.dataset_licence; "
                               "see curation.review_checks"),
}
STEWARD_PATHS = {'correction': 'data/', 'new-claim': 'data/claims/', 'dispute': 'data/disputes/',
                 'taxonomy-term': 'taxonomy/'}


class IntakeError(RuntimeError):
    """The bot's own failure, never the contributor's: reported as `error`, with no detail on the issue."""


# ---- the forms ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FormField:
    id: str
    label: str
    type: str                               # input | textarea | dropdown | checkboxes
    required: bool
    multiple: bool = False
    options: tuple[str, ...] = ()
    ticks: tuple[str, ...] = ()             # a checkboxes field's required boxes
    hint: str = ''                          # the form's own description of the field


@dataclass(frozen=True)
class Form:
    name: str
    fields: tuple[FormField, ...]
    digest: str                             # the form file's sha256: a draft's prompt_version names it

    def get(self, ident: str) -> FormField:
        return next(f for f in self.fields if f.id == ident)


def load_form(name: str, root: str = ROOT) -> Form:
    from ruamel.yaml import YAML
    path = os.path.join(root, FORMS, name + '.yml')
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    doc = YAML(typ='safe').load(text) or {}
    fields = []
    for item in doc.get('body') or []:
        kind = item.get('type')
        if kind not in FIELD_TYPES:
            continue
        a = item.get('attributes') or {}
        hint = ' '.join(str(a.get('description') or '').split())
        if kind == 'checkboxes':
            opts = [o for o in a.get('options') or []]
            fields.append(FormField(item['id'], str(a['label']), kind, any(o.get('required') for o in opts),
                                    options=tuple(str(o['label']) for o in opts),
                                    ticks=tuple(str(o['label']) for o in opts if o.get('required')), hint=hint))
        else:
            fields.append(FormField(item['id'], str(a['label']), kind,
                                    bool((item.get('validations') or {}).get('required')),
                                    bool(a.get('multiple')), tuple(str(o) for o in a.get('options') or []), hint=hint))
    labels = [f.label for f in fields]
    if len(set(labels)) != len(labels):
        raise IntakeError('%s.yml: two fields share a label, so its issue body cannot be parsed' % name)
    return Form(name, tuple(fields), hashlib.sha256(text.encode('utf-8')).hexdigest())


def form_for(labels, root: str = ROOT) -> str | None:
    """The form an issue came from: its `form:<name>` label, when that form exists."""
    for label in labels:
        if label.startswith('form:') and label[5:] in KNOWN_FORMS and \
                os.path.exists(os.path.join(root, FORMS, label[5:] + '.yml')):
            return label[5:]
    return None


# ---- the body ----------------------------------------------------------------------------------------------

def split_options(text: str, options) -> list[str]:
    """A multiple-choice answer: GitHub joins the chosen options with ", ", and an option may hold ", " itself."""
    known, out, buf = set(options), [], []
    for piece in (p.strip() for p in text.split(', ')):
        buf.append(piece)
        if ', '.join(buf) in known:
            out.append(', '.join(buf))
            buf = []
        elif piece in known:
            out += [b for b in buf[:-1] if b] + [piece]
            buf = []
    return out + [b for b in buf if b]


def parse_body(body: str, form: Form) -> tuple[dict[str, Any], list[str]]:
    """({field id: answer}, the ids whose heading is not in the body). An answer is None when blank, a string
    for an input, a textarea or a single dropdown, a list of option texts for a multiple dropdown, and
    {box label: ticked} for checkboxes. The first heading of each label wins; a repeat is answer text."""
    by_label = {f.label: f for f in form.fields}
    sections: dict[str, list[str]] = {}
    current = None
    for line in (body or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        m = HEADING.match(line)
        if m and m.group(1) in by_label and m.group(1) not in sections:
            current = m.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    answers: dict[str, Any] = {}
    missing = []
    for f in form.fields:
        if f.label not in sections:
            missing.append(f.id)
            answers[f.id] = {} if f.type == 'checkboxes' else None
            continue
        text = '\n'.join(sections[f.label]).strip()
        if f.type == 'checkboxes':
            answers[f.id] = {m.group(2): m.group(1) in 'xX' for m in BOX.finditer(text)}
        elif text in ('', NO_RESPONSE):
            answers[f.id] = None
        elif f.type == 'dropdown' and f.multiple:
            answers[f.id] = split_options(text, f.options)
        else:
            answers[f.id] = text
    return answers, missing


# ---- the resolver: everything normalise() reads besides the payload ------------------------------------------

@dataclass(frozen=True)
class Resolver:
    forms: dict[str, Form]
    benchmarks: Index                       # ingest.resolve's, over curated benchmarks and their alias table
    held: dict[str, str]                    # an id the bot may not propose -> why, as a clause
    stubs: frozenset[str]
    vocab: dict[str, frozenset[str]]        # domains (assignable subdomains), families, capabilities, evaluation-methods
    repo: str


def _head(path: str) -> dict:
    """The id, name, aliases, external ids and versions of one entry: only those top-level keys are parsed.
    `bench fmt` writes a top-level key at column 0 and everything under it indented, so a key's block is the
    run of lines from it to the next top-level key."""
    from ruamel.yaml import YAML
    keep, out = False, []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            m = TOP_KEY.match(line)
            if m:
                keep = m.group(1) in HEAD_KEYS
            if keep:
                out.append(line)
    doc = YAML(typ='safe').load(''.join(out))
    return doc if isinstance(doc, dict) else {}


def benchmark_index(root: str = ROOT) -> Index:
    """ingest.resolve.Index('benchmark') over data/benchmarks/<family>/ (stubs are not resolution targets) and
    data/aliases/benchmarks.yaml, as Index.load builds it, from a read of five keys instead of every record."""
    from schema.entities import AliasFile
    from schema.taxonomy import read_yaml
    entries = []
    for p in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '*', '*.yaml'))):
        if os.sep + '_stubs' + os.sep in p:
            continue
        d = _head(p)
        entries.append(Entry(
            str(d.get('id') or os.path.basename(p)[:-5]), str(d.get('name') or ''),       # get-default: optional keys
            tuple(str(a) for a in d.get('aliases') or ()),                                  # get-default: as above
            tuple(str(v) for v in (d.get('external_ids') or {}).values() if v),           # get-default: as above
            tuple((str(v['version']), v.get('api_identifier')) for v in d.get('versions') or ()  # get-default: as above
                  if isinstance(v, dict) and v.get('version') is not None)))
    aliases = ()
    path = os.path.join(root, 'data', 'aliases', 'benchmarks.yaml')
    if os.path.exists(path):
        aliases = AliasFile.model_validate(read_yaml(path) or []).root
    return Index('benchmark', entries, aliases)


def load_resolver(root: str = ROOT, repo: str = DEFAULT_REPO) -> Resolver:
    from schema.benchmark import Capability, DomainLeaf, EvaluationMethod
    from schema.taxonomy import RetiredIdFile, read_yaml
    held: dict[str, str] = {}
    retired = os.path.join(root, 'taxonomy', 'retired-ids.yaml')
    if os.path.exists(retired):
        for r in RetiredIdFile.model_validate(read_yaml(retired)).retired:
            held[r.id] = 'is retired, and an id is never reused (04 S3)'
    for p in glob.glob(os.path.join(root, 'data', 'tombstones', '**', '*.yaml'), recursive=True):
        target = (read_yaml(p) or {}).get('redirects_to')                         # get-default: optional key
        held[os.path.basename(p)[:-5]] = ('was merged into `%s`' % target if target
                                          else 'is a tombstone, and an id is never reused (04 S3)')
    for p in glob.glob(os.path.join(root, 'drafts', 'benchmarks', '*.yaml')):
        held[os.path.basename(p)[:-5]] = 'already has a draft waiting for review (drafts/benchmarks/)'
    stubs = frozenset(os.path.basename(p)[:-5] for p in
                      glob.glob(os.path.join(root, 'data', 'benchmarks', '_stubs', '*.yaml')))
    leaves = frozenset(DomainLeaf.__args__)
    forms = {n: load_form(n, root) for n in KNOWN_FORMS if os.path.exists(os.path.join(root, FORMS, n + '.yml'))}
    return Resolver(forms, benchmark_index(root), held, stubs,
                    {'domains': leaves, 'families': frozenset(x.split('/')[0] for x in leaves),
                     'capabilities': frozenset(Capability.__args__),
                     'evaluation-methods': frozenset(EvaluationMethod.__args__)}, repo)


# ---- the payload (ADR-0022: the adapter contract's front half) ------------------------------------------------

def _when(stamp: str | None) -> datetime:
    if not stamp:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return datetime.fromisoformat(stamp.replace('Z', '+00:00'))


def payload_from(issue: dict, form: Form, repo: str = DEFAULT_REPO) -> Payload:
    """07 S1.1's Payload for one issue. Nothing is fetched, so the HTTP fields carry placeholders (ADR-0022's
    first ask, deferred until it is accepted: ingest/adapters/base.py). `doc` holds the parsed answers and
    what normalise() needs of the issue; never the author."""
    body = issue.get('body') or ''
    answers, missing = parse_body(body, form)
    number = int(issue['number'])
    url = issue.get('html_url') or 'https://github.com/%s/issues/%d' % (repo, number)
    doc = {'form': form.name, 'answers': answers, 'missing': missing, 'number': number, 'url': url, 'repo': repo,
           'year': _when(issue.get('created_at') or issue.get('updated_at')).year}
    canon = json.dumps({'form': form.name, 'answers': answers}, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False)
    kind = 'claim' if form.name in ('new-claim', 'dispute') else 'benchmark'   # what the form proposes or concerns
    return Payload(candidate=Candidate('issue:%d' % number, kind, url, {'form': form.name + '.yml'}),
                   body=body.encode('utf-8'), content_type='text/markdown', http_status=200,
                   fetched_at=_when(issue.get('updated_at') or issue.get('created_at')), etag=None,
                   last_modified=None, sha256_normalised=hashlib.sha256(canon.encode('utf-8')).hexdigest(),
                   from_cache=False, doc=doc)


# ---- field-level checks ------------------------------------------------------------------------------------

def _code(value: Any, cap: int = 80) -> str:
    """A contributor's value inside a message: one line, no backtick to break out of the code span, capped."""
    s = ' '.join(str(value).replace('`', "'").split())
    return '`%s`' % (s if len(s) <= cap else s[:cap - 3] + '...')


def _err(key: str, f: FormField, observed: Any, reason: str, task: str, suggestions=()) -> Unresolved:
    return Unresolved(source_key=key, field=f.id, observed=' '.join(str(observed or '').split())[:200],
                      reason=reason, suggestions=list(suggestions), human_task=task)


def _term(option: str) -> str:
    """The id an option carries in its last parentheses (`Protein design (biology-genetics/protein-design)`),
    or the text itself when the contributor wrote a bare id."""
    m = TERM.search(option)
    return m.group(1) if m else option.strip()


def check_answers(form: Form, answers: dict, missing: list, key: str, today: date) -> list[Unresolved]:
    """What every form is held to: required answers, ticked boxes, one-line inputs, URLs, dates, options."""
    out = []
    for f in form.fields:
        v = answers[f.id]
        gone = ' Its heading, `### %s`, is missing from the issue: the bot reads each answer under its heading.' \
            % f.label if f.id in missing else ''
        if f.type == 'checkboxes':
            for box in f.ticks:
                if not v.get(box):                                    # get-default: a box the body lacks is unticked
                    out.append(_err(key, f, box, 'policy', '%s: tick "%s". The bot cannot take the submission '
                                                           'without it.%s' % (f.label, box, gone)))
            continue
        if v is None:
            if f.required:
                out.append(_err(key, f, '', 'policy', '%s is empty, and it is required. %s%s'
                                % (f.label, f.hint, gone)))
            continue
        if f.type == 'input' and '\n' in v:
            out.append(_err(key, f, v, 'unparseable', '%s should be one line.' % f.label))
            continue
        if f.type == 'input' and len(v) > LINE_MAX:
            out.append(_err(key, f, v, 'unparseable', '%s is %d characters long; keep it under %d.'
                            % (f.label, len(v), LINE_MAX)))
            continue
        if f.type == 'dropdown' and f.id not in VOCAB:
            for x in v if isinstance(v, list) else [v]:
                if x not in f.options:
                    near = difflib.get_close_matches(x, f.options, n=2, cutoff=0.5)
                    out.append(_err(key, f, x, 'no-match', '%s %s is not one of the form\'s options (%s).%s' % (
                        f.label, _code(x), ', '.join(f.options[:8]) + (', ...' if len(f.options) > 8 else ''),
                        ' Did you mean %s?' % ' or '.join(_code(n) for n in near) if near else ''),
                        [(n, 1.0) for n in near]))
        if f.id in URL_FIELDS and not URL.match(v):
            out.append(_err(key, f, v, 'unparseable', '%s %s is not a web address the bot can use: it must start '
                                                     'with https:// and hold no spaces.' % (f.label, _code(v))))
        if f.id in DATE_FIELDS:
            out += _date(key, f, v, today)
    return out


def _date(key: str, f: FormField, v: str, today: date) -> list[Unresolved]:
    try:
        d = date.fromisoformat(v) if ISO_DATE.match(v) else None
    except ValueError:
        d = None
    if d is None:
        return [_err(key, f, v, 'unparseable', '%s %s is not a date the bot can read: write it as YYYY-MM-DD, for '
                                              'example 2024-03-15. Leave it blank if you are not sure.'
                     % (f.label, _code(v)))]
    if d > today:
        return [_err(key, f, v, 'out-of-band', '%s %s is after today. Give the date it was released, or leave it '
                                              'blank.' % (f.label, _code(v)))]
    return []


def _vocab(key: str, f: FormField, values: list[str], resolver: Resolver) -> tuple[list[str], list[Unresolved]]:
    """The term ids a vocabulary dropdown's options carry, and an error for each that is not a live term."""
    name, filename = VOCAB[f.id]
    live, out, ids = resolver.vocab[name], [], []
    link = 'https://github.com/%s/blob/main/taxonomy/%s' % (resolver.repo, filename)
    for option in values:
        term = _term(option)
        if term in live:
            if term not in ids:
                ids.append(term)
            continue
        if name == 'domains' and term in resolver.vocab['families']:
            first = sorted(x for x in live if x.startswith(term + '/'))[0]
            out.append(_err(key, f, term, 'no-match', '%s %s is a domain family, which is not assignable: pick one '
                                                      'of its subdomains, for example %s. The full list is here: %s'
                            % (f.label, _code(term), _code(first), link)))
            continue
        # a subdomain of a real family is matched within the family, by its own name: across the whole list the
        # shared family prefix would make every sibling look close
        family, _, leaf = term.partition('/')
        siblings = sorted(x for x in live if x.startswith(family + '/')) if name == 'domains' and leaf else []
        if siblings:
            near = ['%s/%s' % (family, n) for n in difflib.get_close_matches(
                leaf, [x.split('/', 1)[1] for x in siblings], n=2, cutoff=0.6)]
        else:
            near = difflib.get_close_matches(term, sorted(live), n=2, cutoff=0.6)
        if near:
            hint = ' Did you mean %s?' % ' or '.join(_code(n) for n in near)
        elif siblings:
            hint = ' The %s subdomains are %s.' % (family, ', '.join(_code(s) for s in siblings))
        else:
            hint = ''
        out.append(_err(key, f, term, 'no-match', '%s %s is not in the vocabulary.%s The full list is here: %s'
                        % (f.label, _code(term), hint, link), [(n, 1.0) for n in near]))
    return ids, out


def propose_id(name: str) -> tuple[str | None, list[str]]:
    """(the proposed id or None, the letters it could not spell). 04 S3's grammar: a lowercase kebab slug."""
    spelled, lost = [], []
    for ch in name:
        if ch.lower() in GREEK:
            spelled.append('-%s-' % GREEK[ch.lower()])
            continue
        ascii_ = unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore').decode('ascii')
        if not ascii_ and unicodedata.category(ch).startswith('L'):
            lost.append(ch)
        spelled.append(ascii_ or ' ')
    slug = re.sub(r'[^a-z0-9]+', '-', ''.join(spelled).lower()).strip('-')[:SLUG_MAX].strip('-')
    return (slug if SLUG.match(slug) else None), lost


def check_new_benchmark(form: Form, a: dict, key: str, resolver: Resolver,
                        skip=frozenset()) -> tuple[dict, list[Unresolved]]:
    """new-benchmark.yml's own rules: ({what the draft needs}, errors). A field in `skip` already has an error
    from check_answers, and a blank one has nothing to check, so every error comes back in one pass."""
    out: list[Unresolved] = []
    got: dict[str, Any] = {}

    def has(fid):
        return fid not in skip and a[fid] is not None
    if has('tagline') and len(a['tagline']) > TAGLINE_MAX:
        f = form.get('tagline')
        out.append(_err(key, f, a['tagline'], 'out-of-band', '%s is %d characters; keep it to %d or fewer.'
                        % (f.label, len(a['tagline']), TAGLINE_MAX)))
    for fid in VOCAB:
        v = a[fid] if has(fid) else []
        got[fid], errs = _vocab(key, form.get(fid), v if isinstance(v, list) else [v], resolver)
        out += errs
    primary = got['primary-domain'][0] if got['primary-domain'] else None
    if primary and primary in got['secondary-domains']:
        f = form.get('secondary-domains')
        out.append(_err(key, f, primary, 'policy', '%s repeats the primary domain %s; leave it out of the secondary '
                                                   'list.' % (f.label, _code(primary))))
    if has('size'):
        m = SIZE.match(a['size'])
        if not m or not m.group(2):
            f = form.get('size')
            out.append(_err(key, f, a['size'], 'unparseable', '%s %s should be a whole number, then its unit, for '
                                                              'example `2,294 task instances`. Leave it blank if you '
                                                              'are not sure.' % (f.label, _code(a['size']))))
        else:
            got['size'] = (int(re.sub(r'\D', '', m.group(1))), m.group(2).strip())
    if has('name'):
        out += _identity(form, a['name'], key, resolver, got)
    return got, out


def _identity(form: Form, name: str, key: str, resolver: Resolver, got: dict) -> list[Unresolved]:
    """The proposed id, and the refusals: no id, or a benchmark the index already holds (04 S3, 04 S10)."""
    f = form.get('name')
    ident, lost = propose_id(name)
    if ident is None:
        return [_err(key, f, name, 'unparseable', '%s %s gives the bot no id: an id is made of the Latin letters and '
                                                  'digits in the name. Add the name\'s Latin-script form, for '
                                                  'example in brackets after it.' % (f.label, _code(name)))]
    for raw in (name, ident):
        r = resolver.benchmarks.resolve(raw)
        if r.entity:
            held = r.entity.split(':', 1)[1]
            if r.subset:
                what = 'as a subset of `%s` (`%s`), not as a benchmark of its own' % (held, r.subset)
            elif r.version:
                what = 'as version `%s` of `%s`' % (r.version, held)
            else:
                what = 'as `%s`' % held
            return [_err(key, f, name, 'policy', '%s %s: the index already holds this %s. To change a field on it, '
                                                 'use the Correction form instead. If yours is a different benchmark '
                                                 'with a similar name, give its full, distinguishing name.'
                         % (f.label, _code(name), what), [(r.entity, r.score)])]
    if ident in resolver.held:
        return [_err(key, f, name, 'policy', '%s %s: the id the bot would give it, `%s`, %s. Give the benchmark\'s '
                                             'full, distinguishing name, or use the Correction form if it is the same '
                                             'benchmark.' % (f.label, _code(name), ident, resolver.held[ident]))]
    got['id'], got['lost'] = ident, lost
    return []


# ---- normalise(): pure, as 07 S1.1 requires ------------------------------------------------------------------

def normalise(payload: Payload, resolver: Resolver) -> tuple[list[Draft], list[Unresolved]]:
    """(drafts, field-level errors) for one submission. No clock, network or file: the date is the event's. Any
    error means no draft (05 S6: the bot never opens a broken pull request). A form the bot does not draft
    returns ([], []) when its answers pass."""
    doc = payload.doc
    form = resolver.forms[doc['form']]
    key = payload.candidate.source_key
    today = payload.fetched_at.date()
    errors = check_answers(form, doc['answers'], doc['missing'], key, today)
    if doc['form'] not in DRAFTED:
        return [], errors
    got, more = check_new_benchmark(form, doc['answers'], key, resolver, frozenset(u.field for u in errors))
    order = [f.id for f in form.fields]
    errors = sorted(errors + more, key=lambda u: order.index(u.field))      # in the form's order, as read
    if errors:
        return [], errors
    return draft_new_benchmark(payload, form, got, resolver)


def _day(d: date) -> date:
    """A fresh date object: the emitter writes one object used twice as a YAML anchor and alias."""
    return date.fromordinal(d.toordinal())


def source_id(repo: str, number: int, year: int) -> str:
    """05 S2's `src-<org>-<slug>-<yyyy>`: the repository's owner, the issue, the year it was opened."""
    owner = re.sub(r'[^a-z0-9]+', '-', repo.split('/')[0].lower()).strip('-') or 'github'
    return 'src-%s-issue-%d-%d' % (owner, number, year)


def draft_new_benchmark(payload: Payload, form: Form, got: dict, resolver: Resolver) -> tuple[list[Draft], list]:
    from schema.draft import DRAFT_FIELDS
    from schema.source import extract_sha256, normalise as normalised, quote_found
    doc, a = payload.doc, payload.doc['answers']
    key, number, today = payload.candidate.source_key, doc['number'], payload.fetched_at.date()
    body = payload.body.decode('utf-8')
    extract = normalised(body)
    if len(extract.encode('utf-8')) > EXTRACT_CAP:
        f = form.get('notes')
        return [], [_err(key, f, '', 'out-of-band', 'The issue is too long for the bot to keep as its source (%d bytes; '
                                                    'at most %d). Shorten "%s".' % (len(extract.encode('utf-8')),
                                                                                   EXTRACT_CAP, f.label))]
    sid, ident = source_id(doc['repo'], number, doc['year']), got['id']
    rec: dict[str, Any] = {'id': ident}
    rows: list[dict] = []
    unread: list[Unresolved] = []

    def quoted(fid: str, answer: str) -> str | None:
        q = normalised(answer)
        if q and quote_found(q, extract):
            return q
        f = form.get(fid)
        unread.append(_err(key, f, answer, 'unparseable', '%s: the bot could not read this answer back from the issue '
                                                          'exactly. Remove any HTML or angle-bracket markup from it.'
                           % f.label))
        return None

    def put(path: str, value: Any, fid: str, answer: str, term: str | None = None):
        q = quoted(fid, answer)
        rows.append({'field': path, 'term': term, 'confidence': 'low', 'source': sid, 'quote': q,
                     'note': 'the answer to "%s" on the form' % form.get(fid).label})
        if term is None:
            node = rec
            for p in path.split('.')[:-1]:
                node = node.setdefault(p, {})
            node[path.split('.')[-1]] = value

    def absent(path: str, why: str):
        rows.append({'field': path, 'confidence': 'absent', 'note': why})

    blank = 'left blank on the form'
    put('name', a['name'], 'name', a['name'])
    put('tagline', a['tagline'], 'tagline', a['tagline'])
    absent('description', NOT_ASKED['description'])
    absent('paper.title', NOT_ASKED['paper.title'])
    arxiv = next(((fid, m.group(1)) for fid in ('homepage', 'repository', 'dataset-url', 'leaderboard-url')
                  for m in [ARXIV.search(a[fid] or '')] if m), None)
    if arxiv:
        put('external_ids.arxiv', arxiv[1], arxiv[0], a[arxiv[0]])
    else:
        absent('external_ids.arxiv', 'no arXiv link among the URLs on the form')
    if a['released']:
        put('released', date.fromisoformat(a['released']), 'released', a['released'])
    else:
        absent('released', blank)
    primary_option = a['primary-domain']
    put('domain.primary', got['primary-domain'][0], 'primary-domain', primary_option)
    for fid, path in (('secondary-domains', 'domain.secondary'), ('capabilities', 'capability'),
                      ('evaluation-method', 'evaluation_method')):
        options = {_term(o): o for o in a[fid] or []}
        if not got[fid]:
            absent(path, 'none chosen on the form')
            continue
        node = rec
        for p in path.split('.')[:-1]:
            node = node.setdefault(p, {})
        node[path.split('.')[-1]] = list(got[fid])
        for term in got[fid]:
            put(path, None, fid, options[term], term)
    target = a['what-is-evaluated']
    if target in SUBJECTS:
        rec['designed_for_subjects'] = [SUBJECTS[target]]
        put('designed_for_subjects', None, 'what-is-evaluated', target, SUBJECTS[target])
    else:
        absent('designed_for_subjects', 'the answer to "What is evaluated" names no subject term')
    if target in TARGETS:
        put('evaluation_target', TARGETS[target], 'what-is-evaluated', target)
    else:
        absent('evaluation_target', 'the answer to "What is evaluated" is %s, which names no evaluation_target term'
               % target)
    for path in ('learned_entrant_evidence', 'task.output', 'task.scoring', 'data.access'):
        absent(path, NOT_ASKED[path])
    if 'size' in got:
        count, unit = got['size']
        q = quoted('size', a['size'])
        rec.setdefault('data', {})['size'] = [{'count': count, 'unit': unit, 'source': sid, 'quote': q}]
        rows.append({'field': 'data.size', 'confidence': 'low', 'source': sid, 'quote': q,
                     'note': 'the answer to "%s" on the form' % form.get('size').label})
    else:
        absent('data.size', blank)
    licence = a['licence']
    if licence and licence != 'other/unknown':
        put('data.dataset_licence', licence, 'licence', licence)
    else:
        absent('data.dataset_licence', 'other/unknown on the form' if licence else blank)
    if a['maintainer']:
        put('governance.maintainer', a['maintainer'], 'maintainer', a['maintainer'])
    else:
        absent('governance.maintainer', blank)
    for path, fid in (('homepage', 'homepage'), ('repository', 'repository'), ('leaderboard_url', 'leaderboard-url'),
                      ('dataset_url', 'dataset-url')):
        if a[fid]:
            put(path, a[fid], fid, a[fid])
        else:
            absent(path, blank)
    absent('execution.code_licence', NOT_ASKED['execution.code_licence'])
    checks = review_checks(form, a, got, sid, resolver, quoted)
    if unread:
        return [], unread
    order = list(DRAFT_FIELDS)
    rows.sort(key=lambda r: order.index(r['field']))       # stable: a facet's terms keep the form's order
    rec['curation'] = {
        'added_by': 'issue-intake bot, from issue #%d' % number, 'added_on': _day(today), 'last_verified': None,
        'verification_status': 'ai-drafted-unverified', 'sources': [sid], 'confidence': 'low',
        'review_checks': checks,
        'notes': ('Drafted by the issue-intake bot from the new-benchmark form of issue #%d (05 S6, Path A). Every '
                  'populated field is the contributor\'s answer, quoted in provenance.fields from the issue\'s '
                  'snapshot; none has been checked against the sources it links. Check each against those '
                  'sources, tick it into fields_verified, then promote.' % number),
    }
    rec['provenance'] = {
        'drafted_by': DRAFTED_BY, 'drafted_on': _day(today),
        'prompt_version': 'form-%s-%s' % (form.name, form.digest[:12]),
        'source_urls': [doc['url']], 'verified_by': None, 'verified_at': None, 'fields_verified': [],
        'fields': [{k: v for k, v in r.items() if v is not None} for r in rows],
    }
    src = {
        'id': sid, 'type': 'personal-communication', 'title': 'Issue #%d, a %s.yml issue-form submission'
                                                              % (number, form.name),
        'url': doc['url'], 'fetched_at': payload.fetched_at, 'archive_status': 'pending',
        'content_sha256': extract_sha256(extract), 'quote_extract': extract, 'licence_class': 'unlicensed',
        'licence_checked_on': _day(today), 'provenance': 'secondary',
        'notes': ('The issue-form submission the draft was made from, as its body read when the bot ran. Its '
                  'answers are what the contributor stated, not what the linked sources say. The issue page names '
                  'its author: on promotion, cite the benchmark\'s own sources in its place.'),
        'cited_by': [ident], 'content_bytes': len(payload.body), 'quote_extract_mode': 'full',
        'quote_extract_basis': 'normalised-text', 'licence_basis': 'a GitHub issue body, which states no licence',
        'drafted_by': DRAFTED_BY,
    }
    labels = list(PR_LABELS)
    # entity_id stays None: the runner mints ids, adapters never do (07 S1.1); the id in the payload is a proposal
    return [Draft('benchmark', None, Path('drafts/benchmarks/%s.yaml' % ident), rec, 'new', None, 0.5, labels),
            Draft('source', None, Path('drafts/sources/%s.yaml' % sid), src, 'new', None, 0.5, labels)], []


def review_checks(form: Form, a: dict, got: dict, sid: str, resolver: Resolver, quoted) -> list[dict]:
    """The questions the bot leaves for the curator (ADR-0026's review_checks)."""
    ident = got['id']
    out = [{'check': 'The id `%s` is the bot\'s proposal, made from the name. Id allocation is a human act and an id '
                     'is permanent (04 S3): confirm it or choose another before promotion.' % ident, 'field': 'id'}]
    if got['lost']:
        out[0]['check'] += ' The name has letters the id could not spell: %s.' % ' '.join(got['lost'])
    if ident in resolver.stubs:
        out.append({'check': 'data/benchmarks/_stubs/%s.yaml already holds a stub with this id: promote the stub '
                             'with the fields this draft checks out on, rather than adding a second entry.' % ident,
                    'field': 'id'})
    if a['what-is-evaluated'] not in TARGETS:
        out.append({'check': 'The form says "other" for what is evaluated, so evaluation_target is null. Check from '
                             'the sources whether a learned system is evaluated (00 S6 A5); a benchmark with none is '
                             'out of scope.', 'field': 'evaluation_target'})
    if a['licence'] and a['licence'] != 'other/unknown':
        out.append({'check': 'The form asks for one licence, the dataset\'s or the code\'s, and the bot recorded it '
                             'as data.dataset_licence. Check which it is; move it to execution.code_licence if it is '
                             'the code\'s.', 'field': 'data.dataset_licence'})
    if a['lineage']:
        out.append({'check': 'The contributor says this is a version or fork of an existing benchmark (quoted). '
                             'Decide its lineage before promotion: a version or subset of an entry the index holds '
                             'is not a new benchmark (04 S4).', 'field': 'lineage', 'source': sid,
                    'quote': quoted('lineage', a['lineage'])})
    if a['notes']:
        out.append({'check': 'The contributor left notes under "Anything we should know" (quoted): contamination, '
                             'saturation or known problems. Record what the sources support.', 'source': sid,
                    'quote': quoted('notes', a['notes'])})
    return out


# ---- render, write, validate (the impure half) -----------------------------------------------------------------

HEADER = {
    'benchmark': ('# drafts/benchmarks/%(id)s.yaml\n'
                  '# Drafted by the issue-intake bot from issue #%(n)d on %(day)s (05 S6, Path A).\n'
                  '#\n'
                  '# ai-drafted-unverified: never built, never published, never citable (05 S4; 11 S G4).\n'
                  '# Every populated field is the contributor\'s answer on the new-benchmark form, quoted in\n'
                  '# provenance.fields from the issue\'s snapshot in drafts/sources/. Nobody has checked them\n'
                  '# against the sources they link: do that before promoting the entry.\n'),
    'source': ('# drafts/sources/%(sid)s.yaml\n'
               '# The issue-form submission a draft\'s quotes are checked against (04 S9), read by the\n'
               '# issue-intake bot from issue #%(n)d on %(day)s. Not archived.\n'),
}


def render(draft: Draft, number: int, sid: str, ident: str, day: date) -> str:
    from tools import fmt
    rel = draft.path.as_posix()
    head = HEADER[draft.entity_type] % {'id': ident, 'sid': sid, 'n': number, 'day': day.isoformat()}
    return fmt.format_text(head + fmt.dumps(draft.payload), fmt.model_for(rel), rel)


def _finding_field(message: str) -> str | None:
    """The form field a validator finding is about: the dotted path its message starts with, list indices and
    `[]` dropped, matched against FROM_FORM by its longest prefix."""
    head = message.split(':', 1)[0].strip()
    parts = [p for p in re.sub(r'\[\]', '', head).split('.') if p and not p.isdigit()]
    for n in range(len(parts), 0, -1):
        if '.'.join(parts[:n]) in FROM_FORM:
            return FROM_FORM['.'.join(parts[:n])]
    return None


def validate(paths: list[str], form: Form, key: str, root: str = ROOT) -> list[Unresolved]:
    """`bench validate --single --tier schema,ref,semantic` on each written file, and the quote-substring check of
    the draft against its snapshot. A finding on a form field is that field's error; any other is the bot's."""
    from schema.taxonomy import read_yaml
    from tools.validate import quotes, tiers
    out, internal = [], []
    for p in paths:
        for finding in tiers.single(p, list(TIERS), root).blocking:
            fid = _finding_field(finding.message)
            if fid is None or finding.rule in ('file-name', 'yaml', 'unknown-path'):
                internal.append(str(finding))
                continue
            f = form.get(fid)
            out.append(_err(key, f, '', 'unparseable', '%s: the catalogue\'s schema does not accept this answer. %s'
                            % (f.label, f.hint)))
    records = [read_yaml(p) for p in paths]
    sources = {r['id']: r for r in records if str(r.get('id') or '').startswith('src-')}
    for r in records:
        if isinstance(r.get('provenance'), dict):            # get-default: the draft has the block, the source not
            internal += ['%s: %s' % (quotes.dotted(q.at + (q.key,)), why) for q, why in quotes.check(r, sources)]
    if internal:
        raise IntakeError('the draft the bot built does not validate: %s' % '; '.join(internal))
    return out


@dataclass
class Outcome:
    form: str | None
    issue: int
    status: str                             # drafted | invalid | human | skipped | error
    errors: list[dict] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    entity_id: str | None = None
    title: str | None = None
    source_id: str | None = None
    steward_path: str | None = None


def _error_dict(u: Unresolved, form: Form) -> dict:
    return {'field': u.field, 'label': form.get(u.field).label, 'observed': u.observed, 'reason': u.reason,
            'message': u.human_task, 'suggestions': [list(s) for s in u.suggestions], 'fingerprint': u.fingerprint}


def _steward_path(form_name: str, payload: Payload | None, resolver: Resolver) -> str:
    if form_name != 'new-benchmark':
        return STEWARD_PATHS[form_name]
    option = (payload.doc['answers'].get('primary-domain') if payload else None) or ''   # get-default: other forms
    family = _term(option).split('/')[0]
    return 'data/benchmarks/%s/' % family if family in resolver.vocab['families'] else 'data/benchmarks/'


def intake(issue: dict, root: str = ROOT, out: str | None = None, repo: str = DEFAULT_REPO,
           resolver: Resolver | None = None) -> Outcome:
    """One issue through the bot's first step. `out` is where the draft files are written to be validated (a
    fresh temporary directory by default); nothing raises: a failure of the bot's own is status `error`."""
    number = int(issue.get('number') or 0)
    labels = [lb['name'] if isinstance(lb, dict) else str(lb) for lb in issue.get('labels') or []]
    name = form_for(labels, root)
    if name is None:
        return Outcome(None, number, 'skipped')
    try:
        resolver = resolver or load_resolver(root, repo)
        form = resolver.forms[name]
        payload = payload_from(issue, form, repo)
        steward = _steward_path(name, payload, resolver)
        drafts, errors = normalise(payload, resolver)
        if errors:
            return Outcome(name, number, 'invalid', [_error_dict(u, form) for u in errors], steward_path=steward)
        if not drafts:
            return Outcome(name, number, 'human', steward_path=steward)
        from ingest import gates
        bench, source = drafts
        gates.derived_field_guard(bench.payload)            # ADR-0022: the gate applies unchanged
        day = payload.fetched_at.date()
        files = {d.path.as_posix(): render(d, number, source.payload['id'], bench.payload['id'], day)
                 for d in drafts}
        out = out or tempfile.mkdtemp(prefix='intake-')
        written = []
        for rel, text in files.items():
            full = os.path.join(out, *rel.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            written.append(full)
        errors = validate(written, form, payload.candidate.source_key, root)
        if errors:
            return Outcome(name, number, 'invalid', [_error_dict(u, form) for u in errors], steward_path=steward)
        return Outcome(name, number, 'drafted', files=files, entity_id=bench.payload['id'],
                       title='New benchmark: %s' % ' '.join(bench.payload['name'].split()),
                       source_id=source.payload['id'], steward_path=steward)
    except Exception:                                       # the bot's failure: the log has it, the issue never does
        traceback.print_exc(file=sys.stderr)
        return Outcome(name, number, 'error', steward_path=STEWARD_PATHS.get(name) or 'data/')


# ---- the command line --------------------------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--event', help='the issues event JSON ($GITHUB_EVENT_PATH)')
    p.add_argument('--form', choices=KNOWN_FORMS, help='with --body: the form the body was submitted on')
    p.add_argument('--body', help='with --form: a file holding an issue body')
    p.add_argument('--issue', type=int, default=0, help='with --body: the issue number')
    p.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY') or DEFAULT_REPO)
    p.add_argument('--out', help='where to write the draft files (default: a temporary directory)')
    p.add_argument('--result', help='write the outcome as JSON here, for open_pr.py')
    a = p.parse_args(argv)
    if a.event:
        with open(a.event, encoding='utf-8') as fh:
            event = json.load(fh)
        issue = event.get('issue') or {}
        repo = (event.get('repository') or {}).get('full_name') or a.repo    # get-default: a hand-made event
    elif a.form and a.body:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        with open(a.body, encoding='utf-8') as fh:
            issue = {'number': a.issue, 'body': fh.read(), 'labels': ['form:' + a.form], 'created_at': now,
                     'updated_at': now}
        repo = a.repo
    else:
        p.error('give --event, or --form with --body')
    outcome = intake(issue, ROOT, a.out, repo)
    if a.result:
        with open(a.result, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(asdict(outcome), fh, indent=1, ensure_ascii=False)
            fh.write('\n')
    print('intake: issue #%d, form %s: %s' % (outcome.issue, outcome.form, outcome.status))
    for e in outcome.errors:
        print('  %s: %s' % (e['field'], e['message']))
    for rel in outcome.files:
        print('  wrote %s' % rel)
    return 0


if __name__ == '__main__':
    sys.exit(main())
