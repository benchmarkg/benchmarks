"""The quote-substring validator (P0-S5-T06; 14-roadmap Phase 0, 04 S9, 05 S4).

14-roadmap: "Every AI-drafted field carries a sibling `quote` string. The validator requires that
`quote` be an exact substring of the archived source snapshot for that field's source -- not the
live page, the snapshot, so the check is reproducible at any commit. A quote that does not match
fails validation and the field is set to `null`."

The snapshot is the Source record's committed `quote_extract` (04 S9), so the check reads files at a
commit and never the network. Both sides go through schema/source.py's one normalisation --
`quote_found()` folds the quote and the extract identically -- because 04 S9 warns that two
normalisations make "the check silently pass on everything".

Where a quote is, and which source it is checked against. The entries write quotes two ways:

  - a block quote: a mapping with `quote` and `source` (a Count, an Evidence, a Basis, a
    learned-entrant row). The quote supports the whole mapping, which is the field nulled;
  - an annotation: `<field>_quote` beside `<field>` in a Block, with the source in
    `<field>_source` or else the mapping's own `source`. The quote supports `<field>`.

A quote with no source, a source with no record, and a source with no `quote_extract` all fail: 04
S9 says a source with no extract "may not be quoted, only cited", and a check that passes when it
had nothing to compare against is the failure it names.

Nulling (`apply`). "Null" means the slot: a mapping value becomes null and a list item is removed.
Where that leaves the record invalid -- a required `n_items`, a `min_length=1` list -- the enclosing
slot is nulled instead, and so on up, so the record as a whole still validates; the reason goes
into `curation.notes`. A quote whose every enclosing slot is required cannot be nulled, and says
so. `apply` never touches the file; the curation copilot (11 S F6) is what writes its output.

In tier 3 (schema/validators.py, rule `quote-substring`) the same check runs over every benchmark.
For an ai-drafted-unverified record the finding is a warning offering the null as its auto-fix --
the record does not fail, the field does. For a record a human has reviewed, an unmatched quote is
blocking: an automatic null would hide a curation error rather than contain a model's guess.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from schema.source import quote_found

SUFFIX = '_quote'
NOTES = ('curation', 'notes')


@dataclass(frozen=True)
class Quote:
    at: tuple                   # the mapping that holds the quote key, as keys and list indices
    key: str                    # 'quote' or '<field>_quote'
    source: str | None
    text: str

    @property
    def field(self) -> tuple:
        """The slot the quote supports."""
        return self.at if self.key == 'quote' else self.at + (self.key[:-len(SUFFIX)],)


@dataclass(frozen=True)
class Result:
    quote: Quote
    reason: str
    nulled: tuple | None        # the slot set to null or removed; None when none could be


def dotted(path: tuple) -> str:
    out = ''
    for p in path:
        out += '[%d]' % p if isinstance(p, int) else ('.' if out else '') + str(p)
    return out or '<record>'


def find(record: Any, at: tuple = ()) -> list[Quote]:
    """Every quote in a record, in document order."""
    out = []
    if isinstance(record, dict):
        for k, v in record.items():
            if isinstance(k, str) and isinstance(v, str) and (k == 'quote' or k.endswith(SUFFIX)):
                own = record.get(k[:-len(SUFFIX)] + '_source') if k != 'quote' else None
                src = own if isinstance(own, str) else record.get('source')
                out.append(Quote(at, k, src if isinstance(src, str) else None, v))
            out += find(v, at + (k,))
    elif isinstance(record, list):
        for i, v in enumerate(record):
            out += find(v, at + (i,))
    return out


def reason(q: Quote, sources: dict[str, dict]) -> str | None:
    """Why the quote fails, or None when it is a substring of its source's snapshot."""
    if q.source is None:
        return 'the quote names no source, so there is no snapshot to check it against'
    src = sources.get(q.source)
    if not isinstance(src, dict):
        return 'it cites %s, which has no Source record' % q.source
    extract = src.get('quote_extract')
    if not isinstance(extract, str) or not extract:
        return ('%s has no quote_extract, and a source with no committed snapshot may be cited, not quoted (04 S9)'
                % q.source)
    if not quote_found(q.text, extract):
        return 'the quote is not a substring of the snapshot of %s (quote_extract, normalised as 04 S9 fixes)' % q.source
    return None


def check(record: dict, sources: dict[str, dict]) -> list[tuple[Quote, str]]:
    return [(q, r) for q in find(record) for r in [reason(q, sources)] if r is not None]


# ---- nulling ------------------------------------------------------------------------------------

def _get(record, path):
    for p in path:
        if isinstance(p, int):
            if not isinstance(record, list) or p >= len(record):
                raise KeyError(p)
        elif not isinstance(record, dict) or p not in record:
            raise KeyError(p)
        record = record[p]
    return record


def _clear(record, slot):
    parent = _get(record, slot[:-1])
    if isinstance(slot[-1], int):
        del parent[slot[-1]]
    else:
        parent[slot[-1]] = None


def _valid(model, record) -> bool:
    try:
        model.model_validate(record)
        return True
    except ValueError:                  # pydantic's ValidationError is a ValueError
        return False


def apply(record: dict, sources: dict[str, dict], model=None) -> tuple[dict, list[Result]]:
    """The record with every unmatched quote's field nulled and the reasons in curation.notes."""
    if model is None:
        from schema.benchmark import Benchmark as model
    fixed = copy.deepcopy(record)
    was_valid = _valid(model, record)
    results = []
    for q, why in reversed(check(record, sources)):     # later first, so a removal shifts no pending index
        enclosing = [r.nulled for r in results if r.nulled is not None and q.field[:len(r.nulled)] == r.nulled]
        if enclosing:                                   # another quote's null already took this field with it
            results.append(Result(q, why, enclosing[0]))
            continue
        slot, nulled = q.field, None
        while slot:
            candidate = copy.deepcopy(fixed)
            _clear(candidate, slot)
            if q.key != 'quote' and slot == q.field:
                del _get(candidate, q.at)[q.key]
            if not was_valid or _valid(model, candidate):
                fixed, nulled = candidate, slot
                break
            slot = slot[:-1]
        if nulled is None:
            why += '; it cannot be nulled, because every field enclosing %s is required' % dotted(q.field)
        results.append(Result(q, why, nulled))
    results.reverse()
    outer = [r.nulled for r in results if r.nulled is not None]
    results = [Result(r.quote, r.reason, min((o for o in outer if r.nulled[:len(o)] == o), key=len))
               if r.nulled is not None else r for r in results]     # a later walk-up may have taken this one too
    lines =['quote-substring: %s %s: %s' % (dotted(r.nulled), 'set to null' if not isinstance(r.nulled[-1], int)
                                              else 'removed', r.reason)
             for r in results if r.nulled is not None]
    if lines:
        curation = _get(fixed, NOTES[:-1])
        curation[NOTES[-1]] = '\n'.join(([curation[NOTES[-1]]] if curation.get(NOTES[-1]) else []) + lines)
    return fixed, results
