// site/src/lib/claims.ts -- P2-S3-T02, P3-S10-T07. One claim as the provenance drill-down reads it: the claims.json row
// 08 S4.2 describes ("every claim ... with its EvalConditions inlined, plus comparability_key, artifact_url,
// provenance_snapshot and source refs"), which P3-S10-T03 emits (tools/build/claims.py). The drill-down was built
// against test/fixtures/provenance-claims.json before the artifact existed, and that fixture keeps the same shape.
//
// P3-S10-T07 reads the artifact itself, at build time, for the pages that render claims: /claims/{id}/ (one per row,
// 10 "Information architecture"), /conditions/{id}/ (one per condition record a row inlines), and the claim lists of
// the benchmark and system pages. claims.json sits beside the corpus (build/claims.json, or the draft preview's
// build/preview/claims.json), and UAIBI_CLAIMS points the site at another one, as UAIBI_CORPUS does for the corpus
// (tests/e2e/fixtures/make_claims_fixture.py writes one for tests/e2e/provenance-drilldown.spec.ts). No file means no
// claims: a page says the artifact is not in this build rather than showing none.
//
// The rules read here, so a page cannot render past them:
//   - 08 S7.5 Decision 1: "machine-ingested claims get no permalink page". claims.json never holds one (P3-S10-T03
//     refuses it), and reading one that does throws, so no /claims/{id}/ page is ever built for one. Their rows live in
//     claims-ingested/<benchmark>.json, which a page reads only for their count and the attribution they carry;
//   - a draft preview's claims.json says `"drafts": true`, and reading one throws unless UAIBI_SITE_DRAFTS=1, as
//     corpus.ts refuses a preview corpus;
//   - 07 S2.3: "Verification rank and review state render together, always." `reviewState` is the second axis for
//     every claim: `ingestion.review_state` (04 S9's four values), or `hand-curated` for a claim with no ingestion block
//     (04 S9: the block is "null on hand-curated ones"). VerificationBadge.astro takes it, and throws without it;
//   - 04 S9: "any page rendering an ingested record shows its attribution inline". `attribution` is that line's data.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve, sep } from 'node:path';
import { CORPUS_PATH } from './corpus';
import { rank } from './vocab';
import type { EvalConditions } from '../types/eval-conditions';
import type { Metric } from '../types/metric';
import type { Ingestion, ResultClaim } from '../types/result-claim';

/** tools/build/comparability.py Comparability.as_dict(): 04 S8's three numbers, and the unknown set. */
export interface ClaimComparability {
  comparability_key: string;
  key_unknown_count: number;
  condition_completeness: number | null;     // null only when every material field was waived
  unknown_fields: string[];
  fields_material_total: number;
}

/** The source a claim cites, reduced to what a citation needs (09 S6.6). */
export interface ClaimSource {
  id: string;
  type: string;
  title: string | null;
  url: string;
  publisher: string | null;
  accessed: string | null;
  fetched_at: string | null;
  archive_url: string | null;
  archive_captured: string | null;
  archive_status: string;
  licence_class: string;
}

export interface ClaimRow {
  claim: ResultClaim;
  conditions: EvalConditions | null;          // inlined; null when the claim names no condition record
  comparability: ClaimComparability;
  material: string[];                         // the benchmark's resolved material fields (04 S8), sorted
  weights: Record<string, number>;            // per material field; 2.0 where 04 S8 doubles one
  key_shared_with: number;                    // other claims with the same comparability_key
  source: ClaimSource | null;
  reporter: { id: string; name: string | null };
  badge?: 'machine-ingested';                 // a claims-ingested/ row only (tools/build/claims.py)
}

// ---- the review state, the badge's second axis -------------------------------------------------------------------

export const MACHINE_INGESTED = 'machine-ingested';
export const HAND_CURATED = 'hand-curated';
/** 04 S9's four `ingestion.review_state` values, then the state of a claim with no ingestion block. */
export const REVIEW_STATES = [MACHINE_INGESTED, 'spot-checked', 'human-reviewed', 'promoted', HAND_CURATED] as const;
export type ReviewMark = (typeof REVIEW_STATES)[number];

