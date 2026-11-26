// site/tests/semantic-results.spec.ts -- P6-S1-T09 (10 V11 "Search: three tiers"; 11 F0 "Made visible", S4 "First-query
// latency" item 3; 09 S8, S11.5). The semantic results as a block of their own on /search/ (components/
// SemanticResults.astro, islands/SearchBox.tsx, islands/search/semantic.ts), in a browser, over the draft preview
// playwright.config.ts builds:
//
//   cd site && npx playwright test tests/semantic-results.spec.ts
//
// The ledger's verify is `npm run test:a11y -- /benchmarks/`, the harness over the browse view; done when "Axe reports
// zero WCAG 2.2 AA violations and a DOM assertion confirms two separately labelled result regions". The block is on
// /search/, the page with the search box (SemanticResults.astro says why), and the harness audits a page as it loads,
// before any query, when the block is rightly absent; so this spec holds the rest:
//
//   - the DOM assertion (readRegions in the page, regionProblems here): before the tier is ready there is no semantic
//     block in the DOM at all, empty or not; once it is, the results region holds exactly two labelled regions, each a
//     <section> named by its own visible heading, the semantic one in 10 V11's words, each with one list of its own, no
//     row in both, the semantic one after the lexical one and inside neither. Its failure cases are checked as failures:
//     the live page with an empty semantic block put in before the tier is ready, and with its two lists fused into one,
//     and fixture markup for each other way to get it wrong;
//   - the block appends itself once the tier is ready, to the answer already on screen, with no further keystroke, and
//     moves nothing of the lexical list;
//   - axe-core, at the harness's WCAG 2.2 AA tags (test/a11y/archetypes.json), reports no violation on the page with
//     both regions shown, in the harness's four modes;
//   - a build without document vectors -- every build today -- never shows the block, and a load that fails in a build
//     that ships them shows the box's one-line notice and no block.
//
// The draft preview ships no document vectors (scripts/preview_corpus.py runs no S6), so the spec serves the page a build
// with them would: /search/ with data-vectors="shipped" and the entry table SemanticResults.astro writes (semantic.ts
// entryTable() and entriesJson(), the component's own functions), and /embed/vectors.meta.json and vectors.i8.bin in
// tools/build/embed.py's format, one row per row of the preview's facets.json. Every row is noise except one, chosen
// once the lexical answer is on screen from the rows it does not show, which is the query's own vector, encoded here by
// the encoder the page runs (islands/search/encoder.ts over public/embed/): so the cosine ranks that row first, and the
// block must show it. The vectors are held back until then, which is also what holds the tier short of ready.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { QueryEncoder, dequantise } from '../src/islands/search/encoder.ts';
import { SEMANTIC_HEADING, entriesJson, entryTable } from '../src/islands/search/semantic.ts';

interface Row { id: string; name: string; aliases: string[]; editions?: string[] }
type ModeName = 'light' | 'dark' | 'forced-colors' | 'contrast-more';
interface Mode { colorScheme: 'light' | 'dark'; forcedColors?: 'active'; contrast?: 'more' }

const TIER = '[data-semantic-tier]';
const BLOCK = '[data-tier="semantic"]';
const VECTORS_META = '/embed/vectors.meta.json';
const VECTORS_BIN = '/embed/vectors.i8.bin';
const READY_MS = 60_000;
const SPEC = JSON.parse(readFileSync(fileURLToPath(new URL('../test/a11y/archetypes.json', import.meta.url)), 'utf8')) as {
  modes: Record<ModeName, Mode>; standard: { axe: string[] };
};

let rows: Row[] | undefined;
const ROWS = () => (rows ??= (JSON.parse(readFileSync(fileURLToPath(new URL('../../build/preview/facets.json', import.meta.url)), 'utf8')) as { benchmarks: Row[] }).benchmarks);
const url = (r: Row) => `/benchmarks/${r.id}/`;

