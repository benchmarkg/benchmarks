// tests/e2e/v5-workbench.spec.ts -- P3-S10-T05: the V5 Comparison Workbench at /compare/ (10 V5; 08 S4.3, S8.3; 04 S8):
// site/src/pages/compare/index.astro, site/src/components/Workbench.astro, site/src/lib/workbench.ts and the browser's
// site/src/islands/workbench/client.ts, over lib/comparability.ts's decisions.
//
//   npx playwright test tests/e2e/v5-workbench.spec.ts
//
// Runs against the site playwright.config.ts builds from the draft preview with build/e2e-claims/'s claims artifacts, as
// tests/e2e/comparability-states.spec.ts does: the preview's real curated claims, which hold all three of 04 S8's states,
// and make_claims_fixture.py's constructed rows. That server copies no /data/ artifact into the site, so the tests that
// run the page's script serve the three it fetches themselves, at the content-hashed URLs the page names: claims.json
// and derived/comparability.json from build/e2e-claims/, the files the table was rendered from, and corpus.json from the
// preview. One test serves the preview's own claims.json instead, which is not the file the table was rendered from, and
// the page must refuse it.
//
// The expectation is computed here from the artifacts, not from the site's modules: a selection's claims (benchmark
// family in b, system in sys, an omitted key no constraint), each (benchmark, metric) column's condition sets by
// comparability key with a restriction (k) keeping its sets only, the state from the number of keys and
// key_unknown_count, the diff from derived/comparability.json's material rows for the pairs the selection keeps. A page
// is then audited against it (`audit`, in the browser over the HTML as served or as the script left it, or as doctored):
//   - the view says which selection it is, and counts its claims and what a restriction dropped;
//   - every column and every system row the selection gives is drawn, a selected one with no claim included, and every
//     claim it keeps is in exactly one cell, its row's and its column's, with its set label, its condition meter, its
//     unknown material fields named by an explicit marker, and its permalink; a cell with no claim says so;
//   - a column spanning condition sets has the field-by-field diff over the table, exactly the material fields its kept
//     sets differ in, each set's value as its claims have it, and the restrict control counting what it drops; a set of
//     claims that share a key and leave fields unknown sits behind the unknowns banner naming them; a comparable column
//     is silent; a restricted column counts every claim it dropped.
// Done when: "A pasted selection renders the table with its comparability banner already computed and with JavaScript
// disabled." What this spec shows of it, and what it does not: with JavaScript disabled the page renders, as sent, the
// selection of the bare address (every curated claim) with every banner already computed; a pasted selection is applied
// by the page's script, banner included, and with JavaScript disabled the page shows the unconstrained table and says
// the selection is not applied -- the tests assert that it never pretends otherwise. Rendering an arbitrary pasted
// selection without JavaScript needs a renderer per request, which a static site does not have (pages/compare/index.astro).
// The failure cases are checked as failures: a selection whose banner is missing or wrong, a claim dropped from its
// cell, a dropped claim not counted, the restrict control's count hidden, each must be reported.
import { AxeBuilder } from '@axe-core/playwright';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

interface Row {
  claim: { id: string; system: string; benchmark: string; metric: string; value: number | null; value_text?: string | null; ingestion?: { batch: string } | null };
  comparability: { comparability_key: string; key_unknown_count: number; unknown_fields: string[] };
}
interface DiffRow { a: string; b: string; field: string; a_val: unknown; b_val: unknown; severity: 'material' | 'informative' }
interface DiffGroup { benchmark: string; metric: string; claims: number; keys: number; diff_status: string; rows: DiffRow[] | null }
interface Sel { b: string[]; k: string[]; sys: string[] }
type State = 'single' | 'comparable' | 'possibly-comparable' | 'not-comparable';
interface WantClaim { id: string; system: string; key: string; unknown: string[]; label: string; numbered: boolean; ingested: string | null }
interface WantColumn {
  id: string;
  state: State | 'no-claim';
  claims: WantClaim[];
  sets: { label: string; key: string; claims: WantClaim[] }[];
  fields: Record<string, Record<string, unknown>>;    // material field that differs -> claim id -> its value
  deferred: boolean;
  dropped: { id: string; system: string }[];
  restricted: boolean;
}
interface Want { selection: string; columns: WantColumn[]; systems: { id: string; spans: number }[]; claims: number; dropped: number }
type Doctor = 'drop-diff' | 'short-diff' | 'drop-unknowns' | 'drop-claim' | 'hide-count' | 'uncount-restriction' | 'relabel-column';

const ROOT = join(__dirname, '..', '..');
const DIR = join(ROOT, 'build', 'e2e-claims');                  // make_claims_fixture.py --out, playwright.config.ts
const PREVIEW = join(ROOT, 'build', 'preview');
const family = (ref: string) => ref.split('@', 1)[0];
const systemOf = (ref: string) => ref.split('@', 1)[0].split('#', 1)[0];
const byCodePoint = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

