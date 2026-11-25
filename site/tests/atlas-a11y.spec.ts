// site/tests/atlas-a11y.spec.ts -- P2-S5-T03 (10 V1 "Without JavaScript", "And it is also the legend"; 09 S4.2, S8.2,
// S8.6). The Atlas's family index -- legend, no-JS fallback, screen-reader linearisation and roving-tabindex target, one
// list -- in a browser, over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/atlas-a11y.spec.ts
//
// Done when: "Keyboard-only traversal reaches every family and opens an entry, and a JS-disabled run finds the complete
// grouped list." The JS-disabled runs are contexts opened with javaScriptEnabled: false inside the `js` project, as
// tests/atlas.spec.ts reads the page as sent, so playwright.config.ts is unchanged. Every expectation is computed here
// from the atlas.json the server was built from (build/preview/, scripts/preview_corpus.py): its group and family
// regions in their order, each family's nodes by name -- not from the page's own logic (lib/atlas.ts familyIndex,
// unit-tested in test/atlas.test.mjs). The numbers are the data's: the preview's atlas.json has six groups and nineteen
// families, the counts 09 S4.2 names, and the expectations read them from the file rather than assume them.
//
// The failure cases are checked as failures:
//   - a list duplicated on hydration. A page that kept the server's list and added a second, rendered by the island,
//     would still "find the complete grouped list", twice, so the hydrated page is held to one list, one heading id, one
//     row per family and one link per benchmark, and the live list to the very element the server sent (the island
//     takes it over in place rather than rendering it again: islands/Atlas.tsx), with the server's groups, rows, counts
//     and links in the same order; a reader focused on a benchmark when the list goes live is still on it after.
//   - a family the keyboard cannot reach, or a cluster the arrows leak out of: every family is reached by Tab alone, one
//     stop each, in order, every benchmark in it by the arrows, and an arrow at a cluster's end stays there.
//   - a list that is not complete, or that keys family to a colour: with JavaScript off every group, family, count and
//     benchmark is there, readable by role (the canvas is aria-hidden, the list is not), and no element in it has a
//     background or an ink of its own family's.
//   - a map that cannot be drawn: the server's list stays, whole, as the fallback, its toggles disabled.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Browser, type Page } from '@playwright/test';

interface Node { id: string; x: number; y: number; cluster: string; label: string }
interface Region { id: string; level: 'group' | 'family'; parent: string | null; label: string }
interface Display { ring: string; label: string | null; highlighted: boolean }
interface Camera { x: number; y: number; ratio: number; angle: number; animated: boolean }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const atlas = preview('atlas.json') as { nodes: Node[]; regions: Region[] };
const manifest = preview('build-manifest.json') as { paths: Record<string, string> };
const tokens = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/tokens.json', import.meta.url)), 'utf8'));
const ATLAS_URL = manifest.paths['atlas.json'];
const NODES = atlas.nodes;
const GROUPS = atlas.regions.filter((r) => r.level === 'group');
const FAMILIES = atlas.regions.filter((r) => r.level === 'family');
const fold = (s: string) => s.toLowerCase();
const byName = (a: Node, b: Node) => (fold(a.label) !== fold(b.label) ? (fold(a.label) < fold(b.label) ? -1 : 1) : a.id < b.id ? -1 : 1);
/** Each family's benchmarks as the index lists them: by name, case folded, then id. */
const ENTRIES = new Map(FAMILIES.map((f) => [f.id, NODES.filter((n) => n.cluster === f.id).sort(byName)]));
const INK = tokens.themes.light['c-ink'].hex as string;
const MUTED = tokens.themes.light['c-ink-muted'].hex as string;
const FAINT = tokens.themes.light['c-ink-faint'].hex as string;

interface Row { id: string; label: string; count: string; toggle: string; entries: [string, string, string][] }
interface Group { id: string; heading: string; families: Row[] }

