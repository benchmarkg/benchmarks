// site/playwright.config.ts -- P2-S2-T07. The site's own browser tests (site/tests/), run from site/:
//
//   cd site && npx playwright test tests/theme.spec.ts
//   cd site && npx playwright test tests/detail-nojs.spec.ts --project=nojs      (P2-S3-T01)
//
// @playwright/test is the repository root's (package.json, pinned there); Node resolves it up the tree. The
// server is the site built with UAIBI_SITE_FIXTURES=theme,components, which routes test/fixtures/theme.astro and
// test/fixtures/components.astro at /_fixtures/<name> (astro.config.mjs), previewed on 4322 so it never collides with the root e2e suite's 4321.
//
// The same build reads the draft preview corpus (P2-S3-T01): no entry is published yet, so the detail pages would
// be zero pages over build/corpus.json. scripts/preview_corpus.py writes every entry that passes tier 1, drafts
// included, with the adoption artifact beside it, into build/preview/, and UAIBI_SITE_DRAFTS=1 is what lets the site
// build from a preview at all (src/lib/corpus.ts). One server for both, because two `astro build`s of one project
// at once share .astro/ and would race.
//
// Two projects: `js` runs every spec but the citable pages'; `nojs` runs those with JavaScript disabled in the
// browser, because a detail page that needs JavaScript to be read has failed (08 S4.3).
import { defineConfig } from '@playwright/test';

// the specs that read the site with JavaScript off: the detail page (P2-S3-T01) and its provenance drill-down (P2-S3-T02)
const NOJS = /(detail-nojs|provenance)\.spec\.ts$/;

export default defineConfig({
  testDir: 'tests',
  fullyParallel: true,
  reporter: 'list',
  use: { baseURL: 'http://localhost:4322' },
  projects: [
    { name: 'js', testIgnore: NOJS },
    { name: 'nojs', testMatch: NOJS, use: { javaScriptEnabled: false } },
  ],
  webServer: {
    command: 'uv run python ../scripts/preview_corpus.py --out ../build/preview && npm run build && npm run preview -- --port 4322',
    url: 'http://localhost:4322/_fixtures/theme',
    reuseExistingServer: false,
    timeout: 300_000,
    env: {
      UAIBI_SITE_FIXTURES: 'theme,components,provenance',
      UAIBI_CORPUS: '../build/preview/corpus.json',
      UAIBI_SITE_DRAFTS: '1',
      ASTRO_TELEMETRY_DISABLED: '1',
      // Astro 7's preview detaches into a background daemon when it detects a coding agent; keep it in the
      // foreground where Playwright can stop it (the root playwright.config.ts explains the same setting).
      ASTRO_PREVIEW_BACKGROUND: '0',
    },
  },
});
