// site/test/taxonomy-routes.test.mjs -- P2-S3-T05. Run after a build: cd site && npm run build && node --test test/taxonomy-routes.test.mjs
//
// Done when: "One page exists per vocabulary term (446 at launch) and /api/ states the four contracts with its
// deprecation rule." The term count is read here from taxonomy/*.yaml, independently of the site's own reader: one
// page per facet-qualified id, which is the raw term count less the ids a file repeats across fields (9c allows
// execution's `wet-lab` as a compute tier and as a reproducibility blocker; its page carries both). The failure the
// verification names -- a term with no page -- is shown to be caught on a throwaway dist missing one.
//
// The three narrative documents render at /docs/{slug}/, /methodology/ still resolves (a static redirect), and the
// quotation the methodology page carries is checked word for word against its Source record's extract.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'js-yaml';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const ROOT = join(SITE, '..');
const DIST = join(SITE, 'dist');
const page = (...parts) => readFileSync(join(DIST, ...parts, 'index.html'), 'utf8');
const text = (html) => html.replace(/<style[^>]*>[\s\S]*?<\/style>/g, ' ').replace(/<[^>]+>/g, ' ')
  .replace(/&#39;|&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/\s+/g, ' ');
const squash = (s) => s.replace(/\s+/g, ' ').trim();

/** Every facet file's terms: [{facet, id, entries}] with one row per facet-qualified id. */
function vocabulary() {
  const dir = join(ROOT, 'taxonomy');
  const out = [];
  for (const name of readdirSync(dir).filter((f) => f.endsWith('.yaml')).sort()) {
    const doc = load(readFileSync(join(dir, name), 'utf8'));
    if (doc == null || typeof doc.facet !== 'string' || !Array.isArray(doc.terms)) continue;
    const byId = new Map();
    for (const t of doc.terms) byId.set(t.id, [...(byId.get(t.id) ?? []), t]);
    for (const [id, entries] of byId) out.push({ facet: doc.facet, id, entries });
  }
  return out;
}
const segment = (facet) => facet.replace(/_/g, '-');

/** The facet-qualified ids with no page under `dist`. */
export function missingTermPages(dist, terms) {
  return terms.filter((t) => !existsSync(join(dist, 'taxonomy', segment(t.facet), ...t.id.split('/'), 'index.html')))
    .map((t) => `${t.facet}:${t.id}`);
}

test('one page per vocabulary term, and no other page under /taxonomy/', () => {
  const terms = vocabulary();
  const entries = terms.reduce((n, t) => n + t.entries.length, 0);
  assert.ok(terms.length >= 446, `${terms.length} terms; 446 at launch`);
  assert.deepEqual(terms.filter((t) => t.entries.length > 1).map((t) => `${t.facet}:${t.id}`), ['execution:wet-lab']);
  assert.equal(terms.length, entries - 1);
  assert.deepEqual(missingTermPages(DIST, terms), []);
  const built = [];
  const walk = (dir, rel) => {
    for (const d of readdirSync(dir, { withFileTypes: true })) {
      if (d.isDirectory()) walk(join(dir, d.name), [...rel, d.name]);
      else if (d.name === 'index.html') built.push(rel.join('/'));
    }
  };
  walk(join(DIST, 'taxonomy'), []);
  assert.equal(built.length, terms.length, 'as many pages as terms, so no stray page either');
});

test('the check fails on a dist missing a term page', () => {
  const dist = mkdtempSync(join(tmpdir(), 'uaibi-terms-'));
  mkdirSync(join(dist, 'taxonomy', 'capability', 'planning'), { recursive: true });
  writeFileSync(join(dist, 'taxonomy', 'capability', 'planning', 'index.html'), '<!doctype html>');
  assert.deepEqual(missingTermPages(dist, [{ facet: 'capability', id: 'planning' }, { facet: 'evaluation_method', id: 'exact-match' }]),
    ['evaluation_method:exact-match']);
});

test('each term page carries the taxonomy prose verbatim: definition, tests and near misses', () => {
  for (const t of vocabulary()) {
    // compared without whitespace: an inline `code` span renders as <code>, whose tags leave spaces in the text
    const body = text(page('taxonomy', segment(t.facet), ...t.id.split('/'))).replace(/\s/g, '');
    for (const e of t.entries) {
      for (const field of ['definition', 'inclusion_test', 'exclusion_test']) {
        if (typeof e[field] !== 'string') continue;
        const head = squash(e[field].replace(/`/g, '')).slice(0, 60);
        assert.ok(body.includes(head.replace(/\s/g, '')), `${t.facet}:${t.id} ${field}: ${head}`);
      }
      for (const ex of (e.examples ?? []).filter((x) => x.qualifies === false)) {
        assert.ok(body.includes(`${ex.ref}doesnotqualify`), `${t.facet}:${t.id} near miss ${ex.ref}`);
      }
    }
  }
});

test('a term an id repeats across fields is one page with every sense', () => {
  const html = page('taxonomy', 'execution', 'wet-lab');
  assert.match(html, /data-senses="2"/);
  assert.match(html, /data-sense="execution\.compute_tier"/);
  assert.match(html, /data-sense="execution\.reproducibility_blockers"/);
});

test('the three documents render at /docs/{slug}/, and /methodology/ still resolves', () => {
  for (const slug of ['methodology', 'provenance', 'comparability']) {
    const md = readFileSync(join(ROOT, 'docs', `${slug}.md`), 'utf8');
    const title = /^title: (.+)$/m.exec(md)[1];
    assert.match(page('docs', slug), new RegExp(`<h1[^>]*>${title}</h1>`), slug);
  }
  const redirect = page('methodology');
  assert.match(redirect, /http-equiv="refresh" content="0;url=\/docs\/methodology\/"/);
  assert.equal((redirect.match(/<script/g) ?? []).length, 0);
});

test('the methodology page carries 02 S11 rule 1 and the quotation its Source record holds', () => {
  const body = text(page('docs', 'methodology'));
  assert.ok(body.includes('density = n_primary + 0.5 × n_secondary'));
  assert.ok(body.includes('weighted benchmark count'));
  const src = load(readFileSync(join(ROOT, 'data', 'sources', '2026', 'src-hf-open-llm-leaderboard-end.yaml'), 'utf8'));
  const quote = /<blockquote>([\s\S]*?)<\/blockquote>/.exec(page('docs', 'methodology'))[1];
  const said = squash(text(quote));
  assert.ok(squash(src.quote_extract).toLowerCase().includes(said.toLowerCase()), `not in the source's extract: ${said}`);
  assert.ok(page('docs', 'methodology').includes(`href="${src.archive_url}"`), 'the archive copy is linked');
});

test('/api/ says it is not an API, states the four contracts and the deprecation rule', () => {
  const html = page('api');
  const body = text(html);
  assert.ok(body.includes('/api/ is not an API.'));
  for (const artifact of ['corpus.json', 'facets.json', 'claims.json, claims-ingested/<id>.json', 'index.sqlite and the data tarball', 'The YAML itself']) {
    assert.ok(html.includes(`data-artifact="${artifact}"`), artifact);
  }
  for (const contract of ['additive within a major schema version', 'kept apart, by path and by label', 'frozen at its tag', 'never expires']) {
    assert.ok(body.includes(contract), contract);
  }
  assert.match(html, /data-rule="deprecation"/);
  assert.ok(body.includes('A deprecation is announced one release before it lands'));
});

test('the narrative and term pages ship no JavaScript of their own', () => {
  for (const html of [page('api'), page('docs', 'methodology'), page('taxonomy', 'capability', 'knowledge-recall'), page('taxonomy', 'domain', 'code', 'repository-scale-se')]) {
    assert.deepEqual([...html.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), ['<script data-prepaint>']);
  }
});
