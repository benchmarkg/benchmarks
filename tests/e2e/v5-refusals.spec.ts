// tests/e2e/v5-refusals.spec.ts -- P3-S10-T06: 10 V5's six categorical refusals in the Comparison Workbench at /compare/
// (site/src/lib/refusals.ts, decided in site/src/lib/workbench.ts `view`, drawn by site/src/components/Workbench.astro at
// build time and by site/src/islands/workbench/client.ts in the browser; 10 V5 "Beyond the generic key"; 04 S8, S9;
// 08 S3.2 S5).
//
//   npx playwright test tests/e2e/v5-refusals.spec.ts
//
// Runs against the site playwright.config.ts builds from the draft preview with build/e2e-claims/'s claims artifacts,
// as tests/e2e/v5-workbench.spec.ts does. Three of the six situations are real claims of the preview (Matbench
// Discovery's F1 under two compliance tiers, which also lists them under two eligibility tracks; ForecastBench's Brier
// scores pending, partial and resolved; WeatherBench 2's RMSE and CRPS over several dimensions, the benchmark flagging
// no_legitimate_aggregate); the other three have no claim in the corpus, so make_claims_fixture.py constructs them:
// RoboArena ratings from its two real rating pools under one key with nothing unknown, tau-bench under pass^1 and pass^8,
// and ARC-AGI-3 on its verified and community boards' own condition records. The first test fails if any of the six
// disappears, and says which are real.
//
// The expectation is computed here from the artifacts and 10 V5's table, not from the site's module: for each column
// (benchmark family, metric) of a selection, each refusal's field over its claims -- the claim's rating_pool (where a
// claim is a rating or the metric requires a pool), selection_strategy pass-hat-k and k, the subset on a benchmark
// flagging no_legitimate_aggregate or aggregation_policy none-by-design or a vector-valued metric, eligibility_track,
// training_data_eligibility, resolution_status -- and a refusal fires when the field takes two or more values there, an
// unrecorded value being one of them. A page is then audited against it (`audit`, in the browser, over the HTML as
// served, as the script left it, or as doctored):
//   - a refused column's header names its refusals; over the table, never in a disclosure, a section per refused column
//     names each refusal (which), says why, lists its groups with their counts, and says what would make the claims
//     comparable; a column nothing is refused on has none of these;
//   - a refused column is cut into parts, one column of the table each, and every claim is in the part of its own
//     values: no cell holds claims of two parts, which would put a number where the refusal belongs, on one axis with a
//     number it may not be read against; a claim whose ground truth is unresolved says so in its cell.
// Done when: "Each of the six situations in 10's refusal table renders a named reason rather than a number." The failure
// cases are checked as failures: the page is audited again doctored -- a refusal's section taken out, its reason or its
// condition emptied, the header unnamed, the parts merged back into one column, a claim moved into another part, the
// whole region taken out, the resolution status hidden -- on the build's render and on the script's, and each must be
// reported. And the script checks its own decision against the build's before it applies anything: a corpus.json whose
// records would decide differently is refused.
import { expect, test, type Browser, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

interface Row {
  claim: {
    id: string; system: string; benchmark: string; metric: string; subset?: string | null; claim_type?: string; rating_pool?: string | null;
    resolution_status?: string; value: number | null;
  };
  conditions: Record<string, unknown> | null;
  comparability: { comparability_key: string };
}
interface Bench { id: string; no_legitimate_aggregate?: boolean; aggregation_policy?: string }
interface Metric { id: string; value_type?: string; requires_pool?: boolean }
interface Sel { b: string[]; k: string[]; sys: string[] }
type Refusal = 'rating-pool' | 'pass-hat-k' | 'vector-valued' | 'legality-track' | 'training-eligibility' | 'resolution';
const SIX: Refusal[] = ['rating-pool', 'pass-hat-k', 'vector-valued', 'legality-track', 'training-eligibility', 'resolution'];
/** One refusal as a column's claims give it: each claim's value of the refusal's field, null where it is not recorded. */
interface WantRefusal { id: Refusal; of: Record<string, string | null> }
interface WantColumn { id: string; claims: { id: string; system: string; status: string }[]; refusals: WantRefusal[] }
interface Want { selection: string; columns: WantColumn[] }
type Doctor = 'drop-refusal' | 'drop-why' | 'drop-requires' | 'unname-header' | 'merge-parts' | 'misgroup' | 'drop-region' | 'hide-status';

const ROOT = join(__dirname, '..', '..');
const DIR = join(ROOT, 'build', 'e2e-claims');                  // make_claims_fixture.py --out, playwright.config.ts
const PREVIEW = join(ROOT, 'build', 'preview');
const family = (ref: string) => ref.split('@', 1)[0];
const systemOf = (ref: string) => ref.split('@', 1)[0].split('#', 1)[0];
const byCodePoint = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const constructed = (id: string) => id.startsWith('claim-e2e');

let memo: { rows: Row[]; benchmarks: Map<string, Bench>; metrics: Map<string, Metric> } | undefined;
/** The artifacts the server was built from, read when a test needs them: the webServer writes them first. */
function fixture() {
  if (memo) return memo;
  const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
  const corpus = read(join(PREVIEW, 'corpus.json')) as { entities: { benchmark: Bench[]; metric: Metric[] } };
  memo = {
    rows: (read(join(DIR, 'claims.json')) as { claims: Row[] }).claims,
    benchmarks: new Map(corpus.entities.benchmark.map((b) => [b.id, b])),
    metrics: new Map(corpus.entities.metric.map((m) => [m.id, m])),
  };
  return memo;
}

/** The canonical query of a selection (10 "Filter state encoding"), as the page writes it. */
function canonical(s: Sel): string {
  const parts = (['b', 'k', 'sys'] as const).map((k) => [k, [...new Set(s[k])].sort(byCodePoint)] as const).filter(([, v]) => v.length > 0)
    .map(([k, v]) => `${k}=${v.map(encodeURIComponent).join(',')}`);
  return parts.length > 0 ? [...parts, 'v=1'].join('&') : '';
}

/** 10 V5's six, each as the field it reads off one claim, and whether it applies to a column at all. */
function refusalsOf(rows: Row[], bench: Bench | undefined, metric: Metric | undefined): WantRefusal[] {
  const cond = (r: Row, f: string) => (r.conditions?.[f] ?? null) as string | number | null;
  const str = (v: unknown) => (v == null ? null : String(v));
  const fields: [Refusal, boolean, (r: Row) => string | null][] = [
    ['rating-pool', metric?.requires_pool === true || rows.some((r) => r.claim.claim_type === 'rating' || r.claim.rating_pool != null), (r) => r.claim.rating_pool ?? null],
    ['pass-hat-k', rows.some((r) => cond(r, 'selection_strategy') === 'pass-hat-k'),
      (r) => (cond(r, 'selection_strategy') === 'pass-hat-k' ? `pass^${cond(r, 'k') ?? 'k'}` : str(cond(r, 'selection_strategy')))],
    ['vector-valued', bench?.no_legitimate_aggregate === true || bench?.aggregation_policy === 'none-by-design' || metric?.value_type === 'vector', (r) => r.claim.subset ?? null],
    ['legality-track', rows.some((r) => cond(r, 'eligibility_track') != null), (r) => str(cond(r, 'eligibility_track'))],
    ['training-eligibility', rows.some((r) => cond(r, 'training_data_eligibility') != null), (r) => str(cond(r, 'training_data_eligibility'))],
    ['resolution', true, (r) => r.claim.resolution_status ?? 'resolved'],
  ];
  const out: WantRefusal[] = [];
  for (const [id, applies, value] of fields) {
    if (!applies || rows.length < 2) continue;
    const of = Object.fromEntries(rows.map((r) => [r.claim.id, value(r)]));
    if (new Set(Object.values(of)).size > 1) out.push({ id, of });
  }
  return out;
}

/** What the table of selection `s` must refuse, from the artifacts: its columns, each its claims and refusals. A
 *  restriction (k) keeps only its keys' claims in the columns holding them, as the workbench does. */
function want(s: Sel): Want {
  const { rows, benchmarks, metrics } = fixture();
  const by = new Map<string, Row[]>();
  for (const r of rows) {
    if (s.b.length > 0 && !s.b.includes(family(r.claim.benchmark))) continue;
    if (s.sys.length > 0 && !s.sys.includes(systemOf(r.claim.system))) continue;
    const k = `${family(r.claim.benchmark)}|${r.claim.metric}`;
    by.set(k, [...(by.get(k) ?? []), r]);
  }
  const columns: WantColumn[] = [];
  for (const [id, picked] of by) {
    const restricted = picked.filter((r) => s.k.includes(r.comparability.comparability_key));
    const kept = restricted.length > 0 ? restricted : picked;
    const [bench, metric] = id.split('|');
    columns.push({
      id, refusals: refusalsOf(kept, benchmarks.get(bench), metrics.get(metric)),
      claims: kept.map((r) => ({ id: r.claim.id, system: systemOf(r.claim.system), status: r.claim.resolution_status ?? 'resolved' })),
    });
  }
  return { selection: canonical(s), columns };
}
interface Audit { problems: string[]; refused: Record<string, number>; parts: number }

/** What is wrong with the refusals in `html` against `w`, read in the browser from a DOMParser document, so a doctored
 *  copy is audited exactly as the page is. `doctor` first changes the document the way a view that hid a refusal
 *  would, on column `target`. */
function audit({ html, w, doctor, target }: { html: string; w: Want; doctor: Doctor | null; target: string | null }): Audit {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const problems: string[] = [];
  const refused: Record<string, number> = {};
  const box = doc.querySelector('[data-workbench-view]');
  if (box == null) return { problems: ['no workbench view'], refused, parts: 0 };
  const esc = (s: string) => s.replace(/["\\]/g, '\\$&');
  const text = (e: Element | null | undefined) => (e?.textContent ?? '').replace(/\s+/g, ' ').trim();
  // a column's claims cut by every refusal that fires on it: the tuple of a claim's values
  const pk = (c: WantColumn, claim: string) => JSON.stringify(c.refusals.map((f) => f.of[claim]));
  // a group named in a label: the value as a word of its own, so "compliant" is not found in "non-compliant"
  const literal = (v: string) => v.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
  const names = (label: string, v: string) => new RegExp('(^|[\\s(])' + literal(v) + '($|[\\s),])').test(label);

  // ---- the failure cases: the page as a view that hides a refusal would render it
  if (doctor != null) {
    const th = target != null ? box.querySelector(`thead th[data-col="${esc(target)}"]`) : null;
    if (th == null) problems.push(`nothing to doctor: no column ${target}`);
    const sec = target != null ? box.querySelector(`[data-wb-col-refusals="${esc(target)}"]`) : null;
    if (doctor === 'drop-refusal') sec?.querySelector('[data-refusal]')?.remove();
    if (doctor === 'drop-why') sec?.querySelector('[data-refusal-why]')?.replaceChildren();
    if (doctor === 'drop-requires') sec?.querySelector('[data-refusal-requires]')?.remove();
    if (doctor === 'unname-header') {
      th?.removeAttribute('data-col-refusal');
      th?.querySelector('[data-col-refusal-note]')?.remove();
    }
    if (doctor === 'merge-parts') {
      // the column drawn as one, the way a table with no refusal draws it: every claim of a row in one cell
      for (const tr of box.querySelectorAll('tbody tr[data-system]')) {
        const tds = [...tr.querySelectorAll(`td[data-col="${esc(target ?? '')}"]`)];
        for (const td of tds.slice(1)) {
          tds[0].append(...td.querySelectorAll('[data-wb-claim]'));
          td.remove();
        }
        tds[0]?.removeAttribute('data-part');
      }
      box.querySelectorAll(`thead th[data-part-col="${esc(target ?? '')}"]`).forEach((e) => e.remove());
      th?.removeAttribute('colspan');
    }
    if (doctor === 'misgroup') {
      // one claim moved into the next part's cell of its own row
      const block = box.querySelector(`tbody td[data-col="${esc(target ?? '')}"] [data-wb-claim]`);
      const td = block?.closest('td');
      const other = [...(td?.parentElement?.querySelectorAll(`td[data-col="${esc(target ?? '')}"]`) ?? [])].find((x) => x !== td);
      if (block != null && other != null) other.append(block);
      else problems.push('nothing to doctor: no row with two parts');
    }
    if (doctor === 'drop-region') box.querySelector('[data-wb-refusals]')?.remove();
    if (doctor === 'hide-status') box.querySelectorAll(`td[data-col="${esc(target ?? '')}"] [data-resolution-status]`).forEach((e) => e.remove());
  }

  // ---- the audit
  if (box.getAttribute('data-selection') !== w.selection) problems.push(`the view says it is selection "${box.getAttribute('data-selection')}", not "${w.selection}"`);
  const table = box.querySelector('table[data-wb-table]');
  if (table == null) return { problems: [...problems, 'no table'], refused, parts: 0 };
  const region = box.querySelector('[data-wb-refusals]');
  const wanted = w.columns.filter((c) => c.refusals.length > 0);
  if (region == null) problems.push('no section says which comparisons are refused');
  else {
    if (!(region.compareDocumentPosition(table) & 4)) problems.push('the refusals are not before the table');
    if (region.closest('details') != null) problems.push('the refusals are inside a disclosure');
    if (!text(region.querySelector('h2')).includes(`(${wanted.length} of ${w.columns.length} column`)) problems.push(`the refusals section does not count ${wanted.length} of ${w.columns.length} columns refused: "${text(region.querySelector('h2'))}"`);
    if ((wanted.length === 0) !== (region.querySelector('[data-wb-refusals-none]') != null)) problems.push('the refusals section says nothing is refused, or says nothing when nothing is');
  }
  let parts = 0;
  for (const c of w.columns) {
    const th = table.querySelector(`thead th[data-col="${esc(c.id)}"]`);
    if (th == null) {
      problems.push(`${c.id}: no column`);
      continue;
    }
    const ids = c.refusals.map((f) => f.id);
    const named = (th.getAttribute('data-col-refusal') ?? '').split(' ').filter(Boolean);
    const sec = region?.querySelector(`[data-wb-col-refusals="${esc(c.id)}"]`) ?? null;
    const rows = [...table.querySelectorAll('tbody tr[data-system]')];
    const want = new Set(c.claims.map((x) => pk(c, x.id)));
    if (ids.length === 0) {
      if (named.length > 0 || sec != null) problems.push(`${c.id}: nothing splits its claims, but it is refused (${named.join(', ') || 'a section'})`);
      for (const tr of rows) if (tr.querySelectorAll(`td[data-col="${esc(c.id)}"]`).length > 1) problems.push(`${c.id}: nothing splits its claims, but it is cut`);
      continue;
    }
    // which refusal, on the column itself
    if (JSON.stringify(named) !== JSON.stringify(ids)) problems.push(`${c.id}: the header names refusals [${named.join(', ')}], where its claims are refused for [${ids.join(', ')}]`);
    if (!text(th.querySelector('[data-col-refusal-note]')).startsWith('⊘ Refused:')) problems.push(`${c.id}: the header does not say it is refused`);
    // why, the groups, and what would make them comparable, over the table
    if (sec == null) problems.push(`${c.id}: refused for [${ids.join(', ')}] by its claims, and no section names why`);
    for (const f of c.refusals) {
      refused[f.id] = (refused[f.id] ?? 0) + 1;
      const r = sec?.querySelector(`[data-refusal="${f.id}"]`) ?? null;
      if (r == null) {
        if (sec != null) problems.push(`${c.id}: refused for ${f.id} by its claims, and no section names why`);
        continue;
      }
      if (!text(r.querySelector('h4')).startsWith('⊘ Refused: ')) problems.push(`${c.id}: the ${f.id} section does not name its refusal`);
      if (text(r.querySelector('[data-refusal-why]')).length < 40) problems.push(`${c.id}: the ${f.id} section says not why`);
      if (!text(r.querySelector('[data-refusal-requires]')).startsWith('Comparable only as ') || text(r.querySelector('[data-refusal-requires]')).length < 40) {
        problems.push(`${c.id}: the ${f.id} section says not what would make the claims comparable`);
      }
      const groups = [...r.querySelectorAll('tr[data-refusal-group]')].map((g) => ({ label: text(g.querySelector('th')), n: Number(g.getAttribute('data-claims')) }));
      const values = new Map<string | null, number>();
      for (const v of Object.values(f.of)) values.set(v, (values.get(v) ?? 0) + 1);
      const counts = (xs: number[]) => JSON.stringify([...xs].sort((a, b) => a - b));
      if (counts(groups.map((g) => g.n)) !== counts([...values.values()])) problems.push(`${c.id}: ${f.id} lists groups of [${groups.map((g) => g.n)}] claims, where its claims hold [${[...values.values()]}]`);
      for (const [v] of values) {
        const label = v == null ? 'not recorded' : v;
        if (!groups.some((g) => names(g.label, label))) problems.push(`${c.id}: ${f.id} names no group for ${label}`);
      }
    }
    // the parts: one column of the table each, every claim in its own, and no cell holding two
    const heads = [...table.querySelectorAll(`thead th[data-part-col="${esc(c.id)}"]`)];
    if (heads.length !== want.size || Number(th.getAttribute('colspan') ?? 1) !== want.size) {
      problems.push(`${c.id}: drawn as ${heads.length || 1} column(s), where its refusals cut it into ${want.size}`);
    }
    parts += want.size;
    for (const tr of rows) {
      const tds = [...tr.querySelectorAll(`td[data-col="${esc(c.id)}"]`)];
      if (tds.length !== want.size) problems.push(`${tr.getAttribute('data-system')}'s ${c.id}: ${tds.length} cell(s), where its refusals cut the column into ${want.size}`);
      for (const td of tds) {
        const keys = new Set([...td.querySelectorAll('[data-wb-claim]')].map((b) => b.getAttribute('data-wb-claim') ?? '').filter((id) => c.claims.some((x) => x.id === id)).map((id) => pk(c, id)));
        if (keys.size > 1) problems.push(`${tr.getAttribute('data-system')}'s ${c.id}: one cell holds claims of ${keys.size} parts, so a number is shown where the refusal belongs`);
      }
    }
    const placed = new Map<string, Set<string>>();          // the page's part -> the claims' own parts
    for (const x of c.claims) {
      const b = table.querySelector(`[data-wb-claim="${esc(x.id)}"]`);
      const td = b?.closest('td');
      if (b == null || td == null) {
        problems.push(`${c.id}: ${x.id} is in no cell`);
        continue;
      }
      if (td.getAttribute('data-col') !== c.id || td.closest('tr')?.getAttribute('data-system') !== x.system) problems.push(`${c.id}: ${x.id} is drawn in another row or column`);
      const p = td.getAttribute('data-part') ?? '';
      placed.set(p, new Set([...(placed.get(p) ?? []), pk(c, x.id)]));
      if (b.getAttribute('data-part') !== p) problems.push(`${c.id}: ${x.id} says it is in part ${b.getAttribute('data-part')}, and is drawn in ${p || 'none'}`);
    }
    for (const [p, ks] of placed) if (ks.size > 1) problems.push(`${c.id}: part ${p || '(none)'} holds claims of ${ks.size} different groups`);
    if (placed.size !== want.size) problems.push(`${c.id}: its claims are drawn in ${placed.size} part(s), where they hold ${want.size}`);
  }
  // 10 V5: "Show resolution_status": a claim whose ground truth is not resolved says so in its cell
  for (const c of w.columns) {
    for (const x of c.claims.filter((y) => y.status !== 'resolved')) {
      const b = table.querySelector(`[data-wb-claim="${esc(x.id)}"]`);
      if (b != null && b.querySelector(`:scope > [data-resolution-status="${x.status}"]`) == null) problems.push(`${x.id}: its resolution_status is ${x.status}, and its cell does not say so`);
    }
  }
  return { problems, refused, parts };
}

const audited = (page: Page, html: string, w: Want, doctor: Doctor | null = null, target: string | null = null) =>
  page.evaluate(audit, { html, w, doctor, target });
async function served(page: Page, path: string): Promise<string> {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
}

// ---- the page's script, with the data it fetches served (as tests/e2e/v5-workbench.spec.ts serves it) ----------------

let hrefs: { claims: string; comparability: string; corpus: string } | undefined;
async function dataHrefs(page: Page) {
  if (hrefs) return hrefs;
  const html = await served(page, '/compare/');
  const attr = (name: string) => new RegExp(`data-${name}-href="([^"]+)"`).exec(html)?.[1];
  const [claims, comparability, corpus] = [attr('claims'), attr('comparability'), attr('corpus')];
  expect(claims && comparability && corpus, 'the page names its three artifacts by their hashed URLs').toBeTruthy();
  hrefs = { claims: claims!, comparability: comparability!, corpus: corpus! };
  return hrefs;
}
/** A context that runs scripts and is served the artifacts at the URLs the page names; `corpus` replaces corpus.json. */
async function live(browser: Browser, page: Page, baseURL: string | undefined, { corpus = null as string | null } = {}) {
  const h = await dataHrefs(page);
  const ctx = await browser.newContext({ javaScriptEnabled: true, baseURL });
  const files: Record<string, string> = { [h.claims]: join(DIR, 'claims.json'), [h.comparability]: join(DIR, 'derived', 'comparability.json'), [h.corpus]: join(PREVIEW, 'corpus.json') };
  await ctx.route('**/data/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === h.corpus && corpus != null) return route.fulfill({ body: corpus, contentType: 'application/json' });
    const file = files[path];
    return file != null ? route.fulfill({ path: file, contentType: 'application/json' }) : route.fulfill({ status: 404, body: '' });
  });
  return { ctx, page: await ctx.newPage() };
}
const settled = (page: Page) => page.waitForFunction(() => {
  const s = document.querySelector<HTMLElement>('[data-workbench]')?.dataset.workbenchLive;
  return s != null && s !== 'static' && s !== 'loading';
}, null, { timeout: 60_000 });
const liveState = (page: Page) => page.locator('[data-workbench]').getAttribute('data-workbench-live');

// ---- the selections ---------------------------------------------------------------------------------------------------

const ALL: Sel = { b: [], k: [], sys: [] };
/** The first column, by id, refused for `id`. */
function refusedFor(id: Refusal): WantColumn {
  const hit = [...want(ALL).columns].sort((a, b) => byCodePoint(a.id, b.id)).find((c) => c.refusals.some((f) => f.id === id));
  expect(hit, `a column refused for ${id} in the fixture`).toBeDefined();
  return hit!;
}
/** Every benchmark with a refused column: a selection holding each of the six. */
const sixBenchmarks = () => [...new Set(SIX.map((id) => refusedFor(id).id.split('|')[0]))];

test.beforeAll(async ({ request }) => {
  expect((await request.get('/claims/claim-e2e000000003/')).status(), 'the server on the baseURL was built from build/e2e-claims with the refusal rows (playwright.config.ts)').toBe(200);
});

test('the fixture holds each of the six situations, three of them in real claims', () => {
  const all = want(ALL);
  for (const id of SIX) expect(all.columns.some((c) => c.refusals.some((f) => f.id === id)), `a column refused for ${id}`).toBe(true);
  // over the preview's own claims, the constructed rows left out: the three the corpus holds
  const { rows } = fixture();
  const real = new Set<string>();
  for (const c of all.columns) {
    const [bench, metric] = c.id.split('|');
    const kept = rows.filter((r) => `${family(r.claim.benchmark)}|${r.claim.metric}` === c.id && !constructed(r.claim.id));
    for (const f of refusalsOf(kept, fixture().benchmarks.get(bench), fixture().metrics.get(metric))) real.add(f.id);
  }
  for (const id of ['vector-valued', 'legality-track', 'training-eligibility', 'resolution'] as const) expect(real.has(id), `${id} on real claims`).toBe(true);
  // the case the comparability key alone gets wrong: ratings from two pools under one key, nothing unknown
  const pools = refusedFor('rating-pool');
  const keyed = rows.filter((r) => pools.claims.some((x) => x.id === r.claim.id));
  expect(new Set(keyed.map((r) => r.comparability.comparability_key)).size, 'the ratings share one comparability key').toBe(1);
});

test.describe('with JavaScript disabled', () => {
  test.use({ javaScriptEnabled: false });

  test('the bare address renders each of the six as a named reason over the table, and cuts each refused column into parts', async ({ page }) => {
    const w = want(ALL);
    const html = await served(page, '/compare/');
    const a = await audited(page, html, w);
    expect(a.problems).toEqual([]);
    for (const id of SIX) expect(a.refused[id] ?? 0, id).toBe(w.columns.filter((c) => c.refusals.some((f) => f.id === id)).length);
    expect(a.parts, 'two parts or more in every refused column').toBeGreaterThanOrEqual(2 * w.columns.filter((c) => c.refusals.length > 0).length);
    // as a reader without a script sees it
    await page.goto('/compare/');
    await expect(page.locator('[data-workbench]')).toHaveAttribute('data-workbench-live', 'static');
    const pools = refusedFor('rating-pool');
    const section = page.locator(`[data-wb-col-refusals="${pools.id}"] [data-refusal="rating-pool"]`);
    await expect(section).toBeVisible();
    await expect(section.locator('h4')).toContainText('Refused: Pool-relative ratings from different rating pools');
    await expect(section.locator('[data-refusal-requires]')).toContainText('the same rating_pool');
    await expect(page.locator(`th[data-col="${pools.id}"] [data-col-refusal-note]`)).toBeVisible();
    await expect(page.locator(`th[data-col="${pools.id}"]`), 'the key alone calls them comparable; the refusal is read beside it').toHaveAttribute('data-col-state', 'comparable');
    await expect(page.locator(`thead th[data-part-col="${pools.id}"]`)).toHaveCount(2);
  });
});

test.describe('with JavaScript', () => {
  test('the script applies the same refusals to a selection, and a selection keeping one group refuses nothing', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const { ctx, page } = await live(browser, probe, baseURL);
    // the bare address: the script decides the six over everything, finds the page's own decision, and applies nothing
    await page.goto('/compare/');
    await settled(page);
    expect(await liveState(page)).toBe('ready');
    const legality = refusedFor('legality-track');
    const arc = legality.id.split('|')[0];
    const twice = legality.claims.find((x) => legality.claims.filter((y) => y.system === x.system).length > 1)!;
    const community = fixture().rows.find((r) => r.claim.id === legality.claims.find((x) => x.system !== twice.system)!.id)!.comparability.comparability_key;
    const selections: [string, Sel, number][] = [
      ['every benchmark with a refused column', { b: sixBenchmarks(), k: [], sys: [] }, SIX.length],
      ['one system on two boards: its two numbers side by side, never on one axis', { b: [arc], k: [], sys: [twice.system] }, 1],
      ['one rating pool only: nothing to refuse', { b: [refusedFor('rating-pool').id.split('|')[0]], k: [], sys: ['pi05-droid'] }, 0],
      ['a restriction to one board: nothing to refuse', { b: [arc], k: [community], sys: [] }, 0],
    ];
    for (const [what, sel, kinds] of selections) {
      const w = want(sel);
      await page.goto(`/compare/?${canonical(sel)}`);
      await settled(page);
      expect(await liveState(page), what).toBe('applied');
      const a = await audited(page, await page.content(), w);
      expect(a.problems, what).toEqual([]);
      expect(Object.keys(a.refused).length, `${what}: the refusals it holds`).toBe(kinds);
    }
    await ctx.close();
  });

  test('a corpus.json whose records decide the refusals differently is refused, and nothing is applied', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const vector = refusedFor('vector-valued');
    const bench = vector.id.split('|')[0];
    const corpus = JSON.parse(readFileSync(join(PREVIEW, 'corpus.json'), 'utf8')) as { entities: { benchmark: Bench[] } };
    for (const b of corpus.entities.benchmark) if (b.id === bench) Object.assign(b, { no_legitimate_aggregate: false, aggregation_policy: 'official-aggregate' });
    const { ctx, page } = await live(browser, probe, baseURL, { corpus: JSON.stringify(corpus) });
    await page.goto(`/compare/?${canonical({ b: [bench], k: [], sys: [] })}`);
    await settled(page);
    expect(await liveState(page)).toBe('failed');
    await expect(page.locator('[data-wb-status]')).toContainText('not the ones its table was built with');
    const a = await audited(page, await page.content(), want(ALL));
    expect(a.problems, 'the build\'s table, every refusal in it, stays').toEqual([]);
    await ctx.close();
  });
});

