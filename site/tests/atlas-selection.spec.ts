// site/tests/atlas-selection.spec.ts -- P2-S5-T04 (09 S8.1 "2.5.7 Dragging Movements", S8.2; 10 V1 "Lasso-select").
// The Atlas's selection (islands/AtlasSelection.tsx, owned by islands/Atlas.tsx), in a browser, over the draft preview
// playwright.config.ts builds:
//
//   cd site && npx playwright test tests/atlas-selection.spec.ts
//
// Done when: "A full selection completes using the keyboard alone, with the lasso disabled." 09 S8.1's order of the ways
// in is what is checked: the filter is the primary one ("Select all N visible"), Space in the family index and the
// summary's button the per-node ones, the lasso a shortcut. Every expectation is computed here from the atlas.json the
// server was built from (build/preview/, scripts/preview_corpus.py) -- a family's benchmarks, the nodes a drawn path
// encloses, by this file's own point-in-polygon test -- not from the island's logic (whose lasso test is the canvas's
// isPointInPath). The selection is read where the island publishes it, the toolbar's data-atlas-selection: benchmark
// ids, in the order they were added.
//
// The failure case the verification names is checked as a failure: a selection that needs a pointer. The first test
// runs with pointer events blocked -- every event a mouse, pen or touch makes is swallowed at the window before any
// listener of the page's sees it, and counted -- and with the lasso off. It first shows the block holds (a drag over the
// map, a click on a node and clicks on the toolbar's buttons do nothing at all, and were each swallowed), then completes
// a selection from the keyboard alone: a family's Highlight in the index filters the map, Shift+Tab reaches "Select all N
// visible", Enter selects those N, Space in the index adds one more benchmark from another family (and takes it out and
// puts it back), and "Clear selection" empties it, focus never dropped. Nothing in it moves a node.
//
// The other tests use the pointer where it belongs: a click on a node and its summary's "Add to selection", and the
// lasso, off until pressed, whose drag selects the nodes inside its path that the filter leaves in ink and pans nothing.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Node { id: string; x: number; y: number; r: number; cluster: string; domain_primary: string; label: string }
interface Region { id: string; level: 'group' | 'family'; parent: string | null; label: string }
interface Row { id: string; domain: string; facets: Record<string, string[]> }
interface Camera { x: number; y: number; ratio: number; angle: number; animated: boolean }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const atlas = preview('atlas.json') as { nodes: Node[]; regions: Region[] };
const ROWS = (preview('facets.json') as { benchmarks: Row[] }).benchmarks;
const tokens = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/tokens.json', import.meta.url)), 'utf8'));
const INK = tokens.themes.light['c-ink'].hex as string;
const NODES = atlas.nodes;
const FAMILIES = atlas.regions.filter((r) => r.level === 'family');
const fold = (s: string) => s.toLowerCase();
const byName = (a: Node, b: Node) => (fold(a.label) !== fold(b.label) ? (fold(a.label) < fold(b.label) ? -1 : 1) : a.id < b.id ? -1 : 1);
/** A family's benchmarks in atlas.json's order (the order "Select all N visible" adds them in), and as the index lists them. */
const MEMBERS = new Map(FAMILIES.map((f) => [f.id, NODES.filter((n) => n.cluster === f.id)]));
const LISTED = new Map(FAMILIES.map((f) => [f.id, [...MEMBERS.get(f.id)!].sort(byName)]));
// the first family in the index with three benchmarks or more, and the largest
const PICK = FAMILIES.findIndex((f) => MEMBERS.get(f.id)!.length >= 3);
const LARGEST = [...FAMILIES].sort((a, b) => MEMBERS.get(b.id)!.length - MEMBERS.get(a.id)!.length || (a.id < b.id ? -1 : 1))[0].id;
// the largest subdomain of a family that has others: a filter on it fits the camera to it with its siblings, dimmed, in view
const SUBS = NODES.reduce((m, n) => m.set(n.domain_primary, (m.get(n.domain_primary) ?? 0) + 1), new Map<string, number>());
const SIBLED = (sub: string) => new Set(NODES.filter((n) => n.cluster === NODES.find((x) => x.domain_primary === sub)!.cluster).map((n) => n.domain_primary)).size > 1;
const SUB = [...SUBS].filter(([d]) => SIBLED(d)).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0]?.[0];
// a capability and an evaluation method each carried by some benchmark, never by the same one (as tests/atlas.spec.ts)
const DISJOINT = (() => {
  const has = (r: Row, f: string, v: string) => r.facets[f].includes(v);
  const caps = [...new Set(ROWS.flatMap((r) => r.facets.capability))].sort();
  const ems = [...new Set(ROWS.flatMap((r) => r.facets.evaluation_method))].sort();
  for (const c of caps) for (const em of ems) if (!ROWS.some((r) => has(r, 'capability', c) && has(r, 'evaluation_method', em))) return { c, em };
  return null;
})();
const ids = (ns: Node[]) => ns.map((n) => n.id);

