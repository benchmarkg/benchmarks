// site/src/lib/pagefind.ts -- P2-S4-T06 (08 S3.2 "S12 search index", S7.5 Decision 2; 10 V11 Tier 1). S12: Pagefind in
// both of its modes, into one index, at the end of every `astro build` (astro.config.mjs registers pagefindIntegration).
//
// 08 S3.2: "Pagefind runs in both of its modes, into one index." In order, over the dist/ the build just wrote:
//
//   1. addCustomRecord() for every entity route the build rendered: benchmarks, systems, organizations, metrics and
//      taxonomy terms. tools/build/pagefind_records.py builds the records from validated YAML -- the corpus this build
//      rendered from (lib/corpus.ts CORPUS_PATH) and the taxonomy/ it read -- so facets become Pagefind filters and the
//      index cannot drift from the data model. In a full build every record must have its page, and one without is a
//      failure; a BENCH_ROUTES preview (lib/bench-routes.ts) renders some entity routes only, and indexes those.
//   2. addDirectory() over dist/: the crawl, for the narrative pages that exist only as HTML. Every entity route's
//      <body> carries data-pagefind-ignore (layouts/Base.astro `search`), so the crawl skips exactly the pages the
//      records cover; so do the unindexed families of 08 S7.5 Decision 2 (/browse/, version-pinned views). The crawl
//      keeps a page beside a record at the same URL rather than replacing it, so a page that lost its ignore is indexed
//      twice, which is what the check looks for. (addHTMLFile() would not do: the API keeps one entry per URL, the last
//      given, so a crawled entity page would silently replace its record, or a record its page. Measured 2026-11-24.)
//   3. writeFiles() into dist/pagefind/, cleared first, so no fragment of an earlier build survives into this one.
//      forceLanguage makes it one index: a crawled page without lang="en" would otherwise start a second.
//   4. scripts/check_pagefind_urls.py over dist/: the indexed URLs equal the rendered routes -- every entity route once,
//      by its record; every narrative route once, by the crawl; nothing twice -- or the build fails. This is 08 S3.2's
//      "CI assertion": it runs wherever the site builds, the pull-request workflow's site build among them.
//
// The Python both steps run is BENCH_PYTHON (CI's locked environment, a test's interpreter), else `uv run python`, the
// repository's own: the records need the taxonomy models (schema/), so a bare `python` without them cannot build them.
// Scripts resolve from the checkout Astro builds in (process.cwd() is site/), not from REPO_ROOT, which a test may point
// at a fixture tree that has no tools/.
//
// Pagefind 1.6.0, not the 1.5.2 08 names (docs/pins.md note 6): 1.5.2 writes its filter files in a different order on
// every run, so two builds of one tree wrote different bundles, and 08 S3.1 lists S12 as deterministic; 1.6.0 writes one
// bundle, byte for byte (four runs over a 923-page dist with 457 records, 2026-11-24). Its `maxFragments` is left unset,
// so there is one .pf_fragment per indexed page, which 08 S7.5's file-count table and the check both read. Node strips
// this file's types itself, so tests drive writeIndex() over hand-made dists without Astro.
import { spawnSync } from 'node:child_process';
import { readdirSync, rmSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as pagefind from 'pagefind';
import type { AstroIntegration } from 'astro';
import { benchRoutes } from './bench-routes.ts';
import { CORPUS_PATH } from './corpus.ts';

type Env = Record<string, string | undefined>;

export const BUNDLE = 'pagefind';
export const LANGUAGE = 'en';
export const RECORDS_ARTIFACT = 'pagefind-records';
export const RECORDS_FORMAT = 1;
export const RECORD_TYPES: readonly string[] = ['benchmark', 'system', 'organization', 'metric', 'term'];

export interface SearchRecord {
  url: string;
  content: string;
  language: string;
  meta: Record<string, string>;
  filters: Record<string, string[]>;
  sort?: Record<string, string>;
}

export interface RecordsDoc {
  artifact: typeof RECORDS_ARTIFACT;
  format: number;
  language: string;
  drafts: boolean;
  counts: Record<string, number>;
  records: SearchRecord[];
}

export interface IndexSummary {
  records: number;          // custom records added
  skipped: string[];        // records whose route this (BENCH_ROUTES) build did not render
  crawled: number;          // HTML files the crawl read; the ignored ones add nothing
  bundle: string;           // dist/pagefind/
}

const CHECKOUT = resolve(process.cwd(), '..');
const REPO_ROOT = process.env.REPO_ROOT ?? CHECKOUT;

/** The interpreter and leading arguments every Python step runs with. */
export function python(env: Env = process.env): [string, string[]] {
  return env.BENCH_PYTHON ? [env.BENCH_PYTHON, []] : ['uv', ['run', '--quiet', 'python']];
}

function run(args: string[], env: Env, what: string): string {
  const [cmd, lead] = python(env);
  const r = spawnSync(cmd, [...lead, ...args], { cwd: CHECKOUT, env: { ...process.env, ...env, PYTHONUTF8: '1' },
    encoding: 'utf8', maxBuffer: 512 * 1024 * 1024 });
  if (r.error) throw new Error(`${what}: could not run ${cmd} (${r.error.message}); set BENCH_PYTHON to the repository's Python`);
  if (r.status !== 0) throw new Error(`${what} failed (exit ${r.status}):\n${r.stdout ?? ''}${r.stderr ?? ''}`);
  return r.stdout;
}

/** A records document as tools/build/pagefind_records.py writes it, checked: one language, known types, one record per URL. */
export function parseRecords(text: string): RecordsDoc {
  const doc = JSON.parse(text) as RecordsDoc;
  if (doc.artifact !== RECORDS_ARTIFACT || doc.format !== RECORDS_FORMAT || !Array.isArray(doc.records)) {
    throw new Error(`not the ${RECORDS_ARTIFACT} document tools/build/pagefind_records.py writes (format ${RECORDS_FORMAT})`);
  }
  const seen = new Set<string>();
  for (const r of doc.records) {
    if (r.language !== LANGUAGE) throw new Error(`${r.url}: a record in ${r.language}, but the index is one, in ${LANGUAGE}`);
    if (!RECORD_TYPES.includes(r.filters?.type?.[0] ?? '')) throw new Error(`${r.url}: type ${r.filters?.type} is not a record type`);
    if (seen.has(r.url)) throw new Error(`${r.url}: two records, which the index would answer twice`);
    seen.add(r.url);
  }
  return doc;
}

/** The records for the corpus this build rendered from and the taxonomy it read. */
export function loadRecords(env: Env = process.env): RecordsDoc {
  const args = [join(CHECKOUT, 'tools', 'build', 'pagefind_records.py'), '--corpus', CORPUS_PATH, '--root', REPO_ROOT];
  if (env.UAIBI_SITE_DRAFTS === '1') args.push('--drafts');           // lib/corpus.ts has already allowed the preview
  return parseRecords(run(args, env, 'tools/build/pagefind_records.py'));
}

/** Every page under `dist` as Pagefind spells a crawled page's URL: 'docs/x/index.html' -> '/docs/x/', 'index.html' ->
 *  '/', '404.html' -> '/404.html' (scripts/check_pagefind_urls.py page_url). */
export function renderedRoutes(dist: string): Set<string> {
  const out = new Set<string>();
  const walk = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, e.name);
      if (e.isDirectory()) {
        if (path !== join(dist, BUNDLE)) walk(path);
      } else if (e.name.endsWith('.html')) {
        const rel = relative(dist, path).split(sep).join('/');
        out.add('/' + (rel === 'index.html' ? '' : rel.endsWith('/index.html') ? rel.slice(0, -'index.html'.length) : rel));
      }
    }
  };
  walk(dist);
  return out;
}