/** The grouped list atlas.json says the index is. */
const EXPECTED: Group[] = GROUPS.map((g) => ({
  id: g.id,
  heading: g.label,
  families: FAMILIES.filter((f) => f.parent === g.id).map((f) => {
    const n = ENTRIES.get(f.id)!.length;
    return {
      id: f.id, label: f.label, count: `${n} ${n === 1 ? 'benchmark' : 'benchmarks'}`, toggle: `Highlight ${f.label} on the map`,
      entries: ENTRIES.get(f.id)!.map((e) => [e.id, `/benchmarks/${e.id}/`, e.label] as [string, string, string]),
    };
  }),
}));

/** The grouped list a page holds, read from its DOM by structure: groups, then rows, then links. */
const readIndex = (page: Page, which: 'server' | 'island') => page.locator(`[data-atlas-index="${which}"]`).evaluate((root) => {
  const text = (el: Element | null) => el?.textContent ?? null;
  return [...root.querySelectorAll(':scope > ul.index-groups > li.index-group')].map((g) => ({
    id: g.getAttribute('data-index-group'),
    heading: text(g.querySelector(':scope > h3')),
    families: [...g.querySelectorAll(':scope > ul.index-families > li.index-family')].map((f) => ({
      id: f.getAttribute('data-index-family'),
      label: text(f.querySelector(':scope > .family-row > h4')),
      count: text(f.querySelector(':scope > .family-row > .family-count')),
      toggle: text(f.querySelector(':scope > .family-row > button.highlight')),
      entries: [...f.querySelectorAll(':scope > ul.index-entries > li > a')].map((a) => [a.getAttribute('data-index-entry'), a.getAttribute('href'), a.textContent]),
    })),
  }));
});

const PROBE = '[data-atlas-view]';
// the island's probe is { renderer, graph } (islands/Atlas.tsx); these readers copy and never write, as tests/atlas.spec.ts's
const camera = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const c = (el as any).atlasProbe.renderer.getCamera();
  return { ...c.getState(), animated: c.isAnimated() } as Camera;
});
const positions = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const { graph } = (el as any).atlasProbe;
  return Object.fromEntries(graph.mapNodes((id: string, a: { x: number; y: number }) => [id, [a.x, a.y]])) as Record<string, [number, number]>;
});
const displays = (page: Page) => page.locator(PROBE).evaluate((el) => {
  const { renderer, graph } = (el as any).atlasProbe;
  return Object.fromEntries(graph.nodes().map((id: string) => {
    const d = renderer.getNodeDisplayData(id);
    return [id, { ring: d.ring, label: d.label, highlighted: d.highlighted }];
  })) as Record<string, Display>;
});
const ASIS = Object.fromEntries(NODES.map((n) => [n.id, [n.x, n.y]]));
const HOME: Camera = { x: 0.5, y: 0.5, ratio: 1, angle: 0, animated: false };

/** What has focus: the index item's kind and id, and which list it is in. */
const focused = (page: Page) => page.evaluate(() => {
  const a = document.activeElement as HTMLElement | null;
  return {
    entry: a?.getAttribute('data-index-entry') ?? null,
    toggle: a?.getAttribute('data-highlight') ?? null,
    list: a?.closest('[data-atlas-index]')?.getAttribute('data-atlas-index') ?? null,
    tag: a?.tagName.toLowerCase() ?? null,
    control: a?.getAttribute('data-control') ?? null,
    id: a?.id ?? '',
  };
});

/** /atlas/ with the map drawn and the island's list in place of the server's. */
async function hydrated(page: Page) {
  await page.goto('/atlas/');
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'drawn');
  await expect(page.locator('[data-atlas-index="island"]')).toHaveCount(1);
}

/** Tab from the top of the page until focus enters the index; the stops on the way are the page's other controls. */
async function tabIntoIndex(page: Page) {
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press('Tab');
    if ((await focused(page)).list != null) return;
  }
  throw new Error('forty Tabs from the top of the page never reached the family index');
}

async function noScript(browser: Browser) {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  const res = await page.goto('/atlas/');
  expect(res!.status()).toBe(200);
  return { context, page };
}

// ---- what the preview is ------------------------------------------------------------------------------------

