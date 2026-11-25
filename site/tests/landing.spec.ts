// site/tests/landing.spec.ts -- P2-S4-T08 (10 "Information architecture", "Progressive disclosure", "Performance budget";
// 08 S4.3, S8.1; 09 S1, S3.2, S10). The landing page, read with JavaScript disabled (the `nojs` project,
// playwright.config.ts), over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/landing.spec.ts --project=nojs
//
// Done when: "The landing page renders the corpus size from build data, works with JavaScript off, and is inside its
// budget." Every expectation is computed here from the files the server was built from -- build/preview/facets.json (the
// rows), src/lib/taxonomy.json (the domain families) -- not from the page's own logic (src/lib/landing.ts). The failures
// are checked as failures: the first screen is looked for in the raw HTML the server sent, not in a DOM a script could
// have filled in; the JavaScript measurement that holds the landing to 40 KB is shown to exceed 40 KB on a page that ships
// an island; and an entry point is held to its route both ways, so a route that starts to resolve fails here until the
// landing links it.
//
// No entry is published yet, so the preview's 320 drafts stand in for the published corpus, as on every page test, and the
// page says they are drafts. The production build, whose facets.json has no row, shows "No benchmark is published yet";
// a build with no facets.json says it cannot count. Those states are lib/landing.ts's, tested in test/landing.test.mjs.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { expect, test, type Browser, type Page } from '@playwright/test';

const read = (rel: string) => JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));
const facets = read('../../build/preview/facets.json') as { drafts?: boolean; benchmarks: { id: string; domain: string }[] };
const corpus = read('../../build/preview/corpus.json') as { entities: { benchmark: unknown[] } };
const taxonomy = read('../src/lib/taxonomy.json') as { facets: { domain: Record<string, unknown> } };
const ROWS = facets.benchmarks;
const FAMILIES = Object.keys(taxonomy.facets.domain).filter((id) => !id.includes('/')).length;
const COVERED = new Set(ROWS.map((r) => r.domain)).size;
const KB = 1024;

// The four entry points and the route each one is (10 "Information architecture"; the methodology page renders at
// /docs/methodology/, which 10's /methodology/ redirects to).
const ENTRIES: [string, string][] = [
  ['browse', '/benchmarks/'], ['atlas', '/atlas/'], ['coverage', '/coverage/'], ['methodology', '/docs/methodology/'],
];

const html = async (page: Page, path = '/') => {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
};
// the page's markup without its <style> blocks, whose selectors could otherwise be mistaken for it
const markup = (h: string) => h.replace(/<style[^>]*>.*?<\/style>/gs, '');
const text = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const block = (h: string, name: string) => {
  const m = new RegExp(`<(\\w+)[^>]*data-landing="${name}"[^>]*>(.*?)</\\1>`, 's').exec(markup(h));
  expect(m, `data-landing="${name}" is in the HTML as sent`).not.toBeNull();
  return { open: m![0].slice(0, m![0].indexOf('>') + 1), body: m![2] };
};

test('the preview holds every draft entry, so the count is checked against real rows', () => {
  expect(facets.drafts).toBe(true);
  expect(ROWS.length).toBeGreaterThanOrEqual(34);
  expect(ROWS.length).toBe(corpus.entities.benchmark.length);
  expect(COVERED).toBeGreaterThan(1);
  expect(COVERED).toBeLessThanOrEqual(FAMILIES);
});

test('the HTML as sent says what the catalogue is, what it refuses to do and how many entries it holds', async ({ page }) => {
  const h = await html(page);
  expect(text(block(h, 'what').body)).toMatch(/^What each benchmark measures, .*primary source/);
  const size = block(h, 'size');
  expect(size.open).toContain(`data-state="preview"`);
  expect(size.open).toContain(`data-count="${ROWS.length}"`);
  expect(text(size.body)).toBe(`${ROWS.length} draft benchmarks, counted as families, in ${COVERED} of the ${FAMILIES} domain families. `
    + 'An agent drafted them and no person has verified them, so none is published.');
  expect(text(block(h, 'refuses').body)).toMatch(/^What it refuses to do It does not rank\. .*no universal score, no cross-domain ranking and no composite index/);
  // and the Base.astro banner above it, on every page of a preview
  expect(markup(h)).toContain('data-draft-preview');
});

