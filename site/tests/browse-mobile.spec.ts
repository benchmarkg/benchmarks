// site/tests/browse-mobile.spec.ts -- P2-S4-T05 (09 S10 "Browse and search"; 10 V11). The browse view at /benchmarks/
// at phone width, in a browser, over the draft preview playwright.config.ts builds, on its `mobile` project (390 by 844
// CSS px, touch):
//
//   cd site && npx playwright test tests/browse-mobile.spec.ts --project=mobile
//
// Done when: "At 390px the sheet opens, the chip row is present, and the result list's scroll position is unchanged
// after a filter is applied." Expectations are computed here from the files the server serves (facets.json and
// enums.json from build/preview/, as tests/browse.spec.ts reads them), not from the view's own logic.
//
// The failure the verification names is checked as a failure: the result list moving under the reader. The page is
// scrolled deep into the list before a filter is applied, from the sheet and from the chip row, and the scroll position
// and the list's place on screen are held to what they were, so a view that scrolled to the top, stacked the rail back
// above the list, or let the browser re-anchor on a row fails here; and the page is first shown to be long enough after
// the filter that the browser had no reason to move it. So is the failure 09 S10 names as the reason for the layout:
// filters applied but out of sight, so that an empty result reads as "no data". A selection that matches nothing is
// held to showing its chips, its "Filters (2)" and the empty result on one screen.
//
// Desktop is tests/browse.spec.ts's, on the `js` project; the one width check here is that from --bp-md up the same
// rail is back beside the list.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Row { id: string; domain: string; subdomain: string; facets: Record<string, string[]> }
interface EnumTerm { id: string; key: string; field?: string; parent?: string | null }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const ROWS = (preview('facets.json') as { benchmarks: Row[] }).benchmarks;
const enums = preview('enums.json') as { flat_facets: Record<string, { vocabularies: string[] }>; vocabularies: Record<string, { terms: EnumTerm[] }> };

// 10's grammar keys the rail answers to: key -> the vocabulary (and field) its terms come from (as browse.spec.ts)
const RAIL: [string, string, string | null][] = [
  ['d', 'domain', null], ['c', 'capability', null], ['em', 'evaluation_method', null], ['s', 'subject', null],
  ['lc', 'lifecycle', 'lifecycle'], ['acc', 'data_properties', 'data.access'], ['mt', 'governance', 'governance.maintainer_type'],
  ['sp', 'governance', 'governance.submission_process'], ['ct', 'execution', 'execution.compute_tier'],
  ['rt', 'execution', 'execution.reproducibility_tier'],
];
const flatOf = new Map(Object.entries(enums.flat_facets).flatMap(([flat, d]) => d.vocabularies.map((v) => [v, flat] as const)));
const VOCAB = new Map(RAIL.map(([key, vocab, field]) => [key, enums.vocabularies[vocab].terms.filter((t) => field == null || t.field === field)]));
const ALL_TERMS = [...VOCAB.values()].reduce((n, ts) => n + ts.length, 0);

function carries(key: string, id: string): (r: Row) => boolean {
  const t = VOCAB.get(key)!.find((x) => x.id === id)!;
  if (key === 'd') return (r) => (t.parent == null ? r.domain === id : r.subdomain === id);
  const flat = flatOf.get(RAIL.find((x) => x[0] === key)![1])!;
  return (r) => r.facets[flat].includes(t.key);
}

type State = Record<string, string[]>;
/** The results and every term's count for a selection: AND across keys, OR within one, a key's own selection left out
 *  of its terms' counts. */
function expected(state: State) {
  const passes = (r: Row, skip: string | null) => Object.entries(state).every(([k, ids]) => k === skip || ids.some((id) => carries(k, id)(r)));
  const counts = new Map<string, number>();
  for (const [key] of RAIL) {
    for (const t of VOCAB.get(key)!) counts.set(`${key}:${t.id}`, ROWS.filter((r) => passes(r, key) && carries(key, t.id)(r)).length);
  }
  return { total: ROWS.filter((r) => passes(r, null)).length, counts };
}
/** A rail key's terms by count under `state`, broadest first. */
const ranked = (key: string, state: State = {}) => [...expected(state).counts].filter(([k, n]) => k.startsWith(`${key}:`) && n > 0)
  .sort((a, b) => b[1] - a[1]).map(([k]) => k.slice(key.length + 1));
