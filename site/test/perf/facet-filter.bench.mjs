// site/test/perf/facet-filter.bench.mjs -- P2-S4-T02 (08 S8.1 "Facet filter to result set", S5.7; 10 V11). The unit
// benchmark that holds the facet filter to 08 S8.1's blocking budget: < 50 ms at 1,500 entries, < 120 ms at 5,000.
//
//   cd site && node --test test/query.test.mjs test/perf/facet-filter.bench.mjs
//
// The corpus is synthetic and seeded, at the two sizes the budget names, over the real taxonomy (taxonomy/*.yaml, read
// as the site reads it): every rail term exists, rows carry values as facets.json format 2 spells them (an id a facet
// defines in two fields is `{field}:{id}`), so the index holds as many sets as a real build's would. What is timed is
// the work a filter change does before rendering:
//
//   view       lib/browse-view.ts tally(): the result list and every rail term's count, plus mostConstraining() when
//              nothing matches, which is what the island (islands/FacetPanel.tsx) computes on each change;
//   pipeline   lib/query.ts run(): step 1's survivors over facets.json's values and ranges, as a result list, and the
//              same with a free-text query, which adds the BM25 leg and the fusion.
//
// Each case is run WARMUP times untimed (the JIT's first compilations), then REPS times timed, and the assertion is on
// the median, so a garbage-collection pause or a scheduler hiccup in a few runs cannot fail it.
//
// The caveat. These are wall-clock milliseconds on whatever machine runs the test, so the number is not
// machine-independent: a slower or busier machine measures more. Two things keep that from making the check flaky.
// The budget is 08 S8.1's whole filter-to-repaint allowance, DOM work included ("the query is the fast part and the DOM
// is the slow part"), while this times the query alone, which 08 S5.7 expects well under a millisecond at 1,500 rows --
// orders of magnitude of headroom, which the medians in the diagnostics show. And the median of REPS runs is robust to
// outliers. So a failure here means an algorithmic regression (a pass over the rows per term, say), not noise; if it
// fails on a loaded machine with the code unchanged, rerun it before believing it. The DOM half of the budget cannot be
// measured under Node: 08 S8.2's advisory Playwright run ("Browse/search first result") is where it is watched.
// The semantic re-rank budget (< 30 ms) has nothing to time until Phase 6 builds the semantic leg.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { buildIndex, mostConstraining, railGroups, tally } from '../../src/lib/browse-view.ts';
import { buildPipeline, run } from '../../src/lib/query.ts';
import { allTerms } from '../../src/lib/terms.ts';

const ROOT = fileURLToPath(new URL('../../../', import.meta.url));

/** 08 S8.1: facet filter to result set, in ms, by corpus size. */
const BUDGET_MS = { 1500: 50, 5000: 120 };
const WARMUP = 25;
const REPS = 101;

// ---- the synthetic corpus ---------------------------------------------------------------------------------------

function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// tools/build/emit.py FLAT_FACETS: the vocabulary files with a facet of their own that fold into one of the seven, and
// the derived field no build stage computes yet (it contributes nothing)
const FOLD = { ceiling_anchor_type: 'data_properties', maintenance_status: 'lifecycle' };
const NOT_YET_DERIVED = new Set(['maintenance_status']);
// the fields a record may carry several values of; every other field holds one
const MANY = new Set(['capability', 'evaluation_method', 'subject', 'governance.independence_flags', 'execution.reproducibility_blockers']);
const WORDS = ['agent', 'bench', 'code', 'math', 'proof', 'vision', 'robot', 'web', 'chem', 'protein', 'climate', 'legal',
  'medical', 'speech', 'arena', 'reasoning', 'tool', 'planning', 'long', 'context', 'multilingual', 'safety', 'game', 'world'];

function corpus(n, terms, seed) {
  const rnd = seeded(seed);
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  // flat facet -> field -> term ids, and which ids the facet defines in more than one field (emit.py term_keys)
  const fields = new Map();
  for (const t of terms) {
    if (t.facet === 'domain' || NOT_YET_DERIVED.has(t.facet)) continue;
    const flat = FOLD[t.facet] ?? t.facet;
    const field = t.field ?? t.facet;
    if (!fields.has(flat)) fields.set(flat, new Map());
    if (!fields.get(flat).has(field)) fields.get(flat).set(field, []);
    fields.get(flat).get(field).push(t.id);
  }
  const spell = new Map([...fields].map(([flat, byField]) => {
    const seen = new Map();
    for (const [field, idsOf] of byField) for (const id of idsOf) seen.set(id, (seen.get(id) ?? 0) + 1);
    return [flat, (field, id) => (seen.get(id) > 1 ? `${field}:${id}` : id)];
  }));
  const subdomains = terms.filter((t) => t.facet === 'domain' && t.parent != null);
  return Array.from({ length: n }, (_, i) => {
    const sub = pick(subdomains);
    const facets = {};
    for (const [flat, byField] of fields) {
      const values = new Set();
      for (const [field, idsOf] of byField) {
        const k = MANY.has(field) ? 1 + Math.floor(rnd() * 3) : 1;
        for (let j = 0; j < k; j++) values.add(spell.get(flat)(field, pick(idsOf)));
      }
      facets[flat] = [...values];
    }
    return {
      id: `bench-${i}`, slug: `bench-${i}`, name: `${pick(WORDS)} ${pick(WORDS)} ${i}`, aliases: rnd() < 0.3 ? [`${pick(WORDS)}-${i}`] : [],
      domain: sub.parent, subdomain: sub.id, facets, year: rnd() < 0.05 ? null : 2000 + Math.floor(rnd() * 27),
      lifecycle: 'active', verification_max: null, condition_completeness_max: null, claim_count: 0,
      headroom: rnd() < 0.3 ? null : Math.round(rnd() * 100) / 100,
    };
  });
}

