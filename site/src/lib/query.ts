// site/src/lib/query.ts -- P2-S4-T02 (08 S5.7 "The fusion order", S5.5; 10 V11 "Search"). The faceted query pipeline
// over facets.json, in 08 S5.7's fixed, deterministic order:
//
//   1. the facet filter over the bitsets (lib/facet-index.ts) -> the survivors. Hard constraints only; nothing scored.
//   2. MiniSearch BM25 over the survivors -> a ranked list with scores.
//   3. cosine similarity over the int8 document matrix, restricted to the survivors -> a second ranked list.
//      NOT IMPLEMENTED: the semantic tier is Phase 6 (08 S5.5: potion-base-8M at 256 dimensions, the encoder spike,
//      vectors.i8.bin), and 08 S5.7 skips this step "entirely if the semantic tier has not been engaged", which until
//      Phase 6 it never is. A result's `semantic` is null, and nothing here stands in for it.
//   4. reciprocal rank fusion at k = 60 (RRF_K) over the ranked lists there are.
//
// Every step runs offline, with no model call (08 S5.7, C6): the AI layer's only entry point is writing step 1's query.
//
// Step 1 takes 08 S5.7's query, facet -> values in facets.json's own spellings, AND across facets and OR within one,
// plus inclusive ranges on the range columns. The browse view (lib/browse-view.ts) does the same over rail terms, each
// of which joins its spellings, and calls lib/facet-index.ts directly, so its island does not carry MiniSearch.
//
// Step 2. 08 S5.7 names the fields as "name, aliases, one-line summary". facets.json (08 S4.2's row, format 2) carries
// no summary, so the leg indexes `name`, `aliases` and `id` -- the id because a benchmark's slug is how it is often
// written; indexing a summary needs it in 08 S4.2's row and the emitter first. The text index is built once over every
// row, like the bitsets, and the survivors only restrict which rows it returns, so IDF and the average field lengths are
// the whole index's and a row's score does not move with the facet selection. MiniSearch scores with BM25+ at its
// defaults (k1 = 1.2, b = 0.7, delta = 0.5); a query term matches a token exactly or as its prefix (no fuzzy matching),
// any term may match (OR), and no field is boosted. Equal scores are ordered by row, never by MiniSearch's map order.
//
// Step 4: score(d) = the sum over the lists of 1 / (k + rank(d)), ranks counted from 1, a list without d adding nothing;
// equal scores are ordered by row. A row's number is its position in the rows the pipeline was built over
// (buildPipeline), the same in the bitsets and the text index, so a caller that orders its rows for display gets the
// survivors in that order.
import MiniSearch from 'minisearch';
import {
  RANGES, buildFacetIndex, has, intersect, members, union, valueSet, within, type Bitset, type FacetIndex, type IndexedRow,
  type RangeName,
} from './facet-index.ts';

// ---- step 1: the facet filter -------------------------------------------------------------------------------

/** 08 S5.7's facet query: facet -> values as facets.json spells them (an empty list is no constraint), and inclusive
 *  [lo, hi] ranges on the index's range columns. */
export interface FacetQuery {
  facets?: Readonly<Record<string, readonly string[]>>;
  ranges?: Readonly<Partial<Record<RangeName, readonly [number, number]>>>;
}

/** The survivors: every row inside each range and carrying, for each facet with a selection, one of its values. A
 *  facet the index has never seen admits nothing, as a value no row carries does. Throws on a range the index does not
 *  hold, rather than ignoring a constraint. */
export function filter(index: FacetIndex, q: FacetQuery): Bitset {
  const sets: (Bitset | null)[] = [];
  for (const [name, range] of Object.entries(q.ranges ?? {})) {
    if (range == null) continue;
    if (!(RANGES as readonly string[]).includes(name)) throw new Error(`no range facet ${name}: the index holds ${RANGES.join(', ')}`);
    sets.push(within(index.ranges[name as RangeName], index.words, range[0], range[1]));
  }
  for (const [facet, values] of Object.entries(q.facets ?? {})) {
    sets.push(values.length === 0 ? null : union(index.words, values.map((v) => valueSet(index, facet, v))));
  }
  return intersect(index.all, sets);
}

