"""The gates 07 S8 adds to the Phase-3 six (P5-S2-T05): schema, referential, caps, metadata-only,
attribution, licence firewall and round-trip determinism.

Each takes a document -- a draft as it would be written: its payload, with the `ingestion` block in it --
and its repository-relative path, and raises GateError (or returns Unresolved, for the one that drops a
row) exactly as the six in numeric.py and record.py do. ingest/gates/__init__.py runs them all.

The schema and referential gates judge a draft exactly as `bench validate` judges the committed file:
through tools/validate/tiers.py's record model, the entity model its path names, and its reference index
built over the tree plus the run's own drafts. A draft is never held to a different rule from the file it
becomes.
"""
from __future__ import annotations

import gzip
import io
import os
from collections import Counter

from ingest.adapters.base import Unresolved
from ingest.gates._common import ROOT, GateError

DISCOVERY = 'data/_discovery/'
DISCOVERY_KEYS = ('candidate_id', 'discovered_via', 'discovered_at', 'identity', '_suggested')


# ---- schema ------------------------------------------------------------------------------------------------

def schema(doc, rel: str) -> None:
    """07 S8: "Pydantic v2 validation of every draft against the canonical models". The model is the one
    05 S2 stores at that path. A discovery candidate has no entity model -- it is 06 S1.1's shape, never
    published -- and is held to that shape. Any other path no kind lives at is refused: an adapter does
    not write where nothing is modelled."""
    from tools.validate import tiers as T
    anchored = T.anchor(rel)
    if anchored.startswith(DISCOVERY):
        missing = [k for k in DISCOVERY_KEYS if not isinstance(doc, dict) or k not in doc]
        if missing or not isinstance(doc['_suggested'], list):
            raise GateError('schema', '%s: a discovery candidate lacks %s (06 S1.1)'
                            % (rel, ', '.join(missing) or '_suggested as a list'))
        return
    kind = T.kind_of(anchored)
    if kind is None:
        raise GateError('schema', '%s: no entity kind is stored at this path (05 S2); an adapter never writes '
                        'there' % rel)
    from pydantic import ValidationError
    try:
        kind.model.model_validate(doc)
    except ValidationError as e:
        raise GateError('schema', '%s: %s' % (rel, ' '.join(str(e).split())[:400])) from None


# ---- referential --------------------------------------------------------------------------------------------

class Tree:
    """The corpus a run's drafts are judged against, read once per run and only when a gate needs it."""

    def __init__(self, root: str = ROOT):
        self.root = root
        self._records = self._taxonomy = None

    @property
    def records(self):
        if self._records is None:
            from tools.validate import tiers as T
            self._records = T.load(self.root)
        return self._records

    @property
    def taxonomy(self):
        if self._taxonomy is None:
            from tools.validate import tiers as T
            self._taxonomy = T._taxonomy(self.root)
        return self._taxonomy

    def counts(self) -> Counter:
        """Files by kind: the `existing_files_of_that_type` 07 S8.1's caps scale with. Classified by path
        alone, as tools/validate does, so counting does not parse the corpus."""
        from tools.validate import tiers as T
        kinds = (T.kind_of(T.anchor(rel)) for rel in T.discover(self.root))
        return Counter(k.name for k in kinds if k is not None)


def _record(doc, rel: str):
    from tools.validate import tiers as T
    anchored = T.anchor(rel)
    return T.Record(rel, anchored, T.kind_of(anchored), raw=doc, parsed=True)


