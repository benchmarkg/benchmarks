// site/test/size-budgets.test.mjs -- P2-S8-T01 (08 S8.1, 10 "Performance budget"). The route groups and the gate they
// make, scripts/route_groups.mjs over scripts/route_groups.json:
//
//   cd site && node --test test/size-budgets.test.mjs
//
// Done when: "All three budgets are enforced per route group and the fixture that adds JS to a detail route turns the
// job red." The first tests read small built sites written here, so every page and file the gate should and should not
// count is known: which family a page is, what a 0 KB page may carry (the pre-paint line, once, the same everywhere),
// which fonts a page's weight counts. The last runs size-limit itself, the way pr-validate.yml's size-budgets job does,
// over the built site/dist/ -- green -- and over test/fixtures/size-detail-js.mjs's copy of it, in which one detail page
// loads 1 KB of JavaScript -- red, on that family's check. It is skipped, with a reason, until dist/ holds a build over
// the draft preview, the only build with detail pages in it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';
import {
  assignPages, builtRoutes, fontFaces, loadGroups, pageFiles, routeRegExp, sizeLimitChecks, usedFamilies,
} from '../../scripts/route_groups.mjs';
import { pagePath } from '../../scripts/route_js.mjs';
import { DETAIL, ONE_KB, SCRIPT } from './fixtures/size-detail-js.mjs';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const SITE = join(ROOT, 'site');
const DIST = join(SITE, 'dist');

function site(files) {
  const dist = mkdtempSync(join(tmpdir(), 'size-budgets-'));
  for (const [rel, body] of Object.entries(files)) {
    mkdirSync(dirname(join(dist, rel)), { recursive: true });
    writeFileSync(join(dist, rel), body);
  }
  return dist;
}
const names = (dist, files) => files.map((f) => f.slice(dist.length + 1).split('\\').join('/'));
const fam = (route, js, more = {}) => ({ route, js, group: 'g', title: 'G', ...more });

// ---- route patterns and page assignment ----------------------------------------------------------------------------

test('a route pattern: {name} is one path segment, {...name} one or more', () => {
  const detail = routeRegExp('/benchmarks/{id}/');
  assert.ok(detail.test('/benchmarks/mmlu/'));
  for (const r of ['/benchmarks/', '/benchmarks/mmlu/v/1.0/', '/benchmarks/mmlu']) assert.ok(!detail.test(r), r);
  const term = routeRegExp('/browse/{facet}/{...term}/');
  assert.ok(term.test('/browse/domain/code/') && term.test('/browse/domain/code/repository-scale-se/'));
  assert.ok(!term.test('/browse/domain/'));
  assert.ok(routeRegExp('/').test('/') && !routeRegExp('/').test('/atlas/'));
});