test('the preview is what these expectations read: every node in a family region, every family in a group', () => {
  expect(NODES.length).toBeGreaterThan(0);
  expect(ATLAS_URL).toMatch(/^\/data\/atlas\.[0-9a-f]{8}\.json$/);
  const groups = new Set(GROUPS.map((g) => g.id));
  for (const f of FAMILIES) expect(groups.has(f.parent!), `${f.id} sits in a group atlas.json lists`).toBe(true);
  expect([...ENTRIES.values()].reduce((s, e) => s + e.length, 0), 'every node in exactly one family').toBe(NODES.length);
  // the data's numbers, which the index renders; in this preview they are the six and nineteen 09 S4.2 names
  expect(GROUPS.length).toBeGreaterThan(0);
  expect(FAMILIES.length).toBe(new Set(NODES.map((n) => n.cluster)).size);
});

// ---- with JavaScript off: the complete grouped list --------------------------------------------------------------

test('with JavaScript off the canvas container holds the complete grouped list: every group, family, count and benchmark', async ({ browser }) => {
  const { context, page } = await noScript(browser);
  const index = page.locator('[data-atlas-index="server"]');
  await expect(index).toHaveCount(1);
  // inside the canvas container, beside the canvas, and not under its aria-hidden
  await expect(page.locator('.frame [data-atlas-index="server"]')).toHaveCount(1);
  await expect(page.locator('.frame [data-atlas-canvas]')).toHaveAttribute('aria-hidden', 'true');
  expect(await index.evaluate((el) => el.closest('[aria-hidden="true"]'))).toBeNull();
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'loading');
  await expect(page.locator('[data-atlas-note="loading"] a[href="/benchmarks/"]')).toBeVisible();
  await expect(index.locator('.index-keys')).toContainText('Every benchmark the map places, under its family.');

  // the whole list, in atlas.json's order: group headings, family rows with their counts, every benchmark linked
  expect(await readIndex(page, 'server')).toEqual(EXPECTED);
  // and readable as such: the accessibility tree has the headings and the links, a group heading never a count
  await expect(index.getByRole('heading', { level: 3 })).toHaveText(GROUPS.map((g) => g.label));
  await expect(index.getByRole('heading', { level: 4 })).toHaveText(FAMILIES.map((f) => f.label));
  await expect(index.getByRole('link')).toHaveCount(NODES.length);
  for (const h of await index.locator('h3').allTextContents()) expect(h, 'a group heading carries no count').not.toMatch(/\d/);
  const first = ENTRIES.get(FAMILIES[0].id)![0];
  await expect(index.getByRole('link', { name: first.label, exact: true })).toHaveAttribute('href', `/benchmarks/${first.id}/`);
  // the toggles are there and disabled: there is no map for them to act on
  await expect(index.locator('button.highlight')).toHaveCount(FAMILIES.length);
  await expect(index.locator('button.highlight:not([disabled])')).toHaveCount(0);
  await expect(index.locator('button.highlight[aria-pressed="false"]')).toHaveCount(FAMILIES.length);

  // no colour swatch and no family ink: no picture in the list, no background but the page's, one ink per kind of text
  await expect(index.locator('svg, canvas, img, [style]')).toHaveCount(0);
  const colours = await index.evaluate((el) => {
    const all = [el, ...el.querySelectorAll('*')];
    const set = (sel: string, prop: 'color' | 'borderColor') => [...new Set([...el.querySelectorAll(sel)].map((e) => getComputedStyle(e)[prop]))];
    return {
      page: getComputedStyle(document.body).backgroundColor,
      backgrounds: [...new Set(all.map((e) => getComputedStyle(e).backgroundColor))],
      groups: set('h3', 'color'), families: set('h4', 'color'), counts: set('.family-count', 'color'), toggles: set('button.highlight', 'borderColor'),
    };
  });
  for (const b of colours.backgrounds) expect(['rgba(0, 0, 0, 0)', colours.page], 'a background in the index').toContain(b);
  for (const k of ['groups', 'families', 'counts', 'toggles'] as const) expect(colours[k], `${k}: one ink for every family`).toHaveLength(1);
  await context.close();
});

