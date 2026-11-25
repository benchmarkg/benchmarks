// site/src/islands/search/lexical.ts -- P6-S1-T04 (11 S4 "The pipeline", step 2; 08 S5.5, S5.7 "The fusion order",
// step 2). The BM25 leg of the faceted query pipeline: MiniSearch over the rows of the already-loaded facets.json, which
// returns the rows that match a free-text query, best first, each with its BM25+ score, for the fusion step to read. It
// is the site's one BM25 implementation: lib/query.ts runs it as step 2 and fuses its list at RRF k = 60, and the Phase 6
// fusion (islands/search/fusion.ts, P6-S1-T05) is to read the same list. It is not the site-wide search box: that is
// Pagefind, over every page, and 08 S5.5 keeps the two apart -- MiniSearch is here because the fusion needs BM25
// *scores*, which Pagefind does not expose. Nothing here reads or changes Pagefind.
//
// The fields. 11 S4 names five: "name, aliases, edition names, description and maintainer"; 08 S5.7 names "name,
// aliases, one-line summary". The leg reads only what facets.json carries, because that is the file every faceted view
// has already loaded, and facets.json format 3 (tools/build/emit.py) carries three of them: `name`, `aliases`, and
// `editions` -- the name of every BenchmarkVersion whose version_kind is `edition`, added to facets.json for this leg,
// which is how 11 S4 puts editions into retrieval: "as alias strings on the family's lexical record", so that CASP17 is
// found on the CASP row. The leg indexes those three and the row's `id`, the benchmark's slug, which is how a benchmark
// is often written (`swe-bench-verified`); in two rows of the preview it holds a word no name does (`davis-vos`).
//
// Left out, and why. What each candidate field adds to facets.json, measured on the 320-entry draft preview
// (scripts/preview_corpus.py, 2026-11-24; gzip -9 of the emitter's canonical bytes) against format 2's 29,568 bytes:
//
//   editions      +6,387 B gz (20 B a row)    added: format 3 is 35,955 B (36,203 at gzip -6), inside the budget
//   maintainer   +12,064 B gz (38 B a row)    left out: governance.maintainer, 305 distinct display strings of 319
//   tagline      +17,419 B gz (54 B a row)    left out: the one-line summary 08 S5.7 names (113 characters a row)
//   description +176,578 B gz (552 B a row)  left out: six times the whole of facets.json
//
// The budget is the one figure 10 "Performance budget" gives facets.json, 36 KB gzipped (36,864 B): the data the landing
// and V11 routes fetch, whose JS budgets (40 and 60 KB) are counted over it, and 08 S4.2's size at 1,500 entries. Only
// editions fits beside format 2's rows; any one of the other three breaks it at 320 entries. Indexing them needs either
// a leaner facets.json or the leg reading corpus.json, which 08 S4.2 loads lazily on entering the AI panel; that is a
// decision for whoever wires the panel, and adding them here is then a change to LEXICAL_FIELDS and BOOST alone. Note
// that format 2 alone is already 3.7 times the 8 KB 08 S4.2 extrapolates for 320 entries (92 B a row, not 24), so the
// 36 KB is spent at about 400 rows with or without editions (about 330 with them).
//
// Boosting (BOOST). A field's boost multiplies the score of every match in it. The values follow one rule, how directly
// the field names the row's benchmark, and are not tuned on the corpus: the name 3; an alias, another name of the same
// benchmark, 2; an edition name, which names one edition of the family rather than the family, 1.5; the id 1, because
// it mostly re-spells the name, whose matches already carry the name's boost. And a row that the query names word
// for word -- the query, tokenized and normalised as the index is, equals its name, one of its aliases or edition
// names, or its id -- has its score multiplied by EXACT_BOOST (10, an order of magnitude). Without it BM25 ranks
// MMLU-Pro above MMLU for `mmlu`, because MMLU-Pro's aliases repeat the word and MMLU's spell it out; 11 S4 calls
// version disambiguation "an exact-match problem", which is what the alias table and BM25 are for. The frozen fixture
// (test/fixtures/lexical-bm25.json) holds the effect of every one of these values, so changing one is a visible change
// to an expected score, and test/lexical.bm25.test.mjs checks over the fixture's every row that each of its names, as
// a query, puts the row first (over the whole preview, 7 of its 1,609 such queries fail with EXACT_BOOST at 1, none
// from 3).
//
// Fuzzy and prefix matching. Every query term matches a token exactly, as the token's prefix (type-ahead: `lanc` finds
// SWE-Lancer), and, for a term of FUZZY_MIN_LENGTH (5) characters or more with no digit in it, within an edit distance
// of FUZZY (0.2, the fraction MiniSearch itself uses for `fuzzy: true`) of its length, rounded and capped at MAX_FUZZY
// (2): one edit for a term of 5 to 7 characters, two from 8 (`agentbnch` finds AgentBench). The two exceptions are
// where an edit is not a typo. Benchmark names are dense with short acronyms one edit apart -- MMLU and MMMU, NLE and
// HLE -- and an acronym one letter off is another benchmark. And a digit is an edition or a version: CASP16 is one
// edit from CASP17 and WMT23 from WMT24, and a fuzzy CASP16 would find CAPRI's every CASP round before CASP itself. A
// prefix match scores PREFIX_WEIGHT (0.375) and a fuzzy one FUZZY_WEIGHT (0.45) of an exact one, each falling with the
// distance (MiniSearch's defaults, stated here so a release cannot move them).
//
// Terms are lowercased and stripped of diacritics, in the index and in the query alike, so `montreal` matches
// `Montréal`; MiniSearch's own tokenizer splits on whitespace and punctuation, so `swe-bench` is `swe` and `bench`.
//
// Scoring. BM25+ at BM25_PARAMS (k1 = 1.2, b = 0.7, delta = 0.5; MiniSearch's defaults, stated so they cannot move):
// a row's score is the sum over the query terms of IDF x the saturated, length-normalised term frequency x the field's
// boost x the match's weight, times the number of query terms that matched it, so a row matching both words of a
// two-word query outranks one matching either. Any term may match (OR). The index is built once over every row and the
// survivors of the facet filter only restrict which rows it returns, so IDF and the average field lengths are the whole
// index's and a row's score does not move with the facet selection. Equal scores are ordered by row number, never by
// MiniSearch's map order, so the list is a pure function of the rows, the query and the survivors.
import MiniSearch from 'minisearch';
import { has, type Bitset } from '../../lib/facet-index.ts';

