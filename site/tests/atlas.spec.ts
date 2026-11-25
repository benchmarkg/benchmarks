// site/tests/atlas.spec.ts -- P2-S5-T02 (10 V1; 08 S4.3, S5.2; 09 S4.2, S4.3, S7.6). The Atlas at /atlas/, in a browser,
// over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/atlas.spec.ts
//
// Done when: "Node coordinates are asserted identical before and after a filter, and the route's colour use matches 09
// S4.3's three-of-ten rule." What the canvas draws is read through the island's probe (islands/Atlas.tsx `atlasProbe`):
// graphology's x and y for each node, sigma's own frame coordinates for it, its viewport position, the display data the
// nodeReducer produced, the labels sigma drew and the camera. Every expectation is computed here from the files the
// server serves -- atlas.json, facets.json, corpus.json and enums.json from build/preview/ (scripts/preview_corpus.py),
// and tokens.json for the colours -- not from the island's own logic (src/lib/atlas.ts, unit-tested in
// test/atlas.test.mjs).
//
// The failure cases the verification names are checked as failures:
//   - a node that moves on a filter. sigma 3.0.3 re-reads x and y from the graph each time it processes it, so a node
//     moves only if the graph's coordinates change or sigma's frame (its normalisation) does: re-framing on what is
//     visible is the classic way to "fit" by moving the nodes instead of the camera. Each node is held to atlas.json's x
//     and y (graphology) and to the frame coordinates the unfiltered map draws (sigma), after a filter applied
//     interactively, on load and on Back, including the two that would move every node if the map were framed on what
//     is visible -- one benchmark at the map's edge, and nothing at all -- while the camera is shown to have moved, so
//     the test cannot pass by the filter doing nothing.
//   - a colour spent outside the three. The preview's drafts carry no contaminated, retracted or saturated benchmark, so
//     the colour test serves an atlas.json whose nodes cycle through all ten lifecycle terms (page.route, as browse.spec.ts
//     serves its empty facets.json): contaminated and retracted are --c-alert, saturated the headroom ramp's top stop,
//     and the other seven -- under-revision, the warning state 10 V1 keeps neutral, among them -- are the one neutral ink.
//
// No entry is published yet, so the preview's 320 drafts stand in for the published corpus, as on every page test.
// The states with no map to draw -- no published entry, an atlas.json or facets.json the view cannot read -- are the
// same page with the file answered by page.route.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Node { id: string; x: number; y: number; r: number; cluster: string; domain_primary: string; lifecycle: string | null; headroom_consumed: number | null; adoption_n: number; label: string }
interface AtlasDoc { artifact: string; format: number; layout_method: string; nodes: Node[]; edges: unknown[]; regions: { id: string; level: string }[] }
interface Row { id: string; domain: string; subdomain: string; facets: Record<string, string[]>; claim_count: number }
interface Display { ring: string; fill: string; empty: string; level: number; label: string | null; zIndex: number; highlighted: boolean }
interface Camera { x: number; y: number; ratio: number; angle: number; animated: boolean }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const atlas = preview('atlas.json') as AtlasDoc;
const facets = preview('facets.json') as { benchmarks: Row[] };
const corpus = preview('corpus.json') as { entities: { benchmark: { id: string; tagline: string }[] } };
const enums = preview('enums.json') as { vocabularies: Record<string, { terms: { id: string; field?: string }[] }> };
const manifest = preview('build-manifest.json') as { paths: Record<string, string> };
const tokens = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/tokens.json', import.meta.url)), 'utf8'));
const taxonomy = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/taxonomy.json', import.meta.url)), 'utf8')) as {
  facets: Record<string, Record<string, { label: string }>>;
};
const ATLAS_URL = manifest.paths['atlas.json'];
const FACETS_URL = manifest.paths['facets.json'];
const NODES = atlas.nodes;
const ROWS = facets.benchmarks;
const byId = new Map(NODES.map((n) => [n.id, n]));
const LIFECYCLE = enums.vocabularies.lifecycle.terms.filter((t) => t.field === 'lifecycle').map((t) => t.id);
const hex = (theme: 'light' | 'dark', token: string): string => tokens.themes[theme][token].hex;
const INK = { light: hex('light', 'c-ink'), dark: hex('dark', 'c-ink') };
const MUTED = { light: hex('light', 'c-ink-muted'), dark: hex('dark', 'c-ink-muted') };
const FAINT = hex('light', 'c-ink-faint');
const ALERT = { light: hex('light', 'c-alert'), dark: hex('dark', 'c-alert') };
const TOP = { light: hex('light', 'seq-head-6'), dark: hex('dark', 'seq-head-6') };

