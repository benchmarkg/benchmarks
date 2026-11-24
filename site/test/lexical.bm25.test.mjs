// site/test/lexical.bm25.test.mjs -- P6-S1-T04 (11 S4 "The pipeline", step 2; 08 S5.5, S5.7). The BM25 leg,
// src/islands/search/lexical.ts, loaded by Node as it is, stripping its types:
//
//   cd site && npm test -- lexical.bm25      # the verify: `npm test` runs every test/*.test.mjs, this file among them
//   cd site && node --test test/lexical.bm25.test.mjs
//
// Done when: "The frozen fixture returns a stable ranked id list and MiniSearch exposes BM25 scores to the fusion step."
// The fixture, test/fixtures/lexical-bm25.json, is 34 rows of the 2026-11-24 draft preview's facets.json (format 3) as
// the leg reads them -- id, name, aliases, editions -- and eighteen queries, each with its expected ranked list and the
// BM25+ score of every entry, frozen when this task wrote the leg and each one's `why` saying what it shows: the exact
// name over a near one, acronyms one edit apart kept apart, edition names finding their family, no fuzzy match on a
// digit, a typo found, diacritics folded, the survivors restricting without rescoring. A change to a boost, a fuzzy rule
// or a BM25 parameter moves a score here, so it is a visible change to this file, not a silent one.
//
// Also held: the configuration's documented values; that the list is the same over 100 fresh indexes; that every name,
// alias, edition name and id of every fixture row, as a query, puts its row first; the fuzzy and prefix rules on rows
// made here; that the scores are what lib/query.ts's fusion reads; and that this module is the only one in src/ that
// imports MiniSearch, so there is one BM25 implementation.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  BM25_PARAMS, BOOST, EXACT_BOOST, FUZZY, FUZZY_MIN_LENGTH, FUZZY_WEIGHT, LEXICAL_FIELDS, MAX_FUZZY, PREFIX_WEIGHT, bm25,
  buildLexicalIndex, fuzziness, normalise, phrase,
} from '../src/islands/search/lexical.ts';
import { add, fullSet, wordsFor } from '../src/lib/facet-index.ts';
import { FACETS_FORMAT } from '../src/lib/browse-view.ts';
import { RRF_K, rrf } from '../src/lib/query.ts';

const SRC = fileURLToPath(new URL('../src/', import.meta.url));
const FIXTURE = JSON.parse(readFileSync(new URL('./fixtures/lexical-bm25.json', import.meta.url), 'utf8'));
const ROWS = FIXTURE.rows;
const AT = new Map(ROWS.map((r, i) => [r.id, i]));

/** The fixture's survivors as a set over its rows. */
function setOf(ids) {
  const s = new Uint32Array(wordsFor(ROWS.length));
  for (const id of ids) add(s, AT.get(id));
  return s;
}

const ranked = (index, q) => bm25(index, q.q, q.survivors ? setOf(q.survivors) : undefined)
  .map((r) => [ROWS[r.row].id, Number(r.score.toFixed(4))]);

// ---- the frozen fixture -----------------------------------------------------------------------------------------

test('lexical.bm25: the fixture is facets.json format 3\'s text fields, and its queries say why', () => {
  assert.equal(FACETS_FORMAT, 3);
  assert.match(FIXTURE.rows_from, /facets\.json format 3/);
  assert.equal(ROWS.length, 34);
  for (const r of ROWS) {
    assert.deepEqual(Object.keys(r), ['id', 'name', 'aliases', 'editions'], r.id);
    assert.ok(typeof r.name === 'string' && Array.isArray(r.aliases) && Array.isArray(r.editions), r.id);
  }
  const ids = ROWS.map((r) => r.id);
  assert.deepEqual(ids, [...ids].sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b))), 'id byte order, as facets.json');
  assert.equal(FIXTURE.queries.length, 18);
  for (const q of FIXTURE.queries) assert.ok(q.why.length > 20, q.q);
});

test('lexical.bm25: the frozen fixture returns its ranked id lists and scores', () => {
  const index = buildLexicalIndex(ROWS);
  for (const q of FIXTURE.queries) {
    assert.deepEqual(ranked(index, q), q.ranked, `${JSON.stringify(q.q)}${q.survivors ? ` within ${q.survivors}` : ''}: ${q.why}`);
  }
  // the lists the docstring names, by eye
  const top = (q) => FIXTURE.queries.find((x) => x.q === q && !x.survivors).ranked.map(([id]) => id);
  assert.deepEqual(top('mmlu'), ['mmlu', 'mmlu-pro']);
  assert.deepEqual(top('MMMU'), ['mmmu', 'mmmu-pro']);
  assert.deepEqual(top('hle'), ['hle']);
  assert.equal(top('CASP16')[0], 'casp');
  assert.deepEqual(top('WMT23'), ['wmt-general-mt']);
  assert.deepEqual(top('SWE-bench Verified').slice(0, 3), ['swe-bench-verified', 'swe-bench', 'swe-bench-pro']);
  assert.deepEqual(top('agentbnch'), ['agentbench']);
  assert.deepEqual(top('montreal'), ['ai-driving-olympics']);
  assert.deepEqual(top('qwxyz'), []);
  assert.deepEqual(top('   '), []);
});

