// site/src/lib/freshness.ts -- P5-S7-T04. Every entry's freshness, as the build derived it (05 S7, 06 S3.0).
//
// The data is tools/build/freshness.py's artifact; the thresholds (180/365/730 days on last_verified, 90 on a live
// source) are applied there and carried in it, so no threshold literal lives in the site. In order of preference
// the site reads:
//   1. FRESHNESS, a path to a freshness JSON file (a fixture build sets it);
//   2. build/derived/freshness.json, which `bench build --derived` writes before the site build;
//   3. otherwise it runs freshness.py itself (BENCH_PYTHON, default `python`), so a bare `astro build` on a clean
//      checkout still badges every entry -- never a page without it.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';
import { REPO_ROOT } from './ingestHealth';

export type FreshnessState = 'neutral' | 'amber' | 'red';

export interface LiveSource {
  source: string;
  adapter: string;
  last_successful_fetch: string | null;
  fetch_basis: string | null;
  days_since_refresh: number | null;
  adapter_status: string;
  slo_badge: 'stale' | 'source-retired' | null;
}

export interface SourceFreshness {
  sources: LiveSource[];
  badged: boolean;
  slo_badges: ('stale' | 'source-retired')[];
}

export interface EntryFreshness {
  id: string;
  kind: string;
  name: string;
  path: string;
  lifecycle: string | null;
  last_verified: string | null;
  days_since_verified: number | null;
  state: FreshnessState;
  demoted: boolean;
  critical: boolean;
  verification_status: string | null;
  source_freshness: SourceFreshness | null;
}

export interface Thresholds {
  amber_from_days: number;
  red_after_days: number;
  critical_after_days: number;
  source_refresh_days: number;
}

export interface Freshness {
  artifact: 'freshness';
  format: number;
  as_of: string;
  thresholds: Thresholds;
  states: FreshnessState[];
  order: string[];
  entries: EntryFreshness[];
}

let cache: Freshness | undefined;

export function freshness(): Freshness {
  if (cache) return cache;
  const fromEnv = process.env.FRESHNESS;
  const built = join(REPO_ROOT, 'build', 'derived', 'freshness.json');
  let text: string;
  if (fromEnv) {
    text = readFileSync(isAbsolute(fromEnv) ? fromEnv : join(REPO_ROOT, fromEnv), 'utf8');
  } else if (existsSync(built)) {
    text = readFileSync(built, 'utf8');
  } else {
    text = execFileSync(process.env.BENCH_PYTHON ?? 'python',
      [join(REPO_ROOT, 'tools', 'build', 'freshness.py'), '--root', REPO_ROOT], { encoding: 'utf8' });
  }
  const doc = JSON.parse(text) as Freshness;
  if (doc.artifact !== 'freshness' || doc.thresholds == null || !Array.isArray(doc.entries) || !Array.isArray(doc.order)) {
    throw new Error('freshness: not the artifact tools/build/freshness.py writes');
  }
  const ids = new Set(doc.entries.map((e) => e.id));
  if (doc.order.length !== ids.size || !doc.order.every((id) => ids.has(id))) {
    throw new Error('freshness: its default order does not list every entry exactly once');
  }
  cache = doc;
  return cache;
}

/** One entry's freshness, or a thrown error: an entry the build did not badge is a build failure (05 S7: "the
 *  site displays it on every entry"), never an entry shown without one. */
export function entryFreshness(id: string, doc: Freshness = freshness()): EntryFreshness {
  const e = doc.entries.find((x) => x.id === id);
  if (e == null) throw new Error(`freshness: no entry ${id} in the artifact; every entry carries its badge (05 S7)`);
  return e;
}

/** 05 S7's demotion, for a view with its own order: every entry past a year moves below every fresher one, and
 *  each half keeps the view's order (a stable partition). The artifact's `order` is this over name order. */
export function demote<T>(items: readonly T[], idOf: (item: T) => string, doc: Freshness = freshness()): T[] {
  const red = (item: T) => entryFreshness(idOf(item), doc).demoted;
  return [...items.filter((i) => !red(i)), ...items.filter(red)];
}

/** The entries in the default sort the build computed. */
export function inDefaultOrder(doc: Freshness = freshness()): EntryFreshness[] {
  return doc.order.map((id) => entryFreshness(id, doc));
}