// ---- step 2: BM25 -------------------------------------------------------------------------------------------

/** What the text leg reads of a facets.json row. */
export interface TextRow {
  id: string;
  name: string;
  aliases: readonly string[];
}

/** The fields the BM25 leg indexes (module docstring, "Step 2"). */
export const TEXT_FIELDS = ['name', 'aliases', 'id'] as const;

interface TextDoc {
  row: number;
  id: string;
  name: string;
  aliases: string;
}

export type TextIndex = MiniSearch<TextDoc>;

/** The MiniSearch index over `rows`, whose document ids are row numbers. */
export function buildTextIndex(rows: readonly TextRow[]): TextIndex {
  const text = new MiniSearch<TextDoc>({
    idField: 'row',
    fields: [...TEXT_FIELDS],
    storeFields: [],
    searchOptions: { prefix: true, fuzzy: false, combineWith: 'OR' },
  });
  text.addAll(rows.map((r, row) => ({ row, id: r.id, name: r.name, aliases: (r.aliases ?? []).join(' ') })));
  return text;
}

/** A row and its score in one ranked list. */
export interface Ranked {
  row: number;
  score: number;
}

const byScore = (a: Ranked, b: Ranked) => b.score - a.score || a.row - b.row;

/** The survivors matching `query`, best first, with their BM25 scores; none for a blank query. */
export function bm25(text: TextIndex, query: string, survivors: Bitset): Ranked[] {
  if (query.trim() === '') return [];
  return text.search(query, { filter: (r) => has(survivors, r.id as number) })
    .map((r) => ({ row: r.id as number, score: r.score }))
    .sort(byScore);
}

// ---- step 3: cosine similarity -- Phase 6, not implemented (module docstring) ----------------------------------

// ---- step 4: reciprocal rank fusion ---------------------------------------------------------------------------

/** The RRF constant. k = 60 is the standard published default: the value fixed by the SIGIR 2009 paper that introduced
 *  reciprocal rank fusion, and the default of the search engines that implement it. It is not a number tuned on this
 *  corpus (08 S5.7). A larger k flattens the gap between the top ranks, so no one list decides the order alone. */
export const RRF_K = 60;

/** Reciprocal rank fusion of ranked lists (module docstring, "Step 4"), best first. */
export function rrf(lists: readonly (readonly Ranked[])[], k: number = RRF_K): Ranked[] {
  const score = new Map<number, number>();
  for (const list of lists) list.forEach((r, i) => score.set(r.row, (score.get(r.row) ?? 0) + 1 / (k + i + 1)));
  return [...score].map(([row, s]) => ({ row, score: s })).sort(byScore);
}

// ---- the pipeline ---------------------------------------------------------------------------------------------

export interface Pipeline {
  facets: FacetIndex;
  text: TextIndex;
}

/** The facet index and the text index over the same rows in the same order, built once on first load. */
export function buildPipeline(rows: readonly (IndexedRow & TextRow)[]): Pipeline {
  return { facets: buildFacetIndex(rows), text: buildTextIndex(rows) };
}

/** A query: the facet filter, and the free text (`q`) the BM25 leg ranks by. */
export interface Query extends FacetQuery {
  text?: string;
}

export interface Result {
  survivors: Bitset;            // step 1
  lexical: Ranked[] | null;     // step 2; null without a text query
  semantic: null;               // step 3: not implemented until Phase 6, so never engaged
  fused: Ranked[] | null;       // step 4 over the lists there are; null without a text query
  rows: number[];               // the result: the fused order with a text query, else every survivor in row order
}

/** The four steps in 08 S5.7's order. */
export function run(p: Pipeline, q: Query): Result {
  const survivors = filter(p.facets, q);
  const text = q.text?.trim() ?? '';
  if (text === '') return { survivors, lexical: null, semantic: null, fused: null, rows: members(survivors) };
  const lexical = bm25(p.text, text, survivors);
  const fused = rrf([lexical]);             // Phase 6 adds the semantic list here, after the lexical one
  return { survivors, lexical, semantic: null, fused, rows: fused.map((r) => r.row) };
}
