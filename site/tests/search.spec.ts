// site/tests/search.spec.ts -- P2-S4-T07 (10 V11 "Search: three tiers", "Failure mode to avoid", "Without JavaScript";
// 09 S6.10, S8.4, S8.6, S11.5). The search route /search/, in a browser, over the draft preview playwright.config.ts
// builds:
//
//   cd site && npx playwright test tests/search.spec.ts
//
// Done when: "A first lexical result appears on keystroke and the JS-disabled search route is a usable route into the
// catalogue rather than a dead box." The failure the verification names is 10 V11's: "A search box that feels slow
// because it is waiting for the clever tier." No slower tier exists yet (the semantic one is P6-S1's), so this spec adds
// one through the island's seam (islands/SearchBox.tsx addLaterTier), importing the island's own module by the URL its
// <astro-island> names, which is the instance the page hydrated, and holds it: a first lexical result must appear while
// it is held, and once released its block is appended after the lexical list, which it neither reorders nor repeats. A
// tier that fails leaves the lexical results as they were, and a Pagefind bundle that cannot load leaves the directory.
//
// The JavaScript-off checks open their own context with JavaScript disabled, as tests/browse.spec.ts does, so the spec
// runs whole in the `js` project. Every expectation is computed from what the server serves: the query is a benchmark
// of the preview's facets.json (build/preview/, scripts/preview_corpus.py) whose name is one word that no other row's
// name, alias, edition or id contains, and the directory's links are held to the browse and taxonomy pages the build
// wrote into dist/. Both are read lazily, once the web server has built them.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Row { id: string; name: string; aliases: string[]; editions?: string[] }

const STEP = 10;                                  // islands/SearchBox.tsx STEP
const NO_MATCH = 'жжжж';
const DIST = fileURLToPath(new URL('../dist/', import.meta.url));

let rows: Row[] | undefined;
const ROWS = () => (rows ??= (JSON.parse(readFileSync(fileURLToPath(new URL('../../build/preview/facets.json', import.meta.url)), 'utf8')) as { benchmarks: Row[] }).benchmarks);

/** The benchmark the queries name: a one-word name no other row's name, aliases, editions or id contains. */
function target(): Row {
  const spelt = (r: Row) => [r.name, ...r.aliases, ...(r.editions ?? []), r.id].map((s) => s.toLowerCase());
  const all = ROWS();
  const found = all.filter((r) => /^[A-Za-z]{5,}$/.test(r.name)).sort((a, b) => a.name.localeCompare(b.name, 'en'))
    .find((r) => all.every((o) => o === r || spelt(o).every((s) => !s.includes(r.name.toLowerCase()))));
  if (found == null) throw new Error('the preview has no benchmark with a one-word name of its own to search for');
  return found;
}
const url = (r: Row) => `/benchmarks/${r.id}/`;

/** The routes the build wrote under dist/{dir}/, as the site spells them. */
function routes(dir: string): string[] {
  const out: string[] = [];
  const walk = (d: string) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      if (e.isDirectory()) walk(join(d, e.name));
      else if (e.name === 'index.html') out.push(`/${relative(DIST, d).split(sep).join('/')}/`);
    }
  };
  walk(join(DIST, dir));
  return out.sort();
}

const box = (page: Page) => page.locator('#search-q');
const results = (page: Page) => page.locator('[data-search-results]');
const lexical = (page: Page) => page.locator('ol[data-tier="lexical"] > li');
const shownUrls = (page: Page) => lexical(page).evaluateAll((lis) => lis.map((li) => li.getAttribute('data-url')));

async function hydrated(page: Page, path = '/search/') {
  await page.goto(path);
  await expect(page.locator('[data-search-box]')).not.toHaveAttribute('data-state', 'static');
}

/** Adds a later tier through the island's seam. `held` answers when release() is called with its hits; `fails` rejects. */
async function addTier(page: Page, id: string, mode: 'held' | 'fails') {
  await page.evaluate(`(async () => {
    const island = [...document.querySelectorAll('astro-island')].find((el) => el.querySelector('[data-search-box]'));
    const seam = await import(island.getAttribute('component-url'));
    const tiers = (window.__testTiers ??= {});
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    tiers[${JSON.stringify(id)}] = { asked: [], release };
    seam.addLaterTier({
      id: ${JSON.stringify(id)}, name: 'The test tier', heading: 'Found by the test tier',
      search: (q) => {
        tiers[${JSON.stringify(id)}].asked.push(q);
        return ${JSON.stringify(mode)} === 'fails' ? Promise.reject(new Error('the tier is down')) : gate;
      },
    });
  })()`);
}
const release = (page: Page, id: string, hits: { url: string; title: string; type: string; excerpt: string }[]) =>
  page.evaluate(([i, h]) => (window as unknown as { __testTiers: Record<string, { release: (x: unknown) => void }> }).__testTiers[i as string].release(h), [id, hits] as const);