const [C, C2, C3] = ranked('c');
const [EM, EM2] = ranked('em', { c: [C] });
// a capability and an evaluation method each carried by some benchmark, never by the same one
const DISJOINT = (() => {
  for (const c of ranked('c')) for (const em of ranked('em')) if (expected({ c: [c], em: [em] }).total === 0) return { c, em };
  return null;
})();
const query = (state: State) => `?${Object.keys(state).sort().map((k) => `${k}=${[...state[k]].sort().join(',')}`).join('&')}&v=1`;

const SHEET = '#browse-sheet';
const sheetOpen = (page: Page) => page.locator(SHEET).evaluate((el) => el.matches(':popover-open'));
const openButton = (page: Page) => page.locator('button[data-open-sheet]');
const box = (page: Page, key: string, id: string) => page.locator(`details[data-group="${key}"] li.term[data-term="${id}"] > .row > input`);
const chips = (page: Page) => page.locator('.results-head .applied .chips button.chip');
const scrollY = (page: Page) => page.evaluate(() => window.scrollY);
const listTop = (page: Page) => page.locator('.results-body').evaluate((el) => el.getBoundingClientRect().top);

async function ready(page: Page, q = '') {
  await page.goto(`/benchmarks/${q}`);
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'ready');
}

/** Every term row of the sheet's rail carries the count facets.json gives for `state`. */
async function countsMatch(page: Page, state: State) {
  const want = expected(state);
  const rows = await page.$$eval(`${SHEET} li.term`, (lis) => lis.map((li) => ({
    key: `${li.closest('details.group')!.getAttribute('data-group')}:${li.getAttribute('data-term')}`,
    count: li.getAttribute('data-count'),
  })));
  expect(rows.length, 'every term of every rail vocabulary is in the sheet').toBe(ALL_TERMS);
  for (const r of rows) expect(Number(r.count), r.key).toBe(want.counts.get(r.key));
  return want;
}

test('the project is the phone the verification names, and the preview holds what these tests choose from', async ({ page }) => {
  expect(page.viewportSize()).toEqual({ width: 390, height: 844 });
  expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches), 'a touch screen').toBe(true);
  expect(ROWS.length).toBeGreaterThan(0);
  expect([C, C2, C3, EM, EM2].every((x) => x != null), 'three capabilities and two evaluation methods with benchmarks').toBe(true);
  expect(DISJOINT, 'a capability and an evaluation method that never meet').not.toBeNull();
});

test('at 390px the rail is a sheet, closed on arrival and opened from the bar above the results, with the same live rail', async ({ page }) => {
  await ready(page);
  const open = openButton(page);
  await expect(open).toHaveText('Filters (0)');
  await expect(open).toBeInViewport();
  await expect(page.locator('aside.rail')).toBeHidden();
  // the list is the page: no rail above it, so its first rows are on the first screen, under the bar
  const bar = (await page.locator('.results-head').boundingBox())!;
  const first = (await page.locator('ol.results > li').first().boundingBox())!;
  expect(bar.y + bar.height).toBeLessThanOrEqual(first.y);
  expect(first.y + first.height).toBeLessThan(844);

  await open.tap();
  await expect.poll(() => sheetOpen(page)).toBe(true);
  await expect(page.locator('aside.rail')).toBeVisible();
  await expect(page.locator(`${SHEET} aside.rail > h2 + p.confidence`)).toHaveCount(1);
  // modal while open: focus is in the sheet, and the page under it takes neither focus nor a tap
  await expect.poll(() => page.evaluate((s) => document.activeElement?.closest(s) != null, SHEET)).toBe(true);
  expect(await page.locator('#browse-results').evaluate((el) => (el as HTMLElement).inert)).toBe(true);
  await countsMatch(page, {});
  await expect(page.locator(`${SHEET} .sheet-done`)).toHaveText(`Show ${ROWS.length} benchmarks`);

  // a filter applied in the sheet: counts recomputed in place, the footer says what it leaves, the URL holds it
  await box(page, 'c', C).tap();
  await expect(box(page, 'c', C)).toBeChecked();
  const one = await countsMatch(page, { c: [C] });
  await expect(page.locator(`${SHEET} .sheet-done`)).toHaveText(`Show ${one.total} benchmarks`);
  await expect(page).toHaveURL(`/benchmarks/?c=${C}&v=1`);

  // closed by its footer button: focus is back on the bar's button, the page is live again, and the chip is in the row
  await page.locator(`${SHEET} .sheet-done`).tap();
  await expect.poll(() => sheetOpen(page)).toBe(false);
  await expect(page.locator('aside.rail')).toBeHidden();
  await expect(open).toBeFocused();
  expect(await page.locator('#browse-results').evaluate((el) => (el as HTMLElement).inert)).toBe(false);
  await expect(open).toHaveText('Filters (1)');
  await expect(chips(page)).toHaveCount(1);
  await expect(chips(page).first()).toHaveAttribute('data-chip', `c=${C}`);
  await expect(page.locator('ol.results > li')).toHaveCount(one.total);

  // closed by Escape, and by a tap on the scrim above the panel
  await open.tap();
  await expect.poll(() => sheetOpen(page)).toBe(true);
  await page.keyboard.press('Escape');
  await expect.poll(() => sheetOpen(page)).toBe(false);
  await expect(open).toBeFocused();
  // the scrim: scrolled until the bar is stuck to the top, its chip lies under the scrim, and a tap there closes the
  // sheet without reaching the chip
  await page.locator('ol.results > li').nth(10).evaluate((li) => window.scrollTo(0, li.getBoundingClientRect().top + window.scrollY));
  const under = (await chips(page).first().boundingBox())!;
  expect(under.y + under.height, 'the chip is under the scrim').toBeLessThan(844 * 0.15);
  await open.tap();
  await expect.poll(() => sheetOpen(page)).toBe(true);
  await page.touchscreen.tap(under.x + under.width / 2, under.y + under.height / 2);
  await expect.poll(() => sheetOpen(page)).toBe(false);
  await expect(open).toBeFocused();
  await expect(chips(page), 'the tap closed the sheet and reached nothing under it').toHaveCount(1);
});

