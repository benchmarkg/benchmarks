// site/test/suite.exclusions.test.mjs -- P6-S4-T03 (11 S2 F2 "Made visible"; 10 V10 "Failure mode to avoid"; 02 S11).
// src/islands/suite/exclusions.ts, the Suite Builder's hard exclusion rules and the one seam both ways of filling a
// basket go through, loaded by Node as it is, stripping its types:
//
//   cd site && npm test -- suite.exclusions    # the verify: npm passes `suite.exclusions` through to the script, so it
//                                              # runs `node --test "test/*.test.mjs" suite.exclusions`; node reads the
//                                              # extra argument as one more file pattern, which names no file and adds
//                                              # nothing, so this runs every test/*.test.mjs, this file among them
//   cd site && node --test test/suite.exclusions.test.mjs                    # this file alone
//
// Done when: "A fixture containing a deprecated and a licence-incompatible entry excludes both with visible reasons on
// both the manual and AI paths." The fixture is test/fixtures/suite-exclusions.json, synthetic records with the fields
// the rules read; fixture-deprecated and fixture-noncommercial are the pair. The manual path is the page's: Add pressed
// once per entry (lib/suite-basket.ts added()), or the basket's own link decoded. The AI accelerator is not built
// (P6-S5), so its path is called as P6-S5-T01 specifies its output, entry_ref integers into the retrieved array, which
// fill a starting basket (10 V10) at once. All three must reach the same screen() and come back with the same suite,
// the same exclusions and the same words. The browser half, the panel on /suite/ and on the fixture page, is
// tests/suite-exclusions.spec.ts.
//
// Also held: every rule fires on the field its header names and on nothing else (an entry's name or prose never
// counts); the use is `any` unless stated, and non-commercial research keeps a non-commercial licence but never a
// stated-purpose one; the licence patterns over the kinds of text the corpus holds; an entry whose licence cannot be
// read is kept and named, not cleared; the fact table keeps only what a rule can fire on; the module imports nothing;
// and the page builds the table and the island screens its basket through this module, once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { decode } from '../src/lib/filter-url.ts';
import { added, basketOf, suiteHref } from '../src/lib/suite-basket.ts';
import { RULES, factTable, factsOf, label, screen, summary, termsOf, unreadNote, why } from '../src/islands/suite/exclusions.ts';

const here = (p) => new URL(p, import.meta.url);
const FIXTURE = JSON.parse(readFileSync(here('./fixtures/suite-exclusions.json'), 'utf8')).entries;
const TABLE = factTable(FIXTURE);
const NAME = new Map(FIXTURE.map((e) => [e.id, e.name]));
const nameOf = (id) => NAME.get(id) ?? id;
const PAIR = ['fixture-deprecated', 'fixture-noncommercial'];

/** The Excluded panel as the island writes it: the summary, then one line per entry left out. */
const panel = (s) => [summary(s), ...s.excluded.map((e) => `${nameOf(e.id)} — ${e.fired.map((f) => `${label(f.rule)}: ${why(f, nameOf)}`).join('; ')}`)];

// the three ways a basket of the pair and one open entry is filled
const PICKS = ['fixture-noncommercial', 'fixture-open', 'fixture-deprecated'];
const byHand = () => PICKS.reduce((s, id) => added(s, [id]), {});
const byLink = () => decode(suiteHref(PICKS).slice('/suite/'.length)).state;
const byAI = () => {
  // P6-S5-T01's suite schema: entry_ref is an integer index into the retrieved array, never an id
  const retrieved = ['fixture-open', 'fixture-purpose', 'fixture-deprecated', 'fixture-unlicensed', 'fixture-noncommercial'].map((id) => ({ id }));
  const proposal = { suite: [{ entry_ref: 4, why: 'vision' }, { entry_ref: 2, why: 'code' }, { entry_ref: 0, why: 'code' }], not_covered: ['multilingual'] };
  return added({}, proposal.suite.map((s) => retrieved[s.entry_ref].id));
};

