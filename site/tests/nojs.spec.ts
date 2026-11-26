// site/tests/nojs.spec.ts -- P2-S8-T02 (10 "Performance budget", the second of its three CI gates; 08 S8.3; 09 S8.6).
// The no-JS render gate: every route family the site builds is mapped to its required fallback element, and one page of
// each, rendered with JavaScript disabled (the `nojs` project, playwright.config.ts), is asserted to carry it:
//
//   cd site && npx playwright test tests/nojs.spec.ts --project=nojs
//
// Done when: "Every route family has an asserted fallback element that renders with JavaScript off." The families are
// scripts/route_groups.json's (P2-S8-T01), the ones the size gate budgets, so the two gates share one subject list: every
// page of the build belongs to exactly one family or to an ignored test route, and a page no family claims throws
// (scripts/route_groups.mjs assignPages). scripts/route_fallback_map.json gives each family its element -- the table, the
// grouped list or the inline SVG that a reader without JavaScript gets -- by kind and CSS selector, with the page source
// it is read from. A family with no entry fails, an entry for a route that is no family fails, and a family whose pages
// exist while its entry still waits on the task that routes it fails, so a new route family cannot pass unchecked (10:
// the gate is indexed by route, and "a gate whose subject list is shorter than the thing it gates is not a gate").
//
// What "renders" means here, for the family's first page in route order:
//   - the page answers 200, and a redirect family's page goes on, by its meta refresh and no script, to the page it
//     names, which is then held to that page's own family element;
//   - the selector matches in the DOM a browser built from the HTML as sent, with scripting off;
//   - the first match is the kind it is mapped to, holding content: a <table> with a row that has a data cell, a <ul>,
//     <ol> or <dl> with an item that has text, an inline <svg> with something drawn in it;
//   - it is not inside a <noscript>: 09 S8.6, "`<noscript>` is not the strategy", and a browser with scripting off parses
//     a <noscript>'s markup as elements, so without this a fallback kept there would pass;
//   - it is visible, once any closed <details> around it is opened by its own summary, a native disclosure.
//
// A regression here is a citability regression (08 S8.3), so it fails the job: pr-validate.yml's size-budgets job runs
// this spec over the build it measures (UAIBI_SITE_BUILT=1, playwright.config.ts). The failure case is checked as a
// failure, as tests/detail-nojs.spec.ts and test/fixtures/size-detail-js.mjs check theirs: each family's page is served
// again doctored -- its fallback element taken out; then the whole page kept, but inside a <noscript> -- and the gate
// must report each; a redirect page is served without its meta refresh; and the map with a family's entry taken out,
// with an entry no family has, or with a built family still pending, must be reported too. Each check of a kind is also
// run on a small page served here (an empty table, an empty list, an SVG with nothing drawn, the wrong element), since no
// family is held to an SVG yet.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';
import { assignPages, builtRoutes, loadGroups } from '../../scripts/route_groups.mjs';

type Kind = 'table' | 'list' | 'svg';
interface Fallback {
  route: string;          // a family of scripts/route_groups.json, as written there
  element?: Kind;         // what the selector must find
  selector?: string;
  what?: string;          // the element, in words
  redirect?: string;      // a family whose pages are a meta refresh: the page they go on to
  pending?: string;       // the task that routes the family; until then it has no page and no element to name
  basis: string;
}
interface Family { route: string; pending?: string; pages: string[] }

const DIST = fileURLToPath(new URL('../dist', import.meta.url));
const MAP_FILE = fileURLToPath(new URL('../../scripts/route_fallback_map.json', import.meta.url));
const MAP = JSON.parse(readFileSync(MAP_FILE, 'utf8')) as { kinds: Record<Kind, string>; families: Fallback[] };
const KINDS = Object.keys(MAP.kinds) as Kind[];

/** What is wrong with the map read against the families of route_groups.json: an entry that is not exactly one of an
 *  element, a redirect or pending, a kind that is not one, a family with no entry or two, an entry no family has. */
