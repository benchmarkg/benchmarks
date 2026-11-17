// site/test/filter-url.test.mjs -- P2-S4-T03 (10 "Filter state encoding"). src/lib/filter-url.ts: one selection always
// produces exactly one URL, unknown values surface visibly rather than silently, and no group key exists.
//
//   cd site && node --test test/filter-url.test.mjs
//
// Node strips filter-url.ts's types itself (it imports nothing), so the module is loaded as the site loads it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  GRAMMAR_VERSION, KEYS, RANGE_KEYS, SINGLE_KEYS, TERM_KEYS, canonicalRange, canonicalise, decode, encode, ignoredNotice,
} from '../src/lib/filter-url.ts';

const VOCAB = {
  c: new Set(['planning', 'tool-use', 'deductive-reasoning', 'perception', 'quantitative-reasoning']),
  d: new Set(['robotics-embodiment', 'robotics-embodiment/manipulation', 'code', 'code/repository-scale-se']),
  em: new Set(['simulation-rollout', 'execution-tests', 'model-graded-judge']),
  lc: new Set(['active', 'mature', 'saturated']),
  sort: new Set(['headroom', 'name', 'year']),
};

test("10's own example is the canonical form, byte for byte", () => {
  const url = encode({
    q: 'bimanual', sort: 'headroom', lc: ['mature', 'active'], hr: '0.0-0.8', em: ['simulation-rollout'],
    d: ['robotics-embodiment/manipulation'], c: ['tool-use', 'planning'],
  });
  assert.equal(url, 'c=planning,tool-use&d=robotics-embodiment%2Fmanipulation&em=simulation-rollout&hr=0.0-0.8'
    + '&lc=active,mature&q=bimanual&sort=headroom&v=1');
});

// A seeded generator, so a failure names a selection that can be replayed.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}
const pick = (r, xs) => xs.filter(() => r() < 0.5);
const shuffle = (r, xs) => xs.map((x) => [r(), x]).sort((a, b) => a[0] - b[0]).map((p) => p[1]);

function selection(r) {
  const s = {};
  for (const key of Object.keys(VOCAB)) {
    if (key === 'sort') continue;
    const values = pick(r, [...VOCAB[key]]);
    if (values.length) s[key] = values;
  }
  if (r() < 0.5) s.hr = `${(r() * 0.5).toFixed(1)}-${(0.5 + r() * 0.5).toFixed(1)}`;
  if (r() < 0.5) s.yr = '2019-2026';
  if (r() < 0.5) s.q = ['bimanual', 'long horizon', 'a,b'][Math.floor(r() * 3)];
  if (r() < 0.5) s.sort = ['headroom', 'name', 'year'][Math.floor(r() * 3)];
  return s;
}

test('one selection, one URL: any order of keys and values, any duplicate, gives the same string', () => {
  const r = rng(20261117);
  for (let i = 0; i < 500; i++) {
    const s = selection(r);
    const url = encode(s);
    const again = {};
    for (const key of shuffle(r, Object.keys(s))) {
      const v = s[key];
      again[key] = Array.isArray(v) ? shuffle(r, [...v, ...pick(r, v)]) : v;   // reordered, with repeats
    }
    assert.equal(encode(again), url, JSON.stringify(s));
    const back = decode(url, VOCAB);
    assert.deepEqual(back.ignored, []);
    assert.equal(back.version, GRAMMAR_VERSION);
    assert.equal(encode(back.state), url, 'decode then encode returns the same URL');
    assert.equal(canonicalise(url, VOCAB), url, 'canonical form is a fixed point');
  }
});

test('a hand-written URL in any order canonicalises to the one string', () => {
  const messy = '?sort=headroom&lc=mature,active&c=tool-use,planning,planning&hr=0-0.8&q=bimanual';
  assert.equal(canonicalise(messy, VOCAB), 'c=planning,tool-use&hr=0.0-0.8&lc=active,mature&q=bimanual&sort=headroom&v=1');
});

test('unknown values are dropped from the state and returned for a visible notice', () => {
  const { state, ignored } = decode('c=planning,nonexistent-term&lc=active&sort=popularity&hr=0.9-0.1', VOCAB);
  assert.deepEqual(state, { c: ['planning'], lc: ['active'] });
  assert.deepEqual(ignored, [{ key: 'c', value: 'nonexistent-term' }, { key: 'sort', value: 'popularity' },
    { key: 'hr', value: '0.9-0.1' }]);
  assert.equal(ignoredNotice(ignored[0]), 'ignored filter: c=nonexistent-term');
});

test('unknown keys are ignored without a notice, and never written back', () => {
  const { state, ignored } = decode('g=frontier-science&group=core&zz=1&c=planning&v=1', VOCAB);
  assert.deepEqual(state, { c: ['planning'] });
  assert.deepEqual(ignored, []);
  assert.equal(encode({ ...state, group: ['core'], g: ['core'] }), 'c=planning&v=1');
});

test('there is no key for the presentation group', () => {
  const all = new Set([...KEYS, 'v']);
  for (const k of ['g', 'grp', 'group', 'dg', 'domain_group', 'family_group']) assert.ok(!all.has(k), k);
  assert.deepEqual([...KEYS], [...KEYS].sort(), 'keys are written in alphabetical order');
  assert.equal(Object.keys(TERM_KEYS).length + Object.keys(RANGE_KEYS).length + Object.keys(SINGLE_KEYS).length,
    KEYS.length);
});

test('an empty selection is the bare path; an omitted key is no constraint', () => {
  assert.equal(encode({}), '');
  assert.equal(encode({ c: [], q: '  ', hr: 'not-a-range' }), '');
  assert.deepEqual(decode('', VOCAB), { state: {}, ignored: [], version: null });
});

test('ranges are checked and written one way', () => {
  assert.equal(canonicalRange('hr', '0-0.8'), '0.0-0.8');
  assert.equal(canonicalRange('hr', '0.25-1'), '0.25-1.0');
  assert.equal(canonicalRange('hr', '0-2'), null);
  assert.equal(canonicalRange('yr', '2020-2024'), '2020-2024');
  assert.equal(canonicalRange('yr', '2020.5-2021'), null);
  assert.equal(canonicalRange('yr', '2024-2020'), null);
});

test('the free-text query is one value: commas and spaces survive the round trip', () => {
  const url = encode({ q: '  long   horizon, bimanual ' });
  assert.equal(url, 'q=long%20horizon%2C%20bimanual&v=1');
  assert.deepEqual(decode(url).state, { q: 'long horizon, bimanual' });
  assert.deepEqual(decode('q=two+words').state, { q: 'two words' });
});

test('a value that is not valid percent-encoding is ignored, not thrown', () => {
  const { state, ignored } = decode('c=planning,%E0%A4%A&q=%', VOCAB);
  assert.deepEqual(state, { c: ['planning'] });
  assert.deepEqual(ignored, []);
});