test('the ledger\'s pair, a deprecated and a licence-incompatible entry, is excluded with its reasons on the manual and the AI path alike', () => {
  const paths = { 'by hand': byHand(), 'by its link': byLink(), 'by the AI accelerator': byAI() };
  const results = Object.entries(paths).map(([how, state]) => [how, screen(basketOf(state), TABLE)]);
  for (const [how, s] of results) {
    assert.deepEqual(s.kept, ['fixture-open'], how);
    assert.deepEqual(s.excluded.map((e) => e.id), PAIR, how);
    assert.deepEqual(panel(s), [
      'Excluded 2 of 3 entries because: licence-incompatible (1), deprecated (1).',
      'Fixture Deprecated Bench — deprecated: lifecycle: deprecated, the maintainer advises against use',
      'Fixture Non-Commercial Bench — licence-incompatible: data.dataset_licence: “CC-BY-NC-4.0”, which allows non-commercial use only, and the suite is screened for any use',
    ], how);
  }
  // one answer, whichever way the basket was filled: the same object, field for field
  for (const [how, s] of results.slice(1)) assert.deepEqual(s, results[0][1], `${how} is screened as ${results[0][0]} is`);
});

test('every rule fires on the field it names, and an entry may fire more than one', () => {
  const s = screen(FIXTURE.map((e) => e.id), TABLE);
  const fired = Object.fromEntries(s.excluded.map((e) => [e.id, e.fired.map((f) => `${f.rule} ${f.field}=${f.value}`)]));
  assert.deepEqual(fired, {
    'fixture-deprecated': ['deprecated lifecycle=deprecated'],
    'fixture-noncommercial': ['licence data.dataset_licence=CC-BY-NC-4.0'],
    'fixture-retracted': ['deprecated lifecycle=retracted'],
    'fixture-superseded': ['superseded lifecycle=superseded', 'superseded lineage.superseded_by=fixture-open'],
    'fixture-succeeded': ['superseded lineage.superseded_by=fixture-open, fixture-deprecated'],
    'fixture-contaminated': ['contaminated lifecycle=contaminated', 'contaminated data.contamination_risk=confirmed'],
    'fixture-high-risk': ['contaminated data.contamination_risk=high'],
    'fixture-purpose': ['licence data.dataset_licence, execution.code_licence=MIT License with an additional clause (use only to evaluate the safety of AI systems)'],
    'fixture-two-rules': ['licence data.dataset_licence=Academic research use only, no commercial use', 'deprecated lifecycle=deprecated'],
  });
  assert.deepEqual(s.kept, ['fixture-open', 'fixture-unlicensed', 'fixture-terms']);
  assert.equal(summary(s), 'Excluded 9 of 12 entries because: licence-incompatible (3), deprecated (3), superseded (2), known-contaminated (2).');
  // each rule's reason names its field and what it holds
  const reasons = Object.fromEntries(s.excluded.map((e) => [e.id, e.fired.map((f) => why(f, nameOf))]));
  assert.deepEqual(reasons['fixture-retracted'], ['lifecycle: retracted, the maintainer has withdrawn it']);
  assert.deepEqual(reasons['fixture-superseded'], ['lifecycle: superseded, a later benchmark has replaced it', 'lineage.superseded_by: Fixture Open Bench']);
  assert.deepEqual(reasons['fixture-succeeded'], ['lineage.superseded_by: Fixture Open Bench, Fixture Deprecated Bench']);
  assert.deepEqual(reasons['fixture-contaminated'], ['lifecycle: contaminated, evidenced training-data leakage compromises it', 'data.contamination_risk: confirmed, on 2 evidence sources']);
  assert.deepEqual(reasons['fixture-high-risk'], ['data.contamination_risk: high, on 1 evidence source']);
  assert.deepEqual(reasons['fixture-purpose'], ['data.dataset_licence, execution.code_licence: “MIT License with an additional clause (use only to evaluate the safety of AI systems)”, which limits use to a stated purpose']);
  assert.deepEqual(RULES.map(([id]) => label(id)), ['licence-incompatible', 'deprecated', 'superseded', 'known-contaminated']);
});

