// tests/e2e/provenance-drilldown.spec.ts -- P3-S10-T07: the provenance drill-down and the verification badges (10 V6
// "The provenance drill-down", "Information architecture"; 04 S7, S9; 07 S2.3; 08 S4.3, S7.5).
//
//   npx playwright test tests/e2e/provenance-drilldown.spec.ts
//
// Runs against the site built from the draft preview with build/e2e-claims/'s claims artifacts
// (playwright.config.ts): the preview's real curated claims plus the two constructed ingested rows
// tests/e2e/fixtures/make_claims_fixture.py adds, because no committed claim is ingested yet. Every page is read
// with JavaScript disabled: /claims/{id}/ and /conditions/{id}/ are citation targets that ship none (08 S4.3).
//
// Done when: "Every number on the site is one click from the record it came from, and the CC-BY attribution renders
// with every ingested claim." So:
//   - every curated claim has its page, the drill-down standalone and open: the number, its badge, the source and
//     its archive link, the provenance snapshot, the conditions, and its permalink; every condition record a claim
//     names has its page, with the claims run under it; a machine-ingested claim has none (08 S7.5 Decision 1);
//   - every page that renders a claim's number -- its own page, its condition record's, its benchmark's, its
//     system's -- is audited: each number (an element carrying data-claim-value) has a link to /claims/{id}/ inside
//     the claim's own scope (its list item, its drill-down or its page), and each verification badge carries a review
//     state beside its rank (07 S2.3: "Verification rank and review state render together, always");
//   - every ingested claim shows its attribution inline wherever it renders, and a machine-ingested one is counted
//     with its attribution on its benchmark's page and its number is rendered nowhere.
// The failure cases the verify names are checked as failures: a real page is audited again doctored, once with its
// permalinks taken out and once with its badges' review state taken out, and each must be reported.
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test.use({ javaScriptEnabled: false });

interface Ingestion { batch: string; source_attribution: string; source_licence: string; review_state?: string }
interface Row {
  claim: {
    id: string; system: string; benchmark: string; metric: string; opponent?: string | null; value: number | null;
    value_text?: string | null; verification: string; ingestion: Ingestion | null; source: string;
    provenance_snapshot: { source_record_id: string | null } | null;
  };
  conditions: ({ id: string } & Record<string, unknown>) | null;
  comparability: { unknown_fields: string[] };
  source: { url: string; archive_url: string | null } | null;
  badge?: string;
}
interface Fixture { curated: Row[]; machine: Row[]; systems: Set<string>; benchmarks: Set<string> }

const ROOT = join(__dirname, '..', '..');
const DIR = join(ROOT, 'build', 'e2e-claims');                  // make_claims_fixture.py --out, playwright.config.ts
const REVIEW = ['machine-ingested', 'spot-checked', 'human-reviewed', 'promoted', 'hand-curated'];
const PREPAINT = '<script data-prepaint>';

let memo: Fixture | undefined;
/** The artifacts the server was built from, read when a test needs them: the webServer writes them first. */
function fixture(): Fixture {
  if (memo) return memo;
  const read = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
  const claims = read(join(DIR, 'claims.json')) as { claims: Row[]; machine_ingested: Record<string, number> };
  const machine = Object.keys(claims.machine_ingested).flatMap((b) => (read(join(DIR, 'claims-ingested', `${b}.json`)) as { claims: Row[] }).claims);
  const corpus = read(join(ROOT, 'build', 'preview', 'corpus.json')) as { entities: { system: { id: string }[]; benchmark: { id: string }[] } };
  memo = { curated: claims.claims, machine, systems: new Set(corpus.entities.system.map((s) => s.id)),
    benchmarks: new Set(corpus.entities.benchmark.map((b) => b.id)) };
  return memo;
}
const base = (ref: string) => ref.split('@', 1)[0].split('#', 1)[0];
const review = (r: Row) => (r.claim.ingestion == null ? 'hand-curated' : r.claim.ingestion.review_state ?? 'machine-ingested');
const numbered = (r: Row) => r.claim.value != null || (r.claim.value_text != null && r.claim.value_text !== '');
const claimPath = (id: string) => `/claims/${id}/`;

interface Audit { problems: string[]; numbers: string[]; badges: number }

