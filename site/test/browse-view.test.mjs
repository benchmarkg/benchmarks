// site/test/browse-view.test.mjs -- P2-S4-T04 (10 V11 "The filter panel"; 08 S5.7, S8.1; 09 S6.10, S8.4). The browse
// view's logic, src/lib/browse-view.ts, which islands/FacetPanel.tsx renders and Node loads as it is, stripping its
// types:
//
//   cd site && node --test test/browse-view.test.mjs
//
// Counts are live: every term's count is recomputed from facets.json rows on every change, AND across facets and OR
// within one, a term's own facet left out of its count. Zero-count terms stay in their group. Chips are one per applied
// filter, each removable alone. The status region's sentence and debounce are 09 S8.4's. The curation-confidence scope
// follows the domain filter. And over the taxonomy as it stands, the rail offers every term of every vocabulary the
// grammar has a key for; over facets.json and enums.json as the emitter wrote them, when a build left them beside the
// corpus, every count equals one computed here from enums.json's `key`, the spelling the emitter writes.
//
// The browser half -- the island fetching the hashed facets.json, disabled checkboxes, the chip row, the one status
// region, the hover definitions -- is tests/browse.spec.ts (Playwright).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  ANNOUNCE_MS, FACETS_FORMAT, RAIL, UNAPPLIED, announcement, browseHref, buildIndex, chips, cleared, confidence,
  mostConstraining, railGroups, readFacets, tally, termHref, toggle, unapplied, vocabularies, without,
} from '../src/lib/browse-view.ts';
import { TERM_KEYS, decode, encode } from '../src/lib/filter-url.ts';
import { allTerms } from '../src/lib/terms.ts';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const ROOT = join(SITE, '..');

// ---- a small world, so every count can be checked by eye -----------------------------------------------------

const TERMS = [
  { facet: 'domain', id: 'code', label: 'Code', definition: 'Software.' },
  { facet: 'domain', id: 'code/repo', label: 'Repository-scale', definition: 'Whole repos.', parent: 'code' },
  { facet: 'domain', id: 'code/snippet', label: 'Snippets', definition: 'Small functions.', parent: 'code' },
  { facet: 'domain', id: 'maths', label: 'Mathematics', definition: 'Proofs and   problems.' },
  { facet: 'domain', id: 'maths/olympiad', label: 'Olympiad', definition: 'Contest maths.', parent: 'maths' },
  { facet: 'capability', id: 'planning', label: 'Planning', definition: 'Plans.' },
  { facet: 'capability', id: 'tool-use', label: 'Tool use', definition: 'Tools.' },
  { facet: 'capability', id: 'proof', label: 'Proof', definition: 'Proving.' },
  { facet: 'capability', id: 'unmeasured', label: 'Unmeasured', definition: 'Nobody measures it.' },
  { facet: 'evaluation_method', id: 'execution-tests', label: 'Execution tests', definition: 'Run it.' },
  { facet: 'evaluation_method', id: 'judge', label: 'Judge', definition: 'A model grades it.' },
  { facet: 'subject', id: 'llm', label: 'LLM', definition: 'A language model.' },
  { facet: 'lifecycle', field: 'lifecycle', id: 'active', label: 'Active', definition: 'In use.' },
  { facet: 'lifecycle', field: 'lifecycle', id: 'saturated', label: 'Saturated', definition: 'Solved.' },
  { facet: 'lifecycle', field: 'activity', id: 'busy', label: 'Busy', definition: 'An activity term.' },
  { facet: 'data_properties', field: 'data.access', id: 'open', label: 'Open', definition: 'Public.' },
  { facet: 'data_properties', field: 'data.access', id: 'gated', label: 'Gated', definition: 'Behind a form.' },
  { facet: 'data_properties', field: 'data.refresh', id: 'static', label: 'Static', definition: 'Never refreshed.' },
  { facet: 'governance', field: 'governance.maintainer_type', id: 'academic', label: 'Academic', definition: 'A lab.' },
  { facet: 'governance', field: 'governance.submission_process', id: 'open-pr', label: 'Open PR', definition: 'Anyone.' },
  { facet: 'execution', field: 'execution.compute_tier', id: 'wet-lab', label: 'Wet lab', definition: 'A lab bench.' },
  { facet: 'execution', field: 'execution.compute_tier', id: 'laptop', label: 'Laptop', definition: 'Small.' },
  { facet: 'execution', field: 'execution.reproducibility_blockers', id: 'wet-lab', label: 'Wet lab', definition: 'Blocker.' },
  { facet: 'execution', field: 'execution.reproducibility_tier', id: 'scripted', label: 'Scripted', definition: 'One command.' },
];

