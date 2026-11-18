"""atlas.json from the deterministic pack layout: nodes, edges and regions (P2-S5-T01; 10 V1, 08 S4.2, S5.3).

    bench build --atlas --out build/    # build/atlas.json over the published corpus, beside the S8 artifacts

10 V1, the hero view: "Every benchmark family is a node", placed at build time, and "the client never runs a layout
algorithm". 08 S5.3: "the deterministic pack layout is the shipping Atlas for public v1"; the warm-start UMAP
construction (P2-S5-T05, T06) is promoted only once it earns it, and `layout_method` says which construction made the
coordinates. This module is the pack half: it builds the containment tree, tools/atlas/pack.py lays it out.

Containment (10 V1): presentation group -> domain family -> subdomain -> benchmark. Capability has no place in it,
because it is a facet (08 S5.3's closing paragraph keys the pack on "domain -> subdomain -> capability"; 10 V1 and the
task follow the presentation-group chain, and this does). A benchmark sits in the subdomain its `domain.primary`
names, that subdomain's family and the family's group in taxonomy/domain_groups.yaml. Groups and their members are
packed in the order domain_groups.yaml declares ("Declared order below IS the render order"), subdomains in
domains.yaml's order, and one subdomain's benchmarks by adoption_n, most first, then by the UTF-8 bytes of their id.
A container that holds no published benchmark is not drawn. PADDING is each level's gap, in leaf-radius units.

Radius (10 V1, "Node size: adoption -- distinct systems with claims, log-scaled"): r = 1 + ln(1 + adoption_n), to 3
places, so a benchmark nobody reports on is the unit dot. adoption_n is the number of distinct System entities with a
claim on the benchmark, both tiers: derived/adoption.json's `systems`, read with tools/build/adoption.py's own
functions, so the map and the detail page cannot disagree. The logarithm is Decimal's, correctly rounded everywhere,
where math.log's last bit is the platform's.

The artifact:

  {artifact: atlas, format, layout_method: pack, layout_epoch, basis_version, vocabularies, adoption_basis,
   nodes, edges, regions, drafts (a preview build only)}

  nodes    10 V1's per-node fields plus 08 S4.2's `cluster`, in UTF-8 byte order of id:
             id, x, y, r           the pack's circle, to 3 places
             cluster               the domain family the node is packed in: the legend row it belongs to
             domain_primary        the record's domain.primary, a subdomain id
             domain_group          the family's presentation group. Display-only: atlas.json is the one artifact
                                   that may carry it (05 S9 9h, scripts/check_display_only_vocab.py PERMITTED)
             lifecycle             the record's, or null
             headroom_consumed     null: nothing computes headroom yet, which is why facets.json's `headroom` is
                                   null too (tools/build/emit.py); S4 fills both
             adoption_n            above
             label                 the record's name
             label_priority        1 for the label drawn first: the rank by adoption_n, most first, then id bytes
  edges    {from, to, kind, coefficient, source}, sorted, each once however many records state it:
             supersedes, extends, subset_of, decontaminates   10 V1's lineage, drawn solid, read as lineage_svg.py
                                   reads the schema: `superseded_by: [X]` on B is X supersedes B, and `extended_by:
                                   [X]` is X extends B. coefficient and source are null.
             correlates_with       drawn dashed, and only where `coefficient` has a `source` ("An unsourced
                                   correlation edge is not drawn at all"); a correlation has no direction, so its
                                   pair is written in id byte order.
           An edge is drawn only between two nodes; one to an unpublished entry has nothing to end on. variants,
           forks and views are the detail page's lineage rows (lineage_svg.py), not 10 V1's edge kinds.
  regions  {id, level, parent, label, x, y, r} for every group and family circle, in containment pre-order, because
           "group and family regions carry hairline outlines and permanent text labels" and the client runs no
           layout to find them. A subdomain circle is packed but not outlined, so it is not carried. No region
           carries a count: a group is never given one (10 V1).

layout_method is `pack`. layout_epoch is 0: the epoch ledger, atlas/atlas_epoch.yaml, is P2-S5-T07's and does not
exist, and a pack layout, a pure function of the corpus and the taxonomy, never needs re-basing. If the ledger
appears before its reader is wired here, the build refuses rather than emit an epoch it did not read. basis_version
is null: the pack projects through no SVD basis (atlas/basis_v1.npz is P2-S5-T05's and only the UMAP construction
reads it).

No entry is published yet (05 S4), so `bench build --atlas` writes an honest empty atlas, the envelope with no nodes,
edges or regions. tests/atlas/test_pack_deterministic.py lays out tests/fixtures/corpus-20/ built as the draft
preview builds it.

Determinism (08 S6): records are taken in id byte order, the claims as adoption.py reads them (sorted paths, counted
into sets), the containment order is the taxonomy's, the layout is pack.py's, every float is rounded to 3 places with
-0.0 folded into 0.0, and the bytes are tools/build/emit.py's serialise() of the NFC artifact. Two runs are
byte-identical, and so are two platforms.
"""
from __future__ import annotations