// the family with the most benchmarks, and the subdomains that hold exactly one (the map's outermost of them first)
const count = (k: (n: Node) => string) => NODES.reduce((m, n) => m.set(k(n), (m.get(k(n)) ?? 0) + 1), new Map<string, number>());
const FAM = [...count((n) => n.cluster)].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0][0];
const SUBS = count((n) => n.domain_primary);
const centre = { x: NODES.reduce((s, n) => s + n.x, 0) / NODES.length, y: NODES.reduce((s, n) => s + n.y, 0) / NODES.length };
const EDGE = NODES.filter((n) => SUBS.get(n.domain_primary) === 1)
  .sort((a, b) => Math.hypot(b.x - centre.x, b.y - centre.y) - Math.hypot(a.x - centre.x, a.y - centre.y))[0];
// a capability and an evaluation method each carried by some benchmark, never by the same one
const DISJOINT = (() => {
  const has = (r: Row, f: string, v: string) => r.facets[f].includes(v);
  const caps = [...new Set(ROWS.flatMap((r) => r.facets.capability))].sort();
  const ems = [...new Set(ROWS.flatMap((r) => r.facets.evaluation_method))].sort();
  for (const c of caps) for (const em of ems) if (!ROWS.some((r) => has(r, 'capability', c) && has(r, 'evaluation_method', em))) return { c, em };
  return null;
})();

// ---- reading the map --------------------------------------------------------------------------------------------

const PROBE = '[data-atlas-view]';
const positions = (page: Page) => page.locator(PROBE).evaluate((el) => (el as any).atlasProbe.positions() as Record<string, [number, number]>);
const framed = (page: Page) => page.locator(PROBE).evaluate((el) => (el as any).atlasProbe.framed() as Record<string, [number, number]>);
const camera = (page: Page) => page.locator(PROBE).evaluate((el) => (el as any).atlasProbe.camera() as Camera);
const labels = (page: Page) => page.locator(PROBE).evaluate((el) => (el as any).atlasProbe.labels() as string[]);
const dims = (page: Page) => page.locator(PROBE).evaluate((el) => (el as any).atlasProbe.dimensions() as { width: number; height: number });
const displays = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const p = (el as any).atlasProbe;
  return Object.fromEntries((p.ids() as string[]).map((id) => [id, p.display(id)])) as Record<string, Display>;
});
const viewports = (page: Page, ids: string[]) => page.locator(PROBE).evaluate((el, list) => {
  const p = (el as any).atlasProbe;
  return Object.fromEntries(list.map((id) => [id, p.viewport(id)])) as Record<string, { x: number; y: number; r: number }>;
}, ids);

async function drawn(page: Page, query = '') {
  await page.goto(`/atlas/${query}`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'drawn');
}
const HOME: Camera = { x: 0.5, y: 0.5, ratio: 1, angle: 0, animated: false };
/** The camera once it has done what `until` waits for and stopped: a fit runs in an effect after the render that
 *  changed the filter, so the camera is waited for, never read straight after the click. */
