"""taxonomy/_corpus/stress-corpus.yaml: every entry is primary-sourced (P1-S1-T02; 03 S3.2).

The task's DONE WHEN: "No 4xx and no suspect result across the 90 URLs; every entry carries a primary
source." The first half is `bench check-links taxonomy/_corpus/stress-corpus.yaml`, which needs the
network; it runs here only when BENCH_NETWORK=1. The second half is a fact about the file and is
checked always.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from schema.taxonomy import read_yaml  # noqa: E402
from tools import links  # noqa: E402

REL = 'taxonomy/_corpus/stress-corpus.yaml'
ARXIV = re.compile(r'^\d{4}\.\d{4,5}$')
DOI = re.compile(r'^10\.\d{4,9}/\S+$')


@pytest.fixture(scope='module')
def entries():
    return read_yaml(os.path.join(ROOT, REL))['entries']


def test_ninety_entries_each_with_a_url(entries):
    assert len(entries) == 90 and len({e['id'] for e in entries}) == 90
    assert all(links.URL.match(e['url']) for e in entries)


def test_every_entry_carries_a_primary_source(entries):
    for e in entries:
        paper = e.get('primary_paper') or {}
        if paper:
            ids = [k for k in ('arxiv_id', 'doi') if paper.get(k)]
            assert ids or paper.get('id_note'), e['id']
            if paper.get('arxiv_id'):
                assert ARXIV.match(paper['arxiv_id']) and paper['arxiv_id'] in paper['url'], e['id']
            if paper.get('doi'):
                assert DOI.match(paper['doi']), e['id']
        else:
            src = e.get('primary_source') or {}
            assert src.get('kind') and src.get('title') and links.URL.match(src.get('url', '')), e['id']
            assert e.get('primary_paper_note'), e['id']         # and says why there is no paper


def test_a_moved_url_records_where_it_was_and_why(entries):
    moved = [(e, f) for e in entries for f in e.get('flags') or [] if f.startswith('url moved on ')]
    assert len(moved) == 14
    for e, f in moved:
        old = re.search(r'from (\S+?): ', f).group(1)
        assert old != e['url'] and links.URL.match(old)


def test_check_links_walks_every_url_the_file_holds(entries):
    walked = {lk.url for lk in links.collect(ROOT, [REL])}
    for e in entries:
        assert e['url'] in walked
        for part in ('primary_paper', 'primary_source'):
            if (e.get(part) or {}).get('url'):
                assert e[part]['url'] in walked


@pytest.mark.skipif(os.environ.get('BENCH_NETWORK') != '1', reason='resolves 180 URLs; set BENCH_NETWORK=1')
def test_no_dead_and_no_suspect_link():
    report = links.run(ROOT, paths=[REL], cache_path=False, resolver=links.Resolver(timeout=20))
    bad = [(r['where'], r['class'], r['detail']) for r in report['links'] if r['class'] not in ('live', 'redirected')]
    assert bad == [] and report['exit_code'] == 0
