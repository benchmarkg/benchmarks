// site/tests/keyboard.spec.ts -- P2-S8-T04 (09 S8.1 "2.5.7 Dragging Movements", "2.5.8 Target Size (Minimum)", "2.4.11
// Focus Not Obscured", S8.2, S8.3; 10 V1, V11; 14 Phase 2 exit criterion 8). Keyboard operability of the Atlas (/atlas/)
// and the facet UI, the browse view (/benchmarks/), in a browser, over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/keyboard.spec.ts
//
// Done when: "Both the Atlas and the facet UI are fully operable from the keyboard including the non-drag path." The
// verification runs it "with pointer events disabled", and so does every test here: before the page's own scripts run,
// every event a mouse, pen, touch or wheel makes is swallowed at the window in the capture phase and counted, the way
// tests/atlas-selection.spec.ts blocks them, and each test ends by finding that count at zero, so nothing in it was done
// with a pointer. That failure case is checked as a failure: on both views a click on a term, a chip, a family's
// Highlight and "Select all N visible", and a wheel over the map, are swallowed and change nothing.
//
// What is asserted, at the widths each view is laid out for -- 1280 by 720, 09 S10's 390 by 844 phone, and a phone on
// its side, 740 by 360, where the browse view's sticky bar takes a quarter of the height:
//   traversal   Tab from the top of each view to its end. On /benchmarks/ each closed group and subdomain list is opened
//               with Enter on its summary as Tab reaches it, so every enabled term's checkbox, and the "Full definition"
//               link its focus shows, is a Tab stop, as are the second skip link, every chip and every result; at phone
//               width the rail is the sheet, opened with Enter on "Filters (N)" and walked inside. On /atlas/ the filter
//               bar's four controls, the selection's three buttons and every family's Highlight are Tab stops, and from
//               each Highlight the arrows reach every benchmark in the family (09 S8.2). Every walk is made again with
//               Shift+Tab from the end, and each must end at the page's last (or first) control: focus never falls to the
//               page on the way. It did, before this task, on the first Tab from a term's checkbox to its definition's
//               link (pages/benchmarks/index.astro says why, and has the fix).
//   operating   a term checked and let go with Space, a group closed and opened with Enter, the skip link followed, a chip
//               removed, "Clear all filters" and the empty result's "Remove ..." pressed with Enter; at phone width the
//               sheet opened, a term chosen in it and Escape closing it, focus back on its button.
//   SC 2.5.7    the Atlas's selection completes from the keyboard with the lasso never pressed: the filter bar's Domain
//               control set with an arrow key, "Select all N visible" pressed, a benchmark added with Space in the index,
//               taken out and put back with its summary's button, and "Clear selection" (09 S8.1's order of the ways in).
//   SC 2.4.11   at every stop of every walk the focused element is looked at where it is: some of it inside the viewport
//               and inside every box that clips it, and none of it under a sticky or fixed box that does not contain it
//               and is painted over it (hit-tested at nine points of the overlap). 09 S8.1 asks more than the SC's "not
//               entirely hidden": the sticky filter bar "must not cover a focused row", so any overlap past a pixel fails.
//               Neither view has a table, so there is no sticky table header today; the check holds every sticky and
//               fixed box alike, and its failure case shows a doctored sticky table header failing it. That failure case:
//               a page doctored so that a sticky bar, and a sticky table header, cover the focus as Shift+Tab climbs the
//               list fails the check, and so does the phone layout with this task's scroll margins taken out. Before
//               them the phone layout failed it twice over: Shift+Tab up the list stopped on results under the 89px bar,
//               and Tab down the sheet's rail on terms under its 69px sticky footer.
//   SC 2.5.8    every interactive chip, badge and legend toggle on the two views, and the buttons that share their bars
//               (09 S8.1 also names table row actions: the selection's, the summary's and the sheet's buttons and the
//               summary's link), is at least 24 by 24 CSS px, or meets one of the SC's exceptions as the SC states it:
//               Spacing -- a 24px circle centred on its box meets no other target's box and no other undersized target's
//               circle -- or Inline -- it sits in a line of text that is not a target. Badges are not interactive on
//               either view (FreshnessBadge and VerificationBadge are spans, on the record pages), so none is measured.
//               No target measured relies on an exception now. The Atlas summary's "Open the full page" link did: 18px
//               tall, it passed on Spacing at 1280px and on nothing at 390px, where the buttons wrap under it, and is a
//               24px target since this task. EXCEPTIONS below pins the list, so a new one is a decision, not an accident.
//               The check's own failure case: doctored 16px chips side by side fail it, and one alone, or two links in a
//               sentence, pass on Spacing and on Inline.
// Out of the size check, and said so: the rail's checkboxes, whose size is the browser's own (the SC's user-agent
// exception) with their labels beside them; the results' and the index's links, which are a list's rows rather than
// chips or toggles; and Atlas nodes, which 09 S8.1 exempts as essential presentation, the index being their alternative.
//
// The known gap, asserted and marked test.fail() until it is decided, so the suite passes while the gap is open and fails
// the day something closes it, which is when the mark comes off: a term no benchmark carries is shown and disabled (10 V11), and
// a disabled checkbox takes no focus, so the definition its row shows on hover, and the "Full definition" link in it, have
// no keyboard path -- 38 of the preview's 385 terms with no filter on (2026-11-26), more under one. Reaching them means a
// focusable aria-disabled checkbox or a definition link always in the Tab order, either of which changes what Tab and a
// screen reader meet in the rail: a design decision, left to the maintainer rather than made here.
//
// Expectations come from the files the server was built from (build/preview/: atlas.json, facets.json, enums.json), as the
// other specs read them, and from the page only for which terms its counts leave enabled.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Node { id: string; cluster: string; domain_primary: string; label: string }
interface Region { id: string; level: 'group' | 'family'; parent: string | null; label: string }
interface Row { id: string; facets: Record<string, string[]> }
interface EnumTerm { id: string; key: string }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const atlas = preview('atlas.json') as { nodes: Node[]; regions: Region[] };
const ROWS = (preview('facets.json') as { benchmarks: Row[] }).benchmarks;
const enums = preview('enums.json') as { flat_facets: Record<string, { vocabularies: string[] }>; vocabularies: Record<string, { terms: EnumTerm[] }> };

