"""The deterministic pack layout behind atlas.json (P2-S5-T01; 10 V1, 08 S5.3).

    from tools.atlas import pack
    root = pack.Node('atlas', padding=8.0, children=[pack.Node('a', r=1.0), pack.Node('b', r=2.0)])
    pack.pack(root)         # every node's x, y and r, absolute, the root's circle centred on the origin

10 V1: the packed layout, the v1 default, is circle packing "keyed on presentation group -> domain family ->
subdomain", and it "is 100% stable by construction, needs no ML, no pinned numba and no drift gate". This module is
the layout and knows nothing of what it lays out: tools/atlas/emit.py builds the containment tree from the corpus and
the taxonomy, in a fixed order, and writes atlas.json.

The algorithm is d3-hierarchy's pack (d3.pack, packSiblings, packEnclose), ported: front-chain sibling packing and a
move-to-front smallest enclosing circle. Bottom up, a container packs its children, each grown by
half the container's `padding`, and its radius is their enclosing circle's plus that half, so `padding` is the gap
between two touching siblings and between the outermost child and the outline, as in d3; top down, each child is
moved into its parent's frame. A leaf keeps the radius it is given and nothing is rescaled, so the unit of every
coordinate is the unit of a leaf's radius.

Byte-identical across runs and platforms by construction:

  - Nothing is random or keyed on a hash. enclose() shuffles with d3's linear congruential generator (a=1664525,
    c=1013904223, m=2**32) from seed 1 on every call, in integer arithmetic, so one subtree's shuffle never depends
    on another's; no set or dict order reaches a coordinate.
  - It is a pure function of the tree, the order of every node's children included; the caller fixes that order.
  - The arithmetic is +, -, *, / and math.sqrt on Python floats, the operations IEEE 754 requires to be correctly
    rounded, so every CPython on a binary64 platform computes the same bits. Nothing here calls a transcendental
    function (whose last bit is the platform libm's), math.hypot, pow or sum() (whose float algorithm changed in
    3.12); tests/atlas/test_pack_deterministic.py holds the module to that, and pins the bits of one layout.
  - Coordinates leave unrounded. emit.py rounds them to fixed decimals for the artifact.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Node:
    """One circle of the containment tree. A leaf's `r` is given; pack() computes a container's `r` and every node's
    `x` and `y`. `padding` is a container's gap between its children, and between them and its outline."""
    id: str
    r: float = 0.0
    padding: float = 0.0
    children: list[Node] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0


@dataclass
class Circle:
    x: float = 0.0
    y: float = 0.0
    r: float = 0.0


def pack(root: Node) -> Node:
    """Lay out the tree in place: every container's radius bottom up, then every position top down."""
    _radii(root)
    root.x = root.y = 0.0
    _translate(root)
    return root


def _radii(node: Node) -> None:
    if not node.children:
        return
    for c in node.children:
        _radii(c)
    half = node.padding / 2
    grown = [Circle(0.0, 0.0, c.r + half) for c in node.children]   # copies: a child's r is never touched
    enclosing = pack_siblings(grown)
    for c, g in zip(node.children, grown):
        c.x, c.y = g.x, g.y                     # relative to the node's centre until _translate
    node.r = enclosing + half


def _translate(node: Node) -> None:
    for c in node.children:
        c.x = node.x + c.x
        c.y = node.y + c.y
        _translate(c)


# ---- siblings: the front chain (d3-hierarchy siblings.js) ----------------------------------------------------------

class _Link:
    __slots__ = ('c', 'next', 'previous')

    def __init__(self, circle: Circle):
        self.c = circle
        self.next: _Link | None = None
        self.previous: _Link | None = None


