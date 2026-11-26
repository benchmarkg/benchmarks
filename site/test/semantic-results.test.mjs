// site/test/semantic-results.test.mjs -- P6-S1-T09 (10 V11 "Search: three tiers"; 11 F0 "Made visible"). The semantic
// tier as the search box's later tier, src/islands/search/semantic.ts, loaded by Node as it is (its types stripped),
// with the real query encoder over the files in public/embed/ and a synthetic document matrix in tools/build/embed.py's
// format:
//
//   cd site && node --test test/semantic-results.test.mjs
//
// The ledger's verify is the accessibility harness over the browse view; the block itself is held in a browser by
// tests/semantic-results.spec.ts, which also holds the DOM assertion of two separately labelled regions. This file holds
// what that spec reads off the tier: the label is 10 V11's words; the entry table links only pages the build rendered
// and survives a `</script>` in a name; the hits are the cosine ranking's, best first, capped, skipping a row the table
// does not name; a stack without document vectors, or a page with no table, gives no tier at all, so no block; a query
// with no token the encoder holds gives no hit, so no block; a question a later keystroke has overtaken is refused; and a
// failed load gives a tier that answers with the failure.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { QueryEncoder, dequantise } from '../src/islands/search/encoder.ts';
import { loadMatrix } from '../src/islands/search/cosine.ts';
import {
  SEMANTIC_HEADING, SEMANTIC_ID, SEMANTIC_NAME, SEMANTIC_NOTE, SEMANTIC_TOP, benchmarkUrl, entriesJson, entryTable,
  readEntries, semanticHits, semanticTier, unavailableTier,
} from '../src/islands/search/semantic.ts';

const EMBED = new URL('../public/embed/', import.meta.url);
const bytes = (f) => new Uint8Array(readFileSync(new URL(f, EMBED)));
const META = JSON.parse(readFileSync(new URL('potion-8m-pruned.meta.json', EMBED), 'utf8'));
const TOKENIZER = JSON.parse(readFileSync(new URL('tokenizer.json', EMBED), 'utf8'));
const ENCODER = new QueryEncoder(TOKENIZER, META, dequantise(META, bytes('potion-8m-pruned.i8.bin'), bytes('potion-8m-pruned.r2.bin')));
const QUERY = 'protein structure prediction';

/** A deterministic stream of int8 values in [-100, 100]. */
function* noise(seed) {
  let s = seed >>> 0;
  for (;;) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    yield (s % 201) - 100;
  }
}

/** A `rows` x 256 matrix in embed.py's format, row `near` the query's own vector quantised, every other row noise. */
function matrix(rows, near) {
  const dims = ENCODER.dims;
  const bin = new Int8Array(rows * dims);
  const scales = [];
  const n = noise(7);
  for (let i = 0; i < rows; i++) {
    if (i === near) {
      const v = ENCODER.encode(QUERY);
      const scale = Math.max(...v.map(Math.abs)) / 127;
      for (let k = 0; k < dims; k++) bin[i * dims + k] = Math.round(v[k] / scale);
      scales.push(scale);
    } else {
      for (let k = 0; k < dims; k++) bin[i * dims + k] = n.next().value;
      scales.push(0.01);
    }
  }
  const ids = Array.from({ length: rows }, (_, i) => `bench-${i}`);
  return loadMatrix({ artifact: 'vectors', format: 1, rows, dims, ids, scales, vectors: { bytes: bin.length } }, bin);
}

const stackOf = (vectors) => ({ commit: 'a'.repeat(40), source: 'network', encoder: ENCODER, vectors });
const tableOf = (rows) => readEntries(entriesJson(Array.from({ length: rows }, (_, i) => [`bench-${i}`, `Bench ${i}`])));
const live = () => new AbortController().signal;

test('the block is labelled in 10 V11\'s words, as related entries the reader did not type the words for', () => {
  assert.equal(SEMANTIC_ID, 'semantic');
  assert.equal(SEMANTIC_NAME, 'Semantic search');
  assert.match(SEMANTIC_HEADING, /^Related benchmarks you did not type the words for$/);
  assert.match(SEMANTIC_NOTE, /without matching its words/);
  assert.match(SEMANTIC_NOTE, /above are unchanged/);
});

