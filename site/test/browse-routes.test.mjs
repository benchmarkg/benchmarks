// site/test/browse-routes.test.mjs -- P2-S4-T01. Run after a build: cd site && npm run build && node --test test/browse-routes.test.mjs
//
// Done when: "About 390 single-facet pages exist and the test fails if /browse/domain/{d}/capability/{c}/ appears."
// 390 is 08 S7.5's estimate. The count is the vocabulary's: 455 term pages today, one per term of each field (execution's
// wet-lab is two), and the test holds the site to the taxonomy rather than to the estimate.
//
// Two sites are read. The first is dist/, which `npm run build` built over the corpus src/lib/corpus.ts reads
// (UAIBI_CORPUS, else ../build/corpus.json, where a missing file is an empty corpus). No entry is published yet, so
// today that is the empty corpus: one page per vocabulary term, each in its empty state, and no organisation page. The
// second is the populated case, a build this test makes itself over the draft preview, as contribute-links.test.mjs
// does. scripts/preview_corpus.py writes every entry that passes tier 1, drafts included, into
// build/site-browse-test/preview/, and the site builds from it into build/site-browse-test/dist/. That build reads an
// empty release feed (FEED_EVENTS), because no browse page reads the feed and feed.py's walk of git history is the
// slowest step of a build. Run this file on its own or with --test-concurrency=1. Two `astro build`s of one project at
// once share its content store (node_modules/.astro/) and race, and contribute-links.test.mjs builds too.
//
// Every expectation is computed here, independently of the site's reader (src/lib/browse.ts):
//   routes    one page per term of taxonomy/*.yaml, under the segment SEGMENTS gives its facet and field (10 V11's
//             spellings: /browse/access/, /browse/lifecycle/), plus /browse/org/{id}/ for each published organisation
//             that governance.maintainers names on a published benchmark, and nothing else under /browse/
//   members   from the facets.json and enums.json the S8 emitter writes beside the corpus (format 3): a term's members
//             are the rows whose facet array holds the term's key, a domain's are the rows whose domain (family) or
//             subdomain it is, and the corpus's domain.secondary entries are listed apart. An empty list must say so
//   review    a domain page carries its family's curation confidence, unreviewed while taxonomy/domains.yaml says
//             reviewer_signoff: none
//   no JS     the prepaint script and nothing else, and on the site as built every page within the record-page
//             budget (HTML <= 60 KB; the preview reports its largest page)
//   links     every /browse/ href anywhere in the site resolves to a page, and a benchmark is on every browse page
//             its own detail page links
// The failure the verification names (an intersection route such as /browse/domain/code/capability/planning/) is
// shown to be caught on a throwaway dist that has one.
//
// No benchmark in data/ names an organisation in governance.maintainers yet, so neither site has a /browse/org/
// page; the rule is held by calling src/lib/browse.ts (which Node loads, stripping its types) on records made here.
import { before, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load } from 'js-yaml';
import { browsePages } from '../src/lib/browse.ts';

const SITE = fileURLToPath(new URL('../', import.meta.url));
const ROOT = join(SITE, '..');
const DIST = join(SITE, 'dist');
const DIST_CORPUS = process.env.UAIBI_CORPUS ? resolve(SITE, process.env.UAIBI_CORPUS) : join(ROOT, 'build', 'corpus.json');
const WORK = join(ROOT, 'build', 'site-browse-test');
const PREVIEW = join(WORK, 'preview');
const POPULATED = join(WORK, 'dist');
// 10 "Performance budget": record pages, HTML <= 60 KB. It fails the site as built, which is what deploys. On the draft
// preview it is reported, not failed. A member line costs about 170 bytes and the page around it about 18 KB with its
// stylesheet inlined, so a term past about 250 members cannot fit on one page however the line is written (the
// preview's lifecycle `active` has 302). Whether to paginate a broad term or exempt /browse/ from the budget is the
// maintainer's decision, and a draft's growth should not fail on it. This test's own `astro build --outDir` emits no
// stylesheet, so the size it reports for the preview is the HTML without the ~11 KB `npm run build` inlines.
const BUDGET = 60 * 1024;