// ---- reading the page ---------------------------------------------------------------------------------------

const PROBE = '[data-atlas-view]';
const SELECTION = '[data-atlas-selection]';
// the island's probe is { renderer, graph } (islands/Atlas.tsx); these readers copy and never write, as the other specs'
const camera = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const c = (el as any).atlasProbe.renderer.getCamera();
  return { ...c.getState(), animated: c.isAnimated() } as Camera;
});
const positions = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const { graph } = (el as any).atlasProbe;
  return Object.fromEntries(graph.mapNodes((id: string, a: { x: number; y: number }) => [id, [a.x, a.y]])) as Record<string, [number, number]>;
});
/** Each node's centre and radius in the map's viewport pixels: where sigma draws it now. */
const viewports = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const { renderer, graph } = (el as any).atlasProbe;
  return Object.fromEntries(graph.nodes().map((id: string) => {
    const d = renderer.getNodeDisplayData(id);
    const at = renderer.framedGraphToViewport(d);
    return [id, { x: at.x, y: at.y, r: renderer.scaleSize(d.size) }];
  })) as Record<string, { x: number; y: number; r: number }>;
});
const ASIS = Object.fromEntries(NODES.map((n) => [n.id, [n.x, n.y]]));
const HOME: Camera = { x: 0.5, y: 0.5, ratio: 1, angle: 0, animated: false };

/** The selection is `want`, in that order: the toolbar's list, its count, and the index's checks. */
async function selected(page: Page, want: string[]) {
  await expect(page.locator(SELECTION)).toHaveAttribute('data-atlas-selection', want.join(' '));
  await expect(page.locator(`${SELECTION} .count`)).toHaveText(`${want.length} selected`);
  const checked = await page.locator('[data-atlas-index="island"] a[data-selected]').evaluateAll((as) => as.map((a) => a.getAttribute('data-index-entry')!));
  expect(checked.sort(), 'the index checks exactly the selection').toEqual([...want].sort());
}

/** What has focus: its text, the index item it is, if any, and which list it is in. */
const focused = (page: Page) => page.evaluate(() => {
  const a = document.activeElement as HTMLElement | null;
  return {
    text: a?.textContent?.trim() ?? '',
    entry: a?.getAttribute('data-index-entry') ?? null,
    toggle: a?.getAttribute('data-highlight') ?? null,
    list: a?.closest('[data-atlas-index]')?.getAttribute('data-atlas-index') ?? null,
  };
});

/** Press `key` until focus is on what `on` accepts; forty presses at most. */
async function pressUntil(page: Page, key: 'Tab' | 'Shift+Tab', on: (f: Awaited<ReturnType<typeof focused>>) => boolean, what: string) {
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press(key);
    if (on(await focused(page))) return;
  }
  throw new Error(`forty presses of ${key} never reached ${what}`);
}

async function drawn(page: Page, query = '') {
  await page.goto(`/atlas/${query}`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'drawn');
  await expect(page.locator('[data-atlas-index="island"]')).toHaveCount(1);
}

/** Block every pointer. Each event a mouse, pen or touch makes is stopped at the window, in the capture phase, before
 *  any listener of the page's -- React's, sigma's -- sees it, its default action prevented, and counted in
 *  window.blocked. A click the keyboard makes (Enter or Space on a button, detail 0) is not a pointer's and goes on. */
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

/** The page coordinates of a node's centre. */
async function onPage(page: Page, id: string) {
  const box = (await page.locator('[data-atlas-canvas]').boundingBox())!;
  const v = (await viewports(page))[id];
  return { x: box.x + v.x, y: box.y + v.y };
}

