// site/src/lib/corrections.ts -- P3-S10-T09 (05 S8 "Corrections and disputes"; 10 V8, "a separate corrections feed at
// /feed/corrections.xml", and "Information architecture"). The record /corrections/ and /feed/corrections.xml publish,
// so that a correction is a published, linkable record rather than a quiet edit.
//
// What counts as a correction, and how it is computed. A correction is a `correction` event of tools/build/feed.py, the
// release feed's own derivation from git history over data/ at build time (lib/feed.ts reads it: FEED_EVENTS, else
// build/feed-events.json from `bench build`, else feed.py run by the site build). That is: a commit on main's
// first-parent line that is tagged `fix:` or carries a `Correction:` trailer (05 S8's trailer; 10 V8's tag), and that
// changes a value the index had already published -- filling in a blank is not a correction -- on an entity the site
// publishes at HEAD. Only the substantive changes are listed (05 S8: "every substantive correction"): a change to
// bookkeeping -- when a record was checked, fetched, archived, reviewed or ingested, and the dispute links a claim carries
// -- is routine curation (feed.py ROUTINE), and a commit that changes nothing else is not a correction at all. Each one
// is listed with 05 S8's five things: the date, the entity, what it said before, what it says now, and who reported it.
//
// Who reported it -- the rule that overrides the ledger's "Name who reported each fix". The repository never writes an
// individual's name, personal handle or e-mail address into a file or a published page. So:
//   - nothing here reads a commit's author, committer or trailers for a person, nor a pull request (the repository's
//     commits are made by three organisation accounts, so authorship says nothing about who found an error anyway);
//   - a reporter is rendered only from an explicit record field: a dispute record's `raised_by` (05 S8), reached either
//     as the dispute itself or through a correction whose `Correction:` trailer names the dispute id (feed.py `disputes`);
//   - it is rendered as an organisation only when `raised_by` is an `org-*` id the corpus publishes as an organisation
//     that is not of kind `individual`; anything else -- a handle, `redacted` (05 S8.1), an unpublished id -- renders
//     as the neutral role its `disputant_relationship` gives ("a third party", "a reader"), and the raw value is never
//     printed;
//   - a correction no record speaks for says that no reporter is recorded, in the absence token, rather than guessing.
//   - a correction of a Source's `authors` is listed with its values withheld: the page prints no person's name.
//
// Disputes. Every record under data/disputes/ (UAIBI_DISPUTES names another directory: the e2e fixture build) is read
// and rendered, open ones first. "Disputes are never resolved by deletion": a record this module cannot read throws
// and fails the build, so an unreadable dispute is never silently left off the page. Each renders both positions with
// both sources: the claim's figure with `claim_sources`, the dispute's position with `evidence`. An open dispute is
// shown as unresolved. bench validate holds the files to schema/dispute.py; the checks here are the ones the page
// itself depends on.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { isAbsolute, join, relative, sep } from 'node:path';
import { load } from 'js-yaml';
import { REPO_ROOT, correctionEvents, type FeedEvent } from './feed';
import type { Dispute } from '../types/dispute';
import type { Organization } from '../types/organization';

export type DisputeStatus = NonNullable<Dispute['status']>;
export type Relationship = Dispute['disputant_relationship'];

/** A dispute as read, its status defaulted as schema/dispute.py defaults it and its dates as YYYY-MM-DD. */
export interface DisputeRecord extends Dispute {
  status: DisputeStatus;
  file: string;                       // the file it was read from, from the repository root
}