function mapProblems(map: Fallback[], families: { route: string }[]): string[] {
  const out: string[] = [];
  const routes = new Set(families.map((f) => f.route));
  for (const e of map) {
    const shapes = [e.element != null || e.selector != null, e.redirect != null, e.pending != null].filter(Boolean).length;
    if (shapes !== 1) out.push(`${e.route}: an entry names an element and its selector, or a redirect, or the task it is pending`);
    if (e.element != null && (!KINDS.includes(e.element) || typeof e.selector !== 'string' || e.selector === '')) {
      out.push(`${e.route}: element is one of ${KINDS.join(', ')}, with a selector`);
    }
    if (!e.basis) out.push(`${e.route}: an entry says where its element comes from, in basis`);
    if (!routes.has(e.route)) out.push(`${e.route} is mapped but is no route family of scripts/route_groups.json`);
  }
  for (const f of families) {
    const n = map.filter((e) => e.route === f.route).length;
    if (n === 0) out.push(`${f.route} has no fallback element in scripts/route_fallback_map.json, so no page of it is checked`);
    if (n > 1) out.push(`${f.route} is mapped ${n} times: a family has one fallback element`);
  }
  return out;
}

/** What is wrong with the map read against the built families: a family with pages whose entry is still pending, an
 *  entry to render that has no page to render, a redirect to a page that is not built or whose family has no element. */
function builtProblems(map: Fallback[], families: Family[]): string[] {
  const out: string[] = [];
  const pagesOf = new Map(families.map((f) => [f.route, f.pages]));
  for (const e of map) {
    const pages = pagesOf.get(e.route) ?? [];
    if (e.pending != null && pages.length > 0) {
      out.push(`${e.route} has ${pages.length} built page(s) but its fallback entry is pending ${e.pending}: name its element`);
    }
    if (e.pending == null && pages.length === 0) out.push(`${e.route} is mapped to be rendered but has no built page`);
    if (e.redirect != null) {
      const target = targetOf(map, families, e.redirect);
      if (target == null) out.push(`${e.route} goes on to ${e.redirect}, which is no built page of a family mapped to an element`);
    }
  }
  return out;
}

/** The entry of the built family whose pages include `route`, when that entry names an element. */
function targetOf(map: Fallback[], families: Family[], route: string): Fallback | null {
  const family = families.find((f) => f.pages.includes(route));
  const entry = family == null ? undefined : map.find((e) => e.route === family.route);
  return entry?.element != null ? entry : null;
}

const groups = loadGroups();
/** The built families, each with its pages; route_groups.mjs throws on a page no family claims. */
const built = (): Family[] => assignPages(groups, builtRoutes(DIST));
/** The page of `e`'s family the gate renders: its first in route order. */
const sampleOf = (e: Fallback, families: Family[]) => families.find((f) => f.route === e.route)!.pages[0];