async function settled(page: Page, until: (c: Camera) => boolean) {
  await expect.poll(async () => {
    const c = await camera(page);
    return !c.animated && until(c);
  }, { message: 'the camera settles where it should' }).toBe(true);
  return camera(page);
}
/** Record, every frame from load, whether the camera is animating (window.animating), to tell a jump from a move. */
const sampleCamera = (page: Page) => page.addInitScript(() => {
  const w = window as unknown as { animating: boolean[] };
  w.animating = [];
  const tick = () => {
    const el = document.querySelector('[data-atlas-view]') as (Element & { atlasProbe?: { camera(): { animated: boolean } } }) | null;
    if (el?.atlasProbe) w.animating.push(el.atlasProbe.camera().animated);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
});
const animating = (page: Page) => page.evaluate(() => (window as unknown as { animating: boolean[] }).animating);
const ASIS = Object.fromEntries(NODES.map((n) => [n.id, [n.x, n.y]]));

/** Every node where atlas.json put it, in graphology and in sigma's frame `frame` (the unfiltered map's). */
async function unmoved(page: Page, frame: Record<string, [number, number]>, why: string) {
  expect(await positions(page), `${why}: graphology's x and y are atlas.json's`).toEqual(ASIS);
  expect(await framed(page), `${why}: sigma's frame coordinates are the unfiltered map's`).toEqual(frame);
}

let FRAME: Record<string, [number, number]>;
test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  await drawn(page);
  FRAME = await framed(page);
  await page.close();
});

// ---- what the preview is ------------------------------------------------------------------------------------

test('the preview is what these expectations read: atlas.json by its hashed URL, a node per facets.json row', () => {
  expect(atlas.artifact).toBe('atlas');
  expect(atlas.format).toBe(1);
  expect(atlas.layout_method).toBe('pack');
  expect(ATLAS_URL).toMatch(/^\/data\/atlas\.[0-9a-f]{8}\.json$/);
  expect(NODES.length).toBeGreaterThan(0);
  expect(NODES.map((n) => n.id).sort()).toEqual(ROWS.map((r) => r.id).sort());
  expect(LIFECYCLE).toHaveLength(10);
  expect(EDGE, 'a subdomain with one benchmark').toBeDefined();
  expect(DISJOINT, 'a capability and an evaluation method that never meet').not.toBeNull();
});

