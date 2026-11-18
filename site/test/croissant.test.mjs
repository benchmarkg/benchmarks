// site/test/croissant.test.mjs -- P2-S3-T06. src/lib/croissant.ts: reading the build's croissant-benchmark JSON-LD and
// making it safe to inline in a <script type="application/ld+json">.
//
//   cd site && node --test test/croissant.test.mjs
//
// The module imports ./corpus without an extension, as the site's modules do, so it is loaded through Vite, the way
// lineage.test.mjs loads its component. The documents themselves are tools/build/croissant.py's, validated by
// tests/build/test_croissant.py; this checks the site's half: an absent document is no JSON-LD, a file that is not the
// benchmark's document is refused, the inlined text parses to exactly the document with no `<` left in it, and the
// citation block links cite.jsonld only where the page says it exists. When the draft preview has been built
// (`uv run python scripts/preview_corpus.py --out build/preview`), its documents are read too.
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { getViteConfig } from 'astro/config';
import { createServer } from 'vite';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const PREVIEW = fileURLToPath(new URL('../../build/preview/croissant-benchmark/', import.meta.url));

let server;
let lib;
let container;
before(async () => {
  const config = await getViteConfig({ logLevel: 'silent' }, { logLevel: 'silent' })({ command: 'serve', mode: 'test' });
  server = await createServer({ ...config, root: SITE, configFile: false, logLevel: 'silent', appType: 'custom',
    server: { middlewareMode: true, hmr: false, ws: false } });
  lib = await server.ssrLoadModule('/src/lib/croissant.ts');
  container = await AstroContainer.create();
});
after(async () => { await server?.close(); });

const dir = mkdtempSync(join(tmpdir(), 'uaibi-croissant-'));
const DOC = {
  '@context': { '@vocab': 'https://schema.org/', cb: 'https://host.invalid/ns/croissant-benchmark/v1#' },
  '@type': ['sc:Dataset', 'cb:Benchmark'], benchmarkId: 'alpha-bench', name: 'Alpha </script><!-- & <b>',
};

test('no document is no JSON-LD', () => {
  assert.equal(lib.croissantText('absent-bench', dir), null);
});

test('the document is read as the build wrote it, and a file that is not that benchmark\'s is refused', () => {
  const text = `${JSON.stringify(DOC)}\n`;
  writeFileSync(join(dir, 'alpha-bench.jsonld'), text);
  assert.equal(lib.croissantText('alpha-bench', dir), text);
  writeFileSync(join(dir, 'beta-bench.jsonld'), JSON.stringify(DOC));
  assert.throws(() => lib.croissantText('beta-bench', dir), /not beta-bench's croissant-benchmark document/);
  writeFileSync(join(dir, 'gamma-bench.jsonld'), JSON.stringify({ ...DOC, benchmarkId: 'gamma-bench', '@type': 'cb:Benchmark' }));
  assert.throws(() => lib.croissantText('gamma-bench', dir), /not gamma-bench's/);
});

test('the inlined text cannot close its <script> or open a comment, and parses to the same document', () => {
  const safe = lib.scriptSafe(`${JSON.stringify(DOC)}\n`);
  assert.doesNotMatch(safe, /</);
  assert.doesNotMatch(safe, /\n$/);
  assert.deepEqual(JSON.parse(safe), DOC);
  assert.equal(JSON.parse(safe).name, 'Alpha </script><!-- & <b>');
});

test('the preview\'s documents, when built, read and inline cleanly', (t) => {
  if (!existsSync(PREVIEW)) {
    t.skip('build the preview first: uv run python scripts/preview_corpus.py --out build/preview');
    return;
  }
  const ids = readdirSync(PREVIEW).filter((f) => f.endsWith('.jsonld') && !f.startsWith('_')).map((f) => f.slice(0, -7));
  assert.ok(ids.length > 0);
  for (const id of ids) {
    const text = lib.croissantText(id, PREVIEW);
    assert.deepEqual(JSON.parse(lib.scriptSafe(text)), JSON.parse(text), id);
  }
});

test('the citation block links the formats the page says exist, and only those', async () => {
  const CiteThis = (await server.ssrLoadModule('/src/components/CiteThis.astro')).default;
  const props = { entity_id: 'alpha-bench', title: 'Alpha', commit_sha: '0123456789abcdef0123456789abcdef01234567',
    release_doi: null, retrieved_at: '2026-11-18', yaml_path: 'data/benchmarks/code/alpha-bench.yaml',
    formats_base: '/benchmarks/alpha-bench/' };
  const every = await container.renderToString(CiteThis, { props });
  assert.match(every, /href="\/benchmarks\/alpha-bench\/cite\.jsonld"[^>]*>Croissant-benchmark JSON-LD</);
  const four = await container.renderToString(CiteThis, { props: { ...props, formats: ['bib', 'json', 'ris', 'yaml'] } });
  assert.doesNotMatch(four, /cite\.jsonld/);
  assert.deepEqual([...four.matchAll(/data-format="(\w+)"/g)].map((m) => m[1]), ['bib', 'json', 'ris', 'yaml']);
});
