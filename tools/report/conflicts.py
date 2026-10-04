"""`bench report conflicts` (P3-S1-T07; 05 S3, 04 S10 "Near-duplicate detection").

Claims about one measurement -- the same benchmark (and version), subset, metric and system (and version) --
whose values disagree. For each such group, every field that differs among the claims is named, and where they
point at different condition records, so is every condition field that differs: a disagreement explained by a
reasoning effort or a harness reads as explained, and one with no differing field is the case to look at.

The task's key is (benchmark, metric, system). Subset is added to it, because two subsets are two measurements
(ForecastBench's 7-day and 30-day horizons), and reporting them as disagreeing would bury the real conflicts.
Nothing here merges or picks a winner: 04 S10, "Never dedupe on ingest". The report is for a person.
"""
from __future__ import annotations

import glob
import os
from collections import defaultdict

from schema.claim import ResultClaim
from schema.conditions import FIELDS, EvalConditions
from schema.taxonomy import read_yaml

COLUMNS = ['benchmark', 'subset', 'metric', 'system', 'claims', 'values', 'differing_fields']
# What a claim says; its id, prose and machine bookkeeping are not a disagreement
IGNORED = {'id', 'notes', 'ingestion', 'external_ids', 'provenance_snapshot', 'artifact_archived', 'superseded_by'}


def _plain(v):
    return v.model_dump(mode='json') if hasattr(v, 'model_dump') else v


def find(claims: list[ResultClaim], conditions: dict[str, EvalConditions]) -> list[dict]:
    groups = defaultdict(list)
    for c in claims:
        if c.superseded_by is None:                          # a superseded claim is history, not a rival
            groups[(c.benchmark, c.subset, c.metric, c.system)].append(c)
    rows = []
    for (bench, subset, metric, system), members in groups.items():
        values = sorted({(c.value, c.value_text) for c in members}, key=repr)
        if len(members) < 2 or len(values) < 2:
            continue
        fields = sorted(f for f in ResultClaim.model_fields if f not in IGNORED
                        and len({repr(_plain(getattr(c, f))) for c in members}) > 1)
        conds = [conditions.get(c.eval_conditions) if c.eval_conditions else None for c in members]  # get-default: an unrecorded condition reads as none
        if 'eval_conditions' in fields:
            for f in FIELDS:
                if len({repr(_plain(getattr(x, f))) if x else None for x in conds}) > 1:
                    fields.append('eval_conditions.' + f)
        rows.append({'benchmark': bench, 'subset': subset, 'metric': metric, 'system': system,
                     'claims': sorted(c.id for c in members),
                     'values': [v if t is None else t for v, t in values],
                     'differing_fields': fields})
    rows.sort(key=lambda r: (r['benchmark'], r['subset'] or '', r['metric'], r['system']))
    return rows


def build(root: str) -> dict:
    claims = [ResultClaim.model_validate(read_yaml(p))
              for p in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True))]
    conditions = {}
    for p in sorted(glob.glob(os.path.join(root, 'data', 'conditions', '**', '*.yaml'), recursive=True)):
        c = EvalConditions.model_validate(read_yaml(p))
        conditions[c.id] = c
    rows = find(claims, conditions)
    return {'report': 'conflicts', 'columns': COLUMNS, 'rows': rows, 'summary': {
        'claims': len(claims), 'conflicting_groups': len(rows),
        'unexplained': sum(1 for r in rows if r['differing_fields'] == ['value'])}}