/** A claim's review state: its ingestion block's, or hand-curated when it has none. An ingestion block that names no
 *  review_state is machine-ingested, the default schema/claim.py's Ingestion gives it. */
export function reviewState(c: ResultClaim): ReviewMark {
  if (c.ingestion == null) return HAND_CURATED;
  return c.ingestion.review_state ?? MACHINE_INGESTED;
}

/** The inline attribution 04 S9 requires beside an ingested record, or null for a hand-curated claim. */
export function attribution(c: ResultClaim): Ingestion | null {
  return c.ingestion ?? null;
}

// ---- the routes ----------------------------------------------------------------------------------------------------

/** /claims/{claim-id}/, the single-claim permalink (10 "Information architecture"). */
export const claimHref = (id: string) => `/claims/${id}/`;
/** /conditions/{cond-id}/, a shared EvalConditions record. */
export const conditionsHref = (id: string) => `/conditions/${id}/`;
export const baseId = (ref: string) => ref.split('@', 1)[0].split('#', 1)[0];

// ---- reading the artifact ------------------------------------------------------------------------------------------

export interface ClaimsDoc {
  rows: ClaimRow[];                           // claims.json's, curated tier, in claim-id order
  machine_ingested: Record<string, number>;   // benchmark id -> rows its claims-ingested/<id>.json holds
  drafts: boolean;
  dir: string;                                // where claims.json is, so claims-ingested/ is read beside it
}

export const CLAIMS_PATH = process.env.UAIBI_CLAIMS ? resolve(process.env.UAIBI_CLAIMS) : join(dirname(CORPUS_PATH), 'claims.json');
const docs = new Map<string, ClaimsDoc | null>();

/** claims.json, checked against the rules above; null when the build did not write it. */
export function claimsDoc(path: string = CLAIMS_PATH): ClaimsDoc | null {
  if (docs.has(path)) return docs.get(path)!;
  let doc: ClaimsDoc | null = null;
  if (existsSync(path)) {
    const raw = JSON.parse(readFileSync(path, 'utf8')) as {
      artifact: string; tier: string; claims: ClaimRow[]; machine_ingested?: Record<string, number>; drafts?: boolean;
    };
    if (raw.artifact !== 'claims' || raw.tier !== 'curated') {
      throw new Error(`${path} is not the curated claims artifact (artifact: ${raw.artifact}, tier: ${raw.tier})`);
    }
    if (raw.drafts === true && process.env.UAIBI_SITE_DRAFTS !== '1') {
      throw new Error(`${path} is a draft preview's claims artifact: it holds claims on ai-drafted-unverified entries, which are `
        + 'never published (05 S4). Set UAIBI_SITE_DRAFTS=1 to build a preview that is not deployed.');
    }
    const seen = new Set<string>();
    for (const row of raw.claims) {
      const id = row.claim.id;
      if (seen.has(id)) throw new Error(`${path}: ${id} is in it twice, so /claims/${id}/ would be two pages`);
      seen.add(id);
      if (row.badge === MACHINE_INGESTED || reviewState(row.claim) === MACHINE_INGESTED) {
        throw new Error(`${path}: ${id} is machine-ingested, and machine-ingested claims get no permalink page `
          + '(08 S7.5 Decision 1); its row belongs in claims-ingested/, which P3-S10-T03 keeps it to');
      }
    }
    doc = { rows: raw.claims, machine_ingested: raw.machine_ingested ?? {}, drafts: raw.drafts === true, dir: dirname(path) };
  }
  docs.set(path, doc);
  return doc;
}

/** claims-ingested/<benchmark>.json beside claims.json: the machine-ingested rows, each badged. Empty when claims.json
 *  counts none for the benchmark; a file claims.json counts that is missing or holds another count throws. */
