"""A Source for every `Source link` in Epoch's export (P3-S4-T05; 06 S3.18, S7; 14 Phase 3).

VERIFY: "bench check-links --archive-missing reports zero unarchived Epoch sources". DONE WHEN: "Every
ingested source URL has an archive_url or a recorded archiving failure, so bare leaderboard URLs survive
rot." The capturing itself is ingest/archive_sources.py's and needs SPN2 credentials; what is held here is
that every link has a record, each record is shaped for the archiver, and the scaffold is repeatable. The
committed-export checks skip where epochdl/ is absent (00 S8.1).
"""
import glob
import os
import sys

import pytest
from ruamel.yaml import YAML

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import scaffold_epoch_sources as S  # noqa: E402
from schema.source import Source  # noqa: E402

SAFE = YAML(typ='safe', pure=True)
HAVE_EPOCH = bool(glob.glob(os.path.join(S.EPOCH, '*_external.csv')))
needs_epoch = pytest.mark.skipif(not HAVE_EPOCH, reason='epochdl/ is not in the working tree (00 S8.1)')


def records():
    out = {}
    for p in glob.glob(os.path.join(ROOT, 'data', 'sources', '**', '*.yaml'), recursive=True):
        with open(p, encoding='utf-8') as fh:
            r = SAFE.load(fh)
        out[r['id']] = r
    return out


OURS = {k: v for k, v in records().items() if v.get('drafted_by') == S.DRAFTED_BY}   # get-default: most have none


@needs_epoch
def test_every_epoch_source_link_has_a_source_record():
    held = {r['url'] for r in records().values()}
    for url in S.links():
        assert url in held or S.source_id(url) in OURS, url


@needs_epoch
def test_the_scaffold_is_repeatable_and_writes_nothing_twice():
    assert S.plan() == {}
    assert len(S.links()) == 101 and len({S.source_id(u) for u in S.links()}) == 88


def test_the_scaffolded_records_are_shaped_for_the_archiver():
    assert len(OURS) == 87
    for sid, r in OURS.items():
        if r['doi']:
            assert r['type'] == 'preprint' and r['archive_status'] == 'not-required' and not r['archive_url']
            assert r['url'] == 'https://arxiv.org/abs/%s' % r['doi'].split('arXiv.')[1]
            Source.model_validate(r)                                  # a DOI Source needs no capture (04 S12)
        elif r['archive_url']:
            # archive_digest comes from CDX, which indexes a Save Page Now capture hours after it is
            # made, so a fresh capture may not have one yet; tools/check_links.py skips its CDX
            # signal until it does.
            assert r['archive_status'] == 'ok' and r['archive_captured']
            assert r['archive_url'].startswith('https://web.archive.org/web/')
            Source.model_validate(r)
        else:
            assert r['archive_status'] in ('pending', 'failed')     # the archiver's to finish
            assert r['archive_status'] == 'pending' or r['failure_reason']
        assert r['licence_class'] == 'unlicensed' and 'not checked' in r['licence_basis']
        assert r['quote_extract'] is None                             # nothing fetched, so nothing quotable


@pytest.mark.parametrize('url, sid, kind', [
    ('http://arxiv.org/abs/2005.14165', 'src-arxiv-2005-14165', 'preprint'),
    ('https://arxiv.org/pdf/2307.09288v2', 'src-arxiv-2307-09288', 'preprint'),
    ('https://github.com/lechmazur/writing', 'src-github-com-lechmazur-writing', 'repository'),
    ('https://www.tbench.ai/leaderboard/terminal-bench/2.0', 'src-tbench-ai-leaderboard-terminal-bench-2-0',
     'leaderboard-page'),
    ('https://example.org/report.pdf', 'src-example-org-report-pdf', 'paper'),
    ('https://example.org/blog/post', 'src-example-org-blog-post', 'documentation'),
])
def test_the_id_and_type_rules(url, sid, kind):
    assert (S.source_id(url), S.source_type(url)) == (sid, kind)


def test_a_long_url_is_cut_and_keeps_a_hash():
    sid = S.source_id('https://example.org/' + 'a-very-long-path-segment/' * 6)
    assert len(sid) <= 64 and sid.startswith('src-example-org-') and len(sid.rsplit('-', 1)[1]) == 8