// the Atlas: its families in order, and each family's benchmarks as the index lists them (by name, case folded, then id)
const NODES = atlas.nodes;
const FAMILIES = atlas.regions.filter((r) => r.level === 'family');
const fold = (s: string) => s.toLowerCase();
const byName = (a: Node, b: Node) => (fold(a.label) !== fold(b.label) ? (fold(a.label) < fold(b.label) ? -1 : 1) : a.id < b.id ? -1 : 1);
const ENTRIES = new Map(FAMILIES.map((f) => [f.id, NODES.filter((n) => n.cluster === f.id).sort(byName)]));

// the browse view: the benchmarks carrying a capability or an evaluation method, from enums.json's key for the term
const flatOf = new Map(Object.entries(enums.flat_facets).flatMap(([flat, d]) => d.vocabularies.map((v) => [v, flat] as const)));
const carrying = (vocab: string, id: string) => {
  const t = enums.vocabularies[vocab].terms.find((x) => x.id === id)!;
  return new Set(ROWS.filter((r) => r.facets[flatOf.get(vocab)!].includes(t.key)).map((r) => r.id));
};
const ranked = (vocab: string) => enums.vocabularies[vocab].terms.map((t) => [t.id, carrying(vocab, t.id)] as const)
  .filter(([, s]) => s.size > 0).sort((a, b) => b[1].size - a[1].size || (a[0] < b[0] ? -1 : 1));
const meet = (a: Set<string>, b: Set<string>) => [...a].filter((x) => b.has(x)).length;
// the two broadest capabilities, and the broadest evaluation method the first meets
const [[C, CS], [C2]] = ranked('capability');
const EM = ranked('evaluation_method').find(([, s]) => meet(s, CS) > 0)![0];
// a capability and an evaluation method each carried by some benchmark, never by the same one
const DISJOINT = (() => {
  for (const [c, cs] of ranked('capability')) for (const [em, es] of ranked('evaluation_method')) if (meet(cs, es) === 0) return { c, em };
  return null;
})();
const query = (state: Record<string, string[]>) => `?${Object.keys(state).sort().map((k) => `${k}=${[...state[k]].sort().join(',')}`).join('&')}&v=1`;
/** The id islands/FacetPanel.tsx gives a term's checkbox. */
const domId = (key: string, id: string) => `f-${key}-${id.replace(/[^a-z0-9]+/gi, '-')}`;

const DESKTOP = { width: 1280, height: 720 };   // the js project's own
const PHONE = { width: 390, height: 844 };      // 09 S10's phone
const SIDEWAYS = { width: 740, height: 360 };   // a phone on its side: below --bp-md, so the bar sticks, in 360px of height

// ---- pointer events disabled ----------------------------------------------------------------------------------

/** Block every pointer, as tests/atlas-selection.spec.ts does. Each event a mouse, pen, touch or wheel makes is stopped at
 *  the window, in the capture phase, before any listener of the page's sees it, its default action prevented where it
 *  can be (Chromium still scrolls the page under a wheel: that is the browser's, not the page's), and counted in
 *  window.blocked. A click the keyboard makes (Enter or Space on a control, detail 0) is not a pointer's and goes on. */
const blockPointers = (page: Page) => page.addInitScript(() => {
  const w = window as unknown as { blocked: number };
  w.blocked = 0;
  const kinds = ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'pointerover', 'pointerout', 'pointerenter', 'pointerleave',
    'mousedown', 'mousemove', 'mouseup', 'mouseover', 'mouseout', 'mouseenter', 'mouseleave', 'click', 'dblclick', 'auxclick',
    'contextmenu', 'wheel', 'touchstart', 'touchmove', 'touchend', 'touchcancel', 'dragstart'];
  for (const k of kinds) {
    window.addEventListener(k, (e) => {
      if (e.type === 'click' && (e as MouseEvent).detail === 0) return;
      e.stopImmediatePropagation();
      if (e.cancelable) e.preventDefault();
      w.blocked++;
    }, { capture: true, passive: false });
  }
});
const blocked = (page: Page) => page.evaluate(() => (window as unknown as { blocked: number }).blocked);
const noPointer = async (page: Page) => expect(await blocked(page), 'no pointer event reached the page').toBe(0);

test.beforeEach(async ({ page }) => {
  await blockPointers(page);
});

// ---- what has focus, and what hides it ---------------------------------------------------------------------------

interface Stop {
  key: string;              // which control: its id, its data-* name, or its tag and text
  open: boolean | null;     // a <summary>'s <details>, open or not
  problems: string[];       // what hides it (SC 2.4.11), empty when nothing does
}

/** The focused element, looked at where it is: null when nothing on the page has focus. It is hidden when none of it is
 *  inside the viewport and every box that clips it (an ancestor whose overflow is not visible, up to a fixed one, past
 *  which nothing clips), and covered when a sticky or fixed box that neither contains it nor is inside it overlaps what
 *  is on screen of it by more than a pixel each way and, at one of nine points of that overlap, is hit before it. */
