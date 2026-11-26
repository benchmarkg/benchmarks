// site/tests/e2e/worker-offline.spec.ts -- P6-S1-T08 (14 Phase 6 "Exit criteria", the first: "With the Worker disabled,
// facet search, lexical search and semantic search all still work and the site remains fully useful, readable and
// citable"; 11 S1 "The degradation contract has three tiers, not two"). Tier 1 and Tier 0 with the Worker unreachable, in
// a browser, over the draft preview playwright.config.ts builds:
//
//   cd site && npm run test:e2e -- worker-offline
//
// That is the ledger's verify. test:e2e (package.json) is `playwright test` under the site's own playwright.config.ts,
// with its server and its three projects, so the argument is Playwright's filter on spec files: it picks this spec out of
// tests/, and it runs in the `js` project (its JavaScript-off checks open their own context, as tests/search.spec.ts
// does). Done when: "The test passes with the Worker unreachable, which is exit criterion 1 made executable." Held here:
//
//   - the Worker is unreachable: every browser context a test opens refuses every request to the Worker's routes at the
//     network layer (BrowserContext.route, before the request leaves the browser) as a refused connection, and records
//     it. The routes are /api/* and /mcp: 11 S3 scopes run_worker_first to those two, so every other path is a file the
//     CDN serves;
//   - Tier 1 works from those files alone: the browse view's facet filter narrows /benchmarks/ to the rows facets.json
//     says carry the term; Pagefind answers a query on /search/ with the benchmark it names, from the files under
//     /pagefind/; and the semantic block appears under its own heading with the row the cosine ranks first;
//   - Tier 0: a benchmark's page renders and cites with JavaScript off (its citation block cites its id, with a permalink
//     at the 40-digit commit the footer prints and BibTeX naming that commit), and with JavaScript on it names no script
//     file and the browser fetches 0 bytes of script;
//   - no page of any test asked the Worker for anything, checked once the page has gone quiet (network idle).
//
// The failure cases are checked as failures, as the other specs check theirs: a /search/ doctored to call /api/ on the
// first keystroke, as an AI layer that did not degrade would, still gets its word-match answer while its call is refused,
// and the check reports the call; a benchmark page doctored to load an image from /api/ is reported with JavaScript off;
// and the zero-byte measurement comes out above zero on /search/, which ships the box.
//
// The draft preview ships no document vectors (scripts/preview_corpus.py runs no S6, and no build ships them today), so
// for the semantic block this spec does what tests/semantic-results.spec.ts does: it serves /search/ as a build with
// vectors would, with data-vectors="shipped" and the component's entry table (semantic.ts entryTable() and
// entriesJson()), and serves made-up /embed/vectors.meta.json and vectors.i8.bin in tools/build/embed.py's format, one row
// per row of the preview's facets.json. Every row is noise except one: the query's own vector, encoded by the encoder the
// page runs (islands/search/encoder.ts over public/embed/), put in a row the word-match answer does not show, once that
// answer is on screen. The vectors are files under /embed/, so they come from the test, not from the Worker.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';
import { QueryEncoder, dequantise } from '../../src/islands/search/encoder.ts';
import { SEMANTIC_HEADING, entriesJson, entryTable } from '../../src/islands/search/semantic.ts';

interface Row { id: string; name: string; aliases: string[]; editions?: string[]; facets: Record<string, string[]> }
interface Term { id: string; key: string }

const READY_MS = 60_000;
const LEXICAL_HEADING = 'Results matching your words';
const BLOCK = '[data-tier="semantic"]';
const VECTORS_META = '/embed/vectors.meta.json';
const VECTORS_BIN = '/embed/vectors.i8.bin';
// the citation block's permalink: the entry's YAML at a full commit (tests/citable-urls.spec.ts PERMALINK)
const PERMALINK = /^https:\/\/github\.com\/[^/]+\/[^/]+\/blob\/([0-9a-f]{40})\/(data\/benchmarks\/.+\.yaml)$/;

