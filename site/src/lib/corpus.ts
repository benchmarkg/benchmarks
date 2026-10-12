// site/src/lib/corpus.ts -- P2-S1-T03. The corpus artifact, typed by the generated interfaces.
//
// build/corpus.json is `bench build`'s (P0-S5-T05; 08 S4.2): every published benchmark, system, organization,
// metric and source. Its records are the Pydantic models' (schema/), so the site types them with the interfaces
// `bench schema gen` generates into src/types/ from the same JSON Schema -- never a second schema of its own
// (content.config.ts says why). No file means an empty corpus: a site build that ran without `bench build`
// (the CI job that only builds the site) renders its pages with nothing in them rather than failing.
//
// UAIBI_CORPUS points the site at another corpus.json (P2-S3-T01): the page tests build from the draft preview
// scripts/preview_corpus.py writes (build/preview/), because no entry is published yet. A preview corpus says
// `"drafts": true`, and reading one throws unless UAIBI_SITE_DRAFTS=1 says the build is a preview: AI-drafted,
// unverified entries are never published (05 S4), so a preview must not become the deployed site by accident.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import type { Benchmark } from '../types/benchmark';
import type { Metric } from '../types/metric';
import type { Organization } from '../types/organization';
import type { Source } from '../types/source';
import type { System } from '../types/system';

export interface CorpusEntities {
  benchmark: Benchmark[];
  system: System[];
  organization: Organization[];
  metric: Metric[];
  source: Source[];
}

/** One materialised subset (tools/build/artifacts.py resolve_subsets): its facets resolved field by field, and
 *  `overrides` naming the facets the subset declares itself rather than inherits. */
export interface SubsetRow {
  id: string;
  benchmark: string;
  parent: string | null;
  label: string;
  depth: number;
  overrides: string[];
  facets: Record<string, unknown>;
}

export interface CorpusDoc {
  entities: CorpusEntities;
  subsets: SubsetRow[];
  drafts: boolean;
}

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');
const EMPTY: CorpusEntities = { benchmark: [], system: [], organization: [], metric: [], source: [] };
export const CORPUS_PATH = process.env.UAIBI_CORPUS ? resolve(process.env.UAIBI_CORPUS) : join(REPO_ROOT, 'build', 'corpus.json');
const read = new Map<string, CorpusDoc>();

export function corpusDoc(path: string = CORPUS_PATH): CorpusDoc {
  const hit = read.get(path);
  if (hit) return hit;
  let doc: CorpusDoc = { entities: EMPTY, subsets: [], drafts: false };
  if (existsSync(path)) {
    const raw = JSON.parse(readFileSync(path, 'utf8')) as {
      artifact: string; entities: Partial<CorpusEntities>; subsets?: SubsetRow[]; drafts?: boolean;
    };
    if (raw.artifact !== 'corpus') throw new Error(`${path} is not the corpus artifact (artifact: ${raw.artifact})`);
    if (raw.drafts === true && process.env.UAIBI_SITE_DRAFTS !== '1') {
      throw new Error(`${path} is a draft preview (scripts/preview_corpus.py): it holds ai-drafted-unverified entries, which `
        + 'are never published (05 S4). Set UAIBI_SITE_DRAFTS=1 to build a preview that is not deployed.');
    }
    doc = { entities: { ...EMPTY, ...raw.entities }, subsets: raw.subsets ?? [], drafts: raw.drafts === true };
  }
  read.set(path, doc);
  return doc;
}

export function corpus(path?: string): CorpusEntities {
  return corpusDoc(path).entities;
}

export function corpusEntities<K extends keyof CorpusEntities>(kind: K, path?: string): CorpusEntities[K] {
  return corpus(path)[kind];
}

export interface Adoption {
  systems: number;    // distinct systems with a claim
  claims: number;     // claims recorded, both tiers
}

/** build/derived/adoption.json beside the corpus (tools/build/adoption.py, 12 S6): per benchmark, its claims and the
 *  distinct systems they are about. Null when the artifact was not built, which a page says rather than showing a
 *  zero; a benchmark the artifact does not list has no claim. */
export function adoptionCounts(path: string = join(dirname(CORPUS_PATH), 'derived', 'adoption.json')): Map<string, Adoption> | null {
  if (!existsSync(path)) return null;
  const doc = JSON.parse(readFileSync(path, 'utf8')) as { artifact: string; benchmarks: ({ id: string } & Adoption)[] };
  if (doc.artifact !== 'adoption') throw new Error(`${path} is not the adoption artifact (artifact: ${doc.artifact})`);
  return new Map(doc.benchmarks.map((b) => [b.id, { systems: b.systems, claims: b.claims }]));
}

/** JSON with every object's keys sorted, so equal content has one spelling whatever order it was built in. */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const o = value as Record<string, unknown>;
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

/** A content digest: sha256 over the canonical JSON, 16 hex digits. Equal content, equal digest. */
export function contentDigest(value: unknown): string {
  return createHash('sha256').update(canonical(value)).digest('hex').slice(0, 16);
}
