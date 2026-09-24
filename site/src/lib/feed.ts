// site/src/lib/feed.ts -- P4-S4-T06. The release feed's data and its two serialisations.
//
// Events come from tools/build/feed.py, which derives them from git history over data/ (V8: never
// a hand-maintained changelog). In order of preference the build reads:
//   1. FEED_EVENTS, a path to an events JSON file (the e2e fixture build sets it);
//   2. build/feed-events.json, which `bench build` writes before the site build (08 S3);
//   3. otherwise it runs feed.py itself (BENCH_PYTHON, default `python`), so a bare `astro build`
//      on a clean checkout still has a feed.
// Machine-ingested events never reach the default feeds (V8 "Failure mode to avoid"); they are
// /feed/ingest.xml's alone.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

export interface FeedEvent {
  id: string;
  type: string;
  entity: string;
  path: string;
  date: string;
  date_basis: string;
  published_on: string;
  commit: string;
  subject: string;
  families: string[];
  organisations: string[];
  machine_ingested?: boolean;
  publishable?: boolean;
  fields?: string[];
  before?: unknown;
  after?: unknown;
  benchmark?: string;
  changes?: { field: string; before: unknown; after: unknown }[];
}

export const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');

export const EVENT_LABELS: Record<string, string> = {
  'benchmark-added': 'Benchmark added',
  'benchmark-updated-material': 'Benchmark updated',
  'claim-added': 'Claim added',
  correction: 'Correction',
  'lifecycle-change': 'Lifecycle change',
  'deprecation-detected': 'Deprecation detected',
  'source-rot-detected': 'Source rot detected',
};

let cache: FeedEvent[] | undefined;

export function allEvents(): FeedEvent[] {
  if (cache) return cache;
  const fromEnv = process.env.FEED_EVENTS;
  const built = join(REPO_ROOT, 'build', 'feed-events.json');
  let text: string;
  if (fromEnv) {
    text = readFileSync(isAbsolute(fromEnv) ? fromEnv : join(REPO_ROOT, fromEnv), 'utf8');
  } else if (existsSync(built)) {
    text = readFileSync(built, 'utf8');
  } else {
    text = execFileSync(process.env.BENCH_PYTHON ?? 'python',
      [join(REPO_ROOT, 'tools', 'build', 'feed.py'), '--repo', REPO_ROOT], { encoding: 'utf8' });
  }
  cache = JSON.parse(text) as FeedEvent[];
  return cache;
}

/** Events the site may announce: feed.py marks an event unpublishable when its entity is still
 * ai-drafted-unverified at HEAD, or gone -- the build refuses to publish those (14-roadmap). */
export const publishedEvents = () => allEvents().filter((e) => e.publishable !== false);
/** The default feed: every published event except the machine-ingested ones. Newest first. */
export const defaultEvents = () => publishedEvents().filter((e) => !e.machine_ingested);
export const ingestEvents = () => publishedEvents().filter((e) => e.machine_ingested);
export const correctionEvents = () => defaultEvents().filter((e) => e.type === 'correction');
export const familyEvents = (family: string) => defaultEvents().filter((e) => e.families.includes(family));

/** The 19 domain families, read from taxonomy/domains.yaml: every `- id:` without a slash. */
export function domainFamilies(): string[] {
  const text = readFileSync(join(REPO_ROOT, 'taxonomy', 'domains.yaml'), 'utf8');
  return [...text.matchAll(/^\s*-\s*id:\s*([a-z0-9-]+)\s*$/gm)].map((m) => m[1]).sort();
}

const fmt = (v: unknown) => (v === null || v === undefined ? 'null' : typeof v === 'string' ? v : JSON.stringify(v));

export function summary(e: FeedEvent): string {
  switch (e.type) {
    case 'benchmark-updated-material':
      return `Changed: ${(e.fields ?? []).join(', ')}`;
    case 'correction':
      return (e.changes ?? []).map((c) => `${c.field}: ${fmt(c.before)} → ${fmt(c.after)}`).join('; ');
    case 'lifecycle-change':
    case 'deprecation-detected':
    case 'source-rot-detected':
      return `${fmt(e.before)} → ${fmt(e.after)}`;
    case 'claim-added':
      return e.benchmark ? `On ${e.benchmark}` : '';
    default:
      return e.subject;
  }
}

export function entityPath(e: FeedEvent): string {
  if (e.path.startsWith('data/benchmarks/')) return `/benchmarks/${e.entity}/`;
  if (e.path.startsWith('data/claims/')) return `/claims/${e.entity}/`;
  if (e.path.startsWith('data/sources/')) return `/sources/${e.entity}/`;
  return '/feed/';
}

const site = () => (import.meta.env.SITE ? String(import.meta.env.SITE).replace(/\/$/, '') : '');
const abs = (p: string) => site() + p;
const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** An Atom 1.0 document (RFC 4287). `updated` is the newest event's date, so a rebuild is stable. */
export function atom(name: string, title: string, selfPath: string, events: FeedEvent[]): string {
  const updated = events[0]?.date ?? '1970-01-01T00:00:00Z';
  const entries = events.map((e) => [
    '  <entry>',
    `    <id>urn:uaibi:event:${esc(e.id)}</id>`,
    `    <title>${esc(`${EVENT_LABELS[e.type] ?? e.type}: ${e.entity}`)}</title>`,
    `    <updated>${esc(e.date)}</updated>`,
    `    <published>${esc(e.published_on)}</published>`,
    `    <link rel="alternate" href="${esc(abs(entityPath(e)))}"/>`,
    `    <category term="${esc(e.type)}"/>`,
    ...e.families.map((f) => `    <category term="${esc(f)}" scheme="urn:uaibi:domain-family"/>`),
    `    <summary>${esc(summary(e) || e.subject || e.type)}</summary>`,
    '  </entry>',
  ].join('\n'));
  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom">',
    `  <id>urn:uaibi:feed:${esc(name)}</id>`,
    `  <title>${esc(title)}</title>`,
    `  <updated>${esc(updated)}</updated>`,
    '  <author><name>Benchmark index</name></author>',
    `  <link rel="self" href="${esc(abs(selfPath))}"/>`,
    ...entries,
    '</feed>',
    '',
  ].join('\n');
}

/** A JSON Feed 1.1 document (jsonfeed.org/version/1.1). The event itself rides in `_uaibi`. */
export function jsonFeed(title: string, events: FeedEvent[]): string {
  return JSON.stringify({
    version: 'https://jsonfeed.org/version/1.1',
    title,
    ...(site() ? { home_page_url: abs('/feed/'), feed_url: abs('/feed.json') } : {}),
    items: events.map((e) => ({
      id: `urn:uaibi:event:${e.id}`,
      url: abs(entityPath(e)),
      title: `${EVENT_LABELS[e.type] ?? e.type}: ${e.entity}`,
      content_text: summary(e) || e.subject || e.type,
      date_published: e.date,
      tags: [e.type, ...e.families],
      _uaibi: e,
    })),
  }, null, 2) + '\n';
}

export const atomResponse = (body: string) =>
  new Response(body, { headers: { 'Content-Type': 'application/atom+xml; charset=utf-8' } });