test('the count is read from facets.json at build time, never written into the page', () => {
  // The rendered count equals the rows (above); here the template itself is held to carrying no corpus size, so a count
  // typed into the markup fails even while it happens to be right.
  const source = readFileSync(fileURLToPath(new URL('../src/pages/index.astro', import.meta.url)), 'utf8');
  const template = source.slice(source.indexOf('---', 3) + 3).replace(/<style[^>]*>.*?<\/style>/gs, '');
  expect(template).not.toMatch(/\b\d{2,}\b/);
  expect(template).not.toContain(String(ROWS.length));
});

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`with JavaScript off, the three statements are on the first screen at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    expect(test.info().project.use.javaScriptEnabled, 'the nojs project').toBe(false);
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page.locator('h1')).toHaveText('A catalogue of AI benchmarks across every domain');
    await expect(page.locator('[data-landing="size"] .figure')).toHaveText(String(ROWS.length));
    for (const name of ['what', 'size', 'refuses']) {
      const box = (await page.locator(`[data-landing="${name}"]`).boundingBox())!;
      expect(box, name).not.toBeNull();
      expect(box.y + box.height, `${name} ends inside the first ${viewport.height}px`).toBeLessThanOrEqual(viewport.height);
    }
    // the theme toggle needs JavaScript, so without it the control is not shown (ThemeToggle.astro)
    await expect(page.locator('[data-theme-toggle]')).toBeHidden();
  });
}

test('the four entry points and nothing else, each linked exactly when its route is built', async ({ page }) => {
  const h = await html(page);
  const main = /<main\b[^>]*>(.*?)<\/main>/s.exec(markup(h))![1];
  const linked: string[] = [];
  for (const [id, route] of ENTRIES) {
    const status = (await page.request.get(route)).status();
    expect([200, 404], `${route} answers`).toContain(status);
    const li = new RegExp(`<li[^>]*data-entry="${id}"[^>]*>(.*?)</li>`, 's').exec(main);
    expect(li, `the ${id} entry`).not.toBeNull();
    const hrefs = [...li![1].matchAll(/<a\b[^>]*href="([^"]+)"/g)].map((m) => m[1]);
    if (status === 200) {
      expect(hrefs, `${route} is built, so the ${id} entry links it`).toEqual([route]);
      linked.push(route);
    } else {
      expect(hrefs, `${route} is not built, so the ${id} entry links nothing`).toEqual([]);
      expect(li![1], `the ${id} entry says it is not built`).toContain('data-not-built');
    }
  }
  // Nothing else: every link in <main> is one of the built entry points. Today that is three of the four; the Coverage
  // Map is P4-S3-T01's /coverage/.
  expect([...main.matchAll(/<a\b[^>]*href="([^"]+)"/g)].map((m) => m[1])).toEqual(linked);
  expect(linked).toEqual(['/benchmarks/', '/atlas/', '/docs/methodology/']);
  // 10's /methodology/ resolves too, by its static redirect to the page the landing links
  expect(await html(page, '/methodology/')).toMatch(/http-equiv="refresh"[^>]*url=\/docs\/methodology\//);
  // and with JavaScript off the links are links: one opens its page
  await page.goto('/');
  await page.locator('[data-entry="browse"] a').click();
  await expect(page).toHaveURL(/\/benchmarks\/$/);
  await expect(page.locator('h1')).toHaveText('Browse benchmarks');
});

test('the landing is a narrative page in the search index: crawled, not ignored', async ({ page }) => {
  const h = await html(page);
  expect(h).toMatch(/<meta data-pagefind-filter="type\[content\]" content="page"/);
  expect(h).not.toMatch(/<body[^>]*data-pagefind-ignore/);
});

/** What `path` fetches with JavaScript running: every script response's bytes, gzipped at level 9 one by one as
 *  size-limit does, plus the inline scripts of the page, and every request for a /data/ artifact. */
async function shipped(browser: Browser, path: string) {
  const ctx = await browser.newContext({ javaScriptEnabled: true });
  const p = await ctx.newPage();
  const bodies: Promise<Buffer>[] = [];
  const data: string[] = [];
  p.on('request', (r) => {
    if (new URL(r.url()).pathname.startsWith('/data/')) data.push(r.url());
  });
  p.on('response', (r) => {
    if (r.request().resourceType() === 'script') bodies.push(r.body());
  });
  await p.goto(path, { waitUntil: 'networkidle' });
  const inline = await p.evaluate(() => [...document.querySelectorAll('script:not([src])')]
    .filter((s) => !/json|importmap/.test(s.getAttribute('type') ?? ''))
    .map((s) => s.textContent ?? '').filter((t) => t.trim() !== ''));
  const gz = [...(await Promise.all(bodies)), ...inline.map((t) => Buffer.from(t))].map((b) => gzipSync(b, { level: 9 }).length);
  await ctx.close();
  return { bytes: gz.reduce((a, b) => a + b, 0), files: bodies.length, data };
}

test('no island, no artifact fetched, and the route ships at most 40 KB of JavaScript', async ({ browser, page }) => {
  // In the HTML: no island and no preloaded module; the scripts are the pre-paint theme line (09 S9) and the theme toggle.
  const h = await html(page);
  expect(h).not.toMatch(/<astro-island/);
  expect(h).not.toMatch(/rel="modulepreload"/);
  expect([...h.matchAll(/<script\b[^>]*>/g)].map((m) => m[0].replace(/src="[^"]+"/, 'src')))
    .toEqual(['<script data-prepaint>', '<script type="module" src>']);
  // In a browser that runs JavaScript: the counts are inlined, so no /data/ file is fetched, and the scripts are inside
  // 10's 40 KB. The same measurement of the browse view, whose filter island hydrates on load, comes out over 40 KB, so a
  // landing that gained an island would fail here as well as in `npx size-limit`.
  const landing = await shipped(browser, '/');
  expect(landing.data, 'the landing fetches no artifact (08 S4.3)').toEqual([]);
  expect(landing.files).toBeGreaterThan(0);
  expect(landing.bytes).toBeLessThanOrEqual(40 * KB);
  const browse = await shipped(browser, '/benchmarks/');
  expect(browse.data.length, 'the browse view fetches facets.json').toBeGreaterThan(0);
  expect(browse.bytes).toBeGreaterThan(40 * KB);
});
