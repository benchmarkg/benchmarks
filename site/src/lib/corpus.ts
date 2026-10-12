// site/src/lib/corpus.ts -- P2-S1-T03. The corpus artifact, typed by the generated interfaces.
//
// build/corpus.json is `bench build`'s (P0-S5-T05; 08 S4.2): every published benchmark, system, organization,
// metric and source. Its records are the Pydantic models' (schema/), so the site types them with the interfaces
// `bench schema gen` generates into src/types/ from the same JSON Schema -- never a second schema of its own
// (content.config.ts says why). No file means an empty corpus: a site build that ran without `bench build`
// (the CI job that only builds the site) renders its pages with nothing in them rather than failing.
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
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

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');
const EMPTY: CorpusEntities = { benchmark: [], system: [], organization: [], metric: [], source: [] };

export function corpus(path: string = join(REPO_ROOT, 'build', 'corpus.json')): CorpusEntities {
  if (!existsSync(path)) return EMPTY;
  const doc = JSON.parse(readFileSync(path, 'utf8')) as { artifact: string; entities: Partial<CorpusEntities> };
  if (doc.artifact !== 'corpus') throw new Error(`${path} is not the corpus artifact (artifact: ${doc.artifact})`);
  return { ...EMPTY, ...doc.entities };
}

export function corpusEntities<K extends keyof CorpusEntities>(kind: K, path?: string): CorpusEntities[K] {
  return corpus(path)[kind];
}
