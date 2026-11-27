// tests/e2e/comparability-states.spec.ts -- P3-S10-T04: the three comparability UI states (04 S8 "What the UI does with
// it"; 10 V5; 09 Rule 2, S6.8), where the site shows claims together: each benchmark page's claims, one comparison per
// metric (site/src/views/BenchmarkDetail.astro section 10, site/src/lib/comparability.ts, ComparabilityBanner.astro).
//
//   npx playwright test tests/e2e/comparability-states.spec.ts
//
// Runs against the site built from the draft preview with build/e2e-claims/'s claims artifacts (playwright.config.ts):
// the preview's real curated claims, which already hold all three states (on 2026-11-26: one key with nothing unknown
// on OC20's IS2RE energy MAE; one key with unknown fields on SciCode, LIBERO and BEHAVIOR-1K; different keys on most
// other groups; the first test fails if one disappears), plus the constructed rows
// tests/e2e/fixtures/make_claims_fixture.py adds, and its derived/comparability.json
// recomputed by the stage's own code over them. Every page is read with JavaScript disabled: the benchmark page is a
// citation target that ships none (08 S4.3).
//
// The expectation is computed here from the artifacts, not from the site's module: a group's state is its number of
// comparability keys and whether any of its claims has key_unknown_count above zero, and its diff the material rows
// derived/comparability.json holds for it. A page is then audited against it (`audit`, run in the browser on the HTML as
// served, or as doctored):
//   - every group has exactly one comparison, in the state its data gives, counting all its claims; every claim is in
//     exactly one plot, so none is dropped silently, and no plot holds claims of two condition sets;
//   - a plot of claims sharing a key with unknown material fields sits behind a persistent banner (before it, in the
//     same disclosure, with no control that dismisses or hides it) naming exactly the unknown fields of each claim;
//     claims agreeing only in their ignorance are never shown as confirmed comparable, and a comparable plot is silent;
//   - a group spanning keys has the field-by-field diff instead of one chart: exactly the material fields that differ,
//     each set's cell its claims' value (unknown and an answered "none" told apart), and the count of claims a
//     restriction to one condition set drops, shown in the control.
// Done when: "Agreement in ignorance is never presented as confirmed comparability, and no claim is ever dropped silently
// to make a chart look clean." The failure cases are checked as failures: real pages are audited again doctored -- the
// unknowns banner taken out, the state relabelled comparable, a claim taken out of its plot, two sets merged into one
// plot, the dropped count taken out, a field taken out of the banner -- and each must be reported.
//
// The banners sit in section 10, which is collapsed by default, so the accessibility harness (site/tests/a11y.spec.ts,
// which reads pages as they load) never sees them open: the last test runs axe-core at the harness's WCAG 2.2 AA tags
// over section 10 opened, on one page per state, light and dark.
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test.use({ javaScriptEnabled: false });

interface Row {
  claim: { id: string; system: string; benchmark: string; metric: string; value: number | null; notes?: string | null };
  comparability: { comparability_key: string; key_unknown_count: number; unknown_fields: string[] };
}
interface DiffRow { a: string; b: string; field: string; a_val: unknown; b_val: unknown; severity: 'material' | 'informative' }
interface DiffGroup { benchmark: string; metric: string; claims: number; keys: number; diff_status: string; rows: DiffRow[] | null }
type State = 'single' | 'comparable' | 'possibly-comparable' | 'not-comparable';
/** One (benchmark, metric) group as the artifacts say it must render. */
interface Want {
  benchmark: string;
  metric: string;
  state: State;
  claims: { id: string; key: string; unknown: string[] }[];
  fields: Record<string, Record<string, unknown>>;     // material field that differs -> claim id -> its value
  deferred: boolean;
}
type Doctor = 'drop-banner' | 'relabel' | 'drop-claim' | 'merge-sets' | 'hide-count' | 'short-banner';

const ROOT = join(__dirname, '..', '..');
const DIR = join(ROOT, 'build', 'e2e-claims');                  // make_claims_fixture.py --out, playwright.config.ts
const family = (ref: string) => ref.split('@', 1)[0];

