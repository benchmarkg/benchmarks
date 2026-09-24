// tests/e2e/feed.spec.ts -- P4-S4-T06: the feed formats and the /feed/ page (10 V8).
//
// Runs against the site built from tests/e2e/fixtures/feed-events.json (playwright.config.ts).
// The failure case the task's done_when names -- a machine-ingested event in the default feed --
// is asserted directly, on every default-feed surface, against a fixture that carries one.
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

interface Ev { id: string; type: string; entity: string; date: string; families: string[];
  organisations: string[]; machine_ingested?: boolean; publishable?: boolean }

const events: Ev[] = JSON.parse(readFileSync(join(__dirname, 'fixtures', 'feed-events.json'), 'utf8'));
const published = events.filter((e) => e.publishable !== false);
const human = published.filter((e) => !e.machine_ingested);
const machine = published.filter((e) => e.machine_ingested);
const draft = events.filter((e) => e.publishable === false);
const ids = (es: Ev[]) => es.map((e) => e.id);

async function atom(page: Page, path: string) {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  const xml = await res.text();
  // Well-formed, and an Atom document -- checked by a real XML parser, in the browser.
  await page.goto('about:blank');
  const root = await page.evaluate((text) => {
    const doc = new DOMParser().parseFromString(text, 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) return 'parsererror';
    return `${doc.documentElement.namespaceURI} ${doc.documentElement.localName}`;
  }, xml);
  expect(root, path).toBe('http://www.w3.org/2005/Atom feed');
  return [...xml.matchAll(/<id>urn:uaibi:event:(ev-[0-9a-f]+)<\/id>/g)].map((m) => m[1]);
}

test.beforeAll(() => {
  // A server left running from a live-data build would make every assertion below vacuous.
  expect(machine.length, 'fixture must carry a machine-ingested event').toBeGreaterThan(0);
  expect(human.some((e) => e.type === 'correction'), 'fixture must carry a correction').toBe(true);
});

test('the default Atom feed is every published, human-curated event, newest first', async ({ page }) => {
  expect(await atom(page, '/feed.xml')).toEqual(ids(human));
});

test('no machine-ingested event appears in the default feed, anywhere', async ({ page }) => {
  const bulk = ids(machine);
  const defaultAtom = await atom(page, '/feed.xml');
  const json = await (await page.request.get('/feed.json')).json();
  const jsonIds = json.items.map((i: { _uaibi: Ev }) => i._uaibi.id);
  await page.goto('/feed/');
  const pageIds = await page.locator('#feed-events > li').evaluateAll((lis) => lis.map((li) => li.getAttribute('data-event')));
  for (const id of bulk) {
    expect(defaultAtom).not.toContain(id);
    expect(jsonIds).not.toContain(id);
    expect(pageIds).not.toContain(id);
    for (const fam of machine.find((e) => e.id === id)!.families) {
      expect(await atom(page, `/feed/${fam}.xml`)).not.toContain(id);
    }
  }
  expect(await atom(page, '/feed/ingest.xml')).toEqual(bulk); // it lives here instead
});

test('the JSON Feed 1.1 carries the same events as the Atom feed', async ({ page }) => {
  const res = await page.request.get('/feed.json');
  expect(res.status()).toBe(200);
  const json = await res.json();
  expect(json.version).toBe('https://jsonfeed.org/version/1.1');
  expect(typeof json.title).toBe('string');
  expect(json.items.map((i: { id: string }) => i.id)).toEqual(human.map((e) => `urn:uaibi:event:${e.id}`));
  for (const item of json.items) {
    expect(item.date_published).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    expect(item.content_text.length).toBeGreaterThan(0);
  }
});

test('each domain family has its own feed, and an empty family is still a valid feed', async ({ page }) => {
  for (const fam of ['code', 'robotics-embodiment']) {
    expect(await atom(page, `/feed/${fam}.xml`)).toEqual(ids(human.filter((e) => e.families.includes(fam))));
  }
  expect(await atom(page, '/feed/language.xml')).toEqual([]);
});

test('the corrections feed is separately subscribable and holds only corrections', async ({ page }) => {
  expect(await atom(page, '/feed/corrections.xml')).toEqual(ids(human.filter((e) => e.type === 'correction')));
  await page.goto('/feed/');
  await expect(page.locator('a[data-test="corrections-feed"]')).toHaveAttribute('href', '/feed/corrections.xml');
  await expect(page.locator('link[rel="alternate"][href="/feed/corrections.xml"]')).toHaveCount(1);
});

test('an unverified draft is announced nowhere', async ({ page }) => {
  expect(draft.length).toBeGreaterThan(0);
  const everywhere = [...await atom(page, '/feed.xml'), ...await atom(page, '/feed/code.xml'),
                      ...await atom(page, '/feed/ingest.xml')];
  for (const id of ids(draft)) expect(everywhere).not.toContain(id);
});

test('the feed page is reverse-chronological', async ({ page }) => {
  await page.goto('/feed/');
  const dates = await page.locator('#feed-events > li time').evaluateAll((ts) => ts.map((t) => t.getAttribute('datetime')!));
  expect(dates).toEqual(human.map((e) => e.date));
  expect([...dates].sort().reverse()).toEqual(dates);
});

test('the feed page filters by event type, domain and organisation', async ({ page }) => {
  await page.goto('/feed/');
  const visible = () => page.locator('#feed-events > li:not([hidden])').evaluateAll((lis) => lis.map((li) => li.getAttribute('data-event')));
  await page.selectOption('select[name="type"]', 'correction');
  expect(await visible()).toEqual(ids(human.filter((e) => e.type === 'correction')));
  await page.selectOption('select[name="type"]', '');
  await page.selectOption('select[name="family"]', 'robotics-embodiment');
  expect(await visible()).toEqual(ids(human.filter((e) => e.families.includes('robotics-embodiment'))));
  await page.selectOption('select[name="family"]', '');
  await page.selectOption('select[name="org"]', 'org-alpha-lab');
  expect(await visible()).toEqual(ids(human.filter((e) => e.organisations.includes('org-alpha-lab'))));
  await expect(page.locator('output[name="count"]')).toHaveText(
    `${human.filter((e) => e.organisations.includes('org-alpha-lab')).length} of ${human.length} events`);
});

test.describe('without JavaScript', () => {
  test.use({ javaScriptEnabled: false });

  test('the page lists every event and hides the filter form it cannot run', async ({ page }) => {
    await page.goto('/feed/');
    await expect(page.locator('#feed-events > li')).toHaveCount(human.length);
    await expect(page.locator('#feed-filters')).toBeHidden();
  });
});
