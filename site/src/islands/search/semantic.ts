// site/src/islands/search/semantic.ts -- P6-S1-T09 (10 V11 "Search: three tiers", the ordering rule; 11 F0 "Made
// visible", S4 "First-query latency" item 3; 09 S11.5). The semantic tier as the search box's later tier
// (islands/SearchBox.tsx LaterTier, addLaterTier()): what components/SemanticResults.astro adds to the box once the
// loader (islands/search/loader.ts) has the stack, and what the box renders as its own labelled block.
//
// 10 V11: "the semantic tier loads in the background and, once ready, *appends* a 'related benchmarks you did not type
// the words for' block"; 11 F0: "the two result sets are rendered as separate, labelled blocks, not fused into one
// mystery list". So the tier is a list of its own, under SEMANTIC_HEADING, after the lexical one: never merged into it,
// never reordering it, and without the pages it already shows (SearchBox.tsx drops those). Its rows are ranked here and
// nowhere else, by the cosine of the query's vector to each document vector (islands/search/cosine.ts) over every row,
// since /search/ applies no facet filter; the reciprocal rank fusion of islands/search/fusion.ts is the faceted query
// pipeline's, which ranks one list for the AI layer, and is not how these two blocks are shown.
//
// What a row is shown as. vectors.meta.json names each row by its benchmark id and nothing else, and the search page
// loads no facets.json, so the page carries the rest: SemanticResults.astro writes, only in a build that ships the
// vectors, an entry table of [id, name] for every benchmark whose page the build rendered (entryTable(), entriesJson()),
// and a row the table does not name -- a page a BENCH_ROUTES preview left out -- is skipped rather than linked.
//
// What it does not do. It sets no similarity floor: that would be a number tuned on this corpus, which 08 S5.7 rules
// out, so the block holds the nearest rows whatever they are, and a query none of whose tokens the encoder holds (the
// zero vector) gets no list and so no block. It does not explain a ranking or show a score.
import type { Hit, LaterTier } from '../SearchBox.tsx';
import type { Ranked } from './lexical.ts';
import type { Matrix } from './cosine.ts';
import type { SemanticStack } from './loader.ts';

/** The tier's id in the box: its block is [data-tier="semantic"]. */
export const SEMANTIC_ID = 'semantic';
/** What the box's one-line notice calls it when it cannot answer (09 S11.5). */
export const SEMANTIC_NAME = 'Semantic search';
/** The block's label, 10 V11's words: related entries the reader did not type the words for. */
export const SEMANTIC_HEADING = 'Related benchmarks you did not type the words for';
/** One line under it: how they were found, and that the list above is untouched. */
export const SEMANTIC_NOTE = 'Close in meaning to your query, found without matching its words. The word matches above are unchanged.';
/** How many rows the tier returns, best first: twice the box's STEP, so its block still has rows to show once the box
 *  has dropped those the lexical list already shows. The box shows at most STEP of them. */
export const SEMANTIC_TOP = 20;

/** A benchmark as the block links it. */
export interface Entry {
  url: string;
  title: string;
}

/** The page's entry table, [id, name] pairs (SemanticResults.astro), as a map from id. */
export type Entries = ReadonlyMap<string, Entry>;

/** A benchmark's page. */
export const benchmarkUrl = (id: string): string => `/benchmarks/${id}/`;

/** [id, name] for every benchmark whose page `rendered` says the build wrote, in the order given. */
export function entryTable(rows: readonly { id: string; name: string }[], rendered: (url: string) => boolean): [string, string][] {
  return rows.filter((r) => rendered(benchmarkUrl(r.id))).map((r) => [r.id, r.name]);
}

/** The table as JSON safe inside a <script type="application/json">: no `<` survives, so no `</script>` can. */
export const entriesJson = (table: readonly (readonly [string, string])[]): string => JSON.stringify(table).replace(/</g, '\\u003c');

/** The entry table read back; anything that is not a list of [id, name] string pairs is no entry. */
export function readEntries(json: string | null | undefined): Map<string, Entry> {
  const out = new Map<string, Entry>();
  if (json == null || json.trim() === '') return out;
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch {
    return out;
  }
  if (!Array.isArray(raw)) return out;
  for (const pair of raw) {
    if (Array.isArray(pair) && pair.length === 2 && typeof pair[0] === 'string' && typeof pair[1] === 'string' && pair[0] !== '') {
      out.set(pair[0], { url: benchmarkUrl(pair[0]), title: pair[1] });
    }
  }
  return out;
}

/** The ranked rows as hits, best first, at most SEMANTIC_TOP, skipping a row the entry table does not name. */
export function semanticHits(ranked: readonly Ranked[], vectors: Pick<Matrix, 'ids'>, entries: Entries): Hit[] {
  const hits: Hit[] = [];
  for (const { row } of ranked) {
    const e = entries.get(vectors.ids[row]);
    if (e == null) continue;
    hits.push({ url: e.url, title: e.title, type: 'benchmark', excerpt: '' });
    if (hits.length === SEMANTIC_TOP) break;
  }
  return hits;
}

const aborted = (signal: AbortSignal) => new DOMException(String(signal.reason ?? 'a later keystroke has asked'), 'AbortError');

/** The tier over a loaded stack, or null when the stack has no document vectors (every build without `bench build
 *  --embed`) or the page names no entry: then there is nothing to rank and no block, ever. */
export async function semanticTier(stack: SemanticStack, entries: Entries): Promise<LaterTier | null> {
  const vectors = stack.vectors;
  if (vectors == null || entries.size === 0) return null;
  const { cosine } = await import('./cosine.ts');     // loaded already: the loader imported it for the vectors
  return {
    id: SEMANTIC_ID,
    name: SEMANTIC_NAME,
    heading: SEMANTIC_HEADING,
    note: SEMANTIC_NOTE,
    search: async (query, signal) => {
      if (signal.aborted) throw aborted(signal);
      return semanticHits(cosine(vectors, stack.encoder.encode(query)), vectors, entries);
    },
  };
}

/** The tier when the load failed in a build that ships the vectors: every question is answered with the failure, which
 *  the box shows as its one-line notice, the results above it unchanged (09 S11.5). */
export function unavailableTier(reason: string): LaterTier {
  return {
    id: SEMANTIC_ID,
    name: SEMANTIC_NAME,
    heading: SEMANTIC_HEADING,
    note: SEMANTIC_NOTE,
    search: () => Promise.reject(new Error(reason)),
  };
}