let memo: { rows: Row[]; groups: Map<string, DiffGroup>; benchmarks: Set<string>; systems: Set<string> } | undefined;
/** The artifacts the server was built from, read when a test needs them: the webServer writes them first. */
function fixture() {
  if (memo) return memo;
  const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
  const rows = (read(join(DIR, 'claims.json')) as { claims: Row[] }).claims;
  const diff = read(join(DIR, 'derived', 'comparability.json')) as { groups: DiffGroup[] };
  const corpus = read(join(PREVIEW, 'corpus.json')) as { entities: { benchmark: { id: string }[]; system: { id: string }[] } };
  memo = {
    rows,
    groups: new Map(diff.groups.map((g) => [`${g.benchmark} ${g.metric}`, g])),
    benchmarks: new Set(corpus.entities.benchmark.map((b) => b.id)),
    systems: new Set(corpus.entities.system.map((s) => s.id)),
  };
  return memo;
}

/** The canonical query of a selection (10 "Filter state encoding"), as the page must write it. */
function canonical(s: Sel): string {
  const parts = (['b', 'k', 'sys'] as const).map((k) => [k, [...new Set(s[k])].sort(byCodePoint)] as const).filter(([, v]) => v.length > 0)
    .map(([k, v]) => `${k}=${v.map(encodeURIComponent).join(',')}`);
  return parts.length > 0 ? [...parts, 'v=1'].join('&') : '';
}

/** What the table of selection `s` must hold, from the artifacts. */
function want(s: Sel): Want {
  const { rows, groups } = fixture();
  const by = new Map<string, Row[]>();
  for (const r of rows) {
    if (s.b.length > 0 && !s.b.includes(family(r.claim.benchmark))) continue;
    if (s.sys.length > 0 && !s.sys.includes(systemOf(r.claim.system))) continue;
    const k = `${family(r.claim.benchmark)} ${r.claim.metric}`;
    by.set(k, [...(by.get(k) ?? []), r]);
  }
  const columns: WantColumn[] = [];
  const systems = new Set(s.sys);
  for (const [k, picked] of by) {
    const g = groups.get(k)!;
    const restrictedKeys = new Set(picked.map((r) => r.comparability.comparability_key).filter((key) => s.k.includes(key)));
    const kept = restrictedKeys.size > 0 ? picked.filter((r) => restrictedKeys.has(r.comparability.comparability_key)) : picked;
    const keys = [...new Set(kept.map((r) => r.comparability.comparability_key))]
      .map((key) => kept.filter((r) => r.comparability.comparability_key === key))
      .sort((a, b) => b.length - a.length || byCodePoint(a.map((r) => r.claim.id).sort(byCodePoint)[0], b.map((r) => r.claim.id).sort(byCodePoint)[0]));
    const label = (i: number) => String.fromCharCode(65 + i);                     // fewer than 27 sets in the fixture
    const claim = (r: Row, i: number): WantClaim => ({
      id: r.claim.id, system: systemOf(r.claim.system), key: r.comparability.comparability_key, unknown: r.comparability.unknown_fields, label: label(i),
      numbered: r.claim.value != null || (r.claim.value_text != null && r.claim.value_text !== ''), ingested: r.claim.ingestion?.batch ?? null,
    });
    const sets = keys.map((set, i) => ({ label: label(i), key: set[0].comparability.comparability_key, claims: set.map((r) => claim(r, i)) }));
    const ids = new Set(kept.map((r) => r.claim.id));
    const fields: WantColumn['fields'] = {};
    for (const d of g.rows ?? []) {
      if (d.severity !== 'material' || !ids.has(d.a) || !ids.has(d.b)) continue;
      fields[d.field] = { ...(fields[d.field] ?? {}), [d.a]: d.a_val, [d.b]: d.b_val };
    }
    const state: State = kept.length < 2 ? 'single' : sets.length > 1 ? 'not-comparable'
      : kept.some((r) => r.comparability.key_unknown_count > 0) ? 'possibly-comparable' : 'comparable';
    const [bench, metric] = k.split(' ');
    columns.push({
      id: `${bench}|${metric}`, state, claims: sets.flatMap((x) => x.claims), sets, fields, deferred: g.diff_status === 'deferred',
      dropped: picked.filter((r) => !ids.has(r.claim.id)).map((r) => ({ id: r.claim.id, system: systemOf(r.claim.system) })),
      restricted: restrictedKeys.size > 0,
    });
    for (const r of picked) systems.add(systemOf(r.claim.system));
  }
  for (const b of s.b) {
    if (!columns.some((c) => c.id.startsWith(`${b}|`))) {
      columns.push({ id: `${b}|`, state: 'no-claim', claims: [], sets: [], fields: {}, deferred: false, dropped: [], restricted: false });
    }
  }
  return {
    selection: canonical(s),
    columns,
    systems: [...systems].map((id) => ({ id, spans: columns.filter((c) => c.state === 'not-comparable' && c.claims.some((x) => x.system === id)).length })),
    claims: columns.reduce((n, c) => n + c.claims.length, 0),
    dropped: columns.reduce((n, c) => n + c.dropped.length, 0),
  };
}

interface Audit { problems: string[]; blocks: number; diffs: number; unknowns: number; restricted: number }

/** What is wrong with the workbench in `html` against `w`, read in the browser from a DOMParser document, so a doctored
 *  copy is audited exactly as the page is. `doctor` first changes the document the way a view that hid a problem would,
 *  on column `target`. */
