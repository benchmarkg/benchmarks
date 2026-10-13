// site/tests/detail-nojs.spec.ts -- P2-S3-T01 (10 V6; 08 S4.3; 09 S5.3, S10). The benchmark detail page, read with
// JavaScript disabled (the `nojs` project, playwright.config.ts), over the draft preview of every entry:
//
//   cd site && npx playwright test tests/detail-nojs.spec.ts --project=nojs
//
// Done when: "Every section renders with JavaScript disabled, collapsed sections are present in the HTML rather
// than absent, and the route ships 0 bytes of JS." The failure each half guards against is checked as a failure:
// collapsed content is looked for in the raw HTML the server sent, not in a DOM a script could have filled in, and
// the zero-JS measurement is shown to come out non-zero on a page that does ship JavaScript.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

const CORPUS = fileURLToPath(new URL('../../build/preview/corpus.json', import.meta.url));
const corpus = JSON.parse(readFileSync(CORPUS, 'utf8')) as {
  drafts?: boolean;
  entities: { benchmark: { id: string; name: string; curation: { sources: unknown[] } }[] };
};
const IDS = corpus.entities.benchmark.map((b) => b.id);
const ARTICLE = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const COLLAPSED = [10, 11, 12, 13, 14, 15, 16, 17];
// The entries that exercise the most shapes: lineage and many sources; breaking versions and human baselines;
// metrics recorded as notes rather than Metric ids; subsets and leaderboards.
const DEEP = ['swe-bench', 'forecastbench', 'casp', 'arc-agi-3'];

const html = async (page: Page, id: string) => {
  const res = await page.request.get(`/benchmarks/${id}/`);
  expect(res.status(), id).toBe(200);
  return res.text();
};
// the page's markup without its <style> blocks, whose selectors could otherwise be mistaken for it
const markup = (h: string) => h.replace(/<style[^>]*>.*?<\/style>/gs, '');
const sectionsIn = (h: string) => [...markup(h).matchAll(/data-section="(\d+)"/g)].map((m) => Number(m[1]));

test('the preview holds every entry, so the pages are checked against real records', () => {
  expect(corpus.drafts).toBe(true);
  expect(IDS.length).toBeGreaterThanOrEqual(34);
  for (const id of DEEP) expect(IDS).toContain(id);
});

test('every benchmark has its page, with the eighteen sections in 10 V6 order', async ({ page }) => {
  for (const id of IDS) {
    expect(sectionsIn(await html(page, id)), id).toEqual([...ARTICLE, ...COLLAPSED, 18]);
  }
});

test('sections 10-17 are closed <details> in the served HTML, each with a count in its summary', async ({ page }) => {
  for (const id of IDS) {
    const h = await html(page, id);
    for (const n of COLLAPSED) {
      const m = new RegExp(`<details([^>]*)data-section="${n}"([^>]*)>\\s*<summary[^>]*>(.*?)</summary>(.*?)</details>`, 's').exec(markup(h));
      expect(m, `${id} section ${n} is a <details>`).not.toBeNull();
      const [, before, after, summary, body] = m!;
      expect(`${before}${after}`, `${id} section ${n} is collapsed by default`).not.toMatch(/\bopen\b/);
      expect(summary.replace(/<[^>]+>/g, ''), `${id} section ${n} summary`).toMatch(/\(\d+[^)]*\)/);
      expect(body.replace(/<[^>]+>/g, '').trim().length, `${id} section ${n} has its content in the HTML`).toBeGreaterThan(0);
    }
  }
});

test('collapsed, not absent: every source is in the served HTML inside the closed Sources section, as counted', async ({ page }) => {
  for (const id of DEEP) {
    const h = await html(page, id);
    const sources = /<details[^>]*data-section="16"[^>]*>\s*<summary[^>]*>(.*?)<\/summary>(.*?)<\/details>/s.exec(markup(h))!;
    const count = Number(/\((\d+)\)/.exec(sources[1].replace(/<[^>]+>/g, ''))![1]);
    const items = [...sources[2].matchAll(/data-source-item="(src-[a-z0-9-]+)"/g)].map((m) => m[1]);
    expect(count, id).toBeGreaterThan(0);
    expect(items.length, `${id}: the summary counts what the section holds`).toBe(count);
    expect(new Set(items).size, id).toBe(items.length);
    // every in-page reference to a source lands on one of those items
    for (const ref of h.matchAll(/data-source-ref="(src-[a-z0-9-]+)"/g)) expect(items, `${id} cites ${ref[1]}`).toContain(ref[1]);
  }
});

for (const id of DEEP) {
  test(`${id}: with JavaScript disabled every section renders, and a closed section opens natively`, async ({ page }) => {
    await page.goto(`/benchmarks/${id}/`);
    expect(test.info().project.use.javaScriptEnabled, 'the nojs project').toBe(false);
    const name = corpus.entities.benchmark.find((b) => b.id === id)!.name;
    await expect(page.locator('h1')).toHaveText(name);
    for (const fact of ['lifecycle', 'headroom', 'adoption']) await expect(page.locator(`[data-fact="${fact}"]`)).toBeVisible();
    for (const n of ARTICLE) await expect(page.locator(`[data-section="${n}"]`).first()).toBeVisible();
    for (const n of COLLAPSED) {
      const d = page.locator(`details[data-section="${n}"]`);
      await expect(d.locator('summary')).toBeVisible();
      await expect(d).not.toHaveAttribute('open', /.*/);
      expect(await d.locator(':scope > :not(summary)').count(), `section ${n} content is in the DOM`).toBeGreaterThan(0);
      await expect(d.locator(':scope > :not(summary)').first()).toBeHidden();
    }
    const sources = page.locator('details[data-section="16"]');
    await sources.locator('summary').click();                                       // native disclosure: no script
    await expect(sources).toHaveAttribute('open', '');
    await expect(sources.locator('[data-source-item]').first()).toBeVisible();
    await expect(page.locator('[data-section="18"] .cite')).toBeVisible();
  });
}