test('as sent, with JavaScript off: a crawled page that names its two data files by their hashed URLs and says where the benchmarks are', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  const res = await page.goto('/atlas/');
  expect(res!.status()).toBe(200);
  const html = await res!.text();
  expect([...new Set(html.match(/\/data\/[^"&\s<]*/g))].sort()).toEqual([ATLAS_URL, FACETS_URL].sort());
  await expect(page.locator('h1')).toHaveText('Atlas');
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'loading');
  await expect(page.locator('[data-atlas-note="loading"] a[href="/benchmarks/"]')).toBeVisible();
  await expect(page.locator('[data-atlas-canvas] canvas')).toHaveCount(0);
  // Pagefind: a narrative page (Base.astro `search`, crawl), the island itself out of the index
  expect(await page.locator('body').getAttribute('data-pagefind-ignore')).toBeNull();
  await expect(page.locator(`div[data-pagefind-ignore="all"] > astro-island ${PROBE}`)).toHaveCount(1);
  await context.close();
});

// ---- sigma draws atlas.json as written ------------------------------------------------------------------------

test('sigma draws every node at atlas.json\'s x and y, sized by its r, and no layout runs', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await drawn(page);
  expect(errors, 'the island hydrates and draws without an error').toEqual([]);
  expect(await positions(page)).toEqual(ASIS);
  expect(await camera(page)).toEqual(HOME);
  // a node's drawn radius is its r in the same units as its position: the distance, in pixels, from its centre to the
  // centre of another node, scaled by atlas.json's distance between them
  const [a, b] = [NODES[0], NODES.find((n) => n.r > 1) ?? NODES[1]];
  const vp = await viewports(page, [a.id, b.id]);
  const scale = Math.hypot(vp[a.id].x - vp[b.id].x, vp[a.id].y - vp[b.id].y) / Math.hypot(a.x - b.x, a.y - b.y);
  expect(vp[b.id].r / scale).toBeCloseTo(b.r, 3);
  await page.waitForTimeout(500);
  expect(await positions(page), 'nothing moves the nodes once drawn').toEqual(ASIS);
  expect(await framed(page)).toEqual(FRAME);
  // the canvases are a picture of the list (09 S8.2), and the regions and edges have their own layer beneath sigma's
  await expect(page.locator('[data-atlas-canvas]')).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('[data-atlas-canvas] canvas.sigma-regions')).toHaveCount(1);
  expect(await page.locator('[data-atlas-canvas] canvas').evaluateAll((cs) => cs.map((c) => c.className))).toContain('sigma-nodes');
});

// ---- a filter: paint and camera change, nodes do not --------------------------------------------------------

test('a filter dims non-matching nodes to --c-ink-faint and drops their labels, fits the camera to the rest, and moves no node', async ({ page }) => {
  await sampleCamera(page);
  await drawn(page);
  const want = ROWS.filter((r) => r.domain === FAM).map((r) => r.id).sort();
  const before = await viewports(page, want);
  await page.locator('select[data-control="d"]').selectOption(FAM);
  await expect(page).toHaveURL(`/atlas/?d=${FAM}&v=1`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', String(want.length));
  await settled(page, (c) => c.ratio < 1);
  await unmoved(page, FRAME, `d=${FAM}`);
  // the camera, not a node, moved -- it was seen animating, it is closer in, and every matching node is in the canvas
  expect(await animating(page)).toContain(true);
  const after = await viewports(page, want);
  expect(after).not.toEqual(before);
  const { width, height } = await dims(page);
  for (const id of want) {
    const v = after[id];
    expect(v.x - v.r, id).toBeGreaterThanOrEqual(0);
    expect(v.y - v.r, id).toBeGreaterThanOrEqual(0);
    expect(v.x + v.r, id).toBeLessThanOrEqual(width);
    expect(v.y + v.r, id).toBeLessThanOrEqual(height);
  }
  const shown = await displays(page);
  for (const n of NODES) {
    const d = shown[n.id];
    if (n.cluster === FAM) expect([d.ring, d.fill, d.label, d.zIndex], n.id).toEqual([INK.light, INK.light, n.label, 1]);
    else expect([d.ring, d.fill, d.label, d.zIndex], n.id).toEqual([FAINT, FAINT, null, 0]);
  }
  const drawnLabels = await labels(page);
  expect(drawnLabels.length, 'the fitted camera labels the matching nodes').toBeGreaterThan(0);
  for (const id of drawnLabels) expect(byId.get(id)!.cluster, `${id} is labelled`).toBe(FAM);
  await expect(page.locator('[data-count]')).toHaveText(`${want.length} of ${ROWS.length} benchmarks match`);

  // removing it: the whole map again, every node back to the neutral ink, and still none moved
  await page.locator(`[data-chip="d=${FAM}"]`).click();
  await expect(page).toHaveURL('/atlas/');
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', 'all');
  expect(await settled(page, (c) => c.ratio === 1)).toEqual(HOME);
  await unmoved(page, FRAME, 'cleared');
  for (const [id, d] of Object.entries(await displays(page))) expect([d.ring, d.label], id).toEqual([MUTED.light, byId.get(id)!.label]);
});

test('the failure case: one benchmark at the map\'s edge, and no benchmark at all, move no node either', async ({ page }) => {
  // one benchmark, from the link: the camera opens on it without animating (09 S7.6), and the frame is unchanged
  await sampleCamera(page);
  await drawn(page, `?d=${encodeURIComponent(EDGE.domain_primary)}&v=1`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', '1');
  await settled(page, (c) => c.ratio < 0.5);
  expect(await animating(page), 'nothing animates on load').not.toContain(true);
  await unmoved(page, FRAME, `d=${EDGE.domain_primary}`);
  const vp = (await viewports(page, [EDGE.id]))[EDGE.id];
  const { width, height } = await dims(page);
  expect(Math.abs(vp.x - width / 2)).toBeLessThan(2);
  expect(Math.abs(vp.y - height / 2)).toBeLessThan(2);
  expect((await displays(page))[EDGE.id].label).toBe(EDGE.label);

  // nothing: every node dimmed and unlabelled, the camera where it was, and the empty state says so
  await drawn(page, `?c=${DISJOINT!.c}&em=${DISJOINT!.em}&v=1`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', '0');
  await expect(page.locator('[data-empty="filter"]')).toContainText('No benchmark matches all 2 filters');
  expect(await camera(page)).toEqual(HOME);
  await unmoved(page, FRAME, 'no match');
  for (const [id, d] of Object.entries(await displays(page))) expect([d.ring, d.label], id).toEqual([FAINT, null]);
  expect(await labels(page)).toEqual([]);
  // and from there, interactively, to the edge benchmark's filter and back to nothing: the camera moves, no node does
  await page.locator(`[data-chip="em=${DISJOINT!.em}"]`).click();
  await expect(page.locator(PROBE)).not.toHaveAttribute('data-matching', '0');
  await settled(page, (c) => c.ratio < 1);
  await unmoved(page, FRAME, `c=${DISJOINT!.c}`);
});

// ---- colour: three of ten -------------------------------------------------------------------------------------

/** atlas.json with every lifecycle term, and none, on the nodes in turn, and headroom on the neutral ones. */
function allLifecycles() {
  const terms: (string | null)[] = [...LIFECYCLE, null];
  return {
    ...atlas,
    nodes: NODES.map((n, i) => ({ ...n, lifecycle: terms[i % terms.length], headroom_consumed: i % 3 === 0 ? null : (i % 5) / 4 })),
  };
}

for (const theme of ['light', 'dark'] as const) {
  test(`${theme}: colour on exactly contaminated, retracted and saturated; the other seven lifecycle terms and none are neutral`, async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: theme });
    const page = await context.newPage();
    const served = allLifecycles();
    await page.route(`**${ATLAS_URL}`, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(served) }));
    await drawn(page);
    const shown = await displays(page);
    const expected = (lc: string | null) => (lc === 'contaminated' || lc === 'retracted' ? ALERT[theme] : lc === 'saturated' ? TOP[theme] : MUTED[theme]);
    const seen = new Set<string | null>();
    for (const n of served.nodes) {
      const d = shown[n.id];
      seen.add(n.lifecycle);
      expect(d.ring, `${n.id} (${n.lifecycle})`).toBe(expected(n.lifecycle));
      expect(d.fill, `${n.id}: one ink for ring and fill`).toBe(d.ring);
      expect(d.empty, `${n.id}: above the fill, the page`).toBe(hex(theme, 'c-bg'));
      const full = expected(n.lifecycle) !== MUTED[theme];
      expect(d.level, `${n.id}: the fill level`).toBe(full ? 1 : n.headroom_consumed == null ? 0 : n.headroom_consumed);
    }
    expect([...seen].length, 'every term was on the map').toBe(11);
    // the route's colour use: the neutral ink, the alert and the ramp's top stop -- and no family colour, no fourth state
    expect([...new Set(Object.values(shown).map((d) => d.ring))].sort()).toEqual([ALERT[theme], MUTED[theme], TOP[theme]].sort());
    // under a filter, matching neutral nodes rise to --c-ink, coloured ones keep their colour, the rest go faint
    await page.locator('select[data-control="d"]').selectOption(FAM);
    await expect(page.locator(PROBE)).toHaveAttribute('data-matching', /^[1-9]/);
    const filtered = await displays(page);
    for (const n of served.nodes) {
      const want = n.cluster !== FAM ? hex(theme, 'c-ink-faint') : expected(n.lifecycle) === MUTED[theme] ? INK[theme] : expected(n.lifecycle);
      expect(filtered[n.id].ring, `${n.id} (${n.lifecycle}) under d=${FAM}`).toBe(want);
    }
    await context.close();
  });
}

