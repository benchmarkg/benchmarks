// site/test/fixtures/size-detail-js.mjs -- P2-S8-T01 (08 S8.1). The fixture that adds 1 KB of JavaScript to a detail
// route, to show the size gate turns red. It writes a copy of the built site in which one detail page, the first
// /benchmarks/{id}/ in route order, loads a 1,024-byte module script; site/.size-limit.js measures that copy instead of
// dist/ when UAIBI_SIZE_FIXTURE=detail-js names it, as UAIBI_SITE_FIXTURES names test pages to astro.config.mjs:
//
//   cd site && UAIBI_SIZE_FIXTURE=detail-js npx size-limit     # exits 1: that detail route is 1,024 B over its 0 B
//
// The copy is hard links into dist/ (a plain copy where a link fails), so it costs next to no disk or time, and the one
// page it changes is unlinked and written anew, so dist/ itself is never touched. test/size-budgets.test.mjs runs it.
import { copyFileSync, linkSync, mkdirSync, readdirSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { builtRoutes, routeRegExp } from '../../../scripts/route_groups.mjs';
import { pagePath } from '../../../scripts/route_js.mjs';

export const DETAIL = '/benchmarks/{id}/';
export const SCRIPT = '/_astro/size-fixture-detail.js';
const HEAD = '// P2-S8-T01 fixture: 1 KB of JavaScript on a detail page, which 08 S8.1 holds to 0 KB\nglobalThis.uaibiSizeFixture = "';
const TAIL = '";\n';
/** Exactly 1,024 bytes of JavaScript (ASCII, so a character is a byte). */
export const ONE_KB = HEAD + 'x'.repeat(1024 - HEAD.length - TAIL.length) + TAIL;

function mirror(from, to) {
  mkdirSync(to, { recursive: true });
  for (const d of readdirSync(from, { withFileTypes: true })) {
    const [src, dst] = [join(from, d.name), join(to, d.name)];
    if (d.isDirectory()) mirror(src, dst);
    else {
      try {
        linkSync(src, dst);
      } catch {
        copyFileSync(src, dst);
      }
    }
  }
}

/** Write into `out` the build in `dist` with ONE_KB loaded by its first detail page; returns {route, script}. */
export function writeDetailJs(dist, out) {
  const route = builtRoutes(dist).find((r) => routeRegExp(DETAIL).test(r));
  if (route == null) throw new Error(`${dist} has no ${DETAIL} page to add JavaScript to: build the site over the draft preview`);
  rmSync(out, { recursive: true, force: true });
  mirror(dist, out);
  const page = pagePath(out, route);
  const html = readFileSync(page, 'utf8');
  if (!html.includes('</head>')) throw new Error(`${route} has no </head> to add a script before`);
  unlinkSync(page);                                   // a hard link into dist/: writing through it would change dist/ too
  writeFileSync(page, html.replace('</head>', `<script type="module" src="${SCRIPT}"></script></head>`));
  writeFileSync(join(out, ...SCRIPT.split('/').filter(Boolean)), ONE_KB);
  return { route, script: SCRIPT };
}
