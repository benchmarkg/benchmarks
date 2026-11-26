// site/test/semantic-loader.test.mjs -- P6-S1-T06 (11 S4 "First-query latency"). The semantic tier's loader,
// src/islands/search/loader.ts, loaded by Node as it is (its types stripped), over the files in public/embed/, with a
// fetch that serves them, an in-memory store that copies what it is given as IndexedDB does (structuredClone), and
// idle callbacks that are always out of time, so every yield the load can make, it makes:
//
//   cd site && node --test test/semantic-loader.test.mjs
//
// The ledger's verify is the browser spec, tests/semantic-loading.spec.ts, which holds the same three conditions against
// the real page, IndexedDB and network. This file holds what that spec cannot reach in the draft preview, which ships
// no document vectors: the vectors' leg, with a synthetic vectors.meta.json and vectors.i8.bin in tools/build/embed.py's
// format. Also held: same commit, no fetch; another commit, every file again and the record replaced; every file's
// length and sha256 checked before anything is used or cached; a record that is not a valid stack, or a store that
// fails, is no cache rather than an error; no key but a commit SHA; the sliced dequantisation equal to one call and
// yielding between slices; nothing fetched before first paint, `after` and an idle callback; and that the module
// imports nothing at load but types.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { QueryEncoder, dequantise } from '../src/islands/search/encoder.ts';
import { loadMatrix } from '../src/islands/search/cosine.ts';
import {
  CACHE_FORMAT, EMBED_URL, ENCODER_META, SLICE_ROWS, VECTORS_BIN, VECTORS_META, cachedRecord, dequantiseSliced, loadStack,
  semanticStack, startSemanticTier,
} from '../src/islands/search/loader.ts';

const EMBED = new URL('../public/embed/', import.meta.url);
const FILES = Object.fromEntries(['potion-8m-pruned.meta.json', 'tokenizer.json', 'potion-8m-pruned.i8.bin', 'potion-8m-pruned.r2.bin']
  .map((f) => [f, new Uint8Array(readFileSync(new URL(f, EMBED)))]));
const META = JSON.parse(new TextDecoder().decode(FILES[ENCODER_META]));
const TOKENIZER = JSON.parse(new TextDecoder().decode(FILES['tokenizer.json']));
const REFERENCE = new QueryEncoder(TOKENIZER, META, dequantise(META, FILES['potion-8m-pruned.i8.bin'], FILES['potion-8m-pruned.r2.bin']));
const QUERY = 'find me benchmarks about protein folding';

const A = 'a'.repeat(40);
const B = '0123456789abcdef0123456789abcdef01234567';
const sha256 = async (b) => createHash('sha256').update(b).digest('hex');

/** vectors.meta.json and vectors.i8.bin as tools/build/embed.py writes them: `rows` x 256 int8, one scale a row. */
function vectorsPair(rows = 5) {
  const dims = 256;
  const bin = new Uint8Array(rows * dims);
  for (let k = 0; k < bin.length; k++) bin[k] = ((k * 37 + 11) % 255) - 127 & 0xff;
  const meta = {
    artifact: 'vectors', format: 1, rows, dims, ids: Array.from({ length: rows }, (_, i) => `bench-${i}`),
    scales: Array.from({ length: rows }, (_, i) => 0.002 + i / 10000),
    vectors: { file: VECTORS_BIN, dtype: 'int8', layout: 'row-major', bytes: bin.length, sha256: createHash('sha256').update(bin).digest('hex') },
  };
  return { [VECTORS_META]: new TextEncoder().encode(JSON.stringify(meta)), [VECTORS_BIN]: bin, meta };
}

/** A host: a fetch over `files` (every request recorded; a name it lacks is a 404), a store that copies as IndexedDB
 *  does, idle callbacks always out of time, and node's sha256. `edit` rewrites a file's bytes as served. */