/** What the leg reads of a facets.json row (tools/build/emit.py FACET_ROW, format 3). `editions` is optional only so
 *  that a caller's hand-made row need not carry it; every facets.json row does. */
export interface LexicalRow {
  id: string;
  name: string;
  aliases: readonly string[];
  editions?: readonly string[];
}

/** The fields the leg indexes, all from facets.json (module docstring, "The fields"). */
export const LEXICAL_FIELDS = ['name', 'aliases', 'editions', 'id'] as const;
export type LexicalField = (typeof LEXICAL_FIELDS)[number];

/** Each field's boost (module docstring, "Boosting"): how directly the field names the row's benchmark. */
export const BOOST: Readonly<Record<LexicalField, number>> = { name: 3, aliases: 2, editions: 1.5, id: 1 };
/** The factor on the score of a row the query names word for word: its name, an alias, an edition name or its id. */
export const EXACT_BOOST = 10;

/** The fuzzy edit distance, as a fraction of the query term's length (MiniSearch's own `fuzzy: true` value). */
export const FUZZY = 0.2;
/** Query terms shorter than this match exactly or as a prefix, never fuzzily: short acronyms one edit apart are other
 *  benchmarks (MMLU, MMMU; NLE, HLE). Nor does a term with a digit: one edit from CASP16 is CASP17. */
