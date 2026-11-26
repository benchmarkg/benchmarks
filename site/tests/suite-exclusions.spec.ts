// site/tests/suite-exclusions.spec.ts -- P6-S4-T03 (11 S2 F2 "Made visible"; 10 V10 "Failure mode to avoid"). The Suite
// Builder's Excluded panel (islands/SuiteBuilder.tsx over islands/suite/exclusions.ts), in a browser, over the draft
// preview playwright.config.ts builds:
//
//   cd site && npx playwright test tests/suite-exclusions.spec.ts
//
// The ledger's verify is the Node half (`npm test -- suite.exclusions`, test/suite.exclusions.test.mjs); this file is
// the panel as a reader sees it. Done when: "A fixture containing a deprecated and a licence-incompatible entry excludes
// both with visible reasons on both the manual and AI paths." No entry of the index is deprecated today, so the pair is
// test/fixtures/suite-exclusions.json's, on the page test/fixtures/suite-exclusions.astro mounts the island on
// (/_fixtures/suite-exclusions, routed because playwright.config.ts names the fixture). The manual path is Add pressed
// for each entry. The AI accelerator is not built (P6-S5); it is to fill a starting basket (10 V10), which reaches the
// page as basket ids in its address, so its path is the basket's link opened in a browser context that never saw the
// page: the panel must read the same, word for word.
//
// On /suite/ itself, over the preview's real entries, the three rules the index has entries for today: an entry whose
// dataset licence is a Creative Commons NC licence (licence-incompatible), one whose contamination risk is high
// (known-contaminated) and one whose lineage names a successor (superseded), beside one with an open licence and one
// with no licence curated, both kept, the second named as not read. Each is chosen here, from the corpus.json and
// facets.json the server was built from (build/preview/), by this file's own reading of the fields, not by
// exclusions.ts. Around them: the basket keeps what the reader chose, the excluded entries tagged in it; removing an
// entry takes it off the panel; and the panel is the analysis pane's first.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test, type Browser, type Page } from '@playwright/test';

interface Row { id: string; name: string }
interface Rec {
  id: string;
  lifecycle?: string | null;
  data: { dataset_licence?: string | null; contamination_risk?: string; contamination_evidence?: unknown[] };
  execution?: { code_licence?: string | null };
  lineage?: { superseded_by?: string[] } | null;
}

const preview = (name: string) => JSON.parse(readFileSync(fileURLToPath(new URL(`../../build/preview/${name}`, import.meta.url)), 'utf8'));
const ROWS = (preview('facets.json') as { benchmarks: Row[] }).benchmarks;
const BY_ID = new Map(ROWS.map((r) => [r.id, r]));
const RECORDS = ((preview('corpus.json') as { entities: { benchmark: Rec[] } }).entities.benchmark).filter((b) => BY_ID.has(b.id));
const nameOf = (id: string) => BY_ID.get(id)?.name ?? id;

// this file's own reading: licence texts that are exactly an open SPDX id, or exactly a Creative Commons NC id
const OPEN = new Set(['CC-BY-4.0', 'CC-BY-SA-4.0', 'CC0-1.0', 'MIT', 'Apache-2.0', 'BSD-3-Clause']);
const NC = /^CC-BY-NC(?:-SA|-ND)?-\d\.\d$/;
const licences = (b: Rec) => [b.data.dataset_licence ?? null, b.execution?.code_licence ?? null];
const openLicensed = (b: Rec) => licences(b).every((t) => t == null || OPEN.has(t)) && licences(b).some((t) => t != null);
const settled = (b: Rec) => !['deprecated', 'retracted', 'superseded', 'contaminated'].includes(b.lifecycle ?? '');
const clean = (b: Rec) => !['high', 'confirmed'].includes(b.data.contamination_risk ?? '');
const successors = (b: Rec) => b.lineage?.superseded_by ?? [];
const pick = (what: string, ok: (b: Rec) => boolean) => {
  const b = RECORDS.find(ok);
  if (b == null) throw new Error(`the preview has no ${what} entry`);
  return b;
};
const NONCOMMERCIAL = pick('CC NC-licensed', (b) => settled(b) && clean(b) && successors(b).length === 0 && NC.test(b.data.dataset_licence ?? '')
  && (b.execution?.code_licence == null || OPEN.has(b.execution.code_licence)));
