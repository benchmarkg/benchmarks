// site/test/fusion.determinism.test.mjs -- P6-S1-T05 (11 S4 "The pipeline", "Sizing"; 08 S5.7 "The fusion order",
// steps 3 and 4, S8.1). The cosine leg (src/islands/search/cosine.ts) and the fusion and rerank
// (src/islands/search/fusion.ts), loaded by Node as they are, stripping their types:
//
//   cd site && npm test -- fusion.determinism    # the verify: `npm test` runs every test/*.test.mjs, this file among
//                                                 # them (node --test reads the extra argument as one more file pattern,
//                                                 # which names no file, so it adds nothing and fails nothing)
//   cd site && node --test test/fusion.determinism.test.mjs
//
// Done when: "Identical inputs produce a byte-identical top-25 ordering across 100 runs and the test asserts k == 60."
// The runs go through the whole of 08 S5.7 over a seeded synthetic world of 600 rows: the facet filter
// (lib/query.ts filter), the real BM25 leg (islands/search/lexical.ts) over the survivors, the cosine leg over a
// 600 x 256 int8 matrix in the format tools/build/embed.py writes vectors.i8.bin and vectors.meta.json in, dequantised
// afresh in every run, then the fusion and the rerank. Every run but the first shuffles every input whose order carries
// no meaning -- both legs' entries, the soft facets' keys and values, with a soft value repeated -- and the top 25 of
// five queries must serialise to the same bytes each time. The world is built to hold the ties that make an ordering
// fragile: names repeated, so that BM25 scores rows equal; matrix rows repeated, so that cosine does; and so RRF scores
// that tie. The test asserts each occurs, and that the rerank's keys are what break them.
//
// Also held: K is 60, says why, and is lib/query.ts's RRF_K; the dequantisation is q x float32(scale) and is refused on
// any mismatch with its meta or the loaded facets.json; the loop's scores are the cosine, restricted to the survivors
// without rescoring; RRF's ranks come from the scores, ties sharing one, and its sum does not depend on the order of
// the lists; the cut and the rerank by eye on small rows; the comparators are total; neither module imports a library;
// and the 1,500 x 256 semantic re-rank is inside 08 S8.1's 30 ms budget.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { VECTORS_FORMAT, cosine, dot, loadMatrix } from '../src/islands/search/cosine.ts';
import {
  COMPLETENESS_FACETS, FUSED_TOP, K, RERANKED_TOP, byFused, byReranked, completeness, facetMatches, fuse, ranks, rrf,
} from '../src/islands/search/fusion.ts';
import { bm25 } from '../src/islands/search/lexical.ts';
import { add, members, wordsFor } from '../src/lib/facet-index.ts';
import { RRF_K, buildPipeline, filter, rrf as rrfByPosition } from '../src/lib/query.ts';

const SRC = new URL('../src/islands/search/', import.meta.url);
const DIMS = 256;       // tools/build/embed.py DIMS: potion-base-8M's hidden_dim (08 S5.5)

// ---- a seeded world -------------------------------------------------------------------------------------------