test('the chip row: below the bar, every applied filter on one line that scrolls sideways, each chip removable', async ({ page }) => {
  await ready(page);
  const row = page.locator('.results-head .applied');
  await expect(row.locator('.none')).toHaveText('No filter applied.');
  const empty = (await row.boundingBox())!;

  const state: State = { c: [C, C2, C3], em: [EM, EM2] };
  await ready(page, query(state));
  await expect(chips(page)).toHaveCount(5);
  await expect(openButton(page)).toHaveText('Filters (5)');
  const button = (await openButton(page).boundingBox())!;
  const held = (await row.boundingBox())!;
  expect(held.y, 'the chip row is below the bar').toBeGreaterThanOrEqual(button.y + button.height);
  expect(held.height, 'five chips take the height of none').toBe(empty.height);
  const ys = await chips(page).evaluateAll((cs) => cs.map((c) => c.getBoundingClientRect().top));
  expect(new Set(ys).size, 'one line').toBe(1);
  const overflow = await row.evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth, style: getComputedStyle(el).overflowX }));
  expect(overflow.style).toBe('auto');
  expect(overflow.scroll, 'more chips than the screen is wide, scrolled sideways rather than wrapped').toBeGreaterThan(overflow.client);
  await expect(page.locator('ol.results > li')).toHaveCount(expected(state).total);

  // the last chip, off the screen to the right: scrolled to and removed on its own
  const last = chips(page).last();
  await expect(last).not.toBeInViewport({ ratio: 1 });
  const gone = (await last.getAttribute('data-chip'))!;
  await last.tap();
  await expect(chips(page)).toHaveCount(4);
  await expect(page.locator(`.results-head [data-chip="${gone}"]`)).toHaveCount(0);
  const [k, v] = gone.split('=');
  const rest: State = { ...state, [k]: state[k].filter((x) => x !== v) };
  await expect(page).toHaveURL(`/benchmarks/${query(rest)}`);
  await expect(page.locator('ol.results > li')).toHaveCount(expected(rest).total);
  await expect(openButton(page)).toHaveText('Filters (4)');

  // and all of them at once, from the end of the row
  await row.locator('button.clear').tap();
  await expect(row.locator('.none')).toHaveText('No filter applied.');
  await expect(page).toHaveURL('/benchmarks/');
  expect((await row.boundingBox())!.height).toBe(empty.height);
});