function host(files = FILES, { store = memoryStore(), edit = {}, status = {} } = {}) {
  const fetched = [];
  let idles = 0;
  return {
    fetched,
    get idles() { return idles; },
    store,
    deps: {
      fetch: async (url, init) => {
        assert.equal(init?.cache, 'no-cache', 'every file revalidates with the server');
        assert.ok(url.startsWith(EMBED_URL), url);
        const name = url.slice(EMBED_URL.length);
        fetched.push(name);
        if (status[name] != null) return new Response('', { status: status[name] });
        if (!(name in files)) return new Response('', { status: 404 });
        return new Response((edit[name] ?? ((b) => b))(files[name].slice()));
      },
      store,
      idle: async () => {
        idles++;
        return { timeRemaining: () => 0 };
      },
      sha256,
    },
  };
}

function memoryStore() {
  const records = new Map();
  return {
    records,
    get: async (commit) => structuredClone(records.get(commit)),
    put: async (record) => {
      records.clear();
      records.set(record.commit, structuredClone(record));
    },
  };
}

const ENCODER_FILES = [ENCODER_META, 'tokenizer.json', 'potion-8m-pruned.i8.bin', 'potion-8m-pruned.r2.bin'];
const sorted = (a) => [...a].sort();

test('a first load fetches the encoder files, checks them, and caches the dequantised stack under the commit', async () => {
  const h = host();
  const s = await loadStack({ commit: A, vectors: false }, h.deps);
  assert.equal(s.source, 'network');
  assert.equal(s.commit, A);
  assert.equal(s.vectors, null, 'a build that ships no vectors has none');
  assert.deepEqual(sorted(h.fetched), sorted(ENCODER_FILES));
  assert.deepEqual([...h.store.records.keys()], [A]);
  const rec = h.store.records.get(A);
  assert.equal(rec.format, CACHE_FORMAT);
  assert.equal(rec.tokenizer, new TextDecoder().decode(FILES['tokenizer.json']));
  assert.ok(rec.encoder.matrix instanceof Float32Array);
  assert.deepEqual(rec.encoder.matrix, dequantise(META, FILES['potion-8m-pruned.i8.bin'], FILES['potion-8m-pruned.r2.bin']),
    'the cached matrix is the dequantised one, bit for bit');
  assert.deepEqual(s.encoder.encode(QUERY), REFERENCE.encode(QUERY));
});

test('a second load at the same commit fetches nothing, and encodes as the first did', async () => {
  const h = host();
  await loadStack({ commit: A, vectors: false }, h.deps);
  h.fetched.length = 0;
  const s = await loadStack({ commit: A, vectors: false }, h.deps);
  assert.equal(s.source, 'cache');
  assert.deepEqual(h.fetched, [], 'zero files, so zero matrix bytes');
  assert.deepEqual(s.encoder.encode(QUERY), REFERENCE.encode(QUERY));
});

test('a load at another commit fetches every file again and replaces the record', async () => {
  const h = host();
  await loadStack({ commit: A, vectors: false }, h.deps);
  h.fetched.length = 0;
  const s = await loadStack({ commit: B, vectors: false }, h.deps);
  assert.equal(s.source, 'network');
  assert.deepEqual(sorted(h.fetched), sorted(ENCODER_FILES));
  assert.deepEqual([...h.store.records.keys()], [B], 'one build in the store, never two');
  h.fetched.length = 0;
  assert.equal((await loadStack({ commit: A, vectors: false }, h.deps)).source, 'network', 'the old commit was evicted');
  assert.equal(h.fetched.length, ENCODER_FILES.length);
});

test('the document vectors are fetched, checked, dequantised with their norms and cached beside the encoder', async () => {
  const pair = vectorsPair();
  const files = { ...FILES, ...pair };
  const h = host(files);
  const s = await loadStack({ commit: A, vectors: true }, h.deps);
  assert.deepEqual(sorted(h.fetched), sorted([...ENCODER_FILES, VECTORS_META, VECTORS_BIN]));
  const want = loadMatrix(pair.meta, pair[VECTORS_BIN]);
  assert.deepEqual(s.vectors, want);
  h.fetched.length = 0;
  const again = await loadStack({ commit: A, vectors: true }, h.deps);
  assert.equal(again.source, 'cache');
  assert.deepEqual(h.fetched, []);
  assert.deepEqual(again.vectors, want);
  // a record without vectors does not serve a build that ships them, nor the other way round
  const without = host(files);
  await loadStack({ commit: A, vectors: false }, without.deps);
  without.fetched.length = 0;
  assert.equal((await loadStack({ commit: A, vectors: true }, without.deps)).source, 'network');
  assert.equal(cachedRecord(without.store.records.get(A), { commit: A, vectors: false }), null);
});

