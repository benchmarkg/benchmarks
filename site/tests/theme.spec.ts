// site/tests/theme.spec.ts -- P2-S2-T07. The three-state theme toggle, the pre-paint script and the ECharts
// re-init (09 S9, S12.2), against /_fixtures/theme (playwright.config.ts builds it).
//
// DONE WHEN: "All three states persist, there is no theme flash on load in either scheme, and ECharts re-inits
// on a prefers-color-scheme change." The flash is the failure case the task's verification names: a reader
// whose stored choice disagrees with the OS. It is checked where it happens -- the theme <html> carries at the
// moment <body> is created, before anything can paint -- and again with every module script blocked, so only
// the inline pre-paint script can be what set it.
import { expect, test, type Browser, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

type Theme = 'light' | 'dark';
type Choice = 'system' | Theme;
const PAGE = '/_fixtures/theme';
const KEY = 'uaibi-theme';
const tokens = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/tokens.json', import.meta.url)), 'utf8'));
// The built CSS is minified (oklch(99% .003 250)), so a colour is compared by its numbers, not its text.
const nums = (s: string) => (s.match(/\d*\.?\d+/g) ?? []).map(Number).join(',');
const BG: Record<Theme, string> = { light: nums(tokens.themes.light['c-bg'].oklch), dark: nums(tokens.themes.dark['c-bg'].oklch) };
const MUTED: Record<Theme, string> = { light: tokens.themes.light['c-ink-muted'].hex, dark: tokens.themes.dark['c-ink-muted'].hex };
const resolve = (c: Choice, os: Theme): Theme => (c === 'system' ? os : c);

/** The theme the CSS shows: which theme's --c-bg the page resolved. */
async function shown(page: Page): Promise<Theme | string> {
  const bg = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--c-bg').trim());
  return nums(bg) === BG.light ? 'light' : nums(bg) === BG.dark ? 'dark' : bg;
}

async function open(browser: Browser, os: Theme, stored?: Theme) {
  const context = await browser.newContext({ colorScheme: os });
  if (stored) await context.addInitScript(([k, v]) => { if (!sessionStorage.getItem('seeded')) { localStorage.setItem(k, v); sessionStorage.setItem('seeded', '1'); } }, [KEY, stored]);
  // Record the theme attribute at the moment <body> is inserted: nothing can paint before that.
  await context.addInitScript(() => {
    new MutationObserver((_, obs) => {
      if (document.body) {
        (window as any).__atBody = document.documentElement.getAttribute('data-theme');
        obs.disconnect();
      }
    }).observe(document, { childList: true, subtree: true });
  });
  const page = await context.newPage();
  return { context, page };
}

const radio = (page: Page, c: Choice) => page.locator(`[data-theme-toggle] input[value="${c}"]`);

// ---- the default -------------------------------------------------------------------------------------------

for (const os of ['light', 'dark'] as Theme[]) {
  test(`with no choice stored it is system, and follows a ${os} OS`, async ({ browser }) => {
    const { context, page } = await open(browser, os);
    await page.goto(PAGE);
    await expect(page.locator('[data-theme-toggle]')).toBeVisible();
    await expect(radio(page, 'system')).toBeChecked();
    expect(await page.evaluate(() => document.documentElement.hasAttribute('data-theme'))).toBe(false);
    expect(await shown(page)).toBe(os);
    await context.close();
  });
}

// ---- all three states persist ------------------------------------------------------------------------------

for (const os of ['light', 'dark'] as Theme[]) {
  for (const choice of ['light', 'dark', 'system'] as Choice[]) {
    test(`${choice} persists across a reload under a ${os} OS`, async ({ browser }) => {
      const { context, page } = await open(browser, os);
      await page.goto(PAGE);
      // Start from the other forced state, so choosing system has something to clear.
      const other: Theme = choice === 'dark' ? 'light' : 'dark';
      await radio(page, other).check();
      await radio(page, choice).check();
      expect(await shown(page)).toBe(resolve(choice, os));
      await page.reload();
      await expect(radio(page, choice)).toBeChecked();
      expect(await shown(page)).toBe(resolve(choice, os));
      expect(await page.evaluate((k) => localStorage.getItem(k), KEY)).toBe(choice === 'system' ? null : choice);
      expect(await page.evaluate(() => (window as any).__atBody)).toBe(choice === 'system' ? null : choice);
      await context.close();
    });
  }
}

test('a stored value that is not one of the three is read as system', async ({ browser }) => {
  const { context, page } = await open(browser, 'dark');
  await page.goto(PAGE);
  await page.evaluate((k) => localStorage.setItem(k, 'sepia'), KEY);
  await page.reload();
  await expect(radio(page, 'system')).toBeChecked();
  expect(await shown(page)).toBe('dark');
  await context.close();
});

// ---- no flash on load: the failure case --------------------------------------------------------------------

for (const [os, stored] of [['light', 'dark'], ['dark', 'light']] as [Theme, Theme][]) {
  test(`a stored ${stored} choice under a ${os} OS is on <html> before <body> exists`, async ({ browser }) => {
    const { context, page } = await open(browser, os, stored);
    await page.goto(PAGE);
    expect(await page.evaluate(() => (window as any).__atBody)).toBe(stored);
    expect(await shown(page)).toBe(stored);
    await context.close();
  });

  test(`a stored ${stored} choice under a ${os} OS holds with every module script blocked`, async ({ browser }) => {
    const { context, page } = await open(browser, os, stored);
    await page.route('**/_astro/*.js', (route) => route.abort());
    await page.goto(PAGE);
    expect(await page.evaluate(() => (window as any).__atBody)).toBe(stored);
    expect(await shown(page)).toBe(stored);
    await context.close();
  });
}

test('the pre-paint script is the first script in <head>, inline, and the only classic script', async ({ request }) => {
  const html = await (await request.get(PAGE)).text();
  const head = html.slice(html.indexOf('<head>'), html.indexOf('</head>'));
  const scripts = [...html.matchAll(/<script\b([^>]*)>/g)].map((m) => m[1]);
  const classic = scripts.filter((a) => !/type="module"/.test(a));
  expect(classic).toHaveLength(1);
  expect(classic[0]).toContain('data-prepaint');
  expect(classic[0]).not.toContain('src=');
  expect(head.indexOf('data-prepaint')).toBeGreaterThan(0);
  expect(head.indexOf('data-prepaint')).toBeLessThan(head.search(/<link[^>]+stylesheet|<style/));
});

test('without JavaScript the toggle is not shown and the page follows the OS', async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: 'dark', javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(PAGE);
  await expect(page.locator('[data-theme-toggle]')).toBeHidden();
  expect(await shown(page)).toBe('dark');
  await context.close();
});

