// site/test/atlas.test.mjs -- P2-S5-T02 (10 V1; 09 S4.3, S4.4, S7.6). The Atlas island's logic, src/lib/atlas.ts, which
// islands/Atlas.tsx renders and Node loads as it is, stripping its types:
//
//   cd site && node --test test/atlas.test.mjs
//
// The colour rule is checked over the lifecycle vocabulary as taxonomy/ holds it, not over a list typed here: of the ten
// terms of the `lifecycle` field exactly three take a colour (contaminated and retracted --c-alert, saturated the headroom
// ramp's top stop), and the other seven, and a node with no lifecycle, are the one neutral ink, in both themes. Paint
// never returns a coordinate, and a filter changes standing only. The matching set is the browse view's tally. The
// camera fit is checked on numbers a person can follow. The browser half -- sigma drawing it, positions held through a
// filter, the hover card and the panel -- is tests/atlas.spec.ts (Playwright).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  ALERT_LIFECYCLES, ATLAS_FORMAT, FIT_PAD, HOME, MIN_FIT_RATIO, SATURATED_LIFECYCLE, box, filtering, fitState, level,
  matching, paint, palette, readAtlas, role, standing,
} from '../src/lib/atlas.ts';
import { buildIndex, railGroups, tally } from '../src/lib/browse-view.ts';
import { allTerms } from '../src/lib/terms.ts';

const tokens = JSON.parse(readFileSync(fileURLToPath(new URL('../src/lib/tokens.json', import.meta.url)), 'utf8'));
const LIFECYCLE = allTerms().filter((t) => t.facet === 'lifecycle' && t.field === 'lifecycle').map((t) => t.id);

const node = (over = {}) => ({
  id: 'n', x: 1.5, y: -2.25, r: 1, cluster: 'code', domain_primary: 'code/repo', domain_group: 'symbolic-formal',
  lifecycle: 'active', headroom_consumed: null, adoption_n: 0, label: 'N', label_priority: 1, ...over,
});

// ---- the three of ten ---------------------------------------------------------------------------------------

test('the lifecycle vocabulary is the ten terms 09 S4.3 colours three of', () => {
  assert.equal(LIFECYCLE.length, 10, LIFECYCLE.join(', '));
  for (const t of [...ALERT_LIFECYCLES, SATURATED_LIFECYCLE]) assert.ok(LIFECYCLE.includes(t), t);
});

for (const theme of ['light', 'dark']) {
  test(`${theme}: exactly contaminated, retracted and saturated take a colour; the other seven are the neutral ink`, () => {
    const p = palette(theme, tokens);
    const k = tokens.themes[theme];
    assert.deepEqual([p.alert, p.saturated, p.muted, p.ink, p.faint], [k['c-alert'].hex, k['seq-head-6'].hex, k['c-ink-muted'].hex, k['c-ink'].hex, k['c-ink-faint'].hex]);
    const coloured = [];
    for (const lc of [...LIFECYCLE, null]) {
      const all = paint(node({ lifecycle: lc }), p, 'all');
      const match = paint(node({ lifecycle: lc }), p, 'match');
      const out = paint(node({ lifecycle: lc }), p, 'out');
      assert.equal(all.ring, all.fill, `${lc}: one ink for ring and fill`);
      assert.equal(out.ring, p.faint, `${lc}: dimmed`);
      assert.equal(out.fill, p.faint, `${lc}: dimmed`);
      if (role(lc) === 'neutral') {
        assert.equal(all.ring, p.muted, String(lc));
        assert.equal(match.ring, p.ink, String(lc));
      } else {
        coloured.push(lc);
        assert.equal(all.ring, role(lc) === 'alert' ? p.alert : p.saturated, lc);
        assert.equal(match.ring, all.ring, `${lc}: a coloured node keeps its colour when it matches`);
        assert.equal(all.level, 1, `${lc}: drawn full`);
      }
    }
    assert.deepEqual(coloured.sort(), ['contaminated', 'retracted', 'saturated']);
    // the colours a whole unfiltered map can use: the neutral ink, the alert and the ramp's top stop, and nothing else
    const used = new Set([...LIFECYCLE, null].map((lc) => paint(node({ lifecycle: lc }), p, 'all').ring));
    assert.deepEqual([...used].sort(), [p.alert, p.muted, p.saturated].sort());
  });
}