test('a file that fails its check is refused, and nothing is cached', async () => {
  const flip = (b) => { b[1000] ^= 1; return b; };
  const cases = [
    [{ edit: { 'potion-8m-pruned.i8.bin': flip } }, /potion-8m-pruned\.i8\.bin has the sha256 [0-9a-f]{64}, and its meta says/],
    [{ edit: { 'potion-8m-pruned.r2.bin': (b) => b.subarray(1) } }, /potion-8m-pruned\.r2\.bin is 949375 bytes, and its meta says 949376/],
    [{ edit: { 'tokenizer.json': flip } }, /tokenizer\.json has the sha256/],
    [{ status: { 'potion-8m-pruned.i8.bin': 500 } }, /potion-8m-pruned\.i8\.bin: HTTP 500/],
    [{ status: { [ENCODER_META]: 404 } }, /potion-8m-pruned\.meta\.json: HTTP 404/],
  ];
  for (const [opts, message] of cases) {
    const h = host(FILES, opts);
    await assert.rejects(loadStack({ commit: A, vectors: false }, h.deps), message);
    assert.equal(h.store.records.size, 0, String(message));
  }
  const pair = vectorsPair();
  const h = host({ ...FILES, ...pair }, { edit: { [VECTORS_BIN]: flip } });
  await assert.rejects(loadStack({ commit: A, vectors: true }, h.deps), /vectors\.i8\.bin has the sha256/);
  assert.equal(h.store.records.size, 0);
  const missing = host(FILES);
  await assert.rejects(loadStack({ commit: A, vectors: true }, missing.deps), /vectors\.meta\.json: HTTP 404/);
  // another artifact where the encoder meta should be
  const other = host({ ...FILES, [ENCODER_META]: new TextEncoder().encode(JSON.stringify({ ...META, artifact: 'vectors' })) });
  await assert.rejects(loadStack({ commit: A, vectors: false }, other.deps), /not a query-encoder meta of format 1/);
  assert.deepEqual(other.fetched, [ENCODER_META], 'refused before a matrix byte is fetched');
});

test('a record that is not a valid stack is a miss: fetched again and replaced', async () => {
  const h = host();
  await loadStack({ commit: A, vectors: false }, h.deps);
  const good = h.store.records.get(A);
  const config = { commit: A, vectors: false };
  assert.equal(cachedRecord(good, config), good);
  const bad = [
    null, 'a string', {}, { ...good, format: CACHE_FORMAT + 1 }, { ...good, commit: B }, { ...good, tokenizer: 7 },
    { ...good, encoder: { ...good.encoder, matrix: good.encoder.matrix.subarray(1) } },
    { ...good, encoder: { ...good.encoder, matrix: Array.from(good.encoder.matrix.subarray(0, 4)) } },
    { ...good, vectors: undefined },
  ];
  bad.forEach((r, i) => assert.equal(cachedRecord(r, config), null, `bad record ${i}`));
  // a record whose tokenizer is not JSON gets past the shape check, fails to build, and is replaced
  h.store.records.set(A, { ...good, tokenizer: '{not json' });
  h.fetched.length = 0;
  const s = await loadStack(config, h.deps);
  assert.equal(s.source, 'network');
  assert.equal(h.fetched.length, ENCODER_FILES.length);
  assert.equal(h.store.records.get(A).tokenizer, good.tokenizer);
});