test('a theme change re-paints the map in the other theme\'s tokens, and moves nothing', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await drawn(page);
  expect((await displays(page))[NODES[0].id].ring).toBe(MUTED.light);
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect.poll(async () => (await displays(page))[NODES[0].id].ring).toBe(MUTED.dark);
  await unmoved(page, FRAME, 'dark');
});

// ---- hover and click ------------------------------------------------------------------------------------------

/** Zoom to a subdomain with several benchmarks (a link's filter), and give the page coordinates of one of them. */
async function zoomed(page: Page) {
  const sub = [...SUBS].filter(([, n]) => n >= 3).sort((a, b) => (a[0] < b[0] ? -1 : 1))[0][0];
  await drawn(page, `?d=${encodeURIComponent(sub)}&v=1`);
  await settled(page, (c) => c.ratio < 1);
  const node = NODES.find((n) => n.domain_primary === sub)!;
  const box = (await page.locator('[data-atlas-canvas]').boundingBox())!;
  const v = (await viewports(page, [node.id]))[node.id];
  return { node, at: { x: box.x + v.x, y: box.y + v.y } };
}

test('hover shows the tagline card: name, tagline, primary domain, lifecycle, headroom and adoption', async ({ page }) => {
  const { node, at } = await zoomed(page);
  await page.mouse.move(at.x, at.y);
  const card = page.locator(`[data-atlas-card="${node.id}"]`);
  await expect(card).toBeVisible();
  await expect(card.locator('.name')).toHaveText(node.label);
  await expect(card.locator('.tagline')).toHaveText(corpus.entities.benchmark.find((b) => b.id === node.id)!.tagline);
  const dom = taxonomy.facets.domain;
  await expect(card).toContainText(`${dom[node.cluster].label} › ${dom[node.domain_primary].label}`);
  await expect(card.locator('[data-card-lifecycle]')).toHaveText(node.lifecycle == null ? /not recorded/ : taxonomy.facets.lifecycle[node.lifecycle].label);
  // no build stage computes headroom yet: the absent token, never a zero (09 S4.4, S11.2)
  await expect(card.locator('[data-card-headroom]')).toHaveText(node.headroom_consumed == null ? '∅ not recorded (headroom)' : /consumed|ceiling/);
  await expect(card.locator('[data-card-adoption]')).toHaveText(`${node.adoption_n} ${node.adoption_n === 1 ? 'system' : 'systems'} with claims`);
  await page.mouse.move(1, 1);
  await expect(card).toHaveCount(0);
});