test('headroom is a fill level; unknown headroom is no fill, never a zero; a value past the ceiling fills the node', () => {
  assert.equal(level(node({ headroom_consumed: null })), 0);
  assert.equal(level(node({ headroom_consumed: 0.9 })), 0.9);
  assert.equal(level(node({ headroom_consumed: 0 })), 0);
  assert.equal(level(node({ headroom_consumed: 1.3 })), 1);
  assert.equal(level(node({ lifecycle: 'contaminated', headroom_consumed: 0.2 })), 1);
  const p = palette('light', tokens);
  assert.equal(paint(node({ headroom_consumed: 0.4 }), p, 'all').level, 0.4);
  assert.equal(paint(node({ headroom_consumed: 0.4 }), p, 'out').level, 0.4, 'a dimmed node keeps its level');
  assert.equal(paint(node(), p, 'all').empty, p.bg);
});

test('a filter changes standing, labels and order, and no paint carries a coordinate', () => {
  const p = palette('light', tokens);
  const n = node();
  const [all, match, out] = ['all', 'match', 'out'].map((s) => paint(n, p, s));
  assert.equal(all.label, 'N');
  assert.equal(match.label, 'N');
  assert.equal(out.label, null);
  assert.ok(out.zIndex < match.zIndex);
  for (const x of [all, match, out]) assert.deepEqual(Object.keys(x).sort(), ['empty', 'fill', 'label', 'level', 'ring', 'zIndex']);
  assert.deepEqual([n.x, n.y, n.r], [1.5, -2.25, 1], 'the node itself is untouched');
  assert.equal(standing(null, 'n'), 'all');
  assert.equal(standing(new Set(['n']), 'n'), 'match');
  assert.equal(standing(new Set(), 'n'), 'out');
});

// ---- the matching set is the browse view's ---------------------------------------------------------------------

const TERMS = [
  { facet: 'domain', id: 'code', label: 'Code', definition: 'Software.' },
  { facet: 'domain', id: 'code/repo', label: 'Repository-scale', definition: 'Repos.', parent: 'code' },
  { facet: 'domain', id: 'maths', label: 'Mathematics', definition: 'Proofs.' },
  { facet: 'domain', id: 'maths/olympiad', label: 'Olympiad', definition: 'Contests.', parent: 'maths' },
  { facet: 'capability', id: 'planning', label: 'Planning', definition: 'Plans.' },
  { facet: 'evaluation_method', id: 'judge', label: 'Judge', definition: 'Graded.' },
  { facet: 'subject', id: 'llm', label: 'LLM', definition: 'A model.' },
  { facet: 'lifecycle', field: 'lifecycle', id: 'active', label: 'Active', definition: 'In use.' },
  { facet: 'data_properties', field: 'data.access', id: 'open', label: 'Open', definition: 'Public.' },
  { facet: 'governance', field: 'governance.maintainer_type', id: 'academic', label: 'Academic', definition: 'A lab.' },
  { facet: 'governance', field: 'governance.submission_process', id: 'open-pr', label: 'Open PR', definition: 'Anyone.' },
  { facet: 'execution', field: 'execution.compute_tier', id: 'laptop', label: 'Laptop', definition: 'Small.' },
  { facet: 'execution', field: 'execution.reproducibility_tier', id: 'scripted', label: 'Scripted', definition: 'Scripted.' },
];
const row = (id, domain, subdomain, capability, year) => ({
  id, slug: id, name: id.toUpperCase(), aliases: [], domain, subdomain, year, lifecycle: 'active', verification_max: null,
  condition_completeness_max: null, claim_count: 0, headroom: null,
  facets: { capability, evaluation_method: [], subject: ['llm'], data_properties: [], lifecycle: ['active'], governance: [], execution: [] },
});
const INDEX = buildIndex(railGroups(TERMS), [
  row('a', 'code', 'code/repo', ['planning'], 2020), row('b', 'code', 'code/repo', [], 2024),
  row('c', 'maths', 'maths/olympiad', ['planning'], 2024),
]);

