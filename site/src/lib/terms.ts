// site/src/lib/terms.ts -- P2-S3-T05 (02 S11; 10 "Information architecture": /taxonomy/{facet}/{term}/). Every vocabulary
// term of every facet, read at build time from the governed files themselves -- taxonomy/*.yaml, each declaring `facet:`
// and `terms:` -- so a term page renders exactly the definition, inclusion and exclusion tests, worked examples and
// near misses the taxonomy holds, and nothing the site wrote. (taxonomy.json carries only id, label and status for
// the components; the prose stays in taxonomy/, which is what is read here.) Parsed with js-yaml, the parser Astro's
// own file() loader uses; the Python models remain the taxonomy's only validator.
//
// A term's members are the published benchmarks that carry it: its `field` names the Benchmark field for the facets
// whose terms span several fields (data_properties, execution, governance, lifecycle, ceiling_anchor_type), and the
// rest map one-to-one. maintenance_status is derived from observable signals, never curated, so it has no members
// to list here.
import { load } from 'js-yaml';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Benchmark } from '../types/benchmark';

export interface TermExample {
  ref: string;
  qualifies: boolean;
  why: string;
}
export interface TaxTerm {
  facet: string;
  id: string;
  label: string;
  status: string;
  definition: string;
  inclusion_test?: string;
  exclusion_test?: string;
  examples?: TermExample[];
  see_also?: string[];
  not_to_be_confused_with?: { term: string; distinction: string }[];
  field?: string;
  parent?: string;
  introduced_in?: string;
  derived?: boolean;
  derivation?: string;
}
export interface FacetFile {
  facet: string;
  file: string;               // taxonomy/<name>.yaml
  description: string;
  version: string;
  terms: TaxTerm[];
}

const REPO_ROOT = process.env.REPO_ROOT ?? resolve(process.cwd(), '..');
let memo: FacetFile[] | undefined;

export function facetFiles(root: string = REPO_ROOT): FacetFile[] {
  if (memo && root === REPO_ROOT) return memo;
  const dir = join(root, 'taxonomy');
  const out: FacetFile[] = [];
  for (const name of readdirSync(dir).filter((f) => f.endsWith('.yaml')).sort()) {
    const doc = load(readFileSync(join(dir, name), 'utf8'), { filename: name }) as Record<string, unknown> | null;
    if (doc == null || typeof doc.facet !== 'string' || !Array.isArray(doc.terms)) continue;
    const facet = doc.facet;
    out.push({
      facet, file: `taxonomy/${name}`, description: String(doc.description ?? '').trim(), version: String(doc.version ?? ''),
      terms: (doc.terms as TaxTerm[]).map((t) => ({ ...t, facet })),
    });
  }
  if (root === REPO_ROOT) memo = out;
  return out;
}

export const allTerms = (root?: string): TaxTerm[] => facetFiles(root).flatMap((f) => f.terms);

/** The facet's URL segment: its id in kebab case (evaluation_method -> evaluation-method), as /browse/ spells it. */
export const facetSegment = (facet: string) => facet.replace(/_/g, '-');
export const termHref = (facet: string, id: string) => `/taxonomy/${facetSegment(facet)}/${id}/`;

const FIELD: Record<string, string> = {
  capability: 'capability', evaluation_method: 'evaluation_method', subject: 'designed_for_subjects',
};

function at(record: unknown, dotted: string): unknown {
  return dotted.split('.').reduce<unknown>((x, k) => (x != null && typeof x === 'object' ? (x as Record<string, unknown>)[k] : undefined), record);
}

/** The published benchmarks carrying `term`, with whether it is their primary domain where that matters. Null for a
 *  derived facet, whose members are computed, not curated. */
export function members(term: TaxTerm, benchmarks: Benchmark[]): { benchmark: Benchmark; secondary: boolean }[] | null {
  if (term.facet === 'maintenance_status') return null;
  if (term.facet === 'domain') {
    const hit = (d: string) => d === term.id || d.startsWith(`${term.id}/`);
    return benchmarks
      .filter((b) => hit(b.domain.primary) || (b.domain.secondary ?? []).some(hit))
      .map((b) => ({ benchmark: b, secondary: !hit(b.domain.primary) }));
  }
  const field = FIELD[term.facet] ?? term.field;
  if (field == null) return null;
  return benchmarks.filter((b) => {
    const v = at(b, field);
    const values = Array.isArray(v) ? v : v == null ? [] : [v];
    return values.some((x) => (x !== null && typeof x === 'object' ? (x as { flag?: string }).flag === term.id : x === term.id));
  }).map((b) => ({ benchmark: b, secondary: false }));
}
