// site/src/lib/ingestHealth.ts -- P5-S7-T03. Every source's health, as the build derived it (07 S9.1, 06 S3.0).
//
// The data is tools/build/ingest_health.py's artifact. In order of preference the site reads:
//   1. INGEST_HEALTH, a path to an ingest-health JSON file (a fixture build sets it);
//   2. build/derived/ingest-health.json, which `bench build --derived` writes before the site build;
//   3. otherwise it runs ingest_health.py itself (BENCH_PYTHON, default `python`), so a bare `astro build`
//      on a clean checkout still publishes every source's health -- never a page without it.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

export type AdapterStatus = 'ok' | 'degraded' | 'broken' | 'retired' | 'not-yet-run';

export interface SourceHealth {
  adapter: string;
  adapter_version: string;
  tier: number | null;
  licence: string | null;
  licence_class: string;
  licence_checked_on: string | null;
  licence_basis: string;
  attribution: string | null;
  attribution_note: string | null;
  last_successful_fetch: string | null;
  fetch_basis: string | null;
  last_content_change: string | null;
  days_since_success: number | null;
  record_count: number;
  adapter_status: AdapterStatus;
  last_run_status: string | null;
  badge: 'stale' | 'source-retired' | null;
}

export interface IngestHealth {
  artifact: 'ingest-health';
  format: number;
  as_of: string;
  slo: string;
  stale_after_days: Record<string, number>;
  sources: SourceHealth[];
}

export const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');

/** What each status means, in the words the page prints beside it. */
export const STATUS_LABEL: Record<AdapterStatus, string> = {
  ok: 'OK',
  degraded: 'Degraded',
  broken: 'Broken',
  retired: 'Retired',
  'not-yet-run': 'No scheduled run logged yet',
};

let cache: IngestHealth | undefined;

export function ingestHealth(): IngestHealth {
  if (cache) return cache;
  const fromEnv = process.env.INGEST_HEALTH;
  const built = join(REPO_ROOT, 'build', 'derived', 'ingest-health.json');
  let text: string;
  if (fromEnv) {
    text = readFileSync(isAbsolute(fromEnv) ? fromEnv : join(REPO_ROOT, fromEnv), 'utf8');
  } else if (existsSync(built)) {
    text = readFileSync(built, 'utf8');
  } else {
    text = execFileSync(process.env.BENCH_PYTHON ?? 'python',
      [join(REPO_ROOT, 'tools', 'build', 'ingest_health.py'), '--root', REPO_ROOT], { encoding: 'utf8' });
  }
  const doc = JSON.parse(text) as IngestHealth;
  if (doc.artifact !== 'ingest-health' || !doc.slo || !Array.isArray(doc.sources)) {
    throw new Error('ingest-health: not the artifact tools/build/ingest_health.py writes');
  }
  cache = doc;
  return cache;
}
