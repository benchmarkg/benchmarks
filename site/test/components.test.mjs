// site/test/components.test.mjs -- P2-S2-T06. The component inventory of 09-design-system.md S6, each component's
// "never" row expressed as a test.
//
//   cd site && node --test test/components.test.mjs
//
// Components are rendered to HTML with Astro's container API, loaded through a Vite server built from this site's
// own astro.config.mjs (the same compiler `astro build` uses), so a test sees exactly the markup a page would.
// A "never" that is a build failure in 09 S6 is a render that throws here.
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { getViteConfig } from 'astro/config';
import { createServer } from 'vite';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const COMPONENTS = ['BenchmarkCard', 'FacetChip', 'VerificationBadge', 'ConditionMeter', 'ValueCell', 'SourceCitation',
  'Staleness', 'ComparabilityBanner', 'Absent', 'EmptyState', 'Skeleton', 'ChartFigure', 'CiteThis', 'Contribute'];
const SHA = '0123456789abcdef0123456789abcdef01234567';
const TODAY = new Date('2026-10-06T00:00:00Z');

let server;
let container;
before(async () => {
  const config = await getViteConfig({ logLevel: 'silent' }, { logLevel: 'silent' })({ command: 'serve', mode: 'test' });
  server = await createServer({ ...config, root: SITE, configFile: false, logLevel: 'silent', appType: 'custom',
    server: { middlewareMode: true, hmr: false, ws: false } });
  container = await AstroContainer.create();
});
after(async () => { await server?.close(); });