/** Render `route` with JavaScript off and say what keeps `entry`'s element from rendering there; [] when nothing does. */
async function renderProblems(page: Page, route: string, entry: Fallback, families: Family[]): Promise<string[]> {
  const res = await page.goto(route);
  if (res == null || res.status() !== 200) return [`${route} answered ${res?.status() ?? 'nothing'}`];
  let e = entry;
  if (entry.redirect != null) {
    try {
      await page.waitForURL((u) => u.pathname === entry.redirect, { timeout: 5_000 });
    } catch {
      return [`${route} does not go on to ${entry.redirect} with JavaScript off (it stayed at ${new URL(page.url()).pathname})`];
    }
    e = targetOf(MAP.families, families, entry.redirect)!;
  }
  const found = page.locator(e.selector!);
  if ((await found.count()) === 0) return [`${page.url()}: nothing matches ${e.selector}, its ${e.element}`];
  const el = found.first();
  const shape = await el.evaluate((node) => {
    const text = (n: Element) => (n.textContent ?? '').trim() !== '';
    const tag = node.tagName.toLowerCase();
    return {
      tag,
      noscript: node.closest('noscript') != null,
      rows: tag === 'table' ? [...node.querySelectorAll('tr')].filter((r) => r.querySelector('td') != null && text(r)).length : 0,
      items: tag === 'dl' ? [...node.querySelectorAll(':scope > dd, :scope > div > dd')].filter(text).length
        : [...node.querySelectorAll(':scope > li')].filter(text).length,
      drawn: node.querySelectorAll('path, rect, circle, ellipse, line, polyline, polygon, text, use, image').length,
    };
  });
  const out: string[] = [];
  const at = `${page.url()} ${e.selector}`;
  if (shape.noscript) out.push(`${at} is inside a <noscript>: the page as sent is the working thing (09 S8.6)`);
  if (e.element === 'table' && (shape.tag !== 'table' || shape.rows === 0)) out.push(`${at} is a <${shape.tag}> with ${shape.rows} row(s) of data, not a table`);
  if (e.element === 'list' && (!['ul', 'ol', 'dl'].includes(shape.tag) || shape.items === 0)) out.push(`${at} is a <${shape.tag}> with ${shape.items} item(s), not a list`);
  if (e.element === 'svg' && (shape.tag !== 'svg' || shape.drawn === 0)) out.push(`${at} is a <${shape.tag}> with nothing drawn, not an inline SVG`);
  if (out.length > 0) return out;
  // a closed <details> around it is opened the way a reader opens it: its summary, natively, with no script
  for (let open = 0; open < 8 && !(await el.isVisible()); open++) {
    const closed = el.locator('xpath=ancestor::details[not(@open)][1]');
    if ((await closed.count()) === 0) break;
    await closed.locator(':scope > summary').click();
  }
  if (!(await el.isVisible())) out.push(`${at} is in the page but not visible`);
  return out;
}

/** From now on, serve `route` to `page` as `body` instead of the page the server built. */
const serve = (page: Page, route: string, body: string) =>
  page.route((u) => u.pathname === route, (r) => r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body }));

/** Serve `route` again as `doctor` leaves the page the browser built from it, scripting still off. */
async function doctored(page: Page, route: string, selector: string, doctor: (els: Element[]) => void) {
  await page.goto(route);
  await page.locator(selector).evaluateAll(doctor);
  await serve(page, route, await page.content());
}

test('the nojs project runs this spec, with JavaScript off', () => {
  expect(test.info().project.name).toBe('nojs');
  expect(test.info().project.use.javaScriptEnabled).toBe(false);
});

test('the fallback map agrees with the route families: one entry for each, and none for a route that is no family', () => {
  expect(mapProblems(MAP.families, groups.families)).toEqual([]);
  expect(MAP.families.map((e) => e.route), 'in route_groups.json order').toEqual(groups.families.map((f) => f.route));
});

test('every page of the build belongs to a family whose entry names its element', () => {
  const families = built();
  expect(builtProblems(MAP.families, families)).toEqual([]);
  for (const f of families.filter((x) => x.pages.length > 0)) {
    const e = MAP.families.find((x) => x.route === f.route)!;
    expect(e.element != null || e.redirect != null, `${f.route} is checked`).toBe(true);
  }
});

test('a family or a route with no mapping fails rather than going unchecked', () => {
  const families = built();
  const [first, ...rest] = MAP.families.filter((e) => e.element != null);
  // the map with a family's entry taken out, with an entry no family has, and with a family mapped twice
  expect(mapProblems(MAP.families.filter((e) => e !== first), groups.families)).toEqual([
    `${first.route} has no fallback element in scripts/route_fallback_map.json, so no page of it is checked`,
  ]);
  expect(mapProblems([...MAP.families, { ...first, route: '/unmapped/{id}/' }], groups.families)).toEqual([
    '/unmapped/{id}/ is mapped but is no route family of scripts/route_groups.json',
  ]);
  expect(mapProblems([...MAP.families, rest[0]], groups.families)).toEqual([`${rest[0].route} is mapped 2 times: a family has one fallback element`]);
  expect(mapProblems([{ route: first.route, element: 'chart' as Kind, selector: 'figure', basis: 'b' }], [{ route: first.route }])).toHaveLength(1);
  // a family whose pages exist while its entry still waits on the task that routes it
  const pending = MAP.families.map((e) => (e === first ? { route: e.route, pending: 'P0-S0-T00', basis: e.basis } : e));
  expect(builtProblems(pending, families)).toEqual([
    `${first.route} has ${families.find((f) => f.route === first.route)!.pages.length} built page(s) but its fallback entry is pending P0-S0-T00: name its element`,
  ]);
  // and a built page that no family claims, which route_groups.mjs refuses before any entry is read
  expect(() => assignPages(groups, [...builtRoutes(DIST), '/unmapped/x/'])).toThrow(/no family in scripts\/route_groups\.json claims 1 built page/);
});

