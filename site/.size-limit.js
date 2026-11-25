// site/.size-limit.js -- P2-S4-T08, P2-S8-T01 (08 S8.1, 10 "Performance budget"). The per-route size gate, run over a
// built site:
//
//   cd site && npm run build && npx size-limit                   # every route group against its budget
//   cd site && UAIBI_SIZE_FIXTURE=detail-js npx size-limit       # the fixture: 1 KB of JS on a detail route, red
//
// 08 S8.1 makes the route budgets blocking because they are deterministic, computed from artifacts: size-limit
// (@size-limit/file, no bundler and no browser timing) gzips each file at level 9 and sums them, and exits non-zero when a
// route is over. A route's files are what scripts/route_js.mjs reads from its built page: every script it names or
// preloads, every island's component and renderer, the chunks those import, and its inline scripts, which are written to
// node_modules/.cache/size-limit-routes/ because size-limit measures files. A KB here is 1,024 bytes (`KiB` to size-limit,
// whose `kB` is 1,000), the unit docs/pins.md's measurements use.
//
// The budgets are scripts/route_groups.json's, one row per route family in three groups, and scripts/route_groups.mjs
// turns them into checks (its header says how each is measured):
//   citable      0 KB of JavaScript on every detail, claim, conditions and other record page (08 S8.1 row 1), and the
//                detail page's total weight, fonts included, <= 120 KB (row 3)
//   interactive  the landing's 40 KB (10's Landing row, P2-S4-T08), and the other pages that ship JavaScript, measured
//   atlas        <= 120 KB of JavaScript gzipped on /atlas/ (row 2)
// A built page no family claims fails, as does a family with no built page that is not pending the task that routes it.
// The detail pages exist only over the draft preview, since no entry is published yet, so the build the gate reads is
// the preview's, as site/playwright.config.ts builds it and pr-validate.yml's size-budgets job does:
//
//   uv run python scripts/preview_corpus.py --out build/preview
//   cd site && UAIBI_CORPUS=../build/preview/corpus.json UAIBI_SITE_DRAFTS=1 npm run build && npx size-limit
//
// The ledger names a .size-limit.json. A static file cannot name a route's files, which are content-hashed chunks found
// only by reading the built page, so the budgets are data in scripts/route_groups.json and this file is what reads the
// build; a .size-limit.json beside it would also come first in size-limit's config search and shadow it.
//
// UAIBI_SIZE_FIXTURE=detail-js measures test/fixtures/size-detail-js.mjs's copy of dist/ instead, in which the first
// detail page loads 1,024 bytes of JavaScript: the citable check for /benchmarks/{id}/ fails, and size-limit exits 1.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sizeLimitChecks } from '../scripts/route_groups.mjs';

const SITE = fileURLToPath(new URL('.', import.meta.url));
const CACHE = join(SITE, 'node_modules', '.cache');
const FIXTURES = { 'detail-js': './test/fixtures/size-detail-js.mjs' };

let dist = join(SITE, 'dist');
const fixture = process.env.UAIBI_SIZE_FIXTURE;
if (fixture) {
  if (!(fixture in FIXTURES)) throw new Error(`UAIBI_SIZE_FIXTURE=${fixture}: no such fixture (have: ${Object.keys(FIXTURES).join(', ')})`);
  const out = join(CACHE, 'size-limit-fixture', fixture);
  const { writeDetailJs } = await import(FIXTURES[fixture]);
  writeDetailJs(dist, out);
  dist = out;
}

export default sizeLimitChecks({ dist, cache: join(CACHE, 'size-limit-routes'), from: SITE });