export function ingestedRows(benchmark: string, doc: ClaimsDoc | null = claimsDoc()): ClaimRow[] {
  const want = doc?.machine_ingested[benchmark] ?? 0;
  if (doc == null || want === 0) return [];
  const path = join(doc.dir, 'claims-ingested', `${benchmark}.json`);
  if (!existsSync(path)) throw new Error(`${path} is missing, but claims.json counts ${want} machine-ingested claim(s) on ${benchmark}`);
  const raw = JSON.parse(readFileSync(path, 'utf8')) as { artifact: string; benchmark: string; badge: string; claims: ClaimRow[] };
  if (raw.artifact !== 'claims-ingested' || raw.benchmark !== benchmark || raw.badge !== MACHINE_INGESTED) {
    throw new Error(`${path} is not the badged claims-ingested file for ${benchmark}`);
  }
  if (raw.claims.length !== want) throw new Error(`${path} holds ${raw.claims.length} row(s), but claims.json counts ${want}`);
  for (const row of raw.claims) {
    if (row.badge !== MACHINE_INGESTED || reviewState(row.claim) !== MACHINE_INGESTED || row.claim.ingestion == null) {
      throw new Error(`${path}: ${row.claim.id} is not a badged machine-ingested row with its ingestion block`);
    }
  }
  return raw.claims;
}

/** Every condition record the rows inline, by id, with the rows that name it, both in id order. */
export function conditionRecords(rows: ClaimRow[]): Map<string, { conditions: EvalConditions; rows: ClaimRow[] }> {
  const out = new Map<string, { conditions: EvalConditions; rows: ClaimRow[] }>();
  for (const row of rows) {
    if (row.conditions == null) continue;
    const hit = out.get(row.conditions.id);
    if (hit == null) out.set(row.conditions.id, { conditions: row.conditions, rows: [row] });
    else hit.rows.push(row);
  }
  return new Map([...out.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
}

// ---- order ---------------------------------------------------------------------------------------------------------

/** How far a value is from its metric's optimum, smaller first; null when the metric gives no direction. */
function distance(value: number, m: Metric | undefined): number | null {
  if (m == null) return null;
  if (m.optimum === 'max') return -value;
  if (m.optimum === 'min') return value;
  if (m.optimum === 'zero') return Math.abs(value);
  return m.optimum_target != null ? Math.abs(value - m.optimum_target) : null;
}

/** 10 V6 item 10's order, "sorted by verification then value": the highest rung first; then by metric, so values are
 *  only ever ordered against values of the same metric; then nearest the metric's optimum (04 S6), a direction the
 *  metric does not give leaving the claim id to decide; a claim with no number after those with one. */
export function sortClaims(rows: ClaimRow[], metrics: Map<string, Metric>): ClaimRow[] {
  const key = (r: ClaimRow) => {
    const v = r.claim.value;
    return v != null ? distance(v, metrics.get(r.claim.metric)) : null;
  };
  return [...rows].sort((a, b) => {
    const byRank = rank(b.claim.verification) - rank(a.claim.verification);
    if (byRank !== 0) return byRank;
    if (a.claim.metric !== b.claim.metric) return a.claim.metric < b.claim.metric ? -1 : 1;
    const [ka, kb] = [key(a), key(b)];
    if (ka != null && kb != null && ka !== kb) return ka - kb;
    if ((ka == null) !== (kb == null)) return ka == null ? 1 : -1;
    return a.claim.id < b.claim.id ? -1 : a.claim.id > b.claim.id ? 1 : 0;
  });
}

// ---- the record at a commit ----------------------------------------------------------------------------------------

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');
let files: Map<string, string> | undefined;

/** The file under data/claims/ that holds a claim, from the repository root (05 S2: one file per claim, named by its
 *  id), so its page can link the YAML at the commit; null when no file there holds it. */
export function claimYamlPath(id: string): string | null {
  if (files == null) {
    files = new Map();
    const dir = join(REPO_ROOT, 'data', 'claims');
    if (existsSync(dir)) {
      for (const rel of (readdirSync(dir, { recursive: true }) as string[]).map((p) => p.split(sep).join('/')).sort()) {
        const name = rel.split('/').pop() ?? '';
        if (name.endsWith('.yaml')) files.set(name.slice(0, -'.yaml'.length), `data/claims/${rel}`);
      }
    }
  }
  return files.get(id) ?? null;
}
