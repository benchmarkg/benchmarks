// site/tests/suite-basket.spec.ts -- P6-S4-T01 (10 V10 "Basket persistence", "Two words, used precisely throughout";
// 10 "Filter state encoding"). The V10 Suite Builder at /suite/ (islands/SuiteBuilder.tsx), in a browser, over the draft
// preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/suite-basket.spec.ts
//
// The ledger's verify is `npm run test:e2e -- suite-basket`; the site has no test:e2e script, and this file is what it
// names. Done when: "A basket round-trips through the URL alone with no server state, and the UI never presents the
// basket as the citable object." Both halves are checked as stated:
//   round-trip   a basket made in one browser context, by adding and removing, is opened from its URL alone in a second
//                context that has never seen the page and holds nothing in storage, and is the same basket; while it was
//                made, no request but a static GET left the page, and none named its entries, so no server can have
//                kept it; the URL is
//                canonical (sorted, each id once, v=1) however the link that opened it was written; Back undoes an edit
//   citable      the basket pane says it is a working selection and not citable, its link is a working link that says it
//                is not a citation, the suite manifest is its own section outside the basket, drawn differently, naming the
//                commit an export pins and saying exporting is not built, and nothing on the page offers to cite the basket
// Around them: localStorage only mirrors and offers (a bare /suite/ starts empty, as its URL says, and offers what this
// browser kept); an id the index does not have is named in a visible notice, never dropped silently; the filter pane's
// search and facets narrow the list and live in the same URL beside the basket; the Atlas's "Add to suite basket" link
// (islands/AtlasSelection.tsx, 10 V10's "+ from lasso (V1)") carries its selection into the basket and the basket kept here
// is offered back; and the add-from-cell entry point says the Coverage Map is not built, which /coverage/'s 404 confirms.
//
// Every expectation is computed here from the facets.json and atlas.json the server was built from (build/preview/,
// scripts/preview_corpus.py), and every canonical URL by this file's own rule, not by lib/filter-url.ts.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Row { id: string; name: string; aliases: string[]; domain: string; subdomain: string }
interface Node { id: string; cluster: string }
interface Region { id: string; level: 'group' | 'family' }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const ROWS = (preview('facets.json') as { benchmarks: Row[] }).benchmarks;
const atlas = preview('atlas.json') as { nodes: Node[]; regions: Region[] };
const BY_ID = new Map(ROWS.map((r) => [r.id, r]));
const STORE_KEY = 'uaibi:suite-basket';

/** 10's canonical basket query: the ids sorted by code point, each once, comma-joined, then v=1. */
const canonical = (ids: string[]) => (ids.length === 0 ? '' : `?b=${[...new Set(ids)].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)).join(',')}&v=1`);
const sorted = (ids: string[]) => [...new Set(ids)].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

// three benchmarks of three different families, so no facet or lasso can take two of them at once by accident
const THREE = (() => {
  const out: Row[] = [];
  for (const r of ROWS) if (!out.some((o) => o.domain === r.domain)) out.push(r);
  return out.slice(0, 3);
})();
const [A, B, C] = THREE;

const ROOT = '[data-suite-builder]';
async function ready(page: Page, query = '') {
  await page.goto(`/suite/${query}`);
  await expect(page.locator(ROOT)).toHaveAttribute('data-state', 'ready');
}
/** The basket is `want`: the island's list, the entries in the pane, and the heading's count. */
async function basket(page: Page, want: string[]) {
  const ids = sorted(want);
  await expect(page.locator(ROOT)).toHaveAttribute('data-basket', ids.join(' '));
  const shown = await page.locator('[data-basket-entry]').evaluateAll((els) => els.map((e) => e.getAttribute('data-basket-entry')!));
  expect(sorted(shown)).toEqual(ids);
  await expect(page.locator('#suite-basket-h .count')).toHaveText(`(${ids.length})`);
}
const search = (page: Page) => new URL(page.url()).search;

test('the preview is what these expectations read: three benchmarks of three families', () => {
  expect(THREE).toHaveLength(3);
  expect(new Set(THREE.map((r) => r.domain)).size).toBe(3);
});

