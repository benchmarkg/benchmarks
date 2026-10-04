"""`bench report completeness` (P3-S1-T07; 04 S8, 13 S4.5).

Per claim: the material field set its benchmark resolves to, how many of those its condition record answers,
and condition_completeness with its denominator shown -- the weighted sums it is a ratio of, and the material
field count -- because a bare percentage is the category error 04 S8 warns about ("Quote the figure with its
profile or not at all"). Resolution and weights are tools/build/comparability.py's, so this report and the
build can never disagree.
"""
from __future__ import annotations

import glob
import os

from schema.benchmark import load_benchmark
from schema.claim import ResultClaim
from schema.conditions import EvalConditions
from schema.stub import curated_benchmark_files
from schema.taxonomy import read_yaml
from tools.build import comparability as comp

COLUMNS = ['claim', 'benchmark', 'metric', 'system', 'profiles', 'material', 'populated', 'fields_material_total',
           'weight_answered', 'weight_total', 'condition_completeness', 'unknown_fields']


def build(root: str) -> dict:
    pf = comp.load_profiles(os.path.join(root, 'taxonomy', 'comparability-profiles.yaml'))
    resolutions = {}
    for path in curated_benchmark_files(root):
        b = load_benchmark(path)
        resolutions[b.id] = comp.resolve_profile(b, pf)
    conditions = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'conditions', '**', '*.yaml'), recursive=True)):
        c = EvalConditions.model_validate(read_yaml(path))
        conditions[c.id] = c
    rows = []
    for path in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        cl = ResultClaim.model_validate(read_yaml(path))
        res = resolutions.get(cl.benchmark.split('@')[0])        # get-default: a claim on an uncurated benchmark
        if res is None:
            continue
        cond = conditions.get(cl.eval_conditions) if cl.eval_conditions else None   # get-default: no record is all unknown
        got = comp.compute_for_claim(cl, res, cond)
        unknown = set(got.unknown_fields)
        total = sum(res.weights[f] for f in res.material)
        answered = sum(res.weights[f] for f in res.material if f not in unknown)
        rows.append({
            'claim': cl.id, 'benchmark': cl.benchmark, 'metric': cl.metric, 'system': cl.system,
            'profiles': list(res.profiles), 'material': list(res.material),
            'populated': len(res.material) - len(unknown), 'fields_material_total': got.fields_material_total,
            'weight_answered': round(answered, 6), 'weight_total': round(total, 6),
            'condition_completeness': None if got.condition_completeness is None
            else round(got.condition_completeness, 6),
            'unknown_fields': list(got.unknown_fields)})
    rows.sort(key=lambda r: (r['benchmark'], r['metric'], r['system'], r['claim']))
    scored = [r['condition_completeness'] for r in rows if r['condition_completeness'] is not None]
    return {'report': 'completeness', 'columns': COLUMNS, 'rows': rows, 'summary': {
        'claims': len(rows),
        'claims_fully_specified': sum(1 for r in rows if r['condition_completeness'] == 1.0),
        'claims_with_no_answered_field': sum(1 for r in rows if r['populated'] == 0),
        'mean_condition_completeness': round(sum(scored) / len(scored), 6) if scored else None,
        'note': 'per-profile ratios: compare a claim only with its own denominator (04 S8)'}}
