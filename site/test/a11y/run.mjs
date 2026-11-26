#!/usr/bin/env node
// site/test/a11y/run.mjs -- P2-S8-T03 (09 S8, S13). `npm run test:a11y`, the accessibility harness, from site/:
//
//   npm run test:a11y                     every archetype in the four modes, the job's run (tests/a11y.spec.ts)
//   npm run test:a11y -- /benchmarks/     only the routes named, in the four modes: an archetype's route against its
//                                         baseline (test/a11y/baseline.json), any other built route against none
//
// Playwright takes a positional argument as a filter on spec files, not as a page, so the routes reach the spec as
// UAIBI_A11Y_ROUTES. Everything else about the run is playwright.config.ts's: its server, and UAIBI_SITE_BUILT=1 to
// preview a site already built.
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const routes = process.argv.slice(2);
const bad = routes.filter((r) => !/^\/[^\s,]*$/.test(r));
if (bad.length > 0) {
  console.error(`test:a11y: ${bad.join(', ')}: a route is a path from the site's root, like /benchmarks/`);
  process.exit(2);
}
const cli = createRequire(import.meta.url).resolve('@playwright/test/cli');
const run = spawnSync(process.execPath, [cli, 'test', 'tests/a11y.spec.ts'], {
  cwd: fileURLToPath(new URL('../../', import.meta.url)),
  env: { ...process.env, UAIBI_A11Y_ROUTES: routes.join(',') },
  stdio: 'inherit',
});
process.exit(run.status ?? 1);
