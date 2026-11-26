// site/src/islands/search/fusion.ts -- P6-S1-T05 (11 S4 "The pipeline", step 2; 08 S5.7 "The fusion order", step 4).
// Reciprocal rank fusion of the two ranked lists -- the BM25 leg's (islands/search/lexical.ts) and the cosine leg's
// (islands/search/cosine.ts), both over the facet filter's survivors -- at K = 60, the top FUSED_TOP (40), then 11 S4's
// "cheap deterministic re-rank on facet-match count, recency and curation completeness, down to the top 25"
// (RERANKED_TOP). No model, no weight and no network: it runs with the Worker offline, like every step of 08 S5.7.
//
// The fusion. score(d) = the sum, over the lists holding d, of 1 / (K + rank(d)); a list without d adds nothing. K = 60
// is the standard published default, a named constant and not a number tuned on this corpus (08 S5.7), and the test
// holds it equal to lib/query.ts's RRF_K, so the Phase 2 pipeline and this module cannot disagree on it. RRF reads ranks
// only, which "sidesteps the BM25-versus-cosine score-scale incompatibility that makes weighted-sum fusion so fragile"
// (11 S4). Two choices make the fused list a function of what the lists say, never of how they are laid out:
//
//   - A rank is read from the scores, not from an array position: 1 + the number of entries in the list that score
//     strictly higher (competition ranking, "1224"). Rows a leg scores equal share a rank and so a fused contribution,
//     and the order an engine happened to emit them in -- MiniSearch's map order, a sort's stability -- never reaches
//     the fusion. lib/query.ts's rrf() counts positions instead; the two agree wherever a list has no tied scores.
//   - A row's terms are summed in ascending rank order, so the float sum does not depend on the order of the lists.
//
// The cut. The fused rows are ordered by RRF score, best first, and the first FUSED_TOP kept. A tie at the cut is broken
// by the rerank's own signals, in the rerank's order, and then by row, so which rows survive it is decided by what the
// rows are rather than by their row numbers wherever the signals can tell them apart.
//
// The rerank, over those 40, down to RERANKED_TOP, by these keys in order:
//
//   1. facet-match count, most first: how many of the query's soft facet values (11 S4: "hard facets filter; soft
//      facets become score boosts") the row carries. Values are spelled as facets.json spells them, as lib/query.ts's
//      FacetQuery takes them; the facet-qualified references the translator writes (`capability:planning`) are the
//      caller's to strip, as 11 S4 says the client does. `domain` and `subdomain` match the row's scalars and every
//      other facet the row's `facets` array of that name; a repeated value counts once, and a facet the row has no
//      array for matches nothing. Hard facets are not counted: every survivor carries them.
//   2. the RRF score, best first: relevance.
//   3. recency, newest first: the release `year` of the facets.json row; a row with none comes after every year.
//   4. curation completeness, most first: how many of the seven flat facet arrays (COMPLETENESS_FACETS, tools/build/
//      emit.py FLAT_FACETS) the row populates. It is an ordering key computed from facets.json and shown nowhere, not a
//      field and not a score: 15 B1 warns that "there is no curation_completeness field anywhere in this plan and
//      inventing one would be a third completeness score next to condition_completeness". Of 15 B1's depth bar, the
//      facets are the part facets.json carries.
//   5. the row number: facets.json order, which is the ids' UTF-8 byte order (tools/build/emit.py), so the last key is
//      the id.
//
// Why relevance sits above recency and completeness. RRF is rank-only so that no weight has to be tuned (08 S5.7), and
// with no weight the three signals can only be ordered against relevance, not traded against it. Put above it, recency
// would rank an exact match below every newer row of the 40 -- the query `mmlu` would list MMLU after its successors,
// and could cut it from the 25 -- so recency and curation completeness order the rows relevance cannot tell apart:
// equal RRF scores, which arise whenever two rows hold the same ranks (one first lexically and third semantically, the
// other the reverse) and whenever a leg scores rows equal. The facet-match count sits above relevance because a soft
// facet is the query's own stated preference, which the user reads and edits as a chip (11 S4 "Inspectability is the
// product"). Moving a key is a one-line change to byReranked() and a visible change to the test.
//
// Determinism. Every comparator here ends on the row number, and a list may not hold a row twice, so no two candidates
// compare equal: the order is total, the same under any sort algorithm, stable or not, and under any order of the
// inputs. test/fusion.determinism.test.mjs holds the top 25 byte-identical over 100 runs with every input shuffled.
//
// What this module does not do: decide how the two result sets are shown (11 F0 renders them as two labelled blocks,
// P6-S1-T09), encode the query (P6-S1-T01) or load the matrix (P6-S1-T06). lib/query.ts's run() still fuses the lexical
// list alone, as the Phase 2 pipeline does until the semantic tier is engaged in it.
import type { Ranked } from './lexical.ts';

/** The RRF constant. k = 60 is the standard published default: the value fixed by the SIGIR 2009 paper that introduced
 *  reciprocal rank fusion, and the default of the search engines that implement it. It is not a number tuned on this
 *  corpus (08 S5.7). */
export const K = 60;
/** How many fused rows the rerank reads (11 S4: "Take the top 40"). */
export const FUSED_TOP = 40;
/** How many it keeps (11 S4: "down to the top 25"): what the synthesis step is given. */
export const RERANKED_TOP = 25;

/** The seven flat facets whose arrays curation completeness counts (tools/build/emit.py FLAT_FACETS, in its order). */
export const COMPLETENESS_FACETS = [
  'capability', 'evaluation_method', 'subject', 'data_properties', 'lifecycle', 'governance', 'execution',
] as const;

