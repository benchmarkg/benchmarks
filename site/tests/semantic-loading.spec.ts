// site/tests/semantic-loading.spec.ts -- P6-S1-T06 (11 S4 "First-query latency"). The semantic tier's loader
// (islands/search/loader.ts) on the search page, in a browser, over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/semantic-loading.spec.ts
//
// The ledger's verify names `npm run test:e2e -- semantic-loading`, a script the site does not have; this is that spec,
// run as the site's other Playwright specs are. Done when: "No embed fetch occurs before first paint, a second visit at
// the same index commit SHA fetches zero matrix bytes, and a changed SHA re-fetches." Held here:
//
//   - a page load fetches nothing of the tier: it waits, and only once the box has loaded Pagefind (on focus, or a query
//     in the link) does it fetch, every /embed/ request starting after the first paint and after every file Pagefind's
//     init fetched has arrived (the browser's own Resource and Paint Timing, one clock);
//   - a second visit at the same commit makes no /embed/ request at all, so zero matrix bytes, and the tier is ready
//     from IndexedDB; the page at another commit -- this build's page with its commit rewritten, which is what a rebuild
//     serves -- requests every file again and leaves IndexedDB holding that commit alone, and the first commit, evicted,
//     is fetched again too;
//   - a keystroke while the tier is still loading (its matrix held back by the test) gets its lexical results without
//     waiting for it;
//   - a file that fails its sha256 is refused: the tier says it failed, the lexical results are unchanged, nothing is
//     cached, and the next visit fetches again.
//
// The commit is read from the page (data-index-commit, which is release()'s, as the footer's is), and so is whether the
// build ships the document vectors (data-vectors): the files a load must fetch are the encoder's four and, when it
// does, the vectors' two. The draft preview ships none today (scripts/preview_corpus.py runs no S6), so their leg is
// held by test/semantic-loader.test.mjs. The query is a benchmark name of the preview's facets.json, so Pagefind has
// an answer.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page, type Request } from '@playwright/test';

const TIER = '[data-semantic-tier]';
const DB_NAME = 'uaibi-semantic-tier';              // loader.ts DB_NAME
const DB_STORE = 'stack';                           // loader.ts DB_STORE
const MATRIX = '/embed/potion-8m-pruned.i8.bin';
const ENCODER_FILES = ['/embed/potion-8m-pruned.meta.json', '/embed/tokenizer.json', MATRIX, '/embed/potion-8m-pruned.r2.bin'];
const VECTOR_FILES = ['/embed/vectors.meta.json', '/embed/vectors.i8.bin'];
const READY_MS = 60_000;

interface Row { id: string; name: string }
let query: string | undefined;
/** A benchmark of the preview whose name is one word, which Pagefind finds by its own record. */
const QUERY = () => (query ??= (() => {
  const rows = (JSON.parse(readFileSync(fileURLToPath(new URL('../../build/preview/facets.json', import.meta.url)), 'utf8')) as { benchmarks: Row[] }).benchmarks;
  const r = rows.filter((x) => /^[A-Za-z]{5,}$/.test(x.name)).sort((a, b) => a.name.localeCompare(b.name, 'en'))[0];
  if (r == null) throw new Error('the preview has no benchmark with a one-word name to search for');
  return r.name;
})());

const tier = (page: Page) => page.locator(TIER);
const box = (page: Page) => page.locator('#search-q');
const lexical = (page: Page) => page.locator('ol[data-tier="lexical"] > li');
const ready = (page: Page) => expect(tier(page)).toHaveAttribute('data-state', 'ready', { timeout: READY_MS });
/** Every file a load from the network fetches, sorted: the encoder's, and the vectors' when this build ships them. */
const tierFiles = async (page: Page) =>
  [...ENCODER_FILES, ...((await tier(page).getAttribute('data-vectors')) === 'shipped' ? VECTOR_FILES : [])].sort();
const distinct = (paths: string[]) => [...new Set(paths)].sort();

/** Every /embed/ request the page makes from now on, by path. */
function embedRequests(page: Page): string[] {
  const seen: string[] = [];
  page.on('request', (r: Request) => {
    const path = new URL(r.url()).pathname;
    if (path.startsWith('/embed/')) seen.push(path);
  });
  return seen;
}

