// site/test/refusals.test.mjs -- P3-S10-T06 (10 V5 "six categorical refusals"). src/lib/refusals.ts over constructed
// rows: each of the six fires on the field 10 V5 names and only when that field splits the claims, a claim that does not
// record the field is a group of its own, the parts are the combinations of every refusal's groups, and the workbench's
// view (src/lib/workbench.ts) carries a column's refusal over the claims a selection keeps. The pages are checked over
// the preview claims and constructed fixture rows, with JavaScript on and off, by tests/e2e/v5-refusals.spec.ts.
//
//   cd site && node --test test/refusals.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { NOT_RECORDED, REFUSALS, factsOf, poolDate, refuse, signature, snapshotOf } from '../src/lib/refusals.ts';
import { EMPTY, cellKey, cellParts, view } from '../src/lib/workbench.ts';

/** A claims.json row, as much of one as the modules read. */
const row = (id, { system = `sys-${id}`, benchmark = 'b', metric = 'm', key = 'k1', claim = {}, conditions = null } = {}) => ({
  claim: { id, system, benchmark, metric, value: 1, ...claim },
  conditions: conditions == null ? null : { id: `cond-${id}`, ...conditions },
  comparability: { comparability_key: key, key_unknown_count: 0, unknown_fields: [], condition_completeness: 1, fields_material_total: 1 },
});
const facts = (benchmark = {}, metric = {}) => factsOf([{ id: 'b', name: 'Bench', ...benchmark }], [{ id: 'm', ...metric }]);
const ids = (r) => r.refusals.map((f) => f.id);
const groups = (r, id) => r.refusals.find((f) => f.id === id).groups.map((g) => [g.id, g.claims]);

test('nothing to refuse: one claim, or claims agreeing on every field a refusal reads', () => {
  assert.equal(refuse([row('c1', { claim: { claim_type: 'rating', rating_pool: 'pool-x-2026-06-10' } })]), null);
  const same = [row('c1'), row('c2', { claim: { resolution_status: 'resolved' } })];
  assert.equal(refuse(same), null, 'resolved is the default resolution_status');
  const tracks = [row('c1', { conditions: { eligibility_track: 'verified' } }), row('c2', { conditions: { eligibility_track: 'verified' } })];
  assert.equal(refuse(tracks), null);
  assert.equal(refuse([row('c1', { claim: { subset: 'b#x' } }), row('c2', { claim: { subset: 'b#y' } })], facts()), null, 'subsets alone are the key\'s business');
  assert.equal(signature(null), '');
});

test('ratings from two pools: refused, whatever the key says, and the pool id carries its snapshot date', () => {
  const rows = [
    row('c1', { claim: { claim_type: 'rating', rating_pool: 'pool-arena-2026-06-10' } }),
    row('c2', { claim: { claim_type: 'rating', rating_pool: 'pool-arena-2026-11-16' } }),
    row('c3', { claim: { claim_type: 'rating', rating_pool: 'pool-arena-2026-11-16' } }),
  ];
  const r = refuse(rows);
  assert.deepEqual(ids(r), ['rating-pool']);
  assert.deepEqual(groups(r, 'rating-pool'), [['pool-arena-2026-06-10', ['c1']], ['pool-arena-2026-11-16', ['c2', 'c3']]], 'oldest snapshot first');
  assert.match(r.refusals[0].groups[0].label, /snapshot 2026-06-10/);
  assert.match(r.refusals[0].requires, /same rating_pool/);
  assert.equal(poolDate('pool-kaggle-game-arena-chess-2026-09'), '2026-09');
  assert.equal(poolDate('pool-undated'), null);
  // a pool-relative metric with a claim that names no pool: the pool is not recorded, never assumed the other's
  const mixed = refuse([row('c1', { claim: { rating_pool: 'pool-a-2026-01' } }), row('c2')], facts({}, { requires_pool: true }));
  assert.deepEqual(groups(mixed, 'rating-pool'), [['pool-a-2026-01', ['c1']], [NOT_RECORDED, ['c2']]]);
});