function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A copy of `xs` in a seeded random order (Fisher-Yates). */
function shuffled(xs, rnd) {
  const out = [...xs];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

const WORDS = ['agent', 'bench', 'code', 'math', 'proof', 'vision', 'robot', 'web', 'chem', 'protein', 'climate', 'legal'];
const DOMAINS = [['code', 'code/repo'], ['code', 'code/snippet'], ['maths', 'maths/olympiad'], ['science', 'science/chemistry']];
const VALUES = {
  capability: ['planning', 'tool-use', 'grounding', 'long-context'], evaluation_method: ['execution-tests', 'judge', 'exact-match'],
  subject: ['llm', 'agent', 'vlm'], data_properties: ['fully-open', 'gated', 'unknown'], lifecycle: ['active', 'saturated'],
  governance: ['academic', 'industry'], execution: ['laptop', 'execution.compute_tier:wet-lab'],
};

/** n facets.json rows (format 3's fields the pipeline reads), ids in byte order as facets.json has them. Names are two
 *  of twelve words, so many rows share one, and BM25 scores them equal. */
function worldRows(n, rnd) {
  const pick = (xs) => xs[Math.floor(rnd() * xs.length)];
  return Array.from({ length: n }, (_, i) => {
    const [domain, subdomain] = pick(DOMAINS);
    const facets = Object.fromEntries(Object.entries(VALUES).map(([f, vs]) => [f, vs.filter(() => rnd() < 0.3)]));
    return {
      id: `b${String(i).padStart(4, '0')}`, name: `${pick(WORDS)} ${pick(WORDS)}`, aliases: rnd() < 0.2 ? [`${pick(WORDS)}-${i % 5}`] : [],
      editions: [], domain, subdomain, facets, year: rnd() < 0.1 ? null : 2015 + Math.floor(rnd() * 11), headroom: null,
    };
  });
}

/** vectors.i8.bin and vectors.meta.json for `ids`, in tools/build/embed.py's format: unit rows, symmetric int8 with one
 *  float32 scale a row (max|v| / 127), row-major with no header. Every `repeat`-th row repeats the one before it,
 *  so that cosine scores rows equal. */
function vectorFiles(ids, dims, rnd, repeat = 0) {
  const rows = ids.length;
  const bin = new Int8Array(rows * dims);
  const scales = [];
  for (let i = 0; i < rows; i++) {
    if (repeat > 0 && i > 0 && i % repeat === 0) {
      bin.copyWithin(i * dims, (i - 1) * dims, i * dims);
      scales.push(scales[i - 1]);
      continue;
    }
    const v = Array.from({ length: dims }, () => rnd() - 0.5);
    const norm = Math.hypot(...v);
    const unit = v.map((x) => x / norm);
    const scale = Math.fround(Math.max(...unit.map(Math.abs)) / 127);
    unit.forEach((x, k) => { bin[i * dims + k] = Math.max(-127, Math.min(127, Math.round(x / scale))); });
    scales.push(scale);
  }
  const meta = { artifact: 'vectors', format: 1, rows, dims, ids: [...ids], scales, vectors: { bytes: bin.length, sha256: '' } };
  return { meta, bin: new Uint8Array(bin.buffer).slice() };         // the bytes as fetched: unsigned, a buffer of their own
}

const unitQuery = (rnd, dims) => Float32Array.from({ length: dims }, () => rnd() - 0.5);

// ---- the verify: K, and 100 runs -----------------------------------------------------------------------------

test('fusion.determinism: K is 60, the standard published default, and lib/query.ts\'s RRF_K; the top is 40, then 25', () => {
  assert.equal(K, 60);
  assert.equal(RRF_K, K, 'the Phase 2 pipeline and this fusion fuse at one k');
  assert.equal(FUSED_TOP, 40);
  assert.equal(RERANKED_TOP, 25);
  const source = readFileSync(new URL('fusion.ts', SRC), 'utf8');
  assert.match(source, /\/\*\*[^/]*standard published default[^/]*\*\/\s*export const K = 60;/, 'the constant says why it is 60');
});

const N = 600;
const QUERIES = [
  { text: 'agent bench', facets: {}, soft: { capability: ['planning', 'tool-use'] } },
  { text: 'protein chem', facets: { domain: ['science', 'maths'] }, soft: {} },
  { text: 'code', facets: { subject: ['llm', 'agent'] }, soft: { evaluation_method: ['judge'], domain: ['code'], subdomain: ['code/repo'] } },
  { text: 'qwxyz', facets: {}, soft: { governance: ['academic'] } },                    // the lexical leg finds nothing
  { text: 'robot web', facets: { capability: ['grounding'] }, soft: { subject: ['vlm'] }, semantic: false },   // the tier not engaged
];

function worldOf(seed) {
  const rnd = seeded(seed);
  const rows = worldRows(N, rnd);
  const files = vectorFiles(rows.map((r) => r.id), DIMS, rnd, 37);
  const vectors = QUERIES.map(() => unitQuery(rnd, DIMS));
  return { rows, files, vectors };
}

/** One run of the whole pipeline over `world`: built and dequantised afresh, its inputs shuffled by `rnd` unless null.
 *  Returns, per query, the fusion's output and the legs it read. */
function runOnce(world, rnd) {
  const { rows, files, vectors } = world;
  const p = buildPipeline(rows);
  const m = loadMatrix(files.meta, files.bin.slice().buffer, rows.map((r) => r.id));
  const mix = (xs) => (rnd == null ? xs : shuffled(xs, rnd));
  return QUERIES.map((q, i) => {
    const survivors = filter(p.facets, { facets: q.facets });
    const lexical = bm25(p.text, q.text, survivors);
    const semantic = q.semantic === false ? null : cosine(m, vectors[i], survivors);
    const soft = Object.fromEntries(mix(Object.entries(q.soft)).map(([f, vs]) => [f, mix(rnd == null ? vs : [...vs, ...vs.slice(0, 1)])]));
    const out = fuse({ lexical: mix(lexical), semantic: semantic && mix(semantic) }, rows, soft);
    return { ...out, lexical, semantic, survivors };
  });
}

test('fusion.determinism: the top 25 is byte-identical over 100 runs, with every input shuffled', () => {
  const world = worldOf(20261125);
  const rnd = seeded(7);
  const first = runOnce(world, null);
  const bytes = JSON.stringify(first.map((r) => r.top));
  for (let run = 1; run < 100; run++) {
    assert.equal(JSON.stringify(runOnce(world, rnd).map((r) => r.top)), bytes, `run ${run}`);
  }
  // the world holds what makes an ordering fragile, so the runs above exercised it
  first.forEach((r, i) => {
    assert.equal(r.fused.length, FUSED_TOP, QUERIES[i].text);
    assert.equal(r.top.length, RERANKED_TOP, QUERIES[i].text);
    assert.ok(r.top.every((c) => r.fused.includes(c)), 'the 25 come from the 40');
    assert.ok(r.top.every((c, j) => j === 0 || byReranked(r.top[j - 1], c) < 0), 'in the rerank order');
  });
  const tiedIn = (list) => list.some((x, j) => j > 0 && x.score === list[j - 1].score);
  assert.ok(first.some((r) => r.lexical.length > 1 && tiedIn(r.lexical)), 'BM25 scores rows equal');
  assert.ok(first.some((r) => r.semantic != null && tiedIn(r.semantic)), 'cosine scores rows equal');
  assert.ok(first.some((r) => tiedIn(r.fused)), 'RRF scores rows equal within the 40');
  // ...and within the 25, rows equal in facet matches and RRF score, which only recency, completeness or the row orders
  assert.ok(first.some((r) => r.top.some((c, j) => j > 0 && c.score === r.top[j - 1].score && c.facetMatches === r.top[j - 1].facetMatches)),
    'a tie in the 25 that the later keys break');
  assert.equal(first[3].lexical.length, 0, 'the semantic leg alone still answers');
  assert.equal(first[4].semantic, null, 'and the lexical leg alone');
  assert.ok(first[4].top.every((c) => c.semantic === null && c.lexical != null));
});

test('fusion.determinism: the comparators are total, so no sort algorithm or stability can change the order', () => {
  const runs = runOnce(worldOf(20261125), null);
  for (const { fused } of runs) {
    for (const cmp of [byFused, byReranked]) {
      for (const a of fused) {
        for (const b of fused) {
          const ab = cmp(a, b);
          if (a === b) assert.equal(ab, 0);
          else assert.ok(ab !== 0 && Math.sign(ab) === -Math.sign(cmp(b, a)), `${a.row} and ${b.row}`);
        }
      }
    }
  }
});

// ---- cosine.ts: the load ---------------------------------------------------------------------------------------

const META = (over = {}) => ({ artifact: 'vectors', format: 1, rows: 2, dims: 3, ids: ['a', 'b'], scales: [0.0078125, 0.1], vectors: { bytes: 6 }, ...over });

test('cosine.ts: dequantised once at load into a Float32Array, each coordinate q x float32(scale) as embed.py has it', () => {
  assert.equal(VECTORS_FORMAT, 1);
  const raw = [127, -64, 0, 1, -2, -127];
  const m = loadMatrix(META(), Int8Array.from(raw));
  assert.ok(m.data instanceof Float32Array && m.data.length === 6);
  const s = [Math.fround(0.0078125), Math.fround(0.1)];
  assert.deepEqual([...m.data], raw.map((q, j) => Math.fround(q * s[j < 3 ? 0 : 1])));
  assert.deepEqual([...m.data.subarray(0, 3)], [0.9921875, -0.5, 0], 'exact where the scale is a power of two');
  assert.equal(m.norms[0], Math.sqrt(0.9921875 ** 2 + 0.25));
  // the same bytes as fetched (unsigned) or as a bare buffer, and a view into a larger buffer, read alike
  const u8 = Uint8Array.from(raw.map((q) => q & 0xff));
  assert.deepEqual(loadMatrix(META(), u8.buffer).data, m.data);
  const wide = new Uint8Array(10);
  wide.set(u8, 3);
  assert.deepEqual(loadMatrix(META(), wide.subarray(3, 9)).data, m.data);
  // the rows are the facets.json rows, so the facets.json ids are checked when given
  assert.deepEqual(loadMatrix(META(), u8, ['a', 'b']).ids, ['a', 'b']);
});

test('cosine.ts: the load refuses a matrix that does not match its meta or the loaded facets.json', () => {
  const u8 = new Uint8Array(6).fill(1);
  assert.throws(() => loadMatrix(META({ artifact: 'facets' }), u8), /not vectors/);
  assert.throws(() => loadMatrix(META({ format: 2 }), u8), /format 2/);
  assert.throws(() => loadMatrix(META(), new Uint8Array(5)), /5 bytes/);
  assert.throws(() => loadMatrix(META({ vectors: { bytes: 7 } }), u8), /the meta says 7/);
  assert.throws(() => loadMatrix(META({ ids: ['a'] }), u8), /1 ids/);
  assert.throws(() => loadMatrix(META({ scales: [0.1] }), u8), /1 scales/);
  assert.throws(() => loadMatrix(META({ scales: [0.1, 0] }), u8), /row 1 \(b\) has the scale 0/);
  assert.throws(() => loadMatrix(META({ scales: [Number.NaN, 0.1] }), u8), /row 0/);
  assert.throws(() => loadMatrix(META(), u8, ['b', 'a']), /another facets\.json/);
  assert.throws(() => loadMatrix(META(), u8, ['a', 'b', 'c']), /another facets\.json/);
  assert.deepEqual(loadMatrix(META({ rows: 0, ids: [], scales: [], vectors: { bytes: 0 } }), new Uint8Array(0), []).data, new Float32Array(0),
    'no entry published yet: embed.py writes zero rows');
});

// ---- cosine.ts: the loop ---------------------------------------------------------------------------------------

test('cosine.ts: the hand-rolled loop gives the cosine of the dequantised rows, best first, ties by row', () => {
  const rnd = seeded(11);
  const ids = Array.from({ length: 300 }, (_, i) => `r${String(i).padStart(3, '0')}`);
  const { meta, bin } = vectorFiles(ids, DIMS, rnd, 10);
  const m = loadMatrix(meta, bin, ids);
  const q = unitQuery(rnd, DIMS);
  const list = cosine(m, q);
  assert.deepEqual(list.map((r) => r.row).sort((a, b) => a - b), ids.map((_, i) => i), 'every row without survivors');
  const signed = new Int8Array(bin.buffer);
  for (const { row, score } of list) {
    // brute force from the file's bytes, in doubles
    let d = 0;
    let rr = 0;
    let qq = 0;
    for (let k = 0; k < DIMS; k++) {
      const v = Math.fround(signed[row * DIMS + k] * Math.fround(meta.scales[row]));
      d += v * Math.fround(q[k]);
      rr += v * v;
      qq += Math.fround(q[k]) ** 2;
    }
    assert.ok(Math.abs(score - d / Math.sqrt(rr * qq)) < 1e-12, `row ${row}`);
    assert.ok(score >= -1 - 1e-12 && score <= 1 + 1e-12);
  }
  assert.ok(list.every((r, i) => i === 0 || list[i - 1].score > r.score || (list[i - 1].score === r.score && list[i - 1].row < r.row)));
  assert.ok(list.some((r, i) => i > 0 && list[i - 1].score === r.score), 'the repeated rows tie, and go by row');
  // a row against itself is first, at 1; and the loop is the plain sum, in order
  const self = cosine(m, m.data.subarray(5 * DIMS, 6 * DIMS));
  assert.equal(self[0].row, 5);
  assert.ok(Math.abs(self[0].score - 1) < 1e-12);
  assert.equal(dot(Float32Array.of(9, 1, 2, 3), 1, Float32Array.of(4, 5, 6), 3), 1 * 4 + 2 * 5 + 3 * 6);
});

test('cosine.ts: restricted to the survivors, whose scores do not move with the selection', () => {
  const rnd = seeded(12);
  const ids = Array.from({ length: 100 }, (_, i) => `r${String(i).padStart(3, '0')}`);
  const { meta, bin } = vectorFiles(ids, DIMS, rnd);
  const m = loadMatrix(meta, bin, ids);
  const q = unitQuery(rnd, DIMS);
  const all = new Map(cosine(m, q).map((r) => [r.row, r.score]));
  const survivors = new Uint32Array(wordsFor(100));
  for (let i = 0; i < 100; i += 3) add(survivors, i);
  const list = cosine(m, q, survivors);
  assert.deepEqual(list.map((r) => r.row).sort((a, b) => a - b), members(survivors), 'only the survivors are scored');
  for (const { row, score } of list) assert.equal(score, all.get(row), `row ${row}`);
  assert.deepEqual(cosine(m, q, new Uint32Array(wordsFor(100))), [], 'no survivor, no result');
  assert.deepEqual(cosine(m, new Float32Array(DIMS), survivors), [], 'a zero query has no direction, and no list');
  assert.throws(() => cosine(m, new Float32Array(384)), /384 dimensions and the matrix 256/);
  assert.throws(() => cosine(m, Float32Array.of(...q.subarray(1), Number.NaN)), /not finite/);
  assert.throws(() => cosine(m, q, new Uint32Array(5)), /5 words, over a matrix of 100 rows/);
  const stray = new Uint32Array(wordsFor(100));
  add(stray, 101);
  assert.throws(() => cosine(m, q, stray), /survivor 101 is past/);
});

// ---- fusion.ts: RRF ---------------------------------------------------------------------------------------------

test('fusion.ts: RRF sums 1 / (K + rank), ranks read from the scores, equal scores sharing one', () => {
  const a = [{ row: 7, score: 9 }, { row: 3, score: 5 }, { row: 1, score: 1 }];
  const b = [{ row: 3, score: 0.9 }, { row: 7, score: 0.2 }];
  assert.deepEqual(rrf([a, b]), [{ row: 3, score: 1 / 61 + 1 / 62 }, { row: 7, score: 1 / 61 + 1 / 62 }, { row: 1, score: 1 / 63 }]);
  assert.deepEqual(rrf([a, b]), rrfByPosition([a, b]), 'with no tied scores, lib/query.ts\'s positions are the same ranks');
  assert.deepEqual(rrf([[{ row: 2, score: 1 }, { row: 0, score: 3 }]], 0), [{ row: 0, score: 1 }, { row: 2, score: 1 / 2 }], 'k is a parameter');
  assert.deepEqual(rrf([]), []);
  assert.deepEqual(rrf([[], []]), []);
  // competition ranking: the rows a leg scores equal share the best rank, in any input order
  const tied = [{ row: 9, score: 1 }, { row: 5, score: 2 }, { row: 2, score: 2 }, { row: 4, score: 0.5 }];
  assert.deepEqual([...ranks(tied)].sort((x, y) => x[0] - y[0]), [[2, 1], [4, 4], [5, 1], [9, 3]]);
  for (const order of [[0, 1, 2, 3], [3, 2, 1, 0], [2, 0, 3, 1]]) {
    assert.deepEqual(rrf([order.map((i) => tied[i])]), rrf([tied]));
  }
  assert.equal(rrf([tied])[0].score, rrf([tied])[1].score, 'tied in the leg, tied in the fusion: the rerank breaks it');
  // a ranked list is a ranking: a row once, a finite score
  assert.throws(() => ranks([{ row: 1, score: 1 }, { row: 1, score: 2 }]), /row 1 twice/);
  assert.throws(() => ranks([{ row: 1, score: Number.NaN }]), /score NaN/);
  assert.throws(() => ranks([{ row: -1, score: 1 }]), /row -1/);
  assert.throws(() => ranks([{ row: 1.5, score: 1 }]), /row 1\.5/);
});

test('fusion.ts: a row\'s terms are summed in rank order, so the order of the lists cannot move its score', () => {
  // three ranks whose float sum depends on the order of addition, found rather than assumed
  let found = null;
  for (let r1 = 1; r1 < 60 && found == null; r1++) {
    for (let r2 = r1; r2 < 60 && found == null; r2++) {
      for (let r3 = r2; r3 < 60 && found == null; r3++) {
        const t = [r1, r2, r3].map((r) => 1 / (K + r));
        if ((t[0] + t[1]) + t[2] !== (t[2] + t[1]) + t[0]) found = [r1, r2, r3];
      }
    }
  }
  assert.ok(found != null, 'float addition is not associative here');
  const lists = found.map((r) => Array.from({ length: r }, (_, i) => ({ row: i === r - 1 ? 0 : 100 + i, score: r - i })));
  const scores = [[0, 1, 2], [2, 1, 0], [1, 2, 0], [2, 0, 1]].map((o) => rrf(o.map((i) => lists[i])).find((x) => x.row === 0).score);
  assert.ok(scores.every((s) => s === scores[0]), `${found}: ${scores}`);
});

// ---- fusion.ts: the cut and the rerank, by eye ---------------------------------------------------------------

const ALL7 = Object.fromEntries(COMPLETENESS_FACETS.map((f) => [f, ['x']]));
const r = (year, facets = {}, over = {}) => ({ domain: 'code', subdomain: 'code/repo', year, facets, ...over });

test('fusion.ts: the facet-match count, then relevance, then recency, then curation completeness, then the row', () => {
  assert.deepEqual([...COMPLETENESS_FACETS], ['capability', 'evaluation_method', 'subject', 'data_properties', 'lifecycle', 'governance', 'execution']);
  const rows = [
    r(2020, ALL7),
    r(2024, { capability: ['tool-use'], subject: ['llm'], lifecycle: ['active'] }),
    r(null, ALL7),
    r(2024, { ...ALL7, capability: ['planning'] }),
    r(2022),
  ];
  // lexical ranks 0:1 1:2 2:2 3:4; semantic ranks 1:1 0:2 3:3 2:4 4:5 -- rows 0 and 1 tie at 1/61 + 1/62
  const legs = {
    lexical: [{ row: 0, score: 10 }, { row: 1, score: 5 }, { row: 2, score: 5 }, { row: 3, score: 1 }],
    semantic: [{ row: 1, score: 0.9 }, { row: 0, score: 0.8 }, { row: 3, score: 0.7 }, { row: 2, score: 0.1 }, { row: 4, score: 0.05 }],
  };
  const { fused, top } = fuse(legs, rows);
  assert.deepEqual(fused.map((c) => c.row), [1, 0, 2, 3, 4], 'RRF, the 0-1 tie to the newer');
  assert.deepEqual(top.map((c) => c.row), [1, 0, 2, 3, 4]);
  assert.deepEqual(top[0], { row: 1, score: 1 / 61 + 1 / 62, lexical: 2, semantic: 1, facetMatches: 0, year: 2024, completeness: 3 });
  assert.deepEqual(top[4], { row: 4, score: 1 / 65, lexical: null, semantic: 5, facetMatches: 0, year: 2022, completeness: 0 });
  // a soft facet lifts the row carrying it over every row that carries fewer
  assert.deepEqual(fuse(legs, rows, { capability: ['planning'] }).top.map((c) => c.row), [3, 1, 0, 2, 4]);
  // recency, a missing year last, then completeness, then the row: four rows a leg scores equal
  const flat = [r(2023, { capability: ['a'], subject: ['b'] }), r(2023, ALL7), r(null, ALL7), r(2023, ALL7), r(2019, ALL7)];
  const equal = { lexical: [0, 1, 2, 3, 4].map((row) => ({ row, score: 1 })), semantic: null };
  assert.deepEqual(fuse(equal, flat).top.map((c) => c.row), [1, 3, 0, 4, 2]);
  // relevance above recency: the newest row does not pass a better-ranked old one
  assert.deepEqual(fuse({ lexical: [{ row: 4, score: 2 }, { row: 1, score: 1 }], semantic: null }, flat).top.map((c) => c.row), [4, 1]);
  assert.deepEqual(fuse({ lexical: null, semantic: null }, flat), { fused: [], top: [] });
  assert.throws(() => fuse({ lexical: [{ row: 5, score: 1 }], semantic: null }, flat), /row 5, and there are 5 rows/);
});

test('fusion.ts: a tie at the cut of 40 goes by the rerank\'s signals, and only then by row', () => {
  // 45 rows a leg scores equal: the cut keeps the 40 newest, unless a soft facet keeps an old one
  const rows = Array.from({ length: 45 }, (_, i) => r(1980 + i, i === 0 ? { capability: ['planning'] } : {}));
  const legs = { lexical: rows.map((_, row) => ({ row, score: 1 })), semantic: null };
  const plain = fuse(legs, rows);
  assert.deepEqual(plain.fused.map((c) => c.row), Array.from({ length: 40 }, (_, i) => 44 - i));
  assert.deepEqual(plain.top.map((c) => c.row), Array.from({ length: 25 }, (_, i) => 44 - i));
  const soft = fuse(legs, rows, { capability: ['planning'] });
  assert.deepEqual(soft.fused.map((c) => c.row), [0, ...Array.from({ length: 39 }, (_, i) => 44 - i)]);
  assert.deepEqual(soft.top.map((c) => c.row), [0, ...Array.from({ length: 24 }, (_, i) => 44 - i)]);
  // equal in everything but the row: the row decides, and no input order does
  const same = Array.from({ length: 45 }, () => r(2024, ALL7));
  const rev = { lexical: [...legs.lexical].reverse(), semantic: null };
  assert.deepEqual(fuse(rev, same).fused.map((c) => c.row), Array.from({ length: 40 }, (_, i) => i));
});

test('fusion.ts: facet matches count distinct soft values carried; completeness counts the seven arrays populated', () => {
  const row = r(2024, { capability: ['planning', 'tool-use'], subject: [], governance: ['academic'], extra: ['x'] }, { subdomain: 'code/repo' });
  assert.equal(facetMatches(row, {}), 0);
  assert.equal(facetMatches(row, { capability: ['planning', 'planning', 'tool-use', 'proof'] }), 2, 'a repeated value counts once');
  assert.equal(facetMatches(row, { domain: ['code'], subdomain: ['code/repo', 'code/snippet'] }), 2, 'the scalars');
  assert.equal(facetMatches(row, { nonesuch: ['planning'], subject: ['llm'] }), 0, 'a facet the row has no value of');
  assert.equal(completeness(row), 2, 'capability and governance; an empty array and an eighth name do not count');
  assert.equal(completeness(r(2024, ALL7)), 7);
  assert.equal(completeness({ domain: 'code', subdomain: 'code/repo', year: null }), 0);
});

// ---- no library ----------------------------------------------------------------------------------------------

test('fusion.determinism: no vector library -- the loop and the fusion import only the site\'s own modules', () => {
  for (const f of ['cosine.ts', 'fusion.ts']) {
    const source = readFileSync(new URL(f, SRC), 'utf8');
    const from = [...source.matchAll(/^import[^;]*?from\s+'([^']+)'/gm)].map((x) => x[1]);
    assert.ok(from.length > 0 && from.every((s) => s.startsWith('./') || s.startsWith('../')), `${f}: ${from}`);
  }
});

// ---- 08 S8.1's budget ------------------------------------------------------------------------------------------

// The semantic re-rank after the vectors are resident -- the cosine pass over 1,500 x 256, the fusion and the rerank --
// is budgeted at < 30 ms (08 S8.1), against 0.61 ms measured for the loop (11 S4). Wall-clock time on whatever machine
// runs the test, so the assertion is on the median of REPS runs after WARMUP, as test/perf/facet-filter.bench.mjs does,
// with a margin of more than an order of magnitude: a failure means an algorithmic regression, not noise.
test('fusion.determinism: the 1,500 x 256 semantic re-rank is inside 08 S8.1\'s 30 ms', (t) => {
  const rnd = seeded(15);
  const rows = worldRows(1500, rnd);
  const ids = rows.map((x) => x.id);
  const { meta, bin } = vectorFiles(ids, DIMS, rnd);
  const p = buildPipeline(rows);
  const m = loadMatrix(meta, bin, ids);
  const q = unitQuery(rnd, DIMS);
  const lexical = bm25(p.text, 'agent bench');
  const once = () => fuse({ lexical, semantic: cosine(m, q, p.facets.all) }, rows, { capability: ['planning'] });
  for (let i = 0; i < 10; i++) once();
  const times = [];
  for (let i = 0; i < 31; i++) {
    const t0 = performance.now();
    once();
    times.push(performance.now() - t0);
  }
  const median = times.sort((a, b) => a - b)[15];
  t.diagnostic(`median ${median.toFixed(3)} ms over 31 runs at 1,500 x ${DIMS}`);
  assert.ok(median < 30, `${median} ms`);
});
