"""Dotted field paths on the Pydantic models (P0-S4-T09, moved here by P0-S4-T10).

`resolve('EvalConditions.sampling.temperature')` walks the models themselves -- from a root entity,
through nested models, lists and optionals, to a declared or computed field -- and returns the
field's annotation, or raises Unresolved naming the first segment that does not exist. A trailing
`[]` on a segment is accepted and ignored. It reads the models, never the generated JSON Schema.

Used by tests/test_crosswalks.py, which resolves every `ours:` key in taxonomy/crosswalks/, and by
the check that docs/schema-field-needs.md's resolutions name real fields.
"""
from __future__ import annotations

import typing

from pydantic import BaseModel

from schema.baseline import Baseline
from schema.benchmark import Benchmark
from schema.claim import ResultClaim
from schema.conditions import EvalConditions
from schema.dispute import Dispute
from schema.entities import Alias, BenchmarkVersion, IngestBatch, Leaderboard, Organization, RatingPool, Subset
from schema.metric import Metric
from schema.source import Source
from schema.system import System, SystemVersion

ENTITIES: dict[str, type[BaseModel]] = {
    m.__name__: m for m in (Alias, Baseline, Benchmark, BenchmarkVersion, Dispute, EvalConditions, IngestBatch,
                            Leaderboard, Metric, Organization, RatingPool, ResultClaim, Source, Subset, System,
                            SystemVersion)}


class Unresolved(LookupError):
    pass


def type_args(tp) -> list:
    """Every type inside an annotation: through Optional, Union, list, dict values and Annotated."""
    origin = typing.get_origin(tp)
    if origin is typing.Annotated:
        return type_args(typing.get_args(tp)[0])
    if origin is None or origin is typing.Literal:
        return [tp]
    out = []
    for a in typing.get_args(tp):
        out += type_args(a)
    return out


def resolve(path: str):
    """The annotation at `path`, or Unresolved naming the first segment that does not exist."""
    root, *segments = path.split('.')
    if root not in ENTITIES or not segments:
        raise Unresolved('%s: no entity %s' % (path, root))
    models = [ENTITIES[root]]
    annotation = None
    for i, seg in enumerate(segments):
        name = seg[:-2] if seg.endswith('[]') else seg
        hit = None
        for m in models:
            if name in m.model_fields:
                hit = m.model_fields[name].annotation
            elif name in m.model_computed_fields:
                hit = m.model_computed_fields[name].return_type
            if hit is not None:
                break
        if hit is None:
            raise Unresolved('%s: %s has no field %s' % (path, '.'.join([root] + segments[:i]) or root, name))
        annotation = hit
        models = [a for a in type_args(hit) if isinstance(a, type) and issubclass(a, BaseModel)]
        if i < len(segments) - 1 and not models:
            raise Unresolved('%s: %s is not a nested model' % (path, name))
    return annotation


def vocabulary(annotation) -> set[str] | None:
    """The Literal values a field accepts, or None when it is not a closed vocabulary."""
    values = [v for a in type_args(annotation) if typing.get_origin(a) is typing.Literal for v in typing.get_args(a)]
    return set(values) if values else None