export const FUZZY_MIN_LENGTH = 5;
/** The largest edit distance any term is allowed. */
export const MAX_FUZZY = 2;
/** A prefix match's and a fuzzy match's weight against an exact match's 1 (MiniSearch's defaults). */
export const PREFIX_WEIGHT = 0.375;
export const FUZZY_WEIGHT = 0.45;
/** BM25+'s parameters: k1, b and delta (MiniSearch's defaults). */
export const BM25_PARAMS = { k: 1.2, b: 0.7, d: 0.5 } as const;

/** The fuzziness MiniSearch is given for one query term: FUZZY from FUZZY_MIN_LENGTH characters with no digit, else
 *  none. */
export const fuzziness = (term: string): number | false => (term.length >= FUZZY_MIN_LENGTH && !/\p{N}/u.test(term) ? FUZZY : false);

/** One term as indexed and as queried: lowercased, its diacritics stripped (NFKD, then the combining marks dropped). */
export const normalise = (term: string): string => term.normalize('NFKD').replace(/\p{M}+/gu, '').toLowerCase();

const tokenize = MiniSearch.getDefault('tokenize') as (text: string) => string[];

/** A text as the index sees it, word for word: its tokens, normalised, joined by one space. */
export const phrase = (text: string): string => tokenize(text).map(normalise).filter(Boolean).join(' ');

interface LexicalDoc {
  row: number;
  id: string;
  name: string;
  aliases: string;
  editions: string;
  exact: string[];          // stored, not indexed: the phrases a query may name the row by (EXACT_BOOST)
}

export type LexicalIndex = MiniSearch<LexicalDoc>;

/** The index over `rows`, whose document ids are row numbers: a row's position in `rows`, as in the facet bitsets. */
export function buildLexicalIndex(rows: readonly LexicalRow[]): LexicalIndex {
  const index = new MiniSearch<LexicalDoc>({
    idField: 'row',
    fields: [...LEXICAL_FIELDS],
    storeFields: ['exact'],
    processTerm: (term) => normalise(term) || null,
    searchOptions: {
      boost: { ...BOOST },
      prefix: true,
      fuzzy: fuzziness,
      maxFuzzy: MAX_FUZZY,
      weights: { prefix: PREFIX_WEIGHT, fuzzy: FUZZY_WEIGHT },
      combineWith: 'OR',
      bm25: { ...BM25_PARAMS },
    },
  });
  index.addAll(rows.map((r, row) => ({
    row, id: r.id, name: r.name, aliases: (r.aliases ?? []).join(' '), editions: (r.editions ?? []).join(' '),
    exact: [...new Set([r.name, ...(r.aliases ?? []), ...(r.editions ?? []), r.id].map(phrase))],
  })));
  return index;
}

/** A row and its score in one ranked list: what the fusion step reads. */
export interface Ranked {
  row: number;
  score: number;
}

/** Best first; equal scores by row. */
export const byScore = (a: Ranked, b: Ranked): number => b.score - a.score || a.row - b.row;

/** The rows matching `query`, best first, with their BM25+ scores; only rows in `survivors` when it is given, and none
 *  for a blank query. */
export function bm25(index: LexicalIndex, query: string, survivors?: Bitset): Ranked[] {
  if (query.trim() === '') return [];
  const named = phrase(query);
  const boostDocument = (_row: unknown, _term: string, stored?: Record<string, unknown>) =>
    ((stored?.exact as string[] | undefined)?.includes(named) ? EXACT_BOOST : 1);
  const filter = survivors == null ? undefined : (r: { id: unknown }) => has(survivors, r.id as number);
  return index.search(query, filter == null ? { boostDocument } : { boostDocument, filter })
    .map((r) => ({ row: r.id as number, score: r.score }))
    .sort(byScore);
}
