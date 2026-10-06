"""`bench promote <path...> --to <status> --evidence <src-id> --by <handle>` (P1-S2-T10; 05 S3, S4, S5).

Raises a record's `curation.verification_status` up 05 S4's six-value ladder, and records who did it, when and
against which evidence in data/_curation/promotions/ (schema/curation.py says why a file of its own). A promotion
is refused, and nothing is written, unless every precondition holds:

  - the record lives in data/ and has a curation block. A draft leaves drafts/ through a reviewed PR that moves
    it, not through this command;
  - `--to` is above the record's current status. Promote never lowers or repeats, never makes a record a draft,
    and never assigns machine-ingested, which only an ingestion adapter does (05 S4);
  - every `--evidence` id is a Source record in data/sources/ and one of the sources the record itself cites
    (curation.sources). The evidence for a promotion is what the record stands on, not a new claim;
  - from primary-source-verified up, the evidence covers EVERY source the record cites: 05 S4's
    primary-source-verified is "a human opened each cited source and confirmed each factual field against it";
  - `--by` is not the record's author (curation.added_by): 05 S5 needs "1, not the author";
  - expert-reviewed and maintainer-confirmed name their `--reviewer` (the domain expert, or the benchmark's
    maintainer), because that rung is somebody else's sign-off, and an unnamed one is not evidence;
  - the record, with the new status and today as curation.last_verified, still validates against its model.

The edit touches exactly those two lines of the curation block, then reloads the file and refuses if anything
else in it changed. The promotion file is created exclusively, never overwritten: the log is append-only.
"""
from __future__ import annotations

import datetime
import glob
import os
import re
from dataclasses import dataclass

from schema.curation import LADDER, NEEDS_REVIEWER, NOT_A_TARGET, Promotion

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMOTIONS = 'data/_curation/promotions'
FLOOR_ALL_SOURCES = 'primary-source-verified'


class PromotionError(Exception):
    """A precondition does not hold; nothing was written."""


@dataclass
class Plan:
    path: str            # the record, relative to the root
    text: str            # its new text
    record: dict         # the promotion record; its file name is taken when it is written


def _read(path: str):
    from schema.taxonomy import read_yaml
    return read_yaml(path)


def _rel(path: str, root: str) -> str:
    """`path` relative to the tree: a relative path already is; an absolute one must be inside it."""
    if not os.path.isabs(path):
        return os.path.normpath(path).replace(os.sep, '/')
    try:
        rel = os.path.relpath(path, root)
    except ValueError:              # another drive
        rel = '..'
    if rel.startswith('..'):
        raise PromotionError('%s is not inside %s' % (path, root))
    return rel.replace(os.sep, '/')


def source_ids(root: str = ROOT) -> set[str]:
    return {os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(root, 'data', 'sources', '**', 'src-*.yaml'), recursive=True)}


def cited(curation: dict) -> list[str]:
    return [s if isinstance(s, str) else s['id'] for s in curation['sources']]


def _set_curation_field(text: str, key: str, value: str) -> str:
    """`key: value` inside the top-level `curation:` block, the line edited in place (or appended to the block)."""
    m = re.search(r'^curation:[ \t]*\n((?:[ \t]+.*\n|[ \t]*\n)*)', text, re.M)
    if not m:
        raise PromotionError('no top-level curation block to edit')
    block = m.group(1)
    line = re.compile(r'^(  %s:)[ \t]*[^\n]*$' % re.escape(key), re.M)
    if line.search(block):
        new = line.sub(lambda x: '%s %s' % (x.group(1), value), block, count=1)
    else:
        new = block.rstrip('\n') + '\n  %s: %s\n' % (key, value) + block[len(block.rstrip('\n')) + 1:]
    return text[:m.start(1)] + new + text[m.end(1):]


