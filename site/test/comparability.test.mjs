// site/test/comparability.test.mjs -- P3-S10-T04 (04 S8 "What the UI does with it"; 08 S3.2 S5). src/lib/comparability.ts
// over constructed rows: the three states, the condition sets, the diff table read off derived/comparability.json's
// rows, the deferred group no page can show a diff for, and the artifact checks. The pages are checked over the real
// preview claims by tests/e2e/comparability-states.spec.ts; what is here is what that preview cannot exercise.
//
//   cd site && node --test test/comparability.test.mjs
//
// Node strips comparability.ts's types itself (its one import from the site is a type), so the module is loaded as the
// site loads it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DEFER_ABOVE, cell, compare, comparisons, conditionSets, diffGroups, setLabel, unknownsOn } from '../src/lib/comparability.ts';

/** A claims.json row, as much of one as the module reads. */
const row = (id, key, unknown = [], { metric = 'm', benchmark = 'b', value = 1 } = {}) => ({
  claim: { id, system: `sys-${id}`, benchmark, metric, value },
  comparability: { comparability_key: key, key_unknown_count: unknown.length, unknown_fields: unknown, condition_completeness: 1, fields_material_total: 4 },
});
const group = (rows, extra = {}) => {
  const keys = new Set(rows.map((r) => r.comparability.comparability_key)).size;
  return { benchmark: 'b', metric: 'm', claims: rows.length, keys, pairs: 0, diff_status: 'computed', rows: [], ...extra };
};
const material = (a, b, field, a_val, b_val) => ({ a, b, field, a_val, b_val, severity: 'material' });

test('state 1: one key and nothing unknown is comparable', () => {
  const rows = [row('c1', 'k1'), row('c2', 'k1')];
  const c = compare(rows, group(rows));
  assert.equal(c.state, 'comparable');
  assert.equal(c.total, 2);
  assert.equal(c.restrict, null);
  assert.deepEqual(c.diff, []);
});

test('state 2: one key with unknowns is possibly comparable, never comparable, and names the fields on each claim', () => {
  const rows = [row('c1', 'k1', ['chain_of_thought']), row('c2', 'k1', ['chain_of_thought'])];
  const c = compare(rows, group(rows));
  assert.equal(c.state, 'possibly-comparable');
  assert.deepEqual(unknownsOn(c.sets[0]), [
    { claim: 'c1', system: 'sys-c1', fields: ['chain_of_thought'] }, { claim: 'c2', system: 'sys-c2', fields: ['chain_of_thought'] }]);
  // one key is one key tuple: rows that share it but not its unknowns, or miscount them, are not this build's
  assert.throws(() => compare([row('c1', 'k1', ['shots']), row('c2', 'k1', [])], group([row('c1', 'k1'), row('c2', 'k1')])), /one key is one key tuple/);
  const miscounted = row('c1', 'k1', ['shots']);
  miscounted.comparability.key_unknown_count = 0;
  assert.throws(() => conditionSets([miscounted]), /key_unknown_count 0 but 1 unknown/);
});

test('one claim compares with nothing', () => {
  const rows = [row('c1', 'k1', ['shots'])];
  assert.equal(compare(rows, group(rows)).state, 'single');
});

test('state 3: different keys, the largest set first, the diff table one cell per set, the restriction counted', () => {
  const rows = [row('c1', 'k1'), row('c2', 'k2', ['judge_model']), row('c3', 'k1'), row('c4', 'k3')];
  const diff = [
    material('c1', 'c2', 'shots', 0, 5), material('c1', 'c2', 'judge_model', null, '?'), material('c2', 'c3', 'shots', 5, 0),
    material('c2', 'c3', 'judge_model', '?', null), material('c1', 'c4', 'tools_allowed', ['bash', 'edit'], []),
    material('c2', 'c4', 'shots', 5, 0), material('c2', 'c4', 'judge_model', '?', null), material('c2', 'c4', 'tools_allowed', ['bash', 'edit'], []),
    material('c3', 'c4', 'tools_allowed', ['bash', 'edit'], []),
    { a: 'c1', b: 'c2', field: 'temperature', a_val: 1, b_val: 0, severity: 'informative' },
  ];
  const c = compare(rows, group(rows, { rows: diff }));
  assert.equal(c.state, 'not-comparable');
  assert.deepEqual(c.sets.map((s) => [s.label, s.key, s.rows.map((r) => r.claim.id)]), [['A', 'k1', ['c1', 'c3']], ['B', 'k2', ['c2']], ['C', 'k3', ['c4']]]);
  assert.deepEqual(c.restrict, { label: 'A', keeps: 2, drops: 2 });
  // material fields only, by name; an answered absence (null) and an unknown ('?') are different cells
  assert.deepEqual(c.diff, [
    { field: 'judge_model', values: [{ kind: 'none' }, { kind: 'unknown' }, { kind: 'none' }] },
    { field: 'shots', values: [{ kind: 'value', text: '0' }, { kind: 'value', text: '5' }, { kind: 'value', text: '0' }] },
    { field: 'tools_allowed', values: [{ kind: 'value', text: '[bash, edit]' }, { kind: 'value', text: '[bash, edit]' }, { kind: 'value', text: '[]' }] },
  ]);
  // a set given two values for one field, or a pair naming a claim of no set, is not one build's
  assert.throws(() => compare(rows, group(rows, { rows: [...diff, material('c3', 'c2', 'shots', 1, 5)] })), /two values for shots/);
  assert.throws(() => compare(rows, group(rows, { rows: [...diff, material('c9', 'c2', 'shots', 0, 5)] })), /names c9/);
  assert.throws(() => compare(rows, group(rows, { rows: [] })), /names no material field/);
});