// build/preview/ is written by the web server's build, so it is read lazily, once that has run
const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../../build/preview/${name}`, import.meta.url)), 'utf8'));
let rows: Row[] | undefined;
const ROWS = () => (rows ??= (preview('facets.json') as { benchmarks: Row[] }).benchmarks);
const url = (r: Row) => `/benchmarks/${r.id}/`;

/** The benchmark the queries name: a one-word name no other row's name, aliases, editions or id contains
 *  (tests/search.spec.ts target()), so Pagefind's answer to it is certain. */
function target(): Row {
  const spelt = (r: Row) => [r.name, ...r.aliases, ...(r.editions ?? []), r.id].map((s) => s.toLowerCase());
  const all = ROWS();
  const found = all.filter((r) => /^[A-Za-z]{5,}$/.test(r.name)).sort((a, b) => a.name.localeCompare(b.name, 'en'))
    .find((r) => all.every((o) => o === r || spelt(o).every((s) => !s.includes(r.name.toLowerCase()))));
  if (found == null) throw new Error('the preview has no benchmark with a one-word name of its own to search for');
  return found;
}

// ---- the Worker, unreachable ----------------------------------------------------------------------------------------

/** The Worker's routes (11 S3, "Recommendation: (b)": run_worker_first is scoped to /api/* and /mcp only). The export
 *  surface's documentation page, /api/ itself (pages/api.astro), is inside the prefix too; no test here opens it. */
const isWorker = (u: URL) => u.pathname.startsWith('/api/') || u.pathname === '/mcp' || u.pathname.startsWith('/mcp/');

interface Attempt { method: string; path: string; from: string }

/** Makes the Worker unreachable from every page of `context`: each request to its routes is refused at the network
 *  layer, as a connection to a Worker that is down is. Returns the list of every such request, which fills as they are
 *  made, refused or not. */
async function workerDown(context: BrowserContext): Promise<Attempt[]> {
  const seen: Attempt[] = [];
  context.on('request', (r) => {
    const u = new URL(r.url());
    if (!isWorker(u)) return;
    let from = '(no page)';
    try {
      from = new URL(r.frame().url()).pathname;
    } catch {
      // a service worker's request has no frame
    }
    seen.push({ method: r.method(), path: `${u.pathname}${u.search}`, from });
  });
  await context.route(isWorker, (route) => route.abort('connectionrefused'));
  return seen;
}

/** What was asked of the Worker, one line each; [] when nothing was. */
const workerProblems = (seen: Attempt[]) =>
  seen.map((a) => `${a.from} requested ${a.method} ${a.path}: the Worker is unreachable, and the deterministic path must not ask it`);

/** Once `page` has gone quiet, no page of its context has asked the Worker for anything. */
async function askedNothing(page: Page, seen: Attempt[]) {
  await page.waitForLoadState('networkidle');
  expect(workerProblems(seen)).toEqual([]);
}

/** Serves `path` to `page` as the server sends it, with `edit` applied to its HTML. */
const doctor = (page: Page, path: string, edit: (html: string) => string) =>
  page.route((u) => u.pathname === path, async (route) => {
    const res = await route.fetch();
    await route.fulfill({ response: res, body: edit(await res.text()) });
  });

/** Every request `page` makes from now on whose path starts with `prefix`, by path. */
function requested(page: Page, prefix: string): string[] {
  const seen: string[] = [];
  page.on('request', (r) => {
    const path = new URL(r.url()).pathname;
    if (path.startsWith(prefix)) seen.push(path);
  });
  return seen;
}

// ---- the semantic tier, as a build with document vectors serves it --------------------------------------------------

let encoder: QueryEncoder | undefined;
/** The encoder the page runs, over the same files. */
function encode(text: string): Float32Array {
  if (encoder == null) {
    const embed = new URL('../../public/embed/', import.meta.url);
    const bytes = (f: string) => new Uint8Array(readFileSync(new URL(f, embed)));
    const meta = JSON.parse(readFileSync(new URL('potion-8m-pruned.meta.json', embed), 'utf8'));
    const tokenizer = JSON.parse(readFileSync(new URL('tokenizer.json', embed), 'utf8'));
    encoder = new QueryEncoder(tokenizer, meta, dequantise(meta, bytes('potion-8m-pruned.i8.bin'), bytes('potion-8m-pruned.r2.bin')));
  }
  return encoder.encode(text);
}

/** vectors.meta.json and vectors.i8.bin as tools/build/embed.py writes them over the preview's rows: row `near` is
 *  `query`'s vector, every other row deterministic noise (tests/semantic-results.spec.ts vectorsFor()). */
function vectorsFor(query: string, near: number) {
  const ids = ROWS().map((r) => r.id);
  const dims = 256;
  const bin = Buffer.alloc(ids.length * dims);
  const scales: number[] = [];
  let s = 11;
  for (let i = 0; i < ids.length; i++) {
    if (i === near) {
      const v = encode(query);
      const scale = Math.max(...Array.from(v, Math.abs)) / 127;
      for (let k = 0; k < dims; k++) bin.writeInt8(Math.round(v[k] / scale), i * dims + k);
      scales.push(scale);
    } else {
      for (let k = 0; k < dims; k++) {
        s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
        bin.writeInt8((s % 201) - 100, i * dims + k);
      }
      scales.push(0.01);
    }
  }
  const sha256 = createHash('sha256').update(bin).digest('hex');
  const meta = { artifact: 'vectors', format: 1, rows: ids.length, dims, ids, scales,
    vectors: { file: 'vectors.i8.bin', dtype: 'int8', layout: 'row-major', bytes: bin.length, sha256 } };
  return { meta: JSON.stringify(meta), bin };
}

/** Serves /search/ as a build that ships the vectors does: data-vectors="shipped", and the component's entry table. */
async function shipVectors(page: Page) {
  const table = entriesJson(entryTable(ROWS(), () => true));
  const tier = /(<div\b[^>]*\bdata-semantic-tier\b[^>]*?)\bdata-vectors="none"([^>]*>)/;
  await doctor(page, '/search/', (html) => {
    if (!tier.test(html)) throw new Error('/search/ has no [data-semantic-tier] element with data-vectors="none" to ship vectors in');
    return html.replace(tier, (_, open: string, rest: string) => `${open}data-vectors="shipped"${rest}<script type="application/json" data-semantic-entries>${table}</script>`);
  });
}

/** Holds the vectors back until release() names the row the query's vector goes in. */
async function holdVectors(page: Page, query: string) {
  let release: (near: number) => void = () => undefined;
  const chosen = new Promise<number>((r) => { release = r; });
  let asked = false;
  let pair: ReturnType<typeof vectorsFor> | undefined;
  await page.route((u) => u.pathname === VECTORS_META || u.pathname === VECTORS_BIN, async (route) => {
    asked = true;
    const near = await chosen;
    pair ??= vectorsFor(query, near);
    const meta = new URL(route.request().url()).pathname === VECTORS_META;
    await route.fulfill({ status: 200, contentType: meta ? 'application/json' : 'application/octet-stream', body: meta ? pair.meta : pair.bin });
  });
  return { release: (near: number) => release(near), asked: () => asked };
}

// ---- the page ---------------------------------------------------------------------------------------------------------

const box = (page: Page) => page.locator('#search-q');
const results = (page: Page) => page.locator('[data-search-results]');
const lexicalUrls = (page: Page) => page.locator('ol[data-tier="lexical"] > li').evaluateAll((lis) => lis.map((li) => li.getAttribute('data-url')!));

/** /search/ hydrated, and `t`'s name typed into its box one key at a time, until the word-match answer naming it is up. */
async function search(page: Page, t: Row) {
  await page.goto('/search/');
  await expect(page.locator('[data-search-box]')).not.toHaveAttribute('data-state', 'static');
  await box(page).focus();
  await box(page).pressSequentially(t.name);
  await expect(results(page)).toHaveAttribute('data-answered', t.name);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
}

/** The bytes of script `context` fetches for `path`, loaded until the network is idle. */
async function scriptBytes(context: BrowserContext, path: string): Promise<number> {
  const p = await context.newPage();
  const bodies: Promise<number>[] = [];
  p.on('response', (r) => {
    if (r.request().resourceType() === 'script') bodies.push(r.body().then((b) => b.length));
  });
  await p.goto(path, { waitUntil: 'networkidle' });
  const bytes = (await Promise.all(bodies)).reduce((a, b) => a + b, 0);
  await p.close();
  return bytes;
}

// ---- the tests --------------------------------------------------------------------------------------------------------

test('facet filtering: a term narrows /benchmarks/ to the rows facets.json gives it, with the Worker unreachable', async ({ context, page }) => {
  const seen = await workerDown(context);
  const terms = (preview('enums.json') as { vocabularies: Record<string, { terms: Term[] }> }).vocabularies.capability.terms;
  const carrying = (t: Term) => ROWS().filter((r) => (r.facets.capability ?? []).includes(t.key)).map((r) => r.id).sort();
  // the broadest capability that still leaves some benchmark out, so the filter is seen to narrow
  const term = terms.filter((t) => carrying(t).length < ROWS().length)
    .sort((a, b) => carrying(b).length - carrying(a).length || a.id.localeCompare(b.id, 'en'))[0];
  const want = carrying(term);
  expect(want.length, `${term.id} is carried by some benchmark`).toBeGreaterThan(0);

  await page.goto('/benchmarks/');
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'ready');
  await expect(page.locator('ol.results > li')).toHaveCount(ROWS().length);
  await page.locator(`details[data-group="c"] li.term[data-term="${term.id}"] > .row > input`).check();
  await expect(page).toHaveURL(`/benchmarks/?c=${term.id}&v=1`);
  await expect(page.locator('ol.results > li')).toHaveCount(want.length);
  const shown = await page.locator('ol.results > li').evaluateAll((lis) => lis.map((li) => li.getAttribute('data-id')!));
  expect(shown.sort(), 'the rows facets.json says carry the term, and no other').toEqual(want);
  await askedNothing(page, seen);
});

test('Pagefind answers a query on /search/ with the benchmark it names, from /pagefind/, with the Worker unreachable', async ({ context, page }) => {
  const seen = await workerDown(context);
  const t = target();
  const pagefind = requested(page, '/pagefind/');
  await search(page, t);
  await expect(page.getByRole('region', { name: LEXICAL_HEADING, exact: true })).toBeVisible();
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"] a`)).toHaveAttribute('href', url(t));
  expect(pagefind.length, "the answer is Pagefind's, read from its files").toBeGreaterThan(0);
  await askedNothing(page, seen);
});