test("a rating's snapshot is its pool record's, as the build inlines it; a row without the record reads the id's date", () => {
  const rated = (id, pool, rec) => ({ ...row(id, { claim: { claim_type: 'rating', rating_pool: pool } }), pool: rec });
  const r = refuse([
    rated('c1', 'pool-chess-2026-09', { id: 'pool-chess-2026-09', snapshot_date: '2026-09-25' }),
    rated('c2', 'pool-chess-2026-10', { id: 'pool-chess-2026-10', snapshot_date: '2026-10-02' }),
  ]);
  assert.deepEqual(r.refusals[0].groups.map((g) => g.label), ['pool-chess-2026-09, snapshot 2026-09-25', 'pool-chess-2026-10, snapshot 2026-10-02']);
  assert.equal(snapshotOf(rated('c3', 'pool-chess-2026-09', null)), '2026-09', "no record inlined: the id's month");
  assert.equal(snapshotOf(rated('c4', 'pool-chess-2026-09', { id: 'pool-other-2026-01-01', snapshot_date: '2026-01-01' })), '2026-09',
    "another pool's record is not this claim's");
  assert.equal(snapshotOf(row('c5')), null);
});

test('pass^k across k, and pass^k beside another selection strategy, are refused; pass@k across k is the key\'s', () => {
  const k = (id, s, kk) => row(id, { conditions: { selection_strategy: s, k: kk } });
  const r = refuse([k('c1', 'pass-hat-k', 8), k('c2', 'pass-hat-k', 1), k('c3', 'pass-hat-k', null), k('c4', 'single', null), row('c5')]);
  assert.deepEqual(ids(r), ['pass-hat-k']);
  assert.deepEqual(groups(r, 'pass-hat-k').map(([g]) => g), ['pass-hat-k@1', 'pass-hat-k@8', 'pass-hat-k', 'single', NOT_RECORDED], 'k ascending, an unrecorded k, other strategies, none recorded');
  assert.match(r.refusals[0].why, /pass\^1 and pass\^8 are different metrics/);
  assert.equal(refuse([k('c1', 'pass-at-k', 1), k('c2', 'pass-at-k', 4)]), null);
});

test('a vector-valued result across dimensions: refused on no_legitimate_aggregate, none-by-design or a vector metric', () => {
  const rows = [row('c1', { claim: { subset: 'b#z500' } }), row('c2', { claim: { subset: 'b#t850' } }), row('c3')];
  for (const f of [facts({ no_legitimate_aggregate: true }), facts({ aggregation_policy: 'none-by-design' }), facts({}, { value_type: 'vector' })]) {
    const r = refuse(rows, f);
    assert.deepEqual(ids(r), ['vector-valued']);
    assert.deepEqual(groups(r, 'vector-valued'), [['b#t850', ['c2']], ['b#z500', ['c1']], [NOT_RECORDED, ['c3']]]);
    assert.match(r.refusals[0].why, /^Bench /);
  }
  assert.equal(refuse(rows, facts({ aggregation_policy: 'official-aggregate' })), null);
});

test('two eligibility tracks, two training-data tiers: refused, each tier named by the benchmark\'s label', () => {
  const tier = (id, t, tr) => row(id, { conditions: { training_data_eligibility: t, eligibility_track: tr } });
  const f = facts({ training_data_eligibility_tiers: [{ id: 'compliant', label: 'Compliant', rule: 'MP only' }] });
  const r = refuse([tier('c1', 'compliant', 'compliant'), tier('c2', 'non-compliant', 'non-compliant'), tier('c3', 'compliant', 'compliant')], f);
  assert.deepEqual(ids(r), ['legality-track', 'training-eligibility'], 'in 10 V5\'s order');
  assert.equal(r.refusals[1].groups[0].label, 'tier Compliant (compliant)');
  assert.equal(r.refusals[1].groups[1].label, 'tier non-compliant', 'a tier the benchmark does not declare keeps its id');
  assert.deepEqual(r.parts.map((p) => p.claims), [['c1', 'c3'], ['c2']], 'the two refusals cut alike: two parts, not four');
  const unrecorded = refuse([row('c1', { conditions: { eligibility_track: 'community' } }), row('c2', { conditions: {} })]);
  assert.deepEqual(groups(unrecorded, 'legality-track'), [['community', ['c1']], [NOT_RECORDED, ['c2']]]);
});