let memo: { rows: Row[]; wants: Want[]; published: Set<string> } | undefined;
/** The artifacts the server was built from, read when a test needs them: the webServer writes them first. */
function fixture() {
  if (memo) return memo;
  const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
  const rows = (read(join(DIR, 'claims.json')) as { claims: Row[] }).claims;
  const diff = read(join(DIR, 'derived', 'comparability.json')) as { groups: DiffGroup[] };
  const corpus = read(join(ROOT, 'build', 'preview', 'corpus.json')) as { entities: { benchmark: { id: string }[] } };
  const by = new Map<string, Row[]>();
  for (const r of rows) {
    const k = `${family(r.claim.benchmark)} ${r.claim.metric}`;
    by.set(k, [...(by.get(k) ?? []), r]);
  }
  const wants: Want[] = [];
  for (const g of diff.groups) {
    const members = by.get(`${g.benchmark} ${g.metric}`) ?? [];
    expect(members.length, `${g.benchmark} ${g.metric}: comparability.json counts claims.json's claims`).toBe(g.claims);
    const claims = members.map((r) => ({ id: r.claim.id, key: r.comparability.comparability_key, unknown: r.comparability.unknown_fields }));
    const keys = new Set(claims.map((c) => c.key)).size;
    const state: State = claims.length < 2 ? 'single' : keys > 1 ? 'not-comparable'
      : members.some((r) => r.comparability.key_unknown_count > 0) ? 'possibly-comparable' : 'comparable';
    const fields: Want['fields'] = {};
    for (const d of g.rows ?? []) {
      if (d.severity !== 'material') continue;
      fields[d.field] = { ...(fields[d.field] ?? {}), [d.a]: d.a_val, [d.b]: d.b_val };
    }
    wants.push({ benchmark: g.benchmark, metric: g.metric, state, claims, fields, deferred: g.diff_status === 'deferred' });
  }
  expect(wants.reduce((n, w) => n + w.claims.length, 0), 'every claims.json row is in a group').toBe(rows.length);
  memo = { rows, wants, published: new Set(corpus.entities.benchmark.map((b) => b.id)) };
  return memo;
}

interface Audit { problems: string[]; comparisons: number; plots: number; banners: number; diffs: number }

/** What is wrong with one benchmark page's comparisons against `wants` (its groups), read from its HTML in the browser
 *  (a DOMParser document, so a doctored copy is audited exactly as the page is). `doctor` first changes the document the
 *  way a view that hid a problem would (the failure cases), on the comparison of `target`'s metric. */