test('the route ships 0 bytes of JavaScript', async ({ browser, page }) => {
  // In the HTML: no script file, no module, no preload of one, no island; the one inline script is 09 S9's pre-paint
  // theme line, which every page carries and which 09 S9 allows.
  for (const id of IDS) {
    const h = await html(page, id);
    expect(h, id).not.toMatch(/<script[^>]*\bsrc=/);
    expect(h, id).not.toMatch(/<script[^>]*type="module"/);
    expect(h, id).not.toMatch(/rel="modulepreload"/);
    expect(h, id).not.toMatch(/<astro-island/);
    expect(h, id).not.toMatch(/data-theme-toggle/);
    expect([...h.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), id).toEqual(['<script data-prepaint>']);
  }
  // In a browser that runs JavaScript: what the page fetches as script, in bytes. The same measurement on a page that
  // ships its theme toggle comes out non-zero, so a detail page that gained a script would fail here.
  const ctx = await browser.newContext({ javaScriptEnabled: true });
  const scriptBytes = async (path: string) => {
    const p = await ctx.newPage();
    let bytes = 0;
    p.on('response', async (r) => {
      if (r.request().resourceType() === 'script') bytes += (await r.body()).length;
    });
    await p.goto(path, { waitUntil: 'networkidle' });
    await p.close();
    return bytes;
  };
  for (const id of DEEP) expect(await scriptBytes(`/benchmarks/${id}/`), id).toBe(0);
  expect(await scriptBytes('/_fixtures/theme')).toBeGreaterThan(0);
  await ctx.close();
});

test('the entry grid: a metadata rail beside the prose at --bp-md, a fact strip above the prose on a phone', async ({ page }) => {
  const box = async (sel: string) => (await page.locator(sel).first().boundingBox())!;
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/benchmarks/swe-bench/');
  let rail = await box('.rail'), body = await box('.body'), head = await box('.head');
  expect(rail.x, 'rail to the right of the prose').toBeGreaterThanOrEqual(body.x + body.width);
  expect(Math.abs(rail.y - head.y), 'rail level with the heading').toBeLessThan(4);
  expect(rail.width).toBeCloseTo(320, -1);                                         // 20rem
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/benchmarks/swe-bench/');
  rail = await box('.rail'); body = await box('.body'); head = await box('.head');
  expect(rail.y, 'the strip comes after the heading').toBeGreaterThanOrEqual(head.y + head.height);
  expect(rail.y + rail.height, 'and before the prose').toBeLessThanOrEqual(body.y);
  expect(rail.width).toBeGreaterThan(300);                                          // full width, one column
});

test('section 18 cites the build: its commit, its release and the concept DOI', async ({ page }) => {
  await page.goto('/benchmarks/swe-bench/');
  const cite = page.locator('[data-section="18"] .cite');
  await expect(cite.locator('a[href*="/blob/"]')).toHaveAttribute('href', /\/blob\/[0-9a-f]{40}\/data\/benchmarks\/code\/swe-bench\.yaml$/);
  await expect(cite.locator('a[href^="https://doi.org/"]')).toHaveText(/^10\.5281\/zenodo\.\d+$/);
  await expect(cite.locator('[data-release-tag]')).toBeVisible();                 // a tag, or "not applicable" before one
});

test('a draft preview says so on the page, and on the entry', async ({ page }) => {
  await page.goto('/benchmarks/swe-bench/');
  await expect(page.locator('[data-draft-preview]')).toBeVisible();
  await expect(page.locator('[data-draft-entry]')).toBeVisible();
  await expect(page.locator('[data-verification-status]')).toHaveText('ai-drafted-unverified');
});

test('claims are counted from the adoption artifact, and the page says their table is not in this build', async ({ page }) => {
  const ADOPTION = fileURLToPath(new URL('../../build/preview/derived/adoption.json', import.meta.url));
  const rows = (JSON.parse(readFileSync(ADOPTION, 'utf8')) as { benchmarks: { id: string; claims: number; systems: number }[] }).benchmarks;
  const withClaims = rows.filter((r) => r.claims > 0 && IDS.includes(r.id));
  expect(withClaims.length, 'some entry has claims, so the non-zero path is exercised').toBeGreaterThan(0);
  for (const r of [...withClaims, { id: 'swe-bench', claims: 0, systems: 0 }]) {
    const want = rows.find((x) => x.id === r.id) ?? r;
    await page.goto(`/benchmarks/${r.id}/`);
    await expect(page.locator('details[data-section="10"] summary .count'), r.id).toHaveText(`(${want.claims})`);
    await expect(page.locator('[data-fact="adoption"] dd'), r.id).toContainText(`${want.systems} system`);
    await expect(page.locator('[data-claims-pending]'), r.id).toHaveCount(want.claims > 0 ? 1 : 0);
  }
});

test('a metric recorded as notes renders its notes with their sources (CASP)', async ({ page }) => {
  await page.goto('/benchmarks/casp/');
  const notes = page.locator('[data-section="6"] [data-metric-note]');
  expect(await notes.count()).toBeGreaterThan(0);
  await expect(notes.first().locator('.ref')).toBeVisible();
});
