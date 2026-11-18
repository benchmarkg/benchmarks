// site/src/lib/croissant.ts -- P2-S3-T06 (08 S5.8; 10 "The permanent citation URL", "Croissant"). The croissant-benchmark
// JSON-LD beside the corpus: build/croissant-benchmark/{id}.jsonld, one per published benchmark, which `bench build`
// (tools/build/croissant.py) validated with mlcroissant and the extension schema before writing it. The detail page
// inlines it in a <script type="application/ld+json"> and serves it as cite.jsonld, both from the text read here, so the
// two are one document. No file means no JSON-LD: the page then carries neither, as it did before the emitter existed.
//
// The documents are the corpus's, written beside it in the same build, so reading one reads the corpus first: its guard
// refuses a draft preview (scripts/preview_corpus.py writes documents too) unless UAIBI_SITE_DRAFTS=1 says the build is one.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { CORPUS_PATH, corpusDoc } from './corpus';

export const CROISSANT_DIR = join(dirname(CORPUS_PATH), 'croissant-benchmark');

const read = new Map<string, string | null>();

/** Benchmark `id`'s document as the build wrote it, or null when the build wrote none. Throws on a file that is not
 *  that benchmark's document, which would otherwise be published under its name. */
export function croissantText(id: string, dir: string = CROISSANT_DIR): string | null {
  const path = join(dir, `${id}.jsonld`);
  if (read.has(path)) return read.get(path) ?? null;
  corpusDoc();
  let out: string | null = null;
  if (existsSync(path)) {
    out = readFileSync(path, 'utf8');
    const doc = JSON.parse(out) as { benchmarkId?: unknown; '@type'?: unknown };
    if (doc.benchmarkId !== id || !Array.isArray(doc['@type']) || doc['@type'][0] !== 'sc:Dataset') {
      throw new Error(`${path} is not ${id}'s croissant-benchmark document (tools/build/croissant.py)`);
    }
  }
  read.set(path, out);
  return out;
}

/** JSON text that is safe as the content of a <script> element: every `<` is written <, which a JSON parser reads
 *  back as `<`, so no string in the document can close the element (`</script>`) or open a comment (`<!--`). The value is
 *  unchanged; only its spelling is. */
export function scriptSafe(json: string): string {
  return json.trimEnd().replace(/</g, '\\u003c');
}
