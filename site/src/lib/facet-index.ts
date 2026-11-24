// site/src/lib/facet-index.ts -- P2-S4-T02 (08 S5.7 "The representation", S8.1; 10 V11). The facet index: one
// Uint32Array bitset per facet value of facets.json, built once on first load, where bit i is set when row i carries the
// value; and the range facets as sorted Float32Array columns. "There is no library, no index format and no dependency"
// (08 S5.7), so the browse view's island (lib/browse-view.ts) carries this without the search leg's MiniSearch
// (lib/query.ts), and Node loads it as it is, stripping its types.
//
// Rows and bits. A row's bit is its position in the rows the index was built over, so a caller that orders its rows for
// display before building gets every result set in display order (members()). A set is ceil(n / 32) words: 47 words,
// 188 bytes, at 1,500 rows; 157 words at 5,000. Bits past the last row are always clear, so a count never needs a mask.
//
// Which values. `domain` and `subdomain` (the family of domain.primary, and domain.primary), and every array of the row's
// `facets` object -- the seven flat facets, keyed by taxonomy facet name (tools/build/emit.py FLAT_FACETS) -- each under
// its own name, with the value as facets.json spells it: the bare term id, or `{field}:{id}` for an id its facet
// defines in two fields. The index does not interpret a value; joining a spelling to a taxonomy term is the caller's
// (lib/browse-view.ts does it for the rail). The scalar `lifecycle` is not indexed apart, because the lifecycle array
// holds it, and the claim-derived scalars are not facets.
//
// Semantics. AND across facets, OR within a facet, 08 S5.7's loop: union() is the OR, intersect() the AND. A facet with
// no selection is no constraint (null), and a facet with a selection that no row carries admits nothing (an empty
// union), never "no constraint". constrain() adds the faceted counts' sets: a value's count is the rows that carry it
// and pass every OTHER facet's selection, so the counts of a facet with a selection still say what each of its other
// values would add.
//
// Ranges. A range facet (release year, headroom) is not bucketed into bits, "because bucketing a continuous range into
// bits throws away exactly the precision a range filter exists to provide" (08 S5.7). Its non-null values sit sorted in
// a Float32Array with, position for position, the row each came from (the position->index map), and [lo, hi] is two
// binary searches -- the first position >= lo, the first > hi -- and the rows between. Both bounds are rounded to
// float32 as the stored values were, so a bound equal to a value admits it: 0.8 has no exact float32, and an unrounded
// 0.8 would leave out a row whose headroom is 0.8. A row with no value is outside every range.

/** A set of rows: bit i of word i >>> 5 is row i. */
export type Bitset = Uint32Array;

/** The words a set over `n` rows takes. */
export const wordsFor = (n: number): number => (n + 31) >>> 5;

/** Every row of `n`. */
export function fullSet(n: number): Bitset {
  const s = new Uint32Array(wordsFor(n)).fill(0xffffffff);
  if ((n & 31) !== 0) s[s.length - 1] = 2 ** (n & 31) - 1;
  return s;
}

export function add(s: Bitset, row: number): void {
  s[row >>> 5] |= 1 << (row & 31);
}

export function has(s: Bitset, row: number): boolean {
  return (s[row >>> 5] & (1 << (row & 31))) !== 0;
}

/** acc |= b, in place; returns acc. */
export function orInto(acc: Bitset, b: Bitset): Bitset {
  for (let w = 0; w < acc.length; w++) acc[w] |= b[w];
  return acc;
}

/** acc &= b, in place; returns acc. */
export function andInto(acc: Bitset, b: Bitset): Bitset {
  for (let w = 0; w < acc.length; w++) acc[w] &= b[w];
  return acc;
}

