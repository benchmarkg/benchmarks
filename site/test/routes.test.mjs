// site/test/routes.test.mjs -- P2-S3-T04. Run after a build: cd site && npm run build && node --test test/routes.test.mjs
//
// One page per published system, organisation and metric, at /systems/{id}/, /orgs/{id}/ and /metrics/{id}/ (10
// "Information architecture"); each one's sources rendered on it as anchored blocks; and no /sources/{src-id}/
// route family (08 S7.5 Decision 4: a page per archived source document would bind the 20,000-file cap). The test
// reads the corpus the site was built from (UAIBI_CORPUS, else ../build/corpus.json, as src/lib/corpus.ts does) and
// the built dist/. The failure its verification names -- a /sources/ route family appearing -- is shown to fail on a
// throwaway dist that has one.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const DIST = join(SITE, 'dist');
const CORPUS = process.env.UAIBI_CORPUS ? resolve(SITE, process.env.UAIBI_CORPUS) : join(SITE, '..', 'build', 'corpus.json');
const ROUTES = { system: 'systems', organization: 'orgs', metric: 'metrics' };

const corpus = () => {
  assert.ok(existsSync(CORPUS), `${CORPUS} is missing: run \`uv run bench build\` before the site build, or every route is vacuously empty`);
  return JSON.parse(readFileSync(CORPUS, 'utf8')).entities;
};
const pages = (dir) => (existsSync(join(DIST, dir))
  ? readdirSync(join(DIST, dir)).filter((d) => existsSync(join(DIST, dir, d, 'index.html'))).sort()
  : []);

/** Every page under a dist that sits in a /sources/{id}/ route family: dist/sources/<anything>/index.html. The
 *  /sources/ index itself (the source-health page, P5-S7-T03) is a single page, not a family. */
export function sourceRouteFamily(dist) {
  const dir = join(dist, 'sources');
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((d) => statSync(join(dir, d)).isDirectory()).map((d) => `/sources/${d}/`);
}

for (const [kind, dir] of Object.entries(ROUTES)) {
  test(`one page per published ${kind}, at /${dir}/{id}/, and nothing else there`, () => {
    const ids = corpus()[kind].map((r) => r.id).sort();
    assert.ok(ids.length > 0, `the corpus publishes no ${kind}, so this would pass vacuously`);
    assert.deepEqual(pages(dir), ids);
  });

  test(`every ${kind} page carries its sources as anchored blocks and ships no JavaScript`, () => {
    for (const r of corpus()[kind]) {
      const html = readFileSync(join(DIST, dir, r.id, 'index.html'), 'utf8');
      for (const src of r.sources ?? []) {
        assert.match(html, new RegExp(`<li[^>]*id="${src}"[^>]*data-source-item="${src}"`), `${dir}/${r.id} anchors ${src}`);
      }
      assert.deepEqual([...html.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), ['<script data-prepaint>'], `${dir}/${r.id}`);
    }
  });
}

test('no /sources/{src-id}/ route family is generated', () => {
  assert.ok(existsSync(DIST), 'build the site first');
  assert.deepEqual(sourceRouteFamily(DIST), []);
  const pagesDir = join(SITE, 'src', 'pages');
  assert.ok(!existsSync(join(pagesDir, 'sources')), 'src/pages/sources/ would be a route family');
  assert.deepEqual(readdirSync(pagesDir).filter((f) => /^sources\b.*\[/.test(f)), []);
});

test('the check fails when a /sources/ route family appears', () => {
  const dist = mkdtempSync(join(tmpdir(), 'uaibi-dist-'));
  mkdirSync(join(dist, 'sources'));
  writeFileSync(join(dist, 'sources', 'index.html'), '<!doctype html>');
  assert.deepEqual(sourceRouteFamily(dist), []);                                  // the index page alone is fine
  mkdirSync(join(dist, 'sources', 'src-arxiv-2310-06770'));
  writeFileSync(join(dist, 'sources', 'src-arxiv-2310-06770', 'index.html'), '<!doctype html>');
  assert.deepEqual(sourceRouteFamily(dist), ['/sources/src-arxiv-2310-06770/']);
});

test('links between the records resolve: a system to its maker, an org to its systems, a metric to its users', () => {
  const e = corpus();
  const orgs = new Set(e.organization.map((o) => o.id));
  for (const s of e.system.filter((x) => x.organization != null && orgs.has(x.organization))) {
    const html = readFileSync(join(DIST, 'systems', s.id, 'index.html'), 'utf8');
    assert.ok(html.includes(`href="/orgs/${s.organization}/"`), `systems/${s.id} links its maker`);
    const org = readFileSync(join(DIST, 'orgs', s.organization, 'index.html'), 'utf8');
    assert.ok(org.includes(`href="/systems/${s.id}/"`), `orgs/${s.organization} lists ${s.id}`);
  }
  for (const b of e.benchmark) {
    for (const m of [b.headline_metric, ...(Array.isArray(b.metrics) ? b.metrics : [])].filter((x) => x != null && e.metric.some((r) => r.id === x))) {
      const html = readFileSync(join(DIST, 'metrics', m, 'index.html'), 'utf8');
      assert.ok(html.includes(`href="/benchmarks/${b.id}/"`), `metrics/${m} lists ${b.id}`);
    }
  }
});