def place(b: Circle, a: Circle, c: Circle) -> None:
    """Put c tangent to both a and b."""
    dx, dy = b.x - a.x, b.y - a.y
    d2 = dx * dx + dy * dy
    if d2:
        a2 = a.r + c.r
        a2 *= a2
        b2 = b.r + c.r
        b2 *= b2
        if a2 > b2:
            x = (d2 + b2 - a2) / (2 * d2)
            y = math.sqrt(max(0.0, b2 / d2 - x * x))
            c.x = b.x - x * dx - y * dy
            c.y = b.y - x * dy + y * dx
        else:
            x = (d2 + a2 - b2) / (2 * d2)
            y = math.sqrt(max(0.0, a2 / d2 - x * x))
            c.x = a.x + x * dx - y * dy
            c.y = a.y + x * dy + y * dx
    else:
        c.x = a.x + c.r
        c.y = a.y


def intersects(a: Circle, b: Circle) -> bool:
    dr = a.r + b.r - 1e-6
    dx, dy = b.x - a.x, b.y - a.y
    return dr > 0 and dr * dr > dx * dx + dy * dy


def _score(link: _Link) -> float:
    a, b = link.c, link.next.c
    ab = a.r + b.r
    dx = (a.x * b.r + b.x * a.r) / ab
    dy = (a.y * b.r + b.y * a.r) / ab
    return dx * dx + dy * dy


def pack_siblings(circles: list[Circle]) -> float:
    """Place the circles, in order, tangent and not overlapping, centred so their enclosing circle is on the origin;
    return its radius."""
    n = len(circles)
    if n == 0:
        return 0.0
    a = circles[0]
    a.x, a.y = 0.0, 0.0
    if n == 1:
        return a.r
    b = circles[1]
    a.x, b.x, b.y = -b.r, a.r, 0.0
    if n == 2:
        return a.r + b.r
    place(b, a, circles[2])
    la, lb, lc = _Link(a), _Link(b), _Link(circles[2])
    la.next = lc.previous = lb
    lb.next = la.previous = lc
    lc.next = lb.previous = la
    i = 3
    while i < n:
        place(la.c, lb.c, circles[i])
        lc = _Link(circles[i])
        # the closest circle on the front chain that the new one intersects, if any, by distance along the chain
        j, k, sj, sk = lb.next, la.previous, lb.c.r, la.c.r
        retry = False
        while True:
            if sj <= sk:
                if intersects(j.c, lc.c):
                    lb = j
                    la.next, lb.previous = lb, la
                    retry = True
                    break
                sj += j.c.r
                j = j.next
            else:
                if intersects(k.c, lc.c):
                    la = k
                    la.next, lb.previous = lb, la
                    retry = True
                    break
                sk += k.c.r
                k = k.previous
            if j is k.next:
                break
        if retry:
            continue                            # place circle i again, between the new pair
        lc.previous, lc.next = la, lb           # insert it between a and b
        la.next = lb.previous = lc
        lb = lc
        best, aa = la, _score(la)               # the pair closest to the centroid starts the next search
        link = lc.next
        while link is not lb:
            ca = _score(link)
            if ca < aa:
                best, aa = link, ca
            link = link.next
        la, lb = best, best.next
        i += 1
    chain, link = [lb.c], lb.next
    while link is not lb:
        chain.append(link.c)
        link = link.next
    e = enclose(chain)
    for c in circles:
        c.x -= e.x
        c.y -= e.y
    return e.r


# ---- the enclosing circle (d3-hierarchy enclose.js) ---------------------------------------------------------------

class _Lcg:
    """d3's lcg.js: the same sequence on every call and every platform, in integers."""
    A, C, M = 1664525, 1013904223, 4294967296

    def __init__(self) -> None:
        self.s = 1

    def below(self, m: int) -> int:
        """floor(random() * m), exactly."""
        self.s = (self.A * self.s + self.C) % self.M
        return (self.s * m) >> 32


def enclose(circles: list[Circle]) -> Circle:
    """The smallest circle enclosing every one of `circles` (move-to-front, over a fixed-seed shuffle)."""
    items, rng = list(circles), _Lcg()
    m = len(items)
    while m:
        i = rng.below(m)
        m -= 1
        items[m], items[i] = items[i], items[m]
    i, basis, e = 0, [], None
    while i < len(items):
        p = items[i]
        if e is not None and encloses_weak(e, p):
            i += 1
        else:
            basis = _extend_basis(basis, p)
            e = _enclose_basis(basis)
            i = 0
    return e