const row = (id, name, over = {}) => ({
  id, slug: id, name, aliases: [], domain: 'code', subdomain: 'code/repo', year: 2024, lifecycle: 'active',
  verification_max: null, condition_completeness_max: null, claim_count: 0, headroom: null,
  ...over,
  facets: { capability: [], evaluation_method: [], subject: ['llm'], data_properties: [], lifecycle: ['active'],
    governance: [], execution: [], ...(over.facets ?? {}) },
});

// wet-lab is two terms of execution, so the emitter writes both qualified: `{field}:{id}`
const ROWS = [
  row('swe', 'SWE', { facets: { capability: ['planning', 'tool-use'], evaluation_method: ['execution-tests'], data_properties: ['open', 'static'],
    execution: ['execution.compute_tier:wet-lab'] } }),
  row('humaneval', 'HumanEval', { subdomain: 'code/snippet', year: 2021, facets: { capability: ['tool-use'], evaluation_method: ['execution-tests'],
    data_properties: ['open'], execution: ['laptop', 'execution.reproducibility_blockers:wet-lab'] } }),
  row('mt-bench', 'MT-Bench', { year: null, lifecycle: 'saturated', facets: { capability: ['planning'], evaluation_method: ['judge'],
    data_properties: ['gated'], lifecycle: ['saturated', 'busy'] } }),
  row('imo', 'IMO', { domain: 'maths', subdomain: 'maths/olympiad', year: 2025, facets: { capability: ['proof', 'planning'],
    evaluation_method: ['judge'], governance: ['academic'] } }),
];

const GROUPS = railGroups(TERMS);
const gi = (key) => GROUPS.findIndex((g) => g.key === key);
const count = (t, key, id) => t.counts[gi(key)].get(id) ?? 0;
const names = (index, t) => t.matches.map((i) => index.rows[i].id);

test('the rail is one group per term key of the grammar but the basket, in RAIL order', () => {
  assert.deepEqual(GROUPS.map((g) => g.key), ['d', 'c', 'em', 's', 'lc', 'acc', 'mt', 'sp', 'ct', 'rt']);
  assert.deepEqual(RAIL.map((g) => g.key).sort(), Object.keys(TERM_KEYS).filter((k) => k !== 'b').sort());
  // a field of a facet with several fields offers its own terms only, and browses under the field
  const lc = GROUPS[gi('lc')];
  assert.deepEqual(lc.terms.map((t) => t.id), ['active', 'saturated']);
  assert.equal(browseHref(lc, 'active'), '/browse/lifecycle/active/');
  assert.equal(browseHref(GROUPS[gi('acc')], 'open'), '/browse/access/open/');
  assert.equal(termHref(GROUPS[gi('acc')], 'open'), '/taxonomy/data-properties/open/');
  assert.equal(browseHref(GROUPS[gi('d')], 'code/repo'), '/browse/domain/code/repo/');
  assert.equal(GROUPS[gi('d')].terms.find((t) => t.id === 'maths').gloss, 'Proofs and problems.');
  assert.throws(() => railGroups(TERMS.filter((t) => t.facet !== 'subject')), /browse rail s: taxonomy\/ has no subject term/);
});

test('with no filter every row matches, sorted by name, and every term counts the rows that carry it', () => {
  const index = buildIndex(GROUPS, ROWS);
  const t = tally(index, {});
  assert.deepEqual(names(index, t), ['humaneval', 'imo', 'mt-bench', 'swe']);
  assert.equal(count(t, 'c', 'planning'), 3);
  assert.equal(count(t, 'c', 'unmeasured'), 0);              // the gap: a zero, not an absent group
  assert.equal(count(t, 'd', 'code'), 3);
  assert.equal(count(t, 'd', 'code/snippet'), 1);
  assert.equal(count(t, 'lc', 'saturated'), 1);
  assert.equal(count(t, 'lc', 'busy'), 0, 'an activity term is not a lifecycle term');
});