// ---- what the preview is ------------------------------------------------------------------------------------

test('the preview is what these expectations read: families of several benchmarks, and a filter that matches none', () => {
  expect(PICK, 'a family with three benchmarks or more').toBeGreaterThanOrEqual(0);
  expect(FAMILIES.length).toBeGreaterThan(1);
  expect(NODES.map((n) => n.id).sort()).toEqual(ROWS.map((r) => r.id).sort());
  expect(DISJOINT, 'a capability and an evaluation method that never meet').not.toBeNull();
  expect(SUB, 'a subdomain beside others in its family').toBeDefined();
});

// ---- the failure case: no pointer, no lasso, the keyboard alone -------------------------------------------------

test('the failure case: with pointer events blocked and the lasso off, a full selection completes from the keyboard alone', async ({ page }) => {
  test.setTimeout(120_000);
  await blockPointers(page);
  await drawn(page);
  const lasso = page.getByRole('button', { name: 'Lasso' });
  const lassoOff = async () => {
    await expect(lasso, 'the lasso stays off').toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('canvas.lasso')).toHaveCount(0);
  };
  await lassoOff();
  await selected(page, []);

  // the block holds: a pointer does nothing here -- not a drag over the map, a click on a node, or a click on a button
  const f = FAMILIES[PICK];
  const a = await onPage(page, MEMBERS.get(f.id)![0].id);
  await page.mouse.move(a.x - 40, a.y - 40);
  await page.mouse.down();
  await page.mouse.move(a.x + 40, a.y - 40, { steps: 4 });
  await page.mouse.move(a.x + 40, a.y + 40, { steps: 4 });
  await page.mouse.move(a.x - 40, a.y + 40, { steps: 4 });
  await page.mouse.up();
  await page.mouse.click(a.x, a.y);
  for (const name of [/^Select all \d+ visible$/, /^Lasso$/]) {
    const b = (await page.getByRole('button', { name }).boundingBox())!;
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  }
  const swallowed = await blocked(page);
  expect(swallowed, 'every one of those pointer events was swallowed before the page saw it').toBeGreaterThan(10);
  await page.waitForTimeout(300);
  await selected(page, []);
  await lassoOff();
  await expect(page.locator('[data-atlas-panel]:not([data-atlas-panel=""])')).toHaveCount(0);
  expect(await camera(page), 'the drag panned nothing').toEqual(HOME);

  // 1. the filter, from the keyboard: Tab into the index, Tab to the family, Space on its Highlight
  await pressUntil(page, 'Tab', (x) => x.list === 'island', 'the family index');
  for (let i = 0; i < PICK; i++) await page.keyboard.press('Tab');
  expect(await focused(page)).toMatchObject({ toggle: f.id, list: 'island' });
  await page.keyboard.press('Space');
  const fam = ids(MEMBERS.get(f.id)!);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', String(fam.length));
  // the filter's own announcement first (09 S8.4, 500 ms after the change), so the selection's is read after it
  await expect(page.locator('[data-filter-status]')).toHaveText(`${fam.length} benchmarks match`);

  // 2. the primary way in: Shift+Tab back to "Select all N visible", N the family's benchmarks, and Enter
  await pressUntil(page, 'Shift+Tab', (x) => x.text.startsWith('Select all'), '"Select all N visible"');
  expect((await focused(page)).text).toBe(`Select all ${fam.length} visible`);
  await page.keyboard.press('Enter');
  await selected(page, fam);
  await expect(page.locator('[data-filter-status]'), 'said once, politely').toHaveText(`${fam.length} benchmarks selected`);
  expect((await focused(page)).text, 'focus stays on the button').toBe(`Select all ${fam.length} visible`);

  // 3. per node: Tab on into the index, to another family, Down to its first benchmark, and Space adds it -- though the
  //    filter dims it -- and shows its summary
  const g = FAMILIES[PICK === 0 ? 1 : 0];
  const e = LISTED.get(g.id)![0];
  await pressUntil(page, 'Tab', (x) => x.toggle === g.id, `${g.id}'s Highlight`);
  await page.keyboard.press('ArrowDown');
  expect((await focused(page)).entry).toBe(e.id);
  await page.keyboard.press('Space');
  await selected(page, [...fam, e.id]);
  await expect(page.locator(`[data-atlas-panel="${e.id}"]`)).toBeVisible();
  await expect(page.locator(`[data-atlas-index="island"] [data-index-entry="${e.id}"]`), 'the check is in the link\'s name').toHaveAccessibleName(/selected$/);
  await expect(page.locator('[data-filter-status]')).toHaveText(`${fam.length + 1} benchmarks selected`);
  // Space toggles: once more takes it out, and once more puts it back, at the end
  await page.keyboard.press('Space');
  await selected(page, fam);
  await expect(page.locator(`[data-atlas-panel="${e.id}"] button`, { hasText: 'Add to selection' })).toBeVisible();
  await page.keyboard.press('Space');
  await selected(page, [...fam, e.id]);
  expect((await focused(page)).entry, 'focus stays in the list').toBe(e.id);

  // that is a full selection, made with the keyboard alone: a family through the filter and one benchmark by hand

  // 4. and "Clear selection" empties it, focus kept on the button
  await pressUntil(page, 'Shift+Tab', (x) => x.text === 'Clear selection', '"Clear selection"');
  await page.keyboard.press('Enter');
  await selected(page, []);
  expect((await focused(page)).text).toBe('Clear selection');
  await expect(page.locator('[data-filter-status]')).toHaveText('0 benchmarks selected');

  // all of it with the keyboard alone: no pointer event since the block was shown to hold, the lasso off throughout,
  // and nothing moved
  expect(await blocked(page), 'no pointer event during the keyboard run').toBe(swallowed);
  await lassoOff();
  expect(await positions(page)).toEqual(ASIS);
});