test('every built page has one family: an unclaimed page, a page two families claim and an empty family all throw', () => {
  const dist = site({
    'index.html': '<p>landing</p>',
    'benchmarks/a/index.html': '<p>a</p>',
    'benchmarks/b/index.html': '<p>b</p>',
    '_fixtures/theme/index.html': '<p>test page</p>',
    'feed.xml': '<rss/>',
  });
  try {
    const routes = builtRoutes(dist);
    assert.deepEqual(routes, ['/', '/_fixtures/theme/', '/benchmarks/a/', '/benchmarks/b/'], 'pages only, not feed.xml');
    const ignored = [{ route: '/_fixtures/{name}/' }];
    const fams = [fam('/', '40 KiB'), fam('/benchmarks/{id}/', '0 B'), fam('/claims/{id}/', '0 B', { pending: 'P3-S10-T07' })];
    assert.deepEqual(assignPages({ families: fams, ignored }, routes).map((f) => [f.route, f.pages]),
      [['/', ['/']], ['/benchmarks/{id}/', ['/benchmarks/a/', '/benchmarks/b/']], ['/claims/{id}/', []]]);
    assert.throws(() => assignPages({ families: fams.slice(0, 2), ignored: [] }, routes), /no family .* claims 1 built page\(s\), so no budget gates them: \/_fixtures\/theme\//);
    assert.throws(() => assignPages({ families: [...fams, fam('/benchmarks/{x}/', '0 B')], ignored }, routes), /claimed by \/benchmarks\/\{id\}\/ and \/benchmarks\/\{x\}\//);
    assert.throws(() => assignPages({ families: [...fams, fam('/orgs/{id}/', '0 B')], ignored }, routes), /no page was built for \/orgs\/\{id\}\/, so the gate would measure nothing/);
    writeFileSync(join(dist, '404.html'), '<p>gone</p>');
    assert.throws(() => builtRoutes(dist), /404\.html: a page that is not <route>\/index\.html/);
  } finally {
    rmSync(dist, { recursive: true, force: true });
  }
});

test('route_groups.json: the three groups, the ledger\'s budgets, and each pending family still unrouted', () => {
  const { families } = loadGroups();
  assert.deepEqual([...new Set(families.map((f) => f.group))], ['citable', 'interactive', 'atlas']);
  assert.equal(new Set(families.map((f) => f.route)).size, families.length, 'one row per route');
  const row = (route) => families.find((f) => f.route === route);
  for (const route of ['/benchmarks/{id}/', '/claims/{id}/', '/conditions/{id}/']) assert.equal(row(route).js, '0 B', route);
  assert.equal(row('/benchmarks/{id}/').weight, '120 KiB');
  assert.equal(row('/atlas/').js, '120 KiB');
  assert.equal(row('/').js, '40 KiB');
  for (const f of families.filter((x) => x.group === 'citable')) assert.equal(f.js, '0 B', f.route);
  for (const f of families.filter((x) => x.pending)) {
    assert.match(f.pending, /^P\d-S\d+-T\d+$/, f.route);
    assert.ok(!existsSync(join(ROOT, f.page)), `${f.page} exists now: drop ${f.route}'s pending in scripts/route_groups.json, so a build `
      + 'with no such page fails rather than passing it');
  }
});

// ---- what a check measures ------------------------------------------------------------------------------------------

const PREPAINT = '<script data-prepaint>try{var t=1}catch(e){}</script>';
const FACES = '@font-face{font-family:"Plex";src:url("/fonts/sans.woff2") format("woff2");font-style:normal}'
  + '@font-face{font-family:"Plex";src:url("/fonts/italic.woff2") format("woff2");font-style:italic}'
  + '@font-face{font-family:"Plex Mono";src:url("/fonts/mono.woff2") format("woff2")}'
  + '@font-face{font-family:"Plex Cond";src:url("/fonts/cond.woff2") format("woff2")}'
  + '@font-face{font-family:"Fallback";src:local("Arial")}'
  + ':root{--font-sans:"Plex","Fallback",sans-serif;--font-cond:"Plex Cond",sans-serif}body{font-family:var(--font-sans)}';

test('the fonts a page counts: the families its CSS sets, the italic only beside italic text, the preloads always', () => {
  assert.deepEqual(fontFaces(FACES).map((f) => [f.family, f.style, f.url]),
    [['Plex', 'normal', '/fonts/sans.woff2'], ['Plex', 'italic', '/fonts/italic.woff2'], ['Plex Mono', 'normal', '/fonts/mono.woff2'],
      ['Plex Cond', 'normal', '/fonts/cond.woff2']], 'a local() face downloads nothing');
  assert.deepEqual([...usedFamilies(FACES)], ['plex', 'fallback', 'sans-serif'], '--font-cond is defined but nothing sets it');
  assert.ok(usedFamilies('.x{font:600 1rem/1.2 var(--f)}:root{--f:"Plex Cond"}').has('plex cond'), 'the font shorthand counts');
  const dist = site({
    'plain/index.html': `<html><head><style>${FACES}</style>`
      + '<link rel="preload" href="/fonts/mono.woff2" as="font" type="font/woff2" crossorigin>'
      + '<link rel="stylesheet" href="/_astro/page.css"></head><body><p>text</p><img src="/img/a.svg"></body></html>',
    'italic/index.html': `<html><head><style>${FACES}</style></head><body><p>a <em>word</em></p></body></html>`,
    '_astro/page.css': '.card{color:red}',
    'img/a.svg': '<svg/>',
    'fonts/sans.woff2': 's', 'fonts/italic.woff2': 'i', 'fonts/mono.woff2': 'm', 'fonts/cond.woff2': 'c',
  });
  try {
    assert.deepEqual(names(dist, pageFiles(dist, '/plain/')),
      ['_astro/page.css', 'fonts/mono.woff2', 'fonts/sans.woff2', 'img/a.svg', 'plain/index.html']);
    assert.deepEqual(names(dist, pageFiles(dist, '/italic/')), ['fonts/italic.woff2', 'fonts/sans.woff2', 'italic/index.html']);
  } finally {
    rmSync(dist, { recursive: true, force: true });
  }
});

test('the checks: 0 B counts every script byte but the pre-paint line, a budget the heaviest page, weight its files', () => {
  const page = (body) => `<html><head>${PREPAINT}<style>${FACES}</style></head><body>${body}</body></html>`;
  const dist = site({
    'index.html': page('<script type="module" src="/_astro/toggle.js"></script>'),
    'benchmarks/a/index.html': page('<p>a</p>'),
    'benchmarks/b/index.html': page('<p>b</p><script>var late=1;</script>'),
    'atlas/index.html': page('<astro-island component-url="/_astro/Atlas.js"></astro-island>'),
    '_astro/toggle.js': 'export const t=1;',
    '_astro/Atlas.js': 'import"./sigma.js";',
    '_astro/sigma.js': 'export default 1;',
    'fonts/sans.woff2': 's', 'fonts/italic.woff2': 'i', 'fonts/mono.woff2': 'm', 'fonts/cond.woff2': 'c',
  });
  const cache = join(dist, '.cache');
  const groups = {
    families: [fam('/', '40 KiB'), fam('/benchmarks/{id}/', '0 B', { weight: '120 KiB' }), fam('/claims/{id}/', '0 B', { pending: 'P3-S10-T07' }),
      fam('/atlas/', null, { budget: 'why' })],
    ignored: [],
  };
  try {
    const checks = sizeLimitChecks({ dist, cache, from: dist, groups });
    const by = (part) => checks.filter((c) => c.name.includes(part));
    const [zero] = by('/benchmarks/{id}/ JavaScript');
    assert.equal(zero.name, 'g: /benchmarks/{id}/ JavaScript on all 2 pages, raw bytes, 09 S9\'s pre-paint line allowed');
    assert.deepEqual([zero.limit, zero.brotli, zero.gzip], ['0 B', false, undefined]);
    assert.equal(zero.path.length, 2, 'the empty file, and the one inline script that is not the pre-paint line');
    assert.equal(readFileSync(join(dist, zero.path[0]), 'utf8'), '');
    assert.equal(readFileSync(join(dist, zero.path[1]), 'utf8'), 'var late=1;');
    const [weight] = by('page weight');
    assert.match(weight.name, /the heaviest of 2 pages \(\/benchmarks\/b\/\)$/);
    assert.deepEqual([weight.limit, weight.brotli, weight.gzip], ['120 KiB', false, undefined]);
    assert.equal(weight.path.length, 2);
    assert.match(weight.path[0], /^\.cache\/weight-\d+-index\.html\.gz$/, 'the HTML as its gzip -9 copy');
    assert.equal(gunzipSync(readFileSync(join(dist, weight.path[0]))).toString(), readFileSync(join(dist, 'benchmarks', 'b', 'index.html'), 'utf8'));
    assert.equal(weight.path[1], 'fonts/sans.woff2', 'the font as it is sent');
    const [landing] = by('g: / JavaScript');
    assert.deepEqual([landing.limit, landing.gzip, landing.path.slice(0, 1)], ['40 KiB', true, ['_astro/toggle.js']]);
    assert.equal(readFileSync(join(dist, landing.path[1]), 'utf8'), 'try{var t=1}catch(e){}', 'a budgeted route counts the pre-paint line');
    const [claims] = by('/claims/{id}/');
    assert.equal(claims.name, 'g: /claims/{id}/ JavaScript: no page built yet, P3-S10-T07 routes it');
    const [atlas] = by('/atlas/');
    assert.ok(!('limit' in atlas) && atlas.name.endsWith('no budget yet (scripts/route_groups.json says why)'));
    assert.deepEqual(atlas.path.slice(0, 2), ['_astro/Atlas.js', '_astro/sigma.js']);
    writeFileSync(join(dist, 'benchmarks', 'a', 'index.html'), page('').replace('var t=1', 'var t=2'));
    assert.throws(() => sizeLimitChecks({ dist, cache, from: dist, groups }), /the pre-paint line differs between pages/);
  } finally {
    rmSync(dist, { recursive: true, force: true });
  }
});

// ---- the gate itself, and the fixture that turns it red -------------------------------------------------------------

const hasDetail = existsSync(join(DIST, 'index.html')) && builtRoutes(DIST).some((r) => routeRegExp(DETAIL).test(r));
const sizeLimit = (env = {}) => {
  const r = spawnSync(process.execPath, [join(SITE, 'node_modules', 'size-limit', 'bin.js'), '--json'], {
    cwd: SITE, encoding: 'utf8', env: { ...process.env, UAIBI_SIZE_FIXTURE: '', ...env },
  });
  return { code: r.status, checks: r.stdout.trim().startsWith('[') ? JSON.parse(r.stdout) : null, out: r.stdout + r.stderr };
};

test('npx size-limit passes over the built site, and the fixture that adds 1 KB of JS to a detail route turns it red', {
  skip: hasDetail ? false : 'site/dist/ has no detail page: build it over the draft preview (site/.size-limit.js says how)',
}, () => {
  const green = sizeLimit();
  assert.equal(green.code, 0, green.out);
  assert.ok(green.checks.every((c) => c.passed !== false), green.out);
  const named = (checks, part) => checks.filter((c) => c.name.includes(part));
  assert.equal(named(green.checks, 'citable: /benchmarks/{id}/ JavaScript')[0].size, 0);

  const red = sizeLimit({ UAIBI_SIZE_FIXTURE: 'detail-js' });
  assert.equal(red.code, 1, red.out);
  const failed = red.checks.filter((c) => c.passed === false);
  assert.deepEqual(failed.map((c) => [c.name.split(' JavaScript')[0], c.size]), [['citable: /benchmarks/{id}/', ONE_KB.length]], red.out);
  assert.equal(ONE_KB.length, 1024);
  const first = builtRoutes(DIST).find((r) => routeRegExp(DETAIL).test(r));
  assert.ok(!readFileSync(pagePath(DIST, first), 'utf8').includes(SCRIPT), 'dist/ itself is untouched');
});