const look = (page: Page) => page.evaluate((): Stop | null => {
  const a = document.activeElement as HTMLElement | null;
  if (a == null || a === document.body || a === document.documentElement) return null;
  const name = (el: Element) => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${[...el.classList].map((c) => `.${c}`).join('')}`;
  const d = a.dataset;
  const details = a.tagName === 'SUMMARY' ? a.parentElement as HTMLDetailsElement : null;
  const term = a.closest('.gloss') != null ? a.closest('.row')?.querySelector('input') : null;
  const key = a.id ? `#${a.id}`
    : d.indexEntry ? `entry:${d.indexEntry}`
    : d.highlight ? `highlight:${d.highlight}`
    : d.chip ? `chip:${d.chip}`
    : d.control ? `control:${d.control}`
    : d.openSheet != null ? 'open-sheet'
    : details != null ? `summary:${details.dataset.group ?? details.closest('[data-term]')?.getAttribute('data-term')}`
    : term != null ? `gloss:${term.id}`
    : a instanceof HTMLInputElement ? `input:${a.name}=${a.value}`
    : a instanceof HTMLAnchorElement ? `a:${a.getAttribute('href')}`
    : `${a.tagName.toLowerCase()}:${(a.textContent ?? '').trim()}`;

  const problems: string[] = [];
  const r = a.getBoundingClientRect();
  let [x0, y0, x1, y1] = [r.left, r.top, r.right, r.bottom];
  const cut = (l: number, t: number, rr: number, b: number) => {
    [x0, y0, x1, y1] = [Math.max(x0, l), Math.max(y0, t), Math.min(x1, rr), Math.min(y1, b)];
  };
  cut(0, 0, document.documentElement.clientWidth, document.documentElement.clientHeight);
  for (let el: Element | null = a; el != null && el !== document.documentElement; el = el.parentElement) {
    const s = getComputedStyle(el);
    if (el !== a && (s.overflowX !== 'visible' || s.overflowY !== 'visible')) {
      const b = el.getBoundingClientRect();
      const [l, t] = [b.left + el.clientLeft, b.top + el.clientTop];
      cut(l, t, l + el.clientWidth, t + el.clientHeight);
    }
    if (s.position === 'fixed') break;
  }
  const at = (b: DOMRect) => `${Math.round(b.left)},${Math.round(b.top)} ${Math.round(b.width)}x${Math.round(b.height)}`;
  if (x1 - x0 < 1 || y1 - y0 < 1) problems.push(`hidden: none of its box (${at(r)}) is on screen`);
  else {
    for (const el of document.querySelectorAll('body *')) {
      const pos = getComputedStyle(el).position;
      if ((pos !== 'sticky' && pos !== 'fixed') || el.contains(a) || a.contains(el)) continue;
      const b = el.getBoundingClientRect();
      const [ox0, oy0] = [Math.max(x0, b.left), Math.max(y0, b.top)];
      const [w, h] = [Math.min(x1, b.right) - ox0, Math.min(y1, b.bottom) - oy0];
      if (w <= 1 || h <= 1) continue;
      let over = false;
      for (const fx of [0.1, 0.5, 0.9]) {
        for (const fy of [0.1, 0.5, 0.9]) {
          const stack = document.elementsFromPoint(ox0 + w * fx, oy0 + h * fy);
          const i = stack.findIndex((n) => a.contains(n)), j = stack.findIndex((n) => el.contains(n));
          if (j >= 0 && (i < 0 || j < i)) over = true;
        }
      }
      if (over) problems.push(`covered by ${name(el)} (${pos}, ${at(b)}): ${Math.round(w)}x${Math.round(h)} px of its ${at(r)}`);
    }
  }
  return { key, open: details?.open ?? null, problems };
});

interface Walked { stops: Stop[]; problems: string[]; ended: boolean }

/** Press `key` until focus leaves the page or comes back round to its first stop, looking at every stop. `at` may act on
 *  a stop -- open a closed group, walk a family's benchmarks with the arrows -- and returns the stops it looked at. A
 *  first press that leaves the page (a walk begun where the last one came round) is pressed again. */
async function walk(page: Page, key: 'Tab' | 'Shift+Tab', at: (s: Stop) => Promise<Stop[]> = async () => [], max = 3000): Promise<Walked> {
  const stops: Stop[] = [];
  let ended = false;
  for (let i = 0; i < max && !ended; i++) {
    await page.keyboard.press(key);
    const s = await look(page);
    if (s == null && i === 0) continue;
    if (s == null || (stops.length > 0 && s.key === stops[0].key)) ended = true;
    else stops.push(s, ...(await at(s)));
  }
  return { stops, problems: stops.flatMap((s) => s.problems.map((p) => `${s.key}: ${p}`)), ended };
}

/** Press `key` until focus is on what `on` accepts. */
async function pressUntil(page: Page, key: 'Tab' | 'Shift+Tab', on: (s: Stop) => boolean, what: string, max = 1500): Promise<Stop> {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press(key);
    const s = await look(page);
    if (s != null && on(s)) return s;
  }
  throw new Error(`${max} presses of ${key} never reached ${what}`);
}

const missing = (keys: string[], walked: Walked) => {
  const seen = new Set(walked.stops.map((s) => s.key));
  return keys.filter((k) => !seen.has(k));
};

/** A page's first control, the site's name in the header, and its last, the footer's commit link (BuildFooter.astro). */
const TOP = 'a:/';
const FOOTER = /^a:\S*\/commit\/[0-9a-f]{40}$/;

/** The walk went all the way: it ended, and on `last`, not wherever focus fell to the page on the way. */
function complete(w: Walked, last: string | RegExp) {
  expect(w.ended, 'the walk came to an end').toBe(true);
  const at = w.stops.at(-1)?.key ?? '(no stop)';
  const what = 'the walk ends on the last control, focus never falling to the page on the way';
  if (typeof last === 'string') expect(at, what).toBe(last);
  else expect(at, what).toMatch(last);
}

// ---- the two views ------------------------------------------------------------------------------------------------

async function ready(page: Page, q = '') {
  await page.goto(`/benchmarks/${q}`);
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'ready');
}

async function drawn(page: Page, q = '') {
  await page.goto(`/atlas/${q}`);
  await expect(page.locator('[data-atlas-view]')).toHaveAttribute('data-state', 'drawn');
  await expect(page.locator('[data-atlas-index="island"]')).toHaveCount(1);
}

