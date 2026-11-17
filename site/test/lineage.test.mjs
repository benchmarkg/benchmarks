// site/test/lineage.test.mjs -- P2-S3-T03. <LineageFigure> (10 V6 section 11; 09 S6.12, S8.4) rendered with Astro's
// container API, the way components.test.mjs renders the inventory:
//
//   cd site && node --test test/lineage.test.mjs
//
// The SVG and the table are tools/build/lineage_svg.py's (tests/build/test_svgcharts.py tests them). This checks the
// component's half: figure -> figcaption -> svg -> summary -> table, the SVG's aria-labelledby and aria-describedby
// resolving to elements of the rendered figure, no script and no aria-label, and markup the build never writes
// refused rather than inlined. When the preview's lineage artifact has been built (`uv run python
// tools/build/lineage_svg.py --corpus build/preview/corpus.json --out build/preview/derived/lineage.json`), its
// SWE-bench figure is rendered too.
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { getViteConfig } from 'astro/config';
import { createServer } from 'vite';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const PREVIEW = fileURLToPath(new URL('../../build/preview/derived/lineage.json', import.meta.url));

let server;
let container;
before(async () => {
  const config = await getViteConfig({ logLevel: 'silent' }, { logLevel: 'silent' })({ command: 'serve', mode: 'test' });
  server = await createServer({ ...config, root: SITE, configFile: false, logLevel: 'silent', appType: 'custom',
    server: { middlewareMode: true, hmr: false, ws: false } });
  container = await AstroContainer.create();
});
after(async () => { await server?.close(); });

const render = async (figure) => (await container.renderToString(
  (await server.ssrLoadModule('/src/components/LineageFigure.astro')).default, { props: { figure } }))
  .replace(/ data-astro-cid-\w+(="[^"]*")?/g, '');

// The shape lineage_svg.entry() writes, cut down to one edge.
const ENTRY = {
  id: 'lineage-a', caption: 'Lineage of A & <B>', caption_id: 'lineage-a-caption', summary: "A's lineage records 1 relation.",
  summary_id: 'lineage-a-summary', relations: 1, related: 1,
  svg: '<svg xmlns="http://www.w3.org/2000/svg" class="svgchart svgchart-lineage" role="img" aria-labelledby="lineage-a-caption" '
    + 'aria-describedby="lineage-a-summary" width="200" height="44" viewBox="0 0 200 44"><g class="edge" data-from="b" '
    + 'data-relation="fork of" data-to="a"><text x="8" y="17" style="font-size:0.6875rem">fork of</text></g></svg>',
  table: '<table class="svgchart-table" id="lineage-a-table"><thead><tr><th scope="col">Entry</th></tr></thead>'
    + '<tbody><tr><td><a href="/benchmarks/b/"><code>b</code></a></td></tr></tbody></table>',
};

test('figure -> figcaption -> svg -> summary -> table, with the SVG labelled and described by the figure itself', async () => {
  const html = await render(ENTRY);
  const order = [...html.matchAll(/<(figure|figcaption|svg|p|table)\b/g)].map((m) => m[1]);
  assert.deepEqual(order, ['figure', 'figcaption', 'svg', 'p', 'table']);
  const svg = html.match(/<svg\b[^>]*>/)[0];
  assert.match(svg, /role="img"/);
  const label = svg.match(/aria-labelledby="([^"]+)"/)[1];
  const desc = svg.match(/aria-describedby="([^"]+)"/)[1];
  assert.match(html, new RegExp(`<figcaption id="${label}">Lineage of A &amp; &lt;B&gt;</figcaption>`));
  assert.match(html, new RegExp(`<p class="summary" id="${desc}">A&#39;s lineage records 1 relation.</p>`));
  assert.doesNotMatch(html, /<script|aria-label="(?!Lineage table)/);
  assert.match(html, /<a href="\/benchmarks\/b\/"><code>b<\/code><\/a>/);
});

test('markup the build never writes is refused, not inlined', async () => {
  for (const [bad, why] of [
    [{ ...ENTRY, svg: ENTRY.svg.replace('</svg>', '<script>alert(1)</script></svg>') }, /never writes/],
    [{ ...ENTRY, svg: ENTRY.svg.replace('<g ', '<g onclick="x()" ') }, /never writes/],
    [{ ...ENTRY, table: ENTRY.table.replace('/benchmarks/b/', 'javascript:alert(1)') }, /never writes/],
    [{ ...ENTRY, svg: ENTRY.svg.replace(' role="img"', '') }, /role="img"/],
    [{ ...ENTRY, caption_id: 'other' }, /aria-labelledby="other"/],
    [{ ...ENTRY, svg: ENTRY.svg.replace('role="img"', 'role="img" aria-label="x"') }, /aria-label/],
    [{ ...ENTRY, table: '<div></div>' }, /not one <table>/],
    [{ ...ENTRY, summary: '' }, /no summary/],
  ]) await assert.rejects(render(bad), why);
});

test('the preview build\'s SWE-bench figure renders whole', { skip: !existsSync(PREVIEW) && 'the preview lineage artifact is not built' }, async () => {
  const doc = JSON.parse(readFileSync(PREVIEW, 'utf8'));
  assert.equal(doc.artifact, 'lineage');
  const e = doc.benchmarks['swe-bench'];
  const html = await render(e);
  for (const id of ['swe-bench', 'swe-bench-verified', 'swe-bench-lite', 'swe-bench-multimodal', 'swe-bench-multilingual', 'swe-bench-pro']) {
    assert.match(html, new RegExp(`data-id="${id}"`), id);
  }
  assert.equal((html.match(/<g class="edge"/g) ?? []).length, e.relations);
  assert.equal((html.match(/<tbody>[\s\S]*<\/tbody>/)[0].match(/<tr>/g) ?? []).length, e.relations);
});
