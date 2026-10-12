// site/test/corpus.test.mjs -- P2-S3-T01. src/lib/corpus.ts: the draft-preview guard and the content digest the
// detail route returns as its cacheKey.
//
//   cd site && node --test test/corpus.test.mjs
//
// Node strips corpus.ts's types itself (its only imports besides node: ones are `import type`), so the module is
// loaded as the site loads it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { adoptionCounts, contentDigest, corpusDoc } from '../src/lib/corpus.ts';

const dir = mkdtempSync(join(tmpdir(), 'uaibi-corpus-'));
const write = (name, doc) => {
  const path = join(dir, name);
  writeFileSync(path, JSON.stringify(doc));
  return path;
};
const ENTITIES = { benchmark: [{ id: 'alpha-bench' }], system: [], organization: [], metric: [], source: [] };

test('a published corpus reads without the preview flag', () => {
  delete process.env.UAIBI_SITE_DRAFTS;
  const doc = corpusDoc(write('published.json', { artifact: 'corpus', format: 1, entities: ENTITIES, subsets: [] }));
  assert.equal(doc.drafts, false);
  assert.deepEqual(doc.entities.benchmark.map((b) => b.id), ['alpha-bench']);
});

test('a draft preview is refused unless the build says it is a preview', () => {
  const preview = { artifact: 'corpus', format: 1, entities: ENTITIES, subsets: [], drafts: true };
  delete process.env.UAIBI_SITE_DRAFTS;
  assert.throws(() => corpusDoc(write('preview-refused.json', preview)), /draft preview .* never published/s);
  process.env.UAIBI_SITE_DRAFTS = '0';
  assert.throws(() => corpusDoc(write('preview-zero.json', preview)), /UAIBI_SITE_DRAFTS=1/);
  process.env.UAIBI_SITE_DRAFTS = '1';
  assert.equal(corpusDoc(write('preview-allowed.json', preview)).drafts, true);
  delete process.env.UAIBI_SITE_DRAFTS;
});

test('no corpus file is an empty corpus, and another artifact is refused', () => {
  assert.deepEqual(corpusDoc(join(dir, 'absent.json')).entities.benchmark, []);
  assert.throws(() => corpusDoc(write('facets.json', { artifact: 'facets' })), /not the corpus artifact/);
});

test('the content digest ignores key order and moves with any value', () => {
  const a = { id: 'alpha-bench', data: { access: 'fully-open', size: [{ count: 1, unit: 'tasks' }] } };
  const reordered = { data: { size: [{ unit: 'tasks', count: 1 }], access: 'fully-open' }, id: 'alpha-bench' };
  assert.match(contentDigest(a), /^[0-9a-f]{16}$/);
  assert.equal(contentDigest(a), contentDigest(reordered));
  assert.notEqual(contentDigest(a), contentDigest({ ...a, data: { ...a.data, access: 'gated-registration' } }));
  assert.notEqual(contentDigest([1, 2]), contentDigest([2, 1]));                  // list order is content
  assert.notEqual(contentDigest({ x: null }), contentDigest({}));
});

test('adoption: claims and systems per benchmark, or null when the artifact was not built', () => {
  assert.equal(adoptionCounts(join(dir, 'no-adoption.json')), null);
  const path = write('adoption.json', { artifact: 'adoption', benchmarks: [{ id: 'alpha-bench', claims: 3, systems: 2 }] });
  assert.deepEqual(adoptionCounts(path).get('alpha-bench'), { systems: 2, claims: 3 });
});