/** What the rerank reads of a facets.json row (lib/browse-view.ts FacetRow has it all). */
export interface RerankRow {
  domain: string;
  subdomain: string;
  facets?: Readonly<Record<string, readonly string[]>>;
  year: number | null;
}

/** The query's soft facets: facet -> values as facets.json spells them. */
export type SoftFacets = Readonly<Record<string, readonly string[]>>;

/** The two legs of 08 S5.7. A leg that did not run -- no text query, or the semantic tier not engaged -- is null. */
export interface Legs {
  lexical: readonly Ranked[] | null;
  semantic: readonly Ranked[] | null;
}

/** A fused row, with everything that placed it, so the order can be shown and checked. */
export interface Candidate {
  row: number;
  score: number;                // the RRF score
  lexical: number | null;       // its rank in the lexical leg, or null when that leg did not return it
  semantic: number | null;      // its rank in the semantic leg, likewise
  facetMatches: number;
  year: number | null;
  completeness: number;
}

/** -1 when x is larger, 1 when y is: a descending key, by comparison rather than subtraction, so that two absent
 *  years (-Infinity) compare equal rather than NaN. */
const desc = (x: number, y: number): number => (x > y ? -1 : x < y ? 1 : 0);

const yearKey = (c: Candidate): number => c.year ?? -Infinity;

/** The rerank's keys after relevance: recency, curation completeness, and the row. */
const after = (a: Candidate, b: Candidate): number =>
  desc(yearKey(a), yearKey(b)) || desc(a.completeness, b.completeness) || a.row - b.row;

/** The cut's order: RRF score, best first, and a tie broken by the rerank's keys in its order (module docstring). */
export const byFused = (a: Candidate, b: Candidate): number =>
  desc(a.score, b.score) || desc(a.facetMatches, b.facetMatches) || after(a, b);

/** The rerank's order: facet-match count, RRF score, recency, curation completeness, row (module docstring). */
export const byReranked = (a: Candidate, b: Candidate): number =>
  desc(a.facetMatches, b.facetMatches) || desc(a.score, b.score) || after(a, b);

/** Each row's rank in `list`, read from its score: 1 + the entries that score strictly higher, so equal scores share a
 *  rank. Throws on a row that is not a non-negative integer, a row listed twice, or a score that is not finite. */
export function ranks(list: readonly Ranked[]): Map<number, number> {
  const seen = new Set<number>();
  for (const { row, score } of list) {
    if (!Number.isSafeInteger(row) || row < 0) throw new Error(`a ranked list holds the row ${String(row)}`);
    if (seen.has(row)) throw new Error(`a ranked list holds row ${row} twice`);
    if (!Number.isFinite(score)) throw new Error(`row ${row} has the score ${String(score)}`);
    seen.add(row);
  }
  const sorted = [...list].sort((a, b) => desc(a.score, b.score) || a.row - b.row);
  const out = new Map<number, number>();
  sorted.forEach((r, i) => out.set(r.row, i > 0 && r.score === sorted[i - 1].score ? out.get(sorted[i - 1].row)! : i + 1));
  return out;
}

/** Reciprocal rank fusion of ranked lists (module docstring, "The fusion"): every row any list holds, best first, equal
 *  scores by row. */
export function rrf(lists: readonly (readonly Ranked[])[], k: number = K): Ranked[] {
  const held = new Map<number, number[]>();
  for (const list of lists) {
    for (const [row, rank] of ranks(list)) {
      const rs = held.get(row);
      if (rs == null) held.set(row, [rank]);
      else rs.push(rank);
    }
  }
  return [...held]
    .map(([row, rs]) => ({ row, score: rs.sort((a, b) => a - b).reduce((s, r) => s + 1 / (k + r), 0) }))
    .sort((a, b) => desc(a.score, b.score) || a.row - b.row);
}

/** How many distinct soft facet values `row` carries (module docstring, key 1). */
export function facetMatches(row: RerankRow, soft: SoftFacets): number {
  let n = 0;
  for (const [facet, values] of Object.entries(soft)) {
    const carried = facet === 'domain' ? [row.domain] : facet === 'subdomain' ? [row.subdomain] : (row.facets?.[facet] ?? []);
    for (const v of new Set(values)) if (carried.includes(v)) n++;
  }
  return n;
}

/** How many of the seven flat facet arrays `row` populates (module docstring, key 4). */
export const completeness = (row: RerankRow): number =>
  COMPLETENESS_FACETS.filter((f) => (row.facets?.[f]?.length ?? 0) > 0).length;

/** 08 S5.7 step 4 and 11 S4's rerank: the legs fused at K, the top FUSED_TOP by byFused (`fused`), and of those the top
 *  RERANKED_TOP by byReranked (`top`). `rows` are the facets.json rows the legs' row numbers index. */
export function fuse(legs: Legs, rows: readonly RerankRow[], soft: SoftFacets = {}): { fused: Candidate[]; top: Candidate[] } {
  const lexical = ranks(legs.lexical ?? []);
  const semantic = ranks(legs.semantic ?? []);
  const scored = rrf([legs.lexical ?? [], legs.semantic ?? []]);
  const candidates = scored.map(({ row, score }): Candidate => {
    const r = rows[row];
    if (r == null) throw new Error(`a leg ranks row ${row}, and there are ${rows.length} rows`);
    return {
      row, score, lexical: lexical.get(row) ?? null, semantic: semantic.get(row) ?? null,
      facetMatches: facetMatches(r, soft), year: r.year ?? null, completeness: completeness(r),
    };
  });
  const fused = candidates.sort(byFused).slice(0, FUSED_TOP);
  return { fused, top: [...fused].sort(byReranked).slice(0, RERANKED_TOP) };
}