test('an entry whose licence the rule cannot read is kept and named, never cleared in silence', () => {
  const s = screen(['fixture-open', 'fixture-terms', 'fixture-unlicensed'], TABLE);
  assert.deepEqual(s.excluded, []);
  assert.deepEqual(s.unread, ['fixture-terms', 'fixture-unlicensed']);
  assert.equal(summary(s), 'No entry is excluded: no rule fires on the 3 entries of the basket.');
  assert.equal(unreadNote(s, nameOf), 'The licence rule read 1 of the 3 entries kept. No licence it recognises is curated for Fixture Terms-of-Use Bench, Fixture Unlicensed Bench: kept, not cleared.');
  assert.equal(unreadNote(screen(['fixture-unlicensed'], TABLE), nameOf), 'The licence rule read 0 of the 1 entry kept. No licence it recognises is curated for Fixture Unlicensed Bench: kept, not cleared.');
  assert.equal(summary(screen([], TABLE)), 'The basket is empty, so nothing is excluded.');
});

test('the use: any use unless stated; non-commercial research keeps a non-commercial licence, never a stated-purpose one', () => {
  const ids = ['fixture-noncommercial', 'fixture-purpose', 'fixture-two-rules', 'fixture-open'];
  assert.deepEqual(screen(ids, TABLE), screen(ids, TABLE, 'any'), 'the default is any use, commercial use included');
  const research = screen(ids, TABLE, 'non-commercial');
  assert.deepEqual(research.kept, ['fixture-noncommercial', 'fixture-open']);
  assert.deepEqual(research.excluded.map((e) => [e.id, e.fired.map((f) => f.rule)]), [['fixture-purpose', ['licence']], ['fixture-two-rules', ['deprecated']]]);
  assert.deepEqual(research.unread, [], 'a non-commercial licence read and allowed is not unread');
});

test('code, not judgement: only the structured fields count, and the same ids give the same answer in any order', () => {
  // a name, an alias or a description that says "deprecated" or "contaminated" is not a field a rule reads
  const decoy = { id: 'decoy', name: 'Deprecated Contaminated NC Bench', aliases: ['superseded'], description: 'non-commercial use only', lifecycle: 'active', data: { dataset_licence: 'MIT', contamination_risk: 'medium' }, execution: { code_licence: 'MIT' } };
  assert.equal(factsOf(decoy), null);
  // medium, low and unknown risk, and every other lifecycle, fire nothing
  for (const risk of ['low', 'medium', 'unknown']) assert.equal(factsOf({ ...decoy, data: { ...decoy.data, contamination_risk: risk } }), null, risk);
  for (const lc of ['proposed', 'active', 'mature', 'saturated', 'under-revision', 'dormant', null]) assert.equal(factsOf({ ...decoy, lifecycle: lc }), null, String(lc));
  // order: `kept` and `excluded` keep the order given, and any order of the same ids is the same partition
  const ids = FIXTURE.map((e) => e.id);
  const one = screen(ids, TABLE);
  let seed = 11;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < 30; i++) {
    const list = [...ids];
    for (let j = list.length - 1; j > 0; j--) {
      const k = Math.floor(next() * (j + 1));
      [list[j], list[k]] = [list[k], list[j]];
    }
    const s = screen(list, TABLE);
    assert.deepEqual(s.kept, list.filter((id) => one.kept.includes(id)));
    assert.deepEqual([...s.excluded].sort((a, b) => (a.id < b.id ? -1 : 1)), [...one.excluded].sort((a, b) => (a.id < b.id ? -1 : 1)));
    assert.equal(summary(s), summary(one));
  }
  // an id the table does not have is kept with nothing read of it, and the table's own keys are not mistaken for rows
  assert.deepEqual(screen(['no-such-entry', 'constructor', '__proto__'], TABLE).kept, ['no-such-entry', 'constructor', '__proto__']);
  // the module reaches nothing beyond its arguments: no import, no request, no model
  const src = readFileSync(here('../src/islands/suite/exclusions.ts'), 'utf8');
  assert.doesNotMatch(src, /^\s*import\s/m);
  assert.doesNotMatch(src, /\b(?:fetch|XMLHttpRequest|eval|Function)\s*\(/);
});