export const STATUS_LABEL: Record<DisputeStatus, string> = {
  open: 'Unresolved',
  'resolved-claim-corrected': 'Resolved: the claim was corrected',
  'resolved-claim-retained': 'Resolved: the claim was retained',
  withdrawn: 'Withdrawn by the disputant',
};
/** The relationship as the page states it (05 S8: "the site shows it"). */
export const RELATIONSHIP_LABEL: Record<Relationship, string> = {
  'evaluated-party': 'the evaluated party',
  'benchmark-maintainer': "the benchmark's maintainer",
  'third-party': 'a third party',
  unknown: 'relationship not stated',
};
/** The neutral role a reporter renders as when the record names no published organisation. */
export const ROLE: Record<Relationship, string> = {
  'evaluated-party': 'the evaluated party',
  'benchmark-maintainer': "the benchmark's maintainers",
  'third-party': 'a third party',
  unknown: 'a reader',
};
const STATUSES = Object.keys(STATUS_LABEL) as DisputeStatus[];
const RELATIONSHIPS = Object.keys(ROLE) as Relationship[];
const DISPUTE_ID = /^dispute-[a-z0-9]+(-[a-z0-9]+)*$/;          // schema/dispute.py DisputeId
const CLAIM_ID = /^claim-[0-9a-f]{12}$/;                         // schema/claim.py ClaimId
const ORG_ID = /^org-[a-z0-9]+(-[a-z0-9]+)*$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

// ---- the dispute records -------------------------------------------------------------------------------------------

export const DISPUTES_DIR = process.env.UAIBI_DISPUTES
  ? (isAbsolute(process.env.UAIBI_DISPUTES) ? process.env.UAIBI_DISPUTES : join(REPO_ROOT, process.env.UAIBI_DISPUTES))
  : join(REPO_ROOT, 'data', 'disputes');

/** A YAML date as YYYY-MM-DD: js-yaml reads an unquoted date as a Date. */
function day(v: unknown): string | null {
  if (v == null) return null;
  const s = v instanceof Date ? v.toISOString().slice(0, 10) : String(v);
  return DAY.test(s) ? s : `invalid:${s}`;
}

/** Every dispute record in `dir`: open ones first, newest raised first, then the closed ones, newest resolved first.
 *  A directory that does not exist holds none; a record the page could not render faithfully throws. */
export function disputes(dir: string = DISPUTES_DIR): DisputeRecord[] {
  if (!existsSync(dir)) return [];
  const out: DisputeRecord[] = [];
  for (const name of readdirSync(dir).filter((n) => n.endsWith('.yaml')).sort()) {
    const file = join(dir, name);
    const where = relative(REPO_ROOT, file).split(sep).join('/');
    const raw = load(readFileSync(file, 'utf8'), { filename: name }) as Record<string, unknown> | null;
    const fail = (why: string): never => {
      throw new Error(`${where}: ${why}. A dispute is never left off /corrections/ (05 S8), so the build stops; `
        + 'schema/dispute.py is the shape (bench validate)');
    };
    if (raw == null || typeof raw !== 'object' || Array.isArray(raw)) fail('not a mapping');
    const r = raw as Record<string, unknown>;
    const text = (k: string) => (typeof r[k] === 'string' && (r[k] as string).trim() !== '' ? (r[k] as string) : fail(`${k} is not text`));
    const ids = (k: string) => {
      const v = r[k];
      if (!Array.isArray(v) || v.length === 0 || v.some((x) => typeof x !== 'string' || x === '')) fail(`${k} is not a list of source ids`);
      return v as [string, ...string[]];
    };
    const id = text('id');
    if (!DISPUTE_ID.test(id)) fail(`id ${id} is not a dispute id`);
    if (name !== `${id}.yaml`) fail(`holds ${id}, so it is named ${id}.yaml`);
    const concerns = text('concerns');
    if (!CLAIM_ID.test(concerns)) fail(`concerns ${concerns} is not a claim id`);
    const relationship = text('disputant_relationship') as Relationship;
    if (!RELATIONSHIPS.includes(relationship)) fail(`disputant_relationship ${relationship} is not one of ${RELATIONSHIPS.join(', ')}`);
    const status = (r.status ?? 'open') as DisputeStatus;
    if (!STATUSES.includes(status)) fail(`status ${String(status)} is not one of ${STATUSES.join(', ')}`);
    const raised_on = day(r.raised_on);
    const resolved_on = day(r.resolved_on);
    if (raised_on == null || !DAY.test(raised_on)) fail('raised_on is not a date');
    if ((status === 'open') !== (resolved_on == null)) fail(`status ${status} ${status === 'open' ? 'has' : 'needs'} resolved_on`);
    if (resolved_on != null && (!DAY.test(resolved_on) || resolved_on < raised_on!)) fail('resolved_on is not a date on or after raised_on');
    const corrected_by = r.corrected_by == null ? null : text('corrected_by');
    if ((status === 'resolved-claim-corrected') !== (corrected_by != null)) fail('corrected_by is given exactly when the claim was corrected');
    out.push({
      id, concerns, raised_by: text('raised_by'), disputant_relationship: relationship, raised_on: raised_on!,
      position: text('position').trim(), evidence: ids('evidence'), claim_sources: ids('claim_sources'),
      our_response: typeof r.our_response === 'string' && r.our_response.trim() !== '' ? r.our_response.trim() : null,
      status, resolved_on, corrected_by, file: where,
    });
  }
  const open = out.filter((d) => d.status === 'open');
  const closed = out.filter((d) => d.status !== 'open');
  const newest = (k: 'raised_on' | 'resolved_on') => (a: DisputeRecord, b: DisputeRecord) =>
    cmp(b[k] ?? '', a[k] ?? '') || cmp(a.id, b.id);
  return [...open.sort(newest('raised_on')), ...closed.sort(newest('resolved_on'))];
}