/** What is wrong with one page's numbers and badges, read from its HTML in the browser (a DOMParser document, so a
 *  doctored copy is audited exactly as the page is): a claim number with no link to its own claim's permalink inside
 *  the claim's scope, and a verification badge that renders its rank without a review state. */
function audit({ html, states }: { html: string; states: string[] }): Audit {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const problems: string[] = [];
  const numbers = [...doc.querySelectorAll('[data-claim-value]')];
  for (const el of numbers) {
    const id = el.getAttribute('data-claim-value') ?? '';
    const href = `/claims/${id}/`;
    const scope = el.closest('[data-claim], [data-prov]');
    if (scope == null || scope.querySelector(`a[href="${href}"]`) == null) {
      problems.push(`the number ${JSON.stringify((el.textContent ?? '').trim())} of ${id} has no link to its permalink ${href}`);
    }
  }
  const badges = [...doc.querySelectorAll('[data-verification]')];
  for (const b of badges) {
    const state = b.getAttribute('data-review-state');
    const mark = (b.querySelector('.review')?.textContent ?? '').trim();
    if (state == null || !states.includes(state) || mark !== state) {
      problems.push(`a ${b.getAttribute('data-verification')} badge renders rank ${b.getAttribute('data-rank')} without its review_state`);
    }
  }
  return { problems, numbers: numbers.map((n) => n.getAttribute('data-claim-value') ?? ''), badges: badges.length };
}

async function html(page: Page, path: string): Promise<string> {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
}
async function audited(page: Page, body: string): Promise<Audit> {
  return page.evaluate(audit, { html: body, states: REVIEW });
}
/** Every page that renders a claim's number, with the claim ids whose numbers it must show. */
function pages(f: Fixture): Map<string, string[]> {
  const out = new Map<string, string[]>();
  const add = (path: string, id: string | null) => {
    const ids = out.get(path) ?? [];
    if (id != null) ids.push(id);
    out.set(path, ids);
  };
  for (const r of f.curated) {
    const id = numbered(r) ? r.claim.id : null;
    add(claimPath(r.claim.id), id);
    if (r.conditions != null) add(`/conditions/${r.conditions.id}/`, id);
    if (f.benchmarks.has(base(r.claim.benchmark))) add(`/benchmarks/${base(r.claim.benchmark)}/`, id);
    for (const s of new Set([r.claim.system, r.claim.opponent].filter((x): x is string => x != null).map(base))) {
      if (f.systems.has(s)) add(`/systems/${s}/`, id);
    }
  }
  for (const r of f.machine) add(`/benchmarks/${base(r.claim.benchmark)}/`, null);
  return out;
}

test.beforeAll(async ({ request }) => {
  const f = fixture();
  // a server left running from a build without the fixture would make the ingested half vacuous
  expect(f.curated.filter((r) => r.claim.ingestion != null).length, 'the fixture carries a curated ingested claim').toBeGreaterThan(0);
  expect(f.machine.length, 'the fixture carries a machine-ingested claim').toBeGreaterThan(0);
  const probe = f.curated.find((r) => r.claim.ingestion != null)!;
  expect((await request.get(claimPath(probe.claim.id))).status(),
    'the server on the baseURL was built from build/e2e-claims (playwright.config.ts)').toBe(200);
});