function audit({ html, wants, doctor, target }: { html: string; wants: Want[]; doctor: Doctor | null; target: string | null }): Audit {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const problems: string[] = [];
  const section = doc.querySelector('details[data-section="10"]');
  const ids = (el: Element) => [...el.querySelectorAll('ul[data-claims] > li[data-claim]')].map((li) => li.getAttribute('data-claim') ?? '');
  const show = (v: unknown): string => (Array.isArray(v) ? `[${v.map(show).join(', ')}]`
    : v !== null && typeof v === 'object' ? Object.entries(v as Record<string, unknown>).filter(([, x]) => x != null).map(([k, x]) => `${k} ${show(x)}`).join(', ') || '{}'
      : String(v));

  // ---- the failure cases: the page as a view that hides the problem would render it
  const hit = section?.querySelector(`[data-comparison="${target}"]`);
  if (doctor != null && hit == null) problems.push(`nothing to doctor: no comparison of ${target}`);
  if (doctor != null && hit != null) {
    if (doctor === 'drop-banner') hit.querySelectorAll('[data-comparability-unknown]').forEach((b) => b.remove());
    if (doctor === 'relabel') {
      hit.setAttribute('data-comparison-state', 'comparable');
      hit.querySelectorAll('[data-comparability-unknown]').forEach((b) => b.remove());
    }
    if (doctor === 'drop-claim') hit.querySelector('ul[data-claims] > li[data-claim]')?.remove();
    if (doctor === 'merge-sets') {
      const sets = [...hit.querySelectorAll('[data-set]')];
      const into = sets[0].querySelector('ul[data-claims]')!;
      for (const s of sets.slice(1)) {
        s.querySelectorAll('ul[data-claims] > li[data-claim]').forEach((li) => into.append(li));
        s.remove();
      }
      hit.querySelectorAll('[data-comparability], [data-comparability-unknown]').forEach((b) => b.remove());
      hit.setAttribute('data-comparison-state', 'comparable');
    }
    if (doctor === 'hide-count') {
      const a = hit.querySelector('a[data-action="restrict"]');
      a?.removeAttribute('data-dropped');
      if (a != null) a.textContent = 'Restrict to one condition set';
    }
    if (doctor === 'short-banner') hit.querySelector('[data-comparability-unknown] tr[data-unknown-claim] [data-unknown-field]')?.remove();
  }

  // ---- the audit
  const blocks = [...(section?.querySelectorAll('[data-comparison]') ?? [])];
  let plots = 0;
  let banners = 0;
  let diffs = 0;
  for (const w of wants) {
    const where = `${w.benchmark} ${w.metric}`;
    const found = blocks.filter((b) => b.getAttribute('data-comparison') === w.metric);
    if (found.length !== 1) {
      problems.push(`${where}: ${found.length} comparisons of its ${w.claims.length} claims, not one: ${found.length === 0 ? 'all dropped silently' : 'shown twice'}`);
      continue;
    }
    const b = found[0];
    const byId = new Map(w.claims.map((c) => [c.id, c]));
    const state = b.getAttribute('data-comparison-state');
    if (state !== w.state) problems.push(`${where}: shown as ${state}, but its keys and unknowns make it ${w.state}`);
    if (b.getAttribute('data-claims-total') !== String(w.claims.length)) {
      problems.push(`${where}: counts ${b.getAttribute('data-claims-total')} claims, of the ${w.claims.length} it has`);
    }
    const listed = ids(b);
    for (const c of w.claims) {
      const n = listed.filter((x) => x === c.id).length;
      if (n === 0) problems.push(`${where}: ${c.id} is dropped silently, in no plot and counted nowhere`);
      if (n > 1) problems.push(`${where}: ${c.id} is plotted ${n} times`);
    }
    for (const id of listed) if (!byId.has(id)) problems.push(`${where}: plots ${id}, which is not one of its claims`);

    // each plot one condition set; one with unknowns behind its banner, one without silent
    for (const p of b.querySelectorAll('[data-set]')) {
      const label = p.getAttribute('data-set');
      const list = p.querySelector(':scope > ul[data-claims]');
      if (list == null) {
        problems.push(`${where}: set ${label} has no plot of its claims`);
        continue;
      }
      plots += 1;
      const members = ids(p).map((id) => byId.get(id)).filter((c): c is Want['claims'][number] => c != null);
      const keys = new Set(members.map((c) => c.key));
      if (keys.size > 1) problems.push(`${where}: set ${label} plots claims of ${keys.size} condition sets together`);
      const banner = p.querySelector(':scope > [data-comparability-unknown]');
      const ignorant = members.filter((c) => c.unknown.length > 0);
      if (members.length > 1 && ignorant.length > 0) {
        if (banner == null) {
          problems.push(`${where}: set ${label} presents ${members.length} claims as comparable while ${[...new Set(ignorant.flatMap((c) => c.unknown))].join(', ')} `
            + 'is unknown on them: agreement in ignorance shown as confirmed comparability');
          continue;
        }
        banners += 1;
        for (const c of members) {
          const tr = banner.querySelector(`tr[data-unknown-claim="${c.id}"]`);
          const named = [...(tr?.querySelectorAll('[data-unknown-field]') ?? [])].map((e) => e.getAttribute('data-unknown-field'));
          if (JSON.stringify(named) !== JSON.stringify(c.unknown)) {
            problems.push(`${where}: the banner names [${named.join(', ')}] unknown on ${c.id}, which leaves [${c.unknown.join(', ')}] unknown`);
          }
        }
        if (banner.querySelector('button, details, dialog, [hidden]') != null || banner.hasAttribute('hidden')) {
          problems.push(`${where}: set ${label}'s banner can be dismissed or hidden, so it is not persistent`);
        }
        if (banner.closest('details') !== list.closest('details')) problems.push(`${where}: set ${label}'s banner is in another disclosure than its plot`);
        if (!(banner.compareDocumentPosition(list) & 4)) problems.push(`${where}: set ${label}'s banner comes after its plot`);   // 4: FOLLOWING
      } else if (banner != null) {
        problems.push(`${where}: set ${label} carries an unknowns banner, but nothing it plots together is unknown`);
      }
    }
    if (w.state === 'comparable' && b.querySelector('[data-comparability], [data-comparability-unknown]') != null) {
      problems.push(`${where}: one key and nothing unknown is plotted silently, but carries a banner`);
    }

    // different keys: the diff instead of one chart, and the dropped count
    const diff = b.querySelector(':scope > [data-comparability]');
    const keys = [...new Set(w.claims.map((c) => c.key))];
    if (keys.length < 2) {
      if (diff != null) problems.push(`${where}: one condition set, but a diff`);
      continue;
    }
    if (diff == null) {
      problems.push(`${where}: spans ${keys.length} condition sets with no field-by-field diff`);
      continue;
    }
    diffs += 1;
    if (!(diff.compareDocumentPosition(b.querySelector('[data-set]')!) & 4)) problems.push(`${where}: the diff comes after the plots`);
    if (!w.deferred) {
      const rows = [...diff.querySelectorAll('tr[data-diff-field]')];
      const named = rows.map((r) => r.getAttribute('data-diff-field') ?? '').sort();
      const differ = Object.keys(w.fields).sort();
      if (JSON.stringify(named) !== JSON.stringify(differ)) problems.push(`${where}: the diff names [${named.join(', ')}], but its claims differ in [${differ.join(', ')}]`);
      const cols = [...diff.querySelectorAll('thead th[data-set-col]')].map((th) => th.getAttribute('data-set-col'));
      for (const r of rows) {
        const field = r.getAttribute('data-diff-field') ?? '';
        const cells = [...r.querySelectorAll('td')];
        cols.forEach((label, i) => {
          const one = b.querySelector(`[data-set="${label}"] ul[data-claims] > li[data-claim]`)?.getAttribute('data-claim') ?? '';
          const v = w.fields[field]?.[one];
          const kind = v === '?' ? 'unknown' : v === null ? 'none' : 'value';
          const c = cells[i];
          const ok = c != null && c.getAttribute('data-cell') === kind
            && (kind !== 'unknown' || c.querySelector('[data-absent="unknown"]') != null)
            && (kind !== 'value' || (c.textContent ?? '').trim() === show(v));
          if (!ok) problems.push(`${where}: set ${label}'s ${field} reads "${(c?.textContent ?? '').trim()}", where its claims have ${JSON.stringify(v)}`);
        });
      }
    }
    const largest = Math.max(...keys.map((k) => w.claims.filter((c) => c.key === k).length));
    const drops = w.claims.length - largest;
    const restrict = diff.querySelector('a[data-action="restrict"]');
    const said = (restrict?.textContent ?? '').replace(/\s+/g, ' ');
    if (restrict == null || restrict.getAttribute('data-dropped') !== String(drops) || !said.includes(`(${drops} of ${w.claims.length} claims dropped)`)) {
      problems.push(`${where}: restricting it to one condition set drops ${drops} of ${w.claims.length} claims, and the control does not say so`);
    }
    if (diff.querySelector('a[data-action="proceed"]') == null) problems.push(`${where}: no way to proceed with every affected cell flagged`);
  }
  for (const b of blocks) {
    if (!wants.some((w) => w.metric === b.getAttribute('data-comparison'))) problems.push(`a comparison of ${b.getAttribute('data-comparison')}, which no claim here has`);
  }
  return { problems, comparisons: blocks.length, plots, banners, diffs };
}