import math
import os
from decimal import Context, Decimal

from tools.atlas import pack
from tools.build import adoption
from tools.build.artifacts import vocabulary_versions
from tools.build.emit import by_id, nfc, serialise, taxonomy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTIFACT = 'atlas.json'
FORMAT = 1
LAYOUT_METHOD = 'pack'
EPOCH_LEDGER = 'atlas/atlas_epoch.yaml'          # P2-S5-T07's (05 S2)
PLACES = 3
PADDING = {'root': 12.0, 'group': 6.0, 'family': 3.0, 'subdomain': 1.0}   # the gap inside each level (pack.py)
LEVELS = ('group', 'family')                     # a region's level, by depth below the root
TIERS = ('curated', 'machine-ingested')          # what adoption_n counts (adoption.py)
NODE = ('id', 'x', 'y', 'r', 'cluster', 'domain_primary', 'domain_group', 'lifecycle', 'headroom_consumed',
        'adoption_n', 'label', 'label_priority')
EDGE = ('from', 'to', 'kind', 'coefficient', 'source')
REGION = ('id', 'level', 'parent', 'label', 'x', 'y', 'r')
LINEAGE = ('supersedes', 'extends', 'subset_of', 'decontaminates')
CORRELATION = 'correlates_with'
KINDS = LINEAGE + (CORRELATION,)
_LN = Context(prec=34)


class AtlasError(Exception):
    """The atlas cannot be emitted; the message says why."""


def fix(v: float) -> float:
    """A coordinate as the artifact carries it: 3 places, and never -0.0 (nor a NaN, which is not JSON)."""
    if not math.isfinite(v):
        raise AtlasError('the pack layout produced a non-finite coordinate (%r)' % v)
    return round(v, PLACES) + 0.0


def radius(adoption_n: int) -> float:
    """r = 1 + ln(1 + adoption_n), to 3 places; Decimal's ln is correctly rounded on every platform."""
    return round(1.0 + float(Decimal(1 + adoption_n).ln(_LN)), PLACES)


def _key(ident: str) -> bytes:
    return ident.encode('utf-8')


def adoption_counts(ids, root: str = ROOT) -> dict[str, int]:
    """benchmark id -> the distinct systems with a claim on it, both tiers (derived/adoption.json's `systems`)."""
    systems: dict[str, set[str]] = {i: set() for i in ids}
    for c in adoption.load_claims(root) if systems else []:        # no node, no claim worth reading
        held = systems.get(adoption.entity(c['benchmark']))
        system = adoption.entity(c.get('system'))
        if held is not None and system is not None:
            held.add(system)
    return {i: len(s) for i, s in systems.items()}


def layout_epoch(root: str = ROOT) -> int:
    if os.path.exists(os.path.join(root, *EPOCH_LEDGER.split('/'))):
        raise AtlasError('%s exists, but nothing reads it yet (P2-S5-T07 builds its reader); the pack layout will not '
                         'emit an epoch it did not read' % EPOCH_LEDGER)
    return 0


# ---- the containment tree -----------------------------------------------------------------------------------------

def _taxonomy():
    """(groups in declared order, family -> group id, subdomain -> its domains.yaml position, (level, id) -> label)."""
    models = taxonomy()
    groups = models['domain_groups.yaml'].groups
    terms = models['domains.yaml'].terms
    labels = {('group', g.id): g.label for g in groups}
    labels.update({('family', t.id): t.label for t in terms if t.parent is None})
    return groups, {f: g.id for g in groups for f in g.members}, {t.id: i for i, t in enumerate(terms)}, labels


def tree(benchmarks: list[dict], adoption_n: dict[str, int]) -> pack.Node:
    """The containment tree, in the module docstring's order, laid out."""
    groups, group_of, position, _ = _taxonomy()
    by_subdomain: dict[str, list[dict]] = {}
    for b in benchmarks:
        sub = b['domain']['primary']
        if sub not in position or sub.split('/')[0] not in group_of:
            raise AtlasError('%s: domain.primary %s is not a subdomain of a grouped family (taxonomy/domains.yaml, '
                             'taxonomy/domain_groups.yaml)' % (b['id'], sub))
        by_subdomain.setdefault(sub, []).append(b)
    root = pack.Node('atlas', padding=PADDING['root'])
    for g in groups:
        group = pack.Node(g.id, padding=PADDING['group'])
        for fam in g.members:
            family = pack.Node(fam, padding=PADDING['family'])
            for sub in sorted((s for s in by_subdomain if s.split('/')[0] == fam), key=position.__getitem__):
                leaves = sorted(by_subdomain[sub], key=lambda b: (-adoption_n[b['id']], _key(b['id'])))
                family.children.append(pack.Node(sub, padding=PADDING['subdomain'], children=[
                    pack.Node(b['id'], r=radius(adoption_n[b['id']])) for b in leaves]))
            if family.children:
                group.children.append(family)
        if group.children:
            root.children.append(group)
    return pack.pack(root)