test('with JavaScript off the keyboard reaches every benchmark in the list, in order, and opens one', async ({ browser }) => {
  const { context, page } = await noScript(browser);
  const order = await page.locator('[data-atlas-index="server"] a').evaluateAll((as) => as.map((a) => a.getAttribute('data-index-entry')));
  expect(order).toEqual(EXPECTED.flatMap((g) => g.families.flatMap((f) => f.entries.map((e) => e[0]))));
  // the browser's own Tab order: into the list, along its links, and Enter follows one
  await tabIntoIndex(page);
  expect((await focused(page)).entry).toBe(order[0]);
  await page.keyboard.press('Tab');
  expect((await focused(page)).entry).toBe(order[1]);
  await Promise.all([page.waitForURL(`/benchmarks/${order[1]}/`), page.keyboard.press('Enter')]);
  await context.close();
});

// ---- hydrated: one list, the island's --------------------------------------------------------------------------

test('the failure case: on hydration the server\'s list goes live in place, and the page never holds two', async ({ browser, page }) => {
  const { context, page: sent } = await noScript(browser);
  const server = await readIndex(sent, 'server');
  await context.close();

  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  // the list element as parsed from the HTML, before any script of the page runs
  await page.addInitScript(() => document.addEventListener('DOMContentLoaded', () => {
    (window as unknown as { sent: Element | null }).sent = document.querySelector('[data-atlas-index]');
  }));
  await hydrated(page);
  expect(errors, 'the island hydrates without an error').toEqual([]);
  await expect(page.locator('[data-atlas-index]')).toHaveCount(1);
  await expect(page.locator('[data-atlas-index="server"]')).toHaveCount(0);
  expect(await page.evaluate(() => {
    const was = (window as unknown as { sent: Element | null }).sent;
    return was != null && was.isConnected && was === document.querySelector('[data-atlas-index]');
  }), 'the live list is the element the server sent, not a second rendering of it').toBe(true);
  await expect(page.locator('#atlas-index-h')).toHaveCount(1);
  await expect(page.locator('[data-index-family]')).toHaveCount(FAMILIES.length);
  await expect(page.locator('[data-index-entry]')).toHaveCount(NODES.length);
  const ids = await page.locator('[id]').evaluateAll((els) => els.map((e) => e.id));
  expect(ids.length, 'no id twice on the page').toBe(new Set(ids).size);
  // the island's list is the server's: the same groups, rows, counts, toggles and links, in the same order
  expect(await readIndex(page, 'island')).toEqual(server);
  expect(server).toEqual(EXPECTED);
  // with its toggles live now that there is a map, and still beside the map, inside the canvas container
  await expect(page.locator('[data-atlas-index="island"] button.highlight:not([disabled])')).toHaveCount(FAMILIES.length);
  await expect(page.locator('.frame [data-atlas-index="island"]')).toHaveCount(1);
  const list = (await page.locator('[data-atlas-index="island"]').boundingBox())!;
  const stage = (await page.locator('.stage').boundingBox())!;
  expect(list.x + list.width, 'the index is a column beside the stage at 1280px').toBeLessThanOrEqual(stage.x + 1);
  // the canvas is still a picture of the list, and every canvas is inside it
  await expect(page.locator('[data-atlas-canvas]')).toHaveAttribute('aria-hidden', 'true');
  expect(await page.locator('canvas').evaluateAll((cs) => cs.every((c) => c.closest('[data-atlas-canvas][aria-hidden="true"]') != null))).toBe(true);
});

test('a reader focused on a benchmark when the list goes live is still on it, and Tab goes on to the next family', async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((r) => { release = r; });
  await page.route(`**${ATLAS_URL}`, async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto('/atlas/');
  const target = ENTRIES.get(FAMILIES[2].id)![1];
  await page.locator(`[data-atlas-index="server"] [data-index-entry="${target.id}"]`).focus();
  expect(await focused(page)).toMatchObject({ entry: target.id, list: 'server' });
  release();
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'drawn');
  await expect(page.locator('[data-atlas-index="island"]')).toHaveCount(1);
  expect(await focused(page), 'the same element, now live').toMatchObject({ entry: target.id, list: 'island' });
  // the list now roves: from there one Tab is the next family's one stop, its toggle
  await page.keyboard.press('Tab');
  expect(await focused(page)).toMatchObject({ toggle: FAMILIES[3].id, list: 'island' });
});