async function html(page: Page, path: string): Promise<string> {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
}
async function audited(page: Page, body: string, wants: Want[], doctor: Doctor | null = null, target: string | null = null) {
  return page.evaluate(audit, { html: body, wants, doctor, target });
}
const onPage = (wants: Want[], benchmark: string) => wants.filter((w) => w.benchmark === benchmark);
/** The condition sets of a group by key, largest first, as the claims fall. */
const setsOf = (w: Want) => [...new Set(w.claims.map((c) => c.key))].map((k) => w.claims.filter((c) => c.key === k)).sort((a, b) => b.length - a.length);
/** The sets of a group whose claims are plotted together while agreeing only in their ignorance. */
const ignorantSets = (w: Want) => setsOf(w).filter((set) => set.length > 1 && set.some((c) => c.unknown.length > 0));
/** The first group in a state, by benchmark then metric; `inner` asks for a refused group with a set of unknowns. */
function first(state: State, inner = false): Want {
  const { wants, published } = fixture();
  const hit = wants.filter((w) => published.has(w.benchmark) && w.state === state).find((w) => !inner || ignorantSets(w).length > 0);
  expect(hit, `a ${state} group${inner ? ' with a set of possibly comparable claims' : ''} in the fixture`).toBeDefined();
  return hit!;
}
const benchmarkPath = (w: Want) => `/benchmarks/${w.benchmark}/`;
async function openClaims(page: Page, w: Want) {
  await page.goto(benchmarkPath(w));
  await page.locator('details[data-section="10"] > summary').click();          // native: no script runs
  return page.locator(`details[data-section="10"] [data-comparison="${w.metric}"]`);
}