test('the semantic block appears with the row the cosine ranks first, with the Worker unreachable', async ({ context, page }) => {
  test.setTimeout(120_000);
  const seen = await workerDown(context);
  const t = target();
  await shipVectors(page);
  const held = await holdVectors(page, t.name);
  await search(page, t);
  await expect.poll(held.asked, { timeout: READY_MS }).toBe(true);
  await expect(page.locator(BLOCK)).toHaveCount(0);

  // the query's vector goes in a row the word-match answer does not show, so the block has a row of its own to show
  const shown = await lexicalUrls(page);
  const near = ROWS().findIndex((r) => r.id !== t.id && !shown.includes(url(r)));
  held.release(near);
  await expect(page.locator('[data-semantic-tier]')).toHaveAttribute('data-state', 'ready', { timeout: READY_MS });
  const block = page.locator(BLOCK);
  await expect(block).toBeVisible();
  await expect(page.getByRole('region', { name: SEMANTIC_HEADING, exact: true })).toBeVisible();
  await expect(block.locator('li').first()).toHaveAttribute('data-url', url(ROWS()[near]));
  await expect(block.locator('li').first().locator('a')).toHaveText(ROWS()[near].name);
  expect(await lexicalUrls(page), 'the word-match answer is still there, as it was').toEqual(shown);
  await askedNothing(page, seen);
});

