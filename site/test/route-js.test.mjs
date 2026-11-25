// site/test/route-js.test.mjs -- P2-S4-T08 (08 S8.1). What the size gate measures for a route, scripts/route_js.mjs, over
// a small built site written here, so every file it should and should not count is known:
//
//   cd site && node --test test/route-js.test.mjs
//
// A route's JavaScript is every script its page names or preloads, every island's component and renderer, the chunks
// those import (statically, or by a literal dynamic import) and its inline scripts; data blocks are not JavaScript, a
// missing chunk fails rather than measuring less, and a path size-limit would read as a glob is refused.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { globSafe, pagePath, routeScripts } from '../../scripts/route_js.mjs';

function site(files) {
  const dist = mkdtempSync(join(tmpdir(), 'route-js-'));
  for (const [rel, body] of Object.entries(files)) {
    mkdirSync(dirname(join(dist, rel)), { recursive: true });
    writeFileSync(join(dist, rel), body);
  }
  return dist;
}
const names = (dist, files) => files.map((f) => f.slice(dist.length + 1).split('\\').join('/'));

test('a page: its scripts, preloads and island, their imports transitively, and its inline scripts', () => {
  const dist = site({
    'index.html': '<html><head><script data-prepaint>var t=1;</script><script type="module" src="/_astro/toggle.js"></script>'
      + '<link rel="modulepreload" href="/_astro/pre.js"><script type="application/ld+json">{"a":1}</script>'
      + '<!-- <script src="/_astro/commented.js"></script> --></head>'
      + '<body><astro-island component-url="/_astro/Panel.js" renderer-url="/_astro/client.js"></astro-island>'
      + '<script>  </script></body></html>',
    '_astro/toggle.js': 'import{a as e}from"./theme.js";e()',
    '_astro/theme.js': 'export const a=()=>1',
    '_astro/pre.js': 'export{}',
    '_astro/Panel.js': 'import"./react.js";const m=()=>import("./lazy.js");',
    '_astro/client.js': 'import*as r from"./react.js"',
    '_astro/react.js': 'export default 1',
    '_astro/lazy.js': 'export*from"./deep.js"',
    '_astro/deep.js': 'export const d=1',
    '_astro/unused.js': 'export const u=1',
  });
  try {
    const { page, external, inline } = routeScripts(dist, '/');
    assert.equal(page, pagePath(dist, '/'));
    assert.deepEqual(names(dist, external),
      ['_astro/Panel.js', '_astro/client.js', '_astro/deep.js', '_astro/lazy.js', '_astro/pre.js', '_astro/react.js', '_astro/theme.js', '_astro/toggle.js']);
    assert.deepEqual(inline, ['var t=1;'], 'the JSON-LD block and the blank script are not JavaScript the page runs');
  } finally {
    rmSync(dist, { recursive: true, force: true });
  }
});

test('a nested route, a page with no script at all, and the failures', () => {
  const dist = site({
    'atlas/index.html': '<script src="/_astro/gone.js"></script>',
    'api/index.html': '<main>static</main>',
    'bad/index.html': '<script src="/_astro/a.js"></script>',
    '_astro/a.js': 'import"./missing.js"',
  });
  try {
    assert.deepEqual(routeScripts(dist, '/api/'), { page: pagePath(dist, '/api/'), external: [], inline: [] });
    assert.throws(() => routeScripts(dist, '/atlas/'), /names \/_astro\/gone\.js, which is not in/);
    assert.throws(() => routeScripts(dist, '/bad/'), /imports \.\/missing\.js, which is not in/);
    assert.throws(() => routeScripts(dist, '/nowhere/'), /is missing: build the site first/);
    assert.equal(globSafe(join(dist, '_astro', 'a.js'), dist), '_astro/a.js');
    assert.throws(() => globSafe(join(dist, '_astro', '[slug].js'), dist), /glob metacharacter/);
  } finally {
    rmSync(dist, { recursive: true, force: true });
  }
});