/** On a closed <summary>, Enter: the group or subdomain list opens, and Tab goes on into it. */
const opening = (page: Page) => async (s: Stop): Promise<Stop[]> => {
  if (s.open !== false) return [];
  await page.keyboard.press('Enter');
  const now = (await look(page))!;
  expect(now, `Enter opens ${s.key}`).toMatchObject({ key: s.key, open: true });
  return [];
};

/** On a family's Highlight, the arrows down through every benchmark in it. */
const arrows = (page: Page) => async (s: Stop): Promise<Stop[]> => {
  const f = s.key.startsWith('highlight:') ? s.key.slice('highlight:'.length) : null;
  if (f == null) return [];
  const seen: Stop[] = [];
  for (const _ of ENTRIES.get(f)!) {
    await page.keyboard.press('ArrowDown');
    seen.push((await look(page))!);
  }
  return seen;
};

/** The Atlas's selection is `want`, in that order (islands/AtlasSelection.tsx publishes it on its toolbar). */
async function selected(page: Page, want: string[]) {
  await expect(page.locator('[data-atlas-selection]')).toHaveAttribute('data-atlas-selection', want.join(' '));
  await expect(page.locator('[data-atlas-selection] .count')).toHaveText(`${want.length} selected`);
}

// ---- what the preview is ------------------------------------------------------------------------------------------

test('the preview is what these expectations read: families of several benchmarks, two capabilities, a filter that matches none', () => {
  expect(FAMILIES.length).toBeGreaterThan(1);
  expect(NODES.map((n) => n.id).sort()).toEqual(ROWS.map((r) => r.id).sort());
  expect(FAMILIES.every((f) => ENTRIES.get(f.id)!.length > 0), 'every family places a benchmark').toBe(true);
  expect([C, C2, EM].every((x) => x != null)).toBe(true);
  expect(DISJOINT, 'a capability and an evaluation method that never meet').not.toBeNull();
});

// ---- the failure case the verification names: pointer events disabled ----------------------------------------------

test('the failure case: with pointer events disabled, a click or a wheel reaches nothing on either view', async ({ page }) => {
  await ready(page);
  const term = page.locator(`#${domId('c', C)}`);
  const at = (await term.boundingBox())!;
  await page.mouse.click(at.x + at.width / 2, at.y + at.height / 2);
  await page.waitForTimeout(300);
  expect(await blocked(page), 'the click was swallowed').toBeGreaterThan(2);
  await expect(term).not.toBeChecked();
  await expect(page).toHaveURL('/benchmarks/');
  // a chip, from a link that applies one
  await ready(page, query({ c: [C] }));
  const chip = (await page.locator('button.chip').boundingBox())!;
  await page.mouse.click(chip.x + chip.width / 2, chip.y + chip.height / 2);
  await page.waitForTimeout(300);
  await expect(page.locator('button.chip')).toHaveCount(1);
  await expect(page).toHaveURL(`/benchmarks/${query({ c: [C] })}`);

  // the Atlas: a click on a family's Highlight and on "Select all N visible", and a wheel over the map, which sigma would
  // take as a zoom
  await drawn(page);
  const camera = () => page.locator('[data-atlas-view]').evaluate((el) => (el as any).atlasProbe.renderer.getCamera().getState());
  const home = await camera();
  for (const name of [/^Highlight /, /^Select all \d+ visible$/]) {
    const b = (await page.getByRole('button', { name }).first().boundingBox())!;
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  }
  const map = (await page.locator('[data-atlas-canvas]').boundingBox())!;
  await page.mouse.move(map.x + map.width / 2, map.y + map.height / 2);
  await page.mouse.wheel(0, -400);
  await page.waitForTimeout(300);
  expect(await blocked(page), 'the clicks and the wheel were swallowed').toBeGreaterThan(4);
  await expect(page.locator('[data-atlas-index="island"] [aria-pressed="true"]')).toHaveCount(0);
  await expect(page).toHaveURL('/atlas/');
  await selected(page, []);
  expect(await camera(), 'the wheel zoomed nothing').toEqual(home);
});

// ---- the facet UI: /benchmarks/ -------------------------------------------------------------------------------------