test('AND across facets, OR within one, and a term\'s own facet is left out of its count', () => {
  const index = buildIndex(GROUPS, ROWS);
  const one = tally(index, { c: ['planning'] });
  assert.deepEqual(names(index, one), ['imo', 'mt-bench', 'swe']);
  // the capability counts ignore the capability selection: what each term would give as the only one
  assert.equal(count(one, 'c', 'tool-use'), 2);
  assert.equal(count(one, 'c', 'proof'), 1);
  // every other facet counts within the selection
  assert.equal(count(one, 'em', 'execution-tests'), 1);
  assert.equal(count(one, 'em', 'judge'), 2);
  assert.equal(count(one, 'd', 'code/snippet'), 0, 'HumanEval carries no planning');

  const or = tally(index, { c: ['planning', 'tool-use'] });
  assert.equal(or.total, 4);

  const and = tally(index, { c: ['planning'], em: ['judge'] });
  assert.deepEqual(names(index, and), ['imo', 'mt-bench']);
  assert.equal(count(and, 'em', 'execution-tests'), 1, 'em counts keep c, not em');
  assert.equal(count(and, 'c', 'tool-use'), 0, 'c counts keep em, not c');
  assert.equal(count(and, 'acc', 'gated'), 1);
});

test('a domain family matches its subdomains, a subdomain only itself; the family and a subdomain together are an OR', () => {
  const index = buildIndex(GROUPS, ROWS);
  assert.deepEqual(names(index, tally(index, { d: ['code'] })), ['humaneval', 'mt-bench', 'swe']);
  assert.deepEqual(names(index, tally(index, { d: ['code/snippet'] })), ['humaneval']);
  assert.deepEqual(names(index, tally(index, { d: ['code/snippet', 'maths'] })), ['humaneval', 'imo']);
  assert.equal(tally(index, { d: ['code', 'code/repo'] }).total, 3);
});

test('a value the emitter qualifies, {field}:{id}, joins to its own field\'s term and to no other', () => {
  const index = buildIndex(GROUPS, ROWS);
  const t = tally(index, {});
  assert.equal(count(t, 'ct', 'wet-lab'), 1, 'only SWE has wet-lab as its compute tier');
  assert.deepEqual(names(index, tally(index, { ct: ['wet-lab'] })), ['swe']);
  assert.equal(count(t, 'ct', 'laptop'), 1);
  assert.equal(count(t, 'acc', 'open'), 2, 'a data_properties array mixes fields; refresh `static` is not an access term');
});

test('the release-year range is inclusive, and a row with no year is outside every range', () => {
  const index = buildIndex(GROUPS, ROWS);
  assert.deepEqual(names(index, tally(index, { yr: '2021-2024' })), ['humaneval', 'swe']);
  assert.equal(tally(index, { yr: '1900-2100' }).total, 3, 'MT-Bench records no year');
  assert.equal(count(tally(index, { yr: '2025-2025' }), 'c', 'planning'), 1);
});

test('no published row: every count is zero and nothing matches, whatever the selection', () => {
  const index = buildIndex(GROUPS, []);
  for (const state of [{}, { c: ['planning'] }]) {
    const t = tally(index, state);
    assert.equal(t.total, 0);
    for (const m of t.counts) assert.equal(m.size, 0);
  }
});

test('chips: one per applied filter, in rail order, each removable alone; the keys the view keeps are untouched', () => {
  const state = decode('c=tool-use,planning&d=code&em=judge&q=bimanual&sort=headroom&yr=2020-2025&hr=0.0-0.8', vocabularies(GROUPS)).state;
  const cs = chips(GROUPS, state);
  assert.deepEqual(cs.map((c) => `${c.key}=${c.value}`), ['d=code', 'c=planning', 'c=tool-use', 'em=judge', 'yr=2020-2025']);
  assert.deepEqual(cs.map((c) => `${c.group}: ${c.label}`).slice(0, 4), ['Domain: Code', 'Capability: Planning', 'Capability: Tool use', 'Evaluation method: Judge']);
  // remove each chip alone: exactly that one goes, and the URL is the canonical one for what is left
  for (const c of cs) {
    const after = chips(GROUPS, without(state, c)).map((x) => `${x.key}=${x.value}`);
    assert.deepEqual(after, cs.filter((x) => x !== c).map((x) => `${x.key}=${x.value}`), `${c.key}=${c.value}`);
    assert.equal(encode(without(state, c)), encode(decode(encode(without(state, c))).state));
  }
  assert.equal(encode(without(state, cs[1])), 'c=tool-use&d=code&em=judge&hr=0.0-0.8&q=bimanual&sort=headroom&yr=2020-2025&v=1');
  assert.equal(encode(cleared(state, GROUPS)), 'hr=0.0-0.8&q=bimanual&sort=headroom&v=1');
  assert.deepEqual(unapplied(state), [{ key: 'hr', value: '0.0-0.8' }, { key: 'q', value: 'bimanual' }, { key: 'sort', value: 'headroom' }]);
  assert.deepEqual([...UNAPPLIED].sort(), ['b', 'hr', 'q', 'sort', 'ver']);
});

