"""`bench report quality` (P3-S1-T07; 05 S3, S7; 04 S12 tier 4).

The validation findings that do not block -- warnings, and tier 4's quality signals -- grouped by rule, so the
triage stage has an input: how many of each, and which records. Blocking findings are `bench validate`'s and are
counted here only, never listed, since a blocking finding is fixed before anything is triaged. The findings are
tools/validate/tiers.py's own, over the whole tree.

The `material-waived` row also carries every waiver itself in `detail`, one item per waived field: the benchmark,
the field, its reason, and `[not material]` where the field was not in the benchmark's resolved set anyway (a
stray waiver, tools/build/comparability.py). 04 S8: "A waiver requires a reason string and shows up in the quality
dashboard, because the failure mode here is curators quietly waiving inconvenient fields until the comparability
check passes everything" -- a list of benchmarks alone would hide which fields went, and why (P3-S10-T01).
"""
from __future__ import annotations

import os
from collections import defaultdict

COLUMNS = ['rule', 'tier', 'severity', 'count', 'entities', 'detail']
WAIVED = 'material-waived'


def waivers(root: str) -> list[dict]:
    """Every comparability.material_waived entry on a curated benchmark, in (benchmark, field) order, with whether
    the field was material before the waiver (False: a stray waiver, which changes nothing)."""
    from schema.benchmark import load_benchmark
    from schema.stub import curated_benchmark_files
    from tools.build import comparability
    profiles = comparability.load_profiles(os.path.join(root, 'taxonomy', 'comparability-profiles.yaml'))
    out = []
    for path in curated_benchmark_files(root):
        b = load_benchmark(path)
        if not b.comparability.material_waived:
            continue
        stray = set(comparability.resolve_profile(b, profiles).stray_waivers)
        out += [{'benchmark': b.id, 'field': w.field, 'reason': ' '.join(w.reason.split()),
                 'material': w.field not in stray} for w in b.comparability.material_waived]
    return sorted(out, key=lambda w: (w['benchmark'], w['field']))


def build(root: str) -> dict:
    from tools.validate import tiers
    report = tiers.run(root)
    groups = defaultdict(set)
    for f in report.findings:
        if f.severity in ('warning', 'quality'):
            groups[(f.rule, f.tier, f.severity)].add(f.entity)
    rows = [{'rule': rule, 'tier': tier, 'severity': sev, 'count': len(ents), 'entities': sorted(ents)}
            for (rule, tier, sev), ents in groups.items()]
    waived = waivers(root)
    for r in rows:
        if r['rule'] == WAIVED:
            r['detail'] = ['%s: %s (%s)%s' % (w['benchmark'], w['field'], w['reason'],
                                              '' if w['material'] else ' [not material]')
                           for w in waived if w['benchmark'] in r['entities']]
    rows.sort(key=lambda r: (-r['count'], r['rule'], r['tier']))
    return {'report': 'quality', 'columns': COLUMNS, 'rows': rows, 'summary': {
        'files': report.files, 'rules': len(rows),
        'warnings': sum(r['count'] for r in rows if r['severity'] == 'warning'),
        'quality_signals': sum(r['count'] for r in rows if r['severity'] == 'quality'),
        'material_waivers': len(waived),
        'blocking (see bench validate)': len(report.blocking)}}