test.describe(`the facet UI at ${DESKTOP.width} by ${DESKTOP.height}`, () => {
  test.use({ viewport: DESKTOP });

  test('Tab reaches the skip link, every group, every enabled term and its definition, every result; nothing hides the focus', async ({ page }) => {
    test.setTimeout(300_000);
    await ready(page);
    const down = await walk(page, 'Tab', opening(page));
    complete(down, FOOTER);
    expect(down.problems, 'nothing hides the focus at any stop').toEqual([]);
    await expect(page.locator('aside.rail details:not([open])'), 'every group and subdomain list was opened from the keyboard').toHaveCount(0);
    const terms = await page.$$eval('aside.rail input[type="checkbox"]:not(:disabled)', (xs) => xs.map((x) => x.id));
    expect(terms.length).toBeGreaterThan(0);
    const groups = await page.$$eval('aside.rail details.group', (ds) => ds.map((x) => `summary:${x.getAttribute('data-group')}`));
    const results = await page.$$eval('ol.results > li > a', (as) => as.map((x) => `a:${x.getAttribute('href')}`));
    expect(results).toHaveLength(ROWS.length);
    expect(missing(['a:#browse-results', ...groups, ...terms.flatMap((id) => [`#${id}`, `gloss:${id}`]), ...results], down)).toEqual([]);
    // and back up from the end
    const up = await walk(page, 'Shift+Tab');
    complete(up, TOP);
    expect(up.problems).toEqual([]);
    expect(missing(results, up)).toEqual([]);
    await noPointer(page);
  });

  test('the known gap: a term no benchmark carries is disabled, so the definition its hover shows has no keyboard path', async ({ page }) => {
    // Expected to fail until it is decided: the spec's header says what would close it and why that is the
    // maintainer's decision rather than this task's. An unexpected pass fails the suite, so the mark comes off with the fix.
    test.fail();
    test.setTimeout(300_000);
    await ready(page);
    const disabled = await page.$$eval('aside.rail input[type="checkbox"]:disabled', (xs) => xs.map((x) => x.id));
    expect(disabled.length, 'the preview has terms no benchmark carries').toBeGreaterThan(0);
    const down = await walk(page, 'Tab', opening(page));
    complete(down, FOOTER);
    expect(missing(disabled.map((id) => `gloss:${id}`), down), 'every disabled term\'s definition is reachable from the keyboard').toEqual([]);
  });

  test('operated from the keyboard: Space on a term, Enter on a group, the skip link, a chip, "Clear all filters", the empty result\'s way out', async ({ page }) => {
    test.setTimeout(180_000);
    await ready(page);
    // a term: Space checks it and the list narrows to what carries it; Space again lets it go
    const c = `#${domId('c', C)}`;
    await pressUntil(page, 'Tab', (s) => s.key === c, `${C}'s checkbox`);
    await page.keyboard.press('Space');
    await expect(page.locator(c)).toBeChecked();
    await expect(page).toHaveURL(`/benchmarks/${query({ c: [C] })}`);
    await expect(page.locator('ol.results > li')).toHaveCount(CS.size);
    await page.keyboard.press('Space');
    await expect(page.locator(c)).not.toBeChecked();
    await expect(page).toHaveURL('/benchmarks/');
    await expect(page.locator('ol.results > li')).toHaveCount(ROWS.length);
    // a group: Shift+Tab back to its summary; Enter closes it, and Tab passes its terms by; Enter opens it again
    await pressUntil(page, 'Shift+Tab', (s) => s.key === 'summary:c', 'the capability group');
    await page.keyboard.press('Enter');
    await expect(page.locator('details[data-group="c"]')).not.toHaveAttribute('open');
    await page.keyboard.press('Tab');
    expect((await look(page))!.key, 'a closed group\'s terms are out of the Tab order').toBe('summary:em');
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Enter');
    await expect(page.locator('details[data-group="c"]')).toHaveAttribute('open');
    await page.keyboard.press('Tab');
    expect((await look(page))!.key).toBe(`#${await page.locator('details[data-group="c"] input:not(:disabled)').first().getAttribute('id')}`);

    // chips, from a link that applies three: the second skip link passes the rail, and Enter on a chip removes its filter
    const three = { c: [C, C2], em: [EM] };
    await ready(page, query(three));
    await pressUntil(page, 'Tab', (s) => s.key === 'a:#browse-results', 'the skip link', 10);
    await page.keyboard.press('Enter');
    expect((await look(page))!.key, 'the skip link moves focus to the results').toBe('#browse-results');
    await page.keyboard.press('Tab');
    expect((await look(page))!.key).toBe(`chip:c=${[C, C2].sort()[0]}`);
    await page.keyboard.press('Enter');
    await expect(page.locator('button.chip')).toHaveCount(2);
    await expect(page).toHaveURL(`/benchmarks/${query({ c: [[C, C2].sort()[1]], em: [EM] })}`);
    // "Clear all filters", reached by Tab and pressed with Enter
    await pressUntil(page, 'Tab', (s) => s.key === 'button:Clear all filters', '"Clear all filters"');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL('/benchmarks/');
    await expect(page.locator('.applied .none')).toHaveText('No filter applied.');

    // the empty result's way out: "Remove ...: ..." pressed with Enter leaves a list
    await ready(page, query({ c: [DISJOINT!.c], em: [DISJOINT!.em] }));
    await expect(page.locator('[data-empty="filter"]')).toBeVisible();
    await pressUntil(page, 'Tab', (s) => s.key === 'a:#browse-results', 'the skip link', 10);
    await page.keyboard.press('Enter');
    await pressUntil(page, 'Tab', (s) => s.key.startsWith('button:Remove '), 'the empty result\'s "Remove ..."', 10);
    await page.keyboard.press('Enter');
    await expect(page.locator('button.chip')).toHaveCount(1);
    await expect(page.locator('ol.results > li').first()).toBeVisible();
    await noPointer(page);
  });
});