// ---- who reported it -----------------------------------------------------------------------------------------------

export type Reporter =
  | { kind: 'organisation'; id: string; name: string; relationship: Relationship }
  | { kind: 'role'; role: string; relationship: Relationship; withheld: boolean };

/** The published organisations by id, those of kind `individual` left out: a person is never named. */
export function organisationNames(orgs: Organization[]): Map<string, string> {
  return new Map(orgs.filter((o) => o.kind !== 'individual').map((o) => [o.id, o.name]));
}

/** Who raised a dispute, as the page may say it: a published organisation, or a neutral role (see the header). */
export function reporterOf(d: Pick<Dispute, 'raised_by' | 'disputant_relationship'>, orgs: Map<string, string>): Reporter {
  const id = d.raised_by.trim();
  const name = ORG_ID.test(id) ? orgs.get(id) : undefined;
  if (name != null) return { kind: 'organisation', id, name, relationship: d.disputant_relationship };
  return { kind: 'role', role: ROLE[d.disputant_relationship], relationship: d.disputant_relationship, withheld: id === 'redacted' };
}

/** A reporter in plain text, for the feed. */
export function reporterText(r: Reporter): string {
  if (r.kind === 'organisation') return `${r.name} (${RELATIONSHIP_LABEL[r.relationship]})`;
  return r.role + (r.withheld ? ', identity withheld at their request' : '');
}

// ---- the corrections -----------------------------------------------------------------------------------------------

/** feed.py's correction event: `disputes` is what its commit's Correction: trailer names (absent before P3-S10-T09). */
export type CorrectionEvent = FeedEvent & { disputes?: string[] };

export interface Correction {
  event: CorrectionEvent;
  reported: DisputeRecord[];          // the dispute records its Correction: trailer names, in the order named
  unmatched: string[];                // dispute ids it names that data/disputes/ does not hold
}

/** Every published correction, newest first (feed.py's order), with the dispute records that say who reported it. */
export function corrections(events: CorrectionEvent[] = correctionEvents(), records: DisputeRecord[] = disputes()): Correction[] {
  const byId = new Map(records.map((d) => [d.id, d]));
  return events.map((event) => {
    const named = event.disputes ?? [];
    return { event, reported: named.flatMap((id) => byId.get(id) ?? []), unmatched: named.filter((id) => !byId.has(id)) };
  });
}

/** A field whose values name people: listed, its values never printed (05 S8.1 makes Source authors bibliographic
 *  metadata; this page still prints no person's name). */
export const withheld = (field: string) => field.split(/[.[\]]/).includes('authors');

/** A changed value as text; null for a value the correction removed. */
export function shown(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ');
  return typeof v === 'string' ? v : JSON.stringify(v);
}

/** One change as a line of text: "field: before → after". */
export function changeText(c: { field: string; before: unknown; after: unknown }): string {
  if (withheld(c.field)) return `${c.field}: corrected (values not shown: they name people)`;
  return `${c.field}: ${shown(c.before) ?? 'not recorded'} → ${shown(c.after) ?? 'removed'}`;
}