test('the failure cases: a refusal removed, or a number shown where a refusal belongs, are reported', async ({ browser, page, baseURL }) => {
  test.setTimeout(240_000);
  await page.goto('about:blank');
  const all = want(ALL);
  const html = await served(page, '/compare/');
  const pools = refusedFor('rating-pool').id;
  const k = refusedFor('pass-hat-k').id;
  const arc = refusedFor('legality-track').id;
  const status = refusedFor('resolution').id;
  const vector = refusedFor('vector-valued').id;
  const tiers = refusedFor('training-eligibility').id;
  const cases: [string, Want, Doctor, string, RegExp][] = [
    [html, all, 'drop-refusal', pools, /refused for rating-pool by its claims, and no section names why/],
    [html, all, 'drop-why', k, /the pass-hat-k section says not why/],
    [html, all, 'drop-requires', tiers, /section says not what would make the claims comparable/],
    [html, all, 'unname-header', arc, /the header names refusals \[\], where its claims are refused for/],
    [html, all, 'merge-parts', pools, /one cell holds claims of 2 parts, so a number is shown where the refusal belongs/],
    [html, all, 'merge-parts', vector, /drawn as 1 column\(s\), where its refusals cut it into/],
    [html, all, 'misgroup', arc, /holds claims of 2 different groups|says it is in part/],
    [html, all, 'drop-region', status, /no section says which comparisons are refused/],
    [html, all, 'hide-status', status, /its resolution_status is pending, and its cell does not say so/],
  ];
  // the same on the script's own render of a selection
  const sel: Sel = { b: sixBenchmarks(), k: [], sys: [] };
  const ws = want(sel);
  const { ctx, page: p } = await live(browser, page, baseURL);
  await p.goto(`/compare/?${ws.selection}`);
  await settled(p);
  const rendered = await p.content();
  await ctx.close();
  cases.push([rendered, ws, 'merge-parts', k, /one cell holds claims of 2 parts|drawn as 1 column/]);
  cases.push([rendered, ws, 'drop-refusal', status, /refused for resolution by its claims, and no section names why/]);
  cases.push([rendered, ws, 'unname-header', pools, /the header names refusals \[\]/]);
  for (const [body, w, doctor, target, expected] of cases) {
    const clean = await audited(page, body, w);
    expect(clean.problems, `${target} as rendered`).toEqual([]);
    const bad = await audited(page, body, w, doctor, target);
    expect(bad.problems.some((x) => expected.test(x)), `${target} doctored by ${doctor}: ${JSON.stringify(bad.problems)}`).toBe(true);
  }
});