test('lexical.bm25: the list is stable -- 100 fresh indexes over the fixture give the same bytes', () => {
  const once = JSON.stringify(FIXTURE.queries.map((q) => bm25(buildLexicalIndex(ROWS), q.q, q.survivors ? setOf(q.survivors) : undefined)));
  for (let i = 0; i < 100; i++) {
    const index = buildLexicalIndex(ROWS);
    assert.equal(JSON.stringify(FIXTURE.queries.map((q) => bm25(index, q.q, q.survivors ? setOf(q.survivors) : undefined))), once, `run ${i}`);
  }
});

test('lexical.bm25: the survivors restrict the list and do not rescore it', () => {
  const index = buildLexicalIndex(ROWS);
  const q = FIXTURE.queries.find((x) => x.survivors);
  const all = new Map(ranked(index, { q: q.q }));
  assert.ok(q.ranked.length > 0 && q.ranked.length < all.size);
  for (const [id, score] of q.ranked) assert.equal(score, all.get(id), id);
  assert.deepEqual(bm25(index, q.q, fullSet(ROWS.length)), bm25(index, q.q), 'every row surviving is no restriction');
  assert.deepEqual(bm25(index, q.q, new Uint32Array(wordsFor(ROWS.length))), [], 'no survivor, no result');
});

test('lexical.bm25: every name, alias, edition name and id of every row, as a query, puts that row first', () => {
  const index = buildLexicalIndex(ROWS);
  const names = ROWS.map((r) => new Set([r.name, ...r.aliases, ...r.editions, r.id].map(phrase)));
  let n = 0;
  ROWS.forEach((r, row) => {
    for (const q of [r.name, ...r.aliases, ...r.editions, r.id]) {
      const list = bm25(index, q);
      const at = list.findIndex((x) => x.row === row);
      assert.ok(at >= 0, `${JSON.stringify(q)} does not find ${r.id}`);
      // only a row the same words also name may rank above it
      const above = list.slice(0, at).filter((x) => !names[x.row].has(phrase(q))).map((x) => ROWS[x.row].id);
      assert.deepEqual(above, [], `${JSON.stringify(q)}: ${r.id} is behind ${above}`);
      n++;
    }
  });
  assert.ok(n > 200, `${n} queries`);
});

// ---- the configuration ------------------------------------------------------------------------------------------

test('lexical.bm25: the fields, boosts, fuzzy rules and BM25+ parameters are the documented values', () => {
  assert.deepEqual([...LEXICAL_FIELDS], ['name', 'aliases', 'editions', 'id']);
  assert.deepEqual(BOOST, { name: 3, aliases: 2, editions: 1.5, id: 1 });
  assert.equal(EXACT_BOOST, 10);
  assert.deepEqual([FUZZY, FUZZY_MIN_LENGTH, MAX_FUZZY], [0.2, 5, 2]);
  assert.deepEqual([PREFIX_WEIGHT, FUZZY_WEIGHT], [0.375, 0.45]);
  assert.deepEqual(BM25_PARAMS, { k: 1.2, b: 0.7, d: 0.5 });
  // each value's reason is in the module docstring, read as prose (the `//` line breaks folded away)
  const prose = readFileSync(join(SRC, 'islands', 'search', 'lexical.ts'), 'utf8').replace(/\n\/\/ ?/g, ' ');
  for (const why of ['how directly the field names the row\'s benchmark', 'an order of magnitude',
    'a digit is an edition or a version', 'short acronyms one edit apart', 'the fraction MiniSearch itself uses',
    'MiniSearch\'s defaults, stated here so a release cannot move them']) assert.ok(prose.includes(why), why);
  // fuzziness per term: none below five characters or with a digit
  assert.equal(fuzziness('mmlu'), false);
  assert.equal(fuzziness('casp16'), false);
  assert.equal(fuzziness('wmt23'), false);
  assert.equal(fuzziness('bench'), FUZZY);
  assert.equal(fuzziness('agentbnch'), FUZZY);
  assert.equal(normalise('Montréal'), 'montreal');
  assert.equal(normalise('ÅNGSTRÖM'), 'angstrom');
  assert.equal(phrase('SWE-bench  Verified'), 'swe bench verified');
  assert.equal(phrase('τ-bench'), 'τ bench');
});

const row = (id, name, aliases = [], editions = []) => ({ id, name, aliases, editions });