// ---- the feed: RSS 2.0 (www.rssboard.org/rss-specification) ----------------------------------------------------------

export interface FeedItem {
  guid: string;
  title: string;
  anchor: string;                     // the item's fragment on /corrections/
  date: string;                       // ISO 8601, the item's own date
  categories: string[];
  description: string;
}

/** The corrections and the disputes as feed items, newest first. A dispute's guid carries its status, so a
 *  resolution is a new item rather than a silent edit of the old one. */
export function feedItems(list: Correction[], records: DisputeRecord[], orgs: Map<string, string>): FeedItem[] {
  const items: FeedItem[] = list.map(({ event: e, reported }) => ({
    guid: `urn:uaibi:event:${e.id}`,
    title: `Correction: ${e.entity}`,
    anchor: e.id,
    date: e.date,
    categories: ['correction', ...e.families],
    description: [(e.changes ?? []).map(changeText).join('; '),
      `Reported by: ${reported.length > 0 ? reported.map((d) => reporterText(reporterOf(d, orgs))).join('; ') : 'not recorded'}.`,
    ].filter((s) => s !== '').join(' '),
  }));
  for (const d of records) {
    const r = reporterText(reporterOf(d, orgs));
    items.push({
      guid: `urn:uaibi:dispute:${d.id}:${d.status}`,
      title: `${d.status === 'open' ? 'Open dispute' : `Dispute closed (${STATUS_LABEL[d.status].toLowerCase()})`}: ${d.concerns}`,
      anchor: d.id,
      date: `${d.resolved_on ?? d.raised_on}T00:00:00Z`,
      categories: ['dispute', d.status],
      description: `${STATUS_LABEL[d.status]}. Raised by ${r} on ${d.raised_on}: ${d.position.replace(/\s+/g, ' ')}`
        + (d.our_response != null ? ` Our response: ${d.our_response.replace(/\s+/g, ' ')}` : ''),
    });
  }
  // stable: on one date, the corrections keep feed.py's order, then the disputes keep theirs
  return items.sort((a, b) => cmp(b.date, a.date));
}

const site = () => (import.meta.env.SITE ? String(import.meta.env.SITE).replace(/\/$/, '') : '');
const xml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
/** RFC 822 (RSS 2.0's date format), in GMT. */
export const rfc822 = (iso: string) => new Date(iso).toUTCString();

export const PAGE = '/corrections/';
export const FEED = '/feed/corrections.xml';

/** The RSS 2.0 document. Links are absolute when the site's origin is configured (astro.config.mjs `site`) and
 *  root-relative until it is; lastBuildDate is the newest item's date, so a rebuild of the same data is the same file. */
export function rss(items: FeedItem[]): string {
  const abs = (p: string) => site() + p;
  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '  <channel>',
    '    <title>Benchmark index: corrections and disputes</title>',
    `    <link>${xml(abs(PAGE))}</link>`,
    '    <description>Every substantive correction to the index, with what it said before and what it says now, and every '
      + 'dispute, open or closed, with both positions.</description>',
    '    <language>en</language>',
    '    <docs>https://www.rssboard.org/rss-specification</docs>',
    ...(items.length > 0 ? [`    <lastBuildDate>${rfc822(items[0].date)}</lastBuildDate>`] : []),
    `    <atom:link href="${xml(abs(FEED))}" rel="self" type="application/rss+xml"/>`,
    ...items.map((i) => [
      '    <item>',
      `      <title>${xml(i.title)}</title>`,
      `      <link>${xml(abs(`${PAGE}#${i.anchor}`))}</link>`,
      `      <guid isPermaLink="false">${xml(i.guid)}</guid>`,
      `      <pubDate>${rfc822(i.date)}</pubDate>`,
      ...i.categories.map((c) => `      <category>${xml(c)}</category>`),
      `      <description>${xml(i.description)}</description>`,
      '    </item>',
    ].join('\n')),
    '  </channel>',
    '</rss>',
    '',
  ].join('\n');
}