test('a deferred group (above 40 claims) is still refused, with its sets counted and no diff invented', () => {
  const rows = Array.from({ length: DEFER_ABOVE + 1 }, (_, i) => row(`c${String(i).padStart(2, '0')}`, i < 30 ? 'k1' : 'k2'));
  const c = compare(rows, group(rows, { diff_status: 'deferred', rows: null }));
  assert.equal(c.state, 'not-comparable');
  assert.equal(c.diff_status, 'deferred');
  assert.deepEqual(c.diff, []);
  assert.deepEqual(c.restrict, { label: 'A', keeps: 30, drops: 11 });
});

test('the group must be the one derived/comparability.json counts', () => {
  const rows = [row('c1', 'k1'), row('c2', 'k2')];
  assert.throws(() => compare(rows, undefined), /has no group/);
  assert.throws(() => compare(rows, group(rows, { claims: 3 })), /not one build's/);
  assert.throws(() => compare(rows, group(rows, { keys: 1 })), /not one build's/);
  assert.throws(() => compare([row('c1', 'k1'), row('c2', 'k1', [], { metric: 'n' })], group(rows)), /is not on \(b, m\)/);
});

test('comparisons groups a page by benchmark family and metric, in metric order, keeping the page order within', () => {
  const rows = [row('c3', 'k1', [], { metric: 'z' }), row('c1', 'k1', [], { benchmark: 'b@2' }), row('c2', 'k1')];
  const g = new Map([['b\u0000m', group([rows[1], rows[2]])], ['b\u0000z', { ...group([rows[0]]), metric: 'z' }]]);
  assert.deepEqual(comparisons(rows, g).map((c) => [c.metric, c.id, c.sets[0].rows.map((r) => r.claim.id)]), [['m', 'cmp-m', ['c1', 'c2']], ['z', 'cmp-z', ['c3']]]);
});

test('set labels run A..Z then AA', () => {
  assert.deepEqual([0, 1, 25, 26, 27, 51, 52].map(setLabel), ['A', 'B', 'Z', 'AA', 'AB', 'AZ', 'BA']);
});

test('cells: values as text, the answered absence and the unknown marker apart', () => {
  assert.deepEqual(cell('?'), { kind: 'unknown' });
  assert.deepEqual(cell(null), { kind: 'none' });
  assert.deepEqual(cell(false), { kind: 'value', text: 'false' });
  assert.deepEqual(cell(0), { kind: 'value', text: '0' });
  assert.deepEqual(cell({ temperature: 1, top_p: null }), { kind: 'value', text: 'temperature 1' });
});

test('derived/comparability.json is read beside claims.json, and refused when missing or not that build', () => {
  const dir = mkdtempSync(join(tmpdir(), 'cmp-'));
  try {
    assert.equal(diffGroups(null), null);
    assert.throws(() => diffGroups({ dir, drafts: false }), /missing beside claims.json/);
    mkdirSync(join(dir, 'derived'));
    const doc = { artifact: 'comparability', format: 1, unknown: '?', defer_above: 40, groups: [group([row('c1', 'k1')])] };
    writeFileSync(join(dir, 'derived', 'comparability.json'), JSON.stringify(doc));
    assert.deepEqual([...diffGroups({ dir, drafts: false }).keys()], ['b\u0000m']);
    assert.throws(() => diffGroups({ dir, drafts: true }), /not one build/);
    writeFileSync(join(dir, 'derived', 'comparability.json'), JSON.stringify({ ...doc, groups: [group([row('c1', 'k1')], { diff_status: 'deferred', rows: null })] }));
    assert.throws(() => diffGroups({ dir, drafts: false }), /of 1 claims is deferred/);
    writeFileSync(join(dir, 'derived', 'comparability.json'), JSON.stringify({ ...doc, defer_above: 50 }));
    assert.throws(() => diffGroups({ dir, drafts: false }), /defer_above 40/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