test('a benchmark page renders and cites with JavaScript off, and fetches 0 bytes of script, with the Worker unreachable', async ({ browser, context, page }) => {
  const t = target();
  // Tier 0: JavaScript off
  const off = await browser.newContext({ javaScriptEnabled: false });
  const seenOff = await workerDown(off);
  const reader = await off.newPage();
  const res = await reader.goto(url(t));
  expect(res!.status()).toBe(200);
  await expect(reader.locator('h1')).toHaveText(t.name);
  const cite = reader.locator(`[data-section="18"] section.cite[data-cite="${t.id}"]`);
  await expect(cite).toBeVisible();
  const link = PERMALINK.exec((await cite.locator('a[href*="/blob/"]').getAttribute('href')) ?? '');
  expect(link, 'the citation block has a permalink at a 40-digit commit').not.toBeNull();
  await expect(reader.locator('[data-build-footer] [data-commit]'), 'the commit the footer prints').toHaveAttribute('data-commit', link![1]);
  await expect(cite.locator('pre code'), 'the BibTeX').toContainText(`at commit ${link![1]}`);
  await askedNothing(reader, seenOff);
  await off.close();

  // JavaScript on: the page as sent names no script to fetch (the one inline script every page carries is 09 S9's
  // pre-paint theme line, which tests/detail-nojs.spec.ts allows the same way), and the browser fetches none
  const seen = await workerDown(context);
  const html = await (await page.request.get(url(t))).text();
  expect(html).not.toMatch(/<script[^>]*\bsrc=/);
  expect(html).not.toMatch(/<script[^>]*type="module"/);
  expect(html).not.toMatch(/rel="modulepreload"/);
  expect(html).not.toMatch(/<astro-island/);
  expect(await scriptBytes(context, url(t)), 'bytes of script fetched').toBe(0);
  // the measurement, on a page that ships JavaScript, is not zero
  expect(await scriptBytes(context, '/search/')).toBeGreaterThan(0);
  expect(workerProblems(seen)).toEqual([]);
});