test('every curated claim has its page: the drill-down open, the source and its archive, the snapshot, the permalink', async ({ page }) => {
  test.setTimeout(300_000);
  const f = fixture();
  expect(f.curated.length).toBeGreaterThanOrEqual(90);
  await page.goto('about:blank');
  for (const r of f.curated) {
    const id = r.claim.id;
    const body = await html(page, claimPath(id));
    const facts = await page.evaluate(({ body, id }) => {
      const doc = new DOMParser().parseFromString(body, 'text/html');
      const article = doc.querySelector(`article[data-claim-page="${id}"]`);
      const d = article?.querySelector(`details[data-prov="${id}"]`);
      const row = (name: string) => d?.querySelector(`[data-prov-row="${name}"]`) ?? null;
      return {
        article: article != null,
        open: d?.hasAttribute('open') ?? null,
        rows: [...(d?.querySelectorAll('[data-prov-row]') ?? [])].map((x) => x.getAttribute('data-prov-row')),
        sourceLinks: [...(row('source')?.querySelectorAll('a') ?? [])].map((a) => a.getAttribute('href')),
        archiveNone: row('source')?.querySelector('[data-archive="none"]') != null,
        snapshot: (row('provenance-snapshot')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
        permalink: [...(article?.querySelectorAll('a[data-claim-permalink]') ?? [])].map((a) => a.getAttribute('href')),
        conditions: article?.querySelector('[data-field="conditions"] a[data-conditions-link]')?.getAttribute('href') ?? null,
        badge: [...(article?.querySelectorAll('[data-verification]') ?? [])].map((b) => [b.getAttribute('data-verification'), b.getAttribute('data-review-state')]),
        attribution: article?.querySelectorAll('[data-attribution]').length ?? 0,
        record: article?.querySelectorAll('dl.pairs > div').length ?? 0,
      };
    }, { body, id });
    expect(facts.article, id).toBe(true);
    expect(facts.record, `${id}: the record list`).toBeGreaterThan(5);
    expect(facts.permalink, `${id}: its permalink`).toContain(claimPath(id));
    expect(facts.badge.length, `${id}: a badge`).toBeGreaterThan(0);
    for (const [v, s] of facts.badge) expect([v, s], `${id}: rank and review state together`).toEqual([r.claim.verification, review(r)]);
    expect(facts.conditions, `${id}: its condition record`).toBe(r.conditions != null ? `/conditions/${r.conditions.id}/` : null);
    expect(facts.attribution > 0, `${id}: an attribution exactly when ingested`).toBe(r.claim.ingestion != null);
    expect([...body.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), `${id}: no JavaScript (08 S4.3)`).toEqual([PREPAINT]);
    if (!numbered(r)) {
      expect(facts.open, `${id}: no number, no drill-down`).toBeNull();
      continue;
    }
    expect(facts.open, `${id}: the drill-down, standalone and open`).toBe(true);
    for (const name of ['source', 'date-reported', 'reported-by', 'verification', 'comparability-key', 'artifact', 'provenance-snapshot',
      'conditions', 'unknown-fields', 'permalink']) expect(facts.rows, `${id}: ${name}`).toContain(name);
    if (r.source != null) {
      expect(facts.sourceLinks, `${id}: the source`).toContain(r.source.url);
      if (r.source.archive_url != null) expect(facts.sourceLinks, `${id}: its archive copy`).toContain(r.source.archive_url);
      else expect(facts.archiveNone, `${id}: says it is not archived`).toBe(true);
    }
    if (r.claim.provenance_snapshot?.source_record_id != null) expect(facts.snapshot, id).toContain(r.claim.provenance_snapshot.source_record_id);
    else if (r.claim.ingestion == null) expect(facts.snapshot, id).toContain('curated by hand');
  }
});

test('every rendered number links to its claim permalink, and no badge renders rank without review_state', async ({ page }) => {
  test.setTimeout(300_000);
  const f = fixture();
  const all = pages(f);
  const machine = new Set(f.machine.map((r) => r.claim.id));
  expect(all.size, 'claim, condition, benchmark and system pages').toBeGreaterThan(f.curated.length);
  await page.goto('about:blank');
  let numbers = 0;
  let badges = 0;
  for (const [path, ids] of all) {
    const a = await audited(page, await html(page, path));
    expect(a.problems, path).toEqual([]);
    for (const id of ids) expect(a.numbers, `${path} renders ${id}'s number`).toContain(id);
    for (const id of a.numbers) expect(machine.has(id), `${path} renders machine-ingested ${id}'s number`).toBe(false);
    numbers += a.numbers.length;
    badges += a.badges;
  }
  expect(numbers, 'numbers audited').toBeGreaterThan(f.curated.length * 3);
  expect(badges, 'badges audited').toBeGreaterThanOrEqual(numbers);
});

test('the failure cases: a number with no permalink, and a badge with rank but no review_state, are reported', async ({ page }) => {
  const f = fixture();
  const r = f.curated.find((x) => numbered(x) && x.conditions != null && f.benchmarks.has(base(x.claim.benchmark)))!;
  await page.goto('about:blank');
  for (const path of [claimPath(r.claim.id), `/benchmarks/${base(r.claim.benchmark)}/`, `/conditions/${r.conditions!.id}/`]) {
    const body = await html(page, path);
    const clean = await audited(page, body);
    expect(clean.problems, path).toEqual([]);
    expect(clean.numbers, path).toContain(r.claim.id);

    // its permalinks pointed elsewhere: every number of that claim on the page is reported
    const unlinked = await audited(page, body.split(`href="${claimPath(r.claim.id)}"`).join('href="/elsewhere/"'));
    const lost = clean.numbers.filter((id) => id === r.claim.id).length;
    expect(unlinked.problems.filter((p) => p.includes(`of ${r.claim.id} has no link to its permalink`)), path).toHaveLength(lost);

    // every badge's review state taken out, attribute and mark: every badge is reported
    const bare = await audited(page, body.replace(/ data-review-state="[^"]*"/g, '').replace(/<span class="review"[^>]*>[^<]*<\/span>/g, ''));
    expect(bare.problems.filter((p) => /badge renders rank \d without its review_state/.test(p)), path).toHaveLength(clean.badges);
    // and the mark alone kept without the attribute, or the attribute without the mark, is no better
    const markless = await audited(page, body.replace(/<span class="review"[^>]*>[^<]*<\/span>/g, ''));
    expect(markless.problems.length, path).toBe(clean.badges);
  }
});

test('the CC-BY attribution renders inline with every ingested claim, wherever it renders', async ({ page }) => {
  test.setTimeout(120_000);
  const f = fixture();
  for (const r of f.curated.filter((x) => x.claim.ingestion != null)) {
    const g = r.claim.ingestion!;
    const where = [claimPath(r.claim.id), `/benchmarks/${base(r.claim.benchmark)}/`];
    if (r.conditions != null) where.push(`/conditions/${r.conditions.id}/`);
    if (f.systems.has(base(r.claim.system))) where.push(`/systems/${base(r.claim.system)}/`);
    for (const path of where) {
      await page.goto(path);
      const own = path === claimPath(r.claim.id);
      const section = page.locator('details[data-section="10"]:not([open]) > summary');
      if (await section.count() > 0) await section.click();      // the benchmark page's claims: native, no script runs
      // on its own page, in the open drill-down; in a list, beside the closed drill-down, never only inside it
      const line = own ? page.locator(`details[data-prov="${r.claim.id}"][open] [data-prov-row="attribution"] [data-attribution="${g.batch}"]`)
        : page.locator(`li[data-claim="${r.claim.id}"] > [data-attribution="${g.batch}"]`);
      await expect(line, path).toBeVisible();
      await expect(line.locator('[data-attribution-text]'), path).toHaveText(g.source_attribution.trim());
      await expect(line.locator('[data-attribution-licence]'), path).toHaveText(g.source_licence);
      const badge = page.locator(`${own ? `details[data-prov="${r.claim.id}"]` : `li[data-claim="${r.claim.id}"]`} summary [data-review-state="${review(r)}"]`);
      await expect(badge, `${path}: the review state beside the rank`).toBeVisible();
    }
    await page.goto(claimPath(r.claim.id));
    await expect(page.locator(`section[data-ingestion="${g.batch}"]`)).toBeVisible();
    await expect(page.locator('[data-prov-row="attribution"] [data-attribution]')).toBeVisible();
  }
  for (const r of f.machine) {
    const g = r.claim.ingestion!;
    expect(review(r)).toBe('machine-ingested');
    expect((await page.request.get(claimPath(r.claim.id))).status(), '08 S7.5 Decision 1: no permalink page').toBe(404);
    await page.goto(`/benchmarks/${base(r.claim.benchmark)}/`);
    await page.locator('details[data-section="10"] > summary').click();
    const counted = page.locator('[data-claims-ingested]');
    await expect(counted).toHaveAttribute('data-claims-ingested', String(f.machine.filter((x) => base(x.claim.benchmark) === base(r.claim.benchmark)).length));
    await expect(counted.locator(`[data-attribution="${g.batch}"] [data-attribution-text]`)).toHaveText(g.source_attribution.trim());
    await expect(counted.locator(`[data-attribution="${g.batch}"]`)).toBeVisible();
    await expect(page.locator(`[data-claim="${r.claim.id}"], [data-claim-value="${r.claim.id}"]`)).toHaveCount(0);
  }
  // and a hand-curated claim carries none, and says so on its badge
  const curated = f.curated.find((x) => x.claim.ingestion == null && numbered(x))!;
  await page.goto(claimPath(curated.claim.id));
  await expect(page.locator('[data-attribution]')).toHaveCount(0);
  await expect(page.locator('summary [data-review-state="hand-curated"] .review')).toHaveText('hand-curated');
});

test('every shared condition record has its page: what it answers, what each benchmark leaves unknown, its claims', async ({ page }) => {
  test.setTimeout(300_000);
  const f = fixture();
  const records = new Map<string, { conditions: NonNullable<Row['conditions']>; rows: Row[] }>();
  for (const r of f.curated) {
    if (r.conditions == null) continue;
    const hit = records.get(r.conditions.id) ?? { conditions: r.conditions, rows: [] };
    hit.rows.push(r);
    records.set(r.conditions.id, hit);
  }
  expect(records.size).toBeGreaterThan(50);
  await page.goto('about:blank');
  for (const [id, { conditions, rows }] of records) {
    const path = `/conditions/${id}/`;
    const body = await html(page, path);
    const facts = await page.evaluate(({ body, id }) => {
      const doc = new DOMParser().parseFromString(body, 'text/html');
      const article = doc.querySelector(`article[data-conditions="${id}"]`);
      return {
        article: article != null,
        named: (article?.querySelector('[data-field="named-by"] dd')?.textContent ?? '').trim(),
        fields: [...(article?.querySelectorAll('[data-cond-field]') ?? [])].map((x) => x.getAttribute('data-cond-field')),
        unknown: Object.fromEntries([...(article?.querySelectorAll('[data-unknown-for]') ?? [])].map((x) => [x.getAttribute('data-unknown-for'),
          [...x.querySelectorAll('[data-unknown-set] li code')].map((c) => c.textContent)])),
        claims: [...(article?.querySelectorAll('ul[data-claims] > li') ?? [])].map((li) => [li.getAttribute('data-claim'),
          li.querySelector('a[data-claim-permalink]')?.getAttribute('href') ?? null]),
      };
    }, { body, id });
    expect(facts.article, path).toBe(true);
    expect(facts.named, path).toBe(`${rows.length} ${rows.length === 1 ? 'claim' : 'claims'}`);
    const answered = Object.entries(conditions).filter(([k, v]) => k !== 'id' && v != null
      && !(typeof v === 'object' && !Array.isArray(v) && Object.values(v as object).every((x) => x == null))).map(([k]) => k);
    expect(facts.fields.sort(), `${path}: every field it answers, and only those`).toEqual(answered.sort());
    for (const r of rows) expect(facts.unknown[base(r.claim.benchmark)], `${path}: ${r.claim.id}'s unknown set`).toEqual(r.comparability.unknown_fields);
    expect(facts.claims.map(([c]) => c).sort(), path).toEqual(rows.map((r) => r.claim.id).sort());
    for (const [c, href] of facts.claims) expect(href, `${path}: ${c}'s permalink`).toBe(claimPath(c!));
    expect([...body.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), `${path}: no JavaScript (08 S4.3)`).toEqual([PREPAINT]);
  }
});

test('with JavaScript off, a claim page reads completely: the open drill-down, the record and the permalink are visible', async ({ page }) => {
  const f = fixture();
  const r = f.curated.find((x) => numbered(x) && x.claim.ingestion == null && x.conditions != null)!;
  await page.goto(claimPath(r.claim.id));
  const d = page.locator(`details[data-prov="${r.claim.id}"]`);
  await expect(d).toHaveAttribute('open', '');
  await expect(d.locator('.prov-list')).toBeVisible();
  await expect(d.locator('[data-prov-row="unknown-fields"]')).toBeVisible();
  await expect(page.locator('article[data-claim-page] dl.pairs').first()).toBeVisible();
  await expect(page.locator(`a[data-claim-permalink="${r.claim.id}"]`).last()).toBeVisible();
  await page.locator(`[data-field="conditions"] a[data-conditions-link]`).click();        // one click to the shared record
  await expect(page).toHaveURL(new RegExp(`/conditions/${r.conditions!.id}/$`));
  await expect(page.locator(`li[data-claim="${r.claim.id}"] > p a[data-claim-permalink]`)).toBeVisible();
});
