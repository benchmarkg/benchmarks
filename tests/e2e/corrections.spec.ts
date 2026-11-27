// tests/e2e/corrections.spec.ts -- P3-S10-T09: the /corrections/ page and /feed/corrections.xml (05 S8 "Corrections and
// disputes"; 10 V8, "a separate corrections feed", and "Information architecture").
//
//   npx playwright test tests/e2e/corrections.spec.ts
//
// Runs against the site the root playwright.config.ts builds: its corrections are tools/build/feed.py's `correction`
// events in tests/e2e/fixtures/feed-events.json (make_feed_events.py), its disputes the constructed records of
// tests/e2e/fixtures/disputes/ (UAIBI_DISPUTES), its organisations, sources and claims the draft preview's and
// build/e2e-claims/'s. Everything is read with JavaScript disabled: the page is a citable record that ships none.
//
// Done when: "Corrections are a published, linkable record rather than a quiet edit, which is the trust instrument 05
// §8 specifies." So:
//   - every published correction is on the page, newest first, at its own anchor, with 05 S8's five things: the date,
//     the entity, what it said before, what it says now, and who reported it (a dispute record's organisation or
//     role when its Correction: trailer names one, "not recorded" otherwise);
//   - every dispute is on the page with both positions and both sources; an open one is listed with the open
//     disputes and shown as unresolved, never dropped and never dressed as resolved;
//   - a reporter is named only as an organisation the corpus publishes; any other raiser renders as its neutral role,
//     and its raw value is printed nowhere;
//   - /feed/corrections.xml is RSS 2.0, checked by a real XML parser and against the specification's structure, and
//     carries an item for every correction and every dispute, each linking its anchor on the page;
//   - every claim page links the page from its footer.
// The failure cases the verify names are checked as failures: the page is audited again doctored -- a correction
// taken out, an open dispute taken out, an open dispute relabelled as resolved or moved to the closed list, a
// dispute's sources or a position taken out, a raiser's raw value printed -- and each must be reported; so must a feed
// with its channel link taken out or a malformed date, and a claim page without its footer link.
import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

test.use({ javaScriptEnabled: false });

// js-yaml is the site's dependency (site/package.json): the root harness has no YAML parser of its own, and the site's
// node_modules is installed for the build this spec reads
const { load } = createRequire(join(__dirname, '..', '..', 'site', 'package.json'))('js-yaml') as { load: (s: string) => unknown };

interface Change { field: string; before: unknown; after: unknown }
interface Ev { id: string; type: string; entity: string; path: string; date: string; commit: string; subject: string;
  publishable?: boolean; machine_ingested?: boolean; changes?: Change[]; disputes?: string[] }
interface Dispute { id: string; concerns: string; raised_by: string; disputant_relationship: string; raised_on: string;
  position: string; evidence: string[]; claim_sources: string[]; our_response?: string | null; status: string;
  resolved_on?: string | null; corrected_by?: string | null }

const ROOT = join(__dirname, '..', '..');
const FIX = join(__dirname, 'fixtures');
const PAGE = '/corrections/';
const FEED = '/feed/corrections.xml';
const PREPAINT = '<script data-prepaint>';
// The rule as this spec states it (lib/corrections.ts ROLE and STATUS_LABEL are the page's): an open dispute is
// "Unresolved"; a raiser that is no published organisation renders as its relationship's neutral role.
const ROLE: Record<string, string> = { 'evaluated-party': 'the evaluated party', 'benchmark-maintainer': "the benchmark's maintainers",
  'third-party': 'a third party', unknown: 'a reader' };
const CLOSED: Record<string, string> = { 'resolved-claim-corrected': 'Resolved: the claim was corrected',
  'resolved-claim-retained': 'Resolved: the claim was retained', withdrawn: 'Withdrawn by the disputant' };

