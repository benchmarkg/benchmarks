// site/src/content.config.ts -- P2-S1-T01.
//
// There is one schema and one validator: the Pydantic models under schema/, run by
// `bench validate` before the S8 emitter writes build/*.json (04 S12, 08 S3). A collection that
// declared a Zod schema here would be a second validator with its own opinion of what is valid,
// and it would drift from the first. So every collection is declared WITHOUT `schema`; the types
// the site uses come from site/src/types/, generated from the same JSON Schema (05 S3).
//
// Collections over the S8 artifacts arrive with the emitter (P2-S1-T02 onward).
// test/config.test.mjs fails if any defineCollection() call here gains a `schema`.

export const collections = {};
