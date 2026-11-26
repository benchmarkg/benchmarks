// site/src/lib/vectors.ts -- P6-S1-T06 (08 S4.2, S4.3; 11 S4 "First-query latency"). The document vectors the site
// publishes for the semantic tier: vectors.meta.json and vectors.i8.bin, which `bench build --embed` writes beside the
// corpus (tools/build/embed.py, P6-S1-T03), served at /embed/ (pages/embed/[file].ts) beside the query encoder's files,
// and fetched by islands/search/loader.ts. tools/build/manifest.py hashes canonical JSON into /data/ and a binary has no
// canonical JSON form, so they are not in build-manifest.json; the loader keys its cache on the index commit instead,
// and checks the binary against the sha256 its meta records.
//
// A build without them ships none, and the search page says so (data-vectors), which is every build today: the draft
// preview (scripts/preview_corpus.py) runs no S6, and CI's `bench build` has no --embed. A build that has them checks
// them before anything is published, because a loader that cannot see facets.json cannot tell vectors of another build
// from these: the pair must be whole, the meta the vectors artifact, the binary the length and sha256 the meta records,
// and the ids exactly the rows of the facets.json beside them, in order (cosine.ts loadMatrix's check, made at build
// time). Anything else fails the build and says to rerun `bench build --embed`, rather than shipping vectors that would
// score the wrong benchmarks.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { CORPUS_PATH } from './corpus';

/** The two files, as embed.py names them and /embed/ serves them. */
export const VECTOR_FILES = ['vectors.meta.json', 'vectors.i8.bin'] as const;
export type VectorFile = (typeof VECTOR_FILES)[number];
/** Where the site serves them: beside the query encoder's files (public/embed/). */
export const VECTORS_BASE = '/embed/';

/** The file paths of the vectors beside the corpus at `dir`, checked; null when the build wrote neither. */
export function shippedVectors(dir: string = dirname(CORPUS_PATH)): Record<VectorFile, string> | null {
  const [metaPath, binPath] = VECTOR_FILES.map((f) => join(dir, f));
  const rerun = 'Rerun `uv run --extra embed bench build --embed`, or delete both.';
  if (!existsSync(metaPath) && !existsSync(binPath)) return null;
  if (!existsSync(metaPath) || !existsSync(binPath)) throw new Error(`${dir} holds one of ${VECTOR_FILES.join(' and ')} without the other. ${rerun}`);
  const meta = JSON.parse(readFileSync(metaPath, 'utf8')) as { artifact?: string; ids?: string[]; vectors?: { bytes?: number; sha256?: string } };
  if (meta.artifact !== 'vectors' || !Array.isArray(meta.ids) || meta.vectors == null) throw new Error(`${metaPath} is not the vectors meta tools/build/embed.py writes. ${rerun}`);
  const bin = readFileSync(binPath);
  const sha = createHash('sha256').update(bin).digest('hex');
  if (bin.length !== meta.vectors.bytes || (meta.vectors.sha256 != null && sha !== meta.vectors.sha256)) {
    throw new Error(`${binPath} (${bin.length} bytes, sha256 ${sha}) is not the file ${metaPath} records. ${rerun}`);
  }
  const facetsPath = join(dir, 'facets.json');
  const rows = existsSync(facetsPath) ? (JSON.parse(readFileSync(facetsPath, 'utf8')) as { benchmarks?: { id: string }[] }).benchmarks : undefined;
  const ids = meta.ids;
  if (rows == null || rows.length !== ids.length || rows.some((r, i) => r.id !== ids[i])) {
    throw new Error(`${metaPath} was built against another facets.json: its ids are not ${facetsPath}'s rows in their order. ${rerun}`);
  }
  return { 'vectors.meta.json': metaPath, 'vectors.i8.bin': binPath };
}