def plan(path: str, to: str, evidence: list[str], by: str, reviewer: str | None = None, note: str | None = None,
         root: str = ROOT, today: datetime.date | None = None) -> Plan:
    """Check every precondition and compute what promoting `path` would write. Raises PromotionError."""
    from tools.validate.tiers import kind_of
    today = today or datetime.date.today()
    rel = _rel(path, root)
    if rel.startswith('drafts/'):
        raise PromotionError('%s is a draft: it leaves drafts/ in a reviewed PR that moves it into data/, '
                             'not through bench promote' % rel)
    if not rel.startswith('data/') or rel.startswith('data/_'):
        raise PromotionError('%s is not a record under data/' % rel)
    full = os.path.join(root, rel)
    if not os.path.isfile(full):
        raise PromotionError('%s does not exist' % rel)
    raw = _read(full)
    if not isinstance(raw, dict) or not isinstance(raw.get('curation'), dict) \
            or 'verification_status' not in raw['curation']:
        raise PromotionError('%s has no curation.verification_status to promote' % rel)
    cur = raw['curation']
    now = cur['verification_status']
    if to not in LADDER:
        raise PromotionError('--to %s is not a rung of the ladder (%s)' % (to, ', '.join(LADDER)))
    if to in NOT_A_TARGET:
        raise PromotionError('--to %s: %s' % (to, NOT_A_TARGET[to]))
    if now not in LADDER or LADDER.index(to) <= LADDER.index(now):
        raise PromotionError('%s is %s; promote only raises it (%s)' % (rel, now, ' < '.join(LADDER)))
    if not evidence:
        raise PromotionError('a promotion cites its evidence: --evidence <src-id>')
    known, cites = source_ids(root), cited(cur)
    for sid in evidence:
        if sid not in known:
            raise PromotionError('--evidence %s is not a Source record in data/sources/' % sid)
        if sid not in cites:
            raise PromotionError('--evidence %s is not one of the sources %s cites (%s)' % (sid, rel, ', '.join(cites)))
    if LADDER.index(to) >= LADDER.index(FLOOR_ALL_SOURCES):
        unopened = [s for s in cites if s not in evidence]
        if unopened:
            raise PromotionError('%s means every cited source was opened and checked (05 S4); the evidence does '
                                 'not cover %s' % (to, ', '.join(unopened)))
    if not by or not by.strip():
        raise PromotionError('a promotion names who made it: --by <handle>')
    if by.strip().lower() == str(cur['added_by']).strip().lower():
        raise PromotionError('%s added %s; a promotion needs a reviewer who is not the author (05 S5)' % (by, rel))
    if to in NEEDS_REVIEWER and not (reviewer and reviewer.strip()):
        raise PromotionError('%s is a sign-off by someone outside the core team: name them with --reviewer' % to)

    text = open(full, encoding='utf-8').read()
    new = _set_curation_field(text, 'verification_status', to)
    new = _set_curation_field(new, 'last_verified', today.isoformat())
    _check_only_curation_changed(raw, new, to, today)
    kind = kind_of(rel)
    if kind is None:
        raise PromotionError('%s is in no directory the validator models' % rel)
    from pydantic import ValidationError
    try:
        kind.model.model_validate(_read_text(new))
    except ValidationError as e:
        raise PromotionError('%s would not validate as %s after the promotion: %s'
                             % (rel, kind.name, ' '.join(str(e).split())[:300])) from None
    entity_id = raw.get('id') or os.path.splitext(os.path.basename(rel))[0]
    record = {'entity': rel, 'entity_id': entity_id, 'from': now, 'to': to, 'by': by.strip(), 'on': today.isoformat(),
              'evidence': list(evidence), 'reviewer': reviewer.strip() if reviewer else None, 'note': note}
    Promotion.model_validate(record)
    return Plan(rel, new, record)


def _read_text(text: str):
    from ruamel.yaml import YAML
    return YAML(typ='safe', pure=True).load(text)


def _check_only_curation_changed(before: dict, text: str, to: str, today: datetime.date) -> None:
    after = _read_text(text)
    expect = dict(before)
    expect['curation'] = dict(before['curation'], verification_status=to, last_verified=today)
    if after != expect:
        raise PromotionError('the edit would change more than curation.verification_status and last_verified; '
                             'nothing written')


def _next_record_path(root: str, today: datetime.date, entity_id: str) -> str:
    stem = '%s-%s-' % (today.isoformat(), entity_id)
    taken = glob.glob(os.path.join(root, PROMOTIONS, stem + '[0-9][0-9][0-9].yaml'))
    n = 1 + max((int(os.path.basename(p)[len(stem):len(stem) + 3]) for p in taken), default=0)
    return '%s/%s%03d.yaml' % (PROMOTIONS, stem, n)


def apply(p: Plan, root: str = ROOT) -> list[str]:
    """Write the promotion record (exclusively: an existing file is never overwritten), then the record."""
    from tools.fmt import dumps
    rel = _next_record_path(root, datetime.date.fromisoformat(p.record['on']), p.record['entity_id'])
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    header = '# %s -- written by bench promote (05 S3); a promotion record is never edited\n' % rel
    with open(full, 'x', encoding='utf-8', newline='\n') as fh:
        fh.write(header + dumps(p.record))
    with open(os.path.join(root, p.path), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(p.text)
    return [rel, p.path]


def promote(paths: list[str], to: str, evidence: list[str], by: str, reviewer: str | None = None,
            note: str | None = None, root: str = ROOT, today: datetime.date | None = None) -> list[str]:
    """Plan every path first, so one refusal writes nothing at all; then apply them."""
    plans = [plan(p, to, evidence, by, reviewer, note, root, today) for p in paths]
    written = []
    for p in plans:
        written += apply(p, root)
    return written