const CONTAMINATED = pick('high-risk', (b) => settled(b) && b.data.contamination_risk === 'high' && successors(b).length === 0 && openLicensed(b));
const SUPERSEDED = pick('succeeded', (b) => settled(b) && clean(b) && successors(b).length > 0 && openLicensed(b));
const KEPT = pick('open-licensed', (b) => settled(b) && clean(b) && successors(b).length === 0 && openLicensed(b));
const UNREAD = pick('unlicensed', (b) => settled(b) && clean(b) && successors(b).length === 0 && licences(b).every((t) => t == null));
const FIVE = [NONCOMMERCIAL, CONTAMINATED, SUPERSEDED, KEPT, UNREAD];
const sorted = (ids: string[]) => [...new Set(ids)].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

const ROOT = '[data-suite-builder]';
const PANEL = '[data-panel="excluded"]';
async function ready(page: Page, path: string) {
  await page.goto(path);
  await expect(page.locator(ROOT)).toHaveAttribute('data-state', 'ready');
}
/** Add `ids` the way a reader does: search for each, then press its Add. */
async function addByHand(page: Page, ids: string[]) {
  for (const id of ids) {
    await page.locator('input[data-control="q"]').fill(id);
    await page.locator(`[data-result="${id}"] button`).click();
    await expect(page.locator(`[data-basket-entry="${id}"]`)).toHaveCount(1);
  }
  await page.locator('input[data-control="q"]').fill('');
}
/** The panel's words, in a browser context that has never seen the page: how a link -- the AI accelerator's hand-over
 *  -- reads. */
async function panelFromLink(browser: Browser, url: string) {
  const fresh = await browser.newContext();
  const other = await fresh.newPage();
  await ready(other, url);
  const text = await other.locator(PANEL).innerText();
  const basket = await other.locator(ROOT).getAttribute('data-basket');
  await fresh.close();
  return { text, basket };
}

test('the preview has what these expectations read: one entry for each rule the index can fire today, and two kept', () => {
  expect(new Set(FIVE.map((b) => b.id)).size).toBe(5);
  expect(NC.test(NONCOMMERCIAL.data.dataset_licence ?? '')).toBe(true);
  expect((CONTAMINATED.data.contamination_evidence ?? []).length, 'a high risk carries its evidence (02 S11)').toBeGreaterThan(0);
});