const day = (v: unknown) => (v instanceof Date ? v.toISOString().slice(0, 10) : v == null ? null : String(v));
const events = JSON.parse(readFileSync(join(FIX, 'feed-events.json'), 'utf8')) as Ev[];
/** lib/feed.ts correctionEvents(): published, not machine-ingested, newest first as feed.py orders them. */
const CORRECTIONS = events.filter((e) => e.type === 'correction' && e.publishable !== false && !e.machine_ingested);
const DISPUTES: Dispute[] = readdirSync(join(FIX, 'disputes')).filter((n) => n.endsWith('.yaml')).sort().map((n) => {
  const r = load(readFileSync(join(FIX, 'disputes', n), 'utf8')) as Record<string, unknown>;
  return { ...r, status: (r.status as string) ?? 'open', raised_on: day(r.raised_on)!, resolved_on: day(r.resolved_on) } as Dispute;
});
const OPEN = DISPUTES.filter((d) => d.status === 'open');

let orgsMemo: Map<string, { name: string; kind: string }> | undefined;
/** The preview's organisations, read when a test needs them: the webServer writes the corpus first. */
function orgs() {
  orgsMemo ??= new Map((JSON.parse(readFileSync(join(ROOT, 'build', 'preview', 'corpus.json'), 'utf8')) as
    { entities: { organization: { id: string; name: string; kind: string }[] } }).entities.organization.map((o) => [o.id, o]));
  return orgsMemo;
}
/** Who the page may say raised `d`: an organisation it publishes (never one of kind individual), or the role. */
function raiser(d: Dispute): { org?: string; name?: string; role?: string } {
  const o = /^org-[a-z0-9]+(-[a-z0-9]+)*$/.test(d.raised_by) ? orgs().get(d.raised_by) : undefined;
  return o != null && o.kind !== 'individual' ? { org: d.raised_by, name: o.name } : { role: ROLE[d.disputant_relationship] };
}
/** lib/corrections.ts shown(): a changed value as the page prints it. */
const shown = (v: unknown) => (v == null ? null : Array.isArray(v) ? v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ')
  : typeof v === 'string' ? v : JSON.stringify(v));
const words = (s: string) => s.replace(/\s+/g, ' ').trim();

interface Expected {
  corrections: { id: string; entity: string; date: string; changes: { field: string; before: string | null; after: string | null }[];
    disputes: string[] }[];
  disputes: { id: string; open: boolean; status: string; label: string; resolved_on: string | null; position: string;
    claim_sources: string[]; evidence: string[]; org?: string; name?: string; role?: string; relationship: string;
    raw: string | null }[];
}
function expected(): Expected {
  return {
    corrections: CORRECTIONS.map((e) => ({ id: e.id, entity: e.entity, date: e.date, disputes: e.disputes ?? [],
      changes: (e.changes ?? []).map((c) => ({ field: c.field, before: shown(c.before), after: shown(c.after) })) })),
    disputes: DISPUTES.map((d) => {
      const r = raiser(d);
      return { id: d.id, open: d.status === 'open', status: d.status, label: d.status === 'open' ? 'Unresolved' : CLOSED[d.status],
        resolved_on: d.resolved_on ?? null, position: words(d.position), claim_sources: d.claim_sources, evidence: d.evidence, ...r,
        relationship: d.disputant_relationship, raw: r.org == null && d.raised_by !== 'redacted' ? d.raised_by : null };
    }),
  };
}

interface Audit { problems: string[]; corrections: string[]; disputes: string[] }

/** What is wrong with /corrections/ read against what it must hold, from its HTML in the browser (a DOMParser document,
 *  so a doctored copy is audited exactly as the page is). */