test('lexical.bm25: prefix for every term; fuzzy only from five letters without a digit, one edit to seven, two from eight', () => {
  const rows = [
    row('mmlu', 'MMLU'), row('swe-lancer', 'SWE-Lancer'), row('agentbench', 'AgentBench'), row('casp', 'CASP', [], ['CASP16 (2024)']),
    row('kinetics', 'Kinetics'), row('olympics', 'LHC Olympics'), row('physionet', 'PhysioNet'),
  ];
  const index = buildLexicalIndex(rows);
  const found = (q) => bm25(index, q).map((r) => rows[r.row].id);
  assert.deepEqual(found('lanc'), ['swe-lancer'], 'a prefix');
  assert.deepEqual(found('mmmu'), [], 'four letters: never fuzzy');
  assert.deepEqual(found('casp15'), [], 'a digit: never fuzzy');
  assert.deepEqual(found('casp1'), ['casp'], 'but a prefix');
  assert.deepEqual(found('agentbnch'), ['agentbench'], 'nine letters, one edit');
  assert.deepEqual(found('kinetcs'), ['kinetics'], 'seven letters, one edit');
  assert.deepEqual(found('kintcs'), [], 'six letters, two edits: one is the most');
  assert.deepEqual(found('olympiad'), ['olympics'], 'eight letters, two edits');
  assert.deepEqual(found('phsyionat'), [], 'nine letters, three edits: two is the most');
  assert.deepEqual(found('PHYSIONET'), ['physionet'], 'case is folded');
  // an exact match outscores both near ones; of those, one edit (FUZZY_WEIGHT x 8 / 9 = 0.400) outscores a token one
  // letter longer (PREFIX_WEIGHT x 9 / 9.3 = 0.363), the weights MiniSearch gives them
  const three = [row('a', 'Kinetics'), row('b', 'Kineticsx'), row('c', 'Kinetica')];
  const list = bm25(buildLexicalIndex(three), 'kinetics');
  assert.deepEqual(list.map((r) => three[r.row].id), ['a', 'c', 'b']);
  const [, c, b] = list.map((r) => r.score);
  assert.ok(Math.abs(c / b - (FUZZY_WEIGHT * 8 / 9) / (PREFIX_WEIGHT * 9 / 9.3)) < 1e-9, 'the ratio is the weights\' alone');
});

test('lexical.bm25: equal scores are ordered by row number, not by id or by MiniSearch\'s map order', () => {
  const twins = [row('b', 'Alpha'), row('a', 'Alpha'), row('c', 'Alpha')];
  assert.deepEqual(bm25(buildLexicalIndex(twins), 'alpha').map((r) => r.row), [0, 1, 2]);
  const scores = bm25(buildLexicalIndex(twins), 'alpha').map((r) => r.score);
  assert.ok(scores.every((s) => s === scores[0]));
});

// ---- what the fusion step reads -----------------------------------------------------------------------------------

test('lexical.bm25: MiniSearch\'s BM25+ scores reach the fusion step, best first', () => {
  const index = buildLexicalIndex(ROWS);
  for (const q of FIXTURE.queries) {
    const list = bm25(index, q.q, q.survivors ? setOf(q.survivors) : undefined);
    assert.ok(list.every((r) => Number.isInteger(r.row) && Number.isFinite(r.score) && r.score > 0), q.q);
    assert.ok(list.every((r, i) => i === 0 || list[i - 1].score > r.score || (list[i - 1].score === r.score && list[i - 1].row < r.row)), q.q);
    // lib/query.ts fuses it at RRF k = 60; one list keeps its order, and each fused score is 1 / (60 + rank)
    const fused = rrf([list]);
    assert.deepEqual(fused.map((r) => r.row), list.map((r) => r.row), q.q);
    fused.forEach((r, i) => assert.equal(r.score, 1 / (RRF_K + i + 1)));
  }
  // the scores are BM25+ scores: a rarer word scores higher than a common one, other things equal
  const two = [row('x', 'Common Rare'), row('y', 'Common'), row('z', 'Common')];
  const i2 = buildLexicalIndex(two);
  assert.ok(bm25(i2, 'rare')[0].score > bm25(i2, 'common').find((r) => r.row === 0).score);
});

test('lexical.bm25: this is the one BM25 implementation -- nothing else in src/ imports MiniSearch', () => {
  const files = readdirSync(SRC, { recursive: true }).map(String).filter((f) => /\.(ts|tsx|astro|mjs|js)$/.test(f));
  const importers = files.filter((f) => /from\s+['"]minisearch['"]/.test(readFileSync(join(SRC, f), 'utf8')))
    .map((f) => f.split('\\').join('/'));
  assert.deepEqual(importers, ['islands/search/lexical.ts']);
  const query = readFileSync(join(SRC, 'lib', 'query.ts'), 'utf8');
  assert.match(query, /from '\.\.\/islands\/search\/lexical\.ts'/, 'lib/query.ts runs this leg');
});