/** The keys of the loader's IndexedDB store; [] when the database does not exist (it is never created here). */
const cachedCommits = (page: Page) => page.evaluate(async ([name, store]) => {
  if (!(await indexedDB.databases()).some((d) => d.name === name)) return [];
  return new Promise<string[]>((resolve, reject) => {
    const req = indexedDB.open(name);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(store)) { db.close(); resolve([]); return; }
      const keys = db.transaction(store, 'readonly').objectStore(store).getAllKeys();
      keys.onsuccess = () => { db.close(); resolve(keys.result.map(String)); };
      keys.onerror = () => reject(keys.error);
    };
  });
}, [DB_NAME, DB_STORE] as const);

/** When the page first painted, when Pagefind's init files had all arrived, and when each /embed/ request started. */
const timings = (page: Page) => page.evaluate(() => {
  const paint = performance.getEntriesByType('paint');
  const first = (paint.find((e) => e.name === 'first-paint') ?? paint.find((e) => e.name === 'first-contentful-paint'))?.startTime ?? null;
  const res = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
  const path = (e: PerformanceResourceTiming) => new URL(e.name).pathname;
  // what Pagefind's init fetches: its script, entry, wasm and metadata; the index chunks and fragments are a search's
  const init = res.filter((e) => path(e).startsWith('/pagefind/') && !/\.pf_(index|fragment)$/.test(path(e)));
  const embed = res.filter((e) => path(e).startsWith('/embed/'));
  return {
    firstPaint: first,
    pagefindInit: init.map(path),
    pagefindReady: Math.max(...init.map((e) => e.responseEnd)),
    embed: embed.map(path),
    firstEmbed: Math.min(...embed.map((e) => e.startTime)),
  };
});

test.beforeEach(async ({ page }) => {
  // room for every resource of a visit in the timeline the first-paint checks read
  await page.addInitScript(() => performance.setResourceTimingBufferSize(2000));
});

test('a page load fetches nothing of the tier; once the box has loaded Pagefind, it fetches after first paint', async ({ page }) => {
  const seen = embedRequests(page);
  await page.goto('/search/');
  await expect(page.locator('[data-search-box]')).not.toHaveAttribute('data-state', 'static');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1_500);
  expect(seen, 'never as part of page load (11 S4)').toEqual([]);
  await expect(tier(page)).toHaveAttribute('data-state', 'waiting');
  expect(await cachedCommits(page)).toEqual([]);

  await box(page).focus();                          // the box loads Pagefind on focus
  await ready(page);
  await expect(tier(page)).toHaveAttribute('data-source', 'network');
  const t = await timings(page);
  expect(t.firstPaint, 'the browser reports a first paint').not.toBeNull();
  expect(t.pagefindInit.length).toBeGreaterThan(0);
  expect(distinct(t.embed)).toEqual(await tierFiles(page));
  expect(t.firstEmbed, 'no embed fetch before first paint').toBeGreaterThan(t.firstPaint!);
  expect(t.firstEmbed, 'nor before Pagefind is interactive').toBeGreaterThanOrEqual(t.pagefindReady);
  await expect(tier(page)).toHaveAttribute('data-vectors', /^(shipped|none)$/);
});

test('with a query in the link, the tier still loads after first paint and after Pagefind, beside the lexical answer', async ({ page }) => {
  await page.goto(`/search/?q=${encodeURIComponent(QUERY())}`);
  await expect(lexical(page).first()).toBeVisible();
  await ready(page);
  const t = await timings(page);
  expect(distinct(t.embed)).toEqual(await tierFiles(page));
  expect(t.firstEmbed).toBeGreaterThan(t.firstPaint!);
  expect(t.firstEmbed).toBeGreaterThanOrEqual(t.pagefindReady);
});