// the bits set in one 32-bit word, without a loop over them
const pop32 = (x: number): number => {
  x -= (x >>> 1) & 0x55555555;
  x = (x & 0x33333333) + ((x >>> 2) & 0x33333333);
  return Math.imul((x + (x >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
};

/** The rows in `s`. */
export function count(s: Bitset): number {
  let n = 0;
  for (let w = 0; w < s.length; w++) n += pop32(s[w]);
  return n;
}

/** The rows in both `a` and `b`, without building their intersection. */
export function countBoth(a: Bitset, b: Bitset): number {
  let n = 0;
  for (let w = 0; w < a.length; w++) n += pop32(a[w] & b[w]);
  return n;
}

/** The rows in `s`, ascending: the build order, which is the caller's display order. */
export function members(s: Bitset): number[] {
  const out: number[] = [];
  for (let w = 0; w < s.length; w++) {
    let word = s[w];
    while (word !== 0) {
      const low = word & -word;               // the lowest set bit
      out.push((w << 5) + 31 - Math.clz32(low));
      word ^= low;
    }
  }
  return out;
}

/** OR within a facet: the rows carrying any of `sets`. An absent set (a value no row carries) adds nothing, so a
 *  selection of such values only is the empty set. A new set. */
export function union(words: number, sets: Iterable<Bitset | null | undefined>): Bitset {
  const acc = new Uint32Array(words);
  for (const s of sets) if (s != null) orInto(acc, s);
  return acc;
}

/** AND across facets: `base` narrowed by every facet's union, where null is a facet with no selection. A new set. */
export function intersect(base: Bitset, unions: readonly (Bitset | null)[]): Bitset {
  const acc = base.slice();
  for (const u of unions) if (u != null) andInto(acc, u);
  return acc;
}

/** The result set, and per facet the set its own values are counted within: `base` and every OTHER facet's union. A
 *  facet with no selection counts within the result set itself. */
export function constrain(base: Bitset, unions: readonly (Bitset | null)[]): { all: Bitset; others: Bitset[] } {
  const all = intersect(base, unions);
  const others = unions.map((u, i) => (u == null ? all : intersect(base, unions.map((v, j) => (j === i ? null : v)))));
  return { all, others };
}

// ---- range columns ------------------------------------------------------------------------------------------

/** A range facet: its non-null values ascending, and the row each came from at the same position. */
export interface RangeColumn {
  values: Float32Array;
  rows: Uint32Array;
}

/** The column of one numeric field, `values[row]`; null, undefined and non-finite values are left out. */
export function rangeColumn(values: readonly (number | null | undefined)[]): RangeColumn {
  const at: number[] = [];
  for (let row = 0; row < values.length; row++) {
    const v = values[row];
    if (typeof v === 'number' && Number.isFinite(v)) at.push(row);
  }
  const f = (row: number) => Math.fround(values[row] as number);
  at.sort((a, b) => f(a) - f(b) || a - b);
  return { values: Float32Array.from(at, f), rows: Uint32Array.from(at) };
}

// the first position whose value is >= x (lower) or > x (upper)
function bound(values: Float32Array, x: number, upper: boolean): number {
  let lo = 0;
  let hi = values.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (values[mid] < x || (upper && values[mid] === x)) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** The rows whose value lies in [lo, hi], inclusive: two binary searches (module docstring, "Ranges"). Empty when
 *  lo > hi or either bound is NaN. */
export function within(col: RangeColumn, words: number, lo: number, hi: number): Bitset {
  const out = new Uint32Array(words);
  if (!(lo <= hi)) return out;
  const end = bound(col.values, Math.fround(hi), true);
  for (let p = bound(col.values, Math.fround(lo), false); p < end; p++) add(out, col.rows[p]);
  return out;
}

// ---- the index over facets.json -----------------------------------------------------------------------------

/** What the index reads of a facets.json row (lib/browse-view.ts FacetRow has it all). */
export interface IndexedRow {
  domain: string;
  subdomain: string;
  facets?: Readonly<Record<string, readonly string[]>>;
  year: number | null;
  headroom: number | null;
}

/** The facets.json fields the index holds as range columns. */
export const RANGES = ['year', 'headroom'] as const;
export type RangeName = (typeof RANGES)[number];

/** The facets.json fields indexed as single values, beside the `facets` arrays. */
export const SCALAR_FACETS = ['domain', 'subdomain'] as const;

export interface FacetIndex {
  size: number;                                   // rows
  words: number;                                  // words per set
  all: Bitset;                                    // every row
  values: Map<string, Map<string, Bitset>>;       // facet -> value as facets.json spells it -> the rows carrying it
  ranges: Record<RangeName, RangeColumn>;
}

/** The index over `rows`, in their order (module docstring). Throws on a `facets` array named like a scalar facet,
 *  which would merge two facets' values into one. */
export function buildFacetIndex(rows: readonly IndexedRow[]): FacetIndex {
  const words = wordsFor(rows.length);
  const values = new Map<string, Map<string, Bitset>>(SCALAR_FACETS.map((f) => [f, new Map()]));
  const mark = (facet: string, value: string, row: number) => {
    let byValue = values.get(facet);
    if (byValue == null) values.set(facet, (byValue = new Map()));
    let s = byValue.get(value);
    if (s == null) byValue.set(value, (s = new Uint32Array(words)));
    add(s, row);
  };
  rows.forEach((r, row) => {
    mark('domain', r.domain, row);
    mark('subdomain', r.subdomain, row);
    for (const [facet, vs] of Object.entries(r.facets ?? {})) {
      if ((SCALAR_FACETS as readonly string[]).includes(facet)) throw new Error(`facets.json row ${row}: a facets array is named ${facet}, which is a scalar facet`);
      for (const v of vs) mark(facet, v, row);
    }
  });
  return {
    size: rows.length, words, all: fullSet(rows.length), values,
    ranges: { year: rangeColumn(rows.map((r) => r.year)), headroom: rangeColumn(rows.map((r) => r.headroom)) },
  };
}

/** The rows carrying `value` of `facet`, as facets.json spells it; undefined when no row does. Read-only: the set is the
 *  index's own. */
export function valueSet(index: FacetIndex, facet: string, value: string): Bitset | undefined {
  return index.values.get(facet)?.get(value);
}
