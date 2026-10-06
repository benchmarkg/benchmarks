#!/usr/bin/env python3
"""A Source record for every distinct `Source link` in Epoch's export (P3-S4-T05; 06 S3.18, S7; 14 Phase 3).

    python scripts/scaffold_epoch_sources.py            # write the Source records not yet held
    python scripts/scaffold_epoch_sources.py --dry-run  # list them; write nothing
    python scripts/scaffold_epoch_sources.py --epoch DIR

Then the archiving is ingest/archive_sources.py's, which already implements 06 S3.18 and S7.1 (CDX
first, never the Availability API; SPN2 with if_not_archived_within=30d; a refusal recorded as
`failed` with its reason, never retried silently):

    python -m ingest.archive_sources                    # IA_SPN_KEY / IA_SPN_SECRET set: captures
                                                        # unset: CDX-only, records captures < 30 days

This script makes no network request and never rewrites a file that exists, so the archiver's writes
survive a re-run. It reads epochdl/ (gitignored; `python scripts/epoch_audit.py --fetch` restores it).

The population. Every non-empty value of a column whose name starts `Source link` (case-insensitive:
`Source link`, `Source link (site from table)`, `Source Link`) in the 80 per-benchmark CSVs, trimmed and
otherwise verbatim: 101 distinct URLs in the 2026-09-17 export. 14 Phase 3's "74 distinct targets"
was counted in the reconnaissance by a rule it does not state; no rule tried here reproduces it (the
`Source link` column alone gives 85, in the 59 metadata-covered files 76), so the count is re-derived
here and the rule is this paragraph. A URL an existing data/sources/ record already holds is skipped.

Each record, and why each field says what it says:
  id            src-<host without www>-<path>, lowercased, every run of other characters one hyphen,
                cut to 60 characters with an 8-hex sha256 of the URL when longer; an arXiv link is
                src-arxiv-<id>. Spellings that reach the same id (http and https, with and without www
                or a trailing slash; an arXiv abs, pdf or vN link) are one Source, under the https spelling
                -- for arXiv, https://arxiv.org/abs/<id> -- with Epoch's other spellings in its notes
  type          by URL: arxiv -> preprint; github.com -> repository; huggingface.co/datasets ->
                dataset-card; a path or host naming a leaderboard -> leaderboard-page; .pdf -> paper;
                else documentation. A curator corrects it when they read the page
  doi           arXiv links only: 10.48550/arXiv.<id>, which makes them DOI Sources, exempt from
                archiving (04 S12) and `archive_status: not-required`
  archive_*     pending and null: filled by the archiver, never here
  licence       unlicensed, the restrictive default, with licence_basis saying no page was read: this
                pass fetches nothing, so it cannot have found a licence statement
  cited_by      the benchmark ids whose Epoch files cite the link, through the P3-S2-T07 allocation;
                a link cited only from a file outside benchmark_metadata.csv has none
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ruamel.yaml import YAML  # noqa: E402

from schema.source import Source  # noqa: E402
from tools import fmt  # noqa: E402

EPOCH = os.path.join(ROOT, 'epochdl')
OUT = os.path.join('data', 'sources', '2026')
DRAFTED_BY = 'agent (P3-S4-T05)'
ADDED_ON = '2026-09-29'
ARXIV = re.compile(r'^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?/?$', re.I)
BOARD = re.compile(r'leaderboard|arena|/rankings?\b|/board\b', re.I)


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return YAML(typ='safe', pure=True).load(fh)


def links(epoch: str = EPOCH) -> dict[str, dict]:
    """url -> {'files': [...], 'rows': n}: every distinct `Source link*` value in the per-benchmark CSVs."""
    out: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(epoch, '*.csv'))):
        name = os.path.basename(path)
        if name in ('benchmark_metadata.csv', 'model_metadata.csv'):
            continue
        with open(path, encoding='utf-8', errors='replace', newline='') as fh:
            for row in csv.DictReader(fh):
                for col, val in row.items():
                    if col and col.lower().startswith('source link') and (val or '').strip():
                        e = out.setdefault(val.strip(), {'files': [], 'rows': 0})
                        e['rows'] += 1
                        if name not in e['files']:
                            e['files'].append(name)
    return dict(sorted(out.items()))


def source_id(url: str) -> str:
    m = ARXIV.match(url)
    if m:
        return 'src-arxiv-' + m.group(1).replace('.', '-')
    body = re.sub(r'^https?://(www\.)?', '', url, flags=re.I)
    s = re.sub(r'[^a-z0-9]+', '-', body.lower()).strip('-')
    if len(s) > 60:
        s = s[:51].rstrip('-') + '-' + hashlib.sha256(url.encode('utf-8')).hexdigest()[:8]
    return 'src-' + s


def source_type(url: str) -> str:
    if ARXIV.match(url):
        return 'preprint'
    if re.match(r'^https?://(www\.)?github\.com/', url, re.I):
        return 'repository'
    if re.match(r'^https?://huggingface\.co/datasets/', url, re.I):
        return 'dataset-card'
    if BOARD.search(url):
        return 'leaderboard-page'
    if url.lower().split('?')[0].endswith('.pdf'):
        return 'paper'
    return 'documentation'


def cited_by(root: str, epoch: str) -> dict[str, list[str]]:
    """Epoch CSV file name -> the benchmark ids its rows belong to (through the id allocation)."""
    meta = _load(os.path.join(root, 'data', 'sources', '2026', 'src-epoch-benchmark-data.yaml'))['quote_extract']
    alloc = _load(os.path.join(root, 'ingest', 'mappings', 'epoch', '_id_allocation.yaml'))['allocations']
    ids = {a['epoch']: a['benchmark'] for a in alloc}
    out: dict[str, list[str]] = {}
    for r in csv.DictReader(io.StringIO(meta)):
        if r['source_file']:
            out.setdefault(r['source_file'], [])
            if ids[r['benchmark']] not in out[r['source_file']]:
                out[r['source_file']].append(ids[r['benchmark']])
    return out


def held(root: str, field: str = 'url') -> dict[str, str]:
    """id -> url (or another URL field) of every data/sources/ record."""
    out = {}
    for path in glob.glob(os.path.join(root, 'data', 'sources', '**', '*.yaml'), recursive=True):
        rec = _load(path)
        if isinstance(rec, dict) and isinstance(rec.get('id'), str):   # get-default: tier 1 reports a bad one
            out[rec['id']] = rec.get(field)                            # get-default: the same
    return out


def record(spellings: list[str], e: dict, citers: dict[str, list[str]]) -> dict:
    url = sorted(spellings, key=lambda u: (not u.startswith('https://'), u))[0]
    m = ARXIV.match(url)
    if m:                                        # an arXiv paper is cited by its abstract page, whatever Epoch wrote
        url = 'https://arxiv.org/abs/%s' % m.group(1)
    benches = sorted({b for f in e['files'] for b in citers.get(f, [])})  # get-default: an orphan file has none
    files = ', '.join(e['files'])
    also = [u for u in spellings if u != url]     # Epoch's other spellings, kept in the notes
    return {
        'id': source_id(url), 'type': source_type(url), 'title': None, 'url': url,
        'doi': '10.48550/arXiv.%s' % m.group(1) if m else None,
        'authors': None, 'publisher': None, 'published': None, 'accessed': None, 'fetched_at': None,
        'archive_url': None, 'archive_captured': None,
        'archive_status': 'not-required' if m else 'pending', 'archive_digest': None,
        'content_sha256': None, 'quote_extract': None,
        'licence_class': 'unlicensed', 'licence_spdx': None, 'licence_checked_on': ADDED_ON,
        'provenance': 'primary',
        'notes': ('Cited as `Source link` by %d row%s of Epoch\'s export (src-epoch-benchmark-data), in %s. '
                  '%sScaffolded from the link alone: title, publisher, type and provenance are unchecked.'
                  % (e['rows'], '' if e['rows'] == 1 else 's', files,
                     'Epoch also writes it %s. ' % ', '.join(also) if also else '')),
        'archive_requested_at': None, 'failure_reason': None,
        'cited_by': benches,
        'licence_basis': 'not checked: scaffolded from Epoch\'s export without fetching the page (P3-S4-T05); '
                         'unlicensed is the restrictive default until a curator reads it',
        'drafted_by': DRAFTED_BY,
    }


def plan(epoch: str = EPOCH, root: str = ROOT) -> dict[str, str]:
    """{path relative to root: file text} for every link no data/sources/ record holds."""
    ids = held(root)
    urls = set(ids.values()) | {u for u in held(root, 'repointed_from').values() if u}   # a re-pointed link is held
    citers = cited_by(root, epoch)
    groups: dict[str, dict] = {}                 # one Source per id: spellings differing in scheme, www or
    for url, e in links(epoch).items():          # trailing punctuation are one target
        g = groups.setdefault(source_id(url), {'spellings': [], 'files': [], 'rows': 0})
        g['spellings'].append(url)
        g['rows'] += e['rows']
        g['files'] += [f for f in e['files'] if f not in g['files']]
    out: dict[str, str] = {}
    for sid, g in groups.items():
        if urls & set(g['spellings']):
            continue
        rec = record(g['spellings'], g, citers)
        if ids.get(rec['id']) == rec['url']:     # get-default: an id no record holds -- written earlier, kept
            continue
        if rec['id'] in ids:
            raise SystemExit('%s: id %s is already a data/sources/ record for another URL; extend the id rule'
                             % (rec['url'], rec['id']))
        head = ('# data/sources/2026/%s.yaml -- scaffolded by scripts/scaffold_epoch_sources.py (P3-S4-T05)\n'
                '# from a `Source link` in Epoch\'s export. The archive fields are ingest/archive_sources.py\'s.\n'
                % rec['id'])
        text = fmt.format_text(head + fmt.dumps(rec), Source)
        out[os.path.join(OUT, rec['id'] + '.yaml')] = text
    return out


def main(argv: list[str]) -> int:
    epoch = argv[argv.index('--epoch') + 1] if '--epoch' in argv else EPOCH
    if not glob.glob(os.path.join(epoch, '*_external.csv')):
        print('no Epoch export at %s: restore it with `python scripts/epoch_audit.py --fetch`' % epoch,
              file=sys.stderr)
        return 2
    ls = links(epoch)
    targets = {source_id(u) for u in ls}
    files = plan(epoch)
    for rel in files:
        print(('would write  ' if '--dry-run' in argv else 'wrote  ') + rel)
        if '--dry-run' not in argv:
            with open(os.path.join(ROOT, rel), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(files[rel])
    print('scaffold_epoch_sources: %d distinct Source links, %d targets after merging spellings; %d already '
          'held by data/sources/; %d %s' % (len(ls), len(targets), len(targets) - len(files), len(files),
                                           'to write' if '--dry-run' in argv else 'written'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
