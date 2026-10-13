// site/tests/provenance.spec.ts -- P2-S3-T02 (10 V6 "The provenance drill-down"). ProvenanceDetails over
// test/fixtures/provenance-claims.json, read with JavaScript disabled (the `nojs` project, playwright.config.ts):
//
//   cd site && npx playwright test tests/provenance.spec.ts --project=nojs
//
// Done when: "With JavaScript disabled, opening the disclosure reveals the full definition list and the
// unknown-field set." The failure that guards against is a list that is not there to reveal: each row's content
// is checked hidden before the click and visible after it, field by field against the fixture the build's own
// comparability arithmetic wrote.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

interface Row {
  claim: { id: string; value: number | null; verification: string; provenance_snapshot: { source_record_id: string; retrieved_at: string } | null };
  conditions: Record<string, unknown> | null;
  comparability: { comparability_key: string; key_unknown_count: number; unknown_fields: string[]; fields_material_total: number };
  material: string[];
  key_shared_with: number;
  constructed: string | null;
}
const FIXTURE = fileURLToPath(new URL('../test/fixtures/provenance-claims.json', import.meta.url));
const ROWS = (JSON.parse(readFileSync(FIXTURE, 'utf8')) as { rows: Row[] }).rows;
const LIST = ['source', 'date-reported', 'reported-by', 'verification', 'comparability-key', 'artifact', 'provenance-snapshot',
  'conditions', 'unknown-fields'];
const PAGE = '/_fixtures/provenance';

test('the fixture covers the shapes: a full set, a weighted profile, shared keys, and an ingested row with no conditions', () => {
  const by = (id: string) => ROWS.find((r) => r.claim.id === id)!;
  expect(by('claim-7112700f8bec').comparability.unknown_fields).toEqual([]);
  expect(by('claim-728956d83bee').comparability.key_unknown_count).toBe(11);
  expect(by('claim-0b51297ad7c5').key_shared_with).toBe(4);
  const ingested = ROWS.filter((r) => r.constructed != null);
  expect(ingested.map((r) => r.claim.id)).toEqual(['claim-000000000001']);
  expect(ingested[0].conditions).toBeNull();
  expect(ingested[0].claim.provenance_snapshot).not.toBeNull();
});

for (const row of ROWS) {
  test(`${row.claim.id}: closed, the summary is the value, badge and meter; opened, the whole list and the unknown set`, async ({ page }) => {
    expect(test.info().project.use.javaScriptEnabled, 'the nojs project').toBe(false);
    await page.goto(PAGE);
    const d = page.locator(`details[data-prov="${row.claim.id}"]`);
    await expect(d).not.toHaveAttribute('open', /.*/);
    const summary = d.locator('summary');
    await expect(summary.locator('[data-prov-value]')).toHaveText(String(row.claim.value));
    await expect(summary.locator('.badge, [data-verification]').first()).toBeVisible();
    const meter = summary.locator('[data-meter]');
    await expect(meter).toHaveAttribute('data-total', String(row.comparability.fields_material_total));
    await expect(meter).toHaveAttribute('data-specified', String(row.comparability.fields_material_total - row.comparability.key_unknown_count));
    await expect(summary.locator('a')).toHaveCount(0);                                     // nothing clickable inside the summary

    const list = d.locator('.prov-list');
    await expect(list).toBeHidden();                                                      // in the DOM, collapsed
    expect(await list.locator('[data-prov-row]').count()).toBeGreaterThanOrEqual(LIST.length);
    await summary.click();                                                                // native: no script runs
    await expect(d).toHaveAttribute('open', '');
    for (const name of LIST) await expect(list.locator(`[data-prov-row="${name}"]`), name).toBeVisible();

    // the unknown fields, as a set, exactly the build's
    const set = list.locator('[data-prov-row="unknown-fields"] [data-unknown-set]');
    if (row.comparability.unknown_fields.length === 0) await expect(set).toHaveText('none');
    else expect(await set.locator('li code').allTextContents()).toEqual(row.comparability.unknown_fields);

    // every material field is listed; the unknown ones say `unknown`, in the absence token, and the rest a value
    const conds = list.locator('[data-prov-row="conditions"]');
    for (const f of row.material) {
      const item = conds.locator(`[data-cond="${f}"]`);
      await expect(item, f).toBeVisible();
      if (row.comparability.unknown_fields.includes(f)) await expect(item.locator('[data-absent="unknown"]'), f).toHaveCount(1);
      else await expect(item.locator('[data-absent]'), f).toHaveCount(0);
    }
    await expect(list.locator('[data-prov-row="comparability-key"]')).toContainText(row.comparability.comparability_key);
    await expect(list.locator('[data-prov-row="comparability-key"]')).toContainText(
      row.key_shared_with === 0 ? 'no other claim shares this key' : `${row.key_shared_with} other`);
  });
}

test('an ingested row shows its snapshot and artifact; a curated one says it was not ingested', async ({ page }) => {
  await page.goto(PAGE);
  const ingested = page.locator('details[data-prov="claim-000000000001"]');
  await ingested.locator('summary').click();
  await expect(ingested.locator('[data-prov-row="provenance-snapshot"]')).toContainText('ingested 2026-10-01 from leaderboard-row-7, raw value 0.262');
  await expect(ingested.locator('[data-prov-row="artifact"] a')).toHaveAttribute('href', /\.invalid\//);
  await expect(ingested.locator('[data-prov-row="conditions"]')).toContainText('No condition record: every material field is unknown.');
  const curated = page.locator('details[data-prov="claim-7112700f8bec"]');
  await curated.locator('summary').click();
  await expect(curated.locator('[data-prov-row="provenance-snapshot"] [data-absent="not-applicable"]')).toContainText('curated by hand');
  await expect(curated.locator('[data-prov-row="artifact"] [data-absent="not-reported"]')).toBeVisible();
});

test('the drill-down ships no JavaScript of its own', async ({ page }) => {
  const h = await (await page.request.get(PAGE)).text();
  expect([...h.matchAll(/<script\b[^>]*>/g)].map((m) => m[0])).toEqual(['<script data-prepaint>']);
});