test('a basket round-trips through its URL alone: no server state, no storage, one canonical link', async ({ page, browser }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });
  // a link written by hand: out of order, an id twice, no grammar version
  await ready(page, `?b=${C.id},${A.id},${C.id}`);
  await basket(page, [A.id, C.id]);
  await expect(page.locator(`[data-basket-entry="${A.id}"] a`)).toHaveText(A.name);

  // from here on, nothing the page does may tell a server about the basket: an edit is the URL's, and nowhere else's.
  // Every request is recorded; a GET of a static file the page needs (a font face a new glyph calls for, say) is
  // allowed, and anything that is not a GET, or that names a benchmark of the basket, fails
  const sent: string[] = [];
  page.on('request', (r) => sent.push(`${r.method()} ${r.url()}`));
  const telling = () => sent.filter((s) => !s.startsWith('GET ') || [A, B, C].some((r) => s.includes(r.id)));
  await page.locator(`[data-result="${B.id}"] button`).click();
  await basket(page, [A.id, B.id, C.id]);
  expect(search(page), 'written back canonical').toBe(canonical([A.id, B.id, C.id]));
  await expect(page.locator('[data-suite-status]')).toHaveText('3 benchmarks in the basket');
  await page.locator(`[data-basket-entry="${C.id}"] button`).click();
  await basket(page, [A.id, B.id]);
  expect(search(page)).toBe(canonical([A.id, B.id]));
  await expect(page.locator(`[data-result="${C.id}"] button`)).toHaveText(`Add ${C.name} to the basket`);
  expect(telling(), 'no request about the basket left the page while it was edited').toEqual([]);
  const link = page.url();
  await expect(page.locator('[data-suite-link]')).toHaveValue(link);

  // the link alone, in a browser context that has never seen the page and has nothing in storage
  const fresh = await browser.newContext();
  const other = await fresh.newPage();
  await other.goto('/suite/');
  expect(await other.evaluate((k) => window.localStorage.getItem(k), STORE_KEY), 'a new context keeps nothing').toBeNull();
  await other.goto(link);
  await expect(other.locator(ROOT)).toHaveAttribute('data-state', 'ready');
  await basket(other, [A.id, B.id]);
  for (const r of [A, B]) await expect(other.locator(`[data-basket-entry="${r.id}"] a`)).toHaveText(r.name);
  expect(await other.evaluate((k) => window.localStorage.getItem(k), STORE_KEY), 'arriving is not an edit: nothing was stored').toBeNull();
  await fresh.close();

  // Back undoes an edit, Forward redoes it
  await page.goBack();
  await basket(page, [A.id, B.id, C.id]);
  await page.goForward();
  await basket(page, [A.id, B.id]);
  expect(errors, 'no script error and no hydration mismatch').toEqual([]);
});

test('localStorage only mirrors: a bare /suite/ starts empty, as its URL says, and offers what this browser kept', async ({ page }) => {
  await ready(page, canonical([A.id, B.id]));
  expect(await page.evaluate((k) => window.localStorage.getItem(k), STORE_KEY), 'arriving stores nothing').toBeNull();
  await page.locator(`[data-basket-entry="${A.id}"] button`).click();          // an edit: mirrored
  await basket(page, [B.id]);
  expect(await page.evaluate((k) => window.localStorage.getItem(k), STORE_KEY)).toBe(canonical([B.id]).slice(1));

  await ready(page);
  await basket(page, []);
  await expect(page.locator('[data-empty="basket"]')).toBeVisible();
  const offer = page.locator('[data-suite-offer]');
  await expect(offer).toHaveAttribute('data-suite-offer', B.id);
  expect(search(page), 'the offer changed nothing yet').toBe('');
  await offer.getByRole('button', { name: 'Restore them' }).click();
  await basket(page, [B.id]);
  expect(search(page)).toBe(canonical([B.id]));
  await expect(offer).toHaveCount(0);

  // a link that names another basket opens as that basket, and the kept one is offered for adding, or dismissed
  await ready(page, canonical([C.id]));
  await basket(page, [C.id]);
  await expect(offer).toHaveAttribute('data-suite-offer', B.id);
  await offer.getByRole('button', { name: 'Dismiss' }).click();
  await expect(offer).toHaveCount(0);
  await basket(page, [C.id]);
  await ready(page, canonical([C.id]));
  await offer.getByRole('button', { name: 'Add them' }).click();
  await basket(page, [B.id, C.id]);
});