// ---- ECharts -----------------------------------------------------------------------------------------------

test('the server-rendered chart is neutral: currentColor only, no colour of either theme', async ({ request }) => {
  const html = await (await request.get(PAGE)).text();
  const svg = html.match(/<div[^>]*data-chart[^>]*>([\s\S]*?<\/svg>)/)![1];
  const paints = new Set([...svg.matchAll(/(?:fill|stroke)="([^"]*)"/g)].map((m) => m[1]));
  expect([...paints].sort()).toEqual(['currentColor', 'none']);
  for (const t of ['light', 'dark'] as Theme[]) {
    for (const v of Object.values<any>(tokens.themes[t])) expect(svg.toLowerCase()).not.toContain(v.hex);
  }
});

async function chart(page: Page) {
  const el = page.locator('[data-chart]');
  return {
    theme: await el.getAttribute('data-chart-theme'),
    inits: Number(await el.getAttribute('data-chart-inits')),
    fills: await el.evaluate((e) => [...e.querySelectorAll('[fill]')].map((n) => n.getAttribute('fill')!.toLowerCase())),
  };
}

test('ECharts hydrates in the page theme and re-inits on a prefers-color-scheme change', async ({ browser }) => {
  const { context, page } = await open(browser, 'light');
  await page.goto(PAGE);
  await expect(page.locator('[data-chart]')).toHaveAttribute('data-chart-inits', '1');
  let c = await chart(page);
  expect(c.theme).toBe('light');
  expect(c.fills).toContain(MUTED.light);
  expect(c.fills).not.toContain('currentcolor');               // the neutral SVG was swapped out

  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('[data-chart]')).toHaveAttribute('data-chart-inits', '2');
  c = await chart(page);
  expect(c.theme).toBe('dark');
  expect(c.fills).toContain(MUTED.dark);
  expect(c.fills).not.toContain(MUTED.light);
  expect(await shown(page)).toBe('dark');

  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('[data-chart]')).toHaveAttribute('data-chart-inits', '3');
  expect((await chart(page)).theme).toBe('light');
  await context.close();
});

test('the toggle re-inits ECharts, and a forced choice ignores the OS changing', async ({ browser }) => {
  const { context, page } = await open(browser, 'light');
  await page.goto(PAGE);
  await expect(page.locator('[data-chart]')).toHaveAttribute('data-chart-inits', '1');
  await radio(page, 'dark').check();
  await expect(page.locator('[data-chart]')).toHaveAttribute('data-chart-theme', 'dark');
  expect((await chart(page)).inits).toBe(2);

  await page.emulateMedia({ colorScheme: 'dark' });              // already dark: nothing to redraw
  await page.emulateMedia({ colorScheme: 'light' });             // forced dark: the OS no longer decides
  await page.waitForTimeout(200);
  const c = await chart(page);
  expect([c.theme, c.inits]).toEqual(['dark', 2]);
  expect(await shown(page)).toBe('dark');
  await context.close();
});