const asked = (page: Page, id: string) =>
  page.evaluate((i) => (window as unknown as { __testTiers: Record<string, { asked: string[] }> }).__testTiers[i].asked, id);

test('the preview holds a benchmark to search for, and the build wrote the pages the directory links', () => {
  const t = target();
  expect(t.name.length).toBeGreaterThanOrEqual(5);
  expect(routes('browse').length).toBeGreaterThan(0);
  expect(routes('taxonomy').length).toBeGreaterThan(0);
});

test('with JavaScript off, /search/ is a route into the catalogue: every browse and taxonomy page linked, no box, no <noscript>', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  const res = await page.goto('/search/');
  expect(res!.status()).toBe(200);
  expect(await res!.text(), '09 S8.6: <noscript> is not the strategy').not.toMatch(/<noscript/i);
  // no dead box: nothing to type into, submit or press that could not answer
  await expect(page.locator('[data-search-box]')).toHaveAttribute('data-state', 'static');
  await expect(page.locator('main input, main form, main button')).toHaveCount(0);

  const hrefs = await page.locator('[data-search-directory] a').evaluateAll((as) => as.map((a) => a.getAttribute('href') ?? ''));
  const under = (prefix: string) => [...new Set(hrefs.filter((h) => h.startsWith(prefix)))].sort();
  expect(under('/browse/'), 'every single-facet browse page the build rendered, and no other').toEqual(routes('browse'));
  expect(under('/taxonomy/'), 'every taxonomy term page the build rendered, and no other').toEqual(routes('taxonomy'));
  const profiles = under('/orgs/');
  expect(hrefs.filter((h) => !/^\/(browse|taxonomy|orgs)\//.test(h)), 'the directory links nothing else').toEqual([]);
  for (const p of profiles) expect(routes('orgs'), p).toContain(p);
  // the spine and the facets most sessions start from are open as sent
  for (const s of ['domain', 'capability', 'evaluation-method']) {
    await expect(page.locator(`details.group[data-segment="${s}"]`)).toHaveAttribute('open', '');
  }

  // and the links work, still without JavaScript: a capability's page, and its definition
  const term = page.locator('details.group[data-segment="capability"] > ul > li').first();
  const browse = await term.locator('a').first().getAttribute('href');
  const definition = await term.locator('a.second').getAttribute('href');
  await term.locator('a').first().click();
  await expect(page).toHaveURL(new RegExp(`${browse}$`));
  await expect(page.locator('main h1')).toBeVisible();
  await page.goBack();
  await term.locator('a.second').click();
  await expect(page).toHaveURL(new RegExp(`${definition}$`));
  await expect(page.locator('main h1')).toBeVisible();
  await context.close();
});

test('Pagefind answers every keystroke, with no Enter, and a first lexical result appears as the name is typed', async ({ page }) => {
  const t = target();
  await hydrated(page);
  const linksAsSent = await page.locator('[data-search-directory] a').count();
  await box(page).focus();
  let first: number | null = null;
  for (let i = 1; i <= t.name.length; i += 1) {
    const typed = t.name.slice(0, i);
    const pressed = Date.now();
    await box(page).press(t.name[i - 1]);
    await expect(results(page), `keystroke ${i} is answered`).toHaveAttribute('data-answered', typed);
    if (first == null && (await lexical(page).count()) > 0) first = Date.now() - pressed;
  }
  expect(first, 'a result appeared while typing').not.toBeNull();
  test.info().annotations.push({ type: 'keystroke to answered result (ms, informational; P2-S8-T06 gates it)', description: String(first) });
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`), `${t.name} is among the first ${STEP}`).toBeVisible();
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toHaveAttribute('data-type', 'benchmark');
  expect(new URL(page.url()).searchParams.get('q'), 'the query is kept in the link').toBe(t.name);
  await expect(page.locator('[data-search-status]')).toHaveText(/\d+ results? for “/);
  // the directory is still the page below the box
  await expect(page.locator('[data-search-directory] a')).toHaveCount(linksAsSent);
});

test('the failure to avoid: a first result never waits on a slower tier, which appends its block once it answers', async ({ page }) => {
  const t = target();
  await hydrated(page);
  await addTier(page, 'held', 'held');
  await box(page).focus();
  await box(page).pressSequentially(t.name);

  // the held tier has been asked, on the same keystrokes, and has not answered: Pagefind's result is up regardless
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  await expect(results(page)).toHaveAttribute('data-later-pending', 'held');
  await expect(page.locator('[data-tier="held"]')).toHaveCount(0);
  expect(await asked(page, 'held')).toContain(t.name);

  // released: its block comes after the lexical list, without the pages the list already shows, and the list is unchanged
  const before = await shownUrls(page);
  const other = ROWS().find((r) => !before.includes(url(r)))!;
  await release(page, 'held', [
    { url: before[0]!, title: 'already shown', type: 'benchmark', excerpt: '' },
    { url: url(other), title: other.name, type: 'benchmark', excerpt: '' },
  ]);
  const block = page.locator('[data-tier="held"]');
  await expect(block).toBeVisible();
  await expect(block.locator('h3')).toHaveText('Found by the test tier');
  await expect(block.locator('li')).toHaveCount(1);
  await expect(block.locator(`li[data-url="${url(other)}"] a`)).toHaveText(other.name);
  await expect(results(page)).not.toHaveAttribute('data-later-pending', /./);
  expect(await shownUrls(page), 'the lexical list is neither reordered nor moved').toEqual(before);
  expect(await page.evaluate(() => {
    const list = document.querySelector('ol[data-tier="lexical"]')!;
    return (list.compareDocumentPosition(document.querySelector('[data-tier="held"]')!) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  }), 'appended after the lexical list').toBe(true);
});

test('a later tier that fails says so in one line and leaves the lexical results as they were', async ({ page }) => {
  const t = target();
  await hydrated(page);
  await addTier(page, 'broken', 'fails');
  await box(page).focus();
  await box(page).pressSequentially(t.name);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  await expect(page.locator('[data-tier-failed="broken"]')).toHaveText(/^The test tier is unavailable/);
  await expect(page.locator('[data-tier="broken"]')).toHaveCount(0);
});

// P2-S8-T09: a form needs a submit button (pa11y H32.2, SC 3.2.2), and this one's asks again for the box as it stands
test('the box\'s submit button, or Enter, asks again for the box as it stands, and the page stays where it is', async ({ page }) => {
  const t = target();
  await hydrated(page);
  await addTier(page, 'counted', 'fails');
  const times = async () => (await asked(page, 'counted')).filter((q) => q === t.name).length;
  const button = page.locator('form[role="search"] button[type="submit"]');
  await expect(button).toHaveText('Search');
  await box(page).fill(t.name);
  await expect(results(page)).toHaveAttribute('data-answered', t.name);
  expect(await times()).toBe(1);
  await button.click();
  await expect.poll(times).toBe(2);
  await box(page).press('Enter');
  await expect.poll(times).toBe(3);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/search/');
  expect(new URL(page.url()).searchParams.get('q')).toBe(t.name);
});

test('a Pagefind bundle that cannot load says so, and the directory stays the way in', async ({ page }) => {
  await page.route('**/pagefind/pagefind.js', (r) => r.abort());
  await hydrated(page);
  const links = await page.locator('[data-search-directory] a').count();
  await box(page).focus();
  await box(page).pressSequentially(target().name.slice(0, 3));
  await expect(page.locator('[data-search-box]')).toHaveAttribute('data-state', 'failed');
  await expect(page.locator('[data-search-failed]')).toHaveText(/^The search index could not be loaded .*facet links below\.$/);
  await expect(lexical(page)).toHaveCount(0);
  await expect(page.locator('[data-search-directory] a')).toHaveCount(links);
});

test('a link carrying ?q= is answered on arrival; more results on request; no match says so; a blank box clears', async ({ page }) => {
  const t = target();
  await hydrated(page, `/search/?q=${encodeURIComponent(t.name)}`);
  await expect(box(page)).toHaveValue(t.name);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();

  // a one-letter query matches more than a step: "Show more" reads the next one
  await box(page).fill(t.name[0]);
  await expect(results(page)).toHaveAttribute('data-answered', t.name[0]);
  const total = Number((await page.locator('.search-results .count').textContent())!.match(/of (\d+) results?/)![1]);
  await expect(lexical(page)).toHaveCount(Math.min(total, STEP));
  if (total > STEP) {
    await page.locator('.search-results button.more').click();
    await expect(lexical(page)).toHaveCount(Math.min(total, 2 * STEP));
  }

  // 09 S6.10: what happened, what it means, one action. Pagefind backs a word it does not hold off to the longest prefix
  // it does (a nonsense Latin word finds `q`), so the query is a word in a script the English index holds no word of
  await box(page).fill(NO_MATCH);
  await expect(results(page)).toHaveAttribute('data-answered', NO_MATCH);
  await expect(page.locator('[data-empty="search"]')).toHaveText(new RegExp(`^No page in the index matches “${NO_MATCH}”\.`));
  await expect(lexical(page)).toHaveCount(0);

  await box(page).fill('');
  await expect(results(page)).not.toHaveAttribute('data-answered', /./);
  await expect(page.locator('[data-empty="search"]')).toHaveCount(0);
  expect(new URL(page.url()).search).toBe('');
});
