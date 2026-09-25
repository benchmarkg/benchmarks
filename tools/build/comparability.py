#!/usr/bin/env python3
"""The comparability rule, computed at build time (P0-S4-T06; 04-data-model.md S8, 13 S4.5).

    python tools/build/comparability.py                 # JSON on stdout
    python tools/build/comparability.py --out build/comparability.json [--root PATH]

Derived values never live in the source YAML (04 S1), so this is where they are made:

    material  = profile(benchmark.evaluation_method, benchmark.designed_for_subjects)
                + benchmark.comparability.material_extra
                - benchmark.comparability.material_waived

    tuple     = [benchmark_version, metric, subset]
                + [ canonicalise(conditions[f]) if conditions[f] is not None else "?"
                    for f in sorted(material) ]

    comparability_key        = sha256(json.dumps(tuple, separators=(",", ":")))[:16]
    key_unknown_count        = tuple.count("?")
    condition_completeness   = sum(w[f] for f in material if conditions[f] is not None)
                               / sum(w[f] for f in material)

The material set is resolved PER BENCHMARK, never globally (04 S8: "there is no such number as the
count of material fields at schema v1"); `fields_material_total` is read off the resolution.

How `profile(...)` resolves, since 04 S8 gives it lists and taxonomy/comparability-profiles.yaml
gives it pairs:
  1. A hand-set `comparability.profile` pins that one profile (04 S5 lets a curator set it).
  2. Otherwise every (evaluation_method, subject) pair in the benchmark's two facet lists is looked
     up, and the material set is the UNION of every profile hit. A benchmark that is both
     model-graded and agentic is material on both profiles' fields; dropping either would let two
     claims agree on a key while differing on a field the benchmark's own method makes material.
  3. No pair hits: the file's `fallback`, and the resolution says so (`basis: fallback`), because an
     unlisted pair means the vocabulary grew and the profile file did not.
Weights come from the profiles' `weights`, the highest where two profiles weigh one field, else
`default_weight`.

One refinement to 04's `is not None`, from 13 S4.5: "The schema penalises unknowns, not absences."
A field whose `*_available` companion (schema.conditions.COMPANIONS) is explicitly `false` was
answered -- the provider publishes no snapshot -- so it counts towards completeness and enters the
key as JSON null, not as "?". A companion that is null answers nothing.

Waivers need a reason (enforced by schema.benchmark.Waiver) and are reported per benchmark, since the
quality dashboard lists them (04 S8). A waiver of a field that was not material is reported as stray
rather than rejected: it changes nothing, and the dashboard is where it should be seen.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from schema.benchmark import Benchmark, load_benchmark  # noqa: E402
from schema.claim import ResultClaim  # noqa: E402
from schema.conditions import FIELDS, EvalConditions  # noqa: E402
from schema.taxonomy import ComparabilityProfileFile, read_yaml  # noqa: E402

UNKNOWN = '?'
PROFILES_PATH = os.path.join(ROOT, 'taxonomy', 'comparability-profiles.yaml')


def load_profiles(path: str = PROFILES_PATH) -> ComparabilityProfileFile:
    pf = ComparabilityProfileFile.model_validate(read_yaml(path))
    for name, material in [('fallback', pf.fallback.material)] + [(p.id, p.material) for p in pf.profiles]:
        stray = sorted(set(material) - set(FIELDS))
        if stray:
            raise ValueError('profile %s names fields EvalConditions does not have: %s' % (name, ', '.join(stray)))
    return pf


@dataclass(frozen=True)
class Resolution:
    benchmark: str
    basis: str                                   # explicit | facets | fallback
    profiles: tuple[str, ...]
    material: tuple[str, ...]                    # sorted; the set the key is built over
    weights: dict[str, float]
    waived: dict[str, str] = field(default_factory=dict)       # field -> reason
    stray_waivers: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()

    @property
    def fields_material_total(self) -> int:
        return len(self.material)

    def as_dict(self) -> dict:
        return {'basis': self.basis, 'profiles': list(self.profiles), 'material': list(self.material),
                'fields_material_total': self.fields_material_total, 'weights': self.weights,
                'material_extra': list(self.extra), 'material_waived': self.waived,
                'stray_waivers': list(self.stray_waivers)}


def resolve_profile(benchmark: Benchmark, profiles: ComparabilityProfileFile | None = None) -> Resolution:
    pf = profiles or load_profiles()
    by_id = {p.id: p for p in pf.profiles}
    comp = benchmark.comparability

    if comp.profile is not None:
        hits, basis = [by_id[comp.profile]], 'explicit'
    else:
        pairs = {(m, s) for m in benchmark.evaluation_method for s in benchmark.designed_for_subjects}
        hits = [p for p in pf.profiles if pairs & set(p.applies_to)]
        basis = 'facets' if hits else 'fallback'

    base = set(pf.fallback.material) if basis == 'fallback' else {f for p in hits for f in p.material}
    for name, fields in (('material_extra', comp.material_extra), ('material_waived', [w.field for w in comp.material_waived])):
        stray = sorted(set(fields) - set(FIELDS))
        if stray:
            raise ValueError('%s: comparability.%s names fields EvalConditions does not have: %s'
                             % (benchmark.id, name, ', '.join(stray)))
    waived = {w.field: w.reason for w in comp.material_waived}
    material = (base | set(comp.material_extra)) - set(waived)
    weights = {}
    for f in sorted(material):
        ws = [p.weights[f] for p in hits if p.weights and f in p.weights]
        weights[f] = max(ws) if ws else pf.default_weight
    return Resolution(
        benchmark=benchmark.id, basis=basis, profiles=tuple(p.id for p in hits), material=tuple(sorted(material)),
        weights=weights, waived=waived,
        stray_waivers=tuple(sorted(set(waived) - base - set(comp.material_extra))),
        extra=tuple(comp.material_extra))


def canonicalise(v: Any) -> Any:
    """One spelling per meaning: NFC-stripped strings, integral floats as ints (a temperature of 1 and
    of 1.0 is one condition), lists as sorted sets (tool order is not a condition), mappings with
    sorted keys, dates as ISO strings."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else v
    if isinstance(v, str):
        s = unicodedata.normalize('NFC', v).strip()
        if s == UNKNOWN:
            raise ValueError('%r is the unknown marker and cannot be a condition value' % UNKNOWN)
        return s
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: canonicalise(v[k]) for k in sorted(v)}
    if isinstance(v, (list, tuple, set)):
        items = {json.dumps(canonicalise(x), separators=(',', ':')): canonicalise(x) for x in v}
        return [items[k] for k in sorted(items)]
    raise TypeError('cannot canonicalise %r' % (v,))