// 10 V11's segment for every facet and field a vocabulary file declares: a one-field facet browses under the facet, a
// field of a facet with several fields under the field. A field taxonomy/ gains fails the routes test until it is
// placed here.
const SEGMENTS = {
  domain: 'domain',
  capability: 'capability',
  evaluation_method: 'evaluation-method',
  subject: 'subject',
  'data_properties:data.access': 'access',
  'data_properties:data.refresh': 'refresh',
  'data_properties:data.data_provenance': 'data-provenance',
  'data_properties:data.contamination_risk': 'contamination-risk',
  'ceiling_anchor_type:data.ceiling_anchor_type': 'ceiling-anchor-type',
  'lifecycle:lifecycle': 'lifecycle',
  'lifecycle:activity': 'activity',
  'maintenance_status:maintenance_status': 'maintenance-status',
  'governance:governance.maintainer_type': 'maintainer-type',
  'governance:governance.submission_process': 'submission-process',
  'governance:governance.independence_flags': 'independence-flags',
  'execution:execution.compute_tier': 'compute-tier',
  'execution:execution.reproducibility_tier': 'reproducibility-tier',
  'execution:execution.reproducibility_blockers': 'reproducibility-blockers',
  'execution:execution.harness_availability': 'harness-availability',
};
const DERIVED = new Set(['maintenance_status']);   // 04 S5: computed from signals, which no build stage derives yet

/** Every term of every facet vocabulary in taxonomy/: [{facet, field, id, parent, segment, route, signoff}]. */
let memo;
function vocabulary() {
  if (memo) return memo;
  const dir = join(ROOT, 'taxonomy');
  const out = [];
  for (const name of readdirSync(dir).filter((f) => f.endsWith('.yaml')).sort()) {
    const doc = load(readFileSync(join(dir, name), 'utf8'));
    if (doc == null || typeof doc.facet !== 'string' || !Array.isArray(doc.terms)) continue;
    for (const t of doc.terms) {
      const key = t.field != null ? `${doc.facet}:${t.field}` : doc.facet;
      assert.ok(key in SEGMENTS, `taxonomy/${name}: ${key} has no browse segment; place it in SEGMENTS (10 V11)`);
      out.push({ facet: doc.facet, field: t.field ?? null, id: t.id, parent: t.parent ?? null, segment: SEGMENTS[key],
        route: `${SEGMENTS[key]}/${t.id}`, signoff: t.reviewer_signoff ?? 'none' });
    }
  }
  memo = out;
  return out;
}

const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));

/** The corpus a site was built from and the emitter's artifacts beside it. No corpus file is an empty corpus. */
function artifacts(corpusPath) {
  if (!existsSync(corpusPath)) return { benchmark: [], organization: [], rows: [], enums: null };
  const dir = dirname(corpusPath);
  for (const f of ['facets.json', 'enums.json']) assert.ok(existsSync(join(dir, f)), `${f} is not beside ${corpusPath}`);
  const facets = readJson(join(dir, 'facets.json'));
  assert.equal(facets.artifact, 'facets');
  assert.equal(facets.format, 3, 'facets.json format 3 is the row these expectations read (tools/build/emit.py)');
  const { entities } = readJson(corpusPath);
  return { benchmark: entities.benchmark ?? [], organization: entities.organization ?? [], rows: facets.benchmarks,
    enums: readJson(join(dir, 'enums.json')) };
}