test.beforeAll(async ({ request }) => {
  const f = fixture();
  expect((await request.get('/claims/claim-e2e000000001/')).status(), 'the server on the baseURL was built from build/e2e-claims (playwright.config.ts)').toBe(200);
  const constructed = f.rows.filter((r) => r.claim.id.startsWith('claim-e2e'));
  for (const r of constructed) expect(r.claim.notes ?? '', `${r.claim.id} says it is constructed`).toMatch(/^Constructed by tests\/e2e\/fixtures\/make_claims_fixture\.py/);
});

test('the preview claims hold all three states, so each is checked against real records', () => {
  const { wants } = fixture();
  // counted over groups with no constructed claim, so no state is there only because the fixture made it
  const count = (s: State) => wants.filter((w) => w.state === s && !w.claims.some((c) => c.id.startsWith('claim-e2e'))).length;
  expect(count('comparable'), 'one key, nothing unknown').toBeGreaterThan(0);
  expect(count('possibly-comparable'), 'one key, unknowns').toBeGreaterThan(0);
  expect(count('not-comparable'), 'different keys').toBeGreaterThan(0);
  first('not-comparable', true);
  // the case 04 S8 names: claims sharing a key only because they leave the same fields unknown
  const ignorant = first('possibly-comparable');
  expect(ignorant.claims.every((c) => c.unknown.length > 0 && c.key === ignorant.claims[0].key)).toBe(true);
});

test('every benchmark page: each metric\'s claims in the state their keys and unknowns give, none dropped', async ({ page }) => {
  test.setTimeout(300_000);
  const { wants, published } = fixture();
  const pages = [...new Set(wants.map((w) => w.benchmark))].filter((b) => published.has(b));
  expect(pages.length).toBeGreaterThan(20);
  await page.goto('about:blank');
  const total = { comparisons: 0, plots: 0, banners: 0, diffs: 0 };
  for (const b of pages) {
    const a = await audited(page, await html(page, `/benchmarks/${b}/`), onPage(wants, b));
    expect(a.problems, b).toEqual([]);
    expect(a.comparisons, b).toBe(onPage(wants, b).length);
    for (const k of Object.keys(total) as (keyof typeof total)[]) total[k] += a[k];
  }
  const refused = wants.filter((w) => w.state === 'not-comparable');
  expect(total.diffs, 'a diff for every refused group').toBe(refused.length);
  expect(total.banners, 'a banner over every plot of claims that agree in ignorance').toBe(wants.reduce((n, w) => n + ignorantSets(w).length, 0));
});

test('state 1: one key and nothing unknown, plotted together silently', async ({ page }) => {
  const w = first('comparable');
  const block = await openClaims(page, w);
  await expect(block).toHaveAttribute('data-comparison-state', 'comparable');
  await expect(block.locator('[data-comparability], [data-comparability-unknown]')).toHaveCount(0);
  await expect(block.locator('[data-set]')).toHaveCount(1);
  const items = block.locator('[data-set] > ul[data-claims] > li[data-claim]');
  expect((await items.evaluateAll((lis) => lis.map((li) => li.getAttribute('data-claim')))).sort()).toEqual(w.claims.map((c) => c.id).sort());
  await expect(items.first()).toBeVisible();
});

test('state 2: one key with unknowns, plotted behind a persistent banner naming the unknown fields on each claim', async ({ page }) => {
  const w = first('possibly-comparable');
  const block = await openClaims(page, w);
  await expect(block).toHaveAttribute('data-comparison-state', 'possibly-comparable');
  const banner = block.locator('[data-set] > [data-comparability-unknown]');
  const list = block.locator('[data-set] > ul[data-claims]');
  await expect(banner).toBeVisible();
  await expect(banner.locator('.title')).toContainText('Possibly comparable');
  for (const c of w.claims) {
    await expect(banner.locator(`tr[data-unknown-claim="${c.id}"] [data-unknown-field]`)).toHaveText(c.unknown);
  }
  // persistent: above the plot, with nothing to close it, visible whenever the plot is
  await expect(banner.locator('button, details, dialog')).toHaveCount(0);
  const [bb, lb] = [await banner.boundingBox(), await list.boundingBox()];
  expect(bb!.y + bb!.height, 'the banner is above the plot').toBeLessThanOrEqual(lb!.y);
  await expect(list.locator('li[data-claim]')).toHaveCount(w.claims.length);
  await expect(block.locator('[data-comparability]'), 'one key: no diff').toHaveCount(0);
});