test('a store that fails is no cache: the stack is fetched and served', async () => {
  const store = { get: async () => { throw new Error('quota'); }, put: async () => { throw new Error('quota'); } };
  const h = host(FILES, { store });
  const s = await loadStack({ commit: A, vectors: false }, h.deps);
  assert.equal(s.source, 'network');
  assert.deepEqual(s.encoder.encode(QUERY), REFERENCE.encode(QUERY));
  const none = host(FILES, { store: null });
  assert.equal((await loadStack({ commit: A, vectors: false }, none.deps)).source, 'network');
});

test('the cache key is the index commit SHA and nothing else', async () => {
  for (const commit of ['', 'HEAD', 'abc1234', 'A'.repeat(40), `${A} `]) {
    const h = host();
    await assert.rejects(loadStack({ commit, vectors: false }, h.deps), /no index commit to key the cache on/);
    assert.deepEqual(h.fetched, []);
    assert.equal(h.store.records.size, 0);
  }
});

test('the matrix is dequantised in slices, yielding between them, to the same values as one call', async () => {
  let idles = 0;
  const idle = async () => { idles++; return { timeRemaining: () => 0 }; };
  const i8 = FILES['potion-8m-pruned.i8.bin'];
  const r2 = FILES['potion-8m-pruned.r2.bin'];
  const sliced = await dequantiseSliced(dequantise, META, i8, r2, idle);
  assert.deepEqual(sliced, dequantise(META, i8, r2));
  assert.equal(idles, Math.ceil(META.rows / SLICE_ROWS), 'one idle callback to start, and one after every slice but the last');
  // with time to spare it does not yield at all after the first
  let spare = 0;
  await dequantiseSliced(dequantise, META, i8, null, async () => { spare++; return { timeRemaining: () => 50 }; });
  assert.equal(spare, 1);
  // a plane of the wrong size is refused by dequantise itself
  await assert.rejects(dequantiseSliced(dequantise, META, i8.subarray(1), r2, idle), /the int8 plane is/);
});

test('nothing is fetched before a painted frame, Pagefind and an idle callback, and the tier starts once a page', async () => {
  const frames = [];
  globalThis.requestAnimationFrame = (f) => frames.push(f);
  let ready;
  const after = new Promise((r) => { ready = r; });
  let idle;
  const h = host();
  const deps = { ...h.deps, idle: () => new Promise((r) => { idle = () => r({ timeRemaining: () => 50 }); }) };
  const states = [];
  assert.equal(semanticStack(), null);
  const tier = startSemanticTier({ commit: A, vectors: false }, after, (s) => states.push(s), deps);
  assert.equal(semanticStack(), tier);
  assert.equal(startSemanticTier({ commit: B, vectors: false }, after, () => undefined, deps), tier, 'once a page');
  const tick = () => new Promise((r) => setTimeout(r, 5));
  await tick();
  assert.deepEqual(states, ['waiting']);
  assert.equal(frames.length, 1, 'it asked for a frame');
  ready();                                     // Pagefind is interactive, but no frame has been painted
  await tick();
  assert.equal(idle, undefined);
  frames[0]();                                 // the frame is painted
  await tick();
  assert.equal(typeof idle, 'function', 'it waits for an idle callback');
  assert.deepEqual(h.fetched, []);
  assert.deepEqual(states, ['waiting']);
  // from here every idle callback is answered at once
  deps.idle = async () => ({ timeRemaining: () => 50 });
  idle();
  const s = await tier;
  assert.equal(s.source, 'network');
  await tick();
  assert.deepEqual(states, ['waiting', 'loading', 'ready']);
  delete globalThis.requestAnimationFrame;
});

test('the loader imports nothing at load but types, so the encoder is no part of the page it is on', () => {
  const src = readFileSync(new URL('../src/islands/search/loader.ts', import.meta.url), 'utf8');
  const imports = src.split('\n').filter((l) => /^import\b/.test(l));
  assert.ok(imports.length > 0);
  for (const l of imports) assert.match(l, /^import type /, l);
  assert.match(src, /await import\('\.\/encoder\.ts'\)/);
  assert.match(src, /await import\('\.\/cosine\.ts'\)/);
});
