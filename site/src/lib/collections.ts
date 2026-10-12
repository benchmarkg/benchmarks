// site/src/lib/collections.ts -- P2-S1-T03. The content collections, read as the generated interfaces.
//
// A collection declared without a schema hands its entries' data over untyped; these accessors give each one the
// interface `bench schema gen` generated from the Pydantic model, so a page that reads a benchmark is checked by
// `npx tsc --noEmit` against the same shape `bench validate` enforces.
import { getCollection } from 'astro:content';
import type { Benchmark } from '../types/benchmark';
import type { Metric } from '../types/metric';
import type { Organization } from '../types/organization';
import type { Source } from '../types/source';
import type { System } from '../types/system';

export async function benchmarks(): Promise<Benchmark[]> {
  return (await getCollection('benchmarks')).map((e) => e.data as Benchmark);
}

export async function systems(): Promise<System[]> {
  return (await getCollection('systems')).map((e) => e.data as System);
}

export async function organizations(): Promise<Organization[]> {
  return (await getCollection('organizations')).map((e) => e.data as Organization);
}

export async function metrics(): Promise<Metric[]> {
  return (await getCollection('metrics')).map((e) => e.data as Metric);
}

export async function sources(): Promise<Source[]> {
  return (await getCollection('sources')).map((e) => e.data as Source);
}