/** route -> {primary: ids, secondary: ids} | 'derived', for every page the site must have. */
function expected(a) {
  const out = new Map();
  const ids = (xs) => xs.map((x) => x.id).sort();
  const flatOf = new Map(Object.entries(a.enums?.flat_facets ?? {}).flatMap(([flat, d]) => d.vocabularies.map((v) => [v, flat])));
  for (const t of vocabulary()) {
    if (DERIVED.has(t.facet)) {
      out.set(t.route, 'derived');
      continue;
    }
    if (t.facet === 'domain') {
      const inIt = (d) => d === t.id || d.startsWith(`${t.id}/`);
      const primary = a.rows.filter((r) => (t.parent == null ? r.domain === t.id : r.subdomain === t.id));
      const secondary = a.benchmark.filter((b) => !inIt(b.domain.primary) && (b.domain.secondary ?? []).some(inIt));
      out.set(t.route, { primary: ids(primary), secondary: ids(secondary) });
      continue;
    }
    let primary = [];
    if (a.rows.length > 0) {
      const flat = flatOf.get(t.facet);
      const key = a.enums.vocabularies[t.facet].terms.find((x) => x.id === t.id && (x.field ?? null) === t.field)?.key;
      assert.ok(flat != null && key != null, `enums.json places no ${t.facet}:${t.field ?? ''}:${t.id}`);
      primary = a.rows.filter((r) => r.facets[flat].includes(key));
    }
    out.set(t.route, { primary: ids(primary), secondary: [] });
  }
  for (const o of a.organization) {
    const maintained = a.benchmark.filter((b) => (b.governance?.maintainers ?? []).includes(o.id));
    if (maintained.length > 0) out.set(`org/${o.id}`, { primary: ids(maintained), secondary: [] });
  }
  return out;
}

/** Every page under `dist`/browse/, as its path below /browse/ (domain/code/repository-scale-se). */
function builtPages(dist) {
  const out = [];
  const walk = (dir, rel) => {
    for (const d of readdirSync(dir, { withFileTypes: true })) {
      if (d.isDirectory()) walk(join(dir, d.name), [...rel, d.name]);
      else if (d.name === 'index.html' && rel.length > 0) out.push(rel.join('/'));
    }
  };
  if (existsSync(join(dist, 'browse'))) walk(join(dist, 'browse'), []);
  return out.sort();
}

/** Every page under a dist that sits deeper than one facet value: /browse/{facet}/{term}/, with a domain value two
 *  segments deep (family/subdomain). /browse/domain/code/capability/planning/ is an intersection; so is any page
 *  with a second facet below the first. */
export function intersectionRoutes(dist) {
  return builtPages(dist).filter((p) => {
    const [facet, ...rest] = p.split('/');
    return rest.length > (facet === 'domain' ? 2 : 1);
  }).map((p) => `/browse/${p}/`);
}

const html = (dist, route) => readFileSync(join(dist, 'browse', ...route.split('/'), 'index.html'), 'utf8');
const list = (page, which) => {
  const m = new RegExp(`<ul[^>]*data-list="${which}"[^>]*>([\\s\\S]*?)</ul>`).exec(page);
  return m == null ? [] : [...m[1].matchAll(/<li[^>]*data-member="([^"]+)"/g)].map((x) => x[1]).sort();
};

/** Every html file under `dist`, as [path relative to dist, contents]. */
function allPages(dist) {
  const out = [];
  const walk = (dir) => {
    for (const d of readdirSync(dir, { withFileTypes: true })) {
      if (d.isDirectory()) walk(join(dir, d.name));
      else if (d.name.endsWith('.html')) out.push([join(dir, d.name).slice(dist.length + 1).replace(/\\/g, '/'), readFileSync(join(dir, d.name), 'utf8')]);
    }
  };
  walk(dist);
  return out;
}

/** The checks both sites must pass. `gate` makes the record-page budget a failure, on the site as built; on the draft
 *  preview the largest page is reported instead (see the note on BUDGET). */
