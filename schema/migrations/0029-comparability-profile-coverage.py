"""Migration 0029: the five entries with an empty facet pin their comparability profile (ADR-0029; P3-S10-T01).

The corpus half of ADR-0029. taxonomy/comparability-profiles.yaml 0.3.0 lists every (evaluation_method, subject)
pair the curated corpus makes, so a benchmark resolves from its facets -- except where one of the two facet lists is
deliberately empty, a logged vocabulary gap, and there is no pair to look up. Those entries pin
`comparability.profile` (04 S5 lets a curator set it), each to the profile whose shape its own notes describe:

  hear, superb, zerospeech     trained-model     frozen or self-supervised encoders scored through probes;
                                                 designed_for_subjects is empty (the gap superb logged)
  epoch-capabilities-index     relative-ranking     its one method is entrant-relative-ranking; subjects empty by
                                                 ADR-0020
  fiction-livebench            llm-static-text   prompted instruction-tuned and reasoning models; evaluation_method
                                                 is empty because no source states the grading

A row is planned only while the entry's profile is unset and one facet list is still empty, so a re-run over an
applied tree plans nothing, and an entry whose facets get filled later resolves from them instead.
"""
from __future__ import annotations

from schema.migrations import ABSENT, Row, entity_files

KIND = 'field'
SUMMARY = ('ADR-0029: hear, superb, zerospeech, epoch-capabilities-index and fiction-livebench, whose facets leave '
           'no pair to look up, pin comparability.profile')

PINS = {
    'hear': 'trained-model',
    'superb': 'trained-model',
    'zerospeech': 'trained-model',
    'epoch-capabilities-index': 'relative-ranking',
    'fiction-livebench': 'llm-static-text',
}


def plan(root: str) -> list[Row]:
    rows = []
    for rel, doc in entity_files(root):
        if not isinstance(doc, dict) or doc.get('id') not in PINS:
            continue
        if doc.get('evaluation_method') and doc.get('designed_for_subjects'):
            continue                                    # facets filled since: they resolve the profile
        comp = doc.get('comparability')
        if isinstance(comp, dict) and comp.get('profile') is not None:
            continue                                    # applied, or a curator's own pin
        if isinstance(comp, dict):
            rows.append(Row(rel, ('comparability', 'profile'), ABSENT, PINS[doc['id']]))
        else:
            rows.append(Row(rel, ('comparability',), ABSENT, {'profile': PINS[doc['id']]}))
    return rows