def referential(docs: list[tuple[str, dict]], tree: Tree, batch: str | None = None) -> list[tuple[str, Unresolved]]:
    """07 S8: every reference resolves to an existing file, and every taxonomy value is in the vocabulary.
    "Unresolvable refs become Unresolved records and the dependent record is dropped, not stubbed": so this
    returns (path, Unresolved) for each draft to drop, and a draft may resolve against another draft of
    the same run. `batch` is the IngestBatch the run itself writes (04 S9): the one batch id a draft may name
    before its file exists. Discovery candidates carry no references to check."""
    from tools.validate import tiers as T
    drafts = [_record(doc, rel) for rel, doc in docs if not T.anchor(rel).startswith(DISCOVERY)]
    if not drafts:
        return []
    ix = T.index(list(tree.records) + drafts)
    if batch:
        ix.add('batch', batch, '(this run)')
    out, seen = [], set()
    for f in T.ref_tier(drafts, ix, tree.taxonomy):
        if f.rule == 'duplicate-id' and f.path not in {d.path for d in drafts}:
            continue
        if (f.path, f.message) in seen:
            continue
        seen.add((f.path, f.message))
        out.append((f.path, Unresolved(source_key=f.path, field=f.message.split(':', 1)[0], observed=f.message,
                                       reason='no-match', human_task='%s. Add the referenced record or an alias, '
                                       'then re-run; the draft was dropped, not stubbed (07 S8).' % f.message)))
    return out


# ---- caps (07 S8.1) -------------------------------------------------------------------------------------------

CAP_ROWS = {                 # entity type -> (floor, ceiling), 07 S8.1's table
    'claim': (50, 200), 'benchmark': (10, 25), 'system': (25, 100), 'organization': (5, 25),
    'metric': (5, 20), 'source': (50, 200), 'conditions': (50, 200),
    'leaderboard': (10, 25),  # not in 07's table: a leaderboard arrives as its benchmark does, so it takes that row
}
CAP_FRACTION = 0.25


def cap_for(entity_type: str, existing: int) -> int:
    """`cap = max(floor, min(ceiling, 0.25 x existing_files_of_that_type))` (07 S8.1). A type with no row
    has no cap to apply, which is refused rather than read as unlimited."""
    if entity_type not in CAP_ROWS:
        raise GateError('caps', '%s has no row in 07 S8.1\'s cap table; add one before drafting it' % entity_type)
    floor, ceiling = CAP_ROWS[entity_type]
    return max(floor, min(ceiling, int(CAP_FRACTION * existing)))


def caps(by_type: Counter, existing: Counter, allow_bulk: bool = False) -> list[str]:
    """`<type> <n> > <cap>` for every type over its cap; empty when within. --allow-bulk lifts them: the
    first Epoch run, "by hand, once" (07 S8.1)."""
    if allow_bulk:
        return []
    over = []
    for t, n in sorted(by_type.items()):
        cap = cap_for(t, existing[t])
        if n > cap:
            over.append('%s %d > %d' % (t, n, cap))
    return over


# ---- metadata-only ----------------------------------------------------------------------------------------------

MAX_PROSE = 280               # 07 S8: "any single YAML string field over 280 characters of copied prose"
MAGIC = (                     # 07 S8's list: a data file, not metadata
    (b'PAR1', 'Parquet'), (b'ARROW1', 'Arrow'), (b'SQLite format 3\x00', 'SQLite'),
    (b'PK\x03\x04', 'ZIP'), (b'\x1f\x8b', 'gzip'),
)


def sniff(data: bytes) -> str | None:
    """The data format `data` is, after decompressing one gzip layer, or None for text. `results.parquet.gz`
    sails past an extension check; this opens it (07 S4.4, "it does not match extensions")."""
    if data[:2] == b'\x1f\x8b':
        try:
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read(64)
        except (OSError, EOFError):
            return 'gzip'
    for magic, name in MAGIC:
        if data.startswith(magic):
            return name
    return None