test('state 3: different keys, the field-by-field diff instead of a chart, with the dropped-claim count shown', async ({ page }) => {
  const w = first('not-comparable', true);
  const block = await openClaims(page, w);
  await expect(block).toHaveAttribute('data-comparison-state', 'not-comparable');
  const diff = block.locator(':scope > [data-comparability]');
  await expect(diff).toBeVisible();
  await expect(diff.locator('tr[data-diff-field]')).toHaveCount(Object.keys(w.fields).length);
  const sizes = setsOf(w).map((set) => set.length);
  const drops = w.claims.length - sizes[0];
  const restrict = diff.locator('a[data-action="restrict"]');
  await expect(restrict).toContainText(`(${drops} of ${w.claims.length} claims dropped)`);
  await expect(diff.locator('a[data-action="proceed"]')).toBeVisible();
  // each set plotted on its own, the largest first, a set that agrees in ignorance behind its own banner
  const sets = block.locator('[data-set]');
  await expect(sets).toHaveCount(sizes.length);
  for (let i = 0; i < sizes.length; i++) await expect(sets.nth(i).locator(':scope > ul[data-claims] > li[data-claim]')).toHaveCount(sizes[i]);
  await expect(block.locator('[data-set] > [data-comparability-unknown]')).toHaveCount(ignorantSets(w).length);
  // restricting is a native jump to the set it keeps, whose heading counts what it leaves out
  await restrict.click();
  expect(new URL(page.url()).hash).toBe(`#cmp-${w.metric}-set-a`);
  await expect(sets.first().locator(':scope > .set-head')).toContainText(`${sizes[0]} of ${w.claims.length} claims`);
});

test('the failure cases: agreement in ignorance shown as comparable, and a claim dropped silently, are reported', async ({ page }) => {
  const { wants } = fixture();
  await page.goto('about:blank');
  const cases: [Want, Doctor, RegExp][] = [
    [first('possibly-comparable'), 'drop-banner', /agreement in ignorance shown as confirmed comparability/],
    [first('possibly-comparable'), 'relabel', /shown as comparable, but its keys and unknowns make it possibly-comparable/],
    [first('possibly-comparable'), 'short-banner', /the banner names \[.*\] unknown on/],
    [first('not-comparable', true), 'drop-banner', /agreement in ignorance shown as confirmed comparability/],
    [first('comparable'), 'drop-claim', /is dropped silently, in no plot and counted nowhere/],
    [first('not-comparable', true), 'drop-claim', /is dropped silently, in no plot and counted nowhere/],
    [first('not-comparable', true), 'merge-sets', /plots claims of \d+ condition sets together/],
    [first('not-comparable', true), 'merge-sets', /spans \d+ condition sets with no field-by-field diff/],
    [first('not-comparable', true), 'hide-count', /drops \d+ of \d+ claims, and the control does not say so/],
  ];
  for (const [w, doctor, want] of cases) {
    const body = await html(page, benchmarkPath(w));
    const clean = await audited(page, body, onPage(wants, w.benchmark));
    expect(clean.problems, `${w.benchmark} as served`).toEqual([]);
    const bad = await audited(page, body, onPage(wants, w.benchmark), doctor, w.metric);
    expect(bad.problems.some((p) => want.test(p)), `${w.benchmark} ${w.metric} doctored by ${doctor}: ${JSON.stringify(bad.problems)}`).toBe(true);
  }
});

test('the three states read accessibly with the claims open: axe at WCAG 2.2 AA, light and dark', async ({ browser }) => {
  test.setTimeout(120_000);
  const tags = (JSON.parse(readFileSync(join(ROOT, 'site', 'test', 'a11y', 'archetypes.json'), 'utf8')) as { standard: { axe: string[] } }).standard.axe;
  const pages = [...new Set([first('comparable'), first('possibly-comparable'), first('not-comparable', true)].map(benchmarkPath))];
  for (const colorScheme of ['light', 'dark'] as const) {
    // axe is injected as a script, so this context runs one; the page itself ships none
    const ctx = await browser.newContext({ javaScriptEnabled: true, colorScheme });
    const page = await ctx.newPage();
    for (const path of pages) {
      await page.goto(path);
      await page.locator('details[data-section="10"] > summary').click();
      const r = await new AxeBuilder({ page }).include('details[data-section="10"]').withTags(tags).analyze();
      expect(r.passes.length, `${path} ${colorScheme}: axe ran rules`).toBeGreaterThan(0);
      expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`), `${path} ${colorScheme}`).toEqual([]);
    }
    await ctx.close();
  }
});