def leaves(node: pack.Node) -> list[pack.Node]:
    return [node] if not node.children else [leaf for c in node.children for leaf in leaves(c)]


def regions(root: pack.Node) -> list[dict]:
    """Every group and family circle, in pre-order."""
    labels = _taxonomy()[3]
    out: list[dict] = []

    def walk(node: pack.Node, depth: int, parent: str | None) -> None:
        if depth == len(LEVELS):
            return
        for c in node.children:
            out.append({'id': c.id, 'level': LEVELS[depth], 'parent': parent, 'label': labels[(LEVELS[depth], c.id)],
                        'x': fix(c.x), 'y': fix(c.y), 'r': fix(c.r)})
            walk(c, depth + 1, c.id)
    walk(root, 0, None)
    return out


# ---- nodes and edges ----------------------------------------------------------------------------------------------

def nodes(benchmarks: list[dict], adoption_n: dict[str, int], root: pack.Node) -> list[dict]:
    circles = {leaf.id: leaf for leaf in leaves(root) if leaf is not root}
    group_of = _taxonomy()[1]
    ranked = sorted(benchmarks, key=lambda b: (-adoption_n[b['id']], _key(b['id'])))
    priority = {b['id']: rank for rank, b in enumerate(ranked, 1)}
    out = []
    for b in by_id(benchmarks):
        c, sub = circles[b['id']], b['domain']['primary']
        fam = sub.split('/')[0]
        out.append({'id': b['id'], 'x': fix(c.x), 'y': fix(c.y), 'r': fix(c.r), 'cluster': fam, 'domain_primary': sub,
                    'domain_group': group_of[fam], 'lifecycle': b['lifecycle'], 'headroom_consumed': None,
                    'adoption_n': adoption_n[b['id']], 'label': b['name'], 'label_priority': priority[b['id']]})
    return out


def edges(benchmarks: list[dict], ids) -> list[dict]:
    """The lineage and sourced-correlation edges between two of `ids`, each once, sorted."""
    found: set[tuple] = set()

    def add(a, b, kind, coefficient=None, source=None):
        if a == b or a not in ids or b not in ids:
            return
        if kind == CORRELATION and _key(b) < _key(a):
            a, b = b, a
        found.add((a, b, kind, coefficient, source))
    for rec in benchmarks:
        me, lin = rec['id'], rec.get('lineage') or {}
        for x in lin.get('supersedes') or []:
            add(me, x, 'supersedes')
        for x in lin.get('superseded_by') or []:
            add(x, me, 'supersedes')
        if lin.get('subset_of') is not None:
            add(me, lin['subset_of'], 'subset_of')
        for x in lin.get('extended_by') or []:
            add(x, me, 'extends')
        if lin.get('decontaminates') is not None:
            add(me, lin['decontaminates'], 'decontaminates')
        for corr in lin.get('correlates_with') or []:
            if corr.get('coefficient') is not None and corr.get('source') is not None:
                add(me, corr['benchmark'], CORRELATION, corr['coefficient'], corr['source'])
    order = sorted(found, key=lambda e: (_key(e[0]), _key(e[1]), KINDS.index(e[2]), _key(e[4] or ''),
                                         e[3] if e[3] is not None else 0.0))
    return [dict(zip(EDGE, e)) for e in order]


# ---- the artifact -------------------------------------------------------------------------------------------------

def build(corpus: dict, root: str = ROOT) -> dict:
    """atlas.json over a corpus.json artifact (artifacts.build().corpus): its benchmarks are the nodes. `root` is the
    data root the corpus was built from, whose data/claims/ adoption_n counts."""
    benchmarks = corpus['entities']['benchmark']
    adoption_n = adoption_counts([b['id'] for b in benchmarks], root)
    laid = tree(benchmarks, adoption_n)
    return nfc({
        'artifact': 'atlas', 'format': FORMAT, 'layout_method': LAYOUT_METHOD, 'layout_epoch': layout_epoch(root),
        'basis_version': None, 'vocabularies': vocabulary_versions(),
        'adoption_basis': {'counts': 'distinct systems with a claim', 'tiers': list(TIERS),
                           'radius': 'r = 1 + ln(1 + adoption_n), to %d places' % PLACES},
        'nodes': nodes(benchmarks, adoption_n, laid), 'edges': edges(benchmarks, {b['id'] for b in benchmarks}),
        'regions': regions(laid),
        **({'drafts': True} if corpus.get('drafts') else {})})


def write(artifact: dict, out_dir: str) -> str:
    """Write out_dir/atlas.json in 08 S6's canonical bytes; returns its path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, ARTIFACT)
    with open(path, 'wb') as fh:
        fh.write(serialise(artifact))
    return path