function audit({ html, want }: { html: string; want: Expected }): Audit {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const text = (n: Element | null | undefined) => (n?.textContent ?? '').replace(/\s+/g, ' ').trim();
  const problems: string[] = [];
  const list = doc.querySelector('article[data-corrections] [data-corrections-list]');
  const listed = [...(list?.querySelectorAll(':scope > li[data-correction]') ?? [])].map((li) => li.getAttribute('data-correction') ?? '');
  for (const c of want.corrections) {
    const li = list?.querySelector(`:scope > li[data-correction="${c.id}"]`);
    if (li == null) { problems.push(`correction ${c.id} (${c.entity}) is missing from the page`); continue; }
    if (li.id !== c.id) problems.push(`correction ${c.id} has no anchor of its own (#${c.id})`);
    if (li.querySelector(`time[datetime="${c.date}"]`) == null) problems.push(`correction ${c.id} does not give its date ${c.date}`);
    if (!text(li.querySelector('h3')).includes(c.entity)) problems.push(`correction ${c.id} does not name its entity ${c.entity}`);
    for (const ch of c.changes) {
      const row = li.querySelector(`tr[data-change-field="${ch.field}"]`);
      const cell = (k: string) => row?.querySelector(`td[data-${k}]`);
      if (row == null) { problems.push(`correction ${c.id} does not list its change to ${ch.field}`); continue; }
      if (row.querySelector('td[data-withheld]') != null) continue;
      const [b, a] = [cell('before'), cell('after')];
      if (ch.before == null ? b?.querySelector('[data-absent]') == null : text(b) !== ch.before) problems.push(`correction ${c.id}: ${ch.field} before is not ${ch.before}`);
      if (ch.after == null ? a?.querySelector('[data-absent]') == null : text(a) !== ch.after) problems.push(`correction ${c.id}: ${ch.field} now is not ${ch.after}`);
    }
    const rep = li.querySelector('[data-reporter]');
    if (rep == null) problems.push(`correction ${c.id} does not say who reported it`);
    else if (c.disputes.length === 0 && rep.querySelector('[data-absent="not-recorded"]') == null) problems.push(`correction ${c.id} names a reporter no record gives`);
    for (const d of c.disputes) {
      if (rep?.querySelector(`a[data-reported-in="${d}"][href="#${d}"]`) == null) problems.push(`correction ${c.id} does not credit dispute ${d}`);
    }
  }
  const order = want.corrections.map((c) => c.id);
  for (const id of listed) if (!order.includes(id)) problems.push(`the page lists ${id}, which is no published correction`);
  if (JSON.stringify(listed.filter((id) => order.includes(id))) !== JSON.stringify(order.filter((id) => listed.includes(id)))) {
    problems.push('the corrections are not newest first');
  }

  const html_ = html;
  for (const d of want.disputes) {
    const li = doc.querySelector(`li[data-dispute="${d.id}"]`);
    if (li == null) { problems.push(`dispute ${d.id} is dropped from the page`); continue; }
    if (li.id !== d.id) problems.push(`dispute ${d.id} has no anchor of its own (#${d.id})`);
    const section = li.closest('[data-disputes]')?.getAttribute('data-disputes');
    if (section !== (d.open ? 'open' : 'closed')) problems.push(`${d.open ? 'open' : 'closed'} dispute ${d.id} is listed with the ${section ?? 'no'} disputes`);
    const status = li.querySelector('[data-dispute-status]');
    const said = text(status);
    if (d.open) {
      if (li.getAttribute('data-status') !== 'open' || status?.getAttribute('data-dispute-status') !== 'open' || !said.startsWith('Unresolved')
        || /\b(resolved|withdrawn|closed)\b/i.test(said.replace(/^Unresolved/, '').replace(/has not resolved/, '')) || li.querySelector('[data-resolved-on]') != null) {
        problems.push(`open dispute ${d.id} looks resolved: "${said}"`);
      }
    } else if (!said.startsWith(d.label) || li.querySelector(`[data-resolved-on][datetime="${d.resolved_on}"]`) == null) {
      problems.push(`closed dispute ${d.id} does not say it is ${d.label} on ${d.resolved_on}: "${said}"`);
    }
    const pos = (k: string) => li.querySelector(`[data-position="${k}"]`);
    for (const [k, ids, what] of [['claim', d.claim_sources, "the claim's position"], ['dispute', d.evidence, "the dispute's position"]] as const) {
      const p = pos(k);
      if (p == null) { problems.push(`dispute ${d.id} is missing ${what}`); continue; }
      for (const sid of ids) {
        const item = p.querySelector(`[data-cited="${sid}"]`);
        if (item == null || (item.querySelector(`cite[data-source="${sid}"] a[href]`) == null && item.querySelector('[data-absent]') == null)) {
          problems.push(`dispute ${d.id}: ${what} is missing its source ${sid}`);
        }
      }
    }
    if (pos('dispute') != null && text(pos('dispute')).indexOf(d.position) < 0) problems.push(`dispute ${d.id}: the dispute's position is not its own words`);
    if (pos('claim') != null && pos('claim')!.querySelector('[data-figure]') == null) problems.push(`dispute ${d.id}: the claim's position does not state its figure`);
    const r = li.querySelector('[data-raised-by] [data-raiser]');
    if (r == null || r.getAttribute('data-relationship') !== d.relationship) problems.push(`dispute ${d.id} does not say who raised it and their relationship`);
    else if (d.org != null) {
      const a = r.querySelector(`a[data-raiser-org="${d.org}"][href="/orgs/${d.org}/"]`);
      if (a == null || text(a) !== d.name) problems.push(`dispute ${d.id} does not name its organisation ${d.org}`);
    } else if (text(r.querySelector('[data-raiser-role]')) !== d.role) problems.push(`dispute ${d.id} does not give its raiser's role, ${d.role}`);
    if (d.raw != null && html_.includes(d.raw)) problems.push(`dispute ${d.id}'s raw raised_by is printed`);
  }
  const count = (k: string) => text(doc.querySelector(`[data-corrections-summary] [data-count="${k}"]`));
  const open = want.disputes.filter((d) => d.open).length;
  if (count('corrections') !== String(want.corrections.length) || count('open') !== String(open)
    || count('closed') !== String(want.disputes.length - open)) problems.push('the summary miscounts');
  return { problems, corrections: listed, disputes: [...doc.querySelectorAll('li[data-dispute]')].map((li) => li.getAttribute('data-dispute') ?? '') };
}