def _extend_basis(basis: list[Circle], p: Circle) -> list[Circle]:
    if _encloses_weak_all(p, basis):
        return [p]
    for b in basis:
        if _encloses_not(p, b) and _encloses_weak_all(_enclose2(b, p), basis):
            return [b, p]
    for i in range(len(basis) - 1):
        for j in range(i + 1, len(basis)):
            bi, bj = basis[i], basis[j]
            if (_encloses_not(_enclose2(bi, bj), p) and _encloses_not(_enclose2(bi, p), bj)
                    and _encloses_not(_enclose2(bj, p), bi) and _encloses_weak_all(_enclose3(bi, bj, p), basis)):
                return [bi, bj, p]
    raise ValueError('no enclosing basis extends %r with %r' % (basis, p))


def _encloses_not(a: Circle, b: Circle) -> bool:
    dr = a.r - b.r
    dx, dy = b.x - a.x, b.y - a.y
    return dr < 0 or dr * dr < dx * dx + dy * dy


def encloses_weak(a: Circle, b: Circle) -> bool:
    dr = a.r - b.r + max(a.r, b.r, 1.0) * 1e-9
    dx, dy = b.x - a.x, b.y - a.y
    return dr > 0 and dr * dr > dx * dx + dy * dy


def _encloses_weak_all(a: Circle, basis: list[Circle]) -> bool:
    return all(encloses_weak(a, b) for b in basis)


def _enclose_basis(basis: list[Circle]) -> Circle:
    if len(basis) == 1:
        return Circle(basis[0].x, basis[0].y, basis[0].r)
    if len(basis) == 2:
        return _enclose2(basis[0], basis[1])
    return _enclose3(basis[0], basis[1], basis[2])


def _enclose2(a: Circle, b: Circle) -> Circle:
    x21, y21, r21 = b.x - a.x, b.y - a.y, b.r - a.r
    l = math.sqrt(x21 * x21 + y21 * y21)  # noqa: E741 -- d3's name
    if not l:                               # concentric: the larger one is the answer (d3 divides by zero here)
        big = a if a.r >= b.r else b
        return Circle(big.x, big.y, big.r)
    return Circle((a.x + b.x + x21 / l * r21) / 2, (a.y + b.y + y21 / l * r21) / 2, (l + a.r + b.r) / 2)


def _enclose3(a: Circle, b: Circle, c: Circle) -> Circle:
    x1, y1, r1 = a.x, a.y, a.r
    x2, y2, r2 = b.x, b.y, b.r
    x3, y3, r3 = c.x, c.y, c.r
    a2, a3 = x1 - x2, x1 - x3
    b2, b3 = y1 - y2, y1 - y3
    c2, c3 = r2 - r1, r3 - r1
    d1 = x1 * x1 + y1 * y1 - r1 * r1
    d2 = d1 - x2 * x2 - y2 * y2 + r2 * r2
    d3 = d1 - x3 * x3 - y3 * y3 + r3 * r3
    ab = a3 * b2 - a2 * b3
    xa = (b2 * d3 - b3 * d2) / (ab * 2) - x1
    xb = (b3 * c2 - b2 * c3) / ab
    ya = (a3 * d2 - a2 * d3) / (ab * 2) - y1
    yb = (a2 * c3 - a3 * c2) / ab
    qa = xb * xb + yb * yb - 1
    qb = 2 * (r1 + xa * xb + ya * yb)
    qc = xa * xa + ya * ya - r1 * r1
    r = -((qb + math.sqrt(max(0.0, qb * qb - 4 * qa * qc))) / (2 * qa) if abs(qa) > 1e-6 else qc / qb)
    return Circle(x1 + xa + xb * r, y1 + ya + yb * r, r)