test('no filter is no matching set; a filter is the tally\'s matches, by id', () => {
  assert.equal(matching(INDEX, {}), null);
  assert.equal(matching(INDEX, { q: 'bimanual', sort: 'headroom', hr: '0.0-0.8' }), null, 'keys this view keeps but does not apply');
  assert.deepEqual([...matching(INDEX, { d: ['code'] })].sort(), ['a', 'b']);
  assert.deepEqual([...matching(INDEX, { d: ['code'], c: ['planning'] })], ['a']);
  assert.deepEqual([...matching(INDEX, { yr: '2024-2024' })].sort(), ['b', 'c']);
  assert.deepEqual([...matching(INDEX, { d: ['maths'], yr: '2020-2020' })], []);
  for (const state of [{ d: ['code'] }, { c: ['planning'], yr: '2021-2030' }]) {
    assert.equal(matching(INDEX, state).size, tally(INDEX, state).total);
  }
  assert.equal(filtering(INDEX, { d: [] }), false);
});

// ---- the camera ---------------------------------------------------------------------------------------------

test('the fit centres the box and scales the ratio by the share of the viewport it spans, within bounds', () => {
  const cam = { x: 0.5, y: 0.5, ratio: 1, angle: 0 };
  const seen = [];
  const toFramed = (pt) => {
    seen.push(pt);
    return { x: pt.x / 1000, y: pt.y / 800 };
  };
  const b = box([{ x: 100, y: 100, r: 10 }, { x: 290, y: 140, r: 10 }]);
  assert.deepEqual(b, { x0: 90, y0: 90, x1: 300, y1: 150 });
  const s = fitState(b, cam, 1000, 800, toFramed);
  assert.deepEqual(seen, [{ x: 195, y: 120 }]);
  assert.deepEqual([s.x, s.y, s.angle], [0.195, 0.15, 0]);
  assert.ok(Math.abs(s.ratio - (210 / 1000) * FIT_PAD) < 1e-12, String(s.ratio));
  // a single small node: never closer than the floor; a box past the viewport: never further than the whole map
  assert.equal(fitState(box([{ x: 5, y: 5, r: 1 }]), cam, 1000, 800, toFramed).ratio, MIN_FIT_RATIO);
  assert.equal(fitState({ x0: -500, y0: 0, x1: 1500, y1: 10 }, cam, 1000, 800, toFramed).ratio, 1);
  // under a zoomed camera the same share of the viewport is a proportionally smaller ratio
  assert.ok(Math.abs(fitState(b, { ...cam, ratio: 0.5 }, 1000, 800, toFramed).ratio - s.ratio / 2) < 1e-12);
  assert.equal(box([]), null);
  assert.deepEqual(HOME, { x: 0.5, y: 0.5, ratio: 1, angle: 0 });
});

// ---- atlas.json --------------------------------------------------------------------------------------------

test('atlas.json is read only as the atlas artifact of this format, with a finite place for every node', () => {
  const doc = { artifact: 'atlas', format: ATLAS_FORMAT, layout_method: 'pack', layout_epoch: 0, basis_version: null, nodes: [node()], edges: [], regions: [] };
  assert.equal(readAtlas(doc).atlas, doc);
  assert.match(readAtlas({ ...doc, artifact: 'facets' }).error, /not the atlas artifact/);
  assert.match(readAtlas({ ...doc, format: 2 }).error, /format 2/);
  assert.match(readAtlas({ ...doc, regions: undefined }).error, /no node, edge or region list/);
  assert.match(readAtlas({ ...doc, nodes: [node({ x: null })] }).error, /no finite position/);
  assert.match(readAtlas(null).error, /not the atlas artifact/);
});