test('the list never moves under the reader: a filter applied from the sheet or the chip row leaves the scroll position as it was', async ({ page }) => {
  await ready(page);
  // deep in the list, and far enough down that the bar is stuck to the top of the screen
  const rows = page.locator('ol.results > li');
  const y = Math.round(await rows.nth(15).evaluate((li) => li.getBoundingClientRect().top + window.scrollY - 300));
  await page.evaluate((to) => window.scrollTo(0, to), y);
  expect(await scrollY(page)).toBe(y);
  expect((await page.locator('.results-head').boundingBox())!.y, 'the bar is stuck to the top').toBe(0);
  const top = await listTop(page);

  // from the sheet
  await openButton(page).tap();
  await box(page, 'c', C).tap();
  await page.locator(`${SHEET} .sheet-done`).tap();
  await expect(rows).toHaveCount(expected({ c: [C] }).total);
  expect(await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight), 'the filtered page still reaches the position')
    .toBeGreaterThanOrEqual(y);
  expect(await scrollY(page), 'the scroll position after a filter from the sheet').toBe(y);
  expect(await listTop(page), 'the list has not moved on screen').toBe(top);
  // and the filter is in sight where the reader is
  await expect(chips(page).first()).toBeInViewport();
  await expect(openButton(page)).toHaveText('Filters (1)');

  // from the chip row: the list widens back under the reader, who stays where they were
  await chips(page).first().tap();
  await expect(rows).toHaveCount(ROWS.length);
  expect(await scrollY(page), 'the scroll position after a chip is removed').toBe(y);
  expect(await listTop(page)).toBe(top);

  // and when something above the list does change: a link's ignored value is a notice above the list, which the first
  // change clears; the list stays where it was on screen
  await ready(page, '?c=nonexistent-term&v=1');
  await expect(page.locator('[data-ignored]')).toBeVisible();
  const y2 = Math.round(await rows.nth(15).evaluate((li) => li.getBoundingClientRect().top + window.scrollY - 300));
  await page.evaluate((to) => window.scrollTo(0, to), y2);
  const top2 = await listTop(page);
  await openButton(page).tap();
  await box(page, 'c', C).tap();
  await page.locator(`${SHEET} .sheet-done`).tap();
  await expect(page.locator('[data-ignored]')).toHaveCount(0);
  await expect(rows).toHaveCount(expected({ c: [C] }).total);
  // to the pixel the page can scroll by: the notice's height need not be a whole number of them
  expect(Math.abs(await listTop(page) - top2), 'the list holds its place on screen as the notice above it goes').toBeLessThanOrEqual(1);
});

test('a selection that matches nothing shows its filters on the same screen as the empty result', async ({ page }) => {
  const state: State = { c: [DISJOINT!.c], em: [DISJOINT!.em] };
  await ready(page, query(state));
  const empty = page.locator('[data-empty="filter"]');
  await expect(empty).toContainText('No benchmark matches all 2 filters.');
  await expect(empty).toBeInViewport();
  await expect(openButton(page)).toHaveText('Filters (2)');
  await expect(openButton(page)).toBeInViewport();
  await expect(chips(page)).toHaveCount(2);
  for (const c of await chips(page).all()) await expect(c).toBeInViewport();
  // the way out is on that screen too, and taking it fills the list where it stands
  const drop = empty.locator('button.drop');
  await expect(drop).toBeInViewport();
  await drop.tap();
  await expect(chips(page)).toHaveCount(1);
  await expect(page.locator('ol.results > li').first()).toBeInViewport();
});

test('as sent, with JavaScript off, the bar still opens the sheet, and its rail is the single-facet links', async ({ browser }) => {
  const use = test.info().project.use;
  const context = await browser.newContext({ viewport: use.viewport, isMobile: use.isMobile, hasTouch: use.hasTouch, javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('/benchmarks/');
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'loading');
  await expect(page.locator('aside.rail')).toBeHidden();
  await expect(openButton(page)).toBeInViewport();
  await openButton(page).tap();
  await expect(page.locator('aside.rail')).toBeVisible();
  await expect(page.locator(`${SHEET} li.term > .row > a[href^="/browse/"]`)).toHaveCount(ALL_TERMS);
  await expect(page.locator(`${SHEET} li.term input`)).toHaveCount(0);
  const done = page.locator(`${SHEET} .sheet-done`);
  await expect(done).toHaveText('Close');
  await done.tap();
  await expect(page.locator('aside.rail')).toBeHidden();
  await context.close();
});

test('from --bp-md up the same rail is back beside the list; widening with the sheet open closes it', async ({ page }) => {
  await ready(page, `?c=${C}&v=1`);
  await openButton(page).tap();
  await expect.poll(() => sheetOpen(page)).toBe(true);
  await page.setViewportSize({ width: 900, height: 844 });
  await expect.poll(() => sheetOpen(page)).toBe(false);
  await expect(openButton(page)).toBeHidden();
  const rail = (await page.locator('aside.rail').boundingBox())!;
  const list = (await page.locator('#browse-results').boundingBox())!;
  expect(rail.x + rail.width, 'the rail beside the list').toBeLessThanOrEqual(list.x);
  await expect(box(page, 'c', C)).toBeChecked();
  await expect(page.locator('#browse-results').evaluate((el) => (el as HTMLElement).inert)).resolves.toBe(false);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('aside.rail')).toBeHidden();
  await expect(openButton(page)).toHaveText('Filters (1)');
});