/** The benchmark the query names: a one-word name no other row's name, aliases, editions or id contains
 *  (tests/search.spec.ts target()), so Pagefind's answer is up on the first keystrokes. */
function target(): Row {
  const spelt = (r: Row) => [r.name, ...r.aliases, ...(r.editions ?? []), r.id].map((s) => s.toLowerCase());
  const all = ROWS();
  const found = all.filter((r) => /^[A-Za-z]{5,}$/.test(r.name)).sort((a, b) => a.name.localeCompare(b.name, 'en'))
    .find((r) => all.every((o) => o === r || spelt(o).every((s) => !s.includes(r.name.toLowerCase()))));
  if (found == null) throw new Error('the preview has no benchmark with a one-word name of its own to search for');
  return found;
}

let encoder: QueryEncoder | undefined;
/** The encoder the page runs, over the same files. */
function encode(text: string): Float32Array {
  if (encoder == null) {
    const embed = new URL('../public/embed/', import.meta.url);
    const bytes = (f: string) => new Uint8Array(readFileSync(new URL(f, embed)));
    const meta = JSON.parse(readFileSync(new URL('potion-8m-pruned.meta.json', embed), 'utf8'));
    const tokenizer = JSON.parse(readFileSync(new URL('tokenizer.json', embed), 'utf8'));
    encoder = new QueryEncoder(tokenizer, meta, dequantise(meta, bytes('potion-8m-pruned.i8.bin'), bytes('potion-8m-pruned.r2.bin')));
  }
  return encoder.encode(text);
}

/** vectors.meta.json and vectors.i8.bin as embed.py writes them over the preview's rows: row `near` is `query`'s vector,
 *  every other row deterministic noise. `corrupt` flips a byte after the sha256 is taken. */
function vectorsFor(query: string, near: number, corrupt = false) {
  const ids = ROWS().map((r) => r.id);
  const dims = 256;
  const bin = Buffer.alloc(ids.length * dims);
  const scales: number[] = [];
  let s = 11;
  for (let i = 0; i < ids.length; i++) {
    if (i === near) {
      const v = encode(query);
      const scale = Math.max(...Array.from(v, Math.abs)) / 127;
      for (let k = 0; k < dims; k++) bin.writeInt8(Math.round(v[k] / scale), i * dims + k);
      scales.push(scale);
    } else {
      for (let k = 0; k < dims; k++) {
        s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
        bin.writeInt8((s % 201) - 100, i * dims + k);
      }
      scales.push(0.01);
    }
  }
  const sha256 = createHash('sha256').update(bin).digest('hex');
  if (corrupt) bin[1000] ^= 1;
  const meta = { artifact: 'vectors', format: 1, rows: ids.length, dims, ids, scales,
    vectors: { file: 'vectors.i8.bin', dtype: 'int8', layout: 'row-major', bytes: bin.length, sha256 } };
  return { meta: JSON.stringify(meta), bin };
}

/** Serves /search/ as a build that ships the vectors does: data-vectors="shipped", and the component's entry table. */
async function shipVectors(page: Page) {
  const table = entriesJson(entryTable(ROWS(), () => true));
  await page.route((u) => u.pathname === '/search/', async (route) => {
    const res = await route.fetch();
    const html = await res.text();
    const tier = /(<div\b[^>]*\bdata-semantic-tier\b[^>]*?)\bdata-vectors="none"([^>]*>)/;
    if (!tier.test(html)) throw new Error('/search/ has no [data-semantic-tier] element with data-vectors="none" to ship vectors in');
    await route.fulfill({ response: res,
      body: html.replace(tier, (_, open: string, rest: string) => `${open}data-vectors="shipped"${rest}<script type="application/json" data-semantic-entries>${table}</script>`) });
  });
}