test('the entry table links only pages the build rendered, in order, and survives a </script> in a name', () => {
  const rows = [{ id: 'mmlu', name: 'MMLU' }, { id: 'left-out', name: 'Left out' }, { id: 'tricky', name: 'A </script><b>name' }];
  const table = entryTable(rows, (url) => url !== benchmarkUrl('left-out'));
  assert.deepEqual(table, [['mmlu', 'MMLU'], ['tricky', 'A </script><b>name']]);
  const json = entriesJson(table);
  assert.ok(!json.includes('<'), 'no < survives inside the <script>');
  assert.deepEqual([...readEntries(json)], [
    ['mmlu', { url: '/benchmarks/mmlu/', title: 'MMLU' }],
    ['tricky', { url: '/benchmarks/tricky/', title: 'A </script><b>name' }],
  ]);
  // anything else is no entry, never an error
  for (const bad of [null, undefined, '', '  ', '{', '{"a": 1}', '[["only-one"]]', '[[1, "x"]]', '[["", "x"]]']) {
    assert.equal(readEntries(bad).size, 0, String(bad));
  }
  assert.deepEqual([...readEntries('[["ok", "OK"], ["bad"], 3]').keys()], ['ok']);
});

test('the hits are the cosine ranking\'s, best first: the row nearest the query first, and SEMANTIC_TOP at most', async () => {
  const vectors = matrix(40, 17);
  const tier = await semanticTier(stackOf(vectors), tableOf(40));
  assert.equal(tier.id, SEMANTIC_ID);
  assert.equal(tier.heading, SEMANTIC_HEADING);
  assert.equal(tier.note, SEMANTIC_NOTE);
  const hits = await tier.search(QUERY, live());
  assert.equal(hits.length, SEMANTIC_TOP);
  assert.deepEqual(hits[0], { url: '/benchmarks/bench-17/', title: 'Bench 17', type: 'benchmark', excerpt: '' });
  assert.equal(new Set(hits.map((h) => h.url)).size, hits.length, 'no row twice');
  // the same question, the same answer
  assert.deepEqual(await tier.search(QUERY, live()), hits);
});

test('a row the entry table does not name is skipped, never linked; fewer rows than SEMANTIC_TOP are all shown', () => {
  const vectors = matrix(5, 2);
  const ranked = [0, 1, 2, 3, 4].map((row) => ({ row, score: 1 - row / 10 }));
  const entries = readEntries(entriesJson([['bench-0', 'Zero'], ['bench-3', 'Three'], ['bench-4', 'Four']]));
  assert.deepEqual(semanticHits(ranked, vectors, entries).map((h) => h.title), ['Zero', 'Three', 'Four']);
});

test('no vectors, or no entry table, is no tier: nothing to rank, so no block, ever', async () => {
  assert.equal(await semanticTier(stackOf(null), tableOf(3)), null);
  assert.equal(await semanticTier(stackOf(matrix(3, 0)), new Map()), null);
});

test('a query with no token the encoder holds is the zero vector: no hit, so no block', async () => {
  const tier = await semanticTier(stackOf(matrix(10, 3)), tableOf(10));
  assert.deepEqual(await tier.search('', live()), []);
  assert.deepEqual(await tier.search('   ', live()), []);
});

test('a question a later keystroke has overtaken is refused, not answered', async () => {
  const tier = await semanticTier(stackOf(matrix(10, 3)), tableOf(10));
  const ctl = new AbortController();
  ctl.abort();
  await assert.rejects(tier.search(QUERY, ctl.signal), { name: 'AbortError' });
});

test('a failed load gives a tier that answers every question with the failure, for the box\'s one-line notice', async () => {
  const tier = unavailableTier('vectors.i8.bin has the sha256 x, and its meta says y');
  assert.equal(tier.id, SEMANTIC_ID);
  assert.equal(tier.name, SEMANTIC_NAME);
  await assert.rejects(tier.search(QUERY, live()), /vectors\.i8\.bin has the sha256 x/);
});
