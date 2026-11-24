// site/test/query.test.mjs -- P2-S4-T02 (08 S5.7, S8.1; 10 V11). The facet index (src/lib/facet-index.ts) and the
// query pipeline (src/lib/query.ts), loaded by Node as they are, stripping their types:
//
//   cd site && node --test test/query.test.mjs test/perf/facet-filter.bench.mjs
//
// The bitsets hold exactly the rows that carry each facets.json value, with no stray bit past the last row. The filter
// is AND across facets and OR within one, a facet with no selection is no constraint and a selection nobody carries
// admits nothing; ranges are inclusive, by two binary searches, with null outside every range. The faceted counts'
// sets leave each facet's own selection out. Every rule is checked by eye on a small fixture, then against a
// brute-force predicate over a seeded random corpus. RRF is 1 / (60 + rank) summed; the pipeline ranks only survivors,
// through the BM25 leg (src/islands/search/lexical.ts, whose own tests and frozen fixture are test/lexical.bm25.test.mjs);
// the semantic leg is absent, and says so. The latency budgets are test/perf/facet-filter.bench.mjs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  RANGES, add, buildFacetIndex, constrain, count, countBoth, fullSet, has, intersect, members, rangeColumn, union,
  valueSet, within, wordsFor,
} from '../src/lib/facet-index.ts';
import { RRF_K, buildPipeline, filter, rrf, run } from '../src/lib/query.ts';
import { bm25 } from '../src/islands/search/lexical.ts';

// ---- a small world, so every set can be checked by eye ---------------------------------------------------------

const row = (id, name, over = {}) => ({
  id, slug: id, name, aliases: [], domain: 'code', subdomain: 'code/repo', year: 2024, lifecycle: 'active',
  verification_max: null, condition_completeness_max: null, claim_count: 0, headroom: null,
  ...over,
  facets: { capability: [], evaluation_method: [], subject: ['llm'], data_properties: [], lifecycle: ['active'],
    governance: [], execution: [], ...(over.facets ?? {}) },
});

// rows 0..4, in this order
const ROWS = [
  row('swe-bench', 'SWE-bench', { aliases: ['SWE-bench Full'], headroom: 0.8,
    facets: { capability: ['planning', 'tool-use'], evaluation_method: ['execution-tests'], execution: ['execution.compute_tier:wet-lab'] } }),
  row('humaneval', 'HumanEval', { subdomain: 'code/snippet', year: 2021, headroom: 0.1,
    facets: { capability: ['tool-use'], evaluation_method: ['execution-tests'], execution: ['laptop', 'execution.reproducibility_blockers:wet-lab'] } }),
  row('mt-bench', 'MT-Bench', { year: null, aliases: ['MTBench'], facets: { capability: ['planning'], evaluation_method: ['judge'] } }),
  row('imo', 'IMO', { domain: 'maths', subdomain: 'maths/olympiad', year: 2025, headroom: 0.5,
    facets: { capability: ['proof', 'planning'], evaluation_method: ['judge'] } }),
  row('swe-lancer', 'SWE-Lancer', { year: 2025, headroom: 0.8, facets: { capability: ['tool-use'], evaluation_method: ['judge', 'execution-tests'] } }),
];

const ids = (set) => members(set).map((i) => ROWS[i].id);

test('a set over n rows has ceil(n / 32) words and no bit past the last row', () => {
  for (const n of [0, 1, 31, 32, 33, 64, 1500, 5000]) {
    const s = fullSet(n);
    assert.equal(s.length, wordsFor(n), `n=${n}`);
    assert.equal(count(s), n, `n=${n}`);
    assert.deepEqual(members(s), Array.from({ length: n }, (_, i) => i), `n=${n}`);
  }
  assert.equal(wordsFor(1500), 47, '188 bytes at 1,500 rows, 08 S5.7');
  // bit 31 is the sign bit of an int32: add, has, count and members must all treat it as an ordinary bit
  const s = new Uint32Array(2);
  for (const i of [0, 31, 32, 63]) add(s, i);
  assert.deepEqual(members(s), [0, 31, 32, 63]);
  assert.ok(has(s, 31) && has(s, 63) && !has(s, 30));
  assert.equal(count(s), 4);
  assert.equal(count(Uint32Array.of(0xffffffff, 0x80000001)), 34);
  assert.equal(countBoth(Uint32Array.of(0xffffffff, 0x80000001), Uint32Array.of(0x0000ffff, 0x80000000)), 17);
});

