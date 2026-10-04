"""`bench report quality` (P3-S1-T07; 05 S3, S7; 04 S12 tier 4).

The validation findings that do not block -- warnings, and tier 4's quality signals -- grouped by rule, so the
triage stage has an input: how many of each, and which records. Blocking findings are `bench validate`'s and are
counted here only, never listed, since a blocking finding is fixed before anything is triaged. The findings are
tools/validate/tiers.py's own, over the whole tree.
"""
from __future__ import annotations

from collections import defaultdict

COLUMNS = ['rule', 'tier', 'severity', 'count', 'entities']


def build(root: str) -> dict:
    from tools.validate import tiers
    report = tiers.run(root)
    groups = defaultdict(set)
    for f in report.findings:
        if f.severity in ('warning', 'quality'):
            groups[(f.rule, f.tier, f.severity)].add(f.entity)
    rows = [{'rule': rule, 'tier': tier, 'severity': sev, 'count': len(ents), 'entities': sorted(ents)}
            for (rule, tier, sev), ents in groups.items()]
    rows.sort(key=lambda r: (-r['count'], r['rule'], r['tier']))
    return {'report': 'quality', 'columns': COLUMNS, 'rows': rows, 'summary': {
        'files': report.files, 'rules': len(rows),
        'warnings': sum(r['count'] for r in rows if r['severity'] == 'warning'),
        'quality_signals': sum(r['count'] for r in rows if r['severity'] == 'quality'),
        'blocking (see bench validate)': len(report.blocking)}}
