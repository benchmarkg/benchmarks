#!/usr/bin/env python3
"""Emit System and Organization stubs from Epoch's model registry (P3-S3-T04; 04 S7, 07 S5, 01 S10).

    python scripts/emit_epoch_entities.py                  # write the stubs and the unresolved batch
    python scripts/emit_epoch_entities.py --check          # exit 1 if any output differs from a fresh emission
    python scripts/emit_epoch_entities.py --epoch DIR      # read an export other than epochdl/

epochdl/ is gitignored (00 S8.1); `python scripts/epoch_audit.py --fetch` restores it from the pinned
capture. Without it this exits 2, as the other Epoch scripts do.

What is read, and from where. Entities come from model_metadata.csv, the registry, and from nowhere
else: no entity is created from a result row (the task's done-when). The per-benchmark CSVs are read
for one column only, `Training compute notes`, because that is where Epoch writes whether a figure was
imputed; the notes are joined back to the registry by `Model version`, which joins at 100%
(reports/epoch-identity-census.md).

The rules, each stated so a reviewer can check a file against it:

  1. One System stub per model_group, as 04 S7's `external_ids: {epoch_model_group: ...}` reads it.
     Groups that differ only in letter case ("Sonar" / "sonar") are one stub, with the other spelling
     an alias and a note for the identity review. A group already curated under data/systems/ gets no
     stub (claude-3-5-sonnet).
  2. The id is the group name, lowercased, with every run of other characters one hyphen
     ("Claude 3.5 Sonnet (October 2024)" -> claude-3-5-sonnet-october-2024). It is a PROPOSAL: the
     file's `identity.reviewed_by` is null until a person confirms the strings in it are one system.
     Where the name without its parenthetical is shared with another group or is a curated system's
     id ("Gemini 1.5 Pro (Feb 2024)" / "(May 2024)" / "(Sept 2024)"), the note names them, because
     those are the likeliest versions of one system.
  3. A registry row is kept verbatim as an Epoch version row. Stripping provider prefixes and effort
     suffixes to make SystemVersions is the resolver's (04 S10 step 4; P3-S3-T02/T05), not this one's.
  4. Training compute, per group (Epoch's figure never disagrees within a group): the registry's
     training_compute_flop, `training_compute_from: model_metadata`. The notes, verbatim, where a result
     row carries them. Notes that say the figure was imputed -- "imputed ... from benchmark scores" or
     "using benchmark imputation", matched as `imput` -- make `training_compute_estimated: true`; for the
     five groups whose imputed figure is in the notes and not in the registry, the figure is read from
     the notes ("imputed to be 1.58e25 FLOP", "estimated to be 2.2e25 FLOP using benchmark
     imputation"), `training_compute_from: notes`. Otherwise estimated is null:
     whether Epoch's other figures were disclosed or estimated is for the curator, with the notes.
  5. Organizations: every `organization` value split on commas (74 names from 70 strings), one stub
     each, id org-<name without parentheticals>. A name already curated under data/organizations/
     gets no stub (org-anthropic).
  6. A registry row this cannot identify -- a blank row, or a row with no model_version -- becomes an
     Unresolved record in data/_ingest/unresolved/epoch/<date>.yaml, never an entity.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import os
import re
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ruamel.yaml import YAML  # noqa: E402

from schema.entities import UnresolvedFile  # noqa: E402
from schema.stub import OrganizationStub, SystemStub  # noqa: E402
from tools import fmt  # noqa: E402

EPOCH = os.path.join(ROOT, 'epochdl')
SOURCE = 'src-epoch-benchmark-data'
ADDED_BY = 'agent (P3-S3-T04)'
ADDED_ON = '2026-09-28'
UNRESOLVED = os.path.join('data', '_ingest', 'unresolved', 'epoch', ADDED_ON + '.yaml')
IMPUTED = re.compile(r'imput', re.I)        # "imputed ... from benchmark scores", "using benchmark imputation"
IMPUTED_FIGURE = re.compile(r'(?:imputed|estimated) to be\s+([0-9.]+e\+?[0-9]+)\s*FLOP', re.I)


def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def org_id(name: str) -> str:
    return 'org-' + slug(re.sub(r'\s*\([^)]*\)', '', name))


def _read(path: str) -> list[dict]:
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        return list(csv.DictReader(fh))


def _curated(root: str, kind: str) -> set[str]:
    return {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(root, 'data', kind, '*.yaml'))}


def compute_notes(epoch: str, registry: dict[str, dict]) -> dict[str, str]:
    """model_group -> the verbatim `Training compute notes` its result rows carry."""
    out: dict[str, set[str]] = {}
    for path in sorted(glob.glob(os.path.join(epoch, '*.csv'))):
        if os.path.basename(path) in ('benchmark_metadata.csv', 'model_metadata.csv'):
            continue
        rows = _read(path)
        if not rows or 'Training compute notes' not in rows[0]:
            continue
        mv = next(c for c in rows[0] if c.strip().lower() == 'model version')
        for r in rows:
            note = (r['Training compute notes'] or '').strip()
            if note and r[mv] in registry:
                out.setdefault(registry[r[mv]]['model_group'], set()).add(note)
    many = {g: n for g, n in out.items() if len(n) > 1}
    if many:
        raise SystemExit('groups whose result rows disagree on the compute notes: %s' % sorted(many))
    return {g: n.pop() for g, n in out.items()}


def _unresolved(key: str, field: str, observed: str, task: str) -> dict:
    return {'source_key': key, 'field': field, 'observed': observed, 'reason': 'unparseable', 'suggestions': [],
            'human_task': task,
            'fingerprint': hashlib.sha256(('%s|%s|%s' % (key, field, observed)).encode('utf-8')).hexdigest()[:16]}


def _one(values: list[str]) -> str | None:
    vals = sorted({v for v in values if v})
    if len(vals) > 1:
        raise SystemExit('a group carries two values where Epoch gives one: %s' % vals)
    return vals[0] if vals else None


def _float(text: str):
    return fmt.emitter().load('v: %s\n' % text)['v']


def emit(epoch: str = EPOCH, root: str = ROOT) -> dict[str, str]:
    """{path relative to root: file text} for every stub and the unresolved batch."""
    rows = _read(os.path.join(epoch, 'model_metadata.csv'))
    unresolved, registry, groups = [], {}, OrderedDict()
    for n, r in enumerate(rows, start=2):                     # line 1 is the header
        key = 'model_metadata.csv#row-%d' % n
        if not any((v or '').strip() for v in r.values()):
            unresolved.append(_unresolved(key, 'model_version', '', 'Line %d of model_metadata.csv is blank. '
                              'Confirm upstream nothing is missing, then mark it wontfix.' % n))
            continue
        if not r['model_version']:
            unresolved.append(_unresolved(key, 'model_version', r['model_group'], 'Line %d names model_group %r '
                              'but no model_version, so no result row can reference it. Confirm the group\'s '
                              'other rows cover it, then mark it wontfix.' % (n, r['model_group'])))
            continue
        registry[r['model_version']] = r
        groups.setdefault(r['model_group'].casefold(), []).append(r)
    notes = compute_notes(epoch, registry)
    curated_sys, curated_org = _curated(root, 'systems'), _curated(root, 'organizations')

    out: dict[str, str] = {}
    ids = {slug(rs[0]['model_group']) for rs in groups.values()}
    bases: dict[str, list[str]] = {}                       # name without its parenthetical -> the stub ids
    for rs in groups.values():
        group = rs[0]['model_group']
        bases.setdefault(slug(re.sub(r'\s*\([^)]*\)', '', group)), []).append(slug(group))
    for rs in groups.values():
        spellings = list(OrderedDict.fromkeys(r['model_group'] for r in rs))
        name, sid = spellings[0], slug(spellings[0])
        if sid in curated_sys:
            continue
        orgs = _one([r['organization'] for r in rs])
        flop = _one([r['training_compute_flop'] for r in rs])
        note = _one([notes.get(s) for s in spellings])
        review = []
        if len(spellings) > 1:
            review.append('Epoch writes this group %s, differing only in case; confirm they are one system.'
                          % ' and '.join(repr(s) for s in spellings))
        base = slug(re.sub(r'\s*\([^)]*\)', '', name))
        siblings = sorted(set(bases[base]) - {sid}) + ([base] if base in curated_sys and base != sid else [])
        if siblings:
            review.append('Epoch groups %s under the same name before its parenthetical (%s); confirm these are '
                          'different systems, not versions of one.' % (', '.join(siblings), base))
        stub = {'id': sid, 'name': name, 'aliases': spellings[1:],
                'organizations': [org_id(o.strip()) for o in orgs.split(',')] if orgs else []}
        stub.update({'system_type': None, 'availability': None})
        if flop:
            stub.update({'training_compute_flop': _float(flop),
                         'training_compute_estimated': True if note and IMPUTED.search(note) else None,
                         'training_compute_notes': note, 'training_compute_from': 'model_metadata'})
        elif note and IMPUTED.search(note) and IMPUTED_FIGURE.search(note):
            stub.update({'training_compute_flop': _float(IMPUTED_FIGURE.search(note).group(1)),
                         'training_compute_estimated': True, 'training_compute_notes': note,
                         'training_compute_from': 'notes'})
        else:
            stub.update({'training_compute_flop': None, 'training_compute_estimated': None,
                         'training_compute_notes': note, 'training_compute_from': None})
        stub['external_ids'] = {'epoch_model_group': name}
        stub['epoch'] = {
            'model_groups': spellings, 'organization': orgs, 'country': _one([r['country'] for r in rs]),
            'accessibility': _one([r['accessibility'] for r in rs]),
            'versions': [{'model_version': r['model_version'], 'display_name': r['display_name'] or None,
                          'released': r['date'] or None} for r in rs]}
        stub['curation'] = {'added_by': ADDED_BY, 'added_on': ADDED_ON, 'verification_status': 'unreviewed',
                            'sources': [SOURCE],
                            'notes': ('The compute figure is read from the notes; the registry carries none.'
                                      if stub['training_compute_from'] == 'notes' else None)}
        stub['identity'] = {'proposed_by': ADDED_BY, 'reviewed_by': None, 'reviewed_on': None,
                            'note': ' '.join(review) or None}
        out[os.path.join('data', 'systems', '_stubs', sid + '.yaml')] = _file(stub, SystemStub, 'system', sid)

    written_as: dict[str, list[str]] = OrderedDict()
    for r in registry.values():
        for o in (r['organization'] or '').split(','):
            if o.strip():
                written_as.setdefault(o.strip(), [])
                if r['organization'] not in written_as[o.strip()]:
                    written_as[o.strip()].append(r['organization'])
    names = sorted(written_as)
    for name in names:
        oid = org_id(name)
        if oid in curated_org:
            continue
        near = [n for n in names if n != name and (n in name or name in n)]
        stub = {'id': oid, 'name': name, 'kind': None, 'country': None, 'homepage': None,
                'epoch': {'written_as': sorted(written_as[name])},
                'curation': {'added_by': ADDED_BY, 'added_on': ADDED_ON, 'verification_status': 'unreviewed',
                             'sources': [SOURCE], 'notes': None},
                'identity': {'proposed_by': ADDED_BY, 'reviewed_by': None, 'reviewed_on': None,
                             'note': ('Epoch also names %s; confirm whether these are one organisation, a '
                                      'parent and a part, or unrelated.' % ', '.join(repr(n) for n in near))
                             if near else None}}
        out[os.path.join('data', 'organizations', '_stubs', oid + '.yaml')] = _file(stub, OrganizationStub,
                                                                                   'organization', oid)
    UnresolvedFile.model_validate(unresolved)
    out[UNRESOLVED] = fmt.format_text(
        ('# data/_ingest/unresolved/epoch/%s.yaml -- GENERATED by scripts/emit_epoch_entities.py\n'
         '# (P3-S3-T04). Registry rows the generator could not identify; none became an entity.\n'
         % ADDED_ON) + fmt.dumps(unresolved), UnresolvedFile)
    return out


def _file(stub: dict, model, kind: str, ident: str) -> str:
    model.model_validate(YAML(typ='safe', pure=True).load(fmt.dumps(stub)))
    text = ('# data/%ss/_stubs/%s.yaml -- GENERATED by scripts/emit_epoch_entities.py from Epoch\'s\n'
            '# model_metadata.csv (src-epoch-benchmark-data; P3-S3-T04). An unreviewed stub: never published.\n'
            '# Promote it to data/%ss/%s.yaml once a curator has checked its identity and filled what\n'
            '# Epoch does not state.\n' % (kind, ident, kind, ident)) + fmt.dumps(stub)
    return fmt.format_text(text, model)                     # bench fmt's canonical form, so --check agrees


def main(argv: list[str]) -> int:
    epoch = argv[argv.index('--epoch') + 1] if '--epoch' in argv else EPOCH
    if not os.path.exists(os.path.join(epoch, 'model_metadata.csv')):
        print('no %s: restore it with `python scripts/epoch_audit.py --fetch`' % os.path.join(epoch,
              'model_metadata.csv'), file=sys.stderr)
        return 2
    files = emit(epoch)
    stale = [rel for rel, text in files.items() if not os.path.exists(os.path.join(ROOT, rel))
             or open(os.path.join(ROOT, rel), encoding='utf-8').read() != text]
    existing = {os.path.relpath(p, ROOT) for k in ('systems', 'organizations')
                for p in glob.glob(os.path.join(ROOT, 'data', k, '_stubs', '*.yaml'))}
    orphans = sorted(existing - set(files))
    if '--check' in argv:
        for rel in stale:
            print('stale   %s' % rel, file=sys.stderr)
        for rel in orphans:
            print('orphan  %s: the registry no longer produces it' % rel, file=sys.stderr)
        return 1 if stale or orphans else 0
    for rel in stale:
        os.makedirs(os.path.dirname(os.path.join(ROOT, rel)), exist_ok=True)
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(files[rel])
    for rel in orphans:
        print('orphan  %s: the registry no longer produces it; not deleted' % rel, file=sys.stderr)
    n_sys = sum(1 for p in files if '/systems/' in p.replace(os.sep, '/'))
    n_org = sum(1 for p in files if '/organizations/' in p.replace(os.sep, '/'))
    print('emit_epoch_entities: %d system stub(s), %d organization stub(s), 1 unresolved batch; %d written'
          % (n_sys, n_org, len(stale)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