/** Holds the vectors back until release() names the row the query's vector goes in. */
async function holdVectors(page: Page, query: string, corrupt = false) {
  let release: (near: number) => void = () => undefined;
  const chosen = new Promise<number>((r) => { release = r; });
  let asked = false;
  let pair: ReturnType<typeof vectorsFor> | undefined;
  await page.route((u) => u.pathname === VECTORS_META || u.pathname === VECTORS_BIN, async (route) => {
    asked = true;
    const near = await chosen;
    pair ??= vectorsFor(query, near, corrupt);
    const meta = new URL(route.request().url()).pathname === VECTORS_META;
    await route.fulfill({ status: 200, contentType: meta ? 'application/json' : 'application/octet-stream', body: meta ? pair.meta : pair.bin });
  });
  return { release: (near: number) => release(near), asked: () => asked };
}

const box = (page: Page) => page.locator('#search-q');
const results = (page: Page) => page.locator('[data-search-results]');
const tier = (page: Page) => page.locator(TIER);
const lexicalUrls = (page: Page) => page.locator('ol[data-tier="lexical"] > li').evaluateAll((lis) => lis.map((li) => li.getAttribute('data-url')!));

// ---- the DOM assertion ----------------------------------------------------------------------------------------------

/** One <section> under the results region, as the DOM says: the name its aria-labelledby (or aria-label) gives, its
 *  lists and their rows, and whether it sits inside another section of the region. */
interface Region { name: string; tier: string | null; lists: number; items: string[]; nested: boolean; empty: boolean }
interface Regions { regions: Region[]; lists: { region: number; items: string[] }[] }

/** Reads the results region under `root` (the page's [data-search-results], or a copy of it). Runs in the page. */
function readRegions(root: Element | null): Regions | null {
  if (root == null) return null;
  const byId = (id: string) => root.querySelector(`[id="${id}"]`) ?? root.ownerDocument.getElementById(id);
  const nameOf = (el: Element) => {
    const ids = (el.getAttribute('aria-labelledby') ?? '').split(/\s+/).filter((x) => x !== '');
    if (ids.length > 0) return ids.map((id) => (byId(id)?.textContent ?? '').trim()).join(' ').trim();
    return (el.getAttribute('aria-label') ?? '').trim();
  };
  const sections = [...root.querySelectorAll('section')];
  const urls = (el: Element) => [...el.querySelectorAll('li')].map((li) => li.getAttribute('data-url') ?? li.querySelector('a')?.getAttribute('href') ?? '');
  return {
    regions: sections.map((s) => ({
      name: nameOf(s),
      tier: s.getAttribute('data-tier') ?? s.getAttribute('data-result-region'),
      lists: s.querySelectorAll('ol, ul').length,
      items: urls(s),
      nested: s.parentElement?.closest('section') !== root,
      empty: (s.textContent ?? '').trim() === '' || s.querySelectorAll('li').length === 0,
    })),
    lists: [...root.querySelectorAll('ol, ul')].map((l) => ({ region: sections.indexOf(l.closest('section') as HTMLElement), items: urls(l) })),
  };
}

const SEMANTIC = /did not type the words for/i;

/** What is wrong with the results region read by readRegions(), before the tier is ready or after. Before: no semantic
 *  block in the DOM at all, empty or not. After: exactly two labelled regions, lexical then semantic, each with one list
 *  of its own, no row in both, neither inside the other. */
