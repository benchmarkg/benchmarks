// site/test/workbench.test.mjs -- P3-S10-T05 (10 V5, "Filter state encoding"). src/lib/workbench.ts over constructed
// rows: the selection's one canonical URL, the pasted list and the ids a build does not have, and the table a selection
// gives -- every kept claim in exactly one cell, every claim a restriction takes out counted, each column's comparison
// cut from the build's group rather than decided again. The pages are checked over the real preview claims, with
// JavaScript on and off, by tests/e2e/v5-workbench.spec.ts.
//
//   cd site && node --test test/workbench.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY, canonical, cellKey, compareHref, constrains, encode, readQuery, resolve, restrictTo, subgroup, unrestrict, view,
} from '../src/lib/workbench.ts';

/** A claims.json row, as much of one as the modules read. */
const row = (id, system, key, { benchmark = 'bench', metric = 'm', unknown = [] } = {}) => ({
  claim: { id, system, benchmark, metric, value: 1 },
  comparability: { comparability_key: key, key_unknown_count: unknown.length, unknown_fields: unknown, condition_completeness: 1, fields_material_total: 4 },
});
const material = (a, b, field, a_val, b_val) => ({ a, b, field, a_val, b_val, severity: 'material' });

// bench/m: three sets -- k1 {c1 s1, c2 s2, c3 s3}, k2 {c4 s1, c5 s2}, k3 {c6 s4}; other/m: one key, s1 and s2
const ROWS = [
  row('c1', 's1', 'k1'), row('c2', 's2', 'k1'), row('c3', 's3', 'k1'), row('c4', 's1', 'k2'), row('c5', 's2@v2', 'k2'), row('c6', 's4', 'k3'),
  row('d1', 's1', 'j1', { benchmark: 'other@2024' }), row('d2', 's2', 'j1', { benchmark: 'other@2024' }),
];
const pairs = [];
for (const a of ROWS.slice(0, 6)) {
  for (const b of ROWS.slice(0, 6)) {
    if (a.claim.id < b.claim.id && a.comparability.comparability_key !== b.comparability.comparability_key) {
      const v = (r) => ({ k1: 0, k2: 5, k3: 5 })[r.comparability.comparability_key];
      const t = (r) => ({ k1: 'none', k2: 'none', k3: 'bash' })[r.comparability.comparability_key];
      if (v(a) !== v(b)) pairs.push(material(a.claim.id, b.claim.id, 'shots', v(a), v(b)));
      if (t(a) !== t(b)) pairs.push(material(a.claim.id, b.claim.id, 'tools_allowed', t(a), t(b)));
    }
  }
}
const GROUPS = new Map([
  ['bench\u0000m', { benchmark: 'bench', metric: 'm', claims: 6, keys: 3, pairs: 11, diff_status: 'computed', rows: pairs }],
  ['other\u0000m', { benchmark: 'other', metric: 'm', claims: 2, keys: 1, pairs: 0, diff_status: 'computed', rows: [] }],
]);
const INDEX = {
  benchmarks: new Map([['bench', 'Bench'], ['other', 'Other'], ['empty', 'Empty']]),
  systems: new Map([['s1', 'One'], ['s2', 'Two'], ['s3', 'Three'], ['s4', 'Four'], ['s9', 'Nine']]),
  metrics: new Map([['m', 'Metric']]),
  rows: ROWS,
};
const ids = (v, column, system) => (v.cells.get(cellKey(column, system)) ?? []).map((r) => r.claim.id);

test('one selection, one URL: keys sorted, values sorted and once, v=1, the bare address for no constraint', () => {
  assert.equal(encode({ sys: ['s2', 's1', 's1'], b: ['other', 'bench'] }), 'b=bench,other&sys=s1,s2&v=1');
  assert.equal(compareHref(EMPTY), '/compare/');
  assert.equal(compareHref({ k: ['k2'] }), '/compare/?k=k2&v=1');
  assert.equal(encode(canonical({ b: [' bench ', ''] })), 'b=bench&v=1');
  assert.equal(constrains(EMPTY), false);
  const q = readQuery('?sys=s2,s1&b=bench&zz=1&ids=c4%0As9,+nope;other&v=1');
  assert.deepEqual(q, { b: ['bench'], k: [], sys: ['s2', 's1'], ids: ['c4', 's9', 'nope', 'other'], version: '1' });
  assert.equal(encode(resolve(readQuery(`?${encode({ b: ['other', 'bench'], sys: ['s1'] })}`), INDEX).selection), 'b=bench,other&sys=s1&v=1', 'idempotent');
});

test('a pasted list resolves to benchmarks and systems, a claim adding both; what the build lacks is ignored, visibly', () => {
  const { selection, ignored } = resolve(readQuery('?ids=c5+s9+other@2024+nope&k=k9&b=gone&v=2'), INDEX);
  assert.deepEqual(selection, { b: ['bench', 'other'], k: [], sys: ['s2', 's9'] }, 'c5 adds s2 (its version dropped) and bench');
  assert.deepEqual(ignored.map((i) => `${i.key}=${i.value}`), ['b=gone', 'k=k9', 'ids=nope', 'v=2']);
  assert.ok(ignored.every((i) => i.why.length > 0));
});

