// site/src/lib/suite-basket.ts -- P6-S4-T01 (10 V10 "Two words, used precisely throughout", "Basket persistence"; 10
// "Filter state encoding"). The Suite Builder's basket, pure and DOM-free: islands/SuiteBuilder.tsx renders it, and
// test/suite-basket.test.mjs drives it under Node, which loads it as it is, stripping the types.
//
// The basket is the working selection inside /suite/ -- "mutable, URL-encoded, thrown away when the tab closes" -- and
// never the citable object: that is the suite manifest a basket exports (10 V10; 11 F3), which this module knows nothing
// of. Its one home is the query string, as 10's grammar key `b`, a term list like any other (lib/filter-url.ts TERM_KEYS):
// benchmark ids, comma-joined, sorted, each once, so one basket always produces exactly one URL, and the page's other
// keys (the filter pane's d, c, em, lc and q) sit beside it in the same canonical query. No second codec: every link to
// a basket is filter-url.ts encode() of `{ b: ids }`, and every reading of one is its decode().
//
//   /suite/?b=gaia,swe-bench,tau2-bench&v=1
//
// An id the link names that the build's index does not have is the grammar's unknown value: decode() with the index's
// ids as the vocabulary of `b` leaves it out of the basket and returns it as `ignored`, which the page shows as filter-url
// ignoredNotice()'s visible "ignored filter: b=..." rather than dropping it silently.
//
// localStorage is a convenience and never the source of truth (10 V10: "The URL is the source of truth, so a suite is
// shareable, citable and reproducible without any server state"). The page writes the basket there on every change the
// reader makes, and reads it once, on arrival, only to offer what it holds that the URL's basket does not: a page opened
// at a bare /suite/ starts empty, as its URL says, and a link from the Atlas starts with the Atlas's selection, each with
// a visible offer to add the entries this browser last kept. Arriving is not a change, so opening someone's link never
// overwrites the basket kept here. Every read and write is wrapped: private windows and blocked storage throw, and the
// page then simply has no offer to make.
import { decode, encode, type FilterState, type Vocabularies } from './filter-url.ts';

/** The Suite Builder's route (10 "Information architecture": /suite/ is V10). */
export const SUITE_PATH = '/suite/';

/** The localStorage key the basket is mirrored under. */
export const STORE_KEY = 'uaibi:suite-basket';

/** The link to a basket: /suite/ with the basket as `b` beside any other keys of `rest`, in canonical form. The Atlas's
 *  "Add to suite basket" link (islands/AtlasSelection.tsx) writes the same `/suite/?` + encode({ b: ids }) inline, since
 *  a byte there counts against the Atlas's 120 KB; the Coverage Map's add-from-cell (10 V2, P4-S3-T01's brush) is to call
 *  this with the cell's benchmark ids. */
export function suiteHref(ids: readonly string[], rest: FilterState = {}): string {
  const q = encode({ ...rest, b: [...ids] });
  return q.length > 0 ? `${SUITE_PATH}?${q}` : SUITE_PATH;
}

/** A basket as the URL holds it: the state's `b`, canonical (sorted, each once), or the empty basket. */
export const basketOf = (state: FilterState): string[] => state.b ?? [];

/** The state with its basket replaced by `ids`; an empty basket is an absent key, as the grammar has it. */
export function withBasket(state: FilterState, ids: readonly string[]): FilterState {
  const out: FilterState = { ...state };
  const b = [...new Set(ids)].sort();
  if (b.length > 0) out.b = b;
  else delete out.b;
  return out;
}

/** The state with `ids` added to its basket (each once). */
export const added = (state: FilterState, ids: readonly string[]) => withBasket(state, [...basketOf(state), ...ids]);

/** The state with `id` taken out of its basket. */
export const removed = (state: FilterState, id: string) => withBasket(state, basketOf(state).filter((x) => x !== id));

/** The vocabularies a query string is read with once the index has loaded: the filter keys' terms, and the index's
 *  benchmark ids as the vocabulary of `b`, so an id the index does not have is returned as ignored. */
export const withIds = (vocab: Vocabularies, ids: Iterable<string>): Vocabularies => ({ ...vocab, b: new Set(ids) });

/** What the basket kept in this browser holds, or [] when nothing is kept or storage cannot be read. */
export function stored(storage: Pick<Storage, 'getItem'> | null | undefined): string[] {
  try {
    const raw = storage?.getItem(STORE_KEY);
    return raw ? basketOf(decode(raw).state) : [];
  } catch {
    return [];
  }
}

/** Mirror the basket to this browser's storage, in the same canonical form as the URL; an empty basket is removed.
 *  False when storage cannot be written (a private window, blocked site data), which costs only the convenience. */
export function store(storage: Pick<Storage, 'setItem' | 'removeItem'> | null | undefined, ids: readonly string[]): boolean {
  try {
    if (storage == null) return false;
    const q = encode({ b: [...ids] });
    if (q.length > 0) storage.setItem(STORE_KEY, q);
    else storage.removeItem(STORE_KEY);
    return true;
  } catch {
    return false;
  }
}

/** The entries kept in this browser that the URL's basket lacks: what the page offers to add, never adds by itself. */
export const offer = (kept: readonly string[], basket: readonly string[]): string[] => {
  const have = new Set(basket);
  return kept.filter((id) => !have.has(id));
};

/** The least of a facets.json row the search box reads. */
export interface Searchable { id: string; name: string; aliases: readonly string[] }

const fold = (s: string) => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');

/** Whether `row` answers the free-text query `q` (10's key q): every whitespace-separated word of it, case and accents
 *  folded, occurs in the row's name, one of its aliases or its id. An empty query matches every row. This is the filter
 *  pane's own lexical match over facets.json, not the site search's ranked tiers (islands/search/). */
export function answers(row: Searchable, q: string | undefined): boolean {
  const words = fold(q ?? '').split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const hay = [row.name, row.id, ...row.aliases].map(fold);
  return words.every((w) => hay.some((h) => h.includes(w)));
}