test('when the map cannot be drawn the server\'s list stays, whole, as the fallback', async ({ page }) => {
  await page.route(`**${ATLAS_URL}`, (route) => route.fulfill({ status: 404, body: 'not found' }));
  await page.goto('/atlas/');
  await expect(page.locator(PROBE)).toHaveAttribute('data-state', 'failed');
  await expect(page.locator('[data-atlas-index]')).toHaveCount(1);
  expect(await readIndex(page, 'server')).toEqual(EXPECTED);
  await expect(page.locator('[data-atlas-index="server"] button.highlight:not([disabled])')).toHaveCount(0);
});

// ---- the keyboard: Tab between clusters, arrows within -------------------------------------------------------------

test('keyboard only: Tab reaches every family in order, one stop each, and the arrows every benchmark in it', async ({ page }) => {
  test.setTimeout(180_000);
  await hydrated(page);
  await tabIntoIndex(page);
  for (const [i, f] of FAMILIES.entries()) {
    expect(await focused(page), `Tab stop ${i + 1} is ${f.id}'s row`).toMatchObject({ toggle: f.id, list: 'island' });
    const seen: string[] = [];
    for (const _ of ENTRIES.get(f.id)!) {
      await page.keyboard.press('ArrowDown');
      seen.push((await focused(page)).entry!);
    }
    expect(seen, `the arrows walk ${f.id}'s benchmarks in order`).toEqual(ENTRIES.get(f.id)!.map((e) => e.id));
    await page.keyboard.press('ArrowDown');
    expect((await focused(page)).entry, `an arrow at ${f.id}'s end stays in it`).toBe(seen.at(-1));
    if (i === 0) {
      // and back up the first family to its start, where Up stays too, then down to its end again
      for (const _ of seen) await page.keyboard.press('ArrowUp');
      expect((await focused(page)).toggle).toBe(f.id);
      await page.keyboard.press('ArrowUp');
      expect((await focused(page)).toggle, 'an arrow at its start stays in it').toBe(f.id);
      for (const _ of seen) await page.keyboard.press('ArrowDown');
      expect((await focused(page)).entry).toBe(seen.at(-1));
    }
    await page.keyboard.press('Tab');
  }
  // past the last family, Tab leaves the list; Shift+Tab comes back to where the reader left that family
  expect((await focused(page)).list).toBeNull();
  await page.keyboard.press('Shift+Tab');
  const last = FAMILIES.at(-1)!;
  expect(await focused(page)).toMatchObject({ entry: ENTRIES.get(last.id)!.at(-1)!.id, list: 'island' });
  // one Tab stop per family, nothing else in the list
  await expect(page.locator('[data-atlas-index="island"] [tabindex="0"]')).toHaveCount(FAMILIES.length);
});

test('Enter opens an entry; Space selects it, showing its summary beside the map, and Escape lets it go', async ({ page }) => {
  await hydrated(page);
  await tabIntoIndex(page);
  const f = FAMILIES[0];
  const [a, b] = ENTRIES.get(f.id)!;
  await page.keyboard.press('ArrowDown');
  expect((await focused(page)).entry).toBe(a.id);
  const scroll = () => page.evaluate(() => [window.scrollY, document.querySelector('[data-atlas-index]')!.scrollTop]);
  const before = await scroll();
  await page.keyboard.press('Space');
  const panel = page.locator(`[data-atlas-panel="${a.id}"]`);
  await expect(panel).toBeVisible();
  await expect(panel.locator('h2')).toHaveText(a.label);
  expect((await displays(page))[a.id], 'its node is drawn on top').toMatchObject({ label: a.label, highlighted: true });
  expect(await scroll(), 'Space selects; it does not scroll').toEqual(before);
  expect((await focused(page)).entry, 'focus stays in the list').toBe(a.id);
  // Space on the next benchmark selects that one instead
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Space');
  await expect(page.locator(`[data-atlas-panel="${b.id}"]`)).toBeVisible();
  await expect(panel).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(page.locator(`[data-atlas-panel="${b.id}"]`)).toHaveCount(0);
  expect((await focused(page)).entry, 'and focus is still where it was').toBe(b.id);
  // a selection never moves the camera or a node
  expect(await camera(page)).toEqual(HOME);
  expect(await positions(page)).toEqual(ASIS);
  // Enter opens the benchmark's page
  const res = page.waitForResponse((r) => r.url().endsWith(`/benchmarks/${b.id}/`));
  await page.keyboard.press('Enter');
  await page.waitForURL(`/benchmarks/${b.id}/`);
  expect((await res).status()).toBe(200);
});

