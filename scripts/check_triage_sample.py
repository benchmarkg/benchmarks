#!/usr/bin/env python3
"""The 200-abstract labelling sample, drawn with a real denominator, and its check (P5-S5-T05; 06 S5.1-5.2).

    python scripts/check_triage_sample.py                     # check the newest evals/triage/sample-*.yaml
    python scripts/check_triage_sample.py PATH                # check one
    python scripts/check_triage_sample.py --draw --from 2026-09-10 --until 2026-09-16 --seed 20261009

Why. 06 S5.1: the regex triage's precision was hand-checked on 13 flagged titles, and "true recall is unmeasured
because the positive set was never enumerated". Recall needs a denominator: every paper in a window, not the
papers some filter already liked. So the sample is drawn from the full listing, and the check proves it was.

The frame (--draw). Every paper whose FIRST version was submitted inside the window (arXivRaw's v1 date, UTC)
and that carries any of cs.AI, cs.CL, cs.CV or cs.LG (06 S5.1's four, primary or cross-listed). It is
enumerated from OAI-PMH, set=cs, from the window's first day to the day of the draw: a record's datestamp is its
LAST modification, so a paper submitted in the window and revised since carries a later datestamp, and a harvest
that stopped at the window's end would miss it. The harvest is complete when its last page carries no
resumptionToken, which is how OAI-PMH ends a list. arXiv's endpoint states no completeListSize (checked
2026-10-10: its tokens carry only an expirationDate), so none is recorded; one that is stated must equal the
records read. Every request goes through ingest/policy.yaml's gate (oaipmh.arxiv.org, one request
every 3 s). export.arxiv.org's search API is not used: its robots.txt disallows every path for every agent.

The draw. The 200 arXiv ids with the smallest sha256("<seed>:<id>") over the whole listing: a uniform sample
without replacement, reproducible in any language, and conditioned on nothing but the seed. random.sample is not
used because Python does not promise its algorithm across versions.

The sheet. Each sampled item carries its arXiv id, title and abstract -- nothing else, and in particular no
heuristic verdict, so the labeller is not anchored by one (P5-S5-T06 writes the labels to a separate file).

What the check proves, each a failure when it does not hold:

  - the window, the categories, the seed, the method and the denominator are recorded, and the denominator is the
    listing's length;
  - the harvest ran to the end of the list (its last page had no resumptionToken), and read as many records as the
    endpoint said the list held, where it said;
  - every listed paper lies inside the window and carries one of the four categories; no id is listed twice;
  - the sample is exactly the 200 ids the recorded seed selects from the whole listing -- so it is uniform over
    the full window, by construction, and cannot have been drawn from a subset;
  - it is not the regex hit set: 06 S5.1's regex does not flag every sampled abstract, and flags no larger a share
    than chance allows (a sample drawn from the hits would be all hits);
  - an item carries its id, title and abstract only.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SAMPLES = os.path.join(ROOT, 'evals', 'triage')
CATEGORIES = ('cs.AI', 'cs.CL', 'cs.CV', 'cs.LG')
SIZE = 200
METHOD = 'the %d arXiv ids with the smallest sha256("<seed>:<id>") over the whole listing'
ITEM_KEYS = ('arxiv_id', 'title', 'abstract')
# 06 S5.1's triage regex, verbatim.
REGEX = re.compile(r'\b(we (introduce|present|propose|release|construct|curate)|this paper introduces)\b'
                   r'.{0,120}?\b(benchmark|dataset|suite|testbed|eval)\b', re.I | re.S)


class SampleError(Exception):
    pass


# ---- the draw -------------------------------------------------------------------------------------------------

def key(seed: int, arxiv_id: str) -> str:
    return hashlib.sha256(('%d:%s' % (seed, arxiv_id)).encode('utf-8')).hexdigest()


def draw(seed: int, ids, size: int = SIZE) -> list[str]:
    """The `size` ids with the smallest key, in key order."""
    return sorted(ids, key=lambda i: key(seed, i))[:size]


def in_frame(record: dict, start: date, end: date) -> bool:
    if record['deleted']:
        return False
    v1 = record['versions'][0]['date']
    return start.isoformat() <= v1 <= end.isoformat() and any(c in CATEGORIES for c in record['categories'])


def _texts(body: bytes) -> dict[str, tuple[str, str]]:
    """id -> (title, abstract), whitespace collapsed, for every record on one page."""
    from ingest.adapters import arxiv_oai as A
    out = {}
    for raw in ET.fromstring(body).iter('{%s}arXivRaw' % A.NS['r']):
        ident = A._text(raw, 'r:id')
        out[ident] = (A._text(raw, 'r:title') or '', A._text(raw, 'r:abstract') or '')
    return out


def harvest(start: date, end: date, until: date, transport=None, log=print) -> dict:
    """The frame: every record of set=cs modified from `start` to `until`, kept when in_frame()."""
    from ingest.adapters import arxiv_oai as A
    transport = transport or A.NetworkTransport()
    window = (start, until)
    url, token, pages, seen, size, deleted = A.list_url(window), None, 0, 0, None, 0
    frame = {}
    while True:
        resp = transport.get(url, {})
        if resp.status != 200:
            raise SampleError('%s answered HTTP %d' % (url, resp.status))
        try:
            records, token = A.parse_page(resp.body, url)
        except KeyError:
            raise SampleError('badResumptionToken mid-harvest; draw again') from None
        texts = _texts(resp.body)
        m = re.search(rb'<resumptionToken[^>]*completeListSize=["\'](\d+)["\']', resp.body)
        if m:
            size = int(m.group(1))
        pages += 1
        seen += len(records)
        for r in records:
            deleted += r['deleted']
            if in_frame(r, start, end):
                title, abstract = texts[r['arxiv_id']]
                frame[r['arxiv_id']] = {'v1': r['versions'][0]['date'], 'categories': r['categories'],
                                        'title': title, 'abstract': abstract}
        log('page %d: %d records, %d read of %s, %d in the frame' % (pages, len(records), seen, size, len(frame)))
        if not token:
            break
        url = A.list_url(window, token)
    return {'frame': frame, 'records': seen, 'complete_list_size': size, 'last_page_token': token,
            'pages': pages, 'deleted': deleted, 'request': A.list_url(window).split('?', 1)[1]}


def build(h: dict, start: date, end: date, seed: int, retrieved_at: str) -> dict:
    frame = h['frame']
    ids = sorted(frame)
    chosen = draw(seed, ids)
    return {
        'sample_of': 'arXiv papers first submitted in the window, in any of the four categories',
        'window': {'field': 'the first version\'s submission date (arXivRaw version v1), UTC',
                   'from': start.isoformat(), 'until': end.isoformat(), 'categories': list(CATEGORIES)},
        'harvest': {'endpoint': 'https://oaipmh.arxiv.org/oai', 'request': h['request'], 'retrieved_at': retrieved_at,
                    'pages': h['pages'], 'records_read': h['records'], 'complete_list_size': h['complete_list_size'],
                    'last_page_token': h['last_page_token'], 'deleted_records': h['deleted']},
        'denominator': len(ids),
        'seed': seed,
        'method': METHOD % SIZE,
        'size': SIZE,
        'listing': ['%s %s %s' % (i, frame[i]['v1'], ' '.join(c for c in frame[i]['categories'] if c in CATEGORIES))
                    for i in ids],
        'sample': [{'arxiv_id': i, 'title': frame[i]['title'], 'abstract': frame[i]['abstract']} for i in chosen],
    }


HEADER = ('# The 200-abstract labelling sample (P5-S5-T05; 06 S5.1-5.2), drawn by scripts/check_triage_sample.py\n'
          '# --draw and checked by it. Titles and abstracts are arXiv metadata, CC0 1.0. No heuristic verdict is\n'
          '# attached: P5-S5-T06 labels every item by hand, in evals/triage/labels-<date>.yaml.\n')


def write(doc: dict, path: str) -> None:
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(HEADER)
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=120, default_flow_style=False)


# ---- the check -------------------------------------------------------------------------------------------------

def hits(items) -> int:
    return sum(1 for it in items if REGEX.search('%s. %s' % (it['title'], it['abstract'])))


def check(doc: dict) -> list[str]:
    """Every reason `doc` is not a uniform sample of its whole window; empty when it is."""
    errs = []
    need = ('window', 'harvest', 'denominator', 'seed', 'method', 'size', 'listing', 'sample')
    missing = [k for k in need if k not in doc]
    if missing:
        return ['the sample does not record %s' % ', '.join(missing)]
    w = doc['window']
    try:
        start, end = date.fromisoformat(str(w['from'])), date.fromisoformat(str(w['until']))
    except (KeyError, ValueError) as e:
        return ['the window is not two dates: %s' % e]
    if start > end:
        errs.append('the window runs backwards: %s to %s' % (start, end))
    if sorted(w.get('categories') or []) != sorted(CATEGORIES):            # get-default: missing is the error
        errs.append('the window\'s categories are %s, not 06 S5.1\'s four %s' % (w.get('categories'), list(CATEGORIES)))  # get-default: as above
    if doc['method'] != METHOD % doc['size'] or doc['size'] != SIZE:
        errs.append('the method or size is not the one this check re-derives (%r, %r)' % (doc['method'], doc['size']))
    h = doc['harvest']
    if 'last_page_token' not in h or h['last_page_token'] is not None:
        errs.append('the harvest did not run to the end of the list (its last page carried a resumptionToken, or '
                    'none is recorded): the frame is incomplete')
    stated = h.get('complete_list_size')                                      # get-default: absent is not stated
    if stated is not None and h.get('records_read') != stated:                # get-default: missing fails the comparison
        errs.append('the harvest read %s records of the %s the endpoint listed: the frame is incomplete'
                    % (h.get('records_read'), stated))                       # get-default: as above

    listing = doc['listing']
    ids, bad = [], []
    for line in listing:
        parts = str(line).split()
        if len(parts) < 3:
            bad.append(str(line))
            continue
        ident, v1, cats = parts[0], parts[1], parts[2:]
        ids.append(ident)
        if not (start.isoformat() <= v1 <= end.isoformat()) or not any(c in CATEGORIES for c in cats):
            bad.append(str(line))
    if bad:
        errs.append('%d listed papers lie outside the window or the four categories: %s' % (len(bad), ', '.join(bad[:3])))
    if len(set(ids)) != len(ids):
        errs.append('the listing names %d papers more than once' % (len(ids) - len(set(ids))))
    if doc['denominator'] != len(listing):
        errs.append('the denominator is %s but the listing holds %d papers' % (doc['denominator'], len(listing)))

    sample = doc['sample']
    sids = [it.get('arxiv_id') for it in sample]                              # get-default: a missing id fails below
    if len(sample) != doc['size']:
        errs.append('the sample holds %d items, not %d' % (len(sample), doc['size']))
    extra = sorted({k for it in sample for k in it} - set(ITEM_KEYS))
    if extra:
        errs.append('sampled items carry %s: the sheet is id, title and abstract only (no verdict)' % ', '.join(extra))
    empty = [it.get('arxiv_id') for it in sample if not it.get('title') or not it.get('abstract')]   # get-default: as above
    if empty:
        errs.append('%d sampled items have no title or abstract: %s' % (len(empty), ', '.join(map(str, empty[:3]))))
    outside = [i for i in sids if i not in set(ids)]
    if outside:
        errs.append('%d sampled papers are not in the listing: %s' % (len(outside), ', '.join(map(str, outside[:3]))))
    expected = draw(int(doc['seed']), ids, doc['size'])
    if sorted(map(str, sids)) != sorted(expected):
        errs.append('the sample is not the %d ids seed %s selects from the whole listing (%d differ): it was not drawn '
                    'uniformly from the full window' % (doc['size'], doc['seed'], len(set(expected) - set(map(str, sids)))))

    # Not the regex hit set: a sample drawn from the hits would be all hits. The bound is generous: the share may
    # not exceed what a uniform draw would show with a 1-in-10^6 chance, taking the hit rate as at most a half.
    n, k = len(sample), hits(sample)
    if n and k == n:
        errs.append('06 S5.1\'s regex flags all %d sampled abstracts: the sample was drawn from its hit set' % n)
    elif n and k > n * 0.5 + 5 * math.sqrt(n * 0.25):
        errs.append('06 S5.1\'s regex flags %d of %d sampled abstracts, more than a uniform draw allows' % (k, n))
    return errs


def _rel(path: str) -> str:
    try:
        return os.path.relpath(path, ROOT).replace(os.sep, '/')
    except ValueError:                        # another drive (Windows): there is no relative path
        return path


def newest() -> str | None:
    found = sorted(glob.glob(os.path.join(SAMPLES, 'sample-*.yaml')))
    return found[-1] if found else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('path', nargs='?')
    p.add_argument('--draw', action='store_true', help='harvest the window and write a new sample')
    p.add_argument('--from', dest='start')
    p.add_argument('--until', dest='end')
    p.add_argument('--seed', type=int)
    a = p.parse_args(argv)
    if a.draw:
        if not (a.start and a.end and a.seed is not None):
            p.error('--draw needs --from, --until and --seed')
        now = datetime.now(timezone.utc).replace(microsecond=0)
        start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
        h = harvest(start, end, now.date(), log=lambda s: print(s, file=sys.stderr))
        doc = build(h, start, end, a.seed, now.strftime('%Y-%m-%dT%H:%M:%SZ'))
        os.makedirs(SAMPLES, exist_ok=True)
        path = a.path or os.path.join(SAMPLES, 'sample-%s.yaml' % now.date().isoformat())
        write(doc, path)
        print('wrote %s: %d of %d papers, seed %d' % (_rel(path), len(doc['sample']), doc['denominator'], a.seed))
    path = a.path or newest()
    if path is None:
        print('check_triage_sample: no evals/triage/sample-*.yaml to check')
        return 1
    with open(path, encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    errs = check(doc)
    rel = _rel(path)
    if errs:
        for e in errs:
            print('%s: %s' % (rel, e))
        return 1
    print('%s: %d of %d papers first submitted %s to %s in %s, seed %s; uniform over the whole listing; the regex '
          'flags %d of them' % (rel, len(doc['sample']), doc['denominator'], doc['window']['from'], doc['window']['until'],
                                ', '.join(CATEGORIES), doc['seed'], hits(doc['sample'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
