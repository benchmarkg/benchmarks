// site/src/lib/landing.ts -- P2-S4-T08 (10 "Information architecture": `/` is the landing; 10 "Performance budget", 08
// S4.3: the landing's summary stats are inlined at build time and it fetches nothing; 10 "Progressive disclosure": every
// view states the entry count behind it). How many entries the index holds, as the landing page's first screen states it,
// read at build time from facets.json, the file every faceted view reads, through the browse view's own reader
// (lib/browse-view.ts readFacets, format 3). No corpus size is ever written into the markup: the page renders what this
// returns, and the count in a build is the number of rows that build's facets.json holds.
//
// Four states, one per kind of build:
//   unbuilt          no facets.json beside the corpus: a site built without `bench build` (the CI job that only builds
//                    the site). The page says it cannot count, rather than printing a zero it did not measure
//   none-published   a facets.json with no row: the published index today, where every entry is still an agent's draft
//                    and 05 S4 publishes none of them
//   published        a facets.json with rows: the published count
//   preview          a draft preview (scripts/preview_corpus.py, UAIBI_SITE_DRAFTS=1): the rows are drafts no person has
//                    verified, and the page says so beside the count, as Base.astro's banner does above it
// A facets.json this view cannot read (another format, not the facets artifact) fails the build, and so does one whose
// `drafts` flag disagrees with the corpus beside it: a landing page must never print a draft count as a published one.
//
// Counting follows docs/methodology.md: every count the index publishes is a family count (02 S11 rule 5), and facets.json
// has one row per benchmark family, so a row is the unit counted. Node loads this module as it is, stripping the types
// (test/landing.test.mjs), so it imports nothing that needs Astro.
import { existsSync, readFileSync } from 'node:fs';
import { readFacets } from './browse-view.ts';

export type SizeState = 'unbuilt' | 'none-published' | 'published' | 'preview';

export interface CorpusSize {
  state: SizeState;
  benchmarks: number | null;      // facets.json's rows; null when the build has no facets.json
  families: number | null;        // the distinct domain families of those rows' primary domains
  familiesTotal: number;          // the domain families taxonomy/ defines
}

/** facets.json at `path`, parsed, or null when the build wrote none. */
export function readFacetsFile(path: string): unknown {
  return existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;
}

/** What the first screen states about the corpus, from a parsed facets.json (null: none built), the number of domain
 *  families taxonomy/ defines, and whether the corpus beside it is a draft preview. Throws on a file it cannot read. */
export function corpusSize(doc: unknown, familiesTotal: number, corpusDrafts: boolean): CorpusSize {
  if (doc == null) return { state: 'unbuilt', benchmarks: null, families: null, familiesTotal };
  const read = readFacets(doc);
  if ('error' in read) throw new Error(`the landing page cannot count the corpus: ${read.error}`);
  if (read.drafts !== corpusDrafts) {
    throw new Error(`facets.json says drafts: ${read.drafts}, but the corpus beside it says drafts: ${corpusDrafts}: `
      + 'the two are not one build. Rerun `uv run bench build` (or scripts/preview_corpus.py for a preview).');
  }
  const benchmarks = read.rows.length;
  const families = new Set(read.rows.map((r) => r.domain)).size;
  const state: SizeState = read.drafts ? 'preview' : benchmarks === 0 ? 'none-published' : 'published';
  return { state, benchmarks, families, familiesTotal };
}

/** A count as 09 S11.4 writes one: locale `en`, a comma thousands separator at 10,000 and above, none below. */
export function formatCount(n: number): string {
  return n >= 10_000 ? n.toLocaleString('en-US') : String(n);
}

/** "1 benchmark" or "N benchmarks". */
export const benchmarksWord = (n: number) => (n === 1 ? 'benchmark' : 'benchmarks');