test('a row\'s toggle emphasises its family on the map and dims the rest, one family at a time, moving no node', async ({ page }) => {
  await hydrated(page);
  await tabIntoIndex(page);
  const [f, g] = FAMILIES;
  const toggle = (id: string) => page.locator(`[data-atlas-index="island"] [data-highlight="${id}"]`);
  const count = (id: string) => String(ENTRIES.get(id)!.length);
  await page.keyboard.press('Space');
  await expect(toggle(f.id)).toHaveAttribute('aria-pressed', 'true');
  // the toggle is the family's domain filter: the link, the filter bar and the legend say the same thing
  await expect(page).toHaveURL(`/atlas/?d=${f.id}&v=1`);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', count(f.id));
  await expect(page.locator('select[data-control="d"]')).toHaveValue(f.id);
  for (const n of NODES) {
    const d = (await displays(page))[n.id];
    if (n.cluster === f.id) expect([d.ring, d.label], n.id).toEqual([INK, n.label]);
    else expect([d.ring, d.label], n.id).toEqual([FAINT, null]);
  }
  expect(await positions(page), 'the camera may fit the family; no node moves').toEqual(ASIS);
  expect((await focused(page)).toggle, 'focus stays on the toggle').toBe(f.id);
  // the next family's toggle takes the emphasis from the first: one at a time
  await page.keyboard.press('Tab');
  expect((await focused(page)).toggle).toBe(g.id);
  await page.keyboard.press('Space');
  await expect(toggle(g.id)).toHaveAttribute('aria-pressed', 'true');
  await expect(toggle(f.id)).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('[data-atlas-index="island"] [aria-pressed="true"]')).toHaveCount(1);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', count(g.id));
  expect((await displays(page))[ENTRIES.get(f.id)![0].id].ring).toBe(FAINT);
  // and pressed again, it lets go: the whole map in its neutral ink, the link clean
  await page.keyboard.press('Space');
  await expect(page).toHaveURL('/atlas/');
  await expect(page.locator('[data-atlas-index="island"] [aria-pressed="true"]')).toHaveCount(0);
  await expect(page.locator(PROBE)).toHaveAttribute('data-matching', 'all');
  for (const [id, d] of Object.entries(await displays(page))) expect(d.ring, id).toBe(MUTED);
  expect(await positions(page)).toEqual(ASIS);
  // the filter bar's Domain control presses the same toggle
  await page.locator('select[data-control="d"]').selectOption(g.id);
  await expect(toggle(g.id)).toHaveAttribute('aria-pressed', 'true');
});

test('/ focuses search: on /atlas/, which has no search box, the filter; and it is a key of the list, not of a text field', async ({ page }) => {
  await hydrated(page);
  await tabIntoIndex(page);
  await page.keyboard.press('ArrowDown');
  // /atlas/ has no search box (the search UI is /search/'s), so "/" goes to the one control that finds things on the map
  await page.keyboard.press('/');
  expect(await focused(page)).toMatchObject({ tag: 'select', control: 'd' });
  // from a toggle too
  await page.locator(`[data-atlas-index="island"] [data-highlight="${FAMILIES[1].id}"]`).focus();
  await page.keyboard.press('/');
  expect(await focused(page)).toMatchObject({ tag: 'select', control: 'd' });
  // outside the list "/" is the page's: typed into a text field it is a character, and focus stays there
  await page.evaluate(() => {
    const input = document.createElement('input');
    input.type = 'search';
    input.id = 'probe-text';
    input.setAttribute('aria-label', 'a text field outside the list');
    document.querySelector('main')!.prepend(input);
  });
  await page.locator('#probe-text').focus();
  await page.keyboard.type('a/b');
  await expect(page.locator('#probe-text')).toHaveValue('a/b');
  expect((await focused(page)).id).toBe('probe-text');
});