test('a page that asks the Worker is caught: /search/ calling /api/ as the reader types, a benchmark page loading from it', async ({ browser, context, page }) => {
  const t = target();
  const seen = await workerDown(context);
  // an AI layer that does not degrade: on the first keystroke it posts the query to the Worker, and marks the outcome
  const asks = '<script>document.addEventListener("input", () => { fetch("/api/facet-query", { method: "POST", body: "{}" })'
    + '.then(() => { document.documentElement.dataset.workerCall = "answered"; }, () => { document.documentElement.dataset.workerCall = "refused"; }); }, { once: true });</script>';
  await doctor(page, '/search/', (html) => html.replace('</body>', `${asks}</body>`));
  await search(page, t);
  await expect(page.locator('html'), 'the call is refused at the network layer').toHaveAttribute('data-worker-call', 'refused');
  await page.waitForLoadState('networkidle');
  expect(workerProblems(seen)).toEqual([
    '/search/ requested POST /api/facet-query: the Worker is unreachable, and the deterministic path must not ask it',
  ]);

  // with JavaScript off, a benchmark page that loads something from the Worker's routes
  const off = await browser.newContext({ javaScriptEnabled: false });
  const seenOff = await workerDown(off);
  const reader = await off.newPage();
  await doctor(reader, url(t), (html) => html.replace('</body>', '<img src="/api/health?from=page" alt=""></body>'));
  await reader.goto(url(t));
  await expect(reader.locator('h1')).toHaveText(t.name);
  await reader.waitForLoadState('networkidle');
  expect(workerProblems(seenOff)).toEqual([
    `${url(t)} requested GET /api/health?from=page: the Worker is unreachable, and the deterministic path must not ask it`,
  ]);
  await off.close();
});