type Doctor =
  | { op: 'remove'; selector: string }
  | { op: 'resolve'; id: string }
  | { op: 'close'; id: string }
  | { op: 'print'; id: string; raw: string };

/** The page's HTML again, as `how` leaves the document a browser built from it. */
function doctor({ html, how }: { html: string; how: Doctor }): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const li = 'id' in how ? doc.querySelector(`li[data-dispute="${how.id}"]`)! : null;
  if (how.op === 'remove') doc.querySelectorAll(how.selector).forEach((n) => n.remove());
  if (how.op === 'resolve') {
    li!.setAttribute('data-status', 'resolved-claim-retained');
    const s = li!.querySelector('[data-dispute-status]')!;
    s.setAttribute('data-dispute-status', 'resolved-claim-retained');
    s.innerHTML = '<strong>Resolved: the claim was retained</strong> on <time datetime="2026-11-21" data-resolved-on>2026-11-21</time>.';
  }
  if (how.op === 'close') doc.querySelector('[data-disputes="closed"]')!.append(li!);
  if (how.op === 'print') li!.querySelector('[data-raiser-role]')!.textContent = how.raw;
  return `<!doctype html>${doc.documentElement.outerHTML}`;
}

interface Rss { problems: string[]; items: { guid: string; link: string; categories: string[]; date: string }[] }

/** What is wrong with an RSS 2.0 document (www.rssboard.org/rss-specification), read by a real XML parser in the
 *  browser: well-formed; an <rss version="2.0"> holding one <channel> with its three required elements; only the
 *  specification's elements, or namespaced extensions, in channel and item; an atom:link to itself; every item with a
 *  title or a description, a unique guid, a link and an RFC 822 pubDate, newest first. */