test('one bitset per facets.json value, holding exactly the rows that carry it, under the value as it is spelt', () => {
  const index = buildFacetIndex(ROWS);
  assert.equal(index.size, 5);
  assert.deepEqual(ids(valueSet(index, 'capability', 'planning')), ['swe-bench', 'mt-bench', 'imo']);
  assert.deepEqual(ids(valueSet(index, 'domain', 'code')), ['swe-bench', 'humaneval', 'mt-bench', 'swe-lancer']);
  assert.deepEqual(ids(valueSet(index, 'subdomain', 'code/snippet')), ['humaneval']);
  // a qualified spelling is its own value: the index does not interpret it
  assert.deepEqual(ids(valueSet(index, 'execution', 'execution.compute_tier:wet-lab')), ['swe-bench']);
  assert.equal(valueSet(index, 'execution', 'wet-lab'), undefined);
  assert.equal(valueSet(index, 'capability', 'unmeasured'), undefined);
  // every value of every row is indexed, and no other bit is set
  for (const [facet, byValue] of index.values) {
    for (const [value, set] of byValue) {
      const want = ROWS.flatMap((r, i) => ((facet === 'domain' || facet === 'subdomain' ? [r[facet]] : r.facets[facet] ?? []).includes(value) ? [i] : []));
      assert.deepEqual(members(set), want, `${facet}:${value}`);
    }
  }
  assert.throws(() => buildFacetIndex([row('x', 'X', { facets: { domain: ['code'] } })]), /a facets array is named domain/);
  assert.deepEqual(RANGES, ['year', 'headroom']);
});

test('AND across facets, OR within one; no selection is no constraint, a selection nobody carries admits nothing', () => {
  const index = buildFacetIndex(ROWS);
  assert.deepEqual(ids(filter(index, {})), ROWS.map((r) => r.id));
  assert.deepEqual(ids(filter(index, { facets: { capability: ['planning'] } })), ['swe-bench', 'mt-bench', 'imo']);
  assert.deepEqual(ids(filter(index, { facets: { capability: ['proof', 'tool-use'] } })), ['swe-bench', 'humaneval', 'imo', 'swe-lancer']);
  assert.deepEqual(ids(filter(index, { facets: { capability: ['planning'], evaluation_method: ['judge'] } })), ['mt-bench', 'imo']);
  assert.deepEqual(ids(filter(index, { facets: { capability: ['planning', 'tool-use'], evaluation_method: ['judge'], domain: ['code'] } })),
    ['mt-bench', 'swe-lancer']);
  assert.deepEqual(ids(filter(index, { facets: { capability: [] } })), ROWS.map((r) => r.id), 'an empty list is no constraint');
  assert.deepEqual(ids(filter(index, { facets: { capability: ['unmeasured'] } })), [], 'a value nobody carries');
  assert.deepEqual(ids(filter(index, { facets: { capability: ['unmeasured', 'proof'] } })), ['imo'], 'adds nothing to an OR');
  assert.deepEqual(ids(filter(index, { facets: { no_such_facet: ['x'] } })), [], 'a facet the index never saw');
  assert.deepEqual(ids(filter(index, { facets: { execution: ['wet-lab'] } })), [], 'the bare id is not the qualified value');
});