for (const vp of [PHONE, SIDEWAYS]) {
  test.describe(`the facet UI at ${vp.width} by ${vp.height}, the sticky bar's layout`, () => {
    test.use({ viewport: vp });

    test('the sticky bar never covers the focus: Tab down the page, Shift+Tab back up, and Tab from the bar to the top of the list', async ({ page }) => {
      test.setTimeout(240_000);
      const three = { c: [C, C2], em: [EM] };
      await ready(page, query(three));
      const bar = page.locator('.results-head');
      await expect(bar, 'the bar is sticky at this width').toHaveCSS('position', 'sticky');
      const results = await page.$$eval('ol.results > li > a', (as) => as.map((x) => `a:${x.getAttribute('href')}`));
      expect(results.length, 'a list long enough to scroll under the bar').toBeGreaterThan(20);
      const chips = await page.$$eval('button.chip', (bs) => bs.map((b) => `chip:${b.getAttribute('data-chip')}`));
      expect(chips).toHaveLength(3);

      const down = await walk(page, 'Tab');
      complete(down, FOOTER);
      expect(down.problems).toEqual([]);
      expect(missing(['open-sheet', ...chips, 'button:Clear all filters', ...results], down)).toEqual([]);
      const up = await walk(page, 'Shift+Tab');
      complete(up, TOP);
      expect(up.problems, 'climbing the list, no result is left under the bar').toEqual([]);
      expect(missing(results, up)).toEqual([]);

      // the bar's button with the page scrolled to its end (End, from the keyboard), and Tab: the list's first result is
      // far above, and is brought into view below the bar, not under it
      await pressUntil(page, 'Tab', (s) => s.key === 'open-sheet', '"Filters (3)"');
      await page.keyboard.press('End');
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(vp.height);
      expect((await look(page))!.problems, 'the bar\'s own button, in the stuck bar').toEqual([]);
      await pressUntil(page, 'Tab', (s) => s.key === results[0], 'the first result', 10);
      expect((await look(page))!.problems).toEqual([]);
      await noPointer(page);
    });

    test('the sheet: opened with Enter, every term reached inside it and none under its footer, a term chosen, Escape closes it', async ({ page }) => {
      test.setTimeout(300_000);
      await ready(page);
      const open = page.locator('button[data-open-sheet]');
      const isOpen = () => page.locator('#browse-sheet').evaluate((el) => el.matches(':popover-open'));
      await pressUntil(page, 'Tab', (s) => s.key === 'open-sheet', '"Filters (0)"', 10);
      await page.keyboard.press('Enter');
      await expect.poll(isOpen).toBe(true);
      await expect.poll(() => page.evaluate(() => document.activeElement?.closest('#browse-sheet') != null), 'focus moves into the sheet').toBe(true);

      const down = await walk(page, 'Tab', opening(page));
      const done = `button:Show ${ROWS.length} benchmarks`;
      complete(down, done);
      expect(down.problems, 'no term is left under the sheet\'s footer').toEqual([]);
      const terms = await page.$$eval('#browse-sheet input[type="checkbox"]:not(:disabled)', (xs) => xs.map((x) => x.id));
      expect(terms.length).toBeGreaterThan(0);
      expect(missing([...terms.map((id) => `#${id}`), done], down)).toEqual([]);
      expect(down.stops.every((s) => s.key === done || s.key.startsWith('#f-') || s.key.startsWith('gloss:') || s.key.startsWith('summary:')),
        'while it is open, Tab stays in the sheet').toBe(true);
      const up = await walk(page, 'Shift+Tab');
      complete(up, 'summary:d');
      expect(up.problems).toEqual([]);
      expect(missing(terms.map((id) => `#${id}`), up)).toEqual([]);

      // a term chosen in the sheet with Space, and Escape: the sheet closes, focus is back on its button, the chip is in the bar
      await pressUntil(page, 'Tab', (s) => s.key === `#${domId('c', C)}`, `${C}'s checkbox`);
      await page.keyboard.press('Space');
      await expect(page.locator(`#${domId('c', C)}`)).toBeChecked();
      await expect(page.locator('#browse-sheet .sheet-done')).toHaveText(`Show ${CS.size} benchmarks`);
      await page.keyboard.press('Escape');
      await expect.poll(isOpen).toBe(false);
      await expect(open).toBeFocused();
      await expect(open).toHaveText('Filters (1)');
      await expect(page.locator('.results-head button.chip')).toHaveCount(1);
      await noPointer(page);
    });
  });
}

// ---- the Atlas: /atlas/ ---------------------------------------------------------------------------------------------

for (const vp of [DESKTOP, SIDEWAYS]) {
  test.describe(`the Atlas at ${vp.width} by ${vp.height}`, () => {
    test.use({ viewport: vp });

    test('Tab reaches the filter bar, the selection and every family, the arrows every benchmark; nothing hides the focus', async ({ page }) => {
      test.setTimeout(240_000);
      await drawn(page);
      const down = await walk(page, 'Tab', arrows(page));
      complete(down, FOOTER);
      expect(down.problems, 'nothing hides the focus at any stop').toEqual([]);
      expect(missing([
        'control:d', 'control:c', 'control:em', 'control:lc',
        `button:Select all ${NODES.length} visible`, 'button:Clear selection', 'button:Lasso',
        ...FAMILIES.map((f) => `highlight:${f.id}`), ...NODES.map((n) => `entry:${n.id}`),
      ], down)).toEqual([]);
      // the index's order: each family's Highlight, then its benchmarks by name
      const order = down.stops.map((s) => s.key).filter((k) => k.startsWith('highlight:') || k.startsWith('entry:'));
      expect(order).toEqual(FAMILIES.flatMap((f) => [`highlight:${f.id}`, ...ENTRIES.get(f.id)!.map((e) => `entry:${e.id}`)]));
      const up = await walk(page, 'Shift+Tab');
      complete(up, TOP);
      expect(up.problems).toEqual([]);
      await noPointer(page);
    });
  });
}

test.describe(`the Atlas's selection at ${DESKTOP.width} by ${DESKTOP.height}`, () => {
  test.use({ viewport: DESKTOP });

  test('SC 2.5.7: a selection completes from the keyboard -- the filter, "Select all N visible", Space, the summary\'s button -- the lasso never pressed', async ({ page }) => {
    test.setTimeout(120_000);
    await drawn(page);
    // the filter bar's Domain control, from the keyboard: Tab to it, and Down picks the first family that has benchmarks
    // (a closed <select> takes the arrows itself on Windows and Linux; on macOS they open its list)
    await pressUntil(page, 'Tab', (s) => s.key === 'control:d', 'the Domain filter', 20);
    await page.keyboard.press('ArrowDown');
    const select = page.locator('select[data-control="d"]');
    await expect(select).not.toHaveValue('');
    const d = await select.inputValue();
    const fam = NODES.filter((n) => n.cluster === d || n.domain_primary === d).map((n) => n.id);
    expect(fam.length).toBeGreaterThan(0);
    await expect(page.locator('[data-atlas-view]')).toHaveAttribute('data-matching', String(fam.length));

    // the primary way in: Tab on to "Select all N visible", N what the filter leaves in ink, and Enter
    await pressUntil(page, 'Tab', (s) => s.key.startsWith('button:Select all '), '"Select all N visible"', 20);
    expect((await look(page))!.key).toBe(`button:Select all ${fam.length} visible`);
    await page.keyboard.press('Enter');
    await selected(page, fam);

    // per node: Tab into the index, to a family the filter dims, Down to its first benchmark, and Space adds it
    const g = FAMILIES.find((f) => f.id !== d.split('/')[0])!;
    const e = ENTRIES.get(g.id)![0];
    await pressUntil(page, 'Tab', (s) => s.key === `highlight:${g.id}`, `${g.id}'s Highlight`, 40);
    await page.keyboard.press('ArrowDown');
    expect((await look(page))!.key).toBe(`entry:${e.id}`);
    await page.keyboard.press('Space');
    await selected(page, [...fam, e.id]);
    const panel = page.locator(`[data-atlas-panel="${e.id}"]`);
    await expect(panel).toBeVisible();

    // its summary's button, reached by Tab past the index, takes it out with Enter and puts it back, focus kept on it
    await pressUntil(page, 'Tab', (s) => s.key === 'button:Remove from selection', 'the summary\'s "Remove from selection"', 40);
    await page.keyboard.press('Enter');
    await selected(page, fam);
    expect((await look(page))!.key).toBe('button:Add to selection');
    await page.keyboard.press('Enter');
    await selected(page, [...fam, e.id]);

    // and "Clear selection", back up the page with Shift+Tab, empties it
    await pressUntil(page, 'Shift+Tab', (s) => s.key === 'button:Clear selection', '"Clear selection"', 60);
    await page.keyboard.press('Enter');
    await selected(page, []);
    await expect(page.getByRole('button', { name: 'Lasso' }), 'the lasso was never pressed').toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('canvas.lasso')).toHaveCount(0);
    await noPointer(page);
  });
});

