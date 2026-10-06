// site/tests/components.spec.ts -- P2-S2-T06. The two behaviours of 09 S6 that only a browser shows, against
// /_fixtures/components (playwright.config.ts builds it). Everything else is site/test/components.test.mjs.
import { expect, test } from '@playwright/test';

const PAGE = '/_fixtures/components';

test('ChartFigure: with JavaScript off the table is the page, and there is no chart', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(PAGE);
  const fig = page.locator('[data-chart-figure]');
  await expect(fig.locator('table')).toBeVisible();
  await expect(fig.locator('details')).toHaveCount(0);
  await expect(fig.locator('svg')).toHaveCount(0);
  await context.close();
});

test('ChartFigure: hydration inserts the chart before the table and folds the table into a disclosure', async ({ page }) => {
  await page.goto(PAGE);
  const fig = page.locator('[data-chart-figure]');
  await expect(fig.locator('.chart svg')).toHaveCount(1);
  const order = await fig.evaluate((f) => [...f.children].map((c) => c.tagName.toLowerCase() + (c.className ? '.' + c.className : '')));
  expect(order).toEqual(['figcaption', 'div.chart', 'details']);
  await expect(fig.locator('details > summary')).toHaveText('Show data table (3 rows)');
  await expect(fig.locator('details > table tbody tr')).toHaveCount(3);
  await expect(fig.locator('.chart')).toHaveAttribute('aria-hidden', 'true');
  expect(await fig.locator('svg[aria-label]').count()).toBe(0);
  await fig.locator('summary').click();
  await expect(fig.locator('details > table')).toBeVisible();
});

test('ValueCell: the provenance popover opens, holds under the pointer, and Escape dismisses it without moving focus', async ({ page }) => {
  await page.goto(PAGE);
  const button = page.locator('.value-cell button');
  const pop = page.locator('.value-cell [popover]');
  await expect(pop).toBeHidden();
  await button.click();
  await expect(pop).toBeVisible();
  await expect(pop).toContainText('Reported by Example Lab');
  await expect(pop.locator('[data-absent="unknown"]')).toHaveCount(2);
  await pop.hover();                                   // hoverable: the pointer can travel into it
  await expect(pop).toBeVisible();
  await page.keyboard.press('Escape');                 // dismissible without moving focus
  await expect(pop).toBeHidden();
  await expect(button).toBeFocused();
});

test('the inventory page carries no script but the toggle and the chart', async ({ request }) => {
  const html = await (await request.get(PAGE)).text();
  const modules = [...html.matchAll(/<script type="module" src="([^"]+)"/g)].map((m) => m[1]);
  expect(modules.every((s) => /ThemeToggle|ChartFigure/.test(s))).toBe(true);
});