function audit({ html, w, doctor, target }: { html: string; w: Want; doctor: Doctor | null; target: string | null }): Audit {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const problems: string[] = [];
  const box = doc.querySelector('[data-workbench-view]');
  if (box == null) return { problems: ['no workbench view'], blocks: 0, diffs: 0, unknowns: 0, restricted: 0 };
  const esc = (s: string) => s.replace(/["\\]/g, '\\$&');
  const banners = (col: string) => box.querySelector(`[data-wb-col-banners="${esc(col)}"]`);
  const show = (v: unknown): string => (Array.isArray(v) ? `[${v.map(show).join(', ')}]`
    : v !== null && typeof v === 'object' ? Object.entries(v as Record<string, unknown>).filter(([, x]) => x != null).map(([k, x]) => `${k} ${show(x)}`).join(', ') || '{}'
      : String(v));

  // ---- the failure cases: the page as a view that hides the problem would render it
  if (doctor != null) {
    if (target == null || box.querySelector(`thead th[data-col="${esc(target)}"]`) == null) problems.push(`nothing to doctor: no column ${target}`);
    const sec = target != null ? banners(target) : null;
    if (doctor === 'drop-diff') sec?.querySelector('[data-comparability]')?.remove();
    if (doctor === 'short-diff') sec?.querySelector('[data-comparability] tr[data-diff-field]')?.remove();
    if (doctor === 'drop-unknowns') sec?.querySelector('[data-comparability-unknown]')?.remove();
    if (doctor === 'hide-count') {
      const a = sec?.querySelector('a[data-action="restrict"]');
      a?.removeAttribute('data-dropped');
      if (a != null) a.textContent = 'Restrict to one condition set';
    }
    if (doctor === 'uncount-restriction') {
      sec?.querySelector('[data-wb-restricted]')?.remove();
      box.querySelectorAll(`td[data-col="${esc(target ?? '')}"] [data-wb-dropped]`).forEach((e) => e.remove());
    }
    if (doctor === 'drop-claim') box.querySelector(`td[data-col="${esc(target ?? '')}"] [data-wb-claim]`)?.remove();
    if (doctor === 'relabel-column') {
      box.querySelector(`th[data-col="${esc(target ?? '')}"]`)?.setAttribute('data-col-state', 'comparable');
      sec?.remove();
    }
  }

  // ---- the audit
  if (box.getAttribute('data-selection') !== w.selection) problems.push(`the view says it is selection "${box.getAttribute('data-selection')}", not "${w.selection}"`);
  if (box.getAttribute('data-claims-total') !== String(w.claims)) problems.push(`the view counts ${box.getAttribute('data-claims-total')} claims, of the ${w.claims} the selection keeps`);
  if (box.getAttribute('data-dropped') !== String(w.dropped)) problems.push(`the view counts ${box.getAttribute('data-dropped')} claims dropped, where the restriction drops ${w.dropped}`);
  const table = box.querySelector('table[data-wb-table]');
  if (table == null) return { problems: [...problems, 'no table'], blocks: 0, diffs: 0, unknowns: 0, restricted: 0 };
  const region = box.querySelector('[data-wb-banners]');
  if (region == null || !(region.compareDocumentPosition(table) & 4)) problems.push('the comparability banners are not before the table');
  if (region?.closest('details') != null) problems.push('the comparability banners are inside a disclosure');

  const heads = [...table.querySelectorAll('thead th[data-col]')].map((th) => th.getAttribute('data-col') ?? '');
  const sorted = (xs: string[]) => [...xs].sort();
  if (JSON.stringify(sorted(heads)) !== JSON.stringify(sorted(w.columns.map((c) => c.id)))) {
    problems.push(`the columns are [${heads.join(', ')}], where the selection gives [${w.columns.map((c) => c.id).join(', ')}]`);
  }
  const rowsDrawn = [...table.querySelectorAll('tbody tr[data-system]')];
  const systemsDrawn = rowsDrawn.map((tr) => tr.getAttribute('data-system') ?? '');
  if (JSON.stringify(sorted(systemsDrawn)) !== JSON.stringify(sorted(w.systems.map((s) => s.id)))) {
    problems.push(`the rows are [${systemsDrawn.join(', ')}], where the selection gives [${w.systems.map((s) => s.id).join(', ')}]`);
  }
  for (const s of w.systems) {
    const tr = rowsDrawn.find((x) => x.getAttribute('data-system') === s.id);
    if (tr != null && tr.getAttribute('data-spans-sets') !== String(s.spans)) {
      problems.push(`${s.id}: its row says it is one of several condition sets in ${tr.getAttribute('data-spans-sets')} columns, not ${s.spans}`);
    }
  }
  const allBlocks = [...table.querySelectorAll('[data-wb-claim]')];
  const wanted = new Map(w.columns.flatMap((c) => c.claims.map((x) => [x.id, c] as const)));
  for (const b of allBlocks) if (!wanted.has(b.getAttribute('data-wb-claim') ?? '')) problems.push(`the table shows ${b.getAttribute('data-wb-claim')}, which the selection does not keep`);
  let diffs = 0;
  let unknowns = 0;
  let restricted = 0;
  for (const c of w.columns) {
    const th = table.querySelector(`thead th[data-col="${esc(c.id)}"]`);
    if (th == null) continue;
    if (th.getAttribute('data-col-state') !== c.state) problems.push(`${c.id}: shown as ${th.getAttribute('data-col-state')}, but the selection's keys and unknowns make it ${c.state}`);
    if (th.getAttribute('data-claims-total') !== String(c.claims.length)) problems.push(`${c.id}: counts ${th.getAttribute('data-claims-total')} claims, of the ${c.claims.length} it keeps`);
    // every claim in exactly one cell, its own
    for (const x of c.claims) {
      const found = allBlocks.filter((b) => b.getAttribute('data-wb-claim') === x.id);
      if (found.length === 0) {
        problems.push(`${c.id}: ${x.id} is dropped silently, in no cell and counted nowhere`);
        continue;
      }
      if (found.length > 1) problems.push(`${c.id}: ${x.id} is drawn ${found.length} times`);
      const b = found[0];
      if (b.closest('td')?.getAttribute('data-col') !== c.id || b.closest('tr')?.getAttribute('data-system') !== x.system) {
        problems.push(`${c.id}: ${x.id} is drawn in ${b.closest('tr')?.getAttribute('data-system')}'s ${b.closest('td')?.getAttribute('data-col')} cell`);
      }
      if (b.getAttribute('data-key') !== x.key) problems.push(`${x.id}: drawn under key ${b.getAttribute('data-key')}, not its ${x.key}`);
      if (b.getAttribute('data-set') !== x.label) problems.push(`${c.id}: ${x.id} is labelled set ${b.getAttribute('data-set')}, but its key is set ${x.label}`);
      const tag = b.querySelector(':scope > [data-set-label]');
      if ((c.state === 'not-comparable') !== (tag != null) || (tag != null && tag.textContent?.trim() !== `Set ${x.label}`)) {
        problems.push(`${c.id}: ${x.id}'s cell ${tag == null ? 'does not say' : `says "${tag.textContent}" for`} which of ${c.sets.length} condition sets it is in`);
      }
      if (x.numbered && b.querySelector('[data-prov] summary :is([data-meter], [data-absent="not-applicable"])') == null) problems.push(`${x.id}: its number has no condition meter`);
      const marker = b.querySelector('[data-unknown-marker]');
      const named = marker == null ? [] : [...marker.querySelectorAll('code')].map((e) => e.textContent ?? '');
      if (JSON.stringify(named) !== JSON.stringify(x.unknown)) problems.push(`${x.id}: the cell marks [${named.join(', ')}] unknown, where [${x.unknown.join(', ')}] is`);
      if (b.querySelector(`a[data-claim-permalink="${esc(x.id)}"][href="/claims/${x.id}/"]`) == null) problems.push(`${x.id}: no permalink beside its number`);
      if (x.ingested != null && b.querySelector(`:scope > [data-attribution="${esc(x.ingested)}"]`) == null) problems.push(`${x.id}: an ingested claim without its attribution inline (04 S9)`);
    }
    // an empty cell says so; a cell whose claims a restriction dropped counts them
    for (const s of w.systems) {
      const td = table.querySelector(`tr[data-system="${esc(s.id)}"] td[data-col="${esc(c.id)}"]`);
      if (td == null) {
        problems.push(`${s.id} has no ${c.id} cell`);
        continue;
      }
      const has = c.claims.filter((x) => x.system === s.id).length;
      const gone = c.dropped.filter((x) => x.system === s.id).length;
      const said = Number(td.querySelector('[data-wb-dropped]')?.getAttribute('data-wb-dropped') ?? 0);
      if (said !== gone) problems.push(`${s.id}'s ${c.id} cell: ${gone} of its claims dropped by the restriction, and it counts ${said}`);
      if (has === 0 && gone === 0 && td.querySelector('[data-wb-none] [data-absent]') == null) problems.push(`${s.id}'s ${c.id} cell is empty, and does not say so`);
    }
    // the banners: the diff of a column spanning sets, the unknowns of a set agreeing in ignorance, a restriction's count
    const sec = banners(c.id);
    const diff = sec?.querySelector('[data-comparability]') ?? null;
    if (c.state !== 'not-comparable') {
      if (diff != null) problems.push(`${c.id}: one condition set, but a diff`);
    } else if (diff == null) {
      problems.push(`${c.id}: spans ${c.sets.length} condition sets with no field-by-field diff`);
    } else {
      diffs += 1;
      if (!c.deferred) {
        const rows = [...diff.querySelectorAll('tr[data-diff-field]')];
        const named = rows.map((r) => r.getAttribute('data-diff-field') ?? '').sort();
        const differ = Object.keys(c.fields).sort();
        if (JSON.stringify(named) !== JSON.stringify(differ)) problems.push(`${c.id}: the diff names [${named.join(', ')}], but its claims differ in [${differ.join(', ')}]`);
        const cols = [...diff.querySelectorAll('thead th[data-set-col]')].map((x) => x.getAttribute('data-set-col') ?? '');
        if (JSON.stringify(cols) !== JSON.stringify(c.sets.map((x) => x.label))) problems.push(`${c.id}: the diff's sets are [${cols.join(', ')}], not [${c.sets.map((x) => x.label).join(', ')}]`);
        for (const r of rows) {
          const field = r.getAttribute('data-diff-field') ?? '';
          const cells = [...r.querySelectorAll('td')];
          c.sets.forEach((set, i) => {
            const v = c.fields[field]?.[set.claims[0].id];
            const kind = v === '?' ? 'unknown' : v === null ? 'none' : 'value';
            const td = cells[i];
            const ok = td != null && td.getAttribute('data-cell') === kind && (kind !== 'unknown' || td.querySelector('[data-absent="unknown"]') != null)
              && (kind !== 'value' || (td.textContent ?? '').trim() === show(v));
            if (!ok) problems.push(`${c.id}: set ${set.label}'s ${field} reads "${(td?.textContent ?? '').trim()}", where its claims have ${JSON.stringify(v)}`);
          });
        }
      }
      const drops = c.claims.length - c.sets[0].claims.length;
      const restrict = diff.querySelector('a[data-action="restrict"]');
      const said = (restrict?.textContent ?? '').replace(/\s+/g, ' ');
      if (restrict == null || restrict.getAttribute('data-dropped') !== String(drops) || !said.includes(`(${drops} of ${c.claims.length} claims dropped)`)) {
        problems.push(`${c.id}: restricting it to one condition set drops ${drops} of ${c.claims.length} claims, and the control does not say so`);
      } else if (!(restrict.getAttribute('href') ?? '').includes(`k=`)) {
        problems.push(`${c.id}: the restrict control links no restriction`);
      }
      if (diff.querySelector('a[data-action="proceed"]') == null) problems.push(`${c.id}: no way to proceed with every affected cell flagged`);
    }
    for (const set of c.sets) {
      const banner = sec?.querySelector(`[data-set-banner="${set.label}"] [data-comparability-unknown]`) ?? null;
      const ignorant = set.claims.filter((x) => x.unknown.length > 0);
      if (set.claims.length > 1 && ignorant.length > 0) {
        if (banner == null) {
          problems.push(`${c.id}: set ${set.label} shows ${set.claims.length} claims together while ${[...new Set(ignorant.flatMap((x) => x.unknown))].join(', ')} `
            + 'is unknown on them: agreement in ignorance shown as confirmed comparability');
          continue;
        }
        unknowns += 1;
        for (const x of set.claims) {
          const named = [...(banner.querySelector(`tr[data-unknown-claim="${esc(x.id)}"]`)?.querySelectorAll('[data-unknown-field]') ?? [])].map((e) => e.getAttribute('data-unknown-field'));
          if (JSON.stringify(named) !== JSON.stringify(x.unknown)) problems.push(`${c.id}: the banner names [${named.join(', ')}] unknown on ${x.id}, which leaves [${x.unknown.join(', ')}] unknown`);
        }
        if (banner.querySelector('button, details, dialog, [hidden]') != null || banner.hasAttribute('hidden')) problems.push(`${c.id}: set ${set.label}'s banner can be dismissed`);
      } else if (banner != null) {
        problems.push(`${c.id}: set ${set.label} carries an unknowns banner, but nothing it shows together is unknown`);
      }
    }
    const note = sec?.querySelector('[data-wb-restricted]') ?? null;
    if (c.dropped.length > 0) {
      if (note == null || note.getAttribute('data-dropped') !== String(c.dropped.length)) {
        problems.push(`${c.id}: ${c.dropped.length} claims dropped by the restriction and counted nowhere`);
      } else restricted += 1;
    } else if (note != null) problems.push(`${c.id}: says a restriction dropped claims, but none is dropped`);
    if (c.state === 'comparable' && sec != null) problems.push(`${c.id}: one key and nothing unknown is shown silently, but carries a banner`);
  }
  return { problems, blocks: allBlocks.length, diffs, unknowns, restricted };
}

const audited = (page: Page, html: string, w: Want, doctor: Doctor | null = null, target: string | null = null) =>
  page.evaluate(audit, { html, w, doctor, target });
async function served(page: Page, path: string): Promise<string> {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
}

// ---- the page's script, with the data it fetches served -------------------------------------------------------------

let hrefs: { claims: string; comparability: string; corpus: string } | undefined;
/** The content-hashed URLs the page names, read off the page as sent. */
async function dataHrefs(page: Page) {
  if (hrefs) return hrefs;
  const html = await served(page, '/compare/');
  const attr = (name: string) => new RegExp(`data-${name}-href="([^"]+)"`).exec(html)?.[1];
  const [claims, comparability, corpus] = [attr('claims'), attr('comparability'), attr('corpus')];
  expect(claims && comparability && corpus, 'the page names its three artifacts by their hashed URLs').toBeTruthy();
  hrefs = { claims: claims!, comparability: comparability!, corpus: corpus! };
  return hrefs;
}
/** A context that runs scripts and is served the artifacts at the URLs the page names; `claims` replaces claims.json. */
async function live(browser: Browser, page: Page, baseURL: string | undefined,
  { claims = join(DIR, 'claims.json'), colorScheme = 'light' as 'light' | 'dark' } = {}) {
  const h = await dataHrefs(page);
  const ctx = await browser.newContext({ javaScriptEnabled: true, colorScheme, baseURL });
  const files: Record<string, string> = { [h.claims]: claims, [h.comparability]: join(DIR, 'derived', 'comparability.json'), [h.corpus]: join(PREVIEW, 'corpus.json') };
  const requested: string[] = [];
  ctx.on('request', (r) => requested.push(new URL(r.url()).pathname));
  await ctx.route('**/data/**', (route) => {
    const file = files[new URL(route.request().url()).pathname];
    return file != null ? route.fulfill({ path: file, contentType: 'application/json' }) : route.fulfill({ status: 404, body: '' });
  });
  return { ctx, page: await ctx.newPage(), requested };
}
const settled = (page: Page) => page.waitForFunction(() => {
  const s = document.querySelector<HTMLElement>('[data-workbench]')?.dataset.workbenchLive;
  return s != null && s !== 'static' && s !== 'loading';
}, null, { timeout: 60_000 });
const liveState = (page: Page) => page.locator('[data-workbench]').getAttribute('data-workbench-live');

// ---- choosing selections from the fixture ---------------------------------------------------------------------------

/** The first column, by benchmark then metric, that spans condition sets (and, if `ignorant`, holds a set agreeing in
 *  ignorance), over the whole index. */
function refusedColumn(ignorant = false): WantColumn {
  const all = want({ b: [], k: [], sys: [] });
  const hit = [...all.columns].sort((a, b) => byCodePoint(a.id, b.id)).find((c) => c.state === 'not-comparable'
    && (!ignorant || c.sets.some((s) => s.claims.length > 1 && s.claims.some((x) => x.unknown.length > 0))));
  expect(hit, `a column spanning condition sets${ignorant ? ' with a set of possibly comparable claims' : ''} in the fixture`).toBeDefined();
  return hit!;
}
/** A pasted list: a refused column's benchmark, a system from each of its first two sets, a claim on another benchmark,
 *  and an id this build does not have. */
function pasteList() {
  const c = refusedColumn(true);
  const bench = c.id.split('|')[0];
  const [a, b] = [c.sets[0].claims[0].system, c.sets[1].claims.find((x) => x.system !== c.sets[0].claims[0].system)?.system ?? c.sets[1].claims[0].system];
  const other = fixture().rows.find((r) => family(r.claim.benchmark) !== bench)!;
  const sel: Sel = { b: [bench, family(other.claim.benchmark)], k: [], sys: [a, b, systemOf(other.claim.system)] };
  return { column: c, tokens: [bench, a, b, other.claim.id, 'no-such-id-e2e'], sel };
}

test.beforeAll(async ({ request }) => {
  expect((await request.get('/claims/claim-e2e000000001/')).status(), 'the server on the baseURL was built from build/e2e-claims (playwright.config.ts)').toBe(200);
});

test.describe('with JavaScript disabled', () => {
  test.use({ javaScriptEnabled: false });

  test('the bare address renders every curated claim as the table, with every banner already computed', async ({ page }) => {
    const { rows } = fixture();
    const w = want({ b: [], k: [], sys: [] });
    expect(w.claims, 'every claims.json row is in the unconstrained selection').toBe(rows.length);
    expect(w.columns.some((c) => c.state === 'not-comparable')).toBe(true);
    expect(w.columns.some((c) => c.state === 'comparable')).toBe(true);
    expect(w.columns.some((c) => c.sets.some((s) => s.claims.length > 1 && s.claims.some((x) => x.unknown.length > 0)))).toBe(true);
    const html = await served(page, '/compare/');
    const a = await audited(page, html, w);
    expect(a.problems).toEqual([]);
    expect(a.blocks).toBe(rows.length);
    expect(rows.some((r) => r.claim.ingestion != null), 'the fixture\'s ingested curated claim is in the table, with its attribution').toBe(true);
    expect(a.diffs).toBe(w.columns.filter((c) => c.state === 'not-comparable').length);
    expect(a.unknowns).toBe(w.columns.reduce((n, c) => n + c.sets.filter((s) => s.claims.length > 1 && s.claims.some((x) => x.unknown.length > 0)).length, 0));
    // as a reader without a script sees it: the table, the banners above it, the notice saying what is shown
    await page.goto('/compare/');
    await expect(page.locator('[data-workbench]')).toHaveAttribute('data-workbench-live', 'static');
    await expect(page.locator('table[data-wb-table] tbody tr').first()).toBeVisible();
    await expect(page.locator('[data-wb-banners] [data-comparability]').first()).toBeVisible();
    await expect(page.locator('[data-wb-static]')).toBeVisible();
    await expect(page.locator('[data-wb-static]')).toContainText('without JavaScript that selection is not applied');
    // the page as sent fetches no data: the three artifacts are named only for the script
    for (const name of ['claims', 'comparability', 'corpus']) expect(html).toMatch(new RegExp(`data-${name}-href="/data/`));
    expect(html).not.toMatch(/<link[^>]+href="\/data\//);
  });

  test('a pasted selection without JavaScript is not applied, and the page says so rather than pretending', async ({ page }) => {
    const { tokens, sel } = pasteList();
    const all = want({ b: [], k: [], sys: [] });
    for (const path of [`/compare/?ids=${encodeURIComponent(tokens.join(' '))}&k=`, `/compare/?${canonical(sel)}`]) {
      await page.goto(path);
      const a = await audited(page, await page.content(), all);
      expect(a.problems, `${path}: the unconstrained table, labelled as such`).toEqual([]);
      await expect(page.locator('[data-workbench-view]')).toHaveAttribute('data-selection', '');
      await expect(page.locator('[data-wb-static]')).toBeVisible();
      await expect(page.locator('[data-wb-summary]')).toContainText('the bare address constraining nothing');
    }
    // the form sends the paste as a GET, which a later renderer can read
    await page.goto('/compare/');
    await page.locator('textarea[name="ids"]').fill(tokens.join('\n'));
    await page.locator('[data-wb-form] button[type="submit"]').click();
    expect(new URL(page.url()).searchParams.get('ids')?.replace(/\r\n/g, '\n')).toBe(tokens.join('\n'));
    await expect(page.locator('[data-workbench-view]')).toHaveAttribute('data-selection', '');
  });
});

test.describe('with JavaScript', () => {
  test('a pasted selection renders its table with its banners computed for it, and names what it ignored', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const { tokens, sel, column } = pasteList();
    const w = want(sel);
    const { ctx, page } = await live(browser, probe, baseURL);
    await page.goto('/compare/');
    await settled(page);
    expect(await liveState(page)).toBe('ready');
    await expect(page.locator('[data-wb-static]')).toHaveCount(0);
    await page.locator('textarea[name="ids"]').fill(tokens.join('\n'));
    await page.locator('[data-wb-form] button[type="submit"]').click();
    await settled(page);
    expect(await liveState(page)).toBe('applied');
    expect(new URL(page.url()).search, 'the paste is rewritten to its canonical selection').toBe(`?${w.selection}`);
    const a = await audited(page, await page.content(), w);
    expect(a.problems).toEqual([]);
    expect(a.blocks).toBe(w.claims);
    expect(w.columns.find((c) => c.id === column.id)?.state, 'the chosen column still spans sets in the selection').toBe('not-comparable');
    expect(a.diffs).toBe(w.columns.filter((c) => c.state === 'not-comparable').length);
    await expect(page.locator('[data-wb-ignored] li[data-ignored-key="ids"][data-ignored-value="no-such-id-e2e"]')).toBeVisible();
    await expect(page.locator('textarea[name="ids"]')).toHaveValue([...new Set(sel.b)].sort(byCodePoint).concat([...new Set(sel.sys)].sort(byCodePoint)).join(' '));
    await ctx.close();
  });

  test('restricting a column to one condition set keeps it, and counts every claim it drops', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const { sel, column } = pasteList();
    const { ctx, page } = await live(browser, probe, baseURL);
    await page.goto(`/compare/?${canonical(sel)}`);
    await settled(page);
    const restrict = page.locator(`[data-wb-col-banners="${column.id}"] [data-comparability] a[data-action="restrict"]`);
    await expect(restrict).toBeVisible();
    await restrict.click();
    await settled(page);
    expect(await liveState(page)).toBe('applied');
    const k = new URL(page.url()).searchParams.get('k');
    expect(k, 'the restriction is in the address').toBeTruthy();
    const w = want({ ...sel, k: k!.split(',') });
    expect(w.dropped).toBeGreaterThan(0);
    const a = await audited(page, await page.content(), w);
    expect(a.problems).toEqual([]);
    expect(a.restricted).toBe(w.columns.filter((c) => c.dropped.length > 0).length);
    await expect(page.locator(`[data-wb-col-banners="${column.id}"] [data-wb-restricted]`)).toContainText(`${w.dropped} of `);
    await expect(page.locator(`th[data-col="${column.id}"]`)).not.toHaveAttribute('data-col-state', 'not-comparable');
    await ctx.close();
  });

  test('a selection of one condition set\'s systems shows the column without the diff its whole group needs', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    // the first column spanning sets in which some system's claims are all in set A
    const onlyA = (c: WantColumn) => {
      const others = new Set(c.sets.slice(1).flatMap((s) => s.claims.map((x) => x.system)));
      return [...new Set(c.sets[0].claims.map((x) => x.system))].filter((s) => !others.has(s));
    };
    const c = [...want({ b: [], k: [], sys: [] }).columns].sort((a, b) => byCodePoint(a.id, b.id))
      .find((x) => x.state === 'not-comparable' && onlyA(x).length > 0);
    expect(c, 'a column spanning condition sets with a system whose claims are all in its set A').toBeDefined();
    const bench = c!.id.split('|')[0];
    const w = want({ b: [bench], k: [], sys: onlyA(c!) });
    expect(w.columns.find((x) => x.id === c!.id)?.state).not.toBe('not-comparable');
    const { ctx, page } = await live(browser, probe, baseURL);
    await page.goto(`/compare/?${w.selection}`);
    await settled(page);
    const a = await audited(page, await page.content(), w);
    expect(a.problems).toEqual([]);
    await expect(page.locator(`[data-wb-col-banners="${c!.id}"] [data-comparability]`)).toHaveCount(0);
    await expect(page.locator(`th[data-col="${c!.id}"]`)).not.toHaveAttribute('data-col-state', 'not-comparable');
    await ctx.close();
  });

  test('corpus.json is loaded on entering the workbench, and by no page before it', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const h = await dataHrefs(probe);
    const { ctx, page, requested } = await live(browser, probe, baseURL);
    for (const path of ['/', '/benchmarks/', `/benchmarks/${refusedColumn().id.split('|')[0]}/`]) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
    }
    expect(requested.filter((p) => p === h.corpus), 'no other view loads corpus.json').toEqual([]);
    await page.goto('/compare/');
    await settled(page);
    expect(requested.filter((p) => p === h.corpus).length, 'the workbench loads it, once').toBe(1);
    expect(requested.indexOf(h.claims)).toBeLessThan(requested.indexOf(h.corpus));
    await ctx.close();
  });

  test('claims that are not the ones the table was built from are refused, and nothing is applied', async ({ browser, page: probe, baseURL }) => {
    test.setTimeout(180_000);
    const { sel } = pasteList();
    const { ctx, page } = await live(browser, probe, baseURL, { claims: join(PREVIEW, 'claims.json') });
    await page.goto(`/compare/?${canonical(sel)}`);
    await settled(page);
    expect(await liveState(page)).toBe('failed');
    await expect(page.locator('[data-wb-status]')).toContainText('not the ones its table was built from');
    const a = await audited(page, await page.content(), want({ b: [], k: [], sys: [] }));
    expect(a.problems, 'the build\'s unconstrained table stays').toEqual([]);
    await ctx.close();
  });
});