test('an id the index does not have is left out of the basket and named, never dropped silently', async ({ page }) => {
  await ready(page, `?b=${A.id},no-such-benchmark&v=1`);
  await basket(page, [A.id]);
  await expect(page.locator('[data-ignored="b"]')).toContainText('ignored filter: b=no-such-benchmark');
  expect(BY_ID.has('no-such-benchmark')).toBe(false);
});

test('the basket is never presented as the citable object: the manifest is apart, drawn apart, and not built', async ({ page }) => {
  await ready(page, canonical([A.id, B.id]));
  const pane = page.locator('[data-suite-basket]');
  const manifest = page.locator('[data-suite-manifest]');
  await expect(pane).toHaveAttribute('data-citable', 'no');
  await expect(pane.locator('[data-scratch]')).toHaveText('Working selection, not citable');
  await expect(pane.getByLabel('Working link to this basket')).toHaveValue(page.url());
  await expect(pane.locator('[data-suite-link-box]')).toContainText('It is not a citation');

  await expect(manifest).toHaveAttribute('data-citable', 'yes');
  await expect(manifest.getByRole('heading')).toHaveText('Suite manifest, the citable export');
  await expect(manifest.locator('[data-not-built]')).toHaveText(/not built yet, so nothing on this page is citable/);
  const commit = (await page.locator('[data-commit]').getAttribute('data-commit'))!;
  await expect(manifest.locator('[data-suite-commit]')).toHaveText(commit.slice(0, 12));
  expect(await manifest.evaluate((m) => m.closest('[data-suite-basket]') == null), 'the manifest is not part of the basket').toBe(true);
  expect(await pane.evaluate((p) => p.querySelector('[data-suite-manifest]') == null)).toBe(true);
  // drawn as different things: the basket a dashed frame, the manifest a solid one
  const style = (sel: string) => page.locator(sel).evaluate((el) => getComputedStyle(el).borderTopStyle);
  expect(await style('[data-suite-basket]')).toBe('dashed');
  expect(await style('[data-suite-manifest]')).toBe('solid');
  // and nothing offers to cite the basket or calls its link a permalink
  await expect(page.getByRole('button', { name: /cite|citation|permalink/i })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /cite|citation|permalink/i })).toHaveCount(0);
  expect(await page.locator('main').innerText()).not.toMatch(/permalink|cite this/i);
});

test('the filter pane: search and facets narrow the list, and live in the URL beside the basket', async ({ page }) => {
  const fold = (s: string) => s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
  const target = ROWS.find((r) => /[a-z]{4,}/i.test(r.name) && ROWS.filter((x) => x.domain === r.domain).length > 1)!;
  const word = fold(target.name).match(/[a-z]{4,}/)![0];
  const answers = (r: Row) => [r.name, r.id, ...r.aliases].some((h) => fold(h).includes(word));
  await ready(page, canonical([A.id]));
  const shown = () => page.locator('[data-result]').evaluateAll((els) => els.map((e) => e.getAttribute('data-result')!));
  expect((await shown()).length).toBe(ROWS.length);

  await page.locator('input[data-control="q"]').fill(word);
  await expect(page.locator('[data-count]')).toHaveText(`${ROWS.filter(answers).length} of ${ROWS.length} benchmarks match`);
  expect(sorted(await shown())).toEqual(sorted(ROWS.filter(answers).map((r) => r.id)));
  await page.locator('select[data-control="d"]').selectOption(target.domain);
  const want = ROWS.filter((r) => answers(r) && r.domain === target.domain).map((r) => r.id);
  await expect(page.locator('[data-count]')).toHaveText(`${want.length} of ${ROWS.length} benchmarks match`);
  expect(sorted(await shown())).toEqual(sorted(want));
  const url = new URL(page.url());
  expect(url.searchParams.get('b')).toBe(A.id);
  expect(url.searchParams.get('d')).toBe(target.domain);
  expect(url.searchParams.get('q')).toBe(word);
  expect([...url.searchParams.keys()], 'keys in the grammar\'s order').toEqual(['b', 'd', 'q', 'v']);

  // the same view from the link, and the filters cleared keep the basket
  await page.reload();
  await expect(page.locator(ROOT)).toHaveAttribute('data-state', 'ready');
  expect(sorted(await shown())).toEqual(sorted(want));
  await expect(page.locator('input[data-control="q"]')).toHaveValue(word);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  expect(search(page)).toBe(canonical([A.id]));
  await basket(page, [A.id]);
});

