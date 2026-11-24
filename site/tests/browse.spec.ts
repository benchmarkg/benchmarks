// site/tests/browse.spec.ts -- P2-S4-T04 (10 V11 "The filter panel", "Filter state encoding"; 09 S6.10, S8.4, S10;
// 12 S5.3). The browse view at /benchmarks/, in a browser, over the draft preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/browse.spec.ts
//
// Done when: "Counts are live, zero-count terms are visible and disabled, chips are individually removable, and the
// curation-confidence indicator is present." Every expectation is computed here from the files the server serves --
// facets.json, and enums.json for each term's key and definition, both from build/preview/ (scripts/preview_corpus.py)
// -- not from the view's own logic (src/lib/browse-view.ts). The failure the verification names is checked as a
// failure: a zero-count term is looked for after a filter has made it zero, and the row count is held to the
// vocabulary's, so a view that hid zero-count terms instead of disabling them fails here.
//
// No entry is published yet, so the preview's 320 drafts stand in for the published corpus, as on every page test. The
// state with no published entry is the same page with facets.json answered by an empty one (page.route), and so is a
// facets.json the view cannot read. Unit tests of the logic are test/browse-view.test.mjs.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

interface Row {
  id: string;
  name: string;
  domain: string;
  subdomain: string;
  year: number | null;
  facets: Record<string, string[]>;
}
interface EnumTerm { id: string; key: string; label: string | null; gloss: string | null; field?: string; parent?: string | null }

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const facets = preview('facets.json') as { artifact: string; format: number; benchmarks: Row[] };
const enums = preview('enums.json') as { flat_facets: Record<string, { vocabularies: string[] }>; vocabularies: Record<string, { terms: EnumTerm[] }> };
const manifest = preview('build-manifest.json') as { paths: Record<string, string> };
const taxonomy = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/taxonomy.json', import.meta.url)), 'utf8')) as {
  facets: { domain: Record<string, { label: string; reviewer_signoff?: string }> };
};
const ROWS = facets.benchmarks;
const FACETS_URL = manifest.paths['facets.json'];

// 10's grammar keys the rail answers to: key -> the vocabulary (and field) its terms come from
const RAIL: [string, string, string | null][] = [
  ['d', 'domain', null], ['c', 'capability', null], ['em', 'evaluation_method', null], ['s', 'subject', null],
  ['lc', 'lifecycle', 'lifecycle'], ['acc', 'data_properties', 'data.access'], ['mt', 'governance', 'governance.maintainer_type'],
  ['sp', 'governance', 'governance.submission_process'], ['ct', 'execution', 'execution.compute_tier'],
  ['rt', 'execution', 'execution.reproducibility_tier'],
];
const SEGMENT: Record<string, [string, string]> = {          // key -> [/taxonomy/ segment, /browse/ segment]
  d: ['domain', 'domain'], c: ['capability', 'capability'], em: ['evaluation-method', 'evaluation-method'], s: ['subject', 'subject'],
  lc: ['lifecycle', 'lifecycle'], acc: ['data-properties', 'access'], mt: ['governance', 'maintainer-type'],
  sp: ['governance', 'submission-process'], ct: ['execution', 'compute-tier'], rt: ['execution', 'reproducibility-tier'],
};
const flatOf = new Map(Object.entries(enums.flat_facets).flatMap(([flat, d]) => d.vocabularies.map((v) => [v, flat] as const)));
const termsOf = (vocab: string, field: string | null) => enums.vocabularies[vocab].terms.filter((t) => field == null || t.field === field);
const VOCAB = new Map(RAIL.map(([key, vocab, field]) => [key, termsOf(vocab, field)]));
const ALL_TERMS = [...VOCAB.values()].reduce((n, ts) => n + ts.length, 0);

/** Does `row` carry term `id` of rail key `key`? From enums.json's `key`, the spelling the emitter writes. */
function carries(key: string, id: string): (r: Row) => boolean {
  const [, vocab, field] = RAIL.find((x) => x[0] === key)!;
  const t = VOCAB.get(key)!.find((x) => x.id === id)!;
  if (key === 'd') return (r) => (t.parent == null ? r.domain === id : r.subdomain === id);
  const flat = flatOf.get(vocab)!;
  void field;
  return (r) => r.facets[flat].includes(t.key);
}

type State = Record<string, string[]>;
/** The results and every term's count for a selection: AND across keys, OR within one, a key's own selection left out
 *  of its terms' counts. */