@dataclass(frozen=True)
class Comparability:
    comparability_key: str
    key_unknown_count: int
    condition_completeness: float | None      # None only when every material field was waived
    unknown_fields: tuple[str, ...]
    fields_material_total: int

    def as_dict(self) -> dict:
        return {'comparability_key': self.comparability_key, 'key_unknown_count': self.key_unknown_count,
                'condition_completeness': self.condition_completeness, 'unknown_fields': list(self.unknown_fields),
                'fields_material_total': self.fields_material_total}


def compute(resolution: Resolution, conditions: EvalConditions | None, benchmark_version: str, metric: str,
            subset: str | None) -> Comparability:
    """04 S8's three numbers for one claim. `conditions` None is a claim with no condition record:
    every material field is unknown."""
    tup: list[Any] = [benchmark_version, metric, subset]
    unknown = []
    for f in resolution.material:                                   # already sorted
        if conditions is not None and conditions.answered(f):
            tup.append(canonicalise(conditions.value(f)))           # an answered absence is JSON null
        else:
            tup.append(UNKNOWN)
            unknown.append(f)
    key = hashlib.sha256(json.dumps(tup, separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
    total = sum(resolution.weights[f] for f in resolution.material)
    answered = sum(resolution.weights[f] for f in resolution.material if f not in unknown)
    return Comparability(
        comparability_key=key, key_unknown_count=tup.count(UNKNOWN),
        condition_completeness=(answered / total) if total else None,
        unknown_fields=tuple(unknown), fields_material_total=resolution.fields_material_total)


def compute_for_claim(claim: ResultClaim, resolution: Resolution, conditions: EvalConditions | None) -> Comparability:
    return compute(resolution, conditions, claim.benchmark, claim.metric, claim.subset)


def build(root: str = ROOT) -> dict:
    pf = load_profiles(os.path.join(root, 'taxonomy', 'comparability-profiles.yaml'))
    benchmarks = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'benchmarks', '**', '*.yaml'), recursive=True)):
        b = load_benchmark(path)
        benchmarks[b.id] = resolve_profile(b, pf)
    conditions = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'conditions', '**', '*.yaml'), recursive=True)):
        c = EvalConditions.model_validate(read_yaml(path))
        conditions[c.id] = c
    claims = {}
    for path in sorted(glob.glob(os.path.join(root, 'data', 'claims', '**', '*.yaml'), recursive=True)):
        cl = ResultClaim.model_validate(read_yaml(path))
        bench = cl.benchmark.split('@')[0]
        if bench not in benchmarks:
            raise ValueError('%s: benchmark %s has no record' % (cl.id, bench))
        if cl.eval_conditions is not None and cl.eval_conditions not in conditions:
            raise ValueError('%s: eval_conditions %s has no record' % (cl.id, cl.eval_conditions))
        cond = conditions.get(cl.eval_conditions) if cl.eval_conditions else None
        claims[cl.id] = compute_for_claim(cl, benchmarks[bench], cond).as_dict()
    return {'profiles': {k: v.as_dict() for k, v in benchmarks.items()}, 'claims': claims}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--root', default=ROOT)
    p.add_argument('--out')
    a = p.parse_args(argv)
    text = json.dumps(build(a.root), indent=2, sort_keys=True) + '\n'
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
