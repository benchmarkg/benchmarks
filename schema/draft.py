"""The curation copilot's drafts (P1-S2-T01; 11-ai-features.md S F6, S G4; 05 S4).

    drafts/benchmarks/<id>.yaml     a BenchmarkDraft
    drafts/sources/<src-id>.yaml    a SourceDraft: the snapshot every quote in the draft is checked against

A draft is not a Benchmark with gaps papered over. 11 S F6: "Fields with no supporting quote are
pre-set to `null`, never guessed." A Benchmark cannot say that, because some of its required fields
are enums with no null (`evaluation_target`, `data.access`), and `bench new` has to put a STUB VALUE
there. So a draft has its own model, identical to Benchmark except that:

  - the fields a stub has to guess are nullable, and so are the defaults that would otherwise assert
    something no source said (`lifecycle: active`, `aggregation_policy: official-aggregate`,
    `data.ceiling_anchor_type: none-known`);
  - `curation.verification_status` is `ai-drafted-unverified` and nothing else, and
    `curation.last_verified` is null, because nobody has opened the sources yet;
  - `provenance` is required, and it states the evidence for every field the copilot drafts.

DRAFT_FIELDS is that field set, and it is a contract, checked here and not only in the copilot:

  1. the record holds no field outside DRAFT_FIELDS, apart from its id, curation and provenance and
     the source/quote/date slots of the drafted blocks;
  2. every DRAFT_FIELDS field has an evidence row in `provenance.fields` (a multi-valued facet has one
     row per term, or one `absent` row when it is empty), so `confidence` is stated for every field;
  3. a populated field's row carries a source and a verbatim quote, and an `absent` row's field is
     null: "a quote on every populated field" is a property of every valid draft;
  4. every evidence source is one of the draft's `curation.sources`;
  5. every value the copilot refused is in `provenance.rejected`, with the quote it claimed and the
     reason (P1-S2-T02), and a refused single-valued field is null: a rejection is never beside a value.

That the quote is a substring of the source's snapshot needs the SourceDraft, so it is tier 3's
quote-substring rule (tools/validate/tiers.py runs it over drafts/), not this model's. The copilot
checks it before it writes anything, so a mismatch means the file was edited afterwards.

A SourceDraft is a Source that has not been archived yet: 04 S12 requires every non-DOI Source in
data/ to carry an `archive_url`, and a snapshot taken a moment ago has none. The requirement comes
back when the source is promoted into data/sources/.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field, model_validator

from schema.benchmark import (AggregationPolicy, Access, Benchmark, CeilingAnchor, Curation, Data, Domain,
                              DomainLeaf, EvaluationTarget, LearnedEntrantEvidence, Lifecycle, Text, Url)
from schema.source import Source, Text as SourceText

# path -> kind. `terms` is a multi-valued facet (one evidence row per term); `count` and `entrant`
# are blocks that carry their own source and quote as well (schema/benchmark.py's Count and
# LearnedEntrantEvidence), which must agree with the evidence row.
DRAFT_FIELDS: dict[str, str] = {
    'name': 'verbatim',
    'tagline': 'prose',
    'description': 'prose',
    'paper.title': 'verbatim',
    'external_ids.arxiv': 'verbatim',
    'released': 'date',
    'domain.primary': 'enum',
    'domain.secondary': 'terms',
    'capability': 'terms',
    'evaluation_method': 'terms',
    'designed_for_subjects': 'terms',
    'evaluation_target': 'enum',
    'learned_entrant_evidence': 'entrant',
    'task.output': 'prose',
    'task.scoring': 'prose',
    'data.access': 'enum',
    'data.size.n_items': 'count',
    'data.dataset_licence': 'verbatim',
    'governance.maintainer': 'verbatim',
    'homepage': 'url',
    'repository': 'url',
    'leaderboard_url': 'url',
    'dataset_url': 'url',
    'license': 'verbatim',
}
# Slots that are not claims of their own. The `count` and `entrant` blocks are leaves here: their
# source, quote, unit and observed_on are typed by their own models.
STRUCTURAL = {'id', 'curation', 'provenance', 'paper.source'}


def _allowed() -> dict:
    tree: dict = {}
    for path in list(DRAFT_FIELDS) + sorted(STRUCTURAL):
        node = tree
        parts = path.split('.')
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node.setdefault(parts[-1], None)
    return tree


ALLOWED = _allowed()


def _stray(raw: Any, tree: dict, at: str = '') -> list[str]:
    if not isinstance(raw, dict):
        return []
    out = []
    for k, v in raw.items():
        path = '%s.%s' % (at, k) if at else str(k)
        if k not in tree:
            out.append(path)
        elif isinstance(tree[k], dict):
            out += _stray(v, tree[k], path)
    return out


def body_value(record: Benchmark, path: str) -> Any:
    """The value at a dotted path, None where any step is missing."""
    node: Any = record
    for p in path.split('.'):
        node = getattr(node, p, None)
        if node is None:
            return None
    return node


def empty(value: Any) -> bool:
    return value is None or value == [] or value == ''


class DraftDomain(Domain):
    primary: DomainLeaf | None = None


class DraftData(Data):
    access: Access | None = None
    ceiling_anchor_type: CeilingAnchor | None = None


class DraftCuration(Curation):
    verification_status: Literal['ai-drafted-unverified'] = 'ai-drafted-unverified'
    last_verified: date | None = None


class BenchmarkDraft(Benchmark):
    """A copilot draft: Benchmark with every guessed field nullable, and the evidence contract above."""
    name: Text | None = None
    tagline: Text | None = None
    domain: DraftDomain = Field(default_factory=DraftDomain)
    lifecycle: Lifecycle | None = None
    learned_entrant_evidence: list[LearnedEntrantEvidence] = Field(default_factory=list)
    evaluation_target: EvaluationTarget | None = None
    data: DraftData = Field(default_factory=DraftData)
    aggregation_policy: AggregationPolicy | None = None
    homepage: Url | None = None
    curation: DraftCuration

    @model_validator(mode='before')
    @classmethod
    def _only_drafted_fields(cls, data):
        stray = _stray(data, ALLOWED)
        if stray:
            raise ValueError('a draft holds only the fields the copilot drafts (schema/draft.py DRAFT_FIELDS), '
                             'and this one also holds: %s' % ', '.join(sorted(stray)))
        if isinstance(data, dict) and not isinstance(data.get('provenance'), dict):
            raise ValueError('a draft carries its provenance block (11 S F6)')
        return data

    @model_validator(mode='after')
    def _evidence(self):
        rows: dict[str, list] = {}
        for e in self.provenance.fields:
            if e.field not in DRAFT_FIELDS:
                raise ValueError('provenance.fields: %s is not a drafted field' % e.field)
            rows.setdefault(e.field, []).append(e)
        sources = set(self.curation.source_ids())
        for e in self.provenance.fields:
            if e.source is not None and e.source not in sources:
                raise ValueError('provenance.fields: %s cites %s, which is not in curation.sources' % (e.field, e.source))
        missing = [f for f in DRAFT_FIELDS if f not in rows]
        if missing:
            raise ValueError('provenance.fields states no confidence for: %s' % ', '.join(missing))
        for path, kind in DRAFT_FIELDS.items():
            value, got = body_value(self, path), rows[path]
            if kind == 'terms':
                self._terms(path, value or [], got)
                continue
            if len(got) != 1:
                raise ValueError('provenance.fields: %s has %d rows; a single-valued field has one' % (path, len(got)))
            e = got[0]
            if e.term is not None:
                raise ValueError('provenance.fields: %s is single-valued and takes no term' % path)
            if kind == 'entrant' and value and len(value) != 1:
                raise ValueError('learned_entrant_evidence: a draft names one entrant, the one its row quotes')
            if e.confidence == 'absent' and not empty(value):
                raise ValueError('%s holds a value, but its evidence is absent: an unquoted field is null' % path)
            if e.confidence != 'absent' and empty(value):
                raise ValueError('%s is null, but its evidence row says %s' % (path, e.confidence))
            inline = value[0] if kind == 'entrant' and value else value if kind == 'count' else None
            if inline is not None and (inline.source, inline.quote) != (e.source, e.quote):
                raise ValueError('%s: the block\'s source and quote differ from its evidence row' % path)
        for r in self.provenance.rejected:
            if r.field not in DRAFT_FIELDS:
                raise ValueError('provenance.rejected: %s is not a drafted field' % r.field)
            if DRAFT_FIELDS[r.field] != 'terms' and rows[r.field][0].confidence != 'absent':
                raise ValueError('provenance.rejected: %s was rejected, so its value is null and its evidence '
                                 'absent (a single-valued field has one offered value)' % r.field)
            if DRAFT_FIELDS[r.field] == 'terms' and r.term is None:
                raise ValueError('provenance.rejected: a rejection on %s names the term refused' % r.field)
        return self

    @staticmethod
    def _terms(path: str, value: list, got: list):
        if not value:
            if len(got) != 1 or got[0].confidence != 'absent':
                raise ValueError('%s is empty, so its evidence is one absent row' % path)
            return
        terms = [e.term for e in got]
        if any(e.confidence == 'absent' for e in got) or len(set(terms)) != len(terms) or set(terms) != set(value):
            raise ValueError('%s: one quoted evidence row per assigned term (rows %s, terms %s)'
                             % (path, sorted(map(str, terms)), sorted(value)))


class SourceDraft(Source):
    """A snapshot the copilot took, not yet archived; drafted_by says so."""
    drafted_by: SourceText
    quote_extract: str

    @model_validator(mode='after')
    def _archive(self):
        if self.archive_status not in ('pending', 'failed'):
            raise ValueError('%s: a draft source is not archived yet; archive_status is pending (or failed)' % self.id)
        return self