function expected(state: State, rows: Row[] = ROWS) {
  const passes = (r: Row, skip: string | null) => Object.entries(state).every(([k, ids]) => k === skip || ids.length === 0 || ids.some((id) => carries(k, id)(r)));
  const counts = new Map<string, number>();
  for (const [key] of RAIL) {
    for (const t of VOCAB.get(key)!) counts.set(`${key}:${t.id}`, rows.filter((r) => passes(r, key) && carries(key, t.id)(r)).length);
  }
  return { total: rows.filter((r) => passes(r, null)).length, counts };
}
const said = (n: number) => (n === 0 ? 'No benchmark matches' : n === 1 ? '1 benchmark matches' : `${n} benchmarks match`);

/** Every term row the rail shows: its group, id, count and checkbox state. */
const shown = (page: Page) => page.$$eval('[data-browse-view] li.term', (lis) => lis.map((li) => {
  const input = li.querySelector(':scope > .row > input') as HTMLInputElement | null;
  return {
    key: `${li.closest('details.group')!.getAttribute('data-group')}:${li.getAttribute('data-term')}`,
    count: li.getAttribute('data-count'),
    disabled: input?.disabled ?? null,
    checked: input?.checked ?? null,
  };
}));

async function ready(page: Page, query = '') {
  await page.goto(`/benchmarks/${query}`);
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'ready');
}
const box = (page: Page, key: string, id: string) => page.locator(`details[data-group="${key}"] li.term[data-term="${id}"] > .row > input`);
// the definitions open beside the rail on hover; a person moves the pointer off one before reaching for the list, and
// Playwright, which jumps, does it explicitly
const away = (page: Page) => page.mouse.move(1, 1);

async function countsMatch(page: Page, state: State) {
  const want = expected(state);
  const rows = await shown(page);
  expect(rows.length, 'every term of every rail vocabulary is a row').toBe(ALL_TERMS);
  for (const r of rows) expect(Number(r.count), r.key).toBe(want.counts.get(r.key));
  await expect(page.locator('ol.results > li')).toHaveCount(want.total);
  return want;
}

// the broadest capability, and the broadest evaluation method within it
const top = (key: string, state: State) => [...expected(state).counts].filter(([k]) => k.startsWith(`${key}:`)).sort((a, b) => b[1] - a[1])[0][0].split(':')[1];
const C = top('c', {});
const EM = top('em', { c: [C] });
const carriesAll = (state: State) => (r: Row) => Object.entries(state).every(([k, ids]) => ids.some((id) => carries(k, id)(r)));
const FAM = ROWS.find(carriesAll({ c: [C], em: [EM] }))!.domain;          // a family the two leave non-zero
const C2 = VOCAB.get('c')!.find((t) => t.id !== C && expected({}).counts.get(`c:${t.id}`)! > 0)!.id;
// a capability and an evaluation method each carried by some benchmark, never by the same one
const DISJOINT = (() => {
  const all = expected({});
  for (const c of VOCAB.get('c')!) {
    if (all.counts.get(`c:${c.id}`) === 0) continue;
    for (const em of VOCAB.get('em')!) {
      if (all.counts.get(`em:${em.id}`)! > 0 && expected({ c: [c.id], em: [em.id] }).total === 0) return { c: c.id, em: em.id };
    }
  }
  return null;
})();

test('the preview is what these expectations read: facets.json format 3 by its hashed URL, and published rows', () => {
  expect(facets.artifact).toBe('facets');
  expect(facets.format).toBe(3);
  expect(ROWS.length).toBeGreaterThan(0);
  expect(FACETS_URL).toMatch(/^\/data\/facets\.[0-9a-f]{8}\.json$/);
  expect(DISJOINT, 'a capability and an evaluation method that never meet').not.toBeNull();
});

