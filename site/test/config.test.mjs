// site/test/config.test.mjs -- P2-S1-T01. Run after `npx astro build`: node --test test/config.test.mjs
//
// Two properties the scaffold exists to lock in (08 S5.1, 04 S12):
//   1. compressHTML is literally `true` -- not 'jsx', not omitted and left to the Astro 7 default;
//   2. no content collection declares a schema, so the Pydantic models stay the only validator.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const here = (p) => fileURLToPath(new URL(p, import.meta.url));

test('compressHTML is literally true in astro.config.mjs', async () => {
  const { default: config } = await import('../astro.config.mjs');
  assert.strictEqual(config.compressHTML, true);
});

test('the built entry-point rows keep the whitespace between inline elements', () => {
  // The failure compressHTML: 'jsx' causes, checked where it shows: the rendered HTML of a row written one element per
  // line, whose line-broken whitespace 'jsx' removes. Observed on 7.3.3 (2026-09-24): 'jsx' keeps a space written on one
  // line but removes whitespace that contains a line break, so such a row renders "robotics-embodimentmanipulation".
  // Until P2-S4-T08 the page was a placeholder carrying a chip row for this; the landing page's entry points (Browse,
  // Atlas, Coverage Map, Methodology) are now the row, each a name then its gloss on the next line, in every build state.
  const page = here('../dist/index.html');
  assert.ok(existsSync(page), 'dist/index.html is missing: run `npx astro build` first');
  const html = readFileSync(page, 'utf8');
  const rows = [...html.matchAll(/<li[^>]*data-entry="([a-z]+)"[^>]*>([\s\S]*?)<\/li>/g)];
  assert.deepEqual(rows.map((r) => r[1]), ['browse', 'atlas', 'coverage', 'methodology'], 'entry-point rows in dist/index.html');
  for (const [, id, row] of rows) {
    assert.match(row, /<\/(a|span)> <span class="gloss"/, `${id}: the name and its gloss are one space apart`);
    assert.doesNotMatch(row, /<\/(a|span)><span/, `${id}: no inline elements run together`);
  }
});

// content.config.ts imports from the virtual module astro:content, which only exists inside an
// Astro build, so it is checked as source text rather than imported.
const source = readFileSync(here('../src/content.config.ts'), 'utf8');
const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

function collectionCalls(text) {
  // The argument text of every defineCollection(...) call, matched by parenthesis depth.
  const out = [];
  const re = /defineCollection\s*\(/g;
  let m;
  while ((m = re.exec(text))) {
    let depth = 1;
    let i = re.lastIndex;
    for (; i < text.length && depth; i++) {
      if (text[i] === '(') depth++;
      else if (text[i] === ')') depth--;
    }
    out.push(text.slice(re.lastIndex, i - 1));
  }
  return out;
}

test('no content collection declares a schema', () => {
  for (const args of collectionCalls(code)) {
    assert.doesNotMatch(args, /\bschema\s*:/, `a collection declares a schema: ${args.trim()}`);
  }
  assert.doesNotMatch(code, /\bfrom\s+['"](astro\/zod|zod)['"]/, 'content.config.ts imports zod');
  assert.doesNotMatch(code, /\bimport\s*\{[^}]*\bz\b[^}]*\}\s*from\s*['"]astro:content['"]/,
    'content.config.ts imports z from astro:content');
  assert.match(code, /export\s+const\s+collections\s*=/, 'content.config.ts exports no collections');
});

test('the schema check is not vacuous: it catches a collection that declares one', () => {
  const bad = "const b = defineCollection({ loader: glob({ pattern: '*.json', base: 'x' }), schema: z.object({}) });";
  assert.throws(() => {
    for (const args of collectionCalls(bad)) assert.doesNotMatch(args, /\bschema\s*:/);
  });
  const good = "const b = defineCollection({ loader: glob({ pattern: '*.json', base: 'x' }) });";
  assert.equal(collectionCalls(good).length, 1);
});

test('package.json pins the toolchain exactly', () => {
  const pkg = JSON.parse(readFileSync(here('../package.json'), 'utf8'));
  assert.deepEqual(
    { astro: pkg.dependencies.astro, react: pkg.dependencies['@astrojs/react'] },
    { astro: '7.3.3', react: '6.0.6' });
  assert.match(pkg.dependencies.react, /^19\.\d+\.\d+$/);
  assert.equal(pkg.engines.node, '>=22.12.0');
  const lock = JSON.parse(readFileSync(here('../package-lock.json'), 'utf8'));
  assert.equal(lock.packages['node_modules/astro'].version, '7.3.3');
  assert.equal(lock.packages['node_modules/@astrojs/react'].version, '6.0.6');
});