test('a second visit at the same index commit fetches zero matrix bytes; a changed commit fetches again', async ({ page }) => {
  test.setTimeout(180_000);
  const at = `/search/?q=${encodeURIComponent(QUERY())}`;
  const seen = embedRequests(page);
  const visit = async () => {
    seen.length = 0;
    await page.goto(at);
    await ready(page);
    return { source: await tier(page).getAttribute('data-source'), fetched: [...seen] };
  };

  const first = await visit();
  const commit = (await tier(page).getAttribute('data-index-commit'))!;
  expect(commit).toMatch(/^[0-9a-f]{40}$/);
  expect(await page.locator('[data-build-footer] [data-commit]').getAttribute('data-commit'), 'the footer names the same commit').toBe(commit);
  expect(first.source).toBe('network');
  expect(first.fetched).toContain(MATRIX);
  expect(await cachedCommits(page)).toEqual([commit]);

  const second = await visit();
  expect(second.source, 'served from IndexedDB').toBe('cache');
  expect(second.fetched, 'no /embed/ request at all, so zero matrix bytes').toEqual([]);

  // the same page at another commit: what a rebuild serves
  const other = commit.replace(/[0-9a-f]/g, (d) => ((parseInt(d, 16) + 1) % 16).toString(16));
  const searchPage = (u: URL) => u.pathname === '/search/';
  await page.route(searchPage, async (route) => {
    const res = await route.fetch();
    await route.fulfill({ response: res, body: (await res.text()).replaceAll(commit, other) });
  });
  const rebuilt = await visit();
  await expect(tier(page)).toHaveAttribute('data-index-commit', other);
  expect(rebuilt.source, 'a changed commit is a miss').toBe('network');
  expect(distinct(rebuilt.fetched), 'every file fetched again').toEqual(await tierFiles(page));
  expect(await cachedCommits(page), 'the old build evicted, the new one cached').toEqual([other]);

  const again = await visit();
  expect(again.source).toBe('cache');
  expect(again.fetched).toEqual([]);

  await page.unroute(searchPage);
  const back = await visit();
  await expect(tier(page)).toHaveAttribute('data-index-commit', commit);
  expect(back.source, 'the first commit, evicted, is fetched again').toBe('network');
  expect(back.fetched).toContain(MATRIX);
  expect(await cachedCommits(page)).toEqual([commit]);
});

test('a keystroke while the tier is still loading gets its lexical results without waiting for it', async ({ page }) => {
  let release: () => void = () => undefined;
  const held = new Promise<void>((r) => { release = r; });
  let asked = false;
  await page.route((u) => u.pathname === MATRIX, async (route) => {
    asked = true;
    await held;
    await route.continue();
  });
  await page.goto('/search/');
  await expect(page.locator('[data-search-box]')).not.toHaveAttribute('data-state', 'static');
  await box(page).focus();
  await expect(tier(page)).toHaveAttribute('data-state', 'loading', { timeout: READY_MS });
  await expect.poll(() => asked, { timeout: READY_MS }).toBe(true);

  await box(page).pressSequentially(QUERY());
  await expect(lexical(page).first(), 'Pagefind answers with the matrix still held back').toBeVisible();
  expect(await lexical(page).count()).toBeGreaterThan(0);
  await expect(tier(page)).toHaveAttribute('data-state', 'loading');

  release();
  await ready(page);
  // the answer on screen is the same one: the tier's arrival moved nothing
  await expect(page.locator('[data-search-results]')).toHaveAttribute('data-answered', QUERY());
});

test('a file that fails its sha256 is refused: the tier fails, the lexical results stand, nothing is cached', async ({ page }) => {
  test.setTimeout(120_000);
  const corrupt = (u: URL) => u.pathname === MATRIX;
  await page.route(corrupt, async (route) => {
    const res = await route.fetch();
    const body = await res.body();
    body[1000] ^= 1;
    await route.fulfill({ response: res, body });
  });
  await page.goto(`/search/?q=${encodeURIComponent(QUERY())}`);
  await expect(tier(page)).toHaveAttribute('data-state', 'failed', { timeout: READY_MS });
  await expect(tier(page)).toHaveAttribute('data-failure', /potion-8m-pruned\.i8\.bin has the sha256 [0-9a-f]{64}, and its meta says/);
  await expect(lexical(page).first()).toBeVisible();
  await expect(page.locator('[data-search-failed]')).toHaveCount(0);
  expect(await cachedCommits(page), 'nothing cached under this commit').toEqual([]);

  await page.unroute(corrupt);
  const seen = embedRequests(page);
  await page.reload();
  await ready(page);
  await expect(tier(page)).toHaveAttribute('data-source', 'network');
  expect(seen).toContain(MATRIX);
});
