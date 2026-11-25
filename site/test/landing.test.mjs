// site/test/landing.test.mjs -- P2-S4-T08 (10 "Information architecture", "Performance budget"; 09 S11.4). What the
// landing page states about the corpus, src/lib/landing.ts, which pages/index.astro renders and Node loads as it is,
// stripping its types:
//
//   cd site && node --test test/landing.test.mjs
//
// The page test, tests/landing.spec.ts, reads the page over the 320-entry draft preview, which is one of the four states.
// The other three -- the published index with no row (what the production build ships today), a build with no
// facets.json, and a published count -- are held here, with the two files the page must refuse to count: one of another
// format, and one whose drafts flag disagrees with the corpus beside it. When a build left facets.json beside the corpus,
// the count is also checked against that file.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { benchmarksWord, corpusSize, formatCount, readFacetsFile } from '../src/lib/landing.ts';
import { FACETS_FORMAT } from '../src/lib/browse-view.ts';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const taxonomy = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/taxonomy.json', import.meta.url)), 'utf8'));
const FAMILIES = Object.keys(taxonomy.facets.domain).filter((id) => !id.includes('/')).length;
const row = (id, domain) => ({ id, slug: id, name: id, aliases: [], editions: [], domain, subdomain: `${domain}/x`, facets: {},
  year: 2024, lifecycle: 'active', verification_max: null, condition_completeness_max: null, claim_count: 0, headroom: null });
const facets = (rows, extra = {}) => ({ artifact: 'facets', format: FACETS_FORMAT, benchmarks: rows, ...extra });

test('no facets.json: the page cannot count, and says so rather than printing a zero', () => {
  assert.deepEqual(corpusSize(null, 19, false), { state: 'unbuilt', benchmarks: null, families: null, familiesTotal: 19 });
});

test('a published facets.json with no row: none published, a count of zero', () => {
  assert.deepEqual(corpusSize(facets([]), 19, false), { state: 'none-published', benchmarks: 0, families: 0, familiesTotal: 19 });
});

test('a published count: the rows, and the distinct families of their primary domains', () => {
  const rows = [row('a', 'code'), row('b', 'code'), row('c', 'mathematics')];
  assert.deepEqual(corpusSize(facets(rows), 19, false), { state: 'published', benchmarks: 3, families: 2, familiesTotal: 19 });
});

test('a draft preview: the same count, in its own state', () => {
  const rows = [row('a', 'code'), row('b', 'vision')];
  assert.deepEqual(corpusSize(facets(rows, { drafts: true }), 19, true), { state: 'preview', benchmarks: 2, families: 2, familiesTotal: 19 });
});

test('a file the browse view cannot read fails the build', () => {
  assert.throws(() => corpusSize(facets([], { format: FACETS_FORMAT - 1 }), 19, false), /format 2, and this view reads format 3/);
  assert.throws(() => corpusSize({ artifact: 'corpus' }, 19, false), /not the facets artifact/);
});

test('a facets.json whose drafts flag disagrees with the corpus fails: a draft count is never a published one', () => {
  assert.throws(() => corpusSize(facets([row('a', 'code')], { drafts: true }), 19, false), /drafts: true, but the corpus beside it says drafts: false/);
  assert.throws(() => corpusSize(facets([row('a', 'code')]), 19, true), /drafts: false, but the corpus beside it says drafts: true/);
});

test('readFacetsFile: null for a missing file, the parsed document otherwise', () => {
  const dir = mkdtempSync(join(tmpdir(), 'landing-'));
  try {
    assert.equal(readFacetsFile(join(dir, 'facets.json')), null);
    writeFileSync(join(dir, 'facets.json'), JSON.stringify(facets([row('a', 'code')])));
    assert.equal(corpusSize(readFacetsFile(join(dir, 'facets.json')), 19, false).benchmarks, 1);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('counts are written as 09 S11.4 says: no separator below 10,000, a comma from there', () => {
  assert.deepEqual([0, 7, 320, 9999, 10000, 123456].map(formatCount), ['0', '7', '320', '9999', '10,000', '123,456']);
  assert.deepEqual([0, 1, 2].map(benchmarksWord), ['benchmarks', 'benchmark', 'benchmarks']);
});

for (const [dir, drafts] of [['build', false], ['build/preview', true]]) {
  const path = join(ROOT, ...dir.split('/'), 'facets.json');
  test(`over ${dir}/facets.json as the emitter wrote it, when a build left one`, { skip: !existsSync(path) && `no ${dir}/facets.json` }, () => {
    const doc = readFacetsFile(path);
    const size = corpusSize(doc, FAMILIES, drafts);
    assert.equal(size.state, drafts ? 'preview' : doc.benchmarks.length === 0 ? 'none-published' : 'published');
    assert.equal(size.benchmarks, doc.benchmarks.length);
    assert.equal(size.families, new Set(doc.benchmarks.map((r) => r.domain)).size);
    assert.ok(size.families <= FAMILIES, 'every row is in a family taxonomy/ defines');
  });
}