test('the checks themselves: an empty table, an empty list, an SVG with nothing drawn and the wrong element each fail', async ({ page }) => {
  // a page the server never built, served here, so each shape is known
  const cases: [string, Kind, string, RegExp][] = [
    ['<table class="x"><thead><tr><th>a</th></tr></thead><tbody></tbody></table>', 'table', 'table.x', /0 row\(s\) of data/],
    ['<div class="x"><p>a</p></div>', 'table', '.x', /is a <div>/],
    ['<ul class="x"></ul>', 'list', 'ul.x', /0 item\(s\)/],
    ['<svg class="x" viewBox="0 0 1 1"></svg>', 'svg', 'svg.x', /nothing drawn/],
    ['<img class="x" src="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22/%3E" alt="">', 'svg', '.x', /is a <img>/],
    ['<noscript><ul class="x"><li>a</li></ul></noscript>', 'list', 'ul.x', /inside a <noscript>/],
    ['<ul class="x" hidden><li>a</li></ul>', 'list', 'ul.x', /not visible/],
    ['<details><summary>open me</summary><svg class="x" viewBox="0 0 1 1"><rect width="1" height="1"/></svg></details>', 'svg', 'svg.x', /^$/],
  ];
  for (const [i, [html, element, selector, want]] of cases.entries()) {
    const route = `/_nojs-check/${i}/`;
    await serve(page, route, `<!doctype html><title>t</title><main>${html}</main>`);
    const got = (await renderProblems(page, route, { route, element, selector, basis: 'b' }, [])).join('\n');
    expect(got, html).toMatch(want);
  }
});

for (const entry of MAP.families.filter((e) => e.pending == null)) {
  const name = entry.redirect != null ? `goes on to ${entry.redirect}, without a script` : `its ${entry.element} renders`;
  test(`${entry.route}: ${name}, with JavaScript off`, async ({ page }) => {
    const families = built();
    expect(await renderProblems(page, sampleOf(entry, families), entry, families)).toEqual([]);
  });

  test(`${entry.route}: the gate goes red on its page doctored`, async ({ page, context }) => {
    const families = built();
    const route = sampleOf(entry, families);
    if (entry.redirect != null) {
      // the meta refresh taken out of the HTML as sent (in a browser it would already have left): it goes nowhere
      const sent = await (await page.request.get(route)).text();
      const refresh = /<meta\b[^>]*http-equiv=["']?refresh["']?[^>]*>/i;
      expect(sent, 'the page is a meta refresh').toMatch(refresh);
      await serve(page, route, sent.replace(refresh, ''));
      expect((await renderProblems(page, route, entry, families)).join('\n')).toMatch(/does not go on to/);
      return;
    }
    // the fallback element taken out
    await doctored(page, route, entry.selector!, (els) => els.forEach((x) => x.remove()));
    expect((await renderProblems(page, route, entry, families)).join('\n')).toContain(`nothing matches ${entry.selector}`);
    // the page kept whole, its fallback element with it, but inside a <noscript>: the selector still matches
    const fresh = await context.newPage();
    await doctored(fresh, route, entry.selector!, () => {
      const n = document.createElement('noscript');
      n.append(...document.body.childNodes);
      document.body.append(n);
    });
    expect((await renderProblems(fresh, route, entry, families)).join('\n')).toContain('inside a <noscript>');
  });
}