test('on /suite/, built by hand: the panel names each excluded entry, the rule that fired and the field it read', async ({ page, browser }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await ready(page, '/suite/');
  const panel = page.locator(PANEL);
  await expect(page.locator('[data-suite-analysis] [data-panel]').first(), 'the analysis pane\'s first panel').toHaveAttribute('data-panel', 'excluded');
  await expect(panel.locator('[data-excluded-summary]')).toHaveText('The basket is empty, so nothing is excluded.');

  await addByHand(page, FIVE.map((b) => b.id));
  const ids = sorted(FIVE.map((b) => b.id));
  await expect(page.locator(ROOT), 'the basket keeps all five, as the reader chose them').toHaveAttribute('data-basket', ids.join(' '));
  expect(new URL(page.url()).searchParams.get('b')).toBe(ids.join(','));
  await expect(panel.locator('[data-excluded-summary]')).toHaveText('Excluded 3 of 5 entries because: licence-incompatible (1), superseded (1), known-contaminated (1).');

  const n = (CONTAMINATED.data.contamination_evidence ?? []).length;
  const want: [Rec, string, string][] = [
    [NONCOMMERCIAL, 'licence', `licence-incompatible: data.dataset_licence: “${NONCOMMERCIAL.data.dataset_licence}”, which allows non-commercial use only, and the suite is screened for any use`],
    [CONTAMINATED, 'contaminated', `known-contaminated: data.contamination_risk: high, on ${n} evidence ${n === 1 ? 'source' : 'sources'}`],
    [SUPERSEDED, 'superseded', `superseded: lineage.superseded_by: ${successors(SUPERSEDED).map(nameOf).join(', ')}`],
  ];
  await expect(panel.locator('[data-excluded-entry]')).toHaveCount(3);
  for (const [b, rule, reason] of want) {
    const li = panel.locator(`[data-excluded-entry="${b.id}"]`);
    await expect(li).toHaveAttribute('data-rules', rule);
    await expect(li).toHaveText(`${nameOf(b.id)} — ${reason}`);
    await expect(li.getByRole('link', { name: nameOf(b.id) })).toHaveAttribute('href', `/benchmarks/${b.id}/`);
    const entry = page.locator(`[data-basket-entry="${b.id}"]`);
    await expect(entry).toHaveAttribute('data-excluded', '');
    await expect(entry.locator('.tag')).toHaveText('excluded');
    await expect(entry.locator('.tag')).toBeVisible();
  }
  for (const b of [KEPT, UNREAD]) {
    await expect(page.locator(`[data-basket-entry="${b.id}"]`)).not.toHaveAttribute('data-excluded', '');
    await expect(panel.locator(`[data-excluded-entry="${b.id}"]`)).toHaveCount(0);
  }
  // the kept entry with no licence curated is named, not cleared in silence; the use the licence rule read for is said
  await expect(panel.locator('[data-licence-unread]')).toHaveAttribute('data-licence-unread', UNREAD.id);
  await expect(panel.locator('[data-licence-unread]')).toHaveText(`The licence rule read 1 of the 2 entries kept. No licence it recognises is curated for ${nameOf(UNREAD.id)}: kept, not cleared.`);
  await expect(panel.locator('[data-use]')).toHaveText(/screened for any use, commercial use included/);

  // the same basket from its link, as the AI accelerator will hand one over: the same panel, word for word
  const mine = await panel.innerText();
  const there = await panelFromLink(browser, page.url());
  expect(there.basket).toBe(ids.join(' '));
  expect(there.text).toBe(mine);

  // taking an excluded entry out of the basket takes it off the panel
  await page.locator(`[data-basket-entry="${SUPERSEDED.id}"] button`).click();
  await expect(panel.locator('[data-excluded-summary]')).toHaveText('Excluded 2 of 4 entries because: licence-incompatible (1), known-contaminated (1).');
  await expect(panel.locator(`[data-excluded-entry="${SUPERSEDED.id}"]`)).toHaveCount(0);
  await page.getByRole('button', { name: 'Empty the basket' }).click();
  await expect(panel.locator('[data-excluded-summary]')).toHaveText('The basket is empty, so nothing is excluded.');
  await expect(panel.locator('[data-excluded-entry]')).toHaveCount(0);
  expect(errors, 'no script error and no hydration mismatch').toEqual([]);
});

test('the ledger\'s fixture: a deprecated and a licence-incompatible entry, excluded with visible reasons by hand and from a link alike', async ({ page, browser }) => {
  const FIXTURE = '/_fixtures/suite-exclusions';
  const res = await page.request.get(FIXTURE);
  expect(res.status(), 'the fixture page is built (playwright.config.ts names suite-exclusions)').toBe(200);
  await ready(page, FIXTURE);
  const panel = page.locator(PANEL);
  await addByHand(page, ['fixture-deprecated', 'fixture-noncommercial', 'fixture-open']);
  await expect(panel.locator('[data-excluded-summary]')).toHaveText('Excluded 2 of 3 entries because: licence-incompatible (1), deprecated (1).');
  await expect(panel.locator('[data-excluded-entry="fixture-deprecated"]')).toHaveText('Fixture Deprecated Bench — deprecated: lifecycle: deprecated, the maintainer advises against use');
  await expect(panel.locator('[data-excluded-entry="fixture-noncommercial"]')).toHaveText('Fixture Non-Commercial Bench — licence-incompatible: data.dataset_licence: “CC-BY-NC-4.0”, which allows non-commercial use only, and the suite is screened for any use');
  for (const id of ['fixture-deprecated', 'fixture-noncommercial']) {
    await expect(panel.locator(`[data-excluded-entry="${id}"]`)).toBeVisible();
    await expect(page.locator(`[data-basket-entry="${id}"] .tag`)).toHaveText('excluded');
  }
  await expect(page.locator('[data-basket-entry="fixture-open"]')).not.toHaveAttribute('data-excluded', '');

  // the AI accelerator's path: the same basket, handed over as a link, in a context that never saw the page
  const mine = await panel.innerText();
  const there = await panelFromLink(browser, `${FIXTURE}?b=fixture-open,fixture-noncommercial,fixture-deprecated`);
  expect(there.basket).toBe('fixture-deprecated fixture-noncommercial fixture-open');
  expect(there.text).toBe(mine);
});