/** Steps 1-3: the records whose routes `dist` holds, then the crawl, written to dist/pagefind/. `restricted` is a
 *  BENCH_ROUTES build, where a record may lack its page; anywhere else that is a failure. */
export async function writeIndex(dist: string, doc: RecordsDoc, restricted: boolean): Promise<IndexSummary> {
  const bundle = join(dist, BUNDLE);
  rmSync(bundle, { recursive: true, force: true });
  const routes = renderedRoutes(dist);
  const skipped = doc.records.filter((r) => !routes.has(r.url)).map((r) => r.url);
  if (skipped.length > 0 && !restricted) {
    throw new Error(`${skipped.length} search record(s) name a route this build did not render, e.g. ${skipped.slice(0, 5).join(', ')}: `
      + 'the records and the pages disagree (rerun `bench build`, or the site reads another corpus or taxonomy than the records)');
  }
  const { index, errors } = await pagefind.createIndex({ forceLanguage: LANGUAGE });
  try {
    if (index == null) throw new Error(`pagefind: no index (${errors.join('; ')})`);
    let records = 0;
    for (const r of doc.records) {
      if (!routes.has(r.url)) continue;
      const added = await index.addCustomRecord(r);
      if (added.errors.length > 0) throw new Error(`pagefind: ${r.url}: ${added.errors.join('; ')}`);
      records += 1;
    }
    const crawl = await index.addDirectory({ path: dist });
    if (crawl.errors.length > 0) throw new Error(`pagefind: the crawl of ${dist}: ${crawl.errors.join('; ')}`);
    const written = await index.writeFiles({ outputPath: bundle });
    if (written.errors.length > 0) throw new Error(`pagefind: writing ${bundle}: ${written.errors.join('; ')}`);
    return { records, skipped, crawled: crawl.page_count, bundle };
  } finally {
    await pagefind.close();
  }
}

/** Step 4: scripts/check_pagefind_urls.py over `dist`; its report, or a throw carrying it. */
export function checkIndex(dist: string, env: Env = process.env): string {
  return run([join(CHECKOUT, 'scripts', 'check_pagefind_urls.py'), '--dist', dist], env, 'scripts/check_pagefind_urls.py').trim();
}

/** S12 as an Astro integration: after the pages are written, the index is built over them and checked. */
export function pagefindIntegration(): AstroIntegration {
  return {
    name: 'uaibi-pagefind',
    hooks: {
      'astro:build:done': async ({ dir, logger }) => {
        const dist = fileURLToPath(dir);
        const doc = loadRecords();
        const s = await writeIndex(dist, doc, benchRoutes() != null);
        logger.info(`S12: ${s.records} record(s) (${Object.entries(doc.counts).map(([k, n]) => `${n} ${k}`).join(', ')}`
          + `${s.skipped.length > 0 ? `; ${s.skipped.length} without a page in this BENCH_ROUTES build` : ''}) and the crawl of `
          + `${s.crawled} page(s), one index in ${s.bundle}`);
        logger.info(checkIndex(dist));
      },
    },
  };
}