test('ranges are inclusive, by two binary searches, and a row with no value is outside every range', () => {
  const index = buildFacetIndex(ROWS);
  assert.deepEqual([...index.ranges.year.values], [2021, 2024, 2025, 2025]);
  assert.deepEqual([...index.ranges.year.rows], [1, 0, 3, 4], 'position -> row, ties by row');
  assert.deepEqual(ids(filter(index, { ranges: { year: [2021, 2024] } })), ['swe-bench', 'humaneval']);
  assert.deepEqual(ids(filter(index, { ranges: { year: [2025, 2025] } })), ['imo', 'swe-lancer']);
  assert.deepEqual(ids(filter(index, { ranges: { year: [1900, 2100] } })), ['swe-bench', 'humaneval', 'imo', 'swe-lancer'], 'MT-Bench has no year');
  assert.deepEqual(ids(filter(index, { ranges: { year: [2022, 2023] } })), [], 'between two values');
  assert.deepEqual(ids(filter(index, { ranges: { year: [2025, 2021] } })), [], 'lo > hi');
  assert.deepEqual(ids(filter(index, { ranges: { year: [Number.NaN, 2030] } })), []);
  // 0.8 has no exact float32: the bound is rounded as the stored value was, so 0.8 admits 0.8 at either end
  assert.deepEqual(ids(filter(index, { ranges: { headroom: [0.0, 0.8] } })), ['swe-bench', 'humaneval', 'imo', 'swe-lancer']);
  assert.deepEqual(ids(filter(index, { ranges: { headroom: [0.8, 1.0] } })), ['swe-bench', 'swe-lancer']);
  assert.deepEqual(ids(filter(index, { ranges: { headroom: [0.11, 0.79] } })), ['imo']);
  assert.deepEqual(ids(filter(index, { ranges: { headroom: [0.0, 1.0], year: [2025, 2025] }, facets: { evaluation_method: ['judge'] } })),
    ['imo', 'swe-lancer']);
  assert.throws(() => filter(index, { ranges: { claim_count: [0, 1] } }), /no range facet claim_count: the index holds year, headroom/);
  // a column of an empty corpus, and of all nulls
  assert.equal(count(within(rangeColumn([]), 0, 0, 1)), 0);
  assert.equal(count(within(rangeColumn([null, undefined, Number.NaN]), 1, -1e9, 1e9)), 0);
});

test('each facet counts within the other facets\' selections, and a facet with none counts within the result set', () => {
  const index = buildFacetIndex(ROWS);
  const cap = union(index.words, ['planning'].map((v) => valueSet(index, 'capability', v)));
  const em = union(index.words, ['judge'].map((v) => valueSet(index, 'evaluation_method', v)));
  const { all, others } = constrain(index.all, [cap, em, null]);
  assert.deepEqual(ids(all), ['mt-bench', 'imo']);
  assert.deepEqual(ids(others[0]), ['mt-bench', 'imo', 'swe-lancer'], 'capability counts keep judge, not planning');
  assert.deepEqual(ids(others[1]), ['swe-bench', 'mt-bench', 'imo'], 'evaluation-method counts keep planning, not judge');
  assert.equal(others[2], all);
  assert.equal(countBoth(valueSet(index, 'capability', 'tool-use'), others[0]), 1);
  assert.deepEqual(ids(intersect(index.all, [null, null])), ROWS.map((r) => r.id));
});

// ---- against brute force, over a seeded random corpus ---------------------------------------------------------

function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

test('over 3,000 random queries on a random 777-row corpus, filter() and constrain() equal a brute-force predicate', () => {
  const rnd = seeded(20261124);
  const pick = (n) => Math.floor(rnd() * n);
  const VOCAB = { capability: 12, evaluation_method: 6, execution: 8 };
  const rows = Array.from({ length: 777 }, (_, i) => row(`r${i}`, `R${i}`, {
    domain: `f${pick(4)}`, subdomain: `s${pick(9)}`, year: rnd() < 0.1 ? null : 2000 + pick(27), headroom: rnd() < 0.3 ? null : Math.round(rnd() * 100) / 100,
    facets: Object.fromEntries(Object.entries(VOCAB).map(([f, n]) => [f, [...new Set(Array.from({ length: pick(4) }, () => `${f}-${pick(n)}`))]])),
  }));
  const index = buildFacetIndex(rows);
  const facetsOf = (r, f) => (f === 'domain' || f === 'subdomain' ? [r[f]] : r.facets[f] ?? []);
  const inRange = (v, [lo, hi]) => v != null && Math.fround(v) >= Math.fround(lo) && Math.fround(v) <= Math.fround(hi);
  for (let k = 0; k < 3000; k++) {
    const facets = {};
    for (const [f, n] of [...Object.entries(VOCAB), ['domain', 4]]) {
      if (rnd() < 0.4) facets[f] = Array.from({ length: pick(3) }, () => (f === 'domain' ? `f${pick(n + 1)}` : `${f}-${pick(n + 1)}`));
    }
    const ranges = {};
    if (rnd() < 0.3) ranges.year = [2000 + pick(30), 2000 + pick(30)];
    if (rnd() < 0.3) ranges.headroom = [Math.round(rnd() * 100) / 100, Math.round(rnd() * 100) / 100];
    const passes = (r, skip) => Object.entries(ranges).every(([n, b]) => inRange(r[n], b))
      && Object.entries(facets).every(([f, vs]) => f === skip || vs.length === 0 || vs.some((v) => facetsOf(r, f).includes(v)));
    const want = rows.flatMap((r, i) => (passes(r, null) ? [i] : []));
    assert.deepEqual(members(filter(index, { facets, ranges })), want, JSON.stringify({ facets, ranges }));
    // the faceted counts' sets, facet by facet
    const names = Object.keys(facets);
    const base = filter(index, { ranges });
    const unions = names.map((f) => (facets[f].length === 0 ? null : union(index.words, facets[f].map((v) => valueSet(index, f, v)))));
    const { all, others } = constrain(base, unions);
    assert.deepEqual(members(all), want);
    names.forEach((f, i) => assert.deepEqual(members(others[i]), rows.flatMap((r, j) => (passes(r, f) ? [j] : [])), `${f} in ${JSON.stringify(facets)}`));
  }
});