// ---- timing -------------------------------------------------------------------------------------------------------

function median(fn) {
  for (let i = 0; i < WARMUP; i++) fn();
  const times = [];
  for (let i = 0; i < REPS; i++) {
    const t0 = performance.now();
    fn();
    times.push(performance.now() - t0);
  }
  times.sort((a, b) => a - b);
  return times[(REPS - 1) / 2];
}

const TERMS = allTerms(ROOT);
const GROUPS = railGroups(TERMS);
const termOf = (key, i) => {
  const g = GROUPS.find((x) => x.key === key);
  const pool = g.terms.filter((t) => t.parent == null);    // a family, for the domain group
  return pool[i % pool.length].id;
};

// what a session does: nothing, one term, an OR within a facet ANDed with another, the domain spine with a year range,
// a five-facet intersection around one entry (so it has a result), and nine facets with a year range no row has (the
// synthetic years run 2000-2026), so nothing matches and the empty state's mostConstraining() runs a tally per filter
const viewCases = (rows) => {
  const r = rows.find((x) => x.year != null);
  return {
    'no filter': {},
    'one capability': { c: [termOf('c', 0)] },
    'two capabilities and a method': { c: [termOf('c', 1), termOf('c', 2)], em: [termOf('em', 0)] },
    'two families, a year range, an access term': { d: [termOf('d', 0), termOf('d', 3)], yr: '2015-2024', acc: [termOf('acc', 0)] },
    'five facets and a year range': { d: [r.domain], c: [r.facets.capability[0]], em: [r.facets.evaluation_method[0]], s: [r.facets.subject[0]], yr: `${r.year}-${r.year}` },
    'nothing matches': { c: [termOf('c', 4)], em: [termOf('em', 2)], s: [termOf('s', 1)], lc: [termOf('lc', 1)], acc: [termOf('acc', 1)], mt: [termOf('mt', 0)], sp: [termOf('sp', 0)], ct: [termOf('ct', 1)], rt: [termOf('rt', 0)], yr: '1990-1995' },
  };
};

const change = (index, state) => {
  const t = tally(index, state);
  return t.total === 0 && index.rows.length > 0 ? mostConstraining(index, state) : t;
};

for (const n of [1500, 5000]) {
  const budget = BUDGET_MS[n];
  const rows = corpus(n, TERMS, n);

  test(`the browse view's filter change is under ${budget} ms at ${n.toLocaleString('en')} entries (08 S8.1), median of ${REPS}`, (t) => {
    const t0 = performance.now();
    const index = buildIndex(GROUPS, rows);
    t.diagnostic(`index built once in ${(performance.now() - t0).toFixed(2)} ms: ${[...index.facets.values.values()].reduce((s, m) => s + m.size, 0)} value sets of ${index.facets.words * 4} bytes`);
    const cases = viewCases(rows);
    assert.ok(tally(index, cases['five facets and a year range']).total > 0, 'the five-facet case has a result');
    assert.equal(tally(index, cases['nothing matches']).total, 0, 'the empty case matches nothing');
    for (const [name, state] of Object.entries(cases)) {
      const ms = median(() => change(index, state));
      t.diagnostic(`${name}: ${tally(index, state).total} results, median ${ms.toFixed(3)} ms`);
      assert.ok(ms < budget, `${name}: median ${ms.toFixed(2)} ms at ${n} entries, budget ${budget} ms`);
    }
  });

  test(`the query pipeline's result set is under ${budget} ms at ${n.toLocaleString('en')} entries (08 S8.1), median of ${REPS}`, (t) => {
    const t0 = performance.now();
    const pipeline = buildPipeline(rows);
    t.diagnostic(`pipeline (bitsets and text index) built once in ${(performance.now() - t0).toFixed(2)} ms`);
    const cap = rows[0].facets.capability[0];
    const method = rows[1].facets.evaluation_method[0];
    const cases = {
      'facets and ranges': { facets: { capability: [cap, rows[2].facets.capability[0]], evaluation_method: [method] }, ranges: { year: [2010, 2024], headroom: [0.2, 0.9] } },
      'facets and free text': { facets: { capability: [cap] }, text: `${WORDS[0]} ${WORDS[5]}` },
      'free text alone': { text: 'bench' },
    };
    for (const [name, q] of Object.entries(cases)) {
      const ms = median(() => run(pipeline, q).rows);
      t.diagnostic(`${name}: ${run(pipeline, q).rows.length} results, median ${ms.toFixed(3)} ms`);
      assert.ok(ms < budget, `${name}: median ${ms.toFixed(2)} ms at ${n} entries, budget ${budget} ms`);
    }
  });
}