function regionProblems(r: Regions | null, ready: boolean): string[] {
  if (r == null) return ['the page has no search results region'];
  const out: string[] = [];
  r.regions.forEach((g, i) => { if (g.name === '') out.push(`result block ${i + 1} has no label`); });
  r.lists.forEach((l, i) => { if (l.region < 0) out.push(`list ${i + 1} is in no labelled region of its own`); });
  const semantic = r.regions.filter((g) => SEMANTIC.test(g.name) || g.tier === 'semantic');
  if (!ready) {
    for (const g of semantic) {
      out.push(`a semantic block (${g.items.length} rows${g.empty ? ', empty' : ''}) is in the DOM before the tier is ready: it must be absent, not empty`);
    }
    return out;
  }
  const labelled = r.regions.filter((g) => g.name !== '');
  if (labelled.length !== 2) out.push(`${labelled.length} labelled result region(s), not two: lexical and semantic`);
  if (semantic.length !== 1) {
    out.push(`${semantic.length} semantic block(s), not one`);
    return out;
  }
  const sem = semantic[0];
  const lex = labelled.find((g) => g !== sem);
  if (lex == null) {
    out.push('no lexical region beside the semantic block');
    return out;
  }
  if (!SEMANTIC.test(sem.name)) out.push(`the semantic block is labelled "${sem.name}", not as related entries the reader did not type the words for`);
  if (SEMANTIC.test(lex.name) || lex.name === sem.name) out.push(`the two regions are not told apart: "${lex.name}" and "${sem.name}"`);
  for (const [what, g] of [['lexical', lex], ['semantic', sem]] as const) {
    if (g.lists !== 1) out.push(`the ${what} region holds ${g.lists} lists, not one of its own`);
    if (g.nested) out.push(`the ${what} region sits inside another region`);
  }
  if (sem.items.length === 0) out.push('the semantic block is empty: a block with nothing to show must be absent');
  const both = sem.items.filter((u) => lex.items.includes(u));
  if (both.length > 0) out.push(`fused: ${both.join(', ')} in both regions`);
  if (r.regions.indexOf(lex) > r.regions.indexOf(sem)) out.push('the semantic block comes before the lexical results');
  return out;
}

// ---- the tests ------------------------------------------------------------------------------------------------------