test('the licence patterns, over the kinds of text the corpus holds', () => {
  const reads = {
    'non-commercial': [
      'CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0', 'CC-BY-NC-ND-4.0', 'CC-BY-NC-SA-3.0', 'CC BY-NC-ND (version not stated in the passage read)',
      'Creative Commons non-commercial (version not stated in the passage read)', 'CC-BY-NC-4.0, with the dataset\'s Terms of Use',
      'CC BY 4.0, except one subset under CC BY-NC 4.0', 'mixed, per dataset (CC-BY, CC-BY-ND, CC-BY-NC-SA, CC0, CC-NC-SA, and terms of use)',
      'Non-commercial research use (the repository\'s license.txt; no named licence)', 'Research use (the task\'s own terms; no named licence)',
      'Dataset Research Use Agreement (personal, non-commercial research use; no redistribution or derivative works)',
      'Academic research use only, no commercial use, no distribution or modification without prior approval',
      'per dataset; some permit commercial use, others research use only', 'terms of use: non-commercial research only',
      'terms of access: non-commercial research and educational use only', 'CC-BY-4.0 as stated, with a licence grant on the same page for non-commercial scientific research only',
      'free for personal or academic use',
    ],
    purpose: ['MIT License with an additional clause (use only to improve the safety and security of AI systems)'],
    open: [
      'CC-BY-4.0', 'CC BY 4.0', 'MIT', 'Apache-2.0', 'BSD-3-Clause', 'BSD-2-Clause', 'GPL-3.0', 'CC-BY-SA-4.0', 'CC-BY-SA-3.0', 'CC-BY-ND-4.0',
      'CC-BY-3.0', 'CC0-1.0', 'ODbL-1.0', 'ODC-By-1.0', 'EUPL-1.2', 'MPL-2.0', 'AFL-3.0', 'CC-BY-4.0 AND Apache-2.0',
      'Apache-2.0, with the added requirement that any public redistribution be encrypted',
      'AFL-3.0 (the 2021 task derivatives); CC-BY-4.0 for the newer data',
      'mixed, per dataset (CC-BY-4.0, CC-BY-SA-4.0, CDLA-Permissive-1.0, CC0-1.0, MIT, Etalab Open Licence 2.0)',
      'Apache-2.0 (lean, isabelle), MIT (metamath), BSD (hollight)',
      'Per dataset. The record is labelled CC BY 4.0, and its LICENSE.txt gives each dataset\'s own open licence.',
    ],
    unread: ['Example Terms of Use', 'software terms of use (not under copyright; use, copying, modification and distribution permitted with the notice kept)', 'see the website'],
  };
  for (const [want, texts] of Object.entries(reads)) for (const t of texts) assert.equal(termsOf(t), want, t);
  // words that only look like a limit are not one
  for (const t of ['MIT (submitted with the paper)', 'Apache-2.0; commercial use permitted', 'CC-BY-4.0, for research purposes and beyond']) assert.equal(termsOf(t), 'open', t);
});

test('the fact table keeps only what a rule can fire on or cannot read, and the page and the island go through this module', () => {
  assert.deepEqual(Object.keys(TABLE).sort(), FIXTURE.map((e) => e.id).filter((id) => id !== 'fixture-open').sort());
  assert.deepEqual(TABLE['fixture-deprecated'], { lifecycle: 'deprecated' });
  assert.deepEqual(TABLE['fixture-noncommercial'], { terms: [{ field: 'data.dataset_licence', text: 'CC-BY-NC-4.0', limit: 'non-commercial' }] });
  assert.deepEqual(TABLE['fixture-high-risk'], { risk: 'high', evidence: 1 });
  assert.deepEqual(TABLE['fixture-unlicensed'], { unread: true });
  assert.deepEqual(JSON.parse(JSON.stringify(TABLE)), TABLE, 'the table survives the prop serialisation the island receives it by');
  // the page reads the full records into the table, and the island screens its basket with it, in one place
  const page = readFileSync(here('../src/pages/suite/index.astro'), 'utf8');
  assert.match(page, /factTable\(records\)/);
  assert.match(page, /facts=\{facts\}/);
  const island = readFileSync(here('../src/islands/SuiteBuilder.tsx'), 'utf8');
  assert.match(island, /from '\.\/suite\/exclusions\.ts'/);
  assert.equal(island.match(/\bscreen\([^)]/g)?.length, 1, 'the island calls screen() once, over its basket');
  assert.match(island, /screen\(basket, facts\)/);
});