test('the failure cases: a missing or wrong banner, a claim dropped, a dropped claim not counted, are reported', async ({ browser, page, baseURL }) => {
  test.setTimeout(240_000);
  await page.goto('about:blank');
  const all = want({ b: [], k: [], sys: [] });
  const html = await served(page, '/compare/');
  const refused = refusedColumn(true);
  const comparable = all.columns.find((c) => c.state === 'comparable')!;
  const cases: [string, Want, Doctor, string, RegExp][] = [
    [html, all, 'drop-diff', refused.id, /spans \d+ condition sets with no field-by-field diff/],
    [html, all, 'short-diff', refused.id, /the diff names \[.*\], but its claims differ in/],
    [html, all, 'drop-unknowns', refused.id, /agreement in ignorance shown as confirmed comparability/],
    [html, all, 'hide-count', refused.id, /drops \d+ of \d+ claims, and the control does not say so/],
    [html, all, 'drop-claim', comparable.id, /is dropped silently, in no cell and counted nowhere/],
    [html, all, 'relabel-column', refused.id, /shown as comparable, but the selection's keys and unknowns make it not-comparable/],
  ];
  // the same on the script's own render of a restricted selection
  const { sel, column } = pasteList();
  const { ctx, page: p } = await live(browser, page, baseURL);
  const k = refused.sets[0].key;
  const ws = want({ ...sel, k: [k] });
  await p.goto(`/compare/?${ws.selection}`);
  await settled(p);
  const rendered = await p.content();
  await ctx.close();
  expect(ws.columns.find((c) => c.id === column.id)?.dropped.length).toBeGreaterThan(0);
  cases.push([rendered, ws, 'uncount-restriction', column.id, /dropped by the restriction and counted nowhere|of its claims dropped by the restriction, and it counts 0/]);
  cases.push([rendered, ws, 'drop-claim', column.id, /is dropped silently, in no cell and counted nowhere/]);
  for (const [body, w, doctor, target, expected] of cases) {
    const clean = await audited(page, body, w);
    expect(clean.problems, `${target} as rendered`).toEqual([]);
    const bad = await audited(page, body, w, doctor, target);
    expect(bad.problems.some((x) => expected.test(x)), `${target} doctored by ${doctor}: ${JSON.stringify(bad.problems)}`).toBe(true);
  }
});

test('the workbench reads accessibly: axe at WCAG 2.2 AA over the build\'s table and a selection, light and dark', async ({ browser, page: probe, baseURL }) => {
  test.setTimeout(300_000);
  const tags = (JSON.parse(readFileSync(join(ROOT, 'site', 'test', 'a11y', 'archetypes.json'), 'utf8')) as { standard: { axe: string[] } }).standard.axe;
  const { sel } = pasteList();
  for (const colorScheme of ['light', 'dark'] as const) {
    // axe is injected as a script, so this context runs one
    const { ctx, page } = await live(browser, probe, baseURL, { colorScheme });
    for (const path of ['/compare/', `/compare/?${canonical(sel)}`]) {
      await page.goto(path);
      await settled(page);
      const r = await new AxeBuilder({ page }).include('main').withTags(tags).analyze();
      expect(r.passes.length, `${path} ${colorScheme}: axe ran rules`).toBeGreaterThan(0);
      expect(r.violations.map((v) => `${v.id}: ${v.nodes.slice(0, 5).map((n) => n.target.join(' ')).join('; ')}`), `${path} ${colorScheme}`).toEqual([]);
    }
    await ctx.close();
  }
});