test('add from lasso: the Atlas selection\'s link opens the basket with it, and the basket kept here is offered back', async ({ page }) => {
  test.setTimeout(120_000);
  const fam = atlas.regions.find((g) => g.level === 'family' && atlas.nodes.filter((n) => n.cluster === g.id).length >= 2)!;
  const members = atlas.nodes.filter((n) => n.cluster === fam.id).map((n) => n.id);
  const outside = ROWS.find((r) => r.domain !== fam.id)!;
  await ready(page, canonical([outside.id]));
  // the basket's entry point to the Atlas, which mirrors the basket first, so it can be offered back
  await page.getByRole('link', { name: '+ from lasso (Atlas)' }).click();
  await page.waitForURL('**/atlas/');
  await expect(page.locator('[data-atlas-view]')).toHaveAttribute('data-state', 'drawn');
  const add = page.getByRole('link', { name: 'Add to suite basket' });
  await expect(add, 'nothing selected: an empty basket').toHaveAttribute('href', '/suite/?');
  await page.locator('select[data-control="d"]').selectOption(fam.id);
  await page.getByRole('button', { name: `Select all ${members.length} visible` }).click();
  await expect(page.locator('[data-atlas-selection]')).toHaveAttribute('data-atlas-selection', members.join(' '));
  await expect(add, 'the selection, canonical: sorted, whatever order it was made in').toHaveAttribute('href', `/suite/${canonical(members)}`);

  await add.click();
  await expect(page.locator(ROOT)).toHaveAttribute('data-state', 'ready');
  expect(search(page)).toBe(canonical(members));
  await basket(page, members);
  const offer = page.locator('[data-suite-offer]');
  await expect(offer).toHaveAttribute('data-suite-offer', outside.id);
  await offer.getByRole('button', { name: 'Add them' }).click();
  await basket(page, [...members, outside.id]);
  expect(search(page)).toBe(canonical([...members, outside.id]));
});

test('add from cell: the Coverage Map is not built, and its entry point says so rather than linking nowhere', async ({ page }) => {
  await ready(page);
  const cell = page.locator('[data-entry-point="cell"]');
  await expect(cell).toHaveAttribute('data-not-built');
  await expect(cell).toContainText('Not built yet');
  await expect(cell.locator('a')).toHaveCount(0);
  const res = await page.request.get('/coverage/');
  expect(res.status(), 'there is no /coverage/ page on this build').toBe(404);
});

test('the basket can be built from the keyboard alone, and each change is said once, politely', async ({ page }) => {
  await ready(page);
  await page.locator('input[data-control="q"]').focus();
  // Tab on past the four facet controls to the first result's link and its Add
  const first = page.locator('[data-result] button').first();
  const id = (await page.locator('[data-result]').first().getAttribute('data-result'))!;
  for (let i = 0; i < 40 && !(await first.evaluate((b) => b === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(first).toBeFocused();
  await page.keyboard.press('Enter');
  await basket(page, [id]);
  await expect(page.locator('[data-suite-status]')).toHaveText('1 benchmark in the basket');
  await expect(first, 'focus stays on the button, now its Remove').toBeFocused();
  await expect(first).toHaveText(`Remove ${BY_ID.get(id)!.name} from the basket`);
  await page.keyboard.press('Space');
  await basket(page, []);
  await expect(page.locator('[data-suite-status]')).toHaveText('0 benchmarks in the basket');
});