// ---- the primary way in: the filter ------------------------------------------------------------------------------

test('"Select all N visible" takes what the filter leaves in ink: every node with no filter, none when it matches nothing, and it adds', async ({ page }) => {
  await drawn(page);
  const all = page.getByRole('button', { name: /^Select all \d+ visible$/ });
  await expect(all).toHaveText(`Select all ${NODES.length} visible`);
  await all.focus();
  await page.keyboard.press('Enter');
  await selected(page, ids(NODES));
  await page.getByRole('button', { name: 'Clear selection' }).focus();
  await page.keyboard.press('Enter');
  await selected(page, []);

  // one family, then another: the second adds to the first, in the order they were added, each benchmark once
  const [f, g] = [FAMILIES[PICK], FAMILIES.find((x) => x.id !== FAMILIES[PICK].id)!];
  await page.locator('select[data-control="d"]').selectOption(f.id);
  await expect(all).toHaveText(`Select all ${MEMBERS.get(f.id)!.length} visible`);
  await all.focus();
  await page.keyboard.press('Enter');
  await page.locator('select[data-control="d"]').selectOption(g.id);
  await expect(all).toHaveText(`Select all ${MEMBERS.get(g.id)!.length} visible`);
  await all.focus();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');                       // twice: what is selected already is not added again
  await selected(page, [...ids(MEMBERS.get(f.id)!), ...ids(MEMBERS.get(g.id)!)]);
  // a selection is not a filter: taking the filter off keeps it, and no node moved for any of it
  await page.locator('select[data-control="d"]').selectOption('');
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', 'all');
  await selected(page, [...ids(MEMBERS.get(f.id)!), ...ids(MEMBERS.get(g.id)!)]);
  expect(await positions(page)).toEqual(ASIS);

  // a filter that matches nothing leaves nothing to select
  await drawn(page, `?c=${DISJOINT!.c}&em=${DISJOINT!.em}&v=1`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', '0');
  await expect(all).toHaveText('Select all 0 visible');
  await all.focus();
  await page.keyboard.press('Enter');
  await selected(page, []);
});

// ---- per node, by click -------------------------------------------------------------------------------------------

/** The regions layer's pixel at a viewport point, where islands/Atlas.tsx rings a selected node. */
const pixel = (page: Page, p: { x: number; y: number }) => page.locator('[data-atlas-canvas] canvas.sigma-regions').evaluate((c, at) => {
  const dpr = window.devicePixelRatio || 1;
  return [...(c as HTMLCanvasElement).getContext('2d')!.getImageData(Math.round(at.x * dpr), Math.round(at.y * dpr), 1, 1).data];
}, p);
/** How many of the four points just outside a node's rim, where its ring goes, are drawn in --c-ink. */
async function ringed(page: Page, id: string) {
  const v = (await viewports(page))[id];
  const ink = [1, 3, 5].map((i) => parseInt(INK.slice(i, i + 2), 16));
  let n = 0;
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    const [r, g, b, a] = await pixel(page, { x: v.x + dx * (v.r + 3), y: v.y + dy * (v.r + 3) });
    if (a > 100 && Math.abs(r - ink[0]) < 48 && Math.abs(g - ink[1]) < 48 && Math.abs(b - ink[2]) < 48) n++;
  }
  return n;
}

