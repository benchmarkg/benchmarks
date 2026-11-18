// site/src/lib/manifest.ts -- P2-S1-T05 (08 S4.4, S6.1). The build manifest beside the corpus, and the one way a page
// names a data artifact: by this build's content-hashed URL.
//
// `bench build` writes build/build-manifest.json next to corpus.json (tools/build/manifest.py): every shipped artifact's
// sha256 and its hashed path, /data/<name>.<sha8>.json, which is the only form a page may reference -- 08 S4.4: "The
// HTML references only the hashed form, emitted by the build, so a deploy can never serve a page against a stale
// artifact." dataHref() returns that path, no page writes a /data/ URL by hand, and S13 (tools/build/manifest.py --site)
// fails on any data reference in the built HTML that the manifest does not name. No manifest means no data link: a
// site build that ran without `bench build` links nothing rather than a file it does not have.
//
// Reading the manifest checks every artifact it names against the file beside it, and throws on a mismatch -- a corpus
// rebuilt without its manifest, or a manifest left from another build -- so a page never links a hashed file other
// than the one it was rendered from.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { CORPUS_PATH } from './corpus';

export interface BuildManifest {
  artifact: 'build-manifest';
  format: number;
  index_commit: string;
  artifacts: Record<string, string>;      // 'corpus.json' -> 'sha256:<64 hex>'
  paths: Record<string, string>;          // 'corpus.json' -> '/data/corpus.<sha8>.json'
}

export const MANIFEST_PATH = join(dirname(CORPUS_PATH), 'build-manifest.json');
const read = new Map<string, BuildManifest | null>();

export function buildManifest(path: string = MANIFEST_PATH): BuildManifest | null {
  if (read.has(path)) return read.get(path) ?? null;
  let doc: BuildManifest | null = null;
  if (existsSync(path)) {
    doc = JSON.parse(readFileSync(path, 'utf8')) as BuildManifest;
    if (doc.artifact !== 'build-manifest' || doc.paths == null || doc.artifacts == null) {
      throw new Error(`${path} is not the build manifest tools/build/manifest.py writes`);
    }
    for (const [name, digest] of Object.entries(doc.artifacts)) {
      const beside = join(dirname(path), name);
      const got = existsSync(beside) ? `sha256:${createHash('sha256').update(readFileSync(beside)).digest('hex')}` : 'missing';
      if (got !== digest) {
        throw new Error(`${path} records ${name} as ${digest}, but ${beside} is ${got}: the manifest is not this build's. `
          + 'Rerun `uv run bench build`.');
      }
    }
  }
  read.set(path, doc);
  return doc;
}

/** This build's content-hashed URL for artifact `name` ('corpus.json'), or null when the build wrote no manifest or
 *  shipped no such artifact. */
export function dataHref(name: string, path?: string): string | null {
  const m = buildManifest(path);
  return m != null && Object.hasOwn(m.paths, name) ? m.paths[name] : null;
}