function rssProblems(xml: string): Rss {
  const NS_ATOM = 'http://www.w3.org/2005/Atom';
  const CHANNEL = ['title', 'link', 'description', 'language', 'copyright', 'managingEditor', 'webMaster', 'pubDate', 'lastBuildDate',
    'category', 'generator', 'docs', 'cloud', 'ttl', 'image', 'rating', 'textInput', 'skipHours', 'skipDays', 'item'];
  const ITEM = ['title', 'link', 'description', 'author', 'category', 'comments', 'enclosure', 'guid', 'pubDate', 'source'];
  const RFC822 = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4} \d{2}:\d{2}:\d{2} (GMT|[+-]\d{4})$/;
  const problems: string[] = [];
  const doc = new DOMParser().parseFromString(xml, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length > 0) return { problems: ['not well-formed XML'], items: [] };
  const root = doc.documentElement;
  if (root.localName !== 'rss' || root.namespaceURI != null || root.getAttribute('version') !== '2.0') problems.push('the root is not <rss version="2.0">');
  const kids = (el: Element) => [...el.children];
  const own = (el: Element, name: string) => kids(el).filter((k) => k.namespaceURI == null && k.localName === name);
  const channels = own(root, 'channel');
  if (channels.length !== 1) return { problems: [...problems, `${channels.length} <channel> elements, not one`], items: [] };
  const ch = channels[0];
  const one = (el: Element, name: string, where: string) => {
    const found = own(el, name);
    if (found.length !== 1 || (found[0].textContent ?? '').trim() === '') problems.push(`${where} has no single, non-empty <${name}>`);
    return (found[0]?.textContent ?? '').trim();
  };
  const url = (s: string) => /^https?:\/\/[^/\s]+\/\S*$/.test(s) || /^\/\S*$/.test(s);
  const date = (s: string, where: string) => {
    if (!RFC822.test(s) || Number.isNaN(Date.parse(s)) || (s.endsWith('GMT') && new Date(s).toUTCString() !== s)) problems.push(`${where}: ${JSON.stringify(s)} is not an RFC 822 date`);
    return Number.isNaN(Date.parse(s)) ? '' : new Date(s).toISOString();
  };
  for (const name of ['title', 'link', 'description']) one(ch, name, 'the channel');
  if (!url(own(ch, 'link')[0]?.textContent?.trim() ?? '')) problems.push('the channel link is not a URL');
  for (const k of kids(ch)) if (k.namespaceURI == null && !CHANNEL.includes(k.localName)) problems.push(`<${k.localName}> is not an RSS 2.0 channel element`);
  const self = kids(ch).filter((k) => k.namespaceURI === NS_ATOM && k.localName === 'link' && k.getAttribute('rel') === 'self');
  if (self.length !== 1 || !(self[0].getAttribute('href') ?? '').endsWith('/feed/corrections.xml') || self[0].getAttribute('type') !== 'application/rss+xml') {
    problems.push('the channel has no atom:link rel="self" to /feed/corrections.xml');
  }
  for (const b of own(ch, 'lastBuildDate')) date((b.textContent ?? '').trim(), 'lastBuildDate');
  const items: Rss['items'] = [];
  const guids = new Set<string>();
  own(ch, 'item').forEach((it, i) => {
    const where = `item ${i + 1}`;
    for (const k of kids(it)) if (k.namespaceURI == null && !ITEM.includes(k.localName)) problems.push(`${where}: <${k.localName}> is not an RSS 2.0 item element`);
    if (own(it, 'title').concat(own(it, 'description')).every((e) => (e.textContent ?? '').trim() === '')) problems.push(`${where} has neither a title nor a description`);
    const guid = one(it, 'guid', where);
    if (guids.has(guid)) problems.push(`${where}: guid ${guid} is not unique`);
    guids.add(guid);
    const link = one(it, 'link', where);
    if (!url(link)) problems.push(`${where}: its link is not a URL`);
    const when = date(one(it, 'pubDate', where), where);
    if (items.length > 0 && when > items[items.length - 1].date) problems.push(`${where} is newer than the item before it`);
    items.push({ guid, link, categories: own(it, 'category').map((c) => (c.textContent ?? '').trim()), date: when });
  });
  return { problems, items };
}

async function get(page: Page, path: string): Promise<string> {
  const res = await page.request.get(path);
  expect(res.status(), path).toBe(200);
  return res.text();
}
const audited = (page: Page, html: string) => page.evaluate(audit, { html, want: expected() });