test('as sent, with JavaScript off: every term links its single-facet page, and facets.json is named by its hashed URL only', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  const res = await page.goto('/benchmarks/');
  expect(res!.status()).toBe(200);
  const html = await res!.text();
  // the only data reference is this build's hashed facets.json (08 S4.4; tools/build/manifest.py S13 checks every page)
  expect([...new Set(html.match(/\/data\/[^"&\s<]*/g))]).toEqual([FACETS_URL]);
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'loading');
  await expect(page.locator('[data-browse-view] li.term')).toHaveCount(ALL_TERMS);
  await expect(page.locator('[data-browse-view] li.term input')).toHaveCount(0);
  for (const [key] of RAIL) {
    for (const t of VOCAB.get(key)!) {
      await expect(page.locator(`details[data-group="${key}"] li.term[data-term="${t.id}"] > .row > a`)).toHaveAttribute('href', `/browse/${SEGMENT[key][1]}/${t.id}/`);
    }
  }
  const sample = page.locator('details[data-group="c"] li.term > .row > a').first();
  expect((await page.request.get((await sample.getAttribute('href'))!)).status(), 'a rail link resolves').toBe(200);
  await context.close();
});

test('counts are live: every count is recomputed on each change and equals the one facets.json gives', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await ready(page);
  expect(errors, 'the island hydrates over the markup the server sent, without an error').toEqual([]);
  await countsMatch(page, {});
  await box(page, 'c', C).check();
  await expect(page).toHaveURL(`/benchmarks/?c=${C}&v=1`);
  const one = await countsMatch(page, { c: [C] });
  expect(one.total).toBe(expected({}).counts.get(`c:${C}`));
  await box(page, 'em', EM).check();
  await countsMatch(page, { c: [C], em: [EM] });
  await box(page, 'd', FAM).check();
  await countsMatch(page, { c: [C], em: [EM], d: [FAM] });
  await box(page, 'c', C).uncheck();
  await countsMatch(page, { em: [EM], d: [FAM] });
  await expect(page.locator('h2#browse-results-h .count')).toHaveText(`(${expected({ em: [EM], d: [FAM] }).total} of ${ROWS.length})`);
});

test('zero-count terms stay visible and disabled, never hidden; a selected term at zero stays enabled to be removed', async ({ page }) => {
  await ready(page);
  const before = await shown(page);
  expect(before.length).toBe(ALL_TERMS);
  await box(page, 'c', C).check();
  await box(page, 'em', EM).check();
  const after = await shown(page);
  expect(after.length, 'a filter hides no term').toBe(ALL_TERMS);
  expect(after.map((r) => r.key)).toEqual(before.map((r) => r.key));
  const zero = after.filter((r) => r.count === '0' && !r.checked);
  expect(zero.length, 'the filter has made some terms zero').toBeGreaterThan(before.filter((r) => r.count === '0').length);
  for (const r of after) expect(r.disabled, r.key).toBe(r.count === '0' && !r.checked);
  // one that the filter made zero, in a group open on arrival (a family, a capability, an evaluation method), is on
  // screen and disabled
  const onScreen = (k: string) => /^(c|em):/.test(k) || (k.startsWith('d:') && !k.includes('/'));
  const madeZero = after.find((r) => onScreen(r.key) && r.count === '0' && before.find((b) => b.key === r.key)!.count !== '0');
  expect(madeZero, 'the filter has made a visible term zero').toBeDefined();
  const [group, id] = [madeZero!.key.split(':')[0], madeZero!.key.slice(madeZero!.key.indexOf(':') + 1)];
  const row = page.locator(`details[data-group="${group}"] li.term[data-term="${id}"]`);
  await expect(row).toBeVisible();
  await expect(row.locator(':scope > .row > input')).toBeDisabled();
  await expect(row.locator(':scope > .row > label .n')).toHaveText('0');

  // a selection that excludes everything: its terms count zero, stay checked and enabled, and the empty state offers
  // the one filter whose removal returns the most
  await ready(page, `?c=${DISJOINT!.c}&em=${DISJOINT!.em}&v=1`);
  for (const [key, id] of [['c', DISJOINT!.c], ['em', DISJOINT!.em]]) {
    const b = box(page, key, id);
    await expect(b).toBeChecked();
    await expect(b).toBeEnabled();
    await expect(page.locator(`details[data-group="${key}"] li.term[data-term="${id}"]`)).toHaveAttribute('data-count', '0');
  }
  await expect(page.locator('[data-empty="filter"]')).toContainText('No benchmark matches all 2 filters.');
  const dropC = expected({ em: [DISJOINT!.em] }).total;
  const dropEm = expected({ c: [DISJOINT!.c] }).total;
  const drop = page.locator('[data-empty="filter"] button.drop');
  await expect(drop).toContainText(dropC >= dropEm ? 'Remove Capability:' : 'Remove Evaluation method:');
  await away(page);
  await drop.click();
  await expect(page.locator('ol.results > li')).toHaveCount(Math.max(dropC, dropEm));
});

test('chips: one per applied filter above the results, each removable on its own', async ({ page }) => {
  const state: State = { c: [C, C2].sort(), em: [EM] };
  await ready(page, `?c=${state.c.join(',')}&em=${EM}&v=1`);
  const chips = page.locator('.applied .chips button.chip');
  await expect(chips).toHaveCount(3);
  await expect(chips.nth(0)).toHaveAttribute('data-chip', `c=${state.c[0]}`);
  await expect(chips.nth(2)).toHaveAttribute('data-chip', `em=${EM}`);
  for (const c of await chips.all()) await expect(c).toHaveAttribute('data-state', 'filter-active');
  // the applied-filter chips sit above the result list
  const chipsBox = (await page.locator('.applied').boundingBox())!;
  const listBox = (await page.locator('[data-browse-state="ready"]').boundingBox())!;
  expect(chipsBox.y).toBeLessThan(listBox.y);
  await away(page);
  await chips.nth(1).click();                                          // the second capability, alone
  await expect(chips).toHaveCount(2);
  await expect(page.locator('.applied [data-chip]')).toHaveText([new RegExp(`Capability:`), new RegExp('Evaluation method:')]);
  await expect(box(page, 'c', state.c[1])).not.toBeChecked();
  await expect(box(page, 'c', state.c[0])).toBeChecked();
  await expect(page).toHaveURL(`/benchmarks/?c=${state.c[0]}&em=${EM}&v=1`);
  await countsMatch(page, { c: [state.c[0]], em: [EM] });
  await page.locator('.applied [data-chip]').first().click();
  await expect(chips).toHaveCount(1);
  await expect(page).toHaveURL(`/benchmarks/?em=${EM}&v=1`);
  await chips.first().click();
  await expect(page.locator('.applied .none')).toHaveText('No filter applied.');
  await expect(page).toHaveURL('/benchmarks/');
  await expect(page.locator('ol.results > li')).toHaveCount(ROWS.length);
});

test('the selection is the URL: canonical on every change, read back on load and on Back; what it cannot apply is said', async ({ page }) => {
  // keys out of order, values out of order, no version: read as the same selection
  await ready(page, `?em=${EM}&c=${C}`);
  await expect(page.locator('.applied [data-chip]')).toHaveCount(2);
  await countsMatch(page, { c: [C], em: [EM] });
  await box(page, 'em', EM).uncheck();
  await expect(page).toHaveURL(`/benchmarks/?c=${C}&v=1`);
  await page.goBack();
  await expect(page.locator('.applied [data-chip]')).toHaveCount(2);
  await countsMatch(page, { c: [C], em: [EM] });
  // an unknown value is a visible notice in 10's words, never silently dropped
  await ready(page, `?c=nonexistent-term&em=${EM}&v=1`);
  await expect(page.locator('[data-ignored]')).toContainText('ignored filter: c=nonexistent-term');
  await expect(page.locator('.applied [data-chip]')).toHaveCount(1);
  // a key the grammar has and this view does not apply is kept in the link and named
  await ready(page, '?q=bimanual&sort=headroom&v=1');
  await expect(page.locator('[data-unapplied]')).toContainText('q=bimanual');
  await expect(page.locator('[data-unapplied]')).toContainText('sort=headroom');
  await box(page, 'c', C).check();
  await expect(page).toHaveURL(`/benchmarks/?c=${C}&q=bimanual&sort=headroom&v=1`);
});

test('the curation-confidence indicator heads the rail, for whatever domain is filtered', async ({ page }) => {
  await ready(page);
  const note = page.locator('aside.rail > h2 + p.confidence');
  await expect(note).toHaveCount(1);
  const fams = Object.entries(taxonomy.facets.domain).filter(([id]) => !id.includes('/'));
  const unsigned = fams.filter(([, t]) => (t.reviewer_signoff ?? 'none') === 'none');
  await expect(note).toHaveAttribute('data-scope', 'all');
  await expect(note).toHaveAttribute('data-curation-confidence', unsigned.length === fams.length ? 'unreviewed' : unsigned.length === 0 ? 'reviewed' : 'partly-reviewed');
  if (unsigned.length === fams.length) await expect(note).toContainText(`any of the ${fams.length} domain families`);
  // filter by a subdomain: the indicator speaks for its family
  const sub = ROWS[0].subdomain;
  const fam = sub.split('/')[0];
  const famLabel = taxonomy.facets.domain[fam].label;
  await ready(page, `?d=${encodeURIComponent(sub)}&v=1`);
  await expect(note).toHaveAttribute('data-scope', 'filtered');
  const famSignoff = taxonomy.facets.domain[fam].reviewer_signoff ?? 'none';
  await expect(note).toContainText(famSignoff === 'none' ? `Curation confidence for ${famLabel}: unreviewed.` : `Curation confidence for ${famLabel}: signed off`);
  await expect(page.locator(`details[data-group="d"] li.term[data-term="${fam}"] details.subdomains`)).toHaveAttribute('open', '');
});

test('filter changes are announced once, politely, through one status region, debounced; the results are not live', async ({ page }) => {
  await ready(page);
  const view = page.locator('[data-browse-view]');
  await expect(view.locator('[role="status"]')).toHaveCount(1);
  await expect(view.locator('[aria-live]')).toHaveCount(0);
  const status = view.locator('[role="status"]');
  await page.waitForTimeout(800);
  await expect(status, 'the page arriving is not a change').toHaveText('');
  await status.evaluate((el) => {
    const w = window as unknown as { said: string[] };
    w.said = [];
    new MutationObserver(() => w.said.push(el.textContent ?? '')).observe(el, { childList: true, characterData: true, subtree: true });
  });
  // two changes well inside 500 ms: clicked in one task, so the test does not depend on how fast the runner is
  await page.evaluate(([c, em]) => {
    for (const [key, id] of [['c', c], ['em', em]]) {
      (document.querySelector(`details[data-group="${key}"] li.term[data-term="${id}"] > .row > input`) as HTMLInputElement).click();
    }
  }, [C, EM]);
  await expect(box(page, 'em', EM)).toBeChecked();
  await page.waitForTimeout(1500);
  const announcements = await page.evaluate(() => (window as unknown as { said: string[] }).said);
  expect(announcements).toEqual([said(expected({ c: [C], em: [EM] }).total)]);
  await expect(status).toHaveText(said(expected({ c: [C], em: [EM] }).total));
});

test('every group collapses, and a term shows its definition on hover and focus, with the full one at /taxonomy/', async ({ page }) => {
  await ready(page);
  for (const [key] of RAIL) {
    const group = page.locator(`details.group[data-group="${key}"]`);
    const was = await group.evaluate((d) => (d as HTMLDetailsElement).open);
    await group.locator(':scope > summary').click();
    await expect.poll(() => group.evaluate((d) => (d as HTMLDetailsElement).open), key).toBe(!was);
    if (was) await group.locator(':scope > summary').click();          // leave the open ones open
  }
  const t = VOCAB.get('c')!.find((x) => x.id === C)!;
  const row = page.locator(`details[data-group="c"] li.term[data-term="${C}"] > .row`);
  const gloss = row.locator(':scope > .gloss');
  await expect(gloss).toBeHidden();
  await row.locator('label').hover();
  await expect(gloss).toBeVisible();
  await expect(gloss.locator('p')).toHaveText(t.gloss!);
  await expect(row.locator('input')).toHaveAttribute('aria-describedby', (await gloss.locator('p').getAttribute('id'))!);
  const full = gloss.locator('a');
  await expect(full).toHaveAttribute('href', `/taxonomy/capability/${C}/`);
  await gloss.hover();                                                 // the definition holds under the pointer
  await expect(gloss).toBeVisible();
  expect((await page.request.get(`/taxonomy/capability/${C}/`)).status()).toBe(200);
  await page.keyboard.press('Escape');
  await expect(gloss).toBeHidden();
  // a mouse click leaves no definition open once the pointer has gone; keyboard focus opens it
  await row.locator('input').check();
  await away(page);
  await expect(gloss).toBeHidden();
  await row.locator('input').uncheck();
  await away(page);
  await page.locator('details[data-group="c"] > summary').focus();
  const input = row.locator('input');
  for (let i = 0; i < 400 && !(await input.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(input).toBeFocused();
  await expect(gloss).toBeVisible();
});

test('with no published entry the view says so: every term at zero, disabled and still there', async ({ page }) => {
  await page.route(`**${FACETS_URL}`, (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...facets, benchmarks: [] }),
  }));
  await ready(page);
  await expect(page.locator('[data-empty="unpublished"]')).toContainText('No benchmark is published yet');
  const rows = await shown(page);
  expect(rows.length).toBe(ALL_TERMS);
  for (const r of rows) {
    expect(r.count, r.key).toBe('0');
    expect(r.disabled, r.key).toBe(true);
  }
  await expect(page.locator('ol.results')).toHaveCount(0);
  await expect(page.locator('h2#browse-results-h .count')).toHaveText('(0 of 0)');
  await expect(page.locator('aside.rail > h2 + p.confidence')).toHaveCount(1);
});

test('a facets.json the view cannot read is said, and the rail stays a set of links', async ({ page }) => {
  await page.route(`**${FACETS_URL}`, (route) => route.fulfill({ status: 404, body: 'not found' }));
  await page.goto('/benchmarks/');
  await expect(page.locator('[data-browse-view]')).toHaveAttribute('data-state', 'failed');
  await expect(page.locator('[data-browse-state="failed"]')).toContainText('HTTP 404');
  await expect(page.locator('[data-browse-view] li.term > .row > a[href^="/browse/"]')).toHaveCount(ALL_TERMS);
});