test('absent, not empty, until the tier is ready; then a second labelled region after the lexical one, never fused', async ({ page }) => {
  test.setTimeout(120_000);
  const t = target();
  await shipVectors(page);
  const held = await holdVectors(page, t.name);
  await page.goto('/search/');
  await expect(page.locator('[data-search-box]')).not.toHaveAttribute('data-state', 'static');
  await expect(tier(page)).toHaveAttribute('data-vectors', 'shipped');
  await box(page).focus();
  await box(page).pressSequentially(t.name);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  await expect.poll(held.asked, { timeout: READY_MS }).toBe(true);

  // the tier is loading, held on its vectors: the lexical region is labelled, and the semantic block is not in the DOM
  await expect(tier(page)).toHaveAttribute('data-state', 'loading');
  await expect(page.locator(BLOCK)).toHaveCount(0);
  const before = await page.evaluate(readRegions, await results(page).elementHandle());
  expect(regionProblems(before, false)).toEqual([]);
  expect(before!.regions.map((g) => g.name)).toEqual(['Results matching your words']);
  // the failure case: an empty block put in before the tier is ready fails the assertion
  const early = await results(page).evaluate((root, heading) => {
    const copy = root.cloneNode(true) as Element;
    copy.insertAdjacentHTML('beforeend', `<section data-tier="semantic" aria-labelledby="early-h"><h2 id="early-h">${heading}</h2><ol class="hits"></ol></section>`);
    return copy.outerHTML;
  }, SEMANTIC_HEADING);
  expect(regionProblems(await readFixture(page, early), false)).toEqual([
    'a semantic block (0 rows, empty) is in the DOM before the tier is ready: it must be absent, not empty',
  ]);

  // released: the query's vector goes in a row the lexical list does not show, and the block appends with no keystroke
  const shown = await lexicalUrls(page);
  const near = ROWS().findIndex((r) => r.id !== t.id && !shown.includes(url(r)));
  held.release(near);
  await expect(tier(page)).toHaveAttribute('data-state', 'ready', { timeout: READY_MS });
  const block = page.locator(BLOCK);
  await expect(block).toBeVisible();
  await expect(block.getByRole('heading')).toHaveText(SEMANTIC_HEADING);
  await expect(page.getByRole('region', { name: SEMANTIC_HEADING, exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Results matching your words', exact: true })).toBeVisible();
  await expect(block.locator('li').first()).toHaveAttribute('data-url', url(ROWS()[near]));
  await expect(block.locator('li').first().locator('a')).toHaveText(ROWS()[near].name);
  expect(await lexicalUrls(page), 'the lexical list is neither reordered nor moved').toEqual(shown);
  await expect(results(page)).toHaveAttribute('data-answered', t.name);

  const after = await page.evaluate(readRegions, await results(page).elementHandle());
  expect(regionProblems(after, true)).toEqual([]);
  expect(after!.regions.map((g) => g.name)).toEqual(['Results matching your words', SEMANTIC_HEADING]);
  expect(after!.regions[1].items.length).toBeLessThanOrEqual(10);

  // the failure case: the same two result sets fused into one list fails it
  const fused = await results(page).evaluate((root) => {
    const copy = root.cloneNode(true) as Element;
    const lexical = copy.querySelector('ol[data-tier="lexical"]')!;
    const semantic = copy.querySelector('[data-tier="semantic"]')!;
    for (const li of semantic.querySelectorAll('li')) lexical.append(li);
    semantic.remove();
    return copy.outerHTML;
  });
  expect(regionProblems(await readFixture(page, fused), true)).toEqual([
    '1 labelled result region(s), not two: lexical and semantic',
    '0 semantic block(s), not one',
  ]);
});

/** readRegions() over `html` in a blank page of the same browser: the assertion's fixtures. */
async function readFixture(page: Page, html: string): Promise<Regions | null> {
  const other = await page.context().newPage();
  try {
    await other.setContent(`<!doctype html><html lang="en"><body>${html}</body></html>`);
    return await other.evaluate(readRegions, await other.locator('body > section').first().elementHandle());
  } finally {
    await other.close();
  }
}

test('the DOM assertion fails every other way to get the two regions wrong', async ({ page }) => {
  const lex = (items: string) => `<section aria-labelledby="l"><h2 id="l">Results matching your words</h2><ol data-tier="lexical">${items}</ol></section>`;
  const sem = (items: string, attrs = 'aria-labelledby="s"', heading = SEMANTIC_HEADING) =>
    `<section data-tier="semantic" ${attrs}><h2 id="s">${heading}</h2><ol>${items}</ol></section>`;
  const li = (u: string) => `<li data-url="${u}"><a href="${u}">${u}</a></li>`;
  const wrap = (inner: string) => `<section aria-label="Search results" data-search-results>${inner}</section>`;
  const cases: [string, string, boolean, string[]][] = [
    ['right', wrap(lex(li('/a/')) + sem(li('/b/'))), true, []],
    ['right, before the tier is ready', wrap(lex(li('/a/'))), false, []],
    ['a non-empty block before the tier is ready', wrap(lex(li('/a/')) + sem(li('/b/'))), false,
      ['a semantic block (1 rows) is in the DOM before the tier is ready: it must be absent, not empty']],
    ['an empty block once ready', wrap(lex(li('/a/')) + sem('')), true, ['the semantic block is empty: a block with nothing to show must be absent']],
    ['one region, two lists', wrap(`<section aria-labelledby="l"><h2 id="l">Results</h2><ol>${li('/a/')}</ol><h2>${SEMANTIC_HEADING}</h2><ol>${li('/b/')}</ol></section>`), true,
      ['1 labelled result region(s), not two: lexical and semantic', '0 semantic block(s), not one']],
    ['an unlabelled block', wrap(lex(li('/a/')) + sem(li('/b/'), '')), true,
      ['result block 2 has no label', '1 labelled result region(s), not two: lexical and semantic', 'the semantic block is labelled "", not as related entries the reader did not type the words for']],
    ['a row in both', wrap(lex(li('/a/') + li('/b/')) + sem(li('/b/'))), true, ['fused: /b/ in both regions']],
    ['the block first', wrap(sem(li('/b/')) + lex(li('/a/'))), true, ['the semantic block comes before the lexical results']],
    ['the block inside the lexical region', wrap(`<section aria-labelledby="l"><h2 id="l">Results matching your words</h2><ol>${li('/a/')}</ol>${sem(li('/b/'))}</section>`), true,
      ['the lexical region holds 2 lists, not one of its own', 'the semantic region sits inside another region', 'fused: /b/ in both regions']],
    ['the block labelled as something else', wrap(lex(li('/a/')) + sem(li('/b/'), 'aria-labelledby="s"', 'More results')), true,
      ['the semantic block is labelled "More results", not as related entries the reader did not type the words for']],
  ];
  for (const [what, html, ready, problems] of cases) {
    const r = await readFixture(page, html);
    expect(regionProblems(r, ready), what).toEqual(problems);
  }
});

test('axe-core finds no WCAG 2.2 AA violation on /search/ with both result regions shown, in the four modes', async ({ page }) => {
  test.setTimeout(150_000);
  const t = target();
  await shipVectors(page);
  const held = await holdVectors(page, t.name);
  await page.goto(`/search/?q=${encodeURIComponent(t.name)}`);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  const shown = await lexicalUrls(page);
  held.release(ROWS().findIndex((r) => r.id !== t.id && !shown.includes(url(r))));
  await expect(tier(page)).toHaveAttribute('data-state', 'ready', { timeout: READY_MS });
  await expect(page.locator(BLOCK)).toBeVisible();
  for (const [name, mode] of Object.entries(SPEC.modes) as [ModeName, Mode][]) {
    await page.emulateMedia({ colorScheme: mode.colorScheme, forcedColors: mode.forcedColors ?? 'none', contrast: mode.contrast ?? 'no-preference' });
    await expect(page.locator(BLOCK), name).toBeVisible();
    expect(regionProblems(await page.evaluate(readRegions, await results(page).elementHandle()), true), name).toEqual([]);
    const axe = await new AxeBuilder({ page }).withTags(SPEC.standard.axe).analyze();
    expect(axe.passes.length, `${name}: axe-core read the page`).toBeGreaterThan(0);
    expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`), name).toEqual([]);
  }
});

test('a build without document vectors never shows the block; a failed load shows the one-line notice and no block', async ({ page }) => {
  test.setTimeout(150_000);
  const t = target();
  // as built: the draft preview ships no vectors, so the tier loads the encoder, is ready, and has nothing to rank
  await page.goto(`/search/?q=${encodeURIComponent(t.name)}`);
  await expect(tier(page)).toHaveAttribute('data-vectors', 'none');
  await expect(tier(page)).toHaveAttribute('data-state', 'ready', { timeout: READY_MS });
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
  await box(page).fill(`${t.name} `);
  await expect(results(page)).toHaveAttribute('data-answered', `${t.name} `);
  await expect(page.locator(BLOCK)).toHaveCount(0);
  await expect(page.locator('[data-tier-failed]')).toHaveCount(0);
  expect(regionProblems(await page.evaluate(readRegions, await results(page).elementHandle()), false)).toEqual([]);

  // a build that ships them, whose vectors fail their sha256: the notice under the lexical results, and no block
  await shipVectors(page);
  const held = await holdVectors(page, t.name, true);
  held.release(0);
  await page.goto(`/search/?q=${encodeURIComponent(t.name)}`);
  await expect(tier(page)).toHaveAttribute('data-state', 'failed', { timeout: READY_MS });
  await expect(tier(page)).toHaveAttribute('data-failure', /vectors\.i8\.bin has the sha256 [0-9a-f]{64}, and its meta says/);
  await box(page).fill(`${t.name} `);
  await expect(page.locator('[data-tier-failed="semantic"]')).toHaveText(/^Semantic search is unavailable: the results above are the word-match results, unchanged\.$/);
  await expect(page.locator(BLOCK)).toHaveCount(0);
  await expect(page.locator(`ol[data-tier="lexical"] > li[data-url="${url(t)}"]`)).toBeVisible();
});