test.beforeAll(async ({ request }) => {
  // a server built without the fixtures would make every assertion below vacuous
  expect(CORRECTIONS.length, 'the feed fixture carries corrections').toBeGreaterThanOrEqual(2);
  expect(CORRECTIONS.some((e) => (e.disputes ?? []).length > 0), 'one names the dispute that reported it').toBe(true);
  expect(OPEN.length, 'the dispute fixture carries open disputes').toBeGreaterThanOrEqual(2);
  expect(DISPUTES.length - OPEN.length, 'and closed ones').toBeGreaterThan(0);
  expect(DISPUTES.some((d) => raiser(d).org != null) && DISPUTES.some((d) => raiser(d).role != null), 'raisers named and not').toBe(true);
  const html = await (await request.get(PAGE)).text();
  expect(html, 'the server on the baseURL was built with UAIBI_DISPUTES (playwright.config.ts)').toContain(`data-dispute="${OPEN[0].id}"`);
});

test('every correction and every dispute is on the page, as 05 S8 lists them, and no individual is named', async ({ page }) => {
  const html = await get(page, PAGE);
  await page.goto('about:blank');
  const a = await audited(page, html);
  expect(a.problems).toEqual([]);
  expect(a.corrections).toEqual(CORRECTIONS.map((e) => e.id));
  expect(a.disputes, 'open disputes first').toEqual([...a.disputes].sort((x, y) =>
    Number(DISPUTES.find((d) => d.id === y)!.status === 'open') - Number(DISPUTES.find((d) => d.id === x)!.status === 'open')));
  expect(new Set(a.disputes)).toEqual(new Set(DISPUTES.map((d) => d.id)));
  // 05 S8.1's redaction: the identity withheld, and said to be
  const redacted = DISPUTES.find((d) => d.raised_by === 'redacted')!;
  expect(html).toMatch(new RegExp(`data-dispute="${redacted.id}"[\\s\\S]*?data-raiser-withheld`));
});

test('the page is a citable record: it ships no JavaScript and reads with it off, and it announces its feed', async ({ page }) => {
  const res = await page.goto(PAGE);
  expect(res?.status()).toBe(200);
  const html = await res!.text();
  expect([...html.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), 'no JavaScript but the pre-paint line').toEqual([PREPAINT]);
  await expect(page.locator('article[data-corrections] dl[data-corrections-summary]')).toBeVisible();
  for (const d of OPEN) await expect(page.locator(`li[data-dispute="${d.id}"] [data-dispute-status]`)).toContainText('Unresolved');
  await expect(page.locator(`head link[rel="alternate"][type="application/rss+xml"][href="${FEED}"]`)).toHaveCount(1);
  await expect(page.locator(`a[data-feed][href="${FEED}"]`)).toBeVisible();
  // each anchor the feed links is the item it names
  for (const id of [...CORRECTIONS.map((e) => e.id), ...DISPUTES.map((d) => d.id)]) await expect(page.locator(`[id="${id}"]`)).toHaveCount(1);
});

test('the failure cases: a dropped or resolved-looking open dispute, and a correction missing from the page, are reported', async ({ page }) => {
  const html = await get(page, PAGE);
  await page.goto('about:blank');
  const c = CORRECTIONS[0];
  const d = OPEN.find((x) => raiser(x).role != null && x.raised_by !== 'redacted')!;
  const ev = (how: Doctor) => page.evaluate(doctor, { html, how }).then((h) => audited(page, h));
  const cases: [Doctor, string][] = [
    [{ op: 'remove', selector: `li[data-correction="${c.id}"]` }, `correction ${c.id} (${c.entity}) is missing from the page`],
    [{ op: 'remove', selector: `li[data-dispute="${d.id}"]` }, `dispute ${d.id} is dropped from the page`],
    [{ op: 'resolve', id: d.id }, `open dispute ${d.id} looks resolved: "Resolved: the claim was retained on 2026-11-21."`],
    [{ op: 'close', id: d.id }, `open dispute ${d.id} is listed with the closed disputes`],
    [{ op: 'remove', selector: `li[data-dispute="${d.id}"] [data-position="dispute"] ul.cited` }, `dispute ${d.id}: the dispute's position is missing its source ${d.evidence[0]}`],
    [{ op: 'remove', selector: `li[data-dispute="${d.id}"] [data-position="claim"]` }, `dispute ${d.id} is missing the claim's position`],
    [{ op: 'print', id: d.id, raw: d.raised_by }, `dispute ${d.id}'s raw raised_by is printed`],
    [{ op: 'remove', selector: `li[data-correction="${c.id}"] tr[data-change-field="${c.changes![0].field}"] td[data-after]` },
      `correction ${c.id}: ${c.changes![0].field} now is not ${shown(c.changes![0].after)}`],
  ];
  for (const [how, problem] of cases) expect((await ev(how)).problems, JSON.stringify(how)).toContain(problem);
});