// ---- SC 2.4.11's failure case: a doctored page ------------------------------------------------------------------

test.describe('the failure case for SC 2.4.11', () => {
  test.use({ viewport: DESKTOP });

  test('a page doctored so that a sticky bar, or a sticky table header, covers the focus fails the check', async ({ page }) => {
    test.setTimeout(120_000);
    // the results' bar made sticky over the list at this width, as the phone layout has it, with no margin kept under it
    await ready(page);
    await page.addStyleTag({ content: '.browse .results-head { position: sticky; z-index: 1; inset-block-start: 0; padding-block: var(--sp-6); background: var(--c-bg); } .browse * { scroll-margin: 0 !important; }' });
    const bar = await walk(page, 'Shift+Tab', undefined, 60);
    expect(bar.problems.length, 'climbing the list, a result is left under the sticky bar').toBeGreaterThan(0);
    expect(bar.problems[0]).toMatch(/^a:\/benchmarks\/[^:]+\/: covered by div\.results-head \(sticky, /);

    // a table of links under a sticky header, after the list
    await ready(page);
    await page.evaluate(() => {
      const t = document.createElement('table');
      t.innerHTML = `<thead><tr><th style="position: sticky; inset-block-start: 0; block-size: 3rem; background: var(--c-bg)">Doctored</th></tr></thead>`
        + `<tbody>${Array.from({ length: 60 }, (_, i) => `<tr><td><a href="#doctored-${i}">row ${i}</a></td></tr>`).join('')}</tbody>`;
      document.querySelector('main')!.append(t);
    });
    const th = await walk(page, 'Shift+Tab', undefined, 60);
    expect(th.problems.length, 'climbing the table, a row is left under its sticky header').toBeGreaterThan(0);
    expect(th.problems[0]).toMatch(/^a:#doctored-\d+: covered by th \(sticky, /);
  });

  test.describe('at phone width', () => {
    test.use({ viewport: PHONE });

    test('the phone layout with its scroll margins taken out fails the check', async ({ page }) => {
      test.setTimeout(120_000);
      await ready(page);
      await page.addStyleTag({ content: '.browse * { scroll-margin: 0 !important; }' });
      const up = await walk(page, 'Shift+Tab', undefined, 80);
      expect(up.problems.length, 'without them, climbing the list leaves a result under the bar').toBeGreaterThan(0);
      expect(up.problems[0]).toMatch(/covered by div\.results-head \(sticky, /);
    });
  });
});

// ---- SC 2.5.8: chips, badges, legend toggles -------------------------------------------------------------------------

interface Target { key: string; w: number; h: number; via: 'size' | 'spacing' | 'inline' | null }

/** Every element `subjects` names that is rendered, measured against SC 2.5.8: 24 by 24 CSS px, or else one of its
 *  exceptions as the SC states them. Spacing: a circle of 24px diameter centred on the undersized target's box
 *  intersects no other target's box and no other undersized target's circle (a circle that only touches does not
 *  intersect). Inline: the target is inline, in a line box that holds text which is not a target's. The other targets
 *  are every rendered link, button, form control, summary, label of a control, and element in the Tab order. */
const measure = (page: Page, subjects: string) => page.evaluate((sel): Target[] => {
  const R = 12;
  const TARGET = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, label[for], [tabindex]:not([tabindex="-1"])';
  const box = (el: Element) => el.getBoundingClientRect();
  const shown = (el: Element) => el.checkVisibility({ visibilityProperty: true, checkVisibilityCSS: true } as CheckVisibilityOptions) && box(el).width > 0 && box(el).height > 0;
  const small = (b: DOMRect) => b.width < 24 - 0.01 || b.height < 24 - 0.01;
  const centre = (b: DOMRect) => ({ x: b.left + b.width / 2, y: b.top + b.height / 2 });
  const hitsBox = (c: { x: number; y: number }, b: DOMRect) => {
    const dx = Math.max(b.left - c.x, 0, c.x - b.right), dy = Math.max(b.top - c.y, 0, c.y - b.bottom);
    return dx * dx + dy * dy < R * R;
  };
  const same = (a: Element, b: Element) => a === b || a.contains(b) || b.contains(a)
    || (b instanceof HTMLLabelElement && b.control === a) || (a instanceof HTMLLabelElement && a.control === b);
  const others = [...document.querySelectorAll(TARGET)].filter(shown);
  const inline = (el: Element) => {
    if (getComputedStyle(el).display !== 'inline') return false;
    let block = el.parentElement!;
    while (getComputedStyle(block).display === 'inline') block = block.parentElement!;
    const b = box(el);
    const texts = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    for (let t = texts.nextNode(); t != null; t = texts.nextNode()) {
      if ((t.textContent ?? '').trim() === '' || t.parentElement!.closest(TARGET) != null) continue;
      const range = document.createRange();
      range.selectNodeContents(t);
      if ([...range.getClientRects()].some((q) => q.bottom > b.top && q.top < b.bottom)) return true;
    }
    return false;
  };
  return [...document.querySelectorAll(sel)].filter(shown).map((el) => {
    const b = box(el);
    const key = `${el.tagName.toLowerCase()}${[...el.classList].map((c) => `.${c}`).join('')}:${(el.textContent ?? '').replace(/\s+/g, ' ').trim()}`;
    let via: Target['via'] = null;
    if (!small(b)) via = 'size';
    else {
      const c = centre(b);
      const clear = others.every((o) => {
        if (same(el, o)) return true;
        const ob = box(o);
        if (hitsBox(c, ob)) return false;
        if (small(ob)) {
          const oc = centre(ob);
          if (Math.hypot(c.x - oc.x, c.y - oc.y) < 2 * R) return false;
        }
        return true;
      });
      if (clear) via = 'spacing';
      else if (inline(el)) via = 'inline';
    }
    return { key, w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10, via };
  });
}, subjects);

/** The targets that meet SC 2.5.8 only by an exception, and which. A new entry is a design decision: add it here. */
const EXCEPTIONS: Record<string, Target['via']> = {};

function sizes(found: Target[], what: string) {
  expect(found.length, `${what}: something to measure`).toBeGreaterThan(0);
  expect(found.filter((t) => t.via == null), `${what}: under 24 by 24 CSS px, with no exception`).toEqual([]);
  const excepted = found.filter((t) => t.via !== 'size').map((t) => [t.key, t.via]);
  expect(excepted, `${what}: the targets that rely on an exception`).toEqual(excepted.filter(([k, v]) => EXCEPTIONS[k as string] === v));
}

const BROWSE_TARGETS = '[data-browse-view] :is(.chip, .clear, .drop, .open-sheet, .sheet-done, a.badge, button.badge, .badge a, .badge button)';
// `.selection a` matches nothing yet: it is the toolbar's "Add to suite basket" link P6-S4-T01 adds, measured once it lands
const ATLAS_TARGETS = '[data-atlas-view] :is(.chip, .clear, .highlight, .selection button, .selection a, .actions a, .actions button, a.badge, button.badge, .badge a, .badge button)';

for (const vp of [DESKTOP, PHONE]) {
  test.describe(`target sizes at ${vp.width} by ${vp.height}`, () => {
    test.use({ viewport: vp });

    test('SC 2.5.8: every chip, legend toggle and the buttons beside them are 24 by 24 CSS px or meet an exception', async ({ page }) => {
      test.setTimeout(120_000);
      // the browse view with three filters applied (three chips and "Clear all filters"), and with none that meet ("Remove ...")
      await ready(page, query({ c: [C, C2], em: [EM] }));
      const chips = await measure(page, BROWSE_TARGETS);
      expect(chips.filter((t) => t.key.startsWith('button.chip')), 'the three chips').toHaveLength(3);
      sizes(chips, '/benchmarks/ with three filters');
      await ready(page, query({ c: [DISJOINT!.c], em: [DISJOINT!.em] }));
      sizes(await measure(page, BROWSE_TARGETS), '/benchmarks/ with a filter that matches nothing');
      if (vp === PHONE) {
        // the sheet's own button, opened from the keyboard
        await pressUntil(page, 'Tab', (s) => s.key === 'open-sheet', '"Filters (2)"', 10);
        await page.keyboard.press('Enter');
        await expect(page.locator('#browse-sheet .sheet-done')).toBeVisible();
        sizes(await measure(page, BROWSE_TARGETS), '/benchmarks/ with its sheet open');
      }

      // the Atlas with two filters (two chips and "Clear all filters"), its legend toggles and its selection's buttons, and
      // a benchmark's summary opened with Space in the index
      await drawn(page, query({ c: [C], em: [EM] }));
      await pressUntil(page, 'Tab', (s) => s.key.startsWith('highlight:'), 'the index', 40);
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('Space');
      await expect(page.locator('[data-atlas-panel] .actions')).toBeVisible();
      const atlasTargets = await measure(page, ATLAS_TARGETS);
      expect(atlasTargets.filter((t) => t.key.startsWith('button.highlight')), 'every family\'s Highlight').toHaveLength(FAMILIES.length);
      sizes(atlasTargets, '/atlas/');
      await noPointer(page);
    });
  });
}

test('the failure case for SC 2.5.8: doctored 16px chips fail the check side by side, and pass it alone or inline in a sentence', async ({ page }) => {
  await ready(page);
  await page.evaluate(() => {
    const chip = 'all: unset; display: inline-block; inline-size: 16px; block-size: 16px';
    const d = document.createElement('div');
    d.id = 'doctored';
    d.innerHTML = `<p style="margin: 0; padding: 40px"><button class="probe tight" style="${chip}">a</button><button class="probe tight" style="${chip}; margin-inline-start: 2px">b</button></p>`
      + `<p style="margin: 0; padding: 40px"><button class="probe alone" style="${chip}">c</button></p>`
      + '<p style="margin: 0; padding: 40px; font-size: 12px">A sentence with <a class="probe inline" href="#one">one</a> <a class="probe inline" href="#two">two</a> links in it.</p>';
    document.querySelector('main')!.prepend(d);
  });
  expect((await measure(page, '#doctored .probe')).map((t) => [t.key, t.via])).toEqual([
    ['button.probe.tight:a', null], ['button.probe.tight:b', null],
    ['button.probe.alone:c', 'spacing'],
    ['a.probe.inline:one', 'inline'], ['a.probe.inline:two', 'inline'],
  ]);
  await noPointer(page);
});