test('a click opens the summary beside the map without losing map position', async ({ page }) => {
  const { node, at } = await zoomed(page);
  const ids = NODES.filter((n) => n.cluster === node.cluster).map((n) => n.id);
  const [cam, size, where] = [await camera(page), await dims(page), await viewports(page, ids)];
  await page.mouse.click(at.x, at.y);
  const panel = page.locator(`[data-atlas-panel="${node.id}"]`);
  await expect(panel).toBeVisible();
  await expect(panel.locator('h2')).toHaveText(node.label);
  const full = panel.locator('a', { hasText: 'Open the full page' });
  await expect(full).toHaveAttribute('href', `/benchmarks/${node.id}/`);
  expect((await page.request.get(`/benchmarks/${node.id}/`)).status()).toBe(200);
  await expect(panel).toContainText(`Claims${ROWS.find((r) => r.id === node.id)!.claim_count}`);
  // the map did not move, resize or re-frame; the chosen node is drawn on top
  expect(await camera(page)).toEqual(cam);
  expect(await dims(page)).toEqual(size);
  expect(await viewports(page, ids)).toEqual(where);
  expect((await displays(page))[node.id].highlighted).toBe(true);
  // the panel sits beside the map, not over it
  const frame = (await page.locator('.frame').boundingBox())!;
  const aside = (await page.locator('aside.panel').boundingBox())!;
  expect(aside.x >= frame.x + frame.width || aside.y >= frame.y + frame.height).toBe(true);
  await panel.locator('button.close').click();
  await expect(panel).toHaveCount(0);
  expect(await camera(page)).toEqual(cam);
  await page.mouse.click(at.x, at.y);
  await expect(panel).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await unmoved(page, FRAME, 'after a click');
});