test('a click on a node opens its summary, whose "Add to selection" adds it: a ring on the map, a check in the index', async ({ page }) => {
  // a subdomain with several benchmarks, from the link, so the nodes are large enough to aim at
  const sub = [...SUBS].filter(([, k]) => k >= 3).sort((x, y) => (x[0] < y[0] ? -1 : 1))[0][0];
  await drawn(page, `?d=${encodeURIComponent(sub)}&v=1`);
  await expect.poll(async () => {
    const c = await camera(page);
    return !c.animated && c.ratio < 1;
  }).toBe(true);
  const node = NODES.find((n) => n.domain_primary === sub)!;
  const cam = await camera(page);
  expect(await ringed(page, node.id), 'no ring before').toBeLessThanOrEqual(1);
  const at = await onPage(page, node.id);
  await page.mouse.click(at.x, at.y);
  const panel = page.locator(`[data-atlas-panel="${node.id}"]`);
  await expect(panel).toBeVisible();
  await selected(page, []);
  await panel.getByRole('button', { name: 'Add to selection' }).click();
  await selected(page, [node.id]);
  await expect(panel.getByRole('button', { name: 'Remove from selection' })).toBeVisible();
  await expect.poll(() => ringed(page, node.id), { message: 'a ring in ink around the selected node' }).toBeGreaterThanOrEqual(3);
  // and out again
  await panel.getByRole('button', { name: 'Remove from selection' }).click();
  await selected(page, []);
  await expect.poll(() => ringed(page, node.id)).toBeLessThanOrEqual(1);
  expect(await camera(page), 'selecting moves no camera').toEqual(cam);
  expect(await positions(page)).toEqual(ASIS);
});

// ---- the lasso: a shortcut --------------------------------------------------------------------------------------

type Corner = [number, number];
/** Is (x, y) inside the closed polygon `path`? This file's own even-odd ray cast, the oracle the island's lasso (the
 *  canvas's isPointInPath) is held to; for the simple paths below the winding rule makes no difference. */
function enclosed(x: number, y: number, path: Corner[]): boolean {
  let odd = false;
  for (let i = 0, j = path.length - 1; i < path.length; j = i++) {
    const [ax, ay] = path[i], [bx, by] = path[j];
    if (ay > y !== by > y && x < ax + ((bx - ax) * (y - ay)) / (by - ay)) odd = !odd;
  }
  return odd;
}
/** How far (x, y) is from the segment a-b. */
function away(x: number, y: number, [ax, ay]: Corner, [bx, by]: Corner): number {
  const l = (bx - ax) ** 2 + (by - ay) ** 2;
  const t = l === 0 ? 0 : Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / l));
  return Math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay)));
}
/** A polygon whose corners are given in the map's viewport pixels, as whole page pixels the mouse can trace, moved by a
 *  pixel at a time until no node's centre is within 2px of an edge, so that no rounding of the pointer's position can
 *  put a node on the other side of it; and the nodes whose centre it encloses, in atlas.json's order. */
async function lassoPath(page: Page, corners: Corner[]) {
  const box = (await page.locator('[data-atlas-canvas]').boundingBox())!;
  const v = await viewports(page);
  const centres = NODES.map((n) => [box.x + v[n.id].x, box.y + v[n.id].y] as Corner);
  for (let shift = 0; shift < 40; shift++) {
    const path = corners.map(([x, y]) => [Math.round(box.x + x) + shift, Math.round(box.y + y) + shift] as Corner);
    const near = centres.some(([x, y]) => path.some((a, i) => away(x, y, a, path[(i + 1) % path.length]) <= 2));
    if (!near) return { path, within: NODES.filter((_, i) => enclosed(centres[i][0], centres[i][1], path)) };
  }
  throw new Error('no placement of the path keeps 2px clear of every node');
}
/** Trace `path` with the mouse, button down, back to where it began. */
async function trace(page: Page, path: Corner[]) {
  await page.mouse.move(...path[0]);
  await page.mouse.down();
  for (const [x, y] of [...path.slice(1), path[0]]) await page.mouse.move(x, y, { steps: 8 });
  await page.mouse.up();
}