test('pending, partial and resolved: refused, every status apart', () => {
  const s = (id, status) => row(id, { claim: { resolution_status: status, value: status === 'pending' ? null : 0.1 } });
  const r = refuse([s('c1', 'pending'), s('c2', 'resolved'), s('c3', 'partial')]);
  assert.deepEqual(ids(r), ['resolution']);
  assert.deepEqual(groups(r, 'resolution').map(([g]) => g), ['resolved', 'partial', 'pending']);
});

test('refusals combine: each part is a combination of groups, ordered, and every claim is in exactly one', () => {
  const rows = [
    row('c1', { claim: { resolution_status: 'pending', value: null }, conditions: { eligibility_track: 'a' } }),
    row('c2', { conditions: { eligibility_track: 'a' } }),
    row('c3', { conditions: { eligibility_track: 'b' } }),
    row('c4', { conditions: { eligibility_track: 'b' } }),
  ];
  const r = refuse(rows);
  assert.deepEqual(ids(r), ['legality-track', 'resolution']);
  assert.deepEqual(r.parts.map((p) => [p.groups, p.claims]), [[['a', 'resolved'], ['c2']], [['a', 'pending'], ['c1']], [['b', 'resolved'], ['c3', 'c4']]]);
  assert.deepEqual([...r.partOf.keys()].sort(), ['c1', 'c2', 'c3', 'c4']);
  assert.equal(new Set(r.parts.map((p) => p.id)).size, r.parts.length);
  assert.match(signature(r), /^legality-track resolution \| /);
  assert.deepEqual(REFUSALS, ['rating-pool', 'pass-hat-k', 'vector-valued', 'legality-track', 'training-eligibility', 'resolution']);
});

test('the workbench\'s view carries each column\'s refusal over the claims a selection keeps, and cuts its cells by part', () => {
  const rows = [
    row('c1', { system: 's1', claim: { claim_type: 'rating', rating_pool: 'pool-p-2026-01' } }),
    row('c2', { system: 's1', claim: { claim_type: 'rating', rating_pool: 'pool-p-2026-02' } }),
    row('c3', { system: 's2', claim: { claim_type: 'rating', rating_pool: 'pool-p-2026-02' } }),
  ];
  const index = { benchmarks: new Map([['b', 'Bench']]), systems: new Map([['s1', 'One'], ['s2', 'Two']]), metrics: new Map([['m', 'M']]), rows };
  const groupsOf = new Map([['b\u0000m', { benchmark: 'b', metric: 'm', claims: 3, keys: 1, pairs: 0, diff_status: 'computed', rows: [] }]]);
  const all = view(index, groupsOf, EMPTY);
  const c = all.columns[0];
  assert.equal(c.comparison.state, 'comparable', 'one key, nothing unknown: the key alone would show them together');
  assert.deepEqual(ids(c.refusal), ['rating-pool']);
  assert.deepEqual(cellParts(c, all.cells.get(cellKey(c.id, 's1'))).map((p) => p.map((x) => x.claim.id)), [['c1'], ['c2']]);
  assert.deepEqual(cellParts(c, all.cells.get(cellKey(c.id, 's2')) ?? []).map((p) => p.map((x) => x.claim.id)), [[], ['c3']]);
  const one = view(index, groupsOf, { b: [], k: [], sys: ['s2'] });
  assert.equal(one.columns[0].refusal, null, 'a selection keeping one pool has nothing to refuse');
  assert.deepEqual(cellParts(one.columns[0], one.cells.get(cellKey(one.columns[0].id, 's2'))).map((p) => p.length), [1]);
});