function checks(name, dist, corpusPath, gate) {
  test(`${name}: one page per single-facet value, plus one per maintaining organisation, and no other page under /browse/`, () => {
    assert.ok(existsSync(dist), `${dist} is missing: build the site first`);
    const want = expected(artifacts(corpusPath));
    const terms = vocabulary();
    assert.equal(new Set(terms.map((t) => t.route)).size, terms.length, 'two terms would share a URL');
    assert.ok(terms.length >= 390, `${terms.length} single-facet pages; about 390 at launch (08 S7.5)`);
    assert.deepEqual(builtPages(dist), [...want.keys()].sort());
    assert.deepEqual(intersectionRoutes(dist), []);
  });

  test(`${name}: each page lists exactly its members, primary and secondary apart, or says it has none`, () => {
    for (const [route, want] of expected(artifacts(corpusPath))) {
      const page = html(dist, route);
      if (want === 'derived') {
        assert.ok(page.includes('data-derived'), `${route} says its members are derived`);
        assert.deepEqual(list(page, 'primary'), [], route);
        continue;
      }
      assert.deepEqual(list(page, 'primary'), want.primary, `${route}: primary members`);
      assert.deepEqual(list(page, 'secondary'), want.secondary, `${route}: secondary members`);
      assert.ok(page.includes(`data-count="${want.primary.length + want.secondary.length}"`), `${route}: its count`);
      if (want.primary.length === 0) assert.ok(/data-empty="(term|primary|domain-page|domain-unreviewed)"/.test(page), `${route} says it is empty`);
    }
  });

  test(`${name}: a domain page says whether its family is review-backed (14 Phase 1, "The honest gate")`, () => {
    const terms = vocabulary();
    const signoff = new Map(terms.filter((t) => t.facet === 'domain' && t.parent == null).map((t) => [t.id, t.signoff]));
    for (const t of terms.filter((x) => x.facet === 'domain')) {
      const want = signoff.get(t.parent ?? t.id);
      assert.ok(html(dist, t.route).includes(`data-curation-confidence="${want === 'none' ? 'unreviewed' : want}"`), t.route);
    }
  });

  test(`${name}: every page ships no JavaScript${gate ? ' and fits the record-page budget' : ''}`, (t) => {
    let largest = ['', 0];
    for (const route of builtPages(dist)) {
      const page = html(dist, route);
      assert.deepEqual([...page.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]), ['<script data-prepaint>'], route);
      const size = Buffer.byteLength(page);
      if (size > largest[1]) largest = [route, size];
      if (gate) assert.ok(size <= BUDGET, `/browse/${route}/ is ${size} bytes, over the record-page budget of ${BUDGET}`);
    }
    t.diagnostic(`largest: /browse/${largest[0]}/ at ${largest[1]} bytes of the ${BUDGET}-byte record-page budget`);
  });

  test(`${name}: every /browse/ link in the site resolves, and a benchmark is on every browse page its detail page links`, () => {
    const built = new Set(builtPages(dist));
    for (const [path, page] of allPages(dist)) {
      for (const m of page.matchAll(/href="\/browse\/([^"#?]+?)\/"/g)) {
        assert.ok(built.has(m[1]), `${path} links /browse/${m[1]}/, which is no page`);
        const own = /^benchmarks\/([^/]+)\/index\.html$/.exec(path);
        if (own != null) {
          const target = html(dist, m[1]);
          assert.ok([...list(target, 'primary'), ...list(target, 'secondary')].includes(own[1]), `/browse/${m[1]}/ lists ${own[1]}, which links it`);
        }
      }
    }
  });
}

// The populated case: the draft preview, built once before any test runs.
before(() => {
  const win = process.platform === 'win32';
  // relative to the repository root: on Windows `uv` needs a shell, and a shell splits the root's path at its spaces
  let r = spawnSync('uv', ['run', 'python', 'scripts/preview_corpus.py', '--out', 'build/site-browse-test/preview'], { cwd: ROOT, encoding: 'utf8', shell: win });
  assert.equal(r.status, 0, r.stderr);
  writeFileSync(join(WORK, 'feed-events.json'), '[]\n');
  r = spawnSync(process.execPath, [join(SITE, 'node_modules', 'astro', 'bin', 'astro.mjs'), 'build', '--outDir', POPULATED], {
    cwd: SITE, encoding: 'utf8',
    env: { ...process.env, UAIBI_CORPUS: join(PREVIEW, 'corpus.json'), UAIBI_SITE_DRAFTS: '1', FEED_EVENTS: join(WORK, 'feed-events.json'),
      ASTRO_TELEMETRY_DISABLED: '1' },
  });
  assert.equal(r.status, 0, (r.stdout ?? '').slice(-3000) + (r.stderr ?? '').slice(-3000));
});

