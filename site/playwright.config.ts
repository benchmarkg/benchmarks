// site/playwright.config.ts -- P2-S2-T07. The site's own browser tests (site/tests/), run from site/:
//
//   cd site && npx playwright test tests/theme.spec.ts
//
// @playwright/test is the repository root's (package.json, pinned there); Node resolves it up the tree. The
// server is the site built with UAIBI_SITE_FIXTURES=theme, which routes test/fixtures/theme.astro at
// /_fixtures/theme (astro.config.mjs), previewed on 4322 so it never collides with the root e2e suite's 4321.
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests',
  fullyParallel: true,
  reporter: 'list',
  use: { baseURL: 'http://localhost:4322' },
  webServer: {
    command: 'npm run build && npm run preview -- --port 4322',
    url: 'http://localhost:4322/_fixtures/theme',
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      UAIBI_SITE_FIXTURES: 'theme',
      ASTRO_TELEMETRY_DISABLED: '1',
      // Astro 7's preview detaches into a background daemon when it detects a coding agent; keep it in the
      // foreground where Playwright can stop it (the root playwright.config.ts explains the same setting).
      ASTRO_PREVIEW_BACKGROUND: '0',
    },
  },
});