// ---- the fusion and the pipeline -------------------------------------------------------------------------------

test('RRF is the sum of 1 / (k + rank) at the published default k = 60, ties by row', () => {
  assert.equal(RRF_K, 60);
  const source = readFileSync(new URL('../src/lib/query.ts', import.meta.url), 'utf8');
  assert.match(source, /\/\*\*[^/]*standard published default[^/]*\*\/\s*export const RRF_K = 60;/, 'the constant says why it is 60');
  const a = [{ row: 7, score: 9 }, { row: 3, score: 5 }, { row: 1, score: 1 }];
  const b = [{ row: 3, score: 0.9 }, { row: 7, score: 0.2 }];
  const fused = rrf([a, b]);
  assert.deepEqual(fused.map((r) => r.row), [3, 7, 1], '3 and 7 tie on rank sum; ties go by row');
  assert.equal(fused[0].score, 1 / 62 + 1 / 61);
  assert.equal(fused[1].score, 1 / 61 + 1 / 62);
  assert.equal(fused[2].score, 1 / 63, 'a list without the row adds nothing');
  assert.deepEqual(rrf([[{ row: 2, score: 1 }, { row: 0, score: 1 }]], 0).map((r) => r.score), [1, 1 / 2], 'k is a parameter');
  assert.deepEqual(rrf([]), []);
});

test('the pipeline runs 08 S5.7\'s steps in order, and the semantic leg is absent (Phase 6), not faked', () => {
  const p = buildPipeline(ROWS);
  const plain = run(p, { facets: { domain: ['code'] } });
  assert.deepEqual(plain.rows.map((i) => ROWS[i].id), ['swe-bench', 'humaneval', 'mt-bench', 'swe-lancer'], 'no text: the survivors in row order');
  assert.equal(plain.lexical, null);
  assert.equal(plain.fused, null);
  assert.equal(plain.semantic, null);
  const searched = run(p, { facets: { capability: ['tool-use'] }, text: 'swe bench' });
  assert.deepEqual(ids(searched.survivors), ['swe-bench', 'humaneval', 'swe-lancer']);
  assert.deepEqual(searched.rows.map((i) => ROWS[i].id), ['swe-bench', 'swe-lancer'], 'filter first, then rank: humaneval does not match the text');
  assert.deepEqual(searched.fused.map((r) => r.row), searched.lexical.map((r) => r.row), 'one list: fusion keeps its order');
  assert.deepEqual(searched.lexical, bm25(p.text, 'swe bench', searched.survivors), 'step 2 is the lexical leg, over the survivors');
  assert.equal(searched.semantic, null);
  assert.deepEqual(run(p, { text: '  ' }).rows, [0, 1, 2, 3, 4], 'a blank query is no query');
  assert.deepEqual(run(buildPipeline([]), { text: 'swe', facets: { capability: ['planning'] } }).rows, [], 'an empty corpus');
});