test('the bare address is every claim: each in one cell, the build\'s comparison of every whole group', () => {
  const v = view(INDEX, GROUPS, EMPTY);
  assert.equal(v.claims, 8);
  assert.equal(v.dropped, 0);
  assert.deepEqual(v.columns.map((c) => [c.id, c.comparison.state]), [['bench|m', 'not-comparable'], ['other|m', 'comparable']]);
  assert.deepEqual(v.rows.map((r) => [r.system, r.spans]), [['s4', 1], ['s1', 1], ['s3', 1], ['s2', 1]], 'by name: Four, One, Three, Two');
  assert.deepEqual(ids(v, 'bench|m', 's1'), ['c1', 'c4'], 'by set label, then id');
  assert.deepEqual(ids(v, 'bench|m', 's2'), ['c2', 'c5'], 's2@v2 is drawn in s2\'s row');
  const g = v.columns[0].comparison;
  assert.deepEqual(g.sets.map((s) => [s.label, s.key, s.rows.length]), [['A', 'k1', 3], ['B', 'k2', 2], ['C', 'k3', 1]]);
  assert.deepEqual(g.diff.map((d) => d.field), ['shots', 'tools_allowed']);
  assert.deepEqual(g.restrict, { label: 'A', keeps: 3, drops: 3 });
});

test('a selection keeps its claims only, and the comparison is cut from the build\'s rows: fewer sets, fewer fields', () => {
  const v = view(INDEX, GROUPS, { b: ['bench'], k: [], sys: ['s1', 's3'] });
  assert.deepEqual(v.columns.map((c) => c.id), ['bench|m']);
  assert.deepEqual(v.rows.map((r) => r.system), ['s1', 's3']);
  const g = v.columns[0].comparison;
  assert.equal(g.total, 3);
  assert.deepEqual(g.sets.map((s) => [s.label, s.key, s.rows.map((r) => r.claim.id)]), [['A', 'k1', ['c1', 'c3']], ['B', 'k2', ['c4']]]);
  assert.deepEqual(g.diff.map((d) => d.field), ['shots'], 'k1 and k2 differ in shots only; tools_allowed was k3\'s');
  assert.deepEqual(g.restrict.drops, 1);
  const one = view(INDEX, GROUPS, { b: [], k: [], sys: ['s3', 's4'] });
  assert.deepEqual(one.columns.map((c) => [c.id, c.comparison.state]), [['bench|m', 'not-comparable']]);
  const sub = subgroup(GROUPS.get('bench\u0000m'), ROWS.filter((r) => ['c1', 'c2', 'c4'].includes(r.claim.id)));
  assert.deepEqual([sub.claims, sub.keys, sub.pairs], [3, 2, 2]);
  assert.ok(sub.rows.every((d) => ['c1', 'c2', 'c4'].includes(d.a) && ['c1', 'c2', 'c4'].includes(d.b)));
});

test('a selected benchmark or system with no curated claim is drawn as absent cells, not left out', () => {
  const v = view(INDEX, GROUPS, { b: ['empty', 'other'], k: [], sys: ['s1', 's9'] });
  assert.deepEqual(v.columns.map((c) => [c.id, c.comparison?.state ?? null]), [['empty|', null], ['other|m', 'single']]);
  assert.deepEqual(v.rows.map((r) => r.system), ['s9', 's1'], 'by name: Nine, One; s9 has no claim and keeps its row');
  assert.deepEqual(ids(v, 'empty|', 's1'), []);
  assert.deepEqual(ids(v, 'other|m', 's9'), []);
  assert.equal(v.claims, 1);
});

test('a restriction keeps one condition set in its column and counts every claim it drops', () => {
  const sel = restrictTo(EMPTY, 'k1');
  assert.deepEqual(sel, { b: [], k: ['k1'], sys: [] });
  const v = view(INDEX, GROUPS, sel);
  const c = v.columns.find((x) => x.id === 'bench|m');
  assert.deepEqual(c.restricted, ['k1']);
  assert.deepEqual(c.dropped.map((r) => r.claim.id).sort(), ['c4', 'c5', 'c6']);
  assert.equal(c.comparison.state, 'comparable');
  assert.equal(v.dropped, 3);
  assert.equal(v.claims, 5);
  assert.ok(v.rows.some((r) => r.system === 's4'), 's4 keeps its row: its claim was dropped, and the cell says so');
  assert.deepEqual(ids(v, 'bench|m', 's4'), []);
  assert.deepEqual(unrestrict(sel, c), EMPTY);
});

test('a comparability artifact that is not this claims file\'s is refused, not cut', () => {
  const short = new Map(GROUPS);
  short.set('bench\u0000m', { ...GROUPS.get('bench\u0000m'), claims: 5 });
  assert.throws(() => view(INDEX, short, EMPTY), /not one build's/);
  assert.throws(() => view(INDEX, new Map(), EMPTY), /has no group/);
});
