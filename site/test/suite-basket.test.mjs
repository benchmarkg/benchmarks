// site/test/suite-basket.test.mjs -- P6-S4-T01 (10 V10 "Basket persistence"; 10 "Filter state encoding"). src/lib/
// suite-basket.ts: the basket is 10's `b` key in lib/filter-url.ts's grammar and no second codec, one basket is one URL,
// an id the index does not have surfaces as an ignored value, and localStorage only mirrors and offers.
//
//   cd site && node --test test/suite-basket.test.mjs
//
// Node strips the module's types itself, so it is loaded as the site loads it. The browser half -- a basket that
// round-trips through its link alone, in a context with no storage -- is tests/suite-basket.spec.ts.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decode, encode, ignoredNotice } from '../src/lib/filter-url.ts';
import {
  STORE_KEY, SUITE_PATH, added, answers, basketOf, offer, removed, store, stored, suiteHref, withBasket, withIds,
} from '../src/lib/suite-basket.ts';

/** A Storage stand-in: a Map, or one whose every call throws, as a private window's or blocked site data's does. */
const memory = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { m, getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
};
const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); }, removeItem() { throw new Error('denied'); } };

test('a basket link is filter-url encode() of `b`: sorted, each once, the grammar version last', () => {
  assert.equal(SUITE_PATH, '/suite/');
  assert.equal(suiteHref(['tau2-bench', 'swe-bench', 'gaia', 'swe-bench']), '/suite/?b=gaia,swe-bench,tau2-bench&v=1');
  assert.equal(suiteHref(['tau2-bench', 'gaia']), `/suite/?${encode({ b: ['gaia', 'tau2-bench'] })}`);
  // the Atlas writes `/suite/?` + encode({ b: ids }) inline (islands/AtlasSelection.tsx): the same string for any order
  for (const ids of [['b', 'a'], ['a', 'b'], ['a', 'b', 'a']]) assert.equal(`/suite/?${encode({ b: ids })}`, suiteHref(['a', 'b']));
  // the filter pane's keys sit beside it, in the one canonical order
  assert.equal(suiteHref(['gaia'], { q: 'web agent', c: ['tool-use'] }), '/suite/?b=gaia&c=tool-use&q=web%20agent&v=1');
  assert.equal(suiteHref([]), '/suite/', 'an empty basket is no key at all');
});

test('one basket, one URL: any order, any repetition, decoded and encoded again, is the same string', () => {
  const ids = ['swe-bench', 'gaia', 'osworld', 'agentdojo', 'cybench', 'tau2-bench', 'terminal-bench'];
  const canonical = suiteHref(ids).slice(SUITE_PATH.length + 1);
  // a seeded shuffle (a linear congruential generator), so a failure names an order that can be replayed
  let seed = 7;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < 50; i++) {
    const list = [...ids, ...ids.slice(0, i % 3)];
    for (let j = list.length - 1; j > 0; j--) {
      const k = Math.floor(next() * (j + 1));
      [list[j], list[k]] = [list[k], list[j]];
    }
    const q = `b=${list.join(',')}`;
    assert.equal(encode(decode(q).state), canonical, q);
    assert.deepEqual(basketOf(decode(q).state), [...ids].sort());
  }
  // a link with the version missing, or the basket split over two `b` keys, reads as the same basket
  assert.deepEqual(basketOf(decode('?b=swe-bench,gaia').state), ['gaia', 'swe-bench']);
  assert.equal(encode(decode('?b=swe-bench&b=gaia').state), 'b=gaia,swe-bench&v=1');
});

test('adding, removing and emptying keep the basket canonical, and an empty basket drops the key', () => {
  let s = decode('?c=planning&b=gaia').state;
  s = added(s, ['swe-bench', 'gaia']);
  assert.deepEqual(s.b, ['gaia', 'swe-bench']);
  assert.deepEqual(s.c, ['planning'], 'the filter keys are left as they were');
  s = removed(s, 'gaia');
  assert.deepEqual(s.b, ['swe-bench']);
  s = removed(s, 'swe-bench');
  assert.ok(!('b' in s));
  assert.equal(encode(s), 'c=planning&v=1');
  assert.ok(!('b' in withBasket({ b: ['x'] }, [])));
});

test('an id the index does not have is the grammar\'s unknown value: left out, and returned as a visible notice', () => {
  const vocab = withIds({ c: new Set(['planning']) }, ['gaia', 'swe-bench']);
  const d = decode('?b=gaia,no-such-benchmark,swe-bench&c=planning&v=1', vocab);
  assert.deepEqual(d.state.b, ['gaia', 'swe-bench']);
  assert.deepEqual(d.ignored, [{ key: 'b', value: 'no-such-benchmark' }]);
  assert.equal(ignoredNotice(d.ignored[0]), 'ignored filter: b=no-such-benchmark');
  // before the index is in, the vocabulary has no `b`, so nothing is judged yet
  assert.deepEqual(decode('?b=gaia,no-such-benchmark').state.b, ['gaia', 'no-such-benchmark']);
});

test('storage mirrors the basket in the URL\'s own form, and an empty basket is removed', () => {
  const s = memory();
  assert.equal(store(s, ['swe-bench', 'gaia']), true);
  assert.equal(s.m.get(STORE_KEY), 'b=gaia,swe-bench&v=1');
  assert.deepEqual(stored(s), ['gaia', 'swe-bench']);
  assert.equal(store(s, []), true);
  assert.ok(!s.m.has(STORE_KEY));
  assert.deepEqual(stored(s), []);
});

test('storage that throws, or is missing, costs only the convenience', () => {
  assert.deepEqual(stored(broken), []);
  assert.equal(store(broken, ['gaia']), false);
  assert.deepEqual(stored(null), []);
  assert.equal(store(undefined, ['gaia']), false);
  assert.deepEqual(stored(memory({ [STORE_KEY]: 'not a basket' })), []);
});

test('what storage holds is offered, never applied: only the entries the URL\'s basket lacks', () => {
  assert.deepEqual(offer(['gaia', 'osworld', 'swe-bench'], ['swe-bench']), ['gaia', 'osworld']);
  assert.deepEqual(offer(['gaia'], ['gaia', 'swe-bench']), []);
  assert.deepEqual(offer([], ['gaia']), []);
  assert.deepEqual(offer(['gaia'], []), ['gaia'], 'a bare /suite/ starts empty, and is offered the kept basket');
});

test('the search box: every word, case and accents folded, in the name, an alias or the id', () => {
  const row = { id: 'swe-bench-verified', name: 'SWE-bench Verified', aliases: ['SWE-bench (human-validated)', 'Café Bench'] };
  for (const q of [undefined, '', '   ', 'swe', 'VERIFIED', 'bench verified', 'human-validated', 'cafe', 'swe-bench-verified']) assert.ok(answers(row, q), String(q));
  for (const q of ['lite', 'swe lite', 'verifiedx']) assert.ok(!answers(row, q), q);
});
