// site/.size-limit.js -- P2-S4-T08 (08 S8.1, 10 "Performance budget"). The per-route size gate, run over a built site:
//
//   cd site && npm run build && npx size-limit
//
// 08 S8.1 makes the route budgets blocking because they are deterministic, computed from artifacts: size-limit
// (@size-limit/file, no bundler and no browser timing) gzips each file at level 9 and sums them, and exits non-zero when a
// route is over. A route's files are what scripts/route_js.mjs reads from its built page: every script it names or
// preloads, every island's component and renderer, the chunks those import, and its inline scripts, which are written to
// node_modules/.cache/size-limit-routes/ because size-limit measures files. A KB here is 1,024 bytes (`KiB` to size-limit,
// whose `kB` is 1,000), the unit docs/pins.md's measurements use.
//
// One route so far, the landing, which P2-S4-T08 needs measured:
//   /   10's Landing row: "JS shipped <= 40 KB" over "Data fetched: facets.json 36 KB gz". The 40 KB is the JavaScript
//       alone; facets.json is the data column, counted beside it rather than in it (islands/search/lexical.ts holds the
//       file to its 36 KB), and the landing fetches no artifact at all: its counts are inlined at build time (08 S4.3,
//       pages/index.astro). facets.json's own size is not a blocking check here, because 08 S8.1 never blocks a deploy on
//       an artifact's size ("warn at 1.2 MB brotli ... never block the deploy").
// P2-S8-T01 adds the route groups 08 S8.1 names (0 KB on detail, claim and conditions routes; the Atlas <= 120 KB; detail
// page weight <= 120 KB including fonts) and the CI job.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { globSafe, routeScripts } from '../scripts/route_js.mjs';

const SITE = fileURLToPath(new URL('.', import.meta.url));
const DIST = join(SITE, 'dist');
const CACHE = join(SITE, 'node_modules', '.cache', 'size-limit-routes');

const ROUTES = [
  { route: '/', name: '/ (landing): the JavaScript it ships, facets.json not counted', limit: '40 KiB' },
];

rmSync(CACHE, { recursive: true, force: true });
mkdirSync(CACHE, { recursive: true });

export default ROUTES.map(({ route, name, limit }) => {
  const { external, inline } = routeScripts(DIST, route);
  const slug = route.replace(/^\/|\/$/g, '').replace(/\//g, '--') || 'index';
  const written = inline.map((body, i) => {
    const file = join(CACHE, `${slug}.inline-${i + 1}.js`);
    writeFileSync(file, body);
    return file;
  });
  return { name, path: [...external, ...written].map((f) => globSafe(f, SITE)), gzip: true, limit };
});