// ---- the selection is the URL ----------------------------------------------------------------------------------

test('the selection is the URL: canonical on every change, read back on Back, and a value it cannot apply is said', async ({ page }) => {
  await drawn(page);
  await page.locator('select[data-control="d"]').selectOption(FAM);
  await expect(page).toHaveURL(`/atlas/?d=${FAM}&v=1`);
  const fam = await settled(page, (c) => c.ratio < 1);
  await page.locator('select[data-control="d"]').selectOption('');
  await expect(page).toHaveURL('/atlas/');
  await settled(page, (c) => c.ratio === 1);
  await page.goBack();
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', String(ROWS.filter((r) => r.domain === FAM).length));
  await expect(page.locator('select[data-control="d"]')).toHaveValue(FAM);
  expect(await settled(page, (c) => c.ratio < 1)).toEqual(fam);
  await unmoved(page, FRAME, 'Back');
  await drawn(page, '?c=nonexistent-term&v=1');
  await expect(page.locator('[data-ignored]')).toContainText('ignored filter: c=nonexistent-term');
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', 'all');
});

test('under prefers-reduced-motion the camera jumps: it is never caught animating', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await sampleCamera(page);
  await drawn(page);
  await page.locator('select[data-control="d"]').selectOption(FAM);
  await expect(page.locator(PROBE)).not.toHaveAttribute('data-matching', 'all');
  await settled(page, (c) => c.ratio < 1);
  await page.locator(`[data-chip="d=${FAM}"]`).click();
  await settled(page, (c) => c.ratio === 1);
  const seen = await animating(page);
  expect(seen.length, 'the camera was sampled every frame').toBeGreaterThan(10);
  expect(seen).not.toContain(true);
});

// ---- what the page says when there is nothing to draw ------------------------------------------------------------

test('an atlas.json the view cannot read is said, with the browse view as the way in', async ({ page }) => {
  await page.route(`**${ATLAS_URL}`, (route) => route.fulfill({ status: 404, body: 'not found' }));
  await page.goto('/atlas/');
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'failed');
  await expect(page.locator('[data-atlas-note="failed"]')).toContainText('HTTP 404');
  await expect(page.locator('[data-atlas-note="failed"] a[href="/benchmarks/"]')).toHaveCount(1);
});

test('without facets.json the map still draws, and says it cannot be filtered', async ({ page }) => {
  await page.route(`**${FACETS_URL}`, (route) => route.fulfill({ status: 404, body: 'not found' }));
  await drawn(page);
  await expect(page.locator('[data-filter-unavailable]')).toContainText('HTTP 404');
  await expect(page.locator('select[data-control="d"]')).toHaveCount(0);
  expect(await positions(page)).toEqual(ASIS);
});

test('with no published entry the map says so and draws nothing', async ({ page }) => {
  await page.route(`**${ATLAS_URL}`, (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ ...atlas, nodes: [], edges: [], regions: [] }),
  }));
  await page.goto('/atlas/');
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'empty');
  await expect(page.locator('[data-atlas-note="empty"]')).toContainText('No benchmark is published yet');
  await expect(page.locator('[data-atlas-canvas] canvas')).toHaveCount(0);
});
