"""The cross-record rules for Stage-3 classification records and the failure log (P1-S1-T03; 03 S3.3).

schema/classification.py checks each file on its own at tier 1. These rules read more than one file:

  tier 2  classification-entry   the record's id is a stress-corpus entry (taxonomy/_corpus/stress-corpus.yaml)
                                 and its corpus_item is that entry's position
          failure-ref            every failure a record cites exists, names the record's benchmark and
                                 the field that cites it, and is still open: a failure marked `resolved`
                                 (P1-S1-T08) no longer applies, so an assignment cannot rest on it
          adr-ref                a failure routed to an ADR names a file in adr/ that exists and names
                                 the failure back, so the decision and its evidence cannot drift apart
                                 (P1-S1-T06)
  tier 3  abstention-logged      every abstention has its failure record: the task's DONE WHEN, "every
                                 abstention has a matching failure record"; tier 1 already requires the
                                 id, and failure-ref that it resolves
          failure-uncited        an open failure for a classified benchmark is cited by that classification, so
                                 the log and the records cannot drift apart. A failure for a benchmark with
                                 no classification record (a later `bench tag-gap`, 05 S3) is not in scope
          blocking-adr           a blocking failure is routed to an ADR: 03 S8.3 handles blocking failures
                                 immediately, and P1-S1-T06's DONE WHEN is "No blocking failure record
                                 lacks an ADR reference"
          failure-triaged        (warning) a failure carries a route (adr, homograph or stage-4), so a
                                 newly logged failure is visible until it is triaged
"""
from __future__ import annotations

import os

from schema.taxonomy import read_yaml

CORPUS = 'taxonomy/_corpus/stress-corpus.yaml'


def _corpus_positions(root: str) -> dict[str, int]:
    try:
        entries = read_yaml(os.path.join(root, CORPUS))['entries']
    except (OSError, KeyError, TypeError):
        return {}
    return {e['id']: i for i, e in enumerate(entries, 1) if isinstance(e, dict) and 'id' in e}


def check(records, root: str, tiers=(2, 3)) -> list:
    from tools.validate.tiers import Finding
    out = []
    cls = [r for r in records if r.kind is not None and r.kind.name == 'classification' and r.model is not None]
    fails = {r.stem: r for r in records if r.kind is not None and r.kind.name == 'failure' and r.model is not None}
    positions = _corpus_positions(root)
    cited: set[str] = set()
    for r in cls:
        m = r.model
        if 2 in tiers:
            if m.id not in positions:
                out.append(Finding(2, 'classification-entry', 'blocking', m.id, r.path,
                                   '%s is not an entry of %s' % (m.id, CORPUS)))
            elif positions[m.id] != m.corpus_item:
                out.append(Finding(2, 'classification-entry', 'blocking', m.id, r.path,
                                   'corpus_item is %d, but %s is item %d of %s' % (m.corpus_item, m.id, positions[m.id],
                                                                                    CORPUS)))
        for field, fid in m.failures():
            cited.add(fid)
            f = fails.get(fid)
            if 2 in tiers:
                if f is None:
                    out.append(Finding(2, 'failure-ref', 'blocking', m.id, r.path,
                                       'facets.%s cites failure %s, and taxonomy/_failures/%s.yaml does not exist'
                                       % (field, fid, fid), related=(fid,)))
                elif (f.model.benchmark, f.model.facet) != (m.id, field):
                    out.append(Finding(2, 'failure-ref', 'blocking', m.id, r.path,
                                       'facets.%s cites failure %s, which is about %s / %s' % (
                                           field, fid, f.model.benchmark, f.model.facet), related=(fid,)))
                elif f.model.resolved is not None:
                    out.append(Finding(2, 'failure-ref', 'blocking', m.id, r.path,
                                       'facets.%s cites failure %s, which is marked resolved' % (field, fid),
                                       related=(fid,)))
        if 3 in tiers:
            for field in m.abstentions():
                if not any(fields == field and fid in fails for fields, fid in m.failures()):
                    out.append(Finding(3, 'abstention-logged', 'blocking', m.id, r.path,
                                       'facets.%s abstains with no failure record in taxonomy/_failures/' % field))
    for fid, f in sorted(fails.items()):
        m = f.model
        if 2 in tiers and m.adr is not None:
            path = os.path.join(root, m.adr)
            try:
                text = open(path, encoding='utf-8').read()
            except OSError:
                out.append(Finding(2, 'adr-ref', 'blocking', fid, f.path, 'routed to %s, which does not exist' % m.adr))
            else:
                if fid not in text:
                    out.append(Finding(2, 'adr-ref', 'blocking', fid, f.path,
                                       'routed to %s, whose text does not name %s' % (m.adr, fid)))
        if 3 in tiers:
            if m.blocking and m.route != 'adr':
                out.append(Finding(3, 'blocking-adr', 'blocking', fid, f.path,
                                   'a blocking failure with no ADR: set `route: adr` and `adr: adr/NNNN-....md`'))
            elif m.route is None:
                out.append(Finding(3, 'failure-triaged', 'warning', fid, f.path,
                                   'not yet triaged: set `route` to adr, homograph or stage-4 (03 S3.3)'))
    if 3 in tiers:
        classified = {r.model.id for r in cls}
        for fid, f in sorted(fails.items()):
            if f.model.benchmark in classified and fid not in cited and f.model.resolved is None:
                out.append(Finding(3, 'failure-uncited', 'blocking', fid, f.path,
                                   'a failure for %s that its classification record does not cite' % f.model.benchmark,
                                   related=(f.model.benchmark,)))
    return out