test('/feed/corrections.xml is valid RSS 2.0 and carries every correction and every dispute, each linking its anchor', async ({ page }) => {
  const xml = await get(page, FEED);
  await page.goto('about:blank');
  const r = await page.evaluate(rssProblems, xml);
  expect(r.problems).toEqual([]);
  const want = new Map([
    ...CORRECTIONS.map((e) => [`urn:uaibi:event:${e.id}`, { anchor: e.id, kind: 'correction' }] as const),
    // a dispute's guid carries its status: its resolution is a new item, not an edit of the old one
    ...DISPUTES.map((d) => [`urn:uaibi:dispute:${d.id}:${d.status}`, { anchor: d.id, kind: 'dispute' }] as const),
  ]);
  expect(new Set(r.items.map((i) => i.guid))).toEqual(new Set(want.keys()));
  for (const i of r.items) {
    const w = want.get(i.guid)!;
    expect(i.categories, i.guid).toContain(w.kind);
    expect(new URL(i.link, 'http://origin.invalid').pathname + new URL(i.link, 'http://origin.invalid').hash, i.guid).toBe(`${PAGE}#${w.anchor}`);
  }
  // the feed names no one the page may not: a raiser that is no published organisation is its role there too
  for (const d of expected().disputes) if (d.raw != null) expect(xml, `${d.id}'s raw raised_by`).not.toContain(d.raw);
  for (const d of expected().disputes) if (d.name != null) expect(xml, `${d.id} names ${d.org}`).toContain(d.name);
  // and the parser and the structural checks fail when they should
  const broken = [
    [xml.replace(/<link>[^<]*<\/link>/, ''), 'the channel has no single, non-empty <link>'],
    [xml.replace(/<pubDate>[^<]*<\/pubDate>/, '<pubDate>2026-03-11</pubDate>'), 'item 1: "2026-03-11" is not an RFC 822 date'],
    [xml.replace('<rss version="2.0"', '<rss version="0.91"'), 'the root is not <rss version="2.0">'],
    [xml.replace('</channel>', '<entry/></channel>'), '<entry> is not an RSS 2.0 channel element'],
    [xml.replace('</channel>', '</channel'), 'not well-formed XML'],
  ];
  for (const [doc, problem] of broken) expect((await page.evaluate(rssProblems, doc)).problems, problem).toContain(problem);
});

test('every claim page links the corrections page from its footer', async ({ page }) => {
  test.setTimeout(300_000);
  const rows = (JSON.parse(readFileSync(join(ROOT, 'build', 'e2e-claims', 'claims.json'), 'utf8')) as { claims: { claim: { id: string } }[] }).claims;
  expect(rows.length).toBeGreaterThanOrEqual(90);
  await page.goto('about:blank');
  const footerless = (html: string) => page.evaluate((h) => {
    const doc = new DOMParser().parseFromString(h, 'text/html');
    return doc.querySelector('article[data-claim-page] > footer[data-corrections-link] a[href="/corrections/"]') == null;
  }, html);
  for (const { claim } of rows) {
    const html = await get(page, `/claims/${claim.id}/`);
    expect(await footerless(html), `/claims/${claim.id}/ links /corrections/ from its footer`).toBe(false);
  }
  const last = await get(page, `/claims/${rows[0].claim.id}/`);
  expect(await footerless(last.replace(/<footer class="corrections-link[^]*?<\/footer>/, '')), 'a claim page without it is reported').toBe(true);
  expect((await page.request.get(PAGE)).status()).toBe(200);
});