checks('the site as built (dist/)', DIST, DIST_CORPUS, true);

const populated = existsSync(DIST_CORPUS) && readJson(DIST_CORPUS).entities.benchmark.length > 0;
// 09 S6.10's domain-page empty state calls the gap a finding, which 14 Phase 1's honest gate refuses in a family no
// reviewer has signed; such a domain says it is empty without asserting a gap.
test('the empty corpus: every page is in its empty state, and no unreviewed domain asserts a gap', { skip: populated && 'dist/ was built over a populated corpus' }, () => {
  const terms = vocabulary();
  const signoff = new Map(terms.filter((t) => t.facet === 'domain' && t.parent == null).map((t) => [t.id, t.signoff]));
  assert.deepEqual(builtPages(DIST).filter((p) => p.startsWith('org/')), []);
  for (const t of terms) {
    const page = html(DIST, t.route);
    const unsigned = t.facet === 'domain' && signoff.get(t.parent ?? t.id) === 'none';
    const want = DERIVED.has(t.facet) ? 'data-derived' : t.facet !== 'domain' ? 'data-empty="term"'
      : unsigned ? 'data-empty="domain-unreviewed"' : 'data-empty="domain-page"';
    assert.ok(page.includes(want), `${t.route}: ${want}`);
    if (unsigned) assert.ok(!page.includes('the gap is a finding'), `${t.route} asserts a gap in an unreviewed family`);
  }
});

test('the check fails on a dist with an intersection route', () => {
  const dist = mkdtempSync(join(tmpdir(), 'uaibi-browse-'));
  const page = (...parts) => {
    mkdirSync(join(dist, 'browse', ...parts), { recursive: true });
    writeFileSync(join(dist, 'browse', ...parts, 'index.html'), '<!doctype html>');
  };
  page('capability', 'planning');
  page('domain', 'code');
  page('domain', 'code', 'repository-scale-se');
  assert.deepEqual(intersectionRoutes(dist), []);                                  // single-facet pages alone are fine
  page('domain', 'code', 'capability', 'planning');
  page('domain', 'code', 'repository-scale-se', 'capability', 'planning');
  page('capability', 'planning', 'domain', 'code');
  assert.deepEqual(intersectionRoutes(dist), ['/browse/capability/planning/domain/code/', '/browse/domain/code/capability/planning/',
    '/browse/domain/code/repository-scale-se/capability/planning/']);
});

test('no other browse route is declared: src/pages/browse/ holds the one single-facet route', () => {
  const dir = join(SITE, 'src', 'pages', 'browse');
  const files = [];
  const walk = (d, rel) => {
    for (const e of readdirSync(d)) (statSync(join(d, e)).isDirectory() ? walk(join(d, e), [...rel, e]) : files.push([...rel, e].join('/')));
  };
  walk(dir, []);
  assert.deepEqual(files, ['[facet]/[...term].astro']);
});

// ---- src/lib/browse.ts on records made here -------------------------------------------------------------------

const record = (id, name, primary, more = {}) => ({ id, name, tagline: 'x', domain: { primary, secondary: more.secondary ?? [] },
  data: {}, governance: { maintainers: more.maintainers ?? [] }, execution: more.execution ?? {}, capability: more.capability ?? [] });
const find = (pages, segment, id) => pages.find((p) => p.segment === segment && (p.kind === 'org' ? p.org.id : p.term.id) === id);