test('toggle adds a value, removes it again, and drops a key left empty', () => {
  const a = toggle({}, 'c', 'planning');
  assert.deepEqual(a, { c: ['planning'] });
  assert.deepEqual(toggle(a, 'c', 'tool-use'), { c: ['planning', 'tool-use'] });
  assert.deepEqual(toggle(a, 'c', 'planning'), {});
  assert.equal(encode(toggle(toggle({}, 'c', 'tool-use'), 'c', 'planning')), encode(toggle(toggle({}, 'c', 'planning'), 'c', 'tool-use')));
});

test('the filter empty-state offers the filter whose removal returns the most results (09 S6.10)', () => {
  const index = buildIndex(GROUPS, ROWS);
  const state = { c: ['proof'], em: ['execution-tests'], acc: ['open'] };
  assert.equal(tally(index, state).total, 0);
  const best = mostConstraining(index, state);
  assert.equal(`${best.chip.key}=${best.chip.value}`, 'c=proof');
  assert.equal(best.results, 2);
  assert.equal(mostConstraining(index, {}), null);
});

test('the status region says one sentence, and waits 500 ms for the last change (09 S8.4)', () => {
  assert.equal(announcement(312), '312 benchmarks match');
  assert.equal(announcement(1), '1 benchmark matches');
  assert.equal(announcement(0), 'No benchmark matches');
  assert.equal(ANNOUNCE_MS, 500);
});

test('curation confidence covers the filtered domain\'s families, or every family when the domain is unfiltered', () => {
  const families = [
    { id: 'code', label: 'Code', signoff: 'none' },
    { id: 'maths', label: 'Mathematics', signoff: 'domain-expert' },
  ];
  assert.deepEqual(confidence(families, {}), { scope: 'all', families, signed: [families[1]], state: 'partly-reviewed' });
  assert.equal(confidence(families, { d: ['code/repo'] }).state, 'unreviewed', 'a subdomain counts its family');
  assert.deepEqual(confidence(families, { d: ['maths'] }).families.map((f) => f.id), ['maths']);
  assert.equal(confidence(families, { d: ['maths'] }).state, 'reviewed');
  assert.equal(confidence(families.slice(0, 1), {}).state, 'unreviewed');
});

test('readFacets reads format 3 and says why it reads nothing else', () => {
  assert.equal(FACETS_FORMAT, 3);
  assert.deepEqual(readFacets({ artifact: 'facets', format: FACETS_FORMAT, benchmarks: ROWS, drafts: true }), { rows: ROWS, drafts: true });
  assert.match(readFacets({ artifact: 'facets', format: 2, benchmarks: [] }).error, /format 2, and this view reads format 3/);
  assert.match(readFacets({ artifact: 'corpus', format: 1 }).error, /not the facets artifact/);
  assert.match(readFacets(null).error, /not the facets artifact/);
});

test('a full recount over 1,500 rows is inside 08 S8.1\'s 50 ms filter budget', () => {
  const caps = GROUPS[gi('c')].terms.map((t) => t.id);
  const many = Array.from({ length: 1500 }, (_, i) => row(`b-${i}`, `Bench ${i}`, {
    subdomain: i % 2 ? 'code/repo' : 'code/snippet', year: 2015 + (i % 11),
    facets: { capability: [caps[i % caps.length], caps[(i * 7) % caps.length]], evaluation_method: [i % 3 ? 'judge' : 'execution-tests'] },
  }));
  const index = buildIndex(GROUPS, many);
  const state = { c: ['planning', 'proof'], em: ['judge'], yr: '2018-2024' };
  const times = [];
  for (let i = 0; i < 25; i++) {
    const t0 = performance.now();
    tally(index, state);
    times.push(performance.now() - t0);
  }
  times.sort((a, b) => a - b);
  assert.ok(times[12] < 50, `median recount ${times[12].toFixed(2)} ms`);
});

// ---- the taxonomy as it stands, and the artifacts a build left ------------------------------------------------

test('over taxonomy/, the rail offers every term of every vocabulary the grammar has a key for', () => {
  const terms = allTerms(ROOT);
  const groups = railGroups(terms);
  const size = (facet, field) => terms.filter((t) => t.facet === facet && (field == null || t.field === field)).length;
  for (const g of groups) assert.equal(g.terms.length, size(g.facet, g.field), g.key);
  assert.equal(groups[0].terms.filter((t) => t.parent == null).length, 19, 'the nineteen domain families');
  // decode() accepts every rail term and nothing else
  const vocab = vocabularies(groups);
  const d = decode('c=nonexistent-term&em=' + groups[2].terms[0].id, vocab);
  assert.deepEqual(d.ignored, [{ key: 'c', value: 'nonexistent-term' }]);
  assert.deepEqual(d.state, { em: [groups[2].terms[0].id] });
});

