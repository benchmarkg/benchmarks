// site/src/content.config.ts -- P2-S1-T01.
//
// There is one schema and one validator: the Pydantic models under schema/, run by
// `bench validate` before the S8 emitter writes build/*.json (04 S12, 08 S3). A collection that
// declared a Zod schema here would be a second validator with its own opinion of what is valid,
// and it would drift from the first. So every collection is declared WITHOUT `schema`; the types
// the site uses come from site/src/types/, generated from the same JSON Schema (05 S3).
//
// The collections read build/corpus.json, `bench build`'s artifact (P2-S1-T03; src/lib/corpus.ts), and the pages
// read them through src/lib/collections.ts, which types every entry with the generated interface.
// test/config.test.mjs fails if any defineCollection() call here gains a `schema`.
import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { corpusEntities } from './lib/corpus';

export const collections = {
  benchmarks: defineCollection({ loader: () => corpusEntities('benchmark') }),
  systems: defineCollection({ loader: () => corpusEntities('system') }),
  organizations: defineCollection({ loader: () => corpusEntities('organization') }),
  metrics: defineCollection({ loader: () => corpusEntities('metric') }),
  sources: defineCollection({ loader: () => corpusEntities('source') }),
  // P2-S3-T05: the three narrative documents the site renders at /docs/{slug}/ (10 "Information architecture"). Prose,
  // not records, so there is nothing for a schema to validate; only these three of docs/ are published.
  docs: defineCollection({ loader: glob({ pattern: '{methodology,provenance,comparability}.md', base: '../docs' }) }),
};