test('browsePages: an organisation has a page only when a published benchmark names it as a maintainer', () => {
  const pages = browsePages([
    record('beta-bench', 'Beta', 'code/repository-scale-se', { maintainers: ['org-lab'] }),
    record('alpha-bench', 'Alpha', 'mathematics/formal-theorem-proving', { maintainers: ['org-lab', 'org-unpublished'] }),
  ], [{ id: 'org-lab', name: 'A lab', kind: 'academic-lab', sources: ['src-x'] }, { id: 'org-maker', name: 'A maker', kind: 'company', sources: ['src-y'] }]);
  assert.deepEqual(pages.filter((p) => p.kind === 'org').map((p) => [p.org.id, p.members.map((m) => m.benchmark.id)]),
    [['org-lab', ['alpha-bench', 'beta-bench']]]);                                // by name; org-maker maintains nothing
  assert.equal(pages.filter((p) => p.kind === 'term').length, vocabulary().length);
});

test('browsePages: primary and secondary apart, wet-lab as two pages, and a derived term listing no one', () => {
  const pages = browsePages([
    record('beta-bench', 'Beta', 'code/repository-scale-se', { capability: ['planning'], execution: { compute_tier: 'wet-lab' } }),
    record('alpha-bench', 'Alpha', 'mathematics/formal-theorem-proving', { secondary: ['code/repository-scale-se'] }),
  ], []);
  const members = (seg, id) => find(pages, seg, id).members.map((m) => [m.benchmark.id, m.secondary]);
  assert.deepEqual(members('domain', 'code/repository-scale-se'), [['alpha-bench', true], ['beta-bench', false]]);
  assert.deepEqual(members('domain', 'code'), [['alpha-bench', true], ['beta-bench', false]]);
  assert.deepEqual(members('capability', 'planning'), [['beta-bench', false]]);
  assert.deepEqual(members('compute-tier', 'wet-lab'), [['beta-bench', false]]);
  assert.deepEqual(members('reproducibility-blockers', 'wet-lab'), []);
  assert.equal(pages.find((p) => p.segment === 'maintenance-status').members, null);
  const code = find(pages, 'domain', 'code');
  assert.ok(code.children.length > 0 && code.children.every((c) => c.term.parent === 'code'));
  assert.equal(code.families.length, vocabulary().filter((t) => t.facet === 'domain' && t.parent == null).length);
});

test('browsePages refuses two vocabularies under one segment, and a vocabulary under /browse/org/', () => {
  const root = mkdtempSync(join(tmpdir(), 'uaibi-browse-taxonomy-'));
  mkdirSync(join(root, 'taxonomy'));
  const file = (name, facet, id, field) => writeFileSync(join(root, 'taxonomy', name),
    `facet: ${facet}\nterms:\n  - id: ${id}\n    label: ${id}\n    status: active\n    definition: d\n    field: ${field}\n`);
  file('a.yaml', 'alpha', 'open', 'data.access');
  file('b.yaml', 'beta', 'closed', 'records.access');
  assert.throws(() => browsePages([], [], root), /\/browse\/access\/ would hold two vocabularies/);
  file('b.yaml', 'beta', 'closed', 'org');
  assert.throws(() => browsePages([], [], root), /organisation route/);
});

// ---- the populated case: the draft preview -------------------------------------------------------------------

checks('the draft preview', POPULATED, join(PREVIEW, 'corpus.json'), false);

test('the draft preview: the populated case is not vacuous', () => {
  const want = expected(artifacts(join(PREVIEW, 'corpus.json')));
  const lists = [...want.values()].filter((w) => w !== 'derived');
  assert.ok(lists.filter((w) => w.primary.length > 0).length >= 100, 'at least a hundred pages with members');
  assert.ok(lists.some((w) => w.secondary.length > 0), 'a domain page with a secondary member');
  assert.ok(lists.some((w) => w.primary.length === 0), 'a term no benchmark carries, still a page');
  const page = html(POPULATED, 'domain/code');
  assert.match(page, /<h2 id="s-subdomains"[^>]*>Subdomains of Code/);
  assert.match(page, /data-neighbours="families"/);
});