def metadata_only(doc, rel: str) -> None:
    """No string in the draft is longer than MAX_PROSE: a field that long is copied prose, not metadata."""
    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                yield from walk(v, '%s.%s' % (where, k) if where else str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                yield from walk(v, '%s[%d]' % (where, i))
        elif isinstance(x, str) and len(x) > MAX_PROSE:
            yield where, len(x)
    long = list(walk(doc, ''))
    if long:
        raise GateError('metadata-only', '%s: %s over %d characters of copied prose (hard constraint 1)'
                        % (rel, ', '.join('%s is %d' % w for w in long), MAX_PROSE))


def metadata_only_files(paths: list[str], root: str = ROOT) -> None:
    """07 S8: sniff every file a run writes under data/ or keeps under ingest/raw/; a data format refuses."""
    bad = []
    for p in paths:
        with open(os.path.join(root, p), 'rb') as f:
            fmt = sniff(f.read(4096))
        if fmt:
            bad.append('%s is %s' % (p, fmt))
    if bad:
        raise GateError('metadata-only', '; '.join(bad) + ': the index links to data and never hosts it')


# ---- attribution -------------------------------------------------------------------------------------------------

def attribution(doc, rel: str, credit: str) -> None:
    """07 S8: "The adapter's attribution string is present on every record". The record's
    ingestion.source_attribution must carry the adapter's credit line. (The other half, docs/attribution.md
    regenerating cleanly, is P4-S7-T04's generator's check: the file does not exist yet.)"""
    if not credit:
        raise GateError('attribution', 'the adapter declares no attribution to carry')
    block = doc.get('ingestion') if isinstance(doc, dict) else None    # get-default: absent is refused below
    said = block.get('source_attribution') if isinstance(block, dict) else None  # get-default: as above
    if not isinstance(said, str) or credit not in said:
        raise GateError('attribution', '%s: ingestion.source_attribution %r does not carry the credit line %r'
                        % (rel, said, credit))


# ---- licence firewall (04 S9) -----------------------------------------------------------------------------------

FIREWALL = {                  # licence class -> where its records may live (04 S9's table)
    'permissive-attribution': ('data/',),
    'share-alike': ('vendor/pwc-archive/',),
    'non-commercial': (),
    'no-redistribution': (),
    'unlicensed': (),
}


def licence_firewall(doc, rel: str, default_class: str) -> None:
    """04 S9: a record lives only where its licence class is allowed. The record's own class wins over the
    adapter's (hf-hub classes each dataset by its own licence tag). A discovery candidate is the one
    exception: data/_discovery/ is never published, built or counted (06 S1.1), and holds join keys and
    suggestions, not a copied record -- the metadata-only gate holds it to that."""
    from tools.validate import tiers as T
    anchored = T.anchor(rel)
    if anchored.startswith(DISCOVERY):
        return
    block = doc.get('ingestion') if isinstance(doc, dict) else None    # get-default: a curated record has none
    cls = (block.get('licence_class') if isinstance(block, dict) else None) or default_class  # get-default: as above
    if cls not in FIREWALL:
        raise GateError('licence-firewall', '%s: licence class %r is not one of 04 S9\'s' % (rel, cls))
    if not anchored.startswith(FIREWALL[cls]):
        where = ', '.join(FIREWALL[cls]) or 'nowhere'
        raise GateError('licence-firewall', '%s: a %s record may live only in %s (04 S9)' % (rel, cls, where))


def raw_retention(retainable: bool, licence_class: str, files: list[str]) -> None:
    """07 S4.4, the firewall's other half: a source whose licence bars keeping its body keeps none in the
    raw store, whatever the adapter class claims."""
    if files and (not retainable or licence_class != 'permissive-attribution'):
        raise GateError('licence-firewall', 'a %s source may keep no raw body (07 S4.4); refused: %s'
                        % (licence_class, ', '.join(files)))


# ---- round-trip determinism -------------------------------------------------------------------------------------

def round_trip(doc, rel: str) -> str:
    """07 S8: re-emitting the file with 07 S1.5's emitter is a zero-byte diff. Returns the text to write."""
    from ingest import emit
    from tools import fmt
    try:
        text = emit.emit(doc, rel)
        again = emit.reemit(text, rel)
    except (fmt.FmtError, ValueError) as e:
        raise GateError('round-trip', '%s: %s' % (rel, e)) from None
    if again != text:
        raise GateError('round-trip', '%s: re-emitting changes it (%d bytes -> %d)' % (rel, len(text), len(again)))
    return text