const load = async (name) => (await server.ssrLoadModule(`/src/components/${name}.astro`)).default;
// Astro's scoped-style attributes (data-astro-cid-*) are noise to every assertion here, so they are dropped.
const render = async (name, props = {}) => (await container.renderToString(await load(name), { props }))
  .replace(/ data-astro-cid-\w+(="[^"]*")?/g, '');
const source = (name) => readFileSync(`${SITE}src/components/${name}.astro`, 'utf8');
const style = (name) => (source(name).match(/<style[^>]*>([\s\S]*?)<\/style>/g) ?? []).join('\n');
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const count = (html, re) => (html.match(re) ?? []).length;

// ---- the inventory -----------------------------------------------------------------------------------------

test('all fourteen components exist, <AiPanel> (Phase 6) aside', () => {
  const have = readdirSync(`${SITE}src/components`).map((f) => f.replace(/\.astro$/, ''));
  for (const c of COMPONENTS) assert.ok(have.includes(c), `${c}.astro is missing`);
  assert.ok(!have.includes('AiPanel'));
});

test('components are sized by container queries, never viewport media queries (09 S5.3)', () => {
  for (const c of [...COMPONENTS, 'FacetChips']) {
    for (const m of style(c).matchAll(/@media\s*([^{]+)\{/g)) {
      assert.match(m[1], /^\((pointer|prefers-reduced-motion|prefers-color-scheme|forced-colors|hover)\b/, `${c}: @media ${m[1]}`);
    }
  }
  assert.match(style('BenchmarkCard'), /container-type:\s*inline-size/);
  assert.match(style('BenchmarkCard'), /@container \(inline-size > 24rem\)/);
});

test('tabular figures and a slashed zero wherever a number is compared or an id transcribed (09 S3.4)', () => {
  const css = readFileSync(`${SITE}src/styles/type.css`, 'utf8');
  const rule = css.match(/([^{}]+)\{\s*font-variant-numeric:\s*tabular-nums slashed-zero;/);
  assert.ok(rule, 'type.css has no tabular-nums slashed-zero rule');
  for (const sel of ['td', 'th', '.value-cell', '.meter', 'code', 'time']) assert.ok(rule[1].includes(sel), sel);
  for (const c of ['ValueCell', 'VerificationBadge', 'FacetChip', 'BenchmarkCard']) assert.match(style(c), /tabular-nums slashed-zero/, c);
});

// ---- 6.9 <Absent> ------------------------------------------------------------------------------------------

test('Absent renders the glyph and one of the four phrases, never blank', async () => {
  for (const [state, phrase] of [['not-reported', 'not reported'], ['not-recorded', 'not recorded'],
    ['not-applicable', 'not applicable'], ['unknown', 'unknown']]) {
    const html = await render('Absent', { state });
    assert.equal(text(html), `∅ ${phrase}`);
  }
});

test('Absent has no fifth state: a dash, an empty string or n/a throws', async () => {
  for (const state of ['', '—', 'n/a', 'missing']) await assert.rejects(render('Absent', { state }), /not one of/);
});

// ---- 6.2 <FacetChip> ---------------------------------------------------------------------------------------

test('FacetChip never invents a term: an unresolvable term_id fails the build', async () => {
  await assert.rejects(render('FacetChip', { facet: 'capability', term_id: 'telepathy' }), /does not resolve in taxonomy/);
  await assert.rejects(render('FacetChip', { facet: 'colour', term_id: 'x' }), /not in taxonomy/);
  assert.match(await render('FacetChip', { facet: 'domain', term_id: 'biology-genetics' }), />Biology and genetics</);
});

test('an active filter chip has a filled ground AND a × affordance, and every chip is at least 24px', async () => {
  const html = await render('FacetChip', { facet: 'lifecycle', term_id: 'proposed', state: 'filter-active', href: '?x' });
  assert.match(html, /data-state="filter-active"/);
  assert.match(html, /aria-current="true"/);
  assert.match(html, /×/);
  assert.match(style('FacetChip'), /\[data-state='filter-active'\]\s*\{\s*background:/);
  assert.match(style('FacetChip'), /min-block-size: 1\.5rem/);
  assert.match(style('FacetChip'), /@media \(pointer: coarse\)\s*\{\s*\.chip\s*\{\s*min-block-size: 1\.75rem/);
});

test('never more than six chips before a +N more disclosure', async () => {
  const caps = ['knowledge-recall', ...Object.keys(JSON.parse(readFileSync(`${SITE}src/lib/taxonomy.json`, 'utf8')).facets.capability).slice(1, 8)];
  const html = await render('FacetChips', { chips: caps.map((t) => ({ facet: 'capability', term_id: t })) });
  const [visible] = html.split('<details');
  assert.equal(count(visible, /class="chip"/g), 6);
  assert.match(html, /<summary>\+2 more<\/summary>/);
});

// ---- 6.3 <VerificationBadge> -------------------------------------------------------------------------------

test('VerificationBadge never renders without a level', async () => {
  await assert.rejects(render('VerificationBadge', {}), /not a rung/);
  await assert.rejects(render('VerificationBadge', { verification: 'unknown' }), /no "unknown verification"/);
});

test('seven segments filled to the rank; the compact code keeps the full name in text, not a title', async () => {
  const html = await render('VerificationBadge', { verification: 'independent-reproduction', compact: true });
  assert.equal(count(html, /<i class="on"/g), 3);
  assert.equal(count(html, /<i class="off"/g), 4);
  assert.match(html, />IR</);
  assert.match(text(html), /Verification: Independent reproduction, level 3 of 7/);
  assert.doesNotMatch(html, /title=/);
});

test('the 2-letter codes are unique and cover every rung of the ladder', async () => {
  const v = await server.ssrLoadModule('/src/lib/vocab.ts');
  assert.deepEqual(Object.keys(v.RUNG_CODES).sort(), [...v.RUNGS].sort());
  assert.equal(new Set(Object.values(v.RUNG_CODES)).size, v.RUNGS.length);
});

test('disputed overlays the warning glyph and links its disputes; disputed with none throws', async () => {
  const html = await render('VerificationBadge', { verification: 'self-reported', disputed: true, disputed_by: ['dsp-1', 'dsp-2'] });
  assert.match(html, /⚠/);
  assert.match(html, /href="\/disputes\/dsp-1\/"/);
  assert.match(html, /href="\/disputes\/dsp-2\/"/);
  await assert.rejects(render('VerificationBadge', { verification: 'self-reported', disputed: true }), /no disputed_by/);
});

// ---- 6.4 <ConditionMeter> ----------------------------------------------------------------------------------

test('one segment per material field, filled for exactly the fields specified', async () => {
  const html = await render('ConditionMeter', { condition_completeness: 7 / 11, fields_specified: 7, fields_material_total: 11 });
  assert.equal(count(html, /<i class="on"/g), 7);
  assert.equal(count(html, /<i class="off"/g), 4);
  assert.match(text(html), /7 of 11 material condition fields specified/);
});

test('ConditionMeter never rounds up: a completeness above its counts throws', async () => {
  await assert.rejects(render('ConditionMeter', { condition_completeness: 0.7, fields_specified: 7, fields_material_total: 11 }), /never round up/);
});

test('ConditionMeter never hides at low completeness, never colours it as an error, and is a fraction above 12', async () => {
  const empty = await render('ConditionMeter', { condition_completeness: 0, fields_specified: 0, fields_material_total: 11 });
  assert.equal(count(empty, /<i class="off"/g), 11);
  assert.doesNotMatch(style('ConditionMeter'), /--c-(alert|caution)/);
  const wide = await render('ConditionMeter', { condition_completeness: 3 / 14, fields_specified: 3, fields_material_total: 14 });
  assert.match(wide, />3\/14</);
  assert.equal(count(wide, /<i /g), 0);
});

// ---- 6.5 <ValueCell> ---------------------------------------------------------------------------------------

const SOURCE = { source_id: 'src-x', title: 'A report', publisher: 'Lab', url: 'https://example.org/r', archive_url: null,
  retrieved_at: '2026-10-01', source_type: 'paper' };
const CELL = { value: 0.712, metric_id: 'accuracy', unit: 'fraction', verification: 'maintainer-verified',
  condition_completeness: 2 / 4, fields_specified: 2, fields_material_total: 4, claim_id: 'clm-abc', comparability_key: 'k1',
  uncertainty: 0.012, source: SOURCE, reporter: 'Lab', date_reported: '2026-05-04',
  conditions: { shots: 0, temperature: null, selection_strategy: null, n_samples: 1 }, commit_sha: SHA, yaml_path: 'data/claims/clm-abc.yaml' };

test('ValueCell never renders the value without the badge and the meter', async () => {
  const html = await render('ValueCell', CELL);
  const button = html.match(/<button[\s\S]*?<\/button>/)[0];
  assert.match(button, /0\.712/);
  assert.match(button, /data-verification="maintainer-verified"/);
  assert.match(button, /data-meter/);
  assert.doesNotMatch(button, /<a /, 'no link inside the button');
});

test('there is no compact mode that drops provenance', async () => {
  for (const mode of ['compact', 'density', 'hide_provenance']) {
    await assert.rejects(render('ValueCell', { ...CELL, [mode]: true }), /provenance is never cut/);
  }
});

test('the provenance popover: native popover=auto, conditions with unknowns shown as unknown, a permalink at the SHA', async () => {
  const html = await render('ValueCell', CELL);
  const id = html.match(/popovertarget="([^"]+)"/)[1];
  assert.match(html, new RegExp(`<div popover="auto" id="${id}"`));
  assert.equal(count(html, /data-absent="unknown"/g), 2);
  assert.match(html, new RegExp(`/blob/${SHA}/data/claims/clm-abc\\.yaml`));
  assert.match(html, /±0\.012/);
  assert.doesNotMatch(html, /<script/, 'no JavaScript: a detail page carries 0 KB');
});

// ---- 6.6 <SourceCitation> ----------------------------------------------------------------------------------

test('SourceCitation never renders a link without retrieved_at', async () => {
  await assert.rejects(render('SourceCitation', { ...SOURCE, retrieved_at: '' }), /no retrieved_at/);
});

test('an unarchived source says "not archived" visibly; an archived one has a separate, secondary archive link', async () => {
  assert.match(text(await render('SourceCitation', SOURCE)), /∅ not archived/);
  const html = await render('SourceCitation', { ...SOURCE, archive_url: 'https://web.archive.org/web/2026/x' });
  const links = [...html.matchAll(/<a class="(\w+)" href="([^"]+)"/g)].map((m) => [m[1], m[2]]);
  assert.deepEqual(links, [['primary', SOURCE.url], ['archive', 'https://web.archive.org/web/2026/x']]);
});

test('link_only renders the citation and never an excerpt', async () => {
  assert.doesNotMatch(await render('SourceCitation', { ...SOURCE, link_only: true }), /<q/);
  await assert.rejects(render('SourceCitation', { ...SOURCE, link_only: true, excerpt: '0.71' }), /link_only forbids an excerpt/);
});

// ---- 6.7 <Staleness> ---------------------------------------------------------------------------------------

test('four bands, always with the absolute ISO date; stale is shown, not hidden', async () => {
  const at = (d) => render('Staleness', { last_verified_at: d, entity_kind: 'benchmark', today: TODAY });
  assert.match(await at('2026-09-01'), /data-band="fresh"/);
  assert.match(await at('2026-03-01'), /data-band="ageing"/);
  const stale = await at('2025-01-15');
  assert.match(stale, /data-band="stale"/);
  assert.match(stale, /<time datetime="2025-01-15">2025-01-15<\/time>/);
  assert.match(text(stale), /\(629 days\)/);
  assert.match(text(await at(null)), /unverified since creation/);
});

test('Staleness takes last_verified_at, never a file mtime', () => {
  const code = source('Staleness').replace(/^\s*\/\/.*$/gm, '');      // the comments say what it never does
  assert.doesNotMatch(code, /mtime|git log|statSync|lastModified/);
});

// ---- 6.8 <ComparabilityBanner> -----------------------------------------------------------------------------

const BANNER = { keys: ['k1', 'k2'], set_labels: ['Set A', 'Set B'], restrict_href: '?restrict', restrict_drops: 3, proceed_href: '?flag',
  diff: [{ field: 'n_samples', values: [1, 5] }, { field: 'selection_strategy', values: ['best-of-n', null] }] };

test('the banner names exactly the fields that differ, as a table, and offers exactly two ways on', async () => {
  const html = await render('ComparabilityBanner', BANNER);
  assert.equal(count(html, /<tr><th scope="row">/g), 2);
  assert.match(html, /data-absent="unknown"/);
  assert.deepEqual([...html.matchAll(/data-action="(\w+)"/g)].map((m) => m[1]), ['restrict', 'proceed']);
  assert.match(text(html), /3 claims dropped/);
});

test('the banner never editorialises and never uses --c-alert', async () => {
  const words = text(await render('ComparabilityBanner', BANNER)).toLowerCase();
  for (const w of ['better', 'worse', 'correct', 'wrong', 'superior', 'invalid', 'error']) assert.ok(!words.includes(w), w);
  assert.doesNotMatch(style('ComparabilityBanner'), /--c-alert/);
  assert.match(style('ComparabilityBanner'), /--c-caution/);
  await assert.rejects(render('ComparabilityBanner', { ...BANNER, keys: ['k1'] }), /is comparable/);
});

// ---- 6.10 <EmptyState> -------------------------------------------------------------------------------------

const sentences = (html) => (text(html).match(/[^.!?]+[.!?](\s|$)/g) ?? []).length;

test('every empty state is at most three sentences, with no apology and no illustration', async () => {
  const cases = [
    { context: 'search', query: 'protein folding' },
    { context: 'filter', applied_filters: [
      { facet: 'domain', term_id: 'biology-genetics', remove_href: '?a', results_without: 4 },
      { facet: 'lifecycle', term_id: 'proposed', remove_href: '?b', results_without: 12 }] },
    { context: 'domain-page', domain: 'biology-genetics' },
    { context: 'coverage-cell', domain: 'biology-genetics', capability: 'knowledge-recall' },
  ];
  for (const props of cases) {
    const html = await render('EmptyState', props);
    assert.ok(sentences(html) <= 3, `${props.context}: ${sentences(html)} sentences: ${text(html)}`);
    assert.doesNotMatch(text(html).toLowerCase(), /sorry|oops|apolog|unfortunately/);
    assert.doesNotMatch(html, /<img|<svg|<picture/);
  }
});

test('a filter empty-state offers the single most-constraining filter to drop, and lists all as removable chips', async () => {
  const html = await render('EmptyState', { context: 'filter', applied_filters: [
    { facet: 'domain', term_id: 'biology-genetics', remove_href: '?a', results_without: 4 },
    { facet: 'lifecycle', term_id: 'proposed', remove_href: '?b', results_without: 12 }] });
  assert.match(text(html), /Remove Proposed to see 12\./);
  assert.equal(count(html, /data-state="filter-active"/g), 2);
});

test('an empty coverage cell renders as a finding', async () => {
  const html = await render('EmptyState', { context: 'coverage-cell', domain: 'biology-genetics', capability: 'knowledge-recall',
    suggestions: [{ id: 'b1', name: 'Bench One', href: '/b1/' }] });
  assert.match(text(html), /^No benchmark in the index measures knowledge-recall \(Knowledge recall\) in biology-genetics/);
  assert.match(html, /href="\/b1\/"/);
});

// ---- 6.11 <Skeleton> ---------------------------------------------------------------------------------------

test('a skeleton exists only for the three late arrivals, and moves only when motion is allowed', async () => {
  await assert.rejects(render('Skeleton', { for: 'entry-page', inline_size: '10rem', block_size: '1rem' }), /static page has no skeleton/);
  assert.match(await render('Skeleton', { for: 'ai-panel', inline_size: '10rem', block_size: '1rem' }), /inline-size: 10rem; block-size: 1rem/);
  const css = style('Skeleton');
  const [outside] = css.split('@media (prefers-reduced-motion: no-preference)');
  assert.doesNotMatch(outside, /animation:/);
  assert.match(css, /@media \(prefers-reduced-motion: no-preference\)\s*\{[\s\S]*animation:/);
});

// ---- 6.12 <ChartFigure> ------------------------------------------------------------------------------------

const DATA = { caption: 'Rows by rule', units: 'rows', rows: [{ rule: 'public', n: 828 }, { rule: 'private', n: 459 }, { rule: 'none', n: null }],
  columns: [{ key: 'rule', label: 'Rule' }, { key: 'n', label: 'Rows' }] };

test('the server render is figure -> figcaption -> table from the one object, with no SVG and no aria-label', async () => {
  const html = await render('ChartFigure', { data: DATA, chart: { type: 'bar', x: 'rule', y: 'n' } });
  const order = [...html.matchAll(/<(figure|figcaption|table)\b/g)].map((m) => m[1]);
  assert.deepEqual(order, ['figure', 'figcaption', 'table']);
  assert.equal(count(html, /<tbody>[\s\S]*?<\/tbody>/g), 1);
  assert.equal(count(html.match(/<tbody>[\s\S]*<\/tbody>/)[0], /<tr>/g), 3);
  assert.match(html, /data-absent="not-reported"/);
  assert.doesNotMatch(html.replace(/<script[\s\S]*?<\/script>/g, ''), /<svg|aria-label/);
  const embedded = JSON.parse(html.match(/data-chart-figure="([^"]+)"/)[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  assert.deepEqual(embedded.data, DATA);
});

test('ECharts aria is off and a missing value is a gap, never a zero', async () => {
  const { chartOption } = await server.ssrLoadModule('/src/lib/chart.ts');
  const o = chartOption(DATA, { type: 'bar', x: 'rule', y: 'n' });
  assert.deepEqual(o.aria, { enabled: false });
  assert.deepEqual(o.series[0].data, [828, 459, null]);
  await assert.rejects(render('ChartFigure', { data: DATA, chart: { type: 'bar', x: 'rule', y: 'nope' } }), /not a column/);
});

// ---- 6.13 <CiteThis>, 6.14 <Contribute> --------------------------------------------------------------------

test('CiteThis offers BibTeX, APA, a permalink at the commit SHA and the raw YAML at it', async () => {
  const html = await render('CiteThis', { entity_id: 'swe-bench', title: 'SWE-bench', commit_sha: SHA, release_doi: null,
    retrieved_at: '2026-10-06', yaml_path: 'data/benchmarks/swe-bench.yaml' });
  assert.match(html, /@misc\{uaibi-swe-bench-0123456,/);
  assert.match(text(html), /Benchmark index contributors\. \(2026\)\. SWE-bench/);
  assert.match(html, new RegExp(`/blob/${SHA}/data/benchmarks/swe-bench\\.yaml`));
  assert.match(html, new RegExp(`/raw/${SHA}/data/benchmarks/swe-bench\\.yaml`));
  assert.match(html, /data-absent="not-applicable"/);
  await assert.rejects(render('CiteThis', { entity_id: 'x', title: 'x', commit_sha: 'main', release_doi: null, retrieved_at: '2026-10-06', yaml_path: 'x' }),
    /not a commit SHA/);
});

test('Contribute: the issue form is the first, primary action; editing the YAML is second and smaller', async () => {
  const html = await render('Contribute', { entity_id: 'swe-bench', entity_kind: 'benchmark', yaml_path: 'data/benchmarks/swe-bench.yaml' });
  const links = [...html.matchAll(/<a class="(\w+)" data-action="([\w-]+)" href="([^"]+)"/g)].map((m) => m.slice(1));
  assert.equal(links[0][0], 'primary');
  assert.equal(links[0][1], 'correction');
  assert.match(links[0][2], /\/issues\/new\?template=correction\.yml&amp;entity_id=swe-bench/);
  assert.deepEqual(links[1].slice(0, 2), ['secondary', 'edit-yaml']);
  assert.match(style('Contribute'), /\.secondary\s*\{\s*font-size: var\(--fs-xs\)/);
  await assert.rejects(render('Contribute', { entity_id: 'x', entity_kind: 'benchmark', yaml_path: 'x',
    issue_form: 'https://github.com/benchmarkg/benchmarks/compare' }), /must be an issue form/);
});

// ---- 6.1 <BenchmarkCard> -----------------------------------------------------------------------------------

const CARD = { id: 'swe-bench', name: 'SWE-bench', tagline: 'Resolve real GitHub issues.', primary_domain: 'biology-genetics/protein-design',
  capabilities: ['knowledge-recall'], lifecycle: 'proposed', year_released: 2023, ceiling_anchor_type: 'theoretical-maximum',
  headroom_consumed: 0.42, claim_count: 12, last_verified_at: '2026-09-01', today: TODAY };

test('BenchmarkCard never shows a headroom bar when no ceiling is known; it shows the absent token and why', async () => {
  const html = await render('BenchmarkCard', { ...CARD, ceiling_anchor_type: 'none-known' });
  assert.doesNotMatch(html, /data-headroom-bar/);
  assert.match(text(html), /∅ not applicable \(no known ceiling, so no headroom\)/);
  assert.match(await render('BenchmarkCard', CARD), /data-headroom-bar style="--v: 0\.42"/);
});

test('BenchmarkCard never carries a metric value', async () => {
  for (const k of ['value', 'score', 'result']) await assert.rejects(render('BenchmarkCard', { ...CARD, [k]: 0.71 }), /cards carry identity and shape/);
  await assert.rejects(render('BenchmarkCard', { ...CARD, capabilities: ['a', 'b', 'c', 'd'] }), /up to 3/);
});

test('the family label comes from the taxonomy, with no swatch, and the footer carries claims and staleness', async () => {
  const html = await render('BenchmarkCard', CARD);
  assert.match(html, /<span class="family"[^>]*>Biology and genetics<\/span>/);
  assert.doesNotMatch(style('BenchmarkCard'), /data-domain|--c-dom/);
  assert.match(text(html), /12 claims/);
  assert.match(html, /data-band="fresh"/);
});
