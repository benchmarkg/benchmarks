"""The mapping stanza and its loader (P3-S2-T02; 07 S2.1, S8).

One stanza per upstream file, at ingest/mappings/<adapter>/<file stem>.yaml, says how that file's rows
become claims: which column holds the score, at what scale, against which metric, with what uncertainty
and conditions. 07 S2: "there is no generic CSV parser for this source" -- Epoch's 80 files carry 62
header signatures, a score in dollars, one in minutes, an Elo and a 0-10 scale -- so each file is mapped
by hand, once, and the adapter reads only what the stanza says.

The rule this module exists for (07 S8, the unit guard): "A claim whose mapping stanza has no explicit
`scale` is refused. There is no default." `scale` is a required field with no default, so a stanza that
leaves it out never loads; it is not read as 1.0. `scale_source` says where the number came from:
Epoch's benchmark_metadata.csv for the 59 files it covers, or the URL a person read it off for the 21
orphans (P3-S2-T03, P3-S2-T04).

    from ingest.mappings.schema import load_mapping
    stanza = load_mapping('epoch', 'csv:swe_bench_verified')   # None: no stanza yet -> Unresolved
"""
from __future__ import annotations

import os
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPPINGS = os.path.join(ROOT, 'ingest', 'mappings')

# 07 S2.2: "scale in {1.0, 0.01, 0.1}; NEVER defaulted". A percentage column is 0.01, a 0-10 column read
# as a fraction 0.1, everything else 1.0 -- including a dollar, minute or Elo column, whose metric is
# unbounded (P3-S2-T05) rather than rescaled.
SCALES = (1.0, 0.1, 0.01)
METADATA = 'benchmark_metadata.csv'

# A benchmark id with the version (@) or subset (#) the allocation names (ingest/mappings/epoch/_id_allocation.yaml).
BenchmarkRef = Annotated[str, StringConstraints(
    pattern=r'^[a-z0-9][a-z0-9-]{1,62}(@[a-z0-9][a-z0-9._-]*)?(#[a-z0-9][a-z0-9._-]*)?$')]
MetricId = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{1,62}$')]
SourceId = Annotated[str, StringConstraints(pattern=r'^src-[a-z0-9]+(-[a-z0-9]+)*$')]
Column = Annotated[str, StringConstraints(min_length=1)]          # a header, verbatim, spaces and all


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class Uncertainty(Closed):
    column: Column
    type: Literal['stderr', 'stddev', 'ci95-half-width']


class Artifact(Closed):
    log_column: Column | None = None                 # -> ResultClaim.artifact_url
    viewer_column: Column | None = None


class ConditionRule(Closed):
    """Where one EvalConditions field comes from: a rule (`from`), or a constant the file implies."""
    from_: Literal['model_version_suffix', 'column'] | None = Field(default=None, alias='from')
    column: Column | None = None                     # with from: column
    const: Any = None
    k: int | None = Field(default=None, ge=1)        # selection_strategy's k, where the strategy needs one

    @model_validator(mode='after')
    def _one_source(self):
        if (self.from_ is None) == (self.const is None):
            raise ValueError('a condition is either `from` a rule or a `const`, exactly one')
        if (self.from_ == 'column') != (self.column is not None):
            raise ValueError('`column` goes with `from: column`, and only with it')
        return self


class Stanza(Closed):
    benchmark_ref: BenchmarkRef                      # allocated by a person, once; never by the adapter
    family: Literal['epoch-run', 'external-scrape']  # decides the verification rule (07 S2.3)
    score_column: Column
    # REQUIRED, no default (07 S8, the unit guard); strict, so `true` or the string '1.0' is not read as 1.0
    scale: Annotated[float, Field(strict=True)]
    scale_source: Annotated[str, StringConstraints(min_length=1)]
    metric_ref: MetricId
    source_ref: SourceId
    uncertainty: Uncertainty | None = None
    artifact: Artifact | None = None
    date_column: Column | None = None
    conditions: dict[str, ConditionRule] = Field(default_factory=dict)
    reviewed_by: str | None = None                   # who checked the score column (P3-S2-T03)
    notes: str | None = None

    @field_validator('scale')
    @classmethod
    def _scale(cls, v: float) -> float:
        if v not in SCALES:
            raise ValueError('scale %r is not one of %s (07 S2.2)' % (v, ', '.join(map(str, SCALES))))
        return v

    @field_validator('scale_source')
    @classmethod
    def _scale_source(cls, v: str) -> str:
        if v != METADATA and not v.startswith(('https://', 'http://')):
            raise ValueError('scale_source is %s or the URL the scale was read from, not %r' % (METADATA, v))
        return v

    @field_validator('conditions')
    @classmethod
    def _condition_fields(cls, v: dict) -> dict:
        from schema.conditions import FIELDS
        unknown = sorted(set(v) - set(FIELDS))
        if unknown:
            raise ValueError('not EvalConditions fields: %s' % ', '.join(unknown))
        return v


class MappingError(ValueError):
    """A stanza exists and does not load. A hard fail: a wrong stanza is worse than a missing one."""


def stanza_path(adapter: str, source_key: str, root: str = MAPPINGS) -> str:
    """The file a candidate's stanza lives in: `csv:<stem>` -> <root>/<adapter>/<stem>.yaml."""
    kind, _, stem = source_key.partition(':')
    if kind != 'csv' or not stem or '/' in stem or stem.startswith('_'):
        raise MappingError('%s has no stanza: only a csv:<file stem> candidate is mapped' % source_key)
    return os.path.join(root, adapter, stem + '.yaml')


def read(path: str) -> Stanza:
    """One stanza file, validated. Any failure names the file."""
    from ruamel.yaml import YAML
    try:
        with open(path, encoding='utf-8') as f:
            doc = YAML(typ='safe', pure=True).load(f)
        return Stanza.model_validate(doc)
    except ValidationError as e:
        raise MappingError('%s: %s' % (path, ' '.join(str(e).split()))) from None
    except Exception as e:                          # ruamel's several error types, or a non-mapping file
        raise MappingError('%s: %s: %s' % (path, type(e).__name__, e)) from None


def load_mapping(adapter: str, source_key: str, root: str = MAPPINGS) -> Stanza | None:
    """The stanza for one candidate, or None when there is none yet (the adapter records an Unresolved
    asking for it). A stanza that exists but does not validate -- one that omits `scale`, say -- raises
    MappingError: it is never read with a default."""
    path = stanza_path(adapter, source_key, root)
    return read(path) if os.path.exists(path) else None


def load_all(adapter: str, root: str = MAPPINGS) -> dict[str, Stanza]:
    """Every stanza an adapter has, by source_key. Files whose names start with `_` (the id allocation)
    are not stanzas. Any invalid stanza raises."""
    folder = os.path.join(root, adapter)
    if not os.path.isdir(folder):
        return {}
    return {'csv:' + n[:-5]: read(os.path.join(folder, n))
            for n in sorted(os.listdir(folder)) if n.endswith('.yaml') and not n.startswith('_')}