// the artifacts beside the corpus the site reads (UAIBI_CORPUS, else build/corpus.json), as src/lib/corpus.ts finds it
const CORPUS = process.env.UAIBI_CORPUS ? resolve(SITE, process.env.UAIBI_CORPUS) : join(ROOT, 'build', 'corpus.json');
const BESIDE = ['facets.json', 'enums.json'].map((f) => join(dirname(CORPUS), f));
const built = BESIDE.every((p) => existsSync(p));

test('over the emitter\'s facets.json, every count equals one computed from enums.json\'s keys', { skip: !built && `no facets.json and enums.json beside ${CORPUS}: run \`uv run bench build\`` }, () => {
  const [facets, enums] = BESIDE.map((p) => JSON.parse(readFileSync(p, 'utf8')));
  const got = readFacets(facets);
  assert.ok(!('error' in got), got.error);
  const groups = railGroups(allTerms(ROOT));
  const index = buildIndex(groups, got.rows);
  const flatOf = new Map(Object.entries(enums.flat_facets).flatMap(([flat, d]) => d.vocabularies.map((v) => [v, flat])));
  // a term's members, the way test/browse-routes.test.mjs computes them: the rows whose array holds its enums.json key
  const carries = (g, t) => {
    if (g.key === 'd') return (r) => (t.parent == null ? r.domain === t.id : r.subdomain === t.id);
    const key = enums.vocabularies[g.facet].terms.find((x) => x.id === t.id && (x.field ?? null) === g.field)?.key;
    assert.ok(key != null, `enums.json places no ${g.facet}:${g.field}:${t.id}`);
    const flat = flatOf.get(g.facet);
    return (r) => r.facets[flat].includes(key);
  };
  const preds = groups.map((g) => new Map(g.terms.map((t) => [t.id, carries(g, t)])));
  const check = (state) => {
    const t = tally(index, state);
    const [lo, hi] = (state.yr ?? '-Infinity--Infinity').split(/(?<=\d)-/).map(Number);
    const inYears = (r) => state.yr == null || (r.year != null && r.year >= lo && r.year <= hi);
    const passes = (r, skip) => inYears(r)
      && groups.every((g, i) => i === skip || !(state[g.key]?.length) || state[g.key].some((id) => preds[i].get(id)(r)));
    assert.equal(t.total, got.rows.filter((r) => passes(r, -1)).length, JSON.stringify(state));
    groups.forEach((g, i) => {
      for (const term of g.terms) {
        const want = got.rows.filter((r) => passes(r, i) && preds[i].get(term.id)(r)).length;
        assert.equal(t.counts[i].get(term.id) ?? 0, want, `${JSON.stringify(state)}: ${g.key}=${term.id}`);
      }
    });
  };
  check({});
  if (got.rows.length > 0) {
    // the broadest capability, and then the broadest evaluation method within it
    const first = tally(index, {});
    const top = (gk, t) => [...t.counts[groups.findIndex((g) => g.key === gk)].entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    const c = top('c', first);
    assert.ok(c != null, 'no published row carries a capability');
    check({ c: [c] });
    const em = top('em', tally(index, { c: [c] }));
    const narrower = em != null ? { c: [c], em: [em] } : { c: [c] };
    check(narrower);
    check({ ...narrower, d: [got.rows[0].domain] });
    check({ d: [got.rows[0].subdomain], yr: '2020-2026' });
  }
});

test('the page names facets.json only through dataHref(), and neither it nor the island writes a /data/ URL', () => {
  const page = readFileSync(join(SITE, 'src', 'pages', 'benchmarks', 'index.astro'), 'utf8');
  const island = readFileSync(join(SITE, 'src', 'islands', 'FacetPanel.tsx'), 'utf8');
  assert.match(page, /dataHref\('facets\.json'\)/);
  assert.match(page, /<FacetPanel client:load facetsHref=\{facetsHref\}/);
  for (const [name, text] of [['index.astro', page], ['FacetPanel.tsx', island]]) {
    assert.doesNotMatch(text.replace(/^\s*\/\/.*$/gm, ''), /['"`]\/data\//, `${name} writes a /data/ URL by hand`);
  }
  // 09 S8.4: one status region, and nothing live on the results
  assert.equal(island.match(/role="status"/g)?.length, 1);
  assert.doesNotMatch(island, /aria-live/);
});