test('the lasso is a shortcut: off until pressed, then a drag selects the nodes inside its path -- the filter\'s only -- and pans nothing', async ({ page }) => {
  await drawn(page);
  const lasso = page.getByRole('button', { name: 'Lasso' });
  const overlay = page.locator('.stage canvas.lasso');
  await expect(lasso).toHaveAttribute('aria-pressed', 'false');
  await expect(overlay).toHaveCount(0);
  await lasso.click();
  await expect(lasso).toHaveAttribute('aria-pressed', 'true');
  await expect(overlay).toHaveCount(1);
  await expect(overlay).toHaveAttribute('aria-hidden', 'true');

  // a triangle over the largest family, its right angle at the top left of the family's nodes: what it encloses is
  // selected, whichever family it is in, and what is in the family's box but beyond the hypotenuse is not -- a polygon
  // test, not a box
  const v = await viewports(page);
  const fam = MEMBERS.get(LARGEST)!;
  const xs = fam.map((n) => v[n.id].x), ys = fam.map((n) => v[n.id].y);
  const [x0, y0, x1, y1] = [Math.min(...xs) - 3, Math.min(...ys) - 3, Math.max(...xs) + 3, Math.max(...ys) + 3];
  const tri = await lassoPath(page, [[x0, y0], [x1, y0], [x0, y1]]);
  const boxed = await lassoPath(page, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]);
  expect(tri.within.length, 'the triangle holds some nodes').toBeGreaterThan(0);
  expect(boxed.within.length, 'and its box holds more').toBeGreaterThan(tri.within.length);
  await trace(page, tri.path);
  await selected(page, ids(tri.within));
  expect(await camera(page), 'the drag drew a path; it did not pan the camera').toEqual(HOME);
  expect(await positions(page)).toEqual(ASIS);
  await expect(page.locator('[data-filter-status]')).toHaveText(`${tri.within.length} ${tri.within.length === 1 ? 'benchmark' : 'benchmarks'} selected`);
  // a click is not a path: it encloses nothing, and the selection stays
  await page.mouse.click(...tri.path[0]);
  await selected(page, ids(tri.within));

  // under a filter the lasso takes what the filter leaves in ink and no dimmed node, however much of the map it covers:
  // a subdomain, fitted, with its sibling subdomains dimmed around it
  await page.getByRole('button', { name: 'Clear selection' }).click();
  await selected(page, []);
  await page.locator('select[data-control="d"]').selectOption(SUB!);
  await expect.poll(async () => {
    const c = await camera(page);
    return !c.animated && c.ratio < 1;
  }).toBe(true);
  const box = (await page.locator('[data-atlas-canvas]').boundingBox())!;
  const whole = await lassoPath(page, [[6, 6], [box.width - 6, 6], [box.width - 6, box.height - 6], [6, box.height - 6]]);
  expect(whole.within.some((n) => n.domain_primary !== SUB), 'the path covers dimmed nodes too').toBe(true);
  expect(whole.within.some((n) => n.domain_primary === SUB), 'and some in ink').toBe(true);
  await trace(page, whole.path);
  await selected(page, ids(whole.within.filter((n) => n.domain_primary === SUB)));

  // Escape turns it off, and a drag pans the map again
  await page.keyboard.press('Escape');
  await expect(lasso).toHaveAttribute('aria-pressed', 'false');
  await expect(overlay).toHaveCount(0);
  const before = await camera(page);
  const [sx, sy] = whole.path[0];
  await trace(page, [[sx + 40, sy + 40], [sx + 140, sy + 40], [sx + 140, sy + 90]]);
  await expect.poll(async () => {
    const c = await camera(page);
    return c.x !== before.x || c.y !== before.y;
  }, { message: 'with the lasso off, a drag pans' }).toBe(true);
  expect(await positions(page)).toEqual(ASIS);
});
